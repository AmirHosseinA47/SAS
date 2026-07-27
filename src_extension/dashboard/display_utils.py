"""Dashboard-only presentation helpers."""

from __future__ import annotations

_DISPLAY_WIND_VECTORS: dict[str, tuple[float, float]] = {
    "north": (0.0, 1.0),
    "south": (0.0, -1.0),
    "east": (1.0, 0.0),
    "west": (-1.0, 0.0),
}


def normalize_display_wind_direction(value: object | None = None) -> str:
    direction = str(value if value is not None else "unknown").strip().lower()
    if direction in _DISPLAY_WIND_VECTORS:
        return direction
    return "unknown"


def display_wind_vector(direction: object | None = None) -> tuple[float, float]:
    """Human-facing wind vector for dashboard display only."""
    label = normalize_display_wind_direction(direction)
    return _DISPLAY_WIND_VECTORS.get(label, (0.0, 0.0))
