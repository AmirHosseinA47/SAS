"""Adaptation option objects for Planning."""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


Scope = Enum(
    "Scope",
    {
        "local": "local",
        "global": "global",
        "rescue": "rescue",
        "system": "system",
    },
    type=str,
)


@dataclass
class AdaptationOption:
    option_id: str
    option_type: str
    target_entity: str
    parameters: dict[str, Any]
    expected_effect: str
    cost_estimate: float
    risk_estimate: float
    confidence: float
    scope: Scope
    timestamp: float
    originating_trigger: str
    explanation_hint: str


@dataclass
class MissionAdaptationOption(AdaptationOption):
    pass


@dataclass
class LocalAdaptationOption(AdaptationOption):
    pass


@dataclass
class RescueAdaptationOption(AdaptationOption):
    pass


@dataclass
class FailSafeAdaptationOption(AdaptationOption):
    pass


def adaptation_option_to_dict(option: AdaptationOption) -> dict[str, Any]:
    data = asdict(option)
    data["scope"] = option.scope.value
    return data
