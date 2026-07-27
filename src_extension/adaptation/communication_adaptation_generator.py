"""Communication adaptation space generator for MAPE-K pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .adaptation_option_objects import AdaptationOption, Scope
from .trigger_input import adaptation_trigger_metadata


COMMUNICATION_MODES = frozenset(
    {
        "normal",
        "reduced_load",
        "rescue_priority",
        "fail_safe_priority",
        "degraded_communication",
        "relay_support",
    }
)


@dataclass
class CommunicationAdaptationSpace:
    options: list[AdaptationOption] = field(default_factory=list)
    trigger_references: list[str] = field(default_factory=list)
    explanation_summaries: list[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        from .adaptation_option_objects import adaptation_option_to_dict

        return {
            "options": [adaptation_option_to_dict(option) for option in self.options],
            "trigger_references": self.trigger_references,
            "explanation_summaries": self.explanation_summaries,
            "timestamp": self.timestamp,
        }


class CommunicationAdaptationGenerator:
    """Builds mission-level communication adaptation option spaces."""

    @staticmethod
    def _read(source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, dict):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _communication_snapshot(runtime_models: Any) -> dict[str, Any]:
        comm_model = CommunicationAdaptationGenerator._read(
            runtime_models, "communication_model", None
        )
        if comm_model is None:
            return {}
        snapshot = getattr(comm_model, "runtime_context", None)
        if callable(snapshot):
            result = snapshot()
            return dict(result) if isinstance(result, dict) else {}
        snapshot = getattr(comm_model, "snapshot", None)
        if callable(snapshot):
            result = snapshot()
            return dict(result) if isinstance(result, dict) else {}
        return {}

    @staticmethod
    def _delivery_confidence(runtime_models: Any, comm_snapshot: dict[str, Any]) -> float:
        dc = comm_snapshot.get("delivery_confidence")
        if dc is not None:
            return float(dc)
        state = comm_snapshot.get("state")
        if isinstance(state, dict) and state.get("delivery_confidence") is not None:
            return float(state["delivery_confidence"])
        comm_model = CommunicationAdaptationGenerator._read(
            runtime_models, "communication_model", None
        )
        if comm_model is not None:
            model_dc = getattr(getattr(comm_model, "state", None), "delivery_confidence", None)
            if model_dc is not None:
                return float(model_dc)
        return 0.75

    @staticmethod
    def _message_load(comm_snapshot: dict[str, Any]) -> int:
        load = comm_snapshot.get("message_load")
        if load is not None:
            return int(load)
        state = comm_snapshot.get("state")
        if isinstance(state, dict):
            delayed = len(state.get("delayed_messages") or [])
            failed = len(state.get("failed_messages") or [])
            sent = len(state.get("last_delivery_status") or {})
            return int(delayed + failed + sent)
        return 0

    @staticmethod
    def _link_degraded(
        delivery_confidence: float,
        comm_snapshot: dict[str, Any],
        trigger_context: str,
    ) -> bool:
        if delivery_confidence < 0.5:
            return True
        if bool(comm_snapshot.get("degraded", False)):
            return True
        if bool(comm_snapshot.get("link_degraded", False)):
            return True
        degraded_terms = (
            "communication",
            "comm",
            "delivery",
            "relay",
            "degraded",
            "unavailable",
        )
        return any(term in trigger_context for term in degraded_terms)

    @staticmethod
    def _rescue_coordination_active(runtime_models: Any, analysis_input: Any) -> bool:
        victim_model = CommunicationAdaptationGenerator._read(
            runtime_models, "victim_runtime_model", None
        )
        if victim_model is not None:
            active = getattr(victim_model, "active_rescues", None)
            if isinstance(active, (list, tuple, set)) and len(active) > 0:
                return True
            assigned = getattr(victim_model, "assigned_victims", None)
            if isinstance(assigned, (list, tuple, set)) and len(assigned) > 0:
                return True
        mission_goals = CommunicationAdaptationGenerator._read(
            runtime_models, "mission_goals", {}
        )
        if isinstance(mission_goals, dict):
            if int(mission_goals.get("active_rescues", 0) or 0) > 0:
                return True
            phase = str(mission_goals.get("mission_phase", "") or "").lower()
            if "rescue" in phase:
                return True
        triggers = CommunicationAdaptationGenerator._read(analysis_input, "triggers", ())
        for trigger in triggers or ():
            trigger_type = str(
                getattr(trigger, "trigger_type", "")
                or (trigger.get("trigger_type") if isinstance(trigger, dict) else "")
            ).upper()
            if "RESCUE" in trigger_type:
                return True
        return False

    @staticmethod
    def _fail_safe_active(runtime_models: Any) -> bool:
        simulation = CommunicationAdaptationGenerator._read(runtime_models, "simulation_model", None)
        if simulation is not None:
            fs_state = getattr(simulation, "latest_failsafe_state", None)
            if fs_state is not None:
                mode = getattr(fs_state, "mode", None)
                mode_val = getattr(mode, "value", mode)
                if str(mode_val or "").lower() not in {"", "normal"}:
                    return True
        mission_goals = CommunicationAdaptationGenerator._read(
            runtime_models, "mission_goals", {}
        )
        if isinstance(mission_goals, dict):
            fs_mode = str(mission_goals.get("active_fail_safe_mode", "") or "").lower()
            if fs_mode and fs_mode not in {"normal", "none"}:
                return True
        return False

    def _build_option(
        self,
        *,
        option_id: str,
        communication_mode: str,
        communication_action: str,
        parameters: dict[str, Any],
        expected_effect: str,
        confidence: float,
        timestamp: float,
        originating_trigger: str,
        explanation_hint: str,
        cost_estimate: float = 0.2,
        risk_estimate: float = 0.1,
    ) -> AdaptationOption:
        merged = {
            **parameters,
            "communication_mode": communication_mode,
            "communication_action": communication_action,
        }
        return AdaptationOption(
            option_id=option_id,
            option_type="communication_adaptation",
            target_entity="communication_system",
            parameters=merged,
            expected_effect=expected_effect,
            cost_estimate=cost_estimate,
            risk_estimate=risk_estimate,
            confidence=confidence,
            scope=Scope.system,
            timestamp=timestamp,
            originating_trigger=originating_trigger,
            explanation_hint=explanation_hint,
        )

    def generate(
        self,
        analysis_input: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> CommunicationAdaptationSpace:
        originating_trigger, trigger_context, confidence, trigger_signals = (
            adaptation_trigger_metadata(analysis_input, default_label="communication_analysis")
        )
        trigger_context = trigger_context.lower()
        trigger_ids = [signal.name for signal in trigger_signals]

        comm_snapshot = self._communication_snapshot(runtime_models)
        delivery_confidence = self._delivery_confidence(runtime_models, comm_snapshot)
        message_load = self._message_load(comm_snapshot)
        relay_needed = bool(comm_snapshot.get("relay_needed", False))
        link_degraded = self._link_degraded(delivery_confidence, comm_snapshot, trigger_context)
        high_load = message_load >= 4
        rescue_active = self._rescue_coordination_active(runtime_models, analysis_input)
        fail_safe_active = self._fail_safe_active(runtime_models)

        base_parameters = {
            "delivery_confidence": delivery_confidence,
            "message_load": message_load,
            "relay_needed": relay_needed,
            "link_degraded": link_degraded,
            "high_message_load": high_load,
            "rescue_coordination_active": rescue_active,
            "fail_safe_active": fail_safe_active,
            "delivery_quality": delivery_confidence,
            "sync_quality": float(comm_snapshot.get("sync_quality", delivery_confidence) or delivery_confidence),
            "critical_support": 0.85 if rescue_active else 0.35,
        }

        options: list[AdaptationOption] = [
            self._build_option(
                option_id="communication_normal",
                communication_mode="normal",
                communication_action="maintain_normal_communication",
                parameters=dict(base_parameters),
                expected_effect="Maintain normal communication load and priorities",
                confidence=max(confidence, 0.7),
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint="Baseline communication mode when links are healthy",
                cost_estimate=0.05,
                risk_estimate=0.05,
            )
        ]

        if link_degraded or delivery_confidence < 0.65:
            options.append(
                self._build_option(
                    option_id="communication_degraded_communication",
                    communication_mode="degraded_communication",
                    communication_action="apply_degraded_communication",
                    parameters={
                        **base_parameters,
                        "degraded_communication": True,
                        "reduce_non_critical_load": True,
                    },
                    expected_effect="Operate in degraded communication mode with reduced non-critical traffic",
                    confidence=min(1.0, confidence + 0.1),
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint="Degraded links favor reduced non-critical communication load",
                    cost_estimate=0.25,
                    risk_estimate=0.15,
                )
            )

        if high_load or delivery_confidence < 0.55:
            options.append(
                self._build_option(
                    option_id="communication_reduced_load",
                    communication_mode="reduced_load",
                    communication_action="reduce_non_critical_communication",
                    parameters={
                        **base_parameters,
                        "reduced_communication": True,
                        "reduce_bandwidth": True,
                    },
                    expected_effect="Reduce non-critical communication load under pressure",
                    confidence=min(1.0, confidence + 0.08),
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint="High message load or weak delivery confidence favors reduced load",
                    cost_estimate=0.2,
                    risk_estimate=0.12,
                )
            )

        if relay_needed or "relay" in trigger_context:
            options.append(
                self._build_option(
                    option_id="communication_relay_support",
                    communication_mode="relay_support",
                    communication_action="activate_relay_support",
                    parameters={
                        **base_parameters,
                        "relay_mode": True,
                        "relay_cost": 0.35,
                    },
                    expected_effect="Enable relay/support communication mode",
                    confidence=min(1.0, confidence + 0.12),
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint="Relay needed or weak team connectivity favors relay support mode",
                    cost_estimate=0.35,
                    risk_estimate=0.18,
                )
            )

        if rescue_active:
            options.append(
                self._build_option(
                    option_id="communication_rescue_priority",
                    communication_mode="rescue_priority",
                    communication_action="prioritize_rescue_messages",
                    parameters={
                        **base_parameters,
                        "prioritize_critical_messages": True,
                        "critical_priority": True,
                        "critical_support": 0.95,
                    },
                    expected_effect="Prioritize rescue and firefighter coordination messages",
                    confidence=min(1.0, max(confidence, 0.75)),
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint="Active rescue coordination requires rescue-priority messaging",
                    cost_estimate=0.15,
                    risk_estimate=0.08,
                )
            )

        if fail_safe_active:
            options.append(
                self._build_option(
                    option_id="communication_fail_safe_priority",
                    communication_mode="fail_safe_priority",
                    communication_action="prioritize_failsafe_messages",
                    parameters={
                        **base_parameters,
                        "prioritize_critical_messages": True,
                        "critical_priority": True,
                        "critical_support": 1.0,
                    },
                    expected_effect="Prioritize fail-safe and emergency coordination messages",
                    confidence=min(1.0, max(confidence, 0.8)),
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint="Non-normal fail-safe posture requires fail-safe communication priority",
                    cost_estimate=0.1,
                    risk_estimate=0.05,
                )
            )

        summaries = [
            f"communication_options={len(options)}",
            f"delivery_confidence={delivery_confidence:.3f}",
            f"message_load={message_load}",
            f"link_degraded={link_degraded}",
            f"rescue_active={rescue_active}",
            f"fail_safe_active={fail_safe_active}",
        ]
        return CommunicationAdaptationSpace(
            options=options,
            trigger_references=trigger_ids,
            explanation_summaries=summaries,
            timestamp=timestamp,
        )
