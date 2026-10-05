#!/usr/bin/env python3
"""Load and enrich the MovieLens content dataset for StreamFlix.

Stage 4 builds the content catalog used by later user simulation, event generation,
analytics, and recommendation stages. The loader keeps transformation logic pure so
it can be tested without PostgreSQL, then persists the resulting catalog to both
processed files and the dimensional tables.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql

load_dotenv()

MOVIELENS_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "movielens"
DEFAULT_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "content"
SERIES_CONTENT_ID_OFFSET = 1_000_000
NO_GENRE = "(no genres listed)"

GENRE_DURATION_RANGES: dict[str, tuple[int, int]] = {
    "Action": (95, 145),
    "Adventure": (95, 150),
    "Animation": (75, 115),
    "Children": (70, 105),
    "Comedy": (80, 120),
    "Crime": (90, 135),
    "Documentary": (60, 110),
    "Drama": (90, 145),
    "Fantasy": (90, 140),
    "Film-Noir": (80, 115),
    "Horror": (80, 115),
    "Musical": (85, 135),
    "Mystery": (85, 130),
    "Romance": (85, 125),
    "Sci-Fi": (90, 140),
    "Thriller": (85, 130),
    "War": (95, 155),
    "Western": (85, 130),
    NO_GENRE: (80, 120),
}


@dataclass(frozen=True)
class DatabaseSettings:
    """PostgreSQL connection settings loaded from environment variables."""

    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "streamflix")
    user: str = os.getenv("POSTGRES_USER", "streamflix")
    password: str = os.getenv("POSTGRES_PASSWORD", "streamflix123")


def parse_movie_title(raw_title: str) -> tuple[str, int | None]:
    """Return a cleaned title and release year parsed from a MovieLens title."""
    title = str(raw_title).strip()
    match = re.search(r"\((\d{4})\)\s*$", title)
    release_year = int(match.group(1)) if match else None
    clean_title = re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip()
    return clean_title or title, release_year


def normalize_genres(raw_genres: str | float | None) -> list[str]:
    """Normalize a MovieLens pipe-delimited genre string into an ordered list."""
    if raw_genres is None or pd.isna(raw_genres):
        return [NO_GENRE]

    genres = [genre.strip() for genre in str(raw_genres).split("|") if genre.strip()]
    return genres or [NO_GENRE]


def stable_int(value: Any, modulo: int) -> int:
    """Generate a deterministic integer bucket for reproducible synthetic attributes."""
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def estimate_duration_minutes(content_id: int, primary_genre: str, content_type: str) -> int:
    """Estimate realistic runtime using genre-based ranges and stable hashing."""
    if content_type == "series":
        return 25 + stable_int(f"series-{content_id}", 36)

    lower, upper = GENRE_DURATION_RANGES.get(primary_genre, GENRE_DURATION_RANGES[NO_GENRE])
    return lower + stable_int(content_id, upper - lower + 1)


def load_movielens_frames(extract_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load MovieLens CSV files needed for the StreamFlix content catalog."""
    movies = pd.read_csv(extract_dir / "movies.csv")
    ratings = pd.read_csv(extract_dir / "ratings.csv")
    links = pd.read_csv(extract_dir / "links.csv")
    return movies, ratings, links


