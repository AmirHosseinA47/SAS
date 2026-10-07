"""MVG round, Part 2d (outputs/urgency_part1d.txt 1d.8 (4)): the urgency round's MOVEMENT tests (outputs/urgency_part1.txt
22.6.2, amendment B1, rulings 23), ported for the two fixes this branch carries - (a) FF_APPROACH_PATH and (b)
FF_RETREAT_KEEP_APPROACH - plus T-SAFE-M, T-SW-M, T-ID-M and T-NT (22.6.1's NOT-TOUCHED list, re-based to this
branch's base a20a2ef5 and to its own touched set). Fix (c) and U1 are not carried (ruling, urgency report 11) and
their tests are not ported. The stranding guard's own tests (T-G1..T-G8) are in tests/test_stranding_guard.py.

THE GUARD IN THESE TESTS. Every test passes the guard switch explicitly (_model's `guard`), as it passes every other
switch it reads. The default here is guard = 0: these tests pin the fixes AS SCREENED in the urgency round (the
guard can only replace a fix step by today's, Part 1d 1d.2.5 G1, so a property of the unguarded fix is a property of
its logic). The safety and route_blocked properties that must also hold for GUARDED fix steps (T-SAFE-M, T-Ma8, T-Mb4)
run with the guard at 0 AND at 1.

Every test names its MUTANT ("MUTANT: <id>"): the smallest exact-text source change that removes what the test
guards, kept in outputs/_mvg_mutants_mv.py (MUTANTS_MV; the ids are the urgency round's, re-anchored to this branch,
plus sw_strict_b, sw_import_b and sw_shipped_b: the (b) accessor's mirrors of the (a)-only switch mutants, added by
the Part 2d review fix C-3).
Each listed test FAILS on its mutant and PASSES on the unmutated source (15.3 / 15.4); the per-mutant record is
that script's output.

Drives the REAL WildFireModel through tests/mvg_test_support.py: the map is quieted, fire and smoke are laid on
chosen cells (burning as numpy.bool_, the simulator's own type), units and victims are parked, and one unit's
advance() or one model method is called directly. Only T-ID-M runs model.step() (a short pinned run). Every
expected value comes from an ORACLE in this file - its own clean predicate, BFS and fire-free route test - never
from the code under test.

Coordinates are (x, y) on the 50 x 50 grid; the neighbour order is (+x, -x, +y, -y). CLEAN = in bounds, not
burning, not smoky, no burning 4-neighbour (22.2.1). G-ESC = the victim's clean region holds a grid-boundary cell.
"""

from __future__ import annotations

import ast
import hashlib
import io
import os
import random
import subprocess
from collections import deque
from contextlib import redirect_stdout
from pathlib import Path

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
from src_extension.planning import movement_paths
from mvg_test_support import (
    FF_A,
    SWITCH_NAMES,
    V0,
    V2,
    assign,
    burn,
    ff,
    fire_agents,
    pinned_model,
    place_units,
    place_victims,
    quiet_fire,
    restore_config,
    smoke,
    switches,
    victim,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _pristine_config(monkeypatch):
    """Every test starts from the import-time configuration: the full suite's other files leave scenario settings
    behind, and the real-model tests here (T-ID-M's golden digest among them) depend on them. A test's own switches
    are set afterwards and win; monkeypatch undoes all of it."""
    restore_config(monkeypatch)
OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1))
TIER_A, TIER_B = 7, 10                               # agents.APPROACH_PATH_TIER, RETREAT_ON_ROUTE_TIER (22.5)
TIER_PATH, TIER_HOLD = 5, 6                          # agents.EXIT_LEG_PATH_TIER, EXIT_LEG_HOLD_TIER

# The barrier board of 22.1 / 22.2 (a fire wall across the approach): the victim is straight behind the wall.
WALL = tuple((x, 25) for x in range(15, 36))
BARRIER_UNIT, BARRIER_VICTIM = (25, 20), (25, 30)


# ============================================================================ construction

def _model(monkeypatch, *, approach=0, retreat=0, guard=0, mode=2, served=1, hold=0):
    """A pinned real model (scenario A's team) with its map quieted and EVERY switch this file reads passed
    explicitly: the round's three on cfv - the two fixes and the stranding guard (0 here unless a test says so: the
    fixes as screened, see the module docstring) - and the carrying leg's MODE / SERVED / HOLD (shipped 2 / 1 / 0)."""
    switches(monkeypatch, approach=approach, retreat=retreat, guard=guard,
             FF_EXIT_LEG_MODE=mode, FF_EXIT_LEG_SERVED=served, FF_EXIT_LEG_HOLD=hold)
    with redirect_stdout(io.StringIO()):
        model = pinned_model(monkeypatch)
    quiet_fire(model)
    return model


def _set(monkeypatch, **values):
    for name, value in values.items():
        monkeypatch.setattr(cfv, name, value, raising=False)


def _cell(agent):
    return (int(agent.pos[0]), int(agent.pos[1]))


def _approacher(model, unit_cell, victim_cell, *, status=None, extra_units=None):
    """FF_A bound to V0 through the executor, APPROACHING (not on her cell). Every other unit dead unless listed."""
    units = {FF_A: unit_cell}
    units.update(extra_units or {})
    place_units(model, units)
    place_victims(model, {V0: victim_cell})
    with redirect_stdout(io.StringIO()):
        assert assign(model, V0, FF_A)
    unit = ff(model, FF_A)
    assert unit.target_pos == victim_cell and not unit.exiting
    if status is not None:
        unit.status = status
    return unit


def _advance(unit):
    with redirect_stdout(io.StringIO()):
        unit.advance()


def _lay(model, burning=(), smoky=()):
    quiet_fire(model)
    burn(model, burning)
    smoke(model, smoky)


def _spy(monkeypatch, name, log, *, through=True, cls=agents.Firefighter):
    original = getattr(cls, name)

    def spy(self, *args, **kwargs):
        result = original(self, *args, **kwargs) if through else None
        log.append((name, getattr(self, "unit_id", None), args, result))
        return result

    monkeypatch.setattr(cls, name, spy)


def _retreat_state(unit) -> dict:
    return {name: getattr(unit, name, None) for name in
            ("_idle_retreat_origin", "_idle_retreat_steps", "_idle_retreat_stalled", "_idle_retreat_last_cell")}


def _outcome(unit) -> tuple:
    reason = unit.movement_reason or {}
    return (_cell(unit), unit.status, unit._last_move_tier, unit._last_move_risk, reason.get("fine_category"),
            unit.exiting, _retreat_state(unit))


# ============================================================================ the oracle (independent of the code)

def _inb(model, c) -> bool:
    return 0 <= c[0] < model.grid.width and 0 <= c[1] < model.grid.height


def _nbrs(model, c) -> list:
    return [(c[0] + ox, c[1] + oy) for ox, oy in OFFSETS if _inb(model, (c[0] + ox, c[1] + oy))]


def _board(model) -> tuple[set, set]:
    burning, smoky = set(), set()
    for fire in fire_agents(model):
        cell = (int(fire.pos[0]), int(fire.pos[1]))
        if fire.burning:
            burning.add(cell)
        if fire.smoke.smoke:
            smoky.add(cell)
    return burning, smoky


def _fire_adjacent(c, burning) -> bool:
    return any((c[0] + ox, c[1] + oy) in burning for ox, oy in OFFSETS)


def _is_clean(model, c, burning, smoky) -> bool:
    return _inb(model, c) and c not in burning and c not in smoky and not _fire_adjacent(c, burning)


def _bfs(model, src, passable) -> dict:
    if not _inb(model, src) or not passable(src):
        return {}
    dist = {src: 0}
    queue = deque([src])
    while queue:
        c = queue.popleft()
        for n in _nbrs(model, c):
            if n not in dist and passable(n):
                dist[n] = dist[c] + 1
                queue.append(n)
    return dist


def _clean_field(model, target, burning, smoky) -> dict:
    return _bfs(model, target, lambda c: _is_clean(model, c, burning, smoky))


def _on_boundary(model, c) -> bool:
    return c[0] in (0, model.grid.width - 1) or c[1] in (0, model.grid.height - 1)


def _gesc(model, field) -> bool:
    return any(_on_boundary(model, c) for c in field)


def _fire_free_route(model, src, dst, burning) -> bool:
    """Today's route_blocked predicate, re-derived: 4-connected, burning impassable, the source never tested, the
    destination reachable even when it burns."""
    if src == dst:
        return True
    seen = {src}
    queue = deque([src])
    while queue:
        c = queue.popleft()
        for n in _nbrs(model, c):
            if n in seen:
                continue
            if n == dst:
                return True
            if n in burning:
                continue
            seen.add(n)
            queue.append(n)
    return False


def _fire_dist(c, burning) -> int:
    return min(abs(c[0] - b[0]) + abs(c[1] - b[1]) for b in burning) if burning else 999


def _ring(x0, x1, y0, y1) -> set:
    """The burning (or smoky) border of the rectangle [x0, x1] x [y0, y1]."""
    return ({(x, y0) for x in range(x0, x1 + 1)} | {(x, y1) for x in range(x0, x1 + 1)}
            | {(x0, y) for y in range(y0, y1 + 1)} | {(x1, y) for y in range(y0, y1 + 1)})


def _square(centre, radius) -> set:
    return _ring(centre[0] - radius, centre[0] + radius, centre[1] - radius, centre[1] + radius)


