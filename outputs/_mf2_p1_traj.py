"""fix2 Part 1: replay T7/T8 (tests/test_wind_aware_trajectory_regression.py) at HEAD and trace
the searcher's wind-search state per step. DIAGNOSIS ONLY - reuses the test module's own helpers
(same seeding, same fixture), adds a read-only observer after each model.step().

usage: _mf2_p1_traj.py [steps] [wind ...]    (default 40, north south east west)
Per step: position, planner option target, coverage_y_commit, x-strip latches, pocket streak,
escape target, corridor index/targets[:3], last 15 recent y (min/max), exec action.
"""
from __future__ import annotations

import importlib.util
import os
import sys

REPO = r"E:\Projects\SAS"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))
os.environ.setdefault("MPLBACKEND", "Agg")

import common_fixed_variables as cfv  # noqa: E402
import wildfire_model as wf  # noqa: E402
from src_extension.adaptation.local_adaptation_generator import _wind_search_state  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "twtr", os.path.join(REPO, "tests", "test_wind_aware_trajectory_regression.py"))
T = importlib.util.module_from_spec(spec)
sys.modules["twtr"] = T  # dataclasses resolve the module through sys.modules
spec.loader.exec_module(T)


def main():
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    winds = sys.argv[2:] or ["north", "south", "east", "west"]
    cfv.BASE_STATION_MODE = 0  # the tests' _pin_centre_spawn
    rows = {}
    orig_step = wf.WildFireModel.step
    for wind in winds:
        log = []

        def step(self, _log=log):
            r = orig_step(self)
            try:
                vs = T._victim_searcher_id(self)
                ag = T._uav_agent(self, vs)
                ws = _wind_search_state(self, vs)
                ry = list(ws.get("recent_y_positions") or [])[-15:]
                log.append((
                    int(self.evaluation_timesteps_counter), tuple(ag.pos),
                    T._latest_wind_option_target(self), T._planner_target_from_model(self, vs),
                    ws.get("coverage_y_commit"), ws.get("west_strip_done"), ws.get("east_strip_done"),
                    ws.get("pocket_streak"), ws.get("escape_target"), ws.get("corridor_index"),
                    [tuple(round(v, 1) for v in p) for p in (ws.get("corridor_targets") or [])[:3]],
                    (min(ry), max(ry), len(ry)) if ry else None, ws.get("unresolved_victim_count"),
                    T._last_exec_action(self, vs)))
            except Exception as exc:  # observer only
                log.append(("OBS_ERR", repr(exc)[:120]))
            return r

        wf.WildFireModel.step = step
        tr = T._run_wind_simulation(wind, steps=steps, seed=T.DEFAULT_SEED)
        wf.WildFireModel.step = orig_step
        rows[wind] = (tr, log)
        print("=" * 110)
        print("WIND %s: searcher final pos %s final planner target %s; distinct option targets %d; "
              "wind_aware_actions %d" % (wind, tr.final_position, tr.final_target,
                                         len(set(tr.wind_planning_targets)), tr.wind_aware_actions))
        for r in log:
            print("  ", r)
    if "north" in rows and "south" in rows:
        a, b = rows["north"][0], rows["south"][0]
        print("N/S option-target sets equal:", set(a.wind_planning_targets) == set(b.wind_planning_targets),
              "final targets", a.final_target, b.final_target)
    if "east" in rows and "west" in rows:
        a, b = rows["east"][0], rows["west"][0]
        print("E/W option-target sets equal:", set(a.wind_planning_targets) == set(b.wind_planning_targets),
              "final targets", a.final_target, b.final_target)


if __name__ == "__main__":
    main()
