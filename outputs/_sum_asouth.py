"""Summarize the A/south hold-vs-nohold diagnosis runs into a report."""
from __future__ import annotations

import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS = [101, 202, 303, 404, 505]


def load(mode, seed):
    p = os.path.join(HERE, "_as_%s_%d.json" % (mode, seed))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def hold_stats(res):
    """Segment the per-step commit_target trace into hold segments."""
    segs = []
    cur = None
    cov_steps = 0
    held_steps = 0
    for r in res["step_records"]:
        ws = r.get("ws_entry") or {}
        if r.get("coverage_active"):
            cov_steps += 1
        t = ws.get("commit_target")
        if t is not None:
            held_steps += 1
            t = tuple(t)
        if t != (cur["target"] if cur else None):
            if cur:
                segs.append(cur)
            cur = {"target": t, "start": r["step"], "n": 0, "pos0": r.get("searcher_pos")} if t else None
        if cur:
            cur["n"] += 1
            cur["end"] = r["step"]
            cur["pos_end"] = r.get("searcher_pos")
            cur["no_progress"] = ws.get("commit_no_progress")
    if cur:
        segs.append(cur)
    last = (res["step_records"][-1].get("ws_entry") or {})
    return {
        "segments": segs,
        "n_segments": len(segs),
        "held_steps": held_steps,
        "coverage_steps": cov_steps,
        "breaks": last.get("commit_breaks") or {},
        "issued": last.get("commit_issued"),
        "mean_hold": (sum(s["n"] for s in segs) / len(segs)) if segs else 0.0,
        "max_hold": max((s["n"] for s in segs), default=0),
    }


def line(mode, seed):
    res = load(mode, seed)
    if res is None:
        return "  %-7s seed=%-4d MISSING" % (mode, seed)
    ev = res["eval"]
    hs = hold_stats(res)
    ms = res["min_searcher"]
    ma = res["min_any"]
    out = ["  %-7s seed=%-4d rescued=%s never_detected=%s causes=%s"
           % (mode, seed, ev.get("rescued"), ev.get("never_detected"),
              ev.get("unreachable_causes") or "-")]
    out.append("      obs_frac searcher=%.3f all=%.3f | coverage_steps=%d held_steps=%d"
               % (res["obs_frac_searcher"], res["obs_frac_all"], hs["coverage_steps"], hs["held_steps"]))
    out.append("      hold segments=%d mean=%.1f max=%d breaks=%s"
               % (hs["n_segments"], hs["mean_hold"], hs["max_hold"], hs["breaks"]))
    for vid in sorted(res["spawns"]):
        out.append("      %-9s spawn=%-10s min_searcher=%-6s min_any=%-6s ever_searcher=%s ever_any=%s"
                   % (vid, tuple(res["spawns"][vid]), ms.get(vid), ma.get(vid),
                      res["ever_searcher"].get(vid), res["ever_any"].get(vid)))
    return "\n".join(out)


def main():
    for mode in ("hold", "nohold"):
        print("=== mode=%s" % mode)
        for seed in SEEDS:
            print(line(mode, seed))
        print()
    # seed 303 detail: longest holds and where the searcher was
    for mode in ("hold", "nohold"):
        res = load(mode, 303)
        if res is None:
            continue
        hs = hold_stats(res)
        print("=== seed 303 %s: longest hold segments" % mode)
        for s in sorted(hs["segments"], key=lambda s: -s["n"])[:12]:
            print("   steps %3d-%3d n=%3d target=%s pos_start=%s pos_end=%s no_progress=%s"
                  % (s["start"], s.get("end", s["start"]), s["n"], s["target"],
                     s["pos0"], s.get("pos_end"), s.get("no_progress")))
        print()
        # searcher position histogram by grid quadrant
        c = Counter()
        for r in res["step_records"]:
            p = r.get("searcher_pos")
            if p:
                c[(p[0] // 10, p[1] // 10)] += 1
        print("   searcher position histogram (10x10 blocks, x_block,y_block):")
        for k in sorted(c):
            print("     %s %d" % (k, c[k]))
        print()


if __name__ == "__main__":
    main()
