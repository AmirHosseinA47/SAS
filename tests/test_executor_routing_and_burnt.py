"""Executor pathfinding on retarget branches and permanent burnt Fire cells."""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import main
from common_fixed_variables import BURNING_RATE, FIRE_SPREAD_SPEED, VEGETATION_COLORS
from src_extension.adaptation.local_adaptation_generator import _wind_search_state
from src_extension.execution.uav_executor import BFS_ESCAPE_MAX_DEPTH, UAVExecutor
from src_extension.planning.decision_objects import PathDecision

from test_uav_executor import _FakeAgent, _bfs_test_model, _next_pos


def _manhattan(a: tuple[int, int], b: tuple[float, float]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _wind_retarget_model(
    *,
    fire_cells: set[tuple[int, int]] | None = None,
    smoke_cells: set[tuple[int, int]] | None = None,
    uav_id: str = "2501",
) -> object:
    model = _bfs_test_model(fire_cells=fire_cells, smoke_cells=smoke_cells)
    model.managed_uav_states = {
        uav_id: SimpleNamespace(
            role="victim_searcher",
            position=(45.0, 38.0),
        )
    }
    model._wind_search_target_state = {}
    model._victim_sweep_state = {}
    return model


def _retarget_direction(
    executor: UAVExecutor,
    agent: _FakeAgent,
    model: object,
    *,
    wind_target: tuple[float, float] = (8.0, 8.0),
) -> tuple[int, str]:
    ws = _wind_search_state(model, executor.uav_id)
    ws["force_coverage_escape"] = True
    ws["force_interior_retarget"] = True
    ws["pocket_streak"] = 25
    executor._wind_aware_victim_search_target = (  # type: ignore[method-assign]
        lambda _a, _m=None: wind_target
    )
    executor._get_wind_direction = lambda _m=None: "east"  # type: ignore[method-assign]
    decision = PathDecision(
        decision_id="retarget-test",
        uav_id=executor.uav_id,
        selected_option_id="wind_aware_victim_search",
        next_action="victim_search_wind_aware",
        uncertainty_context={
            "force_wind_retarget": True,
            "force_coverage_escape": True,
            "target_position": wind_target,
        },
    )
    return executor._resolve_direction_intent(
        agent, decision, "victim", "victim_search_wind_aware",
    )


def test_retarget_routes_around_smoke() -> None:
    agent = _FakeAgent(unique_id=2501, pos=(45, 38))
    smoke_wall = {(44, 38), (43, 38), (42, 38), (41, 38), (40, 38)}
    model = _wind_retarget_model(smoke_cells=smoke_wall)
    executor = UAVExecutor(uav_id="2501", model=model, agent=agent)
    wind_target = (8.0, 8.0)

    chosen, label = _retarget_direction(executor, agent, model, wind_target=wind_target)

    next_cell = _next_pos(agent.pos, chosen)
    assert executor._strict_victim_hazard_level(next_cell) == 0
    assert next_cell not in smoke_wall
    assert next_cell != (44, 38)
    escape_method = str(getattr(executor, "_last_escape_method", "") or "")
    assert escape_method.startswith("bfs") or escape_method == "greedy"
    assert label in {
        "victim_search_wind_aware_retarget_to_interior",
        "victim_search_escape_bfs",
    }
    retreat = executor._retreat_to_safe_interior_direction(agent)
    if retreat is not None:
        assert chosen != retreat or _manhattan(
            _next_pos(agent.pos, chosen), wind_target
        ) < _manhattan(agent.pos, wind_target)


def test_bfs_escape_reaches_far_target() -> None:
    agent = _FakeAgent(unique_id=0, pos=(45, 38))
    model = _bfs_test_model()
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (8.0, 8.0)

    direction = executor._bfs_escape_direction(
        agent, target, avoid_smoke=True, max_depth=BFS_ESCAPE_MAX_DEPTH,
    )

    assert direction is not None
    assert executor._strict_victim_hazard_level(_next_pos(agent.pos, direction)) == 0


def test_bfs_depth_30_fails_but_100_succeeds() -> None:
    agent = _FakeAgent(unique_id=0, pos=(45, 38))
    model = _bfs_test_model()
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (8.0, 8.0)

    shallow = executor._bfs_escape_direction(
        agent, target, avoid_smoke=True, max_depth=30,
    )
    deep = executor._bfs_escape_direction(
        agent, target, avoid_smoke=True, max_depth=BFS_ESCAPE_MAX_DEPTH,
    )

    assert shallow is None
    assert deep is not None


def test_forced_progress_uses_deep_bfs_for_far_target() -> None:
    agent = _FakeAgent(unique_id=0, pos=(45, 38))
    model = _bfs_test_model(fire_cells={(44, 38)})
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)

    direction = executor._forced_progress_direction(agent, (8.0, 8.0))

    assert direction is not None
    assert str(getattr(executor, "_last_escape_method", "")).startswith("bfs")


def _fire_model_stub() -> object:
    return type(
        "FireModelStub",
        (),
        {
            "grid": type(
                "Grid",
                (),
                {
                    "get_neighborhood": lambda *a, **k: [],
                    "get_cell_list_contents": lambda *a, **k: [],
                },
            )(),
            "wind": SimpleNamespace(apply_wind=lambda p, *a: p),
        },
    )()


def test_fire_cell_becomes_burnt_when_fuel_depleted() -> None:
    model = _fire_model_stub()
    fire = agents.Fire(unique_id=1, model=model, burning=True)
    fire.fuel = BURNING_RATE
    fire.steps_counter = FIRE_SPREAD_SPEED - 1

    fire.step()
    fire.advance()

    assert fire.is_burnt()
    assert not fire.is_burning()


