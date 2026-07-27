"""Managing system: global analyzer.

**Responsibility:** interpret the shared operational picture and related
snapshots/models to produce ``GlobalAnalysisResult`` (fleet-level triggers and
summaries for planning).

Not allowed here: mutating managed operational state, executing UAV
actions, sending messages, or emitting planner decisions only analysis
outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..knowledge.shared_operational_picture import SharedOperationalPicture
from .analysis_results import GlobalAnalysisResult
from .trigger_objects import (
    AdaptationTrigger,
    CommunicationTrigger,
    InformationTrigger,
    RescueTrigger,
    ResourceTrigger,
    SafetyTrigger,
    Scope,
    Severity,
    StructuredTrigger,
    UncertaintyTrigger,
)


@dataclass
class GlobalAnalyzer:
    """Interpretation step: fused knowledge → ``GlobalAnalysisResult`` (no execution)."""

    fire_probability_threshold: float = 0.7
    low_confidence_threshold: float = 0.4
    high_uncertainty_threshold: float = 0.6
    low_information_gain_threshold: float = 0.05
    communication_critical_threshold: float = 0.25
    stale_information_threshold: float = 10.0
    low_battery_threshold: float = 30.0
    critical_battery_threshold: float = 15.0
    previous_uncertainty_score: float | None = field(default=None, repr=False)
    previous_fire_front_count: int | None = field(default=None, repr=False)
    previous_predicted_spread_bias: Any = field(default=None, repr=False)
    previous_delivery_confidence: float | None = field(default=None, repr=False)
    previous_mean_battery: float | None = field(default=None, repr=False)

    def analyze(
        self,
        shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> GlobalAnalysisResult:
        """Run global analysis sub-steps and assemble a ``GlobalAnalysisResult``."""
        triggers: list[StructuredTrigger] = []
        trend_baseline = (
            self.previous_uncertainty_score,
            self.previous_fire_front_count,
            self.previous_delivery_confidence,
            self.previous_mean_battery,
        )
        triggers.extend(
            self._analyze_mission_quality(
                shared_operational_picture, global_snapshot, runtime_models, timestamp
            )
        )
        triggers.extend(
            self._analyze_uncertainty(
                shared_operational_picture, global_snapshot, runtime_models, timestamp
            )
        )
        triggers.extend(
            self._analyze_information_sufficiency(
                shared_operational_picture, global_snapshot, runtime_models, timestamp
            )
        )
        triggers.extend(
            self._analyze_resource_status(
                shared_operational_picture, global_snapshot, runtime_models, timestamp
            )
        )
        triggers.extend(
            self._analyze_safety(
                shared_operational_picture, global_snapshot, runtime_models, timestamp
            )
        )
        triggers.extend(
            self._analyze_fire_evolution(
                shared_operational_picture, global_snapshot, runtime_models, timestamp
            )
        )
        triggers.extend(
            self._analyze_communication(
                shared_operational_picture, global_snapshot, runtime_models, timestamp
            )
        )
        triggers.extend(
            self._analyze_rescue_feasibility(
                shared_operational_picture, global_snapshot, runtime_models, timestamp
            )
        )
        triggers.extend(
            self._analyze_stability(
                shared_operational_picture, global_snapshot, runtime_models, timestamp
            )
        )
        triggers.extend(
            self._analyze_trends(
                shared_operational_picture,
                global_snapshot,
                runtime_models,
                timestamp,
                trend_baseline,
            )
        )
        wind_context = self._wind_explanation_context(
            shared_operational_picture, global_snapshot
        )
        return GlobalAnalysisResult(
            timestamp=timestamp,
            trigger_list=tuple(triggers),
            system_health_summary="",
            risk_flags=(),
            priority_updates=(),
            fail_safe_flags=(),
            uncertainty_summary="",
            information_summary="",
            trend_summary="",
            explanation_context=wind_context,
        )

    @staticmethod
    def _wind_explanation_context(
        shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
    ) -> str:
        """Non-trigger wind metadata for planners/execution (spread direction)."""
        direction = global_snapshot.get("wind_direction")
        vector = global_snapshot.get("wind_vector")
        if direction is None:
            layers = getattr(shared_operational_picture, "layers", None)
            if isinstance(layers, dict):
                env_layer = layers.get("environment")
                if isinstance(env_layer, dict):
                    wind = env_layer.get("wind")
                    if isinstance(wind, dict):
                        direction = wind.get("direction")
                        vector = wind.get("vector")
        if not direction:
            return ""
        vector_s = vector if vector is not None else "unknown"
        return (
            f"environment_wind spread_direction={direction} "
            f"spread_vector={vector_s}"
        )

    def _analyze_mission_quality(
        self,
        _shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> list[StructuredTrigger]:
        prob, conf, last_obs = self._merged_fire_maps(runtime_models, global_snapshot)
        high_pri = {k: p for k, p in prob.items() if p >= self.fire_probability_threshold}
        triggers: list[StructuredTrigger] = []
        mean_conf_hp = self._mean_map_values(conf, high_pri.keys()) if high_pri else None

        if high_pri:
            conf_hp = mean_conf_hp if mean_conf_hp is not None else 0.5
            sev = Severity.HIGH if len(high_pri) >= 5 else Severity.MEDIUM
            triggers.append(
                AdaptationTrigger(
                    trigger_type="HIGH_PRIORITY_FIRE_REGION",
                    severity=sev,
                    confidence=max(0.0, min(1.0, conf_hp)),
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="global_mission_planner",
                    explanation_context=(
                        f"HIGH_PRIORITY_FIRE_REGION: cells={len(high_pri)}; "
                        f"fire_probability_threshold={self.fire_probability_threshold}"
                    ),
                )
            )

        stale_gap = False
        stale_time = False
        for k in high_pri:
            c_v = conf.get(k)
            if c_v is not None and float(c_v) < self.low_confidence_threshold:
                stale_gap = True
            lt = last_obs.get(k)
            if lt is not None and (timestamp - float(lt)) > self.stale_information_threshold:
                stale_time = True
        if high_pri and (stale_gap or stale_time):
            stale_conf = mean_conf_hp if mean_conf_hp is not None else 0.4
            triggers.append(
                InformationTrigger(
                    trigger_type="STALE_HIGH_PRIORITY_REGION",
                    severity=Severity.HIGH if stale_gap and stale_time else Severity.MEDIUM,
                    confidence=max(0.0, min(1.0, stale_conf)),
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="global_mission_planner",
                    explanation_context=(
                        "STALE_HIGH_PRIORITY_REGION: "
                        f"belief_gap={stale_gap}; observation_stale={stale_time}; "
                        f"high_priority_cells={len(high_pri)}"
                    ),
                )
            )

        unknown = self._unknown_regions_from_snapshot(global_snapshot)
        n_unknown = len(unknown)
        n_prob = len([p for p in prob.values() if p > 0.05])
        if n_unknown > 0:
            denom = n_unknown + max(n_prob, 1)
            unknown_ratio = n_unknown / float(denom)
            if unknown_ratio >= self.high_uncertainty_threshold or (
                n_prob == 0 and n_unknown >= 3
            ):
                triggers.append(
                    InformationTrigger(
                        trigger_type="POOR_FIRE_COVERAGE",
                        severity=Severity.HIGH if unknown_ratio >= 0.75 else Severity.MEDIUM,
                        confidence=max(0.0, min(1.0, 1.0 - unknown_ratio)),
                        scope=Scope.GLOBAL,
                        affected_entities=("fleet",),
                        timestamp=timestamp,
                        recommended_planner="global_mission_planner",
                        explanation_context=(
                            f"POOR_FIRE_COVERAGE: unknown_regions={n_unknown}; "
                            f"low_confidence_fire_cells={n_prob}; "
                            f"unknown_ratio={unknown_ratio:.3f}"
                        ),
                    )
                )

        return triggers

    @staticmethod
    def _unwrap_summary_layer(blob: Any) -> dict[str, Any]:
        if not isinstance(blob, dict):
            return {}
        inner = blob.get("value", blob)
        return inner if isinstance(inner, dict) else {}

    def _merged_fire_maps(
        self,
        runtime_models: dict[str, Any],
        global_snapshot: dict[str, Any],
    ) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
        prob: dict[str, float] = {}
        conf: dict[str, float] = {}
        last_obs: dict[str, float] = {}
        fr = runtime_models.get("fire_runtime_model")
        if fr is not None:
            prob.update(self._coerce_float_map(getattr(fr, "fire_probability_map", None)))
            conf.update(self._coerce_float_map(getattr(fr, "fire_confidence_map", None)))
            last_obs.update(self._coerce_float_map(getattr(fr, "last_observed_fire_time", None)))
        fb = self._unwrap_summary_layer(global_snapshot.get("fire_belief_summary"))
        prob.update(self._coerce_float_map(fb.get("fire_probability_map")))
        conf.update(self._coerce_float_map(fb.get("fire_confidence_map")))
        last_obs.update(self._coerce_float_map(fb.get("last_observed_fire_time")))
        return prob, conf, last_obs

    @staticmethod
    def _coerce_float_map(raw: Any) -> dict[str, float]:
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in raw.items():
            try:
                out[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
        return out

    @staticmethod
    def _mean_map_values(full: dict[str, float], keys: Any) -> float | None:
        vals = [float(full[k]) for k in keys if k in full]
        if not vals:
            return None
        return sum(vals) / len(vals)

    @staticmethod
    def _unknown_regions_from_snapshot(global_snapshot: dict[str, Any]) -> list[Any]:
        u = GlobalAnalyzer._unwrap_summary_layer(global_snapshot.get("uncertainty_summary"))
        regions = u.get("unknown_or_uncertain_regions")
        if isinstance(regions, list):
            return regions
        return []

    def _analyze_uncertainty(
        self,
        shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> list[StructuredTrigger]:
        triggers: list[StructuredTrigger] = []
        vm = runtime_models.get("visibility_model")

        snap_u = self._unwrap_summary_layer(global_snapshot.get("uncertainty_summary"))
        sop_raw = shared_operational_picture.uncertainty_summary
        sop_u = (
            self._unwrap_summary_layer(sop_raw)
            if isinstance(sop_raw, dict)
            else {}
        )
        merged_inner: dict[str, Any] = dict(snap_u)
        for k, v in sop_u.items():
            if k not in merged_inner:
                merged_inner[k] = v

        rus = getattr(vm, "region_uncertainty_score", None) if vm is not None else None
        region_agg, region_max = self._region_uncertainty_stats(rus)

        stale_vm = self._coerce_float_map(getattr(vm, "staleness_map", None)) if vm is not None else {}
        stale_snap = self._coerce_float_map(
            snap_u.get("staleness_map") if isinstance(snap_u.get("staleness_map"), dict) else {}
        )
        stale_sop = self._coerce_float_map(
            sop_u.get("staleness_map") if isinstance(sop_u.get("staleness_map"), dict) else {}
        )
        stale_map = dict(stale_snap)
        stale_map.update(stale_sop)
        stale_map.update(stale_vm)
        stale_mean = sum(stale_map.values()) / len(stale_map) if stale_map else None

        obs_map = getattr(vm, "observation_status_map", None) if vm is not None else None
        stale_obs_ratio = self._stale_observation_ratio(obs_map)

        score_candidates: list[float] = []
        if region_agg is not None:
            score_candidates.append(float(region_agg))
        if region_max is not None:
            score_candidates.append(float(region_max))
        if stale_mean is not None:
            score_candidates.append(float(stale_mean))
        current_score = max(score_candidates) if score_candidates else None

        conf_hint = 1.0 - (current_score if current_score is not None else 0.0)
        conf_hint = max(0.0, min(1.0, conf_hint))

        if current_score is not None and current_score >= self.high_uncertainty_threshold:
            triggers.append(
                UncertaintyTrigger(
                    trigger_type="HIGH_UNCERTAINTY_REGION",
                    severity=Severity.HIGH if current_score >= 0.8 else Severity.MEDIUM,
                    confidence=conf_hint,
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="global_mission_planner",
                    explanation_context=(
                        f"HIGH_UNCERTAINTY_REGION: aggregate={current_score:.3f}; "
                        f"threshold={self.high_uncertainty_threshold}"
                    ),
                )
            )

        prev = self.previous_uncertainty_score
        if (
            prev is not None
            and current_score is not None
            and current_score > prev + 0.01
        ):
            triggers.append(
                UncertaintyTrigger(
                    trigger_type="UNCERTAINTY_INCREASING",
                    severity=Severity.MEDIUM,
                    confidence=conf_hint,
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="global_mission_planner",
                    explanation_context=(
                        f"UNCERTAINTY_INCREASING: previous={prev:.3f}; current={current_score:.3f}"
                    ),
                )
            )

        stale_signal = False
        if stale_mean is not None and stale_mean >= self.high_uncertainty_threshold:
            stale_signal = True
        if stale_obs_ratio is not None and stale_obs_ratio >= 0.5:
            stale_signal = True
        if stale_map:
            if any(v >= self.stale_information_threshold for v in stale_map.values()):
                stale_signal = True
        if stale_signal:
            sm = f"{stale_mean:.3f}" if stale_mean is not None else "n/a"
            sor = f"{stale_obs_ratio:.3f}" if stale_obs_ratio is not None else "n/a"
            vm_local = vm is not None and (bool(stale_vm) or obs_map)
            scope_stale = Scope.LOCAL if vm_local else Scope.GLOBAL
            planner_stale = (
                "local_uav_path_planner" if vm_local else "global_mission_planner"
            )
            triggers.append(
                UncertaintyTrigger(
                    trigger_type="STALE_INFORMATION",
                    severity=(
                        Severity.HIGH
                        if stale_mean is not None and stale_mean >= 0.75
                        else Severity.MEDIUM
                    ),
                    confidence=max(0.0, min(1.0, 1.0 - (stale_mean or 0.0))),
                    scope=scope_stale,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner=planner_stale,
                    explanation_context=(
                        f"STALE_INFORMATION: staleness_mean={sm}; stale_observation_ratio={sor}; "
                        f"staleness_cells={len(stale_map)}"
                    ),
                )
            )

        if current_score is not None:
            self.previous_uncertainty_score = float(current_score)
        elif prev is None and stale_mean is not None:
            self.previous_uncertainty_score = float(stale_mean)

        return triggers

    @staticmethod
    def _region_uncertainty_stats(rus: Any) -> tuple[float | None, float | None]:
        if isinstance(rus, dict):
            vals = []
            for v in rus.values():
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    continue
            if not vals:
                return None, None
            return sum(vals) / len(vals), max(vals)
        if rus is None:
            return None, None
        try:
            x = float(rus)
            return x, x
        except (TypeError, ValueError):
            return None, None

    @staticmethod
    def _stale_observation_ratio(obs_map: Any) -> float | None:
        if not isinstance(obs_map, dict) or not obs_map:
            return None
        stale_like = 0
        total = 0
        for v in obs_map.values():
            total += 1
            s = str(v).lower()
            if "stale" in s or "unknown" in s or "old" in s:
                stale_like += 1
        if total == 0:
            return None
        return stale_like / float(total)

    def _analyze_information_sufficiency(
        self,
        _shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> list[StructuredTrigger]:
        triggers: list[StructuredTrigger] = []

        unc_inner = self._unwrap_summary_layer(global_snapshot.get("uncertainty_summary"))
        total_gain = self._parse_optional_float(unc_inner.get("total_information_gain"))
        if total_gain is None:
            total_gain = self._parse_optional_float(
                (global_snapshot.get("uncertainty_summary") or {}).get("total_information_gain")
                if isinstance(global_snapshot.get("uncertainty_summary"), dict)
                else None
            )

        suff = global_snapshot.get("information_sufficiency")
        suff_score = self._information_sufficiency_score(suff)

        unk = unc_inner.get("unknown_or_uncertain_regions")
        unk_n = len(unk) if isinstance(unk, list) else 0
        stale_m = self._mean_float_values(self._coerce_float_map(unc_inner.get("staleness_map")))
        high_unc = unk_n >= 5 or (
            stale_m is not None and stale_m >= self.high_uncertainty_threshold
        )

        low_gain = (
            total_gain is not None and total_gain <= self.low_information_gain_threshold
        ) or (
            total_gain is None
            and suff_score is not None
            and suff_score < self.low_confidence_threshold
        )

        bg = global_snapshot.get("belief_gap_indicators")
        critical_collapse = self._belief_gap_critical(bg, suff_score, total_gain)

        planner_info = "fail_safe_planner" if critical_collapse else "global_mission_planner"
        conf = (
            max(0.0, min(1.0, float(total_gain)))
            if total_gain is not None
            else (suff_score if suff_score is not None else 0.5)
        )

        if low_gain:
            triggers.append(
                InformationTrigger(
                    trigger_type="LOW_INFORMATION_GAIN",
                    severity=Severity.CRITICAL if critical_collapse else Severity.MEDIUM,
                    confidence=conf,
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner=planner_info,
                    explanation_context=self._info_explain(
                        "LOW_INFORMATION_GAIN",
                        total_gain,
                        suff_score,
                        critical_collapse,
                        runtime_models,
                        timestamp,
                    ),
                )
            )

        if low_gain and high_unc:
            triggers.append(
                InformationTrigger(
                    trigger_type="INFORMATION_INSUFFICIENT",
                    severity=Severity.CRITICAL if critical_collapse else Severity.HIGH,
                    confidence=max(0.0, min(1.0, 1.0 - (stale_m if stale_m is not None else 0.5))),
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner=planner_info,
                    explanation_context=(
                        f"INFORMATION_INSUFFICIENT: total_information_gain={total_gain}; "
                        f"unknown_regions={unk_n}; staleness_mean={stale_m}; "
                        f"critical_collapse={critical_collapse}"
                    ),
                )
            )

        prob, _, _ = self._merged_fire_maps(runtime_models, global_snapshot)
        high_belief = any(p >= self.fire_probability_threshold for p in prob.values())
        state_inner = self._unwrap_summary_layer(global_snapshot.get("fire_state_summary"))
        burning = state_inner.get("estimated_burning_cells")
        visible_empty = isinstance(burning, list) and len(burning) == 0
        fb_inner = self._unwrap_summary_layer(global_snapshot.get("fire_belief_summary"))
        confirmed = fb_inner.get("confirmed_fire_cells")
        if isinstance(confirmed, list) and len(confirmed) > 0:
            visible_empty = False
        if visible_empty and high_belief:
            triggers.append(
                InformationTrigger(
                    trigger_type="SEARCH_MODE_REQUIRED",
                    severity=Severity.HIGH if critical_collapse else Severity.MEDIUM,
                    confidence=max(0.0, min(1.0, max(prob.values()) if prob else 0.5)),
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="global_mission_planner",
                    explanation_context=self._info_explain(
                        "SEARCH_MODE_REQUIRED",
                        total_gain,
                        suff_score,
                        critical_collapse,
                        runtime_models,
                        timestamp,
                        extra=f"high_belief_cells={sum(1 for p in prob.values() if p >= self.fire_probability_threshold)}",
                    ),
                )
            )

        return triggers

    @staticmethod
    def _parse_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _information_sufficiency_score(raw: Any) -> float | None:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, dict):
            for key in ("score", "sufficiency_score", "value", "information_sufficiency"):
                if key in raw:
                    v = GlobalAnalyzer._parse_optional_float(raw.get(key))
                    if v is not None:
                        return v
        return None

    @staticmethod
    def _mean_float_values(m: dict[str, float]) -> float | None:
        if not m:
            return None
        vals = list(m.values())
        return sum(vals) / len(vals)

    @staticmethod
    def _belief_gap_critical(
        belief_gap: Any,
        suff_score: float | None,
        total_gain: float | None,
    ) -> bool:
        if isinstance(belief_gap, list) and len(belief_gap) >= 3:
            return True
        if isinstance(belief_gap, dict) and len(belief_gap) >= 3:
            return True
        if suff_score is not None and suff_score < 0.15:
            return True
        if total_gain is not None and total_gain < 0.01:
            return True
        return False

    def _info_explain(
        self,
        kind: str,
        total_gain: float | None,
        suff_score: float | None,
        critical_collapse: bool,
        runtime_models: dict[str, Any],
        timestamp: float,
        extra: str | None = None,
    ) -> str:
        parts = [
            f"{kind}: total_information_gain={total_gain}; information_sufficiency={suff_score}; "
            f"critical_collapse={critical_collapse}"
        ]
        if extra:
            parts.append(extra)
        fr = runtime_models.get("fire_runtime_model")
        fn = getattr(fr, "get_best_search_target", None) if fr is not None else None
        if callable(fn):
            tgt: Any = None
            try:
                tgt = fn(timestamp=float(timestamp))
            except TypeError:
                try:
                    tgt = fn()
                except TypeError:
                    tgt = None
            if tgt is not None:
                parts.append(f"get_best_search_target={tgt!r}")
        return "; ".join(parts)

    def _analyze_resource_status(
        self,
        _shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> list[StructuredTrigger]:
        triggers: list[StructuredTrigger] = []
        urm = runtime_models.get("uav_resource_model")
        by_uav: dict[str, Any] = {}
        if urm is not None:
            raw_by = getattr(urm, "by_uav_id", None)
            if isinstance(raw_by, dict):
                by_uav = dict(raw_by)

        snap_bat = self._uav_team_battery_levels(global_snapshot)
        uav_ids = sorted(set(by_uav.keys()) | set(snap_bat.keys()))
        critical_ids: list[str] = []

        for uid in uav_ids:
            st = by_uav.get(uid)
            level = snap_bat.get(uid)
            if level is None and st is not None:
                level = getattr(st, "battery_level", None)
            if level is not None:
                try:
                    level_f = float(level)
                except (TypeError, ValueError):
                    level_f = None
            else:
                level_f = None

            status = getattr(st, "battery_status", None) if st is not None else None
            status_l = str(status).lower() if status is not None else None

            rel = getattr(st, "local_plan_reliability", None) if st is not None else None
            prut = getattr(st, "predicted_remaining_useful_time", None) if st is not None else None
            conf = self._clamp01_float(rel) if rel is not None else 0.75

            is_crit = (level_f is not None and level_f <= self.critical_battery_threshold) or (
                status_l == "critical"
            )
            is_low = (not is_crit) and (
                (level_f is not None and level_f <= self.low_battery_threshold)
                or (status_l == "low")
            )

            def _bat_txt() -> str:
                lv = f"{level_f:.1f}%" if level_f is not None else "unknown"
                stt = status if status is not None else "unknown"
                return f"battery_level={lv}; battery_status={stt}"

            if is_crit:
                critical_ids.append(uid)
                triggers.append(
                    ResourceTrigger(
                        trigger_type="CRITICAL_BATTERY",
                        severity=Severity.CRITICAL,
                        confidence=conf,
                        scope=Scope.GLOBAL,
                        affected_entities=(uid,),
                        timestamp=timestamp,
                        recommended_planner="fail_safe_planner",
                        explanation_context=f"CRITICAL_BATTERY uav={uid}: {_bat_txt()}",
                    )
                )
            elif is_low:
                triggers.append(
                    ResourceTrigger(
                        trigger_type="LOW_BATTERY",
                        severity=Severity.HIGH,
                        confidence=conf,
                        scope=Scope.GLOBAL,
                        affected_entities=(uid,),
                        timestamp=timestamp,
                        recommended_planner="global_mission_planner",
                        explanation_context=f"LOW_BATTERY uav={uid}: {_bat_txt()}",
                    )
                )

            degrading = False
            if rel is not None and float(rel) < self.low_confidence_threshold:
                degrading = True
            if prut is not None and float(prut) < 120.0:
                degrading = True
            if degrading and (rel is not None or prut is not None):
                pr_s = f"{float(prut):.1f}" if prut is not None else "n/a"
                rel_s = f"{float(rel):.3f}" if rel is not None else "n/a"
                triggers.append(
                    ResourceTrigger(
                        trigger_type="RESOURCE_DEGRADING",
                        severity=Severity.MEDIUM,
                        confidence=conf,
                        scope=Scope.GLOBAL,
                        affected_entities=(uid,),
                        timestamp=timestamp,
                        recommended_planner="global_mission_planner",
                        explanation_context=(
                            f"RESOURCE_DEGRADING uav={uid}: {_bat_txt()}; "
                            f"local_plan_reliability={rel_s}; predicted_remaining_useful_time={pr_s}"
                        ),
                    )
                )

        if len(critical_ids) >= 2:
            triggers.append(
                ResourceTrigger(
                    trigger_type="RESOURCE_DEGRADING",
                    severity=Severity.CRITICAL,
                    confidence=0.5,
                    scope=Scope.GLOBAL,
                    affected_entities=tuple(sorted(critical_ids)),
                    timestamp=timestamp,
                    recommended_planner="fail_safe_planner",
                    explanation_context=(
                        "RESOURCE_DEGRADING (fleet): multiple_critical_battery_uavs="
                        f"{','.join(sorted(critical_ids))}"
                    ),
                )
            )

        return triggers

    @staticmethod
    def _uav_team_battery_levels(global_snapshot: dict[str, Any]) -> dict[str, float]:
        out: dict[str, float] = {}
        raw = global_snapshot.get("uav_team_summary")
        if not isinstance(raw, dict):
            return out
        bat = raw.get("battery_levels")
        if bat is None:
            inner = raw.get("value", raw)
            if isinstance(inner, dict):
                bat = inner.get("battery_levels")
        if not isinstance(bat, dict):
            return out
        for k, v in bat.items():
            try:
                out[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
        return out

    @staticmethod
    def _clamp01_float(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.75

    def _analyze_safety(
        self,
        _shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> list[StructuredTrigger]:
        triggers: list[StructuredTrigger] = []
        urm = runtime_models.get("uav_resource_model")
        by_uav: dict[str, Any] = {}
        if urm is not None:
            raw = getattr(urm, "by_uav_id", None)
            if isinstance(raw, dict):
                by_uav = dict(raw)

        for uid, st in by_uav.items():
            drift = getattr(st, "drift_level", None)
            risk = getattr(st, "local_risk_status", None)
            drift_f = self._parse_optional_float(drift)
            r = (str(risk).lower() if risk is not None else "")
            drift_sev = self._global_drift_severity(drift_f, r)
            if drift_sev is None:
                continue
            crit = drift_sev == Severity.CRITICAL
            uid_s = str(uid)
            triggers.append(
                SafetyTrigger(
                    trigger_type="DRIFT_TOO_HIGH",
                    severity=drift_sev,
                    confidence=self._clamp01_float(getattr(st, "local_plan_reliability", None)),
                    scope=Scope.GLOBAL,
                    affected_entities=(uid_s,),
                    timestamp=timestamp,
                    recommended_planner="fail_safe_planner" if crit else "local_uav_path_planner",
                    explanation_context=(
                        f"DRIFT_TOO_HIGH uav={uid_s}: drift_level={drift_f}; local_risk_status={risk!r}"
                    ),
                )
            )

        positions = self._collect_uav_positions(by_uav, global_snapshot)
        if self._positions_reliable_for_collision(positions):
            uids = sorted(positions.keys())
            for i, a in enumerate(uids):
                for b in uids[i + 1 :]:
                    d = self._position_distance(positions[a], positions[b])
                    if d is not None and d < 1.0:
                        crit = d < 0.25
                        triggers.append(
                            SafetyTrigger(
                                trigger_type="COLLISION_RISK",
                                severity=Severity.CRITICAL if crit else Severity.HIGH,
                                confidence=0.85,
                                scope=Scope.GLOBAL,
                                affected_entities=tuple(sorted((a, b))),
                                timestamp=timestamp,
                                recommended_planner=(
                                    "fail_safe_planner" if crit else "local_uav_path_planner"
                                ),
                                explanation_context=(
                                    f"COLLISION_RISK: uav_pair=({a},{b}); distance={d:.4f}"
                                ),
                            )
                        )

        unsafe_uavs = self._unsafe_uav_ids(by_uav, global_snapshot)
        if self._fleet_level_unsafe(global_snapshot):
            triggers.append(
                SafetyTrigger(
                    trigger_type="UNSAFE_SYSTEM_STATE",
                    severity=Severity.CRITICAL,
                    confidence=0.45,
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="fail_safe_planner",
                    explanation_context="UNSAFE_SYSTEM_STATE: fleet_level_issue_flag=True",
                )
            )
        if unsafe_uavs:
            crit = len(unsafe_uavs) >= 2
            triggers.append(
                SafetyTrigger(
                    trigger_type="UNSAFE_SYSTEM_STATE",
                    severity=Severity.CRITICAL if crit else Severity.HIGH,
                    confidence=0.55,
                    scope=Scope.GLOBAL,
                    affected_entities=tuple(sorted(unsafe_uavs)),
                    timestamp=timestamp,
                    recommended_planner="fail_safe_planner" if crit else "global_mission_planner",
                    explanation_context=(
                        f"UNSAFE_SYSTEM_STATE: uavs={','.join(sorted(unsafe_uavs))}"
                    ),
                )
            )

        return triggers

    @staticmethod
    def _global_drift_severity(drift_f: float | None, risk_lower: str) -> Severity | None:
        from_obs: Severity | None = None
        if drift_f is not None:
            if drift_f >= 1.0:
                from_obs = Severity.CRITICAL
            elif drift_f >= 0.7:
                from_obs = Severity.HIGH
            elif drift_f >= 0.3:
                from_obs = Severity.MEDIUM
        from_risk: Severity | None = None
        if "high_drift" in risk_lower:
            from_risk = Severity.HIGH
        elif "moderate_drift" in risk_lower or "moderate" in risk_lower:
            from_risk = Severity.MEDIUM
        cands = [s for s in (from_obs, from_risk) if s is not None]
        if not cands:
            return None
        order = (Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        return max(cands, key=lambda s: order.index(s))

    @staticmethod
    def _to_position_tuple(pos: Any) -> tuple[float, ...] | None:
        if pos is None:
            return None
        if isinstance(pos, (list, tuple)):
            out: list[float] = []
            for x in pos:
                try:
                    out.append(float(x))
                except (TypeError, ValueError):
                    return None
            if len(out) < 2:
                return None
            return tuple(out)
        return None

    def _collect_uav_positions(
        self,
        by_uav: dict[str, Any],
        global_snapshot: dict[str, Any],
    ) -> dict[str, tuple[float, ...]]:
        pos: dict[str, tuple[float, ...]] = {}
        for uid, st in by_uav.items():
            uid_s = str(uid)
            t = self._to_position_tuple(getattr(st, "current_position", None))
            if t is not None:
                pos[uid_s] = t
        team = self._unwrap_summary_layer(global_snapshot.get("uav_team_summary"))
        inner = team.get("value", team) if isinstance(team, dict) else {}
        by_snap = inner.get("by_uav_id") if isinstance(inner, dict) else None
        if isinstance(by_snap, dict):
            for uid, info in by_snap.items():
                uid_s = str(uid)
                if uid_s in pos:
                    continue
                if not isinstance(info, dict):
                    continue
                t = self._to_position_tuple(
                    info.get("current_position") or info.get("position")
                )
                if t is not None:
                    pos[uid_s] = t
        return pos

    @staticmethod
    def _positions_reliable_for_collision(positions: dict[str, tuple[float, ...]]) -> bool:
        if len(positions) < 2:
            return False
        dims = {len(p) for p in positions.values()}
        if len(dims) != 1:
            return False
        dim = next(iter(dims))
        if dim < 2:
            return False
        for p in positions.values():
            if any(not (x == x) or abs(x) > 1e9 for x in p):
                return False
        return True

    @staticmethod
    def _position_distance(
        a: tuple[float, ...], b: tuple[float, ...]
    ) -> float | None:
        if len(a) != len(b):
            return None
        s = 0.0
        for x, y in zip(a, b):
            d = x - y
            s += d * d
        return s**0.5

    def _unsafe_uav_ids(
        self,
        by_uav: dict[str, Any],
        global_snapshot: dict[str, Any],
    ) -> list[str]:
        found: set[str] = set()
        risky = ("unsafe", "emergency", "lost", "critical", "fault")
        for uid, st in by_uav.items():
            rs = str(getattr(st, "local_risk_status", "") or "").lower()
            cs = str(getattr(st, "communication_status", "") or "").lower()
            pfs = str(getattr(st, "path_feasibility_status", "") or "").lower()
            if any(t in rs for t in risky) or "lost" in cs or "blocked" in pfs:
                found.add(str(uid))
        team = self._unwrap_summary_layer(global_snapshot.get("uav_team_summary"))
        inner = team.get("value", team) if isinstance(team, dict) else {}
        by_snap = inner.get("by_uav_id") if isinstance(inner, dict) else None
        if isinstance(by_snap, dict):
            for uid, info in by_snap.items():
                if not isinstance(info, dict):
                    continue
                flags = info.get("issue_flags") or info.get("flags") or []
                if isinstance(flags, (list, tuple)) and flags:
                    found.add(str(uid))
                    continue
                for key in ("unsafe", "critical_issue", "system_fault"):
                    v = info.get(key)
                    if v is True or (isinstance(v, str) and v.lower() not in ("", "ok", "nominal")):
                        found.add(str(uid))
                        break
        return sorted(found)

    @staticmethod
    def _fleet_level_unsafe(global_snapshot: dict[str, Any]) -> bool:
        raw = global_snapshot.get("uav_team_summary")
        if isinstance(raw, dict):
            if raw.get("system_unsafe") is True or raw.get("fleet_emergency") is True:
                return True
            inner = raw.get("value")
            if isinstance(inner, dict):
                if inner.get("system_unsafe") is True or inner.get("fleet_emergency") is True:
                    return True
        return False

    def _analyze_fire_evolution(
        self,
        _shared_operational_picture: SharedOperationalPicture,
        _global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> list[StructuredTrigger]:
        triggers: list[StructuredTrigger] = []
        fr = runtime_models.get("fire_runtime_model")
        if fr is None:
            return triggers

        cells = getattr(fr, "estimated_fire_front_cells", None)
        current_count = 0
        if isinstance(cells, (list, tuple, set)):
            current_count = len(cells)
        if current_count == 0:
            pmap = getattr(fr, "predicted_fire_front_map", None)
            if isinstance(pmap, dict):
                current_count = len(pmap)

        bias = getattr(fr, "predicted_spread_bias", None)

        prev_c = self.previous_fire_front_count
        if prev_c is not None and current_count > prev_c:
            step = current_count - prev_c
            rel = (current_count / float(prev_c)) if prev_c > 0 else None
            accel = (prev_c > 0 and rel is not None and rel >= 1.25) or step >= max(
                3, prev_c // 4
            ) or (prev_c == 0 and current_count >= 5)
            if accel:
                sev = Severity.HIGH
                if prev_c > 0 and rel is not None:
                    sev = Severity.HIGH if rel >= 1.5 or step >= 6 else Severity.MEDIUM
                else:
                    sev = Severity.HIGH if step >= 8 else Severity.MEDIUM
                triggers.append(
                    AdaptationTrigger(
                        trigger_type="FIRE_SPREAD_ACCELERATING",
                        severity=sev,
                        confidence=0.7,
                        scope=Scope.GLOBAL,
                        affected_entities=("fleet",),
                        timestamp=timestamp,
                        recommended_planner="global_mission_planner",
                        explanation_context=(
                            f"FIRE_SPREAD_ACCELERATING: fire_front_count={current_count}; "
                            f"previous_fire_front_count={prev_c}"
                        ),
                    )
                )

        prev_bias = self.previous_predicted_spread_bias
        if prev_bias is not None and bias is not None and prev_bias != bias:
            triggers.append(
                AdaptationTrigger(
                    trigger_type="FIRE_DIRECTION_SHIFT",
                    severity=Severity.MEDIUM,
                    confidence=0.65,
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="global_mission_planner",
                    explanation_context="FIRE_DIRECTION_SHIFT: predicted_spread_bias changed vs prior cycle",
                )
            )

        self.previous_fire_front_count = int(current_count)
        self.previous_predicted_spread_bias = self._clone_fire_bias(bias)
        return triggers

    @staticmethod
    def _clone_fire_bias(bias: Any) -> Any:
        if bias is None:
            return None
        if isinstance(bias, dict):
            return dict(bias)
        if isinstance(bias, (list, tuple)):
            return list(bias)
        return bias

    def _analyze_communication(
        self,
        _shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> list[StructuredTrigger]:
        triggers: list[StructuredTrigger] = []
        cm = runtime_models.get("communication_model")
        snap = self._unwrap_summary_layer(global_snapshot.get("communication_summary"))

        delivery = self._comm_float(cm, snap, "delivery_confidence")
        crit_link = self._comm_float(cm, snap, "critical_link_reliability")
        sync_q = self._comm_float(cm, snap, "shared_knowledge_sync_quality")
        staleness = self._comm_float(cm, snap, "message_staleness")
        failed_n = self._failed_message_count(cm, snap)

        crit = (
            (crit_link is not None and crit_link < self.communication_critical_threshold / 2.0)
            or (delivery is not None and delivery < 0.15)
            or failed_n >= 8
        )
        planner = "fail_safe_planner" if crit else "global_mission_planner"
        conf = self._clamp01_float(delivery if delivery is not None else sync_q)

        link_bad = crit_link is not None and crit_link < self.communication_critical_threshold
        link_bad = link_bad or (delivery is not None and delivery < self.communication_critical_threshold)
        link_bad = link_bad or failed_n >= 3
        if link_bad:
            triggers.append(
                CommunicationTrigger(
                    trigger_type="CRITICAL_LINK_UNRELIABLE",
                    severity=Severity.CRITICAL if crit else Severity.HIGH,
                    confidence=conf,
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner=planner,
                    explanation_context=(
                        f"CRITICAL_LINK_UNRELIABLE: critical_link_reliability={crit_link}; "
                        f"delivery_confidence={delivery}; failed_messages={failed_n}"
                    ),
                )
            )

        desync = False
        if sync_q is not None and sync_q < self.low_confidence_threshold:
            desync = True
        if staleness is not None and staleness > self.stale_information_threshold:
            desync = True
        if snap.get("knowledge_desync_risk") is True or snap.get("desync_risk") is True:
            desync = True
        if desync:
            d_crit = crit or (sync_q is not None and sync_q < 0.2) or (
                staleness is not None and staleness > 2.0 * self.stale_information_threshold
            )
            triggers.append(
                CommunicationTrigger(
                    trigger_type="KNOWLEDGE_DESYNC_RISK",
                    severity=Severity.HIGH if d_crit else Severity.MEDIUM,
                    confidence=self._clamp01_float(sync_q if sync_q is not None else delivery),
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="fail_safe_planner" if d_crit else "global_mission_planner",
                    explanation_context=(
                        f"KNOWLEDGE_DESYNC_RISK: shared_knowledge_sync_quality={sync_q}; "
                        f"message_staleness={staleness}"
                    ),
                )
            )

        return triggers

    @staticmethod
    def _comm_float(
        cm: Any,
        snap: dict[str, Any],
        name: str,
    ) -> float | None:
        v = getattr(cm, name, None) if cm is not None else None
        if v is None and isinstance(snap, dict):
            inner = snap.get("state") if isinstance(snap.get("state"), dict) else snap
            if isinstance(inner, dict):
                v = inner.get(name)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _failed_message_count(cm: Any, snap: dict[str, Any]) -> int:
        raw = getattr(cm, "failed_messages", None) if cm is not None else None
        if raw is None and isinstance(snap, dict):
            inner = snap.get("state") if isinstance(snap.get("state"), dict) else snap
            if isinstance(inner, dict):
                raw = inner.get("failed_messages")
        if isinstance(raw, (list, tuple, set)):
            return len(raw)
        if isinstance(raw, int):
            return max(0, raw)
        return 0

    def _analyze_rescue_feasibility(
        self,
        _shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> list[StructuredTrigger]:
        triggers: list[StructuredTrigger] = []
        vm = runtime_models.get("victim_runtime_model")
        victims = getattr(vm, "victims", None) if vm is not None else None
        entries = self._rescue_victim_entries(victims)

        fm = runtime_models.get("firefighter_model")
        units = getattr(fm, "units", None) if fm is not None else None
        has_units = self._rescue_has_units(units)

        cm = runtime_models.get("communication_model")
        snap_comm = self._unwrap_summary_layer(global_snapshot.get("communication_summary"))
        delivery = self._comm_float(cm, snap_comm, "delivery_confidence")

        low_ids: list[str] = []
        uncertain_ids: list[str] = []
        unsafe_ids: list[str] = []
        good_feasible: list[str] = []

        for vid, raw in entries:
            conf = self._parse_optional_float(self._rescue_victim_field(raw, "confidence_score"))
            unc_r = self._parse_optional_float(
                self._rescue_victim_field(raw, "position_uncertainty_radius")
            )
            last_c = self._parse_optional_float(
                self._rescue_victim_field(raw, "last_confirmation_time")
            )
            route_c = self._parse_optional_float(
                self._rescue_victim_field(raw, "route_feasibility_confidence")
            )

            if conf is not None and conf < self.low_confidence_threshold:
                low_ids.append(vid)
            stale = last_c is not None and (timestamp - last_c) > self.stale_information_threshold
            if (unc_r is not None and unc_r > 5.0) or stale:
                uncertain_ids.append(vid)

            deliv = delivery if delivery is not None else 0.5
            route_bad = route_c is not None and route_c < 0.35
            if route_bad and (deliv < self.communication_critical_threshold or (conf is not None and conf < 0.25)):
                unsafe_ids.append(vid)

            if (
                conf is not None
                and conf >= 0.55
                and (unc_r is None or unc_r <= 3.0)
                and (route_c is None or route_c >= 0.5)
                and deliv >= 0.5
                and not stale
            ):
                good_feasible.append(vid)

        def _entities(ids: list[str]) -> tuple[str, ...]:
            return tuple(sorted(ids)) if ids else ("fleet",)

        if low_ids:
            triggers.append(
                RescueTrigger(
                    trigger_type="VICTIM_CONFIDENCE_LOW",
                    severity=Severity.HIGH,
                    confidence=self._clamp01_float(delivery),
                    scope=Scope.GLOBAL,
                    affected_entities=_entities(low_ids),
                    timestamp=timestamp,
                    recommended_planner="rescue_planner",
                    explanation_context=f"VICTIM_CONFIDENCE_LOW: victims={','.join(sorted(low_ids))}",
                )
            )
        if uncertain_ids:
            triggers.append(
                RescueTrigger(
                    trigger_type="RESCUE_UNCERTAIN",
                    severity=Severity.MEDIUM,
                    confidence=self._clamp01_float(delivery),
                    scope=Scope.GLOBAL,
                    affected_entities=_entities(uncertain_ids),
                    timestamp=timestamp,
                    recommended_planner="rescue_planner",
                    explanation_context=f"RESCUE_UNCERTAIN: victims={','.join(sorted(uncertain_ids))}",
                )
            )
        if unsafe_ids:
            triggers.append(
                RescueTrigger(
                    trigger_type="RESCUE_UNSAFE",
                    severity=Severity.CRITICAL,
                    confidence=self._clamp01_float(delivery),
                    scope=Scope.GLOBAL,
                    affected_entities=_entities(unsafe_ids),
                    timestamp=timestamp,
                    recommended_planner="fail_safe_planner",
                    explanation_context=f"RESCUE_UNSAFE: victims={','.join(sorted(unsafe_ids))}",
                )
            )

        feasible = (
            bool(good_feasible)
            and has_units
            and not low_ids
            and not uncertain_ids
            and not unsafe_ids
        )
        if feasible:
            triggers.append(
                RescueTrigger(
                    trigger_type="RESCUE_FEASIBLE",
                    severity=Severity.LOW,
                    confidence=self._clamp01_float(delivery),
                    scope=Scope.GLOBAL,
                    affected_entities=_entities(good_feasible),
                    timestamp=timestamp,
                    recommended_planner="rescue_planner",
                    explanation_context=(
                        f"RESCUE_FEASIBLE: victims={','.join(sorted(good_feasible))}; "
                        f"firefighter_units_available={has_units}"
                    ),
                )
            )

        return triggers

    @staticmethod
    def _rescue_victim_entries(victims: Any) -> list[tuple[str, Any]]:
        if victims is None:
            return []
        if isinstance(victims, dict):
            return [(str(k), v) for k, v in victims.items()]
        if isinstance(victims, (list, tuple)):
            out: list[tuple[str, Any]] = []
            for i, v in enumerate(victims):
                vid = str(i)
                if isinstance(v, dict) and v.get("victim_id") is not None:
                    vid = str(v["victim_id"])
                out.append((vid, v))
            return out
        return []

    @staticmethod
    def _rescue_victim_field(victim: Any, name: str) -> Any:
        if isinstance(victim, dict):
            return victim.get(name)
        return getattr(victim, name, None)

    @staticmethod
    def _rescue_has_units(units: Any) -> bool:
        if units is None:
            return False
        if isinstance(units, dict):
            return len(units) > 0
        if isinstance(units, (list, tuple, set)):
            return len(units) > 0
        return False

    def _analyze_stability(
        self,
        _shared_operational_picture: SharedOperationalPicture,
        _global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
    ) -> list[StructuredTrigger]:
        triggers: list[StructuredTrigger] = []
        urm = runtime_models.get("uav_resource_model")
        by_uav: dict[str, Any] = {}
        if urm is not None:
            raw = getattr(urm, "by_uav_id", None)
            if isinstance(raw, dict):
                by_uav = dict(raw)

        for uid, st in by_uav.items():
            uid_s = str(uid)
            switches = int(getattr(st, "role_switch_count", 0) or 0)
            timer = self._parse_optional_float(getattr(st, "role_stability_timer", None))
            task_age = self._parse_optional_float(getattr(st, "task_commitment_age", None))
            rel = self._parse_optional_float(getattr(st, "local_plan_reliability", None))

            if switches >= 3:
                triggers.append(
                    AdaptationTrigger(
                        trigger_type="OSCILLATION_RISK",
                        severity=Severity.HIGH if switches >= 6 else Severity.MEDIUM,
                        confidence=self._clamp01_float(rel),
                        scope=Scope.GLOBAL,
                        affected_entities=(uid_s,),
                        timestamp=timestamp,
                        recommended_planner="global_mission_planner",
                        explanation_context=(
                            f"OSCILLATION_RISK uav={uid_s}: role_switch_count={switches}; "
                            f"role_stability_timer={timer}; task_commitment_age={task_age}; "
                            f"local_plan_reliability={rel}"
                        ),
                    )
                )

            inst = False
            if switches >= 2 and timer is not None and timer < 10.0:
                inst = True
            if switches >= 3 and task_age is not None and task_age < 8.0:
                inst = True
            if inst:
                triggers.append(
                    SafetyTrigger(
                        trigger_type="INSTABILITY_DETECTED",
                        severity=Severity.CRITICAL
                        if (timer is not None and timer < 3.0 and switches >= 3)
                        else Severity.HIGH,
                        confidence=self._clamp01_float(rel),
                        scope=Scope.GLOBAL,
                        affected_entities=(uid_s,),
                        timestamp=timestamp,
                        recommended_planner="global_mission_planner",
                        explanation_context=(
                            f"INSTABILITY_DETECTED uav={uid_s}: role_switch_count={switches}; "
                            f"role_stability_timer={timer}; task_commitment_age={task_age}; "
                            f"local_plan_reliability={rel}"
                        ),
                    )
                )

        return triggers

    def _analyze_trends(
        self,
        _shared_operational_picture: SharedOperationalPicture,
        global_snapshot: dict[str, Any],
        runtime_models: dict[str, Any],
        timestamp: float,
        trend_baseline: tuple[float | None, int | None, float | None, float | None],
    ) -> list[StructuredTrigger]:
        prev_unc, prev_fire, prev_deliv, prev_batt = trend_baseline
        triggers: list[StructuredTrigger] = []

        curr_unc = self._trend_uncertainty_metric(global_snapshot)
        cm = runtime_models.get("communication_model")
        snap_comm = self._unwrap_summary_layer(global_snapshot.get("communication_summary"))
        curr_deliv = self._comm_float(cm, snap_comm, "delivery_confidence")
        curr_batt = self._trend_mean_battery(runtime_models)
        curr_fire = self._trend_fire_front_count(runtime_models)

        eps = 0.02
        worse: list[str] = []
        better: list[str] = []

        if prev_unc is not None and curr_unc is not None:
            if curr_unc > prev_unc + eps:
                worse.append(f"uncertainty {prev_unc:.3f}->{curr_unc:.3f}")
            elif curr_unc < prev_unc - eps:
                better.append(f"uncertainty {prev_unc:.3f}->{curr_unc:.3f}")

        if prev_deliv is not None and curr_deliv is not None:
            if curr_deliv < prev_deliv - eps:
                worse.append(f"delivery {prev_deliv:.3f}->{curr_deliv:.3f}")
            elif curr_deliv > prev_deliv + eps:
                better.append(f"delivery {prev_deliv:.3f}->{curr_deliv:.3f}")

        if prev_batt is not None and curr_batt is not None:
            if curr_batt < prev_batt - eps:
                worse.append(f"mean_battery {prev_batt:.3f}->{curr_batt:.3f}")
            elif curr_batt > prev_batt + eps:
                better.append(f"mean_battery {prev_batt:.3f}->{curr_batt:.3f}")

        if prev_fire is not None and curr_fire is not None:
            if curr_fire > prev_fire:
                worse.append(f"fire_front_count {prev_fire}->{curr_fire}")
            elif curr_fire < prev_fire:
                better.append(f"fire_front_count {prev_fire}->{curr_fire}")

        if worse:
            triggers.append(
                AdaptationTrigger(
                    trigger_type="TREND_WORSENING",
                    severity=Severity.MEDIUM,
                    confidence=0.55,
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="global_mission_planner",
                    explanation_context="TREND_WORSENING: " + "; ".join(worse),
                )
            )
        if better and not worse:
            triggers.append(
                AdaptationTrigger(
                    trigger_type="TREND_IMPROVING",
                    severity=Severity.LOW,
                    confidence=0.6,
                    scope=Scope.GLOBAL,
                    affected_entities=("fleet",),
                    timestamp=timestamp,
                    recommended_planner="global_mission_planner",
                    explanation_context="TREND_IMPROVING: " + "; ".join(better),
                )
            )

        if curr_deliv is not None:
            self.previous_delivery_confidence = float(curr_deliv)
        if curr_batt is not None:
            self.previous_mean_battery = float(curr_batt)

        return triggers

    def _trend_uncertainty_metric(self, global_snapshot: dict[str, Any]) -> float | None:
        u = self._unwrap_summary_layer(global_snapshot.get("uncertainty_summary"))
        stale = self._coerce_float_map(u.get("staleness_map") if isinstance(u.get("staleness_map"), dict) else {})
        if stale:
            return sum(stale.values()) / len(stale)
        unk = u.get("unknown_or_uncertain_regions")
        if isinstance(unk, list) and unk:
            return min(1.0, len(unk) / 20.0)
        return None

    @staticmethod
    def _trend_mean_battery(runtime_models: dict[str, Any]) -> float | None:
        urm = runtime_models.get("uav_resource_model")
        if urm is None:
            return None
        raw = getattr(urm, "by_uav_id", None)
        if not isinstance(raw, dict) or not raw:
            return None
        vals: list[float] = []
        for st in raw.values():
            bl = getattr(st, "battery_level", None)
            if bl is not None:
                try:
                    vals.append(float(bl))
                except (TypeError, ValueError):
                    continue
        if not vals:
            return None
        return sum(vals) / len(vals)

    @staticmethod
    def _trend_fire_front_count(runtime_models: dict[str, Any]) -> int | None:
        fr = runtime_models.get("fire_runtime_model")
        if fr is None:
            return None
        cells = getattr(fr, "estimated_fire_front_cells", None)
        n = 0
        if isinstance(cells, (list, tuple, set)):
            n = len(cells)
        if n == 0:
            pmap = getattr(fr, "predicted_fire_front_map", None)
            if isinstance(pmap, dict):
                n = len(pmap)
        return int(n)
