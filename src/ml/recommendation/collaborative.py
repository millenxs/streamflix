"""Collaborative filtering recommendations from user-content interactions."""

from __future__ import annotations

import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


def user_item_matrix(events: pd.DataFrame) -> pd.DataFrame:
    """Build a user-content implicit feedback matrix."""
    if events.empty:
        return pd.DataFrame()
    weights = events.assign(weight=events["event_type"].map({"play": 1.0, "complete": 3.0, "like": 4.0}).fillna(0.2))
    return weights.pivot_table(index="user_id", columns="content_id", values="weight", aggfunc="sum", fill_value=0)


def recommend_collaborative(events: pd.DataFrame, user_id: int, limit: int = 10) -> list[int]:
    """Recommend content liked by users similar to ``user_id``."""
    matrix = user_item_matrix(events)
    if matrix.empty or user_id not in matrix.index:
        return []
    similarities = cosine_similarity(matrix.loc[[user_id]], matrix)[0]
    neighbor_weights = pd.Series(similarities, index=matrix.index).drop(index=user_id, errors="ignore")
    scores = neighbor_weights @ matrix.loc[neighbor_weights.index]
    seen = matrix.loc[user_id][matrix.loc[user_id] > 0].index
    ranked = pd.Series(scores).drop(index=seen, errors="ignore").sort_values(ascending=False)
    return ranked.head(limit).index.astype(int).tolist()
