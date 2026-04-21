from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.media import GenerateScriptResponse, GenerateVideoResponse
from app.schemas.recommend import RecommendOutfitResponse


class ChatContext(BaseModel):
    occasion: str = ""
    weather: str = ""
    vibe: str = ""
    preference: str = ""
    wardrobe_item_ids: list[str] = Field(default_factory=list)
    outfit_summary: str | None = None
    face_anchor_path: str | None = None


class AssistantTurnRequest(BaseModel):
    message: str
    context: ChatContext = Field(default_factory=ChatContext)


class AssistantTurnResponse(BaseModel):
    reply: str
    actions: list[str] = Field(default_factory=list)
    recommendation: RecommendOutfitResponse | None = None
    script: GenerateScriptResponse | None = None
    video: GenerateVideoResponse | None = None
    updated_context: ChatContext | None = None
