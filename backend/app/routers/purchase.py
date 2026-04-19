from __future__ import annotations

from fastapi import APIRouter

from app.agents.orchestrator import analyze_purchase_with_optional_agent
from app.schemas.purchase import AnalyzePurchaseRequest, PurchaseAnalysisResponse
from app.services.store import get_store

router = APIRouter(tags=["purchase"])


@router.post("/analyze-purchase", response_model=PurchaseAnalysisResponse)
async def analyze_purchase(body: AnalyzePurchaseRequest) -> PurchaseAnalysisResponse:
    store = get_store()
    # Demo resilience: clients may have stale/local-only IDs (e.g., offline fallback on the frontend).
    # Instead of 404-ing, ignore missing IDs and analyze against what we have.
    if body.wardrobe_item_ids:
        wardrobe = store.get_many(body.wardrobe_item_ids)
        if not wardrobe:
            wardrobe = store.all()
    else:
        wardrobe = store.all()
    return await analyze_purchase_with_optional_agent(body.candidate, wardrobe)
