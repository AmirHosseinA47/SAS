"""Feature 1: a firefighter leaves the environment for a rescue hand-over.

Drives the real WildFireModel through the post-move removal stage by hand,
the way the dispatch/replacement tests do, so every assertion holds against
the production path: queue drain -> off-grid removal -> return -> recycle ->
re-dispatch, and the planner's behaviour while a unit is off the grid.
"""

from __future__ import annotations

import os
import random

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.planning.rescue_planner import select_rescue_assignment
from wildfire_model import WildFireModel

FF_A = "ff_unit_0"
FF_B = "ff_unit_1"
V0 = "victim_0"
V1 = "victim_1"
EXIT_CELL = (0, 10)          # a boundary cell, as every exit cell is
VICTIM_CELL = (10, 10)
OTHER_VICTIM_CELL = (10, 40)


@pytest.fixture(autouse=True)
def _restore_module_config():
    """apply_scenario_config mutates module globals; put them back for other tests."""
    saved = {}
    for mod in (cfv, wf):
        saved[mod] = {
            name: getattr(mod, name, None)
            for name in ("FF_RESCUE_ABSENCE_MIN_STEPS", "FF_RESCUE_ABSENCE_MAX_STEPS", "SYSTEM_RANDOM")
        }
    saved_agents_random = agents.random
    yield
    for mod, values in saved.items():
        for name, value in values.items():
            setattr(mod, name, value)
    agents.random = saved_agents_random


def _seeded_model(seed: int = 101, absence_min: int = 3, absence_max: int = 5) -> WildFireModel:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv,
        wf,
        FF_RESCUE_ABSENCE_MIN_STEPS=absence_min,
        FF_RESCUE_ABSENCE_MAX_STEPS=absence_max,
    )
    model = WildFireModel()
    model.debug_log = False
    return model


def _ff(model: WildFireModel, ff_id: str) -> agents.Firefighter:
    return model.firefighter_marker_agents[ff_id]


def _reset_firefighters(model: WildFireModel) -> None:
    for ff in model.firefighter_marker_agents.values():
        ff.dead = False
        ff.assigned = False
        ff.target_pos = None
        ff.rescued_victim = None
        ff.exiting = False
        ff.exit_target = None
        ff.rescue_completed = False
        ff.status = "available"


def _kill_all_except(model: WildFireModel, *keep: str) -> None:
    """Empty the dispatch pool of every unit not under test (the preset has 3)."""
    for ff_id, ff in model.firefighter_marker_agents.items():
        if ff_id in keep:
            continue
        ff.dead = True
        ff.status = "dead"
        ff.assigned = False
        ff.rescued_victim = None


def _confirm_victim(model: WildFireModel, vid: str, cell: tuple[int, int]) -> agents.Victim:
    marker = model.victim_marker_agents[vid]
    state = model.managed_victims[vid]
    model.grid.move_agent(marker, cell)
    state.confirmed = True
    state.rescue_assigned = False
    state.assigned = False
    state.status = "confirmed"
    state.unreachable = False
    state.cancelled = False
    marker.status = "confirmed"
    return marker


def _set_cell_burning(model: WildFireModel, cell: tuple[int, int]) -> agents.Fire:
    for agent in model.grid.get_cell_list_contents([cell]):
        if type(agent) is agents.Fire:
            agent.burning = True
            return agent
    fire = agents.Fire(model.unique_agents_id, model, burning=True)
    model.unique_agents_id += 1
    model.schedule.add(fire)
    model.grid.place_agent(fire, cell)
    return fire


def _complete_rescue_at_exit(model: WildFireModel, ff_id: str, vid: str, step: int) -> agents.Victim:
    """Put `ff_id` on its exit cell carrying `vid` and run the completion + drain."""
    marker = _confirm_victim(model, vid, VICTIM_CELL)
    ff = _ff(model, ff_id)
    model.grid.move_agent(ff, EXIT_CELL)
    model.grid.move_agent(marker, EXIT_CELL)
    ff.assigned = True
    ff.target_pos = VICTIM_CELL
    ff.rescued_victim = marker
    ff.status = "en_route"
    ff.exiting = True
    ff.exit_target = EXIT_CELL
    model.evaluation_timesteps_counter = step
    ff.advance()                      # the production completion path
    assert ff.rescue_completed is True
    model._process_pending_agent_removals()
    return marker


def _drain_at(model: WildFireModel, step: int) -> int:
    model.evaluation_timesteps_counter = step
    return model._process_pending_agent_removals()


