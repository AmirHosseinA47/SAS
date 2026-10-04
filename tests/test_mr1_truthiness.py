"""isTrue round F-1 (outputs/isTrue_part1.txt 5.1; rulings in its section 10): MR1_TRUTHINESS_FIX (ships 1).

UAV.surrounding_states - the MR1 input - counts a burning cell by truthiness. After the fire's first spread tick every
burning cell holds a numpy True, which the inherited `is True` test never counted. At MR1_TRUTHINESS_FIX 0 the method
is the inherited identity test exactly (the kill-switch test pins it). The fix tests FAIL on f686e932 (verified red in
Part 2); every test sets its own configuration through monkeypatch.
"""
from __future__ import annotations

import contextlib
import io
import os
import random
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pytest

import agents
import common_fixed_variables as cfv

os.environ.setdefault("MPLBACKEND", "Agg")

_JUNK = ("off", "", None, 0.5, -0.5, "0.5", "2.0", float("inf"), float("nan"), Decimal("0.5"), Fraction(1, 2),
         [], object())
_EXACT_ZEROS = (0, 0.0, "0", " 0 ", False, Decimal("0"), np.int64(0))
_ONES = (1, 1.0, "1", True, -1, 2, np.int64(1))


# ============================================================================ the switch
def test_mr1_truthiness_fix_ships_on():
    src = open(cfv.__file__, encoding="utf-8").read()
    assert "\nMR1_TRUTHINESS_FIX = 1\n" in src
    assert agents.mr1_truthiness_fix() is True


def test_mr1_truthiness_fix_turns_off_only_on_an_exact_zero(monkeypatch):
    fn = getattr(agents, "mr1_truthiness_fix")
    for raw in _EXACT_ZEROS:
        monkeypatch.setattr(cfv, "MR1_TRUTHINESS_FIX", raw, raising=False)
        assert fn() is False, raw
    for raw in _ONES + _JUNK:
        monkeypatch.setattr(cfv, "MR1_TRUTHINESS_FIX", raw, raising=False)
        assert fn() is True, raw
    monkeypatch.delattr(cfv, "MR1_TRUTHINESS_FIX", raising=False)
    assert fn() is True, "missing"


# ============================================================================ the MR1 input on a real model
def _model(monkeypatch, seed=9613):
    import wildfire_model as wf

    rng = random.Random(seed)
    for mod in (cfv, wf):
        monkeypatch.setattr(mod, "SYSTEM_RANDOM", rng, raising=False)
        # scenario A's team, pinned: other tests call apply_scenario_config (e.g. NUM_VICTIMS=3) and leave it set
        for name, value in (("NUM_AGENTS", 3), ("NUM_VICTIMS", 5), ("NUM_FIREFIGHTERS", 3)):
            monkeypatch.setattr(mod, name, value, raising=False)
    monkeypatch.setattr(agents, "random", rng, raising=False)
    with contextlib.redirect_stdout(io.StringIO()):
        model = wf.WildFireModel()
    model.debug_log = False
    return model


def _uavs(model):
    return [a for a in model.schedule.agents if type(a) is agents.UAV]


def _box_fires(model, uav):
    cells = model.grid.get_neighborhood(uav.pos, moore=uav.moore, include_center=True,
                                        radius=agents.UAV_OBSERVATION_RADIUS)
    return [f for c in cells for f in model.grid.get_cell_list_contents([c]) if type(f) is agents.Fire]


def _set_box(model, uav, value, n=4):
    """Every Fire cell in the UAV's box not burning (Python False), then n of them burning with `value`."""
    fires = _box_fires(model, uav)
    assert len(fires) >= n
    for f in fires:
        f.burning = False
    for f in fires[:n]:
        f.burning = value
    return fires[:n]


def test_f1_a_numpy_true_burning_cell_is_counted(monkeypatch):
    # FAILS on f686e932: surrounding_states counted `is_burning() is True`, so the 4 numpy-True cells counted 0
    model = _model(monkeypatch)
    uav = _uavs(model)[0]
    _set_box(model, uav, np.True_)
    assert sum(uav.surrounding_states()) == 4


def test_f1_b_kill_switch_is_the_inherited_identity_test(monkeypatch):
    model = _model(monkeypatch)
    uav = _uavs(model)[0]
    monkeypatch.setattr(cfv, "MR1_TRUTHINESS_FIX", 0, raising=False)
    _set_box(model, uav, np.True_)
    assert sum(uav.surrounding_states()) == 0          # what the model computed before the fix
    _set_box(model, uav, True)
    assert sum(uav.surrounding_states()) == 4          # the seeded cell's Python True was always counted


def test_f1_c_a_cell_counts_once_and_only_while_burning(monkeypatch):
    # FAILS on f686e932 (the numpy-True cells counted 0)
    model = _model(monkeypatch)
    uav = _uavs(model)[0]
    fires = _set_box(model, uav, np.True_)
    on = uav.surrounding_states()
    assert len(on) == len(_box_fires(model, uav)) and sorted(set(on)) == [0, 1] and sum(on) == 4
    for f in fires:
        f.burning = np.False_
    assert sum(uav.surrounding_states()) == 0


def test_f1_d_mr1_accumulates_the_truthy_count(monkeypatch):
    # FAILS on f686e932: MR1 added 0 for the UAV whose box holds 4 numpy-True cells
    model = _model(monkeypatch)
    uavs = _uavs(model)
    _set_box(model, uavs[0], np.True_)
    expected = [cfv.normalize(float(sum(u.surrounding_states())), cfv.N_OBSERVATIONS, 1, 0) for u in uavs]
    before = list(model.MR1_LIST)
    model.MR1(model.state())
    assert [b - a for a, b in zip(before, model.MR1_LIST)] == expected
    assert expected[0] == cfv.normalize(4.0, cfv.N_OBSERVATIONS, 1, 0) > 0


def test_f1_e_the_cause_fire_spread_writes_a_numpy_bool(monkeypatch):
    """Characterisation, not a fix test: after a spread tick next to a burning cell, Fire.burning is a numpy bool
    (generated < cell_prob, cell_prob a numpy float from cfv.euclidean_distance). It holds before and after F-1; it
    fails only if the fire's type changes, which is when F-1's rejected alternative must be revisited."""
    model = _model(monkeypatch)
    fires = [a for a in model.schedule.agents if type(a) is agents.Fire and a.fuel > 0 and not a.burnt]
    cell = fires[len(fires) // 2]
    x, y = cell.pos
    neighbour = next(f for f in fires if f.pos == (x + 1, y))
    neighbour.burning = True
    cell.steps_counter = cfv.FIRE_SPREAD_SPEED - 1     # the next step() is a spread tick
    cell.step()
    cell.advance()
    assert type(cell.cell_prob).__module__ == "numpy" and cell.cell_prob > 0
    assert type(cell.burning).__module__ == "numpy"
    assert cell.burning is not True and cell.burning is not False
