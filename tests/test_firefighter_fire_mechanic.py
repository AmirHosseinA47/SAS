"""Fire mechanic: idle firefighters extinguish and cut firebreaks (round 1), and the
round-2 mission gate that decides WHEN they may do it.

Drives the real WildFireModel and the real Firefighter.advance(), in the style of
tests/test_victim_fire_flight.py: the whole map is quieted, a test lays out
exactly which cells burn, and one firefighter's advance() is called directly so
nothing else moves. Design: outputs/firemech_part1.txt, outputs/firemech2_part1.txt.

THE SHIPPED DEFAULT, SINCE THE UNGATED ROUND (outputs/ungated_part1.txt), IS THE
FEATURE ON AND UNGATED: EXTINGUISH 1, FIREBREAK 1, ENGAGED_RETREAT_RANGE 1,
MISSION_GATE 0 - any idle unit engages at any time, while the drones search. Every
round-1 case below is about the MECHANIC and passes its whole configuration to _model()
explicitly, so none of them depends on the default. The round-2 gate cases arm the gate
explicitly (mission_gate=1), since it is no longer the default. The shipped default
itself is pinned in the "switches" section (constants and fallbacks) and, as
BEHAVIOUR, by the two "shipped default engages" cases near the end: at the shipped
values a unit fights fire while victims are still unresolved.

A full-suite run with the four constants flipped (outputs/_ug_simplugin.py,
outputs/ungated_part1.txt 2.4) showed that NOTHING outside this file notices whether
firefighters fight fire from step 1. The behavioural pins at the end are the tests that
would catch the feature being re-gated or switched off by accident.
"""

from __future__ import annotations

import contextlib
import enum
import io
import os
import random
from decimal import Decimal
from fractions import Fraction

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
    "FF_FIREFIGHT_MISSION_GATE",
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


def _model(seed: int = 101, extinguish=0, firebreak=0, retreat_range=3, dry=0,
           mission_gate=0) -> WildFireModel:
    """A real model with the map quieted, EVERY switch passed explicitly.

    The keyword defaults here are the feature OFF (extinguish 0, firebreak 0, range 3)
    with the gate open (0). They are TEST PARAMETERS, not the shipped defaults (which
    since the ungated round are 1 / 1 / 1 / gate 0): the OFF-path cases call _model()
    bare and must keep getting the OFF path whatever ships, and every other case names
    the configuration it tests. mission_gate=0 matters for the round-1 cases: the
    model's victims are all "candidate" from reset, so a closed gate would keep every
    one of them from ever engaging.
    """
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
        FF_FIREFIGHT_MISSION_GATE=mission_gate,
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

# RE-RUNNING A FLIP OF THESE SWITCHES (what the ungated round had to do, in order):
#   1. the constant in common_fixed_variables.py;
#   2. the getattr default in the agents.py accessor - it IS the shipped value, so a
#      missing attribute agrees with the file;
#   3. the expected values in the three pins below;
#   4. outputs/_ug_fallback_mutants.py - puts each pre-flip literal back into its
#      accessor and requires these pins to FAIL on it (a pin that cannot fail is not a
#      pin);
#   5. the full suite with the flip simulated (outputs/_ug_simplugin.py via
#      outputs/_ug_pytest.sh VARIANT=sim) to find every NON-pin test the flip breaks;
#   6. the runner register (outputs/ungated_runner_register.txt) for every script and
#      queue line whose meaning the flip changes silently.

# Values that are not an exact integer: each must ARM (take the shipped value), never
# silently take the zero path. inf used to raise OverflowError; Decimal("0.5") and
# Fraction(1, 2) used to truncate to 0 (outputs/_ug_accessor_matrix.txt).
_JUNK = ("off", "", None, 0.5, -0.5, "0.5", "2.0", float("inf"), float("nan"),
         Decimal("0.5"), Fraction(1, 2), [], object())
_EXACT_ZEROS = (0, 0.0, "0", " 0 ", False, Decimal("0"))


class _IntEnum(enum.IntEnum):
    ZERO = 0
    ONE = 1


