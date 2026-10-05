"""Generate synthetic StreamFlix users with latent behavioral personas.

Stage 6 creates the user base that the event generator (stage 7) will simulate.
Each user is assigned a hidden persona that shapes genre taste, viewing hours,
device usage and churn risk. Users of the same persona share tendencies but are
not identical: every trait is sampled around the persona mean, so clustering has
real but noisy patterns to discover.

The persona is stored only in ``sim_user_profiles`` (simulation ground truth).
``dim_users`` receives only what a real platform would know about a subscriber.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

from src.ingestion.load_movielens import NO_GENRE, DatabaseSettings

load_dotenv()

DEVICES = ("smart_tv", "mobile", "web", "tablet", "console")

# Country (ISO 3166-1 alpha-3) -> (share of users, regions)
LOCATIONS: dict[str, tuple[float, tuple[str, ...]]] = {
    "BRA": (0.35, ("Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte")),
    "USA": (0.25, ("Northeast", "Midwest", "South", "West")),
    "MEX": (0.12, ("Norte", "Centro", "Sur")),
    "ARG": (0.10, ("Buenos Aires", "Centro", "Cuyo", "Patagonia")),
    "GBR": (0.10, ("England", "Scotland", "Wales", "Northern Ireland")),
    "ESP": (0.08, ("Madrid", "Cataluna", "Andalucia", "Valencia")),
}

SIGNUP_HISTORY_DAYS = 365
# How much a user's traits may deviate from the persona mean (higher = closer to the mean)
TRAIT_CONCENTRATION = 20.0
FAVORITE_GENRE_ALPHA = 4.0
BASE_GENRE_ALPHA = 0.3


@dataclass(frozen=True)
class Persona:
    """Mean behavior of a group of users. Individual users vary around these values."""

    name: str
    share: float
    favorite_genres: tuple[str, ...]
    device_weights: dict[str, float]
    peak_hour: int
    weekend_bias: float
    sessions_per_week: float
    series_preference: float
    completion_propensity: float
    discovery_rate: float
    churn_risk: float


PERSONAS: tuple[Persona, ...] = (
    Persona(
        name="night_thriller_binger",
        share=0.18,
        favorite_genres=("Thriller", "Horror", "Crime", "Mystery"),
        device_weights={"smart_tv": 0.5, "web": 0.3, "mobile": 0.2},
        peak_hour=23,
        weekend_bias=0.35,
        sessions_per_week=6.0,
        series_preference=0.70,
        completion_propensity=0.75,
        discovery_rate=0.15,
        churn_risk=0.10,
    ),
    Persona(
        name="family_weekender",
        share=0.17,
        favorite_genres=("Children", "Animation", "Comedy", "Fantasy"),
        device_weights={"smart_tv": 0.7, "tablet": 0.3},
        peak_hour=16,
        weekend_bias=0.70,
        sessions_per_week=3.0,
        series_preference=0.40,
        completion_propensity=0.80,
        discovery_rate=0.10,
        churn_risk=0.08,
    ),
    Persona(
        name="casual_mobile_snacker",
        share=0.22,
        favorite_genres=("Comedy", "Romance", "Action"),
        device_weights={"mobile": 0.8, "tablet": 0.2},
        peak_hour=12,
        weekend_bias=0.25,
        sessions_per_week=5.0,
        series_preference=0.55,
        completion_propensity=0.35,
        discovery_rate=0.25,
        churn_risk=0.30,
    ),
    Persona(
        name="cinephile",
        share=0.13,
        favorite_genres=("Drama", "Documentary", "Film-Noir", "War"),
        device_weights={"web": 0.5, "smart_tv": 0.5},
        peak_hour=21,
        weekend_bias=0.40,
        sessions_per_week=3.0,
        series_preference=0.15,
        completion_propensity=0.85,
        discovery_rate=0.40,
        churn_risk=0.06,
    ),
    Persona(
        name="action_scifi_fan",
        share=0.18,
        favorite_genres=("Action", "Sci-Fi", "Adventure", "Fantasy"),
        device_weights={"console": 0.5, "smart_tv": 0.4, "web": 0.1},
        peak_hour=20,
        weekend_bias=0.45,
        sessions_per_week=4.0,
        series_preference=0.35,
        completion_propensity=0.60,
        discovery_rate=0.20,
        churn_risk=0.12,
    ),
    Persona(
        name="genre_explorer",
        share=0.12,
        favorite_genres=(),  # no favorites: spreads attention across every genre
        device_weights={"web": 0.4, "tablet": 0.3, "mobile": 0.3},
        peak_hour=19,
        weekend_bias=0.30,
        sessions_per_week=2.0,
        series_preference=0.45,
        completion_propensity=0.50,
        discovery_rate=0.60,
        churn_risk=0.25,
    ),
)


def _beta_around(rng: np.random.Generator, mean: float, size: int) -> np.ndarray:
    """Sample proportions in (0, 1) centered on ``mean``."""
    return rng.beta(mean * TRAIT_CONCENTRATION, (1 - mean) * TRAIT_CONCENTRATION, size)


def _sample_locations(rng: np.random.Generator, size: int) -> tuple[list[str], list[str]]:
    countries = list(LOCATIONS)
    shares = np.array([LOCATIONS[c][0] for c in countries])
    chosen = rng.choice(countries, size=size, p=shares / shares.sum())
    # ponytail: regions are uniform within a country; weight them if regional analysis needs it
    regions = [LOCATIONS[c][1][rng.integers(len(LOCATIONS[c][1]))] for c in chosen]
    return list(chosen), regions


def _persona_users(
    persona: Persona, user_ids: np.ndarray, genres: list[str], reference_date: date, rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame]:
    size = len(user_ids)

    devices = list(persona.device_weights)
    device_p = np.array(list(persona.device_weights.values()))
    countries, regions = _sample_locations(rng, size)
    # ponytail: uniform signups over the last year; add a growth curve if cohort analysis needs it
    days_ago = rng.integers(0, SIGNUP_HISTORY_DAYS, size)

    users = pd.DataFrame(
        {
            "user_id": user_ids,
            "signup_date": [reference_date - timedelta(days=int(d)) for d in days_ago],
            "country": countries,
            "region": regions,
            "preferred_device": rng.choice(devices, size=size, p=device_p / device_p.sum()),
        }
    )

    # Dirichlet: each user gets a genre distribution that sums to 1, concentrated on the
    # persona's favorites but never zero elsewhere, so tastes overlap like real people's.
    alpha = np.array([FAVORITE_GENRE_ALPHA if g in persona.favorite_genres else BASE_GENRE_ALPHA for g in genres])
    affinity = rng.dirichlet(alpha, size)

    profiles = pd.DataFrame(
        {
            "user_id": user_ids,
            "persona": persona.name,
            "genre_affinity": [dict(zip(genres, np.round(row, 4).tolist())) for row in affinity],
            # Gamma keeps the mean but allows heavy and light users within the same persona
            "sessions_per_week": np.maximum(rng.gamma(4.0, persona.sessions_per_week / 4.0, size), 0.2).round(2),
            "peak_hour": (persona.peak_hour + np.rint(rng.normal(0, 1.5, size))).astype(int) % 24,
            "weekend_bias": _beta_around(rng, persona.weekend_bias, size).round(3),
            "series_preference": _beta_around(rng, persona.series_preference, size).round(3),
            "completion_propensity": _beta_around(rng, persona.completion_propensity, size).round(3),
            "discovery_rate": _beta_around(rng, persona.discovery_rate, size).round(3),
            "churn_risk": _beta_around(rng, persona.churn_risk, size).round(3),
        }
    )
    return users, profiles


def generate_users(
    num_users: int, genres: list[str], reference_date: date, seed: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate ``dim_users`` rows and their hidden ``sim_user_profiles``.

    The output is deterministic for the same ``num_users``, ``genres``, ``reference_date``
    and ``seed``, which makes reruns idempotent.
    """
    if num_users <= 0:
        raise ValueError("num_users must be positive")
    missing = {g for p in PERSONAS for g in p.favorite_genres} - set(genres)
    if missing:
        raise ValueError(f"Persona genres missing from catalog: {sorted(missing)}")

    rng = np.random.default_rng(seed)
    shares = np.array([p.share for p in PERSONAS])
    assignments = rng.choice(len(PERSONAS), size=num_users, p=shares / shares.sum())
    all_ids = np.arange(1, num_users + 1)

    parts = [
        _persona_users(persona, all_ids[assignments == i], genres, reference_date, rng)
        for i, persona in enumerate(PERSONAS)
        if (assignments == i).any()
    ]
    users = pd.concat([u for u, _ in parts]).sort_values("user_id", ignore_index=True)
    profiles = pd.concat([p for _, p in parts]).sort_values("user_id", ignore_index=True)
    return users, profiles


