"""Profile tracker hazard cache performance and record trajectory snapshot."""

from __future__ import annotations

import contextlib
import io
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from serve_dashboard import _build_evaluation
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.execution import uav_executor as ue_module
from wildfire_model import WildFireModel


def _setup(seed: int = 42, wind: str = "south") -> dict:
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
    return params


def _tracker_positions(model: WildFireModel) -> dict[str, tuple[int, int] | None]:
    out: dict[str, tuple[int, int] | None] = {}
    for uid, _st in model.managed_uav_states.items():
        if model._uav_assignment_role(uid) != "fire_tracker":
            continue
        agent = next(
            (a for a in model.schedule.agents if str(a.unique_id) == uid), None
        )
        if agent is None or agent.pos is None:
            out[uid] = None
        else:
            out[uid] = (int(agent.pos[0]), int(agent.pos[1]))
    return out


def run_trajectory(steps: int = 120, *, seed: int = 42, wind: str = "south") -> dict:
    params = _setup(seed, wind)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        positions_by_step: dict[int, dict[str, tuple[int, int] | None]] = {}
        for step in range(1, steps + 1):
            model.step()
            positions_by_step[step] = _tracker_positions(model)
        ev = _build_evaluation(model, None, steps, params)
    return {
        "positions_end": positions_by_step[steps],
        "positions_by_step": positions_by_step,
        "rescued": ev["rescued"],
        "dead": ev["dead"],
        "ff_deaths": ev["firefighter_deaths"],
    }


def profile_mid_fire(num_steps: int = 12, *, start: int = 60, seed: int = 42) -> dict:
    params = _setup(seed, "south")
    counts = {
        "collect_hazard": 0,
        "build_hazard": 0,
        "cell_has_active_smoke": 0,
        "cell_agents": 0,
    }
    orig_collect = ue_module.UAVExecutor._collect_tracker_hazard_cells
    orig_build = ue_module.UAVExecutor._build_tracker_hazard_cache
    orig_smoke = ue_module.UAVExecutor._cell_has_active_smoke
    orig_agents = ue_module.UAVExecutor._cell_agents

    def wrap_collect(self, model=None):
        counts["collect_hazard"] += 1
        return orig_collect(self, model)

    def wrap_build(self, model=None):
        counts["build_hazard"] += 1
        return orig_build(self, model)

    def wrap_smoke(self, cell):
        counts["cell_has_active_smoke"] += 1
        return orig_smoke(self, cell)

    def wrap_agents(self, cell):
        counts["cell_agents"] += 1
        return orig_agents(self, cell)

    ue_module.UAVExecutor._collect_tracker_hazard_cells = wrap_collect
    ue_module.UAVExecutor._build_tracker_hazard_cache = wrap_build
    ue_module.UAVExecutor._cell_has_active_smoke = wrap_smoke
    ue_module.UAVExecutor._cell_agents = wrap_agents

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            model = WildFireModel()
            model.debug_log = False
            for _ in range(start):
                model.step()
            t0 = time.perf_counter()
            for _ in range(num_steps):
                model.step()
            elapsed = time.perf_counter() - t0
    finally:
        ue_module.UAVExecutor._collect_tracker_hazard_cells = orig_collect
        ue_module.UAVExecutor._build_tracker_hazard_cache = orig_build
        ue_module.UAVExecutor._cell_has_active_smoke = orig_smoke
        ue_module.UAVExecutor._cell_agents = orig_agents

    return {
        "seconds_per_step": elapsed / num_steps,
        "total_seconds": elapsed,
        **counts,
    }


if __name__ == "__main__":
    traj = run_trajectory(120)
    prof = profile_mid_fire(12, start=60)
    print("TRAJECTORY seed=42 south 120 steps")
    print("  end_positions", traj["positions_end"])
    print("  rescued", traj["rescued"], "dead", traj["dead"], "ff", traj["ff_deaths"])
    print("PROFILE 12 mid-fire steps (from step 60)")
    print("  sec/step", round(prof["seconds_per_step"], 3))
    print("  _collect_tracker_hazard_cells calls", prof["collect_hazard"])
    print("  _build_tracker_hazard_cache calls", prof["build_hazard"])
    print("  _cell_has_active_smoke calls", prof["cell_has_active_smoke"])
    print("  _cell_agents calls", prof["cell_agents"])
