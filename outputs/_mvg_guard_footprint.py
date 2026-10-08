"""MVG Part 1d 1d.2.6: the FOOTPRINT of the frozen guard on the urgency screen's arm-M runs (in-sample, descriptive;
the guard is never adjusted on it). It imports guard() from outputs/_mvg_guard_diag.py UNCHANGED (sha256 recorded
before any board was read) and evaluates it on every LIVE (a) / (b) event of every replayed arm-M run
(outputs/_ud_replay/_bd_udrp_ud2*_R0.json: the 8 runs of the death review and the 36 footprint runs = all 43 cells
where a fix acted, with ud2u3_D_N counted once; the MU run ud3u3_D_N is excluded here).

Reported, per set and pooled:
  - live events, G-T vetoes, G-W vetoes; cells with >= 1 G-T veto;
  - per LEG (unit, bound victim, from bind to unbind), the leg's outcome in arm M (pickup -> rescued / the victim
    died / unassigned route_blocked / the unit died / other) against whether the leg had a G-T veto, so the reader
    can see which kinds of legs the guard would have touched. Computed on M's trajectory: in an arm with the guard
    every vetoed step changes the rest of the run, so these are descriptive counts, not predictions.
usage: _mvg_guard_footprint.py [--json <out>]
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _mvg_guard_diag as G  # noqa: E402  (frozen; imported, not copied)

RD = os.path.join(HERE, "_ud_replay")


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def legs_of(d):
    """[(unit, victim, first step, last step, outcome)] from rows_ff + commands."""
    out = []
    cur = {}
    rows = d["rows_ff"]
    cmds = (d.get("dp") or {}).get("commands") or []
    for t, row in enumerate(rows, start=1):
        for r in row:
            u, v, dead, exiting = r[0], r[8], r[6], r[5]
            if u in cur and (v != cur[u][1] or dead):
                out.append((u, cur[u][1], cur[u][0], t - 1, cur[u][2], dead))
                del cur[u]
            if v and not dead and u not in cur:
                cur[u] = [t, v, False]
            if u in cur and exiting:
                cur[u][2] = True
    for u, (t0, v, pk) in cur.items():
        out.append((u, v, t0, len(rows), pk, False))
    vdead = {}
    for t, row in enumerate(d["rows_vic"], start=1):
        for r in row:
            if r[4] == "dead" and r[0] not in vdead:
                vdead[r[0]] = t
    res = []
    for u, v, t0, t1, picked, udead in out:
        unassign = [c for c in cmds if c[2] == "unassign" and c[4] == u and c[3] == v and t0 <= c[0] <= t1 + 1]
        if picked:
            outcome = "picked-up"
        elif udead:
            outcome = "unit-died"
        elif v in vdead and vdead[v] <= t1 + 1:
            outcome = "victim-died"
        elif any("blocked" in str(c[5]) for c in unassign):
            outcome = "route_blocked-unassign"
        else:
            outcome = "other:" + (str(unassign[-1][5]) if unassign else "run-end")
        res.append({"unit": u, "victim": v, "t0": t0, "t1": t1, "outcome": outcome})
    return res


def main():
    rows = []
    per_cell = []
    leg_tab = collections.Counter()
    for bpath in sorted(glob.glob(os.path.join(RD, "_bd_udrp_ud2*_R0.json"))):
        name = os.path.basename(bpath)[len("_bd_"):-len(".json")]
        run = name[len("udrp_"):-len("_R0")]
        k = run[4]
        sset = "set%s" % k
        bd = load(bpath)
        d = load(os.path.join(RD, "_sd_%s.json" % name))
        w, h = bd["grid"]
        wind = tuple(bd["wind"]["vector"]) if bd["wind"]["vector"] else None
        dec = {(s, uid): dig for s, uid, _p, _t, _st, _ex, dig in bd["decisions"]}
        cols = d["mv"]["cols"]
        mv = {}
        for r in d["mv"]["rows"]:
            row = dict(zip(cols, r))
            mv[(row["step"], row["unit"])] = row
        legs = legs_of(d)
        n = vt = vw = 0
        leg_veto = collections.defaultdict(bool)
        for e in d.get("mv_events") or []:
            if not e.get("live") or e.get("kind") not in ("a", "b"):
                continue
            row = mv.get((e["step"], e["unit"]))
            dig = dec.get((e["step"], e["unit"]))
            if row is None or dig is None:
                continue
            b = bd["boards"][dig]
            burning = {tuple(c) for c in b["burning"]}
            smoky = {tuple(c) for c in b["smoky"]}
            gt = G.guard(row["pre"], e["taken"], row["target"], burning, smoky, wind, w, h)
            gw = G.guard(row["pre"], e["taken"], row["target"], burning, smoky, None, w, h)
            n += 1
            vt += not gt[0]
            vw += not gw[0]
            rows.append({"run": run, "set": sset, "step": e["step"], "unit": e["unit"], "kind": e["kind"],
                         "GT": gt[0], "GW": gw[0]})
            if not gt[0]:
                for lg in legs:
                    if lg["unit"] == e["unit"] and lg["t0"] <= e["step"] <= lg["t1"] + 1:
                        leg_veto[(lg["unit"], lg["t0"])] = True
        fix_legs = []
        for lg in legs:
            has_fix = any(r["run"] == run and r["unit"] == lg["unit"] and lg["t0"] <= r["step"] <= lg["t1"] + 1
                          for r in rows)
            if not has_fix:
                continue
            vetoed = leg_veto[(lg["unit"], lg["t0"])]
            leg_tab[(sset, "vetoed" if vetoed else "admitted-only", lg["outcome"])] += 1
            fix_legs.append(dict(lg, vetoed=vetoed))
        per_cell.append({"run": run, "set": sset, "events": n, "GT_vetoes": vt, "GW_vetoes": vw, "legs": fix_legs})
    print("GUARD FOOTPRINT on arm M's replayed runs (in-sample; descriptive)")
    for s in ("set3", "set4", "all"):
        cs = [c for c in per_cell if s == "all" or c["set"] == s]
        ev = sum(c["events"] for c in cs)
        vt = sum(c["GT_vetoes"] for c in cs)
        vw = sum(c["GW_vetoes"] for c in cs)
        cv = sum(1 for c in cs if c["GT_vetoes"])
        print("  %-4s runs %2d | live (a)/(b) events %4d | G-T vetoes %4d (%.0f %%) | G-W vetoes %4d (%.0f %%) | "
              "runs with >= 1 G-T veto %d" % (s, len(cs), ev, vt, 100.0 * vt / max(ev, 1), vw, 100.0 * vw / max(ev, 1), cv))
    by_kind = collections.Counter((r["kind"], r["GT"]) for r in rows)
    print("  by fix: (a) %d events, %d vetoed | (b) %d events, %d vetoed" % (
        by_kind[("a", True)] + by_kind[("a", False)], by_kind[("a", False)],
        by_kind[("b", True)] + by_kind[("b", False)], by_kind[("b", False)]))
    print("LEGS with >= 1 live fix event, by G-T veto and the leg's outcome in arm M:")
    for s in ("set3", "set4"):
        for vv in ("vetoed", "admitted-only"):
            items = {o: c for (ss, v, o), c in leg_tab.items() if ss == s and v == vv}
            print("  %s %-13s %s" % (s, vv, dict(sorted(items.items()))))
    print("PER RUN: events / G-T vetoes / G-W vetoes")
    print("  " + ", ".join("%s %d/%d/%d" % (c["run"], c["events"], c["GT_vetoes"], c["GW_vetoes"]) for c in per_cell))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"per_cell": per_cell, "events": rows}, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
