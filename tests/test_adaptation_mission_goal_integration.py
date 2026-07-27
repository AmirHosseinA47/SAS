"""Local/rescue adaptation generators consume live mission_goals."""

from __future__ import annotations

from types import SimpleNamespace

from common_fixed_variables import wind_vector_from_direction
from src_extension.adaptation.local_adaptation_generator import LocalAdaptationSpaceGenerator
from src_extension.adaptation.rescue_adaptation_generator import RescueAdaptationSpaceGenerator
from src_extension.knowledge.mission_goal_model import MissionGoalModel


def _mission_goals(**overrides: object) -> dict:
    model = MissionGoalModel()
    context = {
        "timestamp": 1.0,
        "step_index": 1,
        "alive_victims_remaining": 0,
        "active_rescues": 0,
        "alive_firefighters": 2,
        "fire_severity_estimate": 0.2,
        "coverage_ratio": 0.4,
        "active_fail_safe_mode": "normal",
    }
    context.update(overrides)
    model.refresh_from_runtime(context)
    return model.runtime_context()


def _local_runtime(*, role: str = "fire_tracker", mission_goals: dict | None = None) -> dict:
    fire_map = {(12, 12): 0.85, (13, 12): 0.9}
    runtime = {
        "uav_id": "2500",
        "available_entities": ["2500"],
        "fire_runtime_model": SimpleNamespace(
            belief=SimpleNamespace(fire_probability_map=fire_map),
            fire_probability_map=fire_map,
        ),
        "uav_resource_model": SimpleNamespace(
            by_uav_id={"2500": SimpleNamespace(current_role=role, position=(10.0, 10.0))}
        ),
        "simulation_model": SimpleNamespace(
            HEIGHT=50,
            WIDTH=50,
            height=50,
            width=50,
            schedule=SimpleNamespace(agents=[]),
            managed_victims={},
        ),
    }
    if mission_goals is not None:
        runtime["mission_goals"] = mission_goals
    return runtime


def test_local_generator_without_mission_goals_still_works() -> None:
    gen = LocalAdaptationSpaceGenerator()
    space = gen.generate(
        {
            "triggers": [],
            "target_entity": "2500",
            "local_uncertainty": {},
            "fire_belief": {},
            "victim_confidence": {},
            "stale_regions": [],
        },
        local_models={},
        runtime_models=_local_runtime(),
        timestamp=1.0,
    )
    assert len(space.options) > 0
    assert all("mission_goal_phase" not in (opt.parameters or {}) for opt in space.options)


def test_local_generator_attaches_mission_goal_metadata() -> None:
    goals = _mission_goals(active_rescues=0, alive_victims_remaining=1)
    gen = LocalAdaptationSpaceGenerator()
    options = gen._generate_path_options(
        {"triggers": [], "target_entity": "2500"},
        {},
        _local_runtime(mission_goals=goals),
        1.0,
    )
    assert options
    params = options[0].parameters
    assert params["mission_goal_phase"] == goals["mission_phase"]
    assert "mission_goal_priorities" in params
    assert "mission_goal_constraints" in params
    assert params["mission_goal_reason"]


def test_prioritize_victim_search_boosts_wind_aware_option() -> None:
    goals = _mission_goals(active_rescues=0, alive_victims_remaining=1)
    goals["goal_priorities"]["prioritize_victim_search"] = True
    fire_cells = {(20, 20)}
    fire_map = {cell: 0.6 for cell in fire_cells}
    runtime = {
        "uav_id": "2502",
        "mission_goals": goals,
        "simulation_model": SimpleNamespace(
            HEIGHT=50,
            WIDTH=50,
            height=50,
            width=50,
            schedule=SimpleNamespace(agents=[]),
            managed_victims={},
        ),
        "fire_runtime_model": SimpleNamespace(
            fire_probability_map=fire_map,
            belief=SimpleNamespace(fire_probability_map=fire_map),
        ),
        "visibility_model": SimpleNamespace(smoke_obscured_cells=set()),
        "victim_runtime_model": SimpleNamespace(victims={}),
        "uav_resource_model": SimpleNamespace(
            by_uav_id={
                "2502": SimpleNamespace(
                    current_role="victim_searcher",
                    position=(10.0, 10.0),
                )
            }
        ),
        "global_observation_snapshot": SimpleNamespace(
            wind_direction="north",
            wind_vector=wind_vector_from_direction("north"),
        ),
    }
    gen = LocalAdaptationSpaceGenerator()
    options = gen._generate_path_options(
        {"triggers": [], "target_entity": "2502"},
        {},
        runtime,
        1.0,
    )
    wind_option = next(
        (opt for opt in options if opt.option_id == "wind_aware_victim_search"),
        None,
    )
    assert wind_option is not None
    assert wind_option.parameters["mission_goal_boost"] is True
    assert wind_option.parameters["mission_goal_reason"] == "prioritize_victim_search"
    assert wind_option.confidence >= 0.6


