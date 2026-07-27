"""Typed monitoring artifacts (Step 5): local observations and global snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

Cell = Tuple[int, int]


@dataclass
class LocalObservation:
    uav_id: str
    timestamp: float
    visible_fire_cells: List[Cell]
    visible_smoke_cells: List[Cell]
    visible_victim_candidates: List[Any]
    current_position: Cell
    intended_move: Cell
    actual_move: Cell
    drift_error: float
    battery_level: float
    battery_status: str
    communication_status: str
    nearby_uavs: List[str]
    task_context: Dict[str, Any]

    negative_observations: List[Tuple[Cell, float, float]]
    raw_information_gain: float
    normalized_information_gain: float
    local_uncertainty_patch: List[Cell]
    observation_confidence: float

    belief_confirmation_flags: List[Cell]
    source: str = "local_monitor"
    confidence: float = 1.0


@dataclass
class GlobalObservationSnapshot:
    timestamp: float
    mission_time: float
    fire_summary: Dict[str, Any]
    fire_belief_summary: Dict[str, Any]
    visibility_summary: Dict[str, Any]
    uav_team_summary: Dict[str, Any]
    victim_summary: Dict[str, Any]
    firefighter_summary: Dict[str, Any]
    communication_summary: Dict[str, Any]

    uncertainty_summary: Dict[str, Any]
    information_sufficiency: str
    belief_gap_indicators: Dict[str, Any]

    event_flags: Dict[str, Any]

    # Environmental wind (spread direction fire/smoke travels toward on the grid).
    wind_direction: str = ""
    wind_vector: Tuple[float, float] = (0.0, 1.0)
    wind_source: str = ""
    wind_timestamp: float = 0.0
    observation_step: int = 0

    source: str = "global_monitor"
    confidence: float = 1.0


@dataclass
class CommunicationStatusSnapshot:
    timestamp: float
    sent: int
    acknowledged: int
    delayed: int
    failed: int
    relay_needed: bool
    delivery_confidence: float
    source: str = "communication_monitor"
    confidence: float = 1.0


@dataclass
class FirefighterStatusSnapshot:
    timestamp: float
    unit_id: str
    position: Cell
    assignment: Any
    route_status: str
    eta: float
    risk_score: float
    feasibility_confidence: float
    source: str = "firefighter_monitor"
    confidence: float = 1.0
