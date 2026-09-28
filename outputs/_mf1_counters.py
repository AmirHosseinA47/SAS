"""fix1 (mf1) Part 3, check P3-5: count the searcher-counter guard, per searcher per step.

usage: _mf1_counters.py <_ffr_harness.py args ...>   (the harness runs in THIS process)

Wraps local_adaptation_generator._first_call_this_step - the single gate every fix1
item-6 counter family passes through (samples, streaks, dwell, post-rescue countdown) -
and records, per (model step, searcher uid, family), [calls, advances]. The wrapper
returns the original's result unchanged, draws no RNG and writes no model state, so the
run is the harness run. Internal calls resolve the module global at call time, so every
caller is covered - including uav_executor's by-name import of _sync_wind_search_streaks,
which calls the gate from inside the function. At SEARCHER_COUNTERS_PER_STEP 0 the gate
returns True on every call, so the same record gives the per-call rate for contrast.
Writes <out>.counters.json after the harness finished: {"rows": [[step, uid, family,
calls, advances], ...], "max_advances_per_step": {family: n}, "calls_per_step": {...}}.
"""
from __future__ import annotations

import collections
import json
import os
import runpy
import sys


def main() -> int:
    argv = sys.argv[1:]
    out = argv[argv.index("--out") + 1]
    repo = os.path.abspath(argv[argv.index("--repo") + 1])
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import wildfire_model as wf  # noqa: E402
    import src_extension.adaptation.local_adaptation_generator as lag  # noqa: E402

    if not hasattr(lag, "_first_call_this_step"):
        print("MF1_COUNTERS: this checkout has no _first_call_this_step (pre-fix1)", file=sys.stderr)
        return 3
    cur = {"model": None}
    counts: dict = collections.defaultdict(lambda: [0, 0])
    orig_step = wf.WildFireModel.step

    def step(self):
        cur["model"] = self
        return orig_step(self)

    wf.WildFireModel.step = step
    orig_gate = lag._first_call_this_step

    def gate(wind_state, key, step_index):
        result = orig_gate(wind_state, key, step_index)
        uid = "?"
        model = cur["model"]
        if model is not None:
            for u, st in (getattr(model, "_wind_search_target_state", {}) or {}).items():
                if st is wind_state:
                    uid = str(u)
                    break
        cell = counts[(int(step_index or 0), uid, str(key))]
        cell[0] += 1
        cell[1] += int(bool(result))
        return result

    lag._first_call_this_step = gate
    harness = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ffr_harness.py")
    sys.argv = [harness] + argv
    rc = 0
    try:
        runpy.run_path(harness, run_name="__main__")
    except SystemExit as exc:
        rc = int(exc.code or 0)
    if rc != 0:
        return rc
    rows = [[s, u, k, c, a] for (s, u, k), (c, a) in sorted(counts.items())]
    max_adv: dict = collections.defaultdict(int)
    calls: dict = collections.defaultdict(list)
    for s, u, k, c, a in rows:
        if s <= 0:
            continue
        max_adv[k] = max(max_adv[k], a)
        calls[k].append(c)
    summary = {k: {"mean_calls": round(sum(v) / len(v), 3), "max_calls": max(v), "n": len(v)}
               for k, v in calls.items()}
    with open(out + ".counters.json", "w", encoding="utf-8") as fh:
        json.dump({"rows": rows, "max_advances_per_step": dict(max_adv), "calls_per_step": summary}, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
