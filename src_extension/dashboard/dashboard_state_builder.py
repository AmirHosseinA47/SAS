"""Managing system: dashboard view assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import agents

from common_fixed_variables import BATCH_SIZE

from .alert_manager import AlertManager, SEVERITY_CRITICAL, SEVERITY_INFO, SEVERITY_WARNING
from .contracts import DashboardState, _json_safe
from .display_utils import display_wind_vector
from .explanation_engine import ExplanationEngine
from .timeline_builder import MissionTimelineBuilder

KNOWN_LIMITATIONS = [
    "Firefighter safety is local/reactive, not global predictive evacuation.",
    "Smoke is soft/non-lethal for UAVs and firefighters.",
    "Operator override is documented but not functional in this phase.",
    "Dashboard is post-hoc/read-only in this phase.",
]

_TERMINAL_VICTIM = frozenset({"rescued", "dead", "unreachable", "cancelled"})


def _coords(value: Any) -> list[float] | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [float(value[0]), float(value[1])]
    return None


@dataclass
class DashboardStateBuilder:
    """Assembles structured, JSON-safe dashboard state from a live model snapshot."""

    alert_manager: AlertManager = field(default_factory=AlertManager)
    explanation_engine: ExplanationEngine = field(default_factory=ExplanationEngine)
    timeline_builder: MissionTimelineBuilder = field(default_factory=MissionTimelineBuilder)

    def build(self, model: Any) -> dict[str, Any]:
        """Read-only snapshot; does not mutate simulation state."""
        step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        alerts = self.alert_manager.generate_alerts(model)
        explanations = self.explanation_engine.collect_explanations(model)
        bundle = self.explanation_engine.bundle
        timeline = self.timeline_builder.build(model)

        critical_count = sum(1 for a in alerts if a.severity == SEVERITY_CRITICAL)
        warning_count = sum(1 for a in alerts if a.severity == SEVERITY_WARNING)
        info_count = sum(1 for a in alerts if a.severity == SEVERITY_INFO)
        unresolved_alert_count = sum(
            1 for a in alerts if a.alert_type == "unresolved_victims" and not a.resolved
        )

        state = DashboardState(
            step=step,
            mission_status=self._build_mission_status(model, step),
            uav_status_view=self._build_uav_status_view(model),
            victim_view=self._build_victim_view(model),
            firefighter_view=self._build_firefighter_view(model),
            fire_view=self._build_fire_view(model),
            rescue_view=self._build_rescue_view(model),
            communication_view=self._build_communication_view(model),
            fail_safe_view=self._build_fail_safe_view(model),
            alert_list=[a.to_dict() for a in alerts],
            explanation_list=[e.to_dict() for e in explanations],
            timeline=[e.to_dict() for e in timeline],
            known_limitations=list(KNOWN_LIMITATIONS),
            recent_alert_count=len(alerts),
            critical_alert_count=critical_count,
            warning_alert_count=warning_count,
            info_alert_count=info_count,
            unresolved_alert_count=unresolved_alert_count,
            structured_explanations=list(bundle.structured_explanations),
            option_comparison_count=bundle.option_comparison_count,
            explanation_count=len(explanations),
        )
        return state.to_dict()

    def _build_mission_status(self, model: Any, step: int) -> dict[str, Any]:
        managed = getattr(model, "managed_victims", None) or {}
        rescued = dead = 0
        all_terminal = bool(managed)
        for _, state in managed.items():
            status = str(getattr(state, "status", "") or "").strip().lower()
            if bool(getattr(state, "rescued", False)) or status == "rescued":
                rescued += 1
            if bool(getattr(state, "dead", False)) or status == "dead":
                dead += 1
            if status not in _TERMINAL_VICTIM and not bool(getattr(state, "rescued", False)):
                all_terminal = False

        try:
            from src_extension.adaptation.local_adaptation_generator import (
                _count_unresolved_victims,
            )

            unresolved = _count_unresolved_victims(model)
        except Exception:
            unresolved = sum(
                1
                for _, st in managed.items()
                if str(getattr(st, "status", "")).lower() not in _TERMINAL_VICTIM
            )

        fail_safe_mode = "normal"
        mission_mode = "normal"
        fs = getattr(model, "latest_failsafe_state", None)
        if fs is not None:
            mode = getattr(fs, "mode", None)
            fail_safe_mode = str(getattr(mode, "value", mode) or "normal")
            mission_mode = fail_safe_mode
        sop = getattr(getattr(model, "knowledge_manager", None), "shared_operational_picture", None)
        if sop is not None:
            sop_mode = getattr(sop, "mission_mode", None)
            if sop_mode:
                mission_mode = str(sop_mode)

        return {
            "step": step,
            "batch_size": int(getattr(model, "BATCH_SIZE", BATCH_SIZE) or BATCH_SIZE),
            "mission_mode": mission_mode,
            "fail_safe_mode": fail_safe_mode,
            "rescued_count": rescued,
            "dead_victim_count": dead,
            "unresolved_victim_count": unresolved,
            "all_victims_terminal": all_terminal and len(managed) > 0,
        }

    def _build_uav_status_view(self, model: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        execution = getattr(model, "latest_execution_result", None) or {}
        stuck_counts = getattr(model, "_uav_stuck_counts", None) or {}

        for agent in getattr(model.schedule, "agents", []) or []:
            if type(agent) is not agents.UAV:
                continue
            uav_id = str(getattr(agent, "unique_id", ""))
            role = ""
            if hasattr(agent, "current_role"):
                role = str(agent.current_role or "")
            managed = getattr(model, "managed_uav_states", None) or {}
            if not role and uav_id in managed:
                role = str(getattr(managed[uav_id], "role", "") or "")

            pos = _coords(getattr(agent, "pos", None))
            target = None
            if hasattr(model, "_resolve_uav_path_context_target"):
                try:
                    target = _coords(model._resolve_uav_path_context_target(uav_id))
                except Exception:
                    target = None
            if target is None:
                last_target = (getattr(model, "_uav_last_targets", None) or {}).get(uav_id)
                target = _coords(last_target)

            execution_action = None
            if hasattr(model, "_resolve_uav_path_context_action"):
                try:
                    execution_action = model._resolve_uav_path_context_action(uav_id, agent)
                except Exception:
                    execution_action = getattr(agent, "execution_action", None)
            else:
                execution_action = getattr(agent, "execution_action", None)

            fail_safe_override = False
            if isinstance(execution, dict):
                fail_safe_override = bool(execution.get("fail_safe_override_active"))
                local = execution.get("local")
                if isinstance(local, dict):
                    fail_safe_override = fail_safe_override or bool(
                        local.get("fail_safe_override_active")
                    )

            last_expl = getattr(agent, "last_explanation", None)
            rows.append(
                {
                    "id": uav_id,
                    "role": role,
                    "position": pos,
                    "battery": float(getattr(agent, "battery_level", 0.0) or 0.0),
                    "execution_action": execution_action,
                    "target_position": target,
                    "fail_safe_override_active": fail_safe_override,
                    "stuck_count": int(stuck_counts.get(uav_id, 0) or 0),
                    "last_explanation": _json_safe(last_expl) if last_expl is not None else None,
                }
            )
        rows.sort(key=lambda r: r["id"])
        return rows

    def _build_victim_view(self, model: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        managed = getattr(model, "managed_victims", None) or {}
        markers = getattr(model, "victim_marker_agents", None) or {}
        for vid, state in managed.items():
            marker = markers.get(vid)
            pos = _coords(getattr(marker, "pos", None) if marker else None)
            if pos is None:
                pos = _coords(getattr(state, "last_known_position", None))
            status = str(getattr(state, "status", "") or "").strip().lower()
            if marker is not None:
                marker_status = str(getattr(marker, "status", "") or "").strip().lower()
                if marker_status:
                    status = marker_status
            rows.append(
                {
                    "id": str(vid),
                    "position": pos,
                    "detected": status in {"confirmed", "detected", "assigned", "rescued"}
                    or bool(getattr(state, "confirmed", False)),
                    "assigned": bool(getattr(state, "rescue_assigned", False))
                    or status == "assigned",
                    "rescued": bool(getattr(state, "rescued", False)) or status == "rescued",
                    "dead": bool(getattr(state, "dead", False)) or status == "dead",
                    "unreachable": bool(getattr(state, "unreachable", False))
                    or status == "unreachable",
                    "cancelled": bool(getattr(state, "cancelled", False))
                    or status == "cancelled",
                    "assigned_firefighter": str(getattr(state, "firefighter_id", "") or ""),
                    "status": status,
                }
            )
        rows.sort(key=lambda r: r["id"])
        return rows

    def _build_firefighter_view(self, model: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        markers = getattr(model, "firefighter_marker_agents", None) or {}
        managed = getattr(model, "managed_firefighters", None) or {}
        for ff_id, marker in markers.items():
            managed_state = managed.get(ff_id)
            pos = _coords(getattr(marker, "pos", None))
            if pos is None and managed_state is not None:
                pos = _coords(getattr(managed_state, "position", None))
            status = str(getattr(marker, "status", "") or "").strip().lower()
            rescued_victim = getattr(marker, "rescued_victim", None)
            rescued_victim_id = None
            if rescued_victim is not None:
                rescued_victim_id = str(
                    getattr(rescued_victim, "victim_id", getattr(rescued_victim, "unique_id", ""))
                )
            rows.append(
                {
                    "id": str(ff_id),
                    "position": pos,
                    "alive": not bool(getattr(marker, "dead", False)),
                    "assigned": bool(getattr(marker, "assigned", False)),
                    "target_pos": _coords(getattr(marker, "target_pos", None)),
                    "rescued_victim": rescued_victim_id,
                    "exiting": bool(getattr(marker, "exiting", False)),
                    "route_blocked": status == "route_blocked",
                    "status": status,
                }
            )
        rows.sort(key=lambda r: r["id"])
        return rows

    def _build_fire_view(self, model: Any) -> dict[str, Any]:
        active_fire = active_smoke = burnt = has_burned = 0
        for agent in getattr(model.schedule, "agents", []) or []:
            if type(agent) is not agents.Fire:
                continue
            if agent.is_burning():
                active_fire += 1
            smoke = getattr(agent, "smoke", None)
            if smoke is not None and getattr(smoke, "is_smoke_active", lambda: False)():
                active_smoke += 1
            if bool(getattr(agent, "burnt", False)) or (
                hasattr(agent, "is_burnt") and agent.is_burnt()
            ):
                burnt += 1
            if bool(getattr(agent, "has_burned", False)):
                has_burned += 1

        wind = getattr(model, "wind", None)
        wind_direction = "unknown"
        if wind is not None:
            wind_direction = str(getattr(wind, "wind_direction", "unknown") or "unknown")
        wind_vector = list(display_wind_vector(wind_direction))

        return {
            "active_fire_cells": active_fire,
            "active_smoke_cells": active_smoke,
            "burnt_cells": burnt,
            "has_burned_cells": has_burned,
            "wind_direction": wind_direction,
            "wind_vector": wind_vector,
        }

    def _build_rescue_view(self, model: Any) -> dict[str, Any]:
        log = list(getattr(model, "_rescue_event_log", None) or [])
        recent = [_json_safe(e) for e in log[-15:]]
        dispatch = rescue_complete = victim_dead = ff_casualty = 0
        for event in log:
            et = str(event.get("event_type", "") or "").lower()
            if "dispatch" in et:
                dispatch += 1
            if et == "rescue_complete":
                rescue_complete += 1
            if et == "victim_dead":
                victim_dead += 1
            if "firefighter_dead" in et or et == "firefighter_casualty":
                ff_casualty += 1

        ff_markers = getattr(model, "firefighter_marker_agents", None) or {}
        ff_casualty += sum(1 for ff in ff_markers.values() if bool(getattr(ff, "dead", False)))

        return {
            "recent_rescue_events": recent,
            "dispatch_count": dispatch,
            "rescue_complete_count": rescue_complete,
            "victim_dead_count": victim_dead,
            "firefighter_casualty_count": ff_casualty,
        }

    def _build_communication_view(self, model: Any) -> dict[str, Any]:
        comm = getattr(model, "communication_model", None)
        view: dict[str, Any] = {
            "communication_mode": "unknown",
            "relay_needed": False,
            "delivery_confidence": None,
            "message_load": 0,
            "latest_communication_execution": None,
        }
        if comm is not None:
            try:
                ctx = comm.runtime_context()
                if isinstance(ctx, dict):
                    view["communication_mode"] = str(ctx.get("communication_mode", "unknown"))
                    view["relay_needed"] = bool(ctx.get("relay_needed"))
                    dc = ctx.get("delivery_confidence")
                    view["delivery_confidence"] = float(dc) if dc is not None else None
                    view["message_load"] = int(ctx.get("message_load", 0) or 0)
            except Exception:
                view["communication_mode"] = str(getattr(comm, "communication_mode", "unknown"))
        exec_result = getattr(model, "latest_communication_execution", None)
        if isinstance(exec_result, dict):
            view["latest_communication_execution"] = _json_safe(exec_result)
        return view

    def _build_fail_safe_view(self, model: Any) -> dict[str, Any]:
        fs = getattr(model, "latest_failsafe_state", None)
        view: dict[str, Any] = {
            "current_mode": "normal",
            "latest_fail_safe_decision": None,
            "active_triggers": [],
        }
        if fs is not None:
            mode = getattr(fs, "mode", None)
            view["current_mode"] = str(getattr(mode, "value", mode) or "normal")
            view["latest_fail_safe_decision"] = {
                "explanation": str(getattr(fs, "explanation", "") or ""),
                "active_reasons": [
                    str(getattr(r, "value", r))
                    for r in (getattr(fs, "active_reasons", ()) or ())
                ],
                "affected_entities": list(getattr(fs, "affected_entities", ()) or ()),
            }
        analysis = getattr(model, "latest_analysis_snapshot", None)
        if analysis is not None:
            triggers = getattr(analysis, "all_triggers", ()) or ()
            view["active_triggers"] = [
                str(getattr(t, "trigger_type", getattr(t, "kind", t)))
                for t in triggers
            ][:20]
        planning = getattr(model, "latest_planning_result", None)
        if isinstance(planning, dict):
            fsd = planning.get("fail_safe_decision")
            if fsd is not None:
                view["latest_fail_safe_decision"] = view.get("latest_fail_safe_decision") or {}
                if isinstance(view["latest_fail_safe_decision"], dict):
                    view["latest_fail_safe_decision"]["planning"] = _json_safe(
                        {
                            "mission_mode": getattr(fsd, "mission_mode", None),
                            "search_mode_active": getattr(fsd, "search_mode_active", None),
                            "fail_safe_action": getattr(fsd, "fail_safe_action", None),
                        }
                    )
        summary = getattr(model, "latest_failsafe_dashboard_summary", None)
        if summary:
            view["dashboard_summary"] = str(summary)
        return view
