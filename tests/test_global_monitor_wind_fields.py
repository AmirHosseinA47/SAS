"""Global monitoring: native wind fields on GlobalObservationSnapshot."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

from dataclasses import fields

import common_fixed_variables as cfv
from common_fixed_variables import wind_vector_from_direction
from src_extension.monitoring.monitoring_interfaces import GlobalObservationSnapshot
from wildfire_model import WildFireModel


def test_global_observation_snapshot_declares_wind_fields() -> None:
    names = {f.name for f in fields(GlobalObservationSnapshot)}
    assert "wind_direction" in names
    assert "wind_vector" in names
    assert "wind_source" in names
    assert "wind_timestamp" in names
    assert "observation_step" in names


def test_global_monitor_populates_wind_fields() -> None:
    model = WildFireModel()
    model.wind.wind_direction = "east"
    model._sync_environment_wind(1.0)
    snapshot = model.global_monitor.collect_global_snapshot(model, 1.0)
    model.latest_global_snapshot = snapshot

    assert snapshot.wind_direction == "east"
    assert snapshot.wind_vector == (1.0, 0.0)
    assert snapshot.wind_source in ("fire_model", "environment_bridge")
    assert snapshot.wind_timestamp >= 0.0
    assert snapshot.observation_step >= 0
    assert snapshot.visibility_summary.get("wind_direction") == "east"


def test_changing_wind_direction_changes_snapshot_vector() -> None:
    model = WildFireModel()

    model.wind.wind_direction = "north"
    model._sync_environment_wind(2.0)
    north_snap = model.global_monitor.collect_global_snapshot(model, 2.0)

    model.wind.wind_direction = "south"
    model._sync_environment_wind(3.0)
    south_snap = model.global_monitor.collect_global_snapshot(model, 3.0)

    assert north_snap.wind_vector == wind_vector_from_direction("north")
    assert south_snap.wind_vector == wind_vector_from_direction("south")
    assert north_snap.wind_vector != south_snap.wind_vector


def test_analysis_snapshot_includes_wind_from_global_snapshot() -> None:
    model = WildFireModel()
    model.wind.wind_direction = "west"
    model._sync_environment_wind(4.0)
    snapshot = model.global_monitor.collect_global_snapshot(model, 4.0)
    model._run_analysis(4.0, snapshot)

    assert model.latest_analysis_snapshot is not None
    global_result = model.latest_analysis_snapshot.global_result
    assert "west" in global_result.explanation_context


def test_wind_summary_prefers_global_snapshot_over_bridge() -> None:
    model = WildFireModel()
    model.wind.wind_direction = "south"
    model._sync_environment_wind(5.0)
    snapshot = model.global_monitor.collect_global_snapshot(model, 5.0)
    summary = model._wind_summary_for_operational_picture(snapshot)
    assert summary["direction"] == "south"
    assert summary["vector"] == [0.0, -1.0]


def test_latest_global_snapshot_after_step_has_wind() -> None:
    cfv.WIND_DIRECTION = "north"
    model = WildFireModel()
    model.step()
    snap = model.latest_global_snapshot
    assert snap is not None
    assert snap.wind_direction == "north"
    assert snap.wind_vector == (0.0, 1.0)
