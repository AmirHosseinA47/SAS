"""MVG round: SYNTHETIC-RECORD SELF-TEST of outputs/_mvg_analyze.py (it must pass before any real run is read). A port
of urgency:outputs/_ud_analyze_selftest.py (5dba5bcb) without its U1 cases (U1 is in no arm of this round), plus every
known-answer case outputs/urgency_part1d.txt names:
  - 1d.8 (6): R2 known answers (a set with 4 cells up and none down -> no rejection; 5 up -> rejection, p = 1/32; 3 up
    2 down -> none; a pooled +1 -> FAIL); veto rows (Zm-a skips them; no mismatch); an OVER-VETO row and an UNDER-VETO
    row (Zg-1 fails);
  - 1d.13.4: L4 - an advanced death counts as CAUSED, a postponed one as PREVENTED, an UNRESOLVED (A) counts as
    CAUSED, a swap counts +1 / +1, a tie passes;
  - the rest of what this port adds: Zg-2, Zg-3, the guard record's bookkeeping, the shadow-mismatch routing with the
    guard, the outcomes and per-switch rule of 1d.6.3, the zero-to-comparison map of 1d.6.2, review 1.3's classes and
    route-closure chain, the W3 rule's knockout evidence, and an END-TO-END W3 check on synthetic files (the frozen
    queue re-derived, R0 reproduction, a knockout that did not apply, a W2 record changed after generation).
Hand-built records only (no run, no model); a temporary directory for the file cases. One line per case; exit 1 if any
fails.

    E:/Projects/SAS/.venv/Scripts/python.exe -B outputs/_mvg_analyze_selftest.py [--out PATH]
"""
from __future__ import annotations

import collections
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_argv = sys.argv
sys.argv = _argv[:1]
import _mvg_analyze as UA  # noqa: E402
import _mvg_queue as Q  # noqa: E402
import _mvg_w3_queue as W3Q  # noqa: E402
sys.argv = _argv

U0, U1_, U2_ = "ff_unit_0", "ff_unit_1", "ff_unit_2"
V0, V1, V2 = "victim_0", "victim_1", "victim_2"
LINES: list[str] = []
FAILS: list[str] = []


def case(name, cond, detail=""):
    LINES.append("%-4s %s%s" % ("PASS" if cond else "FAIL", name, ("  | " + str(detail)[:300]) if detail else ""))
    if not cond:
        FAILS.append(name)


def cmd(step, phase, action, vid, uid, reason="initial", ok=True, d_route=5):
    return [step, phase, action, vid, uid, reason, ok, True, d_route, d_route]


def ffrow(uid, x, y, status="en_route", assigned=1, exiting=0, dead=0, victim=None, target=None):
    return [uid, x, y, status, assigned, exiting, dead, 0, victim, target, 0, None]


def mvrow(i, step, unit, **kw):
    r = {"_i": i, "step": step, "unit": unit, "victim": V0, "leg": "approach", "branch": "approach", "pre": (1, 1),
         "post": (1, 2), "target": (9, 9), "digest": "d0", "st_pre": "en_route", "st_post": "en_route", "tier": 1,
         "mt": 1, "rb_call": 0, "rb_set": 0, "trig": False, "zrb": False, "today": ["greedy", (1, 2), 1, False],
         "fa": None, "fb": None, "fbB": None, "fc": None, "acted": "", "dc": 10, "dcx": 10, "df": 10, "dm": 10,
         "dr": 10, "gesc": True, "cls_pre": "C", "cls_post": "C", "fd_pre": 5, "fd_post": 5, "c1_pre": None,
         "c1_post": None, "fix_ms": 0.0, "inst_ms": 0.0, "dcb": 3, "gA": None, "gB": None, "veto": "", "acted_g": ""}
    r.update(kw)
    return r


def digest(h, cmds=None, kicks=None, events=None, rows=None, so=None, marks=None, ev=None):
    return {"h": {"rows_ff": list(h)}, "cmds": cmds or [], "eval": ev or {"rescued": 1}, "so": so or ["l0"],
            "so_marks": marks or [None] * len(so or ["l0"]), "kicks": kicks or [], "mv_events": events or [],
            "mv_rows": rows or [], "dry": False}


def kick(i, step, qualifies=True, u1=(V0, V1), index=(V0, V1), bound=((V0, U0),), divergent=False,
         div_shadow=False, ms_model=None, triage=None, F=((U0, (1, 1)),), rec=None, z4_ok=True):
    W = [[v, [i, i]] for v in index]
    return {"i": i, "step": step, "phase": "post", "site": "K1", "W": W, "F": [[f, list(c)] for f, c in F],
            "index": list(index), "qualifies": qualifies, "u1": list(u1) if u1 is not None else None,
            "rec": rec if rec is not None else {v: [100.0, 5, True] for v in index}, "d": {}, "nB": 3,
            "z4": None, "z4_ok": z4_ok, "div_shadow": div_shadow, "bound": [list(b) for b in bound],
            "divergent": divergent, "ms_model": ms_model, "triage": triage}


def kick2(i, step, index, u1, acc, bound, qualifies=True):
    """A ud_probe v2 kick record (the U1 shadow's bookkeeping, kept by mvg_probe v1)."""
    K = kick(i, step, qualifies=qualifies, u1=u1, index=index, bound=bound, ms_model=1.0 if qualifies else None)
    first = lambda xs: next((v for v in xs if acc.get(v)), None)                    # noqa: E731
    K["acc"] = dict(acc)
    K["index_wb"], K["u1_wb"] = first(index), first(u1)
    K["div_shadow"] = bool(qualifies and K["u1_wb"] != K["index_wb"])
    K["divergent"] = bool(qualifies and (bound[0][0] if bound else None) != K["index_wb"])
    return K


def grow(step, unit, kind, admit, model_admit, took, c=5, T_v=20.0, **kw):
    """A guard row (d['mvg']['guard'] as guard_dicts returns it)."""
    r = {"step": step, "unit": unit, "victim": V0, "kind": kind, "u": (5, 5), "n": (5, 6), "v": (9, 9),
         "today": (4, 5), "today_kind": "greedy" if kind == "a" else "survival", "today_tier": 3 if kind == "a" else None,
         "today_raise": False, "c": c if admit else None, "T_v": T_v, "admit": admit, "model_admit": model_admit,
         "model_verdict": None if model_admit is None else [bool(model_admit), c if admit else None, T_v],
         "model_cell": None if model_admit is None else (5, 6), "took": took,
         "post": (5, 6) if took == "fix" else (4, 5), "tier": 7 if (took == "fix" and kind == "a") else
         10 if took == "fix" else 3, "raise": False, "pre_writes": None, "pred_writes": None, "post_writes": None,
         "ms_guard": None if model_admit is None else 1.0, "ms_inst": 1.0, "row": 0}
    r.update(kw)
    return r


def reported_cases():
    """Known answers for the REPORTED measures of section 6 (6.R1-6.R4; functions verbatim from the urgency
    analyzer); none gates anything."""
    def g_(det, resc):
        return {"victims": [V0, V1], "det": det, "resc": resc, "censor": 361}
    c1 = {"id": "set5/ring/A_N", "set": "set5", "plc": "ring", "scen": "A"}
    c2 = {"id": "set5/uniform/B_N", "set": "set5", "plc": "uniform", "scen": "B"}
    c3 = {"id": "set6/ring/A_N", "set": "set6", "plc": "ring", "scen": "A"}
    rows = [(c1, g_({V0: 10, V1: 20}, {V0: 50, V1: 80}), g_({V0: 10, V1: 20}, {V0: 40, V1: 100})),
            (c2, g_({V0: 5, V1: 7}, {V0: 25}), g_({V0: 5, V1: None}, {V0: 15})),
            (c3, g_({V0: 5, V1: None}, {}), g_({V0: 5, V1: None}, {V0: 50}))]
    res = UA.m1_compare(rows)
    cset = {c["id"]: c["set"] for c in (c1, c2, c3)}
    st = UA.m1_stat(res["m1"], cset, UA.FRESH)
    stc = UA.m1_stat(res["m1c"], cset, UA.FRESH)
    case("M1-1 M1: per-victim deltas -10 / +20 give m_c +5 in one cell, -10 in another; T(set5) = -2.5 (unweighted "
         "over cells), +5 after removing the most negative m_c; a cell without a rescued pair is listed and excluded; "
         "a victim detected in one arm only is listed",
         res["m1"] == {c1["id"]: 5.0, c2["id"]: -10.0} and st["T"]["set5"] == -2.5 and st["loo"]["set5"] == 5.0
         and st["n"]["set6"] == 0 and st["T"]["set6"] is None and st["T"]["pooled"] == -2.5
         and res["no_pair"] == [c3["id"]] and res["only_one"] == [(c2["id"], V1, 7, None)], (res["m1"], st))
    case("M1-2 M1c: a victim dead in X and rescued at 50 in Y gives (50 - 5) - (361 - 5) = -311; pooled T over 3 cells "
         "= -105.33, -2.5 after removing the most negative m_c",
         res["m1c"] == {c1["id"]: 5.0, c2["id"]: -10.0, c3["id"]: -311.0}
         and abs(stc["T"]["pooled"] - (5 - 10 - 311) / 3.0) < 1e-12 and stc["loo"]["pooled"] == -2.5, stc)
    w = UA.wilcoxon([1.0, 2.0, 3.0])
    case("M1-3 Wilcoxon on m_c (DPR verbatim): three positive values -> W+ 6, exact two-sided p = 2 x 1/8 = 0.25",
         w["w_plus"] == 6.0 and w["method"] == "exact" and abs(w["p"] - 0.25) < 1e-12, w)
    decs = [{"k": 0, "step": 10, "vid": V0, "T": 10.0, "P": True, "first_burn": 15, "pickup": 12, "death": None,
             "complete": 20},
            {"k": 0, "step": 10, "vid": V1, "T": 20.0, "P": False, "first_burn": None, "pickup": None, "death": 55,
             "complete": None},
            {"k": 0, "step": 10, "vid": V2, "T": 5.0, "P": True, "first_burn": 40, "pickup": 45, "death": None,
             "complete": None}]
    h = UA.mu3_concordance(decs, 60)
    case("MU3-1 Harrell C on a 3-victim run: comparable pairs 3, concordant 2 -> C = 2/3 (per kick and per run); death "
         "target (0, 0, 1)",
         h[("kick", "burn")] == (2, 0, 3) and h[("run", "burn")] == (2, 0, 3) and UA.cval(h[("kick", "burn")]) == 2 / 3
         and h[("kick", "death")] == (0, 0, 1) and h[("run", "death")] == (0, 0, 1), h)
    vc = UA.mu3_verdicts(decs)
    case("MU3-2 verdict vs outcome: P picked up before the burn; D never picked up, died; P picked up after the burn",
         vc == {("P", "picked before burn", "survived"): 1, ("D", "never picked", "died"): 1,
                ("P", "picked after burn", "survived"): 1}, dict(vc))
    burn, death, cens, noest = UA.mu3_bias(decs + [dict(decs[0], vid="victim_9", T=None)], 60)
    case("MU3-3 bias: T - (first burn - step) = 5, -30 (censored at the horizon 60), -25; vs death -25; an infinite T is "
         "no estimate", burn == [5.0, -30.0, -25.0] and death == [-25.0] and cens == 1 and noest == 1,
         (burn, death, cens, noest))
    b1 = UA.seed_bootstrap({("set5", "A_N"): (2, 0, 3)})
    b2 = UA.seed_bootstrap({("set5", "A_N"): (1, 0, 1), ("set5", "B_N"): (0, 0, 1)})
    case("MU3-4 seed-level bootstrap: one cluster -> C 2/3, degenerate interval; two clusters C = 0.5 in [0, 1]; ring "
         "and uniform of one seed are ONE cluster",
         b1[:3] == (2 / 3, 2 / 3, 2 / 3) and b1[3] == 3 and b1[4] == 2000 and b2[:3] == (0.5, 0.0, 1.0)
         and UA.seed_cluster({"set": "set5", "key": "A_N", "plc": "ring"})
         == UA.seed_cluster({"set": "set5", "key": "A_N", "plc": "uniform"}), (b1, b2))
    o1 = [cmd(10, "advance", "unassign", V0, U0, "replacement_after_blocked")]
    case("MU4-1 stranding: an o1 unassign at 10 and the unit's death at 25 (15 steps) is a stranding; at 26 it is not; a "
         "casualty unassign is never one",
         len(UA.strandings(o1, {U0: 25})) == 1 and not UA.strandings(o1, {U0: 26})
         and not UA.strandings([cmd(10, "post", "unassign", V0, U0, "firefighter_fire_casualty")], {U0: 12}))
    rows_ff = []
    for t in range(1, 31):
        if t < 5:
            r0 = ffrow(U0, 1, 1, status="available", assigned=0)
        elif t < 9:
            r0 = ffrow(U0, 1, 1, status="en_route", assigned=1, victim=V0)
        elif t < 12:
            r0 = ffrow(U0, 1, 1, status="route_blocked", assigned=0)
        else:
            r0 = ffrow(U0, 1, 1, status="dead", assigned=0, dead=1)
        r1 = ffrow(U1_, 5, 5, status="en_route", assigned=1, victim=V1) if t >= 5 else ffrow(U1_, 5, 5, assigned=0)
        rows_ff.append([r0, r1])
    cmds = [cmd(5, "post", "assign", V0, U0), cmd(5, "post", "assign", V1, U1_),
            cmd(9, "advance", "unassign", V0, U0, "replacement_after_blocked")]
    ctx = [["kick:K1"], ["kick:K1"], ["adv:ff_unit_0"]]
    kicks = [kick(0, 5, divergent=True, div_shadow=True, u1=(V0, V1), index=(V1, V0), bound=((V0, U0),))]
    mv = [mvrow(0, 6, U0, cls_post="C"), mvrow(1, 7, U0, cls_post="A"), mvrow(2, 8, U0, cls_post="B", rb_set=1),
          mvrow(3, 6, U1_, victim=V1, cls_post="S")]
    evs = [{"step": 7, "kind": "a", "unit": U0, "victim": V0, "live": False}]
    tab, strand, deaths = UA.mu4_exposure(rows_ff, cmds, ctx, kicks, mv, evs, {U0: 12})
    case("MU4-2 exposure split by bind leg (the shadow-divergent kick's leg with a would-act fix event holds 3 unit-steps, "
         "2 unclean, the raise, the onset, the stranding and the rb_unbound death)",
         tab["legs"] == {"n": 2, "div": 1, "acted": 1} and tab["unit_steps"] == {"n": 4, "div": 3, "nodiv": 1,
                                                                                  "acted": 3, "notacted": 1}
         and tab["unclean"] == {"n": 3, "div": 2, "nodiv": 1, "acted": 2, "notacted": 1}
         and tab["raises_mv"] == {"n": 1, "div": 1, "acted": 1} and strand == [[9, U0, V0, 12, True, True]]
         and deaths == [[12, U0, "rb_unbound", None, True, True]], (dict(tab), strand, deaths))
    binders = [[1, [[V0, [[U0, "en_route"], [U1_, "route_blocked"]]]]], [2, [[V0, [[U0, "en_route"], [U1_, "en_route"]]]]],
               [3, [[V1, [[U0, "en_route"]]]]]]
    n, _l = UA.gb_counts(binders, [[2, "RescueInvariant: double binding"]])
    case("DP-1 G-B: (a) 2, (b) 1 (a route_blocked binder is not active), (d) 1",
         n["gb_a"] == 2 and n["gb_b"] == 1 and n["gb_d"] == 1, dict(n))
    b = [cmd(1, "post", "assign", V0, U0), cmd(3, "post", "assign", V0, U1_), cmd(5, "post", "assign", V0, U0)]
    rets = UA.gt_returns_amended(b, [[s, []] for s in range(1, 6)], {U1_: 4}, {})
    n, rows_gt = UA.gt_b_counts(rets)
    case("DP-2 G-T(b): an A..X..A return whose X died between (o3)",
         dict(n) == {"gt_b_o3": 1} and rows_gt == [[5, "post", V0, U0, U1_, "victim", ["o3"]]], (dict(n), rows_gt))
    n, _l, chk = UA.rb_figures([[5, 2, [[V0, [[U0, 4, 0]]]]]], [[5, []]], [[5, 2, 0, [U0, U1_]]], [], False)
    case("DP-4 M3 (DPR rb_figures, live False): m3a 2, m3b 1, the tooling checks pass",
         n["m3a"] == 2 and n["m3a_allowed"] == 2 and n["m3b_allowed"] == 1 and not UA.rb_checks_fail(chk), dict(n))


