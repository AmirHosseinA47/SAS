"""Urgency round instrument: outputs/_ud_probe.py (outputs/urgency_part1.txt 16.5 and 22.6.3; rulings 23).

A port of dispatch:outputs/_dp_probe.py v2: outputs/_ut_probe.py (UNCHANGED, run in-process) plus read-only
recorders. usage (exactly _dp_probe.py's interface):
    _ud_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args ...>
    --repo is REQUIRED after "--" (every layer below defaults to the main checkout otherwise).

RECORD-ONLY. Every recorder only READS model state: no draw from any RNG, no print to stdout or stderr of its own (the
invariant checker's own stderr lines are re-emitted, as _dp_probe does), no attribute set on the model or an agent.
Every wrap is installed at CLASS level before the model is built. The shadows call the model's own PURE choice
methods (agents.Firefighter._greedy_choice, _survival_choice, _approach_path_choice, _retreat_on_route_choice,
_carry_replan_choice) through the class functions captured before any wrap; each shadow is guarded: the unit's
__dict__, the model's attribute set and the RNG states (agents.random, model.random, numpy) are compared before and
after, and a difference is an instrument error. Observer exceptions are caught and listed (dp: d["dp"]["errors"],
the rest: d["ud"]["errors"]); an observer never stops a run. d is written whatever the chain's return code.

d["dp"]   EXACTLY _dp_probe v2's section (same keys, same meaning; see that file's docstring): commands (with the
          instrument's BFS verdict at every assign), releases, binders, waiting, waiting_custody, m3a, invariant,
          m8 (with T_fire), m9, writeoffs_avoided, errors, chain_exception; the J-only fields (j_calls, j_events,
          ledger, j_detail, j_timing) are empty - the urgency checkout has no joint dispatcher. With all four urgency
          switches at 0 every field _dp_analyze.ident_diff compares equals what _dp_probe records on the same line.
d["ud"]   probe, rc_chain, switches, src_sha, kicks, decisions, fates, cmd_ctx, rel_ctx, shadow_mismatch,
          timing, errors (schema in UD_SCHEMA below and in the Part 2 notes).
          ud_probe v2 (review R2 B-1 / B-2): a waiting victim the PLANNER refuses (select_rescue_assignment drops a
          victim whose snapshot entry is cancelled, unreachable, ... - rescue_planner.py) can head either order, so
          the counterfactual bind is the first ACCEPTED victim of an order, not its head. Per kick: acc {vid: the
          planner yields "assign" for her, read at kick entry before any bind through the model's own
          get_rescue_operational_snapshot + select_rescue_assignment}, index_wb / u1_wb (the first accepted victim of
          the index / U1 order), div_shadow / divergent defined on them (the head-based v1 values are kept as
          div_shadow_head / divergent_head), attempts (every _dispatch_firefighter_to_victim call of the kick with
          its return value). In every arm the kick's first bind must equal the shadow (u1_wb at a qualifying kick of
          an ON arm, else index_wb); a difference is a shadow_mismatch row.
d["mv"]   {"cols": MV_COLS, "rows": [...]} - one row per unit-advance on an approach or carry leg (survival retreats
          of an approaching unit included; idle units have no row). v2 adds the last column dcb (clean distance from
          the unit's cell to the boundary, every row; review R3 D-16).
d["mv_events"]  one dict per ACTED event (shadow definition of 22.8.2, every arm; "live" says the fix was effective
          and so actually ran), plus C4 / C5 lookups and guard branches (live, or "would" in an arm without (c)).
"""
from __future__ import annotations

