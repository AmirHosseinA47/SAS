"""Carrying-leg round: the three switches FF_EXIT_LEG_MODE, FF_EXIT_LEG_HOLD and
FF_EXIT_LEG_SERVED (one per pre-existing defect of a firefighter's trip home with a
victim).

Design: outputs/carryleg_part1.txt (sections 2-5; the test list is 8.2). Tooling
contract: outputs/_cl_tooling_spec.txt section J. SERVED rung 2 is NOT built
(maintainer D-1): FF_EXIT_LEG_SERVED is 0/1, and an exact 2 is junk that maps to 1.

Drives the real WildFireModel with its map quieted, in the style of
tests/test_firefighter_fire_mechanic.py and tests/test_victim_fire_flight.py. A test
lays out exactly which cells burn or smoke, then calls one firefighter's advance() or
one model method directly. No test calls model.step(), so nothing here depends on the
random ignition. Every behaviour test passes ALL THREE switches explicitly through
apply_scenario_config, so none of them depends on the shipped default. The shipped
default is pinned only in the switches section.

A carrier is always made by the real path: an executor "assign", the unit on the
victim's cell, and one advance() whose own pickup branch sets `exiting` and the
fire-blind `exit_target`. Fire and smoke are laid AFTER the pickup.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import io
import os
import random
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.planning import rescue_planner
from wildfire_model import PhysicalRescueCommand, WildFireModel

FF_A = "ff_unit_0"
FF_B = "ff_unit_1"
FF_C = "ff_unit_2"
V0 = "victim_0"
V1 = "victim_1"

_SWITCHES = ("FF_EXIT_LEG_MODE", "FF_EXIT_LEG_HOLD", "FF_EXIT_LEG_SERVED")
_CONFIG_NAMES = _SWITCHES + ("SYSTEM_RANDOM",)


def _accessor_values():
    """The three accessors' values, with their types (False and 0 must not compare equal)."""
    values = (agents.ff_exit_leg_mode(), agents.ff_exit_leg_hold(), agents.ff_exit_leg_served())
    return tuple((value, type(value)) for value in values)


@pytest.fixture(autouse=True)
def _restore_module_config():
    """apply_scenario_config mutates module globals; put them back for other tests.

    Copied from tests/test_firefighter_fire_mechanic.py, over this round's three switches
    and SYSTEM_RANDOM on cfv and wf, plus agents.random. A name that was absent before
    the test is deleted again. The teardown canary then asserts that the three accessors
    return exactly what they returned at setup, so a leaked switch fails HERE, in any
    test order, with no conftest.
    """
    saved = {}
    for mod in (cfv, wf):
        saved[mod] = {name: (hasattr(mod, name), getattr(mod, name, None)) for name in _CONFIG_NAMES}
    saved_agents_random = agents.random
    setup_values = _accessor_values()
    yield
    for mod, values in saved.items():
        for name, (present, value) in values.items():
            if present:
                setattr(mod, name, value)
            elif hasattr(mod, name):
                delattr(mod, name)
    agents.random = saved_agents_random
    assert _accessor_values() == setup_values, "a carrying-leg switch leaked out of the test"


# ---------------------------------------------------------------------------
# construction helpers
# ---------------------------------------------------------------------------

def _model(mode=0, hold=0, served=0, seed: int = 101) -> WildFireModel:
    """A real, seeded model with the map quieted and ALL THREE switches passed explicitly."""
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv,
        wf,
        FF_EXIT_LEG_MODE=mode,
        FF_EXIT_LEG_HOLD=hold,
        FF_EXIT_LEG_SERVED=served,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False
    _quiet_map(model)
    return model


def _quiet_map(model: WildFireModel) -> None:
    """Every cell unburnt vegetation with fuel 8 and no smoke."""
    for agent in model.schedule.agents:
        if type(agent) is agents.Fire:
            agent.burning = False
            agent.burnt = False
            agent.has_burned = False
            agent.next_burning_state = False
            agent.fuel = 8
            agent.smoke.smoke = False


def _fire(model: WildFireModel, cell) -> agents.Fire:
    for agent in model.grid.get_cell_list_contents([tuple(cell)]):
        if type(agent) is agents.Fire:
            return agent
    raise AssertionError("no Fire agent at %s" % (cell,))


def _ignite(model: WildFireModel, *cells) -> None:
    for cell in cells:
        fire = _fire(model, cell)
        fire.burning = True
        fire.has_burned = True


def _smoke(model: WildFireModel, *cells) -> None:
    for cell in cells:
        _fire(model, cell).smoke.smoke = True


def _neighbours(model: WildFireModel, cell):
    cx, cy = cell
    out = []
    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nxt = (cx + ox, cy + oy)
        if not model.grid.out_of_bounds(nxt):
            out.append(nxt)
    return out


def _enclose(model: WildFireModel, cell) -> None:
    """Every in-grid 4-neighbour of `cell` burns; the cell itself does not."""
    _ignite(model, *_neighbours(model, cell))


def _cell(agent):
    return (int(agent.pos[0]), int(agent.pos[1]))


def _pickup(model: WildFireModel, cell, ff_id: str = FF_A, vid: str = V0):
    """A carrier made by the real path: executor assign, the unit on the victim's cell,
    and one advance() - the unit's own pickup branch sets `exiting` and `exit_target`."""
    cell = tuple(cell)
    marker = model.victim_marker_agents[vid]
    model.grid.move_agent(marker, cell)
    state = model.managed_victims[vid]
    state.confirmed = True
    state.status = "confirmed"
    marker.status = "confirmed"
    ff = model.firefighter_marker_agents[ff_id]
    model.grid.move_agent(ff, cell)
    result = model._execute_physical_rescue_via_executor(
        PhysicalRescueCommand(
            action="assign",
            victim_id=vid,
            firefighter_id=ff_id,
            reason="test_initial",
            metadata={},
        )
    )
    assert result.get("success") is True
    ff.advance()
    assert ff.exiting is True and _cell(ff) == cell and ff.rescued_victim is marker
    return ff, marker


def _assign(model: WildFireModel, ff_id: str, vid: str, ff_cell, victim_cell) -> agents.Firefighter:
    """An APPROACHING unit: assigned through the executor, not on its victim's cell."""
    marker = model.victim_marker_agents[vid]
    model.grid.move_agent(marker, tuple(victim_cell))
    state = model.managed_victims[vid]
    state.confirmed = True
    state.status = "confirmed"
    marker.status = "confirmed"
    ff = model.firefighter_marker_agents[ff_id]
    model.grid.move_agent(ff, tuple(ff_cell))
    result = model._execute_physical_rescue_via_executor(
        PhysicalRescueCommand(
            action="assign",
            victim_id=vid,
            firefighter_id=ff_id,
            reason="test_initial",
            metadata={},
        )
    )
    assert result.get("success") is True
    return ff


def _carry_to(model: WildFireModel, ff, marker, cell) -> None:
    """Put a carrier and its victim on `cell` together (a test shortcut for a walk)."""
    model.grid.move_agent(ff, tuple(cell))
    model.grid.move_agent(marker, tuple(cell))


