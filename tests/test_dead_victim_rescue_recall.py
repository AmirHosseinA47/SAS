"""Dead/cancelled victims must not complete rescue; assigned firefighters are recalled."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from wildfire_model import PhysicalRescueCommand, WildFireModel

VICTIM_ID = "victim_0"
FF_ID = "ff_unit_0"
VICTIM_CELL = (10, 10)
FF_CELL = (10, 9)


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


def _assign_ff_to_victim(model: WildFireModel) -> tuple[agents.Victim, agents.Firefighter]:
    marker = model.victim_marker_agents[VICTIM_ID]
    ff = model.firefighter_marker_agents[FF_ID]
    state = model.managed_victims[VICTIM_ID]
    model.grid.move_agent(marker, VICTIM_CELL)
    model.grid.move_agent(ff, FF_CELL)
    state.confirmed = True
    state.status = "confirmed"
    marker.status = "confirmed"
    assert model.apply_physical_rescue_command(
        PhysicalRescueCommand(
            action="assign",
            victim_id=VICTIM_ID,
            firefighter_id=FF_ID,
            reason="initial",
            metadata={"victim_marker": marker, "target_pos": VICTIM_CELL},
        )
    )
    return marker, ff


def test_dead_victim_cannot_be_rescued() -> None:
    model = _fresh_model()
    marker = model.victim_marker_agents[VICTIM_ID]
    state = model.managed_victims[VICTIM_ID]
    marker.status = "dead"
    state.status = "dead"
    state.dead = True
    state.cancelled = True

    model._handle_rescue_incident(
        {
            "type": "rescue_complete",
            "victim_id": VICTIM_ID,
            "firefighter_id": FF_ID,
        }
    )

    assert not getattr(state, "rescued", False)
    assert str(getattr(state, "status", "")).lower() == "dead"
    assert _events(model, event_type="rescue_complete", victim_id=VICTIM_ID) == []


def test_firefighter_recalled_when_assigned_victim_dies() -> None:
    model = _fresh_model()
    marker, ff = _assign_ff_to_victim(model)
    assert ff.assigned
    assert ff.target_pos == VICTIM_CELL
    assert ff.rescued_victim is marker

    state = model.managed_victims[VICTIM_ID]
    marker.status = "dead"
    state.status = "dead"
    state.dead = True
    state.cancelled = True

    model._handle_rescue_incident(
        {
            "type": "victim_dead",
            "victim_id": VICTIM_ID,
            "firefighter_id": None,
            "reason": "fire_casualty",
        }
    )

    assert not ff.assigned
    assert ff.target_pos is None
    assert ff.rescued_victim is None
    assert not ff.exiting


def test_no_rescue_complete_event_after_victim_dead() -> None:
    model = _fresh_model()
    marker, ff = _assign_ff_to_victim(model)
    state = model.managed_victims[VICTIM_ID]
    marker.status = "dead"
    state.status = "dead"
    state.dead = True
    state.cancelled = True

    model._handle_rescue_incident(
        {
            "type": "victim_dead",
            "victim_id": VICTIM_ID,
            "firefighter_id": None,
            "reason": "fire_casualty",
        }
    )
    model._finalize_rescued_victim(VICTIM_ID, marker, firefighter_id=FF_ID)

    assert _events(model, event_type="rescue_complete", victim_id=VICTIM_ID) == []
    assert not getattr(state, "rescued", False)
