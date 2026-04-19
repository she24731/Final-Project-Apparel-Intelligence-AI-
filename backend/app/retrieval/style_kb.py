from __future__ import annotations

from app.retrieval.models import Corpus, RetrievalDoc
from app.services.embeddings import deterministic_embedding


def sample_style_docs() -> list[RetrievalDoc]:
    """
    Small curated KB: style rules, occasion guidance, and trends.
    Kept intentionally compact for class-demo reliability.
    """

    def doc(
        *,
        doc_id: str,
        corpus: Corpus,
        text: str,
        tags: list[str],
        colors: list[str] | None = None,
        occasion: str | None = None,
        vibe: str | None = None,
        season: str | None = None,
        category: str | None = None,
    ) -> RetrievalDoc:
        emb = deterministic_embedding(("kb", corpus.value, doc_id, text))
        return RetrievalDoc(
            id=doc_id,
            corpus=corpus,
            text=text,
            embedding=emb,
            tags=tags,
            colors=colors or [],
            occasion=occasion,
            vibe=vibe,
            season=season,
            category=category,
        )

    return [
        doc(
            doc_id="rule_formality_balance",
            corpus=Corpus.style_rules,
            text="Match formality across key anchors (shoes + outerwear). Avoid a single casual item collapsing the whole look.",
            tags=["formality", "anchors"],
        ),
        doc(
            doc_id="rule_color_harmony_3hues",
            corpus=Corpus.style_rules,
            text="Keep the palette to 2–3 main hues; choose one accent in a small surface area (belt, bag, shoe).",
            tags=["color", "palette"],
        ),
        doc(
            doc_id="rule_weather_layering_rain",
            corpus=Corpus.style_rules,
            text="Cold rain: water-resistant outer layer, darker bottoms, and footwear with traction. Add one mid-layer for indoor heat swings.",
            tags=["weather", "layering"],
            season="winter",
        ),
        doc(
            doc_id="occasion_work_presentation",
            corpus=Corpus.occasion_guidance,
            text="Work presentation: prioritize clarity. Clean lines, low-logo, controlled contrast, and footwear that reads intentional on stage.",
            tags=["occasion", "work"],
            occasion="work_presentation",
            vibe="quiet_luxury",
        ),
        doc(
            doc_id="occasion_date_night",
            corpus=Corpus.occasion_guidance,
            text="Date night: elevate one notch above daily baseline. One statement texture is enough; avoid loud patterns that dominate photos.",
            tags=["occasion", "dating"],
            occasion="date_night",
            vibe="classic",
        ),
        doc(
            doc_id="trend_quiet_luxury_2026",
            corpus=Corpus.trend_snippets,
            text="Quiet luxury trend: muted neutrals, subtle texture, relaxed tailoring, premium materials. The signal is restraint.",
            tags=["trend", "quiet_luxury"],
            vibe="quiet_luxury",
            colors=["navy", "cream", "charcoal", "beige"],
        ),
        doc(
            doc_id="trend_tech_chic",
            corpus=Corpus.trend_snippets,
            text="Tech-chic: monochrome base, functional layers, sleek sneakers/boots. Strong silhouette with minimal ornament.",
            tags=["trend", "tech_chic"],
            vibe="tech_chic",
            colors=["black", "gray", "white"],
        ),
    ]

