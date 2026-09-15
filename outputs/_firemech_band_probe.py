"""Fire-mechanic Part 1: which distance metric makes a 3-wide cleared band block? Read-only.

Uses the model's own Fire.probability_of_fire (radius-3 Moore neighbourhood,
euclidean**-2 kernel with a euclidean cutoff of 3, wind bias) on a real
WildFireModel grid. For a straight front at two orientations (axis-aligned and
45-degree) it:
  1. sets a half-plane burning,
  2. defines a band from the distance of every other cell to that burning set,
     under two candidate rules,
  3. removes the band's fuel (fuel = 0, the proposed firebreak write),
  4. WORST CASE: sets every fuel cell on the fire side of the band burning too,
     i.e. the fire has advanced right up to the band,
  5. reports the maximum ignition probability over the cells beyond the band.
A band "blocks" iff that maximum is exactly 0.

Rules compared (d = distance to the nearest ORIGINAL burning cell):
  manhattan [3,5]  : 3 <= d_manhattan <= 5
  euclid    (2,5]  : 4 <  d_euclid^2  <= 25
The model is built only to obtain Fire agents on a grid; nothing is stepped.
"""
from __future__ import annotations

import contextlib
import io as _io
import os
import random
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am  # noqa: E402
import common_fixed_variables as cfv  # noqa: E402
import wildfire_model as wf  # noqa: E402
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402
from wildfire_model import WildFireModel  # noqa: E402


def build(wind):
    rng = random.Random(7)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=2, NUM_VICTIMS=1, NUM_FIREFIGHTERS=1,
                          WIND_DIRECTION=wind, BATCH_SIZE=300,
                          FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
                          NUM_FIRE_TRACKERS=1, NUM_VICTIM_SEARCHERS=1)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
    grid = {}
    for a in m.schedule.agents:
        if type(a) is am.Fire and getattr(a, "pos", None) is not None:
            grid[(int(a.pos[0]), int(a.pos[1]))] = a
    return m, grid


def run(orientation, rule, wind):
    m, grid = build(wind)
    for a in grid.values():
        a.burning = False
        a.burnt = False
        a.has_burned = False
        a.fuel = 8
    if orientation == "axis":
        burning0 = {c for c in grid if c[0] <= 20}
    else:
        burning0 = {c for c in grid if c[0] + c[1] <= 45}
    for c in burning0:
        grid[c].burning = True
    b0 = list(burning0)

    def d_man(c):
        return min(abs(c[0] - x) + abs(c[1] - y) for x, y in b0)

    def d_e2(c):
        return min((c[0] - x) ** 2 + (c[1] - y) ** 2 for x, y in b0)

    band, fire_side, beyond = set(), set(), set()
    for c in grid:
        if c in burning0:
            continue
        if rule == "manhattan":
            d = d_man(c)
            (band if 3 <= d <= 5 else fire_side if d <= 2 else beyond).add(c)
        else:
            d2 = d_e2(c)
            (band if 4 < d2 <= 25 else fire_side if d2 <= 4 else beyond).add(c)
    for c in band:
        grid[c].fuel = 0
    for c in fire_side:
        grid[c].burning = True
    # stay away from the grid edge so a truncated neighbourhood cannot flatter a rule
    probe = [c for c in beyond if 5 <= c[0] <= 44 and 5 <= c[1] <= 44]
    worst = max(((grid[c].probability_of_fire(), c) for c in probe), default=(0.0, None))
    band_check = max((grid[c].probability_of_fire() for c in band), default=0.0)
    return len(band), len(probe), worst, band_check


def main():
    print("orientation  rule        wind   band_cells  probed_beyond  max_P_beyond  at_cell    max_P_on_band")
    for wind in ("east", "south"):
        for orientation in ("axis", "diagonal"):
            for rule in ("manhattan", "euclid"):
                nb, npb, (p, cell), pb = run(orientation, rule, wind)
                print("%-12s %-11s %-6s %10d %14d %13.4f  %-10s %13.4f  %s" % (
                    orientation, rule, wind, nb, npb, p, cell, pb, "BLOCKS" if p == 0 else "LEAKS"))


if __name__ == "__main__":
    main()
