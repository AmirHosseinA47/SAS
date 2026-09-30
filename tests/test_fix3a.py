"""fix3a (session 3a): the depot area and scenario B - outputs/fix3a_part1.txt, rulings R-1..R-5 in
outputs/fix3a_part3_prereg.txt.

  A1-R  SEARCHER_ROUTE_FIRE_FIELD   the route plans within its near-field guard over BURNING cells
  A1-S  SEARCHER_SWEEP_IN_BOUNDS    the searcher's sector / sweep stays out of the edge band
  A1-D  SEARCHER_CORNER_ESCAPE      a corner cell has an exit; the escape does not plan through a UAV
  A2    FREE_CELL_DOCKING           dock on any free footprint cell, reached by a UAV-avoiding path;
                                    charge only inside a footprint
  B1    SCENARIO_B_TEAM             B = 4 UAV (2T + 2S) / 4 victims / 3 FF
  B2    SCENARIO_B_STAGGERED_LAUNCH  85 / 65 searchers, 78 / 72 trackers in the battery scenario
  B3    SCENARIO_B_RETURN_DELAY     a searcher's return waits while the other is away, never below
                                    0.3 d + 32.30

Every rule's tests FAIL when its switch is forced to 0 (revert-checked: outputs/_fx3_revert_check.py);
each switch's OFF path is pinned where it is the a5a496db behaviour.
"""
from __future__ import annotations

import argparse
import os

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import evaluate_scenarios as es
import serve_dashboard as sd
from src_extension.execution.uav_executor import UAVExecutor

from test_uav_executor import _FakeAgent, _bfs_test_model

EAST, SOUTH, WEST, NORTH = 0, 1, 2, 3
MX = [1, 0, -1, 0]
MY = [0, -1, 0, 1]
H = W = 50


# ============================================================================ A1 helpers
def _searcher(pos, fire_cells=(), smoke_cells=(), uav_id="2502", others=()):
    agent = _FakeAgent(unique_id=int(uav_id), pos=pos)
    model = _bfs_test_model(fire_cells=set(fire_cells), smoke_cells=set(smoke_cells))
    for i, cell in enumerate(others):
        other = agents.UAV.__new__(agents.UAV)
        other.unique_id = 9000 + i
        other.pos = tuple(cell)
        model.schedule.agents.append(other)
    model.managed_uav_states = {uav_id: type("S", (), {"role": "victim_searcher", "position": pos})()}
    model._wind_search_target_state = {}
    model.evaluation_timesteps_counter = 30
    ex = UAVExecutor(uav_id=uav_id, model=model, agent=agent)
    ex._read_uav_role = lambda: "victim_searcher"  # type: ignore[method-assign]
    return ex, agent


def _near_field_setting(monkeypatch):
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 99, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_GATE_NEAR_FIELD", 1, raising=False)


def _manhattan_to(cells, cell):
    return min(abs(cell[0] - a) + abs(cell[1] - b) for a, b in cells)


# ============================================================================ A1-D
def test_a_corner_cell_has_an_inward_exit():
    """(46, 3): 3 from the east edge and 3 from the south edge. The min-over-axes filter refused all four
    moves (the D/north pair sat there 139 steps); penetration allows both inward moves."""
    ex, agent = _searcher((46, 3))
    blocked = [ex._victim_edge_blocked_direction(agent, d) for d in range(4)]
    assert blocked == [True, True, False, False]   # E, S blocked; W, N (inward) legal


def test_a_corner_cell_is_trapped_with_the_switch_off(monkeypatch):
    monkeypatch.setattr(cfv, "SEARCHER_CORNER_ESCAPE", 0, raising=False)
    ex, agent = _searcher((46, 3))
    assert all(ex._victim_edge_blocked_direction(agent, d) for d in range(4))


def test_penetration_equals_the_margin_rule_everywhere_but_at_corners(monkeypatch):
    """Exhaustive over the grid: the two filters agree on every cell and direction except where BOTH axes
    are within 3 of an edge - the only cells the fix is meant to change - and they differ there."""
    ex, agent = _searcher((25, 25))
    on, off = {}, {}
    cells = [(x, y) for x in range(H) for y in range(W)]
    for cell in cells:
        agent.pos = cell
        on[cell] = tuple(ex._victim_edge_blocked_direction(agent, d) for d in range(4))
    monkeypatch.setattr(cfv, "SEARCHER_CORNER_ESCAPE", 0, raising=False)
    for cell in cells:
        agent.pos = cell
        off[cell] = tuple(ex._victim_edge_blocked_direction(agent, d) for d in range(4))
    corner = {c for c in cells if min(c[0], H - 1 - c[0]) <= 3 and min(c[1], W - 1 - c[1]) <= 3}
    assert all(on[c] == off[c] for c in cells if c not in corner)
    assert any(on[c] != off[c] for c in corner)


@pytest.mark.parametrize("origin", [(0, 45), (45, 0)])
def test_every_footprint_cell_of_a_corner_depot_has_an_exit(origin):
    ex, agent = _searcher((25, 25))
    for i in range(5):
        for j in range(5):
            agent.pos = (origin[0] + i, origin[1] + j)
            assert not all(ex._victim_edge_blocked_direction(agent, d) for d in range(4)), agent.pos


