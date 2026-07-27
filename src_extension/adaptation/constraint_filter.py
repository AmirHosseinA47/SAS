"""Constraint filtering for adaptation options."""

from typing import Any

from .adaptation_option_objects import AdaptationOption


class ConstraintFilter:
    """Filters adaptation options while retaining lightweight rejection reasons."""

    def __init__(self) -> None:
        self.rejected_options: list[dict[str, Any]] = []

    def filter_options(
        self,
        options: list[AdaptationOption],
        runtime_models: Any,
        mission_constraints: Any,
    ) -> list[AdaptationOption]:
        self.rejected_options = []
        filtered_options: list[AdaptationOption] = []

        for option in options:
            reasons = self._rejection_reasons(
                option,
                runtime_models,
                mission_constraints,
            )
            if reasons:
                self.rejected_options.append(
                    {
                        "option_id": option.option_id,
                        "option_type": option.option_type,
                        "reasons": reasons,
                        "explanation_hint": option.explanation_hint,
                    }
                )
                continue

            filtered_options.append(option)

        return filtered_options

    def _rejection_reasons(
        self,
        option: AdaptationOption,
        runtime_models: Any,
        mission_constraints: Any,
    ) -> list[str]:
        reasons: list[str] = []
        reasons.extend(self._safety_reasons(option, mission_constraints))
        reasons.extend(self._mission_goal_reasons(option, mission_constraints))
        reasons.extend(self._battery_reasons(option, runtime_models, mission_constraints))
        reasons.extend(
            self._communication_reasons(option, runtime_models, mission_constraints)
        )
        reasons.extend(self._feasibility_reasons(option, runtime_models, mission_constraints))
        return reasons

    def _safety_reasons(
        self,
        option: AdaptationOption,
        mission_constraints: Any,
    ) -> list[str]:
        reasons: list[str] = []
        forbidden_actions = set(self._read(mission_constraints, "forbidden_actions", ()))
        if not forbidden_actions and hasattr(mission_constraints, "forbidden_actions"):
            forbidden_actions = set(mission_constraints.forbidden_actions)
        forbidden_option_types = set(
            self._read(mission_constraints, "forbidden_option_types", ())
        )
        forbidden_scopes = set(self._read(mission_constraints, "forbidden_scopes", ()))
        max_risk = self._read(mission_constraints, "max_risk_estimate", None)
        if max_risk is None and hasattr(mission_constraints, "max_risk_estimate"):
            max_risk = mission_constraints.max_risk_estimate
        if max_risk is None and hasattr(mission_constraints, "get_threshold"):
            max_risk = mission_constraints.get_threshold("max_risk_estimate")
        action = self._option_action(option)

        if action in forbidden_actions:
            reasons.append("safety: forbidden action")
        if option.option_type in forbidden_option_types:
            reasons.append("safety: forbidden option type")
        if option.scope.value in forbidden_scopes:
            reasons.append("safety: forbidden scope")
        if isinstance(max_risk, (int, float)) and option.risk_estimate > max_risk:
            reasons.append("safety: risk estimate exceeds maximum")

        return reasons

    def _battery_reasons(
        self,
        option: AdaptationOption,
        runtime_models: Any,
        mission_constraints: Any,
    ) -> list[str]:
        battery = self._read(runtime_models, "battery", self._read(runtime_models, "battery_state"))
        min_battery = self._read(mission_constraints, "min_battery", None)
        if min_battery is None and hasattr(mission_constraints, "min_battery"):
            min_battery = mission_constraints.min_battery
        if min_battery is None and hasattr(mission_constraints, "get_threshold"):
            min_battery = mission_constraints.get_threshold("min_battery")
        required_battery = option.parameters.get(
            "required_battery",
            option.parameters.get("battery_required", None),
        )
        reasons: list[str] = []

        if (
            isinstance(battery, (int, float))
            and isinstance(min_battery, (int, float))
            and battery < min_battery
        ):
            reasons.append("battery: below mission minimum")
        if (
            isinstance(battery, (int, float))
            and isinstance(required_battery, (int, float))
            and battery < required_battery
        ):
            reasons.append("battery: below option requirement")

        return reasons

    def _communication_reasons(
        self,
        option: AdaptationOption,
        runtime_models: Any,
        mission_constraints: Any,
    ) -> list[str]:
        reliability = self._read(runtime_models, "communication_reliability", None)
        delivery_confidence = self._read(runtime_models, "delivery_confidence", None)
        min_reliability = self._read(mission_constraints, "min_communication_reliability", None)
        min_delivery = self._read(mission_constraints, "min_delivery_confidence", None)
        requires_communication = bool(option.parameters.get("requires_communication", False))
        reasons: list[str] = []

        if (
            requires_communication
            and isinstance(reliability, (int, float))
            and isinstance(min_reliability, (int, float))
            and reliability < min_reliability
        ):
            reasons.append("communication: reliability below option requirement")
        if (
            requires_communication
            and isinstance(delivery_confidence, (int, float))
            and isinstance(min_delivery, (int, float))
            and delivery_confidence < min_delivery
        ):
            reasons.append("communication: delivery confidence below option requirement")

        return reasons

    def _mission_goal_reasons(
        self,
        option: AdaptationOption,
        mission_constraints: Any,
    ) -> list[str]:
        constraints = self._read(mission_constraints, "operational_constraints", None)
        if constraints is None and hasattr(mission_constraints, "operational_constraints"):
            constraints = mission_constraints.operational_constraints
        if not isinstance(constraints, dict):
            hard = self._read(mission_constraints, "hard_constraints", {})
            if isinstance(hard, dict):
                constraints = hard.get("operational_constraints", {})
        if not isinstance(constraints, dict):
            return []

        reasons: list[str] = []
        params = option.parameters or {}
        if constraints.get("avoid_fire_entry") and bool(
            params.get("enters_fire_zone") or params.get("enter_fire_zone")
        ):
            reasons.append("mission: fire entry disallowed")
        if constraints.get("avoid_smoke_entry") and bool(
            params.get("enters_smoke_zone") or params.get("enter_smoke_zone")
        ):
            reasons.append("mission: smoke entry disallowed")
        if constraints.get("preserve_battery_margin") and bool(
            params.get("high_battery_cost") or params.get("battery_intensive")
        ):
            reasons.append("mission: battery margin preservation")
        return reasons

    def _feasibility_reasons(
        self,
        option: AdaptationOption,
        runtime_models: Any,
        mission_constraints: Any,
    ) -> list[str]:
        reasons: list[str] = []
        action = self._option_action(option)
        unavailable_actions = set(self._read(mission_constraints, "unavailable_actions", ()))
        unavailable_targets = set(self._read(mission_constraints, "unavailable_targets", ()))
        available_entities = set(self._read(runtime_models, "available_entities", ()))
        required_entities = set(option.parameters.get("required_entities", ()))

        if option.parameters.get("feasible") is False:
            reasons.append("feasibility: option marked infeasible")
        if option.parameters.get("infeasible") is True:
            reasons.append("feasibility: option marked infeasible")
        if action in unavailable_actions:
            reasons.append("feasibility: action unavailable")
        if option.target_entity in unavailable_targets:
            reasons.append("feasibility: target unavailable")
        if required_entities and not required_entities.issubset(available_entities):
            reasons.append("feasibility: required entities unavailable")

        return reasons

    def _option_action(self, option: AdaptationOption) -> Any:
        for key in (
            "action",
            "assigned_role",
            "task_action",
            "strategy",
            "resource_action",
            "path_action",
            "horizon_action",
            "movement_action",
            "sensing_action",
            "communication_action",
            "stability_action",
            "victim_action",
            "rescue_action",
            "assignment_action",
            "route_action",
            "failsafe_action",
        ):
            if key in option.parameters:
                return option.parameters[key]
        return None

    def _read(self, source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, dict):
            return source.get(name, default)
        return getattr(source, name, default)
