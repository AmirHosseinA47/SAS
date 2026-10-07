"""MVG round instrument: outputs/_mvg_probe.py (outputs/urgency_part1d.txt 1d.6.2, 1d.8 (5), amendment 1d.13).

A port of urgency:outputs/_ud_probe.py (ud_probe v2, commit 5dba5bcb): outputs/_ut_probe.py (UNCHANGED, run in-process)
plus read-only recorders. usage (exactly _ud_probe.py's interface):
    _mvg_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args ...>
    --repo is REQUIRED after "--" (every layer below defaults to the main checkout otherwise).

WHAT CHANGED FROM ud_probe v2, AND WHY (nothing else did):
  - The movement record is GUARD-AWARE (the stranding guard SG-T, 1d.2): branch labels approach_a_veto /
    retreat_b_veto, the instrument's own guard verdict at every decision where fix (a) or (b) WOULD act (in every arm;
    a shadow in arms 0 and N), the model's verdict where the model evaluated the guard, a new d["mvg"] section.
  - Fix (c) and U1 are not in this round (rulings, urgency report 11; Part 1d 1d.7): no (c) shadow (the fc column is
    kept, always None, so the v2 column indices hold), no C-4 / C-5 detectors, no carry-kind branches (c0..c3), no
    wraps of the model's U1 code. The U1 SHADOW of 22.9's U1 class is kept: the kick recorder computes the U1 order
    from INSTRUMENT-SIDE replicas of the urgency round's WildFireModel._urgency_waiting (waiting_replica) and
    _urgency_dispatch_view (view_replica; urgency:wildfire_model.py at 5dba5bcb) and a frozen instrument-only copy of
    urgency:src_extension/planning/urgency_dispatch.py at 5dba5bcb, outputs/_mvg_u1_shadow.py, loaded BY PATH
    (importlib, module name "mvg_u1_shadow"), never from the repo; its sha256 is d["mvg"]["u1_shadow_sha"].
  - The repo SHA list (d["ud"]["src_sha"] and d["mvg"]["src_sha"]) is MVG_SHA_FILES (no urgency_dispatch.py).

RECORD-ONLY. Every recorder only READS model state: no draw from any RNG, no print to stdout or stderr of its own (the
invariant checker's own stderr lines are re-emitted, as _dp_probe does), no attribute set on the model or an agent.
Every wrap is installed at CLASS level before the model is built. The shadows call the model's own PURE methods
(agents.Firefighter._greedy_choice, _survival_choice, _approach_path_choice, _retreat_on_route_choice) through the class
functions captured before any wrap, and the guard's pure function movement_paths.stranding_guard on arguments the
instrument builds itself (the unit's cell, the fix's cell, target_pos after the refresh, fire_board_sets, the wind
vector of the model's wind label, grid.width / grid.height); each shadow is guarded: the unit's __dict__, the model's
attributes (names and shallow values) and the RNG states (agents.random, model.random, numpy) are compared before and
after, and a difference is an instrument error. Observer exceptions are caught and listed (dp: d["dp"]["errors"], the
v2 movement / kick recorders: d["ud"]["errors"], the guard material: d["mvg"]["errors"]); an observer never stops a
run. d is written whatever the chain's return code.

d["dp"]   EXACTLY _dp_probe v2's section (as ud_probe v2).
d["ud"]   probe, rc_chain, switches, src_sha, schema, kicks, decisions, fates, cmd_ctx, rel_ctx, shadow_mismatch,
          timing, errors - ud_probe v2's section (kick recorder, decisions, fates, timing); fix_calls / fix_ms_total
          carry "a", "b" and "g" (the guard, timed as its OWN fix-code call, S6); u1_model_ms is always 0 (no U1 in the
          model).
d["mv"]   {"cols": MV_COLS, "rows": [...]}: v2's 38 columns + gA, gB, veto, acted_g (see MV_SCHEMA).
d["mv_events"]  one dict per ACTED event (the UNGUARDED shadow acted, v2's definition, every arm) with v2's fields
          (step, kind, unit, victim, live, row, cell, today, taken, branch, detail, agree) plus guard {admit, c, T_v,
          model_admit}, vetoed and ran. live = the fix's switch is effective (v2); vetoed = live, the guard is on and
          the MODEL's verdict vetoed the step; ran = live and not vetoed (the fix's step was taken). agree (live only)
          = the model did what the GUARDED pre-advance shadow says: the fix's step (branch approach_a / retreat_b,
          post == the fix's cell) when the guard is off or the INSTRUMENT admits, today's step (branch approach_a_veto /
          retreat_b_veto, post == today's shadow cell, or the unit's cell when today's shadow does not move) when the
          guard is on and the instrument vetoes.
d["mvg"]  probe, switches, src_sha, u1_shadow_sha, u1_shadow_path, u1_shadow_error, guard {cols, rows}, replica,
          timing, errors (see MVG_SCHEMA).
"""
from __future__ import annotations

import hashlib
import heapq
import importlib.util
import io
import json
import math
import os
import runpy
import sys
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "mvg_probe v1"
U1_SHADOW = os.path.join(HERE, "_mvg_u1_shadow.py")
U1_SHADOW_MODULE = "mvg_u1_shadow"
_N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
# _dp_probe v2's list, unchanged (d["dp"]["src_sha"])
SHA_FILES = (
    "src_extension/planning/joint_dispatch.py",
    "src_extension/adaptation_manager.py",
    "src_extension/execution/rescue_executor.py",
    "src_extension/planning/rescue_planner.py",
    "wildfire_model.py",
    "agents.py",
    "common_fixed_variables.py",
)
# the repo files this round's code lives in (d["ud"]["src_sha"] and d["mvg"]["src_sha"]); urgency_dispatch.py is NOT
# here: U1 is not in the repo, its instrument-only copy is hashed apart (d["mvg"]["u1_shadow_sha"])
MVG_SHA_FILES = (
    "agents.py",
    "wildfire_model.py",
    "common_fixed_variables.py",
    "src_extension/planning/movement_paths.py",
    "src_extension/planning/fire_arrival_estimate.py",
)
MVG_SWITCHES = ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_FIX_STRANDING_GUARD")
URGENCY_SWITCHES = ("DISPATCH_URGENCY", "FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_CARRY_REPLAN")
OTHER_SWITCHES = ("FF_EXIT_LEG_MODE", "FF_EXIT_LEG_SERVED", "FF_EXIT_LEG_HOLD", "ROUTE_BLOCK_STALE_CLEAR")
MV_COLS = (
    "step", "unit", "victim", "leg", "branch", "pre", "post", "target", "digest",
    "st_pre", "st_post", "tier", "mt", "rb_call", "rb_set",
    "trig", "zrb", "today", "fa", "fb", "fbB", "fc", "acted",
    "dc", "dcx", "df", "dm", "dr", "gesc",
    "cls_pre", "cls_post", "fd_pre", "fd_post", "c1_pre", "c1_post",
    "fix_ms", "inst_ms", "dcb",
    "gA", "gB", "veto", "acted_g",
)
_INST_MS_I = MV_COLS.index("inst_ms")
GUARD_COLS = (
    "step", "unit", "victim", "kind", "u", "n", "v", "today", "today_kind", "today_tier", "today_raise",
    "c", "T_v", "admit", "model_admit", "model_verdict", "model_cell", "took", "post", "tier", "raise",
    "pre_writes", "pred_writes", "post_writes", "ms_guard", "ms_inst", "row",
)
FIX_BRANCH = {"a": "approach_a", "b": "retreat_b"}
VETO_BRANCH = {"a": "approach_a_veto", "b": "retreat_b_veto"}
MV_SCHEMA = (
    "mv cols (v2 meaning unless stated): step = evaluation_timesteps_counter at the advance (rows_ff index + 1); "
    "unit / victim = ids (victim = the bound victim before the advance); leg approach|carry; branch = the branch the "
    "advance TOOK, GUARD-AWARE: approach (today's _move_toward; the fix did not act or is off), approach_a (fix (a)'s "
    "step was taken: guard off, or the guard admitted), approach_a_veto (fix (a)'s pure choice returned a cell, the "
    "guard was on and the MODEL's verdict vetoed it: today's step ran), retreat (today's survival retreat), retreat_fb "
    "(survival with no move -> _move_toward), retreat_b (fix (b)'s step taken), retreat_b_veto (fix (b) would have "
    "acted, the model's guard vetoed: today's survival retreat and its fallback ran), pickup; carry: path / "
    "fallback[_hold|_raise] (MODE 2), greedy[_hold|_raise] (MODE 0/1), complete; other:<fine_category>. pre / post = "
    "cells (a vetoed decision whose fix step was nevertheless taken - post the fix's cell with its tier - is labelled "
    "approach_a / retreat_b: the label is the step TAKEN; veto says what the model's guard said); target = "
    "post-refresh target (approach) or exit_target (carry); digest = sha1[:16] of sorted burning + "
    "sorted active-smoke cells read at the decision; st_pre / st_post = status; tier = _last_move_tier after the "
    "advance (stale when the advance did not set it); mt = _move_toward calls; rb_call = _mark_route_blocked calls; "
    "rb_set = those that set route_blocked; trig = the survival trigger held (approach); zrb = today's raise "
    "predicate (instrument's own BFS); today = TODAY's shadow [kind, cell, tier, raise] (approach: greedy; survival: "
    "survival, or fallback when _survival_choice would not move; carry: path = MODE 2 exit_leg_first_step, else greedy "
    "/ hold / raise); fa / fb = fix (a) / fix (b) cell from the pure methods BEFORE the advance (None where not "
    "evaluated); fbB = the on-route clean neighbours with the smallest clean distance; fc = always None (no fix (c) in "
    "this round; the column keeps v2's indices); acted = letters of the fixes whose UNGUARDED shadow ACTED (22.8.2: a "
    "= fa not None and != today's cell; b = fb not None on a survival step); dc / dcx / df / dm / dr / gesc / cls_* / "
    "fd_* / c1_* / dcb as v2; fix_ms = ms in fix code during the advance (pure choices, _fix_move and the guard) when "
    "the model called it; inst_ms = the instrument's ms for the row. NEW: gA / gB = the INSTRUMENT's guard verdict "
    "(movement_paths.stranding_guard on the decision board) for fa / fb when that fix would act, else None; veto = "
    "letters of the fixes whose live step the MODEL's guard vetoed in this advance; acted_g = the letters of acted "
    "whose instrument verdict admits (what the fixes do in arm G). None = not applicable / infinite."
)
MVG_SCHEMA = (
    "guard rows (cols GUARD_COLS): one per decision at which fix (a) or (b) WOULD act (the pure choice returns a cell n "
    "!= today's), in EVERY arm: step, unit, victim, kind a|b, u = the unit's cell, n = the fix's cell, v = target_pos "
    "after the refresh (the bound victim's cell), today = today's cell (a: _greedy_choice; b: _survival_choice, or the "
    "fallback greedy cell when survival would not move; None = today's step does not move), today_kind (greedy | "
    "survival | fallback), today_tier (the tier today's _move_toward writes; None for survival), today_raise (today's "
    "raise predicate), c = c_n (None = infinite), T_v = FAE T at v (None = infinite), admit = the INSTRUMENT's verdict "
    "(movement_paths.stranding_guard on the decision board; equal to the frozen _mvg_guard_diag.guard by test T-G7; "
    "None if it raised), model_admit = the MODEL's verdict (the return of _stranding_guard_verdict called inside "
    "_guarded) or None when the model did not evaluate the guard (fix off: arm 0; guard off: arm N; a knocked-out "
    "choice), model_verdict = [admit, c, T_v] of that call, model_cell = the cell it was evaluated on, took = 'fix' if "
    "post == n and _last_move_tier after the advance is the fix's tier (7 / 10), else 'today', post = the unit's cell "
    "after the advance, tier = _last_move_tier after it, raise = _mark_route_blocked was called in the advance, "
    "pre_writes / pred_writes / post_writes (kind b; else None) = the _idle_retreat_* state [origin, steps, stalled, "
    "last_cell] before the advance / as a PURE replica of today's _survival_move would leave it (survival_writes) / "
    "after the advance, ms_guard = the model's guard call ms (None if not evaluated), ms_inst = the instrument's guard "
    "ms, row = the index of the advance's d['mv'] row. replica: the survival_writes replica checked at EVERY advance "
    "with the survival trigger: where today's _survival_move ran (branch retreat / retreat_fb / retreat_b_veto) the "
    "predicted writes must equal the unit's post-advance state (checked / mismatch), where fix (b)'s step ran "
    "(retreat_b) the state must be unchanged (fix_checked / fix_mismatch), and the replica's destination must be "
    "today's survival cell (_survival_choice; cell_checked / cell_mismatch). timing: guard_ms = every model guard call "
    "(ms), guard_calls, inst_guard_ms = every instrument guard evaluation (ms)."
)
UD_SCHEMA = (
    "ud_probe v2's kick schema, unchanged: kicks (W, F, index, qualifies, u1, rec, d, ms, div_shadow, nB, z4, z4_ok, "
    "acc, index_wb, u1_wb, div_shadow_head, bound, n_cmd, attempts, divergent, divergent_head, ms_model, triage, i, "
    "step, phase, site, switch, inst_ms) - the U1 shadow computed by the instrument-side replicas and the frozen U1 "
    "copy (no U1 in the model: switch always False, ms_model / triage always None); decisions, fates, cmd_ctx, rel_ctx "
    "and shadow_mismatch as v2. shadow_mismatch movement rows: [step, unit, 'a' | 'b', text, branch, cell, taken] - "
    "'shadow acted, model did not' (the guarded shadow expected the fix's step), 'guard vetoes (instrument), model did "
    "not take today's step', 'model acted, shadow did not', 'guard evaluated on a cell other than the shadow's', "
    "'model guard verdict != instrument verdict' (Zg-1)."
)

