"""Provenance control: the arm-none probe must reproduce c4d5a25's
committed per-step data exactly.

Compares outputs/_dr_none_<cell>.json against the last_cell round's
post-fix data outputs/_lc_post_<cell>.json on the full firefighter trace
(step, unit, cell, dead, status, assigned, target, exiting, mfd, n_free),
on the exact (step, unit, cell) of every death, and on the run outcomes.
This is the same provenance check every round in this chain has run.

    python outputs/_dr_prov.py [--arm none] [--ref _lc_post]
"""
from __future__ import annotations
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS = ["east_default_101", "east_default_202", "east_default_303",
         "east_half_101", "east_half_202", "east_half_303",
         "east_half_404", "east_half_505",
         "south_half_101", "south_half_202", "south_half_303",
         "south_half_404", "south_half_505",
         "east_half_606", "east_half_707", "east_half_808",
         "east_half_909", "east_half_1010",
         "south_half_606", "south_half_707", "south_half_808",
         "south_half_909", "south_half_1010"]
K = ("step", "ff", "pos", "dead", "status", "assigned", "target",
     "exiting", "mfd", "n_free")


def key(rows):
    return [tuple(str(r.get(k)) for k in K) for r in rows]


def ev(d):
    e = d["evals"][0]
    return (int(e.get("rescued", 0) or 0), int(e.get("dead", 0) or 0), len(d["deaths"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="none")
    ap.add_argument("--prefix", default="_dr")
    ap.add_argument("--ref", default="_lc_post")
    a = ap.parse_args()
    ok = miss = bad = 0
    print("%-20s %-14s %-14s %-9s %s" % ("cell", "probe", "c4d5a25", "outcomes", "trace"))
    for c in CELLS:
        p1 = os.path.join(HERE, "%s_%s_%s.json" % (a.prefix, a.arm, c))
        p2 = os.path.join(HERE, "%s_%s.json" % (a.ref, c))
        if not (os.path.exists(p1) and os.path.getsize(p1) > 0):
            print("%-20s MISSING probe" % c); miss += 1; continue
        if not (os.path.exists(p2) and os.path.getsize(p2) > 0):
            print("%-20s MISSING ref" % c); miss += 1; continue
        d1 = json.load(open(p1)); d2 = json.load(open(p2))
        e1, e2 = ev(d1), ev(d2)
        t1, t2 = key(d1["fftrace"]), key(d2["fftrace"])
        dd1 = sorted((x["step"], x["ff"], str(x["pos"])) for x in d1["deaths"])
        dd2 = sorted((x["step"], x["ff"], str(x["pos"])) for x in d2["deaths"])
        same = (t1 == t2) and (dd1 == dd2) and (e1 == e2)
        tag = "IDENTICAL" if same else "*** DIFFERS ***"
        print("%-20s r%d/d%d/ff%-5d r%d/d%d/ff%-5d %-9s %s"
              % (c, e1[0], e1[1], e1[2], e2[0], e2[1], e2[2],
                 "same" if e1 == e2 else "DIFF", tag))
        if same:
            ok += 1
        else:
            bad += 1
            for x, y in zip(t1, t2):
                if x != y:
                    print("     first trace diff:\n       probe   %s\n       c4d5a25 %s" % (x, y))
                    break
            if len(t1) != len(t2):
                print("     trace lengths %d vs %d" % (len(t1), len(t2)))
            if dd1 != dd2:
                print("     deaths probe=%s\n            ref  =%s" % (dd1, dd2))
    print()
    print("IDENTICAL %d / %d   differs %d   missing %d" % (ok, ok + bad, bad, miss))
    return 0 if bad == 0 else 1


sys.exit(main())
