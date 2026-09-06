"""Battery diagnosis probe: direct read/write hooks + seed-matched counterfactual arms.

Mirrors evaluate_scenarios._run_seed byte for byte (seeding order,
apply_scenario_config, model.debug_log = False, stdout redirected, per-step
get_dashboard_state() polling until the terminal step) and layers READ-ONLY
observers on top. Nothing here draws from any RNG.

DIRECT hooks (not snapshot inference):
  * agents.UAV.battery_level / battery_status              -> class property; every
    get and set is counted per caller (file:function:line) with first/last step
  * UAVResourceRuntimeState.battery_level / battery_status -> same, knowledge side
  * UAVExtensionState.battery_level                        -> same, managed mirror
  * UAV._update_battery_after_step                         -> moved flag, before/after
  * UAVResourceModel.update_battery                        -> call count, PRUT after
  * LocalUAVAnalyzer._analyze_local_resource               -> inputs + trigger types
  * GlobalAnalyzer._analyze_resource_status / _analyze_trends
  * GlobalMonitor.classify_events                          -> resource_events flags
  * ConstraintFilter._battery_reasons / _rejection_reasons -> what value it sees
  * UtilityEvaluation._check_utility_feasibility           -> battery violations
  * FailSafePlanner.plan                                   -> chosen action per step
  * SafetyChecker.extract_fail_safe_reasons, ModeManager.update
  * MissionGoalModel.utility_weight_mode                   -> weight profile chosen

Arms (--arm):
  stock    unmodified
  nodrain  both drain constants zeroed after UAV.__init__ (battery pinned at 100)
  low25    battery_level forced to 25.0 after UAV.__init__ (below LOW=30, above CRIT=15)
  crit12   battery_level forced to 12.0 after UAV.__init__ (below CRIT=15)
The forced arms write the raw storage slot, so they never appear in the write log.

usage:
  _bat_probe.py --repo <checkout> --wind east --roles half --seed 101 --steps 240
                --arm stock --out outputs/_bat_stock_east_half_101.json
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io as _io
import json
import os
import random
import sys
import time

STATE = {"model": None}


def _cur_step() -> int:
    m = STATE["model"]
    if m is None:
        return 0
    return int(getattr(m, "evaluation_timesteps_counter", 0) or 0)


def _caller(depth: int) -> str:
    try:
        f = sys._getframe(depth)
    except ValueError:
        return "<unknown>"
    return "%s:%s:%d" % (os.path.basename(f.f_code.co_filename), f.f_code.co_name, f.f_lineno)


def _install_attr_hook(cls, name: str, log: dict) -> str:
    """Replace attribute `name` on `cls` with a logging property; returns the raw slot key."""
    key = "_hook_" + name
    reads = log.setdefault("reads", {})
    writes = log.setdefault("writes", {})

    def _get(self):
        c = _caller(2)
        st = _cur_step()
        rec = reads.get(c)
        if rec is None:
            reads[c] = [1, st, st]
        else:
            rec[0] += 1
            rec[2] = st
        try:
            return self.__dict__[key]
        except KeyError:
            raise AttributeError(name)

    def _set(self, value):
        c = _caller(2)
        st = _cur_step()
        rec = writes.get(c)
        if rec is None:
            writes[c] = [1, st, st, _num(value), _num(value)]
        else:
            rec[0] += 1
            rec[2] = st
            v = _num(value)
            if v is not None:
                rec[3] = v if rec[3] is None else min(rec[3], v)
                rec[4] = v if rec[4] is None else max(rec[4], v)
        self.__dict__[key] = value

    setattr(cls, name, property(_get, _set))
    return key


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _trig_types(triggers) -> list:
    out = []
    for t in triggers or ():
        tt = getattr(t, "trigger_type", None)
        if tt is None and isinstance(t, dict):
            tt = t.get("trigger_type")
        out.append(str(tt))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--wind", default="east", choices=["north", "south", "east", "west"])
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--arm", default="stock", choices=["stock", "nodrain", "low25", "crit12"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")

    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402
    from wildfire_model import WildFireModel  # noqa: E402
    from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation, _resolve_role_count_params  # noqa: E402
    from src_extension.knowledge.uav_resource_model import UAVResourceModel, UAVResourceRuntimeState  # noqa: E402
    from src_extension.managed.uav_extension_state import UAVExtensionState  # noqa: E402
    from src_extension.analysis.local_uav_analyzer import LocalUAVAnalyzer  # noqa: E402
    from src_extension.analysis.global_analyzer import GlobalAnalyzer  # noqa: E402
    from src_extension.monitoring.global_monitor import GlobalMonitor  # noqa: E402
    from src_extension.adaptation.constraint_filter import ConstraintFilter  # noqa: E402
    from src_extension.planning.utility_evaluation import UtilityEvaluation  # noqa: E402
    from src_extension.planning.fail_safe_planner import FailSafePlanner  # noqa: E402
    from src_extension.execution.safety_checker import SafetyChecker  # noqa: E402
    from src_extension.execution.mode_manager import ModeManager  # noqa: E402
    from src_extension.knowledge.mission_goal_model import MissionGoalModel  # noqa: E402

    for mod in (am, cfv, wf):
        path = os.path.abspath(getattr(mod, "__file__", ""))
        if not path.lower().startswith(repo.lower()):
            print("IMPORT MISMATCH: %s from %s" % (mod.__name__, path), file=sys.stderr)
            return 3

    preset = BUILTIN_SCENARIOS.get(args.scenario, {})
    num_agents = int(preset.get("NUM_AGENTS", 3))
    if args.roles == "half":
        ft, vs = _resolve_role_count_params(num_agents, 2, 2)
    else:
        ft, vs = _resolve_role_count_params(num_agents, None, None)
    params = {
        "NUM_AGENTS": num_agents,
        "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
        "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)),
        "WIND_DIRECTION": str(args.wind),
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": ft,
        "NUM_VICTIM_SEARCHERS": vs,
    }

    REC: dict = {
        "agent_attr": {"battery_level": {}, "battery_status": {}},
        "knowledge_attr": {"battery_level": {}, "battery_status": {}},
        "managed_attr": {"battery_level": {}},
        "drain_calls": [],            # [step, uav, moved, before, after, status_after]
        "update_battery_calls": 0,
        "prut_samples": [],           # [step, uav, prut]
        "local_resource": [],         # [step, uav, latest_has_level, latest_level, latest_status, kn_level, kn_status, [trigger types]]
        "global_resource": [],        # [step, [trigger types]]
        "global_trends": [],          # [step, [trigger types], mean_battery_mentioned, context]
        "monitor_events": [],         # [step, low, critical]
        "constraint_battery": {"calls": 0, "value_types": {}, "nonempty": 0},
        "constraint_reasons_battery": 0,
        "utility_feasibility": {"calls": 0, "battery_violations": 0, "params_had_battery_level": 0, "params_had_projected": 0},
        "failsafe_plan": [],          # [step, option_id, action, mission_mode, search_mode_active, fs_mode, reasons, prefer_critical]
        "safety_reasons": [],         # [step, [reasons]]
        "mode_updates": [],           # [step, mode, [reasons]]
        "weight_modes": {},           # mode -> count
        "steps": [],
        "trigger_type_counts": {},
    }

    # ---- attribute hooks (direct, caller-attributed) ------------------------------
    K_A_LEVEL = _install_attr_hook(am.UAV, "battery_level", REC["agent_attr"]["battery_level"])
    K_A_STAT = _install_attr_hook(am.UAV, "battery_status", REC["agent_attr"]["battery_status"])
    K_K_LEVEL = _install_attr_hook(UAVResourceRuntimeState, "battery_level", REC["knowledge_attr"]["battery_level"])
    K_K_STAT = _install_attr_hook(UAVResourceRuntimeState, "battery_status", REC["knowledge_attr"]["battery_status"])
    K_M_LEVEL = _install_attr_hook(UAVExtensionState, "battery_level", REC["managed_attr"]["battery_level"])

    # ---- arm application: after the stock __init__, touch only raw slots / drains --
    arm = args.arm
    _orig_init = am.UAV.__init__

    def _init(self, *a, **k):
        _orig_init(self, *a, **k)
        if arm == "nodrain":
            self.battery_drain_per_step = 0.0
            self.battery_drain_per_move = 0.0
        elif arm == "low25":
            self.__dict__[K_A_LEVEL] = 25.0
        elif arm == "crit12":
            self.__dict__[K_A_LEVEL] = 12.0

    am.UAV.__init__ = _init

    # ---- method observers --------------------------------------------------------
    _orig_drain = am.UAV._update_battery_after_step

    def _obs_drain(self, moved):
        before = self.__dict__.get(K_A_LEVEL)
        r = _orig_drain(self, moved)
        REC["drain_calls"].append([
            _cur_step(), str(self.unique_id), bool(moved), before,
            self.__dict__.get(K_A_LEVEL), self.__dict__.get(K_A_STAT),
        ])
        return r

    am.UAV._update_battery_after_step = _obs_drain

    _orig_upd = UAVResourceModel.update_battery

    def _obs_upd(self, uav_id, *a, **k):
        r = _orig_upd(self, uav_id, *a, **k)
        REC["update_battery_calls"] += 1
        st = self.by_uav_id.get(str(uav_id))
        if st is not None:
            REC["prut_samples"].append([_cur_step(), str(uav_id), st.__dict__.get("predicted_remaining_useful_time")])
        return r

    UAVResourceModel.update_battery = _obs_upd

    _orig_lres = LocalUAVAnalyzer._analyze_local_resource

    def _obs_lres(self, *a, **k):
        r = _orig_lres(self, *a, **k)
        try:
            uav_id = a[0] if a else k.get("uav_id")
            state = a[3] if len(a) > 3 else k.get("uav_resource_state")
            latest = a[4] if len(a) > 4 else k.get("latest_local_observation")
            latest = latest if isinstance(latest, dict) else {}
            triggers = r[0] if isinstance(r, tuple) else r
            REC["local_resource"].append([
                _cur_step(), str(uav_id), "battery_level" in latest,
                _num(latest.get("battery_level")), latest.get("battery_status"),
                _num(state.__dict__.get(K_K_LEVEL)) if state is not None else None,
                state.__dict__.get(K_K_STAT) if state is not None else None,
                _trig_types(triggers),
            ])
        except Exception as exc:
            REC["local_resource"].append([_cur_step(), "error", repr(exc)])
        return r

    LocalUAVAnalyzer._analyze_local_resource = _obs_lres

    _orig_gres = GlobalAnalyzer._analyze_resource_status

    def _obs_gres(self, *a, **k):
        r = _orig_gres(self, *a, **k)
        REC["global_resource"].append([_cur_step(), _trig_types(r)])
        return r

    GlobalAnalyzer._analyze_resource_status = _obs_gres

    _orig_gtr = GlobalAnalyzer._analyze_trends

    def _obs_gtr(self, *a, **k):
        r = _orig_gtr(self, *a, **k)
        ctx = "; ".join(str(getattr(t, "explanation_context", "")) for t in (r or ()))
        REC["global_trends"].append([_cur_step(), _trig_types(r), "mean_battery" in ctx, ctx[:400]])
        return r

    GlobalAnalyzer._analyze_trends = _obs_gtr

    _orig_cls = GlobalMonitor.classify_events

    def _obs_cls(self, *a, **k):
        r = _orig_cls(self, *a, **k)
        try:
            ev = r.get("resource_events", {}) if isinstance(r, dict) else {}
            REC["monitor_events"].append([_cur_step(), bool(ev.get("low_battery")), bool(ev.get("critical_battery"))])
        except Exception:
            pass
        return r

    GlobalMonitor.classify_events = _obs_cls

    _orig_cb = ConstraintFilter._battery_reasons

    def _obs_cb(self, option, runtime_models, mission_constraints):
        r = _orig_cb(self, option, runtime_models, mission_constraints)
        cb = REC["constraint_battery"]
        cb["calls"] += 1
        try:
            val = self._read(runtime_models, "battery", self._read(runtime_models, "battery_state"))
            tn = type(val).__name__
            cb["value_types"][tn] = cb["value_types"].get(tn, 0) + 1
        except Exception:
            pass
        if r:
            cb["nonempty"] += 1
        return r

    ConstraintFilter._battery_reasons = _obs_cb

    _orig_rr = ConstraintFilter._rejection_reasons

    def _obs_rr(self, *a, **k):
        r = _orig_rr(self, *a, **k)
        for reason in r or ():
            if "battery" in str(reason).lower():
                REC["constraint_reasons_battery"] += 1
        return r

    ConstraintFilter._rejection_reasons = _obs_rr

    _orig_feas = UtilityEvaluation._check_utility_feasibility

    def _obs_feas(self, option, context=None):
        r = _orig_feas(self, option, context)
        uf = REC["utility_feasibility"]
        uf["calls"] += 1
        try:
            feasible, violations = r
            if any("battery" in str(v) for v in violations):
                uf["battery_violations"] += 1
            params = UtilityEvaluation._merge_params_for_feasibility(option, context)
            if "battery_level" in params:
                uf["params_had_battery_level"] += 1
            if "projected_battery_after_option" in params:
                uf["params_had_projected"] += 1
        except Exception:
            pass
        return r

    UtilityEvaluation._check_utility_feasibility = _obs_feas

    _orig_plan = FailSafePlanner.plan

    def _obs_plan(self, *a, **k):
        r = _orig_plan(self, *a, **k)
        try:
            ctx = getattr(r, "uncertainty_context", None) or {}
            summ = getattr(r, "comparison_summary", None) or {}
            text = str(summ.get("summary", "")) if isinstance(summ, dict) else str(summ)
            prefer_critical = "Prefer critical fail-safe options: True" in text
            REC["failsafe_plan"].append([
                _cur_step(),
                str(getattr(r, "selected_option_id", "") or ""),
                str(getattr(r, "fail_safe_action", "") or ""),
                str(getattr(r, "mission_mode", "") or ""),
                bool(getattr(r, "search_mode_active", False)),
                str(ctx.get("fail_safe_mode", "") or "") if isinstance(ctx, dict) else "",
                [str(x) for x in (ctx.get("fail_safe_reasons", []) if isinstance(ctx, dict) else [])],
                prefer_critical,
            ])
        except Exception as exc:
            REC["failsafe_plan"].append([_cur_step(), "error", repr(exc)])
        return r

    FailSafePlanner.plan = _obs_plan

    _orig_reasons = SafetyChecker.extract_fail_safe_reasons

    def _obs_reasons(self, *a, **k):
        r = _orig_reasons(self, *a, **k)
        REC["safety_reasons"].append([_cur_step(), [str(x) for x in (r or ())]])
        return r

    SafetyChecker.extract_fail_safe_reasons = _obs_reasons

    _orig_mode = ModeManager.update

    def _obs_mode(self, *a, **k):
        r = _orig_mode(self, *a, **k)
        try:
            mode = getattr(r, "mode", None)
            REC["mode_updates"].append([
                _cur_step(),
                str(getattr(mode, "value", mode) or ""),
                [str(getattr(x, "value", x)) for x in (getattr(r, "active_reasons", ()) or ())],
            ])
        except Exception:
            pass
        return r

    ModeManager.update = _obs_mode

    _orig_wm = MissionGoalModel.utility_weight_mode

    def _obs_wm(self):
        r = _orig_wm(self)
        REC["weight_modes"][str(r)] = REC["weight_modes"].get(str(r), 0) + 1
        return r

    MissionGoalModel.utility_weight_mode = _obs_wm

    # ---- run: byte-for-byte the evaluate_scenarios._run_seed sequence --------------
    rng = random.Random(args.seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    fire_digests: list = []
    terminal_step = None
    step = 0
    t0 = time.perf_counter()
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        STATE["model"] = model
        model.debug_log = False
        for _ in range(args.steps):
            model.step()
            step += 1
            if terminal_step is None:
                panel = model.get_dashboard_state()
                mission = panel.get("mission_status", {}) or {}
                if mission.get("all_victims_terminal"):
                    terminal_step = step
            # --- observers only below this line (raw slots, no hooked reads)
            parts = []
            for a in model.schedule.agents:
                if type(a).__name__ == "Fire":
                    parts.append("%s:%d%d%s" % (a.unique_id, int(bool(a.burning)), int(bool(a.burnt)), a.fuel))
            fire_digests.append(hashlib.sha256("|".join(parts).encode()).hexdigest())

            uav_rows = []
            rm = getattr(model, "uav_resource_model", None)
            managed = getattr(model, "managed_uav_states", {}) or {}
            for a in model.schedule.agents:
                if type(a) is not am.UAV:
                    continue
                uid = str(a.unique_id)
                pos = getattr(a, "pos", None)
                st = rm.by_uav_id.get(uid) if rm is not None else None
                ms = managed.get(uid)
                uav_rows.append([
                    uid,
                    None if pos is None else [int(pos[0]), int(pos[1])],
                    int(getattr(a, "selected_dir", 0) or 0),
                    str(getattr(a, "execution_action", "") or ""),
                    str(a.current_role or ""),
                    _num(a.__dict__.get(K_A_LEVEL)),
                    str(a.__dict__.get(K_A_STAT) or ""),
                    _num(st.__dict__.get(K_K_LEVEL)) if st is not None else None,
                    (st.__dict__.get(K_K_STAT) if st is not None else None),
                    _num(st.__dict__.get("predicted_remaining_useful_time")) if st is not None else None,
                    _num(ms.__dict__.get(K_M_LEVEL)) if ms is not None else None,
                ])

            trig = []
            snap = getattr(model, "latest_analysis_snapshot", None)
            if snap is not None:
                trig = _trig_types(getattr(snap, "all_triggers", ()))
                for tt in trig:
                    REC["trigger_type_counts"][tt] = REC["trigger_type_counts"].get(tt, 0) + 1

            ex = getattr(model, "latest_execution_result", None)
            ex_row = None
            if isinstance(ex, dict):
                local = ex.get("local") if isinstance(ex.get("local"), dict) else {}
                ur = local.get("uav_results") if isinstance(local.get("uav_results"), dict) else {}
                fs = ex.get("fail_safe") if isinstance(ex.get("fail_safe"), dict) else {}
                ex_row = {
                    "override": bool(ex.get("fail_safe_override_active")),
                    "override_reason": str(ex.get("override_reason", "") or ""),
                    "fs_action": str(fs.get("fail_safe_action", "") or ""),
                    "fs_applied": fs.get("applied"),
                    "uav": {
                        str(k): [v.get("applied"), str(v.get("reason", "") or ""), str(v.get("action", "") or "")]
                        for k, v in ur.items() if isinstance(v, dict)
                    },
                }

            fs_state = getattr(model, "latest_failsafe_state", None)
            fs_mode = getattr(fs_state, "mode", None)
            mgm = getattr(model, "mission_goal_model", None)
            dyn = getattr(mgm, "dynamic_metrics", {}) if mgm is not None else {}

            alerts = 0
            panel_state = getattr(model, "latest_dashboard_state", None)
            if isinstance(panel_state, dict):
                for al in panel_state.get("alert_list", []) or []:
                    if isinstance(al, dict) and al.get("alert_type") == "low_battery":
                        alerts += 1

            REC["steps"].append({
                "step": step,
                "uavs": uav_rows,
                "triggers": sorted(trig),
                "exec": ex_row,
                "fs_mode": str(getattr(fs_mode, "value", fs_mode) or ""),
                "mgm_fs_mode": str(dyn.get("active_fail_safe_mode", "") or ""),
                "mgm_phase": str(getattr(mgm, "mission_phase", "") or ""),
                "low_battery_alerts": alerts,
            })
        evaluation = _build_evaluation(model, terminal_step, step, params)
    wall = time.perf_counter() - t0

    out = {
        "arm": arm,
        "repo": repo,
        "scenario": args.scenario,
        "wind": args.wind,
        "roles": args.roles,
        "seed": args.seed,
        "steps": args.steps,
        "params": params,
        "eval": evaluation,
        "terminal_step": terminal_step,
        "wall_s": round(wall, 1),
        "fire_final_digest": fire_digests[-1] if fire_digests else None,
        "fire_digests": fire_digests,
        "cfv_thresholds": {
            "LOW_BATTERY_THRESHOLD": getattr(cfv, "LOW_BATTERY_THRESHOLD", None),
            "BATTERY_CRITICAL_THRESHOLD": getattr(cfv, "BATTERY_CRITICAL_THRESHOLD", None),
        },
        "rec": REC,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print("wrote %s arm=%s seed=%d wall=%.1fs terminal=%s" % (args.out, arm, args.seed, wall, terminal_step))
    return 0


if __name__ == "__main__":
    sys.exit(main())
