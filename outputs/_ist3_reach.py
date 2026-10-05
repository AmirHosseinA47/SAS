"""isTrue round Part 3: RECORD-ONLY reach counter at every F-2 site, around the measurement round's own chain.

usage: _ist3_reach.py <outputs/_ut_probe.py arguments, unchanged>      (e.g. --crn --hazard --instrument -- --repo ...)

Runs outputs/_ut_probe.py (runpy, run_name "__main__", same directory as this file) with exactly the arguments given,
after installing pass-through hooks. Each hook calls the original once with the original arguments and returns its
result unchanged; it draws from no RNG and writes into no simulation object. The probe chain's JSON (--out) is written
by the chain as without the wrapper; this file writes <out>.reach.json beside it. An observer exception is recorded,
never raised. The same hooks are installed in every arm (on a checkout without F-2 the plain_scalar hook is absent).

A value is recorded as its category: None | bool | int | float | str | numpy.<type name> | other:<type name>.
  truthy[<module>]     every value reaching a planner's _is_truthy (fail_safe / global_mission / local_uav_path / rescue)
  maintain             every value of the three marker keys read by planner_selection._is_maintain_option
  safe_float           every value reaching safe_float (each module binding: utility_evaluation, planner_selection,
                       rescue_planner)
  params / context     numpy-typed values in the option.parameters / context reaching UtilityEvaluation.evaluate_option,
                       per key (the ptruth / ptruth_s / ptruth_p closures read option.parameters and cannot be hooked)
  plain_scalar         (F-2 heads only) every numpy input, by category and by calling function, and how many were
                       converted (the returned object differs from the argument)
A numpy bool / integer / float32 in arm B (f686e932) at truthy / maintain / safe_float / params is the latent F-2
defect actually reached in that configuration.
"""
from __future__ import annotations

import json
import os
import runpy
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def cat(v) -> str:
    if v is None:
        return "None"
    t = type(v)
    if t in (bool, int, float, str):
        return t.__name__
    if t.__module__ == "numpy":
        return "numpy." + t.__name__
    return "other:" + t.__name__


