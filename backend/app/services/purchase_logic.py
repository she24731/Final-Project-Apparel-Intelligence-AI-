from __future__ import annotations

from typing import Literal

from app.schemas.purchase import PurchaseAnalysisResponse
from app.schemas.wardrobe import GarmentRecord
from app.schemas.purchase import OutfitSuggestion
from app.services.embeddings import average_top_k_similarities, cosine_similarity, count_outfit_combinations_heuristic, deterministic_embedding
from app.services.buy_no_buy_engine import BuyNoBuyEngine


def analyze_purchase_deterministic(
    candidate: GarmentRecord,
    wardrobe: list[GarmentRecord],
) -> PurchaseAnalysisResponse:
    # If the client intentionally clears embedding (e.g., user edits metadata),
    # regenerate a deterministic embedding so scores respond to those edits.
    if not candidate.embedding:
        tags = ",".join(candidate.tags or [])
        candidate.embedding = deterministic_embedding(
            (
                str(candidate.category),
                str(candidate.color),
                f"{float(candidate.formality_score):.2f}",
                str(candidate.season),
                tags,
            )
        )

    wardrobe_embs = [g.embedding for g in wardrobe]
    compat = average_top_k_similarities(candidate.embedding, wardrobe_embs, k=3) if wardrobe_embs else 0.45
    combos = count_outfit_combinations_heuristic(candidate.embedding, wardrobe_embs) if wardrobe_embs else 0

    # Make the score respond to user-edited metadata (even when embeddings are noisy/mocked).
    if not wardrobe:
        # With no wardrobe, still reflect candidate's stated formality in the baseline.
        compat = float(max(0.0, min(1.0, 0.38 + 0.24 * float(candidate.formality_score))))
        combos = int(max(0, min(6, round(1 + 5 * (1.0 - abs(float(candidate.formality_score) - 0.55))))))
    else:
        avg_formality = sum(g.formality_score for g in wardrobe) / len(wardrobe)
        formality_match = 1.0 - min(1.0, abs(float(candidate.formality_score) - float(avg_formality)))
        # [-0.06, +0.06]
        formality_bonus = (formality_match - 0.5) * 0.12

        cand_color = str(candidate.color or "").lower().strip()
        color_matches = sum(1 for g in wardrobe if str(g.color or "").lower().strip() == cand_color) if cand_color else 0
        color_ratio = color_matches / max(1, len(wardrobe))
        # [-0.02, +0.06]
        color_bonus = (color_ratio * 0.08) - 0.02

        compat = float(max(0.0, min(1.0, compat + formality_bonus + color_bonus)))

        # Category-based combination potential: shoes pair with tops+bottoms, etc.
        by_cat: dict[str, int] = {}
        for g in wardrobe:
            by_cat[str(g.category).lower()] = by_cat.get(str(g.category).lower(), 0) + 1
        cand_cat = str(candidate.category).lower()
        if cand_cat == "shoes":
            combos += int(min(6, (by_cat.get("top", 0) + by_cat.get("bottom", 0)) / 4))
        elif cand_cat == "top":
            combos += int(min(6, (by_cat.get("bottom", 0) + by_cat.get("shoes", 0)) / 4))
        elif cand_cat == "bottom":
            combos += int(min(6, (by_cat.get("top", 0) + by_cat.get("shoes", 0)) / 4))
        elif cand_cat == "outerwear":
            combos += int(min(4, (by_cat.get("top", 0) + by_cat.get("bottom", 0)) / 6))

    engine = BuyNoBuyEngine()
    adv = engine.score(candidate=candidate, wardrobe=wardrobe, context_season=candidate.season)

    # Use the engine's recommendation so verdict isn't stuck on legacy thresholds.
    rec: Literal["BUY", "NO_BUY", "MAYBE"] = adv.recommendation

    # Build concrete pairings so users can see "what outfits" it fits.
    # We select cross-category matches, then enumerate combinations ranked by similarity.
    def best_in_category(cat: str, exclude: set[str], k: int = 8) -> list[GarmentRecord]:
        pool = [g for g in wardrobe if str(g.category).lower() == cat and g.id not in exclude]
        scored = sorted(pool, key=lambda g: cosine_similarity(candidate.embedding, g.embedding), reverse=True)
        return scored[:k]

    cand_cat = str(candidate.category).lower()
    exclude_ids: set[str] = {candidate.id}

    tops = best_in_category("top", exclude_ids)
    bottoms = best_in_category("bottom", exclude_ids)
    shoes = best_in_category("shoes", exclude_ids)
    outers = best_in_category("outerwear", exclude_ids)

    def _occasion_label(avg_formality: float) -> str:
        if avg_formality >= 0.72:
            return "formal / interview"
        if avg_formality >= 0.56:
            return "work / smart casual"
        if avg_formality >= 0.40:
            return "casual day"
        return "off-duty / relaxed"

    def _quick_title(avg_formality: float) -> str:
        if avg_formality >= 0.72:
            return "Polished, formal set"
        if avg_formality >= 0.56:
            return "Client-ready, clean set"
        if avg_formality >= 0.40:
            return "Everyday clean set"
        return "Relaxed, low-key set"

    # Enumerate candidate pairings (ranked), and return up to outfit potential.
    # We cap to 20 to keep response size reasonable.
    wanted = int(max(0, min(20, adv.estimated_new_combinations)))

    combos_ranked: list[tuple[float, list[GarmentRecord]]] = []

    def sim(g: GarmentRecord) -> float:
        return cosine_similarity(candidate.embedding, g.embedding)

    if wardrobe and wanted > 0:
        if cand_cat == "shoes":
            for t in tops[:8]:
                for b in bottoms[:8]:
                    base = [t, b]
                    # Optional outerwear for the first few (when available)
                    for o in ([None] + outers[:3]):  # type: ignore[list-item]
                        items = base + ([o] if o else [])
                        score = sum(sim(x) for x in items) / len(items)
                        combos_ranked.append((score, items))
        elif cand_cat == "top":
            for b in bottoms[:8]:
                for s in shoes[:8]:
                    base = [b, s]
                    for o in ([None] + outers[:3]):  # type: ignore[list-item]
                        items = base + ([o] if o else [])
                        score = sum(sim(x) for x in items) / len(items)
                        combos_ranked.append((score, items))
        elif cand_cat == "bottom":
            for t in tops[:8]:
                for s in shoes[:8]:
                    base = [t, s]
                    for o in ([None] + outers[:3]):  # type: ignore[list-item]
                        items = base + ([o] if o else [])
                        score = sum(sim(x) for x in items) / len(items)
                        combos_ranked.append((score, items))
        else:
            # outerwear / accessory
            for t in tops[:8]:
                for b in bottoms[:8]:
                    items = [t, b]
                    if shoes:
                        items.append(shoes[0])
                    score = sum(sim(x) for x in items) / len(items)
                    combos_ranked.append((score, items))

    combos_ranked.sort(key=lambda x: x[0], reverse=True)

    suggestions: list[OutfitSuggestion] = []
    seen: set[tuple[str, ...]] = set()
    for _, items in combos_ranked:
        ids = tuple(sorted([g.id for g in items]))
        if ids in seen:
            continue
        seen.add(ids)
        avg_form = sum(float(g.formality_score) for g in items) / len(items)
        occ = _occasion_label(avg_form)
        title = _quick_title(avg_form)
        desc = f"Best for {occ}. Balanced formality around {avg_form:.2f}; selected as strong cross-category matches."
        suggestions.append(
            OutfitSuggestion(
                title=title,
                occasion=occ,
                description=desc,
                garment_ids=[g.id for g in items],
                reason="Picked from your wardrobe by similarity + category coverage.",
            )
        )
        if len(suggestions) >= wanted:
            break

    bullets = [
        f"Compatibility vs wardrobe (0–1): {compat:.2f}",
        f"Estimated new combinations: {adv.estimated_new_combinations}",
        f"Candidate category '{candidate.category}' with formality {candidate.formality_score:.2f}",
    ]
    explanation = (
        "Deterministic MVP analysis: favors BUY when the item opens several coherent pairings "
        "and aligns vector-wise with existing pieces."
    )
    return PurchaseAnalysisResponse(
        # Drive legacy fields from the richer engine outputs for more intuitive behavior.
        compatibility_score=round(float(adv.compatibility_score) / 100.0, 4),
        outfit_combination_potential=int(adv.estimated_new_combinations),
        recommendation=rec,
        explanation=explanation,
        rationale_bullets=bullets,
        compatibility_score_0_100=adv.compatibility_score,
        versatility_score_0_100=adv.versatility_score,
        redundancy_score_0_100=adv.redundancy_score,
        estimated_new_combinations=adv.estimated_new_combinations,
        top_matching_existing_items=adv.top_matching_existing_items,
        outfit_suggestions=suggestions,
        decision_criteria=[
            "We compute a purchase score from compatibility, versatility, (100 - redundancy), and outfit potential.",
            "BUY: score is high, redundancy isn't high, and outfit potential is strong.",
            "NO_BUY: redundancy is extremely high, or the score is low with weak fit/low combos.",
            "MAYBE: the middle band (some potential, but not a clear additive purchase).",
        ],
        used_live_agent=False,
    )
