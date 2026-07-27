"""Lightweight helpers for scoring and selecting planner adaptation options."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .utility_evaluation import (
    ScoredOption,
    UtilityEvaluation,
    build_utility_dashboard_summary,
    safe_float,
)

_MAINTAIN_TYPE_MARKERS = ("do_nothing", "stability_control", "maintain_current_config")


def score_and_select_best(
    options: Iterable[object],
    utility_evaluator: UtilityEvaluation,
    runtime_models: object | None = None,
    context: object | None = None,
    mode: str | None = None,
) -> tuple[object | None, tuple[ScoredOption, ...], str]:
    """Score options via ``utility_evaluator`` and return the top-ranked choice."""
    scored = utility_evaluator.score_options(
        options,
        runtime_models=runtime_models,
        context=context,
        mode=mode,
    )
    best = scored[0].option if scored else None
    comparison_summary = build_utility_dashboard_summary(scored)
    return best, scored, comparison_summary


def find_maintain_option(options: Iterable[object]) -> object | None:
    """Return a do-nothing / stability-control option when present."""
    for option in options:
        if _is_maintain_option(option):
            return option
    return None


def option_parameters(option: object) -> dict[str, Any]:
    """Safely extract ``option.parameters`` as a dict."""
    params = getattr(option, "parameters", None)
    if isinstance(params, dict):
        return dict(params)
    return {}


def option_id(option: object) -> str:
    """Safely extract ``option.option_id`` as a string."""
    return str(getattr(option, "option_id", "") or "")


def option_confidence(option: object) -> float:
    """Safely extract ``option.confidence`` as a float."""
    return safe_float(getattr(option, "confidence", None), 0.5)


def _is_maintain_option(option: object) -> bool:
    ot = str(getattr(option, "option_type", "") or "").lower()
    if any(marker in ot for marker in _MAINTAIN_TYPE_MARKERS):
        return True
    params = option_parameters(option)
    for key in _MAINTAIN_TYPE_MARKERS:
        value = params.get(key)
        if value is True:
            return True
        if isinstance(value, (int, float)) and value != 0.0:
            return True
        if isinstance(value, str) and value.strip().lower() in ("1", "true", "yes", "on"):
            return True
    return False
