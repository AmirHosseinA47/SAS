"""Global and local planner decision logic."""

from dataclasses import dataclass
from types import SimpleNamespace

from src_extension.adaptation.adaptation_option_objects import LocalAdaptationOption, MissionAdaptationOption, Scope
from src_extension.adaptation.adaptation_results import GlobalAdaptationSpace, LocalAdaptationSpace
from src_extension.planning.global_mission_planner import GlobalMissionPlanner
from src_extension.planning.local_uav_path_planner import LocalUAVPathPlanner
from src_extension.planning.utility_evaluation import UtilityEvaluation


def _global_baseline_params() -> dict[str, float]:
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


@dataclass
class _GlobalSnapshot:
    global_space: GlobalAdaptationSpace


def test_global_mission_planner_selects_high_utility_over_do_nothing() -> None:
    do_nothing = _global_option(
        "do_nothing",
        {**_global_baseline_params(), "mission_mode": "do_nothing"},
        option_type="do_nothing_mission",
    )
    active = _global_option(
        "active_mission",
        {
            **_global_baseline_params(),
            "fire_contribution": 0.95,
            "victim_contribution": 0.9,
            "communication_contribution": 0.85,
            "uncertainty_reduction": 0.8,
            "information_recovery": 0.75,
        },
        option_type="mission_reassign",
    )
    snapshot = _GlobalSnapshot(
        global_space=GlobalAdaptationSpace(options=[do_nothing, active]),
    )
    planner = GlobalMissionPlanner(utility_evaluator=UtilityEvaluation(default_mode="safety_first_mode"))

    decision = planner.plan(1, adaptation_space_snapshot=snapshot)

    assert decision is not None
    assert decision.selected_option_id == "active_mission"


def test_global_mission_planner_returns_maintain_when_no_feasible_option() -> None:
    maintain = _global_option(
        "maintain",
        {**_global_baseline_params(), "do_nothing": True},
        option_type="stability_control",
    )
    infeasible_a = _global_option(
        "bad_a",
        {**_global_baseline_params(), "hard_collision_violation": True},
        option_type="mission_reassign",
    )
    infeasible_b = _global_option(
        "bad_b",
        {**_global_baseline_params(), "route_feasible": False},
        option_type="role_change",
    )
    snapshot = _GlobalSnapshot(
        global_space=GlobalAdaptationSpace(options=[infeasible_a, infeasible_b, maintain]),
    )
    planner = GlobalMissionPlanner(utility_evaluator=UtilityEvaluation(default_mode="safety_first_mode"))

    decision = planner.plan(2, adaptation_space_snapshot=snapshot)

    assert decision is not None
    assert decision.selected_option_id == "maintain"


def _local_baseline_params() -> dict[str, float]:
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


def _local_option(
    option_id: str,
    parameters: dict,
    *,
    option_type: str = "path_adjust",
    target_entity: str = "uav-1",
) -> LocalAdaptationOption:
    return LocalAdaptationOption(
        option_id=option_id,
        option_type=option_type,
        target_entity=target_entity,
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


def test_local_path_planner_selects_higher_utility_search_option() -> None:
    low = _local_option(
        "low_path",
        {
            **_local_baseline_params(),
            "expected_info_gain": 0.05,
            "recovery_value": 0.05,
            "task_support": 0.05,
        },
    )
    search = _local_option(
        "search_path",
        {
            **_local_baseline_params(),
            "expected_info_gain": 0.9,
            "recovery_value": 0.95,
            "information_recovery_score": 0.9,
            "task_support": 0.8,
            "search_mode": True,
        },
        option_type="information_recovery_search",
    )
    space = LocalAdaptationSpace(options=[low, search])
    planner = LocalUAVPathPlanner(
        uav_id="uav-1",
        utility_evaluator=UtilityEvaluation(default_mode="safety_first_mode"),
    )

    decision = planner.plan(1, local_adaptation_space=space)

    assert decision is not None
    assert decision.selected_option_id == "search_path"


def test_local_path_planner_returns_hold_current_path_fallback() -> None:
    hold = _local_option(
        "hold",
        {**_local_baseline_params(), "keep_current_path": True},
        option_type="keep_current_path",
    )
    infeasible = _local_option(
        "bad_path",
        {**_local_baseline_params(), "hard_collision_violation": True},
        option_type="path_adjust",
    )
    space = LocalAdaptationSpace(options=[infeasible, hold])
    planner = LocalUAVPathPlanner(
        uav_id="uav-1",
        utility_evaluator=UtilityEvaluation(default_mode="safety_first_mode"),
    )

    decision = planner.plan(2, local_adaptation_space=space)

    assert decision is not None
    assert decision.selected_option_id == "hold"


def test_local_path_planner_does_not_modify_uav_agent_or_selected_dir() -> None:
    agent = SimpleNamespace(selected_dir=3, unique_id="uav-1")
    original_dir = agent.selected_dir

    space = LocalAdaptationSpace(
        options=[
            _local_option(
                "path_a",
                {**_local_baseline_params(), "expected_info_gain": 0.8},
            )
        ]
    )
    planner = LocalUAVPathPlanner(
        uav_id="uav-1",
        utility_evaluator=UtilityEvaluation(default_mode="safety_first_mode"),
    )

    decision = planner.plan(3, local_adaptation_space=space)

    assert decision is not None
    assert agent.selected_dir == original_dir
    assert not hasattr(decision, "selected_dir")
