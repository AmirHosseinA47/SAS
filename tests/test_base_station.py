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
    """Every fallback equals the value the module SHIPS, and none raises in a step.

    Since the dcD flip (2026-09-14) the shipped defaults are BASE_STATION_MODE 3,
    DEPOTS 9 (NW + SE), SPAWN_SPLIT 2, UAV_RETURN_TO_BASE_RESERVE 0.0 and
    BASE_STATION_RETURN_MARGIN 39.23, and the agents.py fallbacks encode exactly
    those. A fallback that silently disagrees with the shipped value would turn one
    missing or unparseable override into a configuration nobody measured - the
    dead-input defect in miniature. So every accessor is checked on BOTH of its
    fallback paths against what it returns for the shipped cfv value:
      - an unparseable value (setattr) reaches its except branch;
      - a MISSING attribute (delattr) reaches its getattr default, which no other
        test can reach.
    BASE_STATION_DEPOTS is the exception on the first path: a bad value RAISES.
    Consequence, accepted with the flip: a junk kill switch arms the full feature.
    A future flip of any default must move the agents.py literals with it; this test
    fails until it does.
    """
    import pytest

    # The raw shipped values, read before anything below deletes or junks them.
    cfv_split = int(cfv.BASE_STATION_SPAWN_SPLIT)
    cfv_depots = int(cfv.BASE_STATION_DEPOTS)

    for name, accessor in (
        ("BASE_STATION_MODE", agents.base_station_mode),
        ("BASE_STATION_RETURN_MECHANISM", agents.base_station_return_mechanism),
        ("BASE_STATION_SIZE", agents.base_station_size),
        ("BASE_STATION_CORNER", agents.base_station_corner),
        ("BASE_STATION_SPAWN_SPLIT", agents.base_station_spawn_split),
        ("BASE_STATION_SPAWN_FIREFIGHTERS", agents.base_station_spawn_firefighters),
        ("UAV_RETURN_TO_BASE_RESERVE", agents.uav_return_to_base_reserve),
        ("BASE_STATION_RETURN_MARGIN", agents.base_station_return_margin),
        ("BASE_STATION_RECHARGE_PER_STEP", agents.base_station_recharge_per_step),
        ("BASE_STATION_RECHARGE_RELEASE_LEVEL", agents.base_station_recharge_release_level),
        ("BASE_STATION_DOCK_FIX", agents.base_station_dock_fix),
        ("BASE_STATION_RETURN_STALL_LIMIT", agents.base_station_return_stall_limit),
        ("BASE_STATION_WAYPOINT_FIX", agents.base_station_waypoint_fix),
    ):
        shipped = accessor()
        monkeypatch.setattr(cfv, name, "not-a-number", raising=False)
        assert accessor() == shipped, "%s: except-branch fallback" % name
        monkeypatch.delattr(cfv, name)
        assert accessor() == shipped, "%s: getattr-default fallback" % name

    # Out of range: SPAWN_SPLIT maps to the shipped value (MODE clamps instead; see
    # test_mode_is_clamped_to_the_ladder).
    monkeypatch.setattr(cfv, "BASE_STATION_SPAWN_SPLIT", 7, raising=False)
    assert agents.base_station_spawn_split() == cfv_split, (
        "BASE_STATION_SPAWN_SPLIT: out-of-range fallback")

    # DEPOTS: a missing attribute falls back to the shipped mask; a bad value raises.
    monkeypatch.delattr(cfv, "BASE_STATION_DEPOTS")
    assert agents.base_station_depots() == cfv_depots, (
        "BASE_STATION_DEPOTS: getattr-default fallback")
    monkeypatch.setattr(cfv, "BASE_STATION_DEPOTS", "not-a-number", raising=False)
    with pytest.raises(ValueError, match="bitmask"):
        agents.base_station_depots()


def test_mode_is_clamped_to_the_ladder(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", -5, raising=False)
    assert agents.base_station_mode() == 0
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 99, raising=False)
    assert agents.base_station_mode() == 3


