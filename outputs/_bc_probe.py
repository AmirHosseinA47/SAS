"""Defect #9 (charred cells treated as safe) - Part 2 quantification. Read-only.

Measures, per run:
  - burnt fraction of the 50x50 grid at steps 60/120/180/240
  - firefighter occupancy of burnt vs unburnt cells (standing + moves-onto)
  - UAV observation effort spent on burnt cells (radius-8 Moore footprint)
  - full per-step firefighter neighbour classification, for death post-mortems
Emits one JSON per run. Does not perturb the simulation: observation only.
"""
from __future__ import annotations
import argparse
import contextlib
import io as _io
import json
import os
import random
import sys

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation, _resolve_role_count_params

SNAPSHOTS = (60, 120, 180, 240)
NB4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def build(seed, scenario, wind, ft, vs):
    preset = BUILTIN_SCENARIOS[scenario]
    fire_trackers, victim_searchers = _resolve_role_count_params(
        preset["NUM_AGENTS"], ft, vs)
    params = {
        "NUM_AGENTS": preset["NUM_AGENTS"],
        "NUM_VICTIMS": preset["NUM_VICTIMS"],
        "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"],
        "WIND_DIRECTION": wind,
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": fire_trackers,
        "NUM_VICTIM_SEARCHERS": victim_searchers,
    }
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
    return m, params


