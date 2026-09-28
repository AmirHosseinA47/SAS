"""sysdebug round: two more counterfactual arms, layered on outputs/_sd_cf.py (unchanged).

DIAGNOSIS ONLY - patches live in this process; no source file is touched.

usage: _sd_cf2.py (--cf2-noartifact | --cf2-allowfire | --cf2-undetected-off) [_sd_cf.py flags] -- <probe args>

  --cf2-noartifact  SafetyChecker.extract_fail_safe_reasons drops the three reasons that
                    come from the artifact alarms named in planner_part1 11A(c):
                    collision_risk, extreme_drift, critical_communication. Every other
                    reason, and everything downstream (classify_mode, mode manager, the
                    fail-safe planner, dispatch), is untouched. Question answered: do the
                    artifact alarms change decisions/outcomes through the fail-safe mode?
  --cf2-allowfire   ConstraintFilter._mission_goal_reasons drops the reason
                    "mission: fire entry disallowed" for options whose option_id starts with
                    local_path_move_toward_fire (the tracker flank/standoff family, removed
                    on every step at shipped config because path_constraint_flags marks every
                    move_toward_fire action as entering the fire zone). Question answered:
                    would that family be selected, and would it move anything?
  --cf2-undetected-off  wildfire_model.unreachable_escape_victims (the name the model calls)
                    is wrapped to pass undetected_threshold=10**9: the 210-step never_detected
                    write-off never fires (the 30-step geographic one is untouched). Question
                    answered: at 360 steps, does the write-off latch cost detections/rescues?
Counters: reasons dropped / options let through, added to the JSON as key "cf2".
"""
from __future__ import annotations

import collections
import json
import os
import runpy
import sys

ART = {"collision_risk", "extreme_drift", "critical_communication"}


def main() -> int:
    argv = sys.argv[1:]
    noart = "--cf2-noartifact" in argv
    allowfire = "--cf2-allowfire" in argv
    undet_off = "--cf2-undetected-off" in argv
    rest = [a for a in argv if a not in ("--cf2-noartifact", "--cf2-allowfire", "--cf2-undetected-off")]
    out_path = rest[rest.index("--out") + 1]
    repo = r"E:\Projects\SAS"
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import src_extension.execution.safety_checker as sc  # noqa: E402
    import src_extension.adaptation.constraint_filter as cfm  # noqa: E402

    C = collections.Counter()
    if noart:
        orig = sc.SafetyChecker.extract_fail_safe_reasons

        def extract(self, *a, **k):
            reasons = orig(self, *a, **k)
            kept = tuple(r for r in reasons if self._canonical_reason(r) not in ART)
            C["reasons_dropped"] += len(reasons) - len(kept)
            C["calls"] += 1
            return kept

        sc.SafetyChecker.extract_fail_safe_reasons = extract
    if allowfire:
        origm = cfm.ConstraintFilter._mission_goal_reasons

        def mission(self, option, mission_constraints):
            reasons = origm(self, option, mission_constraints)
            if str(getattr(option, "option_id", "")).startswith("local_path_move_toward_fire"):
                new = [r for r in reasons if r != "mission: fire entry disallowed"]
                if len(new) != len(reasons):
                    C["fire_options_let_through"] += 1
                return new
            return reasons

        cfm.ConstraintFilter._mission_goal_reasons = mission

    if undet_off:
        import wildfire_model as wfm  # noqa: E402
        origu = wfm.unreachable_escape_victims

        def unesc(flags, geo=None, und=None, **k):
            k["undetected_threshold"] = 10 ** 9
            C["undetected_off_calls"] += 1
            return origu(flags, geo, und, **k)

        wfm.unreachable_escape_victims = unesc

    cf = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sd_cf.py"),
                        run_name="sd_cf_module")
    sys.argv = [sys.argv[0]] + rest
    rc = cf["main"]()
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        d["cf2"] = {"noartifact": noart, "allowfire": allowfire, "undetected_off": undet_off, "counters": dict(C)}
        tmp = out_path + ".cf2tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("SD_CF2 RECORD FAILED: %r" % (exc,), file=sys.stderr)
        return 5
    print("SD_CF2_DONE %s" % dict(C))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
