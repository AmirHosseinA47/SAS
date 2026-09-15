"""Fire mechanic round 1: idle firefighters extinguish and cut firebreaks.

Drives the real WildFireModel and the real Firefighter.advance(), in the style of
tests/test_victim_fire_flight.py: the whole map is quieted, a test lays out
exactly which cells burn, and one firefighter's advance() is called directly so
nothing else moves. Design: outputs/firemech_part1.txt.
"""

from __future__ import annotations

import contextlib
import io
import os
import random

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

FF_A = "ff_unit_0"
FF_B = "ff_unit_1"

_SWITCHES = (
    "FF_FIREFIGHT_EXTINGUISH",
    "FF_FIREFIGHT_FIREBREAK",
    "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE",
    "FF_FIREFIGHT_DRY_RUN",
)
_CONFIG_NAMES = _SWITCHES + ("SYSTEM_RANDOM",)


@pytest.fixture(autouse=True)
def _restore_module_config():
    """apply_scenario_config mutates module globals; put them back for other tests."""
    saved = {}
    for mod in (cfv, wf):
        saved[mod] = {name: (hasattr(mod, name), getattr(mod, name, None)) for name in _CONFIG_NAMES}
    saved_agents_random = agents.random
    yield
    for mod, values in saved.items():
        for name, (present, value) in values.items():
            if present:
                setattr(mod, name, value)
            elif hasattr(mod, name):
                delattr(mod, name)
    agents.random = saved_agents_random


def _model(seed: int = 101, extinguish=0, firebreak=0, retreat_range=3, dry=0) -> WildFireModel:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv,
        wf,
        FF_FIREFIGHT_EXTINGUISH=extinguish,
        FF_FIREFIGHT_FIREBREAK=firebreak,
        FF_FIREFIGHT_ENGAGED_RETREAT_RANGE=retreat_range,
        FF_FIREFIGHT_DRY_RUN=dry,
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


def _line_x(model: WildFireModel, x: int, y0: int = 10, y1: int = 40) -> None:
    _ignite(model, *[(x, y) for y in range(y0, y1 + 1)])


def _unit(model: WildFireModel, cell, ff_id: str = FF_A) -> agents.Firefighter:
    """An idle, dispatch-available firefighter on `cell`; the other unit parked far away."""
    for other_id, other in model.firefighter_marker_agents.items():
        if other_id != ff_id:
            model.grid.move_agent(other, (49, 0))
    ff = model.firefighter_marker_agents[ff_id]
    model.grid.move_agent(ff, tuple(cell))
    ff.dead = False
    ff.assigned = False
    ff.target_pos = None
    ff.rescued_victim = None
    ff.exiting = False
    ff.exit_target = None
    ff.rescue_completed = False
    ff.status = "available"
    ff._reset_idle_retreat_state()
    return ff


def _cell(agent):
    return (int(agent.pos[0]), int(agent.pos[1]))


def _manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _log(model):
    return list(getattr(model, "_firefight_log", []) or [])


def _fire_steps(model: WildFireModel, n: int) -> None:
    fires = [a for a in model.schedule.agents if type(a) is agents.Fire]
    for _ in range(n):
        for a in fires:
            a.step()
        for a in fires:
            a.advance()


# ---------------------------------------------------------------------------
# switches
# ---------------------------------------------------------------------------

def test_every_switch_ships_off_and_every_fallback_is_off(monkeypatch) -> None:
    assert cfv.FF_FIREFIGHT_EXTINGUISH == 0
    assert cfv.FF_FIREFIGHT_FIREBREAK == 0
    assert cfv.FF_FIREFIGHT_ENGAGED_RETREAT_RANGE == agents.IDLE_RETREAT_SAFETY_BUFFER
    assert cfv.FF_FIREFIGHT_DRY_RUN == 0
    buffer = agents.IDLE_RETREAT_SAFETY_BUFFER
    for name, accessor, off in (
        ("FF_FIREFIGHT_EXTINGUISH", agents.ff_firefight_extinguish, False),
        ("FF_FIREFIGHT_FIREBREAK", agents.ff_firefight_firebreak, False),
        ("FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", agents.ff_firefight_engaged_retreat_range, buffer),
        ("FF_FIREFIGHT_DRY_RUN", agents.ff_firefight_dry_run, False),
    ):
        assert accessor() == off, name
        monkeypatch.setattr(cfv, name, "off", raising=False)
        assert accessor() == off, name + " junk"
        monkeypatch.delattr(cfv, name, raising=False)
        assert accessor() == off, name + " missing"


