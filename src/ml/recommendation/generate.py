"""Generate personalized recommendations and persist them to fact_recommendations."""

from __future__ import annotations

import argparse
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

from src.generation.events import DatabaseSettings

load_dotenv()

DEFAULT_MODEL_VERSION = "hybrid-v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "recommendations"

USERS_SQL = "SELECT user_id FROM dim_users WHERE is_active = TRUE ORDER BY user_id"
CONTENT_SQL = """
SELECT
    content.content_id,
    COALESCE(view.primary_genre, genre.genre_name, 'unknown') AS primary_genre,
    COALESCE(view.watch_time_hours, 0.0) AS watch_time_hours,
    COALESCE(view.completion_rate, 0.0) AS completion_rate
FROM dim_content content
LEFT JOIN vw_content_performance view ON view.content_id = content.content_id
LEFT JOIN dim_genre genre ON genre.genre_id = content.primary_genre_id
WHERE content.is_active = TRUE
"""
USER_GENRE_SQL = """
SELECT
    watch.user_id,
    COALESCE(genre.genre_name, 'unknown') AS primary_genre,
    COALESCE(SUM(watch.watch_seconds), 0) AS watch_seconds,
    COUNT(*) FILTER (WHERE watch.completed) AS completions
FROM fact_watch_events watch
JOIN dim_content content ON content.content_id = watch.content_id
LEFT JOIN dim_genre genre ON genre.genre_id = content.primary_genre_id
GROUP BY watch.user_id, COALESCE(genre.genre_name, 'unknown')
"""
SEEN_SQL = "SELECT DISTINCT user_id, content_id FROM fact_watch_events"
INSERT_RECOMMENDATIONS_SQL = """
INSERT INTO fact_recommendations (
    recommendation_id, user_id, content_id, model_version, algorithm, score, rank, generated_at
)
VALUES %s
ON CONFLICT (recommendation_id) DO UPDATE SET
    score = EXCLUDED.score,
    rank = EXCLUDED.rank,
    generated_at = EXCLUDED.generated_at
"""


def _minmax(series: pd.Series) -> pd.Series:
    """Return a min-max normalized numeric series."""
    values = series.fillna(0).astype(float)
    span = values.max() - values.min()
    if span == 0:
        return pd.Series(0.0, index=series.index)
    return (values - values.min()) / span


def load_recommendation_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load users, content, user genre preferences, and seen content from PostgreSQL."""
    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    try:
        users = pd.read_sql_query(USERS_SQL, connection)
        content = pd.read_sql_query(CONTENT_SQL, connection)
        user_genres = pd.read_sql_query(USER_GENRE_SQL, connection)
        seen = pd.read_sql_query(SEEN_SQL, connection)
    finally:
        connection.close()
    return users, content, user_genres, seen


def build_user_genre_affinity(user_genres: pd.DataFrame) -> dict[int, dict[str, float]]:
    """Convert user genre aggregates into per-user affinity scores."""
    if user_genres.empty:
        return {}
    frame = user_genres.copy()
    frame["preference_score"] = frame["watch_seconds"].astype(float) + frame["completions"].astype(float) * 1800
    totals = frame.groupby("user_id")["preference_score"].transform("sum")
    frame["affinity"] = frame["preference_score"] / totals.where(totals > 0, 1)
    return {
        int(user_id): dict(zip(group["primary_genre"], group["affinity"], strict=False))
        for user_id, group in frame.groupby("user_id")
    }


def prepare_content_scores(content: pd.DataFrame) -> pd.DataFrame:
    """Add popularity score columns used by the hybrid recommender."""
    frame = content.copy()
    frame["popularity_score"] = (
        _minmax(frame["watch_time_hours"]) * 0.7 + _minmax(frame["completion_rate"]) * 0.3
    )
    return frame.sort_values(["popularity_score", "content_id"], ascending=[False, True], ignore_index=True)


def recommendation_uuid(model_version: str, user_id: int, content_id: int) -> str:
    """Return a deterministic recommendation UUID for idempotent upserts."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"streamflix:{model_version}:{user_id}:{content_id}"))


