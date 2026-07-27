"""Unresolved-victim coverage mode: general triggers and corridor diversity."""

from __future__ import annotations

import os
import random
from types import SimpleNamespace

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from common_fixed_variables import wind_vector_from_direction
from src_extension.adaptation.local_adaptation_generator import (
    COVERAGE_INTERIOR_X_MIN,
    LocalAdaptationSpaceGenerator,
    _apply_unresolved_coverage_mode,
    _corridor_diversity_failure,
    _count_unresolved_victims,
    _coverage_interior_x_max,
    _wind_search_state,
    apply_scenario_config,
    resolve_primary_victim_searcher_uav_id,
)
from src_extension.managed.victim_state import VictimState
from wildfire_model import WildFireModel


def _configure_scenario_a_east(*, batch_size: int = 300) -> None:
    rng = random.Random(42)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    os.environ["WIND_DIRECTION"] = "east"
    apply_scenario_config(
        cfv,
        wf,
        NUM_AGENTS=2,
        NUM_VICTIMS=3,
        NUM_FIREFIGHTERS=3,
        FIRE_SPREAD_MULTIPLIER=0.75,
        BATCH_SIZE=batch_size,
        FIXED_WIND=True,
        WIND_DIRECTION="east",
    )


def _runtime_models(
    *,
    wind: str = "east",
    fire_cells: set[tuple[int, int]] | None = None,
    uav_pos: tuple[float, float] = (45.0, 25.0),
    uav_id: str = "2501",
    simulation: object | None = None,
) -> dict:
    fire_cells = fire_cells or {(20, 20), (21, 20), (22, 21)}
    sim = simulation or SimpleNamespace(
        HEIGHT=50,
        WIDTH=50,
        height=50,
        width=50,
        schedule=SimpleNamespace(agents=[]),
        managed_victims={
            "victim_2": VictimState(victim_id="victim_2", status="unknown"),
        },
        evaluation_timesteps_counter=50,
        uav_visit_counts={},
        _wind_search_target_state={},
    )
    fire_map = {cell: 0.6 for cell in fire_cells}
    fire_runtime = SimpleNamespace(
        fire_probability_map=fire_map,
        belief=SimpleNamespace(fire_probability_map=fire_map),
    )
    visibility = SimpleNamespace(
        smoke_obscured_cells=set(),
        state=SimpleNamespace(observation_status_map={}),
    )
    resource = SimpleNamespace(
        by_uav_id={
            uav_id: SimpleNamespace(
                current_role="victim_searcher",
                position=uav_pos,
            )
        }
    )
    from src_extension.monitoring.monitoring_interfaces import GlobalObservationSnapshot

    snapshot = GlobalObservationSnapshot(
        timestamp=1.0,
        mission_time=1.0,
        fire_summary={},
        fire_belief_summary={},
        visibility_summary={},
        uav_team_summary={},
        victim_summary={},
        firefighter_summary={},
        communication_summary={},
        uncertainty_summary={},
        information_sufficiency="sufficient",
        belief_gap_indicators={},
        event_flags={},
        wind_direction=wind,
        wind_vector=wind_vector_from_direction(wind),
        wind_source="test",
        wind_timestamp=1.0,
        observation_step=50,
    )
    return {
        "simulation_model": sim,
        "fire_runtime_model": fire_runtime,
        "visibility_model": visibility,
        "victim_runtime_model": SimpleNamespace(victims={}),
        "uav_resource_model": resource,
        "global_observation_snapshot": snapshot,
    }


def test_post_rescue_coverage_flag_set_in_wind_state() -> None:
    _configure_scenario_a_east()
    model = WildFireModel()
    vs_id = resolve_primary_victim_searcher_uav_id(model)
    assert vs_id is not None
    for _ in range(5):
        model.step()
    assert _count_unresolved_victims(model) >= 2
    model._handle_rescue_incident(
        {
            "type": "rescue_complete",
            "victim_id": "victim_0",
            "firefighter_id": "ff_unit_0",
        }
    )
    wind_state = (getattr(model, "_wind_search_target_state", {}) or {}).get(vs_id, {})
    assert int(wind_state.get("post_rescue_coverage_steps_remaining", 0) or 0) > 0
    assert float(wind_state.get("coverage_priority", 0.0) or 0.0) >= 0.85


def test_corridor_diversity_failure_forces_west_target() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="east", uav_pos=(45.0, 25.0))
    sim = runtime["simulation_model"]
    state = _wind_search_state(sim, "2501")
    state["recent_x_positions"] = [45] * 25
    state["steps_since_detection"] = 50
    assert _corridor_diversity_failure(state)
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2501",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    assert int(round(target[0])) <= 25


