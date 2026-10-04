"""isTrue round Part 1: RECORD-ONLY runtime type census at every `is True` / `is False` identity site.

usage: _ist_probe.py --census-out <census.json> -- <_ffr_harness.py args ...>   (--repo is required there)

Runs outputs/_ffr_harness.py unchanged (runpy, run_name "__main__") after installing pass-through hooks. Each
hook calls the original exactly once with the original arguments and returns its result unchanged; it draws
from no RNG and writes into no simulation object (it only reads attributes and builds its own counters). An
observer exception is recorded in "errors", never raised. The harness JSON (--out) is written exactly as a bare
harness run writes it; the census goes to --census-out.

A value is recorded as "<category>:<truth>", category = None | bool (Python bool) | numpy.<type name> (any
type whose __module__ is numpy; numpy 2's numpy.bool_ reports the name "bool", so it shows as numpy.bool) |
<builtin type name>, truth = T / F (bool(value)) or "?" when bool() raises. "absent" = the key is not in the
dict. A numpy.bool:T at an `is True` site, or numpy.bool:F at an `is False` site, is a reachable divergence
from truthiness; numpy.int*/numpy.float32 at a parser-style helper is too (neither is an int/float subclass).

Hooks (site -> hook point):
  agents.py:422 (MR1)               UAV.surrounding_states: the same Moore box re-read; per step the model's own
                                    sum (literal `is True`) vs the truthiness count; burning value categories
  fire                              WildFireModel.step (after it returns): every Fire agent's `burning` category,
                                    per step [t, truthy, is True]
  wildfire_model.py:2544            WildFireModel._has_pending_execution_directions: calls and results; after
                                    every step, the categories of uav_results[*]["applied"] it would read
  constraint_filter.py:198/200      ConstraintFilter._feasibility_reasons: parameters "feasible" / "infeasible"
                                    (+ ConstraintFilter.filter_options: a key census of every generated option)
  global_analyzer.py:1136           GlobalAnalyzer._unsafe_uav_ids: by_uav_id presence, unsafe/critical_issue/
                                    system_fault per entry
  global_analyzer.py:1145/1149      GlobalAnalyzer._fleet_level_unsafe (staticmethod): system_unsafe /
                                    fleet_emergency at both layers
  global_analyzer.py:1284           GlobalAnalyzer._analyze_communication: knowledge_desync_risk / desync_risk
  local_uav_monitor.py:184          LocalUAVMonitor._compute_information_gain (before the call; the method does
                                    not write the map): _prev_fov_cell_uncertain.get(cell) per cell
  4 planner _is_truthy              module attribute replaced (callers resolve the module global at call time)
  planner_selection.py:70           planner_selection._is_maintain_option: the three marker keys
  utility_evaluation.py:274-288     UtilityEvaluation._check_utility_feasibility: the four keys of the merged dict
  utility_evaluation.py ptruth*,    UtilityEvaluation.evaluate_option: a key census of option.parameters and of
    _indicator, sig                 the context (every closure reads option.parameters)
  safe_float (sibling class)        every module attribute bound to utility_evaluation.safe_float: the categories
                                    of non-None values that are not bool/int/float/str (they return the default),
                                    with the calling function's name (v2: for pfloat, also the parameter key and
                                    the evaluator that called it; v1 = wave 1 recorded the caller name only)
"""
from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ABSENT = object()


def cat(v) -> str:
    if v is ABSENT:
        return "absent"
    if v is None:
        return "None"
    t = type(v)
    if t is bool:
        name = "bool"
    elif t.__module__ == "numpy":
        name = "numpy." + t.__name__
    else:
        name = t.__name__
    try:
        truth = "T" if bool(v) else "F"
    except Exception:
        truth = "?"
    return "%s:%s" % (name, truth)