def gsyn(dd, resc, ffd, extra=None):
    num = collections.Counter({"DD": dd, "rescued": resc, "ff_deaths": ffd, "of_broad": 2, "never_detected": 1})
    num.update(extra or {})
    return {"usable": True, "num": num, "wall_s": 100.0, "fix_ms": 50.0, "fix_calls": {"a": [0.5, 1.5], "g": [3.0]},
            "eval": {"rescued": resc, "firefighter_deaths": ffd, "dead": 0}, "deaths": [], "ff_dead": {},
            "decisions": [], "kicks": [], "lists": {}, "latched_end": [], "terminal": 300, "n_ff": 5, "horizon": 360,
            "mu4": {}, "rb_checks": {}, "rb_fail": False, "det": {}, "resc": {}, "victims": [], "censor": 361,
            "acted_ran": {"a": True, "b": True}, "m8": [], "Z": {}, "gnum": {}, "guard_legs": [], "guard_alt": {},
            "pvm": {"raise": {}, "o1": {}, "dead": {}}, "vetoes": [], "guard_ms": [], "inst_guard_ms": [],
            "probe_frac": 0.004}


def srec(cell_id="set5/ring/A_N", G=None):
    k = int(cell_id[3])
    cell = {"id": cell_id, "set": "set%d" % k, "k": k, "fresh": True, "kind": "screen", "plc": cell_id.split("/")[1],
            "p": cell_id.split("/")[1][0], "scen": cell_id[-3], "key": cell_id[-3:], "arms": UA.ARMS}
    return {"cell": cell, "g": {"0": gsyn(2, 3, 1), "G": G or gsyn(1, 4, 0), "N": gsyn(3, 2, 2)}, "prov": {},
            "crash": {}, "missing": [], "stop": [],
            "pairs": {xy: {"s": None, "ident": False, "D": 5, "viol": [], "what": ["eval"]} for xy in UA.COMPARISONS}}


def review_cases():
    """The urgency self-test's non-U1 review cases, ported."""
    ky = [kick2(0, 7, index=(V0, V1, V2), u1=(V1, V0, V2), acc={V0: False, V1: True, V2: True}, bound=((V1, U0),))]
    case("B-1b the reported kick-flag consistency check (the U1 shadow's bookkeeping) passes a consistent record and "
         "flags a div_shadow that disagrees with acc", not UA.kick_flag_check(ky[0])
         and UA.kick_flag_check(dict(ky[0], div_shadow=True)) == ["div_shadow"], UA.kick_flag_check(ky[0]))
    opts = types.SimpleNamespace(smoke="x", head=None)
    d = {"crashed": {"type": "ValueError", "step": 0}, "steps": 360, "steps_done": 0, "terminal_step": None,
         "extra_params": {}, "dp": {"probe": "dp_probe v2"}, "ud": {"probe": UA.MVG_PROBE, "switches": {}},
         "mvg": {"probe": UA.MVG_PROBE, "switches": {"FF_FIX_STRANDING_GUARD": True},
                 "guard": {"cols": list(UA.GUARD_COLS), "rows": []}},
         "fb3": {"crn": {"on": True, "crn_draws": 0}}, "mv": {"cols": list(UA.MV_COLS), "rows": []}}
    why, crash, _s = UA.prov_run(d, os.path.join(HERE, "__no_such_run__.json"), None, None, opts)
    d_rc = dict(d, crashed=None, steps_done=360, dp={"probe": "dp_probe v2", "rc_chain": 1},
                fb3={"crn": {"on": True, "crn_draws": 9}})
    _w, crash_rc, _s = UA.prov_run(d_rc, os.path.join(HERE, "__no_such_run__.json"), None, None, opts)
    case("m-1 a run that crashed before any CRN draw and wrote no stdout goes to Z6 (crash text), with no CRN-draw or "
         "stdout INVALID reason; a non-zero chain exit code is a crash too",
         crash is not None and not any("crn" in w.lower() or "stdout" in w for w in why)
         and crash_rc == "chain exit code 1", (why, crash, crash_rc))
    rec = {"cell": {"id": "set1/ring/A_N", "set": "set1", "kind": "w1"}, "ident": (["eval"], "", [],
                                                                                   ".eval.rescued: 3 != 2"),
           "ref_bad": None, "g": {}, "prov": {}, "crash": {}, "port": None}
    n0 = len(UA._LINES)
    with contextlib.redirect_stdout(io.StringIO()):
        UA.sec_z0([rec], types.SimpleNamespace(smoke=None, zeros_only=False, smoke_files={}))
        UA.sec_z0([rec], types.SimpleNamespace(smoke=None, zeros_only=True, smoke_files={}))
    z0_lines = UA._LINES[n0:]
    zrec = {"cell": {"id": "set5/ring/A_N", "set": "set5"}, "pairs": {},
            "g": {"G": {"usable": True, "lists": {}, "Z": {"Zg-2": [[60, U0, "b", "veto (b): writes [1] != [2]"]]}}}}
    with contextlib.redirect_stdout(io.StringIO()):
        UA.sec_zeros([zrec], {"gate": [], "stop": []}, types.SimpleNamespace(smoke=None, zeros_only=True))
    z_lines = UA._LINES[n0 + len(z0_lines):]
    del UA._LINES[n0:]
    inst = [ln.split("owner GUARD:", 1)[1] for ln in z_lines if "owner GUARD:" in ln]
    case("m-2 S1 identity lines print the field path and 'differs', never a value ('3 != 2'), in EVERY mode (sets 1-4: "
         "no outcome is printed in this round); the M8 reproduction prints no count; --zeros-only masks every number "
         "of a zero's failure instance",
         not any("3 != 2" in ln for ln in z0_lines) and sum(".eval.rescued differs" in ln for ln in z0_lines) == 2
         and not any(re.search(r"FC \d|futile \d", ln) for ln in z0_lines) and inst
         and not any(re.search(r"\d", x) for x in inst), (z0_lines, inst))
    st_miss = {"missing": [("G", "set6/ring/B_N")], "invalid": [], "gate": [], "stop": [], "seed": []}
    st_ok = {"missing": [], "invalid": [], "gate": [], "stop": [], "seed": []}
    bad = re.compile(r"LITERAL|SIGN-TESTED|rescued|\bDD\b|\bF[1-8]\b|FULL|HARMLESS|\bM8\b|\bMU[1-4]\b|->\s+\d+|CAUSED")
    w3_ok = {"complete": True, "state": "COMPLETE", "l4": {"G": UA.l4_counts([]), "N": UA.l4_counts([])},
             "items": {"G": [], "N": []}, "same": [], "uncomputable": []}
    outs = {}
    for name, st, w3, op in (("zeros-only", st_ok, w3_ok, types.SimpleNamespace(smoke=None, zeros_only=True,
                                                                                 allow_incomplete=False)),
                             ("incomplete", st_miss, w3_ok, types.SimpleNamespace(smoke=None, zeros_only=False,
                                                                                  allow_incomplete=False)),
                             ("w3-missing", st_ok, {"complete": False, "state": "W3 NOT GENERATED"},
                              types.SimpleNamespace(smoke=None, zeros_only=False, allow_incomplete=False)),
                             ("control", st_miss, w3_ok, types.SimpleNamespace(smoke=None, zeros_only=False,
                                                                               allow_incomplete=True))):
        n0 = len(UA._LINES)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                UA.outcome_sections([srec()], st, {"pass": True, "fail": False}, {"fails": [], "stop": []}, w3, op)
        except Exception as exc:                     # noqa: BLE001 - the control may not render every section here
            UA._LINES.append("EXC %r" % (exc,))
        outs[name] = UA._LINES[n0:]
        del UA._LINES[n0:]
    case("M-3 --zeros-only prints only its line after the W3 validity; a missing run, or a W3 that is not complete, "
         "without --allow-incomplete stops with the INCOMPLETE line - neither prints a LITERAL / F-count / rescued / DD "
         "/ FULL / CAUSED line; with --allow-incomplete the same records DO print them (positive control)",
         outs["zeros-only"] == [UA.ZEROS_ONLY_LINE]
         and not any(bad.search(ln) for ln in outs["incomplete"] + outs["w3-missing"])
         and any("INCOMPLETE" in ln for ln in outs["incomplete"]) and any("W3 NOT GENERATED" in ln
                                                                          for ln in outs["w3-missing"])
         and sum(1 for ln in outs["control"] if "LITERAL" in ln) >= 5,
         (outs["zeros-only"], outs["incomplete"][-1:], outs["w3-missing"][-1:], len(outs["control"])))
    need = ("_ut_probe.py", "_fb3_probe.py", "_fx3_probe.py", "_mf2_probe.py", "_sd_probe.py", "_fm2_probe_harness.py",
            "_ffr_harness.py", "_bp_inst.py", "_mvg_seeds.txt", "_mvg_ref/_MANIFEST.sha256", "_mvg_q_w1.jsonl",
            "_mvg_q_w2.jsonl", "_mvg_probe.py", "_mvg_u1_shadow.py", "_mvg_replay.py", "_mvg_w3_queue.py",
            "_mvg_queue.py", "_mvg_analyze.py", "_mvg_analyze_selftest.py", "_mvg_mutants.py", "_mvg_mutants_mv.py",
            "_mvg_guard_diag.py")
    case("m-4 the Part 2d notes must list the probe chain, the frozen seed / reference lists and queues, the instrument, "
         "replay, W3 and analyzer tooling and the mutation / guard tooling", all("outputs/" + n in UA.NOTES_REQUIRED
                                                                                for n in need))
    sd_out = {"I2_uav_livelock": [[10, 39, "uav_1", [], "victim_searcher", []], [50, 79, "uav_2", [], "fire_tracker",
                                                                                   []]],
              "I2_uav_stuck": [[5, 30, "uav_1", [1, 1], "victim_searcher", 0, []], [5, 30, "uav_2", [1, 1],
                                                                                    "fire_tracker", 0, []]],
              "I6_rtb_no_progress": [[25, 44, "uav_1", [1, 1], [0, 0], 9], [25, 44, "uav_2", [2, 2], [0, 0], 9]]}
    rows_uav = []
    for t in range(1, 51):
        rtb = t >= 4
        rows_uav.append([["uav_1", 1, 1, "victim_searcher" if t <= 4 else "returning", 50.0, rtb, False, (0, 0), "x"],
                         ["uav_2", 2, 2, "victim_searcher" if t < 4 else "fire_tracker", 50.0, rtb, False, (0, 0),
                          "x"]])
    n, l_ = UA.searcher_kinds(sd_out, rows_uav)
    case("D2-1 F4 searcher kinds: I2 LIVELOCK / STUCK for the victim_searcher role only; I6 RTB no-progress by the role "
         "at the first step of the return leg",
         n["os_i2_livelock"] == 1 and n["uav_livelock_all"] == 2 and n["os_i2_stuck"] == 1 and n["os_rtb_noprog"] == 1
         and l_["os_rtb_noprog"][0][-1] == "victim_searcher", dict(n))
    wcmds = [cmd(10, "sweep", "mark_unreachable", V0, "", "geographically_isolated"),
             cmd(10, "sweep", "mark_unreachable", V1, "", "no_firefighter_available"),
             cmd(10, "sweep", "mark_unreachable", V2, "", "geographically_isolated"),
             cmd(12, "post", "mark_unreachable", V0, "", "replacement_after_casualty")]
    n, _l = UA.writeoff_counts(wcmds, {V0: 5, V1: 12, V2: None})
    case("D2-2 F8 escape write-offs of DETECTED victims: 3 sweep write-offs, 1 of a victim detected before it",
         n["escape_writeoffs"] == 3 and n["escape_writeoffs_det"] == 1 and n["dispatch_writeoffs"] == 1, dict(n))
    rows_ff = []
    for t in range(1, 41):
        carry = 5 <= t <= 35
        rows_ff.append([ffrow(U0, 5, 5, status="exiting" if carry else "available", assigned=1 if carry else 0,
                              exiting=1 if carry else 0, victim=V0 if carry else None)])
    dsyn = {"rows_ff": rows_ff, "rows_uav": [[] for _ in range(40)], "params": {"NUM_VICTIMS": 1}, "rows_dec": [],
            "rows_vic": [[[V0, 5, 5, "confirmed", "confirmed", "", 0, 0, 0, 0]] for _ in range(40)]}
    base_sd, _i = UA.SD.analyze("t", dsyn, UA.STUCK, UA.WIN)
    eps0, n0x = UA.stuck_carry_excluded("t", dsyn, [mvrow(0, 15, U0, leg="carry", branch="path")])
    case("D2-3 F5 I2 STUCK carry: a carrier 31 steps on one cell is 1 stuck episode; 22.8.3's exclusion is VOID in this "
         "round (no C-2 stay / C-3 hold row exists without fix (c)): a carry row excludes nothing",
         len(base_sd.get("I2_ff_stuck_carry") or []) == 1 and eps0 is None and n0x == 0,
         (len(base_sd.get("I2_ff_stuck_carry") or []), n0x))
    cells = [(5, 5), (5, 6), (5, 5)] + [(6, k) for k in range(9)]
    leg = [mvrow(i, 100 + i, U0, leg="carry", branch="path", pre=cells[i], dr=6) for i in range(12)]
    ev = UA.leg_events(leg)
    case("D2-4 carry legs (MODE 2 path rows): a recurring cell is a CYCLE, the route distance flat for 10 steps a "
         "PROGRESS violation", ev["cycle"] and ev["prog"], ev)
    rows_vic = [[[V0, 1, 9, "candidate", "candidate", "", 0, 0, 0, 0]] for _ in range(40)]
    m8e = {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 5}
    pos = {1: (1, 1), 2: (1, 2), 3: (1, 1), 4: (1, 2), 5: (1, 1)}
    rows_ff_a = [[ffrow(U0, *pos.get(t, (1, 1)), victim=V0, assigned=1)] for t in range(1, 41)]
    cls_a, _f, _m = UA.attribute(V0, 10, 30, m8e, [], [], [], UA.ff_cells_by_step(rows_ff_a), rows_ff_a, rows_vic,
                                 [mvrow(0, 4, U0)], [], [], {}, [], [])
    rows_ff_s = [[ffrow(U0, 1, 1, victim=V0, assigned=1)] for _ in range(40)]
    ffs_s = UA.ff_cells_by_step(rows_ff_s)
    cls_b, _f, _m = UA.attribute(V0, 10, 30, m8e, [], [], [], ffs_s, rows_ff_s, rows_vic,
                                 [mvrow(0, 20, U0, trig=True, fbB=[(5, 5)], today=["survival", (1, 2), 1, False])],
                                 [], [], {}, [], [])
    cls_rp, _f, _m = UA.attribute(V0, 10, 30, m8e, [], [], [[19, 1, [[V0, [[U1_, 3, 0]]]]]], ffs_s, rows_ff_s,
                                  rows_vic, [], [], [], {}, [cmd(20, "post", "assign", V0, U0, d_route=8)], [["adv"]])
    case("D2-5 22.9 classes (frozen, verbatim): an approach loop with a finite shadow clean distance -> MOV-a; a survival "
         "retreat off a non-empty on-route set B -> MOV-b; another free unit strictly shorter at her last bind -> RP",
         cls_a == "MOV-a" and cls_b == "MOV-b" and cls_rp == "RP", (cls_a, cls_b, cls_rp))


