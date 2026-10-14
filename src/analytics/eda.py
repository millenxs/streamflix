"""Exploratory analysis export for StreamFlix dashboards and notebooks."""

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
DEFAULT_EDA_DIR = PROJECT_ROOT / "data" / "processed" / "eda"
EDA_QUERIES = {
    "daily_engagement": "SELECT * FROM vw_daily_engagement ORDER BY date_id",
    "content_performance": "SELECT * FROM vw_content_performance ORDER BY watch_time_hours DESC NULLS LAST",
    "recommendation_performance": "SELECT * FROM vw_recommendation_performance ORDER BY date_id, algorithm",
    "executive_kpis": "SELECT * FROM vw_executive_kpis ORDER BY date_id",
}


def export_eda_tables(output_dir: Path = DEFAULT_EDA_DIR) -> list[Path]:
    """Export analytics views to CSV files for EDA and Power BI checks."""
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    paths: list[Path] = []
    try:
        for name, query in EDA_QUERIES.items():
            frame = pd.read_sql_query(query, connection)
            path = output_dir / f"{name}.csv"
            frame.to_csv(path, index=False)
            paths.append(path)
    finally:
        connection.close()
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Export StreamFlix EDA datasets from analytics views.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_EDA_DIR)
    args = parser.parse_args()

    paths = export_eda_tables(args.output_dir)
    for path in paths:
        print(f"[OK] Wrote {path}")


if __name__ == "__main__":
    main()
