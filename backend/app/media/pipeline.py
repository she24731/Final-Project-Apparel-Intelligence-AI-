from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.media import GenerateVideoRequest, GenerateVideoResponse
from app.schemas.recommend import RecommendOutfitResponse
from app.schemas.reel_preview import ReelSceneDraft
from app.config import get_settings


@dataclass(frozen=True)
class Storyboard:
    logline: str
    scene_texts: list[str]


@dataclass(frozen=True)
class MediaPrompts:
    storyboard: Storyboard
    image_prompts: list[str]
    video_prompt: str


def build_storyboard(*, outfit: RecommendOutfitResponse | None, narrative: str, duration_seconds: int) -> Storyboard:
    garments = outfit.garments if outfit else []
    garment_phrase = ", ".join(f"{g.color} {g.category}" for g in garments) if garments else "a clean minimalist outfit"
    logline = f"Runway reel: {garment_phrase}. Tone: {narrative[:80].strip()}."

    # Keep scenes minimal for reliability.
    scenes = [
        f"Scene 1 (1–2s): establishing shot, soft natural light, {garment_phrase}.",
        f"Scene 2 (2–4s): runway walk, fabric drape focus, camera slow pan.",
        f"Scene 3 (last): hero pose, subtle turn, clean backdrop, premium editorial feel.",
    ]
    # Trim scenes if short duration
    if duration_seconds <= 4:
        scenes = scenes[:2]
    return Storyboard(logline=logline, scene_texts=scenes)