def _kill(model: WildFireModel, *ff_ids: str) -> None:
    for ff_id in ff_ids:
        ff = model.firefighter_marker_agents[ff_id]
        ff.dead = True
        ff.status = "dead"


def _retire_victims(model: WildFireModel, keep=()) -> None:
    """Every victim but `keep` dead, so it is terminal and out of every streak."""
    for vid, marker in model.victim_marker_agents.items():
        if vid in keep:
            continue
        marker.status = "dead"
        state = model.managed_victims.get(vid)
        if state is not None:
            state.status = "dead"
            state.rescued = False


def _record_commands(model: WildFireModel) -> list:
    """Every physical rescue command applied from now on, WITH its metadata.

    The executor's audit list drops metadata, and reset_victim_pending is exactly what
    the casualty guard changes, so the model's single entry point is wrapped on the
    instance (pass-through: same arguments, same result).
    """
    seen: list = []
    original = model.apply_physical_rescue_command

    def recorder(cmd):
        seen.append(
            (
                str(cmd.action),
                str(cmd.victim_id or ""),
                str(cmd.firefighter_id or ""),
                str(cmd.reason or ""),
                dict(cmd.metadata or {}),
            )
        )
        return original(cmd)

    model.apply_physical_rescue_command = recorder
    return seen


def _events(model: WildFireModel, event_type: str, vid: str | None = None) -> list:
    out = []
    for event in list(getattr(model, "_rescue_event_log", []) or []):
        if event.get("event_type") != event_type:
            continue
        if vid is not None and event.get("victim_id") != vid:
            continue
        out.append(event)
    return out


def _spy_flags(monkeypatch) -> list:
    """Every flags dict _update_unreachable_victims hands the planner, copied per call."""
    calls: list = []
    original = wf.unreachable_escape_victims

    def spy(flags, *args, **kwargs):
        calls.append({vid: dict(entry) for vid, entry in flags.items()})
        return original(flags, *args, **kwargs)

    monkeypatch.setattr(wf, "unreachable_escape_victims", spy)
    return calls


def _walk(ff, marker, limit: int):
    """Advance a carrier until it completes or `limit` advances; the cells it stood on."""
    cells = []
    tiers = []
    for _ in range(limit):
        ff.advance()
        if ff.rescue_completed:
            break
        cells.append(_cell(ff))
        tiers.append(ff._last_move_tier)
        assert _cell(marker) == _cell(ff), "the carried victim must move with its carrier"
    return cells, tiers


def _unit_state(ff) -> dict:
    """vars(unit) without the object references that differ between two models."""
    state = {k: v for k, v in vars(ff).items() if k not in ("model", "rescued_victim")}
    rv = getattr(ff, "rescued_victim", None)
    state["rescued_victim_id"] = getattr(rv, "victim_id", None) if rv is not None else None
    return state


class _NoRNG:
    """Any attribute read - random(), randint(), choice(), getstate() - fails the test."""

    def __getattr__(self, name):
        raise AssertionError("an RNG was touched: .%s" % name)


# ---------------------------------------------------------------------------
# the switches
# ---------------------------------------------------------------------------

# RE-RUNNING A FLIP OF THESE SWITCHES: the constant in common_fixed_variables.py, the
# getattr default in the agents.py accessor (it IS the shipped value, so a missing
# attribute agrees with the file), the junk mapping (while a switch ships 0, junk arms
# a named non-zero value; after the flip it takes the shipped value), and the pins in
# test_every_switch_ships_zero_and_a_missing_attribute_is_the_shipped_zero below.

_INF = float("inf")
_NAN = float("nan")
_MISSING = object()

# (raw value, mode, hold, served). Only an exact integral zero disables; anything that is
# not an exact 0/1/2 arms MODE at 1, anything but an exact 0 arms HOLD, and anything but
# an exact 0/1 arms SERVED at 1 - including an exact 2 (rung 2 is not built, D-1).
_MATRIX = [
    (0, 0, False, 0),
    (0.0, 0, False, 0),
    ("0", 0, False, 0),
    (" 0 ", 0, False, 0),
    (False, 0, False, 0),
    (Decimal("0"), 0, False, 0),
    (1, 1, True, 1),
    (True, 1, True, 1),
    (2, 2, True, 1),
    (" 2 ", 2, True, 1),
    (Decimal("2"), 2, True, 1),
    (Fraction(4, 2), 2, True, 1),
    (0.5, 1, True, 1),
    ("0.5", 1, True, 1),
    ("2.0", 1, True, 1),
    (-1, 1, True, 1),
    (3, 1, True, 1),
    (None, 1, True, 1),
    ("", 1, True, 1),
    ("off", 1, True, 1),
    (_INF, 1, True, 1),
    (-_INF, 1, True, 1),
    (_NAN, 1, True, 1),
    (Decimal("0.5"), 1, True, 1),
    (Fraction(1, 2), 1, True, 1),
    ([], 1, True, 1),
    (_MISSING, 0, False, 0),
]


def _matrix_id(raw) -> str:
    if raw is _MISSING:
        return "missing"
    return "%s:%r" % (type(raw).__name__, raw)


@pytest.mark.parametrize(
    "raw,mode,hold,served", _MATRIX, ids=[_matrix_id(row[0]) for row in _MATRIX]
)
def test_accessor_edge_matrix(monkeypatch, raw, mode, hold, served) -> None:
    """Each switch read alone, the other two left alone. Never raises; exact types."""
    for name, accessor, expected in (
        ("FF_EXIT_LEG_MODE", agents.ff_exit_leg_mode, mode),
        ("FF_EXIT_LEG_HOLD", agents.ff_exit_leg_hold, hold),
        ("FF_EXIT_LEG_SERVED", agents.ff_exit_leg_served, served),
    ):
        if raw is _MISSING:
            monkeypatch.delattr(cfv, name, raising=False)
        else:
            monkeypatch.setattr(cfv, name, raw, raising=False)
        got = accessor()
        assert got == expected, (name, raw, got)
        assert type(got) is type(expected), (name, raw, type(got))
        monkeypatch.undo()


def test_every_switch_ships_zero_and_a_missing_attribute_is_the_shipped_zero(monkeypatch) -> None:
    """SHIPPED: all three 0 until the round's gate is passed. See the flip note above."""
    assert cfv.FF_EXIT_LEG_MODE == 0
    assert cfv.FF_EXIT_LEG_HOLD == 0
    assert cfv.FF_EXIT_LEG_SERVED == 0
    assert agents.EXIT_LEG_MODE_JUNK == 1
    assert agents.EXIT_LEG_SERVED_JUNK == 1
    for name in _SWITCHES:
        monkeypatch.delattr(cfv, name, raising=False)
    assert agents.ff_exit_leg_mode() == 0
    assert agents.ff_exit_leg_hold() is False
    assert agents.ff_exit_leg_served() == 0


