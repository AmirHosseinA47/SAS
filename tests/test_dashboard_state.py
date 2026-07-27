"""Dashboard state, alerts, timeline, and operator override tests."""

from __future__ import annotations

import copy
import json
import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.dashboard.alert_manager import (
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    AlertManager,
)
from src_extension.dashboard.dashboard_state_builder import DashboardStateBuilder
from src_extension.dashboard.display_utils import display_wind_vector
from src_extension.dashboard.explanation_engine import ExplanationEngine
from src_extension.dashboard.operator_override import (
    OperatorOverrideCommand,
    OperatorOverrideInterface,
)
from src_extension.dashboard.timeline_builder import MissionTimelineBuilder
from wildfire_model import WildFireModel

_DISPLAY_VECTORS = {
    "north": [0.0, 1.0],
    "south": [0.0, -1.0],
    "east": [1.0, 0.0],
    "west": [-1.0, 0.0],
}


def _scenario_a_model(*, batch_size: int = 50, seed: int = 42) -> WildFireModel:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv,
        wf,
        NUM_AGENTS=2,
        NUM_VICTIMS=3,
        NUM_FIREFIGHTERS=3,
        FIRE_SPREAD_MULTIPLIER=0.75,
        BATCH_SIZE=batch_size,
        FIXED_WIND=True,
        WIND_DIRECTION="east",
    )
    model = WildFireModel()
    model.debug_log = False
    return model


def _snapshot_model(model: WildFireModel) -> dict:
    return {
        "step": model.evaluation_timesteps_counter,
        "victim_statuses": {
            vid: str(getattr(st, "status", ""))
            for vid, st in model.managed_victims.items()
        },
        "uav_positions": {
            str(a.unique_id): tuple(a.pos)
            for a in model.schedule.agents
            if type(a) is agents.UAV and a.pos is not None
        },
        "ff_dead": {
            fid: bool(getattr(ff, "dead", False))
            for fid, ff in model.firefighter_marker_agents.items()
        },
    }


def test_dashboard_state_builder_returns_serializable_dict() -> None:
    model = _scenario_a_model()
    state = DashboardStateBuilder().build(model)
    parsed = json.loads(json.dumps(state))
    assert isinstance(parsed, dict)
    assert parsed["step"] == 0


def test_dashboard_state_contains_mission_uav_victim_firefighter_views() -> None:
    model = _scenario_a_model()
    state = DashboardStateBuilder().build(model)
    assert len(state["uav_status_view"]) >= 1
    assert len(state["victim_view"]) == 3
    assert len(state["firefighter_view"]) == 3
    assert "unresolved_victim_count" in state["mission_status"]


def test_dashboard_state_contains_fire_wind_and_burnt_summary() -> None:
    model = _scenario_a_model()
    for _ in range(5):
        model.step()
    fire = model.get_dashboard_state()["fire_view"]
    assert fire["wind_direction"] == "east"
    assert fire["wind_vector"] == _DISPLAY_VECTORS["east"]


def test_dashboard_wind_vector_matches_direction() -> None:
    for direction, expected in _DISPLAY_VECTORS.items():
        assert list(display_wind_vector(direction)) == expected
        assert list(display_wind_vector(direction.upper())) == expected


def test_dashboard_wind_fix_does_not_change_trajectory() -> None:
    def run_with_dashboard(*, build_each_step: bool) -> dict:
        model = _scenario_a_model(batch_size=30)
        builder = DashboardStateBuilder()
        for _ in range(10):
            if build_each_step:
                builder.build(model)
            model.step()
        return _snapshot_model(model)

    assert run_with_dashboard(build_each_step=False) == run_with_dashboard(
        build_each_step=True
    )


def test_alert_manager_generates_victim_and_firefighter_alerts() -> None:
    model = _scenario_a_model()
    model.managed_victims["victim_0"].status = "dead"
    model.managed_victims["victim_0"].dead = True
    model.firefighter_marker_agents["ff_unit_0"].dead = True

    alerts = AlertManager().generate_alerts(model)
    types = {a.alert_type for a in alerts}
    assert "victim_dead" in types
    assert "firefighter_dead" in types


def test_alert_manager_assigns_correct_severity() -> None:
    model = _scenario_a_model()
    model.managed_victims["victim_0"].dead = True
    model.managed_victims["victim_0"].status = "dead"
    model.managed_victims["victim_1"].confirmed = True
    model.managed_victims["victim_1"].status = "confirmed"

    alerts = AlertManager().generate_alerts(model)
    by_type = {a.alert_type: a.severity for a in alerts}
    assert by_type["victim_dead"] == SEVERITY_CRITICAL
    assert by_type["victim_detected"] == SEVERITY_INFO
    assert by_type["unresolved_victims"] == SEVERITY_WARNING


def test_alert_manager_deduplicates_alerts() -> None:
    model = _scenario_a_model()
    model.managed_victims["victim_0"].dead = True
    model.managed_victims["victim_0"].status = "dead"
    manager = AlertManager()
    first = manager.generate_alerts(model)
    second = manager.generate_alerts(model)
    keys = [(a.step, a.alert_type, a.target_id) for a in second]
    assert len(keys) == len(set(keys))
    victim_dead = [a for a in second if a.alert_type == "victim_dead"]
    assert len(victim_dead) == 1
    assert len(second) == len(first)


def test_alert_manager_generates_critical_victim_and_firefighter_alerts() -> None:
    model = _scenario_a_model()
    model.managed_victims["victim_0"].status = "dead"
    model.firefighter_marker_agents["ff_unit_0"].dead = True
    model._rescue_event_log.append(
        {
            "step": 5,
            "victim_id": "victim_2",
            "firefighter_id": "ff_unit_1",
            "event_type": "rescue_failed",
            "reason": "no path",
            "metadata": {},
        }
    )
    alerts = AlertManager().generate_alerts(model)
    critical = [a for a in alerts if a.severity == SEVERITY_CRITICAL]
    types = {a.alert_type for a in critical}
    assert "victim_dead" in types
    assert "firefighter_dead" in types
    assert "rescue_failed" in types


