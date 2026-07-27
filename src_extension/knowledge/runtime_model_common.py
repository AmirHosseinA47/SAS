"""Minimal shared types for Step 4 runtime knowledge scaffolds.

Runtime knowledge follows a global rule: important items should carry **time**
(timestamp), confidence, and source.

TODO: Align ``Timestamp`` with simulator clock / monotonic time; tighten
``Confidence`` bounds and validation when wiring observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

# Grid cell in the adaptation layer's discrete world indexing (placeholder).
CellCoord: TypeAlias = tuple[int, int]

# Simulation or wall-clock time unit (placeholder).
Timestamp: TypeAlias = float

# Evidence weight, typically in [0.0, 1.0] once normalized (placeholder).
Confidence: TypeAlias = float

# Who produced an observation or fused belief (sensor id, UAV id, "global", …).
SourceId: TypeAlias = str


@dataclass
class KnowledgeProvenance:
    """Optional bundle for time-aware, confidence-aware, sourced knowledge."""

    timestamp: Timestamp | None = None
    confidence: Confidence | None = None
    source: SourceId | None = None