def test_switches_are_read_at_call_time_through_cfv_only(monkeypatch) -> None:
    """The dead-input test. The model and the carrier are BUILT FIRST, all at 0, and only
    then does apply_scenario_config write the override - the harness's real order. A
    switch frozen at import or at construction fails this. The star-imported copies in
    agents must be ignored. (apply_scenario_config below rewrites wildfire_model's copies
    before the model reads anything, so the model side is pinned by the next test.)"""
    model = _model(mode=0, hold=0, served=0)
    ff, marker = _pickup(model, (3, 25))
    assert ff.exit_target == (0, 25)

    # the accessors ignore agents' and wildfire_model's star-imported copies
    monkeypatch.setattr(agents, "FF_EXIT_LEG_MODE", 2, raising=False)
    monkeypatch.setattr(agents, "FF_EXIT_LEG_HOLD", 1, raising=False)
    monkeypatch.setattr(agents, "FF_EXIT_LEG_SERVED", 1, raising=False)
    wf.FF_EXIT_LEG_MODE = 2
    wf.FF_EXIT_LEG_HOLD = 1
    wf.FF_EXIT_LEG_SERVED = 1
    assert agents.ff_exit_leg_mode() == 0
    assert agents.ff_exit_leg_hold() is False
    assert agents.ff_exit_leg_served() == 0

    for value in (0, 1, 2, 0):
        apply_scenario_config(cfv, wf, FF_EXIT_LEG_MODE=value)
        assert agents.ff_exit_leg_mode() == value
    for value, expected in ((1, True), (0, False)):
        apply_scenario_config(cfv, wf, FF_EXIT_LEG_HOLD=value)
        assert agents.ff_exit_leg_hold() is expected
    for value, expected in ((1, 1), (2, 1), (0, 0)):
        apply_scenario_config(cfv, wf, FF_EXIT_LEG_SERVED=value)
        assert agents.ff_exit_leg_served() == expected

    # ...and the model built at 0 obeys an override written after its construction
    _carry_to(model, ff, marker, (0, 28))
    apply_scenario_config(cfv, wf, FF_EXIT_LEG_MODE=1)
    ff.advance()
    assert ff.rescue_completed is True
    assert ff.movement_reason["key_factors"] == {"exit_target": (0, 25), "exit_cell": (0, 28)}

    held = _model(mode=0, hold=0, served=0)
    carrier, _victim = _pickup(held, (20, 25))
    _enclose(held, (20, 25))
    apply_scenario_config(cfv, wf, FF_EXIT_LEG_HOLD=1)
    carrier.advance()
    assert carrier.exiting is True and carrier.status != "route_blocked"
    assert carrier._last_move_tier == agents.EXIT_LEG_HOLD_TIER

    served = _model(mode=0, hold=0, served=0)
    _pickup(served, (20, 25))
    calls = _spy_flags(monkeypatch)
    apply_scenario_config(cfv, wf, FF_EXIT_LEG_SERVED=1)
    served._update_unreachable_victims()
    assert calls[-1][V0].get("in_custody") is True


@pytest.mark.parametrize("cfv_value,wf_copy", ((0, 1), (1, 0)))
@pytest.mark.parametrize("name", ("FF_EXIT_LEG_HOLD", "FF_EXIT_LEG_SERVED"))
def test_the_model_side_reads_hold_and_served_through_cfv_only(monkeypatch, name, cfv_value, wf_copy) -> None:
    """wildfire_model's HOLD start and SERVED custody gate read cfv (through the agents
    accessors), never wildfire_model's star-imported copies. One switch at a time, cfv and
    the copy DISAGREE (monkeypatch on one module each, never apply_scenario_config, which
    writes both); the other two stay 0 in both. The board: an enclosed carrier, no other
    live unit, a streak of 19. The cfv value alone decides: 1 is the hold start (HOLD) or
    the custody key (SERVED) and the streak resets to 0; 0 is today's pass - the streak
    reaches 20 and no flags dict has an in_custody key."""
    model, _ff, _marker = _enclosed_carrier(hold=0)
    _kill(model, FF_B, FF_C)
    monkeypatch.setattr(cfv, name, cfv_value)
    monkeypatch.setattr(wf, name, wf_copy, raising=False)
    assert (agents.ff_exit_leg_hold(), agents.ff_exit_leg_served()) == (
        bool(cfv_value) and name == "FF_EXIT_LEG_HOLD",
        cfv_value if name == "FF_EXIT_LEG_SERVED" else 0,
    )
    calls = _spy_flags(monkeypatch)
    model._unreachable_geo_streak = {V0: 19}

    model._update_unreachable_victims()

    assert model._unreachable_geo_streak[V0] == (0 if cfv_value else 20)
    if cfv_value and name == "FF_EXIT_LEG_SERVED":
        assert calls[-1][V0]["in_custody"] is True
    else:
        assert "in_custody" not in calls[-1][V0]


# ---------------------------------------------------------------------------
# D1 - FF_EXIT_LEG_MODE: completion on any boundary cell / the clean-cell search
# ---------------------------------------------------------------------------

def _exit_walk(mode):
    """A carrier picked up at (3, 25) walks the fire-free row to its exit (0, 25)."""
    model = _model(mode=mode)
    ff, marker = _pickup(model, (3, 25))
    assert ff.exit_target == (0, 25)
    log_before = len(model._movement_transition_log)
    cells, tiers = _walk(ff, marker, 10)
    return model, ff, marker, cells, tiers, model._movement_transition_log[log_before:]


@pytest.mark.parametrize("mode", (0, 1, 2))
def test_the_exit_cell_completes_with_todays_record_at_every_mode(mode) -> None:
    """The walk to a clean exit and its completion are identical at 0, 1 and 2, compared
    with a mode-0 run on the same board: the cells, the completion record
    (movement_reason), the transition-log entries and every other unit attribute. The one
    difference is the tier label of a mode-2 step: EXIT_LEG_PATH_TIER instead of today's
    tier 1."""
    model, ff, marker, cells, tiers, log = _exit_walk(mode)
    _ref_model, ref_ff, _ref_marker, ref_cells, ref_tiers, ref_log = _exit_walk(0)

    assert cells == ref_cells == [(2, 25), (1, 25), (0, 25)]
    assert ff.rescue_completed is True
    assert ff in model._agents_pending_removal and marker in model._agents_pending_removal
    assert ff.movement_reason["fine_category"] == "exiting_complete"
    assert ff.movement_reason["key_factors"] == {"exit_target": (0, 25)}
    assert ff.movement_reason == ref_ff.movement_reason
    assert log == ref_log
    unit, ref_unit = _unit_state(ff), _unit_state(ref_ff)
    assert unit.pop("_last_move_tier") == tiers[-1] and ref_unit.pop("_last_move_tier") == 1
    assert unit == ref_unit
    assert ref_tiers == [1, 1, 1]
    assert tiers == ([agents.EXIT_LEG_PATH_TIER] * 3 if mode == 2 else ref_tiers)


@pytest.mark.parametrize("mode", (0, 1, 2))
def test_a_non_exit_boundary_cell_completes_only_at_a_nonzero_mode(mode) -> None:
    """Mode 0 pins today: only the exit cell fixed at pickup completes."""
    model = _model(mode=mode)
    ff, marker = _pickup(model, (3, 25))
    _carry_to(model, ff, marker, (0, 28))  # on the boundary, three cells from the exit

    ff.advance()

    if mode == 0:
        assert ff.rescue_completed is False
        assert _cell(ff) == (0, 27) and _cell(marker) == (0, 27)
        assert ff not in getattr(model, "_agents_pending_removal", [])
    else:
        assert ff.rescue_completed is True
        assert _cell(ff) == (0, 28)
        assert ff in model._agents_pending_removal and marker in model._agents_pending_removal
        assert ff.exit_target == (0, 25), "exit_target is never rewritten"
        assert ff.movement_reason["key_factors"] == {
            "exit_target": (0, 25),
            "exit_cell": (0, 28),
        }