def build_movie_catalog(
    movies: pd.DataFrame, ratings: pd.DataFrame, links: pd.DataFrame
) -> pd.DataFrame:
    """Build the enriched movie catalog from MovieLens source tables."""
    required_movies = {"movieId", "title", "genres"}
    required_ratings = {"movieId", "rating"}
    required_links = {"movieId", "imdbId", "tmdbId"}

    missing_movies = required_movies - set(movies.columns)
    missing_ratings = required_ratings - set(ratings.columns)
    missing_links = required_links - set(links.columns)
    if missing_movies or missing_ratings or missing_links:
        raise ValueError(
            "Missing MovieLens columns: "
            f"movies={sorted(missing_movies)}, "
            f"ratings={sorted(missing_ratings)}, "
            f"links={sorted(missing_links)}"
        )

    parsed_titles = movies["title"].apply(parse_movie_title)
    catalog = movies.copy()
    catalog["content_id"] = catalog["movieId"].astype(int)
    catalog["title"] = parsed_titles.apply(lambda value: value[0])
    catalog["release_year"] = parsed_titles.apply(lambda value: value[1]).astype("Int64")
    catalog["genres_list"] = catalog["genres"].apply(normalize_genres)
    catalog["primary_genre"] = catalog["genres_list"].apply(lambda genres: genres[0])
    catalog["genre_count"] = catalog["genres_list"].apply(len)
    catalog["content_type"] = "movie"

    rating_stats = (
        ratings.groupby("movieId", as_index=False)
        .agg(rating_count=("rating", "size"), avg_rating=("rating", "mean"))
        .assign(avg_rating=lambda df: df["avg_rating"].round(3))
    )

    catalog = catalog.merge(rating_stats, on="movieId", how="left")
    catalog = catalog.merge(links[list(required_links)], on="movieId", how="left")
    catalog["rating_count"] = catalog["rating_count"].fillna(0).astype(int)
    catalog["avg_rating"] = catalog["avg_rating"].astype(float).round(3)
    catalog["tmdb_id"] = catalog["tmdbId"].astype("Int64")
    catalog["imdb_id"] = catalog["imdbId"].apply(format_imdb_id)
    catalog["duration_minutes"] = catalog.apply(
        lambda row: estimate_duration_minutes(
            int(row["content_id"]), str(row["primary_genre"]), str(row["content_type"])
        ),
        axis=1,
    )
    catalog["source"] = "movielens"
    catalog["description"] = catalog.apply(build_description, axis=1)

    return catalog[
        [
            "content_id",
            "title",
            "content_type",
            "release_year",
            "duration_minutes",
            "primary_genre",
            "genres_list",
            "genre_count",
            "rating_count",
            "avg_rating",
            "tmdb_id",
            "imdb_id",
            "description",
            "source",
        ]
    ].sort_values("content_id", ignore_index=True)


def format_imdb_id(value: Any) -> str | None:
    """Format MovieLens numeric IMDb identifiers as standard tt-prefixed IDs."""
    if pd.isna(value):
        return None
    return f"tt{int(value):07d}"


def build_description(row: pd.Series) -> str:
    """Create a concise portfolio-safe synthetic description for catalog entries."""
    year = int(row["release_year"]) if pd.notna(row["release_year"]) else "unknown year"
    genres = ", ".join(row["genres_list"])
    return f"{row['title']} is a {row['content_type']} from {year} categorized as {genres}."


def build_synthetic_series_catalog(movie_catalog: pd.DataFrame, series_ratio: float = 0.08) -> pd.DataFrame:
    """Create synthetic series records derived from popular MovieLens titles.

    MovieLens is movie-centric. StreamFlix needs both movies and series, so this
    function creates deterministic synthetic series from high-signal catalog rows
    without introducing private or copyrighted platform data.
    """
    if movie_catalog.empty or series_ratio <= 0:
        return movie_catalog.iloc[0:0].copy()

    series_count = max(1, round(len(movie_catalog) * series_ratio))
    candidates = movie_catalog.sort_values(
        ["rating_count", "avg_rating", "content_id"], ascending=[False, False, True]
    ).head(series_count)

    series = candidates.copy().reset_index(drop=True)
    series["content_id"] = series["content_id"].astype(int) + SERIES_CONTENT_ID_OFFSET
    series["title"] = series["title"].apply(lambda title: f"{title}: The Series")
    series["content_type"] = "series"
    series["duration_minutes"] = series.apply(
        lambda row: estimate_duration_minutes(
            int(row["content_id"]), str(row["primary_genre"]), str(row["content_type"])
        ),
        axis=1,
    )
    series["source"] = "synthetic_series_from_movielens"
    series["description"] = series.apply(build_description, axis=1)
    return series


def build_content_catalog(
    movies: pd.DataFrame,
    ratings: pd.DataFrame,
    links: pd.DataFrame,
    series_ratio: float = 0.08,
) -> pd.DataFrame:
    """Build the full StreamFlix content catalog with movies and synthetic series."""
    movie_catalog = build_movie_catalog(movies, ratings, links)
    series_catalog = build_synthetic_series_catalog(movie_catalog, series_ratio=series_ratio)
    return pd.concat([movie_catalog, series_catalog], ignore_index=True).sort_values(
        "content_id", ignore_index=True
    )


def build_content_genre_bridge(content_catalog: pd.DataFrame) -> pd.DataFrame:
    """Flatten content-to-genre relationships for database loading and analytics."""
    rows: list[dict[str, int | str]] = []
    for content in content_catalog[["content_id", "genres_list"]].itertuples(index=False):
        for genre in content.genres_list:
            rows.append({"content_id": int(content.content_id), "genre_name": str(genre)})
    return pd.DataFrame(rows).drop_duplicates(ignore_index=True)


