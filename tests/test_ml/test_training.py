import pandas as pd

from src.features.user_features import normalize_feature_frame
from src.ml.clustering.train import train_taste_clusters
from src.ml.churn.train import train_churn_model


def test_normalize_feature_frame_adds_missing_columns() -> None:
    features = normalize_feature_frame(pd.DataFrame({"user_id": [1]}))

    assert features.loc[0, "sessions_count"] == 0
    assert features.loc[0, "is_churned_30d"] == 0


def test_train_taste_clusters_caps_cluster_count() -> None:
    features = normalize_feature_frame(pd.DataFrame({"user_id": [1, 2], "sessions_count": [1, 5]}))

    assignments, _ = train_taste_clusters(features, n_clusters=8)

    assert len(assignments) == 2
    assert assignments["taste_cluster_id"].nunique() <= 2


def test_train_churn_model_returns_auc_metric() -> None:
    features = pd.DataFrame(
        {
            "user_id": range(1, 9),
            "sessions_count": [1, 2, 3, 4, 10, 11, 12, 13],
            "events_count": [1, 2, 3, 4, 10, 11, 12, 13],
            "contents_watched": [1, 1, 2, 2, 5, 5, 6, 6],
            "total_watch_seconds": [10, 20, 30, 40, 500, 600, 700, 800],
            "avg_session_seconds": [10, 20, 30, 40, 50, 60, 70, 80],
            "completion_rate": [0, 0, 0.1, 0.2, 0.8, 0.9, 1, 1],
            "like_rate": [0, 0, 0, 0, 0.7, 0.8, 0.9, 1],
            "recommendation_ctr": [0, 0, 0, 0, 0.1, 0.2, 0.3, 0.4],
            "rec_watch_share": [0, 0, 0, 0, 0.2, 0.2, 0.3, 0.4],
            "days_since_last_activity": [40, 35, 31, 30, 1, 2, 3, 4],
            "is_churned_30d": [1, 1, 1, 1, 0, 0, 0, 0],
        }
    )

    _, metrics = train_churn_model(features)

    assert 0 <= metrics["roc_auc"] <= 1
