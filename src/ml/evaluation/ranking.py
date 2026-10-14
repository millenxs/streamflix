"""Ranking metrics for recommendation evaluation."""

from __future__ import annotations

import math


def precision_at_k(recommended: list[int], relevant: set[int], k: int) -> float:
    """Return precision@k."""
    if k <= 0:
        raise ValueError("k must be positive")
    top_k = recommended[:k]
    return len(set(top_k) & relevant) / k


def recall_at_k(recommended: list[int], relevant: set[int], k: int) -> float:
    """Return recall@k."""
    if not relevant:
        return 0.0
    return len(set(recommended[:k]) & relevant) / len(relevant)


def ndcg_at_k(recommended: list[int], relevant: set[int], k: int) -> float:
    """Return NDCG@k for binary relevance."""
    dcg = sum((1 / math.log2(rank + 1)) for rank, item in enumerate(recommended[:k], start=1) if item in relevant)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0
