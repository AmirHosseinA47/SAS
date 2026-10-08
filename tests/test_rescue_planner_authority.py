"""RescuePlanner owns pairing; model enqueues incidents only."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from src_extension.planning.rescue_planner import select_rescue_assignment
from wildfire_model import WildFireModel
import pytest
import common_fixed_variables as cfv

VICTIM_ID = "victim_0"
FF_FAR = "ff_unit_0"
FF_NEAR = "ff_unit_1"
VICTIM_CELL = (10, 10)
FF_FAR_CELL = (0, 0)
FF_NEAR_CELL = (9, 10)
FF0_CASUALTY_CELL = (10, 9)


@pytest.fixture
def today_dispatch(monkeypatch):
    """THE DISPATCH FLIP (dispatch round 2: outputs/dispatch2_part1.txt 10.8 and 21; outputs/dispatch2_report.txt
    section 10). DISPATCH_JOINT and DISPATCH_REASSIGN ship 1. A test marked with this fixture encodes TODAY'S (legacy)
    dispatch - the per-incident nearest pairing and its replacement / write-off paths - so it pins
    DISPATCH_JOINT = 0 explicitly (REASSIGN with it; it is enforced off anyway). Each such test names its ON
    counterpart in the dispatch tests (outputs/dispatch_part1.txt 13.3 / 15)."""
    monkeypatch.setattr(cfv, "DISPATCH_JOINT", 0, raising=False)
    monkeypatch.setattr(cfv, "DISPATCH_REASSIGN", 0, raising=False)


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


def _disable_other_firefighters(model: WildFireModel, keep=(FF_FAR, FF_NEAR)) -> None:
    """Every firefighter the model has, other than `keep`, dead.

    fix1 item 7 (T3/T4): the "no firefighter left" tests assumed a two-firefighter model -
    that ff_unit_0 and ff_unit_1 are the only units, i.e. NUM_FIREFIGHTERS == 2 (the B/D
    team size). WildFireModel() is built at whatever NUM_FIREFIGHTERS the config holds (3
    at the cfv default), so ff_unit_2 stayed alive and the code correctly re-paired it.
    Disabling every other unit makes the premise hold for any team size.
    """
    for ff_id, ff in model.firefighter_marker_agents.items():
        if ff_id in keep:
            continue
        ff.dead = True
        ff.assigned = False
        ff.rescued_victim = None
        ff.target_pos = None
        ff.status = "dead"


# TODAY'S DISPATCH (pinned at the dispatch flip). ON counterpart(s):
#   tests/test_dispatch_joint.py::test_tj1_crossing_pairs_are_uncrossed
#   tests/test_dispatch_joint.py::test_tj3_scarcity_serves_the_nearest_by_route
@pytest.mark.usefixtures("today_dispatch")
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


# TODAY'S DISPATCH (pinned at the dispatch flip). ON counterpart(s):
#   tests/test_dispatch_joint.py::test_tj7_no_pairing_mid_advance_and_a_same_step_detection_is_seen
@pytest.mark.usefixtures("today_dispatch")
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


# TODAY'S DISPATCH (pinned at the dispatch flip). ON counterpart(s):
#   tests/test_dispatch_joint.py::test_tj8_a_casualty_victim_is_rebound_with_the_casualty_reason
@pytest.mark.usefixtures("today_dispatch")
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


# TODAY'S DISPATCH (pinned at the dispatch flip). ON counterpart(s):
#   tests/test_dispatch_joint.py::test_tj8_casualty_with_an_empty_pool_waits_and_is_counted
#   tests/test_dispatch_joint.py::test_tj8_a_returning_unit_means_no_would_have_been_writeoff
@pytest.mark.usefixtures("today_dispatch")
def test_no_firefighter_planner_delay_or_unreachable() -> None:
    model = _fresh_model()
    _reset_firefighters(model)
    _disable_other_firefighters(model)
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


# TODAY'S DISPATCH (pinned at the dispatch flip). ON counterpart(s):
#   tests/test_dispatch_joint.py::test_tj4_order_independence_model
#   tests/test_dispatch_joint.py::test_tj13_the_ledger_counts_every_bind_at_the_single_sink
@pytest.mark.usefixtures("today_dispatch")
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
