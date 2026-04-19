from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.orchestrator import generate_reel_narration_with_optional_agent, generate_script_with_optional_agent
from app.config import get_settings
from app.media.pipeline import build_anchor_scenes, build_media_prompts
from app.schemas.media import GenerateScriptRequest, GenerateScriptResponse, GenerateVideoRequest, GenerateVideoResponse
from app.schemas.reel_preview import PreviewReelCopyRequest, PreviewReelCopyResponse
from app.services.video_generation import run_generate_video

router = APIRouter(tags=["media"])


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
    )


@router.post("/generate-video", response_model=GenerateVideoResponse)
async def generate_video(body: GenerateVideoRequest) -> GenerateVideoResponse:
    return await run_generate_video(body)


@router.post("/preview-reel-copy", response_model=PreviewReelCopyResponse)
async def preview_reel_copy(body: PreviewReelCopyRequest) -> PreviewReelCopyResponse:
    prompts = build_media_prompts(outfit=None, narrative=body.scene_prompt, duration_seconds=body.duration_seconds)
    narration = body.narration_text
    if narration is None:
        narration = await generate_reel_narration_with_optional_agent(
            outfit_summary=body.scene_prompt,
            face_anchor_present=body.face_anchor_present,
            user_voice=None,
        )
    anchors = list(body.anchor_image_paths)
    scenes = build_anchor_scenes(
        anchor_paths=anchors,
        scene_prompt=body.scene_prompt,
        narration=narration,
        face_anchor_path=body.face_anchor_path,
    )
    return PreviewReelCopyResponse(
        description=prompts.storyboard.logline,
        narration_text=narration,
        video_prompt=prompts.video_prompt,
        scenes=scenes,
    )


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
