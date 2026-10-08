"""DISPATCH ROUND 2: SYNTHETIC-RECORD SELF-TEST of outputs/_dq_analyze.py (it must pass before any real run is read;
outputs/dispatch2_part1.txt 12.2: "a synthetic self-test with known answers for every rule"). Known answers for:
  - R2 (10.5 F1 (ii)): a set with 4 cells all up -> no rejection; 5 all up -> p = 1/32, rejection; 3 up 2 down -> none;
    a pooled +1 -> FAIL;
  - Holm's reach at m = 28 (10.6): 10 of 10 changed cells rising rejects; 9 of 9 does not; 12 of 13 rejects (11 of 13
    does not);
  - S3 (10.4: pooled fall, per set, robust to the best cell), L2, L3, L4 (11.3: an advanced death counts as CAUSED, a
    postponed one as PREVENTED, an UNRESOLVED (A) counts as CAUSED, a swap +1 / +1, a tie passes);
  - every new zero, each with a passing and a failing synthetic case: G-B(a) / I7, G-B(b), G-B(c), I4-W, G-T(a),
    G-T(c), M6, Z-C1a, Z-C1b, Z-C2, Z-R1, Z-R2, Z-C3. The J points are built by an EMULATOR of
    WildFireModel._joint_dispatch_point that calls the REAL corrected joint_dispatch functions (loaded by path) and
    records them in the probe's _cap format: J's own decisions must give 0 violations (positive controls: a C1 nearer
    re-used fill, an L1b clean fill, a STALL REPLACE, a MARGIN REPLACE, a nearest-barred frame, a LATCH-FILL on a
    closed route, a second fill), and each corruption (round 1's choice, a wrong value passed, a wrong verdict, a
    refused bind, ...) must be flagged by its zero;
  - D1-D4 (10.6) on hand-made samples; the S1 field list (a missing field fails); the DIVERGED assertion;
  - the ownership of 10.3, the outcome ladder of 10.8 and its texts, the hash checks of 12.2, the seeds, validity, the
    knockout events / evidence, and the W3 validity END TO END with a stand-in W3 generator (the analyzer's side of the
    contract: R0 reproduction, the knockout evidence, missing replays, a changed W2 record).
Hand-built records only (no run, no model); a temporary directory for the file cases. One line per case; exit 1 if any
fails.

    E:/Projects/SAS/.venv/Scripts/python.exe -B outputs/_dq_analyze_selftest.py [--out PATH]
"""
from __future__ import annotations

import collections
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_argv = sys.argv
sys.argv = _argv[:1]
import _dq_analyze as DA  # noqa: E402
sys.argv = _argv

U0, U1, U2, U3 = "ff_unit_0", "ff_unit_1", "ff_unit_2", "ff_unit_3"
V0, V1, V2 = "victim_0", "victim_1", "victim_2"
LINES: list[str] = []
FAILS: list[str] = []


def case(name, cond, detail=""):
    LINES.append("%-4s %s%s" % ("PASS" if cond else "FAIL", name, ("  | " + str(detail)[:300]) if detail else ""))
    if not cond:
        FAILS.append(name)


def load_jd():
    """The repo's CORRECTED joint_dispatch.py (the worktree's), loaded BY PATH under a private name - the positive
    controls' J."""
    path = os.path.join(DA.WT, "src_extension", "planning", "joint_dispatch.py")
    spec = importlib.util.spec_from_file_location("dq_selftest_joint_dispatch", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dq_selftest_joint_dispatch"] = mod
    spec.loader.exec_module(mod)
    return mod


JD = load_jd()


# ================================================================================================ the J emulator
def prow(st):
    return [[list(c) for c in st.history], st.k, st.k_closed, st.closed, st.age, dict(st.persist_map())]


def to_state(row):
    H, k, kl, closed, age, persist = row
    return JD.Progress(history=tuple((int(c[0]), int(c[1])) for c in H), k=int(k), k_closed=int(kl),
                       closed=bool(closed), age=int(age),
                       persist=tuple(sorted(((str(u), int(n)) for u, n in persist.items()),
                                            key=lambda kv: JD.id_index(kv[0]))))


def emulate(free, W, units, victims, dist, contest=None, latched_binder=None, progress_before=None, hist=None,
            ledger=None, SMP=(10, 5, 3), post=True, reassign=True, step=50, refuse=()):
    """WildFireModel._joint_dispatch_point (steps 1-4 under Limit 3) on recorded values, with the REAL corrected
    joint_dispatch functions, recorded exactly as outputs/_dq_probe.py records a J point. units {u: (x, y, unclean,
    status)}, victims {v: (x, y)}, dist {v: {u: (d, D_c)}} (None = none; d* = D_c if finite else d; clean = D_c
    finite); progress_before {(u, v): row}; hist {'u|v': {'H': [[d, D_c], ...]}}; ledger {(u, v): b}; refuse: (u, v)
    fill binds the executor refuses. Returns {cur, events, cmds, releases, ledger}."""
    phase = "post" if post else "pre"
    L = dict(ledger or {})
    full = {v: {u: [d, c, (None if d is None else (c if c is not None else d)), c is not None]
                for u, (d, c) in row.items()} for v, row in dist.items()}

    def dv(v, u, i):
        return full[v][u][i]

    con = dict(contest or {}) if (reassign and post) else {}
    lb = dict(latched_binder or {}) if (reassign and post) else {}
    allc = dict(con)
    allc.update(lb)
    prog = {k: to_state(r) for k, r in (progress_before or {}).items()}
    pb = {DA.pkey(u, v): r for (u, v), r in (progress_before or {}).items()}
    calls, events, cmds, rels = [], [], [], []

    def cell(u):
        return (units[u][0], units[u][1])

    def nonzero(pairs):
        return {DA.pkey(u, v): L[(u, v)] for u, v in pairs if L.get((u, v))}

    deltas, opens = {}, {}
    for v, u in allc.items():
        d_now = dv(v, u, 0)
        op = d_now is not None
        opens[v] = op
        c_now = dv(v, u, 1) if op else None
        deltas[v] = (int(d_now) if c_now is None else int(c_now)) if op else JD.grid_distance(cell(u), victims[v])
        st = prog.get((u, v))
        if st is None:
            prog[(u, v)] = JD.new_progress(cell(u))
            continue
        hrow = hist[DA.pkey(u, v)]["H"]
        dh, ch = tuple(h[0] for h in hrow), tuple(h[1] for h in hrow)
        fz = not (bool(dv(v, u, 3)) or any(bool(dv(v, f, 3)) for f in free))
        new = JD.progress_step(st, op, d_now, c_now, dh, ch, cell(u), fz)
        calls.append({"fn": "progress_step", "binding": [u, v], "open": op, "d": d_now, "c": c_now, "d_hist": list(dh),
                      "c_hist": list(ch), "cell": list(cell(u)), "frozen": fz, "before": prow(st)[:5],
                      "after": prow(new)[:5]})
        prog[(u, v)] = new
    bu, bv = set(), set()

    def bind(u, v, reason, dd):
        L[(u, v)] = L.get((u, v), 0) + 1
        prog[(u, v)] = JD.new_progress(cell(u))
        cmds.append([step, phase, "assign", v, u, reason, True, True, dd, dd])

    def fill(units_, victims_, stage, kind):
        d2 = {(u, v): dv(v, u, 2) for u in units_ for v in victims_}
        c2 = {(u, v): bool(dv(v, u, 3)) for u in units_ for v in victims_}
        out = JD.solve_fill(units_, victims_, d2, L, clean=c2)
        calls.append({"fn": "solve_fill", "stage": stage, "units": list(units_), "victims": list(victims_),
                      "d": {DA.pkey(u, v): d2[(u, v)] for u, v in d2}, "clean": {DA.pkey(u, v): c2[(u, v)] for u, v in c2},
                      "b": nonzero(d2), "capped": [],
                      "out": [[p.victim, p.unit, p.distance, bool(p.reused), bool(p.clean)] for p in out]})
        for p in out:
            if (p.unit, p.victim) in refuse:
                cmds.append([step, phase, "assign", p.victim, p.unit, "joint_initial", False, True, p.distance,
                             p.distance])
                events.append({"phase": phase, "kind": kind + "_refused", "stage": stage, "victim_id": p.victim,
                               "unit": p.unit, "old_units": [], "reason": "joint_initial", "distance": p.distance,
                               "message": "refused", "step": step})
                continue
            bind(p.unit, p.victim, "joint_initial", p.distance)
            events.append({"phase": phase, "kind": kind, "stage": stage, "victim_id": p.victim, "unit": p.unit,
                           "old_units": [], "reason": "joint_initial", "distance": p.distance, "message": "",
                           "step": step})
            bu.add(p.unit)
            bv.add(p.victim)

    fill_v = list(W) if reassign else list(W)
    if free and fill_v:
        fill(list(free), fill_v, 2, "fill")
    if allc:
        S, M, P = SMP
        spares = [u for u in free if u not in bu]
        cons = []
        for v, u in allc.items():
            st = prog[(u, v)]
            sd = {b: dv(v, b, 2) for b in spares}
            st2 = JD.update_persistence(st, sd, deltas[v], M)
            calls.append({"fn": "update_persistence", "binding": [u, v], "spare_d": dict(sd), "delta": deltas[v],
                          "M": M, "before": dict(st.persist_map()), "after": dict(st2.persist_map())})
            prog[(u, v)] = st2
            cons.append(JD.Contest(victim=v, incumbent=u, delta=int(deltas[v]), route_open=opens[v], k=st2.k,
                                   k_closed=st2.k_closed, persist=st2.persist_map(),
                                   latched=units[u][3] == "route_blocked"))
        released = []
        if spares and cons:
            d3 = {(b, c.victim): dv(c.victim, b, 2) for b in spares for c in cons}
            c3 = {(b, c.victim): bool(dv(c.victim, b, 3)) for b in spares for c in cons}
            plan, barred = JD.plan_replacements_detail(cons, spares, d3, L, c3, stall_steps=S, margin_persist=P)
            calls.append({"fn": "plan_replacements_detail",
                          "contests": [[c.victim, c.incumbent, c.delta, c.route_open, c.k, c.k_closed, dict(c.persist),
                                        c.latched] for c in cons], "spares": list(spares),
                          "d": {DA.pkey(b, v): d3[(b, v)] for b, v in d3}, "clean": {DA.pkey(b, v): c3[(b, v)] for b, v in c3},
                          "b": nonzero(d3), "S": S, "P": P,
                          "out": [[r.victim, r.old_unit, r.new_unit, r.cause, r.distance, r.latched] for r in plan],
                          "barred": [[b.victim, b.incumbent, b.cause, b.distance, list(b.units)] for b in barred]})
            for b in barred:
                events.append({"phase": phase, "kind": "nearest_barred", "stage": 3, "victim_id": b.victim,
                               "unit": b.incumbent, "old_units": [], "barred": list(b.units),
                               "reason": "nearest_barred_" + b.cause, "distance": b.distance, "message": "",
                               "step": step})
            for r in plan:
                reason, kind = ("joint_replace_latched", "latch_fill") if r.latched else ("reassign_" + r.cause,
                                                                                          "replace")
                bind(r.new_unit, r.victim, reason, r.distance)
                prog.pop((r.old_unit, r.victim), None)
                cmds.append([step, phase, "unassign", r.victim, r.old_unit, reason, True, None, None, None])
                rels.append([step, phase, r.victim, "", reason, r.old_unit, [r.old_unit]])
                events.append({"phase": phase, "kind": kind, "stage": 3, "victim_id": r.victim, "unit": r.new_unit,
                               "old_units": [r.old_unit], "released": [r.old_unit], "reason": reason,
                               "distance": r.distance, "message": "", "step": step})
                if not r.latched:
                    released.append(r.old_unit)
        if released:
            still = [v for v in W if v not in bv]
            if still:
                fill(released, still, 4, "second_fill")
    voi = list(dict.fromkeys(list(W) + list(allc)))
    cur = {"sets": {"free": list(free), "waiting": list(W), "latched": list(lb), "contest": con, "latched_binder": lb,
                    "fill_victims": fill_v, "binders": {v: [u] for v, u in allc.items()}, "reassign": reassign,
                    "post": post},
           "pre": True, "calls": calls, "progress_before": pb,
           "progress": {DA.pkey(u, v): prow(st) for (u, v), st in prog.items()},
           "unevaluated": [], "initialised": sorted([u, v] for v, u in allc.items() if DA.pkey(u, v) not in pb),
           "inst": {"digest": "t", "nB": 0, "nS": 0,
                    "ucell": {u: [x, y, uncl, st] for u, (x, y, uncl, st) in units.items()},
                    "vcell": {v: [victims[v][0], victims[v][1], True] for v in voi},
                    "dist": {v: full[v] for v in voi}, "hist": dict(hist or {}),
                    "ledger": {DA.pkey(u, v): b for (u, v), b in (ledger or {}).items()}, "SMP": list(SMP)},
           "contests": [], "zr1": [], "fp": {"acted": [], "base_eq_actual": True}}
    return {"cur": cur, "events": events, "cmds": cmds, "releases": rels, "ledger": L, "step": step, "phase": phase}


def zeros(e, cur=None, events=None):
    Z, st = DA.jpoint_zeros(cur if cur is not None else e["cur"], e["step"], e["phase"],
                            events if events is not None else e["events"])
    return {k: v for k, v in Z.items() if v}, st


def bad_of(Z):
    return sorted(Z)


FREE = "available"
EN = "en_route"
RB = "route_blocked"


def jpoint_cases():
    """The J point zeros (Z-C1a, Z-C1b, Z-C2, Z-R1, Z-R2, I4-W, Z-C3's plan leg): the real J's decisions -> 0; each
    corruption -> its zero."""
    # ---- C1 at the fill: a NEARER RE-USED unit beats a farther fresh one (unit side)
    e = emulate([U0, U1], [V0], {U0: (1, 1, False, FREE), U1: (9, 9, False, FREE)}, {V0: (3, 3)},
                {V0: {U0: (5, 5), U1: (9, 9)}}, ledger={(U0, V0): 1}, post=False)
    Z, st = zeros(e)
    fills = [x for x in e["events"] if x["kind"] == "fill"]
    case("ZC1a-1 positive: the corrected J fills victim_0 with the NEARER RE-USED ff_unit_0 (b = 1) over the farther "
         "fresh ff_unit_1 -> 0 violations; the structure counts the C1 path (a re-used pair nearest)",
         not Z and [(x["victim_id"], x["unit"]) for x in fills] == [(V0, U0)]
         and st["fills with a re-used pair nearest (C1 path)"] == 1, (Z, fills, dict(st)))
    bad = copy.deepcopy(e)
    fc = next(c for c in bad["cur"]["calls"] if c["fn"] == "solve_fill")
    fc["out"] = [[V0, U1, 9, False, True]]
    bad["events"] = [dict(fills[0], unit=U1)]
    Z, _st = zeros(bad)
    case("ZC1a-2 negative: round 1's fresh-first choice (the farther fresh ff_unit_1) is flagged by Z-C1a (the "
         "ledger-blind optimum is ff_unit_0)", "Z-C1a" in Z and any("optimum" in x[2] for x in Z["Z-C1a"]), Z)
    # ---- C1 victim side: one unit, two victims; a nearer victim on a re-used pair beats a farther fresh one
    e = emulate([U0], [V0, V1], {U0: (1, 1, False, FREE)}, {V0: (3, 3), V1: (7, 7)},
                {V0: {U0: (34, 34)}, V1: {U0: (43, 43)}}, ledger={(U0, V0): 1}, post=False)
    Z, _st = zeros(e)
    bad = copy.deepcopy(e)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "solve_fill")["out"] = [[V1, U0, 43, False, True]]
    bad["events"] = [dict(bad["events"][0], victim_id=V1)]
    Zb, _st = zeros(bad)
    case("ZC1a-3 victim side (|W| > |F_free|): the nearer victim_0 (re-used pair, 34) is served, not victim_1 (fresh, "
         "43): J -> 0 violations; the fresh-victim choice -> Z-C1a",
         not Z and [x["victim_id"] for x in e["events"]] == [V0] and "Z-C1a" in Zb, (Z, Zb))
    # ---- L1b: a clean-approach unit beats a nearer unit without one
    e = emulate([U0, U1], [V0], {U0: (1, 1, False, FREE), U1: (9, 9, False, FREE)}, {V0: (3, 3)},
                {V0: {U0: (5, None), U1: (9, 9)}}, post=False)
    Z, _st = zeros(e)
    bad = copy.deepcopy(e)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "solve_fill")["out"] = [[V0, U0, 5, False, False]]
    bad["events"] = [dict(bad["events"][0], unit=U0)]
    Zb, _st = zeros(bad)
    case("ZC1a-4 L1b (R-2 (b)): ff_unit_1 with a clean approach (9) beats the nearer ff_unit_0 without one (d 5): J -> "
         "0; choosing ff_unit_0 -> Z-C1a", not Z and [x["unit"] for x in e["events"]] == [U1] and "Z-C1a" in Zb, Zb)
    # ---- an exact tie goes to the fresh pair (L4')
    e = emulate([U0, U1], [V0], {U0: (1, 1, False, FREE), U1: (9, 9, False, FREE)}, {V0: (3, 3)},
                {V0: {U0: (6, 6), U1: (6, 6)}}, ledger={(U0, V0): 1}, post=False)
    Z, _st = zeros(e)
    case("ZC1a-5 an exact tie on (L1, L1b, L2', L3') goes to the FRESH pair (L4'): ff_unit_1 -> 0 violations",
         not Z and [x["unit"] for x in e["events"]] == [U1], (Z, e["events"]))
    # ---- I4-W: a fill bind refused by the executor leaves a free unit and a W victim with a finite route
    e = emulate([U0], [V0], {U0: (1, 1, False, FREE)}, {V0: (3, 3)}, {V0: {U0: (5, 5)}}, post=False,
                refuse={(U0, V0)})
    Z, _st = zeros(e)
    ok = emulate([U0], [V0], {U0: (1, 1, False, FREE)}, {V0: (3, 3)}, {V0: {U0: (None, None)}}, post=False)
    Zok, _st = zeros(ok)
    case("I4W-1 the end of a J call with a refused fill bind: free ff_unit_0 and waiting victim_0 with d 5 -> I4-W "
         "(Z-C1a holds: J chose the pair); no finite route -> no I4-W, nothing bound, 0 violations",
         bad_of(Z) == ["I4-W"] and not Zok, (Z, Zok))
    # ---- a STALL REPLACE (open route): k reaches S = 10 at this J-post; the spare is nearer than delta + k
    units = {U0: (2, 2, False, EN), U1: (8, 8, False, FREE), U2: (9, 9, False, FREE)}
    hist = {DA.pkey(U0, V0): {"H": [[19, 19]]}}
    pb = {(U0, V0): [[[2, 3]], 9, 0, False, 9, {}]}
    e = emulate([U1, U2], [], units, {V0: (5, 5)}, {V0: {U0: (20, 20), U1: (15, 15), U2: (18, 18)}},
                contest={V0: U0}, progress_before=pb, hist=hist)
    Z, st = zeros(e)
    rep = [x for x in e["events"] if x["kind"] == "replace"]
    case("ZSTALL-1 positive: no progress (d 20 not below H's 19) -> k = 10 = S; ff_unit_1 (d* 15 < 20 + 10, clean) "
         "REPLACEs ff_unit_0 (reassign_stall) -> 0 violations",
         not Z and [(x["unit"], x["old_units"], x["reason"]) for x in rep] == [(U1, [U0], "reassign_stall")]
         and st["replacements planned, stall"] == 1, (Z, e["events"], dict(st)))
    bad = copy.deepcopy(e)
    pc = next(c for c in bad["cur"]["calls"] if c["fn"] == "plan_replacements_detail")
    pc["out"] = [[V0, U0, U2, "stall", 18, False]]
    bad["events"] = [dict(rep[0], unit=U2, distance=18)]
    Z, _st = zeros(bad)
    case("ZC1b-1 negative: a REPLACE by the farther ff_unit_2 (18) while the nearest qualifying ff_unit_1 (15) is "
         "allowed -> Z-C1b", "Z-C1b" in Z, Z)
    bad = copy.deepcopy(e)
    bad["cur"]["inst"]["dist"][V0][U1][3] = False
    Z, _st = zeros(bad)
    case("ZR2-1 negative: the challenger ff_unit_1 has no clean approach on the instrument's map -> Z-R2 (and Z-R1: "
         "J passed clean True)", "Z-R2" in Z and "Z-R1" in Z, bad_of(Z))
    bad = copy.deepcopy(e)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "plan_replacements_detail")["out"][0][4] = 14
    Z, _st = zeros(bad)
    case("ZC2-1 negative: the replacement's distance 14 is not the instrument's d* 15 -> Z-C2",
         "Z-C2" in Z and any("distance" in x[2] for x in Z["Z-C2"]), Z)
    bad = copy.deepcopy(e)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "progress_step")["after"][1] = 9
    Z, _st = zeros(bad)
    case("ZR1-1 negative: J's progress verdict k = 9 (the analyzer's: 10, no progress over H) -> Z-R1",
         "Z-R1" in Z and any("verdict" in x[2] for x in Z["Z-R1"]), Z)
    bad = copy.deepcopy(e)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "update_persistence")["spare_d"][U1] = 16
    Z, _st = zeros(bad)
    case("ZR1-2 negative: a spare's d* passed to update_persistence (16) differs from the instrument's (15) -> Z-R1",
         "Z-R1" in Z and any("spare d*" in x[2] for x in Z["Z-R1"]), Z)
    bad = copy.deepcopy(e)
    bad["cur"]["progress"][DA.pkey(U1, V0)][1] = 3
    Z, _st = zeros(bad)
    case("ZR1-3 negative: the state J keeps for its bind ff_unit_1 -> victim_0 is not the bind state -> Z-R1",
         "Z-R1" in Z and any("bind state" in x[2] for x in Z["Z-R1"]), Z)
    # ---- the same contest one step earlier: k = 9 < S -> no stall; a corrupted plan claiming a stall -> Z-C2
    pb9 = {(U0, V0): [[[2, 3]], 8, 0, False, 8, {}]}
    e9 = emulate([U1, U2], [], units, {V0: (5, 5)}, {V0: {U0: (20, 20), U1: (15, 15), U2: (18, 18)}},
                 contest={V0: U0}, progress_before=pb9, hist=hist)
    Z9, _st = zeros(e9)
    bad = copy.deepcopy(e9)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "plan_replacements_detail")["out"] = [[V0, U0, U1, "stall", 15,
                                                                                            False]]
    bad["events"] = [{"phase": "post", "kind": "replace", "stage": 3, "victim_id": V0, "unit": U1, "old_units": [U0],
                      "released": [U0], "reason": "reassign_stall", "distance": 15, "step": 50}]
    Zb, _st = zeros(bad)
    case("ZC2-2 at k = 9 (< S) J replaces nothing (0 violations); a recorded STALL replacement there fails its rule "
         "(count 9 < S = 10) -> Z-C2 (and Z-C1b)", not Z9 and not [x for x in e9["events"] if x["kind"] == "replace"]
         and "Z-C2" in Zb and "Z-C1b" in Zb, (Z9, bad_of(Zb)))
    # ---- a MARGIN REPLACE: the incumbent progresses (k = 0); spare d* + M <= delta for the 3rd evaluation
    pbm = {(U0, V0): [[[2, 3]], 0, 0, False, 4, {U1: 2}]}
    histm = {DA.pkey(U0, V0): {"H": [[21, 21]]}}
    e = emulate([U1], [], {U0: (2, 2, False, EN), U1: (8, 8, False, FREE)}, {V0: (5, 5)},
                {V0: {U0: (20, 20), U1: (10, 10)}}, contest={V0: U0}, progress_before=pbm, hist=histm)
    Z, st = zeros(e)
    rep = [x for x in e["events"] if x["kind"] == "replace"]
    case("ZMARGIN-1 positive: progress (20 < 21) -> k = 0; ff_unit_1's persistence 2 -> 3 = P (10 + 5 <= 20) -> a "
         "MARGIN REPLACE -> 0 violations", not Z and [x["reason"] for x in rep] == ["reassign_margin"]
         and st["replacements planned, margin"] == 1, (Z, e["events"]))
    bad = copy.deepcopy(e)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "plan_replacements_detail")["out"][0][3] = "stall"
    bad["events"] = [dict(rep[0], reason="reassign_stall")]
    Z, _st = zeros(bad)
    case("ZC2-3 negative: the same replacement recorded as a STALL (count 0 < S) -> Z-C2", "Z-C2" in Z, Z)
    bad = copy.deepcopy(e)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "update_persistence")["after"] = {U1: 2}
    Z, _st = zeros(bad)
    case("ZR1-4 negative: the persistence count J derived (2) differs from the analyzer's (3) -> Z-R1",
         "Z-R1" in Z and any("counts" in x[2] for x in Z["Z-R1"]), Z)
    e2 = emulate([U1], [], {U0: (2, 2, False, EN), U1: (8, 8, False, FREE)}, {V0: (5, 5)},
                 {V0: {U0: (20, 20), U1: (10, None)}}, contest={V0: U0}, progress_before=pbm, hist=histm)
    Z2, _st = zeros(e2)
    case("ZMARGIN-2 R-2 (a): the same margin challenger WITHOUT a clean approach is refused by the corrected J (no "
         "replacement, 0 violations)", not Z2 and not [x for x in e2["events"] if x["kind"] == "replace"], Z2)
    # ---- NEAREST-BARRED: the nearest qualifying spare (b = 1) cannot REPLACE (b = 0 needed); the farther allowed one
    # is NOT sent (C1, X-1 (a)) - the incumbent is kept
    e = emulate([U1, U2], [], units, {V0: (5, 5)}, {V0: {U0: (20, 20), U1: (15, 15), U2: (18, 18)}},
                contest={V0: U0}, progress_before=pb, hist=hist, ledger={(U1, V0): 1, (U0, V0): 1})
    Z, st = zeros(e)
    nb = [x for x in e["events"] if x["kind"] == "nearest_barred"]
    case("ZNB-1 positive: the nearest qualifying ff_unit_1 is barred (b = 1) -> no REPLACE, a nearest_barred event, "
         "the incumbent kept -> 0 violations; the structure counts a nearest-barred frame",
         not Z and len(nb) == 1 and nb[0]["barred"] == [U1] and not [x for x in e["events"] if x["kind"] == "replace"]
         and st["nearest-barred frames"] == 1, (Z, e["events"]))
    bad = copy.deepcopy(e)
    pc = next(c for c in bad["cur"]["calls"] if c["fn"] == "plan_replacements_detail")
    pc["out"], pc["barred"] = [[V0, U0, U2, "stall", 18, False]], []
    bad["events"] = [{"phase": "post", "kind": "replace", "stage": 3, "victim_id": V0, "unit": U2, "old_units": [U0],
                      "released": [U0], "reason": "reassign_stall", "distance": 18, "step": 50}]
    Z, _st = zeros(bad)
    case("ZC1b-2 negative: round 1's rule (the nearest ALLOWED spare ff_unit_2 sent) -> Z-C1b", "Z-C1b" in Z, Z)
    # ---- a LATCHED incumbent on a CLOSED route: delta = G, k_L counts; a LATCH-FILL at k_L = S with d*(B) < G + k_L
    unitsL = {U0: (2, 2, False, RB), U1: (8, 8, False, FREE)}
    pbL = {(U0, V0): [[[2, 3]], 0, 9, True, 9, {}]}
    histL = {DA.pkey(U0, V0): {"H": [[None, None]]}}
    e = emulate([U1], [], unitsL, {V0: (5, 5)}, {V0: {U0: (None, None), U1: (12, 12)}}, latched_binder={V0: U0},
                progress_before=pbL, hist=histL)
    Z, st = zeros(e)
    lf = [x for x in e["events"] if x["kind"] == "latch_fill"]
    case("ZLATCH-1 positive: route closed -> delta = G = 6, k_L 9 -> 10 = S; ff_unit_1 d* 12 < 6 + 10 -> a LATCH-FILL "
         "(joint_replace_latched) -> 0 violations; the structure counts a closed-route contest and a latched incumbent",
         not Z and [(x["unit"], x["reason"]) for x in lf] == [(U1, "joint_replace_latched")]
         and st["contests, route closed"] == 1 and st["contests, latched incumbent"] == 1, (Z, e["events"]))
    e2 = emulate([U1], [], unitsL, {V0: (5, 5)}, {V0: {U0: (None, None), U1: (30, 30)}}, latched_binder={V0: U0},
                 progress_before=pbL, hist=histL)
    Z2, _st = zeros(e2)
    bad = copy.deepcopy(e2)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "plan_replacements_detail")["out"] = [[V0, U0, U1, "stall", 30,
                                                                                            True]]
    bad["events"] = [{"phase": "post", "kind": "latch_fill", "stage": 3, "victim_id": V0, "unit": U1,
                      "old_units": [U0], "released": [U0], "reason": "joint_replace_latched", "distance": 30,
                      "step": 50}]
    Zb, _st = zeros(bad)
    case("ZLATCH-2 C2: a far spare (30 >= G 6 + k_L 10) does not replace the latched unit (0 violations); a recorded "
         "LATCH-FILL there fails its rule -> Z-C2", not Z2 and not [x for x in e2["events"] if x["kind"] == "latch_fill"]
         and "Z-C2" in Zb, (Z2, bad_of(Zb)))
    bad = copy.deepcopy(e)
    next(c for c in bad["cur"]["calls"] if c["fn"] == "update_persistence")["delta"] = 99
    Z, _st = zeros(bad)
    case("ZR1-5 negative: J passed delta 99 for a closed route (5.2: G = 6) -> Z-R1", "Z-R1" in Z
         and any("delta" in x[2] for x in Z["Z-R1"]), Z)
    # ---- a SECOND FILL: the REPLACE releases an active unit, which then fills the W victim step 2 left unserved
    units2 = {U0: (2, 2, False, EN), U1: (8, 8, False, FREE)}
    e = emulate([U1], [V1], units2, {V0: (5, 5), V1: (2, 4)},
                {V0: {U0: (20, 20), U1: (15, 15)}, V1: {U0: (2, 2), U1: (None, None)}}, contest={V0: U0},
                progress_before=pb, hist=hist)
    Z, _st = zeros(e)
    kinds = [x["kind"] for x in e["events"]]
    case("ZFILL4-1 positive: step 2 cannot serve victim_1 (no route for ff_unit_1); the stall REPLACE releases ff_unit_0, "
         "which the step-4 SECOND FILL binds to victim_1 -> 0 violations (I4-W holds at the end)",
         not Z and kinds == ["replace", "second_fill"], (Z, kinds))
    bad = copy.deepcopy(e)
    bad["cur"]["calls"] = [c for c in bad["cur"]["calls"] if not (c["fn"] == "solve_fill" and c["stage"] == 4)]
    bad["events"] = [x for x in bad["events"] if x["kind"] != "second_fill"]
    Z, _st = zeros(bad)
    case("I4W-2 negative: without the second fill the released ff_unit_0 and victim_1 (d 2) end the J call unpaired -> "
         "I4-W", "I4-W" in Z, Z)
    bad = copy.deepcopy(e)
    pc = next(c for c in bad["cur"]["calls"] if c["fn"] == "plan_replacements_detail")
    bad["events"] = [x for x in bad["events"] if x["kind"] != "replace"]
    Z, _st = zeros(bad)
    case("ZC3-1 negative: a planned replacement neither applied nor aborted -> Z-C3", "Z-C3" in Z, bad_of(Z))
    # ---- the first sight of a contest (no state at entry): initialised, no progress verdict, counts 0
    e = emulate([U1], [], units, {V0: (5, 5)}, {V0: {U0: (20, 20), U1: (15, 15), U2: (18, 18)}}, contest={V0: U0})
    Z, _st = zeros(e)
    bad = copy.deepcopy(e)
    bad["cur"]["unevaluated"] = [[U0, V0]]
    Zb, _st = zeros(bad)
    case("ZR1-6 a contest seen first (no state at entry) is initialised with no progress_step call (0 violations); a "
         "recorded 'unevaluated' contest is a Z-R1 instance", not Z and "Z-R1" in Zb, (Z, Zb))
    # ---- the chain: the state J reads at a J point is the state it left at the previous one
    e1 = emulate([U1, U2], [], units, {V0: (5, 5)}, {V0: {U0: (20, 20), U1: (15, 15), U2: (18, 18)}},
                 contest={V0: U0}, progress_before=pb9, hist=hist)
    nxt = copy.deepcopy(e1["cur"])
    nxt["progress_before"] = copy.deepcopy(e1["cur"]["progress"])
    first = copy.deepcopy(e1["cur"])
    first["progress_before"] = {}
    ok = DA.chain_zeros([[49, "post", first], [50, "post", nxt]])
    nxt2 = copy.deepcopy(nxt)
    nxt2["progress_before"][DA.pkey(U0, V0)][1] = 0
    badc = DA.chain_zeros([[49, "post", first], [50, "post", nxt2]])
    badf = DA.chain_zeros([[49, "post", e1["cur"]]])
    case("ZR1-7 the chain (Z-R1): a J point reading exactly the states the previous one left holds; a state reset "
         "between them (k 9 -> 0) and states before the first J bind are flagged",
         not ok and len(badc) == 1 and len(badf) == 1, (ok, badc, badf))


