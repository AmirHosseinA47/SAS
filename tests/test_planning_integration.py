"""Planning integrated with WildFireModel."""

from __future__ import annotations

import os
from types import MethodType

os.environ.setdefault("MPLBACKEND", "Agg")

from wildfire_model import WildFireModel


def _uav_movement_snapshot(model: WildFireModel) -> frozenset[tuple[int, tuple, int | None]]:
    return frozenset(
        (agent.unique_id, agent.pos, getattr(agent, "selected_dir", None))
        for agent in model.schedule.agents
        if type(agent).__name__ == "UAV"
    )


def _role_task_snapshot(model: WildFireModel) -> frozenset[tuple[str, str | None, str | None]]:
    return frozenset(
        (uid, st.current_role, st.assigned_task)
        for uid, st in sorted(model.uav_resource_model.by_uav_id.items())
    )


def test_step_populates_planning_result_without_execution_side_effects() -> None:
    model = WildFireModel()
    orig_run = model._run_planning

    def _run_planning_tracked(self: WildFireModel, current_step_time: float) -> None:
        movement_before = _uav_movement_snapshot(self)
        role_task_before = _role_task_snapshot(self)
        orig_run(current_step_time)
        movement_after = _uav_movement_snapshot(self)
        role_task_after = _role_task_snapshot(self)
        assert movement_before == movement_after
        assert role_task_before == role_task_after

    model._run_planning = MethodType(_run_planning_tracked, model)

    for _ in range(3):
        model.step()

    result = model.latest_planning_result
    assert result is not None
    assert result.get("mission_decision") is not None
    assert result.get("rescue_decision") is not None
    assert result.get("fail_safe_decision") is not None

    path_decisions = result.get("path_decisions")
    assert path_decisions is not None
    assert isinstance(path_decisions, dict)
    assert len(path_decisions) > 0

    dashboard_summary = result.get("dashboard_summary")
    assert dashboard_summary is not None
    assert isinstance(dashboard_summary, str)
    assert dashboard_summary.strip()

    assert not hasattr(result, "executed_options")
    assert not hasattr(result, "execution_receipt")
