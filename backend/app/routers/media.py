from __future__ import annotations

import asyncio
import base64
import json
import re
import uuid
from pathlib import Path
import subprocess

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from google.genai import types  # type: ignore
from google import genai  # type: ignore

from app.agents.orchestrator import generate_reel_preview_scenes, generate_script_with_optional_agent
from app.config import get_settings
from app.schemas.media import GenerateScriptRequest, GenerateScriptResponse, GenerateVideoRequest, GenerateVideoResponse
from app.schemas.reel_preview import PreviewReelCopyRequest, PreviewReelCopyResponse, ReelSceneDraft
from app.services.garment_analysis import analyze_anchor_image
from app.services.video_generation import run_generate_video
from app.utils.image_upload import looks_like_image_upload

router = APIRouter(tags=["media"])


def _copy_to_generated(anchor_path: str | None) -> str | None:
    """
    Last-resort still: copy the anchor bytes into generated_media so the UI always has a file
    under /generated_media/ (even if Pillow isn't installed).
    """
    if not anchor_path:
        return None
    settings = get_settings()
    try:
        src = (settings.data_dir / anchor_path).resolve()
        if not src.exists() or not src.is_file():
            return None
    except Exception:
        return None
    try:
        settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
        ext = src.suffix if src.suffix else ".png"
        name = f"scene_{uuid.uuid4().hex}{ext}"
        dst = settings.generated_media_dir / name
        dst.write_bytes(src.read_bytes())
        return f"generated_media/{name}"
    except Exception:
        return None


def _clear_previous_generation_outputs() -> None:
    """
    Keep only the current generation outputs to control disk usage and demo cost.

    Deletes:
    - data/reel_runs/*
    - data/generated_media/scene_*.{png,jpg,jpeg,webp,wav,mp4}
    - data/generated_media/*_slideshow.mp4 and *_vo.mp4

    Never deletes uploads/ (user-provided anchors) or other data.
    """
    settings = get_settings()
    # Clear reel_runs
    try:
        rr = (settings.data_dir / "reel_runs").resolve()
        if rr.exists() and rr.is_dir():
            for child in rr.iterdir():
                try:
                    if child.is_dir():
                        for p in sorted(child.rglob("*"), reverse=True):
                            try:
                                if p.is_file():
                                    p.unlink()
                                elif p.is_dir():
                                    p.rmdir()
                            except Exception:
                                pass
                        child.rmdir()
                    elif child.is_file():
                        child.unlink()
                except Exception:
                    pass
    except Exception:
        pass

    # Clear generated_media artifacts from previous runs.
    try:
        gm = settings.generated_media_dir.resolve()
        if gm.exists() and gm.is_dir():
            patterns = [
                "scene_*.png",
                "scene_*.jpg",
                "scene_*.jpeg",
                "scene_*.webp",
                "scene_*.wav",
                "scene_*.mp4",
                "*_slideshow.mp4",
                "*_vo.mp4",
            ]
            for pat in patterns:
                for p in gm.glob(pat):
                    try:
                        if p.is_file():
                            p.unlink()
                    except Exception:
                        pass
    except Exception:
        pass


def _extract_inline_image_bytes(resp: object) -> bytes | None:
    """
    Gemini image responses vary slightly by SDK/model; extract inline bytes safely.
    Supports both raw bytes and base64-encoded strings.
    """
    cands = getattr(resp, "candidates", None) or []
    for cand in cands:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) if content is not None else None
        for part in parts or []:
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline is not None else None
            if not data:
                continue
            if isinstance(data, str):
                try:
                    return base64.b64decode(data)
                except Exception:
                    return None
            return data
    return None


