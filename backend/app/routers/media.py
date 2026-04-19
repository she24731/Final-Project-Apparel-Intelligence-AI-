from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.agents.orchestrator import generate_script_with_optional_agent
from app.config import get_settings
from app.media.pipeline import build_media_prompts, pick_provider
from app.schemas.media import GenerateScriptRequest, GenerateScriptResponse, GenerateVideoRequest, GenerateVideoResponse

router = APIRouter(tags=["media"])


@router.post("/generate-script", response_model=GenerateScriptResponse)
async def generate_script(body: GenerateScriptRequest) -> GenerateScriptResponse:
    return await generate_script_with_optional_agent(
        platform=body.platform,
        outfit_summary=body.outfit_summary,
        user_voice=body.user_voice,
    )


@router.post("/generate-video", response_model=GenerateVideoResponse)
async def generate_video(body: GenerateVideoRequest) -> GenerateVideoResponse:
    settings = get_settings()
    provider = pick_provider(has_runway_key=bool(settings.runway_api_key))
    prompts = build_media_prompts(outfit=None, narrative=body.scene_prompt, duration_seconds=body.duration_seconds)
    return await provider.generate(req=body, prompts=prompts)
