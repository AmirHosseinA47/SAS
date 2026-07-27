"""Structured explanation type contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .contracts import _json_safe


@dataclass
class OptionComparisonExplanation:
    step: int
    planner: str
    selected_option: str
    alternatives: list[dict[str, Any]]
    selected_score: float | None
    alternative_scores: list[float]
    ranking_reason: str
    key_factors: list[str] = field(default_factory=list)
    target_id: str = "mission"
    source_data_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe({**asdict(self), "explanation_kind": "option_comparison"})


@dataclass
class BeforeAfterDecisionExplanation:
    step: int
    decision_type: str
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    expected_effect: str
    observed_effect: str = ""
    source_data_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe({**asdict(self), "explanation_kind": "before_after"})


@dataclass
class UncertaintyExplanation:
    step: int
    uncertainty_metric: str
    trigger: str
    affected_area: str
    selected_recovery_action: str
    evidence: dict[str, Any] = field(default_factory=dict)
    source_data_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe({**asdict(self), "explanation_kind": "uncertainty"})


@dataclass
class TradeoffExplanation:
    step: int
    tradeoff_type: str
    selected_side: str
    rejected_side: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    source_data_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe({**asdict(self), "explanation_kind": "tradeoff"})


@dataclass
class ExplanationBundle:
    """All explanation records collected for one dashboard snapshot."""

    decision_explanations: list[dict[str, Any]] = field(default_factory=list)
    structured_explanations: list[dict[str, Any]] = field(default_factory=list)
    option_comparison_count: int = 0
    uncertainty_count: int = 0
    tradeoff_count: int = 0
    before_after_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))