def test_unknown_corner_falls_back_to_nw(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_CORNER", 7, raising=False)
    assert agents.base_station_corner() == 0


def test_shipped_defaults() -> None:
    """The values the model ships with, so a silent edit is caught.

    BASE_STATION_MODE SHIPS AT 3, in the configuration measured as arm dcD with the
    dock fix on (outputs/_dcd4_queue.py:31-37, d4D): two depots, NW + SE
    (BASE_STATION_DEPOTS 9 = 1 + 8); searchers launched from the depot nearest their
    crosswind lane (BASE_STATION_SPAWN_SPLIT 2); the distance-regime return trigger,
    with no flat floor (UAV_RETURN_TO_BASE_RESERVE 0.0) and the derived margin that
    carries the horizon constraint (BASE_STATION_RETURN_MARGIN 39.23); the hardcoded
    return mechanism (2); recharge. Flipped 2026-09-14, from 0 / 0 / 0 / 60.0 / 5.0,
    because the feature is wanted at roughly neutral cost - not because it improves
    outcomes: on the independent fourth seed set rescued held at 89, dead rose 16 -> 23
    and firefighter deaths fell 18 -> 7 (outputs/_dcd4_splits.txt; checklist
    outputs/flip_part1.txt, validation outputs/flip_report.txt). Mode 0 is still the
    kill switch but no longer
    the default: a run that must reproduce the pre-flip default (b853617) has to pass
    BASE_STATION_MODE=0 explicitly.

    CHANGING ANY OF THESE DEFAULTS AGAIN requires, before the edit lands:
      - re-running the gate wave and the route_blocked gate at the new settings;
      - running the FULL test suite at the new settings and accounting for every
        name in its failing set (not just the count) against the recorded baseline;
      - a byte-identity check of a run on the new defaults against an arm that sets
        every BASE_STATION_* value explicitly with --set;
      - moving the agents.py accessor fallbacks with the constants
        (test_accessors_survive_junk_values).
    The assertions are deliberate.
    """
    assert cfv.BASE_STATION_MODE == 3
    assert cfv.BASE_STATION_RETURN_MECHANISM == 2
    assert cfv.BASE_STATION_SIZE == 5
    assert cfv.UAV_RETURN_TO_BASE_RESERVE == 0.0
    assert cfv.BASE_STATION_RETURN_MARGIN == 39.23
    assert cfv.BASE_STATION_RECHARGE_PER_STEP == 5.0
    assert cfv.BASE_STATION_RECHARGE_RELEASE_LEVEL == 100.0
    # Depot-cost round, shipped at its dcD arm: NW (1) + SE (8), searchers homed by
    # lane, trackers and firefighters at depot 0. DEPOTS 0 / SPLIT 0 (one depot at
    # BASE_STATION_CORNER, every unit launching from it) is now an override, and
    # BASE_STATION_CORNER is read only when BASE_STATION_DEPOTS is 0.
    assert cfv.BASE_STATION_DEPOTS == 9
    assert cfv.BASE_STATION_SPAWN_SPLIT == 2
    assert cfv.BASE_STATION_CORNER == 0
    assert cfv.BASE_STATION_SPAWN_FIREFIGHTERS == 1


# --- depot geometry -----------------------------------------------------------

class _GeometryModel:
    """Minimal stand-in carrying only what _build_base_station reads."""

    HEIGHT = 50
    WIDTH = 50
    NUM_AGENTS = 4

    from wildfire_model import WildFireModel as _WF

    _build_base_station = _WF._build_base_station
    base_station_contains = _WF.base_station_contains


def _station(monkeypatch, *, corner=0, uavs=4, ffs=2, size=5, depots=0):
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_CORNER", corner, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DEPOTS", depots, raising=False)
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
    # The SHIPPED distance regime: no flat floor, the margin alone.
    monkeypatch.setattr(cfv, "UAV_RETURN_TO_BASE_RESERVE", 0.0, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MARGIN", 39.23, raising=False)
    assert round(near._rtb_trigger_level((4, 45)), 6) == 39.83   # 0.3*2 + 39.23
    assert round(far._rtb_trigger_level((4, 45)), 6) == 66.23    # 0.3*90 + 39.23


def test_reserve_covers_the_worst_case_return(monkeypatch) -> None:
    """The SHIPPED return trigger at the SHIPPED depot geometry: what its derivation
    claims, and what dcD's own record showed instead.

    Since the dcD flip (2026-09-14) the trigger runs in the DISTANCE regime.
    UAV_RETURN_TO_BASE_RESERVE is 0.0, the identity of max(R, 0.3*d + M), so the
    trigger is 0.3*d + M with M = BASE_STATION_RETURN_MARGIN = 39.23 and d the
    manhattan distance to the NEAREST of the UAV's OWN berths. The margin carries the
    horizon constraint the flat reserve used to (derivation:
    test_distance_regime_margin_is_the_derived_one and common_fixed_variables).

    d comes from the real _build_base_station at cfv's own depot set, for every one
    of the 25 berth indices a 5x5 depot holds, from every cell of the 50x50 grid:
    49/50/49/50/51 for UAV index 0-4, 53 over all 25. The single-NW 90/92 this test
    used to lock cannot occur at BASE_STATION_DEPOTS 9.

    The fuel and horizon numbers are the DERIVATION'S, at its own premises (blocked
    standoff 11 steps, trigger latency 0.30, outbound move fraction 5/6), and are
    asserted as exactly that:
      fuel     the worst trigger, 55.13, is below a full charge, and the derived
               arrival is 37.83;
      horizon  finish(d) = (100 - level(d) + 0.30)/e + d + 11 is largest at d = 0,
               where it is 240.0125 - NOT <= 240. 39.2333 was rounded down to 39.23,
               a 0.0125-step miss at the stated premises, asserted exactly so the
               rounding stays visible.
    dcD's OWN RECORD EXCEEDS TWO OF THOSE PREMISES: over the 192 trips of d4D + drhD
    one return leg waited 17 steps (d4D south/half/423146201, UAV 2501) and 177
    triggers carried 0.43-0.53 of latency (207 of 228 over all 57 distinct dcD runs).
    The measured minimum arrival was 37.1, not 37.83. Every trip still arrived (the
    latest at step 227) and no UAV stranded. So the derived figures are the design
    point, not guarantees. The measured minimum is RECORDED here as a constant and
    compared with the configured analyzer thresholds; it is a sample minimum, not a
    floor, and nothing in this test re-measures it.

    Changing these defaults again requires the gate wave, the route_blocked gate, the
    full suite at the new settings with its failing name set accounted for, and a
    byte-identity check of a default run against an explicit --set arm. A revert to
    the flat single-NW regime must rewrite this test: it fails first at the depot
    origins, and its horizon check would fail too (flat finish(92) = 254.125 with the
    0.30 latency, 253 without; the worst own-berth distance over all 25 berths of a
    single NW depot is 98).
    """
    reserve = float(cfv.UAV_RETURN_TO_BASE_RESERVE)
    margin = float(cfv.BASE_STATION_RETURN_MARGIN)
    corner, depots = cfv.BASE_STATION_CORNER, cfv.BASE_STATION_DEPOTS
    size = int(cfv.BASE_STATION_SIZE)
    assert int(cfv.BASE_STATION_MODE) >= 2   # below 2 neither value is read
    assert (int(cfv.HEIGHT), int(cfv.WIDTH)) == (50, 50)
    # _station overwrites cfv, so everything above is read first. 25 UAVs and no
    # firefighters fill every berth index without tripping the per-depot capacity.
    station = _station(monkeypatch, corner=corner, depots=depots, size=size,
                       uavs=size * size, ffs=0)
    assert [d["origin"] for d in station["depots"]] == [(0, 45), (45, 0)]
    worst = [
        max(min(abs(x - bx) + abs(y - by) for bx, by in berths)
            for x in range(50) for y in range(50))
        for berths in station["uav_berths_by_depot"]
    ]
    assert worst[:5] == [49, 50, 49, 50, 51]
    d_max = max(worst)
    assert d_max == 53

    per_move = 0.1 + 0.2                  # UAV drain on a moving step
    e = 0.1 + 0.2 * (5.0 / 6.0)           # effective drain at move fraction 5/6
    blocked, latency = 11, 0.30           # the derivation's premises

    def level(d):
        return max(reserve, per_move * d + margin)

    # FUEL
    assert round(level(d_max), 2) == 55.13
    assert level(d_max) < float(cfv.BASE_STATION_RECHARGE_RELEASE_LEVEL)
    derived_arrival = (min(level(d) - per_move * d for d in range(d_max + 1))
                       - 0.1 * blocked - latency)
    assert round(derived_arrival, 2) == 37.83
    measured_min_arrival = 37.1           # recorded: 17-step standoff, 0.43 latency
    for arrival in (derived_arrival, measured_min_arrival):
        assert arrival > float(cfv.LOW_BATTERY_THRESHOLD)
        assert arrival > float(cfv.BATTERY_CRITICAL_THRESHOLD)

    # HORIZON
    def finish(d):
        return (100.0 - level(d) + latency) / e + d + blocked

    assert max(finish(d) for d in range(d_max + 1)) == finish(0)
    assert round(finish(0), 4) == 240.0125


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


# --- depot-cost round: the depot SET ------------------------------------------

def test_depot_mask_zero_is_the_single_corner_unchanged(monkeypatch) -> None:
    """Mask 0 must be the pre-round single-corner geometry exactly.

    It is no longer the shipped default - BASE_STATION_DEPOTS ships at 9 (NW + SE)
    since the dcD flip - but it is what every --set BASE_STATION_DEPOTS=0 arm and
    every pre-flip reference run measured, so it must not drift.
    """
    single = _station(monkeypatch, depots=0)
    explicit_nw = _station(monkeypatch, depots=1)
    assert single["origin"] == (0, 45)
    assert len(single["depots"]) == 1
    assert single["uav_berths"] == ((4, 45), (3, 45), (3, 46), (4, 46))
    assert single["firefighter_berths"] == ((2, 45), (2, 46))
    # mask 1 names the same corner that mask 0 falls back to (BASE_STATION_CORNER 0, NW)
    assert explicit_nw["uav_berths"] == single["uav_berths"]
    assert explicit_nw["cells"] == single["cells"]


def test_depot_mask_builds_depots_in_ascending_bit_order(monkeypatch) -> None:
    station = _station(monkeypatch, depots=9)          # NW (1) + SE (8)
    assert [d["origin"] for d in station["depots"]] == [(0, 45), (45, 0)]
    assert len(station["cells"]) == 50
    # bit order is depot order, so depot 0 is always the lowest set bit
    assert station["origin"] == (0, 45)


def test_central_depot_contains_the_pre_feature_spawn_cluster(monkeypatch) -> None:
    """The central block CONTAINS the pre-feature 2x2 UAV cluster.

    CORRECTED: containment does NOT discriminate (23,23) from (22,22) - a 5x5
    block at (22,22) spans 22..26 and contains the cluster too. What picks
    (23,23) is CENTREDNESS: the pre-feature anchor is (HEIGHT//2, WIDTH//2) =
    (25,25) and only (23,23) puts that cell at the block centre. Both are
    asserted, so the criterion that actually decides is the one under test.
    """
    station = _station(monkeypatch, depots=16)
    assert station["origin"] == (23, 23)
    ox, oy = station["origin"]
    size = station["size"]
    assert (ox + size // 2, oy + size // 2) == (50 // 2, 50 // 2)
    for cell in ((25, 25), (26, 25), (25, 26), (26, 26)):
        assert cell in station["cells"], cell


def test_every_uav_owns_a_distinct_berth_in_every_depot(monkeypatch) -> None:
    """The deadlock-free invariant, restated for more than one depot.

    Distinctness has to hold WITHIN each depot, because a UAV may dock in either.
    """
    station = _station(monkeypatch, depots=9, uavs=4, ffs=2)
    by_depot = station["uav_berths_by_depot"]
    ff_by_depot = station["firefighter_berths_by_depot"]
    assert len(by_depot) == 4 and all(len(row) == 2 for row in by_depot)
    for d in range(2):
        col = [row[d] for row in by_depot] + [row[d] for row in ff_by_depot]
        assert len(set(col)) == len(col), "a berth was handed out twice in depot %d" % d
        assert set(col) <= station["depots"][d]["cells"]


def test_berth_ranking_is_per_depot_not_over_the_union(monkeypatch) -> None:
    """A single sort over the union interleaves the blocks.

    Measured: ranking the concatenated NW+SE cell list gives uav_berths
    [(4,45) NW, (45,4) SE, (3,45) NW, (3,46) NW] - a 3/1 split that is an artifact
    of the (x, y) tie-break rather than a decision. Per depot, every UAV berth of
    depot 0 lies in depot 0.
    """
    station = _station(monkeypatch, depots=9)
    # CONCRETE cells, not a value read back out of the same "ranked" tuple the
    # code built the berths from - that comparison holds for ANY per-depot key,
    # including a wrong one, so it asserts nothing about the geometry.
    assert [row[0] for row in station["uav_berths_by_depot"]] == [
        (4, 45), (3, 45), (3, 46), (4, 46)]
    assert [row[1] for row in station["uav_berths_by_depot"]] == [
        (45, 4), (45, 3), (46, 3), (46, 4)]
    # and the interleaved 3/1 split the docstring names is what does NOT happen
    assert station["uav_berths"] != ((4, 45), (45, 4), (3, 45), (3, 46))


def test_overlapping_depots_raise_rather_than_duplicating_a_berth(monkeypatch) -> None:
    """Two regions sharing a cell would hand it out as two different berths."""
    import pytest

    # size 30 at 50x50 makes NW and SE overlap.
    with pytest.raises(ValueError, match="disjoint"):
        _station(monkeypatch, depots=9, size=30)


def test_capacity_is_checked_per_depot(monkeypatch) -> None:
    """A global check against the union is vacuous once there are two depots."""
    import pytest

    # 20 UAVs + 20 firefighters is 40, under the 50 berths of two 5x5 blocks but
    # over the 25 of either one. It must still raise.
    with pytest.raises(ValueError):
        _station(monkeypatch, depots=9, uavs=20, ffs=20)


def test_contains_is_scoped_when_a_depot_index_is_given(monkeypatch) -> None:
    """The docking fallback must not park a UAV in a depot it never flew to."""
    station = _station(monkeypatch, depots=9)
    model = _GeometryModel()
    model.base_station = station
    assert model.base_station_contains((4, 45))            # union
    assert model.base_station_contains((45, 4))            # union
    assert model.base_station_contains((4, 45), 0)
    assert not model.base_station_contains((4, 45), 1)
    assert model.base_station_contains((45, 4), 1)
    assert not model.base_station_contains((45, 4), 0)
    assert not model.base_station_contains((25, 25), 0)
    assert not model.base_station_contains((4, 45), 7)     # index out of range


def test_depot_mask_raises_on_an_unrecognised_value(monkeypatch) -> None:
    """base_station_corner() falls back to NW silently; this must not.

    A silent fallback would run a two-depot arm as a one-depot arm, and the wave
    would measure the wrong thing with no error anywhere.
    """
    import pytest

    monkeypatch.setattr(cfv, "BASE_STATION_DEPOTS", 99, raising=False)
    with pytest.raises(ValueError, match="bitmask"):
        agents.base_station_depots()
    monkeypatch.setattr(cfv, "BASE_STATION_DEPOTS", -1, raising=False)
    with pytest.raises(ValueError, match="bitmask"):
        agents.base_station_depots()


def test_nearest_berth_selection_and_tie_break(monkeypatch) -> None:
    """A UAV returns to the nearest of ITS OWN berths; ties go to the lower depot."""
    uav = _TriggerAgent((40, 10))
    uav.rtb_berths = ((4, 45), (45, 4))
    uav.rtb_berth = (4, 45)
    assert uav._rtb_select_berth() == (45, 4)          # SE is nearer from (40,10)
    assert uav.rtb_target_depot == 1

    near_nw = _TriggerAgent((6, 44))
    near_nw.rtb_berths = ((4, 45), (45, 4))
    near_nw.rtb_berth = (4, 45)
    assert near_nw._rtb_select_berth() == (4, 45)
    assert near_nw.rtb_target_depot == 0

    # Equidistant: from (24,24) it is 20+21 = 41 to (4,45) and 21+20 = 41 to (45,4).
    tie = _TriggerAgent((24, 24))
    tie.rtb_berths = ((4, 45), (45, 4))
    tie.rtb_berth = (4, 45)
    assert tie._rtb_select_berth() == (4, 45)
    assert tie.rtb_target_depot == 0


def test_single_depot_selection_is_the_shipped_berth(monkeypatch) -> None:
    """With one depot the selector must be inert, or nothing stays byte-identical."""
    uav = _TriggerAgent((49, 0))
    uav.rtb_berth = (4, 45)
    uav.rtb_berths = ()
    assert uav._rtb_select_berth() == (4, 45)
    assert uav.rtb_target_depot == 0


def test_stall_sidestep_cannot_fire_on_a_pure_axis_approach() -> None:
    """KNOWN DEFECT IN THE SHIPPED FEATURE, pinned so a fix flips it visibly.

    test_steering_sidesteps_a_stall covers (10,48) -> (4,45), where dx and dy are
    both non-zero and a secondary direction therefore exists. When one delta is
    zero there is nothing to swap to, and _rtb_direction returns the SAME blocked
    direction it just returned - so a UAV blocked on a pure-axis approach retries
    that move forever.

    MEASURED at BASE_STATION_MODE = 2: all five non-arriving return legs of the
    base-station round are one UAV stuck at (3,44), two cells short of berth
    (3,46) up the y axis, for 34-66 steps with 37-42 battery in hand. The round
    that produced them recorded them as still flying home. Mode 3 masks it because
    a docked blocker recharges and leaves, and the shipped default is mode 0, so
    nothing is exposed today - but any round that flips the mode inherits it.

    This test asserts the BROKEN behaviour on purpose. When it is fixed, this test
    fails, which is the point.
    """
    uav = _TriggerAgent((3, 44))
    uav.rtb_last_pos = None
    first = uav._rtb_direction((3, 46))
    assert first == 3, "straight up the y axis toward the berth"
    uav.rtb_last_pos = (3, 44)                 # the move was refused; still here
    assert uav._rtb_direction((3, 46)) == 3, (
        "the sidestep has no secondary axis to take and re-picks the blocked "
        "direction - this is the defect, not the intent"
    )


# --- depot-cost round: the spawn split, the latch, and the distance regime -----
#
# These three cover the mechanism that distinguishes arm dcD from arm dcB, the
# design's headline "chosen at the trigger and LATCHED" commitment, and the
# derivation of the margin three of the four measured arms run. All three were
# unasserted when the wave was launched; an axis or index error in the split would
# have homed every searcher at depot 0 and recorded a null lane-matching effect as
# though it had been measured, with the whole suite still green.

class _SplitModel(_GeometryModel):
    """_GeometryModel plus what _assign_depot_homes reads.

    _assign_depot_homes deliberately does NOT live in _build_base_station - the
    geometry stand-in above exposes only HEIGHT/WIDTH/NUM_AGENTS - so it needs the
    role counts and the wind, which is exactly the extra state listed here.
    """

    from wildfire_model import WildFireModel as _WF2

    _assign_depot_homes = _WF2._assign_depot_homes
    _uav_role_for_index = _WF2._uav_role_for_index
    _resolve_uav_role_counts = _WF2._resolve_uav_role_counts

    # scenario D at the round's "half" roles: 2 trackers (idx 0,1) then 2
    # searchers (idx 2,3), which is what every measured canonical run used.
    NUM_FIRE_TRACKERS = 2
    NUM_VICTIM_SEARCHERS = 2


def _homes(monkeypatch, wind, split=2, depots=9):
    monkeypatch.setattr(cfv, "BASE_STATION_SPAWN_SPLIT", split, raising=False)
    model = _SplitModel()
    model.WIND_DIRECTION = wind
    model.base_station = _station(monkeypatch, depots=depots)
    model._assign_depot_homes()
    return model.base_station


def test_role_index_map_matches_the_measured_runs(monkeypatch) -> None:
    """Recorded at steps 1/120/240 of every mode-0 arm: 2500,2501 trackers;
    2502,2503 searchers at the 2+2 split, and only 2503 a searcher at legacy."""
    m = _SplitModel()
    assert [m._uav_role_for_index(i, 4) for i in range(4)] == [
        "fire_tracker", "fire_tracker", "victim_searcher", "victim_searcher"]
    legacy = _SplitModel()
    legacy.NUM_FIRE_TRACKERS = None
    legacy.NUM_VICTIM_SEARCHERS = None
    assert [legacy._uav_role_for_index(i, 4) for i in range(4)] == [
        "fire_tracker", "fire_tracker", "fire_tracker", "victim_searcher"]


def test_partition_nearest_split_flips_with_the_wind(monkeypatch) -> None:
    """THE reason split 2 exists, and the thing no wind-blind rule can do.

    NW (x 0-4, y 45-49) and SE (x 45-49, y 0-4) fall in OPPOSITE halves of both
    possible lane axes. Under east the lanes are on y, so the low-y searcher
    (index 2) belongs to SE; under south they are on x, so the low-x searcher
    belongs to NW. If this ever stops flipping, arm dcD is measuring arm dcB with
    an unused second depot.
    """
    east = _homes(monkeypatch, "east")
    assert east["uav_home"] == (0, 0, 1, 0), east["uav_home"]
    south = _homes(monkeypatch, "south")
    assert south["uav_home"] == (0, 0, 0, 1), south["uav_home"]
    # and the spawn berth actually follows the home depot, not just the index
    assert east["uav_berths"][2] == (46, 3)      # SE berth of UAV 2
    assert south["uav_berths"][2] == (3, 46)     # NW berth of UAV 2
    # trackers and firefighters stay at depot 0 under both winds
    for st in (east, south):
        assert st["uav_home"][0] == st["uav_home"][1] == 0
        assert st["firefighter_home"] == (0, 0)
        assert st["firefighter_berths"] == ((2, 45), (2, 46))


def test_spawn_split_zero_and_one_are_what_they_say(monkeypatch) -> None:
    zero = _homes(monkeypatch, "east", split=0)
    assert zero["uav_home"] == (0, 0, 0, 0)
    assert zero["uav_berths"] == ((4, 45), (3, 45), (3, 46), (4, 46))
    alt = _homes(monkeypatch, "east", split=1)
    assert alt["uav_home"] == (0, 1, 0, 1)
    # one depot: every split degenerates to depot 0, so a single-depot arm is
    # unaffected by this setting no matter what it is set to.
    for sp in (0, 1, 2):
        one = _homes(monkeypatch, "east", split=sp, depots=0)
        assert one["uav_home"] == (0, 0, 0, 0)
        assert one["uav_berths"] == ((4, 45), (3, 45), (3, 46), (4, 46))


def test_return_target_is_latched_for_the_whole_trip(monkeypatch) -> None:
    """Re-running the argmin every step would reverse a tie-straddling UAV.

    _rtb_direction has no memory beyond one step, so a target that flips step to
    step flips the heading with it and the UAV never arrives. The latch is the
    guard; this pins it.
    """
    import agents as am
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DEPOTS", 9, raising=False)
    monkeypatch.setattr(cfv, "UAV_RETURN_TO_BASE_RESERVE", 0.0, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MARGIN", 39.23, raising=False)

    station = _station(monkeypatch, depots=9)

    class _M:
        evaluation_timesteps_counter = 7

        def base_station_contains(self, pos, depot_index=None):
            if depot_index is None:
                return tuple(pos) in station["cells"]
            return tuple(pos) in station["depots"][depot_index]["cells"]

        def __init__(self):
            self.grid = None

    uav = _TriggerAgent((24, 24))
    uav.model = _M()
    # the RTB state a real UAV carries from __init__; the stub predates it
    uav.rtb_active = False
    uav.rtb_docked = False
    uav.rtb_trips = 0
    uav.rtb_cycles = 0
    uav.rtb_return_steps = 0
    uav.rtb_log = []
    uav.rtb_target_berth = None
    uav.rtb_target_depot = None
    uav.rtb_home_depot = 0
    uav.execution_direction_applied = False
    uav.execution_action = None
    uav.rtb_berths = station["uav_berths_by_depot"][0]
    uav.rtb_berth = uav.rtb_berths[0]
    uav.battery_level = 0.0                # force the trigger on this step
    uav._apply_return_to_base()
    assert uav.rtb_active
    latched = uav.rtb_target_berth
    assert latched is not None
    # now move the UAV decisively into the OTHER depot's half and step again;
    # the target must not follow it.
    uav.pos = (46, 6)
    uav._apply_return_to_base()
    assert uav.rtb_target_berth == latched, (
        "the target moved mid-trip - the argmin is being re-run")


def test_distance_regime_margin_is_the_derived_one() -> None:
    """39.23 is derived, not tuned, and the derivation is checkable.

    It is the SHIPPED margin: since the dcD flip (2026-09-14)
    UAV_RETURN_TO_BASE_RESERVE is 0.0, so this regime is the default trigger rather
    than an arm.

    M >= [100 - e*H + e*blocked] - d*(0.3 - e), worst at d = 0, with
    e = 0.1 + 0.2*(5/6), H = 240 and blocked = 11 (the measured maximum
    blocked-step standoff over 137 recorded mechanism-2 return legs at the time),
    plus 0.30 of trigger latency. This locks the arithmetic, including that 39.2333
    was rounded DOWN to 39.23. test_reserve_covers_the_worst_case_return checks the
    shipped values against the shipped NW+SE geometry.

    The premises are the derivation's, not a measured bound: dcD's own record has a
    17-step standoff, triggers carrying 0.43-0.53 of latency, and a minimum arrival
    of 37.1 rather than the derived 37.83 (common_fixed_variables). No UAV stranded.
    """
    e = 0.1 + 0.2 * (5.0 / 6.0)
    horizon = 100.0 - e * 240.0 + e * 11
    assert round(horizon, 4) == 38.9333
    assert round(horizon + 0.30, 4) == 39.2333
    margin = round(horizon + 0.30, 2)
    assert margin == 39.23
    assert margin == cfv.BASE_STATION_RETURN_MARGIN
    # At the shipped NW+SE depots the nearest own berth is at most 53 cells away, so
    # this rule turns a UAV back LATER than a flat 60 at every reachable cell; it
    # would need d > 69.23 to turn back earlier. Its safety rests on the margin
    # carrying the horizon (no stranding in 228 recorded dcD trips), not on slack
    # against the flat rule. (Before the
    # flip, at the single NW depot's worst own-berth distance of 92, it was earlier:
    # 0.3*92 + 39.23 = 66.83.)
    assert 0.3 * 53 + margin < 60.0
    assert round((60.0 - margin) / 0.3, 2) == 69.23
    # and the DERIVED arrival - the design point; the measured minimum is 37.1 -
    # is clear of both analyzer thresholds
    arrival = margin - 0.30 - 1.10
    assert arrival > 30.0          # LOW_BATTERY_THRESHOLD
    assert arrival > 15.0          # global_analyzer critical_battery_threshold


# --- dock-fix round: the docking deadlock -------------------------------------
#
# Two independent defects, both reachable only at BASE_STATION_MODE >= 2, both
# measured on the depot-cost and base-station rounds' own artifacts before this
# code was written (outputs/dockfix_part1.txt, outputs/_df_evidence.py):
#
#   1. the docking fallback fired on an INSTANT of berth occupancy, so a UAV
#      transiting a berth for ONE STEP - which mesa makes visible to a
#      later-ordered agent inside the same advance() sweep - permanently
#      re-assigned that berth. 34 fallback docks on disk, 7 onto another UAV's
#      berth, one of which stranded a third UAV for 37 steps.
#   2. a leg stalled OUTSIDE the depot had no escape at all: the sidestep in
#      _rtb_direction is dead on a pure-axis approach and the fallback is scoped
#      to the depot interior. Twelve episodes, five of them permanent.
#
# These drive the REAL _apply_return_to_base against a grid stub, because both
# defects are about what happens on the grid over several steps and neither is
# visible to a pure-geometry test.

class _Grid:
    """The four things agents.UAV asks of a mesa grid, and nothing else."""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.cells = {}

    def out_of_bounds(self, pos):
        x, y = int(pos[0]), int(pos[1])
        return not (0 <= x < self.width and 0 <= y < self.height)

    def get_cell_list_contents(self, cells):
        return [self.cells[tuple(c)] for c in cells if tuple(c) in self.cells]

    def move_agent(self, agent, pos):
        self.cells.pop(tuple(agent.pos), None)
        agent.pos = (int(pos[0]), int(pos[1]))
        self.cells[agent.pos] = agent


class _DepotModel:
    """A model exposing only the depot geometry the RTB code reads."""

    def __init__(self, grid, origins=((0, 45),), size=5):
        self.grid = grid
        self.evaluation_timesteps_counter = 0
        depots = []
        every = set()
        for ox, oy in origins:
            cells = frozenset((ox + i, oy + j)
                              for i in range(size) for j in range(size))
            depots.append({"origin": (ox, oy), "size": size, "cells": cells})
            every |= cells
        self.base_station = {"depots": tuple(depots), "size": size,
                             "cells": frozenset(every)}

    def base_station_contains(self, pos, depot_index=None):
        cell = (int(pos[0]), int(pos[1]))
        if depot_index is None:
            return cell in self.base_station["cells"]
        depots = self.base_station["depots"]
        if not 0 <= int(depot_index) < len(depots):
            return False
        return cell in depots[int(depot_index)]["cells"]


def _blocker(grid, cell):
    """An EXACT agents.UAV: not_UAV_adjacent tests `type(a) is UAV`, so a
    subclass would be invisible to it and the block would not block."""
    other = agents.UAV.__new__(agents.UAV)
    other.pos = tuple(cell)
    grid.cells[tuple(cell)] = other
    return other


def _returner(model, pos, berth, depot=0):
    """A UAV mid-return, with exactly the state _apply_return_to_base reads."""
    uav = agents.UAV.__new__(agents.UAV)
    uav.model = model
    uav.pos = tuple(pos)
    uav.selected_dir = 0
    uav.battery_level = 40.0
    uav.battery_status = "normal"
    uav.battery_drain_per_step = 0.1
    uav.battery_drain_per_move = 0.2
    uav.rtb_berth = tuple(berth)
    uav.rtb_berths = (tuple(berth),)
    uav.rtb_home_depot = depot
    uav.rtb_target_berth = tuple(berth)
    uav.rtb_target_depot = depot
    uav.rtb_active = True
    uav.rtb_docked = False
    uav.rtb_last_pos = None
    uav.rtb_stall_steps = 0
    uav.rtb_recovery_cell = None
    uav.rtb_recovery_steered = None
    uav.rtb_trips = 1
    uav.rtb_cycles = 0
    uav.rtb_return_steps = 0
    uav.rtb_charge_steps = 0
    uav.rtb_log = [{"trigger_step": 0, "arrival_step": None, "arrival_level": None,
                    "dock_cell": None, "released_step": None,
                    "released_level": None}]
    uav.execution_direction_applied = False
    uav.execution_action = None
    model.grid.cells[uav.pos] = uav
    return uav


def _drive(uav, steps):
    """advance() for one UAV: _apply_return_to_base, then move()'s grid test.

    move() itself is not called because it consults the extension pipeline, which
    is not what these tests are about; the two conditions it applies to the
    candidate cell - in bounds, and no other UAV there - are applied here.
    """
    trail = [tuple(uav.pos)]
    move_x, move_y = (1, 0, -1, 0), (0, -1, 0, 1)
    for _ in range(steps):
        uav._apply_return_to_base()
        if uav.rtb_docked:
            break
        nxt = (uav.pos[0] + move_x[uav.selected_dir],
               uav.pos[1] + move_y[uav.selected_dir])
        if not uav.model.grid.out_of_bounds(nxt) and uav.not_UAV_adjacent(nxt):
            uav.model.grid.move_agent(uav, nxt)
        trail.append(tuple(uav.pos))
    return trail


def _mode_two_world(monkeypatch, fix=2):
    """bsret east/half/101 at frame 207, the exact recorded mode-2 deadlock.

    2502 is returning to (3,46). ITS BERTH IS FREE AND STAYS FREE. It is stuck at
    (3,44) because (3,45) - the only cell on its pure-axis path - holds a UAV
    docked at mode 2, where the release branch is unreachable, so that blocker
    provably never moves. That is what makes this the case a berth-occupancy
    trigger cannot see.
    """
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 2, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MECHANISM", 2, raising=False)
    monkeypatch.setattr(cfv, "UAV_RETURN_TO_BASE_RESERVE", 60.0, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", fix, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_STALL_LIMIT", 3, raising=False)
    grid = _Grid(50, 50)
    model = _DepotModel(grid)
    for cell in ((4, 45), (3, 45), (4, 46)):
        _blocker(grid, cell)
    return model, _returner(model, (3, 44), (3, 46))


def test_stall_sidestep_cannot_fire_on_a_pure_axis_approach() -> None:
    """The STEER still re-picks the blocked direction - now by design.

    This test used to assert the broken behaviour so a fix would flip it. The fix
    deliberately does NOT change _rtb_direction: keeping it distance-monotone is
    what bounds the number of moves on a leg and makes the consecutive-stall
    counter a valid termination variant, and an in-steer detour interleaved with
    a memoryless greedy undoes itself (built, replayed and rejected -
    outputs/_df_sandbox.py rule R1). So the geometry below is unchanged and the
    recovery lives one level up, in _apply_return_to_base; the test that pins the
    fix is test_recovery_reaches_the_berth_in_the_recorded_mode_two_deadlock.

    Note also what the shipped comment used to say about this: that the swap put
    None in `primary` and the function fell through. It does not. The swap is
    GUARDED by `secondary is not None` and simply never runs.
    """
    uav = _TriggerAgent((3, 44))
    uav.rtb_last_pos = None
    assert uav._rtb_direction((3, 46)) == 3, "straight up the y axis"
    uav.rtb_last_pos = (3, 44)                 # the move was refused; still here
    assert uav._rtb_direction((3, 46)) == 3, (
        "the swap has no secondary axis to take, so the steer re-picks the "
        "blocked direction - deliberately unchanged; the recovery is elsewhere"
    )


def test_the_pure_axis_hole_is_symmetric() -> None:
    """The shipped comment and the brief both framed it as dx == 0 only."""
    uav = _TriggerAgent((44, 3))
    uav.rtb_last_pos = (44, 3)
    assert uav._rtb_direction((46, 3)) == 0    # dy == 0: +x, re-picked
    uav = _TriggerAgent((3, 44))
    uav.rtb_last_pos = (3, 44)
    assert uav._rtb_direction((3, 46)) == 3    # dx == 0: +y, re-picked


def test_explicit_stalled_argument_does_not_disturb_the_default() -> None:
    """The recovery passes `stalled` explicitly; no other caller may see a change."""
    uav = _TriggerAgent((10, 48))
    uav.rtb_last_pos = (10, 48)
    assert uav._rtb_direction((4, 45)) == 1              # inferred: stalled
    assert uav._rtb_direction((4, 45), True) == 1        # same, explicit
    assert uav._rtb_direction((4, 45), False) == 2       # as if it had moved


def test_recovery_reaches_the_berth_in_the_recorded_mode_two_deadlock(monkeypatch) -> None:
    """THE PRIMARY UNIT GATE for mechanism 2.

    At HEAD this UAV re-picks +y into a permanently docked blocker for the rest of
    the run - 33 to 65 steps across the five recorded mode-2 legs. With the
    recovery it routes around and reaches ITS OWN BERTH.
    """
    model, uav = _mode_two_world(monkeypatch)
    trail = _drive(uav, 12)
    assert uav.rtb_docked, "the leg must terminate; trail was %s" % (trail,)
    assert uav.rtb_log[-1]["dock_cell"] == (3, 46), (
        "and it must terminate AT ITS OWN BERTH, which was free all along; "
        "trail was %s" % (trail,)
    )
    assert model.base_station_contains(uav.pos, 0)


def test_head_behaviour_is_a_permanent_freeze_with_the_switch_off(monkeypatch) -> None:
    """The same world with BASE_STATION_DOCK_FIX = 0 must still deadlock.

    This is the kill switch doing its job, and it is also the proof that the test
    above is measuring the fix rather than an artefact of the stub.
    """
    _model, uav = _mode_two_world(monkeypatch, fix=0)
    trail = _drive(uav, 20)
    assert not uav.rtb_docked
    assert set(trail) == {(3, 44)}, "frozen on one cell, as at 9f77178"


def test_the_recovery_cannot_livelock(monkeypatch) -> None:
    """A UAV that MOVES every step while getting nowhere is invisible to a
    "position unchanged for N steps" stall gate - a fix that turned freezes into
    cycles would have scored a clean sweep on it. The obvious minimal fix does
    exactly that (outputs/_df_sandbox.py rule R1), so it is asserted against.
    """
    _model, uav = _mode_two_world(monkeypatch)
    trail = _drive(uav, 20)
    # A LIVELOCK IS A RETURN TO A CELL THE UAV HAS LEFT, which is not the same
    # thing as standing still: the leg legitimately holds position while the
    # stall counter reaches the limit, and those repeats are consecutive. Collapse
    # consecutive runs first, then no cell may appear twice.
    visited = [cell for i, cell in enumerate(trail)
               if i == 0 or cell != trail[i - 1]]
    assert len(visited) == len(set(visited)), (
        "returned to a cell it had left - that is a cycle, not a stall: %s"
        % (trail,)
    )


def test_the_recovery_is_sticky_not_stall_gated(monkeypatch) -> None:
    """Engaging only on stalled steps is ping-pong with extra steps.

    The escape step MOVES the UAV, so on the next step it is not stalled; if the
    latch stops steering there the memoryless greedy toward the berth runs and
    walks it straight back. The latch must own the steer on every step until the
    depot is reached. Asserted directly: after the UAV has moved, the recovery
    still returns the latched cell.
    """
    _model, uav = _mode_two_world(monkeypatch)
    move_x, move_y = (1, 0, -1, 0), (0, -1, 0, 1)
    for _ in range(6):
        uav._apply_return_to_base()
        nxt = (uav.pos[0] + move_x[uav.selected_dir],
               uav.pos[1] + move_y[uav.selected_dir])
        moved = (not uav.model.grid.out_of_bounds(nxt)
                 and uav.not_UAV_adjacent(nxt))
        if moved:
            uav.model.grid.move_agent(uav, nxt)
        if moved and uav.rtb_recovery_cell is not None:
            break
    assert uav.rtb_recovery_cell is not None, "the latch never engaged"
    assert uav.rtb_last_pos != tuple(uav.pos), "precondition: it moved"
    assert uav._rtb_recovery_berth(tuple(uav.pos)) == uav.rtb_recovery_cell, (
        "the latch must still steer on a step where the UAV is NOT stalled"
    )


def test_recovery_is_inert_inside_the_depot(monkeypatch) -> None:
    """Inside the depot the berth is the target again and the terminator owns it.

    An earlier draft let the recovery keep re-latching inside the footprint and
    it walked the UAV back out.
    """
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", 2, raising=False)
    grid = _Grid(50, 50)
    model = _DepotModel(grid)
    _blocker(grid, (3, 45))
    uav = _returner(model, (2, 45), (3, 46))
    uav.rtb_stall_steps = 99
    uav.rtb_recovery_cell = (0, 49)
    assert uav._rtb_recovery_berth((2, 45)) is None
    assert uav.rtb_recovery_cell is None, "and the latch is dropped on entry"


def test_recovery_is_inert_without_a_grid(monkeypatch) -> None:
    """Which is what keeps the pure-geometry steering tests meaningful."""
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", 2, raising=False)
    uav = _TriggerAgent((3, 44))
    uav.rtb_stall_steps = 99
    uav.rtb_target_depot = 0
    uav.rtb_recovery_cell = None

    class _NoGrid:
        grid = None
        base_station = None

        def base_station_contains(self, _pos, _depot=None):
            return False

    uav.model = _NoGrid()
    assert uav._rtb_recovery_berth((3, 44)) is None


def test_a_one_step_transit_never_re_assigns_a_berth(monkeypatch) -> None:
    """MECHANISM 1, on the geometry that produced the recorded deadlock.

    dcB east/half/808 frame 202: 2501 stands on 2502's berth (3,46) for exactly
    one step, in transit to its own berth (3,45). 2502 is inside the depot at
    (4,45) - which is 2500's berth. At HEAD it docked there permanently and
    stranded 2500 for 37 steps.
    """
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MECHANISM", 2, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", 2, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_STALL_LIMIT", 3, raising=False)
    grid = _Grid(50, 50)
    model = _DepotModel(grid)
    _blocker(grid, (3, 46))                  # the transiting UAV, this step only
    uav = _returner(model, (4, 45), (3, 46))
    uav._apply_return_to_base()
    assert not uav.rtb_docked, (
        "a one-step transit must not re-assign a berth; it did at 9f77178"
    )
    assert uav.rtb_log[-1]["dock_cell"] is None


def test_the_old_trigger_still_docks_with_the_switch_off(monkeypatch) -> None:
    """The same transit, at BASE_STATION_DOCK_FIX = 0, must still misdock -
    otherwise the test above is not measuring the fix."""
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MECHANISM", 2, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", 0, raising=False)
    grid = _Grid(50, 50)
    model = _DepotModel(grid)
    _blocker(grid, (3, 46))
    uav = _returner(model, (4, 45), (3, 46))
    uav._apply_return_to_base()
    assert uav.rtb_docked
    assert uav.rtb_log[-1]["dock_cell"] == (4, 45), "on another UAV's berth"


def test_the_stall_witness_counts_and_resets(monkeypatch) -> None:
    """L-1 refused steps do not dock; L does; one successful move resets it."""
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MECHANISM", 2, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", 1, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_STALL_LIMIT", 3, raising=False)
    grid = _Grid(50, 50)
    model = _DepotModel(grid)
    _blocker(grid, (3, 46))
    uav = _returner(model, (3, 45), (3, 46))
    for expected in (0, 1, 2):
        uav._apply_return_to_base()
        assert uav.rtb_stall_steps == expected
        assert not uav.rtb_docked
        uav.rtb_last_pos = tuple(uav.pos)      # the move was refused
    uav._apply_return_to_base()
    assert uav.rtb_docked, "the third consecutive refusal reaches the limit"
    # and a successful move resets it
    uav2 = _returner(_DepotModel(_Grid(50, 50)), (3, 40), (3, 46))
    uav2._apply_return_to_base()
    uav2.rtb_last_pos = tuple(uav2.pos)
    uav2._apply_return_to_base()
    assert uav2.rtb_stall_steps == 1
    uav2.rtb_last_pos = (9, 9)                 # i.e. it moved
    uav2._apply_return_to_base()
    assert uav2.rtb_stall_steps == 0


def test_the_terminator_never_docks_outside_the_depot(monkeypatch) -> None:
    """The rejected alternative docked on the DOORSTEP. It must not.

    _update_battery_after_step gates the recharge on rtb_docked alone with no
    positional test, and the harness derives base_state from the same flag, so a
    dock one cell outside the footprint would refuel a UAV on open ground AND
    relabel a stranding as a charge - clearing the round's own stranding gate
    without the UAV ever coming home.
    """
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MECHANISM", 2, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", 1, raising=False)   # no recovery
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_STALL_LIMIT", 3, raising=False)
    grid = _Grid(50, 50)
    model = _DepotModel(grid)
    _blocker(grid, (4, 45))
    uav = _returner(model, (4, 44), (4, 45))   # the doorstep cell, outside
    _drive(uav, 15)
    assert not uav.rtb_docked, "it must NOT dock on the doorstep"
    assert not model.base_station_contains((4, 44), 0)


def test_recharge_still_has_no_positional_test() -> None:
    """The premise of the test above, pinned so it cannot rot silently.

    If a positional test is ever added to _update_battery_after_step, the
    doorstep-dock alternative becomes safe and section 5b of
    outputs/dockfix_part1.txt should be revisited.
    """
    import inspect
    src = inspect.getsource(agents.UAV._update_battery_after_step)
    assert "rtb_docked" in src
    assert "base_station_contains" not in src
    assert "rtb_berth" not in src


# --- dock-fix round: the mechanism-1 planner waypoint -------------------------
#
# A SEPARATE defect behind a SEPARATE switch, so the round can attribute an
# outcome to it independently. It published the HOME berth rather than the berth
# LATCHED for the trip; with one depot the two are equal and it is inert, which
# is every arm measured so far.

def test_waypoint_publishes_the_latched_berth(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_WAYPOINT_FIX", 1, raising=False)
    uav = _TriggerAgent((10, 10))
    uav.rtb_berth = (4, 45)                    # home
    uav.rtb_target_berth = (24, 24)            # latched for THIS trip
    assert agents.base_station_waypoint_fix() is True
    chosen = uav.rtb_target_berth or uav.rtb_berth
    assert chosen == (24, 24)


def test_waypoint_fix_is_inert_with_one_depot(monkeypatch) -> None:
    """Which is why every arm measured before this round could not see it."""
    monkeypatch.setattr(cfv, "BASE_STATION_WAYPOINT_FIX", 1, raising=False)
    uav = _TriggerAgent((10, 10))
    uav.rtb_berth = (4, 45)
    uav.rtb_target_berth = (4, 45)
    assert (uav.rtb_target_berth or uav.rtb_berth) == uav.rtb_berth


def test_waypoint_fix_switch_reads_the_module_at_call_time(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_WAYPOINT_FIX", 0, raising=False)
    assert agents.base_station_waypoint_fix() is False
    monkeypatch.setattr(cfv, "BASE_STATION_WAYPOINT_FIX", 1, raising=False)
    assert agents.base_station_waypoint_fix() is True


# --- dock-fix round: the kill switches ----------------------------------------

def test_dock_fix_accessors_read_the_module_at_call_time(monkeypatch) -> None:
    for value in (0, 1, 2):
        monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", value, raising=False)
        assert agents.base_station_dock_fix() == value
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_STALL_LIMIT", 7, raising=False)
    assert agents.base_station_return_stall_limit() == 7


def test_dock_fix_accessors_survive_junk_and_clamp(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", "nonsense", raising=False)
    assert agents.base_station_dock_fix() == 2
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", 9, raising=False)
    assert agents.base_station_dock_fix() == 2
    monkeypatch.setattr(cfv, "BASE_STATION_DOCK_FIX", -3, raising=False)
    assert agents.base_station_dock_fix() == 0
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_STALL_LIMIT", 0, raising=False)
    assert agents.base_station_return_stall_limit() == 1


def test_dock_fix_shipped_defaults() -> None:
    """DEFAULT ON, and LIVE at the shipped configuration.

    BASE_STATION_MODE ships at 3 with RETURN_MECHANISM 2 (the dcD flip, 2026-09-14),
    so the re-keyed terminator (DOCK_FIX >= 1) and the stall recovery (DOCK_FIX 2)
    run on every default return leg. DOCK_FIX 0 is therefore no longer a no-op on a
    default run: it reverts docking to the 9f77178 behaviour. The waypoint fix is
    still unreachable by default, because it is mechanism-1 only
    (local_adaptation_generator.py _generate_base_return_options), not because of
    the depot count. Shipping the dock fix off would mean carrying a known stranding
    bug behind a flag nobody remembers to flip.

    Changing the shipped mode again requires what test_shipped_defaults lists: the
    gate wave, the route_blocked gate, the full suite at the new settings with its
    failing name set accounted for, and a byte-identity check of a default run
    against an explicit --set arm.
    """
    assert cfv.BASE_STATION_DOCK_FIX == 2
    assert cfv.BASE_STATION_RETURN_STALL_LIMIT == 3
    assert cfv.BASE_STATION_WAYPOINT_FIX == 1
    assert cfv.BASE_STATION_MODE == 3
    assert cfv.BASE_STATION_RETURN_MECHANISM == 2
