"""JSON-serializable dashboard and explanation data contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if hasattr(value, "value"):  # Enum-like
        return str(getattr(value, "value", value))
    return str(value)


@dataclass
class DecisionExplanation:
    explanation_id: str
    step: int
    source_module: str
    decision_type: str
    target_id: str
    selected_action: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    alternatives_considered: list[dict[str, Any]] = field(default_factory=list)
    key_factors: list[str] = field(default_factory=list)
    expected_effect: str = ""
    actual_outcome: str = ""
    chosen_option: str = ""
    tradeoffs: list[dict[str, Any]] = field(default_factory=list)
    confidence: float | None = None
    uncertainty: dict[str, Any] = field(default_factory=dict)
    before_after: dict[str, Any] = field(default_factory=dict)
    source_data_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass
class AlertRecord:
    alert_id: str
    step: int
    severity: str
    alert_type: str
    target_id: str
    message: str
    source_module: str
    resolved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass
class MissionTimelineEvent:
    step: int
    event_type: str
    entity_id: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_module: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass
class DashboardState:
    step: int
    mission_status: dict[str, Any]
    uav_status_view: list[dict[str, Any]]
    victim_view: list[dict[str, Any]]
    firefighter_view: list[dict[str, Any]]
    fire_view: dict[str, Any]
    rescue_view: dict[str, Any]
    communication_view: dict[str, Any]
    fail_safe_view: dict[str, Any]
    alert_list: list[dict[str, Any]]
    explanation_list: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    known_limitations: list[str]
    recent_alert_count: int = 0
    critical_alert_count: int = 0
    warning_alert_count: int = 0
    info_alert_count: int = 0
    unresolved_alert_count: int = 0
    structured_explanations: list[dict[str, Any]] = field(default_factory=list)
    option_comparison_count: int = 0
    explanation_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))
