"""Rescue and fail-safe planner decision logic."""

from types import SimpleNamespace

from src_extension.adaptation.adaptation_option_objects import FailSafeAdaptationOption, RescueAdaptationOption, Scope
from src_extension.adaptation.adaptation_results import FailSafeAdaptationSpace, RescueAdaptationSpace
from src_extension.planning.fail_safe_planner import FailSafePlanner
from src_extension.planning.rescue_planner import RescuePlanner
from src_extension.planning.utility_evaluation import UtilityEvaluation


def _rescue_option(
    option_id: str,
    option_type: str,
    parameters: dict,
    *,
    confidence: float = 0.5,
) -> RescueAdaptationOption:
    return RescueAdaptationOption(
        option_id=option_id,
        option_type=option_type,
        target_entity="victim_0",
        parameters=dict(parameters),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=confidence,
        scope=Scope.rescue,
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def _rescue_baseline() -> dict[str, float]:
    return {
        "victim_priority": 0.75,
        "support_quality": 0.65,
        "expected_delay": 0.25,
        "route_risk": 0.35,
        "victim_uncertainty": 0.88,
        "communication_risk": 0.22,
    }


def test_rescue_planner_prefers_confirmation_when_victim_uncertainty_high() -> None:
    analysis = SimpleNamespace(
        uncertainty_level=0.93,
        victim_uncertainty=0.88,
        victim_confidence=0.2,
    )
    dispatch = _rescue_option(
        "dispatch",
        "rescue_dispatch_step",
        {**_rescue_baseline(), "victim_priority": 0.98, "support_quality": 0.95},
        confidence=0.9,
    )
    confirm = _rescue_option(
        "confirm",
        "rescue_confirm_step",
        {**_rescue_baseline(), "victim_priority": 0.55, "support_quality": 0.5},
        confidence=0.15,
    )
    space = RescueAdaptationSpace(options=[dispatch, confirm])
    planner = RescuePlanner(utility_evaluator=UtilityEvaluation(default_mode="victim_support_mode"))

    decision = planner.plan(1, rescue_space=space, analysis_snapshot=analysis, context=analysis)

    assert decision is not None
    assert decision.selected_option_id == "confirm"
    assert "confirmation-first policy applied" in decision.explanation


def test_rescue_planner_maintain_current_rescue_state_fallback() -> None:
    maintain = _rescue_option(
        "maintain",
        "maintain_current_rescue",
        {**_rescue_baseline(), "maintain_current_rescue": True},
    )
    infeasible_dispatch = _rescue_option(
        "bad_dispatch",
        "rescue_dispatch_step",
        {**_rescue_baseline(), "hard_collision_violation": True},
    )
    infeasible_confirm = _rescue_option(
        "bad_confirm",
        "rescue_confirm_step",
        {**_rescue_baseline(), "route_feasible": False},
    )
    space = RescueAdaptationSpace(options=[infeasible_dispatch, infeasible_confirm, maintain])
    planner = RescuePlanner(utility_evaluator=UtilityEvaluation(default_mode="victim_support_mode"))

    decision = planner.plan(2, rescue_space=space)

    assert decision is not None
    assert decision.selected_option_id == "maintain"


def _failsafe_option(
    option_id: str,
    option_type: str,
    parameters: dict,
) -> FailSafeAdaptationOption:
    return FailSafeAdaptationOption(
        option_id=option_id,
        option_type=option_type,
        target_entity="uav-1",
        parameters=dict(parameters),
        expected_effect="test",
        cost_estimate=0.1,
        risk_estimate=0.1,
        confidence=1.0,
        scope=Scope.system,
        timestamp=0.0,
        originating_trigger="t",
        explanation_hint="",
    )


def test_fail_safe_planner_prefers_search_under_search_mode_required_trigger() -> None:
    trigger = SimpleNamespace(trigger_type="SEARCH_MODE_REQUIRED")
    analysis = SimpleNamespace(all_triggers=(trigger,))
    hold = _failsafe_option(
        "hold",
        "failsafe_hold_position",
        {
            "mission_value": 0.9,
            "stability_bonus": 0.85,
            "energy_failure_risk": 0.1,
            "support_loss": 0.05,
        },
    )
    search = _failsafe_option(
        "search",
        "failsafe_search_patrol",
        {
            "mission_value": 0.25,
            "stability_bonus": 0.2,
            "energy_failure_risk": 0.2,
            "support_loss": 0.1,
            "recovery_value": 0.15,
            "search_mode": True,
        },
    )
    space = FailSafeAdaptationSpace(options=[hold, search])
    planner = FailSafePlanner(utility_evaluator=UtilityEvaluation(default_mode="information_recovery_mode"))

    decision = planner.plan(
        1,
        triggers=(trigger,),
        fail_safe_space=space,
        analysis_snapshot=analysis,
    )

    assert decision is not None
    assert decision.selected_option_id == "search"
    assert "search-mode policy applied" in decision.explanation


def test_fail_safe_planner_marks_search_mode_active_for_search_decision() -> None:
    search = _failsafe_option(
        "search",
        "failsafe_search_patrol",
        {
            "mission_value": 0.5,
            "stability_bonus": 0.5,
            "energy_failure_risk": 0.2,
            "support_loss": 0.1,
            "search_mode": True,
            "recovery_value": 0.8,
        },
    )
    space = FailSafeAdaptationSpace(options=[search])
    planner = FailSafePlanner(utility_evaluator=UtilityEvaluation(default_mode="information_recovery_mode"))

    decision = planner.plan(2, fail_safe_space=space)

    assert decision is not None
    assert decision.search_mode_active is True


def test_fail_safe_planner_maintain_current_failsafe_fallback() -> None:
    maintain = _failsafe_option(
        "maintain",
        "maintain_current_failsafe",
        {
            "mission_value": 0.4,
            "stability_bonus": 0.5,
            "energy_failure_risk": 0.1,
            "support_loss": 0.1,
            "maintain_current_failsafe": True,
        },
    )
    infeasible_rtb = _failsafe_option(
        "bad_rtb",
        "failsafe_return_to_base",
        {
            "mission_value": 0.9,
            "stability_bonus": 0.8,
            "energy_failure_risk": 0.9,
            "support_loss": 0.1,
            "hard_collision_violation": True,
        },
    )
    infeasible_search = _failsafe_option(
        "bad_search",
        "failsafe_search_patrol",
        {
            "mission_value": 0.8,
            "stability_bonus": 0.7,
            "energy_failure_risk": 0.2,
            "support_loss": 0.1,
            "search_mode": True,
            "route_feasible": False,
        },
    )
    space = FailSafeAdaptationSpace(options=[infeasible_rtb, infeasible_search, maintain])
    planner = FailSafePlanner(utility_evaluator=UtilityEvaluation(default_mode="safety_first_mode"))

    decision = planner.plan(3, fail_safe_space=space)

    assert decision is not None
    assert decision.selected_option_id == "maintain"
