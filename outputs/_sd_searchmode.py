"""sysdebug: why does SEARCH_MODE_REQUIRED fire on ~78% of steps?

Pass-through wrapper on GlobalAnalyzer.analyze (read-only): at every call records the inputs of
the SEARCH_MODE_REQUIRED condition (global_analyzer.py ~553-566) - the snapshot's
fire_state_summary.estimated_burning_cells length, confirmed_fire_cells, the merged probability
map's count of cells >= fire_probability_threshold, the fire runtime model's own
belief.estimated_burning_cells size, the number of truly burning Fire agents - and whether the
returned trigger list contains SEARCH_MODE_REQUIRED. Shipped config, scenario D, evaluate_scenarios
seeding. usage: _sd_searchmode.py <wind> <seed> <steps>
"""
import argparse
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
import src_extension.analysis.global_analyzer as ga  # noqa: E402
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402

ROWS = []
CUR = {"model": None}
orig = ga.GlobalAnalyzer.analyze


def analyze(self, sop, snap_dict, runtime_models, t):
    res = orig(self, sop, snap_dict, runtime_models, t)
    st = self._unwrap_summary_layer((snap_dict or {}).get("fire_state_summary"))
    fb = self._unwrap_summary_layer((snap_dict or {}).get("fire_belief_summary"))
    burning = st.get("estimated_burning_cells")
    prob, _, _ = self._merged_fire_maps(runtime_models, snap_dict or {})
    hi = sum(1 for p in prob.values() if p >= self.fire_probability_threshold)
    fr = runtime_models.get("fire_runtime_model")
    est_now = len(getattr(getattr(fr, "belief", None), "estimated_burning_cells", ()) or ())
    m = CUR["model"]
    truth = sum(1 for a in m.schedule.agents if type(a) is am.Fire and a.burning) if m is not None else -1
    names = [str(getattr(x, "trigger_type", "")) for x in (getattr(res, "trigger_list", ()) or ())]
    ROWS.append((int(t), None if burning is None else len(burning), fb.get("confirmed_fire_cells"),
                 hi, len(prob), est_now, truth, "SEARCH_MODE_REQUIRED" in names,
                 sorted((snap_dict or {}).keys())[:0]))
    return res


ga.GlobalAnalyzer.analyze = analyze


def main():
    wind, seed, steps = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    ns = argparse.Namespace(scenario="D", wind=wind, uavs=None, victims=None, firefighters=None,
                            fire_trackers=None, victim_searchers=None, batch_size=300, fire_spread=0.75,
                            ff_absence_min=None, ff_absence_max=None)
    params = es._scenario_params(ns)
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(io.StringIO()):
        model = wf.WildFireModel()
        CUR["model"] = model
        model.debug_log = False
        for _ in range(steps):
            model.step()
    print("t | snapshot estimated_burning len | confirmed_fire_cells | merged cells>=thr | merged map size |"
          " fire model estimated now | truly burning | SEARCH_MODE_REQUIRED")
    for r in ROWS:
        print(r[:8])
    fired = sum(1 for r in ROWS if r[7])
    print("SUMMARY calls=%d fired=%d; fired with snapshot-empty & merged>=thr: %d; fired while fire model's own estimated set non-empty: %d; fired while truly burning>0: %d" % (
        len(ROWS), fired, sum(1 for r in ROWS if r[7] and r[1] == 0 and r[3] > 0),
        sum(1 for r in ROWS if r[7] and r[5] > 0), sum(1 for r in ROWS if r[7] and r[6] > 0)))


if __name__ == "__main__":
    main()
