"""Probe gate for target commitment (throwaway).

Compares the four instrumented runs against the pre-commitment baseline:
  impossible-segment rate  86-100%
  median slack             -19 to -34 steps
  searcher x-range         [2,26] [1,26] [11,38] [4,25]
  D/north 101 victim_3     never_detected
  A/west 505 (control)     never_detected = 0
"""
from __future__ import annotations

import itertools
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS = [("D", "north", 101), ("D", "south", 101), ("A", "west", 505), ("A", "north", 101)]
BASE = {
    "D_north_101": dict(imposs=94, med=-23, xr=(2, 26), nd=["victim_3"]),
    "D_south_101": dict(imposs=100, med=-26, xr=(1, 26), nd=["victim_1"]),
    "A_west_505": dict(imposs=98, med=-23, xr=(11, 38), nd=[]),
    "A_north_101": dict(imposs=86, med=-26, xr=(4, 25), nd=["victim_0"]),
}


def load(tag: str, suffix: str = ""):
    p = os.path.join(ROOT, "_tf_%s%s.json" % (tag, suffix))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def segments(sr):
    rows = []
    for r in sr:
        t = r.get("gen_target_exec") or r.get("gen_target_planner")
        pos = None
        for a in r.get("advance") or []:
            if a and a[0]:
                pos = (int(a[0][0]), int(a[0][1]))
        rows.append((tuple(t) if t else None, pos))
    out = []
    for key, grp in itertools.groupby(rows, key=lambda z: z[0]):
        grp = list(grp)
        if key is None:
            continue
        start = next((p for _, p in grp if p), None)
        if start is None:
            continue
        need = abs(key[0] - start[0]) + abs(key[1] - start[1])
        out.append((len(grp), need))
    return out


def main() -> int:
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    print("%-13s %5s %7s %8s %7s %-11s %-16s" % (
        "run", "segs", "imposs%", "med_slack", "held_max", "x_range", "never_detected"))
    verdict = {}
    for s, w, sd in RUNS:
        tag = "%s_%s_%d" % (s, w, sd)
        d = load(tag, suffix)
        if d is None:
            print("%-13s MISSING" % tag)
            continue
        sr = d["step_records"]
        segs = segments(sr)
        imposs = sum(1 for L, need in segs if L < need)
        pct = 100.0 * imposs / max(1, len(segs))
        slack = sorted(L - need for L, need in segs)
        med = slack[len(slack) // 2] if slack else 0
        xs = [int(a[1][0]) for r in sr for a in (r.get("advance") or []) if a and a[1]]
        held = max(
            [int((r.get("ws_entry") or {}).get("commit_held_steps", 0) or 0) for r in sr]
            or [0]
        )
        nd = d.get("nd") or []
        b = BASE[tag]
        print("%-13s %5d %6.0f%% %8d %7d %-11s %-16s" % (
            tag, len(segs), pct, med, held, "[%d,%d]" % (min(xs), max(xs)), str(nd)))
        print("              baseline: imposs=%d%% med=%d x=[%d,%d] nd=%s" % (
            b["imposs"], b["med"], b["xr"][0], b["xr"][1], b["nd"]))
        brk = {}
        for r in sr:
            cb = (r.get("ws_entry") or {}).get("commit_breaks") or {}
            for k, v in cb.items():
                brk[k] = max(brk.get(k, 0), int(v))
        issued = max(
            [int((r.get("ws_entry") or {}).get("commit_issued", 0) or 0) for r in sr]
            or [0]
        )
        print("              commit: issued=%d breaks=%s" % (issued, brk or "{}"))
        verdict[tag] = dict(
            pct=pct, med=med, xmax=max(xs), nd=nd,
            d_imposs=pct - b["imposs"], d_med=med - b["med"], d_xmax=max(xs) - b["xr"][1],
        )
        print()

    print("=== GATE ===")
    g1 = all(v["d_imposs"] < -5 for v in verdict.values())
    g2 = all(v["d_med"] > 0 for v in verdict.values())
    ns = [verdict[t]["xmax"] for t in ("D_north_101", "D_south_101", "A_north_101") if t in verdict]
    g3 = any(x > 26 for x in ns)
    g4 = "victim_3" not in (verdict.get("D_north_101", {}).get("nd") or [])
    g5 = not (verdict.get("A_west_505", {}).get("nd") or [])
    for name, ok, detail in [
        ("impossible-rate falls materially", g1,
         {t: round(v["d_imposs"], 1) for t, v in verdict.items()}),
        ("median slack moves toward zero", g2,
         {t: v["d_med"] for t, v in verdict.items()}),
        ("x-range widens past 26 (N/S)", g3, ns),
        ("D/north 101 victim_3 detected", g4,
         verdict.get("D_north_101", {}).get("nd")),
        ("A/west 505 control nd==0", g5,
         verdict.get("A_west_505", {}).get("nd")),
    ]:
        print("  %-34s %s   %s" % (name, "PASS" if ok else "FAIL", detail))
    print("VERDICT: %s" % ("GATE PASSED" if all([g1, g2, g3, g4, g5]) else "GATE FAILED"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
