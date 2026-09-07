"""VICTIM_SEARCHER_HAZARD_RETREAT_RANGE: the victim searchers' interior hazard retreat.

Pins the three meanings of the constant at the searcher hazard gate and the
scoring of the retreat it selects:
  0      edge-only gate (the retreat fires within 2 cells of a grid edge, and is
         scored toward the interior)
  1..98  the retreat fires when the nearest strict fire/smoke cell is within range
  >= 99  the retreat fires on every gated step
and that, when on, the retreat ignores the grid edge and steps away from the fire.
The fake model (test_uav_executor._bfs_test_model) exposes HEIGHT/WIDTH, real
Fire agents on the schedule and a visibility model, which is what the strict
hazard helpers read; it has no per-cell agent lookup, so the gate's
"current cell is hazard" branch cannot fire here and every case below is a
searcher standing on safe ground.
"""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import common_fixed_variables as cfv
from src_extension.execution.uav_executor import UAVExecutor

from test_uav_executor import _FakeAgent, _bfs_test_model, _next_pos

ACTION = "victim_search_wind_aware"
EAST, NORTH, WEST, SOUTH = 0, 1, 2, 3


def _model(fire_cells=None):
    model = _bfs_test_model(fire_cells=set(fire_cells or ()))
    model.managed_uav_states = {}
    model._wind_search_target_state = {}
    return model


def _gate(executor, agent, chosen):
    return executor._apply_victim_searcher_hazard_gate(agent, chosen, ACTION)


def _fire_distance(cell, fire_cells):
    return min(abs(cell[0] - fx) + abs(cell[1] - fy) for fx, fy in fire_cells)


@pytest.fixture
def searcher():
    def make(pos, fire_cells=None, uav_id="2502"):
        agent = _FakeAgent(unique_id=int(uav_id), pos=pos)
        model = _model(fire_cells)
        model.managed_uav_states = {uav_id: type("S", (), {"role": "victim_searcher", "position": pos})()}
        executor = UAVExecutor(uav_id=uav_id, model=model, agent=agent)
        executor._read_uav_role = lambda: "victim_searcher"  # type: ignore[method-assign]
        return executor, agent
    return make


def test_range_reads_the_module_at_call_time(monkeypatch, searcher):
    executor, _ = searcher((20, 20))
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 0)
    assert executor._hazard_retreat_range() == 0
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 6)
    assert executor._hazard_retreat_range() == 6
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 99)
    assert executor._hazard_retreat_range() == 99
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", -4)
    assert executor._hazard_retreat_range() == 0
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", "bad")
    assert executor._hazard_retreat_range() == 0


def test_default_is_always_on():
    assert int(cfv.VICTIM_SEARCHER_HAZARD_RETREAT_RANGE) >= 99


def test_range_zero_passes_a_safe_interior_direction_through(monkeypatch, searcher):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 0)
    fire = {(30, 20)}
    executor, agent = searcher((20, 20), fire)
    # east is toward the fire but ten cells away: the 3-cell lookahead is clean
    assert _gate(executor, agent, EAST) == (EAST, ACTION)


def test_range_always_retreats_away_from_the_fire(monkeypatch, searcher):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 99)
    fire = {(30, 20)}
    executor, agent = searcher((20, 20), fire)
    direction, label = _gate(executor, agent, EAST)
    # the retreat: the neighbour furthest from the fire; north, west and south tie
    # at 11 and the first in index order wins
    assert direction == NORTH
    assert label == ACTION
    assert _fire_distance(_next_pos(agent.pos, direction), fire) > _fire_distance(agent.pos, fire)


def test_finite_range_fires_only_when_the_fire_is_within_range(monkeypatch, searcher):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 6)
    fire = {(30, 20)}
    far, agent_far = searcher((20, 20), fire)      # fire 10 away
    assert _gate(far, agent_far, EAST) == (EAST, ACTION)
    near, agent_near = searcher((25, 20), fire)    # fire 5 away
    direction, label = _gate(near, agent_near, EAST)
    assert direction == NORTH
    assert label == ACTION


def test_retarget_label_is_kept_when_the_retreat_fires(monkeypatch, searcher):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 99)
    executor, agent = searcher((20, 20), {(30, 20)})
    direction, label = executor._apply_victim_searcher_hazard_gate(
        agent, EAST, "victim_search_wind_aware_retarget",
    )
    assert direction == NORTH
    assert label == "victim_search_wind_aware_retarget_to_interior"


def test_range_zero_still_retreats_inward_at_the_edge(monkeypatch, searcher):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 0)
    executor, agent = searcher((20, 1))            # one cell from the y=0 edge, no fire
    # every direction that does not increase the edge distance is edge-blocked
    # (margin 3), so the only candidate is south, into the interior
    assert _gate(executor, agent, NORTH) == (SOUTH, ACTION)


def test_always_on_keeps_edge_handling_through_the_edge_filter(monkeypatch, searcher):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 99)
    executor, agent = searcher((20, 1))
    assert _gate(executor, agent, NORTH) == (SOUTH, ACTION)


def test_retreat_scoring_is_hazard_only_when_on(monkeypatch, searcher):
    # searcher 5 cells from the y=0 edge (outside the edge-blocked margin), fire 7
    # cells to the south, i.e. toward the interior
    fire = {(20, 12)}
    executor, agent = searcher((20, 5), fire)
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 0)
    # edge-scored: the inward step (south) wins on 14*D + 18 even though it is the
    # step toward the fire
    assert executor._retreat_to_safe_interior_direction(agent) == SOUTH
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 99)
    # hazard-only: east, north and west tie at 8 cells from the fire, east wins
    # the tie; south (6 cells) is never chosen
    assert executor._retreat_to_safe_interior_direction(agent) == EAST


def test_range_zero_gate_is_unchanged_far_from_edge_and_fire(monkeypatch, searcher):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 0)
    executor, agent = searcher((25, 25))
    for direction in (EAST, NORTH, WEST, SOUTH):
        assert _gate(executor, agent, direction) == (direction, ACTION)
