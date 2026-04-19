from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.embeddings import DeterministicEmbeddingPipeline, EmbeddingPipeline
from app.retrieval.local_vector_store import LocalVectorStore
from app.retrieval.models import Corpus, RetrievalDoc, RetrievalHit, RetrievalQuery
from app.retrieval.style_kb import sample_style_docs
from app.schemas.wardrobe import GarmentRecord


def _norm_color(c: str) -> str:
    return c.strip().lower().replace("grey", "gray")


def wardrobe_doc_from_garment(g: GarmentRecord) -> RetrievalDoc:
    colors = [_norm_color(g.color)] if g.color else []
    return RetrievalDoc(
        id=f"wardrobe:{g.id}",
        corpus=Corpus.wardrobe,
        text=f"{g.category} in {g.color}. tags: {', '.join(g.tags)}. season: {g.season}.",
        embedding=g.embedding,
        category=str(g.category),
        season=g.season,
        colors=colors,
        tags=[t.strip().lower() for t in g.tags],
    )


@dataclass
class RetrievalResult:
    hits: list[RetrievalHit]

    @property
    def docs(self) -> list[RetrievalDoc]:
        return [h.doc for h in self.hits]


class RetrievalService:
    """
    Single entrypoint for RAG-style retrieval across:
    - wardrobe embeddings
    - style-rule KB
    - occasion guidance
    - curated trend snippets
    """

    def __init__(self, *, embedder: EmbeddingPipeline | None = None) -> None:
        self.embedder = embedder or DeterministicEmbeddingPipeline()
        self.store = LocalVectorStore()

        # Load KB by default (wardrobe is ingested at runtime).
        self.store.upsert_many(sample_style_docs())

    def ingest_wardrobe(self, items: list[GarmentRecord]) -> None:
        docs = [wardrobe_doc_from_garment(g) for g in items]
        self.store.upsert_many(docs)

    def ingest_documents(self, docs: list[RetrievalDoc]) -> None:
        self.store.upsert_many(docs)

    def build_query_embedding(self, q: RetrievalQuery) -> list[float]:
        # Embed the natural-language portion. Facets are used in filtering/scoring downstream.
        return self.embedder.embed_text(text=q.text, namespace="retrieval_query")

    def search(self, q: RetrievalQuery) -> RetrievalResult:
        query_emb = self.build_query_embedding(q)
        allowed_corpora = set(q.corpus)
        desired = {_norm_color(c) for c in q.desired_colors}

        def f(doc: RetrievalDoc) -> bool:
            if doc.corpus not in allowed_corpora:
                return False
            if q.category and doc.category and doc.category.lower() != q.category.lower():
                return False
            if q.season and doc.season and doc.season.lower() != q.season.lower():
                return False
            if q.occasion and doc.occasion and doc.occasion.lower() != q.occasion.lower():
                return False
            if q.vibe and doc.vibe and doc.vibe.lower() != q.vibe.lower():
                return False
            if desired and doc.colors:
                if not (desired & {_norm_color(x) for x in doc.colors}):
                    # keep it soft: only filter out when the doc explicitly has colors and none match
                    return False
            return True

        hits = self.store.search(query_embedding=query_emb, top_k=q.top_k, filter_fn=f)
        return RetrievalResult(hits=hits)


_retrieval_service: RetrievalService | None = None


def get_retrieval_service() -> RetrievalService:
    global _retrieval_service  # noqa: PLW0603
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service