class Census:
    def __init__(self):
        self.sites: dict[str, Counter] = defaultdict(Counter)
        self.keys_ue: dict[str, Counter] = defaultdict(Counter)
        self.keys_ctx: dict[str, Counter] = defaultdict(Counter)
        self.keys_cf: dict[str, Counter] = defaultdict(Counter)
        self.safe_float_fell: Counter = Counter()
        self.safe_float_calls = 0
        self.calls: Counter = Counter()
        self.fire_steps: list = []
        self.mr1_steps: list = []
        self.keysets: dict[str, list] = defaultdict(list)
        self.errors: list = []
        self.step = 0
        self._mr1_acc = None

    def tally(self, site: str, v) -> None:
        self.sites[site][cat(v)] += 1

    def err(self, where: str, exc: BaseException) -> None:
        if len(self.errors) < 50:
            self.errors.append("%s: %r" % (where, exc))

    def keyset(self, where: str, keys) -> None:
        ks = sorted(str(k) for k in keys)
        slot = self.keysets[where]
        if ks not in slot and len(slot) < 6:
            slot.append(ks)

    def as_json(self) -> dict:
        return {
            "sites": {k: dict(v) for k, v in sorted(self.sites.items())},
            "keys_option_parameters_scored": {k: dict(v) for k, v in sorted(self.keys_ue.items())},
            "keys_context_scored": {k: dict(v) for k, v in sorted(self.keys_ctx.items())},
            "keys_option_parameters_generated": {k: dict(v) for k, v in sorted(self.keys_cf.items())},
            "safe_float_calls": self.safe_float_calls,
            "safe_float_fell_to_default": {"%s|%s" % k: n for k, n in sorted(self.safe_float_fell.items())},
            "calls": dict(self.calls),
            "fire_steps": self.fire_steps,
            "mr1_steps": self.mr1_steps,
            "keysets": dict(self.keysets),
            "errors": self.errors,
        }


C = Census()


