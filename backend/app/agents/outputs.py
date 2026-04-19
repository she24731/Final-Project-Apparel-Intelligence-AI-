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
