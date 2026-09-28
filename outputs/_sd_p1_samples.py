"""sysdebug: how many recent_x/y_positions samples does a searcher get per model step?

Counts calls of local_adaptation_generator._record_victim_searcher_x_band per step and
per caller (pass-through wrapper, read-only), in a shipped-config run built exactly like
evaluate_scenarios._run_seed (scenario D, legacy roles unless --half).

usage: _sd_p1_samples.py <wind> <seed> <steps> [--half]
"""
import collections
import contextlib
import io
import os
import random
import sys

sys.path.insert(0, r"E:\Projects\SAS")
os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am  # noqa: E402
import common_fixed_variables as cfv  # noqa: E402
import wildfire_model as wf  # noqa: E402
import evaluate_scenarios as es  # noqa: E402
import argparse  # noqa: E402
import src_extension.adaptation.local_adaptation_generator as lag  # noqa: E402

CALLS = collections.Counter()
CUR = {"step": 0}
_orig = lag._record_victim_searcher_x_band


def _wrap(wind_state, agent_x, agent_y=None):
    caller = sys._getframe(1)
    CALLS[(CUR["step"], caller.f_code.co_name, caller.f_lineno)] += 1
    return _orig(wind_state, agent_x, agent_y)


lag._record_victim_searcher_x_band = _wrap


def main():
    wind, seed, steps = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    half = "--half" in sys.argv
    ns = argparse.Namespace(scenario="D", wind=wind, uavs=None, victims=None, firefighters=None,
                            fire_trackers=2 if half else None, victim_searchers=2 if half else None,
                            batch_size=300, fire_spread=0.75, ff_absence_min=None, ff_absence_max=None)
    params = es._scenario_params(ns)
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    lag.apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(io.StringIO()):
        model = wf.WildFireModel()
        model.debug_log = False
        for s in range(steps):
            CUR["step"] = s + 1
            model.step()
    per_step = collections.Counter()
    per_site = collections.Counter()
    for (st, fn, ln), n in CALLS.items():
        per_step[st] += n
        per_site[(fn, ln)] += n
    searchers = lag.resolve_victim_searcher_uav_ids(model)
    print("searchers", searchers)
    print("samples per step (all searchers):", [per_step[s] for s in range(1, steps + 1)])
    print("per call site:", dict(per_site))
    for uid in searchers:
        st = (getattr(model, "_wind_search_target_state", {}) or {}).get(uid, {})
        print(uid, "len recent_y", len(st.get("recent_y_positions") or []), "commit", st.get("coverage_y_commit"),
              "lane_axis", st.get("lane_axis"), "tail_y", (st.get("recent_y_positions") or [])[-15:])


if __name__ == "__main__":
    main()
