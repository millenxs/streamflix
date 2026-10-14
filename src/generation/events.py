"""Generate synthetic StreamFlix behavioral events from user personas.

Stage 7 turns the hidden profiles created in stage 6 into a stream of events.
Nothing here is an independent random number: each session follows a state
machine and every decision (when to log in, what to watch, whether to finish,
whether to churn) is driven by the user's profile:

    user_login -> home_view -> content_impression* -> recommendation_impression*
    -> [search | recommendation_click | content_click] -> play
    -> (seek | pause -> resume)* -> complete | stop -> [like | dislike]
    -> ... more titles ... -> session_end

Events are yielded one at a time, so millions of them never sit in memory.
``watch_seconds`` is the time watched in the segment that ends at that event, so
summing it over a session gives its total watch time without double counting.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import time
import uuid
from bisect import bisect
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from itertools import accumulate
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from src.ingestion.load_movielens import DEFAULT_PROCESSED_DIR, DatabaseSettings
from src.generation.users import DEVICES

load_dotenv()

# ponytail: one fixed UTC offset per country, no DST or multiple US time zones
COUNTRY_UTC_OFFSET_HOURS: dict[str, int] = {"BRA": -3, "USA": -5, "MEX": -6, "ARG": -3, "GBR": 0, "ESP": 1}

PREFERRED_DEVICE_SHARE = 0.8
BROWSE_ONLY_PROBABILITY = 0.12
RECOMMENDATION_ROW_PROBABILITY = 0.7
RECOMMENDATION_ROW_SIZE = 5
RECOMMENDATION_CLICK_PROBABILITY = 0.3
OFF_TASTE_COMPLETION_FACTOR = 0.6
SEEK_PROBABILITY = 0.15
SECONDS_PER_PAUSE = 2400  # one pause every ~40 minutes watched
CHURN_DECAY_DAYS = 21
MIN_DAYS_BEFORE_CHURN = 14


@dataclass(frozen=True)
class SimUser:
    """A synthetic user joined with its hidden simulation profile."""

    user_id: int
    signup_date: date
    country: str
    region: str
    preferred_device: str
    persona: str
    genre_affinity: dict[str, float]
    sessions_per_week: float
    peak_hour: int
    weekend_bias: float
    series_preference: float
    completion_propensity: float
    discovery_rate: float
    churn_risk: float

    @property
    def top_genres(self) -> set[str]:
        return set(sorted(self.genre_affinity, key=self.genre_affinity.get, reverse=True)[:3])


class CatalogIndex:
    """Content lookups for fast weighted sampling by genre and type."""

    def __init__(self, catalog: pd.DataFrame, recommendations_per_genre: int = 10) -> None:
        self.duration_seconds: dict[int, int] = {}
        self.genres: dict[int, frozenset[str]] = {}
        self.series_ids: set[int] = set()
        buckets: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)

        for row in catalog[["content_id", "content_type", "duration_minutes", "genres", "rating_count"]].itertuples(
            index=False
        ):
            content_id = int(row.content_id)
            genres = frozenset(str(row.genres).split("|"))
            self.duration_seconds[content_id] = int(row.duration_minutes) * 60
            self.genres[content_id] = genres
            if row.content_type == "series":
                self.series_ids.add(content_id)
            for genre in genres:
                buckets[(genre, row.content_type)].append((content_id, int(row.rating_count)))

        # Popularity-weighted sampling: +1 so titles without ratings can still be found
        self._ids = {key: [cid for cid, _ in items] for key, items in buckets.items()}
        self._cum_weights = {key: list(accumulate(count + 1 for _, count in items)) for key, items in buckets.items()}
        # Placeholder "recommendations": most popular titles per genre (stage 21 replaces this)
        self.popular_by_genre: dict[str, list[int]] = defaultdict(list)
        for (genre, _), items in buckets.items():
            self.popular_by_genre[genre].extend(items)
        self.popular_by_genre = {
            genre: [cid for cid, _ in sorted(items, key=lambda i: (-i[1], i[0]))[:recommendations_per_genre]]
            for genre, items in self.popular_by_genre.items()
        }

    def sample(self, rng: random.Random, genre: str, content_type: str) -> int:
        key = (genre, content_type) if (genre, content_type) in self._ids else (genre, "movie")
        weights = self._cum_weights[key]
        return self._ids[key][bisect(weights, rng.random() * weights[-1])]


def _poisson(rng: random.Random, lam: float) -> int:
    """Knuth's algorithm; fine for the small rates used here (< 10)."""
    threshold, count, product = math.exp(-lam), 0, rng.random()
    while product > threshold:
        count += 1
        product *= rng.random()
    return count