import hashlib
import heapq
import io
import json
import math
import os
import runpy
import sys
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "ud_probe v2"
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
UD_SHA_FILES = (
    "src_extension/planning/urgency_dispatch.py",
    "src_extension/planning/movement_paths.py",
    "src_extension/planning/fire_arrival_estimate.py",
    "agents.py",
    "wildfire_model.py",
    "common_fixed_variables.py",
)
URGENCY_SWITCHES = ("DISPATCH_URGENCY", "FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_CARRY_REPLAN")
OTHER_SWITCHES = ("FF_EXIT_LEG_MODE", "FF_EXIT_LEG_SERVED", "FF_EXIT_LEG_HOLD", "ROUTE_BLOCK_STALE_CLEAR")
MV_COLS = (
    "step", "unit", "victim", "leg", "branch", "pre", "post", "target", "digest",
    "st_pre", "st_post", "tier", "mt", "rb_call", "rb_set",
    "trig", "zrb", "today", "fa", "fb", "fbB", "fc", "acted",
    "dc", "dcx", "df", "dm", "dr", "gesc",
    "cls_pre", "cls_post", "fd_pre", "fd_post", "c1_pre", "c1_post",
    "fix_ms", "inst_ms", "dcb",
)
_INST_MS_I = MV_COLS.index("inst_ms")
CARRY_BRANCH = {"path": "c0", "replan": "c1", "shelter": "c2", "shelter_stay": "c2s", "hold": "c3"}
UD_SCHEMA = (
    "mv cols: step = evaluation_timesteps_counter at the advance (rows_ff index + 1); unit / victim = ids (victim = "
    "the bound victim before the advance); leg approach|carry; branch = the branch the advance TOOK (approach, "
    "approach_a, retreat, retreat_b, retreat_fb (survival with no move -> _move_toward), pickup; carry: c0 c1 c2 c2s "
    "c3 (fix (c) kinds), path / fallback[_hold|_raise] (MODE 2), greedy[_hold|_raise] (MODE 0/1), complete; "
    "other:<fine_category>); pre / post = cells; target = post-refresh target (approach) or exit_target (carry); "
    "digest = sha1[:16] of sorted burning + sorted active-smoke cells read at the decision; st_pre / st_post = status; "
    "tier = _last_move_tier after the advance (stale when the advance did not set it); mt = _move_toward calls; "
    "rb_call = _mark_route_blocked calls; rb_set = those that set route_blocked (status was not route_blocked); "
    "trig = the survival trigger held (approach); zrb = today's raise predicate for an approaching unit (no "
    "non-burning in-grid neighbour, or no fire-free path to the target; instrument's own BFS); today = TODAY's shadow "
    "[kind, cell, tier, raise] (approach: greedy = _greedy_choice + its tier; survival: survival = _survival_choice, "
    "fallback = the _move_toward greedy when it would not move; carry: path = MODE 2 exit_leg_first_step, else "
    "greedy / hold / raise of _move_toward(exit_target)); fa / fb / fc = fix (a) cell / fix (b) cell / fix (c) "
    "[kind, cell] from the pure methods BEFORE the advance (None where not evaluated); fbB = B, the on-route clean "
    "neighbours with the smallest clean distance (survival steps, G-ESC true; [] if none); acted = letters of the "
    "fixes whose shadow ACTED (22.8.2: a = fa not None and != today's cell; b = fb not None on a survival step; c = "
    "C-1/C-2/C-3 kind and cell or raise differs from today's); dc = clean BFS distance (instrument's own) from the "
    "target at the unit's cell (approach; strict: the unit's cell must be clean) or from the carrier to a clean "
    "boundary cell (carry, start exempt); dcx = dc with the unit's own cell exempt; df = fire-free (non-burning) BFS "
    "distance (unit cell exempt, target exempt / to a non-burning boundary cell); dm = Manhattan to target / boundary; "
    "dr = ROUTE distance (22.8.3) = dcx if finite else df if finite else dm; gesc = G-ESC (approach: the victim's "
    "clean region touches the boundary; carry: dc finite); cls_pre / cls_post = B burning, A fire-adjacent, S smoky, "
    "C clean (both on the decision board); fd_pre / fd_post = min Manhattan fire distance (999 = no fire); c1_pre / "
    "c1_post = [fire-adjacent, smoky, length] least-exposure cost to a non-burning boundary cell (carry rows; start "
    "exempt; [0,0,0] on a boundary cell; None = pocket); fix_ms = ms in fix code during the advance when the model "
    "called it (ON arms); inst_ms = the instrument's ms for the row; dcb (v2, every row, approach and carry) = clean "
    "BFS distance from the unit's cell (its own cell exempt) to the nearest CLEAN grid-boundary cell, 0 on a "
    "boundary cell, None when no clean boundary cell is reachable (on carry rows dcb == dc). None = not applicable "
    "/ infinite. "
    "kicks (v2 fields): acc = {vid: bool} for every vid of index (W), read at kick ENTRY before any bind whenever the "
    "U1 shadow is computed (|F| = 1, a W victim with a cell, some cell burning), else None: acc[vid] = "
    "select_rescue_assignment(model.get_rescue_operational_snapshot(), 'initial', victim_id=vid) yields action "
    "'assign' (the model's own two functions; rescue_planner's select_rescue_assignment, the one wildfire_model "
    "imports); index_wb / u1_wb = the first vid of index / u1 with acc True, else None (u1_wb None when u1 is None); "
    "div_shadow = qualifies and u1_wb != index_wb; divergent = qualifies and (bound[0][0] if bound else None) != "
    "index_wb; div_shadow_head / divergent_head = the v1 head-based values (u1[0] != index[0]; bound[0][0] != "
    "index[0]); attempts = [[vid, bool], ...] every _dispatch_firefighter_to_victim call made during the kick, in "
    "call order, with its return value (None if it raised). decisions (v2): accepted = acc[vid] (None when acc is "
    "None); index_wb / u1_wb = bool, the victim is the kick's index_wb / u1_wb. shadow_mismatch kick rows: [step, "
    "unit, 'u1' | 'index', 'kick bind differs from the acc shadow', 'kick:<i>', expected, bound] - expected = u1_wb "
    "at a qualifying kick with DISPATCH_URGENCY effective, index_wb at every other kick where acc is not None."
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


def shadow_funcs(ag):
    """The Firefighter class functions the shadows call, captured BEFORE any wrap (pure methods)."""
    F = ag.Firefighter
    return {"needs": F._needs_immediate_survival_retreat, "greedy": F._greedy_choice, "survival": F._survival_choice,
            "fix_a": F._approach_path_choice, "fix_b": F._retreat_on_route_choice, "fix_c": F._carry_replan_choice,
            "on_boundary": F._on_grid_boundary}


def mv_shadow(unit, model, ag, fn):
    """PURE pre-advance shadow for one unit (after its target refresh). None = no row (idle / off-grid / dead)."""
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
         "dc": None, "dcx": None, "df": None, "dm": None, "dr": None, "gesc": None, "c1_pre": None}
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
        else:
            a = _cell(fn["fix_a"](unit))
            today = ["greedy", g, gt, bool(zrb)]
            S.update(kind="approach", fa=a, acted="a" if (a is not None and a != g) else "")
        S.update(trig=trig, zrb=bool(zrb), today=today, dc=dc, dcx=dcx, df=df, dm=dm, gesc=bool(has_exit),
                 dr=dcx if dcx is not None else df if df is not None else dm)
        return S
    # carry
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
    kind, ccell = fn["fix_c"](unit)
    ccell = _cell(ccell)
    acted = kind in ("replan", "shelter", "shelter_stay", "hold") and (ccell != today[1] or bool(today[3]))
    S.update(kind="carry", today=today, fc=[str(kind), ccell], acted="c" if acted else "", dc=dc, dcx=dc, df=df,
             gesc=dc is not None, c1_pre=_c1_cost(cell, burning, smoky, oob),
             dr=dc if dc is not None else df if df is not None else dm)
    return S