def run_level_cases():
    """The run-level dispatch zeros: G-B(a) / I7, G-B(b), G-B(c), G-T(a), G-T(c), M6, Z-C3."""
    bind2 = [[5, [[V0, [[U0, "en_route"], [U1, "route_blocked"]]]]], [6, [[V0, [[U0, "en_route"], [U1, "en_route"]]]]]]
    _n, l_ = DA.gb_counts(bind2, [])
    _n, l_ok = DA.gb_counts([[5, [[V0, [[U0, "en_route"]]]]]], [])
    case("GB-1 G-B(a) / I7: two victim-steps with >= 2 living binders; G-B(b): one with >= 2 ACTIVE binders; one "
         "binder -> none", len(l_["gb_a"]) == 2 and len(l_["gb_b"]) == 1 and not l_ok["gb_a"] and not l_ok["gb_b"],
         (l_["gb_a"], l_["gb_b"]))
    ev = [{"step": 7, "phase": "post", "kind": "replace", "victim_id": V0, "unit": U1, "old_units": [U0]}]
    inst_, exc, nos = DA.gb_c_check(ev, [[7, []]], [], {}, [])
    ok, _e, _n = DA.gb_c_check(ev, [[7, [[V0, [[U1, "en_route"]]]]]], [], {}, [])
    case("GBC-1 G-B(c) I3: a REPLACE at J-post whose victim has no binder at the same step's sample -> 1; bound -> 0",
         len(inst_) == 1 and not ok and not exc and not nos, inst_)
    cmd = lambda s, a, v, u, r, ok_=True, op=True: [s, "post", a, v, u, r, ok_, op, 5, 5]      # noqa: E731
    rets = DA.gt_returns([cmd(1, "assign", V0, U0, "joint_initial"), cmd(3, "assign", V0, U1, "reassign_stall"),
                          cmd(5, "assign", V0, U0, "reassign_stall")], [[s, []] for s in range(1, 6)], {}, {})
    rets_o3 = DA.gt_returns([cmd(1, "assign", V0, U0, "joint_initial"), cmd(3, "assign", V0, U1, "reassign_stall"),
                             cmd(5, "assign", V0, U0, "reassign_stall")], [[s, []] for s in range(1, 6)], {U1: 4}, {})
    case("GTA-1 G-T(a) (round 1's reading): A..X..A on a victim with no outside event on X -> a G-T(a) instance; X's "
         "death between (o3) -> an outside event, not G-T(a)", [r["outside"] for r in rets] == [[]]
         and [r["outside"] for r in rets_o3] == [["o3"]], (rets, rets_o3))
    viol, reused, _b = DA.ledger_check([cmd(1, "assign", V0, U0, "joint_initial"), cmd(3, "assign", V1, U0, "x"),
                                        cmd(5, "assign", V0, U0, "reassign_stall"),
                                        cmd(6, "assign", V1, U2, "joint_initial"),
                                        cmd(7, "assign", V1, U2, "joint_replace_latched"),
                                        cmd(8, "assign", V1, U2, "joint_replace_latched")])
    case("GTC-1 G-T(c): a REPLACE (reassign_stall) on a pair bound before (b = 1) and a LATCH-FILL on b = 2 are "
         "violations; a LATCH-FILL on b = 1 is not", [v[4] for v in viol] == ["reassign_stall", "joint_replace_latched"]
         and [v[5] for v in viol] == [1, 2] and len(reused) == 3, viol)
    dp = {"commands": [cmd(5, "assign", V0, U0, "joint_initial", True, False), cmd(6, "assign", V1, U1,
                                                                                    "joint_initial")],
          "binders": [], "j_events": [{"step": 5, "phase": "post", "kind": "fill", "stage": 2, "victim_id": V0,
                                       "unit": U0}, {"step": 6, "phase": "post", "kind": "fill", "stage": 2,
                                                     "victim_id": V1, "unit": U1}],
          "j_calls": [[5, "post", 1.0, 1], [6, "post", 1.0, 1]], "releases": [], "j_detail": []}
    Z, _st, _x = DA.dispatch_zeros(dp, [], [], {}, {}, True)
    case("M6-1 M6: a successful assign into a route the instrument's BFS found closed -> 1 instance; an open one -> "
         "none", [x[2] for x in Z["M6"]] == [V0], Z["M6"])
    case("ZC3-2 a J bind at a J point with no recorded PRE (no j_detail entry) -> Z-C3",
         any("no recorded PRE" in x[2] for x in Z["Z-C3"]), Z["Z-C3"])
    e = emulate([U1, U2], [], {U0: (2, 2, False, EN), U1: (8, 8, False, FREE), U2: (9, 9, False, FREE)}, {V0: (5, 5)},
                {V0: {U0: (20, 20), U1: (15, 15), U2: (18, 18)}}, contest={V0: U0},
                progress_before={(U0, V0): [[[2, 3]], 9, 0, False, 9, {}]}, hist={DA.pkey(U0, V0): {"H": [[19, 19]]}})
    jc = [[50, "post", 1.0, len(e["events"])]]
    ok = DA.zc3_run(e["cmds"], e["releases"], e["events"], jc, True)
    swapped = [e["cmds"][1], e["cmds"][0]]
    bad_order = DA.zc3_run(swapped, e["releases"], e["events"], jc, True)
    extra = DA.zc3_run(e["cmds"] + [[50, "post", "unassign", V1, U2, "reassign_margin", True, None, None, None]],
                       e["releases"], e["events"], jc, True)
    outside = DA.zc3_run(e["cmds"], e["releases"], e["events"], [[49, "post", 1.0, 0]], True)
    rel_bad = DA.zc3_run(e["cmds"], e["releases"] + [[50, "post", V1, "", "reassign_stall", U2, [U2]]], e["events"],
                         jc, True)
    kind_bad = DA.zc3_run(e["cmds"], e["releases"], e["events"] + [{"step": 50, "phase": "post", "kind": "waypoint",
                                                                    "stage": 3}], jc, True)
    case("ZC3-3 Z-C3 on the commands: a stall REPLACE's assign + release -> 0; the release BEFORE the bind, a J unassign "
         "no replacement released, a J command / event outside a J point, a single-unit release outside an atomic "
         "replacement, an unknown J event kind -> each flagged",
         not ok and bad_order and extra and outside and rel_bad and kind_bad,
         (ok, bad_order[:1], extra[:1], outside[:1], rel_bad[:1], kind_bad[:1]))


