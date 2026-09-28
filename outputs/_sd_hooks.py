"""sysdebug round: runtime confirmation hooks (Parts 2, 3, 6) around outputs/_sd_probe.py.

DIAGNOSIS ONLY. Every hook is a PASS-THROUGH wrapper installed in THIS process: it calls
the original with the original arguments, returns the original result unchanged,
draws from no RNG and writes no simulation state (reads only). No source file is
touched. A hooked run must therefore be value-identical to an unhooked run of the same
arguments; the probe's stdout sha256 and eval are recorded for that comparison.

usage: _sd_hooks.py [--trace-exc] -- <_sd_probe.py args ...>

Hooks (ids match outputs/sysdebug_report.txt):
  H_FILTER   ConstraintFilter.filter_options: options in/out by family, rejection reasons,
             and parameter-key census (search_mode_required / search_mode / target_regions
             / target_region / horizon_type / horizon_action / smoke_penalty ...).
  H_GENIN    LocalAdaptationSpaceGenerator.generate: keys of local_input / local_models.
  H_FIREGEN  LocalAdaptationSpaceGenerator._collect_active_fire_cells vs ground truth.
  H_FIREEXE  UAVExecutor._collect_active_fire_cells vs ground truth.
  H_VCAND    _collect_active_live_victim_targets / UAVExecutor._victim_positions_from_runtime:
             non-empty returns.
  H_GATE     UAVExecutor._apply_victim_searcher_hazard_gate: direction replaced, by label.
  H_HORIZON  UtilityEvaluation._compute_horizon_context_fit: distinct returned values.
  H_FEAS     UtilityEvaluation._check_utility_feasibility: infeasible count.
  H_SCORE    UtilityEvaluation.score_options by calling planner: max/min score, ties at top.
  H_FLANK    UAVExecutor._flank_target_from_decision: non-None, flank ctx keys present.
  H_SAFETY   SafetyChecker._reasons_from_execution: non-empty returns; nested failure keys.
  H_RESMAPE  RescuePlanner.plan / RescueExecutor.execute: selected ids, decision.victim_id.
  H_GMP      GlobalMissionPlanner.plan: fail_safe_mission options in space vs selected.
  H_MOVE     UAV.move: (execution_action family, moved) - does a hold move the UAV?
  H_INCID    WildFireModel._handle_rescue_incident: exceptions (counted, then re-raised).
  H_SURV     Firefighter._survival_move: assigned entries with the idle stall latch set.
  H_FINAL    local_adaptation_generator._finalize_coverage_target: x pull west/east and y
             forced north/south, by wind and lane axis.
  H_UNREACH  WildFireModel._mark_victim_unreachable: calls by reason/cause, step.
  H_RADIUS   model attribute UAV_OBSERVATION_RADIUS present at step 1.
  --trace-exc  sys.settrace census of every exception raised in a repo frame and the
             repo frame that caught it (the swallow site). Slow; read-only.
"""
from __future__ import annotations

import collections
import json
import os
import runpy
import sys
import traceback

KEYS_OF_INTEREST = ("search_mode_required", "search_mode", "target_regions", "target_region",
                    "horizon_type", "horizon_action", "smoke_penalty", "next_step_smoke_penalty",
                    "overlap_penalty", "collision_risk", "battery_cost", "drift_risk",
                    "recovery_value", "uncertainty_level", "information_recovery", "victim_id",
                    "firefighter_id")
GENIN_NAMES = ("local_uncertainty", "belief_gain", "negative_observations", "fire_belief",
               "stale_regions", "victim_confidence", "hidden_regions", "sensing_evidence")


def fam(option_id: str) -> str:
    s = str(option_id or "")
    for p in ("local_path_move_toward_fire", "local_path_move_toward_victim", "explore_unknown_region",
              "wind_aware_victim_search", "local_stability", "local_sensing", "local_path",
              "global_role_assignment", "global_stability", "global_", "rescue_", "failsafe", "info-",
              "safety-", "comm"):
        if s.startswith(p):
            return p
    return s.split("_")[0] if "_" in s else s


