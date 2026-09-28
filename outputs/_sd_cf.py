"""sysdebug round: counterfactual / instrumentation wrapper around outputs/_sd_probe.py.

DIAGNOSIS ONLY - every patch lives in THIS process; no source file is touched.

usage: _sd_cf.py [--cf-crn] [--cf-dedupe] -- <_sd_probe.py args ...>

  --cf-crn     common random numbers for the fire, exactly the construction of
               outputs/_fm2_probe_harness.py FM2P_CRN=1: Fire.step's single draw becomes
               a pure function of (seed, cell unique_id, cell steps_counter). CRN arms
               compare only with CRN arms.
  --cf-dedupe  the wind-search state machine's per-CALL counters made per-STEP:
               (a) local_adaptation_generator._record_victim_searcher_x_band keeps ONE
                   recent_x/y_positions sample per searcher per model step (a second call
                   in the same step REPLACES that step's sample instead of appending);
               (b) _sync_wind_search_streaks runs at most once per searcher per model
                   step (later calls in the same step return without touching state).
               This is the named-in-steps semantics of COVERAGE_Y_SWEEP_MIN_STEPS,
               the 30-entry windows, pocket/edge/hold/same-target streaks and
               steps_since_detection. It is a counterfactual, not a proposed fix.
Always recorded (both arms): per-step call counts of _record_victim_searcher_x_band,
_sync_wind_search_streaks and LocalAdaptationSpaceGenerator._compute_wind_aware_search_target,
and per-step per-searcher coverage_y_commit / force_coverage_escape / escape_target.
The record is added to the probe JSON as key "cf" after the probe finished (atomic replace).
"""
from __future__ import annotations

import collections
import inspect
import json
import os
import runpy
import sys
import textwrap

M64 = (1 << 64) - 1


def _splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & M64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
    return z ^ (z >> 31)


def crn_uniform(seed: int, uid: int, tick: int) -> float:
    h = _splitmix64(_splitmix64(_splitmix64(int(seed) & M64) ^ (int(uid) & M64)) ^ (int(tick) & M64))
    return (h >> 11) / float(1 << 53)


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _sd_cf.py [--cf-crn] [--cf-dedupe] -- <probe args>", file=sys.stderr)
        return 2
    cut = argv.index("--")
    own, probe_args = argv[:cut], argv[cut + 1:]
    use_crn = "--cf-crn" in own
    use_dedupe = "--cf-dedupe" in own
    repo = r"E:\Projects\SAS"
    if "--repo" in probe_args:
        repo = probe_args[probe_args.index("--repo") + 1]
    seed = int(probe_args[probe_args.index("--seed") + 1])
    out_path = probe_args[probe_args.index("--out") + 1]
    sys.path.insert(0, os.path.abspath(repo))
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.adaptation.local_adaptation_generator as lag  # noqa: E402

    rec = {"config": {"crn": use_crn, "dedupe": use_dedupe},
           "counters": collections.Counter(), "calls_per_step": [], "searcher_state": []}
    cur = {"step": 0}
    per_step = collections.Counter()

    # -- current model step (set before the original step body runs)
    orig_model_step = wf.WildFireModel.step

    def model_step(self):
        cur["step"] += 1
        per_step.clear()
        r = orig_model_step(self)
        rec["calls_per_step"].append([per_step.get("record", 0), per_step.get("sync", 0), per_step.get("target", 0)])
        row = {}
        store = getattr(self, "_wind_search_target_state", {}) or {}
        for uid, st in store.items():
            et = st.get("escape_target")
            row[str(uid)] = [st.get("coverage_y_commit"), int(bool(st.get("force_coverage_escape"))),
                             (list(et) if isinstance(et, (list, tuple)) else None),
                             int(st.get("pocket_streak", 0) or 0), int(bool(st.get("west_strip_done"))),
                             int(bool(st.get("east_strip_done"))), st.get("lane_axis")]
        rec["searcher_state"].append(row)
        return r

    wf.WildFireModel.step = model_step

    # -- CRN fire draw (identical construction to _fm2_probe_harness FM2P_CRN)
    if use_crn:
        src = textwrap.dedent(inspect.getsource(am.Fire.step))
        needle = "generated = random.random()"
        if src.count(needle) != 1:
            raise SystemExit("SD_CF: Fire.step draw line not found exactly once - refusing to run")
        body = src.replace(needle, "generated = _sd_draw(self)")
        factory = "def _sd_make(_sd_draw):\n" + textwrap.indent(body, "    ") + "    return step\n"
        ns: dict = {}
        exec(compile(factory, "<sd_cf Fire.step>", "exec"), am.__dict__, ns)

        def _draw(fire):
            rec["counters"]["crn_draws"] += 1
            return crn_uniform(seed, fire.unique_id, fire.steps_counter)

        patched = ns["_sd_make"](_draw)
        patched.__qualname__ = am.Fire.step.__qualname__
        am.Fire.step = patched

    # -- per-call instrumentation (+ optional per-step dedupe)
    orig_record = lag._record_victim_searcher_x_band

    def record(wind_state, agent_x, agent_y=None):
        per_step["record"] += 1
        rec["counters"]["record_calls"] += 1
        if use_dedupe:
            if wind_state.get("_sd_rec_step") == cur["step"]:
                # replace this step's sample instead of appending a new one
                if agent_x is not None and wind_state.get("recent_x_positions"):
                    wind_state["recent_x_positions"][-1] = int(round(float(agent_x)))
                if agent_y is not None and wind_state.get("recent_y_positions"):
                    wind_state["recent_y_positions"][-1] = int(round(float(agent_y)))
                rec["counters"]["record_deduped"] += 1
                return None
            wind_state["_sd_rec_step"] = cur["step"]
        return orig_record(wind_state, agent_x, agent_y)

    lag._record_victim_searcher_x_band = record

    orig_sync = lag._sync_wind_search_streaks

    def sync(wind_state, **kw):
        per_step["sync"] += 1
        rec["counters"]["sync_calls"] += 1
        if use_dedupe:
            if wind_state.get("_sd_sync_step") == cur["step"]:
                rec["counters"]["sync_skipped"] += 1
                return None
            wind_state["_sd_sync_step"] = cur["step"]
        return orig_sync(wind_state, **kw)

    lag._sync_wind_search_streaks = sync

    orig_target = lag.LocalAdaptationSpaceGenerator._compute_wind_aware_search_target

    def target(self, *a, **k):
        per_step["target"] += 1
        return orig_target(self, *a, **k)

    lag.LocalAdaptationSpaceGenerator._compute_wind_aware_search_target = target

    # -- run the probe in this process
    probe = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sd_probe.py"),
                           run_name="sd_probe_module")
    sys.argv = [sys.argv[0]] + probe_args
    rc = probe["main"]()
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        rec["counters"] = dict(rec["counters"])
        d["cf"] = rec
        tmp = out_path + ".cftmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("SD_CF RECORD FAILED: %r" % (exc,), file=sys.stderr)
        return 5
    print("SD_CF_DONE crn=%s dedupe=%s counters=%s" % (use_crn, use_dedupe, dict(rec["counters"])))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
