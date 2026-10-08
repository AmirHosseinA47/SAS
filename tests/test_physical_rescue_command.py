"""Phase 2: physical rescue commands are the only assign mutation path."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

from wildfire_model import WildFireModel
import pytest
import common_fixed_variables as cfv

VICTIM_ID = "victim_0"
FF_FAR = "ff_unit_0"
VICTIM_CELL = (10, 10)
FF_CELL = (10, 9)


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


# TODAY'S DISPATCH (pinned at the dispatch flip). ON counterpart(s):
#   tests/test_dispatch_joint.py::test_tj13_the_ledger_counts_every_bind_at_the_single_sink
#   tests/test_dispatch_joint.py::test_tj6_a_unit_free_between_steps_is_paired_at_j_pre_before_moving
#   tests/test_dispatch_information.py::test_tinfo_b_metamorphic_applied_binds
@pytest.mark.usefixtures("today_dispatch")
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