def main() -> int:
    args = sys.argv[1:]
    if "--" not in args:
        print("usage: _ist3_reach.py <_ut_probe.py args>", file=sys.stderr)
        return 2
    after = args[args.index("--") + 1:]
    if "--repo" not in after or "--out" not in after:
        print("IST3 REACH REFUSED: --repo and --out are required after --", file=sys.stderr)
        return 2
    repo = os.path.abspath(after[after.index("--repo") + 1])
    out = after[after.index("--out") + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    rec = {"truthy": defaultdict(Counter), "maintain": Counter(), "safe_float": Counter(),
           "params": defaultdict(Counter), "context": defaultdict(Counter), "plain_scalar": Counter(),
           "plain_scalar_callers": Counter(), "plain_scalar_converted": Counter(), "calls": Counter(), "errors": []}

    def err(where, exc):
        if len(rec["errors"]) < 20:
            rec["errors"].append("%s: %r" % (where, exc))

    # the chain's own import order (_ut_probe: agents, common_fixed_variables, wildfire_model); wildfire_model loads
    # the planning modules, so the wrapper changes no import order
    import agents  # noqa: F401
    import common_fixed_variables  # noqa: F401
    import wildfire_model  # noqa: F401
    from src_extension.planning import (fail_safe_planner, global_mission_planner, local_uav_path_planner,
                                        planner_selection, rescue_planner, utility_evaluation as ue)
    mods = (fail_safe_planner, global_mission_planner, local_uav_path_planner, planner_selection, rescue_planner, ue)
    for m in mods:
        p = os.path.abspath(m.__file__)
        if not p.lower().startswith(repo.lower() + os.sep.lower()):
            print("IST3 REACH IMPORT MISMATCH: %s from %s" % (m.__name__, p), file=sys.stderr)
            return 3

    for mod in (fail_safe_planner, global_mission_planner, local_uav_path_planner, rescue_planner):
        site = mod.__name__.rsplit(".", 1)[-1]
        orig = mod._is_truthy

        def make(orig=orig, site=site):
            def _is_truthy(value):
                try:
                    rec["truthy"][site][cat(value)] += 1
                except Exception as exc:
                    err("truthy", exc)
                return orig(value)
            return _is_truthy

        mod._is_truthy = make()

    o_im = planner_selection._is_maintain_option

    def _is_maintain_option(option, *a, **kw):
        try:
            rec["calls"]["_is_maintain_option"] += 1
            params = getattr(option, "parameters", None)
            if isinstance(params, dict):
                for key in planner_selection._MAINTAIN_TYPE_MARKERS:
                    if key in params:
                        rec["maintain"][cat(params[key])] += 1
        except Exception as exc:
            err("maintain", exc)
        return o_im(option, *a, **kw)

    planner_selection._is_maintain_option = _is_maintain_option

    o_sf = ue.safe_float

    def safe_float(value, default=0.0):
        try:
            rec["safe_float"][cat(value)] += 1
        except Exception as exc:
            err("safe_float", exc)
        return o_sf(value, default)

    for m in mods:
        if getattr(m, "safe_float", None) is o_sf:
            m.safe_float = safe_float

    o_ps = getattr(ue, "plain_scalar", None)
    if o_ps is not None:
        def plain_scalar(value):
            r = o_ps(value)
            try:
                rec["calls"]["plain_scalar"] += 1
                if type(value).__module__ == "numpy":
                    c = cat(value)
                    rec["plain_scalar"][c] += 1
                    rec["plain_scalar_callers"][sys._getframe(1).f_code.co_name] += 1
                    if r is not value:
                        rec["plain_scalar_converted"][c] += 1
            except Exception as exc:
                err("plain_scalar", exc)
            return r

        for m in mods:
            if getattr(m, "plain_scalar", None) is o_ps:
                m.plain_scalar = plain_scalar

    o_eo = ue.UtilityEvaluation.evaluate_option

    def evaluate_option(self, option, *a, **kw):
        try:
            rec["calls"]["evaluate_option"] += 1
            params = getattr(option, "parameters", None)
            if isinstance(params, dict):
                for k, v in params.items():
                    if type(v).__module__ == "numpy":
                        rec["params"][str(k)][cat(v)] += 1
            ctx = kw.get("context", a[1] if len(a) > 1 else None)
            if isinstance(ctx, dict):
                for k, v in ctx.items():
                    if type(v).__module__ == "numpy":
                        rec["context"][str(k)][cat(v)] += 1
        except Exception as exc:
            err("evaluate_option", exc)
        return o_eo(self, option, *a, **kw)

    ue.UtilityEvaluation.evaluate_option = evaluate_option

    probe = os.path.join(HERE, "_ut_probe.py")
    sys.argv = [probe] + args
    code = None
    try:
        runpy.run_path(probe, run_name="__main__")
    except SystemExit as exc:
        code = exc.code
    finally:
        doc = {"probe": "ist3 reach v1", "repo": repo, "f2_present": o_ps is not None, "chain_exit": code,
               "truthy": {k: dict(v) for k, v in rec["truthy"].items()}, "maintain": dict(rec["maintain"]),
               "safe_float": dict(rec["safe_float"]),
               "params": {k: dict(v) for k, v in rec["params"].items()},
               "context": {k: dict(v) for k, v in rec["context"].items()},
               "plain_scalar": dict(rec["plain_scalar"]), "plain_scalar_callers": dict(rec["plain_scalar_callers"]),
               "plain_scalar_converted": dict(rec["plain_scalar_converted"]), "calls": dict(rec["calls"]),
               "errors": rec["errors"]}
        tmp = out + ".reach.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, indent=1)
        os.replace(tmp, out + ".reach.json")
    return int(code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