def routing_cases():
    """The shadow-mismatch routing of this round (urgency 24.1 (g) with the guard): behaviour, never INVALID."""
    mov_row = [9, U0, "a", "shadow acted, model did not", "approach", [2, 1], [1, 2]]
    grd_row = [9, U0, "a", "model guard verdict != instrument verdict", "approach_a", [True, 5, 9.0], [False, None, 9.0]]
    kick_row = [7, U0, "u1", "kick bind differs from the acc shadow", "kick:0", V1, V2]
    ev_dis = [{"step": 11, "kind": "b", "unit": U0, "live": True, "agree": False, "branch": "retreat"},
              {"step": 9, "kind": "a", "unit": U0, "live": True, "agree": False, "branch": "approach"}]
    zg = UA.shadow_mismatch_zeros([grd_row, mov_row, kick_row], ev_dis, "G")
    case("SMR-G in G: a guard-text row -> Zg-1 (guard-owned); another (a) / (b) row -> Z1-M (v); a live disagreement "
         "already in a row is not duplicated, one without a row is added; a kick row -> SM (reported outside arm 0)",
         sorted(zg) == ["SM", "Z1-M", "Zg-1"] and len(zg["Zg-1"]) == 1 and len(zg["Z1-M"]) == 2 and len(zg["SM"]) == 1
         and UA.zero_owners("Zg-1", "G") == {"GUARD"} and UA.zero_owners("SM", "G") == "REPORTED", zg)
    zn = UA.shadow_mismatch_zeros([grd_row], [], "N")
    z0 = UA.shadow_mismatch_zeros([mov_row, kick_row], [], "0")
    case("SMR-N/0 in N a guard text is Z1-M (the guard ran although off: N is not 'the fixes without the guard'); in arm "
         "0 every row is SM, a STOP",
         list(zn) == ["Z1-M"] and list(z0) == ["SM"] and len(z0["SM"]) == 2 and UA.zero_owners("SM", "0") == "STOP",
         (zn, z0))
    veto_ev = [{"step": 12, "kind": "a", "unit": U0, "live": True, "agree": True, "vetoed": True, "ran": False,
                "branch": "approach_a_veto"}]
    case("VETO-2 a vetoed decision whose model took today's step (agree True) produces no mismatch instance",
         UA.shadow_mismatch_zeros([], veto_ev, "G") == {})
    rows_ff = [[ffrow(U0, 1, 1, victim=V0, assigned=1)] for _ in range(40)]
    rows_vic = [[[V0, 1, 9, "candidate", "candidate", "", 0, 0, 0, 0]] for _ in range(40)]
    ffs = UA.ff_cells_by_step(rows_ff)
    m8e = {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 5}
    dec = [{"k": 0, "step": 12, "vid": V0, "d": 6, "served": False, "accepted": False},
           {"k": 0, "step": 12, "vid": V1, "d": 3, "served": True, "accepted": True}]
    cls_r, fl_r, _m = UA.attribute(V0, 10, 30, m8e, dec, [], [], ffs, rows_ff, rows_vic, [], [], [], {}, [], [])
    cls_a, _f, _m = UA.attribute(V0, 10, 30, m8e, [dict(dec[0], accepted=True), dec[1]], [], [], ffs, rows_ff,
                                 rows_vic, [], [], [], {}, [], [])
    case("SMR-5 22.9's U1 class (from the instrument's U1 shadow): a planner-REFUSED victim passed over is never U1; "
         "accepted, she is", cls_r != "U1" and not fl_r["U1"] and cls_a == "U1", (cls_r, cls_a))


def smoke_case():
    """--smoke prints no outcome: the STRUCTURE counts and the S6 cost lines only; the same records outside smoke DO
    print outcomes (positive control)."""
    rec = srec()
    zres = {"fails": [], "stop": []}
    st = {"missing": [], "invalid": [], "gate": [], "stop": [], "seed": []}
    n0 = len(UA._LINES)
    with contextlib.redirect_stdout(io.StringIO()):
        UA.outcome_sections([rec], st, {"pass": True, "fail": False}, zres, None,
                            types.SimpleNamespace(smoke="synthetic", allow_incomplete=False))
    smoke = UA._LINES[n0:]
    n1 = len(UA._LINES)
    with contextlib.redirect_stdout(io.StringIO()):
        UA.sec_comparisons([rec], zres, True, None)
    full = UA._LINES[n1:]
    del UA._LINES[n0:]
    bad = re.compile(r"LITERAL|SIGN-TESTED|rescued|\bDD\b|\bF[1-8]\b|\bS[2-5]\b|FULL|HARMLESS|VERDICT|\bM8\b|\bM1c?\b"
                     r"|\bMU[1-4]\b|death|never-detected|->\s+\d+\s+\||CAUSED")
    leaks = [ln for ln in smoke if bad.search(ln)]
    case("SM-1 --smoke prints no outcome: the STRUCTURE line per arm (3) and the S6 cost line per comparison (3) and the "
         "suppression line - no literal / sign-tested / rescued / DD / FULL / L4 / decision line; outside smoke the "
         "same records DO print them",
         not leaks and smoke[-1] == UA.SMOKE_SUPPRESSED and sum(1 for ln in smoke if ln.startswith("  S6 COST")) == 3
         and sum(1 for ln in smoke if ln.startswith("  STRUCTURE")) == 3 and sum(1 for ln in full if bad.search(ln))
         >= 20 and any("LITERAL" in ln for ln in full), leaks[:3] or smoke)


def r2_cases():
    """1d.3.3 / 1d.8 (6): F1 read as R2 - known answers."""
    cells = ["set5/ring/%s_N" % s for s in "ABCD"] + ["set5/uniform/%s_N" % s for s in "ABCD"] + \
        ["set5/ring/%s_S" % s for s in "AB"] + ["set6/ring/%s_N" % s for s in "ABCD"] + \
        ["set6/uniform/%s_N" % s for s in "ABCD"] + ["set6/ring/%s_S" % s for s in "AB"]
    cset = {c: c.split("/")[0] for c in cells}
    s5 = [c for c in cells if c.startswith("set5")]
    s6 = [c for c in cells if c.startswith("set6")]

    def run(up5, down5, up6, down6, div=None):
        nx = {c: {"ff_deaths": 1, "rescued": 3, "DD": 1} for c in cells}
        ny = {c: dict(nx[c]) for c in cells}
        for c in s5[:up5]:
            ny[c]["ff_deaths"] = 2
        for c in s5[up5:up5 + down5]:
            ny[c]["ff_deaths"] = 0
        for c in s6[:up6]:
            ny[c]["ff_deaths"] = 2
        for c in s6[up6:up6 + down6]:
            ny[c]["ff_deaths"] = 0
        return UA.compare_counts(nx, ny, cset, set(cells) if div is None else div)
    r = run(4, 0, 0, 4)
    case("R2-1 a set with 4 cells up, none down: p = 1/16 > 0.05 -> NO rejection (with set 6 4 down, pooled 0): F1 "
         "holds; the R0 reading (per-set literal) would fail and is reported, never gating",
         not r["literal"]["F1 R2 set5"]["fail"] and abs(r["r2"]["set5"]["p"] - 1 / 16) < 1e-15
         and not r["literal"]["F1 ff deaths pooled"]["fail"] and r["S5"] and r["r0"]["fail"], (r["r2"], r["lit_fail"]))
    r = run(5, 0, 0, 5)
    case("R2-2 5 up, none down: p = 1/32 <= 0.05 -> REJECTION: F1 FAILS in set 5 although pooled deaths do not rise",
         r["literal"]["F1 R2 set5"]["fail"] and abs(r["r2"]["set5"]["p"] - 1 / 32) < 1e-15
         and not r["literal"]["F1 ff deaths pooled"]["fail"] and r["lit_fail"] == ["F1 R2 set5"] and not r["S5"],
         (r["r2"], r["lit_fail"]))
    r = run(3, 2, 0, 1)
    case("R2-3 3 up, 2 down: p = P(Bin(5, 1/2) >= 3) = 0.5 -> none; (set 6 one down, pooled 0) F1 holds",
         not r["lit_fail"] and r["r2"]["set5"]["p"] == 0.5 and r["r2"]["set5"]["n_plus"] == 3
         and r["r2"]["set5"]["n_minus"] == 2, (r["r2"], r["lit_fail"]))
    r = run(1, 0, 0, 0)
    case("R2-4 pooled +1 (one cell up, no per-set evidence: p = 0.5) -> F1 FAILS on the pooled literal clause",
         r["lit_fail"] == ["F1 ff deaths pooled"] and not r["literal"]["F1 R2 set5"]["fail"], r["lit_fail"])
    r = run(5, 0, 0, 5, div=set(s5[1:]) | set(s6))
    case("R2-5 the sign test runs over the DIVERGED cells only (a rising cell outside them is not counted: n+ 4)",
         r["r2"]["set5"]["n_plus"] == 4 and not r["literal"]["F1 R2 set5"]["fail"], r["r2"]["set5"])
    nx = {c: {"ff_deaths": 1} for c in cells}
    ny = {c: dict(nx[c]) for c in cells}
    ny["set5/ring/A_N"]["ff_deaths"] = 2
    ny["set5/uniform/A_N"]["ff_deaths"] = 0
    ny["set5/ring/B_N"]["ff_deaths"] = 2
    r = UA.compare_counts(nx, ny, cset, set(cells))
    case("R2-6 by SEED (reported, R2s): ring +1 and uniform -1 of one seed sum to 0 (dropped); a lone +1 seed counts",
         r["r2s"]["set5"]["n_plus"] == 1 and r["r2s"]["set5"]["n_minus"] == 0 and r["r2"]["set5"]["n_plus"] == 2
         and r["r2"]["set5"]["n_minus"] == 1, (r["r2s"]["set5"], r["r2"]["set5"]))