def test_alert_manager_is_read_only() -> None:
    model = _scenario_a_model()
    for _ in range(2):
        model.step()
    before = _snapshot_model(model)
    log_len = len(model._rescue_event_log)
    AlertManager().generate_alerts(model)
    assert _snapshot_model(model) == before
    assert len(model._rescue_event_log) == log_len


def test_timeline_contains_rescue_and_casualty_events() -> None:
    model = _scenario_a_model()
    model._rescue_event_log.extend(
        [
            {
                "step": 3,
                "victim_id": "victim_0",
                "firefighter_id": "ff_unit_0",
                "event_type": "dispatch_initial",
                "reason": "initial",
                "metadata": {},
            },
            {
                "step": 10,
                "victim_id": "victim_0",
                "firefighter_id": "ff_unit_0",
                "event_type": "rescue_complete",
                "reason": "exited with victim",
                "metadata": {},
            },
            {
                "step": 12,
                "victim_id": "victim_1",
                "firefighter_id": "ff_unit_1",
                "event_type": "casualty",
                "reason": "firefighter_fire_casualty",
                "metadata": {},
            },
        ]
    )
    timeline = MissionTimelineBuilder().build(model)
    types = {e.event_type for e in timeline}
    assert "dispatch_initial" in types
    assert "rescue_complete" in types
    assert "firefighter_dead" in types
    assert all(e.source_module for e in timeline)


def test_timeline_is_ordered_by_step() -> None:
    model = _scenario_a_model()
    model._rescue_event_log.extend(
        [
            {"step": 20, "victim_id": "victim_1", "firefighter_id": "", "event_type": "victim_dead", "reason": "fire", "metadata": {}},
            {"step": 5, "victim_id": "victim_0", "firefighter_id": "ff_unit_0", "event_type": "dispatch_initial", "reason": "initial", "metadata": {}},
            {"step": 15, "victim_id": "victim_0", "firefighter_id": "ff_unit_0", "event_type": "route_blocked", "reason": "blocked", "metadata": {}},
        ]
    )
    timeline = MissionTimelineBuilder().build(model)
    steps = [e.step for e in timeline]
    assert steps == sorted(steps)


def test_dashboard_state_contains_alert_counts() -> None:
    model = _scenario_a_model()
    model.managed_victims["victim_0"].confirmed = True
    model.managed_victims["victim_0"].status = "confirmed"
    state = DashboardStateBuilder().build(model)
    assert "recent_alert_count" in state
    assert "critical_alert_count" in state
    assert "warning_alert_count" in state
    assert "info_alert_count" in state
    assert "unresolved_alert_count" in state
    assert state["recent_alert_count"] == len(state["alert_list"])
    assert (
        state["critical_alert_count"]
        + state["warning_alert_count"]
        + state["info_alert_count"]
        == state["recent_alert_count"]
    )


def test_explanation_engine_collects_uav_and_rescue_explanations() -> None:
    model = _scenario_a_model()
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    uav.last_explanation = {
        "decision": "victim_search_wind_aware",
        "source": "executor",
        "wind_direction": "east",
        "target": [12.0, 15.0],
        "reason": "prioritized safe downwind area",
    }
    model._rescue_event_log.append(
        {
            "step": 1,
            "victim_id": "victim_1",
            "firefighter_id": "ff_unit_1",
            "event_type": "rescue_complete",
            "reason": "firefighter exited with victim",
            "metadata": {},
        }
    )
    explanations = ExplanationEngine().collect_explanations(model)
    assert "victim_search_wind_aware" in {e.decision_type for e in explanations}
    assert "rescue_complete" in {e.decision_type for e in explanations}


def test_dashboard_state_builder_is_read_only() -> None:
    model = _scenario_a_model()
    for _ in range(3):
        model.step()
    before = _snapshot_model(model)
    log_len = len(model._rescue_event_log)
    DashboardStateBuilder().build(model)
    assert _snapshot_model(model) == before
    assert len(model._rescue_event_log) == log_len


def test_operator_override_stub_does_not_mutate_model() -> None:
    model = _scenario_a_model()
    before = _snapshot_model(model)
    result = OperatorOverrideInterface().submit(
        OperatorOverrideCommand(
            override_id="ov-1",
            kind="assign_rescue",
            payload={"victim_id": "victim_0", "firefighter_id": "ff_unit_0"},
            step=0,
            reason="operator test",
        )
    )
    assert result["accepted"] is True
    assert result["executed"] is False
    assert _snapshot_model(model) == before


def test_wildfire_model_get_dashboard_state_after_50_steps() -> None:
    model = _scenario_a_model(batch_size=50)
    assert model.get_dashboard_state()["step"] == 0
    for _ in range(50):
        model.step()
    state50 = model.get_dashboard_state()
    assert state50["step"] == 50
    json.dumps(state50)
    expected_keys = {
        "step",
        "mission_status",
        "uav_status_view",
        "victim_view",
        "firefighter_view",
        "fire_view",
        "rescue_view",
        "communication_view",
        "fail_safe_view",
        "alert_list",
        "explanation_list",
        "timeline",
        "known_limitations",
        "recent_alert_count",
        "critical_alert_count",
        "warning_alert_count",
        "info_alert_count",
        "unresolved_alert_count",
        "structured_explanations",
        "option_comparison_count",
        "explanation_count",
    }
    assert expected_keys <= set(state50.keys())
