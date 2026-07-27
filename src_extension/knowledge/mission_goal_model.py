"""Managing system: mission goals and constraints runtime knowledge.

Live mission goals are refreshed each simulation step from operational state.
Legacy Step-4 fields remain for backward-compatible consumers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MISSION_PHASES = frozenset(
    {
        "exploration",
        "rescue_active",
        "evacuation",
        "degraded_operation",
        "emergency",
    }
)

DEFAULT_GOAL_PRIORITIES: dict[str, bool] = {
    "prioritize_victim_search": False,
    "prioritize_rescue_completion": False,
    "prioritize_fire_perimeter_tracking": True,
    "prioritize_information_gain": True,
    "prioritize_uav_survivability": False,
}

DEFAULT_OPERATIONAL_CONSTRAINTS: dict[str, bool] = {
    "avoid_fire_entry": True,
    "avoid_smoke_entry": True,
    "maintain_uav_spacing": True,
    "preserve_battery_margin": True,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _read_context(context: dict[str, Any], key: str, default: Any = None) -> Any:
    return context.get(key, default)


@dataclass
class MissionGoalModel:
    """Typed mission goal/constraint knowledge with live runtime fields."""

    adaptation_goals: list[str] = field(default_factory=list)
    goal_weights: dict[str, float] = field(default_factory=dict)
    hard_constraints: dict[str, Any] = field(default_factory=dict)
    soft_preferences: dict[str, Any] = field(default_factory=dict)
    priority_ordering: list[str] = field(default_factory=list)
    safety_thresholds: dict[str, float] = field(default_factory=dict)
    resource_thresholds: dict[str, float] = field(default_factory=dict)
    uncertainty_tolerance_thresholds: dict[str, float] = field(default_factory=dict)

    mission_phase: str = "exploration"
    goal_priorities: dict[str, bool] = field(
        default_factory=lambda: dict(DEFAULT_GOAL_PRIORITIES)
    )
    dynamic_metrics: dict[str, Any] = field(default_factory=dict)
    operational_constraints: dict[str, bool] = field(
        default_factory=lambda: dict(DEFAULT_OPERATIONAL_CONSTRAINTS)
    )
    last_updated: float = 0.0
    step_index: int = 0

    def get_threshold(self, name: str, default: Any = None) -> Any:
        """Return threshold by name across supported threshold categories."""
        for bucket in (
            self.safety_thresholds,
            self.resource_thresholds,
            self.uncertainty_tolerance_thresholds,
        ):
            if name in bucket:
                return bucket[name]
        if name in self.hard_constraints:
            return self.hard_constraints[name]
        return default

    def set_threshold(self, category: str, name: str, value: float) -> None:
        """Set one threshold value in a known category."""
        category_key = category.strip().lower()
        if category_key == "safety":
            self.safety_thresholds[name] = float(value)
        elif category_key == "resource":
            self.resource_thresholds[name] = float(value)
        elif category_key == "uncertainty":
            self.uncertainty_tolerance_thresholds[name] = float(value)
        else:
            raise ValueError(
                "Unknown threshold category. Use 'safety', 'resource', or 'uncertainty'."
            )

    @property
    def min_battery(self) -> float | None:
        value = self.resource_thresholds.get("min_battery")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def max_risk_estimate(self) -> float | None:
        value = self.hard_constraints.get("max_risk_estimate")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def forbidden_actions(self) -> tuple[str, ...]:
        raw = self.hard_constraints.get("forbidden_actions", ())
        if isinstance(raw, (list, tuple, set, frozenset)):
            return tuple(str(item) for item in raw)
        return ()

    def goal_priority(self, name: str) -> bool:
        return bool(self.goal_priorities.get(name, False))

    def constraint_enabled(self, name: str) -> bool:
        return bool(self.operational_constraints.get(name, False))

    def utility_weight_mode(self) -> str:
        """Map live mission posture to a known utility weight profile."""
        fail_safe_mode = str(
            self.dynamic_metrics.get("active_fail_safe_mode", "normal") or "normal"
        ).strip().lower()
        if fail_safe_mode == "information_recovery":
            return "information_recovery_mode"
        if fail_safe_mode in {"safety_first", "emergency"}:
            return "safety_first_mode"
        if fail_safe_mode == "degraded":
            return "battery_constrained_mode"
        phase_mode = {
            "emergency": "safety_first_mode",
            "degraded_operation": "battery_constrained_mode",
            "evacuation": "victim_support_mode",
            "rescue_active": "victim_support_mode",
            "exploration": "normal_monitoring_mode",
        }
        return phase_mode.get(self.mission_phase, "normal_monitoring_mode")

    def runtime_context(self) -> dict[str, Any]:
        """Planner/adaptation-facing read-only mission goal context."""
        return {
            "mission_phase": self.mission_phase,
            "goal_priorities": dict(self.goal_priorities),
            "dynamic_metrics": dict(self.dynamic_metrics),
            "operational_constraints": dict(self.operational_constraints),
            "utility_weight_mode": self.utility_weight_mode(),
            "goal_weights": dict(self.goal_weights),
            "hard_constraints": dict(self.hard_constraints),
            "resource_thresholds": dict(self.resource_thresholds),
        }

    def refresh_from_runtime(self, context: dict[str, Any]) -> None:
        """Update live mission goals from one simulation-step context."""
        timestamp = float(_read_context(context, "timestamp", self.last_updated) or 0.0)
        self.step_index = int(_read_context(context, "step_index", self.step_index) or 0)
        self.last_updated = timestamp

        alive_victims = int(_read_context(context, "alive_victims_remaining", 0) or 0)
        active_rescues = int(_read_context(context, "active_rescues", 0) or 0)
        alive_firefighters = int(_read_context(context, "alive_firefighters", 0) or 0)
        fire_severity = _clamp01(float(_read_context(context, "fire_severity_estimate", 0.0) or 0.0))
        coverage_ratio = _clamp01(float(_read_context(context, "coverage_ratio", 0.0) or 0.0))
        fail_safe_mode = str(
            _read_context(context, "active_fail_safe_mode", "normal") or "normal"
        ).strip().lower()

        self.dynamic_metrics = {
            "alive_victims_remaining": alive_victims,
            "active_rescues": active_rescues,
            "alive_firefighters": alive_firefighters,
            "fire_severity_estimate": fire_severity,
            "coverage_ratio": coverage_ratio,
            "active_fail_safe_mode": fail_safe_mode,
        }

        self.mission_phase = self._derive_mission_phase(
            fail_safe_mode=fail_safe_mode,
            active_rescues=active_rescues,
            alive_victims=alive_victims,
            fire_severity=fire_severity,
        )
        self.goal_priorities = self._derive_goal_priorities(
            mission_phase=self.mission_phase,
            fail_safe_mode=fail_safe_mode,
            active_rescues=active_rescues,
            alive_victims=alive_victims,
            coverage_ratio=coverage_ratio,
        )
        self.operational_constraints = self._derive_operational_constraints(
            mission_phase=self.mission_phase,
            fail_safe_mode=fail_safe_mode,
            fire_severity=fire_severity,
        )
        self._sync_legacy_fields()

    @staticmethod
    def _derive_mission_phase(
        *,
        fail_safe_mode: str,
        active_rescues: int,
        alive_victims: int,
        fire_severity: float,
    ) -> str:
        if fail_safe_mode == "emergency":
            return "emergency"
        if active_rescues > 0:
            return "rescue_active"
        if fail_safe_mode in {"degraded", "safety_first", "information_recovery"}:
            return "degraded_operation"
        if fire_severity >= 0.65 and alive_victims > 0:
            return "evacuation"
        return "exploration"

    @staticmethod
    def _derive_goal_priorities(
        *,
        mission_phase: str,
        fail_safe_mode: str,
        active_rescues: int,
        alive_victims: int,
        coverage_ratio: float,
    ) -> dict[str, bool]:
        priorities = dict(DEFAULT_GOAL_PRIORITIES)
        if mission_phase == "rescue_active":
            priorities["prioritize_rescue_completion"] = True
            priorities["prioritize_victim_search"] = True
        elif mission_phase == "evacuation":
            priorities["prioritize_victim_search"] = True
            priorities["prioritize_uav_survivability"] = True
        elif mission_phase == "exploration":
            priorities["prioritize_information_gain"] = coverage_ratio < 0.55
            priorities["prioritize_fire_perimeter_tracking"] = True
            if alive_victims > 0:
                priorities["prioritize_victim_search"] = True
        elif mission_phase == "degraded_operation":
            priorities["prioritize_uav_survivability"] = True
            priorities["prioritize_information_gain"] = fail_safe_mode == "information_recovery"
        elif mission_phase == "emergency":
            priorities["prioritize_uav_survivability"] = True
            priorities["prioritize_rescue_completion"] = active_rescues > 0
        return priorities

    @staticmethod
    def _derive_operational_constraints(
        *,
        mission_phase: str,
        fail_safe_mode: str,
        fire_severity: float,
    ) -> dict[str, bool]:
        constraints = dict(DEFAULT_OPERATIONAL_CONSTRAINTS)
        if mission_phase in {"emergency", "degraded_operation", "evacuation"}:
            constraints["avoid_fire_entry"] = True
            constraints["avoid_smoke_entry"] = True
            constraints["preserve_battery_margin"] = True
        if fail_safe_mode in {"emergency", "safety_first"}:
            constraints["maintain_uav_spacing"] = True
        if fire_severity >= 0.8:
            constraints["avoid_fire_entry"] = True
        return constraints

    def _sync_legacy_fields(self) -> None:
        self.goal_weights = {
            key: 1.0 if enabled else 0.25 for key, enabled in self.goal_priorities.items()
        }
        active_goals = [name for name, enabled in self.goal_priorities.items() if enabled]
        self.adaptation_goals = active_goals or ["maintain_situational_awareness"]
        self.priority_ordering = sorted(
            self.goal_priorities,
            key=lambda name: (0 if self.goal_priorities[name] else 1, name),
        )

        max_risk = 0.85
        min_battery = 0.15
        forbidden_actions: list[str] = []
        if self.mission_phase == "emergency":
            max_risk = 0.35
            min_battery = 0.35
            forbidden_actions.extend(["abandon_task", "aggressive_pursuit"])
        elif self.mission_phase == "degraded_operation":
            max_risk = 0.55
            min_battery = 0.25
        elif self.mission_phase == "evacuation":
            max_risk = 0.45
            min_battery = 0.30

        fail_safe_mode = str(self.dynamic_metrics.get("active_fail_safe_mode", "normal"))
        if fail_safe_mode == "information_recovery":
            self.soft_preferences["prefer_information_recovery"] = True
        else:
            self.soft_preferences.pop("prefer_information_recovery", None)

        self.resource_thresholds["min_battery"] = min_battery
        self.safety_thresholds["max_risk_estimate"] = max_risk
        self.hard_constraints = {
            **self.hard_constraints,
            "max_risk_estimate": max_risk,
            "min_battery": min_battery,
            "forbidden_actions": tuple(forbidden_actions),
            "mission_phase": self.mission_phase,
            "operational_constraints": dict(self.operational_constraints),
        }

    def snapshot(self) -> dict[str, Any]:
        """Read-only knowledge snapshot (no planning side effects)."""
        payload = asdict(self)
        payload["utility_weight_mode"] = self.utility_weight_mode()
        payload["runtime_context"] = self.runtime_context()
        return payload

    def apply_time_decay(self, current_time: float) -> None:
        """Mission goals are refreshed each step; decay is a no-op placeholder."""
        _ = float(current_time)
