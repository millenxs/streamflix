"""Hybrid recommendation utilities."""

from __future__ import annotations

from collections import defaultdict


def blend_rankings(rankings: list[list[int]], weights: list[float] | None = None, limit: int = 10) -> list[int]:
    """Blend ranked recommendation lists with reciprocal-rank scoring."""
    if weights is None:
        weights = [1.0] * len(rankings)
    scores: dict[int, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights, strict=False):
        for rank, content_id in enumerate(ranking, start=1):
            scores[int(content_id)] += weight / rank
    return [content_id for content_id, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]]
