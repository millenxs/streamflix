from collections import defaultdict
from datetime import date, datetime

import pandas as pd
import pytest

from src.generation.events import (
    COUNTRY_UTC_OFFSET_HOURS,
    CatalogIndex,
    SimUser,
    generate_history,
    generate_user_history,
)
from src.generation.users import LOCATIONS, generate_users

GENRES = [
    "Action", "Adventure", "Animation", "Children", "Comedy", "Crime", "Documentary", "Drama", "Fantasy",
    "Film-Noir", "Horror", "Musical", "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western",
]
START, END = date(2026, 9, 1), date(2026, 9, 29)


@pytest.fixture(scope="module")
def catalog() -> CatalogIndex:
    rows = []
    for i, genre in enumerate(GENRES):
        for j in range(5):
            rows.append((i * 10 + j + 1, "movie", 100, genre, j * 10))
        for j in range(2):
            rows.append((1_000_000 + i * 10 + j, "series", 40, genre, j * 10))
    columns = ["content_id", "content_type", "duration_minutes", "genres", "rating_count"]
    return CatalogIndex(pd.DataFrame(rows, columns=columns))


@pytest.fixture(scope="module")
def users() -> list[SimUser]:
    dim_users, profiles = generate_users(300, GENRES, reference_date=date(2026, 10, 1), seed=3)
    merged = dim_users.merge(profiles, on="user_id")
    return [SimUser(**{k: v.item() if hasattr(v, "item") else v for k, v in row.items()}) for row in merged.to_dict("records")]


@pytest.fixture(scope="module")
def events(users, catalog) -> list[dict]:
    return list(generate_history(users, catalog, START, END, seed=11))


@pytest.fixture(scope="module")
def sessions(events) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        grouped[event["session_id"]].append(event)
    return grouped


def test_country_offsets_cover_every_generated_country() -> None:
    assert set(COUNTRY_UTC_OFFSET_HOURS) == set(LOCATIONS)


def test_generation_is_deterministic_and_independent_per_user(users, catalog, events) -> None:
    user = users[42]
    alone = list(generate_user_history(user, catalog, START, END, seed=11))

    assert alone == [e for e in events if e["user_id"] == user.user_id]
    assert len({e["event_id"] for e in events}) == len(events)


def test_sessions_follow_the_state_machine(sessions) -> None:
    for session in sessions.values():
        assert session[0]["event_type"] == "user_login"
        assert session[-1]["event_type"] == "session_end"
        timestamps = [datetime.fromisoformat(e["timestamp"]) for e in session]
        assert timestamps == sorted(timestamps)
        assert len({e["device_type"] for e in session}) == 1


def test_sessions_of_a_user_never_overlap(sessions) -> None:
    by_user: dict[int, list[tuple[datetime, datetime]]] = defaultdict(list)
    for session in sessions.values():
        by_user[session[0]["user_id"]].append(
            (datetime.fromisoformat(session[0]["timestamp"]), datetime.fromisoformat(session[-1]["timestamp"]))
        )
    for spans in by_user.values():
        spans.sort()
        assert all(previous_end <= next_start for (_, previous_end), (next_start, _) in zip(spans, spans[1:]))


def test_playback_watch_time_is_consistent_with_duration(events, catalog) -> None:
    watched: dict[tuple[str, int], int] = defaultdict(int)
    for event in events:
        assert (event["watch_seconds"] or 0) >= 0
        if event["event_type"] == "play":
            watched[(event["session_id"], event["content_id"])] = 0
        if event["watch_seconds"]:
            key = (event["session_id"], event["content_id"])
            watched[key] += event["watch_seconds"]
            assert watched[key] <= catalog.duration_seconds[event["content_id"]]
        if event["event_type"] == "complete":
            assert event["position_seconds"] == catalog.duration_seconds[event["content_id"]]


def test_events_respect_signup_and_simulation_window(users, events) -> None:
    signup = {u.user_id: u.signup_date for u in users}
    for event in events:
        day = datetime.fromisoformat(event["timestamp"]).date()
        assert day >= max(START, signup[event["user_id"]])
        assert day <= END  # a session that starts on the last day may end after midnight


def test_recommendation_clicks_refer_to_impressions_of_the_same_session(sessions) -> None:
    for session in sessions.values():
        shown = {e["recommendation_id"]: e["content_id"] for e in session if e["event_type"] == "recommendation_impression"}
        for event in session:
            if event["event_type"] == "recommendation_click":
                assert shown[event["recommendation_id"]] == event["content_id"]


def test_personas_produce_distinguishable_behavior(users, events) -> None:
    """The patterns stage 19 (clustering) must find are present in the raw events."""
    persona = {u.user_id: u.persona for u in users}
    play_hours: dict[str, list[int]] = defaultdict(list)
    finished: dict[str, list[bool]] = defaultdict(list)
    for event in events:
        name = persona[event["user_id"]]
        if event["event_type"] == "play":
            play_hours[name].append(int(event["timestamp"][11:13]))
        if event["event_type"] in ("complete", "stop"):
            finished[name].append(event["event_type"] == "complete")

    def completion(name: str) -> float:
        return sum(finished[name]) / len(finished[name])

    assert sum(14 <= h <= 18 for h in play_hours["family_weekender"]) / len(play_hours["family_weekender"]) > 0.5
    assert sum(h >= 21 or h <= 1 for h in play_hours["night_thriller_binger"]) / len(play_hours["night_thriller_binger"]) > 0.5
    assert completion("cinephile") > completion("casual_mobile_snacker") + 0.2
