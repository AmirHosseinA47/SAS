"""Managing system: local UAV path-context runtime knowledge.

This container tracks local path-related context metrics as knowledge-layer
state. It does not implement path planning algorithms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .knowledge_utils import clamp01, compute_age, validate_metadata
from .runtime_model_common import Confidence, Timestamp

_DIRECTION_OPPOSITES: dict[int, int] = {0: 2, 2: 0, 1: 3, 3: 1}


@dataclass
class LocalPathContextModel:
    """Per-UAV local path context state (Step 4 knowledge-layer container)."""

    uav_id: str
    current_path_segment: list[tuple[float, float]] = field(default_factory=list)
    candidate_moves: list[tuple[float, float]] = field(default_factory=list)
    candidate_horizon_length: int = 1
    local_path_utility_estimates: dict[str, float] = field(default_factory=dict)
    local_collision_risk_estimates: dict[str, float] = field(default_factory=dict)
    local_smoke_penalty_estimates: dict[str, float] = field(default_factory=dict)
    local_drift_penalty_estimates: dict[str, float] = field(default_factory=dict)
    task_support_score: Confidence | None = None
    belief_gain_score: Confidence | None = None
    path_stability_score: Confidence | None = None
    timestamp: Timestamp | None = None
    current_target: tuple[float, float] | None = None
    current_action: str | None = None
    selected_direction: int | None = None
    last_positions: list[tuple[float, float]] = field(default_factory=list)
    movement_stability: Confidence | None = None
    stuck_count: int = 0
    oscillation_score: float = 0.0
    nearby_fire: float = 0.0
    nearby_smoke: float = 0.0
    local_risk_estimate: float = 0.0
    path_safety_score: float = 1.0
    target_switch_count: int = 0
    navigation_confidence: Confidence | None = None
    sector_alignment_score: Confidence | None = None
    boundary_pressure: float = 0.0
    congestion_pressure: float = 0.0
    wind_edge_streak: int = 0
    wind_hold_streak: int = 0
    wind_same_target_streak: int = 0
    wind_aware_hold_streak: int = 0
    corridor_targets: list[tuple[float, float]] = field(default_factory=list)
    corridor_index: int = 0
    recent_corridor_targets: list[tuple[float, float]] = field(default_factory=list)
    force_wind_retarget: bool = False
    force_wind_sweep: bool = False
    pocket_streak: int = 0
    coverage_priority: float = 0.0
    hazard_buffer_level: int = 0
    force_coverage_escape: bool = False
    post_rescue_coverage_steps_remaining: int = 0
    unresolved_victim_count: int = 0
    recent_x_positions: list[int] = field(default_factory=list)

    @staticmethod
    def compute_oscillation_score(
        last_positions: list[tuple[float, float]],
        last_directions: list[int],
    ) -> float:
        """Estimate path oscillation from recent positions and heading changes."""
        score = 0.0
        if len(last_directions) >= 3:
            reversals = 0
            for index in range(2, len(last_directions)):
                previous = last_directions[index - 2]
                current = last_directions[index]
                if current == _DIRECTION_OPPOSITES.get(previous, -1):
                    reversals += 1
            score = max(score, min(1.0, reversals / max(1, len(last_directions) - 2)))
        if len(last_positions) >= 3:
            ping_pong = 0
            for index in range(2, len(last_positions)):
                if (
                    last_positions[index] == last_positions[index - 2]
                    and last_positions[index] != last_positions[index - 1]
                ):
                    ping_pong += 1
            score = max(score, min(1.0, ping_pong / max(1, len(last_positions) - 2)))
        return clamp01(score)

    @staticmethod
    def compute_movement_stability(
        *,
        stuck_count: int,
        oscillation_score: float,
        drift_level: float,
    ) -> float:
        stability = 1.0
        stability -= min(0.45, max(0, int(stuck_count)) * 0.08)
        stability -= clamp01(oscillation_score) * 0.35
        stability -= clamp01(drift_level) * 0.25
        return clamp01(stability)

    @staticmethod
    def compute_local_risk_estimate(
        *,
        nearby_fire: float,
        nearby_smoke: float,
        congestion_pressure: float,
        boundary_pressure: float,
        drift_level: float,
    ) -> float:
        return clamp01(
            nearby_fire * 0.35
            + nearby_smoke * 0.25
            + congestion_pressure * 0.15
            + boundary_pressure * 0.1
            + drift_level * 0.15
        )

    @staticmethod
    def compute_sector_alignment_score(
        position: tuple[float, float] | None,
        sector_bounds: dict[str, int] | None,
    ) -> float:
        if position is None or not sector_bounds:
            return 0.5
        x, y = float(position[0]), float(position[1])
        inside = (
            sector_bounds.get("x_min", 0) <= x <= sector_bounds.get("x_max", 0)
            and sector_bounds.get("y_min", 0) <= y <= sector_bounds.get("y_max", 0)
        )
        return 0.9 if inside else 0.35

    def refresh_from_runtime(
        self,
        *,
        timestamp: Timestamp,
        position: tuple[float, float] | None = None,
        selected_direction: int | None = None,
        current_action: str | None = None,
        current_target: tuple[float, float] | None = None,
        last_positions: list[tuple[float, float]] | None = None,
        last_directions: list[int] | None = None,
        stuck_count: int = 0,
        target_switch_count: int = 0,
        nearby_fire: float = 0.0,
        nearby_smoke: float = 0.0,
        congestion_pressure: float = 0.0,
        boundary_pressure: float = 0.0,
        drift_level: float = 0.0,
        navigation_confidence: float | None = None,
        sector_alignment_score: float | None = None,
        local_plan_reliability: float | None = None,
        candidate_moves: list[tuple[float, float]] | None = None,
        wind_edge_streak: int | None = None,
        wind_hold_streak: int | None = None,
        wind_same_target_streak: int | None = None,
        wind_aware_hold_streak: int | None = None,
        corridor_targets: list[tuple[float, float]] | None = None,
        corridor_index: int | None = None,
        recent_corridor_targets: list[tuple[float, float]] | None = None,
        force_wind_retarget: bool | None = None,
        force_wind_sweep: bool | None = None,
        pocket_streak: int | None = None,
        coverage_priority: float | None = None,
        hazard_buffer_level: int | None = None,
        force_coverage_escape: bool | None = None,
        post_rescue_coverage_steps_remaining: int | None = None,
        unresolved_victim_count: int | None = None,
        recent_x_positions: list[int] | None = None,
        source: str = "wildfire_model",
        confidence: float = 0.85,
    ) -> None:
        """Refresh live path-context knowledge from runtime UAV execution state."""
        ts, conf, _ = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        positions = list(last_positions or self.last_positions)
        directions = list(last_directions or [])
        if position is not None:
            positions.append((float(position[0]), float(position[1])))
        positions = positions[-8:]
        oscillation = self.compute_oscillation_score(positions, directions)
        movement_stability = self.compute_movement_stability(
            stuck_count=int(stuck_count),
            oscillation_score=oscillation,
            drift_level=float(drift_level),
        )
        fire_pressure = clamp01(nearby_fire)
        smoke_pressure = clamp01(nearby_smoke)
        congestion = clamp01(congestion_pressure)
        boundary = clamp01(boundary_pressure)
        risk = self.compute_local_risk_estimate(
            nearby_fire=fire_pressure,
            nearby_smoke=smoke_pressure,
            congestion_pressure=congestion,
            boundary_pressure=boundary,
            drift_level=float(drift_level),
        )
        path_safety = clamp01(1.0 - risk)
        nav_conf = (
            clamp01(navigation_confidence)
            if navigation_confidence is not None
            else clamp01((movement_stability + path_safety) / 2.0)
        )
        sector_score = (
            clamp01(sector_alignment_score)
            if sector_alignment_score is not None
            else self.sector_alignment_score
        )
        if sector_score is None:
            sector_score = 0.5

        self.last_positions = positions
        self.selected_direction = (
            int(selected_direction) if selected_direction is not None else self.selected_direction
        )
        self.current_action = current_action if current_action is not None else self.current_action
        self.current_target = current_target if current_target is not None else self.current_target
        self.stuck_count = max(0, int(stuck_count))
        self.target_switch_count = max(0, int(target_switch_count))
        self.oscillation_score = oscillation
        self.movement_stability = movement_stability
        self.nearby_fire = fire_pressure
        self.nearby_smoke = smoke_pressure
        self.congestion_pressure = congestion
        self.boundary_pressure = boundary
        self.local_risk_estimate = risk
        self.path_safety_score = path_safety
        self.navigation_confidence = nav_conf
        self.sector_alignment_score = sector_score
        self.path_stability_score = movement_stability
        self.task_support_score = sector_score
        self.belief_gain_score = nav_conf
        if candidate_moves is not None:
            self.candidate_moves = list(candidate_moves)
        if wind_edge_streak is not None:
            self.wind_edge_streak = max(0, int(wind_edge_streak))
        if wind_hold_streak is not None:
            self.wind_hold_streak = max(0, int(wind_hold_streak))
        if wind_same_target_streak is not None:
            self.wind_same_target_streak = max(0, int(wind_same_target_streak))
        if wind_aware_hold_streak is not None:
            self.wind_aware_hold_streak = max(0, int(wind_aware_hold_streak))
        if corridor_targets is not None:
            self.corridor_targets = list(corridor_targets)
        if corridor_index is not None:
            self.corridor_index = max(0, int(corridor_index))
        if recent_corridor_targets is not None:
            self.recent_corridor_targets = list(recent_corridor_targets)
        if force_wind_retarget is not None:
            self.force_wind_retarget = bool(force_wind_retarget)
        if force_wind_sweep is not None:
            self.force_wind_sweep = bool(force_wind_sweep)
        if pocket_streak is not None:
            self.pocket_streak = max(0, int(pocket_streak))
        if coverage_priority is not None:
            self.coverage_priority = max(0.0, float(coverage_priority))
        if hazard_buffer_level is not None:
            self.hazard_buffer_level = max(0, int(hazard_buffer_level))
        if force_coverage_escape is not None:
            self.force_coverage_escape = bool(force_coverage_escape)
        if post_rescue_coverage_steps_remaining is not None:
            self.post_rescue_coverage_steps_remaining = max(
                0, int(post_rescue_coverage_steps_remaining)
            )
        if unresolved_victim_count is not None:
            self.unresolved_victim_count = max(0, int(unresolved_victim_count))
        if recent_x_positions is not None:
            self.recent_x_positions = [int(x) for x in recent_x_positions][-30:]
        if position is not None and self.current_target is not None:
            self.current_path_segment = [position, self.current_target]
        elif position is not None:
            self.current_path_segment = [position]

        reliability = (
            clamp01(local_plan_reliability)
            if local_plan_reliability is not None
            else nav_conf
        )
        self.local_collision_risk_estimates = {
            "congestion": congestion,
            "local_risk": risk,
        }
        self.local_smoke_penalty_estimates = {"nearby_smoke": smoke_pressure}
        self.local_drift_penalty_estimates = {"drift_level": clamp01(drift_level)}
        self.local_path_utility_estimates = {
            "path_safety": path_safety,
            "navigation_confidence": nav_conf,
            "movement_stability": movement_stability,
            "sector_alignment": sector_score,
            "reliability": reliability,
        }
        self.timestamp = ts
        if self.path_stability_score is None:
            self.path_stability_score = conf

    def update_context(
        self,
        *,
        timestamp: Timestamp,
        current_path_segment: list[tuple[float, float]] | None = None,
        candidate_moves: list[tuple[float, float]] | None = None,
        candidate_horizon_length: int | None = None,
        local_path_utility_estimates: dict[str, float] | None = None,
        local_collision_risk_estimates: dict[str, float] | None = None,
        local_smoke_penalty_estimates: dict[str, float] | None = None,
        local_drift_penalty_estimates: dict[str, float] | None = None,
        task_support_score: Confidence | None = None,
        belief_gain_score: Confidence | None = None,
        path_stability_score: Confidence | None = None,
        source: str = "local_path_context",
        confidence: float = 0.8,
    ) -> None:
        """Update path-context knowledge from local scoring context."""
        ts, conf, _ = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        if current_path_segment is not None:
            self.current_path_segment = list(current_path_segment)
        if candidate_moves is not None:
            self.candidate_moves = list(candidate_moves)
        if candidate_horizon_length is not None:
            self.candidate_horizon_length = max(1, int(candidate_horizon_length))
        if local_path_utility_estimates is not None:
            self.local_path_utility_estimates = dict(local_path_utility_estimates)
        if local_collision_risk_estimates is not None:
            self.local_collision_risk_estimates = dict(local_collision_risk_estimates)
        if local_smoke_penalty_estimates is not None:
            self.local_smoke_penalty_estimates = dict(local_smoke_penalty_estimates)
        if local_drift_penalty_estimates is not None:
            self.local_drift_penalty_estimates = dict(local_drift_penalty_estimates)
        if task_support_score is not None:
            self.task_support_score = clamp01(task_support_score)
        if belief_gain_score is not None:
            self.belief_gain_score = clamp01(belief_gain_score)
        if path_stability_score is not None:
            self.path_stability_score = clamp01(path_stability_score)
        self.timestamp = ts
        if self.path_stability_score is None:
            self.path_stability_score = conf

    def apply_time_decay(self, current_time: float) -> None:
        """Decay path stability confidence over time."""
        if self.timestamp is None or self.path_stability_score is None:
            return
        age = compute_age(float(current_time), self.timestamp)
        if age <= 0.0:
            return
        self.path_stability_score = clamp01(
            self.path_stability_score * max(0.0, 1.0 - (0.03 * age))
        )
        if self.navigation_confidence is not None:
            self.navigation_confidence = clamp01(
                self.navigation_confidence * max(0.0, 1.0 - (0.03 * age))
            )

    def set_candidate_horizon_length(self, candidate_horizon_length: int) -> None:
        """Set local horizon length with a minimum of 1."""
        self.candidate_horizon_length = max(1, int(candidate_horizon_length))

    def runtime_context(self) -> dict[str, Any]:
        """Read-only live path context for planners and adaptation."""
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        """Read-only local path context snapshot."""
        return {
            "uav_id": self.uav_id,
            "current_path_segment": list(self.current_path_segment),
            "candidate_moves": list(self.candidate_moves),
            "candidate_horizon_length": self.candidate_horizon_length,
            "local_path_utility_estimates": dict(self.local_path_utility_estimates),
            "local_collision_risk_estimates": dict(self.local_collision_risk_estimates),
            "local_smoke_penalty_estimates": dict(self.local_smoke_penalty_estimates),
            "local_drift_penalty_estimates": dict(self.local_drift_penalty_estimates),
            "task_support_score": self.task_support_score,
            "belief_gain_score": self.belief_gain_score,
            "path_stability_score": self.path_stability_score,
            "timestamp": self.timestamp,
            "current_target": self.current_target,
            "current_action": self.current_action,
            "selected_direction": self.selected_direction,
            "last_positions": list(self.last_positions),
            "movement_stability": self.movement_stability,
            "stuck_count": self.stuck_count,
            "oscillation_score": self.oscillation_score,
            "nearby_fire": self.nearby_fire,
            "nearby_smoke": self.nearby_smoke,
            "local_risk_estimate": self.local_risk_estimate,
            "path_safety_score": self.path_safety_score,
            "target_switch_count": self.target_switch_count,
            "navigation_confidence": self.navigation_confidence,
            "sector_alignment_score": self.sector_alignment_score,
            "boundary_pressure": self.boundary_pressure,
            "congestion_pressure": self.congestion_pressure,
            "oscillation_risk": self.oscillation_score >= 0.45,
            "wind_edge_streak": self.wind_edge_streak,
            "wind_hold_streak": self.wind_hold_streak,
            "wind_same_target_streak": self.wind_same_target_streak,
            "wind_aware_hold_streak": self.wind_aware_hold_streak,
            "corridor_targets": list(self.corridor_targets),
            "corridor_index": self.corridor_index,
            "recent_corridor_targets": list(self.recent_corridor_targets),
            "force_wind_retarget": self.force_wind_retarget,
            "force_wind_sweep": self.force_wind_sweep,
            "pocket_streak": self.pocket_streak,
            "coverage_priority": self.coverage_priority,
            "hazard_buffer_level": self.hazard_buffer_level,
            "force_coverage_escape": self.force_coverage_escape,
            "post_rescue_coverage_steps_remaining": self.post_rescue_coverage_steps_remaining,
            "unresolved_victim_count": self.unresolved_victim_count,
            "recent_x_positions": list(self.recent_x_positions),
        }
