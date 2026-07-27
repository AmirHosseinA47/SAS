"""Global mission utility evaluation."""

from src_extension.adaptation.adaptation_option_objects import MissionAdaptationOption, Scope
from src_extension.planning.utility_evaluation import UtilityEvaluation


def _global_option(
    option_id: str,
    parameters: dict,
    *,
    option_type: str = "mission_plan",
) -> MissionAdaptationOption:
    return MissionAdaptationOption(
        option_id=option_id,
        option_type=option_type,
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


def _baseline_params() -> dict[str, float]:
    return {
        "fire_contribution": 0.35,
        "victim_contribution": 0.25,
        "communication_contribution": 0.25,
        "uncertainty_reduction": 0.25,
        "information_recovery": 0.25,
        "collision_risk": 0.08,
        "battery_cost": 0.08,
        "drift_risk": 0.05,
        "switching_cost": 0.05,
    }


def _eval(option: MissionAdaptationOption, mode: str = "safety_first_mode"):
    return UtilityEvaluation(default_mode=mode).evaluate_option(option, mode=mode)


def _score(option: MissionAdaptationOption, mode: str = "safety_first_mode") -> float:
    return _eval(option, mode).total_utility


def test_high_fire_contribution_improves_score() -> None:
    low = _global_option("f0", {**_baseline_params(), "fire_contribution": 0.02})
    high = _global_option("f1", {**_baseline_params(), "fire_contribution": 0.95})
    assert _score(high) > _score(low)


def test_high_uncertainty_reduction_improves_score() -> None:
    low = _global_option("u0", {**_baseline_params(), "uncertainty_reduction": 0.05})
    high = _global_option("u1", {**_baseline_params(), "uncertainty_reduction": 0.92})
    assert _score(high) > _score(low)


def test_high_information_recovery_improves_score() -> None:
    low = _global_option("i0", {**_baseline_params(), "information_recovery": 0.05})
    high = _global_option("i1", {**_baseline_params(), "information_recovery": 0.92})
    assert _score(high) > _score(low)


def test_high_switching_cost_lowers_score() -> None:
    low_sw = _global_option("s0", {**_baseline_params(), "switching_cost": 0.02})
    high_sw = _global_option("s1", {**_baseline_params(), "switching_cost": 0.95})
    assert _score(low_sw) > _score(high_sw)


def test_do_nothing_feasible_and_stability_idle() -> None:
    opt = _global_option(
        "dn",
        {**_baseline_params(), "mission_mode": "do_nothing"},
        option_type="do_nothing_mission",
    )
    ev = _eval(opt)
    assert ev.feasible is True
    assert ev.predicted_effects.get("mission_stability_idle") is True
    assert ev.stability_cost < 0.2
