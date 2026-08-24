"""fix14 supplementary readouts.

Two things the headline gate table gets wrong or leaves out.

1. clampX in the gate table counts FINALIZE OUTPUTS whose x is 8 or 41, one
   per step. That was the right unit for the x-clamp round, where each step
   produced an independently chosen target. Under a hold one target is
   returned for many consecutive steps, so a single clamped commitment inflates
   the per-step count by its hold length. Counted per SEGMENT the two rounds
   are comparable again.

2. Whether the run is in the "churn-free but wrong reachability" regime that
   gate condition 1 forbids is not decidable from the distinct-target count
   alone. The regime is defined by two properties, and the second one -
   reachability - has to be measured directly.

   Reachability for FIX14 is read from production's own hold bookkeeping
   (commit_initial_dist, commit_best_dist), snapshotted per step by the probe.
   It is NOT recomputed from the step records: the probe's `advance` entries
   carry the PRE-move position while `searcher_pos` carries the POST-move one,
   so a recomputation lags production's own arrival test by one step and
   reports arrivals as near-misses. The BASE and XCLAMP sides have no hold
   bookkeeping to read, so their per-segment closest approach is recomputed
   from `searcher_pos` - the post-move field, which is the one that matches
   production's arrival test at the following step's generation.
"""
from __future__ import annotations

import itertools
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS = ["D_north_101", "D_south_101", "A_north_101", "A_west_505"]
SIDES = [("_BASE", "BASE"), ("_XCLAMP", "XCLAMP"),
         ("_P2ONLY", "P2ONLY"), ("_FIX14", "FIX14")]
CLAMP_X = (8, 41)
ARRIVAL = 2.0


def cell(v):
    return (int(v[0]), int(v[1])) if v else None


def load(tag, sfx):
    p = os.path.join(ROOT, "_tf_%s%s.json" % (tag, sfx))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def finalized(rec):
    out = None
    for name, c in rec.get("gen_inner") or []:
        if name == "finalize" and c:
            out = cell(c)
    return out


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def segs_of(d):
    """Segments keyed on the finalized target, using the POST-move position."""
    rows = [(finalized(r), cell(r.get("searcher_pos"))) for r in d["step_records"]]
    rows = [(t, p) for t, p in rows if t is not None and p is not None]
    out = []
    for tgt, grp in itertools.groupby(rows, key=lambda z: z[0]):
        grp = list(grp)
        out.append(dict(
            target=tgt, length=len(grp),
            start_man=man(grp[0][1], tgt),
            best_man=min(man(p, tgt) for _, p in grp),
        ))
    return out


def holds_of(d):
    """One row per completed hold, read from production's own bookkeeping.

    A hold ends on the step where commit_breaks gains a count; the state to
    report is the PREVIOUS step's snapshot, the last one taken while the hold
    was still standing.
    """
    rows, prev_breaks, prev_ws = [], None, None
    for r in d["step_records"]:
        ws = r.get("ws_entry") or {}
        b = dict(ws.get("commit_breaks") or {})
        if prev_breaks is not None and b != prev_breaks:
            reason = next(
                (k for k, v in b.items() if v > int(prev_breaks.get(k, 0))), "?"
            )
            rows.append(dict(
                reason=reason,
                target=prev_ws.get("commit_target"),
                initial=float(prev_ws.get("commit_initial_dist") or 0.0),
                best=(None if prev_ws.get("commit_best_dist") is None
                      else float(prev_ws.get("commit_best_dist"))),
                held=int(prev_ws.get("commit_held_steps") or 0),
                no_progress=int(prev_ws.get("commit_no_progress") or 0),
                step=r.get("step"),
            ))
        prev_breaks, prev_ws = b, ws
    return rows


def main() -> int:
    lines: list = []

    def log(m: str = "") -> None:
        print(m, flush=True)
        lines.append(m)

    log("=" * 78)
    log("1. CLAMPED TARGETS, COUNTED PER SEGMENT INSTEAD OF PER STEP")
    log("=" * 78)
    log("")
    log("A segment is one commitment. Per-step counts inflate under a hold.")
    log("")
    hdr = ("%-13s %-7s %6s %10s %10s %10s %11s"
           % ("run", "side", "segs", "clampSeg", "clampSeg%", "clampStep", "clampStep%"))
    log(hdr)
    log("-" * len(hdr))
    for tag in RUNS:
        for sfx, side in SIDES:
            d = load(tag, sfx)
            if d is None:
                continue
            segs = segs_of(d)
            cs = sum(1 for s in segs if s["target"][0] in CLAMP_X)
            fins = [f for f in (finalized(r) for r in d["step_records"]) if f]
            ct = sum(1 for f in fins if f[0] in CLAMP_X)
            log("%-13s %-7s %6d %10d %10.1f %10d %11.1f"
                % (tag, side, len(segs), cs, 100.0 * cs / max(1, len(segs)),
                   ct, 100.0 * ct / max(1, len(fins))))
        log("")

    log("=" * 78)
    log("2. REACHABILITY - IS THIS THE 'CHURN-FREE BUT WRONG REACHABILITY' REGIME?")
    log("=" * 78)
    log("")
    log("The regime condition 1 forbids has TWO properties: few distinct targets")
    log("AND the searcher cannot reach them. The distinct-target count alone")
    log("cannot separate them. These columns measure the second property.")
    log("")
    log("  meanStart    Manhattan distance to the target when it was chosen")
    log("  meanClosest  closest Manhattan approach reached while it was held")
    log("  closed%      fraction of the initial gap actually closed")
    log("")
    hdr = ("%-13s %-7s %6s %10s %12s %9s"
           % ("run", "side", "segs", "meanStart", "meanClosest", "closed%"))
    log(hdr)
    log("-" * len(hdr))
    for tag in RUNS:
        for sfx, side in SIDES:
            d = load(tag, sfx)
            if d is None:
                continue
            segs = segs_of(d)
            n = len(segs)
            st = sum(s["start_man"] for s in segs) / n
            be = sum(s["best_man"] for s in segs) / n
            log("%-13s %-7s %6d %10.1f %12.1f %9.1f"
                % (tag, side, n, st, be, 100.0 * (st - be) / st if st else 0.0))
        log("")

    log("=" * 78)
    log("3. EVERY COMPLETED HOLD, FROM PRODUCTION'S OWN BOOKKEEPING (FIX14)")
    log("=" * 78)
    log("")
    log("initial = Manhattan gap when the hold armed; best = closest approach")
    log("reached; held = steps held; nop = consecutive non-closing steps.")
    log("")
    hdr = ("%-13s %-9s %-10s %8s %7s %7s %5s %7s"
           % ("run", "release", "target", "initial", "best", "closed", "held", "nop"))
    log(hdr)
    log("-" * len(hdr))
    for tag in RUNS:
        d = load(tag, "_FIX14")
        if d is None:
            continue
        for h in holds_of(d):
            closed = ("-" if h["best"] is None
                      else "%.0f" % (h["initial"] - h["best"]))
            log("%-13s %-9s %-10s %8.0f %7s %7s %5d %7d"
                % (tag, h["reason"], str(h["target"]), h["initial"],
                   ("-" if h["best"] is None else "%.0f" % h["best"]),
                   closed, h["held"], h["no_progress"]))
        log("")

    out = os.path.join(ROOT, "fix14_gate_detail.txt")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
