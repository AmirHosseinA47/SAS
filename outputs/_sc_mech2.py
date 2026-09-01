"""Why do scorched cells re-ignite at 96%?  Intrinsic hazard, or position?

probability_of_fire() (agents.py:53-84) gates on the cell OWN fuel > 0 and then
sums over BURNING neighbours in a Moore radius-3 disc.  It never reads
has_burned.  So a scorched cell and a virgin cell facing the same burning
neighbourhood draw from the identical distribution, and any measured difference
in re-ignition rate can only come from scorched cells sitting in richer burning
neighbourhoods - i.e. from POSITION, not from a property of the ground.

This tests that directly.  mesa SimultaneousActivation runs every Fire.step()
and then every Fire.advance() inside one model.step(), so a cell that ignites
this step is already burning when model.step() returns.  The at-risk set is
therefore snapshotted BEFORE the step and resolved after it, and cell_prob read
afterwards is exactly the clamped probability that step drew against.

Comparing ignition rates at MATCHED cell_prob separates the two explanations.
Read-only: observes model state, never writes it.
"""
from __future__ import annotations
import argparse
import contextlib
import io as _io
import json
import os
import random
import sys
from collections import defaultdict

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS

BINS = [0.0, 1e-12, 0.01, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.01]


def binof(p):
    for i in range(len(BINS) - 1):
        if BINS[i] <= p < BINS[i + 1]:
            return i
    return len(BINS) - 2


def run(seed, wind, steps):
    preset = BUILTIN_SCENARIOS["D"]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"],
              "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
              "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft}
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    # exposure[(has_burned, prob_bin)] = [n_at_risk, n_ignited, prob_sum]
    exposure = defaultdict(lambda: [0, 0, 0.0])
    seen = {True: set(), False: set()}
    lit = {True: set(), False: set()}
    ticks = 0

    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        fires = {}
        for a in model.schedule.agents:
            if type(a) is am.Fire and getattr(a, "pos", None) is not None:
                fires[(int(a.pos[0]), int(a.pos[1]))] = a

        for _ in range(1, steps + 1):
            before = []
            for cell, a in fires.items():
                if a.is_burning() or getattr(a, "burnt", False):
                    continue
                if float(getattr(a, "fuel", 0) or 0) <= 0:
                    continue
                before.append((cell, bool(getattr(a, "has_burned", False))))
            sc_before = int(getattr(next(iter(fires.values())), "steps_counter", 0))

            model.step()

            # Only the throttled tick draws; on other steps nothing can ignite.
            if (sc_before + 1) % cfv.FIRE_SPREAD_SPEED != 0:
                continue
            ticks += 1
            for cell, hb in before:
                a = fires[cell]
                p = float(getattr(a, "cell_prob", 0.0) or 0.0)
                pb = binof(p)
                e = exposure[(hb, pb)]
                e[0] += 1
                e[2] += p
                seen[hb].add(cell)
                if a.is_burning():
                    e[1] += 1
                    lit[hb].add(cell)

    return {"seed": seed, "wind": wind, "steps": steps, "bins": BINS,
            "ticks": ticks,
            "distinct": {"scorched_at_risk": len(seen[True]),
                         "scorched_ignited": len(lit[True]),
                         "virgin_at_risk": len(seen[False]),
                         "virgin_ignited": len(lit[False])},
            "rows": [{"has_burned": hb, "bin": pb, "lo": BINS[pb],
                      "hi": BINS[pb + 1], "at_risk": v[0], "ignited": v[1],
                      "prob_sum": v[2]}
                     for (hb, pb), v in sorted(exposure.items())]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    a = ap.parse_args()
    res = run(a.seed, a.wind, a.steps)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_sc_mech2_%s_%d.json" % (a.wind, a.seed))
    with open(p, "w", encoding="utf-8") as f:
        json.dump(res, f)
    print(p, res["ticks"], res["distinct"])
