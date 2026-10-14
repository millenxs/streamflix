"""Deterministic A/B testing assignment utilities."""

from __future__ import annotations

import hashlib


def assign_variant(user_id: int, experiment_name: str, variants: tuple[str, ...] = ("control", "treatment")) -> str:
    """Assign a user to a stable experiment variant."""
    if not variants:
        raise ValueError("variants must not be empty")
    digest = hashlib.sha256(f"{experiment_name}:{user_id}".encode("utf-8")).hexdigest()
    return variants[int(digest[:8], 16) % len(variants)]
