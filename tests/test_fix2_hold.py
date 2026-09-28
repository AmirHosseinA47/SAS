"""fix2 item 2: a hold holds, and the fail-safe hold goes only to the UAV that must yield.

UAV_HOLD_STATIONARY (shipped 1; off only on an exact integral 0) - outputs/fix2_part1.txt section 2:
  (a) a committed 'hold' (and a tracker flank hold aimed at its own cell) leaves the UAV on its cell;
      the lateral flank step and 'hold_escape' still move; a return leg clears the stay;
  (b) the stay intends its own cell (no drift sample);
  (c) under SAFETY_FIRST the dispatcher holds only a UAV that must yield: airborne, not returning,
      named by its own COLLISION_RISK, with a LOWER-id airborne UAV within 2 - at most 3 steps in a
      row (ruling D-5). Every other UAV keeps its path.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.analysis.trigger_objects import SafetyTrigger, Scope, Severity
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.planning.decision_objects import FailSafeDecision, PathDecision
from wildfire_model import WildFireModel


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


@pytest.fixture
def switch(monkeypatch):
    def set_(value):
        monkeypatch.setattr(cfv, "UAV_HOLD_STATIONARY", value, raising=False)
    return set_


def _uavs(model):
    return sorted((a for a in model.schedule.agents if type(a) is agents.UAV), key=lambda a: a.unique_id)


def _airborne_model(cells):
    """A model with the depot off, so no UAV is docked or returning; UAVs placed on `cells`."""
    cfv.BASE_STATION_MODE = 0
    model = WildFireModel()
    uavs = _uavs(model)
    for uav, cell in zip(uavs, cells):
        model.grid.move_agent(uav, cell)
    return model, uavs


# --------------------------------------------------------------------------- the switch

def test_shipped_on() -> None:
    assert cfv.UAV_HOLD_STATIONARY == 1 and agents.uav_hold_stationary() is True
    assert agents.FAILSAFE_YIELD_MAX_STEPS == 3


@pytest.mark.parametrize("value, expected", [(0, False), ("0", False), (0.0, False), (1, True),
                                             (0.5, True), (None, True), ("no", True)])
def test_off_only_on_an_exact_integral_zero(switch, value, expected) -> None:
    switch(value)
    assert agents.uav_hold_stationary() is expected


# --------------------------------------------------------------------------- (a) the stay

@pytest.mark.parametrize("value, stays", [(1, True), (0, False)])
def test_a_stay_does_not_move(switch, value, stays) -> None:
    switch(value)
    model, u = _airborne_model([(20, 20), (30, 30), (40, 40)])
    uav = u[0]
    uav.selected_dir = 0                      # east, free
    uav.execution_direction_applied = True
    uav.execution_action = "hold"
    uav.execution_stay = True
    moved = uav.move()
    assert moved is (not stays)
    assert tuple(uav.pos) == ((20, 20) if stays else (21, 20))


@pytest.mark.parametrize("value, expected", [(1, 0.0), (0, 1.0)])
def test_a_stay_intends_its_own_cell(monkeypatch, switch, value, expected) -> None:
    switch(value)
    monkeypatch.setattr(cfv, "FAILSAFE_REAL_ALARMS", 0, raising=False)   # isolate item 2's part
    model, u = _airborne_model([(20, 20), (30, 30), (40, 40)])
    uav = u[0]
    uav.selected_dir = 0
    uav.execution_direction_applied = True
    uav.execution_action = "hold"
    uav.execution_stay = True
    uav.advance()
    if value:
        assert tuple(uav.pos) == (20, 20)
        assert uav._monitor_prev_drift_error == expected
    else:                                     # off: the hold moved, so no deviation either
        assert tuple(uav.pos) == (21, 20)


def test_a_return_leg_clears_the_stay(switch) -> None:
    switch(1)
    model = WildFireModel()                   # shipped depot (mode 3): UAVs own berths
    uav = _uavs(model)[0]
    berth = uav.rtb_berth
    far = (25, 25)
    model.grid.move_agent(uav, far)
    uav.battery_level = 40.0                  # at / below the return trigger from here
    uav.execution_direction_applied = True
    uav.execution_action = "hold"
    uav.execution_stay = True
    uav.advance()
    assert uav.rtb_active is True
    assert uav.execution_stay is False
    assert tuple(uav.pos) != far              # the return leg moved it
    assert abs(uav.pos[0] - berth[0]) + abs(uav.pos[1] - berth[1]) < abs(far[0] - berth[0]) + abs(far[1] - berth[1])


def _executor(model, uav):
    return UAVExecutor(uav_id=str(uav.unique_id), model=model, agent=uav)


@pytest.mark.parametrize("label, in_place, stays", [
    ("hold", False, True), ("hold_escape", False, False), ("fire_flank_hold", False, False),
    ("fire_flank_hold", True, True), ("fire_flank_relocate", True, False),
])
def test_which_labels_stay(switch, label, in_place, stays) -> None:
    switch(1)
    model, u = _airborne_model([(20, 20), (30, 30), (40, 40)])
    ex = _executor(model, u[0])
    ex._flank_hold_in_place = in_place
    ex._commit_execution_direction(u[0], 0, label)
    assert u[0].execution_stay is stays
    assert ex._flank_hold_in_place is False    # consumed by the commit


def test_commit_off_never_sets_a_stay(switch) -> None:
    switch(0)
    model, u = _airborne_model([(20, 20), (30, 30), (40, 40)])
    ex = _executor(model, u[0])
    ex._commit_execution_direction(u[0], 0, "hold")
    assert u[0].execution_stay is False


# --------------------------------------------------------------------------- (c) the yield

def _collision(uid):
    return SafetyTrigger(trigger_type="COLLISION_RISK", severity=Severity.MEDIUM, confidence=0.75,
                         scope=Scope.LOCAL, affected_entities=(str(uid),), timestamp=1.0,
                         recommended_planner="local_uav_path_planner", explanation_context="test")


def _yield_setup(cells, named):
    model, u = _airborne_model(cells)
    model.latest_analysis_snapshot = SimpleNamespace(all_triggers=tuple(_collision(a.unique_id) for a in named))
    return model, u, DecisionDispatcher(model=model)


def test_right_of_way_to_the_lower_id(switch) -> None:
    switch(1)
    model, u, d = _yield_setup([(20, 20), (21, 21), (40, 40)], named=[])
    model.latest_analysis_snapshot = SimpleNamespace(all_triggers=(_collision(u[0].unique_id),
                                                                   _collision(u[1].unique_id)))
    model.evaluation_timesteps_counter = 30
    assert d._must_yield(str(u[1].unique_id)) is True     # higher id, lower id within 2
    assert d._must_yield(str(u[0].unique_id)) is False    # the lower id proceeds
    assert d._must_yield(str(u[2].unique_id)) is False    # alone


def test_yield_needs_its_own_collision_trigger(switch) -> None:
    switch(1)
    model, u, d = _yield_setup([(20, 20), (21, 21), (40, 40)], named=[])
    model.evaluation_timesteps_counter = 30
    assert d._must_yield(str(u[1].unique_id)) is False


def test_returning_or_docked_never_yields(switch) -> None:
    switch(1)
    model, u, d = _yield_setup([(20, 20), (21, 21), (40, 40)], named=[])
    model.latest_analysis_snapshot = SimpleNamespace(all_triggers=(_collision(u[1].unique_id),))
    model.evaluation_timesteps_counter = 30
    u[1].rtb_active = True
    assert d._must_yield(str(u[1].unique_id)) is False
    u[1].rtb_active = False
    u[0].rtb_docked = True                                 # the lower-id UAV is parked
    d._yield_streaks.clear()
    assert d._must_yield(str(u[1].unique_id)) is False


def test_three_step_cap_then_proceed_then_yield_again(switch) -> None:
    switch(1)
    model, u, d = _yield_setup([(20, 20), (21, 21), (40, 40)], named=[])
    model.latest_analysis_snapshot = SimpleNamespace(all_triggers=(_collision(u[1].unique_id),))
    got = []
    for step in range(10, 16):
        model.evaluation_timesteps_counter = step
        got.append(d._must_yield(str(u[1].unique_id)))
        got_again = d._must_yield(str(u[1].unique_id))   # one answer per step
        assert got_again is got[-1]
    assert got == [True, True, True, False, True, True]


def test_dispatch_holds_only_the_yielding_uav(switch) -> None:
    switch(1)
    model, u, d = _yield_setup([(20, 20), (21, 21), (40, 40)], named=[])
    model.latest_analysis_snapshot = SimpleNamespace(all_triggers=(_collision(u[0].unique_id),
                                                                   _collision(u[1].unique_id)))
    model.evaluation_timesteps_counter = 30
    fs = FailSafeDecision(decision_id="fs", selected_option_id="safety-hold", fail_safe_action="safe_hold",
                          mission_mode="safety_first",
                          uncertainty_context={"fail_safe_mode": "safety_first"})
    paths = [PathDecision(decision_id="p%d" % i, uav_id=str(a.unique_id), selected_option_id="explore_x",
                          next_action="east") for i, a in enumerate(u)]
    seen = {}
    for a in u:
        ex = d._get_uav_executor(str(a.unique_id))
        orig = ex.execute

        def spy(decision, timestamp=0.0, fail_safe_decision=None, _o=orig, _id=str(a.unique_id)):
            seen[_id] = (decision.next_action, decision.selected_option_id)
            return _o(decision, timestamp, fail_safe_decision=fail_safe_decision)

        ex.execute = spy
    d._dispatch_local_paths(paths, 30.0, fs, fail_safe_override_active=True, override_reason="safety_first_mode")
    assert seen[str(u[1].unique_id)] == ("hold", "")          # yields: a fail-safe hold
    assert seen[str(u[0].unique_id)] == ("east", "explore_x")  # right of way: its own path
    assert seen[str(u[2].unique_id)] == ("east", "explore_x")  # not in a pair: its own path


def test_dispatch_off_rewrites_every_path(switch) -> None:
    switch(0)
    model, u, d = _yield_setup([(20, 20), (21, 21), (40, 40)], named=[])
    model.evaluation_timesteps_counter = 30
    fs = FailSafeDecision(decision_id="fs", selected_option_id="safety-hold", fail_safe_action="safe_hold",
                          mission_mode="safety_first",
                          uncertainty_context={"fail_safe_mode": "safety_first"})
    paths = [PathDecision(decision_id="p%d" % i, uav_id=str(a.unique_id), selected_option_id="explore_x",
                          next_action="east") for i, a in enumerate(u)]
    seen = {}
    for a in u:
        ex = d._get_uav_executor(str(a.unique_id))
        orig = ex.execute

        def spy(decision, timestamp=0.0, fail_safe_decision=None, _o=orig, _id=str(a.unique_id)):
            seen[_id] = decision.next_action
            return _o(decision, timestamp, fail_safe_decision=fail_safe_decision)

        ex.execute = spy
    d._dispatch_local_paths(paths, 30.0, fs, fail_safe_override_active=True, override_reason="safety_first_mode")
    assert set(seen.values()) == {"hold"}
