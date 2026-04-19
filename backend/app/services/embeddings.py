from __future__ import annotations

import hashlib

import numpy as np


def _hash_seed(parts: tuple[str, ...]) -> int:
    h = hashlib.sha256("||".join(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


def deterministic_embedding(parts: tuple[str, ...], dim: int = 128) -> list[float]:
    """Deterministic pseudo-embedding for demo / offline mode."""
    rng = np.random.default_rng(_hash_seed(parts) % (2**32 - 1))
    vec = rng.normal(0, 1, size=dim).astype(np.float64)
    norm = float(np.linalg.norm(vec)) or 1.0
    vec = vec / norm
    return [float(x) for x in vec.tolist()]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0.0:
        denom = 1.0
    return float(np.dot(va, vb) / denom)


def average_top_k_similarities(candidate: list[float], others: list[list[float]], k: int = 3) -> float:
    if not others:
        return 0.0
    sims = sorted((cosine_similarity(candidate, o) for o in others), reverse=True)
    top = sims[: max(1, min(k, len(sims)))]
    return float(sum(top) / len(top))


def count_outfit_combinations_heuristic(
    candidate_emb: list[float],
    wardrobe_embs: list[list[float]],
    threshold: float = 0.35,
) -> int:
    """Rough count of 'new mix' edges: pairs with sim above threshold."""
    if not wardrobe_embs:
        return 0
    count = 0
    for w in wardrobe_embs:
        if cosine_similarity(candidate_emb, w) >= threshold:
            count += 1
    # Scale to mimic "outfits" not just edges
    base = count * 2
    return int(min(12, max(base, count)))