def _rows(frame: pd.DataFrame) -> list[tuple]:
    """Convert a DataFrame to tuples of native Python values that psycopg2 can adapt."""
    return [tuple(record.values()) for record in frame.to_dict("records")]


def load_users(connection: psycopg2.extensions.connection, users: pd.DataFrame, profiles: pd.DataFrame) -> None:
    """Upsert users, their locations and profiles in a single transaction."""
    locations = users[["country", "region"]].drop_duplicates()
    profiles = profiles.assign(genre_affinity=profiles["genre_affinity"].map(json.dumps))

    with connection.cursor() as cursor:
        execute_values(
            cursor,
            "INSERT INTO dim_location (country, region) VALUES %s ON CONFLICT DO NOTHING",
            _rows(locations),
        )
        execute_values(
            cursor,
            """
            INSERT INTO dim_users (user_id, signup_date, country, region, preferred_device)
            VALUES %s
            ON CONFLICT (user_id) DO UPDATE SET
                signup_date = EXCLUDED.signup_date,
                country = EXCLUDED.country,
                region = EXCLUDED.region,
                preferred_device = EXCLUDED.preferred_device,
                updated_at = NOW()
            """,
            _rows(users),
            page_size=1000,
        )
        execute_values(
            cursor,
            """
            INSERT INTO sim_user_profiles (
                user_id, persona, genre_affinity, sessions_per_week, peak_hour, weekend_bias,
                series_preference, completion_propensity, discovery_rate, churn_risk
            )
            VALUES %s
            ON CONFLICT (user_id) DO UPDATE SET
                persona = EXCLUDED.persona,
                genre_affinity = EXCLUDED.genre_affinity,
                sessions_per_week = EXCLUDED.sessions_per_week,
                peak_hour = EXCLUDED.peak_hour,
                weekend_bias = EXCLUDED.weekend_bias,
                series_preference = EXCLUDED.series_preference,
                completion_propensity = EXCLUDED.completion_propensity,
                discovery_rate = EXCLUDED.discovery_rate,
                churn_risk = EXCLUDED.churn_risk
            """,
            _rows(profiles),
            page_size=1000,
        )
    connection.commit()