_MISSING = object()


# ---------------------------------------------------------------------------------------------- pure helpers
def _bfs(source, grid, blocked):
    """The instrument's own 4-connected BFS from `source` over in-bounds cells not in `blocked` (_dp_probe)."""
    start = (int(source[0]), int(source[1]))
    dist = {start: 0}
    queue = deque([start])
    while queue:
        cx, cy = queue.popleft()
        for ox, oy in _N4:
            cell = (cx + ox, cy + oy)
            if cell in dist or cell in blocked or grid.out_of_bounds(cell):
                continue
            dist[cell] = dist[(cx, cy)] + 1
            queue.append(cell)
    return dist


def _at(dist, cell, blocked):
    """d at a unit's cell, the unit's own cell exempt like the route test's source (_dp_probe)."""
    cell = (int(cell[0]), int(cell[1]))
    if cell in dist:
        return dist[cell]
    if cell not in blocked:
        return None
    near = [dist[(cell[0] + ox, cell[1] + oy)] for ox, oy in _N4 if (cell[0] + ox, cell[1] + oy) in dist]
    return min(near) + 1 if near else None


def _cell(pos):
    return None if pos is None else (int(pos[0]), int(pos[1]))


def _jc(cell):
    return None if cell is None else [int(cell[0]), int(cell[1])]


def _fin(value):
    value = float(value)
    return None if math.isinf(value) else value


def _is_boundary(cell, oob):
    return any(oob((cell[0] + ox, cell[1] + oy)) for ox, oy in _N4)


def _unclean(burning, smoky, oob):
    """Burning, 4-adjacent to burning (in bounds) or active-smoke cells: the complement of CLEAN in the grid."""
    out = set()
    for c in burning:
        out.add(c)
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if not oob(n):
                out.add(n)
    out.update(smoky)
    return out


def _cls(cell, burning, smoky):
    if cell in burning:
        return "B"
    if any((cell[0] + ox, cell[1] + oy) in burning for ox, oy in _N4):
        return "A"
    if cell in smoky:
        return "S"
    return "C"


def _mfd(cell, burning):
    if not burning:
        return 999
    return min(abs(cell[0] - x) + abs(cell[1] - y) for x, y in burning)


def _digest(burning, smoky):
    h = hashlib.sha1()
    h.update(repr(sorted(burning)).encode())
    h.update(b"|")
    h.update(repr(sorted(smoky)).encode())
    return h.hexdigest()[:16]


def _clean_field(target, unclean, oob):
    """(D, has_exit): BFS over CLEAN cells from `target` (which must be clean, else empty), and whether the region
    touches the grid boundary (G-ESC). The instrument's own code."""
    if oob(target) or target in unclean:
        return {}, False
    dist = {target: 0}
    queue = deque([target])
    has_exit = False
    while queue:
        c = queue.popleft()
        if not has_exit and _is_boundary(c, oob):
            has_exit = True
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if n in dist or oob(n) or n in unclean:
                continue
            dist[n] = dist[c] + 1
            queue.append(n)
    return dist, has_exit


def _dist_boundary(start, passable, oob):
    """Hops from `start` (exempt) to the nearest passable boundary cell; 0 if start is a boundary cell; None if none."""
    if _is_boundary(start, oob):
        return 0
    dist = {start: 0}
    queue = deque([start])
    while queue:
        c = queue.popleft()
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if n in dist or oob(n) or not passable(n):
                continue
            dist[n] = dist[c] + 1
            if _is_boundary(n, oob):
                return dist[n]
            queue.append(n)
    return None


def _c1_cost(start, burning, smoky, oob):
    """[fire-adjacent cells entered, smoky cells entered, length] of a least-exposure path (lexicographic) from
    `start` (exempt) over non-burning cells to a non-burning boundary cell; [0, 0, 0] on a boundary cell; None when no
    such cell is reachable (a pocket). The instrument's own Dijkstra."""
    if _is_boundary(start, oob):
        return [0, 0, 0]
    best = {start: (0, 0, 0)}
    heap = [(0, 0, 0, start)]
    while heap:
        fa, sm, ln, c = heapq.heappop(heap)
        if best.get(c) != (fa, sm, ln):
            continue
        if c != start and _is_boundary(c, oob):
            return [fa, sm, ln]
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if oob(n) or n in burning:
                continue
            adj = any((n[0] + px, n[1] + py) in burning for px, py in _N4)
            key = (fa + (1 if adj else 0), sm + (1 if n in smoky else 0), ln + 1)
            if n not in best or key < best[n]:
                best[n] = key
                heapq.heappush(heap, (key[0], key[1], key[2], n))
    return None


def _greedy_tier(cell, target, chosen, burning, smoky):
    """The tier _move_toward reports for `chosen` (exact: the first clean-ish pool holding it, else 4)."""
    if chosen is None:
        return None
    before = abs(cell[0] - target[0]) + abs(cell[1] - target[1])
    after = abs(chosen[0] - target[0]) + abs(chosen[1] - target[1])
    adj = any((chosen[0] + ox, chosen[1] + oy) in burning for ox, oy in _N4)
    if not adj and chosen not in smoky:
        return 1 if after < before else 2 if after == before else 3
    return 4


def _safe_hops(src, x_size, y_size, unclean, t_grid):
    """The instrument's own time-expanded clean BFS (8.2), for Z4's independent recomputation."""
    def inb(c):
        return 0 <= c[0] < x_size and 0 <= c[1] < y_size

    def tstar(c):
        best = float(t_grid[c[0], c[1]])
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if inb(n):
                best = min(best, float(t_grid[n[0], n[1]]))
        return best

    hops = {src: 0}
    queue = deque([src])
    while queue:
        c = queue.popleft()
        k = hops[c] + 1
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if n in hops or not inb(n) or n in unclean:
                continue
            if not tstar(n) > k:
                continue
            hops[n] = k
            queue.append(n)
    return hops


