"""Behavior regression: direction intent, hazards, and command translation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import MethodType
from typing import Any
from unittest.mock import patch

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from src_extension.adaptation.local_adaptation_generator import LocalAdaptationSpaceGenerator
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.planning.decision_objects import PathDecision
from src_extension.planning.local_uav_path_planner import LocalUAVPathPlanner
from wildfire_model import WildFireModel


@dataclass
class _FakeGrid:
    width: int
    height: int

    def out_of_bounds(self, pos: tuple[int, int]) -> bool:
        x, y = int(pos[0]), int(pos[1])
        return x < 0 or y < 0 or x >= self.width or y >= self.height


@dataclass
class _FakeBelief:
    fire_probability_map: dict[tuple[int, int], float] = field(default_factory=dict)


@dataclass
class _FakeFireRuntime:
    belief: _FakeBelief = field(default_factory=_FakeBelief)


@dataclass
class _FakeVisibilityState:
    observation_status_map: dict[tuple[int, int], str] = field(default_factory=dict)


@dataclass
class _FakeVisibility:
    state: _FakeVisibilityState = field(default_factory=_FakeVisibilityState)


@dataclass
class _FakeVictim:
    estimated_position: tuple[float, float]


@dataclass
class _FakeVictimRuntime:
    victims: dict[str, _FakeVictim] = field(default_factory=dict)


@dataclass
class _FakeUAVState:
    current_role: str | None = None
    current_position: tuple[float, float] | None = None


@dataclass
class _FakeResource:
    by_uav_id: dict[str, _FakeUAVState] = field(default_factory=dict)


@dataclass
class _FakeModel:
    grid: _FakeGrid
    WIDTH: int
    HEIGHT: int
    fire_runtime_model: _FakeFireRuntime = field(default_factory=_FakeFireRuntime)
    visibility_model: _FakeVisibility = field(default_factory=_FakeVisibility)
    victim_runtime_model: _FakeVictimRuntime = field(default_factory=_FakeVictimRuntime)
    uav_resource_model: _FakeResource = field(default_factory=_FakeResource)
    uav_visit_counts: dict[tuple[str, int, int], int] = field(default_factory=dict)
    uav_last_failed_dir: dict[str, int] = field(default_factory=dict)


@dataclass
class _FakeAgent:
    unique_id: int
    pos: tuple[int, int]
    selected_dir: int = 0
    model: _FakeModel | None = None


def _executor_at(
    pos: tuple[int, int],
    *,
    fire_map: dict[tuple[int, int], float] | None = None,
    smoke_cells: set[tuple[int, int]] | None = None,
    role: str = "scout",
    victims: dict[str, _FakeVictim] | None = None,
) -> tuple[UAVExecutor, _FakeAgent, _FakeModel]:
    model = _FakeModel(grid=_FakeGrid(width=10, height=10), WIDTH=10, HEIGHT=10)
    if fire_map is not None:
        model.fire_runtime_model.belief.fire_probability_map = dict(fire_map)
    if smoke_cells:
        model.visibility_model.state.observation_status_map = {
            cell: "smoke_obscured" for cell in smoke_cells
        }
    if victims:
        model.victim_runtime_model.victims = dict(victims)
    model.uav_resource_model.by_uav_id["0"] = _FakeUAVState(
        current_role=role, current_position=(float(pos[0]), float(pos[1]))
    )
    agent = _FakeAgent(unique_id=0, pos=pos, model=model)
    return UAVExecutor(uav_id="0", model=model, agent=agent), agent, model


def test_execution_selected_dir_not_overwritten_before_move() -> None:
    model = WildFireModel()
    for _ in range(3):
        model.step()
    model.latest_execution_result = {
        "local": {
            "applied": True,
            "uav_results": {"0": {"applied": True, "selected_dir": 2}},
        }
    }
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    uav.selected_dir = 2
    captured: dict[str, int] = {}

    def _capture_dir(self: WildFireModel) -> None:
        for agent in self.schedule.agents:
            if type(agent) is agents.UAV:
                captured[str(agent.unique_id)] = int(agent.selected_dir)

    model._sync_new_direction_from_uav_selected_dirs = MethodType(_capture_dir, model)
    assert model._has_pending_execution_directions()
    model._sync_new_direction_from_uav_selected_dirs()
    assert captured[str(uav.unique_id)] == 2


def test_left_boundary_avoids_west_direction() -> None:
    executor, agent, _ = _executor_at((0, 5))
    decision = PathDecision(
        decision_id="p-1",
        uav_id="0",
        next_action="move_toward_fire_front",
        uncertainty_context={"target_position": (9.0, 5.0)},
    )
    result = executor.execute(decision, timestamp=1.0)
    assert result["selected_dir"] != 2
    assert executor._direction_in_bounds(agent, int(result["selected_dir"]))


def test_avoids_high_fire_neighbor_when_safer_exists() -> None:
    fire_map = {(2, 5): 0.9, (1, 6): 0.05, (1, 4): 0.05, (3, 5): 0.05}
    executor, agent, _ = _executor_at((1, 5), fire_map=fire_map)
    decision = PathDecision(
        decision_id="p-2",
        uav_id="0",
        next_action="move_toward_fire_front",
        uncertainty_context={"target_position": (5.0, 5.0)},
    )
    result = executor.execute(decision, timestamp=1.0)
    assert result["selected_dir"] != 0
    nx = int(agent.pos[0]) + [1, 0, -1, 0][int(result["selected_dir"])]
    assert fire_map.get((nx, 5), 0.0) < 0.3


def test_avoids_smoke_obscured_neighbor_when_safer_exists() -> None:
    executor, agent, _ = _executor_at(
        (3, 5),
        smoke_cells={(4, 5)},
    )
    decision = PathDecision(
        decision_id="p-3",
        uav_id="0",
        next_action="move_toward_fire_front",
        uncertainty_context={"target_position": (8.0, 5.0)},
    )
    result = executor.execute(decision, timestamp=1.0)
    assert result["selected_dir"] != 0
    nx = int(agent.pos[0]) + [1, 0, -1, 0][int(result["selected_dir"])]
    assert nx != 4


def test_victim_searcher_prefers_victim_target_over_fire() -> None:
    executor, _, model = _executor_at(
        (5, 5),
        role="victim_searcher",
        fire_map={(8, 5): 0.95},
        victims={"v1": _FakeVictim(estimated_position=(7.0, 5.0))},
    )
    decision = PathDecision(
        decision_id="p-4",
        uav_id="0",
        next_action="move_toward_fire_front",
        uncertainty_context={"target_position": (8.0, 5.0)},
    )
    result = executor.execute(decision, timestamp=1.0)
    assert result["action"] == "computed_from_target"
    assert result["selected_dir"] in (0, 1, 3)


def test_exploration_fallback_avoids_repeated_failed_direction() -> None:
    executor, agent, model = _executor_at((4, 5))
    model.uav_last_failed_dir["0"] = 2
    first = executor._exploration_fallback(agent)
    second = executor._exploration_fallback(agent)
    assert first != 2 or second != 2


def test_wind_does_not_overwrite_selected_dir() -> None:
    uav = agents.UAV(0, None)
    uav.selected_dir = 3
    wind = agents.Wind()
    before = int(uav.selected_dir)
    wind.apply_wind(0.5, (1, 1), (2, 1))
    after = int(uav.selected_dir)
    assert before == after == 3


def test_descriptive_next_action_uses_target_position() -> None:
    executor, agent, _ = _executor_at((2, 5))
    decision = PathDecision(
        decision_id="p-5",
        uav_id="0",
        next_action="move_toward_fire_front",
        uncertainty_context={"target_position": (7.0, 5.0)},
    )
    result = executor.execute(decision, timestamp=1.0)
    assert result["action"] == "computed_from_target"
    assert result["selected_dir"] == 0
    assert agent.selected_dir == 0


def test_local_path_options_include_target_position_for_fire_and_victim() -> None:
    generator = LocalAdaptationSpaceGenerator()
    fire_map = {
        (5, 5): 0.9,
        (6, 5): 0.9,
        (4, 5): 0.9,
        (5, 6): 0.9,
        (5, 4): 0.9,
        (10, 5): 0.9,
        (11, 5): 0.1,
    }
    base_runtime = {
        "fire_runtime_model": type("FR", (), {"belief": _FakeBelief(fire_map)})(),
        "victim_runtime_model": _FakeVictimRuntime(
            victims={"v0": _FakeVictim(estimated_position=(12.0, 8.0))}
        ),
    }
    fire_options = generator._generate_path_options(
        {"triggers": [], "target_entity": "uav-1"},
        {},
        {
            **base_runtime,
            "uav_resource_model": _FakeResource(
                by_uav_id={"uav-1": _FakeUAVState(current_role="fire_tracker")}
            ),
        },
        1.0,
    )
    victim_options = generator._generate_path_options(
        {"triggers": [], "target_entity": "uav-1"},
        {},
        {
            **base_runtime,
            "uav_resource_model": _FakeResource(
                by_uav_id={"uav-1": _FakeUAVState(current_role="victim_searcher")}
            ),
        },
        1.0,
    )
    fire_opts = [
        o
        for o in fire_options
        if o.parameters.get("path_action", "").startswith("move_toward_fire")
    ]
    victim_opts = [
        o
        for o in victim_options
        if o.parameters.get("path_action") == "move_toward_victim_candidate"
    ]
    assert fire_opts and fire_opts[0].parameters.get("target_position") is not None
    assert victim_opts and victim_opts[0].parameters.get("target_position") is not None


def test_planner_converts_descriptive_action_to_cardinal() -> None:
    planner = LocalUAVPathPlanner(uav_id="uav-1")
    params = {
        "path_action": "move_toward_fire_front",
        "target_position": (8.0, 5.0),
    }
    runtime = {
        "uav_resource_model": _FakeResource(
            by_uav_id={"uav-1": _FakeUAVState(current_position=(2.0, 5.0))}
        )
    }
    decision = planner.plan(
        1,
        local_adaptation_space=type(
            "S",
            (),
            {
                "options": [
                    type(
                        "O",
                        (),
                        {
                            "option_id": "local_path_move_toward_fire_front_0",
                            "option_type": "path_planning",
                            "target_entity": "uav-1",
                            "parameters": params,
                            "expected_effect": "x",
                            "cost_estimate": 1.0,
                            "risk_estimate": 0.2,
                            "confidence": 1.0,
                            "scope": type("Sc", (), {"value": "local"})(),
                            "timestamp": 1.0,
                            "originating_trigger": "t",
                            "explanation_hint": "x",
                        },
                    )()
                ]
            },
        )(),
        runtime_models=runtime,
        timestamp=1.0,
    )
    assert decision is not None
    assert decision.next_action == "east"
    assert decision.uncertainty_context.get("target_position") == (8.0, 5.0)
