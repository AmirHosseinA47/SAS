"""TriggerBatch / TriggerSignal normalization across analysis and fail-safe."""

from __future__ import annotations

from dataclasses import dataclass

from src_extension.analysis.analysis_results import AnalysisSnapshot, GlobalAnalysisResult, LocalAnalysisResult
from src_extension.analysis.trigger_objects import (
    InformationTrigger,
    ResourceTrigger,
    Scope,
    Severity,
    StructuredTrigger,
    TriggerBatch,
    TriggerSignal,
    normalize_triggers,
    trigger_batch_from_structured,
    trigger_signal_passes_information_confidence,
)
from src_extension.execution.failsafe_modes import FailSafeMode, FailSafeReason
from src_extension.execution.mode_manager import ModeManager
from src_extension.execution.safety_checker import SafetyChecker
from src_extension.planning.fail_safe_planner import FailSafePlanner
from src_extension.adaptation.adaptation_results import FailSafeAdaptationSpace
from src_extension.planning.planning_coordinator import PlanningCoordinator, _analysis_triggers


def _information_trigger(*, confidence: float) -> InformationTrigger:
    return InformationTrigger(
        trigger_type="INFORMATION_INSUFFICIENT",
        severity=Severity.HIGH,
        confidence=confidence,
        scope=Scope.GLOBAL,
        affected_entities=("uav_0",),
        timestamp=1.0,
        recommended_planner="fail_safe_planner",
        explanation_context="insufficient coverage",
    )


def test_normalize_triggers_from_trigger_batch_object() -> None:
    batch = TriggerBatch(
        triggers=(
            TriggerSignal(name="SEARCH_MODE_REQUIRED", confidence=0.9, source="test"),
        ),
        source="test",
        timestamp=2.0,
        step_index=3,
    )
    normalized = normalize_triggers(batch)
    assert normalized is batch
    assert normalized.triggers[0].name == "SEARCH_MODE_REQUIRED"


def test_normalize_triggers_from_dict_all_triggers() -> None:
    batch = normalize_triggers(
        {
            "all_triggers": (
                {"trigger_type": "CRITICAL_BATTERY", "confidence": 0.95},
                {"trigger_type": "COLLISION_RISK", "confidence": 0.8},
            )
        }
    )
    names = {signal.name for signal in batch.triggers}
    assert names == {"CRITICAL_BATTERY", "COLLISION_RISK"}


def test_normalize_triggers_from_tuple_and_string() -> None:
    batch = normalize_triggers(("SEARCH_MODE_REQUIRED", "CRITICAL_BATTERY"))
    assert [signal.name for signal in batch.triggers] == [
        "SEARCH_MODE_REQUIRED",
        "CRITICAL_BATTERY",
    ]


def test_low_confidence_information_trigger_ignored_by_safety_checker() -> None:
    checker = SafetyChecker()
    low = {"triggers": (_information_trigger(confidence=0.2),)}
    high = {"triggers": (_information_trigger(confidence=0.8),)}

    assert FailSafeReason.INFORMATION_INSUFFICIENT.value not in checker.extract_fail_safe_reasons(
        analysis_snapshot=low
    )
    assert FailSafeReason.INFORMATION_INSUFFICIENT.value in checker.extract_fail_safe_reasons(
        analysis_snapshot=high
    )


def test_search_mode_required_maps_to_information_recovery() -> None:
    checker = SafetyChecker()
    reasons = checker.extract_fail_safe_reasons(
        analysis_snapshot={
            "triggers": (
                {"trigger_type": "SEARCH_MODE_REQUIRED", "confidence": 0.85},
            )
        }
    )
    assert FailSafeReason.SEARCH_MODE_REQUIRED.value in reasons
    assert checker.classify_mode(reasons) == FailSafeMode.INFORMATION_RECOVERY.value


def test_critical_battery_maps_correctly() -> None:
    checker = SafetyChecker()
    reasons = checker.extract_fail_safe_reasons(
        analysis_snapshot={
            "triggers": ({"trigger_type": "CRITICAL_BATTERY", "confidence": 0.9},),
        }
    )
    assert FailSafeReason.CRITICAL_BATTERY.value in reasons


def test_fail_safe_planner_uses_normalized_object_snapshot() -> None:
    structured = _information_trigger(confidence=0.85)
    snapshot = AnalysisSnapshot(
        timestamp=1.0,
        local_results=(),
        global_result=GlobalAnalysisResult(
            timestamp=1.0,
            trigger_list=(structured,),
            system_health_summary="",
            risk_flags=(),
            priority_updates=(),
            fail_safe_flags=(),
            uncertainty_summary="",
            information_summary="",
            trend_summary="",
            explanation_context="",
        ),
        all_triggers=(structured,),
        dashboard_summary="",
    )
    planner = FailSafePlanner()
    decision = planner.plan(
        1,
        analysis_snapshot=snapshot,
        fail_safe_space=FailSafeAdaptationSpace(options=[]),
        timestamp=1.0,
    )
    assert decision is not None
    assert decision.search_mode_active is True
    assert decision.mission_mode == "information_recovery"


