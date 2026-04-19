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
        est_combos = int(min(20, max(0, len(cross_cat_edges) * 2 + (1 if len(pair_edges) >= 6 else 0))))

        # Scores (0-100)
        compat = _clamp_int((mean_top3 * self.similarity_weight) + (complement * self.complementarity_weight) + 20.0)
        versatility = _clamp_int(
            (len({str(g.category).lower() for g in cross_cat_edges}) / 4.0) * 60.0
            + (complement * 25.0)
            + _season_bonus(candidate.season, context_season)
            + 10.0
        )
        redundancy = _clamp_int((same_cat_max * self.redundancy_penalty_weight) + (max_sim * 35.0))

        # Recommendation decision
        if compat >= 70 and versatility >= 60 and redundancy <= 55 and est_combos >= 4:
            rec: Decision = "BUY"
        elif redundancy >= 75 or est_combos <= 1:
            rec = "NO_BUY"
        else:
            rec = "MAYBE"

        explanation = (
            f"compat={compat}/100, versatility={versatility}/100, redundancy={redundancy}/100, "
            f"new_combos≈{est_combos}. Top similarity={max_sim:.2f}, top-3 mean={mean_top3:.2f}. "
            f"Decision favors BUY when cross-category pairing coverage is strong without heavy same-category overlap."
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

