"""Execution integrated with WildFireModel.step."""

from __future__ import annotations

import os
from types import MethodType

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from wildfire_model import WildFireModel


def _uav_pos_dir_snapshot(model: WildFireModel) -> dict[int, tuple[tuple, int]]:
    return {
        agent.unique_id: (agent.pos, agent.selected_dir)
        for agent in model.schedule.agents
        if type(agent) is agents.UAV
    }


def _execution_reports_selected_dir(execution: dict) -> bool:
    for section_name in ("fail_safe", "local"):
        section = execution.get(section_name)
        if not isinstance(section, dict):
            continue
        uav_results = section.get("uav_results")
        if not isinstance(uav_results, dict):
            continue
        for uav_result in uav_results.values():
            if isinstance(uav_result, dict) and "selected_dir" in uav_result:
                return True
    return False


def test_step_populates_execution_artifacts_and_feedback() -> None:
    model = WildFireModel()
    seen_dir_change_during_execution = False
    orig_run_execution = model._run_execution

    def _run_execution_tracked(self: WildFireModel, current_step_time: float) -> None:
        nonlocal seen_dir_change_during_execution
        before = _uav_pos_dir_snapshot(self)
        orig_run_execution(current_step_time)
        after = _uav_pos_dir_snapshot(self)
        for uav_id, (pos_before, dir_before) in before.items():
            pos_after, dir_after = after[uav_id]
            assert pos_before == pos_after
            if dir_before != dir_after:
                seen_dir_change_during_execution = True

    model._run_execution = MethodType(_run_execution_tracked, model)

    for _ in range(5):
        model.step()

    assert model.latest_planning_result is not None
    assert model.latest_execution_result is not None
    assert model.latest_execution_feedback_event is not None
    assert isinstance(model.execution_log, type(model.execution_log))
    assert len(model.execution_log.entries) > 0

    feedback = model.latest_execution_feedback_event
    assert "timestamp" in feedback
    assert "result" in feedback
    assert feedback["execution_log_count"] == len(model.execution_log.entries)

    execution = model.latest_execution_result
    assert isinstance(execution, dict)
    assert set(execution.keys()) >= {"fail_safe", "global", "local", "rescue", "communication"}
    assert (
        seen_dir_change_during_execution
        or _execution_reports_selected_dir(execution)
        or execution.get("fail_safe_override_active") is True
    )

    assert execution.get("global", {}).get("applied") is True
    assert execution.get("rescue", {}).get("applied") is True
    assert len(feedback.get("affected_entities", [])) > 0

    step_counter_before = model.evaluation_timesteps_counter
    feedback_entities_before = list(feedback.get("affected_entities", []))

    model.step()

    assert model.evaluation_timesteps_counter == step_counter_before + 1
    assert model.latest_global_snapshot is not None
    assert model.latest_execution_feedback_event is not None
    assert feedback_entities_before  # execution effects recorded for monitoring

    for agent in model.schedule.agents:
        if type(agent) is not agents.UAV:
            continue
        uav_id = str(agent.unique_id)
        managed = model.managed_uav_states[uav_id]
        assert managed.position == (float(agent.pos[0]), float(agent.pos[1]))
