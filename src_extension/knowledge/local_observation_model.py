"""Managing system: local UAV observation runtime knowledge.

This container stores one UAV's local perception patch for Step 4 runtime
knowledge. It is not a planner, analyzer, or executor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .knowledge_utils import clamp01, compute_age, validate_metadata
from .runtime_model_common import CellCoord, Confidence, Timestamp


@dataclass
class LocalObservationModel:
    """Per-UAV local observation state (knowledge-layer only)."""

    uav_id: str
    visible_fire_cells: set[CellCoord] = field(default_factory=set)
    visible_smoke_cells: set[CellCoord] = field(default_factory=set)
    visible_victim_candidates: list[dict[str, Any]] = field(default_factory=list)
    local_confidence_patch: dict[CellCoord, Confidence] = field(default_factory=dict)
    local_uncertainty_patch: dict[CellCoord, float] = field(default_factory=dict)
    nearby_uavs: set[str] = field(default_factory=set)
    local_comm_quality: Confidence | None = None
    local_drift_state: str | None = None
    local_battery_state: str | None = None
    current_task_context: dict[str, Any] = field(default_factory=dict)
    negative_local_observations: dict[CellCoord, str] = field(default_factory=dict)
    timestamp: Timestamp | None = None

    def update_from_local_report(
        self,
        *,
        timestamp: Timestamp,
        visible_fire_cells: set[CellCoord] | None = None,
        visible_smoke_cells: set[CellCoord] | None = None,
        visible_victim_candidates: list[dict[str, Any]] | None = None,
        local_confidence_patch: dict[CellCoord, Confidence] | None = None,
        local_uncertainty_patch: dict[CellCoord, float] | None = None,
        nearby_uavs: set[str] | None = None,
        local_comm_quality: Confidence | None = None,
        local_drift_state: str | None = None,
        local_battery_state: str | None = None,
        current_task_context: dict[str, Any] | None = None,
        negative_local_observations: dict[CellCoord, str] | None = None,
        source: str = "local_uav_sensor",
        confidence: float = 0.8,
    ) -> None:
        """Update local observation knowledge from one local report."""
        ts, conf, _ = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        if visible_fire_cells is not None:
            self.visible_fire_cells = set(visible_fire_cells)
        if visible_smoke_cells is not None:
            self.visible_smoke_cells = set(visible_smoke_cells)
        if visible_victim_candidates is not None:
            self.visible_victim_candidates = list(visible_victim_candidates)
        if local_confidence_patch is not None:
            self.local_confidence_patch = dict(local_confidence_patch)
        if local_uncertainty_patch is not None:
            self.local_uncertainty_patch = dict(local_uncertainty_patch)
        if nearby_uavs is not None:
            self.nearby_uavs = set(nearby_uavs)
        if local_comm_quality is not None:
            self.local_comm_quality = clamp01(local_comm_quality)
        if local_drift_state is not None:
            self.local_drift_state = local_drift_state
        if local_battery_state is not None:
            self.local_battery_state = local_battery_state
        if current_task_context is not None:
            self.current_task_context = dict(current_task_context)
        if negative_local_observations is not None:
            self.negative_local_observations = dict(negative_local_observations)
        self.timestamp = ts
        if self.local_comm_quality is None:
            self.local_comm_quality = conf

    def apply_time_decay(self, current_time: float) -> None:
        """Decay local confidence patch over time since last local report."""
        if self.timestamp is None:
            return
        age = compute_age(float(current_time), self.timestamp)
        if age <= 0.0:
            return
        decay = max(0.0, 1.0 - (0.03 * age))
        for cell, value in list(self.local_confidence_patch.items()):
            self.local_confidence_patch[cell] = clamp01(value * decay)

    def snapshot(self) -> dict[str, Any]:
        """Read-only local observation snapshot."""
        return {
            "uav_id": self.uav_id,
            "visible_fire_cells": [list(c) for c in self.visible_fire_cells],
            "visible_smoke_cells": [list(c) for c in self.visible_smoke_cells],
            "visible_victim_candidates": list(self.visible_victim_candidates),
            "local_confidence_patch": {f"{a},{b}": v for (a, b), v in self.local_confidence_patch.items()},
            "local_uncertainty_patch": {
                f"{a},{b}": v for (a, b), v in self.local_uncertainty_patch.items()
            },
            "nearby_uavs": sorted(self.nearby_uavs),
            "local_comm_quality": self.local_comm_quality,
            "local_drift_state": self.local_drift_state,
            "local_battery_state": self.local_battery_state,
            "current_task_context": dict(self.current_task_context),
            "negative_local_observations": {
                f"{a},{b}": v for (a, b), v in self.negative_local_observations.items()
            },
            "timestamp": self.timestamp,
        }
