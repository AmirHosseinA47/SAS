"""Managing system: communication adaptation planner.

Managing system: plans communication-aware adaptation (priorities, relay
role, degraded modes) not operational message send/receive (managed
execution). Produces decisions for execution to apply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..analysis.trigger_objects import TriggerBatch
from .decision_objects import FailSafeDecision, RescueDecision

MODE_PRIORITY: tuple[str, ...] = (
    "fail_safe_priority",
    "rescue_priority",
    "relay_support",
    "degraded_communication",
    "reduced_load",
    "normal",
)


@dataclass
class CommunicationAdaptationPlanner:
    """Managing-side planner: communication adaptation choices (not packet I/O)."""

    def plan(
        self,
        step_index: int,
        triggers: TriggerBatch | None = None,
        *,
        communication_adaptation_space: object | None = None,
        adaptation_space_snapshot: object | None = None,
        analysis_snapshot: object | None = None,
        runtime_models: object | None = None,
        fail_safe_decision: FailSafeDecision | None = None,
        rescue_decision: RescueDecision | None = None,
        timestamp: float | None = None,
    ) -> dict[str, Any] | None:
        """Select the best communication adaptation decision for this step."""
        _ = triggers
        _ = adaptation_space_snapshot
        _ = analysis_snapshot
        _ = fail_safe_decision
        _ = rescue_decision

        options = _communication_options(communication_adaptation_space, runtime_models)
        if not options:
            return None

        resolved_timestamp = float(timestamp if timestamp is not None else step_index)
        context_mode, context_explanation = _resolve_context_preferred_mode(runtime_models)
        if context_mode:
            selected = _find_option_by_mode(options, context_mode)
            if selected is None:
                return _synthetic_decision(
                    context_mode,
                    step_index=step_index,
                    timestamp=resolved_timestamp,
                    explanation=context_explanation,
                )
            return _decision_from_option(
                selected,
                step_index=step_index,
                timestamp=resolved_timestamp,
                explanation=context_explanation,
            )

        available = {
            str(getattr(option, "parameters", {}).get("communication_mode", "") or ""): option
            for option in options
        }
        for mode in MODE_PRIORITY:
            option = available.get(mode)
            if option is not None:
                return _decision_from_option(
                    option,
                    step_index=step_index,
                    timestamp=resolved_timestamp,
                    explanation=str(getattr(option, "explanation_hint", "") or ""),
                )

        selected = max(options, key=lambda opt: float(getattr(opt, "confidence", 0.0) or 0.0))
        return _decision_from_option(
            selected,
            step_index=step_index,
            timestamp=resolved_timestamp,
            explanation=str(getattr(selected, "explanation_hint", "") or ""),
        )


def _communication_options(
    communication_adaptation_space: object | None,
    runtime_models: object | None,
) -> list[Any]:
    if communication_adaptation_space is None and runtime_models is not None:
        models = runtime_models if isinstance(runtime_models, dict) else {}
        communication_adaptation_space = models.get("communication_adaptation_space")
    if communication_adaptation_space is None:
        return []
    raw_options = getattr(communication_adaptation_space, "options", None)
    if raw_options is None and isinstance(communication_adaptation_space, dict):
        raw_options = communication_adaptation_space.get("options")
    if not raw_options:
        return []
    return [
        option
        for option in raw_options
        if "communication" in str(getattr(option, "option_type", "") or "").lower()
        or str(getattr(option, "parameters", {}).get("communication_mode", "") or "")
    ]


def _find_option_by_mode(options: list[Any], mode: str) -> Any | None:
    for option in options:
        option_mode = str(getattr(option, "parameters", {}).get("communication_mode", "") or "")
        if option_mode == mode:
            return option
    return None


def _resolve_context_preferred_mode(
    runtime_models: object | None,
) -> tuple[str | None, str]:
    failsafe = _read_runtime(runtime_models, "latest_failsafe_state")
    if failsafe is not None:
        mode = getattr(failsafe, "mode", None)
        mode_val = str(getattr(mode, "value", mode) or "").lower()
        if mode_val and mode_val not in {"normal", "none"}:
            return (
                "fail_safe_priority",
                f"Fail-safe mode {mode_val} requires fail-safe communication priority",
            )

    if _rescue_coordination_active(runtime_models):
        return (
            "rescue_priority",
            "Active rescue coordination requires rescue-priority communication",
        )
    return None, ""


def _rescue_coordination_active(runtime_models: object | None) -> bool:
    mission_goals = _read_runtime(runtime_models, "mission_goals")
    if isinstance(mission_goals, dict):
        if int(mission_goals.get("active_rescues", 0) or 0) > 0:
            return True
        phase = str(mission_goals.get("mission_phase", "") or "").lower()
        if "rescue" in phase:
            return True

    victim_model = _read_runtime(runtime_models, "victim_runtime_model")
    if victim_model is not None:
        for attr in ("active_rescues", "assigned_victims", "pending_rescues"):
            value = getattr(victim_model, attr, None)
            if isinstance(value, (list, tuple, set)) and len(value) > 0:
                return True

    simulation = _read_runtime(runtime_models, "simulation_model")
    managed = getattr(simulation, "managed_victims", None) if simulation is not None else None
    if isinstance(managed, dict):
        for state in managed.values():
            if bool(getattr(state, "rescue_assigned", False)):
                return True
            status = str(getattr(state, "status", "") or "").lower()
            if status in {"assigned", "en_route", "confirmed", "pending_rescue"}:
                return True
    return False


def _read_runtime(runtime_models: object | None, key: str) -> Any:
    if runtime_models is None:
        return None
    if isinstance(runtime_models, dict):
        return runtime_models.get(key)
    return getattr(runtime_models, key, None)


def _synthetic_decision(
    mode: str,
    *,
    step_index: int,
    timestamp: float,
    explanation: str,
) -> dict[str, Any]:
    return {
        "decision_id": f"comm-{int(timestamp)}-{mode}",
        "selected_option_id": f"communication_{mode}",
        "communication_mode": mode,
        "communication_action": f"prioritize_{mode.replace('_priority', '')}_messages",
        "target_entity": "communication_system",
        "message_id": f"comm-{int(timestamp)}",
        "priority": "critical" if mode in {"rescue_priority", "fail_safe_priority"} else "normal",
        "explanation": explanation,
        "parameters": {"communication_mode": mode},
        "step_index": step_index,
    }


def _decision_from_option(
    option: Any,
    *,
    step_index: int,
    timestamp: float,
    explanation: str,
) -> dict[str, Any]:
    params = dict(getattr(option, "parameters", {}) or {})
    mode = str(params.get("communication_mode", "normal") or "normal")
    action = str(
        params.get("communication_action", "")
        or getattr(option, "expected_effect", "")
        or mode
    )
    hint = str(getattr(option, "explanation_hint", "") or "")
    return {
        "decision_id": f"comm-{int(timestamp)}-{getattr(option, 'option_id', 'communication')}",
        "selected_option_id": str(getattr(option, "option_id", "")),
        "communication_mode": mode,
        "communication_action": action,
        "target_entity": str(getattr(option, "target_entity", "communication_system")),
        "message_id": f"comm-{int(timestamp)}",
        "priority": "critical" if mode in {"rescue_priority", "fail_safe_priority"} else "normal",
        "explanation": explanation or hint,
        "parameters": params,
        "step_index": step_index,
        "comparison_summary": {
            "summary": f"communication_mode={mode}; {explanation or hint}".strip()
        },
    }