def main() -> int:
    argv = sys.argv[1:]
    cut = argv.index("--")
    own, probe_args = argv[:cut], argv[cut + 1:]
    trace_exc = "--trace-exc" in own
    repo = r"E:\Projects\SAS"
    out_path = probe_args[probe_args.index("--out") + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.adaptation.local_adaptation_generator as lag  # noqa: E402
    import src_extension.adaptation.constraint_filter as cfm  # noqa: E402
    import src_extension.execution.uav_executor as ux  # noqa: E402
    import src_extension.planning.utility_evaluation as ue  # noqa: E402
    import src_extension.execution.safety_checker as sc  # noqa: E402
    import src_extension.planning.rescue_planner as rp  # noqa: E402
    import src_extension.execution.rescue_executor as rx  # noqa: E402
    import src_extension.planning.global_mission_planner as gmp  # noqa: E402

    C = collections.defaultdict(collections.Counter)
    EV = collections.defaultdict(list)
    cur = {"step": 0, "model": None}

    def ev(name, row, cap=400):
        if len(EV[name]) < cap:
            EV[name].append(row)

    orig_step = wf.WildFireModel.step

    def model_step(self):
        cur["step"] += 1
        cur["model"] = self
        if cur["step"] == 1:
            C["H_RADIUS"]["model_has_UAV_OBSERVATION_RADIUS=%s" % hasattr(self, "UAV_OBSERVATION_RADIUS")] += 1
        return orig_step(self)

    wf.WildFireModel.step = model_step

    def true_burning(model):
        cells = set()
        if model is None:
            return cells
        for a in model.schedule.agents:
            if type(a) is am.Fire and a.pos is not None and a.burning:
                cells.add((int(a.pos[0]), int(a.pos[1])))
        return cells

    # H_FILTER
    of = cfm.ConstraintFilter.filter_options

    def filter_options(self, options, runtime_models, mission_constraints):
        options = list(options)
        out = of(self, options, runtime_models, mission_constraints)
        kept = {id(o) for o in out}
        for o in options:
            f = fam(getattr(o, "option_id", ""))
            C["H_FILTER_in"][f] += 1
            if id(o) in kept:
                C["H_FILTER_out"][f] += 1
            params = getattr(o, "parameters", None) or {}
            if isinstance(params, dict):
                for k in KEYS_OF_INTEREST:
                    if k in params:
                        C["H_FILTER_keys"]["%s|%s" % (k, fam(getattr(o, "option_id", "")))] += 1
        for r in getattr(self, "rejected_options", []) or []:
            for reason in r.get("reasons") or ():
                C["H_FILTER_reject"]["%s|%s" % (fam(r.get("option_id")), str(reason)[:60])] += 1
        return out

    cfm.ConstraintFilter.filter_options = filter_options

    # H_GENIN
    og = lag.LocalAdaptationSpaceGenerator.generate

    def generate(self, local_input, local_models, runtime_models, timestamp):
        if isinstance(local_input, dict):
            for k in local_input.keys():
                C["H_GENIN_input_keys"][str(k)] += 1
            for n in GENIN_NAMES:
                C["H_GENIN_named_present"]["%s=%s" % (n, n in local_input)] += 1
        if isinstance(local_models, dict):
            for k in local_models.keys():
                C["H_GENIN_model_keys"][str(k)] += 1
        space = og(self, local_input, local_models, runtime_models, timestamp)
        return space

    lag.LocalAdaptationSpaceGenerator.generate = generate

    # H_FIREGEN (staticmethod)
    ofg = lag.LocalAdaptationSpaceGenerator._collect_active_fire_cells

    def fire_gen(runtime_models):
        ret = ofg(runtime_models)
        sim = runtime_models.get("simulation_model") if isinstance(runtime_models, dict) else None
        tb = true_burning(sim)
        C["H_FIREGEN"]["calls"] += 1
        C["H_FIREGEN"]["ret_cells"] += len(ret)
        C["H_FIREGEN"]["true_burning"] += len(tb)
        C["H_FIREGEN"]["true_missing_from_ret"] += len(tb - ret)
        C["H_FIREGEN"]["ret_not_burning"] += len(ret - tb)
        if not ret and tb:
            C["H_FIREGEN"]["empty_while_fire_burns"] += 1
        return ret

    lag.LocalAdaptationSpaceGenerator._collect_active_fire_cells = staticmethod(fire_gen)

    # H_FIREEXE
    ofe = ux.UAVExecutor._collect_active_fire_cells

    def fire_exe(self, model=None):
        ret = ofe(self, model)
        tb = true_burning(model or getattr(self, "_model", None))
        C["H_FIREEXE"]["calls"] += 1
        C["H_FIREEXE"]["ret_cells"] += len(ret)
        C["H_FIREEXE"]["true_burning"] += len(tb)
        C["H_FIREEXE"]["true_missing_from_ret"] += len(tb - ret)
        C["H_FIREEXE"]["ret_not_burning"] += len(ret - tb)
        return ret

    ux.UAVExecutor._collect_active_fire_cells = fire_exe

    # H_VCAND
    import inspect as _inspect
    _static = isinstance(_inspect.getattr_static(lag.LocalAdaptationSpaceGenerator,
                                                 "_collect_active_live_victim_targets"), staticmethod)
    ovc = lag.LocalAdaptationSpaceGenerator._collect_active_live_victim_targets

    def vcand(*a, **k):
        ret = ovc(*a, **k)
        C["H_VCAND"]["gen_calls"] += 1
        if ret:
            C["H_VCAND"]["gen_nonempty"] += 1
        return ret

    lag.LocalAdaptationSpaceGenerator._collect_active_live_victim_targets = (
        staticmethod(vcand) if _static else vcand)
    for _name in ("_victim_positions_from_runtime", "_apply_victim_searcher_hazard_gate",
                  "_flank_target_from_decision", "_collect_active_fire_cells"):
        if isinstance(_inspect.getattr_static(ux.UAVExecutor, _name), staticmethod):
            raise SystemExit("SD_HOOKS: %s is a staticmethod - hook needs updating" % _name)
    ovp = ux.UAVExecutor._victim_positions_from_runtime

    def vpos(self):
        ret = ovp(self)
        C["H_VCAND"]["exe_calls"] += 1
        if ret:
            C["H_VCAND"]["exe_nonempty"] += 1
        return ret

    ux.UAVExecutor._victim_positions_from_runtime = vpos

    # H_GATE
    ogate = ux.UAVExecutor._apply_victim_searcher_hazard_gate

    def gate(self, agent, chosen_dir, action):
        d, lab = ogate(self, agent, chosen_dir, action)
        key = str(action)
        C["H_GATE_calls"][key] += 1
        if int(d) != int(chosen_dir):
            C["H_GATE_replaced"][key] += 1
            C["H_GATE_replaced_label"]["%s->%s" % (key, lab)] += 1
        return d, lab

    ux.UAVExecutor._apply_victim_searcher_hazard_gate = gate

    # H_HORIZON / H_FEAS / H_SCORE
    oh = ue.UtilityEvaluation._compute_horizon_context_fit

    def horizon(self, option, context=None):
        val, why = oh(self, option, context)
        params = getattr(option, "parameters", None) or {}
        C["H_HORIZON"]["%s|ht=%s" % (round(float(val), 4), params.get("horizon_type") if isinstance(params, dict) else None)] += 1
        return val, why

    ue.UtilityEvaluation._compute_horizon_context_fit = horizon
    ofeas = ue.UtilityEvaluation._check_utility_feasibility

    def feas(self, option, context=None):
        ok, viol = ofeas(self, option, context)
        C["H_FEAS"]["feasible=%s" % ok] += 1
        return ok, viol

    ue.UtilityEvaluation._check_utility_feasibility = feas
    osc = ue.UtilityEvaluation.score_options

    def score(self, options, runtime_models=None, context=None, mode=None):
        res = osc(self, options, runtime_models, context, mode)
        caller = sys._getframe(1)
        who = "%s.%s" % (os.path.basename(caller.f_code.co_filename), caller.f_code.co_name)
        C["H_SCORE_calls"][who] += 1
        C["H_SCORE_mode"]["%s|%s" % (who, mode)] += 1
        if res:
            top = res[0].score
            ties = sum(1 for s in res if abs(s.score - top) < 1e-12)
            C["H_SCORE_top_zero"]["%s|top==0:%s" % (who, abs(top) < 1e-12)] += 1
            C["H_SCORE_ties"]["%s|tie>1:%s" % (who, ties > 1)] += 1
            if all(abs(s.score) < 1e-12 for s in res):
                C["H_SCORE_allzero"][who] += 1
        else:
            C["H_SCORE_empty"][who] += 1
        return res

    ue.UtilityEvaluation.score_options = score

    # H_FLANK
    ofl = ux.UAVExecutor._flank_target_from_decision

    def flank(self, decision):
        ret = ofl(self, decision)
        ctx = getattr(decision, "uncertainty_context", None) or {}
        C["H_FLANK"]["calls"] += 1
        if ret is not None:
            C["H_FLANK"]["nonnull"] += 1
        if isinstance(ctx, dict) and ("flank_hold_target" in ctx or ctx.get("flank_standoff_hold")):
            C["H_FLANK"]["ctx_flank_keys"] += 1
        return ret

    ux.UAVExecutor._flank_target_from_decision = flank

    # H_SAFETY
    osf = sc.SafetyChecker._reasons_from_execution

    def safety(self, execution_result):
        ret = osf(self, execution_result)
        C["H_SAFETY"]["calls"] += 1
        if ret:
            C["H_SAFETY"]["nonempty"] += 1
        try:
            local = (execution_result or {}).get("local") or {}
            ures = local.get("uav_results") or {}
            for uid, r in ures.items():
                if isinstance(r, dict):
                    for k in ("no_search_target", "partial_success", "failures"):
                        if r.get(k):
                            C["H_SAFETY"]["nested_%s" % k] += 1
            for k in ("no_search_target", "partial_success", "failures"):
                if isinstance(execution_result, dict) and execution_result.get(k):
                    C["H_SAFETY"]["top_%s" % k] += 1
        except Exception as exc:  # recorded
            C["H_SAFETY"]["probe_err_%s" % type(exc).__name__] += 1
        return ret

    sc.SafetyChecker._reasons_from_execution = safety

    # H_RESMAPE
    orp = rp.RescuePlanner.plan

    def rplan(self, *a, **k):
        d = orp(self, *a, **k)
        C["H_RESMAPE"]["plan_selected=%s" % getattr(d, "selected_option_id", None)] += 1
        C["H_RESMAPE"]["plan_victim_id_empty=%s" % (not getattr(d, "victim_id", ""))] += 1
        return d

    rp.RescuePlanner.plan = rplan
    orx = rx.RescueExecutor.execute

    def rexec(self, decision, *a, **k):
        r = orx(self, decision, *a, **k)
        C["H_RESMAPE"]["exec_victim_id_empty=%s" % (not getattr(decision, "victim_id", "") if decision is not None else "None")] += 1
        payload = (r or {}).get("payload") if isinstance(r, dict) else None
        if isinstance(payload, dict):
            for key in ("victim_updates", "firefighter_updates", "runtime_updates"):
                if payload.get(key):
                    C["H_RESMAPE"]["exec_%s_nonempty" % key] += 1
        return r

    rx.RescueExecutor.execute = rexec

    # H_GMP
    ogm = gmp.GlobalMissionPlanner.plan

    def gplan(self, step_index, *a, **k):
        d = ogm(self, step_index, *a, **k)
        snap = k.get("adaptation_space_snapshot")
        gs = getattr(snap, "global_space", None) if snap is not None else None
        opts = list(getattr(gs, "options", ()) or ()) if gs is not None else []
        C["H_GMP"]["fail_safe_mission_in_space"] += sum(1 for o in opts if str(getattr(o, "option_type", "")) == "fail_safe_mission")
        sel = str(getattr(d, "selected_option_id", "") or "")
        C["H_GMP"]["selected_family=%s" % fam(sel)] += 1
        for o in opts:
            if getattr(o, "option_id", None) == sel and str(getattr(o, "option_type", "")) == "fail_safe_mission":
                C["H_GMP"]["fail_safe_mission_selected"] += 1
        return d

    gmp.GlobalMissionPlanner.plan = gplan

    # H_MOVE
    omove = am.UAV.move

    def move(self):
        label = str(getattr(self, "execution_action", "") or "")
        before = self.pos
        moved = omove(self)
        after_label = str(getattr(self, "execution_action", "") or "")
        famlabel = "hold" if "hold" in label.lower() else ("rtb" if "rtb" in label.lower() else "other")
        C["H_MOVE"]["%s|moved=%s" % (famlabel, bool(moved))] += 1
        if label.lower() == "hold" or label.lower().endswith("_hold"):
            C["H_MOVE_holdlabels"]["%s|moved=%s" % (label, bool(moved))] += 1
        return moved

    am.UAV.move = move

    # H_INCID
    oinc = wf.WildFireModel._handle_rescue_incident

    def incident(self, incident):
        try:
            return oinc(self, incident)
        except Exception as exc:
            C["H_INCID"]["%s|%s" % ((incident or {}).get("type"), type(exc).__name__)] += 1
            ev("H_INCID", [cur["step"], (incident or {}).get("type"), (incident or {}).get("victim_id"),
                           type(exc).__name__, str(exc)[:200], traceback.format_exc()[-800:]])
            raise

    wf.WildFireModel._handle_rescue_incident = incident

    # H_SURV
    osurv = am.Firefighter._survival_move

    def surv(self):
        tp = getattr(self, "target_pos", None)
        stalled = bool(getattr(self, "_idle_retreat_stalled", False))
        exiting = bool(getattr(self, "exiting", False))
        role = "carry" if exiting else ("approach" if tp else "idle")
        C["H_SURV"]["%s|stalled_at_entry=%s" % (role, stalled)] += 1
        if tp and stalled:
            ev("H_SURV_latched", [cur["step"], str(getattr(self, "unit_id", "")), list(self.pos) if self.pos else None,
                                  list(tp) if tp else None, exiting])
        return osurv(self)

    am.Firefighter._survival_move = surv

    # H_FINAL (module-level function; all callers look it up in the module at call time)
    ofin = lag._finalize_coverage_target

    def finalize(target, wind_state, **kw):
        out = ofin(target, wind_state, **kw)
        if target is not None and out is not None:
            wind = str(wind_state.get("last_wind_direction") or "?")
            lane = str(wind_state.get("lane_axis"))
            tx0, ty0 = float(target[0]), float(target[1])
            tx1, ty1 = float(out[0]), float(out[1])
            C["H_FINAL_calls"]["%s|lane=%s" % (wind, lane)] += 1
            if tx1 < tx0:
                C["H_FINAL_xpull"]["%s|lane=%s|WEST" % (wind, lane)] += 1
            elif tx1 > tx0:
                C["H_FINAL_xpull"]["%s|lane=%s|EAST" % (wind, lane)] += 1
            if ty1 > ty0:
                C["H_FINAL_ypull"]["%s|lane=%s|NORTH|commit=%s" % (wind, lane, wind_state.get("coverage_y_commit"))] += 1
            elif ty1 < ty0:
                C["H_FINAL_ypull"]["%s|lane=%s|SOUTH|commit=%s" % (wind, lane, wind_state.get("coverage_y_commit"))] += 1
            C["H_FINAL_commit"]["%s|%s" % (wind, wind_state.get("coverage_y_commit"))] += 1
        return out

    lag._finalize_coverage_target = finalize

    # H_UNREACH
    oun = wf.WildFireModel._mark_victim_unreachable

    def unreach(self, victim_id, victim_marker, reason="no_available_firefighter", cause=""):
        C["H_UNREACH"]["%s|%s" % (reason, cause)] += 1
        ev("H_UNREACH", [cur["step"], victim_id, reason, cause])
        return oun(self, victim_id, victim_marker, reason, cause)

    wf.WildFireModel._mark_victim_unreachable = unreach

    # --- per-step invariants from the Part 6 list (#5, #8): pure reads after the step
    orig_step_inv = wf.WildFireModel.step

    def step_inv(self):
        r = orig_step_inv(self)
        try:
            ids = {str(a.unique_id) for a in self.schedule.agents if type(a) is am.UAV and a.pos is not None}
            before = set((getattr(self, "_uav_positions_before_step", {}) or {}).keys())
            if ids - before:
                C["INV_before_positions_missing"]["steps"] += 1
            for ff in (getattr(self, "firefighter_marker_agents", {}) or {}).values():
                rv = getattr(ff, "rescued_victim", None)
                if getattr(ff, "exiting", False) and rv is not None and not getattr(ff, "dead", False) \
                        and ff.pos is not None:
                    C["INV_carry"]["carry_steps"] += 1
                    if getattr(rv, "pos", None) != ff.pos:
                        C["INV_carry"]["victim_not_with_carrier"] += 1
                        ev("INV_carry", [cur["step"], str(ff.unit_id), list(ff.pos),
                                         list(rv.pos) if rv.pos is not None else None])
            for vid, st in (getattr(self, "managed_victims", {}) or {}).items():
                if getattr(st, "rescue_assigned", False) and str(getattr(st, "status", "")) not in ("rescued", "dead", "unreachable"):
                    bound = [f for f in (getattr(self, "firefighter_marker_agents", {}) or {}).values()
                             if getattr(f, "rescued_victim", None) is (getattr(self, "victim_marker_agents", {}) or {}).get(vid)
                             and not getattr(f, "dead", False)]
                    if not bound:
                        C["INV_rescue_assigned_without_ff"]["steps"] += 1
                        ev("INV_rescue_assigned_without_ff", [cur["step"], vid, str(getattr(st, "status", ""))])
        except Exception as exc:  # recorded, never hidden
            C["INV_probe_error"][type(exc).__name__] += 1
        return r

    wf.WildFireModel.step = step_inv

    # --- scoped exception census inside the functions holding decision-path swallow handlers
    SCOPED = collections.Counter()
    SCOPED_EX = {}
    scoped_on = "--no-trace-scoped" not in own
    repo_l = repo.lower()
    state = {"depth": 0, "live": {}}

    def s_local(frame, event, arg):
        if event == "exception":
            exc_type, exc_val, _tb = arg
            if exc_type in (GeneratorExit, StopIteration):
                return s_local
            site = "%s:%d:%s" % (os.path.relpath(frame.f_code.co_filename, repo), frame.f_lineno, frame.f_code.co_name)
            rec = state["live"].get(id(exc_val))
            if rec is None:
                state["live"][id(exc_val)] = [site, site, exc_type.__name__, str(exc_val)[:160], exc_val]
            else:
                rec[1] = site
        return s_local

    def s_global(frame, event, arg):
        fn = frame.f_code.co_filename.lower()
        if fn.startswith(repo_l) and "\\outputs\\" not in fn and "\\.venv\\" not in fn:
            return s_local
        return None

    def scoped(owner, name, label):
        orig = getattr(owner, name)

        def wrapper(*a, **k):
            if state["depth"] > 0:
                return orig(*a, **k)
            state["depth"] += 1
            sys.settrace(s_global)
            escaped = None
            try:
                return orig(*a, **k)
            except BaseException as exc:
                escaped = exc
                raise
            finally:
                sys.settrace(None)
                state["depth"] -= 1
                for key, (origin, last, tname, msg, v) in list(state["live"].items()):
                    tag = "%s || %s | caught_in %s | %s%s" % (label, origin, last, tname,
                                                              " | ESCAPED" if v is escaped else "")
                    SCOPED[tag] += 1
                    SCOPED_EX.setdefault(tag, [cur["step"], msg])
                state["live"].clear()

        setattr(owner, name, wrapper)

    if scoped_on:
        for owner, name in ((wf.WildFireModel, "_process_rescue_incidents"),
                            (wf.WildFireModel, "_sync_victim_agent_status"),
                            (wf.WildFireModel, "_revalidate_route_blocked_firefighters"),
                            (wf.WildFireModel, "_update_uav_stuck_counts_after_move"),
                            (wf.WildFireModel, "_check_fire_casualties"),
                            (wf.WildFireModel, "_process_pending_agent_removals"),
                            (wf.WildFireModel, "_recycle_firefighter_after_exit"),
                            (wf.WildFireModel, "_clear_rescue_path_if_requested"),
                            (wf.WildFireModel, "_update_unreachable_victims"),
                            (am.Firefighter, "advance"),
                            (am.UAV, "advance")):
            if isinstance(_inspect.getattr_static(owner, name), (staticmethod, classmethod)):
                raise SystemExit("SD_HOOKS: scoped target %s.%s is static" % (owner.__name__, name))
            scoped(owner, name, "%s.%s" % (owner.__name__, name))

    # --trace-exc
    EXC = collections.Counter()
    EXC_EX = {}
    if trace_exc:
        repo_l = repo.lower()
        live = {}

        def local_tracer(frame, event, arg):
            if event == "exception":
                exc_type, exc_val, _tb = arg
                key = id(exc_val)
                site = "%s:%d:%s" % (os.path.relpath(frame.f_code.co_filename, repo), frame.f_lineno, frame.f_code.co_name)
                if key not in live:
                    live[key] = [site, site, exc_type.__name__, str(exc_val)[:120], exc_val]
                else:
                    live[key][1] = site
            return local_tracer

        def global_tracer(frame, event, arg):
            fn = frame.f_code.co_filename.lower()
            if fn.startswith(repo_l) and "\\outputs\\" not in fn and "\\.venv\\" not in fn:
                return local_tracer
            return None

        def flush():
            for key, (origin, last, tname, msg, _v) in list(live.items()):
                EXC["%s | caught_in %s | %s" % (origin, last, tname)] += 1
                EXC_EX.setdefault("%s | caught_in %s | %s" % (origin, last, tname), msg)
            live.clear()

        orig_step2 = wf.WildFireModel.step

        def traced_step(self):
            r = orig_step2(self)
            flush()
            return r

        wf.WildFireModel.step = traced_step
        sys.settrace(global_tracer)

    probe = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sd_probe.py"),
                           run_name="sd_probe_module")
    sys.argv = [sys.argv[0]] + probe_args
    rc = probe["main"]()
    if trace_exc:
        sys.settrace(None)
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        d["hooks"] = {"counters": {k: dict(v) for k, v in C.items()}, "events": dict(EV),
                      "scoped_exc": {"on": scoped_on, "counts": dict(SCOPED.most_common(400)),
                                     "examples": {k: SCOPED_EX[k] for k in list(SCOPED_EX)[:400]}},
                      "trace_exc": ({"counts": dict(EXC.most_common(300)), "examples": {k: EXC_EX[k] for k in list(EXC_EX)[:300]}}
                                    if trace_exc else None)}
        tmp = out_path + ".hktmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("SD_HOOKS RECORD FAILED: %r" % (exc,), file=sys.stderr)
        return 5
    print("SD_HOOKS_DONE trace_exc=%s" % trace_exc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