def build_anchor_scenes(
    *,
    anchor_paths: list[str],
    scene_prompt: str,
    face_anchor_path: str | None,
) -> list[ReelSceneDraft]:
    """
    Build editable scene beats for the reel, not per-anchor.

    IMPORTANT:
    - Anchors (face + garments) are *conditioning inputs* for image/video generation.
    - They should NOT appear as the "scene thumbnails" themselves, and we should not split the
      storyboard into "face scenes" vs "garment scenes".
    """
    target = 30
    try:
        # This function is used by multiple routes; we keep it resilient.
        # If duration is available upstream, it will be reflected in the final prompts anyway.
        target = int(getattr(get_settings(), "default_reel_seconds", 30) or 30)
    except Exception:
        target = 30

    # Prefer ~8s/scene, clamp to a small reel for reliability.
    sec_each = 8
    n = max(3, min(6, int((target + sec_each - 1) // sec_each)))
    sec_each = max(6, min(10, int((target + n - 1) // max(1, n))))

    base = (scene_prompt or "").strip()[:260]
    scenes: list[ReelSceneDraft] = []
    for i in range(n):
        scenes.append(
            ReelSceneDraft(
                anchor_image_path=None,
                anchor_type="none",
                label=f"Scene {i + 1}/{n}",
                duration_seconds=sec_each,
                description=(base + f" (beat {i + 1}/{n})").strip(),
            )
        )
    return scenes


@dataclass(frozen=True)
class CategorizedAnchors:
    """
    Canonical anchor split:
    - face: exactly one (optional but recommended)
    - garments: zero or more
    """

    face_anchor: str | None
    garment_anchors: list[str]


def categorize_anchors(*, face_anchor_path: str | None, anchor_paths: list[str]) -> CategorizedAnchors:
    """
    Categorize incoming anchors into exactly one 'face anchor' and the remaining 'garment anchors'.

    Rules:
    - If face_anchor_path is provided, it becomes the face anchor.
    - All other unique paths become garment anchors.
    - If face_anchor_path is missing, we still return garment anchors (face_anchor=None).
    """
    face = (face_anchor_path or "").strip() or None
    garments: list[str] = []
    seen: set[str] = set()

    for p in (anchor_paths or []):
        rp = (p or "").strip()
        if not rp:
            continue
        if face and rp == face:
            continue
        if rp in seen:
            continue
        seen.add(rp)
        garments.append(rp)

    return CategorizedAnchors(face_anchor=face, garment_anchors=garments)


def _resolve_local(settings, rel: str | None):
    if not rel:
        return None
    try:
        p = (settings.data_dir / rel).resolve()
        return p if p.exists() else None
    except Exception:
        return None


def _build_outfit_collage(*, garment_paths: list[str], out_stem: str) -> str | None:
    """
    Build a single "outfit anchor" image by compositing multiple garment anchors into a grid.

    NOTE:
    We previously used this to force a single "outfit anchor" at index 1. The current design
    passes ALL garment anchors as image 2..N instead, so this helper is no longer used by the
    Veo payload formatter. Kept as a utility in case a provider requires a single outfit image.
    """
    settings = get_settings()
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return None

    locals_ = []
    for rel in (garment_paths or [])[:6]:
        lp = _resolve_local(settings, rel)
        if lp is not None:
            locals_.append(lp)
    if not locals_:
        return None

    thumbs: list[Image.Image] = []
    for lp in locals_:
        try:
            im = Image.open(str(lp)).convert("RGB")
            thumbs.append(im)
        except Exception:
            continue
    if not thumbs:
        return None

    # 2x2 grid for up to 4 items; if >4, still show first 4 for clarity.
    thumbs = thumbs[:4]
    cols = 2
    rows = 2 if len(thumbs) > 1 else 1
    cell = 768
    pad = 24
    W = cols * cell + (cols + 1) * pad
    H = rows * cell + (rows + 1) * pad
    canvas = Image.new("RGB", (W, H), (245, 245, 248))

    def _fit(im: Image.Image) -> Image.Image:
        # cover-fit crop into a square
        scale = max(cell / im.width, cell / im.height)
        nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
        im2 = im.resize((nw, nh))
        left = max(0, (nw - cell) // 2)
        top = max(0, (nh - cell) // 2)
        return im2.crop((left, top, left + cell, top + cell))

    for idx, im in enumerate(thumbs):
        r = idx // cols
        c = idx % cols
        x = pad + c * (cell + pad)
        y = pad + r * (cell + pad)
        try:
            canvas.paste(_fit(im), (x, y))
        except Exception:
            pass

    settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
    out = settings.generated_media_dir / f"{out_stem}_outfit_anchor.png"
    try:
        canvas.save(str(out), format="PNG", optimize=True)
        return f"generated_media/{out.name}"
    except Exception:
        return None


def format_veo_reference_images(*, req: GenerateVideoRequest) -> list[str]:
    """
    Format anchors into the payload ordering required by Veo:
    - index 0: face anchor (if available)
    - index 1..N: garment/outfit anchors (all of them, in stable order)

    Returns:
    - ref_paths: list[str] in the required order
    """
    categorized = categorize_anchors(face_anchor_path=req.face_anchor_image_path, anchor_paths=req.anchor_image_paths or [])

    ref_paths: list[str] = []
    if categorized.face_anchor:
        ref_paths.append(categorized.face_anchor)
    # Append ALL garments (outfit anchors) as image 2..N.
    for g in categorized.garment_anchors:
        if g and g not in ref_paths:
            ref_paths.append(g)

    return ref_paths


def build_veo_prompt(*, base_prompt: str, reference_images_count: int) -> str:
    """
    Dynamically construct the Veo prompt with explicit anchor instructions.
    This matches the user requirement exactly.
    """
    p = (base_prompt or "").strip()
    n = max(0, int(reference_images_count or 0))
    # If we have >=2 images, image 1 is face and images 2..N are garments.
    if n >= 2:
        if n == 2:
            outfit_list = "image 2"
        else:
            outfit_list = ", ".join(f"image {i}" for i in range(2, n + 1))
        anchor_clause = (
            f"The subject should stay visually consistent with reference image 1, wearing clothing aligned with {outfit_list}."
        )
    elif n == 1:
        # No face anchor. Image 1 is the first garment/outfit anchor.
        anchor_clause = "The subject should wear clothing aligned with reference image 1."
    else:
        anchor_clause = ""
    return (
        f"{p}\n\n"
        f"{anchor_clause}\n"
        "FULL MOTION VIDEO (FMV). Continuous realistic movement, not a slideshow.\n"
        "No text, no logos, no watermarks.\n"
    ).strip()


def build_media_prompts(*, outfit: RecommendOutfitResponse | None, narrative: str, duration_seconds: int) -> MediaPrompts:
    sb = build_storyboard(outfit=outfit, narrative=narrative, duration_seconds=duration_seconds)
    image_prompts = [
        "High-end fashion editorial still, minimalist studio, softbox lighting, clean background, realistic fabric texture.",
        "Full-body runway still, subtle motion blur, premium lookbook aesthetic, neutral backdrop, high detail garments.",
    ]
    video_prompt = (
        f"{sb.logline}\n"
        f"Style: premium minimalist, realistic fabric drape, consistent outfit, natural movement.\n"
        f"Scenes:\n- " + "\n- ".join(sb.scene_texts)
    )
    return MediaPrompts(storyboard=sb, image_prompts=image_prompts, video_prompt=video_prompt)


class MediaProvider:
    """Provider adapter interface (Runway/Veo/etc.)."""

    name: str = "base"

    async def generate(self, *, req: GenerateVideoRequest, prompts: MediaPrompts) -> GenerateVideoResponse:
        raise NotImplementedError


class PlaceholderProvider(MediaProvider):
    name = "mock"

    async def generate(self, *, req: GenerateVideoRequest, prompts: MediaPrompts) -> GenerateVideoResponse:
        # Structured fallback: deterministic mock with message only.
        import uuid

        job_id = str(uuid.uuid4())
        if req.scenes:
            lines = "\n".join(f"— {s.description[:110]}…" for s in req.scenes[:8])
            msg = (
                f"Placeholder: {len(req.scenes)}-scene reel plan (~{req.duration_seconds}s). "
                "Set MEDIA_PROVIDER=gemini_video + GEMINI_API_KEY for stitched MP4.\n"
                f"{lines}"
            )
        else:
            msg = "Placeholder runway reel (no provider)."
        return GenerateVideoResponse(
            status="mock",
            job_id=job_id,
            preview_message=msg,
            video_url=None,
            provider=self.name,
            description=prompts.storyboard.logline,
            video_prompt=prompts.video_prompt,
        )


class GeminiStubProvider(MediaProvider):
    """
    Gemini-first demo provider (no paid video generation).

    Today: returns a structured preview message that includes narration + prompt.
    Later upgrade path: swap in Veo + TTS providers to return a real video_url.
    """

    name = "gemini_stub"

    async def generate(self, *, req: GenerateVideoRequest, prompts: MediaPrompts) -> GenerateVideoResponse:
        import uuid

        job_id = str(uuid.uuid4())
        face = f"Face anchor: {req.face_anchor_image_path}" if req.face_anchor_image_path else "Face anchor: none"
        return GenerateVideoResponse(
            status="mock",
            job_id=job_id,
            preview_message=(
                "Gemini demo runway reel (no paid provider).\n"
                f"{face}\n"
                f"Video prompt: {prompts.video_prompt[:220]}…"
            ),
            video_url=None,
            provider=self.name,
            description=prompts.storyboard.logline,
            video_prompt=prompts.video_prompt,
        )


class GeminiVeoProvider(MediaProvider):
    """
    Real video generation via Gemini API (Veo models) using user's GEMINI_API_KEY.

    Implementation strategy for a 30s reel:
    - Generate multiple short clips (e.g., 8s) with Veo
    - Concatenate locally into a single MP4
    - Serve from /generated_media/<job_id>.mp4
    """

    name = "gemini_video"

    async def generate(self, *, req: GenerateVideoRequest, prompts: MediaPrompts) -> GenerateVideoResponse:
        import asyncio
        import time
        import uuid
        from pathlib import Path

        settings = get_settings()
        if not settings.gemini_api_key or not settings.gemini_api_key.strip():
            return GenerateVideoResponse(
                status="failed",
                job_id="",
                preview_message="Missing GEMINI_API_KEY. Set it in backend/.env to generate real video.",
                video_url=None,
                provider=self.name,
                description=prompts.storyboard.logline,
                video_prompt=prompts.video_prompt,
            )

        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
        except Exception:
            return GenerateVideoResponse(
                status="failed",
                job_id="",
                preview_message="google-genai SDK not installed. Run: pip install -r backend/requirements.txt",
                video_url=None,
                provider=self.name,
                description=prompts.storyboard.logline,
                video_prompt=prompts.video_prompt,
            )

        # Optional dependency for concatenation. If unavailable, we still return the first clip as "real video".
        try:
            from moviepy import VideoFileClip, concatenate_videoclips  # type: ignore
        except Exception:  # pragma: no cover
            VideoFileClip = None  # type: ignore[assignment]
            concatenate_videoclips = None  # type: ignore[assignment]

        job_id = str(uuid.uuid4())
        out_dir = settings.generated_media_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        client = genai.Client(api_key=settings.gemini_api_key)
        model = settings.gemini_video_model

        def _local_image_path(p: str) -> Path:
            return (
                (settings.data_dir / p).resolve()
                if p.startswith("uploads/") or p.startswith("generated_media/")
                else (settings.data_dir / p).resolve()
            )

        def _to_image_obj(rel_path: str | None) -> object | None:
            if not rel_path:
                return None
            lp = _local_image_path(rel_path)
            if not lp.exists():
                return None
            try:
                return types.Image.from_file(location=str(lp.resolve()))
            except Exception:
                return None

        clip_paths: list[Path] = []

        async def _one_veo_clip(
            *,
            clip_index: int,
            prompt: str,
            reference_images: list[object],
            duration_sec: int,
        ) -> tuple[Path | None, str | None]:
            """
            Call Veo with robust payload handling.

            We *prefer* sending an array of reference images (index 0 = face, index 1 = outfit),
            matching the requested payload format. Some SDK versions accept only `image=` (single),
            so we fall back to `image=reference_images[0]` while keeping the anchor instruction in the prompt.
            """
            cfg = types.GenerateVideosConfig(
                number_of_videos=1,
                duration_seconds=int(duration_sec),
                aspect_ratio="9:16",
            )

            # Try: multi-image payload first (requested behavior).
            op = None
            try:
                op = client.models.generate_videos(model=model, prompt=prompt, image=reference_images, config=cfg)
            except TypeError:
                # Fallback: SDK only supports a single image.
                one = reference_images[0] if reference_images else None
                op = client.models.generate_videos(model=model, prompt=prompt, image=one, config=cfg)
            except Exception as e:
                return None, f"Veo request failed: {e!s}"
            while not op.done:
                await asyncio.sleep(3)
                op = client.operations.get(op)

            if getattr(op, "error", None):
                err_obj = getattr(op, "error", None)
                msg = None
                try:
                    msg = getattr(err_obj, "message", None) or str(err_obj)
                except Exception:
                    msg = "unknown error"
                return None, msg
            video = op.response.generated_videos[0].video
            clip_file = out_dir / f"{job_id}_clip{clip_index + 1}.mp4"
            wrote = False
            try:
                if hasattr(video, "download"):
                    video.download(str(clip_file))
                    wrote = True
                elif hasattr(video, "data") and video.data:
                    clip_file.write_bytes(video.data)
                    wrote = True
            except Exception:
                wrote = False
            if not wrote or not clip_file.exists() or clip_file.stat().st_size == 0:
                return None, "empty video bytes"
            return clip_file, None

        if req.scenes and len(req.scenes) > 0:
            # Categorize anchors once for the whole reel and format the ordered reference array.
            ref_paths = format_veo_reference_images(req=req)
            ref_objs: list[object] = []
            for rp in ref_paths[:8]:
                img = _to_image_obj(rp)
                if img is not None:
                    ref_objs.append(img)

            for i, seg in enumerate(req.scenes):
                # Veo duration bounds: 4–8 seconds (API enforces this).
                clip_len = min(8, max(4, int(seg.duration_seconds or 8)))
                prompt = build_veo_prompt(base_prompt=seg.description, reference_images_count=len(ref_objs))
                clip_file, err = await _one_veo_clip(
                    clip_index=i, prompt=prompt, reference_images=ref_objs, duration_sec=clip_len
                )
                if clip_file is None:
                    return GenerateVideoResponse(
                        status="failed",
                        job_id=job_id,
                        preview_message=f"Gemini video generation failed for scene {i + 1}: {err or 'unknown'}.",
                        video_url=None,
                        provider=self.name,
                        description=prompts.storyboard.logline,
                        video_prompt=prompts.video_prompt,
                    )
                clip_paths.append(clip_file)
                time.sleep(0.25)
        else:
            # Legacy: one prompt, optionally repeated clips to fill duration.
            ref_paths = format_veo_reference_images(req=req)
            ref_objs: list[object] = []
            for rp in ref_paths[:8]:
                img = _to_image_obj(rp)
                if img is not None:
                    ref_objs.append(img)

            total = int(req.duration_seconds or 8)
            # Veo duration bounds: 4–8 seconds (API enforces this).
            clip_len = 8 if total >= 8 else max(4, total)
            n = max(1, int((total + clip_len - 1) // clip_len))

            prompt = build_veo_prompt(base_prompt=prompts.video_prompt, reference_images_count=len(ref_objs))
            for i in range(n):
                clip_file, err = await _one_veo_clip(
                    clip_index=i, prompt=prompt, reference_images=ref_objs, duration_sec=int(clip_len)
                )
                if clip_file is None:
                    return GenerateVideoResponse(
                        status="failed",
                        job_id=job_id,
                        preview_message=f"Gemini video generation failed: {err or 'unknown'}.",
                        video_url=None,
                        provider=self.name,
                        description=prompts.storyboard.logline,
                        video_prompt=prompts.video_prompt,
                    )
                clip_paths.append(clip_file)
                time.sleep(0.25)

        total = int(req.duration_seconds or 8)

        # If we can't concatenate, return the first clip as a real video.
        if VideoFileClip is None or concatenate_videoclips is None or len(clip_paths) == 1:
            final_name = out_dir / f"{job_id}.mp4"
            clip_paths[0].replace(final_name)
            return GenerateVideoResponse(
                status="completed",
                job_id=job_id,
                preview_message="Generated a real MP4 via Gemini (single clip).",
                video_url=f"/generated_media/{final_name.name}",
                provider=self.name,
                description=prompts.storyboard.logline,
                video_prompt=prompts.video_prompt,
            )

        try:
            clips = [VideoFileClip(str(p)) for p in clip_paths]
            final = concatenate_videoclips(clips, method="compose")
            final_name = out_dir / f"{job_id}.mp4"
            final.write_videofile(str(final_name), codec="libx264", audio_codec="aac", fps=24, logger=None)
            for c in clips:
                try:
                    c.close()
                except Exception:
                    pass
            # Cleanup intermediate clips
            for p in clip_paths:
                try:
                    p.unlink(missing_ok=True)  # type: ignore[arg-type]
                except Exception:
                    pass
            return GenerateVideoResponse(
                status="completed",
                job_id=job_id,
                preview_message=f"Generated a real {total}s MP4 via Gemini (Veo) and concatenated clips.",
                video_url=f"/generated_media/{final_name.name}",
                provider=self.name,
                description=prompts.storyboard.logline,
                video_prompt=prompts.video_prompt,
            )
        except Exception as e:
            # Last resort: return first clip file
            final_name = out_dir / f"{job_id}.mp4"
            clip_paths[0].replace(final_name)
            return GenerateVideoResponse(
                status="completed",
                job_id=job_id,
                preview_message=f"Generated a real MP4 via Gemini, but concatenation failed ({e!s}). Returning first clip.",
                video_url=f"/generated_media/{final_name.name}",
                provider=self.name,
                description=prompts.storyboard.logline,
                video_prompt=prompts.video_prompt,
            )

class RunwayStubProvider(MediaProvider):
    name = "runway_stub"

    async def generate(self, *, req: GenerateVideoRequest, prompts: MediaPrompts) -> GenerateVideoResponse:
        import uuid

        job_id = str(uuid.uuid4())
        return GenerateVideoResponse(
            status="queued",
            job_id=job_id,
            preview_message="Runway configured but not integrated in MVP. This is a stub adapter; swap in real API calls later.",
            video_url=None,
            provider=self.name,
            description=prompts.storyboard.logline,
            video_prompt=prompts.video_prompt,
        )


def pick_provider(*, provider_name: str, has_runway_key: bool) -> MediaProvider:
    name = (provider_name or "mock").lower().strip()
    if name in {"gemini_video", "veo", "veo_video"}:
        return GeminiVeoProvider()
    if name in {"gemini", "gemini_stub"}:
        return GeminiStubProvider()
    if name in {"runway", "runway_stub"}:
        return RunwayStubProvider() if has_runway_key else PlaceholderProvider()
    return PlaceholderProvider()

