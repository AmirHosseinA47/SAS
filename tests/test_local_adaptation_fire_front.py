"""Local adaptation: prefer fire-front cells over fire-center cells."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from src_extension.adaptation.local_adaptation_generator import LocalAdaptationSpaceGenerator


@dataclass
class _FakeBelief:
    fire_probability_map: dict[tuple[int, int], float]


@dataclass
class _FakeFireRuntimeModel:
    belief: _FakeBelief


def _fire_map_center_and_front() -> dict[tuple[int, int], float]:
    high = 0.9
    low = 0.1
    return {
        (5, 5): high,
        (6, 5): high,
        (4, 5): high,
        (5, 6): high,
        (5, 4): high,
        (10, 5): high,
        (11, 5): low,
        (10, 6): low,
        (10, 4): low,
    }


def test_center_cell_is_not_fire_front() -> None:
    fire_map = _fire_map_center_and_front()
    generator = LocalAdaptationSpaceGenerator()

    assert generator._is_fire_front_cell((5, 5), fire_map) is False
    assert generator._is_fire_front_cell((10, 5), fire_map) is True


def test_front_cells_preferred_over_center_cells() -> None:
    fire_map = _fire_map_center_and_front()
    generator = LocalAdaptationSpaceGenerator()

    front_cells, all_high_cells = generator._classify_fire_cells(fire_map)
    preferred = front_cells if front_cells else all_high_cells

    assert (5, 5) in all_high_cells
    assert (5, 5) not in front_cells
    assert (10, 5) in front_cells
    assert (5, 5) not in preferred
    assert (10, 5) in preferred


def test_fallback_to_all_high_when_no_front_cells() -> None:
    fire_map = {(2, 2): 0.9, (4, 4): 0.8}
    generator = LocalAdaptationSpaceGenerator()

    with patch.object(
        LocalAdaptationSpaceGenerator,
        "_is_fire_front_cell",
        return_value=False,
    ):
        front_cells, all_high_cells = generator._classify_fire_cells(fire_map)

    preferred = front_cells if front_cells else all_high_cells

    assert front_cells == []
    assert set(all_high_cells) == {(2, 2), (4, 4)}
    assert set(preferred) == {(2, 2), (4, 4)}


def test_generate_path_options_marks_fire_front_targets() -> None:
    generator = LocalAdaptationSpaceGenerator()
    fire_map = _fire_map_center_and_front()
    runtime_models = {
        "fire_runtime_model": _FakeFireRuntimeModel(
            belief=_FakeBelief(fire_probability_map=fire_map)
        ),
    }
    front_cells, _ = generator._classify_fire_cells(fire_map, runtime_models=runtime_models)
    options = generator._generate_path_options(
        local_analysis_result={"triggers": [], "target_entity": "uav-1"},
        local_models={},
        runtime_models=runtime_models,
        timestamp=1.0,
    )
    front_targets = {
        option.parameters["target_region"]
        for option in options
        if option.parameters.get("path_action") == "move_toward_fire_front"
    }

    assert front_targets, "expected at least one fire-front path option"
    assert (5, 5) not in front_targets
    assert (10, 5) in front_cells, "isolated front cell should be classified as front"
    for target in front_targets:
        assert generator._is_fire_front_cell(target, fire_map)
    assert all(
        option.parameters.get("fire_front_target") is True
        for option in options
        if option.parameters.get("path_action") == "move_toward_fire_front"
    )
