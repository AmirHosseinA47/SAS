"""CommunicationAdaptationPlanner selection tests."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

from src_extension.adaptation.communication_adaptation_generator import (
    CommunicationAdaptationGenerator,
)
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.knowledge.communication_model import CommunicationModel
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture
from src_extension.planning.communication_adaptation_planner import (
    CommunicationAdaptationPlanner,
)
from src_extension.planning.planning_coordinator import PlanningCoordinator
from wildfire_model import WildFireModel


MODE_NAMES = {
    "normal",
    "reduced_load",
    "rescue_priority",
    "fail_safe_priority",
    "degraded_communication",
    "relay_support",
}


def _generate_space(
    *,
    delivery_confidence: float = 0.75,
    relay_needed: bool = False,
    active_rescues: int = 0,
    mission_phase: str = "exploration",
    fail_safe_active: bool = False,
    simulation_model: object | None = None,
) -> object:
    comm_model = CommunicationModel()
    comm_model.state.delivery_confidence = delivery_confidence
    comm_model.state.relay_needed_flag = relay_needed
    runtime: dict[str, object] = {
        "communication_model": comm_model,
        "mission_goals": {
            "active_rescues": active_rescues,
            "mission_phase": mission_phase,
        },
        "simulation_model": simulation_model,
    }
    if fail_safe_active:
        runtime["latest_failsafe_state"] = SimpleNamespace(
            mode=SimpleNamespace(value="emergency")
        )
    return CommunicationAdaptationGenerator().generate({"triggers": []}, runtime, 1.0)


def _planner_decision(
    space: object,
    *,
    runtime_models: dict[str, object] | None = None,
) -> dict[str, object]:
    planner = CommunicationAdaptationPlanner()
    models = dict(runtime_models or {})
    models.setdefault("communication_adaptation_space", space)
    decision = planner.plan(
        1,
        communication_adaptation_space=space,
        runtime_models=models,
        timestamp=1.0,
    )
    assert decision is not None
    return decision


def test_planner_selects_fail_safe_priority_over_rescue_priority() -> None:
    space = _generate_space(active_rescues=1, mission_phase="rescue_active")
    decision = _planner_decision(
        space,
        runtime_models={
            "latest_failsafe_state": SimpleNamespace(mode=SimpleNamespace(value="emergency")),
            "mission_goals": {"active_rescues": 1, "mission_phase": "rescue_active"},
        },
    )
    assert decision["communication_mode"] == "fail_safe_priority"


def test_planner_selects_rescue_priority_over_degraded_communication() -> None:
    space = _generate_space(delivery_confidence=0.3, active_rescues=1, mission_phase="rescue_active")
    decision = _planner_decision(
        space,
        runtime_models={
            "latest_failsafe_state": SimpleNamespace(mode=SimpleNamespace(value="normal")),
            "mission_goals": {"active_rescues": 1, "mission_phase": "rescue_active"},
        },
    )
    assert decision["communication_mode"] == "rescue_priority"


def test_planner_selects_relay_support_when_relay_needed() -> None:
    space = _generate_space(relay_needed=True, delivery_confidence=0.7)
    decision = _planner_decision(
        space,
        runtime_models={
            "latest_failsafe_state": SimpleNamespace(mode=SimpleNamespace(value="normal")),
            "mission_goals": {"active_rescues": 0, "mission_phase": "exploration"},
        },
    )
    assert decision["communication_mode"] == "relay_support"


def test_planner_selects_normal_when_no_higher_priority_option_exists() -> None:
    from src_extension.adaptation.adaptation_option_objects import AdaptationOption, Scope

    only_normal = AdaptationOption(
        option_id="communication_normal",
        option_type="communication_adaptation",
        target_entity="communication_system",
        parameters={
            "communication_mode": "normal",
            "communication_action": "maintain_normal_communication",
        },
        expected_effect="Maintain normal communication load and priorities",
        cost_estimate=0.05,
        risk_estimate=0.05,
        confidence=0.9,
        scope=Scope.system,
        timestamp=1.0,
        originating_trigger="communication_analysis",
        explanation_hint="Baseline communication mode when links are healthy",
    )
    space = SimpleNamespace(options=[only_normal])
    decision = _planner_decision(
        space,
        runtime_models={
            "mission_goals": {"active_rescues": 0, "mission_phase": "exploration"},
        },
    )
    assert decision["communication_mode"] == "normal"


def test_planning_coordinator_includes_communication_decision() -> None:
    space = _generate_space(delivery_confidence=0.3)
    coordinator = PlanningCoordinator()
    result = coordinator.run_planning(
        None,
        None,
        runtime_models={"communication_adaptation_space": space},
        timestamp=2.0,
    )
    assert "communication_decision" in result
    assert isinstance(result["communication_decision"], dict)
    assert result["communication_decision"]["communication_mode"] in MODE_NAMES


def test_wildfire_model_planning_result_includes_planner_communication_decision() -> None:
    model = WildFireModel()
    model.latest_analysis_snapshot = SimpleNamespace(
        timestamp=1.0,
        local_results=(),
        global_result=SimpleNamespace(
            timestamp=1.0,
            trigger_list=(),
            to_dict=lambda: {},
            trigger_batch=SimpleNamespace(triggers=()),
        ),
        all_triggers=(),
        trigger_batch=SimpleNamespace(triggers=()),
    )
    model.latest_adaptation_space_snapshot = SimpleNamespace(
        timestamp=1.0,
        local_spaces=[],
        global_space=SimpleNamespace(options=[]),
        rescue_space=SimpleNamespace(options=[]),
        fail_safe_space=SimpleNamespace(options=[]),
    )
    model.latest_communication_adaptation_space = _generate_space(delivery_confidence=0.35)
    model._run_planning(1.0)
    assert model.latest_planning_result is not None
    assert "communication_decision" in model.latest_planning_result
    assert model.latest_planning_result["communication_decision"]["communication_mode"] in MODE_NAMES


def test_dispatcher_executes_planner_communication_decision() -> None:
    comm_model = CommunicationModel()
    model = SimpleNamespace(
        communication_model=comm_model,
        pending_global_commands=[],
        latest_communication_execution=None,
    )
    planner = CommunicationAdaptationPlanner()
    space = _generate_space(delivery_confidence=0.25)
    decision = planner.plan(1, communication_adaptation_space=space, timestamp=3.0)
    assert decision is not None
    dispatcher = DecisionDispatcher(model=model)
    result = dispatcher.dispatch({"path_decisions": [], "communication_decision": decision}, 3.0)
    assert result["communication"]["applied"] is True
    assert comm_model.communication_mode in MODE_NAMES