def main() -> None:
    num_users = int(os.getenv("NUM_USERS", "10000"))
    seed = int(os.getenv("SIMULATION_SEED", "42"))
    reference_date = date.fromisoformat(os.getenv("SIMULATION_REFERENCE_DATE", date.today().isoformat()))

    print("=" * 60)
    print(f"StreamFlix User Generator: {num_users} users, seed={seed}, reference_date={reference_date}")
    print("=" * 60)

    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT genre_name FROM dim_genre WHERE genre_name <> %s ORDER BY genre_name", [NO_GENRE])
            genres = [row[0] for row in cursor.fetchall()]

        users, profiles = generate_users(num_users, genres, reference_date, seed)
        load_users(connection, users, profiles)
        print(f"[OK] Loaded {len(users)} users into dim_users and sim_user_profiles")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.persona, COUNT(*), ROUND(AVG(p.sessions_per_week), 2), ROUND(AVG(p.churn_risk), 3),
                       MODE() WITHIN GROUP (ORDER BY u.preferred_device)
                FROM sim_user_profiles p JOIN dim_users u USING (user_id)
                GROUP BY p.persona ORDER BY COUNT(*) DESC
                """
            )
            print(f"\n{'persona':<24}{'users':>7}{'sess/wk':>9}{'churn':>7}  top_device")
            for persona, count, sessions, churn, device in cursor.fetchall():
                print(f"{persona:<24}{count:>7}{sessions:>9}{churn:>7}  {device}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
