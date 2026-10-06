"""Urgency round: SYNTHETIC-RECORD SELF-TEST of outputs/_ud_analyze.py (16.6: it must pass before any real run is
read; 23.3: the sign test, Holm, the empty case and a mixed literal / sign-test failure; 22.8.5: every rule outcome and
the NOT MEASURED path; 22.8.2: one violation per structural zero; section 6's REPORTED measures: M1 / M1c, MU3,
MU4 and 16.8's G-B / G-T(b) / M6 / M3, one known answer each; the R2 / R3 review fixes: divergence on the victim
each order would bind (ud_probe v2), Z7 literal vs Z7-ACC, Z8 / Z3 on attempts, the harness reading, source
provenance, --zeros-only and the INCOMPLETE stop, early crashes, masked failure lines, the notes list, Z-RB ownership,
and a known answer for every count R3 D-2 named; the coordinator's 16.6 ruling: shadow_mismatch routed to Z7 / Z1-M /
an arm-0 STOP, never INVALID, and a refused victim never classed U1).

Hand-built records only (no run, no model): each case states what the pre-registration requires; the script prints one
line per case and exits 1 if any fails.

    .venv/Scripts/python.exe outputs/_ud_analyze_selftest.py [--out PATH]
"""
from __future__ import annotations

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_argv = sys.argv
sys.argv = _argv[:1]
import _ud_analyze as UA  # noqa: E402
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
         "c1_post": None, "fix_ms": 0.0, "inst_ms": 0.0}
    r.update(kw)
    return r


def digest(h, cmds=None, kicks=None, events=None, rows=None, so=None, marks=None, ev=None):
    return {"h": {"rows_ff": list(h)}, "cmds": cmds or [], "eval": ev or {"rescued": 1}, "so": so or ["l0"],
            "so_marks": marks or [None] * len(so or ["l0"]), "kicks": kicks or [], "mv_events": events or [],
            "mv_rows": rows or []}


def kick(i, step, qualifies=True, u1=(V0, V1), index=(V0, V1), bound=((V0, U0),), divergent=False,
         div_shadow=False, ms_model=None, triage=None, F=((U0, (1, 1)),), rec=None, z4_ok=True):
    W = [[v, [i, i]] for v in index]
    return {"i": i, "step": step, "phase": "post", "site": "K1", "W": W, "F": [[f, list(c)] for f, c in F],
            "index": list(index), "qualifies": qualifies, "u1": list(u1) if u1 is not None else None,
            "rec": rec if rec is not None else {v: [100.0, 5, True] for v in index}, "d": {}, "nB": 3,
            "z4": None, "z4_ok": z4_ok, "div_shadow": div_shadow, "bound": [list(b) for b in bound],
            "divergent": divergent, "ms_model": ms_model, "triage": triage}


