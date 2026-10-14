"""Publish synthetic StreamFlix behavioral events to Kafka.

The generator in :mod:`src.generation.events` remains the source of truth for
synthetic behavior. This module adds the streaming boundary: each generated event
is published to the all-events topic and, when applicable, to a domain-specific
topic for playback, interactions, or recommendations.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable, Iterator

from dotenv import load_dotenv

from src.generation.events import SimUser, generate_history, load_catalog, load_users

load_dotenv()

PLAYBACK_EVENT_TYPES = {"play", "pause", "resume", "seek", "stop", "complete"}
INTERACTION_EVENT_TYPES = {"search", "content_click", "like", "dislike"}
RECOMMENDATION_EVENT_TYPES = {"recommendation_impression", "recommendation_click"}


@dataclass(frozen=True)
class TopicSettings:
    """Kafka topic names loaded from environment variables."""

    events: str = os.getenv("KAFKA_TOPIC_EVENTS", "streamflix.events")
    playback: str = os.getenv("KAFKA_TOPIC_PLAYBACK", "streamflix.playback")
    interactions: str = os.getenv("KAFKA_TOPIC_INTERACTIONS", "streamflix.interactions")
    recommendations: str = os.getenv("KAFKA_TOPIC_RECOMMENDATIONS", "streamflix.recommendations")


@dataclass
class PublishStats:
    """Counters collected while publishing events."""

    source_events: int = 0
    kafka_messages: int = 0
    delivery_errors: int = 0
    by_event_type: Counter[str] = field(default_factory=Counter)
    by_topic: Counter[str] = field(default_factory=Counter)


def event_topics(event: dict[str, Any], settings: TopicSettings) -> list[str]:
    """Return the Kafka topics that should receive an event."""
    event_type = str(event["event_type"])
    topics = [settings.events]
    if event_type in PLAYBACK_EVENT_TYPES:
        topics.append(settings.playback)
    if event_type in INTERACTION_EVENT_TYPES:
        topics.append(settings.interactions)
    if event_type in RECOMMENDATION_EVENT_TYPES:
        topics.append(settings.recommendations)
    return topics


def serialize_event(event: dict[str, Any]) -> bytes:
    """Serialize an event as stable UTF-8 JSON."""
    return json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def select_users(users: list[SimUser], count: int | None, seed: int) -> list[SimUser]:
    """Return all users or a deterministic sample, sorted for reproducible output."""
    if count is None:
        return users
    sampled = random.Random(seed).sample(users, min(count, len(users)))
    return sorted(sampled, key=lambda user: user.user_id)


def build_event_stream(days: int, user_count: int | None, seed: int) -> Iterator[dict[str, Any]]:
    """Build the synthetic event stream from loaded users and content catalog."""
    end = date.fromisoformat(os.getenv("SIMULATION_REFERENCE_DATE", date.today().isoformat()))
    start = end - timedelta(days=days)
    users = select_users(load_users(), user_count, seed)
    catalog = load_catalog()
    return generate_history(users, catalog, start, end, seed)


def limited(events: Iterable[dict[str, Any]], limit: int | None) -> Iterator[dict[str, Any]]:
    """Yield at most ``limit`` events when a limit was provided."""
    for index, event in enumerate(events, start=1):
        if limit is not None and index > limit:
            return
        yield event


def print_stats(stats: PublishStats) -> None:
    """Print a concise publishing summary."""
    print(f"\n[OK] Source events: {stats.source_events:,}")
    print(f"[OK] Kafka messages: {stats.kafka_messages:,}")
    if stats.delivery_errors:
        print(f"[WARN] Delivery errors: {stats.delivery_errors:,}")

    print("\nMessages by topic:")
    for topic, count in stats.by_topic.most_common():
        print(f"  {topic:<35}{count:>10,}")

    print("\nSource events by type:")
    for event_type, count in stats.by_event_type.most_common():
        print(f"  {event_type:<28}{count:>10,}")


def dry_run(events: Iterable[dict[str, Any]], settings: TopicSettings, limit: int) -> PublishStats:
    """Print generated events without connecting to Kafka."""
    stats = PublishStats()
    for event in limited(events, limit):
        topics = event_topics(event, settings)
        print(json.dumps({"topics": topics, "event": event}, ensure_ascii=False, sort_keys=True))
        stats.source_events += 1
        stats.kafka_messages += len(topics)
        stats.by_event_type[event["event_type"]] += 1
        stats.by_topic.update(topics)
    return stats


def publish_to_kafka(
    events: Iterable[dict[str, Any]],
    settings: TopicSettings,
    bootstrap_servers: str,
    limit: int | None,
    events_per_second: float,
) -> PublishStats:
    """Publish generated events to Kafka and return delivery statistics."""
    try:
        from confluent_kafka import Producer
    except ImportError as exc:
        raise RuntimeError("confluent-kafka is not installed. Run: python -m pip install -r requirements.txt") from exc

    stats = PublishStats()

    def on_delivery(error: Any, message: Any) -> None:
        del message
        if error is not None:
            stats.delivery_errors += 1
            print(f"[ERROR] Kafka delivery failed: {error}")

    producer = Producer({"bootstrap.servers": bootstrap_servers})
    next_emit = time.perf_counter()
    interval = 1 / events_per_second if events_per_second > 0 else 0

    for event in limited(events, limit):
        payload = serialize_event(event)
        key = str(event["user_id"])
        topics = event_topics(event, settings)
        for topic in topics:
            producer.produce(topic, key=key, value=payload, callback=on_delivery)
            producer.poll(0)

        stats.source_events += 1
        stats.kafka_messages += len(topics)
        stats.by_event_type[event["event_type"]] += 1
        stats.by_topic.update(topics)

        if interval:
            next_emit += interval
            sleep_for = next_emit - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)

    producer.flush()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish synthetic StreamFlix events to Kafka.")
    parser.add_argument("--days", type=int, default=int(os.getenv("HISTORY_DAYS", "30")))
    parser.add_argument("--users", type=int, default=None, help="Use a deterministic sample of N users")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N source events")
    parser.add_argument(
        "--events-per-second",
        type=float,
        default=float(os.getenv("EVENTS_PER_SECOND", "100")),
        help="Source event rate; use 0 to publish as fast as possible",
    )
    parser.add_argument("--seed", type=int, default=int(os.getenv("SIMULATION_SEED", "42")))
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
        help="Kafka bootstrap servers visible from this Python process",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print events and target topics without Kafka")
    args = parser.parse_args()

    if args.days <= 0:
        raise ValueError("--days must be positive")
    if args.users is not None and args.users <= 0:
        raise ValueError("--users must be positive")
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be positive")
    if args.events_per_second < 0:
        raise ValueError("--events-per-second cannot be negative")

    settings = TopicSettings()
    events = build_event_stream(args.days, args.users, args.seed)

    if args.dry_run:
        stats = dry_run(events, settings, args.limit or 10)
    else:
        stats = publish_to_kafka(
            events,
            settings,
            args.bootstrap_servers,
            args.limit,
            args.events_per_second,
        )

    print_stats(stats)


if __name__ == "__main__":
    main()