class _IntSub(int):
    pass


class _RaisingInt:
    """An object whose __int__ raises something other than TypeError/ValueError."""

    def __int__(self):
        raise RuntimeError("no int here")


def test_every_switch_ships_on_and_every_fallback_is_the_shipped_value(monkeypatch) -> None:
    """SHIPPED (ungated round): EXTINGUISH 1, FIREBREAK 1, RANGE 1, DRY_RUN 0.

    For the two action switches: a MISSING attribute and every non-exact-integer value
    arm the feature, and only an exact integral zero turns it off. DRY_RUN keeps its
    round-1 accessor (fallback 0, bare int) on purpose - its default did not change and
    its truncation belongs to the accessor round - so only its unchanged fallback is
    pinned. RANGE has its own pin below. See the flip checklist above this test.
    """
    assert cfv.FF_FIREFIGHT_EXTINGUISH == 1
    assert cfv.FF_FIREFIGHT_FIREBREAK == 1
    assert cfv.FF_FIREFIGHT_ENGAGED_RETREAT_RANGE == 1
    assert cfv.FF_FIREFIGHT_DRY_RUN == 0
    for name, accessor in (
        ("FF_FIREFIGHT_EXTINGUISH", agents.ff_firefight_extinguish),
        ("FF_FIREFIGHT_FIREBREAK", agents.ff_firefight_firebreak),
    ):
        assert accessor() is True, name
        for zero in _EXACT_ZEROS:
            monkeypatch.setattr(cfv, name, zero, raising=False)
            assert accessor() is False, (name, zero)
        for one in (1, 1.0, "1", True, -1, 2, 7):
            monkeypatch.setattr(cfv, name, one, raising=False)
            assert accessor() is True, (name, one)
        for junk in _JUNK:
            monkeypatch.setattr(cfv, name, junk, raising=False)
            assert accessor() is True, (name, junk)
        monkeypatch.delattr(cfv, name, raising=False)
        assert accessor() is True, name + " missing"
    assert agents.ff_firefight_engaged_retreat_range() == 1
    monkeypatch.delattr(cfv, "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", raising=False)
    assert agents.ff_firefight_engaged_retreat_range() == 1, "RANGE missing"
    assert agents.ff_firefight_dry_run() is False
    monkeypatch.setattr(cfv, "FF_FIREFIGHT_DRY_RUN", "off", raising=False)
    assert agents.ff_firefight_dry_run() is False, "DRY_RUN junk"
    monkeypatch.delattr(cfv, "FF_FIREFIGHT_DRY_RUN", raising=False)
    assert agents.ff_firefight_dry_run() is False, "DRY_RUN missing"


def test_mission_gate_ships_off_missing_is_off_and_junk_closes_it(monkeypatch) -> None:
    """SHIPPED (ungated round): MISSION_GATE 0 - any idle unit engages at any time.

    The one FF switch whose shipped value IS the zero, so the two halves of the rule
    point different ways: a MISSING attribute takes the shipped 0 (it must not silently
    disagree with common_fixed_variables), while anything that is not an exact integer
    CLOSES the gate. The gate cannot arm the feature, so a typo can only make it more
    rescue-neutral. Only an exact integral zero opens it. See the flip checklist above.
    """
    assert cfv.FF_FIREFIGHT_MISSION_GATE == 0
    assert agents.ff_firefight_mission_gate() is False
    monkeypatch.delattr(cfv, "FF_FIREFIGHT_MISSION_GATE", raising=False)
    assert agents.ff_firefight_mission_gate() is False, "missing"
    for zero in _EXACT_ZEROS:
        monkeypatch.setattr(cfv, "FF_FIREFIGHT_MISSION_GATE", zero, raising=False)
        assert agents.ff_firefight_mission_gate() is False, zero
    for on in (1, 1.0, "1", True, -1, 2):
        monkeypatch.setattr(cfv, "FF_FIREFIGHT_MISSION_GATE", on, raising=False)
        assert agents.ff_firefight_mission_gate() is True, on
    for junk in _JUNK:
        monkeypatch.setattr(cfv, "FF_FIREFIGHT_MISSION_GATE", junk, raising=False)
        assert agents.ff_firefight_mission_gate() is True, junk


