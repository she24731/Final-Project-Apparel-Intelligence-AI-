from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReelSceneDraft(BaseModel):
    anchor_image_path: str | None = None
    anchor_type: Literal["face", "wardrobe", "none"] = "wardrobe"
    label: str = ""
    duration_seconds: int = Field(default=8, ge=2, le=30)
    description: str
    # Optional generated assets derived from anchor/context + copy.
    generated_image_path: str | None = None
    # Optional animated preview clip (Ken Burns + VO), used for “film-like” per-scene output.
    generated_video_path: str | None = None


class PreviewReelCopyRequest(BaseModel):
    scene_prompt: str
    idealization: str | None = Field(
        default=None,
        description="Optional creative direction (tone, era, film reference, constraints) layered on top of scene_prompt.",
    )
    anchor_image_paths: list[str] = Field(default_factory=list)
    face_anchor_path: str | None = None
    duration_seconds: int = Field(default=30, ge=2, le=60)
    face_anchor_present: bool = False


class PreviewReelCopyResponse(BaseModel):
    description: str
    video_prompt: str
    scenes: list[ReelSceneDraft]
