"""Defect #9 Part 2b: decision-level post-mortem. Read-only, observation only.

Tests the specific lethal-chain claim: a retreating/held firefighter refuses a
permanently-safe BURNT neighbour because that cell is fire-adjacent or smoky
(_cell_meets_required_idle_safety agents.py:727-736,
 _assigned_one_step_retreat agents.py:1014-1020), holds position, and the front
then arrives on its own cell (wildfire_model.py:4118/4139).

For every alive-firefighter step it records each von-Neumann neighbour under
exactly the predicates the retreat code uses, plus whether the unit moved.
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

NB4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def build(seed, scenario, wind, ft, vs):
    preset = BUILTIN_SCENARIOS[scenario]
    fire_trackers, victim_searchers = _resolve_role_count_params(
        preset["NUM_AGENTS"], ft, vs)
    params = {
        "NUM_AGENTS": preset["NUM_AGENTS"],
        "NUM_VICTIMS": preset["NUM_VICTIMS"],
        "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"],
        "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": fire_trackers, "NUM_VICTIM_SEARCHERS": victim_searchers,
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

    trace = {}
    deaths = []
    prev_pos = {}
    prev_dead = {}
    terminal_step = None

    for step_i in range(1, steps + 1):
        with contextlib.redirect_stdout(_io.StringIO()):
            model.step()
        if terminal_step is None:
            mission = (model.get_dashboard_state().get("mission_status", {}) or {})
            if mission.get("all_victims_terminal"):
                terminal_step = step_i

        burning = {c for c, a in fires.items() if a.is_burning()}
        burnt = {c for c, a in fires.items() if getattr(a, "burnt", False)}
        scorched = {c for c, a in fires.items()
                    if getattr(a, "has_burned", False)
                    and not getattr(a, "burnt", False) and not a.is_burning()}
        smoky = {c for c, a in fires.items()
                 if getattr(getattr(a, "smoke", None), "is_smoke_active", lambda: False)()}

        def adj_fire(c):
            return any((c[0] + ox, c[1] + oy) in burning for ox, oy in NB4)

        for uid, ff in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
            uid = str(uid)
            dead = bool(getattr(ff, "dead", False)) or \
                str(getattr(ff, "status", "")).lower() == "dead"
            pos = getattr(ff, "pos", None)
            cell = (int(pos[0]), int(pos[1])) if pos is not None else None
            if not prev_dead.get(uid, False) and dead:
                deaths.append({"unit": uid, "step": step_i, "cell": cell})
            prev_dead[uid] = dead
            if dead or cell is None:
                continue
            nb = []
            for ox, oy in NB4:
                n = (cell[0] + ox, cell[1] + oy)
                if n not in fires:
                    continue
                nb.append({
                    "cell": list(n),
                    "burning": n in burning,
                    "burnt": n in burnt,
                    "scorched": n in scorched,
                    "smoky": n in smoky,
                    "adj_fire": adj_fire(n),
                })
            moved = prev_pos.get(uid) is not None and prev_pos[uid] != cell
            trace.setdefault(uid, []).append({
                "step": step_i, "cell": list(cell), "moved": moved,
                "on_burning": cell in burning, "on_burnt": cell in burnt,
                "on_smoky": cell in smoky,
                "status": str(getattr(ff, "status", "")),
                "assigned": bool(getattr(ff, "assigned", False)),
                "exiting": bool(getattr(ff, "exiting", False)),
                "stalled": bool(getattr(ff, "_idle_retreat_stalled", False)),
                "nb": nb,
            })
            prev_pos[uid] = cell

    ev = _build_evaluation(model, terminal_step, steps, params)
    return {"seed": seed, "wind": wind,
            "roles": ("half" if ft is not None else "default"),
            "eval": {k: ev.get(k) for k in
                     ("firefighter_deaths", "rescued", "burnt_cells")},
            "deaths": deaths, "trace": trace}


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
    print("seed=%-5d %s deaths=%d" % (a.seed, a.wind, res["eval"]["firefighter_deaths"]))
