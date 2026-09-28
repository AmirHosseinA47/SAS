"""sysdebug Part 1: per-step searcher wind_state + corridor generation for one wind.

Same setup as tests/test_wind_aware_trajectory_regression.py (_run_wind_simulation,
BASE_STATION_MODE 0 pin). Wraps LocalAdaptationSpaceGenerator._generate_corridor_waypoints
and _finalize_coverage_target pass-through to record their inputs/outputs. Read-only.

usage: _sd_p1_windstate.py <wind> [steps]
"""
import os
import sys

sys.path.insert(0, r"E:\Projects\SAS")
sys.path.insert(0, r"E:\Projects\SAS\tests")
os.environ.setdefault("MPLBACKEND", "Agg")

import common_fixed_variables as cfv  # noqa: E402
import test_wind_aware_trajectory_regression as T  # noqa: E402
import src_extension.adaptation.local_adaptation_generator as lag  # noqa: E402

LOG = []

_orig_gen = lag.LocalAdaptationSpaceGenerator._generate_corridor_waypoints
_orig_fin = lag._finalize_coverage_target


def _gen(self, **kw):
    out = _orig_gen(self, **kw)
    LOG.append(("corridor", kw.get("wind_direction"), kw.get("force_interior"),
                (round(kw.get("fx"), 1), round(kw.get("fy"), 1)), (kw.get("ax"), kw.get("ay")),
                [tuple(p) for p in (out or [])]))
    return out


def _fin(target, wind_state, **kw):
    out = _orig_fin(target, wind_state, **kw)
    LOG.append(("finalize", tuple(target) if target else None, tuple(out) if out else None,
                wind_state.get("coverage_y_commit")))
    return out


lag.LocalAdaptationSpaceGenerator._generate_corridor_waypoints = _gen
lag._finalize_coverage_target = _fin

KEYS = ("current_target", "corridor_index", "coverage_y_commit", "force_interior_retarget",
        "escape_target", "force_sweep", "west_strip_done", "east_strip_done", "active_lane_axis",
        "coverage_mode", "force_coverage_escape", "pocket_streak", "last_wind_direction")


def main():
    wind = sys.argv[1]
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    cfv.BASE_STATION_MODE = 0
    T._seed_deterministic_environment(wind, seed=T.DEFAULT_SEED)
    model = T.WildFireModel()
    T._apply_model_wind(model, wind)
    T._configure_no_live_victims(model)
    vs = T._victim_searcher_id(model)
    agent = T._uav_agent(model, vs)
    for s in range(steps):
        LOG.clear()
        model.step()
        st = (getattr(model, "_wind_search_target_state", {}) or {}).get(vs, {})
        print("STEP", s + 1, "pos", agent.pos, "windopt", T._latest_wind_option_target(model),
              {k: st.get(k) for k in KEYS if k in st})
        for row in LOG:
            print("   ", row)


if __name__ == "__main__":
    main()
