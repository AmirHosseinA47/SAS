"""Decision objects and planner selection helpers."""

from dataclasses import fields, is_dataclass

import pytest

from src_extension.adaptation.adaptation_option_objects import LocalAdaptationOption, MissionAdaptationOption, Scope
from src_extension.planning.decision_objects import (
    FailSafeDecision,
    MissionDecision,
    PathDecision,
    RescueDecision,
)
from src_extension.planning.planner_selection import find_maintain_option, score_and_select_best
from src_extension.planning.utility_evaluation import UtilityEvaluation


def _field_names(cls: type) -> set[str]:
    return {f.name for f in fields(cls)}


def test_mission_decision_supports_new_fields() -> None:
    decision = MissionDecision(
        decision_id="m-1",
        uav_assignments={"uav-1": "scout"},
        task_assignments={"sector": "north"},
        mission_mode="search",
        relay_assignments={"uav-2": "relay"},
        recall_orders=("return_to_base",),
        confidence_score=0.8,
        uncertainty_context={"uncertainty_level": 0.4},
        comparison_summary={"summary": "ok"},
        explanation="mission explanation",
        selected_option_id="global-opt-1",
    )
    assert is_dataclass(decision)
    required = {
        "decision_id",
        "uav_assignments",
        "task_assignments",
        "mission_mode",
        "relay_assignments",
        "recall_orders",
        "confidence_score",
        "uncertainty_context",
        "comparison_summary",
        "explanation",
        "selected_option_id",
        "notes",
    }
    assert required == _field_names(MissionDecision)
    assert decision.mission_mode == "search"
    assert decision.selected_option_id == "global-opt-1"


def test_path_decision_supports_new_fields() -> None:
    decision = PathDecision(
        decision_id="p-uav-1-1",
        uav_id="uav-1",
        selected_option_id="path-opt-1",
        next_action="advance",
        path_segment=((1.0, 2.0), (3.0, 4.0)),
        waypoints_by_uav={"uav-1": ((5.0, 6.0),)},
        confidence_score=0.7,
        uncertainty_context={"knowledge_confidence": 0.6},
        comparison_summary={"summary": "path"},
        explanation="path explanation",
        escalation_request={"reason": "high_risk"},
    )
    assert is_dataclass(decision)
    required = {
        "decision_id",
        "uav_id",
        "selected_option_id",
        "next_action",
        "path_segment",
        "waypoints_by_uav",
        "confidence_score",
        "uncertainty_context",
        "comparison_summary",
        "explanation",
        "escalation_request",
    }
    assert required == _field_names(PathDecision)
    assert decision.next_action == "advance"
    assert decision.escalation_request == {"reason": "high_risk"}


def test_rescue_decision_supports_new_fields() -> None:
    decision = RescueDecision(
        decision_id="r-1",
        selected_option_id="rescue-opt-1",
        rescue_action="confirm_rescue",
        victim_id="victim_0",
        firefighter_id="ff_1",
        route_choice="safe_route",
        payload={"dispatch": True},
        confidence_score=0.65,
        uncertainty_context={"victim_uncertainty": 0.5},
        comparison_summary={"summary": "rescue"},
        explanation="rescue explanation",
    )
    assert is_dataclass(decision)
    required = {
        "decision_id",
        "selected_option_id",
        "rescue_action",
        "victim_id",
        "firefighter_id",
        "route_choice",
        "payload",
        "confidence_score",
        "uncertainty_context",
        "comparison_summary",
        "explanation",
    }
    assert required == _field_names(RescueDecision)
    assert decision.rescue_action == "confirm_rescue"


def test_fail_safe_decision_supports_new_fields() -> None:
    decision = FailSafeDecision(
        decision_id="fs-1",
        selected_option_id="fs-opt-1",
        fail_safe_action="search_mode",
        search_mode_active=True,
        target_region="sector-a",
        mission_mode="search",
        actions=({"search_mode": True},),
        confidence_score=0.55,
        uncertainty_context={"information_collapse": 0.2},
        comparison_summary={"summary": "failsafe"},
        explanation="failsafe explanation",
    )
    assert is_dataclass(decision)
    required = {
        "decision_id",
        "selected_option_id",
        "fail_safe_action",
        "search_mode_active",
        "target_region",
        "mission_mode",
        "actions",
        "confidence_score",
        "uncertainty_context",
        "comparison_summary",
        "explanation",
    }
    assert required == _field_names(FailSafeDecision)
    assert decision.search_mode_active is True


def _local_path_option(option_id: str, **params: float) -> LocalAdaptationOption:
    return LocalAdaptationOption(
        option_id=option_id,
        option_type="path_adjust",
        target_entity="uav-1",
        parameters=dict(params),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=1.0,
        scope=Scope.local,
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def test_score_and_select_best_returns_highest_utility_option() -> None:
    high = _local_path_option(
        "high",
        expected_info_gain=0.9,
        task_support=0.8,
        overlap_penalty=0.05,
        collision_risk=0.05,
        smoke_penalty=0.05,
        battery_cost=0.05,
        drift_penalty=0.05,
        stability_bonus=0.9,
        belief_gain=0.5,
        recovery_value=0.5,
    )
    low = _local_path_option(
        "low",
        expected_info_gain=0.05,
        task_support=0.05,
        overlap_penalty=0.9,
        collision_risk=0.9,
        smoke_penalty=0.9,
        battery_cost=0.9,
        drift_penalty=0.9,
        stability_bonus=0.1,
        belief_gain=0.0,
        recovery_value=0.0,
    )
    evaluator = UtilityEvaluation(default_mode="safety_first_mode")
    best, scored, summary = score_and_select_best((low, high), evaluator)

    assert best is high
    assert len(scored) == 2
    assert scored[0].evaluation.option_id == "high"
    assert scored[1].evaluation.option_id == "low"
    assert isinstance(summary, str)
    assert "high" in summary


def _mission_option(option_id: str, option_type: str, **params: object) -> MissionAdaptationOption:
    return MissionAdaptationOption(
        option_id=option_id,
        option_type=option_type,
        target_entity="mission",
        parameters=dict(params),
        expected_effect="test",
        cost_estimate=0.0,
        risk_estimate=0.0,
        confidence=1.0,
        scope=Scope["global"],
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def test_find_maintain_option_returns_stability_option_when_present() -> None:
    active = _mission_option(
        "active",
        "role_reassign",
        fire_contribution=0.8,
        victim_contribution=0.8,
        communication_contribution=0.8,
    )
    maintain = _mission_option("maintain", "stability_control", do_nothing=True)
    found = find_maintain_option((active, maintain))

    assert found is maintain
    assert getattr(found, "option_id", None) == "maintain"
