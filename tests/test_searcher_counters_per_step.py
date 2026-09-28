"""fix1 item 6: the victim searcher's wind-search counters count per model STEP.

They were advanced on every CALL: the planner pass, the executor's second target
computation and the executor's post-decision sync all run inside one step, so the
30-entry position windows, COVERAGE_Y_SWEEP_MIN_STEPS, the pocket / edge / hold /
same-target streaks, steps_since_detection (and its % 25 escape), the dwell count and
the post-rescue countdown ran 2-8x too fast. With SEARCHER_COUNTERS_PER_STEP (ships 1)
the first call of a step advances them and later calls in that step do not. The guard
lives inside the functions, because uav_executor imports _sync_wind_search_streaks by
name - a module-level patch (the sysdebug counterfactual) never reached that call.
"""

from __future__ import annotations

import contextlib
import io
import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation import local_adaptation_generator as lag
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.execution import uav_executor as ux
from wildfire_model import WildFireModel


@pytest.fixture(autouse=True)
def _restore_module_config():
    saved = {mod: {n: getattr(mod, n) for n in dir(mod) if n.isupper()} for mod in (cfv, wf)}
    saved_random = agents.random
    yield
    for mod, values in saved.items():
        for name in [n for n in dir(mod) if n.isupper() and n not in values]:
            delattr(mod, name)
        for name, value in values.items():
            setattr(mod, name, value)
    agents.random = saved_random


def _sync(ws, step, *, pos=(0, 10), action="hold", target=(5.0, 5.0), fn=None):
    (fn or lag._sync_wind_search_streaks)(
        ws, grid_position=pos, action=action, target=target,
        x_min=0, x_max=49, y_min=0, y_max=49, step_index=step,
    )


@pytest.mark.parametrize("raw,on", [(1, True), (0, False), ("0", False), (False, False), (None, True), (0.5, True)])
def test_switch_off_only_on_exact_zero(monkeypatch, raw, on) -> None:
    monkeypatch.setattr(cfv, "SEARCHER_COUNTERS_PER_STEP", raw)
    assert agents.searcher_counters_per_step() is on


def test_streaks_advance_once_per_step() -> None:
    ws = lag._default_wind_search_state()
    for step in (1, 1, 1, 2, 2, 3):
        _sync(ws, step)
    # on an edge cell, holding, same target: three steps -> three increments each
    assert ws["edge_streak"] == 3 and ws["hold_streak"] == 3
    assert ws["same_target_streak"] == 2  # the first sighting of a target sets it to 0
    assert ws["steps_since_detection"] == 3
    assert len(ws["recent_y_positions"]) == 3 and len(ws["recent_x_positions"]) == 3


def test_per_call_counting_at_switch_zero(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "SEARCHER_COUNTERS_PER_STEP", 0)
    ws = lag._default_wind_search_state()
    for step in (1, 1, 1, 2, 2, 3):
        _sync(ws, step)
    assert ws["edge_streak"] == 6 and ws["hold_streak"] == 6
    assert ws["steps_since_detection"] == 6 and len(ws["recent_y_positions"]) == 6


def test_the_executors_by_name_import_is_guarded_too() -> None:
    """The executor's reference IS the guarded function (no module-level patch needed)."""
    assert ux._sync_wind_search_streaks is lag._sync_wind_search_streaks
    ws = lag._default_wind_search_state()
    _sync(ws, 7)  # the planner-pass call
    _sync(ws, 7, fn=ux._sync_wind_search_streaks, action="victim_search_wind_aware")  # executor
    assert ws["hold_streak"] == 1 and ws["steps_since_detection"] == 1


def test_one_sample_per_step_from_every_caller() -> None:
    ws = lag._default_wind_search_state()
    for x in (1, 2, 3):
        lag._record_victim_searcher_x_band(ws, x, x, step_index=4)
    lag._record_victim_searcher_x_band(ws, 9, 9, step_index=5)
    assert ws["recent_x_positions"] == [1, 9] and ws["recent_y_positions"] == [1, 9]


@pytest.mark.parametrize("step", [None, 0])
def test_no_step_means_no_guard(step) -> None:
    """Before the first step, or a stand-in runtime with no step counter: per call."""
    ws = lag._default_wind_search_state()
    for x in (1, 2, 3):
        lag._record_victim_searcher_x_band(ws, x, x, step_index=step)
    assert ws["recent_x_positions"] == [1, 2, 3]


def test_dwell_counts_steps() -> None:
    ws = lag._default_wind_search_state()
    for step in (1, 1, 1):
        lag._touch_wind_search_dwell(ws, (5.0, 5.0), (5.0, 6.0), step)
    assert ws["dwell_count"] == 1


def test_post_rescue_countdown_counts_steps() -> None:
    class _Sim:
        evaluation_timesteps_counter = 12
        managed_victims: dict = {}
        victim_marker_agents: dict = {}

    ws = lag._default_wind_search_state()
    ws["post_rescue_coverage_steps_remaining"] = 50
    for _ in range(4):
        lag._update_unresolved_coverage_state(_Sim(), ws, agent_x=3, agent_y=4)
    assert ws["post_rescue_coverage_steps_remaining"] == 49
    assert ws["recent_x_positions"] == [3]


def _run(steps, **params):
    rng = random.Random(21)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=2, NUM_VICTIMS=2, NUM_FIREFIGHTERS=2,
                          WIND_DIRECTION="south", BATCH_SIZE=300, PROBABILITY_MAP=False, **params)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            model.step()
    searcher = [uid for uid in model.managed_uav_states
                if model._uav_assignment_role(uid) == "victim_searcher"][0]
    return lag._wind_search_state(model, searcher)


def test_a_real_run_samples_at_most_once_per_step() -> None:
    ws = _run(20)
    assert 0 < len(ws["recent_y_positions"]) <= 20
    assert int(ws.get("steps_since_detection", 0) or 0) <= 20


def test_a_real_run_at_switch_zero_samples_more_than_once_per_step() -> None:
    """The pre-fix1 rate, kept at switch 0: several samples per step (the 30-entry cap)."""
    ws = _run(20, SEARCHER_COUNTERS_PER_STEP=0)
    assert len(ws["recent_y_positions"]) == 30
