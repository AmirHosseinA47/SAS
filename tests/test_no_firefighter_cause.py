"""fix1 item 5: 'geographically_isolated' is no longer used when no rescuer existed.

The escape sweep writes a victim off after 30 steps without a safe path from any
reachability start. With every firefighter dead, carrying or off the grid there is no
start at all, so the streak runs for EVERY unserved victim - fire geometry has nothing
to do with it. Such a streak (no free rescuer on every one of its steps) is now written
off as no_firefighter_available; a streak with at least one step on which a free rescuer
existed keeps geographically_isolated. The write-off itself (step, effects) is unchanged.
"""

from __future__ import annotations

import contextlib
import io
import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from serve_dashboard import _build_evaluation
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.planning import rescue_planner as rp
from wildfire_model import WildFireModel

V0 = "victim_0"


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


# --------------------------------------------------------------------------- pure function

def _flags(no_start: bool, **extra) -> dict:
    entry = {"status": "confirmed", "confirmed": True, "geo_reachable": False}
    if no_start:
        entry["no_rescuer_start"] = True
    entry.update(extra)
    return {"v": entry}


def _sweep(steps, nostart=None):
    geo, und = {}, {}
    marked = []
    for no_start in steps:
        marked, geo, und = rp.unreachable_escape_victims(_flags(no_start), geo, und,
                                                         nostart_streaks=nostart)
    return marked, geo


def test_a_streak_with_no_rescuer_on_every_step_is_no_firefighter_available() -> None:
    nostart = {}
    marked, geo = _sweep([True] * 30, nostart)
    assert marked == [("v", rp.UNREACHABLE_CAUSE_NO_FIREFIGHTER)]
    assert geo == {"v": 30} and nostart == {"v": 30}


def test_one_step_with_a_rescuer_keeps_the_geographic_cause() -> None:
    marked, _ = _sweep([False] + [True] * 29, {})
    assert marked == [("v", rp.UNREACHABLE_CAUSE_GEOGRAPHIC)]
    marked, _ = _sweep([True] * 29 + [False], {})
    assert marked == [("v", rp.UNREACHABLE_CAUSE_GEOGRAPHIC)]


def test_without_the_dict_the_cause_is_geographic_as_before() -> None:
    marked, _ = _sweep([True] * 30, None)
    assert marked == [("v", rp.UNREACHABLE_CAUSE_GEOGRAPHIC)]


def test_a_reachable_step_resets_the_no_rescuer_count() -> None:
    geo, und, nostart = {}, {}, {}
    for _ in range(5):
        rp.unreachable_escape_victims(_flags(True), geo, und, nostart_streaks=nostart)
    rp.unreachable_escape_victims(_flags(True, geo_reachable=True), geo, und, nostart_streaks=nostart)
    assert geo == {"v": 0} and nostart == {"v": 0}
    rp.unreachable_escape_victims(_flags(True, terminal=True), geo, und, nostart_streaks=nostart)
    assert nostart == {"v": 0}
    rp.unreachable_escape_victims({}, geo, und, nostart_streaks=nostart)
    assert nostart == {}


# --------------------------------------------------------------------------- the model

def _model() -> WildFireModel:
    rng = random.Random(101)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=2, NUM_VICTIMS=3, NUM_FIREFIGHTERS=2,
                          WIND_DIRECTION="east", BATCH_SIZE=300, PROBABILITY_MAP=False)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False
    for a in model.schedule.agents:  # a quiet map: nothing burns
        if type(a) is agents.Fire:
            a.burning = a.burnt = a.has_burned = a.next_burning_state = False
            a.fuel = 8
            a.smoke.smoke = False
    for vid, marker in model.victim_marker_agents.items():
        state = model.managed_victims[vid]
        if vid == V0:  # a DETECTED victim, so item 4 never exempts it
            state.confirmed = True
            state.status = "confirmed"
            marker.status = "confirmed"
        else:
            state.status = "dead"
            marker.status = "dead"
    return model


def _kill_all_but(model, keep=()):
    for ff_id, ff in model.firefighter_marker_agents.items():
        if ff_id not in keep:
            ff.dead = True
            ff.status = "dead"


def _enclose(model, cell):
    cx, cy = cell
    for nxt in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
        if model.grid.out_of_bounds(nxt):
            continue
        for a in model.grid.get_cell_list_contents([nxt]):
            if type(a) is agents.Fire:
                a.burning = True


def _sweep_model(model, n):
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(n):
            model._update_unreachable_victims()
    return [e for e in model._unreachable_escape_log if e["victim_id"] == V0]


def test_every_firefighter_dead_writes_off_as_no_firefighter_available() -> None:
    model = _model()
    _kill_all_but(model)
    log = _sweep_model(model, 30)
    assert [(e["cause"], e["streak"]) for e in log] == [("no_firefighter_available", 30)]
    assert log[0]["firefighters_alive"] == 0
    state = model.managed_victims[V0]
    assert state.unreachable is True and state.unreachable_cause == "no_firefighter_available"
    ev = _build_evaluation(model, None, 30, {"WIND_DIRECTION": "east", "NUM_AGENTS": 2,
                                             "NUM_VICTIMS": 3, "NUM_FIREFIGHTERS": 2})
    assert ev["no_firefighter_available"] == 1
    assert ev["geographically_isolated"] == 0 and ev["unreachable_other"] == 0
    assert "victim_0:no_firefighter_available" in ev["unreachable_causes"]


def test_a_free_rescuer_that_cannot_reach_keeps_geographically_isolated() -> None:
    model = _model()
    keep = sorted(model.firefighter_marker_agents)[0]
    _kill_all_but(model, keep=(keep,))
    _enclose(model, tuple(model.victim_marker_agents[V0].pos))
    log = _sweep_model(model, 30)
    assert [(e["cause"], e["streak"]) for e in log] == [("geographically_isolated", 30)]
    assert "firefighters_alive" not in log[0]


def test_a_mixed_streak_is_geographic() -> None:
    """Fire isolates the victim while a free unit lives; the unit dies mid-streak."""
    model = _model()
    keep = sorted(model.firefighter_marker_agents)[0]
    _kill_all_but(model, keep=(keep,))
    _enclose(model, tuple(model.victim_marker_agents[V0].pos))
    assert _sweep_model(model, 10) == []
    _kill_all_but(model)
    log = _sweep_model(model, 20)
    assert [(e["cause"], e["streak"]) for e in log] == [("geographically_isolated", 30)]


def test_all_units_busy_counts_as_no_rescuer_with_live_firefighters() -> None:
    """Every live unit off the grid (a hand-over absence) - alive but no free rescuer."""
    model = _model()
    for ff in model.firefighter_marker_agents.values():
        model.grid.remove_agent(ff)  # pos None: not a reachability start
    log = _sweep_model(model, 30)
    assert [(e["cause"], e["streak"]) for e in log] == [("no_firefighter_available", 30)]
    assert log[0]["firefighters_alive"] == len(model.firefighter_marker_agents)