def test_the_escape_does_not_plan_through_another_uav(monkeypatch):
    ex, agent = _searcher((46, 3), others=[(46, 4)])
    assert (46, 4) in ex._pocket_blocked_cells_for_escape(agent, (46, 3))
    monkeypatch.setattr(cfv, "SEARCHER_CORNER_ESCAPE", 0, raising=False)
    assert (46, 4) not in ex._pocket_blocked_cells_for_escape(agent, (46, 3))


# ============================================================================ A1-S
def _with_sector(ex, bounds=None):
    ex._model._uav_sector_assignments = {
        str(ex.uav_id): dict(bounds or {"x_min": 0, "x_max": H - 1, "y_min": 0, "y_max": W - 1})}


def test_a_searchers_sector_excludes_the_edge_band():
    ex, _agent = _searcher((25, 25))
    _with_sector(ex)
    assert ex._uav_sector_bounds(ex._model) == {"x_min": 4, "x_max": 45, "y_min": 4, "y_max": 45}


def test_a_trackers_sector_is_untouched():
    ex, _agent = _searcher((25, 25))
    _with_sector(ex)
    ex._read_uav_role = lambda: "fire_tracker"  # type: ignore[method-assign]
    assert ex._uav_sector_bounds(ex._model) == {"x_min": 0, "x_max": 49, "y_min": 0, "y_max": 49}


def test_the_sector_is_the_full_grid_with_the_switch_off(monkeypatch):
    monkeypatch.setattr(cfv, "SEARCHER_SWEEP_IN_BOUNDS", 0, raising=False)
    ex, _agent = _searcher((25, 25))
    _with_sector(ex)
    assert ex._uav_sector_bounds(ex._model) == {"x_min": 0, "x_max": 49, "y_min": 0, "y_max": 49}


@pytest.mark.parametrize("wind", ["north", "south", "east", "west"])
def test_the_sweep_starts_inside_the_band(wind):
    """The lawnmower sweep's start (x 0 or 49, y 0 or 49 before) is a cell the searcher can reach."""
    ex, _agent = _searcher((25, 25))
    state = ex._init_wind_aware_sweep_state(ex._model, (25, 25), None, H, W, wind)
    assert 4 <= state["sweep_x"] <= 45 and 4 <= state["sweep_y"] <= 45


def test_the_sweep_target_is_inside_the_band():
    ex, agent = _searcher((41, 4))
    state = {"sweep_x": 41, "sweep_y": 0, "sweep_dir": -1, "wind_direction": "west", "primary_axis": "y"}
    tx, ty = ex._safe_victim_sweep_target(agent, state, ex._model, None, H, W, 8, (41, 4))
    assert 4 <= tx <= 45 and 4 <= ty <= 45
    assert 4 <= state["sweep_x"] <= 45 and 4 <= state["sweep_y"] <= 45


def test_the_sweep_aims_at_the_edge_with_the_switch_off(monkeypatch):
    monkeypatch.setattr(cfv, "SEARCHER_SWEEP_IN_BOUNDS", 0, raising=False)
    ex, _agent = _searcher((25, 25))
    state = ex._init_wind_aware_sweep_state(ex._model, (25, 25), None, H, W, "west")
    assert (state["sweep_x"], state["sweep_y"]) == (49, 0)


