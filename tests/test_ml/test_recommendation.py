import pandas as pd

from src.experiments.ab_testing import assign_variant
from src.ml.evaluation.ranking import ndcg_at_k, precision_at_k, recall_at_k
from src.ml.recommendation.baseline import recommend_popular
from src.ml.recommendation.content_based import recommend_similar_content
from src.ml.recommendation.hybrid import blend_rankings


def test_popularity_recommender_ranks_by_engagement() -> None:
    events = pd.DataFrame(
        [
            {"content_id": 1, "event_type": "play", "completed": False, "watch_seconds": 10},
            {"content_id": 2, "event_type": "complete", "completed": True, "watch_seconds": 1000},
        ]
    )

    assert recommend_popular(events, limit=2)[0] == 2


def test_content_based_recommends_shared_genres() -> None:
    catalog = pd.DataFrame(
        [
            {"content_id": 1, "genres": "Action|Sci-Fi"},
            {"content_id": 2, "genres": "Action"},
            {"content_id": 3, "genres": "Romance"},
        ]
    )

    assert recommend_similar_content(catalog, 1, limit=1) == [2]


def test_hybrid_blends_rankings() -> None:
    assert blend_rankings([[1, 2], [2, 3]], weights=[1.0, 2.0], limit=2) == [2, 1]


def test_ranking_metrics() -> None:
    recommended = [10, 20, 30]
    relevant = {20, 40}

    assert precision_at_k(recommended, relevant, 2) == 0.5
    assert recall_at_k(recommended, relevant, 3) == 0.5
    assert ndcg_at_k(recommended, relevant, 3) > 0


def test_ab_assignment_is_deterministic() -> None:
    assert assign_variant(123, "rec-test") == assign_variant(123, "rec-test")
