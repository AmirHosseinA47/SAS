"""Adaptation generators consume normalized TriggerBatch / legacy trigger fields."""

from __future__ import annotations

from src_extension.adaptation.failsafe_adaptation_generator import FailSafeAdaptationGenerator
from src_extension.adaptation.global_adaptation_generator import GlobalAdaptationSpaceGenerator
from src_extension.adaptation.local_adaptation_generator import LocalAdaptationSpaceGenerator
from src_extension.analysis.trigger_objects import (
    TriggerBatch,
    TriggerSignal,
    trigger_batch_from_structured,
)
from src_extension.analysis.trigger_objects import InformationTrigger, ResourceTrigger, Scope, Severity


def _information_trigger(*, confidence: float) -> InformationTrigger:
    return InformationTrigger(
        trigger_type="INFORMATION_INSUFFICIENT",
        severity=Severity.HIGH,
        confidence=confidence,
        scope=Scope.GLOBAL,
        affected_entities=("mission",),
        timestamp=1.0,
        recommended_planner="fail_safe_planner",
        explanation_context="insufficient coverage",
    )


def _battery_trigger(*, confidence: float = 0.9) -> ResourceTrigger:
    return ResourceTrigger(
        trigger_type="CRITICAL_BATTERY",
        severity=Severity.CRITICAL,
        confidence=confidence,
        scope=Scope.LOCAL,
        affected_entities=("2500",),
        timestamp=1.0,
        recommended_planner="fail_safe_planner",
        explanation_context="battery low",
    )


def test_failsafe_generator_accepts_trigger_batch() -> None:
    batch = trigger_batch_from_structured(
        (_battery_trigger(),),
        source="analysis_snapshot",
        timestamp=1.0,
    )
    space = FailSafeAdaptationGenerator().generate(
        {"trigger_batch": batch, "target_entity": "mission"},
        runtime_models={},
        timestamp=1.0,
    )
    uav_options = [option for option in space.options if option.option_type == "uav_failsafe"]
    assert uav_options
    assert "CRITICAL_BATTERY" in uav_options[0].originating_trigger


def test_global_generator_accepts_legacy_all_triggers() -> None:
    space = GlobalAdaptationSpaceGenerator().generate(
        {
            "all_triggers": (
                {
                    "trigger_type": "SEARCH_MODE_REQUIRED",
                    "confidence": 0.85,
                    "explanation_context": "search mode required",
                },
            ),
            "target_entity": "mission",
            "fire_probability_map": {"r1": 0.9},
            "fire_confidence_map": {"r1": 0.2},
            "uncertainty_map": {"r1": 0.8},
            "battery": {"uav-1": 0.2},
        },
        runtime_models={"battery": {"uav-1": 0.2}},
        timestamp=1.0,
    )
    assert "global_coverage_strategy_search_mode_activation" in {
        option.option_id for option in space.options
    }


def test_search_mode_required_produces_information_recovery_options() -> None:
    batch = TriggerBatch(
        triggers=(
            TriggerSignal(
                name="SEARCH_MODE_REQUIRED",
                confidence=0.85,
                source="test",
                metadata={"explanation_context": "search mode required"},
            ),
        ),
        source="test",
        timestamp=1.0,
    )
    space = FailSafeAdaptationGenerator().generate(
        {"trigger_batch": batch, "target_entity": "mission"},
        runtime_models={},
        timestamp=1.0,
    )
    mission_options = [
        option for option in space.options if option.option_type == "mission_failsafe"
    ]
    assert mission_options
    search_mode = next(
        option for option in mission_options if option.parameters.get("failsafe_action") == "search_mode"
    )
    assert search_mode.parameters.get("information_insufficient") is False
    assert "SEARCH_MODE_REQUIRED" in search_mode.originating_trigger


def test_information_insufficient_produces_search_mode_mission_options() -> None:
    batch = trigger_batch_from_structured(
        (_information_trigger(confidence=0.85),),
        source="test",
        timestamp=1.0,
    )
    space = FailSafeAdaptationGenerator().generate(
        {"trigger_batch": batch, "target_entity": "mission"},
        runtime_models={},
        timestamp=1.0,
    )
    mission_options = [
        option for option in space.options if option.option_type == "mission_failsafe"
    ]
    assert any(option.parameters.get("information_insufficient") is True for option in mission_options)


def test_critical_battery_creates_failsafe_uav_options() -> None:
    space = FailSafeAdaptationGenerator().generate(
        {
            "triggers": ({"trigger_type": "CRITICAL_BATTERY", "confidence": 0.9},),
            "target_entity": "2500",
        },
        runtime_models={"uav_id": "2500"},
        timestamp=1.0,
    )
    uav_options = [option for option in space.options if option.option_type == "uav_failsafe"]
    assert {option.parameters.get("failsafe_action") for option in uav_options} >= {
        "return_to_base",
        "hold_position",
    }
    assert all("CRITICAL_BATTERY" in option.originating_trigger for option in uav_options)


def test_low_confidence_information_trigger_ignored_in_failsafe_metadata() -> None:
    space = FailSafeAdaptationGenerator().generate(
        {
            "all_triggers": (_information_trigger(confidence=0.2),),
            "target_entity": "mission",
        },
        runtime_models={},
        timestamp=1.0,
    )
    mission_options = [
        option for option in space.options if option.option_type == "mission_failsafe"
    ]
    assert mission_options
    assert all(option.parameters.get("information_insufficient") is False for option in mission_options)
    assert mission_options[0].originating_trigger == "fail_safe_analysis"


def test_local_generator_accepts_trigger_batch_for_search_mode() -> None:
    batch = trigger_batch_from_structured(
        (
            InformationTrigger(
                trigger_type="SEARCH_MODE_REQUIRED",
                severity=Severity.HIGH,
                confidence=0.85,
                scope=Scope.LOCAL,
                affected_entities=("uav-1",),
                timestamp=1.0,
                recommended_planner="local_uav_path_planner",
                explanation_context="search mode required",
            ),
        ),
        source="local_analysis:uav-1",
        timestamp=1.0,
    )
    space = LocalAdaptationSpaceGenerator().generate(
        {
            "trigger_batch": batch,
            "triggers": (),
            "target_entity": "uav-1",
            "local_uncertainty": {(1, 1): 0.9},
            "belief_gain": {(1, 1): 0.7},
            "drift_state": "high",
            "stale_regions": [(1, 1)],
        },
        local_models={
            "local_uncertainty": {(1, 1): 0.9},
            "belief_gain": {(1, 1): 0.7},
            "drift_state": "high",
        },
        runtime_models={"uav_id": "uav-1"},
        timestamp=1.0,
    )
    assert any("search" in option.option_id for option in space.options)


def test_legacy_triggers_field_still_works_for_global_generator() -> None:
    space = GlobalAdaptationSpaceGenerator().generate(
        {
            "triggers": (
                {
                    "trigger_type": "INFORMATION_INSUFFICIENT",
                    "confidence": 0.85,
                    "explanation_context": "information insufficient",
                },
            ),
            "target_entity": "mission",
            "fire_probability_map": {},
            "fire_confidence_map": {},
            "uncertainty_map": {},
            "battery": {},
        },
        runtime_models={},
        timestamp=1.0,
    )
    assert any(option.option_type == "fail_safe_mission" for option in space.options)
