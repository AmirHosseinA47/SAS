"""Part 2 what-if probe for the route_blocked unassign inflow.

Nothing is written to source. Each arm is applied as a runtime monkeypatch on
top of HEAD 62b4fbe so the design can be tested BEFORE any edit, same
discipline as outputs/_ir_whatif.py in the idle-retreat round.

ARMS
  none    control. Must reproduce the Part 1 sample exactly (bit-check).

  abort   Stop walking toward the blocked target once the unit has been
          released. Today _move_toward raises route_blocked, the handler
          unassigns the unit synchronously, and then the SAME call keeps going
          and steps the unit one cell using tiers scored against the target it
          no longer has. This arm ends the call at the release instead.

  retreat "Check for immediate danger and move now" at the release point:
          call the already-fixed Firefighter._survival_move() from the unassign
          site. Implies `abort`, and NOT for cosmetic reasons - see below.

  both    retreat + abort (identical to `retreat`; kept as an explicit label).

WHY `retreat` CANNOT BE APPLIED WITHOUT `abort`
  _move_toward builds `scored` from self._neighbor_cells() BEFORE it calls
  _mark_route_blocked(). If the release handler moves the unit, `chosen` is
  still a neighbour of the cell the unit has just left, and the trailing
  grid.move_agent(self, chosen) teleports it up to two cells. Any real
  implementation of the step-5 proposal has to stop the rest of that call.

usage:
  _ui_whatif.py --arm none    --wind south --seeds 101 --steps 240 --tag S101
"""
from __future__ import annotations
import argparse, contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import (
    BUILTIN_SCENARIOS,
    _build_evaluation,
    _resolve_role_count_params,
)

ARM = {"retreat": False, "abort": False}
CUR = {"seed": None}
DEATHS = []
EVALS = []
FFTRACE = []
EVENTS = []      # what the arm actually did, per release
MT_STACK = []

# HOW `abort` IS IMPLEMENTED, AND WHY NOT BY RAISING
#   Raising out of apply_physical_rescue_command does not work:
#   _process_rescue_incidents wraps _handle_rescue_incident in a bare
#   `except Exception: continue` (wildfire_model.py:2869-2875), so the
#   exception is swallowed there and never reaches _move_toward - and even if
#   it were re-raised, it would skip the replacement dispatch at
#   wildfire_model.py:2831-2840, which is NOT part of what this arm changes.
#   Instead the released agent is flagged, and the ONE trailing
#   grid.move_agent(self, chosen) at agents.py:1163 is suppressed for it.
#   _survival_move (the `retreat` arm) runs BEFORE the flag is set, so its own
#   move is never suppressed.
SUPPRESS = set()   # id(agent) whose next grid move is cancelled


def _step_no(model):
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def _mfd(cell, fires):
    if not fires:
        return 999
    cx, cy = cell
    return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fires)


# ------------------------------------------------------------------ the arms
_orig_cmd = wf.WildFireModel.apply_physical_rescue_command


def _cmd(self, command):
    action = str(getattr(command, "action", "") or "")
    reason = str(getattr(command, "reason", "") or "")
    ff_id = str(getattr(command, "firefighter_id", "") or "")
    ok = _orig_cmd(self, command)
    if not (ok and action == "unassign" and "blocked" in reason):
        return ok
    ffm = (getattr(self, "firefighter_marker_agents", {}) or {}).get(ff_id)
    if ffm is None or getattr(ffm, "pos", None) is None:
        return ok
    fires = ffm._fire_cells()
    pre = (int(ffm.pos[0]), int(ffm.pos[1]))
    nb = ffm._neighbor_cells()
    free = [c for c in nb if not ffm._cell_contains_active_fire(c)]
    ev = {
        "seed": CUR["seed"], "step": _step_no(self),
        "ff": str(getattr(ffm, "unit_id", ff_id)),
        "pre": list(pre), "pre_mfd": _mfd(pre, fires),
        "enclosed": len(free) == 0,
        "n_free": len(free),
        "retreat_ran": False, "retreat_moved": False,
        "post": list(pre), "post_mfd": _mfd(pre, fires),
        "aborted": False,
    }
    if ARM["retreat"]:
        ffm._survival_move()
        post = (int(ffm.pos[0]), int(ffm.pos[1]))
        ev["retreat_ran"] = True
        ev["retreat_moved"] = post != pre
        ev["post"] = list(post)
        ev["post_mfd"] = _mfd(post, ffm._fire_cells())
    EVENTS.append(ev)
    if ARM["abort"] and MT_STACK:
        ev["aborted"] = True
        SUPPRESS.add(id(ffm))
    return ok


