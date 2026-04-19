from __future__ import annotations

from dataclasses import dataclass

from app.schemas.media import GenerateVideoRequest, GenerateVideoResponse
from app.schemas.recommend import RecommendOutfitResponse


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
            preview_message=f"Placeholder runway reel (no provider). Video prompt: {prompts.video_prompt[:160]}…",
            video_url=None,
            provider=self.name,
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
        )


def pick_provider(*, has_runway_key: bool) -> MediaProvider:
    return RunwayStubProvider() if has_runway_key else PlaceholderProvider()