class SessionSimulator:
    """Simulate one session of one user as an ordered list of events."""

    def __init__(self, user: SimUser, catalog: CatalogIndex, rng: random.Random) -> None:
        self.user = user
        self.catalog = catalog
        self.rng = rng
        self.genres = list(user.genre_affinity)
        self.genre_weights = list(accumulate(user.genre_affinity.values()))
        self.top_genres = user.top_genres
        top_two = sorted(user.genre_affinity, key=user.genre_affinity.get, reverse=True)[:2]
        self.recommendation_candidates = list(
            dict.fromkeys(c for g in top_two for c in catalog.popular_by_genre.get(g, []))
        )

    def _uuid(self) -> str:
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def _pick_genre(self) -> str:
        return self.genres[bisect(self.genre_weights, self.rng.random() * self.genre_weights[-1])]

    def _pick_content(self, genre: str | None = None) -> int:
        content_type = "series" if self.rng.random() < self.user.series_preference else "movie"
        return self.catalog.sample(self.rng, genre or self._pick_genre(), content_type)

    def run(self, start: datetime) -> list[dict[str, Any]]:
        rng, user = self.rng, self.user
        self.events: list[dict[str, Any]] = []
        self.session_id = self._uuid()
        self.device = (
            user.preferred_device if rng.random() < PREFERRED_DEVICE_SHARE else rng.choice(DEVICES)
        )
        self.t = start

        self._emit("user_login")
        self._wait(2, 10)
        self._emit("home_view")
        impressions = [self._pick_content() for _ in range(rng.randint(4, 8))]
        for content_id in impressions:
            self._wait(1, 3)
            self._emit("content_impression", content_id)

        shown: list[tuple[str, int]] = []
        if rng.random() < RECOMMENDATION_ROW_PROBABILITY:
            candidates = self.recommendation_candidates
            for rank, content_id in enumerate(rng.sample(candidates, min(RECOMMENDATION_ROW_SIZE, len(candidates))), 1):
                recommendation_id = self._uuid()
                shown.append((recommendation_id, content_id))
                self._emit(
                    "recommendation_impression",
                    content_id,
                    recommendation_id=recommendation_id,
                    metadata={"algorithm": "popularity", "rank": rank},
                )

        plays = 0 if rng.random() < BROWSE_ONLY_PROBABILITY else 1 + _poisson(rng, user.series_preference * 1.5)
        content_id: int | None = None
        for _ in range(plays):
            recommendation_id = None
            if content_id in self.catalog.series_ids and rng.random() < user.series_preference:
                pass  # autoplay the next episode of the same series: no click needed
            elif rng.random() < user.discovery_rate:
                genre = self._pick_genre()
                self._wait(5, 20)
                self._emit("search", metadata={"query": genre.lower()})
                content_id = self._pick_content(genre)
                self._wait(3, 10)
                self._emit("content_click", content_id)
            elif shown and rng.random() < RECOMMENDATION_CLICK_PROBABILITY:
                # Higher-ranked recommendations get clicked more often
                recommendation_id, content_id = rng.choices(shown, weights=range(len(shown), 0, -1))[0]
                self._wait(2, 8)
                self._emit("recommendation_click", content_id, recommendation_id=recommendation_id)
            else:
                content_id = rng.choice(impressions)
                self._wait(2, 8)
                self._emit("content_click", content_id)
            self._play(content_id, recommendation_id)
            self._wait(5, 30)

        self._emit("session_end")
        return self.events

    def _play(self, content_id: int, recommendation_id: str | None) -> None:
        rng, user = self.rng, self.user
        duration = self.catalog.duration_seconds[content_id]
        on_taste = bool(self.catalog.genres[content_id] & self.top_genres)
        completion = user.completion_propensity * (1 if on_taste else OFF_TASTE_COMPLETION_FACTOR)
        completes = rng.random() < completion
        # Abandonment concentrates early in the title, like real drop-off curves
        stop_at = duration if completes else max(60, int(duration * rng.betavariate(1.2, 2.5)))

        self._emit("play", content_id, position_seconds=0, recommendation_id=recommendation_id)
        position = 0
        if rng.random() < SEEK_PROBABILITY and stop_at > 600:
            skip = rng.randint(30, 180)
            self._wait(5, 30)
            position += skip
            self._emit("seek", content_id, position_seconds=position, metadata={"from_seconds": position - skip})

        remaining = range(position + 1, stop_at)
        pauses = min(_poisson(rng, stop_at / SECONDS_PER_PAUSE), len(remaining))
        for pause_at in sorted(rng.sample(remaining, pauses)):
            self.t += timedelta(seconds=pause_at - position)
            self._emit("pause", content_id, watch_seconds=pause_at - position, position_seconds=pause_at)
            self._wait(10, 600)
            self._emit("resume", content_id, position_seconds=pause_at)
            position = pause_at

        self.t += timedelta(seconds=stop_at - position)
        self._emit(
            "complete" if completes else "stop",
            content_id,
            watch_seconds=stop_at - position,
            position_seconds=stop_at,
            recommendation_id=recommendation_id,
        )
        if completes and rng.random() < (0.35 if on_taste else 0.1):
            self._wait(1, 5)
            self._emit("like", content_id)
        elif not completes and rng.random() < (0.05 if on_taste else 0.15):
            self._wait(1, 5)
            self._emit("dislike", content_id)

    def _wait(self, low: int, high: int) -> None:
        self.t += timedelta(seconds=self.rng.randint(low, high))

    def _emit(
        self,
        event_type: str,
        content_id: int | None = None,
        *,
        watch_seconds: int | None = None,
        position_seconds: int | None = None,
        recommendation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            {
                "event_id": self._uuid(),
                "event_type": event_type,
                "user_id": self.user.user_id,
                "session_id": self.session_id,
                "content_id": content_id,
                "timestamp": self.t.isoformat(),
                "device_type": self.device,
                "country": self.user.country,
                "region": self.user.region,
                "watch_seconds": watch_seconds,
                "position_seconds": position_seconds,
                "recommendation_id": recommendation_id,
                "metadata": metadata,
            }
        )


