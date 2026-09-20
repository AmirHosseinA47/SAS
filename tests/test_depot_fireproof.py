"""Non-burnable depot cells, and the colour that says so.

serve_dashboard._cell_color had NO test coverage before this file: a grep for
_cell_color / _veg_color / _capture_frame over tests/ returned nothing, and every
existing colour assertion goes through main.agent_portrayal or compares bare
literals. Both surfaces are asserted here, against the same predicate, because
they are two independent transcriptions of one rule.
"""
from __future__ import annotations

import contextlib
import io
import random

import pytest

import agents
import common_fixed_variables as cfv
import main
import serve_dashboard as sd
from common_fixed_variables import (FIRE_COLORS, FUEL_BOTTOM_LIMIT, SMOKE_COLORS,
                                    VEGETATION_COLORS)
from wildfire_model import WildFireModel

CLEARED = "#193cff"


class _Smoke:
    def __init__(self, active=False):
        self._a = active

    def is_smoke_active(self):
        return self._a


class _Cell:
    """The four Fire-agent states _cell_color distinguishes, with nothing else."""

    def __init__(self, fuel, burning=False, burnt=False, has_burned=False, smoke=False):
        self.fuel = fuel
        self.burning = burning
        self.burnt = burnt
        self.has_burned = has_burned
        self.smoke = _Smoke(smoke)

    def is_burning(self):
        return self.burning

    def is_burnt(self):
        return self.burnt

    def get_fuel(self):
        return round(self.fuel)

    def get_prob(self):
        return 0.0


# --- the colour itself --------------------------------------------------------

def test_cleared_colour_is_distinct_from_every_other_map_colour():
    """Equality alone would survive someone collapsing two branches later.

    Mirrors test_base_station.test_depot_colour_is_distinct_from_every_ground_colour.
    The measured margins are in outputs/_dfp_colour.txt; this only guards the
    identities, which are what a later edit could silently break.
    """
    assert CLEARED not in VEGETATION_COLORS
    assert CLEARED not in FIRE_COLORS
    assert CLEARED not in SMOKE_COLORS
    assert CLEARED != "#2b2b2b"                 # burnt
    assert CLEARED != "#895e00"                 # scorched
    assert CLEARED != "#2f4a1a"                 # spared vegetation
    assert CLEARED != "#770099"                 # depot outline / BASE banner
    assert CLEARED != VEGETATION_COLORS[0]      # the #414141 it replaces
    assert CLEARED not in {"#00FFFF", "#FF00FF", "#0066CC", "#FF8C00", "#888888",
                           "#00FFCC", "#00BFFF", "#FFFF00", "#FFA500", "#00AAFF",
                           "#000000", "#ffffff", "#78aaff", "#ffd75a"}


def test_all_three_surfaces_carry_the_same_literal():
    """The dashboard's Python, the dashboard's JavaScript and the mesa canvas."""
    assert main.CLEARED_COLOR == CLEARED
    assert sd._cell_color(_Cell(0)) == CLEARED
    assert ('const NOFUEL="%s";' % CLEARED) in sd.HTML


# --- the predicate, on both surfaces -----------------------------------------

STATES = [
    ("plain vegetation", _Cell(FUEL_BOTTOM_LIMIT), None),
    ("cleared", _Cell(0), CLEARED),
    ("burning", _Cell(5, burning=True, has_burned=True), None),
    ("burnt", _Cell(0, burnt=True, has_burned=True), "#2b2b2b"),
    ("scorched", _Cell(4, has_burned=True), "#895e00"),
    ("extinguished (fuel 0 but it BURNED)", _Cell(0, has_burned=True), "#895e00"),
    ("smoking", _Cell(0, smoke=True), SMOKE_COLORS[0]),
]


@pytest.mark.parametrize("label,cell,expect", STATES, ids=[s[0] for s in STATES])
def test_cell_colour_branch_order(label, cell, expect):
    """A fuel-0 cell that HAS burned must stay scorched/burnt, not read as cleared."""
    got = sd._cell_color(cell)
    if expect is None:
        assert got != CLEARED, label
    else:
        assert got == expect, label


