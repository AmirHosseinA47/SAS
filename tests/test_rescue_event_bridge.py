"""Physical rescue bridge events recorded for MAPE-K traceability."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from wildfire_model import WildFireModel

VICTIM_ID = "victim_0"
FF_FAR = "ff_unit_0"
FF_NEAR = "ff_unit_1"
VICTIM_CELL = (10, 10)
FF0_CELL = (10, 9)
FF1_CELL = (0, 0)


def _fresh_model() -> WildFireModel:
    return WildFireModel()


def _events(
    model: WildFireModel,
    *,
    event_type: str | None = None,
    victim_id: str | None = None,
) -> list[dict]:
    log = list(getattr(model, "_rescue_event_log", []) or [])
    if event_type is not None:
        log = [e for e in log if e.get("event_type") == event_type]
    if victim_id is not None:
        log = [e for e in log if e.get("victim_id") == victim_id]
    return log


def _prepare_victim(model: WildFireModel) -> agents.Victim:
    marker = model.victim_marker_agents[VICTIM_ID]
    state = model.managed_victims[VICTIM_ID]
    model.grid.move_agent(marker, VICTIM_CELL)
    state.confirmed = True
    state.rescue_assigned = False
    state.status = "confirmed"
    marker.status = "confirmed"
    return marker


def _reset_ff(model: WildFireModel) -> None:
    for ff_id in (FF_FAR, FF_NEAR):
        ff = model.firefighter_marker_agents[ff_id]
        ff.dead = False
        ff.assigned = False
        ff.target_pos = None
        ff.rescued_victim = None
        ff.status = "available"
        ff.exiting = False
        ff.rescue_completed = False


def _set_cell_burning(model: WildFireModel, cell: tuple[int, int]) -> None:
    for agent in model.grid.get_cell_list_contents([cell]):
        if type(agent) is agents.Fire:
            agent.burning = True
            return
    fire = agents.Fire(model.unique_agents_id, model, burning=True)
    model.unique_agents_id += 1
    model.schedule.add(fire)
    model.grid.place_agent(fire, cell)


def test_initial_dispatch_records_dispatch_initial() -> None:
    model = _fresh_model()
    _reset_ff(model)
    marker = _prepare_victim(model)
    model.grid.move_agent(model.firefighter_marker_agents[FF_FAR], FF0_CELL)
    model.grid.move_agent(model.firefighter_marker_agents[FF_NEAR], FF1_CELL)

    assert model._dispatch_firefighter_to_victim(VICTIM_ID, marker, "initial")

    events = _events(model, event_type="dispatch_initial", victim_id=VICTIM_ID)
    assert len(events) == 1
    assert events[0]["firefighter_id"] == FF_FAR
    assert events[0]["reason"] == "initial"
    assert model.latest_physical_rescue_decision is not None
    assert model.latest_physical_rescue_decision.victim_id == VICTIM_ID


def test_route_blocked_and_replacement_record_events() -> None:
    model = _fresh_model()
    _reset_ff(model)
    marker = _prepare_victim(model)
    ff0 = model.firefighter_marker_agents[FF_FAR]
    ff1 = model.firefighter_marker_agents[FF_NEAR]
    model.grid.move_agent(ff0, FF0_CELL)
    model.grid.move_agent(ff1, FF1_CELL)

    ff0.assigned = True
    ff0.target_pos = VICTIM_CELL
    ff0.rescued_victim = marker
    ff0.status = "route_blocked"

    model._on_firefighter_route_blocked(ff0)

    blocked = _events(model, event_type="route_blocked", victim_id=VICTIM_ID)
    replacement = _events(
        model, event_type="dispatch_replacement_after_blocked", victim_id=VICTIM_ID
    )
    assert len(blocked) == 1
    assert blocked[0]["firefighter_id"] == FF_FAR
    assert len(replacement) == 1
    assert replacement[0]["firefighter_id"] == FF_NEAR


def test_casualty_replacement_records_events() -> None:
    model = _fresh_model()
    _reset_ff(model)
    marker = _prepare_victim(model)
    model.grid.move_agent(model.firefighter_marker_agents[FF_FAR], FF0_CELL)
    model.grid.move_agent(model.firefighter_marker_agents[FF_NEAR], FF1_CELL)

    assert model._dispatch_firefighter_to_victim(VICTIM_ID, marker, "test_initial")
    _set_cell_burning(model, FF0_CELL)
    model._check_fire_casualties()

    casualty = _events(model, event_type="casualty", victim_id=VICTIM_ID)
    replacement = _events(
        model, event_type="dispatch_replacement_after_casualty", victim_id=VICTIM_ID
    )
    assert len(casualty) == 1
    assert casualty[0]["firefighter_id"] == FF_FAR
    assert len(replacement) == 1
    assert replacement[0]["firefighter_id"] == FF_NEAR


def test_rescue_failure_records_rescue_failed() -> None:
    model = _fresh_model()
    _reset_ff(model)
    marker = _prepare_victim(model)
    near = model.firefighter_marker_agents[FF_NEAR]
    far = model.firefighter_marker_agents[FF_FAR]
    model.grid.move_agent(near, FF1_CELL)
    model.grid.move_agent(far, FF0_CELL)
    near.dead = True
    far.dead = True

    model._mark_victim_unreachable(VICTIM_ID, marker)

    failed = _events(model, event_type="rescue_failed", victim_id=VICTIM_ID)
    assert len(failed) == 1
    assert failed[0]["reason"] == "no_available_firefighter"


def test_rescue_complete_records_rescue_complete() -> None:
    model = _fresh_model()
    _reset_ff(model)
    marker = _prepare_victim(model)
    model.managed_victims[VICTIM_ID].firefighter_id = FF_NEAR

    model._finalize_rescued_victim(VICTIM_ID, marker, firefighter_id=FF_NEAR)

    complete = _events(model, event_type="rescue_complete", victim_id=VICTIM_ID)
    assert len(complete) == 1
    assert complete[0]["firefighter_id"] == FF_NEAR
    assert model.latest_physical_rescue_decision is not None
    assert "physical_rescue_complete" in (
        model.latest_physical_rescue_decision.rescue_action or ""
    )