def _barrier(mode):
    """The livelock ingredient: the improving cell toward the exit is smoky."""
    model = _model(mode=mode)
    ff, marker = _pickup(model, (5, 25))
    assert ff.exit_target == (0, 25)
    _smoke(model, (4, 25))
    return model, ff, marker


@pytest.mark.parametrize("mode", (0, 1))
def test_modes_zero_and_one_reproduce_the_tier_three_step_back(mode) -> None:
    """Mode 0 pins today's memoryless cycle, and mode 1 moves exactly like mode 0."""
    _model_, ff, marker = _barrier(mode)

    cells, tiers = _walk(ff, marker, 8)

    assert cells == [(6, 25), (5, 25)] * 4
    assert tiers == [3, 1] * 4
    assert ff.rescue_completed is False
    assert ff.exit_target == (0, 25)


def test_mode_two_leaves_the_barrier_on_the_first_step_of_a_clean_path() -> None:
    _model_, ff, marker = _barrier(2)

    cells, tiers = _walk(ff, marker, 20)

    assert cells == [(5, 26), (4, 26), (3, 26), (2, 26), (1, 26), (0, 26)]
    assert tiers == [agents.EXIT_LEG_PATH_TIER] * 6
    assert ff.rescue_completed is True
    assert ff.exit_target == (0, 25)
    assert ff.movement_reason["key_factors"] == {"exit_target": (0, 25), "exit_cell": (0, 26)}


_CORRIDOR = [(10, 26), (10, 27), (10, 28), (10, 29), (10, 30)] + [(x, 30) for x in range(9, -1, -1)]


def test_mode_two_walks_a_constructed_clean_corridor() -> None:
    """Every cell smokes except the start and one L-shaped corridor to the boundary. The
    fixed exit (0, 25) is straight ahead through smoke; the carrier takes the corridor."""
    model = _model(mode=2)
    ff, marker = _pickup(model, (10, 25))
    assert ff.exit_target == (0, 25)
    keep = set(_CORRIDOR) | {(10, 25)}
    for agent in model.schedule.agents:
        if type(agent) is agents.Fire and _cell(agent) not in keep:
            agent.smoke.smoke = True

    cells, tiers = _walk(ff, marker, 40)

    assert cells == _CORRIDOR
    assert set(tiers) == {agents.EXIT_LEG_PATH_TIER}
    assert ff._last_move_risk == 0
    assert ff.rescue_completed is True
    assert ff.exit_target == (0, 25)
    assert ff.movement_reason["key_factors"] == {"exit_target": (0, 25), "exit_cell": (0, 30)}


@pytest.mark.parametrize("hazard", (None, "smoky", "fire_adjacent"))
def test_mode_two_never_takes_a_smoky_or_fire_adjacent_goal(hazard) -> None:
    """The goal test runs at discovery AFTER the clean test: the exit one step away is
    refused when it smokes or touches fire, and the next clean boundary cell is taken."""
    model = _model(mode=2)
    ff, marker = _pickup(model, (1, 25))
    assert ff.exit_target == (0, 25)
    if hazard == "smoky":
        _smoke(model, (0, 25))
    elif hazard == "fire_adjacent":
        _ignite(model, (0, 24))  # (0, 25) is fire-adjacent, not burning

    cells, _tiers = _walk(ff, marker, 10)

    if hazard is None:
        assert cells == [(0, 25)]
        assert ff.movement_reason["key_factors"] == {"exit_target": (0, 25)}
    else:
        assert cells == [(1, 26), (0, 26)]
        assert ff.movement_reason["key_factors"] == {
            "exit_target": (0, 25),
            "exit_cell": (0, 26),
        }
    assert ff.rescue_completed is True


@pytest.mark.parametrize("start_hazard", ("smoky", "fire_adjacent"))
def test_mode_two_searches_from_a_smoky_or_fire_adjacent_start(start_hazard) -> None:
    """The start cell is exempt from every test, so a hazardous start still searches."""
    model = _model(mode=2)
    ff, marker = _pickup(model, (5, 25))
    if start_hazard == "smoky":
        _smoke(model, (5, 25))
    else:
        _ignite(model, (6, 25))

    assert ff._exit_leg_step() == "path"
    assert _cell(ff) == (4, 25)
    assert ff._last_move_tier == agents.EXIT_LEG_PATH_TIER
    assert ff._last_move_risk == 0


def test_mode_two_from_a_burning_start_is_todays_step_bit_for_bit() -> None:
    """Every neighbour of a burning cell is fire-adjacent, so no clean path exists and
    the step is today's _move_toward(exit_target): the same cell, tier, risk, status,
    movement record and transition-log entry as mode 0 on the same board."""
    outcomes = {}
    for mode in (0, 2):
        model = _model(mode=mode)
        ff, marker = _pickup(model, (5, 25))
        _ignite(model, (5, 25))
        _smoke(model, (4, 25))
        log_before = len(model._movement_transition_log)
        ff.advance()
        outcomes[mode] = (
            _unit_state(ff),
            _cell(marker),
            model._movement_transition_log[log_before:],
        )
    assert outcomes[2] == outcomes[0]
    assert outcomes[0][0]["pos"] == (6, 25) and outcomes[0][0]["_last_move_tier"] == 4

    model = _model(mode=2)
    ff, _marker = _pickup(model, (5, 25))
    _ignite(model, (5, 25))
    assert ff._exit_leg_step() == "fallback"


@pytest.mark.parametrize(
    "start,smoky,expected",
    [
        ((1, 1), None, (0, 1)),  # -x is searched before -y
        ((1, 1), (0, 1), (1, 0)),
        ((48, 48), None, (49, 48)),  # +x is searched before +y
        ((48, 48), (49, 48), (48, 49)),
    ],
)
def test_mode_two_near_a_corner_breaks_ties_by_the_search_order(start, smoky, expected) -> None:
    """Two boundary cells one step away: EXIT_LEG_SEARCH_ORDER (+x, -x, +y, -y) decides.
    The step lands on a boundary cell, so the next advance completes there."""
    model = _model(mode=2)
    ff, marker = _pickup(model, start)
    if smoky is not None:
        _smoke(model, smoky)

    cells, _tiers = _walk(ff, marker, 5)

    assert cells == [expected]
    assert ff.rescue_completed is True


