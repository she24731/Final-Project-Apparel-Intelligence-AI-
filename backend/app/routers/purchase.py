from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.orchestrator import analyze_purchase_with_optional_agent
from app.schemas.purchase import AnalyzePurchaseRequest, PurchaseAnalysisResponse
from app.services.store import get_store

router = APIRouter(tags=["purchase"])


@router.post("/analyze-purchase", response_model=PurchaseAnalysisResponse)
async def analyze_purchase(body: AnalyzePurchaseRequest) -> PurchaseAnalysisResponse:
    store = get_store()
    wardrobe = store.get_many(body.wardrobe_item_ids) if body.wardrobe_item_ids else store.all()
    missing = set(body.wardrobe_item_ids) - {g.id for g in wardrobe}
    if body.wardrobe_item_ids and missing:
        raise HTTPException(status_code=404, detail=f"Unknown garment ids: {sorted(missing)}")
    return await analyze_purchase_with_optional_agent(body.candidate, wardrobe)
