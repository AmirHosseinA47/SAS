"""fix2 item 3: the victim searcher's wind search (outputs/fix2_part1.txt section 3, rulings D-6/D-7).

3a SEARCHER_WIND_COVERAGE_FIX - the y-commit follows the wind: under north/south wind a camping
   searcher is committed to the DOWNWIND strip until it has been reached, then the upwind one;
   under east/west wind the camping bands are disjoint (a searcher on or across the midline is not
   camping). The overlap band (y 25-30) sent every searcher north whatever the wind.
3b SEARCHER_GATE_NEAR_FIELD - at the always-retreat setting (range >= 99) the searcher hazard gate
   retreats only when a strict fire/smoke cell is within 6 cells, and the gate-bypassing pathfinding
   route gets the same near-field rule. At 99 the gate was a global target-blind repulsion, and with
   no fire on the map its tied scores drove the searcher east (the B/west loop).
Both ship 1; off only on an exact integral 0.
"""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
from src_extension.adaptation.local_adaptation_generator import (
    COVERAGE_Y_COMMIT_PENETRATE_MARGIN,
    COVERAGE_Y_SWEEP_MIN_STEPS,
    _update_coverage_y_commit,
)
from src_extension.execution.uav_executor import UAVExecutor

EAST, SOUTH, WEST, NORTH = 0, 1, 2, 3
Y_MIN, Y_MAX = 0, 49


# --------------------------------------------------------------------------- switches

def test_shipped_on() -> None:
    assert cfv.SEARCHER_WIND_COVERAGE_FIX == 1 and agents.searcher_wind_coverage_fix() is True
    assert cfv.SEARCHER_GATE_NEAR_FIELD == 1 and agents.searcher_gate_near_field() is True
    assert agents.SEARCHER_GATE_NEAR_RANGE == 6


@pytest.mark.parametrize("name, accessor", [("SEARCHER_WIND_COVERAGE_FIX", "searcher_wind_coverage_fix"),
                                            ("SEARCHER_GATE_NEAR_FIELD", "searcher_gate_near_field")])
@pytest.mark.parametrize("value, expected", [(0, False), ("0", False), (0.0, False), (1, True),
                                             (0.5, True), (None, True)])
def test_off_only_on_an_exact_integral_zero(monkeypatch, name, accessor, value, expected) -> None:
    monkeypatch.setattr(cfv, name, value, raising=False)
    assert getattr(agents, accessor)() is expected


# --------------------------------------------------------------------------- 3a the y-commit

def _state(wind, ys):
    return {"last_wind_direction": wind, "recent_y_positions": list(ys), "coverage_y_commit": None}


@pytest.mark.parametrize("wind, expected", [("north", "north"), ("south", "south")])
def test_middle_band_is_sent_downwind(wind, expected) -> None:
    ws = _state(wind, [26] * COVERAGE_Y_SWEEP_MIN_STEPS)
    _update_coverage_y_commit(ws, Y_MIN, Y_MAX, 26.0)
    assert ws["coverage_y_commit"] == expected


def test_middle_band_off_is_always_north(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "SEARCHER_WIND_COVERAGE_FIX", 0)
    for wind in ("north", "south"):
        ws = _state(wind, [26] * COVERAGE_Y_SWEEP_MIN_STEPS)
        _update_coverage_y_commit(ws, Y_MIN, Y_MAX, 26.0)
        assert ws["coverage_y_commit"] == "north"


def test_upper_camping_under_north_wind_goes_north_before_south() -> None:
    ws = _state("north", [35] * COVERAGE_Y_SWEEP_MIN_STEPS)
    _update_coverage_y_commit(ws, Y_MIN, Y_MAX, 35.0)
    assert ws["coverage_y_commit"] == "north"            # the downwind strip is not reached yet


def test_after_the_downwind_strip_the_upwind_one() -> None:
    ws = _state("south", [30] * COVERAGE_Y_SWEEP_MIN_STEPS)
    _update_coverage_y_commit(ws, Y_MIN, Y_MAX, float(Y_MIN + COVERAGE_Y_COMMIT_PENETRATE_MARGIN))
    assert ws.get("south_strip_done") is True
    ws["coverage_y_commit"] = None
    ws["recent_y_positions"] = [8] * COVERAGE_Y_SWEEP_MIN_STEPS
    _update_coverage_y_commit(ws, Y_MIN, Y_MAX, 8.0)
    assert ws["coverage_y_commit"] == "north"


@pytest.mark.parametrize("ys, expected", [([26] * COVERAGE_Y_SWEEP_MIN_STEPS, "south"),
                                          ([23, 26] * 8, None),
                                          ([10] * COVERAGE_Y_SWEEP_MIN_STEPS, "north")])
def test_east_west_bands_are_disjoint(ys, expected) -> None:
    ws = _state("east", ys)
    _update_coverage_y_commit(ws, Y_MIN, Y_MAX, float(ys[-1]))
    assert ws["coverage_y_commit"] == expected