def test_prioritize_fire_perimeter_tracking_marks_fire_front_metadata() -> None:
    goals = _mission_goals()
    goals["goal_priorities"]["prioritize_fire_perimeter_tracking"] = True
    gen = LocalAdaptationSpaceGenerator()
    options = gen._generate_path_options(
        {"triggers": [], "target_entity": "2500"},
        {},
        _local_runtime(mission_goals=goals),
        1.0,
    )
    fire_front = next(
        (
            opt
            for opt in options
            if opt.parameters.get("fire_front_target") is True
            or str(opt.parameters.get("path_action", "")).startswith("move_toward_fire")
        ),
        None,
    )
    assert fire_front is not None
    assert fire_front.parameters.get("enters_fire_zone") is True
    assert fire_front.parameters["mission_goal_priorities"]["prioritize_fire_perimeter_tracking"] is True


def test_rescue_generator_attaches_mission_goal_metadata() -> None:
    goals = _mission_goals(active_rescues=1, alive_victims_remaining=1)
    gen = RescueAdaptationSpaceGenerator()
    space = gen.generate(
        {"triggers": [], "target_entity": "mission"},
        runtime_models={"mission_goals": goals},
        timestamp=1.0,
    )
    assignment = next(
        opt for opt in space.options if opt.option_id == "rescue_firefighter_assignment_nearest"
    )
    assert assignment.parameters["mission_goal_phase"] == "rescue_active"
    assert assignment.parameters["rescue_urgency"] == 1
    assert assignment.parameters["active_rescues"] == 1


def test_prioritize_rescue_completion_affects_rescue_assignment_metadata() -> None:
    goals = _mission_goals(active_rescues=1, alive_victims_remaining=2)
    gen = RescueAdaptationSpaceGenerator()
    space = gen.generate(
        {"triggers": [], "target_entity": "mission"},
        runtime_models={"mission_goals": goals},
        timestamp=1.0,
    )
    assignment = next(
        opt for opt in space.options if opt.option_id == "rescue_firefighter_assignment_nearest"
    )
    assert assignment.parameters["mission_goal_boost"] is True
    assert assignment.parameters["mission_goal_reason"] == "prioritize_rescue_completion"


def test_failsafe_emergency_marks_delay_and_cancel_metadata() -> None:
    goals = _mission_goals(active_fail_safe_mode="emergency", alive_victims_remaining=1)
    gen = RescueAdaptationSpaceGenerator()
    space = gen.generate(
        {"triggers": [], "target_entity": "mission"},
        runtime_models={"mission_goals": goals},
        timestamp=1.0,
    )
    delay = next(opt for opt in space.options if opt.option_id == "rescue_decision_delay_rescue")
    cancel = next(opt for opt in space.options if opt.option_id == "rescue_decision_cancel_rescue")
    assert delay.parameters["preferred_under_failsafe"] is True
    assert cancel.parameters["preferred_under_failsafe"] is True
    assert delay.parameters["mission_goal_phase"] == "emergency"


def _local_input(**extra: object) -> dict:
    base = {
        "triggers": [],
        "target_entity": "2500",
        "local_uncertainty": {(1, 1): 0.9},
        "belief_gain": {(1, 1): 0.7},
        "drift_state": "high",
        "stale_regions": [(1, 1)],
        "communication_reliability": 0.4,
        "delivery_confidence": 0.5,
        "stability_state": "stable",
    }
    base.update(extra)
    return base


