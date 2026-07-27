"""Rescue adaptation space generator skeleton."""

from typing import Any

from ..planning.mission_goal_integration import (
    boost_confidence,
    dynamic_metric,
    failsafe_restricts_rescue,
    goal_priority_enabled,
    mission_goal_option_metadata,
    read_mission_goals,
)
from .adaptation_option_objects import AdaptationOption, RescueAdaptationOption, Scope
from .trigger_input import adaptation_trigger_metadata
from .adaptation_results import RescueAdaptationSpace


class RescueAdaptationSpaceGenerator:
    """Builds rescue adaptation option spaces."""

    @staticmethod
    def _merge_rescue_goal_parameters(
        parameters: dict[str, Any],
        mission_goals: dict[str, Any],
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        merged = dict(parameters)
        merged.update(mission_goal_option_metadata(mission_goals, reason=reason))
        if mission_goals:
            merged["rescue_urgency"] = int(dynamic_metric(mission_goals, "alive_victims_remaining", 0) or 0)
            merged["active_rescues"] = int(dynamic_metric(mission_goals, "active_rescues", 0) or 0)
            merged["alive_firefighters"] = int(dynamic_metric(mission_goals, "alive_firefighters", 0) or 0)
        return merged

    def _generate_rescue_noop_option(
        self,
        rescue_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> RescueAdaptationOption:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, _, _, trigger_signals = adaptation_trigger_metadata(
            rescue_analysis_result,
            default_label="rescue_analysis",
        )
        target_entity = read_value(rescue_analysis_result, "target_entity", "rescue_target")
        mission_goals = read_mission_goals(runtime_models)

        return RescueAdaptationOption(
            option_id="rescue_stability_maintain_current_rescue_state",
            option_type="stability_control",
            target_entity=target_entity,
            parameters=self._merge_rescue_goal_parameters(
                {
                    "stability_action": "maintain_current_rescue_state",
                    "do_nothing": True,
                },
                mission_goals,
                reason="rescue_baseline",
            ),
            expected_effect="Keep current rescue coordination state; no adaptation applied",
            cost_estimate=0.0,
            risk_estimate=0.0,
            confidence=1.0,
            scope=Scope.rescue,
            timestamp=timestamp,
            originating_trigger=originating_trigger,
            explanation_hint=(
                "Do-nothing rescue baseline; always present for stability comparison"
            ),
        )

    def generate(
        self,
        rescue_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> RescueAdaptationSpace:
        options: list[AdaptationOption] = []

        options.extend(
            self._generate_victim_handling_options(
                rescue_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_rescue_decision_options(
                rescue_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_firefighter_assignment_options(
                rescue_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_route_options(
                rescue_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.append(
            self._generate_rescue_noop_option(
                rescue_analysis_result,
                runtime_models,
                timestamp,
            )
        )

        return RescueAdaptationSpace(
            options=options,
            trigger_references=[],
            explanation_summaries=[],
            timestamp=timestamp,
        )

    def _generate_victim_handling_options(
        self,
        rescue_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, _, confidence, trigger_signals = adaptation_trigger_metadata(
            rescue_analysis_result,
            default_label="rescue_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)
        mission_goals = read_mission_goals(runtime_models)

        victim_confidence = read_value(
            rescue_analysis_result,
            "victim_confidence",
            read_value(runtime_models, "victim_confidence", None),
        )
        low_victim_confidence = (
            isinstance(victim_confidence, (int, float)) and victim_confidence < 0.5
        )
        target_entity = read_value(rescue_analysis_result, "target_entity", "rescue_target")
        base_parameters = self._merge_rescue_goal_parameters(
            {
                "victim_confidence": victim_confidence,
                "confirmation_required": low_victim_confidence,
            },
            mission_goals,
            reason="victim_handling",
        )
        victim_options = [
            (
                "confirm_victim",
                "confirm_victim",
                "Confirm victim detection",
                "Low victim confidence requires confirmation before rescue action.",
            ),
            (
                "track_victim",
                "track_victim",
                "Track victim location",
                "Victim tracking option only; no rescue action is executed.",
            ),
            (
                "ignore_low_confidence_detection",
                "ignore_low_confidence_detection",
                "Ignore low-confidence victim detection",
                "Low-confidence detections can be ignored as an option only.",
            ),
        ]

        return [
            RescueAdaptationOption(
                option_id=f"rescue_victim_handling_{option_id}",
                option_type="victim_handling",
                target_entity=target_entity,
                parameters={**base_parameters, "victim_action": action},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope.rescue,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, expected_effect, explanation_hint in victim_options
        ]

    def _generate_rescue_decision_options(
        self,
        rescue_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, _, confidence, trigger_signals = adaptation_trigger_metadata(
            rescue_analysis_result,
            default_label="rescue_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)
        mission_goals = read_mission_goals(runtime_models)
        failsafe_restricted = failsafe_restricts_rescue(mission_goals)

        communication_reliability = read_value(
            rescue_analysis_result,
            "communication_reliability",
            read_value(runtime_models, "communication_reliability", None),
        )
        unreliable_communication = (
            isinstance(communication_reliability, (int, float))
            and communication_reliability < 0.5
        )
        target_entity = read_value(rescue_analysis_result, "target_entity", "rescue_target")
        base_parameters = self._merge_rescue_goal_parameters(
            {
                "communication_reliability": communication_reliability,
                "unreliable_communication": unreliable_communication,
            },
            mission_goals,
            reason="rescue_decision",
        )
        decision_options = [
            (
                "delay_rescue",
                "delay_rescue",
                {
                    "preferred_under_unreliable_communication": unreliable_communication,
                    "preferred_under_failsafe": failsafe_restricted,
                },
                "Delay rescue decision",
                "Unreliable communication should prefer rescue delay.",
            ),
            (
                "cancel_rescue",
                "cancel_rescue",
                {
                    "preferred_under_failsafe": failsafe_restricted,
                    "unreachable_candidate": failsafe_restricted,
                },
                "Cancel rescue decision",
                "Rescue cancellation option only; no rescue action is executed.",
            ),
            (
                "escalate_to_operator",
                "escalate_to_operator",
                {
                    "preferred_under_failsafe": failsafe_restricted,
                },
                "Escalate rescue decision to operator",
                "Operator escalation option only; no rescue action is executed.",
            ),
        ]

        options: list[AdaptationOption] = []
        for option_id, action, parameters, expected_effect, explanation_hint in decision_options:
            merged = self._merge_rescue_goal_parameters(
                {**base_parameters, **parameters, "rescue_action": action},
                mission_goals,
                reason="failsafe_rescue_delay_cancel"
                if failsafe_restricted and action in {"delay_rescue", "cancel_rescue"}
                else "rescue_decision",
            )
            option_confidence = confidence
            if goal_priority_enabled(mission_goals, "prioritize_rescue_completion") and action not in {
                "delay_rescue",
                "cancel_rescue",
            }:
                option_confidence = boost_confidence(option_confidence, 0.1)
            options.append(
                RescueAdaptationOption(
                    option_id=f"rescue_decision_{option_id}",
                    option_type="rescue_decision",
                    target_entity=target_entity,
                    parameters=merged,
                    expected_effect=expected_effect,
                    cost_estimate=1.0,
                    risk_estimate=0.2,
                    confidence=option_confidence,
                    scope=Scope.rescue,
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint=explanation_hint,
                )
            )
        return options

    def _generate_firefighter_assignment_options(
        self,
        rescue_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, _, confidence, trigger_signals = adaptation_trigger_metadata(
            rescue_analysis_result,
            default_label="rescue_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)
        mission_goals = read_mission_goals(runtime_models)

        nearest_firefighter = read_value(
            rescue_analysis_result,
            "nearest_firefighter",
            read_value(runtime_models, "nearest_firefighter", None),
        )
        firefighter_candidates = read_value(
            rescue_analysis_result,
            "firefighter_candidates",
            read_value(runtime_models, "firefighter_candidates", []),
        )
        target_entity = read_value(rescue_analysis_result, "target_entity", "rescue_target")
        alive_firefighters = int(dynamic_metric(mission_goals, "alive_firefighters", 0) or 0)
        resource_constrained = alive_firefighters <= 1
        option_confidence = confidence
        if goal_priority_enabled(mission_goals, "prioritize_rescue_completion"):
            option_confidence = boost_confidence(option_confidence, 0.1)
        if resource_constrained:
            option_confidence = boost_confidence(option_confidence, 0.05)

        return [
            RescueAdaptationOption(
                option_id="rescue_firefighter_assignment_nearest",
                option_type="firefighter_assignment",
                target_entity=target_entity,
                parameters=self._merge_rescue_goal_parameters(
                    {
                        "assignment_action": "assign_nearest_firefighter",
                        "nearest_firefighter": nearest_firefighter,
                        "firefighter_candidates": firefighter_candidates,
                        "resource_constrained": resource_constrained,
                        "mission_goal_boost": goal_priority_enabled(
                            mission_goals, "prioritize_rescue_completion"
                        ),
                    },
                    mission_goals,
                    reason="prioritize_rescue_completion"
                    if goal_priority_enabled(mission_goals, "prioritize_rescue_completion")
                    else "resource_aware_assignment",
                ),
                expected_effect="Assign nearest firefighter",
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=option_confidence,
                scope=Scope.rescue,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint="Nearest firefighter assignment option only.",
            )
        ]

    def _generate_route_options(
        self,
        rescue_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, _, confidence, trigger_signals = adaptation_trigger_metadata(
            rescue_analysis_result,
            default_label="rescue_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)
        mission_goals = read_mission_goals(runtime_models)

        safest_route = read_value(
            rescue_analysis_result,
            "safest_route",
            read_value(runtime_models, "safest_route", None),
        )
        uncertainty_map = read_value(
            rescue_analysis_result,
            "uncertainty_map",
            read_value(runtime_models, "uncertainty_map", {}),
        )
        route_candidates = read_value(
            rescue_analysis_result,
            "route_candidates",
            read_value(runtime_models, "route_candidates", []),
        )
        target_entity = read_value(rescue_analysis_result, "target_entity", "rescue_target")
        base_parameters = self._merge_rescue_goal_parameters(
            {
                "safest_route": safest_route,
                "uncertainty_map": uncertainty_map,
                "route_candidates": route_candidates,
            },
            mission_goals,
            reason="rescue_route_planning",
        )
        route_options = [
            (
                "assign_safest_route",
                "assign_safest_route",
                "Assign safest rescue route",
                "Route planning option only; no rescue route is executed.",
            ),
            (
                "uncertainty_aware_routing",
                "uncertainty_aware_routing",
                "Use uncertainty-aware rescue routing",
                "Route planning option only; no rescue route is executed.",
            ),
        ]

        return [
            RescueAdaptationOption(
                option_id=f"rescue_route_{option_id}",
                option_type="route_planning",
                target_entity=target_entity,
                parameters={**base_parameters, "route_action": action},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope.rescue,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, expected_effect, explanation_hint in route_options
        ]
