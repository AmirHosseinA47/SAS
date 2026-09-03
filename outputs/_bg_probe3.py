"""belief_gap_regions round, probe 3: HOW WIDE IS THE CLASS?

Probe 1 recorded the live key sets of ``global_analysis_result`` and
``runtime_models`` ONCE per run (first call only). That is enough to explain the
two belief-gap lookups but not enough to claim the failure is file-wide - keys
could in principle appear on later steps.

This probe records, PER CALL to GlobalAdaptationSpaceGenerator.generate, whether
each name that any read_value() lookup in global_adaptation_generator.py asks for
is present on global_analysis_result and on runtime_models. Pure observer: it
wraps generate(), records, and returns the original result untouched.

Names are transcribed from the read_value call sites:
  l.112-125  _generate_role_assignment_options
  l.239-289  _generate_task_allocation_options
  l.437-481  _generate_coverage_strategy_options   <- the subject
  l.583-613  _generate_resource_reallocation_options

usage:
  _bg_probe3.py --wind east --roles half --seed 101 --steps 60 --out P.json
"""
from __future__ import annotations
import argparse, contextlib, io as _io, json, os, random, sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

# name -> which generator asks for it (for the report)
NAMES = {
    # _generate_role_assignment_options (l.112-125)
    "current_role": "role_assignment",
    "role_stability_timer": "role_assignment",
    "role_switch_count": "role_assignment",
    "battery_state": "role_assignment/resource_realloc",
    "battery": "role_assignment/resource_realloc",
    "battery_level": "role_assignment",
    "resources": "role_assignment",
    # _generate_task_allocation_options (l.239-279)
    "negative_observation_maps": "task_allocation",
    "stale_information": "task_allocation",
    "last_known_fire_regions": "task_allocation",
    "communication_support_zones": "task_allocation",
    # _generate_coverage_strategy_options (l.437-455)  <- SUBJECT
    "fire_probability_map": "coverage_strategy/task_allocation",
    "fire_confidence_map": "coverage_strategy  <-- belief_gap_regions",
    "uncertainty_map": "coverage_strategy/task_allocation",
    "victim_confidence": "coverage_strategy/task_allocation",
    # _generate_resource_reallocation_options (l.583-611)
    "predicted_remaining_useful_time": "resource_realloc",
    "communication_reliability": "resource_realloc",
    "uncertainty_regions": "resource_realloc",
    "critical_regions": "resource_realloc",
    "region_value_map": "resource_realloc",
    # control group: names that DO exist live
    "target_entity": "CONTROL (expected present on gar)",
    "mission_goals": "CONTROL (expected present on rm)",
    "mission_goal_model": "CONTROL (expected present on rm)",
}

REC = {"generate_calls": 0,
       "gar_present": {n: 0 for n in NAMES},
       "rm_present": {n: 0 for n in NAMES},
       "gar_keys_union": set(),
       "rm_keys_union": set(),
       "gar_is_dict": 0, "rm_is_dict": 0}


def install():
    from src_extension.adaptation.global_adaptation_generator import (
        GlobalAdaptationSpaceGenerator as G,
    )
    orig = G.generate

    def generate(self, gar, rm, ts):
        REC["generate_calls"] += 1
        if isinstance(gar, dict):
            REC["gar_is_dict"] += 1
            REC["gar_keys_union"] |= set(map(str, gar.keys()))
        if isinstance(rm, dict):
            REC["rm_is_dict"] += 1
            REC["rm_keys_union"] |= set(map(str, rm.keys()))
        for n in NAMES:
            # exactly what read_value() tests: dict -> .get(name), else getattr
            if (n in gar) if isinstance(gar, dict) else hasattr(gar, n):
                REC["gar_present"][n] += 1
            if (n in rm) if isinstance(rm, dict) else hasattr(rm, n):
                REC["rm_present"][n] += 1
        return orig(self, gar, rm, ts)

    G.generate = generate


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

    n = REC["generate_calls"]
    print("generate() calls: %d   gar_is_dict=%d  rm_is_dict=%d" % (n, REC["gar_is_dict"], REC["rm_is_dict"]))
    print()
    print("%-34s %-38s %8s %8s" % ("LOOKUP NAME", "asked for by", "on gar", "on rm"))
    print("-" * 92)
    for name, who in NAMES.items():
        g, r = REC["gar_present"][name], REC["rm_present"][name]
        flag = "" if (g or r) else "   <-- NEVER PRESENT"
        print("%-34s %-38s %4d/%-3d %4d/%-3d%s" % (name, who, g, n, r, n, flag))
    print()
    print("gar key union (%d):" % len(REC["gar_keys_union"]), sorted(REC["gar_keys_union"]))
    print("rm  key union (%d):" % len(REC["rm_keys_union"]), sorted(REC["rm_keys_union"]))

    if a.out:
        doc = {k: (sorted(v) if isinstance(v, set) else v) for k, v in REC.items()}
        doc["names"] = NAMES
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
