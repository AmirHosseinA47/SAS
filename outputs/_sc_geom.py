"""Grid geometry of the burn scar: does virgin ground ever border burnt ground?

The A/B found that penalising scorched cells evicted firefighters from BURNT
ground - the only ground in the model with a guaranteed-zero future hazard -
and the step-transition matrix showed every entry into the black came off a
scorched cell.  That is a claim about the paths units took.  This measures the
underlying geometry instead: at several snapshots, the 4-neighbour composition
of every burnt cell, and how many burnt cells have any green neighbour at all.

Read-only.
"""
from __future__ import annotations
import argparse
import contextlib
import io as _io
import json
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
from serve_dashboard import BUILTIN_SCENARIOS

NB4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
SNAPS = (60, 120, 180, 240)


def kind(a):
    if a.is_burning():
        return "burning"
    if getattr(a, "burnt", False):
        return "burnt"
    if getattr(a, "has_burned", False) and float(getattr(a, "fuel", 0) or 0) > 0:
        return "scorched"
    return "green"


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

    out = []
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        fires = {}
        for a in model.schedule.agents:
            if type(a) is am.Fire and getattr(a, "pos", None) is not None:
                fires[(int(a.pos[0]), int(a.pos[1]))] = a

        for step_i in range(1, steps + 1):
            model.step()
            if step_i not in SNAPS:
                continue
            k = {c: kind(a) for c, a in fires.items()}
            counts = {"green": 0, "scorched": 0, "burnt": 0, "burning": 0}
            for v in k.values():
                counts[v] += 1
            nb = {"green": 0, "scorched": 0, "burnt": 0, "burning": 0, "edge": 0}
            with_green = 0
            n_burnt = 0
            for c, v in k.items():
                if v != "burnt":
                    continue
                n_burnt += 1
                has_green = False
                for ox, oy in NB4:
                    m = (c[0] + ox, c[1] + oy)
                    if m not in k:
                        nb["edge"] += 1
                        continue
                    nb[k[m]] += 1
                    if k[m] == "green":
                        has_green = True
                with_green += has_green
            out.append({"step": step_i, "counts": counts, "n_burnt": n_burnt,
                        "nb_of_burnt": nb, "burnt_with_green_nb": with_green})
    return {"seed": seed, "wind": wind, "snaps": out}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    a = ap.parse_args()
    res = run(a.seed, a.wind, a.steps)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_sc_geom_%s_%d.json" % (a.wind, a.seed))
    with open(p, "w", encoding="utf-8") as f:
        json.dump(res, f)
    print(p)
    for s in res["snaps"]:
        nb = s["nb_of_burnt"]
        tot = sum(nb.values()) or 1
        print("  step %3d  burnt=%4d  burnt-with-a-GREEN-neighbour=%d (%.2f%%)  "
              "nb mix green/scorch/burnt/burning/edge = %.1f%%/%.1f%%/%.1f%%/%.1f%%/%.1f%%"
              % (s["step"], s["n_burnt"], s["burnt_with_green_nb"],
                 100.0 * s["burnt_with_green_nb"] / max(1, s["n_burnt"]),
                 100.0 * nb["green"] / tot, 100.0 * nb["scorched"] / tot,
                 100.0 * nb["burnt"] / tot, 100.0 * nb["burning"] / tot,
                 100.0 * nb["edge"] / tot))