@pytest.mark.parametrize("raw,expected", [(1, 1), (2, 2), (3, 3), (0, 3), (-1, 3), (7, 3), ("x", 3), (None, 3)])
def test_retreat_range_only_one_and_two_suppress(monkeypatch, raw, expected) -> None:
    monkeypatch.setattr(cfv, "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", raw, raising=False)
    assert agents.ff_firefight_engaged_retreat_range() == expected


# ---------------------------------------------------------------------------
# the two Fire writers
# ---------------------------------------------------------------------------

def test_extinguish_write_semantics() -> None:
    model = _model()
    _ignite(model, (20, 25))
    fire = _fire(model, (20, 25))
    fire.has_burned = False  # ignited on the latest tick: the latch is not set yet
    assert fire.firefighter_extinguish() is True
    assert (fire.fuel, fire.burning, fire.has_burned, fire.burnt) == (0, False, True, False)
    # no longer burning -> refuses, writes nothing
    assert fire.firefighter_extinguish() is False
    green = _fire(model, (30, 30))
    assert green.firefighter_extinguish() is False
    assert (green.fuel, green.burning, green.has_burned) == (8, False, False)
    burnt = _fire(model, (31, 30))
    burnt.burnt = True
    burnt.burning = True
    assert burnt.firefighter_extinguish() is False


def test_extinguished_cell_turns_burnt_at_next_tick_and_never_reignites() -> None:
    model = _model()
    _line_x(model, 20)
    _ignite(model, (19, 25), (21, 25))
    target = _fire(model, (20, 25))
    assert target.firefighter_extinguish() is True
    burning_seen = []
    for _ in range(12):
        _fire_steps(model, 1)
        burning_seen.append(target.burning)
    assert not any(burning_seen)
    assert target.burnt is True and target.fuel == 0


def test_remove_fuel_semantics_virgin_and_scorched() -> None:
    model = _model()
    _line_x(model, 20)
    virgin = _fire(model, (21, 25))       # right next to the fire: P would be high
    assert virgin.firefighter_remove_fuel() is True
    assert (virgin.fuel, virgin.burning, virgin.has_burned, virgin.burnt) == (0, False, False, False)
    scorched = _fire(model, (21, 30))
    scorched.has_burned = True
    assert scorched.firefighter_remove_fuel() is True
    assert _fire(model, (20, 12)).firefighter_remove_fuel() is False  # burning
    assert virgin.firefighter_remove_fuel() is False                  # already no fuel
    for _ in range(12):
        _fire_steps(model, 1)
        assert virgin.burning is False
    assert virgin.has_burned is False and virgin.burnt is False  # never counted as burnt
    assert scorched.burnt is True and scorched.burning is False


def test_euclidean_band_blocks_a_diagonal_front_where_a_manhattan_band_leaks() -> None:
    """The band rule, checked against the model's own probability_of_fire."""

    def worst_beyond(rule):
        model = _model()
        grid = {
            (int(a.pos[0]), int(a.pos[1])): a
            for a in model.schedule.agents if type(a) is agents.Fire
        }
        burning0 = [c for c in grid if c[0] + c[1] <= 45]
        for c in burning0:
            grid[c].burning = True
        beyond, fire_side = [], []
        for c in grid:
            if c[0] + c[1] <= 45:
                continue
            if rule == "euclid":
                d2 = min((c[0] - x) ** 2 + (c[1] - y) ** 2 for x, y in burning0)
                if agents.FIREFIGHT_BAND_INNER_SQ < d2 <= agents.FIREFIGHT_BAND_OUTER_SQ:
                    grid[c].firefighter_remove_fuel()
                elif d2 <= agents.FIREFIGHT_BAND_INNER_SQ:
                    fire_side.append(c)
                else:
                    beyond.append(c)
            else:
                d = min(abs(c[0] - x) + abs(c[1] - y) for x, y in burning0)
                if 3 <= d <= 5:
                    grid[c].firefighter_remove_fuel()
                elif d <= 2:
                    fire_side.append(c)
                else:
                    beyond.append(c)
        for c in fire_side:
            grid[c].burning = True
        return max(
            grid[c].probability_of_fire()
            for c in beyond if 5 <= c[0] <= 44 and 5 <= c[1] <= 44
        )

    assert worst_beyond("euclid") == 0
    assert worst_beyond("manhattan") > 0


# ---------------------------------------------------------------------------
# kill switch and identity-by-construction
# ---------------------------------------------------------------------------