def guard_cases():
    """Zg-1 (two-sided), Zg-2, Zg-3, the veto rows, the guard record's bookkeeping."""
    on = {"a": True, "b": True}
    ok_a = grow(10, U0, "a", True, True, "fix")
    ok_v = grow(11, U0, "a", False, False, "today")
    case("Zg-1 holds: an admitted step taken (the model's verdict and (c_n, T_v) equal the instrument's), a veto with "
         "today's step taken; a row of a fix that is off is a shadow (not checked)",
         not UA.zg1([ok_a, ok_v], on) and not UA.zg1([grow(12, U0, "a", True, None, "today")], {"a": False}),
         UA.zg1([ok_a, ok_v], on))
    over = grow(10, U0, "a", True, False, "today")
    under = grow(10, U0, "a", False, True, "fix")
    under_step = grow(10, U0, "a", False, False, "fix")
    case("Zg-1 OVER-VETO: ADMIT true but the model vetoed (today's step) -> FAIL", any(
        "OVER-VETO" in x[3] for x in UA.zg1([over], on)), UA.zg1([over], on))
    case("Zg-1 UNDER-VETO: ADMIT false but the model admitted (the fix's step) -> FAIL; also when the model's call "
         "vetoed but the fix's step was taken anyway",
         any("UNDER-VETO" in x[3] for x in UA.zg1([under], on)) and any("UNDER-VETO" in x[3]
                                                                        for x in UA.zg1([under_step], on)),
         (UA.zg1([under], on), UA.zg1([under_step], on)))
    no_eval = grow(10, U0, "b", True, None, "fix")
    bad_tuple = dict(ok_a, model_verdict=[True, 6, 20.0])
    bad_rule = grow(10, U0, "a", True, True, "fix", c=20, T_v=20.0)
    case("Zg-1 also fails: the guard not evaluated by the model where a live fix acts; the model's (c_n, T_v) differing; "
         "an instrument verdict inconsistent with 1d.2.2 (ADMIT with c + 1 > T(v)); no instrument verdict",
         UA.zg1([no_eval], on) and UA.zg1([bad_tuple], on) and any("1d.2.2" in x[3] for x in UA.zg1([bad_rule], on))
         and UA.zg1([dict(ok_a, admit=None)], on), (UA.zg1([no_eval], on), UA.zg1([bad_rule], on)))
    adm_edge = grow(10, U0, "a", True, True, "fix", c=19, T_v=20.0)
    adm_over = grow(10, U0, "a", True, True, "fix", c=20, T_v=20.0)
    case("Zg-1 boundary (1d.2.2: ADMIT iff c finite and c + 1 <= T(v)): c 19, T 20 admits consistently; c 20, T 20 "
         "with ADMIT true is flagged",
         not any("1d.2.2" in x[3] for x in UA.zg1([adm_edge], on)) and any("1d.2.2" in x[3]
                                                                           for x in UA.zg1([adm_over], on)),
         (UA.zg1([adm_edge], on), UA.zg1([adm_over], on)))
    v_a = grow(20, U0, "a", False, False, "today")
    case("Zg-2 holds at a veto whose step is today's (cell, raise, tier)", not UA.zg2([v_a], on), UA.zg2([v_a], on))
    case("Zg-2 fails: the veto's cell is not today's; the raise differs; the tier differs from today's _move_toward tier",
         UA.zg2([dict(v_a, post=(5, 6))], on) and UA.zg2([dict(v_a, **{"raise": True})], on)
         and UA.zg2([dict(v_a, tier=7)], on))
    v_b = grow(21, U0, "b", False, False, "today", pre_writes=[None, 0, False, None], pred_writes=[[5, 5], 1, False,
                                                                                                    [5, 5]],
               post_writes=[[5, 5], 1, False, [5, 5]], tier=10)
    case("Zg-2 (b): today's survival retreat writes no tier (a stale tier is not checked); the _idle_retreat_* writes "
         "equal the pure replica's -> holds; writes differing, or no replica -> FAIL; today's step not moving -> the "
         "unit's own cell",
         not UA.zg2([v_b], on) and UA.zg2([dict(v_b, post_writes=[[5, 5], 2, False, [5, 5]])], on)
         and UA.zg2([dict(v_b, pred_writes=None)], on)
         and not UA.zg2([dict(v_b, today=None, today_kind="fallback", post=(5, 5))], on)
         and UA.zg2([dict(v_b, today=None, today_kind="fallback", post=(5, 6))], on), UA.zg2([v_b], on))
    rows = [mvrow(0, 3, U0, branch="approach_a", dc=8), mvrow(1, 4, U0, branch="approach_a_veto", dc=8),
            mvrow(2, 5, U0, branch="approach_a", dc=8)]
    bad, n = UA.zm_a(rows)
    case("VETO-1 Zm-a skips veto rows: an admitted step, a veto, an admitted step on one board with D unchanged is no "
         "violation (a veto between two admitted steps breaks the chain; 1d.6.2)", not bad and n == 0, (bad, n))
    bad, n = UA.zm_a([mvrow(0, 3, U0, branch="approach_a", dc=8), mvrow(1, 4, U0, branch="approach_a", dc=8)])
    case("Zm-a still fails on two consecutive admitted steps with D 8 -> 8 on an unchanged board", len(bad) == 1
         and n == 1, bad)
    mv = [mvrow(0, 10, U0, acted="a", fa=(5, 6), pre=(5, 5), target=(9, 9), today=["greedy", (4, 5), 3, False],
                gA=True, acted_g="a")]
    gr = [grow(10, U0, "a", True, True, "fix", row=0)]
    ev = [{"step": 10, "kind": "a", "unit": U0, "row": 0, "live": True, "vetoed": False, "ran": True,
           "guard": {"admit": True, "c": 5, "T_v": 20.0, "model_admit": True}}]
    case("GB-1 the guard record's bookkeeping: a consistent row / d['mv'] row / event triple passes; an acted row without "
         "its guard row, an event whose vetoed flag contradicts the model's verdict, and n not a 4-neighbour of u are "
         "INSTRUMENT problems (INVALID)",
         not UA.guard_record_problems(gr, mv, ev) and UA.guard_record_problems([], mv, ev)
         and UA.guard_record_problems(gr, mv, [dict(ev[0], vetoed=True, ran=False)])
         and UA.guard_record_problems([dict(gr[0], n=(7, 7))], [dict(mv[0], fa=(7, 7))], ev),
         UA.guard_record_problems(gr, mv, ev))
    hx = ["a%d" % t for t in range(12)]
    vev = [{"step": 9, "kind": "a", "unit": U0, "live": True, "ran": False, "vetoed": True, "row": 0, "cell": [2, 1],
            "today": ["greedy", [1, 2], 1, False], "guard": {"admit": False}}]
    nev = [dict(vev[0], ran=True, vetoed=False)]
    rows = [mvrow(0, 9, U0, acted="a", fa=(2, 1))]
    hy = list(hx)
    hy[8] = "zz"                                                   # rows_ff index 8 = step 9
    res = UA.zg3(digest(hx, events=nev, rows=rows), digest(hy, events=vev, rows=rows))
    case("Zg-3 holds: N and G identical up to the first (a) veto at 9, the first difference at 9, N ran the fix's step "
         "there with the same instrument verdict and pre-advance shadow", not res["viol"] and res["s"] == 9, res["viol"])
    hy = list(hx)
    hy[5] = "zz"
    res = UA.zg3(digest(hx, events=nev, rows=rows), digest(hy, events=vev, rows=rows))
    case("Zg-3 fails: a difference before the first veto", any("before the first veto" in v for v in res["viol"]),
         res["viol"])
    hy = list(hx)
    hy[9] = "zz"
    res = UA.zg3(digest(hx, events=nev, rows=rows), digest(hy, events=vev, rows=rows))
    vb_f = [dict(vev[0], kind="b", today=["fallback", [1, 2], 3, False])]
    nb_f = [dict(vb_f[0], ran=True, vetoed=False)]
    res_bf = UA.zg3(digest(hx, events=nb_f, rows=rows), digest(hy, events=vb_f, rows=rows))
    vb_s = [dict(vev[0], kind="b", today=["survival", [1, 2], None, False])]
    nb_s = [dict(vb_s[0], ran=True, vetoed=False)]
    res_bs = UA.zg3(digest(hx, events=nb_s, rows=rows), digest(hy, events=vb_s, rows=rows))
    case("Zg-3: an (a) veto at 9 whose first difference is at 10 fails (AT the veto); a (b) veto whose today's retreat "
         "does not move (fallback) may differ AT OR AFTER it; a (b) veto with today's retreat cell defined must differ "
         "AT it",
         any("first difference is at" in v for v in res["viol"]) and not res_bf["viol"]
         and any("first difference is at" in v for v in res_bs["viol"]), (res["viol"], res_bf["viol"], res_bs["viol"]))
    hy = list(hx)
    hy[8] = "zz"
    res_n = UA.zg3(digest(hx, events=[dict(nev[0], guard={"admit": True})], rows=rows),
                   digest(hy, events=vev, rows=rows))
    res_m = UA.zg3(digest(hx, events=[], rows=rows), digest(hy, events=vev, rows=rows))
    res_i = UA.zg3(digest(hx), digest(hx[:3] + ["zz"] + hx[4:]))
    case("Zg-3 fails: N's instrument verdict differs from G's at the first veto; N has no ran step there; no veto in G "
         "but G differs from N. A cell with no veto and identical runs holds",
         any("instrument verdict" in v for v in res_n["viol"]) and any("N has no ran" in v for v in res_m["viol"])
         and any("no veto in G" in v for v in res_i["viol"]) and not UA.zg3(digest(hx), digest(hx))["viol"],
         (res_n["viol"], res_m["viol"], res_i["viol"]))


def z1m_cases():
    """Z1-M (1d.6.2: ACTED = a live fix step that RAN; a veto is today's step)."""
    hx = ["a%d" % t for t in range(12)]
    ev_y = [{"step": 9, "kind": "a", "unit": U0, "live": True, "ran": True, "row": 0, "cell": [2, 1],
             "today": ["greedy", [1, 2], 1, False]}]
    ev_x = [dict(ev_y[0], live=False, ran=False)]
    rows = [mvrow(0, 9, U0, acted="a", fa=(2, 1))]
    hy = list(hx)
    hy[5] = "zz"
    res = UA.z1_mov(digest(hx, events=ev_x, rows=rows), digest(hy, events=ev_y, rows=rows))
    case("Z1-M violation (ii): first difference at step 6, before s* = 9 (the first fix step that ran)",
         any("before s* = 9" in v for v in res["viol"]), res["viol"])
    hy = list(hx)
    hy[8] = "zz"
    res = UA.z1_mov(digest(hx, events=ev_x, rows=rows), digest(hy, events=ev_y, rows=rows))
    case("Z1-M holds: first difference at s* = 9, X's would-act (a) shadow matches, rows' shadow fields equal",
         not res["viol"] and res["s"] == 9, res["viol"])
    hy = list(hx)
    hy[9] = "zz"
    res = UA.z1_mov(digest(hx, events=ev_x, rows=rows), digest(hy, events=ev_y, rows=rows))
    case("Z1-M violation (iv): an (a) cell change at s* = 9 but the first difference is at 10",
         any("(a) cell change" in v for v in res["viol"]), res["viol"])
    res = UA.z1_mov(digest(hx, events=[], rows=rows), digest(hx[:8] + ["zz", "zz"], events=ev_y, rows=rows))
    case("Z1-M violation (iii): no matching would-act shadow in X", any("no matching would-act" in v for v in res["viol"]),
         res["viol"])
    res = UA.z1_mov(digest(hx, events=ev_x, rows=rows), digest(hx, events=ev_x, rows=[dict(rows[0], gA=False)]))
    vet = [dict(ev_y[0], ran=False, vetoed=True)]
    res_v = UA.z1_mov(digest(hx, events=ev_x, rows=rows), digest(hx, events=vet, rows=rows))
    res_vd = UA.z1_mov(digest(hx, events=ev_x, rows=rows), digest(hx[:3] + ["zz"] + hx[4:], events=vet, rows=rows))
    case("Z1-M (i) in G: a VETOED decision is today's step - a cell whose only fix decisions were vetoed is identical "
         "end to end (holds), and differing runs there fail (i)",
         not res_v["viol"] and res_v["s"] is None and any("no fix step ran" in v for v in res_vd["viol"]),
         (res_v, res_vd["viol"]))
    rows_g = [dict(rows[0], gA=False)]
    hy = list(hx)
    hy[8] = "zz"
    res = UA.z1_mov(digest(hx, events=ev_x, rows=rows), digest(hy, events=ev_y, rows=rows_g))
    case("Z1-M (iii) compares the instrument's guard verdicts too (gA differs across arms at s* -> violation)",
         any("shadow fields differ" in v and "gA" in v for v in res["viol"]), res["viol"])


