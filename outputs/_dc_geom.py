#!/usr/bin/env python
"""Depot-cost round, Part 1 evidence: the geometry that sets the return-leg cost.

The measured return-leg share of UAV-steps is 17.5%, and it is not a tuning
constant - it is arithmetic. One return trip costs d steps, d is the Manhattan
distance from wherever the UAV happened to be to its berth, and the sample mean
of d was 41.8 on a 240-step run with 4 UAVs: 41.8/240 = 17.4%. So the only levers
on the return-leg share are (i) the number of trips and (ii) d itself. This script
computes (ii) exactly for every candidate depot set, and reports the victim-ring
distances the original corner choice was made on.

Victim placement and the corner encoding are re-implemented here from the source
rather than imported, so the script runs in a second and touches no model state.
Both are checked against the values the base-station round reported.

Read-only. Runs no simulation.
"""
from __future__ import annotations

import math
import statistics

HEIGHT = WIDTH = 50
SIZE = 5

# --- transcribed from wildfire_model._build_base_station ---------------------
# 0 NW, 1 NE, 2 SW, 3 SE. x is the HEIGHT axis, y is the WIDTH axis.
CORNERS = {"NW": 0, "NE": 1, "SW": 2, "SE": 3}


def corner_origin(corner, size=SIZE):
    ox = 0 if corner in (0, 2) else HEIGHT - size
    oy = 0 if corner in (2, 3) else WIDTH - size
    return ox, oy


def block(origin, size=SIZE):
    ox, oy = origin
    return [(ox + i, oy + j) for i in range(size) for j in range(size)]


def ranked(origin, size=SIZE):
    return sorted(
        block(origin, size),
        key=lambda c: (-min(c[0], c[1], HEIGHT - 1 - c[0], WIDTH - 1 - c[1]), c[0], c[1]),
    )


