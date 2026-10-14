"""Content-based recommendations using genre metadata."""

from __future__ import annotations

import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer


def _genre_lists(catalog: pd.DataFrame) -> list[list[str]]:
    if "genres" in catalog.columns:
        return catalog["genres"].fillna("").map(lambda value: [g for g in str(value).split("|") if g]).tolist()
    if "primary_genre" in catalog.columns:
        return catalog["primary_genre"].fillna("").map(lambda value: [str(value)] if value else []).tolist()
    return [[] for _ in range(len(catalog))]


def recommend_similar_content(catalog: pd.DataFrame, content_id: int, limit: int = 10) -> list[int]:
    """Recommend catalog items with genres similar to a seed content item."""
    if catalog.empty or content_id not in set(catalog["content_id"]):
        return []
    frame = catalog.reset_index(drop=True)
    matrix = MultiLabelBinarizer().fit_transform(_genre_lists(frame))
    seed_index = int(frame.index[frame["content_id"] == content_id][0])
    scores = cosine_similarity(matrix[seed_index : seed_index + 1], matrix)[0]
    ranked = frame.assign(score=scores).query("content_id != @content_id")
    return ranked.sort_values(["score", "content_id"], ascending=[False, True]).head(limit)["content_id"].astype(int).tolist()
