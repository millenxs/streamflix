"""Transform raw Kafka events into StreamFlix warehouse fact tables.

This module intentionally performs set-based ELT inside PostgreSQL. Raw Kafka
messages remain immutable in ``raw_events`` and ``raw_playback_events``; this
pipeline upserts derived dimensions and inserts facts idempotently.
"""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import psycopg2
from dotenv import load_dotenv

from src.generation.events import DatabaseSettings

load_dotenv()

DEFAULT_MODEL_VERSION = os.getenv("MODEL_VERSION", "1.0.0")

UPSERT_DEVICE_DIMENSION_SQL = """
INSERT INTO dim_device (device_type)
SELECT DISTINCT COALESCE(device_type, 'unknown') AS device_type
FROM raw_events
ON CONFLICT (device_type) DO NOTHING
"""

UPSERT_LOCATION_DIMENSION_SQL = """
INSERT INTO dim_location (country, region)
SELECT DISTINCT country, region
FROM raw_events
WHERE country IS NOT NULL AND region IS NOT NULL
ON CONFLICT (country, region) DO NOTHING
"""

INSERT_FACT_RECOMMENDATIONS_SQL = """
INSERT INTO fact_recommendations (
    recommendation_id, user_id, content_id, model_version, algorithm, score, rank, generated_at
)
SELECT
    (event.metadata->>'recommendation_id')::uuid AS recommendation_id,
    event.user_id,
    event.content_id,
    %(model_version)s AS model_version,
    COALESCE(event.metadata->>'algorithm', 'popularity') AS algorithm,
    (1.0 / GREATEST(COALESCE((event.metadata->>'rank')::integer, 1), 1))::decimal(10, 6) AS score,
    COALESCE((event.metadata->>'rank')::integer, 1) AS rank,
    event.timestamp AS generated_at
FROM raw_events event
JOIN dim_users users ON users.user_id = event.user_id
JOIN dim_content content ON content.content_id = event.content_id
WHERE event.event_type = 'recommendation_impression'
  AND event.content_id IS NOT NULL
  AND event.metadata ? 'algorithm'
  AND event.metadata ? 'recommendation_id'
ON CONFLICT (recommendation_id) DO NOTHING
"""

INSERT_FACT_WATCH_EVENTS_SQL = """
INSERT INTO fact_watch_events (
    event_id, user_id, content_id, date_id, device_id, location_id,
    event_type, timestamp, watch_seconds, position_seconds, completed,
    is_from_recommendation, recommendation_id
)
SELECT
    event.event_id,
    event.user_id,
    event.content_id,
    event.timestamp::date AS date_id,
    device.device_id,
    location.location_id,
    event.event_type,
    event.timestamp,
    playback.watch_seconds,
    playback.position_seconds,
    event.event_type = 'complete' AS completed,
    event.metadata ? 'recommendation_id' AS is_from_recommendation,
    (event.metadata->>'recommendation_id')::uuid AS recommendation_id
FROM raw_events event
JOIN raw_playback_events playback ON playback.event_id = event.event_id
JOIN dim_users users ON users.user_id = event.user_id
JOIN dim_content content ON content.content_id = event.content_id
JOIN dim_date date_dim ON date_dim.date_id = event.timestamp::date
JOIN dim_device device ON device.device_type = COALESCE(event.device_type, 'unknown')
LEFT JOIN dim_location location ON location.country = event.country AND location.region = event.region
WHERE event.event_type IN ('play', 'pause', 'resume', 'seek', 'stop', 'complete')
  AND event.content_id IS NOT NULL
ON CONFLICT (event_id) DO NOTHING
"""

INSERT_FACT_SESSIONS_SQL = """
WITH session_rollup AS (
    SELECT
        event.session_id,
        MIN(event.user_id) AS user_id,
        MIN(event.timestamp) AS start_time,
        MAX(event.timestamp) AS end_time,
        COUNT(*)::integer AS events_count,
        COUNT(DISTINCT playback.content_id)::integer AS contents_watched,
        COALESCE(SUM(playback.watch_seconds), 0)::integer AS total_watch_seconds,
        (ARRAY_AGG(COALESCE(event.device_type, 'unknown') ORDER BY event.timestamp))[1] AS device_type,
        (ARRAY_AGG(event.country ORDER BY event.timestamp))[1] AS country,
        (ARRAY_AGG(event.region ORDER BY event.timestamp))[1] AS region
    FROM raw_events event
    LEFT JOIN raw_playback_events playback ON playback.event_id = event.event_id
    GROUP BY event.session_id
)
INSERT INTO fact_sessions (
    session_id, user_id, start_time, end_time, duration_seconds,
    device_id, location_id, events_count, contents_watched, total_watch_seconds
)
SELECT
    rollup.session_id,
    rollup.user_id,
    rollup.start_time,
    rollup.end_time,
    EXTRACT(EPOCH FROM (rollup.end_time - rollup.start_time))::integer AS duration_seconds,
    device.device_id,
    location.location_id,
    rollup.events_count,
    rollup.contents_watched,
    rollup.total_watch_seconds
FROM session_rollup rollup
JOIN dim_users users ON users.user_id = rollup.user_id
JOIN dim_device device ON device.device_type = rollup.device_type
LEFT JOIN dim_location location ON location.country = rollup.country AND location.region = rollup.region
ON CONFLICT (session_id) DO UPDATE SET
    end_time = EXCLUDED.end_time,
    duration_seconds = EXCLUDED.duration_seconds,
    events_count = EXCLUDED.events_count,
    contents_watched = EXCLUDED.contents_watched,
    total_watch_seconds = EXCLUDED.total_watch_seconds
"""

