"""FOV-frame round: dump one real dashboard frame to JSON, for _fov_render.py.

Split from rendering deliberately, the same way the scorched round split its
ground dump from its image script: the capture runs the model (and the RNG), the
render is then pure drawing and can be repeated against any renderer without
touching the simulation again.

usage: _fov_capture.py <steps> <seed> <out.json>
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

PARAMS = {"NUM_AGENTS": 3, "NUM_VICTIMS": 5, "NUM_FIREFIGHTERS": 3,
          "WIND_DIRECTION": "east", "BATCH_SIZE": 300,
          "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
          "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 1}


def main() -> int:
    steps = int(sys.argv[1]); seed = int(sys.argv[2]); out = sys.argv[3]
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
    apply_scenario_config(cfv, wf, **PARAMS)
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel(); model.debug_log = False
        for _ in range(steps):
            model.step()
        frame = sd._capture_frame(model, steps)
    W, H = int(getattr(cfv, "WIDTH", 50)), int(getattr(cfv, "HEIGHT", 50))
    blob = {
        "frame": frame, "width": W, "height": H, "cs": 560.0 / W,
        "fov_radius": int(getattr(cfv, "UAV_OBSERVATION_RADIUS", 8)),
        "victim_flee_radius": int(am.victim_flee_trigger_distance()),
        "seed": seed, "steps": steps, "params": PARAMS,
    }
    json.dump(blob, open(out, "w"), sort_keys=True)
    uavs = [(u["x"], u["y"]) for u in frame["uavs"]]
    vics = [(v["x"], v["y"], v.get("flee")) for v in frame["victims"]]
    print("steps=%d seed=%d  fov_radius=%d  victim_flee_radius=%d"
          % (steps, seed, blob["fov_radius"], blob["victim_flee_radius"]))
    print("uavs:", uavs)
    print("victims (x,y,flee):", vics)
    print("cells:", len(frame["cells"]), " wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
