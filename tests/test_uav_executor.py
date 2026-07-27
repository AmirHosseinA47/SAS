"""UAV executor: direction mapping, waypoints, search mode."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any
import pytest

import agents
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.planning.decision_objects import FailSafeDecision, PathDecision


@dataclass
class _FakeAgent:
    unique_id: int
    pos: tuple[int, int]
    selected_dir: int = 0
    move_called: bool = False

    def move(self) -> bool:
        self.move_called = True
        return False


@dataclass
class _FakeFireRuntimeModel:
    target: tuple[float, float] | None = (7.0, 3.0)
    calls: list[dict[str, object]] = field(default_factory=list)

    def get_best_search_target(
        self,
        current_time: float | None = None,
        min_conf: float = 0.3,
        **kwargs: Any,
    ) -> tuple[float, float] | None:
        self.calls.append(
            {"current_time": current_time, "min_conf": min_conf, **kwargs}
        )
        return self.target


@dataclass
class _FakeModel:
    fire_runtime_model: _FakeFireRuntimeModel
    evaluation_timesteps_counter: float = 10.0


def _path_decision(**overrides: object) -> PathDecision:
    base: dict[str, object] = {
        "decision_id": "path-1",
        "uav_id": "0",
        "next_action": "",
        "waypoints_by_uav": {},
        "path_segment": (),
    }
    base.update(overrides)
    return PathDecision(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("action", "expected_dir"),
    [
        ("east", 0),
        ("south", 1),
        ("west", 2),
        ("north", 3),
    ],
)
def test_uav_executor_maps_cardinal_actions(action: str, expected_dir: int) -> None:
    agent = _FakeAgent(unique_id=0, pos=(4, 4), selected_dir=2)
    executor = UAVExecutor(uav_id="0", agent=agent)
    decision = _path_decision(next_action=action)

    result = executor.execute(decision, timestamp=1.0)

    assert agent.selected_dir == expected_dir
    assert result["selected_dir"] == expected_dir
    assert result["applied"] is True


def test_uav_executor_hold_preserves_selected_dir() -> None:
    agent = _FakeAgent(unique_id=0, pos=(4, 4), selected_dir=2)
    executor = UAVExecutor(uav_id="0", agent=agent)
    decision = _path_decision(next_action="hold")

    result = executor.execute(decision, timestamp=1.0)

    assert agent.selected_dir == 2
    assert result["action"] == "hold"
    assert result["selected_dir"] == 2


def test_uav_executor_uses_waypoint_for_selected_dir() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=3)
    executor = UAVExecutor(uav_id="0", agent=agent)
    decision = _path_decision(
        waypoints_by_uav={"0": ((8.0, 5.0),)},
    )

    result = executor.execute(decision, timestamp=1.0)

    assert agent.selected_dir == 0
    assert result["action"] == "waypoint"
    assert result["selected_dir"] == 0


def test_uav_executor_does_not_move_uav_position() -> None:
    agent = _FakeAgent(unique_id=0, pos=(10, 12), selected_dir=1)
    executor = UAVExecutor(uav_id="0", agent=agent)
    before = agent.pos

    executor.execute(_path_decision(next_action="north"), timestamp=1.0)

    assert agent.pos == before
    assert agent.move_called is False


def test_search_mode_steers_toward_get_best_search_target() -> None:
    fire_runtime = _FakeFireRuntimeModel(target=(9.0, 5.0))
    model = _FakeModel(fire_runtime_model=fire_runtime)
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    fail_safe = FailSafeDecision(
        decision_id="fs-1",
        search_mode_active=True,
        target_region="",
    )

    result = executor.execute(
        None,
        timestamp=3.0,
        fail_safe_decision=fail_safe,
    )

    assert fire_runtime.calls
    assert result["applied"] is True
    assert result["action"] == "search_mode"
    assert result["search_target"] == (9.0, 5.0)
    assert agent.selected_dir == 0
    assert agent.pos == (5, 5)


def test_uav_move_no_longer_calls_knowledge_fallback_bias() -> None:
    assert not hasattr(agents.UAV, "_apply_knowledge_fallback_bias")
    move_source = inspect.getsource(agents.UAV.move)
    assert "_apply_knowledge_fallback_bias" not in move_source


@dataclass
class _FakeGrid:
    width: int = 30
    height: int = 30

    def out_of_bounds(self, pos: tuple[int, int]) -> bool:
        return pos[0] < 0 or pos[1] < 0 or pos[0] >= self.width or pos[1] >= self.height


def _simulate_uav_stuck_count_update(
    before_positions: dict[str, tuple[int, int]],
    agents: list[object],
    stuck_counts: dict[str, int],
) -> None:
    for agent in agents:
        if type(agent).__name__ != "UAV":
            continue
        uid = str(getattr(agent, "unique_id", ""))
        pos = getattr(agent, "pos", None)
        if pos is None:
            continue
        after_pos = (int(pos[0]), int(pos[1]))
        before_pos = before_positions.get(uid)
        if (
            before_pos is not None
            and before_pos[0] == after_pos[0]
            and before_pos[1] == after_pos[1]
        ):
            stuck_counts[uid] = int(stuck_counts.get(uid, 0) or 0) + 1
        else:
            stuck_counts[uid] = 0


def _victim_executor_model(
    *,
    fire_map: dict[tuple[int, int], float] | None = None,
    smoke_cells: set[tuple[int, int]] | None = None,
    stuck_count: int = 0,
    failed_dir: int = -1,
    victim_pos: tuple[float, float] = (12.0, 12.0),
) -> object:
    smoke_cells = smoke_cells or set()
    fire_map = fire_map or {}

    class _VisibilityState:
        observation_status_map = {
            cell: type("Status", (), {"value": "smoke_obscured"})()
            for cell in smoke_cells
        }

    class _VisibilityModel:
        state = _VisibilityState()

    class _FireBelief:
        fire_probability_map = fire_map

    class _FireRuntime:
        belief = _FireBelief()
        fire_probability_map = fire_map

    class _VictimRuntime:
        victims = {
            "victim_0": type(
                "Victim",
                (),
                {"estimated_position": victim_pos},
            )()
        }

    return type(
        "VictimTestModel",
        (),
        {
            "grid": _FakeGrid(),
            "fire_runtime_model": _FireRuntime(),
            "visibility_model": _VisibilityModel(),
            "victim_runtime_model": _VictimRuntime(),
            "_uav_stuck_counts": {"0": int(stuck_count)},
            "_victim_escape_memory": {},
            "uav_last_failed_dir": {"0": failed_dir},
            "uav_visit_counts": {},
            "managed_uav_states": {},
        },
    )()


def _manhattan(agent_pos: tuple[int, int], target: tuple[float, float]) -> float:
    return abs(agent_pos[0] - target[0]) + abs(agent_pos[1] - target[1])


def _next_pos(agent_pos: tuple[int, int], direction: int) -> tuple[int, int]:
    move_x = [1, 0, -1, 0]
    move_y = [0, -1, 0, 1]
    return (
        agent_pos[0] + move_x[direction],
        agent_pos[1] + move_y[direction],
    )


def _resolve_victim_direction(
    executor: UAVExecutor,
    agent: _FakeAgent,
    model: object,
    *,
    action: str = "move_toward_victim_candidate",
) -> tuple[int, str]:
    executor._model = model
    executor._agent = agent
    return executor._resolve_direction_intent(
        agent,
        _path_decision(next_action=action),
        "victim",
        action,
    )


def test_stuck_count_below_two_uses_normal_victim_routing() -> None:
    agent = _FakeAgent(unique_id=0, pos=(25, 25), selected_dir=2)
    model = _victim_executor_model(stuck_count=1)
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (12.0, 12.0)

    expected = executor._choose_best_direction(agent, target, target_kind="victim")
    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "computed_from_target"
    assert chosen == expected


def test_stuck_victim_uav_escapes_repeated_position() -> None:
    agent = _FakeAgent(unique_id=0, pos=(25, 25), selected_dir=2)
    model = _victim_executor_model(stuck_count=2)
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (12.0, 12.0)

    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "victim_stuck_escape"
    assert _manhattan(_next_pos(agent.pos, chosen), target) < _manhattan(agent.pos, target)


def test_stuck_victim_uav_avoids_fire() -> None:
    agent = _FakeAgent(unique_id=0, pos=(10, 10), selected_dir=0)
    target = (5.0, 10.0)
    model = _victim_executor_model(
        stuck_count=2,
        victim_pos=target,
        fire_map={(9, 10): 0.95},
    )
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)

    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "victim_stuck_escape"
    assert chosen != 2
    assert _next_pos(agent.pos, chosen) != (9, 10)


def test_stuck_victim_uav_avoids_smoke() -> None:
    agent = _FakeAgent(unique_id=0, pos=(10, 10), selected_dir=0)
    target = (5.0, 10.0)
    model = _victim_executor_model(
        stuck_count=2,
        victim_pos=target,
        smoke_cells={(9, 10)},
    )
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)

    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "victim_stuck_escape"
    assert chosen != 2
    assert _next_pos(agent.pos, chosen) != (9, 10)


def test_stuck_victim_uav_changes_selected_dir() -> None:
    agent = _FakeAgent(unique_id=0, pos=(10, 10), selected_dir=2)
    model = _victim_executor_model(stuck_count=2, victim_pos=(10.0, 5.0))
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)

    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "victim_stuck_escape"
    assert chosen != agent.selected_dir


def test_non_stuck_victim_routing_unchanged() -> None:
    agent = _FakeAgent(unique_id=0, pos=(10, 10), selected_dir=2)
    model = _victim_executor_model(stuck_count=0)
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (12.0, 12.0)

    expected = executor._choose_best_direction(agent, target, target_kind="victim")
    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "computed_from_target"
    assert chosen == expected


def test_moving_uav_resets_stuck_count() -> None:
    UAV = type("UAV", (), {})
    agent = UAV()
    agent.unique_id = 0
    agent.pos = (10, 10)
    stuck_counts: dict[str, int] = {"0": 3}
    before = {"0": (10, 10)}
    agent.pos = (11, 10)

    _simulate_uav_stuck_count_update(before, [agent], stuck_counts)

    assert stuck_counts["0"] == 0


def test_victim_oscillation_activates_escape_committed() -> None:
    agent = _FakeAgent(unique_id=0, pos=(28, 22), selected_dir=0)
    model = _victim_executor_model(victim_pos=(12.5, 12.5))
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)

    _resolve_victim_direction(executor, agent, model)
    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "victim_escape_committed"
    mem = getattr(model, "_victim_escape_memory", {}).get("0", {})
    assert mem.get("escape_steps_remaining") == 5
    assert mem.get("escape_dir") == chosen


def test_victim_escape_memory_continues_same_direction() -> None:
    agent = _FakeAgent(unique_id=0, pos=(28, 22), selected_dir=0)
    model = _victim_executor_model(victim_pos=(12.5, 12.5))
    model._victim_escape_memory = {
        "0": {
            "escape_dir": 1,
            "escape_steps_remaining": 3,
            "last_dist_to_target": 25.5,
        }
    }
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)

    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "victim_escape_committed"
    assert chosen == 1
    assert model._victim_escape_memory["0"]["escape_steps_remaining"] == 2


def test_victim_escape_memory_clears_after_significant_progress() -> None:
    agent = _FakeAgent(unique_id=0, pos=(20, 20), selected_dir=0)
    model = _victim_executor_model(victim_pos=(12.0, 12.0))
    model._victim_escape_memory = {
        "0": {
            "escape_dir": 1,
            "escape_steps_remaining": 4,
            "last_dist_to_target": 20.0,
        }
    }
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (12.0, 12.0)
    expected = executor._choose_best_direction(agent, target, target_kind="victim")

    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "computed_from_target"
    assert chosen == expected
    mem = model._victim_escape_memory["0"]
    assert mem["escape_steps_remaining"] == 0
    assert mem["escape_dir"] is None


def test_victim_oscillation_prefers_safe_over_hazardous() -> None:
    agent = _FakeAgent(unique_id=0, pos=(15, 12), selected_dir=0)
    target = (5.0, 12.0)
    model = _victim_executor_model(
        victim_pos=target,
        fire_map={(14, 12): 0.95},
    )
    model._victim_escape_memory = {
        "0": {
            "escape_dir": None,
            "escape_steps_remaining": 0,
            "last_dist_to_target": _manhattan(agent.pos, target),
        }
    }
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)

    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "victim_escape_committed"
    assert chosen != 2
    assert _next_pos(agent.pos, chosen) != (14, 12)


def test_victim_non_oscillating_routing_uses_computed_from_target() -> None:
    agent = _FakeAgent(unique_id=0, pos=(25, 25), selected_dir=2)
    model = _victim_executor_model(stuck_count=0)
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (12.0, 12.0)
    expected = executor._choose_best_direction(agent, target, target_kind="victim")

    chosen, label = _resolve_victim_direction(executor, agent, model)

    assert label == "computed_from_target"
    assert chosen == expected


def test_blocked_uav_increments_stuck_count() -> None:
    UAV = type("UAV", (), {})
    agent = UAV()
    agent.unique_id = 0
    agent.pos = (10, 10)
    stuck_counts: dict[str, int] = {}
    before = {"0": (10, 10)}

    _simulate_uav_stuck_count_update(before, [agent], stuck_counts)
    assert stuck_counts["0"] == 1

    _simulate_uav_stuck_count_update(before, [agent], stuck_counts)
    assert stuck_counts["0"] == 2


def _bfs_test_model(
    *,
    fire_cells: set[tuple[int, int]] | None = None,
    smoke_cells: set[tuple[int, int]] | None = None,
    height: int = 50,
    width: int = 50,
) -> object:
    fire_cells = fire_cells or set()
    smoke_cells = smoke_cells or set()

    class _Grid:
        def out_of_bounds(self, cell: tuple[int, int]) -> bool:
            return not (0 <= cell[0] < height and 0 <= cell[1] < width)

    class _VisibilityState:
        observation_status_map = {
            cell: type("Status", (), {"value": "smoke_obscured"})()
            for cell in smoke_cells
        }

    class _VisibilityModel:
        smoke_obscured_cells = set(smoke_cells)
        state = _VisibilityState()

    base = type("BaseModel", (), {"HEIGHT": height, "WIDTH": width, "grid": _Grid()})()
    fires: list[object] = []
    for idx, cell in enumerate(sorted(fire_cells)):
        fire = agents.Fire(unique_id=1000 + idx, model=base, burning=True)
        fire.pos = cell
        fires.append(fire)

    return type(
        "BfsTestModel",
        (),
        {
            "HEIGHT": height,
            "WIDTH": width,
            "grid": _Grid(),
            "schedule": type("Schedule", (), {"agents": fires})(),
            "visibility_model": _VisibilityModel(),
            "fire_runtime_model": type("FR", (), {"fire_probability_map": {}})(),
        },
    )()


def test_bfs_escape_finds_path_around_fire_wall() -> None:
    agent = _FakeAgent(unique_id=0, pos=(4, 25))
    model = _bfs_test_model(
        fire_cells={(5, 25)},
        smoke_cells={(4, 24)},
    )
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (24.0, 24.0)

    direction = executor._bfs_escape_direction(agent, target, avoid_smoke=True, max_depth=30)

    assert direction is not None
    next_cell = _next_pos(agent.pos, direction)
    assert next_cell not in {(5, 25), (4, 24)}
    assert executor._strict_victim_hazard_level(next_cell) == 0


def test_bfs_escape_returns_none_when_fully_enclosed() -> None:
    agent = _FakeAgent(unique_id=0, pos=(10, 10))
    model = _bfs_test_model(
        fire_cells={(11, 10), (9, 10), (10, 11), (10, 9)},
    )
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)

    direction = executor._bfs_escape_direction(
        agent, (20.0, 20.0), avoid_smoke=True, max_depth=30,
    )

    assert direction is None


def test_bfs_smoke_fallback_can_ignore_smoke_when_needed() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 10))
    model = _bfs_test_model(
        fire_cells={(4, 10), (5, 9), (5, 11), (6, 9), (6, 11)},
        smoke_cells={(6, 10)},
    )
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (8.0, 10.0)

    safe_dir = executor._bfs_escape_direction(agent, target, avoid_smoke=True, max_depth=30)
    smoke_dir = executor._bfs_escape_direction(agent, target, avoid_smoke=False, max_depth=30)

    assert safe_dir is None
    assert smoke_dir is not None
    assert smoke_dir == 0
    assert _next_pos(agent.pos, smoke_dir) == (6, 10)


def test_forced_progress_uses_bfs_when_greedy_fails() -> None:
    agent = _FakeAgent(unique_id=0, pos=(4, 25))
    model = _bfs_test_model(
        fire_cells={(5, 25)},
        smoke_cells={(4, 24)},
    )
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    target = (24.0, 24.0)

    direction = executor._forced_progress_direction(agent, target)

    assert direction is not None
    assert str(getattr(executor, "_last_escape_method", "")).startswith("bfs")
    next_cell = _next_pos(agent.pos, direction)
    assert executor._strict_victim_hazard_level(next_cell) == 0
