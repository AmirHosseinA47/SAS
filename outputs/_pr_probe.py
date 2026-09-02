"""Defect #5 Part-2 probe: instrument _agents_pending_removal end to end.

Read-only w.r.t. simulation logic: every patch is an observer that calls the
original and re-raises unchanged, so control flow is byte-identical.
"""
from __future__ import annotations
import contextlib, io as _io, json, os, random, sys, traceback
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

REC = {
    "calls": 0,
    "queued_total": 0,
    "queued_by_type": {},
    "enqueue_events": [],
    "removed": 0,
    "recycled": 0,
    "dropped": [],
    "helper_exc": [],
    "double_queued": 0,
    "requeued_after": 0,
    "fallthrough": [],
    "pathmarker_sched_guard_skips": 0,
    "left_pending_at_end": [],
    "max_queue_len": 0,
    "returned_counts": [],
    "victim_finalize_calls": 0,
    "victim_double_finalize": 0,
}
SEEN_QUEUED = set()
CUR = {"step": 0}


def _tname(a):
    return type(a).__name__


def _in_sched(model, a):
    try:
        return getattr(model.schedule, "_agents", {}).get(a.unique_id) is a
    except Exception:
        return False


def _wrap_raise_recorder(owner, name):
    orig = getattr(owner, name)

    def _w(self, *a, **k):
        try:
            return orig(self, *a, **k)
        except Exception as exc:
            REC["helper_exc"].append(
                {"step": CUR["step"], "helper": name,
                 "exc": "%s: %s" % (type(exc).__name__, exc),
                 "tb": traceback.format_exc(limit=6)}
            )
            raise
    setattr(owner, name, _w)


for _h in ("_victim_id_from_agent", "_finalize_rescued_victim",
           "_recycle_firefighter_after_exit",
           "_try_dispatch_unresolved_confirmed_victims"):
    _wrap_raise_recorder(WildFireModel, _h)

_orig_final = WildFireModel._finalize_rescued_victim
_FINAL_SEEN = set()


def _final_obs(self, victim_id, agent=None, firefighter_id=None):
    REC["victim_finalize_calls"] += 1
    key = str(victim_id or "")
    if key and key in _FINAL_SEEN:
        REC["victim_double_finalize"] += 1
    if key:
        _FINAL_SEEN.add(key)
    return _orig_final(self, victim_id, agent, firefighter_id)


WildFireModel._finalize_rescued_victim = _final_obs

_orig_clear = WildFireModel._clear_rescue_path


def _clear_obs(self):
    before = len(getattr(self, "_agents_pending_removal", []) or [])
    r = _orig_clear(self)
    after = len(getattr(self, "_agents_pending_removal", []) or [])
    for _ in range(max(0, after - before)):
        REC["enqueue_events"].append((CUR["step"], "_clear_rescue_path", "PathMarker"))
    return r


WildFireModel._clear_rescue_path = _clear_obs

_orig_proc = WildFireModel._process_pending_agent_removals


def _proc_obs(self):
    pending = list(getattr(self, "_agents_pending_removal", []) or [])
    REC["calls"] += 1
    if len(pending) > REC["max_queue_len"]:
        REC["max_queue_len"] = len(pending)
    seen_this_call = set()
    snap = []
    for a in pending:
        oid = id(a)
        if oid in seen_this_call:
            REC["double_queued"] += 1
        seen_this_call.add(oid)
        if oid in SEEN_QUEUED:
            REC["requeued_after"] += 1
        SEEN_QUEUED.add(oid)
        tn = _tname(a)
        REC["queued_total"] += 1
        REC["queued_by_type"][tn] = REC["queued_by_type"].get(tn, 0) + 1
        if tn not in ("PathMarker", "Victim", "Firefighter"):
            REC["fallthrough"].append({"step": CUR["step"], "type": tn})
        guard_skip = False
        if tn == "PathMarker":
            guard_skip = a.unique_id not in getattr(self.schedule, "_agents", {})
        snap.append({
            "obj": a, "tn": tn, "uid": getattr(a, "unique_id", None),
            "pos": getattr(a, "pos", None), "sched": _in_sched(self, a),
            "dead": bool(getattr(a, "dead", False)),
            "guard_skip": guard_skip,
        })
        if guard_skip:
            REC["pathmarker_sched_guard_skips"] += 1

    ret = _orig_proc(self)

    n_removed = 0
    n_recycled = 0
    for s in snap:
        a = s["obj"]
        tn = s["tn"]
        pos_now = getattr(a, "pos", None)
        sched_now = _in_sched(self, a)
        if tn in ("PathMarker", "Victim") or (tn == "Firefighter" and s["dead"]):
            ok = (pos_now is None) and (not sched_now)
            if ok:
                n_removed += 1
            else:
                REC["dropped"].append({
                    "step": CUR["step"], "type": tn, "uid": s["uid"],
                    "why": "not_removed",
                    "pos_before": str(s["pos"]), "pos_after": str(pos_now),
                    "sched_before": s["sched"], "sched_after": sched_now,
                })
        elif tn == "Firefighter":
            recycled = (str(getattr(a, "status", "")) == "available"
                        and not getattr(a, "exiting", False)
                        and getattr(a, "rescued_victim", None) is None
                        and not getattr(a, "rescue_completed", False))
            if recycled:
                n_recycled += 1
            else:
                REC["dropped"].append({
                    "step": CUR["step"], "type": tn, "uid": s["uid"],
                    "why": "not_recycled",
                    "status": str(getattr(a, "status", "")),
                    "exiting": bool(getattr(a, "exiting", False)),
                    "rescue_completed": bool(getattr(a, "rescue_completed", False)),
                })
        else:
            REC["dropped"].append({
                "step": CUR["step"], "type": tn, "uid": s["uid"],
                "why": "fallthrough_unhandled_type",
            })
    REC["removed"] += n_removed
    REC["recycled"] += n_recycled
    REC["returned_counts"].append((CUR["step"], int(ret or 0), n_removed, n_recycled))
    return ret


