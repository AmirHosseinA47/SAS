"""Managing system: UAV resource and role runtime knowledge.

Per-UAV belief about role, task, battery, comms, drift, local risk, plan
reliability, and stability counters—supporting distributed coordination without
embedding planning or execution.

TODO: Refresh from structured observations; apply **time decay** to stale
role/task effectiveness signals; fuse multi-source **confidence**.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .knowledge_utils import clamp01, compute_age, validate_metadata
from .runtime_model_common import Confidence, KnowledgeProvenance, Timestamp


@dataclass
class UAVResourceRuntimeState:
    """Per-UAV typed placeholders (Step 4)."""

    uav_id: str
    current_position: tuple[float, ...] | None = None
    current_role: str | None = None
    assigned_task: str | None = None
    battery_level: float | None = None
    battery_status: str | None = None
    communication_status: str | None = None
    drift_level: float | None = None
    path_feasibility_status: str | None = None
    local_risk_status: str | None = None
    task_effectiveness_score: float | None = None
    role_stability_timer: float = 0.0
    role_switch_count: int = 0
    task_commitment_age: float = 0.0
    predicted_remaining_useful_time: float | None = None
    local_plan_reliability: Confidence | None = None
    last_update_time: Timestamp | None = None
    provenance: KnowledgeProvenance = field(default_factory=KnowledgeProvenance)


@dataclass
class UAVResourceModel:
    """Runtime knowledge: per-UAV resource/role **beliefs** (not execution).

    This model stores only knowledge-layer state used by higher-level reasoning.
    It does not implement adaptation policy or mission execution.
    """

    step_index: int = 0
    by_uav_id: dict[str, UAVResourceRuntimeState] = field(default_factory=dict)
    _last_battery_update: dict[str, tuple[float, float]] = field(default_factory=dict)

    def update(self, step_index: int) -> None:
        """TODO: Refresh per-UAV state from observations; update stability timers."""
        self.step_index = step_index

    def _get_or_create(self, uav_id: str) -> UAVResourceRuntimeState:
        state = self.by_uav_id.get(uav_id)
        if state is None:
            state = UAVResourceRuntimeState(uav_id=uav_id)
            self.by_uav_id[uav_id] = state
        return state

    def update_uav_state(
        self,
        uav_id: str,
        timestamp: Timestamp,
        current_position: tuple[float, ...] | None = None,
        current_role: str | None = None,
        assigned_task: str | None = None,
        battery_level: float | None = None,
        battery_status: str | None = None,
        communication_status: str | None = None,
        drift_level: float | None = None,
        path_feasibility_status: str | None = None,
        local_risk_status: str | None = None,
        task_effectiveness_score: float | None = None,
        task_commitment_age: float | None = None,
        predicted_remaining_useful_time: float | None = None,
        local_plan_reliability: Confidence | None = None,
        source: str | None = None,
    ) -> None:
        """Update any subset of UAV runtime fields from observations."""
        meta_conf = (
            local_plan_reliability
            if local_plan_reliability is not None
            else (0.8 if battery_level is not None else 0.6)
        )
        ts, _, src = validate_metadata(
            timestamp=timestamp,
            confidence=meta_conf,
            source=source or "uav_runtime",
        )
        state = self._get_or_create(uav_id)
        last_time = state.last_update_time if state.last_update_time is not None else ts
        dt = max(0.0, ts - float(last_time))
        state.role_stability_timer += dt
        if current_position is not None:
            state.current_position = current_position
        if current_role is not None:
            self.update_role(uav_id=uav_id, new_role=current_role, timestamp=ts, source=src)
            state = self._get_or_create(uav_id)
        if assigned_task is not None:
            state.assigned_task = assigned_task
            state.task_commitment_age = 0.0
        if battery_level is not None:
            self.update_battery(
                uav_id=uav_id,
                battery_level=battery_level,
                timestamp=ts,
                source=src,
                confidence=0.9,
            )
            state = self._get_or_create(uav_id)
        if battery_status is not None:
            state.battery_status = battery_status
        if communication_status is not None:
            state.communication_status = communication_status
        if drift_level is not None:
            self.update_drift(
                uav_id=uav_id,
                drift_level=drift_level,
                timestamp=ts,
                source=src,
                confidence=0.8,
            )
            state = self._get_or_create(uav_id)
        if path_feasibility_status is not None:
            state.path_feasibility_status = path_feasibility_status
        if local_risk_status is not None:
            state.local_risk_status = local_risk_status
        if task_effectiveness_score is not None:
            state.task_effectiveness_score = task_effectiveness_score
        if task_commitment_age is not None:
            state.task_commitment_age = max(0.0, float(task_commitment_age))
        else:
            state.task_commitment_age += dt
        if predicted_remaining_useful_time is not None:
            state.predicted_remaining_useful_time = max(0.0, float(predicted_remaining_useful_time))
        if local_plan_reliability is not None:
            state.local_plan_reliability = max(0.0, min(1.0, float(local_plan_reliability)))
        state.last_update_time = ts
        state.provenance.source = src
        state.provenance.timestamp = ts
        state.provenance.confidence = state.local_plan_reliability

    def update_role(
        self,
        uav_id: str,
        new_role: str,
        timestamp: Timestamp,
        source: str = "uav_runtime",
        confidence: float = 0.8,
    ) -> None:
        """Update role; role switch count/timer change only when role changes."""
        ts, _, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        state = self._get_or_create(uav_id)
        if state.current_role != new_role:
            if state.current_role is not None:
                state.role_switch_count += 1
            state.current_role = new_role
            state.role_stability_timer = 0.0
        state.last_update_time = ts
        state.provenance.timestamp = ts
        state.provenance.source = src
        state.provenance.confidence = clamp01(confidence)

    def update_battery(
        self,
        uav_id: str,
        battery_level: float,
        timestamp: Timestamp,
        source: str = "uav_runtime",
        confidence: float = 0.9,
    ) -> None:
        """Update battery level and derived battery status."""
        ts, conf, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        state = self._get_or_create(uav_id)
        level = max(0.0, min(100.0, float(battery_level)))
        prev = self._last_battery_update.get(uav_id)
        state.battery_level = level
        if level < 20.0:
            state.battery_status = "critical"
        elif level < 50.0:
            state.battery_status = "low"
        else:
            state.battery_status = "nominal"
        if prev is not None:
            prev_level, prev_ts = prev
            dt = max(0.0, ts - prev_ts)
            if dt > 0.0:
                drain_per_time = max(0.0, (prev_level - level) / dt)
                if drain_per_time > 0.0:
                    state.predicted_remaining_useful_time = max(0.0, level / drain_per_time)
        self._last_battery_update[uav_id] = (level, ts)
        state.last_update_time = ts
        state.provenance.timestamp = ts
        state.provenance.source = src
        state.provenance.confidence = conf

    def update_drift(
        self,
        uav_id: str,
        drift_level: float,
        timestamp: Timestamp,
        source: str = "uav_runtime",
        confidence: float = 0.8,
    ) -> None:
        """Update drift estimate and lightweight risk/status hint."""
        ts, conf, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        state = self._get_or_create(uav_id)
        drift = max(0.0, float(drift_level))
        state.drift_level = drift
        if drift > 0.7:
            state.local_risk_status = "high_drift"
        elif drift > 0.3:
            state.local_risk_status = "moderate_drift"
        elif state.local_risk_status is None:
            state.local_risk_status = "low_drift"
        state.last_update_time = ts
        state.provenance.timestamp = ts
        state.provenance.source = src
        state.provenance.confidence = conf

    def apply_time_decay(self, current_time: float) -> None:
        """Decay plan reliability and predicted useful time over time."""
        now = float(current_time)
        for state in self.by_uav_id.values():
            if state.last_update_time is None:
                continue
            age = compute_age(now, state.last_update_time)
            if age <= 0.0:
                continue
            if state.local_plan_reliability is not None:
                state.local_plan_reliability = clamp01(
                    state.local_plan_reliability * max(0.0, 1.0 - (0.02 * age))
                )
            if state.predicted_remaining_useful_time is not None:
                state.predicted_remaining_useful_time = max(
                    0.0,
                    state.predicted_remaining_useful_time - age,
                )
            state.provenance.confidence = state.local_plan_reliability

    def snapshot(self) -> dict[str, Any]:
        """Read-only knowledge snapshot (no side effects)."""
        return {
            "step_index": self.step_index,
            "by_uav_id": {uid: asdict(st) for uid, st in self.by_uav_id.items()},
        }