def install(repo: str) -> dict:
    import agents
    import wildfire_model as wf
    from src_extension.adaptation.constraint_filter import ConstraintFilter
    from src_extension.analysis.global_analyzer import GlobalAnalyzer
    from src_extension.monitoring.local_uav_monitor import LocalUAVMonitor
    from src_extension.planning import (fail_safe_planner, global_mission_planner, local_uav_path_planner,
                                        planner_selection, rescue_planner, utility_evaluation as ue)
    mods = (agents, wf, ue, planner_selection, fail_safe_planner, global_mission_planner, local_uav_path_planner,
            rescue_planner, sys.modules[ConstraintFilter.__module__], sys.modules[GlobalAnalyzer.__module__],
            sys.modules[LocalUAVMonitor.__module__])
    for m in mods:
        p = os.path.abspath(m.__file__)
        if not p.lower().startswith(repo.lower()):
            raise SystemExit("IST IMPORT MISMATCH: %s from %s, expected under %s" % (m.__name__, p, repo))

    Fire, UAV = agents.Fire, agents.UAV

    # ---- fire + MR1 (agents.py:422)
    o_step = wf.WildFireModel.step

    def step(self, *a, **kw):
        C.step += 1
        C._mr1_acc = [0, 0, 0]
        r = o_step(self, *a, **kw)
        try:
            truthy = is_true = 0
            for ag in self.schedule.agents:
                if type(ag) is Fire:
                    b = ag.burning
                    C.tally("fire.burning", b)
                    if b:
                        truthy += 1
                    if b is True:
                        is_true += 1
            C.fire_steps.append([C.step, truthy, is_true])
            C.mr1_steps.append([C.step] + list(C._mr1_acc))
            res = getattr(self, "latest_execution_result", None)
            if isinstance(res, dict):
                for sec in ("fail_safe", "local"):
                    s = res.get(sec)
                    if isinstance(s, dict) and isinstance(s.get("uav_results"), dict):
                        for ur in s["uav_results"].values():
                            if isinstance(ur, dict):
                                C.tally("wildfire_model.py:2544 applied (post-step read)", ur.get("applied", ABSENT))
        except Exception as exc:
            C.err("step", exc)
        return r

    wf.WildFireModel.step = step

    o_ss = UAV.surrounding_states

    def surrounding_states(self, *a, **kw):
        r = o_ss(self, *a, **kw)
        try:
            C.calls["UAV.surrounding_states"] += 1
            cells = self.model.grid.get_neighborhood(self.pos, moore=self.moore, include_center=True,
                                                     radius=agents.UAV_OBSERVATION_RADIUS)
            lit = cor = 0
            for cell in cells:
                for ag in self.model.grid.get_cell_list_contents([cell]):
                    if type(ag) is Fire:
                        b = ag.is_burning()
                        C.tally("agents.py:422", b)
                        lit += 1 if b is True else 0
                        cor += 1 if b else 0
            if lit != sum(r):
                C.err("surrounding_states", AssertionError("literal %d != model sum %d" % (lit, sum(r))))
            if C._mr1_acc is not None:
                C._mr1_acc[0] += sum(r)
                C._mr1_acc[1] += cor
                C._mr1_acc[2] += 1
        except Exception as exc:
            C.err("surrounding_states", exc)
        return r

    UAV.surrounding_states = surrounding_states

    # ---- wildfire_model.py:2544
    o_pend = wf.WildFireModel._has_pending_execution_directions

    def pend(self, *a, **kw):
        r = o_pend(self, *a, **kw)
        C.calls["WildFireModel._has_pending_execution_directions"] += 1
        C.tally("wildfire_model.py:2544 result", r)
        return r

    wf.WildFireModel._has_pending_execution_directions = pend

    # ---- constraint_filter.py:198/200
    o_fr = ConstraintFilter._feasibility_reasons

    def feas(self, option, *a, **kw):
        try:
            params = getattr(option, "parameters", None) or {}
            C.tally("constraint_filter.py:198 feasible", params.get("feasible", ABSENT))
            C.tally("constraint_filter.py:200 infeasible", params.get("infeasible", ABSENT))
        except Exception as exc:
            C.err("_feasibility_reasons", exc)
        return o_fr(self, option, *a, **kw)

    ConstraintFilter._feasibility_reasons = feas

    o_fo = ConstraintFilter.filter_options

    def filter_options(self, options, *a, **kw):
        try:
            C.calls["ConstraintFilter.filter_options"] += 1
            for option in options or ():
                params = getattr(option, "parameters", None)
                if isinstance(params, dict):
                    for k, v in params.items():
                        C.keys_cf[str(k)][cat(v)] += 1
        except Exception as exc:
            C.err("filter_options", exc)
        return o_fo(self, options, *a, **kw)

    ConstraintFilter.filter_options = filter_options

    # ---- global_analyzer.py:1136 / 1145 / 1149 / 1284
    unwrap = GlobalAnalyzer._unwrap_summary_layer
    o_uu = GlobalAnalyzer._unsafe_uav_ids

    def unsafe_ids(self, by_uav, global_snapshot, *a, **kw):
        try:
            C.calls["GlobalAnalyzer._unsafe_uav_ids"] += 1
            team = unwrap(global_snapshot.get("uav_team_summary"))
            C.keyset("uav_team_summary (unwrapped)", team.keys())
            inner = team.get("value", team) if isinstance(team, dict) else {}
            by_snap = inner.get("by_uav_id", ABSENT) if isinstance(inner, dict) else ABSENT
            if not isinstance(by_snap, dict):
                C.tally("global_analyzer.py:1136 by_uav_id", by_snap)
            else:
                for info in by_snap.values():
                    if isinstance(info, dict):
                        for key in ("unsafe", "critical_issue", "system_fault"):
                            C.tally("global_analyzer.py:1136 " + key, info.get(key, ABSENT))
        except Exception as exc:
            C.err("_unsafe_uav_ids", exc)
        return o_uu(self, by_uav, global_snapshot, *a, **kw)

    GlobalAnalyzer._unsafe_uav_ids = unsafe_ids

    o_fl = GlobalAnalyzer.__dict__["_fleet_level_unsafe"].__func__

    def fleet(global_snapshot, *a, **kw):
        try:
            C.calls["GlobalAnalyzer._fleet_level_unsafe"] += 1
            raw = global_snapshot.get("uav_team_summary")
            if isinstance(raw, dict):
                C.tally("global_analyzer.py:1145 system_unsafe", raw.get("system_unsafe", ABSENT))
                C.tally("global_analyzer.py:1145 fleet_emergency", raw.get("fleet_emergency", ABSENT))
                inner = raw.get("value", ABSENT)
                if isinstance(inner, dict):
                    C.tally("global_analyzer.py:1149 system_unsafe", inner.get("system_unsafe", ABSENT))
                    C.tally("global_analyzer.py:1149 fleet_emergency", inner.get("fleet_emergency", ABSENT))
                else:
                    C.tally("global_analyzer.py:1149 value layer", inner)
            else:
                C.tally("global_analyzer.py:1145 uav_team_summary", raw)
        except Exception as exc:
            C.err("_fleet_level_unsafe", exc)
        return o_fl(global_snapshot, *a, **kw)

    GlobalAnalyzer._fleet_level_unsafe = staticmethod(fleet)

    o_ac = GlobalAnalyzer._analyze_communication

    def comm(self, sop, global_snapshot, *a, **kw):
        try:
            C.calls["GlobalAnalyzer._analyze_communication"] += 1
            snap = unwrap(global_snapshot.get("communication_summary"))
            C.keyset("communication_summary (unwrapped)", snap.keys())
            C.tally("global_analyzer.py:1284 knowledge_desync_risk", snap.get("knowledge_desync_risk", ABSENT))
            C.tally("global_analyzer.py:1284 desync_risk", snap.get("desync_risk", ABSENT))
        except Exception as exc:
            C.err("_analyze_communication", exc)
        return o_ac(self, sop, global_snapshot, *a, **kw)

    GlobalAnalyzer._analyze_communication = comm

    # ---- local_uav_monitor.py:184
    o_ig = LocalUAVMonitor._compute_information_gain

    def info_gain(self, cells, *a, **kw):
        try:
            C.calls["LocalUAVMonitor._compute_information_gain"] += 1
            prev = self._prev_fov_cell_uncertain
            for cell in cells:
                C.tally("local_uav_monitor.py:184", prev.get(cell))
        except Exception as exc:
            C.err("_compute_information_gain", exc)
        return o_ig(self, cells, *a, **kw)

    LocalUAVMonitor._compute_information_gain = info_gain

    # ---- the four planner _is_truthy helpers
    for mod, line in ((fail_safe_planner, 486), (global_mission_planner, 303), (local_uav_path_planner, 641),
                      (rescue_planner, 412)):
        site = "%s.py:%d" % (mod.__name__.rsplit(".", 1)[-1], line)
        orig = mod._is_truthy

        def make(orig=orig, site=site):
            def _is_truthy(value):
                C.tally(site, value)
                return orig(value)
            return _is_truthy

        mod._is_truthy = make()

    # ---- planner_selection.py:70
    o_im = planner_selection._is_maintain_option

    def is_maintain(option, *a, **kw):
        try:
            params = getattr(option, "parameters", None)
            params = params if isinstance(params, dict) else {}
            for key in planner_selection._MAINTAIN_TYPE_MARKERS:
                C.tally("planner_selection.py:70 " + key, params.get(key, ABSENT))
        except Exception as exc:
            C.err("_is_maintain_option", exc)
        return o_im(option, *a, **kw)

    planner_selection._is_maintain_option = is_maintain

    # ---- utility_evaluation.py:274-288 and the closures
    o_cuf = ue.UtilityEvaluation._check_utility_feasibility

    def cuf(self, option, context=None, *a, **kw):
        try:
            merged = ue.UtilityEvaluation._merge_params_for_feasibility(option, context)
            for line, key in ((274, "hard_collision_violation"), (280, "route_feasible"),
                              (287, "requires_critical_communication"), (288, "fail_safe_mode")):
                C.tally("utility_evaluation.py:%d %s" % (line, key), merged.get(key, ABSENT))
        except Exception as exc:
            C.err("_check_utility_feasibility", exc)
        return o_cuf(self, option, context, *a, **kw)

    ue.UtilityEvaluation._check_utility_feasibility = cuf

    o_eo = ue.UtilityEvaluation.evaluate_option

    def evaluate_option(self, option, *a, **kw):
        try:
            C.calls["UtilityEvaluation.evaluate_option"] += 1
            params = getattr(option, "parameters", None)
            if isinstance(params, dict):
                for k, v in params.items():
                    C.keys_ue[str(k)][cat(v)] += 1
            ctx = kw.get("context", a[1] if len(a) > 1 else None)
            if isinstance(ctx, dict):
                for k, v in ctx.items():
                    C.keys_ctx[str(k)][cat(v)] += 1
            else:
                C.keys_ctx["<context object>"][cat(ctx).split(":")[0]] += 1
        except Exception as exc:
            C.err("evaluate_option", exc)
        return o_eo(self, option, *a, **kw)

    ue.UtilityEvaluation.evaluate_option = evaluate_option

    # ---- safe_float (the isinstance sibling at utility_evaluation.py:1595), every by-name binding
    o_sf = ue.safe_float

    def safe_float(value, default=0.0):
        C.safe_float_calls += 1
        if not (value is None or isinstance(value, (bool, int, float, str))):
            try:
                fr = sys._getframe(1)
                caller = fr.f_code.co_name
                key = fr.f_locals.get("key") if caller == "pfloat" else None  # v2: pfloat's loop key
                if key is not None:
                    caller = "%s[%s] in %s" % (caller, key, fr.f_back.f_code.co_name if fr.f_back else "?")
            except Exception:
                caller = "?"
            C.safe_float_fell[(caller, cat(value))] += 1
        return o_sf(value, default)

    rebound = []
    for name, m in list(sys.modules.items()):
        if m is not None and getattr(m, "safe_float", None) is o_sf:
            setattr(m, "safe_float", safe_float)
            rebound.append(name)
    return {"safe_float_rebound": sorted(rebound)}


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _ist_probe.py --census-out <path> -- <_ffr_harness.py args>", file=sys.stderr)
        return 2
    own, hargs = argv[:argv.index("--")], argv[argv.index("--") + 1:]
    if len(own) != 2 or own[0] != "--census-out":
        print("IST REFUSED: own args must be exactly --census-out <path>", file=sys.stderr)
        return 2
    census_out = own[1]
    if "--repo" not in hargs:
        print("IST REFUSED: --repo is required (probes must never default to the main checkout)", file=sys.stderr)
        return 2
    repo = os.path.abspath(hargs[hargs.index("--repo") + 1])
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    try:
        head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        head = None
    info = install(repo)
    harness = os.path.join(HERE, "_ffr_harness.py")
    sys.argv = [harness] + hargs
    code = None
    t0 = time.perf_counter()
    try:
        runpy.run_path(harness, run_name="__main__")
    except SystemExit as exc:
        code = exc.code
    finally:
        out = {"probe": "ist census v2", "repo": repo, "head": head, "harness_args": hargs,
               "harness_exit": code, "wall_s": round(time.perf_counter() - t0, 1), "steps_seen": C.step}
        out.update(info)
        out.update(C.as_json())
        tmp = census_out + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, indent=1)
        os.replace(tmp, census_out)
    return int(code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
