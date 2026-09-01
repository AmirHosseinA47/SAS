"""Defect #9: do cells that RENDER as charred actually re-ignite? Read-only.

main.py:77 and serve_dashboard.py:63 both paint a cell charcoal #2b2b2b on
"is_burnt() OR has_burned". Those are different populations:
  burnt    = has_burned AND fuel <= 0  -> absorbing, can never re-ignite
  scorched = has_burned AND fuel  > 0 AND not burning -> ORDINARY IGNITABLE GROUND
A burning cell's continuation is decided by probability_of_fire(), which reads
its BURNING NEIGHBOURS, not its own fuel (agents.py:99-103), so a cell can stop
burning with fuel left and become "scorched".

This counts scorched -> burning transitions, and burnt -> burning transitions
(which must be exactly zero).
"""
from __future__ import annotations
import argparse
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
from serve_dashboard import BUILTIN_SCENARIOS, _resolve_role_count_params


def build(seed, wind, ft, vs):
    preset = BUILTIN_SCENARIOS["D"]
    fire_trackers, victim_searchers = _resolve_role_count_params(
        preset["NUM_AGENTS"], ft, vs)
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(
        cfv, wf, NUM_AGENTS=preset["NUM_AGENTS"], NUM_VICTIMS=preset["NUM_VICTIMS"],
        NUM_FIREFIGHTERS=preset["NUM_FIREFIGHTERS"], WIND_DIRECTION=wind,
        BATCH_SIZE=300, FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
        NUM_FIRE_TRACKERS=fire_trackers, NUM_VICTIM_SEARCHERS=victim_searchers)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
    return m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--wind", default="east")
    p.add_argument("--steps", type=int, default=240)
    a = p.parse_args()

    m = build(a.seed, a.wind, 2, 2)
    fires = {}
    for ag in m.schedule.agents:
        if type(ag) is am.Fire and getattr(ag, "pos", None) is not None:
            fires[(int(ag.pos[0]), int(ag.pos[1]))] = ag

    prev = {c: "green" for c in fires}
    reignite_scorched = 0
    reignite_burnt = 0
    cells_ever_scorched = set()
    cells_ever_reignited = set()
    max_scorched = max_burnt = 0

    for _ in range(a.steps):
        with contextlib.redirect_stdout(_io.StringIO()):
            m.step()
        n_sc = n_bt = 0
        for c, ag in fires.items():
            if ag.is_burning():
                cur = "burning"
            elif getattr(ag, "burnt", False):
                cur = "burnt"
            elif getattr(ag, "has_burned", False):
                cur = "scorched"
            else:
                cur = "green"
            if cur == "scorched":
                n_sc += 1
                cells_ever_scorched.add(c)
            elif cur == "burnt":
                n_bt += 1
            if cur == "burning" and prev[c] == "scorched":
                reignite_scorched += 1
                cells_ever_reignited.add(c)
            if cur == "burning" and prev[c] == "burnt":
                reignite_burnt += 1
            prev[c] = cur
        max_scorched = max(max_scorched, n_sc)
        max_burnt = max(max_burnt, n_bt)

    print("seed=%-5s wind=%-6s steps=%d" % (a.seed, a.wind, a.steps))
    print("  peak SCORCHED (renders charred, still fuelled) ...... %5d cells" % max_scorched)
    print("  peak BURNT    (renders charred, absorbing/safe) ..... %5d cells" % max_burnt)
    print("  distinct cells that were scorched at some point ..... %5d" % len(cells_ever_scorched))
    print("  SCORCHED -> BURNING re-ignition events .............. %5d" % reignite_scorched)
    print("  distinct cells that re-ignited after scorching ...... %5d" % len(cells_ever_reignited))
    print("  BURNT -> BURNING events (must be 0) ................. %5d" % reignite_burnt)


if __name__ == "__main__":
    main()
