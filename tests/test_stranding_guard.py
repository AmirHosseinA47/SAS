"""MVG round, Part 2d: the STRANDING GUARD's tests T-G1..T-G8 (outputs/urgency_part1d.txt 1d.8 (4); the guard SG-T of
1d.2.2, ruling W-1 (a); a veto is today's step, ruling W-2 (a); amendment C1, 1d.13).

THE BUILT GUARD. At a decision where fix (a) or fix (b) would act - its pure choice n differs from today's step -
with the unit's cell u, the bound victim's cell v, the true burning set B, the active-smoke set S and the wind:
    T        = FAE arrival_time(grid.width, grid.height, B, wind, FrontPriorityParams())   (never SEARCHER_FP_*)
    unclean  = burning, smoky, or 4-adjacent to a burning cell
    T*(x)    = min of T over x and its in-grid 4-neighbours
    c_n      = the earliest hop at which v is entered on a time-expanded clean route whose first step is u -> n
               (n at hop 1 iff clean and T*(n) > 1; then x at hop k iff clean and T*(x) > k; u never re-entered)
    ADMIT    iff c_n is finite and c_n + 1 <= T(v)
movement_paths.stranding_guard computes (admit, c_n, T(v)); Firefighter._stranding_guard_verdict feeds it the model's
board, wind and extents; Firefighter._guarded applies it (a veto returns None: today's step runs). The switch
FF_FIX_STRANDING_GUARD ships 1 and is off only on an exact 0; it is read only where a fix would act.

Every test names its MUTANT(S) ("MUTANT: <id>"), kept with the movement mutants in outputs/_mvg_mutants_mv.py; the
MUTANT KEY below states each new mutant's source change. Each listed test FAILS on its mutant and PASSES on the
unmutated source. Expected values come from hand-derived boards (crafted T grids, where the boundary must be exact)
or from the ORACLE in this file - an independent level-by-level time-expanded BFS written from 1d.2.2 - and, for
T-G7, from the frozen reference implementation outputs/_mvg_guard_diag.guard (sha256 70eeba78..., via the corpus
written by outputs/_mvg_make_guard_corpus.py in the urgency checkout).

Base-safe at import: nothing at module level reads a name this round adds, so _fix_corpus (T-G3) also runs against
the urgency round's code, which is how T-G3's golden digest is recorded.

MUTANT KEY (the new mutants; the (a) / (b) and switch mutants of the urgency round are in test_movement_fixes.py):
  g_plus1          stranding_guard admits on c_n <= T(v) (the pickup "+1" dropped)
  g_tstar          stranding_guard tests T(x) itself, not T*(x): the first-hop test and the route's t_star_of read
                   float(t_grid[x]) instead of t_star(t_grid, x, ...)
  hp_t_star_cell   the ported helper t_star ignores the neighbours (returns T at the cell)
  g_ge_k           "> k" read as ">= k" in the ported helper safe_route_hops' entry test (t_star_of(n) > k)
  g_ge_1           the same at n: stranding_guard's first-hop test t_star(t_grid, n, ...) > 1 read as >= 1
  g_first_hop      no forced first hop: the route BFS starts at u (c = hops from u to v), not at n
  g_reenter_u      u re-entered: u is not added to the BFS's blocked set
  g_admit_inf      v never entered admits: stranding_guard's "v not in hops" return is (True, None, T(v))
  g_n_exempt       n's own unclean test dropped (only T*(n) > 1 is tested at n)
  g_victim_exempt  the victim's cell removed from the unclean set
  hp_no_adjacent   the ported helper unclean_cells drops the 4-neighbours of burning cells (EQUIVALENT inside the
                   guard - FAE sets T = 0 on burning cells, so T* of a fire-adjacent cell is 0 and no hop enters it -
                   and killed by T-G4's direct comparison)
  g_nofire_veto    with nothing burning the guard vetoes (an early (False, None, inf) when the burning set is empty)
  g_wind_none      the guard reads no wind: _stranding_guard_verdict passes wind None
  g_wind_none_mp   the same inside movement_paths: stranding_guard calls arrival_time with wind None
  g_xy_swap        stranding_guard calls arrival_time(y_size, x_size, ...)
  g_view_swap      _stranding_guard_verdict passes grid.height as x_size and grid.width as y_size
  g_numpy_identity fire_board_sets reads burning by identity with True (a numpy.bool_ fire is invisible)
  g_fae_params     stranding_guard's default params are front_priority_params() (the SEARCHER_FP_* knobs)
  g_fae_params_view _stranding_guard_verdict passes params=front_priority_params()
  g_veto_acts      a veto still takes the fix's step (_guarded returns the cell whatever the verdict)
  sw_guard_ignored _guarded applies the guard whatever FF_FIX_STRANDING_GUARD says (the switch test removed)
  sw_guard_default ff_fix_stranding_guard reads a MISSING switch as 0 (getattr default 0)
  sw_guard_truthy  ff_fix_stranding_guard reads truthiness: bool(getattr(cfv, "FF_FIX_STRANDING_GUARD", 1))
  sw_guard_exact1  ff_fix_stranding_guard is on only on an exact 1
  sw_guard_import  FF_FIX_STRANDING_GUARD read once at import time
  sw_guard_shipped0 FF_FIX_STRANDING_GUARD shipped 0
  g_switch_first   _guarded reads ff_fix_stranding_guard() before it tests for a missing step
  g_eval_off       the (a) site evaluates the guard on (a)'s pure choice whatever FF_APPROACH_PATH says, the result
                   discarded when the switch is off
  g_eval_off_b     the same at the (b) site: the guard evaluated on (b)'s pure choice whatever
                   FF_RETREAT_KEEP_APPROACH says, the result discarded when the switch is off (added by the Part 2d
                   review fix C-3 with the (b) accessor's switch mirrors sw_strict_b, sw_import_b and sw_shipped_b,
                   which are in test_movement_fixes.py)

Coordinates are (x, y); x indexes the FIRST extent (grid.width, FAE's first argument); neighbour order (+x, -x, +y, -y).
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import math
import os
import random
import subprocess
import types
from collections import deque
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
from src_extension.planning import movement_paths
from src_extension.planning.fire_arrival_estimate import FrontPriorityParams, arrival_time, front_priority_params
from mvg_test_support import (
    FF_A,
    V0,
    assign,
    burn,
    ff,
    fire_at,
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
DATA = Path(__file__).resolve().parent / "data"


@pytest.fixture(autouse=True)
def _pristine_config(monkeypatch):
    """Every test starts from the import-time configuration (see tests/mvg_test_support.restore_config); a test's own
    switches are set afterwards and win; monkeypatch undoes all of it."""
    restore_config(monkeypatch)


OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1))
TIER_A, TIER_B = 7, 10                              # agents.APPROACH_PATH_TIER, RETREAT_ON_ROUTE_TIER
WALL = tuple((x, 25) for x in range(15, 36))        # the barrier board (test_movement_fixes.py)
BARRIER_VICTIM = (25, 30)
A_UNIT, A_STEP, A_TODAY = (26, 23), (27, 23), (25, 23)      # (a) on the barrier: the fix's step and today's
B_UNIT, B_STEP, B_TODAY = (25, 20), (24, 20), (26, 20)      # (b) below a fire cell: the fix's step and today's
B_FIRE = (25, 19)
B_CLOSER_VETO, B_CLOSER_ADMIT = (26, 26), (26, 25)          # a second fire cell near her: the guard vetoes / admits
CRAFT_T = 1000.0


# ============================================================================ construction

def _model(monkeypatch, *, approach=0, retreat=0, guard=1, wind="north"):
    """A pinned real model (scenario A's team), map quieted, the wind label set, and every switch this file reads
    passed explicitly: the two fixes, the guard, and the carrying leg's MODE / SERVED / HOLD (shipped 2 / 1 / 0)."""
    switches(monkeypatch, approach=approach, retreat=retreat, guard=guard,
             FF_EXIT_LEG_MODE=2, FF_EXIT_LEG_SERVED=1, FF_EXIT_LEG_HOLD=0)
    with redirect_stdout(io.StringIO()):
        model = pinned_model(monkeypatch)
    quiet_fire(model)
    model.wind.wind_direction = wind
    return model


def _cell(agent):
    return (int(agent.pos[0]), int(agent.pos[1]))


def _approacher(model, unit_cell, victim_cell, *, status=None):
    """FF_A bound to V0 through the executor, APPROACHING (not on her cell); every other unit dead."""
    place_units(model, {FF_A: unit_cell})
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


def _reset_approacher(model, unit, cell, victim_cell, status):
    model.grid.move_agent(victim(model, V0), victim_cell)
    model.grid.move_agent(unit, cell)
    unit.target_pos = victim_cell
    unit.exiting = False
    unit.exit_target = None
    unit.status = status
    unit._reset_idle_retreat_state()


def _inb(model, c) -> bool:
    return 0 <= c[0] < model.grid.width and 0 <= c[1] < model.grid.height


def _fire_adjacent(c, burning) -> bool:
    return any((c[0] + ox, c[1] + oy) in burning for ox, oy in OFFSETS)


def _is_clean(model, c, burning, smoky) -> bool:
    return _inb(model, c) and c not in burning and c not in smoky and not _fire_adjacent(c, burning)


def _clean_field(model, target, burning, smoky) -> dict:
    if not _is_clean(model, target, burning, smoky):
        return {}
    dist = {target: 0}
    queue = deque([target])
    while queue:
        c = queue.popleft()
        for ox, oy in OFFSETS:
            n = (c[0] + ox, c[1] + oy)
            if n not in dist and _is_clean(model, n, burning, smoky):
                dist[n] = dist[c] + 1
                queue.append(n)
    return dist


def _random_box_fire(rng, model) -> tuple[set, set, tuple]:
    """test_movement_fixes.py's fenced corner box (walls, single cells and smoke inside, a burning L outside)."""
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


# ============================================================================ the oracle (independent of the code)

def _oracle_guard(u, n, v, burning, smoky, wind, x_size, y_size, t_grid=None):
    """1d.2.2 re-derived: a LEVEL-BY-LEVEL time-expanded BFS (the code under test uses a FIFO queue over hop counts).
    Level k holds the cells first entered at hop k from u; level 1 is {n} iff n is clean and T*(n) > 1; a cell joins
    level k iff it neighbours level k - 1, is in the grid, is clean, has not been entered (u counts as entered) and
    T*(x) > k. c = the level holding v. T is FAE at the published defaults unless a crafted grid is given."""
    burning = {(int(x), int(y)) for x, y in burning}
    smoky = {(int(x), int(y)) for x, y in smoky}
    if t_grid is None:
        t_grid = arrival_time(x_size, y_size, sorted(burning), wind, FrontPriorityParams())

    def inb(c):
        return 0 <= c[0] < x_size and 0 <= c[1] < y_size

    def nbrs(c):
        return [(c[0] + ox, c[1] + oy) for ox, oy in OFFSETS if inb((c[0] + ox, c[1] + oy))]

    def unclean(c):
        return c in burning or c in smoky or any(b in burning for b in nbrs(c))

    def tstar(c):
        return min(float(t_grid[x[0], x[1]]) for x in [c] + nbrs(c))

    t_v = float(t_grid[v[0], v[1]])
    if unclean(n) or not tstar(n) > 1:
        return False, None, t_v
    entered = {u, n}
    level, k, c_n = {n}, 1, (1 if n == v else None)
    while c_n is None and level:
        k += 1
        level = {y for x in level for y in nbrs(x)
                 if y not in entered and not unclean(y) and tstar(y) > k}
        entered |= level
        if v in level:
            c_n = k
    if c_n is None:
        return False, None, t_v
    return c_n + 1 <= t_v, c_n, t_v


def _crafted_t(monkeypatch, values, default=CRAFT_T):
    """Replace the guard's estimator call (movement_paths.arrival_time, read at call time) with a crafted T grid:
    `default` everywhere, 0 on burning cells (as FAE), `values` where given."""
    def fake(x_size, y_size, burning, wind, params):
        grid = np.full((x_size, y_size), float(default))
        for x, y in burning:
            grid[int(x), int(y)] = 0.0
        for cell, value in values.items():
            grid[cell] = float(value)
        return grid

    monkeypatch.setattr(movement_paths, "arrival_time", fake)
    return fake


def _corridor(x0, x1, y, *, open_cells=(), extra=()):
    """The SMOKY fence of a one-cell-wide corridor (x0..x1, y): rows y - 1 and y + 1 from x0 - 1 to x1 + 1 and both
    ends, minus `open_cells`, plus `extra`. Smoke is unclean but leaves its neighbours clean, so the corridor is the
    only clean way along."""
    fence = {(x, y - 1) for x in range(x0 - 1, x1 + 2)} | {(x, y + 1) for x in range(x0 - 1, x1 + 2)}
    fence |= {(x0 - 1, y), (x1 + 1, y)}
    return sorted((fence - set(open_cells)) | set(extra))


def _guard(u, n, v, burning=(), smoky=(), wind=(0.0, 1.0), x_size=50, y_size=50):
    return movement_paths.stranding_guard(u, n, v, burning, smoky, wind, x_size, y_size)


# ============================================================================ T-G1 known-answer boards

# Crafted T (CRAFT_T everywhere, 0 on burning cells, the listed values). Expected (admit, c_n, T(v)) derived by hand.
_TG1_CRAFTED = {
    # open ground: c = 1 + |(11,10) -> (15,12)| = 7
    "open_ground": dict(u=(10, 10), n=(11, 10), v=(15, 12), expect=(True, 7, CRAFT_T)),
    # fire at (11,13) makes (10,13) unclean: the route detours by 2 -> c = 1 + 5 + 2 = 8
    "fire_beside_route": dict(u=(10, 10), n=(10, 11), v=(10, 16), burning=[(11, 13)], expect=(True, 8, CRAFT_T)),
    # the victim's cell is unclean: never entered
    "victim_smoky": dict(u=(10, 10), n=(11, 10), v=(14, 10), smoky=[(14, 10)], expect=(False, None, CRAFT_T)),
    "victim_fire_adjacent": dict(u=(10, 10), n=(11, 10), v=(14, 10), burning=[(14, 11)],
                                 expect=(False, None, CRAFT_T)),
    # n itself unclean: vetoed at once
    "n_smoky": dict(u=(10, 10), n=(11, 10), v=(14, 10), smoky=[(11, 10)], expect=(False, None, CRAFT_T)),
    "n_fire_adjacent": dict(u=(10, 10), n=(11, 10), v=(14, 10), burning=[(11, 11)], expect=(False, None, CRAFT_T)),
    # n = v: c = 1; admitted iff 2 <= T(v); T*(v) = T(v) must also exceed 1
    "n_is_v_admit": dict(u=(10, 10), n=(11, 10), v=(11, 10), t={(11, 10): 2.0}, expect=(True, 1, 2.0)),
    "n_is_v_cut": dict(u=(10, 10), n=(11, 10), v=(11, 10), t={(11, 10): 1.5}, expect=(False, 1, 1.5)),
    "n_is_v_closes": dict(u=(10, 10), n=(11, 10), v=(11, 10), t={(11, 10): 1.0}, expect=(False, None, 1.0)),
    # the "+1": straight route, c = 4. T(v) = c + 1 admits; c < T(v) < c + 1 is vetoed by the cut ALONE; T(v) = c is
    # refused already by v's entry test T*(v) > c (T*(v) <= T(v)), so c is infinite there
    "plus_one_admit": dict(u=(10, 10), n=(11, 10), v=(14, 10), t={(14, 10): 5.0}, expect=(True, 4, 5.0)),
    "plus_one_cut": dict(u=(10, 10), n=(11, 10), v=(14, 10), t={(14, 10): 4.5}, expect=(False, 4, 4.5)),
    "c_equals_t": dict(u=(10, 10), n=(11, 10), v=(14, 10), t={(14, 10): 4.0}, expect=(False, None, 4.0)),
    # a corridor (10..16, 10) clean NOW; v = (16,10), c would be 6. It closes at (13,10), hop 3, through a NEIGHBOUR's
    # T (the fence cell (13,11) at 2.5): T*(13,10) = 2.5 <= 3
    "closes_by_neighbour_t": dict(u=(10, 10), n=(11, 10), v=(16, 10), smoky=_corridor(10, 16, 10),
                                  t={(13, 11): 2.5}, expect=(False, None, CRAFT_T)),
    # the same corridor, T*(14,10) = 4 exactly at hop 4 (fence cell (14,11) at 4.0): closed, "> k" is strict
    "closes_at_hop_k": dict(u=(10, 10), n=(11, 10), v=(16, 10), smoky=_corridor(10, 16, 10),
                            t={(14, 11): 4.0}, expect=(False, None, CRAFT_T)),
    # control: 4.5 there stays open: c = 6
    "open_after_hop_k": dict(u=(10, 10), n=(11, 10), v=(16, 10), smoky=_corridor(10, 16, 10),
                             t={(14, 11): 4.5}, expect=(True, 6, CRAFT_T)),
    # a corridor (9..16, 10): n = (10,10) lies BEHIND u = (11,10); the only route from n to v passes u
    "only_through_u": dict(u=(11, 10), n=(10, 10), v=(15, 10), smoky=_corridor(9, 16, 10),
                           expect=(False, None, CRAFT_T)),
    # the same corridor with a dead-end pocket n = (11,11) above u: v is reachable from u by its OTHER neighbour
    # (12,10) only
    "only_via_another_neighbour": dict(u=(11, 10), n=(11, 11), v=(15, 10),
                                       smoky=_corridor(9, 16, 10, open_cells=[(11, 11)], extra=[(11, 12)]),
                                       expect=(False, None, CRAFT_T)),
}


@pytest.mark.parametrize("case", sorted(_TG1_CRAFTED))
def test_tg1_known_answer_boards_crafted_t(monkeypatch, case):
    """T-G1 (pure, crafted T grids; Part 1d 1d.8 (4)): open ground; fire beside the route; the victim's cell unclean
    (smoky, fire-adjacent); n unclean; n = v; the "+1" at c_n + 1 = T(v) (admit), c_n < T(v) < c_n + 1 (veto by the
    cut alone) and c_n = T(v) (veto: v's entry test); a route clean now that closes at hop k through a neighbour's
    T (T*), and at T* = k exactly; a time-safe route only THROUGH u; a time-safe route only via ANOTHER neighbour of
    u. The verdict equals the hand-derived (admit, c_n, T(v)) and the oracle's, admit is a Python bool.
    (Fire-adjacency needs no case of its own here: FAE's T is 0 on burning cells, so T* already closes every
    fire-adjacent cell; T-G4 pins unclean_cells directly.)
    MUTANTS (by case): g_plus1 on [plus_one_cut] and [n_is_v_cut]; g_tstar and hp_t_star_cell on
    [closes_by_neighbour_t] and [closes_at_hop_k]; g_ge_k on [c_equals_t] and [closes_at_hop_k]; g_ge_1 on
    [n_is_v_closes]; g_reenter_u on [only_through_u] and [only_via_another_neighbour]; g_first_hop on
    [only_via_another_neighbour]; g_admit_inf on [victim_smoky], [victim_fire_adjacent], [c_equals_t],
    [closes_by_neighbour_t], [closes_at_hop_k], [only_through_u] and [only_via_another_neighbour]; g_n_exempt on
    [n_smoky]; g_victim_exempt on [victim_smoky]."""
    spec = _TG1_CRAFTED[case]
    fake = _crafted_t(monkeypatch, spec.get("t", {}))
    burning, smoky = spec.get("burning", []), spec.get("smoky", [])
    got = _guard(spec["u"], spec["n"], spec["v"], burning, smoky)
    assert got == spec["expect"], (case, got)
    assert type(got[0]) is bool and type(got[2]) is float
    t_grid = fake(50, 50, burning, None, None)
    assert _oracle_guard(spec["u"], spec["n"], spec["v"], burning, smoky, None, 50, 50, t_grid) == spec["expect"]


def test_tg1_no_fire_admits_with_t_infinite():
    """T-G1 (no fire, real FAE): with nothing burning T is infinite everywhere; the step is ADMITTED with c_n the
    clean hop count (1 + |n - v| = 7 here) and T(v) = inf.
    MUTANT: g_nofire_veto (with nothing burning the guard vetoes)."""
    got = _guard((10, 10), (11, 10), (15, 12), [], [])
    assert got == (True, 7, math.inf)
    assert _oracle_guard((10, 10), (11, 10), (15, 12), [], [], (0.0, 1.0), 50, 50) == got


def test_tg1_the_wind_vector_decides_the_barrier_board(monkeypatch):
    """T-G1 (an asymmetric-wind board, real FAE). The barrier board: (a)'s step (26,23) -> (27,23) toward (25,30)
    behind a 21-cell fire wall. With the wind from the WEST (vector (1, 0), "east") the flank is slow and the 36-hop
    detour is time-safe: ADMIT, c 36. With no wind (FAE's isotropic head rate) T(v) is about 12: VETO. The model's
    verdict (_stranding_guard_verdict) reads the model's wind label: "east" admits, "north" vetoes - each equal to
    the oracle at that wind.
    MUTANTS: g_wind_none (the verdict passes wind None); g_wind_none_mp (stranding_guard calls FAE with wind None)."""
    east = cfv.wind_vector_from_direction("east")
    t_east = arrival_time(50, 50, list(WALL), east, FrontPriorityParams())
    got = _guard(A_UNIT, A_STEP, BARRIER_VICTIM, WALL, [], east)
    assert got == (True, 36, float(t_east[BARRIER_VICTIM])) == _oracle_guard(A_UNIT, A_STEP, BARRIER_VICTIM, WALL, [],
                                                                            east, 50, 50)
    calm = _guard(A_UNIT, A_STEP, BARRIER_VICTIM, WALL, [], None)
    assert calm[:2] == (False, None) and calm[2] < 13.0
    for label, admit in (("east", True), ("north", False)):
        model = _model(monkeypatch, approach=1, wind=label)
        unit = _approacher(model, A_UNIT, BARRIER_VICTIM)
        burn(model, WALL)
        assert unit._approach_path_choice() == A_STEP
        verdict = unit._stranding_guard_verdict(A_STEP)
        assert verdict == _oracle_guard(A_UNIT, A_STEP, BARRIER_VICTIM, WALL, [],
                                        cfv.wind_vector_from_direction(label), 50, 50)
        assert verdict[0] is admit


def test_tg1_non_square_grid_x_is_the_first_extent(monkeypatch):
    """T-G1 (a non-square fixture, real FAE). On a 30 x 50 board (x_size = grid.width = 30, y_size = 50) the guard
    indexes T[x, y] of arrival_time(30, 50, ...): the victim at (27, 44) exists only with x as the first extent, and
    the verdict equals the oracle's (c 17 along y = 44). The model's verdict passes (grid.width, grid.height) as
    (x_size, y_size): with the grid replaced by a 30 x 50 namespace, stranding_guard receives (30, 50).
    MUTANTS: g_xy_swap (arrival_time(y_size, x_size, ...)); g_view_swap (the verdict swaps width and height)."""
    east = cfv.wind_vector_from_direction("east")
    fire = [(20, 40)]
    got = _guard((10, 44), (11, 44), (27, 44), fire, [], east, 30, 50)
    t_grid = arrival_time(30, 50, fire, east, FrontPriorityParams())
    assert t_grid.shape == (30, 50)
    assert got == (True, 17, float(t_grid[27, 44])) == _oracle_guard((10, 44), (11, 44), (27, 44), fire, [], east,
                                                                     30, 50)
    model = _model(monkeypatch, approach=1, wind="east")
    unit = _approacher(model, (10, 10), (14, 10))
    seen: list = []
    original = movement_paths.stranding_guard

    def spy(*args, **kwargs):
        seen.append(args[6:8])
        return original(*args, **kwargs)

    monkeypatch.setattr(movement_paths, "stranding_guard", spy)
    monkeypatch.setattr(model, "grid", types.SimpleNamespace(width=30, height=50))
    unit._stranding_guard_verdict((11, 10))
    assert seen == [(30, 50)]


def test_tg1_numpy_bool_burning_flags_are_read_by_truthiness(monkeypatch):
    """T-G1 (numpy.bool_ burning flags). The simulator stores burning as numpy.bool_ after its first tick: on the
    barrier board (wind "north") the model's verdict with numpy flags equals the one with Python bools and the
    oracle's - a VETO; an invisible fire would admit the step (T infinite).
    MUTANT: g_numpy_identity (fire_board_sets reads burning by identity with True)."""
    verdicts = []
    for numpy_bool in (True, False):
        model = _model(monkeypatch, approach=1, wind="north")
        unit = _approacher(model, A_UNIT, BARRIER_VICTIM)
        burn(model, WALL, numpy_bool=numpy_bool)
        assert type(fire_at(model, WALL[0]).burning) is (np.bool_ if numpy_bool else bool)
        verdicts.append(unit._stranding_guard_verdict(A_STEP))
    north = cfv.wind_vector_from_direction("north")
    assert verdicts[0] == verdicts[1] == _oracle_guard(A_UNIT, A_STEP, BARRIER_VICTIM, WALL, [], north, 50, 50)
    assert verdicts[0][:2] == (False, None)


def _random_guard_board(rng, xs, ys):
    """A random decision on an xs x ys grid: 0-3 burning walls (2-6 long) and 0-2 dots, 0-10 smoky cells, u anywhere
    (clean or not), n one of u's in-grid neighbours, v anywhere or near n."""
    burning: set = set()
    for _ in range(rng.randint(0, 3)):
        horizontal = rng.random() < 0.5
        x0, y0 = rng.randrange(xs), rng.randrange(ys)
        for i in range(rng.randint(2, 6)):
            c = (x0 + i, y0) if horizontal else (x0, y0 + i)
            if 0 <= c[0] < xs and 0 <= c[1] < ys:
                burning.add(c)
    burning |= {(rng.randrange(xs), rng.randrange(ys)) for _ in range(rng.randint(0, 2))}
    smoky = {(rng.randrange(xs), rng.randrange(ys)) for _ in range(rng.randint(0, 10))} - burning
    u = (rng.randrange(xs), rng.randrange(ys))
    n = rng.choice([(u[0] + ox, u[1] + oy) for ox, oy in OFFSETS if 0 <= u[0] + ox < xs and 0 <= u[1] + oy < ys])
    v = (rng.randrange(xs), rng.randrange(ys)) if rng.random() < 0.7 else (
        min(xs - 1, max(0, n[0] + rng.randint(-4, 4))), min(ys - 1, max(0, n[1] + rng.randint(-4, 4))))
    return burning, smoky, u, n, v


def test_tg1_property_the_guard_equals_the_oracle(monkeypatch):
    """T-G1 (property). On a NON-SQUARE 23 x 31 grid, stranding_guard equals the level-by-level oracle exactly:
    (1) 300 random boards with the REAL FAE (a random wind: four labels and None); (2) 300 random boards with a
    CRAFTED T - a front moving out from a random point at a random 0.4-3 steps per cell, plus noise, 0 on burning
    cells - where routes close part-way and T(v) falls inside the "+1" margin. Admits, vetoes with c infinite and
    vetoes with c finite (the cut alone) must all occur.
    MUTANTS: g_first_hop; g_reenter_u; g_admit_inf; g_tstar; g_plus1; g_wind_none_mp."""
    xs, ys = 23, 31
    rng = random.Random(4401)
    winds = [cfv.wind_vector_from_direction(w) for w in ("north", "south", "east", "west")] + [None]
    seen = {"fae": {"admit": 0, "veto_inf": 0, "veto_finite": 0}, "crafted": {"admit": 0, "veto_inf": 0,
                                                                            "veto_finite": 0}}
    for board in range(300):
        burning, smoky, u, n, v = _random_guard_board(rng, xs, ys)
        wind = rng.choice(winds)
        got = movement_paths.stranding_guard(u, n, v, burning, smoky, wind, xs, ys)
        assert got == _oracle_guard(u, n, v, burning, smoky, wind, xs, ys), (board, u, n, v, wind)
        seen["fae"]["admit" if got[0] else ("veto_inf" if got[1] is None else "veto_finite")] += 1
    original = movement_paths.arrival_time
    for board in range(300):
        burning, smoky, u, n, v = _random_guard_board(rng, xs, ys)
        origin, rate = (rng.randrange(xs), rng.randrange(ys)), rng.uniform(0.4, 3.0)
        grid = np.array([[rate * (abs(x - origin[0]) + abs(y - origin[1])) + rng.uniform(-1.0, 1.0)
                          for y in range(ys)] for x in range(xs)])
        for b in burning:
            grid[b] = 0.0
        if rng.random() < 0.5:                  # put T(v) inside the "+1" margin of the earliest arrival c
            near = [v] + [(v[0] + ox, v[1] + oy) for ox, oy in OFFSETS if 0 <= v[0] + ox < xs and 0 <= v[1] + oy < ys]
            for c in near:
                if c not in burning:
                    grid[c] = float(grid.max()) + 50.0
            c0 = _oracle_guard(u, n, v, burning, smoky, None, xs, ys, grid)[1]
            if c0 is not None and v not in burning:
                grid[v] = c0 + rng.uniform(0.05, 0.95)
        monkeypatch.setattr(movement_paths, "arrival_time", lambda *args, g=grid: g)
        got = movement_paths.stranding_guard(u, n, v, burning, smoky, None, xs, ys)
        monkeypatch.setattr(movement_paths, "arrival_time", original)
        assert got == _oracle_guard(u, n, v, burning, smoky, None, xs, ys, grid), (board, u, n, v)
        seen["crafted"]["admit" if got[0] else ("veto_inf" if got[1] is None else "veto_finite")] += 1
    assert seen["fae"]["admit"] >= 40 and seen["fae"]["veto_inf"] >= 40, seen
    assert min(seen["crafted"].values()) >= 10, seen


# ============================================================================ T-G2 a veto is today's step

def _b_board(model, closer):
    burn(model, [B_FIRE, closer])


@pytest.mark.parametrize("status", ("assigned", "route_blocked"))
def test_tg2_an_a_veto_is_todays_step(monkeypatch, status):
    """T-G2 ((a), Zg-2). The barrier board, wind "north": (a)'s pure choice is (27,23), the guard VETOES it (c
    infinite), and the unit takes TODAY's step - _move_toward's (25,23) - exactly as the switch-0 twin does: the
    same cell, status (today's relabel of a route_blocked unit included), tier, risk, record and retreat state, and
    no raise in either. With the wind "east" the same decision is ADMITTED and the fix's step (27,23) runs at tier 7
    (the case discriminates).
    MUTANT: g_veto_acts (a veto still takes the fix's step)."""
    outcomes = {}
    for approach in (1, 0):
        model = _model(monkeypatch, approach=approach, wind="north")
        unit = _approacher(model, A_UNIT, BARRIER_VICTIM, status=status)
        burn(model, WALL)
        verdicts: list = []
        raises: list = []
        _spy(monkeypatch, "_stranding_guard_verdict", verdicts)
        _spy(monkeypatch, "_mark_route_blocked", raises)
        if approach:
            assert unit._approach_path_choice() == A_STEP
            assert unit._greedy_choice(BARRIER_VICTIM, set(WALL), set()) == A_TODAY
        _advance(unit)
        outcomes[approach] = (_outcome(unit), raises)
        assert [(v[2], v[3][:2]) for v in verdicts] == ([((A_STEP,), (False, None))] if approach else [])
        monkeypatch.undo()
        restore_config(monkeypatch)
    assert outcomes[1] == outcomes[0]
    assert outcomes[1][0][0] == A_TODAY and outcomes[1][0][2] == 1 and outcomes[1][1] == []
    model = _model(monkeypatch, approach=1, wind="east")
    unit = _approacher(model, A_UNIT, BARRIER_VICTIM, status=status)
    burn(model, WALL)
    _advance(unit)
    assert (_cell(unit), unit._last_move_tier, unit.status) == (A_STEP, TIER_A, "assigned")


@pytest.mark.parametrize("stored", ("fresh", "stored"))
def test_tg2_a_b_veto_is_todays_retreat_with_its_writes(monkeypatch, stored):
    """T-G2 ((b), Zg-2). A fire cell below the unit and a second one near her ((26,26), wind "north"): (b)'s pure
    choice is (24,20) and the guard VETOES it; the unit runs TODAY's _survival_move - cell (26,20), record
    "survival_retreat", and the _idle_retreat_* writes (origin, steps, stalled, last cell) - exactly as the
    switch-0 twin, from a fresh or a stored retreat state. With the second fire at (26,25) the same decision is
    ADMITTED: the fix's step (24,20) at tier 10, "survival_retreat_on_route", no retreat-state write.
    MUTANT: g_veto_acts (a veto still takes the fix's step)."""
    state = {"_idle_retreat_origin": (25, 21), "_idle_retreat_steps": 2, "_idle_retreat_stalled": False,
             "_idle_retreat_last_cell": (24, 21)}
    outcomes = {}
    for retreat in (1, 0):
        model = _model(monkeypatch, retreat=retreat, wind="north")
        unit = _approacher(model, B_UNIT, BARRIER_VICTIM)
        if stored == "stored":
            for name, value in state.items():
                setattr(unit, name, value)
        _b_board(model, B_CLOSER_VETO)
        verdicts: list = []
        _spy(monkeypatch, "_stranding_guard_verdict", verdicts)
        if retreat:
            assert unit._retreat_on_route_choice() == B_STEP and unit._survival_choice() == B_TODAY
        _advance(unit)
        outcomes[retreat] = _outcome(unit)
        assert [(v[2], v[3][:2]) for v in verdicts] == ([((B_STEP,), (False, None))] if retreat else [])
        monkeypatch.undo()
        restore_config(monkeypatch)
    assert outcomes[1] == outcomes[0]
    assert outcomes[1][0] == B_TODAY and outcomes[1][4] == "survival_retreat"
    model = _model(monkeypatch, retreat=1, wind="north")
    unit = _approacher(model, B_UNIT, BARRIER_VICTIM)
    if stored == "stored":
        for name, value in state.items():
            setattr(unit, name, value)
    before = _retreat_state(unit)
    _b_board(model, B_CLOSER_ADMIT)
    _advance(unit)
    assert (_cell(unit), unit._last_move_tier) == (B_STEP, TIER_B)
    assert unit.movement_reason["fine_category"] == "survival_retreat_on_route"
    assert _retreat_state(unit) == before


_SNAP = ("status", "assigned", "target_pos", "exiting", "exit_target", "_idle_retreat_origin", "_idle_retreat_steps",
         "_idle_retreat_stalled", "_idle_retreat_last_cell", "_last_move_tier", "_last_move_risk", "movement_reason",
         "_movement_last_transition_key", "_movement_last_notable_category")


def _snapshot(unit) -> dict:
    out = {name: getattr(unit, name, None) for name in _SNAP}
    out["movement_reason"] = dict(out["movement_reason"] or {})
    out["pos"] = _cell(unit)
    return out


def _restore(unit, snap) -> None:
    unit.model.grid.move_agent(unit, snap["pos"])
    for name in _SNAP:
        setattr(unit, name, dict(snap[name]) if name == "movement_reason" else snap[name])


def test_tg2_property_every_veto_is_todays_step(monkeypatch):
    """T-G2 (property, Zg-2). 200 random boards (fenced corner boxes, a random wind), both fixes and the guard on:
    an approacher from a clean start behind a barrier (up to six advances) and from three unclean starts (one
    advance each). At EVERY decision the guard vetoes, the advance is replayed from the same unit state with both
    fix switches at 0 (today's code): cell, status, tier, risk, record, retreat-state writes and the raise are
    identical. At every admitted decision the fix's own step is taken (the cell the pure choice named, at tier 7 or
    10). Vetoes of (a) and of (b) and admits of both must occur.
    MUTANT: g_veto_acts (a veto still takes the fix's step)."""
    model = _model(monkeypatch, approach=1, retreat=1)
    unit = _approacher(model, (1, 1), (3, 3))
    status = unit.status
    raises: list = []
    _spy(monkeypatch, "_mark_route_blocked", raises, through=False)
    verdicts: list = []
    _spy(monkeypatch, "_stranding_guard_verdict", verdicts)
    choices: list = []
    for name in ("_approach_path_choice", "_retreat_on_route_choice"):
        _spy(monkeypatch, name, choices)
    rng = random.Random(4402)
    counts = {"a_veto": 0, "b_veto": 0, "a_admit": 0, "b_admit": 0}
    for board in range(200):
        burning, smoky, box = _random_box_fire(rng, model)
        model.wind.wind_direction = rng.choice(("north", "south", "east", "west"))
        v = _random_cell(rng, model, lambda c: c not in burning, box=box)
        field = _clean_field(model, v, burning, smoky)
        detour = [c for c, d in field.items() if d - abs(c[0] - v[0]) - abs(c[1] - v[1]) >= 2]
        clean_s = (rng.choice(detour) if detour and rng.random() < 0.8 else
                   _random_cell(rng, model, lambda c: c != v and _is_clean(model, c, burning, smoky), box=box))
        unclean = [_random_cell(rng, model, lambda c: c != v and c not in burning
                                and not _is_clean(model, c, burning, smoky), box=box) for _ in range(3)]
        _lay(model, burning, smoky)
        for start, steps in [(clean_s, 6)] + [(s, 1) for s in unclean]:
            if start is None:
                continue
            _reset_approacher(model, unit, start, v, status)
            for _ in range(steps):
                before = _snapshot(unit)
                del raises[:], verdicts[:], choices[:]
                _advance(unit)
                guarded = (_outcome(unit), list(raises))
                after = _snapshot(unit)
                acting = [c for c in choices if c[3] is not None]
                assert len(verdicts) == len(acting) <= 1, (board, verdicts, choices)
                if verdicts:
                    kind = "a" if acting[0][0] == "_approach_path_choice" else "b"
                    step_cell, admit = verdicts[0][2][0], verdicts[0][3][0]
                    assert step_cell == acting[0][3]
                    if admit:
                        counts[kind + "_admit"] += 1
                        assert guarded[0][0] == step_cell and guarded[0][2] == (TIER_A if kind == "a" else TIER_B)
                    else:
                        counts[kind + "_veto"] += 1
                        _restore(unit, before)
                        monkeypatch.setattr(cfv, "FF_APPROACH_PATH", 0)
                        monkeypatch.setattr(cfv, "FF_RETREAT_KEEP_APPROACH", 0)
                        del raises[:]
                        _advance(unit)
                        today = (_outcome(unit), list(raises))
                        monkeypatch.setattr(cfv, "FF_APPROACH_PATH", 1)
                        monkeypatch.setattr(cfv, "FF_RETREAT_KEEP_APPROACH", 1)
                        assert guarded == today, (board, start, kind, guarded, today)
                        _restore(unit, after)
                if _cell(unit) == v:
                    break
    assert min(counts.values()) >= 10 and counts["a_veto"] >= 100, counts


# ============================================================================ T-G3 guard at exact 0 = the urgency round's fixes

# The digest of _fix_corpus(guard=0) on the URGENCY round's code (5dba5bcb: fixes (a) and (b) as screened, U1 and
# fix (c) at their shipped 0), recorded by running this very function with the urgency checkout (E:/Projects/SAS_wt/
# urgency at 0d5358e3, whose code is 5dba5bcb's byte for byte) first on sys.path - tests/mvg_test_support.py is
# base-safe and the guard switch is an unknown, unread name there - under PYTHONHASHSEED 0 and 12345 (equal). This
# branch's code at guard 0 gave the same digest before the pin was written.
TG3_GOLDEN_URGENCY = "d65f26742d2cda8c6765cef298e557ba69109b20c0fdc1baed222a21e0d69ca1"
TG3_BOARDS = 400


def _fix_corpus(monkeypatch, guard) -> tuple[str, dict]:
    """A board corpus of fix decisions, both fixes ON and the guard at `guard`: 400 fenced corner boxes with a random
    wind; on each, an approacher from a clean start behind a barrier (up to four advances: (a), and (b) after any
    unclean step) and from three unclean starts (one advance each; a random stored retreat state on a third of
    them). Returns (sha256 over every advance's outcome - cell, status, tier, risk, record, exiting, retreat state -
    and the raise flag, {tier: count}). Base-safe: reads no name this round adds."""
    restore_config(monkeypatch)
    switches(monkeypatch, approach=1, retreat=1, guard=guard,
             FF_EXIT_LEG_MODE=2, FF_EXIT_LEG_SERVED=1, FF_EXIT_LEG_HOLD=0)
    with redirect_stdout(io.StringIO()):
        model = pinned_model(monkeypatch)
    quiet_fire(model)
    unit = _approacher(model, (1, 1), (3, 3))
    status = unit.status
    raised: list = []

    def stub(self, *args, **kwargs):
        raised.append(1)

    monkeypatch.setattr(agents.Firefighter, "_mark_route_blocked", stub)
    rng = random.Random(4403)
    rows, tiers = [], {}
    for board in range(TG3_BOARDS):
        burning, smoky, box = _random_box_fire(rng, model)
        model.wind.wind_direction = rng.choice(("north", "south", "east", "west"))
        v = _random_cell(rng, model, lambda c: c not in burning, box=box)
        field = _clean_field(model, v, burning, smoky)
        detour = [c for c, d in field.items() if d - abs(c[0] - v[0]) - abs(c[1] - v[1]) >= 2]
        clean_s = (rng.choice(detour) if detour and rng.random() < 0.8 else
                   _random_cell(rng, model, lambda c: c != v and _is_clean(model, c, burning, smoky), box=box))
        unclean = [_random_cell(rng, model, lambda c: c != v and c not in burning
                                and not _is_clean(model, c, burning, smoky), box=box) for _ in range(3)]
        _lay(model, burning, smoky)
        for i, (start, steps) in enumerate([(clean_s, 4)] + [(s, 1) for s in unclean]):
            if start is None:
                continue
            _reset_approacher(model, unit, start, v, status)
            if i and rng.random() < 1 / 3:
                unit._idle_retreat_origin = (start[0] + rng.randint(-3, 3), start[1] + rng.randint(-3, 3))
                unit._idle_retreat_steps = rng.randint(0, 6)
                unit._idle_retreat_stalled = rng.random() < 0.3
                unit._idle_retreat_last_cell = rng.choice(
                    [None] + [(start[0] + ox, start[1] + oy) for ox, oy in OFFSETS])
            for k in range(steps):
                del raised[:]
                _advance(unit)
                out = _outcome(unit)
                rows.append((board, i, k, out, bool(raised)))
                tiers[out[2]] = tiers.get(out[2], 0) + 1
                if _cell(unit) == v:
                    break
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest(), tiers


def test_tg3_guard_at_exact_0_is_the_urgency_rounds_fixes(monkeypatch):
    """T-G3. With FF_FIX_STRANDING_GUARD at an exact 0, both fixes on, a 400-board corpus of fix decisions gives the
    digest the urgency round's own (a) / (b) code gives (5dba5bcb, TG3_GOLDEN_URGENCY): the guard switch at 0 is the
    screened fixes, step for step. The corpus exercises both fixes, and with the guard at 1 its digest differs
    (the guard vetoes there), so the comparison can see a guard that is not off.
    MUTANT: sw_guard_ignored (the guard applied whatever FF_FIX_STRANDING_GUARD says)."""
    digest0, tiers0 = _fix_corpus(monkeypatch, 0)
    assert tiers0.get(TIER_A, 0) >= 200 and tiers0.get(TIER_B, 0) >= 100, tiers0
    assert digest0 == TG3_GOLDEN_URGENCY
    verdicts: list = []
    _spy(monkeypatch, "_stranding_guard_verdict", verdicts)
    digest1, _tiers1 = _fix_corpus(monkeypatch, 1)
    vetoes = sum(1 for v in verdicts if not v[3][0])
    assert vetoes >= 100 and digest1 != digest0, vetoes


# ============================================================================ T-G4 the ported helpers = U1's

U1_COPY = DATA / "urgency_dispatch_5dba5bcb.py"
U1_COMMIT, U1_PATH = "5dba5bcb", "src_extension/planning/urgency_dispatch.py"
U1_SHA = "cfc97ebd6dcc4f3d2b3102468769b7396f78e86d5f93e342f25fe5370632b1cf"


def _load_u1():
    """The frozen copy of the urgency round's U1 module (urgency_dispatch.py at 5dba5bcb, byte for byte), loaded BY
    PATH as test data - this branch does not carry U1. Its sha256 (of the LF form: a checkout with autocrlf holds CRLF)
    is pinned, and checked against `git show` when git can see the commit."""
    raw = U1_COPY.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == U1_SHA
    try:
        proc = subprocess.run(["git", "-C", str(ROOT), "show", f"{U1_COMMIT}:{U1_PATH}"], capture_output=True,
                              timeout=60)
        if proc.returncode == 0:
            assert proc.stdout == raw
    except (OSError, subprocess.SubprocessError):
        pass
    loader = importlib.machinery.SourceFileLoader("_mvg_frozen_urgency_dispatch", str(U1_COPY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_tg4_the_ported_bfs_helpers_equal_u1s_on_a_property_corpus():
    """T-G4. unclean_cells, t_star, safe_route_hops and _in_bounds of movement_paths equal those of the frozen U1
    module (urgency_dispatch.py at 5dba5bcb) - and SEARCH_ORDER is the same - on 400 random boards: square and
    non-square grids (50 x 50, 30 x 50, 50 x 30, 17 x 23), burning cells in and out of the grid, smoke; T grids from
    FAE (four winds and none), random real grids with infinite entries, and INTEGER fronts (a whole number of steps
    per cell from a random origin, plus whole-step noise), on which T* - offset equals the hop count k often, so the
    strict "> k" is exercised; T* at 20 random cells per board, and the time-expanded BFS from a random source with
    a random blocked set and hop offset (0, 1 or 2.5).
    MUTANTS: hp_t_star_cell (t_star ignores the neighbours); hp_no_adjacent (unclean_cells drops the burning cells'
    neighbours); g_ge_k (">= k" in safe_route_hops)."""
    u1 = _load_u1()
    assert movement_paths.SEARCH_ORDER == u1.SEARCH_ORDER
    rng = random.Random(4404)
    winds = [(0.0, 1.0), (0.0, -1.0), (1.0, 0.0), (-1.0, 0.0), None]
    reached = 0
    for sample in range(400):
        xs, ys = rng.choice([(50, 50), (30, 50), (50, 30), (17, 23)])
        burning = [(rng.randint(-2, xs + 1), rng.randint(-2, ys + 1)) for _ in range(rng.randint(0, 25))]
        smoky = [(rng.randrange(xs), rng.randrange(ys)) for _ in range(rng.randint(0, 12))]
        assert movement_paths.unclean_cells(burning, smoky, xs, ys) == u1.unclean_cells(burning, smoky, xs, ys)
        kind = rng.random()
        if kind < 0.5:
            t_grid = arrival_time(xs, ys, burning, rng.choice(winds), FrontPriorityParams())
        elif kind < 0.7:
            t_grid = np.array([[rng.choice([math.inf, rng.uniform(0, 40)]) for _ in range(ys)] for _ in range(xs)])
        else:
            ox, oy, rate = rng.randrange(xs), rng.randrange(ys), rng.randint(1, 3)
            t_grid = np.array([[float(rate * (abs(x - ox) + abs(y - oy)) + rng.randint(0, 2)) for y in range(ys)]
                               for x in range(xs)])
        for _ in range(20):
            c = (rng.randrange(xs), rng.randrange(ys))
            assert movement_paths.t_star(t_grid, c, xs, ys) == u1.t_star(t_grid, c, xs, ys)
            p = (rng.randint(-1, xs), rng.randint(-1, ys))
            assert movement_paths._in_bounds(p, xs, ys) is u1._in_bounds(p, xs, ys)
        unclean = u1.unclean_cells(burning, smoky, xs, ys) | {(rng.randrange(xs), rng.randrange(ys))
                                                              for _ in range(rng.randint(0, 6))}
        source = (rng.randrange(xs), rng.randrange(ys))
        offset = rng.choice([0.0, 1.0, 2.5])

        def tso(x, grid=t_grid):
            return u1.t_star(grid, x, xs, ys) - offset

        mine = movement_paths.safe_route_hops(source, xs, ys, unclean, tso)
        assert mine == u1.safe_route_hops(source, xs, ys, unclean, tso), sample
        reached += len(mine) > 1
    assert reached >= 200, reached


# ============================================================================ T-G5 the switch

_MISSING = object()
GUARD_ON = [1, 1.0, True, "1", None, 2, " 1 ", 0.5, "on", "", _MISSING]
GUARD_ON_IDS = ["1", "1.0", "True", "str1", "None", "2", "str_1_", "0.5", "on", "empty", "missing"]
GUARD_OFF = [0, 0.0, False, "0", " 0 "]
GUARD_OFF_IDS = ["0", "0.0", "False", "str0", "str_0_"]


def _put(monkeypatch, value):
    if value is _MISSING:
        monkeypatch.delattr(cfv, "FF_FIX_STRANDING_GUARD", raising=False)
    else:
        monkeypatch.setattr(cfv, "FF_FIX_STRANDING_GUARD", value, raising=False)


@pytest.mark.parametrize("value", GUARD_ON, ids=GUARD_ON_IDS)
def test_tg5_the_guard_is_on_for_everything_but_an_exact_zero(monkeypatch, value):
    """T-G5 (Part 1d 1d.8 (4): 1, 1.0, True, "1", None, 2 - plus " 1 ", 0.5, "on", "" and a missing name): the
    guard switch ships 1 and is OFF only on an exact 0, so every one of these reads ON.
    MUTANTS: sw_guard_default on [missing]; sw_guard_truthy on [None] and [empty]; sw_guard_exact1 on [None], [2],
    [0.5], [on] and [empty]."""
    _put(monkeypatch, value)
    assert agents.ff_fix_stranding_guard() is True


@pytest.mark.parametrize("value", GUARD_OFF, ids=GUARD_OFF_IDS)
def test_tg5_the_guard_is_off_only_on_an_exact_zero(monkeypatch, value):
    """T-G5 (0, 0.0, "0" - plus False and " 0 "): what denotes the integer 0 turns the guard OFF.
    MUTANT: sw_guard_truthy on [str0] and [str_0_]."""
    _put(monkeypatch, value)
    assert agents.ff_fix_stranding_guard() is False


def test_tg5_shipped_one_and_read_at_call_time(monkeypatch):
    """T-G5. FF_FIX_STRANDING_GUARD ships 1, and the accessor reads the cfv module at CALL time; through the model,
    the same barrier decision is vetoed with the switch at 1 and taken with it at 0, on one model, switching between
    advances.
    MUTANTS: sw_guard_import (read once at import time); sw_guard_shipped0 (shipped 0)."""
    assert cfv.FF_FIX_STRANDING_GUARD == 1
    for value, expected in ((0, False), (1, True), (" 0 ", False), (_MISSING, True), (0.0, False)):
        _put(monkeypatch, value)
        assert agents.ff_fix_stranding_guard() is expected, value
    model = _model(monkeypatch, approach=1, guard=1, wind="north")
    unit = _approacher(model, A_UNIT, BARRIER_VICTIM)
    burn(model, WALL)
    for value, cell in ((1, A_TODAY), (0, A_STEP)):
        _put(monkeypatch, value)
        _reset_approacher(model, unit, A_UNIT, BARRIER_VICTIM, "assigned")
        _advance(unit)
        assert _cell(unit) == cell, value


# ============================================================================ T-G6 never evaluated with both fixes at 0

@pytest.mark.parametrize("guard", (1, 0, "missing"))
@pytest.mark.parametrize("fixes", ("zero", "false"))
def test_tg6_with_both_fixes_at_0_the_guard_is_never_evaluated(monkeypatch, fixes, guard):
    """T-G6 (identity). Both fix switches at an exact 0 (0, or False - since the flip a MISSING fix switch reads ON,
    so it is no longer an off form), the guard at 1, 0 or missing: on four boards where a fix
    WOULD act and the guard would veto or admit - (a) on the barrier with the wind "north" (veto) and "east"
    (admit), (b) below a fire with the second fire at (26,26) (veto) and (26,25) (admit) - the guard is never
    evaluated: not its switch, not the verdict, not stranding_guard, FAE's call or the ported helpers (each raises
    if called). Each unit takes today's step. (The real-run identity - the switches at 0, and the fixes at 0 with the
    guard at 1, equal the base digest - is test_movement_fixes.py T-ID-M.)
    MUTANTS: g_switch_first (_guarded reads the switch before testing for a missing step); g_eval_off (the (a)
    site evaluates the guard on (a)'s choice whatever FF_APPROACH_PATH says); g_eval_off_b (the (b) site evaluates
    the guard on (b)'s choice whatever FF_RETREAT_KEEP_APPROACH says - failed on the two (b) boards)."""

    def boom(*args, **kwargs):
        raise AssertionError("the stranding guard was evaluated with both fixes off")

    monkeypatch.setattr(agents.Firefighter, "_stranding_guard_verdict", boom)
    for name in ("stranding_guard", "arrival_time", "unclean_cells", "t_star", "safe_route_hops"):
        monkeypatch.setattr(movement_paths, name, boom)
    monkeypatch.setattr(agents, "ff_fix_stranding_guard", boom)
    boards = (("a", "north", None), ("a", "east", None), ("b", "north", B_CLOSER_VETO), ("b", "north", B_CLOSER_ADMIT))
    for kind, wind, closer in boards:
        model = _model(monkeypatch, wind=wind)
        for name in ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH"):
            monkeypatch.setattr(cfv, name, 0 if fixes == "zero" else False, raising=False)
        if guard == "missing":
            monkeypatch.delattr(cfv, "FF_FIX_STRANDING_GUARD", raising=False)
        else:
            monkeypatch.setattr(cfv, "FF_FIX_STRANDING_GUARD", guard, raising=False)
        if kind == "a":
            unit = _approacher(model, A_UNIT, BARRIER_VICTIM)
            burn(model, WALL)
            _advance(unit)
            assert _cell(unit) == A_TODAY
        else:
            unit = _approacher(model, B_UNIT, BARRIER_VICTIM)
            _b_board(model, closer)
            _advance(unit)
            assert _cell(unit) == B_TODAY


# ============================================================================ T-G7 the built guard = the frozen guard

FROZEN_GUARD_SHA = "70eeba7877dae6174999ae2a00774bdeeb36ced08d35df407f27318cd3a313b2"
CORPUS = DATA / "mvg_guard_corpus.json.gz"
CORPUS_COLS = ["run", "step", "unit", "kind", "u", "n", "v", "burning", "smoky", "wind", "grid", "admit", "c", "T_v"]


def _sha256_lf(path) -> str:
    """sha256 of a file's bytes with CRLF folded to LF (the form the frozen hashes are of)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _decode_float(x) -> float:
    """The corpus writes a non-finite T(v) as the string "inf" / "-inf" / "nan" (strict JSON); float() reads both."""
    return float(x)


def test_tg7_the_built_guard_equals_the_frozen_guard_on_1019_recorded_decisions():
    """T-G7 (value identity, no outcome read). The corpus tests/data/mvg_guard_corpus.json.gz holds every live fix
    (a) / (b) decision of the urgency screen's 43 arm-M R0 replays - 1 019, 626 vetoed (Part 1d 1d.2.6) - with its
    decision board and the verdict of the FROZEN guard outputs/_mvg_guard_diag.guard (sha256 70eeba78..., computed
    in the urgency checkout by outputs/_mvg_make_guard_corpus.py, which also checked each verdict against the Part 1d
    diagnostic's own output). movement_paths.stranding_guard, called on the same (u, n, v, board, wind, extents),
    equals it on every decision: admit, c_n and T(v), exactly. PROVENANCE: the header names the frozen guard by its
    sha256 (LF form; this branch's byte copy outputs/_mvg_guard_diag.py is re-hashed here when the tree holds it -
    the mutation check's partial copy does not), the 43 source replays,
    U1's module (the frozen copy T-G4 loads), and an FAE whose sha256 equals this branch's fire_arrival_estimate.py
    (the estimate the frozen guard ran on is the one the built guard runs on).
    MUTANTS: g_wind_none_mp (FAE without the wind); g_admit_inf; g_first_hop; g_tstar."""
    with gzip.open(CORPUS, "rb") as fh:
        corpus = json.loads(fh.read().decode("utf-8"))
    header = corpus["header"]
    assert header["frozen_guard"]["sha256_lf"] == FROZEN_GUARD_SHA
    assert header["frozen_guard"]["copy_sha256_lf"] == FROZEN_GUARD_SHA
    copy = ROOT / "outputs" / "_mvg_guard_diag.py"
    if copy.exists():                       # absent only in a partial copy of the tree (the mutation check's)
        assert _sha256_lf(copy) == FROZEN_GUARD_SHA
    fae =_sha256_lf(ROOT / "src_extension" / "planning" / "fire_arrival_estimate.py")
    assert header["frozen_guard"]["fire_arrival_estimate_sha256_lf"] == fae
    assert header["mvg_fire_arrival_estimate_sha256_lf"] == fae
    assert len(header["sources"]) == 43 and all(s["run"].startswith("ud2") for s in header["sources"])
    assert header["frozen_guard"]["urgency_dispatch_sha256_lf"] == U1_SHA
    assert header["counts"]["decisions"] == 1019 and header["counts"]["vetoes"] == 626
    assert corpus["cols"] == CORPUS_COLS
    rows = [dict(zip(CORPUS_COLS, r)) for r in corpus["decisions"]]
    assert len(rows) == 1019 and sum(1 for r in rows if not r["admit"]) == 626
    mismatches = []
    for r in rows:
        got = movement_paths.stranding_guard(
            tuple(r["u"]), tuple(r["n"]), tuple(r["v"]), {tuple(c) for c in r["burning"]},
            {tuple(c) for c in r["smoky"]}, None if r["wind"] is None else tuple(r["wind"]), r["grid"][0], r["grid"][1])
        want = (r["admit"], r["c"], _decode_float(r["T_v"]))
        if got != want or type(got[0]) is not bool:
            mismatches.append((r["run"], r["step"], r["unit"], r["kind"], got, want))
    assert mismatches == [], mismatches[:5]


# ============================================================================ T-G8 the published-rate estimate only

def test_tg8_searcher_fp_knobs_do_not_change_any_verdict(monkeypatch):
    """T-G8. With SEARCHER_FP_U10_KMH = 40 set on cfv (the --set route), the searchers' front_priority_params()
    changes and would turn two ADMITTED decisions into vetoes - the barrier board with the wind "east" and the (b)
    board with the second fire at (26,25), wind "north" - but the guard's verdicts (the model's and
    stranding_guard's with no params) stay those of the published defaults, and the fixes' steps are taken.
    MUTANTS: g_fae_params (stranding_guard's default params read front_priority_params()); g_fae_params_view (the
    verdict passes params=front_priority_params())."""
    monkeypatch.setattr(cfv, "SEARCHER_FP_U10_KMH", 40.0, raising=False)
    assert front_priority_params().u10_kmh == 40.0 and front_priority_params() != FrontPriorityParams()
    cases = (("a", "east", A_UNIT, A_STEP, WALL), ("b", "north", B_UNIT, B_STEP, (B_FIRE, B_CLOSER_ADMIT)))
    for kind, label, u, n, fire in cases:
        wind = cfv.wind_vector_from_direction(label)
        published = _oracle_guard(u, n, BARRIER_VICTIM, fire, [], wind, 50, 50)
        knob = _oracle_guard(u, n, BARRIER_VICTIM, fire, [], wind, 50, 50,
                             arrival_time(50, 50, list(fire), wind, front_priority_params()))
        assert published[0] is True and knob[0] is False, (kind, published, knob)
        assert _guard(u, n, BARRIER_VICTIM, fire, [], wind) == published
        model = _model(monkeypatch, approach=1, retreat=1, wind=label)
        unit = _approacher(model, u, BARRIER_VICTIM)
        burn(model, fire)
        assert unit._stranding_guard_verdict(n) == published
        _advance(unit)
        assert (_cell(unit), unit._last_move_tier) == (n, TIER_A if kind == "a" else TIER_B)
