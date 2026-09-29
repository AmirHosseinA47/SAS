"""fix2 Part 1 (item 3b): the searcher-exposure fixtures under candidate near-field ranges K.
NO SOURCE EDIT - the gate range is patched in-process exactly as the pytest plugin does
(outputs/_mf2_p1_proto_plugin.py), with and without the 3a y-commit prototype.

Runs the two fixtures of tests/test_victim_searcher_scenario_matrix.py that bound
strict_fire_smoke_steps (<= 2): test_no_crash_zero_victims (edge case, north, 50 steps, depot pinned
off) and test_scenario_a_no_5x5_camping_east (A, east, 50 steps), plus the T7/T8 verdicts
(outputs/_mf2_p1_proto3.py logic) for each K.
usage: _mf2_p1_krange.py <K> [ycommit]     (K = 99 means the shipped always-retreat)
"""
from __future__ import annotations

import os
import sys

REPO = r"E:\Projects\SAS"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))
sys.path.insert(0, os.path.join(REPO, "outputs"))
os.environ.setdefault("MPLBACKEND", "Agg")


def main():
    k = int(sys.argv[1])
    with_y = len(sys.argv) > 2 and sys.argv[2] == "ycommit"
    os.environ["MF2_PROTO"] = "ycommit" if with_y else "none"
    import _mf2_p1_proto_plugin  # noqa: F401  (installs the y-commit prototype if asked)
    import common_fixed_variables as cfv
    import src_extension.execution.uav_executor as ux
    from victim_searcher_scenario_validation import EDGE_CASES, SCENARIO_A, run_scenario

    orig = ux.UAVExecutor._hazard_retreat_range

    def rng(self):
        r = orig(self)
        return k if r >= 99 else r

    ux.UAVExecutor._hazard_retreat_range = rng
    if "approach_all" in sys.argv[2:]:
        # 3b variant: the NEAR-FIELD rule also covers the pathfinding-routed retarget, which bypasses the
        # gate (uav_executor.py:419-426): within K of a strict hazard, a move that brings the searcher
        # closer to it is replaced by the gate's retreat.
        oret = ux.UAVExecutor._attempt_pathfinding_toward_target

        def retarget(self, agent, target, **kw):
            routed = oret(self, agent, target, **kw)
            if routed is None:
                return None
            d, lab = routed
            pos = getattr(agent, "pos", None)
            if pos is not None:
                here = (int(pos[0]), int(pos[1]))
                nxt = self._next_cell_for_direction(agent, d)
                dh = self._min_strict_hazard_distance(here)
                if nxt is not None and dh <= k and self._min_strict_hazard_distance(nxt) < dh:
                    retreat = self._retreat_to_safe_interior_direction(agent)
                    if retreat is not None:
                        return retreat, lab
            return d, lab

        ux.UAVExecutor._attempt_pathfinding_toward_target = retarget
    saved = getattr(cfv, "BASE_STATION_MODE", None)
    cfv.BASE_STATION_MODE = 0
    r1 = run_scenario(scenario_name="edge", scenario=EDGE_CASES[0], wind="north", steps=50)
    cfv.BASE_STATION_MODE = saved
    r2 = run_scenario(scenario_name="A", scenario=SCENARIO_A, wind="east", steps=50)
    print("K=%d ycommit=%s  zero_victims strict_fire_smoke_steps=%s (<=2)  scenarioA_east strict=%s camping_5x5=%s "
          "unique_positions=%s" % (k, with_y, r1.metrics.get("strict_fire_smoke_steps"),
                                   r2.metrics.get("strict_fire_smoke_steps"), r2.metrics.get("camping_5x5"),
                                   r2.metrics.get("unique_positions")))


if __name__ == "__main__":
    main()
