from fastapi.testclient import TestClient

from src.api.main import app, load_recommendations
from src.api.models.recommendations import RecommendationItem
from src.api.thumbnail import choose_thumbnail_variant


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recommendations_endpoint_returns_items() -> None:
    response = TestClient(app).get("/recommendations/1?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == 1
    assert len(payload["recommendations"]) == 2
    assert "title" in payload["recommendations"][0]
    assert "primary_genre" in payload["recommendations"][0]


def test_feedback_endpoint_accepts_payload() -> None:
    response = TestClient(app).post(
        "/feedback",
        json={"user_id": 1, "content_id": 10, "feedback_type": "click"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_thumbnail_variant_uses_genre_and_experiment() -> None:
    assert choose_thumbnail_variant("Action", "treatment") == "action_treatment"


def test_load_recommendations_prefers_fact_recommendations(monkeypatch) -> None:
    expected = [RecommendationItem(content_id=99, algorithm="hybrid")]

    monkeypatch.setattr("src.api.main._warehouse_items", lambda user_id, limit, variant: expected)
    monkeypatch.setattr("src.api.main._popular_items", lambda limit, variant: [])

    assert load_recommendations(1, 10, "control") == expected


def test_load_recommendations_uses_popular_view_when_user_has_no_recommendations(monkeypatch) -> None:
    expected = [RecommendationItem(content_id=20, algorithm="warehouse_popularity")]

    monkeypatch.setattr("src.api.main._warehouse_items", lambda user_id, limit, variant: [])
    monkeypatch.setattr("src.api.main._popular_items", lambda limit, variant: expected)

    assert load_recommendations(1, 10, "control") == expected
