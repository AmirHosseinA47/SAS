"""fix3b instrument: outputs/_fx3_probe.py (UNCHANGED) plus a CRN switch and read-only fix3b recorders.

usage: _fb3_probe.py [--crn] [--hazard] -- <_sd_probe.py args ...>

  --crn     common random numbers for the fire: Fire.step's single draw becomes crn_uniform(seed, cell
            unique_id, cell steps_counter) - EXACTLY outputs/_fm2_probe_harness.py's FM2P_CRN=1 construction
            (crn_uniform imported from it). The JSON records fb3.crn.crn_draws; a CRN run with 0 draws is
            invalid. CRN arms compare only with CRN arms.
  --hazard  passed through to _fx3_probe.py.
  REFUSES any --set FM2P_CRN=...: _fx3_probe / _sd_probe accept that key and silently ignore it
  (outputs/fix3b_crn_audit.txt). CRN is requested with --crn only.

Adds d["fb3"] to the probe JSON (read-only observers; no RNG draw, no simulation write):
  crn        {"on": bool, "crn_draws": n}
  coverage   every 10 steps (and the last): [step, share of cells ever inside any UAV's Euclidean-8
             detection disc (the probe's own record, all arms), belief summary or None]
  spawn      {victim_id: [x, y]} at step 1 (before any move)
  stats      model._searcher_targeting_stats (per searcher: selections, give-ups, drops, fallbacks, ...)
  issued     model._searcher_targeting_issued: [step, uid, target, L, G, S, reachable_at_issue]
  timing     per-step ms of the belief update and the planner post-pass: {name: {n, median, p95, max, raw}}
  switches   the fix3b switch values the run saw
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import runpy
import sys
import textwrap
import inspect

HERE = os.path.dirname(os.path.abspath(__file__))
FIX3B_KEYS = ("SEARCHER_TARGETING", "SEARCHER_TARGETING_COORDINATION", "SEARCHER_TARGETING_REACHABILITY",
              "SEARCHER_TARGETING_BATTERY", "SEARCHER_BELIEF_MOTION", "SEARCHER_TARGETING_RW_GATED",
              "SEARCHER_BELIEF_PD", "SEARCHER_BELIEF_PD_SMOKE", "SEARCHER_BELIEF_DIFFUSION_Q",
              "SEARCHER_BELIEF_FLEE_D50", "SEARCHER_BELIEF_FLEE_S", "SEARCHER_BELIEF_FLEE_P_GO",
              "SEARCHER_BELIEF_FLEE_BETA", "SEARCHER_BELIEF_FLEE_Q_CALM", "SEARCHER_BELIEF_BURNOVER",
              "SEARCHER_BELIEF_STRIDE", "SEARCHER_TARGETING_TOP_M", "SEARCHER_TARGETING_L0",
              "SEARCHER_TARGETING_SWEPT_RHO", "SEARCHER_TARGETING_MIN_DIST", "SEARCHER_TARGETING_GIVEUP_COOLDOWN",
              "SEARCHER_TARGETING_FALLBACK_HOLD", "SEARCHER_TARGETING_TILE", "SEARCHER_TARGETING_AGE_BUCKET",
              "VICTIM_SPAWN_MODE")


def _crn_uniform():
    spec = importlib.util.spec_from_file_location("_fm2_probe_harness_crn", os.path.join(HERE, "_fm2_probe_harness.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.crn_uniform


def _summ(values):
    if not values:
        return {"n": 0}
    s = sorted(values)
    return {"n": len(s), "median": s[len(s) // 2], "p95": s[min(len(s) - 1, int(math.ceil(0.95 * len(s))) - 1)],
            "max": s[-1], "raw": values}


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _fb3_probe.py [--crn] [--hazard] -- <_sd_probe.py args>", file=sys.stderr)
        return 2
    own = argv[:argv.index("--")]
    probe_args = argv[argv.index("--") + 1:]
    unknown = [a for a in own if a not in ("--crn", "--hazard")]
    if unknown:
        print("FB3 REFUSED: unknown own flag(s) %r (only --crn, --hazard)" % (unknown,), file=sys.stderr)
        return 2
    for i, a in enumerate(probe_args):
        key = None
        if a == "--set" and i + 1 < len(probe_args):
            key = probe_args[i + 1]
        elif a.startswith("--set="):
            key = a[len("--set="):]
        if key is not None and key.split("=", 1)[0].strip().upper() == "FM2P_CRN":
            print("FB3 REFUSED: --set FM2P_CRN is ignored by _fx3_probe/_sd_probe; use --crn", file=sys.stderr)
            return 3
    use_crn = "--crn" in own
    out_path = probe_args[probe_args.index("--out") + 1]
    seed = int(probe_args[probe_args.index("--seed") + 1])
    repo = r"E:\Projects\SAS"
    for i, a in enumerate(probe_args):
        if a == "--repo":
            repo = probe_args[i + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402

    crn = {"on": use_crn, "crn_draws": 0}
    if use_crn:
        crn_uniform = _crn_uniform()
        src = textwrap.dedent(inspect.getsource(am.Fire.step))
        needle = "generated = random.random()"
        if src.count(needle) != 1:
            print("FB3: Fire.step draw line not found exactly once - refusing to run", file=sys.stderr)
            return 4
        body = src.replace(needle, "generated = _fb3_draw(self)")
        factory = "def _fb3_make(_fb3_draw):\n" + textwrap.indent(body, "    ") + "    return step\n"
        ns: dict = {}
        exec(compile(factory, "<fb3 Fire.step>", "exec"), am.__dict__, ns)

        def _draw(fire):
            crn["crn_draws"] += 1
            return crn_uniform(seed, fire.unique_id, fire.steps_counter)

        patched = ns["_fb3_make"](_draw)
        patched.__qualname__ = am.Fire.step.__qualname__
        am.Fire.step = patched

    from src_extension.knowledge.victim_search_belief import disc_mask, disc_offsets  # noqa: E402

    state = {"model": None, "step": 0, "covered": None, "rows": [], "spawn": None}
    ostep = wf.WildFireModel.step

    def step(self):
        if state["spawn"] is None:
            state["spawn"] = {vid: [int(m.pos[0]), int(m.pos[1])] for vid, m in
                              (getattr(self, "victim_marker_agents", {}) or {}).items() if m.pos is not None}
        r = ostep(self)
        state["model"] = self
        state["step"] += 1
        try:
            h, w = int(self.HEIGHT), int(self.WIDTH)
            if state["covered"] is None:
                state["offsets"] = disc_offsets(float(getattr(wf, "UAV_OBSERVATION_RADIUS", 8)))
                state["covered"] = disc_mask(h, w, [], state["offsets"])
            cells = [(int(a.pos[0]), int(a.pos[1])) for a in self.schedule.agents
                     if type(a).__name__ == "UAV" and a.pos is not None]
            state["covered"] |= disc_mask(h, w, cells, state["offsets"])
            if state["step"] % 10 == 0:
                belief = getattr(self, "victim_search_belief", None)
                state["rows"].append([state["step"], round(float(state["covered"].mean()), 4),
                                      belief.summary() if belief is not None else None])
        except Exception as exc:  # an observer never stops the run
            state["rows"].append([state["step"], "ERR", repr(exc)[:200]])
        return r

    wf.WildFireModel.step = step

    fx3 = runpy.run_path(os.path.join(HERE, "_fx3_probe.py"), run_name="fx3_probe_module")
    sys.argv = [sys.argv[0]] + (["--hazard"] if "--hazard" in own else []) + ["--"] + probe_args
    rc = fx3["main"]()
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        m = state["model"]
        if state["rows"] and state["rows"][-1][0] != state["step"] and state["covered"] is not None:
            belief = getattr(m, "victim_search_belief", None)
            state["rows"].append([state["step"], round(float(state["covered"].mean()), 4),
                                  belief.summary() if belief is not None else None])
        timing = getattr(m, "_searcher_targeting_timing", None) or {}
        d["fb3"] = {
            "probe": "fb3_probe v1",
            "crn": crn,
            "coverage": state["rows"],
            "spawn": state["spawn"],
            "stats": getattr(m, "_searcher_targeting_stats", None) or {},
            "issued": getattr(m, "_searcher_targeting_issued", None) or [],
            "timing": {k: _summ(list(v)) for k, v in timing.items()},
            "switches": {k: getattr(cfv, k, None) for k in FIX3B_KEYS},
            "eff": {"searcher_targeting": am.searcher_targeting(), "victim_spawn_mode": am.victim_spawn_mode(),
                    "belief_built": getattr(m, "victim_search_belief", None) is not None,
                    "rw_stream_built": getattr(m, "_searcher_rw_rng", None) is not None,
                    "spawn_stream_built": getattr(m, "_victim_spawn_rng", None) is not None},
        }
        tmp = out_path + ".fb3tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("FB3 WRITE FAILED %r" % (exc,), file=sys.stderr)
        return 5
    if use_crn and crn["crn_draws"] == 0:
        print("FB3: --crn run made 0 CRN draws - INVALID", file=sys.stderr)
        return 6
    return rc


if __name__ == "__main__":
    sys.exit(main())
