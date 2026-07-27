"""Fail-safe planner, mode manager, and fallback strategy tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src_extension.adaptation.adaptation_results import FailSafeAdaptationSpace
from src_extension.execution.failsafe_modes import FailSafeMode
from src_extension.execution.fallback_strategy import FallbackStrategyLibrary
from src_extension.execution.mode_manager import ModeManager
from src_extension.execution.safety_checker import SafetyChecker
from src_extension.planning.fail_safe_planner import FailSafePlanner


def _search_trigger_analysis() -> dict[str, object]:
    return {"triggers": ({"trigger_type": "SEARCH_MODE_REQUIRED", "confidence": 0.8},)}


def _emergency_trigger_analysis() -> dict[str, object]:
    return {
        "triggers": (
            {"trigger_type": "CRITICAL_BATTERY"},
            {"trigger_type": "COLLISION_RISK"},
        )
    }


def test_fail_safe_planner_information_recovery_under_search_mode_required() -> None:
    planner = FailSafePlanner()
    decision = planner.plan(
        1,
        analysis_snapshot=_search_trigger_analysis(),
        fail_safe_space=FailSafeAdaptationSpace(options=[]),
        timestamp=1.0,
    )

    assert decision is not None
    assert decision.search_mode_active is True
    assert decision.mission_mode == "information_recovery"
    assert decision.fail_safe_action in {
        "activate_search_mode",
        "search_mode",
        "information_recovery",
        "move_to_last_known_fire_region",
        "explore_high_uncertainty_regions",
    }
    assert decision.uncertainty_context.get("fail_safe_mode") == FailSafeMode.INFORMATION_RECOVERY.value


def test_fail_safe_planner_emergency_prefers_safe_hold_or_return_to_base() -> None:
    planner = FailSafePlanner()
    decision = planner.plan(
        2,
        analysis_snapshot=_emergency_trigger_analysis(),
        fail_safe_space=FailSafeAdaptationSpace(options=[]),
        timestamp=2.0,
    )

    assert decision is not None
    assert decision.fail_safe_action in {"safe_hold", "return_to_base"}
    assert decision.uncertainty_context.get("fail_safe_mode") == FailSafeMode.EMERGENCY.value


def test_mode_manager_enters_information_recovery_from_search_mode_required() -> None:
    manager = ModeManager(SafetyChecker())

    state = manager.update(
        analysis_snapshot=_search_trigger_analysis(),
        timestamp=1.0,
    )

    assert state.mode == FailSafeMode.INFORMATION_RECOVERY
    assert manager.is_information_recovery_active() is True


def test_mode_manager_returns_to_normal_after_recovery() -> None:
    manager = ModeManager(SafetyChecker())

    manager.update(analysis_snapshot=_search_trigger_analysis(), timestamp=1.0)
    assert manager.current_state.mode == FailSafeMode.INFORMATION_RECOVERY

    recovery_context = {
        "triggers": (),
        "information_sufficiency_score": 0.7,
    }
    state = manager.update(analysis_snapshot=recovery_context, timestamp=2.0)

    assert state.mode == FailSafeMode.NORMAL
    assert not state.active_reasons
    assert manager.should_return_to_normal(analysis_snapshot=recovery_context) is False


@pytest.mark.parametrize(
    ("mode", "expected_actions"),
    [
        (FailSafeMode.NORMAL, {"maintain_current_config"}),
        (FailSafeMode.DEGRADED, {"reduce_mission_scope", "critical_tasks_only"}),
        (
            FailSafeMode.SAFETY_FIRST,
            {"safe_hold", "retreat_to_safe_region", "collision_avoidance_override"},
        ),
        (
            FailSafeMode.EMERGENCY,
            {"safe_hold", "return_to_base", "suspend_non_critical_tasks"},
        ),
        (
            FailSafeMode.INFORMATION_RECOVERY,
            {
                "activate_search_mode",
                "move_to_last_known_fire_region",
                "explore_high_uncertainty_regions",
            },
        ),
    ],
)
def test_fallback_strategy_library_returns_predefined_strategies(
    mode: FailSafeMode,
    expected_actions: set[str],
) -> None:
    library = FallbackStrategyLibrary()
    strategies = library.strategies_for_mode(mode.value, timestamp=1.0)

    assert strategies
    assert {strategy.action for strategy in strategies} == expected_actions