def test_horizon_option_has_mission_goal_metadata() -> None:
    goals = _mission_goals()
    gen = LocalAdaptationSpaceGenerator()
    options = gen._generate_horizon_options(
        _local_input(),
        {},
        _local_runtime(mission_goals=goals),
        1.0,
    )
    assert options
    assert options[0].parameters["mission_goal_phase"] == goals["mission_phase"]
    assert options[0].parameters["mission_goal_reason"]


def test_movement_option_has_mission_goal_metadata() -> None:
    goals = _mission_goals(active_fail_safe_mode="emergency")
    gen = LocalAdaptationSpaceGenerator()
    options = gen._generate_movement_strategy_options(
        _local_input(),
        {},
        _local_runtime(mission_goals=goals),
        1.0,
    )
    cautious = next(opt for opt in options if opt.option_id == "local_movement_cautious_movement")
    assert cautious.parameters["mission_goal_phase"] == "emergency"
    assert cautious.parameters["mission_goal_constraints"]


def test_stability_option_has_mission_goal_metadata() -> None:
    goals = _mission_goals()
    gen = LocalAdaptationSpaceGenerator()
    options = gen._generate_stability_options(
        _local_input(),
        {},
        _local_runtime(mission_goals=goals),
        1.0,
    )
    keep_path = next(opt for opt in options if opt.option_id == "local_stability_keep_current_path")
    assert keep_path.parameters["mission_goal_priorities"]
    assert keep_path.parameters["mission_goal_reason"]


def test_communication_option_has_mission_goal_metadata() -> None:
    goals = _mission_goals()
    gen = LocalAdaptationSpaceGenerator()
    options = gen._generate_communication_options(
        _local_input(),
        {},
        _local_runtime(mission_goals=goals),
        1.0,
    )
    relay = next(opt for opt in options if opt.option_id == "local_communication_relay_mode")
    assert relay.parameters["mission_goal_phase"] == goals["mission_phase"]


def test_survivability_priority_boosts_safe_movement_confidence() -> None:
    goals = _mission_goals(active_fail_safe_mode="emergency")
    goals["goal_priorities"]["prioritize_uav_survivability"] = True
    gen = LocalAdaptationSpaceGenerator()
    runtime = _local_runtime(mission_goals=goals)
    boosted = gen._generate_movement_strategy_options(_local_input(), {}, runtime, 1.0)
    baseline = gen._generate_movement_strategy_options(
        _local_input(),
        {},
        _local_runtime(mission_goals={}),
        1.0,
    )
    boosted_hold = next(
        opt for opt in boosted if opt.option_id == "local_movement_hold_position"
    )
    baseline_hold = next(
        opt for opt in baseline if opt.option_id == "local_movement_hold_position"
    )
    assert boosted_hold.confidence > baseline_hold.confidence


def test_full_generate_attaches_metadata_to_all_option_families() -> None:
    goals = _mission_goals(active_rescues=0, alive_victims_remaining=1)
    gen = LocalAdaptationSpaceGenerator()
    space = gen.generate(
        _local_input(),
        local_models={
            "local_uncertainty": {(1, 1): 0.9},
            "belief_gain": {(1, 1): 0.7},
            "drift_state": "high",
            "stale_regions": [(1, 1)],
        },
        runtime_models=_local_runtime(mission_goals=goals),
        timestamp=1.0,
    )
    families = {opt.option_type for opt in space.options}
    assert "horizon_control" in families
    assert "movement_strategy" in families
    assert "communication_strategy" in families
    assert "stability_control" in families
    for opt in space.options:
        assert opt.parameters.get("mission_goal_phase") == goals["mission_phase"]


def test_rescue_legacy_behavior_without_mission_goals() -> None:
    gen = RescueAdaptationSpaceGenerator()
    space = gen.generate(
        {"triggers": [], "target_entity": "mission"},
        runtime_models={},
        timestamp=1.0,
    )
    assert any(
        opt.option_id == "rescue_stability_maintain_current_rescue_state" for opt in space.options
    )
    decision = next(opt for opt in space.options if opt.option_id == "rescue_decision_delay_rescue")
    assert "mission_goal_phase" not in decision.parameters