def waiting_replica(model, managed, markers):
    """Today's three loop predicates (only for a checkout without _urgency_waiting)."""
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


def kick_shadow(model, ag, ud, fae, order_fn, select_fn=None):
    """PURE kick record: W (today's predicates), F, qualifies (the model's exact predicate), the U1 order and per-victim
    [T, c, promotable] from a pure urgency_order call (whenever |F| = 1, |W| >= 1 and a cell burns), with the
    planner's acceptance of every W victim (acc, v2; when select_fn is given) and the flags of kick_flags, the
    non-burning d from each waiting victim to each free unit, and at a qualifying kick Z4's independent
    recomputation."""
    K = {"W": None, "F": None, "index": None, "qualifies": False, "u1": None, "rec": {}, "d": {}, "ms": None,
         "div_shadow": False, "nB": None, "z4": None, "z4_ok": None, "acc": None, "index_wb": None, "u1_wb": None,
         "div_shadow_head": False}
    managed = getattr(model, "managed_victims", None)
    markers = getattr(model, "victim_marker_agents", None)
    if not isinstance(managed, dict) or not isinstance(markers, dict):
        return K
    if hasattr(model, "_urgency_waiting"):
        waiting = model._urgency_waiting(managed, markers)
    else:
        waiting = waiting_replica(model, managed, markers)
    units = getattr(model, "firefighter_marker_agents", None) or {}
    free = [(str(fid), u) for fid, u in units.items() if model._firefighter_available_for_dispatch(u)]
    K["W"] = [[str(vid), _jc(_cell(getattr(mk, "pos", None)))] for vid, mk in waiting]
    K["F"] = [[fid, _jc(_cell(getattr(u, "pos", None)))] for fid, u in free]
    K["index"] = [str(vid) for vid, _mk in waiting]
    view = None
    if len(free) == 1 and len(waiting) >= 1 and hasattr(model, "_urgency_dispatch_view"):
        view = model._urgency_dispatch_view(waiting, free[0][1])
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


