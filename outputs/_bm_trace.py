"""Base-mark round: per-step geometry trace at the SHIPPED default (MODE 3).

One instrument for three Part 1 questions, so they are answered from the same
runs rather than from three differently-configured probes:

  * Item B - the firefighter's retreat range as the model actually applies it:
    per unit, per step, the state class that selects the range
    (agents.py _needs_immediate_survival_retreat: exiting -> no range,
    target_pos -> 1, else idle_buffer = 3), so the flicker rate of a
    state-dependent frame is MEASURED, not guessed. Also every dispatch distance.
  * Overlap - positions of every UAV / victim / firefighter, so frame-vs-depot,
    frame-vs-frame and edge clipping can be recomputed offline for any candidate.
  * Depot occupancy - which units sit inside a depot block, and whether fire,
    smoke, burnt or scorched ground reaches it (the flag's real background).

Display-only probe: reads the model, writes nothing into it. Parameters are the
dashboard's own defaults (serve_dashboard.py form values), not evaluate_scenarios'.

usage: _bm_trace.py <seed> <wind> <steps> <out.json>
"""
from __future__ import annotations
import contextlib, io as _io, json, os, random, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
import serve_dashboard as sd


def params(wind: str) -> dict:
    return {"NUM_AGENTS": 3, "NUM_VICTIMS": 5, "NUM_FIREFIGHTERS": 3,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 1}


def ff_state(a) -> str:
    """The class that selects the retreat range, in the model's own order."""
    if str(getattr(a, "status", "") or "").strip().lower() == "dead" or getattr(a, "dead", False):
        return "dead"
    if getattr(a, "pos", None) is None:
        return "offgrid"
    if getattr(a, "exiting", False):
        return "exiting"          # _needs_immediate_survival_retreat returns False
    if getattr(a, "target_pos", None):
        return "assigned"         # range 1 (+ von Neumann adjacency, same set)
    return "idle"                 # range idle_buffer


def main() -> int:
    seed = int(sys.argv[1]); wind = sys.argv[2]; steps = int(sys.argv[3]); out = sys.argv[4]
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
    P = params(wind)
    apply_scenario_config(cfv, wf, **P)
    rows, dispatches = [], []
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel(); model.debug_log = False
        station = getattr(model, "base_station", None)
        depots = []
        if station is not None:
            blocks = station.get("depots") or ({"origin": station["origin"], "size": station["size"]},)
            depots = [{"x": int(d["origin"][0]), "y": int(d["origin"][1]), "size": int(d["size"])}
                      for d in blocks]
        prev_target = {}
        for step in range(steps + 1):
            if step:
                model.step()
            burning, ground = set(), {}
            for a in model.schedule.agents:
                if type(a).__name__ != "Fire" or a.pos is None:
                    continue
                if a.is_burning():
                    burning.add((int(a.pos[0]), int(a.pos[1])))
            # ground colour under each depot cell, exactly as the dashboard publishes it
            frame = sd._capture_frame(model, step)
            depot_ground = []
            for d in depots:
                cols = {}
                for x in range(d["x"], d["x"] + d["size"]):
                    for y in range(d["y"], d["y"] + d["size"]):
                        c = frame["cells"].get("%d,%d" % (x, y), "#1c630b")
                        cols[c] = cols.get(c, 0) + 1
                depot_ground.append(cols)
            ffs = []
            for a in model.schedule.agents:
                if type(a).__name__ != "Firefighter":
                    continue
                uid = str(getattr(a, "unique_id", ""))
                st = ff_state(a)
                pos = None if a.pos is None else [int(a.pos[0]), int(a.pos[1])]
                tgt = getattr(a, "target_pos", None)
                tgt = [int(tgt[0]), int(tgt[1])] if tgt else None
                nfd = None
                if pos is not None and burning:
                    nfd = min(abs(pos[0] - bx) + abs(pos[1] - by) for bx, by in burning)
                ffs.append({"id": uid, "pos": pos, "state": st, "target": tgt,
                            "assigned_attr": bool(getattr(a, "assigned", False)),
                            "exiting": bool(getattr(a, "exiting", False)),
                            "nearest_fire": nfd})
                # a dispatch = target_pos going from empty to set, measured at that step
                if tgt and not prev_target.get(uid) and pos is not None:
                    dispatches.append({"step": step, "id": uid, "from": pos, "to": tgt,
                                       "manhattan": abs(pos[0] - tgt[0]) + abs(pos[1] - tgt[1])})
                prev_target[uid] = tgt
            rows.append({
                "step": step,
                "uavs": [{"id": u["id"], "x": u["x"], "y": u["y"]} for u in frame["uavs"]],
                "victims": [{"id": v["id"], "x": v["x"], "y": v["y"], "flee": v["flee"]}
                            for v in frame["victims"]],
                "ffs": ffs,
                "n_burning": len(burning),
                "depot_ground": depot_ground,
            })
    json.dump({"seed": seed, "wind": wind, "steps": steps, "params": P, "depots": depots,
               "width": int(getattr(cfv, "WIDTH", 50)), "height": int(getattr(cfv, "HEIGHT", 50)),
               "base_station_mode": int(getattr(cfv, "BASE_STATION_MODE", -1)),
               "fov_radius": int(getattr(cfv, "UAV_OBSERVATION_RADIUS", 8)),
               "victim_flee_radius": int(am.victim_flee_trigger_distance()),
               "idle_buffer": int(am.IDLE_RETREAT_SAFETY_BUFFER),
               "engaged_retreat_range": int(am.ff_firefight_engaged_retreat_range()),
               "ff_extinguish": bool(am.ff_firefight_extinguish()),
               "ff_firebreak": bool(am.ff_firefight_firebreak()),
               "rows": rows, "dispatches": dispatches}, open(out, "w"))
    print("seed=%d wind=%s steps=%d depots=%s dispatches=%d wrote %s"
          % (seed, wind, steps, depots, len(dispatches), out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
