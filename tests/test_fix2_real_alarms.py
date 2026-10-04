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
from src_extension.adaptation.adaptation_option_objects import FailSafeAdaptationOption
from src_extension.adaptation.adaptation_option_objects import Scope as OptionScope
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
from src_extension.monitoring.monitoring_buffer import MonitoringBuffer
from src_extension.monitoring.monitoring_interfaces import LocalObservation
from src_extension.planning.fail_safe_planner import FailSafePlanner
from src_extension.planning.utility_evaluation import UtilityEvaluation
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
    # the default fleet, pinned: other test modules call apply_scenario_config (e.g. NUM_AGENTS=2)
    # and leave it set; the autouse fixture restores whatever it found, so pin what these tests need
    cfv.NUM_AGENTS = wf.NUM_AGENTS = 3
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

def _search_space() -> FailSafeAdaptationSpace:
    # the search option of tests/test_rescue_failsafe_planners.py::
    # test_fail_safe_planner_marks_search_mode_active_for_search_decision - the one a reasonless
    # planner SELECTS (fail_safe_action 'failsafe_search_patrol', search_mode_active True). An empty
    # space cannot tell the no-op from the old planner: both return an empty decision (review D1).
    search = FailSafeAdaptationOption(
        option_id="search", option_type="failsafe_search_patrol", target_entity="uav-1",
        parameters={"mission_value": 0.5, "stability_bonus": 0.5, "energy_failure_risk": 0.2,
                    "support_loss": 0.1, "search_mode": True, "recovery_value": 0.8},
        expected_effect="test", cost_estimate=0.1, risk_estimate=0.1, confidence=1.0,
        scope=OptionScope.system, timestamp=0.0, originating_trigger="t", explanation_hint="")
    return FailSafeAdaptationSpace(options=[search])


def _plan_local_hint_only(triggers=None):
    snapshot = {"all_triggers": (_search_trigger(Scope.LOCAL),) if triggers is None else triggers}
    planner = FailSafePlanner(utility_evaluator=UtilityEvaluation(default_mode="information_recovery_mode"))
    return snapshot, planner.plan(1, analysis_snapshot=snapshot, fail_safe_space=_search_space(),
                                  timestamp=1.0)


def test_no_reason_no_action(switch) -> None:
    switch(1)
    snapshot, decision = _plan_local_hint_only()
    assert decision is not None
    assert decision.fail_safe_action == "" and decision.search_mode_active is False
    assert decision.mission_mode == ""
    # and the mode manager reads nothing back from it
    state = ModeManager(SafetyChecker()).update(analysis_snapshot=snapshot, planning_result=decision,
                                                timestamp=1.0)
    assert state.mode == FailSafeMode.NORMAL


@pytest.mark.parametrize("value, action, search", [(1, "", False), (0, "failsafe_search_patrol", True)])
def test_no_trigger_at_all(switch, value, action, search) -> None:
    # the planning echo itself: with NO reason (no trigger at all) the old planner still SELECTS
    # from the space - the search patrol, search_mode_active True - and the mode manager reads that
    # back as information_recovery. On: the no-op, and the mode stays normal.
    switch(value)
    snapshot, decision = _plan_local_hint_only(triggers=())
    assert decision.fail_safe_action == action
    assert decision.search_mode_active is search
    state = ModeManager(SafetyChecker()).update(analysis_snapshot=snapshot, planning_result=decision,
                                                timestamp=1.0)
    assert state.mode == (FailSafeMode.INFORMATION_RECOVERY if search else FailSafeMode.NORMAL)


def test_a_real_reason_still_plans(switch) -> None:
    switch(1)
    snapshot = {"all_triggers": (_search_trigger(Scope.GLOBAL),)}
    decision = FailSafePlanner().plan(1, analysis_snapshot=snapshot,
                                      fail_safe_space=FailSafeAdaptationSpace(options=[]), timestamp=1.0)
    assert decision.search_mode_active is True
    assert decision.mission_mode == "information_recovery"


# --------------------------------------------------------------------------- the model wiring (review R1)

def _fleet_fire_lost_triggers(model):
    return [t for t in model.latest_analysis_snapshot.all_triggers
            if t.trigger_type == "SEARCH_MODE_REQUIRED" and t.scope == Scope.GLOBAL
            and "FLEET_FIRE_LOST" in str(t.explanation_context)]


def _model_believing_an_unseen_fire():
    model = WildFireModel()
    for _ in range(2):
        model.fire_runtime_model.update_fire_observation((3, 3), timestamp=1.0, source="t",
                                                         confidence=1.0, probability=1.0)
    for lom in model.local_observation_models.values():
        lom.visible_fire_cells = set()
    return model


