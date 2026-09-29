"""fix2 Part 1 (item 3b): WHY does the zero-victims fixture's searcher stand on fire/smoke when the
always-retreat is narrowed? NO SOURCE EDIT - in-process patch of the gate range as in
outputs/_mf2_p1_krange.py, plus read-only per-step observation of the searcher.

Per step: position before -> after, the executed label, the gate's direction in/out, the strict hazard
level of the cell BEFORE the move (was the searcher already on a hazard?) and AFTER it (did it step
onto one, or did the hazard come to it?), and the nearest strict hazard distance.
usage: _mf2_p1_exposure_trace.py <K>
"""
from __future__ import annotations

import os
import sys

REPO = r"E:\Projects\SAS"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))
os.environ.setdefault("MPLBACKEND", "Agg")


def main():
    k = int(sys.argv[1])
    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    import src_extension.execution.uav_executor as ux
    import victim_searcher_scenario_validation as vsv

    orig_rng = ux.UAVExecutor._hazard_retreat_range

    def rng(self):
        r = orig_rng(self)
        return k if r >= 99 else r

    ux.UAVExecutor._hazard_retreat_range = rng
    RET = []
    if "approach_all" in sys.argv[2:]:
        oret = ux.UAVExecutor._attempt_pathfinding_toward_target

        def retarget(self, agent, target, **kw):
            routed = oret(self, agent, target, **kw)
            if routed is None:
                return None
            d, lab = routed
            pos = getattr(agent, "pos", None)
            out = d
            if pos is not None:
                here = (int(pos[0]), int(pos[1]))
                nxt = self._next_cell_for_direction(agent, d)
                dh = self._min_strict_hazard_distance(here)
                dn = self._min_strict_hazard_distance(nxt) if nxt is not None else None
                if nxt is not None and dh <= k and dn < dh:
                    retreat = self._retreat_to_safe_interior_direction(agent)
                    if retreat is not None:
                        out = retreat
                RET.append((here, target, d, dh, dn, out))
            return out, lab

        ux.UAVExecutor._attempt_pathfinding_toward_target = retarget

    rows = []
    cur = {"step": 0, "gate": []}
    ogate = ux.UAVExecutor._apply_victim_searcher_hazard_gate

    def gate(self, agent, chosen_dir, action):
        r = ogate(self, agent, chosen_dir, action)
        cur["gate"].append((chosen_dir, r[0]))
        return r

    ux.UAVExecutor._apply_victim_searcher_hazard_gate = gate

    ostep = wf.WildFireModel.step

    def step(self):
        cur["step"] += 1
        cur["gate"] = []
        s = [a for a in self.schedule.agents if type(a) is am.UAV
             and str(getattr(a, "current_role", "")) == "victim_searcher"]
        before = tuple(s[0].pos) if s else None
        ex = ux.UAVExecutor(uav_id=str(s[0].unique_id), model=self, agent=s[0]) if s else None
        lvl_before = ex._strict_victim_hazard_level(before) if ex and before else None
        r = ostep(self)
        if s:
            after = tuple(s[0].pos)
            ex2 = ux.UAVExecutor(uav_id=str(s[0].unique_id), model=self, agent=s[0])
            rows.append((cur["step"], before, after, str(getattr(s[0], "execution_action", "")),
                         list(cur["gate"]), lvl_before, ex2._strict_victim_hazard_level(after),
                         ex2._strict_victim_hazard_level(before) if before else None,
                         round(ex2._min_strict_hazard_distance(after), 1)))
        return r

    wf.WildFireModel.step = step
    cfv.BASE_STATION_MODE = 0
    res = vsv.run_scenario(scenario_name="edge", scenario=vsv.EDGE_CASES[0], wind="north", steps=50)
    print("K=%d strict_fire_smoke_steps=%s" % (k, res.metrics.get("strict_fire_smoke_steps")))
    print("step before -> after | label | gate (in,out)... | hazard lvl: before-cell@start, after-cell@end, "
          "before-cell@end | nearest hazard after")
    for r in rows:
        mark = "  <== ON HAZARD" if r[6] and r[6] > 0 else ""
        print(r, mark)
    print("RETARGET CALLS (here, target, dir, d_here, d_next, dir_out):", len(RET))
    for x in RET[-30:]:
        print("  ", x)


if __name__ == "__main__":
    main()
