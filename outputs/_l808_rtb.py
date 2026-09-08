"""Return-to-base activity probe for one (seed, mode). Read-only.

_l808_trace.py read UAV.battery / UAV.base_state, which are not the attribute
names (agents.UAV carries battery_level and rtb_log; base_state is computed in
the dashboard builder). This probe records the real ones so the round can say
how much return-leg activity the arm actually had, and when.
"""
from __future__ import annotations
import argparse, contextlib, io as _io, json, os, random, sys, time

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--mode", type=int, required=True)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS["D"]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft,
              "BASE_STATION_MODE": a.mode}
    rng = random.Random(a.seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    t0 = time.perf_counter()
    per_step = []
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        uavs = [x for x in model.schedule.agents if isinstance(x, am.UAV)]
        spawn = {int(u.unique_id): (list(u.pos) if u.pos else None) for u in uavs}
        for s in range(1, a.steps + 1):
            model.step()
            per_step.append({
                "step": s,
                "uav": {int(u.unique_id): {
                    "pos": list(u.pos) if u.pos else None,
                    "bat": round(float(getattr(u, "battery_level", 0.0)), 2),
                    "bstat": str(getattr(u, "battery_status", "")),
                    "trips": len(getattr(u, "rtb_log", []) or []),
                } for u in uavs},
            })
        logs = {int(u.unique_id): (getattr(u, "rtb_log", []) or []) for u in uavs}
        roles = {int(u.unique_id): str(getattr(u, "role", "")) for u in uavs}
    out = {"seed": a.seed, "mode": a.mode, "wind": a.wind, "spawn": spawn,
           "roles": roles, "rtb_log": logs, "per_step": per_step,
           "wall_s": round(time.perf_counter() - t0, 1)}
    with open(a.out, "w") as f:
        json.dump(out, f, default=str)
    total = sum(len(v) for v in logs.values())
    sys.stderr.write("seed=%s mode=%s rtb_trips=%d per_uav=%s wall=%ss\n" % (
        a.seed, a.mode, total, {k: len(v) for k, v in logs.items()}, out["wall_s"]))
    print(a.out)


main()
