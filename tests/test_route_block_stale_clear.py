"""ROUTE_BLOCK_STALE_CLEAR: dropping a route_blocked flag that lost its referent.

route_blocked is raised about ONE target but read by four gates as a property of
the unit. The replacement unassign issued inside the raise's own call stack
deletes the whole referent and leaves the flag, which disarms all three clears at
once - _move_toward's tail needs target_pos, the 70e1b33 revalidation pass needs
a live victim to test a path against, and the dd0a1b9 D6 clear needs
rescued_victim through its _bound gate. Once the last victim is terminal the flag
can never be cleared and the unit is undispatchable for the rest of the run.

The clear fires ONLY when no victim needs rescue, so it closes the latch and by
its own trigger cannot save a victim.

RUNG 1 IS WHAT SHIPS. Rung 2 additionally releases a unit still bound to a
terminal referent - clearing its status alone would leave it undispatchable on
`assigned` and relabelled "assigned" by agents.py:1816, a latch that hides from
any detector counting status == "route_blocked" - but its release path never
executed in the round's 34-run sweep, so it is tested here and shipped OFF.
Tests below that exercise it set ROUTE_BLOCK_STALE_CLEAR = 2 explicitly.

Drives the real WildFireModel through the real pass, the way
test_phantom_rescue_release does.
"""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
from src_extension.planning.rescue_planner import select_rescue_assignment
from wildfire_model import PhysicalRescueCommand, WildFireModel

V0 = "victim_0"
V1 = "victim_1"
FF_A = "ff_unit_0"
FF_B = "ff_unit_1"

# Ignition is random in [10, 39]^2 (SystemRandom, unseeded in tests). Every cell
# below is outside that box, so no assertion here can be perturbed by a burning
# cell, and no unit can be accidentally fire-enclosed.
CELL_A = (2, 2)
CELL_B = (47, 47)
VICTIM_CELL = (2, 47)
CLEARED_LINE = "flag dropped with no victim left to reach"


@pytest.fixture(autouse=True)
def _restore_switch():
    """Never leak a monkeypatched switch into another module's tests."""
    original = cfv.ROUTE_BLOCK_STALE_CLEAR
    yield
    cfv.ROUTE_BLOCK_STALE_CLEAR = original


def _fresh_model() -> WildFireModel:
    model = WildFireModel()
    model.debug_log = False
    return model


def _ff(model: WildFireModel, ff_id: str) -> agents.Firefighter:
    return model.firefighter_marker_agents[ff_id]


def _reset_all_ff(model: WildFireModel) -> None:
    for ff in model.firefighter_marker_agents.values():
        ff.dead = False
        ff.assigned = False
        ff.target_pos = None
        ff.rescued_victim = None
        ff.exiting = False
        ff.exit_target = None
        ff.rescue_completed = False
        ff.status = "available"


def _park(model: WildFireModel, ff_id: str, cell) -> agents.Firefighter:
    ff = _ff(model, ff_id)
    model.grid.move_agent(ff, cell)
    return ff


def _terminate_all_victims(model: WildFireModel, skip=()) -> None:
    """Every victim dead, so _any_victim_needs_rescue() is False."""
    for vid, marker in model.victim_marker_agents.items():
        if vid in skip:
            continue
        marker.status = "dead"
        state = model.managed_victims.get(vid)
        if state is not None:
            state.status = "dead"
            state.rescued = False


def _latched(model: WildFireModel, ff_id: str, cell) -> agents.Firefighter:
    """The state the replacement unassign leaves behind: flagged, no referent."""
    ff = _park(model, ff_id, cell)
    ff.assigned = False
    ff.target_pos = None
    ff.rescued_victim = None
    ff.exiting = False
    ff.exit_target = None
    ff.rescue_completed = False
    ff.status = "route_blocked"
    return ff


