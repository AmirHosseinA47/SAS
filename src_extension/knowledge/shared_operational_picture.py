"""Managing system: Shared operational picture (used knowledge).

A fused adaptation-layer summary: what is believed, how certain it is,
and how fresh it is aggregated from other runtime knowledge models, not raw
managed operational storage.

TODO: Implement merge/staleness rules; avoid circular imports via lazy assembly;
apply decay and negative information policies when fusing summaries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .knowledge_utils import clamp01
from .runtime_model_common import KnowledgeProvenance


@dataclass
class SharedOperationalPicture:
    """Fused runtime **summaries** for global reasoning (knowledge assembly only)."""

    step_index: int = 0
    provenance: KnowledgeProvenance = field(default_factory=KnowledgeProvenance)
    fire_state_summary: dict[str, Any] = field(default_factory=dict)
    fire_belief_summary: dict[str, Any] = field(default_factory=dict)
    visibility_summary: dict[str, Any] = field(default_factory=dict)
    uncertainty_summary: dict[str, Any] = field(default_factory=dict)
    victim_confidence_summary: dict[str, Any] = field(default_factory=dict)
    uav_team_summary: dict[str, Any] = field(default_factory=dict)
    firefighter_summary: dict[str, Any] = field(default_factory=dict)
    communication_reliability_summary: dict[str, Any] = field(default_factory=dict)
    active_alerts: list[dict[str, Any]] = field(default_factory=list)
    mission_mode: str | None = None
    active_adaptation_state: str | None = None
    layers: dict[str, Any] = field(default_factory=dict)

    def rebuild(self, step_index: int) -> None:
        """TODO: Pull from other knowledge models into typed summaries / ``layers``."""
        self.step_index = step_index

    @staticmethod
    def compute_freshness(timestamp: float | None, current_time: float | None) -> float:
        """Compute normalized freshness score from timestamp age."""
        if timestamp is None or current_time is None:
            return 0.0
        age = max(0.0, float(current_time) - float(timestamp))
        return clamp01(1.0 / (1.0 + age))

    def _snapshot_or_dict(self, candidate: Any) -> dict[str, Any]:
        if candidate is None:
            return {}
        if isinstance(candidate, dict):
            return dict(candidate)
        snap_fn = getattr(candidate, "snapshot", None)
        if callable(snap_fn):
            raw = snap_fn()
            return dict(raw) if isinstance(raw, dict) else {"value": raw}
        return {"value": candidate}

    def rebuild_from_models(
        self,
        *,
        step_index: int | None = None,
        fire_model: Any | None = None,
        fire_snapshot: dict[str, Any] | None = None,
        visibility_model: Any | None = None,
        visibility_snapshot: dict[str, Any] | None = None,
        victim_model: Any | None = None,
        victim_snapshot: dict[str, Any] | None = None,
        uav_model: Any | None = None,
        uav_snapshot: dict[str, Any] | None = None,
        firefighter_model: Any | None = None,
        firefighter_snapshot: dict[str, Any] | None = None,
        communication_model: Any | None = None,
        communication_snapshot: dict[str, Any] | None = None,
        active_alerts: list[dict[str, Any]] | None = None,
        mission_mode: str | None = None,
        active_adaptation_state: str | None = None,
        source: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        """Rebuild fused summaries from optional model objects or snapshots.

        This remains knowledge-layer assembly only (no analysis/planning logic).
        TODO: Add explicit confidence/freshness harmonization across sources.
        """
        if step_index is not None:
            self.step_index = int(step_index)

        fire_data = fire_snapshot or self._snapshot_or_dict(fire_model)
        visibility_data = visibility_snapshot or self._snapshot_or_dict(visibility_model)
        victim_data = victim_snapshot or self._snapshot_or_dict(victim_model)
        uav_data = uav_snapshot or self._snapshot_or_dict(uav_model)
        firefighter_data = firefighter_snapshot or self._snapshot_or_dict(firefighter_model)
        communication_data = communication_snapshot or self._snapshot_or_dict(communication_model)
        now_ts = float(timestamp) if timestamp is not None else self.provenance.timestamp

        self.fire_state_summary = {
            "estimated_burning_cells": fire_data.get("estimated_burning_cells", []),
            "estimated_fire_front_cells": fire_data.get("estimated_fire_front_cells", []),
        }
        self.fire_belief_summary = {
            "fire_probability_map": fire_data.get("fire_probability_map", {}),
            "fire_confidence_map": fire_data.get("fire_confidence_map", {}),
            "last_observed_fire_time": fire_data.get("last_observed_fire_time", {}),
        }
        self.visibility_summary = {
            "visible_cells": visibility_data.get("visible_cells", []),
            "smoke_obscured_cells": visibility_data.get("smoke_obscured_cells", []),
            "observation_status_map": visibility_data.get("observation_status_map", {}),
        }
        self.uncertainty_summary = {
            "unknown_or_uncertain_regions": visibility_data.get("unknown_or_uncertain_regions", []),
            "information_freshness_map": visibility_data.get("information_freshness_map", {}),
            "staleness_map": visibility_data.get("staleness_map", {}),
        }
        self.victim_confidence_summary = {
            "victims": victim_data.get("victims", {}),
            "catalog_provenance": victim_data.get("catalog_provenance", {}),
        }
        self.uav_team_summary = {"by_uav_id": uav_data.get("by_uav_id", {})}
        self.firefighter_summary = {"units": firefighter_data.get("units", {})}
        self.communication_reliability_summary = {
            "delivery_confidence": communication_data.get("state", {}).get("delivery_confidence")
            if isinstance(communication_data.get("state"), dict)
            else communication_data.get("delivery_confidence"),
            "shared_knowledge_sync_quality": communication_data.get("state", {}).get(
                "shared_knowledge_sync_quality"
            )
            if isinstance(communication_data.get("state"), dict)
            else communication_data.get("shared_knowledge_sync_quality"),
            "relay_needed_flag": communication_data.get("state", {}).get("relay_needed_flag")
            if isinstance(communication_data.get("state"), dict)
            else communication_data.get("relay_needed_flag"),
        }
        self.fire_state_summary = {
            "value": dict(self.fire_state_summary),
            "confidence": fire_data.get("provenance", {}).get("confidence"),
            "freshness": self.compute_freshness(
                fire_data.get("provenance", {}).get("timestamp"),
                now_ts,
            ),
        }
        self.fire_belief_summary = {
            "value": dict(self.fire_belief_summary),
            "confidence": fire_data.get("provenance", {}).get("confidence"),
            "freshness": self.compute_freshness(
                fire_data.get("provenance", {}).get("timestamp"),
                now_ts,
            ),
        }
        self.visibility_summary = {
            "value": dict(self.visibility_summary),
            "confidence": visibility_data.get("provenance", {}).get("confidence"),
            "freshness": self.compute_freshness(
                visibility_data.get("provenance", {}).get("timestamp"),
                now_ts,
            ),
        }
        self.uncertainty_summary = {
            "value": dict(self.uncertainty_summary),
            "confidence": visibility_data.get("provenance", {}).get("confidence"),
            "freshness": self.compute_freshness(
                visibility_data.get("provenance", {}).get("timestamp"),
                now_ts,
            ),
        }
        self.victim_confidence_summary = {
            "value": dict(self.victim_confidence_summary),
            "confidence": victim_data.get("catalog_provenance", {}).get("confidence"),
            "freshness": self.compute_freshness(
                victim_data.get("catalog_provenance", {}).get("timestamp"),
                now_ts,
            ),
        }
        self.uav_team_summary = {
            "value": dict(self.uav_team_summary),
            "confidence": None,
            "freshness": self.compute_freshness(
                uav_data.get("provenance", {}).get("timestamp"),
                now_ts,
            ),
        }
        self.firefighter_summary = {
            "value": dict(self.firefighter_summary),
            "confidence": None,
            "freshness": self.compute_freshness(
                firefighter_data.get("provenance", {}).get("timestamp"),
                now_ts,
            ),
        }
        comm_conf = self.communication_reliability_summary.get("shared_knowledge_sync_quality")
        self.communication_reliability_summary = {
            "value": dict(self.communication_reliability_summary),
            "confidence": comm_conf,
            "freshness": self.compute_freshness(
                communication_data.get("provenance", {}).get("timestamp"),
                now_ts,
            ),
        }

        if active_alerts is not None:
            self.active_alerts = list(active_alerts)
        if mission_mode is not None:
            self.mission_mode = mission_mode
        if active_adaptation_state is not None:
            self.active_adaptation_state = active_adaptation_state

        self.layers = {
            "fire_state_summary": dict(self.fire_state_summary),
            "fire_belief_summary": dict(self.fire_belief_summary),
            "visibility_summary": dict(self.visibility_summary),
            "uncertainty_summary": dict(self.uncertainty_summary),
            "victim_confidence_summary": dict(self.victim_confidence_summary),
            "uav_team_summary": dict(self.uav_team_summary),
            "firefighter_summary": dict(self.firefighter_summary),
            "communication_reliability_summary": dict(self.communication_reliability_summary),
        }

        if timestamp is not None:
            self.provenance.timestamp = float(timestamp)
        if source is not None:
            self.provenance.source = source
        # Surface confidence/freshness metadata in one place for consumers.
        self.provenance.confidence = self.communication_reliability_summary.get(
            "confidence"
        )

    def get_dashboard_summary(self) -> dict[str, Any]:
        """Return a simple summary suitable for dashboard builders later."""
        return {
            "what_is_believed": {
                "fire": dict(self.fire_belief_summary),
                "visibility": dict(self.visibility_summary),
                "victims": dict(self.victim_confidence_summary),
                "uav_team": dict(self.uav_team_summary),
                "firefighters": dict(self.firefighter_summary),
                "communication": dict(self.communication_reliability_summary),
            },
            "how_certain_it_is": {
                "global_confidence": self.provenance.confidence,
                "fire_confidence_map": self.fire_belief_summary.get("value", {}).get(
                    "fire_confidence_map", {}
                ),
                "sync_quality": self.communication_reliability_summary.get("confidence"),
            },
            "how_fresh_it_is": {
                "global_timestamp": self.provenance.timestamp,
                "fire_last_observed": self.fire_belief_summary.get("value", {}).get(
                    "last_observed_fire_time", {}
                ),
                "visibility_freshness": self.uncertainty_summary.get("value", {}).get(
                    "information_freshness_map", {}
                ),
            },
            "active_alerts": list(self.active_alerts),
            "mission_mode": self.mission_mode,
            "active_adaptation_state": self.active_adaptation_state,
        }

    def snapshot(self) -> dict[str, Any]:
        """Read-only fused knowledge snapshot (no side effects)."""
        return {
            "step_index": self.step_index,
            "provenance": asdict(self.provenance),
            "fire_state_summary": dict(self.fire_state_summary),
            "fire_belief_summary": dict(self.fire_belief_summary),
            "visibility_summary": dict(self.visibility_summary),
            "uncertainty_summary": dict(self.uncertainty_summary),
            "victim_confidence_summary": dict(self.victim_confidence_summary),
            "uav_team_summary": dict(self.uav_team_summary),
            "firefighter_summary": dict(self.firefighter_summary),
            "communication_reliability_summary": dict(self.communication_reliability_summary),
            "active_alerts": list(self.active_alerts),
            "mission_mode": self.mission_mode,
            "active_adaptation_state": self.active_adaptation_state,
            "layers": dict(self.layers),
        }
