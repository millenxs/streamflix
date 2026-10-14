"""Popularity-based recommendations."""

from __future__ import annotations

import pandas as pd


def popularity_scores(events: pd.DataFrame) -> pd.DataFrame:
    """Score content by watch completions and total watch time."""
    if events.empty:
        return pd.DataFrame(columns=["content_id", "score"])
    grouped = events.groupby("content_id", as_index=False).agg(
        plays=("event_type", lambda values: (values == "play").sum()),
        completes=("completed", "sum"),
        watch_seconds=("watch_seconds", "sum"),
    )
    grouped["score"] = grouped["plays"] + grouped["completes"] * 2 + grouped["watch_seconds"].fillna(0) / 3600
    return grouped[["content_id", "score"]].sort_values(["score", "content_id"], ascending=[False, True], ignore_index=True)


def recommend_popular(events: pd.DataFrame, limit: int = 10) -> list[int]:
    """Return top-N popular content IDs."""
    return popularity_scores(events).head(limit)["content_id"].astype(int).tolist()
