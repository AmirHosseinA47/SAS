"""Managing system: planner outputs.

These dataclasses represent adaptation decisions what should change for
 execution to apply to managed entities. They are not:

- operational telemetry from the managed system
- execution receipts or acknowledgements from the simulator
- triggers (see ``analysis.trigger_objects``)

TODO: Narrow ``payload`` / action dicts into typed enums/records over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MissionDecision:
    """Planned change: high-level mission/role allocation (awaiting execution)."""

    decision_id: str
    uav_assignments: dict[str, str] = field(default_factory=dict)
    task_assignments: dict[str, str] = field(default_factory=dict)
    mission_mode: str = ""
    relay_assignments: dict[str, str] = field(default_factory=dict)
    recall_orders: tuple[str, ...] = ()
    confidence_score: float = 0.0
    uncertainty_context: dict[str, Any] = field(default_factory=dict)
    comparison_summary: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    selected_option_id: str = ""
    notes: str = ""


@dataclass(frozen=True)
class PathDecision:
    """Planned change: path-level intent for one or more UAVs (awaiting execution)."""

    decision_id: str
    uav_id: str = ""
    selected_option_id: str = ""
    next_action: str = ""
    path_segment: tuple[tuple[float, float], ...] = ()
    waypoints_by_uav: dict[str, tuple[tuple[float, float], ...]] = field(default_factory=dict)
    confidence_score: float = 0.0
    uncertainty_context: dict[str, Any] = field(default_factory=dict)
    comparison_summary: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    escalation_request: dict[str, Any] | None = None


@dataclass(frozen=True)
class RescueDecision:
    """Planned change: simplified rescue coordination (awaiting execution)."""

    decision_id: str
    selected_option_id: str = ""
    rescue_action: str = ""
    victim_id: str = ""
    firefighter_id: str = ""
    route_choice: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    uncertainty_context: dict[str, Any] = field(default_factory=dict)
    comparison_summary: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""


@dataclass(frozen=True)
class FailSafeDecision:
    """Planned change: conservative/emergency adaptation (awaiting execution)."""

    decision_id: str
    selected_option_id: str = ""
    fail_safe_action: str = ""
    search_mode_active: bool = False
    target_region: str = ""
    mission_mode: str = ""
    actions: tuple[dict[str, Any], ...] = ()
    confidence_score: float = 0.0
    uncertainty_context: dict[str, Any] = field(default_factory=dict)
    comparison_summary: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
