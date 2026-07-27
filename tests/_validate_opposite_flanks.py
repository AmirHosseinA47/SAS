"""Validate opposite-flank fire_tracker assignment across winds."""

from __future__ import annotations

import contextlib
import io
import os
import random
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


def _active_fire(model: WildFireModel) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for agent in model.schedule.agents:
        if type(agent).__name__ != "Fire":
            continue
        if getattr(agent, "is_burning", lambda: False)():
            cells.add((int(agent.pos[0]), int(agent.pos[1])))
    return cells


def _tracker_ids(model: WildFireModel) -> list[str]:
    return sorted(
        uid
        for uid in model.managed_uav_states
        if model._uav_assignment_role(uid) == "fire_tracker"
    )


def _side_label(
    pos: tuple[int, int],
    centroid: tuple[float, float],
    axis: str,
) -> str:
    if axis == "x":
        return "west" if pos[0] < centroid[0] else "east"
    if axis == "y":
        return "south" if pos[1] < centroid[1] else "north"
    return "full"


def _split_axis(model: WildFireModel, tracker_ids: list[str]) -> str:
    if not tracker_ids:
        return "none"
    bounds = model._uav_sector_assignments.get(tracker_ids[0], {})
    return str(bounds.get("split_axis", "y"))


def _position_in_bounds(
    pos: tuple[int, int],
    bounds: dict[str, int],
) -> bool:
    x, y = pos
    return (
        bounds["x_min"] <= x <= bounds["x_max"]
        and bounds["y_min"] <= y <= bounds["y_max"]
    )


def _half_label(
    pos: tuple[int, int],
    bounds: dict[str, int],
    axis: str,
) -> str:
    if axis == "x":
        mid = (bounds["x_min"] + bounds["x_max"]) / 2.0
        return "low" if pos[0] <= mid else "high"
    if axis == "y":
        mid = (bounds["y_min"] + bounds["y_max"]) / 2.0
        return "low" if pos[1] <= mid else "high"
    return "full"


def _tracker_bounds(model: WildFireModel, uid: str) -> dict:
    return dict(model._uav_sector_assignments.get(uid, {}))


def run_wind(
    wind: str,
    *,
    seed: int = 42,
    steps: int = 150,
    **extra,
) -> dict:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    am.random = rng
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
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        ft_ids = _tracker_ids(model)
        smoke = {uid: 0 for uid in ft_ids}
        fire_steps = {uid: 0 for uid in ft_ids}
        snapshots: dict[int, dict] = {}
        for step in range(1, steps + 1):
            model.step()
            active = _active_fire(model)
            if step in (50, 100, 150) and active:
                snap: dict = {"trackers": {}}
                all_bounds = [_tracker_bounds(model, uid) for uid in ft_ids]
                x_min = min(b.get("x_min", 0) for b in all_bounds)
                x_max = max(b.get("x_max", 0) for b in all_bounds)
                y_min = min(b.get("y_min", 0) for b in all_bounds)
                y_max = max(b.get("y_max", 0) for b in all_bounds)
                axis = str(all_bounds[0].get("split_axis", "none")) if all_bounds else "none"
                fire_bbox = {
                    "x_min": x_min,
                    "x_max": x_max,
                    "y_min": y_min,
                    "y_max": y_max,
                }
                halves: list[str] = []
                for uid in ft_ids:
                    agent = next(
                        (a for a in model.schedule.agents if str(a.unique_id) == uid),
                        None,
                    )
                    if agent is None or agent.pos is None:
                        continue
                    x, y = int(agent.pos[0]), int(agent.pos[1])
                    bounds = _tracker_bounds(model, uid)
                    nearest = min(abs(x - fx) + abs(y - fy) for fx, fy in active)
                    half = _half_label((x, y), fire_bbox, axis) if axis in ("x", "y") else "full"
                    snap["trackers"][uid] = {
                        "pos": (x, y),
                        "axis": axis,
                        "half": half,
                        "flank_index": bounds.get("flank_index"),
                        "in_band": _position_in_bounds((x, y), bounds),
                        "nearest_fire": nearest,
                    }
                    if axis in ("x", "y"):
                        halves.append(half)
                snap["axis"] = snap["trackers"][ft_ids[0]]["axis"] if ft_ids else "none"
                if len(halves) >= 2:
                    in_bands = [
                        snap["trackers"][uid]["in_band"]
                        for uid in ft_ids
                        if uid in snap["trackers"]
                    ]
                    snap["opposite"] = (
                        len(in_bands) >= 2
                        and all(in_bands)
                        and halves[0] != halves[1]
                    )
                else:
                    snap["opposite"] = True
                snapshots[step] = snap
            for uid in ft_ids:
                agent = next(
                    (a for a in model.schedule.agents if str(a.unique_id) == uid), None
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
        ev = _build_evaluation(model, None, steps, params)
    return {
        "wind": wind,
        "snapshots": snapshots,
        "smoke": smoke,
        "fire": fire_steps,
        "rescued": ev["rescued"],
        "dead": ev["dead"],
        "ff_deaths": ev["firefighter_deaths"],
    }


if __name__ == "__main__":
    for wind in ("east", "west", "north", "south"):
        r = run_wind(wind)
        print(f"=== {wind} ===")
        for step in (50, 100, 150):
            s = r["snapshots"].get(step)
            print(f"  step {step}: {s}")
        print(
            f"  smoke={r['smoke']} fire={r['fire']} "
            f"resc={r['rescued']} dead={r['dead']} ff={r['ff_deaths']}"
        )
    extra = run_wind(
        "west",
        seed=42,
        steps=150,
        NUM_AGENTS=3,
        NUM_FIRE_TRACKERS=2,
        NUM_VICTIM_SEARCHERS=1,
    )
    print("=== 2FT+1VS west ===")
    for step in (50, 100, 150):
        print(f"  step {step}: {extra['snapshots'].get(step)}")
    print(
        f"  smoke={extra['smoke']} resc={extra['rescued']} "
        f"dead={extra['dead']} ff={extra['ff_deaths']}"
    )
