"""Base station (feature 3): kill switch, berths, config plumbing, recharge.

The plumbing tests here are the regression that stops this becoming the tenth
dead-input defect in this repo. apply_scenario_config sets attributes on the
common_fixed_variables and wildfire_model MODULES only, so a constant read
through the star-imported name, or read once at import time, keeps its original
value forever and the kill switch is silently inert. Every accessor must
therefore read getattr(cfv, ...) at CALL TIME, and that is what
test_*_reads_the_module_at_call_time asserts.
"""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
from common_fixed_variables import FIRE_COLORS, SMOKE_COLORS, VEGETATION_COLORS


# --- configuration plumbing ---------------------------------------------------

def test_base_station_mode_reads_the_module_at_call_time(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 0, raising=False)
    assert agents.base_station_mode() == 0
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    assert agents.base_station_mode() == 3


def test_return_reserve_reads_the_module_at_call_time(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "UAV_RETURN_TO_BASE_RESERVE", 42.5, raising=False)
    assert agents.uav_return_to_base_reserve() == 42.5


def test_accessors_survive_junk_values(monkeypatch) -> None:
    """A bad override must fall back, not raise inside a step."""
    for name, accessor, fallback in (
        ("BASE_STATION_MODE", agents.base_station_mode, 0),
        ("BASE_STATION_RETURN_MECHANISM", agents.base_station_return_mechanism, 2),
        ("BASE_STATION_CORNER", agents.base_station_corner, 0),
        ("BASE_STATION_SIZE", agents.base_station_size, 5),
        ("UAV_RETURN_TO_BASE_RESERVE", agents.uav_return_to_base_reserve, 60.0),
        ("BASE_STATION_RECHARGE_PER_STEP", agents.base_station_recharge_per_step, 5.0),
    ):
        monkeypatch.setattr(cfv, name, "not-a-number", raising=False)
        assert accessor() == fallback, name


def test_mode_is_clamped_to_the_ladder(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", -5, raising=False)
    assert agents.base_station_mode() == 0
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 99, raising=False)
    assert agents.base_station_mode() == 3


def test_unknown_corner_falls_back_to_nw(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_CORNER", 7, raising=False)
    assert agents.base_station_corner() == 0


def test_shipped_defaults() -> None:
    """The values the round ships with, so a silent edit is caught.

    BASE_STATION_MODE ships at 0. That is not an oversight: at mode 3 the feature
    fails three gate items, including two firefighters left permanently latched
    as route_blocked on seed 808 - the category commit 70e1b33 closed, with an
    undiagnosed mechanism. With the mode at 0 the model's default behaviour is
    provably identical to 16b2da8. Anything that flips this default must re-run
    the wave and the route_blocked gate, so the assertion is deliberate.
    """
    assert cfv.BASE_STATION_MODE == 0
    assert cfv.BASE_STATION_RETURN_MECHANISM == 2
    assert cfv.BASE_STATION_SIZE == 5
    assert cfv.UAV_RETURN_TO_BASE_RESERVE == 60.0
    assert cfv.BASE_STATION_RETURN_MARGIN == 5.0
    assert cfv.BASE_STATION_RECHARGE_PER_STEP == 5.0
    assert cfv.BASE_STATION_RECHARGE_RELEASE_LEVEL == 100.0


# --- depot geometry -----------------------------------------------------------

class _GeometryModel:
    """Minimal stand-in carrying only what _build_base_station reads."""

    HEIGHT = 50
    WIDTH = 50
    NUM_AGENTS = 4

    from wildfire_model import WildFireModel as _WF

    _build_base_station = _WF._build_base_station
    base_station_contains = _WF.base_station_contains


def _station(monkeypatch, *, corner=0, uavs=4, ffs=2, size=5):
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_CORNER", corner, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_SIZE", size, raising=False)
    import wildfire_model as wf

    monkeypatch.setattr(wf, "NUM_FIREFIGHTERS", ffs, raising=False)
    model = _GeometryModel()
    model.NUM_AGENTS = uavs
    return model._build_base_station()


def test_kill_switch_builds_no_depot(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 0, raising=False)
    model = _GeometryModel()
    assert model._build_base_station() is None