def test_off_leaves_advance_untouched() -> None:
    model = _model()
    _line_x(model, 20)
    ff = _unit(model, (25, 25))
    before = {c: (f.fuel, f.burning) for c, f in ((c, _fire(model, c)) for c in [(20, 25), (24, 25), (25, 25)])}
    assert ff._firefight_prepare() is None
    ff.advance()
    assert not hasattr(model, "_firefight_log")
    assert not hasattr(model, "_firefight_shadow")
    assert {c: (_fire(model, c).fuel, _fire(model, c).burning) for c in before} == before


@pytest.mark.parametrize("config", [
    dict(retreat_range=1),                  # suppression alone needs an action
    dict(extinguish=1),                     # extinguish at reach 2 needs suppression
    dict(extinguish=1, dry=1),
])
def test_configurations_with_no_possible_action_are_inert(config) -> None:
    model = _model(**config)
    _line_x(model, 20)
    ff = _unit(model, (22, 25))
    assert ff._firefight_prepare() is None
    ff.advance()
    assert not hasattr(model, "_firefight_log")
    assert _fire(model, (20, 25)).burning is True


def test_default_retreat_test_is_the_idle_buffer() -> None:
    model = _model()
    _line_x(model, 20)
    assert _unit(model, (23, 25))._needs_immediate_survival_retreat() is True    # d 3
    assert _unit(model, (24, 25))._needs_immediate_survival_retreat() is False   # d 4
    assert _unit(model, (22, 25))._needs_immediate_survival_retreat(1) is False  # d 2 at 1
    assert _unit(model, (21, 25))._needs_immediate_survival_retreat(1) is True   # adjacent


# ---------------------------------------------------------------------------
# extinguish, firebreak, approach
# ---------------------------------------------------------------------------

def test_extinguish_nearest_front_cell_within_reach_under_suppression() -> None:
    model = _model(extinguish=1, retreat_range=1)
    _line_x(model, 20)
    ff = _unit(model, (22, 25))
    ff.advance()
    target = _fire(model, (20, 25))
    assert (target.fuel, target.burning, target.has_burned) == (0, False, True)
    assert _cell(ff) == (22, 25)
    row = _log(model)[-1]
    assert row["action"] == "extinguish" and row["wrote"] is True
    assert row["target"] == [20, 25] and row["T"] == 1 and row["exit_guard"] is True
    assert model.firefight_extinguished_total == 1


def test_nearest_front_ties_break_on_x_then_y() -> None:
    model = _model(extinguish=1, retreat_range=1)
    _ignite(model, (22, 27), (20, 25))      # both manhattan 2 from the unit
    ff = _unit(model, (22, 25))
    ctx = ff._firefight_prepare()
    assert ctx is not None and ctx["plan"][0] == "extinguish"
    assert ctx["plan"][1] == (20, 25)


def test_front_excludes_burning_cells_with_no_fuel_neighbour() -> None:
    model = _model(extinguish=1, retreat_range=1)
    _ignite(model, (22, 27))
    for c in ((21, 27), (23, 27), (22, 26), (22, 28)):
        _fire(model, c).fuel = 0            # boxed in: no fuel next to it
    ff = _unit(model, (22, 25))
    ctx = ff._firefight_prepare()
    assert ctx is not None
    assert ctx["n_front"] == 0 and ctx["plan"] is None
    assert ctx["T"] == agents.IDLE_RETREAT_SAFETY_BUFFER  # no plan -> full buffer


def test_firebreak_works_from_the_idle_standoff_without_suppression() -> None:
    model = _model(firebreak=1)
    _line_x(model, 20)
    ff = _unit(model, (24, 25))             # manhattan 4: outside the idle buffer
    ff.advance()
    own = _fire(model, (24, 25))            # euclidean 4, inside (2, 5]: nearest band cell
    assert (own.fuel, own.has_burned) == (0, False)
    assert _cell(ff) == (24, 25)
    row = _log(model)[-1]
    assert row["action"] == "clear" and row["T"] == 3 and row["scorched"] is False
    assert model.firefight_cleared_unburned_total == 1


