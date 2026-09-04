"""GLOBAL PLANNER SCOPING probe.

Answers, by hooking the real call sites (never by reading a per-step snapshot):

PART 1  Why is every non-baseline global option scored exactly 0.0?
        Hook UtilityEvaluation._evaluate_global_mission_option and record, per
        option_id per call: (a) the INPUT side - presence and value of every
        parameter key the scorer or its helpers read anywhere; (b) the OUTPUT
        side - the real UtilityTerm list the scorer built, and every scalar it
        put in predicted_effects. No formula is reimplemented; the term values
        are the ones the shipped scorer computed.

PART 2  The deciding experiment. Arm one option so it scores non-zero and see
        how far the effect travels: selection -> MissionDecision -> GlobalExecutor
        -> model state -> simulation outcome. Modes:

          nopatch       no hooks at all (observer-purity control)
          observe       hooks only, nothing armed
          arm_lo        NEGATIVE CONTROL. fire_contribution=0.01 on the fire-front
                        option. Score must move off 0.0 (proving the arm reaches
                        the scorer) yet stay below the ~0.153-0.255 baseline, so
                        selection must NOT change. Separates "the arm did nothing"
                        from "the arm worked but did not cross the threshold".
          arm_hi        fire_contribution=0.9 on the fire-front option. Score must
                        beat the baseline; does the planner now select it?
          arm_role_str  fire_contribution=0.9 on global_role_assignment_fire_tracking,
                        leaving assigned_role as the STRING the generator writes.
                        Tests selection alone.
          arm_role_dict fire_contribution=0.9 on the same option PLUS
                        uav_assignments={<live uav id>: "fire_tracker"} as a proper
                        dict in the LIVE role vocabulary. Bypasses both known
                        plumbing breaks (str-vs-dict at global_mission_planner.py
                        _uav_assignments_from_params, and the fire_tracking-vs-
                        fire_tracker vocabulary gap). POSITIVE CONTROL for outcome
                        sensitivity: if even this moves nothing, the executor path
                        is dead too; if it moves outcomes, the breaks are located
                        exactly between it and arm_role_str.

Scenario params verbatim from outputs/_sc_control.py:35-39 (scenario D), same
canonical 13-run sample as the preceding rounds.

usage:
  _gp_probe.py --mode observe --wind east --roles half --seed 101 --steps 240 --out P.json
  _gp_probe.py --aggregate --glob "outputs/_gp_run_*.json" --out outputs/_gp_probe.json
"""
from __future__ import annotations
import argparse, contextlib, glob as _glob, hashlib, io as _io, json, os, random, sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

MAINTAIN_ID = "global_stability_maintain_current_config"
FIRE_FRONT_ID = "global_coverage_strategy_fire_front_tracking_mode"
ROLE_FT_ID = "global_role_assignment_fire_tracking"

# Every parameter key read anywhere in the global scoring path. Sources:
#   utility_evaluation.py _evaluate_global_mission_option  (the nine pfloat terms
#     plus the gate keys), _compute_switching_cost, _compute_stability_bonus,
#     _compute_negative_information_adjustment, _compute_horizon_context_fit,
#     _apply_confidence_and_uncertainty_adjustment, _check_utility_feasibility
#   global_mission_planner.py  the six MissionDecision extractors
WATCH = [
    # --- the nine weighted utility terms ---
    "fire_contribution", "victim_contribution", "communication_contribution",
    "uncertainty_reduction", "information_recovery", "collision_risk",
    "battery_cost", "drift_risk", "switching_cost",
    # --- gates inside the scorer body ---
    "stability_control", "do_nothing", "mission_mode", "search_mode",
    "recovery_value", "information_recovery_score",
    "from_role", "to_role", "from_uav_role", "to_uav_role", "role_change",
    # --- _compute_switching_cost ---
    "task_change", "recent_switch_count", "role_switch_count", "role_stability_timer",
    # --- _compute_stability_bonus ---
    "maintain_current_config", "keep_current_path", "keep_current_assignment",
    "critical_trigger", "emergency", "immediate_action", "mayday", "criticality",
    # --- _compute_negative_information_adjustment ---
    "negative_observation_recent", "negative_observation_stale",
    "avoids_recent_negative_region", "confirms_stale_negative_region",
    # --- _compute_horizon_context_fit gate (needs ALL SIX) ---
    "horizon_type", "candidate_horizon_length", "uncertainty_level",
    "communication_reliability", "fire_spread_speed", "information_collapse",
    # --- _apply_confidence_and_uncertainty_adjustment ---
    "knowledge_confidence", "confirmation",
    # --- _check_utility_feasibility ---
    "battery_level", "projected_battery_after_option", "hard_collision_violation",
    "route_feasible", "route_feasibility_confidence",
    "requires_critical_communication", "fail_safe_mode", "delivery_confidence",
    # --- the six MissionDecision extractors ---
    "uav_assignments", "role_assignments", "assigned_role",
    "task_assignments", "task_assignment", "target_region",
    "relay_assignments", "relay_assignment", "return_to_base", "recall_order",
]

