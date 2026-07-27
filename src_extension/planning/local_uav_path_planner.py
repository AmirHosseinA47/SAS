"""Managing system: local UAV path planner (scaffold).

Responsibility: choose what path change should occur for one UAV by
producing ``PathDecision`` values (decision-level waypoints/segments). Does
not perform low-level flight control or simulator moves execution applies
the decision to managed operation.

TODO: Consume knowledge constraints (resource, visibility, communication).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..analysis.trigger_objects import TriggerBatch
from ..adaptation.local_adaptation_generator import (
    LocalAdaptationSpaceGenerator,
    WIND_INTERIOR_MARGIN,
    WIND_POCKET_CAMP_THRESHOLD,
)
from .decision_objects import PathDecision
from .planner_selection import (
    find_maintain_option,
    option_confidence,
    option_id,
    option_parameters,
)
from .mission_goal_integration import resolve_utility_mode as _resolve_utility_mode_from_goals
from .utility_evaluation import ScoredOption, UtilityEvaluation

_NON_LOCAL_SCOPES = frozenset({"rescue", "global", "system"})
_NON_LOCAL_TYPE_MARKERS = (
    "rescue",
    "fail_safe",
    "failsafe",
    "fail-safe",
    "mission",
    "role",
    "resource",
    "communication",
)
_HOLD_PATH_MARKERS = ("keep_current_path", "hold_current_path", "maintain_current_path")
_CARDINAL_WORDS = frozenset({"east", "south", "west", "north", "hold"})
_UNCERTAINTY_PARAM_KEYS = (
    "uncertainty_level",
    "knowledge_confidence",
    "information_collapse",
    "communication_reliability",
    "fire_spread_speed",
)


@dataclass
class LocalUAVPathPlanner:
    """Adaptation planner: local path intent for one UAV (not actuation)."""

    uav_id: str
    utility_evaluator: UtilityEvaluation = field(default_factory=UtilityEvaluation)

    def plan(
        self,
        step_index: int,
        triggers: TriggerBatch | None = None,
        *,
        local_adaptation_space: object | None = None,
        analysis_snapshot: object | None = None,
        local_analysis_result: object | None = None,
        runtime_models: object | None = None,
        context: object | None = None,
        timestamp: float | None = None,
    ) -> PathDecision | None:
        """Produce a path decision for ``uav_id`` (planning only)."""
        _ = triggers
        _ = timestamp

        options = _local_path_options(local_adaptation_space, self.uav_id)
        path_options = tuple(o for o in options if _is_local_path_option(o))

        analysis = local_analysis_result if local_analysis_result is not None else analysis_snapshot
        mode = _resolve_utility_mode_from_goals(analysis, runtime_models)
        planning_context = context if context is not None else analysis

        scored = self.utility_evaluator.score_options(
            path_options,
            runtime_models=runtime_models,
            context=planning_context,
            mode=mode,
        )
        selected = _select_feasible_option(scored, path_options)
        comparison_text = _comparison_summary_text(scored, self.uav_id)

        decision_id = f"p-{self.uav_id}-{step_index}"
        if not selected:
            return PathDecision(
                decision_id=decision_id,
                uav_id=self.uav_id,
                comparison_summary={"summary": comparison_text},
                explanation=f"No local path options for UAV {self.uav_id}; hold current path.",
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

        target_position = _extract_target_position(params)
        next_action = _next_action_from_params(params)
        uav_position = _resolve_uav_position(
            runtime_models, self.uav_id, planning_context, local_analysis_result
        )
        selected_option_id = option_id(selected)
        wind_target_reached = False
        needs_new_wind_target = False
        force_wind_retarget = False
        force_wind_sweep = False
        path_context = _resolve_path_context(runtime_models, self.uav_id) or {}
        force_wind_retarget = bool(path_context.get("force_wind_retarget"))
        force_wind_sweep = bool(path_context.get("force_wind_sweep"))
        force_coverage_escape = bool(path_context.get("force_coverage_escape"))
        post_rescue_coverage = int(
            path_context.get("post_rescue_coverage_steps_remaining", 0) or 0
        )
        unresolved_victims = int(path_context.get("unresolved_victim_count", 0) or 0)
        coverage_priority = float(path_context.get("coverage_priority", 0.0) or 0.0)
        recent_x = [int(x) for x in (path_context.get("recent_x_positions") or [])]
        corridor_diversity_failure = (
            len(recent_x) >= 20 and all(x >= 38 for x in recent_x[-20:])
        )
        unresolved_coverage_active = (
            post_rescue_coverage > 0
            or (unresolved_victims > 0 and coverage_priority >= 0.85)
            or corridor_diversity_failure
        )
        if unresolved_coverage_active:
            force_coverage_escape = True
            force_wind_retarget = True
        pocket_streak = int(path_context.get("pocket_streak", 0) or 0)
        is_wind_aware = selected_option_id == "wind_aware_victim_search"
        wind_direction = str(params.get("wind_direction") or path_context.get("wind_direction") or "")
        if (
            target_position is not None
            and next_action.lower() not in _CARDINAL_WORDS
            and uav_position is not None
            and not is_wind_aware
        ):
            cardinal = _cardinal_from_positions(uav_position, target_position)
            if cardinal:
                next_action = cardinal
        if is_wind_aware and target_position is not None and uav_position is not None:
            dist = abs(float(uav_position[0]) - float(target_position[0])) + abs(
                float(uav_position[1]) - float(target_position[1])
            )
            near_boundary = _uav_near_boundary(
                uav_position,
                runtime_models,
            )
            gh = _grid_height(runtime_models)
            gw = _grid_width(runtime_models)
            margin = WIND_INTERIOR_MARGIN
            uav_x = int(round(float(uav_position[0])))
            uav_y = int(round(float(uav_position[1])))
            directional_edge = (
                uav_x <= margin
                or uav_x >= gh - 1 - margin
                or uav_y <= margin
                or uav_y >= gw - 1 - margin
            )
            wind_hold_streak = int(path_context.get("wind_aware_hold_streak", 0) or 0)
            wind_edge_streak = int(path_context.get("wind_edge_streak", 0) or 0)
            if dist <= 2.0:
                wind_target_reached = True
                needs_new_wind_target = True
            if (
                dist <= 2.0
                or near_boundary
                or directional_edge
                or wind_hold_streak > 2
                or wind_edge_streak > 10
                or force_wind_retarget
                or force_wind_sweep
                or force_coverage_escape
                or unresolved_coverage_active
                or pocket_streak >= WIND_POCKET_CAMP_THRESHOLD // 2
            ):
                needs_new_wind_target = True
                next_action = str(
                    params.get("path_action")
                    or params.get("next_action")
                    or "victim_search_wind_aware"
                )
            if next_action.lower() == "hold":
                needs_new_wind_target = True
                next_action = "victim_search_wind_aware"
            if directional_edge or pocket_streak >= WIND_POCKET_CAMP_THRESHOLD // 2:
                force_wind_retarget = True
                needs_new_wind_target = True
                next_action = "victim_search_wind_aware"

        uav_role = LocalAdaptationSpaceGenerator._read_uav_role(runtime_models, self.uav_id)
        role_norm = str(uav_role or "").lower()
        if role_norm in {"victim_searcher", "victim_search"} and next_action.lower() == "hold":
            next_action = "victim_search_wind_aware"
            needs_new_wind_target = True
            force_wind_retarget = True

        uncertainty_ctx = _uncertainty_context(params, analysis)
        if path_context:
            uncertainty_ctx = {**path_context, **uncertainty_ctx}
        if target_position is not None:
            uncertainty_ctx = {
                **uncertainty_ctx,
                "target_position": target_position,
                "target_region": target_position,
            }
        if wind_target_reached:
            uncertainty_ctx["wind_target_reached"] = True
        if needs_new_wind_target:
            uncertainty_ctx["needs_new_wind_target"] = True
        if force_wind_retarget:
            uncertainty_ctx["force_wind_retarget"] = True
        if force_wind_sweep:
            uncertainty_ctx["force_wind_sweep"] = True
        if force_coverage_escape:
            uncertainty_ctx["force_coverage_escape"] = True
        if (
            uav_position is not None
            and _uav_near_boundary(uav_position, runtime_models)
            and next_action.lower() == "hold"
        ):
            if role_norm in {"victim_searcher", "victim_search"}:
                next_action = "victim_search_wind_aware"
                needs_new_wind_target = True
                force_wind_retarget = True
            else:
                next_action = "search"
        for key in (
            "wind_direction",
            "wind_vector",
            "search_policy",
            "reason",
            "source",
            "safety_filter",
            "wind_source",
        ):
            if key in params:
                uncertainty_ctx[key] = params[key]

        return PathDecision(
            decision_id=decision_id,
            uav_id=self.uav_id,
            selected_option_id=option_id(selected),
            next_action=next_action,
            path_segment=_path_segment_from_params(params),
            waypoints_by_uav=_waypoints_by_uav_from_params(params, self.uav_id),
            confidence_score=confidence,
            uncertainty_context=uncertainty_ctx,
            comparison_summary={"summary": comparison_text},
            explanation=explanation,
            escalation_request=_escalation_request_from_option(selected, params),
        )


def _local_path_options(space: object | None, uav_id: str) -> tuple[object, ...]:
    if space is None:
        return ()
    options = getattr(space, "options", None)
    if options is None and isinstance(space, dict):
        options = space.get(uav_id)
    if options is None:
        by_uav = getattr(space, "options_by_uav", None)
        if isinstance(by_uav, dict):
            options = by_uav.get(uav_id)
    if options is None:
        return ()
    return tuple(o for o in options if _option_targets_uav(o, uav_id))


def _option_targets_uav(option: object, uav_id: str) -> bool:
    target = getattr(option, "target_entity", None)
    if target is None:
        return True
    return str(target) == uav_id


def _is_local_path_option(option: object) -> bool:
    if type(option).__name__ == "LocalAdaptationOption":
        return not _is_clearly_non_local(option)
    if _is_clearly_non_local(option):
        return False
    scope = _scope_value(option)
    if scope == "local":
        return True
    ot = str(getattr(option, "option_type", "") or "").lower()
    if "wind_aware" in ot:
        return True
    local_keys = ("path", "movement", "sensing", "horizon", "local")
    return any(k in ot for k in local_keys)


def _is_clearly_non_local(option: object) -> bool:
    scope = _scope_value(option)
    if scope in _NON_LOCAL_SCOPES:
        return True
    ot = str(getattr(option, "option_type", "") or "").lower()
    return any(marker in ot for marker in _NON_LOCAL_TYPE_MARKERS)


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
        if (
            entry.evaluation.feasible
            and option_id(entry.option) == "wind_aware_victim_search"
        ):
            return entry.option
    for entry in scored:
        if entry.evaluation.feasible:
            return entry.option
    return _find_hold_path_option(options)


def _find_hold_path_option(options: tuple[object, ...]) -> object | None:
    hold = find_maintain_option(options)
    if hold is not None:
        return hold
    for option in options:
        ot = str(getattr(option, "option_type", "") or "").lower()
        if any(marker in ot for marker in _HOLD_PATH_MARKERS):
            return option
        params = option_parameters(option)
        for key in _HOLD_PATH_MARKERS:
            if _is_truthy(params.get(key)):
                return option
    return None


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


def _comparison_summary_text(scored: tuple[ScoredOption, ...], uav_id: str) -> str:
    if not scored:
        return f"Local path planner ({uav_id}): no options evaluated."
    lines = [
        f"Local path option comparison ({uav_id})",
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


def _resolve_utility_mode(analysis: object | None) -> str | None:
    if analysis is None:
        return None
    for key in ("utility_mode", "operational_mode", "mission_mode"):
        value = _snapshot_value(analysis, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _snapshot_value(snapshot: object, key: str) -> object | None:
    if isinstance(snapshot, dict):
        return snapshot.get(key)
    return getattr(snapshot, key, None)


def _next_action_from_params(params: dict[str, Any]) -> str:
    for key in ("next_action", "movement_action", "path_action", "direction"):
        value = params.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _path_segment_from_params(params: dict[str, Any]) -> tuple[tuple[float, float], ...]:
    return _coords_tuple(params.get("path_segment"))


def _waypoints_by_uav_from_params(params: dict[str, Any], uav_id: str) -> dict[str, tuple[tuple[float, float], ...]]:
    for key in ("waypoints", "target_position", "target_region", "target_location", "waypoint"):
        if key in params:
            coords = _coords_tuple(params.get(key))
            if coords:
                return {uav_id: coords}
    return {}


def _extract_target_position(params: dict[str, Any]) -> tuple[float, float] | None:
    for key in ("target_position", "target_region", "target_location", "waypoint"):
        if key not in params:
            continue
        coords = _coords_tuple(params.get(key))
        if coords:
            return coords[0]
    return None


def _resolve_uav_position(
    runtime_models: object | None,
    uav_id: str,
    context: object | None,
    local_analysis_result: object | None,
) -> tuple[float, float] | None:
    if runtime_models is not None:
        resource = (
            runtime_models.get("uav_resource_model")
            if isinstance(runtime_models, dict)
            else getattr(runtime_models, "uav_resource_model", None)
        )
        if resource is not None:
            by_uav = getattr(resource, "by_uav_id", None)
            if isinstance(by_uav, dict) and uav_id in by_uav:
                state = by_uav[uav_id]
                pos = getattr(state, "current_position", None)
                if pos is None:
                    pos = getattr(state, "position", None)
                if pos is None and isinstance(state, dict):
                    pos = state.get("current_position", state.get("position"))
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    return (float(pos[0]), float(pos[1]))
    for source in (local_analysis_result, context):
        if source is None:
            continue
        for key in ("current_position", "position", "uav_position"):
            value = _snapshot_value(source, key)
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                return (float(value[0]), float(value[1]))
    return None


def _resolve_path_context(
    runtime_models: object | None,
    uav_id: str,
) -> dict[str, Any]:
    if runtime_models is None:
        return {}
    models = runtime_models if isinstance(runtime_models, dict) else {}
    by_uav = models.get("local_path_context_models")
    model = None
    if isinstance(by_uav, dict):
        model = by_uav.get(str(uav_id))
    if model is None:
        model = models.get("local_path_context_model")
    if model is None:
        return {}
    runtime_context = getattr(model, "runtime_context", None)
    if callable(runtime_context):
        snapshot = runtime_context()
        return dict(snapshot) if isinstance(snapshot, dict) else {}
    snapshot = getattr(model, "snapshot", None)
    if callable(snapshot):
        result = snapshot()
        return dict(result) if isinstance(result, dict) else {}
    return {}


def _grid_height(runtime_models: object | None) -> int:
    if runtime_models is not None:
        sim = (
            runtime_models.get("simulation_model")
            if isinstance(runtime_models, dict)
            else getattr(runtime_models, "simulation_model", None)
        )
        if sim is not None:
            return int(getattr(sim, "HEIGHT", getattr(sim, "height", 50)) or 50)
    return 50


def _grid_width(runtime_models: object | None) -> int:
    if runtime_models is not None:
        sim = (
            runtime_models.get("simulation_model")
            if isinstance(runtime_models, dict)
            else getattr(runtime_models, "simulation_model", None)
        )
        if sim is not None:
            return int(getattr(sim, "WIDTH", getattr(sim, "width", 50)) or 50)
    return 50


def _uav_near_boundary(
    uav_position: tuple[float, float],
    runtime_models: object | None,
    margin: int = 2,
) -> bool:
    height = width = 50
    if runtime_models is not None:
        sim = (
            runtime_models.get("simulation_model")
            if isinstance(runtime_models, dict)
            else getattr(runtime_models, "simulation_model", None)
        )
        if sim is not None:
            height = int(getattr(sim, "HEIGHT", getattr(sim, "height", 50)) or 50)
            width = int(getattr(sim, "WIDTH", getattr(sim, "width", 50)) or 50)
    x = int(round(float(uav_position[0])))
    y = int(round(float(uav_position[1])))
    return (
        x <= margin
        or y <= margin
        or x >= height - 1 - margin
        or y >= width - 1 - margin
    )


def _cardinal_from_positions(
    uav_position: tuple[float, float],
    target_position: tuple[float, float],
) -> str:
    dx = float(target_position[0]) - float(uav_position[0])
    dy = float(target_position[1]) - float(uav_position[1])
    if abs(dx) < 0.01 and abs(dy) < 0.01:
        return "hold"
    if abs(dx) >= abs(dy):
        if dx > 0:
            return "east"
        if dx < 0:
            return "west"
        return "hold"
    if dy < 0:
        return "south"
    if dy > 0:
        return "north"
    return "hold"


def _coords_tuple(value: object) -> tuple[tuple[float, float], ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        if not value:
            return ()
        if isinstance(value[0], (list, tuple)):
            out: list[tuple[float, float]] = []
            for point in value:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    out.append((float(point[0]), float(point[1])))
            return tuple(out)
        if len(value) >= 2 and isinstance(value[0], (int, float)):
            return ((float(value[0]), float(value[1])),)
    return ()


def _escalation_request_from_option(
    option: object,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    escalation = params.get("escalation_request")
    if isinstance(escalation, dict):
        return dict(escalation)
    ot = str(getattr(option, "option_type", "") or "").lower()
    if _is_truthy(params.get("escalation")) or "escalat" in ot:
        payload = params.get("escalation_payload")
        request: dict[str, Any] = {
            "uav_id": str(getattr(option, "target_entity", "") or params.get("uav_id", "") or ""),
            "reason": str(params.get("escalation_reason", "") or "local_path_escalation"),
        }
        if isinstance(payload, dict):
            request["payload"] = dict(payload)
        return request
    return None


def _uncertainty_context(
    params: dict[str, Any],
    analysis: object | None,
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key in _UNCERTAINTY_PARAM_KEYS:
        if key in params:
            context[key] = params[key]
    if analysis is not None:
        for key in _UNCERTAINTY_PARAM_KEYS:
            if key in context:
                continue
            value = _snapshot_value(analysis, key)
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
