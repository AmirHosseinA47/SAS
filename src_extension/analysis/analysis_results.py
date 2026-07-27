"""Analysis result containers (local/global snapshot; no planning/execution)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

from .trigger_objects import Severity, StructuredTrigger, TriggerBatch, trigger_batch_from_structured, trigger_to_dict


@dataclass(frozen=True)
class LocalAnalysisResult:
    """Per-UAV structured output of local analysis."""

    uav_id: str
    timestamp: float
    local_trigger_list: tuple[StructuredTrigger, ...]
    local_risk_summary: str
    path_quality_summary: str
    uncertainty_summary: str
    information_summary: str
    escalation_flags: tuple[str, ...]
    explanation_context: str

    @property
    def trigger_batch(self) -> TriggerBatch:
        return trigger_batch_from_structured(
            self.local_trigger_list,
            source=f"local_analysis:{self.uav_id}",
            timestamp=self.timestamp,
        )

    @property
    def triggers(self) -> TriggerBatch:
        return self.trigger_batch

    def to_dict(self) -> dict[str, Any]:
        return {
            "uav_id": self.uav_id,
            "timestamp": self.timestamp,
            "local_trigger_list": [trigger_to_dict(t) for t in self.local_trigger_list],
            "local_risk_summary": self.local_risk_summary,
            "path_quality_summary": self.path_quality_summary,
            "uncertainty_summary": self.uncertainty_summary,
            "information_summary": self.information_summary,
            "escalation_flags": list(self.escalation_flags),
            "explanation_context": self.explanation_context,
        }


@dataclass(frozen=True)
class GlobalAnalysisResult:
    """Fleet-wide structured output of global analysis."""

    timestamp: float
    trigger_list: tuple[StructuredTrigger, ...]
    system_health_summary: str
    risk_flags: tuple[str, ...]
    priority_updates: tuple[str, ...]
    fail_safe_flags: tuple[str, ...]
    uncertainty_summary: str
    information_summary: str
    trend_summary: str
    explanation_context: str

    @property
    def trigger_batch(self) -> TriggerBatch:
        return trigger_batch_from_structured(
            self.trigger_list,
            source="global_analysis",
            timestamp=self.timestamp,
        )

    @property
    def triggers(self) -> TriggerBatch:
        return self.trigger_batch

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "trigger_list": [trigger_to_dict(t) for t in self.trigger_list],
            "system_health_summary": self.system_health_summary,
            "risk_flags": list(self.risk_flags),
            "priority_updates": list(self.priority_updates),
            "fail_safe_flags": list(self.fail_safe_flags),
            "uncertainty_summary": self.uncertainty_summary,
            "information_summary": self.information_summary,
            "trend_summary": self.trend_summary,
            "explanation_context": self.explanation_context,
        }


@dataclass(frozen=True)
class AnalysisSnapshot:
    """Combined view of local and global analysis for one cycle."""

    timestamp: float
    local_results: tuple[LocalAnalysisResult, ...]
    global_result: GlobalAnalysisResult
    all_triggers: tuple[StructuredTrigger, ...]
    dashboard_summary: str

    @property
    def trigger_batch(self) -> TriggerBatch:
        return trigger_batch_from_structured(
            self.all_triggers,
            source="analysis_snapshot",
            timestamp=self.timestamp,
        )

    @property
    def triggers(self) -> TriggerBatch:
        return self.trigger_batch

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "local_results": [r.to_dict() for r in self.local_results],
            "global_result": self.global_result.to_dict(),
            "all_triggers": [trigger_to_dict(t) for t in self.all_triggers],
            "dashboard_summary": self.dashboard_summary,
        }


def collect_all_triggers(
    local_results: Sequence[LocalAnalysisResult],
    global_result: GlobalAnalysisResult,
) -> list[dict[str, Any]]:
    """Flatten structured triggers from local and global results using ``trigger_to_dict``."""

    out: list[dict[str, Any]] = []
    for lr in local_results:
        out.extend(trigger_to_dict(t) for t in lr.local_trigger_list)
    out.extend(trigger_to_dict(t) for t in global_result.trigger_list)
    return out


def build_dashboard_summary(
    local_results: Sequence[LocalAnalysisResult],
    global_result: GlobalAnalysisResult,
    all_triggers: Sequence[StructuredTrigger],
) -> str:
    """Build a single dashboard-oriented text block (counts, categories, trigger explanations)."""

    def _fmt_counter(c: Counter[str]) -> str:
        if not c:
            return "(none)"
        return ", ".join(f"{k}={v}" for k, v in sorted(c.items()))

    total = len(all_triggers)
    by_severity = Counter(t.severity.value for t in all_triggers)
    by_category = Counter(type(t).__name__ for t in all_triggers)
    critical_lines = [
        f"  - [{t.trigger_type}] {t.explanation_context}"
        for t in all_triggers
        if t.severity == Severity.CRITICAL
    ]
    expl_lines = [f"  - [{t.trigger_type}] {t.explanation_context}" for t in all_triggers if t.explanation_context]

    local_lines: list[str] = []
    for lr in local_results:
        trig_ctx = "; ".join(
            t.explanation_context for t in lr.local_trigger_list if t.explanation_context
        )
        parts = [
            f"uav_id={lr.uav_id}",
            f"risk={lr.local_risk_summary!r}" if lr.local_risk_summary else "",
            f"path={lr.path_quality_summary!r}" if lr.path_quality_summary else "",
            f"uncertainty={lr.uncertainty_summary!r}" if lr.uncertainty_summary else "",
            f"information={lr.information_summary!r}" if lr.information_summary else "",
            f"ctx={lr.explanation_context!r}" if lr.explanation_context else "",
            f"trigger_ctx={trig_ctx!r}" if trig_ctx else "",
        ]
        local_lines.append("  - " + "; ".join(p for p in parts if p))

    gh_parts = [
        f"system_health={global_result.system_health_summary!r}" if global_result.system_health_summary else "",
        f"uncertainty={global_result.uncertainty_summary!r}" if global_result.uncertainty_summary else "",
        f"information={global_result.information_summary!r}" if global_result.information_summary else "",
        f"trends={global_result.trend_summary!r}" if global_result.trend_summary else "",
        f"ctx={global_result.explanation_context!r}" if global_result.explanation_context else "",
    ]
    g_trig = "; ".join(
        t.explanation_context for t in global_result.trigger_list if t.explanation_context
    )
    if g_trig:
        gh_parts.append(f"trigger_ctx={g_trig!r}")
    global_health = "; ".join(p for p in gh_parts if p) or "(no global summary fields)"

    blocks = [
        f"total_trigger_count: {total}",
        f"trigger_count_by_severity: {_fmt_counter(by_severity)}",
        f"trigger_count_by_category: {_fmt_counter(by_category)}",
        "critical_triggers:",
        "\n".join(critical_lines) if critical_lines else "  (none)",
        "explanation_messages:",
        (
            "\n".join(expl_lines[:200]) + ("\n  ..." if len(expl_lines) > 200 else "")
            if expl_lines
            else "  (none)"
        ),
        "local_uav_status_summary:",
        "\n".join(local_lines) if local_lines else "  (none)",
        f"global_health_summary: {global_health}",
    ]
    text = "\n".join(blocks)
    if len(text) > 12000:
        return text[:12000] + "\n... (truncated)"
    return text
