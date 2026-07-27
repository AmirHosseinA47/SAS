"""Fire tracker standoff + UAV role count validation."""

from __future__ import annotations

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from common_fixed_variables import euclidean_distance
from src_extension.adaptation.local_adaptation_generator import (
    apply_scenario_config,
    resolve_victim_searcher_uav_ids,
)
from wildfire_model import WildFireModel


def _active_fire_cells(model: WildFireModel) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for agent in model.schedule.agents:
        if type(agent).__name__ != "Fire":
            continue
        if getattr(agent, "is_burning", lambda: False)():
            cells.add((int(agent.pos[0]), int(agent.pos[1])))
    if not cells:
        cells = model._collect_fire_cells_for_sector_update()
    return cells


def run_scenario(wind: str, *, seed: int = 42, steps: int = 120, **extra) -> dict:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    params = dict(
        NUM_AGENTS=int(extra.pop("NUM_AGENTS", 3)),
        NUM_VICTIMS=5,
        NUM_FIREFIGHTERS=3,
        WIND_DIRECTION=wind,
        BATCH_SIZE=300,
        FIRE_SPREAD_MULTIPLIER=0.75,
        PROBABILITY_MAP=False,
        **extra,
    )
    apply_scenario_config(cfv, wf, **params)
    model = WildFireModel()
    model.debug_log = False
    ft_ids = sorted(
        uid
        for uid in model.managed_uav_states
        if model._uav_assignment_role(uid) == "fire_tracker"
    )
    vs_ids = resolve_victim_searcher_uav_ids(model)
    nearest: dict[str, dict[int, int | None]] = {
        uid: {30: None, 60: None, 90: None} for uid in ft_ids
    }
    smoke_steps = {uid: 0 for uid in ft_ids}
    fire_steps = {uid: 0 for uid in ft_ids}
    closest_v1 = float("inf")
    v1_detected = False

    for step in range(1, steps + 1):
        model.step()
        active = _active_fire_cells(model)
        for uid in ft_ids:
            agent = next(
                (a for a in model.schedule.agents if str(a.unique_id) == uid), None
            )
            if agent is None or getattr(agent, "pos", None) is None:
                continue
            x, y = int(agent.pos[0]), int(agent.pos[1])
            if step in (30, 60, 90) and active:
                nearest[uid][step] = min(
                    abs(x - fx) + abs(y - fy) for fx, fy in active
                )
            vis = getattr(model, "visibility_model", None)
            sm = getattr(vis, "smoke_obscured_cells", None) if vis else None
            if isinstance(sm, (set, list, tuple)) and (x, y) in sm:
                smoke_steps[uid] += 1
            for fa in model.schedule.agents:
                if (
                    type(fa).__name__ == "Fire"
                    and fa.pos == (x, y)
                    and fa.is_burning()
                ):
                    fire_steps[uid] += 1
        for uid in vs_ids:
            agent = next(
                (a for a in model.schedule.agents if str(a.unique_id) == uid), None
            )
            if agent is not None and getattr(agent, "pos", None) is not None:
                px, py = float(agent.pos[0]), float(agent.pos[1])
                closest_v1 = min(
                    closest_v1, euclidean_distance(px, py, 32.0, 46.0)
                )
        st = model.managed_victims.get("victim_1")
        if st is not None and str(getattr(st, "status", "")).lower() not in {
            "candidate",
            "unknown",
        }:
            v1_detected = True

    rescued = sum(
        1
        for st in model.managed_victims.values()
        if str(getattr(st, "status", "")).lower() == "rescued"
    )
    dead = sum(
        1
        for st in model.managed_victims.values()
        if str(getattr(st, "status", "")).lower() == "dead"
    )
    return {
        "wind": wind,
        "nearest": nearest,
        "smoke": smoke_steps,
        "fire": fire_steps,
        "closest_v1": closest_v1,
        "v1_detected": v1_detected,
        "rescued": rescued,
        "dead": dead,
    }


def check_roles(**extra) -> dict[str, str | None]:
    rng = random.Random(42)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv,
        wf,
        NUM_VICTIMS=5,
        NUM_FIREFIGHTERS=3,
        WIND_DIRECTION="east",
        BATCH_SIZE=300,
        FIRE_SPREAD_MULTIPLIER=0.75,
        PROBABILITY_MAP=False,
        **extra,
    )
    model = WildFireModel()
    model.step()
    return {
        uid: model._uav_assignment_role(uid) for uid in model.managed_uav_states
    }


if __name__ == "__main__":
    for wind in ("east", "south"):
        r = run_scenario(wind)
        print(f"=== {wind} ===")
        print("nearest_fire_dist", r["nearest"])
        print("smoke", r["smoke"], "fire", r["fire"])
        print(
            f"closest_v1={r['closest_v1']:.2f} v1={r['v1_detected']} "
            f"resc={r['rescued']} dead={r['dead']}"
        )
    print("roles 2FT+1VS", check_roles(NUM_AGENTS=3, NUM_FIRE_TRACKERS=2, NUM_VICTIM_SEARCHERS=1))
    print("roles 1FT+2VS", check_roles(NUM_AGENTS=3, NUM_FIRE_TRACKERS=1, NUM_VICTIM_SEARCHERS=2))