def test_the_model_raises_fleet_fire_lost(switch) -> None:
    # _run_analysis must hand the analyzer the fleet's view (snap_dict['fleet_fire_view']);
    # without it FLEET_FIRE_LOST can never fire in a run and no unit test would notice
    switch(1)
    model = _model_believing_an_unseen_fire()
    model._run_analysis(1.0, None)
    assert len(_fleet_fire_lost_triggers(model)) == 1
    next(iter(model.local_observation_models.values())).visible_fire_cells = {(3, 3)}
    model._run_analysis(2.0, None)
    assert _fleet_fire_lost_triggers(model) == []           # one UAV sees fire: not lost
    switch(0)
    model = _model_believing_an_unseen_fire()
    model._run_analysis(1.0, None)
    assert _fleet_fire_lost_triggers(model) == []


def _observation(uid, drift):
    return LocalObservation(
        uav_id=uid, timestamp=1.0, visible_fire_cells=[], visible_smoke_cells=[],
        visible_victim_candidates=[], current_position=(5, 5), intended_move=(6, 5), actual_move=(5, 5),
        drift_error=drift, battery_level=90.0, battery_status="normal", communication_status="",
        nearby_uavs=[], task_context={}, negative_observations=[], raw_information_gain=0.0,
        normalized_information_gain=0.0, local_uncertainty_patch=[], observation_confidence=1.0,
        belief_confirmation_flags=[])


@pytest.mark.parametrize("docked, level, status", [(True, 0.0, "low_drift"), (False, 0.6, "moderate_drift")])
def test_docking_restarts_the_drift_window(switch, docked, level, status) -> None:
    # Part 3 (check P3-3 v): three refusals on the approach to a berth, then the UAV docks. Without
    # the restart its window still held them for the next steps, so DRIFT_TOO_HIGH named a docked
    # UAV and put the fleet in safety_first (mf2ALL at 98ded8c, A/south, steps 280-282).
    switch(1)
    model = WildFireModel()
    uid = sorted(model.local_observation_models)[0]
    for t in (1.0, 2.0, 3.0):
        model.uav_resource_model.update_drift(uid, 1.0, timestamp=t)
    obs = _observation(uid, 0.0)
    obs.task_context = {"role": None, "assigned_task": None, "docked": docked}
    buf = MonitoringBuffer()
    buf.add_local_observation(uid, obs)
    model._apply_uav_resource_updates(buf, 4.0)
    st = model.uav_resource_model.by_uav_id[uid]
    assert st.drift_level == pytest.approx(level) and st.local_risk_status == status


def test_the_monitor_reports_the_dock_state_only_when_on(switch, monkeypatch) -> None:
    """bayesprep item 5 (review R2-F1): the dock state is also reported whenever UAV_DOCKED_NOT_OBSTACLE acts (its
    global collision guard reads it); with both switches off it is not reported, as in fix2."""
    model = WildFireModel()
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    uav.rtb_docked = True
    switch(1)
    assert uav.local_monitor.collect_observation(uav, 1.0).task_context.get("docked") is True
    switch(0)
    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", 0, raising=False)
    assert "docked" not in uav.local_monitor.collect_observation(uav, 2.0).task_context
    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", 1, raising=False)
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 1, raising=False)
    assert uav.local_monitor.collect_observation(uav, 3.0).task_context.get("docked") is True


@pytest.mark.parametrize("value", [1, 0])
def test_a_refused_move_is_not_a_lost_message(switch, value) -> None:
    # every UAV refused (drift 1.0) for 50 steps, with the model's 3%-per-step delivery decay:
    # on, telemetry stays delivered and delivery confidence never nears the 0.25 alarm; off, the
    # old derivation marks telemetry delayed and takes delivery confidence from the drift
    switch(value)
    model = WildFireModel()
    buf = MonitoringBuffer()
    for uid in model.local_observation_models:
        buf.add_local_observation(uid, _observation(uid, 1.0))
    cm = model.communication_model
    lowest = 1.0
    for t in range(1, 51):
        cm.apply_time_decay(float(t))
        model._apply_communication_updates(buf, float(t))
        lowest = min(lowest, float(cm.state.delivery_confidence or 0.0))
    status = {cm.state.last_delivery_status.get("uav_%s_telemetry" % uid) for uid in model.local_observation_models}
    if value:
        assert status == {"delivered"}
        assert lowest >= 0.25
    else:
        assert status == {"delayed"}
        assert lowest < 0.25