def _random_box_fire(rng, model) -> tuple[set, set, tuple]:
    """A random board inside a corner box (12-24 cells a side, at a random corner) fenced off from the rest of the
    grid by a burning L along its two inner sides, so its clean region touches the grid boundary on two sides and
    every BFS stays small: 2-5 walls (3-12 long), 0-4 single cells and 0-6 smoky cells inside. Returns the box
    (x0, x1, y0, y1), inclusive."""
    width, height = model.grid.width, model.grid.height
    w, h = rng.randint(12, 24), rng.randint(12, 24)
    x0, x1 = (0, w - 1) if rng.random() < 0.5 else (width - w, width - 1)
    y0, y1 = (0, h - 1) if rng.random() < 0.5 else (height - h, height - 1)
    fx = x1 + 1 if x0 == 0 else x0 - 1
    fy = y1 + 1 if y0 == 0 else y0 - 1
    burning = {(fx, y) for y in range(min(y0, fy), max(y1, fy) + 1)} | {(x, fy) for x in range(min(x0, fx), max(x1, fx) + 1)}
    for _ in range(rng.randint(2, 5)):
        horizontal = rng.random() < 0.5
        length = rng.randint(3, 12)
        cx, cy = rng.randint(x0, x1), rng.randint(y0, y1)
        for i in range(length):
            c = (cx + i, cy) if horizontal else (cx, cy + i)
            if x0 <= c[0] <= x1 and y0 <= c[1] <= y1:
                burning.add(c)
    for _ in range(rng.randint(0, 4)):
        burning.add((rng.randint(x0, x1), rng.randint(y0, y1)))
    smoky = {(rng.randint(x0, x1), rng.randint(y0, y1)) for _ in range(rng.randint(0, 6))} - burning
    return burning, smoky, (x0, x1, y0, y1)


def _random_cell(rng, model, ok, tries=400, box=None):
    x0, x1, y0, y1 = box or (0, model.grid.width - 1, 0, model.grid.height - 1)
    for _ in range(tries):
        c = (rng.randint(x0, x1), rng.randint(y0, y1))
        if ok(c):
            return c
    return None


def _reset_approacher(model, unit, cell, victim_cell, status):
    """Re-use one bound unit on a new board: park it and its victim, approaching, with no retreat memory."""
    model.grid.move_agent(victim(model, V0), victim_cell)
    model.grid.move_agent(unit, cell)
    unit.target_pos = victim_cell
    unit.exiting = False
    unit.exit_target = None
    unit.status = status
    unit._reset_idle_retreat_state()


# ============================================================================ (a) FF_APPROACH_PATH

def test_ma1_barrier_board_reaches_the_victim_in_d_steps(monkeypatch):
    """T-Ma1. The barrier board: a fire wall straight across the approach. Today's greedy mover 2-cycles in front of
    it forever; with (a) the unit reaches the victim in exactly D(start) = 34 advances, the clean distance falling
    by 1 per advance, on clean cells only, with no revisit.
    MUTANTS: ma1_switch (the switch ignored: the accessor never reads it); ma1_pass (passable = non-burning)."""
    model = _model(monkeypatch, approach=1)
    unit = _approacher(model, BARRIER_UNIT, BARRIER_VICTIM)
    burn(model, WALL)
    burning, smoky = _board(model)
    field = _clean_field(model, BARRIER_VICTIM, burning, smoky)
    d0 = field[BARRIER_UNIT]
    assert d0 == 34 and _gesc(model, field)
    cells, tiers = [], []
    for k in range(1, d0 + 1):
        _advance(unit)
        cells.append(_cell(unit))
        tiers.append(unit._last_move_tier)
        assert field.get(cells[-1]) == d0 - k, (k, cells[-1])
    assert cells[-1] == BARRIER_VICTIM and len(set(cells)) == d0
    assert TIER_A in tiers

    # The same board with the switch at 0 is today's 2-cycle: it never arrives.
    _set(monkeypatch, FF_APPROACH_PATH=0)
    model0 = _model(monkeypatch)
    unit0 = _approacher(model0, BARRIER_UNIT, BARRIER_VICTIM)
    burn(model0, WALL)
    seen = []
    for _ in range(2 * d0):
        _advance(unit0)
        seen.append(_cell(unit0))
    assert BARRIER_VICTIM not in seen and set(seen[-10:]) == {(25, 23), (26, 23)}


_MA2_CASES = {
    # a smoky (not burning) band splits the grid: a fire-free route exists, a clean one does not
    "no_clean_path": dict(unit=(25, 24), victim=(25, 30), burning=(), smoky=tuple((x, 25) for x in range(50)),
                          today=(26, 24)),
    # the victim's own cell is unclean (smoky): no clean path ENDS there
    "unclean_victim": dict(unit=(25, 29), victim=(25, 30), burning=(), smoky=((25, 30),), today=(26, 29)),
    # a clean path exists but the victim's clean region is enclosed by a smoke ring: G-ESC is false
    "gesc_false": dict(unit=(26, 23), victim=(25, 30), burning=tuple((x, 25) for x in range(19, 32)),
                       smoky=tuple(sorted(_square((25, 25), 12))), today=(25, 23)),
}


@pytest.mark.parametrize("case", sorted(_MA2_CASES))
def test_ma2_without_a_qualifying_clean_path_todays_mover_runs(monkeypatch, case):
    """T-Ma2. No clean path, an unclean victim cell, or G-ESC false: (a) does not act, _move_toward(target) is called
    exactly once (spy), and the outcome equals the switch-0 twin's. In every case today's step is OFF a shortest
    fire-free (resp. clean) path, so a fix that acted would move elsewhere.
    MUTANTS: ma2_burning (with no clean path, (a) follows a shortest fire-free path) - kills no_clean_path and
    unclean_victim; ma2_gesc (G-ESC removed from (a)) - kills gesc_false."""
    spec = _MA2_CASES[case]
    calls: list = []
    _spy(monkeypatch, "_move_toward", calls)
    outcomes, choice = {}, None
    for approach in (1, 0):
        model = _model(monkeypatch, approach=approach)
        unit = _approacher(model, spec["unit"], spec["victim"])
        _lay(model, spec["burning"], spec["smoky"])
        burning, smoky = _board(model)
        assert _is_clean(model, spec["unit"], burning, smoky)          # the approach branch, not survival
        if approach:
            choice = unit._approach_path_choice()                      # pure: read before the advance
        del calls[:]
        _advance(unit)
        assert [(c[0], c[2]) for c in calls] == [("_move_toward", (spec["victim"],))]
        outcomes[approach] = _outcome(unit)
    assert outcomes[1] == outcomes[0]
    assert outcomes[1][0] == spec["today"]
    assert choice is None


def test_ma3_today_first_on_open_ground(monkeypatch):
    """T-Ma3. TODAY-FIRST (ruling V-6): on open ground both (+x) and (+y) are on a shortest clean path, today's
    preferred (+x) step is kept although (+y) is farther from the fire, and ACTED(a) is false.
    MUTANT: ma3_tiebreak (the fire-distance tie-break applied to every step)."""
    model = _model(monkeypatch, approach=1)
    unit = _approacher(model, (20, 20), (25, 25))
    burn(model, [(30, 15)])
    burning, smoky = _board(model)
    field = _clean_field(model, (25, 25), burning, smoky)
    assert field[(21, 20)] == field[(20, 21)] == field[(20, 20)] - 1
    assert _fire_dist((20, 21), burning) > _fire_dist((21, 20), burning)
    choice = unit._approach_path_choice()                              # pure: read before the advance
    _advance(unit)
    assert _cell(unit) == (21, 20) and unit._last_move_tier == 1
    assert choice is None                                              # ACTED(a) is false


def test_ma3_greedy_choice_is_move_towards_destination(monkeypatch):
    """T-Ma3 (today's step, as (a) reads it). TODAY-FIRST rests on the pure replica of _move_toward's tier choice
    (also the instrument's today-shadow, 22.6.3): over 400 random boards - fire and smoke around an approaching unit,
    targets in every direction, ties of |dx| and |dy| included - _greedy_choice equals the cell _move_toward actually
    moves to (None = every neighbour burns and it does not move). The raise is stubbed (it moves nothing).
    MUTANT: ma3_replica (the replica's axis rule |dx| >= |dy| changed to >)."""
    model = _model(monkeypatch)
    unit = _approacher(model, (25, 25), (30, 30))
    status = unit.status
    raises: list = []
    _spy(monkeypatch, "_mark_route_blocked", raises, through=False)
    rng = random.Random(2275)
    for sample in range(400):
        burning = {(25 + rng.randint(-3, 3), 25 + rng.randint(-3, 3)) for _ in range(rng.randint(0, 9))}
        burning.discard((25, 25))
        smoky = {(25 + rng.randint(-2, 2), 25 + rng.randint(-2, 2)) for _ in range(rng.randint(0, 3))} - burning
        v = (25 + rng.randint(-6, 6), 25 + rng.randint(-6, 6))
        if v == (25, 25):
            continue
        _lay(model, burning, smoky)
        _reset_approacher(model, unit, (25, 25), v, status)
        choice = unit._greedy_choice(v, *_board(model))
        with redirect_stdout(io.StringIO()):
            unit._move_toward(v)
        assert _cell(unit) == (choice if choice is not None else (25, 25)), (sample, v, choice, _cell(unit))


