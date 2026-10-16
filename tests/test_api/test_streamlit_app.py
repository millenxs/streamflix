from app.streamlit_app import build_feedback_payload, content_subtitle, recommendation_reason


def test_build_feedback_payload_without_recommendation_id() -> None:
    item = {"content_id": 2571, "score": 0.45}

    assert build_feedback_payload(1, item, "click") == {
        "user_id": 1,
        "content_id": 2571,
        "feedback_type": "click",
    }


def test_build_feedback_payload_includes_recommendation_id() -> None:
    item = {"content_id": 2571, "recommendation_id": "rec-1"}

    assert build_feedback_payload(1, item, "play") == {
        "user_id": 1,
        "content_id": 2571,
        "feedback_type": "play",
        "recommendation_id": "rec-1",
    }


def test_content_subtitle_uses_metadata() -> None:
    item = {"primary_genre": "Action", "release_year": 1999, "content_type": "movie"}

    assert content_subtitle(item) == "Action • 1999 • Movie"


def test_recommendation_reason_explains_hybrid_model() -> None:
    item = {"algorithm": "hybrid", "primary_genre": "Action"}

    assert "histórico" in recommendation_reason(item)
    assert "Action" in recommendation_reason(item)