def run(seed, scenario, wind, ft, vs, steps):
    model, params = build(seed, scenario, wind, ft, vs)

    fires = {}
    for a in model.schedule.agents:
        if type(a) is am.Fire and getattr(a, "pos", None) is not None:
            fires[(int(a.pos[0]), int(a.pos[1]))] = a
    total_cells = len(fires)

    snap = {}
    ff_steps = {}
    ff_prev_pos = {}
    ff_prev_dead = {}
    deaths = []
    uav_obs_total = 0
    uav_obs_burnt = 0
    uav_obs_scorched = 0
    uav_obs_burning = 0
    ff_stand_burnt = 0
    ff_stand_scorched = 0
    ff_stand_total = 0
    ff_move_onto_burnt = 0
    ff_moves_total = 0
    burnt_nb_available = 0
    burnt_nb_taken = 0
    terminal_step = None

    for step_i in range(1, steps + 1):
        with contextlib.redirect_stdout(_io.StringIO()):
            model.step()
        if terminal_step is None:
            panel = model.get_dashboard_state()
            mission = panel.get("mission_status", {}) or {}
            if mission.get("all_victims_terminal"):
                terminal_step = step_i

        burnt = {c for c, a in fires.items() if getattr(a, "burnt", False)}
        burning = {c for c, a in fires.items() if a.is_burning()}
        # Rendered charred (main.py:77, serve_dashboard.py:63 use
        # "is_burnt() or has_burned") but NOT burnt: fuel remains, so
        # probability_of_fire() is still live and the cell can re-ignite.
        scorched = {c for c, a in fires.items()
                    if getattr(a, "has_burned", False)
                    and not getattr(a, "burnt", False)
                    and not a.is_burning()}

        if step_i in SNAPSHOTS:
            snap[step_i] = {"burnt": len(burnt), "burning": len(burning),
                            "scorched": len(scorched), "total": total_cells}

        # --- UAV observation footprint (radius-8 Moore, include_center) ---
        for a in model.schedule.agents:
            if type(a) is not am.UAV or getattr(a, "pos", None) is None:
                continue
            for cell in model.grid.get_neighborhood(
                    a.pos, moore=True, include_center=True,
                    radius=cfv.UAV_OBSERVATION_RADIUS):
                if cell in fires:
                    uav_obs_total += 1
                    if cell in burnt:
                        uav_obs_burnt += 1
                    elif cell in scorched:
                        uav_obs_scorched += 1
                    elif cell in burning:
                        uav_obs_burning += 1

        # --- firefighter occupancy + neighbour classification ---
        for uid, ff in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
            uid = str(uid)
            dead = bool(getattr(ff, "dead", False)) or \
                str(getattr(ff, "status", "")).lower() == "dead"
            pos = getattr(ff, "pos", None)
            cell = (int(pos[0]), int(pos[1])) if pos is not None else None

            if not ff_prev_dead.get(uid, False) and dead:
                deaths.append({"unit": uid, "step": step_i, "cell": cell,
                               "cell_was_scorched": cell in scorched,
                               "cell_was_burnt": cell in burnt})
            ff_prev_dead[uid] = dead

            if dead or cell is None:
                continue

            nb = []
            for ox, oy in NB4:
                n = (cell[0] + ox, cell[1] + oy)
                if n not in fires:
                    continue
                nb.append({"cell": list(n),
                           "burning": n in burning,
                           "burnt": n in burnt,
                           "scorched": n in scorched})
            rec = {"step": step_i, "cell": list(cell),
                   "on_burnt": cell in burnt, "on_burning": cell in burning,
                   "on_scorched": cell in scorched,
                   "status": str(getattr(ff, "status", "")),
                   "assigned": bool(getattr(ff, "assigned", False)),
                   "exiting": bool(getattr(ff, "exiting", False)),
                   "nb": nb}
            ff_steps.setdefault(uid, []).append(rec)

            ff_stand_total += 1
            if cell in burnt:
                ff_stand_burnt += 1
            if cell in scorched:
                ff_stand_scorched += 1

            prev = ff_prev_pos.get(uid)
            if prev is not None and prev != cell:
                ff_moves_total += 1
                if cell in burnt:
                    ff_move_onto_burnt += 1
            avail = [n for n in nb if n["burnt"] and not n["burning"]]
            if avail:
                burnt_nb_available += 1
                if prev is not None and prev != cell and cell in burnt:
                    burnt_nb_taken += 1
            ff_prev_pos[uid] = cell

    ev = _build_evaluation(model, terminal_step, steps, params)
    return {
        "seed": seed, "scenario": scenario, "wind": wind,
        "roles": ("half" if ft is not None else "default"),
        "snapshots": snap, "total_cells": total_cells,
        "eval": {k: ev.get(k) for k in
                 ("rescued", "dead", "unreachable", "firefighter_deaths",
                  "burnt_cells", "rescue_rate", "terminal_step")},
        "uav": {"obs_total": uav_obs_total, "obs_burnt": uav_obs_burnt, "obs_scorched": uav_obs_scorched,
                "obs_burning": uav_obs_burning},
        "ff": {"stand_total": ff_stand_total, "stand_burnt": ff_stand_burnt, "stand_scorched": ff_stand_scorched,
               "moves_total": ff_moves_total, "move_onto_burnt": ff_move_onto_burnt,
               "burnt_nb_available": burnt_nb_available,
               "burnt_nb_taken": burnt_nb_taken},
        "deaths": deaths,
        "ff_trace": ff_steps,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--scenario", default="D")
    p.add_argument("--wind", default="east")
    p.add_argument("--fire-trackers", type=int, default=None, dest="ft")
    p.add_argument("--victim-searchers", type=int, default=None, dest="vs")
    p.add_argument("--steps", type=int, default=240)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    res = run(a.seed, a.scenario, a.wind, a.ft, a.vs, a.steps)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh)
    e = res["eval"]
    s = res["snapshots"]
    print("seed=%-5d %s/%s/%-7s ff_deaths=%d burnt=%d rescued=%d | "
          "burnt@60/120/180/240=%s | ff_on_burnt=%d/%d uav_burnt=%d/%d"
          % (a.seed, a.scenario, a.wind, res["roles"], e["firefighter_deaths"],
             e["burnt_cells"], e["rescued"],
             "/".join(str(s.get(k, {}).get("burnt", "-")) for k in SNAPSHOTS),
             res["ff"]["stand_burnt"], res["ff"]["stand_total"],
             res["uav"]["obs_burnt"], res["uav"]["obs_total"]))
