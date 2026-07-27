"""AdaptationManager.run_cycle orchestration tests."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

import common_fixed_variables as cfv
from src_extension.adaptation_manager import AdaptationManager
from wildfire_model import WildFireModel


PRE_MOVE_STAGE_ORDER = (
    "_sync_environment_wind",
    "_detect_victims_in_uav_radius",
    "_process_rescue_incidents",
    "_rebuild_shared_operational_picture",
    "_refresh_mission_goal_model",
    "_refresh_local_path_context_models",
    "_run_analysis",
    "_run_adaptation_space_generation",
    "_run_planning",
    "_update_failsafe_mode",
    "_run_execution",
    "_update_failsafe_mode",
)

POST_MOVE_STAGE_ORDER = (
    "_process_pending_agent_removals",
    "_clear_rescue_path_if_requested",
    "_update_uav_stuck_counts_after_move",
    "_update_managed_uav_states_from_agents",
    "_refresh_local_path_context_models",
    "_refresh_post_move_environment_bridge",
    "_collect_post_move_monitoring_snapshots",
    "_detect_victims_in_uav_radius",
    "_process_rescue_incidents",
    "_refresh_knowledge_from_post_move_monitoring",
    "_check_fire_casualties",
    "_process_rescue_incidents",
    "_sync_firefighter_marker_status",
    "_sync_victim_agent_status",
    "_assert_no_direct_rescue_mutation",
)


class _FakeModel:
    def __init__(self) -> None:
        self.evaluation_timesteps_counter = 3
        self.call_log: list[str] = []
        self.latest_global_snapshot = None
        self.latest_environment_bridge_snapshot = None
        self.latest_analysis_snapshot = None
        self.latest_adaptation_space_snapshot = None
        self.latest_planning_result = None
        self.latest_execution_result = None
        self.latest_failsafe_state = None
        self.latest_failsafe_dashboard_summary = None
        self.latest_communication_execution = None
        self.latest_execution_feedback_event = None
        self._rescue_incident_queue: list[dict[str, object]] = []
        self.monitoring_buffer = SimpleNamespace(local_observations={})
        self.knowledge_manager = SimpleNamespace()
        self.shared_operational_picture = SimpleNamespace()
        self.global_monitor = SimpleNamespace(
            collect_global_snapshot=lambda model, ts: SimpleNamespace(
                timestamp=float(ts),
                observation_step=int(ts),
                uncertainty_summary={
                    "avg_normalized_information_gain": 0.0,
                    "aggregated_uncertain_cell_count": 0,
                },
            )
        )

    def _sync_environment_wind(self, current_step_time: float) -> None:
        self.call_log.append("_sync_environment_wind")

    def _detect_victims_in_uav_radius(self) -> None:
        self.call_log.append("_detect_victims_in_uav_radius")

    def _process_rescue_incidents(self) -> None:
        self.call_log.append("_process_rescue_incidents")
        self._rescue_incident_queue.clear()

    def _rebuild_shared_operational_picture(
        self, current_step_time: float, global_snapshot: object
    ) -> None:
        self.call_log.append("_rebuild_shared_operational_picture")

    def _refresh_mission_goal_model(self, current_step_time: float) -> None:
        self.call_log.append("_refresh_mission_goal_model")

    def _refresh_local_path_context_models(self, current_step_time: float) -> None:
        self.call_log.append("_refresh_local_path_context_models")

    def _run_analysis(self, current_step_time: float, global_snapshot: object) -> None:
        self.call_log.append("_run_analysis")
        self.latest_analysis_snapshot = SimpleNamespace(
            timestamp=float(current_step_time),
            all_triggers=(),
            dashboard_summary="analysis ok",
        )

    def _run_adaptation_space_generation(self) -> None:
        self.call_log.append("_run_adaptation_space_generation")
        self.latest_adaptation_space_snapshot = SimpleNamespace(
            timestamp=3.0,
            all_options=[object()],
            explanation_summaries=["generated_options=1"],
            dashboard_summary="adaptation ok",
        )

    def _run_planning(self, current_step_time: float) -> None:
        self.call_log.append("_run_planning")
        self.latest_planning_result = {
            "mission_decision": object(),
            "path_decisions": {"0": object()},
            "communication_decision": {"communication_mode": "normal"},
            "dashboard_summary": "planning ok",
        }

    def _update_failsafe_mode(self, current_step_time: float) -> None:
        self.call_log.append("_update_failsafe_mode")
        self.latest_failsafe_state = SimpleNamespace(
            mode=SimpleNamespace(value="normal"),
            explanation="nominal",
        )
        self.latest_failsafe_dashboard_summary = "failsafe ok"

    def _run_execution(self, current_step_time: float) -> None:
        self.call_log.append("_run_execution")
        self.latest_execution_result = {
            "applied": True,
            "communication": {"applied": True},
            "local": {"applied": True},
        }
        self.latest_communication_execution = {
            "applied": True,
            "communication_mode": "normal",
        }

    def _process_pending_agent_removals(self) -> int:
        self.call_log.append("_process_pending_agent_removals")
        return 0

    def _clear_rescue_path_if_requested(self) -> bool:
        self.call_log.append("_clear_rescue_path_if_requested")
        return False

    def _update_uav_stuck_counts_after_move(self) -> None:
        self.call_log.append("_update_uav_stuck_counts_after_move")

    def _update_managed_uav_states_from_agents(self) -> None:
        self.call_log.append("_update_managed_uav_states_from_agents")

    def _refresh_post_move_environment_bridge(self, current_step_time: float) -> None:
        self.call_log.append("_refresh_post_move_environment_bridge")
        self.latest_environment_bridge_snapshot = {"step": current_step_time}

    def _collect_post_move_monitoring_snapshots(self, current_step_time: float) -> object:
        self.call_log.append("_collect_post_move_monitoring_snapshots")
        snapshot = SimpleNamespace(
            timestamp=float(current_step_time),
            observation_step=int(current_step_time),
            uncertainty_summary={
                "avg_normalized_information_gain": 0.0,
                "aggregated_uncertain_cell_count": 0,
            },
        )
        self.latest_global_snapshot = snapshot
        return snapshot

    def _refresh_knowledge_from_post_move_monitoring(
        self, current_step_time: float, global_snapshot: object
    ) -> None:
        self.call_log.append("_refresh_knowledge_from_post_move_monitoring")
        self.latest_global_snapshot = global_snapshot

    def _check_fire_casualties(self) -> None:
        self.call_log.append("_check_fire_casualties")

    def _sync_firefighter_marker_status(self) -> None:
        self.call_log.append("_sync_firefighter_marker_status")

    def _sync_victim_agent_status(self) -> None:
        self.call_log.append("_sync_victim_agent_status")

    def _assert_no_direct_rescue_mutation(self) -> None:
        self.call_log.append("_assert_no_direct_rescue_mutation")


def test_run_cycle_calls_stages_in_correct_order() -> None:
    model = _FakeModel()
    model._rescue_incident_queue.append({"type": "victim_confirmed", "victim_id": "v1"})
    manager = AdaptationManager()

    result = manager.run_cycle(model, phase="pre_move")

    assert model.call_log == list(PRE_MOVE_STAGE_ORDER)
    assert result["phase"] == "pre_move"
    assert result["step_time"] == 3.0
    assert result["rescue_events"]["count"] == 1
    assert result["rescue_events"]["processed"] is True


def test_post_move_phase_calls_expected_methods_in_order() -> None:
    model = _FakeModel()
    model._rescue_incident_queue.append({"type": "route_blocked", "victim_id": "v2"})
    manager = AdaptationManager()

    result = manager.run_cycle(model, phase="post_move")

    assert model.call_log == list(POST_MOVE_STAGE_ORDER)
    assert result["phase"] == "post_move"
    assert result["monitoring"]["available"] is True
    assert result["knowledge"]["available"] is True
    assert result["rescue_events"]["count"] == 1
    assert result["cleanup"]["pending_removals"] == 0


def test_run_cycle_returns_analysis_planning_execution_summaries() -> None:
    model = _FakeModel()
    manager = AdaptationManager()

    result = manager.run_cycle(model, phase="pre_move")

    assert result["monitoring"]["available"] is True
    assert result["analysis"]["available"] is True
    assert result["analysis"]["trigger_count"] == 0
    assert result["adaptation"]["available"] is True
    assert result["adaptation"]["option_count"] == 1
    assert result["planning"]["available"] is True
    assert result["planning"]["has_communication_decision"] is True
    assert result["execution"]["available"] is True
    assert result["execution"]["applied"] is True
    assert result["failsafe_mode"]["available"] is True
    assert result["communication"]["execution"]["applied"] is True
    assert "generated_options=1" in result["explanations"]


def test_wildfire_model_step_uses_adaptation_manager_when_extension_pipeline_active() -> None:
    model = WildFireModel()
    assert model._is_extension_pipeline_active()

    with patch.object(
        model.adaptation_manager,
        "run_cycle",
        wraps=model.adaptation_manager.run_cycle,
    ) as mock_run:
        model.step()
        assert mock_run.call_count == 2
        mock_run.assert_any_call(model, phase="pre_move")
        mock_run.assert_any_call(model, phase="post_move")

    assert model.latest_adaptation_cycle_result is not None
    assert model.latest_adaptation_cycle_result["phase"] == "pre_move"
    assert model.latest_post_move_cycle_result is not None
    assert model.latest_post_move_cycle_result["phase"] == "post_move"


def test_wildfire_model_step_populates_latest_post_move_cycle_result() -> None:
    model = WildFireModel()
    model.step()

    post_move = model.latest_post_move_cycle_result
    assert post_move is not None
    assert post_move["phase"] == "post_move"
    assert post_move["monitoring"]["available"] is True
    assert post_move["knowledge"]["available"] is True


def test_rescue_incidents_and_communication_execution_appear_after_run_cycle() -> None:
    model = WildFireModel()
    model.step()

    cycle = model.latest_adaptation_cycle_result
    assert cycle is not None
    assert "rescue_events" in cycle
    assert isinstance(cycle["rescue_events"], dict)
    assert "communication" in cycle
    assert model.latest_communication_execution is not None or cycle["communication"]["available"]


def test_communication_execution_from_pre_move_unaffected_by_post_move() -> None:
    model = WildFireModel()
    model.step()

    pre_move = model.latest_adaptation_cycle_result
    post_move = model.latest_post_move_cycle_result
    assert pre_move is not None
    assert post_move is not None
    assert pre_move.get("communication") is not None
    assert model.latest_communication_execution is not None
    assert post_move["communication"]["communication_mode"] == pre_move["communication"]["communication_mode"]


def test_rescue_completion_and_casualty_handling_still_work_after_post_move_cycle() -> None:
    model = WildFireModel()
    model.step()

    post_move = model.latest_post_move_cycle_result
    assert post_move is not None
    assert "rescue_sync" in post_move
    assert "rescue_events" in post_move

    model._check_fire_casualties()
    assert callable(model._sync_firefighter_marker_status)
    assert callable(model._sync_victim_agent_status)


def test_fifty_step_simulation_still_runs() -> None:
    import random

    import agents
    import wildfire_model as wf

    rng = random.Random(42)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    original_batch = cfv.BATCH_SIZE
    cfv.BATCH_SIZE = 99_999
    try:
        model = WildFireModel()
        for step in range(1, 51):
            model.step()
            assert model.latest_adaptation_cycle_result is not None
            assert model.latest_adaptation_cycle_result["step_time"] == float(step)
            assert model.latest_post_move_cycle_result is not None
            assert model.latest_post_move_cycle_result["step_time"] == float(step)
    finally:
        cfv.BATCH_SIZE = original_batch


def test_run_cycle_rejects_unknown_phase() -> None:
    manager = AdaptationManager()
    with pytest.raises(ValueError, match="unsupported adaptation cycle phase"):
        manager.run_cycle(_FakeModel(), phase="mid_move")
