"""Global adaptation-space generation."""

from src_extension.adaptation.global_adaptation_generator import GlobalAdaptationSpaceGenerator


def _trigger(trigger_type: str, explanation_context: str = "") -> dict:
    return {
        "trigger_type": trigger_type,
        "confidence": 0.8,
        "explanation_context": explanation_context or trigger_type,
    }


def _generate_global_space(triggers: list[dict] | None = None):
    generator = GlobalAdaptationSpaceGenerator()
    return generator.generate(
        global_analysis_result={
            "triggers": triggers or [],
            "target_entity": "mission",
            "fire_probability_map": {"r1": 0.9, "r2": 0.1},
            "fire_confidence_map": {"r1": 0.2, "r2": 0.9},
            "uncertainty_map": {"r1": 0.8},
            "uncertainty_regions": ["r1"],
            "battery": {"uav-1": 0.2},
            "critical_regions": ["r1"],
            "region_value_map": {"r2": 0.1},
        },
        runtime_models={
            "battery": {"uav-1": 0.2},
            "battery_state": {"uav-1": "low"},
            "uncertainty_regions": ["r1"],
            "critical_regions": ["r1"],
        },
        timestamp=1.0,
    )


def _option_ids(space) -> set[str]:
    return {option.option_id for option in space.options}


def test_maintain_current_role_option_always_exists() -> None:
    assert "global_role_assignment_maintain_current" in _option_ids(
        _generate_global_space()
    )


def test_uncertainty_reduction_strategy_exists_under_uncertainty_trigger() -> None:
    space = _generate_global_space([_trigger("UNCERTAINTY_TOO_HIGH")])

    assert "global_coverage_strategy_uncertainty_reduction_mode" in _option_ids(space)


def test_belief_gap_reduction_option_generated() -> None:
    space = _generate_global_space()
    option = next(
        option
        for option in space.options
        if option.option_id == "global_coverage_strategy_belief_gap_reduction_strategy"
    )

    assert option.parameters["target_regions"] == ["r1"]


def test_resource_reallocation_options_generated_under_low_battery() -> None:
    space = _generate_global_space([_trigger("LOW_BATTERY")])

    assert any(
        option.option_type == "resource_reallocation" for option in space.options
    )


def test_fail_safe_mission_options_generated_under_information_collapse() -> None:
    space = _generate_global_space(
        [_trigger("INFORMATION_COLLAPSE", "information collapse")]
    )

    assert any(option.option_type == "fail_safe_mission" for option in space.options)
