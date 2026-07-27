"""Managed system: abstract firefighter unit operational state.

Managed system — abstract firefighter units: location, assignment, route
progress, rescue progress, availability—the actual operational picture.
Rescue planning and assignment logic live in the managing system; this
module only holds state those decisions update when applied.

TODO: Sync operational fields with managing ``knowledge.firefighter_model`` via
execution paths, not by embedding planners here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FirefighterOperationalState:
    """Operational placeholder: per-unit fields as in the mission world."""

    unit_id: str
    position: tuple[float, float] | None = None
    availability: str = "unknown"
    assignment_state: str = "unassigned"
    route_state: str = "idle"
    eta_seconds: float | None = None
    rescue_progress: str = "none"
    route_risk_summary: str = "unknown"
    extra: dict[str, Any] = field(default_factory=dict)
