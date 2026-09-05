"""route_blocked gate, THIS round's delta: ffabs (feature 1) vs rhfix (2acfb54,
behaviourally identical to 1511ada per outputs/recoveryhysteresis_report.txt).

`_ir_rbmerge.py --prefix ffabs` answers the gate as originally defined, against
the 70e1b33 baseline. This script answers the question this round needs: did
the rescue-absence feature move anything relative to the head it was branched
from, seed for seed, and are the route_blocked mechanics still alive?

usage: _ffr_rbcompare.py [--new ffabs] [--old rhfix]
Read-only.
"""
from __future__ import annotations
import argparse, collections, glob, json, os

BASE = os.path.dirname(os.path.abspath(__file__))


def merge(paths):
    out = {"evals": [], "stats": collections.Counter(), "exact": collections.Counter(),
           "exact_fires": [], "exact_recoveries": [], "fires": [], "recoveries": [],
           "assigns": [], "latched": [], "deaths": [], "shards": []}
    for p in sorted(paths):
        with open(p) as f:
            d = json.load(f)
        out["shards"].append((os.path.basename(p), d["seeds"]))
        out["evals"].extend(d.get("evals") or [])
        out["stats"].update(d.get("stats") or {})
        out["exact"].update(d.get("exact") or {})
        for k in ("exact_fires", "exact_recoveries", "fires", "recoveries", "assigns", "latched", "deaths"):
            out[k].extend(d.get(k) or [])
    return out


def by_seed(evals):
    return {int(e["seed"]): (int(e.get("rescued") or 0), int(e.get("dead") or 0),
                             int(e.get("firefighter_deaths") or 0), e.get("terminal_step"))
            for e in evals}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", default="ffabs")
    ap.add_argument("--old", default="rhfix")
    a = ap.parse_args()
    grand_old = [0, 0, 0]
    grand_new = [0, 0, 0]
    regressions, changed = [], []
    ex_old, ex_new = collections.Counter(), collections.Counter()
    latched_new = []
    for wind in ("east", "south"):
        old = merge(glob.glob(os.path.join(BASE, "_rblatch_camp2_%s*_D_%s.json" % (a.old, wind))))
        new = glob.glob(os.path.join(BASE, "_rblatch_camp2_%s*_D_%s.json" % (a.new, wind)))
        if not new:
            print("D/%s: no %s shards yet" % (wind, a.new))
            continue
        new = merge(new)
        o, n = by_seed(old["evals"]), by_seed(new["evals"])
        seeds = sorted(o)
        if sorted(n) != seeds:
            print("  !! SEED SET MISMATCH D/%s: new=%s old=%s" % (wind, sorted(n), seeds))
        print("=" * 78)
        print("D/%s   %s (== 1511ada behaviour)  ->  %s (feature 1)" % (wind, a.old, a.new))
        print("=" * 78)
        print("  seed |  rescued      | victims dead  | ff_deaths     | terminal")
        for s in seeds:
            eo, en = o.get(s), n.get(s)
            if eo is None or en is None:
                print("  %-5s MISSING" % s)
                continue
            for i in range(3):
                grand_old[i] += eo[i]
                grand_new[i] += en[i]
            if en[0] < eo[0]:
                regressions.append((wind, s, eo[0], en[0]))
            mark = "  <-- changed" if eo[:3] != en[:3] else ""
            if mark:
                changed.append((wind, s, eo, en))

            def cell(x, y):
                d = y - x
                return "%2d -> %2d%-6s" % (x, y, (" (%+d)" % d) if d else "")
            print("  %-5s %s| %s| %s| %s -> %s%s" % (
                s, cell(eo[0], en[0]), cell(eo[1], en[1]), cell(eo[2], en[2]),
                eo[3] if eo[3] is not None else "-", en[3] if en[3] is not None else "-", mark))
        print("  route_blocked mechanics (exact hooks):")
        for k in ("fires", "recoveries", "reval_calls", "reval_calls_with_blocked_unit"):
            print("    %-32s %6s -> %6s" % (k, old["exact"].get(k, 0), new["exact"].get(k, 0)))
        print("    %-32s %6s -> %6s" % ("end-of-run units still blocked", len(old["latched"]), len(new["latched"])))
        print("    %-32s %6s -> %6s" % ("assign into blocked route", old["stats"].get("assign_into_blocked_route", 0),
                                         new["stats"].get("assign_into_blocked_route", 0)))
        ex_old.update(old["exact"])
        ex_new.update(new["exact"])
        latched_new.extend(new["latched"])
        print()
    print("=" * 78)
    print("ALL RUNS   rescued %d -> %d (%+d)   victims dead %d -> %d (%+d)   ff_deaths %d -> %d (%+d)" % (
        grand_old[0], grand_new[0], grand_new[0] - grand_old[0], grand_old[1], grand_new[1], grand_new[1] - grand_old[1],
        grand_old[2], grand_new[2], grand_new[2] - grand_old[2]))
    print("  [%s] rescued does not decrease on any seed vs %s" % ("PASS" if not regressions else "FAIL", a.old))
    for r in regressions:
        print("        regression: D/%s seed %s  rescued %d -> %d" % r)
    print("  [%s] recovery pass still recovers units (recoveries %d -> %d, firings %d -> %d)" % (
        "PASS" if ex_new.get("recoveries", 0) > 0 else "CHECK", ex_old.get("recoveries", 0), ex_new.get("recoveries", 0),
        ex_old.get("fires", 0), ex_new.get("fires", 0)))
    print("  [%s] no unit left latched as route_blocked at end of run" % ("PASS" if not latched_new else "FAIL"))
    for l in latched_new:
        print("        still blocked: %s" % l)
    print("  seeds changed on (rescued, dead, ff_deaths): %d" % len(changed))
    for wind, s, eo, en in changed:
        print("        D/%s %s: rescued %d->%d dead %d->%d ff_deaths %d->%d" % (wind, s, eo[0], en[0], eo[1], en[1], eo[2], en[2]))


main()