def d_cases():
    """D1-D4 (10.6) on hand-made samples."""
    def unit(u, status, free, bound, moved, routes, log=()):
        return [u, status, free, bound, [1, 1], moved, [list(r) for r in routes], [list(x) for x in log]]
    rows = [
        [10, [V0], [V1], [], [], [unit(U0, "available", True, False, True, [(V0, 5), (V1, None)]),
                                 unit(U1, "available", True, False, True, [(V0, None), (V1, 7)]),
                                 unit(U2, "route_blocked", False, False, False, [(V0, None), (V1, None)])]],
        [11, [V0], [], [], [], [unit(U0, "available", True, False, False, [(V0, None)], [("move", False)]),
                                unit(U1, "available", True, False, False, [(V0, None)], [("extinguish", True)]),
                                unit(U2, "route_blocked", False, False, None, [(V0, None)]),
                                unit(U3, "available", True, False, False, [(V0, None)], [("clear", False)])]],
        [12, [], [V1], [], [], [unit(U1, "available", True, False, True, [(V1, 4)])]],
        [13, [], [V1], [], [], [unit(U1, "available", True, False, True, [(V1, 4)])]],
        [14, [], [], [], [V0], [unit(U2, "available", True, False, False, [])]],
    ]
    binders = [[10, [[V1, [[U3, "route_blocked"]]]]], [12, [[V1, [[U3, "route_blocked"]]]]],
               [13, [[V1, [[U3, "route_blocked"], [U2, "route_blocked"]]]]]]
    num, lists = DA.d_counts(rows, {(12, V1): "stall"}, binders)
    case("D1-1 ABANDONED WAITING: step 10 W victim_0 (free ff_unit_0, d 5) and W_L victim_1 (free ff_unit_1, d 7, one "
         "binder) -> W + latch-held; step 11 no free unit has a route -> none; step 12 W_L victim_1 nearest-barred at "
         "J-post -> nearest-barred; step 13 two binders -> other; step 14 no waiting victim -> none: D1 = 4",
         num["d1_abandoned"] == 4 and num["d1_W"] == 1 and num["d1_latch-held"] == 1
         and num["d1_nearest-barred"] == 1 and num["d1_other"] == 1, dict(num))
    case("D3-1 IDLE-UNREACHABLE: step 10 ff_unit_2 (route_blocked, unbound, no route, did not move, no write) counts; "
         "step 11 ff_unit_0 (no route, did not move, a move row without a write) and ff_unit_3 (a clear with no write) "
         "count, ff_unit_1 extinguished (a write = work) and ff_unit_2's first sample (moved None) do not; step 14 "
         "(no waiting victim) none: D3 = 3; action-blind 5",
         num["d3_idle_unreachable"] == 3 and num["d3_blind"] == 5
         and sorted(x[1] for x in lists["d3"]) == [U0, U2, U3], (dict(num), lists["d3"]))
    case("D1-2 spells: victim_0 one spell (step 10), victim_1 10 and 12-13 -> spells of 1 and 2",
         lists["d1_spells"] == [[V0, 10, 10, 1], [V1, 10, 10, 1], [V1, 12, 13, 2]], lists["d1_spells"])
    i4 = DA.i4w_sample(rows)
    case("I4W-3 I4-W at the sample instant (D1's W part): step 10 victim_0 with free ff_unit_0 -> 1 instance",
         i4 == [[10, "sample", V0, [U0]]], i4)
    rows_ff = []
    for t in range(1, 21):
        rows_ff.append([[U0, 1, 1, "route_blocked" if t >= 15 else "en_route", 1, 0, 0, 0, V0, None, 0, None],
                        [U1, 2, 2, "route_blocked" if 5 <= t <= 10 else "available", 0, 0, 0, 0, None, None, 0, None],
                        [U2, 3, 3, "route_blocked" if t >= 18 else "available", 0, 0, 0, 0, None, None, 0, None]])
    lat, bound = DA.d4_route_blocked_end({"rows_ff": rows_ff})
    case("D4-1 ROUTE_BLOCKED AT RUN END: ff_unit_0 (bound) and ff_unit_2 (unbound) end route_blocked; ff_unit_1 "
         "recovered -> D4 = 2, bound 1", lat == [U0, U2] and bound == [U0], (lat, bound))
    cmd = lambda s, a, v, u, r: [s, "post", a, v, u, r, True, True, 5, 5]                     # noqa: E731
    cmds = [cmd(1, "assign", V0, U0, "joint_initial"), cmd(3, "assign", V0, U1, "reassign_stall"),
            cmd(5, "assign", V0, U0, "joint_replace_latched"), cmd(7, "assign", V1, U1, "joint_initial")]
    rets = DA.gt_returns_amended(cmds, [[s, []] for s in range(1, 8)], {}, {U1: {4}})
    case("D2-1 FLIP-FLOPS (returns of any cause, round 1's G-T(b)): A..X..A on victim_0 -> 1 return, whatever its "
         "outside events", len(rets) == 1, rets)


def s1_cases():
    """10.2: the FROZEN S1 field list."""
    a = {k: [1] for k in DA.R.FIELDS}
    a.update({"params": {"NUM_FIREFIGHTERS": 3}, "effective": {"global_planner_mode": 0},
              "mf2": {"probe": "p1", "fleet": [1]}, "fb3": {"x": 1}, "mr": {"y": 2}, "ut": {"z": 3},
              "dp": {k: [] for k in DA.S1_DP_REQUIRED}, "mv": {"cols": ["step", "fix_ms", "inst_ms"],
                                                               "rows": [[1, 0.5, 0.1]]},
              "mv_events": [], "mvg": {"guard": {"cols": list(DA.GUARD_COLS), "rows": []}},
              "dq": {"sample": {"rows": [[1]]}, "ff_log": {"rows": []}, "timing": {"x": 1}}})
    a["dp"].update({"j_calls": [], "timing": {"j": 1}, "src_sha": {"a": 1}, "errors": []})
    b = copy.deepcopy(a)
    b["mf2"]["probe"] = "p2"
    b["dp"]["timing"] = {"j": 2}
    b["dp"]["src_sha"] = {"a": 2}
    b["mv"]["rows"] = [[1, 9.9, 9.9]]
    b["dq"]["timing"] = {"x": 2}
    b["wall_s"] = 3.0
    bad, rows = DA.s1_compare(DA.s1_fields(a), DA.s1_fields(b))
    case("S1-1 identical on the frozen list: mf2's probe string, dp's J-only fields (timing, src_sha), the mv timing "
         "columns, d['dq'] outside the sample / ff_log and wall_s are NOT compared -> PASS", not bad, bad)
    c = copy.deepcopy(b)
    del c["dq"]["sample"]
    bad, rows = DA.s1_compare(DA.s1_fields(a), DA.s1_fields(c))
    case("S1-2 a listed field (the per-step sample) MISSING from one record fails S1 ('MISSING in dq0')",
         bad == ["dq.sample"] and any("MISSING" in r[2] for r in rows if r[0] == "dq.sample"), (bad, rows[:2]))
    c = copy.deepcopy(b)
    del c["dp"]["m9"]
    d = copy.deepcopy(a)
    del d["dp"]["m9"]
    bad, _r = DA.s1_compare(DA.s1_fields(d), DA.s1_fields(c))
    case("S1-3 a required field missing from BOTH records still fails (every listed field must be present)",
         bad == ["dp.m9"], bad)
    c = copy.deepcopy(b)
    c["dp"]["commands"] = [[1, "post", "assign", V0, U0, "x", True, False, None, 3]]
    c["dq"]["ff_log"] = {"rows": [[1]]}
    bad, rows = DA.s1_compare(DA.s1_fields(a), DA.s1_fields(c))
    case("S1-4 a differing dp.commands (with the instrument's route verdicts) and firefighting log fail; the failure "
         "line names the field path only", bad == ["dp.commands", "dq.ff_log"]
         and all(r[2].endswith("differs") for r in rows if not r[1]), rows)


def diverged_cases():
    gx = {"h": {k: ["a", "b"] for k in DA.ROW_KINDS}, "eval": {"rescued": 1}, "cmd_seq": [[1, "assign", V0, U0, True]]}
    gy = copy.deepcopy(gx)
    same = DA.diverged(gx, gy)
    gy2 = copy.deepcopy(gx)
    gy2["cmd_seq"] = [[1, "assign", V0, U1, True]]
    gy3 = copy.deepcopy(gx)
    gy3["h"]["rows_vic"] = ["a", "c"]
    case("DIV-1 DIVERGED: identical rows / eval / commands -> not diverged; a command (step, action, victim, unit, ok) "
         "differing or a rows_vic hash differing -> diverged", same == (False, [])
         and DA.diverged(gx, gy2) == (True, ["commands"]) and DA.diverged(gx, gy3) == (True, ["rows_vic"]))
    nx = {"c1": {"DD": 1, "d1_abandoned": 2}, "c2": {"DD": 1}}
    ny = {"c1": {"DD": 0, "d1_abandoned": 2}, "c2": {"DD": 1, "d3_idle_unreachable": 1}}
    case("DIV-2 the DIVERGED assertion: a non-diverged cell with a non-zero delta in a gated count (DD in c1; D3 in "
         "c2) -> flagged (a STOP); with both cells diverged -> holds",
         DA.diverged_assertion(nx, ny, set()) == [["c1", "DD"], ["c2", "d3_idle_unreachable"]]
         and DA.diverged_assertion(nx, ny, {"c1", "c2"}) == [])


def stat_cases():
    case("S-1 sign test: n+ 10 n- 0 -> 2^-10; n+ 3 n- 1 -> 5/16; none changed -> 1",
         abs(DA.sign_test_p(10, 0) - 2 ** -10) < 1e-15 and abs(DA.sign_test_p(3, 1) - 5 / 16) < 1e-15
         and DA.sign_test_p(0, 0) == 1.0)
    case("S-2 the family: m = 28 = the movement round's 24 (unchanged) + D1-D4",
         len(DA.SIGN_KEYS) == 28 and [k for k, _l in DA.SIGN_KEYS[:24]] == [k for k, _l in DA.SIGN_KEYS_MVG]
         and [k for k, _l in DA.SIGN_KEYS[24:]] == ["d1_abandoned", "d2_returns", "d3_idle_unreachable", "d4_rb_end"])
    cells = ["set7/ring/%s_%s" % (s, w) for s in "ABCD" for w in "NSEW"] + \
        ["set8/ring/%s_%s" % (s, w) for s in "ABCD" for w in "NSEW"]
    cset = {c: c.split("/")[0] for c in cells}
    base = {c: {"ff_deaths": 1, "rescued": 3, "DD": 1} for c in cells}

    def reach(up, down, key="d1_abandoned"):
        nx = {c: dict(base[c]) for c in cells}
        ny = {c: dict(base[c]) for c in cells}
        for c in cells[:up]:
            ny[c][key] = 1
        for c in cells[up:up + down]:
            nx[c][key] = 1
        return DA.compare_counts(nx, ny, cset, set(cells))
    r10, r9, r1213, r1113 = reach(10, 0), reach(9, 0), reach(12, 1), reach(11, 2)
    case("H-1 Holm's reach at m = 28 (threshold 0.05 / 28 = 0.001786): D1 rising in 10 of 10 changed cells (p = "
         "2^-10) is REJECTED -> S5 FAIL",
         r10["sign"]["d1_abandoned"]["rejected"] and abs(r10["sign"]["d1_abandoned"]["threshold"] - 0.05 / 28) < 1e-15
         and not r10["S5"] and r10["sig_fail"] == ["d1_abandoned"], r10["sign"]["d1_abandoned"])
    case("H-2 9 of 9 rising (p = 2^-9 = 0.00195 > 0.001786) is NOT rejected", not r9["sign"]["d1_abandoned"]["rejected"]
         and r9["S5"], r9["sign"]["d1_abandoned"])
    case("H-3 12 of 13 (p = 14/8192 = 0.00171) is REJECTED; 11 of 13 (p = 92/8192) is not",
         r1213["sign"]["d1_abandoned"]["rejected"] and abs(r1213["sign"]["d1_abandoned"]["p"] - 14 / 8192) < 1e-15
         and not r1113["sign"]["d1_abandoned"]["rejected"], (r1213["sign"]["d1_abandoned"]["p"],
                                                             r1113["sign"]["d1_abandoned"]["p"]))
    pv = {k: 1.0 for k, _l in DA.SIGN_KEYS}
    pv["d3_idle_unreachable"], pv["of_broad"], pv["d2_returns"] = 0.0005, 0.0019, 0.0019
    h = DA.holm(pv)
    case("H-4 Holm step-down over the 28: the second-smallest p fails its threshold (0.05 / 27), so the third is not "
         "rejected either", h["d3_idle_unreachable"]["rejected"] and not h["of_broad"]["rejected"]
         and not h["d2_returns"]["rejected"])
    # R2 (10.5 F1 (ii)), known answers
    s7 = [c for c in cells if c.startswith("set7")]
    s8 = [c for c in cells if c.startswith("set8")]

    def r2(up7, down7, up8, down8, div=None):
        nx = {c: dict(base[c]) for c in cells}
        ny = {c: dict(base[c]) for c in cells}
        for c in s7[:up7]:
            ny[c]["ff_deaths"] = 2
        for c in s7[up7:up7 + down7]:
            ny[c]["ff_deaths"] = 0
        for c in s8[:up8]:
            ny[c]["ff_deaths"] = 2
        for c in s8[up8:up8 + down8]:
            ny[c]["ff_deaths"] = 0
        return DA.compare_counts(nx, ny, cset, set(cells) if div is None else div)
    r = r2(4, 0, 0, 4)
    case("R2-1 a set with 4 cells all up (p = 1/16): NO rejection (set 8 four down, pooled 0): F1 holds; the R0 reading "
         "(per-set literal) would fail and is reported only",
         not r["literal"]["F1 R2 set7"]["fail"] and abs(r["r2"]["set7"]["p"] - 1 / 16) < 1e-15
         and not r["literal"]["F1 ff deaths pooled"]["fail"] and r["S5"] and r["r0"]["fail"], r["r2"]["set7"])
    r = r2(5, 0, 0, 5)
    case("R2-2 5 all up: p = 1/32 <= 0.05 -> REJECTION, F1 FAILS in set 7 although pooled deaths do not rise",
         r["literal"]["F1 R2 set7"]["fail"] and abs(r["r2"]["set7"]["p"] - 1 / 32) < 1e-15
         and not r["literal"]["F1 ff deaths pooled"]["fail"] and r["lit_fail"] == ["F1 R2 set7"], r["lit_fail"])
    r = r2(3, 2, 0, 1)
    case("R2-3 3 up 2 down: p = 0.5 -> none (set 8 one down, pooled 0): F1 holds",
         not r["lit_fail"] and r["r2"]["set7"]["p"] == 0.5, (r["r2"]["set7"], r["lit_fail"]))
    r = r2(1, 0, 0, 0)
    case("R2-4 pooled +1 (one cell up) -> F1 FAILS on the pooled literal clause",
         r["lit_fail"] == ["F1 ff deaths pooled"], r["lit_fail"])
    r = r2(5, 0, 0, 5, div=set(s7[1:]) | set(s8))
    case("R2-5 the sign test runs over the DIVERGED cells only (one rising cell outside them: n+ 4, no rejection)",
         r["r2"]["set7"]["n_plus"] == 4 and not r["literal"]["F1 R2 set7"]["fail"], r["r2"]["set7"])
    # L2, L3
    nx = {c: dict(base[c]) for c in cells}
    ny = {c: dict(base[c]) for c in cells}
    ny[s7[0]]["rescued"] = 2
    ny[s8[0]]["rescued"] = 5
    r = DA.compare_counts(nx, ny, cset, set(cells))
    case("L2-1 rescued falls by one in set 7 (and rises by two in set 8): L2 FAILS in set 7 (each set literal) -> S4 FAIL",
         r["lit_fail"] == ["L2 rescued set7"] and not r["S4"], r["lit_fail"])
    ny = {c: dict(base[c]) for c in cells}
    ny[s7[0]]["DD"] = 2
    r = DA.compare_counts(nx, ny, cset, set(cells))
    ny2 = {c: dict(base[c]) for c in cells}
    ny2[s7[0]]["DD"], ny2[s8[0]]["DD"] = 2, 0
    r2_ = DA.compare_counts(nx, ny2, cset, set(cells))
    case("L3-1 pooled DD rises by one -> L3 FAILS (S4 FAIL); +1 / -1 (pooled 0) holds",
         r["lit_fail"] == ["L3 DD pooled"] and not r["S4"] and not r2_["lit_fail"] and r2_["S4"], (r["lit_fail"],
                                                                                                  r2_["lit_fail"]))
    # S3
    dx = {c: 1 for c in cells}
    dy = dict(dx)
    dy[s7[0]], dy[s8[0]] = 0, 0
    s3 = DA.s3_rule(dx, dy, cset)
    case("S3-1 pooled -2, set 7 -1, set 8 -1, -1 without the most favourable cell -> PASS",
         s3["pass"] and s3["pooled"] == -2 and s3["loo"] == -1 and s3["per_set"] == {"set7": -1, "set8": -1}, s3)
    dy = dict(dx)
    dy[s7[0]] = -1
    s3 = DA.s3_rule(dx, dy, cset)
    case("S3-2 a single cell carries the whole fall (-2): not robust (0 without it) -> FAIL", not s3["pass"]
         and s3["loo"] == 0, s3)
    dy = dict(dx)
    dy[s7[0]], dy[s7[1]], dy[s8[0]] = 0, 0, 2
    s3 = DA.s3_rule(dx, dy, cset)
    case("S3-3 pooled -1 but set 8 rises -> FAIL (each set must not rise)", not s3["pass"]
         and s3["per_set"]["set8"] == 1, s3)
    s6 = DA.s6_rule([0.001, 0.03, 0.002], [1.0] * 99 + [60.0])
    case("S6-1 median R 0.2 % but p99 60 ms per J point -> FAIL; no J point (vacuous) -> PASS",
         not s6["pass"] and DA.s6_rule([0.0], [])["pass"], s6)


