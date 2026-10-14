"""FastAPI service for StreamFlix recommendations and feedback."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from uuid import uuid4

import pandas as pd
import psycopg2
from fastapi import FastAPI

from src.api.models.recommendations import RecommendationFeedback, RecommendationItem, RecommendationResponse
from src.api.thumbnail import choose_thumbnail_variant
from src.experiments.ab_testing import assign_variant
from src.generation.events import DatabaseSettings
from src.ml.recommendation.baseline import recommend_popular

app = FastAPI(title="StreamFlix Recommendation API", version="0.1.0")

# In-memory fallback data keeps the service usable before model artifacts exist.
SAMPLE_EVENTS = pd.DataFrame(
    [
        {"user_id": 1, "content_id": 10, "event_type": "play", "completed": False, "watch_seconds": 120},
        {"user_id": 2, "content_id": 20, "event_type": "complete", "completed": True, "watch_seconds": 3600},
        {"user_id": 3, "content_id": 20, "event_type": "play", "completed": False, "watch_seconds": 600},
    ]
)
FEEDBACK_EVENTS: list[dict[str, int | str | None]] = []

WAREHOUSE_RECOMMENDATION_SQL = """
SELECT
    recommendation.content_id,
    recommendation.score,
    recommendation.algorithm,
    genre.genre_name AS primary_genre
FROM fact_recommendations recommendation
JOIN dim_content content ON content.content_id = recommendation.content_id
LEFT JOIN dim_genre genre ON genre.genre_id = content.primary_genre_id
WHERE recommendation.user_id = %s
ORDER BY recommendation.generated_at DESC, recommendation.rank ASC
LIMIT %s
"""

POPULAR_CONTENT_SQL = """
SELECT
    content_id,
    COALESCE(watch_time_hours, 0.0) AS score,
    primary_genre
FROM vw_content_performance
ORDER BY watch_time_hours DESC NULLS LAST, plays DESC NULLS LAST, content_id
LIMIT %s
"""


def _float(value: object, default: float = 1.0) -> float:
    """Convert database numeric values to JSON-friendly floats."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _database_connection() -> psycopg2.extensions.connection:
    """Open a PostgreSQL connection for short API queries."""
    settings = asdict(DatabaseSettings())
    settings["connect_timeout"] = 2
    return psycopg2.connect(**settings)


def _warehouse_items(user_id: int, limit: int, variant: str) -> list[RecommendationItem]:
    """Load user-specific recommendations from fact_recommendations."""
    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(WAREHOUSE_RECOMMENDATION_SQL, (user_id, limit))
            rows = cursor.fetchall()

    return [
        RecommendationItem(
            content_id=int(content_id),
            score=_float(score),
            algorithm=str(algorithm),
            thumbnail_variant=choose_thumbnail_variant(primary_genre, variant),
        )
        for content_id, score, algorithm, primary_genre in rows
    ]


def _popular_items(limit: int, variant: str) -> list[RecommendationItem]:
    """Load popular content from analytics views as warehouse fallback."""
    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(POPULAR_CONTENT_SQL, (limit,))
            rows = cursor.fetchall()

    return [
        RecommendationItem(
            content_id=int(content_id),
            score=_float(score, 0.0),
            algorithm="warehouse_popularity",
            thumbnail_variant=choose_thumbnail_variant(primary_genre, variant),
        )
        for content_id, score, primary_genre in rows
    ]


def _sample_items(limit: int, variant: str) -> list[RecommendationItem]:
    """Last-resort fallback used when PostgreSQL or analytics views are unavailable."""
    content_ids = recommend_popular(SAMPLE_EVENTS, limit=limit)
    return [
        RecommendationItem(
            content_id=content_id,
            score=1 / rank,
            algorithm="popularity_fallback",
            thumbnail_variant=choose_thumbnail_variant(None, variant),
        )
        for rank, content_id in enumerate(content_ids, start=1)
    ]


def load_recommendations(user_id: int, limit: int, variant: str) -> list[RecommendationItem]:
    """Load recommendations using PostgreSQL first, then analytics and local fallback."""
    try:
        items = _warehouse_items(user_id, limit, variant)
        if items:
            return items
        items = _popular_items(limit, variant)
        if items:
            return items
    except psycopg2.Error:
        pass
    return _sample_items(limit, variant)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/recommendations/{user_id}", response_model=RecommendationResponse)
def get_recommendations(user_id: int, limit: int = 10) -> RecommendationResponse:
    """Return recommendations for a user."""
    variant = assign_variant(user_id, "hybrid-recommender")
    items = load_recommendations(user_id, limit, variant)
    return RecommendationResponse(user_id=user_id, experiment_variant=variant, recommendations=items)


@app.post("/feedback")
def post_feedback(feedback: RecommendationFeedback) -> dict[str, str]:
    """Record recommendation feedback for later ingestion."""
    event_id = str(uuid4())
    FEEDBACK_EVENTS.append({"event_id": event_id, **feedback.model_dump()})
    return {"status": "accepted", "event_id": event_id}
