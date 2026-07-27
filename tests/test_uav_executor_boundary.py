"""UAVExecutor boundary-safe direction selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src_extension.execution.uav_executor import UAVExecutor


@dataclass
class _FakeGrid:
    width: int
    height: int

    def out_of_bounds(self, pos: tuple[int, int]) -> bool:
        x, y = int(pos[0]), int(pos[1])
        return x < 0 or y < 0 or x >= self.width or y >= self.height


@dataclass
class _FakeModel:
    grid: _FakeGrid
    WIDTH: int
    HEIGHT: int


@dataclass
class _FakeAgent:
    pos: tuple[int, int]
    model: Any | None = None
    selected_dir: int = 0


def test_right_boundary_avoids_east_when_target_is_further_right() -> None:
    model = _FakeModel(grid=_FakeGrid(width=10, height=10), WIDTH=10, HEIGHT=10)
    agent = _FakeAgent(pos=(9, 5), model=model)
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)

    direction = executor._direction_toward(agent, (15.0, 5.0))

    assert direction != 0
    assert executor._direction_in_bounds(agent, direction)


def test_vertical_boundaries_avoid_out_of_bounds_direction() -> None:
    model = _FakeModel(grid=_FakeGrid(width=10, height=10), WIDTH=10, HEIGHT=10)

    top_agent = _FakeAgent(pos=(5, 9), model=model)
    bottom_agent = _FakeAgent(pos=(5, 0), model=model)
    executor = UAVExecutor(uav_id="0", model=model, agent=top_agent)

    top_dir = executor._direction_toward(top_agent, (5.0, 15.0))
    assert top_dir != 3
    assert executor._direction_in_bounds(top_agent, top_dir)

    bottom_dir = executor._direction_toward(bottom_agent, (5.0, -5.0))
    assert bottom_dir != 1
    assert executor._direction_in_bounds(bottom_agent, bottom_dir)


def test_no_bounds_information_returns_original_chosen_direction() -> None:
    agent = _FakeAgent(pos=(9, 5), model=None)
    executor = UAVExecutor(uav_id="0", model=None, agent=agent)

    direction = executor._direction_toward(agent, (15.0, 5.0))

    assert direction == 0