def test_ma4_off_path_today_takes_the_larger_fire_distance(monkeypatch):
    """T-Ma4. A dead-end bay opens toward the unit: today's tier-1 step enters it (off every shortest clean path).
    Three neighbours are on a shortest clean path - (+x), (-x) and (-y) - and (a) takes the one with the larger
    minimum fire distance, (-y), not the first in search order, (+x).
    MUTANT: ma4_order (order-only: the first shortest-path neighbour in search order)."""
    model = _model(monkeypatch, approach=1)
    unit = _approacher(model, (25, 21), BARRIER_VICTIM)
    bay = [(23, y) for y in range(22, 25)] + [(27, y) for y in range(22, 25)]
    burn(model, list(WALL) + bay)
    burning, smoky = _board(model)
    field = _clean_field(model, BARRIER_VICTIM, burning, smoky)
    d = field[(25, 21)]
    on_path = [n for n in _nbrs(model, (25, 21)) if field.get(n) == d - 1]
    assert on_path == [(26, 21), (24, 21), (25, 20)]
    assert field[(25, 22)] == d + 1                                   # today's step: into the bay
    assert [_fire_dist(c, burning) for c in on_path] == [2, 2, 4]
    _advance(unit)
    assert _cell(unit) == (25, 20) and unit._last_move_tier == TIER_A

    _set(monkeypatch, FF_APPROACH_PATH=0)                             # today's step on the same board: the bay
    model0 = _model(monkeypatch)
    unit0 = _approacher(model0, (25, 21), BARRIER_VICTIM)
    burn(model0, list(WALL) + bay)
    _advance(unit0)
    assert _cell(unit0) == (25, 22) and unit0._last_move_tier == 1


def test_ma5_an_a_step_relabels_a_route_blocked_unit_tier_7_risk_0(monkeypatch):
    """T-Ma5. An (a) step applies _move_toward's tail relabel (a unit labelled route_blocked is visible again), sets
    tier 7 and risk 0, and raises nothing.
    MUTANT: ma5_relabel (the relabel removed from the (a) step)."""
    model = _model(monkeypatch, approach=1)
    unit = _approacher(model, (26, 23), BARRIER_VICTIM, status="route_blocked")
    burn(model, WALL)
    raises: list = []
    _spy(monkeypatch, "_mark_route_blocked", raises)
    assert unit._approach_path_choice() == (27, 23)
    _advance(unit)
    assert _cell(unit) == (27, 23)
    assert (unit._last_move_tier, unit._last_move_risk) == (TIER_A, 0)
    assert unit.status == "assigned" and raises == []
    assert unit.model._find_active_firefighter_for_victim(V0, victim(unit.model, V0)) == (FF_A, unit)


def test_ma6_property_the_clean_distance_falls_by_one_per_step(monkeypatch):
    """T-Ma6. Property test, 500 random static boards (a fenced corner box with walls, single cells and smoke):
    from a start with a finite clean distance D inside a G-ESC region, every advance - an (a) step or a kept today
    step - lowers D by exactly 1, on a clean cell, so the unit arrives after D(start) advances and never revisits a
    cell. The boards favour starts behind a barrier (D at least 2 above L1); (a) must have acted on a good share.
    MUTANT: ma6_greedy (today's greedy only: the (a) branch never taken)."""
    model = _model(monkeypatch, approach=1)
    rng = random.Random(2215)
    unit = _approacher(model, (1, 1), (3, 3))
    status = unit.status
    acted_boards = 0
    for board in range(500):
        while True:
            burning, smoky, box = _random_box_fire(rng, model)
            v = _random_cell(rng, model, lambda c: _is_clean(model, c, burning, smoky), box=box)
            if v is None:
                continue
            field = _clean_field(model, v, burning, smoky)
            if not _gesc(model, field):
                continue
            cands = [c for c, d in field.items() if 1 <= d <= 24]
            detour = [c for c in cands if field[c] - abs(c[0] - v[0]) - abs(c[1] - v[1]) >= 2]
            pool = detour if detour and rng.random() < 0.85 else cands
            if pool:
                break
        s = rng.choice(pool)
        _lay(model, burning, smoky)
        _reset_approacher(model, unit, s, v, status)
        d0 = field[s]
        seen = {s}
        acted = False
        for k in range(1, d0 + 1):
            _advance(unit)
            c = _cell(unit)
            assert field.get(c) == d0 - k and _is_clean(model, c, burning, smoky), (board, s, v, k, c)
            assert c not in seen, (board, k, c)
            seen.add(c)
            acted |= unit._last_move_tier == TIER_A
        assert _cell(unit) == v
        acted_boards += acted
    assert acted_boards >= 100, acted_boards


def test_ma7_the_field_is_recomputed_every_step(monkeypatch):
    """T-Ma7. Recomputed, not cached: after one (a) step around the right end of the wall, the wall is extended so
    that the left way round becomes the shortest; the next step follows the NEW board (today's step, now on its
    shortest path), not the field of the first step.
    MUTANT: ma7_cache (the clean field cached at the first call for the bound victim's cell)."""
    model = _model(monkeypatch, approach=1)
    unit = _approacher(model, (26, 23), BARRIER_VICTIM)
    burn(model, WALL)
    _advance(unit)
    assert _cell(unit) == (27, 23) and unit._last_move_tier == TIER_A
    burn(model, [(x, 25) for x in range(36, 46)])
    burning, smoky = _board(model)
    field = _clean_field(model, BARRIER_VICTIM, burning, smoky)
    assert field[(26, 23)] == field[(27, 23)] - 1 < field[(28, 23)]
    _advance(unit)
    assert _cell(unit) == (26, 23)


@pytest.mark.parametrize("guard", (0, 1), ids=("guard0", "guard1"))
def test_ma8_z_rb_the_raise_is_todays_predicate_and_never_on_an_a_step(monkeypatch, guard):
    """T-Ma8 (Z-RB). 500 random boards, a third of them with the victim inside a closed burning ring; up to six
    approach advances each with (a) on, while the unit stands on a clean cell (the approach branch): route_blocked
    is raised exactly when today's predicate says so (no fire-free route from the unit's cell to the victim) - and
    never on an (a) step, where a fire-free route necessarily exists. With the guard on (guard1) the same holds for
    every admitted step and every veto (a vetoed decision is today's _move_toward, which raises on today's
    predicate; Part 1d 1d.2.5 "route_blocked").
    MUTANT: ma8_raise (with (a) on and no fire-free route, the unit holds instead of raising)."""
    model = _model(monkeypatch, approach=1, guard=guard)
    rng = random.Random(2225)
    unit = _approacher(model, (1, 1), (3, 3))
    status = unit.status
    raises: list = []
    _spy(monkeypatch, "_mark_route_blocked", raises, through=False)
    n_raise = n_acted = 0
    for board in range(500):
        while True:
            burning, smoky, box = _random_box_fire(rng, model)
            enclose = rng.random() < 0.35
            inner = (box[0] + 5, box[1] - 5, box[2] + 5, box[3] - 5)
            v = _random_cell(rng, model, lambda c: c not in burning, box=inner if enclose else box)
            if v is None:
                continue
            if enclose:
                burning |= _square(v, rng.randint(2, 4))
                s = _random_cell(rng, model, lambda c: c != v and _is_clean(model, c, burning, smoky), box=box)
            else:                                       # favour starts behind a barrier, where (a) can act
                field = _clean_field(model, v, burning, smoky)
                detour = [c for c, d in field.items() if d - abs(c[0] - v[0]) - abs(c[1] - v[1]) >= 2]
                s = (rng.choice(detour) if detour and rng.random() < 0.8 else
                     _random_cell(rng, model, lambda c: c != v and _is_clean(model, c, burning, smoky), box=box))
            if s is not None:
                break
        _lay(model, burning, smoky)
        _reset_approacher(model, unit, s, v, status)
        for _ in range(6):
            c = _cell(unit)
            if c == v or not _is_clean(model, c, burning, smoky):
                break
            del raises[:]
            _advance(unit)
            raised = bool(raises)
            expected = not _fire_free_route(model, c, v, burning)
            assert expected == (not unit._path_exists_avoiding_fire(c, v, burning))
            if unit._last_move_tier == TIER_A:
                n_acted += 1
                assert not raised and not expected, (board, c, v)
            else:
                assert raised == expected, (board, c, v, raised, expected)
            n_raise += raised
    assert n_raise >= 300 and n_acted >= (100 if guard == 0 else 30), (n_raise, n_acted)


# ============================================================================ (b) FF_RETREAT_KEEP_APPROACH

def test_mb1_an_off_route_retreat_takes_the_on_route_clean_cell(monkeypatch):
    """T-Mb1. A fire cell just below an approaching unit: today's retreat takes the first improving neighbour
    (+x), off the route; (b) retreats to (+y), the clean neighbour with the smallest clean distance to her.
    MUTANT: mb1_today (today's retreat: the (b) choice never consulted)."""
    model = _model(monkeypatch, retreat=1)
    unit = _approacher(model, (25, 20), BARRIER_VICTIM)
    burn(model, [(25, 19)])
    burning, smoky = _board(model)
    field = _clean_field(model, BARRIER_VICTIM, burning, smoky)
    assert [field[c] for c in ((26, 20), (24, 20), (25, 21))] == [11, 11, 9]
    _advance(unit)
    assert _cell(unit) == (25, 21) and unit._last_move_tier == TIER_B

    _set(monkeypatch, FF_RETREAT_KEEP_APPROACH=0)                     # today's retreat on the same board: (+x)
    model0 = _model(monkeypatch)
    unit0 = _approacher(model0, (25, 20), BARRIER_VICTIM)
    burn(model0, [(25, 19)])
    _advance(unit0)
    assert _cell(unit0) == (26, 20) and unit0.movement_reason["fine_category"] == "survival_retreat"


