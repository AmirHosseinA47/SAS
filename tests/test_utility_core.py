"""Utility evaluation core objects."""

from dataclasses import fields, is_dataclass

import pytest

from src_extension.adaptation.adaptation_option_objects import LocalAdaptationOption, Scope
from src_extension.planning.utility_evaluation import (
    OptionEvaluation,
    ScoredOption,
    UtilityEvaluation,
    UtilityTerm,
    build_utility_dashboard_summary,
)


def test_option_evaluation_has_required_fields() -> None:
    ev = OptionEvaluation(
        option_id="o1",
        option_type="path",
        feasible=True,
        constraint_violations=(),
        predicted_effects={},
        utility_terms=(),
        total_utility=0.0,
        confidence_score=0.5,
        stability_cost=0.0,
        information_recovery_score=0.0,
        explanation_summary="ok",
    )
    assert is_dataclass(ev)
    names = {f.name for f in fields(OptionEvaluation)}
    required = {
        "option_id",
        "option_type",
        "feasible",
        "constraint_violations",
        "predicted_effects",
        "utility_terms",
        "total_utility",
        "confidence_score",
        "stability_cost",
        "information_recovery_score",
        "explanation_summary",
    }
    assert required == names


def test_utility_term_contribution_stored() -> None:
    t = UtilityTerm(
        name="G_info",
        value=0.5,
        weight=1.0,
        contribution=0.42,
        explanation="x",
    )
    assert t.contribution == pytest.approx(0.42)


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


def test_score_options_returns_scored_option_descending() -> None:
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
    ue = UtilityEvaluation(default_mode="safety_first_mode")
    scored = ue.score_options((low, high))
    assert len(scored) == 2
    assert all(isinstance(s, ScoredOption) for s in scored)
    scores = [s.score for s in scored]
    assert scores == sorted(scores, reverse=True)
    assert scored[0].evaluation.option_id == "high"
    assert scored[1].evaluation.option_id == "low"


def test_dashboard_summary_returns_string() -> None:
    high = _local_path_option("a", expected_info_gain=0.8, task_support=0.7)
    low = _local_path_option("b", expected_info_gain=0.1, task_support=0.1)
    ue = UtilityEvaluation(default_mode="safety_first_mode")
    scored = ue.score_options((low, high))
    text = build_utility_dashboard_summary(scored)
    assert isinstance(text, str)
    assert len(text) > 0
    assert "Utility dashboard" in text
    assert "Best option id" in text
