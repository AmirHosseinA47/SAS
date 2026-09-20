"""Base-mark round: dump real dashboard frames at several steps of ONE run.

Same split as _fov_capture.py (the capture runs the model and the RNG; rendering
is then pure drawing), extended two ways this round needs: the wind is a
parameter, and several steps are captured from a single run so a burning-depot
frame and a quiet one come from the same trajectory.

usage: _bm_capture.py <seed> <wind> <out_prefix> <step> [<step> ...]
       writes <out_prefix>_s<step>.json for each step
"""
from __future__ import annotations
import contextlib, io as _io, json, os, random, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
import serve_dashboard as sd


def main() -> int:
    seed = int(sys.argv[1]); wind = sys.argv[2]; prefix = sys.argv[3]
    steps = sorted({int(s) for s in sys.argv[4:]})
    P = {"NUM_AGENTS": 3, "NUM_VICTIMS": 5, "NUM_FIREFIGHTERS": 3,
         "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
         "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
         "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 1}
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
    apply_scenario_config(cfv, wf, **P)
    W, H = int(getattr(cfv, "WIDTH", 50)), int(getattr(cfv, "HEIGHT", 50))
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel(); model.debug_log = False
        for step in range(max(steps) + 1):
            if step:
                model.step()
            if step not in steps:
                continue
            frame = sd._capture_frame(model, step)
            # the range-selecting state of each firefighter, for the Item B prototypes
            ffstate = {}
            for a in model.schedule.agents:
                if type(a).__name__ != "Firefighter" or a.pos is None:
                    continue
                ffstate[str(a.unique_id)] = ("exiting" if getattr(a, "exiting", False)
                                             else "assigned" if getattr(a, "target_pos", None)
                                             else "idle")
            blob = {"frame": frame, "width": W, "height": H, "cs": 560.0 / W,
                    "fov_radius": int(getattr(cfv, "UAV_OBSERVATION_RADIUS", 8)),
                    "victim_flee_radius": int(am.victim_flee_trigger_distance()),
                    "seed": seed, "wind": wind, "steps": step, "params": P,
                    "ff_state": ffstate}
            json.dump(blob, open("%s_s%d.json" % (prefix, step), "w"), sort_keys=True)
    print("seed=%d wind=%s captured steps %s -> %s_s*.json" % (seed, wind, steps, prefix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