def decision_cases():
    case("R-1 FULL order (verbatim): S1 fails -> STOP; S2 / S4 / S5 -> FAIL; S3 -> NOT SHOWN; S6 -> NOT READY; PASS",
         UA.full_verdict(False, True, True, True, True, True) == "STOP"
         and UA.full_verdict(True, False, False, True, True, False) == "FAIL"
         and UA.full_verdict(True, True, True, True, False, True) == "FAIL"
         and UA.full_verdict(True, True, False, True, True, False) == "NOT SHOWN"
         and UA.full_verdict(True, True, True, True, True, False) == "NOT READY"
         and UA.full_verdict(True, True, True, True, True, True) == "PASS")
    outs = [UA.decide(True, False, "PASS"), UA.decide(False, True, "PASS"), UA.decide(False, False, "STOP"),
            UA.decide(False, False, "FAIL"), UA.decide(False, False, "NOT SHOWN"), UA.decide(False, False, "NOT READY"),
            UA.decide(False, False, "PASS")]
    case("R-3 1d.6.3's outcomes in order: an arm-0 failure -> 1 (even with a PASS); S1 -> 2; FAIL -> 3; NOT SHOWN -> 4; "
         "NOT READY -> 5; PASS -> 6", outs == [1, 2, 2, 3, 4, 5, 6], outs)
    for o in range(1, 7):
        case("R-4.%d outcome %d has its pre-registered text" % (o, o), bool(UA.OUTCOME_TEXT.get(o)))
    both = {"a": {"set5": 2, "set6": 1}, "b": {"set5": 1, "set6": 0}}
    sv = UA.movement_switch_verdicts(6, {"a": True, "b": True}, both)
    case("R-5 per switch under PASS: (a) acted (ran) in both sets, Zm-a holds -> ON recommended; (b) did not act in set "
         "6 -> NOT MEASURED, ships 0 and its code is NOT merged",
         sv["a"].startswith("ON") and sv["b"].startswith("NOT MEASURED") and "NOT merged" in sv["b"], sv)
    sv = UA.movement_switch_verdicts(6, {"a": False, "b": True}, {k: {"set5": 1, "set6": 1} for k in "ab"})
    sv3 = UA.movement_switch_verdicts(3, {"a": True, "b": True}, {k: {"set5": 1, "set6": 1} for k in "ab"})
    case("R-6 a measured switch whose Zm fails ships 0; under FAIL (outcome 3) every measured switch ships 0",
         "Zm-a fails" in sv["a"] and sv["b"].startswith("ON") and all("FAIL" in v for v in sv3.values()), (sv, sv3))
    zf = [("Zg-1", "G", "w", {"GUARD"}, "x"), ("Zm-b", "N", "w", {"MOV"}, "x"), ("Z6", "G", "w", {"MOV", "GUARD"}, "x"),
          ("Z5", "N", "w", {"MOV"}, "x"), ("Zg-1", "N", "w", "REPORTED", "x")]
    got = {k: [f[0] + f[1] for f in UA.s2_for(zf, UA.ADDED[k])] for k in UA.COMPARISONS}
    case("R-9 the zero-to-comparison map (1d.6.2): a movement-owned zero or Z5 / Z6 in G OR N, or a guard zero in G, "
         "fails S2 of FULL(0 -> G); FULL(0 -> N) is failed by movement-owned ones; HARMLESS(N -> G) by the guard's and "
         "G's Z6; a REPORTED item fails nothing",
         got == {("0", "G"): ["Zg-1G", "Zm-bN", "Z6G", "Z5N"], ("0", "N"): ["Zm-bN", "Z6G", "Z5N"],
                 ("N", "G"): ["Zg-1G", "Z6G"]}, got)
    case("R-10 owners: arm-0 Z5 / Z-RB / Z6 / SM -> STOP; Zg-* in G -> GUARD, elsewhere REPORTED; movement zeros in G and "
         "N -> MOV; Z6 in G -> MOV + GUARD, in N -> MOV; SM outside arm 0 -> REPORTED; Z2-M in arm 0 -> REPORTED",
         UA.zero_owners("Z5", "0") == "STOP" and UA.zero_owners("Z-RB", "0") == "STOP" and UA.zero_owners("Z6", "0")
         == "STOP" and UA.zero_owners("SM", "0") == "STOP" and UA.zero_owners("Zg-3", "G") == {"GUARD"}
         and UA.zero_owners("Zg-1", "N") == "REPORTED" and UA.zero_owners("Zm-a", "N") == {"MOV"}
         and UA.zero_owners("Z-S", "G") == {"MOV"} and UA.zero_owners("Z6", "G") == {"MOV", "GUARD"}
         and UA.zero_owners("Z6", "N") == {"MOV"} and UA.zero_owners("SM", "N") == "REPORTED"
         and UA.zero_owners("Z2-M", "0") == "REPORTED")
    rec = srec()
    w3 = {"complete": True, "l4": {"G": UA.l4_counts([{"set": "set5", "kind": "A", "resolved": True, "own": True,
                                                       "others": False}]),
                                   "N": UA.l4_counts([])}}
    with contextlib.redirect_stdout(io.StringIO()):
        cg = UA.comparison([rec], "0", "G", [], True, w3)
        cg_inc = UA.comparison([rec], "0", "G", [], True, None)
        cn = UA.comparison([rec], "N", "G", [], True, w3)
    case("L4-C the comparison FULL(0 -> G) carries L4 as a literal clause of S5 (CAUSED 1 > PREVENTED 0 -> FAIL); with "
         "W3 incomplete S5 and the verdict are INCOMPLETE; HARMLESS(N -> G) has no L4",
         UA.L4_KEY in cg["lit_fail"] and cg["full"] == "FAIL" and cg_inc["L4_incomplete"]
         and cg_inc["full"].startswith("INCOMPLETE") and UA.L4_KEY not in cn["literal"],
         (cg["lit_fail"], cg_inc["full"], list(cn["literal"])))
    case("S6 FULL(0 -> G) checks the fixes' calls and the guard's calls separately (p99 <= 50 ms each, median R <= 2 %)",
         set(cg["S6_detail"]) == {"FIX", "GUARD"} and set(cn["S6_detail"]) == {"GUARD"}
         and cg["S6_detail"]["GUARD"]["n_calls"] == 1, cg["S6_detail"])


def l4_cases():
    """1d.13.2 / 1d.13.4: the L4 counts' known answers and review 1.3's classes."""
    adv = {"set": "set5", "kind": "A", "resolved": True, "own": True, "others": False}
    post = {"set": "set5", "kind": "B", "resolved": True, "own": False, "others": True}
    unres_a = {"set": "set6", "kind": "A", "resolved": False, "own": None, "others": None}
    unres_b = {"set": "set6", "kind": "B", "resolved": False, "own": False, "others": False}
    down_a = {"set": "set5", "kind": "A", "resolved": True, "own": False, "others": False}
    r = UA.l4_counts([adv])
    case("L4-1 an ADVANCED (or new) death whose unit is alive at t in KO-OWN counts as CAUSED: 1 > 0 -> FAIL",
         r["caused"] == 1 and r["prevented"] == 0 and r["fail"], r)
    r = UA.l4_counts([post])
    case("L4-2 a POSTPONED arm-0 death whose unit is dead by t in KO-OWN counts as PREVENTED: 0 vs 1 -> holds",
         r["caused"] == 0 and r["prevented"] == 1 and not r["fail"], r)
    r = UA.l4_counts([unres_a, unres_b])
    case("L4-3 an UNRESOLVED (A) counts as CAUSED; an UNRESOLVED (B) never counts as PREVENTED (a hard clause never "
         "passes on missing evidence): 1 > 0 -> FAIL", r["caused"] == 1 and r["prevented"] == 0 and r["fail"], r)
    r = UA.l4_counts([adv, post])
    case("L4-4 a SWAP (one unit's death caused, another's prevented, in one cell) counts +1 / +1 -> a tie -> holds",
         r["caused"] == 1 and r["prevented"] == 1 and not r["fail"] and r["per_set"]["set5"] == [1, 1], r)
    r = UA.l4_counts([adv, dict(adv, set="set6"), post, dict(post, set="set6")])
    r2 = UA.l4_counts([adv, dict(adv, set="set6"), post])
    case("L4-5 a TIE passes (2 vs 2); 2 vs 1 fails; per set recorded both ways",
         not r["fail"] and r2["fail"] and r["per_set"] == {"set5": [1, 1], "set6": [1, 1]}, (r, r2))
    r = UA.l4_counts([down_a, dict(post, own=True, others=True)])
    case("L4-6 candidates no knockout reverses count neither way (downstream coupling, reported)",
         r["caused"] == 0 and r["prevented"] == 0 and not r["fail"], r)
    oth = dict(adv, own=False, others=True)
    case("L4-7 KO-OTHERS alone reverses an (A): CAUSED (the other units' fix steps are but-for)",
         UA.l4_counts([oth])["caused"] == 1)
    rl = UA.l4_run_level([dict(adv, never_other=True, own_dies=False), dict(adv, never_other=False, own_dies=False),
                          dict(post, never_other=True, own_dies=True), dict(unres_a, never_other=True)])
    case("L4-8 the RUN-LEVEL variant (reported): only units dying in one run and nowhere in the other count; an (A) "
         "reversed when U dies nowhere in a knockout, a (B) when it dies somewhere; an unresolved (A) counts",
         rl["caused"] == 2 and rl["prevented"] == 1, rl)
    ch_ok = {"i": True, "iii": True}
    case("L4-9 review 1.3's classes (reported): C-PROX, C-PROX single step, C-BUTFOR, C-DOWN via others, C-DOWN, "
         "UNRESOLVED",
         UA.review13_class(adv, ch_ok) == "C-PROX" and UA.review13_class(dict(adv, last=True), ch_ok)
         == "C-PROX single step" and UA.review13_class(adv, {"i": True, "iii": False}) == "C-BUTFOR"
         and UA.review13_class(oth, ch_ok) == "C-DOWN via others' fix steps"
         and UA.review13_class(down_a, {"i": False}) == "C-DOWN" and UA.review13_class(unres_a, ch_ok) == "UNRESOLVED")
    cmds = [cmd(10, "post", "assign", V0, U0)]
    rows_ff = [[ffrow(U0, 1, 1, victim=V0, assigned=1, status="route_blocked" if t >= 15 else "en_route")]
               for t in range(1, 31)]
    ffs = UA.ff_cells_by_step(rows_ff)
    mv = [mvrow(i, 11 + i, U0, branch="approach_a" if i < 2 else "approach") for i in range(8)]
    evs = [{"step": 12, "kind": "a", "unit": U0, "victim": V0, "live": True, "ran": True},
           {"step": 13, "kind": "a", "unit": U0, "victim": V0, "live": True, "ran": True},
           {"step": 14, "kind": "a", "unit": U0, "victim": V0, "live": True, "ran": False, "vetoed": True}]
    ch = UA.death_chain(U0, 20, cmds, mv, ffs, evs)
    ch_rb = UA.death_chain(U0, 20, cmds + [cmd(17, "post", "assign", V1, U0)], mv, ffs, evs)
    mv_pk = [dict(r, branch="pickup") if r["step"] == 14 else r for r in mv]
    ch_pk = UA.death_chain(U0, 20, cmds, mv_pk, ffs, evs)
    ch_dc = UA.death_chain(U0, 20, cmds, [dict(r, dc=None) if r["step"] == 14 else r for r in mv],
                           UA.ff_cells_by_step([[ffrow(U0, 1, 1, victim=V0, assigned=1)] for _ in range(30)]), evs)
    case("L4-10 review 1.3's chain: (i) the ran fix steps on the dying leg (12, 13; a veto is not one); (iii) the "
         "route_blocked onset at 15 closes the way; a re-bind to an OPEN route after it breaks (iii); a pickup first "
         "breaks it; an infinite clean distance (dc None) at 14 is a closure",
         ch["i"] and [s for s, _k in ch["own"]] == [12, 13] and ch["closure"] == 15 and ch["iii"]
         and not ch_rb["iii"] and ch_pk["closure"] is None and not ch_pk["iii"] and ch_dc["closure"] == 14
         and ch_dc["iii"], (ch, ch_rb, ch_pk, ch_dc))
    evs_ko = [[10, U0, "a", False, True], [12, U0, "a", True, False], [14, U1_, "b", True, False]]
    case("L4-11 ko_first: a/b knockouts change the first matched decision that RAN (a vetoed one is already today's "
         "step); a g knockout the first matched VETO; '!U' matches the other units",
         UA.ko_first(evs_ko, [{"unit": U0, "kinds": "ab", "from": 0, "to": 30}]) == [12, U0, "a"]
         and UA.ko_first(evs_ko, [{"unit": U0, "kinds": "g", "from": 0, "to": 30}]) == [10, U0, "g"]
         and UA.ko_first(evs_ko, [{"unit": "!" + U0, "kinds": "ab", "from": 0, "to": 30}]) == [14, U1_, "b"]
         and UA.ko_first(evs_ko, [{"unit": U0, "kinds": "ab", "from": 13, "to": 30}]) is None)
    x = {"rows_ff": [[1]], "rows_vic": [], "rows_uav": [], "rows_dec": [], "rows_trig": [], "dp": {"commands": [1]},
         "mv_events": [{"a": 1}], "eval": {"rescued": 1}}
    case("L4-12 R0 reproduction compares every per-step row, the commands, the movement events, eval and stdout",
         UA.r0_reproduces(x, dict(x), "s", "s") == [] and UA.r0_reproduces(x, dict(x, eval={"rescued": 2}), "s", "s")
         == ["eval"] and UA.r0_reproduces(x, dict(x, mv_events=[]), "s", "t") == ["mv_events", "stdout"]
         and UA.r0_reproduces(x, dict(x, dp={"commands": []}), None, None) == ["dp.commands", "stdout"])


