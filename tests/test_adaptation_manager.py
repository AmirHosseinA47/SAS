"""AdaptationManager MAPE-K orchestration status."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

from src_extension.adaptation_manager import AdaptationManager
from wildfire_model import WildFireModel


def test_adaptation_manager_run_step_reports_pipeline_status_after_model_step() -> None:
    model = WildFireModel()
    model.step()

    manager = AdaptationManager()
    step_index = int(model.evaluation_timesteps_counter)
    out = manager.run_step(step_index, model)

    for key in (
        "monitoring_available",
        "knowledge_available",
        "analysis_available",
        "adaptation_space_available",
        "planning_available",
        "execution_available",
        "status",
    ):
        assert key in out

    assert out["monitoring_available"] is True
    assert out["knowledge_available"] is True
    assert out["analysis_available"] is True
    assert out["adaptation_space_available"] is True
    assert out["planning_available"] is True
    assert out["execution_available"] is True
    assert out["status"] == "full_mape_cycle_ready"
    assert out["step_index"] == step_index