@pytest.mark.parametrize("raw,expected", [
    (1, 1), (2, 2), (3, 3), (7, 3), (3.0, 3), (True, 1),
    (0, 3), (False, 3), (0.0, 3),                     # the exact-zero kill switch: no suppression
    (-1, 1), ("x", 1), (None, 1), (0.5, 1), (2.5, 1),  # junk arms the shipped 1
    (float("inf"), 1), (Decimal("0.5"), 1),
])
def test_retreat_range_only_one_and_two_suppress(monkeypatch, raw, expected) -> None:
    """SHIPPED (ungated round): 1. A DISTANCE, not a switch.

    exact 0 -> the buffer (no suppression, its kill switch); 1 and 2 suppress; an explicit
    integer >= 3 is the unsuppressed buffer; negative / non-integral / junk / missing take
    the shipped 1 - a junk value that fell to the buffer would silently make the shipped
    configuration firebreak-only, since extinguish at reach 2 needs a range below 2.
    Until the ungated round (-1, "x", None) read 3, 0.5 read 3 and 2.5 truncated to 2.
    See the flip checklist above.
    """
    monkeypatch.setattr(cfv, "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", raw, raising=False)
    assert agents.ff_firefight_engaged_retreat_range() == expected


@pytest.mark.parametrize("raw,expected", [
    (0, 0), (1, 1), (-1, -1), (7, 7), (True, 1), (False, 0),
    (0.0, 0), (3.0, 3), (-2.0, -2), (0.5, None), (-0.5, None),
    (float("inf"), None), (float("-inf"), None), (float("nan"), None),
    ("0", 0), (" 1 ", 1), ("-1", -1), ("0.5", None), ("2.0", None), ("off", None), ("", None),
    (None, None), ([], None), (Decimal("0"), 0), (Decimal("2"), 2), (Decimal("0.5"), None),
    (Fraction(1, 2), None), (Fraction(4, 2), 2),
    (_IntEnum.ONE, 1), (_IntEnum.ZERO, 0), (_IntSub(5), 5), (_RaisingInt(), None), (b"1", None),
])
def test_exact_integer_accepts_only_exact_integers_and_never_raises(raw, expected) -> None:
    """The helper under all four changed accessors (outputs/_ug_accessor_matrix.txt)."""
    assert agents._exact_integer(raw) == expected
    if expected is not None:
        assert type(agents._exact_integer(raw)) is int


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


# ---------------------------------------------------------------------------
# Round 2: the mission gate. It shipped at 1 in round 2 and has shipped at 0 since the
# ungated round, so these cases ARM IT EXPLICITLY (mission_gate=1) and drive the
# victims themselves. They test the gate's mechanism, which is unchanged and still
# available as a per-run setting.
# ---------------------------------------------------------------------------


def _victim_statuses(model, status: str) -> None:
    """Force every managed victim to one status (the gate reads managed_victims)."""
    for state in (getattr(model, "managed_victims", None) or {}).values():
        if state is not None:
            state.status = status


def _engaged_rows(model) -> int:
    return sum(1 for row in (getattr(model, "_firefight_log", None) or []) if row["engaged"])


def test_gate_closed_while_any_victim_is_unresolved_runs_no_feature_code() -> None:
    """Gate armed, with victims as a real run starts them: nothing engages.

    Not merely "does not write": prepare returns before any accessor below it, so no
    model attribute is created and no log row exists.
    """
    model = _model(extinguish=1, firebreak=1, retreat_range=1, mission_gate=1)
    _line_x(model, 20)
    ff = _unit(model, (24, 25))
    assert ff._firefight_mission_resolved() is False
    assert ff._firefight_prepare() is None
    before = _cell(ff)
    for _ in range(5):
        ff.advance()
    assert getattr(model, "_firefight_log", None) is None
    assert getattr(model, "_firefight_shadow", None) is None
    assert getattr(model, "firefight_cleared_total", None) is None
    assert _cell(ff) == before