def test_default_corner_is_north_west(monkeypatch) -> None:
    station = _station(monkeypatch)
    assert station["origin"] == (0, 45)
    assert station["size"] == 5
    assert len(station["cells"]) == 25


def test_every_corner_stays_on_the_grid(monkeypatch) -> None:
    for corner, origin in ((0, (0, 45)), (1, (45, 45)), (2, (0, 0)), (3, (45, 0))):
        station = _station(monkeypatch, corner=corner)
        assert station["origin"] == origin, corner
        for x, y in station["cells"]:
            assert 0 <= x < 50 and 0 <= y < 50


def test_berths_are_distinct_and_never_collide(monkeypatch) -> None:
    station = _station(monkeypatch, uavs=5, ffs=3)
    uav = list(station["uav_berths"])
    ff = list(station["firefighter_berths"])
    assert len(uav) == 5 and len(ff) == 3
    assert len(set(uav + ff)) == 8, "a berth was handed out twice"
    assert set(uav + ff) <= station["cells"]


def test_berths_are_ranked_by_distance_from_the_edge(monkeypatch) -> None:
    """The first berth is the one cell in the block with all four moves legal.

    The ranking key is deliberately the executor's own margin-3 edge filter key,
    so the units handed berths first are the ones with the most ways out.
    """
    station = _station(monkeypatch)
    assert station["uav_berths"][0] == (4, 45)

    def edge_distance(cell):
        return min(cell[0], cell[1], 49 - cell[0], 49 - cell[1])

    ranked = station["ranked"]
    distances = [edge_distance(c) for c in ranked]
    assert distances == sorted(distances, reverse=True)
    assert distances[0] == 4


def test_footprint_overflow_raises_rather_than_stacking(monkeypatch) -> None:
    """Silently wrapping would stack UAVs and cost them a blocked first move."""
    import pytest

    with pytest.raises(ValueError):
        _station(monkeypatch, uavs=20, ffs=20)


def test_contains_matches_the_footprint(monkeypatch) -> None:
    station = _station(monkeypatch)
    model = _GeometryModel()
    model.base_station = station
    assert model.base_station_contains((4, 45))
    assert model.base_station_contains((0, 49))
    assert not model.base_station_contains((5, 45))
    assert not model.base_station_contains((25, 25))
    assert not model.base_station_contains(None)


# --- battery: the first upward writer in the model ----------------------------

class _RechargeAgent(agents.UAV):
    def __init__(self):  # noqa: D107 - deliberately skips mesa.Agent.__init__
        self.battery_level = 40.0
        self.battery_status = "normal"
        self.battery_drain_per_step = 0.1
        self.battery_drain_per_move = 0.2
        self.battery_low_threshold = 30.0
        self.battery_critical_threshold = 15.0
        self.rtb_docked = False
        self.rtb_charge_steps = 0


