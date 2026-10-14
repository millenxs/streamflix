"""Consume StreamFlix events from Kafka and persist the raw PostgreSQL layer.

The producer publishes each source event to ``streamflix.events`` and duplicates
some events to domain-specific Kafka topics. This consumer reads only the
all-events topic by default, which avoids inserting duplicate raw rows while still
materializing playback-specific records from the same canonical message.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json

from src.generation.events import DatabaseSettings
from src.streaming.producer import PLAYBACK_EVENT_TYPES, TopicSettings

load_dotenv()

REQUIRED_EVENT_FIELDS = {"event_id", "event_type", "user_id", "session_id", "timestamp"}

RAW_EVENT_INSERT = """
INSERT INTO raw_events (
    event_id, event_type, user_id, session_id, content_id, timestamp,
    device_type, country, region, metadata, processed_at,
    kafka_offset, kafka_partition, kafka_topic
)
VALUES (
    %(event_id)s, %(event_type)s, %(user_id)s, %(session_id)s, %(content_id)s, %(timestamp)s,
    %(device_type)s, %(country)s, %(region)s, %(metadata)s, %(processed_at)s,
    %(kafka_offset)s, %(kafka_partition)s, %(kafka_topic)s
)
ON CONFLICT (event_id) DO NOTHING
"""

RAW_PLAYBACK_INSERT = """
INSERT INTO raw_playback_events (
    event_id, user_id, session_id, content_id, event_type, timestamp,
    position_seconds, watch_seconds, duration_seconds, device_type
)
VALUES (
    %(event_id)s, %(user_id)s, %(session_id)s, %(content_id)s, %(event_type)s, %(timestamp)s,
    %(position_seconds)s, %(watch_seconds)s, %(duration_seconds)s, %(device_type)s
)
ON CONFLICT (event_id) DO NOTHING
"""


@dataclass(frozen=True)
class KafkaMessageContext:
    """Kafka coordinates attached to a consumed event."""

    topic: str
    partition: int
    offset: int


@dataclass
class ConsumerStats:
    """Counters collected while consuming Kafka events."""

    messages: int = 0
    raw_events: int = 0
    raw_playback_events: int = 0
    skipped: int = 0
    by_event_type: Counter[str] = field(default_factory=Counter)


def parse_event_payload(payload: bytes | str) -> dict[str, Any]:
    """Decode and validate a JSON event payload from Kafka."""
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Kafka payload must be a JSON object")

    missing = REQUIRED_EVENT_FIELDS - value.keys()
    if missing:
        raise ValueError(f"Kafka event is missing required fields: {sorted(missing)}")
    return value


def raw_event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    """Return raw-event metadata while preserving fields without dedicated columns."""
    metadata = dict(event.get("metadata") or {})
    if event.get("recommendation_id") is not None:
        metadata["recommendation_id"] = event["recommendation_id"]
    return metadata


def raw_event_params(event: dict[str, Any], context: KafkaMessageContext) -> dict[str, Any]:
    """Map a generated event to ``raw_events`` insert parameters."""
    return {
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "user_id": event["user_id"],
        "session_id": event["session_id"],
        "content_id": event.get("content_id"),
        "timestamp": event["timestamp"],
        "device_type": event.get("device_type"),
        "country": event.get("country"),
        "region": event.get("region"),
        "metadata": Json(raw_event_metadata(event)),
        "processed_at": datetime.now(timezone.utc),
        "kafka_offset": context.offset,
        "kafka_partition": context.partition,
        "kafka_topic": context.topic,
    }


def raw_playback_params(event: dict[str, Any]) -> dict[str, Any]:
    """Map a generated playback event to ``raw_playback_events`` insert parameters."""
    return {
        "event_id": event["event_id"],
        "user_id": event["user_id"],
        "session_id": event["session_id"],
        "content_id": event["content_id"],
        "event_type": event["event_type"],
        "timestamp": event["timestamp"],
        "position_seconds": event.get("position_seconds"),
        "watch_seconds": event.get("watch_seconds"),
        "duration_seconds": event.get("duration_seconds"),
        "device_type": event.get("device_type"),
    }


def insert_event(cursor: Any, event: dict[str, Any], context: KafkaMessageContext) -> tuple[bool, bool]:
    """Insert an event into raw tables and return inserted table flags.

    The first returned flag indicates an attempted ``raw_events`` insert. The
    second flag indicates an attempted ``raw_playback_events`` insert.
    """
    cursor.execute(RAW_EVENT_INSERT, raw_event_params(event, context))
    inserted_playback = False
    if event["event_type"] in PLAYBACK_EVENT_TYPES and event.get("content_id") is not None:
        cursor.execute(RAW_PLAYBACK_INSERT, raw_playback_params(event))
        inserted_playback = True
    return True, inserted_playback


def print_stats(stats: ConsumerStats) -> None:
    """Print a concise consumer summary."""
    print(f"\n[OK] Kafka messages: {stats.messages:,}")
    print(f"[OK] raw_events writes: {stats.raw_events:,}")
    print(f"[OK] raw_playback_events writes: {stats.raw_playback_events:,}")
    if stats.skipped:
        print(f"[WARN] Skipped messages: {stats.skipped:,}")

    print("\nMessages by event type:")
    for event_type, count in stats.by_event_type.most_common():
        print(f"  {event_type:<28}{count:>10,}")


def consume_to_postgres(
    bootstrap_servers: str,
    group_id: str,
    topics: list[str],
    limit: int | None,
    poll_timeout: float,
    idle_timeout: float,
) -> ConsumerStats:
    """Consume Kafka messages and persist them into PostgreSQL raw tables."""
    try:
        from confluent_kafka import Consumer, KafkaException
    except ImportError as exc:
        raise RuntimeError("confluent-kafka is not installed. Run: python -m pip install -r requirements.txt") from exc

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    stats = ConsumerStats()

    connection = psycopg2.connect(**asdict(DatabaseSettings()))
    try:
        consumer.subscribe(topics)
        last_message_at = time.perf_counter()
        while limit is None or stats.messages < limit:
            message = consumer.poll(poll_timeout)
            if message is None:
                if idle_timeout > 0 and time.perf_counter() - last_message_at >= idle_timeout:
                    print(f"[INFO] No Kafka messages received for {idle_timeout:.0f}s; stopping consumer.")
                    break
                continue
            if message.error():
                raise KafkaException(message.error())
            last_message_at = time.perf_counter()

            context = KafkaMessageContext(message.topic(), message.partition(), message.offset())
            try:
                event = parse_event_payload(message.value())
                with connection.cursor() as cursor:
                    inserted_raw, inserted_playback = insert_event(cursor, event, context)
                connection.commit()
                consumer.commit(message=message, asynchronous=False)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                connection.rollback()
                stats.skipped += 1
                print(f"[WARN] Skipping invalid Kafka message at {context}: {exc}")
                consumer.commit(message=message, asynchronous=False)
                continue
            except Exception:
                connection.rollback()
                raise

            stats.messages += 1
            stats.raw_events += int(inserted_raw)
            stats.raw_playback_events += int(inserted_playback)
            stats.by_event_type[event["event_type"]] += 1
    finally:
        consumer.close()
        connection.close()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist StreamFlix Kafka events into PostgreSQL raw tables.")
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
        help="Kafka bootstrap servers visible from this Python process",
    )
    parser.add_argument("--group-id", default=os.getenv("KAFKA_CONSUMER_GROUP", "streamflix-raw-loader"))
    parser.add_argument(
        "--topic",
        action="append",
        dest="topics",
        help="Kafka topic to consume. Defaults to KAFKA_TOPIC_EVENTS only to avoid duplicate raw ingestion.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Stop after N valid Kafka messages")
    parser.add_argument("--poll-timeout", type=float, default=1.0)
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=float(os.getenv("KAFKA_CONSUMER_IDLE_TIMEOUT", "30")),
        help="Stop after N seconds without new messages; use 0 to wait forever",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be positive")
    if args.poll_timeout <= 0:
        raise ValueError("--poll-timeout must be positive")
    if args.idle_timeout < 0:
        raise ValueError("--idle-timeout cannot be negative")

    topics = args.topics or [TopicSettings().events]
    stats = consume_to_postgres(
        bootstrap_servers=args.bootstrap_servers,
        group_id=args.group_id,
        topics=topics,
        limit=args.limit,
        poll_timeout=args.poll_timeout,
        idle_timeout=args.idle_timeout,
    )
    print_stats(stats)


if __name__ == "__main__":
    main()
