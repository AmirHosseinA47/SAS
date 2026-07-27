"""Read live mission goal context inside planners and adaptation generators."""

from __future__ import annotations

from typing import Any


def _read(source: object | None, name: str, default: object = None) -> object:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def read_mission_goals(runtime_models: object | None) -> dict[str, Any]:
    if runtime_models is None:
        return {}
    cached = _read(runtime_models, "mission_goals", None)
    if isinstance(cached, dict):
        return cached
    mission_goal_model = _read(runtime_models, "mission_goal_model", None)
    if mission_goal_model is not None and hasattr(mission_goal_model, "runtime_context"):
        return mission_goal_model.runtime_context()
    return {}


def mission_goal_option_metadata(
    mission_goals: dict[str, Any],
    *,
    reason: str = "",
) -> dict[str, Any]:
    if not mission_goals:
        return {}
    return {
        "mission_goal_phase": mission_goals.get("mission_phase"),
        "mission_goal_priorities": dict(mission_goals.get("goal_priorities") or {}),
        "mission_goal_constraints": dict(mission_goals.get("operational_constraints") or {}),
        "mission_goal_reason": reason,
    }


def goal_priority_enabled(mission_goals: dict[str, Any], priority_key: str) -> bool:
    priorities = mission_goals.get("goal_priorities") or {}
    return bool(priorities.get(priority_key))


def active_fail_safe_mode(mission_goals: dict[str, Any]) -> str:
    metrics = mission_goals.get("dynamic_metrics") or {}
    return str(metrics.get("active_fail_safe_mode", "normal") or "normal").strip().lower()


def dynamic_metric(mission_goals: dict[str, Any], key: str, default: object = 0) -> object:
    metrics = mission_goals.get("dynamic_metrics") or {}
    return metrics.get(key, default)


def boost_confidence(confidence: float, amount: float) -> float:
    return min(1.0, float(confidence) + float(amount))


def path_constraint_flags(parameters: dict[str, Any]) -> dict[str, bool]:
    """Mark known risky path parameters for ConstraintFilter mission checks."""
    flags: dict[str, bool] = {}
    action = str(parameters.get("path_action", "") or "")
    if parameters.get("fire_front_target") or action.startswith("move_toward_fire"):
        flags["enters_fire_zone"] = True
    if parameters.get("smoke_exposure") or parameters.get("near_smoke"):
        flags["enters_smoke_zone"] = True
    return flags


def failsafe_restricts_rescue(mission_goals: dict[str, Any]) -> bool:
    return active_fail_safe_mode(mission_goals) in {"safety_first", "emergency"}


def resolve_utility_mode(
    analysis_snapshot: object | None,
    runtime_models: object | None = None,
) -> str | None:
    goals = read_mission_goals(runtime_models)
    utility_mode = goals.get("utility_weight_mode")
    if isinstance(utility_mode, str) and utility_mode.strip():
        return utility_mode.strip()

    mission_goal_model = _read(runtime_models, "mission_goal_model", None)
    if mission_goal_model is not None and hasattr(mission_goal_model, "utility_weight_mode"):
        return mission_goal_model.utility_weight_mode()

    if analysis_snapshot is None:
        return None
    for key in ("utility_mode", "operational_mode", "mission_mode"):
        value = _read(analysis_snapshot, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
