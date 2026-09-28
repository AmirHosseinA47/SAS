"""Planner round, Part 3: THE SIDECAR - out of tree, pass-through, no source file is modified.

Design: outputs/planner_part1.txt 6.4 and section 7 (SIDECAR SCHEMA). Pattern: outputs/_cl_obs.py.
Wraps attributes of the --repo checkout's modules with PASS-THROUGH observers, runs the inner
harness UNCHANGED in this process via runpy, then writes ONE extra file,
<out-without-.json>.plobs.json. The harness JSON and .stdout.txt are never opened for writing.

Launchers: _pl_obs_stock.py -> outputs/_ffr_harness.py ; _pl_obs_crn.py -> outputs/_fm2_probe_harness.py
(which runs _ffr_harness.py; requires exactly one --set FM2P_CRN=1). Both take the inner
harness's command line.

EVERY WRAP IS A PASS-THROUGH: it calls the original with the same arguments and returns its
result unchanged (exceptions propagate), draws no random number, prints nothing, creates no
attribute on any model or agent object. The only extra computation that touches simulation
code is the P5 counterfactual: score_options + _select_feasible_option (the ORIGINAL functions)
re-run over the planner step's IDENTICAL option tuple, mode and context, on COPIES
(dataclasses.replace(option, parameters=dict(option.parameters))) - the scorer is pure. Its
purity is gated by 7.1 (e) (mode 0) and 7.2 PURITY (mode 1): the same line WITHOUT the sidecar
must equal the run WITH it on every harness key but tag, repo and wall_s.
A bookkeeping failure never reaches the run: it is recorded, and at the end the launcher exits
5 WITHOUT writing the sidecar.

STEP STAMPS: model.evaluation_timesteps_counter at the moment of the event = the harness step t
(uav_steps[t-1] is the state after step t) - the harness's own convention.

SIDECAR JSON (version 1)
  version, harness ("stock"|"crn"), repo, argv, json_sha256 (the harness JSON as the inner
  harness left it), source {module: {"file", "sha256"}} (ABSENT for a module the checkout does
  not have), tool_sha256, absent [names not wrapped], counters, errors
  accessor {"calls", "values": {repr(value): count}} - agents.global_planner_mode() read (with
      the ORIGINAL accessor) before EVERY call of the role-family generator; "ABSENT" when
      the checkout has no accessor (the dfbfbe7 worktree)
  calls {"mode1_builder", "switch_specs", "rov.<fn>": n} - calls of the mode-1 builder and of
      every role_option_values function
  census [[t, sha256 over [(option_id, sorted parameter keys)] of the global space, n_options,
      n_with_nine_or_target]] - one row per generator call
  plan [one row per GlobalMissionPlanner.plan call]:
      t, mode, trig {type: n}, instab [[type, entities]] (OSCILLATION_RISK / INSTABILITY_DETECTED),
      scored [[id, score, feasible]] in rank order, sel, cat SWITCH|BASELINE|OTHER, base,
      margin (selected score - baseline score), tie (a non-baseline selection whose score
      EQUALS the baseline's), ua (MissionDecision.uav_assignments), sel_params (the selected
      SWITCH option's target/from/to), nine {option_id: {nine values, target, from, to}} for
      every SWITCH option scored, cf {"null": id, variant: id} the P5 re-selections (variants:
      each of the nine removed = 0.0, and switching_cost as "switching_cost@1e-12" (the whole
      term) and "switching_cost@0.15" (the recency part only); only when a SWITCH option exists)
  exec [one row per GlobalExecutor.execute call]: t, pre {uid: [managed role, resource role]},
      post {...}, applied (the executor's assignments), decision (selected_option_id)
  dispatch_skips [t, ...] - steps whose dispatcher result has global.skipped
  hooks [[t, uid, old, new]] - WildFireModel.on_uav_role_changed calls
  roles_end [[t, {uid: [managed, resource]}]] - both role stores at the end of every step
  local {"total": {...}, "by_role": {role: {...}}} - the LOCAL path planner's selections
      (local_uav_path_planner._select_feasible_option), per call classified by the branch that
      returned: rtb (return-to-base precedence), wind (wind_aware_victim_search precedence),
      score (the top-scored feasible option), fallback (no feasible option); for rtb/wind also
      *_over_top (the top-scored feasible option was a DIFFERENT option: precedence decided)
      and *_over_top_strict (and it scored strictly higher than the one selected)

EXIT CODES: the inner harness's code when non-zero (no sidecar); 2 bad command line or a path
this run would write already exists; 4 provenance (module imported from outside --repo, model
or step count mismatch, --out missing); 5 observer error. 0 only with the sidecar written.
"""
from __future__ import annotations

