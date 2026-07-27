"""Managing system: operator-facing support (Step 12B dashboard state surface)."""

from __future__ import annotations

from .alert_manager import (
    AlertManager,
    AlertRecord,
    CRITICAL_ALERT_TYPES,
    INFO_ALERT_TYPES,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    WARNING_ALERT_TYPES,
)
from .contracts import (
    AlertRecord as AlertRecordContract,
    DashboardState,
    DecisionExplanation,
    MissionTimelineEvent,
)
from .dashboard_state_builder import DashboardStateBuilder, KNOWN_LIMITATIONS
from .comparison_parser import (
    build_tradeoff_pairs,
    find_selected_score,
    parse_comparison_summary,
)
from .dashboard_exporter import DashboardStateExporter
from .display_utils import display_wind_vector, normalize_display_wind_direction
from .live_dashboard_panel import DashboardPanel
from .explanation_types import (
    ExplanationBundle,
    OptionComparisonExplanation,
    TradeoffExplanation,
    UncertaintyExplanation,
)
from .explanation_engine import ExplanationEngine
from .operator_override import (
    OperatorOverride,
    OperatorOverrideCommand,
    OperatorOverrideInterface,
    OperatorOverrideRegistry,
)
from .timeline_builder import MissionTimelineBuilder

__all__ = [
    "AlertManager",
    "AlertRecord",
    "AlertRecordContract",
    "CRITICAL_ALERT_TYPES",
    "INFO_ALERT_TYPES",
    "WARNING_ALERT_TYPES",
    "DashboardState",
    "DashboardStateBuilder",
    "DecisionExplanation",
    "ExplanationEngine",
    "KNOWN_LIMITATIONS",
    "MissionTimelineBuilder",
    "MissionTimelineEvent",
    "OperatorOverride",
    "OperatorOverrideCommand",
    "OperatorOverrideInterface",
    "OperatorOverrideRegistry",
    "SEVERITY_CRITICAL",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "DashboardPanel",
    "DashboardStateExporter",
    "ExplanationBundle",
    "OptionComparisonExplanation",
    "TradeoffExplanation",
    "UncertaintyExplanation",
    "build_tradeoff_pairs",
    "display_wind_vector",
    "find_selected_score",
    "normalize_display_wind_direction",
    "parse_comparison_summary",
]
