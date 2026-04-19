from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.orchestrator import generate_reel_narration_with_optional_agent, generate_script_with_optional_agent
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
    provider = pick_provider(provider_name=settings.media_provider, has_runway_key=bool(settings.runway_api_key))
    prompts = build_media_prompts(outfit=None, narrative=body.scene_prompt, duration_seconds=body.duration_seconds)
    # Auto narration if missing (Gemini when available; deterministic fallback otherwise)
    narration = body.narration_text
    if narration is None:
        narration = await generate_reel_narration_with_optional_agent(
            outfit_summary=body.scene_prompt,
            face_anchor_present=bool(body.face_anchor_image_path),
            user_voice=None,
        )
        body.narration_text = narration
    res = await provider.generate(req=body, prompts=prompts)
    # Ensure these are always present for the UI.
    if res.description is None:
        res.description = prompts.storyboard.logline
    if res.narration_text is None:
        res.narration_text = body.narration_text
    if res.video_prompt is None:
        res.video_prompt = prompts.video_prompt
    return res


@router.post("/upload-anchor")
async def upload_anchor(file: UploadFile = File(...), kind: str = Form(default="face")) -> dict[str, str]:
    """
    Upload an anchor image (e.g., selfie) to be used in media generation.
    Returns a relative uploads path you can pass to /generate-video.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename on upload")
    if file.content_type and not file.content_type.lower().startswith("image/"):
        raise HTTPException(status_code=415, detail="Unsupported file type. Please upload an image file.")
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
