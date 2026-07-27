"""Managed system: environment interaction support.

Managed system — environment interaction layer: read wildfire/smoke from the
simulator, apply UAV moves when driven by execution, and surface resulting world
changes including wind/drift outcomes as operational facts. This bridge is
domain-side I/O to Wildfire-UAVSim; it does not analyze, plan, or adapt.

Future integration must remain read/write without refactoring baseline
simulator internals.

TODO: Accept simulator model/world references; expose typed snapshots and
controlled apply hooks only—no adaptation policy here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EnvironmentBridge:
    """Managed-side bridge: lazy binding and queries against the running simulation."""

    _sim_handle: Any | None = None
    _wind_direction: str | None = None
    _wind_vector: tuple[float, float] | None = None
    _wind_timestamp: float = 0.0
    _wind_step: int = 0
    _wind_source: str = "config"
    _wind_history: list[dict[str, Any]] = field(default_factory=list)

    def attach(self, sim_handle: Any) -> None:
        """Store reference for managed-side read/write as integration allows."""
        self._sim_handle = sim_handle

    def update_wind(
        self,
        direction: str,
        vector: tuple[float, float],
        timestamp: float,
        *,
        step: int | None = None,
        source: str = "fire_model",
    ) -> None:
        """Record current wind spread direction for MAPE-K consumers."""
        self._wind_direction = str(direction or "").strip().lower()
        self._wind_vector = (float(vector[0]), float(vector[1]))
        self._wind_timestamp = float(timestamp)
        if step is not None:
            self._wind_step = int(step)
        self._wind_source = str(source or "fire_model")
        entry = {
            "direction": self._wind_direction,
            "vector": list(self._wind_vector),
            "timestamp": self._wind_timestamp,
            "step": self._wind_step,
            "source": self._wind_source,
        }
        self._wind_history.append(entry)
        if len(self._wind_history) > 256:
            self._wind_history = self._wind_history[-128:]

    def get_wind_summary(self) -> dict[str, Any]:
        """Latest wind facts for monitors, analysis, and execution."""
        if self._wind_direction is None or self._wind_vector is None:
            return {}
        return {
            "direction": self._wind_direction,
            "wind_direction": self._wind_direction,
            "vector": list(self._wind_vector),
            "wind_vector": list(self._wind_vector),
            "timestamp": self._wind_timestamp,
            "step": self._wind_step,
            "source": self._wind_source,
        }

    def snapshot(self, current_time: float = 0.0) -> dict[str, Any]:
        """Return a shallow, extension-safe view of environment state."""
        sim = self._sim_handle
        if sim is None:
            return {}

        grid = getattr(sim, "grid", None)
        width = getattr(grid, "width", None)
        height = getattr(grid, "height", None)
        schedule = getattr(sim, "schedule", None)
        agents_list = getattr(schedule, "agents", ()) if schedule is not None else ()

        fire_cells: list[list[int]] = []
        burning_cells: list[list[int]] = []
        smoke_cells: list[list[int]] = []

        for agent in agents_list or ():
            pos = getattr(agent, "pos", None)
            if pos is None or len(pos) < 2:
                continue
            smoke = getattr(agent, "smoke", None)
            is_burning = getattr(agent, "is_burning", None)
            is_fire_like = callable(is_burning) or smoke is not None
            if not is_fire_like:
                continue

            cell = [int(pos[0]), int(pos[1])]
            fire_cells.append(cell)
            if callable(is_burning) and bool(is_burning()):
                burning_cells.append(cell)
            smoke_active = getattr(smoke, "is_smoke_active", None)
            if callable(smoke_active) and bool(smoke_active()):
                smoke_cells.append(cell)

        wind_summary = self.get_wind_summary()
        if not wind_summary:
            wind = getattr(sim, "wind", None)
            if wind is not None:
                from common_fixed_variables import (
                    normalize_wind_direction,
                    wind_vector_from_direction,
                )

                direction = normalize_wind_direction(
                    getattr(wind, "wind_direction", None)
                )
                vector = wind_vector_from_direction(direction)
                wind_summary = {
                    "direction": direction,
                    "wind_direction": direction,
                    "vector": list(vector),
                    "wind_vector": list(vector),
                    "timestamp": float(current_time),
                    "step": int(getattr(sim, "evaluation_timesteps_counter", 0) or 0),
                    "source": "fire_model",
                }

        return {
            "timestamp": float(current_time),
            "source": "environment_bridge",
            "grid_width": width,
            "grid_height": height,
            "fire_cells": fire_cells,
            "burning_cells": burning_cells,
            "smoke_cells": smoke_cells,
            "wind_available": bool(wind_summary),
            "wind_summary": wind_summary or None,
            "wind_direction": (wind_summary or {}).get("direction"),
            "wind_vector": (wind_summary or {}).get("vector"),
        }