def l4_cases():
    adv = {"set": "set7", "kind": "A", "resolved": True, "own": True, "others": False}
    post = {"set": "set7", "kind": "B", "resolved": True, "own": False, "others": True}
    unres_a = {"set": "set8", "kind": "A", "resolved": False, "own": None, "others": None}
    unres_b = {"set": "set8", "kind": "B", "resolved": False, "own": False, "others": False}
    r = DA.l4_counts([adv])
    case("L4-1 an ADVANCED (or new) dq1 death whose unit is alive at t in KO-OWN counts as CAUSED: 1 > 0 -> FAIL",
         r["caused"] == 1 and r["prevented"] == 0 and r["fail"], r)
    r = DA.l4_counts([post])
    case("L4-2 a POSTPONED dq0 death whose unit is dead by t in KO-OWN counts as PREVENTED: 0 vs 1 -> holds",
         r["caused"] == 0 and r["prevented"] == 1 and not r["fail"], r)
    r = DA.l4_counts([unres_a, unres_b])
    case("L4-3 an UNRESOLVED (A) counts as CAUSED; an unresolved (B) never as PREVENTED: 1 > 0 -> FAIL",
         r["caused"] == 1 and r["prevented"] == 0 and r["fail"], r)
    r = DA.l4_counts([adv, post])
    case("L4-4 a SWAP counts +1 / +1 -> a tie -> holds", r["caused"] == 1 and r["prevented"] == 1 and not r["fail"]
         and r["per_set"]["set7"] == [1, 1], r)
    r = DA.l4_counts([adv, dict(adv, set="set8"), post, dict(post, set="set8")])
    r2 = DA.l4_counts([adv, dict(adv, set="set8"), post])
    case("L4-5 a TIE passes (2 vs 2, per set 1 / 1); 2 vs 1 fails", not r["fail"] and r2["fail"]
         and r["per_set"] == {"set7": [1, 1], "set8": [1, 1]}, (r, r2))
    case("L4-6 KO-OTHERS alone reverses an (A): CAUSED", DA.l4_counts([dict(adv, own=False, others=True)])["caused"] == 1)
    rows25 = [[[U0, 1, 1, "available", 0, 0, 0, 0, None, None, 0, None],
               [U2, 1, 1, "available", 0, 0, int(t >= 20), 0, None, None, 0, None]] for t in range(1, 26)]
    case("L4-7 alive_at (verbatim): inside the rows the row decides; a COMPLETE run ending before t gives dead / alive "
         "by its rows; an incomplete one None",
         DA.alive_at(rows25, U2, 19) is True and DA.alive_at(rows25, U2, 20) is False
         and DA.alive_at(rows25, U2, 30, True) is False and DA.alive_at(rows25, U0, 30, True) is True
         and DA.alive_at(rows25, U0, 30, False) is None)


def ko_cases():
    """11.2's knockout evidence: dq1's recorded J decisions, the override's changes, the first change of a knockout."""
    dp = {"j_calls": [[10, "post", 1.0, 1, {"legacy": [[V0, U1]], "j_fills": [[V0, U0]], "stage3": [], "stage4": []}],
                      [14, "post", 1.0, 2, {"legacy": [[V2, U3]], "j_fills": [], "stage3": [], "stage4": []}],
                      [15, "pre", 1.0, 0]],
          "j_events": [{"step": 10, "phase": "post", "kind": "fill", "stage": 2, "victim_id": V0, "unit": U0},
                       {"step": 14, "phase": "post", "kind": "nearest_barred", "stage": 3, "victim_id": V1,
                        "unit": U1, "barred": [U2]},
                       {"step": 14, "phase": "post", "kind": "replace", "stage": 3, "victim_id": V1, "unit": U2,
                        "old_units": [U1]},
                       {"step": 14, "phase": "post", "kind": "second_fill_refused", "stage": 4, "victim_id": V2,
                        "unit": U1}]}
    jp = DA.j_decision_points(dp)
    case("KO-1 j_decision_points: per J point the recorded counterfactual (j_calls 'legacy') and J's stage-2 / 3 / 4 "
         "decisions from dp.j_events (refused / aborted included with ok False; nearest_barred skipped)",
         jp == [[10, "post", [[V0, U1]], [[V0, U0, True]], [], []],
                [14, "post", [[V2, U3]], [], [["replace", V1, U2, [U1], True]], [[V2, U1, False]]]], jp)
    own0 = DA.override_changes(10, "post", [[V0, U1]], [[V0, U0, True]], [], [], {U0})
    oth0 = DA.override_changes(10, "post", [[V0, U1]], [[V0, U0, True]], [], [], {U1, U2})
    same = DA.override_changes(10, "post", [[V0, U0]], [[V0, U0, True]], [], [], {U0})
    rel = DA.override_changes(14, "post", [[V2, U3]], [], [["replace", V1, U2, [U1], True]], [[V2, U1, False]],
                              {U1})
    case("KO-2 override_changes (11.2): J's bind of a knocked-out unit -> drop_bind (1); the counterfactual's pair of a "
         "knocked-out unit -> ko_today and J's bind on that victim -> drop_victim (3); a counterfactual pair EQUAL to J's "
         "own fill -> no change; a replacement releasing a knocked-out unit -> drop_release, and that unit's step-4 bind "
         "-> drop_bind (it is in K)",
         own0 == [[10, "post", U0, V0, "drop_bind"]]
         and oth0 == [[10, "post", U0, V0, "drop_victim"], [10, "post", U1, V0, "ko_today"]] and same == []
         and rel == [[14, "post", U1, V1, "drop_release"], [14, "post", U1, V2, "drop_bind"]], (own0, oth0, same, rel))
    unrel = DA.override_changes(14, "post", [], [], [["replace", V1, U2, [U1], True]], [[V2, U1, True]], {U2})
    case("KO-3 a dropped challenger (2) leaves its incumbent bound: the incumbent's step-4 second fill -> "
         "drop_unreleased (keys in change order: unit, then victim)",
         unrel == [[14, "post", U1, V2, "drop_unreleased"], [14, "post", U2, V1, "drop_challenger"]], unrel)
    units = [U0, U1, U2, U3]
    case("KO-4 ko_first: KO-OWN of ff_unit_0 to 40 -> (10, drop_bind); KO-OTHERS ('!ff_unit_0') -> its first change "
         "(10, drop_victim of ff_unit_0, ordered before ff_unit_1's ko_today); KO-LAST with a phase rule (14 post) of "
         "ff_unit_1 -> drop_release; KO-OWN of ff_unit_3 before 14 -> EMPTY (None); a rule for J-pre only at 10 -> None",
         DA.ko_first(jp, [{"unit": U0, "from": 0, "to": 40}], units) == [10, "post", U0, V0, "drop_bind"]
         and DA.ko_first(jp, [{"unit": "!" + U0, "from": 0, "to": 40}], units) == [10, "post", U0, V0, "drop_victim"]
         and DA.ko_first(jp, [{"unit": U1, "from": 14, "to": 14, "phase": "post"}], units) == [14, "post", U1, V1,
                                                                                                "drop_release"]
         and DA.ko_first(jp, [{"unit": U3, "from": 0, "to": 13}], units) is None
         and DA.ko_first(jp, [{"unit": U0, "from": 10, "to": 10, "phase": "pre"}], units) is None)
    x = {"rows_ff": [[1]], "rows_vic": [], "rows_uav": [], "rows_dec": [], "rows_trig": [],
         "dp": {"commands": [1], "j_events": [{"k": 1}]}, "mv_events": [], "eval": {"rescued": 1}}
    case("KO-5 R0 reproduction compares every per-step row, the commands, the J EVENTS, the movement events, eval and "
         "stdout", DA.r0_reproduces(x, copy.deepcopy(x), "s", "s") == []
         and DA.r0_reproduces(x, dict(x, dp={"commands": [1], "j_events": []}), "s", "s") == ["dp.j_events"]
         and DA.r0_reproduces(x, dict(x, eval={"rescued": 2}), "s", "t") == ["eval", "stdout"])


def owner_cases():
    case("OWN-1 10.3 ownership (X-11 (a)): a movement / guard zero in dq0 or dqR -> STOP for a maintainer ruling; Z5 / "
         "Z6 / SM there -> STOP; a dispatch zero there -> reported (J off); every zero in dq1 -> an S2 FAIL",
         DA.zero_owners("Zm-a", "0") == "STOP-RULING" and DA.zero_owners("Zg-1", "R") == "STOP-RULING"
         and DA.zero_owners("Z5", "0") == "STOP" and DA.zero_owners("Z6", "R") == "STOP"
         and DA.zero_owners("SM", "0") == "STOP" and DA.zero_owners("M6", "0") == "REPORTED"
         and all(DA.zero_owners(z, "1") == "S2" for z in DA.ZERO_ORDER))
    case("OUT-1 FULL order (verbatim): S1 fails -> STOP; S2 / S4 / S5 -> FAIL; S3 -> NOT SHOWN; S6 -> NOT READY; PASS",
         DA.full_verdict(False, True, True, True, True, True) == "STOP"
         and DA.full_verdict(True, False, True, True, True, True) == "FAIL"
         and DA.full_verdict(True, True, True, True, False, True) == "FAIL"
         and DA.full_verdict(True, True, False, True, True, False) == "NOT SHOWN"
         and DA.full_verdict(True, True, True, True, True, False) == "NOT READY"
         and DA.full_verdict(True, True, True, True, True, True) == "PASS")
    outs = [DA.decide(True, False, "PASS"), DA.decide(False, True, "PASS"), DA.decide(False, False, "FAIL"),
            DA.decide(False, False, "NOT SHOWN"), DA.decide(False, False, "NOT READY"), DA.decide(False, False, "PASS")]
    case("OUT-2 10.8's outcomes in order: a dq0 / dqR failure -> 1 (even with a PASS); S1 -> 2; FAIL -> 3; NOT SHOWN -> "
         "4; NOT READY -> 5; PASS -> 6", outs == [1, 2, 3, 4, 5, 6], outs)
    t = DA.OUTCOME_TEXT
    case("OUT-3 the texts name decision 0.2: FAIL and NOT SHOWN both keep DISPATCH_JOINT and DISPATCH_REASSIGN at 0, "
         "the code NOT merged and no further dispatch round; PASS recommends shipping both = 1",
         all("DISPATCH_JOINT and DISPATCH_REASSIGN stay 0" in t[o] and "NOT merged" in t[o]
             and "NO further dispatch round" in t[o] for o in (3, 4))
         and "DISPATCH_JOINT = 1 and DISPATCH_REASSIGN = 1" in t[6] and "STOP" in t[1] and "STOP" in t[2])


def header_cases():
    ok, _l = DA.hash_checks()
    with open(os.path.join(HERE, "dispatch2_part1.txt"), encoding="utf-8") as fh:
        text = fh.read()
    e10, l10 = DA.hash_checks(text.replace("median R <= 2 %; p99 <= 50 ms per J point", "median R <= 3 %; p99 <= 50 ms "
                                                                                          "per J point"))
    e19, l19 = DA.hash_checks(text.replace("X-15 the stranding guard is not run inside J.",
                                           "X-15 the stranding guard is run inside J."))
    e16, _l = DA.hash_checks(text.replace("P.7 The no-flip-flop theorem holds unchanged.",
                                          "P.7 The no-flip-flop theorem holds."))
    app, lapp = DA.hash_checks(text.rstrip("\n") + "\n\n" + "=" * 80 + "\n21. AMENDMENT A3 - A LATER READING\n" +
                               "=" * 80 + "\n    text\n")
    case("HASH-1 (12.2) the working dispatch2_part1.txt passes (sections 0, 2-15 and 19 at their frozen sha256, also at "
         "ba647655 / 87a93cda); one edited character in section 10 or in the rulings section 19 REFUSES; an edit in "
         "section 16 (not hashed) does not; an appended section 21 leaves every hashed section identical (reported)",
         ok and not e10 and not e19 and e16 and app
         and any(ln.lstrip().startswith("section 10") and "DIFFERS" in ln for ln in l10)
         and any(ln.lstrip().startswith("section 19") and "DIFFERS" in ln for ln in l19)
         and any("section 21" in ln and "info" in ln for ln in lapp), [ln for ln in l10 + l19 if "DIFFERS" in ln][:2])
    txt = "x\n" + "=" * 10 + "\n3. THREE\n" + "=" * 10 + "\n a\n\n" + "=" * 10 + "\n4. FOUR\n b\n"
    case("HASH-2 section extraction: from the 'N. ' header to the line before the next one, trailing blank / '=' lines "
         "dropped; a '4.1 ' sub-header is no boundary; EOF ends the last",
         DA.spec_section(txt, 3) == "3. THREE\n" + "=" * 10 + "\n a" and DA.spec_section(txt, 4) == "4. FOUR\n b"
         and DA.spec_section("1. A\n1.1 B\n c\n", 1) == "1. A\n1.1 B\n c" and DA.spec_section(txt, 5) is None)
    vok, vl = DA.verbatim_check()
    case("VERB-1 the ported functions are verbatim: _mvg_analyze.py at 897e93b5 and _dp_analyze.py at cc8d653c", vok, vl)
    with contextlib.redirect_stdout(io.StringIO()):
        frozen = DA.load_seeds()
    case("SEED-1 the seed rule recomputed for sets 1-8 (set 7 A_N = 575201, set 8 D_W = 741156; set 7 = 575201-575216)",
         frozen is not None and ["A_N", "A", "north", "575201"] in frozen["set7"]
         and ["D_W", "D", "west", "741156"] in frozen["set8"] and len(frozen["set7"]) == 16
         and sorted(int(r[3]) for r in frozen["set7"]) == list(range(575201, 575217)))
    tmp = tempfile.mkdtemp(prefix="dq_seed_")
    try:
        doc = json.load(open(os.path.join(HERE, "_dq_seeds.txt"), encoding="utf-8"))
        doc["set8"][0][3] = "741199"
        p = os.path.join(tmp, "_dq_seeds.txt")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh)
        with contextlib.redirect_stdout(io.StringIO()):
            badseed = DA.load_seeds(p)
        doc2 = json.load(open(os.path.join(HERE, "_dq_seeds.txt"), encoding="utf-8"))
        doc2["bases"]["set7"] = 575221
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc2, fh)
        with contextlib.redirect_stdout(io.StringIO()):
            badbase = DA.load_seeds(p)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    case("SEED-2 a seed off the rule, or a base other than the frozen 575201 / 741141, STOPS (None)", badseed is None
         and badbase is None)
    cells = DA.screen_cells(frozen, types.SimpleNamespace(smoke=None))
    case("CELLS-1 the screen: 64 cells (sets 7-8 x ring / uniform x 16), arms R / 0 / 1, all fresh",
         len(cells) == 64 and all(c["fresh"] and c["arms"] == ("R", "0", "1") for c in cells)
         and {c["set"] for c in cells} == {"set7", "set8"})


# ================================================================================================ file fixtures
SCEN = ("A", "north", 575201)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh)


