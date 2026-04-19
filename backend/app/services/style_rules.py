from __future__ import annotations

from pydantic import BaseModel, Field

from app.retrieval.models import Corpus, RetrievalQuery
from app.retrieval.service import get_retrieval_service


class StyleRuleChunk(BaseModel):
    id: str
    text: str
    tags: list[str] = Field(default_factory=list)


def retrieve_style_rules(query_parts: tuple[str, ...], top_n: int = 2) -> list[StyleRuleChunk]:
    """
    Backward-compatible helper used by earlier MVP code.

    Internally delegates to the unified RetrievalService.
    """
    occasion = query_parts[0] if len(query_parts) > 0 else ""
    weather = query_parts[1] if len(query_parts) > 1 else ""
    vibe = query_parts[2] if len(query_parts) > 2 else ""
    q = RetrievalQuery(
        text=f"{occasion} {weather} {vibe}".strip(),
        corpus=[Corpus.style_rules, Corpus.occasion_guidance, Corpus.trend_snippets],
        occasion=occasion or None,
        vibe=vibe or None,
        top_k=top_n,
    )
    hits = get_retrieval_service().search(q).hits[:top_n]
    out: list[StyleRuleChunk] = []
    for h in hits:
        out.append(StyleRuleChunk(id=h.doc.id, text=h.doc.text, tags=h.doc.tags))
    return out