def c4_event(model, out, victim_id, victim_marker, carry_on):
    """C-4 at one _find_active_firefighter_for_victim call (pure). With (c) effective: the lookup returned an
    EXITING unit labelled route_blocked (live). Without it: a live, on-grid, assigned, exiting unit labelled
    route_blocked and bound to this victim exists while the lookup returned None - where C-4 WOULD return it (not
    live). None otherwise. Returns {unit, victim, live, carry_replan}."""
    if out is not None:
        fm = out[1]
        if (str(getattr(fm, "status", "") or "").strip().lower() == "route_blocked"
                and getattr(fm, "exiting", False)):
            return {"unit": str(out[0]), "victim": str(victim_id), "live": True, "carry_replan": bool(carry_on)}
        return None
    if carry_on:
        return None
    for fid, fm in (getattr(model, "firefighter_marker_agents", None) or {}).items():
        if getattr(fm, "dead", False) or not getattr(fm, "assigned", False):
            continue
        if str(getattr(fm, "status", "") or "").strip().lower() != "route_blocked":
            continue
        if not getattr(fm, "exiting", False) or getattr(fm, "pos", None) is None:
            continue
        rv = getattr(fm, "rescued_victim", None)
        if rv is None:
            continue
        if rv is victim_marker or model._victim_id_from_agent(rv) == victim_id:
            return {"unit": str(fid), "victim": str(victim_id), "live": False, "carry_replan": False}
    return None


def c5_event(model, victim_id, unit_id, metadata, carry_on, hold_on):
    """C-5 at a casualty unassign (action unassign, reason firefighter_fire_casualty; pure, read BEFORE the command
    runs). For an EXITING unit whose victim no longer needs rescue (died in custody): the guard's branch is visible as
    the metadata without reset_victim_pending. live = that no-reset branch was taken with (c) effective; otherwise
    the row says where C-5 WOULD act (today_branch = HOLD's own trigger of the same branch). None for other units."""
    fm = (getattr(model, "firefighter_marker_agents", None) or {}).get(unit_id)
    if fm is None or not getattr(fm, "exiting", False):
        return None
    vm = getattr(fm, "rescued_victim", None)
    if model._victim_needs_rescue(victim_id, vm):
        return None
    no_reset = "reset_victim_pending" not in (metadata or {})
    return {"unit": str(unit_id), "victim": str(victim_id), "live": bool(no_reset and carry_on),
            "no_reset": bool(no_reset), "hold": bool(hold_on), "carry_replan": bool(carry_on),
            "today_branch": bool(hold_on)}


