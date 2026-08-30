"""Part 4 campaign harness for the route_blocked CONSUMER LATCH fix.

Same 18-run sample and identical params to outputs/_rb_campaign.py so results
line up seed-for-seed with the trigger-fix round (_rb_after_*.json == f2827ed).

Adds the two metrics the brief asks for:
  RECOVERY      - a unit that was route_blocked and later became dispatchable
                  again while still alive (status left route_blocked).
  OVERCORRECTION - a unit dispatched into a route that was ALREADY blocked at
                  the moment of the assign, measured with the same live BFS the
                  trigger uses. Counted separately for units that had previously
                  recovered (the fix's own re-dispatches) and for all assigns.
Read-only: wraps, never mutates.
"""
from __future__ import annotations
import argparse, collections, contextlib, io as _io, json, os, random, sys, time
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation

CUR = {"seed": None}
FIRES = []        # route_blocked transitions
RECOVERIES = []   # route_blocked -> dispatchable again, while alive
ASSIGNS = []      # every successful assign, with live-BFS verdict on its target
LATCH = []        # end-of-run units still route_blocked and alive
DEATHS = []
STATS = collections.Counter()

# units that have been route_blocked at least once, per seed
_blocked_ever: set[tuple[int, str]] = set()
_recovered_ever: set[tuple[int, str]] = set()


def _ff_cell(ff):
    p = getattr(ff, "pos", None)
    return (int(p[0]), int(p[1])) if p is not None else None


_orig_apply = WildFireModel.apply_physical_rescue_command


def _traced_apply(self, cmd):
    ok = _orig_apply(self, cmd)
    action = str(getattr(cmd, "action", "") or "").strip().lower()
    if not ok or action != "assign":
        return ok
    ff_id = str(getattr(cmd, "firefighter_id", "") or "")
    markers = getattr(self, "firefighter_marker_agents", None) or {}
    ff = markers.get(ff_id)
    if ff is None:
        return ok
    src = _ff_cell(ff)
    tgt = getattr(ff, "target_pos", None)
    if src is None or tgt is None:
        return ok
    tgt = (int(tgt[0]), int(tgt[1]))
    try:
        reachable = bool(ff._path_exists_avoiding_fire(src, tgt, ff._fire_cells()))
    except Exception:
        return ok
    seed = CUR["seed"]
    uid = str(getattr(ff, "unit_id", ff_id) or ff_id)
    rec = {
        "seed": seed,
        "step": int(getattr(self, "evaluation_timesteps_counter", 0) or 0),
        "ff": uid, "vid": str(getattr(cmd, "victim_id", "") or ""),
        "reason": str(getattr(cmd, "reason", "") or ""),
        "src": src, "target": tgt, "reachable_at_assign": reachable,
        "after_recovery": (seed, uid) in _recovered_ever,
    }
    ASSIGNS.append(rec)
    STATS["assigns"] += 1
    if not reachable:
        STATS["assign_into_blocked_route"] += 1
        if rec["after_recovery"]:
            STATS["assign_into_blocked_route_after_recovery"] += 1
    return ok


WildFireModel.apply_physical_rescue_command = _traced_apply


def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    CUR["seed"] = seed
    terminal_step = None
    ran = 0
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        prev_status: dict[str, str] = {}
        alive: dict[str, bool] = {}
        for s in range(1, steps + 1):
            model.step()
            ran = s
            for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                uid = str(getattr(m, "unit_id", "") or fid)
                st = str(getattr(m, "status", "") or "").strip().lower()
                dead = bool(getattr(m, "dead", False))
                before = prev_status.get(fid)
                if before != st:
                    if st == "route_blocked" and before != "route_blocked":
                        STATS["route_blocked_fires"] += 1
                        _blocked_ever.add((seed, uid))
                        FIRES.append({"seed": seed, "step": s, "ff": uid,
                                      "pos": _ff_cell(m), "from": before})
                    elif before == "route_blocked" and st not in ("route_blocked", "dead"):
                        STATS["recoveries"] += 1
                        _recovered_ever.add((seed, uid))
                        RECOVERIES.append({"seed": seed, "step": s, "ff": uid,
                                           "to": st, "pos": _ff_cell(m)})
                    prev_status[fid] = st
                was = alive.get(fid)
                if was is False and dead:
                    DEATHS.append({"seed": seed, "step": s, "ff": uid,
                                   "pos": _ff_cell(m),
                                   "was_blocked_ever": (seed, uid) in _blocked_ever,
                                   "recovered_ever": (seed, uid) in _recovered_ever})
                alive[fid] = dead
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = s
        for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
            st = str(getattr(m, "status", "") or "").strip().lower()
            if st == "route_blocked" and not getattr(m, "dead", False):
                LATCH.append({"seed": seed, "ff": str(getattr(m, "unit_id", "") or fid),
                              "pos": _ff_cell(m)})
        ev = _build_evaluation(model, terminal_step, ran, params)
    ev["seed"] = seed
    ev["wall_s"] = round(time.perf_counter() - t0, 1)
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft}
    evals = []
    for seed in [int(s) for s in a.seeds.split(",")]:
        ev = run(seed, params, a.steps)
        evals.append(ev)
        sys.stderr.write(
            "%s %s seed %s done %ss: rescued=%s dead=%s ff_deaths=%s "
            "| fires=%s recoveries=%s bad_assign=%s\n"
            % (a.tag, a.wind, seed, ev.get("wall_s"), ev.get("rescued"),
               ev.get("dead"), ev.get("firefighter_deaths"),
               STATS["route_blocked_fires"], STATS["recoveries"],
               STATS["assign_into_blocked_route"]))
        sys.stderr.flush()
    out = {"tag": a.tag, "scenario": a.scenario, "wind": a.wind, "steps": a.steps,
           "seeds": a.seeds, "params": params, "evals": evals,
           "stats": dict(STATS), "fires": FIRES, "recoveries": RECOVERIES,
           "assigns": ASSIGNS, "latched": LATCH, "deaths": DEATHS}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_rblatch_camp_%s_%s_%s.json" % (a.tag, a.scenario, a.wind))
    with open(p, "w") as f:
        json.dump(out, f, default=str)
    print(p)


main()
