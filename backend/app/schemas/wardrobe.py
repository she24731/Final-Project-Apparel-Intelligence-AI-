from __future__ import annotations

from pydantic import BaseModel, Field


class GarmentRecord(BaseModel):
    """Canonical wardrobe item stored server-side."""

    id: str = Field(..., description="Stable UUID string")
    category: str = Field(..., examples=["outerwear", "top", "bottom", "shoes", "accessory"])
    color: str
    formality_score: float = Field(..., ge=0.0, le=1.0)
    season: str = Field(..., examples=["all-season", "summer", "winter"])
    tags: list[str] = Field(default_factory=list)
    image_path: str
    embedding: list[float] = Field(..., description="Vector for retrieval; mock or real")


class IngestGarmentResponse(BaseModel):
    garment: GarmentRecord
    ingestion_notes: str | None = None
    used_live_agent: bool = False
