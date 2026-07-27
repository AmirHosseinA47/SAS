"""Managing system: centralized fail-safe safety checker.

Derives fail-safe reasons and mode from analysis, planning, and execution
artifacts without mutating managed state.
"""

from __future__ import annotations

from typing import Any

from ..analysis.trigger_objects import (
    TriggerBatch,
    normalize_triggers,
    trigger_signal_passes_information_confidence,
)
from .failsafe_modes import FailSafeMode, FailSafeReason

_TRIGGER_TYPE_TO_REASON: dict[str, str] = {
    "CRITICAL_BATTERY": FailSafeReason.CRITICAL_BATTERY.value,
    "DRIFT_TOO_HIGH": FailSafeReason.EXTREME_DRIFT.value,
    "COLLISION_RISK": FailSafeReason.COLLISION_RISK.value,
    "CRITICAL_LINK_UNRELIABLE": FailSafeReason.CRITICAL_COMMUNICATION.value,
    "RESCUE_UNSAFE": FailSafeReason.RESCUE_ROUTE_UNSAFE.value,
    "INFORMATION_INSUFFICIENT": FailSafeReason.INFORMATION_INSUFFICIENT.value,
    "SEARCH_MODE_REQUIRED": FailSafeReason.SEARCH_MODE_REQUIRED.value,
    "OSCILLATION_RISK": FailSafeReason.INSTABILITY.value,
    "INSTABILITY_DETECTED": FailSafeReason.INSTABILITY.value,
}

_PLANNING_TEXT_TO_REASON: tuple[tuple[str, str], ...] = (
    ("critical_battery", FailSafeReason.CRITICAL_BATTERY.value),
    ("collision", FailSafeReason.COLLISION_RISK.value),
    ("no_feasible_path", FailSafeReason.NO_FEASIBLE_PATH.value),
    ("no feasible path", FailSafeReason.NO_FEASIBLE_PATH.value),
    ("extreme_drift", FailSafeReason.EXTREME_DRIFT.value),
    ("drift", FailSafeReason.EXTREME_DRIFT.value),
    ("rescue_unsafe", FailSafeReason.RESCUE_ROUTE_UNSAFE.value),
    ("rescue unsafe", FailSafeReason.RESCUE_ROUTE_UNSAFE.value),
    ("critical_communication", FailSafeReason.CRITICAL_COMMUNICATION.value),
    ("communication", FailSafeReason.CRITICAL_COMMUNICATION.value),
    ("global_uncertainty", FailSafeReason.GLOBAL_UNCERTAINTY.value),
    ("victim_uncertainty", FailSafeReason.VICTIM_UNCERTAINTY.value),
    ("information_insufficient", FailSafeReason.INFORMATION_INSUFFICIENT.value),
    ("search_mode", FailSafeReason.SEARCH_MODE_REQUIRED.value),
    ("instability", FailSafeReason.INSTABILITY.value),
    ("manual_hold", FailSafeReason.MANUAL_HOLD.value),
)


