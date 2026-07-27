"""Fail-safe mode objects and safety checker tests."""

from __future__ import annotations

import pytest

from src_extension.execution.failsafe_modes import (
    FailSafeMode,
    FailSafeReason,
    FailSafeState,
    failsafe_state_to_dict,
    normalize_mode,
    normalize_reason,
)
from src_extension.execution.safety_checker import SafetyChecker


def test_failsafe_state_serializes_to_dict() -> None:
    state = FailSafeState(
        mode=FailSafeMode.SAFETY_FIRST,
        active_reasons=(FailSafeReason.COLLISION_RISK,),
        affected_entities=("uav_0",),
        started_at=1.0,
        last_updated=2.0,
        confidence=0.8,
        recovery_score=0.4,
        explanation="mode=safety_first; reasons=collision_risk",
        previous_mode=FailSafeMode.DEGRADED,
    )

    payload = failsafe_state_to_dict(state)

    assert payload == {
        "mode": "safety_first",
        "active_reasons": ["collision_risk"],
        "affected_entities": ["uav_0"],
        "started_at": 1.0,
        "last_updated": 2.0,
        "confidence": 0.8,
        "recovery_score": 0.4,
        "explanation": "mode=safety_first; reasons=collision_risk",
        "previous_mode": "degraded",
    }


def test_normalize_mode_and_reason_handle_strings_safely() -> None:
    assert normalize_mode("safety-first") == FailSafeMode.SAFETY_FIRST
    assert normalize_mode(FailSafeMode.EMERGENCY) == FailSafeMode.EMERGENCY
    assert normalize_reason("SEARCH_MODE_REQUIRED") == FailSafeReason.SEARCH_MODE_REQUIRED
    assert normalize_reason(FailSafeReason.CRITICAL_BATTERY) == FailSafeReason.CRITICAL_BATTERY

    with pytest.raises(ValueError):
        normalize_mode("unknown_mode")
    with pytest.raises(TypeError):
        normalize_reason(42)  # type: ignore[arg-type]


def test_safety_checker_detects_information_insufficient_from_trigger() -> None:
    checker = SafetyChecker()
    analysis_snapshot = {
        "triggers": (
            {"trigger_type": "INFORMATION_INSUFFICIENT", "confidence": 0.8},
        )
    }

    reasons = checker.extract_fail_safe_reasons(analysis_snapshot=analysis_snapshot)

    assert FailSafeReason.INFORMATION_INSUFFICIENT.value in reasons


def test_safety_checker_classifies_search_mode_required_as_information_recovery() -> None:
    checker = SafetyChecker()
    reasons = (FailSafeReason.SEARCH_MODE_REQUIRED.value,)

    mode = checker.classify_mode(reasons)

    assert mode == FailSafeMode.INFORMATION_RECOVERY.value


def test_safety_checker_classifies_collision_and_battery_modes() -> None:
    checker = SafetyChecker()

    collision_mode = checker.classify_mode((FailSafeReason.COLLISION_RISK.value,))
    assert collision_mode == FailSafeMode.SAFETY_FIRST.value

    emergency_mode = checker.classify_mode(
        (
            FailSafeReason.CRITICAL_BATTERY.value,
            FailSafeReason.COLLISION_RISK.value,
        )
    )
    assert emergency_mode == FailSafeMode.EMERGENCY.value


def test_should_override_utility_for_emergency_and_information_recovery() -> None:
    checker = SafetyChecker()

    assert checker.should_override_utility((), FailSafeMode.EMERGENCY.value) is True
    assert (
        checker.should_override_utility(
            (FailSafeReason.INFORMATION_INSUFFICIENT.value,),
            FailSafeMode.INFORMATION_RECOVERY.value,
        )
        is True
    )
