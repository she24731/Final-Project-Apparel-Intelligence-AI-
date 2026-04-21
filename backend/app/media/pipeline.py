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
    One editable block per anchor image (face first, then wardrobe product shots).
    """
    wardrobe_paths = [p for p in anchor_paths if p]
    paths: list[str] = []
    if face_anchor_path:
        paths.append(face_anchor_path)
    for p in wardrobe_paths:
        if p not in paths:
            paths.append(p)

    if not paths:
        return [
            ReelSceneDraft(
                anchor_image_path=None,
                anchor_type="none",
                label="Scene 1/1",
                duration_seconds=8,
                description=scene_prompt[:280],
            ),
        ]

    sec = max(4, min(8, 30 // max(len(paths), 1)))
    scenes: list[ReelSceneDraft] = []
    for i, p in enumerate(paths):
        label = p.split("/")[-1]
        at: Literal["face", "wardrobe", "none"] = "face" if face_anchor_path and p == face_anchor_path else "wardrobe"
        scenes.append(
            ReelSceneDraft(
                anchor_image_path=p,
                anchor_type=at,
                label=f"Scene {i + 1}/{len(paths)} — {label}",
                duration_seconds=sec,
                description=f"Scene {i + 1} — highlight {label}: {scene_prompt[:120].strip()}",
            ),
        )
    return scenes


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

        clip_paths: list[Path] = []

        async def _one_veo_clip(
            *,
            clip_index: int,
            prompt: str,
            image_obj: object | None,
            duration_sec: int,
        ) -> tuple[Path | None, str | None]:
            op = client.models.generate_videos(
                model=model,
                prompt=prompt,
                image=image_obj,
                config=types.GenerateVideosConfig(
                    number_of_videos=1,
                    duration_seconds=int(duration_sec),
                    aspect_ratio="9:16",
                ),
            )
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
            for i, seg in enumerate(req.scenes):
                img_obj = None
                # Prefer AI-generated still if present, otherwise the original anchor still.
                img_path = seg.render_image_path or seg.anchor_image_path
                if img_path:
                    lp = _local_image_path(img_path)
                    if lp.exists():
                        try:
                            img_obj = types.Image.from_file(str(lp))
                        except Exception:
                            img_obj = None
                # Veo duration bounds: 4–8 seconds (API enforces this).
                clip_len = min(8, max(4, int(seg.duration_seconds or 8)))
                prompt = seg.description
                clip_file, err = await _one_veo_clip(clip_index=i, prompt=prompt, image_obj=img_obj, duration_sec=clip_len)
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
            anchor_candidates = []
            if req.face_anchor_image_path:
                anchor_candidates.append(req.face_anchor_image_path)
            anchor_candidates.extend(req.anchor_image_paths or [])
            img_obj = None
            if anchor_candidates:
                p = anchor_candidates[0]
                local = _local_image_path(p)
                if local.exists():
                    try:
                        img_obj = types.Image.from_file(str(local))
                    except Exception:
                        img_obj = None

            total = int(req.duration_seconds or 8)
            # Veo duration bounds: 4–8 seconds (API enforces this).
            clip_len = 8 if total >= 8 else max(4, total)
            n = max(1, int((total + clip_len - 1) // clip_len))

            prompt = prompts.video_prompt
            for i in range(n):
                clip_file, err = await _one_veo_clip(clip_index=i, prompt=prompt, image_obj=img_obj, duration_sec=int(clip_len))
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

