"""Managing system: apply rescue decisions to managed operational state.

Managing → managed: applies RescueDecision by updating managed
abstract firefighter/victim state, not physical movement or UAV paths.
"""

from __future__ import annotations

import sys
from typing import Any

from ..planning.decision_objects import RescueDecision
from ..planning.rescue_planner import select_rescue_assignment
from .execution_log import ExecutionLog, ExecutionResult

_GENERIC_VICTIM_IDS = frozenset({"", "mission", "rescue_target"})


class RescueExecutor:
    """Managing-side applier: rescue coordination decisions → managed ops updates."""

    def __init__(
        self,
        model: Any | None = None,
        execution_log: ExecutionLog | None = None,
    ) -> None:
        self._model = model
        self._execution_log = execution_log

    def execute(
        self,
        decision: RescueDecision | None,
        timestamp: float = 0.0,
    ) -> dict[str, object]:
        if decision is None:
            return {"applied": False, "reason": "no_decision"}

        model = self._model
        action_kind = self._classify_rescue_action(decision.rescue_action)
        victim_updates: dict[str, object] = {}
        firefighter_updates: dict[str, object] = {}
        runtime_updates: dict[str, object] = {}

        if action_kind == "delay":
            pairing = self._active_physical_pairing(
                model, decision.victim_id, decision.firefighter_id
            )
            step = 0
            if model is not None:
                step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
            if pairing is not None:
                pair_ff, pair_vid = pairing
                print(
                    f"[RescueDelayRefused] step={step} "
                    f"victim={pair_vid or decision.victim_id or ''} "
                    f"firefighter={pair_ff or decision.firefighter_id or ''} "
                    f"reason=delay_refused_active_physical_pairing",
                    file=sys.stderr,
                )
                refused_payload: dict[str, object] = {
                    **dict(decision.payload),
                    "rescue_action": decision.rescue_action,
                    "victim_id": decision.victim_id,
                    "firefighter_id": decision.firefighter_id,
                    "route_choice": decision.route_choice,
                    "refused_reason": "delay_refused_active_physical_pairing",
                    "active_firefighter_id": pair_ff,
                    "active_victim_id": pair_vid,
                }
                if self._execution_log is not None:
                    self._execution_log.add(
                        ExecutionResult(
                            decision_id=decision.decision_id,
                            executor_type="rescue",
                            target_entity=decision.victim_id or "rescue",
                            action=decision.rescue_action or "delay",
                            status="failure",
                            timestamp=timestamp,
                            intended_effect=decision.explanation or decision.rescue_action,
                            actual_result="delay_refused_active_physical_pairing",
                            feedback_event=refused_payload,
                            confidence_before=decision.confidence_score,
                            confidence_after=decision.confidence_score,
                            explanation=decision.explanation,
                        )
                    )
                return {
                    "applied": False,
                    "reason": "delay_refused_active_physical_pairing",
                    "decision_id": decision.decision_id,
                    "payload": refused_payload,
                }

        if model is not None and decision.victim_id:
            managed_victims = getattr(model, "managed_victims", None)
            if isinstance(managed_victims, dict) and decision.victim_id in managed_victims:
                victim = managed_victims[decision.victim_id]
                victim_updates = self._apply_victim_state(
                    victim,
                    action_kind,
                    decision.firefighter_id,
                    decision.route_choice,
                )

            firefighter_model = getattr(model, "firefighter_model", None)
            if firefighter_model is not None and decision.firefighter_id:
                firefighter_updates = self._apply_firefighter_model(
                    firefighter_model,
                    decision.firefighter_id,
                    decision.victim_id,
                    action_kind,
                    decision.payload,
                )

            victim_runtime = getattr(model, "victim_runtime_model", None)
            if victim_runtime is not None and decision.victim_id:
                runtime_updates = self._apply_victim_runtime(
                    victim_runtime,
                    decision.victim_id,
                    action_kind,
                    decision.firefighter_id,
                    decision.route_choice,
                    decision.payload,
                )

        result_payload: dict[str, object] = {
            **dict(decision.payload),
            "rescue_action": decision.rescue_action,
            "victim_id": decision.victim_id,
            "firefighter_id": decision.firefighter_id,
            "route_choice": decision.route_choice,
            "victim_updates": victim_updates,
            "firefighter_updates": firefighter_updates,
            "runtime_updates": runtime_updates,
        }

        if self._execution_log is not None:
            self._execution_log.add(
                ExecutionResult(
                    decision_id=decision.decision_id,
                    executor_type="rescue",
                    target_entity=decision.victim_id or "rescue",
                    action=decision.rescue_action or "apply_rescue_decision",
                    status="success",
                    timestamp=timestamp,
                    intended_effect=decision.explanation or decision.rescue_action,
                    actual_result="applied",
                    feedback_event=result_payload,
                    confidence_before=decision.confidence_score,
                    confidence_after=decision.confidence_score,
                    explanation=decision.explanation,
                )
            )

        return {
            "applied": True,
            "decision_id": decision.decision_id,
            "payload": result_payload,
        }

    def execute_physical_dispatch(
        self,
        model: Any,
        victim_id: str,
        victim_marker: Any,
        reason: str,
        preferred_firefighter_id: str | None = None,
    ) -> dict[str, object]:
        """Plan pairing via RescuePlanner snapshot, then apply physical command."""
        vid = str(victim_id or "").strip()
        reason_s = str(reason or "")
        empty_result: dict[str, object] = {
            "success": False,
            "victim_id": vid,
            "firefighter_id": None,
            "reason": reason_s,
            "event_type": "",
            "message": "invalid_request",
        }
        if not vid or victim_marker is None:
            return empty_result

        snapshot_fn = getattr(model, "get_rescue_operational_snapshot", None)
        if not callable(snapshot_fn):
            return {**empty_result, "message": "no_rescue_snapshot"}
        snapshot = snapshot_fn()
        decision = select_rescue_assignment(snapshot, reason_s, victim_id=vid)
        if preferred_firefighter_id and isinstance(decision, RescueDecision):
            if str(decision.rescue_action or "").strip().lower() == "assign":
                decision = RescueDecision(
                    decision_id=decision.decision_id,
                    selected_option_id=decision.selected_option_id,
                    rescue_action=decision.rescue_action,
                    victim_id=decision.victim_id,
                    firefighter_id=str(preferred_firefighter_id),
                    route_choice=decision.route_choice,
                    payload=dict(decision.payload),
                    confidence_score=decision.confidence_score,
                    uncertainty_context=dict(decision.uncertainty_context),
                    comparison_summary=dict(decision.comparison_summary),
                    explanation=decision.explanation,
                )
        return self.apply_physical_pairing_decision(
            model, decision, victim_marker=victim_marker
        )

    def execute_physical_command(
        self,
        model: Any,
        command: Any,
    ) -> dict[str, object]:
        """Validate and apply a physical rescue command (sole runtime mutation path)."""
        from wildfire_model import PhysicalRescueCommand

        if not isinstance(command, PhysicalRescueCommand):
            return {
                "success": False,
                "action": "",
                "victim_id": "",
                "firefighter_id": None,
                "reason": "",
                "event_type": "",
                "message": "invalid_command_type",
            }

        action = str(command.action or "").strip().lower()
        vid = str(command.victim_id or "").strip()
        ff_raw = command.firefighter_id
        ff_id = str(ff_raw or "").strip() if ff_raw else None
        reason = str(command.reason or "")
        allowed = frozenset({"assign", "unassign", "mark_unreachable", "finalize_rescue"})
        empty: dict[str, object] = {
            "success": False,
            "action": action,
            "victim_id": vid,
            "firefighter_id": ff_id,
            "reason": reason,
            "event_type": "",
            "message": "invalid_action",
        }
        if action not in allowed:
            return empty
        if action in ("assign", "mark_unreachable", "finalize_rescue") and not vid:
            return {**empty, "message": "missing_victim_id"}
        if action in ("assign", "unassign") and not ff_id:
            return {**empty, "message": "missing_firefighter_id"}

        apply_cmd = getattr(model, "apply_physical_rescue_command", None)
        if not callable(apply_cmd):
            return {**empty, "message": "no_physical_command_api"}

        setattr(model, "_physical_rescue_command_via_executor", True)
        try:
            applied = bool(apply_cmd(command))
        finally:
            setattr(model, "_physical_rescue_command_via_executor", False)

        audit = getattr(model, "_physical_rescue_command_audit", None)
        if not isinstance(audit, list):
            model._physical_rescue_command_audit = []
            audit = model._physical_rescue_command_audit
        audit.append(
            {
                "action": action,
                "victim_id": vid,
                "firefighter_id": ff_id,
                "reason": reason,
                "success": applied,
            }
        )

        event_type = ""
        if action == "assign":
            event_type_fn = getattr(model, "_physical_rescue_event_type_from_reason", None)
            event_type = (
                event_type_fn(reason) if callable(event_type_fn) else "dispatch_initial"
            )
        elif action == "mark_unreachable":
            event_type = "rescue_failed"
        elif action == "finalize_rescue":
            event_type = "rescue_complete"
        elif action == "unassign":
            event_type = "physical_unassign"

        timestamp = float(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        if applied and action in allowed:
            self.record_physical_event(
                event_type=event_type or f"physical_{action}",
                victim_id=vid,
                firefighter_id=ff_id or "",
                reason=reason,
                timestamp=timestamp,
                metadata=dict(command.metadata or {}),
            )

        message = f"{action}_applied" if applied else f"{action}_failed"
        return {
            "success": applied,
            "action": action,
            "victim_id": vid,
            "firefighter_id": ff_id,
            "reason": reason,
            "event_type": event_type,
            "message": message,
        }

    def apply_physical_pairing_decision(
        self,
        model: Any,
        decision: RescueDecision | dict[str, Any],
        *,
        victim_marker: Any | None = None,
    ) -> dict[str, object]:
        """Apply planner pairing decision through the physical command API."""
        from wildfire_model import PhysicalRescueCommand

        if isinstance(decision, dict):
            action = str(decision.get("action", "") or "").strip().lower()
            vid = str(decision.get("victim_id", "") or "")
            ff_id = str(decision.get("firefighter_id", "") or "") or None
            reason = str(decision.get("reason", "") or "")
        else:
            action = str(decision.rescue_action or "").strip().lower()
            vid = str(decision.victim_id or "")
            ff_id = str(decision.firefighter_id or "").strip() or None
            payload = dict(decision.payload or {})
            reason = str(payload.get("reason", "") or decision.explanation or "")

        reason_s = str(reason or "")
        empty_result: dict[str, object] = {
            "success": False,
            "victim_id": vid,
            "firefighter_id": ff_id,
            "reason": reason_s,
            "event_type": "",
            "message": "no_action",
        }
        if action in ("", "none"):
            return empty_result

        if victim_marker is None and vid:
            markers = getattr(model, "victim_marker_agents", None)
            if isinstance(markers, dict):
                victim_marker = markers.get(vid)

        if action == "delay":
            return {**empty_result, "message": "delayed"}

        if action == "mark_unreachable":
            cmd_result = self.execute_physical_command(
                model,
                PhysicalRescueCommand(
                    action="mark_unreachable",
                    victim_id=vid,
                    firefighter_id=None,
                    reason=reason_s or "no_available_firefighter",
                    metadata={"victim_marker": victim_marker},
                ),
            )
            applied = bool(cmd_result.get("success"))
            if applied and vid:
                failed_logged = getattr(model, "_rescue_failed_logged", None)
                if isinstance(failed_logged, set):
                    failed_logged.add(vid)
            return {
                "success": applied,
                "victim_id": vid,
                "firefighter_id": None,
                "reason": reason_s,
                "event_type": "rescue_failed",
                "message": "marked_unreachable" if applied else "mark_unreachable_failed",
            }

        if action != "assign":
            return {**empty_result, "message": f"unsupported_action:{action}"}

        if not vid or not ff_id or victim_marker is None:
            return {**empty_result, "message": "invalid_assign_request"}

        needs_rescue = getattr(model, "_victim_needs_rescue", None)
        if callable(needs_rescue) and not needs_rescue(vid, victim_marker):
            return {**empty_result, "message": "victim_does_not_need_rescue"}

        find_active = getattr(model, "_find_active_firefighter_for_victim", None)
        if callable(find_active) and find_active(vid, victim_marker) is not None:
            return {**empty_result, "message": "already_assigned"}

        victim_pos = getattr(victim_marker, "pos", None)
        if victim_pos is None:
            return {**empty_result, "message": "victim_has_no_position"}
        victim_cell = (int(victim_pos[0]), int(victim_pos[1]))

        ff_markers = getattr(model, "firefighter_marker_agents", None)
        ff_marker = (
            ff_markers.get(ff_id) if isinstance(ff_markers, dict) else None
        )
        if ff_marker is None:
            return {**empty_result, "message": "no_firefighter_marker"}

        cmd_result = self.execute_physical_command(
            model,
            PhysicalRescueCommand(
                action="assign",
                victim_id=vid,
                firefighter_id=ff_id,
                reason=reason_s,
                metadata={
                    "victim_marker": victim_marker,
                    "target_pos": victim_cell,
                },
            ),
        )
        applied = bool(cmd_result.get("success"))
        event_type = str(cmd_result.get("event_type", "") or "")
        if applied:
            return {
                "success": True,
                "victim_id": vid,
                "firefighter_id": ff_id,
                "reason": reason_s,
                "event_type": event_type,
                "message": "dispatched",
            }
        return {
            **empty_result,
            "firefighter_id": ff_id,
            "message": "apply_command_failed",
        }

    def record_physical_event(
        self,
        *,
        event_type: str,
        victim_id: str,
        firefighter_id: str,
        reason: str,
        timestamp: float,
        victim_pos: tuple[int, int] | None = None,
        firefighter_pos: tuple[int, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a physical rescue bridge event without mutating managed state."""
        if self._execution_log is None:
            return
        feedback: dict[str, Any] = {
            "bridge": "physical_rescue",
            "event_type": event_type,
            "victim_id": victim_id,
            "firefighter_id": firefighter_id,
            "reason": reason,
            "victim_pos": victim_pos,
            "firefighter_pos": firefighter_pos,
            "metadata": dict(metadata or {}),
        }
        self._execution_log.add(
            ExecutionResult(
                decision_id=(
                    f"physical-{event_type}-{victim_id or 'na'}-"
                    f"{firefighter_id or 'na'}-{int(timestamp)}"
                ),
                executor_type="rescue",
                target_entity=victim_id or "rescue",
                action=event_type,
                status="recorded",
                timestamp=timestamp,
                intended_effect=reason,
                actual_result="physical_bridge",
                feedback_event=feedback,
                confidence_before=1.0,
                confidence_after=1.0,
                explanation=f"Physical rescue bridge: {event_type} ({reason})",
            )
        )

    @staticmethod
    def _firefighter_is_active_physical(ff_marker: Any) -> bool:
        if ff_marker is None:
            return False
        if getattr(ff_marker, "dead", False):
            return False
        status = str(getattr(ff_marker, "status", "") or "").strip().lower()
        if status in ("dead", "route_blocked"):
            return False
        if not getattr(ff_marker, "assigned", False):
            return False
        return getattr(ff_marker, "rescued_victim", None) is not None

    def _active_physical_pairing(
        self,
        model: Any,
        victim_id: str,
        firefighter_id: str,
    ) -> tuple[str, str] | None:
        """Return (firefighter_id, victim_id) if an active physical pairing exists."""
        if model is None:
            return None
        vid = str(victim_id or "").strip()
        ff_id = str(firefighter_id or "").strip()
        generic = vid.lower() in _GENERIC_VICTIM_IDS
        victim_markers = getattr(model, "victim_marker_agents", None)
        victim_marker = None
        if isinstance(victim_markers, dict) and vid:
            victim_marker = victim_markers.get(vid)
        find_active = getattr(model, "_find_active_firefighter_for_victim", None)
        if not generic and vid and callable(find_active):
            pair = find_active(vid, victim_marker)
            if pair is not None:
                return str(pair[0]), vid

        markers = getattr(model, "firefighter_marker_agents", None)
        resolve = getattr(model, "_victim_id_from_agent", None)

        def _target_victim_id(ff_marker: Any) -> str:
            rv = getattr(ff_marker, "rescued_victim", None)
            if rv is None:
                return ""
            if callable(resolve):
                return str(resolve(rv) or "").strip()
            return str(getattr(rv, "victim_id", "") or "").strip()

        if ff_id and isinstance(markers, dict):
            ff_marker = markers.get(ff_id)
            if self._firefighter_is_active_physical(ff_marker):
                rv_id = _target_victim_id(ff_marker)
                if rv_id and (generic or rv_id == vid):
                    return ff_id, rv_id

        if generic and isinstance(markers, dict):
            for fid, ff_marker in markers.items():
                if not self._firefighter_is_active_physical(ff_marker):
                    continue
                rv_id = _target_victim_id(ff_marker)
                return str(fid), rv_id or vid
        return None

    @staticmethod
    def _classify_rescue_action(rescue_action: str) -> str:
        action = rescue_action.strip().lower()
        if not action:
            return ""
        if "confirm" in action:
            return "confirm"
        if any(token in action for token in ("assign", "initiate", "dispatch")):
            return "assign"
        if "delay" in action:
            return "delay"
        if "cancel" in action:
            return "cancel"
        return ""

    @staticmethod
    def _apply_victim_state(
        victim: Any,
        action_kind: str,
        firefighter_id: str,
        route_choice: str,
    ) -> dict[str, object]:
        updates: dict[str, object] = {"action_kind": action_kind}
        if firefighter_id and hasattr(victim, "firefighter_id"):
            victim.firefighter_id = firefighter_id
            updates["firefighter_id"] = firefighter_id
        if route_choice and hasattr(victim, "route_choice"):
            victim.route_choice = route_choice
            updates["route_choice"] = route_choice

        if action_kind == "confirm":
            if hasattr(victim, "confirmed"):
                victim.confirmed = True
            if hasattr(victim, "needs_confirmation"):
                victim.needs_confirmation = False
            updates["confirmed"] = True
            updates["needs_confirmation"] = False
        elif action_kind == "assign":
            if hasattr(victim, "rescue_assigned"):
                victim.rescue_assigned = True
            updates["rescue_assigned"] = True
        elif action_kind == "delay":
            if hasattr(victim, "rescue_assigned"):
                victim.rescue_assigned = False
            if hasattr(victim, "status"):
                victim.status = "delayed"
            updates["rescue_assigned"] = False
            updates["status"] = "delayed"
        elif action_kind == "cancel":
            if hasattr(victim, "rescue_assigned"):
                victim.rescue_assigned = False
            if hasattr(victim, "status"):
                victim.status = "cancelled"
            updates["rescue_assigned"] = False
            updates["status"] = "cancelled"

        return updates

    @staticmethod
    def _apply_firefighter_model(
        firefighter_model: Any,
        firefighter_id: str,
        victim_id: str,
        action_kind: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        updates: dict[str, object] = {}
        assign_to_victim = getattr(firefighter_model, "assign_to_victim", None)
        if callable(assign_to_victim) and victim_id:
            try:
                assign_to_victim(firefighter_id, victim_id, action_kind=action_kind)
            except TypeError:
                assign_to_victim(firefighter_id, victim_id)
            updates["assign_to_victim"] = True
            return updates

        update_unit_state = getattr(firefighter_model, "update_unit_state", None)
        if callable(update_unit_state):
            state: dict[str, object] = {
                "victim_id": victim_id,
                "action_kind": action_kind,
            }
            update_unit_state(firefighter_id, state)
            updates["update_unit_state"] = state

        return updates

    @staticmethod
    def _apply_victim_runtime(
        victim_runtime: Any,
        victim_id: str,
        action_kind: str,
        firefighter_id: str,
        route_choice: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        updates: dict[str, object] = {}
        for method_name in (
            "update_rescue_state",
            "set_rescue_state",
            "apply_rescue_action",
        ):
            method = getattr(victim_runtime, method_name, None)
            if not callable(method):
                continue
            kwargs: dict[str, object] = {
                "victim_id": victim_id,
                "action_kind": action_kind,
                "firefighter_id": firefighter_id,
                "route_choice": route_choice,
            }
            kwargs.update(payload)
            try:
                method(**kwargs)
            except TypeError:
                method(victim_id, action_kind)
            updates[method_name] = True
            break
        return updates