def test_gate_opens_only_when_every_victim_is_rescued_or_dead() -> None:
    """rescued and dead open it; candidate, confirmed, assigned, unreachable do not."""
    model = _model(extinguish=1, firebreak=1, retreat_range=1, mission_gate=1)
    _line_x(model, 20)
    ff = _unit(model, (24, 25))
    for status in ("candidate", "confirmed", "assigned", "unreachable", "cancelled"):
        _victim_statuses(model, status)
        assert ff._firefight_mission_resolved() is False, status
        assert ff._firefight_prepare() is None, status
    for status in ("rescued", "dead", "DEAD"):
        _victim_statuses(model, status)
        assert ff._firefight_mission_resolved() is True, status
        assert ff._firefight_prepare() is not None, status


def test_gate_stays_closed_while_one_victim_of_many_is_unresolved() -> None:
    """All victims must be terminal - one unreachable straggler keeps it shut.

    That straggler is the reason for the strict predicate: an unreachable victim is
    still alive on the grid and can still burn, so fire written while it lives could
    change its recorded outcome (outputs/_fm2_audit_gate.txt, P1).
    """
    model = _model(extinguish=1, firebreak=1, retreat_range=1, mission_gate=1)
    _line_x(model, 20)
    ff = _unit(model, (24, 25))
    _victim_statuses(model, "rescued")
    managed = list((getattr(model, "managed_victims", None) or {}).values())
    assert managed
    managed[0].status = "unreachable"
    assert ff._firefight_mission_resolved() is False
    assert ff._firefight_prepare() is None
    managed[0].status = "dead"
    assert ff._firefight_mission_resolved() is True


def test_gate_off_reproduces_round_one_engagement_exactly() -> None:
    """MISSION_GATE=0 is round 1: same decisions, same writes, same cells."""

    def run(gate):
        model = _model(extinguish=1, firebreak=1, retreat_range=1, mission_gate=gate)
        _line_x(model, 20)
        if gate:  # let the gate open so the two runs are comparable
            _victim_statuses(model, "dead")
        ff = _unit(model, (24, 25))
        for _ in range(12):
            ff.advance()
        fuel = sorted(
            (int(a.pos[0]), int(a.pos[1]), a.fuel, a.burning)
            for a in model.schedule.agents if type(a) is agents.Fire
        )
        return _log(model), fuel, _cell(ff)

    assert run(0) == run(1)


def test_gate_closed_is_identical_to_the_feature_being_off() -> None:
    """The gate-closed path and the kill switch produce the same run, step for step."""

    def run(**kw):
        model = _model(**kw)
        _line_x(model, 20)
        ff = _unit(model, (24, 25))
        cells = []
        for _ in range(12):
            ff.advance()
            cells.append(_cell(ff))
        fuel = sorted(
            (int(a.pos[0]), int(a.pos[1]), a.fuel, a.burning)
            for a in model.schedule.agents if type(a) is agents.Fire
        )
        return cells, fuel

    gated = run(extinguish=1, firebreak=1, retreat_range=1, mission_gate=1)
    off = run(extinguish=0, firebreak=0, retreat_range=3, mission_gate=0)
    assert gated == off


def test_gate_predicate_is_open_when_a_model_has_no_managed_victims() -> None:
    """No victims means no rescue to protect; a real model always populates the dict."""
    model = _model(extinguish=1, firebreak=1, retreat_range=1, mission_gate=1)
    ff = _unit(model, (24, 25))
    assert isinstance(getattr(model, "managed_victims", None), dict)
    assert getattr(model, "managed_victims")
    model.managed_victims = {}
    assert ff._firefight_mission_resolved() is True
    model.managed_victims = None
    assert ff._firefight_mission_resolved() is True


