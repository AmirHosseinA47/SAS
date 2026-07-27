"""Fail-safe override integration tests."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import MethodType
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.execution.failsafe_modes import FailSafeMode
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.planning.decision_objects import FailSafeDecision, PathDecision
from wildfire_model import WildFireModel


@dataclass
class _FakeAgent:
    unique_id: int
    pos: tuple[int, int]
    selected_dir: int = 0

    def move(self) -> bool:
        return False


@dataclass
class _FakeFireRuntimeModel:
    target: tuple[float, float] | None = (9.0, 5.0)

    def get_best_search_target(
        self,
        current_time: float | None = None,
        min_conf: float = 0.3,
        **kwargs: Any,
    ) -> tuple[float, float] | None:
        return self.target


@dataclass
class _FakeSchedule:
    agents: list[_FakeAgent]


@dataclass
class _FakeDispatcherModel:
    schedule: _FakeSchedule
    fire_runtime_model: _FakeFireRuntimeModel = field(default_factory=_FakeFireRuntimeModel)
    evaluation_timesteps_counter: float = 1.0
    pending_global_commands: list[object] = field(default_factory=list)


def _search_fail_safe_decision() -> FailSafeDecision:
    return FailSafeDecision(
        decision_id="fs-search",
        search_mode_active=True,
        mission_mode="information_recovery",
        fail_safe_action="activate_search_mode",
        target_region="9.0,5.0",
        uncertainty_context={"fail_safe_mode": FailSafeMode.INFORMATION_RECOVERY.value},
    )


def _hold_fail_safe_decision() -> FailSafeDecision:
    return FailSafeDecision(
        decision_id="fs-hold",
        fail_safe_action="safe_hold",
        mission_mode="safety_first",
        uncertainty_context={"fail_safe_mode": FailSafeMode.SAFETY_FIRST.value},
    )


def _normal_fail_safe_decision() -> FailSafeDecision:
    return FailSafeDecision(
        decision_id="fs-normal",
        mission_mode="normal",
        fail_safe_action="maintain_current_config",
        search_mode_active=False,
        uncertainty_context={"fail_safe_mode": FailSafeMode.NORMAL.value},
    )


def _stale_context_normal_fail_safe_decision() -> FailSafeDecision:
    return FailSafeDecision(
        decision_id="fs-normal-stale",
        mission_mode="normal",
        fail_safe_action="maintain_current_config",
        search_mode_active=False,
        uncertainty_context={
            "fail_safe_mode": FailSafeMode.INFORMATION_RECOVERY.value,
        },
    )


def _emergency_fail_safe_decision() -> FailSafeDecision:
    return FailSafeDecision(
        decision_id="fs-emergency",
        fail_safe_action="suspend_non_critical_tasks",
        mission_mode=FailSafeMode.EMERGENCY.value,
        uncertainty_context={"fail_safe_mode": FailSafeMode.EMERGENCY.value},
    )


def _dispatcher_model(agent: _FakeAgent) -> _FakeDispatcherModel:
    return _FakeDispatcherModel(schedule=_FakeSchedule(agents=[agent]))


def test_search_mode_active_with_normal_mission_mode_does_not_override() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": FailSafeDecision(
            decision_id="fs-search-stale",
            search_mode_active=True,
            mission_mode="normal",
            fail_safe_action="maintain_current_config",
        ),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)

    assert result["fail_safe_override_active"] is False
    assert result["local"]["uav_results"]["0"]["applied"] is True


def test_search_mode_active_with_empty_mission_mode_does_not_override() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": FailSafeDecision(
            decision_id="fs-search-empty",
            search_mode_active=True,
            mission_mode="",
            fail_safe_action="maintain_current_config",
        ),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)

    assert result["fail_safe_override_active"] is False
    assert result["local"]["uav_results"]["0"]["applied"] is True


def test_search_mode_active_with_information_recovery_mission_mode_overrides() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": FailSafeDecision(
            decision_id="fs-search-ir",
            search_mode_active=True,
            mission_mode="information_recovery",
            fail_safe_action="activate_search_mode",
            target_region="9.0,5.0",
        ),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)

    assert result["fail_safe_override_active"] is True
    assert "search_mode_active" in str(result["override_reason"])


def test_normal_mission_mode_ignores_stale_uncertainty_context_mode() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": _stale_context_normal_fail_safe_decision(),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)

    assert result["fail_safe_override_active"] is False
    assert result["local"]["uav_results"]["0"]["applied"] is True


def test_normal_fail_safe_does_not_activate_override() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": _normal_fail_safe_decision(),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)

    assert result["fail_safe_override_active"] is False
    assert result["local"]["fail_safe_override_active"] is False


def test_normal_fail_safe_applies_local_path_execution() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": _normal_fail_safe_decision(),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)
    uav_result = result["local"]["uav_results"]["0"]

    assert uav_result["applied"] is True
    assert uav_result["selected_dir"] == 2
    assert agent.selected_dir == 2


def test_normal_execution_passes_none_fail_safe_to_uav_executor(monkeypatch) -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    captured: list[FailSafeDecision | None] = []
    original_execute = UAVExecutor.execute

    def _spy_execute(
        self: UAVExecutor,
        decision: PathDecision,
        timestamp: float = 0.0,
        fail_safe_decision: FailSafeDecision | None = None,
    ) -> dict[str, object]:
        captured.append(fail_safe_decision)
        return original_execute(self, decision, timestamp, fail_safe_decision)

    monkeypatch.setattr(UAVExecutor, "execute", _spy_execute)
    dispatcher.dispatch(
        {
            "fail_safe_decision": _normal_fail_safe_decision(),
            "path_decisions": [
                PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
            ],
        },
        timestamp=1.0,
    )

    assert captured
    assert captured[0] is None


def test_search_mode_forwards_fail_safe_decision_to_uav_executor(monkeypatch) -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    captured: list[FailSafeDecision | None] = []
    original_execute = UAVExecutor.execute

    def _spy_execute(
        self: UAVExecutor,
        decision: PathDecision,
        timestamp: float = 0.0,
        fail_safe_decision: FailSafeDecision | None = None,
    ) -> dict[str, object]:
        captured.append(fail_safe_decision)
        return original_execute(self, decision, timestamp, fail_safe_decision)

    monkeypatch.setattr(UAVExecutor, "execute", _spy_execute)
    fail_safe = _search_fail_safe_decision()
    dispatcher.dispatch(
        {
            "fail_safe_decision": fail_safe,
            "path_decisions": [
                PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
            ],
        },
        timestamp=1.0,
    )

    assert captured
    assert captured[0] is fail_safe


def test_emergency_fail_safe_still_activates_override() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": _emergency_fail_safe_decision(),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="east"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)

    assert result["fail_safe_override_active"] is True
    assert "emergency_mode" in str(result["override_reason"])


def test_emergency_mode_still_forwards_fail_safe_when_applicable(monkeypatch) -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    captured: list[FailSafeDecision | None] = []
    original_execute = UAVExecutor.execute

    def _spy_execute(
        self: UAVExecutor,
        decision: PathDecision,
        timestamp: float = 0.0,
        fail_safe_decision: FailSafeDecision | None = None,
    ) -> dict[str, object]:
        captured.append(fail_safe_decision)
        return original_execute(self, decision, timestamp, fail_safe_decision)

    monkeypatch.setattr(UAVExecutor, "execute", _spy_execute)
    fail_safe = _emergency_fail_safe_decision()
    result = dispatcher.dispatch(
        {
            "fail_safe_decision": fail_safe,
            "path_decisions": [
                PathDecision(decision_id="path-1", uav_id="0", next_action="east"),
            ],
        },
        timestamp=1.0,
    )

    assert result["fail_safe_override_active"] is True
    assert captured
    assert captured[0] is None


def test_dispatcher_marks_fail_safe_override_active_for_search_mode() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": _search_fail_safe_decision(),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)

    assert result["fail_safe_override_active"] is True
    assert "search_mode_active" in str(result["override_reason"])


def test_search_mode_fail_safe_steers_selected_dir_via_uav_executor() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": _search_fail_safe_decision(),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)
    local = result["local"]
    uav_result = local["uav_results"]["0"]

    assert uav_result["action"] == "search_mode"
    assert uav_result["selected_dir"] == 0
    assert agent.selected_dir == 0
    assert agent.pos == (5, 5)


def test_safe_hold_converts_local_path_to_hold() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    dispatcher = DecisionDispatcher(model=_dispatcher_model(agent))
    planning_result = {
        "fail_safe_decision": _hold_fail_safe_decision(),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="0", next_action="east"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)
    uav_result = result["local"]["uav_results"]["0"]

    assert result["fail_safe_override_active"] is True
    assert uav_result["action"] == "hold"
    assert uav_result["selected_dir"] == 2
    assert agent.selected_dir == 2
    assert agent.pos == (5, 5)


def test_uav_executor_search_mode_receives_fail_safe_decision() -> None:
    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    model = _FakeDispatcherModel(schedule=_FakeSchedule(agents=[agent]))
    executor = UAVExecutor(uav_id="0", model=model, agent=agent)
    fail_safe = _search_fail_safe_decision()

    result = executor.execute(
        PathDecision(decision_id="path-1", uav_id="0", next_action="west"),
        timestamp=1.0,
        fail_safe_decision=fail_safe,
    )

    assert result["action"] == "search_mode"
    assert agent.selected_dir == 0


def _uav_pos_snapshot(model: WildFireModel) -> dict[int, tuple[int, int]]:
    return {
        agent.unique_id: agent.pos
        for agent in model.schedule.agents
        if type(agent) is agents.UAV
    }


def test_wildfire_model_stores_failsafe_state_and_dashboard_summary() -> None:
    model = WildFireModel()
    update_count = 0
    orig_update = model._update_failsafe_mode

    def _tracked_update(self: WildFireModel, current_step_time: float) -> None:
        nonlocal update_count
        orig_update(current_step_time)
        update_count += 1

    model._update_failsafe_mode = MethodType(_tracked_update, model)
    model.latest_analysis_snapshot = {
        "triggers": ({"trigger_type": "SEARCH_MODE_REQUIRED"},),
    }

    model._run_planning(1.0)
    model._update_failsafe_mode(1.0)
    model.latest_execution_result = {"failures": (), "partial_success": False}
    model._run_execution(1.0)
    model._update_failsafe_mode(2.0)

    assert model.latest_failsafe_state is not None
    assert model.latest_failsafe_dashboard_summary is not None
    assert "Fail-safe dashboard" in model.latest_failsafe_dashboard_summary
    assert model.latest_failsafe_state.mode in {
        FailSafeMode.NORMAL,
        FailSafeMode.INFORMATION_RECOVERY,
    }
    assert update_count >= 2


def test_execution_does_not_mutate_agent_pos() -> None:
    model = WildFireModel()
    orig_run_execution = model._run_execution

    def _run_execution_tracked(self: WildFireModel, current_step_time: float) -> None:
        before = _uav_pos_snapshot(self)
        orig_run_execution(current_step_time)
        after = _uav_pos_snapshot(self)
        assert before == after

    model._run_execution = MethodType(_run_execution_tracked, model)

    for _ in range(3):
        model.step()

    assert model.latest_failsafe_state is not None
