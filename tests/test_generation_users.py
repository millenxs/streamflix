from datetime import date

import numpy as np
import pytest

from src.generation.users import DEVICES, LOCATIONS, PERSONAS, SIGNUP_HISTORY_DAYS, generate_users

GENRES = [
    "Action", "Adventure", "Animation", "Children", "Comedy", "Crime", "Documentary", "Drama", "Fantasy",
    "Film-Noir", "Horror", "Musical", "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western",
]
REFERENCE_DATE = date(2026, 10, 1)


@pytest.fixture(scope="module")
def generated():
    return generate_users(6000, GENRES, REFERENCE_DATE, seed=7)


def test_generation_is_deterministic_for_same_seed() -> None:
    first_users, first_profiles = generate_users(500, GENRES, REFERENCE_DATE, seed=1)
    second_users, second_profiles = generate_users(500, GENRES, REFERENCE_DATE, seed=1)

    assert first_users.equals(second_users)
    assert first_profiles.equals(second_profiles)


def test_users_have_unique_sequential_ids_and_valid_attributes(generated) -> None:
    users, profiles = generated

    assert users["user_id"].tolist() == list(range(1, 6001))
    assert profiles["user_id"].tolist() == users["user_id"].tolist()
    assert set(users["preferred_device"]) <= set(DEVICES)
    assert all(region in LOCATIONS[country][1] for country, region in zip(users["country"], users["region"]))
    assert users["signup_date"].min() > date.fromordinal(REFERENCE_DATE.toordinal() - SIGNUP_HISTORY_DAYS)
    assert users["signup_date"].max() <= REFERENCE_DATE


def test_profile_traits_are_within_bounds(generated) -> None:
    _, profiles = generated

    for column in ["weekend_bias", "series_preference", "completion_propensity", "discovery_rate", "churn_risk"]:
        assert profiles[column].between(0, 1).all(), column
    assert (profiles["sessions_per_week"] > 0).all()
    assert profiles["peak_hour"].between(0, 23).all()
    assert all(abs(sum(a.values()) - 1) < 0.01 and set(a) == set(GENRES) for a in profiles["genre_affinity"])


def test_persona_shares_match_configuration(generated) -> None:
    _, profiles = generated
    observed = profiles["persona"].value_counts(normalize=True)

    for persona in PERSONAS:
        assert observed[persona.name] == pytest.approx(persona.share, abs=0.03)


def test_personas_have_distinguishable_behavior(generated) -> None:
    """Patterns must be real so clustering in later stages has something to find."""
    _, profiles = generated
    thriller = profiles["genre_affinity"].map(lambda a: a["Thriller"] + a["Horror"])
    by_persona = profiles.assign(thriller=thriller).groupby("persona")

    assert by_persona["thriller"].mean()["night_thriller_binger"] > 3 * by_persona["thriller"].mean()["family_weekender"]
    assert by_persona["churn_risk"].mean()["casual_mobile_snacker"] > by_persona["churn_risk"].mean()["cinephile"]
    assert np.isclose(by_persona["peak_hour"].median()["family_weekender"], 16, atol=1)


def test_rejects_catalog_without_persona_genres() -> None:
    with pytest.raises(ValueError, match="Thriller"):
        generate_users(10, [g for g in GENRES if g != "Thriller"], REFERENCE_DATE)
