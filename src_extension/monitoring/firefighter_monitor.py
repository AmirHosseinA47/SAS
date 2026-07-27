"""Firefighter monitoring: per-unit structured snapshots from firefighter runtime knowledge."""

from __future__ import annotations

from src_extension.knowledge.firefighter_model import FirefighterModel

from .monitoring_interfaces import Cell, FirefighterStatusSnapshot


class FirefighterMonitor:
    """Observe-only snapshot builder for firefighter units."""

    def __init__(self, firefighter_model: FirefighterModel) -> None:
        self.firefighter_model = firefighter_model

    def collect_snapshot(self, current_time: float) -> list[FirefighterStatusSnapshot]:
        ts = float(current_time)
        out: list[FirefighterStatusSnapshot] = []
        for uid, unit in self.firefighter_model.units.items():
            pos = unit.current_position
            if pos is not None and len(pos) >= 2:
                position: Cell = (int(round(pos[0])), int(round(pos[1])))
            else:
                position = (0, 0)

            eta_val = unit.eta
            eta_f = float(eta_val) if eta_val is not None else 0.0

            rs = unit.route_risk_score
            risk_f = float(rs) if rs is not None else 0.0

            fc = unit.route_feasibility_confidence
            feas_f = float(fc) if fc is not None else 0.0

            rs_status = unit.route_status or ""

            out.append(
                FirefighterStatusSnapshot(
                    timestamp=ts,
                    unit_id=str(uid),
                    position=position,
                    assignment=unit.current_assignment,
                    route_status=rs_status,
                    eta=eta_f,
                    risk_score=risk_f,
                    feasibility_confidence=feas_f,
                    source="firefighter_monitor",
                    confidence=max(0.0, min(1.0, feas_f if feas_f > 0 else 0.7)),
                )
            )
        return out