def reported_cases():
    """Known answers for the REPORTED measures of section 6 (6.R1-6.R4); none gates anything."""
    # ============================================================== 6.R1 M1 / M1c (DPR 14.7)
    def g_(det, resc):
        return {"victims": [V0, V1], "det": det, "resc": resc, "censor": 361}
    c1 = {"id": "set3/ring/A_N", "set": "set3", "plc": "ring", "scen": "A"}
    c2 = {"id": "set3/uniform/B_N", "set": "set3", "plc": "uniform", "scen": "B"}
    c3 = {"id": "set4/ring/A_N", "set": "set4", "plc": "ring", "scen": "A"}
    rows = [(c1, g_({V0: 10, V1: 20}, {V0: 50, V1: 80}), g_({V0: 10, V1: 20}, {V0: 40, V1: 100})),
            (c2, g_({V0: 5, V1: 7}, {V0: 25}), g_({V0: 5, V1: None}, {V0: 15})),
            (c3, g_({V0: 5, V1: None}, {}), g_({V0: 5, V1: None}, {V0: 50}))]
    res = UA.m1_compare(rows)
    cset = {c["id"]: c["set"] for c in (c1, c2, c3)}
    st = UA.m1_stat(res["m1"], cset, UA.FRESH)
    stc = UA.m1_stat(res["m1c"], cset, UA.FRESH)
    case("M1-1 M1: per-victim deltas -10 / +20 give m_c +5 in one cell, -10 in another; T(set3) = -2.5 (unweighted "
         "over cells), +5 after removing the most negative m_c; a cell without a rescued pair is listed and excluded; "
         "a victim detected in one arm only is listed",
         res["m1"] == {c1["id"]: 5.0, c2["id"]: -10.0} and st["T"]["set3"] == -2.5 and st["loo"]["set3"] == 5.0
         and st["n"]["set4"] == 0 and st["T"]["set4"] is None and st["T"]["pooled"] == -2.5
         and res["no_pair"] == [c3["id"]] and res["only_one"] == [(c2["id"], V1, 7, None)], (res["m1"], st))
    case("M1-2 M1c: a victim dead in X and rescued at 50 in Y gives (50 - 5) - (361 - 5) = -311; pooled T over 3 cells "
         "= -105.33, -2.5 after removing the most negative m_c",
         res["m1c"] == {c1["id"]: 5.0, c2["id"]: -10.0, c3["id"]: -311.0}
         and abs(stc["T"]["pooled"] - (5 - 10 - 311) / 3.0) < 1e-12 and stc["loo"]["pooled"] == -2.5, stc)
    w = UA.wilcoxon([1.0, 2.0, 3.0])
    case("M1-3 Wilcoxon on m_c (DPR verbatim): three positive values -> W+ 6, exact two-sided p = 2 x 1/8 = 0.25",
         w["w_plus"] == 6.0 and w["method"] == "exact" and abs(w["p"] - 0.25) < 1e-12, w)
    # ============================================================== 6.R2 MU3
    decs = [{"k": 0, "step": 10, "vid": V0, "T": 10.0, "P": True, "first_burn": 15, "pickup": 12, "death": None,
             "complete": 20},
            {"k": 0, "step": 10, "vid": V1, "T": 20.0, "P": False, "first_burn": None, "pickup": None, "death": 55,
             "complete": None},
            {"k": 0, "step": 10, "vid": V2, "T": 5.0, "P": True, "first_burn": 40, "pickup": 45, "death": None,
             "complete": None}]
    h = UA.mu3_concordance(decs, 60)
    case("MU3-1 Harrell C on a 3-victim run: (T, first burn - step) = (10, 5) (20, censored 50) (5, 30) -> comparable "
         "pairs 3, concordant 2 -> C = 2/3 (per kick and per run); death target: the one death (45 after the decision, "
         "T 20) is comparable only with the victim censored later (50, T 5) and is discordant -> (0, 0, 1)",
         h[("kick", "burn")] == (2, 0, 3) and h[("run", "burn")] == (2, 0, 3) and UA.cval(h[("kick", "burn")]) == 2 / 3
         and h[("kick", "death")] == (0, 0, 1) and h[("run", "death")] == (0, 0, 1), h)
    vc = UA.mu3_verdicts(decs)
    case("MU3-2 verdict vs outcome: P picked up at 12 before her cell burned at 15; D never picked up, died; P picked "
         "up at 45 after the burn at 40",
         vc == {("P", "picked before burn", "survived"): 1, ("D", "never picked", "died"): 1,
                ("P", "picked after burn", "survived"): 1}, dict(vc))
    burn, death, cens, noest = UA.mu3_bias(decs + [dict(decs[0], vid="victim_9", T=None)], 60)
    case("MU3-3 bias: T - (first burn - step) = 5, -30 (censored at the horizon 60), -25; vs death 20 - 45 = -25; "
         "an infinite T is counted as no estimate",
         burn == [5.0, -30.0, -25.0] and death == [-25.0] and cens == 1 and noest == 1, (burn, death, cens, noest))
    b1 = UA.seed_bootstrap({("set3", "A_N"): (2, 0, 3)})
    b2 = UA.seed_bootstrap({("set3", "A_N"): (1, 0, 1), ("set3", "B_N"): (0, 0, 1)})
    case("MU3-4 seed-level bootstrap: one cluster -> C 2/3 with a degenerate interval; two clusters C = 0.5 with the "
         "interval [0, 1] over 2000 draws; the fixed RNG seed reproduces it exactly; ring and uniform of one seed are "
         "ONE cluster",
         b1[:3] == (2 / 3, 2 / 3, 2 / 3) and b1[3] == 3 and b1[4] == 2000 and b2[:3] == (0.5, 0.0, 1.0)
         and UA.seed_bootstrap({("set3", "A_N"): (1, 0, 1), ("set3", "B_N"): (0, 0, 1)}) == b2
         and UA.seed_cluster({"set": "set3", "key": "A_N", "plc": "ring"})
         == UA.seed_cluster({"set": "set3", "key": "A_N", "plc": "uniform"}), (b1, b2))
    # ============================================================== 6.R3 MU4
    o1 = [cmd(10, "advance", "unassign", V0, U0, "replacement_after_blocked")]
    case("MU4-1 stranding: an o1 unassign at 10 and the unit's death at 25 (15 steps) is a stranding; at 26 (16 steps) "
         "it is not; a casualty unassign is never one",
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
    ctx = [["kick:K1", "u1pass"], ["kick:K1"], ["adv:ff_unit_0"]]
    kicks = [kick(0, 5, divergent=True, div_shadow=True, u1=(V0, V1), index=(V1, V0), bound=((V0, U0),))]
    mv = [mvrow(0, 6, U0, cls_post="C"), mvrow(1, 7, U0, cls_post="A"), mvrow(2, 8, U0, cls_post="B", rb_set=1),
          mvrow(3, 6, U1_, victim=V1, cls_post="S")]
    evs = [{"step": 7, "kind": "a", "unit": U0, "victim": V0, "live": False}]
    tab, strand, deaths = UA.mu4_exposure(rows_ff, cmds, ctx, kicks, mv, evs, {U0: 12})
    case("MU4-2 exposure split: the leg bound at a U1-divergent kick (with a fix ACTED in it) holds 3 unit-steps, 2 "
         "unclean (A, B), 1 raise, the route_blocked onset, the stranding (o1 at 9, death at 12) and the rb_unbound "
         "death; the other unit's leg (not at a divergent kick) holds 1 smoky unit-step",
         tab["legs"] == {"n": 2, "div": 1, "acted": 1} and tab["unit_steps"] == {"n": 4, "div": 3, "nodiv": 1,
                                                                                  "acted": 3, "notacted": 1}
         and tab["unclean"] == {"n": 3, "div": 2, "nodiv": 1, "acted": 2, "notacted": 1}
         and tab["unclean_B"]["n"] == 1 and tab["unclean_S"]["nodiv"] == 1 and tab["raises_mv"] == {
             "n": 1, "div": 1, "acted": 1} and tab["rb_onsets"]["div"] == 1 and tab["strandings"]["div"] == 1
         and tab["deaths_rb_unbound"] == {"n": 1, "div": 1, "acted": 1} and strand == [[9, U0, V0, 12, True, True]]
         and deaths == [[12, U0, "rb_unbound", None, True, True]] and tab["stranded_deaths"] == {
             "n": 1, "div": 1, "acted": 1}, (dict(tab), strand, deaths))
    tab2, strand2, _d = UA.mu4_exposure(rows_ff, cmds + [cmd(11, "advance", "unassign", V0, U0,
                                                             "replacement_after_blocked")], ctx + [["adv:ff_unit_0"]],
                                        kicks, mv, evs, {U0: 12})
    case("MU4-3 two o1 unassigns of one unit before its death are 2 strandings but 1 stranded death",
         tab2["strandings"]["n"] == 2 and tab2["stranded_deaths"]["n"] == 1 and len(strand2) == 2, dict(tab2))
    # ============================================================== 6.R4 16.8's dispatch-round items
    binders = [[1, [[V0, [[U0, "en_route"], [U1_, "route_blocked"]]]]], [2, [[V0, [[U0, "en_route"], [U1_, "en_route"]]]]],
               [3, [[V1, [[U0, "en_route"]]]]]]
    n, _l = UA.gb_counts(binders, [[2, "RescueInvariant: double binding"]])
    case("DP-1 G-B: (a) 2 victim-steps with two living binders, (b) 1 with two ACTIVE binders (a route_blocked binder is "
         "not active), (d) 1 captured invariant line",
         n["gb_a"] == 2 and n["gb_b"] == 1 and n["gb_d"] == 1, dict(n))
    b = [cmd(1, "post", "assign", V0, U0), cmd(3, "post", "assign", V0, U1_), cmd(5, "post", "assign", V0, U0)]
    rets = UA.gt_returns_amended(b, [[s, []] for s in range(1, 6)], {U1_: 4}, {})
    n, rows_gt = UA.gt_b_counts(rets)
    case("DP-2 G-T(b): one A..X..A return whose X died between (o3) is counted under its outside events",
         dict(n) == {"gt_b_o3": 1} and rows_gt == [[5, "post", V0, U0, U1_, "victim", ["o3"]]], (dict(n), rows_gt))
    closed = cmd(4, "post", "assign", V0, U0)
    closed[7] = False
    n, _l = UA.m6_counts([closed, cmd(6, "sweep", "mark_unreachable", V1, "", "geographically_isolated"),
                          cmd(7, "post", "mark_unreachable", V0, "", "replacement_after_casualty"),
                          cmd(8, "post", "mark_unreachable", V2, "", "no_available_firefighter")], [])
    case("DP-3 M6: an assign with the BFS verdict route_open False; a sweep write-off; a casualty write-off; another",
         n["assign_closed"] == 1 and n["m6_escape"] == 1 and n["casualty_writeoffs"] == 1 and n["other_writeoffs"] == 1
         and n["writeoffs_avoided"] == 0, dict(n))
    n, _l, chk = UA.rb_figures([[5, 2, [[V0, [[U0, 4, 0]]]]]], [[5, []]], [[5, 2, 0, [U0, U1_]]], [], False)
    case("DP-4 M3 (DPR rb_figures, live False): 2 free units while a needy victim waits unbound -> m3a 2; one unit with "
         "a finite d -> m3b 1; the tooling checks pass",
         n["m3a"] == 2 and n["m3a_allowed"] == 2 and n["m3b_allowed"] == 1 and n["gb_f_allowed_W"] == 1
         and not UA.rb_checks_fail(chk), dict(n))


def kick2(i, step, index, u1, acc, bound, qualifies=True, attempts=None, triage=None, F=((U0, (1, 1)),)):
    """A ud_probe v2 kick record: acc, index_wb / u1_wb (the first ACCEPTED victim of each order) and the flags defined
    on them, as the coordinator specified them (the head-based ones kept as *_head)."""
    K = kick(i, step, qualifies=qualifies, u1=u1, index=index, bound=bound, F=F, triage=triage,
             ms_model=1.0 if qualifies else None)
    first = lambda xs: next((v for v in xs if acc.get(v)), None)                    # noqa: E731
    K["acc"] = dict(acc)
    K["index_wb"], K["u1_wb"] = first(index), first(u1)
    K["div_shadow_head"] = bool(qualifies and u1[0] != index[0])
    K["divergent_head"] = bool(qualifies and bound and bound[0][0] != index[0])
    K["div_shadow"] = bool(qualifies and K["u1_wb"] != K["index_wb"])
    K["divergent"] = bool(qualifies and (bound[0][0] if bound else None) != K["index_wb"])
    if attempts is not None:
        K["attempts"] = [list(a) for a in attempts]
    return K


def review_cases():
    """R2 / R3 review fixes: a known answer per fix."""
    import collections
    import contextlib
    import io
    import re
    # ============================================================== B-1: divergence = the victim each order WOULD BIND
    hx = ["a%d" % t for t in range(12)]
    acc = {V0: False, V1: True, V2: True}
    kx = [kick2(0, 7, index=(V0, V1, V2), u1=(V1, V0, V2), acc=acc, bound=((V1, U0),))]
    ky = [kick2(0, 7, index=(V0, V1, V2), u1=(V1, V0, V2), acc=acc, bound=((V1, U0),))]
    res = UA.z1_u1(digest(hx, kicks=kx), digest(hx, kicks=ky))
    hy = list(hx)
    hy[9] = "zz"                                                   # a genuine divergence at step 10
    k2 = kick2(1, 10, index=(V0, V2), u1=(V2, V0), acc={V0: True, V2: True}, bound=((V2, U0),))
    k2x = kick2(1, 10, index=(V0, V2), u1=(V2, V0), acc={V0: True, V2: True}, bound=((V0, U0),))
    res2 = UA.z1_u1(digest(hx, kicks=kx + [k2x]), digest(hy, kicks=ky + [k2]))
    case("B-1 index [v0 refused, v1, v2], U1 order [v1, v0, v2]: both orders bind v1 -> NOT divergent (the head-based "
         "flag would say so), value-identical runs give no Z1 violation; a real divergence at 10 is found at 10",
         kx[0]["div_shadow_head"] and not kx[0]["div_shadow"] and not ky[0]["divergent"] and not res["viol"]
         and res["s"] is None and not res2["viol"] and res2["s"] == 10 and not UA.kick_flag_check(ky[0])
         and UA.idx_wb(ky[0]) == V1, (res["viol"], res2["viol"]))
    bad_flag = dict(ky[0], div_shadow=True)
    case("B-1b the reported v2 kick-flag consistency check flags a div_shadow that disagrees with acc",
         UA.kick_flag_check(bad_flag) == ["div_shadow"], UA.kick_flag_check(bad_flag))
    # ============================================================== B-2 / R3 D-24: Z7 literal gates, Z7-ACC reported
    tri = "[UrgencyTriage] step=4 unit=ff_unit_0 order=[victim_0(T=10.0,c=3,P) victim_1(T=50.0,c=3,P)] served=victim_1"
    ref_head = [kick2(0, 4, index=(V1, V0), u1=(V0, V1), acc={V0: False, V1: True}, bound=((V1, U0),), triage=tri)]
    tri0 = "[UrgencyTriage] step=4 unit=ff_unit_0 order=[victim_0(T=10.0,c=3,P) victim_1(T=50.0,c=3,P)] served=none"
    all_ref = [kick2(0, 4, index=(V0, V1), u1=(V0, V1), acc={V0: False, V1: False}, bound=(), triage=tri0)]
    wrong = [kick2(0, 4, index=(V1, V2), u1=(V0, V1, V2), acc={V0: False, V1: True, V2: True}, bound=((V2, U0),))]
    case("Z7-1 refused U1 head (U binds v1, the first ACCEPTED victim): literal Z7 fails, Z7-ACC holds; every victim "
         "refused (0 binds, served=none): literal fails, Z7-ACC holds; binding a later accepted victim fails both",
         len(UA.z7_kicks(ref_head)) == 1 and not UA.z7_acc_kicks(ref_head) and len(UA.z7_kicks(all_ref)) == 1
         and not UA.z7_acc_kicks(all_ref) and len(UA.z7_acc_kicks(wrong)) == 1 and len(UA.z7_kicks(wrong)) == 1,
         (UA.z7_kicks(ref_head), UA.z7_acc_kicks(wrong)))
    r_lit, r_acc = UA.z7_readings(ref_head), UA.z7_readings(ref_head, "acc")
    case("Z7-2 Z7_READING = 'literal' (the module constant) gates the literal reading and REPORTS Z7-ACC; 'acc' swaps "
         "them", UA.Z7_READING == "literal" and len(r_lit["gate"]) == 1 and not r_lit["reported"]
         and not r_acc["gate"] and len(r_acc["reported"]) == 1, (r_lit, r_acc))
    # ============================================================== Z8 / Z3 on the v2 records
    q_none = kick2(0, 4, index=(V1,), u1=(V1,), acc={V1: True}, bound=())
    nq_ok = kick2(1, 6, index=(V0, V1), u1=(V0, V1), acc={V0: False, V1: True}, bound=((V1, U0),),
                  qualifies=False, attempts=[[V0, False], [V1, True]], F=((U0, (1, 1)), (U1_, (2, 2))))
    nq_bad = dict(nq_ok, bound=[])
    case("Z8-1 counterfactual count from index_wb / attempts: every victim refused -> 0, bound 0 -> no violation; "
         "index_wb exists but nothing bound -> violation; a non-qualifying kick binding its accepted attempts -> none, "
         "binding fewer -> violation",
         not UA.z8_kicks(all_ref) and len(UA.z8_kicks([q_none])) == 1 and not UA.z8_kicks([nq_ok])
         and len(UA.z8_kicks([nq_bad])) == 1, (UA.z8_kicks([q_none]), UA.z8_kicks([nq_bad])))
    nq_order = dict(nq_ok, attempts=[[V1, True], [V0, False]])
    nq_pairs = dict(nq_ok, attempts=[[V0, True], [V1, False]])
    case("Z3-1 (R2 m-6) non-qualifying kick: attempts in index order whose accepted victims are the binds -> none; "
         "attempts out of index order -> violation; binds differing from the accepted attempts -> violation",
         not UA.z3_kicks([nq_ok]) and len(UA.z3_kicks([nq_order])) == 1 and len(UA.z3_kicks([nq_pairs])) == 1,
         (UA.z3_kicks([nq_order]), UA.z3_kicks([nq_pairs])))
    lem = UA.lemma2_offarm(all_ref + [q_none])
    case("Z8-2 off-arm Lemma 2 report uses the same counterfactual: all refused (0 = 0) is not listed, a 0 bind with an "
         "accepted victim is", lem == [[4, 0, 0, 1]], lem)
    # ============================================================== M-1: harness reading
    rows = ["r%d" % t for t in range(12)]
    rows2 = list(rows)
    rows2[9] = "zz"
    ax = [(5, U0, V1, "initial", True), (10, U0, V0, "initial", True)]
    ay = [(5, U0, V1, "initial", True), (10, U0, V2, "initial", True)]
    trs = ["[UrgencyTriage] step=5 unit=ff_unit_0 order=[victim_0(T=10.0,c=3,P) victim_1(T=50.0,c=3,P)] "
           "served=victim_1",
           "[UrgencyTriage] step=7 unit=ff_unit_0 order=[victim_0(T=10.0,c=3,P) victim_2(T=50.0,c=3,P)] served=none",
           "[UrgencyTriage] step=10 unit=ff_unit_0 order=[victim_2(T=9.0,c=3,P) victim_0(T=50.0,c=3,P)] "
           "served=victim_2"]
    gx = {"h": {"steps": rows}, "assigns": ax, "unassigns": [], "eval": {}, "so": ["a"], "so_marks": [None],
          "so_triage": []}
    gy = dict(gx, h={"steps": rows2}, assigns=ay, so_triage=trs)
    r1 = UA.z1_harness(gx, gy)
    rows3 = list(rows)
    rows3[7] = "zz"
    r2 = UA.z1_harness(gx, dict(gy, h={"steps": rows3}))
    case("M-1 harness case 1: a refused lowest-index victim served by both arms (step 5) and served=none (step 7) are "
         "not divergences; served=victim_2 where OFF bound victim_0 (step 10) is - first difference 10 holds; a "
         "difference at 8 violates", r1["s"] == 10 and not r1["viol"] and any("first difference at 8" in v
                                                                              for v in r2["viol"]),
         (r1, r2["viol"]))
    # ============================================================== m-1: an early crash is Z6, never INVALID
    opts = types.SimpleNamespace(smoke="x", head=None)
    d = {"crashed": {"type": "ValueError", "step": 0}, "steps": 360, "steps_done": 0, "terminal_step": None,
         "extra_params": {}, "dp": {"probe": "dp_probe v2"}, "ud": {"probe": UA.UD_PROBE, "switches": {}},
         "fb3": {"crn": {"on": True, "crn_draws": 0}}, "mv": {"cols": list(UA.MV_COLS) + ["dcb"], "rows": []}}
    why, crash, _s = UA.prov_run(d, os.path.join(HERE, "__no_such_run__.json"), None, None, opts)
    d_rc = dict(d, crashed=None, steps_done=360, dp={"probe": "dp_probe v2", "rc_chain": 1},
                fb3={"crn": {"on": True, "crn_draws": 9}})
    _w, crash_rc, _s = UA.prov_run(d_rc, os.path.join(HERE, "__no_such_run__.json"), None, None, opts)
    case("m-1 a U run that crashed before any CRN draw and wrote no stdout goes to Z6 (crash text), with no CRN-draw or "
         "stdout INVALID reason; a non-zero chain exit code is a crash too",
         crash is not None and not any("crn" in w.lower() or "stdout" in w for w in why)
         and crash_rc == "chain exit code 1", (why, crash, crash_rc))
    # ============================================================== m-2: no outcome VALUE in masked Z0 / zero lines
    rec = {"cell": {"id": "set1/ring/A_N", "set": "set1"}, "ident": (["eval"], "", [], ".eval.rescued: 3 != 2"),
           "ref_bad": None, "g": {}, "prov": {}, "crash": {}}
    n0 = len(UA._LINES)
    with contextlib.redirect_stdout(io.StringIO()):
        UA.sec_z0([rec], [], types.SimpleNamespace(smoke="x", zeros_only=False))
        UA.sec_z0([rec], [], types.SimpleNamespace(smoke=None, zeros_only=True))
    z0_lines = UA._LINES[n0:]
    zrec = {"cell": {"id": "set3/ring/A_N", "set": "set3"}, "pairs": {},
            "g": {"MU": {"usable": True, "lists": {}, "z7_other": [],
                         "Z": {"Zm-c": [[60, None, "2 victim_dead events for victim_0, who died in custody"]]}}}}
    with contextlib.redirect_stdout(io.StringIO()):
        UA.sec_zeros([zrec], [], {"gate": [], "stop": []}, types.SimpleNamespace(smoke=None, zeros_only=True))
    z_lines = UA._LINES[n0 + len(z0_lines):]
    del UA._LINES[n0:]
    inst = [ln.split("owner MOV:", 1)[1] for ln in z_lines if "owner MOV:" in ln]
    case("m-2 --smoke / --zeros-only: a Z0 difference prints its field path and 'differs', not '3 != 2'; the M8 "
         "reproduction prints no FC / futile count; a zero's failure instance prints with every number masked",
         not any("3 != 2" in ln for ln in z0_lines) and sum(".eval.rescued differs" in ln for ln in z0_lines) == 2
         and not any(re.search(r"FC \d|futile \d", ln) for ln in z0_lines) and inst
         and not any(re.search(r"\d", x) for x in inst), (z0_lines, inst))
    # ============================================================== M-3: --zeros-only and the INCOMPLETE stop
    def gsyn(dd, resc, ffd):
        num = collections.Counter({"DD": dd, "rescued": resc, "ff_deaths": ffd, "of_broad": 2})
        return {"usable": True, "num": num, "u1_ms": 5.0, "wall_s": 100.0, "u1_kick_ms": [1.0], "fix_ms": 50.0,
                "fix_calls": {"a": [0.5]}, "eval": {"rescued": resc, "firefighter_deaths": ffd, "dead": 0},
                "deaths": [], "ff_dead": {}, "decisions": [], "kicks": [], "lists": {}, "latched_end": [],
                "terminal": 300, "n_ff": 5, "horizon": 360, "mu4": {}, "rb_checks": {}, "rb_fail": False, "det": {},
                "resc": {}, "victims": [], "censor": 361, "acted_live": {"a": False, "b": False, "c": False},
                "m8": [], "Z": {}, "z7_other": []}
    cell = {"id": "set3/ring/A_N", "set": "set3", "k": 3, "fresh": True, "plc": "ring", "p": "r", "scen": "A",
            "key": "A_N", "arms": UA.ARMS}
    srec = {"cell": cell, "g": {"0": gsyn(2, 3, 1), "U": gsyn(1, 4, 0), "M": gsyn(3, 2, 2), "MU": gsyn(0, 5, 0)},
            "prov": {}, "crash": {}, "missing": [], "stop": [],
            "pairs": {xy: {"s": None, "ident": False, "D": 5, "viol": [], "what": ["eval"]} for xy in UA.COMPARISONS}}
    st_miss = {"missing": [("U", "set4/ring/B_N")], "invalid": [], "gate": [], "stop": [], "seed": []}
    st_ok = {"missing": [], "invalid": [], "gate": [], "stop": [], "seed": []}
    bad = re.compile(r"LITERAL|SIGN-TESTED|rescued|\bDD\b|\bF[1-8]\b|FULL|HARMLESS|\bM8\b|\bMU[1-4]\b|->\s+\d+")
    outs = {}
    for name, st, op in (("zeros-only", st_ok, types.SimpleNamespace(smoke=None, zeros_only=True,
                                                                       allow_incomplete=False)),
                         ("incomplete", st_miss, types.SimpleNamespace(smoke=None, zeros_only=False,
                                                                       allow_incomplete=False)),
                         ("control", st_miss, types.SimpleNamespace(smoke=None, zeros_only=False,
                                                                    allow_incomplete=True))):
        n0 = len(UA._LINES)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                UA.outcome_sections([srec], [], st, {"pass": True, "fail": False}, {"fails": [], "stop": []}, op)
        except Exception as exc:                     # noqa: BLE001 - the control may not render every section here
            UA._LINES.append("EXC %r" % (exc,))
        outs[name] = UA._LINES[n0:]
        del UA._LINES[n0:]
    case("M-3 --zeros-only prints only its line after section 3; a missing run without --allow-incomplete stops with "
         "the INCOMPLETE line - neither prints a LITERAL / F-count / rescued / DD / FULL line; with --allow-incomplete "
         "the same records DO print them (positive control)",
         outs["zeros-only"] == [UA.ZEROS_ONLY_LINE]
         and not any(bad.search(ln) for ln in outs["incomplete"]) and any("INCOMPLETE" in ln for ln in outs["incomplete"])
         and sum(1 for ln in outs["control"] if "LITERAL" in ln) >= 5,
         (outs["zeros-only"], outs["incomplete"][-1:], len(outs["control"])))
    # ============================================================== m-4: the notes list
    need = ("_ut_probe.py", "_fb3_probe.py", "_fx3_probe.py", "_mf2_probe.py", "_sd_probe.py", "_fm2_probe_harness.py",
            "_ffr_harness.py", "_bp_inst.py", "_ud_seeds.txt", "_ud_dpR_sha256.txt", "_ud_q_smoke.jsonl",
            "_ud_probe_check.py", "_ud_mutants.py", "_ud_mutants_u1.py", "_ud_mutants_mv.py")
    case("m-4 the Part 2 notes must list the probe chain, the seed and reference lists, the smoke queue and the check / "
         "mutation tooling", all("outputs/" + n in UA.NOTES_REQUIRED for n in need))
    # ============================================================== R3 D-2: the counts still lacking a known answer
    sd_out = {"I2_uav_livelock": [[10, 39, "uav_1", [], "victim_searcher", []], [50, 79, "uav_2", [], "fire_tracker",
                                                                                   []]],
              "I2_uav_stuck": [[5, 30, "uav_1", [1, 1], "victim_searcher", 0, []], [5, 30, "uav_2", [1, 1],
                                                                                    "fire_tracker", 0, []]],
              "I6_rtb_no_progress": [[25, 44, "uav_1", [1, 1], [0, 0], 9], [25, 44, "uav_2", [2, 2], [0, 0], 9]]}
    rows_uav = []
    for t in range(1, 51):
        rtb = t >= 4
        r1u = ["uav_1", 1, 1, "victim_searcher" if t <= 4 else "returning", 50.0, rtb, False, (0, 0), "x"]
        r2u = ["uav_2", 2, 2, "victim_searcher" if t < 4 else "fire_tracker", 50.0, rtb, False, (0, 0), "x"]
        rows_uav.append([r1u, r2u])
    n, l_ = UA.searcher_kinds(sd_out, rows_uav)
    case("D2-1 F4 searcher kinds: I2 LIVELOCK / STUCK counted for the victim_searcher role only; I6 RTB no-progress by "
         "the role at the FIRST step of the return leg (uav_1: victim_searcher at 4, 'returning' at 25 -> counted; "
         "uav_2: fire_tracker at the leg start -> not)",
         n["os_i2_livelock"] == 1 and n["uav_livelock_all"] == 2 and n["os_i2_stuck"] == 1 and n["uav_stuck_all"] == 2
         and n["os_rtb_noprog"] == 1 and n["rtb_noprog_all"] == 2 and l_["os_rtb_noprog"][0][-1] == "victim_searcher",
         dict(n))
    wcmds = [cmd(10, "sweep", "mark_unreachable", V0, "", "geographically_isolated"),
             cmd(10, "sweep", "mark_unreachable", V1, "", "no_firefighter_available"),
             cmd(10, "sweep", "mark_unreachable", V2, "", "geographically_isolated"),
             cmd(12, "post", "mark_unreachable", V0, "", "replacement_after_casualty")]
    n, _l = UA.writeoff_counts(wcmds, {V0: 5, V1: 12, V2: None})
    case("D2-2 F8 escape write-offs of DETECTED victims: three sweep write-offs, one of a victim detected before it "
         "(5 <= 10); detected after (12) or never: not F8; the post-phase one is a dispatch write-off",
         n["escape_writeoffs"] == 3 and n["escape_writeoffs_det"] == 1 and n["dispatch_writeoffs"] == 1, dict(n))
    rows_ff = []
    for t in range(1, 41):
        carry = 5 <= t <= 35
        rows_ff.append([ffrow(U0, 5, 5, status="exiting" if carry else "available", assigned=1 if carry else 0,
                              exiting=1 if carry else 0, victim=V0 if carry else None)])
    dsyn = {"rows_ff": rows_ff, "rows_uav": [[] for _ in range(40)], "params": {"NUM_VICTIMS": 1}, "rows_dec": [],
            "rows_vic": [[[V0, 5, 5, "confirmed", "confirmed", "", 0, 0, 0, 0]] for _ in range(40)]}
    base_sd, _i = UA.SD.analyze("t", dsyn, UA.STUCK, UA.WIN)
    eps, nx = UA.stuck_carry_excluded("t", dsyn, [mvrow(0, 15, U0, leg="carry", branch="c2s"),
                                                  mvrow(1, 16, U0, leg="carry", branch="c3")])
    eps0, n0x = UA.stuck_carry_excluded("t", dsyn, [mvrow(0, 15, U0, leg="carry", branch="c1")])
    case("D2-3 F5 I2 STUCK carry, designed-behaviour exclusion: a carrier 31 steps on one cell is 1 stuck episode; its "
         "C-2 stay and C-3 hold rows (steps 15, 16) break it into 10 + 19 steps -> 0; a C-1 row excludes nothing",
         len(base_sd.get("I2_ff_stuck_carry") or []) == 1 and eps == [] and nx == 2 and eps0 is None and n0x == 0,
         (len(base_sd.get("I2_ff_stuck_carry") or []), eps, nx))
    cells = [(5, 5), (5, 6), (5, 5)] + [(6, k) for k in range(9)]
    leg = [mvrow(i, 100 + i, U0, leg="carry", branch="c0", pre=cells[i], dr=6) for i in range(12)]
    ev = UA.leg_events(leg)
    ev_h = UA.leg_events([dict(r, branch="c3") if i == 5 else r for i, r in enumerate(leg)])
    case("D2-4 carry legs beyond C-2: a carry leg on C-0 / path rows with a recurring cell is a CYCLE and with the route "
         "distance flat for 10 steps a PROGRESS violation; a C-3 hold row splits the PROGRESS series (no 10-step "
         "window left) but CYCLE is not excluded",
         ev["cycle"] and ev["prog"] and ev_h["cycle"] and not ev_h["prog"], (ev, ev_h))
    rows_vic = [[[V0, 1, 9, "candidate", "candidate", "", 0, 0, 0, 0]] for _ in range(40)]
    m8e = {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 5}
    pos = {1: (1, 1), 2: (1, 2), 3: (1, 1), 4: (1, 2), 5: (1, 1)}
    rows_ff_a = [[ffrow(U0, *pos.get(t, (1, 1)), victim=V0, assigned=1)] for t in range(1, 41)]
    ffs_a = UA.ff_cells_by_step(rows_ff_a)
    cls_a, _f, _m = UA.attribute(V0, 10, 30, m8e, [], [], [], ffs_a, rows_ff_a, rows_vic, [mvrow(0, 4, U0)], [], [], {},
                                 [], [])
    rows_ff_s = [[ffrow(U0, 1, 1, victim=V0, assigned=1)] for _ in range(40)]
    ffs_s = UA.ff_cells_by_step(rows_ff_s)
    cls_a0, _f, _m = UA.attribute(V0, 10, 30, m8e, [], [], [], ffs_s, rows_ff_s, rows_vic, [mvrow(0, 4, U0)], [], [],
                                  {}, [], [])
    cls_b, _f, _m = UA.attribute(V0, 10, 30, m8e, [], [], [], ffs_s, rows_ff_s, rows_vic,
                                 [mvrow(0, 20, U0, trig=True, fbB=[(5, 5)], today=["survival", (1, 2), 1, False])],
                                 [], [], {}, [], [])
    cls_c, _f, _m = UA.attribute(V0, 10, 30, m8e, [], [], [], ffs_s, rows_ff_s, rows_vic, [], [], [[15, U0, V0]], {},
                                 [], [])
    cls_rp, _f, _m = UA.attribute(V0, 10, 30, m8e, [], [], [[19, 1, [[V0, [[U1_, 3, 0]]]]]], ffs_s, rows_ff_s,
                                  rows_vic, [], [], [], {}, [cmd(20, "post", "assign", V0, U0, d_route=8)], [["adv"]])
    case("D2-5 22.9 classes: an approach loop (3 revisits <= 4 moves apart) with a finite shadow clean distance -> "
         "MOV-a (no loop: not); a survival retreat off a non-empty on-route set B -> MOV-b; a carry drop -> MOV-c; "
         "another free unit with a strictly shorter route (3 < 8) at her last bind -> RP",
         cls_a == "MOV-a" and cls_a0 != "MOV-a" and cls_b == "MOV-b" and cls_c == "MOV-c" and cls_rp == "RP",
         (cls_a, cls_a0, cls_b, cls_c, cls_rp))


def ruling_cases():
    """The coordinator's ruling on 16.6: shadow_mismatch routing and the 22.9 U1 class on refused victims."""
    kick_row = [7, U0, "u1", "kick bind differs from the acc shadow", "kick:0", V1, V2]
    mov_row = [9, U0, "a", "shadow acted, model did not", "approach", [2, 1], [1, 2]]
    odd_row = [3, U0, "x", "something else"]
    smz = UA.shadow_mismatch_zeros([kick_row], [], False)
    Z = {"Z7": []}
    z7o = UA.merge_mismatch(Z, [], smz)
    fails = [("Z7", "U", "U set3/ring/A_N", UA.zero_owners("Z7", "U"), Z["Z7"][0])]
    case("SMR-2 a KICK bind mismatch in U is a Z7 instance under BOTH readings (the gating list and the reported one), "
         "U1-owned: it fails 0->U, 0->MU and M->MU (S2)",
         list(smz) == ["Z7"] and len(Z["Z7"]) == 1 and len(z7o) == 1 and UA.zero_owners("Z7", "U") == {"U1"}
         and all(UA.s2_for(fails, UA.ADDED[k]) for k in (("0", "U"), ("0", "MU"), ("M", "MU")))
         and not UA.s2_for(fails, UA.ADDED[("0", "M")]), (smz, z7o))
    ev_dis = [{"step": 11, "kind": "b", "unit": U0, "live": True, "agree": False, "branch": "retreat"},
              {"step": 9, "kind": "a", "unit": U0, "live": True, "agree": False, "branch": "approach"}]
    smm = UA.shadow_mismatch_zeros([mov_row], ev_dis, False)
    fm = [("Z1-M", "M", "M set3/ring/A_N", UA.zero_owners("Z1-M", "M"), smm["Z1-M"][0])]
    case("SMR-3 a MOVEMENT live-vs-shadow mismatch is a Z1-M item (v) instance, movement-owned (fails 0->M, 0->MU, "
         "U->MU); a live ACTED disagreement without a row is added once, one already in a row is not duplicated",
         list(smm) == ["Z1-M"] and len(smm["Z1-M"]) == 2 and UA.zero_owners("Z1-M", "M") == {"MOV"}
         and all(UA.s2_for(fm, UA.ADDED[k]) for k in (("0", "M"), ("0", "MU"), ("U", "MU")))
         and not UA.s2_for(fm, UA.ADDED[("0", "U")]), smm)
    sm0 = UA.shadow_mismatch_zeros([kick_row, mov_row], [], True)
    smo = UA.shadow_mismatch_zeros([odd_row], [], False)
    case("SMR-4 in arm 0 / E0 any shadow_mismatch row is 'SM' and a STOP (22.8.2 'ANY failure in ARM 0'); a row of "
         "unknown kind elsewhere is 'SM', reported",
         list(sm0) == ["SM"] and len(sm0["SM"]) == 2 and UA.zero_owners("SM", "0") == "STOP"
         and UA.zero_owners("SM", "E0") == "STOP" and list(smo) == ["SM"] and UA.zero_owners("SM", "U") == "REPORTED",
         (sm0, smo))
    rows_ff = [[ffrow(U0, 1, 1, victim=V0, assigned=1)] for _ in range(40)]
    rows_vic = [[[V0, 1, 9, "candidate", "candidate", "", 0, 0, 0, 0]] for _ in range(40)]
    ffs = UA.ff_cells_by_step(rows_ff)
    m8e = {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 5}
    dec = [{"k": 0, "step": 12, "vid": V0, "d": 6, "served": False, "accepted": False},
           {"k": 0, "step": 12, "vid": V1, "d": 3, "served": True, "accepted": True}]
    cls_r, fl_r, _m = UA.attribute(V0, 10, 30, m8e, dec, [], [], ffs, rows_ff, rows_vic, [], [], [], {}, [], [])
    cls_a, _f, _m = UA.attribute(V0, 10, 30, m8e, [dict(dec[0], accepted=True), dec[1]], [], [], ffs, rows_ff,
                                 rows_vic, [], [], [], {}, [], [])
    case("SMR-5 22.9 U1 class: a victim the planner REFUSED (accepted False) and passed over at a qualifying kick is "
         "never U1 (she could not be served under either order); the same record accepted is U1",
         cls_r != "U1" and not fl_r["U1"] and cls_a == "U1", (cls_r, cls_a))


def smoke_case():
    """22.6.3: --smoke prints no outcome. Synthetic digested records of one fresh-flagged cell (all four arms, every
    pair diverged, outcome counts that differ) go through the analyzer's sections 4-8 entry point in smoke mode; the
    same records through section 4 outside smoke mode are the positive control that the patterns do catch outcomes."""
    import collections
    import contextlib
    import io
    import re

    def gsyn(dd, resc, ffd):
        num = collections.Counter({"DD": dd, "rescued": resc, "ff_deaths": ffd, "of_broad": 2, "never_detected": 1})
        return {"usable": True, "num": num, "u1_ms": 5.0, "wall_s": 100.0, "u1_kick_ms": [1.0, 2.0], "fix_ms": 50.0,
                "fix_calls": {"a": [0.5, 1.5]}, "eval": {"rescued": resc}, "deaths": [], "ff_dead": {}}
    cell = {"id": "set3/ring/A_N", "set": "set3", "k": 3, "fresh": True, "plc": "ring", "p": "r", "scen": "A",
            "key": "A_N", "arms": UA.ARMS}
    rec = {"cell": cell, "g": {"0": gsyn(2, 3, 1), "U": gsyn(1, 4, 0), "M": gsyn(3, 2, 2), "MU": gsyn(0, 5, 0)},
           "prov": {}, "crash": {}, "missing": [], "stop": [],
           "pairs": {xy: {"s": None, "ident": False, "D": 5, "viol": [], "what": ["eval"]} for xy in UA.COMPARISONS}}
    zres = {"fails": [], "stop": []}
    st = {"missing": [], "invalid": [], "gate": [], "stop": [], "seed": []}
    n0 = len(UA._LINES)
    with contextlib.redirect_stdout(io.StringIO()):
        UA.outcome_sections([rec], [], st, {"pass": True, "fail": False}, zres,
                            types.SimpleNamespace(smoke="synthetic", allow_incomplete=False))
    smoke = UA._LINES[n0:]
    n1 = len(UA._LINES)
    with contextlib.redirect_stdout(io.StringIO()):
        UA.sec_comparisons([rec], zres, True)
    full = UA._LINES[n1:]
    del UA._LINES[n0:]
    bad = re.compile(r"LITERAL|SIGN-TESTED|rescued|\bDD\b|\bF[1-8]\b|\bS[2-5]\b|FULL|HARMLESS|VERDICT|\bM8\b|\bM1c?\b"
                     r"|\bMU[1-4]\b|death|never-detected|->\s+\d+\s+\|")
    leaks = [ln for ln in smoke if bad.search(ln)]
    case("SM-1 --smoke prints no outcome (22.6.3): only the S6 cost line per comparison (5) and the suppression line - "
         "no comparison / literal / sign-tested F-count / rescued / DD / FULL / decision line; the same records outside "
         "smoke DO print them (positive control)",
         not leaks and smoke[-1] == UA.SMOKE_SUPPRESSED and sum(1 for ln in smoke if ln.startswith("  S6 COST")) == 5
         and sum(1 for ln in full if bad.search(ln)) >= 20 and any("LITERAL" in ln for ln in full),
         leaks[:3] or smoke)


def main() -> int:
    # ============================================================== 23.2 statistics
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
    case("S-5 Holm step-down: the smallest p is rejected; the second-smallest (0.0022 > 0.05/23) fails its threshold, "
         "so the third (0.0022 <= 0.05/22) is NOT rejected either",
         h["of_broad"]["rejected"] and not h["latch_episodes"]["rejected"] and not h["never_finish"]["rejected"]
         and h["never_finish"]["p"] <= 0.05 / 22, {k: (v["rank"], round(v["threshold"], 6), v["rejected"]) for k, v in
                                                   h.items() if v["p"] < 1})
    cells = ["c%02d" % i for i in range(12)]
    cset = {c: ("set3" if i < 6 else "set4") for i, c in enumerate(cells)}
    base = {c: {"ff_deaths": 1, "rescued": 3, "DD": 1} for c in cells}
    nx = {c: dict(base[c]) for c in cells}
    ny = {c: dict(base[c]) for c in cells}
    r = UA.compare_counts(nx, ny, cset, set())
    case("S-6 no diverged cell: every count has n+ + n- = 0, p = 1, nothing rejected; literal clauses hold; S5 PASS",
         r["S5"] and r["S4"] and all(v["p"] == 1.0 and not v["rejected"] for v in r["sign"].values())
         and r["diverged"] == 0)
    for i, c in enumerate(cells[:10]):
        ny[c]["of_broad"] = 1
    r = UA.compare_counts(nx, ny, cset, set(cells))
    case("S-7 compare_counts: of_broad rises in 10 diverged cells (n+ 10, n- 0) -> p = 2^-10, rejected, S5 FAIL; "
         "literal clauses hold", r["sign"]["of_broad"]["rejected"] and r["sign"]["of_broad"]["n_plus"] == 10
         and abs(r["sign"]["of_broad"]["p"] - 2 ** -10) < 1e-15 and not r["S5"] and r["S4"] and not r["lit_fail"]
         and r["sig_fail"] == ["of_broad"], r["sig_fail"])
    ny = {c: dict(base[c]) for c in cells}
    for c in cells[:10]:
        ny[c]["latch_episodes"] = 2
    ny["c07"]["ff_deaths"] = 2                  # set4: L1 set4 and L1 pooled rise
    ny["c01"]["DD"] = 0                          # DD falls: L3 holds
    ny["c02"]["of_stuck_approach"] = 1           # one rising cell: p = 1/2 (with this cell's tie-less delta), never rejected
    r = UA.compare_counts(nx, ny, cset, set(cells))
    case("S-8 MIXED: a literal rise (ff deaths set 4 and pooled) AND a sign-tested rejection (latch episodes, n+ 10); "
         "a single rising cell is not rejected; S5 FAIL, S4 PASS",
         set(r["lit_fail"]) == {"L1 ff deaths pooled", "L1 ff deaths set4"} and r["sig_fail"] == ["latch_episodes"]
         and not r["sign"]["of_stuck_approach"]["rejected"] and r["sign"]["of_stuck_approach"]["p"] == 0.5
         and not r["S5"] and r["S4"], (r["lit_fail"], r["sig_fail"]))
    ny = {c: dict(base[c]) for c in cells}
    ny["c00"]["rescued"] = 2
    r = UA.compare_counts(nx, ny, cset, {"c00"})
    case("S-9 literal L2: rescued falls by one in set 3 -> L2 FAIL, S4 FAIL, S5 FAIL",
         r["lit_fail"] == ["L2 rescued set3"] and not r["S4"] and not r["S5"])
    dx = {c: 1 for c in cells}
    dy = dict(dx)
    dy["c00"] = 0
    dy["c01"] = 0
    s3 = UA.s3_rule(dx, dy, cset)
    case("S-10 S3: two set-3 cells -1 each, set 4 0 -> pooled -2, sets <= 0, without the most favourable cell -1 < 0 "
         "-> PASS", s3["pass"] and s3["pooled"] == -2 and s3["loo"] == -1, s3)
    dy = dict(dx)
    dy["c00"] = -1
    s3 = UA.s3_rule(dx, dy, cset)
    case("S-11 S3: a single cell carries the whole fall (-2) -> without it 0 -> FAIL (no one-cell result counts)",
         not s3["pass"] and s3["loo"] == 0, s3)
    dy = dict(dx)
    dy["c00"], dy["c01"], dy["c07"] = 0, 0, 2
    s3 = UA.s3_rule(dx, dy, cset)
    case("S-12 S3: pooled -1 but set 4 rises -> FAIL", not s3["pass"] and s3["per_set"]["set4"] == 1, s3)
    s6 = UA.s6_rule([0.001, 0.03, 0.002], [1.0] * 99 + [60.0])
    case("S-13 S6: median R 0.2 %, p99 (the _fb3_analyze rule) 60 ms -> FAIL; vacuous (no call) -> PASS",
         not s6["pass"] and UA.s6_rule([0.0], [])["pass"], s6)
    # ============================================================== FULL, HARMLESS, rules, per-switch
    case("R-1 FULL order: S1 fails -> STOP; S2 fails -> FAIL even with S3 and S6 failing; S3 -> NOT SHOWN even with S6 "
         "failing; S6 alone -> NOT READY; all -> PASS",
         UA.full_verdict(False, True, True, True, True, True) == "STOP"
         and UA.full_verdict(True, False, False, True, True, False) == "FAIL"
         and UA.full_verdict(True, True, True, False, True, True) == "FAIL"
         and UA.full_verdict(True, True, True, True, False, True) == "FAIL"
         and UA.full_verdict(True, True, False, True, True, False) == "NOT SHOWN"
         and UA.full_verdict(True, True, True, True, True, False) == "NOT READY"
         and UA.full_verdict(True, True, True, True, True, True) == "PASS")
    case("R-2 R-MU = FULL(0->MU) AND HARMLESS(M->MU) AND HARMLESS(U->MU): a failing HARMLESS turns a PASS into FAIL",
         UA.rmu_verdict("PASS", True, False) == "FAIL" and UA.rmu_verdict("PASS", True, True) == "PASS"
         and UA.rmu_verdict("NOT SHOWN", True, True) == "NOT SHOWN" and UA.rmu_verdict("FAIL", True, True) == "FAIL")
    outs = [UA.decide(True, "PASS", "PASS", "PASS"), UA.decide(False, "PASS", "PASS", "PASS"),
            UA.decide(False, "PASS", "PASS", "FAIL", 1, 2), UA.decide(False, "PASS", "PASS", "NOT SHOWN", 2, 2),
            UA.decide(False, "PASS", "FAIL", "PASS"), UA.decide(False, "NOT SHOWN", "PASS", "FAIL"),
            UA.decide(False, "FAIL", "NOT SHOWN", "PASS"), UA.decide(False, "NOT READY", "NOT READY", "NOT READY")]
    case("R-3 outcomes 1-6: arm-0 failure -> 1; all hold -> 2; R-M and R-U hold, R-MU fails -> 3 (default: larger DD "
         "reduction U; a tie -> M); R-M only -> 4; R-U only -> 5; neither (an MU-only pass, or NOT READY) -> 6",
         outs == [(1, None), (2, None), (3, "U"), (3, "M"), (4, None), (5, None), (6, None), (6, None)], outs)
    for o in range(1, 7):
        case("R-4.%d outcome %d has its pre-registered text" % (o, o), bool(UA.OUTCOME_TEXT.get(o)))
    acted = {"a": {"set3": 2, "set4": 0}, "b": {"set3": 1, "set4": 3}, "c": {"set3": 4, "set4": 1}}
    sv = UA.movement_switch_verdicts(4, None, "PASS", "FAIL", {"a": True, "b": True, "c": False}, acted)
    case("R-5 per movement switch under outcome 4: (a) acted in set 3 only -> NOT MEASURED (ships 0, may merge at 0); "
         "(b) acted in both, Zm-b holds -> ON recommended; (c) acted in both but Zm-c fails -> ships 0",
         sv["a"].startswith("NOT MEASURED") and sv["b"].startswith("ON") and "Zm-c fails" in sv["c"], sv)
    sv = UA.movement_switch_verdicts(6, None, "NOT SHOWN", "NOT SHOWN", {"a": True, "b": True, "c": True},
                                     {k: {"set3": 0, "set4": 0} for k in "abc"})
    case("R-6 NOT MEASURED wins over the R-M verdict when a fix never acted", all(v.startswith("NOT MEASURED")
                                                                                   for v in sv.values()), sv)
    sv = UA.movement_switch_verdicts(5, None, "FAIL", "FAIL", {"a": True, "b": True, "c": True},
                                     {k: {"set3": 1, "set4": 1} for k in "abc"})
    case("R-7 a measured switch with R-M FAIL ships 0 (R-M FAIL)", all("R-M FAIL" in v for v in sv.values()), sv)
    sv = UA.movement_switch_verdicts(3, "U", "PASS", "FAIL", {"a": True, "b": True, "c": True},
                                     {k: {"set3": 1, "set4": 1} for k in "abc"})
    case("R-8 outcome 3 with the default U: movement switches ship 0 pending the ruling",
         all("outcome-3 default" in v for v in sv.values()), sv)
    zf = [("Z7", "U", "w", {"U1"}, "x"), ("Zm-b", "MU", "w", {"MOV"}, "x"), ("Z5", "M", "w", {"MOV"}, "x"),
          ("Z4", "0", "w", "REPORTED", "x")]
    got = {k: [f[0] for f in UA.s2_for(zf, UA.ADDED[k])] for k in UA.COMPARISONS}
    case("R-9 the zero-to-comparison map: a U1-owned failure fails 0->U, 0->MU, M->MU; a movement-owned one fails 0->M, "
         "0->MU, U->MU; a REPORTED item fails nothing",
         got == {("0", "M"): ["Zm-b", "Z5"], ("0", "U"): ["Z7"], ("0", "MU"): ["Z7", "Zm-b", "Z5"],
                 ("M", "MU"): ["Z7"], ("U", "MU"): ["Zm-b", "Z5"]}, got)
    case("R-10 owners: arm-0 Z5 / Z-RB / Z6 -> STOP; Z6 in MU -> U1 + MOV; Z5 in U -> U1; Z-RB in U or E1 -> REPORTED "
         "(R3 D-12: 22.8.2 makes STOP arm-0 only); Z-RB in M -> MOV; Z4 in M -> reported",
         UA.zero_owners("Z5", "0") == "STOP" and UA.zero_owners("Z-RB", "0") == "STOP" and UA.zero_owners("Z6", "0")
         == "STOP" and UA.zero_owners("Z6", "MU") == {"U1", "MOV"} and UA.zero_owners("Z5", "U") == {"U1"}
         and UA.zero_owners("Z-RB", "U") == "REPORTED" and UA.zero_owners("Z-RB", "E1") == "REPORTED"
         and UA.zero_owners("Z-RB", "M") == {"MOV"} and UA.zero_owners("Z4", "M") == "REPORTED"
         and UA.zero_owners("Z1-M", "MU") == {"MOV"} and UA.zero_owners("Z3", "E1") == {"U1"})
    # ============================================================== structural zeros: one violation each
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
    hx = ["a%d" % t for t in range(10)]
    hy = list(hx)
    hy[4] = "zz"                                                   # rows differ at step 5
    kx = [kick(0, 7, div_shadow=True, u1=(V1, V0), bound=((V0, U0),))]
    ky = [kick(0, 7, divergent=True, div_shadow=True, u1=(V1, V0), bound=((V1, U0),))]
    res = UA.z1_u1(digest(hx, kicks=kx), digest(hy, kicks=ky))
    case("Z1 violation: the runs first differ at step 5 but the first U1-divergent kick is at step 7",
         any("first difference at step 5" in v for v in res["viol"]), res["viol"])
    hy = list(hx)
    hy[6] = "zz"
    res = UA.z1_u1(digest(hx, kicks=kx), digest(hy, kicks=ky))
    case("Z1 holds: first difference at the divergent kick's step 7, X's shadow flags it, shadows equal",
         not res["viol"] and res["s"] == 7, res["viol"])
    res = UA.z1_u1(digest(hx, kicks=kx, so=["l0", "x step=3", "l2"], marks=[None, 3, None]),
                   digest(hy, kicks=ky, so=["l0", "y step=3", "l2"], marks=[None, 3, None]))
    case("Z1 violation: stdout (new tags stripped) provably differs by step 3, before the kick at 7",
         any("stdout differs by step 3" in v for v in res["viol"]), res["viol"])
    res = UA.z1_u1(digest(hx), digest(hy))
    case("Z1 (i) violation: no divergent kick but the runs differ", any("no U1-divergent kick" in v for v in res["viol"]))
    kx2 = [kick(0, 7, div_shadow=False, u1=(V1, V0), bound=((V0, U0),))]
    res = UA.z1_u1(digest(hx, kicks=kx2), digest(hy, kicks=ky))
    case("Z1 cross-arm violation: X's shadow verdict at the kick differs from Y's", any(
        "cross-arm shadow" in v or "does not flag" in v for v in res["viol"]), res["viol"])
    ev_y = [{"step": 9, "kind": "a", "unit": U0, "live": True, "row": 0, "cell": [2, 1],
             "today": ["greedy", [1, 2], 1, False]}]
    ev_x = [dict(ev_y[0], live=False)]
    rows = [mvrow(0, 9, U0, acted="a", fa=(2, 1))]
    hy = list(hx)
    hy[5] = "zz"                                                   # differ at step 6
    res = UA.z1_mov(digest(hx, events=ev_x, rows=rows), digest(hy, events=ev_y, rows=rows))
    case("Z1-M violation (ii): first difference at step 6, before s* = 9 (the first live ACTED event)",
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
         any("(a) / (c) cell change" in v for v in res["viol"]), res["viol"])
    res = UA.z1_mov(digest(hx, events=[], rows=rows), digest(hx[:8] + ["zz", "zz"], events=ev_y, rows=rows))
    case("Z1-M violation (iii): no matching would-act shadow in X", any("no matching would-act" in v for v in res["viol"]),
         res["viol"])
    res = UA.z1_mov(digest(hx), digest(hx[:3] + ["zz"] + hx[4:]))
    case("Z1-M violation (i): no movement switch ACTED but the runs differ",
         any("no movement switch ACTED" in v for v in res["viol"]), res["viol"])
    bad = UA.z2_u1([cmd(5, "post", "unassign", V0, U0, "x")], [["kick:K1", "u1pass"]], [], [])
    ok = UA.z2_u1([cmd(5, "post", "assign", V0, U0)], [["kick:K1", "u1pass"]], [[5, "post", V1, "", "r", "", []]],
                  [["adv:ff_unit_0"]])
    case("Z2 violation: an unassign issued inside the U1 pass (assigns inside it are allowed)", len(bad) == 1 and not ok,
         bad)
    bad = UA.z2_mov([cmd(5, "advance", "assign", V0, U0)], [["adv:ff_unit_0", "fix:a"]],
                    [[5, "advance", V1, "", "r", "", []]], [["adv:ff_unit_1", "fix:_fix_move"]])
    ok = UA.z2_mov([cmd(5, "advance", "unassign", V0, U0, "replacement_after_blocked")], [["adv:ff_unit_0"]], [], [])
    case("Z2-M violation: a command and a release issued from movement fix code (today's advance path is not)",
         len(bad) == 2 and not ok, bad)
    bad = UA.z3_kicks([kick(0, 4, qualifies=False, ms_model=3.0)])
    bad2 = UA.z3_kicks([kick(0, 4, qualifies=False, index=(V0, V1), bound=((V1, U0), (V0, U1_)),
                             F=((U0, (1, 1)), (U1_, (2, 2))))])
    ok = UA.z3_kicks([kick(0, 4, qualifies=False, index=(V0, V1), bound=((V0, U0), (V1, U1_)),
                           F=((U0, (1, 1)), (U1_, (2, 2))))])
    case("Z3 violation: the ordering function entered at a non-qualifying kick; binds out of index order",
         len(bad) == 1 and len(bad2) == 1 and not ok, (bad, bad2))
    bad = UA.z4_kicks([kick(0, 4, rec={V0: [10.0, 12, True], V1: [50.0, 3, True]})], False)
    bad2 = UA.z4_kicks([kick(0, 4, rec={V0: [10.0, 9, True], V1: [50.0, 3, True]}, z4_ok=False)], False)
    tri = "[UrgencyTriage] step=4 unit=ff_unit_0 order=[victim_0(T=10.0,c=9,P) victim_1(T=50.0,c=3,D)] served=victim_0"
    bad3 = UA.z4_kicks([kick(0, 4, rec={V0: [10.0, 9, True], V1: [50.0, 3, True]}, triage=tri)], True)
    ok = UA.z4_kicks([kick(0, 4, rec={V0: [10.0, 9, True], V1: [None, None, False]},
                           triage="[UrgencyTriage] step=4 unit=ff_unit_0 order=[victim_0(T=10.0,c=9,P) "
                                  "victim_1(T=inf,c=inf,D)] served=victim_0")], True)
    case("Z4 violations: a promotion with c + 1 > T; the independent recomputation disagreeing; a triage verdict "
         "differing from the record (and c + 1 = T is promotable)", len(bad) == 1 and len(bad2) == 1
         and len(bad3) == 1 and not ok, (bad, bad2, bad3, ok))
    b = [cmd(1, "post", "assign", V0, U0), cmd(3, "post", "assign", V0, U1_), cmd(5, "post", "assign", V0, U0)]
    rets = UA.gt_returns_amended(b, [[s, []] for s in range(1, 6)], {}, {})
    case("Z5 violation: A..X..A on a victim with no outside event on X", len(rets) == 1 and not rets[0]["outside"], rets)
    rb = {U1_: {5}}
    rets_amd = UA.gt_returns_amended(b, [[s, []] for s in range(1, 6)], {}, rb)
    rets_dpr = UA.gt_returns(b, [[s, []] for s in range(1, 6)], {}, rb)
    case("Z5 AMENDED (section 10): a post-phase return whose X is route_blocked in rows_ff at the return step is a "
         "same-frame latch whatever the reason ('initial'); DPR's own definition does not accept it",
         rets_amd[0]["outside"] == ["o2@frame"] and rets_dpr[0]["outside"] == [] and UA.outside_events is not
         UA.outside_events_amended, (rets_amd, rets_dpr))
    opts = types.SimpleNamespace(smoke="x", head=None)
    d = {"crashed": {"type": "ValueError", "step": 17}, "steps": 360, "steps_done": 17, "terminal_step": None,
         "extra_params": {}, "dp": {"probe": "dp_probe v2"}, "ud": {"probe": "ud_probe v1", "switches": {}},
         "fb3": {"crn": {"on": True, "crn_draws": 5}}, "mv": {"cols": list(UA.MV_COLS), "rows": []}}
    why, crash, stop = UA.prov_run(d, os.path.join(HERE, "__no_such_run__.json"), None, None, opts)
    d2 = dict(d, crashed=None, steps_done=200, terminal_step=None)
    _w, crash2, _s = UA.prov_run(d2, os.path.join(HERE, "__no_such_run__.json"), None, None, opts)
    case("Z6 violation: a crash, and a run that stops neither terminal nor at its last step, are reported as crashes "
         "(a GATE FAILURE owned by the arm's switches)", crash is not None and "crashed ValueError" in crash
         and crash2 is not None and "stopped at step 200" in crash2, (crash, crash2))
    d3 = dict(d, crashed=None, steps_done=360, ud={"probe": "ud_probe v1", "switches": {}, "errors": ["mv_purity: x"]},
              fb3={"crn": {"on": True, "crn_draws": 0}})
    why3, crash3, _s = UA.prov_run(d3, os.path.join(HERE, "__no_such_run__.json"), None, None, opts)
    case("INVALID: an instrument error and 0 CRN draws make a run INVALID (16.6), not a crash",
         crash3 is None and any("instrument errors" in w for w in why3) and any("crn_draws 0" in w for w in why3), why3)
    bad = UA.z7_kicks([kick(0, 4, u1=(V1, V0), bound=((V0, U0),))])
    bad2 = UA.z7_kicks([kick(0, 4, u1=(V0, V1), bound=((V0, U1_),))])
    ok = UA.z7_kicks([kick(0, 4, u1=(V1, V0), bound=((V1, U0),))])
    case("Z7 violations: the bound victim is not the first of the U1 order; the bound unit is not f",
         len(bad) == 1 and len(bad2) == 1 and not ok, (bad, bad2))
    bad = UA.z8_kicks([kick(0, 4, bound=((V0, U0), (V1, U1_)))])
    bad2 = UA.z8_kicks([kick(0, 4, qualifies=False, index=(V0,), bound=((V0, U0), (V1, U1_)))])
    case("Z8 violations: a qualifying kick binding 2 (counterfactual 1); a kick binding more than min(|W|, |F|)",
         len(bad) == 1 and len(bad2) == 1, (bad, bad2))
    bad = UA.z_rb([mvrow(0, 3, U0, zrb=True, rb_call=0, mt=1)], False)
    bad2 = UA.z_rb([mvrow(0, 3, U0, zrb=True, acted="a", rb_call=1)], False)
    bad3 = UA.z_rb([mvrow(0, 3, U0, leg="carry", branch="c1", rb_call=1, mt=0)], True)
    ok = UA.z_rb([mvrow(0, 3, U0, zrb=True, rb_call=1, mt=1), mvrow(1, 3, U1_, leg="carry", rb_call=1, mt=1)], False)
    case("Z-RB violations: no raise although today's predicate holds; an (a)-acted step with the predicate true; a "
         "carrier raise with (c) effective", len(bad) == 1 and len(bad2) >= 1 and len(bad3) == 1 and not ok,
         (bad, bad2, bad3))
    rows = [mvrow(0, 3, U0, branch="approach_a", dc=8, post=(2, 1)), mvrow(1, 4, U0, branch="approach_a", dc=8)]
    bad, n = UA.zm_a(rows)
    rows_ok = [mvrow(0, 3, U0, branch="approach_a", dc=8), mvrow(1, 4, U0, branch="approach_a", dc=7),
               mvrow(2, 5, U0, branch="approach_a", dc=9, digest="d1")]
    ok, n2 = UA.zm_a(rows_ok)
    case("Zm-a violation: D 8 -> 8 over consecutive (a) steps on an unchanged board (a changed digest is exempt)",
         len(bad) == 1 and n == 1 and not ok and n2 == 1, (bad, ok))
    bad = UA.zm_b([mvrow(0, 3, U0, branch="retreat_b", post=(3, 3), fbB=[(2, 2)])])
    bad2 = UA.zm_b([mvrow(0, 3, U0, branch="retreat_b", post=(2, 2), fbB=[(2, 2)], cls_post="A")])
    ok = UA.zm_b([mvrow(0, 3, U0, branch="retreat_b", post=(2, 2), fbB=[(2, 2), (1, 3)])])
    case("Zm-b violations: a (b) step off B; a (b) step onto a fire-adjacent cell", len(bad) == 1 and len(bad2) == 1
         and not ok)
    rows_ff = [[ffrow(U0, 5, 5, exiting=1, victim=V0), ffrow(U1_, 9, 9, assigned=0)] for _ in range(12)]
    ffs = UA.ff_cells_by_step(rows_ff)
    drop, exc = UA.zm_c([], [cmd(10, "advance", "unassign", V0, U0, "replacement_after_blocked")], ffs, {}, {})
    cas, exc2 = UA.zm_c([], [cmd(10, "sweep", "unassign", V0, U0, "firefighter_fire_casualty")], ffs, {}, {})
    cust, _e = UA.zm_c([], [cmd(10, "post", "assign", V0, U1_)], ffs, {}, {})
    dup, _e = UA.zm_c([], [], ffs, {V0: 12}, {V0: 2})
    one, _e = UA.zm_c([], [], ffs, {V0: 12}, {V0: 1})
    c1, _e = UA.zm_c([mvrow(0, 3, U0, leg="carry", branch="c1", c1_pre=[2, 0, 10], c1_post=[2, 0, 10])], [], {}, {}, {})
    c1ok, _e = UA.zm_c([mvrow(0, 3, U0, leg="carry", branch="c1", c1_pre=[2, 0, 10], c1_post=[1, 0, 9])], [], {}, {},
                       {})
    cyc_rows = [mvrow(i, 3 + i, U0, leg="carry", branch="c0", pre=p, post=q) for i, (p, q) in enumerate(
        [((1, 1), (1, 2)), ((1, 2), (1, 3)), ((1, 3), (1, 2))])]
    cyc, _e = UA.zm_c(cyc_rows, [], {}, {}, {})
    cyc_ok, _e = UA.zm_c([dict(r, digest="d%d" % i) for i, r in enumerate(cyc_rows)], [], {}, {}, {})
    case("Zm-c violations: a DROP (route_blocked-pathway unassign of an exiting unit; a casualty unassign is excluded and "
         "reported); a dispatch to a victim in custody; 2 victim_dead for a victim who died in custody; a C-1 step whose "
         "cost does not fall; a carry cycle on an equal digest",
         len(drop) == 1 and not exc and not cas and len(exc2) == 1 and len(cust) == 1 and len(dup) == 1 and not one
         and len(c1) == 1 and not c1ok and len(cyc) == 1 and not cyc_ok, (drop, cas, cust, dup, c1, cyc))
    bad, holds = UA.z_s([mvrow(0, 3, U0, branch="approach_a", cls_post="B"),
                         mvrow(1, 3, U1_, branch="c3", leg="carry", cls_post="B")])
    ok, _h = UA.z_s([mvrow(0, 3, U0, branch="c1", leg="carry", cls_post="A", gesc=None)])
    case("Z-S violation: an (a) step onto a burning cell (a C-3 hold on a burning cell is reported, not gated); a C-1 "
         "step onto a fire-adjacent cell is allowed", len(bad) >= 1 and len(holds) == 1 and not ok, (bad, holds))
    # ============================================================== counts and attribution
    leg = [mvrow(i, 10 + i, U0, pre=p, dr=d_) for i, (p, d_) in enumerate(
        [((1, 1), 5), ((1, 2), 4), ((1, 1), 5)] + [((2, 2 + k), 4 - (k % 2)) for k in range(10)])]
    ev = UA.leg_events(leg)
    case("C-1 leg kinds (approach): a recurring cell after collapsing -> CYCLE; route distance not lower 10 steps later -> "
         "PROGRESS", ev["cycle"] and ev["prog"], ev)
    cells = [(5, 5), (5, 6), (6, 6), (6, 5)]
    carry = [mvrow(i, 50 + i, U0, leg="carry", branch="c1", pre=cells[i % 4], dr=5) for i in range(32)]
    ev_c = UA.leg_events(carry)
    carry_x = [dict(r, branch="c2s") if i in (15, 16) else r for i, r in enumerate(carry)]
    ev_x = UA.leg_events(carry_x)
    case("C-2 carry NO-PROGRESS (30-step window, >= 4 moves, dr not lower) is found; the designed-behaviour exclusion "
         "(C-2 stay rows) splits the series so no 30-step window remains",
         ev_c["noprog"] and ev_c["prog"] and not ev_x["noprog"], (ev_c["noprog_w"], ev_x["noprog_w"]))
    osc = [mvrow(i, 80 + i, U0, pre=[(3, 3), (3, 4)][i % 2], dr=5) for i in range(10)]
    case("C-3 OSCILLATION: a 10-frame window on 2 cells with >= 2 changes", UA.leg_events(osc)["osc"])
    binders = [[1, [[V0, [[U0, "route_blocked"]]]]], [2, [[V0, [[U0, "route_blocked"]]]]], [3, []],
               [4, [[V0, [[U0, "route_blocked"]], ], [V1, [[U1_, "route_blocked"]]]]]]
    case("C-4 F6 latch episodes: maximal runs of consecutive samples with the pair route_blocked (3 here)",
         len(UA.latch_episodes(binders)) == 3, UA.latch_episodes(binders))
    rows_ff = [[ffrow(U0, 1, 1, victim=V0, assigned=1)] for _ in range(40)]
    rows_vic = [[[V0, 1, 9, "candidate", "candidate", "", 0, 0, 0, 0]] for _ in range(40)]
    ffs = UA.ff_cells_by_step(rows_ff)
    m8e = {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 40}
    cls, flags, m8d = UA.attribute(V0, 10, 30, m8e, [], [], [], ffs, rows_ff, rows_vic, [], [], [], {}, [], [])
    case("C-5 attribution: M8 futile (min_d 40 + 1 > 30 - 10) -> FUT first", cls == "FUT" and not m8d, (cls, flags))
    m8e = {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 5}
    dec = [{"k": 0, "step": 12, "vid": V0, "d": 6, "served": False}, {"k": 0, "step": 12, "vid": V1, "d": 3,
                                                                      "served": True}]
    cls, flags, m8d = UA.attribute(V0, 10, 30, m8e, dec, [], [], ffs, rows_ff, rows_vic, [], [], [], {}, [], [])
    case("C-6 attribution: passed over at a qualifying kick with the free unit's d + 1 <= death - t -> U1",
         cls == "U1", (cls, flags))
    waiting = [[15, 1, [[V0, [[U1_, 4, 0]]]]]]
    cls, flags, m8d = UA.attribute(V0, 10, 30, m8e, [], [], waiting, ffs, rows_ff, rows_vic,
                                   [mvrow(0, 20, U0, today=["greedy", (1, 2), 1, False], dcx=None, df=None)], [], [],
                                   {}, [], [])
    case("C-7 attribution: M8-D from a waiting sample (free unit d 4 + 1 <= 30 - 15); a step with no clean and no "
         "fire-free distance -> MOV-closure", m8d and cls == "MOV-closure", (cls, flags, m8d))
    # ============================================================== validity against a queue line (temp files only)
    import json
    import tempfile
    tmp = tempfile.mkdtemp(prefix="ud_selftest_")
    path = os.path.join(tmp, "_sd_ud1r3_A_E.json")
    sd = ["--repo", UA.WT, "--scenario", "A", "--wind", "east", "--seed", "573003", "--set", "GLOBAL_PLANNER_MODE=0",
          "--set", "VICTIM_SPAWN_MODE=0", "--set", "DISPATCH_URGENCY=1", "--steps", "360", "--set", "BATCH_SIZE=360",
          "--out", path, "--tag", "ud1r3_A_E"]
    line = {"name": "ud1r3_A_E", "argv": [os.path.join(UA.OUT_DIR, "_ud_probe.py"), "--crn", "--hazard", "--"] + sd,
            "out": path, "cwd": UA.WT}
    with open(path + ".argv", "w", encoding="utf-8") as fh:
        fh.write(UA.POOL.signature(line))
    with open(path[:-5] + ".stdout.txt", "w", encoding="utf-8") as fh:
        fh.write("[Victim Detection] step=3 UAV-2502 detected victim_0 at (1, 1)\n")
    rc_, hd = UA.git("rev-parse", "HEAD")
    head_sha = hd.decode().strip()
    pick = lambda rel: sorted(UA.committed_shas(head_sha, rel) or ["missing"])[0]          # noqa: E731
    # the Part 2 modules are not in this worktree's HEAD yet: the cases below require two files HEAD does hold
    req_saved = UA.UD_SRC_REQUIRED
    UA.UD_SRC_REQUIRED = ("agents.py", "common_fixed_variables.py")
    ud_src = {rel: pick(rel) for rel in UA.UD_SRC_REQUIRED}
    good = {"repo": UA.WT, "head": head_sha, "argv": sd, "steps": 360, "steps_done": 360, "terminal_step": None,
            "crashed": None, "scenario": "A", "wind": "east", "seed": 573003,
            "extra_params": {"GLOBAL_PLANNER_MODE": 0, "VICTIM_SPAWN_MODE": 0, "DISPATCH_URGENCY": 1, "BATCH_SIZE": 360},
            "fb3": {"crn": {"on": True, "crn_draws": 99}, "eff": {"victim_spawn_mode": 0}},
            "dp": {"probe": "dp_probe v2", "commands": [], "releases": [], "errors": [],
                   "src_sha": {"agents.py": pick("agents.py")}},
            "ud": {"probe": UA.UD_PROBE, "errors": [], "shadow_mismatch": [], "cmd_ctx": [], "rel_ctx": [],
                   "src_sha": ud_src,
                   "switches": {"DISPATCH_URGENCY": True, "FF_APPROACH_PATH": False, "FF_RETREAT_KEEP_APPROACH": False,
                                "FF_CARRY_REPLAN": False, "FF_EXIT_LEG_MODE": 2, "FF_EXIT_LEG_SERVED": 1}},
            "mv": {"cols": list(UA.MV_COLS[:20]) + ["dcb"] + list(UA.MV_COLS[20:]), "rows": []}, "mv_events": []}
    cell = {"scen": "A", "wind": "east", "seed": 573003}
    o2 = types.SimpleNamespace(smoke=None, head=head_sha[:8])
    w0, c0, s0 = UA.prov_run(good, path, line, cell, o2)
    w1, _c, _s = UA.prov_run(dict(good, extra_params=dict(good["extra_params"], DISPATCH_URGENCY=0)), path, line, cell,
                             o2)
    w2, _c, _s = UA.prov_run(dict(good, head="0123456789"), path, line, cell, o2)
    w3, _c, s3_ = UA.prov_run(dict(good, seed=573004), path, line, cell, o2)
    w4, _c, _s = UA.prov_run(dict(good, ud=dict(good["ud"], switches=dict(good["ud"]["switches"],
                                                                          DISPATCH_URGENCY=False))), path, line, cell, o2)
    w5, _c, _s = UA.prov_run(good, path, None, cell, o2)
    case("V-1 16.6 validity against the queue line: a valid ud_probe v2 run passes; extra_params, head and the effective "
         "switch differing make it INVALID; no queue line is INVALID; a seed differing from the frozen cell is a STOP",
         not w0 and c0 is None and s0 is None and any("extra_params" in w for w in w1) and any("head" in w for w in w2)
         and s3_ is not None and "SEED MISMATCH" in s3_ and any("effective switches" in w for w in w4)
         and any("no line" in w for w in w5), (w0, w1, w2, s3_, w4, w5))
    w6, _c, _s = UA.prov_run(dict(good, ud=dict(good["ud"], probe="ud_probe v1"),
                                  mv={"cols": list(UA.MV_COLS), "rows": []}), path, line, cell, o2)
    w6s, _c, _s = UA.prov_run(dict(good, ud=dict(good["ud"], probe="ud_probe v1"),
                                   mv={"cols": list(UA.MV_COLS), "rows": []}), path, line, cell,
                              types.SimpleNamespace(smoke="x", head=None))
    w7, _c, _s = UA.prov_run(dict(good, mv={"cols": list(UA.MV_COLS), "rows": []}), path, line, cell, o2)
    case("V-2 probe version: a ud_probe v1 record is INVALID for the screen but readable in --smoke; a v2 record "
         "without the dcb column is INVALID",
         any("ud.probe" in w for w in w6) and not w6s and any("d['mv']" in w for w in w7), (w6, w6s, w7))
    doct = dict(good, ud=dict(good["ud"], src_sha=dict(ud_src, **{"agents.py": "0" * 64})))
    w8, _c, _s = UA.prov_run(doct, path, line, cell, o2)
    rc_, blob = UA.git("show", "%s:common_fixed_variables.py" % head_sha)
    import hashlib
    lfb = blob.replace(b"\r\n", b"\n")
    forms = {hashlib.sha256(lfb).hexdigest(), hashlib.sha256(lfb.replace(b"\n", b"\r\n")).hexdigest()}
    case("M-2 provenance (R2 M-2): a record whose ud.src_sha for agents.py is not the file at --head is INVALID "
         "('ran uncommitted source'); the committed file's LF and CRLF forms are both accepted; a record that names no "
         "src_sha is INVALID",
         any("ran uncommitted source" in w and "agents.py" in w for w in w8)
         and forms <= (UA.committed_shas(head_sha, "common_fixed_variables.py") or set())
         and not UA.src_check(good, head_sha)
         and any("not recorded" in w for w in UA.src_check(dict(good, dp=dict(good["dp"], src_sha={})), head_sha))
         and any("does not name" in w for w in UA.src_check(dict(good, ud=dict(good["ud"], src_sha={
             "agents.py": ud_src["agents.py"]})), head_sha)),
         (w8, len(forms)))
    kick_row = [7, U0, "u1", "kick bind differs from the acc shadow", "kick:0", V1, V2]
    mov_row = [9, U0, "a", "shadow acted, model did not", "approach", [2, 1], [1, 2]]
    beh = dict(good, ud=dict(good["ud"], shadow_mismatch=[kick_row, mov_row]),
               mv_events=[{"step": 11, "kind": "b", "unit": U0, "victim": V0, "live": True, "agree": False}])
    w9, c9, _s = UA.prov_run(beh, path, line, cell, o2)
    w9e, _c, _s = UA.prov_run(dict(good, ud=dict(good["ud"], errors=["mv_purity: x"])), path, line, cell, o2)
    case("SMR-1 (ruling on 16.6) a run whose ud.shadow_mismatch holds a kick-bind row and a movement row, and whose "
         "mv_events hold a live ACTED disagreement, is NOT INVALID (behaviour, not an instrument error); ud.errors "
         "still make a run INVALID",
         not w9 and c9 is None and any("instrument errors" in w for w in w9e), (w9, w9e))
    UA.UD_SRC_REQUIRED = req_saved
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    ok_h, _l = UA.hash_checks()
    with open(os.path.join(HERE, "urgency_part1.txt"), encoding="utf-8") as fh:
        text = fh.read()
    bad_h, lines_h = UA.hash_checks(text.replace("p_k = P( Binomial(n_plus + n_minus, 1/2) >= n_plus )",
                                                 "p_k = P( Binomial(n_plus + n_minus, 1/2) > n_plus )"))
    case("H-2 hash checks: the working urgency_part1.txt passes; one edited character in section 23 is REFUSED",
         ok_h and not bad_h and any("23" in ln and "DIFFERS" in ln for ln in lines_h), [ln for ln in lines_h
                                                                                   if "DIFFERS" in ln])
    vok, _vl = UA.verbatim_check()
    case("H-3 the replicated DPR functions are verbatim substrings of dispatch:outputs/_dp_analyze.py at cc8d653c", vok)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        frozen = UA.load_seeds()
    case("H-4 seeds: the 16.2 rule recomputed from outputs/_ud_seeds.txt gives 4 sets x 16 cells (set 3 A_N = 573001, "
         "set 4 D_W = 780016)", frozen is not None and all(len(frozen[s]) == 16 for s in UA.EXPECTED_BASES)
         and ["A_N", "A", "north", "573001"] in frozen["set3"] and ["D_W", "D", "west", "780016"] in frozen["set4"])
    rows_ff2 = [[ffrow(U0, 1, 1, victim=V0, assigned=1), ffrow(U1_, 1, 5, victim=V1, assigned=1)] for _ in range(40)]
    ffs2 = UA.ff_cells_by_step(rows_ff2)
    m8e = {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 8}
    waiting = [[10, 0, [[V0, []]]]]
    cls, flags, _m = UA.attribute(V0, 10, 30, m8e, [], [], waiting, ffs2, rows_ff2, rows_vic, [], [], [], {}, [], [])
    cls2, flags2, _m = UA.attribute(V0, 10, 30, dict(m8e, min_d=19), [], [], [[12, 0, [[V0, []]]]], ffs2, rows_ff2,
                                    rows_vic, [], [], [], {}, [], [])
    case("C-8 attribution PRE: unbound at detection with no free unit and the record's busy-unit d (m8 min_d 8 + 1 <= "
         "30 - 10) -> PRE; at a later step only the Manhattan bound exists -> flag PRE(L1), class not PRE",
         cls == "PRE" and cls2 != "PRE" and "PRE(L1)" in [k for k, v in flags2.items() if v], (cls, cls2,
                                                                                            dict(flags2)))
    i2 = {"stuck_approach": [[12, 20, U0]]}
    rows_ff3 = [[ffrow(U0, 1, 1, victim=V0, assigned=1), ffrow(U1_, 1, 5, assigned=0, status="available")]
                for _ in range(40)]
    ffs3 = UA.ff_cells_by_step(rows_ff3)
    m8e = {"victim": V0, "detection_step": 10, "death_step": 30, "min_d": 3}
    cls, flags, _m = UA.attribute(V0, 10, 30, m8e, [], [], [[15, 1, [[V0, [[U1_, 4, 0]]]]]], ffs3, rows_ff3, rows_vic,
                                  [], [], [], i2, [], [])
    cls2, flags2, _m = UA.attribute(V0, 10, 30, m8e, [], [], [], ffs3, rows_ff3, rows_vic, [], [], [], i2, [], [])
    case("C-9 attribution L3: her unit's I2 STUCK window while she is latched-held with a free unit's recorded d (4 + 1 "
         "<= 30 - 15) -> L3; without a recorded d only the flag L3(L1) is set",
         cls == "L3" and cls2 == "OTHER" and flags2.get("L3(L1)"), (cls, cls2, dict(flags2)))
    reported_cases()
    smoke_case()
    review_cases()
    ruling_cases()
    txt ="x\n16.5 THE INSTRUMENT\n  a\n\n16.12 WAVES\ny\n====\n23. AMENDMENT B2\n b\n\n====\n24. NEXT\nz"
    case("H-1 hashed-section extraction: up to the next named header; trailing blank / '=' lines dropped; 23 stops at a "
         "later top-level header", UA.extract_section(txt, "16.5 THE INSTRUMENT", "16.12 WAVES") == "16.5 THE INSTRUMENT"
         "\n  a" and UA.extract_section(txt, "23. AMENDMENT B2", None) == "23. AMENDMENT B2\n b")
    LINES.append("")
    LINES.append("SELF-TEST %s (%d cases, %d failed)" % ("PASS" if not FAILS else "FAIL", sum(
        1 for ln in LINES if ln.startswith(("PASS", "FAIL"))), len(FAILS)))
    text = "\n".join(LINES)
    print(text)
    if "--out" in _argv:
        with open(_argv[_argv.index("--out") + 1], "w", encoding="utf-8", newline="\n") as fh:
            fh.write("urgency round - synthetic-record self-test of outputs/_ud_analyze.py\n\n" + text + "\n")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
