"""VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX: the legality guard on the victim
searcher hazard gate's two unvalidated fall-through returns.

The defect: when no safe in-bounds neighbour exists,
_apply_victim_searcher_hazard_gate falls through and returns the UPSTREAM
direction with no bounds test. At a grid edge that direction leaves the grid and
agents.py move() refuses it silently, so the same illegal move is re-emitted
every step until the local fire burns out. All ten recorded pins were on a
boundary. Derivation: outputs/searcherfix_part1.txt.

These pin:
  * the kill switch, including that ONLY an exact integral zero disables it
    (0.5 must NOT disarm - the int(0.5) == 0 defect class);
  * that the guard is an exact identity on any already-legal direction;
  * the bounds INVARIANT at all four edges and all four corners, for every
    chosen direction;
  * that rung 1 is the strictly-inward reverse and rung 2 is the nearest-index
    scan, and that the two genuinely differ (which is why they are separate);
  * that the gate itself never returns an off-grid direction when the guard
    is on, driven end to end through the fall-through.
"""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import common_fixed_variables as cfv
from src_extension.execution.uav_executor import UAVExecutor

from test_uav_executor import _FakeAgent, _bfs_test_model

# agents.py:823 "[0,1,2,3] = [right, down, left, up]"
EAST, SOUTH, WEST, NORTH = 0, 1, 2, 3
MOVE_X = [1, 0, -1, 0]
MOVE_Y = [0, -1, 0, 1]
H = W = 50
ACTION = "victim_search_wind_aware"


def _exec(pos, fire_cells=None, uav_id="2502"):
    agent = _FakeAgent(unique_id=int(uav_id), pos=pos)
    model = _bfs_test_model(fire_cells=set(fire_cells or ()))
    model.managed_uav_states = {
        uav_id: type("S", (), {"role": "victim_searcher", "position": pos})()
    }
    model._wind_search_target_state = {}
    ex = UAVExecutor(uav_id=uav_id, model=model, agent=agent)
    ex._read_uav_role = lambda: "victim_searcher"  # type: ignore[method-assign]
    return ex, agent


def _in_bounds(pos, direction):
    return (0 <= pos[0] + MOVE_X[direction] < H
            and 0 <= pos[1] + MOVE_Y[direction] < W)


# The outward direction at each of the four edges and the two outward
# directions at each of the four corners.
EDGE_CASES = [
    ((27, 0), SOUTH),
    ((23, 0), SOUTH),
    ((49, 12), EAST),
    ((49, 3), EAST),
    ((39, 49), NORTH),
    ((0, 20), WEST),
]
CORNER_CASES = [
    ((0, 0), SOUTH), ((0, 0), WEST),
    ((49, 0), SOUTH), ((49, 0), EAST),
    ((0, 49), NORTH), ((0, 49), WEST),
    ((49, 49), NORTH), ((49, 49), EAST),
]


# ------------------------------------------------------------ kill switch ----
def test_default_is_on_at_rung_one():
    assert cfv.VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX == 1


def test_zero_disables_and_the_direction_passes_through(monkeypatch):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 0)
    ex, agent = _exec((27, 0))
    assert ex._offgrid_guard_level() == 0
    # SOUTH from y=0 leaves the grid and is handed straight back
    assert ex._offgrid_guard_direction(agent, SOUTH) == SOUTH


@pytest.mark.parametrize("raw", [0, "0", 0.0, False])
def test_only_an_exact_integral_zero_disables(monkeypatch, raw):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", raw)
    ex, _ = _exec((27, 0))
    assert ex._offgrid_guard_level() == 0


@pytest.mark.parametrize("raw", [0.5, -0.5, 1.5, "off", None, "", object()])
def test_a_non_integral_or_junk_value_does_not_disarm(monkeypatch, raw):
    """The int(0.5) == 0 defect class: a bare cast would silently take the OFF
    path. The fallback is the SHIPPED value, so junk ARMS rather than disarms."""
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", raw)
    ex, _ = _exec((27, 0))
    assert ex._offgrid_guard_level() != 0
    assert ex._offgrid_guard_level() == UAVExecutor._OFFGRID_GUARD_SHIPPED


def test_the_level_is_read_from_the_module_at_call_time(monkeypatch):
    ex, _ = _exec((27, 0))
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 0)
    assert ex._offgrid_guard_level() == 0
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 2)
    assert ex._offgrid_guard_level() == 2


# --------------------------------------------------------------- identity ----
@pytest.mark.parametrize("level", [1, 2])
@pytest.mark.parametrize("direction", [EAST, SOUTH, WEST, NORTH])
def test_an_already_legal_direction_is_returned_unchanged(monkeypatch, level, direction):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", level)
    ex, agent = _exec((25, 25))  # deep interior: every direction is legal
    assert ex._offgrid_guard_direction(agent, direction) == direction