HZ_REQUIRED = ("horizon_type", "candidate_horizon_length", "uncertainty_level",
               "communication_reliability", "fire_spread_speed", "information_collapse")

CUR = {"step": 0}
REC = {
    "eval_calls": 0,
    "by_option": {},          # option_id -> census
    "select_calls": 0,
    "selected_hist": {},
    "branch_hist": {},
    "rank_of": {},            # option_id -> {rank: count}
    "score_table_step1": [],  # full scored table, first plan call
    "score_table_mid": [],    # full scored table, step ~120
    "param_dump": {},         # option_id -> verbatim summarised params, first sight
    "term_dump": {},          # option_id -> verbatim term list, first sight
    # --- MissionDecision census ---
    "plan_calls": 0,
    "md_nonempty": {},        # field -> count of calls where it was non-empty
    "md_selected_hist": {},
    "md_sample": [],
    # --- GlobalExecutor census ---
    "exec_calls": 0,
    "exec_applied": 0,
    "exec_assign_n": {},      # len(assignments) -> count
    "exec_task_n": {},
    "exec_mode_hist": {},
    "exec_pending_n": {},
    "exec_sample": [],
    # --- model role state census ---
    "role_sig_hist": {},      # "uid=role;..." -> count of steps
    "arm_applied": 0,         # how many times the arming hook actually mutated
    "arm_target": "",
    "arm_uavs_sample": [],
}


def _bump(d, k):
    d[k] = d.get(k, 0) + 1


def _vs(v):
    """Compact, stable summary of a parameter value."""
    if isinstance(v, dict):
        return "<dict:%d>" % len(v)
    if isinstance(v, (list, tuple, set)):
        return "<%s:%d>" % (type(v).__name__, len(v))
    if isinstance(v, bool) or v is None:
        return repr(v)
    if isinstance(v, (int, float)):
        return repr(round(float(v), 6))
    s = repr(v)
    return s if len(s) <= 60 else s[:57] + "..."


def _census(oid):
    c = REC["by_option"].get(oid)
    if c is None:
        c = {
            "calls": 0,
            "key_present": {},     # watched key -> times present in params
            "key_values": {},      # watched key -> {summarised value: count}
            "n_params": {},        # len(params) -> count
            "terms": {},           # term name -> {"n":, "values": {}, "contribs": {}}
            "total": {},           # rounded total_utility -> count
            "feasible": 0,
            "violations": {},
            "confidence": {},
            "pe": {},              # predicted_effects scalar -> {value: count}
            "hz_gate_keys_present": {},   # how many of the six were present
        }
        REC["by_option"][oid] = c
    return c


