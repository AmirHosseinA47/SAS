"""GlobalExecutor update_role signature compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src_extension.execution.global_executor import GlobalExecutor
from src_extension.knowledge.uav_resource_model import UAVResourceModel
from src_extension.managed.uav_extension_state import UAVExtensionState
from src_extension.planning.decision_objects import MissionDecision


@dataclass
class _FullSignatureResourceModel:
    roles: dict[str, str] = field(default_factory=dict)
    calls: list[dict[str, object]] = field(default_factory=list)

    def update_role(
        self,
        uav_id: str,
        new_role: str,
        timestamp: float,
        source: str = "uav_runtime",
        confidence: float = 0.8,
    ) -> None:
        self.calls.append(
            {
                "uav_id": uav_id,
                "new_role": new_role,
                "timestamp": timestamp,
                "source": source,
                "confidence": confidence,
            }
        )
        self.roles[uav_id] = new_role


@dataclass
class _LegacyResourceModel:
    roles: dict[str, str] = field(default_factory=dict)

    def update_role(self, uav_id: str, role: str) -> None:
        self.roles[uav_id] = role


@dataclass
class _FakeModel:
    uav_resource_model: Any
    managed_uav_states: dict[str, UAVExtensionState]


def test_full_update_role_signature_receives_metadata() -> None:
    resource = _FullSignatureResourceModel()
    model = _FakeModel(
        uav_resource_model=resource,
        managed_uav_states={"uav-0": UAVExtensionState(uav_id="uav-0", role="idle")},
    )
    decision = MissionDecision(
        decision_id="m-1",
        uav_assignments={"uav-0": "scout"},
        confidence_score=0.65,
    )
    executor = GlobalExecutor(model=model)

    result = executor.execute(decision, timestamp=12.0)

    assert result["applied"] is True
    assert len(resource.calls) == 1
    call = resource.calls[0]
    assert call["timestamp"] == 12.0
    assert call["source"] == "global_executor"
    assert call["confidence"] == 0.65
    assert resource.roles["uav-0"] == "scout"
    assert model.managed_uav_states["uav-0"].role == "scout"


def test_legacy_update_role_signature_still_works() -> None:
    resource = _LegacyResourceModel()
    model = _FakeModel(
        uav_resource_model=resource,
        managed_uav_states={"uav-1": UAVExtensionState(uav_id="uav-1")},
    )
    decision = MissionDecision(
        decision_id="m-2",
        uav_assignments={"uav-1": "relay"},
    )
    executor = GlobalExecutor(model=model)

    result = executor.execute(decision, timestamp=3.0)

    assert result["applied"] is True
    assert resource.roles["uav-1"] == "relay"
    assert model.managed_uav_states["uav-1"].role == "relay"


def test_real_uav_resource_model_does_not_crash() -> None:
    resource = UAVResourceModel()
    model = _FakeModel(
        uav_resource_model=resource,
        managed_uav_states={"uav-2": UAVExtensionState(uav_id="uav-2", role="idle")},
    )
    decision = MissionDecision(
        decision_id="m-3",
        uav_assignments={"uav-2": "mapper"},
        confidence_score=0.9,
    )
    executor = GlobalExecutor(model=model)

    result = executor.execute(decision, timestamp=7.0)

    assert result["applied"] is True
    assert resource.by_uav_id["uav-2"].current_role == "mapper"
    assert model.managed_uav_states["uav-2"].role == "mapper"
