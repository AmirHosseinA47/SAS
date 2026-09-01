"""BFS cost at the DISPATCH call frequency specifically.

The prior rounds measured BFS cost as negligible when run every step for
every en-route unit.  This measures the two pieces a dispatch-time
reachability test would actually pay for, at the fire sizes a 240-step
run reaches:

  * _fire_cells()               - one scan of the schedule per snapshot
  * _path_exists_avoiding_fire() - one BFS per candidate per dispatch

and compares them to the cost of a single model.step() at the same point in
the run, which is the only honest denominator.

    python outputs/_dr_cost.py --wind east --seed 505 --steps 240
"""
from __future__ import annotations
import argparse, contextlib, io as _io, os, random, sys, time
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS

SAMPLE_AT = (30, 60, 90, 120, 150, 180, 210, 240)
REPS = 200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wind", default="east")
    ap.add_argument("--seed", type=int, default=505)
    ap.add_argument("--steps", type=int, default=240)
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS["D"]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"],
              "WIND_DIRECTION": a.wind, "BATCH_SIZE": 300,
              "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft}
    rng = random.Random(a.seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    print("%5s %7s %11s %13s %13s %12s"
          % ("step", "fires", "step_ms", "fire_cells_ms", "bfs_open_ms", "bfs_closed_ms"))
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        rows = []
        for s in range(1, a.steps + 1):
            t0 = time.perf_counter()
            model.step()
            step_ms = 1000.0 * (time.perf_counter() - t0)
            if s not in SAMPLE_AT:
                continue
            mk = None
            for m in (getattr(model, "firefighter_marker_agents", {}) or {}).values():
                if getattr(m, "pos", None) is not None:
                    mk = m
                    break
            if mk is None:
                continue
            t0 = time.perf_counter()
            for _ in range(REPS):
                fc = mk._fire_cells()
            fc_ms = 1000.0 * (time.perf_counter() - t0) / REPS
            src = (int(mk.pos[0]), int(mk.pos[1]))
            # a far corner - the worst realistic dispatch geometry
            far = (49 - src[0], 49 - src[1])
            t0 = time.perf_counter()
            for _ in range(REPS):
                mk._path_exists_avoiding_fire(src, far, fc)
            open_ms = 1000.0 * (time.perf_counter() - t0) / REPS
            # TRUE worst case: a destination the search can never match, so
            # the flood fill exhausts the entire reachable component before
            # returning False.  out_of_bounds is tested before the dst
            # comparison in _path_exists_avoiding_fire, so an out-of-bounds
            # dst is never matched and never short-circuits.
            # (An earlier version of this benchmark walled off the SOURCE's
            # four neighbours instead, which makes the queue drain on the
            # first iteration - the fastest case, not the slowest.)
            t0 = time.perf_counter()
            for _ in range(REPS):
                mk._path_exists_avoiding_fire(src, (-1, -1), fc)
            closed_ms = 1000.0 * (time.perf_counter() - t0) / REPS
            rows.append((s, len(fc), step_ms, fc_ms, open_ms, closed_ms))
    for r in rows:
        print("%5d %7d %11.3f %13.4f %13.4f %12.4f" % r)


main()
