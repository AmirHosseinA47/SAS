"""Managing system: local UAV analyzer (Step 6 skeleton).

Responsibility: interpret local structured knowledge and observations for
one UAV to produce LocalAnalysisResult (triggers and summaries for planning).

TODO: Implement private analyzers; pair with monitoring/planning as needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..knowledge.local_observation_model import LocalObservationModel
from ..knowledge.local_path_context_model import LocalPathContextModel
from ..knowledge.uav_resource_model import UAVResourceRuntimeState
from .analysis_results import LocalAnalysisResult
from .trigger_objects import (
    AdaptationTrigger,
    InformationTrigger,
    ResourceTrigger,
    SafetyTrigger,
    Scope,
    Severity,
    StructuredTrigger,
    UncertaintyTrigger,
)


@dataclass
class LocalUAVAnalyzer:
    """Interpretation step: local models → ``LocalAnalysisResult`` (no execution)."""

    low_battery_threshold: float = 30.0
    critical_battery_threshold: float = 15.0
    drift_warning_threshold: float = 1.0
    drift_critical_threshold: float = 2.0
    low_information_gain_threshold: float = 0.05
    low_confidence_threshold: float = 0.4

    def analyze(
        self,
        uav_id: str,
        local_observation_model: LocalObservationModel,
        local_path_context_model: LocalPathContextModel,
        uav_resource_state: UAVResourceRuntimeState,
        latest_local_observation: dict[str, Any],
        timestamp: float,
    ) -> LocalAnalysisResult:
        """Run local analysis sub-steps and assemble a ``LocalAnalysisResult``."""
        triggers: list[StructuredTrigger] = []
        resource_triggers, resource_risk_summary = self._analyze_local_resource(
            uav_id,
            local_observation_model,
            local_path_context_model,
            uav_resource_state,
            latest_local_observation,
            timestamp,
        )
        triggers.extend(resource_triggers)
        safety_triggers, safety_risk_summary = self._analyze_local_safety(
            uav_id,
            local_observation_model,
            local_path_context_model,
            uav_resource_state,
            latest_local_observation,
            timestamp,
        )
        triggers.extend(safety_triggers)
        unc_triggers, uncertainty_summary = self._analyze_local_uncertainty(
            uav_id,
            local_observation_model,
            local_path_context_model,
            uav_resource_state,
            latest_local_observation,
            timestamp,
        )
        triggers.extend(unc_triggers)
        info_triggers, information_summary = self._analyze_local_information(
            uav_id,
            local_observation_model,
            local_path_context_model,
            uav_resource_state,
            latest_local_observation,
            timestamp,
        )
        triggers.extend(info_triggers)
        path_triggers, path_quality_summary = self._analyze_local_path_quality(
            uav_id,
            local_observation_model,
            local_path_context_model,
            uav_resource_state,
            latest_local_observation,
            timestamp,
        )
        triggers.extend(path_triggers)
        risk_summary = "; ".join(
            s for s in (resource_risk_summary, safety_risk_summary) if s
        )
        explanation = "; ".join(
            s
            for s in (
                resource_risk_summary,
                safety_risk_summary,
                uncertainty_summary,
                information_summary,
                path_quality_summary,
            )
            if s
        )
        return LocalAnalysisResult(
            uav_id=uav_id,
            timestamp=timestamp,
            local_trigger_list=tuple(triggers),
            local_risk_summary=risk_summary,
            path_quality_summary=path_quality_summary,
            uncertainty_summary=uncertainty_summary,
            information_summary=information_summary,
            escalation_flags=(),
            explanation_context=explanation,
        )

    def _analyze_local_resource(
        self,
        uav_id: str,
        local_observation_model: LocalObservationModel,
        local_path_context_model: LocalPathContextModel,
        uav_resource_state: UAVResourceRuntimeState,
        latest_local_observation: dict[str, Any],
        timestamp: float,
    ) -> tuple[list[StructuredTrigger], str]:
        level, status = self._coalesce_battery_reading(
            latest_local_observation, uav_resource_state
        )
        reliability = uav_resource_state.local_plan_reliability
        time_left = uav_resource_state.predicted_remaining_useful_time

        triggers: list[StructuredTrigger] = []
        summary_parts: list[str] = []

        status_l = status.lower() if status else None
        is_critical = (level is not None and level <= self.critical_battery_threshold) or (
            status_l == "critical"
        )
        is_low = (not is_critical) and (
            (level is not None and level <= self.low_battery_threshold) or (status_l == "low")
        )

        def _bat_fmt() -> str:
            lv = f"{level:.1f}%" if level is not None else "unknown"
            st = status if status is not None else "unknown"
            return f"battery_level={lv}; battery_status={st}"

        if is_critical:
            triggers.append(
                ResourceTrigger(
                    trigger_type="CRITICAL_BATTERY",
                    severity=Severity.CRITICAL,
                    confidence=self._resource_confidence(reliability),
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="fail_safe_planner",
                    explanation_context=f"CRITICAL_BATTERY: {_bat_fmt()}",
                )
            )
            summary_parts.append(f"Critical battery ({_bat_fmt()})")
        elif is_low:
            triggers.append(
                ResourceTrigger(
                    trigger_type="LOW_BATTERY",
                    severity=Severity.HIGH,
                    confidence=self._resource_confidence(reliability),
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=f"LOW_BATTERY: {_bat_fmt()}",
                )
            )
            summary_parts.append(f"Low battery ({_bat_fmt()})")

        degrading = False
        if reliability is not None and float(reliability) < self.low_confidence_threshold:
            degrading = True
        if time_left is not None and float(time_left) < 120.0:
            degrading = True
        if degrading and (reliability is not None or time_left is not None):
            rel_s = f"{float(reliability):.2f}" if reliability is not None else "unknown"
            t_s = f"{float(time_left):.1f}s" if time_left is not None else "unknown"
            triggers.append(
                ResourceTrigger(
                    trigger_type="RESOURCE_DEGRADING",
                    severity=Severity.MEDIUM,
                    confidence=self._resource_confidence(reliability),
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"RESOURCE_DEGRADING: {_bat_fmt()}; "
                        f"local_plan_reliability={rel_s}; "
                        f"predicted_remaining_useful_time={t_s}"
                    ),
                )
            )
            summary_parts.append(
                f"Resource runway degrading (reliability={rel_s}, predicted_time={t_s}; {_bat_fmt()})"
            )

        return triggers, "; ".join(summary_parts) if summary_parts else ""

    @staticmethod
    def _coalesce_battery_reading(
        latest_local_observation: dict[str, Any],
        uav_resource_state: UAVResourceRuntimeState,
    ) -> tuple[float | None, str | None]:
        raw_level = latest_local_observation.get("battery_level")
        level: float | None
        try:
            level = float(raw_level) if raw_level is not None else None
        except (TypeError, ValueError):
            level = None
        if level is None and uav_resource_state.battery_level is not None:
            level = float(uav_resource_state.battery_level)

        st = latest_local_observation.get("battery_status")
        status = str(st) if st is not None else None
        if status is None and uav_resource_state.battery_status is not None:
            status = str(uav_resource_state.battery_status)
        return level, status

    @staticmethod
    def _resource_confidence(local_plan_reliability: float | None) -> float:
        if local_plan_reliability is None:
            return 0.75
        return max(0.0, min(1.0, float(local_plan_reliability)))

    def _analyze_local_safety(
        self,
        uav_id: str,
        local_observation_model: LocalObservationModel,
        local_path_context_model: LocalPathContextModel,
        uav_resource_state: UAVResourceRuntimeState,
        latest_local_observation: dict[str, Any],
        timestamp: float,
    ) -> tuple[list[StructuredTrigger], str]:
        triggers: list[StructuredTrigger] = []
        summary_parts: list[str] = []
        reliability = uav_resource_state.local_plan_reliability
        conf = self._resource_confidence(reliability)

        drift_obs, drift_state, risk_status = self._coalesce_drift_signals(
            latest_local_observation, uav_resource_state
        )
        drift_sev = self._drift_too_high_severity(drift_obs, drift_state, risk_status)
        if drift_sev is not None:
            planner = (
                "fail_safe_planner" if drift_sev == Severity.CRITICAL else "local_uav_path_planner"
            )
            obs_s = f"{float(drift_obs):.3f}" if drift_obs is not None else "unknown"
            st_s = f"{float(drift_state):.3f}" if drift_state is not None else "unknown"
            rs = risk_status if risk_status is not None else "unknown"
            triggers.append(
                SafetyTrigger(
                    trigger_type="DRIFT_TOO_HIGH",
                    severity=drift_sev,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner=planner,
                    explanation_context=(
                        f"DRIFT_TOO_HIGH: drift_error={obs_s}; drift_level={st_s}; "
                        f"local_risk_status={rs}"
                    ),
                )
            )
            summary_parts.append(
                f"Drift elevated (drift_error={obs_s}, drift_level={st_s}, risk={rs})"
            )

        coll = local_path_context_model.local_collision_risk_estimates
        congestion_risk = float(coll.get("congestion", 0.0) or 0.0) if coll else 0.0
        if congestion_risk > 0.0:
            coll_sev = (
                Severity.HIGH
                if congestion_risk >= 0.6
                else Severity.MEDIUM
            )
            triggers.append(
                SafetyTrigger(
                    trigger_type="COLLISION_RISK",
                    severity=coll_sev,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"COLLISION_RISK: congestion_pressure={congestion_risk:.3f}; "
                        f"path_context_stuck_count={local_path_context_model.stuck_count}"
                    ),
                )
            )
            summary_parts.append(f"Congestion risk elevated (pressure={congestion_risk:.3f})")
        elif coll:
            legacy_risks = {
                key: float(value)
                for key, value in coll.items()
                if key not in ("congestion", "local_risk")
            }
            if legacy_risks:
                max_risk = max(legacy_risks.values())
                if max_risk > 0.0:
                    coll_sev = (
                        Severity.HIGH
                        if max_risk >= 0.6
                        else Severity.MEDIUM
                        if max_risk >= 0.35
                        else Severity.MEDIUM
                    )
                    triggers.append(
                        SafetyTrigger(
                            trigger_type="COLLISION_RISK",
                            severity=coll_sev,
                            confidence=conf,
                            scope=Scope.LOCAL,
                            affected_entities=(uav_id,),
                            timestamp=timestamp,
                            recommended_planner="local_uav_path_planner",
                            explanation_context=(
                                f"COLLISION_RISK: max_local_collision_risk={max_risk:.3f}; "
                                f"keys={sorted(legacy_risks.keys())}"
                            ),
                        )
                    )
                    summary_parts.append(f"Collision risk elevated (max={max_risk:.3f})")

        if reliability is not None and float(reliability) < self.low_confidence_threshold:
            path_sev = Severity.HIGH if float(reliability) < 0.25 else Severity.MEDIUM
            triggers.append(
                SafetyTrigger(
                    trigger_type="LOCAL_PATH_UNRELIABLE",
                    severity=path_sev,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"LOCAL_PATH_UNRELIABLE: local_plan_reliability={float(reliability):.3f}"
                    ),
                )
            )
            summary_parts.append(f"Local path unreliable (reliability={float(reliability):.3f})")

        if local_path_context_model.stuck_count >= 3:
            triggers.append(
                SafetyTrigger(
                    trigger_type="UAV_STUCK",
                    severity=Severity.HIGH if local_path_context_model.stuck_count >= 5 else Severity.MEDIUM,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"UAV_STUCK: stuck_count={local_path_context_model.stuck_count}; "
                        f"path_safety_score={local_path_context_model.path_safety_score:.3f}"
                    ),
                )
            )
            summary_parts.append(
                f"UAV stuck (count={local_path_context_model.stuck_count})"
            )

        if local_path_context_model.oscillation_score >= 0.45:
            triggers.append(
                SafetyTrigger(
                    trigger_type="PATH_OSCILLATION",
                    severity=Severity.MEDIUM,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"PATH_OSCILLATION: oscillation_score="
                        f"{local_path_context_model.oscillation_score:.3f}; "
                        f"target_switch_count={local_path_context_model.target_switch_count}"
                    ),
                )
            )
            summary_parts.append(
                f"Path oscillation detected (score={local_path_context_model.oscillation_score:.3f})"
            )

        if local_path_context_model.local_risk_estimate >= 0.55:
            triggers.append(
                SafetyTrigger(
                    trigger_type="LOCAL_HAZARD_PRESSURE",
                    severity=Severity.HIGH if local_path_context_model.local_risk_estimate >= 0.75 else Severity.MEDIUM,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"LOCAL_HAZARD_PRESSURE: local_risk={local_path_context_model.local_risk_estimate:.3f}; "
                        f"nearby_fire={local_path_context_model.nearby_fire:.3f}; "
                        f"nearby_smoke={local_path_context_model.nearby_smoke:.3f}"
                    ),
                )
            )
            summary_parts.append(
                f"Local hazard pressure elevated (risk={local_path_context_model.local_risk_estimate:.3f})"
            )

        return triggers, "; ".join(summary_parts) if summary_parts else ""

    @staticmethod
    def _coalesce_drift_signals(
        latest_local_observation: dict[str, Any],
        uav_resource_state: UAVResourceRuntimeState,
    ) -> tuple[float | None, float | None, str | None]:
        raw_err = latest_local_observation.get("drift_error")
        drift_obs: float | None
        try:
            drift_obs = float(raw_err) if raw_err is not None else None
        except (TypeError, ValueError):
            drift_obs = None
        drift_state = (
            float(uav_resource_state.drift_level)
            if uav_resource_state.drift_level is not None
            else None
        )
        rs = uav_resource_state.local_risk_status
        risk = str(rs) if rs is not None else None
        return drift_obs, drift_state, risk

    def _drift_too_high_severity(
        self,
        drift_obs: float | None,
        drift_state: float | None,
        risk_status: str | None,
    ) -> Severity | None:
        """Return worst drift severity, or None if drift is acceptable."""
        r = (risk_status or "").lower()
        from_obs: Severity | None = None
        if drift_obs is not None:
            if drift_obs >= self.drift_critical_threshold:
                from_obs = Severity.CRITICAL
            elif drift_obs >= self.drift_warning_threshold:
                from_obs = Severity.HIGH

        from_state: Severity | None = None
        if drift_state is not None:
            if drift_state >= 0.7:
                from_state = Severity.HIGH
            elif drift_state >= 0.3:
                from_state = Severity.MEDIUM

        from_risk: Severity | None = None
        if "high_drift" in r:
            from_risk = Severity.HIGH
        elif "moderate_drift" in r or "moderate" in r:
            from_risk = Severity.MEDIUM

        candidates = [s for s in (from_obs, from_state, from_risk) if s is not None]
        if not candidates:
            return None
        order = (Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        return max(candidates, key=lambda s: order.index(s))

    def _analyze_local_uncertainty(
        self,
        uav_id: str,
        local_observation_model: LocalObservationModel,
        local_path_context_model: LocalPathContextModel,
        uav_resource_state: UAVResourceRuntimeState,
        latest_local_observation: dict[str, Any],
        timestamp: float,
    ) -> tuple[list[StructuredTrigger], str]:
        triggers: list[StructuredTrigger] = []
        summary_parts: list[str] = []
        reliability = uav_resource_state.local_plan_reliability
        base_conf = self._resource_confidence(reliability)

        merged_unc = self._merge_uncertainty_patches(
            local_observation_model.local_uncertainty_patch,
            latest_local_observation.get("local_uncertainty_patch"),
        )
        unc_vals = [float(v) for v in merged_unc.values()] if merged_unc else []
        mean_unc = sum(unc_vals) / len(unc_vals) if unc_vals else None
        max_unc = max(unc_vals) if unc_vals else None

        if (
            unc_vals
            and max_unc is not None
            and (max_unc >= 0.5 or (mean_unc is not None and mean_unc >= 0.35))
        ):
            sev = Severity.HIGH if max_unc >= 0.6 else Severity.MEDIUM
            m_s = f"{float(mean_unc):.3f}" if mean_unc is not None else "n/a"
            x_s = f"{float(max_unc):.3f}"
            conf = base_conf if mean_unc is None else max(0.0, min(1.0, 1.0 - float(mean_unc)))
            triggers.append(
                UncertaintyTrigger(
                    trigger_type="HIGH_LOCAL_UNCERTAINTY",
                    severity=sev,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"HIGH_LOCAL_UNCERTAINTY: merged_uncertainty_cells={len(merged_unc)}; "
                        f"mean_uncertainty={m_s}; max_uncertainty={x_s}"
                    ),
                )
            )
            summary_parts.append(
                f"High local uncertainty (cells={len(merged_unc)}, mean={m_s}, max={x_s})"
            )

        stale = self._local_observation_stale(local_observation_model, timestamp, base_conf)
        if stale is not None:
            age_s, mean_conf_s = stale
            triggers.append(
                UncertaintyTrigger(
                    trigger_type="STALE_LOCAL_INFORMATION",
                    severity=Severity.MEDIUM,
                    confidence=base_conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"STALE_LOCAL_INFORMATION: observation_age_s={age_s}; "
                        f"mean_local_confidence={mean_conf_s}"
                    ),
                )
            )
            summary_parts.append(f"Stale local information ({age_s}; confidence_mean={mean_conf_s})")

        return triggers, "; ".join(summary_parts) if summary_parts else ""

    @staticmethod
    def _merge_uncertainty_patches(
        model_patch: dict[Any, float],
        latest_patch: Any,
    ) -> dict[Any, float]:
        out: dict[Any, float] = dict(model_patch)
        if not isinstance(latest_patch, dict):
            return out
        for k, v in latest_patch.items():
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                continue
        return out

    def _local_observation_stale(
        self,
        local_observation_model: LocalObservationModel,
        timestamp: float,
        base_conf: float,
    ) -> tuple[str, str] | None:
        """Return (age_description, mean_conf_str) if stale signal is present."""
        parts_age: list[str] = []
        ts = local_observation_model.timestamp
        if ts is not None:
            age = max(0.0, float(timestamp) - float(ts))
            if age > 10.0:
                parts_age.append(f"age={age:.1f}s")

        mean_conf = self._mean_local_confidence(local_observation_model)
        conf_flag = mean_conf is not None and mean_conf < self.low_confidence_threshold
        mean_s = f"{float(mean_conf):.3f}" if mean_conf is not None else "n/a"

        if parts_age:
            return ("; ".join(parts_age), mean_s)
        if conf_flag:
            return ("confidence_below_threshold", mean_s)
        return None

    @staticmethod
    def _mean_local_confidence(local_observation_model: LocalObservationModel) -> float | None:
        patch = local_observation_model.local_confidence_patch
        if not patch:
            return None
        vals: list[float] = []
        for v in patch.values():
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue
        if not vals:
            return None
        return sum(vals) / len(vals)

    def _analyze_local_information(
        self,
        uav_id: str,
        local_observation_model: LocalObservationModel,
        local_path_context_model: LocalPathContextModel,
        uav_resource_state: UAVResourceRuntimeState,
        latest_local_observation: dict[str, Any],
        timestamp: float,
    ) -> tuple[list[StructuredTrigger], str]:
        triggers: list[StructuredTrigger] = []
        summary_parts: list[str] = []
        reliability = uav_resource_state.local_plan_reliability
        conf = self._resource_confidence(reliability)

        norm_ig = self._parse_optional_float(latest_local_observation.get("normalized_information_gain"))
        raw_ig = self._parse_optional_float(latest_local_observation.get("raw_information_gain"))

        uncertainty_patch = local_observation_model.local_uncertainty_patch
        has_uncertainty = bool(uncertainty_patch)
        visible_fire = local_observation_model.visible_fire_cells
        visible_smoke = local_observation_model.visible_smoke_cells
        negative_obs = local_observation_model.negative_local_observations

        low_norm = norm_ig is not None and norm_ig <= self.low_information_gain_threshold
        if low_norm:
            n_s = f"{float(norm_ig):.4f}" if norm_ig is not None else "unknown"
            triggers.append(
                InformationTrigger(
                    trigger_type="LOW_INFORMATION_GAIN",
                    severity=Severity.MEDIUM,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"LOW_INFORMATION_GAIN: normalized_information_gain={n_s} "
                        f"(threshold={self.low_information_gain_threshold})"
                    ),
                )
            )
            summary_parts.append(f"Low information gain (normalized={n_s})")

        raw_near_zero = raw_ig is not None and raw_ig <= self.low_information_gain_threshold
        norm_near_zero = norm_ig is not None and norm_ig <= self.low_information_gain_threshold
        gain_near_zero = raw_near_zero or (raw_ig is None and norm_near_zero)
        if gain_near_zero and has_uncertainty:
            r_s = f"{float(raw_ig):.4f}" if raw_ig is not None else "n/a"
            n_s = f"{float(norm_ig):.4f}" if norm_ig is not None else "n/a"
            triggers.append(
                InformationTrigger(
                    trigger_type="INFORMATION_INSUFFICIENT",
                    severity=Severity.HIGH,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"INFORMATION_INSUFFICIENT: raw_information_gain={r_s}; "
                        f"normalized_information_gain={n_s}; "
                        f"local_uncertainty_patch_cells={len(uncertainty_patch)}"
                    ),
                )
            )
            summary_parts.append(
                f"Information insufficient (raw={r_s}, normalized={n_s}, "
                f"uncertain_cells={len(uncertainty_patch)})"
            )

        no_visible_fire = len(visible_fire) == 0
        has_smoke_or_unknown = bool(visible_smoke) or has_uncertainty or bool(negative_obs)
        if no_visible_fire and has_smoke_or_unknown:
            triggers.append(
                InformationTrigger(
                    trigger_type="SEARCH_MODE_REQUIRED",
                    severity=Severity.MEDIUM,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        "SEARCH_MODE_REQUIRED: visible_fire_cells=0; "
                        f"visible_smoke_cells={len(visible_smoke)}; "
                        f"local_uncertainty_patch_cells={len(uncertainty_patch)}; "
                        f"negative_local_observations={len(negative_obs)}"
                    ),
                )
            )
            summary_parts.append(
                "Search mode suggested (no visible fire; smoke/uncertainty/negative evidence present)"
            )

        return triggers, "; ".join(summary_parts) if summary_parts else ""

    @staticmethod
    def _parse_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _analyze_local_path_quality(
        self,
        uav_id: str,
        local_observation_model: LocalObservationModel,
        local_path_context_model: LocalPathContextModel,
        uav_resource_state: UAVResourceRuntimeState,
        latest_local_observation: dict[str, Any],
        timestamp: float,
    ) -> tuple[list[StructuredTrigger], str]:
        triggers: list[StructuredTrigger] = []
        summary_parts: list[str] = []
        reliability = uav_resource_state.local_plan_reliability
        conf = self._resource_confidence(reliability)

        ps = local_path_context_model.path_stability_score
        ts_ = local_path_context_model.task_support_score
        bg = local_path_context_model.belief_gain_score
        nav = local_path_context_model.navigation_confidence
        movement = local_path_context_model.movement_stability

        ps_f = float(ps) if ps is not None else None
        ts_f = float(ts_) if ts_ is not None else None
        bg_f = float(bg) if bg is not None else None
        nav_f = float(nav) if nav is not None else None
        movement_f = float(movement) if movement is not None else None
        if movement_f is None and ps_f is not None:
            movement_f = ps_f
        if nav_f is None and bg_f is not None:
            nav_f = bg_f

        if ps_f is not None and ps_f < self.low_confidence_threshold:
            triggers.append(
                AdaptationTrigger(
                    trigger_type="LOW_PATH_STABILITY",
                    severity=Severity.HIGH if ps_f < 0.25 else Severity.MEDIUM,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"LOW_PATH_STABILITY: path_stability_score={ps_f:.3f}; "
                        f"movement_stability={movement_f if movement_f is not None else 'n/a'}; "
                        f"stuck_count={local_path_context_model.stuck_count}; "
                        f"belief_gain_score={bg_f if bg_f is not None else 'n/a'}"
                    ),
                )
            )
            summary_parts.append(f"Low path stability (score={ps_f:.3f})")

        if nav_f is not None and nav_f < self.low_confidence_threshold:
            triggers.append(
                AdaptationTrigger(
                    trigger_type="LOW_NAVIGATION_CONFIDENCE",
                    severity=Severity.HIGH if nav_f < 0.25 else Severity.MEDIUM,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"LOW_NAVIGATION_CONFIDENCE: navigation_confidence={nav_f:.3f}; "
                        f"path_safety_score={local_path_context_model.path_safety_score:.3f}"
                    ),
                )
            )
            summary_parts.append(f"Low navigation confidence (score={nav_f:.3f})")

        if ts_f is not None and ts_f < self.low_confidence_threshold:
            sev = Severity.HIGH
            if bg_f is not None and bg_f >= self.low_confidence_threshold:
                sev = Severity.MEDIUM
            triggers.append(
                AdaptationTrigger(
                    trigger_type="LOW_TASK_SUPPORT",
                    severity=sev,
                    confidence=conf,
                    scope=Scope.LOCAL,
                    affected_entities=(uav_id,),
                    timestamp=timestamp,
                    recommended_planner="local_uav_path_planner",
                    explanation_context=(
                        f"LOW_TASK_SUPPORT: task_support_score={ts_f:.3f}; "
                        f"belief_gain_score={bg_f if bg_f is not None else 'n/a'}"
                    ),
                )
            )
            summary_parts.append(f"Low task support (score={ts_f:.3f})")

        return triggers, "; ".join(summary_parts) if summary_parts else ""
