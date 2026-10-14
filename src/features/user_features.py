"""Feature engineering for StreamFlix ML and recommendation workflows."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from src.generation.events import DatabaseSettings

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEATURE_DIR = PROJECT_ROOT / "data" / "processed" / "features"
USER_FEATURE_COLUMNS = [
    "user_id",
    "sessions_count",
    "events_count",
    "contents_watched",
    "total_watch_seconds",
    "avg_session_seconds",
    "completion_rate",
    "like_rate",
    "recommendation_ctr",
    "rec_watch_share",
    "days_since_last_activity",
    "is_churned_30d",
]

USER_FEATURE_SQL = """
WITH user_base AS (
    SELECT user_id FROM dim_users
), watch AS (
    SELECT
        user_id,
        COUNT(*) AS events_count,
        COUNT(DISTINCT content_id) AS contents_watched,
        COALESCE(SUM(watch_seconds), 0) AS total_watch_seconds,
        COUNT(*) FILTER (WHERE completed) AS completed_events,
        COUNT(*) FILTER (WHERE event_type IN ('complete', 'stop')) AS terminal_events,
        COUNT(*) FILTER (WHERE is_from_recommendation) AS recommendation_watch_events,
        MAX(date_id) AS last_activity_date
    FROM fact_watch_events
    GROUP BY user_id
), sessions AS (
    SELECT
        user_id,
        COUNT(*) AS sessions_count,
        COALESCE(AVG(duration_seconds), 0) AS avg_session_seconds
    FROM fact_sessions
    GROUP BY user_id
), interactions AS (
    SELECT
        user_id,
        COUNT(*) FILTER (WHERE interaction_type = 'like') AS likes,
        COUNT(*) AS interactions_count
    FROM fact_user_interactions
    GROUP BY user_id
), recs AS (
    SELECT
        user_id,
        COUNT(*) FILTER (WHERE feedback_type = 'click') AS rec_clicks,
        COUNT(*) FILTER (WHERE feedback_type = 'impression') AS rec_impressions
    FROM fact_recommendation_feedback
    GROUP BY user_id
)
SELECT
    users.user_id,
    COALESCE(sessions.sessions_count, 0)::integer AS sessions_count,
    COALESCE(watch.events_count, 0)::integer AS events_count,
    COALESCE(watch.contents_watched, 0)::integer AS contents_watched,
    COALESCE(watch.total_watch_seconds, 0)::integer AS total_watch_seconds,
    COALESCE(sessions.avg_session_seconds, 0)::float AS avg_session_seconds,
    COALESCE(watch.completed_events::float / NULLIF(watch.terminal_events, 0), 0.0) AS completion_rate,
    COALESCE(interactions.likes::float / NULLIF(interactions.interactions_count, 0), 0.0) AS like_rate,
    COALESCE(recs.rec_clicks::float / NULLIF(recs.rec_impressions, 0), 0.0) AS recommendation_ctr,
    COALESCE(watch.recommendation_watch_events::float / NULLIF(watch.events_count, 0), 0.0) AS rec_watch_share,
    COALESCE((CURRENT_DATE - watch.last_activity_date), 9999)::integer AS days_since_last_activity,
    (COALESCE((CURRENT_DATE - watch.last_activity_date), 9999) >= 30)::integer AS is_churned_30d
FROM user_base users
LEFT JOIN watch ON watch.user_id = users.user_id
LEFT JOIN sessions ON sessions.user_id = users.user_id
LEFT JOIN interactions ON interactions.user_id = users.user_id
LEFT JOIN recs ON recs.user_id = users.user_id
ORDER BY users.user_id
"""


def normalize_feature_frame(features: pd.DataFrame) -> pd.DataFrame:
    """Return feature data with expected columns and numeric nulls filled."""
    frame = features.copy()
    for column in USER_FEATURE_COLUMNS:
        if column not in frame.columns:
            frame[column] = 0
    frame = frame[USER_FEATURE_COLUMNS]
    numeric_columns = [column for column in USER_FEATURE_COLUMNS if column != "user_id"]
    frame[numeric_columns] = frame[numeric_columns].fillna(0)
    return frame


def load_user_features() -> pd.DataFrame:
    """Load user feature rows from PostgreSQL warehouse facts."""
    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    try:
        return pd.read_sql_query(USER_FEATURE_SQL, connection)
    finally:
        connection.close()


def save_user_features(features: pd.DataFrame, output_dir: Path = DEFAULT_FEATURE_DIR) -> Path:
    """Persist user features as a parquet artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "user_features.parquet"
    normalize_feature_frame(features).to_parquet(path, index=False)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build StreamFlix user ML features.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_FEATURE_DIR)
    args = parser.parse_args()

    path = save_user_features(load_user_features(), args.output_dir)
    print(f"[OK] Wrote user features to {path}")


if __name__ == "__main__":
    main()
