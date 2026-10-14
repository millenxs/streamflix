"""Data quality checks for StreamFlix raw and warehouse tables."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import psycopg2
from dotenv import load_dotenv

from src.generation.events import DatabaseSettings

load_dotenv()


@dataclass(frozen=True)
class QualityCheck:
    """A SQL check that passes when it returns zero rows."""

    name: str
    description: str
    sql: str
    severity: str = "error"


@dataclass(frozen=True)
class QualityResult:
    """Result of one data quality check."""

    name: str
    description: str
    severity: str
    failed_rows: int

    @property
    def passed(self) -> bool:
        """Whether the check passed."""
        return self.failed_rows == 0


QUALITY_CHECKS: tuple[QualityCheck, ...] = (
    QualityCheck(
        name="raw_events_required_fields",
        description="raw_events must have required IDs, types, timestamps, users, and sessions",
        sql="""
        SELECT COUNT(*)
        FROM raw_events
        WHERE event_id IS NULL
           OR event_type IS NULL
           OR user_id IS NULL
           OR session_id IS NULL
           OR timestamp IS NULL
        """,
    ),
    QualityCheck(
        name="raw_events_known_users",
        description="raw_events.user_id must exist in dim_users",
        sql="""
        SELECT COUNT(*)
        FROM raw_events event
        LEFT JOIN dim_users users ON users.user_id = event.user_id
        WHERE users.user_id IS NULL
        """,
    ),
    QualityCheck(
        name="raw_events_known_content",
        description="content-bearing raw events must reference dim_content",
        sql="""
        SELECT COUNT(*)
        FROM raw_events event
        LEFT JOIN dim_content content ON content.content_id = event.content_id
        WHERE event.content_id IS NOT NULL
          AND content.content_id IS NULL
        """,
    ),
    QualityCheck(
        name="raw_playback_has_raw_event",
        description="raw_playback_events rows must have matching raw_events rows",
        sql="""
        SELECT COUNT(*)
        FROM raw_playback_events playback
        LEFT JOIN raw_events event ON event.event_id = playback.event_id
        WHERE event.event_id IS NULL
        """,
    ),
    QualityCheck(
        name="raw_playback_non_negative_time",
        description="playback timing fields must be non-negative",
        sql="""
        SELECT COUNT(*)
        FROM raw_playback_events
        WHERE COALESCE(position_seconds, 0) < 0
           OR COALESCE(watch_seconds, 0) < 0
           OR COALESCE(duration_seconds, 0) < 0
        """,
    ),
    QualityCheck(
        name="fact_sessions_valid_duration",
        description="fact_sessions duration and watch totals must be non-negative",
        sql="""
        SELECT COUNT(*)
        FROM fact_sessions
        WHERE COALESCE(duration_seconds, 0) < 0
           OR COALESCE(total_watch_seconds, 0) < 0
           OR COALESCE(events_count, 0) < 0
           OR COALESCE(contents_watched, 0) < 0
        """,
    ),
    QualityCheck(
        name="fact_watch_events_valid_dates",
        description="fact_watch_events.date_id must match timestamp::date",
        sql="""
        SELECT COUNT(*)
        FROM fact_watch_events
        WHERE date_id <> timestamp::date
        """,
    ),
)


def run_check(cursor: Any, check: QualityCheck) -> QualityResult:
    """Run one quality check and return its result."""
    cursor.execute(check.sql)
    row = cursor.fetchone()
    failed_rows = int(row[0]) if row else 0
    return QualityResult(
        name=check.name,
        description=check.description,
        severity=check.severity,
        failed_rows=failed_rows,
    )


def run_quality_checks(checks: Sequence[QualityCheck] = QUALITY_CHECKS) -> tuple[QualityResult, ...]:
    """Run all data quality checks against PostgreSQL."""
    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    try:
        with connection.cursor() as cursor:
            return tuple(run_check(cursor, check) for check in checks)
    finally:
        connection.close()


def has_blocking_failures(results: Sequence[QualityResult]) -> bool:
    """Return true when any error-severity check failed."""
    return any(not result.passed and result.severity == "error" for result in results)


def print_results(results: Sequence[QualityResult]) -> None:
    """Print a concise data quality report."""
    print("\nData quality report")
    print("=" * 80)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status:<5} {result.name:<35} {result.failed_rows:>8,} failed rows  {result.description}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run StreamFlix data quality checks.")
    parser.add_argument("--warn-only", action="store_true", help="Always exit with status 0")
    args = parser.parse_args()

    results = run_quality_checks()
    print_results(results)
    if has_blocking_failures(results) and not args.warn_only:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
