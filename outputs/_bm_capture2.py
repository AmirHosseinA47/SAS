"""Base-mark round Part 3: capture real dashboard frames the way the DASHBOARD
produces them - _capture_frame is called on EVERY step, so fr.trails is the real
60-point walked history (Part 1's _bm_capture.py called it only at the captured
steps, which left sparse chords and could not exercise the trail arm).

Each dumped frame also carries `ff_truth`: every firefighter's retreat-range
state read straight off the MODEL's own attributes, in the model's own order
(agents.py _needs_immediate_survival_retreat) - NOT from the panel. That is what
the "fire d / r" cell is checked against, so the check is of the dashboard
against the model, not of the dashboard against itself. Keyed by panel id
(ff_unit_i), which is how the table rows are keyed.

usage: _bm_capture2.py <seed> <wind> <out_prefix> <step> [<step> ...]
"""
from __future__ import annotations
import contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
import serve_dashboard as sd


def truth(model) -> dict:
    out = {}
    for ff_id, a in (getattr(model, "firefighter_marker_agents", None) or {}).items():
        dead = bool(getattr(a, "dead", False)) or str(getattr(a, "status", "") or "").strip().lower() == "dead"
        if dead:
            st, r = "dead", None
        elif getattr(a, "pos", None) is None:
            st, r = "offgrid", None
        elif getattr(a, "exiting", False):
            st, r = "exiting", None                       # tested BEFORE target_pos, as the model does
        elif getattr(a, "target_pos", None):
            st, r = "assigned", 1                         # the bare literal at agents.py:1879
        else:
            st, r = "idle", int(am.IDLE_RETREAT_SAFETY_BUFFER)
        out[str(ff_id)] = {"state": st, "range": r,
                           "pos": None if a.pos is None else [int(a.pos[0]), int(a.pos[1])],
                           "target_pos_truthy": bool(getattr(a, "target_pos", None)),
                           "assigned_attr": bool(getattr(a, "assigned", False))}
    return out


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
    sd.SESSION["trails"] = {}
    W, H = int(getattr(cfv, "WIDTH", 50)), int(getattr(cfv, "HEIGHT", 50))
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel(); model.debug_log = False
        for step in range(max(steps) + 1):
            if step:
                model.step()
            frame = sd._capture_frame(model, step)        # EVERY step: real trails
            if step not in steps:
                continue
            blob = {"frame": frame, "width": W, "height": H, "cs": 560.0 / W,
                    "fov_radius": int(getattr(cfv, "UAV_OBSERVATION_RADIUS", 8)),
                    "victim_flee_radius": int(am.victim_flee_trigger_distance()),
                    "seed": seed, "wind": wind, "steps": step, "params": P,
                    "ff_truth": truth(model)}
            json.dump(blob, open("%s_s%d.json" % (prefix, step), "w"), sort_keys=True)
    print("seed=%d wind=%s captured %s -> %s_s*.json" % (seed, wind, steps, prefix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
