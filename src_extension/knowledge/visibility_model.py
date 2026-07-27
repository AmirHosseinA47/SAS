"""Managing system: Visibility and uncertainty runtime knowledge.

Structured partial observability: which cells are visible, smoke-obscured,
per-cell observation status, confidence, staleness, and regional uncertainty.
This is knowledge for adaptation, not a second smoke engine.

Decay rules, negative observations, and fusion with fire belief are **TODO**
for future wiring—not implemented here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .knowledge_utils import clamp01, compute_age, validate_metadata
from .runtime_model_common import CellCoord, Confidence, KnowledgeProvenance, Timestamp


class ObservationStatus(str, Enum):
    """Per-cell observation classification (string values are stable API)."""

    OBSERVED_FIRE = "observed_fire"
    OBSERVED_NO_FIRE = "observed_no_fire"
    SMOKE_OBSCURED = "smoke_obscured"
    NEVER_SEEN = "never_seen"
    STALE_INFORMATION = "stale_information"


@dataclass
class VisibilityRuntimeState:
    """Typed placeholders for visibility / uncertainty (Step 4)."""

    visible_cells: set[CellCoord] = field(default_factory=set)
    smoke_obscured_cells: set[CellCoord] = field(default_factory=set)
    observation_status_map: dict[CellCoord, ObservationStatus] = field(default_factory=dict)
    cell_confidence_map: dict[CellCoord, Confidence] = field(default_factory=dict)
    staleness_map: dict[CellCoord, float] = field(default_factory=dict)
    last_seen_timestamp_per_cell: dict[CellCoord, Timestamp] = field(default_factory=dict)
    visibility_confidence_decay: float = 0.02
    region_uncertainty_score: dict[str, float] = field(default_factory=dict)
    unknown_or_uncertain_regions: set[CellCoord] = field(default_factory=set)
    information_freshness_map: dict[CellCoord, float] = field(default_factory=dict)


@dataclass
class VisibilityModel:
    """Runtime knowledge for partial observability and uncertainty awareness.

    This model tracks what is visible, what is smoke-obscured, and how stale or
    uncertain each cell's information is. The resulting state can later support
    informative path planning decisions, but this module keeps only knowledge.

    TODO: Add multi-UAV fusion and region-level aggregation strategies.
    """

    step_index: int = 0
    provenance: KnowledgeProvenance = field(default_factory=KnowledgeProvenance)
    state: VisibilityRuntimeState = field(default_factory=VisibilityRuntimeState)
    visibility_grid_ref: Any | None = None
    notes: dict[str, Any] = field(default_factory=dict)
    _grid_width: int = 0
    _grid_height: int = 0
    _all_cells: set[CellCoord] = field(default_factory=set)
    smoke_obscured_handler: Any | None = None

    def update(self, step_index: int) -> None:
        """TODO: Ingest observations; refresh staleness / freshness; decay old negatives."""
        self.step_index = step_index

    def set_smoke_obscured_handler(self, handler: Any) -> None:
        """Set optional callback invoked when a cell becomes smoke-obscured."""
        self.smoke_obscured_handler = handler

    @staticmethod
    def _clamp01(value: float) -> float:
        return clamp01(value)

    @staticmethod
    def _cell_key(cell: CellCoord) -> str:
        return f"{cell[0]},{cell[1]}"

    def initialize_grid(self, width: int, height: int) -> None:
        """Initialize known cell space and reset visibility knowledge fields."""
        self._grid_width = max(0, int(width))
        self._grid_height = max(0, int(height))
        self._all_cells = {
            (x, y) for y in range(self._grid_height) for x in range(self._grid_width)
        }

        s = self.state
        s.visible_cells.clear()
        s.smoke_obscured_cells.clear()
        s.observation_status_map = {
            cell: ObservationStatus.NEVER_SEEN for cell in self._all_cells
        }
        s.cell_confidence_map = {cell: 0.0 for cell in self._all_cells}
        s.staleness_map = {cell: 0.0 for cell in self._all_cells}
        s.last_seen_timestamp_per_cell.clear()
        s.information_freshness_map = {cell: 0.0 for cell in self._all_cells}
        s.unknown_or_uncertain_regions = set(self._all_cells)
        s.region_uncertainty_score = {}

    def update_visible_cell(
        self,
        cell: CellCoord,
        timestamp: Timestamp,
        status: ObservationStatus | str,
        confidence: float = 1.0,
        source: str = "visibility_sensor",
    ) -> None:
        """Update one visible cell using a fresh direct observation."""
        ts, conf, _ = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        resolved_status = (
            status if isinstance(status, ObservationStatus) else ObservationStatus(status)
        )
        if resolved_status == ObservationStatus.SMOKE_OBSCURED:
            self.update_smoke_obscured_cell(
                cell=cell,
                timestamp=ts,
                confidence=conf,
                source=source,
            )
            return

        s = self.state
        s.visible_cells.add(cell)
        s.smoke_obscured_cells.discard(cell)
        s.observation_status_map[cell] = resolved_status
        s.cell_confidence_map[cell] = conf
        s.last_seen_timestamp_per_cell[cell] = ts
        # Fresh direct observations reduce staleness.
        s.staleness_map[cell] = 0.0
        s.information_freshness_map[cell] = 1.0

    def update_smoke_obscured_cell(
        self,
        cell: CellCoord,
        timestamp: Timestamp,
        confidence: float = 0.5,
        source: str = "visibility_sensor",
    ) -> None:
        """Mark one cell as smoke-obscured and slightly lower confidence."""
        ts, target_conf, src = validate_metadata(timestamp=timestamp, confidence=confidence, source=source)
        s = self.state
        prior_conf = s.cell_confidence_map.get(cell, 0.0)
        # Keep some prior belief but nudge confidence downward.
        s.cell_confidence_map[cell] = self._clamp01(min(prior_conf, target_conf))
        s.observation_status_map[cell] = ObservationStatus.SMOKE_OBSCURED
        s.smoke_obscured_cells.add(cell)
        s.visible_cells.discard(cell)
        s.last_seen_timestamp_per_cell[cell] = ts
        s.staleness_map[cell] = 0.0
        s.information_freshness_map[cell] = 1.0
        if callable(self.smoke_obscured_handler):
            self.smoke_obscured_handler(cell=cell, timestamp=ts, source=src, confidence=target_conf)

    def update_staleness(self, current_time: Timestamp) -> None:
        """Refresh per-cell staleness and mark aged observations as stale."""
        s = self.state
        now = float(current_time)
        cells = self._all_cells or set(s.observation_status_map.keys())
        for cell in cells:
            if cell not in s.last_seen_timestamp_per_cell:
                # Never seen stays explicit and distinguishable.
                s.observation_status_map[cell] = ObservationStatus.NEVER_SEEN
                s.staleness_map[cell] = float("inf")
                s.information_freshness_map[cell] = 0.0
                continue

            dt = max(0.0, now - float(s.last_seen_timestamp_per_cell[cell]))
            s.staleness_map[cell] = dt
            if (
                s.observation_status_map.get(cell) != ObservationStatus.SMOKE_OBSCURED
                and dt > 10.0
            ):
                s.observation_status_map[cell] = ObservationStatus.STALE_INFORMATION

            decay = max(0.0, 1.0 - s.visibility_confidence_decay * dt)
            base_conf = s.cell_confidence_map.get(cell, 0.0)
            s.cell_confidence_map[cell] = self._clamp01(base_conf * decay)

    def apply_time_decay(self, current_time: float) -> None:
        """Apply unified visibility decay and stale conversion over time."""
        s = self.state
        now = float(current_time)
        for cell, last_seen in list(s.last_seen_timestamp_per_cell.items()):
            age = compute_age(now, last_seen)
            s.staleness_map[cell] = age
            freshness = self._clamp01(1.0 - (s.visibility_confidence_decay * age))
            s.information_freshness_map[cell] = freshness
            base_conf = s.cell_confidence_map.get(cell, 0.0)
            s.cell_confidence_map[cell] = self._clamp01(base_conf * freshness)
            status = s.observation_status_map.get(cell)
            if status != ObservationStatus.SMOKE_OBSCURED and age > 10.0:
                s.observation_status_map[cell] = ObservationStatus.STALE_INFORMATION
        self.get_uncertain_regions()

    def compute_information_freshness(self, current_time: Timestamp) -> dict[CellCoord, float]:
        """Compute normalized freshness per cell from last-seen and staleness."""
        self.update_staleness(current_time)
        s = self.state
        cells = self._all_cells or set(s.observation_status_map.keys())
        for cell in cells:
            status = s.observation_status_map.get(cell, ObservationStatus.NEVER_SEEN)
            if status == ObservationStatus.NEVER_SEEN:
                s.information_freshness_map[cell] = 0.0
                continue
            staleness = s.staleness_map.get(cell, float("inf"))
            if staleness == float("inf"):
                s.information_freshness_map[cell] = 0.0
            else:
                s.information_freshness_map[cell] = self._clamp01(
                    1.0 - (s.visibility_confidence_decay * staleness)
                )
        return dict(s.information_freshness_map)

    def get_uncertain_regions(
        self,
        confidence_threshold: float = 0.4,
        staleness_threshold: float = 10.0,
    ) -> set[CellCoord]:
        """Return cells uncertain due to low confidence, smoke, never-seen, or staleness."""
        s = self.state
        c_t = self._clamp01(confidence_threshold)
        stale_t = max(0.0, float(staleness_threshold))
        uncertain: set[CellCoord] = set()
        cells = self._all_cells or set(s.observation_status_map.keys())
        for cell in cells:
            status = s.observation_status_map.get(cell, ObservationStatus.NEVER_SEEN)
            conf = s.cell_confidence_map.get(cell, 0.0)
            stale = s.staleness_map.get(cell, float("inf"))
            if (
                status in (ObservationStatus.SMOKE_OBSCURED, ObservationStatus.NEVER_SEEN)
                or status == ObservationStatus.STALE_INFORMATION
                or conf < c_t
                or stale > stale_t
            ):
                uncertain.add(cell)
        s.unknown_or_uncertain_regions = uncertain
        return set(uncertain)

    def snapshot(self) -> dict[str, Any]:
        """Read-only knowledge snapshot (no side effects)."""
        s = self.state
        return {
            "step_index": self.step_index,
            "provenance": asdict(self.provenance),
            "grid_size": {"width": self._grid_width, "height": self._grid_height},
            "visibility_grid_ref": self.visibility_grid_ref,
            "notes": dict(self.notes),
            "visible_cells": [list(c) for c in s.visible_cells],
            "smoke_obscured_cells": [list(c) for c in s.smoke_obscured_cells],
            "observation_status_map": {
                self._cell_key(c): v.value for c, v in s.observation_status_map.items()
            },
            "cell_confidence_map": {self._cell_key(c): v for c, v in s.cell_confidence_map.items()},
            "staleness_map": {self._cell_key(c): v for c, v in s.staleness_map.items()},
            "last_seen_timestamp_per_cell": {
                self._cell_key(c): v for c, v in s.last_seen_timestamp_per_cell.items()
            },
            "visibility_confidence_decay": s.visibility_confidence_decay,
            "region_uncertainty_score": dict(s.region_uncertainty_score),
            "unknown_or_uncertain_regions": [list(c) for c in s.unknown_or_uncertain_regions],
            "information_freshness_map": {
                self._cell_key(c): v for c, v in s.information_freshness_map.items()
            },
        }
