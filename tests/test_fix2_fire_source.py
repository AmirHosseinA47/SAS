"""fix2 row (B): the global analyzer reads the fire picture from FireRuntimeModel.belief.

GLOBAL_ANALYZER_FIRE_SOURCE_FIX (shipped 1; off only on an exact integral 0). Before the fix the
analyzer read the fire maps, the front cells and the spread bias as top-level attributes of the
fire runtime model, which do not exist - every fire trigger of the global layer was silent.
"""

from __future__ import annotations

import common_fixed_variables as cfv
import pytest

from src_extension.analysis.global_analyzer import GlobalAnalyzer
from src_extension.knowledge.fire_runtime_model import FireRuntimeModel
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture


def _types(result) -> set[str]:
    return {t.trigger_type for t in result.trigger_list}


def _fire_model(cells, times=2, timestamp=1.0) -> FireRuntimeModel:
    fr = FireRuntimeModel()
    fr.initialize_grid(10, 10)
    for _ in range(times):  # two full-confidence sightings: p 0 -> 0.5 -> 0.75 (>= 0.7)
        for c in cells:
            fr.update_fire_observation(c, timestamp=timestamp, source="test", confidence=1.0, probability=1.0)
    return fr


@pytest.fixture
def switch(monkeypatch):
    def set_(value):
        monkeypatch.setattr(cfv, "GLOBAL_ANALYZER_FIRE_SOURCE_FIX", value, raising=False)
    return set_


def test_shipped_on():
    import agents

    assert agents.global_analyzer_fire_source_fix() is True


@pytest.mark.parametrize("value, expected", [(0, False), (0.0, False), (1, True), (2, True),
                                             (0.5, True), ("0", False), ("off", True), (None, True)])
def test_switch_is_off_only_on_an_exact_integral_zero(switch, value, expected):
    import agents

    switch(value)
    assert agents.global_analyzer_fire_source_fix() is expected


def test_high_priority_fire_region_reads_the_belief(switch):
    fr = _fire_model([(2, 2), (2, 3), (3, 2)])
    runtime = {"fire_runtime_model": fr}
    switch(1)
    on = GlobalAnalyzer().analyze(SharedOperationalPicture(), {}, runtime, timestamp=2.0)
    assert "HIGH_PRIORITY_FIRE_REGION" in _types(on)
    switch(0)
    off = GlobalAnalyzer().analyze(SharedOperationalPicture(), {}, runtime, timestamp=2.0)
    assert "HIGH_PRIORITY_FIRE_REGION" not in _types(off)


def test_stale_high_priority_region_from_old_observations(switch):
    fr = _fire_model([(4, 4)], timestamp=1.0)
    switch(1)
    result = GlobalAnalyzer().analyze(SharedOperationalPicture(), {}, {"fire_runtime_model": fr},
                                      timestamp=40.0)  # 39 > stale_information_threshold (10)
    assert "STALE_HIGH_PRIORITY_REGION" in _types(result)


def test_fire_spread_accelerating_sees_the_belief_front(switch):
    switch(1)
    analyzer = GlobalAnalyzer()
    sop = SharedOperationalPicture()
    small = _fire_model([(1, 1)])
    analyzer.analyze(sop, {}, {"fire_runtime_model": small}, timestamp=1.0)
    big = _fire_model([(x, y) for x in range(1, 6) for y in (1, 6)])  # 10 front cells
    result = analyzer.analyze(sop, {}, {"fire_runtime_model": big}, timestamp=2.0)
    assert "FIRE_SPREAD_ACCELERATING" in _types(result)


def test_stand_in_without_belief_is_read_directly(switch):
    class StandIn:
        fire_probability_map = {"a": 0.9}
        fire_confidence_map = {"a": 0.9}
        last_observed_fire_time = {"a": 1.0}

    for value in (0, 1):
        switch(value)
        result = GlobalAnalyzer().analyze(SharedOperationalPicture(), {}, {"fire_runtime_model": StandIn()},
                                          timestamp=2.0)
        assert "HIGH_PRIORITY_FIRE_REGION" in _types(result)


def test_snapshot_fire_state_summary_keeps_precedence(switch):
    # the existing snapshot path (tests/test_global_analysis.py) is unchanged by the switch
    switch(1)
    snapshot = {
        "uncertainty_summary": {"total_information_gain": 0.02},
        "fire_belief_summary": {"fire_probability_map": {"x": 0.85}},
        "fire_state_summary": {"estimated_burning_cells": []},
    }
    result = GlobalAnalyzer(fire_probability_threshold=0.7).analyze(
        SharedOperationalPicture(), snapshot, {}, timestamp=1.0)
    assert "SEARCH_MODE_REQUIRED" in _types(result)


def test_old_global_search_test_stays_silent_on_the_belief(switch):
    # outputs/fix2_part1.txt 1d: with the estimated-burning set read from the belief, "visible empty"
    # and "high belief" contradict each other at the same 0.7 threshold - dead by construction.
    switch(1)
    fr = _fire_model([(2, 2)])
    result = GlobalAnalyzer().analyze(SharedOperationalPicture(), {}, {"fire_runtime_model": fr},
                                      timestamp=2.0)
    assert "SEARCH_MODE_REQUIRED" not in _types(result)
