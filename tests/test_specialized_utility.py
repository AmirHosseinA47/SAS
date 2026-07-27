"""Rescue, communication, and fail-safe utility."""

from src_extension.adaptation.adaptation_option_objects import (
    FailSafeAdaptationOption,
    MissionAdaptationOption,
    RescueAdaptationOption,
    Scope,
)
from src_extension.planning.utility_evaluation import UtilityEvaluation


def _rescue_option(
    option_id: str,
    option_type: str,
    parameters: dict,
    *,
    confidence: float = 0.15,
) -> RescueAdaptationOption:
    return RescueAdaptationOption(
        option_id=option_id,
        option_type=option_type,
        target_entity="uav-1",
        parameters=dict(parameters),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=confidence,
        scope=Scope.rescue,
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def _comm_option(
    option_id: str,
    parameters: dict,
    *,
    confidence: float = 1.0,
) -> MissionAdaptationOption:
    return MissionAdaptationOption(
        option_id=option_id,
        option_type="communication_relay",
        target_entity="net",
        parameters=dict(parameters),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=confidence,
        scope=Scope["global"],
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def _failsafe_option(
    option_id: str,
    option_type: str,
    parameters: dict,
    *,
    confidence: float = 1.0,
) -> FailSafeAdaptationOption:
    return FailSafeAdaptationOption(
        option_id=option_id,
        option_type=option_type,
        target_entity="uav-1",
        parameters=dict(parameters),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=confidence,
        scope=Scope.system,
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def _local_path_option(option_id: str, parameters: dict, *, confidence: float) -> MissionAdaptationOption:
    return MissionAdaptationOption(
        option_id=option_id,
        option_type="path_adjust",
        target_entity="uav-1",
        parameters=dict(parameters),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=confidence,
        scope=Scope.local,
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def _score(opt: object, mode: str = "normal_monitoring_mode") -> float:
    return UtilityEvaluation(default_mode=mode).evaluate_option(opt, mode=mode).total_utility


def test_rescue_confirmation_beats_dispatch_low_confidence_high_uncertainty() -> None:
    base = {
        "victim_priority": 0.75,
        "support_quality": 0.65,
        "expected_delay": 0.25,
        "route_risk": 0.35,
        "victim_uncertainty": 0.88,
        "communication_risk": 0.22,
        "uncertainty_level": 0.93,
    }
    confirm = _rescue_option("rc", "rescue_confirm_step", base, confidence=0.15)
    dispatch = _rescue_option("rd", "rescue_dispatch_step", base, confidence=0.15)
    assert _score(confirm) > _score(dispatch)


def test_relay_communication_scores_higher_with_low_delivery_confidence() -> None:
    base = {
        "delivery_quality": 0.5,
        "critical_support": 0.25,
        "sync_quality": 0.45,
        "relay_cost": 0.35,
        "delay_cost": 0.12,
    }
    low_dc = _comm_option("c0", {**base, "delivery_confidence": 0.12})
    high_dc = _comm_option("c1", {**base, "delivery_confidence": 0.95})
    assert _score(low_dc) > _score(high_dc)


def test_return_to_base_scores_higher_with_high_energy_failure_risk() -> None:
    params = {
        "mission_value": 0.45,
        "stability_bonus": 0.55,
        "energy_failure_risk": 0.92,
        "support_loss": 0.12,
    }
    rtb = _failsafe_option("rtb", "failsafe_return_to_base", params)
    idle = _failsafe_option("idle", "failsafe_hold_idle", params)
    assert _score(rtb) > _score(idle)


def test_failsafe_search_scores_higher_with_high_recovery_value() -> None:
    low_r = _failsafe_option(
        "s0",
        "failsafe_search_patrol",
        {
            "mission_value": 0.4,
            "stability_bonus": 0.5,
            "energy_failure_risk": 0.2,
            "support_loss": 0.1,
            "recovery_value": 0.05,
            "search_mode": True,
        },
    )
    high_r = _failsafe_option(
        "s1",
        "failsafe_search_patrol",
        {
            "mission_value": 0.4,
            "stability_bonus": 0.5,
            "energy_failure_risk": 0.2,
            "support_loss": 0.1,
            "recovery_value": 0.95,
            "search_mode": True,
        },
    )
    assert _score(high_r) > _score(low_r)


def test_confidence_adjustment_lowers_weak_confidence_score() -> None:
    params = {
        "expected_info_gain": 0.55,
        "belief_gain": 0.35,
        "recovery_value": 0.35,
        "task_support": 0.45,
        "overlap_penalty": 0.1,
        "collision_risk": 0.1,
        "smoke_penalty": 0.1,
        "battery_cost": 0.1,
        "drift_penalty": 0.1,
        "stability_bonus": 0.5,
    }
    strong = _local_path_option("lc0", params, confidence=1.0)
    weak = _local_path_option("lc1", params, confidence=0.12)
    assert _score(strong) > _score(weak)
