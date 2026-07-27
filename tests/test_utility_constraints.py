"""Utility hard-constraint / feasibility checks."""

from src_extension.adaptation.adaptation_option_objects import (
    LocalAdaptationOption,
    MissionAdaptationOption,
    RescueAdaptationOption,
    Scope,
)
from src_extension.planning.utility_evaluation import UtilityEvaluation


def _local(**params: object) -> LocalAdaptationOption:
    return LocalAdaptationOption(
        option_id="loc-1",
        option_type="path_adjust",
        target_entity="uav-1",
        parameters=dict(params),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=1.0,
        scope=Scope.local,
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def _global(parameters: dict) -> MissionAdaptationOption:
    return MissionAdaptationOption(
        option_id="g-1",
        option_type="mission_plan",
        target_entity="fleet",
        parameters=dict(parameters),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=1.0,
        scope=Scope["global"],
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def _rescue(**params: object) -> RescueAdaptationOption:
    return RescueAdaptationOption(
        option_id="r-1",
        option_type="rescue_dispatch",
        target_entity="uav-1",
        parameters=dict(params),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=1.0,
        scope=Scope["rescue"],
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def _comm(**params: object) -> MissionAdaptationOption:
    return MissionAdaptationOption(
        option_id="c-1",
        option_type="communication_relay",
        target_entity="uav-1",
        parameters=dict(params),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=1.0,
        scope=Scope["global"],
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def test_local_hard_collision_violation_infeasible() -> None:
    ev = UtilityEvaluation().evaluate_option(
        _local(
            expected_info_gain=0.5,
            hard_collision_violation=True,
        )
    )
    assert ev.feasible is False
    assert "hard_collision_constraint" in ev.constraint_violations
    assert ev.total_utility < -999_000.0
    assert "Infeasible" in ev.explanation_summary


def test_global_projected_battery_below_threshold_infeasible() -> None:
    base = {
        "fire_contribution": 0.35,
        "victim_contribution": 0.25,
        "communication_contribution": 0.25,
        "uncertainty_reduction": 0.25,
        "information_recovery": 0.25,
        "collision_risk": 0.08,
        "battery_cost": 0.08,
        "drift_risk": 0.05,
        "switching_cost": 0.05,
        "projected_battery_after_option": 10.0,
    }
    ev = UtilityEvaluation().evaluate_option(_global(base))
    assert ev.feasible is False
    assert "battery_below_critical" in ev.constraint_violations
    assert ev.total_utility < -999_000.0


def test_rescue_route_feasible_false_infeasible() -> None:
    ev = UtilityEvaluation().evaluate_option(
        _rescue(
            victim_priority=0.6,
            route_risk=0.2,
            route_feasible=False,
        )
    )
    assert ev.feasible is False
    assert "rescue_route_infeasible" in ev.constraint_violations


def test_communication_critical_requires_delivery_infeasible() -> None:
    ev = UtilityEvaluation().evaluate_option(
        _comm(
            delivery_quality=0.5,
            critical_support=0.4,
            sync_quality=0.5,
            relay_cost=0.1,
            delay_cost=0.1,
            requires_critical_communication=True,
            delivery_confidence=0.1,
        )
    )
    assert ev.feasible is False
    assert "critical_communication_unavailable" in ev.constraint_violations


def test_fail_safe_mode_bypasses_critical_communication_violation() -> None:
    ev = UtilityEvaluation().evaluate_option(
        _comm(
            delivery_quality=0.5,
            critical_support=0.4,
            sync_quality=0.5,
            relay_cost=0.1,
            delay_cost=0.1,
            requires_critical_communication=True,
            delivery_confidence=0.1,
            fail_safe_mode=True,
        )
    )
    assert ev.feasible is True
    assert ev.constraint_violations == ()