def generate_user_history(
    user: SimUser, catalog: CatalogIndex, start: date, end: date, seed: int = 42
) -> Iterator[dict[str, Any]]:
    """Yield every event of one user between ``start`` (inclusive) and ``end`` (exclusive).

    Each user has its own random stream seeded by (seed, user_id), so the output does
    not depend on which other users are generated: reruns produce the same event_ids.
    """
    rng = random.Random(f"{seed}-{user.user_id}")
    first_day = max(start, user.signup_date)
    total_days = (end - first_day).days
    if total_days <= 0:
        return

    churn_day: date | None = None
    if rng.random() < user.churn_risk and total_days > MIN_DAYS_BEFORE_CHURN:
        churn_day = first_day + timedelta(days=rng.randint(MIN_DAYS_BEFORE_CHURN, total_days - 1))

    tz = timezone(timedelta(hours=COUNTRY_UTC_OFFSET_HOURS[user.country]))
    simulator = SessionSimulator(user, catalog, rng)
    weekend_rate = user.sessions_per_week * user.weekend_bias / 2
    weekday_rate = user.sessions_per_week * (1 - user.weekend_bias) / 5
    last_end = datetime.combine(first_day, datetime.min.time(), tz)

    for offset in range(total_days):
        day = first_day + timedelta(days=offset)
        if churn_day and day >= churn_day:
            return
        rate = weekend_rate if day.weekday() >= 5 else weekday_rate
        if churn_day:
            # Engagement fades in the weeks before churn: the signal the churn model will learn
            rate *= min(1.0, max(0.2, (churn_day - day).days / CHURN_DECAY_DAYS))

        for _ in range(_poisson(rng, rate)):
            hour = round(rng.gauss(user.peak_hour, 2)) % 24
            start_at = datetime.combine(day, datetime.min.time(), tz) + timedelta(
                hours=hour, seconds=rng.randint(0, 3599)
            )
            if start_at <= last_end:  # never overlap two sessions of the same user
                start_at = last_end + timedelta(minutes=rng.randint(10, 60))
            events = simulator.run(start_at)
            last_end = simulator.t
            yield from events


