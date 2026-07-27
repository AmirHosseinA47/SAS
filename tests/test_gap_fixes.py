"""Regression tests for adaptation gap fixes."""

from __future__ import annotations

from src_extension.adaptation.failsafe_adaptation_generator import FailSafeAdaptationGenerator
from src_extension.adaptation.global_adaptation_generator import GlobalAdaptationSpaceGenerator
from src_extension.adaptation.local_adaptation_generator import LocalAdaptationSpaceGenerator
from src_extension.adaptation.rescue_adaptation_generator import RescueAdaptationSpaceGenerator


def _minimal_global_result_no_triggers_no_region_signals() -> dict:
    return {
        "triggers": [],
        "target_entity": "mission",
        "fire_probability_map": {},
        "fire_confidence_map": {},
        "uncertainty_map": {},
        "victim_confidence": {},
        "last_known_fire_regions": [],
        "communication_support_zones": [],
        "uncertainty_regions": [],
        "critical_regions": [],
        "region_value_map": {},
        "battery": {},
        "negative_observation_maps": {},
        "stale_information": {},
    }


def test_global_space_includes_stability_control_do_nothing() -> None:
    gen = GlobalAdaptationSpaceGenerator()
    space = gen.generate(
        _minimal_global_result_no_triggers_no_region_signals(),
        runtime_models={},
        timestamp=0.0,
    )
    noop = [
        o
        for o in space.options
        if o.option_type == "stability_control"
        and o.parameters.get("do_nothing") is True
        and o.parameters.get("stability_action") == "maintain_current_config"
    ]
    assert len(noop) == 1
    assert noop[0].option_id == "global_stability_maintain_current_config"


def test_global_task_allocation_nonempty_without_triggers() -> None:
    gen = GlobalAdaptationSpaceGenerator()
    space = gen.generate(
        _minimal_global_result_no_triggers_no_region_signals(),
        runtime_models={},
        timestamp=0.0,
    )
    task_opts = [o for o in space.options if o.option_type == "task_allocation"]
    assert len(task_opts) > 0


def test_global_resource_reallocation_nonempty_without_triggers() -> None:
    gen = GlobalAdaptationSpaceGenerator()
    space = gen.generate(
        _minimal_global_result_no_triggers_no_region_signals(),
        runtime_models={},
        timestamp=0.0,
    )
    res_opts = [o for o in space.options if o.option_type == "resource_reallocation"]
    assert len(res_opts) > 0


def test_local_space_includes_stability_control_do_nothing() -> None:
    gen = LocalAdaptationSpaceGenerator()
    space = gen.generate(
        local_analysis_result={
            "triggers": [],
            "target_entity": "uav-1",
            "local_uncertainty": {},
            "fire_belief": {},
            "victim_confidence": {},
            "stale_regions": [],
        },
        local_models={
            "local_uncertainty": {},
            "fire_belief": {},
            "victim_confidence": {},
            "stale_regions": [],
        },
        runtime_models={"uav_id": "uav-1"},
        timestamp=1.0,
    )
    noop = [
        o
        for o in space.options
        if o.option_type == "stability_control"
        and o.parameters.get("do_nothing") is True
        and o.parameters.get("stability_action") == "maintain_current_config"
    ]
    assert len(noop) == 1
    assert noop[0].option_id == "local_stability_maintain_current_config_uav-1"


def test_local_sensing_nonempty_without_evidence_or_triggers() -> None:
    gen = LocalAdaptationSpaceGenerator()
    space = gen.generate(
        local_analysis_result={
            "triggers": [],
            "target_entity": "uav-1",
            "local_uncertainty": {},
            "fire_belief": {},
            "victim_confidence": {},
            "stale_regions": [],
        },
        local_models={
            "local_uncertainty": {},
            "fire_belief": {},
            "victim_confidence": {},
            "stale_regions": [],
        },
        runtime_models={"uav_id": "uav-1"},
        timestamp=1.0,
    )
    sensing = [o for o in space.options if o.option_type == "sensing_strategy"]
    assert len(sensing) > 0


def test_rescue_space_includes_rescue_do_nothing_baseline() -> None:
    gen = RescueAdaptationSpaceGenerator()
    space = gen.generate(
        rescue_analysis_result={"triggers": [], "target_entity": "mission"},
        runtime_models={},
        timestamp=1.0,
    )
    assert sum(
        1
        for o in space.options
        if o.option_id == "rescue_stability_maintain_current_rescue_state"
    ) == 1


def test_failsafe_space_includes_failsafe_do_nothing_baseline() -> None:
    gen = FailSafeAdaptationGenerator()
    space = gen.generate(
        fail_safe_analysis_result={"triggers": []},
        runtime_models={},
        timestamp=1.0,
    )
    assert sum(
        1
        for o in space.options
        if o.option_id == "failsafe_stability_maintain_current_failsafe_state"
    ) == 1
