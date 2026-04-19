from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.wardrobe import GarmentRecord
from app.services.embeddings import cosine_similarity


Decision = Literal["BUY", "MAYBE", "NO_BUY"]


@dataclass(frozen=True)
class BuyNoBuyResult:
    compatibility_score: int  # 0-100
    versatility_score: int  # 0-100
    redundancy_score: int  # 0-100 (higher means more redundant / worse)
    estimated_new_combinations: int
    recommendation: Decision
    explanation: str
    top_matching_existing_items: list[str]


def _clamp_int(x: float) -> int:
    return int(max(0, min(100, round(x))))


def _season_bonus(candidate_season: str, context_season: str | None) -> float:
    if not context_season:
        return 0.0
    cs = candidate_season.lower()
    qs = context_season.lower()
    if cs == "all-season":
        return 6.0
    if cs == qs:
        return 8.0
    return -3.0


class BuyNoBuyEngine:
    """
    Deterministic baseline algorithm.

    Upgrade path:
    - replace cosine similarity with CLIP/text-image embeddings
    - learn weights from labeled outcomes
    - incorporate real outfit-graph generation
    """

    def __init__(
        self,
        *,
        similarity_weight: float = 55.0,
        complementarity_weight: float = 25.0,
        season_weight: float = 10.0,
        redundancy_penalty_weight: float = 35.0,
    ) -> None:
        self.similarity_weight = similarity_weight
        self.complementarity_weight = complementarity_weight
        self.season_weight = season_weight
        self.redundancy_penalty_weight = redundancy_penalty_weight

    def score(
        self,
        *,
        candidate: GarmentRecord,
        wardrobe: list[GarmentRecord],
        occasion: str | None = None,
        vibe: str | None = None,
        context_season: str | None = None,
    ) -> BuyNoBuyResult:
        if not wardrobe:
            return BuyNoBuyResult(
                compatibility_score=62,
                versatility_score=55,
                redundancy_score=10,
                estimated_new_combinations=2,
                recommendation="MAYBE",
                explanation="Wardrobe is empty, so we cannot estimate redundancy or pairing coverage reliably.",
                top_matching_existing_items=[],
            )

        # Formality alignment: compatibility is higher when candidate sits near the wardrobe's center of gravity.
        avg_formality = sum(float(g.formality_score) for g in wardrobe) / max(1, len(wardrobe))
        formality_match = 1.0 - min(1.0, abs(float(candidate.formality_score) - avg_formality))  # 0..1

        # Similarity profile (high similarity = compatibility, but *too* high can mean redundancy)
        sims: list[tuple[float, GarmentRecord]] = []
        for g in wardrobe:
            sims.append((cosine_similarity(candidate.embedding, g.embedding), g))
        sims.sort(key=lambda x: x[0], reverse=True)

        top_matches = sims[:5]
        top_ids = [g.id for _, g in top_matches]

        mean_top3 = sum(s for s, _ in sims[:3]) / max(1, min(3, len(sims)))
        max_sim = sims[0][0]

        # Complementarity heuristic:
        # candidate should connect to multiple categories, not only duplicates of itself.
        by_cat: dict[str, float] = {}
        for s, g in sims:
            cat = str(g.category).lower()
            by_cat[cat] = max(by_cat.get(cat, -1.0), s)
        non_self = [v for k, v in by_cat.items() if k != str(candidate.category).lower()]
        complement = sum(sorted(non_self, reverse=True)[:2]) / (2 if len(non_self) >= 2 else 1)

        # Redundancy: items already very close in the same category.
        same_cat = [s for s, g in sims if str(g.category).lower() == str(candidate.category).lower()]
        same_cat_max = max(same_cat) if same_cat else 0.0

        # Estimated new combinations:
        # Count wardrobe items above a pairing threshold, discounting same-category links.
        pair_threshold = 0.35
        pair_edges = [g for s, g in sims if s >= pair_threshold]
        cross_cat_edges = [g for s, g in sims if s >= pair_threshold and str(g.category).lower() != str(candidate.category).lower()]
        est_combos_sim = int(min(20, max(0, len(cross_cat_edges) * 2 + (1 if len(pair_edges) >= 6 else 0))))

        # Also estimate combinations from wardrobe coverage so the number is intuitive in demos
        # even when embeddings are low-signal.
        cat_counts: dict[str, int] = {}
        for g in wardrobe:
            cat_counts[str(g.category).lower()] = cat_counts.get(str(g.category).lower(), 0) + 1
        tops = cat_counts.get("top", 0)
        bottoms = cat_counts.get("bottom", 0)
        shoes = cat_counts.get("shoes", 0)
        cand_cat = str(candidate.category).lower()
        if cand_cat == "shoes":
            est_combos_struct = int(min(12, max(1, (tops + bottoms) // 2)))
        elif cand_cat == "top":
            est_combos_struct = int(min(12, max(1, (bottoms + shoes) // 2)))
        elif cand_cat == "bottom":
            est_combos_struct = int(min(12, max(1, (tops + shoes) // 2)))
        elif cand_cat == "outerwear":
            est_combos_struct = int(min(8, max(1, (tops + bottoms) // 3)))
        else:
            est_combos_struct = int(min(6, max(1, (tops + bottoms + shoes) // 4)))

        est_combos = int(max(est_combos_sim, est_combos_struct))

        # Make "outfit potential" respond to formality in a predictable way:
        # best when formality matches the wardrobe average; lower when it's far off.
        # multiplier in [0.6, 1.4], peaking at match=1.0.
        combo_multiplier = 0.6 + 0.8 * float(formality_match)
        est_combos = int(max(1, min(20, round(est_combos * combo_multiplier))))

        # Scores (0-100)
        # Add a small, predictable formality term so user adjustments have a visible effect.
        formality_term = (formality_match - 0.5) * 18.0  # [-9, +9]
        compat = _clamp_int(
            (mean_top3 * self.similarity_weight) + (complement * self.complementarity_weight) + 20.0 + formality_term
        )
        versatility = _clamp_int(
            (len({str(g.category).lower() for g in cross_cat_edges}) / 4.0) * 60.0
            + (complement * 25.0)
            + _season_bonus(candidate.season, context_season)
            + 10.0
            + (formality_match - 0.5) * 10.0
        )
        redundancy = _clamp_int((same_cat_max * self.redundancy_penalty_weight) + (max_sim * 35.0))

        # Recommendation decision (score-based to avoid "always MAYBE"):
        #
        # We compute a single purchase score from:
        # - compatibility (higher = better)
        # - versatility (higher = better)
        # - redundancy (lower = better)
        # - outfit potential (diminishing returns)
        #
        # Then map score -> BUY/MAYBE/NO_BUY with a couple safety gates.
        # Outfit potential should meaningfully move the verdict in a demo.
        # Use diminishing returns so the score doesn't blow up.
        combo_bonus = (min(12.0, float(est_combos)) ** 0.85) * 6.0  # ~0..~44
        purchase_score = (
            0.42 * float(compat)
            + 0.33 * float(versatility)
            + 0.25 * float(100 - redundancy)
            + combo_bonus
        )  # ~0..~144

        # Safety gates
        if redundancy >= 95:
            rec: Decision = "NO_BUY"
        # Strong pairing potential should generally qualify as BUY unless redundancy is notable.
        elif est_combos >= 10 and redundancy <= 80:
            rec = "BUY"
        # High potential + not redundant should become BUY more often.
        elif purchase_score >= 82 and redundancy <= 78 and est_combos >= 5:
            rec = "BUY"
        # Reserve NO_BUY for low score AND low potential (or very weak fit).
        elif purchase_score <= 66 and (est_combos <= 2 or compat <= 40):
            rec = "NO_BUY"
        else:
            rec = "MAYBE"

        explanation = (
            f"compat={compat}/100, versatility={versatility}/100, redundancy={redundancy}/100, "
            f"new_combos≈{est_combos}, score={purchase_score:.1f}. "
            f"Top similarity={max_sim:.2f}, top-3 mean={mean_top3:.2f}."
        )

        return BuyNoBuyResult(
            compatibility_score=compat,
            versatility_score=versatility,
            redundancy_score=redundancy,
            estimated_new_combinations=est_combos,
            recommendation=rec,
            explanation=explanation,
            top_matching_existing_items=top_ids,
        )

