"""Managing system: route decisions to executors.

Managing system: orchestrates execution order—fail-safe, global mission,
local paths, rescue, then pending communication commands.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..planning.decision_objects import (
    FailSafeDecision,
    MissionDecision,
    PathDecision,
    RescueDecision,
)
from .communication_executor import CommunicationExecutor
from .execution_log import ExecutionLog
from .failsafe_modes import FailSafeMode
from .global_executor import GlobalExecutor
from .rescue_executor import RescueExecutor
from .uav_executor import UAVExecutor

_NO_OVERRIDE_FAIL_SAFE_ACTIONS = frozenset(
    {
        "",
        "maintain_current_config",
        "maintain_current_failsafe_state",
        "do_nothing",
        "none",
    }
)
_REAL_OVERRIDE_FAIL_SAFE_ACTIONS = frozenset(
    {
        "search_mode",
        "activate_search_mode",
        "information_recovery",
        "safe_hold",
        "return_to_base",
        "suspend_non_critical_tasks",
        "critical_tasks_only",
        "collision_avoidance_override",
    }
)
_OVERRIDE_FAIL_SAFE_ACTIONS = _REAL_OVERRIDE_FAIL_SAFE_ACTIONS
_SEARCH_FAIL_SAFE_ACTIONS = frozenset(
    {
        "search_mode",
        "activate_search_mode",
        "information_recovery",
        "move_to_last_known_fire_region",
        "explore_high_uncertainty_regions",
    }
)


class DecisionDispatcher:
    """Managing-side switchboard: planning results → executor applications."""

    def __init__(
        self,
        model: Any | None = None,
        execution_log: ExecutionLog | None = None,
    ) -> None:
        self._model = model
        self._execution_log = execution_log
        self._global = GlobalExecutor(model=model, execution_log=execution_log)
        self._rescue = RescueExecutor(model=model, execution_log=execution_log)
        self._communication = CommunicationExecutor(model=model, execution_log=execution_log)
        self._uav_executors: dict[str, UAVExecutor] = {}

    @property
    def rescue_executor(self) -> RescueExecutor:
        """Shared rescue executor for MAPE dispatch and physical rescue bridge."""
        return self._rescue

    def dispatch(
        self,
        planning_result: dict[str, object] | Any | None,
        timestamp: float = 0.0,
    ) -> dict[str, object]:
        fail_safe_decision, mission_decision, path_decisions, rescue_decision = (
            self._extract_decisions(planning_result)
        )

        fail_safe_override_active, override_reason = _resolve_fail_safe_override(
            fail_safe_decision
        )

        if fail_safe_override_active and self._model is not None:
            try:
                _fs_state = getattr(self._model, "latest_failsafe_state", None)
                if _fs_state is not None:
                    _fs_mode = getattr(_fs_state, "mode", None)
                    _fs_mode_val = (
                        _fs_mode.value if hasattr(_fs_mode, "value") else str(_fs_mode or "")
                    )
                    if str(_fs_mode_val).lower() == "normal":
                        fail_safe_override_active = False
                        override_reason = ""
            except Exception:
                pass

        fail_safe_result = self._dispatch_fail_safe(fail_safe_decision, timestamp)
        if fail_safe_override_active and _should_skip_global_execution(fail_safe_decision):
            global_result = {
                "applied": False,
                "reason": "emergency_suspend_non_critical_tasks",
                "skipped": True,
            }
        else:
            global_result = self._global.execute(mission_decision, timestamp)
        local_result = self._dispatch_local_paths(
            path_decisions,
            timestamp,
            fail_safe_decision,
            fail_safe_override_active=fail_safe_override_active,
            override_reason=override_reason,
        )
        rescue_result = self._rescue.execute(rescue_decision, timestamp)
        communication_result = self._dispatch_communication(
            planning_result,
            timestamp,
            fail_safe_decision=fail_safe_decision,
            rescue_decision=rescue_decision,
        )

        return {
            "fail_safe": fail_safe_result,
            "global": global_result,
            "local": local_result,
            "rescue": rescue_result,
            "communication": communication_result,
            "fail_safe_override_active": fail_safe_override_active,
            "override_reason": override_reason,
        }

    def _get_uav_executor(self, uav_id: str) -> UAVExecutor:
        if uav_id not in self._uav_executors:
            self._uav_executors[uav_id] = UAVExecutor(
                uav_id,
                model=self._model,
                execution_log=self._execution_log,
            )
        return self._uav_executors[uav_id]

    @staticmethod
    def _extract_decisions(
        planning_result: dict[str, object] | Any | None,
    ) -> tuple[
        FailSafeDecision | None,
        MissionDecision | None,
        list[PathDecision],
        RescueDecision | None,
    ]:
        if planning_result is None:
            return None, None, [], None
        if isinstance(planning_result, dict):
            fail_safe = planning_result.get("fail_safe_decision")
            mission = planning_result.get("mission_decision")
            paths = planning_result.get("path_decisions", [])
            rescue = planning_result.get("rescue_decision")
        else:
            fail_safe = getattr(planning_result, "fail_safe_decision", None)
            mission = getattr(planning_result, "mission_decision", None)
            paths = getattr(planning_result, "path_decisions", [])
            rescue = getattr(planning_result, "rescue_decision", None)
        return (
            fail_safe if isinstance(fail_safe, FailSafeDecision) else None,
            mission if isinstance(mission, MissionDecision) else None,
            DecisionDispatcher._normalize_path_decisions(paths),
            rescue if isinstance(rescue, RescueDecision) else None,
        )

    @staticmethod
    def _normalize_path_decisions(
        path_decisions: object,
    ) -> list[PathDecision]:
        if path_decisions is None:
            return []
        if isinstance(path_decisions, PathDecision):
            return [path_decisions]
        if isinstance(path_decisions, dict):
            items = list(path_decisions.values())
        elif isinstance(path_decisions, (list, tuple)):
            items = list(path_decisions)
        else:
            return []
        return [item for item in items if isinstance(item, PathDecision)]

    def _dispatch_fail_safe(
        self,
        decision: FailSafeDecision | None,
        timestamp: float,
    ) -> dict[str, object]:
        if decision is None:
            return {"applied": False, "reason": "no_decision"}

        model = self._model
        if model is not None and decision.mission_mode:
            sop = getattr(model, "shared_operational_picture", None)
            if sop is not None and hasattr(sop, "mission_mode"):
                sop.mission_mode = decision.mission_mode

        uav_results: dict[str, object] = {}
        for action in decision.actions:
            if not isinstance(action, dict):
                continue
            uav_id = str(action.get("uav_id", action.get("target_entity", "")))
            if not uav_id:
                continue
            path_decision = PathDecision(
                decision_id=decision.decision_id,
                uav_id=uav_id,
                next_action=str(action.get("next_action", action.get("action", ""))),
            )
            uav_results[uav_id] = self._get_uav_executor(uav_id).execute(
                path_decision,
                timestamp,
                fail_safe_decision=decision,
            )

        return {
            "applied": True,
            "decision_id": decision.decision_id,
            "fail_safe_action": decision.fail_safe_action,
            "uav_results": uav_results,
        }

    def _dispatch_local_paths(
        self,
        path_decisions: list[PathDecision],
        timestamp: float,
        fail_safe_decision: FailSafeDecision | None,
        *,
        fail_safe_override_active: bool = False,
        override_reason: str = "",
    ) -> dict[str, object]:
        if not path_decisions:
            return {
                "applied": False,
                "reason": "no_path_decisions",
                "uav_results": {},
                "fail_safe_override_active": fail_safe_override_active,
                "override_reason": override_reason,
            }

        uav_results: dict[str, object] = {}
        for decision in path_decisions:
            uav_id = decision.uav_id or decision.selected_option_id
            if not uav_id:
                continue
            if _is_victim_search_mode_exempt(
                uav_id,
                self._model,
                fail_safe_decision,
                fail_safe_override_active,
            ):
                result = dict(
                    self._get_uav_executor(uav_id).execute(
                        decision,
                        timestamp,
                        fail_safe_decision=None,
                    )
                )
                result["override_exempt"] = True
                result["override_exempt_reason"] = "victim_searcher_role"
                uav_results[uav_id] = result
                continue
            path_to_execute, execute_path = _adjust_local_path_for_fail_safe(
                decision,
                fail_safe_decision,
                fail_safe_override_active,
            )
            if not execute_path or path_to_execute is None:
                uav_results[uav_id] = {
                    "applied": False,
                    "reason": "fail_safe_override",
                    "override_reason": override_reason,
                    "fail_safe_action": (
                        fail_safe_decision.fail_safe_action if fail_safe_decision else ""
                    ),
                }
                continue
            fs_for_execute = (
                _fail_safe_decision_for_execute(
                    fail_safe_decision,
                    fail_safe_override_active,
                )
                if fail_safe_override_active
                else None
            )
            uav_results[uav_id] = self._get_uav_executor(uav_id).execute(
                path_to_execute,
                timestamp,
                fail_safe_decision=fs_for_execute,
            )
        return {
            "applied": bool(uav_results),
            "uav_results": uav_results,
            "fail_safe_override_active": fail_safe_override_active,
            "override_reason": override_reason,
        }

    def _dispatch_communication(
        self,
        planning_result: dict[str, object] | Any | None,
        timestamp: float,
        *,
        fail_safe_decision: FailSafeDecision | None = None,
        rescue_decision: RescueDecision | None = None,
    ) -> dict[str, object]:
        model = self._model
        results: list[dict[str, object]] = []
        selected_mode = ""
        selected_explanation = ""

        communication_decision = _extract_communication_decision(planning_result)
        if communication_decision is not None:
            result = self._communication.execute(communication_decision, timestamp)
            results.append(result)
            selected_mode = str(result.get("communication_mode") or "")
            selected_explanation = str(
                communication_decision.get("explanation", "")
                if isinstance(communication_decision, dict)
                else getattr(communication_decision, "explanation", "")
            )

        pending = getattr(model, "pending_global_commands", None) if model is not None else None
        consumed_indices: list[int] = []
        if pending:
            for index, cmd in enumerate(list(pending)):
                if not isinstance(cmd, dict):
                    continue
                if not self._is_communication_command(cmd):
                    continue
                results.append(self._communication.execute(cmd, timestamp))
                consumed_indices.append(index)
            if consumed_indices and isinstance(pending, list):
                for offset, index in enumerate(consumed_indices):
                    pending.pop(index - offset)

        if model is not None:
            latest = getattr(model, "latest_communication_execution", None)
            if not isinstance(latest, dict):
                latest = {}
            latest.update(
                {
                    "timestamp": timestamp,
                    "applied": bool(results),
                    "results": results,
                    "communication_mode": selected_mode
                    or _communication_mode_from_model(model),
                    "explanation": selected_explanation,
                    "pending_commands_remaining": len(getattr(model, "pending_global_commands", []) or []),
                }
            )
            model.latest_communication_execution = latest

        if not results:
            return {"applied": False, "reason": "no_communication_decision", "results": []}
        return {
            "applied": True,
            "results": results,
            "communication_mode": selected_mode or _communication_mode_from_model(model),
            "explanation": selected_explanation,
        }

    @staticmethod
    def _is_communication_command(command: dict[str, object]) -> bool:
        command_type = str(command.get("command_type", "")).lower()
        if "comm" in command_type or command_type in {"message", "send_message"}:
            return True
        return "communication_action" in command


def _get_uav_role(uav_id: str, model: object | None) -> str:
    if model is None:
        return ""
    uav_key = str(uav_id)
    resource_model = getattr(model, "uav_resource_model", None)
    if resource_model is not None:
        by_uav_id = getattr(resource_model, "by_uav_id", None)
        if isinstance(by_uav_id, dict) and uav_key in by_uav_id:
            state = by_uav_id[uav_key]
            role = getattr(state, "current_role", None)
            if role is None and isinstance(state, dict):
                role = state.get("current_role", state.get("role"))
            if role is not None:
                return str(role)
    managed_states = getattr(model, "managed_uav_states", None)
    if isinstance(managed_states, dict) and uav_key in managed_states:
        state = managed_states[uav_key]
        role = getattr(state, "role", None)
        if role is None and isinstance(state, dict):
            role = state.get("role")
        if role is not None:
            return str(role)
    return ""


def _is_victim_search_mode_exempt(
    uav_id: str,
    model: object | None,
    fail_safe_decision: FailSafeDecision | None,
    fail_safe_override_active: bool,
) -> bool:
    if not fail_safe_override_active or fail_safe_decision is None:
        return False
    role = _get_uav_role(uav_id, model)
    if role not in {"victim_searcher", "victim_search"}:
        return False
    if not fail_safe_decision.search_mode_active:
        return False
    mode = _fail_safe_mode(fail_safe_decision)
    action = _normalize_fail_safe_token(fail_safe_decision.fail_safe_action)
    if mode in {FailSafeMode.EMERGENCY.value, FailSafeMode.SAFETY_FIRST.value}:
        return False
    if action in {"safe_hold", "return_to_base"}:
        return False
    if "safe_hold" in action or "return_to_base" in action:
        return False
    return True


def _resolve_fail_safe_override(
    decision: FailSafeDecision | None,
) -> tuple[bool, str]:
    if decision is None:
        return False, ""

    mission_mode = _normalize_fail_safe_token(decision.mission_mode)
    action = _normalize_fail_safe_token(decision.fail_safe_action)
    if (
        mission_mode in {"", "normal"}
        and not decision.search_mode_active
        and action in _NO_OVERRIDE_FAIL_SAFE_ACTIONS
    ):
        return False, ""

    reasons: list[str] = []
    mode = _fail_safe_mode(decision)

    if mode == FailSafeMode.EMERGENCY.value:
        reasons.append("emergency_mode")
    if mode == FailSafeMode.SAFETY_FIRST.value:
        reasons.append("safety_first_mode")
    if mode == FailSafeMode.INFORMATION_RECOVERY.value:
        if mission_mode in {"information_recovery", "search"}:
            reasons.append("information_recovery_mode")
    if decision.search_mode_active:
        if mission_mode in {
            "search",
            "information_recovery",
            "emergency",
            "safety_first",
            "degraded",
        }:
            reasons.append("search_mode_active")
    if action in _REAL_OVERRIDE_FAIL_SAFE_ACTIONS:
        reasons.append(f"fail_safe_action:{action or decision.fail_safe_action}")
    elif action:
        for token in _REAL_OVERRIDE_FAIL_SAFE_ACTIONS:
            if token in action and action not in _NO_OVERRIDE_FAIL_SAFE_ACTIONS:
                reasons.append(f"fail_safe_action:{action or decision.fail_safe_action}")
                break

    if not reasons:
        return False, ""
    return True, "; ".join(reasons)


def _should_skip_global_execution(decision: FailSafeDecision | None) -> bool:
    if decision is None:
        return False
    if _fail_safe_mode(decision) != FailSafeMode.EMERGENCY.value:
        return False
    action = _normalize_fail_safe_token(decision.fail_safe_action)
    return action == "suspend_non_critical_tasks" or "suspend_non_critical" in action


def _adjust_local_path_for_fail_safe(
    path: PathDecision,
    fail_safe_decision: FailSafeDecision | None,
    override_active: bool,
) -> tuple[PathDecision | None, bool]:
    if not override_active or fail_safe_decision is None:
        return path, True

    action = _normalize_fail_safe_token(fail_safe_decision.fail_safe_action)
    mode = _fail_safe_mode(fail_safe_decision)

    if mode in {FailSafeMode.EMERGENCY.value, FailSafeMode.SAFETY_FIRST.value}:
        if action == "safe_hold" or action.endswith("_hold") or action == "hold":
            return replace(path, next_action="hold"), True
        if action == "return_to_base" or "return_to_base" in action:
            if _path_consistent_with_return_to_base(path):
                return path, True
            return None, False

    if action == "safe_hold" or action.endswith("_hold") or action == "hold":
        return replace(path, next_action="hold"), True

    if action == "return_to_base" or "return_to_base" in action:
        if _path_consistent_with_return_to_base(path):
            return path, True
        return None, False

    if fail_safe_decision.search_mode_active or action in _SEARCH_FAIL_SAFE_ACTIONS:
        return path, True

    if action in _OVERRIDE_FAIL_SAFE_ACTIONS:
        return path, True

    return path, True


def _fail_safe_decision_for_execute(
    fail_safe_decision: FailSafeDecision | None,
    fail_safe_override_active: bool,
) -> FailSafeDecision | None:
    if not fail_safe_override_active:
        return None
    if fail_safe_decision is None:
        return None
    mode = _fail_safe_mode(fail_safe_decision)
    action = _normalize_fail_safe_token(fail_safe_decision.fail_safe_action)
    if mode in {FailSafeMode.EMERGENCY.value, FailSafeMode.SAFETY_FIRST.value}:
        return None
    if action in {"safe_hold", "return_to_base"}:
        return None
    if "safe_hold" in action or "return_to_base" in action:
        return None
    return fail_safe_decision


def _path_consistent_with_return_to_base(path: PathDecision) -> bool:
    markers = ("return", "base", "home", "rtb")
    parts = (
        path.next_action,
        path.selected_option_id,
        str(path.path_segment),
        str(path.waypoints_by_uav),
    )
    text = " ".join(str(part).lower() for part in parts)
    return any(marker in text for marker in markers)


def _fail_safe_mode(decision: FailSafeDecision) -> str:
    return _normalize_fail_safe_token(str(decision.mission_mode or ""))


def _normalize_fail_safe_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _extract_communication_decision(
    planning_result: dict[str, object] | Any | None,
) -> dict[str, object] | None:
    if planning_result is None:
        return None
    if isinstance(planning_result, dict):
        decision = planning_result.get("communication_decision")
    else:
        decision = getattr(planning_result, "communication_decision", None)
    if decision is None:
        return None
    if isinstance(decision, dict):
        return dict(decision)
    return {
        "decision_id": getattr(decision, "decision_id", "communication"),
        "communication_mode": getattr(decision, "communication_mode", "normal"),
        "communication_action": getattr(decision, "communication_action", ""),
        "target_entity": getattr(decision, "target_entity", "communication_system"),
        "message_id": getattr(decision, "message_id", getattr(decision, "decision_id", "")),
        "priority": getattr(decision, "priority", "normal"),
        "explanation": getattr(decision, "explanation", ""),
        "parameters": dict(getattr(decision, "parameters", {}) or {}),
    }


def _communication_mode_from_model(model: object | None) -> str:
    if model is None:
        return ""
    comm_model = getattr(model, "communication_model", None)
    if comm_model is None:
        return ""
    mode = getattr(comm_model, "communication_mode", None)
    if mode is not None:
        return str(mode)
    state = getattr(comm_model, "state", None)
    if state is not None:
        return str(getattr(state, "communication_mode", "") or "")
    return ""
