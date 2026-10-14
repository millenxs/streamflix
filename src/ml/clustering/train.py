"""Taste clustering model training."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.features.user_features import DEFAULT_FEATURE_DIR, USER_FEATURE_COLUMNS, normalize_feature_frame

DEFAULT_MODEL_DIR = Path("models") / "clustering"
CLUSTER_FEATURES = [column for column in USER_FEATURE_COLUMNS if column not in {"user_id", "is_churned_30d"}]


def train_taste_clusters(features: pd.DataFrame, n_clusters: int = 8, random_state: int = 42) -> tuple[pd.DataFrame, Pipeline]:
    """Fit K-Means taste clusters and return assignments plus the fitted pipeline."""
    frame = normalize_feature_frame(features)
    if frame.empty:
        raise ValueError("features must not be empty")
    k = min(max(1, n_clusters), len(frame))
    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("kmeans", KMeans(n_clusters=k, random_state=random_state, n_init=10)),
        ]
    )
    labels = model.fit_predict(frame[CLUSTER_FEATURES])
    assignments = frame[["user_id"]].copy()
    assignments["taste_cluster_id"] = labels.astype(int)
    return assignments, model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train StreamFlix taste clustering model.")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURE_DIR / "user_features.parquet")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--clusters", type=int, default=8)
    args = parser.parse_args()

    features = pd.read_parquet(args.features)
    assignments, model = train_taste_clusters(features, args.clusters)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.output_dir / "taste_clusters.joblib")
    assignments.to_parquet(args.output_dir / "taste_cluster_assignments.parquet", index=False)
    print(f"[OK] Trained taste clustering model for {len(assignments):,} users")


if __name__ == "__main__":
    main()