def test_mb2_an_on_route_retreat_is_todays_survival_move_verbatim(monkeypatch):
    """T-Mb2. Today's retreat cell is already on the route: (b) does not act, and _survival_move runs verbatim -
    the same cell, the same _idle_retreat_* writes, the same record and tier as with the switch at 0.
    MUTANT: mb2_always ((b) used even when today's cell is on the route)."""
    calls: list = []
    _spy(monkeypatch, "_survival_move", calls)
    outcomes = {}
    for retreat in (1, 0):
        model = _model(monkeypatch, retreat=retreat)
        unit = _approacher(model, (25, 20), (35, 20))
        burn(model, [(24, 20)])
        del calls[:]
        _advance(unit)
        assert [c[0] for c in calls] == ["_survival_move"]
        outcomes[retreat] = _outcome(unit)
    assert outcomes[1] == outcomes[0]
    assert outcomes[1][0] == (26, 20) and outcomes[1][4] == "survival_retreat"
    assert outcomes[1][6] == {"_idle_retreat_origin": (25, 20), "_idle_retreat_steps": 1,
                              "_idle_retreat_stalled": False, "_idle_retreat_last_cell": (25, 20)}


_MB3_CASES = {
    # every non-burning neighbour is smoky: no clean neighbour
    "no_clean_neighbour": dict(burning=((25, 19),), smoky=((26, 20), (24, 20), (25, 21))),
    # the unit sits in a smoke-walled pocket: its clean neighbours are outside the victim's clean region
    "no_clean_route": dict(burning=((25, 19),), smoky=tuple(sorted(_square((25, 20), 3)))),
    # unit and victim inside one smoke-walled region: a clean route exists, G-ESC is false
    "gesc_false": dict(burning=((25, 19),), smoky=tuple(sorted(_square((25, 25), 12)))),
}


@pytest.mark.parametrize("case", sorted(_MB3_CASES))
def test_mb3_without_a_clean_on_route_cell_todays_retreat_runs(monkeypatch, case):
    """T-Mb3. No clean neighbour, no clean route, or G-ESC false: (b) does not act and today's survival code runs
    verbatim (spy; the outcome equals the switch-0 twin's). In every case today's cell, (+x), differs from the
    cell a (b) that acted would take, (+y).
    MUTANTS: mb3_unclean (unclean cells admitted: the on-route set over non-burning cells) - kills
    no_clean_neighbour and no_clean_route; mb3_gesc (G-ESC removed from (b)) - kills gesc_false."""
    spec = _MB3_CASES[case]
    calls: list = []
    _spy(monkeypatch, "_survival_move", calls)
    outcomes, choice = {}, None
    for retreat in (1, 0):
        model = _model(monkeypatch, retreat=retreat)
        unit = _approacher(model, (25, 20), BARRIER_VICTIM)
        _lay(model, spec["burning"], spec["smoky"])
        if retreat:
            choice = unit._retreat_on_route_choice()                    # pure: read before the advance
        del calls[:]
        _advance(unit)
        assert [c[0] for c in calls] == ["_survival_move"]
        outcomes[retreat] = _outcome(unit)
    assert outcomes[1] == outcomes[0]
    assert outcomes[1][0] == (26, 20)
    assert choice is None


@pytest.mark.parametrize("guard", (0, 1), ids=("guard0", "guard1"))
@pytest.mark.parametrize("case", ("on_her_cell", "next_to_her"))
def test_mb4_an_unclean_victim_cell_is_never_entered_nor_a_pickup_made(monkeypatch, case, guard):
    """T-Mb4 (ruling V-4): a victim on an UNCLEAN, non-burning cell is never picked up and her cell is never entered
    by a fix, with (a) and (b) both on - unguarded (guard0) and guarded (guard1). on_her_cell: a unit standing on
    her fire-adjacent cell retreats (survival runs first) and does not pick her up. next_to_her: a unit beside her
    smoky cell hovers on clean cells for six advances and never steps onto hers.
    MUTANTS: mb4_pickup (a unit on its victim's unclean, non-burning cell skips the retreat and picks her up) -
    kills on_her_cell; mb4_exempt (the victim's cell exempt from the clean test, so the field ends on it) - kills
    next_to_her."""
    model = _model(monkeypatch, approach=1, retreat=1, guard=guard)
    her = BARRIER_VICTIM
    if case == "on_her_cell":
        place_units(model, {FF_A: her})
        place_victims(model, {V0: her})
        with redirect_stdout(io.StringIO()):
            assert assign(model, V0, FF_A)
        unit = ff(model, FF_A)
        burn(model, [(25, 31)])
        steps = 1
    else:
        unit = _approacher(model, (25, 29), her)
        smoke(model, [her])
        steps = 6
    for _ in range(steps):
        _advance(unit)
        assert unit.exiting is False and _cell(unit) != her
        assert unit.target_pos == her and unit.rescued_victim is victim(model, V0)


def test_mb5_a_b_step_relabels_and_records_survival_retreat_on_route(monkeypatch):
    """T-Mb5. A (b) step applies the relabel tail (route_blocked -> assigned), records the movement reason
    "survival_retreat_on_route", sets tier 10 and risk 0, and raises nothing.
    MUTANT: mb5_both (the relabel and the record both removed)."""
    model = _model(monkeypatch, retreat=1)
    unit = _approacher(model, (25, 20), BARRIER_VICTIM, status="route_blocked")
    burn(model, [(25, 19)])
    raises: list = []
    _spy(monkeypatch, "_mark_route_blocked", raises)
    _advance(unit)
    assert _cell(unit) == (25, 21)
    assert unit.status == "assigned" and raises == []
    assert unit.movement_reason["fine_category"] == "survival_retreat_on_route"
    assert (unit._last_move_tier, unit._last_move_risk) == (TIER_B, 0)
    log = [e for e in model._movement_transition_log if e["target_id"] == FF_A]
    assert log and log[-1]["fine_category"] == "survival_retreat_on_route"


def test_mb6_hidden_state_a_today_retreat_after_b_steps_reads_the_stored_state(monkeypatch):
    """T-Mb6 (22.3.5). A (b) step writes no _idle_retreat_* state; a later TODAY-path retreat then equals
    _survival_move run on the same stored state (a twin unit on a fresh model).
    MUTANT: mb6_write ((b) writes _idle_retreat_last_cell)."""
    stored = {"_idle_retreat_origin": (24, 21), "_idle_retreat_steps": 2, "_idle_retreat_stalled": False,
              "_idle_retreat_last_cell": (24, 20)}
    model = _model(monkeypatch, retreat=1)
    unit = _approacher(model, (25, 20), BARRIER_VICTIM)
    for name, value in stored.items():
        setattr(unit, name, value)
    burn(model, [(25, 19)])
    _advance(unit)
    assert _cell(unit) == (25, 21) and unit._last_move_tier == TIER_B
    assert _retreat_state(unit) == stored

    # now today's retreat cell IS on the route: today's code runs on the stored state
    _lay(model, [(24, 21)])
    model.grid.move_agent(victim(model, V0), (35, 21))
    _advance(unit)
    assert unit.movement_reason["fine_category"] == "survival_retreat"      # today's path (it writes no tier)

    twin_model = _model(monkeypatch, retreat=0)
    twin = _approacher(twin_model, (25, 21), (35, 21))
    for name, value in stored.items():
        setattr(twin, name, value)
    burn(twin_model, [(24, 21)])
    with redirect_stdout(io.StringIO()):
        twin._survival_move()
    assert (_cell(unit), _retreat_state(unit)) == (_cell(twin), _retreat_state(twin))
    assert _cell(twin) == (26, 21)


def test_mb6_survival_choice_is_survival_moves_destination(monkeypatch):
    """T-Mb6 (the shadow). Over 400 random states - fire and smoke near the unit, a random stored retreat state
    (origin, steps, stalled, last cell), idle or assigned - the pure _survival_choice equals the cell
    _survival_move actually moves to (None = it does not move).
    MUTANT: mb6_replica (the replica ignores the stored last cell)."""
    model = _model(monkeypatch)
    place_units(model, {FF_A: (25, 25)})
    place_victims(model, {V0: (40, 40)})
    unit = ff(model, FF_A)
    rng = random.Random(2235)
    moved = 0
    for sample in range(400):
        burning = {(25 + rng.randint(-4, 4), 25 + rng.randint(-4, 4)) for _ in range(rng.randint(1, 7))}
        if rng.random() < 0.8:                                   # the unit's own cell burns in ~1 sample of 5
            burning.discard((25, 25))
        smoky = {(25 + rng.randint(-3, 3), 25 + rng.randint(-3, 3)) for _ in range(rng.randint(0, 4))} - burning
        _lay(model, burning, smoky)
        model.grid.move_agent(unit, (25, 25))
        unit.target_pos = (40, 40) if rng.random() < 0.5 else None
        unit._idle_retreat_origin = (None if rng.random() < 0.3 else
                                     (25 + rng.randint(-7, 7), 25 + rng.randint(-7, 7)))
        unit._idle_retreat_steps = rng.randint(0, 7)
        unit._idle_retreat_stalled = rng.random() < 0.3
        unit._idle_retreat_last_cell = rng.choice([None] + _nbrs(model, (25, 25)))
        choice = unit._survival_choice()
        with redirect_stdout(io.StringIO()):
            unit._survival_move()
        after = _cell(unit)
        assert after == (choice if choice is not None else (25, 25)), (sample, choice, after)
        moved += after != (25, 25)
    assert moved >= 150, moved


