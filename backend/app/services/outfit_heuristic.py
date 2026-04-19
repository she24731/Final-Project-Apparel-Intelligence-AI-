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
    # Confidence should reflect: context match, category coverage, and weather suitability.
    q = deterministic_embedding((occasion, weather, vibe, user_preference or ""))
    sims = [cosine_similarity(q, g.embedding) for g in garments if g.embedding]
    sim_score = (sum(sims) / len(sims)) if sims else 0.0  # [-1, 1] but deterministic embeddings tend positive
    sim_score = max(-1.0, min(1.0, float(sim_score)))

    coverage = 0.0
    coverage += 1.0 if top else 0.0
    coverage += 1.0 if bottom else 0.0
    coverage += 1.0 if shoe else 0.0
    coverage_score = coverage / 3.0  # [0, 1]

    w = weather.lower()
    needs_outer = ("cold" in w) or ("rain" in w) or ("snow" in w) or ("wind" in w)
    has_outer = any(g.category.lower() == "outerwear" for g in garments)
    weather_score = 1.0
    if needs_outer and not has_outer:
        weather_score = 0.65
    if (("rain" in w) or ("snow" in w)) and not shoe:
        weather_score *= 0.85

    # Map similarity from [-1, 1] to [0, 1], then blend.
    sim_0_1 = (sim_score + 1.0) / 2.0
    blended = (0.55 * sim_0_1) + (0.30 * coverage_score) + (0.15 * weather_score)
    confidence = float(max(0.25, min(0.95, blended)))

    pref = user_preference.strip() if user_preference else ""
    explanation = f"Selected pieces for '{occasion}' in '{weather}' with a '{vibe}' vibe."
    if pref:
        explanation = f"{explanation} Preference: {pref}."

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
