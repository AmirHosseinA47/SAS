"""fix2 Part 1: why does the B/west searcher loop at the east edge? DIAGNOSIS ONLY.

Pass-through hooks around outputs/_sd_probe.py (same pattern as _mf2_p1_hooks.py): for every
victim searcher, record per call of
  UAVExecutor._safe_victim_sweep_target  - position, sweep state BEFORE, returned target
  UAVExecutor._apply_victim_searcher_hazard_gate - direction in / out, label in / out
  UAVExecutor._choose_best_direction (target_kind victim) - target in, direction out
  UAV.move - moved or refused
inside the step windows given by --win a-b (repeatable). Nothing is mutated; the state copy
is taken with dict(). usage: _mf2_p1_sweep.py --win 100-140 --win 265-300 -- <probe args>
"""
from __future__ import annotations

import json
import os
import runpy
import sys


def main() -> int:
    argv = sys.argv[1:]
    cut = argv.index("--")
    own, probe_args = argv[:cut], argv[cut + 1:]
    wins = []
    for i, a in enumerate(own):
        if a == "--win":
            lo, hi = own[i + 1].split("-")
            wins.append((int(lo), int(hi)))
    out_path = probe_args[probe_args.index("--out") + 1]
    repo = r"E:\Projects\SAS"
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.execution.uav_executor as ux  # noqa: E402

    cur = {"step": 0}
    EV = []

    def inwin():
        return any(lo <= cur["step"] <= hi for lo, hi in wins)

    ostep = wf.WildFireModel.step

    def step(self):
        cur["step"] += 1
        return ostep(self)

    wf.WildFireModel.step = step

    def searcher(ex):
        try:
            return str(ex._read_uav_role() or "") in ("victim_searcher", "victim_search")
        except Exception:
            return False

    osafe = ux.UAVExecutor._safe_victim_sweep_target

    def safe(self, agent, state, model, sector_bounds, height, width, step_, pos):
        before = dict(state)
        r = osafe(self, agent, state, model, sector_bounds, height, width, step_, pos)
        if inwin():
            EV.append([cur["step"], "SAFE", str(self.uav_id), list(pos) if pos else None,
                       {k: before.get(k) for k in ("sweep_x", "sweep_y", "sweep_dir", "wind_direction")},
                       sector_bounds, list(r)])
        return r

    ux.UAVExecutor._safe_victim_sweep_target = safe

    ogate = ux.UAVExecutor._apply_victim_searcher_hazard_gate

    def gate(self, agent, chosen_dir, action):
        r = ogate(self, agent, chosen_dir, action)
        if inwin() and searcher(self):
            EV.append([cur["step"], "GATE", str(self.uav_id), list(agent.pos), chosen_dir, action, list(r)])
        return r

    ux.UAVExecutor._apply_victim_searcher_hazard_gate = gate

    ochoose = ux.UAVExecutor._choose_best_direction

    def choose(self, agent, target, *a, **k):
        r = ochoose(self, agent, target, *a, **k)
        if inwin() and searcher(self):
            EV.append([cur["step"], "CHOOSE", str(self.uav_id), list(agent.pos),
                       list(target) if target is not None else None, k.get("target_kind"), r])
        return r

    ux.UAVExecutor._choose_best_direction = choose

    omove = am.UAV.move

    def move(self):
        before = self.pos
        d = int(self.selected_dir)
        r = omove(self)
        if inwin() and str(getattr(self, "current_role", "")) == "victim_searcher":
            EV.append([cur["step"], "MOVE", str(self.unique_id), list(before), d, bool(r),
                       str(getattr(self, "execution_action", ""))])
        return r

    am.UAV.move = move

    probe = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sd_probe.py"),
                           run_name="sd_probe_module")
    sys.argv = [sys.argv[0]] + probe_args
    rc = probe["main"]()
    with open(out_path, encoding="utf-8") as fh:
        d = json.load(fh)
    d["mf2_sweep"] = EV
    tmp = out_path + ".hktmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(d, fh, separators=(",", ":"))
    os.replace(tmp, out_path)
    print("MF2_SWEEP_DONE %d events" % len(EV))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
