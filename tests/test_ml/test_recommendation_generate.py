from datetime import datetime, timezone

import pandas as pd

from src.ml.recommendation.generate import (
    build_recommendations,
    build_user_genre_affinity,
    recommendation_uuid,
)


def test_build_user_genre_affinity_normalizes_preferences() -> None:
    user_genres = pd.DataFrame(
        [
            {"user_id": 1, "primary_genre": "Action", "watch_seconds": 100, "completions": 1},
            {"user_id": 1, "primary_genre": "Drama", "watch_seconds": 100, "completions": 0},
        ]
    )

    affinity = build_user_genre_affinity(user_genres)[1]

    assert affinity["Action"] > affinity["Drama"]
    assert round(sum(affinity.values()), 6) == 1.0


def test_recommendation_uuid_is_deterministic() -> None:
    assert recommendation_uuid("hybrid-v1", 1, 10) == recommendation_uuid("hybrid-v1", 1, 10)


def test_build_recommendations_uses_user_genre_and_excludes_seen_content() -> None:
    users = pd.DataFrame([{"user_id": 1}])
    content = pd.DataFrame(
        [
            {"content_id": 10, "primary_genre": "Action", "watch_time_hours": 10, "completion_rate": 0.9},
            {"content_id": 20, "primary_genre": "Drama", "watch_time_hours": 50, "completion_rate": 0.9},
            {"content_id": 30, "primary_genre": "Action", "watch_time_hours": 5, "completion_rate": 0.8},
        ]
    )
    user_genres = pd.DataFrame(
        [{"user_id": 1, "primary_genre": "Action", "watch_seconds": 1000, "completions": 2}]
    )
    seen = pd.DataFrame([{"user_id": 1, "content_id": 10}])

    recommendations = build_recommendations(
        users,
        content,
        user_genres,
        seen,
        limit=2,
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert recommendations["content_id"].tolist() == [30, 20]
    assert recommendations["algorithm"].unique().tolist() == ["hybrid"]
    assert recommendations["rank"].tolist() == [1, 2]
