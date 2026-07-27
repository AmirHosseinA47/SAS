"""Option-comparison explanations and JSON export tests."""

from __future__ import annotations

import json
import os
import random
import tempfile
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.dashboard.comparison_parser import parse_comparison_summary
from src_extension.dashboard.dashboard_exporter import DashboardStateExporter
from src_extension.dashboard.explanation_engine import ExplanationEngine
from src_extension.execution.failsafe_modes import FailSafeMode, FailSafeReason, FailSafeState
from src_extension.planning.decision_objects import FailSafeDecision, PathDecision, RescueDecision
from wildfire_model import WildFireModel

_SAMPLE_PATH_SUMMARY = """Local path option comparison (2501)
- Candidates evaluated: 4
  1. wind_aware_victim_search [search] score=1.6400 feasible=True
  2. stability_hold [stability] score=0.0000 feasible=True
  3. explore_unknown_region_2501_40 [explore] score=0.0000 feasible=True
  4. do_nothing [hold] score=0.0000 feasible=False
- Top ranked id: wind_aware_victim_search (feasible=True)
"""

_SAMPLE_FAILSAFE_SUMMARY = """Fail-safe option comparison
- Candidates evaluated: 3
- Prefer search-mode options: True
- Classified fail-safe mode: information_recovery
- Fail-safe reasons: search_mode_required, information_insufficient
  1. information_recovery_search [search] score=2.7600 pref_bonus=0.500 feasible=True
  2. safe_hold [stability] score=0.1800 pref_bonus=0.000 feasible=True
- Top utility-ranked id: information_recovery_search (feasible=True)
"""

_SAMPLE_RESCUE_SUMMARY = """Rescue option comparison
- Candidates evaluated: 2
  1. assign_ff_unit_1 [assign] score=0.8500 pref_bonus=0.100 feasible=True
  2. delay_rescue [delay] score=0.1200 pref_bonus=0.000 feasible=True
- Top utility-ranked id: assign_ff_unit_1 (feasible=True)
"""


def _scenario_a_model(*, batch_size: int = 50, seed: int = 42) -> WildFireModel:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv,
        wf,
        NUM_AGENTS=2,
        NUM_VICTIMS=3,
        NUM_FIREFIGHTERS=3,
        FIRE_SPREAD_MULTIPLIER=0.75,
        BATCH_SIZE=batch_size,
        FIXED_WIND=True,
        WIND_DIRECTION="east",
    )
    model = WildFireModel()
    model.debug_log = False
    return model


def _attach_planning(model: WildFireModel) -> None:
    model.latest_planning_result = {
        "mission_decision": SimpleNamespace(
            selected_option_id="maintain_roles",
            comparison_summary={"summary": _SAMPLE_PATH_SUMMARY.replace("2501", "mission")},
            confidence_score=0.8,
            explanation="Maintain current roles.",
        ),
        "rescue_decision": RescueDecision(
            decision_id="r1",
            selected_option_id="assign_ff_unit_1",
            rescue_action="assign",
            victim_id="victim_1",
            firefighter_id="ff_unit_1",
            comparison_summary={"summary": _SAMPLE_RESCUE_SUMMARY},
            confidence_score=0.85,
            explanation="Assign closest firefighter.",
        ),
        "fail_safe_decision": FailSafeDecision(
            decision_id="fs1",
            selected_option_id="information_recovery_search",
            fail_safe_action="search",
            search_mode_active=True,
            mission_mode="information_recovery",
            comparison_summary={"summary": _SAMPLE_FAILSAFE_SUMMARY},
            confidence_score=0.7,
            explanation="Search mode under uncertainty.",
        ),
        "path_decisions": {
            "2501": PathDecision(
                decision_id="p1",
                uav_id="2501",
                selected_option_id="wind_aware_victim_search",
                next_action="victim_search_wind_aware",
                comparison_summary={"summary": _SAMPLE_PATH_SUMMARY},
                confidence_score=0.9,
                explanation="Wind-aware search preferred.",
            ),
        },
    }


def test_option_comparison_parses_real_scores() -> None:
    parsed = parse_comparison_summary({"summary": _SAMPLE_PATH_SUMMARY})
    alts = parsed["alternatives"]
    assert len(alts) == 4
    top = alts[0]
    assert top["option_id"] == "wind_aware_victim_search"
    assert top["score"] == 1.64
    assert alts[1]["score"] == 0.0

    failsafe = parse_comparison_summary({"summary": _SAMPLE_FAILSAFE_SUMMARY})
    assert failsafe["alternatives"][0]["score"] == 2.76
    assert failsafe["alternatives"][0]["pref_bonus"] == 0.5

    non_scoring = parse_comparison_summary({"summary": "Classified fail-safe mode: emergency\n- Fail-safe reasons: none"})
    assert non_scoring["alternatives"] == []
    assert "Classified fail-safe mode" in non_scoring["summary_text"]


