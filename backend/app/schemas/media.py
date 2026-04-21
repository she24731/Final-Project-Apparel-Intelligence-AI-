from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReelVideoScenePayload(BaseModel):
    """One timed shot in a multi-scene reel (concatenated into a single MP4)."""

    anchor_image_path: str | None = None
    # Prefer this image for rendering/animation if present (AI-generated still).
    render_image_path: str | None = None
    anchor_type: Literal["face", "wardrobe", "none"] = "wardrobe"
    description: str
    duration_seconds: int = Field(default=8, ge=2, le=16)


class GenerateScriptRequest(BaseModel):
    platform: Literal["linkedin", "instagram", "tiktok"] = "linkedin"
    outfit_summary: str
    user_voice: str | None = Field(default=None, description="Short note on tone or persona")
    tone: str | None = Field(default=None, description="e.g. warm, crisp, authoritative")
    emotion: str | None = Field(default=None, description="e.g. grounded excitement, calm confidence")
    target_audience: str | None = Field(default=None, description="Who should feel spoken to")
    scenario: str | None = Field(default=None, description="Where this is filmed / context")
    vibe: str | None = Field(default=None, description="Aesthetic vibe label")
    variation_salt: str | None = Field(
        default=None,
        description="Optional per-request salt to force heterogeneous drafts across repeated clicks.",
    )


class GenerateScriptResponse(BaseModel):
    script: str
    caption: str | None = None
    hashtags: list[str] | None = None
    used_live_agent: bool = False


class GenerateVideoRequest(BaseModel):
    """MVP hook: describe scenes; provider integration is stubbed."""

    scene_prompt: str
    anchor_image_paths: list[str] = Field(default_factory=list)
    duration_seconds: int = Field(default=5, ge=2, le=60)
    # When true, do NOT fall back to local slideshow/zoom-pan.
    # If a real motion video provider is unavailable, return failed instead.
    require_fmv: bool = False
    # Optional: provide a selfie/portrait anchor; used for "face" continuity in a real provider.
    face_anchor_image_path: str | None = None
    # Optional: uploaded audio file to use as background music (muxed into final MP4 when possible).
    background_music_path: str | None = None
    # When non-empty, video provider generates one clip per scene (same order) then concatenates.
    scenes: list[ReelVideoScenePayload] = Field(default_factory=list)


class GenerateVideoResponse(BaseModel):
    status: Literal["queued", "completed", "failed", "mock"]
    job_id: str
    preview_message: str
    video_url: str | None = None
    provider: str = "mock"
    # Surfaced fields for the UI (so description isn't hidden in preview_message)
    description: str | None = None
    video_prompt: str | None = None
