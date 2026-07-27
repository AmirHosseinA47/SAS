"""Validate victim_searcher grid coverage and victim detection."""

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
from common_fixed_variables import UAV_OBSERVATION_RADIUS
from serve_dashboard import _build_evaluation
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

SEEDS = [42, 101, 202, 303, 404]
STEPS = 300


def _searcher_id(model: WildFireModel) -> str | None:
    for uid in model.managed_uav_states:
        if model._uav_assignment_role(uid) == "victim_searcher":
            return str(uid)
    return None


def _victim_positions(model: WildFireModel) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    markers = getattr(model, "victim_marker_agents", {}) or {}
    for vid, marker in markers.items():
        pos = getattr(marker, "pos", None)
        if pos is not None:
            out[str(vid)] = (int(pos[0]), int(pos[1]))
    return out


def _is_detected(model: WildFireModel, vid: str) -> bool:
    runtime = getattr(model, "victim_runtime_model", None)
    if runtime is not None and vid in getattr(runtime, "victims", {}):
        return True
    managed = getattr(model, "managed_victims", {}).get(vid)
    if managed is not None and getattr(managed, "confirmed", False):
        return True
    return False


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
        vs_id = _searcher_id(model)
        victims = _victim_positions(model)
        closest: dict[str, float] = {vid: float("inf") for vid in victims}
        xs: list[int] = []
        ys: list[int] = []
        smoke = fire_steps = 0
        for _ in range(STEPS):
            model.step()
            if vs_id is None:
                continue
            agent = next(
                (a for a in model.schedule.agents if str(a.unique_id) == vs_id), None
            )
            if agent is None or agent.pos is None:
                continue
            x, y = int(agent.pos[0]), int(agent.pos[1])
            xs.append(x)
            ys.append(y)
            vis = getattr(model, "visibility_model", None)
            sm = getattr(vis, "smoke_obscured_cells", None) if vis else None
            if isinstance(sm, (set, list, tuple)) and (x, y) in sm:
                smoke += 1
            for fa in model.schedule.agents:
                if (
                    type(fa).__name__ == "Fire"
                    and fa.pos == (x, y)
                    and fa.is_burning()
                ):
                    fire_steps += 1
            for vid, (vx, vy) in victims.items():
                dist = ((x - vx) ** 2 + (y - vy) ** 2) ** 0.5
                closest[vid] = min(closest[vid], dist)
        ev = _build_evaluation(model, None, STEPS, params)
        undetected = [vid for vid in victims if not _is_detected(model, vid)]
    return {
        "seed": seed,
        "x_range": (min(xs), max(xs)) if xs else (None, None),
        "y_range": (min(ys), max(ys)) if ys else (None, None),
        "closest": {k: round(v, 1) for k, v in closest.items()},
        "undetected": undetected,
        "undetected_count": len(undetected),
        "smoke": smoke,
        "fire": fire_steps,
        "rescued": ev["rescued"],
        "dead": ev["dead"],
        "ff_deaths": ev["firefighter_deaths"],
    }


def summarize(wind: str) -> dict:
    rows = [run_seed(wind, seed) for seed in SEEDS]
    return {
        "wind": wind,
        "rows": rows,
        "mean_undetected": statistics.mean(r["undetected_count"] for r in rows),
        "mean_rescued": statistics.mean(r["rescued"] for r in rows),
        "mean_dead": statistics.mean(r["dead"] for r in rows),
        "mean_ff": statistics.mean(r["ff_deaths"] for r in rows),
        "mean_smoke": statistics.mean(r["smoke"] for r in rows),
        "mean_fire": statistics.mean(r["fire"] for r in rows),
    }


if __name__ == "__main__":
    for wind in ("east", "south"):
        s = summarize(wind)
        print(f"=== {wind} ===")
        for r in s["rows"]:
            print(
                f"  seed {r['seed']}: x={r['x_range']} y={r['y_range']} "
                f"undet={r['undetected_count']} {r['undetected']} "
                f"closest={r['closest']} smoke={r['smoke']} fire={r['fire']} "
                f"resc={r['rescued']} dead={r['dead']} ff={r['ff_deaths']}"
            )
        print(
            f"  MEAN undetected={s['mean_undetected']:.1f} "
            f"resc={s['mean_rescued']:.1f} dead={s['mean_dead']:.1f} "
            f"ff={s['mean_ff']:.1f} smoke={s['mean_smoke']:.1f}"
        )
    r42 = run_seed("east", 42)
    v3 = r42["closest"].get("victim_3", 999)
    print(f"east seed=42 victim_3 closest={v3} detected={v3 <= UAV_OBSERVATION_RADIUS}")
