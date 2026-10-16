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
from src.api.tmdb import fetch_tmdb_metadata
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
    recommendation.recommendation_id::text,
    recommendation.content_id,
    recommendation.score,
    recommendation.algorithm,
    content.title,
    content.content_type,
    content.release_year,
    genre.genre_name AS primary_genre,
    content.tmdb_id,
    content.description
FROM fact_recommendations recommendation
JOIN dim_content content ON content.content_id = recommendation.content_id
LEFT JOIN dim_genre genre ON genre.genre_id = content.primary_genre_id
WHERE recommendation.user_id = %s
ORDER BY recommendation.generated_at DESC, recommendation.rank ASC
LIMIT %s
"""

POPULAR_CONTENT_SQL = """
SELECT
    view.content_id,
    COALESCE(view.watch_time_hours, 0.0) AS score,
    view.primary_genre,
    view.title,
    view.content_type,
    content.release_year,
    content.tmdb_id,
    content.description
FROM vw_content_performance view
JOIN dim_content content ON content.content_id = view.content_id
ORDER BY view.watch_time_hours DESC NULLS LAST, view.plays DESC NULLS LAST, view.content_id
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


def _recommendation_item(
    *,
    content_id: int,
    score: object,
    algorithm: str,
    variant: str,
    title: str | None,
    content_type: str | None,
    release_year: int | None,
    primary_genre: str | None,
    tmdb_id: int | None,
    description: str | None,
    recommendation_id: str | None = None,
) -> RecommendationItem:
    """Build a recommendation item enriched with warehouse and TMDB metadata."""
    tmdb = fetch_tmdb_metadata(tmdb_id, content_type)
    return RecommendationItem(
        recommendation_id=recommendation_id,
        content_id=int(content_id),
        score=_float(score, 0.0),
        algorithm=algorithm,
        title=title,
        content_type=content_type,
        release_year=release_year,
        primary_genre=primary_genre,
        overview=tmdb.get("overview") or description,
        poster_url=tmdb.get("poster_url"),
        backdrop_url=tmdb.get("backdrop_url"),
        vote_average=_float(tmdb.get("vote_average"), 0.0) if tmdb.get("vote_average") is not None else None,
        tmdb_popularity=_float(tmdb.get("tmdb_popularity"), 0.0) if tmdb.get("tmdb_popularity") is not None else None,
        tmdb_url=tmdb.get("tmdb_url"),
        thumbnail_variant=choose_thumbnail_variant(primary_genre, variant),
    )


def _warehouse_items(user_id: int, limit: int, variant: str) -> list[RecommendationItem]:
    """Load user-specific recommendations from fact_recommendations."""
    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(WAREHOUSE_RECOMMENDATION_SQL, (user_id, limit))
            rows = cursor.fetchall()

    return [
        _recommendation_item(
            recommendation_id=str(recommendation_id),
            content_id=int(content_id),
            score=score,
            algorithm=str(algorithm),
            variant=variant,
            title=str(title),
            content_type=str(content_type),
            release_year=int(release_year) if release_year is not None else None,
            primary_genre=str(primary_genre) if primary_genre is not None else None,
            tmdb_id=int(tmdb_id) if tmdb_id is not None else None,
            description=str(description) if description is not None else None,
        )
        for recommendation_id, content_id, score, algorithm, title, content_type, release_year, primary_genre, tmdb_id, description in rows
    ]


def _popular_items(limit: int, variant: str) -> list[RecommendationItem]:
    """Load popular content from analytics views as warehouse fallback."""
    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(POPULAR_CONTENT_SQL, (limit,))
            rows = cursor.fetchall()

    return [
        _recommendation_item(
            content_id=int(content_id),
            score=score,
            algorithm="warehouse_popularity",
            variant=variant,
            title=str(title),
            content_type=str(content_type),
            release_year=int(release_year) if release_year is not None else None,
            primary_genre=str(primary_genre) if primary_genre is not None else None,
            tmdb_id=int(tmdb_id) if tmdb_id is not None else None,
            description=str(description) if description is not None else None,
        )
        for content_id, score, primary_genre, title, content_type, release_year, tmdb_id, description in rows
    ]


def _sample_items(limit: int, variant: str) -> list[RecommendationItem]:
    """Last-resort fallback used when PostgreSQL or analytics views are unavailable."""
    content_ids = recommend_popular(SAMPLE_EVENTS, limit=limit)
    return [
        RecommendationItem(
            content_id=content_id,
            score=1 / rank,
            algorithm="popularity_fallback",
            title=f"Demo title {content_id}",
            content_type="movie",
            primary_genre=None,
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
