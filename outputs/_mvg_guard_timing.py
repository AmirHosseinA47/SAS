"""MVG Part 1d 1d.2.5: offline wall time of the frozen guard (_mvg_guard_diag.guard, imported unchanged) on every live
(a) / (b) decision of the replayed arm-M runs (outputs/_ud_replay/_bd_udrp_ud2*_R0.json). One process, no contention;
in-run times under 9-12 concurrent runs are higher (U1's identical FAE + BFS measured p99 34.6-43.0 ms in-run,
report 4.1). usage: _mvg_guard_timing.py"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _mvg_guard_diag as G  # noqa: E402

ts, nb = [], []
for bpath in sorted(glob.glob(os.path.join(HERE, "_ud_replay", "_bd_udrp_ud2*_R0.json"))):
    name = os.path.basename(bpath)[4:-5]
    with open(bpath, encoding="utf-8") as fh:
        bd = json.load(fh)
    with open(os.path.join(HERE, "_ud_replay", "_sd_%s.json" % name), encoding="utf-8") as fh:
        d = json.load(fh)
    w, h = bd["grid"]
    wind = tuple(bd["wind"]["vector"])
    dec = {(s, u): dig for s, u, _p, _t, _st, _ex, dig in bd["decisions"]}
    cols = d["mv"]["cols"]
    mv = {(r[0], r[1]): dict(zip(cols, r)) for r in d["mv"]["rows"]}
    for e in d["mv_events"]:
        if not e.get("live") or e.get("kind") not in ("a", "b"):
            continue
        row = mv.get((e["step"], e["unit"]))
        dig = dec.get((e["step"], e["unit"]))
        if row is None or dig is None:
            continue
        b = bd["boards"][dig]
        burning = {tuple(c) for c in b["burning"]}
        smoky = {tuple(c) for c in b["smoky"]}
        t0 = time.perf_counter()
        G.guard(row["pre"], e["taken"], row["target"], burning, smoky, wind, w, h)
        ts.append((time.perf_counter() - t0) * 1000.0)
        nb.append(len(burning))
ts.sort()


def q(p):
    return ts[min(len(ts) - 1, int(p * len(ts)))]


print("guard calls %d | median %.1f ms | p90 %.1f | p99 %.1f | max %.1f | burning cells median %d, max %d" % (
    len(ts), statistics.median(ts), q(0.9), q(0.99), ts[-1], statistics.median(nb), max(nb)))
