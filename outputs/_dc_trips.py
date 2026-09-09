#!/usr/bin/env python
"""Depot-cost round, Part 1 evidence: what the RECORDED return trips actually cost.

Reads the base-station round's arm JSONs (rtb_log, one record per trip) and
reports, per arm, the realised return leg against its Manhattan distance. This is
the empirical basis for the distance-based margin: the margin has to cover
whatever the realised path costs OVER the Manhattan lower bound, and that
overhead is measured here rather than assumed.

Read-only. Touches no model code and runs no simulation.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))

CANON = [
    ("east", "half", s) for s in (101, 202, 303, 404, 505)
] + [
    ("east", "def", s) for s in (101, 202, 303)
] + [
    ("south", "half", s) for s in (101, 202, 303, 404, 505)
]
FRESH = [("east", "half", s) for s in (606, 707, 808, 909, 1010)] + [
    ("south", "half", s) for s in (606, 707, 808, 909, 1010)
]


def load(tag, wind, roles, seed):
    p = os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, roles, seed))
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def trips_for(tag, sample):
    rows = []
    for wind, roles, seed in sample:
        d = load(tag, wind, roles, seed)
        if d is None:
            continue
        log = d.get("rtb_log") or {}
        for uid, trips in sorted(log.items()):
            for t in trips:
                rows.append({
                    "tag": tag, "wind": wind, "roles": roles, "seed": seed,
                    "uid": uid,
                    "trigger_step": t.get("trigger_step"),
                    "trigger_level": t.get("trigger_level"),
                    "d": t.get("trigger_distance"),
                    "arrival_step": t.get("arrival_step"),
                    "arrival_level": t.get("arrival_level"),
                    "dock_cell": t.get("dock_cell"),
                })
    return rows


def summarise(rows, label):
    done = [r for r in rows if r["arrival_step"] is not None]
    print("  %-9s trips %3d  arrived %3d  en-route %d"
          % (label, len(rows), len(done), len(rows) - len(done)))
    if not done:
        return None
    dur = [r["arrival_step"] - r["trigger_step"] for r in done]
    dist = [r["d"] for r in done]
    spent = [r["trigger_level"] - r["arrival_level"] for r in done]
    # Realised battery cost per unit of Manhattan distance. The floor is 0.3
    # (0.1 idle + 0.2 move) when every step moves and the path is exactly d.
    per_cell = [s / dd for s, dd in zip(spent, dist) if dd > 0]
    # Step overhead: realised steps minus the Manhattan lower bound.
    over_steps = [u - dd for u, dd in zip(dur, dist)]
    # Battery overhead against the design's own 0.3*d prediction.
    over_batt = [s - 0.3 * dd for s, dd in zip(spent, dist)]
    print("      distance   mean %6.2f  max %3d" % (statistics.mean(dist), max(dist)))
    print("      duration   mean %6.2f  max %3d" % (statistics.mean(dur), max(dur)))
    print("      spent      mean %6.2f  max %6.2f" % (statistics.mean(spent), max(spent)))
    print("      spent/cell mean %6.4f  max %6.4f  min %6.4f"
          % (statistics.mean(per_cell), max(per_cell), min(per_cell)))
    print("      steps-d    mean %6.2f  max %3d  min %3d  p95 %5.1f"
          % (statistics.mean(over_steps), max(over_steps), min(over_steps),
             sorted(over_steps)[int(0.95 * (len(over_steps) - 1))]))
    print("      batt-0.3d  mean %6.2f  max %6.2f  min %6.2f  p95 %5.2f"
          % (statistics.mean(over_batt), max(over_batt), min(over_batt),
             sorted(over_batt)[int(0.95 * (len(over_batt) - 1))]))
    return {
        "over_steps": over_steps, "over_batt": over_batt,
        "dur": dur, "dist": dist, "spent": spent, "per_cell": per_cell,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="bsret,bsretp,bsfull,bsfullp")
    args = ap.parse_args()

    allover_steps, allover_batt = [], []
    for tag in args.arms.split(","):
        print("ARM %s" % tag)
        for name, sample in (("canonical", CANON), ("fresh", FRESH)):
            rows = trips_for(tag, sample)
            if not rows:
                continue
            r = summarise(rows, name)
            if r and tag in ("bsret", "bsfull"):
                allover_steps += r["over_steps"]
                allover_batt += r["over_batt"]
        print()

    if allover_steps:
        print("HARDCODED-MECHANISM POOLED (bsret + bsfull, all arrived trips): n=%d"
              % len(allover_steps))
        s = sorted(allover_steps)
        b = sorted(allover_batt)
        for q in (0.50, 0.90, 0.95, 0.99, 1.00):
            i = int(q * (len(s) - 1))
            print("   q%.2f  steps-over-d %5.1f   batt-over-0.3d %6.2f" % (q, s[i], b[i]))


if __name__ == "__main__":
    main()
