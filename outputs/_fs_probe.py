"""Defect #7 Part-2 probe: instrument the fail-safe override lifecycle.

Every patch is an OBSERVER: it calls the original, records, and returns the
original result unchanged. Control flow is byte-identical to an unpatched run.

Transitions are hooked DIRECTLY (not sampled per step), because
_update_failsafe_mode runs twice per step, so a set-and-clear inside one step
is invisible to end-of-step sampling. (Lesson from the #5 round.)

What is measured
  1. ModeManager.update()            -> every mode transition, with reasons
  2. SafetyChecker.should_override_utility() -> call count + True/False
  3. SafetyChecker.extract_fail_safe_reasons() -> reason multisets actually seen
  4. SafetyChecker.classify_mode()   -> (reasons -> mode) pairs actually seen
  5. SharedOperationalPicture.__setattr__ -> EVERY write to mission_mode /
     active_adaptation_state, with the writing file:line. Catches write sites
     this probe does not know about, and proves whether any clear site exists.
  6. DecisionDispatcher.dispatch()   -> per call, recomputes the two halves of
     the dispatcher clear (decision_dispatcher.py ~91-103) without altering it:
       resolve_active = _resolve_fail_safe_override(fs_decision)
       mode_at_read   = model.latest_failsafe_state.mode
     The clear fires iff resolve_active and mode_at_read == "normal".
  7. ModeManager.should_return_to_normal / is_information_recovery_active ->
     call counters, to prove empirically whether they are dead in production.
  8. stable_recovery_counter trajectory.
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

from src_extension.execution import decision_dispatcher as dd_mod
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.execution.mode_manager import ModeManager
from src_extension.execution.safety_checker import SafetyChecker
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture

CUR = {"step": 0, "phase": "init"}

REC = {
    # --- ModeManager ---
    "mm_update_calls": 0,
    "mm_transitions": [],          # (step, phase, prev_mode, new_mode, reasons)
    "mm_mode_calls_by_mode": {},   # mode -> number of update() calls ending in it
    "mm_nonnormal_episodes": [],   # (start_step, end_step_or_None, mode, len_in_updates)
    "mm_started_at_anomaly": [],   # started_at kept/reset oddities
    "mm_prev_mode_seen": [],
    "src_counter_traj": [],        # (step, phase, stable_recovery_counter, mode)
    "mm_should_return_calls": 0,
    "mm_is_inforecovery_calls": 0,
    # --- SafetyChecker ---
    "sc_override_calls": 0,
    "sc_override_true": 0,
    "sc_override_by_mode": {},     # mode -> [n_true, n_calls]
    "sc_reason_sets": {},          # ",".join(reasons) -> count
    "sc_classify": {},             # "reasons=>mode" -> count
    # --- SOP writes ---
    "sop_writes": [],              # (step, phase, obj_tag, attr, old, new, caller)
    "sop_write_sites": {},         # "caller|attr" -> count
    "sop_clear_events": 0,         # a write that moves a non-normal value back to normal/None
    "sop_ids": {},                 # tag -> id
    # --- Dispatcher override ---
    "disp_calls": 0,
    "disp_resolve_true": 0,
    "disp_clear_fires": 0,         # resolve True AND mode == normal  -> override dropped
    "disp_survives": 0,            # resolve True AND mode != normal  -> override kept
    "disp_clear_detail": [],       # (step, mission_mode, action, search, reason, mode_at_read)
    "disp_survive_detail": [],
    "disp_resolve_reasons": {},    # override_reason -> count
    "disp_decision_modes": {},     # mission_mode -> count (all dispatches with a fs decision)
    "disp_no_decision": 0,
    "disp_skip_global": 0,         # override active AND _should_skip_global_execution
    # --- per-step end state ---
    "step_mode": [],               # (step, mode, sop_mission_mode)
}


def _tag_sop(obj):
    for tag, oid in REC["sop_ids"].items():
        if oid == id(obj):
            return tag
    return "unknown:%d" % id(obj)


def _caller(depth=2):
    try:
        f = sys._getframe(depth)
        return "%s:%d" % (os.path.basename(f.f_code.co_filename), f.f_lineno)
    except Exception:
        return "?"


# ---------------------------------------------------------------- SOP writes
_WATCH = ("mission_mode", "active_adaptation_state")
_NORMALISH = (None, "", "normal", "monitoring")

_orig_sop_setattr = SharedOperationalPicture.__setattr__


def _sop_setattr(self, name, value):
    if name in _WATCH:
        old = getattr(self, name, "<unset>")
        if old != value:
            site = _caller(2)
            REC["sop_writes"].append(
                (CUR["step"], CUR["phase"], _tag_sop(self), name,
                 str(old), str(value), site)
            )
            k = "%s|%s" % (site, name)
            REC["sop_write_sites"][k] = REC["sop_write_sites"].get(k, 0) + 1
            if old not in _NORMALISH and old != "<unset>" and value in _NORMALISH:
                REC["sop_clear_events"] += 1
    return _orig_sop_setattr(self, name, value)


SharedOperationalPicture.__setattr__ = _sop_setattr


# ------------------------------------------------------------- ModeManager
_orig_mm_update = ModeManager.update


def _mm_update(self, *a, **k):
    prev = self.current_state
    prev_mode = prev.mode.value if prev is not None else "?"
    prev_started = getattr(prev, "started_at", None)
    out = _orig_mm_update(self, *a, **k)
    REC["mm_update_calls"] += 1
    new_mode = out.mode.value
    reasons = tuple(r.value for r in out.active_reasons)
    REC["mm_mode_calls_by_mode"][new_mode] = REC["mm_mode_calls_by_mode"].get(new_mode, 0) + 1
    if new_mode != prev_mode:
        REC["mm_transitions"].append(
            (CUR["step"], CUR["phase"], prev_mode, new_mode, list(reasons))
        )
        if new_mode == "normal":
            for ep in reversed(REC["mm_nonnormal_episodes"]):
                if ep[1] is None:
                    ep[1] = CUR["step"]
                    break
        else:
            REC["mm_nonnormal_episodes"].append(
                [CUR["step"], None, new_mode, list(reasons)]
            )
    # started_at semantics: NORMAL episodes should not carry a live start stamp
    if new_mode == "normal" and out.started_at not in (0.0, None):
        REC["mm_started_at_anomaly"].append(
            (CUR["step"], CUR["phase"], prev_mode, out.started_at, prev_started)
        )
    REC["src_counter_traj"].append(
        (CUR["step"], CUR["phase"], self.stable_recovery_counter, new_mode)
    )
    if out.previous_mode is not None:
        REC["mm_prev_mode_seen"].append((CUR["step"], new_mode, out.previous_mode.value))
    return out


ModeManager.update = _mm_update

_orig_srn = ModeManager.should_return_to_normal


def _srn(self, *a, **k):
    REC["mm_should_return_calls"] += 1
    return _orig_srn(self, *a, **k)


ModeManager.should_return_to_normal = _srn

_orig_ira = ModeManager.is_information_recovery_active


def _ira(self, *a, **k):
    REC["mm_is_inforecovery_calls"] += 1
    return _orig_ira(self, *a, **k)


ModeManager.is_information_recovery_active = _ira


# ----------------------------------------------------------- SafetyChecker
_orig_sou = SafetyChecker.should_override_utility


def _sou(self, reasons, mode):
    out = _orig_sou(self, reasons, mode)
    REC["sc_override_calls"] += 1
    if out:
        REC["sc_override_true"] += 1
    ent = REC["sc_override_by_mode"].setdefault(str(mode), [0, 0])
    ent[1] += 1
    if out:
        ent[0] += 1
    return out


SafetyChecker.should_override_utility = _sou

_orig_efsr = SafetyChecker.extract_fail_safe_reasons


def _efsr(self, *a, **k):
    out = _orig_efsr(self, *a, **k)
    key = ",".join(out) if out else "<none>"
    REC["sc_reason_sets"][key] = REC["sc_reason_sets"].get(key, 0) + 1
    return out


SafetyChecker.extract_fail_safe_reasons = _efsr

_orig_cm = SafetyChecker.classify_mode


def _cm(self, reasons, current_mode="normal"):
    out = _orig_cm(self, reasons, current_mode)
    key = "%s=>%s" % (",".join(sorted(reasons)) if reasons else "<none>", out)
    REC["sc_classify"][key] = REC["sc_classify"].get(key, 0) + 1
    return out


SafetyChecker.classify_mode = _cm


# ------------------------------------------------------------- Dispatcher
_orig_dispatch = DecisionDispatcher.dispatch


def _dispatch(self, planning_result, timestamp=0.0):
    # Recompute the two halves of the in-method clear WITHOUT changing it.
    try:
        fs_dec, _mis, _paths, _resc = self._extract_decisions(planning_result)
    except Exception:
        fs_dec = None
    if fs_dec is None:
        REC["disp_no_decision"] += 1
    else:
        mm = str(getattr(fs_dec, "mission_mode", "") or "")
        REC["disp_decision_modes"][mm or "<empty>"] = (
            REC["disp_decision_modes"].get(mm or "<empty>", 0) + 1
        )
        active, reason = dd_mod._resolve_fail_safe_override(fs_dec)
        REC["disp_calls"] += 1
        if active:
            REC["disp_resolve_true"] += 1
            REC["disp_resolve_reasons"][reason] = (
                REC["disp_resolve_reasons"].get(reason, 0) + 1
            )
            fs_state = getattr(self._model, "latest_failsafe_state", None) if self._model else None
            mode_v = ""
            if fs_state is not None:
                mo = getattr(fs_state, "mode", None)
                mode_v = mo.value if hasattr(mo, "value") else str(mo or "")
            row = (
                CUR["step"],
                str(getattr(fs_dec, "mission_mode", "") or ""),
                str(getattr(fs_dec, "fail_safe_action", "") or ""),
                bool(getattr(fs_dec, "search_mode_active", False)),
                reason,
                mode_v,
            )
            if str(mode_v).lower() == "normal":
                REC["disp_clear_fires"] += 1
                if len(REC["disp_clear_detail"]) < 400:
                    REC["disp_clear_detail"].append(row)
            else:
                REC["disp_survives"] += 1
                if len(REC["disp_survive_detail"]) < 400:
                    REC["disp_survive_detail"].append(row)
                try:
                    if dd_mod._should_skip_global_execution(fs_dec):
                        REC["disp_skip_global"] += 1
                except Exception:
                    pass
    return _orig_dispatch(self, planning_result, timestamp)


DecisionDispatcher.dispatch = _dispatch


# ------------------------------------------------------------- phase marks
for _stage in ("_run_analysis", "_run_planning", "_run_execution", "_update_failsafe_mode"):
    def _mk(stage_name):
        _o = getattr(WildFireModel, stage_name)

        def _w(self, *a, **k):
            CUR["phase"] = stage_name
            return _o(self, *a, **k)
        return _w
    setattr(WildFireModel, _stage, _mk(_stage))


# ------------------------------------------------------------------- runner
def build(seed, scenario, wind, ft, vs):
    preset = BUILTIN_SCENARIOS[scenario]
    fire_trackers, victim_searchers = _resolve_role_count_params(
        preset["NUM_AGENTS"], ft, vs)
    params = {
        "NUM_AGENTS": preset["NUM_AGENTS"],
        "NUM_VICTIMS": preset["NUM_VICTIMS"],
        "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"],
        "WIND_DIRECTION": wind,
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": fire_trackers,
        "NUM_VICTIM_SEARCHERS": victim_searchers,
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

    sop_model = getattr(model, "shared_operational_picture", None)
    km = getattr(model, "knowledge_manager", None)
    sop_km = getattr(km, "shared_operational_picture", None) if km is not None else None
    if sop_model is not None:
        REC["sop_ids"]["model.shared_operational_picture"] = id(sop_model)
    if sop_km is not None:
        REC["sop_ids"]["knowledge_manager.shared_operational_picture"] = id(sop_km)
    REC["sop_same_object"] = (
        sop_model is not None and sop_km is not None and sop_model is sop_km
    )

    terminal_step = None
    for step_i in range(1, steps + 1):
        CUR["step"] = step_i
        with contextlib.redirect_stdout(_io.StringIO()):
            model.step()
        if terminal_step is None:
            panel = model.get_dashboard_state()
            if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                terminal_step = step_i
        fs = getattr(model, "latest_failsafe_state", None)
        mode_v = ""
        if fs is not None:
            mo = getattr(fs, "mode", None)
            mode_v = mo.value if hasattr(mo, "value") else str(mo or "")
        smm = getattr(sop_model, "mission_mode", None) if sop_model is not None else None
        REC["step_mode"].append((step_i, mode_v, str(smm)))

    # close any still-open non-normal episode
    open_eps = [ep for ep in REC["mm_nonnormal_episodes"] if ep[1] is None]
    ev = _build_evaluation(model, terminal_step, steps, params)
    final_sop = {
        "model.mission_mode": str(getattr(sop_model, "mission_mode", None)),
        "model.active_adaptation_state": str(getattr(sop_model, "active_adaptation_state", None)),
        "km.mission_mode": str(getattr(sop_km, "mission_mode", None)) if sop_km is not None else None,
    }
    return {
        "seed": seed, "scenario": scenario, "wind": wind,
        "roles": ("half" if ft is not None else "default"),
        "steps": steps,
        "eval": {k: ev.get(k) for k in
                 ("rescued", "dead", "unreachable", "never_detected",
                  "geographically_isolated", "firefighter_deaths",
                  "burnt_cells", "rescue_rate", "terminal_step")},
        "episodes_open_at_end": open_eps,
        "final_sop": final_sop,
        "sop_same_object": REC["sop_same_object"],
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
        "seed=%-5d %s/%s/%-7s | mm_updates=%d transitions=%d modes=%s | "
        "sc_override T/N=%d/%d | disp resolve_true=%d clear_fires=%d survives=%d | "
        "sop_writes=%d clears=%d same_obj=%s | srn_calls=%d ira_calls=%d | "
        "rescued=%s dead=%s ffd=%s term=%s"
        % (a.seed, a.scenario, a.wind, res["roles"],
           r["mm_update_calls"], len(r["mm_transitions"]),
           r["mm_mode_calls_by_mode"],
           r["sc_override_true"], r["sc_override_calls"],
           r["disp_resolve_true"], r["disp_clear_fires"], r["disp_survives"],
           len(r["sop_writes"]), r["sop_clear_events"], res["sop_same_object"],
           r["mm_should_return_calls"], r["mm_is_inforecovery_calls"],
           res["eval"]["rescued"], res["eval"]["dead"],
           res["eval"]["firefighter_deaths"], res["eval"]["terminal_step"]),
        flush=True,
    )