def load_u1_shadow(path=U1_SHADOW):
    """(module, sha256 of the file's bytes): the frozen instrument-only copy of urgency_dispatch.py, loaded BY PATH under
    the module name "mvg_u1_shadow" (never as src_extension.planning.urgency_dispatch, never from the repo). It imports
    only src_extension.planning.fire_arrival_estimate (the repo's FAE, the estimator U1 read)."""
    with open(path, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    spec = importlib.util.spec_from_file_location(U1_SHADOW_MODULE, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[U1_SHADOW_MODULE] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(U1_SHADOW_MODULE, None)
        raise
    return module, sha


def shadow_funcs(ag):
    """The Firefighter class functions the shadows call, captured BEFORE any wrap (pure methods)."""
    F = ag.Firefighter
    return {"needs": F._needs_immediate_survival_retreat, "greedy": F._greedy_choice, "survival": F._survival_choice,
            "fix_a": F._approach_path_choice, "fix_b": F._retreat_on_route_choice,
            "on_boundary": F._on_grid_boundary}


def guard_inputs(model, cfv):
    """(wind vector, x_size, y_size) exactly as the guard's 1d.2.2 reads them: cfv.wind_vector_from_direction of the
    model's wind label (U1's view, WM:3106-3110) and the grid's extents."""
    label = getattr(getattr(model, "wind", None), "wind_direction", None)
    return cfv.wind_vector_from_direction(label), int(model.grid.width), int(model.grid.height)


def guard_shadow(gfn, u, n, v, burning, smoky, wind, x_size, y_size):
    """The INSTRUMENT's guard verdict (1d.2.2) at one decision: [admit, c_n, T_v (None = infinite), ms]. gfn is
    movement_paths.stranding_guard (pure; T-G7 pins it to the frozen _mvg_guard_diag.guard)."""
    t0 = time.perf_counter()
    admit, c_n, t_v = gfn(u, n, v, burning, smoky, wind, x_size, y_size)
    ms = (time.perf_counter() - t0) * 1000.0
    return [bool(admit), None if c_n is None else int(c_n), _fin(t_v), ms]


def writes_of(unit):
    """The unit's _idle_retreat_* state as [origin, steps, stalled, last_cell] (JSON form), read with the model's own
    defaults (getattr ..., None / 0 / False / None)."""
    origin = getattr(unit, "_idle_retreat_origin", None)
    last = getattr(unit, "_idle_retreat_last_cell", None)
    return [_jc(origin), int(getattr(unit, "_idle_retreat_steps", 0) or 0),
            bool(getattr(unit, "_idle_retreat_stalled", False)), _jc(last)]


def survival_writes(unit, ag):
    """PURE replica of Firefighter._survival_move's _idle_retreat_* WRITES (Zg-2 for (b), 1d.8 (5)): returns
    (writes, cell) - the [origin, steps, stalled, last_cell] state today's _survival_move would leave, and the cell it
    would step to (None = it would not move; for an assigned unit its _assigned_one_step_retreat counts as a move).

    HOW IT IS PURE: the unit's four _idle_retreat_* values are COPIED into a local dict `st`, and _survival_move's
    control flow (agents.py, the method and its _revalidate_idle_retreat_stall / _assigned_one_step_retreat callees) is
    re-run against `st` - every write of the method becomes a write to `st`; every move becomes the returned cell. The
    only model calls are the unit's READ helpers (_fire_cells, _cell_is_ideal_idle_standoff, _retreat_candidates,
    _pick_improving_retreat, _min_fire_distance, _firefighter_cell_risk, _cell_meets_required_idle_safety,
    _neighbor_cells, _cell_contains_active_fire, _cell_adjacent_to_fire, _cell_has_active_smoke), none of which moves
    or writes. The post-move standoff tests read only Fire agents, which the unit's own move does not change, so they
    are evaluated on the destination before any move. It is checked (1) by the in-run purity guard around every shadow
    (unit __dict__, model attributes, RNG states), (2) by _mvg_probe_check.py synthetic (a deep snapshot of every agent,
    the model to depth 3, the grid and the RNGs around the shadow on hand-built boards, with positive controls), and
    (3) against the model itself on every advance where today's _survival_move ran (d["mvg"]["replica"])."""
    st = {"origin": getattr(unit, "_idle_retreat_origin", None),
          "steps": getattr(unit, "_idle_retreat_steps", 0),
          "stalled": getattr(unit, "_idle_retreat_stalled", False),
          "last_cell": getattr(unit, "_idle_retreat_last_cell", None)}

    def out(cell):
        return [_jc(st["origin"]), int(st["steps"] or 0), bool(st["stalled"]), _jc(st["last_cell"])], _cell(cell)

    if unit.pos is None:
        return out(None)
    cell = (int(unit.pos[0]), int(unit.pos[1]))
    fire_cells = unit._fire_cells()
    max_cells = ag.IDLE_RETREAT_MAX_CELLS
    has_target = bool(unit.target_pos)

    def reset():
        st.update(origin=None, steps=0, stalled=False, last_cell=None)

    def one_step():
        # _assigned_one_step_retreat's destination (it moves, and returns True, iff this is not None)
        best = None
        best_score = -1
        for ncell in unit._neighbor_cells():
            if unit._cell_contains_active_fire(ncell):
                continue
            if unit._cell_adjacent_to_fire(ncell):
                continue
            if unit._cell_has_active_smoke(ncell):
                continue
            score = unit._min_fire_distance(ncell, fire_cells)
            if score > best_score:
                best_score = score
                best = ncell
        return best if best is not None and best != cell else None

    def key(c):
        return (int(c["dist"]), -int(c["risk"]))

    if unit._cell_is_ideal_idle_standoff(cell, fire_cells):
        reset()
        return out(None)
    origin = st["origin"]
    if origin is None or (not has_target and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) > max_cells):
        st.update(origin=cell, steps=0, stalled=False, last_cell=None)
        origin = cell
    if bool(st["stalled"]):
        if has_target:
            return out(one_step())
        # _revalidate_idle_retreat_stall
        current_dist = unit._min_fire_distance(cell, fire_cells)
        current_risk = unit._firefighter_cell_risk(cell)
        chosen = unit._pick_improving_retreat(
            unit._retreat_candidates(cell, origin, st["last_cell"], fire_cells, current_dist), current_dist,
            current_risk)
        if chosen is None:
            return out(None)
        steps = int(st["steps"] or 0)
        st.update(last_cell=cell, steps=steps + 1, stalled=False)
        return out(chosen["cell"])
    steps = int(st["steps"] or 0)
    at_cap = steps >= max_cells
    current_dist = unit._min_fire_distance(cell, fire_cells)
    current_risk = unit._firefighter_cell_risk(cell)
    candidates = unit._retreat_candidates(cell, origin, st["last_cell"], fire_cells, current_dist)
    if not candidates:
        if has_target:
            step = one_step()
            if step is not None:
                return out(step)
        st["stalled"] = True
        return out(None)
    chosen = None
    if not at_cap:
        chosen = unit._pick_improving_retreat(candidates, current_dist, current_risk)
        if chosen is None:
            chosen = max(candidates, key=key)
            if not has_target:
                st["stalled"] = True
    else:
        required = [c for c in candidates if c["required"]]
        if required:
            chosen = max(required, key=key)
            if not has_target:
                reset()
        else:
            chosen = max(candidates, key=key)
            if not has_target:
                st["stalled"] = True
    if chosen is None:
        if has_target:
            step = one_step()
            if step is not None:
                return out(step)
        st["stalled"] = True
        return out(None)
    target = chosen["cell"]
    if target == cell:
        if has_target:
            step = one_step()
            if step is not None:
                return out(step)
        st["stalled"] = True
        return out(None)
    st["last_cell"] = cell
    st["steps"] = steps + 1
    if unit._cell_is_ideal_idle_standoff(target, fire_cells):
        reset()
    elif unit._cell_meets_required_idle_safety(target, fire_cells) and (
            (at_cap or st["stalled"]) and not has_target):
        reset()
    return out(target)


def mv_shadow(unit, model, ag, fn, gfn=None, cfv=None):
    """PURE pre-advance shadow for one unit (after its target refresh). None = no row (idle / off-grid / dead).
    v2's shadow without fix (c), plus, at every decision where fix (a) or (b) would act, the instrument's guard verdict
    (S["ga"] / S["gb"] = [admit, c, T_v, ms], None where the fix would not act or gfn is None), and on every survival
    step the survival_writes replica (S["sv"] = {"pre", "pred", "cell"})."""
    pos = getattr(unit, "pos", None)
    if pos is None or getattr(unit, "dead", False):
        return None
    exiting = bool(getattr(unit, "exiting", False))
    target = getattr(unit, "target_pos", None)
    if exiting:
        leg = "carry"
    elif target:
        leg = "approach"
    else:
        return None
    cell = _cell(pos)
    grid = model.grid
    oob = grid.out_of_bounds
    burning, smoky = ag.fire_board_sets(model)
    S = {"leg": leg, "pre": cell, "burning": burning, "smoky": smoky, "digest": _digest(burning, smoky),
         "cls_pre": _cls(cell, burning, smoky), "fd_pre": _mfd(cell, burning), "kind": None, "target": None,
         "trig": None, "zrb": None, "today": None, "fa": None, "fb": None, "fbB": None, "fc": None, "acted": "",
         "dc": None, "dcx": None, "df": None, "dm": None, "dr": None, "gesc": None, "c1_pre": None,
         "ga": None, "gb": None, "sv": None, "gerr": None}
    unclean = _unclean(burning, smoky, oob)
    # dcb (v2, R3 D-16): clean distance to the boundary on EVERY row, the unit's own cell exempt
    S["dcb"] = _dist_boundary(cell, lambda c: c not in unclean, oob)
    if leg == "approach":
        tgt = _cell(target)
        S["target"] = tgt
        dm = abs(cell[0] - tgt[0]) + abs(cell[1] - tgt[1])
        # advance() tests the survival trigger BEFORE the pickup (a unit on its victim's unclean cell retreats)
        trig = bool(fn["needs"](unit))
        if cell == tgt and not trig:
            S.update(kind="pickup", trig=False, dm=0, df=0, dr=0)
            return S
        field, has_exit = _clean_field(tgt, unclean, oob)
        dc = field.get(cell)
        if dc is None:
            near = [field[(cell[0] + ox, cell[1] + oy)] for ox, oy in _N4 if (cell[0] + ox, cell[1] + oy) in field]
            dcx = min(near) + 1 if near else None
        else:
            dcx = dc
        df = _at(_bfs(tgt, grid, burning), cell, burning)
        nbrs = [(cell[0] + ox, cell[1] + oy) for ox, oy in _N4 if not oob((cell[0] + ox, cell[1] + oy))]
        zrb = (not any(n not in burning for n in nbrs)) or df is None
        g = fn["greedy"](unit, tgt, burning, smoky)
        g = _cell(g)
        gt = _greedy_tier(cell, tgt, g, burning, smoky)
        if trig:
            r = _cell(fn["survival"](unit))
            b = _cell(fn["fix_b"](unit))
            B = None
            if field and has_exit:
                fin = [n for n in nbrs if n not in unclean and n in field]
                if fin:
                    low = min(field[n] for n in fin)
                    B = sorted(n for n in fin if field[n] == low)
                else:
                    B = []
            today = ["survival", r, None, False] if r is not None else ["fallback", g, gt, bool(zrb)]
            S.update(kind="retreat", fb=b, fbB=B, acted="b" if b is not None else "")
            pred, pred_cell = survival_writes(unit, ag)
            S["sv"] = {"pre": writes_of(unit), "pred": pred, "cell": _jc(pred_cell)}
        else:
            a = _cell(fn["fix_a"](unit))
            today = ["greedy", g, gt, bool(zrb)]
            S.update(kind="approach", fa=a, acted="a" if (a is not None and a != g) else "")
        S.update(trig=trig, zrb=bool(zrb), today=today, dc=dc, dcx=dcx, df=df, dm=dm, gesc=bool(has_exit),
                 dr=dcx if dcx is not None else df if df is not None else dm)
        if gfn is not None and S["acted"]:
            f = S["acted"]
            n = S["fa"] if f == "a" else S["fb"]
            try:
                wind, xs, ys = guard_inputs(model, cfv)
                S["g" + f] = guard_shadow(gfn, cell, n, tgt, burning, smoky, wind, xs, ys)
            except Exception as exc:  # recorded as a guard error; the verdict stays None
                S["gerr"] = ("guard_shadow: %r" % (exc,))[:300]
        return S
    # carry (no fix (c) in this round: today's carry step only)
    et = getattr(unit, "exit_target", None)
    S["target"] = _cell(et)
    dm = min(cell[0], int(grid.width) - 1 - cell[0], cell[1], int(grid.height) - 1 - cell[1])
    S["dm"] = dm
    if et is None:
        S.update(kind="noexit", dr=dm)
        return S
    mode = ag.ff_exit_leg_mode()
    if cell == S["target"] or (mode != 0 and _is_boundary(cell, oob)):
        S.update(kind="complete", dr=0)
        return S
    dc = S["dcb"]   # the same call: _dist_boundary(cell, clean, oob), start exempt
    df = _dist_boundary(cell, lambda c: c not in burning, oob)

    def greedy_today():
        g = _cell(fn["greedy"](unit, S["target"], burning, smoky))
        if g is None:
            if ag.ff_exit_leg_hold():
                return ["hold", cell, 6, False]
            return ["raise", cell, None, True]
        return ["greedy", g, _greedy_tier(cell, S["target"], g, burning, smoky), False]

    if mode == 2:
        first = ag.exit_leg_first_step(cell, lambda c: c not in unclean, lambda c: fn["on_boundary"](unit, c), oob)
        today = ["path", _cell(first), 5, False] if first is not None else greedy_today()
    else:
        today = greedy_today()
    S.update(kind="carry", today=today, dc=dc, dcx=dc, df=df, gesc=dc is not None,
             c1_pre=_c1_cost(cell, burning, smoky, oob), dr=dc if dc is not None else df if df is not None else dm)
    return S


def waiting_replica(model, managed, markers):
    """INSTRUMENT-SIDE replica of the urgency round's WildFireModel._urgency_waiting (urgency:wildfire_model.py at
    5dba5bcb; = today's kick loop's three predicates, in today's index order): W."""
    out = []
    for vid, state in managed.items():
        marker = markers.get(vid)
        if not model._victim_needs_rescue(vid, marker):
            continue
        confirmed = bool(getattr(state, "confirmed", False) if state is not None else False)
        ms = str(getattr(marker, "status", "") or "").strip().lower() if marker is not None else ""
        if not confirmed and ms != "confirmed":
            continue
        if model._find_active_firefighter_for_victim(vid, marker):
            continue
        out.append((vid, marker))
    return out


def view_replica(model, waiting, unit, ag, cfv):
    """INSTRUMENT-SIDE replica of the urgency round's WildFireModel._urgency_dispatch_view (urgency:wildfire_model.py
    at 5dba5bcb, its 11.1 reads made AFTER W is built): each waiting victim's live cell, the free unit's cell, the true
    burning and active-smoke sets (agents.fire_board_sets), the wind vector (cfv.wind_vector_from_direction of the
    model's wind label) and the grid's extents."""
    burning, smoky = ag.fire_board_sets(model)
    cells = []
    for vid, marker in waiting:
        pos = getattr(marker, "pos", None)
        if pos is None:
            continue
        cells.append((vid, (int(pos[0]), int(pos[1]))))
    wind_label = getattr(getattr(model, "wind", None), "wind_direction", None)
    return {
        "waiting": cells,
        "unit_cell": (int(unit.pos[0]), int(unit.pos[1])),
        "burning": burning,
        "smoky": smoky,
        "wind": cfv.wind_vector_from_direction(wind_label),
        "x_size": int(model.grid.width),
        "y_size": int(model.grid.height),
    }


def decision_action(decision):
    """The action of a select_rescue_assignment result, parsed exactly as RescueExecutor.apply_physical_pairing_decision
    parses it: a dict's "action" (the planner's {"action": "none", ...}), else a RescueDecision's rescue_action;
    stripped and lower-cased."""
    if isinstance(decision, dict):
        return str(decision.get("action", "") or "").strip().lower()
    return str(getattr(decision, "rescue_action", "") or "").strip().lower()


def planner_accepts(model, select_fn, waiting):
    """{vid: bool} for every (vid, marker) of W: whether the planner call _dispatch_firefighter_to_victim makes for
    her - select_fn(model.get_rescue_operational_snapshot(), "initial", victim_id=str(vid or "")) - yields "assign".
    One fresh snapshot per victim, as the model takes one per call (before any bind the state is the same). PURE: the
    snapshot is the model's read-only planner view and select_rescue_assignment a pure function of it."""
    out = {}
    for vid, _marker in waiting:
        snapshot = model.get_rescue_operational_snapshot()
        out[str(vid)] = decision_action(select_fn(snapshot, "initial", victim_id=str(vid or ""))) == "assign"
    return out


def first_accepted(order, acc):
    """The first vid of `order` the planner accepts (acc True); None when there is none, or order / acc is None."""
    if order is None or acc is None:
        return None
    return next((v for v in order if acc.get(v)), None)


def kick_flags(K):
    """The v2 shadow flags of a kick record (pure, set in K) from its index / u1 / acc / qualifies:
    index_wb / u1_wb = the victim each order WOULD BIND (its first accepted victim); div_shadow (16.5's U1-divergent,
    in shadow) = qualifies and u1_wb != index_wb; div_shadow_head = v1's head-based value (u1[0] != index[0])."""
    K["index_wb"] = first_accepted(K.get("index"), K.get("acc"))
    K["u1_wb"] = first_accepted(K.get("u1"), K.get("acc"))
    K["div_shadow"] = bool(K.get("qualifies") and K["u1_wb"] != K["index_wb"])
    K["div_shadow_head"] = bool(K.get("qualifies") and K.get("u1") and K.get("index")
                                and K["u1"][0] != K["index"][0])
    return K


def bind_flags(K, bound):
    """The v2 bind flags of a kick record (pure, set in K): divergent = qualifies and the victim the kick actually
    bound first (None if none) != index_wb; divergent_head = v1's value (bound[0][0] != index[0])."""
    first = bound[0][0] if bound else None
    K["divergent"] = bool(K.get("qualifies") and first != K.get("index_wb"))
    K["divergent_head"] = bool(K.get("qualifies") and bound and K.get("index") and bound[0][0] != K["index"][0])
    return K


def kick_shadow(model, ag, ud, fae, order_fn, select_fn=None, cfv=None):
    """PURE kick record: W (today's predicates, waiting_replica), F, qualifies (U1's exact predicate), the U1 order and
    per-victim [T, c, promotable] from a pure urgency_order call of the frozen U1 copy (whenever |F| = 1, |W| >= 1 and
    a cell burns), with the planner's acceptance of every W victim (acc, v2; when select_fn is given) and the flags of
    kick_flags, the non-burning d from each waiting victim to each free unit, and at a qualifying kick Z4's independent
    recomputation. The view is view_replica (U1 is not in the model)."""
    K = {"W": None, "F": None, "index": None, "qualifies": False, "u1": None, "rec": {}, "d": {}, "ms": None,
         "div_shadow": False, "nB": None, "z4": None, "z4_ok": None, "acc": None, "index_wb": None, "u1_wb": None,
         "div_shadow_head": False}
    managed = getattr(model, "managed_victims", None)
    markers = getattr(model, "victim_marker_agents", None)
    if not isinstance(managed, dict) or not isinstance(markers, dict):
        return K
    waiting = waiting_replica(model, managed, markers)
    units = getattr(model, "firefighter_marker_agents", None) or {}
    free = [(str(fid), u) for fid, u in units.items() if model._firefighter_available_for_dispatch(u)]
    K["W"] = [[str(vid), _jc(_cell(getattr(mk, "pos", None)))] for vid, mk in waiting]
    K["F"] = [[fid, _jc(_cell(getattr(u, "pos", None)))] for fid, u in free]
    K["index"] = [str(vid) for vid, _mk in waiting]
    view = None
    if len(free) == 1 and len(waiting) >= 1:
        view = view_replica(model, waiting, free[0][1], ag, cfv)
    if view is not None and len(waiting) >= 2:
        K["qualifies"] = bool(ud.qualifies(len(view["waiting"]), len(free), bool(view["burning"]))
                              and len(view["waiting"]) == len(waiting))
    burning = view["burning"] if view is not None else ag.fire_board_sets(model)[0]
    K["nB"] = len(burning)
    if view is not None and view["burning"] and view["waiting"]:
        t0 = time.perf_counter()
        ordered, records = order_fn(view["waiting"], view["unit_cell"], view["burning"], view["smoky"],
                                    view["wind"], view["x_size"], view["y_size"])
        K["ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
        K["u1"] = [str(v) for v in ordered]
        K["rec"] = {str(v): [_fin(r["T"]), r["c"], bool(r["promotable"])] for v, r in records.items()}
        if select_fn is not None:
            K["acc"] = planner_accepts(model, select_fn, waiting)
    kick_flags(K)
    grid = model.grid
    for vid, mk in waiting:
        if getattr(mk, "pos", None) is None:
            continue
        dmap = _bfs(mk.pos, grid, burning)
        K["d"][str(vid)] = {fid: _at(dmap, u.pos, burning) for fid, u in free if getattr(u, "pos", None) is not None}
    if K["qualifies"]:
        xs, ys = int(view["x_size"]), int(view["y_size"])
        t_grid = fae.arrival_time(xs, ys, list(view["burning"]), view["wind"], fae.FrontPriorityParams())
        oob = grid.out_of_bounds
        unclean = _unclean(set(view["burning"]), set(view["smoky"]), oob)
        hops = _safe_hops(tuple(view["unit_cell"]), xs, ys, unclean, t_grid)
        z4 = {}
        for vid, vc in view["waiting"]:
            vc = (int(vc[0]), int(vc[1]))
            t_v = float(t_grid[vc[0], vc[1]])
            c = None if vc in unclean else hops.get(vc)
            z4[str(vid)] = [_fin(t_v), c, bool(c is not None and c + 1 <= t_v)]
        K["z4"] = z4
        K["z4_ok"] = all(K["rec"].get(v) == z for v, z in z4.items())
    return K


def rng_states(ag, model):
    """A cheap fingerprint of every RNG a shadow could touch (agents.random, model.random, numpy's global)."""
    out = []
    for r in (getattr(ag, "random", None), getattr(model, "random", None)):
        try:
            out.append(r.getstate())
        except Exception:
            out.append(None)
    try:
        import numpy as np
        st = np.random.get_state()
        out.append((st[0], st[1].tobytes(), st[2], st[3], st[4]))
    except Exception:
        out.append(None)
    return out


def dict_changed(before, after):
    """Keys whose value is no longer the same object (or equal value) - a shallow purity check."""
    bad = sorted(set(before) ^ set(after))
    for k, v in before.items():
        if k not in after:
            continue
        w = after[k]
        if w is v:
            continue
        try:
            if bool(w == v):
                continue
        except Exception:
            pass
        bad.append(k)
    return bad


# ------------------------------------------------------------------------------------------------- recorders
def install(ag, cfv, wf, amod, gen, fae, udm, mpm=None):
    """Install every recorder (class-level wraps; call BEFORE the model is built). udm = the frozen U1 copy (or None:
    no kick shadow), mpm = src_extension.planning.movement_paths (the guard's pure function; None: no guard shadow).
    Returns the record dict `rec` that sections() turns into d["dp"], d["ud"], d["mv"], d["mv_events"], d["mvg"]."""
    WM = wf.WildFireModel
    FF = ag.Firefighter
    rec = {
        # _dp_probe v2's recorders
        "model": None, "phase": "init", "commands": [], "releases": [], "j_calls": [], "binders": [], "waiting": [],
        "waiting_custody": [], "m3a": [], "invariant": [], "m8": {}, "m9": [], "m9_open": [], "last_release": {},
        "errors": [], "inst_ms": 0.0, "j_detail": [], "j_timing": [], "in_j": False, "j_phase": None,
        # ud (v2)
        "ud_errors": [], "ud_ms": 0.0, "ctx": [], "inst": 0, "site": [], "adv": None, "kicks": [],
        "decisions": [], "burn_watch": [], "cmd_ctx": [], "rel_ctx": [], "mv_rows": [], "mv_events": [],
        "mismatch": [], "fix_calls": {"a": [], "b": [], "g": []}, "fix_depth": 0,
        "u1_shadow_ms": 0.0, "mv_ms": 0.0,
        "kick_ms": 0.0, "fid": {}, "vid": {}, "pickups": {}, "completes": {}, "kick_att": [],
        # mvg
        "mvg_errors": [], "guard_rows": [], "guard_ms": [], "inst_guard_ms": [],
        "replica": {"checked": 0, "mismatch": [], "fix_checked": 0, "fix_mismatch": [], "cell_checked": 0,
                    "cell_mismatch": []},
    }
    joint_on = getattr(ag, "dispatch_joint", None) or (lambda: False)
    fn = shadow_funcs(ag)
    gfn = getattr(mpm, "stranding_guard", None) if mpm is not None else None
    o_uorder = getattr(udm, "urgency_order", None) if udm is not None else None
    fix_tier = {"a": getattr(ag, "APPROACH_PATH_TIER", 7), "b": getattr(ag, "RETREAT_ON_ROUTE_TIER", 10)}
    # v2: the planner function _dispatch_firefighter_to_victim calls, imported the way wildfire_model imports it - the
    # rescue_planner module's own function, never wildfire_model's module global (a harness in the chain rebinds that
    # global to a recorder; a shadow call through it would add records to the harness)
    try:
        from src_extension.planning.rescue_planner import select_rescue_assignment as o_select
    except Exception as exc:  # recorded; acc stays None
        o_select = None
        rec["ud_errors"].append(("install_select: %r" % (exc,))[:300])
    sw_fn = {"a": getattr(ag, "ff_approach_path", lambda: False),
             "b": getattr(ag, "ff_retreat_keep_approach", lambda: False),
             "g": getattr(ag, "ff_fix_stranding_guard", lambda: False)}

    def err(where, exc):
        if len(rec["errors"]) < 30:
            rec["errors"].append(f"{where}: {exc!r}"[:240])

    def uerr(where, exc):
        if len(rec["ud_errors"]) < 60:
            rec["ud_errors"].append(f"{where}: {exc!r}"[:300])

    def gerr(where, exc):
        if len(rec["mvg_errors"]) < 60:
            rec["mvg_errors"].append(f"{where}: {exc!r}"[:300])

    def step_of(m):
        return int(getattr(m, "evaluation_timesteps_counter", 0) or 0)

    def burning_cells(m):
        cells = set()
        for a in m.schedule.agents:
            if type(a) is ag.Fire and a.pos is not None and a.is_burning():
                cells.add((int(a.pos[0]), int(a.pos[1])))
        return cells

    def living_units(m):
        out = {}
        for fid, fm in (getattr(m, "firefighter_marker_agents", None) or {}).items():
            if getattr(fm, "dead", False) or str(getattr(fm, "status", "") or "").lower() == "dead":
                continue
            out[str(fid)] = fm
        return out

    def needy(m, vid, marker):
        state = (getattr(m, "managed_victims", None) or {}).get(vid)
        ms = str(getattr(marker, "status", "") or "").lower()
        ss = str(getattr(state, "status", "") or "").lower() if state is not None else ""
        if state is None or getattr(marker, "pos", None) is None:
            return False
        if getattr(state, "rescued", False) or "rescued" in (ms, ss) or "dead" in (ms, ss):
            return False
        if getattr(state, "cancelled", False) or ms == "cancelled":
            return False
        if getattr(state, "unreachable", False) or ms == "unreachable":
            return False
        return True

    def fid_of(m, unit):
        key = rec["fid"].get(id(unit))
        if key is None:
            for fid, fm in (getattr(m, "firefighter_marker_agents", None) or {}).items():
                rec["fid"][id(fm)] = str(fid)
            key = rec["fid"].get(id(unit), str(getattr(unit, "unit_id", "?")))
        return key

    def vid_of(m, marker):
        if marker is None:
            return None
        key = rec["vid"].get(id(marker))
        if key is None:
            for vid, mk in (getattr(m, "victim_marker_agents", None) or {}).items():
                rec["vid"][id(mk)] = str(vid)
            key = rec["vid"].get(id(marker), "?")
        return key

    # ================================================================== _dp_probe v2 recorders (unchanged meaning)
    am_cls = None
    for obj in vars(amod).values():
        if isinstance(obj, type) and hasattr(obj, "_run_post_move_cycle") and hasattr(obj, "_run_pre_move_cycle"):
            am_cls = obj
            break
    if am_cls is not None:
        o_pre, o_post = am_cls._run_pre_move_cycle, am_cls._run_post_move_cycle

        def pre_cycle(self, model, *a, **k):
            rec["phase"] = "pre"
            r = o_pre(self, model, *a, **k)
            rec["phase"] = "advance"
            return r

        def post_cycle(self, model, *a, **k):
            rec["phase"] = "post"
            r = o_post(self, model, *a, **k)
            rec["phase"] = "sweep"
            return r

        am_cls._run_pre_move_cycle = pre_cycle
        am_cls._run_post_move_cycle = post_cycle

    # ------------------------------------------------------------------ commands (the sink)
    o_apply = WM.apply_physical_rescue_command

    def apply_cmd(self, cmd):
        info = None
        extra = [None, None, None]
        t0 = time.perf_counter()
        try:
            action = str(cmd.action or "").strip().lower()
            vid = str(cmd.victim_id or "")
            fid = str(cmd.firefighter_id or "")
            # the record first: an observer error below can never drop it (R3 finding 1)
            info = [step_of(self), rec["phase"], action, vid, fid, str(cmd.reason or "")]
        except Exception as exc:
            err("apply_pre", exc)
        if info is not None and info[2] == "assign":
            try:
                vm = (cmd.metadata or {}).get("victim_marker") or (self.victim_marker_agents or {}).get(vid)
                fm = (self.firefighter_marker_agents or {}).get(fid)
                if vm is not None and fm is not None and vm.pos is not None and fm.pos is not None:
                    blocked = burning_cells(self)
                    d_route = _at(_bfs(vm.pos, self.grid, blocked), fm.pos, blocked)
                    extra = [d_route is not None, d_route,
                             abs(int(vm.pos[0]) - int(fm.pos[0])) + abs(int(vm.pos[1]) - int(fm.pos[1]))]
                    # K13 / M9: a unit freed by its first route_blocked raise on v, now bound to w != v
                    last = rec["last_release"].get(fid)
                    if joint_on() and last and last[0] == "o1" and last[1] != vid:
                        v_old = (self.victim_marker_agents or {}).get(last[1])
                        if v_old is not None and v_old.pos is not None and needy(self, last[1], v_old):
                            dmap = _bfs(v_old.pos, self.grid, blocked)
                            closed = all(_at(dmap, u.pos, blocked) is None
                                         for u in living_units(self).values() if u.pos is not None)
                            if closed:
                                entry = [step_of(self), fid, last[1], vid, []]
                                rec["m9"].append(entry)
                                rec["m9_open"].append((entry, step_of(self), rec["j_phase"] if rec["in_j"] else None))
            except Exception as exc:
                err("apply_obs", exc)
        spent = (time.perf_counter() - t0) * 1000.0
        rec["inst_ms"] += spent
        uctx = list(rec["ctx"])
        ok = o_apply(self, cmd)
        try:
            if info is not None:
                rec["commands"].append(info + [bool(ok)] + extra)
                rec["cmd_ctx"].append(uctx)
                if info[2] == "unassign" and ok:
                    kind = "o1" if "replacement" in info[5] and "blocked" in info[5] else "other"
                    rec["last_release"][info[4]] = (kind, info[3], info[0])
                elif info[2] == "assign" and ok:
                    rec["last_release"].pop(info[4], None)
        except Exception as exc:
            err("apply_post", exc)
        return ok

    WM.apply_physical_rescue_command = apply_cmd

    # ------------------------------------------------------------------ releases
    o_release = WM._release_other_claimants

    def release(self, *args, **kwargs):
        uctx = list(rec["ctx"])
        out = o_release(self, *args, **kwargs)
        try:
            vid = args[0] if args else kwargs.get("victim_id")
            keep = args[2] if len(args) > 2 else kwargs.get("keep_ff_id")
            reason = args[3] if len(args) > 3 else kwargs.get("reason")
            rec["releases"].append([step_of(self), rec["phase"], str(vid), str(keep or ""), str(reason or ""),
                                    str(kwargs.get("only_ff_id", "") or ""), list(out or [])])
            rec["rel_ctx"].append(uctx)
            for fid in out or []:
                rec["last_release"][str(fid)] = ("release", str(vid), step_of(self))
        except Exception as exc:
            err("release", exc)
        return out

    WM._release_other_claimants = release

    # ------------------------------------------------------------------ post-J sampling (no J here: the same instant)
    o_sync = WM._sync_firefighter_marker_status

    def sync(self, *a, **k):
        r = o_sync(self, *a, **k)
        t0 = time.perf_counter()
        try:
            step = step_of(self)
            units = living_units(self)
            vmarkers = getattr(self, "victim_marker_agents", None) or {}
            by_id = {id(mk): str(v) for v, mk in vmarkers.items()}
            bound: dict[str, list] = {}
            for fid, fm in units.items():
                rv = getattr(fm, "rescued_victim", None)
                if rv is not None and id(rv) in by_id:
                    bound.setdefault(by_id[id(rv)], []).append([fid, str(getattr(fm, "status", "") or "")])
            rec["binders"].append([step, sorted([v, sorted(b)] for v, b in bound.items())])
            free = [fid for fid, fm in units.items() if self._firefighter_available_for_dispatch(fm)]
            detected = gen._detected_victim_ids(self)
            ledger = getattr(self, "_dispatch_ledger", None) or {}
            rows = []
            custody_rows = []
            blocked = None
            for vid in sorted(detected):
                mk = vmarkers.get(vid)
                if mk is None or not needy(self, vid, mk):
                    continue
                if any(str(s).lower() != "route_blocked" for _, s in bound.get(vid, [])):
                    continue
                # custody (design 5.2, J's _dispatch_view): a binder exiting, rescue_completed or on the victim's cell
                cell = (int(mk.pos[0]), int(mk.pos[1]))
                if any(getattr(units[f], "exiting", False) or getattr(units[f], "rescue_completed", False)
                       or (units[f].pos is not None and (int(units[f].pos[0]), int(units[f].pos[1])) == cell)
                       for f, _ in bound.get(vid, [])):
                    custody_rows.append(vid)
                    continue
                if blocked is None:
                    blocked = burning_cells(self)
                dmap = _bfs(mk.pos, self.grid, blocked)
                cand = []
                for fid in free:
                    d = _at(dmap, units[fid].pos, blocked)
                    if d is not None:
                        cand.append([fid, d, int(ledger.get((fid, vid), 0) or 0)])
                rows.append([vid, cand])
            rec["waiting"].append([step, len(free), rows])
            if custody_rows:
                rec["waiting_custody"].append([step, custody_rows])
            if rows:
                cap = bool(getattr(ag, "dispatch_reassign", lambda: False)())
                held = {v for v, _ in rows if bound.get(v)}
                n_ok = sum(1 for fid in free
                           if any(not (cap and v in held and int(ledger.get((fid, v), 0) or 0) >= 2) for v, _ in rows))
                rec["m3a"].append([step, len(free), n_ok, sorted(free)])
            still = []
            for item in rec["m9_open"]:
                entry, bind_step, bind_phase = item
                if bind_phase == "post" and bind_step == step:
                    still.append(item)
                    continue
                vm = vmarkers.get(entry[2])
                if vm is None or vm.pos is None:
                    entry[4].append(None)
                else:
                    if blocked is None:
                        blocked = burning_cells(self)
                    dmap = _bfs(vm.pos, self.grid, blocked)
                    entry[4].append(any(_at(dmap, u.pos, blocked) is not None
                                        for u in units.values() if u.pos is not None))
                if len(entry[4]) < 3:
                    still.append(item)
            rec["m9_open"] = still
        except Exception as exc:
            err("sync", exc)
        rec["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        return r

    WM._sync_firefighter_marker_status = sync

    # ------------------------------------------------------------------ invariant capture
    o_inv = amod._check_rescue_assignment_invariant

    def inv(model):
        buf = io.StringIO()
        real = sys.stderr
        sys.stderr = buf
        try:
            o_inv(model)
        finally:
            sys.stderr = real
            text = buf.getvalue()
            if text:
                real.write(text)
                try:
                    step = step_of(model)
                    for line in text.splitlines():
                        if line.strip():
                            rec["invariant"].append([step, line.strip()[:300]])
                except Exception as exc:
                    err("inv", exc)

    amod._check_rescue_assignment_invariant = inv

    # ------------------------------------------------------------------ M8 at detection
    o_detect = WM._detect_victims_in_uav_radius

    def detect(self, *a, **k):
        try:
            before = set(gen._detected_victim_ids(self))
        except Exception as exc:
            err("detect_pre", exc)
            before = None
        r = o_detect(self, *a, **k)
        t0 = time.perf_counter()
        try:
            if before is not None:
                new = sorted(set(gen._detected_victim_ids(self)) - before)
                for vid in new:
                    mk = (self.victim_marker_agents or {}).get(vid)
                    if mk is None or mk.pos is None or vid in rec["m8"]:
                        continue
                    cell = (int(mk.pos[0]), int(mk.pos[1]))
                    blocked = burning_cells(self)
                    dmap = _bfs(cell, self.grid, blocked)
                    ds = [_at(dmap, u.pos, blocked) for u in living_units(self).values() if u.pos is not None]
                    ds = [d for d in ds if d is not None]
                    t_fire = None
                    try:
                        burning, _smoke = self._fix3b_true_fire()
                        wind = cfv.wind_vector_from_direction(getattr(getattr(self, "wind", None), "wind_direction", None))
                        grid_t = fae.arrival_time(int(self.grid.width), int(self.grid.height), set(burning), wind,
                                                  fae.front_priority_params())
                        value = float(grid_t[cell[0], cell[1]])
                        t_fire = None if value == float("inf") else round(value, 3)
                    except Exception as exc:
                        err("m8_tfire", exc)
                    rec["m8"][vid] = {"victim": vid, "detection_step": step_of(self), "cell": list(cell),
                                      "t_fire": t_fire, "min_d": min(ds) if ds else None,
                                      "first_burn_step": None, "death_step": None}
        except Exception as exc:
            err("detect", exc)
        rec["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        return r

    WM._detect_victims_in_uav_radius = detect

    # ------------------------------------------------------------------ per step: model capture, M8 + ud follow-up
    o_step = WM.step

    def step(self, *a, **k):
        rec["model"] = self
        r = o_step(self, *a, **k)
        t0 = time.perf_counter()
        try:
            if rec["m8"]:
                burning = None
                for vid, e in rec["m8"].items():
                    if e["first_burn_step"] is None:
                        if burning is None:
                            burning = burning_cells(self)
                        if tuple(e["cell"]) in burning:
                            e["first_burn_step"] = step_of(self)
                    if e["death_step"] is None:
                        mk = (self.victim_marker_agents or {}).get(vid)
                        state = (self.managed_victims or {}).get(vid)
                        ms = str(getattr(mk, "status", "") or "").lower() if mk is not None else ""
                        ss = str(getattr(state, "status", "") or "").lower() if state is not None else ""
                        if "dead" in (ms, ss):
                            e["death_step"] = step_of(self)
        except Exception as exc:
            err("step", exc)
        rec["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        t1 = time.perf_counter()
        try:
            if rec["burn_watch"]:
                burning = burning_cells(self)
                keep = []
                for dec in rec["burn_watch"]:
                    if tuple(dec["cell"]) in burning:
                        dec["first_burn"] = step_of(self)
                    else:
                        keep.append(dec)
                rec["burn_watch"] = keep
        except Exception as exc:
            uerr("step", exc)
        rec["ud_ms"] += (time.perf_counter() - t1) * 1000.0
        return r

    WM.step = step

    # ================================================================== ud: kicks (the U1 SHADOW, 16.5 / 22.9)
    def site_wrap(name, label):
        original = getattr(WM, name, None)
        if original is None:
            return

        def wrapper(self, *a, **k):
            rec["site"].append(label)
            try:
                return original(self, *a, **k)
            finally:
                rec["site"].pop()

        setattr(WM, name, wrapper)

    site_wrap("_process_pending_agent_removals", "K1")
    site_wrap("_revalidate_route_blocked_firefighters", "K2")

    o_kick = WM._try_dispatch_unresolved_confirmed_victims

    def guard_state(m):
        """The kick purity guard's reading: the model's attributes (shallow: the same names, the same objects), the
        RNG states, and the __dict__ of every agent / state object a kick shadow reads (firefighter and victim
        markers, managed victim and firefighter states)."""
        objs = []
        for name in ("firefighter_marker_agents", "victim_marker_agents", "managed_victims", "managed_firefighters"):
            coll = getattr(m, name, None)
            if isinstance(coll, dict):
                for key, obj in coll.items():
                    dd = getattr(obj, "__dict__", None)
                    if isinstance(dd, dict):
                        objs.append((name, str(key), obj, dict(dd)))
        return dict(vars(m)), rng_states(ag, m), objs

    def guard_diff(before, m):
        bad = []
        changed = dict_changed(before[0], vars(m))
        if changed:
            bad.append("model attrs %r" % changed[:5])
        if before[1] != rng_states(ag, m):
            bad.append("rng state")
        for name, key, obj, dd in before[2]:
            changed = dict_changed(dd, getattr(obj, "__dict__", None) or {})
            if changed:
                bad.append("%s[%s] %r" % (name, key, changed[:5]))
        return bad

    def kick(self, *a, **k):
        t0 = time.perf_counter()
        K = None
        try:
            site = rec["site"][-1] if rec["site"] else "other"
            rec["inst"] += 1
            try:
                before = guard_state(self)
                K = kick_shadow(self, ag, udm, fae, o_uorder, o_select, cfv) if udm is not None else None
                bad = guard_diff(before, self)
                if bad:
                    uerr("kick_purity", "the kick shadow changed state: %s" % "; ".join(bad))
            finally:
                rec["inst"] -= 1
            if K is not None:
                K.update(i=len(rec["kicks"]), step=step_of(self), phase=rec["phase"], site=site,
                         switch=bool(getattr(ag, "dispatch_urgency", lambda: False)()))
                rec["u1_shadow_ms"] += K["ms"] or 0.0
        except Exception as exc:
            uerr("kick_pre", exc)
            K = None
        n0 = len(rec["commands"])
        att = []
        rec["kick_att"].append(att)
        rec["ctx"].append("kick:" + (rec["site"][-1] if rec["site"] else "other"))
        spent = (time.perf_counter() - t0) * 1000.0
        try:
            r = o_kick(self, *a, **k)
        finally:
            rec["ctx"].pop()
            rec["kick_att"].pop()
        t1 = time.perf_counter()
        try:
            if K is not None:
                bound = [[c[3], c[4]] for c in rec["commands"][n0:] if c[2] == "assign" and c[6]]
                K["bound"] = bound
                K["n_cmd"] = len(rec["commands"]) - n0
                K["attempts"] = att
                bind_flags(K, bound)
                K["ms_model"] = None    # no U1 in the model
                K["triage"] = None
                served = bound[0][0] if bound else None
                if K["acc"] is not None:
                    # the kick's first bind must be the shadow's: U1's at a qualifying kick of an ON arm (never in
                    # this round: U1 is not in the model), the index order's at every other kick
                    on_u1 = bool(K["switch"] and K["qualifies"])
                    expected = K["u1_wb"] if on_u1 else K["index_wb"]
                    if served != expected:
                        rec["mismatch"].append([K["step"], K["F"][0][0] if K["F"] else None,
                                                "u1" if on_u1 else "index", "kick bind differs from the acc shadow",
                                                "kick:%d" % K["i"], expected, served])
                if K["qualifies"]:
                    free_id = K["F"][0][0] if K["F"] else None
                    pos = {v: c for v, c in K["W"]}
                    acc = K["acc"]
                    for vid in K["index"]:
                        r3 = K["rec"].get(vid) or [None, None, None]
                        dec = {"k": K["i"], "step": K["step"], "vid": vid, "cell": pos.get(vid), "T": r3[0],
                               "c": r3[1], "P": r3[2], "d": (K["d"].get(vid) or {}).get(free_id), "unit": free_id,
                               "served": vid == served, "u1_first": bool(K["u1"]) and K["u1"][0] == vid,
                               "index_first": K["index"][0] == vid,
                               "accepted": None if acc is None else bool(acc.get(vid)),
                               "index_wb": vid == K["index_wb"], "u1_wb": vid == K["u1_wb"],
                               "first_burn": None, "pickup": None, "death": None, "complete": None}
                        rec["decisions"].append(dec)
                        if dec["cell"] is not None:
                            rec["burn_watch"].append(dec)
                K["inst_ms"] = round(spent + (time.perf_counter() - t1) * 1000.0, 3)
                rec["kicks"].append(K)
        except Exception as exc:
            uerr("kick_post", exc)
        tot = spent + (time.perf_counter() - t1) * 1000.0
        rec["ud_ms"] += tot
        rec["kick_ms"] += tot
        return r

    WM._try_dispatch_unresolved_confirmed_victims = kick

    # v2: every _dispatch_firefighter_to_victim call made during a kick, in call order, with its return value
    # (record-only; a call outside any kick, or from a shadow, is not recorded)
    o_dispatch = getattr(WM, "_dispatch_firefighter_to_victim", None)
    if o_dispatch is not None:
        def dispatch(self, *a, **k):
            slot = None
            if rec["kick_att"] and not rec["inst"]:
                try:
                    slot = [str(a[0] if a else k.get("victim_id")), None]
                    for lst in rec["kick_att"]:
                        lst.append(slot)
                except Exception as exc:
                    uerr("dispatch_pre", exc)
                    slot = None
            out = o_dispatch(self, *a, **k)
            if slot is not None:
                slot[1] = bool(out)
            return out

        WM._dispatch_firefighter_to_victim = dispatch

    # ================================================================== movement (22.6.3) + the guard (1d.8 (5))
    o_advance = FF.advance
    o_refresh = FF._refresh_target_from_victim

    def refresh(self, *a, **k):
        r = o_refresh(self, *a, **k)
        ctx = rec["adv"]
        if ctx is not None and ctx["unit"] is self and ctx["S"] is None and not ctx["done"]:
            ctx["done"] = True
            t0 = time.perf_counter()
            model = self.model
            rec["inst"] += 1
            try:
                before = (dict(self.__dict__), dict(vars(model)), rng_states(ag, model))
                S = mv_shadow(self, model, ag, fn, gfn, cfv)
                bad = dict_changed(before[0], self.__dict__)
                bad_m = dict_changed(before[1], vars(model))
                bad_r = before[2] != rng_states(ag, model)
                if bad or bad_m or bad_r:
                    uerr("mv_purity", "shadow changed state: unit keys %r, model attrs %r, rng %s" % (
                        bad[:5], bad_m[:5], bad_r))
                ctx["S"] = S
                if S is not None:
                    if S.get("gerr"):
                        gerr("guard_shadow step %s" % step_of(model), S["gerr"])
                    for f in ("a", "b"):
                        if S.get("g" + f) is not None:
                            rec["inst_guard_ms"].append(round(S["g" + f][3], 3))
            except Exception as exc:
                uerr("mv_shadow", exc)
            finally:
                rec["inst"] -= 1
            ctx["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        return r

    def advance(self, *a, **k):
        t0 = time.perf_counter()
        ctx = None
        try:
            if getattr(self, "pos", None) is not None and not getattr(self, "dead", False):
                ctx = {"unit": self, "S": None, "done": False, "mt": 0, "rb_call": 0, "rb_set": 0,
                       "st_pre": str(getattr(self, "status", "") or ""),
                       "victim": vid_of(self.model, getattr(self, "rescued_victim", None)),
                       "fix_ms": 0.0, "fix_by": {}, "exit_kind": None,
                       "model_a": _MISSING, "model_b": _MISSING, "model_g": [], "inst_ms": 0.0}
        except Exception as exc:
            uerr("advance_pre", exc)
            ctx = None
        prev = rec["adv"]
        rec["adv"] = ctx
        rec["ctx"].append("adv:" + (fid_of(self.model, self) if ctx is not None else "?"))
        pre_ms = (time.perf_counter() - t0) * 1000.0
        try:
            r = o_advance(self, *a, **k)
        finally:
            rec["ctx"].pop()
            rec["adv"] = prev
        t1 = time.perf_counter()
        try:
            if ctx is not None and ctx["S"] is not None:
                mv_row(self, ctx)
        except Exception as exc:
            uerr("advance_post", exc)
        post_ms = (time.perf_counter() - t1) * 1000.0
        tot = pre_ms + post_ms + (ctx["inst_ms"] if ctx is not None else 0.0)
        rec["ud_ms"] += pre_ms + post_ms
        rec["mv_ms"] += tot
        if ctx is not None and rec["mv_rows"] and ctx.get("row_i") is not None:
            rec["mv_rows"][ctx["row_i"]][_INST_MS_I] = round(tot, 3)
        if ctx is not None:
            rec["ud_ms"] += ctx["inst_ms"]
        return r

    def mv_row(unit, ctx):
        S = ctx["S"]
        model = unit.model
        post = _cell(getattr(unit, "pos", None))
        burning, smoky = S["burning"], S["smoky"]
        oob = model.grid.out_of_bounds
        fine = str((getattr(unit, "movement_reason", None) or {}).get("fine_category", "") or "")
        tier = int(getattr(unit, "_last_move_tier", 0) or 0)
        leg = S["leg"]
        # the MODEL's guard calls in this advance (at most one: (b) at the survival retreat, or (a) at the approach)
        mg = {}
        for call in ctx["model_g"]:
            if call["kind"] in mg:
                gerr("model_guard step %s" % step_of(model), "more than one model guard call for fix %s in one advance"
                     % call["kind"])
            mg[call["kind"]] = call
        vetoed = {f: not c["verdict"][0] for f, c in mg.items()}
        if leg == "approach":
            if fine == "exiting_setup":
                br = "pickup"
            elif fine == "survival_retreat_on_route":
                br = "retreat_b"
            elif fine == "survival_retreat":
                br = "retreat_b_veto" if vetoed.get("b") else "retreat"
            elif fine == "moving_to_victim":
                if S["trig"]:
                    br = "retreat_b_veto" if vetoed.get("b") else "retreat_fb"
                elif ctx["model_a"] is not _MISSING and ctx["model_a"] is not None:
                    # the label says which step was TAKEN: a vetoed decision whose fix step was nevertheless taken (a
                    # defect) stays approach_a, and the guarded agreement below fails it
                    took_fix = post == _cell(ctx["model_a"]) and tier == fix_tier["a"]
                    br = "approach_a_veto" if (vetoed.get("a") and not took_fix) else "approach_a"
                else:
                    br = "approach"
            else:
                br = "other:" + fine
        else:
            if fine == "exiting_complete":
                br = "complete"
            elif fine == "exiting_with_victim":
                base = ("path" if ctx["exit_kind"] == "path" else "fallback") if ctx["exit_kind"] else "greedy"
                if base != "path":
                    if ctx["rb_call"]:
                        base += "_raise"
                    elif tier == 6 and post == S["pre"]:
                        base += "_hold"
                br = base
            else:
                br = "other:" + fine
        c1_post = None
        if S["kind"] == "carry" and post is not None:
            c1_post = _c1_cost(post, burning, smoky, oob)
        step = step_of(model)
        uid = fid_of(model, unit)
        ga = S["ga"][0] if S.get("ga") is not None else None
        gb = S["gb"][0] if S.get("gb") is not None else None
        inst_admit = {"a": ga, "b": gb}
        veto = "".join(f for f in "ab" if vetoed.get(f))
        acted_g = "".join(f for f in S["acted"] if inst_admit.get(f) is True)
        row = [step, uid, ctx["victim"], leg, br, _jc(S["pre"]), _jc(post), _jc(S["target"]), S["digest"],
               ctx["st_pre"], str(getattr(unit, "status", "") or ""), tier, ctx["mt"], ctx["rb_call"], ctx["rb_set"],
               S["trig"], S["zrb"],
               None if S["today"] is None else [S["today"][0], _jc(S["today"][1]), S["today"][2], S["today"][3]],
               _jc(S["fa"]), _jc(S["fb"]), None if S["fbB"] is None else [_jc(c) for c in S["fbB"]],
               None, S["acted"],
               S["dc"], S["dcx"], S["df"], S["dm"], S["dr"], S["gesc"],
               S["cls_pre"], None if post is None else _cls(post, burning, smoky),
               S["fd_pre"], None if post is None else _mfd(post, burning), S["c1_pre"], c1_post,
               round(ctx["fix_ms"], 3), None, S["dcb"],
               ga, gb, veto, acted_g]
        ctx["row_i"] = len(rec["mv_rows"])
        rec["mv_rows"].append(row)
        if br == "pickup" and ctx["victim"]:
            rec["pickups"].setdefault(ctx["victim"], []).append(step)
        if br == "complete" and ctx["victim"]:
            rec["completes"].setdefault(ctx["victim"], step)
        for f, ms in ctx["fix_by"].items():
            rec["fix_calls"].setdefault(f, []).append(round(ms, 3))
        post_w = writes_of(unit)
        # the survival_writes replica against the model (every advance with the survival trigger)
        sv = S.get("sv")
        if leg == "approach" and S["trig"] and sv is not None:
            rp = rec["replica"]
            if br in ("retreat", "retreat_fb", "retreat_b_veto"):
                rp["checked"] += 1
                if sv["pred"] != post_w:
                    if len(rp["mismatch"]) < 30:
                        rp["mismatch"].append([step, uid, br, sv["pre"], sv["pred"], post_w])
            elif br == "retreat_b":
                rp["fix_checked"] += 1
                if sv["pre"] != post_w:
                    if len(rp["fix_mismatch"]) < 30:
                        rp["fix_mismatch"].append([step, uid, br, sv["pre"], post_w])
            today_cell = S["today"][1] if S["today"] is not None else None
            want = _jc(today_cell) if S["today"] is not None and S["today"][0] == "survival" else None
            rp["cell_checked"] += 1
            if sv["cell"] != want:
                if len(rp["cell_mismatch"]) < 30:
                    rp["cell_mismatch"].append([step, uid, sv["cell"], S["today"]])
        # ACTED events (the UNGUARDED shadow, every arm), guard-aware agreement, and one guard row per acting fix
        guard_on = bool(sw_fn["g"]())
        for f in S["acted"]:
            live = bool(sw_fn[f]())
            cell = S["fa"] if f == "a" else S["fb"]
            gs = S.get("g" + f)
            call = mg.get(f)
            model_admit = None if call is None else bool(call["verdict"][0])
            was_vetoed = bool(live and call is not None and not call["verdict"][0])
            t_cell = S["today"][1] if S["today"][1] is not None else S["pre"]
            agree = None
            expect_fix = None
            if live:
                if not guard_on:
                    expect_fix = True
                elif gs is not None:
                    expect_fix = bool(gs[0])
                if expect_fix is True:
                    agree = br == FIX_BRANCH[f] and post == cell
                elif expect_fix is False:
                    agree = br == VETO_BRANCH[f] and post == t_cell
            ev = {"step": step, "kind": f, "unit": uid, "victim": ctx["victim"], "live": live, "row": ctx["row_i"],
                  "cell": _jc(cell), "today": row[17], "taken": _jc(post), "branch": br, "detail": None,
                  "agree": agree,
                  "guard": {"admit": None if gs is None else gs[0], "c": None if gs is None else gs[1],
                            "T_v": None if gs is None else gs[2], "model_admit": model_admit},
                  "vetoed": was_vetoed, "ran": bool(live and not was_vetoed)}
            rec["mv_events"].append(ev)
            if live and agree is False:
                if expect_fix:
                    rec["mismatch"].append([step, uid, f, "shadow acted, model did not", br, _jc(cell), _jc(post)])
                else:
                    rec["mismatch"].append([step, uid, f, "guard vetoes (instrument), model did not take today's step",
                                            br, _jc(t_cell), _jc(post)])
            if call is not None:
                if call["cell"] != cell:
                    rec["mismatch"].append([step, uid, f, "guard evaluated on a cell other than the shadow's", br,
                                            _jc(cell), _jc(call["cell"])])
                if gs is not None and bool(call["verdict"][0]) != bool(gs[0]):
                    rec["mismatch"].append([step, uid, f, "model guard verdict != instrument verdict", br,
                                            [bool(call["verdict"][0]), call["verdict"][1], call["verdict"][2]],
                                            [gs[0], gs[1], gs[2]]])
            took = "fix" if (post == cell and tier == fix_tier[f]) else "today"
            rec["guard_rows"].append([
                step, uid, ctx["victim"], f, _jc(S["pre"]), _jc(cell), _jc(S["target"]),
                _jc(S["today"][1]), S["today"][0], S["today"][2], bool(S["today"][3]),
                None if gs is None else gs[1], None if gs is None else gs[2], None if gs is None else gs[0],
                model_admit, None if call is None else list(call["verdict"]),
                None if call is None else _jc(call["cell"]), took, _jc(post), tier, bool(ctx["rb_call"]),
                sv["pre"] if (f == "b" and sv) else None, sv["pred"] if (f == "b" and sv) else None,
                post_w if f == "b" else None,
                None if call is None else round(call["ms"], 3), None if gs is None else round(gs[3], 3),
                ctx["row_i"]])
        for f in ("a", "b"):
            if f in mg and f not in S["acted"]:
                # the model evaluated the guard on a fix the (unguarded) shadow says does not act
                rec["mismatch"].append([step, uid, f, "model guard call where the shadow did not act", br,
                                        _jc(S["fa"] if f == "a" else S["fb"]), _jc(mg[f]["cell"])])
        if leg == "approach" and S["kind"] == "approach" and sw_fn["a"]() and br in ("approach_a", "approach_a_veto") \
                and "a" not in S["acted"]:
            rec["mismatch"].append([step, uid, "a", "model acted, shadow did not", br, _jc(S["fa"]), _jc(post)])
        if leg == "approach" and br in ("retreat_b", "retreat_b_veto") and "b" not in S["acted"]:
            rec["mismatch"].append([step, uid, "b", "model acted, shadow did not", br, _jc(S["fb"]), _jc(post)])

    FF.advance = advance
    FF._refresh_target_from_victim = refresh

    def thin(name, before=None, after=None):
        original = getattr(FF, name)

        def wrapper(self, *a, **k):
            ctx = rec["adv"]
            if ctx is not None and ctx["unit"] is not self:
                ctx = None
            if ctx is not None and before is not None:
                before(self, ctx, a)
            out = original(self, *a, **k)
            if ctx is not None and after is not None:
                after(self, ctx, out)
            return out

        setattr(FF, name, wrapper)

    def mt_before(self, ctx, a):
        ctx["mt"] += 1

    def rb_before(self, ctx, a):
        ctx["rb_call"] += 1
        if str(getattr(self, "status", "") or "").strip().lower() != "route_blocked":
            ctx["rb_set"] += 1

    def exit_after(self, ctx, out):
        ctx["exit_kind"] = out

    thin("_move_toward", before=mt_before)
    thin("_mark_route_blocked", before=rb_before)
    thin("_exit_leg_step", after=exit_after)

    def fix_wrap(name, fix, slot=None):
        original = getattr(FF, name)

        def wrapper(self, *a, **k):
            ctx = rec["adv"]
            if rec["inst"] or rec["fix_depth"] or ctx is None or ctx["unit"] is not self:
                return original(self, *a, **k)
            f = fix
            if f is None:   # _fix_move: the tier says which fix called it
                tier = a[1] if len(a) > 1 else k.get("tier")
                f = "a" if tier == fix_tier["a"] else "b" if tier == fix_tier["b"] else "x"
                if f == "x":
                    gerr("fix_move", "a _fix_move call with tier %r (neither fix's)" % (tier,))
            rec["fix_depth"] += 1
            rec["ctx"].append("fix:" + (name if fix is None else f))
            t0 = time.perf_counter()
            try:
                out = original(self, *a, **k)
            finally:
                ms = (time.perf_counter() - t0) * 1000.0
                rec["ctx"].pop()
                rec["fix_depth"] -= 1
                ctx["fix_ms"] += ms
                ctx["fix_by"][f] = ctx["fix_by"].get(f, 0.0) + ms
            if slot is not None:
                ctx[slot] = out
            return out

        setattr(FF, name, wrapper)

    if hasattr(FF, "_approach_path_choice"):
        fix_wrap("_approach_path_choice", "a", "model_a")
        fix_wrap("_retreat_on_route_choice", "b", "model_b")
        fix_wrap("_fix_move", None)

    # the guard, timed as its OWN fix-code call ("g"); its return is the MODEL's verdict (model_admit)
    o_verdict = getattr(FF, "_stranding_guard_verdict", None)
    if o_verdict is not None:
        def verdict(self, step_cell, *a, **k):
            ctx = rec["adv"]
            if rec["inst"] or rec["fix_depth"] or ctx is None or ctx["unit"] is not self:
                return o_verdict(self, step_cell, *a, **k)
            rec["fix_depth"] += 1
            rec["ctx"].append("fix:g")
            t0 = time.perf_counter()
            try:
                out = o_verdict(self, step_cell, *a, **k)
            finally:
                ms = (time.perf_counter() - t0) * 1000.0
                rec["ctx"].pop()
                rec["fix_depth"] -= 1
                ctx["fix_ms"] += ms
                ctx["fix_by"]["g"] = ctx["fix_by"].get("g", 0.0) + ms
                rec["guard_ms"].append(round(ms, 3))
            try:
                # which fix's step is judged: (b) when this advance called fix (b)'s choice (the survival branch),
                # else (a) - the two branches are exclusive within one advance
                kind = "b" if ctx["model_b"] is not _MISSING else "a"
                ctx["model_g"].append({"kind": kind, "cell": _cell(step_cell), "ms": ms,
                                       "verdict": [bool(out[0]), None if out[1] is None else int(out[1]),
                                                   _fin(out[2])]})
            except Exception as exc:
                gerr("model_verdict", exc)
            return out

        FF._stranding_guard_verdict = verdict
    else:
        gerr("install", "agents.Firefighter has no _stranding_guard_verdict")

    return rec


def _file_shas(repo, rels):
    out = {}
    for rel in rels:
        path = os.path.join(repo, rel)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def sections(rec, ag, cfv, wf, repo, rc=None, chain_exc=None, wall_s=None, process_s=None, u1=None):
    """(d["dp"], d["ud"], d["mv"], d["mv_events"], d["mvg"]) from the record `install` filled. u1 = {"sha", "path",
    "error"} of the U1 shadow load."""
    m = rec["model"]
    ledger = getattr(m, "_dispatch_ledger", None) or {} if m is not None else {}
    dp = {
        "probe": "dp_probe v2",
        "rc_chain": rc,
        "chain_exception": repr(chain_exc) if chain_exc is not None else None,
        "switches": {
            "DISPATCH_JOINT": repr(getattr(cfv, "DISPATCH_JOINT", None)),
            "DISPATCH_REASSIGN": repr(getattr(cfv, "DISPATCH_REASSIGN", None)),
            "joint_on": bool(getattr(ag, "dispatch_joint", lambda: False)()),
            "reassign_on": bool(getattr(ag, "dispatch_reassign", lambda: False)()),
            "S": getattr(ag, "dispatch_stall_steps", lambda: None)(),
            "M": getattr(ag, "dispatch_margin_steps", lambda: None)(),
            "P": getattr(ag, "dispatch_margin_persist", lambda: None)(),
        },
        "src_sha": _file_shas(repo, SHA_FILES),
        "commands": rec["commands"],
        "releases": rec["releases"],
        "j_calls": rec["j_calls"],
        "j_events": list(getattr(m, "_dispatch_events", None) or []) if m is not None else [],
        "ledger": {f"{u}|{v}": int(b) for (u, v), b in ledger.items()},
        "binders": rec["binders"],
        "waiting": rec["waiting"],
        "waiting_custody": rec["waiting_custody"],
        "m3a": rec["m3a"],
        "invariant": rec["invariant"],
        "m8": sorted(rec["m8"].values(), key=lambda e: e["victim"]),
        "m9": rec["m9"],
        "j_detail": rec["j_detail"],
        "j_timing": rec["j_timing"],
        "writeoffs_avoided": list(getattr(m, "dispatch_writeoffs_avoided", None) or []) if m is not None else [],
        "timing": {"j_ms_total": 0.0, "j_ms_raw_total": 0.0, "inst_ms_total": round(rec["inst_ms"], 3)},
        "errors": rec["errors"],
    }
    # fates of every victim the record met, and the decisions' outcome fields
    deaths = {e["victim"]: e["death_step"] for e in rec["m8"].values()}
    fates = {}
    for v in sorted(set(rec["pickups"]) | set(rec["completes"]) | set(deaths)):
        fates[v] = {"pickups": rec["pickups"].get(v, []), "complete": rec["completes"].get(v),
                    "death": deaths.get(v)}
    for dec in rec["decisions"]:
        later = [s for s in rec["pickups"].get(dec["vid"], []) if s >= dec["step"]]
        dec["pickup"] = later[0] if later else None
        dec["death"] = deaths.get(dec["vid"])
        c = rec["completes"].get(dec["vid"])
        dec["complete"] = c if c is not None and c >= dec["step"] else None

    def acc(name, default=None):
        f = getattr(ag, name, None)
        try:
            return f() if callable(f) else default
        except Exception as exc:  # recorded, not swallowed
            return "ERR %s" % type(exc).__name__

    try:
        stale = wf.WildFireModel._route_block_stale_clear_mode()
    except Exception as exc:
        stale = "ERR %s" % type(exc).__name__
    other = {
        "FF_EXIT_LEG_MODE": acc("ff_exit_leg_mode"),
        "FF_EXIT_LEG_SERVED": acc("ff_exit_leg_served"),
        "FF_EXIT_LEG_HOLD": acc("ff_exit_leg_hold"),
        "ROUTE_BLOCK_STALE_CLEAR": stale,
    }
    probe_ms = rec["inst_ms"] + rec["ud_ms"]
    ud = {
        "probe": VERSION,
        "rc_chain": rc,
        "switches": dict({
            "DISPATCH_URGENCY": bool(acc("dispatch_urgency", False)),
            "FF_APPROACH_PATH": bool(acc("ff_approach_path", False)),
            "FF_RETREAT_KEEP_APPROACH": bool(acc("ff_retreat_keep_approach", False)),
            "FF_CARRY_REPLAN": bool(acc("ff_carry_replan", False)),
            "FF_FIX_STRANDING_GUARD": bool(acc("ff_fix_stranding_guard", False)),
        }, **other, raw={name: repr(getattr(cfv, name, None))
                         for name in URGENCY_SWITCHES + ("FF_FIX_STRANDING_GUARD",) + OTHER_SWITCHES}),
        "src_sha": _file_shas(repo, MVG_SHA_FILES),
        "schema": UD_SCHEMA,
        "kicks": rec["kicks"],
        "decisions": rec["decisions"],
        "fates": fates,
        "cmd_ctx": rec["cmd_ctx"],
        "rel_ctx": rec["rel_ctx"],
        "shadow_mismatch": rec["mismatch"],
        "timing": {
            "probe_ms_total": round(probe_ms, 3),
            "dp_inst_ms": round(rec["inst_ms"], 3),
            "ud_ms": round(rec["ud_ms"], 3),
            "kick_ms": round(rec["kick_ms"], 3),
            "mv_ms": round(rec["mv_ms"], 3),
            "u1_shadow_ms": round(rec["u1_shadow_ms"], 3),
            "u1_model_ms": 0.0,
            "fix_ms_total": {f: round(sum(v), 3) for f, v in rec["fix_calls"].items()},
            "fix_calls": rec["fix_calls"],
            "wall_s": wall_s,
            "process_s": None if process_s is None else round(process_s, 3),
            "probe_frac_of_wall": round(probe_ms / (float(wall_s) * 1000.0), 5) if wall_s else None,
        },
        "errors": rec["ud_errors"],
    }
    u1 = u1 or {}
    mvg = {
        "probe": VERSION,
        "switches": dict({
            "FF_APPROACH_PATH": bool(acc("ff_approach_path", False)),
            "FF_RETREAT_KEEP_APPROACH": bool(acc("ff_retreat_keep_approach", False)),
            "FF_FIX_STRANDING_GUARD": bool(acc("ff_fix_stranding_guard", False)),
        }, **other, raw={name: repr(getattr(cfv, name, None)) for name in MVG_SWITCHES + OTHER_SWITCHES}),
        "src_sha": _file_shas(repo, MVG_SHA_FILES),
        "u1_shadow_sha": u1.get("sha"),
        "u1_shadow_path": u1.get("path"),
        "u1_shadow_error": u1.get("error"),
        "schema": MVG_SCHEMA + " | " + MV_SCHEMA,
        "guard": {"cols": list(GUARD_COLS), "rows": rec["guard_rows"]},
        "replica": rec["replica"],
        "timing": {
            "guard_ms": rec["guard_ms"],
            "guard_calls": len(rec["guard_ms"]),
            "guard_ms_total": round(sum(rec["guard_ms"]), 3),
            "inst_guard_ms": rec["inst_guard_ms"],
            "inst_guard_calls": len(rec["inst_guard_ms"]),
        },
        "errors": rec["mvg_errors"],
    }
    return dp, ud, {"cols": list(MV_COLS), "rows": rec["mv_rows"]}, rec["mv_events"], mvg


# ------------------------------------------------------------------------------------------------- main
def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _mvg_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args>", file=sys.stderr)
        return 2
    probe_args = argv[argv.index("--") + 1:]
    if "--repo" not in probe_args:
        print("MVG REFUSED: --repo is required (every layer defaults to the main checkout)", file=sys.stderr)
        return 3
    repo = probe_args[probe_args.index("--repo") + 1]
    out_path = probe_args[probe_args.index("--out") + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    t_process = time.perf_counter()
    import agents as ag  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.adaptation_manager as amod  # noqa: E402
    import src_extension.adaptation.local_adaptation_generator as gen  # noqa: E402
    from src_extension.planning import fire_arrival_estimate as fae  # noqa: E402
    from src_extension.planning import movement_paths as mpm  # noqa: E402

    u1 = {"sha": None, "path": U1_SHADOW, "error": None}
    try:
        udm, u1["sha"] = load_u1_shadow(U1_SHADOW)
    except Exception as exc:  # recorded: the kick shadow (and 22.9's U1 class) is then not computed
        udm = None
        u1["error"] = repr(exc)[:300]

    rec = install(ag, cfv, wf, amod, gen, fae, udm, mpm)

    # A record already at --out (an earlier attempt's) is moved aside, never written into (as _dp_probe).
    if os.path.exists(out_path):
        n = 0
        while os.path.exists("%s.prev%d" % (out_path, n)):
            n += 1
        os.replace(out_path, "%s.prev%d" % (out_path, n))
    rc = None
    chain_exc = None
    try:
        ut = runpy.run_path(os.path.join(HERE, "_ut_probe.py"), run_name="ut_probe_module")
        sys.argv = [os.path.join(HERE, "_ut_probe.py")] + argv
        rc = ut["main"]()
    except BaseException as exc:  # noqa: BLE001 - the record is written whatever happened
        chain_exc = exc
        rc = 9
        print("MVG CHAIN RAISED %r" % (exc,), file=sys.stderr)
    process_s = time.perf_counter() - t_process

    try:
        wall_s = None
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as fh:
                d = json.load(fh)
            wall_s = d.get("wall_s")
        else:
            d = {"dp_only": True, "crashed": True}
        d["dp"], d["ud"], d["mv"], d["mv_events"], d["mvg"] = sections(rec, ag, cfv, wf, repo, rc, chain_exc, wall_s,
                                                                       process_s, u1)
        tmp = out_path + ".mvgtmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"), default=str)
        os.replace(tmp, out_path)
    except Exception as exc:
        print("MVG WRITE FAILED %r" % (exc,), file=sys.stderr)
        return 8
    return rc


if __name__ == "__main__":
    sys.exit(main())