# ============================================================================ ALL

@pytest.mark.parametrize("guard", (0, 1), ids=("guard0", "guard1"))
def test_tsafem_property_no_fix_enters_fire_and_a_b_land_clean_in_a_gesc_region(monkeypatch, guard):
    """T-SAFE-M. 300 random boards (fenced corner boxes with extra smoke), both fixes on, unguarded (guard0) and
    guarded (guard1): an approaching unit from a clean cell behind a barrier (up to four advances: (a), and (b)
    after any unclean step) and one from an unclean non-burning cell (three starts: (b), one advance each). No
    fix-acted step lands on a burning cell, and every (a) and (b) step lands on a CLEAN cell inside the victim's clean
    region, which has a clean way out (G-ESC). Each fix must act on a good share of the boards. (The urgency round's
    carrier start, fix (c), is not carried.)
    MUTANT: safe_clean (the clean filter dropped: CLEAN = in bounds and not burning)."""
    model = _model(monkeypatch, approach=1, retreat=1, guard=guard)
    unit = _approacher(model, (1, 1), (3, 3))
    status = unit.status
    acted: list = []
    original = agents.Firefighter._fix_move

    def spy(self, cell, tier):
        acted.append((self.unit_id, tuple(cell), tier))
        return original(self, cell, tier)

    monkeypatch.setattr(agents.Firefighter, "_fix_move", spy)
    rng = random.Random(2265)
    counts = {TIER_A: 0, TIER_B: 0}
    for board in range(300):
        burning, smoky, box = _random_box_fire(rng, model)
        smoky |= {(rng.randint(box[0], box[1]), rng.randint(box[2], box[3])) for _ in range(rng.randint(2, 8))}
        smoky -= burning
        v = _random_cell(rng, model, lambda c: c not in burning, box=box)
        field = _clean_field(model, v, burning, smoky)
        detour = [c for c, d in field.items() if d - abs(c[0] - v[0]) - abs(c[1] - v[1]) >= 2]
        clean_s = (rng.choice(detour) if detour and rng.random() < 0.8 else
                   _random_cell(rng, model, lambda c: c != v and _is_clean(model, c, burning, smoky), box=box))
        unclean = [_random_cell(rng, model, lambda c: c != v and c not in burning
                                and not _is_clean(model, c, burning, smoky), box=box) for _ in range(3)]
        _lay(model, burning, smoky)
        for start, steps in [(clean_s, 4)] + [(u, 1) for u in unclean]:
            if start is None:
                continue
            _reset_approacher(model, unit, start, v, status)
            for _ in range(steps):
                del acted[:]
                _advance(unit)
                for _uid, cell, tier in acted:
                    assert cell not in burning, (board, start, cell, tier)
                    assert tier in (TIER_A, TIER_B)
                    assert _is_clean(model, cell, burning, smoky) and cell in field and _gesc(model, field), (
                        board, start, cell, tier)
                    counts[tier] += 1
                if _cell(unit) == v:
                    break
    floor = {0: (80, 40), 1: (25, 20)}[guard]
    assert counts[TIER_A] >= floor[0] and counts[TIER_B] >= floor[1], counts


ON_VALUES = [1, True, 1.0, "1", " 1 "]
_MISSING = object()
OFF_VALUES = [0, 2, 0.5, "2.0", "on", "", None, _MISSING]
OFF_IDS = ["0", "2", "0.5", "str2.0", "on", "empty", "None", "missing"]
ACCESSORS = {
    "FF_APPROACH_PATH": "ff_approach_path",
    "FF_RETREAT_KEEP_APPROACH": "ff_retreat_keep_approach",
}


def _put(monkeypatch, name, value):
    if value is _MISSING:
        monkeypatch.delattr(cfv, name, raising=False)
    else:
        monkeypatch.setattr(cfv, name, value, raising=False)


@pytest.mark.parametrize("name", sorted(ACCESSORS))
@pytest.mark.parametrize("value", ON_VALUES, ids=["1", "True", "1.0", "str1", "str_1_"])
def test_tswm_on_only_on_an_exact_one(monkeypatch, name, value):
    """T-SW-M (the ON half of the exact-1 table): each fix accessor is True for what denotes the integer 1.
    MUTANTS: sw_strict_a (FF_APPROACH_PATH compared with 1 without the exact-integer parsing: "1" and " 1 " off);
    sw_strict_b (the same for FF_RETREAT_KEEP_APPROACH, listed on its two cases [str1-FF_RETREAT_KEEP_APPROACH] and
    [str_1_-FF_RETREAT_KEEP_APPROACH])."""
    _put(monkeypatch, name, value)
    assert getattr(agents, ACCESSORS[name])() is True


def _off_table(monkeypatch, name, value):
    _put(monkeypatch, name, value)
    assert getattr(agents, ACCESSORS[name])() is False


@pytest.mark.parametrize("value", OFF_VALUES, ids=OFF_IDS)
def test_tswm_off_approach_path(monkeypatch, value):
    """T-SW-M. FF_APPROACH_PATH is OFF for everything but an exact 1, missing included.
    MUTANT: sw_truthy_a (the accessor reads truthiness instead of an exact 1)."""
    _off_table(monkeypatch, "FF_APPROACH_PATH", value)


@pytest.mark.parametrize("value", OFF_VALUES, ids=OFF_IDS)
def test_tswm_off_retreat_keep_approach(monkeypatch, value):
    """T-SW-M. FF_RETREAT_KEEP_APPROACH is OFF for everything but an exact 1, missing included.
    MUTANT: sw_truthy_b (truthiness instead of an exact 1)."""
    _off_table(monkeypatch, "FF_RETREAT_KEEP_APPROACH", value)


def test_tswm_read_at_call_time_and_shipped_zero(monkeypatch):
    """T-SW-M. The fix switches ship 0, and each accessor reads the cfv module at CALL time (no import-time copy).
    MUTANTS: sw_import_a (FF_APPROACH_PATH read once at import time); sw_shipped_a (FF_APPROACH_PATH shipped 1);
    sw_import_b, sw_shipped_b (the same two for FF_RETREAT_KEEP_APPROACH)."""
    for name in ACCESSORS:
        assert getattr(cfv, name) == 0
    for name, accessor in ACCESSORS.items():
        for value, expected in ((0, False), (1, True), (0, False), (" 1 ", True), (_MISSING, False)):
            _put(monkeypatch, name, value)
            assert getattr(agents, accessor)() is expected, (name, value)


_NEW_METHODS = ("_approach_path_choice", "_retreat_on_route_choice", "_fix_move", "_greedy_choice",
                "_survival_choice", "_one_step_retreat_choice", "_victim_clean_field", "_board_sets",
                "_clean_predicate", "_relabel_if_route_blocked", "_stranding_guard_verdict")
_NEW_FUNCTIONS = ("clean_distance_field", "region_has_exit", "approach_choice", "retreat_choice", "stranding_guard",
                  "unclean_cells", "t_star", "safe_route_hops")


@pytest.mark.parametrize("off", ("zero", "missing"))
def test_tswm_off_never_enters_new_code(monkeypatch, off):
    """T-SW-M. With the two fix switches at 0 (or missing) and the guard at its shipped 1, on boards where each fix
    WOULD act - (a) on the barrier, (b) beside a fire cell - no new method (but _guarded, which is called with no
    step and returns it at once), no movement_paths function and fire_board_sets is ever entered (each raises if
    called), and each unit takes today's step.
    MUTANTS: sw_enter_a, sw_enter_b (the fix's pure choice evaluated while its switch is off)."""

    def boom(*args, **kwargs):
        raise AssertionError("new movement code entered with its switch off")

    def setup(**kwargs):
        model = _model(monkeypatch, guard=1, **kwargs)
        for name in ACCESSORS:
            _put(monkeypatch, name, 0 if off == "zero" else _MISSING)
        return model

    for name in _NEW_METHODS:
        monkeypatch.setattr(agents.Firefighter, name, boom)
    for name in _NEW_FUNCTIONS:
        monkeypatch.setattr(movement_paths, name, boom)
    monkeypatch.setattr(agents, "fire_board_sets", boom)

    model = setup()
    unit = _approacher(model, (26, 23), BARRIER_VICTIM)
    burn(model, WALL)
    _advance(unit)
    assert _cell(unit) == (25, 23)

    model = setup()
    unit = _approacher(model, (25, 20), BARRIER_VICTIM)
    burn(model, [(25, 19)])
    _advance(unit)
    assert _cell(unit) == (26, 20)


# ---------------------------------------------------------------------------- T-ID-M

ID_STEPS = 20
# The digest of _identity_run on the BASE code (a20a2ef5: no movement fix, no switch; behaviour = 27744a28), recorded
# by running this very function in a copy of the worktree whose agents.py, wildfire_model.py and
# common_fixed_variables.py are `git show a20a2ef5:<file>` (what outputs/_mvg_mutants_mv.py --golden does), under
# PYTHONHASHSEED 0 and 12345 (equal). It equals the urgency round's ID_GOLDEN_BASE at 27744a28 (the two bases differ
# only in two outputs/ documents).
ID_GOLDEN_BASE = "cdfe27599df24b7176203ed06db41219933273ebc6a6d52120fb283297e47e94"