def test_analysis_result_exposes_trigger_batch_alias() -> None:
    trigger = ResourceTrigger(
        trigger_type="CRITICAL_BATTERY",
        severity=Severity.CRITICAL,
        confidence=0.9,
        scope=Scope.LOCAL,
        affected_entities=("2500",),
        timestamp=4.0,
        recommended_planner="fail_safe_planner",
        explanation_context="battery low",
    )
    local = LocalAnalysisResult(
        uav_id="2500",
        timestamp=4.0,
        local_trigger_list=(trigger,),
        local_risk_summary="",
        path_quality_summary="",
        uncertainty_summary="",
        information_summary="",
        escalation_flags=(),
        explanation_context="",
    )
    batch = local.trigger_batch
    assert isinstance(batch, TriggerBatch)
    assert batch.triggers[0].name == "CRITICAL_BATTERY"
    assert local.triggers.triggers[0].name == "CRITICAL_BATTERY"


def test_trigger_signal_passes_information_confidence_gate() -> None:
    low = TriggerSignal(name="SEARCH_MODE_REQUIRED", confidence=0.4)
    high = TriggerSignal(name="SEARCH_MODE_REQUIRED", confidence=0.8)
    assert trigger_signal_passes_information_confidence(low) is False
    assert trigger_signal_passes_information_confidence(high) is True


def test_mode_manager_accepts_trigger_batch_on_snapshot() -> None:
    batch = trigger_batch_from_structured(
        (_information_trigger(confidence=0.85),),
        source="test",
        timestamp=1.0,
    )

    @dataclass(frozen=True)
    class _Snapshot:
        triggers: TriggerBatch

    manager = ModeManager(SafetyChecker())
    state = manager.update(analysis_snapshot=_Snapshot(triggers=batch), timestamp=1.0)
    assert state.mode == FailSafeMode.INFORMATION_RECOVERY


def test_mode_manager_accepts_dict_all_triggers() -> None:
    manager = ModeManager(SafetyChecker())
    state = manager.update(
        analysis_snapshot={
            "all_triggers": (
                {"trigger_type": "SEARCH_MODE_REQUIRED", "confidence": 0.85},
            )
        },
        timestamp=1.0,
    )
    assert state.mode == FailSafeMode.INFORMATION_RECOVERY


def test_planning_coordinator_uses_trigger_batch_from_snapshot() -> None:
    structured = _information_trigger(confidence=0.85)
    snapshot = AnalysisSnapshot(
        timestamp=1.0,
        local_results=(),
        global_result=GlobalAnalysisResult(
            timestamp=1.0,
            trigger_list=(structured,),
            system_health_summary="",
            risk_flags=(),
            priority_updates=(),
            fail_safe_flags=(),
            uncertainty_summary="",
            information_summary="",
            trend_summary="",
            explanation_context="",
        ),
        all_triggers=(structured,),
        dashboard_summary="",
    )
    coordinator = PlanningCoordinator()
    result = coordinator.run_planning(
        adaptation_space_snapshot={"fail_safe_space": FailSafeAdaptationSpace(options=[])},
        analysis_snapshot=snapshot,
        timestamp=1.0,
    )
    decision = result["fail_safe_decision"]
    assert decision is not None
    assert decision.search_mode_active is True
    assert decision.mission_mode == "information_recovery"


def test_analysis_triggers_falls_back_to_global_trigger_list() -> None:
    batch = _analysis_triggers(
        {
            "global_result": {
                "trigger_list": (
                    {"trigger_type": "SEARCH_MODE_REQUIRED", "confidence": 0.85},
                )
            }
        }
    )
    assert batch is not None
    assert batch.triggers[0].name == "SEARCH_MODE_REQUIRED"


def test_planning_coordinator_falls_back_to_legacy_trigger_list() -> None:
    coordinator = PlanningCoordinator()
    result = coordinator.run_planning(
        adaptation_space_snapshot={"fail_safe_space": FailSafeAdaptationSpace(options=[])},
        analysis_snapshot={
            "global_result": {
                "trigger_list": (
                    {"trigger_type": "SEARCH_MODE_REQUIRED", "confidence": 0.85},
                )
            }
        },
        timestamp=1.0,
    )
    decision = result["fail_safe_decision"]
    assert decision is not None
    assert decision.search_mode_active is True


def test_mode_manager_backward_compatible_with_triggers_field() -> None:
    manager = ModeManager(SafetyChecker())
    state = manager.update(
        analysis_snapshot={
            "triggers": (
                {"trigger_type": "CRITICAL_BATTERY", "confidence": 0.9},
            )
        },
        timestamp=1.0,
    )
    assert FailSafeReason.CRITICAL_BATTERY in state.active_reasons
    assert state.mode == FailSafeMode.DEGRADED
