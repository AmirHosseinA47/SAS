"""Local path utility evaluation."""

import pytest

from src_extension.adaptation.adaptation_option_objects import LocalAdaptationOption, Scope
from src_extension.planning.utility_evaluation import UtilityEvaluation


def _local_option(option_id: str, parameters: dict) -> LocalAdaptationOption:
    return LocalAdaptationOption(
        option_id=option_id,
        option_type="path_adjust",
        target_entity="uav-1",
        parameters=dict(parameters),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=1.0,
        scope=Scope.local,
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def _baseline_params() -> dict[str, float]:
    return {
        "expected_info_gain": 0.35,
        "belief_gain": 0.2,
        "recovery_value": 0.2,
        "task_support": 0.35,
        "overlap_penalty": 0.08,
        "collision_risk": 0.08,
        "smoke_penalty": 0.08,
        "battery_cost": 0.08,
        "drift_penalty": 0.08,
        "stability_bonus": 0.45,
    }


def _score(option: LocalAdaptationOption, mode: str = "safety_first_mode") -> float:
    return UtilityEvaluation(default_mode=mode).evaluate_option(option, mode=mode).total_utility


def test_high_information_gain_scores_higher() -> None:
    low = _local_option("low", {**_baseline_params(), "expected_info_gain": 0.05})
    high = _local_option("high", {**_baseline_params(), "expected_info_gain": 0.95})
    assert _score(high) > _score(low)


def test_high_collision_risk_lowers_score() -> None:
    safe = _local_option("safe", {**_baseline_params(), "collision_risk": 0.02})
    risky = _local_option("risky", {**_baseline_params(), "collision_risk": 0.98})
    assert _score(safe) > _score(risky)


def test_high_drift_penalty_lowers_score() -> None:
    low_drift = _local_option("a", {**_baseline_params(), "drift_penalty": 0.02})
    high_drift = _local_option("b", {**_baseline_params(), "drift_penalty": 0.98})
    assert _score(low_drift) > _score(high_drift)


def test_stability_bonus_increases_score() -> None:
    low_stab = _local_option("s0", {**_baseline_params(), "stability_bonus": 0.05})
    high_stab = _local_option("s1", {**_baseline_params(), "stability_bonus": 0.98})
    assert _score(high_stab) > _score(low_stab)


def test_recovery_scores_higher_under_information_recovery_mode() -> None:
    params = {**_baseline_params(), "recovery_value": 0.85, "expected_info_gain": 0.15}
    opt = _local_option("recovery", params)
    ue = UtilityEvaluation()
    s_normal = ue.evaluate_option(opt, mode="normal_monitoring_mode").total_utility
    s_ir = ue.evaluate_option(opt, mode="information_recovery_mode").total_utility
    assert s_ir > s_normal
