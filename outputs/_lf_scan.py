"""Latch-fix round: end-of-run latch scan over a whole _ffr_ arm.

Applies the round's CORRECTED latch definition to the last ff_steps row of every
run in an arm. Counting `status == "route_blocked"` alone is not enough: a unit
whose route reopens while it is still `assigned` is relabelled "assigned" by
agents.py:1816 and stays undispatchable on a DIFFERENT gate (:2973), invisible to
a status-only scan - a latch that hides from its own detector.

Per unit, from the last row [unit_id, pos, status, assigned, exiting, dead]:
  DEAD        dead, or status "dead"
  OFF_GRID    pos is None (rescue absence)
  EXITING     carrying a victim out - legitimately busy
  DISPATCHABLE
  LATCHED_STATUS    alive, on grid, not exiting, status == "route_blocked"
  LATCHED_ASSIGNED  alive, on grid, not exiting, status != route_blocked but
                    still `assigned` at the horizon with no dispatch possible -
                    the Variant B shape

HORIZON runs are reported separately, never folded into the count: a flag raised
on the final step, or a run that ended with a victim still needing rescue, is a
240-step budget artifact and not a referent-less latch (the brief excludes it
explicitly for seed 909). Fire enclosure cannot be recovered from ff_steps, so
enclosure is reported by outputs/_lf_assert.py instead; this scan flags such a
unit and says so.

usage: _lf_scan.py --tags rbcon,rbcoff [--sample canonical|fresh|all]
Read-only.
"""
from __future__ import annotations

import argparse
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

CANONICAL = (
    [("east", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("east", "default", s) for s in (101, 202, 303)]
)
FRESH = (
    [("east", "half", s) for s in (606, 707, 808, 909, 1010)]
    + [("south", "half", s) for s in (606, 707, 808, 909, 1010)]
)


def _name(tag, wind, roles, seed):
    rr = "def" if roles == "default" else roles
    return os.path.join(BASE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def classify(row):
    unit, pos, status, assigned, exiting, dead = (
        row[0], row[1], str(row[2] or "").strip().lower(), bool(row[3]),
        bool(row[4]), bool(row[5]),
    )
    if dead or status == "dead":
        return unit, "DEAD"
    if pos is None:
        return unit, "OFF_GRID"
    if exiting:
        return unit, "EXITING"
    if status == "route_blocked":
        return unit, "LATCHED_STATUS"
    if assigned:
        return unit, "LATCHED_ASSIGNED"
    return unit, "DISPATCHABLE"


def scan(tag, combos):
    runs, missing = [], []
    for wind, roles, seed in combos:
        p = _name(tag, wind, roles, seed)
        if not os.path.exists(p):
            missing.append((wind, roles, seed))
            continue
        with open(p) as f:
            d = json.load(f)
        ev = d.get("eval") or {}
        rows = d.get("ff_steps") or []
        last = rows[-1] if rows else []
        units = [classify(r) for r in last]
        steps_run = int(ev.get("steps_run") or 0)
        terminal = ev.get("terminal_step")
        # HORIZON: the run never reached all-victims-terminal, so any flag it
        # ends with is a budget artifact, not a referent-less latch.
        horizon = terminal is None
        runs.append({
            "wind": wind, "roles": roles, "seed": seed, "horizon": horizon,
            "terminal_step": terminal, "steps_run": steps_run,
            "units": units,
            "latched": [u for u, c in units if c.startswith("LATCHED")],
            "latched_status": [u for u, c in units if c == "LATCHED_STATUS"],
            "latched_assigned": [u for u, c in units if c == "LATCHED_ASSIGNED"],
            "eval": {k: ev.get(k) for k in
                     ("rescued", "dead", "unreachable", "never_detected",
                      "firefighter_deaths", "terminal_step", "horizon_unresolved")},
        })
    return runs, missing


def report(tag, combos, label):
    runs, missing = scan(tag, combos)
    real = [r for r in runs if r["latched"] and not r["horizon"]]
    hor = [r for r in runs if r["latched"] and r["horizon"]]
    print("  %-14s %-10s runs=%2d  latched_runs=%d  units=%d  horizon_runs=%d"
          % (tag, label, len(runs), len(real),
             sum(len(r["latched"]) for r in real), len(hor)))
    for r in real:
        print("      LATCH  %s/%s/%s  %s  status=%s assigned=%s  term=%s  %s"
              % (r["wind"], r["roles"], r["seed"],
                 ",".join(r["latched"]), r["latched_status"],
                 r["latched_assigned"], r["terminal_step"], r["eval"]))
    for r in hor:
        # A run that never reached all-victims-terminal ends with work still
        # live, so an `assigned` unit is legitimately busy and a flagged one is
        # the seed-909 shape: raised against a referent that is still alive.
        print("      horizon (EXCLUDED)  %s/%s/%s  status=%s assigned=%s  "
              "terminal_step=%s steps_run=%s"
              % (r["wind"], r["roles"], r["seed"], r["latched_status"],
                 r["latched_assigned"], r["terminal_step"], r["steps_run"]))
    if missing:
        print("      MISSING %d run(s): %s" % (len(missing), missing))
    return runs, real, hor, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", required=True, help="comma-separated arm tags")
    ap.add_argument("--sample", default="all",
                    choices=["canonical", "fresh", "all"])
    a = ap.parse_args()
    samples = []
    if a.sample in ("canonical", "all"):
        samples.append(("canonical", CANONICAL))
    if a.sample in ("fresh", "all"):
        samples.append(("fresh", FRESH))

    print("END-OF-RUN LATCH SCAN  (corrected definition: alive, on grid, not")
    print("exiting, and undispatchable - status route_blocked OR still assigned)")
    print("-" * 96)
    grand = {}
    for tag in [t.strip() for t in a.tags.split(",") if t.strip()]:
        total_real = total_units = total_hor = total_missing = 0
        for label, combos in samples:
            _runs, real, hor, missing = report(tag, combos, label)
            total_real += len(real)
            total_units += sum(len(r["latched"]) for r in real)
            total_hor += len(hor)
            total_missing += len(missing)
        grand[tag] = (total_real, total_units, total_hor, total_missing)
        print()
    print("-" * 96)
    print("SUMMARY  (horizon runs excluded from the gate, per the brief)")
    for tag, (r, u, h, m) in grand.items():
        verdict = "PASS" if (r == 0 and m == 0) else ("INCOMPLETE" if m else "FAIL")
        print("  %-14s latched_runs=%d units=%d  horizon=%d  missing=%d  -> %s"
              % (tag, r, u, h, m, verdict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
