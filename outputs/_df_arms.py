#!/usr/bin/env python
"""Dock-fix round: the two readings _dc_arms.py cannot make.

  paired     SEED-MATCHED comparison of two arms. _dc_arms.py --mode outcomes
             reports per-arm TOTALS and their deltas, which is the right reading
             for "which arm is better" but the wrong one for "did this fix move
             this seed": two arms can total the same while half the seeds moved
             in each direction. Gate item 5 asks for the seed-matched reading, so
             it is done here, per seed, with the runs that differ named.
  identity   byte-identity over _dc_arms.IDENTITY_FIELDS, but over ANY sample -
             including the 5-seed waypoint sample, which _dc_arms.py's --sample
             choices do not contain.

Everything else in the round is read with outputs/_dc_arms.py and
outputs/_df_evidence.py. Read-only; runs no simulation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location(
    "_dc_arms", os.path.join(HERE, "_dc_arms.py"))
DC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DC)

# The depot round's samples, plus the 5-seed mechanism-1 sample this round adds.
SAMPLES = dict(DC.SAMPLES)
SAMPLES["waypoint"] = [("east", "half", s) for s in (101, 202, 303, 404, 505)]

# The six quantities gate item 5 names, plus the return share, which is the one
# the depot round existed to move and therefore the one a fix must not wreck.
PAIRED = ["rescued", "dead", "firefighter_deaths", "never_detected"]


def load(tag, wind, roles, seed):
    p = os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, roles, seed))
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _return_share(d):
    """UAV-steps spent on a return leg, as a share of all UAV-steps."""
    rows = d.get("uav_steps") or []
    total = returning = 0
    for row in rows:
        for cell in row:
            total += 1
            if str(cell[5] or "") in ("returning",):
                returning += 1
    return (100.0 * returning / total) if total else 0.0


def mode_paired(args):
    a, b = args.a, args.b
    print("PAIRED  %s (new) against %s (old)  sample=%s" % (a, b, args.sample))
    print("  seed-matched. A row appears only when something DIFFERS.")
    print("")
    rows = []
    missing = 0
    moved = {k: 0 for k in PAIRED + ["terminal_step", "return_share"]}
    same = 0
    for wind, roles, seed in SAMPLES[args.sample]:
        da, db = load(a, wind, roles, seed), load(b, wind, roles, seed)
        if da is None or db is None:
            missing += 1
            continue
        ea = da.get("eval") or {}
        eb = db.get("eval") or {}
        diff = []
        for k in PAIRED:
            va, vb = int(ea.get(k) or 0), int(eb.get(k) or 0)
            if va != vb:
                diff.append("%s %d->%d" % (k, vb, va))
                moved[k] += 1
        ta, tb = da.get("terminal_step"), db.get("terminal_step")
        if ta != tb:
            diff.append("terminal_step %s->%s" % (tb, ta))
            moved["terminal_step"] += 1
        ra, rb = _return_share(da), _return_share(db)
        if abs(ra - rb) > 0.005:
            diff.append("return_share %.2f%%->%.2f%%" % (rb, ra))
            moved["return_share"] += 1
        if diff:
            rows.append(("%s/%s/%s" % (wind, roles, seed), diff))
        else:
            same += 1
    for key, diff in rows:
        print("  %-20s %s" % (key, "; ".join(diff)))
    if not rows:
        print("  (no run differs on any of these quantities)")
    print("")
    print("  %d of %d runs identical on all of them   (missing files: %d)"
          % (same, same + len(rows), missing))
    print("  runs moved, per quantity: %s"
          % ", ".join("%s %d" % (k, v) for k, v in moved.items() if v))
    print("")
    # Totals, so a report can quote both readings.
    print("  TOTALS      " + " ".join("%18s" % k for k in PAIRED))
    for tag in (b, a):
        tot = []
        for k in PAIRED:
            s = 0
            for wind, roles, seed in SAMPLES[args.sample]:
                d = load(tag, wind, roles, seed)
                if d is not None:
                    s += int((d.get("eval") or {}).get(k) or 0)
            tot.append(s)
        print("  %-11s " % tag + " ".join("%18d" % v for v in tot))


def mode_identity(args):
    a, b = args.a, args.b
    total = same = missing = 0
    field_diffs: dict = {}
    for wind, roles, seed in SAMPLES[args.sample]:
        da, db = load(a, wind, roles, seed), load(b, wind, roles, seed)
        if da is None or db is None:
            missing += 1
            continue
        total += 1
        diffs = [f for f in DC.IDENTITY_FIELDS if da.get(f) != db.get(f)]
        if diffs:
            for f in diffs:
                field_diffs.setdefault(f, []).append((wind, roles, seed))
        else:
            same += 1
    print("IDENTITY  %s vs %s  sample=%s" % (a, b, args.sample))
    print("  %d / %d runs IDENTICAL on all %d fields   (missing files: %d)"
          % (same, total, len(DC.IDENTITY_FIELDS), missing))
    if not field_diffs:
        return
    print("  DIFFERING FIELDS:")
    for f, where in sorted(field_diffs.items()):
        print("    %-32s on %d of %d runs" % (f, len(where), total))
    every = all(len(w) == total for w in field_diffs.values())
    print("")
    if every and "eval" not in field_diffs:
        print("  SIGNATURE: the differing field set is IDENTICAL on every run and")
        print("  contains no evaluation metric. That is SCHEMA DRIFT, not a")
        print("  regression - re-measure the reference with the current harness.")
    else:
        print("  SIGNATURE: this is a BEHAVIOUR difference, not schema drift.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", required=True, choices=("paired", "identity"))
    ap.add_argument("--a", required=True, help="the NEW arm")
    ap.add_argument("--b", required=True, help="the OLD arm it is read against")
    ap.add_argument("--sample", default="both",
                    choices=("canonical", "fresh", "both", "waypoint"))
    args = ap.parse_args()
    {"paired": mode_paired, "identity": mode_identity}[args.mode](args)


if __name__ == "__main__":
    main()
