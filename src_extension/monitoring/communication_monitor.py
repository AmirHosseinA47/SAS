"""Communication monitoring: structured snapshot from communication runtime knowledge."""

from __future__ import annotations

from typing import Any

from src_extension.knowledge.communication_model import CommunicationModel

from .monitoring_interfaces import CommunicationStatusSnapshot


class CommunicationMonitor:
    """Observe-only snapshot builder for communication model state."""

    def __init__(self, communication_model: CommunicationModel) -> None:
        self.communication_model = communication_model

    def collect_snapshot(self, current_time: float) -> CommunicationStatusSnapshot:
        ts = float(current_time)
        snap = self.communication_model.snapshot()
        state: dict[str, Any] = (snap.get("state") or {}) if isinstance(snap.get("state"), dict) else {}
        if not isinstance(state, dict):
            state = {}

        sent = len(state.get("last_delivery_status") or {})
        ack_map = state.get("ack_status") or {}
        acknowledged = sum(1 for v in ack_map.values() if v) if isinstance(ack_map, dict) else 0
        delayed = len(state.get("delayed_messages") or [])
        failed = len(state.get("failed_messages") or [])
        relay = bool(state.get("relay_needed_flag", False))
        dc = state.get("delivery_confidence")
        delivery_confidence = float(dc) if dc is not None else 0.0
        meta_conf = delivery_confidence if delivery_confidence > 0.0 else 0.75
        message_load = int(sent + delayed + failed)
        link_degraded = delivery_confidence < 0.5 or failed > 0

        return CommunicationStatusSnapshot(
            timestamp=ts,
            sent=sent,
            acknowledged=acknowledged,
            delayed=delayed,
            failed=failed,
            relay_needed=relay,
            delivery_confidence=delivery_confidence,
            source="communication_monitor",
            confidence=max(0.0, min(1.0, meta_conf)),
        )