def _bound_latched(model: WildFireModel, ff_id: str, cell, vid: str):
    """The SECOND-block shape: flagged but still assigned and bound.

    _handle_rescue_incident returns at its _blocked_replacement_attempted guard
    BEFORE the unassign on a repeat raise for the same (unit, victim) pair, so
    the unit keeps assigned/target_pos/rescued_victim along with the flag.
    """
    marker = model.victim_marker_agents[vid]
    model.grid.move_agent(marker, VICTIM_CELL)
    ff = _park(model, ff_id, cell)
    ff.assigned = True
    ff.rescued_victim = marker
    ff.target_pos = tuple(VICTIM_CELL)
    ff.exiting = False
    ff.exit_target = None
    ff.rescue_completed = False
    ff.status = "route_blocked"
    return ff, marker


def _mark_unreachable(model: WildFireModel, vid: str) -> None:
    assert model.apply_physical_rescue_command(
        PhysicalRescueCommand(
            action="mark_unreachable",
            victim_id=vid,
            firefighter_id=None,
            reason="replacement_after_casualty",
            metadata={},
        )
    )


def _unassign_audit(model: WildFireModel) -> list[dict]:
    return [
        e
        for e in list(getattr(model, "_physical_rescue_command_audit", []) or [])
        if e.get("action") == "unassign"
    ]


def _enclose(ff: agents.Firefighter) -> None:
    """Force the trapped case without needing a real ring of fire."""
    ff._cell_contains_active_fire = lambda cell: True


# ---------------------------------------------------------------- the switch


def test_mode_reads_the_module_at_call_time() -> None:
    """The dead-input test: the read must be frozen neither at import NOR at
    construction.

    The model is BUILT FIRST and only then is cfv patched, so a mode cached in
    __init__ fails this as surely as a module-level constant or a star-imported
    name would. That ordering is the real one: apply_scenario_config
    (local_adaptation_generator.py:270-273) writes the override after this
    module is imported, and the harness then builds the model.
    """
    model = _fresh_model()
    for value, expected in ((0, 0), (1, 1), (2, 2)):
        cfv.ROUTE_BLOCK_STALE_CLEAR = value
        assert model._route_block_stale_clear_mode() == expected
        assert WildFireModel._route_block_stale_clear_mode() == expected
    # numbers clamp to the ladder; junk falls back to the shipped default
    for value, expected in ((-5, 0), (99, 2), ("bad", 1), (None, 1)):
        cfv.ROUTE_BLOCK_STALE_CLEAR = value
        assert model._route_block_stale_clear_mode() == expected
    # and the getattr fallback itself, which the junk rows do not reach: they
    # exercise only the except branch, leaving the default in the getattr call
    # free to drift back with the suite green
    del cfv.ROUTE_BLOCK_STALE_CLEAR
    assert model._route_block_stale_clear_mode() == 1


def test_default_is_rung_one_and_ships_on() -> None:
    """Rung 1 ships, not rung 2.

    Rung 2's release path never fired in the round's 34-run sweep
    (ff_route_blocks_stale_released_total == 0 everywhere, because all five
    cleared units were already unbound), so shipping it on would add a
    never-executed code path. Rung 2 stays in the tree, tested, for whenever a
    case demands it. See outputs/latchfix_report.txt section 5.
    """
    assert cfv.ROUTE_BLOCK_STALE_CLEAR == 1


# ---------------------------------------------------------------- mode 0


def test_switch_off_is_a_no_op(capsys) -> None:
    cfv.ROUTE_BLOCK_STALE_CLEAR = 0
    model = _fresh_model()
    _reset_all_ff(model)
    ff = _latched(model, FF_A, CELL_A)
    _terminate_all_victims(model)
    assert model._any_victim_needs_rescue() is False
    before = len(_unassign_audit(model))
    capsys.readouterr()

    model._revalidate_route_blocked_firefighters()

    assert ff.status == "route_blocked"
    assert model._firefighter_available_for_dispatch(ff) is False
    assert getattr(model, "ff_route_blocks_stale_cleared_total", 0) == 0
    assert len(_unassign_audit(model)) == before
    assert "[Route Cleared]" not in capsys.readouterr().out


