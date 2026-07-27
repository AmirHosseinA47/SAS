"""Local adaptation-space generation."""

from src_extension.adaptation.local_adaptation_generator import LocalAdaptationSpaceGenerator


def _trigger(trigger_type: str, explanation_context: str = "") -> dict:
    return {
        "trigger_type": trigger_type,
        "confidence": 0.8,
        "explanation_context": explanation_context or trigger_type,
    }


def _generate_local_space(triggers: list[dict] | None = None):
    generator = LocalAdaptationSpaceGenerator()
    return generator.generate(
        local_analysis_result={
            "triggers": triggers or [],
            "target_entity": "uav-1",
            "local_uncertainty": {(1, 1): 0.9},
            "belief_gain": {(1, 1): 0.7},
            "drift_state": "high",
            "stale_regions": [(1, 1)],
            "recently_confirmed_empty_regions": [(2, 2)],
        },
        local_models={
            "local_uncertainty": {(1, 1): 0.9},
            "belief_gain": {(1, 1): 0.7},
            "drift_state": "high",
        },
        runtime_models={"uav_id": "uav-1"},
        timestamp=1.0,
    )


def _option_ids(space) -> set[str]:
    return {option.option_id for option in space.options}


def test_hold_current_path_option_exists() -> None:
    assert "local_path_hold_current_path" in _option_ids(_generate_local_space())


def test_search_option_generated_from_search_mode_required_trigger() -> None:
    space = _generate_local_space([_trigger("SEARCH_MODE_REQUIRED")])

    assert any("search" in option.option_id for option in space.options)


def test_drift_aware_movement_option_generated_under_drift_too_high() -> None:
    space = _generate_local_space([_trigger("DRIFT_TOO_HIGH")])

    assert "local_movement_drift_aware_movement" in _option_ids(space)


def test_delayed_adaptation_exists_under_instability_trigger() -> None:
    space = _generate_local_space(
        [_trigger("LOCAL_INSTABILITY", "instability and oscillation detected")]
    )

    assert "local_stability_delayed_adaptation" in _option_ids(space)


def test_uncertainty_driven_sensing_options_exist() -> None:
    space = _generate_local_space()

    assert "local_sensing_focus_sensing_on_uncertainty" in _option_ids(space)