def test_gate_predicate_draws_no_rng_and_creates_nothing() -> None:
    """The predicate is a pure read: same RNG state, no new model attribute."""
    model = _model(extinguish=1, firebreak=1, retreat_range=1, mission_gate=1)
    ff = _unit(model, (24, 25))
    before_state = agents.random.getstate()
    before_attrs = set(vars(model))
    for _ in range(3):
        ff._firefight_mission_resolved()
    assert agents.random.getstate() == before_state
    assert set(vars(model)) == before_attrs


# ---------------------------------------------------------------------------
# The ungated round: the SHIPPED DEFAULT as behaviour, and the fireproof depots.
# No case below passes an FF switch - each runs whatever common_fixed_variables ships.
# A full-suite run with the constants flipped showed that nothing outside this file
# notices firefighters fighting fire from step 1 (outputs/ungated_part1.txt 2.4), so
# these are the tests that catch the feature being re-gated or switched off.
# ---------------------------------------------------------------------------


def _shipped_model(seed: int = 101) -> WildFireModel:
    """A real model at the SHIPPED FF configuration: no switch is passed."""
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False
    return model


def _depot_cells(model: WildFireModel) -> set:
    cells = {tuple(c) for c in (getattr(model, "base_station_fireproof_cells", ()) or ())}
    assert len(cells) == 50, "two 5x5 fireproof depots expected at the shipped default"
    return cells


def _quiet_map_keeping_depots(model: WildFireModel, depots: set) -> None:
    """_quiet_map for every cell EXCEPT the depot, which keeps its fireproofed fuel 0.

    _quiet_map re-fuels every cell, depots included, so no case above ever sees the
    fireproofed state; this one does.
    """
    for agent in model.schedule.agents:
        if type(agent) is agents.Fire:
            agent.burning = False
            agent.burnt = False
            agent.has_burned = False
            agent.next_burning_state = False
            agent.smoke.smoke = False
            if (int(agent.pos[0]), int(agent.pos[1])) not in depots:
                agent.fuel = 8


def test_shipped_default_engages_while_every_victim_is_unresolved() -> None:
    """At the shipped values an idle unit fights fire BEFORE the mission is decided.

    Every victim of a fresh model is unresolved, so a gate-closed configuration would
    return None here (test_gate_closed_while_any_victim_is_unresolved_runs_no_feature_code).
    Ungated, the unit plans and engages, and retreat suppression is live (K = 1).
    """
    model = _shipped_model()
    _quiet_map(model)
    _line_x(model, 20)
    ff = _unit(model, (24, 25))
    assert ff._firefight_mission_resolved() is False
    ctx = ff._firefight_prepare()
    assert ctx is not None and ctx["plan"] is not None
    assert ctx["K"] == 1 and ctx["extinguish"] is True and ctx["firebreak"] is True
    ff.advance()
    assert _engaged_rows(model) >= 1


# The canonical tuple east/half/101 exactly as outputs/_ffr_harness.py builds it with no
# --set (scenario D, --roles half; the 9 keys of its params build). The recorded
# outputs/_ffr_sfON_east_half_101.json params add one --set extra,
# VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX=1, the shipped default, so it is omitted here:
# pinning it would hide a future change of that default from this guard.
_CANONICAL_EAST_HALF = {
    "NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2, "WIND_DIRECTION": "east",
    "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
    "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 2,
}


