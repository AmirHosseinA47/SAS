"""fix3a follow-up (fx3b): the EDGE-COVERAGE question (maintainer, after Part 3: B/N 9671 in the B3-alone arm, a
victim on the grid edge that no UAV came within range of in 360 steps - does the hole exist in the shipped
arm, and does it relate to the edge filter keeping searchers off the outer ring?). Read-only over probe JSONs.

  ring      = cells at edge distance <= 3 (the band the edge filter / A1-S keep searchers out of: edge
              distance < SEARCHER_EDGE_BAND 4)
  observed  = cells within Euclidean UAV_OBSERVATION_RADIUS (8) of ANY UAV at some step (every UAV detects;
              wildfire_model.py detection loop)
Per arm: the share of ring / interior cells ever observed (PRE = before the terminal step, and FULL); the
share of SEARCHER flying steps spent in the ring; per victim: steps spent in the ring while undetected,
detected or not, and the undetected victims' last cell; the victims never detected.
usage: _fx3b_edgecov.py <tag> [<tag> ...]
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = 8.0
BAND = 4


def edge_dist(c, n=50):
    return min(c[0], n - 1 - c[0], c[1], n - 1 - c[1])


def disk(r):
    k = int(r)
    return [(dx, dy) for dx in range(-k, k + 1) for dy in range(-k, k + 1) if dx * dx + dy * dy <= r * r]


DISK = disk(R)


def runs(tag):
    for f in sorted(glob.glob(os.path.join(HERE, "_sd_%s_*.json" % tag))):
        b = os.path.basename(f)
        if ".json." in b:
            continue
        key = b[len("_sd_%s_" % tag):-5]
        if not re.fullmatch(r"[ABCD]_[ENSW](_\d+)?", key):
            continue
        yield key, json.load(open(f, encoding="utf-8"))


def analyse(d):
    n = int((d.get("grid") or [50, 50])[0])
    term = d.get("terminal_step")
    rows, vrows = d["rows_uav"], d["rows_vic"]
    obs_pre, obs_full = set(), set()
    s_ring = s_fly = 0
    first_det = {}
    ring_undet = {}
    for t, row in enumerate(rows):
        step = t + 1
        for u in row:
            x, y = int(u[1]), int(u[2])
            for dx, dy in DISK:
                c = (x + dx, y + dy)
                if 0 <= c[0] < n and 0 <= c[1] < n:
                    obs_full.add(c)
                    if term is None or step < term:
                        obs_pre.add(c)
            if u[3] == "victim_searcher" and not u[6]:        # airborne searcher (not docked)
                s_fly += 1
                s_ring += edge_dist((x, y), n) < BAND
        if t < len(vrows):
            for v in vrows[t]:
                vid, st = v[0], (v[4] or v[3])
                if st != "candidate" and vid not in first_det:
                    first_det[vid] = step
                if v[1] is not None and vid not in first_det and st == "candidate":
                    if edge_dist((int(v[1]), int(v[2])), n) < BAND:
                        ring_undet[vid] = ring_undet.get(vid, 0) + 1
    ring = [(x, y) for x in range(n) for y in range(n) if edge_dist((x, y), n) < BAND]
    inner = [(x, y) for x in range(n) for y in range(n) if edge_dist((x, y), n) >= BAND]
    never = [(v[0], v[1], v[2]) for v in vrows[-1] if v[0] not in first_det]
    return {
        "ring_pre": sum(c in obs_pre for c in ring) / len(ring), "ring_full": sum(c in obs_full for c in ring) / len(ring),
        "inner_pre": sum(c in obs_pre for c in inner) / len(inner),
        "inner_full": sum(c in obs_full for c in inner) / len(inner),
        "s_ring": s_ring, "s_fly": s_fly, "ring_undet": ring_undet, "never": never, "first_det": first_det,
    }


def main():
    for tag in sys.argv[1:]:
        res = [(k, analyse(d)) for k, d in runs(tag)]
        if not res:
            print("%-8s (no runs)" % tag)
            continue
        m = len(res)
        rp = sum(r["ring_pre"] for _, r in res) / m
        rf = sum(r["ring_full"] for _, r in res) / m
        ip = sum(r["inner_pre"] for _, r in res) / m
        inf = sum(r["inner_full"] for _, r in res) / m
        sr = sum(r["s_ring"] for _, r in res)
        sf = sum(r["s_fly"] for _, r in res)
        vic_ring = sum(1 for _, r in res for v in r["ring_undet"])
        vic_ring_steps = sum(s for _, r in res for s in r["ring_undet"].values())
        never = [(k,) + v for k, r in res for v in r["never"]]
        print("%-8s runs %2d | ring cells observed PRE %.1f%% FULL %.1f%% | interior PRE %.1f%% FULL %.1f%% | "
              "searcher flying steps in the ring %d of %d (%.1f%%) | victims undetected in the ring: %d (%d steps) | "
              "never detected %s" % (tag, m, 100 * rp, 100 * rf, 100 * ip, 100 * inf, sr, sf, 100.0 * sr / max(1, sf),
                                     vic_ring, vic_ring_steps, never or "none"))


if __name__ == "__main__":
    main()
