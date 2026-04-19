from __future__ import annotations

from pydantic import BaseModel, Field


class ReelSceneDraft(BaseModel):
    anchor_image_path: str | None = None
    description: str
    narration: str


class PreviewReelCopyRequest(BaseModel):
    scene_prompt: str
    anchor_image_paths: list[str] = Field(default_factory=list)
    face_anchor_path: str | None = None
    duration_seconds: int = Field(default=30, ge=2, le=60)
    face_anchor_present: bool = False
    narration_text: str | None = Field(
        default=None,
        description="If set, skips auto narration generation.",
    )


class PreviewReelCopyResponse(BaseModel):
    description: str
    narration_text: str
    video_prompt: str
    scenes: list[ReelSceneDraft]