def test_switch_off_leaves_the_bound_latch_too(capsys) -> None:
    cfv.ROUTE_BLOCK_STALE_CLEAR = 0
    model = _fresh_model()
    _reset_all_ff(model)
    ff, _marker = _bound_latched(model, FF_A, CELL_A, V0)
    _mark_unreachable(model, V0)
    _terminate_all_victims(model, skip=(V0,))
    capsys.readouterr()

    model._revalidate_route_blocked_firefighters()

    assert ff.status == "route_blocked" and ff.assigned is True
    assert "[Route Cleared]" not in capsys.readouterr().out


@pytest.mark.parametrize("mode", (0, 1, 2))
def test_fast_path_is_untouched_at_every_mode(capsys, mode) -> None:
    """No flagged marker anywhere: both candidate lists empty, pass returns."""
    cfv.ROUTE_BLOCK_STALE_CLEAR = mode
    model = _fresh_model()
    _reset_all_ff(model)
    _terminate_all_victims(model)
    capsys.readouterr()

    model._revalidate_route_blocked_firefighters()

    assert "[Route Cleared]" not in capsys.readouterr().out
    assert getattr(model, "ff_route_blocks_stale_cleared_total", 0) == 0


# ---------------------------------------------------------------- rung 1


def test_mode_one_clears_the_unassigned_no_referent_unit(capsys) -> None:
    cfv.ROUTE_BLOCK_STALE_CLEAR = 1
    model = _fresh_model()
    _reset_all_ff(model)
    ff = _latched(model, FF_A, CELL_A)
    _terminate_all_victims(model)
    capsys.readouterr()

    model._revalidate_route_blocked_firefighters()

    # Cleared, and genuinely back in the dispatch pool - asserted through the
    # gate and the planner's own snapshot, not inferred from the status string.
    assert ff.status == "available"
    assert ff.assigned is False and ff.rescued_victim is None
    assert ff.target_pos is None
    assert model._firefighter_available_for_dispatch(ff) is True
    entry = model.get_rescue_operational_snapshot()["firefighters"][FF_A]
    assert entry["route_blocked"] is False
    assert entry["available"] is True
    assert model.ff_route_blocks_stale_cleared_total == 1
    out = capsys.readouterr().out
    assert CLEARED_LINE in out
    # No dispatch may follow: there is nothing left to dispatch to.
    assert not [e for e in _unassign_audit(model)]
    assert not [
        e
        for e in list(getattr(model, "_physical_rescue_command_audit", []) or [])
        if e.get("action") == "assign"
    ]


def test_mode_one_leaves_the_second_block_latch_flagged() -> None:
    """Pins the rung boundary, so rung 1 is not mistaken for complete."""
    cfv.ROUTE_BLOCK_STALE_CLEAR = 1
    model = _fresh_model()
    _reset_all_ff(model)
    ff, _marker = _bound_latched(model, FF_A, CELL_A, V0)
    _mark_unreachable(model, V0)
    _terminate_all_victims(model, skip=(V0,))
    assert model._any_victim_needs_rescue() is False

    model._revalidate_route_blocked_firefighters()

    assert ff.status == "route_blocked"
    assert ff.assigned is True


# ---------------------------------------------------------------- rung 2