# ------------------------------------------------------- the bounds rule -----
@pytest.mark.parametrize("level", [1, 2])
@pytest.mark.parametrize("pos,direction", EDGE_CASES + CORNER_CASES)
def test_the_guard_always_returns_an_in_bounds_direction(monkeypatch, level, pos, direction):
    """THE INVARIANT. At every edge and every corner, for the outward direction,
    the guard returns something the grid will accept."""
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", level)
    ex, agent = _exec(pos)
    assert not _in_bounds(pos, direction), "test case is not actually off-grid"
    out = ex._offgrid_guard_direction(agent, direction)
    assert _in_bounds(pos, out), "guard returned an off-grid direction"


@pytest.mark.parametrize("pos,direction", EDGE_CASES + CORNER_CASES)
def test_rung_one_is_the_reverse_and_is_strictly_inward(monkeypatch, pos, direction):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 1)
    ex, agent = _exec(pos)
    out = ex._offgrid_guard_direction(agent, direction)
    assert out == (direction + 2) % 4
    # the offending coordinate strictly improves
    axis = 0 if MOVE_X[direction] else 1
    before = pos[axis]
    after = pos[axis] + (MOVE_X[out] if axis == 0 else MOVE_Y[out])
    limit = (H - 1) if axis == 0 else (W - 1)
    assert min(after, limit - after) > min(before, limit - before)


def test_rung_one_and_rung_two_genuinely_differ(monkeypatch):
    """Why the ladder is not bundled: at (27,0) with SOUTH off-grid, rung 1
    takes the reverse (NORTH, inward) and rung 2's nearest-index scan takes the
    first in-bounds of (SOUTH, WEST, EAST, NORTH) - WEST, along the edge."""
    ex, agent = _exec((27, 0))
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 1)
    assert ex._offgrid_guard_direction(agent, SOUTH) == NORTH
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 2)
    assert ex._offgrid_guard_direction(agent, SOUTH) == WEST


def test_it_cannot_be_starved_where_the_margin_three_filter_is(monkeypatch):
    """At a corner _retreat_to_safe_interior_direction is structurally unable to
    return anything - all four directions are edge-blocked regardless of fire -
    which is exactly why the guard may not reuse that filter."""
    ex, agent = _exec((0, 0))
    for direction in range(4):
        assert ex._victim_edge_blocked_direction(agent, direction)
    assert ex._retreat_to_safe_interior_direction(agent) is None
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 1)
    assert _in_bounds((0, 0), ex._offgrid_guard_direction(agent, SOUTH))
    assert _in_bounds((0, 0), ex._offgrid_guard_direction(agent, WEST))


# -------------------------------------------------- end to end, the gate -----
@pytest.mark.parametrize("pos,direction", EDGE_CASES + CORNER_CASES)
def test_the_gate_never_returns_an_off_grid_direction_when_on(monkeypatch, pos, direction):
    """Drive the real gate through SITE A: force the searcher's own cell to read
    hazardous so the first branch is taken, and force the retreat to find
    nothing, which is what every recorded pin did."""
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 1)
    ex, agent = _exec(pos)
    monkeypatch.setattr(ex, "_strict_victim_hazard_level", lambda cell: 2)
    monkeypatch.setattr(ex, "_retreat_to_safe_interior_direction", lambda a: None)
    out, label = ex._apply_victim_searcher_hazard_gate(agent, direction, ACTION)
    assert _in_bounds(pos, out)
    assert label == "victim_search_hazard_retreat_oob_oncell"
    assert "victim_search_hazard_retreat" in label


@pytest.mark.parametrize("pos,direction", EDGE_CASES)
def test_the_gate_reproduces_the_defect_when_the_switch_is_off(monkeypatch, pos, direction):
    """The positive control: with the guard off, the gate hands back the
    off-grid direction - the behaviour every recorded pin is made of."""
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 0)
    ex, agent = _exec(pos)
    monkeypatch.setattr(ex, "_strict_victim_hazard_level", lambda cell: 2)
    monkeypatch.setattr(ex, "_retreat_to_safe_interior_direction", lambda a: None)
    out, label = ex._apply_victim_searcher_hazard_gate(agent, direction, ACTION)
    assert out == direction
    assert not _in_bounds(pos, out)
    assert label == "victim_search_hazard_retreat"


def test_the_worked_example_from_the_diagnosis(monkeypatch):
    """seed 404 south, uid 2502, cell (27,0), 26 consecutive refused steps with
    applied direction 1 (SOUTH) on every one. With the guard on, the gate
    returns 3 (NORTH) and the searcher leaves the boundary."""
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 1)
    ex, agent = _exec((27, 0))
    monkeypatch.setattr(ex, "_strict_victim_hazard_level", lambda cell: 2)
    monkeypatch.setattr(ex, "_retreat_to_safe_interior_direction", lambda a: None)
    out, _ = ex._apply_victim_searcher_hazard_gate(agent, SOUTH, ACTION)
    assert out == NORTH


def test_the_guard_is_idempotent(monkeypatch):
    """The gate can run twice in one step (once inside _resolve_direction_intent,
    again at the primary dispatch site), so applying it twice must equal
    applying it once."""
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", 1)
    ex, agent = _exec((27, 0))
    once = ex._offgrid_guard_direction(agent, SOUTH)
    assert ex._offgrid_guard_direction(agent, once) == once
