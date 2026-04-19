from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.wardrobe import GarmentRecord


class RecommendOutfitRequest(BaseModel):
    occasion: str = Field(..., examples=["work_presentation", "date_night", "casual_brunch"])
    weather: str = Field(..., examples=["cold_rain", "mild_clear", "hot_humid"])
    vibe: str = Field(..., examples=["quiet_luxury", "streetwear", "classic"])
    wardrobe_item_ids: list[str] = Field(default_factory=list)
    user_preference: str | None = None


class OutfitItemRef(BaseModel):
    garment_id: str
    role: str = Field(..., examples=["base_layer", "statement", "footwear"])


class RecommendOutfitResponse(BaseModel):
    outfit_items: list[OutfitItemRef]
    garments: list[GarmentRecord] = Field(
        default_factory=list,
        description="Resolved garments for convenience in UI",
    )
    explanation: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    retrieved_style_rule_ids: list[str] = Field(default_factory=list)
    used_live_agent: bool = False
