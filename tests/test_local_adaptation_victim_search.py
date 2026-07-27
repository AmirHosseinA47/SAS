"""Local adaptation: victim-searcher path options toward victims."""

from __future__ import annotations

from dataclasses import dataclass

from src_extension.adaptation.local_adaptation_generator import LocalAdaptationSpaceGenerator


@dataclass
class _FakeUAVResourceState:
    current_role: str


@dataclass
class _FakeUAVResourceModel:
    by_uav_id: dict[str, _FakeUAVResourceState]


@dataclass
class _FakeVictim:
    estimated_position: tuple[float, float]


@dataclass
class _FakeVictimRuntimeModel:
    victims: dict[str, _FakeVictim]


def _generate_path_options(
    *,
    uav_id: str = "uav-1",
    role: str = "victim_searcher",
    victims: dict[str, _FakeVictim] | None = None,
) -> list:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = {
        "uav_resource_model": _FakeUAVResourceModel(
            by_uav_id={uav_id: _FakeUAVResourceState(current_role=role)}
        ),
        "victim_runtime_model": _FakeVictimRuntimeModel(
            victims=victims
            or {
                "victim_0": _FakeVictim(estimated_position=(12.0, 8.0)),
            }
        ),
    }
    return generator._generate_path_options(
        local_analysis_result={"triggers": [], "target_entity": uav_id},
        local_models={},
        runtime_models=runtime_models,
        timestamp=1.0,
    )


def test_victim_searcher_gets_move_toward_victim_candidate_options() -> None:
    options = _generate_path_options()

    victim_options = [
        option
        for option in options
        if option.parameters.get("path_action") == "move_toward_victim_candidate"
    ]
    assert victim_options
    assert victim_options[0].parameters.get("victim_search") is True
    assert victim_options[0].parameters.get("task_support", 0) > 0


def test_non_victim_role_keeps_fire_path_options_without_victim_candidate() -> None:
    options = _generate_path_options(role="scout")

    assert any(option.option_id == "local_path_hold_current_path" for option in options)
    assert not any(
        option.parameters.get("path_action") == "move_toward_victim_candidate"
        for option in options
    )


def test_victim_directed_option_has_strong_task_support_flags() -> None:
    options = _generate_path_options()
    victim_option = next(
        option
        for option in options
        if option.parameters.get("path_action") == "move_toward_victim_candidate"
    )

    assert victim_option.parameters["task_support"] > 0
    assert victim_option.parameters["victim_search"] is True
    assert victim_option.parameters["role"] == "victim_searcher"
    assert victim_option.parameters["target_position"] == (12.0, 8.0)
