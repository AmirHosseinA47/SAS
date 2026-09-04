"""COMPARATIVE CONTROL for the global-planner scoping round.

The global scorer reads nine parameter names (fire_contribution, ... ,
switching_cost) that NO generator in the live tree writes, so every non-baseline
global option scores 0.0. The obvious follow-up question is whether that is a
house-wide architectural vacuum or a gap in one lane.

This probe answers it by measuring the LOCAL lane the same way: hook
UtilityEvaluation._evaluate_local_path_option and record the real score
distribution of the options the LOCAL generator produces, plus which of the
local scorer's own key names are present in their parameters.

If local options score non-zero from real generator output, the producer/consumer
utility contract is honoured in that lane and the global lane is the outlier -
which is a materially smaller problem than "no lane has a scoring contract".

usage: _gp_local.py --wind east --roles half --seed 101 --steps 40 --out P.json
"""
from __future__ import annotations
import argparse, contextlib, io as _io, json, os, random, sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

# the local scorer's own vocabulary, utility_evaluation.py:653-657 (pfloat sites)
LOCAL_KEYS = ["expected_info_gain", "information_gain", "belief_gain",
              "recovery_value", "information_recovery_score", "task_support",
              "overlap_penalty", "collision_risk", "risk_estimate",
              "smoke_penalty", "battery_cost", "cost_estimate",
              "drift_penalty", "stability_bonus", "path_stability_score"]
# the global scorer's vocabulary, utility_evaluation.py:812-820
GLOBAL_KEYS = ["fire_contribution", "victim_contribution", "communication_contribution",
               "uncertainty_reduction", "information_recovery", "collision_risk",
               "battery_cost", "drift_risk", "switching_cost"]

REC = {"local_calls": 0, "local_nonzero": 0, "local_score_buckets": {},
       "local_key_present": {}, "local_by_type": {}, "local_sample": [],
       "global_calls": 0, "global_nonzero": 0, "global_key_present": {},
       "local_selected_nonzero": 0, "local_plan_calls": 0}


def _bump(d, k):
    d[k] = d.get(k, 0) + 1


def bucket(x):
    x = float(x)
    if x == 0.0:
        return "0.0"
    if x < 0:
        return "<0"
    for hi in (0.05, 0.1, 0.25, 0.5, 1.0, 2.0):
        if x < hi:
            return "<%s" % hi
    return ">=2.0"


def install():
    from src_extension.planning.utility_evaluation import UtilityEvaluation as UE

    orig_local = UE._evaluate_local_path_option
    orig_global = UE._evaluate_global_mission_option

    def loc(self, option, rm, ctx, mode):
        r = orig_local(self, option, rm, ctx, mode)
        params = getattr(option, "parameters", None) or {}
        REC["local_calls"] += 1
        if abs(float(r.total_utility)) > 1e-12:
            REC["local_nonzero"] += 1
        _bump(REC["local_score_buckets"], bucket(r.total_utility))
        for k in LOCAL_KEYS:
            if isinstance(params, dict) and k in params:
                _bump(REC["local_key_present"], k)
        ot = str(getattr(option, "option_type", ""))
        e = REC["local_by_type"].setdefault(ot, {"n": 0, "nonzero": 0})
        e["n"] += 1
        if abs(float(r.total_utility)) > 1e-12:
            e["nonzero"] += 1
        if len(REC["local_sample"]) < 6 and abs(float(r.total_utility)) > 1e-12:
            REC["local_sample"].append({
                "option_id": str(getattr(option, "option_id", "")),
                "option_type": ot,
                "total_utility": round(float(r.total_utility), 6),
                "terms": [{"n": t.name, "v": round(float(t.value), 5),
                           "c": round(float(t.contribution), 5)}
                          for t in r.utility_terms if abs(float(t.value)) > 1e-12],
                "params_present": sorted(k for k in LOCAL_KEYS
                                         if isinstance(params, dict) and k in params),
            })
        return r

    def glo(self, option, rm, ctx, mode):
        r = orig_global(self, option, rm, ctx, mode)
        params = getattr(option, "parameters", None) or {}
        REC["global_calls"] += 1
        if abs(float(r.total_utility)) > 1e-12:
            REC["global_nonzero"] += 1
        for k in GLOBAL_KEYS:
            if isinstance(params, dict) and k in params:
                _bump(REC["global_key_present"], k)
        return r

    UE._evaluate_local_path_option = loc
    UE._evaluate_global_mission_option = glo


def params(wind, ft, vs):
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", choices=["half", "default"], default="half")
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--out")
    a = ap.parse_args()

    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    from wildfire_model import WildFireModel

    install()
    ft, vs = (2, 2) if a.roles == "half" else (None, None)
    p = params(a.wind, ft, vs)
    rng = random.Random(a.seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **p)
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(a.steps):
            model.step()

    print("LOCAL  calls=%d nonzero=%d (%.1f%%)  buckets=%s"
          % (REC["local_calls"], REC["local_nonzero"],
             100.0 * REC["local_nonzero"] / max(1, REC["local_calls"]),
             json.dumps(REC["local_score_buckets"])), flush=True)
    print("LOCAL  scorer-key presence: %s" % json.dumps(REC["local_key_present"]), flush=True)
    print("GLOBAL calls=%d nonzero=%d  scorer-key presence: %s"
          % (REC["global_calls"], REC["global_nonzero"],
             json.dumps(REC["global_key_present"])), flush=True)
    print("LOCAL  by option_type: %s" % json.dumps(REC["local_by_type"]), flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(REC, fh, indent=1, default=str)