class MovieLensLoader:
    """Download, transform, persist, and load MovieLens content into StreamFlix."""

    def __init__(
        self,
        db_settings: DatabaseSettings | None = None,
        raw_dir: Path = DEFAULT_RAW_DIR,
        processed_dir: Path = DEFAULT_PROCESSED_DIR,
        movielens_url: str = MOVIELENS_URL,
        series_ratio: float = 0.08,
    ) -> None:
        self.db_settings = db_settings or DatabaseSettings()
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.movielens_url = movielens_url
        self.series_ratio = series_ratio
        self.connection: psycopg2.extensions.connection | None = None

    def connect(self) -> None:
        """Connect to PostgreSQL database."""
        try:
            self.connection = psycopg2.connect(
                host=self.db_settings.host,
                port=self.db_settings.port,
                database=self.db_settings.database,
                user=self.db_settings.user,
                password=self.db_settings.password,
            )
            self.connection.autocommit = False
            print(
                "[OK] Connected to PostgreSQL at "
                f"{self.db_settings.host}:{self.db_settings.port}/{self.db_settings.database}"
            )
        except psycopg2.Error as error:
            print(f"[ERROR] Failed to connect to PostgreSQL: {error}")
            sys.exit(1)

    def disconnect(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            print("[OK] Disconnected from PostgreSQL")

    def download_dataset(self) -> Path:
        """Download the MovieLens dataset if it is not already available locally."""
        print(f"Downloading MovieLens dataset from {self.movielens_url}...")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.raw_dir / "ml-latest-small.zip"

        if zip_path.exists():
            print(f"[OK] Dataset already exists at {zip_path}")
            return zip_path

        try:
            urllib.request.urlretrieve(self.movielens_url, zip_path)
            print(f"[OK] Downloaded to {zip_path}")
        except Exception as error:
            print(f"[ERROR] Failed to download dataset: {error}")
            sys.exit(1)
        return zip_path

    def extract_dataset(self, zip_path: Path) -> Path:
        """Extract MovieLens zip contents if needed."""
        extract_dir = self.raw_dir / "ml-latest-small"
        if extract_dir.exists():
            print(f"[OK] Dataset already extracted at {extract_dir}")
            return extract_dir

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(self.raw_dir)
            print(f"[OK] Extracted to {extract_dir}")
        except Exception as error:
            print(f"[ERROR] Failed to extract dataset: {error}")
            sys.exit(1)
        return extract_dir

    def build_catalog_from_files(self, extract_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load source CSV files and build catalog plus content-genre bridge."""
        movies, ratings, links = load_movielens_frames(extract_dir)
        content_catalog = build_content_catalog(
            movies, ratings, links, series_ratio=self.series_ratio
        )
        content_genres = build_content_genre_bridge(content_catalog)
        print(
            "[OK] Built content catalog: "
            f"{len(content_catalog)} titles, {len(content_genres)} content-genre rows"
        )
        return content_catalog, content_genres

    def save_processed_outputs(
        self, content_catalog: pd.DataFrame, content_genres: pd.DataFrame
    ) -> None:
        """Persist processed content outputs for notebooks, ETL, and reproducibility."""
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        catalog_for_files = content_catalog.copy()
        catalog_for_files["genres"] = catalog_for_files["genres_list"].apply(lambda x: "|".join(x))
        catalog_for_files = catalog_for_files.drop(columns=["genres_list"])

        catalog_csv = self.processed_dir / "content_catalog.csv"
        catalog_parquet = self.processed_dir / "content_catalog.parquet"
        genres_csv = self.processed_dir / "content_genres.csv"
        genres_parquet = self.processed_dir / "content_genres.parquet"

        catalog_for_files.to_csv(catalog_csv, index=False)
        catalog_for_files.to_parquet(catalog_parquet, index=False)
        content_genres.to_csv(genres_csv, index=False)
        content_genres.to_parquet(genres_parquet, index=False)

        print(f"[OK] Saved processed catalog to {self.processed_dir}")

    def load_content_to_db(self, content_catalog: pd.DataFrame) -> None:
        """Load enriched content data into dim_content idempotently."""
        if self.connection is None:
            raise RuntimeError("Database connection is not open")

        with self.connection.cursor() as cursor:
            for row in content_catalog.itertuples(index=False):
                cursor.execute(
                    sql.SQL(
                        """
                        INSERT INTO dim_content (
                            content_id, title, content_type, release_year,
                            duration_minutes, tmdb_id, imdb_id, description, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                        ON CONFLICT (content_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            content_type = EXCLUDED.content_type,
                            release_year = EXCLUDED.release_year,
                            duration_minutes = EXCLUDED.duration_minutes,
                            tmdb_id = EXCLUDED.tmdb_id,
                            imdb_id = EXCLUDED.imdb_id,
                            description = EXCLUDED.description,
                            is_active = TRUE,
                            updated_at = NOW()
                        """
                    ),
                    [
                        int(row.content_id),
                        row.title,
                        row.content_type,
                        int(row.release_year) if pd.notna(row.release_year) else None,
                        int(row.duration_minutes) if pd.notna(row.duration_minutes) else None,
                        int(row.tmdb_id) if pd.notna(row.tmdb_id) else None,
                        row.imdb_id,
                        row.description,
                    ],
                )
        self.connection.commit()
        print(f"[OK] Loaded {len(content_catalog)} content items into dim_content")

    def load_genres_to_db(self, content_genres: pd.DataFrame, content_catalog: pd.DataFrame) -> None:
        """Load genre dimension rows and content-genre mappings idempotently."""
        if self.connection is None:
            raise RuntimeError("Database connection is not open")

        genre_names = sorted(content_genres["genre_name"].dropna().unique())
        with self.connection.cursor() as cursor:
            for genre_name in genre_names:
                cursor.execute(
                    "INSERT INTO dim_genre (genre_name) VALUES (%s) ON CONFLICT DO NOTHING",
                    [genre_name],
                )
            cursor.execute("SELECT genre_id, genre_name FROM dim_genre")
            genre_mapping = {name: genre_id for genre_id, name in cursor.fetchall()}

            cursor.execute("DELETE FROM dim_content_genre")
            for row in content_genres.itertuples(index=False):
                cursor.execute(
                    """
                    INSERT INTO dim_content_genre (content_id, genre_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    [int(row.content_id), genre_mapping[row.genre_name]],
                )

            for row in content_catalog[["content_id", "primary_genre"]].itertuples(index=False):
                cursor.execute(
                    """
                    UPDATE dim_content
                    SET primary_genre_id = %s
                    WHERE content_id = %s
                    """,
                    [genre_mapping[row.primary_genre], int(row.content_id)],
                )

        self.connection.commit()
        print(f"[OK] Loaded {len(content_genres)} content-genre mappings")

    def load(self) -> None:
        """Run the full MovieLens content load."""
        print("=" * 60)
        print("StreamFlix MovieLens Content Dataset Loader")
        print("=" * 60)

        zip_path = self.download_dataset()
        extract_dir = self.extract_dataset(zip_path)
        content_catalog, content_genres = self.build_catalog_from_files(extract_dir)
        self.save_processed_outputs(content_catalog, content_genres)

        self.connect()
        try:
            self.load_content_to_db(content_catalog)
            self.load_genres_to_db(content_genres, content_catalog)
            self.verify_loading()
        finally:
            self.disconnect()

        print("\n" + "=" * 60)
        print("MovieLens content dataset loaded successfully")
        print("=" * 60)

    def verify_loading(self) -> None:
        """Verify that dimensional content data was loaded correctly."""
        if self.connection is None:
            raise RuntimeError("Database connection is not open")

        print("\nVerifying loading...")
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM dim_content")
            content_count = cursor.fetchone()[0]
            print(f"  [OK] Content items: {content_count}")

            cursor.execute("SELECT COUNT(*) FROM dim_content WHERE content_type = 'series'")
            series_count = cursor.fetchone()[0]
            print(f"  [OK] Synthetic series: {series_count}")

            cursor.execute("SELECT COUNT(*) FROM dim_content_genre")
            genre_mapping_count = cursor.fetchone()[0]
            print(f"  [OK] Genre mappings: {genre_mapping_count}")

            cursor.execute("SELECT COUNT(*) FROM dim_content WHERE primary_genre_id IS NOT NULL")
            primary_genre_count = cursor.fetchone()[0]
            print(f"  [OK] Content with primary genre: {primary_genre_count}")


def main() -> None:
    """CLI entry point."""
    loader = MovieLensLoader()
    try:
        loader.load()
    except Exception as error:
        print(f"\n[ERROR] MovieLens loading failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