def test_coverage_mode_activates_when_unresolved_and_no_detection() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="east", uav_pos=(45.0, 25.0))
    sim = runtime["simulation_model"]
    state = _wind_search_state(sim, "2501")
    state["steps_since_detection"] = 50
    state["unresolved_victim_count"] = 1
    _apply_unresolved_coverage_mode(state)
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2501",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    assert float(state.get("coverage_priority", 0.0) or 0.0) >= 0.85
    option = gen._try_generate_wind_aware_victim_search_option(
        runtime_models=runtime,
        uav_id="2501",
        target_entity="2501",
        current_role="victim_searcher",
        confidence=0.8,
        timestamp=1.0,
        originating_trigger="test",
        base_parameters={},
        mission_goals={},
    )
    assert option is not None
    assert float(option.parameters.get("coverage_priority", 0.0) or 0.0) >= 0.85


def test_victim_searcher_does_not_stay_in_single_corridor_when_unresolved() -> None:
    _configure_scenario_a_east()
    model = WildFireModel()
    vs_id = resolve_primary_victim_searcher_uav_id(model)
    assert vs_id is not None
    east_flags: list[bool] = []
    for _ in range(50):
        model.step()
        agent = next((a for a in model.schedule.agents if str(a.unique_id) == vs_id), None)
        assert agent is not None
        east_flags.append(int(agent.pos[0]) >= 38)
    assert not all(east_flags)
    max_streak = 0
    streak = 0
    for flag in east_flags:
        if flag:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    assert max_streak < 40


def test_coverage_target_stays_in_interior_band() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="east", uav_pos=(4.0, 20.0))
    sim = runtime["simulation_model"]
    state = _wind_search_state(sim, "2501")
    state["steps_since_detection"] = 50
    state["unresolved_victim_count"] = 1
    _apply_unresolved_coverage_mode(state)
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2501",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    tx = int(round(target[0]))
    assert COVERAGE_INTERIOR_X_MIN <= tx <= _coverage_interior_x_max(49)
    assert tx > 5


def test_coverage_y_sweep_alternates_halves() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="east", uav_pos=(15.0, 10.0))
    sim = runtime["simulation_model"]
    state = _wind_search_state(sim, "2501")
    state["recent_y_positions"] = [10] * 15
    state["steps_since_detection"] = 50
    state["unresolved_victim_count"] = 1
    _apply_unresolved_coverage_mode(state)
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2501",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    assert int(round(target[1])) >= 25


def test_coverage_y_sweep_lower_after_upper_camping() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="east", uav_pos=(15.0, 40.0))
    sim = runtime["simulation_model"]
    state = _wind_search_state(sim, "2501")
    state["recent_y_positions"] = [40] * 15
    state["steps_since_detection"] = 50
    state["unresolved_victim_count"] = 1
    _apply_unresolved_coverage_mode(state)
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2501",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    assert int(round(target[1])) <= 24


def _assert_all_victims_terminal(model: WildFireModel) -> None:
    terminal = {"rescued", "dead", "unreachable", "cancelled"}
    for vid, state in model.managed_victims.items():
        status = str(getattr(state, "status", "") or "").strip().lower()
        assert status in terminal, f"{vid} status={status!r} not terminal"
        assert status not in {"candidate", "assigned", "unknown"}, (
            f"{vid} still unaccounted: {status!r}"
        )


@pytest.mark.slow
def test_remaining_victim_coverage_after_two_rescues() -> None:
    _configure_scenario_a_east()
    model = WildFireModel()
    vs_id = resolve_primary_victim_searcher_uav_id(model)
    assert vs_id is not None
    west_after_40 = False
    for step in range(1, 101):
        model.step()
        wind_state = (getattr(model, "_wind_search_target_state", {}) or {}).get(vs_id, {})
        if step > 40:
            agent = next((a for a in model.schedule.agents if str(a.unique_id) == vs_id), None)
            if agent is not None and int(agent.pos[0]) < 35:
                west_after_40 = True
        if step == 100:
            unresolved = int(wind_state.get("unresolved_victim_count", 0) or 0)
            managed_unresolved = _count_unresolved_victims(model)
            assert unresolved == managed_unresolved
    assert west_after_40


@pytest.mark.slow
def test_scenario_a_all_victims_accounted() -> None:
    _configure_scenario_a_east(batch_size=300)
    model = WildFireModel()
    for _ in range(300):
        model.step()
    _assert_all_victims_terminal(model)


@pytest.mark.slow
def test_seed42_scenario_a_all_victims_accounted_by_300() -> None:
    _configure_scenario_a_east(batch_size=300)
    model = WildFireModel()
    for _ in range(300):
        model.step()
    _assert_all_victims_terminal(model)