def generate_history(
    users: list[SimUser], catalog: CatalogIndex, start: date, end: date, seed: int = 42
) -> Iterator[dict[str, Any]]:
    """Yield the events of all users, one user at a time."""
    for user in users:
        yield from generate_user_history(user, catalog, start, end, seed)


def load_catalog(processed_dir: Path = DEFAULT_PROCESSED_DIR) -> CatalogIndex:
    path = processed_dir / "content_catalog.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: python src/ingestion/load_movielens.py")
    return CatalogIndex(pd.read_parquet(path))


def load_users() -> list[SimUser]:
    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.user_id, u.signup_date, u.country, u.region, u.preferred_device, p.persona,
                       p.genre_affinity, p.sessions_per_week, p.peak_hour, p.weekend_bias,
                       p.series_preference, p.completion_propensity, p.discovery_rate, p.churn_risk
                FROM dim_users u JOIN sim_user_profiles p USING (user_id)
                ORDER BY u.user_id
                """
            )
            rows = cursor.fetchall()
    finally:
        connection.close()
    if not rows:
        raise RuntimeError("No users found. Run: python -m src.generation.users")
    return [
        SimUser(*row[:6], {g: float(v) for g, v in row[6].items()}, float(row[7]), int(row[8]), *map(float, row[9:]))
        for row in rows
    ]


def print_summary(events: Iterator[dict[str, Any]], users: list[SimUser], days: int) -> None:
    """Consume the stream and print per-persona behavior, without storing events."""
    persona_of = {u.user_id: u.persona for u in users}
    users_per_persona = Counter(persona_of.values())
    by_type: Counter[str] = Counter()
    stats: dict[str, Counter[str]] = defaultdict(Counter)
    hours: dict[str, Counter[int]] = defaultdict(Counter)
    started = time.perf_counter()

    for event in events:
        persona = persona_of[event["user_id"]]
        event_type = event["event_type"]
        by_type[event_type] += 1
        stats[persona][event_type] += 1
        stats[persona]["watch_seconds"] += event["watch_seconds"] or 0
        if event_type == "play":
            hours[persona][int(event["timestamp"][11:13])] += 1

    elapsed = time.perf_counter() - started
    total = sum(by_type.values())
    print(f"\n[OK] {total:,} events in {elapsed:.1f}s ({total / max(elapsed, 1e-9):,.0f} events/s)\n")
    for event_type, count in by_type.most_common():
        print(f"  {event_type:<28}{count:>12,}")

    weeks = days / 7
    print(f"\n{'persona':<24}{'sess/user/wk':>13}{'watch h/user':>13}{'completion':>11}{'rec CTR':>9}{'top hour':>10}")
    for persona, counter in sorted(stats.items()):
        n = users_per_persona[persona]
        finished = counter["complete"] + counter["stop"]
        print(
            f"{persona:<24}"
            f"{counter['user_login'] / n / weeks:>13.2f}"
            f"{counter['watch_seconds'] / 3600 / n:>13.1f}"
            f"{counter['complete'] / max(finished, 1):>11.1%}"
            f"{counter['recommendation_click'] / max(counter['recommendation_impression'], 1):>9.1%}"
            # Mode, not median: hours are circular, so 23h and 0h are neighbors
            f"{hours[persona].most_common(1)[0][0] if hours[persona] else '-':>10}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate StreamFlix behavioral events and print a summary.")
    parser.add_argument("--days", type=int, default=int(os.getenv("HISTORY_DAYS", "30")))
    parser.add_argument("--users", type=int, default=None, help="Simulate only a random sample of N users")
    args = parser.parse_args()

    seed = int(os.getenv("SIMULATION_SEED", "42"))
    end = date.fromisoformat(os.getenv("SIMULATION_REFERENCE_DATE", date.today().isoformat()))
    start = end - timedelta(days=args.days)

    users = load_users()
    if args.users:
        users = sorted(random.Random(seed).sample(users, min(args.users, len(users))), key=lambda u: u.user_id)
    catalog = load_catalog()

    print("=" * 60)
    print(f"StreamFlix Event Generator: {len(users):,} users, {start} -> {end} ({args.days} days), seed={seed}")
    print("=" * 60)
    print_summary(generate_history(users, catalog, start, end, seed), users, args.days)


if __name__ == "__main__":
    main()