def test_mode_two_releases_and_clears_the_bound_second_block_latch(capsys) -> None:
    cfv.ROUTE_BLOCK_STALE_CLEAR = 2
    model = _fresh_model()
    _reset_all_ff(model)
    ff, marker = _bound_latched(model, FF_A, CELL_A, V0)
    _mark_unreachable(model, V0)
    _terminate_all_victims(model, skip=(V0,))
    assert model._any_victim_needs_rescue() is False
    before = len(_unassign_audit(model))
    capsys.readouterr()

    model._revalidate_route_blocked_firefighters()

    assert ff.status == "available"
    assert ff.assigned is False
    assert ff.rescued_victim is None
    assert ff.target_pos is None
    assert model._firefighter_available_for_dispatch(ff) is True
    entry = model.get_rescue_operational_snapshot()["firefighters"][FF_A]
    assert entry["route_blocked"] is False and entry["available"] is True
    assert model.ff_route_blocks_stale_released_total == 1
    assert model.ff_route_blocks_stale_cleared_total == 1
    assert CLEARED_LINE in capsys.readouterr().out

    # Exactly one release, through the audited path, with the round's own reason
    # and WITHOUT reset_victim_pending - that flag would relabel the terminal
    # victim back to "confirmed" and resurrect it.
    added = _unassign_audit(model)[before:]
    assert len(added) == 1
    assert added[0].get("reason") == "stale_route_block_no_referent"
    assert not (added[0].get("metadata") or {}).get("reset_victim_pending")

    # The victim stays terminal.
    state = model.managed_victims[V0]
    assert bool(getattr(state, "unreachable", False)) is True
    assert bool(getattr(state, "cancelled", False)) is True
    assert str(marker.status).lower() == "unreachable"
    assert model._victim_needs_rescue(V0, marker) is False


def test_mode_two_still_clears_the_plain_unassigned_latch(capsys) -> None:
    """Rung 2 is a strict superset of rung 1."""
    cfv.ROUTE_BLOCK_STALE_CLEAR = 2
    model = _fresh_model()
    _reset_all_ff(model)
    ff = _latched(model, FF_A, CELL_A)
    _terminate_all_victims(model)
    before = len(_unassign_audit(model))
    capsys.readouterr()

    model._revalidate_route_blocked_firefighters()

    assert ff.status == "available"
    assert model.ff_route_blocks_stale_cleared_total == 1
    # An unbound unit needs no release.
    assert getattr(model, "ff_route_blocks_stale_released_total", 0) == 0
    assert len(_unassign_audit(model)) == before
    assert CLEARED_LINE in capsys.readouterr().out


# ---------------------------------------------------------------- the guards


@pytest.mark.parametrize("mode", (1, 2))
def test_fire_enclosed_unit_stays_flagged(mode) -> None:
    """70e1b33's trapped guard, via _firefighter_fire_enclosed, not a copy.

    A unit with no fire-free neighbour is genuinely blocked whatever else is
    true, and the pass that owns the flag holds it back deliberately.
    """
    cfv.ROUTE_BLOCK_STALE_CLEAR = mode
    model = _fresh_model()
    _reset_all_ff(model)
    ff = _latched(model, FF_A, CELL_A)
    _enclose(ff)
    _terminate_all_victims(model)
    assert model._firefighter_fire_enclosed(ff) is True

    model._revalidate_route_blocked_firefighters()

    assert ff.status == "route_blocked"
    assert getattr(model, "ff_route_blocks_stale_cleared_total", 0) == 0


@pytest.mark.parametrize("mode", (1, 2))
def test_dead_unit_is_untouched(mode) -> None:
    cfv.ROUTE_BLOCK_STALE_CLEAR = mode
    model = _fresh_model()
    _reset_all_ff(model)
    ff = _latched(model, FF_A, CELL_A)
    ff.dead = True
    _terminate_all_victims(model)

    model._revalidate_route_blocked_firefighters()

    assert ff.status == "route_blocked"


