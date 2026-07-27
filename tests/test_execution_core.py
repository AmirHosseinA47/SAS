"""Execution core: execution log and global executor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src_extension.execution.execution_log import ExecutionLog, ExecutionResult
from src_extension.execution.global_executor import GlobalExecutor
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture
from src_extension.managed.uav_extension_state import UAVExtensionState
from src_extension.planning.decision_objects import MissionDecision


@dataclass
class _FakeUAVResourceModel:
    roles: dict[str, str] = field(default_factory=dict)

    def update_role(self, uav_id: str, new_role: str, *args: Any, **kwargs: Any) -> None:
        self.roles[uav_id] = new_role


@dataclass
class _FakeAgent:
    unique_id: int
    pos: tuple[int, int]
    selected_dir: int = 0


@dataclass
class _FakeSchedule:
    agents: list[_FakeAgent]


@dataclass
class _FakeModel:
    uav_resource_model: _FakeUAVResourceModel
    managed_uav_states: dict[str, UAVExtensionState]
    shared_operational_picture: SharedOperationalPicture
    schedule: _FakeSchedule
    pending_global_commands: list[dict[str, object]] = field(default_factory=list)


def _mission_decision(**overrides: object) -> MissionDecision:
    base = {
        "decision_id": "mission-1",
        "uav_assignments": {"0": "scout"},
        "task_assignments": {},
        "mission_mode": "containment",
        "relay_assignments": {},
        "recall_orders": (),
        "confidence_score": 0.8,
        "explanation": "test mission",
    }
    base.update(overrides)
    return MissionDecision(**base)  # type: ignore[arg-type]


def test_execution_result_and_execution_log() -> None:
    log = ExecutionLog()
    r1 = ExecutionResult(
        decision_id="d1",
        executor_type="global",
        target_entity="mission",
        action="apply",
        status="success",
        timestamp=1.0,
        intended_effect="x",
        actual_result="ok",
    )
    r2 = ExecutionResult(
        decision_id="d2",
        executor_type="uav",
        target_entity="0",
        action="set_direction",
        status="success",
        timestamp=2.0,
        intended_effect="y",
        actual_result="ok",
    )
    log.add(r1)
    log.add(r2)

    assert len(log.entries) == 2
    assert log.latest(1) == [r2]
    assert log.latest(0) == []

    exported = log.to_dict()
    assert len(exported["entries"]) == 2
    assert exported["entries"][0]["decision_id"] == "d1"
    assert exported["entries"][1]["executor_type"] == "uav"


def test_global_executor_applies_role_assignment() -> None:
    model = _FakeModel(
        uav_resource_model=_FakeUAVResourceModel(),
        managed_uav_states={"0": UAVExtensionState(uav_id="0", role="idle")},
        shared_operational_picture=SharedOperationalPicture(),
        schedule=_FakeSchedule(agents=[_FakeAgent(unique_id=0, pos=(3, 4))]),
    )
    executor = GlobalExecutor(model=model)
    decision = _mission_decision(uav_assignments={"0": "relay"})

    result = executor.execute(decision, timestamp=5.0)

    assert model.uav_resource_model.roles["0"] == "relay"
    assert model.managed_uav_states["0"].role == "relay"
    assert result["assignments"] == {"0": "relay"}


def test_global_executor_updates_mission_mode() -> None:
    model = _FakeModel(
        uav_resource_model=_FakeUAVResourceModel(),
        managed_uav_states={},
        shared_operational_picture=SharedOperationalPicture(),
        schedule=_FakeSchedule(agents=[]),
    )
    executor = GlobalExecutor(model=model)
    decision = _mission_decision(mission_mode="search_focus")

    executor.execute(decision, timestamp=1.0)

    assert model.shared_operational_picture.mission_mode == "search_focus"


def test_global_executor_returns_applied_for_real_decision() -> None:
    model = _FakeModel(
        uav_resource_model=_FakeUAVResourceModel(),
        managed_uav_states={},
        shared_operational_picture=SharedOperationalPicture(),
        schedule=_FakeSchedule(agents=[]),
    )
    execution_log = ExecutionLog()
    executor = GlobalExecutor(model=model, execution_log=execution_log)
    decision = _mission_decision()

    result = executor.execute(decision, timestamp=2.0)

    assert result["applied"] is True
    assert result["decision_id"] == "mission-1"
    assert len(execution_log.entries) == 1


def test_global_executor_does_not_modify_uav_position() -> None:
    agent = _FakeAgent(unique_id=0, pos=(10, 20))
    model = _FakeModel(
        uav_resource_model=_FakeUAVResourceModel(),
        managed_uav_states={"0": UAVExtensionState(uav_id="0")},
        shared_operational_picture=SharedOperationalPicture(),
        schedule=_FakeSchedule(agents=[agent]),
    )
    executor = GlobalExecutor(model=model)
    before = agent.pos

    executor.execute(_mission_decision(), timestamp=1.0)

    assert agent.pos == before
    assert agent.pos == (10, 20)
