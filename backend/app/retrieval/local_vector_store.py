from __future__ import annotations

import threading
from collections.abc import Callable, Iterable

import numpy as np

from app.retrieval.models import RetrievalDoc, RetrievalHit


def _normalize(v: np.ndarray) -> np.ndarray:
    denom = float(np.linalg.norm(v))
    if denom == 0.0:
        denom = 1.0
    return v / denom


class LocalVectorStore:
    """
    Lightweight, in-process vector store.

    - Optimized for demo scale (<10k docs)
    - Deterministic + no external dependencies
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._docs: list[RetrievalDoc] = []
        self._mat: np.ndarray | None = None  # (N, D) normalized

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._docs)

    def upsert_many(self, docs: Iterable[RetrievalDoc]) -> None:
        with self._lock:
            by_id = {d.id: d for d in self._docs}
            for d in docs:
                by_id[d.id] = d
            self._docs = list(by_id.values())
            self._rebuild_matrix_locked()

    def clear(self) -> None:
        with self._lock:
            self._docs = []
            self._mat = None

    def _rebuild_matrix_locked(self) -> None:
        if not self._docs:
            self._mat = None
            return
        mat = np.array([d.embedding for d in self._docs], dtype=np.float64)
        mat = np.apply_along_axis(_normalize, 1, mat)
        self._mat = mat

    def search(
        self,
        *,
        query_embedding: list[float],
        top_k: int,
        filter_fn: Callable[[RetrievalDoc], bool] | None = None,
    ) -> list[RetrievalHit]:
        with self._lock:
            if not self._docs or self._mat is None:
                return []
            q = _normalize(np.array(query_embedding, dtype=np.float64))
            scores = (self._mat @ q).astype(np.float64)  # (N,)
            idxs = np.argsort(-scores)  # desc
            hits: list[RetrievalHit] = []
            for i in idxs.tolist():
                doc = self._docs[int(i)]
                if filter_fn and not filter_fn(doc):
                    continue
                hits.append(RetrievalHit(doc=doc, score=float(scores[int(i)])))
                if len(hits) >= top_k:
                    break
            return hits