wf.WildFireModel.apply_physical_rescue_command = _cmd


import mesa.space as _ms

_orig_move_agent = _ms.MultiGrid.move_agent


def _move_agent(self, agent, pos):
    if id(agent) in SUPPRESS:
        SUPPRESS.discard(id(agent))
        return
    return _orig_move_agent(self, agent, pos)


_ms.MultiGrid.move_agent = _move_agent


_orig_mt = am.Firefighter._move_toward


def _mt(self, target):
    MT_STACK.append(1)
    try:
        _orig_mt(self, target)
    finally:
        MT_STACK.pop()
        SUPPRESS.discard(id(self))


am.Firefighter._move_toward = _mt


def _fire_cells(model):
    out = set()
    for a in model.schedule.agents:
        if type(a) is am.Fire and a.is_burning():
            p = getattr(a, "pos", None)
            if p is not None:
                out.add((int(p[0]), int(p[1])))
    return out


def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    CUR["seed"] = seed
    alive = {}
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for s in range(1, steps + 1):
            model.step()
            fires = _fire_cells(model)
            for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                d = bool(getattr(m, "dead", False))
                pos = getattr(m, "pos", None)
                cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                FFTRACE.append({
                    "seed": seed, "step": s, "ff": str(getattr(m, "unit_id", fid)),
                    "ff_id": fid, "pos": (list(cell) if cell else None), "dead": d,
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "mfd": (_mfd(cell, fires) if cell else None),
                })
                if fid not in alive:
                    alive[fid] = d
                elif d and not alive[fid]:
                    DEATHS.append({"seed": seed, "step": s,
                                   "ff": str(getattr(m, "unit_id", fid)),
                                   "ff_id": fid,
                                   "pos": (list(cell) if cell else None)})
                alive[fid] = d
        ev = _build_evaluation(model, None, steps, params)
        ev["seed"] = seed
        EVALS.append(ev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="none",
                    choices=["none", "abort", "retreat", "both"])
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", default="101")
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    if a.arm in ("retreat", "both"):
        ARM["retreat"] = True
        ARM["abort"] = True   # mandatory, see module docstring
    elif a.arm == "abort":
        ARM["abort"] = True

    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    if a.roles == "half":
        ft = n // 2 or 1
        vs = n - ft
    else:
        ft, vs = _resolve_role_count_params(n, None, None)
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"],
              "WIND_DIRECTION": a.wind, "BATCH_SIZE": 300,
              "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}
    for seed in [int(s) for s in a.seeds.split(",")]:
        run(seed, params, a.steps)
        sys.stderr.write("arm=%s seed=%s done: %d deaths, %d releases\n"
                         % (a.arm, seed, len(DEATHS), len(EVENTS)))
        sys.stderr.flush()
    out = {"arm": a.arm, "scenario": a.scenario, "wind": a.wind,
           "roles": a.roles, "steps": a.steps, "seeds": a.seeds,
           "deaths": DEATHS, "evals": EVALS, "events": EVENTS,
           "fftrace": FFTRACE}
    tag = a.tag or ("%s_%s" % (a.wind, a.roles))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_ui_wi_%s_%s.json" % (a.arm, tag))
    with open(p, "w") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    print(p)


main()
