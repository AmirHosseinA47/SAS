"""MVG follow-up round, Part 1d (outputs/urgency_part1d.txt 1d.2): the STRANDING GUARD, frozen, and its OFFLINE
DIAGNOSTIC on the urgency screen's replayed arm-M runs. DIAGNOSTICS ONLY (maintainer ruling on report section 9):
the set-3 / set-4 deaths show what to guard against and are never the test; the guard is not adjusted on them.
This file's sha256 was recorded BEFORE it read any board (Part 1d 1d.2.6).

THE GUARD G-T (principle: a fix step never moves a unit onto a route the fire is expected to close before the unit
passes). It is U1's safe-in-time test (urgency_part1.txt 8.2-8.3) applied at the cell the fix would step to:
  At a decision where fix (a) or fix (b) would act - its pure choice n is a 4-neighbour of the unit's cell u and
  differs from today's choice - with the bound victim's current cell v, the true burning set B, the active-smoke
  set S and the wind:
    T       = fire_arrival_estimate.arrival_time(W, H, B, wind, FrontPriorityParams())   (U1: the published-rate
              estimate, defaults, never the SEARCHER_FP_* knobs - ruling U-6)
    unclean = urgency_dispatch.unclean_cells(B, S, W, H)      (burning, smoky, or 4-adjacent to a burning cell)
    T*(x)   = urgency_dispatch.t_star(T, x, W, H)             (min of T over x and its in-grid 4-neighbours)
    c_n     = the earliest hop at which v is entered on a TIME-EXPANDED CLEAN route that starts u -> n:
              n is entered at hop 1 iff n is clean now and T*(n) > 1; afterwards a cell x is entered at hop k iff x
              is clean now and T*(x) > k (8.2); u itself is not re-entered. c_n = infinity if v is never entered.
    ADMIT(n) iff c_n is finite AND c_n + 1 <= T(v)            (8.3's test; "+1" is the pickup step, as M8 / U1)
  Admitted: the fix's step runs. Not admitted (VETO): the fix does not act at this decision, and TODAY's step runs
  verbatim - today's mover for (a), today's survival retreat (with its state writes) for (b).
  No constant is introduced: T is the frozen published-rate estimator, the hop clock is the units' one cell per step,
  "+1" is U1's pickup step.
VARIANT G-W (offered as a ruling, not recommended): the same test with wind = None, i.e. FAE's isotropic estimate at
  the head rate R_H in every direction (fire_arrival_estimate.arrival_time sets e = 0 without a wind). Equally
  parameter-free; stricter wherever the wind slows the estimate (the flanks and upwind).

THE DIAGNOSTIC (fixed with the guard, before any board was read). For every replay record with boards (R0 runs:
the arm-M run line reproduced exactly, _ud_replay.py with no knockout), every LIVE fix event (d["mv_events"], kind a
or b): u = the event's pre cell (the mv row), n = the cell taken, v = the mv row's target, the board = the unit's
decision board at that step. Printed per event: step, unit, kind, u, n, v, D(n) (clean BFS), c_n and T(v) under G-T
and G-W, and the verdicts; per dying unit (outputs/_ud_replay/_ud_rp_deaths.json) its fix events with the verdicts;
per run, the footprint (live events, G-T vetoes, G-W vetoes).

usage: _mvg_guard_diag.py <replay dir> [--json <out>]
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(HERE)
sys.path.insert(0, WT)
from src_extension.planning.fire_arrival_estimate import FrontPriorityParams, arrival_time  # noqa: E402
from src_extension.planning.urgency_dispatch import safe_route_hops, t_star, unclean_cells  # noqa: E402

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def guard(u, n, v, burning, smoky, wind, w, h):
    """(admit, c_n, T(v)) - G-T with `wind` (a vector) or G-W with wind None."""
    u, n, v = tuple(u), tuple(n), tuple(v)
    T = arrival_time(w, h, list(burning), wind, FrontPriorityParams())
    unclean = unclean_cells(burning, smoky, w, h)
    t_v = float(T[v[0], v[1]])
    if n in unclean or not t_star(T, n, w, h) > 1:
        return False, None, t_v
    hops = safe_route_hops(n, w, h, unclean | {u}, lambda x: t_star(T, x, w, h) - 1)
    if v not in hops:
        return False, None, t_v
    c_n = 1 + hops[v]
    return (c_n + 1) <= t_v, c_n, t_v


def clean_dist(src, dst, burning, smoky, w, h):
    unclean = unclean_cells(burning, smoky, w, h)
    src, dst = tuple(src), tuple(dst)
    if dst in unclean:
        return None
    seen = {src: 0}
    q = deque([src])
    while q:
        c = q.popleft()
        if c == dst:
            return seen[c]
        for ox, oy in N4:
            x = (c[0] + ox, c[1] + oy)
            if x in seen or not (0 <= x[0] < w and 0 <= x[1] < h) or x in unclean:
                continue
            seen[x] = seen[c] + 1
            q.append(x)
    return None


def fmt(x):
    if x is None:
        return "inf"
    if isinstance(x, float):
        return "inf" if math.isinf(x) else "%.1f" % x
    return str(x)


def main():
    rdir = sys.argv[1]
    out_json = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    with open(os.path.join(rdir, "_ud_rp_deaths.json"), encoding="utf-8") as fh:
        deaths = json.load(fh)
    result = {}
    for bpath in sorted(glob.glob(os.path.join(rdir, "_bd_udrp_*_R0.json"))):
        name = os.path.basename(bpath)[len("_bd_"):-len(".json")]
        run = name[len("udrp_"):-len("_R0")]
        with open(bpath, encoding="utf-8") as fh:
            bd = json.load(fh)
        with open(os.path.join(rdir, "_sd_%s.json" % name), encoding="utf-8") as fh:
            d = json.load(fh)
        w, h = bd["grid"]
        wind = bd["wind"]["vector"]
        dec = {(s, uid): dig for s, uid, _p, _t, _st, _ex, dig in bd["decisions"]}
        cols = d["mv"]["cols"]
        mv = {}
        for r in d["mv"]["rows"]:
            row = dict(zip(cols, r))
            mv[(row["step"], row["unit"])] = row
        evs = []
        for e in d.get("mv_events") or []:
            if not e.get("live") or e.get("kind") not in ("a", "b"):
                continue
            row = mv.get((e["step"], e["unit"]))
            dig = dec.get((e["step"], e["unit"]))
            if row is None or dig is None:
                evs.append({"step": e["step"], "unit": e["unit"], "kind": e["kind"], "error": "no mv row / board"})
                continue
            b = bd["boards"][dig]
            burning = {tuple(c) for c in b["burning"]}
            smoky = {tuple(c) for c in b["smoky"]}
            u, n, v = row["pre"], e["taken"], row["target"]
            gt = guard(u, n, v, burning, smoky, tuple(wind) if wind else None, w, h)
            gw = guard(u, n, v, burning, smoky, None, w, h)
            evs.append({"step": e["step"], "unit": e["unit"], "kind": e["kind"], "u": u, "n": n, "v": v,
                        "D_n": clean_dist(n, v, burning, smoky, w, h),
                        "GT": {"admit": gt[0], "c": gt[1], "T_v": gt[2]},
                        "GW": {"admit": gw[0], "c": gw[1], "T_v": gw[2]}})
        result[run] = evs
        print("=" * 100)
        n_live = len(evs)
        n_vt = sum(1 for x in evs if "GT" in x and not x["GT"]["admit"])
        n_vw = sum(1 for x in evs if "GW" in x and not x["GW"]["admit"])
        print("%s: live (a)/(b) events %d | G-T vetoes %d | G-W vetoes %d | wind %s" % (run, n_live, n_vt, n_vw,
                                                                                       bd["wind"]))
        for dd in deaths:
            if dd["run"] != run:
                continue
            mine = [x for x in evs if x["unit"] == dd["unit"]]
            print("  DYING UNIT %s (death %d): %d own live fix events" % (dd["unit"], dd["death"], len(mine)))
            for x in mine:
                if "error" in x:
                    print("    step %d %s ERROR %s" % (x["step"], x["kind"], x["error"]))
                    continue
                print("    step %-4d %s u %s -> n %s  v %s  D(n) %s | G-T c %s T(v) %s %s | G-W c %s T(v) %s %s" % (
                    x["step"], x["kind"], x["u"], x["n"], x["v"], fmt(x["D_n"]), fmt(x["GT"]["c"]),
                    fmt(x["GT"]["T_v"]), "ADMIT" if x["GT"]["admit"] else "VETO", fmt(x["GW"]["c"]),
                    fmt(x["GW"]["T_v"]), "ADMIT" if x["GW"]["admit"] else "VETO"))
        others = [x for x in evs if "GT" in x and not x["GT"]["admit"] and
                  not any(dd["run"] == run and dd["unit"] == x["unit"] for dd in deaths)]
        if others:
            print("  G-T vetoes of other units' events:", [(x["step"], x["unit"], x["kind"]) for x in others])
    if out_json:
        with open(out_json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(result, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
