"""No-monkeypatch control for _irh_probe.py. Same params, same fftrace shape.

Its only job is to prove the probe is non-perturbing: the position trace and
the evaluation must match the probe run cell for cell.
"""
from __future__ import annotations
import argparse, contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation, _resolve_role_count_params

FFTRACE, EVALS = [], []


def _mfd(cell, fires):
    if not fires:
        return 999
    cx, cy = cell
    return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fires)


def _fire_cells(model):
    out = set()
    for a in model.schedule.agents:
        if type(a) is am.Fire and a.is_burning():
            p = getattr(a, "pos", None)
            if p is not None:
                out.add((int(p[0]), int(p[1])))
    return out


def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for s in range(1, steps + 1):
            model.step()
            fires = _fire_cells(model)
            for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                pos = getattr(m, "pos", None)
                cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                mr = getattr(m, "movement_reason", None) or {}
                FFTRACE.append({
                    "seed": seed, "step": s, "ff": fid,
                    "pos": (list(cell) if cell else None),
                    "dead": bool(getattr(m, "dead", False)),
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "target": (list(m.target_pos)
                               if getattr(m, "target_pos", None) else None),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "stalled": bool(getattr(m, "_idle_retreat_stalled", False)),
                    "mfd": (_mfd(cell, fires) if cell else None),
                    "cat": str(mr.get("category", "")),
                })
        ev = _build_evaluation(model, None, steps, params)
        ev["seed"] = seed
        EVALS.append(ev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", default="101")
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--tag", default="ctl")
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    if a.roles == "half":
        ft = n // 2 or 1
        vs = n - ft
    else:
        ft, vs = _resolve_role_count_params(n, None, None)
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"],
              "WIND_DIRECTION": a.wind, "BATCH_SIZE": 300,
              "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}
    for seed in [int(s) for s in a.seeds.split(",")]:
        run(seed, params, a.steps)
        sys.stderr.write("seed %s done\n" % seed)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_irh_%s.json" % a.tag)
    with open(p, "w") as f:
        json.dump({"fftrace": FFTRACE, "evals": EVALS}, f,
                  separators=(",", ":"), default=str)
    print(p)


main()