def write_json(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh)


def w3_end_to_end():
    """W3 VALIDITY end to end on synthetic files in a temporary directory: the frozen rule's queue and candidates,
    the replay records validated as screen records, R0 reproduction, the L4 counts (a swap: 1 / 1, passes), then a
    non-reproducing R0 (its candidates UNRESOLVED: CAUSED 1, PREVENTED 0 -> FAIL), a knockout that did not apply its
    first decision (UNRESOLVED), a W2 record changed after the queue was generated (REFUSED), a missing replay
    (INCOMPLETE)."""
    tmp = tempfile.mkdtemp(prefix="mvg_w3_e2e_")
    saved = (UA.Q_W2, W3Q.Q_W3, W3Q.CANDS, Q.W3_DIR)
    try:
        UA.Q_W2 = os.path.join(tmp, "_mvg_q_w2.jsonl")
        W3Q.Q_W3 = os.path.join(tmp, "_mvg_q_w3.jsonl")
        W3Q.CANDS = os.path.join(tmp, "_mvg_w3_candidates.json")
        Q.W3_DIR = tmp
        w2 = []
        for a in (0, 1, 2):
            ln = Q.probe_line("mvg%dr5" % a, "A_N", "A", "north", "135961", Q.arm_sets(a, 0))
            out = os.path.join(tmp, os.path.basename(ln["out"]))
            ln["argv"][ln["argv"].index("--out") + 1] = out
            ln["out"] = out
            w2.append(ln)
        with open(UA.Q_W2, "wb") as fh:
            fh.write(Q.queue_bytes(w2))

        def rows_for(deaths):
            return [[ffrow("ff_unit_%d" % i, 1, 1, dead=int(deaths.get("ff_unit_%d" % i) is not None
                                                            and t >= deaths["ff_unit_%d" % i]))
                     for i in range(3)] for t in range(1, 361)]
        ev_g = [{"step": 10, "kind": "a", "unit": U0, "victim": V0, "live": True, "ran": True, "vetoed": False},
                {"step": 12, "kind": "a", "unit": U1_, "victim": V1, "live": True, "ran": True, "vetoed": False}]

        def record(line, deaths, events, ko_applied=None, eval_=None):
            sd = UA.sd_args(line["argv"])
            sets = UA.parse_sets(sd)
            sw = UA.expected_switches(sets)
            d = {"repo": UA.WT, "head": "x", "argv": sd, "steps": 360, "steps_done": 360, "terminal_step": None,
                 "crashed": None, "scenario": "A", "wind": "north", "seed": 135961, "extra_params": sets,
                 "fb3": {"crn": {"on": True, "crn_draws": 5}, "eff": {"victim_spawn_mode": 0}},
                 "dp": {"probe": "dp_probe v2", "commands": [], "releases": [], "errors": []},
                 "ud": {"probe": UA.MVG_PROBE, "errors": [], "shadow_mismatch": [], "cmd_ctx": [], "rel_ctx": [],
                        "switches": dict(sw, DISPATCH_URGENCY=False, FF_CARRY_REPLAN=False)},
                 "mvg": {"probe": UA.MVG_PROBE, "errors": [], "switches": dict(sw),
                         "guard": {"cols": list(UA.GUARD_COLS), "rows": []}, "replica": {}},
                 "mv": {"cols": list(UA.MV_COLS), "rows": []}, "mv_events": events, "rows_ff": rows_for(deaths),
                 "rows_vic": [], "rows_uav": [], "rows_dec": [], "rows_trig": [], "eval": eval_ or {"rescued": 1}}
            write_json(line["out"], d)
            with open(line["out"][:-5] + ".stdout.txt", "w", encoding="utf-8", newline="\n") as fh:
                fh.write("[Victim Detection] step=3 UAV-1 detected victim_0 at (1, 1)\n")
            with open(line["out"] + ".argv", "w", encoding="utf-8") as fh:
                fh.write(UA.POOL.signature(line))
            if "--boards" in line["argv"]:
                own = line["argv"][1:line["argv"].index("--")]
                rules = json.loads(own[own.index("--ko") + 1]) if "--ko" in own else []
                write_json(own[own.index("--boards") + 1], {"ko_rules": rules, "argv": line["argv"][1:],
                                                            "ko_applied": ko_applied or [], "boards": {}})
            return d
        deaths = {"0": {U0: 60, U2_: 30}, "G": {U0: 40}, "N": {U0: 60, U2_: 30}}
        raw = {}
        for ln, arm in zip(w2, ("0", "G", "N")):
            raw[arm] = record(ln, deaths[arm], ev_g if arm != "0" else [dict(e, live=False, ran=False)
                                                                        for e in ev_g])
        rec = {"cell": {"id": "set5/ring/A_N", "set": "set5", "fresh": True, "scen": "A", "wind": "north",
                        "seed": 135961, "key": "A_N"}, "prov": {}, "g": {}}
        for arm, ln in zip(("0", "G", "N"), w2):
            d = raw[arm]
            rec["g"][arm] = {"w3c": W3Q.compact(d), "w2_name": ln["name"], "ff_dead": W3Q.compact(d)["ff_dead"],
                             "death_chain": {}, "dead_unit_h": {u: ["h"] for u in W3Q.compact(d)["ff_dead"]}}
        recs = [rec]
        doc, lines = W3Q.build_plan(w2, {ln["name"]: rec["g"][a]["w3c"] for ln, a in zip(w2, ("0", "G", "N"))})
        shas = {ln["name"]: W3Q.sha256_file(ln["out"]) for ln in w2}
        with open(UA.Q_W2, "rb") as fh:
            w2sha = hashlib.sha256(fh.read()).hexdigest()
        with open(W3Q.Q_W3, "wb") as fh:
            fh.write(Q.queue_bytes(lines))
        with open(W3Q.CANDS, "wb") as fh:
            fh.write(W3Q.doc_bytes(W3Q.full_doc(doc, shas, w2sha)))
        names = [ln["name"] for ln in lines]
        byn = {ln["name"]: ln for ln in lines}
        e = doc["entries"][0]
        opts = types.SimpleNamespace(smoke=None, head=None, zeros_only=False, allow_incomplete=False)
        # the replays: R0 reproduces G's record; KO-OWN of ff_unit_0 keeps it alive at 40; KO-OTHERS of ff_unit_2 kills
        # it at 30 (its arm-0 death restored)
        record(byn["mvgrp_mvg1r5_A_N_R0"], deaths["G"], ev_g)
        record(byn["mvgrp_mvg1r5_A_N_f0_KOown"], {}, [], ko_applied=[[10, U0, "a", [1, 2]]])
        record(byn["mvgrp_mvg1r5_A_N_f0_KOothers"], {U0: 40}, [], ko_applied=[[12, U1_, "a", [1, 2]]])
        record(byn["mvgrp_mvg1r5_A_N_f2_KOothers"], {U2_: 30, U0: 40}, [], ko_applied=[[10, U0, "a", [1, 2]]])
        with contextlib.redirect_stdout(io.StringIO()):
            res = UA.w3_validity(recs, opts)
        items = {(it["kind"], it["unit"]): it for it in res["items"]["G"]}
        case("W3-E1 the frozen rule's lines for G: R0, KO-OWN / KO-LAST (its last ran step before 40: 10) / KO-OTHERS of "
             "the (A) unit (no KO-GUARD: it has no veto), KO-OTHERS of the (B) unit (KO-OWN empty - it never ran a fix "
             "step - so not run: R0's outcome); arm N equals arm 0 there (no line)",
             names == ["mvgrp_mvg1r5_A_N_R0", "mvgrp_mvg1r5_A_N_f0_KOown", "mvgrp_mvg1r5_A_N_f0_KOlast",
                       "mvgrp_mvg1r5_A_N_f0_KOothers", "mvgrp_mvg1r5_A_N_f2_KOothers"]
             and e["A"][0]["ko"]["KOguard"] is None and e["B"][0]["ko"]["KOown"] is None, (names, e))
        record(byn["mvgrp_mvg1r5_A_N_f0_KOlast"], {}, [], ko_applied=[[10, U0, "a", [1, 2]]])
        with contextlib.redirect_stdout(io.StringIO()):
            res = UA.w3_validity(recs, opts)
        items = {(it["kind"], it["unit"]): it for it in res["items"]["G"]}
        ia, ib = items.get(("A", U0)), items.get(("B", U2_))
        case("W3-E2 a complete W3: R0 reproduces; (A) ff_unit_0 alive at 40 in KO-OWN -> CAUSED; (B) ff_unit_2 dead by "
             "30 in KO-OTHERS -> PREVENTED (KO-OWN not run: R0's outcome, alive); L4(G) 1 vs 1, a tie -> holds",
             res["complete"] and res["r0"][("set5/ring/A_N", "G")] == [] and ia["resolved"] and ia["own"] is True
             and ib["resolved"] and ib["others"] is False and ib["own"] is True and not ib["own_run"]
             and res["l4"]["G"]["caused"] == 1 and res["l4"]["G"]["prevented"] == 1 and not res["l4"]["G"]["fail"],
             (res.get("state"), ia, ib, res.get("l4")))
        record(byn["mvgrp_mvg1r5_A_N_R0"], deaths["G"], ev_g, eval_={"rescued": 9})
        with contextlib.redirect_stdout(io.StringIO()):
            res = UA.w3_validity(recs, opts)
        case("W3-E3 R0 does not reproduce G's record (eval): the cell's candidates are UNRESOLVED - the (A) counts as "
             "CAUSED, the (B) not as PREVENTED: 1 > 0 -> FAIL",
             res["complete"] and res["r0"][("set5/ring/A_N", "G")] == ["eval"]
             and res["l4"]["G"]["caused"] == 1 and res["l4"]["G"]["prevented"] == 0 and res["l4"]["G"]["fail"],
             (res.get("l4"), res["r0"]))
        record(byn["mvgrp_mvg1r5_A_N_R0"], deaths["G"], ev_g)
        record(byn["mvgrp_mvg1r5_A_N_f2_KOothers"], {U2_: 30, U0: 40}, [], ko_applied=[])
        with contextlib.redirect_stdout(io.StringIO()):
            res = UA.w3_validity(recs, opts)
        ib = {(it["kind"], it["unit"]): it for it in res["items"]["G"]}[("B", U2_)]
        case("W3-E4 a knockout whose boards show it did not knock out X's first changed decision is conflicting "
             "evidence: the candidate is UNRESOLVED (a (B): not PREVENTED)",
             res["conflicts"] and not ib["resolved"] and res["l4"]["G"]["prevented"] == 0, (res["conflicts"], ib))
        os.remove(byn["mvgrp_mvg1r5_A_N_f0_KOlast"]["out"])
        with contextlib.redirect_stdout(io.StringIO()):
            res = UA.w3_validity(recs, opts)
        case("W3-E5 a missing replay leaves W3 INCOMPLETE (no L4 count, hence no verdict)",
             not res["complete"] and "l4" not in res and "INCOMPLETE" in res["state"], res["state"])
        d0 = json.load(open(w2[0]["out"], encoding="utf-8"))
        d0["eval"] = {"rescued": 2}
        write_json(w2[0]["out"], d0)
        with contextlib.redirect_stdout(io.StringIO()):
            res = UA.w3_validity(recs, opts)
        case("W3-E6 a W2 record changed after W3 was generated: REFUSED", res["refused"] and "W2 record" in res["state"],
             res["state"])
        d0["eval"] = raw["0"]["eval"]
        write_json(w2[0]["out"], d0)
        with open(W3Q.Q_W3, "ab") as fh:
            fh.write(b'{"name": "extra"}\n')
        with contextlib.redirect_stdout(io.StringIO()):
            res = UA.w3_validity(recs, opts)
        case("W3-E7 a W3 queue that is not the frozen rule's re-derivation (the W2 records restored): REFUSED",
             res["refused"] and "_mvg_q_w3.jsonl differs" in res["state"] and "W2 record" not in res["state"],
             res["state"])
    finally:
        UA.Q_W2, W3Q.Q_W3, W3Q.CANDS, Q.W3_DIR = saved
        shutil.rmtree(tmp, ignore_errors=True)


