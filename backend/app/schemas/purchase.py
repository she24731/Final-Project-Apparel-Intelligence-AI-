from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.wardrobe import GarmentRecord


class AnalyzePurchaseRequest(BaseModel):
    """Analyze a candidate item against the current wardrobe."""

    candidate: GarmentRecord = Field(
        ...,
        description="Client may send inferred metadata; image_path may be a temp id",
    )
    wardrobe_item_ids: list[str] = Field(default_factory=list)


class PurchaseAnalysisResponse(BaseModel):
    # Legacy MVP fields (kept for frontend compatibility)
    compatibility_score: float = Field(..., ge=0.0, le=1.0, description="0..1 legacy compatibility")
    outfit_combination_potential: int = Field(..., ge=0, description="Legacy heuristic count of outfits")

    # Prompt 6 analytics fields (preferred for reporting)
    compatibility_score_0_100: int | None = Field(default=None, ge=0, le=100)
    versatility_score_0_100: int | None = Field(default=None, ge=0, le=100)
    redundancy_score_0_100: int | None = Field(default=None, ge=0, le=100)
    estimated_new_combinations: int | None = Field(default=None, ge=0)
    top_matching_existing_items: list[str] = Field(default_factory=list)
    recommendation: Literal["BUY", "NO_BUY", "MAYBE"]
    explanation: str
    rationale_bullets: list[str] = Field(default_factory=list)
    used_live_agent: bool = False
