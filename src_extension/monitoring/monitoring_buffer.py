"""MAPE-K buffer between monitoring (observe) and knowledge updates."""

from __future__ import annotations

from typing import Any


class MonitoringBuffer:
    """Holds monitoring outputs until the knowledge layer consumes them."""

    def __init__(self) -> None:
        self.local_observations: dict[str, Any] = {}
        self.global_snapshot: Any = None
        self.communication_snapshot: Any = None
        self.firefighter_snapshot: list[Any] | None = None

    def add_local_observation(self, uav_id: str, obs: Any) -> None:
        self.local_observations[uav_id] = obs

    def set_global_snapshot(self, snapshot: Any) -> None:
        self.global_snapshot = snapshot

    def clear(self) -> None:
        self.local_observations.clear()
        self.global_snapshot = None
        self.communication_snapshot = None
        self.firefighter_snapshot = None
