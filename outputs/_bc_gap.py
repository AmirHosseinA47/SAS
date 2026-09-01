"""Defect #9: how far is the nearest BURNT cell when a firefighter needs one?

A cell burns for FUEL(7..10) ticks at one tick per FIRE_SPREAD_SPEED=3 steps,
i.e. 21-30 model steps, while the front keeps advancing. So "the black" is
always well behind the flame. This measures the resulting standoff gap:
per firefighter step, Manhattan distance to the nearest BURNING cell and to
the nearest BURNT cell. Read-only.
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
from serve_dashboard import BUILTIN_SCENARIOS, _resolve_role_count_params


def build(seed, wind, ft, vs):
    preset = BUILTIN_SCENARIOS["D"]
    fire_trackers, victim_searchers = _resolve_role_count_params(
        preset["NUM_AGENTS"], ft, vs)
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(
        cfv, wf, NUM_AGENTS=preset["NUM_AGENTS"], NUM_VICTIMS=preset["NUM_VICTIMS"],
        NUM_FIREFIGHTERS=preset["NUM_FIREFIGHTERS"], WIND_DIRECTION=wind,
        BATCH_SIZE=300, FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
        NUM_FIRE_TRACKERS=fire_trackers, NUM_VICTIM_SEARCHERS=victim_searchers)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
    return m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--wind", default="east")
    p.add_argument("--roles", default="half")
    p.add_argument("--steps", type=int, default=240)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    ft, vs = (2, 2) if a.roles == "half" else (None, None)
    m = build(a.seed, a.wind, ft, vs)
    fires = {}
    for ag in m.schedule.agents:
        if type(ag) is am.Fire and getattr(ag, "pos", None) is not None:
            fires[(int(ag.pos[0]), int(ag.pos[1]))] = ag

    recs = []
    prev_dead = {}
    deaths = []
    for step_i in range(1, a.steps + 1):
        with contextlib.redirect_stdout(_io.StringIO()):
            m.step()
        burning = [c for c, ag in fires.items() if ag.is_burning()]
        burnt = [c for c, ag in fires.items() if getattr(ag, "burnt", False)]
        if not burning:
            continue
        for uid, ff in (getattr(m, "firefighter_marker_agents", {}) or {}).items():
            uid = str(uid)
            dead = bool(getattr(ff, "dead", False)) or \
                str(getattr(ff, "status", "")).lower() == "dead"
            pos = getattr(ff, "pos", None)
            if not prev_dead.get(uid, False) and dead and pos is not None:
                deaths.append({"unit": uid, "step": step_i})
            prev_dead[uid] = dead
            if dead or pos is None:
                continue
            cx, cy = int(pos[0]), int(pos[1])
            d_fire = min(abs(cx - x) + abs(cy - y) for x, y in burning)
            d_burnt = (min(abs(cx - x) + abs(cy - y) for x, y in burnt)
                       if burnt else None)
            recs.append({"step": step_i, "unit": uid, "d_fire": d_fire,
                         "d_burnt": d_burnt})
    json.dump({"seed": a.seed, "wind": a.wind, "roles": a.roles,
               "recs": recs, "deaths": deaths},
              open(a.out, "w", encoding="utf-8"))
    near = [r for r in recs if r["d_fire"] <= 2 and r["d_burnt"] is not None]
    if near:
        print("seed=%-5d %s/%-7s  steps with fire within 2: %4d | "
              "mean d_burnt %.1f | d_burnt<=1 in %d of them"
              % (a.seed, a.wind, a.roles, len(near),
                 sum(r["d_burnt"] for r in near) / len(near),
                 sum(1 for r in near if r["d_burnt"] <= 1)))
    else:
        print("seed=%-5d %s/%-7s  no steps with fire within 2" % (a.seed, a.wind, a.roles))


if __name__ == "__main__":
    main()