def test_kernel_ties_follow_its_order_argument() -> None:
    """The pure kernel: default order, an explicit order, goal-after-passable, None."""
    start = (5, 5)
    everywhere = dict(
        passable=lambda c: True,
        is_boundary=lambda c: c != start,
        out_of_bounds=lambda c: False,
    )
    assert agents.exit_leg_first_step(start, **everywhere) == (6, 5)
    for offset in agents.EXIT_LEG_SEARCH_ORDER:
        order = (offset,) + tuple(o for o in agents.EXIT_LEG_SEARCH_ORDER if o != offset)
        assert agents.exit_leg_first_step(start, order=order, **everywhere) == (
            start[0] + offset[0],
            start[1] + offset[1],
        )
    # a goal that is not passable is never a goal; the next one in order is taken
    assert agents.exit_leg_first_step(
        start,
        passable=lambda c: c != (6, 5),
        is_boundary=lambda c: c != start,
        out_of_bounds=lambda c: False,
    ) == (4, 5)
    # the start itself is never tested
    assert agents.exit_leg_first_step(
        start,
        passable=lambda c: c != start,
        is_boundary=lambda c: c == (5, 7),
        out_of_bounds=lambda c: not (0 <= c[0] < 11 and 0 <= c[1] < 11),
    ) == (5, 6)
    # no path: None
    assert agents.exit_leg_first_step(
        start,
        passable=lambda c: False,
        is_boundary=lambda c: True,
        out_of_bounds=lambda c: False,
    ) is None


def test_search_order_is_its_own_constant(monkeypatch) -> None:
    """EXIT_LEG_SEARCH_ORDER is (+x, -x, +y, -y), written as its own literal, not a
    reference to ORTHOGONAL_OFFSETS (the victim-flee tie-break): a future flee change must
    not move mode 2.

    NOT asserted: `EXIT_LEG_SEARCH_ORDER is not ORTHOGONAL_OFFSETS`. The two literals are
    equal, and CPython merges equal constant tuples compiled in one module, so the two
    names ARE the same object today although neither refers to the other. Identity is
    therefore no evidence either way. Independence is pinned instead at the source (the
    assignment is a tuple literal naming nothing) and by behaviour (rebinding
    ORTHOGONAL_OFFSETS moves neither the boundary test nor the search).
    """
    assert agents.EXIT_LEG_SEARCH_ORDER == ((1, 0), (-1, 0), (0, 1), (0, -1))
    assert agents.exit_leg_first_step.__defaults__ == (agents.EXIT_LEG_SEARCH_ORDER,)

    tree = ast.parse(Path(agents.__file__).read_text(encoding="utf-8"))
    values = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "EXIT_LEG_SEARCH_ORDER" for t in node.targets)
    ]
    assert len(values) == 1
    assert isinstance(values[0], ast.Tuple)
    assert not [n for n in ast.walk(values[0]) if isinstance(n, ast.Name)]

    monkeypatch.setattr(agents, "ORTHOGONAL_OFFSETS", ((0, -1), (0, 1), (-1, 0), (1, 0)))
    model = _model(mode=2)
    ff, marker = _pickup(model, (1, 1))
    assert ff._on_grid_boundary((0, 1)) is True and ff._on_grid_boundary((1, 1)) is False
    cells, _tiers = _walk(ff, marker, 5)
    assert cells == [(0, 1)]


def test_mode_two_is_deterministic_and_draws_no_rng(monkeypatch) -> None:
    """Path steps, a fallback step, a mode-2 completion, a HOLD and the SERVED pass, with
    every RNG the model and its agents can reach replaced by one that fails on use: the
    random module and the star-imported SYSTEM_RANDOM copy in agents and in
    wildfire_model, cfv.SYSTEM_RANDOM, and the mesa model's own random (which the agents'
    self.random reads). src_extension imports no RNG."""
    trajectories = []
    for _ in range(2):
        model, ff, marker = _barrier(2)
        trajectories.append(_walk(ff, marker, 20)[0])
    assert trajectories[0] == trajectories[1]

    model = _model(mode=2, hold=1, served=1)
    ff, marker = _pickup(model, (5, 25))
    _smoke(model, (4, 25))
    for owner, name in (
        (agents, "random"),
        (agents, "SYSTEM_RANDOM"),
        (cfv, "SYSTEM_RANDOM"),
        (wf, "SYSTEM_RANDOM"),
        (wf, "random"),
    ):
        monkeypatch.setattr(owner, name, _NoRNG())
    monkeypatch.setattr(model, "random", _NoRNG(), raising=False)

    ff.advance()  # a path step
    assert ff._last_move_tier == agents.EXIT_LEG_PATH_TIER
    _enclose(model, _cell(ff))
    ff.advance()  # no clean path -> fallback -> every neighbour burns -> HOLD
    assert ff._last_move_tier == agents.EXIT_LEG_HOLD_TIER
    model._update_unreachable_victims()  # the HOLD start and the SERVED custody set
    _quiet_map(model)
    _carry_to(model, ff, marker, (0, 20))
    ff.advance()  # a completion off the exit cell
    assert ff.rescue_completed is True


def test_a_step_changes_nothing_but_the_position_and_the_two_labels() -> None:
    """No new unit attribute and no new model attribute; nothing stored between steps.
    Rebinding is caught by the shallow snapshot, and an IN-PLACE change (a dict or list
    attribute edited without rebinding, which the shallow snapshot shares) by a deep copy
    of every attribute but the model, the carried victim, pos and the two labels."""
    model = _model(mode=2)
    ff, marker = _pickup(model, (5, 25))
    _smoke(model, (4, 25))
    ff._last_move_tier = 0
    ff._last_move_risk = 7
    unit_before = dict(vars(ff))
    moved = ("model", "rescued_victim", "pos", "_last_move_tier", "_last_move_risk")
    deep_before = copy.deepcopy({k: v for k, v in vars(ff).items() if k not in moved})
    model_keys_before = set(vars(model))

    assert ff._exit_leg_step() == "path"

    unit_after = dict(vars(ff))
    assert set(unit_after) == set(unit_before)
    changed = {k for k in unit_after if unit_after[k] is not unit_before[k] and unit_after[k] != unit_before[k]}
    assert changed == {"pos", "_last_move_tier", "_last_move_risk"}
    assert {k: v for k, v in vars(ff).items() if k not in moved} == deep_before
    assert ff.model is model and ff.rescued_victim is marker
    assert set(vars(model)) == model_keys_before

    # the fallback branch adds nothing either
    model = _model(mode=2)
    ff, _marker = _pickup(model, (5, 25))
    _ignite(model, (5, 25))
    unit_keys = set(vars(ff))
    model_keys_before = set(vars(model))
    assert ff._exit_leg_step() == "fallback"
    assert set(vars(ff)) == unit_keys
    assert set(vars(model)) == model_keys_before


@pytest.mark.parametrize("assigned,expected", ((True, "assigned"), (False, "available")))
def test_a_route_blocked_carrier_is_relabelled_on_a_path_step(assigned, expected) -> None:
    """_move_toward's own tail, applied to a path step: a carrier is never left invisible
    to the victim lookup."""
    model = _model(mode=2)
    ff, marker = _pickup(model, (5, 25))
    ff.status = "route_blocked"
    ff.assigned = assigned
    assert model._find_active_firefighter_for_victim(V0, marker) is None

    assert ff._exit_leg_step() == "path"

    assert ff.status == expected
    if assigned:
        assert model._find_active_firefighter_for_victim(V0, marker) == (FF_A, ff)


