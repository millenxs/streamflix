#!/usr/bin/env python3
"""
StreamFlix Database Initialization Script

This script initializes the StreamFlix database by:
1. Connecting to PostgreSQL
2. Executing SQL schema scripts in order
3. Populating initial data (date dimension, genres, devices)
"""

import os
import sys
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseInitializer:
    """Initialize StreamFlix database schema and initial data"""

    def __init__(self):
        """Initialize database connection parameters"""
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = os.getenv("POSTGRES_DB", "streamflix")
        self.user = os.getenv("POSTGRES_USER", "streamflix")
        self.password = os.getenv("POSTGRES_PASSWORD", "streamflix123")
        self.connection: Optional[psycopg2.extensions.connection] = None

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

    def execute_sql_file(self, file_path: Path) -> None:
        """Execute SQL script from file"""
        print(f"  Executing {file_path.name}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                sql_script = f.read()

            with self.connection.cursor() as cursor:
                cursor.execute(sql_script)
            self.connection.commit()
            print(f"  [OK] {file_path.name} executed successfully")
        except psycopg2.Error as e:
            self.connection.rollback()
            print(f"  [ERROR] Failed to execute {file_path.name}: {e}")
            raise

    def populate_initial_data(self) -> None:
        """Populate initial data for dimensions"""
        print("Populating initial data...")

        # Populate genres
        self._populate_genres()

        # Populate devices
        self._populate_devices()

        # Populate date dimension (if not already done by SQL script)
        self._populate_date_dimension()

        print("[OK] Initial data populated")

    def _populate_genres(self) -> None:
        """Populate genre dimension with standard genres"""
        genres = [
            "Action",
            "Adventure",
            "Animation",
            "Children",
            "Comedy",
            "Crime",
            "Documentary",
            "Drama",
            "Fantasy",
            "Film-Noir",
            "Horror",
            "Musical",
            "Mystery",
            "Romance",
            "Sci-Fi",
            "Thriller",
            "War",
            "Western",
            "(no genres listed)",
        ]

        with self.connection.cursor() as cursor:
            for genre in genres:
                cursor.execute(
                    sql.SQL("INSERT INTO dim_genre (genre_name) VALUES (%s) ON CONFLICT DO NOTHING"),
                    [genre],
                )
        self.connection.commit()
        print("  [OK] Genres populated")

    def _populate_devices(self) -> None:
        """Populate device dimension with standard device types"""
        devices = ["smart_tv", "mobile", "web", "tablet", "console", "other"]

        with self.connection.cursor() as cursor:
            for device in devices:
                cursor.execute(
                    sql.SQL("INSERT INTO dim_device (device_type) VALUES (%s) ON CONFLICT DO NOTHING"),
                    [device],
                )
        self.connection.commit()
        print("  [OK] Devices populated")

    def _populate_date_dimension(self) -> None:
        """Populate date dimension if empty"""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM dim_date")
            count = cursor.fetchone()[0]

            if count == 0:
                print("  Populating date dimension...")
                schema_dir = Path(__file__).parent.parent / "src" / "sql" / "schema"
                date_file = schema_dir / "05_populate_dim_date.sql"
                if date_file.exists():
                    self.execute_sql_file(date_file)
                else:
                    print("  [WARN] Date dimension SQL file not found, skipping")
            else:
                print(f"  [OK] Date dimension already has {count} dates")

    def initialize(self) -> None:
        """Initialize database schema and data"""
        print("=" * 60)
        print("StreamFlix Database Initialization")
        print("=" * 60)

        # Connect to database
        self.connect()

        # Get schema directory
        schema_dir = Path(__file__).parent.parent / "src" / "sql" / "schema"

        # Execute SQL scripts in order
        sql_files = [
            "01_raw_layer.sql",
            "02_dimensions.sql",
            "03_facts.sql",
            "04_indexes.sql",
            "05_populate_dim_date.sql",
        ]

        print("\nExecuting SQL schema scripts...")
        for sql_file in sql_files:
            file_path = schema_dir / sql_file
            if file_path.exists():
                self.execute_sql_file(file_path)
            else:
                print(f"  [WARN] {sql_file} not found, skipping")

        # Populate initial data
        self.populate_initial_data()

        # Verify initialization
        self._verify_initialization()

        # Disconnect
        self.disconnect()

        print("\n" + "=" * 60)
        print("Database initialization completed successfully!")
        print("=" * 60)

    def _verify_initialization(self) -> None:
        """Verify that tables were created correctly"""
        print("\nVerifying initialization...")

        tables_to_check = [
            "raw_events",
            "raw_playback_events",
            "dim_users",
            "dim_content",
            "dim_genre",
            "dim_device",
            "dim_location",
            "dim_date",
            "fact_watch_events",
            "fact_sessions",
            "fact_user_interactions",
            "fact_recommendations",
            "fact_recommendation_feedback",
        ]

        with self.connection.cursor() as cursor:
            for table in tables_to_check:
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = %s"),
                    [table],
                )
                exists = cursor.fetchone()[0] > 0
                status = "[OK]" if exists else "[ERROR]"
                print(f"  {status} Table {table}")

        # Check initial data counts
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM dim_genre")
            genre_count = cursor.fetchone()[0]
            print(f"  [OK] Genres: {genre_count}")

            cursor.execute("SELECT COUNT(*) FROM dim_device")
            device_count = cursor.fetchone()[0]
            print(f"  [OK] Devices: {device_count}")

            cursor.execute("SELECT COUNT(*) FROM dim_date")
            date_count = cursor.fetchone()[0]
            print(f"  [OK] Dates: {date_count}")


def main():
    """Main entry point"""
    initializer = DatabaseInitializer()
    try:
        initializer.initialize()
    except Exception as e:
        print(f"\n[ERROR] Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