def queue_line(arm, tmp, k=7):
    """A frozen-queue line of the ring A_N cell of set k (seed 575201 / 741141), section 9's run line."""
    name = "%sr%d_A_N" % (DA.ARM_TAG[arm], k)
    seed = DA.EXPECTED_BASES["set%d" % k]
    out = os.path.join(tmp, "_sd_%s.json" % name)
    sets = ["--set", "GLOBAL_PLANNER_MODE=0", "--set", "VICTIM_SPAWN_MODE=0", "--set", "FF_APPROACH_PATH=1", "--set",
            "FF_RETREAT_KEEP_APPROACH=1", "--set", "FF_FIX_STRANDING_GUARD=1"]
    if arm in ("0", "1"):
        sets += ["--set", "DISPATCH_JOINT=%s" % arm, "--set", "DISPATCH_REASSIGN=%s" % arm]
    argv = [os.path.join(HERE, "_dq_probe.py"), "--crn", "--hazard", "--", "--repo", DA.ARM_REPO[arm], "--scenario",
            SCEN[0], "--wind", SCEN[1], "--seed", str(seed)] + sets + ["--steps", "360", "--set", "BATCH_SIZE=360",
                                                                       "--out", out, "--tag", name]
    return {"name": name, "argv": argv, "out": out, "cwd": DA.ARM_REPO[arm]}


def ffrow(uid, dead=0):
    return [uid, 1, 1, "available", 0, 0, dead, 0, None, None, 0, None]


def mini_record(arm, line, deaths=None, eval_=None, j_calls=None, steps_done=360, terminal=None, crashed=None):
    """A minimal dq_probe v1 record of the arm that prov_run accepts and digest reads (no outcome is asserted on it)."""
    deaths = deaths or {}
    sd = DA.sd_args(line["argv"])
    sets = DA.parse_sets(sd)
    joint = arm == "1"
    sw = {"FF_APPROACH_PATH": True, "FF_RETREAT_KEEP_APPROACH": True, "FF_FIX_STRANDING_GUARD": True}
    raw = {k: ("None" if arm == "R" else arm) for k in ("DISPATCH_JOINT", "DISPATCH_REASSIGN")}
    # the dispatch parameters as dq_probe v1 records them (absent at main: 'None' / None); the self-test's own copy of
    # the shipped values (D-8: 10 / 5 / 3)
    shipped = (("DISPATCH_STALL_STEPS", 10), ("DISPATCH_MARGIN_STEPS", 5), ("DISPATCH_MARGIN_PERSIST", 3))
    raw.update({k: ("None" if arm == "R" else repr(v)) for k, v in shipped})
    smp = dict(zip(("S", "M", "P"), (None,) * 3 if arm == "R" else [v for _k, v in shipped]))
    jc = list(j_calls or [])
    rows_ff = [[ffrow(u, dead=int(deaths.get(u) is not None and t >= deaths[u])) for u in (U0, U1, U2)]
               for t in range(1, steps_done + 1)]
    return {"repo": DA.ARM_REPO[arm], "head": "x", "argv": sd, "steps": 360, "steps_done": steps_done,
            "terminal_step": terminal, "crashed": crashed, "scenario": DA.arg_of(sd, "--scenario"),
            "wind": DA.arg_of(sd, "--wind"), "seed": int(DA.arg_of(sd, "--seed")),
            "extra_params": sets, "fb3": {"crn": {"on": True, "crn_draws": 7}, "eff": {"victim_spawn_mode": 0}},
            "dp": {"probe": DA.DP_PROBE, "commands": [], "releases": [], "errors": [], "binders": [], "waiting": [],
                   "waiting_custody": [], "m3a": [], "invariant": [], "m8": [], "m9": [], "writeoffs_avoided": [],
                   "switches": {"joint_on": joint, "reassign_on": joint}, "j_calls": jc,
                   "j_timing": [[c[0], c[1], 1.0, 0.5, 0.5, 0] for c in jc], "j_events": [], "j_detail": [],
                   "ledger": {}, "timing": {"j_ms_total": 0.5 * len(jc), "j_ms_raw_total": 1.0 * len(jc)},
                   "rc_chain": 0},
            "ud": {"probe": DA.DQ_PROBE, "errors": [], "shadow_mismatch": [], "cmd_ctx": [], "rel_ctx": [], "kicks": [],
                   "decisions": [], "switches": dict(sw, DISPATCH_URGENCY=False, FF_CARRY_REPLAN=False)},
            "mvg": {"probe": DA.DQ_PROBE, "errors": [], "switches": dict(sw), "mp_mismatch": [], "replica": {},
                    "guard": {"cols": list(DA.GUARD_COLS), "rows": []}},
            "dq": {"probe": DA.DQ_PROBE, "errors": [], "switches": dict(sw, raw=raw, joint_on=joint, reassign_on=joint,
                                                                         **smp),
                   "sample": {"cols": list(DA.SAMPLE_COLS), "unit_cols": list(DA.SAMPLE_UNIT_COLS),
                              "rows": [[t, [], [], [], [], []] for t in range(1, steps_done + 1)]},
                   "ff_log": {"cols": list(DA.FFLOG_COLS), "rows": []}, "zr1": {"jpoints": 0},
                   "footprint": {"jpoints": 0, "errors": []}},
            "mv": {"cols": list(DA.MV_COLS), "rows": []}, "mv_events": [], "rows_ff": rows_ff,
            "rows_vic": [[[V0, 5, 5, "candidate", "candidate", "", 0, 0, 0, 0]] for _ in range(steps_done)],
            "rows_uav": [[["uav_1", 1, 1, "victim_searcher", 50.0, False, False, [0, 0], "x"]]
                         for _ in range(steps_done)],
            "rows_dec": [], "rows_trig": [],
            "params": dict({"NUM_FIREFIGHTERS": 3, "NUM_VICTIMS": 1},
                           **({} if arm == "R" else {"DISPATCH_JOINT": int(arm), "DISPATCH_REASSIGN": int(arm)})),
            "effective": {"global_planner_mode": 0, "base_station_mode": 3},
            "eval": eval_ or {"rescued": 1, "firefighter_deaths": len(deaths)}, "depots": {"cells": [[0, 45]]},
            "grid": [50, 50], "stdout_sha": "", "stdout_tags": {}, "inline_violations": [], "warning_count": 0,
            "mf2": {"probe": "mf2", "fleet": [1]}, "mr": {"probe": "mr"}, "ut": {"probe": "ut"}}


