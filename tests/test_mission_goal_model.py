"""Live MissionGoalModel runtime refresh and integrations."""

from __future__ import annotations

from src_extension.adaptation.adaptation_option_objects import LocalAdaptationOption, Scope
from src_extension.adaptation.constraint_filter import ConstraintFilter
from src_extension.adaptation.global_adaptation_generator import GlobalAdaptationSpaceGenerator
from src_extension.knowledge.mission_goal_model import MissionGoalModel
from src_extension.planning.mission_goal_integration import read_mission_goals, resolve_utility_mode


def _refresh(**overrides: object) -> MissionGoalModel:
    model = MissionGoalModel()
    context = {
        "timestamp": 1.0,
        "step_index": 1,
        "alive_victims_remaining": 0,
        "active_rescues": 0,
        "alive_firefighters": 2,
        "fire_severity_estimate": 0.1,
        "coverage_ratio": 0.4,
        "active_fail_safe_mode": "normal",
    }
    context.update(overrides)
    model.refresh_from_runtime(context)
    return model


def test_default_exploration_phase() -> None:
    model = _refresh()
    assert model.mission_phase == "exploration"
    assert model.goal_priority("prioritize_information_gain") is True
    assert model.dynamic_metrics["coverage_ratio"] == 0.4


def test_rescue_active_when_victim_assigned() -> None:
    model = _refresh(active_rescues=1, alive_victims_remaining=1)
    assert model.mission_phase == "rescue_active"
    assert model.goal_priority("prioritize_rescue_completion") is True
    assert model.goal_priority("prioritize_victim_search") is True


def test_emergency_and_degraded_propagation() -> None:
    emergency = _refresh(active_fail_safe_mode="emergency")
    assert emergency.mission_phase == "emergency"
    assert emergency.dynamic_metrics["active_fail_safe_mode"] == "emergency"
    assert emergency.utility_weight_mode() == "safety_first_mode"
    assert emergency.goal_priority("prioritize_uav_survivability") is True

    degraded = _refresh(active_fail_safe_mode="degraded")
    assert degraded.mission_phase == "degraded_operation"
    assert degraded.utility_weight_mode() == "battery_constrained_mode"


def test_evacuation_when_fire_severity_high_with_victims() -> None:
    model = _refresh(
        fire_severity_estimate=0.8,
        alive_victims_remaining=2,
        active_rescues=0,
    )
    assert model.mission_phase == "evacuation"
    assert model.constraint_enabled("avoid_fire_entry") is True


def test_fire_severity_and_coverage_metrics_update() -> None:
    model = _refresh(fire_severity_estimate=0.55, coverage_ratio=0.72)
    assert model.dynamic_metrics["fire_severity_estimate"] == 0.55
    assert model.dynamic_metrics["coverage_ratio"] == 0.72


def test_goal_priority_toggles_and_legacy_weights() -> None:
    model = _refresh(active_rescues=1, alive_victims_remaining=1)
    assert model.goal_weights["prioritize_rescue_completion"] == 1.0
    assert "prioritize_rescue_completion" in model.adaptation_goals


def test_runtime_context_exposed_to_planners() -> None:
    model = _refresh(active_rescues=1, alive_victims_remaining=1)
    runtime_models = {"mission_goal_model": model, "mission_goals": model.runtime_context()}
    goals = read_mission_goals(runtime_models)
    assert goals["mission_phase"] == "rescue_active"
    assert resolve_utility_mode(None, runtime_models) == "victim_support_mode"


def test_constraint_filter_uses_live_mission_constraints() -> None:
    model = _refresh(active_fail_safe_mode="emergency")
    option = LocalAdaptationOption(
        option_id="local_path_enter_fire",
        option_type="path_adaptation",
        target_entity="2500",
        parameters={"path_action": "enter_fire_zone", "enters_fire_zone": True},
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=0.8,
        scope=Scope.local,
        timestamp=1.0,
        originating_trigger="test",
        explanation_hint="test",
    )
    filt = ConstraintFilter()
    kept = filt.filter_options([option], runtime_models={}, mission_constraints=model)
    assert kept == []
    assert filt.rejected_options[0]["reasons"]


def test_global_adaptation_reads_mission_goals_for_search_mode() -> None:
    model = _refresh(active_rescues=0, alive_victims_remaining=2)
    model.goal_priorities["prioritize_victim_search"] = True
    model._sync_legacy_fields()
    space = GlobalAdaptationSpaceGenerator().generate(
        {"triggers": [], "target_entity": "mission", "fire_probability_map": {"r1": 0.8}},
        runtime_models={
            "mission_goal_model": model,
            "mission_goals": model.runtime_context(),
        },
        timestamp=1.0,
    )
    search_option = next(
        option
        for option in space.options
        if option.option_id == "global_coverage_strategy_search_mode_activation"
    )
    assert search_option.parameters["search_mode_required"] is True
    assert search_option.parameters["mission_goal_phase"] == model.mission_phase


def test_global_planner_reads_mission_goal_utility_mode() -> None:
    model = _refresh(active_fail_safe_mode="information_recovery")
    mode = resolve_utility_mode(None, {"mission_goal_model": model})
    assert mode == "information_recovery_mode"


def test_snapshot_backward_compatibility() -> None:
    model = _refresh()
    snapshot = model.snapshot()
    assert "adaptation_goals" in snapshot
    assert "goal_weights" in snapshot
    assert "hard_constraints" in snapshot
    assert snapshot["runtime_context"]["mission_phase"] == "exploration"
