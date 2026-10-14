from src.streaming.producer import TopicSettings, event_topics, limited, serialize_event


def test_event_topics_include_all_events_and_playback_topic() -> None:
    settings = TopicSettings()
    event = {"event_type": "play"}

    assert event_topics(event, settings) == ["streamflix.events", "streamflix.playback"]


def test_event_topics_route_recommendation_events() -> None:
    settings = TopicSettings()
    event = {"event_type": "recommendation_click"}

    assert event_topics(event, settings) == ["streamflix.events", "streamflix.recommendations"]


def test_serialize_event_returns_stable_utf8_json() -> None:
    event = {"event_type": "search", "user_id": 1, "metadata": {"query": "ação"}}

    assert serialize_event(event) == b'{"event_type":"search","metadata":{"query":"a\xc3\xa7\xc3\xa3o"},"user_id":1}'


def test_limited_stops_after_requested_count() -> None:
    events = ({"event_type": str(index)} for index in range(5))

    assert list(limited(events, 2)) == [{"event_type": "0"}, {"event_type": "1"}]
