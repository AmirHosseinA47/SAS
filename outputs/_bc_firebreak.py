"""Defect #9 Part 1.3: does a burnt region act as a firebreak? Read-only.

probability_of_fire (agents.py:56-84) sums over a Moore radius-3 neighbourhood
with NO line-of-sight or occlusion test, so burnt cells cannot "shield" anything
geometrically. They can only stop fire by ceasing to be ignitable themselves.
This measures the resulting critical width directly.
"""
from __future__ import annotations
import contextlib
import io as _io
import os
import random
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel


def build(seed=7):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=2, NUM_VICTIMS=1, NUM_FIREFIGHTERS=1,
                          WIND_DIRECTION="east", BATCH_SIZE=300,
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


def quiesce(grid):
    for a in grid.values():
        a.burning = False
        a.burnt = False
        a.has_burned = False
        a.next_burning_state = False


def trial(width):
    """Burnt band of `width` columns at x=20.., fire wall at x=19. Can x=20+width ignite?"""
    m, grid = build()
    quiesce(grid)
    band = list(range(20, 20 + width))
    for (x, y), a in grid.items():
        if x in band:
            a.has_burned = True
            a.fuel = 0
            a.burnt = True
            a.burning = False
    # fire wall immediately upwind of the band
    for (x, y), a in grid.items():
        if x == 19:
            a.burning = True
            a.has_burned = True
            a.burnt = False
    target_x = 20 + width
    probs = []
    for y in range(20, 31):
        cell = grid.get((target_x, y))
        if cell is not None:
            probs.append(cell.probability_of_fire())
    return max(probs) if probs else 0.0


def main():
    print("BURNT-BAND FIREBREAK TEST")
    print("  fire wall at x=19; burnt band x=20..20+w-1; probe cell x=20+w")
    print("  probability_of_fire() of the first UNBURNT cell beyond the band")
    print()
    print("  %-6s %-14s %s" % ("width", "max p_ignite", "verdict"))
    for w in range(0, 6):
        p = trial(w)
        verdict = "fire crosses" if p > 0 else "BLOCKED (permanent firebreak)"
        print("  %-6d %-14.4f %s" % (w, p, verdict))
    print()
    print("  A burnt cell can never re-ignite (agents.py:53-55, :91-95, :121-125),")
    print("  so a band this wide is a PERMANENT firebreak, not a transient one.")
    print("  distance_rate = euclidean**-2 for d <= 3, else 0 (common_fixed_variables.py:156-161),")
    print("  hence the critical width is 3: burnt cells never occlude, they only stop being fuel.")


if __name__ == "__main__":
    main()
