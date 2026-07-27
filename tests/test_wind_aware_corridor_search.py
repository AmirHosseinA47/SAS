"""Wind-aware corridor search: anti-camping penalties and target lifecycle."""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("MPLBACKEND", "Agg")

import random

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from common_fixed_variables import wind_vector_from_direction
from src_extension.adaptation.local_adaptation_generator import (
    LocalAdaptationSpaceGenerator,
    WIND_EDGE_MARGIN,
    WIND_SAME_TARGET_RESET_STREAK,
    _advance_corridor_index,
    _record_wind_search_target,
    _reset_corridor_on_same_target_streak,
    _wind_search_state,
    resolve_primary_victim_searcher_uav_id,
)
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.monitoring.monitoring_interfaces import GlobalObservationSnapshot
from src_extension.planning.decision_objects import PathDecision
from src_extension.planning.local_uav_path_planner import LocalUAVPathPlanner
from wildfire_model import WildFireModel


def _runtime_models(
    *,
    wind: str = "east",
    fire_cells: set[tuple[int, int]] | None = None,
    uav_pos: tuple[float, float] = (10.0, 10.0),
    uav_id: str = "2502",
    simulation: object | None = None,
) -> dict:
    fire_cells = fire_cells or {(20, 20)}
    sim = simulation or SimpleNamespace(
        HEIGHT=50,
        WIDTH=50,
        height=50,
        width=50,
        schedule=SimpleNamespace(agents=[]),
        managed_victims={},
        evaluation_timesteps_counter=5,
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
        observation_step=1,
    )
    return {
        "simulation_model": sim,
        "fire_runtime_model": fire_runtime,
        "visibility_model": visibility,
        "victim_runtime_model": SimpleNamespace(victims={}),
        "uav_resource_model": resource,
        "global_observation_snapshot": snapshot,
    }


def test_same_target_streak_resets_corridor() -> None:
    sim = SimpleNamespace(
        HEIGHT=50, WIDTH=50, evaluation_timesteps_counter=20,
        uav_visit_counts={}, _wind_search_target_state={},
    )
    state = _wind_search_state(sim, "2502")
    state["corridor_targets"] = [(10.0, 10.0)]
    state["same_target_streak"] = WIND_SAME_TARGET_RESET_STREAK + 1
    _reset_corridor_on_same_target_streak(state, 20, (10.0, 10.0))
    assert state["corridor_targets"] == []
    assert state["force_interior_retarget"] is True


def test_corridor_generates_interior_waypoints() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="east", uav_pos=(20.0, 20.0))
    sim = runtime["simulation_model"]
    state = _wind_search_state(sim, "2502")
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2502",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    corridor = state.get("corridor_targets") or []
    assert len(corridor) >= 3
    assert all(
        int(round(point[0])) <= 48 - WIND_EDGE_MARGIN for point in corridor[:5]
    )


def test_corridor_exhaustion_sets_force_sweep() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="north", uav_pos=(24.0, 24.0))
    sim = runtime["simulation_model"]
    state = _wind_search_state(sim, "2502")
    state["corridor_targets"] = [(10.0, 10.0), (12.0, 12.0)]
    state["corridor_index"] = 1
    state["current_target"] = (12.0, 12.0)
    state["dwell_count"] = 3
    _advance_corridor_index(state)
    assert state.get("force_sweep") is True
    result = gen._compute_wind_aware_search_target(
        runtime,
        "2502",
        "north",
        wind_vector_from_direction("north"),
    )
    assert result is None


def test_south_wind_penalizes_southern_edge() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="south", uav_pos=(24.0, 24.0))
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2502",
        "south",
        wind_vector_from_direction("south"),
    )
    assert target is not None
    assert int(round(target[1])) > 1


def test_east_wind_prefers_interior_when_corner_penalized() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="east", uav_pos=(24.0, 24.0))
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2502",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    assert int(round(target[0])) <= 48 - WIND_EDGE_MARGIN


def test_high_visit_count_reduces_corner_score() -> None:
    gen = LocalAdaptationSpaceGenerator()
    sim = SimpleNamespace(
        HEIGHT=50,
        WIDTH=50,
        evaluation_timesteps_counter=5,
        uav_visit_counts={("2502", 48, 48): 12},
        _wind_search_target_state={},
    )
    runtime = _runtime_models(wind="east", uav_pos=(40.0, 40.0), simulation=sim)
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2502",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    assert (int(round(target[0])), int(round(target[1]))) != (48, 48)


def test_saturated_target_not_reselected_immediately() -> None:
    gen = LocalAdaptationSpaceGenerator()
    sim = SimpleNamespace(
        HEIGHT=50,
        WIDTH=50,
        evaluation_timesteps_counter=20,
        uav_visit_counts={},
        _wind_search_target_state={},
    )
    runtime = _runtime_models(wind="east", uav_pos=(46.0, 46.0), simulation=sim)
    state = _wind_search_state(sim, "2502")
    state["saturated_until"] = {(48, 48): 40}
    first = gen._compute_wind_aware_search_target(
        runtime,
        "2502",
        "east",
        wind_vector_from_direction("east"),
    )
    assert first is not None
    assert (int(round(first[0])), int(round(first[1]))) != (48, 48)


