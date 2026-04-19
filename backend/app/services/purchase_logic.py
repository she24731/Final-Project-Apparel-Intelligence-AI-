from __future__ import annotations

from typing import Literal

from app.schemas.purchase import PurchaseAnalysisResponse
from app.schemas.wardrobe import GarmentRecord
from app.services.embeddings import average_top_k_similarities, count_outfit_combinations_heuristic
from app.services.buy_no_buy_engine import BuyNoBuyEngine


def analyze_purchase_deterministic(
    candidate: GarmentRecord,
    wardrobe: list[GarmentRecord],
) -> PurchaseAnalysisResponse:
    wardrobe_embs = [g.embedding for g in wardrobe]
    compat = average_top_k_similarities(candidate.embedding, wardrobe_embs, k=3) if wardrobe_embs else 0.45
    combos = count_outfit_combinations_heuristic(candidate.embedding, wardrobe_embs)

    engine = BuyNoBuyEngine()
    adv = engine.score(candidate=candidate, wardrobe=wardrobe, context_season=candidate.season)

    if combos > 3 and compat >= 0.55:
        rec: Literal["BUY", "NO_BUY", "MAYBE"] = "BUY"
    elif compat < 0.35 or combos <= 1:
        rec = "NO_BUY"
    else:
        rec = "MAYBE"

    bullets = [
        f"Compatibility vs wardrobe (top-3 mean cosine): {compat:.2f}",
        f"Heuristic new outfit combinations: {combos}",
        f"Candidate category '{candidate.category}' with formality {candidate.formality_score:.2f}",
    ]
    explanation = (
        "Deterministic MVP analysis: favors BUY when the item opens several coherent pairings "
        "and aligns vector-wise with existing pieces."
    )
    return PurchaseAnalysisResponse(
        compatibility_score=round(compat, 4),
        outfit_combination_potential=combos,
        recommendation=rec,
        explanation=explanation,
        rationale_bullets=bullets,
        compatibility_score_0_100=adv.compatibility_score,
        versatility_score_0_100=adv.versatility_score,
        redundancy_score_0_100=adv.redundancy_score,
        estimated_new_combinations=adv.estimated_new_combinations,
        top_matching_existing_items=adv.top_matching_existing_items,
        used_live_agent=False,
    )
