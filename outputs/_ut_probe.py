"""untune Part 3 probe: outputs/_fb3_probe.py (UNCHANGED, run in-process) plus read-only untune recorders.

usage: _ut_probe.py [--crn] [--hazard] -- <_sd_probe.py args ...>     (exactly _fb3_probe.py's interface)

Adds d["ut"] to the probe JSON. Every recorder only READS model state after the step has run: no RNG draw, no
write into the model (outputs/untune_part1.txt 7.3 / 11.10, the attribution counts):
  rows      per step: [step, privileged searcher count (_count_unresolved_victims), known searcher count
            (briefing - detected), privileged mission count (the shipped alive_victims_remaining rule),
            known mission count (briefing - rescued - observed dead), mission phase under the privileged count,
            under the known count, the phase the run actually holds]. The two phases are derived with the
            run's own fail-safe mode / active rescues / fire severity (MissionGoalModel._derive_mission_phase).
  sweep     per searcher, the untuned x-sweep first-strip latch at the end (None at switch 0 or along-wind)
  corridor  calls / firings of the escape x bounds: untuned floor fired, untuned cap below safe_x_max, shipped
            cap below safe_x_max
  switch    {"raw": cfv.SEARCHER_UNTUNED, "on": agents.searcher_untuned()}
  errors    the first 20 observer exceptions (an observer never stops a run)
"""
from __future__ import annotations

import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PHASES = ("exploration", "evacuation", "rescue_active", "degraded_operation", "emergency")


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _ut_probe.py [--crn] [--hazard] -- <_sd_probe.py args>", file=sys.stderr)
        return 2
    probe_args = argv[argv.index("--") + 1:]
    out_path = probe_args[probe_args.index("--out") + 1]
    repo = r"E:\Projects\SAS"
    for i, a in enumerate(probe_args):
        if a == "--repo":
            repo = probe_args[i + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.adaptation.local_adaptation_generator as gen  # noqa: E402
    from src_extension.knowledge.mission_goal_model import MissionGoalModel  # noqa: E402

    rec = {"rows": [], "errors": [], "model": None,
           "corridor": {"bounds_calls": 0, "floor_fired": 0, "untuned_cap_fired": 0, "cap_calls": 0,
                        "shipped_cap_fired": 0}}

    def err(exc):
        if len(rec["errors"]) < 20:
            rec["errors"].append(repr(exc)[:200])

    o_bounds = gen._corridor_target_x_bounds_untuned

    def bounds(wind_state, x_min, x_max):
        r = o_bounds(wind_state, x_min, x_max)
        try:
            c = rec["corridor"]
            c["bounds_calls"] += 1
            c["floor_fired"] += r[0] is not None
            c["untuned_cap_fired"] += r[1] < gen._coverage_safe_x_max(x_max)
        except Exception as exc:
            err(exc)
        return r

    o_cap = gen._corridor_target_x_cap

    def cap(wind_state, x_min, x_max, *, coverage_active):
        r = o_cap(wind_state, x_min, x_max, coverage_active=coverage_active)
        try:
            rec["corridor"]["cap_calls"] += 1
            rec["corridor"]["shipped_cap_fired"] += r < gen._coverage_safe_x_max(x_max)
        except Exception as exc:
            err(exc)
        return r

    gen._corridor_target_x_bounds_untuned = bounds
    gen._corridor_target_x_cap = cap

    def privileged_mission(model):
        """The shipped _build_mission_goal_runtime_context alive_victims_remaining rule, read-only."""
        n = 0
        managed = getattr(model, "managed_victims", None) or {}
        for vid, marker in (getattr(model, "victim_marker_agents", None) or {}).items():
            state = managed.get(vid)
            ms = str(getattr(marker, "status", "") or "").strip().lower()
            ss = str(getattr(state, "status", "") or "").strip().lower() if state is not None else ""
            dead = ms == "dead" or ss == "dead"
            rescued = bool(getattr(state, "rescued", False) if state is not None else False) or ms == "rescued"
            unreach = bool(getattr(state, "unreachable", False) if state is not None else False) or ms == "unreachable"
            if not (dead or rescued or unreach):
                n += 1
        return n

    ostep = wf.WildFireModel.step

    def step(self):
        r = ostep(self)
        rec["model"] = self
        try:
            pf = gen._count_unresolved_victims(self)
            kf = gen._count_known_undetected_victims(self)
            pm = privileged_mission(self)
            km = gen._count_known_mission_unresolved(self)
            goals = getattr(self, "mission_goal_model", None)
            dm = dict(getattr(goals, "dynamic_metrics", None) or {})

            def phase(alive):
                return MissionGoalModel._derive_mission_phase(
                    fail_safe_mode=str(dm.get("active_fail_safe_mode", "normal") or "normal"),
                    active_rescues=int(dm.get("active_rescues", 0) or 0), alive_victims=int(alive),
                    fire_severity=float(dm.get("fire_severity_estimate", 0.0) or 0.0))

            code = {p: i for i, p in enumerate(PHASES)}
            rec["rows"].append([int(getattr(self, "evaluation_timesteps_counter", 0) or 0), pf, kf, pm, km,
                                code.get(phase(pm), -1), code.get(phase(km), -1),
                                code.get(str(getattr(goals, "mission_phase", "") or ""), -1)])
        except Exception as exc:
            err(exc)
        return r

    wf.WildFireModel.step = step

    fb3 = runpy.run_path(os.path.join(HERE, "_fb3_probe.py"), run_name="fb3_probe_module")
    sys.argv = [os.path.join(HERE, "_fb3_probe.py")] + argv
    rc = fb3["main"]()
    if rc != 0:
        return rc
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        m = rec["model"]
        sweep = {}
        if m is not None:
            for uid in gen.resolve_victim_searcher_uav_ids(m):
                latch = (getattr(m, "_wind_search_target_state", {}) or {}).get(uid, {}).get("untuned_x_sweep_first")
                sweep[uid] = list(latch) if isinstance(latch, (list, tuple)) else latch
        d["ut"] = {"probe": "ut_probe v1", "phases": list(PHASES), "rows": rec["rows"], "sweep": sweep,
                   "corridor": rec["corridor"], "errors": rec["errors"],
                   "switch": {"raw": getattr(cfv, "SEARCHER_UNTUNED", None), "on": am.searcher_untuned()}}
        tmp = out_path + ".uttmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("UT WRITE FAILED %r" % (exc,), file=sys.stderr)
        return 7
    return rc


if __name__ == "__main__":
    sys.exit(main())