# ------------------------------------------------------------------------------------------------- recorders
def install(ag, cfv, wf, amod, gen, fae, udm):
    """Install every recorder (class-level wraps; call BEFORE the model is built). Returns the record dict `rec`
    that sections() turns into d["dp"], d["ud"], d["mv"] and d["mv_events"]."""
    WM = wf.WildFireModel
    FF = ag.Firefighter
    rec = {
        # _dp_probe v2's recorders
        "model": None, "phase": "init", "commands": [], "releases": [], "j_calls": [], "binders": [], "waiting": [],
        "waiting_custody": [], "m3a": [], "invariant": [], "m8": {}, "m9": [], "m9_open": [], "last_release": {},
        "errors": [], "inst_ms": 0.0, "j_detail": [], "j_timing": [], "in_j": False, "j_phase": None,
        # ud
        "ud_errors": [], "ud_ms": 0.0, "ctx": [], "inst": 0, "site": [], "adv": None, "kicks": [],
        "decisions": [], "burn_watch": [], "cmd_ctx": [], "rel_ctx": [], "mv_rows": [], "mv_events": [],
        "ev_seen": set(), "mismatch": [], "fix_calls": {"a": [], "b": [], "c": []}, "fix_depth": 0,
        "kick_model_ms": None, "triage": None, "u1_model_ms": 0.0, "u1_shadow_ms": 0.0, "mv_ms": 0.0,
        "kick_ms": 0.0, "fid": {}, "vid": {}, "pickups": {}, "completes": {}, "kick_att": [],
    }
    joint_on = getattr(ag, "dispatch_joint", None) or (lambda: False)
    fn = shadow_funcs(ag)
    o_uorder = getattr(udm, "urgency_order", None) if udm is not None else None
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
             "c": getattr(ag, "ff_carry_replan", lambda: False)}

    def err(where, exc):
        if len(rec["errors"]) < 30:
            rec["errors"].append(f"{where}: {exc!r}"[:240])

    def uerr(where, exc):
        if len(rec["ud_errors"]) < 60:
            rec["ud_errors"].append(f"{where}: {exc!r}"[:300])

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

    def event(ev):
        k = (ev.get("step"), ev.get("kind"), ev.get("unit"), ev.get("victim"), ev.get("caller"), ev.get("live"))
        if ev.get("kind") in ("C4", "C5"):
            if k in rec["ev_seen"]:
                return
            rec["ev_seen"].add(k)
        rec["mv_events"].append(ev)

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
        # ---- ud: call-site context and the C-5 guard branch (recorded apart from dp)
        t1 = time.perf_counter()
        uctx = list(rec["ctx"])
        try:
            if info is not None and info[2] == "unassign" and info[5] == "firefighter_fire_casualty":
                ev = c5_event(self, info[3], info[4], cmd.metadata, bool(sw_fn["c"]()), bool(ag.ff_exit_leg_hold()))
                if ev is not None:
                    ev.update(step=info[0], kind="C5")
                    event(ev)
        except Exception as exc:
            uerr("apply_c5", exc)
        rec["ud_ms"] += (time.perf_counter() - t1) * 1000.0
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

    # ================================================================== ud: kicks (U1, 16.5)
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

    if hasattr(WM, "_urgency_dispatch_pass"):
        o_pass = WM._urgency_dispatch_pass

        def u1_pass(self, *a, **k):
            rec["ctx"].append("u1pass")
            try:
                return o_pass(self, *a, **k)
            finally:
                rec["ctx"].pop()

        WM._urgency_dispatch_pass = u1_pass

    if udm is not None and o_uorder is not None:
        o_triage = udm.triage_line

        def uorder(*a, **k):
            t0 = time.perf_counter()
            out = o_uorder(*a, **k)
            if rec["inst"] == 0:
                ms = (time.perf_counter() - t0) * 1000.0
                rec["kick_model_ms"] = (rec["kick_model_ms"] or 0.0) + ms
                rec["u1_model_ms"] += ms
            return out

        def triage(*a, **k):
            line = o_triage(*a, **k)
            if rec["inst"] == 0:
                rec["triage"] = line
            return line

        udm.urgency_order = uorder
        udm.triage_line = triage

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
                K = kick_shadow(self, ag, udm, fae, o_uorder, o_select) if udm is not None else None
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
        rec["kick_model_ms"], rec["triage"] = None, None
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
                K["ms_model"] = None if rec["kick_model_ms"] is None else round(rec["kick_model_ms"], 3)
                K["triage"] = rec["triage"]
                served = bound[0][0] if bound else None
                if K["acc"] is not None:
                    # the kick's first bind must be the shadow's: U1's at a qualifying kick of an ON arm, the index
                    # order's at every other kick (the model ran today's order there)
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

    # ------------------------------------------------------------------ C-4 lookups
    o_find = WM._find_active_firefighter_for_victim

    def find_active(self, victim_id, victim_marker, *a, **k):
        out = o_find(self, victim_id, victim_marker, *a, **k)
        if rec["inst"]:
            return out
        t0 = time.perf_counter()
        try:
            ev = c4_event(self, out, victim_id, victim_marker, bool(sw_fn["c"]()))
            if ev is not None:
                ev.update(step=step_of(self), kind="C4", caller=sys._getframe(1).f_code.co_name)
                event(ev)
        except Exception as exc:
            uerr("find_active", exc)
        rec["ud_ms"] += (time.perf_counter() - t0) * 1000.0
        return out

    WM._find_active_firefighter_for_victim = find_active

    # ================================================================== ud: movement (22.6.3)
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
                before = (dict(self.__dict__), set(vars(model)), rng_states(ag, model))
                S = mv_shadow(self, model, ag, fn)
                bad = dict_changed(before[0], self.__dict__)
                if bad or before[1] != set(vars(model)) or before[2] != rng_states(ag, model):
                    uerr("mv_purity", "shadow changed state: unit keys %r, model attrs %s, rng %s" % (
                        bad[:5], before[1] != set(vars(model)), before[2] != rng_states(ag, model)))
                ctx["S"] = S
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
                       "fix_ms": 0.0, "fix_by": {}, "carry_kind": None, "exit_kind": None,
                       "model_a": _MISSING, "model_b": _MISSING, "inst_ms": 0.0}
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
        if leg == "approach":
            if fine == "exiting_setup":
                br = "pickup"
            elif fine == "survival_retreat_on_route":
                br = "retreat_b"
            elif fine == "survival_retreat":
                br = "retreat"
            elif fine == "moving_to_victim":
                if S["trig"]:
                    br = "retreat_fb"
                elif ctx["model_a"] is not _MISSING and ctx["model_a"] is not None:
                    br = "approach_a"
                else:
                    br = "approach"
            else:
                br = "other:" + fine
        else:
            if fine == "exiting_complete":
                br = "complete"
            elif fine == "exiting_with_victim":
                if ctx["carry_kind"] is not None:
                    br = CARRY_BRANCH.get(str(ctx["carry_kind"]), "c?")
                else:
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
        row = [step, uid, ctx["victim"], leg, br, _jc(S["pre"]), _jc(post), _jc(S["target"]), S["digest"],
               ctx["st_pre"], str(getattr(unit, "status", "") or ""), tier, ctx["mt"], ctx["rb_call"], ctx["rb_set"],
               S["trig"], S["zrb"],
               None if S["today"] is None else [S["today"][0], _jc(S["today"][1]), S["today"][2], S["today"][3]],
               _jc(S["fa"]), _jc(S["fb"]), None if S["fbB"] is None else [_jc(c) for c in S["fbB"]],
               None if S["fc"] is None else [S["fc"][0], _jc(S["fc"][1])], S["acted"],
               S["dc"], S["dcx"], S["df"], S["dm"], S["dr"], S["gesc"],
               S["cls_pre"], None if post is None else _cls(post, burning, smoky),
               S["fd_pre"], None if post is None else _mfd(post, burning), S["c1_pre"], c1_post,
               round(ctx["fix_ms"], 3), None, S["dcb"]]
        ctx["row_i"] = len(rec["mv_rows"])
        rec["mv_rows"].append(row)
        if br == "pickup" and ctx["victim"]:
            rec["pickups"].setdefault(ctx["victim"], []).append(step)
        if br == "complete" and ctx["victim"]:
            rec["completes"].setdefault(ctx["victim"], step)
        for f, ms in ctx["fix_by"].items():
            rec["fix_calls"][f].append(round(ms, 3))
        # ACTED events (shadow definition, every arm) and live agreement
        for f in S["acted"]:
            live = bool(sw_fn[f]())
            cell = S["fa"] if f == "a" else S["fb"] if f == "b" else S["fc"][1]
            if f == "a":
                agree = br == "approach_a" and post == cell
            elif f == "b":
                agree = br == "retreat_b" and post == cell
            else:
                agree = ctx["carry_kind"] == S["fc"][0] and post == cell
            ev = {"step": step, "kind": f, "unit": uid, "victim": ctx["victim"], "live": live, "row": ctx["row_i"],
                  "cell": _jc(cell), "today": row[17], "taken": _jc(post), "branch": br,
                  "detail": S["fc"][0] if f == "c" else None, "agree": agree if live else None}
            event(ev)
            if live and not agree:
                rec["mismatch"].append([step, uid, f, "shadow acted, model did not", br, _jc(cell), _jc(post)])
        if leg == "approach" and S["kind"] == "approach" and sw_fn["a"]() and br == "approach_a" and "a" not in S["acted"]:
            rec["mismatch"].append([step, uid, "a", "model acted, shadow did not", br, _jc(S["fa"]), _jc(post)])
        if leg == "approach" and br == "retreat_b" and "b" not in S["acted"]:
            rec["mismatch"].append([step, uid, "b", "model acted, shadow did not", br, _jc(S["fb"]), _jc(post)])
        if leg == "carry" and ctx["carry_kind"] is not None and S["fc"] is not None and (
                ctx["carry_kind"] != S["fc"][0] or (post != S["fc"][1])):
            rec["mismatch"].append([step, uid, "c", "model kind/cell differs from shadow", br,
                                    [S["fc"][0], _jc(S["fc"][1])], [ctx["carry_kind"], _jc(post)]])

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
                f = "a" if tier == getattr(ag, "APPROACH_PATH_TIER", 7) else (
                    "b" if tier == getattr(ag, "RETREAT_ON_ROUTE_TIER", 10) else "c")
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
        fix_wrap("_carry_replan_step", "c", "carry_kind")
        fix_wrap("_fix_move", None)


    return rec


