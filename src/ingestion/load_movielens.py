#!/usr/bin/env python3
"""
StreamFlix MovieLens Dataset Loader

This script downloads and loads the MovieLens dataset into the database.
It processes movies and creates content entries in dim_content and dim_content_genre.
"""

import os
import sys
import ssl
import zipfile
from pathlib import Path
from typing import Optional
import urllib.request

import pandas as pd
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class MovieLensLoader:
    """Load MovieLens dataset into StreamFlix database"""

    def __init__(self):
        """Initialize database connection parameters"""
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = os.getenv("POSTGRES_DB", "streamflix")
        self.user = os.getenv("POSTGRES_USER", "streamflix")
        self.password = os.getenv("POSTGRES_PASSWORD", "streamflix123")
        self.connection: Optional[psycopg2.extensions.connection] = None

        # MovieLens dataset URL (small dataset for testing)
        self.movielens_url = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
        self.data_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "movielens"

    def connect(self) -> None:
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            self.connection.autocommit = False
            print(f"[OK] Connected to PostgreSQL at {self.host}:{self.port}/{self.database}")
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to connect to PostgreSQL: {e}")
            sys.exit(1)

    def disconnect(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("[OK] Disconnected from PostgreSQL")

    def download_dataset(self) -> Path:
        """Download MovieLens dataset"""
        print(f"Downloading MovieLens dataset from {self.movielens_url}...")

        # Create data directory
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Download zip file
        zip_path = self.data_dir / "ml-latest-small.zip"
        if not zip_path.exists():
            try:
                # Create SSL context that doesn't verify certificates (for educational purposes)
                ssl_context = ssl._create_unverified_context()
                with urllib.request.urlopen(self.movielens_url, context=ssl_context) as response:
                    with open(zip_path, 'wb') as out_file:
                        out_file.write(response.read())
                print(f"[OK] Downloaded to {zip_path}")
            except Exception as e:
                print(f"[ERROR] Failed to download dataset: {e}")
                sys.exit(1)
        else:
            print(f"[OK] Dataset already exists at {zip_path}")

        return zip_path

    def extract_dataset(self, zip_path: Path) -> Path:
        """Extract MovieLens dataset"""
        print("Extracting dataset...")

        extract_dir = self.data_dir / "ml-latest-small"
        if not extract_dir.exists():
            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(self.data_dir)
                print(f"[OK] Extracted to {extract_dir}")
            except Exception as e:
                print(f"[ERROR] Failed to extract dataset: {e}")
                sys.exit(1)
        else:
            print(f"[OK] Dataset already extracted at {extract_dir}")

        return extract_dir

    def load_movies(self, extract_dir: Path) -> pd.DataFrame:
        """Load movies.csv from MovieLens dataset"""
        movies_path = extract_dir / "movies.csv"
        print(f"Loading movies from {movies_path}...")

        try:
            movies_df = pd.read_csv(movies_path)
            print(f"[OK] Loaded {len(movies_df)} movies")
            return movies_df
        except Exception as e:
            print(f"[ERROR] Failed to load movies: {e}")
            sys.exit(1)

    def process_movies(self, movies_df: pd.DataFrame) -> pd.DataFrame:
        """Process movies data for database insertion"""
        print("Processing movies data...")

        # Parse genres (format: "Action|Adventure|Comedy")
        movies_df["genres_list"] = movies_df["genres"].str.split("|")

        # Extract year from title (format: "Movie Title (1999)")
        movies_df["release_year"] = movies_df["title"].str.extract(r"\((\d{4})\)").astype(float)

        # Clean title (remove year)
        movies_df["title_clean"] = movies_df["title"].str.replace(r"\s*\(\d{4}\)", "", regex=True)

        # Assign content type (all movies in MovieLens are movies)
        movies_df["content_type"] = "movie"

        # Assign content_id (use movieId from MovieLens)
        movies_df["content_id"] = movies_df["movieId"]

        print(f"[OK] Processed {len(movies_df)} movies")
        return movies_df

    def load_content_to_db(self, movies_df: pd.DataFrame) -> None:
        """Load content data into dim_content"""
        print("Loading content into dim_content...")

        with self.connection.cursor() as cursor:
            for _, row in movies_df.iterrows():
                cursor.execute(
                    sql.SQL("""
                        INSERT INTO dim_content (
                            content_id, title, content_type, release_year,
                            primary_genre_id, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (content_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            release_year = EXCLUDED.release_year,
                            updated_at = NOW()
                    """),
                    [
                        row["content_id"],
                        row["title_clean"],
                        row["content_type"],
                        int(row["release_year"]) if pd.notna(row["release_year"]) else None,
                        None,  # primary_genre_id will be set after genre mapping
                        True,
                    ],
                )

        self.connection.commit()
        print(f"[OK] Loaded {len(movies_df)} content items")

    def load_genres_to_db(self, movies_df: pd.DataFrame) -> None:
        """Load genre mappings into dim_content_genre"""
        print("Loading genre mappings into dim_content_genre...")

        # Get genre_id mapping from dim_genre
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT genre_id, genre_name FROM dim_genre")
            genre_mapping = {row[1]: row[0] for row in cursor.fetchall()}

        # Load content-genre mappings
        with self.connection.cursor() as cursor:
            count = 0
            for _, row in movies_df.iterrows():
                for genre in row["genres_list"]:
                    if genre in genre_mapping:
                        genre_id = genre_mapping[genre]
                        cursor.execute(
                            sql.SQL("""
                                INSERT INTO dim_content_genre (content_id, genre_id)
                                VALUES (%s, %s)
                                ON CONFLICT DO NOTHING
                            """),
                            [row["content_id"], genre_id],
                        )
                        count += 1

                        # Set primary_genre_id to first genre
                        cursor.execute(
                            sql.SQL("""
                                UPDATE dim_content
                                SET primary_genre_id = %s
                                WHERE content_id = %s AND primary_genre_id IS NULL
                            """),
                            [genre_id, row["content_id"]],
                        )

        self.connection.commit()
        print(f"[OK] Loaded {count} genre mappings")

    def load(self) -> None:
        """Load MovieLens dataset into database"""
        print("=" * 60)
        print("StreamFlix MovieLens Dataset Loader")
        print("=" * 60)

        # Connect to database
        self.connect()

        # Download dataset
        zip_path = self.download_dataset()

        # Extract dataset
        extract_dir = self.extract_dataset(zip_path)

        # Load movies
        movies_df = self.load_movies(extract_dir)

        # Process movies
        movies_df = self.process_movies(movies_df)

        # Load content to database
        self.load_content_to_db(movies_df)

        # Load genres to database
        self.load_genres_to_db(movies_df)

        # Verify loading
        self._verify_loading()

        # Disconnect
        self.disconnect()

        print("\n" + "=" * 60)
        print("MovieLens dataset loaded successfully!")
        print("=" * 60)

    def _verify_loading(self) -> None:
        """Verify that data was loaded correctly"""
        print("\nVerifying loading...")

        with self.connection.cursor() as cursor:
            # Check content count
            cursor.execute("SELECT COUNT(*) FROM dim_content")
            content_count = cursor.fetchone()[0]
            print(f"  [OK] Content items: {content_count}")

            # Check genre mapping count
            cursor.execute("SELECT COUNT(*) FROM dim_content_genre")
            genre_mapping_count = cursor.fetchone()[0]
            print(f"  [OK] Genre mappings: {genre_mapping_count}")

            # Check content with primary genre
            cursor.execute("SELECT COUNT(*) FROM dim_content WHERE primary_genre_id IS NOT NULL")
            primary_genre_count = cursor.fetchone()[0]
            print(f"  [OK] Content with primary genre: {primary_genre_count}")


def main():
    """Main entry point"""
    loader = MovieLensLoader()
    try:
        loader.load()
    except Exception as e:
        print(f"\n[ERROR] MovieLens loading failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