def validity_cases():
    """16.6 as this round: validity against a queue line, provenance at --head, the shadow-mismatch ruling."""
    tmp = tempfile.mkdtemp(prefix="mvg_selftest_")
    try:
        line = Q.probe_line("mvg1r5", "A_E", "A", "east", "135963", Q.arm_sets(1, 0))
        path = os.path.join(tmp, "_sd_mvg1r5_A_E.json")
        line["argv"][line["argv"].index("--out") + 1] = path
        line["out"] = path
        sd = UA.sd_args(line["argv"])
        with open(path + ".argv", "w", encoding="utf-8") as fh:
            fh.write(UA.POOL.signature(line))
        with open(path[:-5] + ".stdout.txt", "w", encoding="utf-8") as fh:
            fh.write("[Victim Detection] step=3 UAV-2502 detected victim_0 at (1, 1)\n")
        rc_, hd = UA.git("rev-parse", "HEAD")
        head_sha = hd.decode().strip()
        pick = lambda rel: sorted(UA.committed_shas(head_sha, rel) or ["missing"])[0]          # noqa: E731
        src = {rel: pick(rel) for rel in UA.MVG_SRC_REQUIRED}
        sw = {"FF_APPROACH_PATH": True, "FF_RETREAT_KEEP_APPROACH": True, "FF_FIX_STRANDING_GUARD": True}
        good = {"repo": UA.WT, "head": head_sha, "argv": sd, "steps": 360, "steps_done": 360, "terminal_step": None,
                "crashed": None, "scenario": "A", "wind": "east", "seed": 135963,
                "extra_params": {"GLOBAL_PLANNER_MODE": 0, "VICTIM_SPAWN_MODE": 0, "FF_APPROACH_PATH": 1,
                                 "FF_RETREAT_KEEP_APPROACH": 1, "BATCH_SIZE": 360},
                "fb3": {"crn": {"on": True, "crn_draws": 99}, "eff": {"victim_spawn_mode": 0}},
                "dp": {"probe": "dp_probe v2", "commands": [], "releases": [], "errors": [],
                       "src_sha": {"agents.py": pick("agents.py")}},
                "ud": {"probe": UA.MVG_PROBE, "errors": [], "shadow_mismatch": [], "cmd_ctx": [], "rel_ctx": [],
                       "src_sha": src, "switches": dict(sw, DISPATCH_URGENCY=False, FF_CARRY_REPLAN=False)},
                "mvg": {"probe": UA.MVG_PROBE, "errors": [], "src_sha": src, "u1_shadow_sha": pick(UA.U1_SHADOW_REL),
                        "switches": dict(sw), "guard": {"cols": list(UA.GUARD_COLS), "rows": []},
                        "replica": {"checked": 0, "mismatch": [], "fix_checked": 0, "fix_mismatch": [],
                                    "cell_checked": 0, "cell_mismatch": []}},
                "mv": {"cols": list(UA.MV_COLS), "rows": []}, "mv_events": []}
        cell = {"scen": "A", "wind": "east", "seed": 135963}
        o2 = types.SimpleNamespace(smoke=None, head=head_sha[:8])
        w0, c0, s0 = UA.prov_run(good, path, line, cell, o2)
        w1, _c, _s = UA.prov_run(dict(good, extra_params=dict(good["extra_params"], FF_FIX_STRANDING_GUARD=0)), path,
                                 line, cell, o2)
        w2, _c, _s = UA.prov_run(dict(good, head="0123456789"), path, line, cell, o2)
        w3, _c, s3_ = UA.prov_run(dict(good, seed=135964), path, line, cell, o2)
        w4, _c, _s = UA.prov_run(dict(good, mvg=dict(good["mvg"], switches=dict(sw, FF_FIX_STRANDING_GUARD=False))),
                                 path, line, cell, o2)
        w5, _c, _s = UA.prov_run(good, path, None, cell, o2)
        case("V-1 validity against the queue line: a valid mvg_probe v1 run passes; extra_params, head and an effective "
             "switch (the guard) differing make it INVALID; no queue line is INVALID; a seed differing from the frozen "
             "cell is a STOP",
             not w0 and c0 is None and s0 is None and any("extra_params" in w for w in w1) and any("head" in w
                                                                                                  for w in w2)
             and s3_ is not None and "SEED MISMATCH" in s3_ and any("effective switches" in w for w in w4)
             and any("no line" in w for w in w5), (w0, w1, w2, s3_, w4, w5))
        dry = {k: v for k, v in good.items() if k != "mvg"}
        dry = dict(dry, ud=dict(good["ud"], probe=UA.UD_PROBE_DRY), mv={"cols": list(UA.MV_COLS_DRY), "rows": []})
        w6, _c, _s = UA.prov_run(dry, path, line, cell, o2)
        w6s, _c, _s = UA.prov_run(dict(dry, extra_params=good["extra_params"]), path, None, None,
                                  types.SimpleNamespace(smoke="x", head=None))
        w7, _c, _s = UA.prov_run(dict(good, mv={"cols": list(UA.MV_COLS_DRY), "rows": []}), path, line, cell, o2)
        w8, _c, _s = UA.prov_run(dict(good, mvg=dict(good["mvg"], guard={"cols": ["x"], "rows": []})), path, line, cell,
                                 o2)
        w9, _c, _s = UA.prov_run(dict(good, mvg=dict(good["mvg"], replica=dict(good["mvg"]["replica"], mismatch=[
            [3, U0, "retreat", None, [1], [2]]]))), path, line, cell, o2)
        case("V-2 the instrument: a urgency ud_probe v2 record is INVALID for the screen but readable in --smoke (DRY); "
             "the d['mv'] columns without the guard's four, the guard table's columns, and the _survival_move replica "
             "disagreeing with the model are INVALID",
             any("ud.probe" in w for w in w6) and not w6s and any("d['mv']" in w for w in w7)
             and any("guard'] columns" in w for w in w8) and any("replica" in w for w in w9), (w6, w6s, w7, w8, w9))
        doct = dict(good, ud=dict(good["ud"], src_sha=dict(src, **{"agents.py": "0" * 64})))
        w10, _c, _s = UA.prov_run(doct, path, line, cell, o2)
        w11, _c, _s = UA.prov_run(dict(good, mvg=dict(good["mvg"], u1_shadow_sha="0" * 64)), path, line, cell, o2)
        rc_, blob = UA.git("show", "%s:common_fixed_variables.py" % head_sha)
        lfb = blob.replace(b"\r\n", b"\n")
        forms = {hashlib.sha256(lfb).hexdigest(), hashlib.sha256(lfb.replace(b"\n", b"\r\n")).hexdigest()}
        case("M-2 provenance: an agents.py sha that is not the file at --head is INVALID ('ran uncommitted source'); so "
             "is a U1 shadow copy that is not outputs/_mvg_u1_shadow.py at --head; the committed file's LF and CRLF forms "
             "are both accepted; a record naming no src_sha is INVALID",
             any("ran uncommitted source" in w and "agents.py" in w for w in w10)
             and any("U1 shadow" in w for w in w11) and forms <= (UA.committed_shas(head_sha,
                                                                                     "common_fixed_variables.py") or set())
             and not UA.src_check(good, head_sha)
             and any("not recorded" in w for w in UA.src_check(dict(good, dp=dict(good["dp"], src_sha={})), head_sha)),
             (w10, w11))
        beh = dict(good, ud=dict(good["ud"], shadow_mismatch=[[9, U0, "a", "shadow acted, model did not", "approach",
                                                                [2, 1], [1, 2]]]),
                   mv_events=[{"step": 11, "kind": "b", "unit": U0, "victim": V0, "live": True, "agree": False}])
        w12, c12, _s = UA.prov_run(beh, path, line, cell, o2)
        w13, _c, _s = UA.prov_run(dict(good, mvg=dict(good["mvg"], errors=["mvg_purity: x"])), path, line, cell, o2)
        case("SMR-1 a run whose ud.shadow_mismatch holds a movement row and whose mv_events hold a live disagreement is "
             "NOT INVALID (behaviour); mvg.errors (an instrument error) make it INVALID",
             not w12 and c12 is None and any("instrument errors mvg.errors" in w for w in w13), (w12, w13))
        d = dict(good, crashed={"type": "ValueError", "step": 17}, steps_done=17)
        _w, crash, _s = UA.prov_run(d, path, line, cell, o2)
        _w2, crash2, _s = UA.prov_run(dict(good, steps_done=200), path, line, cell, o2)
        d3 = dict(good, fb3={"crn": {"on": True, "crn_draws": 0}, "eff": {"victim_spawn_mode": 0}})
        why3, crash3, _s = UA.prov_run(d3, path, line, cell, o2)
        case("Z6 / INVALID: a crash and an early stop are crashes (GATE FAILURE in G / N), never INVALID; 0 CRN draws is "
             "INVALID", crash is not None and "crashed ValueError" in crash and "stopped at step 200" in str(crash2)
             and crash3 is None and any("crn_draws 0" in w for w in why3), (crash, crash2, why3))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def zero_cases():
    a = {"rows_ff": [[1]], "eval": {"rescued": 1}, "dp": {"commands": [], "timing": 1}}
    b = {"rows_ff": [[1]], "eval": {"rescued": 2}, "dp": {"commands": [], "timing": 2}}
    diff, _n, _o = UA.ident_diff(a, b, False)
    case("Z0 ident_diff (DPR's G-ID field set): an eval difference is found; a J-only field (timing) is not",
         diff == ["eval"], diff)
    case("Z0 M8 reproduction: dp0's (4,1) / (7,1) over 32 + 32 runs -> PASS; (4,1) / (6,2) -> FAIL; 31 runs -> "
         "INCOMPLETE",
         UA.m8_check({"set1": (4, 1, 32), "set2": (7, 1, 32)}) == "PASS"
         and UA.m8_check({"set1": (4, 1, 32), "set2": (6, 2, 32)}) == "FAIL"
         and UA.m8_check({"set1": (4, 1, 31), "set2": (7, 1, 32)}) == "INCOMPLETE")
    bad = UA.z2_mov([cmd(5, "advance", "assign", V0, U0)], [["adv:ff_unit_0", "fix:a"]],
                    [[5, "advance", V1, "", "r", "", []]], [["adv:ff_unit_1", "fix:g"]])
    ok = UA.z2_mov([cmd(5, "advance", "unassign", V0, U0, "replacement_after_blocked")], [["adv:ff_unit_0"]], [], [])
    case("Z2-M violation: a command from fix code and a release from the guard's code ('fix:g'); today's advance path "
         "is not", len(bad) == 2 and not ok, bad)
    b = [cmd(1, "post", "assign", V0, U0), cmd(3, "post", "assign", V0, U1_), cmd(5, "post", "assign", V0, U0)]
    rets = UA.gt_returns_amended(b, [[s, []] for s in range(1, 6)], {}, {})
    case("Z5 violation: A..X..A on a victim with no outside event on X", len(rets) == 1 and not rets[0]["outside"], rets)
    bad = UA.z_rb([mvrow(0, 3, U0, zrb=True, rb_call=0, mt=1)], False)
    bad2 = UA.z_rb([mvrow(0, 3, U0, zrb=True, acted="a", rb_call=1)], False)
    ok = UA.z_rb([mvrow(0, 3, U0, zrb=True, rb_call=1, mt=1), mvrow(1, 4, U0, branch="approach_a_veto", acted="a",
                                                                  zrb=False, rb_call=0)], False)
    case("Z-RB violations: no raise although today's predicate holds; an (a)-acted step with the predicate true; a "
         "vetoed (a) decision without a raise is fine", len(bad) == 1 and len(bad2) >= 1 and not ok, (bad, bad2))
    bad = UA.zm_b([mvrow(0, 3, U0, branch="retreat_b", post=(3, 3), fbB=[(2, 2)])])
    ok = UA.zm_b([mvrow(0, 3, U0, branch="retreat_b", post=(2, 2), fbB=[(2, 2), (1, 3)]),
                  mvrow(1, 4, U0, branch="retreat_b_veto", post=(3, 3), fbB=[(2, 2)])])
    case("Zm-b violation: a (b) step off B; a (b) VETO (today's retreat) is not a (b) step", len(bad) == 1 and not ok)
    bad, _h = UA.z_s([mvrow(0, 3, U0, branch="approach_a", cls_post="B")])
    ok, _h = UA.z_s([mvrow(0, 3, U0, branch="approach_a_veto", cls_post="A", gesc=None)])
    case("Z-S violation: an (a) step onto a burning cell; a veto row (today's step) is not a fix step",
         len(bad) >= 1 and not ok, bad)