def _file_shas(repo, rels):
    out = {}
    for rel in rels:
        path = os.path.join(repo, rel)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def sections(rec, ag, cfv, wf, repo, rc=None, chain_exc=None, wall_s=None, process_s=None):
    """(d["dp"], d["ud"], d["mv"], d["mv_events"]) from the record `install` filled."""
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
    probe_ms = rec["inst_ms"] + rec["ud_ms"]
    ud = {
        "probe": VERSION,
        "rc_chain": rc,
        "switches": {
            "DISPATCH_URGENCY": bool(acc("dispatch_urgency", False)),
            "FF_APPROACH_PATH": bool(acc("ff_approach_path", False)),
            "FF_RETREAT_KEEP_APPROACH": bool(acc("ff_retreat_keep_approach", False)),
            "FF_CARRY_REPLAN": bool(acc("ff_carry_replan", False)),
            "FF_EXIT_LEG_MODE": acc("ff_exit_leg_mode"),
            "FF_EXIT_LEG_SERVED": acc("ff_exit_leg_served"),
            "FF_EXIT_LEG_HOLD": acc("ff_exit_leg_hold"),
            "ROUTE_BLOCK_STALE_CLEAR": stale,
            "raw": {name: repr(getattr(cfv, name, None)) for name in URGENCY_SWITCHES + OTHER_SWITCHES},
        },
        "src_sha": _file_shas(repo, UD_SHA_FILES),
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
            "u1_model_ms": round(rec["u1_model_ms"], 3),
            "fix_ms_total": {f: round(sum(v), 3) for f, v in rec["fix_calls"].items()},
            "fix_calls": rec["fix_calls"],
            "wall_s": wall_s,
            "process_s": None if process_s is None else round(process_s, 3),
            "probe_frac_of_wall": round(probe_ms / (float(wall_s) * 1000.0), 5) if wall_s else None,
        },
        "errors": rec["ud_errors"],
    }
    return dp, ud, {"cols": list(MV_COLS), "rows": rec["mv_rows"]}, rec["mv_events"]


