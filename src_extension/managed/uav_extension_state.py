"""Managed system: operational UAV-related state.

Managed system — UAV operational agents: holds domain-side fields for a
UAV as it exists in the mission (like identifier, executed role/path
reflection as operational facts). This is not where adaptation or global
utility is computed; the managing system reasons about changes, then those
decisions are applied to operational entities elsewhere.

TODO: Align operational fields with simulator UAV state and managing-side
``knowledge.uav_resource_model`` / execution adapters without embedding policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UAVExtensionState:
    """Operational placeholder: per-UAV mission facts as lived in the environment."""

    uav_id: str
    # Operational role as executed in the world (not the reasoning that chose it).
    role: str | None = None
    assigned_task: str | None = None
    battery_level: float = 100.0
    battery_status: str = "normal"
    position: tuple[float, float] | None = None
    communication_status: str = "normal"
    drift_level: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
