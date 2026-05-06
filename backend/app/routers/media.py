from __future__ import annotations

import asyncio
import base64
import json
import math
import re
import uuid
import random
import hashlib
from pathlib import Path
import subprocess
from typing import Literal

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


def _genai_image_from_local_path(path: Path) -> types.Image:
    """
    Build a google-genai Image from disk.

    The SDK defines `Image.from_file(*, location=..., mime_type=...)`. Positional calls raise
    TypeError; those errors were previously swallowed by broad try/except blocks, breaking every
    multimodal image request (face / wardrobe references).
    """
    return types.Image.from_file(location=str(path.resolve()))


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
    - (no longer deletes generated_media artifacts automatically)

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

    # IMPORTANT:
    # Previously we cleared generated_media at the start of each run, but the UI persists scene URLs
    # (and also requests thumbnails/videos asynchronously). Deleting files here causes 404s and makes
    # "Generate scenes" appear broken even when the request succeeds.
    #
    # We keep generated_media artifacts for demo reliability. If disk becomes a concern, add a separate
    # maintenance command or TTL-based cleanup outside the request path.


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
            if getattr(part, "thought", None) is True:
                continue
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline is not None else None
            if data:
                if isinstance(data, str):
                    try:
                        return base64.b64decode(data)
                    except Exception:
                        continue
                return data
            try:
                gimg = part.as_image()
                if gimg is not None:
                    ib = getattr(gimg, "image_bytes", None)
                    if ib:
                        return ib
            except Exception:
                pass
    return None