def _as_fire(cell):
    """The same state, wearing the class main.agent_portrayal dispatches on.

    agent_portrayal branches on `type(agent) is agents.Fire`, so a stand-in has to
    BE one. Constructed without __init__ because that would draw from the RNG and
    need a model; every attribute the portrayal reads is set here.
    """
    a = object.__new__(agents.Fire)
    a.fuel, a.burning, a.burnt = cell.fuel, cell.burning, cell.burnt
    a.has_burned, a.smoke, a.cell_prob = cell.has_burned, cell.smoke, 0.0
    return a


@pytest.mark.parametrize("label,cell,_expect", STATES, ids=[s[0] for s in STATES])
def test_mesa_canvas_agrees_with_the_dashboard_on_every_state(label, cell, _expect):
    """Two independent transcriptions of one rule; they must not drift apart.

    Compares the SURFACES - what each one actually paints - not a helper against a
    colour. main._is_cleared is only the fuel/burn half of the rule; the smoke test
    lives in agent_portrayal, ahead of it, exactly as it does in _cell_color. An
    earlier version of this test asserted the helper alone matched the colour and
    failed on the smoking row for that reason.
    """
    assert main.agent_portrayal(_as_fire(cell))["Color"] == sd._cell_color(cell), label


def test_cleared_branch_is_unreachable_without_a_fuel_clear():
    """FUEL_BOTTOM_LIMIT is the floor at construction, and fuel only falls while
    burning - which sets has_burned first (agents.py Fire.step). So with both the
    fireproof switch and the fire mechanic off, no cell can reach this branch and
    the rendered surface is unchanged."""
    assert FUEL_BOTTOM_LIMIT > 0
    for fuel in range(FUEL_BOTTOM_LIMIT, cfv.FUEL_UPPER_LIMIT + 1):
        assert sd._cell_color(_Cell(fuel)) != CLEARED


# --- the legend ---------------------------------------------------------------

def test_cleared_chip_is_in_both_legend_branches():
    html = sd.HTML
    j = html.index("function setLegend(){")
    legend = html[j:html.index("function showEval(", j)]
    prob_branch, normal_branch = legend.split("\n  :'", 1)
    chip = '<span><i class="sw" style="background:%s"></i>cleared (no fuel)</span>' % CLEARED
    assert chip in prob_branch
    assert chip in normal_branch
    k = html.index("document.getElementById('probtoggle').onclick")
    assert "setLegend();" in html[k:html.index("};", k)]


# --- the simulation change ----------------------------------------------------

def _model(fireproof, dry=0, seed=101):
    cfv.BASE_STATION_FIREPROOF = fireproof
    cfv.BASE_STATION_FIREPROOF_DRY_RUN = dry
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    agents.random = rng
    with contextlib.redirect_stdout(io.StringIO()):
        m = WildFireModel()
    m.debug_log = False
    return m


@pytest.fixture(autouse=True)
def _restore_switch():
    before = (getattr(cfv, "BASE_STATION_FIREPROOF", 1),
              getattr(cfv, "BASE_STATION_FIREPROOF_DRY_RUN", 0),
              cfv.SYSTEM_RANDOM, agents.random)
    yield
    (cfv.BASE_STATION_FIREPROOF, cfv.BASE_STATION_FIREPROOF_DRY_RUN,
     cfv.SYSTEM_RANDOM, agents.random) = before


def _fuels(model):
    cells = set(model.base_station["cells"])
    inside, outside = [], []
    for a in model.schedule.agents:
        if type(a) is not agents.Fire or a.pos is None:
            continue
        (inside if tuple(a.pos) in cells else outside).append(a.fuel)
    return inside, outside


