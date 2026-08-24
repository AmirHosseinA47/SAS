"""fix14 Part 1: churn baseline, BASE vs POST, from the preserved x-clamp probes.

Sources (commit 65f5b31 on claude/coverage-target-clamp-fix-8cc247):
  BASE = _tf_<tag>_BASE.json   pre-x-clamp
  POST = _tf_<tag>.json        x-clamp applied
Both sides are present on disk; re-running _gate_xclamp.py on this pair
reproduces the committed xclamp_gate_report.txt byte-for-byte (modulo CRLF),
which is what identifies the no-suffix files as the POST artifacts.

A "segment" is a maximal run of consecutive steps holding the same target.
Segment count and mean segment length are the churn numbers quoted in commit
0bff40f ("target segments 16/21 -> 70/73, mean hold 14.9/11.4 -> 3.4/3.3").
"""
from __future__ import annotations

import itertools
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS = ["D_north_101", "D_south_101", "A_north_101", "A_west_505"]
ARRIVAL = 2.0  # COMMIT_ARRIVAL_DIST


def cell(v):
    return (int(v[0]), int(v[1])) if v else None


def load(tag, sfx):
    with open(os.path.join(ROOT, "_tf_%s%s.json" % (tag, sfx)), encoding="utf-8") as f:
        return json.load(f)


def proposed(rec):
    return cell(rec.get("gen_target_exec") or rec.get("gen_target_planner"))


def finalized(rec):
    out = None
    for name, c in rec.get("gen_inner") or []:
        if name == "finalize" and c:
            out = cell(c)
    return out


def pos_at(rec):
    """Searcher position BEFORE this step's move (the 'from' of advance)."""
    for a in rec.get("advance") or []:
        if a and a[0]:
            return cell(a[0])
    return cell(rec.get("searcher_pos"))


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def euc(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def churn(d, key):
    """Segment stats over the target series produced by `key`.

    Steps with no target are dropped before grouping, so a one-step gap in
    instrumentation does not manufacture an extra segment.
    """
    rows = [(key(r), pos_at(r), r.get("step")) for r in d["step_records"]]
    rows = [(t, p, s) for t, p, s in rows if t is not None and p is not None]
    segs = []
    for tgt, grp in itertools.groupby(rows, key=lambda z: z[0]):
        grp = list(grp)
        segs.append(dict(
            target=tgt,
            length=len(grp),
            start_pos=grp[0][1],
            end_pos=grp[-1][1],
            start_step=grp[0][2],
            start_man=man(grp[0][1], tgt),
            end_man=man(grp[-1][1], tgt),
            end_euc=euc(grp[-1][1], tgt),
        ))
    return segs


def summarize(segs):
    if not segs:
        return {}
    n = len(segs)
    lens = [s["length"] for s in segs]
    # a re-target is a segment boundary: every segment but the last is abandoned
    abandoned = segs[:-1]
    arrived = [s for s in abandoned if s["end_euc"] <= ARRIVAL]
    return dict(
        n_segments=n,
        n_distinct=len(set(s["target"] for s in segs)),
        mean_hold=sum(lens) / n,
        median_hold=sorted(lens)[n // 2],
        max_hold=max(lens),
        n_hold_le2=sum(1 for L in lens if L <= 2),
        n_hold_le3=sum(1 for L in lens if L <= 3),
        n_retargets=len(abandoned),
        mean_rem_man=(sum(s["end_man"] for s in abandoned) / len(abandoned)) if abandoned else 0.0,
        median_rem_man=(sorted(s["end_man"] for s in abandoned)[len(abandoned) // 2]) if abandoned else 0,
        mean_start_man=sum(s["start_man"] for s in segs) / n,
        mean_closed=(sum(s["start_man"] - s["end_man"] for s in abandoned) / len(abandoned)) if abandoned else 0.0,
        min_rem_man=(min(s["end_man"] for s in abandoned)) if abandoned else 0,
        timeout_budget=2.0 * (sum(s["start_man"] for s in segs) / n),
        n_arrived=len(arrived),
        pct_arrived=(100.0 * len(arrived) / len(abandoned)) if abandoned else 0.0,
    )


def main():
    lines = []

    def log(m=""):
        print(m, flush=True)
        lines.append(m)

    for label, key in [("FINALIZED target (finalizer output)", finalized),
                       ("PROPOSED target (generator return)", proposed)]:
        log("=" * 78)
        log("CHURN BASELINE - %s" % label)
        log("=" * 78)
        log("")
        hdr = ("%-13s %-6s %5s %5s %8s %7s %7s %7s %6s %8s %7s %7s %7s %8s %8s"
               % ("run", "side", "segs", "dist", "meanhold", "medhold", "maxhold",
                  "hold<=3", "retgt", "meanStart", "meanRem", "medRem", "minRem",
                  "closed", "arrived%"))
        log(hdr)
        log("-" * len(hdr))
        for tag in RUNS:
            for sfx, side in [("_BASE", "BASE"), ("", "POST")]:
                s = summarize(churn(load(tag, sfx), key))
                log("%-13s %-6s %5d %5d %8.1f %7d %7d %7d %6d %8.1f %7.1f %7d %7d %8.1f %8.1f"
                    % (tag, side, s["n_segments"], s["n_distinct"], s["mean_hold"],
                       s["median_hold"], s["max_hold"], s["n_hold_le3"],
                       s["n_retargets"], s["mean_start_man"], s["mean_rem_man"],
                       s["median_rem_man"], s["min_rem_man"], s["mean_closed"],
                       s["pct_arrived"]))
            log("")
        log("")

    out = os.path.join(ROOT, "fix14_churn_baseline.txt")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