# ============================================================================ A1-R
def test_smoke_alone_no_longer_vetoes_the_route(monkeypatch):
    """Smoke 4 cells west, no fire: the routed step west (to 3 from the smoke, never INTO it) stands.
    52% of the depot-pocket vetoes were smoke alone. (Part 2's unlatched step: pinned with round 2's
    one-owner switch at 0; with it on, smoke within 6 puts the route in fire mode - test_fix3a_r2.)"""
    _near_field_setting(monkeypatch)
    monkeypatch.setattr(cfv, "SEARCHER_FIRE_ROUTE_OWNER", 0, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_ROUTE_BOUNDED_WAIT", 0, raising=False)   # Part 2's route exactly
    ex, agent = _searcher((20, 20), smoke_cells={(16, 20)})
    routed = ex._attempt_pathfinding_toward_target(agent, (5.0, 20.0), action_label="lbl")
    assert routed is not None and routed[0] == WEST


def test_with_the_switch_off_smoke_vetoes_the_route(monkeypatch):
    """The fix2 3b(ii) behaviour, pinned: within 6 of a strict hazard (smoke included) a routed step that
    approaches it is replaced by the retreat."""
    _near_field_setting(monkeypatch)
    monkeypatch.setattr(cfv, "SEARCHER_ROUTE_FIRE_FIELD", 0, raising=False)
    ex, agent = _searcher((20, 20), smoke_cells={(16, 20)})
    routed = ex._attempt_pathfinding_toward_target(agent, (5.0, 20.0), action_label="lbl")
    assert routed is not None and routed[0] != WEST


def test_near_a_fire_the_route_keeps_its_clearance(monkeypatch):
    """A burning cell 4 west, the target beyond it: the plan never steps closer than 4 to the fire (it goes
    around, or retreats, or waits) - so the guard never has anything to veto."""
    _near_field_setting(monkeypatch)
    fire = {(16, 20)}
    ex, agent = _searcher((20, 20), fire_cells=fire)
    direction, label = ex._attempt_pathfinding_toward_target(agent, (5.0, 20.0), action_label="lbl")
    nxt = (20 + MX[direction], 20 + MY[direction])
    assert label == UAVExecutor.FIRE_WAIT_LABEL or _manhattan_to(fire, nxt) >= 4


def test_an_enclosed_searcher_waits_and_holds_its_cell(monkeypatch):
    """A ring of fire 2 around the searcher: every neighbour is 1 from the fire, no path keeps 2, no
    neighbour is safer -> WAIT, committed as a stay (it holds the cell instead of oscillating)."""
    _near_field_setting(monkeypatch)
    ring = {(25 + dx, 25 + dy) for dx in range(-2, 3) for dy in range(-2, 3) if abs(dx) + abs(dy) == 2}
    ex, agent = _searcher((25, 25), fire_cells=ring)
    direction, label = ex._attempt_pathfinding_toward_target(agent, (5.0, 5.0), action_label="lbl")
    assert label == UAVExecutor.FIRE_WAIT_LABEL
    ex._commit_execution_direction(agent, direction, label)
    assert getattr(agent, "execution_stay", False) is True


def test_a_strictly_safer_neighbour_is_taken_when_no_path_keeps_the_clearance(monkeypatch):
    """A wall of fire 2 west over the whole height, the target beyond it: no admissible path, and east is
    strictly further from the fire -> the fire retreat, east."""
    _near_field_setting(monkeypatch)
    wall = {(23, y) for y in range(W)}
    ex, agent = _searcher((25, 25), fire_cells=wall)
    direction, label = ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl")
    assert (direction, label) == (EAST, UAVExecutor.FIRE_RETREAT_LABEL)


def test_a_routed_step_through_the_near_field_of_smoke_never_enters_the_smoke(monkeypatch):
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((20, 20), smoke_cells={(19, 20), (19, 21), (19, 19)})
    routed = ex._attempt_pathfinding_toward_target(agent, (5.0, 20.0), action_label="lbl")
    assert routed is not None
    nxt = (20 + MX[routed[0]], 20 + MY[routed[0]])
    assert nxt not in {(19, 20), (19, 21), (19, 19)}


def _route_drive(ex, agent, target, steps):
    """Route step by step in a STATIC fire (the route only - no pocket, gate or sweep machinery).
    Returns (trail, labels); stops at a wait (static: it would wait forever), when the route ends, or on
    arrival (within the goal radius 2 - fix3a round 2 keeps a reached goal and waits there for the source)."""
    trail, labels = [tuple(agent.pos)], []
    for _ in range(steps):
        if abs(agent.pos[0] - target[0]) + abs(agent.pos[1] - target[1]) <= 2:
            break
        routed = ex._attempt_pathfinding_toward_target(agent, target, action_label="lbl")
        if routed is None:
            break
        direction, label = routed
        labels.append(label)
        if label == UAVExecutor.FIRE_WAIT_LABEL:
            break
        agent.pos = (agent.pos[0] + MX[direction], agent.pos[1] + MY[direction])
        trail.append(tuple(agent.pos))
    return trail, labels


def _two_cell_alternations(trail):
    return sum(1 for i in range(2, len(trail)) if trail[i] == trail[i - 2] and trail[i] != trail[i - 1])


def test_the_route_does_not_undo_its_own_detour(monkeypatch):
    """The review's repro: a burning cell 6 north of the searcher, the target beyond it. Unlatched, the
    BFS detour to distance 7 was undone by the ordinary planner stepping straight back to 6 - a two-cell
    livelock in a STATIC fire. Latched, the route goes round and arrives, never closer than 6."""
    _near_field_setting(monkeypatch)
    fire = {(25, 25)}
    ex, agent = _searcher((25, 19), fire_cells=fire)
    trail, labels = _route_drive(ex, agent, (25.0, 40.0), 80)
    assert _two_cell_alternations(trail) == 0, trail
    assert len(set(trail)) == len(trail), trail
    assert abs(trail[-1][0] - 25) + abs(trail[-1][1] - 40) <= 2, trail
    assert min(_manhattan_to(fire, cell) for cell in trail) >= 6
    assert UAVExecutor.FIRE_WAIT_LABEL not in labels
    assert ex._model._wind_search_target_state  # the latch lives in the wind state ...
    arrived = ex._attempt_pathfinding_toward_target(agent, (25.0, 40.0), action_label="lbl")
    if agents.searcher_fire_route_owner():
        # fix3a round 2 (a): the reached goal is KEPT - the route waits there for the source to move it
        assert arrived[1] == UAVExecutor.FIRE_WAIT_LABEL and _wind_state(ex).get("fire_route_target") == [25, 40]
    else:
        # ... Part 2: and is released on arrival
        assert arrived is None and _wind_state(ex).get("fire_route_target") is None


def _wind_state(ex):
    from src_extension.adaptation.local_adaptation_generator import _wind_search_state
    return _wind_search_state(ex._model, ex.uav_id)


def test_the_route_goes_round_a_fire_wall_without_cycling(monkeypatch):
    """A wall of fire (x 15, y 10-30) between the searcher and its target: the route keeps its clearance
    on every step and reaches the target round the wall's end, with no cell visited twice."""
    _near_field_setting(monkeypatch)
    wall = {(15, y) for y in range(10, 31)}
    ex, agent = _searcher((20, 20), fire_cells=wall)
    trail, _labels = _route_drive(ex, agent, (5.0, 20.0), 120)
    assert _two_cell_alternations(trail) == 0, trail
    assert len(set(trail)) == len(trail), trail
    assert abs(trail[-1][0] - 5) + abs(trail[-1][1] - 20) <= 2, trail
    assert min(_manhattan_to(wall, cell) for cell in trail) >= 5


def test_a_latched_route_beyond_the_near_field_waits_instead_of_walking_away(monkeypatch):
    """Latched on a target behind a full-height wall of fire, 10 from the wall: no admissible path, and
    outside the near field there is no retreat - it waits (it does not walk away one cell per step)."""
    _near_field_setting(monkeypatch)
    wall = {(10, y) for y in range(W)}
    ex, agent = _searcher((20, 25), fire_cells=wall)
    _wind_state(ex)["fire_route_target"] = [5, 25]
    _direction, label = ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl")
    assert label == UAVExecutor.FIRE_WAIT_LABEL


def test_a_new_target_releases_the_latch(monkeypatch):
    """Far from the fire and latched on an OLD target: the new target is a new route - the ordinary
    planner, straight toward it (not the fire mode's wait)."""
    _near_field_setting(monkeypatch)
    wall = {(10, y) for y in range(W)}
    ex, agent = _searcher((20, 25), fire_cells=wall)
    _wind_state(ex)["fire_route_target"] = [5, 25]
    direction, label = ex._attempt_pathfinding_toward_target(agent, (40.0, 25.0), action_label="lbl")
    assert (direction, label) == (EAST, "lbl")
    assert _wind_state(ex).get("fire_route_target") is None


def test_without_the_stay_action_the_fire_wait_is_never_a_blind_move(monkeypatch):
    """UAV_HOLD_STATIONARY = 0 has no stay: the enclosed searcher takes the legal neighbour farthest from
    the fire (never fire, smoke or a UAV), labelled a retreat - not selected_dir with a wait label."""
    _near_field_setting(monkeypatch)
    monkeypatch.setattr(cfv, "UAV_HOLD_STATIONARY", 0, raising=False)
    ring = {(25 + dx, 25 + dy) for dx in range(-2, 3) for dy in range(-2, 3) if abs(dx) + abs(dy) == 2}
    ex, agent = _searcher((25, 25), fire_cells=ring, others=[(26, 25)])
    agent.selected_dir = EAST
    direction, label = ex._attempt_pathfinding_toward_target(agent, (5.0, 5.0), action_label="lbl")
    assert label == UAVExecutor.FIRE_RETREAT_LABEL
    nxt = (25 + MX[direction], 25 + MY[direction])
    assert nxt not in ring and nxt != (26, 25)


# ============================================================================ A2 helpers
class _Grid:
    def __init__(self):
        self.cells = {}

    def out_of_bounds(self, pos):
        return not (0 <= int(pos[0]) < H and 0 <= int(pos[1]) < W)

    def get_cell_list_contents(self, cells):
        return [self.cells[tuple(c)] for c in cells if tuple(c) in self.cells]


class _World:
    """The two shipped 5x5 depots (NW x 0-4 y 45-49, SE x 45-49 y 0-4), a grid, a schedule."""

    def __init__(self):
        self.grid = _Grid()
        self.evaluation_timesteps_counter = 100
        depots = []
        every = set()
        for ox, oy in ((0, 45), (45, 0)):
            cells = frozenset((ox + i, oy + j) for i in range(5) for j in range(5))
            depots.append({"origin": (ox, oy), "size": 5, "cells": cells})
            every |= cells
        self.base_station = {"depots": tuple(depots), "cells": frozenset(every), "size": 5}
        self.schedule = type("Sch", (), {"agents": []})()
        self.managed_uav_states = {}

    def base_station_contains(self, pos, depot_index=None):
        cell = (int(pos[0]), int(pos[1]))
        if depot_index is None:
            return cell in self.base_station["cells"]
        return cell in self.base_station["depots"][int(depot_index)]["cells"]


def _uav(world, pos, uid, role="fire_tracker", battery=80.0, active=False, docked=False):
    uav = agents.UAV.__new__(agents.UAV)
    uav.unique_id = uid
    uav.model = world
    uav.pos = tuple(pos)
    uav.selected_dir = 0
    uav.battery_level = battery
    uav.battery_status = "normal"
    uav.battery_drain_per_step = 0.1
    uav.battery_drain_per_move = 0.2
    uav.rtb_berth = (4, 45)
    uav.rtb_berths = ((4, 45), (45, 4))
    uav.rtb_home_depot = 0
    uav.rtb_target_berth = None
    uav.rtb_target_depot = None
    uav.rtb_active = active
    uav.rtb_docked = docked
    uav.rtb_last_pos = None
    uav.rtb_stall_steps = 0
    uav.rtb_recovery_cell = None
    uav.rtb_recovery_steered = None
    uav.rtb_trips = 0
    uav.rtb_cycles = 0
    uav.rtb_return_steps = 0
    uav.rtb_charge_steps = 0
    uav.rtb_log = []
    uav.rtb_delay_steps = 0
    uav.rtb_delay_log = []
    uav.rtb_boxed_steps = 0
    uav.execution_direction_applied = False
    uav.execution_action = None
    uav.execution_stay = False
    world.grid.cells[uav.pos] = uav
    world.schedule.agents.append(uav)
    world.managed_uav_states[str(uid)] = type("S", (), {"role": role})()
    return uav


def _start_leg(uav, target, depot):
    uav.rtb_active = True
    uav.rtb_target_berth = tuple(target)
    uav.rtb_target_depot = depot
    uav.rtb_log.append({"trigger_step": 0, "arrival_step": None, "arrival_level": None, "dock_cell": None,
                        "released_step": None, "released_level": None, "repicks": 0, "boxed_steps": 0})


def _drive(uav, steps):
    """_apply_return_to_base, then move()'s own grid test (in bounds, no UAV there). Returns the cells."""
    trail = [uav.pos]
    for _ in range(steps):
        uav._apply_return_to_base()
        if uav.rtb_docked:
            break
        if uav.execution_direction_applied:
            d = uav.selected_dir
            nxt = (uav.pos[0] + MX[d], uav.pos[1] + MY[d])
            if not uav.model.grid.out_of_bounds(nxt) and nxt not in uav.model.grid.cells:
                uav.model.grid.cells.pop(uav.pos)
                uav.pos = nxt
                uav.model.grid.cells[nxt] = uav
        trail.append(uav.pos)
    return trail


@pytest.fixture
def _mode3(monkeypatch):
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MECHANISM", 2, raising=False)
    monkeypatch.setattr(cfv, "UAV_RETURN_TO_BASE_RESERVE", 0.0, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MARGIN", 39.23, raising=False)


# ============================================================================ A2
def test_a_return_docks_on_the_first_footprint_cell_it_reaches(_mode3):
    """Latched on (3, 46) from (7, 46): the leg enters the footprint at (4, 46) and docks THERE - no berth."""
    world = _World()
    uav = _uav(world, (7, 46), 2500)
    _start_leg(uav, (3, 46), 0)
    _drive(uav, 20)
    assert uav.rtb_docked and uav.pos == (4, 46)
    assert uav.rtb_log[-1]["dock_cell"] == (4, 46)


def test_the_trigger_measures_to_the_nearest_free_footprint_cell(_mode3):
    """(10, 40) -> the nearest footprint cell is (4, 45), d = 11, trigger 0.3 * 11 + 39.23 = 42.53. With a
    UAV on (4, 45) the nearest FREE cell is 12 away and the trigger rises to 42.83."""
    world = _World()
    uav = _uav(world, (10, 40), 2500, battery=42.6)
    uav._apply_return_to_base()
    assert not uav.rtb_active                      # 42.6 > 42.53
    uav.battery_level = 42.5
    uav._apply_return_to_base()
    assert uav.rtb_active and uav.rtb_target_berth == (4, 45)
    world2 = _World()
    _uav(world2, (4, 45), 2501)
    uav2 = _uav(world2, (10, 40), 2500, battery=42.8)
    uav2._apply_return_to_base()
    assert uav2.rtb_active and uav2.rtb_target_berth != (4, 45)
    assert abs(uav2.rtb_target_berth[0] - 10) + abs(uav2.rtb_target_berth[1] - 40) == 12


def test_a_doorstep_walled_by_parked_uavs_is_passed_by_a_detour(_mode3):
    """The C/W case that failed the Manhattan + greedy variant: returning to the NW depot from (4, 44) with
    UAVs parked on (4, 45) and (3, 44). The path goes round (east, north) and docks in a few steps."""
    world = _World()
    _uav(world, (4, 45), 2500)
    _uav(world, (3, 44), 2501)
    uav = _uav(world, (4, 44), 2504, role="victim_searcher")
    _start_leg(uav, (4, 46), 0)
    trail = _drive(uav, 8)
    assert uav.rtb_docked, trail
    assert len(trail) <= 5


def test_the_latched_cell_is_re_picked_when_another_uav_takes_it(_mode3):
    world = _World()
    uav = _uav(world, (8, 42), 2500)
    _start_leg(uav, (4, 45), 0)
    _uav(world, (4, 45), 2501)
    uav._apply_return_to_base()
    assert uav.rtb_target_berth != (4, 45)
    assert world.base_station_contains(uav.rtb_target_berth, 0)
    assert uav.rtb_log[-1]["repicks"] == 1


def test_a_boxed_in_return_makes_no_move(_mode3):
    world = _World()
    for i, cell in enumerate([(21, 20), (19, 20), (20, 21), (20, 19)]):
        _uav(world, cell, 2600 + i)
    uav = _uav(world, (20, 20), 2500)
    _start_leg(uav, (4, 45), 0)
    uav._apply_return_to_base()
    assert uav.execution_direction_applied is False
    assert uav.rtb_boxed_steps == 1 and uav.rtb_log[-1]["boxed_steps"] == 1


def test_a_uav_never_charges_outside_a_footprint(_mode3):
    """The positional test the berth code never had: docked (by whatever route) on open ground - no charge."""
    world = _World()
    uav = _uav(world, (20, 20), 2500, battery=50.0, active=True, docked=True)
    uav._update_battery_after_step(False)
    assert uav.battery_level == pytest.approx(49.9)
    inside = _uav(world, (4, 45), 2501, battery=50.0, active=True, docked=True)
    inside._update_battery_after_step(False)
    assert inside.battery_level == pytest.approx(49.9 + agents.base_station_recharge_per_step())


def test_the_berth_charge_has_no_positional_test_with_the_switch_off(_mode3, monkeypatch):
    """FREE_CELL_DOCKING = 0 is a5a496db: the charge is gated on rtb_docked alone."""
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 0, raising=False)
    world = _World()
    uav = _uav(world, (20, 20), 2500, battery=50.0, active=True, docked=True)
    uav._update_battery_after_step(False)
    assert uav.battery_level == pytest.approx(49.9 + agents.base_station_recharge_per_step())


def test_with_the_switch_off_a_leg_steers_to_its_berth(_mode3, monkeypatch):
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 0, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", 2, raising=False)
    world = _World()
    uav = _uav(world, (7, 46), 2500)
    uav.rtb_berth, uav.rtb_berths = (3, 46), ((3, 46), (46, 3))
    _start_leg(uav, (3, 46), 0)
    _drive(uav, 20)
    assert uav.rtb_docked and uav.pos == (3, 46)   # the berth, past the footprint cell (4, 46)


def test_trigger_level_at_follows_the_free_cell(_mode3):
    """(4, 45) is both the nearest footprint cell and the nearest berth; with a UAV on it the level
    follows the next free cell, 12 away (the berth code would still say 11)."""
    world = _World()
    uav = _uav(world, (10, 40), 2500)
    assert agents.rtb_trigger_level_at(uav, (10, 40)) == pytest.approx(0.3 * 11 + 39.23)
    _uav(world, (4, 45), 2501)
    assert agents.rtb_trigger_level_at(uav, (10, 40)) == pytest.approx(0.3 * 12 + 39.23)


def test_a_depot_walled_off_by_uavs_sends_the_return_to_the_other_depot(_mode3):
    """Latched on the NW depot, whose every approach cell (x 5, y 45-49 and y 44, x 0-4) holds a UAV: no
    UAV-free path to any of its free cells, so the re-pick falls back to the SE depot."""
    world = _World()
    for i, cell in enumerate([(5, y) for y in range(45, 50)] + [(x, 44) for x in range(5)]):
        _uav(world, cell, 2600 + i)
    uav = _uav(world, (10, 40), 2500)
    _start_leg(uav, (4, 45), 0)
    uav._apply_return_to_base()
    assert uav.rtb_target_depot == 1 and world.base_station_contains(uav.rtb_target_berth, 1)
    assert uav.execution_direction_applied is True and uav.rtb_log[-1]["repicks"] == 1


def test_mechanism_1_re_picks_a_taken_cell(_mode3, monkeypatch):
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MECHANISM", 1, raising=False)
    world = _World()
    uav = _uav(world, (8, 42), 2500)
    _start_leg(uav, (4, 45), 0)
    _uav(world, (4, 45), 2501)
    uav._apply_return_to_base()
    assert uav.rtb_target_berth != (4, 45) and world.base_station_contains(uav.rtb_target_berth, 0)
    assert uav.rtb_log[-1]["repicks"] == 1


def test_the_nearest_free_cell_tie_breaks(_mode3):
    """(25, 25) is 41 from both (4, 45) and (45, 4): the lower depot index wins - unless the first step
    toward it is blocked by a UAV and the other's is not."""
    world = _World()
    uav = _uav(world, (25, 25), 2500)
    depots = world.base_station["depots"]
    assert uav._nearest_free_dock_cell(depots, set()) == ((4, 45), 0)
    d_nw, d_se = uav._rtb_direction((4, 45), False), uav._rtb_direction((45, 4), False)
    assert d_nw != d_se
    blocker = (25 + MX[d_nw], 25 + MY[d_nw])
    assert uav._nearest_free_dock_cell(depots, {blocker}) == ((45, 4), 1)


# ============================================================================ B1
def test_scenario_b_is_the_new_team():
    preset = sd.scenario_preset("B")
    assert (preset["NUM_AGENTS"], preset["NUM_VICTIMS"], preset["NUM_FIREFIGHTERS"]) == (4, 4, 3)
    assert agents.default_role_split(preset["NUM_AGENTS"]) == (2, 2)
    assert sd.scenarios_payload()["B"]["NUM_VICTIM_SEARCHERS"] == 2


def test_scenario_b_team_switch_restores_the_legacy_team(monkeypatch):
    legacy = sd.scenario_preset("B", {"SCENARIO_B_TEAM": 0})
    assert (legacy["NUM_AGENTS"], legacy["NUM_VICTIMS"], legacy["NUM_FIREFIGHTERS"]) == (3, 2, 2)
    monkeypatch.setattr(cfv, "SCENARIO_B_TEAM", 0, raising=False)
    assert sd.scenario_preset("B")["NUM_AGENTS"] == 3
    assert sd.scenario_preset("B", {"SCENARIO_B_TEAM": 1})["NUM_AGENTS"] == 4


def test_every_preset_states_the_battery_scenario_marker():
    assert sd.scenario_extra_params("B")["BATTERY_SCENARIO"] == 1
    for key in ("A", "C", "D", "nope"):
        assert sd.scenario_extra_params(key)["BATTERY_SCENARIO"] == 0


def test_evaluate_scenarios_builds_b_from_the_resolver():
    args = argparse.Namespace(scenario="B", wind="east", uavs=None, victims=None, firefighters=None,
                              batch_size=None, steps=360, fire_spread=0.75)
    params = es._scenario_params(args)
    assert (params["NUM_AGENTS"], params["NUM_VICTIMS"], params["NUM_FIREFIGHTERS"]) == (4, 4, 3)
    assert params["BATTERY_SCENARIO"] == 1
    args.preset_overrides = {"SCENARIO_B_TEAM": 0}
    assert es._scenario_params(args)["NUM_AGENTS"] == 3


# ============================================================================ B2
ROLES = ["fire_tracker", "fire_tracker", "victim_searcher", "victim_searcher"]


def test_the_battery_scenario_launch_charges(monkeypatch):
    monkeypatch.setattr(cfv, "BATTERY_SCENARIO", 1, raising=False)
    assert agents.battery_scenario_launch_charges(ROLES) == [78.0, 72.0, 85.0, 65.0]


def test_no_launch_charges_outside_the_battery_scenario(monkeypatch):
    monkeypatch.setattr(cfv, "BATTERY_SCENARIO", 0, raising=False)
    assert agents.battery_scenario_launch_charges(ROLES) is None


def test_no_launch_charges_without_the_reduced_launch(monkeypatch):
    """REDUCED_LAUNCH_BATTERY = 0 is the pre-fix1 full-charge B: B2 replaces the reduced launch, so it
    does not apply either."""
    monkeypatch.setattr(cfv, "BATTERY_SCENARIO", 1, raising=False)
    monkeypatch.setattr(cfv, "REDUCED_LAUNCH_BATTERY", 0, raising=False)
    assert agents.battery_scenario_launch_charges(ROLES) is None


def test_a_junk_launch_fraction_still_raises_under_b2(monkeypatch):
    monkeypatch.setattr(cfv, "BATTERY_SCENARIO", 1, raising=False)
    monkeypatch.setattr(cfv, "UAV_LAUNCH_BATTERY_FRACTION", 0.0, raising=False)
    with pytest.raises(ValueError):
        agents.battery_scenario_launch_charges(ROLES)


def test_a_scenario_run_after_b_is_not_the_battery_scenario(monkeypatch):
    """apply_scenario_config never resets a parameter: A's stated marker 0 undoes B's 1 in one process."""
    import wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    for mod in (cfv, wf):
        monkeypatch.setattr(mod, "BATTERY_SCENARIO", 0, raising=False)
        monkeypatch.setattr(mod, "UAV_LAUNCH_BATTERY_FRACTION", 1.0, raising=False)
    apply_scenario_config(cfv, wf, **sd.scenario_extra_params("B"))
    assert agents.battery_scenario_launch_charges(ROLES) is not None
    apply_scenario_config(cfv, wf, **sd.scenario_extra_params("A"))
    assert agents.battery_scenario_launch_charges(ROLES) is None


def test_every_launch_charge_is_above_the_return_point_at_the_depot(monkeypatch):
    """No UAV turns home at step 1: at a depot cell d <= 8, the trigger <= 0.3 * 8 + 39.23 = 41.63."""
    monkeypatch.setattr(cfv, "BATTERY_SCENARIO", 1, raising=False)
    assert min(agents.battery_scenario_launch_charges(ROLES)) > 0.3 * 8 + 39.23


def test_the_model_launches_the_b2_charges(monkeypatch):
    import wildfire_model as wf
    for mod in (cfv, wf):
        for key, value in (("NUM_AGENTS", 4), ("NUM_FIRE_TRACKERS", None), ("NUM_VICTIM_SEARCHERS", None),
                           ("NUM_VICTIMS", 4), ("NUM_FIREFIGHTERS", 3), ("BATTERY_SCENARIO", 1),
                           ("UAV_LAUNCH_BATTERY_FRACTION", 0.5)):
            monkeypatch.setattr(mod, key, value, raising=False)
    model = wf.WildFireModel()
    uavs = sorted((a for a in model.schedule.agents if type(a) is agents.UAV), key=lambda a: a.unique_id)
    by_role = {(a.current_role, round(a.battery_level, 3)) for a in uavs}
    assert by_role == {("fire_tracker", 78.0), ("fire_tracker", 72.0),
                       ("victim_searcher", 85.0), ("victim_searcher", 65.0)}


# ============================================================================ B3
def _two_searchers(world, other_state, battery=45.0, pos=(20, 30)):
    other = _uav(world, (30, 30), 2503, role="victim_searcher")
    other.rtb_active, other.rtb_docked = other_state
    me = _uav(world, pos, 2502, role="victim_searcher", battery=battery)
    return me, other


@pytest.fixture
def _battery_scenario(monkeypatch, _mode3):
    monkeypatch.setattr(cfv, "BATTERY_SCENARIO", 1, raising=False)


def _trigger(me):
    return 0.3 * (abs(me.pos[0] - 4) + abs(me.pos[1] - 45)) + 39.23   # the nearest free cell (4, 45)


def test_the_return_waits_while_the_other_searcher_is_away(_battery_scenario):
    world = _World()
    me, _other = _two_searchers(world, (True, False))
    me.battery_level = _trigger(me) - 0.1          # the return would start now; well above the floor
    me._apply_return_to_base()
    assert not me.rtb_active and me.rtb_delay_steps == 1
    assert me.rtb_delay_log[-1]["floor"] == pytest.approx(0.3 * 31 + 32.30)


def test_the_return_waits_while_the_other_searcher_is_docked(_battery_scenario):
    world = _World()
    me, _other = _two_searchers(world, (True, True))
    me.battery_level = _trigger(me) - 0.1
    me._apply_return_to_base()
    assert not me.rtb_active


def test_never_past_the_floor(_battery_scenario):
    """At or below 0.3 d + 32.30 the return starts, other searcher away or not."""
    world = _World()
    me, _other = _two_searchers(world, (True, False))
    me.battery_level = 0.3 * 31 + 32.30
    me._apply_return_to_base()
    assert me.rtb_active and me.rtb_delay_steps == 0


def test_no_wait_when_the_other_searcher_is_flying(_battery_scenario):
    world = _World()
    me, _other = _two_searchers(world, (False, False))
    me.battery_level = _trigger(me) - 0.1
    me._apply_return_to_base()
    assert me.rtb_active


def test_a_tracker_never_waits(_battery_scenario):
    world = _World()
    _other = _uav(world, (30, 30), 2503, role="victim_searcher", active=True)
    tracker = _uav(world, (20, 30), 2500, role="fire_tracker")
    tracker.battery_level = _trigger(tracker) - 0.1
    tracker._apply_return_to_base()
    assert tracker.rtb_active


def test_no_wait_outside_the_battery_scenario(_mode3, monkeypatch):
    monkeypatch.setattr(cfv, "BATTERY_SCENARIO", 0, raising=False)
    world = _World()
    me, _other = _two_searchers(world, (True, False))
    me.battery_level = _trigger(me) - 0.1
    me._apply_return_to_base()
    assert me.rtb_active


def test_the_wait_applies_on_the_berth_path_too(_battery_scenario, monkeypatch):
    """B3 sits in both triggers: FREE_CELL_DOCKING = 0 measures to the nearest own berth."""
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 0, raising=False)
    world = _World()
    me, _other = _two_searchers(world, (True, False))
    me.battery_level = 0.3 * (abs(20 - 4) + abs(30 - 45)) + 39.23 - 0.1   # berth (4, 45)
    me._apply_return_to_base()
    assert not me.rtb_active and me.rtb_delay_steps == 1