def test_shipped_default_engages_before_terminal_step_on_a_canonical_seed(monkeypatch) -> None:
    """THE RE-GATING GUARD: a full canonical run engages a firefighter while victims live.

    east/half/101 with scenario D's parameters, seeded the way evaluate_scenarios and the
    harness seed it, at the SHIPPED FF configuration. The run is stepped until the first
    engaged firefight row appears, checking all_victims_terminal after every step exactly
    as evaluate_scenarios._run_seed does. The first engagement must come while the mission
    is still undecided, i.e. strictly before terminal_step.

    Re-gating the feature (MISSION_GATE back to 1), switching both actions off, or
    breaking suppression so that no plan forms all fail this. Nothing OUTSIDE this file
    would notice (outputs/ungated_part1.txt 2.4). Inside it, the constant pins and
    test_shipped_default_engages_while_every_victim_is_unresolved catch the same
    constant flips (outputs/_ug_fallback_mutants.txt); this is the only test that checks
    engagement in a real stepped canonical run, strictly before terminal_step. Every
    value set here is set through monkeypatch, so nothing leaks into later tests.
    """
    rng = random.Random(101)
    for mod in (cfv, wf):
        monkeypatch.setattr(mod, "SYSTEM_RANDOM", rng, raising=False)
        for key, value in _CANONICAL_EAST_HALF.items():
            monkeypatch.setattr(mod, key, value, raising=False)
    monkeypatch.setattr(agents, "random", rng)
    engaged_at = None
    terminal_at = None
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for step in range(1, 61):
            model.step()
            if any(row["engaged"] for row in _log(model)):
                engaged_at = step
            mission = model.get_dashboard_state().get("mission_status", {}) or {}
            if mission.get("all_victims_terminal"):
                terminal_at = step
                break
            if engaged_at is not None:
                break
    assert engaged_at is not None, "no firefighter engaged in 60 steps at the shipped default"
    assert terminal_at is None, "the mission was decided no later than the first engagement"
    first = min(row["step"] for row in _log(model) if row["engaged"])
    assert first <= engaged_at
    managed = getattr(model, "managed_victims", None) or {}
    assert any(
        str(getattr(s, "status", "") or "").strip().lower() not in ("rescued", "dead")
        for s in managed.values() if s is not None
    ), "every victim was already resolved when the unit engaged"


def test_fireproof_depot_cells_are_never_fuel_work_or_a_target() -> None:
    """Non-burnable depots x the fire mechanic (outputs/ungated_part1.txt 3.1).

    At the shipped default both features are on: the depot cells have fuel 0 from
    reset, so the plan's fuel set must exclude them, no firebreak band cell may be a
    depot cell, and no target or write may land in one. The geometry puts depot 0's
    cells (x 0-4, y 45-49) inside the band of a burning line at x = 7 and stands the
    unit INSIDE the depot, so a depot cell would be the nearest band cell if it were
    ever treated as fuel.
    """
    model = _shipped_model()
    depots = _depot_cells(model)
    assert all(_fire(model, c).fuel <= 0 for c in depots)
    _quiet_map_keeping_depots(model, depots)
    _ignite(model, *[(7, y) for y in range(38, 50)])
    ff = _unit(model, (2, 47))
    assert (2, 47) in depots
    ctx = ff._firefight_prepare()
    assert ctx is not None and ctx["plan"] is not None
    assert not (ctx["fuel"] & depots)
    assert tuple(ctx["plan"][2]) not in depots
    for _ in range(15):
        ff.advance()
    rows = _log(model)
    assert rows
    for row in rows:
        if row.get("target") is not None:
            assert tuple(row["target"]) not in depots, row
    assert all(_fire(model, c).fuel <= 0 and not _fire(model, c).burning for c in depots)


def test_a_burning_cell_bordering_only_the_depot_is_not_front() -> None:
    """A burning cell whose only unburnt 4-neighbour is a depot cell is not FRONT and is
    never an extinguish target (outputs/ungated_part1.txt 3.1).

    The planner's front test is 4-neighbour only and depot cells (fuel 0) are never in
    its fuel set; the fire cannot spread INTO the depot. The cell CAN still ignite fuel
    diagonally or within the radius-3 spread neighbourhood, so "not front" is the
    planner's heuristic, not a claim that the cell cannot spread.
    """
    model = _shipped_model()
    depots = _depot_cells(model)
    _quiet_map_keeping_depots(model, depots)
    assert (4, 47) in depots
    _ignite(model, (5, 47))
    for cell in ((6, 47), (5, 46), (5, 48)):
        fire = _fire(model, cell)
        fire.has_burned = True
        fire.burnt = True
        fire.fuel = 0
    ff = _unit(model, (5, 45))
    ctx = ff._firefight_prepare()
    assert ctx is not None
    assert ctx["n_front"] == 0
    assert ctx["plan"] is None or ctx["plan"][0] != "extinguish"
