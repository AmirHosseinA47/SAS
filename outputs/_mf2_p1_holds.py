"""fix2 Part 1 (item 2): where do the moving holds come from? DIAGNOSIS ONLY.

Pass-through hooks around outputs/_sd_probe.py:
  decision_dispatcher._adjust_local_path_for_fail_safe - marks (step, uav) whose path the
      fail-safe layer rewrote to next_action "hold" (the SAFETY_FIRST / EMERGENCY safe_hold);
  UAVExecutor._execute_hold - every executor hold: role, fail-safe-origin or not, returned label;
  UAVExecutor._fire_tracker_lateral_hold_target - the flank hold's target: a lateral neighbour
      (a patrol step) or None (the hold target is then the tracker's own cell);
  UAV.move - the step's executor label and whether the UAV moved.
Counters only; nothing is mutated. usage: _mf2_p1_holds.py -- <probe args>
"""
from __future__ import annotations

import collections
import json
import os
import runpy
import sys


def main() -> int:
    argv = sys.argv[1:]
    probe_args = argv[argv.index("--") + 1:]
    out_path = probe_args[probe_args.index("--out") + 1]
    repo = r"E:\Projects\SAS"
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.execution.uav_executor as ux  # noqa: E402
    import src_extension.execution.decision_dispatcher as dd  # noqa: E402

    cur = {"step": 0}
    FS = set()
    C = collections.Counter()
    lateral_last = {}

    ostep = wf.WildFireModel.step

    def step(self):
        cur["step"] += 1
        return ostep(self)

    wf.WildFireModel.step = step

    oadj = dd._adjust_local_path_for_fail_safe

    def adj(path, fail_safe_decision, override_active):
        r = oadj(path, fail_safe_decision, override_active)
        p, ok = r
        if ok and p is not None and str(getattr(p, "next_action", "")).lower() == "hold" and \
                str(getattr(path, "next_action", "")).lower() != "hold":
            FS.add((cur["step"], str(getattr(path, "uav_id", ""))))
        return r

    dd._adjust_local_path_for_fail_safe = adj

    ohold = ux.UAVExecutor._execute_hold

    def ex_hold(self, agent, current_dir):
        r = ohold(self, agent, current_dir)
        role = str(self._read_uav_role() or "")
        origin = "failsafe" if (cur["step"], str(self.uav_id)) in FS else "planner"
        C["execute_hold|%s|%s|%s" % (role, origin, r[1])] += 1
        return r

    ux.UAVExecutor._execute_hold = ex_hold

    olat = ux.UAVExecutor._fire_tracker_lateral_hold_target

    def lat(self, agent, fire_cells):
        r = olat(self, agent, fire_cells)
        lateral_last[str(self.uav_id)] = (cur["step"], r is not None)
        C["flank_hold_target|%s" % ("lateral" if r is not None else "own_cell")] += 1
        return r

    ux.UAVExecutor._fire_tracker_lateral_hold_target = lat

    omove = am.UAV.move

    def move(self):
        label = str(getattr(self, "execution_action", "") or "")
        moved = omove(self)
        low = label.lower()
        if low == "fire_flank_hold":
            st, lateral = lateral_last.get(str(self.unique_id), (None, None))
            kind = ("lateral" if lateral else "own_cell") if st == cur["step"] else "unknown"
            C["move|fire_flank_hold|%s|moved=%s" % (kind, moved)] += 1
        elif low == "hold":
            origin = "failsafe" if (cur["step"], str(self.unique_id)) in FS else "planner"
            C["move|hold|%s|%s|moved=%s" % (origin, str(getattr(self, "current_role", "")), moved)] += 1
        return moved

    am.UAV.move = move

    probe = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sd_probe.py"),
                           run_name="sd_probe_module")
    sys.argv = [sys.argv[0]] + probe_args
    rc = probe["main"]()
    with open(out_path, encoding="utf-8") as fh:
        d = json.load(fh)
    d["mf2_holds"] = dict(C)
    tmp = out_path + ".hktmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(d, fh, separators=(",", ":"))
    os.replace(tmp, out_path)
    print("MF2_HOLDS_DONE %s" % dict(C))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