def test_switch_on_clears_every_depot_cell_and_nothing_else():
    m = _model(1)
    inside, outside = _fuels(m)
    assert len(inside) == 50                       # two 5x5 depots
    assert set(inside) == {0}
    assert 0 not in outside
    assert m.base_station_fireproof_cleared == 50
    assert len(m.base_station_fireproof_cells) == 50


def test_switch_off_writes_nothing():
    m = _model(0)
    inside, outside = _fuels(m)
    assert 0 not in inside and 0 not in outside
    assert m.base_station_fireproof_cleared == 0
    assert m.base_station_fireproof_cells == ()


def test_dry_run_identifies_the_cells_and_clears_none():
    m = _model(1, dry=1)
    inside, _outside = _fuels(m)
    assert 0 not in inside
    assert m.base_station_fireproof_cleared == 0
    assert len(m.base_station_fireproof_cells) == 50


def test_a_cleared_cell_can_never_ignite_and_never_becomes_burnt():
    """probability_of_fire returns 0 at fuel 0, and `burnt` needs has_burned."""
    m = _model(1)
    cell = sorted(m.base_station["cells"])[0]
    fire = next(a for a in m.grid.get_cell_list_contents([cell]) if type(a) is agents.Fire)
    assert fire.probability_of_fire() == 0
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(12):
            m.step()
    assert not fire.is_burning() and not fire.is_burnt()
    assert not getattr(fire, "has_burned", False)
    assert sd._cell_color(fire) == CLEARED


def test_a_fractional_override_cannot_silently_flip_either_switch():
    """int(0.5) is 0. A bare int() cast would read --set ...=0.5 as OFF while
    params recorded 0.5 - a non-zero value disarming the feature with nothing
    saying so. Both accessors fall back instead, like ff_firefight_mission_gate."""
    keep = (cfv.BASE_STATION_FIREPROOF, cfv.BASE_STATION_FIREPROOF_DRY_RUN)
    try:
        for frac in (0.5, -0.5, 0.9, 1.5):
            cfv.BASE_STATION_FIREPROOF = frac
            assert agents.base_station_fireproof() is True, frac
            cfv.BASE_STATION_FIREPROOF_DRY_RUN = frac
            assert agents.base_station_fireproof_dry_run() is False, frac
        # integral floats are honoured, both ways
        cfv.BASE_STATION_FIREPROOF = 0.0
        assert agents.base_station_fireproof() is False
        cfv.BASE_STATION_FIREPROOF = 1.0
        assert agents.base_station_fireproof() is True
        cfv.BASE_STATION_FIREPROOF_DRY_RUN = 1.0
        assert agents.base_station_fireproof_dry_run() is True
    finally:
        cfv.BASE_STATION_FIREPROOF, cfv.BASE_STATION_FIREPROOF_DRY_RUN = keep


def test_accessors_survive_junk_values():
    """Both fall back the way the module says they do, and only an exact zero
    disarms the feature - the recorded base-station hazard, stated out loud."""
    keep = (cfv.BASE_STATION_FIREPROOF, cfv.BASE_STATION_FIREPROOF_DRY_RUN)
    try:
        for junk in ("off", "", None, [], {}):
            cfv.BASE_STATION_FIREPROOF = junk
            assert agents.base_station_fireproof() is True, junk
            cfv.BASE_STATION_FIREPROOF_DRY_RUN = junk
            assert agents.base_station_fireproof_dry_run() is False, junk
        for zero in (0, "0", False, 0.0):
            cfv.BASE_STATION_FIREPROOF = zero
            assert agents.base_station_fireproof() is False, zero
        for one in (1, "1", True, 2, -1):
            cfv.BASE_STATION_FIREPROOF = one
            assert agents.base_station_fireproof() is True, one
        del cfv.BASE_STATION_FIREPROOF
        assert agents.base_station_fireproof() is True
        del cfv.BASE_STATION_FIREPROOF_DRY_RUN
        assert agents.base_station_fireproof_dry_run() is False
    finally:
        cfv.BASE_STATION_FIREPROOF, cfv.BASE_STATION_FIREPROOF_DRY_RUN = keep
