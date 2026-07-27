"""Managing system: Fire Belief runtime knowledge.

This is a belief-based view of fire not a deterministic copy of simulator
ground truth. It holds estimated cells, probability/confidence maps, predicted
fronts, negative observations with separate timing, and uncertain regions
for adaptation-facing consumers.

**Not allowed here:** analysis, triggers, utility scoring, or planning—only
**knowledge** containers and trivial refresh hooks.

Negative information, freshness decay, and belief fusion will be
handled in future update paths.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .knowledge_utils import clamp01, compute_age, validate_metadata
from .runtime_model_common import CellCoord, Confidence, KnowledgeProvenance, Timestamp


@dataclass
class FireBeliefRuntimeState:
    """Grid-based placeholders for fire belief state (Step 4)."""

    estimated_burning_cells: set[CellCoord] = field(default_factory=set)
    estimated_fire_front_cells: set[CellCoord] = field(default_factory=set)
    fire_probability_map: dict[CellCoord, float] = field(default_factory=dict)
    fire_confidence_map: dict[CellCoord, Confidence] = field(default_factory=dict)
    predicted_fire_front_map: dict[CellCoord, float] = field(default_factory=dict)
    predicted_spread_bias: dict[str, float] = field(default_factory=dict)
    last_observed_fire_time: dict[CellCoord, Timestamp] = field(default_factory=dict)
    negative_observation_map: dict[CellCoord, bool] = field(default_factory=dict)
    negative_observation_time: dict[CellCoord, Timestamp] = field(default_factory=dict)
    fire_sector_map: dict[str, frozenset[CellCoord]] = field(default_factory=dict)
    fire_sector_priority: dict[str, float] = field(default_factory=dict)
    uncertain_fire_regions: set[CellCoord] = field(default_factory=set)


@dataclass
class FireRuntimeModel:
    """Runtime knowledge: fire-related **beliefs** (not the managed world state).

    This model is deliberately belief/time/confidence aware:
    - per-cell fire probability and confidence
    - timestamps for positive/negative observations
    - uncertainty tracking for smoke/low-confidence areas

    TODO: Add multi-source fusion and predictive spread logic when integration
    paths are finalized.
    """

    step_index: int = 0
    provenance: KnowledgeProvenance = field(default_factory=KnowledgeProvenance)
    belief: FireBeliefRuntimeState = field(default_factory=FireBeliefRuntimeState)
    summary: dict[str, Any] = field(default_factory=dict)
    _last_observation_source: dict[CellCoord, str] = field(default_factory=dict)
    _last_update_time_map: dict[CellCoord, Timestamp] = field(default_factory=dict)
    _grid_width: int = 0
    _grid_height: int = 0

    def update(self, step_index: int) -> None:
        """TODO: Fuse observations into ``belief``; apply freshness / negative-info decay."""
        self.step_index = step_index

    @staticmethod
    def clamp01(value: float) -> float:
        """Clamp a numeric value into [0.0, 1.0]."""
        return clamp01(value)

    @staticmethod
    def cell_key(cell: CellCoord) -> str:
        """Return a JSON-friendly key for a grid cell."""
        return f"{cell[0]},{cell[1]}"

    def initialize_grid(
        self,
        width: int,
        height: int,
        default_probability: float = 0.0,
        default_confidence: float = 0.0,
    ) -> None:
        """Initialize per-cell probability/confidence memory for a rectangular grid."""
        self._grid_width = max(0, int(width))
        self._grid_height = max(0, int(height))
        p0 = self.clamp01(default_probability)
        c0 = self.clamp01(default_confidence)
        self.belief.fire_probability_map.clear()
        self.belief.fire_confidence_map.clear()
        self.belief.estimated_burning_cells.clear()
        self.belief.estimated_fire_front_cells.clear()
        self.belief.uncertain_fire_regions.clear()
        for y in range(self._grid_height):
            for x in range(self._grid_width):
                cell = (x, y)
                self.belief.fire_probability_map[cell] = p0
                self.belief.fire_confidence_map[cell] = c0
                self._last_update_time_map.setdefault(cell, 0.0)
                if c0 < 0.4:
                    self.belief.uncertain_fire_regions.add(cell)
        self._refresh_estimated_sets()

    def update_fire_observation(
        self,
        cell: CellCoord,
        timestamp: Timestamp,
        source: str,
        confidence: float = 1.0,
        probability: float = 1.0,
    ) -> None:
        """Incorporate a positive fire observation for one cell."""
        ts, c_obs, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        b = self.belief
        old_p = b.fire_probability_map.get(cell, 0.0)
        old_c = b.fire_confidence_map.get(cell, 0.0)
        p_obs = self.clamp01(probability)
        # Raise belief/confidence toward observation without hard overwrite.
        b.fire_probability_map[cell] = self.clamp01(max(old_p, (old_p + p_obs) * 0.5))
        b.fire_confidence_map[cell] = self.clamp01(max(old_c, (old_c + c_obs) * 0.5))
        b.last_observed_fire_time[cell] = ts
        b.negative_observation_map.pop(cell, None)
        b.negative_observation_time.pop(cell, None)
        self._last_observation_source[cell] = src
        self._last_update_time_map[cell] = ts
        self._refresh_estimated_sets()
        self._refresh_uncertainty()

    def update_no_fire_observation(
        self,
        cell: CellCoord,
        timestamp: Timestamp,
        source: str,
        confidence: float = 1.0,
    ) -> None:
        """Incorporate an explicit no-fire observation and negative evidence."""
        ts, c_obs, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        b = self.belief
        old_p = b.fire_probability_map.get(cell, 0.0)
        old_c = b.fire_confidence_map.get(cell, 0.0)
        reduction = 0.5 + 0.5 * c_obs
        b.fire_probability_map[cell] = self.clamp01(old_p * (1.0 - reduction))
        b.fire_confidence_map[cell] = self.clamp01(max(old_c, c_obs * 0.8))
        b.negative_observation_map[cell] = True
        b.negative_observation_time[cell] = ts
        self._last_observation_source[cell] = src
        self._last_update_time_map[cell] = ts
        self._refresh_estimated_sets()
        self._refresh_uncertainty()

    def mark_smoke_obscured(
        self,
        cell: CellCoord,
        timestamp: Timestamp,
        source: str,
        confidence: float = 0.5,
    ) -> None:
        """Record smoke-obscured visibility: keep belief, lower confidence slightly."""
        ts, c_obs, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        b = self.belief
        old_c = b.fire_confidence_map.get(cell, 0.0)
        b.fire_confidence_map[cell] = self.clamp01(max(0.0, old_c - (0.15 * (1.0 - c_obs))))
        self._last_observation_source[cell] = src
        self._last_update_time_map[cell] = ts
        self._refresh_uncertainty()

    def apply_decay(
        self,
        current_time: Timestamp,
        probability_decay_rate: float = 0.01,
        confidence_decay_rate: float = 0.02,
    ) -> None:
        """Apply simple time decay to per-cell beliefs/confidence."""
        b = self.belief
        p_rate = max(0.0, float(probability_decay_rate))
        c_rate = max(0.0, float(confidence_decay_rate))
        for cell, prob in list(b.fire_probability_map.items()):
            last_time = self._last_update_time_map.get(cell, 0.0)
            dt = max(0.0, float(current_time) - float(last_time))
            if dt <= 0.0:
                continue
            b.fire_probability_map[cell] = self.clamp01(prob * (1.0 - (p_rate * dt)))
            c0 = b.fire_confidence_map.get(cell, 0.0)
            b.fire_confidence_map[cell] = self.clamp01(c0 * (1.0 - (c_rate * dt)))
            # Keep last update marker at current decay application point.
            self._last_update_time_map[cell] = float(current_time)
        self._refresh_estimated_sets()
        self._refresh_uncertainty()

    def decay_negative_observations(self, current_time: Timestamp, decay_rate: float = 0.05) -> None:
        """Decay strength of old no-fire evidence so it never blocks fire permanently."""
        b = self.belief
        rate = max(0.0, float(decay_rate))
        now = float(current_time)
        for cell in list(b.negative_observation_map.keys()):
            last_ts = b.negative_observation_time.get(cell, 0.0)
            age = compute_age(now, last_ts)
            if age <= 0.0:
                continue
            conf = b.fire_confidence_map.get(cell, 0.0)
            weakened_conf = self.clamp01(conf * max(0.0, 1.0 - rate * age))
            b.fire_confidence_map[cell] = weakened_conf
            if weakened_conf < 0.1:
                b.negative_observation_map.pop(cell, None)
                b.negative_observation_time.pop(cell, None)
            self._last_update_time_map[cell] = now

    def apply_time_decay(self, current_time: float) -> None:
        """Apply unified fire belief decay while preserving strong smoke-hidden beliefs."""
        b = self.belief
        now = float(current_time)
        for cell, prob in list(b.fire_probability_map.items()):
            last_time = self._last_update_time_map.get(cell, 0.0)
            age = compute_age(now, last_time)
            if age <= 0.0:
                continue
            conf = b.fire_confidence_map.get(cell, 0.0)
            # Preserve high-probability beliefs while still decaying over time.
            if prob >= 0.75:
                prob_rate = 0.005
            elif prob >= 0.4:
                prob_rate = 0.01
            else:
                prob_rate = 0.02
            conf_rate = 0.03
            b.fire_probability_map[cell] = self.clamp01(prob * max(0.0, 1.0 - prob_rate * age))
            b.fire_confidence_map[cell] = self.clamp01(conf * max(0.0, 1.0 - conf_rate * age))
            self._last_update_time_map[cell] = now
        self.decay_negative_observations(current_time=now, decay_rate=0.05)
        self._refresh_estimated_sets()
        self._refresh_uncertainty()

    def get_best_search_target(self, current_time: float, min_conf: float = 0.3) -> CellCoord | None:
        """Return best fallback fire target ignoring visibility constraints."""
        _ = float(current_time)
        min_conf_c = self.clamp01(min_conf)
        best_cell: CellCoord | None = None
        best_score = -1.0
        for cell, prob in self.belief.fire_probability_map.items():
            conf = self.belief.fire_confidence_map.get(cell, 0.0)
            if conf < min_conf_c:
                continue
            last_time = self._last_update_time_map.get(cell, 0.0)
            freshness = 1.0 / (1.0 + max(0.0, float(current_time) - float(last_time)))
            score = (0.7 * prob) + (0.2 * conf) + (0.1 * freshness)
            if score > best_score:
                best_score = score
                best_cell = cell
        return best_cell

    def get_high_probability_cells(self, threshold: float = 0.7) -> set[CellCoord]:
        """Return cells with probability >= threshold."""
        t = self.clamp01(threshold)
        return {cell for cell, prob in self.belief.fire_probability_map.items() if prob >= t}

    def get_uncertain_cells(self, confidence_threshold: float = 0.4) -> set[CellCoord]:
        """Return cells with confidence below threshold."""
        t = self.clamp01(confidence_threshold)
        return {cell for cell, conf in self.belief.fire_confidence_map.items() if conf < t}

    def get_last_known_fire_regions(self, threshold: float = 0.7) -> set[CellCoord]:
        """Return likely fire regions from stored belief, independent of current visibility."""
        return self.get_high_probability_cells(threshold=threshold)

    def _refresh_estimated_sets(self) -> None:
        """Refresh estimated burning and front cells from current belief maps."""
        b = self.belief
        b.estimated_burning_cells = self.get_high_probability_cells(threshold=0.7)
        front: set[CellCoord] = set()
        for cell in b.estimated_burning_cells:
            for nx, ny in self._neighbors4(cell):
                if b.fire_probability_map.get((nx, ny), 0.0) < 0.7:
                    front.add(cell)
                    break
        b.estimated_fire_front_cells = front

    def _refresh_uncertainty(self, confidence_threshold: float = 0.4) -> None:
        """Refresh uncertain-fire region set from confidence values."""
        self.belief.uncertain_fire_regions = self.get_uncertain_cells(confidence_threshold)

    @staticmethod
    def _neighbors4(cell: CellCoord) -> tuple[CellCoord, CellCoord, CellCoord, CellCoord]:
        """Return von-Neumann neighbors (without bounds checks)."""
        x, y = cell
        return ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))

    def snapshot(self) -> dict[str, Any]:
        """Read-only knowledge snapshot for planners/monitors (no side effects)."""
        # TODO: Extend snapshot with sector-level confidence after fusion logic exists.
        b = self.belief
        return {
            "step_index": self.step_index,
            "provenance": asdict(self.provenance),
            "summary": dict(self.summary),
            "grid_size": {"width": self._grid_width, "height": self._grid_height},
            "estimated_burning_cells": [list(c) for c in b.estimated_burning_cells],
            "estimated_fire_front_cells": [list(c) for c in b.estimated_fire_front_cells],
            "fire_probability_map": {self.cell_key(c): v for c, v in b.fire_probability_map.items()},
            "fire_confidence_map": {self.cell_key(c): v for c, v in b.fire_confidence_map.items()},
            "predicted_fire_front_map": {self.cell_key(c): v for c, v in b.predicted_fire_front_map.items()},
            "predicted_spread_bias": dict(b.predicted_spread_bias),
            "last_observed_fire_time": {self.cell_key(c): v for c, v in b.last_observed_fire_time.items()},
            "negative_observation_map": {self.cell_key(c): v for c, v in b.negative_observation_map.items()},
            "negative_observation_time": {self.cell_key(c): v for c, v in b.negative_observation_time.items()},
            "fire_sector_map": {k: [list(c) for c in v] for k, v in b.fire_sector_map.items()},
            "fire_sector_priority": dict(b.fire_sector_priority),
            "uncertain_fire_regions": [list(c) for c in b.uncertain_fire_regions],
            "last_observation_source": {
                self.cell_key(c): src for c, src in self._last_observation_source.items()
            },
        }