WildFireModel._process_pending_agent_removals = _proc_obs

_orig_ff_step = am.Firefighter.step


def _ff_step_obs(self):
    m = self.model
    before = len(getattr(m, "_agents_pending_removal", []) or [])
    r = _orig_ff_step(self)
    q = getattr(m, "_agents_pending_removal", []) or []
    for a in q[before:]:
        REC["enqueue_events"].append((CUR["step"], "Firefighter.exit", _tname(a)))
    return r


am.Firefighter.step = _ff_step_obs


def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for i in range(steps):
            CUR["step"] = i + 1
            model.step()
    left = list(getattr(model, "_agents_pending_removal", []) or [])
    for a in left:
        REC["left_pending_at_end"].append({
            "seed": seed, "type": _tname(a),
            "uid": getattr(a, "unique_id", None),
            "pos": str(getattr(a, "pos", None)),
            "in_sched": _in_sched(model, a),
        })
    return model


def base(ft, vs):
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": "east", "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


COMBOS = []
for _s in (101, 202, 303, 404, 505):
    _p = base(2, 2)
    _p["WIND_DIRECTION"] = "east"
    COMBOS.append(("D/east/half", _s, _p))
for _s in (101, 202, 303, 404, 505):
    _p = base(2, 2)
    _p["WIND_DIRECTION"] = "south"
    COMBOS.append(("D/south/half", _s, _p))
for _s in (101, 202, 303):
    _p = base(None, None)
    _p["WIND_DIRECTION"] = "east"
    COMBOS.append(("D/east/default", _s, _p))

if __name__ == "__main__":
    STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 240
    per_run = []
    for label, seed, params in COMBOS:
        q0 = REC["queued_total"]
        r0 = REC["removed"]
        c0 = REC["recycled"]
        d0 = len(REC["dropped"])
        e0 = len(REC["helper_exc"])
        _FINAL_SEEN.clear()
        run(seed, params, STEPS)
        per_run.append({
            "combo": label, "seed": seed,
            "queued": REC["queued_total"] - q0,
            "removed": REC["removed"] - r0,
            "recycled": REC["recycled"] - c0,
            "dropped": len(REC["dropped"]) - d0,
            "helper_exc": len(REC["helper_exc"]) - e0,
        })
        print("%s seed=%s queued=%d removed=%d recycled=%d dropped=%d exc=%d"
              % (label, seed, per_run[-1]["queued"], per_run[-1]["removed"],
                 per_run[-1]["recycled"], per_run[-1]["dropped"],
                 per_run[-1]["helper_exc"]), flush=True)
    out = {
        "steps": STEPS,
        "per_run": per_run,
        "totals": {k: REC[k] for k in
                   ("calls", "queued_total", "queued_by_type", "removed",
                    "recycled", "double_queued", "requeued_after",
                    "pathmarker_sched_guard_skips", "max_queue_len",
                    "victim_finalize_calls", "victim_double_finalize")},
        "dropped": REC["dropped"][:80],
        "n_dropped": len(REC["dropped"]),
        "fallthrough": REC["fallthrough"][:40],
        "helper_exc": REC["helper_exc"][:20],
        "n_helper_exc": len(REC["helper_exc"]),
        "left_pending_at_end": REC["left_pending_at_end"],
        "return_mismatch": [t for t in REC["returned_counts"] if t[1] != t[2]][:40],
        "n_return_mismatch": sum(1 for t in REC["returned_counts"] if t[1] != t[2]),
    }
    sites = {}
    for _st, site, tn in REC["enqueue_events"]:
        k = "%s:%s" % (site, tn)
        sites[k] = sites.get(k, 0) + 1
    out["enqueue_sites"] = sites
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_pr_probe.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print("WROTE outputs/_pr_probe.json")
