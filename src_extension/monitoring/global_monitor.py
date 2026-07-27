"""Global monitoring: aggregate runtime knowledge and local UAV reports (observe-only).

No analysis, planning, or control—only structured snapshots for downstream consumers.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from common_fixed_variables import (
    HEIGHT,
    WIDTH,
    WIND_DIRECTION,
    normalize_wind_direction,
    wind_vector_from_direction,
)

from src_extension.knowledge.communication_model import CommunicationModel
from src_extension.knowledge.fire_runtime_model import FireRuntimeModel
from src_extension.knowledge.firefighter_model import FirefighterModel
from src_extension.knowledge.uav_resource_model import UAVResourceModel
from src_extension.knowledge.victim_runtime_model import VictimRuntimeModel
from src_extension.knowledge.visibility_model import VisibilityModel
from src_extension.knowledge.runtime_model_common import CellCoord

from .communication_monitor import CommunicationMonitor
from .environment_monitor import EnvironmentMonitor
from .firefighter_monitor import FirefighterMonitor
from .monitoring_interfaces import GlobalObservationSnapshot, LocalObservation


class GlobalMonitor:
    """Aggregate team-level and environment-level observation structures."""

    def __init__(
        self,
        fire_runtime_model: FireRuntimeModel,
        visibility_model: VisibilityModel,
        victim_runtime_model: VictimRuntimeModel,
        uav_resource_model: UAVResourceModel,
        communication_model: CommunicationModel,
        firefighter_model: FirefighterModel,
        communication_monitor: CommunicationMonitor,
        firefighter_monitor: FirefighterMonitor,
        environment_monitor: EnvironmentMonitor,
        uavs: list[Any],
    ) -> None:
        self.fire_runtime_model = fire_runtime_model
        self.visibility_model = visibility_model
        self.victim_runtime_model = victim_runtime_model
        self.uav_resource_model = uav_resource_model
        self.communication_model = communication_model
        self.firefighter_model = firefighter_model
        self.communication_monitor = communication_monitor
        self.firefighter_monitor = firefighter_monitor
        self.environment_monitor = environment_monitor
        self.uavs = uavs
        self._prev_victim_candidate_count = 0

    @staticmethod
    def _grid_cell_total() -> int:
        return max(1, int(HEIGHT) * int(WIDTH))

    def _aggregate_local_uav_reports(self) -> dict[str, Any]:
        total_raw_gain = 0.0
        norm_sum = 0.0
        n_with_obs = 0
        uncertain_cells_union: set[CellCoord] = set()

        for uav in self.uavs:
            obs = getattr(uav, "latest_local_observation", None)
            if isinstance(obs, LocalObservation):
                total_raw_gain += float(getattr(obs, "raw_information_gain", 0.0))
                norm_sum += float(getattr(obs, "normalized_information_gain", 0.0))
                n_with_obs += 1
                for cell in obs.local_uncertainty_patch:
                    uncertain_cells_union.add((int(cell[0]), int(cell[1])))
            elif isinstance(obs, dict):
                total_raw_gain += float(
                    obs.get("raw_information_gain", obs.get("information_gain", 0.0))
                )
                if "normalized_information_gain" in obs:
                    norm_sum += float(obs["normalized_information_gain"])
                    n_with_obs += 1
                patch = obs.get("local_uncertainty_patch") or []
                for entry in patch:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        uncertain_cells_union.add((int(entry[0]), int(entry[1])))
                    elif isinstance(entry, dict):
                        cell = entry.get("cell")
                        if isinstance(cell, (list, tuple)) and len(cell) >= 2:
                            uncertain_cells_union.add((int(cell[0]), int(cell[1])))

        vis = self.visibility_model
        vis_uncertain = vis.get_uncertain_regions()
        combined_uncertain = uncertain_cells_union | vis_uncertain
        n_union = len(combined_uncertain)

        observed = len(vis.state.visible_cells)
        total_cells = self._grid_cell_total()
        unobserved = max(0, total_cells - observed)

        denom_observed = max(1, observed)
        global_uncertainty_score = min(1.0, float(n_union) / float(denom_observed))

        return {
            "total_information_gain": float(total_raw_gain),
            "avg_normalized_information_gain": float(norm_sum) / float(max(1, n_with_obs)),
            "aggregated_uncertain_cell_count": int(n_union),
            "visibility_uncertain_count": int(len(vis_uncertain)),
            "local_union_uncertain_count": len(uncertain_cells_union),
            "coverage_observed_cell_count": int(observed),
            "coverage_total_cell_count": int(total_cells),
            "coverage_unobserved_cell_count": int(unobserved),
            "coverage_observed_fraction": float(observed) / float(total_cells),
            "coverage_unobserved_fraction": float(unobserved) / float(total_cells),
            "global_uncertainty_score": float(global_uncertainty_score),
        }

    def _fire_summary(self) -> dict[str, Any]:
        b = self.fire_runtime_model.belief
        prob_values = list(b.fire_probability_map.values())
        conf_values = list(b.fire_confidence_map.values())
        return {
            "estimated_burning_cells": [list(c) for c in b.estimated_burning_cells],
            "fire_front": [list(c) for c in b.estimated_fire_front_cells],
            "fire_probability_summary": {
                "mean": float(sum(prob_values) / max(1, len(prob_values))),
                "max": float(max(prob_values)) if prob_values else 0.0,
                "count": len(prob_values),
            },
            "confidence_summary": {
                "mean": float(sum(conf_values) / max(1, len(conf_values))),
                "min": float(min(conf_values)) if conf_values else 0.0,
                "count": len(conf_values),
            },
        }

    def _fire_belief_summary(self) -> dict[str, Any]:
        b = self.fire_runtime_model.belief
        prob_map = b.fire_probability_map
        conf_map = b.fire_confidence_map
        prob_values = list(prob_map.values())
        conf_values = list(conf_map.values())

        low_confidence_high_prob_cells = [
            list(cell)
            for cell, prob in prob_map.items()
            if float(prob) >= 0.6 and float(conf_map.get(cell, 0.0)) < 0.4
        ]
        uncertain_fire_regions = sum(1 for prob in prob_values if 0.3 < float(prob) < 0.7)

        return {
            "mean_probability": float(sum(prob_values) / max(1, len(prob_values))),
            "max_probability": float(max(prob_values)) if prob_values else 0.0,
            "mean_confidence": float(sum(conf_values) / max(1, len(conf_values))),
            "low_confidence_high_prob_cells": low_confidence_high_prob_cells,
            "uncertain_fire_regions": int(uncertain_fire_regions),
        }

    def _visibility_summary(self) -> dict[str, Any]:
        s = self.visibility_model.state
        finite_stale = [v for v in s.staleness_map.values() if v != float("inf")]
        return {
            "visible_regions": {
                "cell_count": len(s.visible_cells),
                "sample_cells": [list(c) for c in list(s.visible_cells)[:12]],
            },
            "smoke_regions": {
                "cell_count": len(s.smoke_obscured_cells),
                "sample_cells": [list(c) for c in list(s.smoke_obscured_cells)[:12]],
            },
            "staleness": {
                "mean": float(sum(finite_stale) / max(1, len(finite_stale))),
                "max": float(max(finite_stale)) if finite_stale else 0.0,
            },
            "uncertainty_regions": {
                "cell_count": len(s.unknown_or_uncertain_regions),
                "sample_cells": [list(c) for c in list(s.unknown_or_uncertain_regions)[:20]],
            },
        }

    def _uav_team_summary(self) -> dict[str, Any]:
        positions: dict[str, list[int]] = {}
        roles: dict[str, Any] = {}
        battery_levels: dict[str, Any] = {}
        drift_levels: dict[str, float] = {}
        uav_information_gain: dict[str, float] = {}
        local_issues: dict[str, list[str]] = {}

        for uav in self.uavs:
            uid = str(uav.unique_id)
            positions[uid] = [int(uav.pos[0]), int(uav.pos[1])]

            obs = getattr(uav, "latest_local_observation", None)
            issues: list[str] = []
            if isinstance(obs, LocalObservation):
                drift_levels[uid] = float(obs.drift_error)
                uav_information_gain[uid] = float(obs.normalized_information_gain)
                battery_levels[uid] = float(obs.battery_level)
                oc = obs.observation_confidence
                if oc < 0.45:
                    issues.append("low_observation_confidence")
                if obs.local_uncertainty_patch:
                    issues.append("local_uncertainty_non_empty")
            elif isinstance(obs, dict):
                drift_levels[uid] = float(obs.get("drift_error", 0.0))
                uav_information_gain[uid] = float(obs.get("normalized_information_gain", 0.0))
                oc = obs.get("observation_confidence")
                if oc is not None and float(oc) < 0.45:
                    issues.append("low_observation_confidence")
                if obs.get("local_uncertainty_patch"):
                    issues.append("local_uncertainty_non_empty")
            else:
                drift_levels[uid] = 0.0
                uav_information_gain[uid] = 0.0
            local_issues[uid] = issues

            if uid not in battery_levels:
                st = self.uav_resource_model.by_uav_id.get(uid)
                if st is not None:
                    battery_levels[uid] = st.battery_level
                else:
                    battery_levels[uid] = None

            st = self.uav_resource_model.by_uav_id.get(uid)
            if st is not None:
                roles[uid] = st.current_role
            else:
                roles[uid] = None

        return {
            "positions": positions,
            "roles": roles,
            "battery_levels": battery_levels,
            "drift_levels": drift_levels,
            "uav_information_gain": uav_information_gain,
            "total_information_gain": float(sum(uav_information_gain.values())),
            "local_issues": local_issues,
        }

    def _victim_summary(self) -> dict[str, Any]:
        snap = self.victim_runtime_model.snapshot()
        victims = snap.get("victims") or {}
        return {
            "victim_count": len(victims),
            "victims": victims,
            "catalog_provenance": snap.get("catalog_provenance"),
        }

    def _belief_gap_indicators(self) -> dict[str, Any]:
        prob_t, conf_t = 0.6, 0.4
        gaps: list[dict[str, Any]] = []
        b = self.fire_runtime_model.belief
        for cell, prob in b.fire_probability_map.items():
            conf = b.fire_confidence_map.get(cell, 0.0)
            if prob >= prob_t and conf < conf_t:
                gaps.append({"cell": list(cell), "fire_probability": float(prob), "confidence": float(conf)})
        return {
            "threshold_probability": prob_t,
            "threshold_confidence": conf_t,
            "cells": gaps[:50],
            "count": len(gaps),
        }

    def _information_sufficiency(self, agg: dict[str, Any]) -> str:
        gu = float(agg["global_uncertainty_score"])
        ig = float(agg["total_information_gain"])
        if gu >= 0.5 and ig < 3.0:
            return "LOW"
        if gu <= 0.3 and ig >= 5.0:
            return "HIGH"
        return "ADEQUATE"

    @staticmethod
    def _resolve_wind_observation(
        model: Any,
        current_time: float,
        env_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve wind spread direction for global monitoring (bridge → agent → config)."""
        ts = float(current_time)
        step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)

        bridge = getattr(model, "environment_bridge", None)
        if bridge is not None:
            get_summary = getattr(bridge, "get_wind_summary", None)
            if callable(get_summary):
                summary = get_summary()
                if isinstance(summary, dict) and summary.get("direction"):
                    direction = normalize_wind_direction(summary.get("direction"))
                    raw_vector = summary.get("vector")
                    if isinstance(raw_vector, (list, tuple)) and len(raw_vector) >= 2:
                        vector = (float(raw_vector[0]), float(raw_vector[1]))
                    else:
                        vector = wind_vector_from_direction(direction)
                    return {
                        "wind_direction": direction,
                        "wind_vector": vector,
                        "wind_source": str(summary.get("source", "environment_bridge")),
                        "wind_timestamp": float(summary.get("timestamp", ts)),
                        "observation_step": int(summary.get("step", step)),
                    }

        if isinstance(env_snapshot, dict):
            env_wind = env_snapshot.get("wind")
            if isinstance(env_wind, dict) and env_wind.get("direction"):
                direction = normalize_wind_direction(env_wind.get("direction"))
                return {
                    "wind_direction": direction,
                    "wind_vector": wind_vector_from_direction(direction),
                    "wind_source": str(env_snapshot.get("source", "environment_monitor")),
                    "wind_timestamp": float(env_snapshot.get("timestamp", ts)),
                    "observation_step": step,
                }

        wind_agent = getattr(model, "wind", None)
        if wind_agent is not None:
            direction = normalize_wind_direction(
                getattr(wind_agent, "wind_direction", WIND_DIRECTION)
            )
            return {
                "wind_direction": direction,
                "wind_vector": wind_vector_from_direction(direction),
                "wind_source": "fire_model",
                "wind_timestamp": ts,
                "observation_step": step,
            }

        direction = normalize_wind_direction(WIND_DIRECTION)
        return {
            "wind_direction": direction,
            "wind_vector": wind_vector_from_direction(direction),
            "wind_source": "config",
            "wind_timestamp": ts,
            "observation_step": step,
        }

    def classify_events(self, snapshot: GlobalObservationSnapshot) -> dict[str, Any]:
        """Classify event flags into structured groups (observe-only)."""
        low_battery_event = False
        critical_battery_event = False
        for uav in self.uavs:
            obs = getattr(uav, "latest_local_observation", None)
            if isinstance(obs, LocalObservation):
                st_b = (obs.battery_status or "").strip().lower()
                bl = float(obs.battery_level)
                if st_b == "critical" or bl <= 15.0:
                    critical_battery_event = True
                    low_battery_event = True
                    break
                if st_b == "low" or bl <= 30.0:
                    low_battery_event = True
                    break
                if bl > 0.0 and bl < 20.0:
                    low_battery_event = True
                    break

        communication_failure_event = False
        ms = snapshot.communication_summary.get("monitor_snapshot") or {}
        delivery_confidence = float(ms.get("delivery_confidence", 1.0))
        failed_n = int(ms.get("failed", 0))
        relay = bool(ms.get("relay_needed", False))
        if delivery_confidence < 0.25 or failed_n >= 2 or relay:
            communication_failure_event = True

        unc = snapshot.uncertainty_summary
        avg_norm = float(unc.get("avg_normalized_information_gain", 0.0))
        gu_score = float(unc.get("global_uncertainty_score", 0.0))
        information_collapse_event = avg_norm < 0.05 and gu_score > 0.6

        vc = int(snapshot.victim_summary.get("victim_count") or 0)
        new_victim_event = vc > self._prev_victim_candidate_count

        self._prev_victim_candidate_count = vc

        low_information_gain_event = avg_norm < 0.05

        return {
            "resource_events": {
                "low_battery": low_battery_event,
                "critical_battery": critical_battery_event,
            },
            "communication_events": {
                "failure": communication_failure_event,
            },
            "information_events": {
                "information_collapse": information_collapse_event,
                "low_information_gain": low_information_gain_event,
            },
            "mission_events": {
                "new_victim": new_victim_event,
            },
        }

    def collect_global_snapshot(self, model: Any, current_time: float) -> GlobalObservationSnapshot:
        ts = float(current_time)
        agg = self._aggregate_local_uav_reports()
        env_snapshot = self.environment_monitor.collect_environment_snapshot(model, ts)

        sufficiency = self._information_sufficiency(agg)
        belief_gap = self._belief_gap_indicators()

        uncertainty_summary = {
            "global_uncertainty_score": agg["global_uncertainty_score"],
            "aggregated_uncertain_cell_count": agg["aggregated_uncertain_cell_count"],
            "total_information_gain": agg["total_information_gain"],
            "avg_normalized_information_gain": agg["avg_normalized_information_gain"],
            "coverage_observed_fraction": agg["coverage_observed_fraction"],
            "coverage_unobserved_fraction": agg["coverage_unobserved_fraction"],
            "coverage_observed_cell_count": agg["coverage_observed_cell_count"],
            "coverage_total_cell_count": agg["coverage_total_cell_count"],
        }
        observed_cells = int(agg["coverage_observed_cell_count"])
        total_grid_cells = int(agg["coverage_total_cell_count"])
        stale_cells = int(
            sum(
                1
                for status in self.visibility_model.state.observation_status_map.values()
                if str(getattr(status, "value", status)) == "stale_information"
            )
        )
        fresh_cells = max(0, observed_cells - stale_cells)
        uncertainty_summary.update(
            {
                "coverage_ratio": float(observed_cells) / float(max(1, total_grid_cells)),
                "fresh_cells_ratio": float(fresh_cells) / float(max(1, observed_cells)),
                "stale_cells_ratio": float(stale_cells) / float(max(1, observed_cells)),
            }
        )

        conf_values = list(self.fire_runtime_model.belief.fire_confidence_map.values())
        uncertainty_summary["uncertainty_distribution"] = {
            "low": int(sum(1 for c in conf_values if float(c) > 0.7)),
            "medium": int(sum(1 for c in conf_values if 0.4 <= float(c) <= 0.7)),
            "high": int(sum(1 for c in conf_values if float(c) < 0.4)),
        }

        comm_snap = self.communication_model.snapshot()
        comm_status = self.communication_monitor.collect_snapshot(ts)
        communication_summary: dict[str, Any] = {
            **comm_snap,
            "monitor_snapshot": asdict(comm_status),
            "timestamp": ts,
            "source": "monitor",
            "confidence": float(getattr(comm_status, "confidence", 1.0)),
        }

        ff_snap = self.firefighter_model.snapshot()
        ff_units = self.firefighter_monitor.collect_snapshot(ts)
        firefighter_summary: dict[str, Any] = {
            **ff_snap,
            "monitor_units": [asdict(u) for u in ff_units],
            "timestamp": ts,
            "source": "monitor",
            "confidence": float(
                sum(float(getattr(u, "confidence", 1.0)) for u in ff_units) / max(1, len(ff_units))
            ),
        }

        fire_summary = self._fire_summary()
        env_fire_cells = {
            (int(c[0]), int(c[1])) for c in (env_snapshot.get("fire_cells") or []) if isinstance(c, list) and len(c) >= 2
        }
        env_smoke_cells = {
            (int(c[0]), int(c[1])) for c in (env_snapshot.get("smoke_cells") or []) if isinstance(c, list) and len(c) >= 2
        }
        observed_fire_cells = {
            cell
            for cell, status in self.visibility_model.state.observation_status_map.items()
            if str(getattr(status, "value", status)) == "observed_fire"
        }
        overlap = len(env_fire_cells & observed_fire_cells)
        fire_summary.update(
            {
                "env_burning_cells_count": int(len(env_fire_cells)),
                "env_smoke_cells_count": int(len(env_smoke_cells)),
                "env_fire_overlap_ratio": float(overlap) / float(max(1, len(env_fire_cells))),
            }
        )

        visibility_summary = self._visibility_summary()
        grid_total = self._grid_cell_total()
        visible_count = int(len(self.visibility_model.state.visible_cells))
        smoke_count = int(len(env_smoke_cells))
        visibility_summary.update(
            {
                "env_smoke_density": float(smoke_count) / float(max(1, grid_total)),
                "env_visibility_impact_score": float(smoke_count)
                / float(max(1, smoke_count + visible_count)),
            }
        )

        wind_obs = self._resolve_wind_observation(model, ts, env_snapshot)
        visibility_summary["wind_direction"] = wind_obs["wind_direction"]
        visibility_summary["wind_vector"] = list(wind_obs["wind_vector"])

        snapshot = GlobalObservationSnapshot(
            timestamp=ts,
            mission_time=ts,
            fire_summary=fire_summary,
            fire_belief_summary=self._fire_belief_summary(),
            visibility_summary=visibility_summary,
            uav_team_summary=self._uav_team_summary(),
            victim_summary=self._victim_summary(),
            firefighter_summary=firefighter_summary,
            communication_summary=communication_summary,
            uncertainty_summary=uncertainty_summary,
            information_sufficiency=sufficiency,
            belief_gap_indicators=belief_gap,
            event_flags={},
            wind_direction=str(wind_obs["wind_direction"]),
            wind_vector=wind_obs["wind_vector"],
            wind_source=str(wind_obs["wind_source"]),
            wind_timestamp=float(wind_obs["wind_timestamp"]),
            observation_step=int(wind_obs["observation_step"]),
        )

        flags = self.classify_events(snapshot)
        return replace(snapshot, event_flags=flags)
