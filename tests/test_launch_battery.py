"""fix1 item 2: scenario B's reduced launch charge and the ONE battery threshold source.

B used to differ from A only in team counts. It now launches every UAV at
UAV_LAUNCH_BATTERY_FRACTION (0.5) of its launch battery - f x L_i, L_i = 100 today, and
session 2's staggered launch battery replaces L_i only. REDUCED_LAUNCH_BATTERY is the
switch (ships 1, off only on an exact integral zero). The low / critical thresholds
(30 / 15) have one source, read at call time; the resource model's 20 / 50 pair is gone.
"""

from __future__ import annotations

import contextlib
import io
import math
import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import evaluate_scenarios as es
import wildfire_model as wf
from serve_dashboard import BUILTIN_SCENARIOS, scenario_extra_params
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.knowledge.uav_resource_model import UAVResourceModel
from wildfire_model import WildFireModel

_MISSING = object()


@pytest.fixture(autouse=True)
def _restore_module_config():
    saved = {mod: {n: getattr(mod, n) for n in dir(mod) if n.isupper()} for mod in (cfv, wf)}
    saved_random = agents.random
    yield
    for mod, values in saved.items():
        for name in [n for n in dir(mod) if n.isupper() and n not in values]:
            delattr(mod, name)
        for name, value in values.items():
            setattr(mod, name, value)
    agents.random = saved_random


def _set(monkeypatch, name, raw):
    if raw is _MISSING:
        monkeypatch.delattr(cfv, name, raising=False)
    else:
        monkeypatch.setattr(cfv, name, raw)


# --------------------------------------------------------------------------- accessors

def test_shipped_values() -> None:
    assert cfv.UAV_LAUNCH_BATTERY_FRACTION == 1.0 and cfv.REDUCED_LAUNCH_BATTERY == 1
    assert agents.battery_low_threshold() == 30.0
    assert agents.battery_critical_threshold() == 15.0
    assert agents.reduced_launch_battery() is True
    assert agents.uav_launch_battery(0) == 100.0


@pytest.mark.parametrize("raw", [0, 0.0, "0", " 0 ", False])
def test_the_switch_is_off_only_on_an_exact_zero(monkeypatch, raw) -> None:
    _set(monkeypatch, "REDUCED_LAUNCH_BATTERY", raw)
    assert agents.reduced_launch_battery() is False


@pytest.mark.parametrize("raw", [1, 1.0, "1", True, 2, -1, 0.5, "off", "", None, math.nan, _MISSING])
def test_anything_else_keeps_the_switch_on(monkeypatch, raw) -> None:
    _set(monkeypatch, "REDUCED_LAUNCH_BATTERY", raw)
    assert agents.reduced_launch_battery() is True


@pytest.mark.parametrize("raw", [0, 0.0, -0.5, 1.5, math.nan, math.inf, "half", None])
def test_an_invalid_fraction_raises_instead_of_falling_back(monkeypatch, raw) -> None:
    _set(monkeypatch, "UAV_LAUNCH_BATTERY_FRACTION", raw)
    with pytest.raises(ValueError):
        agents.uav_launch_battery_fraction()


@pytest.mark.parametrize("raw,expected", [(1.0, 100.0), (0.5, 50.0), ("0.25", 25.0), (1, 100.0), (_MISSING, 100.0)])
def test_launch_battery_is_fraction_times_full(monkeypatch, raw, expected) -> None:
    _set(monkeypatch, "UAV_LAUNCH_BATTERY_FRACTION", raw)
    assert agents.uav_launch_battery(0) == expected
    assert agents.uav_launch_battery(7) == expected  # L_i is not staggered yet (session 2)


def test_switch_off_ignores_the_fraction_even_a_junk_one(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "REDUCED_LAUNCH_BATTERY", 0)
    monkeypatch.setattr(cfv, "UAV_LAUNCH_BATTERY_FRACTION", 0.5)
    assert agents.uav_launch_battery(0) == 100.0
    monkeypatch.setattr(cfv, "UAV_LAUNCH_BATTERY_FRACTION", "junk")
    assert agents.uav_launch_battery(0) == 100.0


@pytest.mark.parametrize("level,label", [(100, "normal"), (30.01, "normal"), (30, "low"), (20, "low"),
                                         (15.01, "low"), (15, "critical"), (0, "critical")])
def test_battery_status_for(level, label) -> None:
    assert agents.battery_status_for(level) == label


def test_thresholds_are_read_at_call_time(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "LOW_BATTERY_THRESHOLD", 40.0)
    monkeypatch.setattr(cfv, "BATTERY_CRITICAL_THRESHOLD", 20.0)
    assert agents.battery_status_for(35) == "low"
    assert agents.battery_status_for(20) == "critical"
    uav = agents.UAV.__new__(agents.UAV)  # the label update needs only these fields
    uav.battery_level, uav.battery_drain_per_step, uav.battery_drain_per_move = 35.3, 0.1, 0.2
    uav.rtb_docked = False
    uav._update_battery_after_step(True)
    assert uav.battery_status == "low"  # 35.0 <= the overridden LOW of 40