def build_recommendations(
    users: pd.DataFrame,
    content: pd.DataFrame,
    user_genres: pd.DataFrame,
    seen: pd.DataFrame,
    *,
    limit: int = 10,
    model_version: str = DEFAULT_MODEL_VERSION,
    generated_at: datetime | None = None,
) -> pd.DataFrame:
    """Build personalized hybrid recommendations for every active user."""
    if users.empty or content.empty:
        return pd.DataFrame(
            columns=["recommendation_id", "user_id", "content_id", "model_version", "algorithm", "score", "rank", "generated_at"]
        )

    generated_at = generated_at or datetime.now(timezone.utc)
    content_scores = prepare_content_scores(content)
    affinities = build_user_genre_affinity(user_genres)
    seen_by_user = seen.groupby("user_id")["content_id"].apply(lambda values: set(values.astype(int))).to_dict() if not seen.empty else {}
    rows: list[dict[str, Any]] = []

    for user_id in users["user_id"].astype(int):
        user_seen = seen_by_user.get(user_id, set())
        affinity = affinities.get(user_id, {})
        candidates = content_scores.loc[~content_scores["content_id"].astype(int).isin(user_seen)].copy()
        if candidates.empty:
            candidates = content_scores.copy()
        candidates["genre_affinity"] = candidates["primary_genre"].map(affinity).fillna(0.0)
        candidates["score"] = candidates["popularity_score"] * 0.45 + candidates["genre_affinity"] * 0.55
        if candidates["score"].max() == 0:
            candidates["score"] = candidates["popularity_score"]
        top = candidates.sort_values(["score", "content_id"], ascending=[False, True]).head(limit)
        for rank, row in enumerate(top.itertuples(index=False), start=1):
            content_id = int(row.content_id)
            rows.append(
                {
                    "recommendation_id": recommendation_uuid(model_version, user_id, content_id),
                    "user_id": user_id,
                    "content_id": content_id,
                    "model_version": model_version,
                    "algorithm": "hybrid",
                    "score": round(float(row.score), 6),
                    "rank": rank,
                    "generated_at": generated_at,
                }
            )
    return pd.DataFrame(rows)


def save_recommendation_artifact(recommendations: pd.DataFrame, output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    """Persist generated recommendations as a parquet artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "personalized_recommendations.parquet"
    recommendations.to_parquet(path, index=False)
    return path


def upsert_recommendations(recommendations: pd.DataFrame) -> int:
    """Upsert generated recommendations into fact_recommendations."""
    if recommendations.empty:
        return 0
    rows = [
        (
            row.recommendation_id,
            int(row.user_id),
            int(row.content_id),
            row.model_version,
            row.algorithm,
            float(row.score),
            int(row.rank),
            row.generated_at,
        )
        for row in recommendations.itertuples(index=False)
    ]
    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    try:
        with connection.cursor() as cursor:
            execute_values(cursor, INSERT_RECOMMENDATIONS_SQL, rows, page_size=1000)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate personalized StreamFlix recommendations.")
    parser.add_argument("--limit", type=int, default=10, help="Recommendations per user")
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.limit <= 0:
        raise ValueError("--limit must be positive")

    users, content, user_genres, seen = load_recommendation_inputs()
    recommendations = build_recommendations(
        users,
        content,
        user_genres,
        seen,
        limit=args.limit,
        model_version=args.model_version,
    )
    written = upsert_recommendations(recommendations)
    artifact = save_recommendation_artifact(recommendations, args.output_dir)
    print(f"[OK] Upserted {written:,} personalized recommendations into fact_recommendations")
    print(f"[OK] Wrote recommendation artifact to {artifact}")


if __name__ == "__main__":
    main()
