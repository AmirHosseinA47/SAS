"""fix2 follow-up (maintainer: explain the yields that escaped and moved): a PASS-THROUGH observer on
UAVExecutor._hold_needs_escape, layered on outputs/_mf2_probe.py (unchanged).

For every call that returns True it records the step, the UAV, whether the dispatcher made this UAV
yield this step, and each condition of the method evaluated with the method's own helpers - pure
reads, no RNG, no state writes:
  stuck      model._uav_stuck_counts[uid] >= 3 (the counter counts ANY step with an unchanged cell,
             wildfire_model._update_uav_stuck_counts_after_move - deliberate stays included)
  boundary   the UAV stands on the grid's outer ring (_position_at_boundary)
  dir_oob    the committed direction leaves the grid (_can_check_bounds / _direction_in_bounds)
  hazard     a fire tracker on a burning / smoke cell or nearer the fire than the standoff minimum
             (_fire_tracker_hold_needs_escape)
The probe JSON (same --out) gains d["escape"] = list of those records. Value identity with the recorded
mf2ALL twin (rows_uav / rows_dec / eval / stdout sha) proves the observer is pass-through.

usage: _mf2_yield_escape_probe.py -- <the _mf2_probe / _sd_probe args ...>
"""
from __future__ import annotations

import json
import os
import runpy
import sys


def main() -> int:
    argv = sys.argv[1:]
    probe_args = argv[argv.index("--") + 1:]
    out_path = probe_args[probe_args.index("--out") + 1]
    sys.path.insert(0, r"E:\Projects\SAS")
    os.environ.setdefault("MPLBACKEND", "Agg")
    import src_extension.execution.uav_executor as ux  # noqa: E402

    records = []
    orig = ux.UAVExecutor._hold_needs_escape

    def hook(self, agent, current_dir):
        r = orig(self, agent, current_dir)
        if r:
            try:
                model = self._resolve_model(agent)
                step = int(getattr(model, "evaluation_timesteps_counter", -1))
                disp = getattr(model, "decision_dispatcher", None)
                ys = (getattr(disp, "_yield_streaks", {}) or {}).get(str(self.uav_id))
                yielded = bool(ys is not None and ys[0] == step and ys[2])
                role = str(self._read_uav_role() or "").strip().lower()
                rec = {
                    "step": step, "uid": str(self.uav_id), "role": role, "yield": yielded,
                    "yield_count": (ys[1] if ys is not None and ys[0] == step else None),
                    "pos": [int(agent.pos[0]), int(agent.pos[1])] if agent.pos is not None else None,
                    "stuck_count": self._uav_stuck_count(agent),
                    "stuck": self._uav_stuck_count(agent) >= 3,
                    "boundary": bool(self._position_at_boundary(agent)),
                    "dir_oob": bool(self._can_check_bounds(agent)
                                    and not self._direction_in_bounds(agent, current_dir)),
                    "hazard": bool(role == "fire_tracker" and self._fire_tracker_hold_needs_escape(agent)),
                }
            except Exception as exc:  # observer only
                rec = {"HOOK_ERR": repr(exc)[:200]}
            records.append(rec)
        return r

    ux.UAVExecutor._hold_needs_escape = hook
    sys.argv = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "_mf2_probe.py"), "--"] + probe_args
    try:
        runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as exc:
        rc = int(exc.code or 0)
    else:
        rc = 0
    with open(out_path, encoding="utf-8") as fh:
        d = json.load(fh)
    d["escape"] = records
    tmp = out_path + ".estmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(d, fh, separators=(",", ":"))
    os.replace(tmp, out_path)
    print("MF2_ESCAPE_DONE %d records" % len(records))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
