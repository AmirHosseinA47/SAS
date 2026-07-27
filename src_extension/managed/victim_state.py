"""Managed system: victim operational state in the domain.

Managed system — victim operational state: presence, location, detection,
and observable/rescue-related world status. A separate victim manager in
the managing layer reasons about victims; victim state here is domain-side
data the mission operates on, not adaptation logic.

TODO: Integrate reads/writes with simulator or shared stores; managing monitors
consume snapshots—do not embed analysis here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VictimState:
    """Operational placeholder: victim as an entity in the operational world."""

    victim_id: str
    # TODO: Define confirmation / tracking substates explicitly.
    status: str = "unknown"
    last_known_position: tuple[float, float] | None = None
    rescue_assigned: bool = False
    firefighter_id: str | None = None
    confirmed: bool = False
    confidence: float = 0.4
    needs_confirmation: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)