def test_two_searchers_triggering_on_one_step_do_not_both_wait(_battery_scenario):
    """Both at the trigger on the same step: the first to act starts its return (the other is flying),
    the second then sees it away and waits - never both waiting, never both gone."""
    world = _World()
    first = _uav(world, (20, 30), 2502, role="victim_searcher")
    second = _uav(world, (22, 30), 2503, role="victim_searcher")
    first.battery_level, second.battery_level = _trigger(first) - 0.1, _trigger(second) - 0.1
    first._apply_return_to_base()
    second._apply_return_to_base()
    assert first.rtb_active and not second.rtb_active and second.rtb_delay_steps == 1


def test_the_floor_measures_to_the_free_cell_not_the_berth(_battery_scenario):
    """With a UAV on (4, 45) - the berth and the nearest footprint cell, d = 11 from (10, 40) - the trigger
    aims at a free cell 12 away and the floor is 0.3 * 12 + 32.30 = 35.90: at 35.80 the return starts
    (measured to the berth, 35.60, it would have waited)."""
    world = _World()
    _uav(world, (4, 45), 2600)
    other = _uav(world, (30, 30), 2503, role="victim_searcher", active=True)
    assert other.rtb_active
    me = _uav(world, (10, 40), 2502, role="victim_searcher", battery=35.8)
    me._apply_return_to_base()
    assert me.rtb_active and me.rtb_delay_steps == 0
    me2_world = _World()
    _uav(me2_world, (4, 45), 2600)
    _uav(me2_world, (30, 30), 2503, role="victim_searcher", active=True)
    me2 = _uav(me2_world, (10, 40), 2502, role="victim_searcher", battery=36.0)
    me2._apply_return_to_base()
    assert not me2.rtb_active and me2.rtb_delay_log[-1]["floor"] == pytest.approx(0.3 * 12 + 32.30)