def count_cases():
    leg = [mvrow(i, 10 + i, U0, pre=p, dr=d_) for i, (p, d_) in enumerate(
        [((1, 1), 5), ((1, 2), 4), ((1, 1), 5)] + [((2, 2 + k), 4 - (k % 2)) for k in range(10)])]
    ev = UA.leg_events(leg)
    case("C-1 leg kinds (approach): CYCLE and PROGRESS", ev["cycle"] and ev["prog"], ev)
    osc = [mvrow(i, 80 + i, U0, pre=[(3, 3), (3, 4)][i % 2], dr=5) for i in range(10)]
    case("C-3 OSCILLATION: a 10-frame window on 2 cells with >= 2 changes", UA.leg_events(osc)["osc"])
    binders = [[1, [[V0, [[U0, "route_blocked"]]]]], [2, [[V0, [[U0, "route_blocked"]]]]], [3, []],
               [4, [[V0, [[U0, "route_blocked"]], ], [V1, [[U1_, "route_blocked"]]]]]]
    case("C-4 F6 latch episodes (3 here)", len(UA.latch_episodes(binders)) == 3, UA.latch_episodes(binders))
    rows_ff = [[ffrow(U0, 1, 1, victim=V0, assigned=1)] for _ in range(40)]
    rows_vic = [[[V0, 1, 9, "candidate", "candidate", "", 0, 0, 0, 0]] for _ in range(40)]
    ffs = UA.ff_cells_by_step(rows_ff)
    cls, _f, m8d = UA.attribute(V0, 10, 30, {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 40}, [],
                                [], [], ffs, rows_ff, rows_vic, [], [], [], {}, [], [])
    case("C-5 attribution: M8 futile -> FUT first", cls == "FUT" and not m8d, cls)
    cls, _f, m8d = UA.attribute(V0, 10, 30, {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 5}, [], [],
                                [[15, 1, [[V0, [[U1_, 4, 0]]]]]], ffs, rows_ff, rows_vic,
                                [mvrow(0, 20, U0, today=["greedy", (1, 2), 1, False], dcx=None, df=None)], [], [], {},
                                [], [])
    case("C-7 attribution: M8-D from a waiting sample; no clean and no fire-free distance -> MOV-closure",
         m8d and cls == "MOV-closure", cls)
    grows = [grow(10, U0, "a", True, True, "fix"), grow(11, U0, "a", False, False, "today"),
             grow(12, U0, "a", True, True, "fix"), grow(20, U1_, "a", True, True, "fix")]
    alt = UA.guard_alternations(grows, [mvrow(i, 30 + i, U0, pre=[(1, 1), (1, 2), (1, 1)][i], post=[(1, 2), (1, 1),
                                                                                                    (1, 2)][i])
                                        for i in range(3)] + [mvrow(3, 10, U0)],
                                lambda r: r.get("model_admit") is False)
    case("G4 alternations: admit at 10, veto at 11, admit at 12 -> one admit->veto and one admit->veto->admit; a "
         "static-board revisit counts only when its run holds a fix decision",
         alt["admit_veto"] == 1 and alt["admit_veto_admit"] == 1 and alt["static_cycles"] == 0, alt)
    cmds = [cmd(5, "post", "assign", V0, U0), cmd(18, "advance", "unassign", V0, U0, "replacement_after_blocked"),
            cmd(19, "post", "assign", V1, U0)]
    legs = UA.bind_legs(cmds, [[], [], []], [], [])
    gl = UA.guard_legs([grow(10, U0, "a", False, False, "today"), grow(11, U0, "a", True, True, "fix"),
                        grow(25, U0, "a", True, True, "fix", victim=V1)], legs, [], cmds, {U0: 40}, {},
                       lambda r: r.get("model_admit") is False)
    case("6.G legs: a leg with a vetoed decision ending in a route_blocked unassign; the next leg admitted only, ended by "
         "the unit's death", sorted((x["vetoed"], x["outcome"], x["n"]) for x in gl)
         == [(False, "unit died", 1), (True, "route_blocked unassign", 2)], gl)
    pvm = UA.post_veto_material([mvrow(0, 13, U0, rb_set=1)], [cmd(14, "advance", "unassign", V0, U0,
                                                                   "replacement_after_blocked")], {U0: 16})
    case("POST-VETO counts within 6 steps of a veto at 10: the raise at 13, the stranding (o1 at 14, death 16) and the "
         "death; a veto at 20 sees none", UA.post_veto_counts(pvm, U0, 10) == {"raises": 1, "strandings": 1, "death": 1}
         and UA.post_veto_counts(pvm, U0, 20) == {"raises": 0, "strandings": 0, "death": 0})


def header_cases():
    ok_h, _l = UA.hash_checks()
    with open(os.path.join(HERE, "urgency_part1d.txt"), encoding="utf-8") as fh:
        text = fh.read()
    bad13, lines13 = UA.hash_checks(text.replace("FAIL iff CAUSED(G) > PREVENTED(G).", "FAIL iff CAUSED(G) >= "
                                                                                         "PREVENTED(G)."))
    bad6, lines6 = UA.hash_checks(text.replace("p = P( Binomial(n_plus + n_minus, 1/2) >= n_plus )",
                                               "p = P( Binomial(n_plus + n_minus, 1/2) > n_plus )"))
    free, _l = UA.hash_checks(text.replace("Found: no BLOCKER; 17 MAJOR", "Found: no BLOCKER; 18 MAJOR"))
    case("H-2 hash checks: the working urgency_part1d.txt passes; one edited character in 1d.13 or in 1d.3 is REFUSED; "
         "an edit outside the hashed sections (1d.11) is not",
         ok_h and not bad13 and not bad6 and free and any("1d.13" in ln and "DIFFERS" in ln for ln in lines13)
         and any("1d.2-1d.9" in ln and "DIFFERS" in ln for ln in lines6), [ln for ln in lines13 + lines6
                                                                          if "DIFFERS" in ln])
    vok, vl = UA.verbatim_check()
    case("H-3 the DPR functions are verbatim from dispatch:outputs/_dp_analyze.py at cc8d653c, and the ud functions "
         "this port keeps verbatim from urgency:outputs/_ud_analyze.py at 5dba5bcb", vok, vl)
    with contextlib.redirect_stdout(io.StringIO()):
        frozen = UA.load_seeds()
    case("H-4 seeds: 1d.4's rule recomputed for 6 sets x 16 cells (set 5 A_N = 135961, set 6 D_W = 287056); sets 1-4 == "
         "the urgency round's frozen file", frozen is not None and all(len(frozen[s]) == 16 for s in UA.EXPECTED_BASES)
         and ["A_N", "A", "north", "135961"] in frozen["set5"] and ["D_W", "D", "west", "287056"] in frozen["set6"])
    txt = "x\n1d.2 THE STRANDING GUARD\n  a\n\n1d.10 WHAT THIS MEANS\ny\n====\n1d.13 AMENDMENT C1\n b\n\n"
    case("H-1 hashed-section extraction (verbatim): up to the next named header; trailing blank / '=' lines dropped; "
         "1d.13 runs to the end of the document",
         UA.extract_section(txt, "1d.2 THE STRANDING GUARD", "1d.10 WHAT THIS MEANS") == "1d.2 THE STRANDING GUARD\n  a"
         and UA.extract_section(txt, "1d.13 AMENDMENT C1", None) == "1d.13 AMENDMENT C1\n b")
    cells = UA.screen_cells(frozen, types.SimpleNamespace(smoke=None))
    kinds = collections.Counter(c["kind"] for c in cells)
    case("H-5 the analysed cells: W1 64 (arm 0, sets 1-2), the screen 64 (arms 0 / G / N, sets 5-6, fresh), the port "
         "identity 8 (arm N, set 3 ring, PORT_KEYS = _mvg_queue's)",
         kinds == {"w1": 64, "screen": 64, "port": 8} and UA.PORT_KEYS == Q.PORT_KEYS
         and sum(1 for c in cells if c["fresh"]) == 64, dict(kinds))


def main() -> int:
    p = UA.sign_test_p(10, 0)
    case("S-1 sign test known answer: n+ 10, n- 0 -> p = 2^-10", abs(p - 2 ** -10) < 1e-15, p)
    case("S-2 sign test: n+ 3, n- 1 -> p = 5/16; n+ 0, n- 4 -> p = 1", abs(UA.sign_test_p(3, 1) - 5 / 16) < 1e-15
         and UA.sign_test_p(0, 4) == 1.0)
    case("S-3 n+ + n- = 0 -> p = 1", UA.sign_test_p(0, 0) == 1.0)
    pv = {k: 1.0 for k, _l in UA.SIGN_KEYS}
    pv["of_broad"] = 2 ** -10
    h = UA.holm(pv)
    case("S-4 Holm: p = 2^-10 alone in a family of 24 is rejected (<= 0.05/24)", h["of_broad"]["rejected"]
         and abs(h["of_broad"]["threshold"] - 0.05 / 24) < 1e-15 and sum(v["rejected"] for v in h.values()) == 1)
    pv = {k: 1.0 for k, _l in UA.SIGN_KEYS}
    pv["of_broad"], pv["latch_episodes"], pv["never_finish"] = 0.0005, 0.0022, 0.0022
    h = UA.holm(pv)
    case("S-5 Holm step-down: the second-smallest p fails its threshold, so the third is NOT rejected either",
         h["of_broad"]["rejected"] and not h["latch_episodes"]["rejected"] and not h["never_finish"]["rejected"])
    cells = ["set5/ring/%s_%s" % (s, w) for s in "ABC" for w in "NS"] + ["set6/ring/%s_%s" % (s, w) for s in "ABC"
                                                                        for w in "NS"]
    cset = {c: c.split("/")[0] for c in cells}
    base = {c: {"ff_deaths": 1, "rescued": 3, "DD": 1} for c in cells}
    nx = {c: dict(base[c]) for c in cells}
    ny = {c: dict(base[c]) for c in cells}
    r = UA.compare_counts(nx, ny, cset, set())
    case("S-6 no diverged cell: every count has n+ + n- = 0, p = 1, nothing rejected; literal clauses hold; S5 PASS",
         r["S5"] and r["S4"] and all(v["p"] == 1.0 and not v["rejected"] for v in r["sign"].values())
         and r["diverged"] == 0)
    for c in cells[:10]:
        ny[c]["of_broad"] = 1
    r = UA.compare_counts(nx, ny, cset, set(cells))
    case("S-7 compare_counts: of_broad rises in 10 diverged cells (n+ 10, n- 0) -> p = 2^-10, rejected, S5 FAIL; "
         "literal clauses hold", r["sign"]["of_broad"]["rejected"] and r["sign"]["of_broad"]["n_plus"] == 10
         and not r["S5"] and r["S4"] and not r["lit_fail"] and r["sig_fail"] == ["of_broad"], r["sig_fail"])
    ny = {c: dict(base[c]) for c in cells}
    for c in cells[:10]:
        ny[c]["latch_episodes"] = 2
    ny["set6/ring/A_S"]["ff_deaths"] = 2
    ny["set5/ring/A_S"]["DD"] = 0
    ny["set5/ring/B_N"]["of_stuck_approach"] = 1
    r = UA.compare_counts(nx, ny, cset, set(cells))
    case("S-8 MIXED: a literal rise (ff deaths pooled) AND a sign-tested rejection (latch episodes, n+ 10); a single "
         "rising cell is not rejected; S5 FAIL, S4 PASS",
         r["lit_fail"] == ["F1 ff deaths pooled"] and r["sig_fail"] == ["latch_episodes"]
         and not r["sign"]["of_stuck_approach"]["rejected"] and r["sign"]["of_stuck_approach"]["p"] == 0.5
         and not r["S5"] and r["S4"], (r["lit_fail"], r["sig_fail"]))
    ny = {c: dict(base[c]) for c in cells}
    ny["set5/ring/A_N"]["rescued"] = 2
    r = UA.compare_counts(nx, ny, cset, {"set5/ring/A_N"})
    case("S-9 literal L2: rescued falls by one in set 5 -> L2 FAIL, S4 FAIL, S5 FAIL",
         r["lit_fail"] == ["L2 rescued set5"] and not r["S4"] and not r["S5"])
    dx = {c: 1 for c in cells}
    dy = dict(dx)
    dy[cells[0]] = 0
    dy[cells[1]] = 0
    s3 = UA.s3_rule(dx, dy, cset)
    case("S-10 S3: two set-5 cells -1 each, set 6 0 -> pooled -2, sets <= 0, without the most favourable cell -1 -> "
         "PASS", s3["pass"] and s3["pooled"] == -2 and s3["loo"] == -1, s3)
    dy = dict(dx)
    dy[cells[0]] = -1
    s3 = UA.s3_rule(dx, dy, cset)
    case("S-11 S3: a single cell carries the whole fall -> FAIL (no one-cell result counts)", not s3["pass"]
         and s3["loo"] == 0, s3)
    dy = dict(dx)
    dy[cells[0]], dy[cells[1]], dy[cells[7]] = 0, 0, 2
    s3 = UA.s3_rule(dx, dy, cset)
    case("S-12 S3: pooled -1 but set 6 rises -> FAIL", not s3["pass"] and s3["per_set"]["set6"] == 1, s3)
    s6 = UA.s6_rule([0.001, 0.03, 0.002], [1.0] * 99 + [60.0])
    case("S-13 S6: median R 0.2 %, p99 60 ms -> FAIL; vacuous (no call) -> PASS",
         not s6["pass"] and UA.s6_rule([0.0], [])["pass"], s6)
    r2_cases()
    decision_cases()
    zero_cases()
    z1m_cases()
    guard_cases()
    routing_cases()
    l4_cases()
    count_cases()
    validity_cases()
    w3_end_to_end()
    reported_cases()
    smoke_case()
    review_cases()
    header_cases()
    LINES.append("")
    LINES.append("SELF-TEST %s (%d cases, %d failed)" % ("PASS" if not FAILS else "FAIL", sum(
        1 for ln in LINES if ln.startswith(("PASS", "FAIL"))), len(FAILS)))
    text = "\n".join(LINES)
    print(text)
    if "--out" in _argv:
        with open(_argv[_argv.index("--out") + 1], "w", encoding="utf-8", newline="\n") as fh:
            fh.write("mvg round - synthetic-record self-test of outputs/_mvg_analyze.py\n\n" + text + "\n")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
