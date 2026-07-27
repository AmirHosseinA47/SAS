"""Managing system: Victim runtime knowledge (beliefs / fused status).

Structured belief about each victim: uncertain position, detection history,
confirmation and lost-contact flags, and rescue coordination fields.
Operational victim entities stay on the managed side; this module is
time-aware and confidence-aware knowledge only.

TODO: Merge observations with explicit **decay** of stale tracks and
**negative-information** handling when wiring fusion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .knowledge_utils import clamp01, compute_age, validate_metadata
from .runtime_model_common import Confidence, KnowledgeProvenance, Timestamp


@dataclass
class VictimBeliefRecord:
    """Per-victim runtime knowledge placeholders (Step 4)."""

    victim_id: str
    estimated_position: tuple[float, float] | None = None
    position_uncertainty_radius: float | None = None
    confidence_score: Confidence | None = None
    detection_confidence_history: list[Confidence] = field(default_factory=list)
    detection_history: list[dict[str, Any]] = field(default_factory=list)
    last_seen_time: Timestamp | None = None
    last_confirmation_time: Timestamp | None = None
    status: str | None = None
    priority: float | None = None
    confirmation_required_flag: bool = False
    lost_contact_flag: bool = False
    reachability_estimate: float | None = None
    assigned_firefighter_unit: str | None = None
    supporting_uav: str | None = None
    rescue_state: str | None = None
    provenance: KnowledgeProvenance = field(default_factory=KnowledgeProvenance)


@dataclass
class VictimRuntimeModel:
    """Runtime knowledge catalog: victim-related **beliefs** (not managed truth)."""

    step_index: int = 0
    catalog_provenance: KnowledgeProvenance = field(default_factory=KnowledgeProvenance)
    victims: dict[str, VictimBeliefRecord] = field(default_factory=dict)

    def update(self, step_index: int) -> None:
        """TODO: Merge observation updates; decay stale beliefs; refresh provenance."""
        self.step_index = step_index

    @staticmethod
    def _clamp01(value: float) -> float:
        return clamp01(value)

    def _get_or_create(self, victim_id: str) -> VictimBeliefRecord:
        record = self.victims.get(victim_id)
        if record is None:
            record = VictimBeliefRecord(victim_id=victim_id)
            self.victims[victim_id] = record
        return record

    def update_detection(
        self,
        victim_id: str,
        position: tuple[float, float],
        timestamp: Timestamp,
        source: str,
        confidence: float,
    ) -> None:
        """Update victim/candidate belief from a single detection event."""
        ts, conf, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        record = self._get_or_create(victim_id)
        record.estimated_position = position
        record.confidence_score = conf
        record.detection_confidence_history.append(conf)
        record.detection_history.append(
            {
                "timestamp": ts,
                "source": src,
                "position": position,
                "confidence": conf,
            }
        )
        if record.position_uncertainty_radius is None:
            record.position_uncertainty_radius = max(0.0, 1.0 - conf)
        else:
            record.position_uncertainty_radius = max(
                0.0,
                min(record.position_uncertainty_radius, 1.0 - conf),
            )
        record.last_seen_time = ts
        record.status = "candidate" if conf < 0.7 else "detected"
        record.lost_contact_flag = False
        record.provenance.timestamp = ts
        record.provenance.confidence = conf
        record.provenance.source = src

    def confirm_victim(
        self,
        victim_id: str,
        timestamp: Timestamp,
        source: str,
        confidence: float = 1.0,
    ) -> None:
        """Mark a victim record as confirmed by reliable evidence."""
        ts, conf, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        record = self._get_or_create(victim_id)
        record.last_confirmation_time = ts
        record.status = "confirmed"
        record.confirmation_required_flag = False
        record.lost_contact_flag = False
        record.confidence_score = max(record.confidence_score or 0.0, conf)
        record.provenance.timestamp = ts
        record.provenance.source = src
        record.provenance.confidence = record.confidence_score

    def mark_lost_contact(
        self,
        victim_id: str,
        timestamp: Timestamp,
        source: str = "tracking_system",
        confidence: float = 0.5,
    ) -> None:
        """Mark track as stale/lost without deleting prior evidence."""
        ts, conf, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        record = self._get_or_create(victim_id)
        record.lost_contact_flag = True
        record.status = "lost_contact"
        record.last_seen_time = ts
        record.provenance.timestamp = ts
        record.provenance.source = src
        record.provenance.confidence = min(record.confidence_score or conf, conf)

    def apply_time_decay(self, current_time: float) -> None:
        """Decay stale victim confidence and grow positional uncertainty."""
        now = float(current_time)
        for record in self.victims.values():
            if record.last_seen_time is None:
                continue
            age = compute_age(now, record.last_seen_time)
            if age <= 0.0:
                continue
            base_conf = record.confidence_score if record.confidence_score is not None else 0.5
            record.confidence_score = self._clamp01(base_conf * max(0.0, 1.0 - (0.03 * age)))
            base_radius = (
                record.position_uncertainty_radius
                if record.position_uncertainty_radius is not None
                else max(0.0, 1.0 - record.confidence_score)
            )
            record.position_uncertainty_radius = max(0.0, float(base_radius) + (0.25 * age))
            record.provenance.confidence = record.confidence_score

    def require_confirmation(self, victim_id: str) -> None:
        """Flag the record so downstream components request confirmation."""
        record = self._get_or_create(victim_id)
        record.confirmation_required_flag = True
        if record.status is None:
            record.status = "candidate"

    def snapshot(self) -> dict[str, Any]:
        """Read-only knowledge snapshot (no side effects)."""
        return {
            "step_index": self.step_index,
            "catalog_provenance": asdict(self.catalog_provenance),
            "victims": {vid: asdict(rec) for vid, rec in self.victims.items()},
        }
