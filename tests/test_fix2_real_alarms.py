"""fix2 item 1: each fail-safe alarm fires only on the condition it names.

FAILSAFE_REAL_ALARMS (shipped 1; off only on an exact integral 0) - outputs/fix2_part1.txt 1a-1d':
  COLLISION_RISK        another AIRBORNE UAV within Manhattan 2 (docked UAVs excluded)
  DRIFT_TOO_HIGH        a refused move on >= 2 of the last 5 steps; no latch; a docked UAV
                        holding its berth intends its own cell
  CRITICAL_LINK_...     real delivery outcomes only
  search_mode_required  from the fleet-level FLEET_FIRE_LOST, not one UAV's empty window
and with no fail-safe reason the fail-safe planner decides nothing (the planning echo).
"""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.adaptation_results import FailSafeAdaptationSpace
from src_extension.analysis.global_analyzer import GlobalAnalyzer
from src_extension.analysis.trigger_objects import InformationTrigger, Scope, Severity
from src_extension.execution.communication_executor import CommunicationExecutor
from src_extension.execution.failsafe_modes import FailSafeMode
from src_extension.execution.mode_manager import ModeManager
from src_extension.execution.safety_checker import SafetyChecker
from src_extension.knowledge.communication_model import CommunicationModel
from src_extension.knowledge.fire_runtime_model import FireRuntimeModel
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture
from src_extension.knowledge.uav_resource_model import UAVResourceModel
from src_extension.planning.fail_safe_planner import FailSafePlanner
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
        monkeypatch.setattr(cfv, "FAILSAFE_REAL_ALARMS", value, raising=False)
    return set_


# --------------------------------------------------------------------------- the switch

def test_shipped_on() -> None:
    assert cfv.FAILSAFE_REAL_ALARMS == 1
    assert agents.failsafe_real_alarms() is True
    assert agents.COLLISION_RISK_RADIUS == 2 and agents.DRIFT_WINDOW_STEPS == 5


@pytest.mark.parametrize("value, expected", [(0, False), (0.0, False), (False, False), ("0", False),
                                             (1, True), (0.5, True), ("off", True), (None, True)])
def test_off_only_on_an_exact_integral_zero(switch, value, expected) -> None:
    switch(value)
    assert agents.failsafe_real_alarms() is expected


# --------------------------------------------------------------------------- 1a collision

def _model_with_uavs(cells, docked=()):
    model = WildFireModel()
    uavs = sorted((a for a in model.schedule.agents if type(a) is agents.UAV), key=lambda a: a.unique_id)
    placed = []
    for uav, cell in zip(uavs, cells):
        model.grid.move_agent(uav, cell)
        uav.rtb_docked = cell in docked
        placed.append(uav)
    return model, placed


def _congestion(model, uav) -> float:
    model._refresh_local_path_context_models(1.0)
    path = model.local_path_context_models[str(uav.unique_id)]
    return float(path.local_collision_risk_estimates.get("congestion", 0.0))


def test_collision_counts_only_airborne_uavs_within_two(switch) -> None:
    switch(1)
    model, u = _model_with_uavs([(20, 20), (22, 20), (40, 40)])   # the default fleet: 3 UAVs
    assert _congestion(model, u[0]) == pytest.approx(1 / 3)   # (22,20) at distance 2
    assert _congestion(model, u[2]) == 0.0                    # alone
    model, u = _model_with_uavs([(20, 20), (20, 23), (40, 40)])
    assert _congestion(model, u[0]) == 0.0                    # distance 3: no single-step conflict


def test_collision_ignores_docked_uavs(switch) -> None:
    switch(1)
    model, u = _model_with_uavs([(20, 20), (21, 20), (40, 40)], docked={(21, 20)})
    assert _congestion(model, u[0]) == 0.0       # the neighbour is docked
    assert _congestion(model, u[1]) == 0.0       # a docked UAV itself raises nothing


