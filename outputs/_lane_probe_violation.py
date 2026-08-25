"""Part 1 probe #3: does the lane filter actually hold at the OUTPUT?

_lane_allows_cell is a hard candidate filter inside
_pick_global_coverage_escape_target and _generate_corridor_waypoints, but the
target then passes through _finalize_coverage_target, which is lane-unaware.
This probe wraps _compute_wind_aware_search_target and records, per emitted
target, whether it lies inside the emitting searcher's own lane, plus the
coverage_y_commit latch state that drives the override.
"""
from __future__ import annotations

import contextlib
import io as _io
import os
import random
import sys

os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
import src_extension.adaptation.local_adaptation_generator as lag
from wildfire_model import WildFireModel

WIND = sys.argv[1] if len(sys.argv) > 1 else "east"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 101
STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 120
NUM_VS = int(sys.argv[4]) if len(sys.argv) > 4 else 2

PARAMS = {
    "NUM_AGENTS": 5, "NUM_VICTIMS": 3, "NUM_FIREFIGHTERS": 3,
    "WIND_DIRECTION": WIND, "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75,
    "PROBABILITY_MAP": False,
    "NUM_FIRE_TRACKERS": 5 - NUM_VS, "NUM_VICTIM_SEARCHERS": NUM_VS,
}

RECORDS = []


def install_shim():
    gen = lag.LocalAdaptationSpaceGenerator
    original = gen._compute_wind_aware_search_target

    def wrapped(self, runtime_models, uav_id, wind_direction, wind_vector, *a, **kw):
        out = original(self, runtime_models, uav_id, wind_direction, wind_vector, *a, **kw)
        sim = lag._simulation_from_runtime(runtime_models)
        if sim is None:
            return out
        h = int(getattr(sim, "HEIGHT", 50))
        w = int(getattr(sim, "WIDTH", 50))
        lane = lag._searcher_crosswind_lane(
            sim, uav_id, lag._wind_label_from_vector(wind_vector), 0, h - 1, 0, w - 1
        )
        ws = lag._wind_search_state(sim, uav_id)
        inside = None
        if out is not None:
            inside = lag._lane_allows_cell(
                lane, int(round(out[0])), int(round(out[1]))
            )
        RECORDS.append({
            "step": int(getattr(sim, "evaluation_timesteps_counter", 0) or 0),
            "uav": str(uav_id),
            "lane": None if lane is None else tuple(lane),
            "target": None if out is None else (round(float(out[0]), 1), round(float(out[1]), 1)),
            "inside": inside,
            "y_commit": ws.get("coverage_y_commit"),
            "coverage_active": lag._coverage_mode_active(ws),
            "unresolved": int(ws.get("unresolved_victim_count", 0) or 0),
        })
        return out

    gen._compute_wind_aware_search_target = wrapped


def main():
    install_shim()
    rng = random.Random(SEED)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    lag.apply_scenario_config(cfv, wf, **PARAMS)

    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(STEPS):
            model.step()

    print("=" * 78)
    print("LANE-VIOLATION PROBE  wind=%s seed=%d steps=%d searchers=%d"
          % (WIND, SEED, STEPS, NUM_VS))
    print("=" * 78)
    print("total target emissions recorded: %d" % len(RECORDS))

    by_uav = {}
    for r in RECORDS:
        by_uav.setdefault(r["uav"], []).append(r)

    for uav in sorted(by_uav):
        rs = by_uav[uav]
        emitted = [r for r in rs if r["target"] is not None]
        outside = [r for r in emitted if r["inside"] is False]
        lane = rs[-1]["lane"]
        commits = {}
        for r in rs:
            commits[r["y_commit"]] = commits.get(r["y_commit"], 0) + 1
        print("")
        print("uav %s  lane=%s" % (uav, "None" if lane is None else "%s[%d..%d]" % lane))
        print("   emissions=%d  targets_outside_own_lane=%d (%.1f%%)"
              % (len(emitted), len(outside),
                 100.0 * len(outside) / max(1, len(emitted))))
        print("   coverage_y_commit histogram: %s" % commits)
        first_commit = next((r for r in rs if r["y_commit"] in ("north", "south")), None)
        if first_commit:
            print("   first y_commit latch at step %d -> %r"
                  % (first_commit["step"], first_commit["y_commit"]))
        if outside:
            print("   first 6 out-of-lane targets:")
            for r in outside[:6]:
                print("      step=%-4d target=%s lane=%s y_commit=%r cov_active=%s"
                      % (r["step"], r["target"],
                         "%s[%d..%d]" % r["lane"] if r["lane"] else None,
                         r["y_commit"], r["coverage_active"]))
            ys = sorted({r["target"][1] for r in outside})
            xs = sorted({r["target"][0] for r in outside})
            print("   distinct out-of-lane target y values: %s" % ys[:20])
            print("   distinct out-of-lane target x values: %s" % xs[:20])

    # cross-searcher target collisions
    per_step = {}
    for r in RECORDS:
        if r["target"] is None:
            continue
        per_step.setdefault(r["step"], {})[r["uav"]] = r["target"]
    collisions = [s for s, d in per_step.items()
                  if len(d) > 1 and len(set(d.values())) < len(d)]
    print("")
    print("steps where two searchers held the SAME target: %d / %d"
          % (len(collisions), len(per_step)))
    if collisions:
        for s in collisions[:6]:
            print("   step=%d %s" % (s, per_step[s]))


if __name__ == "__main__":
    main()