def install(arm_mode: str):
    """Install arming (if any) plus the four observation hooks."""
    from src_extension.adaptation.global_adaptation_generator import (
        GlobalAdaptationSpaceGenerator as G,
    )
    from src_extension.planning import global_mission_planner as gmp
    from src_extension.planning.utility_evaluation import UtilityEvaluation as UE
    from src_extension.execution.global_executor import GlobalExecutor as GE

    # ------------------------------------------------------------------ ARM
    ARM_SPEC = {
        "arm_lo":            (FIRE_FRONT_ID, {"fire_contribution": 0.01}, None),
        "arm_hi":            (FIRE_FRONT_ID, {"fire_contribution": 0.9}, None),
        "arm_role_str":      (ROLE_FT_ID,    {"fire_contribution": 0.9}, None),
        "arm_role_dict":     (ROLE_FT_ID,    {"fire_contribution": 0.9}, "fire_tracker"),
        "arm_role_dict_gen": (ROLE_FT_ID,    {"fire_contribution": 0.9}, "fire_tracking"),
    }
    spec = ARM_SPEC.get(arm_mode)
    REC["arm_target"] = spec[0] if spec else ""

    orig_generate = G.generate

    def generate(self, gar, rm, ts):
        space = orig_generate(self, gar, rm, ts)
        if spec is None:
            return space
        target_id, inject, role_word = spec
        extra = dict(inject)
        if role_word:
            uav_ids = []
            resource = rm.get("uav_resource_model") if isinstance(rm, dict) else None
            by_id = getattr(resource, "by_uav_id", None)
            if isinstance(by_id, dict):
                uav_ids = sorted(by_id.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
            if uav_ids:
                # "fire_tracker"  = the LIVE vocabulary (wildfire_model._assign_uav_roles:657-663)
                # "fire_tracking" = the vocabulary the GENERATOR emits
                #                   (global_adaptation_generator.py:134 roles list)
                extra["uav_assignments"] = {str(u): role_word for u in uav_ids}
                if len(REC["arm_uavs_sample"]) < 2:
                    REC["arm_uavs_sample"].append(dict(extra["uav_assignments"]))
        for option in getattr(space, "options", ()) or ():
            if str(getattr(option, "option_id", "")) == target_id:
                params = getattr(option, "parameters", None)
                if isinstance(params, dict):
                    params.update(extra)
                    REC["arm_applied"] += 1
        return space

    G.generate = generate

    # ------------------------------------------------- HOOK 1: the scorer
    orig_eval = UE._evaluate_global_mission_option

    def ev(self, option, runtime_models, context, mode):
        result = orig_eval(self, option, runtime_models, context, mode)
        oid = str(getattr(option, "option_id", "") or "")
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}
        c = _census(oid)
        c["calls"] += 1
        REC["eval_calls"] += 1
        _bump(c["n_params"], len(params))
        for k in WATCH:
            if k in params:
                c["key_present"][k] = c["key_present"].get(k, 0) + 1
                _bump(c["key_values"].setdefault(k, {}), _vs(params.get(k)))
        _bump(c["hz_gate_keys_present"], sum(1 for k in HZ_REQUIRED if k in params))
        for t in result.utility_terms:
            e = c["terms"].setdefault(t.name, {"n": 0, "values": {}, "contribs": {}, "weights": {}})
            e["n"] += 1
            _bump(e["values"], repr(round(float(t.value), 9)))
            _bump(e["contribs"], repr(round(float(t.contribution), 9)))
            _bump(e["weights"], repr(round(float(t.weight), 6)))
        _bump(c["total"], repr(round(float(result.total_utility), 9)))
        if result.feasible:
            c["feasible"] += 1
        _bump(c["violations"], "|".join(result.constraint_violations) or "<none>")
        _bump(c["confidence"], repr(round(float(result.confidence_score), 6)))
        for k, v in (result.predicted_effects or {}).items():
            if isinstance(v, (int, float, bool)) or v is None:
                _bump(c["pe"].setdefault(k, {}), _vs(v))
            elif isinstance(v, str):
                _bump(c["pe"].setdefault(k, {}), _vs(v))
        if oid not in REC["param_dump"]:
            REC["param_dump"][oid] = {
                "option_type": str(getattr(option, "option_type", "")),
                "cost_estimate": getattr(option, "cost_estimate", None),
                "risk_estimate": getattr(option, "risk_estimate", None),
                "confidence": getattr(option, "confidence", None),
                "params": {k: _vs(v) for k, v in sorted(params.items())},
            }
            REC["term_dump"][oid] = [
                {"name": t.name, "value": round(float(t.value), 9),
                 "weight": round(float(t.weight), 6),
                 "contribution": round(float(t.contribution), 9),
                 "explanation": t.explanation[:70]}
                for t in result.utility_terms
            ] + [{"name": "<TOTAL>", "value": round(float(result.total_utility), 9),
                  "weight": 0.0, "contribution": round(float(result.total_utility), 9),
                  "explanation": result.explanation_summary[:160]}]
        return result

    UE._evaluate_global_mission_option = ev

    # ---------------------------------------------- HOOK 2: the selection
    orig_select = gmp._select_feasible_option

    def select(scored, options):
        REC["select_calls"] += 1
        for rank, entry in enumerate(scored):
            oid = str(getattr(entry.option, "option_id", "") or "")
            _bump(REC["rank_of"].setdefault(oid, {}), rank)
        table = [{"rank": i, "id": str(getattr(e.option, "option_id", "")),
                  "score": round(float(e.evaluation.total_utility), 9),
                  "feasible": bool(e.evaluation.feasible),
                  "violations": list(e.evaluation.constraint_violations)}
                 for i, e in enumerate(scored)]
        if not REC["score_table_step1"] and len(scored) > 5:
            REC["score_table_step1"] = table
        if not REC["score_table_mid"] and CUR["step"] >= 120 and len(scored) > 5:
            REC["score_table_mid"] = table

        out = orig_select(scored, options)
        first_feasible = None
        for entry in scored:
            if entry.evaluation.feasible:
                first_feasible = entry.option
                break
        if first_feasible is not None and out is first_feasible:
            _bump(REC["branch_hist"], "feasible_loop")
        elif out is None:
            _bump(REC["branch_hist"], "none")
        else:
            _bump(REC["branch_hist"], "maintain_fallback")
        _bump(REC["selected_hist"], str(getattr(out, "option_id", "") or "<none>"))
        return out

    gmp._select_feasible_option = select

    # ------------------------------------------- HOOK 3: the MissionDecision
    orig_plan = gmp.GlobalMissionPlanner.plan

    def plan(self, step_index, triggers=None, **kw):
        d = orig_plan(self, step_index, triggers=triggers, **kw)
        REC["plan_calls"] += 1
        if d is not None:
            fields = {
                "uav_assignments": len(d.uav_assignments),
                "task_assignments": len(d.task_assignments),
                "mission_mode": 1 if str(d.mission_mode).strip() else 0,
                "relay_assignments": len(d.relay_assignments),
                "recall_orders": len(d.recall_orders),
                "uncertainty_context": len(d.uncertainty_context),
            }
            for k, n in fields.items():
                if n:
                    REC["md_nonempty"][k] = REC["md_nonempty"].get(k, 0) + 1
            _bump(REC["md_selected_hist"], str(d.selected_option_id or "<empty>"))
            if len(REC["md_sample"]) < 3:
                REC["md_sample"].append({
                    "step": CUR["step"], "selected_option_id": d.selected_option_id,
                    "uav_assignments": dict(d.uav_assignments),
                    "task_assignments": dict(d.task_assignments),
                    "mission_mode": d.mission_mode,
                    "relay_assignments": dict(d.relay_assignments),
                    "recall_orders": list(d.recall_orders),
                    "uncertainty_context_keys": sorted(d.uncertainty_context.keys()),
                    "confidence_score": round(float(d.confidence_score), 6),
                })
        return d

    gmp.GlobalMissionPlanner.plan = plan

    # ------------------------------------------- HOOK 4: the GlobalExecutor
    orig_exec = GE.execute

    def gexec(self, decision, timestamp=0.0):
        res = orig_exec(self, decision, timestamp)
        REC["exec_calls"] += 1
        if isinstance(res, dict):
            if res.get("applied"):
                REC["exec_applied"] += 1
            _bump(REC["exec_assign_n"], len(res.get("assignments") or {}))
            _bump(REC["exec_task_n"], len(res.get("task_assignments") or {}))
            _bump(REC["exec_mode_hist"], repr(res.get("mission_mode")))
            _bump(REC["exec_pending_n"], len(res.get("pending_commands") or []))
            if len(REC["exec_sample"]) < 3:
                REC["exec_sample"].append({
                    "step": CUR["step"],
                    "applied": res.get("applied"),
                    "reason": res.get("reason"),
                    "assignments": dict(res.get("assignments") or {}),
                    "task_assignments": dict(res.get("task_assignments") or {}),
                    "mission_mode": res.get("mission_mode"),
                    "n_pending": len(res.get("pending_commands") or []),
                })
        return res

    GE.execute = gexec


