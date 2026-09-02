"""Managing system: adaptation manager — MAPE-K orchestration facade.

**Responsibility:** single place to orchestrate one self-adaptive control cycle:

1. **Monitoring** — structured observations from managed + environment
2. **Knowledge** — refresh runtime models / shared operational picture
3. **Analysis** — interpret observations → ``TriggerBatch``
4. **Adaptation** — generate adaptation option spaces
5. **Planning** — choose adaptations → decisions
6. **Execution** — apply decisions to **managed** entities

This module **orchestrates** by delegating to existing model stage methods; it does
**not** own managed operational state or implement planning/analysis algorithms.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdaptationManager:
    """High-level orchestration facade for one MAPE-K cycle."""

    config: dict[str, Any] = field(default_factory=dict)

    def run_cycle(self, model: Any, phase: str = "pre_move") -> dict[str, Any]:
        """Run one MAPE-K cycle by calling existing model stage methods in order."""
        if phase == "pre_move":
            return self._run_pre_move_cycle(model)
        if phase == "post_move":
            return self._run_post_move_cycle(model)
        raise ValueError(f"unsupported adaptation cycle phase: {phase!r}")

    def run_step(self, step_index: int, model: Any) -> dict[str, Any]:
        """Summarize MAPE-K pipeline readiness from model state after a step."""
        required = (
            "monitoring_buffer",
            "knowledge_manager",
            "shared_operational_picture",
            "latest_analysis_snapshot",
            "latest_adaptation_space_snapshot",
        )
        missing = [name for name in required if not hasattr(model, name)]
        if missing:
            raise ValueError(
                "model missing required MAPE-K pipeline attributes: " + ", ".join(missing)
            )

        monitoring_buffer = getattr(model, "monitoring_buffer")
        knowledge_manager = getattr(model, "knowledge_manager")
        shared_operational_picture = getattr(model, "shared_operational_picture")
        latest_analysis_snapshot = getattr(model, "latest_analysis_snapshot")
        latest_adaptation_space_snapshot = getattr(model, "latest_adaptation_space_snapshot")
        latest_planning_result = getattr(model, "latest_planning_result", None)
        latest_execution_result = getattr(model, "latest_execution_result", None)

        planning_available = latest_planning_result is not None
        execution_available = latest_execution_result is not None
        status = "monitor_knowledge_analysis_adaptation_space_ready"
        if planning_available and execution_available:
            status = "full_mape_cycle_ready"
        elif planning_available:
            status = "planning_ready"

        return {
            "step_index": step_index,
            "monitoring_available": monitoring_buffer is not None,
            "knowledge_available": knowledge_manager is not None
            and shared_operational_picture is not None,
            "analysis_available": latest_analysis_snapshot is not None,
            "adaptation_space_available": latest_adaptation_space_snapshot is not None,
            "planning_available": planning_available,
            "execution_available": execution_available,
            "status": status,
        }

    def _run_pre_move_cycle(self, model: Any) -> dict[str, Any]:
        current_step_time = float(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        result: dict[str, Any] = {
            "phase": "pre_move",
            "step_time": current_step_time,
            "monitoring": None,
            "analysis": None,
            "adaptation": None,
            "planning": None,
            "execution": None,
            "failsafe_mode": None,
            "rescue_events": None,
            "communication": None,
            "explanations": [],
        }

        _call_stage(model, "_sync_environment_wind", current_step_time)

        snapshot = _collect_global_snapshot(model, current_step_time)
        result["monitoring"] = _monitoring_summary(model, snapshot)

        _call_stage(model, "_detect_victims_in_uav_radius")
        result["rescue_events"] = _process_rescue_incidents(model)

        _call_stage(model, "_rebuild_shared_operational_picture", current_step_time, snapshot)
        _call_stage(model, "_refresh_mission_goal_model", current_step_time)
        _call_stage(model, "_refresh_local_path_context_models", current_step_time)

        _call_stage(model, "_run_analysis", current_step_time, snapshot)
        result["analysis"] = _analysis_summary(model)

        _call_stage(model, "_run_adaptation_space_generation")
        result["adaptation"] = _adaptation_summary(model)

        _call_stage(model, "_run_planning", current_step_time)
        result["planning"] = _planning_summary(model)

        _call_stage(model, "_update_failsafe_mode", current_step_time)
        result["failsafe_mode"] = _failsafe_summary(model)

        _call_stage(model, "_run_execution", current_step_time)
        result["execution"] = _execution_summary(model)
        result["communication"] = _communication_summary(model)

        _call_stage(model, "_update_failsafe_mode", current_step_time)
        result["failsafe_mode"] = _failsafe_summary(model)

        result["explanations"] = _collect_explanations(model, result)
        return result

    def _run_post_move_cycle(self, model: Any) -> dict[str, Any]:
        current_step_time = float(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        result: dict[str, Any] = {
            "phase": "post_move",
            "step_time": current_step_time,
            "cleanup": None,
            "monitoring": None,
            "knowledge": None,
            "rescue_events": None,
            "rescue_sync": None,
            "communication": None,
            "explanations": [],
        }

        pending_removals = _call_stage(model, "_process_pending_agent_removals")
        rescue_path_cleared = _call_stage(model, "_clear_rescue_path_if_requested")
        _call_stage(model, "_update_uav_stuck_counts_after_move")
        removal_failures = int(
            getattr(model, "pending_removal_failures_last_step", 0) or 0
        )
        result["cleanup"] = {
            "pending_removals": int(pending_removals or 0),
            "pending_removal_failures": removal_failures,
            "rescue_path_cleared": bool(rescue_path_cleared),
        }
        if removal_failures:
            # `dashboard_summary` is the only key of this result the explanation
            # engine reads, and a swallowed removal is the one thing in the
            # cleanup stage worth putting in front of a human.
            result["dashboard_summary"] = (
                "pending agent removal failed for %d queued agent(s)"
                % removal_failures
            )

        _call_stage(model, "_update_managed_uav_states_from_agents")
        _call_stage(model, "_refresh_local_path_context_models", current_step_time)

        _call_stage(model, "_refresh_post_move_environment_bridge", current_step_time)
        snapshot = _collect_post_move_monitoring_snapshots(model, current_step_time)
        result["monitoring"] = _monitoring_summary(model, snapshot)

        _call_stage(model, "_detect_victims_in_uav_radius")
        result["rescue_events"] = _process_rescue_incidents(model)

        _call_stage(
            model,
            "_refresh_knowledge_from_post_move_monitoring",
            current_step_time,
            snapshot,
        )
        result["knowledge"] = _post_move_knowledge_summary(model)

        _call_stage(model, "_check_fire_casualties")
        result["rescue_sync"] = _process_rescue_incidents(model)
        _call_stage(model, "_sync_firefighter_marker_status")
        _call_stage(model, "_sync_victim_agent_status")
        _check_rescue_assignment_invariant(model)
        _call_stage(model, "_assert_no_direct_rescue_mutation")
        result["communication"] = _communication_summary(model)

        result["explanations"] = _collect_post_move_explanations(model, result)
        return result


def _call_stage(model: Any, method_name: str, *args: Any) -> Any:
    method = getattr(model, method_name, None)
    if callable(method):
        return method(*args)
    return None


def _collect_global_snapshot(model: Any, current_step_time: float) -> Any:
    monitor = getattr(model, "global_monitor", None)
    if monitor is None or not callable(getattr(monitor, "collect_global_snapshot", None)):
        return None
    snapshot = monitor.collect_global_snapshot(model, current_step_time)
    setattr(model, "latest_global_snapshot", snapshot)
    return snapshot


def _collect_post_move_monitoring_snapshots(model: Any, current_step_time: float) -> Any:
    collector = getattr(model, "_collect_post_move_monitoring_snapshots", None)
    if callable(collector):
        return collector(current_step_time)
    monitor = getattr(model, "global_monitor", None)
    if monitor is None or not callable(getattr(monitor, "collect_global_snapshot", None)):
        return None
    return monitor.collect_global_snapshot(model, current_step_time)


_TERMINAL_VICTIM_STATUSES = frozenset(
    {"rescued", "dead", "unreachable", "cancelled"}
)


def _check_rescue_assignment_invariant(model: Any) -> None:
    """Log firefighter/victim assignment divergence. Does not repair state."""
    step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
    victim_markers = getattr(model, "victim_marker_agents", None)
    ff_markers = getattr(model, "firefighter_marker_agents", None)
    if not isinstance(victim_markers, dict) or not isinstance(ff_markers, dict):
        return
    managed = getattr(model, "managed_victims", None)
    if not isinstance(managed, dict):
        managed = {}
    resolve = getattr(model, "_victim_id_from_agent", None)

    def _vid_from_rv(rv: Any) -> str:
        if rv is None:
            return ""
        if callable(resolve):
            return str(resolve(rv) or "").strip()
        return str(getattr(rv, "victim_id", "") or "").strip()

    def _ff_points_at_victim(ff_marker: Any) -> bool:
        if getattr(ff_marker, "dead", False):
            return False
        status = str(getattr(ff_marker, "status", "") or "").strip().lower()
        if status in ("dead", "route_blocked"):
            return False
        if not getattr(ff_marker, "assigned", False):
            return False
        return getattr(ff_marker, "rescued_victim", None) is not None

    def _victim_terminal(marker: Any, state: Any) -> bool:
        if marker is not None:
            mstatus = str(getattr(marker, "status", "") or "").strip().lower()
            if mstatus in _TERMINAL_VICTIM_STATUSES:
                return True
        if state is None:
            return False
        sstatus = str(getattr(state, "status", "") or "").strip().lower()
        if sstatus in _TERMINAL_VICTIM_STATUSES:
            return True
        return bool(
            getattr(state, "rescued", False)
            or getattr(state, "dead", False)
            or getattr(state, "cancelled", False)
            or getattr(state, "unreachable", False)
        )

    def _victim_marked_assigned(marker: Any, state: Any) -> bool:
        if _victim_terminal(marker, state):
            return False
        if marker is not None:
            if str(getattr(marker, "status", "") or "").strip().lower() == "assigned":
                return True
        if state is None:
            return False
        if getattr(state, "rescue_assigned", False):
            return True
        if str(getattr(state, "status", "") or "").strip().lower() == "assigned":
            return True
        return bool(getattr(state, "assigned", False))

    ff_to_victim: dict[str, str] = {}
    victim_to_ffs: dict[str, list[str]] = {}
    for ff_id, ff_marker in ff_markers.items():
        if not _ff_points_at_victim(ff_marker):
            continue
        vid = _vid_from_rv(getattr(ff_marker, "rescued_victim", None))
        ff_s = str(ff_id)
        if not vid:
            print(
                f"[RescueInvariant] step={step} firefighter={ff_s} "
                f"assigned but victim id missing",
                file=sys.stderr,
            )
            continue
        ff_to_victim[ff_s] = vid
        victim_to_ffs.setdefault(vid, []).append(ff_s)

    for vid, marker in victim_markers.items():
        vid_s = str(vid)
        state = managed.get(vid_s)
        if not _victim_marked_assigned(marker, state):
            continue
        ffs = victim_to_ffs.get(vid_s, [])
        if len(ffs) != 1:
            print(
                f"[RescueInvariant] step={step} victim={vid_s} "
                f"assigned but firefighters={ffs}",
                file=sys.stderr,
            )
        elif state is not None:
            back = str(getattr(state, "firefighter_id", "") or "").strip()
            if back and back != ffs[0]:
                print(
                    f"[RescueInvariant] step={step} victim={vid_s} "
                    f"assigned firefighter_id={back} but firefighter={ffs[0]}",
                    file=sys.stderr,
                )

    for ff_id, vid in ff_to_victim.items():
        marker = victim_markers.get(vid)
        state = managed.get(vid)
        if not _victim_marked_assigned(marker, state):
            print(
                f"[RescueInvariant] step={step} firefighter={ff_id} "
                f"assigned to {vid} but victim not marked assigned",
                file=sys.stderr,
            )
        elif state is not None:
            back = str(getattr(state, "firefighter_id", "") or "").strip()
            if back and back != ff_id:
                print(
                    f"[RescueInvariant] step={step} firefighter={ff_id} "
                    f"assigned to {vid} but victim firefighter_id={back}",
                    file=sys.stderr,
                )


def _process_rescue_incidents(model: Any) -> dict[str, Any]:
    queue = getattr(model, "_rescue_incident_queue", None)
    pending = list(queue) if isinstance(queue, list) else []
    _call_stage(model, "_process_rescue_incidents")
    return {
        "count": len(pending),
        "incidents": pending,
        "processed": len(pending) > 0,
    }


def _monitoring_summary(model: Any, snapshot: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "available": snapshot is not None,
        "timestamp": float(getattr(snapshot, "timestamp", 0.0) or 0.0) if snapshot else None,
        "observation_step": getattr(snapshot, "observation_step", None) if snapshot else None,
    }
    buffer = getattr(model, "monitoring_buffer", None)
    if buffer is not None:
        summary["local_observation_count"] = len(getattr(buffer, "local_observations", {}) or {})
    return summary


def _analysis_summary(model: Any) -> dict[str, Any]:
    snapshot = getattr(model, "latest_analysis_snapshot", None)
    if snapshot is None:
        return {"available": False}
    triggers = getattr(snapshot, "all_triggers", ()) or ()
    return {
        "available": True,
        "timestamp": float(getattr(snapshot, "timestamp", 0.0) or 0.0),
        "trigger_count": len(triggers),
        "dashboard_summary": str(getattr(snapshot, "dashboard_summary", "") or ""),
    }


def _adaptation_summary(model: Any) -> dict[str, Any]:
    snapshot = getattr(model, "latest_adaptation_space_snapshot", None)
    if snapshot is None:
        return {"available": False}
    options = getattr(snapshot, "all_options", None) or []
    explanation_summaries = list(getattr(snapshot, "explanation_summaries", ()) or ())
    return {
        "available": True,
        "timestamp": float(getattr(snapshot, "timestamp", 0.0) or 0.0),
        "option_count": len(options),
        "explanation_summaries": explanation_summaries,
        "dashboard_summary": str(getattr(snapshot, "dashboard_summary", "") or ""),
    }


def _planning_summary(model: Any) -> dict[str, Any]:
    planning_result = getattr(model, "latest_planning_result", None)
    if not isinstance(planning_result, dict):
        return {"available": False}
    communication_decision = planning_result.get("communication_decision")
    return {
        "available": True,
        "has_mission_decision": planning_result.get("mission_decision") is not None,
        "has_rescue_decision": planning_result.get("rescue_decision") is not None,
        "has_fail_safe_decision": planning_result.get("fail_safe_decision") is not None,
        "path_decision_count": len(planning_result.get("path_decisions") or {}),
        "has_communication_decision": isinstance(communication_decision, dict),
        "dashboard_summary": str(planning_result.get("dashboard_summary", "") or ""),
    }


def _execution_summary(model: Any) -> dict[str, Any]:
    execution_result = getattr(model, "latest_execution_result", None)
    if not isinstance(execution_result, dict):
        return {"available": False}
    return {
        "available": True,
        "applied": execution_result.get("applied"),
        "communication_applied": _nested_applied(execution_result, "communication"),
        "local_applied": _nested_applied(execution_result, "local"),
        "global_applied": _nested_applied(execution_result, "global"),
    }


def _nested_applied(execution_result: dict[str, Any], key: str) -> bool | None:
    section = execution_result.get(key)
    if isinstance(section, dict):
        applied = section.get("applied")
        return bool(applied) if applied is not None else None
    return None


def _failsafe_summary(model: Any) -> dict[str, Any]:
    state = getattr(model, "latest_failsafe_state", None)
    if state is None:
        return {"available": False}
    mode = getattr(state, "mode", None)
    mode_value = getattr(mode, "value", mode)
    return {
        "available": True,
        "mode": str(mode_value or ""),
        "explanation": str(getattr(state, "explanation", "") or ""),
        "dashboard_summary": str(getattr(model, "latest_failsafe_dashboard_summary", "") or ""),
    }


def _communication_summary(model: Any) -> dict[str, Any]:
    comm_execution = getattr(model, "latest_communication_execution", None)
    comm_model = getattr(model, "communication_model", None)
    mode = None
    if comm_model is not None:
        mode = getattr(comm_model, "communication_mode", None)
        if mode is None:
            state = getattr(comm_model, "state", None)
            mode = getattr(state, "communication_mode", None) if state is not None else None
    return {
        "available": comm_execution is not None or comm_model is not None,
        "execution": dict(comm_execution) if isinstance(comm_execution, dict) else comm_execution,
        "communication_mode": str(mode or ""),
    }


def _collect_explanations(model: Any, cycle_result: dict[str, Any]) -> list[str]:
    explanations: list[str] = []

    adaptation = cycle_result.get("adaptation")
    if isinstance(adaptation, dict):
        for item in adaptation.get("explanation_summaries") or []:
            text = str(item or "").strip()
            if text:
                explanations.append(text)

    failsafe = cycle_result.get("failsafe_mode")
    if isinstance(failsafe, dict):
        text = str(failsafe.get("explanation") or "").strip()
        if text:
            explanations.append(text)

    feedback = getattr(model, "latest_execution_feedback_event", None)
    if isinstance(feedback, dict):
        text = str(feedback.get("summary") or feedback.get("explanation") or "").strip()
        if text:
            explanations.append(text)

    return explanations


def _post_move_knowledge_summary(model: Any) -> dict[str, Any]:
    knowledge_manager = getattr(model, "knowledge_manager", None)
    shared_picture = getattr(model, "shared_operational_picture", None)
    global_snapshot = getattr(model, "latest_global_snapshot", None)
    return {
        "available": knowledge_manager is not None and shared_picture is not None,
        "global_snapshot_available": global_snapshot is not None,
        "environment_bridge_snapshot_available": getattr(
            model, "latest_environment_bridge_snapshot", None
        )
        is not None,
    }


def _collect_post_move_explanations(model: Any, cycle_result: dict[str, Any]) -> list[str]:
    explanations: list[str] = []
    cleanup = cycle_result.get("cleanup")
    if isinstance(cleanup, dict):
        removals = int(cleanup.get("pending_removals", 0) or 0)
        if removals > 0:
            explanations.append(f"pending_agent_removals={removals}")
        removal_failures = int(cleanup.get("pending_removal_failures", 0) or 0)
        if removal_failures > 0:
            explanations.append(f"pending_agent_removal_failures={removal_failures}")
    rescue_events = cycle_result.get("rescue_events")
    if isinstance(rescue_events, dict) and rescue_events.get("processed"):
        explanations.append(f"post_move_rescue_incidents={rescue_events.get('count', 0)}")
    rescue_sync = cycle_result.get("rescue_sync")
    if isinstance(rescue_sync, dict) and rescue_sync.get("processed"):
        explanations.append(f"post_casualty_rescue_incidents={rescue_sync.get('count', 0)}")
    return explanations
