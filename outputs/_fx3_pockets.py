"""fix3a - DEPOT POCKETS from _sd_probe JSONs (read-only).

Definition (reconstructs the session-2 ad hoc numbers; see --check):
  a step t of UAV u is a POCKET step when some window of W consecutive steps containing t has, on
  every step of the window, u airborne (not rtb_docked) and within R (Manhattan) of a depot cell,
  and u occupies at most 2 distinct cells over the window. An EPISODE is a maximal run of pocket
  steps. PRE-TERMINAL = steps 1 .. terminal_step - 1 (all 360 when the run has no terminal step).

usage: _fx3_pockets.py <tag> [<tag> ...] [--w 10] [--r 5] [--list] [--full] [--dist man|cheb]
  reads outputs/_sd_<tag>_<S>_<W>.json for every file that exists.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def depot_dist_fn(cells, kind):
    cells = [tuple(c) for c in cells]

    def f(x, y):
        if kind == "cheb":
            return min(max(abs(x - a), abs(y - b)) for a, b in cells)
        return min(abs(x - a) + abs(y - b) for a, b in cells)
    return f


def pockets(d, w=10, r=5, pre_terminal=True, kind="man"):
    rows = d["rows_uav"]
    cells = d["depots"]["cells"]
    dist = depot_dist_fn(cells, kind)
    T = len(rows)
    term = d.get("terminal_step")
    last = (term - 1) if (pre_terminal and term) else T
    per_uav = {}
    for s in range(T):
        for r_ in rows[s]:
            per_uav.setdefault(r_[0], []).append(r_)
    out = []
    for uid, seq in per_uav.items():
        n = min(len(seq), last)
        ok = []
        for i in range(n):
            x, y, docked = seq[i][1], seq[i][2], seq[i][6]
            ok.append(x is not None and not docked and dist(x, y) <= r)
        mark = [False] * n
        for i in range(0, n - w + 1):
            if not all(ok[i:i + w]):
                continue
            cs = {(seq[j][1], seq[j][2]) for j in range(i, i + w)}
            if len(cs) <= 2:
                for j in range(i, i + w):
                    mark[j] = True
        i = 0
        while i < n:
            if mark[i]:
                j = i
                while j + 1 < n and mark[j + 1]:
                    j += 1
                cs = sorted({(seq[k][1], seq[k][2]) for k in range(i, j + 1)})
                acts = {}
                for k in range(i, j + 1):
                    acts[seq[k][8]] = acts.get(seq[k][8], 0) + 1
                out.append({"uid": uid, "role": seq[i][3], "start": i + 1, "end": j + 1,
                            "len": j - i + 1, "cells": cs[:6], "ncells": len(cs),
                            "inside": sum(1 for k in range(i, j + 1)
                                          if dist(seq[k][1], seq[k][2]) == 0),
                            "rtb": sum(1 for k in range(i, j + 1) if seq[k][5]),
                            "acts": acts})
                i = j + 1
            else:
                i += 1
    return out, term


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--r", type=int, default=5)
    ap.add_argument("--full", action="store_true", help="all steps, not pre-terminal")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dist", default="man")
    ap.add_argument("--min", type=int, default=20, help="report episodes >= this length separately")
    a = ap.parse_args()
    for tag in a.tags:
        files = sorted(glob.glob(os.path.join(HERE, "_sd_%s_*.json" % tag)))
        files = [f for f in files if f.endswith(".json") and "_" in os.path.basename(f)]
        tot_steps = tot_eps = long_eps = 0
        lines = []
        for f in files:
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception as exc:
                print("SKIP %s %r" % (f, exc))
                continue
            eps, term = pockets(d, a.w, a.r, not a.full, a.dist)
            tot_steps += sum(e["len"] for e in eps)
            tot_eps += len(eps)
            long_eps += sum(1 for e in eps if e["len"] >= a.min)
            for e in eps:
                lines.append("  %-10s %s/%s term=%s  %s %-16s %3d-%3d len %3d inside %3d rtb %3d cells %s acts %s" % (
                    tag, d["scenario"], d["wind"][0].upper(), term, e["uid"], e["role"], e["start"], e["end"],
                    e["len"], e["inside"], e["rtb"], e["cells"], e["acts"]))
        print("%-10s files %2d  pocket UAV-steps %4d  episodes %3d  (>= %d: %d)  [w=%d r=%d %s %s]" % (
            tag, len(files), tot_steps, tot_eps, a.min, long_eps, a.w, a.r, a.dist,
            "full" if a.full else "pre-terminal"))
        if a.list:
            print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
