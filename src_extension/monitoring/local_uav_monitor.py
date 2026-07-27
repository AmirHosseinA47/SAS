"""Local UAV monitoring: collect, structure, and optionally forward observations.

Observe-only: no planning or movement decisions. Outputs feed analysis/knowledge.
"""

from __future__ import annotations

from typing import Any

from common_fixed_variables import ACTIVATE_SMOKE, UAV_OBSERVATION_RADIUS, euclidean_distance

from src_extension.knowledge.fire_runtime_model import FireRuntimeModel
from src_extension.knowledge.uav_resource_model import UAVResourceModel
from src_extension.knowledge.victim_runtime_model import VictimRuntimeModel
from src_extension.knowledge.visibility_model import ObservationStatus, VisibilityModel
from src_extension.knowledge.runtime_model_common import CellCoord, Timestamp

from .monitoring_interfaces import Cell, LocalObservation

import agents as agents_module


class LocalUAVMonitor:
    """Structured local observation collector for one UAV (observe-only)."""

    _MOVE_X = (1, 0, -1, 0)
    _MOVE_Y = (0, -1, 0, 1)
    _CONFIRM_PROB_THRESHOLD = 0.35

    def __init__(
        self,
        uav_id: str,
        fire_runtime_model: FireRuntimeModel,
        visibility_model: VisibilityModel,
        victim_runtime_model: VictimRuntimeModel,
        uav_resource_model: UAVResourceModel,
    ) -> None:
        self.uav_id = uav_id
        self.fire_runtime_model = fire_runtime_model
        self.visibility_model = visibility_model
        self.victim_runtime_model = victim_runtime_model
        self.uav_resource_model = uav_resource_model

        self._cells_ever_seen: set[CellCoord] = set()
        self._last_patch_signature: dict[CellCoord, tuple[bool, bool, str]] = {}
        self._prev_fov_cell_uncertain: dict[CellCoord, bool] = {}

    @staticmethod
    def _dir_to_delta(selected_dir: int) -> tuple[int, int]:
        d = int(selected_dir) % 4
        return (LocalUAVMonitor._MOVE_X[d], LocalUAVMonitor._MOVE_Y[d])

    def _visible_cells(self, uav: Any) -> list[CellCoord]:
        return list(
            uav.model.grid.get_neighborhood(
                uav.pos,
                moore=uav.moore,
                include_center=True,
                radius=UAV_OBSERVATION_RADIUS,
            )
        )

    def _cell_visibility_status_key(self, cell: CellCoord) -> str:
        st = self.visibility_model.state.observation_status_map.get(cell)
        if st is None:
            return "never_seen"
        return st.value if hasattr(st, "value") else str(st)

    def _is_visibility_uncertain(self, cell: CellCoord) -> bool:
        st = self.visibility_model.state.observation_status_map.get(cell, ObservationStatus.NEVER_SEEN)
        return st in (
            ObservationStatus.SMOKE_OBSCURED,
            ObservationStatus.NEVER_SEEN,
            ObservationStatus.STALE_INFORMATION,
        )

    def _is_visibility_known(self, cell: CellCoord) -> bool:
        st = self.visibility_model.state.observation_status_map.get(cell)
        return st in (ObservationStatus.OBSERVED_FIRE, ObservationStatus.OBSERVED_NO_FIRE)

    def _classify_cells(self, uav: Any, cells: list[CellCoord]) -> tuple[list[CellCoord], list[CellCoord]]:
        fire_cells: list[CellCoord] = []
        smoke_cells: list[CellCoord] = []
        for cell in cells:
            contents = uav.model.grid.get_cell_list_contents([cell])
            for agent in contents:
                if type(agent) is agents_module.Fire:
                    if ACTIVATE_SMOKE and agent.smoke.is_smoke_active():
                        smoke_cells.append(cell)
                    elif agent.is_burning():
                        fire_cells.append(cell)
                    break
        return fire_cells, smoke_cells

    def _visible_victim_candidates(self, cells: list[CellCoord]) -> list[dict[str, Any]]:
        cell_set = set(cells)
        out: list[dict[str, Any]] = []
        for vid, rec in self.victim_runtime_model.victims.items():
            pos = rec.estimated_position
            if pos is None:
                continue
            cx, cy = int(round(pos[0])), int(round(pos[1]))
            ch: CellCoord = (cx, cy)
            if ch in cell_set:
                out.append(
                    {
                        "victim_id": vid,
                        "cell": list(ch),
                        "confidence": rec.confidence_score,
                    }
                )
        return out

    def _negative_observations(
        self,
        cells: list[CellCoord],
        fire_cells: set[CellCoord],
        smoke_cells: set[CellCoord],
        victim_cells: set[CellCoord],
        timestamp: Timestamp,
        base_confidence: float,
    ) -> list[tuple[CellCoord, float, float]]:
        neg: list[tuple[CellCoord, float, float]] = []
        for cell in cells:
            if cell in fire_cells or cell in smoke_cells or cell in victim_cells:
                continue
            neg.append((cell, float(base_confidence), float(timestamp)))
        return neg

    def _belief_confirmation_flags(
        self,
        uav: Any,
        cells: list[CellCoord],
    ) -> list[CellCoord]:
        fm = self.fire_runtime_model.belief
        confirmed: list[CellCoord] = []
        for cell in cells:
            if cell not in fm.fire_probability_map:
                continue
            contents = uav.model.grid.get_cell_list_contents([cell])
            fire_agent = None
            for agent in contents:
                if type(agent) is agents_module.Fire:
                    fire_agent = agent
                    break
            if fire_agent is None:
                continue
            if ACTIVATE_SMOKE and fire_agent.smoke.is_smoke_active():
                continue
            prob = float(fm.fire_probability_map.get(cell, 0.0))
            observed_flag = 1.0 if fire_agent.is_burning() else 0.0
            if abs(prob - observed_flag) < self._CONFIRM_PROB_THRESHOLD:
                confirmed.append(cell)
        return confirmed

    _W_NEW = 1.0
    _W_UPDATE = 0.6
    _W_CONFIRM = 0.7
    _W_UNCERTAINTY = 1.2

    def _compute_information_gain(
        self,
        cells: list[CellCoord],
        patch_sig: dict[CellCoord, tuple[bool, bool, str]],
        confirmations: list[CellCoord],
    ) -> tuple[float, float]:
        new_cells: list[CellCoord] = []
        updated_cells: list[CellCoord] = []
        for cell in cells:
            sig = patch_sig.get(cell)
            if sig is None:
                continue
            if cell not in self._cells_ever_seen:
                new_cells.append(cell)
            else:
                prev = self._last_patch_signature.get(cell)
                if prev is not None and prev != sig:
                    updated_cells.append(cell)

        uncertainty_reduction = 0
        for cell in cells:
            prev_u = self._prev_fov_cell_uncertain.get(cell)
            now_known = self._is_visibility_known(cell)
            if prev_u is True and now_known:
                uncertainty_reduction += 1

        n_conf = len(confirmations)
        n_vis = max(1, len(cells))
        raw_gain = (
            self._W_NEW * float(len(new_cells))
            + self._W_UPDATE * float(len(updated_cells))
            + self._W_CONFIRM * float(n_conf)
            + self._W_UNCERTAINTY * float(uncertainty_reduction)
        )
        normalized_gain = raw_gain / float(n_vis)
        return raw_gain, normalized_gain

    def _local_uncertainty_cells(self, cells: list[CellCoord]) -> list[Cell]:
        out: list[Cell] = []
        for cell in cells:
            status = self.visibility_model.state.observation_status_map.get(
                cell, ObservationStatus.NEVER_SEEN
            )
            if status in (
                ObservationStatus.SMOKE_OBSCURED,
                ObservationStatus.NEVER_SEEN,
                ObservationStatus.STALE_INFORMATION,
            ):
                out.append((int(cell[0]), int(cell[1])))
        return out

    def _aggregate_observation_confidence(self, cells: list[CellCoord]) -> float:
        vm = self.visibility_model
        if not cells:
            return 0.5
        scores: list[float] = []
        for cell in cells:
            status = vm.state.observation_status_map.get(cell, ObservationStatus.NEVER_SEEN)
            if status == ObservationStatus.SMOKE_OBSCURED:
                scores.append(0.55)
            elif status in (ObservationStatus.STALE_INFORMATION, ObservationStatus.NEVER_SEEN):
                scores.append(0.35)
            elif status in (ObservationStatus.OBSERVED_FIRE, ObservationStatus.OBSERVED_NO_FIRE):
                scores.append(0.9)
            else:
                scores.append(0.6)
        return sum(scores) / max(1, len(scores))

    def _nearby_uav_ids(self, uav: Any) -> list[str]:
        ids: list[str] = []
        for agent in uav.model.schedule.agents:
            if type(agent) is not agents_module.UAV or agent.unique_id == uav.unique_id:
                continue
            ids.append(str(agent.unique_id))
        return ids

    def _task_context(self) -> dict[str, Any]:
        st = self.uav_resource_model.by_uav_id.get(self.uav_id)
        if st is None:
            return {"role": None, "assigned_task": None}
        return {"role": st.current_role, "assigned_task": st.assigned_task}

    def _resource_snapshot(self) -> tuple[float, str, str]:
        st = self.uav_resource_model.by_uav_id.get(self.uav_id)
        if st is None:
            return 0.0, "", ""
        bl = st.battery_level
        level = float(bl) if bl is not None else 0.0
        bs = st.battery_status or ""
        cs = st.communication_status or ""
        return level, bs, cs

    def _battery_and_comm_from_uav(self, uav: Any) -> tuple[float, str, str]:
        """Prefer managed UAV battery fields; fall back to UAVResourceModel knowledge."""
        fb_level, fb_stat, fb_comm = self._resource_snapshot()
        raw_bl = getattr(uav, "battery_level", None)
        battery_level = float(raw_bl) if raw_bl is not None else fb_level
        raw_bs = getattr(uav, "battery_status", None)
        battery_status = (
            raw_bs
            if isinstance(raw_bs, str) and raw_bs.strip()
            else fb_stat
        )
        raw_cs = getattr(uav, "communication_status", None)
        communication_status = (
            raw_cs
            if isinstance(raw_cs, str) and raw_cs.strip()
            else fb_comm
        )
        return battery_level, battery_status, communication_status

    def collect_observation(self, uav: Any, current_time: Timestamp) -> LocalObservation:
        ts = float(current_time)
        cells = self._visible_cells(uav)
        fire_cells_list, smoke_cells_list = self._classify_cells(uav, cells)
        fire_set = set(fire_cells_list)
        smoke_set = set(smoke_cells_list)

        victims_visible = self._visible_victim_candidates(cells)
        victim_cells = {tuple(v["cell"]) for v in victims_visible}

        patch_sig: dict[CellCoord, tuple[bool, bool, str]] = {}
        for cell in cells:
            in_fire = cell in fire_set
            in_smoke = cell in smoke_set
            vk = self._cell_visibility_status_key(cell)
            patch_sig[cell] = (in_fire, in_smoke, vk)

        obs_confidence = self._aggregate_observation_confidence(cells)
        neg_obs = self._negative_observations(
            cells,
            fire_set,
            smoke_set,
            victim_cells,
            ts,
            base_confidence=max(0.2, min(0.95, obs_confidence * 0.85)),
        )

        confirmations = self._belief_confirmation_flags(uav, cells)
        raw_ig, norm_ig = self._compute_information_gain(cells, patch_sig, confirmations)

        uncertainty_cells = self._local_uncertainty_cells(cells)

        ix, iy = self._dir_to_delta(uav.selected_dir)
        intended_move: Cell = (ix, iy)

        prev_actual = getattr(uav, "_monitor_prev_actual_delta", (0, 0))
        prev_drift = getattr(uav, "_monitor_prev_drift_error", 0.0)
        actual_move: Cell = (int(prev_actual[0]), int(prev_actual[1]))

        batt_level, batt_stat, comm_stat = self._battery_and_comm_from_uav(uav)

        cx, cy = int(uav.pos[0]), int(uav.pos[1])
        current_position: Cell = (cx, cy)

        neg_typed: list[tuple[Cell, float, float]] = [
            ((int(c[0]), int(c[1])), conf, t) for c, conf, t in neg_obs
        ]

        fire_cells_t: list[Cell] = [(int(c[0]), int(c[1])) for c in fire_cells_list]
        smoke_cells_t: list[Cell] = [(int(c[0]), int(c[1])) for c in smoke_cells_list]

        confirmation_cells_t: list[Cell] = [(int(c[0]), int(c[1])) for c in confirmations]

        for cell in cells:
            self._cells_ever_seen.add(cell)
        self._last_patch_signature = dict(patch_sig)

        for cell in cells:
            self._prev_fov_cell_uncertain[cell] = self._is_visibility_uncertain(cell)

        conf_meta = float(obs_confidence)
        return LocalObservation(
            uav_id=self.uav_id,
            timestamp=ts,
            visible_fire_cells=fire_cells_t,
            visible_smoke_cells=smoke_cells_t,
            visible_victim_candidates=victims_visible,
            current_position=current_position,
            intended_move=intended_move,
            actual_move=actual_move,
            drift_error=float(prev_drift),
            battery_level=batt_level,
            battery_status=batt_stat,
            communication_status=comm_stat,
            nearby_uavs=self._nearby_uav_ids(uav),
            task_context=self._task_context(),
            negative_observations=neg_typed,
            raw_information_gain=float(raw_ig),
            normalized_information_gain=float(norm_ig),
            local_uncertainty_patch=uncertainty_cells,
            observation_confidence=conf_meta,
            belief_confirmation_flags=confirmation_cells_t,
            source="local_monitor",
            confidence=conf_meta,
        )

    def finalize_step_after_move(
        self,
        uav: Any,
        pos_before: CellCoord,
        pos_after: CellCoord,
        intended_delta: tuple[int, int],
    ) -> None:
        """Record actual delta and drift for this step; call before collect_observation for the same timestep."""
        ax = pos_after[0] - pos_before[0]
        ay = pos_after[1] - pos_before[1]
        actual = (ax, ay)
        target_x = pos_before[0] + intended_delta[0]
        target_y = pos_before[1] + intended_delta[1]
        drift = euclidean_distance(float(target_x), float(target_y), float(pos_after[0]), float(pos_after[1]))
        uav._monitor_prev_actual_delta = actual
        uav._monitor_prev_drift_error = float(drift)


def local_observation_to_dict(obs: LocalObservation) -> dict[str, Any]:
    """Optional dict view for debugging or legacy serialization."""
    from dataclasses import asdict

    return asdict(obs)
