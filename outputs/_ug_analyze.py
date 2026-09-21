"""Ungated-firefighting round, Part 3 analysis. Read-only; implements every item of
outputs/ungated_part1.txt section 6 (pre-registered before any run existed).

  .venv/Scripts/python.exe -B outputs/_ug_analyze.py [--out outputs/_ug_analysis.txt]

ARMS (tag: checkout, the exact --set dict every run of the arm must carry)
  ugC  CTRL  {}                               the 11c3661 control
  ugD  FLIP  {}                               the shipped default (no --set)
  ugX  CTRL  E=1 F=1 K=1 G=0 DRY=0            the explicitly configured arm (G1)
  ugA  CTRL  ugX + FIREPROOF=0 BOUNDS_FIX=0   the anchor: must equal the fmEFS corpus (G1)
  ugY  FLIP  DRY_RUN=1                        positioning only, stock
  ugKC CTRL  FM2P_CRN=1                       CRN control
  ugKD FLIP  FM2P_CRN=1                       CRN shipped
  ugKY FLIP  FM2P_CRN=1 DRY_RUN=1             CRN positioning only
A run whose recorded repo, extra_params, seed, wind, roles or steps is not exactly its
arm's is REFUSED (never used), and the refusal is printed (worktree-round-isolation).

DEFINITIONS (section 6.4)
  intact      |fire_ground_final| - ever_burned - depot_unburned - ff_cleared_unburned,
              depot cells read FROM THE RUN (base_station depots, 5x5 each);
              ff_cleared_unburned = firefight_counters.cleared_unburned (0 when absent).
              Cross-check, when present: fire_cleared_unburned_final - depot_unburned ==
              ff_cleared_unburned. P8: the round-1 analyzer's intact would count the 50
              depot cells as cleared in feature runs only.
  E1 / E2     _dfp_analyze.exposure (the interior-hazard definition + the depot split)
  deaths      _firemech_analyze.run_summary's classifier (engaged / prev / streak /
              preempted / enclosure / after_terminal)
  re-rolled   stock run whose fire digest first differs from its control's before the
              control's terminal_step (240 when non-terminal)
  attribution DRY arm fire == control fire 240/240; writing arm's first fire divergence
              == its first write step
  oob         searcher off-grid refusals (_sfx_analyze.oob_refusals); must be 0 in every
              arm with the guard on (all but ugA, which switches it off on purpose)
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _firemech_analyze as FM  # noqa: E402
import _dfp_analyze as DFP  # noqa: E402
import _sfx_analyze as SFX  # noqa: E402
import _ug_seeds  # noqa: E402

FLIP = "e:/projects/sas"
CTRL = "e:/projects/sas_wt/base11c3661"
EXPL = {"FF_FIREFIGHT_EXTINGUISH": 1, "FF_FIREFIGHT_FIREBREAK": 1,
        "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE": 1, "FF_FIREFIGHT_MISSION_GATE": 0,
        "FF_FIREFIGHT_DRY_RUN": 0}
ARMS = {
    "ugC": (CTRL, {}),
    "ugD": (FLIP, {}),
    "ugX": (CTRL, dict(EXPL)),
    "ugA": (CTRL, dict(EXPL, BASE_STATION_FIREPROOF=0, VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX=0)),
    "ugY": (FLIP, {"FF_FIREFIGHT_DRY_RUN": 1}),
    "ugKC": (CTRL, {"FM2P_CRN": 1}),
    "ugKD": (FLIP, {"FM2P_CRN": 1}),
    "ugKY": (FLIP, {"FM2P_CRN": 1, "FF_FIREFIGHT_DRY_RUN": 1}),
}
EXCLUDE = ("tag", "repo", "wall_s", "params", "extra_params")
C13 = DFP.CANONICAL
F10 = DFP.FRESH
RB4 = DFP.RB_EXTRA
RB18 = DFP.RB18


def _u30():
    tuples, _r, _s, _n = _ug_seeds.choose()
    out = []
    for combo, seed, _c, _i in tuples:
        w, r = combo.split("|")
        out.append((w, r, seed))
    return out


U30 = _u30()
ACCEPTED = {"stock": (2, 68), "crn_shipped": (3, 72), "crn_positioning": (6, 72)}
M = 3
OUT = []


def say(s=""):
    OUT.append(str(s))
    print(s)


def label(t):
    return FM.label(t)


def norm(p):
    return str(p or "").replace("\\", "/").rstrip("/").lower()


REFUSED = []


def load(tag, t, check=True):
    p = FM.path(tag, t)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    if not check or tag not in ARMS:
        return d
    repo, sets = ARMS[tag]
    why = []
    if norm(d.get("repo")) != repo:
        why.append("repo %r" % d.get("repo"))
    if (d.get("extra_params") or {}) != sets:
        why.append("extra_params %r" % d.get("extra_params"))
    if (d.get("wind"), d.get("roles"), d.get("seed"), d.get("steps")) != (t[0], t[1], t[2], 240):
        why.append("tuple %r" % ((d.get("wind"), d.get("roles"), d.get("seed"), d.get("steps")),))
    crn = "FM2P_CRN" in sets
    if crn and not d.get("fm2p"):
        why.append("CRN arm without an fm2p block")
    if not crn and d.get("fm2p"):
        why.append("stock arm WITH an fm2p block")
    if why:
        REFUSED.append((tag, label(t), "; ".join(why)))
        return None
    return d


def victims(d):
    vs = d.get("victim_steps") or []
    return {v[0]: v[2] for v in (vs[-1] if vs else [])}


def intact_of(d, fireproof=True):
    """fireproof=False (ugA, and any pre-6668368 corpus): the depot is ordinary
    vegetation there, so it is neither subtracted nor part of the cross-check."""
    fgf = d.get("fire_ground_final") or {}
    dep = (DFP.depot_cells(d) or set()) if fireproof else set()
    ever = sum(1 for v in fgf.values() if v[0])
    dep_unburned = sum(1 for c in dep if not (fgf.get("%d,%d" % c) or [0])[0])
    cnt = d.get("firefight_counters") or {}
    ffc = int(cnt.get("cleared_unburned") or 0)
    xchk = None
    if "fire_cleared_unburned_final" in d:
        xchk = int(d["fire_cleared_unburned_final"]) - dep_unburned == ffc
    return {"cells": len(fgf), "ever": ever, "dep_unburned": dep_unburned, "ffc": ffc,
            "intact": len(fgf) - ever - dep_unburned - ffc, "xchk": xchk,
            "burning240": sum(1 for v in fgf.values() if v[2])}


def first_dispatch_spacing(d):
    oks = [a for a in (d.get("assigns") or []) if a.get("ok")]
    if not oks:
        return None
    s = min(a["step"] for a in oks)
    ffs = d.get("ff_steps") or []
    row = ffs[s - 2] if s >= 2 and s - 2 < len(ffs) else None
    if row is None:
        return None
    ps = [tuple(p) for _ff, p, _st, _a, _e, dead in row if p is not None and not dead]
    if len(ps) != 2:
        return None
    return abs(ps[0][0] - ps[1][0]) + abs(ps[0][1] - ps[1][1])


def summarize(tag, t, off_d):
    d = load(tag, t)
    if d is None:
        return None
    S = FM.run_summary(d, off_d)
    S.update(intact_of(d, fireproof=(tag in ARMS and tag != "ugA")))
    S["victims"] = victims(d)
    S["exp"] = DFP.exposure(d)
    S["oob"] = SFX.oob_refusals(d)
    S["spacing"] = first_dispatch_spacing(d)
    log = d.get("firefight_log") or []
    eng = [r["step"] for r in log if r.get("engaged")]
    S["first_engaged"] = min(eng) if eng else None
    S["n_writes"] = sum(1 for r in log if r.get("wrote"))
    S["digests"] = d.get("fire_digests") or []
    return S


CACHE = {}


def get(tag, t, ctrl=None):
    key = (tag, tuple(t))
    if key not in CACHE:
        off = None
        if ctrl is not None:
            off = load(ctrl, t)
        CACHE[key] = summarize(tag, t, off)
    return CACHE[key]


CTRL_OF = {"ugD": "ugC", "ugY": "ugC", "ugX": "ugC", "ugKD": "ugKC", "ugKY": "ugKC"}


def S_(tag, t):
    return get(tag, t, CTRL_OF.get(tag))


# ------------------------------------------------------------------ sections --
def sec_provenance():
    say("=" * 88)
    say("0. PROVENANCE - every run checked against its arm (repo, extra_params, tuple, instrument)")
    say("=" * 88)
    plan = {"ugC": C13 + F10 + RB4 + U30, "ugD": C13 + F10 + RB4 + U30, "ugX": C13 + F10,
            "ugA": C13 + F10, "ugY": U30, "ugKC": U30, "ugKD": U30, "ugKY": U30}
    bad = 0
    for tag, tuples in plan.items():
        have = sum(1 for t in tuples if S_(tag, t) is not None)
        say("  %-5s %3d / %3d present and valid" % (tag, have, len(tuples)))
        bad += len(tuples) - have
    for r in REFUSED:
        say("  REFUSED %s %s: %s" % r)
    say("  VERDICT: %s" % ("PASS" if bad == 0 and not REFUSED else "FAIL (%d missing/refused)" % bad))
    return bad == 0 and not REFUSED


def identity(tuples, new, old, why, check_old=True):
    same, rows, missing = 0, [], 0
    for t in tuples:
        a = load(new, t)
        b = load(old, t, check=check_old)
        if a is None or b is None:
            missing += 1
            rows.append("    %-16s MISSING %s" % (label(t), new if a is None else old))
            continue
        dk = FM.diff_keys(a, b, EXCLUDE)
        if not dk:
            same += 1
        else:
            rows.append("    %-16s DIFFERS in %s" % (label(t), ", ".join(dk)))
    ok = same == len(tuples)
    say("  %-5s == %-6s %s %d/%d value-identical (%s; excluded %s)" % (
        new, old, "PASS" if ok else "FAIL", same, len(tuples), why, ", ".join(EXCLUDE)))
    for r in rows:
        say(r)
    return ok


def sec_g1():
    say("")
    say("=" * 88)
    say("G1. IDENTITY")
    say("=" * 88)
    a = identity(C13 + F10, "ugD", "ugX", "no-set flip == explicit E1 F1 K1 G0 at 11c3661")
    b = identity(C13 + F10, "ugA", "fmEFS",
                 "anchor: explicit + FIREPROOF=0 + BOUNDS_FIX=0 at 11c3661 == round 1's fmEFS (003ed91)",
                 check_old=False)
    c = identity(C13 + F10, "ugC", "sfON", "control parity: 11c3661 == 629a321 (same source)",
                 check_old=False)
    say("  G1 VERDICT: %s" % ("PASS" if (a and b and c) else "FAIL"))
    return a and b and c


def ev_row(runs):
    rows = [r for r in runs if r is not None]
    term = [r["terminal"] for r in rows if r["terminal"] is not None]
    return {
        "n": len(rows), "rescued": sum(r["rescued"] for r in rows), "dead": sum(r["dead"] for r in rows),
        "ffd": sum(r["ffd"] for r in rows), "nd": sum(r["nd"] for r in rows),
        "nonterm": sum(1 for r in rows if r["terminal"] is None),
        "meanterm": (sum(term) / len(term)) if term else None,
        "burnt": sum(r["burnt"] for r in rows), "ever": sum(r["ever"] for r in rows),
        "ffc": sum(r["ffc"] for r in rows), "intact": sum(r["intact"] for r in rows),
        "burning240": sum(r["burning240"] for r in rows),
    }


def fmt_ev(tag, e):
    mt = ("%.1f" % e["meanterm"]) if e["meanterm"] is not None else "-"
    return "  %-5s n=%-3d rescued %3d  dead %3d  ff_deaths %3d  never_detected %3d  nonterminal %2d  mean_terminal %6s" % (
        tag, e["n"], e["rescued"], e["dead"], e["ffd"], e["nd"], e["nonterm"], mt)


SAMPLES = [("CANONICAL 13", C13), ("FRESH 10", F10), ("FRESH INDEPENDENT 30 (U30)", U30), ("RB4 (rb18 extras)", RB4)]


def sec_outcomes():
    say("")
    say("=" * 88)
    say("ITEM 6. OUTCOMES PER ARM (counted; de-duplicated = canonical without east/def)")
    say("=" * 88)
    for name, tuples in SAMPLES:
        say(name)
        arms = ["ugC", "ugD", "ugX", "ugA"] if tuples in (C13, F10) else (
            ["ugC", "ugD", "ugY", "ugKC", "ugKD", "ugKY"] if tuples is U30 else ["ugC", "ugD"])
        for tag in arms:
            say(fmt_ev(tag, ev_row([S_(tag, t) for t in tuples])))
        if tuples is C13:
            say("  de-duplicated (east/def excluded):")
            dd = [t for t in C13 if t[1] != "default"]
            for tag in arms:
                say(fmt_ev(tag, ev_row([S_(tag, t) for t in dd])))


def flips(ctrl, feat, tuples):
    losses, gains = [], []
    for t in tuples:
        a, b = S_(ctrl, t), S_(feat, t)
        if a is None or b is None:
            continue
        for vid, st in a["victims"].items():
            st2 = b["victims"].get(vid)
            if st == "rescued" and st2 != "rescued":
                losses.append("%s %s (%s -> %s)" % (label(t), vid, st, st2))
            elif st != "rescued" and st2 == "rescued":
                gains.append("%s %s (%s -> %s)" % (label(t), vid, st, st2))
    return losses, gains


def cost_item(name, ctrl, feat, tuples, accepted, gated=True):
    R = ev_row([S_(ctrl, t) for t in tuples])["rescued"]
    F = ev_row([S_(feat, t) for t in tuples])["rescued"]
    loss = R - F
    k, base = accepted
    scaled = k / base * R
    limit = scaled + M
    ok = loss <= limit
    losses, gains = flips(ctrl, feat, tuples)
    say("  %-26s %s %d -> %s %d   loss %+d   accepted %d/%d scaled to R=%d: %.2f  +M=%d -> limit %.2f   %s" % (
        name, ctrl, R, feat, F, loss, k, base, R, scaled, M, limit,
        ("PASS" if ok else "BREACH - STOP") if gated else ("within" if ok else "EXCEEDS")))
    say("      victim flips: %d lost, %d gained (net %+d)" % (len(losses), len(gains), len(gains) - len(losses)))
    for x in losses:
        say("        LOST   %s" % x)
    for x in gains:
        say("        GAINED %s" % x)
    return ok


def sec_g2():
    say("")
    say("=" * 88)
    say("G2. RESCUE COST ON U30 - two channels, never pooled; M=%d (Q1), CRN shipped vs -3/72 (Q2)" % M)
    say("=" * 88)
    a = cost_item("STOCK (channel 1)", "ugC", "ugD", U30, ACCEPTED["stock"])
    b = cost_item("CRN, shipped arm", "ugKC", "ugKD", U30, ACCEPTED["crn_shipped"])
    c = cost_item("CRN, positioning only", "ugKC", "ugKY", U30, ACCEPTED["crn_positioning"])
    say("  reported, not gated:")
    cost_item("stock, positioning only", "ugC", "ugY", U30, ACCEPTED["crn_positioning"], gated=False)
    cost_item("CRN shipped vs -6/72 (brief)", "ugKC", "ugKD", U30, ACCEPTED["crn_positioning"], gated=False)
    say("  screens (C13+F10, stock; used by six+ rounds, not evidence):")
    cost_item("stock C13+F10", "ugC", "ugD", C13 + F10, ACCEPTED["stock"], gated=False)
    say("  G2 VERDICT: %s" % ("PASS" if (a and b and c) else "BREACH - STOP"))
    return a and b and c


def intact_block(name, ctrl, feat, tuples):
    e0 = ev_row([S_(ctrl, t) for t in tuples])
    e1 = ev_row([S_(feat, t) for t in tuples])
    up = dn = eq = 0
    for t in tuples:
        a, b = S_(ctrl, t), S_(feat, t)
        if a is None or b is None:
            continue
        dlt = b["intact"] - a["intact"]
        up += dlt > 0
        dn += dlt < 0
        eq += dlt == 0
    say("  %-34s intact %6d -> %6d (%+5d; up/down/eq %d/%d/%d)  burnt_cells %6d -> %6d  ever %6d -> %6d  ff_cleared %4d -> %4d  burning@240 %4d -> %4d" % (
        name, e0["intact"], e1["intact"], e1["intact"] - e0["intact"], up, dn, eq,
        e0["burnt"], e1["burnt"], e0["ever"], e1["ever"], e0["ffc"], e1["ffc"], e0["burning240"], e1["burning240"]))
    return e1["intact"] > e0["intact"]


def sec_g3():
    say("")
    say("=" * 88)
    say("G3. UNTOUCHED VEGETATION AT STEP 240 (intact, depot-corrected) + burnt_cells")
    say("=" * 88)
    xbad = [(tag, label(t)) for (tag, t), S in CACHE.items() if S is not None and S["xchk"] is False]
    say("  per-run cross-check fire_cleared_unburned_final - depot_unburned == counters.cleared_unburned: %s" % (
        "ALL AGREE" if not xbad else "MISMATCH %r" % xbad))
    a = intact_block("stock U30  ugC -> ugD", "ugC", "ugD", U30)
    b = intact_block("stock C13+F10  ugC -> ugD", "ugC", "ugD", C13 + F10)
    intact_block("stock canonical 13", "ugC", "ugD", C13)
    intact_block("stock fresh 10", "ugC", "ugD", F10)
    c = intact_block("CRN U30  ugKC -> ugKD", "ugKC", "ugKD", U30)
    intact_block("stock U30 DRY  ugC -> ugY (must be 0)", "ugC", "ugY", U30)
    intact_block("CRN U30 DRY  ugKC -> ugKY (must be 0)", "ugKC", "ugKY", U30)
    say("  G3 VERDICT: %s" % ("PASS" if (a and b and c and not xbad) else "FAIL"))
    return a and b and c and not xbad


def sec_g4():
    say("")
    say("=" * 88)
    say("G4. FIREFIGHTER DEATHS - the risk metric")
    say("=" * 88)
    ok = True
    for name, tuples, pairs in (("U30 stock", U30, [("ugC", "ugD"), ("ugC", "ugY")]),
                                ("U30 CRN", U30, [("ugKC", "ugKD"), ("ugKC", "ugKY")]),
                                ("C13+F10 stock", C13 + F10, [("ugC", "ugD")])):
        for ctrl, feat in pairs:
            d0 = ev_row([S_(ctrl, t) for t in tuples])["ffd"]
            d1 = ev_row([S_(feat, t) for t in tuples])["ffd"]
            say("  %-14s %-5s %3d -> %-5s %3d" % (name, ctrl, d0, feat, d1))
            if feat in ("ugD", "ugKD") and d1 > d0:
                ok = False
    say("  every death, classified (engaged = firefighting on the death step):")
    for tag in ("ugC", "ugD", "ugY", "ugKC", "ugKD", "ugKY"):
        tuples = U30 + (C13 + F10 if tag in ("ugC", "ugD") else [])
        n = collections.Counter()
        for t in tuples:
            S = S_(tag, t)
            if S is None:
                continue
            for dd in S["deaths"]:
                n["deaths"] += 1
                for k in ("engaged", "engaged_prev", "streak_engaged", "preempted", "after_terminal"):
                    n[k] += int(bool(dd[k]))
                n["full_enclosure"] += int(dd["enclosure"] == "full")
                say("    %-5s %-18s %s step %3s cell %-9s engaged=%d prev=%d streak=%d preempted=%d after_terminal=%d %s" % (
                    tag, label(t), dd["ff"], dd["step"], dd["cell"], dd["engaged"], dd["engaged_prev"],
                    dd["streak_engaged"], dd["preempted"], dd["after_terminal"], dd["enclosure"]))
        say("  %-5s totals %s" % (tag, dict(n)))
    say("  per-tuple death changes vs control (U30):")
    for ctrl, feat in (("ugC", "ugD"), ("ugC", "ugY"), ("ugKC", "ugKD"), ("ugKC", "ugKY")):
        adds, rems = [], []
        for t in U30:
            a, b = S_(ctrl, t), S_(feat, t)
            if a is None or b is None:
                continue
            if b["ffd"] > a["ffd"]:
                adds.append("%s +%d" % (label(t), b["ffd"] - a["ffd"]))
            elif b["ffd"] < a["ffd"]:
                rems.append("%s %d" % (label(t), b["ffd"] - a["ffd"]))
        say("    %s vs %s  added: %s | removed: %s" % (feat, ctrl, ", ".join(adds) or "-", ", ".join(rems) or "-"))
    say("  G4 (no increase in ugD / ugKD): %s - if it increased, the classification above is the explanation required" % (
        "NO INCREASE" if ok else "INCREASED"))
    return ok


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def sec_exposure():
    say("")
    say("=" * 88)
    say("ITEM 5. DRONE STEPS IN FIRE (E1 searcher-only, E2 all-UAV; interior-hazard definition)")
    say("=" * 88)
    for name, tuples, arms in (("rb18 (14 C13/F10 tuples + rb4)", RB18, ("ugC", "ugD")),
                               ("canonical+fresh 23", C13 + F10, ("ugC", "ugD")),
                               ("U30 stock", U30, ("ugC", "ugD", "ugY")),
                               ("U30 CRN", U30, ("ugKC", "ugKD", "ugKY"))):
        for tag in arms:
            agg = collections.Counter()
            for t in tuples:
                S = S_(tag, t)
                if S is not None:
                    agg.update(S["exp"])
            say("  %-32s %-5s E1 %5.2f%% (%d/%d; depot %d)   E2 %5.2f%% (%d/%d; depot %d)" % (
                name, tag, pct(agg["e1n"], agg["e1d"]), agg["e1n"], agg["e1d"], agg["e1n_dep"],
                pct(agg["e2n"], agg["e2d"]), agg["e2n"], agg["e2d"], agg["e2n_dep"]))


def sec_structural():
    say("")
    say("=" * 88)
    say("G7. STRUCTURAL + ATTRIBUTION")
    say("=" * 88)
    ok = True
    for tag in ("ugC", "ugD", "ugX", "ugY", "ugKC", "ugKD", "ugKY", "ugA"):
        tot = sum((S["oob"] for (tg, t), S in CACHE.items() if tg == tag and S is not None))
        runs = sum(1 for (tg, t), S in CACHE.items() if tg == tag and S is not None)
        note = "  (guard switched OFF in this arm on purpose - not gated)" if tag == "ugA" else ""
        say("  off-grid refusals %-5s %5d over %3d runs%s" % (tag, tot, runs, note))
        if tag != "ugA" and tot:
            ok = False
    for ctrl, dry, tuples in (("ugC", "ugY", U30), ("ugKC", "ugKY", U30)):
        same = sum(1 for t in tuples if S_(ctrl, t) and S_(dry, t) and S_(ctrl, t)["digests"] == S_(dry, t)["digests"])
        say("  DRY fire == control fire 240/240: %s vs %s %d/%d" % (dry, ctrl, same, len(tuples)))
        ok = ok and same == len(tuples)
    for ctrl, wet, tuples in (("ugC", "ugD", U30 + C13 + F10 + RB4), ("ugKC", "ugKD", U30)):
        exact = nowrite_same = viol = 0
        for t in tuples:
            S = S_(wet, t)
            if S is None:
                continue
            if S["first_write"] is None:
                nowrite_same += int(S["fire_div"] is None)
                viol += int(S["fire_div"] is not None)
            else:
                exact += int(S["fire_div"] == S["first_write"])
                viol += int(S["fire_div"] != S["first_write"])
        say("  attribution %s vs %s: diverges EXACTLY at first write %d, no write & identical %d, violations %d" % (
            wet, ctrl, exact, nowrite_same, viol))
        ok = ok and viol == 0
    say("  G7 VERDICT: %s" % ("PASS" if ok else "FAIL"))
    return ok


def sec_reroll():
    say("")
    say("=" * 88)
    say("RE-ROLL STATUS per rb18 tuple (stock ugD vs ugC) - input to G5")
    say("=" * 88)
    for t in RB18:
        a, b = S_("ugC", t), S_("ugD", t)
        if a is None or b is None:
            say("  %-16s MISSING" % label(t))
            continue
        term = a["terminal"] if a["terminal"] is not None else 240
        div = b["fire_div"]
        rer = div is not None and div < term
        say("  %-16s control terminal %-4s first fire divergence %-4s -> %s   rescued %d -> %d" % (
            label(t), a["terminal"], div, "RE-ROLLED" if rer else "same fire until decided", a["rescued"], b["rescued"]))


def sec_engagement():
    say("")
    say("=" * 88)
    say("ENGAGEMENT BEFORE terminal_step, first-dispatch spacing, mechanism counters")
    say("=" * 88)
    for tag, tuples in (("ugD", C13 + F10 + RB4 + U30), ("ugKD", U30)):
        n = pre = 0
        firsts = []
        for t in tuples:
            S = S_(tag, t)
            if S is None:
                continue
            n += 1
            fe = S["first_engaged"]
            term = S["terminal"] if S["terminal"] is not None else 241
            if fe is not None and fe < term:
                pre += 1
            if fe is not None:
                firsts.append(fe)
        say("  %-5s runs %d, first engaged row strictly before terminal_step on %d; first-engaged step min/median/max %s" % (
            tag, n, pre, (min(firsts), sorted(firsts)[len(firsts) // 2], max(firsts)) if firsts else None))
    for tag, tuples in (("ugC", C13 + F10 + U30), ("ugD", C13 + F10 + U30)):
        sp = collections.Counter(S_(tag, t)["spacing"] for t in tuples if S_(tag, t) is not None)
        say("  first ok dispatch: manhattan between the two units  %-5s %s" % (tag, dict(sorted(sp.items(), key=lambda kv: (kv[0] is None, kv[0])))))
    for tag, tuples in (("ugD", C13 + F10), ("ugD", U30), ("ugKD", U30), ("ugY", U30)):
        agg = collections.Counter()
        for t in tuples:
            S = S_(tag, t)
            if S is None:
                continue
            for k in ("ext", "clear", "clear_scorched", "engaged", "after_term", "preempt", "rows", "dry"):
                agg[k] += S[k]
        say("  %-5s %-8s extinguish %4d  clear %5d (scorched %4d)  dry-suppressed %5d  engaged rows %5d (after terminal %5d)  preemptions %3d" % (
            tag, "C13+F10" if tuples is not U30 else "U30", agg["ext"], agg["clear"], agg["clear_scorched"],
            agg["dry"], agg["engaged"], agg["after_term"], agg["preempt"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "_ug_analysis.txt"))
    a = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    say("UNGATED ROUND - PART 3 ANALYSIS (outputs/_ug_analyze.py; pre-registration outputs/ungated_part1.txt s.6)")
    say("U30 seeds: %s" % ", ".join("%s/%s/%d" % t for t in U30))
    res = {}
    res["provenance"] = sec_provenance()
    res["G1"] = sec_g1()
    sec_outcomes()
    res["G2"] = sec_g2()
    res["G3"] = sec_g3()
    res["G4"] = sec_g4()
    sec_exposure()
    res["G7"] = sec_structural()
    sec_reroll()
    sec_engagement()
    say("")
    say("SUMMARY %s   (G5 route_blocked: outputs/_ug_rbgate.txt; G6 tests: _flip_pytest_names.py)" % res)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