def role_signature(model):
    """Live role state as the managed system exposes it to behavioural readers."""
    parts = []
    managed = getattr(model, "managed_uav_states", None) or {}
    for uid in sorted(managed, key=lambda x: int(x) if str(x).isdigit() else 0):
        parts.append("%s=%s" % (uid, getattr(managed[uid], "role", None)))
    rm = getattr(model, "uav_resource_model", None)
    by_id = getattr(rm, "by_uav_id", None)
    if isinstance(by_id, dict):
        for uid in sorted(by_id, key=lambda x: int(x) if str(x).isdigit() else 0):
            parts.append("rm:%s=%s" % (uid, getattr(by_id[uid], "current_role", None)))
    return ";".join(parts)


def params(wind, ft, vs):
    """Verbatim from outputs/_sc_control.py:35-39 (scenario D)."""
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


def run(seed, p, steps, track_roles):
    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    from wildfire_model import WildFireModel
    from serve_dashboard import _build_evaluation

    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **p)
    buf = _io.StringIO()
    terminal_step, n = None, 0
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            CUR["step"] = n + 1
            model.step()
            n += 1
            if track_roles:
                _bump(REC["role_sig_hist"], role_signature(model))
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = n
    ev = _build_evaluation(model, terminal_step, n, p)
    poslist = sorted(
        "%s:%s:%s" % (type(a).__name__, getattr(a, "unique_id", ""), a.pos)
        for a in model.schedule.agents if type(a).__name__ != "Fire"
    )
    fires = sorted((x for x in model.schedule.agents
                    if type(x).__name__ == "Fire"), key=lambda x: x.unique_id)
    firemap = "".join(
        "1" if getattr(a, "burning", False) else ("2" if getattr(a, "burnt", False) else "0")
        for a in fires)
    return {
        "eval": {k: ev.get(k) for k in
                 ("rescued", "dead", "unreachable", "never_detected",
                  "geographically_isolated", "firefighter_deaths",
                  "burnt_cells", "rescue_rate", "terminal_step")},
        "stdout_sha256": hashlib.sha256(buf.getvalue().encode("utf-8")).hexdigest(),
        "agent_positions_sha256": hashlib.sha256("\n".join(poslist).encode("utf-8")).hexdigest(),
        "firemap_sha256": hashlib.sha256(firemap.encode("utf-8")).hexdigest(),
        "final_role_signature": role_signature(model),
    }