def _identity_run(monkeypatch, setting: str) -> str:
    """A short pinned REAL run: scenario A's team, every victim detected at step 0 (so the searchers idle), victim_2
    moved behind an 11-cell fire wall and bound to ff_unit_0 - the barrier on which today's mover 2-cycles and fix
    (a) would act at the third step. `setting` "absent" deletes the round's three switches from cfv (the guard then
    reads ON); "zero" sets all three 0; "shipped" sets the fixes 0 and the guard 1, as cfv ships them.
    Returns one sha256 over stdout, the command audit, the rescue events, the movement transitions and every
    unit's (cell, status, tier) after each of ID_STEPS model steps. Base-safe: no name new in this round.
    Each run starts from the import-time configuration (the caller's monkeypatch.undo() also undoes the autouse
    fixture's restore, and the full suite's other files leave scenario settings behind)."""
    restore_config(monkeypatch)
    for name in SWITCH_NAMES:
        if setting == "absent":
            monkeypatch.delattr(cfv, name, raising=False)
        else:
            value = 1 if (setting == "shipped" and name == "FF_FIX_STRANDING_GUARD") else 0
            monkeypatch.setattr(cfv, name, value, raising=False)
    out = io.StringIO()
    with redirect_stdout(out):
        model = pinned_model(monkeypatch)
        for vid, state in model.managed_victims.items():
            state.confirmed = True
            state.status = "confirmed"
            model.victim_marker_agents[vid].status = "confirmed"
        her = model.victim_marker_agents[V2]
        model.grid.move_agent(her, (40, 20))
        her.spawn_cell = her.leash_anchor = (40, 20)
        model.grid.move_agent(model.firefighter_marker_agents[FF_A], (40, 8))
        burn(model, [(x, 14) for x in range(35, 46)])
        assert assign(model, V2, FF_A)
        rows = []
        for _ in range(ID_STEPS):
            model.step()
            rows.append(tuple((fid, None if m.pos is None else (int(m.pos[0]), int(m.pos[1])), str(m.status),
                               int(m._last_move_tier)) for fid, m in model.firefighter_marker_agents.items()))
    audit = [(e["action"], e["victim_id"], e["firefighter_id"], e["success"])
             for e in model._physical_rescue_command_audit]
    events = [(e.get("step"), e.get("event_type"), e.get("victim_id"), e.get("firefighter_id"), e.get("reason"))
              for e in model._rescue_event_log]
    moves = [(e["step"], e["target_id"], e["fine_category"], e["transition_key"])
             for e in getattr(model, "_movement_transition_log", []) or []]
    blob = repr((out.getvalue(), audit, events, moves, rows))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def test_tidm_switches_absent_zero_and_shipped_are_identical_and_equal_the_base(monkeypatch):
    """T-ID-M (and Part 1d T-G6's real-run identity). The pinned real run with the round's three switches ABSENT,
    all at 0, and as SHIPPED (fixes 0, guard 1) gives one identical digest of stdout and the logs, and it equals the
    base code's (a20a2ef5) digest: with both fixes off, neither the fixes nor the guard change anything.
    MUTANT: id_a_off (the (a) branch taken when its switch is off)."""
    absent = _identity_run(monkeypatch, "absent")
    monkeypatch.undo()
    zero = _identity_run(monkeypatch, "zero")
    monkeypatch.undo()
    shipped = _identity_run(monkeypatch, "shipped")
    assert absent == zero == shipped
    assert zero == ID_GOLDEN_BASE


# ---------------------------------------------------------------------------- T-NT

BASE_COMMIT = "a20a2ef5"

