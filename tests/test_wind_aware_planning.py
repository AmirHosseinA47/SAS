"""Wind-aware victim search planning: adaptation option → planner → executor."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("MPLBACKEND", "Agg")

from common_fixed_variables import wind_vector_from_direction
from src_extension.adaptation.local_adaptation_generator import LocalAdaptationSpaceGenerator
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.monitoring.monitoring_interfaces import GlobalObservationSnapshot
from src_extension.planning.decision_objects import PathDecision
from src_extension.planning.local_uav_path_planner import LocalUAVPathPlanner


def _runtime_models(
    *,
    wind: str,
    fire_cells: set[tuple[int, int]] | None = None,
    smoke_cells: set[tuple[int, int]] | None = None,
    victims: dict | None = None,
    uav_pos: tuple[float, float] = (10.0, 10.0),
) -> dict:
    fire_cells = fire_cells or {(20, 20)}
    sim = MagicMock()
    sim.HEIGHT = 50
    sim.WIDTH = 50
    sim.height = 50
    sim.width = 50
    sim.schedule = SimpleNamespace(agents=[])
    sim.managed_victims = {}

    fire_map = {cell: 0.6 for cell in fire_cells}
    fire_runtime = SimpleNamespace(
        fire_probability_map=fire_map,
        belief=SimpleNamespace(fire_probability_map=fire_map),
    )
    smoke = smoke_cells or set()
    visibility = SimpleNamespace(smoke_obscured_cells=smoke)

    resource = SimpleNamespace(
        by_uav_id={
            "2502": SimpleNamespace(
                current_role="victim_searcher",
                current_position=uav_pos,
            )
        }
    )
    victim_runtime = SimpleNamespace(victims=victims or {})

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
        "victim_runtime_model": victim_runtime,
        "uav_resource_model": resource,
        "global_observation_snapshot": snapshot,
        "uav_id": "2502",
    }


def _generate_wind_option(wind: str) -> object | None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind=wind)
    local_input = {"target_entity": "2502", "triggers": []}
    options = gen._generate_path_options(local_input, {}, runtime, 1.0)
    for opt in options:
        if getattr(opt, "option_id", "") == "wind_aware_victim_search":
            return opt
    return None


def test_local_adaptation_generator_emits_wind_aware_option() -> None:
    opt = _generate_wind_option("north")
    assert opt is not None
    assert opt.option_id == "wind_aware_victim_search"


def test_cardinal_winds_produce_different_option_targets() -> None:
    targets: dict[str, tuple[float, float]] = {}
    for wind in ("north", "south", "east", "west"):
        opt = _generate_wind_option(wind)
        assert opt is not None
        params = opt.parameters
        target = params["target_position"]
        targets[wind] = (float(target[0]), float(target[1]))
    assert targets["north"][1] > targets["south"][1]
    assert targets["east"][0] > targets["west"][0]


def test_wind_option_includes_required_parameters() -> None:
    opt = _generate_wind_option("east")
    assert opt is not None
    params = opt.parameters
    assert params.get("wind_direction") == "east"
    assert params.get("wind_vector") is not None
    assert params.get("target_position") is not None
    assert params.get("search_policy") == "wind_aware"


def test_executor_consumes_planner_generated_option() -> None:
    opt = _generate_wind_option("north")
    assert opt is not None
    params = opt.parameters
    target = params["target_position"]
    decision = PathDecision(
        decision_id="p-2502-1",
        uav_id="2502",
        selected_option_id="wind_aware_victim_search",
        next_action="victim_search_wind_aware",
        uncertainty_context={
            "target_position": target,
            "wind_direction": "north",
            "search_policy": "wind_aware",
            "source": "local_adaptation_generator",
        },
    )
    agent = SimpleNamespace(pos=(10, 10), last_explanation=None)
    model = MagicMock()
    model.HEIGHT = 50
    model.WIDTH = 50
    executor = UAVExecutor(uav_id="2502", model=model, agent=agent)
    executor._victim_search_cell_is_safe = lambda _cell: True  # type: ignore[method-assign]
    executor._cell_high_fire = lambda _cell: False  # type: ignore[method-assign]
    executor._cell_smoke_obscured = lambda _cell: False  # type: ignore[method-assign]

    parsed = executor._planner_wind_aware_target_from_decision(decision)
    assert parsed is not None
    planner_target, _meta = parsed
    assert planner_target == (float(target[0]), float(target[1]))


def test_executor_fallback_wind_aware_when_planner_option_absent() -> None:
    agent = SimpleNamespace(pos=(10, 10), last_explanation=None)
    model = MagicMock()
    model.HEIGHT = 50
    model.WIDTH = 50
    model.debug_log = False
    model._wind_aware_last_targets = {}
    model.environment_bridge = MagicMock()
    model.environment_bridge.get_wind_summary.return_value = {
        "direction": "north",
        "vector": (0.0, 1.0),
    }
    model.schedule = SimpleNamespace(agents=[])
    executor = UAVExecutor(uav_id="2502", model=model, agent=agent)
    executor._collect_active_fire_cells = lambda _m=None: {(20, 20)}  # type: ignore[method-assign]
    executor._read_fire_probability_map = lambda: {}  # type: ignore[method-assign]
    executor._sector_filtering_active = lambda _m: False  # type: ignore[method-assign]
    executor._cell_in_bounds = lambda cell: True  # type: ignore[method-assign]
    executor._victim_search_cell_is_safe = lambda cell: cell != (20, 20)  # type: ignore[method-assign]
    executor._cell_high_fire = lambda cell: cell == (20, 20)  # type: ignore[method-assign]
    executor._cell_smoke_obscured = lambda _cell: False  # type: ignore[method-assign]
    executor._min_hazard_distance = lambda _cell: 4.0  # type: ignore[method-assign]
    executor._visit_penalty = lambda _x, _y: 0.0  # type: ignore[method-assign]

    decision = PathDecision(decision_id="p-2502-0", uav_id="2502")
    assert executor._planner_wind_aware_target_from_decision(decision) is None
    fallback = executor._wind_aware_victim_search_target(agent, model)
    assert fallback is not None


def test_generated_targets_avoid_fire_and_smoke() -> None:
    fire = {(20, 20)}
    smoke = {(22, 22)}
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(wind="east", fire_cells=fire, smoke_cells=smoke)
    options = gen._generate_path_options(
        {"target_entity": "2502", "triggers": []}, {}, runtime, 1.0
    )
    opt = next(
        (
            o
            for o in options
            if getattr(o, "option_id", "") == "wind_aware_victim_search"
        ),
        None,
    )
    assert opt is not None
    target = opt.parameters["target_position"]
    cell = (int(round(target[0])), int(round(target[1])))
    assert cell not in fire
    assert cell not in smoke


def test_planner_explanation_source_is_planner() -> None:
    agent = SimpleNamespace(pos=(5, 5), last_explanation=None)
    model = MagicMock()
    model.debug_log = False
    executor = UAVExecutor(uav_id="2502", model=model, agent=agent)
    executor._record_wind_aware_explanation(
        agent,
        wind_direction="north",
        target=(12.0, 18.0),
        model=model,
        source="planner",
        reason="planner selected safe downwind search target",
    )
    assert agent.last_explanation["source"] == "planner"
    assert agent.last_explanation["decision"] == "victim_search_wind_aware"


def test_known_victim_target_overrides_wind_aware_exploration() -> None:
    gen = LocalAdaptationSpaceGenerator()
    runtime = _runtime_models(
        wind="north",
        victims={
            "v1": {
                "position": (15.0, 15.0),
                "status": "detected",
            }
        },
    )
    options = gen._generate_path_options(
        {"target_entity": "2502", "triggers": []}, {}, runtime, 1.0
    )
    wind_opts = [
        o for o in options if getattr(o, "option_id", "") == "wind_aware_victim_search"
    ]
    victim_opts = [
        o
        for o in options
        if "victim" in str(getattr(o, "parameters", {}).get("path_action", ""))
    ]
    assert len(wind_opts) == 0
    assert len(victim_opts) >= 1

    planner = LocalUAVPathPlanner(uav_id="2502")
    from src_extension.adaptation.adaptation_results import LocalAdaptationSpace

    space = LocalAdaptationSpace(options=options, trigger_references=[], explanation_summaries=[], timestamp=1.0)
    decision = planner.plan(0, local_adaptation_space=space, runtime_models=runtime)
    assert decision is not None
    assert decision.selected_option_id != "wind_aware_victim_search"
