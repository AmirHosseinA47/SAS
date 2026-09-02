"""Defect #7 Part-2 provenance probe: WHICH source sustains the fail-safe mode?

SafetyChecker.extract_fail_safe_reasons unions three private helpers:
    _reasons_from_analysis(analysis_snapshot)     <- independent evidence
    _reasons_from_planning(planning_result)       <- the planner's OWN output
    _reasons_from_execution(execution_result)     <- executor feedback

If INFORMATION_RECOVERY is sustained only because the planner emits
search_mode_active / "activate_search_mode" and the checker reads that back as
SEARCH_MODE_REQUIRED, the mode is self-confirming: a latch clearable only by
the action it suppresses.

This probe wraps each helper separately and records, per _update_failsafe_mode
call, the reason set each source contributed, plus the counterfactual mode that
classify_mode would return if the planning contribution were removed.

Purely observational: every wrapper calls the original and returns its result
unchanged. classify_mode counterfactuals are computed on a SEPARATE checker
instance and never fed back into the simulation.
"""
from __future__ import annotations
import argparse, contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation, _resolve_role_count_params

from src_extension.execution.safety_checker import SafetyChecker

CUR = {"step": 0, "phase": "init"}
PENDING = {"analysis": (), "planning": (), "execution": ()}

REC = {
    "by_source": {"analysis": {}, "planning": {}, "execution": {}},
    "calls": 0,
    # per extract call: (step, phase, analysis, planning, execution, union, mode,
    #                    mode_without_planning, mode_analysis_only)
    "rows": [],
    "mode_hist": {},
    "mode_wo_planning_hist": {},
    "mode_analysis_only_hist": {},
    "planning_only_reasons": {},   # reasons contributed ONLY by planning -> count
    "steps_planning_load_bearing": 0,   # mode != mode_without_planning
    "steps_analysis_alone_normal": 0,   # analysis-only would be normal
    "search_src": {"analysis": 0, "planning": 0, "execution": 0},
    "planning_decision_fields": {},     # (mission_mode|action|search) -> count
}

_probe_checker = SafetyChecker()

_o_an = SafetyChecker._reasons_from_analysis
_o_pl = SafetyChecker._reasons_from_planning
_o_ex = SafetyChecker._reasons_from_execution
_o_ext = SafetyChecker.extract_fail_safe_reasons
_o_cls = SafetyChecker.classify_mode


def _mk(name, orig):
    def _w(self, arg):
        out = orig(self, arg)
        PENDING[name] = tuple(out)
        d = REC["by_source"][name]
        key = ",".join(sorted(set(out))) if out else "<none>"
        d[key] = d.get(key, 0) + 1
        if name == "planning" and arg is not None:
            dec = self._read_value(arg, "fail_safe_decision", None)
            if dec is None:
                dec = arg
            k = "mm=%s|act=%s|search=%s" % (
                str(getattr(dec, "mission_mode", "?") or ""),
                str(getattr(dec, "fail_safe_action", "?") or ""),
                bool(getattr(dec, "search_mode_active", False)),
            )
            REC["planning_decision_fields"][k] = REC["planning_decision_fields"].get(k, 0) + 1
        return out
    return _w


SafetyChecker._reasons_from_analysis = _mk("analysis", _o_an)
SafetyChecker._reasons_from_planning = _mk("planning", _o_pl)
SafetyChecker._reasons_from_execution = _mk("execution", _o_ex)


