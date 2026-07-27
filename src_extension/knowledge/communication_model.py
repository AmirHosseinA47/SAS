"""Managing system: Communication runtime knowledge.

TODO: Ingest comm observations; compute message_staleness and
delivery_confidence with decay; model relay and failed paths without
business policy here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .knowledge_utils import clamp01, compute_age, validate_metadata
from .runtime_model_common import Confidence, KnowledgeProvenance, Timestamp


@dataclass
class CommunicationRuntimeState:
    """Aggregate communication-knowledge fields (Step 4)."""

    link_quality_summary: dict[str, Any] = field(default_factory=dict)
    critical_message_queue: list[dict[str, Any]] = field(default_factory=list)
    ack_status: dict[str, Any] = field(default_factory=dict)
    last_delivery_status: dict[str, Any] = field(default_factory=dict)
    delayed_messages: list[dict[str, Any]] = field(default_factory=list)
    failed_messages: list[dict[str, Any]] = field(default_factory=list)
    relay_needed_flag: bool = False
    communication_mode: str | None = None
    delivery_confidence: Confidence | None = None
    critical_link_reliability: Confidence | None = None
    message_staleness: dict[str, float] = field(default_factory=dict)
    shared_knowledge_sync_quality: Confidence | None = None


@dataclass
class CommunicationModel:
    """Runtime knowledge: communication **quality and queues** (not execution).

    This tracks communication outcomes and quality indicators as adaptation-layer
    knowledge. It does not perform transport/protocol behavior.
    """

    step_index: int = 0
    provenance: KnowledgeProvenance = field(default_factory=KnowledgeProvenance)
    state: CommunicationRuntimeState = field(default_factory=CommunicationRuntimeState)
    links: dict[str, dict[str, Any]] = field(default_factory=dict)
    _communication_command_log: list[dict[str, Any]] = field(default_factory=list)

    @property
    def communication_mode(self) -> str:
        mode = self.state.communication_mode
        return str(mode) if mode else "normal"

    @communication_mode.setter
    def communication_mode(self, value: str) -> None:
        self.state.communication_mode = str(value)

    @property
    def relay_needed(self) -> bool:
        return bool(self.state.relay_needed_flag)

    @relay_needed.setter
    def relay_needed(self, value: bool) -> None:
        self.state.relay_needed_flag = bool(value)

    def runtime_context(self) -> dict[str, Any]:
        """Live communication context for adaptation/planning."""
        snap = self.snapshot()
        state = snap.get("state") if isinstance(snap.get("state"), dict) else {}
        delayed = len(state.get("delayed_messages") or [])
        failed = len(state.get("failed_messages") or [])
        sent = len(state.get("last_delivery_status") or {})
        delivery_confidence = state.get("delivery_confidence")
        return {
            **snap,
            "communication_mode": self.communication_mode,
            "delivery_confidence": delivery_confidence,
            "message_load": int(delayed + failed + sent),
            "relay_needed": self.relay_needed,
            "link_degraded": (
                delivery_confidence is not None and float(delivery_confidence) < 0.5
            ),
            "sync_quality": state.get("shared_knowledge_sync_quality"),
            "command_log_size": len(self._communication_command_log),
        }

    def set_communication_mode(
        self,
        mode: str,
        *,
        timestamp: Timestamp = 0.0,
        source: str = "communication_executor",
        reason: str = "",
        confidence: float = 0.85,
    ) -> None:
        """Apply a live communication mode and record it in the command log."""
        normalized = str(mode or "normal").strip().lower()
        ts, conf, src = validate_metadata(
            timestamp=timestamp, confidence=confidence, source=source
        )
        previous = self.communication_mode
        self.communication_mode = normalized
        self._communication_command_log.append(
            {
                "timestamp": ts,
                "source": src,
                "previous_mode": previous,
                "communication_mode": normalized,
                "reason": reason,
                "confidence": conf,
            }
        )
        self.provenance.timestamp = ts
        self.provenance.source = src
        self.provenance.confidence = conf

    def record_sent(
        self,
        message_id: str,
        *,
        target_entity: str = "",
        timestamp: Timestamp = 0.0,
        action: str = "",
        **_: Any,
    ) -> None:
        self.update_message_result(
            str(message_id),
            "delivered",
            float(timestamp),
            critical="rescue" in action.lower() or "critical" in action.lower(),
            source="communication_executor",
            confidence=0.85,
        )

    def record_failure(
        self,
        message_id: str,
        *,
        target_entity: str = "",
        timestamp: Timestamp = 0.0,
        action: str = "",
        **_: Any,
    ) -> None:
        self.update_message_result(
            str(message_id),
            "failed",
            float(timestamp),
            critical="rescue" in action.lower() or "critical" in action.lower(),
            source="communication_executor",
            confidence=0.75,
        )

    def record_delayed(
        self,
        message_id: str,
        *,
        target_entity: str = "",
        timestamp: Timestamp = 0.0,
        action: str = "",
        **_: Any,
    ) -> None:
        self.update_message_result(
            str(message_id),
            "delayed",
            float(timestamp),
            critical="rescue" in action.lower() or "critical" in action.lower(),
            source="communication_executor",
            confidence=0.75,
        )

    add_sent_result = record_sent
    add_failed_result = record_failure
    add_delayed_result = record_delayed
    mark_sent = record_sent
    mark_failed = record_failure
    mark_delayed = record_delayed

    def update(self, step_index: int) -> None:
        """TODO: Refresh ``state`` and optional per-link ``links`` from observations."""
        self.step_index = step_index

    def update_message_result(
        self,
        message_id: str,
        delivery_status: str,
        timestamp: Timestamp,
        critical: bool = False,
        source: str = "communication_runtime",
        confidence: float = 0.8,
    ) -> None:
        """Record one message delivery outcome in knowledge state."""
        ts, conf, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        s = self.state
        status = delivery_status.lower().strip()
        s.last_delivery_status[message_id] = status
        s.message_staleness[message_id] = 0.0
        if status in {"delivered", "acked"}:
            s.ack_status[message_id] = True
            s.failed_messages = [m for m in s.failed_messages if m.get("message_id") != message_id]
            s.delayed_messages = [m for m in s.delayed_messages if m.get("message_id") != message_id]
        elif status in {"delayed", "pending"}:
            s.ack_status[message_id] = False
            s.delayed_messages.append(
                {"message_id": message_id, "timestamp": float(timestamp), "critical": critical}
            )
        else:
            s.ack_status[message_id] = False
            s.failed_messages.append(
                {"message_id": message_id, "timestamp": float(timestamp), "critical": critical}
            )
            if critical:
                s.relay_needed_flag = True

        if critical:
            s.critical_message_queue.append(
                {"message_id": message_id, "timestamp": float(timestamp), "status": status}
            )
        s.delivery_confidence = self._compute_delivery_confidence()
        s.critical_link_reliability = self._compute_critical_reliability()
        s.shared_knowledge_sync_quality = self.compute_shared_sync_quality()
        self.provenance.timestamp = ts
        sync_conf = s.shared_knowledge_sync_quality if s.shared_knowledge_sync_quality is not None else 0.0
        self.provenance.confidence = clamp01((sync_conf + conf) / 2.0)
        self.provenance.source = src

    def mark_relay_needed(
        self,
        flag: bool = True,
        timestamp: Timestamp = 0.0,
        source: str = "communication_runtime",
        confidence: float = 0.7,
    ) -> None:
        """Set/clear relay-needed indicator based on runtime communication state."""
        ts, conf, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        self.state.relay_needed_flag = bool(flag)
        self.provenance.timestamp = ts
        self.provenance.source = src
        self.provenance.confidence = conf

    def compute_shared_sync_quality(self) -> Confidence:
        """Compute a simple sync-quality score from ack and delay/failure signals."""
        s = self.state
        total_msgs = max(1, len(s.last_delivery_status))
        acked = sum(1 for v in s.ack_status.values() if bool(v))
        delayed_penalty = 0.5 * len(s.delayed_messages)
        failed_penalty = 1.0 * len(s.failed_messages)
        raw = (acked - delayed_penalty - failed_penalty) / total_msgs
        score = max(0.0, min(1.0, raw))
        s.shared_knowledge_sync_quality = score
        return score

    def _compute_delivery_confidence(self) -> Confidence:
        s = self.state
        total_msgs = max(1, len(s.last_delivery_status))
        delivered = sum(
            1 for st in s.last_delivery_status.values() if st in {"delivered", "acked"}
        )
        return max(0.0, min(1.0, delivered / total_msgs))

    def _compute_critical_reliability(self) -> Confidence:
        s = self.state
        critical_count = max(1, len(s.critical_message_queue))
        critical_delivered = 0
        for msg in s.critical_message_queue:
            mid = str(msg.get("message_id", ""))
            if s.last_delivery_status.get(mid) in {"delivered", "acked"}:
                critical_delivered += 1
        return max(0.0, min(1.0, critical_delivered / critical_count))

    def apply_time_decay(self, current_time: float) -> None:
        """Increase message staleness and decay delivery confidence over time."""
        s = self.state
        now = float(current_time)
        latest_ts = self.provenance.timestamp if self.provenance.timestamp is not None else now
        age = compute_age(now, latest_ts)
        for message_id in list(s.message_staleness.keys()):
            s.message_staleness[message_id] = s.message_staleness.get(message_id, 0.0) + age
        if age > 0.0:
            if s.delivery_confidence is not None:
                s.delivery_confidence = clamp01(s.delivery_confidence * max(0.0, 1.0 - (0.03 * age)))
            if s.shared_knowledge_sync_quality is not None:
                s.shared_knowledge_sync_quality = clamp01(
                    s.shared_knowledge_sync_quality * max(0.0, 1.0 - (0.02 * age))
                )
            self.provenance.confidence = s.shared_knowledge_sync_quality
            self.provenance.timestamp = now

    def snapshot(self) -> dict[str, Any]:
        """Read-only knowledge snapshot (no side effects)."""
        return {
            "step_index": self.step_index,
            "provenance": asdict(self.provenance),
            "state": asdict(self.state),
            "links": {k: dict(v) for k, v in self.links.items()},
            "communication_mode": self.communication_mode,
            "command_log_size": len(self._communication_command_log),
            "recent_commands": list(self._communication_command_log[-5:]),
        }
