"""Managing system: triggers from analysis to planning (scaffold).

Analysis outputs: TriggerSignal / TriggerBatch encode interpretation
results, what may need adaptation not operational commands and not
planner decisions. Planning consumes triggers to form decisions.

At this stage, we add structured trigger dataclasses (severity, scope, planner hints, etc.).

TODO: Add severity / deduplication keys if needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

_INFORMATION_CONFIDENCE_THRESHOLD = 0.6


@dataclass(frozen=True)
class TriggerSignal:
    """Single signal: analysis interpretation for planning (not an action)."""

    name: str
    source: str = "analysis"
    confidence: float = 1.0
    severity: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float | None = None

    @property
    def kind(self) -> str:
        return self.name

    @property
    def trigger_id(self) -> str:
        return self.name

    @property
    def trigger_type(self) -> str:
        return self.name

    @property
    def data(self) -> dict[str, Any]:
        return self.metadata


@dataclass(frozen=True)
class TriggerBatch:
    """Batch of triggers for one analysis cycle (planning input; not execution)."""

    triggers: tuple[TriggerSignal, ...] = ()
    source: str = "analysis"
    timestamp: float | None = None
    step_index: int = 0


class Severity(str, Enum):
    """Step 6 trigger severity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Scope(str, Enum):
    """Step 6 trigger scope."""

    LOCAL = "local"
    GLOBAL = "global"


@dataclass(frozen=True)
class StructuredTrigger:
    """Step 6 structured trigger: shared fields for all trigger categories."""

    trigger_type: str
    severity: Severity
    confidence: float
    scope: Scope
    affected_entities: tuple[str, ...]
    timestamp: float
    recommended_planner: str
    explanation_context: str


@dataclass(frozen=True)
class AdaptationTrigger(StructuredTrigger):
    """Adaptation-related Step 6 trigger."""

    pass


@dataclass(frozen=True)
class SafetyTrigger(StructuredTrigger):
    """Safety-related Step 6 trigger."""

    pass


@dataclass(frozen=True)
class ResourceTrigger(StructuredTrigger):
    """Resource-related Step 6 trigger."""

    pass


@dataclass(frozen=True)
class RescueTrigger(StructuredTrigger):
    """Rescue-related Step 6 trigger."""

    pass


@dataclass(frozen=True)
class CommunicationTrigger(StructuredTrigger):
    """Communication-related Step 6 trigger."""

    pass


@dataclass(frozen=True)
class UncertaintyTrigger(StructuredTrigger):
    """Uncertainty-related Step 6 trigger."""

    pass


@dataclass(frozen=True)
class InformationTrigger(StructuredTrigger):
    """Information-related Step 6 trigger."""

    pass


def trigger_to_dict(trigger: StructuredTrigger) -> dict[str, Any]:
    """Serialize a Step 6 structured trigger to a plain dict (JSON-friendly values)."""

    return {
        "trigger_type": trigger.trigger_type,
        "severity": trigger.severity.value,
        "confidence": trigger.confidence,
        "scope": trigger.scope.value,
        "affected_entities": list(trigger.affected_entities),
        "timestamp": trigger.timestamp,
        "recommended_planner": trigger.recommended_planner,
        "explanation_context": trigger.explanation_context,
    }


