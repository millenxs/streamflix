"""Churn prediction model training."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.features.user_features import DEFAULT_FEATURE_DIR, USER_FEATURE_COLUMNS, normalize_feature_frame

DEFAULT_MODEL_DIR = Path("models") / "churn"
CHURN_FEATURES = [column for column in USER_FEATURE_COLUMNS if column not in {"user_id", "is_churned_30d"}]


def train_churn_model(features: pd.DataFrame, random_state: int = 42) -> tuple[Pipeline, dict[str, float]]:
    """Train a churn classifier and return model metrics."""
    frame = normalize_feature_frame(features)
    if frame["is_churned_30d"].nunique() < 2:
        raise ValueError("churn training requires both churned and active users")

    x_train, x_test, y_train, y_test = train_test_split(
        frame[CHURN_FEATURES],
        frame["is_churned_30d"],
        test_size=0.25,
        random_state=random_state,
        stratify=frame["is_churned_30d"],
    )
    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("classifier", RandomForestClassifier(n_estimators=100, random_state=random_state, class_weight="balanced")),
        ]
    )
    model.fit(x_train, y_train)
    probabilities = model.predict_proba(x_test)[:, 1]
    metrics = {"roc_auc": float(roc_auc_score(y_test, probabilities)), "test_users": float(len(y_test))}
    return model, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train StreamFlix churn prediction model.")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURE_DIR / "user_features.parquet")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MODEL_DIR)
    args = parser.parse_args()

    model, metrics = train_churn_model(pd.read_parquet(args.features))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.output_dir / "churn_model.joblib")
    pd.DataFrame([metrics]).to_json(args.output_dir / "churn_metrics.json", orient="records", indent=2)
    print(f"[OK] Trained churn model: roc_auc={metrics['roc_auc']:.3f}")


if __name__ == "__main__":
    main()