def test_approach_never_enters_the_retreat_distance_and_builds_a_band() -> None:
    model = _model(firebreak=1)
    _line_x(model, 20)
    ff = _unit(model, (40, 25))
    burning = {(20, y) for y in range(10, 41)}
    for _ in range(40):
        ff.advance()
        assert ff._min_fire_distance(_cell(ff), burning) > agents.IDLE_RETREAT_SAFETY_BUFFER
    actions = [r["action"] for r in _log(model)]
    assert "retreat" not in actions
    cleared = [
        (a.pos[0], a.pos[1]) for a in model.schedule.agents
        if type(a) is agents.Fire and a.fuel == 0
    ]
    assert len(cleared) >= 10
    for x, y in cleared:                   # every cleared cell is a band cell
        d2 = min((x - 20) ** 2 + (y - yy) ** 2 for yy in range(10, 41))
        assert agents.FIREFIGHT_BAND_INNER_SQ < d2 <= agents.FIREFIGHT_BAND_OUTER_SQ


def test_retreat_still_fires_at_the_suppressed_distance_and_suspends_until_safe() -> None:
    model = _model(extinguish=1, retreat_range=1)
    _line_x(model, 20)
    ff = _unit(model, (21, 25))             # adjacent: the retreat must win
    ff.advance()
    assert _fire(model, (20, 25)).burning is True
    row = _log(model)[-1]
    assert row["action"] == "retreat" and row["suspend_set"] is True
    assert ff._firefight_suspended is True
    burning = {(20, y) for y in range(10, 41)}
    for _ in range(12):
        ctx = ff._firefight_prepare()
        if not ff._firefight_suspended:
            break
        assert ctx["T"] == agents.IDLE_RETREAT_SAFETY_BUFFER
        ff.advance()
    assert ff._firefight_suspended is False
    assert ff._min_fire_distance(_cell(ff), burning) >= agents.IDLE_RETREAT_SAFETY_BUFFER + 1


def test_exit_guard_refuses_suppression_with_fire_on_both_sides() -> None:
    model = _model(extinguish=1, retreat_range=1)
    _line_x(model, 20)
    _line_x(model, 24)
    ff = _unit(model, (22, 25))
    ctx = ff._firefight_prepare()
    assert ctx["exit_guard"] is False
    assert ctx["T"] == agents.IDLE_RETREAT_SAFETY_BUFFER and ctx["plan"] is None
    assert ff._needs_immediate_survival_retreat(ctx["T"]) is True


def test_rescue_assignment_preempts_on_the_next_advance() -> None:
    model = _model(extinguish=1, firebreak=1, retreat_range=1)
    _line_x(model, 20)
    ff = _unit(model, (22, 25))
    ff.advance()
    n = len(_log(model))
    ff.assigned = True
    ff.target_pos = (22, 45)
    ff.status = "en_route"
    assert ff._firefight_prepare() is None
    fuel_before = {c: _fire(model, c).fuel for c in [(20, 24), (20, 26), (22, 25)]}
    ff.advance()
    assert len(_log(model)) == n
    assert {c: _fire(model, c).fuel for c in fuel_before} == fuel_before


def test_partial_firebreak_persists_for_another_unit() -> None:
    model = _model(firebreak=1)
    _line_x(model, 20)
    ff = _unit(model, (24, 25))
    for _ in range(3):
        ff.advance()
    cleared = {
        (int(a.pos[0]), int(a.pos[1])) for a in model.schedule.agents
        if type(a) is agents.Fire and a.fuel == 0
    }
    assert len(cleared) == 3
    ff.assigned = True                      # preempted by a rescue
    ff.target_pos = (40, 45)
    ff.status = "en_route"
    assert ff._firefight_prepare() is None
    # another idle unit next to the half-built band picks up where it stopped
    other = _unit(model, (24, 26), ff_id=FF_B)
    ctx = other._firefight_prepare()
    assert ctx["plan"] is not None and ctx["plan"][0] == "clear"
    assert ctx["plan"][1] not in cleared
    # and the fire cannot undo the finished part
    _fire_steps(model, 9)
    for c in cleared:
        fire = _fire(model, c)
        assert (fire.fuel, fire.burning, fire.has_burned) == (0, False, False)


# ---------------------------------------------------------------------------
# Part 2 review fixes: no zero-work approach/retreat cycle, latching, far guard
# ---------------------------------------------------------------------------

def _positions_and_actions(model, ff, n):
    out = []
    for _ in range(n):
        before = len(_log(model))
        ff.advance()
        rows = _log(model)
        out.append((_cell(ff), rows[-1]["action"] if len(rows) > before else None))
    return out


