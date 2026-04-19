from __future__ import annotations

import uuid

from app.schemas.recommend import OutfitItemRef, RecommendOutfitResponse
from app.schemas.wardrobe import GarmentRecord
from app.services.embeddings import cosine_similarity, deterministic_embedding
from app.services.style_rules import retrieve_style_rules


def _pick_by_category(items: list[GarmentRecord], category: str) -> GarmentRecord | None:
    for g in items:
        if g.category.lower() == category.lower():
            return g
    return None


def recommend_outfit_deterministic(
    occasion: str,
    weather: str,
    vibe: str,
    wardrobe: list[GarmentRecord],
    user_preference: str | None,
) -> RecommendOutfitResponse:
    rules = retrieve_style_rules((occasion, weather, vibe), top_n=2)
    rule_ids = [r.id for r in rules]

    if not wardrobe:
        return RecommendOutfitResponse(
            outfit_items=[],
            garments=[],
            explanation="Wardrobe is empty. Upload garments before requesting an outfit.",
            confidence=0.2,
            retrieved_style_rule_ids=rule_ids,
            used_live_agent=False,
        )

    tops = [g for g in wardrobe if g.category.lower() == "top"]
    bottoms = [g for g in wardrobe if g.category.lower() == "bottom"]
    shoes = [g for g in wardrobe if g.category.lower() == "shoes"]
    outer = [g for g in wardrobe if g.category.lower() == "outerwear"]

    def best_match(pool: list[GarmentRecord]) -> GarmentRecord | None:
        if not pool:
            return None
        q = deterministic_embedding((occasion, weather, vibe, user_preference or ""))
        best = max(pool, key=lambda g: cosine_similarity(q, g.embedding))
        return best

    top = best_match(tops) or wardrobe[0]
    bottom = best_match(bottoms) or _pick_by_category(wardrobe, "bottom") or wardrobe[min(1, len(wardrobe) - 1)]
    shoe = best_match(shoes) or _pick_by_category(wardrobe, "shoes")
    outw = best_match(outer)

    refs: list[OutfitItemRef] = [
        OutfitItemRef(garment_id=top.id, role="top"),
        OutfitItemRef(garment_id=bottom.id, role="bottom"),
    ]
    resolved = {top.id: top, bottom.id: bottom}
    if shoe and shoe.id not in resolved:
        refs.append(OutfitItemRef(garment_id=shoe.id, role="footwear"))
        resolved[shoe.id] = shoe
    if outw and outw.id not in resolved and ("cold" in weather.lower() or "rain" in weather.lower()):
        refs.append(OutfitItemRef(garment_id=outw.id, role="outerwear"))
        resolved[outw.id] = outw

    garments = list(resolved.values())
    formality_spread = max((g.formality_score for g in garments), default=0.5) - min(
        (g.formality_score for g in garments), default=0.5
    )
    confidence = float(max(0.35, min(0.95, 0.72 - formality_spread)))

    explanation = (
        f"Selected pieces for '{occasion}' under '{weather}' with '{vibe}' vibe. "
        f"Grounded rules: {', '.join(rule_ids)}. "
        f"{(user_preference + ' ') if user_preference else ''}"
    ).strip()

    return RecommendOutfitResponse(
        outfit_items=refs,
        garments=garments,
        explanation=explanation,
        confidence=confidence,
        retrieved_style_rule_ids=rule_ids,
        used_live_agent=False,
    )


def new_garment_id() -> str:
    return str(uuid.uuid4())