# ------------------------------------------------------------------------------------------------- main
def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _ud_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args>", file=sys.stderr)
        return 2
    probe_args = argv[argv.index("--") + 1:]
    if "--repo" not in probe_args:
        print("UD REFUSED: --repo is required (every layer defaults to the main checkout)", file=sys.stderr)
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
    try:
        from src_extension.planning import urgency_dispatch as udm  # noqa: E402
    except Exception:  # a checkout without U1
        udm = None

    rec = install(ag, cfv, wf, amod, gen, fae, udm)

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
        print("UD CHAIN RAISED %r" % (exc,), file=sys.stderr)
    process_s = time.perf_counter() - t_process

    try:
        wall_s = None
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as fh:
                d = json.load(fh)
            wall_s = d.get("wall_s")
        else:
            d = {"dp_only": True, "crashed": True}
        d["dp"], d["ud"], d["mv"], d["mv_events"] = sections(rec, ag, cfv, wf, repo, rc, chain_exc, wall_s,
                                                             process_s)
        tmp = out_path + ".udtmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"), default=str)
        os.replace(tmp, out_path)
    except Exception as exc:
        print("UD WRITE FAILED %r" % (exc,), file=sys.stderr)
        return 8
    return rc


if __name__ == "__main__":
    sys.exit(main())
