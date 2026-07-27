"""Shared trigger normalization for adaptation generators."""

from __future__ import annotations

from typing import Any

from ..analysis.trigger_objects import (
    TriggerBatch,
    TriggerSignal,
    normalize_triggers,
    trigger_signal_passes_information_confidence,
)

_INFORMATION_TRIGGER_NAMES = frozenset({"SEARCH_MODE_REQUIRED", "INFORMATION_INSUFFICIENT"})


def adaptation_trigger_batch(
    source: object | None,
    *,
    default_label: str = "analysis",
) -> TriggerBatch:
    """Normalize adaptation inputs; prefers ``trigger_batch``, falls back to legacy keys."""
    if isinstance(source, (list, tuple, set, frozenset)) and not isinstance(source, (str, bytes)):
        return normalize_triggers(source, default_source=default_label)
    batch = normalize_triggers(source, default_source=default_label)
    if batch.triggers:
        return batch
    if isinstance(source, (list, tuple, set, frozenset)):
        return normalize_triggers(source, default_source=default_label)
    return batch


def filter_adaptation_trigger_signals(
    signals: tuple[TriggerSignal, ...] | list[TriggerSignal],
    *,
    apply_information_confidence: bool = True,
) -> tuple[TriggerSignal, ...]:
    if not apply_information_confidence:
        return tuple(signals)
    return tuple(
        signal
        for signal in signals
        if signal.name.strip().upper() not in _INFORMATION_TRIGGER_NAMES
        or trigger_signal_passes_information_confidence(signal)
    )


def adaptation_trigger_metadata(
    source: object | None,
    *,
    default_label: str = "analysis",
    apply_information_confidence: bool = True,
) -> tuple[str, str, float, tuple[TriggerSignal, ...]]:
    """Return ``(originating_trigger, trigger_context_text, confidence, signals)``."""
    batch = adaptation_trigger_batch(source, default_label=default_label)
    signals = filter_adaptation_trigger_signals(
        batch.triggers,
        apply_information_confidence=apply_information_confidence,
    )
    trigger_ids = [signal.name for signal in signals]
    context_parts: list[str] = list(trigger_ids)
    for signal in signals:
        explanation = signal.metadata.get("explanation_context")
        if explanation:
            context_parts.append(str(explanation))
        elif signal.severity:
            context_parts.append(str(signal.severity))
        else:
            context_parts.append(signal.name)
    confidences = [
        signal.confidence for signal in signals if isinstance(signal.confidence, (int, float))
    ]
    confidence = sum(confidences) / len(confidences) if confidences else 0.5
    originating_trigger = ",".join(trigger_ids) if trigger_ids else default_label
    trigger_context_text = " ".join(context_parts)
    return originating_trigger, trigger_context_text, confidence, signals
