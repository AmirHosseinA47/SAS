"""belief_gap_regions round, probe 4: IS THE PARALLEL MECHANISM ACTUALLY LIVE?

The redundancy question for this round is whether the belief-gap CONCEPT is
already covered by a working mechanism elsewhere. The candidate is:

  GlobalMonitor._belief_gap_indicators()          global_monitor.py:252
      -> GlobalMonitorSnapshot.belief_gap_indicators   monitoring_interfaces.py:53
      -> GlobalAnalyzer._belief_gap_critical()     global_analyzer.py:618

_belief_gap_indicators() returns a DICT with exactly four keys:
    {"threshold_probability", "threshold_confidence", "cells", "count"}
_belief_gap_critical() tests:
    if isinstance(belief_gap, dict) and len(belief_gap) >= 3: return True
len() of that dict is 4 regardless of how many gap cells were found, so the
test appears to be counting KEYS, not GAPS, and should be constant-True.

This probe measures that directly rather than inferring it. Pure observer:
wraps _belief_gap_indicators and _belief_gap_critical, records, returns the
original results untouched.

Records per call:
  - the real gap count from the indicator dict ("count") and len(cells)
  - the container type and len() that _belief_gap_critical actually branches on
  - which of the four return branches fired, and the return value
  - whether the return value is ever False

usage:
  _bg_probe4.py --wind east --roles half --seed 101 --steps 60 --out P.json
"""
from __future__ import annotations
import argparse, contextlib, io as _io, json, os, random, sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

REC = {
    "ind_calls": 0,
    "ind_count_zero": 0,          # steps where the monitor found NO belief gaps
    "ind_count_nonzero": 0,
    "ind_count_max": 0,
    "ind_count_series": [],
    "ind_len_dict": {},           # len(returned dict) histogram -> should be {"4": n}

    "crit_calls": 0,
    "crit_input_type": {},
    "crit_input_len": {},         # len() of the arg _belief_gap_critical branches on
    "crit_true": 0,
    "crit_false": 0,
    "crit_branch": {},            # which branch produced True
    # the decisive cross-tab: monitor found 0 gaps, yet critical returned True?
    "crit_true_while_zero_gaps": 0,
}


def _bump(d, k):
    d[k] = d.get(k, 0) + 1


def install():
    from src_extension.monitoring.global_monitor import GlobalMonitor as M
    from src_extension.analysis.global_analyzer import GlobalAnalyzer as A

    orig_ind = M._belief_gap_indicators

    def ind(self):
        out = orig_ind(self)
        REC["ind_calls"] += 1
        if isinstance(out, dict):
            _bump(REC["ind_len_dict"], str(len(out)))
            c = int(out.get("count", -1))
            REC["ind_count_series"].append(c)
            if c == 0:
                REC["ind_count_zero"] += 1
            elif c > 0:
                REC["ind_count_nonzero"] += 1
            REC["ind_count_max"] = max(REC["ind_count_max"], c)
        return out

    M._belief_gap_indicators = ind

    # _belief_gap_critical is a @staticmethod; accessed off the class it is
    # already the plain underlying function, so no __func__ unwrapping needed.
    orig_crit = A._belief_gap_critical

    def crit(belief_gap, suff_score, total_gain):
        REC["crit_calls"] += 1
        _bump(REC["crit_input_type"], type(belief_gap).__name__)
        try:
            n = len(belief_gap)
        except TypeError:
            n = -1
        _bump(REC["crit_input_len"], str(n))

        # which branch fires, evaluated in source order (l.623-631)
        if isinstance(belief_gap, list) and len(belief_gap) >= 3:
            branch = "list_len_ge_3"
        elif isinstance(belief_gap, dict) and len(belief_gap) >= 3:
            branch = "DICT_LEN_GE_3  (counts keys, not gaps)"
        elif suff_score is not None and suff_score < 0.15:
            branch = "suff_score_lt_0.15"
        elif total_gain is not None and total_gain < 0.01:
            branch = "total_gain_lt_0.01"
        else:
            branch = "<none - returns False>"
        _bump(REC["crit_branch"], branch)

        out = orig_crit(belief_gap, suff_score, total_gain)
        if out:
            REC["crit_true"] += 1
            gaps = belief_gap.get("count") if isinstance(belief_gap, dict) else None
            if gaps == 0:
                REC["crit_true_while_zero_gaps"] += 1
        else:
            REC["crit_false"] += 1
        return out

    A._belief_gap_critical = staticmethod(crit)


def params(wind, ft, vs):
    """Verbatim from outputs/_sc_control.py:35-39 (scenario D)."""
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


def run(seed, p, steps):
    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    from wildfire_model import WildFireModel

    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **p)
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            model.step()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", choices=["half", "default"], default="half")
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--out")
    a = ap.parse_args()

    ft, vs = (2, 2) if a.roles == "half" else (None, None)
    install()
    run(a.seed, params(a.wind, ft, vs), a.steps)

    print("_belief_gap_indicators calls : %d" % REC["ind_calls"])
    print("   len(returned dict)        : %s" % json.dumps(REC["ind_len_dict"]))
    print("   real gap count == 0       : %d" % REC["ind_count_zero"])
    print("   real gap count  > 0       : %d  (max %d)" % (REC["ind_count_nonzero"], REC["ind_count_max"]))
    print("   count series (first 30)   : %s" % REC["ind_count_series"][:30])
    print()
    print("_belief_gap_critical calls    : %d" % REC["crit_calls"])
    print("   arg type                  : %s" % json.dumps(REC["crit_input_type"]))
    print("   len(arg)                  : %s" % json.dumps(REC["crit_input_len"]))
    print("   returned True / False     : %d / %d" % (REC["crit_true"], REC["crit_false"]))
    print("   branch that fired         : %s" % json.dumps(REC["crit_branch"], indent=1))
    print("   True WHILE zero real gaps : %d   <-- degenerate if > 0" % REC["crit_true_while_zero_gaps"])

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(REC, fh, indent=1, default=str)
