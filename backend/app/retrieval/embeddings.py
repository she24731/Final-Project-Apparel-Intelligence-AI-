from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.embeddings import deterministic_embedding


class EmbeddingPipeline(ABC):
    """Abstraction so we can swap deterministic embeddings for real models later."""

    dim: int = 128

    @abstractmethod
    def embed_text(self, *, text: str, namespace: str) -> list[float]:
        raise NotImplementedError


class DeterministicEmbeddingPipeline(EmbeddingPipeline):
    """Local, deterministic embeddings for demo reliability."""

    dim: int = 128

    def embed_text(self, *, text: str, namespace: str) -> list[float]:
        return deterministic_embedding((namespace, text), dim=self.dim)

