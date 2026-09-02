"""Defect #5: settle whether the 6 flagged firefighter 'drops' are real drops
or immediate re-dispatch after a successful recycle.

Single run, D/east half-roles seed 101, 120 steps (drops seen at step 46).
"""
from __future__ import annotations
import contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

LOG = []
CUR = {"step": 0, "in_proc": False}


def _snap(ff):
    return {
        "unit_id": str(getattr(ff, "unit_id", "")),
        "uid": getattr(ff, "unique_id", None),
        "status": str(getattr(ff, "status", "")),
        "assigned": bool(getattr(ff, "assigned", False)),
        "exiting": bool(getattr(ff, "exiting", False)),
        "exit_target": str(getattr(ff, "exit_target", None)),
        "target_pos": str(getattr(ff, "target_pos", None)),
        "rescued_victim": str(getattr(getattr(ff, "rescued_victim", None),
                                      "victim_id", None)),
        "rescue_completed": bool(getattr(ff, "rescue_completed", False)),
        "pos": str(getattr(ff, "pos", None)),
        "dead": bool(getattr(ff, "dead", False)),
    }


_orig_recycle = WildFireModel._recycle_firefighter_after_exit


def _recycle_obs(self, ff_marker):
    before = _snap(ff_marker)
    r = _orig_recycle(self, ff_marker)
    LOG.append({"step": CUR["step"], "event": "recycle_ran",
                "before": before, "after": _snap(ff_marker)})
    return r


WildFireModel._recycle_firefighter_after_exit = _recycle_obs

_orig_dispatch = WildFireModel._dispatch_firefighter_to_victim


def _dispatch_obs(self, vid, marker, reason, *a, **k):
    r = _orig_dispatch(self, vid, marker, reason, *a, **k)
    LOG.append({"step": CUR["step"], "event": "dispatch",
                "vid": str(vid), "reason": str(reason),
                "in_removal_processing": CUR["in_proc"],
                "result": str(r)[:120]})
    return r


WildFireModel._dispatch_firefighter_to_victim = _dispatch_obs

_orig_proc = WildFireModel._process_pending_agent_removals


def _proc_obs(self):
    pending = list(getattr(self, "_agents_pending_removal", []) or [])
    ffs = [a for a in pending if type(a).__name__ == "Firefighter"]
    if ffs:
        LOG.append({"step": CUR["step"], "event": "proc_enter",
                    "queue_len": len(pending),
                    "ff_before": [_snap(f) for f in ffs]})
    CUR["in_proc"] = True
    try:
        ret = _orig_proc(self)
    finally:
        CUR["in_proc"] = False
    if ffs:
        LOG.append({"step": CUR["step"], "event": "proc_exit", "returned": int(ret or 0),
                    "ff_after": [_snap(f) for f in ffs],
                    "still_in_schedule": [
                        getattr(self.schedule, "_agents", {}).get(f.unique_id) is f
                        for f in ffs],
                    "queue_after": len(getattr(self, "_agents_pending_removal", []) or [])})
    return ret


WildFireModel._process_pending_agent_removals = _proc_obs

_orig_step = WildFireModel.step


def _step_obs(self):
    CUR["step"] += 1
    return _orig_step(self)


WildFireModel.step = _step_obs

if __name__ == "__main__":
    STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    p = {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
         "WIND_DIRECTION": "east", "BATCH_SIZE": 300,
         "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
         "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 2}
    rng = random.Random(101)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **p)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
        for _ in range(STEPS):
            m.step()
    keep = [e for e in LOG if e["event"] != "dispatch"
            or e.get("in_removal_processing")]
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_pr_verify.json"), "w", encoding="utf-8") as fh:
        json.dump({"steps": STEPS, "log": LOG}, fh, indent=2, default=str)
    for e in LOG:
        print(json.dumps(e, default=str)[:600])
    print("WROTE outputs/_pr_verify.json  events=%d" % len(LOG))
