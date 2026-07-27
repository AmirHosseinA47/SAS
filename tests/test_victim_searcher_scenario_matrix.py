"""Scenario-invariant victim_searcher validation tests."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import (
    apply_scenario_config,
    resolve_primary_victim_searcher_uav_id,
    resolve_victim_searcher_uav_ids,
)
from victim_searcher_scenario_validation import (
    EDGE_CASES,
    SCENARIO_A,
    SCENARIO_B,
    SCENARIO_C,
    SCENARIO_D,
    run_scenario,
)
from wildfire_model import WildFireModel


def _patch(**values: int) -> None:
    apply_scenario_config(cfv, wf, **values)


def test_resolve_victim_searcher_role_lookup_one_uav() -> None:
    _patch(NUM_AGENTS=1, NUM_VICTIMS=1, NUM_FIREFIGHTERS=0)
    model = WildFireModel()
    ids = resolve_victim_searcher_uav_ids(model)
    assert len(ids) == 1


def test_resolve_victim_searcher_role_lookup_two_uavs() -> None:
    _patch(NUM_AGENTS=2, NUM_VICTIMS=3, NUM_FIREFIGHTERS=3)
    model = WildFireModel()
    primary = resolve_primary_victim_searcher_uav_id(model)
    assert primary is not None
    assert model.managed_uav_states[primary].role == "victim_searcher"


def test_resolve_victim_searcher_role_lookup_three_uavs() -> None:
    _patch(NUM_AGENTS=3, NUM_VICTIMS=2, NUM_FIREFIGHTERS=2)
    assert len(resolve_victim_searcher_uav_ids(WildFireModel())) == 1


def test_resolve_victim_searcher_role_lookup_five_uavs() -> None:
    _patch(NUM_AGENTS=5, NUM_VICTIMS=3, NUM_FIREFIGHTERS=3)
    assert len(resolve_victim_searcher_uav_ids(WildFireModel())) == 1


def test_no_crash_zero_victims() -> None:
    result = run_scenario(scenario_name="edge", scenario=EDGE_CASES[0], wind="north", steps=50)
    assert result.victim_searcher_id is not None
    assert result.metrics.get("strict_fire_smoke_steps", 99) <= 2


def test_scenario_matrix_helper_runs() -> None:
    result = run_scenario(scenario_name="B", scenario=SCENARIO_B, wind="north", steps=30)
    assert result.victim_searcher_id is not None


def test_scenario_a_no_5x5_camping_east() -> None:
    result = run_scenario(
        scenario_name="A", scenario=SCENARIO_A, wind="east", steps=50,
    )
    assert result.metrics.get("camping_5x5", 999) <= 30, result.metrics
    assert result.metrics.get("strict_fire_smoke_steps", 99) <= 2
    assert result.metrics.get("unique_positions", 0) >= 20


def test_variable_wind_adapts_scenario_a() -> None:
    fixed = run_scenario(scenario_name="A", scenario=SCENARIO_A, wind="west", steps=80)
    variable = run_scenario(
        scenario_name="A", scenario=SCENARIO_A, wind="west/east", variable_wind=True, steps=80,
    )
    assert fixed.victim_searcher_id == variable.victim_searcher_id
    assert variable.metrics.get("unique_targets", 0) >= 1
