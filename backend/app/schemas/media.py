from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GenerateScriptRequest(BaseModel):
    platform: Literal["linkedin", "instagram", "tiktok"] = "linkedin"
    outfit_summary: str
    user_voice: str | None = Field(default=None, description="Short note on tone or persona")


class GenerateScriptResponse(BaseModel):
    script: str
    caption: str | None = None
    used_live_agent: bool = False


class GenerateVideoRequest(BaseModel):
    """MVP hook: describe scenes; provider integration is stubbed."""

    scene_prompt: str
    anchor_image_paths: list[str] = Field(default_factory=list)
    duration_seconds: int = Field(default=5, ge=2, le=60)
    # Optional: provide a selfie/portrait anchor; used for "face" continuity in a real provider.
    face_anchor_image_path: str | None = None
    # Optional: if provided, the provider should treat this as narration voiceover text.
    narration_text: str | None = None


class GenerateVideoResponse(BaseModel):
    status: Literal["queued", "completed", "failed", "mock"]
    job_id: str
    preview_message: str
    video_url: str | None = None
    provider: str = "mock"
    # Surfaced fields for the UI (so narration/description aren't hidden in preview_message)
    description: str | None = None
    narration_text: str | None = None
    video_prompt: str | None = None