# ---------------------------------------------------------------------------
# D2 - FF_EXIT_LEG_HOLD: an enclosed carrier holds its cell and keeps its victim
# ---------------------------------------------------------------------------

def _enclosed_carrier(hold):
    model = _model(hold=hold)
    ff, marker = _pickup(model, (20, 25))
    assert ff.exit_target == (0, 25)
    _enclose(model, (20, 25))
    return model, ff, marker


def test_hold_one_keeps_the_carry_and_raises_nothing() -> None:
    model, ff, marker = _enclosed_carrier(hold=1)
    kept = (ff.assigned, ff.rescued_victim, ff.exiting, ff.exit_target, ff.status, ff.target_pos)
    commands = _record_commands(model)
    events_before = len(model._rescue_event_log)
    attempted_before = set(model._blocked_replacement_attempted)

    ff.advance()

    assert (ff.assigned, ff.rescued_victim, ff.exiting, ff.exit_target, ff.status, ff.target_pos) == kept
    assert ff.rescued_victim is marker and ff.status != "route_blocked"
    assert _cell(ff) == (20, 25) and _cell(marker) == (20, 25)
    assert ff._last_move_tier == agents.EXIT_LEG_HOLD_TIER
    assert model._rescue_event_log[events_before:] == []
    assert commands == []  # no unassign, no replacement assign
    assert set(model._blocked_replacement_attempted) == attempted_before
    for other_id in (FF_B, FF_C):
        assert model.firefighter_marker_agents[other_id].assigned is False
    assert model._find_active_firefighter_for_victim(V0, marker) == (FF_A, ff)

    # the first step a neighbour stops burning, the carrier moves and the victim with it
    _fire(model, (19, 25)).burning = False
    ff.advance()
    assert _cell(ff) == (19, 25) and _cell(marker) == (19, 25)
    assert ff.exiting is True and ff.rescued_victim is marker
    assert commands == []


def test_hold_zero_drops_the_victim_exactly_as_today() -> None:
    """Pins the defect: route_blocked, the replacement unassign, and the victim left on
    the cell while another unit is paired to it."""
    model, ff, marker = _enclosed_carrier(hold=0)
    commands = _record_commands(model)

    ff.advance()

    assert ff.status == "route_blocked"
    assert ff.assigned is False and ff.rescued_victim is None
    assert ff.exiting is False and ff.exit_target is None
    assert _cell(marker) == (20, 25)
    assert [e["firefighter_id"] for e in _events(model, "route_blocked", V0)] == [FF_A]
    drops = [c for c in commands if c[0] == "unassign" and c[2] == FF_A]
    assert drops == [("unassign", V0, FF_A, "replacement_after_blocked", {"reset_victim_pending": True})]
    replacements = [c for c in commands if c[0] == "assign" and c[1] == V0]
    assert len(replacements) == 1 and replacements[0][2] in (FF_B, FF_C)


@pytest.mark.parametrize("hold", (0, 1))
def test_an_enclosed_approaching_unit_is_route_blocked_at_both_settings(hold) -> None:
    """The pathway's real purpose - replacing an APPROACHING unit - is untouched."""
    model = _model(hold=hold)
    ff = _assign(model, FF_A, V0, (20, 25), (30, 25))
    _enclose(model, (20, 25))
    commands = _record_commands(model)

    ff.advance()

    assert ff.exiting is False
    assert ff.status == "route_blocked"
    assert [e["firefighter_id"] for e in _events(model, "route_blocked", V0)] == [FF_A]
    assert ("unassign", V0, FF_A, "replacement_after_blocked", {"reset_victim_pending": True}) in commands


@pytest.mark.parametrize("hold", (0, 1))
def test_a_carrier_already_labelled_route_blocked(hold) -> None:
    """HOLD 1 relabels it on its first hold, so _find_active_firefighter_for_victim sees
    it again. HOLD 0 pins today: the label is already set, so _mark_route_blocked raises
    nothing and the carrier stays bound, labelled, and invisible to the lookup."""
    model, ff, marker = _enclosed_carrier(hold=hold)
    ff.status = "route_blocked"
    commands = _record_commands(model)
    events_before = len(model._rescue_event_log)

    ff.advance()

    assert ff.exiting is True and ff.rescued_victim is marker and ff.assigned is True
    assert model._rescue_event_log[events_before:] == []
    assert commands == []
    if hold:
        assert ff.status == "assigned"
        assert model._find_active_firefighter_for_victim(V0, marker) == (FF_A, ff)
    else:
        assert ff.status == "route_blocked"
        assert model._find_active_firefighter_for_victim(V0, marker) is None


def test_the_hold_start_resets_the_held_victims_streak(monkeypatch) -> None:
    """With no other live unit, HOLD 1 makes the enclosed carrier's cell a reachability
    start, so its victim's isolation streak resets exactly as today's dropped ex-carrier
    resets it. No other victim's flags move, and the start is stateless: a carrier that
    is no longer enclosed is no start."""
    flags = {}
    for hold in (0, 1):
        model, ff, marker = _enclosed_carrier(hold=hold)
        _kill(model, FF_B, FF_C)
        other = model.victim_marker_agents[V1]
        model.grid.move_agent(other, (22, 25))
        calls = _spy_flags(monkeypatch)
        model._unreachable_geo_streak = {V0: 19}

        model._update_unreachable_victims()

        flags[hold] = calls[-1]
        assert model._unreachable_geo_streak[V0] == (0 if hold else 20)
        assert flags[hold][V0]["geo_reachable"] is bool(hold)
        assert "in_custody" not in flags[hold][V0]
        assert ff.exiting is True and ff.rescued_victim is marker

        # stateless: one neighbour clears, the carrier is no longer enclosed, no start
        _fire(model, (19, 25)).burning = False
        model._update_unreachable_victims()
        assert model._unreachable_geo_streak[V0] == (1 if hold else 21)
        monkeypatch.undo()

    others = sorted(set(flags[0]) - {V0})
    assert others and {v: flags[0][v] for v in others} == {v: flags[1][v] for v in others}


def test_the_hold_start_keeps_the_streak_at_zero_for_the_whole_hold() -> None:
    """Design 8.2 D2: with HOLD 1, SERVED 0 and no other live unit, the held victim's
    streak STAYS 0 during the hold - on every update of a 30-advance hold, not only the
    first - so the carry is never written off; and the held carrier is a start only,
    never in `living` (no distance is ever recorded)."""
    model, ff, marker = _enclosed_carrier(hold=1)
    _kill(model, FF_B, FF_C)
    commands = _record_commands(model)
    model._unreachable_geo_streak = {V0: 19}
    streaks = []

    for _ in range(30):
        ff.advance()
        assert ff._last_move_tier == agents.EXIT_LEG_HOLD_TIER
        model._update_unreachable_victims()
        streaks.append(model._unreachable_geo_streak[V0])
        assert model._ff_victim_distances == {}

    assert streaks == [0] * 30
    assert [e for e in getattr(model, "_unreachable_escape_log", []) or [] if e["victim_id"] == V0] == []
    assert ff.exiting is True and ff.rescued_victim is marker and ff.assigned is True
    assert _cell(ff) == (20, 25) and _cell(marker) == (20, 25)
    assert not [c for c in commands if c[1] == V0 or c[2] == FF_A]


