"""API models for recommendation endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    """One recommended content item."""

    content_id: int
    score: float = 1.0
    algorithm: str = "hybrid"
    thumbnail_variant: str = "default"
    recommendation_id: str | None = None
    title: str | None = None
    content_type: str | None = None
    release_year: int | None = None
    primary_genre: str | None = None
    overview: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    vote_average: float | None = None
    tmdb_popularity: float | None = None
    tmdb_url: str | None = None


class RecommendationResponse(BaseModel):
    """Recommendation endpoint response."""

    user_id: int
    experiment_variant: str
    recommendations: list[RecommendationItem]


class RecommendationFeedback(BaseModel):
    """Feedback payload emitted by clients."""

    user_id: int
    content_id: int
    recommendation_id: str | None = None
    feedback_type: str = Field(pattern="^(impression|click|play|complete)$")