def test_the_floor_keeps_the_arrival_above_low():
    """F(d) = 0.3 d + LOW + 1.70 + 0.60: after one more step away (-0.3 battery, +1 distance) the return
    still has 0.3 d' + LOW + 1.70, i.e. LOW after 17 blocked steps."""
    assert agents.return_delay_floor(0.3, 0) == pytest.approx(32.30)
    assert agents.return_delay_floor(0.3, 10) == pytest.approx(35.30)
    for d in (0, 10, 50):
        after = agents.return_delay_floor(0.3, d) - 0.3
        assert after - 0.3 * (d + 1) - 1.70 == pytest.approx(agents.battery_low_threshold())


# ============================================================================ switches
@pytest.mark.parametrize("name", ["SEARCHER_ROUTE_FIRE_FIELD", "SEARCHER_SWEEP_IN_BOUNDS", "SEARCHER_CORNER_ESCAPE",
                                  "FREE_CELL_DOCKING", "SCENARIO_B_TEAM", "SCENARIO_B_STAGGERED_LAUNCH",
                                  "SCENARIO_B_RETURN_DELAY"])
def test_every_fix3a_switch_ships_on_and_turns_off_only_on_an_exact_zero(monkeypatch, name):
    accessor = {"SEARCHER_ROUTE_FIRE_FIELD": agents.searcher_route_fire_field,
                "SEARCHER_SWEEP_IN_BOUNDS": agents.searcher_sweep_in_bounds,
                "SEARCHER_CORNER_ESCAPE": agents.searcher_corner_escape,
                "FREE_CELL_DOCKING": agents.free_cell_docking,
                "SCENARIO_B_TEAM": agents.scenario_b_team,
                "SCENARIO_B_STAGGERED_LAUNCH": agents.scenario_b_staggered_launch,
                "SCENARIO_B_RETURN_DELAY": agents.scenario_b_return_delay}[name]
    assert getattr(cfv, name) == 1 and accessor()
    for junk in (0.5, "off", None, 2):
        monkeypatch.setattr(cfv, name, junk, raising=False)
        assert accessor(), junk
    for zero in (0, 0.0, "0", False):
        monkeypatch.setattr(cfv, name, zero, raising=False)
        assert not accessor(), zero


def test_the_battery_scenario_marker_is_on_only_on_an_exact_one(monkeypatch):
    for value, expected in ((1, True), (1.0, True), ("1", True), (0, False), (0.5, False), ("yes", False),
                            (None, False), (2, False)):
        monkeypatch.setattr(cfv, "BATTERY_SCENARIO", value, raising=False)
        assert agents.battery_scenario() is expected, value