@pytest.mark.parametrize("hold", (0, 1))
@pytest.mark.parametrize("cell", ((0, 28), (0, 0)), ids=("edge", "corner"))
def test_an_enclosed_carrier_on_the_grid_edge_holds_and_is_a_start(cell, hold) -> None:
    """Off-grid neighbours do not count as open, on either side. A mode-0 carrier on a
    NON-exit boundary cell whose every IN-GRID neighbour burns holds at HOLD 1 (the
    agent's no-neighbour branch), and _exit_leg_held_cell returns its cell whatever the
    setting, so at HOLD 1 it is a reachability start and the streak resets. HOLD 0,
    before its advance: the same board is no start and the streak runs."""
    model = _model(mode=0, hold=hold)
    ff, marker = _pickup(model, (3, 25))
    _carry_to(model, ff, marker, cell)
    _enclose(model, cell)
    _kill(model, FF_B, FF_C)
    assert len(_neighbours(model, cell)) == (3 if cell == (0, 28) else 2)
    model._unreachable_geo_streak = {V0: 19}
    if hold:
        ff.advance()
        assert ff._last_move_tier == agents.EXIT_LEG_HOLD_TIER
        assert ff.exiting is True and ff.rescued_victim is marker and ff.rescue_completed is False
        assert _cell(ff) == cell and _cell(marker) == cell
    assert model._exit_leg_held_cell(ff, model._active_burning_cells()) == cell

    model._update_unreachable_victims()

    assert model._unreachable_geo_streak[V0] == (0 if hold else 20)


@pytest.mark.parametrize("shape", ("dead_flag", "dead_status", "off_grid"))
def test_a_dead_or_off_grid_enclosed_carrier_is_no_start(shape) -> None:
    """The hold start is a LIVE, on-grid carrier's cell only: the enclosed board is a start
    until the carrier is dead-flagged (status untouched), labelled dead (flag untouched)
    or off the grid, and then the held victim's streak runs."""
    model, ff, marker = _enclosed_carrier(hold=1)
    _kill(model, FF_B, FF_C)
    assert model._exit_leg_held_cell(ff, model._active_burning_cells()) == (20, 25)
    if shape == "dead_flag":
        ff.dead = True
    elif shape == "dead_status":
        ff.status = "dead"
    else:
        model.grid.remove_agent(ff)
        assert ff.pos is None
    assert ff.exiting is True and ff.rescued_victim is marker
    model._unreachable_geo_streak = {V0: 19}

    assert model._exit_leg_held_cell(ff, model._active_burning_cells()) is None
    model._update_unreachable_victims()

    assert model._unreachable_geo_streak[V0] == 20


@pytest.mark.parametrize("hold", (0, 1))
@pytest.mark.parametrize("role", ("carrier", "approaching"))
def test_the_enclosure_hook_runs_before_the_switch(monkeypatch, role, hold) -> None:
    """The sidecar counts enclosures through Firefighter._exit_leg_enclosed in EVERY arm,
    the HOLD-0 control included (tooling spec F), so the no-neighbour branch must call it
    BEFORE it reads the switch: once per enclosed step, True for an enclosed carrier and
    False for an enclosed approaching unit, at both settings."""
    if role == "carrier":
        _model_, ff, _marker = _enclosed_carrier(hold=hold)
    else:
        model = _model(hold=hold)
        ff = _assign(model, FF_A, V0, (20, 25), (30, 25))
        _enclose(model, (20, 25))
    seen = []
    original = agents.Firefighter._exit_leg_enclosed

    def spy(self):
        result = original(self)
        seen.append((self.unit_id, result))
        return result

    monkeypatch.setattr(agents.Firefighter, "_exit_leg_enclosed", spy)

    ff.advance()

    assert seen == [(FF_A, role == "carrier")]
    held = role == "carrier" and hold == 1
    assert (ff._last_move_tier == agents.EXIT_LEG_HOLD_TIER) is held
    assert (ff.status == "route_blocked") is (not held)


@pytest.mark.parametrize("hold", (0, 1))
def test_a_held_carrier_that_dies_leaves_its_dead_victim_dead(hold) -> None:
    """The casualty guard. HOLD 1: the corpse's marker stays "dead", the casualty
    unassign carries no reset_victim_pending, the casualty incident dispatches nobody,
    and a second sweep adds no second victim_dead. HOLD 0 shows what the guard prevents
    (a state today's drop never reaches): the unguarded marker write relabels the
    corpse "confirmed" and the next sweep kills it again."""
    model, ff, marker = _enclosed_carrier(hold=hold)
    _ignite(model, (20, 25))  # its own cell ignites: death in custody
    commands = _record_commands(model)
    state = model.managed_victims[V0]

    model._check_fire_casualties()

    assert ff.dead is True and ff.status == "dead"
    assert str(state.status).lower() == "dead"
    assert [e["firefighter_id"] for e in _events(model, "casualty", V0)] == [FF_A]
    casualty = [c for c in commands if c[0] == "unassign" and c[2] == FF_A]
    assert [c[3] for c in casualty] == ["firefighter_fire_casualty"]
    assert not [c for c in commands if c[0] == "assign"]
    assert len(_events(model, "victim_dead", V0)) == 1
    if hold:
        assert casualty[0][4] == {}
        assert str(marker.status).lower() == "dead"
    else:
        assert casualty[0][4] == {"reset_victim_pending": True}
        assert str(marker.status).lower() == "confirmed"  # the corpse relabelled

    model._check_fire_casualties()

    if hold:
        assert str(marker.status).lower() == "dead"
        assert len(_events(model, "victim_dead", V0)) == 1
    else:
        assert len(_events(model, "victim_dead", V0)) == 2  # killed a second time
    assert not [c for c in commands if c[0] == "assign"]


def test_a_dying_carrier_whose_victim_still_lives_keeps_todays_reset() -> None:
    """HOLD 1's guard fires only for a victim that no longer needs rescue. A carrier that
    dies away from its victim (the swallowed move_agent case) keeps today's
    reset_victim_pending, and the victim is re-dispatched."""
    model, ff, marker = _enclosed_carrier(hold=1)
    model.grid.move_agent(marker, (24, 25))
    _ignite(model, (20, 25))
    commands = _record_commands(model)

    model._check_fire_casualties()

    assert ff.dead is True
    assert str(marker.status).lower() != "dead"
    casualty = [c for c in commands if c[0] == "unassign" and c[2] == FF_A]
    assert casualty == [("unassign", V0, FF_A, "firefighter_fire_casualty", {"reset_victim_pending": True})]
    pair = model._find_active_firefighter_for_victim(V0, marker)
    assert pair is not None and pair[0] in (FF_B, FF_C)


# ---------------------------------------------------------------------------
# D3 - FF_EXIT_LEG_SERVED: a victim in a live carrier's custody counts as served
# ---------------------------------------------------------------------------

def _lone_carrier(served, hold=0):
    """A carrier with V0 on a fire-free map, every other unit dead, every other victim
    terminal: nobody but the carrier can reach V0, and the carrier is not in `living`."""
    model = _model(hold=hold, served=served)
    ff, marker = _pickup(model, (20, 25))
    _kill(model, FF_B, FF_C)
    _retire_victims(model, keep=(V0,))
    return model, ff, marker


