"""Managing system: fail-safe mode/state objects.

Explicit fail-safe mode and reason types plus FailSafeState for
execution-layer tracking. No simulator integration in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FailSafeMode(str, Enum):
    """Operational fail-safe mode."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    SAFETY_FIRST = "safety_first"
    EMERGENCY = "emergency"
    INFORMATION_RECOVERY = "information_recovery"


class FailSafeReason(str, Enum):
    """Why fail-safe mode was entered or reinforced."""

    CRITICAL_BATTERY = "critical_battery"
    EXTREME_DRIFT = "extreme_drift"
    NO_FEASIBLE_PATH = "no_feasible_path"
    COLLISION_RISK = "collision_risk"
    CRITICAL_COMMUNICATION = "critical_communication"
    RESCUE_ROUTE_UNSAFE = "rescue_route_unsafe"
    VICTIM_UNCERTAINTY = "victim_uncertainty"
    GLOBAL_UNCERTAINTY = "global_uncertainty"
    INFORMATION_INSUFFICIENT = "information_insufficient"
    SEARCH_MODE_REQUIRED = "search_mode_required"
    INSTABILITY = "instability"
    MANUAL_HOLD = "manual_hold"


@dataclass
class FailSafeState:
    """Current fail-safe posture for one scope (e.g. fleet or entity set)."""

    mode: FailSafeMode
    active_reasons: tuple[FailSafeReason, ...] = ()
    affected_entities: tuple[str, ...] = ()
    started_at: float = 0.0
    last_updated: float = 0.0
    confidence: float = 0.0
    recovery_score: float = 0.0
    explanation: str = ""
    previous_mode: FailSafeMode | None = None


def failsafe_state_to_dict(state: FailSafeState) -> dict[str, Any]:
    return {
        "mode": state.mode.value,
        "active_reasons": [reason.value for reason in state.active_reasons],
        "affected_entities": list(state.affected_entities),
        "started_at": state.started_at,
        "last_updated": state.last_updated,
        "confidence": state.confidence,
        "recovery_score": state.recovery_score,
        "explanation": state.explanation,
        "previous_mode": state.previous_mode.value if state.previous_mode else None,
    }


def normalize_mode(value: FailSafeMode | str) -> FailSafeMode:
    return _normalize_enum(value, FailSafeMode)


def normalize_reason(value: FailSafeReason | str) -> FailSafeReason:
    return _normalize_enum(value, FailSafeReason)


def _normalize_enum(value: FailSafeMode | FailSafeReason | str, enum_cls: type) -> Any:
    if isinstance(value, enum_cls):
        return value
    if not isinstance(value, str):
        raise TypeError(f"expected {enum_cls.__name__} or str, got {type(value).__name__}")
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    for member in enum_cls:
        if member.value == key or member.name.lower() == key:
            return member
    raise ValueError(f"unknown {enum_cls.__name__}: {value!r}")
