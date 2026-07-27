"""Communication adaptation live MAPE-K pipeline integration tests."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

from src_extension.adaptation.communication_adaptation_generator import (
    CommunicationAdaptationGenerator,
)
from src_extension.execution.communication_executor import CommunicationExecutor
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.knowledge.communication_model import CommunicationModel
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture
from src_extension.monitoring.communication_monitor import CommunicationMonitor
from src_extension.planning.communication_adaptation_planner import CommunicationAdaptationPlanner
from src_extension.planning.decision_objects import PathDecision
from wildfire_model import WildFireModel


@dataclass
class _FakeModel:
    communication_model: CommunicationModel
    shared_operational_picture: SharedOperationalPicture = field(
        default_factory=SharedOperationalPicture
    )
    pending_global_commands: list[dict[str, object]] = field(default_factory=list)
    latest_communication_execution: dict[str, object] | None = None
    latest_failsafe_state: object | None = None
    managed_victims: dict[str, object] = field(default_factory=dict)
    schedule: object = field(default_factory=lambda: SimpleNamespace(agents=[]))


def test_degraded_comm_snapshot_creates_adaptation_option() -> None:
    comm_model = CommunicationModel()
    comm_model.state.delivery_confidence = 0.35
    comm_model.state.failed_messages = [{"message_id": "m1", "timestamp": 1.0}]
    comm_model.state.link_quality_summary = {"degraded": True, "message_load": 5}
    monitor = CommunicationMonitor(comm_model)
    snapshot = monitor.collect_snapshot(1.0)
    assert snapshot.failed >= 1
    assert snapshot.delivery_confidence == pytest.approx(0.35)

    generator = CommunicationAdaptationGenerator()
    space = generator.generate(
        {"triggers": [], "delivery_confidence": 0.35},
        {
            "communication_model": comm_model,
            "mission_goals": {"active_rescues": 0, "mission_phase": "exploration"},
        },
        1.0,
    )
    modes = {opt.parameters.get("communication_mode") for opt in space.options}
    assert "degraded_communication" in modes
    assert "reduced_load" in modes


def test_communication_executor_updates_model_mode() -> None:
    comm_model = CommunicationModel()
    model = _FakeModel(communication_model=comm_model)
    executor = CommunicationExecutor(model=model)
    result = executor.execute(
        {
            "decision_id": "comm-1",
            "communication_mode": "reduced_load",
            "communication_action": "reduce_non_critical_communication",
            "message_id": "msg-1",
            "target_entity": "communication_system",
            "explanation": "test reduced load",
        },
        timestamp=2.0,
    )
    assert result["applied"] is True
    assert result["communication_mode"] == "reduced_load"
    assert comm_model.communication_mode == "reduced_load"
    assert comm_model._communication_command_log
    assert comm_model._communication_command_log[-1]["communication_mode"] == "reduced_load"


def test_dispatcher_applies_selected_communication_decision() -> None:
    comm_model = CommunicationModel()
    model = _FakeModel(communication_model=comm_model)
    dispatcher = DecisionDispatcher(model=model)
    planning_result = {
        "path_decisions": [],
        "communication_decision": {
            "decision_id": "comm-plan-1",
            "communication_mode": "degraded_communication",
            "communication_action": "apply_degraded_communication",
            "message_id": "comm-plan-1",
            "target_entity": "communication_system",
            "explanation": "degraded links",
        },
    }
    result = dispatcher.dispatch(planning_result, timestamp=3.0)
    assert result["communication"]["applied"] is True
    assert comm_model.communication_mode == "degraded_communication"
    assert model.latest_communication_execution is not None
    assert model.latest_communication_execution.get("communication_mode") == "degraded_communication"


def test_pending_global_commands_are_consumed_after_execution() -> None:
    comm_model = CommunicationModel()
    model = _FakeModel(
        communication_model=comm_model,
        pending_global_commands=[
            {
                "command_type": "communication_message",
                "message_id": "pending-1",
                "communication_action": "sent",
                "target_entity": "uav-0",
            }
        ],
    )
    dispatcher = DecisionDispatcher(model=model)
    result = dispatcher.dispatch({"path_decisions": []}, timestamp=4.0)
    assert result["communication"]["applied"] is True
    assert model.pending_global_commands == []
    assert model.latest_communication_execution is not None
    assert model.latest_communication_execution.get("pending_commands_remaining") == 0


def test_rescue_active_selects_rescue_priority_mode() -> None:
    space = CommunicationAdaptationGenerator().generate(
        {"triggers": []},
        {
            "communication_model": CommunicationModel(),
            "mission_goals": {"active_rescues": 1, "mission_phase": "rescue_active"},
            "latest_failsafe_state": SimpleNamespace(mode=SimpleNamespace(value="normal")),
        },
        1.0,
    )
    planner = CommunicationAdaptationPlanner()
    decision = planner.plan(
        1,
        communication_adaptation_space=space,
        runtime_models={
            "mission_goals": {"active_rescues": 1, "mission_phase": "rescue_active"},
            "latest_failsafe_state": SimpleNamespace(mode=SimpleNamespace(value="normal")),
        },
        timestamp=1.0,
    )
    assert decision is not None
    assert decision["communication_mode"] == "rescue_priority"


def test_fail_safe_mode_selects_fail_safe_priority_mode() -> None:
    space = CommunicationAdaptationGenerator().generate(
        {"triggers": []},
        {"communication_model": CommunicationModel(), "mission_goals": {}},
        1.0,
    )
    planner = CommunicationAdaptationPlanner()
    decision = planner.plan(
        2,
        communication_adaptation_space=space,
        runtime_models={
            "latest_failsafe_state": SimpleNamespace(mode=SimpleNamespace(value="emergency")),
        },
        timestamp=2.0,
    )
    assert decision is not None
    assert decision["communication_mode"] == "fail_safe_priority"


def test_wildfire_model_step_with_communication_adaptation_active() -> None:
    model = WildFireModel()
    with patch("wildfire_model.SYSTEM_RANDOM") as mock_random:
        mock_random.choice.return_value = 0
        model.step()
    assert model.latest_communication_adaptation_space is not None
    assert model.latest_planning_result is not None
    assert "communication_decision" in model.latest_planning_result
    assert model.latest_execution_result is not None
    assert "communication" in model.latest_execution_result
    assert model.latest_communication_execution is not None


def test_wildfire_model_communication_decision_reaches_executor() -> None:
    model = WildFireModel()
    model.communication_model.state.delivery_confidence = 0.3
    space = CommunicationAdaptationGenerator().generate(
        {"triggers": [], "communication_degraded": True},
        {
            "communication_model": model.communication_model,
            "simulation_model": model,
            "mission_goals": model.mission_goal_model.runtime_context(),
        },
        5.0,
    )
    planner = CommunicationAdaptationPlanner()
    decision = planner.plan(
        5,
        communication_adaptation_space=space,
        runtime_models={
            "communication_adaptation_space": space,
            "mission_goals": model.mission_goal_model.runtime_context(),
        },
        timestamp=5.0,
    )
    assert decision is not None
    planning_result = {
        "path_decisions": [
            PathDecision(decision_id="p-0", uav_id="2500", next_action="hold"),
        ],
        "communication_decision": decision,
    }
    result = model.decision_dispatcher.dispatch(planning_result, timestamp=5.0)
    assert result["communication"]["applied"] is True
    assert model.communication_model.communication_mode in {
        "degraded_communication",
        "reduced_load",
        "normal",
        "rescue_priority",
        "fail_safe_priority",
        "relay_support",
    }
