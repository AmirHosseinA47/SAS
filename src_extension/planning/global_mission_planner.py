"""Managing system: global mission planner.

Responsibility: choose what should change at team level (roles, sectors,
mode switches) by producing ``MissionDecision`` objects. This module **does not**
move UAVs, does not write simulator state, and does not execute. execution
applies decisions to managed entities.

TODO: Input from ``knowledge.shared_operational_picture`` and ``TriggerBatch``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..analysis.trigger_objects import TriggerBatch
from .decision_objects import MissionDecision
from .planner_selection import (
    find_maintain_option,
    option_confidence,
    option_id,
    option_parameters,
)
from .mission_goal_integration import resolve_utility_mode as _resolve_utility_mode_from_goals
from .utility_evaluation import ScoredOption, UtilityEvaluation

_NON_GLOBAL_SCOPES = frozenset({"rescue", "local", "system"})
_NON_GLOBAL_TYPE_MARKERS = (
    "rescue",
    "fail_safe",
    "failsafe",
    "fail-safe",
    "path",
    "movement",
    "sensing",
    "communication",
    "horizon",
    "relay_adapt",
)
_UNCERTAINTY_PARAM_KEYS = (
    "uncertainty_level",
    "knowledge_confidence",
    "information_collapse",
    "communication_reliability",
    "fire_spread_speed",
)


@dataclass
class GlobalMissionPlanner:
    """Adaptation planner: global mission intent (not physical actuation)."""

    utility_evaluator: UtilityEvaluation = field(default_factory=UtilityEvaluation)

    def plan(
        self,
        step_index: int,
        triggers: TriggerBatch | None = None,
        *,
        adaptation_space_snapshot: object | None = None,
        analysis_snapshot: object | None = None,
        runtime_models: object | None = None,
        timestamp: float | None = None,
    ) -> MissionDecision | None:
        """Produce a mission decision from global adaptation options (planning only)."""
        _ = triggers
        _ = timestamp

        options = _global_mission_options(adaptation_space_snapshot)
        mission_options = tuple(o for o in options if _is_global_mission_option(o))

        mode = _resolve_utility_mode_from_goals(analysis_snapshot, runtime_models)
        context = _planning_context(analysis_snapshot)
        evaluator = self.utility_evaluator

        scored = evaluator.score_options(
            mission_options,
            runtime_models=runtime_models,
            context=context,
            mode=mode,
        )
        selected = _select_feasible_option(scored, mission_options)
        comparison_text = _comparison_summary_text(scored)

        decision_id = f"m-{step_index}"
        if not selected:
            return MissionDecision(
                decision_id=decision_id,
                comparison_summary={"summary": comparison_text},
                explanation="No global mission options available; no assignment change.",
            )

        params = option_parameters(selected)
        scored_entry = _scored_entry_for(scored, selected)
        explanation = (
            scored_entry.evaluation.explanation_summary
            if scored_entry is not None
            else str(params.get("explanation", "") or "")
        )
        confidence = (
            scored_entry.evaluation.confidence_score
            if scored_entry is not None
            else option_confidence(selected)
        )

        return MissionDecision(
            decision_id=decision_id,
            uav_assignments=_uav_assignments_from_params(params),
            task_assignments=_task_assignments_from_params(params),
            mission_mode=str(params.get("mission_mode", "") or ""),
            relay_assignments=_relay_assignments_from_params(params),
            recall_orders=_recall_orders_from_params(params),
            confidence_score=confidence,
            uncertainty_context=_uncertainty_context(params, analysis_snapshot),
            comparison_summary={"summary": comparison_text},
            explanation=explanation,
            selected_option_id=option_id(selected),
        )


def _global_mission_options(snapshot: object | None) -> tuple[object, ...]:
    if snapshot is None:
        return ()
    global_space = getattr(snapshot, "global_space", None)
    if global_space is None:
        return ()
    options = getattr(global_space, "options", None)
    if options is not None:
        return tuple(options)
    if isinstance(global_space, (list, tuple)):
        return tuple(global_space)
    return ()


def _is_global_mission_option(option: object) -> bool:
    if type(option).__name__ == "MissionAdaptationOption":
        return not _is_clearly_non_global(option)
    if _is_clearly_non_global(option):
        return False
    scope = _scope_value(option)
    if scope == "global":
        return True
    ot = str(getattr(option, "option_type", "") or "").lower()
    global_keys = ("global", "mission", "task", "role", "resource", "reassign")
    return any(k in ot for k in global_keys)


def _is_clearly_non_global(option: object) -> bool:
    scope = _scope_value(option)
    if scope in _NON_GLOBAL_SCOPES:
        return True
    ot = str(getattr(option, "option_type", "") or "").lower()
    return any(marker in ot for marker in _NON_GLOBAL_TYPE_MARKERS)


def _scope_value(option: object) -> str | None:
    scope = getattr(option, "scope", None)
    if scope is None:
        return None
    raw = getattr(scope, "value", scope)
    return str(raw).lower()


def _select_feasible_option(
    scored: tuple[ScoredOption, ...],
    options: tuple[object, ...],
) -> object | None:
    for entry in scored:
        if entry.evaluation.feasible:
            return entry.option
    return find_maintain_option(options)


def _scored_entry_for(
    scored: tuple[ScoredOption, ...],
    selected: object,
) -> ScoredOption | None:
    for entry in scored:
        if entry.option is selected:
            return entry
    sel_id = option_id(selected)
    if not sel_id:
        return None
    for entry in scored:
        if entry.evaluation.option_id == sel_id:
            return entry
    return None


def _comparison_summary_text(scored: tuple[ScoredOption, ...]) -> str:
    if not scored:
        return "Global mission planner: no options evaluated."
    lines = [
        "Global mission option comparison",
        f"- Candidates evaluated: {len(scored)}",
    ]
    for i, entry in enumerate(scored[:5], start=1):
        ev = entry.evaluation
        lines.append(
            f"  {i}. {ev.option_id} [{ev.option_type}] score={entry.score:.4f} feasible={ev.feasible}"
        )
    best = scored[0]
    lines.append(f"- Top ranked id: {best.evaluation.option_id} (feasible={best.evaluation.feasible})")
    return "\n".join(lines)


def _resolve_utility_mode(analysis_snapshot: object | None) -> str | None:
    if analysis_snapshot is None:
        return None
    for key in ("utility_mode", "operational_mode", "mission_mode"):
        value = _snapshot_value(analysis_snapshot, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _planning_context(analysis_snapshot: object | None) -> object | None:
    return analysis_snapshot


def _snapshot_value(snapshot: object, key: str) -> object | None:
    if isinstance(snapshot, dict):
        return snapshot.get(key)
    return getattr(snapshot, key, None)


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}


def _uav_assignments_from_params(params: dict[str, Any]) -> dict[str, str]:
    for key in ("uav_assignments", "role_assignments"):
        mapped = _string_dict(params.get(key))
        if mapped:
            return mapped
    assigned = params.get("assigned_role")
    if isinstance(assigned, dict):
        return _string_dict(assigned)
    return {}


def _task_assignments_from_params(params: dict[str, Any]) -> dict[str, str]:
    for key in ("task_assignments", "task_assignment"):
        val = params.get(key)
        if isinstance(val, dict):
            return _string_dict(val)
        if isinstance(val, str) and val.strip():
            return {"task": val.strip()}
    target_region = params.get("target_region")
    if target_region is not None and str(target_region).strip():
        return {"target_region": str(target_region).strip()}
    return {}


def _relay_assignments_from_params(params: dict[str, Any]) -> dict[str, str]:
    for key in ("relay_assignments", "relay_assignment"):
        mapped = _string_dict(params.get(key))
        if mapped:
            return mapped
    return {}


def _recall_orders_from_params(params: dict[str, Any]) -> tuple[str, ...]:
    orders: list[str] = []
    if _is_truthy(params.get("return_to_base")):
        orders.append("return_to_base")
    recall = params.get("recall_order")
    if isinstance(recall, str) and recall.strip():
        orders.append(recall.strip())
    elif isinstance(recall, (list, tuple)):
        orders.extend(str(item).strip() for item in recall if str(item).strip())
    return tuple(orders)


def _uncertainty_context(
    params: dict[str, Any],
    analysis_snapshot: object | None,
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key in _UNCERTAINTY_PARAM_KEYS:
        if key in params:
            context[key] = params[key]
    if analysis_snapshot is not None:
        for key in _UNCERTAINTY_PARAM_KEYS:
            if key in context:
                continue
            value = _snapshot_value(analysis_snapshot, key)
            if value is not None:
                context[key] = value
    return context


def _is_truthy(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value != 0.0:
        return True
    if isinstance(value, str) and value.strip().lower() in ("1", "true", "yes", "on"):
        return True
    return False
