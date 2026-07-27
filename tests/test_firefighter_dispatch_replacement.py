"""Deterministic tests for closest-FF dispatch and replacement rescue."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from wildfire_model import WildFireModel

VICTIM_ID = "victim_0"
FF_FAR = "ff_unit_0"
FF_NEAR = "ff_unit_1"
VICTIM_CELL = (10, 10)
FF_FAR_CELL = (0, 0)
FF_NEAR_CELL = (9, 10)
FF0_CASUALTY_CELL = (10, 9)
FF1_REPLACEMENT_CELL = (0, 0)


def _fresh_model() -> WildFireModel:
    return WildFireModel()


def _ff(model: WildFireModel, ff_id: str) -> agents.Firefighter:
    return model.firefighter_marker_agents[ff_id]


def _victim_marker(model: WildFireModel, victim_id: str = VICTIM_ID) -> agents.Victim:
    return model.victim_marker_agents[victim_id]


def _place(model: WildFireModel, agent: agents.Firefighter | agents.Victim, cell: tuple[int, int]) -> None:
    model.grid.move_agent(agent, cell)


def _prepare_victim_for_dispatch(model: WildFireModel) -> agents.Victim:
    marker = _victim_marker(model)
    state = model.managed_victims[VICTIM_ID]
    _place(model, marker, VICTIM_CELL)
    state.confirmed = True
    state.rescue_assigned = False
    state.assigned = False
    state.status = "confirmed"
    state.unreachable = False
    state.cancelled = False
    marker.status = "confirmed"
    return marker


def _reset_firefighters(model: WildFireModel) -> None:
    for ff_id in (FF_FAR, FF_NEAR):
        ff = _ff(model, ff_id)
        ff.dead = False
        ff.assigned = False
        ff.target_pos = None
        ff.rescued_victim = None
        ff.exiting = False
        ff.exit_target = None
        ff.rescue_completed = False
        ff.status = "available"


def _set_cell_burning(model: WildFireModel, cell: tuple[int, int]) -> agents.Fire:
    for agent in model.grid.get_cell_list_contents([cell]):
        if type(agent) is agents.Fire:
            agent.burning = True
            return agent
    fire = agents.Fire(model.unique_agents_id, model, burning=True)
    model.unique_agents_id += 1
    model.schedule.add(fire)
    model.grid.place_agent(fire, cell)
    return fire


def _path_marker_count(model: WildFireModel) -> int:
    return sum(1 for a in model.schedule.agents if type(a) is agents.PathMarker)


def _assign_ff_to_victim(
    model: WildFireModel, ff_id: str, marker: agents.Victim, cell: tuple[int, int]
) -> agents.Firefighter:
    ff = _ff(model, ff_id)
    _place(model, ff, cell)
    ff.assigned = True
    ff.target_pos = VICTIM_CELL
    ff.rescued_victim = marker
    ff.status = "en_route"
    return ff


def test_closest_firefighter_selected_on_dispatch() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim_for_dispatch(model)
    _place(model, _ff(model, FF_FAR), FF_FAR_CELL)
    _place(model, _ff(model, FF_NEAR), FF_NEAR_CELL)

    closest_before = model._find_closest_available_firefighter(VICTIM_CELL)
    assert closest_before is not None
    assert closest_before[0] == FF_NEAR
    assert model._manhattan_distance(_ff(model, FF_NEAR).pos, VICTIM_CELL) < model._manhattan_distance(
        _ff(model, FF_FAR).pos, VICTIM_CELL
    )

    assert model._dispatch_firefighter_to_victim(VICTIM_ID, marker, "test_initial")

    near = _ff(model, FF_NEAR)
    far = _ff(model, FF_FAR)
    state = model.managed_victims[VICTIM_ID]

    assert near.assigned is True
    assert near.rescued_victim is marker
    assert near.target_pos == VICTIM_CELL
    assert far.assigned is False
    assert far.rescued_victim is None
    assert state.rescue_assigned is True
    assert state.assigned is True
    assert state.status == "assigned"
    assert marker.status == "assigned"
    assert model._find_active_firefighter_for_victim(VICTIM_ID, marker) == (FF_NEAR, near)


def test_route_blocked_triggers_replacement_firefighter() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim_for_dispatch(model)
    _place(model, _ff(model, FF_FAR), FF_FAR_CELL)
    _place(model, _ff(model, FF_NEAR), FF_NEAR_CELL)

    ff0 = _assign_ff_to_victim(model, FF_FAR, marker, FF_FAR_CELL)
    ff0.status = "route_blocked"

    model._on_firefighter_route_blocked(ff0)

    far = _ff(model, FF_FAR)
    near = _ff(model, FF_NEAR)
    state = model.managed_victims[VICTIM_ID]

    assert far.assigned is False
    assert far.rescued_victim is None
    assert str(getattr(far, "status", "")).lower() == "route_blocked"
    assert near.assigned is True
    assert near.rescued_victim is marker
    assert near.target_pos == VICTIM_CELL
    assert state.rescue_assigned is True
    assert state.status in ("assigned", "confirmed")
    assert state.unreachable is False
    assert marker.status in ("assigned", "confirmed")
    assert VICTIM_ID not in model._rescue_failed_logged


def test_firefighter_casualty_triggers_replacement() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim_for_dispatch(model)
    _place(model, _ff(model, FF_FAR), FF_FAR_CELL)
    _place(model, _ff(model, FF_NEAR), FF_NEAR_CELL)

    ff0 = _assign_ff_to_victim(model, FF_FAR, marker, FF_FAR_CELL)
    ff0.dead = True
    ff0.assigned = False
    ff0.target_pos = None
    ff0.rescued_victim = None
    ff0.status = "dead"

    model._try_replacement_after_firefighter_casualty(marker)

    near = _ff(model, FF_NEAR)
    far = _ff(model, FF_FAR)
    state = model.managed_victims[VICTIM_ID]

    assert far.dead is True
    assert far.assigned is False
    assert near.assigned is True
    assert near.rescued_victim is marker
    assert not model._firefighter_available_for_dispatch(far)
    assert state.rescue_assigned is True
    assert state.unreachable is False
    assert marker.status in ("assigned", "confirmed")


def test_no_replacement_available_marks_victim_unreachable_once() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim_for_dispatch(model)
    _place(model, _ff(model, FF_FAR), FF_FAR_CELL)
    near = _ff(model, FF_NEAR)
    _place(model, near, FF_NEAR_CELL)
    near.dead = True
    near.status = "dead"

    _assign_ff_to_victim(model, FF_FAR, marker, FF_FAR_CELL)
    ff0 = _ff(model, FF_FAR)
    ff0.dead = True
    ff0.assigned = False
    ff0.target_pos = None
    ff0.rescued_victim = None
    ff0.status = "dead"

    model._try_replacement_after_firefighter_casualty(marker)
    model._try_replacement_after_firefighter_casualty(marker)

    state = model.managed_victims[VICTIM_ID]
    assert state.unreachable is True
    assert state.status == "unreachable"
    assert marker.status == "unreachable"
    assert VICTIM_ID in model._rescue_failed_logged
    assert sum(1 for ff in model.firefighter_marker_agents.values() if ff.dead and ff.assigned) == 0
    assert model._dispatch_firefighter_to_victim(VICTIM_ID, marker, "test_retry") is False


def test_check_fire_casualties_replaces_dead_assigned_firefighter() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim_for_dispatch(model)
    _place(model, _ff(model, FF_FAR), FF0_CASUALTY_CELL)
    _place(model, _ff(model, FF_NEAR), FF1_REPLACEMENT_CELL)

    assert model._dispatch_firefighter_to_victim(VICTIM_ID, marker, "test_initial")
    ff0 = _ff(model, FF_FAR)
    ff1 = _ff(model, FF_NEAR)
    assert ff0.assigned is True
    assert ff0.rescued_victim is marker
    assert ff0.pos == FF0_CASUALTY_CELL

    fire = _set_cell_burning(model, FF0_CASUALTY_CELL)
    assert fire.is_burning()

    model._check_fire_casualties()

    state = model.managed_victims[VICTIM_ID]
    assert ff0.dead is True
    assert str(ff0.status).lower() == "dead"
    assert ff0.assigned is False
    assert not model._firefighter_available_for_dispatch(ff0)
    assert ff1.assigned is True
    assert ff1.rescued_victim is marker
    assert ff1.target_pos == VICTIM_CELL
    assert state.unreachable is False
    assert state.cancelled is not True
    assert str(getattr(state, "status", "")).lower() not in ("dead", "unreachable")
    assert marker.status in ("assigned", "confirmed")
    assert VICTIM_ID not in model._rescue_failed_logged
    assert model._find_active_firefighter_for_victim(VICTIM_ID, marker) == (FF_NEAR, ff1)
    assert _path_marker_count(model) > 0 or state.rescue_assigned is True
    assert all(
        not (getattr(ff, "dead", False) and getattr(ff, "assigned", False))
        for ff in model.firefighter_marker_agents.values()
    )


def test_route_blocked_without_replacement_keeps_victim_pending_not_unreachable() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim_for_dispatch(model)
    _place(model, _ff(model, FF_FAR), FF_FAR_CELL)
    near = _ff(model, FF_NEAR)
    _place(model, near, FF_NEAR_CELL)
    near.assigned = True
    near.status = "en_route"
    near.target_pos = (20, 20)
    near.rescued_victim = model.victim_marker_agents.get("victim_1")

    ff0 = _assign_ff_to_victim(model, FF_FAR, marker, FF_FAR_CELL)
    ff0.status = "route_blocked"
    model._on_firefighter_route_blocked(ff0)

    state = model.managed_victims[VICTIM_ID]
    assert state.unreachable is False
    assert marker.status in ("confirmed", "assigned")
    assert VICTIM_ID not in model._rescue_failed_logged