@pytest.mark.parametrize("served", (0, 1))
def test_a_carried_victim_is_written_off_at_thirty_only_at_served_zero(served) -> None:
    """SERVED 0 pins the defect: the streak runs from the pickup and the carry is written
    off at 30 - the carrier unassigned, the victim unreachable and cancelled. SERVED 1:
    the streak never leaves 0 and the carry goes on."""
    model, ff, marker = _lone_carrier(served)
    streaks = []
    for _ in range(30):
        model._update_unreachable_victims()
        streaks.append(model._unreachable_geo_streak.get(V0))
    log = [e for e in getattr(model, "_unreachable_escape_log", []) or [] if e["victim_id"] == V0]
    state = model.managed_victims[V0]

    if served:
        assert streaks == [0] * 30
        assert log == []
        assert ff.exiting is True and ff.rescued_victim is marker and ff.assigned is True
        assert not getattr(state, "unreachable", False)
    else:
        assert streaks == list(range(1, 31))
        assert [(e["cause"], e["streak"]) for e in log] == [("geographically_isolated", 30)]
        assert ff.assigned is False and ff.rescued_victim is None and ff.exiting is False
        assert state.unreachable is True and state.cancelled is True
        assert str(marker.status).lower() == "unreachable"


def test_a_route_blocked_carrier_still_serves() -> None:
    """No status filter: the lookup that skips route_blocked units is not used."""
    model, ff, marker = _lone_carrier(served=1)
    ff.status = "route_blocked"
    assert model._find_active_firefighter_for_victim(V0, marker) is None
    assert model._exit_leg_custody() == {V0}
    for _ in range(30):
        model._update_unreachable_victims()
        assert model._unreachable_geo_streak.get(V0) == 0
    assert ff.rescued_victim is marker and ff.exiting is True


@pytest.mark.parametrize("shape", ("dead_flag", "dead_status", "off_grid"))
def test_a_dead_or_off_grid_exiting_unit_does_not_serve(monkeypatch, shape) -> None:
    model, ff, marker = _lone_carrier(served=1)
    if shape == "dead_flag":
        ff.dead = True
    elif shape == "dead_status":
        ff.status = "dead"
    else:
        model.grid.remove_agent(ff)
        assert ff.pos is None
    assert ff.exiting is True and ff.rescued_victim is marker
    calls = _spy_flags(monkeypatch)

    assert model._exit_leg_custody() == set()
    model._update_unreachable_victims()

    assert "in_custody" not in calls[-1][V0]
    assert model._unreachable_geo_streak.get(V0) == 1


@pytest.mark.parametrize("first_claimant", ("route_blocked_approach", "dead_carrier"))
def test_a_double_claim_still_serves(first_claimant) -> None:
    """The carrier is NOT first in dict order: ff_unit_0 also holds V0 - a route_blocked
    approaching claimant walled in by fire (so it reaches nothing), or a dead carrier
    that kept its binding. The custody set must look past it to ff_unit_1. SERVED 0 on
    the same board shows the streak does run there."""
    for served in (0, 1):
        model = _model(served=served)
        carrier, marker = _pickup(model, (20, 25), ff_id=FF_B)
        _kill(model, FF_C)
        _retire_victims(model, keep=(V0,))
        first = model.firefighter_marker_agents[FF_A]
        if first_claimant == "route_blocked_approach":
            _assign(model, FF_A, V0, (35, 15), _cell(marker))
            first.status = "route_blocked"
            _enclose(model, (35, 15))
        else:
            model.grid.move_agent(first, (35, 15))
            first.rescued_victim = marker
            first.exiting = True
            first.exit_target = (49, 15)
            first.dead = True
        assert list(model.firefighter_marker_agents)[:2] == [FF_A, FF_B]
        assert carrier.rescued_victim is marker and carrier.exiting is True

        model._update_unreachable_victims()

        if served:
            assert model._exit_leg_custody() == {V0}
            assert model._unreachable_geo_streak.get(V0) == 0
        else:
            assert model._unreachable_geo_streak.get(V0) == 1


def test_served_zero_writes_no_custody_key_and_served_one_only_the_carried_victim(monkeypatch) -> None:
    for served in (0, 1):
        model = _model(served=served)
        _pickup(model, (20, 25))
        calls = _spy_flags(monkeypatch)
        model._update_unreachable_victims()
        model._update_unreachable_victims()
        assert len(calls) == 2
        for flags in calls:
            keyed = sorted(vid for vid, entry in flags.items() if "in_custody" in entry)
            if served:
                assert keyed == [V0] and flags[V0]["in_custody"] is True
            else:
                assert keyed == []
        monkeypatch.undo()


def test_served_leaves_distances_and_approaching_flags_untouched(monkeypatch) -> None:
    """SERVED adds one key and nothing else: _ff_victim_distances and every
    approaching / assigned_approaching flag are identical at 0 and 1 on the same board,
    with a live unit really approaching a second victim."""
    seen = {}
    for served in (0, 1):
        model = _model(served=served)
        _pickup(model, (20, 25))
        approacher = _assign(model, FF_B, V1, (35, 30), (35, 35))
        calls = _spy_flags(monkeypatch)
        distances = []
        model._update_unreachable_victims()
        distances.append(dict(model._ff_victim_distances))
        model.grid.move_agent(approacher, (35, 31))
        model._update_unreachable_victims()
        distances.append(dict(model._ff_victim_distances))
        stripped = [
            {vid: {k: v for k, v in entry.items() if k != "in_custody"} for vid, entry in flags.items()}
            for flags in calls
        ]
        seen[served] = (distances, stripped)
        monkeypatch.undo()

    assert seen[0] == seen[1]
    distances, flags = seen[1]
    assert flags[1][V1]["approaching"] is True and flags[1][V1]["assigned_approaching"] is True
    assert flags[1][V0]["approaching"] is False
    assert all(key[0] != FF_A for key in distances[1]), "the carrier is not in `living`"


def test_unreachable_escape_victims_with_in_custody() -> None:
    """The planner side, called directly: in_custody serves, so a streak of 29 resets
    instead of reaching 30; without it (or False) the victim is marked."""
    base = {
        "status": "assigned",
        "terminal": False,
        "assigned": True,
        "assigned_approaching": False,
        "geo_reachable": False,
        "confirmed": True,
        "approaching": False,
    }
    marked, geo, undetected = rescue_planner.unreachable_escape_victims(
        {"v": dict(base, in_custody=True)}, {"v": 29}, {"v": 5}
    )
    assert marked == [] and geo == {"v": 0} and undetected == {"v": 0}
    for flags in (dict(base), dict(base, in_custody=False)):
        marked, geo, _undetected = rescue_planner.unreachable_escape_victims({"v": flags}, {"v": 29}, {})
        assert marked == [("v", "geographically_isolated")] and geo == {"v": 30}
    assert rescue_planner._is_productively_served({"in_custody": True}) is True
    assert rescue_planner._is_productively_served({"in_custody": False}) is False
    assert rescue_planner._is_productively_served({}) is False
