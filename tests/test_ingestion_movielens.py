import pandas as pd

from src.ingestion.load_movielens import (
    NO_GENRE,
    SERIES_CONTENT_ID_OFFSET,
    build_content_catalog,
    build_content_genre_bridge,
    build_movie_catalog,
    normalize_genres,
    parse_movie_title,
)


def test_parse_movie_title_extracts_clean_title_and_year() -> None:
    title, year = parse_movie_title("Toy Story (1995)")

    assert title == "Toy Story"
    assert year == 1995


def test_parse_movie_title_handles_missing_year() -> None:
    title, year = parse_movie_title("No Year Title")

    assert title == "No Year Title"
    assert year is None


def test_normalize_genres_returns_no_genre_for_empty_values() -> None:
    assert normalize_genres(None) == [NO_GENRE]
    assert normalize_genres("") == [NO_GENRE]


def test_build_movie_catalog_enriches_movielens_sources() -> None:
    movies = pd.DataFrame(
        {
            "movieId": [1, 2],
            "title": ["Toy Story (1995)", "Heat (1995)"],
            "genres": ["Adventure|Animation|Children", "Action|Crime|Thriller"],
        }
    )
    ratings = pd.DataFrame(
        {
            "userId": [10, 11, 12],
            "movieId": [1, 1, 2],
            "rating": [4.0, 5.0, 3.0],
            "timestamp": [1, 2, 3],
        }
    )
    links = pd.DataFrame(
        {
            "movieId": [1, 2],
            "imdbId": [114709, 113277],
            "tmdbId": [862, 949],
        }
    )

    catalog = build_movie_catalog(movies, ratings, links)

    toy_story = catalog.loc[catalog["content_id"] == 1].iloc[0]
    assert toy_story["title"] == "Toy Story"
    assert toy_story["release_year"] == 1995
    assert toy_story["content_type"] == "movie"
    assert toy_story["primary_genre"] == "Adventure"
    assert toy_story["genres_list"] == ["Adventure", "Animation", "Children"]
    assert toy_story["rating_count"] == 2
    assert toy_story["avg_rating"] == 4.5
    assert toy_story["imdb_id"] == "tt0114709"
    assert toy_story["tmdb_id"] == 862
    assert toy_story["duration_minutes"] > 0


def test_build_content_catalog_adds_deterministic_synthetic_series() -> None:
    movies = pd.DataFrame(
        {
            "movieId": [1, 2, 3],
            "title": ["Movie A (2001)", "Movie B (2002)", "Movie C (2003)"],
            "genres": ["Drama", "Comedy", "Sci-Fi"],
        }
    )
    ratings = pd.DataFrame(
        {
            "userId": [10, 11, 12, 13, 14, 15],
            "movieId": [1, 1, 2, 2, 2, 3],
            "rating": [4.0, 4.5, 5.0, 4.0, 4.0, 3.0],
            "timestamp": [1, 2, 3, 4, 5, 6],
        }
    )
    links = pd.DataFrame(
        {
            "movieId": [1, 2, 3],
            "imdbId": [1, 2, 3],
            "tmdbId": [101, 102, 103],
        }
    )

    catalog = build_content_catalog(movies, ratings, links, series_ratio=0.34)
    series = catalog[catalog["content_type"] == "series"]

    assert len(series) == 1
    assert series.iloc[0]["content_id"] == 2 + SERIES_CONTENT_ID_OFFSET
    assert series.iloc[0]["title"] == "Movie B: The Series"
    assert series.iloc[0]["source"] == "synthetic_series_from_movielens"


def test_build_content_genre_bridge_flattens_all_genres() -> None:
    catalog = pd.DataFrame(
        {
            "content_id": [1, 2],
            "genres_list": [["Action", "Thriller"], ["Drama"]],
        }
    )

    bridge = build_content_genre_bridge(catalog)

    assert set(map(tuple, bridge[["content_id", "genre_name"]].to_numpy())) == {
        (1, "Action"),
        (1, "Thriller"),
        (2, "Drama"),
    }
