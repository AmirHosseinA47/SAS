"""Seed-matched arm comparison for the dispatch-reachability round.

    python outputs/_dr_arms.py [--arms none,a,b,bt]

Prints, per cell and per group, rescued / victims-dead / firefighter-deaths
for every arm, flags which cells are trajectory-identical to arm none, and
calls out D/east 505 - the rescue c4d5a25's gate flagged as lost.
"""
from __future__ import annotations
import argparse, collections, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS13 = ["east_default_101", "east_default_202", "east_default_303",
           "east_half_101", "east_half_202", "east_half_303",
           "east_half_404", "east_half_505",
           "south_half_101", "south_half_202", "south_half_303",
           "south_half_404", "south_half_505"]
CELLSF = ["east_half_606", "east_half_707", "east_half_808",
          "east_half_909", "east_half_1010",
          "south_half_606", "south_half_707", "south_half_808",
          "south_half_909", "south_half_1010"]
K = ("step", "ff", "pos", "dead", "status", "assigned", "target",
     "exiting", "mfd", "n_free")


def path(arm, cell):
    return os.path.join(HERE, "_dr_%s_%s.json" % (arm, cell))


def load(arm, cell):
    p = path(arm, cell)
    if not (os.path.exists(p) and os.path.getsize(p) > 0):
        return None
    return json.load(open(p))


def ev(d):
    e = d["evals"][0]
    return (int(e.get("rescued", 0) or 0), int(e.get("dead", 0) or 0), len(d["deaths"]))


def trace(d):
    return [tuple(str(r.get(k)) for k in K) for r in d["fftrace"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="none,a,b")
    a = ap.parse_args()
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]

    for grp, cells in (("13-RUN SEED-MATCHED SAMPLE", CELLS13),
                       ("10 FRESH SEEDS", CELLSF)):
        print("=" * 78)
        print(grp)
        print("=" * 78)
        hdr = "%-20s" % "cell"
        for arm in arms:
            hdr += " %-14s" % ("arm " + arm)
        hdr += "  diverges-from-none"
        print(hdr)
        tot = {arm: [0, 0, 0] for arm in arms}
        n = 0
        for c in cells:
            ds = {arm: load(arm, c) for arm in arms}
            if any(v is None for v in ds.values()):
                print("%-20s  (incomplete: %s)"
                      % (c, ",".join(k for k, v in ds.items() if v is None)))
                continue
            n += 1
            line = "%-20s" % c
            for arm in arms:
                e = ev(ds[arm])
                for i in range(3):
                    tot[arm][i] += e[i]
                line += " r%d/d%d/ff%-6d" % e
            base = trace(ds["none"]) if "none" in ds else None
            div = [arm for arm in arms
                   if arm != "none" and base is not None and trace(ds[arm]) != base]
            line += "  " + (",".join(div) if div else "-")
            print(line)
        line = "%-20s" % ("TOTAL (%d cells)" % n)
        for arm in arms:
            line += " r%d/d%d/ff%-6d" % tuple(tot[arm])
        print(line)
        print()

    # pooled
    print("=" * 78)
    print("POOLED, 23 RUNS")
    print("=" * 78)
    tot = {arm: [0, 0, 0] for arm in arms}
    n = 0
    for c in CELLS13 + CELLSF:
        ds = {arm: load(arm, c) for arm in arms}
        if any(v is None for v in ds.values()):
            continue
        n += 1
        for arm in arms:
            e = ev(ds[arm])
            for i in range(3):
                tot[arm][i] += e[i]
    for arm in arms:
        print("  arm %-5s  rescued %-4d victims dead %-4d firefighter_deaths %-4d   (%d cells)"
              % (arm, tot[arm][0], tot[arm][1], tot[arm][2], n))
    print()

    # the gate item
    print("=" * 78)
    print("D/EAST 505 - THE RESCUE c4d5a25's GATE FLAGGED AS LOST")
    print("=" * 78)
    for arm in arms:
        d = load(arm, "east_half_505")
        if d is None:
            print("  arm %-5s  (missing)" % arm)
            continue
        e = ev(d)
        print("  arm %-5s  rescued %d  victims dead %d  ff deaths %d" % (arm, e[0], e[1], e[2]))
        for r in d["dispatch"]:
            if r["step"] < 90 or r["step"] > 110:
                continue
            print("      step %3d victim %s  stock=%s arm=%s changed=%s"
                  % (r["step"], r["victim"], r["stock_ff"], r["arm_ff"], r["arm_changed"]))
            for c in r["cands"]:
                print("          %-12s pos=%-10s man=%3d reach=%s"
                      % (c["ff"], c["pos"], c["man"], c["reach"]))
    print()

    # where each arm actually acted
    print("=" * 78)
    print("EVERY DISPATCH WHERE AN ARM CHANGED THE CHOICE")
    print("=" * 78)
    for arm in arms:
        if arm == "none":
            continue
        hits = []
        for c in CELLS13 + CELLSF:
            d = load(arm, c)
            if d is None:
                continue
            for r in d["dispatch"]:
                if r.get("arm_changed"):
                    hits.append((c, r))
        print("  arm %s: %d changed dispatches" % (arm, len(hits)))
        for c, r in hits:
            print("    %-20s step %3d victim %-9s %s -> %s  (action %s, pool %d)"
                  % (c, r["step"], r["victim"], r["stock_ff"],
                     r["arm_ff"] or "NONE", r.get("arm_action", "assign"), r["n_cand"]))
            for cd in r["cands"]:
                print("        %-12s pos=%-10s man=%3d reach=%s"
                      % (cd["ff"], cd["pos"], cd["man"], cd["reach"]))
        # empty-pool branch accounting for the hard filter
        if arm == "a":
            forced = []
            for c in CELLS13 + CELLSF:
                d = load(arm, c)
                if d is None:
                    continue
                forced.extend((c, x) for x in d["noff"] if x.get("forced"))
            print("  arm a: empty-pool branch reached %d times" % len(forced))
            for c, x in forced:
                print("    %-20s step %3d victim %-9s -> %s (reason %s, pool was %d)"
                      % (c, x["step"], x["victim"], x["action"], x["reason"], x["n_cand"]))
    print()


main()
