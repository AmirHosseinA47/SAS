"""Defect #7: confirm the fail-safe override ACTUATES, and price the step-1 clear.

Two questions left as static inferences by the other probes:
  Q1 does an active override actually reach UAV movement code, or does the
     chain terminate in a record? -> count real calls to _execute_search_mode /
     _execute_role_preserving_search and the search-mode exemption path.
  Q2 the dispatcher clear fires once per run at step 1 on a degenerate
     return_to_base decision. If it did NOT fire, how many UAV path decisions
     would _adjust_local_path_for_fail_safe have DROPPED that step?
     Computed counterfactually, without changing what the run does.

Observer-only: every wrapper calls the original and returns it unchanged.
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
from serve_dashboard import BUILTIN_SCENARIOS, _resolve_role_count_params

from src_extension.execution import decision_dispatcher as dd_mod
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.execution.uav_executor import UAVExecutor

CUR = {"step": 0}
REC = {
    "exec_search_mode": 0,
    "exec_role_preserving_search": 0,
    "uav_execute_calls": 0,
    "uav_execute_with_fs": 0,
    "search_exempt": 0,
    "path_dropped_actual": 0,
    # counterfactual for the cleared step
    "cf_steps": [],
}

for _n in ("_execute_search_mode", "_execute_role_preserving_search"):
    if hasattr(UAVExecutor, _n):
        def _mk(nm):
            _o = getattr(UAVExecutor, nm)

            def _w(self, *a, **k):
                REC["exec_" + nm.lstrip("_")] = REC.get("exec_" + nm.lstrip("_"), 0) + 1
                return _o(self, *a, **k)
            return _w
        setattr(UAVExecutor, _n, _mk(_n))

_o_uav_exec = UAVExecutor.execute


def _uav_exec(self, decision, timestamp=0.0, fail_safe_decision=None):
    REC["uav_execute_calls"] += 1
    if fail_safe_decision is not None:
        REC["uav_execute_with_fs"] += 1
    return _o_uav_exec(self, decision, timestamp, fail_safe_decision)


UAVExecutor.execute = _uav_exec

_o_exempt = dd_mod._is_victim_search_mode_exempt


def _exempt(uav_id, model, fs_dec, active):
    out = _o_exempt(uav_id, model, fs_dec, active)
    if out:
        REC["search_exempt"] += 1
    return out


dd_mod._is_victim_search_mode_exempt = _exempt

_o_adj = dd_mod._adjust_local_path_for_fail_safe


def _adj(path, fs_dec, active):
    out = _o_adj(path, fs_dec, active)
    if not out[1] or out[0] is None:
        REC["path_dropped_actual"] += 1
    return out


dd_mod._adjust_local_path_for_fail_safe = _adj

_o_dispatch = DecisionDispatcher.dispatch


def _dispatch(self, planning_result, timestamp=0.0):
    try:
        fs_dec, _m, paths, _r = self._extract_decisions(planning_result)
    except Exception:
        fs_dec, paths = None, []
    if fs_dec is not None:
        active, reason = dd_mod._resolve_fail_safe_override(fs_dec)
        fs_state = getattr(self._model, "latest_failsafe_state", None) if self._model else None
        mo = getattr(fs_state, "mode", None) if fs_state is not None else None
        mode_v = (mo.value if hasattr(mo, "value") else str(mo or "")) if mo is not None else ""
        if active and str(mode_v).lower() == "normal":
            # The clear WILL fire this step. Price it: how many paths would the
            # un-cleared override have dropped? Uses the pristine original fn.
            would_drop = 0
            for pd in paths:
                p2, ok = _o_adj(pd, fs_dec, True)
                if not ok or p2 is None:
                    would_drop += 1
            REC["cf_steps"].append({
                "step": CUR["step"], "reason": reason,
                "action": str(getattr(fs_dec, "fail_safe_action", "") or ""),
                "n_path_decisions": len(paths),
                "would_drop_if_not_cleared": would_drop,
            })
    return _o_dispatch(self, planning_result, timestamp)


DecisionDispatcher.dispatch = _dispatch


def build(seed, scenario, wind, ft, vs):
    preset = BUILTIN_SCENARIOS[scenario]
    f, v = _resolve_role_count_params(preset["NUM_AGENTS"], ft, vs)
    params = {"NUM_AGENTS": preset["NUM_AGENTS"], "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": wind,
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": f, "NUM_VICTIM_SEARCHERS": v}
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
    return m


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--wind", default="east")
    p.add_argument("--fire-trackers", type=int, default=2, dest="ft")
    p.add_argument("--victim-searchers", type=int, default=2, dest="vs")
    p.add_argument("--steps", type=int, default=60)
    a = p.parse_args()
    model = build(a.seed, "D", a.wind, a.ft, a.vs)
    for i in range(1, a.steps + 1):
        CUR["step"] = i
        with contextlib.redirect_stdout(_io.StringIO()):
            model.step()
    print(json.dumps(REC, indent=2))