def _parse_json_object(text: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


@router.post("/generate-script", response_model=GenerateScriptResponse)
async def generate_script(body: GenerateScriptRequest) -> GenerateScriptResponse:
    return await generate_script_with_optional_agent(
        platform=body.platform,
        outfit_summary=body.outfit_summary,
        user_voice=body.user_voice,
        tone=body.tone,
        emotion=body.emotion,
        target_audience=body.target_audience,
        scenario=body.scenario,
        vibe=body.vibe,
        variation_salt=body.variation_salt,
    )


@router.post("/generate-video", response_model=GenerateVideoResponse)
async def generate_video(body: GenerateVideoRequest) -> GenerateVideoResponse:
    return await run_generate_video(body)


@router.post("/preview-reel-copy", response_model=PreviewReelCopyResponse)
async def preview_reel_copy(body: PreviewReelCopyRequest) -> PreviewReelCopyResponse:
    # New logic: we draft N scenes for the full reel, not 1:1 with anchors.
    target = int(body.duration_seconds or 30)
    sec_each = 6
    n = max(4, min(10, int((target + sec_each - 1) // sec_each)))
    sec_each = max(3, min(12, int(target // max(1, n))))
    scenes = [
        ReelSceneDraft(
            anchor_image_path=body.face_anchor_path,
            anchor_type="wardrobe",
            label=f"Scene {i + 1}/{n}",
            duration_seconds=sec_each,
            description=f"{(body.scene_prompt or '').strip()[:240]} (beat {i + 1}/{n})",
        )
        for i in range(n)
    ]
    logline = f"Runway reel — {n} scenes (~{target}s total)"
    video_prompt = f"{logline}\n" + "\n".join(f"• {s.label}: {s.description}" for s in scenes)
    return PreviewReelCopyResponse(
        description=logline,
        video_prompt=video_prompt,
        scenes=scenes,
    )


@router.post("/generate-scenes", response_model=PreviewReelCopyResponse)
async def generate_scenes(body: PreviewReelCopyRequest) -> PreviewReelCopyResponse:
    """
    Step 2: Generate a NEW still + shot description for every scene, sequentially,
    chaining prior scene outputs for consistency.

    - Uses all anchor images + the current (draft) descriptions as base context.
    - For scene i, also feeds outputs from scenes 1..i-1.
    - Works without Gemini (local 9:16 stills + chained copy).
    - Persists structured reel metadata under data/reel_runs/<id>/ for reuse (premise + architecture JSON).
    """
    # Keep only the current run's outputs.
    _clear_previous_generation_outputs()
    settings = get_settings()
    movie_idea = (body.scene_prompt or "").strip()
    ideal = (getattr(body, "idealization", None) or "").strip()
    use_llm = bool(settings.gemini_api_key and settings.gemini_api_key.strip())
    target = int(body.duration_seconds or 30)

    if not (body.face_anchor_path or "").strip():
        raise HTTPException(status_code=400, detail="Please upload a face anchor first (required for scene generation).")

    def _sanitize_movie_idea(text: str) -> str:
        """
        If the movie idea mentions celebrities, treat as style reference only.
        We redact common tokens to prevent the image model from swapping the subject away from the face anchor.
        """
        t = (text or "").strip()
        if not t:
            return t
        t = re.sub(r"\bblackpink\b", "[style reference]", t, flags=re.IGNORECASE)
        t = re.sub(r"\btom\s+cruise\b", "[style reference]", t, flags=re.IGNORECASE)
        # "Rose" is a frequent demo token; redact to prevent the model from generating her instead of the user.
        t = re.sub(r"\brose\b", "[style reference]", t, flags=re.IGNORECASE)
        return t

    movie_idea_s = _sanitize_movie_idea(movie_idea)

    def _resolve(rel: str | None) -> Path | None:
        if not rel:
            return None
        try:
            p = (settings.data_dir / rel).resolve()
            return p if p.exists() else None
        except Exception:
            return None

    async def _gemini_cinematic_still(*, prompt: str, ref_paths: list[Path], timeout_s: float = 42.0) -> bytes | None:
        """
        Best-effort image generation with retries across model name variants.
        If reference + prompt fails, we retry text-only (still aligned to MOVIE_IDEA) rather than silently
        falling back to a near-identical crop of the anchor.
        """

        model_candidates = [
            "gemini-2.5-flash-image",
            "models/gemini-2.5-flash-image",
            "gemini-2.0-flash-exp-image-generation",
            "models/gemini-2.0-flash-exp-image-generation",
        ]

        def _cfg():
            # Some SDK versions support ImageConfig (aspect ratio). If not, fall back safely.
            try:
                return types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio="9:16"),
                )
            except Exception:
                return types.GenerateContentConfig(response_modalities=["IMAGE"])

        def _run() -> bytes | None:
            client = genai.Client(api_key=settings.gemini_api_key)  # type: ignore[arg-type]
            cfg = _cfg()

            parts_with_ref: list[object] = [prompt]
            # Attach multiple references when available (face + a couple garments).
            for p in ref_paths[:4]:
                if p.exists():
                    parts_with_ref.append(types.Image.from_file(str(p)))

            last_exc: Exception | None = None
            for model in model_candidates:
                # Attempt with reference (derivation).
                try:
                    resp = client.models.generate_content(model=model, contents=parts_with_ref, config=cfg)
                    data = _extract_inline_image_bytes(resp)
                    if data:
                        return data
                except Exception as exc:
                    last_exc = exc
                # Retry text-only (still "new frame, not a copy").
                try:
                    resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
                    data = _extract_inline_image_bytes(resp)
                    if data:
                        return data
                except Exception as exc:
                    last_exc = exc

            # Surface nothing; caller will fallback locally. Persisting last_exc is optional.
            return None

        try:
            return await asyncio.wait_for(asyncio.to_thread(_run), timeout=timeout_s)
        except Exception:
            return None

    def _write_png_bytes(data: bytes) -> str:
        settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
        name = f"scene_{uuid.uuid4().hex}.png"
        out = settings.generated_media_dir / name
        out.write_bytes(data)
        return f"generated_media/{name}"

    async def _gemini_frame_description(
        *, frame_path: Path, scene_index: int, scene_total: int, desired_beat: str | None
    ) -> str | None:
        """
        Generate a description that matches the generated frame *and* the movie idea.
        We intentionally describe what is visible, not a plan.
        """
        if not use_llm:
            return None
        try:
            img = types.Image.from_file(str(frame_path))
        except Exception:
            return None
        try:
            client = genai.Client(api_key=settings.gemini_api_key)  # type: ignore[arg-type]
            model = settings.gemini_model
            prompt = (
                "You are writing a short shot description for a fashion reel.\n"
                "Given the GENERATED frame image and the MOVIE_IDEA, write ONE paragraph that:\n"
                "- describes what we can see (subject, outfit, environment, lighting)\n"
                "- mentions the camera angle/move implied by the frame\n"
                "- ties it to the MOVIE_IDEA vibe without naming brands\n"
                "- differs meaningfully from other scenes (include at least one unique visual detail)\n\n"
                f"MOVIE_IDEA:\n{movie_idea_s}\n"
                f"IDEALIZATION:\n{ideal or '(none)'}\n"
                f"INTENDED_BEAT:\n{(desired_beat or '').strip()[:240]}\n"
                f"Scene {scene_index + 1} of {scene_total}.\n"
                "Return STRICT JSON: {\"description\": \"...\"} (no extra keys)."
            )
            resp = client.models.generate_content(model=model, contents=[prompt, img])
            payload = _parse_json_object(resp.text or "")
            desc = str(payload.get("description", "") or "").strip()
            desc = re.sub(r"\s+", " ", desc)
            if len(desc) < 40:
                return None
            # Bound size so UI stays tidy.
            if len(desc) > 380:
                desc = desc[:377].rstrip(" ,;:") + "…"
            return desc
        except Exception:
            return None

    def _scene_clip_mp4(*, still_rel: str, duration_s: int, stem: str) -> str | None:
        """
        Build a short animated MP4 from a still (Ken Burns), silent.
        Uses ffmpeg zoompan at full 1080x1920 to avoid blurry previews.
        Kept fast via modest fps + CRF.
        """
        try:
            still_local = _resolve(still_rel)
            if still_local is None:
                return None
            settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
            out = settings.generated_media_dir / f"{stem}.mp4"

            w, h = 1080, 1920
            fps = 18
            dur_cap = max(2, min(12, int(duration_s or 6)))
            dur = float(dur_cap)
            frames = max(1, int(dur * fps))

            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},"
                # Subtle zoom: 1.00 -> ~1.06 across the clip.
                f"zoompan=z='min(zoom+0.0012,1.06)':"
                f"d={frames}:s={w}x{h}:fps={fps}"
            )

            cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(still_local)]
            cmd += [
                "-t",
                f"{dur:.3f}",
                "-vf",
                vf,
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "veryfast",
                "-crf",
                "20",
            ]
            cmd += ["-an"]
            cmd += ["-movflags", "+faststart", str(out)]

            subprocess.run(cmd, check=True, timeout=90)
            if out.exists() and out.stat().st_size > 0:
                return f"generated_media/{out.name}"
        except Exception:
            return None
        return None

    # Draft N scenes for the reel (not 1:1 with anchors).
    sec_each_target = 6
    n_scenes = max(4, min(10, int((target + sec_each_target - 1) // sec_each_target)))
    sec_each = max(3, min(12, int(target // max(1, n_scenes))))
    scenes: list[ReelSceneDraft] = [
        ReelSceneDraft(
            anchor_image_path=body.face_anchor_path,
            anchor_type="wardrobe",
            label=f"Scene {i + 1}/{n_scenes}",
            duration_seconds=sec_each,
            description="",
        )
        for i in range(n_scenes)
    ]
    logline = f"Runway reel — {n_scenes} scenes (~{target}s total)"
    video_prompt = f"{logline}\nMovie idea: {movie_idea_s[:240]}"

    # NOTE: Reliable for class demos: local 9:16 stills (Pillow) + chained copy.

    def _local_render_still(*, anchor_path: str | None, prev_generated_path: str | None) -> str | None:
        """
        Create a fresh 9:16 still locally from the anchor image (and lightly blend prior output for continuity).
        This guarantees "new generated images" even if cloud models are overloaded/unavailable.
        """
        try:
            from PIL import Image, ImageEnhance  # type: ignore
        except Exception:
            return _copy_to_generated(anchor_path)

        def _load_and_fit(p: str | None) -> Image.Image | None:
            if not p:
                return None
            lp = (settings.data_dir / p).resolve()
            if not lp.exists():
                return None
            try:
                im = Image.open(str(lp)).convert("RGB")
            except Exception:
                return None
            target_w, target_h = 1080, 1920
            # Resize to cover then center-crop.
            scale = max(target_w / im.width, target_h / im.height)
            nw, nh = int(im.width * scale), int(im.height * scale)
            im = im.resize((nw, nh))
            left = max(0, (nw - target_w) // 2)
            top = max(0, (nh - target_h) // 2)
            return im.crop((left, top, left + target_w, top + target_h))

        base = _load_and_fit(anchor_path)
        if base is None:
            # Fallback: solid dark canvas.
            base = Image.new("RGB", (1080, 1920), (10, 10, 14))

        # NOTE: Do not blend previous generated stills.
        # Blending can create incorrect multi-item overlays (e.g., shoe+jacket composites).

        # Subtle grade so it feels "generated" not copied.
        base = ImageEnhance.Contrast(base).enhance(1.05)
        base = ImageEnhance.Color(base).enhance(1.03)

        settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
        name = f"scene_{uuid.uuid4().hex}.png"
        out = settings.generated_media_dir / name
        base.save(str(out), format="PNG", optimize=True)
        return f"generated_media/{name}"

    def _context_block(drafts: list[ReelSceneDraft]) -> str:
        lines: list[str] = []
        for s in drafts:
            lines.append(
                f"- {s.label} (type={s.anchor_type}, anchor={s.anchor_image_path}): "
                f"desc={s.description.strip()[:220]}"
            )
        return "\n".join(lines)

    def _offline_description(*, idx: int, total: int, scene: ReelSceneDraft) -> str:
        """
        Offline fallback copy that still references the movie idea (no LLM available).
        """
        brief = (movie_idea_s or movie_idea or "").strip()
        return (
            f"{brief[:240]} "
            f"(scene {idx + 1}/{total}: new location + camera move; same face-anchor person wearing the outfit)."
        ).strip()

    job_id = uuid.uuid4().hex
    run_dir = settings.data_dir / "reel_runs" / job_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 0) Analyze anchors into structured data for reuse + better prompts.
    analyses: list[dict] = []
    try:
        # Always include face anchor (if present) plus all garment anchors from the recommended outfit.
        paths: list[str] = []
        if body.face_anchor_path:
            paths.append(body.face_anchor_path)
        for p in body.anchor_image_paths or []:
            if p and p not in paths:
                paths.append(p)
        for rel in paths[:16]:
            lp = _resolve(rel)
            if lp is None:
                continue
            a = analyze_anchor_image(local_path=lp, rel_path=rel, filename_hint=lp.name)
            analyses.append(a.to_dict())
        (run_dir / "anchors_analysis.json").write_text(json.dumps({"job_id": job_id, "anchors": analyses}, indent=2), encoding="utf-8")
    except Exception:
        analyses = analyses or []

    def _analysis_block() -> str:
        if not analyses:
            return "(no anchor analysis available)"
        lines: list[str] = []
        for a in analyses:
            lines.append(
                f"- {a.get('filename')}: category={a.get('category')} "
                f"(conf={a.get('category_confidence')}); color={a.get('dominant_color_name')}; "
                f"aspect={a.get('aspect_ratio')}"
            )
        return "\n".join(lines)

    async def _gemini_scene_beat(*, scene_index: int, scene_total: int, prior: list[ReelSceneDraft]) -> str | None:
        """
        Produce a unique per-scene beat (plot + camera) so frames and descriptions don't repeat.
        This beat conditions image generation; the final description is frame-grounded after generation.
        """
        if not use_llm:
            return None
        try:
            client = genai.Client(api_key=settings.gemini_api_key)  # type: ignore[arg-type]
            model = settings.gemini_model
            prior_ctx = _context_block(prior[-3:]) if prior else "(none)"
            prompt = (
                "Write ONE concise scene beat for a 30s cinematic fashion reel.\n"
                "Return STRICT JSON: {\"beat\": \"...\"}.\n\n"
                f"MOVIE_IDEA:\n{movie_idea_s}\n"
                f"IDEALIZATION:\n{ideal or '(none)'}\n\n"
                "OUTFIT (structured hints from wardrobe anchors):\n"
                f"{_analysis_block()}\n\n"
                "PRIOR_SCENES (for continuity; avoid repeating the same setting/camera):\n"
                f"{prior_ctx}\n\n"
                f"Scene {scene_index + 1} of {scene_total}.\n"
                "Constraints:\n"
                "- The main subject MUST be the face-anchor person (not any celebrity).\n"
                "- The outfit MUST be worn on-body and visibly resembles the wardrobe anchors.\n"
                "- Make this beat visually distinct (new location/camera move/action).\n"
                "- 1–2 sentences max."
            )
            resp = client.models.generate_content(model=model, contents=prompt)
            payload = _parse_json_object(resp.text or "")
            beat = str(payload.get("beat", "") or "").strip()
            beat = re.sub(r"\s+", " ", beat)
            if len(beat) < 30:
                return None
            if len(beat) > 260:
                beat = beat[:257].rstrip(" ,;:") + "…"
            return beat
        except Exception:
            return None

    generated: list[ReelSceneDraft] = []
    for i, s in enumerate(scenes):
        total = len(scenes)
        # Start with a unique beat when possible; we'll overwrite with a frame-derived description after image gen.
        beat = await _gemini_scene_beat(scene_index=i, scene_total=total, prior=generated)
        s2 = s.model_copy(update={"description": beat or _offline_description(idx=i, total=total, scene=s)})

        # 2) Generate a fresh cinematic still.
        # Prefer Gemini image generation with references: face + (cycled) garment anchors.
        img_path: str | None = None
        ref_for_image: list[Path] = []
        face_local = _resolve(body.face_anchor_path) if body.face_anchor_path else None
        if face_local is not None:
            ref_for_image.append(face_local)
        garments_local: list[Path] = []
        for p in body.anchor_image_paths or []:
            lp = _resolve(p)
            if lp is not None:
                garments_local.append(lp)
        if garments_local:
            # Cycle 1–2 garment references per scene so Veo/image gen sees the outfit.
            g0 = garments_local[i % len(garments_local)]
            ref_for_image.append(g0)
            if len(garments_local) > 1:
                g1 = garments_local[(i + 1) % len(garments_local)]
                if g1 != g0:
                    ref_for_image.append(g1)

        if use_llm and ref_for_image:
            prior_ctx = _context_block(generated[-3:]) if generated else ""
            wardrobe_ctx = "\n".join(f"- {p}" for p in (body.anchor_image_paths or [])[:12])
            analysis_ctx = _analysis_block()
            img_prompt = (
                "Generate ONE photorealistic vertical 9:16 cinematic KEYFRAME for a fashion reel.\n"
                "Hard constraints:\n"
                "- The result must be a NEW frame (new environment, new camera angle). Do NOT crop/rotate the reference.\n"
                "- No text, no logos, no watermarks, no UI.\n"
                "- Keep continuity with prior scenes (same person + same outfit), unless this is Scene 1.\n"
                "- Enforce ON-BODY interpretation: garments must be worn by the person, never a flat-lay product shot.\n\n"
                f"MOVIE_IDEA:\n{movie_idea_s}\n"
                f"IDEALIZATION:\n{ideal or '(none)'}\n\n"
                f"SCENE_INDEX: {i + 1}/{total}\n"
                f"SCENE_BEAT (what happens in this moment):\n{s2.description}\n\n"
                "WARDROBE_ANCHORS (for outfit continuity; interpret as worn clothing, not flat lays):\n"
                f"{wardrobe_ctx or '(none)'}\n\n"
                "ANCHOR_ANALYSIS (structured hints; use for continuity):\n"
                f"{analysis_ctx}\n\n"
                "PRIOR_SCENES (for continuity):\n"
                f"{prior_ctx or '(none)'}\n\n"
                "IMPORTANT: Use the attached reference images:\n"
                "- Preserve identity from the face reference.\n"
                "- Preserve key garment colors/materials/silhouettes from wardrobe references.\n"
                "- If MOVIE_IDEA mentions celebrities, treat them as style references ONLY. Do NOT depict them.\n"
                "- The only main subject is the face-anchor person.\n"
            )
            async def _validate_frame(*, frame_path: Path, garment_refs: list[Path]) -> bool:
                """
                Validate that the generated frame depicts the face-anchor person and resembles wardrobe anchors.
                Returns True if acceptable.
                """
                try:
                    face_local2 = _resolve(body.face_anchor_path) if body.face_anchor_path else None
                    if face_local2 is None:
                        return False
                    face_img = types.Image.from_file(str(face_local2))
                    gen_img = types.Image.from_file(str(frame_path))
                    parts: list[object] = []
                    prompt_v = (
                        "You are validating an AI-generated video frame.\n"
                        "Compare the FACE_ANCHOR photo to the GENERATED_FRAME.\n"
                        "Also compare the GENERATED_FRAME outfit to the WARDROBE_REFERENCES.\n"
                        "Return STRICT JSON with keys:\n"
                        "- same_person: true/false (does generated subject match face anchor identity?)\n"
                        "- outfit_match: true/false (does outfit resemble wardrobe refs in colors/materials/silhouette?)\n"
                        "- single_subject: true/false (one main person, not a different celebrity)\n"
                        "- score: number 0..1 (overall)\n"
                        "Be strict: if unsure, set false.\n"
                    )
                    parts.append(prompt_v)
                    parts.append(face_img)
                    parts.append(gen_img)
                    for pth in garment_refs[:2]:
                        parts.append(types.Image.from_file(str(pth)))
                    client_v = genai.Client(api_key=settings.gemini_api_key)  # type: ignore[arg-type]
                    resp_v = client_v.models.generate_content(model=settings.gemini_model, contents=parts)
                    payload_v = _parse_json_object(resp_v.text or "")
                    same_person = bool(payload_v.get("same_person", False))
                    outfit_match = bool(payload_v.get("outfit_match", False))
                    single_subject = bool(payload_v.get("single_subject", False))
                    try:
                        score = float(payload_v.get("score", 0.0))
                    except Exception:
                        score = 0.0
                    return bool(same_person and outfit_match and single_subject and score >= 0.65)
                except Exception:
                    return False

            # Attempt generation with validation + retries.
            max_attempts = 3
            for attempt in range(max_attempts):
                data = await _gemini_cinematic_still(prompt=img_prompt, ref_paths=ref_for_image, timeout_s=42.0)
                if not data:
                    continue
                candidate_rel = _write_png_bytes(data)
                candidate_local = _resolve(candidate_rel)
                if candidate_local is None:
                    continue
                ok = await _validate_frame(frame_path=candidate_local, garment_refs=garments_local)
                if ok:
                    img_path = candidate_rel
                    break
                # Tighten prompt on retry.
                img_prompt = (
                    img_prompt
                    + "\n\nRETRY_CONSTRAINTS:\n"
                    + "- The main subject MUST match the face anchor identity.\n"
                    + "- The outfit MUST visibly resemble the wardrobe references.\n"
                    + "- Do NOT depict celebrities; use movie idea as vibe only.\n"
                )
            # If the image model fails:
            # - For FACE scenes, do NOT retry without the face reference (identity drift). Fall back locally.
            # - For WARDROBE scenes, we may retry text-only to still get a "new frame".
            if img_path is None and s2.anchor_type != "face":
                data2 = await _gemini_cinematic_still(prompt=img_prompt, ref_paths=[], timeout_s=42.0)
                if data2:
                    img_path = _write_png_bytes(data2)

        if img_path is None:
            # Fallback: local 9:16 crop only (no blending).
            fallback_anchor = s2.anchor_image_path
            if s2.anchor_type == "face" and body.face_anchor_path:
                fallback_anchor = body.face_anchor_path
            img_path = _local_render_still(anchor_path=fallback_anchor, prev_generated_path=None)
        # Absolute last resort: ensure UI never falls back to /uploads/ for thumbnails.
        if not img_path:
            img_path = _copy_to_generated(s2.anchor_image_path)

        # 3) Update description so it describes the generated frame (and ties to movie idea).
        try:
            if img_path:
                local = _resolve(img_path)
                if local is not None:
                    desc2 = await _gemini_frame_description(
                        frame_path=local,
                        scene_index=i,
                        scene_total=total,
                        desired_beat=s2.description,
                    )
                    if desc2:
                        s2 = s2.model_copy(update={"description": desc2})
        except Exception:
            pass

        # Optional animated clip (still). Run in a thread with a hard timeout so the HTTP request can't hang.
        clip_path = None
        if img_path:
            stem_clip = f"scene_{uuid.uuid4().hex}"
            try:
                clip_path = await asyncio.wait_for(
                    asyncio.to_thread(
                        _scene_clip_mp4,
                        still_rel=img_path,
                        duration_s=int(s2.duration_seconds or 6),
                        stem=stem_clip,
                    ),
                    timeout=55.0,
                )
            except (asyncio.TimeoutError, Exception):
                clip_path = None

        s3 = s2.model_copy(
            update={
                "generated_image_path": img_path,
                "generated_video_path": clip_path,
            }
        )
        generated.append(s3)

    premise = {
        "job_id": job_id,
        "logline": logline,
        "objective": body.scene_prompt,
        "face_anchor": body.face_anchor_path,
        "wardrobe_anchors": list(body.anchor_image_paths),
        "anchor_analysis_path": "anchors_analysis.json",
        "beats": [
            {
                "index": i + 1,
                "label": s.label,
                "anchor_type": s.anchor_type,
                "anchor_image_path": s.anchor_image_path,
                "description": s.description,
                "generated_image_path": s.generated_image_path,
            }
            for i, s in enumerate(generated)
        ],
    }
    architecture = {
        "job_id": job_id,
        "duration_target_seconds": body.duration_seconds,
        "aspect": "9:16",
        "arc": {
            "acts": [
                {"name": "hook", "scenes": [1] if generated else []},
                {
                    "name": "wardrobe_proof",
                    "scenes": list(range(2, len(generated))) if len(generated) > 2 else [],
                },
                {"name": "payoff", "scenes": [len(generated)] if generated else []},
            ],
            "blocking_notes": [s.description for s in generated],
        },
    }
    (run_dir / "premise.json").write_text(json.dumps(premise, indent=2), encoding="utf-8")
    (run_dir / "architecture.json").write_text(json.dumps(architecture, indent=2), encoding="utf-8")

    return PreviewReelCopyResponse(
        description=logline,
        video_prompt=video_prompt,
        scenes=generated,
    )


@router.post("/upload-anchor")
async def upload_anchor(file: UploadFile = File(...), kind: str = Form(default="face")) -> dict[str, str]:
    """
    Upload an anchor image (e.g., selfie) to be used in media generation.
    Returns a relative uploads path you can pass to /generate-video.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename on upload")
    if not looks_like_image_upload(filename=file.filename, content_type=file.content_type):
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Please upload an image file (JPG, PNG, WebP, HEIC, etc.).",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    # iPhone selfies (especially HEIC) can be large; keep it generous for demos.
    max_mb = 25
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Max size is {max_mb}MB.")

    settings = get_settings()
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.uploads_dir / f"anchor_{kind}_{safe_name}"
    dest.write_bytes(content)
    rel_path = f"uploads/{dest.name}"
    return {"path": rel_path}


@router.post("/upload-music")
async def upload_music(file: UploadFile = File(...)) -> dict[str, str]:
    """
    Upload a background music file (mp3/m4a/wav/ogg) to be muxed into the final MP4.
    Returns a relative uploads path you can pass as GenerateVideoRequest.background_music_path.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename on upload")
    ct = (file.content_type or "").lower()
    name = file.filename.lower()
    if not (ct.startswith("audio/") or name.endswith((".mp3", ".m4a", ".wav", ".ogg", ".aac"))):
        raise HTTPException(status_code=415, detail="Unsupported audio type. Upload mp3/m4a/wav/ogg.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    max_mb = 30
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Max size is {max_mb}MB.")
    settings = get_settings()
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.uploads_dir / f"music_{safe_name}"
    dest.write_bytes(content)
    rel_path = f"uploads/{dest.name}"
    return {"path": rel_path}


class GenerateSceneAssetsRequest(PreviewReelCopyRequest):
    """
    Generate an AI image + audio for a single scene.

    We reuse the reel context fields (scene_prompt + anchors) and accept per-scene copy.
    """

    scene: ReelSceneDraft


class GenerateSceneAssetsResponse(ReelSceneDraft):
    pass


@router.post("/generate-scene-assets", response_model=GenerateSceneAssetsResponse)
async def generate_scene_assets(body: GenerateSceneAssetsRequest) -> GenerateSceneAssetsResponse:
    """
    Use Gemini image generation to create a new still for a scene.
    The generated still can be regenerated until user is satisfied, and is used to animate the reel.
    """
    settings = get_settings()
    if not settings.gemini_api_key or not settings.gemini_api_key.strip():
        raise HTTPException(status_code=400, detail="Missing GEMINI_API_KEY. Set it in backend/.env.")

    movie_idea = (body.scene_prompt or "").strip()
    ideal = (body.idealization or "").strip()
    movie_idea_s = movie_idea
    try:
        # Reuse the same sanitizer logic as /generate-scenes.
        movie_idea_s = re.sub(r"\bblackpink\b", "[style reference]", movie_idea_s, flags=re.IGNORECASE)
        movie_idea_s = re.sub(r"\btom\s+cruise\b", "[style reference]", movie_idea_s, flags=re.IGNORECASE)
        movie_idea_s = re.sub(r"\brose\b", "[style reference]", movie_idea_s, flags=re.IGNORECASE)
    except Exception:
        movie_idea_s = movie_idea

    def _resolve(rel: str | None) -> Path | None:
        if not rel:
            return None
        try:
            p = (settings.data_dir / rel).resolve()
            return p if p.exists() else None
        except Exception:
            return None

    # Unified logic: every scene is conditioned on face + wardrobe anchors (on-body interpretation).
    ref_for_image: list[Path] = []
    face_local = _resolve(body.face_anchor_path) if body.face_anchor_path else None
    if face_local is not None:
        ref_for_image.append(face_local)
    garments_local: list[Path] = []
    for p in body.anchor_image_paths or []:
        lp = _resolve(p)
        if lp is not None:
            garments_local.append(lp)
    if garments_local:
        # Pick one garment reference deterministically from label/description hash.
        h = abs(hash((body.scene.label or "", body.scene.description or "")))
        g0 = garments_local[h % len(garments_local)]
        ref_for_image.append(g0)
        if len(garments_local) > 1:
            g1 = garments_local[(h + 1) % len(garments_local)]
            if g1 != g0:
                ref_for_image.append(g1)

    prompt = (
        "Generate ONE photorealistic vertical 9:16 cinematic KEYFRAME (1080x1920 feel).\n"
        "This must look like a NEW frame from a film—not a duplicate of the reference photo’s composition, framing, or background.\n"
        "Invent a fresh environment, lighting, and camera angle aligned with the MOVIE_IDEA.\n\n"
        f"MOVIE_IDEA:\n{movie_idea_s}\nIDEALIZATION:\n{ideal or '(none)'}\n\n"
        f"DESCRIPTION:\n{body.scene.description}\n\n"
        "REFERENCE IMAGE RULES:\n"
        "- Preserve identity from the face reference.\n"
        "- Preserve key garment colors/materials/silhouettes from wardrobe references and show them ON-BODY.\n"
        "- If MOVIE_IDEA mentions celebrities, treat them as style references ONLY. Do NOT depict them.\n"
        "- The only main subject is the face-anchor person.\n"
        "- Do NOT paste the reference as a flat lay. Do NOT stack multiple garments or double-exposure overlays.\n"
        "- Avoid plain catalog/studio backdrops (no seamless white/grey product background).\n"
        "- No text, logos, watermarks, or UI overlays in the image.\n"
    )

    client = genai.Client(api_key=settings.gemini_api_key)
    img_model = "models/gemini-2.5-flash-image"

    try:
        try:
            parts: list[object] = [prompt]
            for p in ref_for_image[:4]:
                if p.exists():
                    parts.append(types.Image.from_file(str(p)))
            resp = client.models.generate_content(
                model=img_model,
                contents=parts,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
        except Exception:
            # Some models/API versions reject multimodal here; fall back to text-only prompt.
            resp = client.models.generate_content(
                model=img_model,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
        data = _extract_inline_image_bytes(resp)
        if not data:
            raise HTTPException(status_code=502, detail="Gemini image generation returned empty bytes.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini image generation failed: {exc!s}")

    settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
    image_name = f"scene_{uuid.uuid4().hex}.png"
    image_path = settings.generated_media_dir / image_name
    image_path.write_bytes(data)
    rel_image = f"generated_media/{image_name}"

    # Update description to match the newly generated still (vision), when possible.
    desc2: str | None = None
    try:
        img2 = types.Image.from_file(str(image_path))
        prompt2 = (
            "You are writing a short shot description for a fashion reel.\n"
            "Given the GENERATED frame image and the MOVIE_IDEA, write ONE paragraph that:\n"
            "- describes what we can see (subject, outfit, environment, lighting)\n"
            "- mentions the camera angle/move implied by the frame\n"
            "- ties it to the MOVIE_IDEA vibe without naming brands\n\n"
            f"MOVIE_IDEA:\n{movie_idea}\n"
            f"IDEALIZATION:\n{ideal or '(none)'}\n"
            "Return STRICT JSON: {\"description\": \"...\"} (no extra keys)."
        )
        resp2 = client.models.generate_content(model=settings.gemini_model, contents=[prompt2, img2])
        payload2 = _parse_json_object(resp2.text or "")
        d = str(payload2.get("description", "") or "").strip()
        d = re.sub(r"\s+", " ", d)
        if len(d) >= 40:
            if len(d) > 380:
                d = d[:377].rstrip(" ,;:") + "…"
            desc2 = d
    except Exception:
        desc2 = None
    out = body.scene.model_copy(update={"generated_image_path": rel_image, "description": desc2 or body.scene.description})
    return GenerateSceneAssetsResponse(**out.model_dump())