@pytest.mark.parametrize("level,label", [(40.0, "normal"), (30.0, "low"), (20.0, "low"), (15.0, "critical")])
def test_resource_model_labels_come_from_the_same_source(level, label) -> None:
    """Was < 20 critical / < 50 low / 'nominal' - a pair no live reader saw."""
    model = UAVResourceModel()
    model.update_battery(uav_id="u1", battery_level=level, timestamp=1.0)
    assert model.by_uav_id["u1"].battery_status == label


# --------------------------------------------------------------------------- scenario presets

def test_only_scenario_b_reduces_the_launch_fraction() -> None:
    """Every scenario states its fraction (A, C, D 1.0), so an in-process run of A after B
    cannot inherit B's 0.5 through the never-reset module globals (review, risk 4)."""
    assert scenario_extra_params("B") == {"UAV_LAUNCH_BATTERY_FRACTION": 0.5}
    for key in ("A", "C", "D", "nope"):
        assert scenario_extra_params(key) == {"UAV_LAUNCH_BATTERY_FRACTION": 1.0}
    assert "Battery-Constrained" in BUILTIN_SCENARIOS["B"]["label"]


def _args(scenario):
    import argparse

    return argparse.Namespace(scenario=scenario, wind="east", uavs=None, victims=None,
                              firefighters=None, batch_size=None, steps=360, fire_spread=0.75)


def test_evaluate_params_pass_b_fraction_and_full_charge_elsewhere() -> None:
    assert es._scenario_params(_args("B"))["UAV_LAUNCH_BATTERY_FRACTION"] == 0.5
    for key in ("A", "C", "D"):
        assert es._scenario_params(_args(key))["UAV_LAUNCH_BATTERY_FRACTION"] == 1.0


def test_a_after_b_in_one_process_runs_at_full_charge() -> None:
    def launch(key):
        return {"UAV_LAUNCH_BATTERY_FRACTION": es._scenario_params(_args(key))["UAV_LAUNCH_BATTERY_FRACTION"]}

    assert {u.battery_level for u in _uavs(_model(**launch("B")))} == {50.0}
    assert {u.battery_level for u in _uavs(_model(**launch("A")))} == {100.0}


# --------------------------------------------------------------------------- the model

def _model(**params) -> WildFireModel:
    # fix2 item 4: these tests pin fix1's launch FRACTION on the unstaggered L_i = 100, so the
    # stagger (a separate switch) is held at 0 here; its composition with the fraction
    # (0.5 x L_i) is pinned in tests/test_fix2_stagger.py.
    params.setdefault("STAGGERED_LAUNCH_BATTERY", 0)
    rng = random.Random(3)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=3, NUM_VICTIMS=2, NUM_FIREFIGHTERS=2,
                          WIND_DIRECTION="east", BATCH_SIZE=300, PROBABILITY_MAP=False, **params)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False
    return model


def _uavs(model):
    return [a for a in model.schedule.agents if type(a) is agents.UAV]


@pytest.mark.parametrize("params,level,label", [
    ({}, 100.0, "normal"),
    ({"UAV_LAUNCH_BATTERY_FRACTION": 0.5}, 50.0, "normal"),
    ({"UAV_LAUNCH_BATTERY_FRACTION": 0.25}, 25.0, "low"),
    ({"UAV_LAUNCH_BATTERY_FRACTION": 0.1}, 10.0, "critical"),
    ({"UAV_LAUNCH_BATTERY_FRACTION": 0.5, "REDUCED_LAUNCH_BATTERY": 0}, 100.0, "normal"),
])
def test_every_uav_launches_with_the_scenario_charge(params, level, label) -> None:
    model = _model(**params)
    uavs = _uavs(model)
    assert len(uavs) == 3
    for uav in uavs:
        assert uav.battery_level == level and uav.battery_status == label
        managed = model.managed_uav_states[str(uav.unique_id)]
        assert managed.battery_level == level and managed.battery_status == label


def test_an_invalid_fraction_stops_the_model_build() -> None:
    with pytest.raises(ValueError, match="UAV_LAUNCH_BATTERY_FRACTION"):
        _model(UAV_LAUNCH_BATTERY_FRACTION=0.0)


def test_a_half_charged_uav_turns_home_early() -> None:
    """At half charge the return trigger (0.3 x distance + 39.23) fires within ~40 steps."""
    model = _model(UAV_LAUNCH_BATTERY_FRACTION=0.5)
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(40):
            model.step()
    for uav in _uavs(model):
        assert uav.rtb_trips >= 1
        assert uav.rtb_log[0]["trigger_step"] <= 40
        assert uav.rtb_log[0]["trigger_distance"] > 0  # in flight, not a dock in place
