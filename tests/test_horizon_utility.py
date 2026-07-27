"""Horizon-aware utility (global + local)."""

from src_extension.adaptation.adaptation_option_objects import LocalAdaptationOption, MissionAdaptationOption, Scope
from src_extension.planning.utility_evaluation import UtilityEvaluation


def _mission_base() -> dict:
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


def _global(option_id: str, parameters: dict) -> MissionAdaptationOption:
    return MissionAdaptationOption(
        option_id=option_id,
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


def _hz_stress() -> dict:
    return {
        "uncertainty_level": 0.95,
        "communication_reliability": 0.2,
        "fire_spread_speed": 0.35,
        "information_collapse": 0.12,
    }


def _hz_stable() -> dict:
    return {
        "uncertainty_level": 0.06,
        "communication_reliability": 0.94,
        "fire_spread_speed": 0.08,
        "information_collapse": 0.04,
    }


def test_global_short_horizon_beats_long_under_high_uncertainty() -> None:
    ue = UtilityEvaluation(default_mode="normal_monitoring_mode")
    common = {**_mission_base(), **_hz_stress()}
    short_opt = _global(
        "g-short",
        {
            **common,
            "horizon_type": "short_adaptive_roll",
            "candidate_horizon_length": 0.22,
        },
    )
    long_opt = _global(
        "g-long",
        {
            **common,
            "horizon_type": "long_extended_mission",
            "candidate_horizon_length": 0.92,
        },
    )
    s_short = ue.evaluate_option(short_opt, mode="normal_monitoring_mode").total_utility
    s_long = ue.evaluate_option(long_opt, mode="normal_monitoring_mode").total_utility
    assert s_short > s_long


def test_global_long_horizon_beats_short_under_stable_low_uncertainty() -> None:
    ue = UtilityEvaluation(default_mode="normal_monitoring_mode")
    common = {**_mission_base(), **_hz_stable()}
    long_opt = _global(
        "g-long-stable",
        {
            **common,
            "horizon_type": "long_extended",
            "candidate_horizon_length": 0.88,
        },
    )
    short_opt = _global(
        "g-short-stable",
        {
            **common,
            "horizon_type": "short_tick",
            "candidate_horizon_length": 0.18,
        },
    )
    assert (
        ue.evaluate_option(long_opt, mode="normal_monitoring_mode").total_utility
        > ue.evaluate_option(short_opt, mode="normal_monitoring_mode").total_utility
    )


def test_global_information_collapse_favors_search_replan_short() -> None:
    ue = UtilityEvaluation(default_mode="normal_monitoring_mode")
    collapse = {
        "uncertainty_level": 0.4,
        "communication_reliability": 0.55,
        "fire_spread_speed": 0.2,
        "information_collapse": 0.88,
    }
    search_opt = _global(
        "g-search",
        {
            **_mission_base(),
            **collapse,
            "horizon_type": "search_replan_window",
            "candidate_horizon_length": 0.35,
        },
    )
    long_opt = _global(
        "g-long-collapse",
        {
            **_mission_base(),
            **collapse,
            "horizon_type": "long_extend_only",
            "candidate_horizon_length": 0.92,
        },
    )
    ev_s = ue.evaluate_option(search_opt, mode="normal_monitoring_mode")
    ev_l = ue.evaluate_option(long_opt, mode="normal_monitoring_mode")
    assert ev_s.total_utility > ev_l.total_utility
    assert "collapse_short_search_replan" in str(ev_s.predicted_effects.get("horizon_context_note", ""))


def test_local_short_horizon_beats_long_under_high_uncertainty() -> None:
    ue = UtilityEvaluation(default_mode="normal_monitoring_mode")
    path = {
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
    hz = _hz_stress()

    def _local(oid: str, ht: str, h_len: float) -> LocalAdaptationOption:
        return LocalAdaptationOption(
            option_id=oid,
            option_type="path_adjust",
            target_entity="uav-1",
            parameters={
                **path,
                **hz,
                "horizon_type": ht,
                "candidate_horizon_length": h_len,
            },
            expected_effect="test",
            cost_estimate=0.1,
            risk_estimate=0.1,
            confidence=1.0,
            scope=Scope.local,
            timestamp=0.0,
            originating_trigger="t",
            explanation_hint="",
        )

    short_l = _local("loc-s", "short_adaptive_roll", 0.22)
    long_l = _local("loc-l", "long_extended_mission", 0.92)
    assert ue.evaluate_option(short_l).total_utility > ue.evaluate_option(long_l).total_utility
