"""Phase 2: physical rescue commands are the only assign mutation path."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

from wildfire_model import WildFireModel

VICTIM_ID = "victim_0"
FF_FAR = "ff_unit_0"
VICTIM_CELL = (10, 10)
FF_CELL = (10, 9)


def _fresh_model() -> WildFireModel:
    return WildFireModel()


def test_apply_physical_rescue_command_assign() -> None:
    from wildfire_model import PhysicalRescueCommand

    model = _fresh_model()
    marker = model.victim_marker_agents[VICTIM_ID]
    ff = model.firefighter_marker_agents[FF_FAR]
    model.grid.move_agent(marker, VICTIM_CELL)
    model.grid.move_agent(ff, FF_CELL)

    assert model.apply_physical_rescue_command(
        PhysicalRescueCommand(
            action="assign",
            victim_id=VICTIM_ID,
            firefighter_id=FF_FAR,
            reason="initial",
            metadata={"victim_marker": marker, "target_pos": VICTIM_CELL},
        )
    )
    assert ff.assigned
    assert ff.rescued_victim is marker


def test_dispatch_uses_shared_rescue_executor() -> None:
    model = _fresh_model()
    marker = model.victim_marker_agents[VICTIM_ID]
    state = model.managed_victims[VICTIM_ID]
    model.grid.move_agent(marker, VICTIM_CELL)
    model.grid.move_agent(model.firefighter_marker_agents[FF_FAR], FF_CELL)
    state.confirmed = True
    state.rescue_assigned = False
    marker.status = "confirmed"

    executor_a = model._physical_rescue_executor()
    executor_b = model.decision_dispatcher.rescue_executor
    assert executor_a is executor_b

    ff = model.firefighter_marker_agents[FF_FAR]
    assert model._dispatch_firefighter_to_victim(VICTIM_ID, marker, "initial")
    assert ff.assigned
    assert ff.rescued_victim is marker


def test_dead_firefighter_not_dispatched_via_apply() -> None:
    from wildfire_model import PhysicalRescueCommand

    model = _fresh_model()
    marker = model.victim_marker_agents[VICTIM_ID]
    ff = model.firefighter_marker_agents[FF_FAR]
    model.grid.move_agent(marker, VICTIM_CELL)
    model.grid.move_agent(ff, FF_CELL)
    ff.dead = True

    assert not model.apply_physical_rescue_command(
        PhysicalRescueCommand(
            action="assign",
            victim_id=VICTIM_ID,
            firefighter_id=FF_FAR,
            reason="initial",
            metadata={"victim_marker": marker, "target_pos": VICTIM_CELL},
        )
    )
