"""Managing system: predefined fail-safe fallback strategies.

Static strategy catalog for execution-layer fallbacks; no simulator integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .failsafe_modes import FailSafeMode, FailSafeReason, normalize_mode

_RESCUE_UNSAFE_REASONS = frozenset(
    {
        FailSafeReason.RESCUE_ROUTE_UNSAFE.value,
        "rescue_unsafe",
    }
)
_COMMUNICATION_CRITICAL_REASONS = frozenset(
    {
        FailSafeReason.CRITICAL_COMMUNICATION.value,
        "critical_link_unreliable",
    }
)


@dataclass
class FallbackStrategy:
    """Predefined fallback strategy for a fail-safe mode or reason."""

    strategy_id: str
    mode: str
    target_entity: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: str = "normal"
    explanation: str = ""


class FallbackStrategyLibrary:
    """Catalog of predefined fallback strategies keyed by mode and reason."""

    def strategies_for_mode(
        self,
        mode: str,
        reasons: tuple[str, ...] | list[str] = (),
        affected_entities: tuple[str, ...] | list[str] = (),
        timestamp: float = 0.0,
    ) -> tuple[FallbackStrategy, ...]:
        mode_key = normalize_mode(mode).value
        target = self._primary_target(affected_entities)
        strategies = list(_MODE_STRATEGIES.get(mode_key, ()))
        strategies = [
            self._with_context(strategy, mode_key, target, timestamp) for strategy in strategies
        ]
        reason_keys = {self._canonical_reason(reason) for reason in reasons}
        if reason_keys & _RESCUE_UNSAFE_REASONS:
            strategies.extend(
                self._with_context(strategy, mode_key, target, timestamp)
                for strategy in _RESCUE_UNSAFE_STRATEGIES
            )
        if reason_keys & _COMMUNICATION_CRITICAL_REASONS:
            strategies.extend(
                self._with_context(strategy, mode_key, target, timestamp)
                for strategy in _COMMUNICATION_CRITICAL_STRATEGIES
            )
        return tuple(strategies)

    @staticmethod
    def strategy_to_fail_safe_action(strategy: FallbackStrategy) -> dict[str, object]:
        return {
            "strategy_id": strategy.strategy_id,
            "fail_safe_action": strategy.action,
            "mode": strategy.mode,
            "target_entity": strategy.target_entity,
            "parameters": dict(strategy.parameters),
            "priority": strategy.priority,
            "explanation": strategy.explanation,
        }

    @staticmethod
    def _primary_target(affected_entities: tuple[str, ...] | list[str]) -> str:
        if affected_entities:
            return str(affected_entities[0])
        return "system"

    @staticmethod
    def _canonical_reason(reason: str) -> str:
        return reason.strip().lower().replace("-", "_").replace(" ", "_")

    @staticmethod
    def _with_context(
        strategy: FallbackStrategy,
        mode: str,
        target_entity: str,
        timestamp: float,
    ) -> FallbackStrategy:
        parameters = dict(strategy.parameters)
        parameters.setdefault("timestamp", timestamp)
        entity = strategy.target_entity or target_entity
        return FallbackStrategy(
            strategy_id=strategy.strategy_id,
            mode=mode,
            target_entity=entity,
            action=strategy.action,
            parameters=parameters,
            priority=strategy.priority,
            explanation=strategy.explanation,
        )


def _strategy(
    strategy_id: str,
    action: str,
    *,
    mode: str = "",
    target_entity: str = "",
    parameters: dict[str, Any] | None = None,
    priority: str = "normal",
    explanation: str = "",
) -> FallbackStrategy:
    return FallbackStrategy(
        strategy_id=strategy_id,
        mode=mode,
        target_entity=target_entity,
        action=action,
        parameters=dict(parameters or {}),
        priority=priority,
        explanation=explanation or f"{action} fallback",
    )


_MODE_STRATEGIES: dict[str, tuple[FallbackStrategy, ...]] = {
    FailSafeMode.NORMAL.value: (
        _strategy("normal-maintain", "maintain_current_config", priority="low"),
    ),
    FailSafeMode.DEGRADED.value: (
        _strategy("degraded-reduce-scope", "reduce_mission_scope", priority="medium"),
        _strategy("degraded-critical-only", "critical_tasks_only", priority="medium"),
    ),
    FailSafeMode.SAFETY_FIRST.value: (
        _strategy("safety-hold", "safe_hold", priority="high"),
        _strategy("safety-retreat", "retreat_to_safe_region", priority="high"),
        _strategy(
            "safety-collision-override",
            "collision_avoidance_override",
            priority="critical",
        ),
    ),
    FailSafeMode.EMERGENCY.value: (
        _strategy("emergency-hold", "safe_hold", priority="critical"),
        _strategy("emergency-rtb", "return_to_base", priority="critical"),
        _strategy(
            "emergency-suspend-noncritical",
            "suspend_non_critical_tasks",
            priority="critical",
        ),
    ),
    FailSafeMode.INFORMATION_RECOVERY.value: (
        _strategy("info-search", "activate_search_mode", priority="high"),
        _strategy(
            "info-last-known-fire",
            "move_to_last_known_fire_region",
            priority="high",
        ),
        _strategy(
            "info-explore-uncertainty",
            "explore_high_uncertainty_regions",
            priority="high",
        ),
    ),
}

_RESCUE_UNSAFE_STRATEGIES: tuple[FallbackStrategy, ...] = (
    _strategy("rescue-delay", "delay_rescue", priority="high", explanation="delay unsafe rescue"),
    _strategy(
        "rescue-cancel",
        "cancel_unsafe_rescue",
        priority="critical",
        explanation="cancel unsafe rescue",
    ),
    _strategy(
        "rescue-escalate",
        "escalate_to_operator",
        priority="critical",
        explanation="escalate unsafe rescue to operator",
    ),
)

_COMMUNICATION_CRITICAL_STRATEGIES: tuple[FallbackStrategy, ...] = (
    _strategy(
        "comm-relay",
        "activate_relay",
        priority="high",
        explanation="activate relay for critical communication",
    ),
    _strategy(
        "comm-prioritize",
        "prioritize_critical_messages",
        priority="high",
        explanation="prioritize critical messages",
    ),
)
