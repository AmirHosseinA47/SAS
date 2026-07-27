"""Managing system: apply global mission decisions.

**Managing → managed:** applies MissionDecision to managed operational
coordination (e.g. role reconfiguration) via minimal hooks not global
analysis or planning here.
"""

from __future__ import annotations

from typing import Any

from ..planning.decision_objects import MissionDecision
from .execution_log import ExecutionLog, ExecutionResult


class GlobalExecutor:
    """Managing-side applier: mission decisions → managed operational updates."""

    def __init__(
        self,
        model: Any | None = None,
        execution_log: ExecutionLog | None = None,
    ) -> None:
        self._model = model
        self._execution_log = execution_log

    def execute(
        self,
        decision: MissionDecision | None,
        timestamp: float = 0.0,
    ) -> dict[str, object]:
        if decision is None:
            return {"applied": False, "reason": "no_decision"}

        model = self._model
        applied_roles: dict[str, str] = {}
        applied_tasks: dict[str, str] = {}
        pending_commands: list[dict[str, object]] = []

        if model is not None:
            resource_model = getattr(model, "uav_resource_model", None)
            managed_states = getattr(model, "managed_uav_states", None)

            confidence = float(decision.confidence_score or 0.8)
            for uav_id, role in decision.uav_assignments.items():
                if resource_model is not None:
                    update_role = getattr(resource_model, "update_role", None)
                    if callable(update_role):
                        self._call_update_role(
                            update_role,
                            uav_id,
                            role,
                            timestamp,
                            confidence,
                        )
                if isinstance(managed_states, dict) and uav_id in managed_states:
                    state = managed_states[uav_id]
                    if hasattr(state, "role"):
                        state.role = role
                applied_roles[uav_id] = role

            for uav_id, task in decision.task_assignments.items():
                if isinstance(managed_states, dict) and uav_id in managed_states:
                    state = managed_states[uav_id]
                    if hasattr(state, "assigned_task"):
                        state.assigned_task = task
                if resource_model is not None:
                    for method_name in (
                        "update_assigned_task",
                        "update_task",
                        "assign_task",
                    ):
                        method = getattr(resource_model, method_name, None)
                        if callable(method):
                            method(uav_id, task)
                            break
                applied_tasks[uav_id] = task

            sop = getattr(model, "shared_operational_picture", None)
            if sop is not None and decision.mission_mode and hasattr(sop, "mission_mode"):
                sop.mission_mode = decision.mission_mode

            pending: list[dict[str, object]] | None = getattr(
                model, "pending_global_commands", None
            )
            if pending is not None:
                for uav_id, relay_target in decision.relay_assignments.items():
                    cmd: dict[str, object] = {
                        "command_type": "relay_assignment",
                        "uav_id": uav_id,
                        "relay_target": relay_target,
                        "source_decision_id": decision.decision_id,
                        "timestamp": timestamp,
                    }
                    pending.append(cmd)
                    pending_commands.append(cmd)
                for uav_id in decision.recall_orders:
                    cmd = {
                        "command_type": "recall_order",
                        "uav_id": uav_id,
                        "source_decision_id": decision.decision_id,
                        "timestamp": timestamp,
                    }
                    pending.append(cmd)
                    pending_commands.append(cmd)

        if self._execution_log is not None:
            self._execution_log.add(
                ExecutionResult(
                    decision_id=decision.decision_id,
                    executor_type="global",
                    target_entity="mission",
                    action="apply_mission_decision",
                    status="success",
                    timestamp=timestamp,
                    intended_effect=decision.explanation or "mission/role/task update",
                    actual_result="applied",
                    feedback_event={
                        "assignments": dict(applied_roles),
                        "task_assignments": dict(applied_tasks),
                        "mission_mode": decision.mission_mode,
                        "pending_commands": list(pending_commands),
                    },
                    confidence_before=decision.confidence_score,
                    confidence_after=decision.confidence_score,
                    explanation=decision.explanation,
                )
            )

        return {
            "applied": True,
            "decision_id": decision.decision_id,
            "assignments": applied_roles,
            "task_assignments": applied_tasks,
            "mission_mode": decision.mission_mode,
            "pending_commands": pending_commands,
        }

    @staticmethod
    def _call_update_role(
        update_role: Any,
        uav_id: str,
        role: str,
        timestamp: float,
        confidence: float,
    ) -> None:
        try:
            update_role(
                uav_id,
                role,
                timestamp=timestamp,
                source="global_executor",
                confidence=confidence,
            )
        except TypeError:
            try:
                update_role(uav_id, role, timestamp)
            except TypeError:
                update_role(uav_id, role)