def _parse_json_object(text: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _story_arc_for_reel(total: int, seed: str) -> list[dict[str, str]]:
    """
    Deterministic narrative spine shared by LLM beats, image prompts, and offline copy.
    Each entry is an act hint (not literal on-screen text) so scenes progress like a short film.
    """
    pool: list[dict[str, str]] = [
        {
            "phase": "departure",
            "hook": "Enclosed transit: tighter framing, practicals, body language leaning into the next beat.",
        },
        {
            "phase": "threshold",
            "hook": "Arrival at a threshold—doors, glass, escalators—wider geography, reflective surfaces, purposeful stride.",
        },
        {
            "phase": "connection",
            "hook": "Public rhythm: a fleeting human beat (glance, gesture, service counter) that advances the journey.",
        },
        {
            "phase": "complication",
            "hook": "Pressure rises: contrasty light, faster blocking, environmental tension without violence.",
        },
        {
            "phase": "resolve",
            "hook": "Breathing room: softer light, slower camera, wardrobe reads clearly before the final move.",
        },
        {
            "phase": "return",
            "hook": "Closing loop—familiar ground or a decisive end beat that completes the arc while proving the outfit.",
        },
    ]
    if total <= 0:
        return []
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)
    start = h % len(pool)
    out: list[dict[str, str]] = []
    for i in range(total):
        out.append(dict(pool[(start + i) % len(pool)]))
    return out


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
    # Course MVP: fixed 4-scene reel so the demo flow is predictable.
    target = int(body.duration_seconds or 30)
    n = 4
    sec_each = max(6, min(10, int(math.ceil(target / max(1, n)))))
    scenes = [
        ReelSceneDraft(
            # IMPORTANT:
            # Do not set Scene 1 thumbnail to the raw face anchor.
            # Anchors are references for generation; the scene still is generated later.
            anchor_image_path=None,
            anchor_type="none",
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
    Step 2 (two-step workflow): Generate a NEW still + shot description for every scene, sequentially,
    chaining prior scene outputs for continuity.

    IMPORTANT (Scene 1 establishing shot):
    - Scene 1 must NEVER pass through the raw face anchor (selfie) as the thumbnail.
    - Scene 1 must always attempt AI image generation using the movie idea + scene beat,
      using the face anchor ONLY as a subject reference (not an init image).

    Video is generated later by POST /generate-video.
    """
    # Keep only the current run's outputs.
    _clear_previous_generation_outputs()
    settings = get_settings()
    movie_idea = (body.scene_prompt or "").strip()
    ideal = (getattr(body, "idealization", None) or "").strip()
    use_llm = bool(settings.gemini_api_key and settings.gemini_api_key.strip())
    target = int(body.duration_seconds or 30)

    has_face = bool((body.face_anchor_path or "").strip())
    if (not has_face) and not (body.anchor_image_paths or []):
        raise HTTPException(status_code=400, detail="Please provide at least one wardrobe anchor image (or a face anchor) first.")
    # Face anchor improves identity continuity, but scenes can still be generated without it
    # (using wardrobe anchors only) for demo reliability.

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

    def _write_png_bytes(data: bytes) -> str:
        settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
        name = f"scene_{uuid.uuid4().hex}.png"
        out = settings.generated_media_dir / name
        out.write_bytes(data)
        return f"generated_media/{name}"

    async def _gemini_cinematic_still(
        *, prompt: str, ref_paths: list[Path], timeout_s: float = 42.0, force_text_to_image: bool = False
    ) -> bytes | None:
        """
        Best-effort still-image generation for scene thumbnails.

        - Uses the movie idea + scene beat as the text prompt.
        - Treats reference images (face / garments) as subject/style references ONLY.
        - Never uses the face anchor as an init/base image.

        CRITICAL:
        Some multimodal image models will "hug" the reference photo composition (appearing like image-to-image).
        When force_text_to_image=True (used for Scene 1 establishing shot), we do TEXT-TO-IMAGE only:
        - We do NOT attach any ref images in the request body.
        """
        if not use_llm:
            return None

        def _run() -> bytes | None:
            client = genai.Client(api_key=settings.gemini_api_key)  # type: ignore[arg-type]
            # IMPORTANT:
            # If we have reference images (especially the face anchor), we must try Gemini multimodal FIRST.
            # Imagen text-to-image ignores references entirely, which causes the UI to look like it's
            # "using the garment anchor" (because the system later falls back to local anchor-based stills
            # or the model drifts). So:
            # - force_text_to_image=True: text-only (no refs)
            # - otherwise, if refs exist: try Gemini multimodal first, then Imagen as a last resort.

            # 1) Gemini image model candidates (prefer current Nano Banana / image-preview IDs).
            model_candidates = [
                "gemini-3.1-flash-image-preview",
                "models/gemini-3.1-flash-image-preview",
                "gemini-3-pro-image-preview",
                "models/gemini-3-pro-image-preview",
                "gemini-2.5-flash-image",
                "models/gemini-2.5-flash-image",
                "gemini-2.0-flash-exp-image-generation",
                "models/gemini-2.0-flash-exp-image-generation",
            ]
            try:
                cfg = types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio="9:16"),
                )
            except Exception:
                cfg = types.GenerateContentConfig(response_modalities=["IMAGE"])
            try:
                cfg_mixed = types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio="9:16"),
                )
            except Exception:
                cfg_mixed = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])

            # Prefer no explicit config first (matches AI Studio samples); then IMAGE-only; then TEXT+IMAGE.
            cfg_attempts: list[types.GenerateContentConfig | None] = [None, cfg, cfg_mixed]

            if force_text_to_image:
                for model in model_candidates:
                    for try_cfg in cfg_attempts:
                        try:
                            if try_cfg is None:
                                resp = client.models.generate_content(model=model, contents=prompt)
                            else:
                                resp = client.models.generate_content(model=model, contents=prompt, config=try_cfg)
                            data = _extract_inline_image_bytes(resp)
                            if data:
                                return data
                        except Exception:
                            pass
                return None

            # 2) Multimodal Gemini first (refs applied).
            if ref_paths:
                parts_with_ref: list[object] = [prompt]
                for p in (ref_paths or [])[:4]:
                    if p.exists():
                        parts_with_ref.append(_genai_image_from_local_path(p))
                for model in model_candidates:
                    for try_cfg in cfg_attempts:
                        try:
                            if try_cfg is None:
                                resp = client.models.generate_content(model=model, contents=parts_with_ref)
                            else:
                                resp = client.models.generate_content(model=model, contents=parts_with_ref, config=try_cfg)
                            data = _extract_inline_image_bytes(resp)
                            if data:
                                return data
                        except Exception:
                            pass

            # 3) Text-only Gemini fallback.
            for model in model_candidates:
                for try_cfg in cfg_attempts:
                    try:
                        if try_cfg is None:
                            resp = client.models.generate_content(model=model, contents=prompt)
                        else:
                            resp = client.models.generate_content(model=model, contents=prompt, config=try_cfg)
                        data = _extract_inline_image_bytes(resp)
                        if data:
                            return data
                    except Exception:
                        pass

            # 4) Last resort: Imagen text-to-image (no refs; may lose identity/outfit).
            try:
                img_resp = client.models.generate_images(
                    model="imagen-3.0-generate-002",
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="9:16",
                    ),
                )
                imgs = getattr(img_resp, "generated_images", None) or getattr(img_resp, "images", None) or []
                for im in imgs:
                    b = getattr(im, "image_bytes", None) or getattr(im, "bytes", None) or None
                    if b:
                        return b
            except Exception:
                pass

            return None

        try:
            return await asyncio.wait_for(asyncio.to_thread(_run), timeout=timeout_s)
        except Exception:
            return None

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
            img = _genai_image_from_local_path(frame_path)
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
            dur_cap = max(2, min(15, int(duration_s or 8)))
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

    # Course MVP: fixed 4-scene reel so the demo flow matches the rubric.
    n_scenes = 4
    sec_each = max(6, min(10, int(math.ceil(target / max(1, n_scenes)))))
    # Build scene drafts. If we have a face anchor, use it for Scene 1; otherwise rotate wardrobe anchors.
    anchors = list(body.anchor_image_paths or [])
    scenes: list[ReelSceneDraft] = []
    for i in range(n_scenes):
        if has_face and i == 0:
            # CRITICAL:
            # Never set the face selfie as the scene's base/thumbnail anchor.
            # The face anchor is used ONLY as a reference image for generation.
            # This prevents any fallback path from copying/animating the raw selfie.
            anchor = None
            a_type: Literal["face", "wardrobe", "none"] = "face"
        else:
            anchor = anchors[(i - 1) % len(anchors)] if (anchors and has_face) else (anchors[i % len(anchors)] if anchors else None)
            a_type = "wardrobe" if anchor else "none"
        scenes.append(
            ReelSceneDraft(
                anchor_image_path=anchor,
                anchor_type=a_type,
                label=f"Scene {i + 1}/{n_scenes}",
                duration_seconds=sec_each,
                description="",
            )
        )
    logline = f"Runway reel — {n_scenes} scenes (~{target}s total)"
    video_prompt = f"{logline}\nMovie idea: {movie_idea_s[:240]}"

    job_id = uuid.uuid4().hex
    run_dir = settings.data_dir / "reel_runs" / job_id
    run_dir.mkdir(parents=True, exist_ok=True)
    story_arc = _story_arc_for_reel(n_scenes, f"{job_id}:{movie_idea_s}:{target}")

    # Static-image pipeline (two-step workflow):
    # Generate scene stills + descriptions here; video generation happens later in POST /generate-video.

    def _local_render_still(*, anchor_path: str | None, scene_index: int, seed_key: str) -> str | None:
        """
        Create a fresh 9:16 "cinematic still" locally using the anchors as texture inputs.

        IMPORTANT: This should not look like a raw crop of the anchor.
        We generate a new background + framing + grade so the UI clearly shows "generated" assets.
        """
        try:
            from PIL import Image, ImageDraw, ImageEnhance, ImageFilter  # type: ignore
        except Exception:
            return _copy_to_generated(anchor_path)

        rng = random.Random(seed_key)

        def _load(p: str | None) -> Image.Image | None:
            if not p:
                return None
            lp = (settings.data_dir / p).resolve()
            if not lp.exists():
                return None
            try:
                return Image.open(str(lp)).convert("RGB")
            except Exception:
                return None

        def _cover_fit(im: Image.Image, w: int, h: int) -> Image.Image:
            scale = max(w / im.width, h / im.height)
            nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
            im2 = im.resize((nw, nh))
            # Randomized crop window to avoid repeated framing
            max_x = max(0, nw - w)
            max_y = max(0, nh - h)
            cx = rng.randint(0, max_x) if max_x else 0
            cy = rng.randint(0, max_y) if max_y else 0
            return im2.crop((cx, cy, cx + w, cy + h))

        W, H = 1080, 1920
        canvas = Image.new("RGB", (W, H), (12, 12, 16))
        dr = ImageDraw.Draw(canvas)

        def _paint_gradient() -> None:
            c1 = (rng.randint(10, 40), rng.randint(10, 40), rng.randint(14, 50))
            c2 = (rng.randint(60, 120), rng.randint(50, 110), rng.randint(40, 100))
            for y in range(H):
                t = y / max(1, H - 1)
                r = int(c1[0] * (1 - t) + c2[0] * t)
                g = int(c1[1] * (1 - t) + c2[1] * t)
                b = int(c1[2] * (1 - t) + c2[2] * t)
                dr.line([(0, y), (W, y)], fill=(r, g, b))

        anchor = _load(anchor_path)
        # Always paint a non-anchor base background first, so the result can't be mistaken
        # for a plain anchor crop (especially for product shots on white backgrounds).
        _paint_gradient()

        if anchor is not None:
            # Add an "environment wash" derived from the anchor at low opacity.
            # This keeps color continuity but ensures it's not just the anchor photo.
            bg = _cover_fit(anchor, W, H)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=rng.uniform(18, 28)))
            bg = ImageEnhance.Color(bg).enhance(1.15 + rng.random() * 0.25)
            bg = ImageEnhance.Contrast(bg).enhance(1.08 + rng.random() * 0.18)
            bg_rgba = bg.convert("RGBA")
            # Low alpha overlay to preserve the new background
            bg_rgba.putalpha(int(70 + rng.random() * 55))  # ~27–49%
            canvas = Image.alpha_composite(canvas.convert("RGBA"), bg_rgba)
            dr = ImageDraw.Draw(canvas)

        # Place the anchor as a "subject layer" (not full-bleed)
        if anchor is not None:
            # Subject box size and placement varies by scene
            box_w = rng.randint(640, 920)
            box_h = rng.randint(720, 1180)
            subject = _cover_fit(anchor, box_w, box_h)
            # Slight rotation and contrast for "generated frame" vibe
            subject = ImageEnhance.Contrast(subject).enhance(1.05 + rng.random() * 0.08)
            subject = ImageEnhance.Color(subject).enhance(1.02 + rng.random() * 0.10)
            subject = subject.rotate(rng.uniform(-2.0, 2.0), resample=Image.BICUBIC, expand=True, fillcolor=(0, 0, 0))

            # Drop shadow
            sx = rng.randint(70, W - box_w - 70)
            sy = rng.randint(170, H - box_h - 220)
            shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            sdr = ImageDraw.Draw(shadow_layer)
            sdr.rectangle((sx + 18, sy + 22, sx + 18 + box_w, sy + 22 + box_h), fill=(0, 0, 0, 110))
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=18))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow_layer).convert("RGBA")

            # Paste subject
            subj_rgba = subject.convert("RGBA")
            # Center crop subject to box again after rotation (so it fits)
            if subj_rgba.width > box_w or subj_rgba.height > box_h:
                left = max(0, (subj_rgba.width - box_w) // 2)
                top = max(0, (subj_rgba.height - box_h) // 2)
                subj_rgba = subj_rgba.crop((left, top, left + box_w, top + box_h))
            canvas.alpha_composite(subj_rgba, (sx, sy))

        # Matte frame so thumbnails look "generated", not raw uploads.
        frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fdr = ImageDraw.Draw(frame)
        pad = 18
        fdr.rounded_rectangle((pad, pad, W - pad, H - pad), radius=34, outline=(255, 255, 255, 70), width=4)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), frame)

        # Light leak overlay (very subtle) to make it feel like a film still.
        try:
            leak = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ldr = ImageDraw.Draw(leak)
            # One or two soft blobs
            for _ in range(1 + (1 if rng.random() < 0.35 else 0)):
                cx = rng.randint(-200, W + 200)
                cy = rng.randint(-200, H + 200)
                rx = rng.randint(240, 520)
                ry = rng.randint(240, 620)
                col = (
                    rng.randint(210, 255),
                    rng.randint(170, 235),
                    rng.randint(120, 210),
                    rng.randint(30, 60),
                )
                ldr.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=col)
            leak = leak.filter(ImageFilter.GaussianBlur(radius=38))
            canvas = Image.alpha_composite(canvas, leak)
        except Exception:
            pass

        # Film grain + vignette so it never looks like a raw upload
        grain = Image.effect_noise((W, H), rng.uniform(6.0, 14.0)).convert("L")
        grain = ImageEnhance.Contrast(grain).enhance(1.6)
        grain_rgba = Image.merge("RGBA", (grain, grain, grain, grain.point(lambda x: int(x * 0.10))))
        canvas = Image.alpha_composite(canvas, grain_rgba)

        vign = Image.new("L", (W, H), 0)
        vdr = ImageDraw.Draw(vign)
        vdr.ellipse((-W * 0.10, -H * 0.05, W * 1.10, H * 1.05), fill=255)
        vign = vign.filter(ImageFilter.GaussianBlur(radius=80))
        vign = ImageEnhance.Contrast(vign).enhance(1.3)
        vign_alpha = Image.eval(vign, lambda x: int((255 - x) * 0.35))
        vign_rgba = Image.merge("RGBA", (Image.new("L", (W, H), 0),) * 3 + (vign_alpha,))
        canvas = Image.alpha_composite(canvas, vign_rgba)

        # Final grade per scene index to make scenes distinct
        canvas = canvas.convert("RGB")
        hue_boost = 1.0 + (0.03 * ((scene_index % 3) - 1))
        canvas = ImageEnhance.Color(canvas).enhance(hue_boost)
        canvas = ImageEnhance.Contrast(canvas).enhance(1.02 + rng.random() * 0.06)

        settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
        name = f"scene_{uuid.uuid4().hex}.png"
        out = settings.generated_media_dir / name
        canvas.save(str(out), format="PNG", optimize=True)
        return f"generated_media/{name}"

    def _context_block(drafts: list[ReelSceneDraft]) -> str:
        lines: list[str] = []
        for s in drafts:
            gen = (s.generated_image_path or "").strip()
            lines.append(
                f"- {s.label} (type={s.anchor_type}, anchor_still={s.anchor_image_path or 'n/a'}, "
                f"generated_still={gen or 'n/a'}): {s.description.strip()[:200]}"
            )
        return "\n".join(lines)

    def _offline_description(*, idx: int, total: int, scene: ReelSceneDraft, arc_phase: str, arc_hook: str) -> str:
        """
        Offline fallback copy that still references the movie idea (no LLM available).
        """
        brief = (movie_idea_s or movie_idea or "").strip()
        hook = (arc_hook or "").strip()[:160]
        who = "the same protagonist in the face anchor" if has_face else "one consistent lead wearing the outfit"
        return (
            f"{brief[:200]} "
            f"[{arc_phase}] {hook} "
            f"(scene {idx + 1}/{total}: new environment + camera; {who}; wardrobe on-body)."
        ).strip()

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

    async def _gemini_scene_beat(
        *,
        scene_index: int,
        scene_total: int,
        prior: list[ReelSceneDraft],
        arc_phase: str,
        arc_hook: str,
        prior_frame_paths: list[Path],
    ) -> str | None:
        """
        Produce a unique per-scene beat (plot + camera) so frames and descriptions don't repeat.
        This beat conditions image generation; the final description is frame-grounded after generation.
        """
        if not use_llm:
            return None
        try:
            client = genai.Client(api_key=settings.gemini_api_key)  # type: ignore[arg-type]
            model = settings.gemini_model
            prior_ctx = _context_block(prior[-5:]) if prior else "(none)"
            subj_rule = (
                "The main subject MUST be the face-anchor person (not any celebrity).\n"
                if has_face
                else "The main subject MUST be one consistent lead wearing the recommended outfit (no celebrity faces).\n"
            )
            prompt = (
                "Write ONE concise scene beat for a short cinematic fashion reel with a coherent story spine.\n"
                "Return STRICT JSON: {\"beat\": \"...\"}.\n\n"
                f"MOVIE_IDEA:\n{movie_idea_s}\n"
                f"IDEALIZATION:\n{ideal or '(none)'}\n\n"
                f"ARC_PHASE (where we are in the story): {arc_phase}\n"
                f"ARC_DIRECTION (blocking hint; do not contradict): {arc_hook}\n\n"
                "OUTFIT (structured hints from wardrobe anchors):\n"
                f"{_analysis_block()}\n\n"
                "PRIOR_SCENES (continuity; do not repeat the same setting/camera; advance the plot):\n"
                f"{prior_ctx}\n\n"
                "If prior generated frame images are attached, treat them as continuity references only "
                "(same person/outfit/story energy). This new beat must move the narrative forward.\n\n"
                f"Scene {scene_index + 1} of {scene_total}.\n"
                "Constraints:\n"
                f"- {subj_rule}"
                "- The outfit MUST be worn on-body and visibly resembles the wardrobe anchors.\n"
                "- Make this beat visually distinct from anchors and from prior generated frames (new location/action).\n"
                "- 1–2 sentences max."
            )
            parts: list[object] = [prompt]
            for p in prior_frame_paths[-2:]:
                if p.exists():
                    parts.append(_genai_image_from_local_path(p))
            resp = client.models.generate_content(model=model, contents=parts)
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

    def _path_for_log(p: Path) -> str:
        try:
            return p.resolve().relative_to(settings.data_dir.resolve()).as_posix()
        except Exception:
            return p.as_posix()

    ref_meta_paths: list[list[str]] = []
    # --- Static still generation loop (Scene 1 establishing shot fix) ---
    generated: list[ReelSceneDraft] = []
    face_local = _resolve(body.face_anchor_path) if (body.face_anchor_path and has_face) else None
    garments_local: list[Path] = []
    for p in body.anchor_image_paths or []:
        lp = _resolve(p)
        if lp is not None:
            garments_local.append(lp)

    if has_face and face_local is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Face anchor file not found on the server. Re-upload your selfie, or set DATA_DIR to the folder "
                f"that contains this relative path: {body.face_anchor_path!r}"
            ),
        )

    for i, s in enumerate(scenes):
        total = len(scenes)
        arc_entry = story_arc[i] if i < len(story_arc) else {"phase": "beat", "hook": ""}
        arc_phase = str(arc_entry.get("phase", "") or "beat")
        arc_hook = str(arc_entry.get("hook", "") or "")

        beat = await _gemini_scene_beat(
            scene_index=i,
            scene_total=total,
            prior=generated,
            arc_phase=arc_phase,
            arc_hook=arc_hook,
            prior_frame_paths=[],
        )
        s2 = s.model_copy(update={"description": beat or _offline_description(idx=i, total=total, scene=s, arc_phase=arc_phase, arc_hook=arc_hook)})

        img_path: str | None = None

        # Reference selection:
        # The main failure mode you reported is the model "hugging" the flat-lay garment photos and outputting
        # something that looks like the garment anchor instead of a new on-body cinematic frame.
        #
        # To make the generated stills reliably "new", we attach ONLY the face anchor as an image reference
        # (identity) and express the outfit constraints via structured JSON + text (anchor analysis).
        ref_for_image: list[Path] = [face_local] if (has_face and face_local is not None) else []
        ref_meta_paths.append([_path_for_log(p) for p in ref_for_image])

        if use_llm:
            # Use the structured analysis (colors/categories/material hints) instead of attaching flat-lay refs.
            wardrobe_ctx = _analysis_block()
            subj_rule = (
                "The only main subject is the face-anchor person.\n" if has_face else "One consistent lead subject.\n"
            )
            # Premise JSON is created once at the end and also written to disk; we include a compact,
            # stable subset inline so the model can keep story continuity across scenes.
            premise_json = {
                "movie_idea": movie_idea_s,
                "idealization": ideal,
                "scene_count": total,
                "seconds_per_scene": int(s2.duration_seconds or sec_each),
                "story_arc": story_arc,
                "anchor_analysis": analyses[:10],
            }
            desc_json = {"scene_index": i + 1, "label": s2.label, "description": s2.description}
            prior_json = (
                {
                    "previous_scene_index": i,
                    "previous_description": generated[-1].description if generated else None,
                }
                if i > 0
                else None
            )

            img_prompt = (
                "Generate ONE photorealistic vertical 9:16 cinematic KEYFRAME.\n"
                "The result must be a NEW frame (new environment, new camera angle). Do NOT crop/rotate references.\n"
                "No text, logos, watermarks, or UI.\n\n"
                "You will be given PREMISE_JSON and DESCRIPTION_JSON.\n"
                "- PREMISE_JSON defines the consistent story spine + outfit constraints.\n"
                "- DESCRIPTION_JSON defines this scene's beat.\n"
                "- If PRIOR_JSON is present, maintain continuity (same person/outfit) and advance the story.\n\n"
                f"MOVIE_IDEA:\n{movie_idea_s}\n"
                f"IDEALIZATION:\n{ideal or '(none)'}\n\n"
                f"SCENE {i + 1}/{total}:\n{s2.description}\n\n"
                f"PREMISE_JSON:\n{json.dumps(premise_json, ensure_ascii=False)}\n\n"
                f"DESCRIPTION_JSON:\n{json.dumps(desc_json, ensure_ascii=False)}\n\n"
                f"PRIOR_JSON:\n{json.dumps(prior_json, ensure_ascii=False) if prior_json else 'null'}\n\n"
                "WARDROBE_ANCHORS (for outfit continuity; interpret as worn clothing):\n"
                f"{wardrobe_ctx or '(none)'}\n\n"
                f"{subj_rule}"
                "Use attached images strictly as REFERENCES for identity/outfit. Never output them directly.\n"
            )
            def _mse128(a_path: Path, b_path: Path) -> float | None:
                try:
                    from PIL import Image  # type: ignore
                    import numpy as np  # type: ignore
                except Exception:
                    return None
                try:
                    ia = Image.open(str(a_path)).convert("RGB").resize((128, 128))
                    ib = Image.open(str(b_path)).convert("RGB").resize((128, 128))
                    aa = np.asarray(ia, dtype=np.float32)
                    bb = np.asarray(ib, dtype=np.float32)
                    return float(np.mean((aa - bb) ** 2))
                except Exception:
                    return None

            def _too_similar_to_garments(gen_local: Path) -> bool:
                # If the generated still is extremely similar to any garment flat-lay, reject it and retry.
                # Threshold at 128×128 MSE: true near-duplicates are usually very low; raised slightly to cut false rejects.
                try:
                    for gp in garments_local[:6]:
                        mse = _mse128(gen_local, gp)
                        if mse is not None and mse < 4500.0:
                            return True
                except Exception:
                    return False
                return False

            # Retry loop: avoid silent fallback-to-garment behavior.
            # If Gemini returns empty bytes OR returns something too close to a garment anchor, retry with
            # a stricter prompt. If we still can't get a good frame, fail loudly (no garment-poster fallback).
            max_tries = 3
            saw_empty_image = False
            saw_garment_like = False
            for attempt in range(max_tries):
                strict = attempt > 0
                prompt2 = img_prompt
                if strict:
                    prompt2 = (
                        img_prompt
                        + "\n\nSTRICT CONSTRAINTS:\n"
                        + "- The subject must be FULL-BODY or 3/4 body, on-location cinematic shot.\n"
                        + "- Do NOT show a single isolated garment on a plain background.\n"
                        + "- Do NOT show a flat-lay, product photo, catalog image, or poster-like centered clothing.\n"
                        + "- The result must clearly look like a film frame with depth, lighting, and environment.\n"
                    )
                data = await _gemini_cinematic_still(
                    prompt=prompt2,
                    ref_paths=ref_for_image,
                    timeout_s=150.0 if strict else 120.0,
                    # We must prioritize face anchor for identity; do not force text-only here.
                    force_text_to_image=False,
                )
                if not data:
                    saw_empty_image = True
                    continue
                rel = _write_png_bytes(data)
                local = _resolve(rel)
                if local is None:
                    saw_empty_image = True
                    continue
                if _too_similar_to_garments(local):
                    saw_garment_like = True
                    img_path = None
                    continue
                img_path = rel
                break

        if img_path is None:
            # IMPORTANT:
            # If we have a live LLM key but still failed, do NOT fall back to a garment-poster renderer.
            # That fallback is exactly the failure mode the user sees (scene looks like the garment anchor).
            if use_llm:
                parts: list[str] = [
                    "Could not produce a valid cinematic still for this scene.",
                ]
                if saw_garment_like:
                    parts.append(
                        "The image model kept returning frames that looked like flat-lay or catalog garment shots. "
                        "Try a different movie idea, different wardrobe photos, or tap Generate scenes again."
                    )
                if saw_empty_image:
                    parts.append(
                        "Gemini returned no image bytes (model unavailable for this key, safety block, network timeout, or quota). "
                        "Check API billing, try again, or shorten the movie idea text."
                    )
                raise HTTPException(status_code=502, detail=" ".join(parts))

            # Offline fallback (no LLM): create a synthetic still so the UI always has something.
            anchor_for_offline = s2.anchor_image_path
            if not anchor_for_offline:
                anchor_for_offline = (body.anchor_image_paths or [None])[0]
            seed_key = hashlib.sha256(f"{job_id}:{movie_idea_s}:{i}:{arc_phase}:{arc_hook}".encode("utf-8")).hexdigest()
            img_path = _local_render_still(anchor_path=anchor_for_offline, scene_index=i, seed_key=seed_key)

        clip_path = None
        if img_path:
            stem_clip = f"scene_{uuid.uuid4().hex}"
            try:
                clip_path = await asyncio.wait_for(
                    asyncio.to_thread(_scene_clip_mp4, still_rel=img_path, duration_s=int(s2.duration_seconds or 8), stem=stem_clip),
                    timeout=55.0,
                )
            except (asyncio.TimeoutError, Exception):
                clip_path = None

        generated.append(s2.model_copy(update={"generated_image_path": img_path, "generated_video_path": clip_path}))

    premise = {
        "job_id": job_id,
        "logline": logline,
        "objective": body.scene_prompt,
        "face_anchor": body.face_anchor_path,
        "wardrobe_anchors": list(body.anchor_image_paths),
        "anchor_analysis_path": "anchors_analysis.json",
        "seconds_per_scene": sec_each,
        "story_arc": story_arc,
        "beats": [
            {
                "index": i + 1,
                "label": s.label,
                "anchor_type": s.anchor_type,
                "anchor_image_path": s.anchor_image_path,
                "arc_phase": story_arc[i].get("phase") if i < len(story_arc) else None,
                "arc_hook": story_arc[i].get("hook") if i < len(story_arc) else None,
                "description": s.description,
                "generated_image_path": s.generated_image_path,
                "generated_video_path": s.generated_video_path,
                "ref_inputs_resolved": ref_meta_paths[i] if i < len(ref_meta_paths) else [],
            }
            for i, s in enumerate(generated)
        ],
    }
    story_state = {
        "version": 1,
        "job_id": job_id,
        "movie_idea": movie_idea,
        "movie_idea_sanitized": movie_idea_s,
        "idealization": ideal,
        "duration_target_seconds": target,
        "seconds_per_scene": sec_each,
        "scene_count": len(generated),
        "story_arc": story_arc,
        "anchors": {
            "face": body.face_anchor_path,
            "wardrobe": list(body.anchor_image_paths or []),
        },
        "anchor_analysis_path": "anchors_analysis.json",
        "scenes": [
            {
                "index": idx + 1,
                "label": sc.label,
                "duration_seconds": sc.duration_seconds,
                "arc_phase": story_arc[idx].get("phase") if idx < len(story_arc) else None,
                "arc_hook": story_arc[idx].get("hook") if idx < len(story_arc) else None,
                "anchor_type": sc.anchor_type,
                "anchor_image_path": sc.anchor_image_path,
                "description": sc.description,
                "ref_inputs_resolved": ref_meta_paths[idx] if idx < len(ref_meta_paths) else [],
                "generated_image_path": sc.generated_image_path,
                "generated_video_path": sc.generated_video_path,
            }
            for idx, sc in enumerate(generated)
        ],
        "video_notes": (
            "Per-scene Ken Burns clips use duration_seconds (~8s target). "
            "For full-motion Veo/Gemini video, pass story_state + anchors to the video provider."
        ),
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
    (run_dir / "story_state.json").write_text(json.dumps(story_state, indent=2), encoding="utf-8")

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
    previous_scene_image_path: str | None = None


class GenerateSceneAssetsResponse(ReelSceneDraft):
    pass


@router.post("/generate-scene-assets", response_model=GenerateSceneAssetsResponse)
async def generate_scene_assets(body: GenerateSceneAssetsRequest) -> GenerateSceneAssetsResponse:
    """
    Use Gemini image generation to create a new still for a scene.
    The generated still can be regenerated until user is satisfied, and is used to animate the reel.
    """
    settings = get_settings()
    use_llm = bool(settings.gemini_api_key and settings.gemini_api_key.strip())

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

    def _write_png_bytes(data: bytes) -> str:
        settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
        name = f"scene_{uuid.uuid4().hex}.png"
        out = settings.generated_media_dir / name
        out.write_bytes(data)
        return f"generated_media/{name}"

    def _local_render_still(*, anchor_path: str | None, seed_key: str) -> str | None:
        """
        Local fallback for regenerating a scene still (no API key required).
        Must look "new" on each click, even if the same garment anchor is used.
        """
        try:
            from PIL import Image, ImageDraw, ImageEnhance, ImageFilter  # type: ignore
        except Exception:
            return _copy_to_generated(anchor_path)

        rng = random.Random(seed_key)

        def _load(p: str | None) -> "Image.Image | None":
            if not p:
                return None
            try:
                lp = (settings.data_dir / p).resolve()
                if not lp.exists():
                    return None
                return Image.open(str(lp)).convert("RGB")
            except Exception:
                return None

        def _cover_fit(im: "Image.Image", w: int, h: int) -> "Image.Image":
            scale = max(w / im.width, h / im.height)
            nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
            im2 = im.resize((nw, nh))
            max_x = max(0, nw - w)
            max_y = max(0, nh - h)
            cx = rng.randint(0, max_x) if max_x else 0
            cy = rng.randint(0, max_y) if max_y else 0
            return im2.crop((cx, cy, cx + w, cy + h))

        W, H = 1080, 1920
        canvas = Image.new("RGB", (W, H), (12, 12, 16))
        dr = ImageDraw.Draw(canvas)

        # Always paint a background that isn't just the anchor.
        c1 = (rng.randint(10, 40), rng.randint(10, 40), rng.randint(14, 50))
        c2 = (rng.randint(70, 140), rng.randint(50, 120), rng.randint(40, 110))
        for y in range(H):
            t = y / max(1, H - 1)
            r = int(c1[0] * (1 - t) + c2[0] * t)
            g = int(c1[1] * (1 - t) + c2[1] * t)
            b = int(c1[2] * (1 - t) + c2[2] * t)
            dr.line([(0, y), (W, y)], fill=(r, g, b))

        anchor = _load(anchor_path)
        if anchor is not None:
            bg = _cover_fit(anchor, W, H).filter(ImageFilter.GaussianBlur(radius=rng.uniform(18, 30)))
            bg = ImageEnhance.Color(bg).enhance(1.10 + rng.random() * 0.35)
            bg = ImageEnhance.Contrast(bg).enhance(1.05 + rng.random() * 0.25)
            canvas = Image.blend(canvas, bg, alpha=0.35 + rng.random() * 0.25)

            # Foreground "poster" crop (varies per regen via seed_key)
            fg = anchor.copy()
            fg = ImageEnhance.Contrast(fg).enhance(1.02 + rng.random() * 0.18)
            fg = ImageEnhance.Color(fg).enhance(1.02 + rng.random() * 0.28)
            pw = int(W * (0.62 + rng.random() * 0.10))
            ph = int(pw * (fg.height / max(1, fg.width)))
            ph = max(420, min(int(H * 0.72), ph))
            fg2 = _cover_fit(fg, pw, ph)

            x = (W - pw) // 2 + rng.randint(-18, 18)
            y = int(H * (0.20 + rng.random() * 0.10))
            shadow = Image.new("RGBA", (pw + 80, ph + 80), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.rounded_rectangle((40, 40, 40 + pw, 40 + ph), radius=36, fill=(0, 0, 0, 150))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
            canvas_rgba = canvas.convert("RGBA")
            canvas_rgba.alpha_composite(shadow, (x - 40, y - 30))

            card = Image.new("RGBA", (pw, ph), (245, 245, 247, 255))
            card.alpha_composite(fg2.convert("RGBA"), (0, 0))
            canvas_rgba.alpha_composite(card, (x, y))
            canvas = canvas_rgba.convert("RGB")

        # Gentle film-like grade (also varies due to seed)
        canvas = canvas.filter(ImageFilter.GaussianBlur(radius=rng.random() * 0.6))
        canvas = ImageEnhance.Contrast(canvas).enhance(1.06 + rng.random() * 0.12)
        canvas = ImageEnhance.Brightness(canvas).enhance(0.98 + rng.random() * 0.08)

        settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
        name = f"scene_{uuid.uuid4().hex}.png"
        out = settings.generated_media_dir / name
        try:
            canvas.save(str(out), format="PNG", optimize=True)
            return f"generated_media/{name}"
        except Exception:
            return None

    def _scene_clip_mp4(*, still_rel: str, duration_s: int, stem: str) -> str | None:
        """
        Build a short animated MP4 from a still (Ken Burns), silent.
        This keeps the UI preview (which prefers generated_video_path) in sync after regenerations.
        """
        try:
            still_local = _resolve(still_rel)
            if still_local is None:
                return None
            settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
            out = settings.generated_media_dir / f"{stem}.mp4"

            w, h = 1080, 1920
            fps = 18
            dur_cap = max(2, min(15, int(duration_s or 8)))
            dur = float(dur_cap)
            frames = max(1, int(dur * fps))

            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},"
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
                "-an",
                "-movflags",
                "+faststart",
                str(out),
            ]
            subprocess.run(cmd, check=True, timeout=90)
            if out.exists() and out.stat().st_size > 0:
                return f"generated_media/{out.name}"
        except Exception:
            return None
        return None

    # Conditioning logic:
    # - Face anchor first (identity).
    # - Previous generated scene still second when available (on-body continuity; helps avoid flat-lay "hugging").
    # - Garments last (flat-lay refs can distort; keep them weak and limited).
    ref_for_image: list[Path] = []
    face_local = _resolve(body.face_anchor_path) if body.face_anchor_path else None
    if face_local is not None:
        ref_for_image.append(face_local)

    prev_local = _resolve(body.previous_scene_image_path) if body.previous_scene_image_path else None
    if prev_local is not None:
        ref_for_image.append(prev_local)
    garments_local: list[Path] = []
    for p in body.anchor_image_paths or []:
        lp = _resolve(p)
        if lp is not None:
            garments_local.append(lp)
    if garments_local:
        # Pick up to 2 garments deterministically, but keep garments last in the ref ordering.
        h = abs(hash((body.scene.label or "", body.scene.description or "")))
        g0 = garments_local[h % len(garments_local)]
        g_candidates = [g0]
        if len(garments_local) > 1:
            g1 = garments_local[(h + 1) % len(garments_local)]
            if g1 != g0:
                g_candidates.append(g1)
        for g in g_candidates:
            if g not in ref_for_image:
                ref_for_image.append(g)

    # Enforce ref-image cap (see MEDIA_MAX_REF_IMAGES).
    try:
        cap = max(0, int(getattr(settings, "media_max_ref_images", 3) or 3))
        ref_for_image = ref_for_image[:cap]
    except Exception:
        ref_for_image = ref_for_image[:3]

    variation = uuid.uuid4().hex
    prompt = (
        "Generate ONE photorealistic vertical 9:16 cinematic KEYFRAME (1080x1920 feel).\n"
        "This must look like a NEW frame from a film—not a duplicate of the reference photo’s composition, framing, or background.\n"
        "Invent a fresh environment, lighting, and camera angle aligned with the MOVIE_IDEA.\n\n"
        f"MOVIE_IDEA:\n{movie_idea_s}\nIDEALIZATION:\n{ideal or '(none)'}\n\n"
        f"DESCRIPTION:\n{body.scene.description}\n\n"
        f"VARIATION_SALT:\n{variation}\n\n"
        "REFERENCE IMAGE RULES:\n"
        "- If a previous scene frame is provided, maintain identity + wardrobe continuity with that frame while advancing the story beat.\n"
        "- Preserve identity from the face reference.\n"
        "- Preserve key garment colors/materials/silhouettes from wardrobe references and show them ON-BODY.\n"
        "- If MOVIE_IDEA mentions celebrities, treat them as style references ONLY. Do NOT depict them.\n"
        "- The only main subject is the face-anchor person.\n"
        "- Do NOT paste the reference as a flat lay. Do NOT stack multiple garments or double-exposure overlays.\n"
        "- Avoid plain catalog/studio backdrops (no seamless white/grey product background).\n"
        "- No text, logos, watermarks, or UI overlays in the image.\n"
    )

    rel_image: str | None = None
    image_path: Path | None = None
    client = None

    if use_llm:
        client = genai.Client(api_key=settings.gemini_api_key)
        img_model = "models/gemini-2.5-flash-image"
        try:
            try:
                parts: list[object] = [prompt]
                for p in ref_for_image[:4]:
                    if p.exists():
                        parts.append(_genai_image_from_local_path(p))
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
            rel_image = _write_png_bytes(data)
            image_path = _resolve(rel_image)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Gemini image generation failed: {exc!s}")
    else:
        # Local fallback: pick a stable anchor (prefer the scene's anchor) but vary output each click.
        anchor_for_local = body.scene.anchor_image_path
        if not anchor_for_local and (body.anchor_image_paths or []):
            anchor_for_local = body.anchor_image_paths[0]
        seed_key = f"{uuid.uuid4().hex}:{body.scene.label}:{body.scene.description}:{movie_idea_s}"
        rel_image = _local_render_still(anchor_path=anchor_for_local, seed_key=seed_key)
        image_path = _resolve(rel_image) if rel_image else None
        if not rel_image or image_path is None:
            raise HTTPException(status_code=502, detail="Local scene image generation failed.")

    # Update description to match the newly generated still (vision), when possible.
    desc2: str | None = None
    try:
        if (not use_llm) or client is None or image_path is None:
            raise RuntimeError("Skip vision description (no LLM or missing image)")
        img2 = _genai_image_from_local_path(image_path)
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

    # Keep video preview in sync: the UI prefers generated_video_path over generated_image_path.
    rel_video: str | None = None
    try:
        if rel_image:
            rel_video = _scene_clip_mp4(
                still_rel=rel_image,
                duration_s=int(getattr(body.scene, "duration_seconds", 8) or 8),
                stem=f"scene_{uuid.uuid4().hex}_preview",
            )
    except Exception:
        rel_video = None

    out = body.scene.model_copy(
        update={
            "generated_image_path": rel_image,
            # If we can't create a new preview mp4, clear any previous one so the UI shows the new still.
            "generated_video_path": rel_video,
            "description": desc2 or body.scene.description,
        }
    )
    return GenerateSceneAssetsResponse(**out.model_dump())
