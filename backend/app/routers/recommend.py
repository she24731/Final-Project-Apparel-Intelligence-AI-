from __future__ import annotations

from fastapi import APIRouter

from app.agents.orchestrator import recommend_outfit_with_optional_agent
from app.schemas.recommend import RecommendOutfitRequest, RecommendOutfitResponse
from app.services.store import get_store

router = APIRouter(tags=["recommendations"])


@router.post("/recommend-outfit", response_model=RecommendOutfitResponse)
async def recommend_outfit(body: RecommendOutfitRequest) -> RecommendOutfitResponse:
    store = get_store()
    # Demo resilience: ignore stale/local-only IDs instead of failing.
    if body.wardrobe_item_ids:
        wardrobe = store.get_many(body.wardrobe_item_ids)
        if not wardrobe:
            wardrobe = store.all()
    else:
        wardrobe = store.all()
    return await recommend_outfit_with_optional_agent(
        occasion=body.occasion,
        weather=body.weather,
        vibe=body.vibe,
        wardrobe=wardrobe,
        user_preference=body.user_preference,
    )
