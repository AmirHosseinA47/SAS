"""Managing system: fail-safe mode state machine.

Tracks FailSafeState transitions via SafetyChecker; no managed-state mutation.
"""

from __future__ import annotations

from typing import Any

from ..analysis.trigger_objects import TriggerSignal, normalize_triggers
from .failsafe_modes import FailSafeMode, FailSafeReason, FailSafeState, normalize_mode, normalize_reason
from .safety_checker import SafetyChecker


class ModeManager:
    """Fail-safe mode state machine backed by ``SafetyChecker``."""

    def __init__(self, safety_checker: SafetyChecker) -> None:
        self._checker = safety_checker
        self.current_state = FailSafeState(mode=FailSafeMode.NORMAL)

    def update(
        self,
        analysis_snapshot: object | None = None,
        planning_result: object | None = None,
        execution_result: object | None = None,
        runtime_models: object | None = None,
        timestamp: float = 0.0,
    ) -> FailSafeState:
        reason_strings = self._checker.extract_fail_safe_reasons(
            analysis_snapshot=analysis_snapshot,
            planning_result=planning_result,
            execution_result=execution_result,
            runtime_models=runtime_models,
        )
        active_reasons = self._to_reason_enums(reason_strings)
        mode_value = self._checker.classify_mode(
            reason_strings,
            current_mode=self.current_state.mode.value,
        )
        new_mode = normalize_mode(mode_value)
        previous_mode = self.current_state.mode
        if new_mode == previous_mode:
            previous_mode = self.current_state.previous_mode
        started_at = self.current_state.started_at
        if new_mode != self.current_state.mode:
            started_at = timestamp
        elif started_at == 0.0 and new_mode != FailSafeMode.NORMAL:
            started_at = timestamp

        affected_entities = self._collect_affected_entities(
            analysis_snapshot,
            planning_result,
            execution_result,
        )
        confidence = self._estimate_confidence(analysis_snapshot, active_reasons)
        recovery_score = self._recovery_score(active_reasons, new_mode)

        self.current_state = FailSafeState(
            mode=new_mode,
            active_reasons=active_reasons,
            affected_entities=affected_entities,
            started_at=started_at,
            last_updated=timestamp,
            confidence=confidence,
            recovery_score=recovery_score,
            explanation=self._build_explanation(new_mode, active_reasons),
            previous_mode=previous_mode,
        )
        return self.current_state

    def should_override_utility(self) -> bool:
        return self._checker.should_override_utility(
            tuple(reason.value for reason in self.current_state.active_reasons),
            self.current_state.mode.value,
        )

    def is_information_recovery_active(self) -> bool:
        return self.current_state.mode == FailSafeMode.INFORMATION_RECOVERY

    @staticmethod
    def _iter_analysis_triggers(analysis_snapshot: object | None) -> tuple[TriggerSignal, ...]:
        if analysis_snapshot is None:
            return ()
        return normalize_triggers(analysis_snapshot).triggers

    @staticmethod
    def _to_reason_enums(reason_strings: tuple[str, ...]) -> tuple[FailSafeReason, ...]:
        reasons: list[FailSafeReason] = []
        for raw in reason_strings:
            try:
                reasons.append(normalize_reason(raw))
            except (TypeError, ValueError):
                continue
        return tuple(reasons)

    def _collect_affected_entities(
        self,
        analysis_snapshot: object | None,
        planning_result: object | None,
        execution_result: object | None,
    ) -> tuple[str, ...]:
        entities: list[str] = []
        self._extend_entities(entities, self._read_value(analysis_snapshot, "affected_entities", ()))
        for signal in self._iter_analysis_triggers(analysis_snapshot):
            affected = signal.metadata.get("affected_entities")
            if affected is not None:
                self._extend_entities(entities, affected)
        decision = self._read_value(planning_result, "fail_safe_decision", None)
        if decision is not None:
            self._extend_entities(entities, self._read_value(decision, "affected_entities", ()))
        self._extend_entities(entities, self._read_value(execution_result, "affected_entities", ()))
        return tuple(entities)

    def _estimate_confidence(
        self,
        analysis_snapshot: object | None,
        active_reasons: tuple[FailSafeReason, ...],
    ) -> float:
        snapshot_confidence = self._read_float(
            analysis_snapshot,
            "confidence",
            self._read_float(analysis_snapshot, "analysis_confidence", None),
        )
        if snapshot_confidence is not None:
            return max(0.0, min(1.0, snapshot_confidence))
        if not active_reasons:
            return 1.0
        return max(0.0, min(1.0, 1.0 - 0.15 * len(active_reasons)))

    @staticmethod
    def _recovery_score(
        active_reasons: tuple[FailSafeReason, ...],
        mode: FailSafeMode,
    ) -> float:
        if mode == FailSafeMode.NORMAL or not active_reasons:
            return 1.0
        penalty = 0.2 * len(active_reasons)
        if mode == FailSafeMode.EMERGENCY:
            penalty += 0.3
        return max(0.0, min(1.0, 1.0 - penalty))

    @staticmethod
    def _build_explanation(mode: FailSafeMode, reasons: tuple[FailSafeReason, ...]) -> str:
        reason_text = ", ".join(reason.value for reason in reasons) if reasons else "none"
        return f"mode={mode.value}; reasons={reason_text}"

    @staticmethod
    def _read_value(source: object | None, name: str, default: Any = None) -> Any:
        if source is None:
            return default
        if isinstance(source, dict):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _read_float(source: object | None, name: str, default: float | None = None) -> float | None:
        if source is None:
            return default
        raw = ModeManager._read_value(source, name, default)
        if isinstance(raw, (int, float)):
            return float(raw)
        return default

    @staticmethod
    def _extend_entities(target: list[str], raw_entities: object) -> None:
        if raw_entities is None:
            return
        if isinstance(raw_entities, str):
            if raw_entities and raw_entities not in target:
                target.append(raw_entities)
            return
        for entity in raw_entities:
            entity_id = str(entity)
            if entity_id and entity_id not in target:
                target.append(entity_id)


def build_failsafe_dashboard_summary(state: FailSafeState) -> str:
    checker = SafetyChecker()
    override_active = checker.should_override_utility(
        tuple(reason.value for reason in state.active_reasons),
        state.mode.value,
    )
    information_recovery_active = state.mode == FailSafeMode.INFORMATION_RECOVERY
    previous_mode = state.previous_mode.value if state.previous_mode is not None else "none"
    active_reasons = ", ".join(reason.value for reason in state.active_reasons) or "none"
    affected_entities = ", ".join(state.affected_entities) or "none"

    lines = [
        "Fail-safe dashboard",
        f"- Current mode: {state.mode.value}",
        f"- Previous mode: {previous_mode}",
        f"- Active reasons: {active_reasons}",
        f"- Affected entities: {affected_entities}",
        f"- Confidence: {state.confidence:.3f}",
        f"- Recovery score: {state.recovery_score:.3f}",
        f"- Explanation: {state.explanation or 'none'}",
        f"- Utility override active: {override_active}",
        f"- Information recovery active: {information_recovery_active}",
    ]
    return "\n".join(lines)
