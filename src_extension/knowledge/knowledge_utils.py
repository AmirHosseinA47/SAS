"""Shared helpers for runtime knowledge metadata and time handling."""

from __future__ import annotations

from .runtime_model_common import Timestamp


def clamp01(value: float) -> float:
    """Clamp numeric input into [0.0, 1.0]."""
    return max(0.0, min(1.0, float(value)))


def compute_age(current_time: float, timestamp: float) -> float:
    """Return non-negative elapsed time from timestamp to now."""
    return max(0.0, float(current_time) - float(timestamp))


def validate_metadata(timestamp: Timestamp, confidence: float, source: str) -> tuple[float, float, str]:
    """Validate and normalize required runtime-knowledge metadata."""
    ts = float(timestamp)
    src = str(source).strip()
    if not src:
        raise ValueError("source must be a non-empty string")
    return ts, clamp01(confidence), src