def test_explanation_engine_creates_option_comparison_when_data_available() -> None:
    model = _scenario_a_model()
    _attach_planning(model)
    bundle = ExplanationEngine().collect_bundle(model)
    option_expls = [
        s for s in bundle.structured_explanations if s.get("explanation_kind") == "option_comparison"
    ]
    assert len(option_expls) >= 4
    assert bundle.option_comparison_count >= 4
    path_expl = next(e for e in option_expls if e.get("target_id") == "2501")
    assert path_expl["selected_option"] == "wind_aware_victim_search"
    assert path_expl["selected_score"] == 1.64
    assert len(path_expl["alternatives"]) >= 2


def test_explanation_engine_handles_missing_alternatives_gracefully() -> None:
    model = _scenario_a_model()
    model.latest_planning_result = {
        "mission_decision": SimpleNamespace(
            selected_option_id="noop",
            comparison_summary={},
            confidence_score=0.0,
            explanation="",
        ),
    }
    records = ExplanationEngine().collect_explanations(model)
    mission = next(r for r in records if r.decision_type == "mission_option_comparison")
    assert mission.alternatives_considered == []
    assert "No comparable option summary available from planner." in mission.reason


def test_explanation_engine_creates_uncertainty_explanation_for_information_recovery() -> None:
    model = _scenario_a_model()
    _attach_planning(model)
    model.latest_failsafe_state = FailSafeState(
        mode=FailSafeMode.INFORMATION_RECOVERY,
        active_reasons=(FailSafeReason.SEARCH_MODE_REQUIRED, FailSafeReason.INFORMATION_INSUFFICIENT),
        explanation="Information recovery due to search-mode-required trigger.",
    )
    bundle = ExplanationEngine().collect_bundle(model)
    uncertainty = [s for s in bundle.structured_explanations if s.get("explanation_kind") == "uncertainty"]
    assert len(uncertainty) >= 1
    triggers = {u["trigger"] for u in uncertainty}
    assert "search_mode_required" in triggers or "information_insufficient" in triggers


def test_explanation_engine_creates_rescue_assignment_explanation() -> None:
    model = _scenario_a_model()
    model._rescue_event_log.append(
        {
            "step": 7,
            "victim_id": "victim_1",
            "firefighter_id": "ff_unit_1",
            "event_type": "dispatch_initial",
            "reason": "initial",
            "metadata": {},
        }
    )
    records = ExplanationEngine().collect_explanations(model)
    assignment = next(r for r in records if r.decision_type == "rescue_assignment")
    assert "ff_unit_1" in assignment.reason
    assert "victim_1" in assignment.reason
    assert "dispatch_initial" in assignment.reason


def test_explanation_engine_skips_firefighter_safety_explanation_when_unavailable() -> None:
    model = _scenario_a_model()
    for _ in range(3):
        model.step()
    bundle = ExplanationEngine().collect_bundle(model)
    kinds = {s.get("explanation_kind") for s in bundle.structured_explanations}
    decision_types = {e.decision_type for e in ExplanationEngine().collect_explanations(model)}
    assert "firefighter_detour" not in kinds
    assert "idle_firefighter_survival_move" not in kinds
    assert not any("survival_move" in dt for dt in decision_types)


def test_dashboard_exporter_writes_json_files() -> None:
    model = _scenario_a_model()
    _attach_planning(model)
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        exporter = DashboardStateExporter(output_dir=out_dir)
        paths = exporter.export_all(model)
        assert paths["dashboard_state"].exists()
        assert paths["timeline"].exists()
        assert paths["explanations"].exists()
        assert paths["dashboard_state"].suffix == ".json"


def test_exported_dashboard_json_is_valid_and_serializable() -> None:
    model = _scenario_a_model()
    for _ in range(5):
        model.step()
    with tempfile.TemporaryDirectory() as tmp:
        exporter = DashboardStateExporter(output_dir=Path(tmp))
        state_path = exporter.export_dashboard_state(model)
        expl_path = exporter.export_explanations(model)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        expl = json.loads(expl_path.read_text(encoding="utf-8"))
        json.dumps(state)
        json.dumps(expl)
        assert "structured_explanations" in state or "explanation_list" in state
        assert "structured_explanations" in expl


def test_export_does_not_mutate_model() -> None:
    model = _scenario_a_model()
    for _ in range(3):
        model.step()
    before_step = model.evaluation_timesteps_counter
    before_log_len = len(model._rescue_event_log)
    with tempfile.TemporaryDirectory() as tmp:
        DashboardStateExporter(output_dir=Path(tmp)).export_all(model)
    assert model.evaluation_timesteps_counter == before_step
    assert len(model._rescue_event_log) == before_log_len
