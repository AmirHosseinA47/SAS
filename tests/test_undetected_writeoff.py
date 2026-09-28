"""fix1 item 4: no permanent write-off of a victim nobody has detected.

Before: after 210 undetected steps (or 30 fire-isolated ones) the escape sweep marked a
never-detected victim unreachable - detection skipped it, dispatch dropped it, finalize
refused it - so at 360 steps rescues the remaining steps would have made were lost.
Now (UNDETECTED_WRITEOFF_FIX, ships 1): the victim is never written off while undetected
(ruling D-4b), a 210-step streak only LABELS it long_undetected, and never_detected in
the results means "not detected by the end of the run" (ruling D-4a).
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
PARAMS = {"WIND_DIRECTION": "east", "NUM_AGENTS": 2, "NUM_VICTIMS": 2, "NUM_FIREFIGHTERS": 2}


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


# --------------------------------------------------------------------------- accessor + pure function

@pytest.mark.parametrize("raw,on", [(1, True), (0, False), (0.0, False), ("0", False), (False, False),
                                    (0.5, True), ("off", True), (None, True)])
def test_switch_off_only_on_exact_zero(monkeypatch, raw, on) -> None:
    monkeypatch.setattr(cfv, "UNDETECTED_WRITEOFF_FIX", raw)
    assert agents.undetected_writeoff_fix() is on


def test_shipped_on() -> None:
    assert cfv.UNDETECTED_WRITEOFF_FIX == 1 and agents.undetected_writeoff_fix() is True


def _undetected(**extra):
    entry = {"status": "candidate", "confirmed": False, "geo_reachable": False}
    entry.update(extra)
    return {"v": entry}


def test_exempt_victim_is_never_marked_but_its_undetected_streak_counts() -> None:
    geo, und, nostart = {}, {}, {}
    for _ in range(300):
        marked, geo, und = rp.unreachable_escape_victims(_undetected(no_rescuer_start=True), geo, und,
                                                         nostart_streaks=nostart, exempt_undetected=True)
        assert marked == []
    assert geo == {"v": 0} and und == {"v": 300} and nostart == {"v": 0}


def test_a_detected_victim_is_still_written_off_when_exempting() -> None:
    geo, und = {}, {}
    for _ in range(30):
        marked, geo, und = rp.unreachable_escape_victims(
            {"v": {"status": "confirmed", "confirmed": True, "geo_reachable": False}}, geo, und,
            exempt_undetected=True)
    assert marked == [("v", rp.UNREACHABLE_CAUSE_GEOGRAPHIC)]


def test_without_exemption_the_legacy_write_off_stands() -> None:
    geo, und = {}, {}
    marked = []
    for _ in range(rp.UNDETECTED_STREAK_STEPS):
        marked, geo, und = rp.unreachable_escape_victims(_undetected(geo_reachable=True), geo, und)
    assert marked == [("v", rp.UNREACHABLE_CAUSE_UNDETECTED)]


# --------------------------------------------------------------------------- the model

def _model(**params) -> WildFireModel:
    rng = random.Random(5)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(cfv, wf, BATCH_SIZE=300, PROBABILITY_MAP=False, **PARAMS, **params)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False
    for a in model.schedule.agents:  # a quiet map
        if type(a) is agents.Fire:
            a.burning = a.burnt = a.has_burned = a.next_burning_state = False
            a.fuel = 8
            a.smoke.smoke = False
    for vid, marker in model.victim_marker_agents.items():
        if vid != V0:
            marker.status = "dead"
            model.managed_victims[vid].status = "dead"
    return model


def _sweep(model, n):
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(n):
            model.evaluation_timesteps_counter += 1
            model._update_unreachable_victims()


def _enclose(model, cell):
    cx, cy = cell
    for nxt in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
        if not model.grid.out_of_bounds(nxt):
            for a in model.grid.get_cell_list_contents([nxt]):
                if type(a) is agents.Fire:
                    a.burning = True


def test_a_long_undetected_victim_is_labelled_once_and_not_written_off() -> None:
    model = _model()
    _sweep(model, 250)
    state = model.managed_victims[V0]
    assert state.status == "candidate" and not getattr(state, "unreachable", False)
    assert not getattr(state, "cancelled", False)
    assert [e for e in model._unreachable_escape_log if e["victim_id"] == V0] == []
    assert state.attributes["undetected_streak_label"] == "long_undetected"
    assert model._long_undetected_log == [{"step": 210, "victim_id": V0, "streak": 210}]


def test_the_labelled_victim_can_still_be_detected_and_dispatched() -> None:
    model = _model()
    _sweep(model, 220)
    marker = model.victim_marker_agents[V0]
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    model.grid.move_agent(uav, tuple(marker.pos))
    with contextlib.redirect_stdout(io.StringIO()):
        model._detect_victims_in_uav_radius()
        model._process_rescue_incidents()
    state = model.managed_victims[V0]
    assert state.confirmed is True
    assert state.rescue_assigned is True and state.status == "assigned"
    assert state.attributes["undetected_streak_label"] == "long_undetected"  # the label stays


def test_an_undetected_fire_isolated_victim_is_not_written_off() -> None:
    """Ruling D-4b: fire isolation before detection no longer makes a victim undetectable."""
    model = _model()
    _enclose(model, tuple(model.victim_marker_agents[V0].pos))
    _sweep(model, 60)
    state = model.managed_victims[V0]
    assert state.status == "candidate" and model._unreachable_geo_streak.get(V0) == 0


def test_switch_zero_is_the_permanent_write_off() -> None:
    model = _model(UNDETECTED_WRITEOFF_FIX=0)
    _sweep(model, 210)
    state = model.managed_victims[V0]
    assert state.status == "unreachable" and state.unreachable_cause == "never_detected"
    assert not hasattr(model, "_long_undetected_log")
    marker = model.victim_marker_agents[V0]
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    model.grid.move_agent(uav, tuple(marker.pos))
    with contextlib.redirect_stdout(io.StringIO()):
        model._detect_victims_in_uav_radius()
    assert not state.confirmed  # the pre-fix1 defect, kept at switch 0


def test_switch_zero_writes_off_a_fire_isolated_undetected_victim() -> None:
    model = _model(UNDETECTED_WRITEOFF_FIX=0)
    _enclose(model, tuple(model.victim_marker_agents[V0].pos))
    _sweep(model, 30)
    assert model.managed_victims[V0].status == "unreachable"


def test_end_of_run_never_detected_is_counted_inside_unreachable() -> None:
    model = _model()
    _sweep(model, 250)
    ev = _build_evaluation(model, None, 250, PARAMS)
    assert ev["never_detected"] == 1 and ev["unreachable"] == 1 and ev["candidate"] == 0
    assert ev["all_terminal"] is False  # never terminal in the run (review, risk 2)
    assert "victim_0:never_detected" in ev["unreachable_causes"]
    assert ev["long_undetected"] == 1 and ev["long_undetected_detected"] == 0
    assert ev["rescued"] + ev["dead"] + ev["unreachable"] + ev["candidate"] == ev["total_victims"]


def test_a_detected_unresolved_victim_stays_unresolved_at_the_end() -> None:
    model = _model()
    _sweep(model, 220)
    state = model.managed_victims[V0]
    state.confirmed = True
    state.status = "confirmed"
    ev = _build_evaluation(model, None, 220, PARAMS)
    assert ev["never_detected"] == 0 and ev["candidate"] == 1
    assert ev["long_undetected"] == 1 and ev["long_undetected_detected"] == 1


def test_short_run_at_switch_zero_keeps_an_undetected_victim_unresolved() -> None:
    """At switch 0 the evaluation is exactly the pre-fix1 one: no end-of-run classification."""
    model = _model(UNDETECTED_WRITEOFF_FIX=0)
    _sweep(model, 100)
    ev = _build_evaluation(model, None, 100, PARAMS)
    assert ev["never_detected"] == 0 and ev["candidate"] == 1 and ev["long_undetected"] == 0
