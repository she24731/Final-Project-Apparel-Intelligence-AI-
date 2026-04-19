from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.wardrobe import GarmentRecord


class WardrobeDeps(BaseModel):
    """Dependencies for ingestion + styling agents."""

    filename: str = ""
    hints: str | None = None


class StylingDeps(BaseModel):
    occasion: str
    weather: str
    vibe: str
    wardrobe: list[GarmentRecord] = Field(default_factory=list)
    user_preference: str | None = None
    retrieved_rules: str = ""


class PurchaseDeps(BaseModel):
    candidate: GarmentRecord
    wardrobe: list[GarmentRecord] = Field(default_factory=list)
    compatibility_score: float = 0.0
    outfit_combination_potential: int = 0


class NarrativeDeps(BaseModel):
    platform: str
    outfit_summary: str
    user_voice: str | None = None