# ------------------------------------------------------------------ aggregate
def aggregate(pattern, out):
    runs = []
    for path in sorted(_glob.glob(pattern)):
        with open(path, "r", encoding="utf-8") as fh:
            runs.append(json.load(fh))
    by_mode = {}
    for r in runs:
        by_mode.setdefault(r["mode"], []).append(r)

    # --- PART 1 rollup: merge per-option census across every observe run ---
    def merge(mode):
        acc = {}
        for r in by_mode.get(mode, []):
            for oid, c in (r.get("by_option") or {}).items():
                a = acc.setdefault(oid, {"calls": 0, "key_present": {}, "key_values": {},
                                         "terms": {}, "total": {}, "feasible": 0,
                                         "violations": {}, "confidence": {}, "pe": {},
                                         "hz_gate_keys_present": {}, "n_params": {}})
                a["calls"] += c["calls"]
                a["feasible"] += c["feasible"]
                for k, v in c["key_present"].items():
                    a["key_present"][k] = a["key_present"].get(k, 0) + v
                for k, d in c["key_values"].items():
                    t = a["key_values"].setdefault(k, {})
                    for vv, n in d.items():
                        t[vv] = t.get(vv, 0) + n
                for k, d in c["terms"].items():
                    t = a["terms"].setdefault(k, {"n": 0, "values": {}, "contribs": {}, "weights": {}})
                    t["n"] += d["n"]
                    for sub in ("values", "contribs", "weights"):
                        for vv, n in d.get(sub, {}).items():
                            t[sub][vv] = t[sub].get(vv, 0) + n
                for sub in ("total", "violations", "confidence", "hz_gate_keys_present", "n_params"):
                    for vv, n in c.get(sub, {}).items():
                        a[sub][str(vv)] = a[sub].get(str(vv), 0) + n
                for k, d in c["pe"].items():
                    t = a["pe"].setdefault(k, {})
                    for vv, n in d.items():
                        t[vv] = t.get(vv, 0) + n
        return acc

    merged = {m: merge(m) for m in by_mode}

    # --- PART 2 rollup: seed-matched mode-vs-mode outcome comparison ---
    idx = {}
    for r in runs:
        idx.setdefault(r["mode"], {})["%s|%s" % (r["label"], r["seed"])] = r
    base_mode = "nopatch" if "nopatch" in idx else "observe"
    comparisons = {}
    for m in sorted(idx):
        if m == base_mode:
            continue
        rows = []
        for k in sorted(set(idx[base_mode]) & set(idx[m])):
            b, a = idx[base_mode][k], idx[m][k]
            rows.append({
                "run": k,
                "eval_identical": b["eval"] == a["eval"],
                "pos_identical": b["agent_positions_sha256"] == a["agent_positions_sha256"],
                "stdout_identical": b["stdout_sha256"] == a["stdout_sha256"],
                "firemap_identical": b["firemap_sha256"] == a["firemap_sha256"],
                "role_sig_identical": b.get("final_role_signature") == a.get("final_role_signature"),
                "base_eval": b["eval"], "mode_eval": a["eval"],
                "base_role_sig": b.get("final_role_signature"),
                "mode_role_sig": a.get("final_role_signature"),
            })
        comparisons[m] = rows

    per_mode = {}
    for m, rs in by_mode.items():
        sel, arm_applied, exec_assign, md_ne = {}, 0, {}, {}
        armed_scores, armed_ranks = {}, {}
        for r in rs:
            for k, v in (r.get("selected_hist") or {}).items():
                sel[k] = sel.get(k, 0) + v
            arm_applied += r.get("arm_applied", 0)
            for k, v in (r.get("exec_assign_n") or {}).items():
                exec_assign[str(k)] = exec_assign.get(str(k), 0) + v
            for k, v in (r.get("md_nonempty") or {}).items():
                md_ne[k] = md_ne.get(k, 0) + v
            tgt = r.get("arm_target") or ""
            if tgt:
                c = (r.get("by_option") or {}).get(tgt) or {}
                for vv, n in (c.get("total") or {}).items():
                    armed_scores[vv] = armed_scores.get(vv, 0) + n
                for vv, n in ((r.get("rank_of") or {}).get(tgt) or {}).items():
                    armed_ranks[str(vv)] = armed_ranks.get(str(vv), 0) + n
        per_mode[m] = {
            "n_runs": len(rs),
            "selected_hist": sel,
            "arm_applied": arm_applied,
            "arm_target": rs[0].get("arm_target") if rs else "",
            "armed_option_score_hist": armed_scores,
            "armed_option_rank_hist": armed_ranks,
            "exec_assign_n_hist": exec_assign,
            "md_nonempty": md_ne,
            "md_sample": rs[0].get("md_sample") if rs else [],
            "exec_sample": rs[0].get("exec_sample") if rs else [],
            "role_sig_hist_first_run": rs[0].get("role_sig_hist") if rs else {},
            "arm_uavs_sample": rs[0].get("arm_uavs_sample") if rs else [],
        }

    doc = {
        "head": "a78f393",
        "n_runs": len(runs),
        "modes": sorted(by_mode),
        "per_mode": per_mode,
        "outcome_comparisons_vs_%s" % base_mode: comparisons,
        "merged_option_census": merged,
        "score_table_step1": (by_mode.get("observe") or [{}])[0].get("score_table_step1"),
        "param_dump": (by_mode.get("observe") or [{}])[0].get("param_dump"),
        "term_dump": (by_mode.get("observe") or [{}])[0].get("term_dump"),
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
    print("WROTE %s (%d runs, modes=%s)" % (out, len(runs), sorted(by_mode)))
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="observe",
                    choices=["nopatch", "observe", "arm_lo", "arm_hi",
                             "arm_role_str", "arm_role_dict", "arm_role_dict_gen"])
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", choices=["half", "default"], default="half")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--out")
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--glob", default=os.path.join(BASE, "_gp_run_*.json"))
    a = ap.parse_args()

    if a.aggregate:
        aggregate(a.glob, a.out or os.path.join(BASE, "_gp_probe.json"))
        sys.exit(0)

    ft, vs = (2, 2) if a.roles == "half" else (None, None)
    p = params(a.wind, ft, vs)
    label = "D/%s/%s" % (a.wind, a.roles)
    if a.mode != "nopatch":
        install(a.mode)
    base = run(a.seed, p, a.steps, track_roles=(a.mode != "nopatch"))
    res = dict(REC)
    res.update({"label": label, "seed": a.seed, "steps": a.steps, "mode": a.mode,
                "eval": base["eval"], "stdout_sha256": base["stdout_sha256"],
                "agent_positions_sha256": base["agent_positions_sha256"],
                "firemap_sha256": base["firemap_sha256"],
                "final_role_signature": base["final_role_signature"]})
    tgt = res.get("arm_target") or ""
    tcen = (res.get("by_option") or {}).get(tgt) or {}
    print("%-13s %s|%-4d evals=%d sel=%s arm_applied=%d armed_total=%s armed_rank=%s "
          "md_nonempty=%s exec_assign=%s roles=%s"
          % (a.mode, label, a.seed, res["eval_calls"],
             json.dumps(res["selected_hist"]), res["arm_applied"],
             json.dumps(tcen.get("total", {}))[:90],
             json.dumps((res.get("rank_of") or {}).get(tgt, {}))[:60],
             json.dumps(res["md_nonempty"]), json.dumps(res["exec_assign_n"]),
             json.dumps(list(res["role_sig_hist"].keys())[:2])[:110]),
          flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, default=str)