import collections
import dataclasses
import functools
import hashlib
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INNER = {"stock": os.path.join(HERE, "_ffr_harness.py"), "crn": os.path.join(HERE, "_fm2_probe_harness.py")}
VERSION = 1
BASELINE_ID = "global_stability_maintain_current_config"
NINE = ("fire_contribution", "victim_contribution", "communication_contribution", "uncertainty_reduction",
        "information_recovery", "collision_risk", "battery_cost", "drift_risk", "switching_cost")
VARIANTS = tuple(v for v in NINE if v != "switching_cost") + ("switching_cost@1e-12", "switching_cost@0.15")
ROV_FUNCS = ("live_role", "other_role", "fire_demand", "stale_demand", "victim_demand", "uncertainty_demand",
             "share", "collision_risk", "battery_cost", "drift_risk", "switching_cost", "switch_option_values",
             "zero_values")
MODULES = (
    ("agents", "agents.py"),
    ("common_fixed_variables", "common_fixed_variables.py"),
    ("wildfire_model", "wildfire_model.py"),
    ("src_extension.adaptation.global_adaptation_generator", "src_extension/adaptation/global_adaptation_generator.py"),
    ("src_extension.planning.global_mission_planner", "src_extension/planning/global_mission_planner.py"),
    ("src_extension.execution.global_executor", "src_extension/execution/global_executor.py"),
    ("src_extension.planning.utility_evaluation", "src_extension/planning/utility_evaluation.py"),
    ("src_extension.adaptation.role_option_values", "src_extension/adaptation/role_option_values.py"),
    ("src_extension.planning.local_uav_path_planner", "src_extension/planning/local_uav_path_planner.py"),
    ("src_extension.execution.decision_dispatcher", "src_extension/execution/decision_dispatcher.py"),
)

_MODELS: list = []
STATE: dict = {
    "counters": collections.Counter(),
    "errors": [],
    "absent": [],
    "accessor": {"calls": 0, "values": collections.Counter()},
    "calls": collections.Counter(),
    "census": [],
    "plan": [],
    "exec": [],
    "dispatch_skips": [],
    "hooks": [],
    "roles_end": [],
    "local": {"total": collections.Counter(), "by_role": collections.defaultdict(collections.Counter)},
}
_CUR: dict = {"in_plan": False, "score_args": None, "scored": None, "options": None, "selected": None}


def _error(where, exc):
    STATE["counters"]["observer_errors"] += 1
    if len(STATE["errors"]) < 50:
        STATE["errors"].append("%s: %r" % (where, exc))


def stamp(model=None) -> int:
    if model is None:
        model = _MODELS[-1] if _MODELS else None
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0) if model is not None else 0


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _under(path, root):
    p = os.path.normcase(os.path.abspath(path))
    r = os.path.normcase(os.path.abspath(root)).rstrip("\\/")
    return p.startswith(r + os.sep)


def _wrap(owner, name, qual, make):
    orig = getattr(owner, name, None)
    if orig is None or not callable(orig):
        STATE["absent"].append(qual)
        return None
    wrapper = make(orig)
    functools.update_wrapper(wrapper, orig)
    setattr(owner, name, wrapper)
    return orig


def _oid(option):
    return str(getattr(option, "option_id", "") or "")


def _params(option):
    p = getattr(option, "parameters", None)
    return p if isinstance(p, dict) else {}


def _is_switch(option):
    return str(getattr(option, "option_type", "") or "") == "role_assignment" and "target_uav_id" in _params(option)


def _roles(model):
    out = {}
    managed = getattr(model, "managed_uav_states", None) or {}
    by_id = getattr(getattr(model, "uav_resource_model", None), "by_uav_id", None) or {}
    for uid in sorted(set(managed) | set(by_id), key=lambda s: (len(str(s)), str(s))):
        m = managed.get(uid)
        r = by_id.get(uid)
        out[str(uid)] = [getattr(m, "role", None) if m is not None else None,
                         getattr(r, "current_role", None) if r is not None else None]
    return out


