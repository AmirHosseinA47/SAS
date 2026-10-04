"""isTrue round Part 1: direct demonstration of each identity-test shape on Python vs numpy inputs.

usage: _ist_demo.py --repo <checkout>

Calls the helpers as they are (nothing patched) with a Python value and its numpy counterpart and prints both
results. Part A uses plain objects (no model). Part B builds one real WildFireModel (team pinned 3/5/3, no step):
it sets the burning flag of Fire cells inside UAV 0's observation box to numpy True and to Python True and prints
sum(surrounding_states()) for each - the model's MR1 input. It then restores every flag it touched. No RNG draw
outside the model's own constructor.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from types import SimpleNamespace


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.stdout.reconfigure(newline="\n")
    import numpy as np
    from src_extension.planning import (fail_safe_planner, global_mission_planner, local_uav_path_planner,
                                        planner_selection, rescue_planner, utility_evaluation as ue)

    print("numpy", np.__version__, "| type(np.bool_(True)).__name__ =", type(np.bool_(True)).__name__,
          "| isinstance(np.True_, (bool, int, float)) =", isinstance(np.True_, (bool, int, float)),
          "| isinstance(np.int64(1), int) =", isinstance(np.int64(1), int),
          "| isinstance(np.float64(1), float) =", isinstance(np.float64(1), float),
          "| isinstance(np.float32(1), float) =", isinstance(np.float32(1), float))
    print("np.float64(0.3) < np.float64(0.5) ->", type(np.float64(0.3) < np.float64(0.5)).__module__,
          type(np.float64(0.3) < np.float64(0.5)).__name__, "| is True:", (np.float64(0.3) < np.float64(0.5)) is True)
    print("0.2 < 0.3 (Python floats) is True:", (0.2 < 0.3) is True,
          "| (x in (a, b)) always returns a Python bool:", type(np.True_ in (np.True_,)).__name__)

    inputs = [("True", True), ("np.True_", np.True_), ("1", 1), ("np.int64(1)", np.int64(1)),
              ("np.float64(1.0)", np.float64(1.0)), ("np.float32(1.0)", np.float32(1.0)), ("'yes'", "yes"),
              ("False", False), ("np.False_", np.False_)]

    print("\nA1. the four planner _is_truthy helpers (fail_safe :486, global_mission :303, local_path :641, rescue :412)")
    for label, v in inputs:
        res = [m._is_truthy(v) for m in (fail_safe_planner, global_mission_planner, local_uav_path_planner, rescue_planner)]
        print("  %-16s -> %s   bool(v)=%s" % (label, res, bool(v)))

    print("\nA2. planner_selection._is_maintain_option(parameters={'do_nothing': v})  (:70)")
    for label, v in inputs:
        opt = SimpleNamespace(option_type="x", parameters={"do_nothing": v})
        print("  %-16s -> %s" % (label, planner_selection._is_maintain_option(opt)))

    U = ue.UtilityEvaluation()
    print("\nA3. utility_evaluation ptruth_s via _compute_stability_bonus(parameters={'do_nothing': v})  (:338)")
    for label, v in inputs:
        opt = SimpleNamespace(option_type="x", parameters={"do_nothing": v})
        print("  %-16s -> bonus %.3f" % (label, U._compute_stability_bonus(opt)))

    print("\nA4. utility_evaluation _indicator via _compute_switching_cost(parameters={'role_change': v})  (:307/309)")
    for label, v in inputs:
        opt = SimpleNamespace(option_type="x", parameters={"role_change": v})
        print("  %-16s -> cost %.3f" % (label, U._compute_switching_cost(opt)))

    print("\nA5. utility_evaluation.safe_float(v, default=-9.0)  (:1595, the isinstance sibling)")
    for label, v in inputs:
        print("  %-16s -> %s" % (label, ue.safe_float(v, -9.0)))

    print("\nA6. utility_evaluation._check_utility_feasibility(parameters={'hard_collision_violation': v})  (:274)")
    for label, v in inputs:
        opt = SimpleNamespace(option_type="x", parameters={"hard_collision_violation": v})
        print("  %-16s -> %s" % (label, U._check_utility_feasibility(opt)))

    print("\nA7. constraint_filter._feasibility_reasons(parameters={'infeasible': v})  (:200)")
    from src_extension.adaptation.constraint_filter import ConstraintFilter
    cf = ConstraintFilter()
    for label, v in inputs:
        opt = SimpleNamespace(option_type="x", target_entity="", parameters={"infeasible": v})
        print("  %-16s -> %s" % (label, cf._feasibility_reasons(opt, None, None)))

    # ---- Part B: the MR1 input on a real model
    import agents
    import common_fixed_variables as cfv
    import wildfire_model as wf
    for mod in (cfv, wf):
        for k, val in (("NUM_AGENTS", 3), ("NUM_VICTIMS", 5), ("NUM_FIREFIGHTERS", 3)):
            setattr(mod, k, val)
    with contextlib.redirect_stdout(io.StringIO()):
        model = wf.WildFireModel()
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    cells = model.grid.get_neighborhood(uav.pos, moore=uav.moore, include_center=True,
                                        radius=agents.UAV_OBSERVATION_RADIUS)
    fires = [f for c in cells for f in model.grid.get_cell_list_contents([c]) if type(f) is agents.Fire][:4]
    saved = [f.burning for f in fires]
    print("\nB. real WildFireModel, UAV %s at %s, %d Fire cells in its box; 4 of them set burning:"
          % (uav.unique_id, uav.pos, sum(1 for c in cells for f in model.grid.get_cell_list_contents([c])
                                         if type(f) is agents.Fire)))
    try:
        base = sum(uav.surrounding_states())
        for label, val in (("numpy True (what Fire.advance writes)", np.True_), ("Python True", True)):
            for f in fires:
                f.burning = val
            print("  %-40s sum(surrounding_states()) = %d   (baseline %d)" % (label, sum(uav.surrounding_states()), base))
    finally:
        for f, b in zip(fires, saved):
            f.burning = b
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
