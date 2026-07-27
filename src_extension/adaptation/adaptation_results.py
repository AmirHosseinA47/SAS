"""Adaptation result containers."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from .adaptation_option_objects import AdaptationOption, adaptation_option_to_dict


@dataclass
class LocalAdaptationSpace:
    options: list[AdaptationOption] = field(default_factory=list)
    trigger_references: list[str] = field(default_factory=list)
    explanation_summaries: list[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "options": [adaptation_option_to_dict(option) for option in self.options],
            "trigger_references": self.trigger_references,
            "explanation_summaries": self.explanation_summaries,
            "timestamp": self.timestamp,
        }


@dataclass
class GlobalAdaptationSpace:
    options: list[AdaptationOption] = field(default_factory=list)
    trigger_references: list[str] = field(default_factory=list)
    explanation_summaries: list[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "options": [adaptation_option_to_dict(option) for option in self.options],
            "trigger_references": self.trigger_references,
            "explanation_summaries": self.explanation_summaries,
            "timestamp": self.timestamp,
        }


@dataclass
class RescueAdaptationSpace:
    options: list[AdaptationOption] = field(default_factory=list)
    trigger_references: list[str] = field(default_factory=list)
    explanation_summaries: list[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "options": [adaptation_option_to_dict(option) for option in self.options],
            "trigger_references": self.trigger_references,
            "explanation_summaries": self.explanation_summaries,
            "timestamp": self.timestamp,
        }


@dataclass
class FailSafeAdaptationSpace:
    options: list[AdaptationOption] = field(default_factory=list)
    trigger_references: list[str] = field(default_factory=list)
    explanation_summaries: list[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "options": [adaptation_option_to_dict(option) for option in self.options],
            "trigger_references": self.trigger_references,
            "explanation_summaries": self.explanation_summaries,
            "timestamp": self.timestamp,
        }


@dataclass
class AdaptationSpaceSnapshot:
    local_spaces: list[LocalAdaptationSpace] = field(default_factory=list)
    global_space: Optional[GlobalAdaptationSpace] = None
    rescue_space: Optional[RescueAdaptationSpace] = None
    fail_safe_space: Optional[FailSafeAdaptationSpace] = None
    all_options: list[AdaptationOption] = field(default_factory=list)
    dashboard_summary: str = ""
    trigger_references: list[str] = field(default_factory=list)
    explanation_summaries: list[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_spaces": [space.to_dict() for space in self.local_spaces],
            "global_space": self.global_space.to_dict() if self.global_space else None,
            "rescue_space": self.rescue_space.to_dict() if self.rescue_space else None,
            "fail_safe_space": (
                self.fail_safe_space.to_dict() if self.fail_safe_space else None
            ),
            "all_options": [
                adaptation_option_to_dict(option) for option in self.all_options
            ],
            "dashboard_summary": self.dashboard_summary,
            "trigger_references": self.trigger_references,
            "explanation_summaries": self.explanation_summaries,
            "timestamp": self.timestamp,
        }


def collect_all_options(
    local_spaces: Optional[list[LocalAdaptationSpace]] = None,
    global_space: Optional[GlobalAdaptationSpace] = None,
    rescue_space: Optional[RescueAdaptationSpace] = None,
    fail_safe_space: Optional[FailSafeAdaptationSpace] = None,
) -> list[AdaptationOption]:
    options: list[AdaptationOption] = []

    for space in local_spaces or []:
        options.extend(space.options)

    for space in (global_space, rescue_space, fail_safe_space):
        if space:
            options.extend(space.options)

    return options


def build_adaptation_dashboard_summary(
    options: list[AdaptationOption],
    trigger_references: Optional[list[str]] = None,
    rejected_count: int = 0,
) -> str:
    by_category = Counter(option.option_type for option in options)
    by_scope = Counter(option.scope.value for option in options)
    fail_safe_count = sum(1 for option in options if "failsafe" in option.option_type)
    search_mode_count = sum(
        1
        for option in options
        if "search" in option.option_id
        or "search" in str(option.parameters).lower()
        or "search" in option.expected_effect.lower()
    )
    stability_options = [
        option.option_id
        for option in options
        if option.option_type == "stability_control"
    ]
    explanation_hints = [
        f"  - [{option.option_id}] {option.explanation_hint}"
        for option in options
        if option.explanation_hint
    ]
    originating_triggers = Counter(option.originating_trigger for option in options)

    def fmt_counter(counter: Counter[str]) -> str:
        if not counter:
            return "(none)"
        return ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))

    return "\n".join(
        [
            f"total_option_count: {len(options)}",
            f"option_count_by_category: {fmt_counter(by_category)}",
            f"option_count_by_scope: {fmt_counter(by_scope)}",
            f"fail_safe_option_count: {fail_safe_count}",
            f"search_mode_option_count: {search_mode_count}",
            f"rejected_option_count: {rejected_count}",
            "stability_options:",
            "\n".join(f"  - {option_id}" for option_id in stability_options)
            if stability_options
            else "  (none)",
            "originating_trigger_summaries:",
            fmt_counter(originating_triggers),
            "trigger_references:",
            ", ".join(trigger_references or []) if trigger_references else "(none)",
            "explanation_hints:",
            "\n".join(explanation_hints[:200])
            + ("\n  ..." if len(explanation_hints) > 200 else "")
            if explanation_hints
            else "  (none)",
        ]
    )
