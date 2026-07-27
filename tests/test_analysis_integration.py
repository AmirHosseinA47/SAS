"""Analysis loop integrated with WildFireModel."""

from __future__ import annotations

import os
from types import MethodType

os.environ.setdefault("MPLBACKEND", "Agg")

from wildfire_model import WildFireModel


def _role_task_snapshot(model: WildFireModel) -> frozenset[tuple[str, str | None, str | None]]:
    return frozenset(
        (uid, st.current_role, st.assigned_task)
        for uid, st in sorted(model.uav_resource_model.by_uav_id.items())
    )


def test_step_populates_analysis_snapshot_without_role_task_side_effects() -> None:
    model = WildFireModel()

    orig_run = model._run_analysis

    def _run_analysis_tracked(self: WildFireModel, current_step_time: float, global_snapshot: object) -> None:
        before = _role_task_snapshot(self)
        orig_run(current_step_time, global_snapshot)
        after = _role_task_snapshot(self)
        assert before == after, "analysis must not mutate UAV role/task on resource model"

    model._run_analysis = MethodType(_run_analysis_tracked, model)

    for _ in range(3):
        model.step()

    snap = model.latest_analysis_snapshot
    assert snap is not None
    assert snap.local_results is not None and len(snap.local_results) > 0
    assert snap.global_result is not None
    assert isinstance(snap.all_triggers, (list, tuple))
    assert snap.dashboard_summary is not None
    assert isinstance(snap.dashboard_summary, str)
