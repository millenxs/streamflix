import json

import pytest

from src.streaming.consumer import (
    RAW_EVENT_INSERT,
    RAW_PLAYBACK_INSERT,
    KafkaMessageContext,
    insert_event,
    parse_event_payload,
    raw_event_metadata,
    raw_event_params,
    raw_playback_params,
)


class RecordingCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement: str, params: dict) -> None:
        self.calls.append((statement, params))


@pytest.fixture
def event() -> dict:
    return {
        "event_id": "49e0fcd7-7227-4f90-b14f-ecb6453772a7",
        "event_type": "pause",
        "user_id": 10,
        "session_id": "00d5e9dd-5cef-48b6-8152-f6da2976b7c9",
        "content_id": 100,
        "timestamp": "2026-10-01T20:00:00-03:00",
        "device_type": "smart_tv",
        "country": "BRA",
        "region": "Sudeste",
        "watch_seconds": 120,
        "position_seconds": 120,
        "metadata": {"reason": "user_action"},
    }


def test_parse_event_payload_accepts_valid_json_object(event) -> None:
    payload = json.dumps(event).encode("utf-8")

    assert parse_event_payload(payload) == event


def test_parse_event_payload_rejects_missing_required_fields(event) -> None:
    event.pop("session_id")

    with pytest.raises(ValueError, match="session_id"):
        parse_event_payload(json.dumps(event))


def test_raw_event_metadata_preserves_recommendation_id(event) -> None:
    event["recommendation_id"] = "74cdfe6f-29ff-4c64-9558-bd9d2c09aaaf"

    assert raw_event_metadata(event) == {
        "reason": "user_action",
        "recommendation_id": "74cdfe6f-29ff-4c64-9558-bd9d2c09aaaf",
    }


def test_raw_event_params_adds_kafka_context(event) -> None:
    context = KafkaMessageContext(topic="streamflix.events", partition=2, offset=99)

    params = raw_event_params(event, context)

    assert params["event_id"] == event["event_id"]
    assert params["kafka_topic"] == "streamflix.events"
    assert params["kafka_partition"] == 2
    assert params["kafka_offset"] == 99
    assert params["processed_at"].tzinfo is not None


def test_raw_playback_params_maps_playback_fields(event) -> None:
    params = raw_playback_params(event)

    assert params == {
        "event_id": event["event_id"],
        "user_id": 10,
        "session_id": event["session_id"],
        "content_id": 100,
        "event_type": "pause",
        "timestamp": event["timestamp"],
        "position_seconds": 120,
        "watch_seconds": 120,
        "duration_seconds": None,
        "device_type": "smart_tv",
    }


def test_insert_event_writes_raw_and_playback_rows(event) -> None:
    cursor = RecordingCursor()
    context = KafkaMessageContext(topic="streamflix.events", partition=0, offset=5)

    assert insert_event(cursor, event, context) == (True, True)

    assert [statement for statement, _ in cursor.calls] == [RAW_EVENT_INSERT, RAW_PLAYBACK_INSERT]


def test_insert_event_writes_only_raw_for_non_playback(event) -> None:
    cursor = RecordingCursor()
    context = KafkaMessageContext(topic="streamflix.events", partition=0, offset=5)
    event = {
        "event_id": "49e0fcd7-7227-4f90-b14f-ecb6453772a7",
        "event_type": "home_view",
        "user_id": 10,
        "session_id": "00d5e9dd-5cef-48b6-8152-f6da2976b7c9",
        "timestamp": "2026-10-01T20:00:00-03:00",
    }

    assert insert_event(cursor, event, context) == (True, False)

    assert [statement for statement, _ in cursor.calls] == [RAW_EVENT_INSERT]