# 22.6.1's NOT-TOUCHED list (both parts of the urgency round), plus the movement layer's own untouched kernels, re-based
# to this branch: wildfire_model.py is not touched at all here (no U1, no C-4, no C-5), so it is pinned WHOLE ("*")
# besides its named functions. "Class.method", "function", "Class" (the whole class) or "*" (the whole file).
TNT_LIST = {
    "agents.py": (
        "Fire", "Smoke", "Wind", "UAV", "Victim",                                   # the fire, victims, UAVs
        "exit_leg_first_step", "EXIT_LEG_SEARCH_ORDER", "EXIT_LEG_PATH_TIER", "EXIT_LEG_HOLD_TIER",  # MODE 2 kernel
        "ff_exit_leg_mode", "ff_exit_leg_hold", "ff_exit_leg_served",
        "Firefighter._move_toward", "Firefighter._path_exists_avoiding_fire", "Firefighter._exit_leg_step",
        "Firefighter._exit_leg_enclosed", "Firefighter._exit_leg_hold",
        "Firefighter._survival_move", "Firefighter._retreat_candidates", "Firefighter._pick_improving_retreat",
        "Firefighter._assigned_one_step_retreat", "Firefighter._revalidate_idle_retreat_stall",
        "Firefighter._needs_immediate_survival_retreat", "Firefighter._idle_needs_survival_move",
        "Firefighter._cell_meets_required_idle_safety", "Firefighter._cell_is_ideal_idle_standoff",
        "Firefighter._reset_idle_retreat_state", "Firefighter._mark_route_blocked",
        "Firefighter._refresh_target_from_victim", "Firefighter._on_grid_boundary",
        "Firefighter._firefight_prepare", "Firefighter._firefight_mission_resolved",
        "Firefighter._firefight_exit_guard", "Firefighter._firefight_plan", "Firefighter._firefight_holdable_check",
        "Firefighter._firefight_approach_step", "Firefighter._firefight_fire_at", "Firefighter._firefight_execute",
        "Firefighter._firefight_after_retreat", "Firefighter._firefight_log_row",
    ),
    "wildfire_model.py": (
        "WildFireModel._on_firefighter_route_blocked", "WildFireModel._revalidate_route_blocked_firefighters",
        "WildFireModel._route_block_stale_clear_mode", "WildFireModel._clear_stale_route_blocks",
        "WildFireModel._update_unreachable_victims", "WildFireModel._exit_leg_custody",
        "WildFireModel._exit_leg_held_cell", "WildFireModel._release_other_claimants",
        "WildFireModel._handle_rescue_incident", "WildFireModel._dispatch_firefighter_to_victim",
        "WildFireModel._try_replacement_after_firefighter_casualty", "WildFireModel.apply_physical_rescue_command",
        "WildFireModel._firefighter_available_for_dispatch", "WildFireModel._victim_needs_rescue",
        "WildFireModel._drain_rescue_incidents", "WildFireModel._process_rescue_incidents",
        "WildFireModel._process_pending_agent_removals", "WildFireModel.step",
        "WildFireModel._check_fire_casualties", "WildFireModel._find_active_firefighter_for_victim",
        "WildFireModel._try_dispatch_unresolved_confirmed_victims", "*",
    ),
    "src_extension/planning/rescue_planner.py": ("select_rescue_assignment", "*"),
    "src_extension/execution/rescue_executor.py": ("*",),
    "src_extension/planning/fire_arrival_estimate.py": ("*",),
    "src_extension/execution/uav_executor.py": ("*",),                          # the searchers' executor
    "src_extension/planning/searcher_targeting.py": ("*",),
}
TNT_PINS: dict[str, str] = {   # _base_pins(`git show a20a2ef5`); outputs/_mvg_mutants_mv.py --pins prints them
    'agents.py::EXIT_LEG_HOLD_TIER': '7dd5975e613771ac9670fc5385982d235e25a4a8e3b93a3fd2aa0e6bdbf8771d',
    'agents.py::EXIT_LEG_PATH_TIER': 'a5cac5b664fca3887a6ab26852bf6cfa5a89139ccec7672647605076143fb854',
    'agents.py::EXIT_LEG_SEARCH_ORDER': 'b46b8859f7874b6de15c02ca483fa5f222125ee7eb5dd95fdbc994df1b605277',
    'agents.py::Fire': 'f248ce9908aa3584920a33c28ea4b0c380e50cde9edef68f2f9964a15b268c9a',
    'agents.py::Firefighter._assigned_one_step_retreat': '1cb15ed722ddc889e4acfd59ddffd6321663a0b05757f5fbfe1a5af8a03e3b0a',
    'agents.py::Firefighter._cell_is_ideal_idle_standoff': 'cb40fff8021db401cd9e9b7adace369436bd04626658f5626ab87eb19cf6bb71',
    'agents.py::Firefighter._cell_meets_required_idle_safety': 'ffa9a834b435e5e73a5aa2b4e99fd308569dde7c5d6d66a04d4bd606d8bc96df',
    'agents.py::Firefighter._exit_leg_enclosed': '70e81cca46ea6519bd1bcec3a8384bd71fe5be851cd0149840b2ce403d994071',
    'agents.py::Firefighter._exit_leg_hold': '225d6a78bbe2717783b2fc34703636e0f93992de582a68a65c3a5e50dd005a8b',
    'agents.py::Firefighter._exit_leg_step': 'd96d760f8093abbd0f5de5ac0ea5720fb2ad3941e52057be7edeca81c80dc680',
    'agents.py::Firefighter._firefight_after_retreat': 'bbe86dce575c38e9a7a14b04c66b6b7a7a9684498d78696bcb9bcfa1dffffe5d',
    'agents.py::Firefighter._firefight_approach_step': '2a1af4d55926cde2d5d6e988b40c8c38b86ef7ea9926430eca22e1906110a982',
    'agents.py::Firefighter._firefight_execute': 'd89ded65e875faa6ad48f2ec13324c583125bc9aa04a1d45f0af00ba3400f9c5',
    'agents.py::Firefighter._firefight_exit_guard': '34a060a38b757fcd68206ee9e2df3dea7524c15dfcba580909180719167823b5',
    'agents.py::Firefighter._firefight_fire_at': '5f28a0d036643dd21a363f616277f16dfd08661ffb8f66e0b8d1b68b9a97cc64',
    'agents.py::Firefighter._firefight_holdable_check': 'bd71b005cacfe99e39fa234dd6eaa6f1cc88d722bfade03ccd600683a31feb63',
    'agents.py::Firefighter._firefight_log_row': 'f53f663bcb4495a28402cce3e60b221cab2e73db145313f5988a91947ba7dabf',
    'agents.py::Firefighter._firefight_mission_resolved': 'e648b8947e2324efa4781fbb9e27d431014f8476b5d2f8039ed828eabc7768ed',
    'agents.py::Firefighter._firefight_plan': '06f74a188bc42fea15d083922e69d8ef655928ad0ea49f05984f2e2be87eb403',
    'agents.py::Firefighter._firefight_prepare': '1daa6267e3fb5966e933d1a9c5ae861323761aec245eb405332c030a1d8ed05c',
    'agents.py::Firefighter._idle_needs_survival_move': '01f0206a4dd1d8fc96b2a3202f214a124e5b7bb3ae7b5371b906fc468c3330eb',
    'agents.py::Firefighter._mark_route_blocked': '35f21e3d279445310bc63a023bb77f34fa6bc0b5b0349b8f16a21be8b9023e96',
    'agents.py::Firefighter._move_toward': '94c3d864b5cc4306cc1d143fab457830544bdd21d1cad4b76a31974d95fd5d9d',
    'agents.py::Firefighter._needs_immediate_survival_retreat': '526cdd2f6e013bccdc27a08231fffd10f4c5b345ef1dd8dc4b39211bf47916b7',
    'agents.py::Firefighter._on_grid_boundary': '8d8591b014c43621314e2a29157cb6b0add43ab96c68124d0b9a2f90b349c84a',
    'agents.py::Firefighter._path_exists_avoiding_fire': 'd8f73b5dbac724bda9660f8a94621f40dc983e4d6acd44d4af302fff1bbfc13a',
    'agents.py::Firefighter._pick_improving_retreat': '2d88b2adb79cd30b25f0a229cc841cecc41d59f3d758dcd608d9de0fa7bbc129',
    'agents.py::Firefighter._refresh_target_from_victim': '5072d715da50d9086d36053909f44dda5dce19699b1a8a136106c98b94f8681d',
    'agents.py::Firefighter._reset_idle_retreat_state': '106e26832b08f72fe6c54318eef920528a7acbd0b413473a9fc12401fbb4bf79',
    'agents.py::Firefighter._retreat_candidates': '2499c5e1d277de6d25ac0cbded4f93cfa2e6604dee9b16e3e6f060096831bb38',
    'agents.py::Firefighter._revalidate_idle_retreat_stall': '4f3b76fe2e0b53426f533bae747636911a0d1a176fdd48873c8508e06a614109',
    'agents.py::Firefighter._survival_move': 'e51e7f6c70edb029a076da074b760b1b32bc30d32089d0c8aefc67415752aef4',
    'agents.py::Smoke': 'c72ff2312dd5f8cf241ceb397ef307d7a1085bba367f61daa50de174284607d9',
    'agents.py::UAV': '16b11caed4fc09520ddbf4fd2bd2a32abe85aebecac7315afb79b7a038ea5449',
    'agents.py::Victim': 'e6a70057176d6dba2e14180d66c502fe97a91dd3a4e15e517a9e2ed425fed8c9',
    'agents.py::Wind': '53d213a12a2d793c511a6987bd4df757cf11f7b23a9c625c8de0df5af78abfaf',
    'agents.py::exit_leg_first_step': 'ae1f3695ee99704f2051d5ee6162096ab0c207a055f0f993837b86a6773d8cea',
    'agents.py::ff_exit_leg_hold': 'efebe4292a761c60bcccb335174b31f8396408bb51fde6328221236305ae337d',
    'agents.py::ff_exit_leg_mode': 'e9f4d1cf1390e5e232a7c0ac0fec5904e7c7ff8699d6b9ed1218290dedb1bc7e',
    'agents.py::ff_exit_leg_served': 'b95e76d80ce3f6ba5d43eb8aa07da4bb98cc1ee05ad3d02c206cec5df8117dc4',
    'src_extension/execution/rescue_executor.py::*': 'a3de8966e1bf5bbaa2d6c0288ccb4044c8a21364e99d121966a0fab059908369',
    'src_extension/execution/uav_executor.py::*': 'd67f0bac99f33fefcd50e1339e3aa5c26433a1780418b9faec4cceebf9451449',
    'src_extension/planning/fire_arrival_estimate.py::*': 'cd4da0934f6c4f692f73cea2d95c1c616a7a45d4f3433bb860dd5c29af8b627e',
    'src_extension/planning/rescue_planner.py::*': '948dde24f7fcafd7f917f2a3c0a672ad59de8bdfe0fc714b0e5ae3425f804451',
    'src_extension/planning/rescue_planner.py::select_rescue_assignment': 'd661dfa1cb1fb171fbc983e32ec0a35820b0721118ceb97643362d7fe4a07619',
    'src_extension/planning/searcher_targeting.py::*': '88796eb0c6b7e610cb0b13af9ed01fc90ca8d8d96360472635390ee785eccc2b',
    'wildfire_model.py::*': 'ebd5b35a326a6b91c235550d680d5f602ddc77a6f8c44598e971957d5a98f9ca',
    'wildfire_model.py::WildFireModel._check_fire_casualties': '75b2480ed55aff671c5f8edded16cbbae97ec1622ed748d71e7b47f4588eff16',
    'wildfire_model.py::WildFireModel._clear_stale_route_blocks': '5cd911021cbdd535484bbec8a1ea1c0e870d523a4ac0444fac5d99630c5a73a9',
    'wildfire_model.py::WildFireModel._dispatch_firefighter_to_victim': '644dd1a1c505a220c0d18feb8c62415ec2bfc1683b899b53d85c175dccd81e56',
    'wildfire_model.py::WildFireModel._drain_rescue_incidents': 'f906dfa5da1da83d103f7d2d5730da345f287441872daa99316492287d548081',
    'wildfire_model.py::WildFireModel._exit_leg_custody': 'bd7cd62572dd12d37520d6d0fe9d2e7bc52addc34a782f0cda7c2a5c635aac43',
    'wildfire_model.py::WildFireModel._exit_leg_held_cell': '2ce22539f36c1097b131b1930f9110c247135f3f652bca739db0eccda21f883b',
    'wildfire_model.py::WildFireModel._find_active_firefighter_for_victim': '6c9523ca5a062da7add1fb13ae03bf9f97aa7eac3ee80f0bdfa477fad0e7248c',
    'wildfire_model.py::WildFireModel._firefighter_available_for_dispatch': '006e86c18f2972e403744018c130bcafcb1b5104dc0bebd537677f147525f9aa',
    'wildfire_model.py::WildFireModel._handle_rescue_incident': '4864aa30d7871ae9482fef9e7586fe496bcc63d1459f07ceb5d4b68e4e125fc6',
    'wildfire_model.py::WildFireModel._on_firefighter_route_blocked': 'b8f0cd44d0ea82fc05e8e049eda5d8035e4f631f1165e42fe4869e213a336489',
    'wildfire_model.py::WildFireModel._process_pending_agent_removals': '0e0ab58bea4466c8533bdc94f3e9168002ff2dfb859502257a22bde35f5b9cd2',
    'wildfire_model.py::WildFireModel._process_rescue_incidents': '5fe4230f370c6056dde72f35ae6e8ec6c2332f6447350e5bb8c75a2ab3b8f960',
    'wildfire_model.py::WildFireModel._release_other_claimants': '9d710aae2644008d1d70f98820e6b1c7ffc0084c83857d75088128e7a31b94d6',
    'wildfire_model.py::WildFireModel._revalidate_route_blocked_firefighters': '3a6f2048b74195db72089fb5f35364825043f049f74d665350f24c1ff2caa8fb',
    'wildfire_model.py::WildFireModel._route_block_stale_clear_mode': '6231170731d3a02272a2341a36929affb837a8de989da9137089981f13cb406d',
    'wildfire_model.py::WildFireModel._try_dispatch_unresolved_confirmed_victims': 'ae94e3e0bc079ceeaab1f01835607dcc9fa6fadbb313bd162afc8257f1132db4',
    'wildfire_model.py::WildFireModel._try_replacement_after_firefighter_casualty': 'a1f38b091ed6bac26a94727b0398ef03bae6f8b56723495dbd9a3791d04a75b8',
    'wildfire_model.py::WildFireModel._update_unreachable_victims': '5a8366a62cfad0ec737016f066cca8f270ea293c6ea1f2ea58baba4c281da3e9',
    'wildfire_model.py::WildFireModel._victim_needs_rescue': '0b77d3f8df1ea039a4b20e229597ad981110772a3038fc59c79537c39b280805',
    'wildfire_model.py::WildFireModel.apply_physical_rescue_command': '460e72f97f1dccf6a7f828d79147b3284b0bab3a87786e2a38c6e37f4051b533',
    'wildfire_model.py::WildFireModel.step': 'caf0ddc9caa2c35753ba2969a8adc55f3bf9c95d420ce9aeadf9a4eba00d5921',
}