def test_no_zero_work_cycle_against_the_grid_edge_under_suppression() -> None:
    """The review's reproduction: burning row y=3, unit walking in along y=0.

    Before the fix the unit cleared two cells and then alternated (40,0)<->(39,0)
    for 30+ steps - a step into a cell whose exit guard fails, a full-buffer
    retreat out of it, and the same step again.
    """
    model = _model(firebreak=1, retreat_range=1)
    _ignite(model, *[(x, 3) for x in range(10, 41)])
    ff = _unit(model, (45, 0))
    hist = _positions_and_actions(model, ff, 60)
    tail = hist[-30:]
    pos = [p for p, _a in tail]
    worked = any(a in ("extinguish", "clear") for _p, a in tail)
    periodic = any(
        len(set(pos)) > 1 and all(pos[k] == pos[k + p] for k in range(len(pos) - p))
        for p in (2, 3, 4)
    )
    assert not (periodic and not worked)
    assert worked or not any(a == "retreat" for _p, a in tail)


def test_lookahead_refuses_a_buffer_cell_whose_exit_guard_fails() -> None:
    model = _model(firebreak=1, retreat_range=1)
    _ignite(model, *[(x, 3) for x in range(10, 41)])
    for c in ((41, 0), (40, 0), (39, 0)):
        _fire(model, c).fuel = 0            # cells the unit had already cleared
    ff = _unit(model, (40, 0))
    ctx = ff._firefight_prepare()
    # nearest band cell is (38,0); the only improving step is (39,0), manhattan 3
    # from the row, on the edge, flanked by equal-distance cells: its exit guard
    # fails, so stepping there would be undone by a full-buffer retreat
    assert ctx["plan"] is None
    assert ctx["blocked_target"] == (38, 0) and ctx["lookahead_rejected"] >= 1


def test_every_retreat_latches_suspension_when_suppression_is_configured() -> None:
    model = _model(extinguish=1, retreat_range=1)
    _line_x(model, 20)
    _line_x(model, 24)
    ff = _unit(model, (22, 25))             # pocket: exit guard fails, T = 3
    ctx = ff._firefight_prepare()
    assert ctx["exit_guard"] is False and ctx["T"] == agents.IDLE_RETREAT_SAFETY_BUFFER
    ff.advance()
    row = _log(model)[-1]
    assert row["action"] == "retreat" and row["suspend_set"] is True
    assert ff._firefight_suspended is True


def test_exit_guard_is_not_required_far_from_the_fire() -> None:
    """A unit parked on the grid edge, facing a flat flank 20 cells away, engages."""
    model = _model(extinguish=1, retreat_range=1)
    _line_x(model, 20)
    ff = _unit(model, (0, 25))
    ctx = ff._firefight_prepare()
    assert ctx["exit_guard"] is True and ctx["T"] == 1
    assert ctx["plan"] is not None and ctx["plan"][0] == "move"


# ---------------------------------------------------------------------------
# dry run, RNG and determinism
# ---------------------------------------------------------------------------

def test_dry_run_writes_nothing_and_moves_on_to_the_next_target() -> None:
    model = _model(extinguish=1, retreat_range=1, dry=1)
    _line_x(model, 20)
    ff = _unit(model, (22, 25))
    ff.advance()
    target = _fire(model, (20, 25))
    assert (target.fuel, target.burning) == (8, True)
    assert model._firefight_shadow == {(20, 25)}
    row = _log(model)[-1]
    assert row["action"] == "extinguish" and row["dry"] is True and row["wrote"] is False
    assert not hasattr(model, "firefight_extinguished_total")
    ff.advance()
    assert _log(model)[-1]["target"] != [20, 25]


def test_firefighting_draws_from_no_rng() -> None:
    model = _model(extinguish=1, firebreak=1, retreat_range=1)
    _line_x(model, 20)
    ff = _unit(model, (30, 25))
    state_agents = agents.random.getstate()
    state_system = cfv.SYSTEM_RANDOM.getstate()
    for _ in range(15):
        ff.advance()
    assert len(_log(model)) == 15
    assert agents.random.getstate() == state_agents
    assert cfv.SYSTEM_RANDOM.getstate() == state_system


def test_same_state_same_decisions() -> None:
    def run():
        model = _model(seed=202, extinguish=1, firebreak=1, retreat_range=1)
        _line_x(model, 20)
        _ignite(model, (24, 18), (24, 32))
        ff = _unit(model, (35, 25))
        for _ in range(25):
            ff.advance()
        fuel = sorted(
            (int(a.pos[0]), int(a.pos[1]), a.fuel, a.burning)
            for a in model.schedule.agents if type(a) is agents.Fire
        )
        return _log(model), fuel, _cell(ff)

    assert run() == run()