def test_burnt_cell_never_reignites() -> None:
    model = _fire_model_stub()
    fire = agents.Fire(unique_id=2, model=model, burning=False)
    fire.burnt = True
    fire.fuel = 0

    for offset in range(FIRE_SPREAD_SPEED * 5):
        fire.steps_counter = offset
        if offset % FIRE_SPREAD_SPEED == FIRE_SPREAD_SPEED - 1:
            fire.step()
        if offset % FIRE_SPREAD_SPEED == 0 and offset > 0:
            fire.advance()

    assert fire.is_burnt()
    assert not fire.is_burning()


def test_burnt_cell_portrayal_is_not_green() -> None:
    model = _fire_model_stub()
    fire = agents.Fire(unique_id=3, model=model, burning=False)
    fire.burnt = True
    fire.fuel = 0
    fire.smoke = agents.Smoke(fire_cell_fuel=0)

    portrayal = main.agent_portrayal(fire)

    assert portrayal["Color"] == "#2b2b2b"
    assert portrayal["Color"] not in VEGETATION_COLORS


def test_burned_cell_renders_dark_not_green_when_fire_stops() -> None:
    model = _fire_model_stub()
    fire = agents.Fire(unique_id=6, model=model, burning=False)
    fire.has_burned = True
    fire.fuel = BURNING_RATE * 3
    fire.burnt = False
    fire.smoke = agents.Smoke(fire_cell_fuel=fire.fuel)

    portrayal = main.agent_portrayal(fire)

    assert not fire.is_burning()
    assert not fire.is_burnt()
    # Scorched ground (has_burned, fuel remaining, not burning) re-ignites 96.6%
    # of the time; burnt ground is absorbing and never does. They must not share
    # a colour - an operator reading the map has to be able to tell them apart.
    assert portrayal["Color"] == "#895e00"
    assert portrayal["Color"] != "#2b2b2b"
    assert portrayal["Color"] not in VEGETATION_COLORS


def test_has_burned_cell_with_fuel_may_reignite() -> None:
    from unittest.mock import patch

    model = _fire_model_stub()
    fire = agents.Fire(unique_id=7, model=model, burning=False)
    fire.has_burned = True
    fire.fuel = BURNING_RATE * 3
    fire.burnt = False
    fire.steps_counter = FIRE_SPREAD_SPEED - 1
    fire.probability_of_fire = lambda: 1.0  # type: ignore[method-assign]

    with patch("agents.random.random", return_value=0.0):
        fire.step()
    fire.advance()

    assert not fire.is_burnt()
    assert fire.next_burning_state is True
    assert fire.is_burning()


def test_cell_becomes_burnt_only_when_fuel_depleted() -> None:
    model = _fire_model_stub()
    fire = agents.Fire(unique_id=8, model=model, burning=True)
    fire.has_burned = True
    fire.fuel = BURNING_RATE
    fire.steps_counter = FIRE_SPREAD_SPEED - 1

    fire.step()
    fire.advance()

    assert fire.is_burnt()
    assert not fire.is_burning()
    assert fire.fuel <= 0

    fire.cell_prob = 1.0
    for offset in range(FIRE_SPREAD_SPEED * 5):
        fire.steps_counter = FIRE_SPREAD_SPEED + offset
        if fire.steps_counter % FIRE_SPREAD_SPEED == 0:
            fire.step()
            fire.advance()

    assert fire.is_burnt()
    assert not fire.is_burning()


def test_has_burned_cell_may_stop_burning_before_fuel_depleted() -> None:
    model = _fire_model_stub()
    fire = agents.Fire(unique_id=9, model=model, burning=True)
    fire.has_burned = True
    fire.fuel = BURNING_RATE * 5
    fire.steps_counter = FIRE_SPREAD_SPEED - 1
    fire.cell_prob = 0.0

    fire.step()
    fire.advance()

    assert fire.has_burned
    assert not fire.is_burnt()
    assert not fire.is_burning()
    assert fire.fuel > 0


def test_fire_self_limits_does_not_burn_whole_map() -> None:
    import random

    import common_fixed_variables as cfv
    import wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    from wildfire_model import WildFireModel

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
        BATCH_SIZE=300,
        FIXED_WIND=True,
        WIND_DIRECTION="east",
    )
    model = WildFireModel()
    for _ in range(150):
        model.step()

    green_vegetation = [
        color for color in VEGETATION_COLORS if color != "#414141"
    ]
    burnt_count = 0
    has_burned_not_burnt = 0
    unburned_vegetation = 0
    green_has_burned = 0
    re_ignited_burnt = 0
    for agent in model.schedule.agents:
        if type(agent) is not agents.Fire:
            continue
        if agent.is_burnt():
            burnt_count += 1
        elif getattr(agent, "has_burned", False):
            has_burned_not_burnt += 1
            if not agent.is_burning():
                portrayal = main.agent_portrayal(agent)
                if portrayal.get("Color") in green_vegetation:
                    green_has_burned += 1
        elif not agent.is_burning():
            unburned_vegetation += 1
        if agent.is_burnt() and agent.is_burning():
            re_ignited_burnt += 1

    grid_cells = int(getattr(model, "width", 0) or getattr(model, "WIDTH", 50)) * int(
        getattr(model, "height", 0) or getattr(model, "HEIGHT", 50)
    )
    assert burnt_count < 1500, f"burnt_count={burnt_count} too high for 50x50 grid"
    assert unburned_vegetation > 0, "expected meaningful unburned vegetation"
    assert green_has_burned == 0
    assert re_ignited_burnt == 0
    assert burnt_count + has_burned_not_burnt + unburned_vegetation <= grid_cells