def test_a_commit_holds_until_penetrated() -> None:
    ws = _state("south", [26] * COVERAGE_Y_SWEEP_MIN_STEPS)
    _update_coverage_y_commit(ws, Y_MIN, Y_MAX, 26.0)
    assert ws["coverage_y_commit"] == "south"
    _update_coverage_y_commit(ws, Y_MIN, Y_MAX, 20.0)
    assert ws["coverage_y_commit"] == "south"
    _update_coverage_y_commit(ws, Y_MIN, Y_MAX, float(Y_MIN + COVERAGE_Y_COMMIT_PENETRATE_MARGIN))
    assert ws["coverage_y_commit"] is None


def test_a_y_lane_keeps_todays_rule() -> None:
    ws = _state("east", [26] * COVERAGE_Y_SWEEP_MIN_STEPS)
    ws["lane_axis"] = "y"
    _update_coverage_y_commit(ws, Y_MIN, Y_MAX, 26.0)
    assert ws["coverage_y_commit"] is None


# --------------------------------------------------------------------------- 3b the gate

from test_uav_executor import _FakeAgent, _bfs_test_model  # noqa: E402  (the gate tests' own fixture)


def _gate_executor(pos, fire_cells=()):
    """A victim searcher on the gate tests' model (tests/test_victim_searcher_hazard_retreat.py)."""
    model = _bfs_test_model(fire_cells=set(fire_cells))
    model._wind_search_target_state = {}
    model.managed_uav_states = {"2502": type("S", (), {"role": "victim_searcher", "position": pos})()}
    agent = _FakeAgent(unique_id=2502, pos=pos)
    ex = UAVExecutor(uav_id="2502", model=model, agent=agent)
    ex._read_uav_role = lambda: "victim_searcher"
    return ex, agent


def test_far_fire_keeps_the_searchers_direction() -> None:
    ex, agent = _gate_executor((20, 20), {(30, 20)})       # fire 10 cells east
    assert ex._apply_victim_searcher_hazard_gate(agent, EAST, "victim_search_wind_aware")[0] == EAST


def test_near_fire_still_retreats() -> None:
    ex, agent = _gate_executor((25, 20), {(30, 20)})       # fire 5 cells east
    direction, _ = ex._apply_victim_searcher_hazard_gate(agent, EAST, "victim_search_wind_aware")
    assert direction != EAST


def test_no_fire_no_tie_retreat() -> None:
    ex, agent = _gate_executor((45, 26), set())            # the B/west loop's cell and choice
    assert ex._apply_victim_searcher_hazard_gate(agent, SOUTH, "victim_search_wind_aware_sweep")[0] == SOUTH


def test_gate_off_is_the_always_retreat(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "SEARCHER_GATE_NEAR_FIELD", 0)
    ex, agent = _gate_executor((45, 26), set())
    assert ex._apply_victim_searcher_hazard_gate(agent, SOUTH, "victim_search_wind_aware_sweep")[0] == EAST
    ex, agent = _gate_executor((20, 20), {(30, 20)})
    assert ex._apply_victim_searcher_hazard_gate(agent, EAST, "victim_search_wind_aware")[0] != EAST


def test_route_approaching_a_near_hazard_is_replaced() -> None:
    ex, agent = _gate_executor((24, 20), {(28, 20)})       # 4 cells from the fire
    ex._forced_progress_direction = lambda *_a, **_k: EAST  # the greedy route steps toward it
    ex._last_escape_method = "greedy"
    routed = ex._attempt_pathfinding_toward_target(agent, (40.0, 20.0), action_label="x")
    assert routed is not None and routed[0] != EAST


def test_route_far_from_hazard_or_moving_away_is_kept(monkeypatch) -> None:
    # fix2 3b(ii)'s route, pinned: fix3a round 2 puts a route within 6 of a hazard in fire mode, whose BFS
    # plans within the edge filter (a goal on the grid edge is then unreachable) - tests/test_fix3a_r2.py.
    monkeypatch.setattr(cfv, "SEARCHER_FIRE_ROUTE_OWNER", 0)
    monkeypatch.setattr(cfv, "SEARCHER_ROUTE_BOUNDED_WAIT", 0)
    ex, agent = _gate_executor((10, 20), {(28, 20)})       # 18 cells away
    ex._forced_progress_direction = lambda *_a, **_k: EAST
    assert ex._attempt_pathfinding_toward_target(agent, (40.0, 20.0), action_label="x")[0] == EAST
    ex, agent = _gate_executor((24, 20), {(28, 20)})       # near, but moving away
    ex._forced_progress_direction = lambda *_a, **_k: WEST
    assert ex._attempt_pathfinding_toward_target(agent, (0.0, 20.0), action_label="x")[0] == WEST


def test_route_off_is_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "SEARCHER_GATE_NEAR_FIELD", 0)
    ex, agent = _gate_executor((24, 20), {(28, 20)})
    ex._forced_progress_direction = lambda *_a, **_k: EAST
    assert ex._attempt_pathfinding_toward_target(agent, (40.0, 20.0), action_label="x")[0] == EAST