def _read_raw(source: object, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _severity_label(value: object | None) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    text = str(raw).strip()
    return text or None


def normalize_trigger_signal(
    raw: object,
    *,
    default_source: str = "analysis",
    default_timestamp: float | None = None,
) -> TriggerSignal | None:
    """Normalize one trigger-like object to ``TriggerSignal``."""
    if raw is None:
        return None
    if isinstance(raw, TriggerSignal):
        return raw
    if isinstance(raw, str):
        name = raw.strip()
        if not name:
            return None
        return TriggerSignal(
            name=name,
            source=default_source,
            confidence=1.0,
            timestamp=default_timestamp,
        )
    if isinstance(raw, StructuredTrigger):
        return TriggerSignal(
            name=str(raw.trigger_type),
            source=default_source,
            confidence=float(raw.confidence),
            severity=_severity_label(raw.severity),
            metadata={
                "scope": raw.scope.value,
                "affected_entities": list(raw.affected_entities),
                "recommended_planner": raw.recommended_planner,
                "explanation_context": raw.explanation_context,
                "structured_trigger_type": type(raw).__name__,
            },
            timestamp=float(raw.timestamp),
        )
    if isinstance(raw, dict):
        name = str(
            raw.get("trigger_type")
            or raw.get("name")
            or raw.get("kind")
            or raw.get("trigger_id")
            or raw.get("code")
            or ""
        ).strip()
        if not name:
            return None
        metadata = dict(raw.get("metadata") or raw.get("data") or {})
        for key in (
            "scope",
            "affected_entities",
            "recommended_planner",
            "explanation_context",
        ):
            if key in raw and key not in metadata:
                metadata[key] = raw[key]
        return TriggerSignal(
            name=name,
            source=str(raw.get("source") or default_source),
            confidence=_coerce_float(raw.get("confidence"), 1.0),
            severity=_severity_label(raw.get("severity")),
            metadata=metadata,
            timestamp=(
                _coerce_float(raw["timestamp"], 0.0)
                if raw.get("timestamp") is not None
                else default_timestamp
            ),
        )
    name = str(
        _read_raw(raw, "trigger_type", _read_raw(raw, "kind", _read_raw(raw, "name", "")))
    ).strip()
    if not name:
        return None
    metadata: dict[str, Any] = {}
    affected = _read_raw(raw, "affected_entities", None)
    if affected is not None:
        metadata["affected_entities"] = list(affected)
    explanation = _read_raw(raw, "explanation_context", None)
    if explanation is not None:
        metadata["explanation_context"] = explanation
    data = _read_raw(raw, "data", None)
    if isinstance(data, dict):
        metadata.update(data)
    return TriggerSignal(
        name=name,
        source=str(_read_raw(raw, "source", default_source) or default_source),
        confidence=_coerce_float(_read_raw(raw, "confidence", 1.0), 1.0),
        severity=_severity_label(_read_raw(raw, "severity", None)),
        metadata=metadata,
        timestamp=(
            _coerce_float(_read_raw(raw, "timestamp", None), 0.0)
            if _read_raw(raw, "timestamp", None) is not None
            else default_timestamp
        ),
    )


def normalize_triggers(
    raw: object | None,
    *,
    default_source: str = "analysis",
    default_timestamp: float | None = None,
    step_index: int = 0,
) -> TriggerBatch:
    """Normalize heterogeneous trigger inputs to a ``TriggerBatch``."""
    if raw is None:
        return TriggerBatch(
            triggers=(),
            source=default_source,
            timestamp=default_timestamp,
            step_index=step_index,
        )
    if isinstance(raw, TriggerBatch):
        return raw
    if isinstance(raw, TriggerSignal):
        return TriggerBatch(
            triggers=(raw,),
            source=raw.source,
            timestamp=raw.timestamp if raw.timestamp is not None else default_timestamp,
            step_index=step_index,
        )
    if isinstance(raw, StructuredTrigger):
        signal = normalize_trigger_signal(
            raw,
            default_source=default_source,
            default_timestamp=default_timestamp,
        )
        if signal is None:
            return TriggerBatch(
                triggers=(),
                source=default_source,
                timestamp=default_timestamp,
                step_index=step_index,
            )
        return TriggerBatch(
            triggers=(signal,),
            source=default_source,
            timestamp=signal.timestamp,
            step_index=step_index,
        )
    if isinstance(raw, str):
        signal = normalize_trigger_signal(
            raw,
            default_source=default_source,
            default_timestamp=default_timestamp,
        )
        triggers = (signal,) if signal is not None else ()
        return TriggerBatch(
            triggers=triggers,
            source=default_source,
            timestamp=default_timestamp,
            step_index=step_index,
        )
    if isinstance(raw, (list, tuple, set, frozenset)):
        signals: list[TriggerSignal] = []
        for item in raw:
            signal = normalize_trigger_signal(
                item,
                default_source=default_source,
                default_timestamp=default_timestamp,
            )
            if signal is not None:
                signals.append(signal)
        return TriggerBatch(
            triggers=tuple(signals),
            source=default_source,
            timestamp=default_timestamp,
            step_index=step_index,
        )
    nested_batch = _read_raw(raw, "trigger_batch", None)
    if nested_batch is not None:
        return normalize_triggers(
            nested_batch,
            default_source=str(_read_raw(raw, "source", default_source) or default_source),
            default_timestamp=_read_raw(raw, "timestamp", default_timestamp),
            step_index=int(_read_raw(raw, "step_index", step_index) or step_index),
        )
    for key in (
        "triggers",
        "all_triggers",
        "local_trigger_list",
        "trigger_list",
        "active_triggers",
    ):
        items = _read_raw(raw, key, None)
        if items is None:
            continue
        if isinstance(items, TriggerBatch):
            return items
        batch = normalize_triggers(
            items,
            default_source=str(_read_raw(raw, "source", default_source) or default_source),
            default_timestamp=_read_raw(raw, "timestamp", default_timestamp),
            step_index=int(_read_raw(raw, "step_index", step_index) or step_index),
        )
        if batch.triggers:
            return batch
        if items:
            return batch
    signal = normalize_trigger_signal(
        raw,
        default_source=default_source,
        default_timestamp=default_timestamp,
    )
    if signal is not None:
        return TriggerBatch(
            triggers=(signal,),
            source=signal.source,
            timestamp=signal.timestamp,
            step_index=step_index,
        )
    return TriggerBatch(
        triggers=(),
        source=default_source,
        timestamp=default_timestamp,
        step_index=step_index,
    )


def trigger_batch_from_structured(
    structured: Sequence[StructuredTrigger],
    *,
    source: str = "analysis",
    timestamp: float | None = None,
    step_index: int = 0,
) -> TriggerBatch:
    """Build a ``TriggerBatch`` from Step 6 structured triggers."""
    return normalize_triggers(
        tuple(structured),
        default_source=source,
        default_timestamp=timestamp,
        step_index=step_index,
    )


def trigger_signal_passes_information_confidence(signal: TriggerSignal) -> bool:
    """Return whether an information/search trigger meets the fail-safe confidence gate."""
    name = signal.name.strip().upper()
    if name not in {"INFORMATION_INSUFFICIENT", "SEARCH_MODE_REQUIRED"}:
        return True
    return float(signal.confidence) >= _INFORMATION_CONFIDENCE_THRESHOLD
