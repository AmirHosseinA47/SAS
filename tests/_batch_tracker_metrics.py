"""Compact batch tracker + rescue metrics (stdout CSV)."""

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
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import _build_evaluation


def run_once(wind: str, seed: int, steps: int = 300) -> dict:
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
        ft_ids = sorted(
            uid
            for uid in model.managed_uav_states
            if model._uav_assignment_role(uid) == "fire_tracker"
        )
        smoke = {uid: 0 for uid in ft_ids}
        fire = {uid: 0 for uid in ft_ids}
        for _ in range(steps):
            model.step()
            for uid in ft_ids:
                agent = next(
                    (a for a in model.schedule.agents if str(a.unique_id) == uid),
                    None,
                )
                if agent is None or getattr(agent, "pos", None) is None:
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
                        fire[uid] += 1
        ev = _build_evaluation(model, None, steps, params)
    return {
        "seed": seed,
        "wind": wind,
        "smoke": smoke,
        "fire": fire,
        "smoke_total": sum(smoke.values()),
        "fire_total": sum(fire.values()),
        "rescued": ev["rescued"],
        "dead": ev["dead"],
        "ff_deaths": ev["firefighter_deaths"],
    }


def ms(values: list[float]) -> str:
    if not values:
        return "n/a"
    if len(values) == 1:
        return f"{values[0]:.2f} +/- 0.00"
    return f"{statistics.mean(values):.2f} +/- {statistics.stdev(values):.2f}"


if __name__ == "__main__":
    wind = sys.argv[1] if len(sys.argv) > 1 else "east"
    seeds = [42] + [1001 + i for i in range(10)]
    rows = [run_once(wind, s) for s in seeds]
    random_rows = [r for r in rows if r["seed"] != 42]
    fixed = next(r for r in rows if r["seed"] == 42)
    print(f"WIND={wind}")
    print(f"seed42 smoke={fixed['smoke']} fire={fixed['fire']} "
          f"resc={fixed['rescued']} dead={fixed['dead']} ff={fixed['ff_deaths']}")
    print(f"smoke_total {ms([float(r['smoke_total']) for r in random_rows])}")
    print(f"fire_total {ms([float(r['fire_total']) for r in random_rows])}")
    print(f"ff_deaths {ms([float(r['ff_deaths']) for r in random_rows])}")
    print(f"rescued {ms([float(r['rescued']) for r in random_rows])}")
    print(f"dead {ms([float(r['dead']) for r in random_rows])}")
