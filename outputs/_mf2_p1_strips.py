"""fix2 Part 1 (item 3): how often do the coverage x-strip pull and the y-commit override a
searcher's target, and in which direction relative to the wind? DIAGNOSIS ONLY.

Pass-through hook on local_adaptation_generator._finalize_coverage_target (called by name inside
the module only - checked: no by-name import elsewhere). Before the original runs, the x-pull it
is about to apply is recomputed on a DEEP COPY of the wind state with the function's own helpers
(_coverage_safe_x_min/_max, _mark_x_strip_progress, _west/_east_sweep_pending,
_allow_east_force), so the interior clamp is separated from the strip pull (the defect of the
sysdebug hook). After it runs: the returned target vs the clamped input, and the y-commit.
Counts per wind: x pull west/east (and whether it moved the target), y commit north/south
(and whether it moved the target). usage: _mf2_p1_strips.py -- <probe args>
"""
from __future__ import annotations

import collections
import copy
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
    import src_extension.adaptation.local_adaptation_generator as lag  # noqa: E402

    C = collections.Counter()
    ofin = lag._finalize_coverage_target

    def fin(target, wind_state, *, x_min=None, y_min, y_max, x_max=None, ax=None, ay=None,
            fire_cells=None, smoke_cells=None, step_index=None):
        pull = None
        try:
            if target is not None and lag._coverage_mode_active(wind_state):
                ws = copy.deepcopy(wind_state)
                sxmin = lag._coverage_safe_x_min(x_min) if x_min is not None else lag.COVERAGE_INTERIOR_X_MIN
                sxmax = lag._coverage_safe_x_max(x_max) if x_max is not None else lag.COVERAGE_INTERIOR_X_MAX
                tx = max(sxmin, min(sxmax, float(target[0])))
                wind = str(ws.get("last_wind_direction") or "").strip().lower()
                if lag._active_lane_axis(ws) != "x":
                    lag._mark_x_strip_progress(ws, sxmin, sxmax)
                    wgoal = float(sxmin + lag.COVERAGE_SWEEP_BAND_MARGIN)
                    egoal = float(sxmax - lag.COVERAGE_SWEEP_BAND_MARGIN)
                    east_ok = lag._allow_east_force(ws) if wind == "west" else True
                    if lag._west_sweep_pending(ws, sxmin) and ax is not None and float(ax) > sxmin + 4:
                        pull = ("west", min(tx, wgoal) != tx)
                    elif (lag._east_sweep_pending(ws, sxmax) and east_ok and ax is not None
                          and float(ax) < sxmax - 4):
                        pull = ("east", max(tx, egoal) != tx)
        except Exception as exc:  # observer only
            C["HOOK_ERR %r" % (exc,)] += 1
        r = ofin(target, wind_state, x_min=x_min, y_min=y_min, y_max=y_max, x_max=x_max, ax=ax, ay=ay,
                 fire_cells=fire_cells, smoke_cells=smoke_cells, step_index=step_index)
        wind = str(wind_state.get("last_wind_direction") or "").strip().lower() or "?"
        C["calls|%s" % wind] += 1
        if pull is not None:
            C["xpull|%s|%s|moved=%s" % (wind, pull[0], pull[1])] += 1
        commit = wind_state.get("coverage_y_commit")
        if commit in ("north", "south") and target is not None and r is not None:
            C["ycommit|%s|%s|moved=%s" % (wind, commit, float(r[1]) != float(target[1]))] += 1
        return r

    lag._finalize_coverage_target = fin
    probe = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sd_probe.py"),
                           run_name="sd_probe_module")
    sys.argv = [sys.argv[0]] + probe_args
    rc = probe["main"]()
    with open(out_path, encoding="utf-8") as fh:
        d = json.load(fh)
    d["mf2_strips"] = dict(C)
    tmp = out_path + ".hktmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(d, fh, separators=(",", ":"))
    os.replace(tmp, out_path)
    print("MF2_STRIPS_DONE %s" % dict(C))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