def test_collision_off_is_the_whole_fleet(switch) -> None:
    switch(0)
    model, u = _model_with_uavs([(5, 5), (40, 40), (20, 20)])
    model._refresh_local_path_context_models(1.0)
    model.local_observation_models[str(u[0].unique_id)].nearby_uavs = {"a", "b", "c"}
    assert _congestion(model, u[0]) == 1.0       # min(1, 3/3): every UAV at any distance


# --------------------------------------------------------------------------- 1b drift

def _drift(model: UAVResourceModel, readings):
    for t, r in enumerate(readings, start=1):
        model.update_drift("u", r, timestamp=float(t))
    st = model.by_uav_id["u"]
    return st.drift_level, st.local_risk_status


def test_one_refusal_never_fires(switch) -> None:
    switch(1)
    level, status = _drift(UAVResourceModel(), [0, 0, 1, 0, 0])
    assert level == pytest.approx(0.2) and status == "low_drift"


def test_two_of_five_is_moderate_four_of_five_is_high(switch) -> None:
    switch(1)
    assert _drift(UAVResourceModel(), [0, 1, 0, 1, 0]) == (pytest.approx(0.4), "moderate_drift")
    assert _drift(UAVResourceModel(), [1, 1, 0, 1, 1]) == (pytest.approx(0.8), "high_drift")


def test_no_latch_the_status_recovers(switch) -> None:
    switch(1)
    level, status = _drift(UAVResourceModel(), [1, 1, 1, 1, 1, 0, 0, 0, 0, 0])
    assert level == 0.0 and status == "low_drift"


def test_same_timestamp_replaces_the_sample(switch) -> None:
    switch(1)
    m = UAVResourceModel()
    m.update_drift("u", 1.0, timestamp=3.0)
    m.update_drift("u", 1.0, timestamp=3.0)
    assert m.by_uav_id["u"].drift_level == pytest.approx(0.2)


def test_drift_off_keeps_the_old_latch(switch) -> None:
    switch(0)
    level, status = _drift(UAVResourceModel(), [1, 0, 0, 0, 0, 0])
    assert level == 0.0 and status == "high_drift"


@pytest.mark.parametrize("value, expected", [(1, 0.0), (0, 1.0)])
def test_a_docked_uav_is_not_drifting(switch, value, expected) -> None:
    switch(value)
    model = WildFireModel()
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    uav.rtb_docked = True
    uav.rtb_active = True
    uav.battery_level = 50.0          # below the release level: stays docked
    uav.advance()
    assert uav.execution_action == "rtb_docked_hold"
    assert uav._monitor_prev_drift_error == expected


# --------------------------------------------------------------------------- 1c link

def test_no_critical_traffic_is_no_evidence(switch) -> None:
    switch(1)
    cm = CommunicationModel()
    cm.update_message_result("uav_1_telemetry", "delivered", 1.0, critical=False)
    assert cm.state.critical_link_reliability is None
    switch(0)
    cm.update_message_result("uav_2_telemetry", "delivered", 2.0, critical=False)
    assert cm.state.critical_link_reliability == 0.0


def test_delivery_confidence_from_outcomes() -> None:
    cm = CommunicationModel()
    assert cm.delivery_confidence_from_outcomes() is None
    cm.update_message_result("a", "delivered", 1.0)
    cm.update_message_result("b", "failed", 1.0)
    assert cm.delivery_confidence_from_outcomes() == pytest.approx(0.5)


@pytest.mark.parametrize("value, expected", [(1, "success"), (0, "failure")])
def test_an_action_name_is_not_a_delivery_outcome(switch, value, expected) -> None:
    switch(value)
    assert CommunicationExecutor._delivery_status("prioritize_failsafe_messages") == expected


# --------------------------------------------------------------------------- 1d search

def _belief(p_cells):
    fr = FireRuntimeModel()
    fr.initialize_grid(10, 10)
    for _ in range(2):
        for c in p_cells:
            fr.update_fire_observation(c, timestamp=1.0, source="t", confidence=1.0, probability=1.0)
    return fr


