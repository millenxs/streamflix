"""TMDB metadata client used to enrich recommendation responses."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

TMDB_API_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"


def tmdb_headers() -> dict[str, str]:
    """Return TMDB auth headers when a v4 read token is configured."""
    token = os.getenv("TOKEN_READ_TMDB")
    return {"Authorization": f"Bearer {token}"} if token else {}


def tmdb_params() -> dict[str, str]:
    """Return TMDB query params when an API key is configured."""
    api_key = os.getenv("TMDB_API_KEY")
    return {"api_key": api_key} if api_key and not tmdb_headers() else {}


def image_url(path: str | None, size: str) -> str | None:
    """Build a full TMDB image URL."""
    if not path:
        return None
    return f"{TMDB_IMAGE_BASE_URL}/{size}{path}"


@lru_cache(maxsize=2048)
def fetch_tmdb_metadata(tmdb_id: int | None, content_type: str | None) -> dict[str, Any]:
    """Fetch compact TMDB metadata for a movie or TV series.

    Missing credentials, missing IDs, network errors, and 404 responses all return
    an empty dictionary so recommendations continue to work offline.
    """
    if not tmdb_id or not (tmdb_headers() or tmdb_params()):
        return {}

    media_type = "tv" if content_type == "series" else "movie"
    try:
        response = requests.get(
            f"{TMDB_API_URL}/{media_type}/{tmdb_id}",
            headers=tmdb_headers(),
            params=tmdb_params(),
            timeout=3,
        )
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        return {}

    return {
        "overview": payload.get("overview") or None,
        "poster_url": image_url(payload.get("poster_path"), "w500"),
        "backdrop_url": image_url(payload.get("backdrop_path"), "w780"),
        "vote_average": payload.get("vote_average"),
        "tmdb_popularity": payload.get("popularity"),
        "tmdb_url": f"https://www.themoviedb.org/{media_type}/{tmdb_id}",
    }
