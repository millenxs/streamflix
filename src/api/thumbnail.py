"""Thumbnail personalization rules."""

from __future__ import annotations

GENRE_THUMBNAIL_PREFIX = {
    "Action": "action",
    "Comedy": "comedy",
    "Drama": "drama",
    "Horror": "horror",
    "Sci-Fi": "scifi",
    "Thriller": "thriller",
}


def choose_thumbnail_variant(primary_genre: str | None, experiment_variant: str = "control") -> str:
    """Choose a deterministic thumbnail variant from genre and experiment arm."""
    prefix = GENRE_THUMBNAIL_PREFIX.get(primary_genre or "", "default")
    return f"{prefix}_{experiment_variant}"
