"""RescuePlanner owns pairing; model enqueues incidents only."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from src_extension.planning.rescue_planner import select_rescue_assignment
from wildfire_model import WildFireModel

VICTIM_ID = "victim_0"
FF_FAR = "ff_unit_0"
FF_NEAR = "ff_unit_1"
VICTIM_CELL = (10, 10)
FF_FAR_CELL = (0, 0)
FF_NEAR_CELL = (9, 10)
FF0_CASUALTY_CELL = (10, 9)


def _fresh_model() -> WildFireModel:
    return WildFireModel()


def _ff(model: WildFireModel, ff_id: str) -> agents.Firefighter:
    return model.firefighter_marker_agents[ff_id]


def _victim_marker(model: WildFireModel, victim_id: str = VICTIM_ID) -> agents.Victim:
    return model.victim_marker_agents[victim_id]


def _place(model: WildFireModel, agent: agents.Firefighter | agents.Victim, cell: tuple[int, int]) -> None:
    model.grid.move_agent(agent, cell)


def _prepare_victim(model: WildFireModel) -> agents.Victim:
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


def test_victim_confirmed_incident_planner_assigns_closest() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim(model)
    _place(model, _ff(model, FF_FAR), FF_FAR_CELL)
    _place(model, _ff(model, FF_NEAR), FF_NEAR_CELL)

    snap = model.get_rescue_operational_snapshot()
    decision = select_rescue_assignment(snap, "initial", victim_id=VICTIM_ID)
    ff_choice = (
        str(getattr(decision, "firefighter_id", ""))
        if not isinstance(decision, dict)
        else str(decision.get("firefighter_id", ""))
    )
    assert ff_choice == FF_NEAR

    model._enqueue_rescue_incident(
        {
            "type": "victim_confirmed",
            "victim_id": VICTIM_ID,
            "firefighter_id": None,
            "reason": "initial",
            "metadata": {},
        }
    )
    model._process_rescue_incidents()

    near = _ff(model, FF_NEAR)
    assert near.assigned is True
    assert near.rescued_victim is marker


def test_sync_victim_status_does_not_dispatch_without_fallback() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    _prepare_victim(model)
    _place(model, _ff(model, FF_FAR), FF_FAR_CELL)
    _place(model, _ff(model, FF_NEAR), FF_NEAR_CELL)
    model._rescue_incident_processing_enabled = False
    model._allow_sync_victim_dispatch_fallback = False

    model._sync_victim_agent_status()

    assert not _ff(model, FF_NEAR).assigned
    assert not _ff(model, FF_FAR).assigned


def test_route_blocked_incident_planner_replacement() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim(model)
    _place(model, _ff(model, FF_FAR), FF_FAR_CELL)
    _place(model, _ff(model, FF_NEAR), FF_NEAR_CELL)

    ff0 = _ff(model, FF_FAR)
    ff0.assigned = True
    ff0.target_pos = VICTIM_CELL
    ff0.rescued_victim = marker
    ff0.status = "route_blocked"

    model._enqueue_rescue_incident(
        {
            "type": "route_blocked",
            "victim_id": VICTIM_ID,
            "firefighter_id": FF_FAR,
            "reason": "replacement_after_blocked",
            "metadata": {},
        }
    )
    model._process_rescue_incidents()

    assert _ff(model, FF_NEAR).assigned is True
    assert _ff(model, FF_NEAR).rescued_victim is marker
    assert _ff(model, FF_FAR).assigned is False


def test_firefighter_casualty_incident_planner_replacement() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim(model)
    _place(model, _ff(model, FF_FAR), FF_FAR_CELL)
    _place(model, _ff(model, FF_NEAR), FF_NEAR_CELL)

    ff0 = _ff(model, FF_FAR)
    ff0.assigned = True
    ff0.target_pos = VICTIM_CELL
    ff0.rescued_victim = marker
    ff0.dead = True
    ff0.assigned = False
    ff0.rescued_victim = None
    ff0.status = "dead"

    model._enqueue_rescue_incident(
        {
            "type": "firefighter_casualty",
            "victim_id": VICTIM_ID,
            "firefighter_id": FF_FAR,
            "reason": "replacement_after_casualty",
            "metadata": {},
        }
    )
    model._process_rescue_incidents()

    assert _ff(model, FF_NEAR).assigned is True
    assert _ff(model, FF_NEAR).rescued_victim is marker


def test_no_firefighter_planner_delay_or_unreachable() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    _prepare_victim(model)
    for ff_id in (FF_FAR, FF_NEAR):
        ff = _ff(model, ff_id)
        ff.dead = True

    snap = model.get_rescue_operational_snapshot()
    initial = select_rescue_assignment(snap, "initial", victim_id=VICTIM_ID)
    replacement = select_rescue_assignment(
        snap, "replacement_after_casualty", victim_id=VICTIM_ID
    )
    assert str(getattr(initial, "rescue_action", "")).lower() == "delay"
    assert str(getattr(replacement, "rescue_action", "")).lower() == "mark_unreachable"


def test_duplicate_incident_not_processed_twice() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    marker = _prepare_victim(model)
    _place(model, _ff(model, FF_NEAR), FF_NEAR_CELL)

    incident = {
        "type": "victim_confirmed",
        "victim_id": VICTIM_ID,
        "firefighter_id": None,
        "reason": "initial",
        "metadata": {},
    }
    model._enqueue_rescue_incident(incident)
    model._enqueue_rescue_incident(incident)
    model._process_rescue_incidents()

    events = [
        e
        for e in model._rescue_event_log
        if e.get("event_type") == "dispatch_initial" and e.get("victim_id") == VICTIM_ID
    ]
    assert len(events) == 1
    assert _ff(model, FF_NEAR).assigned is True
    assert _ff(model, FF_NEAR).rescued_victim is marker