class SafetyChecker:
    """Extract fail-safe reasons and classify operational mode."""

    def extract_fail_safe_reasons(
        self,
        analysis_snapshot: object | None = None,
        planning_result: object | None = None,
        execution_result: object | None = None,
        runtime_models: object | None = None,
    ) -> tuple[str, ...]:
        _ = runtime_models
        reasons: list[str] = []
        self._extend_unique(reasons, self._reasons_from_analysis(analysis_snapshot))
        self._extend_unique(reasons, self._reasons_from_planning(planning_result))
        self._extend_unique(reasons, self._reasons_from_execution(execution_result))
        return tuple(reasons)

    def classify_mode(
        self,
        reasons: tuple[str, ...] | list[str],
        current_mode: str = "normal",
    ) -> str:
        _ = current_mode
        reason_set = {self._canonical_reason(r) for r in reasons}

        if self._is_emergency(reason_set):
            return FailSafeMode.EMERGENCY.value
        if (
            FailSafeReason.INFORMATION_INSUFFICIENT.value in reason_set
            or FailSafeReason.SEARCH_MODE_REQUIRED.value in reason_set
        ):
            return FailSafeMode.INFORMATION_RECOVERY.value
        if reason_set & {
            FailSafeReason.COLLISION_RISK.value,
            FailSafeReason.EXTREME_DRIFT.value,
            FailSafeReason.NO_FEASIBLE_PATH.value,
            FailSafeReason.RESCUE_ROUTE_UNSAFE.value,
        }:
            return FailSafeMode.SAFETY_FIRST.value
        if reason_set & {
            FailSafeReason.CRITICAL_COMMUNICATION.value,
            FailSafeReason.GLOBAL_UNCERTAINTY.value,
            FailSafeReason.INSTABILITY.value,
        }:
            return FailSafeMode.DEGRADED.value
        if not reason_set:
            return FailSafeMode.NORMAL.value
        return FailSafeMode.DEGRADED.value

    def should_override_utility(self, reasons: tuple[str, ...] | list[str], mode: str) -> bool:
        mode_key = mode.strip().lower().replace("-", "_").replace(" ", "_")
        if mode_key in {
            FailSafeMode.EMERGENCY.value,
            FailSafeMode.SAFETY_FIRST.value,
            FailSafeMode.INFORMATION_RECOVERY.value,
        }:
            return True

        reason_set = {self._canonical_reason(r) for r in reasons}
        return bool(
            reason_set
            & {
                FailSafeReason.CRITICAL_BATTERY.value,
                FailSafeReason.COLLISION_RISK.value,
                FailSafeReason.NO_FEASIBLE_PATH.value,
                FailSafeReason.SEARCH_MODE_REQUIRED.value,
            }
        )

    def _reasons_from_analysis(self, analysis_snapshot: object | None) -> list[str]:
        if analysis_snapshot is None:
            return []
        batch = normalize_triggers(analysis_snapshot)
        found: list[str] = []
        for signal in batch.triggers:
            trigger_type = signal.name.strip().upper()
            reason = _TRIGGER_TYPE_TO_REASON.get(trigger_type)
            if not reason:
                continue
            if not trigger_signal_passes_information_confidence(signal):
                continue
            found.append(reason)
        return found

    def _reasons_from_planning(self, planning_result: object | None) -> list[str]:
        if planning_result is None:
            return []
        decision = self._read_value(planning_result, "fail_safe_decision", None)
        if decision is None:
            decision = planning_result
        found: list[str] = []
        if bool(self._read_value(decision, "search_mode_active", False)):
            found.append(FailSafeReason.SEARCH_MODE_REQUIRED.value)
        for field_name in ("fail_safe_action", "mission_mode"):
            text = str(self._read_value(decision, field_name, "") or "")
            self._extend_unique(found, self._reasons_from_text(text))
        return found

    def _reasons_from_execution(self, execution_result: object | None) -> list[str]:
        if execution_result is None:
            return []
        found: list[str] = []
        if bool(self._read_value(execution_result, "no_search_target", False)):
            found.append(FailSafeReason.INFORMATION_INSUFFICIENT.value)
            found.append(FailSafeReason.SEARCH_MODE_REQUIRED.value)
        if bool(self._read_value(execution_result, "partial_success", False)):
            found.append(FailSafeReason.GLOBAL_UNCERTAINTY.value)
        failures = self._read_value(execution_result, "failures", ())
        if failures is None:
            failures = ()
        for failure in failures:
            if isinstance(failure, str):
                self._extend_unique(found, self._reasons_from_text(failure))
                continue
            code = str(
                self._read_value(
                    failure,
                    "reason",
                    self._read_value(
                        failure,
                        "code",
                        self._read_value(failure, "type", ""),
                    ),
                )
            )
            self._extend_unique(found, self._reasons_from_text(code))
        return found

    @staticmethod
    def _is_emergency(reason_set: set[str]) -> bool:
        if FailSafeReason.CRITICAL_BATTERY.value in reason_set and reason_set & {
            FailSafeReason.COLLISION_RISK.value,
            FailSafeReason.NO_FEASIBLE_PATH.value,
        }:
            return True
        return (
            FailSafeReason.RESCUE_ROUTE_UNSAFE.value in reason_set
            and FailSafeReason.CRITICAL_COMMUNICATION.value in reason_set
        )

    @staticmethod
    def _reasons_from_text(text: str) -> list[str]:
        normalized = text.strip().lower().replace("-", "_")
        if not normalized:
            return []
        found: list[str] = []
        for marker, reason in _PLANNING_TEXT_TO_REASON:
            if marker in normalized:
                found.append(reason)
        upper = text.strip().upper()
        trigger_reason = _TRIGGER_TYPE_TO_REASON.get(upper)
        if trigger_reason:
            found.append(trigger_reason)
        return found

    @staticmethod
    def _canonical_reason(reason: str) -> str:
        key = reason.strip().lower().replace("-", "_").replace(" ", "_")
        for member in FailSafeReason:
            if member.value == key or member.name.lower() == key:
                return member.value
        return key

    @staticmethod
    def _read_value(source: object, name: str, default: Any = None) -> Any:
        if isinstance(source, dict):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _extend_unique(target: list[str], items: list[str]) -> None:
        seen = set(target)
        for item in items:
            canonical = SafetyChecker._canonical_reason(item)
            if canonical not in seen:
                target.append(canonical)
                seen.add(canonical)
