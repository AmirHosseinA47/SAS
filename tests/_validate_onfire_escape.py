"""Validate fire_tracker on-fire step counts across random seeds."""

from __future__ import annotations

import contextlib
import io
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from serve_dashboard import _build_evaluation
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

SEEDS = [42, 101, 202, 303, 404]
STEPS = 150
CHECKPOINTS = (50, 100, 150)


def _tracker_ids(model: WildFireModel) -> list[str]:
    return sorted(
        uid
        for uid in model.managed_uav_states
        if model._uav_assignment_role(uid) == "fire_tracker"
    )


def _position_in_bounds(pos: tuple[int, int], bounds: dict) -> bool:
    x, y = pos
    return (
        bounds["x_min"] <= x <= bounds["x_max"]
        and bounds["y_min"] <= y <= bounds["y_max"]
    )


def _half_label(pos: tuple[int, int], bbox: dict, axis: str) -> str:
    if axis == "x":
        mid = (bbox["x_min"] + bbox["x_max"]) / 2.0
        return "low" if pos[0] <= mid else "high"
    if axis == "y":
        mid = (bbox["y_min"] + bbox["y_max"]) / 2.0
        return "low" if pos[1] <= mid else "high"
    return "full"


def _opposite_at_step(model: WildFireModel, ft_ids: list[str]) -> bool:
    all_bounds = [
        dict(model._uav_sector_assignments.get(uid, {})) for uid in ft_ids
    ]
    if len(all_bounds) < 2:
        return True
    axis = str(all_bounds[0].get("split_axis", "none"))
    if axis not in ("x", "y"):
        return True
    bbox = {
        "x_min": min(b.get("x_min", 0) for b in all_bounds),
        "x_max": max(b.get("x_max", 0) for b in all_bounds),
        "y_min": min(b.get("y_min", 0) for b in all_bounds),
        "y_max": max(b.get("y_max", 0) for b in all_bounds),
    }
    halves: list[str] = []
    in_bands = True
    for uid in ft_ids:
        agent = next(
            (a for a in model.schedule.agents if str(a.unique_id) == uid), None
        )
        if agent is None or agent.pos is None:
            return False
        pos = (int(agent.pos[0]), int(agent.pos[1]))
        bounds = dict(model._uav_sector_assignments.get(uid, {}))
        if not _position_in_bounds(pos, bounds):
            in_bands = False
        halves.append(_half_label(pos, bbox, axis))
    return in_bands and len(halves) >= 2 and halves[0] != halves[1]


def run_seed(wind: str, seed: int) -> dict:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    am.random = rng
    params = dict(
        NUM_AGENTS=3,
        NUM_VICTIMS=5,
        NUM_FIREFIGHTERS=3,
        WIND_DIRECTION=wind,
        BATCH_SIZE=300,
        FIRE_SPREAD_MULTIPLIER=0.75,
        PROBABILITY_MAP=False,
    )
    apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        ft_ids = _tracker_ids(model)
        smoke = {uid: 0 for uid in ft_ids}
        fire_steps = {uid: 0 for uid in ft_ids}
        nearest_samples: dict[str, list[int]] = {uid: [] for uid in ft_ids}
        opposite_ok = {step: True for step in CHECKPOINTS}
        for step in range(1, STEPS + 1):
            model.step()
            if step in CHECKPOINTS:
                opposite_ok[step] = _opposite_at_step(model, ft_ids)
            active: set[tuple[int, int]] = set()
            for agent in model.schedule.agents:
                if type(agent).__name__ != "Fire":
                    continue
                if getattr(agent, "is_burning", lambda: False)():
                    active.add((int(agent.pos[0]), int(agent.pos[1])))
            for uid in ft_ids:
                agent = next(
                    (a for a in model.schedule.agents if str(a.unique_id) == uid),
                    None,
                )
                if agent is None or agent.pos is None:
                    continue
                x, y = int(agent.pos[0]), int(agent.pos[1])
                vis = getattr(model, "visibility_model", None)
                sm = getattr(vis, "smoke_obscured_cells", None) if vis else None
                if isinstance(sm, (set, list, tuple)) and (x, y) in sm:
                    smoke[uid] += 1
                for fa in model.schedule.agents:
                    if (
                        type(fa).__name__ == "Fire"
                        and fa.pos == (x, y)
                        and fa.is_burning()
                    ):
                        fire_steps[uid] += 1
                if active:
                    nearest_samples[uid].append(
                        min(abs(x - fx) + abs(y - fy) for fx, fy in active)
                    )
        ev = _build_evaluation(model, None, STEPS, params)
    return {
        "seed": seed,
        "fire": fire_steps,
        "smoke": smoke,
        "nearest_mean": {
            uid: statistics.mean(nearest_samples[uid]) if nearest_samples[uid] else 99
            for uid in ft_ids
        },
        "rescued": ev["rescued"],
        "dead": ev["dead"],
        "ff_deaths": ev["firefighter_deaths"],
        "opposite": opposite_ok,
    }


def summarize(wind: str) -> dict:
    rows = [run_seed(wind, seed) for seed in SEEDS]
    total_fire = sum(sum(r["fire"].values()) for r in rows)
    total_smoke = sum(sum(r["smoke"].values()) for r in rows)
    per_seed_fire = {r["seed"]: sum(r["fire"].values()) for r in rows}
    per_seed_smoke = {r["seed"]: sum(r["smoke"].values()) for r in rows}
    return {
        "wind": wind,
        "rows": rows,
        "per_seed_fire": per_seed_fire,
        "per_seed_smoke": per_seed_smoke,
        "mean_fire": total_fire / len(SEEDS),
        "mean_smoke": total_smoke / len(SEEDS),
        "mean_rescued": statistics.mean(r["rescued"] for r in rows),
        "mean_dead": statistics.mean(r["dead"] for r in rows),
        "mean_ff": statistics.mean(r["ff_deaths"] for r in rows),
        "opposite_all": all(
            all(r["opposite"].get(s, False) for s in CHECKPOINTS) for r in rows
        ),
    }


if __name__ == "__main__":
    for wind in ("east", "south"):
        s = summarize(wind)
        print(f"=== {wind} ===")
        print(f"  per-seed on-fire steps: {s['per_seed_fire']}")
        print(f"  per-seed smoke steps:   {s['per_seed_smoke']}")
        print(f"  MEAN on-fire: {s['mean_fire']:.1f}  smoke: {s['mean_smoke']:.1f}")
        print(
            f"  MEAN rescued={s['mean_rescued']:.1f} dead={s['mean_dead']:.1f} "
            f"ff={s['mean_ff']:.1f}"
        )
        for r in s["rows"]:
            print(f"    seed {r['seed']} nearest_mean: {r['nearest_mean']}")
        print(f"  opposite flanks all seeds/steps: {s['opposite_all']}")
