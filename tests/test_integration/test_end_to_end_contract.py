import pandas as pd

from src.features.user_features import normalize_feature_frame
from src.ml.clustering.train import train_taste_clusters
from src.ml.recommendation.baseline import recommend_popular
from src.streaming.producer import TopicSettings, event_topics


def test_end_to_end_contract_from_event_to_recommendation() -> None:
    event = {"event_type": "play", "user_id": 1}
    assert event_topics(event, TopicSettings()) == ["streamflix.events", "streamflix.playback"]

    events = pd.DataFrame(
        [{"content_id": 10, "event_type": "complete", "completed": True, "watch_seconds": 1000}]
    )
    assert recommend_popular(events, limit=1) == [10]

    features = normalize_feature_frame(pd.DataFrame({"user_id": [1], "sessions_count": [1]}))
    assignments, _ = train_taste_clusters(features, n_clusters=1)
    assert assignments.loc[0, "taste_cluster_id"] == 0
