#!/usr/bin/env python
"""Depot-cost round: the route_blocked sample read as the round's THIRD SAMPLE.

outputs/_ffr_rbcompare.py answers the GATE (rescued must not regress, units must
not stay latched) and reports rescued / dead / ff_deaths / terminal. It does not
report never_detected, which is this round's target metric - so on its own it
cannot answer the round's own gate on the 18-seed sample.

The shard JSONs do carry never_detected per seed (and every other mission metric),
so this reads them directly and reports the same metric set the harness arms are
reported with, seed-matched against the e703861 reference. It does NOT replace
_ffr_rbcompare.py; both are run, and the report carries both.

  python outputs/_dc_rbread.py --new dcrbA --old rbc
  python outputs/_dc_rbread.py --arms dcrbA,dcrbB,dcrbC,dcrbD --old rbc

Read-only. Runs no simulation.
"""
from __future__ import annotations

import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# The four shards every round in this chain uses, so the seed set is identical
# and _ir_rbmerge.py's own verification applies unchanged.
SHARDS = ("a", "b", "c", "s")
METRICS = ("rescued", "dead", "never_detected", "unreachable",
           "geographically_isolated", "horizon_unresolved", "candidate",
           "firefighter_deaths", "burnt_cells")


def load_arm(prefix):
    """{(wind, seed): eval} over the four shards of one arm."""
    out = {}
    for sh in SHARDS:
        for p in glob.glob(os.path.join(HERE, "_rblatch_camp2_%s%s_D_*.json" % (prefix, sh))):
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            wind = str(d.get("wind"))
            for e in (d.get("evals") or []):
                out[(wind, int(e["seed"]))] = e
    return out


def totals(arm, keys):
    return {m: sum(int(arm[k].get(m) or 0) for k in keys) for m in METRICS}


def report(new_prefix, old_prefix):
    new, old = load_arm(new_prefix), load_arm(old_prefix)
    keys = sorted(set(new) & set(old))
    only_new, only_old = sorted(set(new) - set(old)), sorted(set(old) - set(new))
    print("RBGATE SAMPLE  %s vs %s" % (new_prefix, old_prefix))
    print("  seed-matched runs: %d   (only in %s: %d, only in %s: %d)"
          % (len(keys), new_prefix, len(only_new), old_prefix, len(only_old)))
    if not keys:
        print("  NOTHING TO COMPARE - shards missing")
        return None
    tn, to = totals(new, keys), totals(old, keys)
    print("  %-24s %8s %8s %8s" % ("metric", old_prefix, new_prefix, "delta"))
    for m in METRICS:
        print("  %-24s %8d %8d %+8d" % (m, to[m], tn[m], tn[m] - to[m]))
    # Per-seed movement on the two metrics the gate is written on, so a total that
    # nets out is not mistaken for nothing happening.
    moved = [(k, old[k].get("rescued"), new[k].get("rescued"),
              old[k].get("never_detected"), new[k].get("never_detected"))
             for k in keys
             if old[k].get("rescued") != new[k].get("rescued")
             or old[k].get("never_detected") != new[k].get("never_detected")]
    if moved:
        print("  seeds that moved on rescued or never_detected: %d of %d"
              % (len(moved), len(keys)))
        for k, ro, rn, no, nn in moved:
            print("     %-6s %-5s  rescued %d -> %d   never_detected %d -> %d"
                  % (k[0], k[1], ro, rn, no, nn))
    else:
        print("  no seed moved on rescued or never_detected")
    return tn, to, len(keys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new")
    ap.add_argument("--arms", help="comma-separated prefixes, reported in order")
    ap.add_argument("--old", default="rbc")
    a = ap.parse_args()
    arms = a.arms.split(",") if a.arms else ([a.new] if a.new else [])
    if not arms:
        raise SystemExit("give --new or --arms")
    for i, arm in enumerate(arms):
        if i:
            print()
        report(arm, a.old)


if __name__ == "__main__":
    main()