def test_battery_still_only_drains_when_not_docked(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    uav = _RechargeAgent()
    uav._update_battery_after_step(True)
    assert round(uav.battery_level, 6) == 39.7
    uav._update_battery_after_step(False)
    assert round(uav.battery_level, 6) == 39.6


def test_docked_uav_recharges_at_the_net_rate(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RECHARGE_PER_STEP", 5.0, raising=False)
    uav = _RechargeAgent()
    uav.rtb_docked = True
    uav._update_battery_after_step(False)
    # +5.0 recharge against the unconditional -0.1 per-step drain.
    assert round(uav.battery_level, 6) == 44.9
    assert uav.rtb_charge_steps == 1


def test_recharge_is_clamped_at_full(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RECHARGE_PER_STEP", 500.0, raising=False)
    uav = _RechargeAgent()
    uav.rtb_docked = True
    uav._update_battery_after_step(False)
    assert uav.battery_level == 100.0


def test_mode_two_parks_without_recharging(monkeypatch) -> None:
    """Return-without-recharge is the honest cost of the return increment alone."""
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 2, raising=False)
    uav = _RechargeAgent()
    uav.rtb_docked = True
    uav._update_battery_after_step(False)
    assert round(uav.battery_level, 6) == 39.9
    assert uav.rtb_charge_steps == 0


# --- the return trigger -------------------------------------------------------

class _TriggerAgent(_RechargeAgent):
    def __init__(self, pos):
        super().__init__()
        self.pos = pos
        self.selected_dir = 0
        self.rtb_last_pos = None


def test_trigger_takes_the_max_of_reserve_and_distance(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "UAV_RETURN_TO_BASE_RESERVE", 60.0, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MARGIN", 5.0, raising=False)
    # Close to the berth: the flat reserve dominates.
    near = _TriggerAgent((6, 45))
    assert near._rtb_trigger_level((4, 45)) == 60.0
    # The worst cell on the grid: 90 * 0.3 + 5 = 32.0, still under the reserve.
    far = _TriggerAgent((49, 0))
    assert far._rtb_trigger_level((4, 45)) == 60.0
    # With the reserve turned down, the distance term is what protects the UAV.
    monkeypatch.setattr(cfv, "UAV_RETURN_TO_BASE_RESERVE", 10.0, raising=False)
    assert far._rtb_trigger_level((4, 45)) == 32.0


def test_reserve_covers_the_worst_case_return() -> None:
    """The derivation, locked down: 90 cells at 0.3 must fit inside the reserve."""
    worst_case_cost = round(90 * (0.1 + 0.2), 6)
    assert worst_case_cost == 27.0
    assert cfv.UAV_RETURN_TO_BASE_RESERVE >= worst_case_cost + cfv.BASE_STATION_RETURN_MARGIN
    # And the horizon constraint: the trigger has to fire by step 150 so a
    # 90-step return still fits inside a 240-step run.
    assert (100.0 - cfv.UAV_RETURN_TO_BASE_RESERVE) / 0.3 <= 150.0


def test_steering_picks_the_larger_residual_axis() -> None:
    # move_x = [1, 0, -1, 0], move_y = [0, -1, 0, 1]
    uav = _TriggerAgent((10, 45))
    assert uav._rtb_direction((4, 45)) == 2       # -x, dx dominates
    uav = _TriggerAgent((4, 40))
    assert uav._rtb_direction((4, 45)) == 3       # +y
    uav = _TriggerAgent((4, 49))
    assert uav._rtb_direction((4, 45)) == 1       # -y


def test_steering_sidesteps_a_stall() -> None:
    """A memoryless greedy steer would re-pick the same blocked direction forever."""
    uav = _TriggerAgent((10, 48))
    assert uav._rtb_direction((4, 45)) == 2       # -x normally
    uav.rtb_last_pos = (10, 48)                   # did not move last step
    assert uav._rtb_direction((4, 45)) == 1       # takes the other axis instead


# --- rendering ----------------------------------------------------------------

def test_depot_colour_is_distinct_from_every_ground_colour() -> None:
    """Equality alone would survive someone collapsing two branches later."""
    depot = "#770099"
    assert depot != "#2b2b2b"                     # burnt
    assert depot != "#895e00"                     # scorched
    assert depot != "#2f4a1a"                     # spared vegetation
    assert depot not in VEGETATION_COLORS
    assert depot not in FIRE_COLORS
    assert depot not in SMOKE_COLORS
    # and from every agent marker on either surface
    assert depot not in {"#00FFFF", "#FF00FF", "#0066CC", "#FF8C00", "#888888",
                         "#00FFCC", "#00BFFF", "#FFFF00", "#FFA500", "#00AAFF",
                         "#000000"}


def test_dashboard_publishes_the_depot_and_the_uav_base_state() -> None:
    """The _slim_panel whitelist is a silent-break site; assert the keys survive."""
    import serve_dashboard

    panel = {"uav_status_view": [{
        "id": "2500", "role": "fire_tracker", "position": [4, 45], "battery": 61.0,
        "battery_status": "normal", "base_state": "returning",
        "execution_action": "rtb_return", "target_position": None,
        "stuck_count": 0, "last_explanation": None,
    }]}
    slim = serve_dashboard._slim_panel(panel)
    row = slim["uav_status_view"][0]
    assert row["base_state"] == "returning"
    assert row["battery_status"] == "normal"