def _search(result):
    return [t for t in result.trigger_list if t.trigger_type == "SEARCH_MODE_REQUIRED"]


def test_fleet_fire_lost_fires_when_believed_and_unseen(switch) -> None:
    switch(1)
    fr = _belief([(3, 3)])
    lost = GlobalAnalyzer().analyze(SharedOperationalPicture(), {"fleet_fire_view": {"visible_fire_cells": 0}},
                                    {"fire_runtime_model": fr}, timestamp=2.0)
    hits = _search(lost)
    assert len(hits) == 1 and hits[0].scope == Scope.GLOBAL and hits[0].confidence >= 0.6
    seen = GlobalAnalyzer().analyze(SharedOperationalPicture(), {"fleet_fire_view": {"visible_fire_cells": 4}},
                                    {"fire_runtime_model": fr}, timestamp=2.0)
    assert not _search(seen)


def test_fleet_fire_lost_needs_a_believed_fire_and_the_switch(switch) -> None:
    switch(1)
    view = {"fleet_fire_view": {"visible_fire_cells": 0}}
    nothing = GlobalAnalyzer().analyze(SharedOperationalPicture(), view, {"fire_runtime_model": _belief([])},
                                       timestamp=2.0)
    assert not _search(nothing)
    switch(0)
    off = GlobalAnalyzer().analyze(SharedOperationalPicture(), view, {"fire_runtime_model": _belief([(3, 3)])},
                                   timestamp=2.0)
    assert not _search(off)


def _search_trigger(scope):
    return InformationTrigger(trigger_type="SEARCH_MODE_REQUIRED", severity=Severity.MEDIUM, confidence=0.75,
                              scope=scope, affected_entities=("u",), timestamp=1.0,
                              recommended_planner="local_uav_path_planner",
                              explanation_context="SEARCH_MODE_REQUIRED: test")


def test_a_local_search_hint_is_not_a_fleet_reason(switch) -> None:
    checker = SafetyChecker()
    local = {"all_triggers": (_search_trigger(Scope.LOCAL),)}
    fleet = {"all_triggers": (_search_trigger(Scope.GLOBAL),)}
    switch(1)
    assert checker.extract_fail_safe_reasons(analysis_snapshot=local) == ()
    assert checker.extract_fail_safe_reasons(analysis_snapshot=fleet) == ("search_mode_required",)
    switch(0)
    assert checker.extract_fail_safe_reasons(analysis_snapshot=local) == ("search_mode_required",)


def test_mode_is_normal_on_a_local_hint_alone(switch) -> None:
    switch(1)
    state = ModeManager(SafetyChecker()).update(
        analysis_snapshot={"all_triggers": (_search_trigger(Scope.LOCAL),)}, timestamp=1.0)
    assert state.mode == FailSafeMode.NORMAL


# --------------------------------------------------------------------------- 1d' the planning echo

def test_no_reason_no_action(switch) -> None:
    switch(1)
    snapshot = {"all_triggers": (_search_trigger(Scope.LOCAL),)}
    decision = FailSafePlanner().plan(1, analysis_snapshot=snapshot,
                                      fail_safe_space=FailSafeAdaptationSpace(options=[]), timestamp=1.0)
    assert decision is not None
    assert decision.fail_safe_action == "" and decision.search_mode_active is False
    assert decision.mission_mode == ""
    # and the mode manager reads nothing back from it
    state = ModeManager(SafetyChecker()).update(analysis_snapshot=snapshot, planning_result=decision,
                                                timestamp=1.0)
    assert state.mode == FailSafeMode.NORMAL


def test_a_real_reason_still_plans(switch) -> None:
    switch(1)
    snapshot = {"all_triggers": (_search_trigger(Scope.GLOBAL),)}
    decision = FailSafePlanner().plan(1, analysis_snapshot=snapshot,
                                      fail_safe_space=FailSafeAdaptationSpace(options=[]), timestamp=1.0)
    assert decision.search_mode_active is True
    assert decision.mission_mode == "information_recovery"