def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n")


def _segments(text: str) -> dict:
    """{qualname: source} of every top-level def / class / single-name assignment and every method, LF-normalised;
    "*" is the whole file."""
    text = _normalise(text)
    lines = text.split("\n")
    out = {"*": text}

    def span(node):
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        return "\n".join(lines[start - 1:node.end_lineno])

    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = span(node)
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out[f"{node.name}.{sub.name}"] = span(sub)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = span(node)
    return out


def _other_statements(text: str) -> list:
    """The source of every top-level statement _segments does not name (imports, annotated or multi-target
    assignments, top-level if / try blocks, expressions), in file order, LF-normalised."""
    text = _normalise(text)
    lines = text.split("\n")
    out = []
    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            continue
        out.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
    return out


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tnt_hashes(read) -> dict:
    """{file::name: sha256} for TNT_LIST. `read(rel)` returns a file's text."""
    out = {}
    for rel, names in TNT_LIST.items():
        segs = _segments(read(rel))
        for name in names:
            assert name in segs, f"{rel}: {name} not found"
            out[f"{rel}::{name}"] = _sha(segs[name])
    return out


def _current_text(rel: str) -> str:
    return (ROOT / rel).read_bytes().decode("utf-8")


def _git_text(rel: str) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE_COMMIT}:{rel}"], capture_output=True,
                              timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.decode("utf-8") if proc.returncode == 0 else None


def test_tnt_the_not_touched_list_hashes_equal_the_base():
    """T-NT (22.6.1, re-based): every function, class and file on the NOT-TOUCHED list - the fire, victims, UAVs and
    searchers; idle movement, the survival and idle retreats, firefighting and its engaged retreat;
    select_rescue_assignment and the executor; the route_blocked handler, the revalidation, the stale clear, the
    escape sweep and the casualty sweep; MODE 2's kernel, _exit_leg_step and _exit_leg_hold; FAE; _move_toward and
    the route test; and the whole of wildfire_model.py - hashes (LF-normalised) equal to the base a20a2ef5. The pins
    are checked against `git show a20a2ef5` whenever git can see the commit.
    MUTANTS: nt_survival (one line changed in _survival_move); nt_release (15.3's T-NT form: one line changed in
    _release_other_claimants)."""
    current = _tnt_hashes(_current_text)
    assert set(current) == set(TNT_PINS)
    changed = sorted(key for key in TNT_PINS if current[key] != TNT_PINS[key])
    assert changed == []
    if _git_text("agents.py") is not None:                 # in a checkout that holds the base commit
        assert _base_pins(_git_text) == {"TNT_PINS": TNT_PINS, "TOUCHED_PINS": TOUCHED_PINS,
                                         "REST_PINS": REST_PINS, "OTHER_PINS": OTHER_PINS}


# The places THIS branch touches differ from the base ONLY by the registered edits. Each edit is (begin marker, end
# marker, base text): the text from `begin` (inclusive) to `end` (exclusive) is the round's insert and is put back as
# `base text`; both markers must occur exactly once in the segment ("*" = the whole file).
TOUCHED_EDITS = {
    "agents.py::Firefighter.advance": (
        ("            # Fix (b), FF_RETREAT_KEEP_APPROACH", "            self._survival_move()\n            if (\n", ""),
        ("                # Fix (a), FF_APPROACH_PATH",
         "                cell = (int(self.pos[0]), int(self.pos[1]))\n                self._record_movement_reason(\n"
         "                    \"moving_to_victim\",",
         "                self._move_toward(self.target_pos)\n"),
    ),
    "common_fixed_variables.py::*": (
        ("# ---- MVG round (outputs/urgency_part1d.txt", "# The ONE battery threshold pair (fix1 item 2)", ""),
    ),
}
# The names this round ADDS to agents.py (Part 1d 1d.8 (2)-(3)); everything else in the file is base. Nothing of U1 or
# fix (c) (dispatch_urgency, ff_carry_replan, CARRY_*_TIER, _carry_replan_*) is among them, so any of those would
# change the "rest" hash.
NEW_NAMES = {
    "agents.py": frozenset({
        "ff_approach_path", "ff_retreat_keep_approach", "ff_fix_stranding_guard", "fire_board_sets",
        "APPROACH_PATH_TIER", "RETREAT_ON_ROUTE_TIER",
        *(f"Firefighter.{name}" for name in (
            "_board_sets", "_clean_predicate", "_greedy_choice", "_one_step_retreat_choice", "_survival_choice",
            "_victim_clean_field", "_approach_path_choice", "_retreat_on_route_choice", "_relabel_if_route_blocked",
            "_fix_move", "_stranding_guard_verdict", "_guarded")),
    }),
}
# The top-level statements this round adds to agents.py outside any def / class / assignment: one import.
NEW_OTHER = {"agents.py": ("from src_extension.planning import movement_paths",)}
# Skipped by the "rest" hash: the whole file, the class that contains the touched method, and the touched method.
TOUCHED_SKIP = frozenset({"*", "Firefighter", "Firefighter.advance"})
TOUCHED_PINS: dict[str, str] = {   # _base_pins(`git show a20a2ef5`); outputs/_mvg_mutants_mv.py --pins prints them
    'agents.py::Firefighter.advance': '1670c8c188e38c21a423fdc75c09f77c63df2a66bc7222edbcd3fc5d4cbc32cc',
    'common_fixed_variables.py::*': '86b7fb7a209f2f8bc7f10a6f220b538ca2e6b31ca84b45d7c0ec6d1ff73c2038',
}
REST_PINS: dict[str, str] = {   # _base_pins(`git show a20a2ef5`); outputs/_mvg_mutants_mv.py --pins prints them
    'agents.py': '0d45ac90f56b93c775d55b06f7495a988552eeb0306ef2df1e0e500c1cd13123',
}
OTHER_PINS: dict[str, str] = {   # _base_pins(`git show a20a2ef5`); outputs/_mvg_mutants_mv.py --pins prints them
    'agents.py': '689a251d5d43a5d32cbbfd5d29da047e993d4b0ac10d6817a94f330b49bd4b6d',
}


def _undo_edits(segment: str, edits) -> str:
    for begin, end, base in edits:
        assert segment.count(begin) == 1 and segment.count(end) == 1, (begin, end)
        i, j = segment.index(begin), segment.index(end)
        assert i < j, (begin, end)
        segment = segment[:i] + base + segment[j:]
    return segment


def _rest_hash(segs: dict, names) -> str:
    """One sha256 over the named segments, name by name (the name set is part of the hash)."""
    return _sha("\n".join(f"{n}:{_sha(segs[n])}" for n in sorted(names)))


def _rest_names(segs: dict, rel: str, *, base: bool) -> list:
    return [n for n in segs if n not in TOUCHED_SKIP and (base or n not in NEW_NAMES[rel])]


def _other_hash(statements: list) -> str:
    return _sha("\n\n".join(statements))


def test_tnt_touched_functions_differ_from_the_base_only_by_the_registered_edits():
    """T-NT (the touched side, re-based to this branch): Firefighter.advance with its two gated fix blocks put back,
    and common_fixed_variables.py with the round's switch block removed, each hash equal to the base; every OTHER
    function, method, class and module constant of agents.py - all but the round's registered new names - is the
    base's, name for name; and agents.py's other top-level statements (imports, top-level blocks) are the base's
    plus the one registered import.
    MUTANTS: nt_advance (one line changed in advance outside the fix blocks); nt_toplevel (an import added at the
    top of agents.py, outside the registered one)."""
    for key, edits in TOUCHED_EDITS.items():
        rel, name = key.split("::")
        segment = _segments(_current_text(rel))[name]
        assert _sha(_undo_edits(segment, edits)) == TOUCHED_PINS[key], key
    for rel in NEW_NAMES:
        text = _current_text(rel)
        segs = _segments(text)
        assert NEW_NAMES[rel] <= set(segs), rel
        assert _rest_hash(segs, _rest_names(segs, rel, base=False)) == REST_PINS[rel], rel
        others = _other_statements(text)
        for added in NEW_OTHER[rel]:
            assert others.count(added) == 1, (rel, added)
            others.remove(added)
        assert _other_hash(others) == OTHER_PINS[rel], rel


def _base_pins(git_text) -> dict:
    """Every pin of this section and of T-NT from the base's text (`git_text(rel)`): used by
    outputs/_mvg_mutants_mv.py --pins to WRITE the pins, and by test_tnt_the_not_touched_list_hashes_equal_the_base
    to check them."""
    tnt = _tnt_hashes(git_text)
    touched = {}
    for key in TOUCHED_EDITS:
        rel, name = key.split("::")
        touched[key] = _sha(_segments(git_text(rel))[name])
    rest, other = {}, {}
    for rel in NEW_NAMES:
        text = git_text(rel)
        segs = _segments(text)
        rest[rel] = _rest_hash(segs, _rest_names(segs, rel, base=True))
        other[rel] = _other_hash(_other_statements(text))
    return {"TNT_PINS": tnt, "TOUCHED_PINS": touched, "REST_PINS": rest, "OTHER_PINS": other}
