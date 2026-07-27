"""Managing system: Firefighter operational runtime knowledge.

Structured belief about ground units: availability, assignment, route and
rescue progress. Mirrors managed operational state only when synchronized;
remains knowledge, not a planner..

TODO: Sync from execution feedback; stamp **provenance** and handle **stale**
updates with decay rules later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .knowledge_utils import clamp01, compute_age, validate_metadata
from .runtime_model_common import Confidence, KnowledgeProvenance, Timestamp


@dataclass
class FirefighterUnitRuntimeState:
    """Per-unit typed placeholders (Step 4)."""

    unit_id: str
    current_position: tuple[float, ...] | None = None
    target_position: tuple[float, ...] | None = None
    availability_status: str | None = None
    current_assignment: str | None = None
    target_victim: str | None = None
    operational_status: str | None = None
    is_dead: bool = False
    is_assigned: bool = False
    route_blocked: bool = False
    route_status: str | None = None
    route_risk_score: float | None = None
    route_feasibility_confidence: Confidence | None = None
    eta: Timestamp | None = None
    rescue_progress_status: str | None = None
    last_update_time: Timestamp | None = None
    provenance: KnowledgeProvenance = field(default_factory=KnowledgeProvenance)


@dataclass
class FirefighterModel:
    """Runtime knowledge: aggregate firefighter **picture** (not planning).

    Stores unit-level status used by adaptation reasoning. No planner/executor
    behavior is implemented here.
    """

    step_index: int = 0
    units: dict[str, FirefighterUnitRuntimeState] = field(default_factory=dict)

    def update(self, step_index: int) -> None:
        """TODO: Merge managed/observed updates; drop or decay stale unit knowledge."""
        self.step_index = step_index

    def _get_or_create(self, unit_id: str) -> FirefighterUnitRuntimeState:
        unit = self.units.get(unit_id)
        if unit is None:
            unit = FirefighterUnitRuntimeState(unit_id=unit_id)
            self.units[unit_id] = unit
        return unit

    def update_unit_state(
        self,
        unit_id: str,
        timestamp: Timestamp,
        current_position: tuple[float, ...] | None = None,
        availability_status: str | None = None,
        current_assignment: str | None = None,
        target_victim: str | None = None,
        route_status: str | None = None,
        route_risk_score: float | None = None,
        route_feasibility_confidence: Confidence | None = None,
        eta: Timestamp | None = None,
        rescue_progress_status: str | None = None,
        source: str | None = None,
    ) -> None:
        """Update any subset of one firefighter unit knowledge record."""
        meta_conf = (
            route_feasibility_confidence
            if route_feasibility_confidence is not None
            else 0.8
        )
        ts, conf, src = validate_metadata(
            timestamp=timestamp,
            confidence=meta_conf,
            source=source or "firefighter_runtime",
        )
        unit = self._get_or_create(unit_id)
        if current_position is not None:
            unit.current_position = current_position
        if availability_status is not None:
            unit.availability_status = availability_status
        if current_assignment is not None:
            unit.current_assignment = current_assignment
        if target_victim is not None:
            unit.target_victim = target_victim
        if route_status is not None:
            unit.route_status = route_status
        if route_risk_score is not None:
            unit.route_risk_score = max(0.0, float(route_risk_score))
        if route_feasibility_confidence is not None:
            unit.route_feasibility_confidence = clamp01(route_feasibility_confidence)
        if eta is not None:
            unit.eta = float(eta)
        if rescue_progress_status is not None:
            unit.rescue_progress_status = rescue_progress_status
        unit.last_update_time = ts
        unit.provenance.timestamp = ts
        unit.provenance.confidence = unit.route_feasibility_confidence or conf
        unit.provenance.source = src

    def mirror_operational_state(
        self,
        unit_id: str,
        timestamp: Timestamp,
        *,
        dead: bool,
        assigned: bool,
        route_blocked: bool,
        operational_status: str,
        current_position: tuple[float, ...] | None,
        target_position: tuple[float, ...] | None,
        target_victim_id: str | None,
        availability_status: str,
        current_assignment: str | None,
        route_status: str,
        rescue_progress_status: str,
        route_risk_score: float,
        route_feasibility_confidence: Confidence,
        source: str = "marker_sync",
    ) -> None:
        """Mirror live marker/managed operational fields into runtime knowledge."""
        ts, conf, src = validate_metadata(
            timestamp=timestamp,
            confidence=route_feasibility_confidence,
            source=source,
        )
        unit = self._get_or_create(unit_id)
        unit.is_dead = bool(dead)
        unit.is_assigned = bool(assigned)
        unit.route_blocked = bool(route_blocked)
        unit.operational_status = str(operational_status or "")
        unit.current_position = current_position
        unit.target_position = target_position
        unit.availability_status = str(availability_status or "")
        unit.current_assignment = current_assignment
        unit.target_victim = target_victim_id
        unit.route_status = str(route_status or "")
        unit.rescue_progress_status = str(rescue_progress_status or "")
        unit.route_risk_score = max(0.0, float(route_risk_score))
        unit.route_feasibility_confidence = clamp01(route_feasibility_confidence)
        unit.last_update_time = ts
        unit.provenance.timestamp = ts
        unit.provenance.confidence = unit.route_feasibility_confidence
        unit.provenance.source = src

    def assign_to_victim(
        self,
        unit_id: str,
        victim_id: str,
        timestamp: Timestamp,
        source: str = "firefighter_runtime",
        confidence: float = 0.8,
    ) -> None:
        """Assign one unit to a victim in runtime knowledge state."""
        ts, conf, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        unit = self._get_or_create(unit_id)
        unit.current_assignment = "victim_rescue"
        unit.target_victim = victim_id
        unit.availability_status = "assigned"
        unit.last_update_time = ts
        unit.provenance.timestamp = ts
        unit.provenance.source = src
        unit.provenance.confidence = conf

    def update_route_status(
        self,
        unit_id: str,
        route_status: str,
        risk_score: float,
        feasibility_confidence: Confidence,
        timestamp: Timestamp,
        source: str = "firefighter_runtime",
    ) -> None:
        """Update route status/risk/feasibility for a unit."""
        ts, conf, src = validate_metadata(
            timestamp=timestamp,
            confidence=feasibility_confidence,
            source=source,
        )
        unit = self._get_or_create(unit_id)
        unit.route_status = route_status
        unit.route_risk_score = max(0.0, float(risk_score))
        unit.route_feasibility_confidence = clamp01(feasibility_confidence)
        unit.last_update_time = ts
        unit.provenance.timestamp = ts
        unit.provenance.confidence = unit.route_feasibility_confidence or conf
        unit.provenance.source = src

    def apply_time_decay(self, current_time: float) -> None:
        """Decay route feasibility confidence as route information gets older."""
        now = float(current_time)
        for unit in self.units.values():
            if unit.last_update_time is None or unit.route_feasibility_confidence is None:
                continue
            age = compute_age(now, unit.last_update_time)
            if age <= 0.0:
                continue
            unit.route_feasibility_confidence = clamp01(
                unit.route_feasibility_confidence * max(0.0, 1.0 - (0.02 * age))
            )
            unit.provenance.confidence = unit.route_feasibility_confidence

    def snapshot(self) -> dict[str, Any]:
        """Read-only knowledge snapshot (no side effects)."""
        return {
            "step_index": self.step_index,
            "units": {uid: asdict(st) for uid, st in self.units.items()},
        }
