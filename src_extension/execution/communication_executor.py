"""Managing system: apply communication directives to managed execution.

Managing → managed: updates abstract communication_model state, not real networking or transport.
"""

from __future__ import annotations

from typing import Any

from .execution_log import ExecutionLog, ExecutionResult

_MODE_ALIASES: dict[str, str] = {
    "normal": "normal",
    "maintain_normal_communication": "normal",
    "reduced_load": "reduced_load",
    "reduce_non_critical_communication": "reduced_load",
    "reduce_non_critical_load": "reduced_load",
    "rescue_priority": "rescue_priority",
    "prioritize_rescue_messages": "rescue_priority",
    "fail_safe_priority": "fail_safe_priority",
    "prioritize_failsafe_messages": "fail_safe_priority",
    "prioritize_emergency_messages": "fail_safe_priority",
    "degraded_communication": "degraded_communication",
    "apply_degraded_communication": "degraded_communication",
    "relay_support": "relay_support",
    "activate_relay_support": "relay_support",
    "activate_relay_uavs": "relay_support",
    "relay_send": "relay_support",
}


class CommunicationExecutor:
    """Managing-side applier: communication directives → managed comms state."""

    def __init__(
        self,
        model: Any | None = None,
        execution_log: ExecutionLog | None = None,
    ) -> None:
        self._model = model
        self._execution_log = execution_log

    def execute(
        self,
        command_or_decision: dict[str, object] | Any | None,
        timestamp: float = 0.0,
    ) -> dict[str, object]:
        if command_or_decision is None:
            return {
                "applied": False,
                "status": "failure",
                "reason": "no_command",
                "message_id": "",
                "priority": "normal",
            }

        fields = self._extract_fields(command_or_decision)
        message_id = str(fields["message_id"] or fields.get("decision_id") or "communication")
        priority = str(fields["priority"] or "normal")
        communication_action = str(fields["communication_action"])
        target_entity = str(fields["target_entity"] or "communication_system")
        decision_id = str(fields.get("decision_id") or message_id or "communication")
        explanation = str(fields.get("explanation") or "")
        resolved_mode = self._resolve_mode(fields, communication_action)

        status = self._delivery_status(communication_action)
        model_updates: dict[str, object] = {"communication_mode": resolved_mode}

        model = self._model
        if model is not None:
            comm_model = getattr(model, "communication_model", None)
            if comm_model is not None:
                model_updates = self._apply_communication_model(
                    comm_model,
                    communication_action,
                    fields,
                    status,
                    message_id,
                    target_entity,
                    timestamp,
                    resolved_mode=resolved_mode,
                    explanation=explanation,
                )

        if self._execution_log is not None:
            log_status = "delayed_effect" if status == "delayed" else status
            self._execution_log.add(
                ExecutionResult(
                    decision_id=decision_id,
                    executor_type="communication",
                    target_entity=target_entity or "communication",
                    action=communication_action or resolved_mode,
                    status=log_status,
                    timestamp=timestamp,
                    intended_effect=resolved_mode,
                    actual_result=status,
                    feedback_event={
                        "message_id": message_id,
                        "priority": priority,
                        "communication_mode": resolved_mode,
                        "model_updates": model_updates,
                    },
                    explanation=explanation,
                )
            )

        return {
            "applied": True,
            "status": status,
            "message_id": message_id,
            "priority": priority,
            "communication_action": communication_action,
            "communication_mode": resolved_mode,
            "target_entity": target_entity,
            "model_updates": model_updates,
            "explanation": explanation,
        }

    @staticmethod
    def _extract_fields(command_or_decision: dict[str, object] | Any) -> dict[str, object]:
        if isinstance(command_or_decision, dict):
            params = command_or_decision.get("parameters")
            param_dict = dict(params) if isinstance(params, dict) else {}
            return {
                "message_id": command_or_decision.get("message_id", ""),
                "priority": command_or_decision.get("priority", param_dict.get("priority", "normal")),
                "communication_action": command_or_decision.get(
                    "communication_action",
                    command_or_decision.get("action", param_dict.get("communication_action", "")),
                ),
                "target_entity": command_or_decision.get(
                    "target_entity", param_dict.get("target_entity", "")
                ),
                "decision_id": command_or_decision.get("decision_id", ""),
                "explanation": command_or_decision.get("explanation", ""),
                "communication_mode": command_or_decision.get(
                    "communication_mode", param_dict.get("communication_mode", "")
                ),
                "parameters": param_dict,
            }
        params = getattr(command_or_decision, "parameters", None)
        param_dict = dict(params) if isinstance(params, dict) else {}
        return {
            "message_id": getattr(command_or_decision, "message_id", ""),
            "priority": getattr(command_or_decision, "priority", param_dict.get("priority", "normal")),
            "communication_action": getattr(
                command_or_decision,
                "communication_action",
                getattr(command_or_decision, "action", param_dict.get("communication_action", "")),
            ),
            "target_entity": getattr(
                command_or_decision, "target_entity", param_dict.get("target_entity", "")
            ),
            "decision_id": getattr(command_or_decision, "decision_id", ""),
            "explanation": getattr(command_or_decision, "explanation", ""),
            "communication_mode": getattr(
                command_or_decision,
                "communication_mode",
                param_dict.get("communication_mode", ""),
            ),
            "parameters": param_dict,
        }

    @staticmethod
    def _resolve_mode(fields: dict[str, object], communication_action: str) -> str:
        for candidate in (
            fields.get("communication_mode"),
            communication_action,
        ):
            token = str(candidate or "").strip().lower()
            if token in _MODE_ALIASES:
                return _MODE_ALIASES[token]
            if token in {
                "normal",
                "reduced_load",
                "rescue_priority",
                "fail_safe_priority",
                "degraded_communication",
                "relay_support",
            }:
                return token
        action_lower = communication_action.strip().lower()
        for key, mode in _MODE_ALIASES.items():
            if key in action_lower:
                return mode
        return "normal"

    @staticmethod
    def _delivery_status(communication_action: str) -> str:
        action = communication_action.strip().lower()
        if not action:
            return "success"
        if "fail" in action:
            return "failure"
        if "delay" in action:
            return "delayed"
        return "success"

    @staticmethod
    def _apply_communication_model(
        comm_model: Any,
        communication_action: str,
        fields: dict[str, object],
        status: str,
        message_id: str,
        target_entity: str,
        timestamp: float,
        *,
        resolved_mode: str,
        explanation: str,
    ) -> dict[str, object]:
        updates: dict[str, object] = {"communication_mode": resolved_mode}
        action_lower = communication_action.strip().lower()
        params = fields.get("parameters")
        param_dict = dict(params) if isinstance(params, dict) else {}

        set_mode = getattr(comm_model, "set_communication_mode", None)
        if callable(set_mode):
            set_mode(
                resolved_mode,
                timestamp=timestamp,
                source="communication_executor",
                reason=explanation or communication_action or resolved_mode,
            )
        elif hasattr(comm_model, "communication_mode"):
            comm_model.communication_mode = resolved_mode
            updates["communication_mode"] = resolved_mode

        if resolved_mode in {"relay_support", "degraded_communication"} or "relay" in action_lower:
            if hasattr(comm_model, "relay_needed"):
                comm_model.relay_needed = True
                updates["relay_needed"] = True
            mark_relay = getattr(comm_model, "mark_relay_needed", None)
            if callable(mark_relay):
                mark_relay(True, timestamp=timestamp, source="communication_executor")

        if resolved_mode in {"reduced_load", "degraded_communication"}:
            updates["reduce_non_critical_load"] = True

        if resolved_mode in {"rescue_priority", "fail_safe_priority"}:
            updates["prioritize_critical_messages"] = True

        result_methods: dict[str, tuple[str, ...]] = {
            "success": ("record_sent", "add_sent_result", "mark_sent"),
            "failure": ("record_failure", "add_failed_result", "mark_failed"),
            "delayed": ("record_delayed", "add_delayed_result", "mark_delayed"),
        }
        for method_name in result_methods.get(status, ()):
            method = getattr(comm_model, method_name, None)
            if not callable(method):
                continue
            try:
                method(
                    message_id=message_id,
                    target_entity=target_entity,
                    timestamp=timestamp,
                    action=communication_action,
                )
            except TypeError:
                try:
                    method(message_id, target_entity, status)
                except TypeError:
                    method(message_id)
            updates[method_name] = True
            break

        if param_dict:
            updates["parameters_applied"] = param_dict
        return updates
