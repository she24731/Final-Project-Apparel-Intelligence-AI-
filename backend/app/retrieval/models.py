from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Corpus(str, Enum):
    wardrobe = "wardrobe"
    style_rules = "style_rules"
    occasion_guidance = "occasion_guidance"
    trend_snippets = "trend_snippets"


class RetrievalDoc(BaseModel):
    """A single retrievable chunk with typed metadata for filtering."""

    id: str
    corpus: Corpus
    text: str
    embedding: list[float]

    # Common filters (not all corpora use all fields)
    category: str | None = None
    season: str | None = None
    occasion: str | None = None
    vibe: str | None = None

    # Simple normalized color tags (e.g. ["navy", "cream"])
    colors: list[str] = Field(default_factory=list)

    # Additional tags (e.g. ["quiet_luxury", "water_resistant"])
    tags: list[str] = Field(default_factory=list)


class RetrievalQuery(BaseModel):
    """Query with structured facets + free text."""

    text: str
    corpus: list[Corpus] = Field(default_factory=lambda: [Corpus.wardrobe, Corpus.style_rules])

    # Facets
    category: str | None = None
    season: str | None = None
    occasion: str | None = None
    vibe: str | None = None
    desired_colors: list[str] = Field(default_factory=list)
    formality_target: float | None = Field(default=None, ge=0.0, le=1.0)

    # Soft constraints
    top_k: int = Field(default=8, ge=1, le=50)


class RetrievalHit(BaseModel):
    doc: RetrievalDoc
    score: float = Field(..., ge=-1.0, le=1.0, description="Cosine similarity")