def test_completion_removes_firefighter_from_grid_but_not_scheduler(capsys) -> None:
    model = _seeded_model()
    _reset_firefighters(model)
    marker = _complete_rescue_at_exit(model, FF_B, V0, step=50)
    ff = _ff(model, FF_B)

    # the victim leaves exactly as before
    assert marker.status == "rescued"
    assert model.managed_victims[V0].rescued is True
    assert marker.pos is None
    assert marker.unique_id not in model.schedule._agents

    # the firefighter is off the grid, still scheduled, unavailable, unarmed
    assert ff.pos is None
    assert ff.unique_id in model.schedule._agents
    assert ff.off_grid is True
    assert ff.status == "off_grid"
    assert ff.assigned is False and ff.rescued_victim is None and ff.exiting is False
    assert model._firefighter_available_for_dispatch(ff) is False
    assert 53 <= ff.absent_until_step <= 55
    record = model._absent_firefighters[FF_B]
    assert record["return_step"] == ff.absent_until_step
    assert record["exit_cell"] == EXIT_CELL
    assert model.ff_absence_removals_total == 1
    assert model.ff_absence_returns_total == 0

    # knowledge mirror and planner snapshot see it as unavailable / off-grid
    managed = model.managed_firefighters[FF_B]
    assert managed.availability == "unavailable"
    assert managed.route_state == "off_grid"
    entry = model.get_rescue_operational_snapshot()["firefighters"][FF_B]
    assert entry["position"] is None
    assert entry["available"] is False
    assert entry["off_grid"] is True
    assert entry["return_step"] == ff.absent_until_step

    # fire on the exit cell cannot kill a unit that is not there
    _set_cell_burning(model, EXIT_CELL)
    model._check_fire_casualties()
    assert ff.dead is False

    out = capsys.readouterr().out
    assert "[Rescue Complete] FF-ff_unit_1" in out
    assert "[Firefighter Off-Grid] FF-ff_unit_1 removed at (0, 10)" in out
    assert "[Firefighter Recycled]" not in out


def test_return_after_duration_recycles_at_exit_cell_and_redispatches(capsys) -> None:
    model = _seeded_model(absence_min=4, absence_max=4)
    _reset_firefighters(model)
    _complete_rescue_at_exit(model, FF_B, V0, step=50)
    ff = _ff(model, FF_B)
    assert ff.absent_until_step == 54

    # a victim confirmed during the window waits: every other unit is dead
    _kill_all_except(model, FF_B)
    other = _confirm_victim(model, V1, OTHER_VICTIM_CELL)
    decision = select_rescue_assignment(
        model.get_rescue_operational_snapshot(), "initial", victim_id=V1
    )
    assert decision.rescue_action == "delay"

    for step in (51, 52, 53):
        _drain_at(model, step)
        assert ff.pos is None
        assert ff.off_grid is True

    handled = _drain_at(model, 54)
    assert handled == 1                      # the return counts as the recycle
    assert ff.pos == EXIT_CELL
    assert ff.off_grid is False and ff.absent_until_step is None
    assert FF_B not in model._absent_firefighters
    assert model.ff_absence_returns_total == 1
    log = model._ff_absence_log
    assert [e["event"] for e in log] == ["removed", "returned"]
    assert log[1]["duration"] == 4 and log[1]["placement"] == "exit_cell"

    # ...and the same post-drain pass that follows a recycle put it to work
    assert ff.assigned is True
    assert ff.rescued_victim is other
    assert ff.status == "en_route"
    assert model._find_active_firefighter_for_victim(V1, other)[0] == FF_B

    out = capsys.readouterr().out
    assert "[Firefighter Returned] FF-ff_unit_1 at (0, 10) after 4 steps (placement=exit_cell)" in out
    assert "[Firefighter Recycled] FF-ff_unit_1 available at (0, 10)" in out


def test_unsafe_exit_cell_relocates_to_nearest_safe_cell_within_leash() -> None:
    model = _seeded_model(absence_min=3, absence_max=3)
    _reset_firefighters(model)
    _complete_rescue_at_exit(model, FF_B, V0, step=50)
    ff = _ff(model, FF_B)

    # fire reaches the exit cell while the unit is away
    _set_cell_burning(model, EXIT_CELL)
    _drain_at(model, 53)

    assert ff.pos is not None
    assert ff.pos != EXIT_CELL
    assert ff._cell_meets_required_idle_safety(tuple(ff.pos), ff._fire_cells())
    assert abs(ff.pos[0] - EXIT_CELL[0]) + abs(ff.pos[1] - EXIT_CELL[1]) <= agents.IDLE_RETREAT_MAX_CELLS
    returned = [e for e in model._ff_absence_log if e["event"] == "returned"][0]
    assert returned["placement"] == "relocated_safe"
    assert tuple(returned["cell"]) == tuple(ff.pos)
    # nearest passing cell in (distance, x, y) order: (0, 8) at distance 2
    assert tuple(ff.pos) == (0, 8)
    assert ff.status == "available"


