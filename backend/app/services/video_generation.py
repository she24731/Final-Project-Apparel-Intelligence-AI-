from __future__ import annotations

from app.agents.orchestrator import generate_reel_narration_with_optional_agent
from app.config import get_settings
from app.media.pipeline import build_media_prompts, pick_provider
from app.schemas.media import GenerateVideoRequest, GenerateVideoResponse


async def run_generate_video(body: GenerateVideoRequest) -> GenerateVideoResponse:
    settings = get_settings()
    provider = pick_provider(provider_name=settings.media_provider, has_runway_key=bool(settings.runway_api_key))
    prompts = build_media_prompts(outfit=None, narrative=body.scene_prompt, duration_seconds=body.duration_seconds)
    narration = body.narration_text
    if narration is None:
        narration = await generate_reel_narration_with_optional_agent(
            outfit_summary=body.scene_prompt,
            face_anchor_present=bool(body.face_anchor_image_path),
            user_voice=None,
        )
    req = body.model_copy(update={"narration_text": narration})
    res = await provider.generate(req=req, prompts=prompts)
    if res.description is None:
        res.description = prompts.storyboard.logline
    if res.narration_text is None:
        res.narration_text = narration
    if res.video_prompt is None:
        res.video_prompt = prompts.video_prompt
    return res
