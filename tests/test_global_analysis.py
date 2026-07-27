"""Global analyzer triggers."""

from __future__ import annotations

from src_extension.analysis.global_analyzer import GlobalAnalyzer
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture
from src_extension.knowledge.uav_resource_model import UAVResourceModel, UAVResourceRuntimeState


def _trigger_types(result: object) -> set[str]:
    return {t.trigger_type for t in result.trigger_list}


def test_high_uncertainty_region_from_uncertainty_summary() -> None:
    analyzer = GlobalAnalyzer()
    sop = SharedOperationalPicture()
    global_snapshot = {
        "uncertainty_summary": {
            "staleness_map": {"c0": 0.75, "c1": 0.75},
        },
    }
    result = analyzer.analyze(sop, global_snapshot, {}, timestamp=0.0)
    assert "HIGH_UNCERTAINTY_REGION" in _trigger_types(result)


def test_search_mode_required_low_gain_and_high_fire_belief() -> None:
    analyzer = GlobalAnalyzer(fire_probability_threshold=0.7)
    sop = SharedOperationalPicture()
    global_snapshot = {
        "uncertainty_summary": {"total_information_gain": 0.02},
        "fire_belief_summary": {"fire_probability_map": {"x": 0.85}},
        "fire_state_summary": {"estimated_burning_cells": []},
    }
    result = analyzer.analyze(sop, global_snapshot, {}, timestamp=1.0)
    types = _trigger_types(result)
    assert "SEARCH_MODE_REQUIRED" in types


def test_critical_link_unreliable_low_comm_confidence() -> None:
    analyzer = GlobalAnalyzer()
    sop = SharedOperationalPicture()
    global_snapshot = {
        "communication_summary": {"critical_link_reliability": 0.1},
    }
    result = analyzer.analyze(sop, global_snapshot, {}, timestamp=0.0)
    assert "CRITICAL_LINK_UNRELIABLE" in _trigger_types(result)


def test_oscillation_risk_high_role_switch_count() -> None:
    analyzer = GlobalAnalyzer()
    sop = SharedOperationalPicture()
    st = UAVResourceRuntimeState(
        uav_id="u1",
        role_switch_count=5,
        role_stability_timer=100.0,
        task_commitment_age=100.0,
        local_plan_reliability=0.8,
    )
    urm = UAVResourceModel(by_uav_id={"u1": st})
    result = analyzer.analyze(sop, {}, {"uav_resource_model": urm}, timestamp=0.0)
    assert "OSCILLATION_RISK" in _trigger_types(result)
