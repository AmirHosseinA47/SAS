"""Wind-aware victim search: spread-direction semantics and MAPE wiring."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
from common_fixed_variables import normalize_wind_direction, wind_vector_from_direction
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.managed.environment_bridge import EnvironmentBridge
from wildfire_model import WildFireModel


def test_wind_reads_runtime_wind_direction_from_common_fixed_variables() -> None:
    original = cfv.WIND_DIRECTION
    try:
        cfv.WIND_DIRECTION = "east"
        assert agents.Wind().wind_direction == "east"

        cfv.WIND_DIRECTION = "west"
        assert agents.Wind().wind_direction == "west"
    finally:
        cfv.WIND_DIRECTION = original


def test_wind_vector_from_direction_maps_cardinals() -> None:
    assert wind_vector_from_direction("north") == (0.0, 1.0)
    assert wind_vector_from_direction("south") == (0.0, -1.0)
    assert wind_vector_from_direction("east") == (1.0, 0.0)
    assert wind_vector_from_direction("west") == (-1.0, 0.0)
    assert wind_vector_from_direction("north") != wind_vector_from_direction("south")
    assert wind_vector_from_direction("east") != wind_vector_from_direction("west")


def test_wind_north_and_south_produce_different_targets() -> None:
    executor = UAVExecutor(uav_id="2502", model=None)
    agent = SimpleNamespace(pos=(10, 10), last_explanation=None)
    model = MagicMock()
    model.HEIGHT = 50
    model.WIDTH = 50
    model.height = 50
    model.width = 50
    model.evaluation_timesteps_counter = 5
    model.debug_log = False
    model._wind_aware_last_targets = {}
    model.schedule = SimpleNamespace(agents=[])
    model.environment_bridge = EnvironmentBridge()
    model.environment_bridge.update_wind(
        "north", (0.0, 1.0), 5.0, step=5, source="test"
    )

    def make_executor(wind: str) -> tuple[tuple[float, float] | None, UAVExecutor]:
        model.environment_bridge.update_wind(
            wind,
            wind_vector_from_direction(wind),
            5.0,
            step=5,
            source="test",
        )
        ex = UAVExecutor(uav_id="2502", model=model, agent=agent)
        ex._collect_active_fire_cells = lambda _m=None: {(20, 20)}  # type: ignore[method-assign]
        ex._read_fire_probability_map = lambda: {}  # type: ignore[method-assign]
        ex._sector_filtering_active = lambda _m: False  # type: ignore[method-assign]
        ex._cell_in_bounds = lambda cell: True  # type: ignore[method-assign]
        ex._victim_search_cell_is_safe = lambda cell: cell != (20, 20)  # type: ignore[method-assign]
        ex._cell_high_fire = lambda cell: cell == (20, 20)  # type: ignore[method-assign]
        ex._cell_smoke_obscured = lambda _cell: False  # type: ignore[method-assign]
        ex._min_hazard_distance = lambda _cell: 4.0  # type: ignore[method-assign]
        ex._visit_penalty = lambda _x, _y: 0.0  # type: ignore[method-assign]
        target = ex._wind_aware_victim_search_target(agent, model)
        return target, ex

    north_target, _ = make_executor("north")
    south_target, _ = make_executor("south")
    assert north_target is not None
    assert south_target is not None
    assert north_target[1] > south_target[1]


def test_wind_east_and_west_produce_different_targets() -> None:
    agent = SimpleNamespace(pos=(10, 10), last_explanation=None)
    model = MagicMock()
    model.HEIGHT = 50
    model.WIDTH = 50
    model.height = 50
    model.width = 50
    model.debug_log = False
    model._wind_aware_last_targets = {}
    model.environment_bridge = EnvironmentBridge()
    def target_for(wind: str) -> tuple[float, float] | None:
        model.environment_bridge.update_wind(
            wind,
            wind_vector_from_direction(wind),
            1.0,
            step=1,
            source="test",
        )
        ex = UAVExecutor(uav_id="2502", model=model, agent=agent)
        ex._collect_active_fire_cells = lambda _m=None: {(20, 20)}  # type: ignore[method-assign]
        ex._read_fire_probability_map = lambda: {}  # type: ignore[method-assign]
        ex._sector_filtering_active = lambda _m: False  # type: ignore[method-assign]
        ex._cell_in_bounds = lambda cell: True  # type: ignore[method-assign]
        ex._victim_search_cell_is_safe = lambda cell: cell != (20, 20)  # type: ignore[method-assign]
        ex._cell_high_fire = lambda cell: cell == (20, 20)  # type: ignore[method-assign]
        ex._cell_smoke_obscured = lambda _cell: False  # type: ignore[method-assign]
        ex._min_hazard_distance = lambda _cell: 4.0  # type: ignore[method-assign]
        ex._visit_penalty = lambda _x, _y: 0.0  # type: ignore[method-assign]
        return ex._wind_aware_victim_search_target(agent, model)

    east_target = target_for("east")
    west_target = target_for("west")
    assert east_target is not None
    assert west_target is not None
    assert east_target[0] > west_target[0]


def test_wind_aware_target_avoids_fire_and_smoke() -> None:
    agent = SimpleNamespace(pos=(5, 5), last_explanation=None)
    model = MagicMock()
    model.HEIGHT = 50
    model.WIDTH = 50
    model.environment_bridge = EnvironmentBridge()
    model.environment_bridge.update_wind("east", (1.0, 0.0), 0.0, source="test")
    model.debug_log = False
    model._wind_aware_last_targets = {}
    executor = UAVExecutor(uav_id="2502", model=model, agent=agent)
    executor._collect_active_fire_cells = lambda _m=None: {(20, 20)}  # type: ignore[method-assign]
    executor._read_fire_probability_map = lambda: {}  # type: ignore[method-assign]
    executor._sector_filtering_active = lambda _m: False  # type: ignore[method-assign]

    unsafe = (21, 20)
    executor._cell_high_fire = lambda cell: cell == unsafe  # type: ignore[method-assign]
    executor._cell_smoke_obscured = lambda cell: cell == (22, 20)  # type: ignore[method-assign]
    executor._cell_in_bounds = lambda cell: True  # type: ignore[method-assign]
    executor._victim_search_cell_is_safe = (  # type: ignore[method-assign]
        lambda cell: cell not in (unsafe, (22, 20), (20, 20))
    )
    executor._min_hazard_distance = lambda cell: 5.0  # type: ignore[method-assign]
    executor._visit_penalty = lambda _x, _y: 0.0  # type: ignore[method-assign]

    target = executor._wind_aware_victim_search_target(agent, model)
    assert target is not None
    assert target != (float(unsafe[0]), float(unsafe[1]))


def test_victim_search_wind_aware_action_when_downwind_exists() -> None:
    model = _fresh_model()
    vs_id = _victim_searcher_id(model)
    executor = UAVExecutor(uav_id=vs_id, model=model)
    agent = _uav_agent(model, vs_id)
    model.environment_bridge.update_wind(
        "north",
        (0.0, 1.0),
        1.0,
        step=1,
        source="test",
    )
    executor._wind_aware_victim_search_target = lambda _a, _m=None: (30.0, 40.0)  # type: ignore[method-assign]
    executor._apply_final_direction_safety = (  # type: ignore[method-assign]
        lambda ag, d, action_label="": (int(d), str(action_label))
    )
    executor._choose_best_direction = lambda _a, t, **_: 0  # type: ignore[method-assign]

    from src_extension.planning.decision_objects import PathDecision

    decision = PathDecision(
        decision_id="p-wind",
        uav_id=vs_id,
        next_action="explore_unknown_region",
    )
    chosen, label = executor._resolve_direction_intent(
        agent, decision, "victim", "explore_unknown_region"
    )
    assert label == "victim_search_wind_aware"
    assert chosen in range(4)


def test_fallback_exploring_when_no_wind_target() -> None:
    model = _fresh_model()
    vs_id = _victim_searcher_id(model)
    executor = UAVExecutor(uav_id=vs_id, model=model)
    agent = _uav_agent(model, vs_id)
    executor._wind_aware_victim_search_target = lambda _a, _m=None: None  # type: ignore[method-assign]
    executor._get_wind_direction = lambda _m=None: "north"  # type: ignore[method-assign]
    executor._init_wind_aware_sweep_state = (  # type: ignore[method-assign]
        lambda _model, pos, bounds, h, w, wind: {
            "sweep_x": 0,
            "sweep_y": 49,
            "sweep_dir": -1,
            "wind_direction": wind,
            "primary_axis": "y",
        }
    )
    executor._safe_victim_sweep_target = lambda *args, **kwargs: (1.0, 2.0)  # type: ignore[method-assign]
    executor._choose_best_direction = lambda _a, t, **_: 1  # type: ignore[method-assign]
    executor._apply_final_direction_safety = (  # type: ignore[method-assign]
        lambda ag, d, action_label="": (int(d), str(action_label))
    )
    executor._apply_victim_searcher_hazard_gate = (  # type: ignore[method-assign]
        lambda ag, d, action_label="": (int(d), str(action_label))
    )

    from src_extension.planning.decision_objects import PathDecision

    decision = PathDecision(decision_id="p-fb", uav_id=vs_id, next_action="hold")
    _, label = executor._resolve_direction_intent(agent, decision, "victim", "hold")
    assert label == "victim_search_wind_aware_sweep"


def test_explanation_recorded_for_wind_aware_search() -> None:
    agent = SimpleNamespace(pos=(1, 1), last_explanation=None)
    model = MagicMock()
    model.debug_log = False
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    executor._record_wind_aware_explanation(
        agent,
        wind_direction="east",
        target=(12.0, 8.0),
        model=model,
    )
    assert agent.last_explanation["decision"] == "victim_search_wind_aware"
    assert agent.last_explanation["wind_direction"] == "east"
    assert "downwind" in agent.last_explanation["reason"]


def test_sweep_initialization_differs_by_wind() -> None:
    executor = UAVExecutor(uav_id="0", model=None)
    model = MagicMock()
    model.HEIGHT = 50
    model.WIDTH = 50
    north = executor._init_wind_aware_sweep_state(
        model, None, None, 50, 50, "north"
    )
    south = executor._init_wind_aware_sweep_state(
        model, None, None, 50, 50, "south"
    )
    east = executor._init_wind_aware_sweep_state(
        model, None, None, 50, 50, "east"
    )
    west = executor._init_wind_aware_sweep_state(
        model, None, None, 50, 50, "west"
    )
    assert north["sweep_y"] > south["sweep_y"]
    assert east["sweep_x"] != west["sweep_x"]
    assert north["wind_direction"] == "north"
    assert west["sweep_x"] > east["sweep_x"]


def test_environment_bridge_update_and_summary() -> None:
    bridge = EnvironmentBridge()
    bridge.update_wind("south", (0.0, -1.0), 3.5, step=3, source="fire_model")
    summary = bridge.get_wind_summary()
    assert summary["direction"] == "south"
    assert summary["vector"] == [0.0, -1.0]
    assert summary["source"] == "fire_model"
    assert summary["step"] == 3


def test_wildfire_model_syncs_wind_to_bridge() -> None:
    model = _fresh_model()
    model.wind.wind_direction = "west"
    model._sync_environment_wind(7.0)
    summary = model.environment_bridge.get_wind_summary()
    assert summary["direction"] == "west"
    assert summary["vector"] == [-1.0, 0.0]


def _fresh_model() -> WildFireModel:
    return WildFireModel()


def _victim_searcher_id(model: WildFireModel) -> str:
    for uid, state in model.managed_uav_states.items():
        if getattr(state, "role", "") == "victim_searcher":
            return str(uid)
    raise AssertionError("no victim_searcher")


def _uav_agent(model: WildFireModel, uav_id: str) -> agents.UAV:
    for agent in model.schedule.agents:
        if type(agent) is agents.UAV and str(agent.unique_id) == str(uav_id):
            return agent
    raise AssertionError(f"uav {uav_id} not found")
