from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.purchase import PurchaseAnalysisResponse
from app.schemas.recommend import RecommendOutfitResponse
from app.schemas.wardrobe import GarmentRecord


class OrchestrationState(BaseModel):
    """Demo-friendly state container for the end-to-end flow."""

    wardrobe: list[GarmentRecord] = Field(default_factory=list)
    last_recommendation: RecommendOutfitResponse | None = None
    last_purchase_analysis: PurchaseAnalysisResponse | None = None
    last_script: str | None = None
    last_video_job_id: str | None = None


def orchestration_diagram_text() -> str:
    return (
        "1) Upload garment image → /ingest-garment\n"
        "   - Extract structured metadata (WardrobeIngestionAgent optional)\n"
        "   - Create embedding (deterministic now, real later)\n"
        "   - Store garment in server memory + ingest into local vector store\n"
        "\n"
        "2) Enter context (occasion/weather/vibe) → /recommend-outfit\n"
        "   - Retrieve style rules + occasion guidance + trend snippets (local RAG)\n"
        "   - Retrieve candidate wardrobe items (by similarity + filters)\n"
        "   - StylingAgent optional; heuristic fallback always available\n"
        "\n"
        "3) Upload candidate purchase item → /analyze-purchase\n"
        "   - Deterministic Buy/No-Buy engine computes: compatibility/versatility/redundancy, est combos\n"
        "   - PurchaseROIAdvisor optional overlays explanation; scores remain deterministic\n"
        "\n"
        "4) Narrative → /generate-script\n"
        "   - NarrativeAgent optional; offline templates fallback\n"
        "\n"
        "5) Media → /generate-video\n"
        "   - Media pipeline: storyboard → image prompts → video prompt → provider adapter\n"
        "   - PlaceholderProvider fallback; Runway stub adapter when key present\n"
    )


def failure_handling_notes() -> dict[str, list[str]]:
    return {
        "ingest": [
            "If agent fails or no API key: fallback to filename/hints heuristics.",
            "If embedding missing: deterministic embedding is generated.",
            "If upload fails: return 400 with error detail.",
        ],
        "recommend": [
            "If retrieval returns few docs: still produce an outfit via heuristic selection.",
            "If StylingAgent fails: return heuristic outfit; include used_live_agent=false.",
        ],
        "purchase": [
            "If wardrobe empty: return MAYBE with conservative scores.",
            "If candidate embedding missing: deterministic embedding is created.",
            "If agent overlay fails: keep deterministic scores and explanation.",
        ],
        "media": [
            "If provider unavailable: PlaceholderProvider returns mock job + preview_message.",
            "If provider errors later: mark job failed; keep prompts for replay.",
        ],
    }


def caching_opportunities() -> list[str]:
    return [
        "Cache deterministic embeddings per (id, category, color, season) tuple.",
        "Cache retrieval results per (occasion, weather, vibe, wardrobe_snapshot_hash).",
        "Cache purchase analytics per (candidate_hash, wardrobe_snapshot_hash).",
        "Cache storyboard/prompts per recommendation id + narrative hash.",
    ]

