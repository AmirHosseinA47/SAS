"""Rescue, communication, and decision dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src_extension.execution.communication_executor import CommunicationExecutor
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.execution.rescue_executor import RescueExecutor
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture
from src_extension.managed.victim_state import VictimState
from src_extension.planning.decision_objects import (
    FailSafeDecision,
    MissionDecision,
    PathDecision,
    RescueDecision,
)


@dataclass
class _FakeCommunicationModel:
    relay_needed: bool = False
    communication_mode: str = "normal"
    sent: list[str] = field(default_factory=list)

    def record_sent(self, message_id: str, **kwargs: Any) -> None:
        self.sent.append(message_id)


@dataclass
class _FakeAgent:
    unique_id: int
    pos: tuple[int, int]
    selected_dir: int = 0
    move_called: bool = False

    def move(self) -> bool:
        self.move_called = True
        return False


@dataclass
class _FakeSchedule:
    agents: list[_FakeAgent]


@dataclass
class _FakeModel:
    managed_victims: dict[str, VictimState]
    communication_model: _FakeCommunicationModel
    shared_operational_picture: SharedOperationalPicture
    schedule: _FakeSchedule
    pending_global_commands: list[dict[str, object]] = field(default_factory=list)
    uav_resource_model: object | None = None
    managed_uav_states: dict[str, object] = field(default_factory=dict)


def test_rescue_executor_confirms_victim() -> None:
    victim = VictimState(
        victim_id="victim_0",
        confirmed=False,
        needs_confirmation=True,
    )
    model = _FakeModel(
        managed_victims={"victim_0": victim},
        communication_model=_FakeCommunicationModel(),
        shared_operational_picture=SharedOperationalPicture(),
        schedule=_FakeSchedule(agents=[]),
    )
    executor = RescueExecutor(model=model)
    decision = RescueDecision(
        decision_id="rescue-1",
        rescue_action="confirm",
        victim_id="victim_0",
    )

    result = executor.execute(decision, timestamp=1.0)

    assert result["applied"] is True
    assert victim.confirmed is True
    assert victim.needs_confirmation is False
    assert result["payload"]["victim_updates"]["confirmed"] is True


def test_rescue_executor_assigns_on_dispatch() -> None:
    victim = VictimState(victim_id="victim_0", rescue_assigned=False)
    model = _FakeModel(
        managed_victims={"victim_0": victim},
        communication_model=_FakeCommunicationModel(),
        shared_operational_picture=SharedOperationalPicture(),
        schedule=_FakeSchedule(agents=[]),
    )
    executor = RescueExecutor(model=model)
    decision = RescueDecision(
        decision_id="rescue-2",
        rescue_action="dispatch",
        victim_id="victim_0",
        firefighter_id="ff-1",
    )

    executor.execute(decision, timestamp=2.0)

    assert victim.rescue_assigned is True
    assert victim.firefighter_id == "ff-1"


def test_communication_executor_updates_model_and_returns_status() -> None:
    comm_model = _FakeCommunicationModel()
    model = _FakeModel(
        managed_victims={},
        communication_model=comm_model,
        shared_operational_picture=SharedOperationalPicture(),
        schedule=_FakeSchedule(agents=[]),
    )
    executor = CommunicationExecutor(model=model)
    command = {
        "message_id": "msg-1",
        "priority": "high",
        "communication_action": "relay_send",
        "target_entity": "uav-0",
    }

    result = executor.execute(command, timestamp=3.0)

    assert result["applied"] is True
    assert result["status"] == "success"
    assert result["message_id"] == "msg-1"
    assert comm_model.relay_needed is True
    assert comm_model.communication_mode == "relay_support"
    assert comm_model.sent == ["msg-1"]


def test_decision_dispatcher_returns_all_sections() -> None:
    agent = _FakeAgent(unique_id=0, pos=(2, 3), selected_dir=1)
    victim = VictimState(victim_id="victim_0")
    model = _FakeModel(
        managed_victims={"victim_0": victim},
        communication_model=_FakeCommunicationModel(),
        shared_operational_picture=SharedOperationalPicture(),
        schedule=_FakeSchedule(agents=[agent]),
        pending_global_commands=[
            {
                "command_type": "communication_message",
                "message_id": "msg-dispatch",
                "communication_action": "sent",
                "target_entity": "0",
            }
        ],
    )
    dispatcher = DecisionDispatcher(model=model)
    planning_result = {
        "fail_safe_decision": FailSafeDecision(
            decision_id="fs-1",
            actions=({"uav_id": "0", "next_action": "east"},),
        ),
        "mission_decision": MissionDecision(
            decision_id="mission-1",
            mission_mode="containment",
        ),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="north"),
        ],
        "rescue_decision": RescueDecision(
            decision_id="rescue-1",
            rescue_action="initiate",
            victim_id="victim_0",
        ),
    }

    result = dispatcher.dispatch(planning_result, timestamp=5.0)

    assert set(result.keys()) == {
        "fail_safe",
        "global",
        "local",
        "rescue",
        "communication",
        "fail_safe_override_active",
        "override_reason",
    }
    assert result["fail_safe"]["applied"] is True
    assert result["global"]["applied"] is True
    assert result["local"]["applied"] is True
    assert result["rescue"]["applied"] is True
    assert result["communication"]["applied"] is True
    assert model.shared_operational_picture.mission_mode == "containment"
    assert victim.rescue_assigned is True


def test_dispatcher_does_not_move_agent_or_change_position() -> None:
    agent = _FakeAgent(unique_id=0, pos=(7, 8), selected_dir=2)
    model = _FakeModel(
        managed_victims={},
        communication_model=_FakeCommunicationModel(),
        shared_operational_picture=SharedOperationalPicture(),
        schedule=_FakeSchedule(agents=[agent]),
    )
    dispatcher = DecisionDispatcher(model=model)
    before = agent.pos
    planning_result = {
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        ],
    }

    dispatcher.dispatch(planning_result, timestamp=1.0)

    assert agent.pos == before
    assert agent.move_called is False