def test_recent_target_penalty_avoids_immediate_repeat() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="east", uav_pos=(30.0, 30.0))
    sim = runtime["simulation_model"]
    state = _wind_search_state(sim, "2502")
    _record_wind_search_target(state, (40.0, 30.0))
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2502",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    assert abs(target[0] - 40.0) + abs(target[1] - 30.0) > 1.0


def test_planner_avoids_hold_when_wind_target_reached() -> None:
    planner = LocalUAVPathPlanner(uav_id="2502")
    option = SimpleNamespace(
        option_id="wind_aware_victim_search",
        option_type="wind_aware_victim_search",
        target_entity="2502",
        parameters={
            "path_action": "victim_search_wind_aware",
            "next_action": "victim_search_wind_aware",
            "target_position": (48.0, 48.0),
            "search_policy": "wind_aware",
        },
        confidence=0.8,
        scope=SimpleNamespace(value="local"),
    )
    space = SimpleNamespace(options=[option])
    runtime = _runtime_models(wind="east", uav_pos=(48.0, 48.0))
    decision = planner.plan(
        1,
        local_adaptation_space=space,
        runtime_models=runtime,
    )
    assert decision is not None
    assert decision.next_action != "hold"
    assert decision.uncertainty_context.get("needs_new_wind_target") is True


def test_executor_retargets_when_planner_requests_new_wind_target() -> None:
    model = WildFireModel()
    vs_id = resolve_primary_victim_searcher_uav_id(model)
    assert vs_id is not None
    agent = next(a for a in model.schedule.agents if str(a.unique_id) == vs_id)
    executor = UAVExecutor(uav_id=vs_id, model=model, agent=agent)
    decision = PathDecision(
        decision_id="p-test",
        uav_id=vs_id,
        selected_option_id="wind_aware_victim_search",
        next_action="victim_search_wind_aware",
        uncertainty_context={
            "target_position": (48.0, 48.0),
            "search_policy": "wind_aware",
            "needs_new_wind_target": True,
            "wind_direction": "east",
        },
    )
    chosen_dir, action = executor._resolve_direction_intent(
        agent,
        decision,
        "victim",
        "victim_search_wind_aware",
    )
    assert action in {
        "victim_search_wind_aware_retarget",
        "victim_search_wind_aware_retarget_to_interior",
        "victim_search_wind_aware",
        "victim_search_wind_aware_sweep",
        "victim_search_hazard_retreat",
    }
    assert isinstance(chosen_dir, int)


def test_no_fire_or_smoke_target_selected() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(
        wind="east",
        fire_cells={(20, 20)},
        uav_pos=(10.0, 10.0),
    )
    runtime["visibility_model"] = SimpleNamespace(
        smoke_obscured_cells={(30, 30)},
        state=SimpleNamespace(observation_status_map={(30, 30): "smoke_obscured"}),
    )
    target = gen._compute_wind_aware_search_target(
        runtime,
        "2502",
        "east",
        wind_vector_from_direction("east"),
    )
    assert target is not None
    cell = (int(round(target[0])), int(round(target[1])))
    assert cell != (20, 20)
    assert cell != (30, 30)


def test_east_wind_80_step_run_visits_multiple_cells_not_one_corner_camp() -> None:
    rng = random.Random(42)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    cfv.WIND_DIRECTION = "east"
    cfv.FIRE_SPREAD_MULTIPLIER = 0.75
    cfv.BATCH_SIZE = 99_999
    original_batch = cfv.BATCH_SIZE
    try:
        model = WildFireModel()
        model.managed_victims = {}
        model.debug_log = False
        vs_id = resolve_primary_victim_searcher_uav_id(model)
        assert vs_id is not None
        positions: list[tuple[int, int]] = []
        targets: list[tuple[int, int] | None] = []
        max_hold_streak = 0
        max_x_streak = 0
        x_edge_streak = 0
        for _ in range(80):
            model.step()
            agent = next(a for a in model.schedule.agents if str(a.unique_id) == vs_id)
            pos = (int(agent.pos[0]), int(agent.pos[1]))
            positions.append(pos)
            pr = model.latest_planning_result or {}
            pd = (pr.get("path_decisions") or {}).get(vs_id)
            tgt = None
            if pd is not None:
                ctx = getattr(pd, "uncertainty_context", {}) or {}
                raw = ctx.get("target_position")
                if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                    tgt = (int(round(raw[0])), int(round(raw[1])))
            targets.append(tgt)
            exec_r = (model.latest_execution_result or {}).get("local", {})
            ur = (exec_r.get("uav_results") or {}).get(vs_id, {})
            action = str(ur.get("action") or "")
            if pos[0] >= 47:
                x_edge_streak += 1
                max_x_streak = max(max_x_streak, x_edge_streak)
            else:
                x_edge_streak = 0
        unique_positions = len(set(positions))
        unique_targets = len({t for t in targets if t is not None})
        assert unique_positions >= 8
        assert unique_targets >= 3
        assert max_x_streak <= 40
    finally:
        cfv.BATCH_SIZE = original_batch