def central_origin(size=SIZE):
    return (HEIGHT // 2 - size // 2, WIDTH // 2 - size // 2)


# --- transcribed from wildfire_model._init_managed_victims -------------------
def victims(n):
    """The victim ring. Formula copied from _init_managed_victims.

        angle = 2*pi*i / max(n,1)
        r_x = r_y = 0.3 + 0.15 * (i % 2)
        vx = max(1.0, min(HEIGHT-1, HEIGHT/2 + HEIGHT*r_x*cos(angle)))
        vy = max(1.0, min(WIDTH -1, WIDTH /2 + WIDTH *r_y*sin(angle)))
    """
    out = []
    for i in range(n):
        angle = (2 * math.pi * i) / max(n, 1)
        r_x = 0.3 + 0.15 * (i % 2)
        r_y = 0.3 + 0.15 * (i % 2)
        vx = max(1.0, min(float(HEIGHT) - 1, HEIGHT / 2.0 + HEIGHT * r_x * math.cos(angle)))
        vy = max(1.0, min(float(WIDTH) - 1, WIDTH / 2.0 + WIDTH * r_y * math.sin(angle)))
        out.append((vx, vy))
    return out


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def dist_to_set(p, cells):
    return min(man(p, c) for c in cells)


def stats_over_grid(cells):
    ds = [dist_to_set((x, y), cells) for x in range(HEIGHT) for y in range(WIDTH)]
    return statistics.mean(ds), max(ds)


def stats_over_victims(cells, vics):
    ds = [dist_to_set((int(round(v[0])), int(round(v[1]))), cells) for v in vics]
    return statistics.mean(ds), max(ds)


def main():
    import importlib
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        cfv = importlib.import_module("common_fixed_variables")
        n_vic = int(getattr(cfv, "NUM_VICTIMS"))
        n_uav = int(getattr(cfv, "NUM_AGENTS"))
        n_ff = int(getattr(cfv, "NUM_FIREFIGHTERS"))
        h, w = int(getattr(cfv, "HEIGHT")), int(getattr(cfv, "WIDTH"))
        print("from common_fixed_variables: HEIGHT %d WIDTH %d NUM_VICTIMS %d "
              "NUM_AGENTS %d NUM_FIREFIGHTERS %d" % (h, w, n_vic, n_uav, n_ff))
        if (h, w) != (HEIGHT, WIDTH):
            print("  !! grid is not %dx%d; this script's constants are stale" % (HEIGHT, WIDTH))
    except Exception as exc:                      # pragma: no cover - diagnostic
        print("could not import common_fixed_variables (%s); assuming 20 victims" % exc)
        n_vic, n_uav, n_ff = 20, 4, 2

    # The wave runs SCENARIO D, whose preset overrides the module constants:
    # NUM_AGENTS 4, NUM_VICTIMS 4, NUM_FIREFIGHTERS 2 (serve_dashboard.py:41).
    # The module defaults (3/5/3) are NOT what any arm of this campaign ran, and
    # the project's own memory records a round that compared against a baseline
    # built on the wrong override. Read the preset, do not trust the constants.
    SCEN = {"A": (3, 5, 3), "B": (3, 2, 2), "C": (5, 3, 3), "D": (4, 4, 2)}
    n_uav, n_vic, n_ff = SCEN["D"]
    print("SCENARIO D preset (serve_dashboard.BUILTIN_SCENARIOS): "
          "NUM_AGENTS %d NUM_VICTIMS %d NUM_FIREFIGHTERS %d" % (n_uav, n_vic, n_ff))

    vics = victims(n_vic)
    print("\nVICTIM RING (%d victims, scenario D, rounded to cells):" % n_vic)
    print("  " + " ".join("(%d,%d)" % (round(v[0]), round(v[1])) for v in vics))

    configs = []
    for name in ("NW", "NE", "SW", "SE"):
        configs.append((name, [corner_origin(CORNERS[name])]))
    configs.append(("CENTRAL", [central_origin()]))
    for second in ("NE", "SW", "SE"):
        configs.append(("NW+" + second, [corner_origin(CORNERS["NW"]),
                                         corner_origin(CORNERS[second])]))
    configs.append(("NW+CENTRAL", [corner_origin(CORNERS["NW"]), central_origin()]))

    print("\n%-12s %-22s %8s %6s %8s %6s" % ("config", "origins", "grid", "grid", "victim", "victim"))
    print("%-12s %-22s %8s %6s %8s %6s" % ("", "", "mean d", "max d", "mean d", "max d"))
    print("-" * 70)
    rows = {}
    for name, origins in configs:
        cells = []
        for o in origins:
            cells += block(o)
        gm, gx = stats_over_grid(cells)
        vm, vx = stats_over_victims(cells, vics)
        rows[name] = (gm, gx, vm, vx)
        print("%-12s %-22s %8.2f %6d %8.2f %6d"
              % (name, ",".join("(%d,%d)" % o for o in origins), gm, gx, vm, vx))

    print("\nThe original round reported mean victim distance 39.65 (NW) against")
    print("40.88 / 41.55 / 42.63 for the other three corners, over ALL FOUR built-in")
    print("scenarios rather than scenario D alone. Reproducing that pooled figure:")
    for name in ("NW", "NE", "SW", "SE", "CENTRAL", "NW+SE"):
        origins = dict(configs)[name]
        cells = []
        for o in origins:
            cells += block(o)
        pooled = []
        per = []
        for sc in ("A", "B", "C", "D"):
            vs = victims(SCEN[sc][1])
            ds = [dist_to_set((int(round(v[0])), int(round(v[1])))
                              if False else (v[0], v[1]), cells) for v in vs]
            per.append(statistics.mean(ds))
            pooled += ds
        print("  %-9s pooled %6.2f   per scenario A %.2f B %.2f C %.2f D %.2f"
              % (name, statistics.mean(pooled), per[0], per[1], per[2], per[3]))

    print("\nWORST-CASE RETURN D (the constant the reserve derivation is built on):")
    for name in ("NW", "CENTRAL", "NW+NE", "NW+SW", "NW+SE", "NW+CENTRAL"):
        gx = rows[name][1]
        # The shipped derivation: R = max(fuel, horizon) over the worst case D.
        fuel = 0.3 * gx + 0.3 + 5.0
        e = 0.1 + 0.2 * (5.0 / 6.0)
        horizon = 100.0 - e * (240.0 - gx)
        print("  %-11s D %3d   fuel %5.1f   horizon %5.1f   reserve max %5.1f"
              % (name, gx, fuel, horizon, max(fuel, horizon)))

    print("\nRETURN-LEG SHARE, arithmetic: one trip costs d steps out of 240 per UAV.")
    print("The measured mean trigger distance under the shipped NW/flat-60 rule was")
    print("41.8 cells, and the measured return share was 17.5% = 41.8/240 to within")
    print("a tenth of a point. Scaling that by the mean grid distance of each config:")
    base = rows["NW"][0]
    for name in ("NW", "CENTRAL", "NW+NE", "NW+SW", "NW+SE"):
        gm = rows[name][0]
        print("  %-11s mean d %5.2f  -> one trip per UAV = %5.1f%% of steps  (x%.2f vs NW)"
              % (name, gm, 100.0 * gm / 240.0, gm / base))

    print("\nBERTH RANKING per candidate block (first 8), from _build_base_station's key:")
    for name, origins in configs:
        if len(origins) != 1:
            continue
        print("  %-9s %s" % (name, " ".join("(%d,%d)" % c for c in ranked(origins[0])[:8])))


if __name__ == "__main__":
    main()