def test_duration_draw_is_seeded_and_leaves_shared_rng_untouched() -> None:
    first = _seeded_model(seed=202)
    draws_first = [first._draw_firefighter_absence_duration() for _ in range(12)]
    second = _seeded_model(seed=202)
    draws_second = [second._draw_firefighter_absence_duration() for _ in range(12)]
    assert draws_first == draws_second
    assert all(3 <= d <= 5 for d in draws_first)
    assert len(set(draws_first)) > 1

    third = _seeded_model(seed=303)
    draws_third = [third._draw_firefighter_absence_duration() for _ in range(12)]
    assert draws_third != draws_first

    # the shared stream is not consumed by the draw
    before = wf.SYSTEM_RANDOM.getstate()
    third._draw_firefighter_absence_duration()
    assert wf.SYSTEM_RANDOM.getstate() == before


def test_disabled_absence_recycles_in_place(capsys) -> None:
    model = _seeded_model(absence_min=3, absence_max=0)
    _reset_firefighters(model)
    before = wf.SYSTEM_RANDOM.getstate()
    _complete_rescue_at_exit(model, FF_B, V0, step=50)
    ff = _ff(model, FF_B)

    assert ff.pos == EXIT_CELL
    assert ff.status == "available"
    assert ff.off_grid is False
    assert model.ff_absence_removals_total == 0
    assert model._absent_firefighters == {}
    assert model._ff_absence_log == []
    assert wf.SYSTEM_RANDOM.getstate() == before
    out = capsys.readouterr().out
    assert "[Firefighter Recycled] FF-ff_unit_1 available at (0, 10)" in out
    assert "[Firefighter Off-Grid]" not in out


def test_planner_delays_casualty_replacement_while_a_unit_is_returning() -> None:
    model = _seeded_model(absence_min=3, absence_max=3)
    _reset_firefighters(model)
    _complete_rescue_at_exit(model, FF_B, V0, step=50)   # B off-grid until 53
    _kill_all_except(model, FF_A, FF_B)

    # A is assigned to another victim and burns; the pool is empty but B is coming back
    victim = _confirm_victim(model, V1, VICTIM_CELL)
    a_cell = (10, 9)
    model.grid.move_agent(_ff(model, FF_A), a_cell)
    assert model._dispatch_firefighter_to_victim(V1, victim, "test_initial")
    unit_a = _ff(model, FF_A)
    assert unit_a.assigned is True and unit_a.rescued_victim is victim

    _set_cell_burning(model, a_cell)
    model._check_fire_casualties()            # the real casualty -> replacement path

    state = model.managed_victims[V1]
    assert unit_a.dead is True
    assert state.unreachable is False
    assert str(state.status).lower() == "confirmed"
    assert V1 not in model._rescue_failed_logged
    assert victim.status == "confirmed"
    assert not [e for e in model._rescue_event_log if e["event_type"] == "rescue_failed"]

    # the decision the replacement path just took, re-derived from the same snapshot:
    # A dead, B off-grid and returning, nobody else alive -> delay, not give up
    decision = select_rescue_assignment(
        model.get_rescue_operational_snapshot(), "replacement_after_casualty", victim_id=V1
    )
    assert decision.rescue_action == "delay"
    assert decision.payload["returning_firefighters"] == [FF_B]

    # B returns and takes the victim over
    _drain_at(model, 53)
    unit_b = _ff(model, FF_B)
    assert unit_b.pos is not None
    assert unit_b.assigned is True
    assert unit_b.rescued_victim is victim
    assert model._find_active_firefighter_for_victim(V1, victim)[0] == FF_B
    assert state.rescue_assigned is True


def test_planner_still_gives_up_when_every_unit_is_dead() -> None:
    model = _seeded_model()
    _reset_firefighters(model)
    _confirm_victim(model, V1, VICTIM_CELL)
    _kill_all_except(model)
    decision = select_rescue_assignment(
        model.get_rescue_operational_snapshot(), "replacement_after_casualty", victim_id=V1
    )
    assert decision.rescue_action == "mark_unreachable"
    assert "returning_firefighters" not in decision.payload


def test_failed_return_is_reported_and_retried_not_lost(capsys) -> None:
    model = _seeded_model(absence_min=3, absence_max=3)
    _reset_firefighters(model)
    _complete_rescue_at_exit(model, FF_B, V0, step=50)
    ff = _ff(model, FF_B)

    original = model.grid.place_agent
    calls = {"n": 0}

    def _flaky(agent, pos):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("grid unavailable")
        return original(agent, pos)

    model.grid.place_agent = _flaky
    _drain_at(model, 53)
    assert ff.pos is None
    assert FF_B in model._absent_firefighters
    assert model.pending_removal_failures_last_step == 1
    assert model.pending_removal_failures_total == 1
    assert "[RemovalFailure] step=53 agent=Firefighter-ff_unit_1 return failed: RuntimeError" in capsys.readouterr().out

    _drain_at(model, 54)
    assert ff.pos == EXIT_CELL
    assert FF_B not in model._absent_firefighters
    assert model.ff_absence_returns_total == 1
    assert model.pending_removal_failures_last_step == 0
    returned = [e for e in model._ff_absence_log if e["event"] == "returned"][0]
    assert returned["duration"] == 4 and returned["planned_duration"] == 3
