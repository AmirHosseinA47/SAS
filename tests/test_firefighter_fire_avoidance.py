"""Firefighter fire-front avoidance for en-route and idle survival."""

from __future__ import annotations

import os
import random

import pytest
from types import SimpleNamespace

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel


def _ff_model(*, height: int = 20, width: int = 20) -> object:
    return type(
        "FFModel",
        (),
        {
            "HEIGHT": height,
            "WIDTH": width,
            "schedule": SimpleNamespace(agents=[]),
            "grid": type(
                "Grid",
                (),
                {
                    "_cells": {},
                    "out_of_bounds": lambda self, cell: not (
                        0 <= cell[0] < height and 0 <= cell[1] < width
                    ),
                    "get_cell_list_contents": lambda self, cells: [
                        a
                        for cell in cells
                        for a in self._cells.get(cell, [])
                    ],
                    "move_agent": lambda self, agent, cell: setattr(agent, "pos", cell),
                    "place_agent": lambda self, agent, cell: (
                        self._cells.setdefault(cell, []).append(agent),
                        setattr(agent, "pos", cell),
                    )[0],
                },
            )(),
        },
    )()


def _place(model: object, agent: agents.Firefighter | agents.Fire, cell: tuple[int, int]) -> None:
    model.grid._cells.setdefault(cell, []).append(agent)
    agent.pos = cell
    if agent not in model.schedule.agents:
        model.schedule.agents.append(agent)


def _fire(model: object, cell: tuple[int, int], *, burning: bool = True) -> agents.Fire:
    fire = agents.Fire(unique_id=len(model.schedule.agents) + 100, model=model, burning=burning)
    _place(model, fire, cell)
    return fire


def _firefighter(
    model: object,
    cell: tuple[int, int],
    *,
    unit_id: str = "ff_test",
    assigned: bool = False,
    target_pos: tuple[int, int] | None = None,
    exiting: bool = False,
    exit_target: tuple[int, int] | None = None,
) -> agents.Firefighter:
    ff = agents.Firefighter(
        unique_id=len(model.schedule.agents) + 1,
        model=model,
        unit_id=unit_id,
        position=cell,
    )
    ff.assigned = assigned
    ff.target_pos = target_pos
    ff.exiting = exiting
    ff.exit_target = exit_target
    ff.status = "assigned" if assigned else "available"
    _place(model, ff, cell)
    return ff


def test_firefighter_detours_around_active_fire_toward_goal() -> None:
    model = _ff_model()
    ff = _firefighter(model, (5, 5), assigned=True, target_pos=(8, 5))
    _fire(model, (6, 5))

    ff.advance()

    assert ff.pos != (6, 5)
    assert ff.pos in {(5, 4), (5, 6), (4, 5)}
    assert ff.assigned
    assert ff.target_pos == (8, 5)


def test_firefighter_prefers_non_adjacent_fire_cell_when_available() -> None:
    model = _ff_model()
    ff = _firefighter(model, (6, 5), assigned=True, target_pos=(6, 8))
    _fire(model, (6, 6))
    _fire(model, (7, 6))

    ff.advance()

    assert ff.pos == (5, 5)
    assert not ff._cell_adjacent_to_fire(ff.pos)


def test_firefighter_can_take_lateral_detour_without_abandoning_rescue() -> None:
    model = _ff_model()
    ff = _firefighter(model, (5, 5), assigned=True, target_pos=(8, 5))
    _fire(model, (6, 5))

    ff.advance()

    assert ff.pos != (6, 5)
    assert ff.pos != (5, 5)
    assert ff.target_pos == (8, 5)
    assert ff.assigned


def test_firefighter_holds_only_when_surrounded_by_active_fire() -> None:
    model = _ff_model()
    ff = _firefighter(model, (5, 5), assigned=True, target_pos=(8, 5))
    blocked: list[tuple[int, int]] = []
    model._on_firefighter_route_blocked = lambda marker: blocked.append(marker.unit_id)
    for cell in ((6, 5), (4, 5), (5, 6), (5, 4)):
        _fire(model, cell)
    start = ff.pos

    ff.advance()

    assert ff.pos == start
    assert ff.status == "route_blocked"
    assert blocked == ["ff_test"]


def test_firefighter_exit_with_victim_uses_same_fire_avoidance() -> None:
    model = _ff_model()
    victim = agents.Victim(unique_id=99, model=model, victim_id="victim_x", position=(5, 5))
    _place(model, victim, (5, 5))
    ff = _firefighter(
        model,
        (5, 5),
        assigned=True,
        exiting=True,
        exit_target=(0, 5),
    )
    ff.rescued_victim = victim
    _fire(model, (4, 5))

    ff.advance()

    assert ff.pos != (4, 5)
    assert not ff._cell_contains_active_fire(ff.pos)
    assert victim.pos == ff.pos
    assert ff.exiting
    assert ff.exit_target == (0, 5)


def test_idle_firefighter_flees_approaching_fire_front() -> None:
    model = _ff_model()
    ff = _firefighter(model, (5, 5), assigned=False)
    _fire(model, (6, 5))

    ff.advance()

    assert ff.pos != (5, 5)
    assert ff.pos != (6, 5)
    assert not ff.assigned
    assert ff.target_pos is None
    assert ff.status == "available"


def test_idle_firefighter_stays_put_when_safe() -> None:
    model = _ff_model()
    ff = _firefighter(model, (5, 5), assigned=False)
    _fire(model, (10, 10), burning=True)

    ff.advance()

    assert ff.pos == (5, 5)


def _events(model: WildFireModel, event_type: str | None = None) -> list[dict]:
    log = list(getattr(model, "_rescue_event_log", []) or [])
    if event_type is not None:
        log = [e for e in log if e.get("event_type") == event_type]
    return log


def _victim_statuses(model: WildFireModel) -> dict[str, str]:
    out: dict[str, str] = {}
    for vid, state in model.managed_victims.items():
        out[str(vid)] = str(getattr(state, "status", "") or "").strip().lower()
    return out


@pytest.mark.slow
def test_scenario_a_east_seed42_firefighter_survival_validation() -> None:
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
    ff_deaths = 0
    for _ in range(300):
        model.step()
        for agent in model.schedule.agents:
            if type(agent) is agents.Firefighter and getattr(agent, "dead", False):
                ff_deaths = sum(
                    1
                    for a in model.schedule.agents
                    if type(a) is agents.Firefighter and getattr(a, "dead", False)
                )

    statuses = _victim_statuses(model)
    terminal = {"rescued", "dead", "unreachable", "cancelled"}
    rescued = sum(1 for s in statuses.values() if s == "rescued")
    all_terminal = all(s in terminal for s in statuses.values())
    silent_candidate = any(s in {"candidate", "assigned", "unknown"} for s in statuses.values())
    route_blocked = len(_events(model, "route_blocked"))
    rescue_complete = len(_events(model, "rescue_complete"))
    casualty = len(_events(model, "casualty"))

    model._ff_validation_metrics = {
        "ff_deaths": ff_deaths,
        "rescued": rescued,
        "all_terminal": all_terminal,
        "silent_candidate": silent_candidate,
        "route_blocked": route_blocked,
        "rescue_complete": rescue_complete,
        "casualty": casualty,
        "statuses": statuses,
    }

    assert all_terminal
    assert not silent_candidate
