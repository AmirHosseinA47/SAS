"""Committed vertical sweep: victim_searcher must penetrate far north/south halves."""

from __future__ import annotations

import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import common_fixed_variables as cfv
import wildfire_model as wf
from common_fixed_variables import wind_vector_from_direction
from src_extension.adaptation.local_adaptation_generator import (
    COVERAGE_Y_COMMIT_PENETRATE_MARGIN,
    COVERAGE_Y_COMMIT_TARGET_MARGIN,
    COVERAGE_Y_SWEEP_MIN_STEPS,
    LocalAdaptationSpaceGenerator,
    _apply_unresolved_coverage_mode,
    _finalize_coverage_target,
    _update_coverage_y_commit,
    _wind_search_state,
    apply_scenario_config,
    resolve_primary_victim_searcher_uav_id,
)
from wildfire_model import WildFireModel

import pytest

from test_unresolved_victim_coverage import _configure_scenario_a_east, _runtime_models


def _y_bounds() -> tuple[int, int]:
    return 0, 49


def _coverage_state(*, recent_y: list[int], agent_y: float) -> tuple[dict, int, int]:
    runtime = _runtime_models(wind="east", uav_pos=(15.0, agent_y))
    sim = runtime["simulation_model"]
    state = _wind_search_state(sim, "2501")
    state["recent_y_positions"] = list(recent_y)
    state["steps_since_detection"] = 50
    state["unresolved_victim_count"] = 1
    _apply_unresolved_coverage_mode(state)
    y_min, y_max = _y_bounds()
    return state, y_min, y_max


def test_y_sweep_commits_to_far_north_until_penetrated() -> None:
    y_min, y_max = _y_bounds()
    state, y_min, y_max = _coverage_state(recent_y=[10] * COVERAGE_Y_SWEEP_MIN_STEPS, agent_y=10.0)
    _update_coverage_y_commit(state, y_min, y_max, 10.0)
    assert state["coverage_y_commit"] == "north"
    target = _finalize_coverage_target(
        (15.0, 20.0),
        state,
        y_min=y_min,
        y_max=y_max,
        ax=15.0,
        ay=10.0,
    )
    assert target is not None
    assert int(round(target[1])) >= y_max - COVERAGE_Y_COMMIT_TARGET_MARGIN

    _update_coverage_y_commit(
        state, y_min, y_max, float(y_max - COVERAGE_Y_COMMIT_PENETRATE_MARGIN),
    )
    assert state["coverage_y_commit"] is None


def test_y_sweep_commits_to_far_south_until_penetrated() -> None:
    y_min, y_max = _y_bounds()
    state, y_min, y_max = _coverage_state(recent_y=[40] * COVERAGE_Y_SWEEP_MIN_STEPS, agent_y=40.0)
    _update_coverage_y_commit(state, y_min, y_max, 40.0)
    assert state["coverage_y_commit"] == "south"
    target = _finalize_coverage_target(
        (15.0, 30.0),
        state,
        y_min=y_min,
        y_max=y_max,
        ax=15.0,
        ay=40.0,
    )
    assert target is not None
    assert int(round(target[1])) <= y_min + COVERAGE_Y_COMMIT_TARGET_MARGIN

    _update_coverage_y_commit(
        state, y_min, y_max, float(y_min + COVERAGE_Y_COMMIT_PENETRATE_MARGIN),
    )
    assert state["coverage_y_commit"] is None


def test_y_sweep_does_not_flip_at_midline() -> None:
    y_min, y_max = _y_bounds()
    _, upper_min = (y_min + y_max) // 2, (y_min + y_max) // 2 + 1
    state, y_min, y_max = _coverage_state(
        recent_y=[10] * COVERAGE_Y_SWEEP_MIN_STEPS,
        agent_y=float(upper_min),
    )
    _update_coverage_y_commit(state, y_min, y_max, float(upper_min))
    assert state["coverage_y_commit"] == "north"
    state["recent_y_positions"] = [upper_min] * COVERAGE_Y_SWEEP_MIN_STEPS
    _update_coverage_y_commit(state, y_min, y_max, float(upper_min))
    assert state["coverage_y_commit"] == "north"


@pytest.mark.slow
def test_victim_searcher_reaches_y_ge_40_in_scenario_a_seed42() -> None:
    rng = random.Random(42)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    _configure_scenario_a_east(batch_size=300)
    model = WildFireModel()
    vs_id = resolve_primary_victim_searcher_uav_id(model)
    assert vs_id is not None
    max_y = 0
    max_target_y = 0
    for _ in range(300):
        model.step()
        agent = next((a for a in model.schedule.agents if str(a.unique_id) == vs_id), None)
        if agent is not None:
            max_y = max(max_y, int(agent.pos[1]))
        wind_state = _wind_search_state(model, vs_id)
        target = wind_state.get("current_target")
        if isinstance(target, (list, tuple)) and len(target) >= 2:
            max_target_y = max(max_target_y, int(round(float(target[1]))))
    assert max_target_y >= 40, (
        f"north commit must issue far-north targets, max_target_y={max_target_y}"
    )
    assert max_y >= 37, (
        f"searcher must penetrate above mid-band (was ~32), max_y={max_y}"
    )
