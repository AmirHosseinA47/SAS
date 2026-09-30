"""fix3a round 2 - read-only reproduction: the two wind-trajectory regression tests under the global state the full
suite leaves behind (outputs/_fx3r_state_suite_*.json: variable wind west->east p 0.8, 2 UAVs, 3 victims,
BATCH_SIZE 99999), with SEARCHER_FIRE_ROUTE_OWNER / SEARCHER_ROUTE_BOUNDED_WAIT on and off.
usage (repo root): PYTHONPATH=tests _fx3r_traj_polluted.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))

import common_fixed_variables as cfv  # noqa: E402
import wildfire_model as wf  # noqa: E402
import test_wind_aware_trajectory_regression as T  # noqa: E402

POLLUTED = {"FIXED_WIND": False, "FIRST_DIR": "west", "FIRST_DIR_PROB": 0.8, "SECOND_DIR": "east",
            "NUM_AGENTS": 2, "NUM_VICTIMS": 3, "BATCH_SIZE": 99999}


class _MP:
    def setattr(self, obj, name, value, raising=True):
        setattr(obj, name, value)


def main():
    for mod in (cfv, wf):
        for k, v in POLLUTED.items():
            setattr(mod, k, v)
    T._pin_centre_spawn(_MP())
    for owner, bounded in ((1, 1), (0, 0), (1, 0), (0, 1)):
        cfv.SEARCHER_FIRE_ROUTE_OWNER, cfv.SEARCHER_ROUTE_BOUNDED_WAIT = owner, bounded
        res = {}
        for wind in ("north", "south"):
            tr = T._run_wind_simulation(wind, steps=40, seed=T.DEFAULT_SEED)
            res[wind] = tr
        ok = True
        try:
            T._assert_trajectory_or_region_diverged(res["north"], res["south"])
        except AssertionError:
            ok = False
        print("owner=%d bounded=%d  north final %s  south final %s  diverged: %s" % (
            owner, bounded, res["north"].final_target, res["south"].final_target, ok))
        print("   north positions", res["north"].positions[:16])


if __name__ == "__main__":
    main()
