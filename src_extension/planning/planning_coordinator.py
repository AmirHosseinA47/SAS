"""Planning coordinator: run planners over adaptation spaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..analysis.trigger_objects import TriggerBatch, normalize_triggers
from .decision_objects import FailSafeDecision, MissionDecision, PathDecision, RescueDecision
from .communication_adaptation_planner import CommunicationAdaptationPlanner
from .fail_safe_planner import FailSafePlanner
from .global_mission_planner import GlobalMissionPlanner
from .local_uav_path_planner import LocalUAVPathPlanner
from .rescue_planner import RescuePlanner


@dataclass
class PlanningCoordinator:
    """Coordinates adaptation planners; does not execute decisions or mutate models."""

    global_mission_planner: GlobalMissionPlanner = field(default_factory=GlobalMissionPlanner)
    rescue_planner: RescuePlanner = field(default_factory=RescuePlanner)
    fail_safe_planner: FailSafePlanner = field(default_factory=FailSafePlanner)
    communication_adaptation_planner: CommunicationAdaptationPlanner = field(
        default_factory=CommunicationAdaptationPlanner
    )
    _local_path_planners: dict[str, LocalUAVPathPlanner] = field(default_factory=dict)

    def run_planning(
        self,
        adaptation_space_snapshot: object | None,
        analysis_snapshot: object | None,
        runtime_models: object | None = None,
        timestamp: float | None = None,
    ) -> dict[str, object]:
        """Run all Step 9 planners and return structured decisions (planning only)."""
        step_index = _resolve_step_index(adaptation_space_snapshot, analysis_snapshot, timestamp)
        resolved_timestamp = _resolve_timestamp(adaptation_space_snapshot, analysis_snapshot, timestamp)
        triggers = _analysis_triggers(analysis_snapshot)

        rescue_space = _snapshot_attr(adaptation_space_snapshot, "rescue_space")
        fail_safe_space = _snapshot_attr(adaptation_space_snapshot, "fail_safe_space")

        mission_decision = self.global_mission_planner.plan(
            step_index,
            triggers=triggers,
            adaptation_space_snapshot=adaptation_space_snapshot,
            analysis_snapshot=analysis_snapshot,
            runtime_models=runtime_models,
            timestamp=resolved_timestamp,
        )

        rescue_decision = self.rescue_planner.plan(
            step_index,
            triggers=triggers,
            rescue_space=rescue_space,
            analysis_snapshot=analysis_snapshot,
            runtime_models=runtime_models,
            context=analysis_snapshot,
            timestamp=resolved_timestamp,
        )

        fail_safe_decision = self.fail_safe_planner.plan(
            step_index,
            triggers=triggers,
            fail_safe_space=fail_safe_space,
            analysis_snapshot=analysis_snapshot,
            runtime_models=runtime_models,
            context=analysis_snapshot,
            timestamp=resolved_timestamp,
        )

        path_decisions: dict[str, PathDecision | None] = {}
        for uav_id, local_space in _local_spaces_by_uav(adaptation_space_snapshot).items():
            planner = self._local_path_planner(uav_id)
            path_decisions[uav_id] = planner.plan(
                step_index,
                triggers=triggers,
                local_adaptation_space=local_space,
                analysis_snapshot=analysis_snapshot,
                local_analysis_result=_local_analysis_result(analysis_snapshot, uav_id),
                runtime_models=runtime_models,
                context=analysis_snapshot,
                timestamp=resolved_timestamp,
            )

        communication_adaptation_space = None
        if isinstance(runtime_models, dict):
            communication_adaptation_space = runtime_models.get("communication_adaptation_space")
        communication_decision = self.communication_adaptation_planner.plan(
            step_index,
            triggers=triggers,
            communication_adaptation_space=communication_adaptation_space,
            adaptation_space_snapshot=adaptation_space_snapshot,
            analysis_snapshot=analysis_snapshot,
            runtime_models=runtime_models,
            fail_safe_decision=fail_safe_decision,
            rescue_decision=rescue_decision,
            timestamp=resolved_timestamp,
        )

        comparison_summary = _build_comparison_summary(
            adaptation_space_snapshot,
            mission_decision,
            rescue_decision,
            fail_safe_decision,
            path_decisions,
            communication_decision=communication_decision,
        )

        planning_result: dict[str, object] = {
            "mission_decision": mission_decision,
            "rescue_decision": rescue_decision,
            "fail_safe_decision": fail_safe_decision,
            "path_decisions": path_decisions,
            "communication_decision": communication_decision,
            "comparison_summary": comparison_summary,
        }
        planning_result["dashboard_summary"] = build_planning_dashboard_summary(planning_result)
        return planning_result

    def _local_path_planner(self, uav_id: str) -> LocalUAVPathPlanner:
        planner = self._local_path_planners.get(uav_id)
        if planner is None:
            planner = LocalUAVPathPlanner(uav_id=uav_id)
            self._local_path_planners[uav_id] = planner
        return planner


def _resolve_step_index(
    adaptation_space_snapshot: object | None,
    analysis_snapshot: object | None,
    timestamp: float | None,
) -> int:
    for source in (adaptation_space_snapshot, analysis_snapshot):
        if source is None:
            continue
        value = _snapshot_attr(source, "step_index")
        if value is not None:
            return int(value)
    if timestamp is not None:
        return int(timestamp)
    resolved = _resolve_timestamp(adaptation_space_snapshot, analysis_snapshot, timestamp)
    return int(resolved) if resolved is not None else 0


def _resolve_timestamp(
    adaptation_space_snapshot: object | None,
    analysis_snapshot: object | None,
    timestamp: float | None,
) -> float | None:
    if timestamp is not None:
        return float(timestamp)
    for source in (adaptation_space_snapshot, analysis_snapshot):
        if source is None:
            continue
        value = _snapshot_attr(source, "timestamp")
        if value is not None:
            return float(value)
    return None


def _snapshot_attr(snapshot: object | None, key: str) -> object | None:
    if snapshot is None:
        return None
    if isinstance(snapshot, dict):
        return snapshot.get(key)
    return getattr(snapshot, key, None)


def _analysis_triggers(analysis_snapshot: object | None) -> TriggerBatch | None:
    """Return normalized triggers for all Step 9 planners."""
    if analysis_snapshot is None:
        return None
    for key in (
        "all_triggers",
        "trigger_batch",
        "triggers",
        "local_trigger_list",
        "trigger_list",
        "active_triggers",
    ):
        if _snapshot_attr(analysis_snapshot, key) is not None:
            return normalize_triggers(analysis_snapshot)
    batch = normalize_triggers(analysis_snapshot)
    if batch.triggers:
        return batch
    global_result = _snapshot_attr(analysis_snapshot, "global_result")
    if global_result is not None:
        return normalize_triggers(global_result)
    return None


def _local_spaces_by_uav(adaptation_space_snapshot: object | None) -> dict[str, object]:
    local_spaces = _snapshot_attr(adaptation_space_snapshot, "local_spaces")
    if not local_spaces:
        return {}
    by_uav: dict[str, object] = {}
    for space in local_spaces:
        uav_id = _snapshot_attr(space, "uav_id")
        if uav_id is None:
            uav_id = _snapshot_attr(space, "target_entity")
        if uav_id is None:
            options = _snapshot_attr(space, "options")
            if options:
                uav_id = _snapshot_attr(options[0], "target_entity")
        if uav_id is None:
            continue
        by_uav[str(uav_id)] = space
    return by_uav


def _local_analysis_result(analysis_snapshot: object | None, uav_id: str) -> object | None:
    if analysis_snapshot is None:
        return None
    local_results = _snapshot_attr(analysis_snapshot, "local_results")
    if not local_results:
        return None
    for result in local_results:
        if str(_snapshot_attr(result, "uav_id") or "") == str(uav_id):
            return result
    return None


def build_planning_dashboard_summary(planning_result: dict[str, object] | None) -> str:
    """Human-readable Step 9 planning summary (no side effects)."""
    if not planning_result:
        return "Planning dashboard: no planning result."

    mission = planning_result.get("mission_decision")
    rescue = planning_result.get("rescue_decision")
    fail_safe = planning_result.get("fail_safe_decision")
    path_decisions = planning_result.get("path_decisions")
    if not isinstance(path_decisions, dict):
        path_decisions = {}

    search_mode_active = bool(getattr(fail_safe, "search_mode_active", False)) if fail_safe else False
    mission_mode = ""
    if isinstance(mission, MissionDecision) and mission.mission_mode.strip():
        mission_mode = mission.mission_mode.strip()
    elif isinstance(fail_safe, FailSafeDecision) and fail_safe.mission_mode.strip():
        mission_mode = fail_safe.mission_mode.strip()

    lines = [
        "Planning dashboard",
        f"- Selected global option: {_selected_option_id(mission)}",
        f"- Selected fail-safe option: {_selected_option_id(fail_safe)}",
        f"- Selected rescue option: {_selected_option_id(rescue)}",
        f"- Local path decisions: {len(path_decisions)}",
        f"- Search mode active: {search_mode_active}",
    ]
    if mission_mode:
        lines.append(f"- Mission mode: {mission_mode}")

    lines.append("- Explanations:")
    for label, decision in (
        ("mission", mission),
        ("rescue", rescue),
        ("fail_safe", fail_safe),
    ):
        explanation = _short_explanation(decision)
        if explanation:
            lines.append(f"  {label}: {explanation}")
    for uav_id in sorted(path_decisions.keys(), key=str):
        path_decision = path_decisions[uav_id]
        explanation = _short_explanation(path_decision)
        if explanation:
            lines.append(f"  path[{uav_id}]: {explanation}")

    lines.append("- Comparison summary:")
    lines.append(_format_comparison_summary(planning_result.get("comparison_summary")))
    return "\n".join(lines)


def _selected_option_id(decision: object | None) -> str:
    if decision is None:
        return "(none)"
    option_id = str(getattr(decision, "selected_option_id", "") or "").strip()
    return option_id or "(none)"


def _short_explanation(decision: object | None, limit: int = 160) -> str:
    if decision is None:
        return ""
    text = str(getattr(decision, "explanation", "") or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _format_comparison_summary(comparison: object) -> str:
    if comparison is None:
        return "  (none)"
    if isinstance(comparison, str):
        return f"  {comparison}"
    if not isinstance(comparison, dict):
        return f"  {comparison!r}"

    lines: list[str] = []
    for key, value in comparison.items():
        if key == "path" and isinstance(value, dict):
            for uav_id, path_summary in value.items():
                lines.append(f"  path[{uav_id}]: {_comparison_value_text(path_summary)}")
            continue
        lines.append(f"  {key}: {_comparison_value_text(value)}")
    return "\n".join(lines) if lines else "  (none)"


def _comparison_value_text(value: object) -> str:
    if isinstance(value, dict):
        summary = value.get("summary")
        if isinstance(summary, str) and summary.strip():
            first_line = summary.strip().splitlines()[0]
            return first_line[:200]
        return str(value)[:200]
    if isinstance(value, str):
        return value.strip().splitlines()[0][:200]
    return str(value)[:200]


def _build_comparison_summary(
    adaptation_space_snapshot: object | None,
    mission_decision: MissionDecision | None,
    rescue_decision: RescueDecision | None,
    fail_safe_decision: FailSafeDecision | None,
    path_decisions: dict[str, PathDecision | None],
    *,
    communication_decision: dict[str, object] | None = None,
) -> dict[str, object]:
    summary: dict[str, object] = {}
    adaptation_dashboard = _snapshot_attr(adaptation_space_snapshot, "dashboard_summary")
    if adaptation_dashboard is not None:
        summary["adaptation_dashboard"] = adaptation_dashboard
    if mission_decision is not None:
        summary["mission"] = mission_decision.comparison_summary
    if rescue_decision is not None:
        summary["rescue"] = rescue_decision.comparison_summary
    if fail_safe_decision is not None:
        summary["fail_safe"] = fail_safe_decision.comparison_summary
    if path_decisions:
        summary["path"] = {
            uav_id: decision.comparison_summary if decision is not None else {}
            for uav_id, decision in path_decisions.items()
        }
    if isinstance(communication_decision, dict):
        comparison = communication_decision.get("comparison_summary")
        if isinstance(comparison, dict) and comparison.get("summary"):
            summary["communication"] = comparison
        else:
            summary["communication"] = {
                "summary": (
                    f"communication_mode={communication_decision.get('communication_mode')}; "
                    f"{communication_decision.get('explanation', '')}"
                )
            }
    return summary
