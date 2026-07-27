"""Fail-safe adaptation space generator skeleton."""

from typing import Any

from .adaptation_option_objects import AdaptationOption, FailSafeAdaptationOption, Scope
from .adaptation_results import FailSafeAdaptationSpace
from .trigger_input import adaptation_trigger_metadata


class FailSafeAdaptationGenerator:
    """Builds fail-safe adaptation option spaces."""

    def _read_value(self, source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, dict):
            return source.get(name, default)
        return getattr(source, name, default)

    def _trigger_metadata(self, fail_safe_analysis_result: Any) -> tuple[str, str, float]:
        originating_trigger, trigger_context_text, confidence, _ = adaptation_trigger_metadata(
            fail_safe_analysis_result,
            default_label="fail_safe_analysis",
        )
        return originating_trigger, trigger_context_text.upper(), confidence

    def _generate_failsafe_noop_option(
        self,
        fail_safe_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> FailSafeAdaptationOption:
        originating_trigger, _, _ = self._trigger_metadata(fail_safe_analysis_result)
        target_entity = self._read_value(
            fail_safe_analysis_result,
            "target_entity",
            self._read_value(runtime_models, "target_entity", "mission"),
        )
        return FailSafeAdaptationOption(
            option_id="failsafe_stability_maintain_current_failsafe_state",
            option_type="stability_control",
            target_entity=str(target_entity),
            parameters={
                "stability_action": "maintain_current_failsafe_state",
                "do_nothing": True,
            },
            expected_effect="Keep current fail-safe posture; no adaptation applied",
            cost_estimate=0.0,
            risk_estimate=0.0,
            confidence=1.0,
            scope=Scope.system,
            timestamp=timestamp,
            originating_trigger=originating_trigger,
            explanation_hint=(
                "Do-nothing fail-safe baseline; always present for stability comparison"
            ),
        )

    def generate(
        self,
        fail_safe_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> FailSafeAdaptationSpace:
        options: list[AdaptationOption] = []

        options.extend(
            self._generate_uav_failsafe_options(
                fail_safe_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_mission_failsafe_options(
                fail_safe_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_communication_failsafe_options(
                fail_safe_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_rescue_failsafe_options(
                fail_safe_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.append(
            self._generate_failsafe_noop_option(
                fail_safe_analysis_result,
                runtime_models,
                timestamp,
            )
        )

        return FailSafeAdaptationSpace(
            options=options,
            trigger_references=[],
            explanation_summaries=[],
            timestamp=timestamp,
        )

    def _generate_uav_failsafe_options(
        self,
        fail_safe_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        originating_trigger, trigger_context, confidence = self._trigger_metadata(
            fail_safe_analysis_result
        )
        critical_degradation = "CRITICAL" in trigger_context and (
            "DEGRADATION" in trigger_context or "FAIL" in trigger_context
        )
        target_entity = self._read_value(
            fail_safe_analysis_result,
            "target_entity",
            self._read_value(runtime_models, "uav_id", "uav"),
        )
        base_parameters = {
            "battery": self._read_value(
                fail_safe_analysis_result,
                "battery",
                self._read_value(runtime_models, "battery", None),
            ),
            "predicted_remaining_useful_time": self._read_value(
                fail_safe_analysis_result,
                "predicted_remaining_useful_time",
                self._read_value(runtime_models, "predicted_remaining_useful_time", None),
            ),
            "critical_degradation": critical_degradation,
        }
        uav_options = [
            ("return_to_base", "Return UAV to base"),
            ("low_power_mode", "Switch UAV to low-power mode"),
            ("abandon_task", "Abandon current UAV task"),
            ("hold_position", "Hold UAV position"),
        ]

        return [
            FailSafeAdaptationOption(
                option_id=f"failsafe_uav_{action}",
                option_type="uav_failsafe",
                target_entity=target_entity,
                parameters={**base_parameters, "failsafe_action": action},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope.system,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint="Fail-safe option only; no UAV behavior is executed.",
            )
            for action, expected_effect in uav_options
        ]

    def _generate_mission_failsafe_options(
        self,
        fail_safe_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        originating_trigger, trigger_context, confidence = self._trigger_metadata(
            fail_safe_analysis_result
        )
        information_insufficient = "INFORMATION_INSUFFICIENT" in trigger_context
        critical_degradation = "CRITICAL" in trigger_context and (
            "DEGRADATION" in trigger_context or "FAIL" in trigger_context
        )
        target_entity = self._read_value(fail_safe_analysis_result, "target_entity", "mission")
        base_parameters = {
            "information_insufficient": information_insufficient,
            "critical_degradation": critical_degradation,
            "mission_state": self._read_value(
                fail_safe_analysis_result,
                "mission_state",
                self._read_value(runtime_models, "mission_state", None),
            ),
        }
        mission_options = [
            ("search_mode", "Activate mission search mode"),
            ("reduce_mission_scope", "Reduce mission scope"),
            (
                "information_recovery_mission_mode",
                "Switch mission toward information recovery",
            ),
        ]

        return [
            FailSafeAdaptationOption(
                option_id=f"failsafe_mission_{action}",
                option_type="mission_failsafe",
                target_entity=target_entity,
                parameters={**base_parameters, "failsafe_action": action},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope.system,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=(
                    "INFORMATION_INSUFFICIENT triggers require search-mode options."
                    if action == "search_mode"
                    else "Fail-safe option only; no mission behavior is executed."
                ),
            )
            for action, expected_effect in mission_options
        ]

    def _generate_communication_failsafe_options(
        self,
        fail_safe_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        originating_trigger, trigger_context, confidence = self._trigger_metadata(
            fail_safe_analysis_result
        )
        critical_degradation = "CRITICAL" in trigger_context and (
            "DEGRADATION" in trigger_context or "COMMUNICATION" in trigger_context
        )
        target_entity = self._read_value(
            fail_safe_analysis_result,
            "target_entity",
            "communication_system",
        )
        base_parameters = {
            "communication_reliability": self._read_value(
                fail_safe_analysis_result,
                "communication_reliability",
                self._read_value(runtime_models, "communication_reliability", None),
            ),
            "delivery_confidence": self._read_value(
                fail_safe_analysis_result,
                "delivery_confidence",
                self._read_value(runtime_models, "delivery_confidence", None),
            ),
            "critical_degradation": critical_degradation,
        }
        communication_options = [
            ("activate_relay_uavs", "Activate relay UAV option"),
            ("prioritize_emergency_messages", "Prioritize emergency messages"),
        ]

        return [
            FailSafeAdaptationOption(
                option_id=f"failsafe_communication_{action}",
                option_type="communication_failsafe",
                target_entity=target_entity,
                parameters={**base_parameters, "failsafe_action": action},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope.system,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint="Fail-safe option only; no communication behavior is executed.",
            )
            for action, expected_effect in communication_options
        ]

    def _generate_rescue_failsafe_options(
        self,
        fail_safe_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        originating_trigger, trigger_context, confidence = self._trigger_metadata(
            fail_safe_analysis_result
        )
        critical_degradation = "CRITICAL" in trigger_context and (
            "DEGRADATION" in trigger_context or "UNSAFE" in trigger_context
        )
        target_entity = self._read_value(
            fail_safe_analysis_result,
            "target_entity",
            "rescue_target",
        )
        base_parameters = {
            "rescue_state": self._read_value(
                fail_safe_analysis_result,
                "rescue_state",
                self._read_value(runtime_models, "rescue_state", None),
            ),
            "safety_state": self._read_value(
                fail_safe_analysis_result,
                "safety_state",
                self._read_value(runtime_models, "safety_state", None),
            ),
            "critical_degradation": critical_degradation,
        }
        rescue_options = [
            ("delay_rescue", "Delay rescue under fail-safe conditions"),
            ("cancel_unsafe_rescue", "Cancel unsafe rescue"),
        ]

        return [
            FailSafeAdaptationOption(
                option_id=f"failsafe_rescue_{action}",
                option_type="rescue_failsafe",
                target_entity=target_entity,
                parameters={**base_parameters, "failsafe_action": action},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope.system,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint="Fail-safe option only; no rescue behavior is executed.",
            )
            for action, expected_effect in rescue_options
        ]
