"""Managing system: structured observation payloads (scaffold).

Monitors **collect and structure** facts from the **managed system** and
**environment** into these types. Observations are **inputs** to **knowledge**
update and **analysis**—they are **not** decisions, **not** plans, and **not**
execution commands.

Minimal generic fields; expand deliberately as integration proceeds.

TODO: Version observations if schema evolves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScalarObservation:
    """Single named metric or reading (structured observation facet)."""

    name: str
    value: float
    unit: str = ""
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityObservation:
    """Observation tied to a managed entity id (structured snapshot facet)."""

    entity_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObservationBatch:
    """Grouped observations for one tick or window (monitor output; no decisions)."""

    step_index: int
    items: tuple[ScalarObservation | EntityObservation, ...] = ()
