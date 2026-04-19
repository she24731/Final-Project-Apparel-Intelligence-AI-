from __future__ import annotations

from dataclasses import dataclass

from app.schemas.media import GenerateVideoRequest, GenerateVideoResponse
from app.schemas.recommend import RecommendOutfitResponse
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
        return GenerateVideoResponse(
            status="mock",
            job_id=job_id,
            preview_message="Placeholder runway reel (no provider).",
            video_url=None,
            provider=self.name,
            description=prompts.storyboard.logline,
            narration_text=req.narration_text,
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
        narration = req.narration_text or "Narration: (auto) clean silhouette, calm palette, confident walk."
        face = f"Face anchor: {req.face_anchor_image_path}" if req.face_anchor_image_path else "Face anchor: none"
        return GenerateVideoResponse(
            status="mock",
            job_id=job_id,
            preview_message=(
                "Gemini demo runway reel (no paid provider).\n"
                f"{face}\n"
                f"{narration}\n"
                f"Video prompt: {prompts.video_prompt[:220]}…"
            ),
            video_url=None,
            provider=self.name,
            description=prompts.storyboard.logline,
            narration_text=narration,
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
                narration_text=req.narration_text,
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
                narration_text=req.narration_text,
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

        # Decide source anchor image for image-to-video (prefer selfie).
        anchor_candidates = []
        if req.face_anchor_image_path:
            anchor_candidates.append(req.face_anchor_image_path)
        anchor_candidates.extend(req.anchor_image_paths or [])
        img_obj = None
        if anchor_candidates:
            p = anchor_candidates[0]
            local = (settings.data_dir / p).resolve() if p.startswith("uploads/") or p.startswith("generated_media/") else (settings.data_dir / p).resolve()
            if local.exists():
                try:
                    img_obj = types.Image.from_file(str(local))
                except Exception:
                    img_obj = None

        client = genai.Client(api_key=settings.gemini_api_key)
        model = settings.gemini_video_model

        total = int(req.duration_seconds or 8)
        clip_len = 8 if total >= 8 else max(2, total)
        n = max(1, int((total + clip_len - 1) // clip_len))

        prompt = prompts.video_prompt
        if req.narration_text:
            prompt = f"{prompt}\n\nVoiceover (for timing): {req.narration_text}"

        clip_paths: list[Path] = []
        for i in range(n):
            # Create operation
            op = client.models.generate_videos(
                model=model,
                prompt=prompt,
                image=img_obj,
                config=types.GenerateVideosConfig(
                    number_of_videos=1,
                    duration_seconds=int(clip_len),
                    enhance_prompt=True,
                ),
            )

            # Poll until done (async-friendly)
            while not op.done:
                await asyncio.sleep(3)
                op = client.operations.get(op)

            if getattr(op, "error", None):
                return GenerateVideoResponse(
                    status="failed",
                    job_id=job_id,
                    preview_message=f"Gemini video generation failed: {op.error}",
                    video_url=None,
                    provider=self.name,
                    description=prompts.storyboard.logline,
                    narration_text=req.narration_text,
                    video_prompt=prompts.video_prompt,
                )

            video = op.response.generated_videos[0].video
            # The SDK video object can be downloaded via .download() or has bytes depending on version.
            # We support both patterns.
            clip_file = out_dir / f"{job_id}_clip{i+1}.mp4"
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
                return GenerateVideoResponse(
                    status="failed",
                    job_id=job_id,
                    preview_message="Gemini returned a video payload we couldn't save. (SDK response format changed.)",
                    video_url=None,
                    provider=self.name,
                    description=prompts.storyboard.logline,
                    narration_text=req.narration_text,
                    video_prompt=prompts.video_prompt,
                )

            clip_paths.append(clip_file)
            # Small pause to avoid rate spikes
            time.sleep(0.25)

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
                narration_text=req.narration_text,
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
                narration_text=req.narration_text,
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
                narration_text=req.narration_text,
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
            narration_text=req.narration_text,
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

