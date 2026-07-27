"""Managing system: operator alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import agents

from common_fixed_variables import LOW_BATTERY_THRESHOLD

from .contracts import AlertRecord

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

CRITICAL_ALERT_TYPES = frozenset(
    {"victim_dead", "firefighter_dead", "emergency_fail_safe", "rescue_failed"}
)
WARNING_ALERT_TYPES = frozenset(
    {
        "route_blocked",
        "low_battery",
        "communication_degraded",
        "unresolved_victims",
        "information_insufficient",
        "search_mode_required",
    }
)
INFO_ALERT_TYPES = frozenset(
    {
        "victim_detected",
        "dispatch_started",
        "rescue_complete",
        "communication_mode_changed",
        "fail_safe_mode_changed",
    }
)

_FAILSAFE_REASON_ALERTS: dict[str, tuple[str, str]] = {
    "information_insufficient": ("information_insufficient", SEVERITY_WARNING),
    "search_mode_required": ("search_mode_required", SEVERITY_WARNING),
}


@dataclass
class AlertManager:
    """Generates operator-facing alert records from model state (no side effects)."""

    alerts: list[AlertRecord] = field(default_factory=list)

    def generate_alerts(self, model: Any) -> list[AlertRecord]:
        """Build alert records from current model snapshot."""
        step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        records: list[AlertRecord] = []

        def add(
            *,
            alert_type: str,
            severity: str,
            target_id: str,
            message: str,
            source_module: str,
            event_step: int | None = None,
            resolved: bool = False,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            alert_step = step if event_step is None else int(event_step)
            records.append(
                AlertRecord(
                    alert_id=f"{alert_type}:{target_id}:{alert_step}",
                    step=alert_step,
                    severity=severity,
                    alert_type=alert_type,
                    target_id=target_id,
                    message=message,
                    source_module=source_module,
                    resolved=resolved,
                    metadata=dict(metadata or {}),
                )
            )

        self._alerts_from_rescue_log(model, add)
        self._alerts_from_victims(model, add)
        self._alerts_from_firefighters(model, add)
        self._alerts_from_uavs(model, add)
        self._alerts_from_failsafe(model, add)
        self._alerts_from_communication(model, add)

        deduped = self._dedupe_alerts(records)
        self.alerts = deduped
        return deduped

    def _alerts_from_rescue_log(self, model: Any, add: Any) -> None:
        for event in list(getattr(model, "_rescue_event_log", None) or []):
            event_type = str(event.get("event_type", "") or "")
            event_step = int(event.get("step", 0) or 0)
            vid = str(event.get("victim_id", "") or "unknown")
            ff_id = str(event.get("firefighter_id", "") or "")
            reason = str(event.get("reason", "") or "")
            meta = {
                "raw_event_type": event_type,
                "firefighter_id": ff_id or None,
                "victim_pos": event.get("victim_pos"),
            }

            if event_type == "dispatch_initial":
                add(
                    alert_type="dispatch_started",
                    severity=SEVERITY_INFO,
                    target_id=vid,
                    message=reason or f"Dispatch started for victim {vid}",
                    source_module="rescue_pipeline",
                    event_step=event_step,
                    metadata=meta,
                )
            elif event_type in {
                "dispatch_replacement_after_blocked",
                "dispatch_replacement_after_casualty",
            }:
                add(
                    alert_type="dispatch_started",
                    severity=SEVERITY_INFO,
                    target_id=vid,
                    message=reason or f"Replacement dispatch for victim {vid}",
                    source_module="rescue_pipeline",
                    event_step=event_step,
                    metadata={**meta, "replacement": True},
                )
            elif event_type == "rescue_complete":
                add(
                    alert_type="rescue_complete",
                    severity=SEVERITY_INFO,
                    target_id=vid,
                    message=reason or f"Rescue complete for victim {vid}",
                    source_module="rescue_pipeline",
                    event_step=event_step,
                    metadata=meta,
                )
            elif event_type == "rescue_failed" or "fail" in event_type:
                add(
                    alert_type="rescue_failed",
                    severity=SEVERITY_CRITICAL,
                    target_id=vid,
                    message=reason or f"Rescue failed: {event_type}",
                    source_module="rescue_pipeline",
                    event_step=event_step,
                    metadata=meta,
                )
            elif event_type == "route_blocked":
                target = ff_id or vid
                add(
                    alert_type="route_blocked",
                    severity=SEVERITY_WARNING,
                    target_id=target,
                    message=reason or f"Route blocked for {target}",
                    source_module="rescue_pipeline",
                    event_step=event_step,
                    metadata=meta,
                )

    def _alerts_from_victims(self, model: Any, add: Any) -> None:
        managed = getattr(model, "managed_victims", None) or {}
        for vid, state in managed.items():
            status = str(getattr(state, "status", "") or "").strip().lower()
            dead = bool(getattr(state, "dead", False)) or status == "dead"
            if dead:
                add(
                    alert_type="victim_dead",
                    severity=SEVERITY_CRITICAL,
                    target_id=str(vid),
                    message=f"Victim {vid} marked dead",
                    source_module="rescue_pipeline",
                    metadata={"status": status},
                )
            elif (
                bool(getattr(state, "confirmed", False))
                or status in {"confirmed", "detected", "assigned"}
            ):
                add(
                    alert_type="victim_detected",
                    severity=SEVERITY_INFO,
                    target_id=str(vid),
                    message=f"Victim {vid} detected (status={status})",
                    source_module="victim_runtime_model",
                    metadata={"status": status},
                )

        unresolved = 0
        try:
            from src_extension.adaptation.local_adaptation_generator import (
                _count_unresolved_victims,
            )

            unresolved = _count_unresolved_victims(model)
        except Exception:
            for _, state in managed.items():
                status = str(getattr(state, "status", "") or "").strip().lower()
                if status not in {"rescued", "dead", "unreachable", "cancelled"}:
                    unresolved += 1
        if unresolved > 0:
            add(
                alert_type="unresolved_victims",
                severity=SEVERITY_WARNING,
                target_id="mission",
                message=f"{unresolved} victim(s) remain unresolved",
                source_module="mission_status",
                metadata={"unresolved_count": unresolved},
            )

    def _alerts_from_firefighters(self, model: Any, add: Any) -> None:
        for ff_id, ff in (getattr(model, "firefighter_marker_agents", None) or {}).items():
            if bool(getattr(ff, "dead", False)):
                add(
                    alert_type="firefighter_dead",
                    severity=SEVERITY_CRITICAL,
                    target_id=str(ff_id),
                    message=f"Firefighter {ff_id} is dead",
                    source_module="firefighter_monitor",
                )
            elif str(getattr(ff, "status", "") or "").strip().lower() == "route_blocked":
                add(
                    alert_type="route_blocked",
                    severity=SEVERITY_WARNING,
                    target_id=str(ff_id),
                    message=f"Firefighter {ff_id} route blocked",
                    source_module="firefighter_monitor",
                )

    def _alerts_from_uavs(self, model: Any, add: Any) -> None:
        for agent in getattr(model.schedule, "agents", []) or []:
            if type(agent) is not agents.UAV:
                continue
            uav_id = str(getattr(agent, "unique_id", ""))
            battery = float(getattr(agent, "battery_level", 100.0) or 100.0)
            if battery <= LOW_BATTERY_THRESHOLD:
                add(
                    alert_type="low_battery",
                    severity=SEVERITY_WARNING,
                    target_id=uav_id,
                    message=f"UAV {uav_id} battery at {battery:.1f}%",
                    source_module="uav_monitor",
                    metadata={"battery_level": battery},
                )

    def _alerts_from_failsafe(self, model: Any, add: Any) -> None:
        fs = getattr(model, "latest_failsafe_state", None)
        if fs is None:
            return
        mode = getattr(fs, "mode", None)
        mode_value = str(getattr(mode, "value", mode) or "").lower()
        if mode_value and mode_value != "normal":
            add(
                alert_type="emergency_fail_safe",
                severity=SEVERITY_CRITICAL,
                target_id="fleet",
                message=str(getattr(fs, "explanation", "") or f"Fail-safe mode: {mode_value}"),
                source_module="failsafe",
                metadata={"mode": mode_value},
            )
            add(
                alert_type="fail_safe_mode_changed",
                severity=SEVERITY_INFO,
                target_id="fleet",
                message=f"Fail-safe mode active: {mode_value}",
                source_module="mode_manager",
                metadata={"mode": mode_value},
            )
        for reason in getattr(fs, "active_reasons", ()) or ():
            reason_value = str(getattr(reason, "value", reason) or "").lower()
            mapping = _FAILSAFE_REASON_ALERTS.get(reason_value)
            if mapping is None:
                continue
            alert_type, severity = mapping
            add(
                alert_type=alert_type,
                severity=severity,
                target_id="fleet",
                message=f"Fail-safe reason active: {reason_value}",
                source_module="failsafe",
                metadata={"reason": reason_value},
            )

    def _alerts_from_communication(self, model: Any, add: Any) -> None:
        comm = getattr(model, "communication_model", None)
        if comm is None:
            return

        log = list(getattr(comm, "_communication_command_log", None) or [])
        for entry in log:
            if not isinstance(entry, dict):
                continue
            previous = str(entry.get("previous_mode", "") or "")
            current = str(entry.get("communication_mode", "") or "")
            if not current or previous == current:
                continue
            ts = entry.get("timestamp")
            event_step = (
                int(ts)
                if isinstance(ts, (int, float)) and ts >= 0
                else int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
            )
            add(
                alert_type="communication_mode_changed",
                severity=SEVERITY_INFO,
                target_id="communication",
                message=str(entry.get("reason", "") or f"Mode changed: {previous} -> {current}"),
                source_module="communication_model",
                event_step=event_step,
                metadata={"previous_mode": previous, "communication_mode": current},
            )

        try:
            ctx = comm.runtime_context()
        except Exception:
            ctx = {}
        if isinstance(ctx, dict):
            degraded = bool(ctx.get("link_degraded"))
            mode = str(ctx.get("communication_mode", "") or "")
            if degraded or mode in {"degraded", "critical", "emergency"}:
                add(
                    alert_type="communication_degraded",
                    severity=SEVERITY_WARNING,
                    target_id="communication",
                    message=f"Communication degraded (mode={mode or 'unknown'})",
                    source_module="communication_model",
                    metadata={"communication_mode": mode, "link_degraded": degraded},
                )

    @staticmethod
    def _dedupe_alerts(records: list[AlertRecord]) -> list[AlertRecord]:
        """Keep latest alert per (step, alert_type, target_id)."""
        latest: dict[tuple[int, str, str], AlertRecord] = {}
        for record in records:
            key = (record.step, record.alert_type, record.target_id)
            latest[key] = record
        result = list(latest.values())
        result.sort(key=lambda r: (r.step, r.severity, r.alert_type, r.target_id))
        return result

    def emit(self, record: AlertRecord) -> None:
        """Append a manually supplied alert (testing / future subscription hook)."""
        self.alerts.append(record)

    @staticmethod
    def count_by_severity(alerts: list[AlertRecord]) -> dict[str, int]:
        counts = {SEVERITY_INFO: 0, SEVERITY_WARNING: 0, SEVERITY_CRITICAL: 0}
        for alert in alerts:
            sev = str(alert.severity or "").lower()
            if sev in counts:
                counts[sev] += 1
        return counts
