"""Structured triggers and local UAV analyzer."""

from __future__ import annotations

import pytest

from src_extension.analysis.local_uav_analyzer import LocalUAVAnalyzer
from src_extension.analysis.trigger_objects import (
    AdaptationTrigger,
    CommunicationTrigger,
    InformationTrigger,
    RescueTrigger,
    ResourceTrigger,
    SafetyTrigger,
    Scope,
    Severity,
    StructuredTrigger,
    UncertaintyTrigger,
    trigger_to_dict,
)
from src_extension.knowledge.local_observation_model import LocalObservationModel
from src_extension.knowledge.local_path_context_model import LocalPathContextModel
from src_extension.knowledge.uav_resource_model import UAVResourceRuntimeState


REQUIRED_TRIGGER_FIELDS = (
    "trigger_type",
    "severity",
    "confidence",
    "scope",
    "affected_entities",
    "timestamp",
    "recommended_planner",
    "explanation_context",
)


@pytest.mark.parametrize(
    "cls",
    [
        AdaptationTrigger,
        SafetyTrigger,
        ResourceTrigger,
        RescueTrigger,
        CommunicationTrigger,
        UncertaintyTrigger,
        InformationTrigger,
    ],
)
def test_structured_trigger_has_required_fields(cls: type[StructuredTrigger]) -> None:
    t = cls(
        trigger_type="TEST",
        severity=Severity.MEDIUM,
        confidence=0.5,
        scope=Scope.LOCAL,
        affected_entities=("u1",),
        timestamp=1.0,
        recommended_planner="local_uav_path_planner",
        explanation_context="explanation",
    )
    for name in REQUIRED_TRIGGER_FIELDS:
        assert hasattr(t, name)
        assert getattr(t, name) is not None or name in ("explanation_context",)

    d = trigger_to_dict(t)
    for name in REQUIRED_TRIGGER_FIELDS:
        assert name in d


def _minimal_path_context(uav_id: str) -> LocalPathContextModel:
    return LocalPathContextModel(uav_id=uav_id)


def _minimal_resource_state(
    uav_id: str,
    *,
    battery_level: float | None = 80.0,
    drift_level: float | None = 0.0,
    local_plan_reliability: float | None = 0.9,
) -> UAVResourceRuntimeState:
    return UAVResourceRuntimeState(
        uav_id=uav_id,
        battery_level=battery_level,
        drift_level=drift_level,
        local_plan_reliability=local_plan_reliability,
    )


def test_low_battery_from_observation() -> None:
    uav_id = "0"
    obs_model = LocalObservationModel(uav_id=uav_id)
    path_model = _minimal_path_context(uav_id)
    state = _minimal_resource_state(uav_id, battery_level=80.0)
    latest = {"battery_level": 25.0, "battery_status": "nominal"}
    analyzer = LocalUAVAnalyzer()
    result = analyzer.analyze(
        uav_id, obs_model, path_model, state, latest, timestamp=10.0
    )
    types = {t.trigger_type for t in result.local_trigger_list}
    assert "LOW_BATTERY" in types
    low = next(t for t in result.local_trigger_list if t.trigger_type == "LOW_BATTERY")
    assert isinstance(low, ResourceTrigger)
    assert low.severity == Severity.HIGH


def test_drift_too_high_from_drift_error() -> None:
    uav_id = "0"
    obs_model = LocalObservationModel(uav_id=uav_id)
    path_model = _minimal_path_context(uav_id)
    state = _minimal_resource_state(uav_id, drift_level=0.0)
    latest = {"drift_error": 1.5}
    analyzer = LocalUAVAnalyzer()
    result = analyzer.analyze(
        uav_id, obs_model, path_model, state, latest, timestamp=10.0
    )
    types = {t.trigger_type for t in result.local_trigger_list}
    assert "DRIFT_TOO_HIGH" in types
    drift = next(t for t in result.local_trigger_list if t.trigger_type == "DRIFT_TOO_HIGH")
    assert isinstance(drift, SafetyTrigger)


def test_low_information_or_search_when_gain_low_and_uncertainty() -> None:
    uav_id = "0"
    obs_model = LocalObservationModel(uav_id=uav_id)
    obs_model.local_uncertainty_patch[(0, 0)] = 0.2
    obs_model.local_uncertainty_patch[(1, 1)] = 0.2
    path_model = _minimal_path_context(uav_id)
    state = _minimal_resource_state(uav_id)
    latest = {
        "normalized_information_gain": 0.01,
        "raw_information_gain": 0.01,
    }
    analyzer = LocalUAVAnalyzer()
    result = analyzer.analyze(
        uav_id, obs_model, path_model, state, latest, timestamp=10.0
    )
    types = {t.trigger_type for t in result.local_trigger_list}
    assert "LOW_INFORMATION_GAIN" in types or "SEARCH_MODE_REQUIRED" in types