def _ext(self, analysis_snapshot=None, planning_result=None, execution_result=None, runtime_models=None):
    PENDING["analysis"] = ()
    PENDING["planning"] = ()
    PENDING["execution"] = ()
    out = _o_ext(self, analysis_snapshot=analysis_snapshot,
                 planning_result=planning_result,
                 execution_result=execution_result,
                 runtime_models=runtime_models)
    REC["calls"] += 1
    an, pl, ex = PENDING["analysis"], PENDING["planning"], PENDING["execution"]
    an_s, pl_s, ex_s = set(an), set(pl), set(ex)

    mode = _o_cls(_probe_checker, tuple(out), "normal")
    wo_pl = _o_cls(_probe_checker, tuple(sorted(an_s | ex_s)), "normal")
    an_only = _o_cls(_probe_checker, tuple(sorted(an_s)), "normal")

    REC["mode_hist"][mode] = REC["mode_hist"].get(mode, 0) + 1
    REC["mode_wo_planning_hist"][wo_pl] = REC["mode_wo_planning_hist"].get(wo_pl, 0) + 1
    REC["mode_analysis_only_hist"][an_only] = REC["mode_analysis_only_hist"].get(an_only, 0) + 1
    if mode != wo_pl:
        REC["steps_planning_load_bearing"] += 1
    if an_only == "normal":
        REC["steps_analysis_alone_normal"] += 1

    only_pl = pl_s - an_s - ex_s
    if only_pl:
        k = ",".join(sorted(only_pl))
        REC["planning_only_reasons"][k] = REC["planning_only_reasons"].get(k, 0) + 1

    for src, s in (("analysis", an_s), ("planning", pl_s), ("execution", ex_s)):
        if "search_mode_required" in s:
            REC["search_src"][src] += 1

    if len(REC["rows"]) < 3000:
        REC["rows"].append(
            (CUR["step"], CUR["phase"], sorted(an_s), sorted(pl_s), sorted(ex_s),
             list(out), mode, wo_pl, an_only)
        )
    return out


SafetyChecker.extract_fail_safe_reasons = _ext

for _stage in ("_run_analysis", "_run_planning", "_run_execution", "_update_failsafe_mode"):
    def _mkp(stage_name):
        _o = getattr(WildFireModel, stage_name)

        def _w(self, *a, **k):
            CUR["phase"] = stage_name
            return _o(self, *a, **k)
        return _w
    setattr(WildFireModel, _stage, _mkp(_stage))


def build(seed, scenario, wind, ft, vs):
    preset = BUILTIN_SCENARIOS[scenario]
    fire_trackers, victim_searchers = _resolve_role_count_params(preset["NUM_AGENTS"], ft, vs)
    params = {
        "NUM_AGENTS": preset["NUM_AGENTS"], "NUM_VICTIMS": preset["NUM_VICTIMS"],
        "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": wind,
        "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": fire_trackers, "NUM_VICTIM_SEARCHERS": victim_searchers,
    }
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
    return m, params


def run(seed, scenario, wind, ft, vs, steps):
    model, params = build(seed, scenario, wind, ft, vs)
    terminal_step = None
    for step_i in range(1, steps + 1):
        CUR["step"] = step_i
        with contextlib.redirect_stdout(_io.StringIO()):
            model.step()
        if terminal_step is None:
            panel = model.get_dashboard_state()
            if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                terminal_step = step_i
    ev = _build_evaluation(model, terminal_step, steps, params)
    return {
        "seed": seed, "wind": wind, "roles": ("half" if ft is not None else "default"),
        "steps": steps,
        "eval": {k: ev.get(k) for k in
                 ("rescued", "dead", "unreachable", "never_detected",
                  "firefighter_deaths", "burnt_cells", "terminal_step")},
        "rec": REC,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--scenario", default="D")
    p.add_argument("--wind", default="east")
    p.add_argument("--fire-trackers", type=int, default=None, dest="ft")
    p.add_argument("--victim-searchers", type=int, default=None, dest="vs")
    p.add_argument("--steps", type=int, default=240)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    res = run(a.seed, a.scenario, a.wind, a.ft, a.vs, a.steps)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, default=str)
    r = res["rec"]
    print(
        "seed=%-5d %s/%-7s calls=%d | mode=%s | mode_wo_planning=%s | mode_analysis_only=%s | "
        "planning_load_bearing=%d/%d | search_src=%s"
        % (a.seed, a.wind, res["roles"], r["calls"], r["mode_hist"],
           r["mode_wo_planning_hist"], r["mode_analysis_only_hist"],
           r["steps_planning_load_bearing"], r["calls"], r["search_src"]),
        flush=True,
    )
