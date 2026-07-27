"""Managing system: mission timeline assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import MissionTimelineEvent, _json_safe

# Rescue log event_type -> normalized timeline event_type
_RESCUE_TIMELINE_MAP: dict[str, str] = {
    "dispatch_initial": "dispatch_initial",
    "dispatch_replacement_after_blocked": "replacement_dispatch",
    "dispatch_replacement_after_casualty": "replacement_dispatch",
    "route_blocked": "route_blocked",
    "rescue_complete": "rescue_complete",
    "victim_dead": "victim_dead",
    "casualty": "firefighter_dead",
    "rescue_failed": "rescue_failed",
}


@dataclass
class MissionTimelineBuilder:
    """Builds ordered mission timeline events from real model logs and fields."""

    events: list[MissionTimelineEvent] = field(default_factory=list)

    def build(self, model: Any) -> list[MissionTimelineEvent]:
        records: list[MissionTimelineEvent] = []
        records.extend(self._from_rescue_event_log(model))
        records.extend(self._from_communication_command_log(model))
        records.extend(self._from_fail_safe_state(model))
        records.extend(self._from_search_mode_state(model))
        records.extend(self._from_movement_transition_log(model))
        records = self._dedupe_timeline(records)
        records.sort(key=lambda e: (e.step, e.event_type, e.entity_id))
        self.events = records
        return records

    def _from_rescue_event_log(self, model: Any) -> list[MissionTimelineEvent]:
        events: list[MissionTimelineEvent] = []
        for raw in list(getattr(model, "_rescue_event_log", None) or []):
            raw_type = str(raw.get("event_type", "") or "")
            timeline_type = _RESCUE_TIMELINE_MAP.get(raw_type, raw_type or "rescue_event")
            vid = str(raw.get("victim_id", "") or "")
            ff_id = str(raw.get("firefighter_id", "") or "")
            entity_id = ff_id if timeline_type == "firefighter_dead" else vid
            if not entity_id:
                entity_id = vid or ff_id or "mission"
            reason = str(raw.get("reason", "") or "")
            message = reason or f"{timeline_type} for {entity_id}"
            meta = dict(raw.get("metadata") or {})
            meta.update(
                {
                    "raw_event_type": raw_type,
                    "firefighter_id": ff_id or None,
                    "victim_id": vid or None,
                    "victim_pos": _json_safe(raw.get("victim_pos")),
                    "firefighter_pos": _json_safe(raw.get("firefighter_pos")),
                }
            )
            events.append(
                MissionTimelineEvent(
                    step=int(raw.get("step", 0) or 0),
                    event_type=timeline_type,
                    entity_id=entity_id,
                    message=message,
                    metadata=meta,
                    source_module="rescue_pipeline",
                )
            )
        return events

    def _from_communication_command_log(self, model: Any) -> list[MissionTimelineEvent]:
        events: list[MissionTimelineEvent] = []
        comm = getattr(model, "communication_model", None)
        if comm is None:
            return events
        log = list(getattr(comm, "_communication_command_log", None) or [])
        for entry in log:
            if not isinstance(entry, dict):
                continue
            previous = str(entry.get("previous_mode", "") or "")
            current = str(entry.get("communication_mode", "") or "")
            if not current or previous == current:
                continue
            ts = entry.get("timestamp")
            step = int(ts) if isinstance(ts, (int, float)) and ts >= 0 else int(
                getattr(model, "evaluation_timesteps_counter", 0) or 0
            )
            reason = str(entry.get("reason", "") or "")
            message = reason or f"Communication mode changed: {previous} -> {current}"
            events.append(
                MissionTimelineEvent(
                    step=step,
                    event_type="communication_mode_changed",
                    entity_id="communication",
                    message=message,
                    metadata={
                        "previous_mode": previous,
                        "communication_mode": current,
                        "source": entry.get("source"),
                    },
                    source_module="communication_model",
                )
            )
        return events

    def _from_fail_safe_state(self, model: Any) -> list[MissionTimelineEvent]:
        fs = getattr(model, "latest_failsafe_state", None)
        if fs is None:
            return []
        mode = getattr(fs, "mode", None)
        mode_value = str(getattr(mode, "value", mode) or "").lower()
        if not mode_value or mode_value == "normal":
            return []
        step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        explanation = str(getattr(fs, "explanation", "") or "")
        summary = str(getattr(model, "latest_failsafe_dashboard_summary", "") or "")
        message = explanation or summary or f"Fail-safe mode: {mode_value}"
        reasons = [
            str(getattr(r, "value", r)) for r in (getattr(fs, "active_reasons", ()) or ())
        ]
        return [
            MissionTimelineEvent(
                step=step,
                event_type="fail_safe_mode_changed",
                entity_id="fleet",
                message=message,
                metadata={"mode": mode_value, "active_reasons": reasons},
                source_module="mode_manager",
            )
        ]

    def _from_search_mode_state(self, model: Any) -> list[MissionTimelineEvent]:
        """UAV search-mode activation from planning/execution fields (snapshot only)."""
        search_active = False
        uav_ids: list[str] = []
        planning = getattr(model, "latest_planning_result", None)
        if isinstance(planning, dict):
            fsd = planning.get("fail_safe_decision")
            if fsd is not None and bool(getattr(fsd, "search_mode_active", False)):
                search_active = True
        execution = getattr(model, "latest_execution_result", None)
        if isinstance(execution, dict):
            if bool(execution.get("fail_safe_override_active")):
                search_active = True
            local = execution.get("local")
            if isinstance(local, dict):
                uav_results = local.get("uav_results")
                if isinstance(uav_results, dict):
                    for uav_id, result in uav_results.items():
                        if isinstance(result, dict) and bool(
                            result.get("fail_safe_override_active")
                        ):
                            search_active = True
                            uav_ids.append(str(uav_id))
        if not search_active:
            return []
        step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        entity = uav_ids[0] if uav_ids else "fleet"
        return [
            MissionTimelineEvent(
                step=step,
                event_type="uav_search_mode_active",
                entity_id=entity,
                message="UAV search-mode fail-safe override active",
                metadata={"uav_ids": uav_ids or None},
                source_module="execution",
            )
        ]

    def _from_movement_transition_log(self, model: Any) -> list[MissionTimelineEvent]:
        events: list[MissionTimelineEvent] = []
        for raw in list(getattr(model, "_movement_transition_log", None) or []):
            if not isinstance(raw, dict):
                continue
            category = str(raw.get("category", "") or "")
            target_id = str(raw.get("target_id", "") or "")
            if not category or not target_id:
                continue
            prev = str(raw.get("prev_category", "") or "")
            reason = str(raw.get("reason", "") or category)
            message = reason
            if prev:
                message = f"{reason} (was {prev})"
            source_module = str(
                raw.get("source_module", "")
                or (
                    "firefighter_move"
                    if raw.get("agent_kind") == "firefighter"
                    else "uav_move"
                )
            )
            events.append(
                MissionTimelineEvent(
                    step=int(raw.get("step", 0) or 0),
                    event_type="movement_transition",
                    entity_id=target_id,
                    message=message,
                    metadata={
                        "category": category,
                        "previous_category": prev or None,
                        "agent_kind": raw.get("agent_kind"),
                        "key_factors": _json_safe(raw.get("key_factors")),
                    },
                    source_module=source_module,
                )
            )
        return events

    @staticmethod
    def _dedupe_timeline(
        events: list[MissionTimelineEvent],
    ) -> list[MissionTimelineEvent]:
        latest: dict[tuple[int, str, str], MissionTimelineEvent] = {}
        for event in events:
            key = (event.step, event.event_type, event.entity_id)
            latest[key] = event
        return list(latest.values())