INSERT_FACT_USER_INTERACTIONS_SQL = """
INSERT INTO fact_user_interactions (
    interaction_id, user_id, content_id, date_id, interaction_type, timestamp
)
SELECT
    event.event_id AS interaction_id,
    event.user_id,
    event.content_id,
    event.timestamp::date AS date_id,
    event.event_type AS interaction_type,
    event.timestamp
FROM raw_events event
JOIN dim_users users ON users.user_id = event.user_id
JOIN dim_content content ON content.content_id = event.content_id
JOIN dim_date date_dim ON date_dim.date_id = event.timestamp::date
WHERE event.event_type IN ('like', 'dislike', 'add_to_list', 'share')
  AND event.content_id IS NOT NULL
ON CONFLICT (interaction_id) DO NOTHING
"""

INSERT_FACT_RECOMMENDATION_FEEDBACK_SQL = """
INSERT INTO fact_recommendation_feedback (
    feedback_id, recommendation_id, user_id, content_id, feedback_type, timestamp
)
SELECT
    event.event_id AS feedback_id,
    (event.metadata->>'recommendation_id')::uuid AS recommendation_id,
    event.user_id,
    event.content_id,
    CASE event.event_type
        WHEN 'recommendation_impression' THEN 'impression'
        WHEN 'recommendation_click' THEN 'click'
        ELSE event.event_type
    END AS feedback_type,
    event.timestamp
FROM raw_events event
JOIN fact_recommendations recommendation ON recommendation.recommendation_id = (event.metadata->>'recommendation_id')::uuid
JOIN dim_users users ON users.user_id = event.user_id
JOIN dim_content content ON content.content_id = event.content_id
WHERE event.event_type IN ('recommendation_impression', 'recommendation_click', 'play', 'complete')
  AND event.metadata ? 'recommendation_id'
  AND event.content_id IS NOT NULL
ON CONFLICT (feedback_id) DO NOTHING
"""

PIPELINE_STEPS: tuple[tuple[str, str], ...] = (
    ("dim_device", UPSERT_DEVICE_DIMENSION_SQL),
    ("dim_location", UPSERT_LOCATION_DIMENSION_SQL),
    ("fact_recommendations", INSERT_FACT_RECOMMENDATIONS_SQL),
    ("fact_watch_events", INSERT_FACT_WATCH_EVENTS_SQL),
    ("fact_sessions", INSERT_FACT_SESSIONS_SQL),
    ("fact_user_interactions", INSERT_FACT_USER_INTERACTIONS_SQL),
    ("fact_recommendation_feedback", INSERT_FACT_RECOMMENDATION_FEEDBACK_SQL),
)


@dataclass(frozen=True)
class StepResult:
    """Result of one ELT step."""

    name: str
    rowcount: int
    elapsed_seconds: float


@dataclass(frozen=True)
class PipelineResult:
    """Complete ETL run result."""

    steps: tuple[StepResult, ...]

    @property
    def total_rowcount(self) -> int:
        """Total row count reported by PostgreSQL across all steps."""
        return sum(step.rowcount for step in self.steps if step.rowcount > 0)


def run_step(cursor: Any, name: str, statement: str, model_version: str) -> StepResult:
    """Execute one ELT statement and capture PostgreSQL's affected-row count."""
    started = time.perf_counter()
    cursor.execute(statement, {"model_version": model_version})
    elapsed = time.perf_counter() - started
    return StepResult(name=name, rowcount=max(cursor.rowcount, 0), elapsed_seconds=elapsed)


def run_pipeline(model_version: str = DEFAULT_MODEL_VERSION, steps: Sequence[tuple[str, str]] = PIPELINE_STEPS) -> PipelineResult:
    """Run the raw-to-warehouse ELT pipeline inside one PostgreSQL transaction."""
    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    results: list[StepResult] = []
    try:
        with connection.cursor() as cursor:
            for name, statement in steps:
                results.append(run_step(cursor, name, statement, model_version))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return PipelineResult(tuple(results))


def print_result(result: PipelineResult) -> None:
    """Print a concise ETL summary."""
    print("\n[OK] Raw-to-warehouse ETL completed")
    print(f"[OK] Total affected rows: {result.total_rowcount:,}\n")
    for step in result.steps:
        print(f"  {step.name:<34}{step.rowcount:>10,} rows  {step.elapsed_seconds:>7.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Transform raw StreamFlix events into warehouse facts.")
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    args = parser.parse_args()

    print_result(run_pipeline(model_version=args.model_version))


if __name__ == "__main__":
    main()
