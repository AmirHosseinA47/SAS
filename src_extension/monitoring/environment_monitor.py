"""Explicit environment perception snapshot (complementary to UAV-local monitoring)."""

from __future__ import annotations

from typing import Any

import agents as agents_module

from common_fixed_variables import ACTIVATE_SMOKE

from src_extension.knowledge.runtime_model_common import CellCoord


class EnvironmentMonitor:
    """Read-only environmental facts from the managed simulation model."""

    def collect_environment_snapshot(self, model: Any, current_time: float) -> dict[str, Any]:
        ts = float(current_time)
        wind_dir = getattr(model.wind, "wind_direction", None) if hasattr(model, "wind") else None

        smoke_cells: list[list[int]] = []
        fire_cells: list[list[int]] = []

        for agent in model.schedule.agents:
            if type(agent) is not agents_module.Fire:
                continue
            cx, cy = int(agent.pos[0]), int(agent.pos[1])
            pos = [cx, cy]
            if ACTIVATE_SMOKE and agent.smoke.is_smoke_active():
                smoke_cells.append(pos)
            elif agent.is_burning():
                fire_cells.append(pos)

        return {
            "time": ts,
            "timestamp": ts,
            "wind": {
                "direction": wind_dir,
                "intensity": None,
            },
            "smoke_cells": smoke_cells,
            "fire_cells": fire_cells,
            "hazard_zones": [],
            "source": "environment_monitor",
            "confidence": 1.0,
        }


def cells_in_any_uav_fov(model: Any, radius: int, moore: bool = True) -> set[CellCoord]:
    """Union of observation neighborhoods for all UAVs (grid coords)."""
    union: set[CellCoord] = set()
    for agent in model.schedule.agents:
        if type(agent) is not agents_module.UAV:
            continue
        cells = model.grid.get_neighborhood(
            agent.pos,
            moore=moore,
            include_center=True,
            radius=radius,
        )
        union.update(cells)
    return union
