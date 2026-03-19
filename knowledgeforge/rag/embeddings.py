"""Embedding search utilities — cosine similarity over stored embeddings (SPEC §2.4)."""

from __future__ import annotations

import numpy as np


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def rank_by_similarity(
    query_embedding: list[float],
    candidates: list[dict],
    embedding_key: str = "embedding",
    top_k: int = 10,
) -> list[dict]:
    """Rank candidate dicts by cosine similarity to query embedding.

    Each candidate must have an `embedding_key` field containing a list[float].
    Returns top_k candidates with an added 'similarity_score' field.
    """
    scored = []
    for candidate in candidates:
        emb = candidate.get(embedding_key)
        if emb is None:
            continue
        score = cosine_similarity(query_embedding, emb)
        scored.append({**candidate, "similarity_score": score})

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:top_k]
