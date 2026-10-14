"""Apply dashboard-ready StreamFlix analytics SQL views."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

from src.generation.events import DatabaseSettings

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYTICS_SQL = PROJECT_ROOT / "src" / "sql" / "analytics" / "01_kpi_views.sql"


def apply_analytics_views(sql_path: Path = DEFAULT_ANALYTICS_SQL) -> None:
    """Execute the analytics view SQL file in PostgreSQL."""
    statement = sql_path.read_text(encoding="utf-8")
    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or replace StreamFlix analytics views.")
    parser.add_argument("--sql-path", type=Path, default=DEFAULT_ANALYTICS_SQL)
    args = parser.parse_args()

    apply_analytics_views(args.sql_path)
    print(f"[OK] Applied analytics views from {args.sql_path}")


if __name__ == "__main__":
    main()