def write_run(line, d, signature=True):
    write_json(line["out"], d)
    with open(line["out"][:-5] + ".stdout.txt", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("[Victim Detection] step=3 UAV-1 detected victim_0 at (5, 5)\n")
    if signature:
        with open(line["out"] + ".argv", "w", encoding="utf-8") as fh:
            fh.write(DA.POOL.signature(line))


def validity_cases():
    """prov_run (section 1) on hand-built records of each arm."""
    tmp = tempfile.mkdtemp(prefix="dq_valid_")
    try:
        cell = {"scen": SCEN[0], "wind": SCEN[1], "seed": SCEN[2]}
        o = types.SimpleNamespace(smoke=None, head=None)
        res = {}
        for arm in DA.ARMS:
            line = queue_line(arm, tmp)
            d = mini_record(arm, line)
            write_run(line, d)
            res[arm] = DA.prov_run(d, line["out"], line, cell, arm, o)
        case("V-1 a minimal valid record of each arm (dqR at main with no DISPATCH_* key, dq0 pinned 0 off, dq1 pinned 1 "
             "on) passes prov_run", all(not w and c is None and s is None for w, c, s in res.values()), res)
        line = queue_line("1", tmp)
        d = mini_record("1", line)
        bads = {
            "J off arm with J points": ("0", lambda x: x["dp"].update(j_calls=[[1, "pre", 1.0, 0]],
                                                                       j_timing=[[1, "pre", 1.0, 1.0, 1.0, 0]])),
            "dq1 kick records": ("1", lambda x: x["ud"].update(kicks=[{"i": 0}])),
            "dq1 pinned 0": ("1", lambda x: x["dq"]["switches"]["raw"].update(DISPATCH_JOINT="0")),
            "dp_probe v2": ("1", lambda x: x["dp"].update(probe="dp_probe v2")),
            "mvg_probe v1": ("1", lambda x: x["mvg"].update(probe="mvg_probe v1")),
            "sample cols": ("1", lambda x: x["dq"]["sample"].update(cols=["step"])),
            "footprint errors": ("1", lambda x: x["dq"]["footprint"].update(errors=[[1, "post", "x"]])),
            "dq errors": ("1", lambda x: x["dq"].update(errors=["sample_purity: x"])),
            "0 CRN draws": ("1", lambda x: x["fb3"].update(crn={"on": True, "crn_draws": 0})),
            "dqR with a DISPATCH key": ("R", lambda x: x["dq"]["switches"]["raw"].update(DISPATCH_JOINT="0")),
        }
        flagged = {}
        for name, (arm, mut) in bads.items():
            ln = queue_line(arm, tmp)
            x = mini_record(arm, ln)
            mut(x)
            w, _c, _s = DA.prov_run(x, ln["out"], ln, cell, arm, o)
            flagged[name] = bool(w)
        case("V-2 INVALID (a tooling defect): J points in a J-off arm; a kick record in dq1 (the U1 shadow is gated off, "
             "12.1); dq1's dispatch switches not pinned 1; a dp_probe v2 / mvg_probe v1 record (mixed versions); the "
             "sample's columns; footprint / dq errors; 0 CRN draws; a DISPATCH_* key in dqR",
             all(flagged.values()), flagged)
        _w, _c, stop = DA.prov_run(d, line["out"], line, dict(cell, seed=575202), "1", o)
        _w2, crash, _s = DA.prov_run(dict(d, crashed={"type": "ValueError", "step": 17}, steps_done=17), line["out"],
                                     line, cell, "1", o)
        case("V-3 a seed other than the frozen cell's is a STOP; a crash is Z6 material (never INVALID)",
             stop is not None and "SEED MISMATCH" in stop and crash is not None and "crashed ValueError" in crash,
             (stop, crash))
        # provenance against real commits: the dispatch head (HEAD) for dq0 / dq1, main 897e93b5 for dqR
        head_sha = DA.git("rev-parse", "HEAD")[1].decode().strip()
        pick = lambda c, rel: sorted(DA.committed_shas(c, rel) or ["missing"])[0]             # noqa: E731
        rels = DA.MVG_SRC_REQUIRED + (DA.JD_REL,)
        rec1 = {sec: {"src_sha": {r: pick(head_sha, r) for r in rels}} for sec in ("dp", "ud", "mvg", "dq")}
        recR = {sec: {"src_sha": {r: pick(DA.BASE, r) for r in DA.MVG_SRC_REQUIRED}} for sec in ("dp", "ud", "mvg",
                                                                                                "dq")}
        bad1 = copy.deepcopy(rec1)
        bad1["dq"]["src_sha"]["agents.py"] = "0" * 64
        badR = copy.deepcopy(recR)
        badR["dq"]["src_sha"][DA.JD_REL] = pick(head_sha, DA.JD_REL)
        miss1 = copy.deepcopy(rec1)
        del miss1["dq"]["src_sha"][DA.JD_REL]
        lf_probe = DA.lf_sha_at(head_sha, DA.PROBE_REL)
        ins = DA.instrument_check({"dq": {"probe_sha": "1" * 64, "r1_shadow_sha": "2" * 64},
                                   "mvg": {"probe_sha": "1" * 64, "u1_shadow_sha": "3" * 64}}, head_sha)
        case("PROV-1 provenance at real commits: dq1's source shas equal to the files at the dispatch head pass, an "
             "agents.py sha that is not the committed file's is 'ran uncommitted source', a dq record not naming the "
             "joint dispatcher is INVALID; dqR's shas at main 897e93b5 pass and a dqR naming a joint_dispatch module is "
             "INVALID; an instrument sha that is not outputs/_dq_probe.py's at --head (or a probe absent from that commit) "
             "is INVALID",
             not DA.src_check(rec1, head_sha, "1") and any("ran uncommitted source" in w
                                                            for w in DA.src_check(bad1, head_sha, "1"))
             and any("joint_dispatch" in w or DA.JD_REL in w for w in DA.src_check(miss1, head_sha, "1"))
             and not DA.src_check(recR, DA.BASE, "R") and any("no joint_dispatch module" in w
                                                              for w in DA.src_check(badR, DA.BASE, "R"))
             and bool(ins) and (lf_probe is None or any("uncommitted instrument" in w for w in ins)),
             (DA.src_check(bad1, head_sha, "1"), DA.src_check(badR, DA.BASE, "R"), ins[:2]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def w3_tools():
    """The REAL frozen W3 generator and replay tool (outputs/_dq_w3_queue.py, outputs/_dq_replay.py): the analyzer's
    side of their contract is what is tested. (module, module) or (None, None) when absent (the W3 cases then FAIL)."""
    try:
        saved = sys.argv
        sys.argv = saved[:1]
        try:
            import _dq_w3_queue as w3q  # noqa: E402
            import _dq_replay as rp  # noqa: E402
        finally:
            sys.argv = saved
        return w3q, rp
    except Exception:                         # noqa: BLE001
        return None, None


class W3Fixture:
    """A synthetic screen in a temporary directory: the frozen W1 / W2 queues, the records of every arm, the REAL
    generator's W3 queue and candidates file (its Q_W3 / CANDS / W3_DIR redirected), and helpers to write the replays
    and their knockout logs."""

    def __init__(self, ks, deaths, dq1_dp, w3q):
        self.tmp = tempfile.mkdtemp(prefix="dq_w3_")
        self.saved = (DA.Q_W1, DA.Q_W2, dict(DA._W3Q), DA.run_path, w3q.Q_W3, w3q.CANDS, w3q.W3_DIR)
        self.w3q = w3q
        DA.Q_W1, DA.Q_W2 = os.path.join(self.tmp, "_dq_q_w1.jsonl"), os.path.join(self.tmp, "_dq_q_w2.jsonl")
        w3q.Q_W3, w3q.CANDS, w3q.W3_DIR = (os.path.join(self.tmp, "_dq_q_w3.jsonl"),
                                           os.path.join(self.tmp, "_dq_w3_candidates.json"), self.tmp)
        DA._W3Q.clear()
        DA._W3Q.update(mod=w3q, why=None)
        self.dq1_dp = dq1_dp
        self.lines, self.w1, self.w2 = {}, [], []
        for k in ks:
            for a in DA.ARMS:
                ln = queue_line(a, self.tmp, k)
                self.lines[(k, a)] = ln
                write_run(ln, self.record(a, ln, deaths[k][a]))
                (self.w2 if a == "1" else self.w1).append(ln)
        for p, ls in ((DA.Q_W1, self.w1), (DA.Q_W2, self.w2)):
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("".join(json.dumps(ln) + "\n" for ln in ls))
        frozen = {s: DA.seed_rows(b) for s, b in DA.EXPECTED_BASES.items()}
        ids = {"set%d/ring/A_N" % k for k in ks}
        self.cells = [c for c in DA.screen_cells(frozen, types.SimpleNamespace(smoke=None)) if c["id"] in ids]
        DA.run_path = lambda arm, c, opts: self.lines[(c["k"], arm)]["out"]
        self.queues = {os.path.normcase(ln["out"]): ("w", ln) for ln in self.lines.values()}

    def record(self, arm, line, dead, eval_=None):
        d = mini_record(arm, line, dead, eval_=eval_, j_calls=self.dq1_dp["j_calls"] if arm == "1" else None)
        if arm == "1":
            d["dp"]["j_events"] = copy.deepcopy(self.dq1_dp.get("j_events") or [])
        return d

    def generate(self, recs):
        """The REAL generator's plan on the records' compacts, frozen as its build would write it."""
        comps = {self.lines[(c["k"], a)]["name"]: r["g"][a]["w3c"] for c, r in zip(self.cells, recs)
                 for a in ("0", "1")}
        doc, rlines = self.w3q.build_plan(self.w1, self.w2, comps)
        shas = {self.lines[(c["k"], a)]["name"]: DA.sha_file(self.lines[(c["k"], a)]["out"]) for c in self.cells
                for a in ("0", "1")}
        full = self.w3q.full_doc(doc, shas, hashlib.sha256(open(DA.Q_W1, "rb").read()).hexdigest(),
                                 hashlib.sha256(open(DA.Q_W2, "rb").read()).hexdigest())
        with open(self.w3q.CANDS, "wb") as fh:
            fh.write(self.w3q.doc_bytes(full))
        with open(self.w3q.Q_W3, "wb") as fh:
            fh.write(DA.lf("".join(json.dumps(ln) + "\n" for ln in rlines)).encode("utf-8"))
        self.byn = {ln["name"]: ln for ln in rlines}
        return doc, rlines

    def replay(self, name, dead, applied, eval_=None):
        ln = self.byn[name]
        write_run(ln, self.record("1", ln, dead, eval_=eval_))
        own = ln["argv"][1:ln["argv"].index("--")]
        rules = json.loads(own[own.index("--ko") + 1]) if "--ko" in own else []
        write_json(own[own.index("--kolog") + 1], {"version": DA.REPLAY_VERSION, "replay_sha": "x", "probe_sha": "x",
                                                    "argv": ln["argv"][1:], "ko_rules": rules, "ko_log": [],
                                                    "ko_applied": applied, "jpoints": [], "errors": []})

    def close(self):
        (DA.Q_W1, DA.Q_W2, w3s, DA.run_path, self.w3q.Q_W3, self.w3q.CANDS, self.w3q.W3_DIR) = self.saved
        DA._W3Q.clear()
        DA._W3Q.update(w3s)
        shutil.rmtree(self.tmp, ignore_errors=True)


# dq1's recorded J decisions in the W3 fixtures: at J-post 10 J fills victim_0 with ff_unit_0 while the counterfactual
# (legacy) binds ff_unit_1 there; at J-post 12 J fills victim_1 with ff_unit_2 (the counterfactual binds nobody)
W3_DP = {"j_calls": [[10, "post", 1.0, 1, {"legacy": [[V0, U1]], "j_fills": [[V0, U0]], "stage3": [], "stage4": []}],
                     [12, "post", 1.0, 1, {"legacy": [], "j_fills": [[V1, U2]], "stage3": [], "stage4": []}]],
         "j_events": [{"step": 10, "phase": "post", "kind": "fill", "stage": 2, "victim_id": V0, "unit": U0},
                      {"step": 12, "phase": "post", "kind": "fill", "stage": 2, "victim_id": V1, "unit": U2}]}


def w3_end_to_end():
    """W3 VALIDITY end to end (11.2-11.3) with the REAL generator on synthetic files: dq0 loses ff_unit_0 at 60 and
    ff_unit_2 at 30; dq1 loses ff_unit_0 at 40 -> an (A) candidate ff_unit_0 (t 40) and a (B) candidate ff_unit_2 (t
    30); the knockout logs hold the changes 11.2's override makes on dq1's recorded J decisions."""
    w3q, _rp = w3_tools()
    if w3q is None:
        case("W3-0 the frozen W3 generator outputs/_dq_w3_queue.py and outputs/_dq_replay.py are importable", False)
        return
    deaths = {7: {"R": {U0: 60, U2: 30}, "0": {U0: 60, U2: 30}, "1": {U0: 40}}}
    fx = W3Fixture((7,), deaths, W3_DP, w3q)
    try:
        opts = types.SimpleNamespace(smoke=None, head=None, zeros_only=False, w3_unresolved=[])
        with contextlib.redirect_stdout(io.StringIO()):
            recs = DA.process(fx.cells, opts, fx.queues)
        doc, rlines = fx.generate(recs)
        p = "dqrp_dq1r7_A_N_"
        names = [ln["name"] for ln in rlines]
        good = {"R0": (deaths[7]["1"], []),
                "f0_KOown": ({}, [[10, "post", U0, V0, "drop_bind"]]),
                "f0_KOlast": ({}, [[10, "post", U0, V0, "drop_bind"]]),
                "f0_KOothers": ({U0: 40}, [[10, "post", U0, V0, "drop_victim"], [10, "post", U1, V0, "ko_today"],
                                           [12, "post", U2, V1, "drop_bind"]]),
                "f2_KOown": ({U0: 40}, [[12, "post", U2, V1, "drop_bind"]]),
                "f2_KOothers": ({U0: 40, U2: 30}, [[10, "post", U0, V0, "drop_bind"], [10, "post", U1, V0, "ko_today"]])}
        for suffix, (dead, applied) in good.items():
            fx.replay(p + suffix, dead, applied)
        with contextlib.redirect_stdout(io.StringIO()):
            res = DA.w3_validity(recs, opts)
        items = {(it["kind"], it["unit"]): it for it in res["items"]}
        ia, ib = items.get(("A", U0)), items.get(("B", U2))
        case("W3-1 the REAL generator's lines re-derived and validated (R0; KO-OWN / KO-LAST / KO-OTHERS of the (A) unit; "
             "KO-OWN / KO-OTHERS of the (B) unit); R0 reproduces dq1; every knockout's first change (the analyzer's own "
             "reading of 11.2) equals the rule's and is in its ko_applied; (A) ff_unit_0 alive at 40 in KO-OWN -> "
             "CAUSED; (B) ff_unit_2 dead by 30 in KO-OTHERS -> PREVENTED; L4 1 vs 1, a tie -> holds; the hybrid "
             "diagnostic reported per knockout",
             names == [p + s for s in good] and res["complete"] and not res["conflicts"]
             and res["r0"]["set7/ring/A_N"] == [] and ia["resolved"] and ia["own"] is True and ib["resolved"]
             and ib["others"] is False and res["l4"]["caused"] == 1 and res["l4"]["prevented"] == 1
             and not res["l4"]["fail"] and isinstance(ia["hybrid"].get("KOown"), bool),
             (res.get("state"), names, res["conflicts"], ia, ib))
        fx.replay(p + "R0", deaths[7]["1"], [], eval_={"rescued": 9})
        with contextlib.redirect_stdout(io.StringIO()):
            res = DA.w3_validity(recs, opts)
        case("W3-2 R0 does not reproduce dq1 (eval): the cell's candidates are UNRESOLVED - the (A) counts as CAUSED, the "
             "(B) not as PREVENTED: 1 > 0 -> FAIL", res["complete"] and res["r0"]["set7/ring/A_N"] == ["eval"]
             and res["l4"]["caused"] == 1 and res["l4"]["prevented"] == 0 and res["l4"]["fail"], res.get("l4"))
        fx.replay(p + "R0", deaths[7]["1"], [])
        fx.replay(p + "f2_KOothers", {U0: 40, U2: 30}, [[10, "post", U1, V0, "ko_today"]])
        with contextlib.redirect_stdout(io.StringIO()):
            res = DA.w3_validity(recs, opts)
        ib = {(it["kind"], it["unit"]): it for it in res["items"]}[("B", U2)]
        case("W3-3 a knockout log lacking dq1's first changed J decision (KO-OTHERS of ff_unit_2: ff_unit_0's drop_bind "
             "at J-post 10) is conflicting evidence: the (B) is UNRESOLVED, not PREVENTED",
             res["conflicts"] and res["conflicts"][0][1] == [10, "post", U0, V0, "drop_bind"] and not ib["resolved"]
             and res["l4"]["prevented"] == 0, (res["conflicts"], ib))
        fx.replay(p + "f2_KOothers", *good["f2_KOothers"])
        os.remove(fx.byn[p + "f0_KOlast"]["out"])
        with contextlib.redirect_stdout(io.StringIO()):
            res = DA.w3_validity(recs, opts)
        case("W3-4 a missing replay leaves W3 INCOMPLETE (no L4 count, hence no verdict)",
             not res["complete"] and "l4" not in res and "INCOMPLETE" in res["state"], res["state"])
        fx.replay(p + "f0_KOlast", *good["f0_KOlast"])
        kl = fx.byn[p + "f0_KOown"]["argv"]
        kpath = kl[kl.index("--kolog") + 1]
        k = json.load(open(kpath, encoding="utf-8"))
        write_json(kpath, dict(k, errors=["rules name units the model does not have: ['ff_unit_9']"]))
        with contextlib.redirect_stdout(io.StringIO()):
            res = DA.w3_validity(recs, opts)
        ia = {(it["kind"], it["unit"]): it for it in res["items"]}[("A", U0)]
        case("W3-5 a knockout log with an error is an INVALID replay: W3 INCOMPLETE",
             not res["complete"] and "INVALID" in res["state"], res["state"])
        write_json(kpath, k)
        d0 = json.load(open(fx.lines[(7, "0")]["out"], encoding="utf-8"))
        write_json(fx.lines[(7, "0")]["out"], dict(d0, eval={"rescued": 2}))
        with contextlib.redirect_stdout(io.StringIO()):
            res = DA.w3_validity(recs, opts)
        case("W3-6 a W1 / W2 record changed after W3 was generated: REFUSED", res["refused"]
             and "record" in res["state"], res["state"])
        write_json(fx.lines[(7, "0")]["out"], d0)
        cands = json.load(open(w3q.CANDS, encoding="utf-8"))
        cands["entries"][0]["A"][0]["first"]["KOown"] = [10, "post", U0, V0, "drop_victim"]
        with open(w3q.CANDS, "wb") as fh:
            fh.write(w3q.doc_bytes(cands))
        with contextlib.redirect_stdout(io.StringIO()):
            res = DA.w3_validity(recs, opts)
        case("W3-7 a candidates file that is not the frozen rule's re-derivation (an edited first change): REFUSED",
             res["refused"] and "entries" in res["state"], res["state"])
        DA._W3Q.clear()
        DA._W3Q.update(mod=None, why="ModuleNotFoundError")
        with contextlib.redirect_stdout(io.StringIO()):
            res = DA.w3_validity(recs, opts)
        case("W3-8 without the W3 generator W3 is not evaluated (no L4, no verdict)", not res["complete"]
             and "not importable" in res["state"], res["state"])
        n0 = len(DA._LINES)
        with contextlib.redirect_stdout(io.StringIO()):
            ok, probs = DA.w2_records_gate(fx.cells, types.SimpleNamespace(smoke=None, head=None, zeros_only=True),
                                           fx.queues)
            os.remove(fx.lines[(7, "1")]["out"] + ".argv")
            bad, bprobs = DA.w2_records_gate(fx.cells, types.SimpleNamespace(smoke=None, head=None, zeros_only=True),
                                             fx.queues)
        del DA._LINES[n0:]
        case("W2G-1 the W3 generator's precondition (w2_records_gate, behind w2_gate(head, notes)): the cell's W1 dq0 and "
             "W2 dq1 records valid -> passes; the dq1 record without its pool .argv -> INVALID, the gate fails",
             ok and not probs and not bad and any("INVALID 1 set7/ring/A_N" in x and ".argv" in x for x in bprobs),
             (probs, bprobs))
        case("W2G-2 w2_gate refuses without both --head and --part2-notes (the generator's build passes both)",
             DA.w2_gate(None, "notes.txt") == (False, ["--head and --part2-notes are both required"])
             and DA.w2_gate("71cfe796", None)[0] is False)
    finally:
        fx.close()


def outcome_e2e():
    """Sections 1-8 end to end on a synthetic two-cell screen (set 7 ring A_N: dq1 loses ff_unit_0 at 40, dq0 loses
    ff_unit_0 at 60 and ff_unit_2 at 30; set 8 ring A_N: the arms identical), the REAL W3 generator: process, section
    1, S1, the zeros, W3 (complete) and the outcome sections (2 of 64 cells, none missing or INVALID: S1 not
    established; --allow-incomplete no longer exists, review M2). dq1's J decisions here are the counterfactual only
    (no J bind: every dispatch zero holds on these
    minimal records). Asserts the printed structure: the DIVERGED assertion line, FULL(0 -> 1), the 28 sign-tested
    rows, L4 1 / 1, sections 5 and 6, and a VERDICT that would be OUTCOME 4 (NOT SHOWN: no DD fall), naming decision
    0.2."""
    w3q, _rp = w3_tools()
    if w3q is None:
        case("E2E-0 the frozen W3 generator is importable", False)
        return
    deaths = {7: {"R": {U0: 60, U2: 30}, "0": {U0: 60, U2: 30}, "1": {U0: 40}},
              8: {"R": {U1: 50}, "0": {U1: 50}, "1": {U1: 50}}}
    dp1 = {"j_calls": [[10, "post", 1.0, 0, {"legacy": [[V0, U1]], "j_fills": [], "stage3": [], "stage4": []}]],
           "j_events": []}
    fx = W3Fixture((7, 8), deaths, dp1, w3q)
    n0 = len(DA._LINES)
    try:
        opts = types.SimpleNamespace(smoke=None, head=None, zeros_only=False, smoke_files={}, w3_unresolved=[])
        with contextlib.redirect_stdout(io.StringIO()):
            recs = DA.process(fx.cells, opts, fx.queues)
        _doc, rlines = fx.generate(recs)
        p = "dqrp_dq1r7_A_N_"
        plan = {"R0": (deaths[7]["1"], []), "f0_KOothers": ({}, [[10, "post", U1, V0, "ko_today"]]),
                "f2_KOothers": ({U0: 40, U2: 30}, [[10, "post", U1, V0, "ko_today"]])}
        for suffix, (dead, applied) in plan.items():
            fx.replay(p + suffix, dead, applied)
        with contextlib.redirect_stdout(io.StringIO()):
            st = DA.sec_prov(recs, opts)
            s1 = DA.sec_s1(recs, opts)
            zres = DA.sec_zeros(recs, st, opts)
            w3 = DA.w3_validity(recs, opts)
            outcome = DA.outcome_sections(recs, st, s1, zres, w3, opts)
        rep = DA._LINES[n0:]
        verdict = [ln for ln in rep if ln.startswith("VERDICT:")]
        sign_rows = [ln for ln in rep if ln.startswith("      ") and "rank" in ln and "thr" in ln]
        case("E2E-1 sections 1-8 end to end (2 synthetic cells, the REAL W3 generator: KO-OWN of both candidates EMPTY - "
             "not queued, R0's outcome stands): S1 incomplete (2 of 64), no zero, W3 COMPLETE (L4 1 / 1), the "
             "DIVERGED assertion holds, FULL(0 -> 1) with 28 sign-tested rows, sections 5-7, and a VERDICT that would "
             "be OUTCOME 4 (NOT SHOWN: no pooled DD fall) naming decision 0.2",
             [ln["name"] for ln in rlines] == [p + s for s in plan] and outcome == 4 and not zres["stop"]
             and not zres["s2"] and w3["complete"] and not w3["conflicts"] and len(sign_rows) == 28
             and any("DIVERGED assertion (10.6)" in ln and "holds" in ln for ln in rep)
             and any(ln.strip().startswith("FULL(0 -> 1) = NOT SHOWN") for ln in rep)
             and any("CAUSED 1 vs PREVENTED 1" in ln for ln in rep) and len(verdict) == 1
             and "would be OUTCOME 4" in verdict[0] and "DISPATCH_REASSIGN stay 0" in verdict[0]
             and any(ln.startswith("6 REPORTED") for ln in rep) and any(ln.startswith("5 M8") for ln in rep)
             and any(ln.startswith("7 W3 / L4") for ln in rep),
             (outcome, verdict, len(sign_rows), w3.get("state"), w3.get("conflicts"),
              [x[:3] for x in zres["fails"] if x[3] != "REPORTED"][:4]))
    finally:
        del DA._LINES[n0:]
        fx.close()


def override_vs_replay_cases():
    """The analyzer's own reading of 11.2's override (override_changes) equals the replay tool's frozen rule
    (_dq_replay.jpoint_changes - the rule the W3 generator and the replay apply) on random recorded J points."""
    import random
    _w3q, rp = w3_tools()
    if rp is None:
        case("IND-2 outputs/_dq_replay.py is importable", False)
        return
    rng = random.Random(20261009)
    units = ["ff_unit_%d" % i for i in range(5)]
    vics = ["victim_%d" % i for i in range(5)]
    bad, n = [], 0
    for _ in range(3000):
        legacy = [[v, rng.choice(units)] for v in rng.sample(vics, rng.randint(0, 3))]
        s2 = [[v, u, rng.random() < 0.85] for v, u in zip(rng.sample(vics, rng.randint(0, 3)), rng.sample(units, 3))]
        s3 = [[rng.choice(("replace", "latch_fill")), v, u, [o], rng.random() < 0.9]
              for v, u, o in zip(rng.sample(vics, rng.randint(0, 2)), rng.sample(units, 2), rng.sample(units, 2))]
        s4 = [[v, u, rng.random() < 0.85] for v, u in zip(rng.sample(vics, rng.randint(0, 2)), rng.sample(units, 2))]
        K = set(rng.sample(units, rng.randint(1, 3)))
        mine = DA.override_changes(7, "post", legacy, s2, s3, s4, K)
        theirs = [list(x) for x in rp.jpoint_changes(7, "post", legacy, s2, s3, s4, K)]
        n += 1
        if mine != theirs:
            bad.append((legacy, s2, s3, s4, sorted(K), mine, theirs))
    case("IND-2 the analyzer's override_changes equals the frozen rule (_dq_replay.jpoint_changes) on %d random "
         "recorded J points (the KO-evidence prediction is the same rule)" % n, not bad, bad[:1])


def random_jpoint_cases():
    """IND-3: the whole J-point check (jpoint_zeros: Z-R1, Z-C1a, Z-C1b, Z-C2, Z-R2, I4-W) on RANDOM J-posts emulated with
    the real J - free units, waiting victims, active and latched contests, open and closed routes, states at entry or
    first sight, persistence counts, ledgers - must find NOTHING (no false zero failure on a correct J); the structure
    counts show the random boards reach the paths (replacements of both causes and kinds, nearest-barred frames,
    closed routes; second fills are rare on random boards and covered by ZFILL4-1)."""
    import random
    rng = random.Random(20261010)
    bad, n = [], 0
    tot = collections.Counter()
    for _ in range(400):
        nu = rng.randint(2, 5)
        us = ["ff_unit_%d" % i for i in range(nu)]
        nv = rng.randint(1, 4)
        vs = ["victim_%d" % i for i in range(nv)]
        rng.shuffle(us)
        n_con = rng.randint(0, min(nv, nu - 1))
        con_v, w_v = vs[:n_con], vs[n_con:]
        incumbents = us[:n_con]
        free = us[n_con:]
        units, contest, latched = {}, {}, {}
        for u in us:
            units[u] = (rng.randint(0, 30), rng.randint(0, 30), rng.random() < 0.2, FREE)
        for v, a in zip(con_v, incumbents):
            lab = RB if rng.random() < 0.35 else EN
            units[a] = units[a][:3] + (lab,)
            (latched if lab == RB else contest)[v] = a
        victims = {v: (rng.randint(0, 30), rng.randint(0, 30)) for v in vs}
        dist = {}
        for v in vs:
            row = {}
            for u in us:
                if rng.random() < 0.15:
                    row[u] = (None, None)
                else:
                    d = rng.randint(0, 40) if u in incumbents else rng.randint(1, 40)
                    row[u] = (d, (d + rng.randint(0, 6)) if rng.random() < 0.65 else None)
            dist[v] = row
        pb, hist, ledger = {}, {}, {}
        for v, a in list(contest.items()) + list(latched.items()):
            if rng.random() < 0.8:
                H = sorted({(rng.randint(0, 30), rng.randint(0, 30)) for _ in range(rng.randint(1, 3))})
                closed = dist[v][a][0] is None and rng.random() < 0.7
                pb[(a, v)] = [[list(c) for c in H], rng.randint(0, 12), rng.randint(0, 12) if closed else 0, closed,
                              rng.randint(1, 30), {f: rng.randint(1, 4) for f in free if rng.random() < 0.4}]
                hist[DA.pkey(a, v)] = {"H": [[(rng.randint(0, 45) if rng.random() < 0.85 else None),
                                              (rng.randint(0, 50) if rng.random() < 0.5 else None)] for _c in H]}
        for u in us:
            for v in vs:
                if rng.random() < 0.25:
                    ledger[(u, v)] = rng.choice([1, 1, 2])
        e = emulate(free, w_v, units, victims, dist, contest=contest, latched_binder=latched, progress_before=pb,
                    hist=hist, ledger=ledger, SMP=(10, 5, 3))
        Z, st = zeros(e)
        n += 1
        tot.update(st)
        tot.update(x["kind"] + ("" if x["kind"] not in ("replace", "latch_fill") else "_" + str(x["reason"]))
                   for x in e["events"])
        if Z:
            bad.append((dict(Z), e["events"]))
    case("IND-3 %d random emulated J-posts with the real J: jpoint_zeros finds nothing; paths reached: %s" % (
        n, {k: tot[k] for k in ("fill", "second_fill", "replace_reassign_stall", "replace_reassign_margin",
                                "latch_fill_joint_replace_latched", "nearest_barred", "contests, route closed",
                                "contests, latched incumbent", "progress evaluations")}),
         not bad and tot["replace_reassign_stall"] and tot["replace_reassign_margin"] and tot["nearest_barred"]
         and tot["latch_fill_joint_replace_latched"], bad[:1])


def own_vs_jd_cases():
    """The analyzer's independent implementations agree with the real J on random valid inputs (no false zero
    failure on a correct J): own_fill vs solve_fill, own_plan vs plan_replacements_detail, own_progress vs
    progress_step, own_persist vs update_persistence."""
    import random
    rng = random.Random(20261008)
    n_fill = n_plan = n_prog = n_pers = 0
    bad = []
    for _ in range(300):
        us = ["ff_unit_%d" % i for i in range(rng.randint(0, 4))]
        vs = ["victim_%d" % i for i in range(rng.randint(0, 4))]
        dist = {(u, v): (rng.randint(1, 30) if rng.random() < 0.8 else None) for u in us for v in vs}
        clean = {k: (x is not None and rng.random() < 0.6) for k, x in dist.items()}
        led = {k: rng.choice([0, 0, 0, 1, 2]) for k in dist}
        mine = DA.own_fill(us, vs, dist, clean, led)
        jd = sorted([(p.victim, p.unit) for p in JD.solve_fill(us, vs, dist, led, clean=clean)],
                    key=lambda p: (DA.id_index(p[0]), DA.id_index(p[1])))
        n_fill += 1
        if mine != jd:
            bad.append(("fill", us, vs, mine, jd))
        cons, plan_c = [], []
        for v in vs:
            inc = "ff_unit_9%s" % v[-1]
            op = rng.random() < 0.7
            c = {"victim": v, "incumbent": inc, "delta": rng.randint(1, 40), "open": op, "k": rng.randint(0, 14),
                 "k_closed": rng.randint(0, 14), "persist": {u: rng.randint(0, 4) for u in us if rng.random() < 0.5},
                 "latched": rng.random() < 0.3}
            plan_c.append(c)
            cons.append(JD.Contest(victim=v, incumbent=inc, delta=c["delta"], route_open=op, k=c["k"],
                                   k_closed=c["k_closed"], persist=c["persist"], latched=c["latched"]))
        r1, b1 = DA.own_plan(plan_c, us, dist, clean, led, 10, 3)
        r2, b2 = JD.plan_replacements_detail(cons, us, dist, led, clean, stall_steps=10, margin_persist=3)
        r2 = [[r.victim, r.old_unit, r.new_unit, r.cause, r.distance, r.latched] for r in r2]
        b2 = [[b.victim, b.incumbent, b.cause, b.distance, list(b.units)] for b in b2]
        n_plan += 1
        if r1 != r2 or b1 != b2:
            bad.append(("plan", r1, r2, b1, b2))
    for _ in range(1000):
        H = [[rng.randint(0, 5), rng.randint(0, 5)] for _ in range(rng.randint(1, 4))]
        H = sorted({tuple(c) for c in H})
        st = JD.Progress(history=tuple(H), k=rng.randint(0, 12), k_closed=rng.randint(0, 12),
                         closed=rng.random() < 0.3, age=rng.randint(0, 20))
        op = rng.random() < 0.75
        d_now = rng.randint(0, 12) if op else None
        c_now = (rng.randint(0, 15) if rng.random() < 0.6 else None) if op else None
        dh = [rng.randint(0, 12) if rng.random() < 0.8 else None for _ in H]
        ch = [rng.randint(0, 15) if rng.random() < 0.5 else None for _ in H]
        cell = (rng.randint(0, 5), rng.randint(0, 5))
        fz = rng.random() < 0.2
        j = JD.progress_step(st, op, d_now, c_now, tuple(dh), tuple(ch), cell, fz)
        before = [[list(c) for c in H], st.k, st.k_closed, st.closed, st.age, {}]
        H1, k1, kl1, cl1, _p, _l = DA.own_progress(before, op, d_now, c_now, dh, ch, cell, fz)
        n_prog += 1
        if [H1, k1, kl1, cl1] != [[list(c) for c in j.history], j.k, j.k_closed, j.closed]:
            bad.append(("progress", before, op, d_now, c_now, dh, ch, cell, fz))
        prev = {"ff_unit_%d" % i: rng.randint(0, 3) for i in range(3) if rng.random() < 0.5}
        sd = {"ff_unit_%d" % i: (rng.randint(1, 30) if rng.random() < 0.8 else None) for i in range(4)}
        delta = rng.randint(1, 40) if rng.random() < 0.9 else None
        st2 = JD.update_persistence(JD.Progress(history=((0, 0),), persist=tuple(sorted(prev.items()))), sd, delta, 5)
        n_pers += 1
        if DA.own_persist(prev, sd, delta, 5) != dict(st2.persist_map()):
            bad.append(("persist", prev, sd, delta))
    case("IND-1 the analyzer's own fill (%d), planner (%d), progress rule (%d) and persistence (%d) equal the real J's on "
         "random valid instances (no false zero failure on a correct J)" % (n_fill, n_plan, n_prog, n_pers), not bad,
         bad[:2])


# ================================================================================================ the review fixes
# Every case below FAILS without its fix (a function the fix adds is missing -> the case records FAIL, never a crash).
def _try(name, fn):
    try:
        cond, detail = fn()
    except Exception as exc:                  # noqa: BLE001
        cond, detail = False, "raised %r" % (exc,)
    case(name, cond, detail)


def _quiet_call(fn, *a, **k):
    err, outb = io.StringIO(), io.StringIO()
    code = None
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(outb):
            fn(*a, **k)
    except SystemExit as exc:
        code = exc.code
    return code, err.getvalue(), outb.getvalue()


def head_sha():
    return DA.git("rev-parse", "HEAD")[1].decode().strip()


def m1_cases():
    """M1: --part2-notes with --head; TOOLING_AT_HEAD at --head; section 9's constants in prov_run."""
    def notes_required():
        n0 = len(DA._LINES)
        code, err, _o = _quiet_call(DA.main, ["--head", head_sha()])
        del DA._LINES[n0:]
        return code == 2 and "--part2-notes" in err, (code, err[-160:])
    _try("M1-1 outside --smoke --head without --part2-notes is an argparse error (exit 2), as _mvg_analyze's main",
         notes_required)

    def files_at_head():
        hd = head_sha()
        tmp = tempfile.mkdtemp(prefix="dq_m1_")
        try:
            present = []                      # the TOOLING_AT_HEAD files committed at HEAD (a copy of each blob)
            for rel in DA.TOOLING_AT_HEAD:
                rc, blob = DA.git("show", "%s:%s" % (hd, rel))
                if rc != 0:
                    continue
                present.append(rel)
                p = os.path.join(tmp, rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as fh:
                    fh.write(blob.replace(b"\r\n", b"\n"))
            ok1, _l1 = DA.head_files_check(hd, rels=present, root=tmp)
            p0 = os.path.join(tmp, "outputs", "_dq_seeds.txt")
            with open(p0, "rb") as fh:
                data = fh.read()
            with open(p0, "wb") as fh:
                fh.write(data.replace(b"\n", b"\r\n"))
            ok2, _l2 = DA.head_files_check(hd, rels=present, root=tmp)
            with open(os.path.join(tmp, "outputs", "_dq_replay.py"), "ab") as fh:
                fh.write(b"# an uncommitted edit\n")
            ok3, l3 = DA.head_files_check(hd, rels=present, root=tmp)
            os.remove(os.path.join(tmp, "outputs", "_dq_seeds.txt"))
            ok4, l4 = DA.head_files_check(hd, rels=["outputs/_dq_seeds.txt"], root=tmp)
            ok5, l5 = DA.head_files_check(hd, rels=["outputs/_dq_q_selftest_never_committed.jsonl"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return (len(present) >= 8 and ok1 and ok2 and not ok3 and not ok4 and not ok5
                and len(DA.TOOLING_AT_HEAD) == 11 and any("_dq_replay.py" in x and "DIFFERS" in x for x in l3)
                and any("MISSING" in x for x in l4) and any("absent" in x for x in l5)), (ok1, ok2, ok3, ok4, ok5,
                                                                                         l3[:2], present)
    _try("M1-2 the TOOLING_AT_HEAD files equal to their blobs at --head pass (a CRLF copy too: LF-normalised); an "
         "uncommitted edit, a file missing on disk, or a file not committed at --head REFUSES", files_at_head)

    def header_refuses():
        saved = DA.head_files_check
        DA.head_files_check = lambda h, rels=DA.TOOLING_AT_HEAD, root=None: (False, ["  outputs/x DIFFERS"])
        n0 = len(DA._LINES)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                ok = DA.sec_header(types.SimpleNamespace(head=head_sha(), smoke=None, part2_notes=None))
        finally:
            DA.head_files_check = saved
        rep = DA._LINES[n0:]
        del DA._LINES[n0:]
        return ok is False and any("REFUSED: a tooling file or frozen input differs" in x for x in rep), rep[-2:]
    _try("M1-3 section 0 REFUSES (no verdict) when a TOOLING_AT_HEAD file differs from --head", header_refuses)

    def s9():
        tmp = tempfile.mkdtemp(prefix="dq_s9_")
        try:
            cell = {"scen": SCEN[0], "wind": SCEN[1], "seed": SCEN[2], "mode": 0}
            o = types.SimpleNamespace(smoke=None, head=None)

            def run(arm, mut_line=None, mut_rec=None, steps_done=360):
                line = queue_line(arm, tmp)
                if mut_line:
                    mut_line(line)
                d = mini_record(arm, line, steps_done=steps_done)
                if mut_rec:
                    mut_rec(d)
                write_run(line, d)
                return DA.prov_run(d, line["out"], line, cell, arm, o)[0]

            def tok(old, new):
                def f(line):
                    line["argv"][line["argv"].index(old)] = new
                return f

            def extra(line):
                i = line["argv"].index("--steps")
                line["argv"][i:i] = ["--set", "FIRE_SPREAD_MULTIPLIER=2"]

            res = {
                "a ring cell with VICTIM_SPAWN_MODE=1 (line and record agree)": run(
                    "1", tok("VICTIM_SPAWN_MODE=0", "VICTIM_SPAWN_MODE=1"),
                    lambda d: d["fb3"]["eff"].update(victim_spawn_mode=1)),
                "GLOBAL_PLANNER_MODE=1": run("0", tok("GLOBAL_PLANNER_MODE=0", "GLOBAL_PLANNER_MODE=1")),
                "BATCH_SIZE=180": run("R", tok("BATCH_SIZE=360", "BATCH_SIZE=180")),
                "--steps 300 (line, record and its rows agree)": run(
                    "1", tok("360", "300"), lambda d: d.update(steps=300), steps_done=300),
                "an extra --set key": run("0", extra),
                "no --crn and CRN off (line and record agree)": run(
                    "1", lambda ln: ln["argv"].pop(1), lambda d: d["fb3"].update(crn={"on": False, "crn_draws": 0})),
            }
            base = run("1")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        flagged = {k: any("section 9" in str(w) for w in v) for k, v in res.items()}
        return not base and all(flagged.values()), (flagged, base)
    _try("M1-4 section 9's CONSTANTS, never the queue line: a record whose line and record agree on a ring cell with "
         "VICTIM_SPAWN_MODE=1, GLOBAL_PLANNER_MODE=1, BATCH_SIZE=180, --steps 300, an extra --set key, or no --crn with "
         "CRN off is INVALID; the section-9 record passes", s9)


def smp_cases():
    """R2-F2: dq1's S / M / P and their raw module values."""
    def f():
        tmp = tempfile.mkdtemp(prefix="dq_smp_")
        try:
            cell = {"scen": SCEN[0], "wind": SCEN[1], "seed": SCEN[2], "mode": 0}
            o = types.SimpleNamespace(smoke=None, head=None)
            out_ = {}
            for label, arm, mut in (("dq1 shipped", "1", None),
                                    ("dq1 S 12", "1", lambda d: d["dq"]["switches"].update(S=12)),
                                    ("dq1 raw margin '6'", "1",
                                     lambda d: d["dq"]["switches"]["raw"].update(DISPATCH_MARGIN_STEPS="6")),
                                    ("dq1 raw persist 'None'", "1",
                                     lambda d: d["dq"]["switches"]["raw"].update(DISPATCH_MARGIN_PERSIST="None"))):
                line = queue_line(arm, tmp)
                d = mini_record(arm, line)
                if mut:
                    mut(d)
                write_run(line, d)
                out_[label] = [w for w in DA.prov_run(d, line["out"], line, cell, arm, o)[0] if "dq1" in str(w)]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return (not out_["dq1 shipped"] and out_["dq1 S 12"] and out_["dq1 raw margin '6'"]
                and out_["dq1 raw persist 'None'"]), out_
    _try("R2F2-1 a dq1 record whose dq.switches S / M / P is not 10 / 5 / 3, or whose raw DISPATCH_STALL_STEPS / "
         "MARGIN_STEPS / MARGIN_PERSIST is not the shipped module value, is INVALID; the shipped record passes", f)


def m2_m3_cases():
    """M2 (--allow-incomplete removed), M3 (section 20 hashed)."""
    def removed():
        n0 = len(DA._LINES)
        code, err, _o = _quiet_call(DA.main, ["--head", "x", "--part2-notes", "y", "--allow-incomplete"])
        del DA._LINES[n0:]
        return code == 2 and "REMOVED" in err, (code, err[-200:])
    _try("M2-1 --allow-incomplete is an argparse error saying it was REMOVED (exit 2)", removed)

    def sec20():
        with open(os.path.join(HERE, "dispatch2_part1.txt"), encoding="utf-8") as fh:
            text = fh.read()
        ok, lines = DA.hash_checks()
        bad, lbad = DA.hash_checks(text.replace("(a) RECOMMENDED - keep the correction",
                                                "(a) RECOMMENDED - keep the corrections"))
        return (ok and not bad and DA.SECTION_COMMITS[20] == (DA.A2_FULL,)
                and any(ln.lstrip().startswith("section 20") and "identical" in ln and DA.A2_FULL in ln
                        for ln in lines)
                and any(ln.lstrip().startswith("section 20") and "DIFFERS" in ln for ln in lbad)), lbad[-3:]
    _try("M3-1 section 20 (amendment A2) is HASHED at 71cfe796 (SECTION_COMMITS[20], printed in the header): the "
         "working file passes; one edited character in section 20 REFUSES", sec20)


def order_cases():
    """m1: 10.8's order - validity and the zeros before S1; outcome 1 precedes outcome 2."""
    w3q, _rp = w3_tools()

    def run(dq0_crash, zeros_only=False):
        fx = W3Fixture((7,), {7: {"R": {}, "0": {}, "1": {}}}, W3_DP, w3q)
        try:
            lnR, ln0 = fx.lines[(7, "R")], fx.lines[(7, "0")]
            dR = fx.record("R", lnR, {})
            dR["eval"] = {"rescued": 9, "firefighter_deaths": 0}          # S1 differs (eval)
            write_run(lnR, dR)
            if dq0_crash:
                write_run(ln0, mini_record("0", ln0, {}, steps_done=17, crashed={"type": "ValueError", "step": 17}))
            opts = types.SimpleNamespace(smoke=None, head=None, zeros_only=zeros_only, w3_unresolved=[])
            with contextlib.redirect_stdout(io.StringIO()):
                recs = DA.process(fx.cells, opts, fx.queues)
            n0 = len(DA._LINES)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = DA.screen_sections(recs, opts)
            rep = DA._LINES[n0:]
            del DA._LINES[n0:]
        finally:
            fx.close()
        zi = next((i for i, ln in enumerate(rep) if ln.startswith("3 STRUCTURAL ZEROS")), None)
        si = next((i for i, ln in enumerate(rep) if ln.startswith("2 S1 IDENTITY")), None)
        stop = [ln for ln in rep if ln.startswith(("VERDICT:", "ZEROS-ONLY STOP CONDITION:"))]
        return rc, zi, si, stop

    def both():
        rc, zi, si, stop = run(True)
        return (rc == 1 and zi is not None and si is None and len(stop) == 1 and "OUTCOME 1" in stop[0]), (rc, zi, si,
                                                                                                            stop)
    _try("m1-1 a crash in dq0 AND an S1 difference: the zeros are printed, S1 is NOT (outcome 1 takes precedence over "
         "outcome 2): STOP, OUTCOME 1, exit 1", both)

    def s1_only():
        rc, zi, si, stop = run(False)
        rcz, ziz, siz, stopz = run(False, zeros_only=True)
        return (rc == 1 and zi is not None and si is not None and zi < si and len(stop) == 1 and "OUTCOME 2" in stop[0]
                and rcz == 1 and ziz is not None and siz is not None and ziz < siz
                and stopz and stopz[0].startswith("ZEROS-ONLY STOP CONDITION")), (rc, zi, si, stop, rcz, stopz)
    _try("m1-2 S1 alone fails: section 3 (the zeros) is printed BEFORE section 2 (S1), then STOP, OUTCOME 2; "
         "--zeros-only still works (the same order, a ZEROS-ONLY STOP CONDITION)", s1_only)


def _w3_good_fixture(w3q):
    """w3_end_to_end's synthetic screen with every replay written (R0, the (A) and (B) knockouts of set7/ring/A_N)."""
    deaths = {7: {"R": {U0: 60, U2: 30}, "0": {U0: 60, U2: 30}, "1": {U0: 40}}}
    fx = W3Fixture((7,), deaths, W3_DP, w3q)
    opts = types.SimpleNamespace(smoke=None, head=None, zeros_only=False, w3_unresolved=[])
    with contextlib.redirect_stdout(io.StringIO()):
        recs = DA.process(fx.cells, opts, fx.queues)
    fx.generate(recs)
    p = "dqrp_dq1r7_A_N_"
    good = {"R0": (deaths[7]["1"], []),
            "f0_KOown": ({}, [[10, "post", U0, V0, "drop_bind"]]),
            "f0_KOlast": ({}, [[10, "post", U0, V0, "drop_bind"]]),
            "f0_KOothers": ({U0: 40}, [[10, "post", U0, V0, "drop_victim"], [10, "post", U1, V0, "ko_today"],
                                       [12, "post", U2, V1, "drop_bind"]]),
            "f2_KOown": ({U0: 40}, [[12, "post", U2, V1, "drop_bind"]]),
            "f2_KOothers": ({U0: 40, U2: 30}, [[10, "post", U0, V0, "drop_bind"], [10, "post", U1, V0, "ko_today"]])}
    for suffix, (dead, applied) in good.items():
        fx.replay(p + suffix, dead, applied)
    return fx, recs, opts, p


def m2_uncomputable_cases():
    """m2: a non-crash uncomputable record is INVALID (no forced L4 FAIL); the crash case keeps the forced FAIL and
    prints why."""
    w3q, _rp = w3_tools()

    def prov():
        tmp = tempfile.mkdtemp(prefix="dq_m2_")
        try:
            line = queue_line("1", tmp)
            d = mini_record("1", line)
            d["rows_ff"] = d["rows_ff"][:359]
            write_run(line, d)
            w = DA.prov_run(d, line["out"], line, {"scen": SCEN[0], "wind": SCEN[1], "seed": SCEN[2], "mode": 0}, "1",
                            types.SimpleNamespace(smoke=None, head=None))[0]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return any("rows_ff holds 359" in x for x in w), w
    _try("m2-1 rows_ff not one row per step done WITHOUT a crash (359 rows, steps_done 360) is INVALID (a tooling "
         "defect, 10.8 (1))", prov)

    def e2e(kind):
        deaths = {7: {"R": {U0: 60}, "0": {U0: 60}, "1": {U0: 40}}}
        fx = W3Fixture((7,), deaths, W3_DP, w3q)
        try:
            ln1 = fx.lines[(7, "1")]
            if kind == "rows":
                d1 = fx.record("1", ln1, deaths[7]["1"])
                d1["rows_ff"] = d1["rows_ff"][:359]
            else:
                d1 = mini_record("1", ln1, {}, j_calls=W3_DP["j_calls"], steps_done=17,
                                 crashed={"type": "ValueError", "step": 17})
            write_run(ln1, d1)
            opts = types.SimpleNamespace(smoke=None, head=None, zeros_only=False, w3_unresolved=[])
            with contextlib.redirect_stdout(io.StringIO()):
                recs = DA.process(fx.cells, opts, fx.queues)
            if kind == "crash":
                fx.generate(recs)
            n0 = len(DA._LINES)
            with contextlib.redirect_stdout(io.StringIO()):
                res = DA.w3_validity(recs, opts)
            rep = DA._LINES[n0:]
            del DA._LINES[n0:]
            return recs, res, rep
        finally:
            fx.close()

    def rows():
        recs, res, _rep = e2e("rows")
        inv = recs[0]["prov"].get("1") or []
        return (any("W3 compact marks the record unusable without a crash" in x for x in inv) and "l4" not in res
                and not res["complete"] and "INVALID" in str(res["state"])), (inv[:2], res.get("state"))
    _try("m2-2 end to end: the dq1 record the W3 compact cannot use without a crash is INVALID - W3 is not evaluated "
         "(no forced L4 FAIL, no verdict)", rows)

    def crash():
        _recs, res, rep = e2e("crash")
        return (res["complete"] and res.get("l4", {}).get("fail") is True and res["l4"].get("uncomputable")
                and any("documented crash" in x and "set7/ring/A_N" in x for x in rep)), (res.get("state"), rep[-4:])
    _try("m2-3 the documented crash case keeps the forced L4 FAIL (11.3: an uncomputable cell counts against) and "
         "prints why", crash)


def m3_cases():
    """m3: --w3-unresolved."""
    w3q, _rp = w3_tools()

    def f():
        fx, recs, opts, p = _w3_good_fixture(w3q)
        try:
            os.remove(fx.byn[p + "f0_KOown"]["out"])
            with contextlib.redirect_stdout(io.StringIO()):
                plain = DA.w3_validity(recs, opts)
            n0 = len(DA._LINES)
            with contextlib.redirect_stdout(io.StringIO()):
                decl = DA.w3_validity(recs, types.SimpleNamespace(**dict(vars(opts), w3_unresolved=[p + "f0_KOown"])))
            rep = DA._LINES[n0:]
            with contextlib.redirect_stdout(io.StringIO()):
                valid = DA.w3_validity(recs, types.SimpleNamespace(**dict(vars(opts), w3_unresolved=[p + "R0"])))
                foreign = DA.w3_validity(recs, types.SimpleNamespace(**dict(vars(opts),
                                                                            w3_unresolved=["dq1r7_A_N"])))
            del DA._LINES[n0:]
        finally:
            fx.close()
        ia = {(it["kind"], it["unit"]): it for it in decl.get("items") or []}.get(("A", U0)) or {}
        return (not plain["complete"] and decl["complete"] and not ia.get("resolved", True)
                and decl["l4"]["caused"] == 1 and any("DECLARED UNRESOLVED" in x and p + "f0_KOown" in x for x in rep)
                and valid.get("refused") and "present and valid" in str(valid.get("refused_text"))
                and foreign.get("refused") and "not W3 queue lines" in str(foreign.get("refused_text"))), (
            plain.get("state"), decl.get("state"), ia.get("why"), valid.get("refused_text"))
    _try("m3-1 --w3-unresolved: a missing KO-OWN replay keeps W3 INCOMPLETE; declared UNRESOLVED it is printed, its "
         "(A) candidate is UNRESOLVED and counts as CAUSED, and W3 is COMPLETE; naming a present valid replay or a "
         "line that is not a W3 queue line REFUSES", f)


def w3_report_cases():
    """m4 (R0 presence), m5 (refused / aborted J decisions), m6 (class at death, challenger)."""
    def m4():
        x = {"rows_ff": [[1]], "rows_vic": [], "rows_uav": [], "rows_dec": [], "dp": {"commands": [1]},
             "mv_events": [], "eval": {"rescued": 1}}
        return (DA.r0_reproduces(x, copy.deepcopy(x), "s", "s") == ["rows_trig", "dp.j_events"]
                and DA.r0_reproduces(dict(x, rows_trig=[]), dict(x, rows_trig=[], dp={"commands": [1],
                                                                                      "j_events": []}),
                                     "s", "s") == ["dp.j_events"]), DA.r0_reproduces(x, copy.deepcopy(x), "s", "s")
    _try("m4-1 R0 reproduction: a listed field (rows_trig, dp.j_events) MISSING from both records - or from one - is a "
         "difference, never an equality of two absences", m4)

    def m5():
        dp = {"j_calls": [[14, "post", 1.0, 2, {"legacy": [[V2, U3]], "j_fills": [], "stage3": [], "stage4": []}]],
              "j_events": [{"step": 14, "phase": "post", "kind": "replace", "stage": 3, "victim_id": V1, "unit": U2,
                            "old_units": [U1]},
                           {"step": 14, "phase": "post", "kind": "second_fill_refused", "stage": 4, "victim_id": V2,
                            "unit": U1},
                           {"step": 20, "phase": "post", "kind": "replace_aborted", "stage": 3, "victim_id": V0,
                            "unit": U3, "old_units": [U0]}]}
        jp = DA.j_decision_points(dp)
        units = [U0, U1, U2, U3]
        own1 = DA.ko_refused(jp, [{"unit": U1, "from": 0, "to": 40}], units)     # drop_bind on the refused fill
        own3 = DA.ko_refused(jp, [{"unit": U3, "from": 0, "to": 40}], units)     # ko_today on V2 -> drop_victim; 20
        own2 = DA.ko_refused(jp, [{"unit": U2, "from": 0, "to": 40}], units)     # drop_challenger -> drop_unreleased
        none0 = DA.ko_refused(jp, [{"unit": U0, "from": 0, "to": 19}], units)    # before 20: no decision of U0
        last1 = DA.ko_refused(jp, [{"unit": U1, "from": 15, "to": 40}], units)   # after 14: nothing
        return (own1 == [[14, "post", "stage 4 refused", V2, U1]]
                and own3 == [[14, "post", "stage 4 refused", V2, U1], [20, "post", "replace aborted", V0, U3]]
                and own2 == [[14, "post", "stage 4 refused", V2, U1]] and none0 == [] and last1 == []), (
            own1, own3, own2, none0, last1)
    _try("m5-1 the knockout decisions on a REFUSED (second fill) or ABORTED (replacement) J decision of dq1's record "
         "are found through every override path (drop_bind, drop_victim of a ko_today victim, drop_unreleased after a "
         "dropped challenger; reported: J's control flow under the knockout may differ from R0's there); a knockout "
         "touching none -> none", m5)

    def m6():
        def r(u, st, exiting, vid):
            return [u, 1, 1, st, int(vid is not None), exiting, 0, 0, vid, None, 0, None]
        rows_ff = [[r(U0, "en_route", 0, V0), r(U1, "en_route", 1, V1), r(U2, "available", 0, None),
                    r(U3, "en_route", 0, V2)] for _t in range(3)]
        rows_ff.append([r(U0, "route_blocked", 0, V0), r(U1, "en_route", 1, V1), r(U2, "available", 0, None),
                        r(U3, "en_route", 0, V2)])
        rows_ff.append([x[:6] + [1] + x[7:] for x in rows_ff[-1]])                  # every unit dead at step 5
        cls = {u: DA.death_class(rows_ff, u, 5) for u in (U0, U1, U2, U3)}
        cmds = [[2, "post", "assign", V0, U0, "reassign_stall", True, True, 5, 5],
                [1, "post", "assign", V2, U3, "joint_initial", True, True, 5, 5]]
        ch0, ch3 = DA.challenger_death(cmds, rows_ff, U0, 5), DA.challenger_death(cmds, rows_ff, U3, 5)
        it = {"kind": "A", "cell": "set7/ring/A_N", "unit": U0, "class": cls[U0], "challenger": ch0,
              "refused": {"KOown": [[14, "post", "stage 4 refused", V2, U0]]}}
        note = DA.candidate_notes(it)
        w3 = {"complete": True, "items": [dict(it, set="set7", t=5, other=None, resolved=True, why=[], hybrid={},
                                               own=True, others=False)], "uncomputable": [], "same": [],
              "declared": []}
        w3["l4"] = DA.l4_counts(w3["items"])
        n0 = len(DA._LINES)
        with contextlib.redirect_stdout(io.StringIO()):
            DA.sec_w3_report(w3)
        rep = DA._LINES[n0:]
        del DA._LINES[n0:]
        return (cls == {U0: "latched", U1: "carrying", U2: "unbound", U3: "bound"}
                and ch0 == [2, V0, "reassign_stall"] and ch3 is None and "DIED AS A CHALLENGER" in note
                and "may differ from R0's" in note
                and any("class at death latched" in x and "CHALLENGER" in x for x in rep)), (cls, ch0, ch3, note)
    _try("m6-1 every candidate's class at death (bound / latched / unbound / carrying, from the record) and, for "
         "KO-OTHERS, whether U died as a CHALLENGER (bound by a J replacement), are printed in the W3 report (with m5's "
         "refused / aborted decisions)", m6)


def m7_cases():
    """m7: the ledger J was passed vs dp.commands (Z-R1)."""
    units = {U0: (2, 2, False, EN), U1: (8, 8, False, FREE), U2: (9, 9, False, FREE)}
    hist = {DA.pkey(U0, V0): {"H": [[19, 19]]}}
    pb = {(U0, V0): [[[2, 3]], 9, 0, False, 9, {}]}

    def dp_of(e, extra=()):
        prior = [[5, "post", "assign", V0, U1, "joint_initial", True, True, 5, 5],
                 [8, "post", "unassign", V0, U1, "joint_replacement_after_blocked", True, None, None, None],
                 [9, "post", "assign", V0, U0, "joint_initial", True, True, 5, 5]]
        return {"commands": prior + list(extra) + e["cmds"], "j_detail": [[e["step"], e["phase"], e["cur"]]]}

    def f():
        e = emulate([U1, U2], [], units, {V0: (5, 5)}, {V0: {U0: (20, 20), U1: (15, 15), U2: (18, 18)}},
                    contest={V0: U0}, progress_before=pb, hist=hist, ledger={(U1, V0): 1, (U0, V0): 1})
        ok, amb, n = DA.ledger_zeros(dp_of(e))
        bad = copy.deepcopy(e)
        pc = next(c for c in bad["cur"]["calls"] if c["fn"] == "plan_replacements_detail")
        pc["b"][DA.pkey(U1, V0)] += 1
        bz, _a, _n = DA.ledger_zeros(dp_of(bad))
        bad2 = copy.deepcopy(e)
        next(c for c in bad2["cur"]["calls"] if c["fn"] == "plan_replacements_detail")["b"][DA.pkey(U2, V0)] = 1
        bz2, _a, _n = DA.ledger_zeros(dp_of(bad2))
        Z, _st, _x = DA.dispatch_zeros(dp_of(bad), [], [], {}, {}, True)
        amb_e = [[50, "post", "assign", V0, U2, "initial", True, True, 5, 5]]
        az, aamb, _n = DA.ledger_zeros(dp_of(bad2, amb_e))
        return (not ok and not amb and n == 2 and len(bz) == 1 and "b = 2, != 1" in bz[0][2] and len(bz2) == 1
                and any("ledger J was passed" in x[2] for x in Z["Z-R1"]) and not az and len(aamb) == 1), (
            ok, bz, bz2, az, aamb)
    _try("m7-1 Z-R1's ledger check: the plan's b equals the ledger rebuilt from dp.commands before the J point "
         "(0 violations); a spare's b raised by 1, or a b on a pair never bound, is flagged (also through "
         "dispatch_zeros); a pair with a non-J assign at the J point's own step and phase is AMBIGUOUS - reported, "
         "never gated", f)

    def fill():
        e = emulate([U0, U1], [V0], {U0: (1, 1, False, FREE), U1: (9, 9, False, FREE)}, {V0: (3, 3)},
                    {V0: {U0: (5, 5), U1: (9, 9)}}, ledger={(U0, V0): 1}, post=False)
        dp = {"commands": [[10, "post", "assign", V0, U0, "joint_initial", True, True, 5, 5]] + e["cmds"],
              "j_detail": [[e["step"], e["phase"], e["cur"]]]}
        ok, _amb, n = DA.ledger_zeros(dp)
        dp_late = {"commands": [[50, "advance", "assign", V0, U0, "joint_initial", True, True, 5, 5]] + e["cmds"],
                   "j_detail": [[e["step"], e["phase"], e["cur"]]]}
        late, _a, _n = DA.ledger_zeros(dp_late)
        return not ok and n == 2 and len(late) == 1, (ok, late)
    _try("m7-2 a J-pre fill's b (a re-used pair, b = 1) equals the bind made before the J point; the same bind stamped "
         "AFTER the J point (step 50 advance > step 50 pre) does not count -> flagged", fill)


def n1_r2f1_cases():
    """N1 (S5's printed status), R2-F1 (S1: params on the common cfv keys, the effective block)."""
    def n1():
        lit = collections.OrderedDict([("F1 ff deaths pooled", {"fail": False}), ("F1 R2 set7", {"fail": False}),
                                       ("F1 R2 set8", {"fail": False}), ("L2 rescued set7", {"fail": True}),
                                       ("L2 rescued set8", {"fail": False}), ("L3 DD pooled", {"fail": True}),
                                       (DA.L4_KEY, {"fail": False})])
        a = DA.s5_literal_fails(lit)
        lit2 = copy.deepcopy(lit)
        lit2["F1 R2 set8"]["fail"] = True
        lit3 = copy.deepcopy(lit)
        lit3[DA.L4_KEY]["fail"] = True
        return (a == [] and DA.s5_literal_fails(lit2) == ["F1 R2 set8"] and DA.s5_literal_fails(lit3) == [DA.L4_KEY]
                and DA.full_verdict(True, True, True, False, True, True) == "FAIL"), (a, )
    _try("N1-1 S5's printed status: L2 / L3 failing (S4's literals) leave S5 PASS; F1 or L4 failing make it FAIL; the "
         "verdict is unchanged (S4 FAIL -> FAIL)", n1)

    def r2f1():
        a = {k: [1] for k in DA.R.FIELDS}
        a.update({"params": {"NUM_FIREFIGHTERS": 3, "NUM_VICTIMS": 5}, "effective": {"global_planner_mode": 0}})
        b = copy.deepcopy(a)
        b["params"]["DISPATCH_JOINT"] = 0
        only = DA.s1_pair(a, b)[0]
        c = copy.deepcopy(b)
        c["params"]["NUM_VICTIMS"] = 4
        com = DA.s1_pair(a, c)[0]
        e = copy.deepcopy(b)
        e["effective"]["global_planner_mode"] = 1
        eff = DA.s1_pair(a, e)[0]
        m = copy.deepcopy(b)
        del m["params"]
        miss = DA.s1_pair(a, m)[0]
        want = [x for x in only if x not in (DA.S1_PARAMS, DA.S1_EFFECTIVE)]
        return (DA.S1_PARAMS not in only and DA.S1_EFFECTIVE not in only and DA.S1_PARAMS in com
                and DA.S1_EFFECTIVE in eff and DA.S1_PARAMS in miss and DA.S1_PARAMS not in want), (only, com, eff, miss)
    _try("R2F1-1 S1 compares params on the cfv keys present in BOTH records (a DISPATCH_* key in dq0 only is not "
         "compared; a common key that differs fails; a missing params block fails) and the 'effective' block", r2f1)


def main() -> int:
    stat_cases()
    l4_cases()
    owner_cases()
    s1_cases()
    diverged_cases()
    d_cases()
    jpoint_cases()
    run_level_cases()
    ko_cases()
    own_vs_jd_cases()
    override_vs_replay_cases()
    random_jpoint_cases()
    validity_cases()
    w3_end_to_end()
    outcome_e2e()
    header_cases()
    # the review fixes (M1-M3, m1-m7, N1, R2-F1, R2-F2): each case fails without its fix
    m1_cases()
    smp_cases()
    m2_m3_cases()
    order_cases()
    m2_uncomputable_cases()
    m3_cases()
    w3_report_cases()
    m7_cases()
    n1_r2f1_cases()
    LINES.append("")
    LINES.append("SELF-TEST %s (%d cases, %d failed)" % ("PASS" if not FAILS else "FAIL", sum(
        1 for ln in LINES if ln.startswith(("PASS", "FAIL"))), len(FAILS)))
    text = "\n".join(LINES)
    print(text)
    if "--out" in _argv:
        with open(_argv[_argv.index("--out") + 1], "w", encoding="utf-8", newline="\n") as fh:
            fh.write("dispatch round 2 - synthetic-record self-test of outputs/_dq_analyze.py\n\n" + text + "\n")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