def _copy_option(option, **overrides):
    params = dict(_params(option))
    params.update(overrides)
    try:
        return dataclasses.replace(option, parameters=params)
    except TypeError:
        import copy
        new = copy.copy(option)
        new.parameters = params
        return new


# ---- install -------------------------------------------------------------------------------------
def install(repo):
    repo = os.path.abspath(repo)
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import importlib
    mods = {}
    source = {}
    for name, rel in MODULES:
        try:
            mod = importlib.import_module(name)
        except ImportError:
            source[name] = "ABSENT"
            STATE["absent"].append(name)
            continue
        path = getattr(mod, "__file__", "") or ""
        want = os.path.normcase(os.path.join(repo, *rel.split("/")))
        if not _under(path, repo) or os.path.normcase(os.path.abspath(path)) != want:
            print("PLOBS PROVENANCE: %s imported from %s, expected %s" % (name, path, want), file=sys.stderr)
            raise SystemExit(4)
        source[name] = {"file": os.path.abspath(path), "sha256": file_sha256(path)}
        mods[name] = mod
    STATE["source"] = source
    am = mods["agents"]
    wf = mods["wildfire_model"]
    gen_mod = mods["src_extension.adaptation.global_adaptation_generator"]
    gmp = mods["src_extension.planning.global_mission_planner"]
    gex = mods["src_extension.execution.global_executor"]
    ue = mods["src_extension.planning.utility_evaluation"]
    lpp = mods["src_extension.planning.local_uav_path_planner"]
    dd = mods["src_extension.execution.decision_dispatcher"]
    rov = mods.get("src_extension.adaptation.role_option_values")
    accessor = getattr(am, "global_planner_mode", None)
    if accessor is None:
        STATE["absent"].append("agents.global_planner_mode")
    Model = wf.WildFireModel
    Gen = gen_mod.GlobalAdaptationSpaceGenerator
    orig_score_options = ue.UtilityEvaluation.score_options
    orig_gsel = gmp._select_feasible_option

    # -- model: capture, step count, end-of-step roles --------------------------------------------
    def make_init(orig):
        def __init__(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                _MODELS.append(self)
                STATE["counters"]["models_built"] += 1
            except Exception as exc:
                _error("init", exc)
            return result
        return __init__
    _wrap(Model, "__init__", "WildFireModel.__init__", make_init)

    def make_step(orig):
        def step(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                STATE["counters"]["model_steps"] += 1
                STATE["roles_end"].append([stamp(self), _roles(self)])
            except Exception as exc:
                _error("step", exc)
            return result
        return step
    _wrap(Model, "step", "WildFireModel.step", make_step)

    def make_hook(orig):
        def on_uav_role_changed(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                args = list(a) + [k.get(n) for n in ("uav_id", "old_role", "new_role") if n in k]
                STATE["hooks"].append([stamp(self)] + [str(x) for x in args[:3]])
            except Exception as exc:
                _error("hook", exc)
            return result
        return on_uav_role_changed
    _wrap(Model, "on_uav_role_changed", "WildFireModel.on_uav_role_changed", make_hook)

    # -- the role-family generator: the accessor value on EVERY call -------------------------------
    def make_role_gen(orig):
        def _generate_role_assignment_options(self, *a, **k):
            try:
                STATE["accessor"]["calls"] += 1
                value = "ABSENT" if accessor is None else accessor()
                STATE["accessor"]["values"][repr(value)] += 1
            except Exception as exc:
                _error("accessor", exc)
            return orig(self, *a, **k)
        return _generate_role_assignment_options
    _wrap(Gen, "_generate_role_assignment_options", "GlobalAdaptationSpaceGenerator._generate_role_assignment_options",
          make_role_gen)

    def make_counter(key):
        def make(orig):
            def counted(*a, **k):
                STATE["calls"][key] += 1
                return orig(*a, **k)
            return counted
        return make
    _wrap(Gen, "_generate_role_switch_options", "GlobalAdaptationSpaceGenerator._generate_role_switch_options",
          make_counter("mode1_builder"))
    _wrap(Gen, "_role_switch_specs", "GlobalAdaptationSpaceGenerator._role_switch_specs", make_counter("switch_specs"))
    if rov is not None:
        for fn in ROV_FUNCS:
            _wrap(rov, fn, "role_option_values." + fn, make_counter("rov." + fn))

    def make_generate(orig):
        def generate(self, *a, **k):
            space = orig(self, *a, **k)
            try:
                rows = []
                special = 0
                for o in getattr(space, "options", []) or []:
                    keys = sorted(str(x) for x in _params(o).keys())
                    rows.append([_oid(o), keys])
                    if "target_uav_id" in keys or set(NINE) & set(keys):
                        special += 1
                digest = hashlib.sha256(json.dumps(rows).encode("utf-8")).hexdigest()[:16]
                STATE["census"].append([stamp(), digest, len(rows), special])
            except Exception as exc:
                _error("generate", exc)
            return space
        return generate
    _wrap(Gen, "generate", "GlobalAdaptationSpaceGenerator.generate", make_generate)

    # -- the global planner: scoring args, selection, the decision ---------------------------------
    def make_score_options(orig):
        def score_options(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                if _CUR["in_plan"] and _CUR["score_args"] is None:
                    names = ("options", "runtime_models", "context", "mode")
                    args = dict(zip(names, a))
                    args.update({n: k[n] for n in names if n in k})
                    _CUR["score_args"] = (self, args)
            except Exception as exc:
                _error("score_options", exc)
            return result
        return score_options
    _wrap(ue.UtilityEvaluation, "score_options", "UtilityEvaluation.score_options", make_score_options)

    def make_gsel(orig):
        def _select_feasible_option(scored, options):
            result = orig(scored, options)
            try:
                if _CUR["in_plan"] and _CUR["scored"] is None:
                    _CUR["scored"] = scored
                    _CUR["options"] = options
                    _CUR["selected"] = result
            except Exception as exc:
                _error("gsel", exc)
            return result
        return _select_feasible_option
    _wrap(gmp, "_select_feasible_option", "global_mission_planner._select_feasible_option", make_gsel)

    def counterfactuals(evaluator, args, options, actual_id):
        """P5 on copies; the ORIGINAL score_options / selection."""
        def reselect(opts):
            scored = orig_score_options(evaluator, opts, runtime_models=args.get("runtime_models"),
                                        context=args.get("context"), mode=args.get("mode"))
            return _oid(orig_gsel(scored, opts))
        out = {"null": reselect(tuple(_copy_option(o) for o in options))}
        if any(_is_switch(o) for o in options):
            for variant in VARIANTS:
                if variant.startswith("switching_cost@"):
                    key, val = "switching_cost", float(variant.split("@")[1])
                else:
                    key, val = variant, 0.0
                opts = tuple(_copy_option(o, **{key: val}) if _is_switch(o) else _copy_option(o) for o in options)
                out[variant] = reselect(opts)
        return out

    def make_plan(orig):
        def plan(self, *a, **k):
            _CUR.update(in_plan=True, score_args=None, scored=None, options=None, selected=None)
            try:
                decision = orig(self, *a, **k)
            finally:
                _CUR["in_plan"] = False
            try:
                row = {"t": stamp()}
                scored = _CUR["scored"] or ()
                args = _CUR["score_args"][1] if _CUR["score_args"] else {}
                row["mode"] = args.get("mode")
                snap = k.get("analysis_snapshot")
                trig = collections.Counter()
                instab = []
                for t in (getattr(snap, "all_triggers", None) or ()):
                    tt = str(getattr(t, "trigger_type", "") or "")
                    trig[tt] += 1
                    if tt in ("OSCILLATION_RISK", "INSTABILITY_DETECTED"):
                        instab.append([tt, [str(e) for e in (getattr(t, "affected_entities", ()) or ())]])
                row["trig"] = dict(trig)
                row["instab"] = instab
                row["scored"] = [[e.evaluation.option_id, float(e.score), bool(e.evaluation.feasible)] for e in scored]
                sel = _CUR["selected"]
                sel_id = _oid(sel) if sel is not None else ""
                row["sel"] = sel_id
                row["cat"] = "SWITCH" if (sel is not None and _is_switch(sel)) else (
                    "BASELINE" if sel_id == BASELINE_ID else "OTHER")
                score_of = {e.evaluation.option_id: float(e.score) for e in scored}
                base = score_of.get(BASELINE_ID)
                row["base"] = base
                sel_score = score_of.get(sel_id)
                row["margin"] = None if (base is None or sel_score is None) else sel_score - base
                row["tie"] = bool(sel_id != BASELINE_ID and base is not None and sel_score == base)
                row["ua"] = dict(getattr(decision, "uav_assignments", {}) or {}) if decision is not None else None
                row["decision_sel"] = str(getattr(decision, "selected_option_id", "") or "") if decision is not None else None
                if row["cat"] == "SWITCH":
                    p = _params(sel)
                    row["sel_params"] = {"target": str(p.get("target_uav_id")), "from": p.get("from_role"),
                                         "to": p.get("to_role")}
                nine = {}
                options = _CUR["options"] or ()
                for o in options:
                    if _is_switch(o):
                        p = _params(o)
                        d = {v: p.get(v) for v in NINE}
                        d.update(target=str(p.get("target_uav_id")), frm=p.get("from_role"), to=p.get("to_role"))
                        nine[_oid(o)] = d
                row["nine"] = nine
                if _CUR["score_args"] is not None and options:
                    row["cf"] = counterfactuals(_CUR["score_args"][0], args, tuple(options), sel_id)
                else:
                    row["cf"] = None
                STATE["plan"].append(row)
            except Exception as exc:
                _error("plan", exc)
            return decision
        return plan
    _wrap(gmp.GlobalMissionPlanner, "plan", "GlobalMissionPlanner.plan", make_plan)

    # -- the executor ---------------------------------------------------------------------------------
    def make_exec(orig):
        def execute(self, *a, **k):
            model = getattr(self, "_model", None)
            pre = None
            try:
                pre = _roles(model) if model is not None else None
            except Exception as exc:
                _error("exec pre", exc)
            result = orig(self, *a, **k)
            try:
                decision = a[0] if a else k.get("decision")
                STATE["exec"].append({
                    "t": stamp(model), "pre": pre, "post": _roles(model) if model is not None else None,
                    "applied": dict(result.get("assignments", {}) or {}) if isinstance(result, dict) else None,
                    "decision": str(getattr(decision, "selected_option_id", "") or "") if decision is not None else None,
                })
            except Exception as exc:
                _error("exec", exc)
            return result
        return execute
    _wrap(gex.GlobalExecutor, "execute", "GlobalExecutor.execute", make_exec)

    def make_dispatch(orig):
        def dispatch(self, *a, **k):
            result = orig(self, *a, **k)
            try:
                g = result.get("global") if isinstance(result, dict) else None
                if isinstance(g, dict) and g.get("skipped"):
                    STATE["dispatch_skips"].append(stamp(getattr(self, "_model", None)))
            except Exception as exc:
                _error("dispatch", exc)
            return result
        return dispatch
    _wrap(dd.DecisionDispatcher, "dispatch", "DecisionDispatcher.dispatch", make_dispatch)

    # -- the LOCAL path planner: precedence vs score (finding 11A (b), ruled 2026-09-28) ----------
    def make_lsel(orig):
        def _select_feasible_option(scored, options):
            result = orig(scored, options)
            try:
                feas = [e for e in scored if e.evaluation.feasible]
                rtb = next((e for e in feas if _oid(e.option).startswith("local_path_return_to_base")), None)
                wind = next((e for e in feas if _oid(e.option) == "wind_aware_victim_search"), None)
                if rtb is not None:
                    branch, chosen = "rtb", rtb
                elif wind is not None:
                    branch, chosen = "wind", wind
                elif feas:
                    branch, chosen = "score", feas[0]
                else:
                    branch, chosen = "fallback", None
                if chosen is not None and chosen.option is not result:
                    STATE["counters"]["local_branch_mismatch"] += 1
                model = _MODELS[-1] if _MODELS else None
                uid = None
                for o in options:
                    uid = getattr(o, "target_entity", None)
                    if uid is not None:
                        break
                role = None
                if model is not None and uid is not None:
                    try:
                        role = model._uav_assignment_role(str(uid))
                    except Exception:
                        role = None
                keys = ["calls", branch]
                if branch in ("rtb", "wind") and feas and feas[0].option is not chosen.option:
                    keys.append(branch + "_over_top")
                    if float(feas[0].score) > float(chosen.score):
                        keys.append(branch + "_over_top_strict")
                for key in keys:
                    STATE["local"]["total"][key] += 1
                    STATE["local"]["by_role"][str(role)][key] += 1
            except Exception as exc:
                _error("local select", exc)
            return result
        return _select_feasible_option
    _wrap(lpp, "_select_feasible_option", "local_uav_path_planner._select_feasible_option", make_lsel)
    return repo


def sidecar_path(out):
    return (out[:-5] if out.endswith(".json") else out) + ".plobs.json"


def _argv_value(argv, flag):
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def _set_items(argv):
    out = []
    for i, a in enumerate(argv):
        item = argv[i + 1] if (a == "--set" and i + 1 < len(argv)) else None
        if item is not None and "=" in item:
            k, v = item.split("=", 1)
            out.append((k.strip(), v))
    return out


def main(harness):
    argv = list(sys.argv[1:])
    repo = _argv_value(argv, "--repo")
    out = _argv_value(argv, "--out")
    if harness not in INNER or repo is None or out is None:
        print("PLOBS: bad command line", file=sys.stderr)
        return 2
    fm2p = [(k, v) for k, v in _set_items(argv) if k.startswith("FM2P_")]
    if harness == "stock" and fm2p:
        print("PLOBS: FM2P_ keys on the stock instrument", file=sys.stderr)
        return 2
    if harness == "crn" and [v.strip() for k, v in fm2p if k == "FM2P_CRN"] != ["1"]:
        print("PLOBS: the CRN instrument needs exactly one --set FM2P_CRN=1", file=sys.stderr)
        return 2
    try:
        want_steps = int(_argv_value(argv, "--steps") or 240)
    except ValueError:
        return 2
    stdout_txt = (out[:-5] if out.endswith(".json") else out) + ".stdout.txt"
    writes = [out, out + ".tmp", stdout_txt, sidecar_path(out), sidecar_path(out) + ".tmp"]
    if harness == "crn":
        writes.append(out + ".fm2p.tmp")
    present = [p for p in writes if os.path.lexists(p)]
    if present:
        print("PLOBS: refusing - path(s) exist: %s" % ", ".join(present), file=sys.stderr)
        return 2
    tools = [os.path.abspath(__file__), os.path.abspath(sys.argv[0]), INNER[harness]]
    if harness == "crn":
        tools.append(INNER["stock"])
    tool_sha = {os.path.basename(p): file_sha256(p) for p in tools}
    repo_abs = install(repo)
    sys.argv = [INNER[harness]] + argv
    code = 0
    try:
        runpy.run_path(INNER[harness], run_name="__main__")
    except SystemExit as exc:
        code = 1 if isinstance(exc.code, str) else int(exc.code or 0)
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
    if code != 0:
        return code
    c = STATE["counters"]
    if len(_MODELS) != 1 or c["models_built"] != 1 or c["model_steps"] != want_steps:
        print("PLOBS PROVENANCE: models=%d steps=%d want %d" % (len(_MODELS), c["model_steps"], want_steps),
              file=sys.stderr)
        return 4
    try:
        json_sha = file_sha256(out)
    except OSError:
        return 4
    if c["observer_errors"]:
        print("PLOBS: %d observer error(s) - no sidecar" % c["observer_errors"], file=sys.stderr)
        for e in STATE["errors"]:
            print("  " + e, file=sys.stderr)
        return 5
    rec = {
        "version": VERSION, "harness": harness, "repo": repo_abs, "argv": argv, "json_sha256": json_sha,
        "source": STATE["source"], "tool_sha256": tool_sha, "absent": STATE["absent"],
        "counters": dict(c), "accessor": {"calls": STATE["accessor"]["calls"],
                                          "values": dict(STATE["accessor"]["values"])},
        "calls": dict(STATE["calls"]), "census": STATE["census"], "plan": STATE["plan"], "exec": STATE["exec"],
        "dispatch_skips": STATE["dispatch_skips"], "hooks": STATE["hooks"], "roles_end": STATE["roles_end"],
        "local": {"total": dict(STATE["local"]["total"]),
                  "by_role": {k: dict(v) for k, v in STATE["local"]["by_role"].items()}},
    }
    path = sidecar_path(out)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f)
    os.replace(path + ".tmp", path)
    return 0