@pytest.mark.parametrize("mode", (1, 2))
def test_exiting_unit_is_untouched(mode) -> None:
    """An exiting unit is carrying; agents.py's own clear is still live for it,
    and 70e1b33's pre-ship bug was exactly a corner-trapped CARRIER."""
    cfv.ROUTE_BLOCK_STALE_CLEAR = mode
    model = _fresh_model()
    _reset_all_ff(model)
    ff = _latched(model, FF_A, CELL_A)
    ff.exiting = True
    ff.exit_target = (0, 2)
    _terminate_all_victims(model)

    model._revalidate_route_blocked_firefighters()

    assert ff.status == "route_blocked"


@pytest.mark.parametrize("mode", (1, 2))
def test_off_grid_unit_is_untouched(mode) -> None:
    cfv.ROUTE_BLOCK_STALE_CLEAR = mode
    model = _fresh_model()
    _reset_all_ff(model)
    ff = _latched(model, FF_A, CELL_A)
    model.grid.remove_agent(ff)
    assert getattr(ff, "pos", None) is None
    _terminate_all_victims(model)

    model._revalidate_route_blocked_firefighters()

    assert ff.status == "route_blocked"


@pytest.mark.parametrize("mode", (1, 2))
def test_live_victim_leaves_the_flag_to_the_ordinary_pass(capsys, mode) -> None:
    """With work left the branch must be invisible: the pass's own BFS decides."""
    cfv.ROUTE_BLOCK_STALE_CLEAR = mode
    model = _fresh_model()
    _reset_all_ff(model)
    ff = _latched(model, FF_A, CELL_A)
    _terminate_all_victims(model, skip=(V1,))
    marker = model.victim_marker_agents[V1]
    model.grid.move_agent(marker, VICTIM_CELL)
    marker.status = "confirmed"
    state = model.managed_victims[V1]
    state.confirmed = True
    state.status = "confirmed"
    state.rescued = False
    assert model._any_victim_needs_rescue() is True
    capsys.readouterr()

    model._revalidate_route_blocked_firefighters()

    # The ordinary path found a fire-free route and cleared it with ITS message;
    # the new branch contributed nothing.
    out = capsys.readouterr().out
    assert CLEARED_LINE not in out
    assert getattr(model, "ff_route_blocks_stale_cleared_total", 0) == 0


# ---------------------------------------------------------------- the premise


def test_terminal_victim_stays_out_of_the_planner_after_a_pending_reset() -> None:
    """The fact the clear's safety actually rests on - pinned so a later round
    cannot remove it silently.

    "No dispatch can follow" is NOT because victim status is monotone: the
    reset_victim_pending arm of the unassign relabels a victim "confirmed"
    (guarded only against dead and rescued) and writes the marker unguarded. It
    holds because mark_unreachable also sets state.cancelled and
    state.unreachable, reset_victim_pending resets NEITHER, the snapshot exports
    both, and the planner drops any victim carrying either.
    """
    model = _fresh_model()
    _reset_all_ff(model)
    ff, marker = _bound_latched(model, FF_A, CELL_A, V0)
    _mark_unreachable(model, V0)
    _terminate_all_victims(model, skip=(V0,))
    ff.status = "available"

    # The resurrection path: an unassign carrying reset_victim_pending.
    model.apply_physical_rescue_command(
        PhysicalRescueCommand(
            action="unassign",
            victim_id=V0,
            firefighter_id=FF_A,
            reason="replacement_after_casualty",
            metadata={"reset_victim_pending": True},
        )
    )

    # The relabel really does happen - this is the non-monotonicity.
    assert str(marker.status).lower() == "confirmed"
    # ...and it is harmless, because these two are never reset.
    state = model.managed_victims[V0]
    assert bool(getattr(state, "unreachable", False)) is True
    assert bool(getattr(state, "cancelled", False)) is True

    snapshot = model.get_rescue_operational_snapshot()
    assert snapshot["victims"][V0]["unreachable"] is True
    assert snapshot["victims"][V0]["cancelled"] is True
    decision = select_rescue_assignment(snapshot, "replacement_after_casualty")
    assert str(getattr(decision, "rescue_action", "")).lower() != "assign"
