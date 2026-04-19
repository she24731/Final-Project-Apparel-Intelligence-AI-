from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class WardrobeIngestionOutput(BaseModel):
    category: str
    color: str
    formality_score: float = Field(..., ge=0.0, le=1.0)
    season: str
    tags: list[str] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        allowed = {"top", "bottom", "outerwear", "shoes", "accessory"}
        key = v.strip().lower()
        return key if key in allowed else "top"


class StylingAgentOutput(BaseModel):
    garment_ids_in_order: list[str] = Field(default_factory=list)
    roles_in_order: list[str] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class PurchaseROIAdvisorOutput(BaseModel):
    recommendation: Literal["BUY", "NO_BUY", "MAYBE"]
    explanation: str
    rationale_bullets: list[str] = Field(default_factory=list, max_length=8)


class NarrativeAgentOutput(BaseModel):
    script: str
    caption: str | None = None
    hashtags: list[str] | None = None


class ConciergeOutput(BaseModel):
    """Structured routing for the chat concierge (Gemini)."""

    reply: str = Field(..., description="Primary message to show the user (plain text or light Markdown).")
    action: Literal[
        "chat_only",
        "recommend_outfit",
        "write_script",
        "preview_reel",
        "render_video",
        "analyze_purchase",
    ] = "chat_only"
    script_platform: Literal["linkedin", "instagram", "tiktok"] | None = None
    purchase_garment_id: str | None = Field(
        default=None,
        description="Wardrobe garment id when action is analyze_purchase.",
    )
