"""Adaptation-space generation integrated with WildFireModel."""

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


def test_step_populates_adaptation_snapshot_without_execution_side_effects() -> None:
    model = WildFireModel()

    orig_run = model._run_adaptation_space_generation

    def _run_adaptation_tracked(self: WildFireModel) -> None:
        movement_before = _uav_movement_snapshot(self)
        role_task_before = _role_task_snapshot(self)
        orig_run()
        movement_after = _uav_movement_snapshot(self)
        role_task_after = _role_task_snapshot(self)
        assert movement_before == movement_after
        assert role_task_before == role_task_after

    model._run_adaptation_space_generation = MethodType(
        _run_adaptation_tracked,
        model,
    )

    for _ in range(3):
        model.step()

    snap = model.latest_adaptation_space_snapshot
    assert snap is not None
    assert snap.local_spaces
    assert snap.global_space is not None
    assert snap.fail_safe_space is not None
    assert isinstance(snap.all_options, list)
    assert len(snap.all_options) > 0
    assert isinstance(snap.dashboard_summary, str)
    assert snap.dashboard_summary

    assert not hasattr(snap, "utility_ranking")
    assert not hasattr(snap, "selected_option")
    assert not hasattr(snap, "executed_options")
    for option in snap.all_options:
        assert not hasattr(option, "utility_score")
        assert "utility" not in option.parameters
        assert "rank" not in option.parameters
