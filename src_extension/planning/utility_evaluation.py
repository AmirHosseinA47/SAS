"""Utility evaluation data structures.

Includes adaptive ``UtilityWeightProfile`` presets per operational mode; no scoring formulas
beyond small helpers (clamp, safe coercions, basic dict).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any


@dataclass
class UtilityTerm:
    name: str
    value: float
    weight: float
    contribution: float
    explanation: str = ""


@dataclass
class OptionEvaluation:
    option_id: str
    option_type: str
    feasible: bool
    constraint_violations: tuple[str, ...]
    predicted_effects: dict[str, object]
    utility_terms: tuple[UtilityTerm, ...]
    total_utility: float
    confidence_score: float
    stability_cost: float
    information_recovery_score: float
    explanation_summary: str


@dataclass
class ScoredOption:
    option: object
    evaluation: OptionEvaluation
    score: float


@dataclass
class UtilityWeightProfile:
    fire_weight: float
    victim_weight: float
    communication_weight: float
    uncertainty_reduction_weight: float
    information_recovery_weight: float
    collision_risk_weight: float
    battery_cost_weight: float
    drift_risk_weight: float
    switching_cost_weight: float
    task_support_weight: float
    overlap_penalty_weight: float
    smoke_penalty_weight: float
    stability_weight: float
    confidence_adjustment_enabled: bool


_WEIGHT_PROFILES: dict[str, UtilityWeightProfile] = {
    "normal_monitoring_mode": UtilityWeightProfile(
        fire_weight=1.0,
        victim_weight=1.0,
        communication_weight=1.0,
        uncertainty_reduction_weight=0.9,
        information_recovery_weight=0.7,
        collision_risk_weight=1.2,
        battery_cost_weight=0.9,
        drift_risk_weight=0.9,
        switching_cost_weight=0.7,
        task_support_weight=1.0,
        overlap_penalty_weight=0.6,
        smoke_penalty_weight=0.6,
        stability_weight=0.9,
        confidence_adjustment_enabled=True,
    ),
    "victim_support_mode": UtilityWeightProfile(
        fire_weight=0.9,
        victim_weight=2.0,
        communication_weight=1.0,
        uncertainty_reduction_weight=0.7,
        information_recovery_weight=0.5,
        collision_risk_weight=1.4,
        battery_cost_weight=0.8,
        drift_risk_weight=0.85,
        switching_cost_weight=0.55,
        task_support_weight=1.8,
        overlap_penalty_weight=0.65,
        smoke_penalty_weight=0.65,
        stability_weight=0.75,
        confidence_adjustment_enabled=True,
    ),
    "communication_degraded_mode": UtilityWeightProfile(
        fire_weight=1.0,
        victim_weight=1.0,
        communication_weight=2.0,
        uncertainty_reduction_weight=1.5,
        information_recovery_weight=1.7,
        collision_risk_weight=1.15,
        battery_cost_weight=0.95,
        drift_risk_weight=1.0,
        switching_cost_weight=0.85,
        task_support_weight=1.1,
        overlap_penalty_weight=0.55,
        smoke_penalty_weight=0.55,
        stability_weight=1.0,
        confidence_adjustment_enabled=True,
    ),
    "battery_constrained_mode": UtilityWeightProfile(
        fire_weight=0.95,
        victim_weight=1.0,
        communication_weight=1.0,
        uncertainty_reduction_weight=0.75,
        information_recovery_weight=0.55,
        collision_risk_weight=1.25,
        battery_cost_weight=2.0,
        drift_risk_weight=1.15,
        switching_cost_weight=1.35,
        task_support_weight=0.95,
        overlap_penalty_weight=0.55,
        smoke_penalty_weight=0.45,
        stability_weight=1.05,
        confidence_adjustment_enabled=True,
    ),
    "safety_first_mode": UtilityWeightProfile(
        fire_weight=1.15,
        victim_weight=1.1,
        communication_weight=0.95,
        uncertainty_reduction_weight=0.65,
        information_recovery_weight=0.55,
        collision_risk_weight=2.4,
        battery_cost_weight=1.05,
        drift_risk_weight=1.35,
        switching_cost_weight=0.85,
        task_support_weight=0.95,
        overlap_penalty_weight=1.15,
        smoke_penalty_weight=1.45,
        stability_weight=1.5,
        confidence_adjustment_enabled=False,
    ),
    "information_recovery_mode": UtilityWeightProfile(
        fire_weight=0.9,
        victim_weight=0.95,
        communication_weight=1.45,
        uncertainty_reduction_weight=1.75,
        information_recovery_weight=2.0,
        collision_risk_weight=1.05,
        battery_cost_weight=0.85,
        drift_risk_weight=0.95,
        switching_cost_weight=0.6,
        task_support_weight=1.05,
        overlap_penalty_weight=0.45,
        smoke_penalty_weight=0.55,
        stability_weight=1.1,
        confidence_adjustment_enabled=True,
    ),
}


def get_weight_profile(mode: str) -> UtilityWeightProfile:
    try:
        return _WEIGHT_PROFILES[mode]
    except KeyError as e:
        supported = ", ".join(sorted(_WEIGHT_PROFILES))
        raise ValueError(f"Unknown utility weight mode {mode!r}; supported: {supported}") from e


class UtilityEvaluation:
    """Skeleton for scoring adaptation options; detailed utility formulas are not implemented yet."""

    def __init__(self, default_mode: str = "normal_monitoring_mode") -> None:
        self.default_mode = default_mode

    def score_options(
        self,
        options: Iterable[object],
        runtime_models: object | None = None,
        context: object | None = None,
        mode: str | None = None,
    ) -> tuple[ScoredOption, ...]:
        resolved_mode = mode if mode is not None else self.default_mode
        scored: list[ScoredOption] = []
        for option in options:
            evaluation = self.evaluate_option(
                option,
                runtime_models=runtime_models,
                context=context,
                mode=resolved_mode,
            )
            scored.append(ScoredOption(option=option, evaluation=evaluation, score=evaluation.total_utility))
        scored.sort(key=lambda s: s.score, reverse=True)
        return tuple(scored)

    def evaluate_option(
        self,
        option: object,
        runtime_models: object | None = None,
        context: object | None = None,
        mode: str | None = None,
    ) -> OptionEvaluation:
        resolved_mode = mode if mode is not None else self.default_mode
        _ = get_weight_profile(resolved_mode)
        evaluator = self._pick_evaluator(option)
        return evaluator(option, runtime_models, context, resolved_mode)

    def _pick_evaluator(self, option: object):
        ot = self._option_type_lower(option)
        sv = self._scope_value(option)

        if "communication" in ot:
            return self._evaluate_communication_option
        if sv == "rescue" or "rescue" in ot:
            return self._evaluate_rescue_option
        if sv == "system" or "fail-safe" in ot or "failsafe" in ot or "fail_safe" in ot:
            return self._evaluate_failsafe_option
        local_keys = ("path", "movement", "sensing", "horizon")
        if sv == "local" or any(k in ot for k in local_keys):
            return self._evaluate_local_path_option
        global_keys = ("global", "mission", "task", "role", "resource")
        if sv == "global" or any(k in ot for k in global_keys):
            return self._evaluate_global_mission_option
        return self._evaluate_global_mission_option

    @staticmethod
    def _scope_value(option: object) -> str | None:
        scope = getattr(option, "scope", None)
        if scope is None:
            return None
        raw = getattr(scope, "value", scope)
        return str(raw)

    @staticmethod
    def _option_type_lower(option: object) -> str:
        return str(getattr(option, "option_type", "") or "").lower()

    @staticmethod
    def _merge_params_for_feasibility(option: object, context: object | None) -> dict[str, Any]:
        """Merge option.parameters with context-derived dict (context overlays option)."""
        params: dict[str, Any] = {}
        op = getattr(option, "parameters", None)
        if isinstance(op, dict):
            params.update(op)
        if isinstance(context, dict):
            params.update(context)
        elif context is not None:
            cp = getattr(context, "parameters", None)
            if isinstance(cp, dict):
                params.update(cp)
        return params

    def _check_utility_feasibility(self, option: object, context: object | None = None) -> tuple[bool, tuple[str, ...]]:
        """Utility-level hard constraints; reads merged option/context parameters only."""
        critical_battery_threshold = 15.0
        hard_collision_risk_threshold = 0.95
        route_feasibility_min_confidence = 0.25
        communication_min_confidence = 0.25

        params = self._merge_params_for_feasibility(option, context)
        violations: set[str] = set()

        if "battery_level" in params and safe_float(params.get("battery_level"), 100.0) <= critical_battery_threshold:
            violations.add("battery_below_critical")
        if "projected_battery_after_option" in params:
            if safe_float(params.get("projected_battery_after_option"), 100.0) <= critical_battery_threshold:
                violations.add("battery_below_critical")

        if params.get("hard_collision_violation") is True:
            violations.add("hard_collision_constraint")
        if "collision_risk" in params:
            if safe_float(params.get("collision_risk"), 0.0) >= hard_collision_risk_threshold:
                violations.add("hard_collision_constraint")

        if params.get("route_feasible") is False:
            violations.add("rescue_route_infeasible")
        if "route_feasibility_confidence" in params:
            if safe_float(params.get("route_feasibility_confidence"), 1.0) <= route_feasibility_min_confidence:
                violations.add("rescue_route_infeasible")

        if (
            params.get("requires_critical_communication") is True
            and params.get("fail_safe_mode") is not True
        ):
            dc = safe_float(params.get("delivery_confidence"), 0.5)
            if dc <= communication_min_confidence:
                violations.add("critical_communication_unavailable")

        if violations:
            return False, tuple(sorted(violations))
        return True, ()

    def _compute_switching_cost(self, option: object, context: object | None = None) -> float:
        """Policy switching / churn cost from role/task change signals and recent switches."""
        _ = context
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}

        def _indicator(key: str) -> float:
            v = params.get(key)
            if v is True:
                return 1.0
            if v is False or v is None:
                return 0.0
            return clamp01(safe_float(v, 0.0))

        role_change_indicator = max(_indicator("role_change"), _indicator("task_change"))
        recent_raw = safe_float(params.get("recent_switch_count"), 0.0) + 0.2 * safe_float(
            params.get("role_switch_count"), 0.0
        )
        timer = safe_float(params.get("role_stability_timer"), 0.0)
        timer_damp = max(0.45, 1.0 - 0.12 * clamp01(timer))
        recent_switch_count_penalty = max(0.0, recent_raw) * timer_damp

        alpha = 0.3
        beta = 0.15
        return alpha * role_change_indicator + beta * recent_switch_count_penalty

    def _compute_stability_bonus(self, option: object, context: object | None = None) -> float:
        """Small bonus for hold-steady / no-change options when no critical trigger is active."""
        _ = context
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}
        ot = self._option_type_lower(option)

        def ptruth_s(*keys: str) -> bool:
            for key in keys:
                if key not in params:
                    continue
                v = params.get(key)
                if v is True:
                    return True
                if isinstance(v, (int, float)) and v != 0.0:
                    return True
                if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
                    return True
            return False

        stability_action = (
            "stability_control" in ot
            or "do_nothing" in ot
            or "maintain_current_config" in ot
            or "keep_current_path" in ot
            or "keep_current_assignment" in ot
            or ptruth_s(
                "stability_control",
                "do_nothing",
                "maintain_current_config",
                "keep_current_path",
                "keep_current_assignment",
            )
        )
        critical = (
            ptruth_s("critical_trigger", "emergency", "immediate_action", "mayday")
            or any(k in ot for k in ("emergency", "mayday", "evade", "escape", "critical"))
            or clamp01(safe_float(params.get("criticality"), 0.0)) >= 0.88
        )
        if not stability_action or critical:
            return 0.0
        base = 0.12
        rt = clamp01(safe_float(params.get("role_stability_timer"), 0.0))
        return float(min(0.22, base + 0.09 * rt))

    def _compute_negative_information_adjustment(
        self, option: object, context: object | None = None
    ) -> tuple[float, str]:
        """Additive utility delta from negative-observation / cleared-region policy."""
        _ = context
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}

        def sig(key: str) -> float:
            v = params.get(key)
            if v is True:
                return 1.0
            if v is False or v is None:
                return 0.0
            return clamp01(safe_float(v, 0.0))

        recent = sig("negative_observation_recent")
        stale = clamp01(safe_float(params.get("negative_observation_stale"), 0.0))
        avoids = sig("avoids_recent_negative_region")
        confirms = sig("confirms_stale_negative_region")
        uncertainty = clamp01(safe_float(params.get("uncertainty_level"), 0.0))

        delta = 0.0
        parts: list[str] = []

        if recent > 1e-9:
            stale_relief = 1.0 - 0.85 * stale
            pen = -0.22 * clamp01(recent) * max(0.0, stale_relief)
            delta += pen
            parts.append(f"recent_negative_rescan({pen:.3f})")

        if avoids > 1e-9:
            bonus = 0.16 * clamp01(avoids)
            delta += bonus
            parts.append(f"avoids_cleared_region(+{bonus:.3f})")

        if confirms > 1e-9 and stale > 0.08:
            u_gate = 0.28 + 0.72 * uncertainty
            bonus_c = 0.15 * clamp01(confirms) * stale * u_gate
            delta += bonus_c
            parts.append(f"confirm_stale_negative(+{bonus_c:.3f})")

        note = "; ".join(parts) if parts else "neutral_negative_information"
        return float(delta), note

    def _compute_horizon_context_fit(
        self, option: object, context: object | None = None
    ) -> tuple[float, str]:
        """Additive utility for aligning horizon type/length with uncertainty, comm, fire, and collapse."""
        _ = context
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}

        ht_raw = params.get("horizon_type")
        ht = str(ht_raw).lower() if ht_raw is not None else ""
        h_len = clamp01(safe_float(params.get("candidate_horizon_length"), 0.5))
        u = clamp01(safe_float(params.get("uncertainty_level"), 0.0))
        comm = clamp01(safe_float(params.get("communication_reliability"), 0.65))
        fire_sp = clamp01(safe_float(params.get("fire_spread_speed"), 0.0))
        collapse = clamp01(safe_float(params.get("information_collapse"), 0.0))

        short_family = ("short" in ht) or ("adapt" in ht) or ("roll" in ht) or ("reced" in ht)
        long_family = ("long" in ht) or ("extend" in ht)
        search_replan = ("search" in ht) or ("replan" in ht)

        prefer_short = clamp01(0.52 * u + 0.48 * (1.0 - comm) + 0.62 * collapse + 0.32 * fire_sp)
        prefer_long = clamp01((1.0 - u) * comm * (1.0 - 0.9 * collapse))

        short_alignment = clamp01((1.0 - h_len + 0.35 * (1.0 if short_family else 0.0)) / 1.35)
        long_alignment = clamp01((h_len + 0.35 * (1.0 if long_family else 0.0)) / 1.35)

        delta = 0.0
        parts: list[str] = []

        if prefer_short > 0.06:
            gain = 0.2 * prefer_short * short_alignment
            delta += gain
            parts.append(f"short_adaptive_context_fit(+{gain:.3f})")

        if prefer_short > 0.12 and h_len > 0.55 and not short_family:
            pen = -0.22 * prefer_short * h_len
            delta += pen
            parts.append(f"horizon_too_long_vs_context({pen:.3f})")

        if prefer_long > 0.15:
            gain_l = 0.16 * prefer_long * long_alignment
            delta += gain_l
            parts.append(f"stable_long_horizon_fit(+{gain_l:.3f})")

        if collapse > 0.2:
            if search_replan or short_family or h_len <= 0.48:
                ex = 0.12 * collapse
                delta += ex
                parts.append(f"collapse_short_search_replan(+{ex:.3f})")
            else:
                ex2 = -0.14 * collapse * h_len
                delta += ex2
                parts.append(f"collapse_vs_long_horizon({ex2:.3f})")

        note = "; ".join(parts) if parts else "neutral_horizon_fit"
        return float(delta), note

    def _compute_distance_from_goal(
        self, option: object, context: object | None = None
    ) -> dict[str, float]:
        """Optional goal-distance metrics from parameters (explanation / diagnostics only)."""
        _ = context
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}
        keys = (
            "battery_distance_to_critical",
            "coverage_distance_to_target",
            "rescue_certainty_distance",
            "communication_distance_to_threshold",
            "information_sufficiency_distance",
        )
        out: dict[str, float] = {}
        for k in keys:
            if k not in params:
                continue
            raw = safe_float(params.get(k), float("nan"))
            if raw != raw:
                continue
            v = max(0.0, raw)
            if k in (
                "rescue_certainty_distance",
                "communication_distance_to_threshold",
                "information_sufficiency_distance",
            ):
                v = clamp01(v)
            else:
                v = min(v, 1.0e6)
            out[k] = float(v)
        return out

    def _apply_confidence_and_uncertainty_adjustment(
        self,
        raw_score: float,
        option: object,
        terms: Iterable[UtilityTerm],
        context: object | None,
        profile: UtilityWeightProfile,
    ) -> tuple[float, tuple[UtilityTerm, ...], str, float]:
        """Scale raw utility and term contributions by confidence, knowledge confidence, and uncertainty."""
        _ = context
        terms_tuple = tuple(terms)
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}

        def ptruth_p(*keys: str) -> bool:
            for key in keys:
                if key not in params:
                    continue
                v = params.get(key)
                if v is True:
                    return True
                if isinstance(v, (int, float)) and v != 0.0:
                    return True
                if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
                    return True
            return False

        mult = 1.0
        detail: list[str] = []

        if profile.confidence_adjustment_enabled:
            c = clamp01(safe_float(getattr(option, "confidence", None), 1.0))
            mult *= c
            detail.append(f"agent_confidence×{c:.3f}")

        if "knowledge_confidence" in params:
            kc = clamp01(safe_float(params.get("knowledge_confidence"), 1.0))
            mult *= kc
            detail.append(f"knowledge_confidence×{kc:.3f}")

        if "uncertainty_level" in params:
            u = clamp01(safe_float(params.get("uncertainty_level"), 0.0))
            if u > 1e-9:
                ot = self._option_type_lower(option)
                is_recovery = (
                    ptruth_p("confirmation", "search_mode")
                    or "confirm" in ot
                    or "search" in ot
                    or "information_recovery" in ot
                    or ptruth_p("information_recovery")
                )
                is_risky = (
                    ptruth_p("risky_action", "execute_mission")
                    or any(
                        k in ot
                        for k in (
                            "dispatch",
                            "initiate",
                            "execute",
                            "reassign",
                            "ingress",
                            "path",
                            "movement",
                        )
                    )
                )
                if is_recovery:
                    boost = min(1.88, 1.0 + 0.45 * u)
                    mult *= boost
                    detail.append(f"uncertainty_boost_inquiry×{boost:.3f}")
                if is_risky:
                    damp = max(0.17, 1.0 - 0.53 * u)
                    mult *= damp
                    detail.append(f"uncertainty_damp_risky×{damp:.3f}")

        adjusted_score = raw_score * mult
        new_terms = tuple(
            UtilityTerm(
                name=t.name,
                value=t.value,
                weight=t.weight,
                contribution=t.contribution * mult,
                explanation=t.explanation,
            )
            for t in terms_tuple
        )
        suffix = ""
        if detail:
            suffix = (
                " [Confidence / uncertainty: "
                + "; ".join(detail)
                + f"; net ×{mult:.3f} on raw {raw_score:.4f}]."
            )
        return adjusted_score, new_terms, suffix, mult

    def _make_evaluation(
        self,
        *,
        option: object,
        feasible: bool = True,
        constraint_violations: tuple[str, ...] = (),
        predicted_effects: dict[str, object] | None = None,
        utility_terms: tuple[UtilityTerm, ...] = (),
        total_utility: float = 0.0,
        stability_cost: float = 0.0,
        information_recovery_score: float = 0.0,
        explanation_summary: str = "",
    ) -> OptionEvaluation:
        option_id = str(getattr(option, "option_id", ""))
        option_type = str(getattr(option, "option_type", ""))
        effects: dict[str, object] = dict(predicted_effects) if predicted_effects is not None else {}
        summary = explanation_summary or "Neutral placeholder evaluation (no utility formula yet)."
        confidence = safe_float(getattr(option, "confidence", None), 0.5)
        return OptionEvaluation(
            option_id=option_id,
            option_type=option_type,
            feasible=feasible,
            constraint_violations=constraint_violations,
            predicted_effects=effects,
            utility_terms=utility_terms,
            total_utility=total_utility,
            confidence_score=confidence,
            stability_cost=stability_cost,
            information_recovery_score=information_recovery_score,
            explanation_summary=summary,
        )

    def _evaluate_local_path_option(
        self,
        option: object,
        runtime_models: object | None,
        context: object | None,
        mode: str,
    ) -> OptionEvaluation:
        _ = runtime_models
        profile = get_weight_profile(mode)
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}

        def pfloat(*keys: str, default: float = 0.0) -> float:
            for key in keys:
                if key in params:
                    return safe_float(params.get(key), default)
            return default

        g_info = pfloat("expected_info_gain", "information_gain")
        g_belief = pfloat("belief_gain")
        g_recovery = pfloat("recovery_value", "information_recovery_score")
        s_task = pfloat("task_support")
        p_overlap = pfloat("overlap_penalty")
        p_collision = pfloat("collision_risk", "risk_estimate")
        p_smoke = pfloat("smoke_penalty")
        c_battery = pfloat("battery_cost", "cost_estimate")
        p_drift = pfloat("drift_penalty")
        s_stab = pfloat("stability_bonus", "path_stability_score")

        # w1..w10: map formula coefficients to UtilityWeightProfile fields (path-relevant subset).
        w1 = profile.uncertainty_reduction_weight
        w2 = profile.fire_weight
        w3 = profile.information_recovery_weight
        w4 = profile.task_support_weight
        w5 = profile.overlap_penalty_weight
        w6 = profile.collision_risk_weight
        w7 = profile.smoke_penalty_weight
        w8 = profile.battery_cost_weight
        w9 = profile.drift_risk_weight
        w10 = profile.stability_weight

        raw_terms: list[tuple[str, float, float, str]] = [
            ("G_info", w1, g_info, "expected information / uncertainty reduction"),
            ("G_belief", w2, g_belief, "belief / shared picture gain"),
            ("G_recovery", w3, g_recovery, "information recovery value"),
            ("S_task", w4, s_task, "task support"),
            ("P_overlap", -w5, p_overlap, "overlap penalty"),
            ("P_collision", -w6, p_collision, "collision risk"),
            ("P_smoke", -w7, p_smoke, "smoke exposure"),
            ("Cost_battery", -w8, c_battery, "battery cost"),
            ("P_drift", -w9, p_drift, "drift / deviation penalty"),
            ("S_stability", w10, s_stab, "path stability bonus"),
        ]

        switch_cost = self._compute_switching_cost(option, context)
        w_sw = profile.switching_cost_weight
        raw_terms.append(("Cost_switch_policy", -w_sw, switch_cost, "switching / role churn (policy)"))

        stab_hyst = self._compute_stability_bonus(option, context)
        if stab_hyst > 0.0:
            raw_terms.append(("S_hysteresis_bonus", w10, stab_hyst, "stability / hysteresis hold preference"))

        ni_delta, ni_note = self._compute_negative_information_adjustment(option, context)
        if abs(ni_delta) > 1e-9:
            raw_terms.append(("U_negative_information", 1.0, ni_delta, ni_note[:200]))

        hz_delta, hz_note = self._compute_horizon_context_fit(option, context)
        if abs(hz_delta) > 1e-9:
            raw_terms.append(("U_horizon_context_fit", 1.0, hz_delta, hz_note[:200]))

        confidence = safe_float(getattr(option, "confidence", None), 0.5)

        utility_terms: list[UtilityTerm] = []
        for name, coeff, value, hint in raw_terms:
            contrib = coeff * value
            utility_terms.append(
                UtilityTerm(
                    name=name,
                    value=value,
                    weight=abs(coeff),
                    contribution=contrib,
                    explanation=hint,
                )
            )

        total_raw = sum(c * v for _, c, v, _ in raw_terms)
        total_utility, adj_terms, cua_note, net_mult = self._apply_confidence_and_uncertainty_adjustment(
            total_raw, option, tuple(utility_terms), context, profile
        )

        pos = [(t.name, t.contribution) for t in adj_terms if t.contribution > 0.0]
        neg = [(t.name, t.contribution) for t in adj_terms if t.contribution < 0.0]
        best_pos = max(pos, key=lambda x: x[1]) if pos else None
        worst_neg = min(neg, key=lambda x: x[1]) if neg else None

        if best_pos and worst_neg:
            explanation_summary = (
                f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}). "
                f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f})."
            )
        elif best_pos:
            explanation_summary = f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}); negligible penalties."
        elif worst_neg:
            explanation_summary = f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f}); no positive drivers."
        else:
            explanation_summary = "All path utility terms near zero; no dominant positive or negative driver."

        explanation_summary += cua_note

        stability_cost = clamp01(1.0 - s_stab)

        predicted_effects: dict[str, object] = {
            "U_path_raw": total_raw,
            "utility_mode": mode,
            "utility_adjustment_multiplier": net_mult,
            "policy_switching_cost": switch_cost,
            "stability_hysteresis_bonus": stab_hyst,
            "negative_information_adjustment": ni_delta,
            "negative_information_note": ni_note,
            "horizon_context_adjustment": hz_delta,
            "horizon_context_note": hz_note,
            "distance_from_goal": self._compute_distance_from_goal(option, context),
        }

        feasible, constraint_violations = self._check_utility_feasibility(option, context)
        total_out = total_utility
        if not feasible:
            total_out = -1_000_000.0 + total_utility * 0.001
            explanation_summary = f"Infeasible ({', '.join(constraint_violations)}). " + explanation_summary

        return OptionEvaluation(
            option_id=str(getattr(option, "option_id", "")),
            option_type=str(getattr(option, "option_type", "")),
            feasible=feasible,
            constraint_violations=constraint_violations,
            predicted_effects=predicted_effects,
            utility_terms=adj_terms,
            total_utility=total_out,
            confidence_score=confidence,
            stability_cost=stability_cost,
            information_recovery_score=g_recovery,
            explanation_summary=explanation_summary,
        )

    def _evaluate_global_mission_option(
        self,
        option: object,
        runtime_models: object | None,
        context: object | None,
        mode: str,
    ) -> OptionEvaluation:
        _ = runtime_models
        profile = get_weight_profile(mode)
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}
        ot = self._option_type_lower(option)

        def pfloat(*keys: str, default: float = 0.0) -> float:
            for key in keys:
                if key in params:
                    return safe_float(params.get(key), default)
            return default

        def ptruth(*keys: str) -> bool:
            for key in keys:
                if key not in params:
                    continue
                v = params.get(key)
                if v is True:
                    return True
                if isinstance(v, (int, float)) and v != 0.0:
                    return True
                if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
                    return True
            return False

        c_fire = pfloat("fire_contribution")
        c_victim = pfloat("victim_contribution")
        c_comm = pfloat("communication_contribution")
        g_unc = pfloat("uncertainty_reduction")
        g_ir = pfloat("information_recovery")
        r_col = pfloat("collision_risk")
        cost_b = pfloat("battery_cost")
        r_drift = pfloat("drift_risk")
        cost_sw = pfloat("switching_cost")

        is_stability_idle = (
            "do_nothing" in ot
            or "stability_control" in ot
            or ptruth("stability_control", "do_nothing")
            or str(params.get("mission_mode", "") or "").lower() in {"hold", "stability", "idle", "do_nothing"}
        )
        if is_stability_idle:
            damp = 0.35
            c_fire *= damp
            c_victim *= damp
            c_comm *= damp
            g_unc *= damp
            g_ir *= damp
            r_col *= 0.55
            cost_b *= 0.55
            r_drift *= 0.55
            cost_sw *= 0.55

        is_search = (
            "search" in ot
            or "information_recovery" in ot
            or ptruth("search_mode")
            or str(params.get("mission_mode", "") or "").lower() in {"search", "information_recovery"}
        )
        if is_search:
            recovery_signal = pfloat("recovery_value", "information_recovery_score")
            g_ir = max(g_ir, recovery_signal)

        from_role = params.get("from_role", params.get("from_uav_role"))
        to_role = params.get("to_role", params.get("to_uav_role"))
        role_changed = (
            ptruth("role_change")
            or ("reassign" in ot)
            or ("role" in ot and "change" in ot)
            or (
                from_role is not None
                and to_role is not None
                and str(from_role) != str(to_role)
            )
        )
        if role_changed and cost_sw == 0.0:
            cost_sw = safe_float(getattr(option, "cost_estimate", None), 0.0)
        if role_changed and cost_sw == 0.0:
            cost_sw = 0.15

        policy_switching = self._compute_switching_cost(option, context)
        cost_sw = cost_sw + policy_switching

        w1 = profile.fire_weight
        w2 = profile.victim_weight
        w3 = profile.communication_weight
        w4 = profile.uncertainty_reduction_weight
        w5 = profile.information_recovery_weight
        w6 = profile.collision_risk_weight
        w7 = profile.battery_cost_weight
        w8 = profile.drift_risk_weight
        w9 = profile.switching_cost_weight

        raw_terms: list[tuple[str, float, float, str]] = [
            ("C_fire", w1, c_fire, "fire-line / spread mission value"),
            ("C_victim", w2, c_victim, "victim / casualty mission value"),
            ("C_comm", w3, c_comm, "communication / coordination value"),
            ("G_uncertainty_reduction", w4, g_unc, "uncertainty reduction"),
            ("G_information_recovery", w5, g_ir, "information recovery gain"),
            ("R_collision", -w6, r_col, "collision risk"),
            ("Cost_battery", -w7, cost_b, "battery cost"),
            ("R_drift", -w8, r_drift, "drift / deviation risk"),
            ("Cost_switch", -w9, cost_sw, "role / plan switching cost"),
        ]

        stab_hyst = self._compute_stability_bonus(option, context)
        if stab_hyst > 0.0:
            raw_terms.append(
                (
                    "S_hysteresis_bonus",
                    profile.stability_weight,
                    stab_hyst,
                    "stability / hysteresis hold preference",
                )
            )

        ni_delta, ni_note = self._compute_negative_information_adjustment(option, context)
        if abs(ni_delta) > 1e-9:
            raw_terms.append(("U_negative_information", 1.0, ni_delta, ni_note[:200]))

        idle_floor = 0.05 * profile.stability_weight if is_stability_idle else 0.0
        if idle_floor > 0.0:
            raw_terms.append(("S_stability_idle_floor", 1.0, idle_floor, "low stable baseline for hold-steady option"))

        hz_delta = 0.0
        hz_note = ""
        _hz_required = (
            "horizon_type",
            "candidate_horizon_length",
            "uncertainty_level",
            "communication_reliability",
            "fire_spread_speed",
            "information_collapse",
        )
        if all(k in params for k in _hz_required):
            hz_delta, hz_note = self._compute_horizon_context_fit(option, context)
            raw_terms.append(("U_horizon_context_fit", 1.0, hz_delta, hz_note[:200]))

        confidence = safe_float(getattr(option, "confidence", None), 0.5)

        utility_terms: list[UtilityTerm] = []
        for name, coeff, value, hint in raw_terms:
            contrib = coeff * value
            utility_terms.append(
                UtilityTerm(
                    name=name,
                    value=value,
                    weight=abs(coeff),
                    contribution=contrib,
                    explanation=hint,
                )
            )

        total_raw = sum(c * v for _, c, v, _ in raw_terms)
        total_utility, adj_terms, cua_note, net_mult = self._apply_confidence_and_uncertainty_adjustment(
            total_raw, option, tuple(utility_terms), context, profile
        )

        pos = [(t.name, t.contribution) for t in adj_terms if t.contribution > 0.0]
        neg = [(t.name, t.contribution) for t in adj_terms if t.contribution < 0.0]
        best_pos = max(pos, key=lambda x: x[1]) if pos else None
        worst_neg = min(neg, key=lambda x: x[1]) if neg else None

        if best_pos and worst_neg:
            explanation_summary = (
                f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}). "
                f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f})."
            )
        elif best_pos:
            explanation_summary = f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}); negligible penalties."
        elif worst_neg:
            explanation_summary = f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f}); no positive drivers."
        else:
            explanation_summary = "Global mission utility near zero; no dominant positive or negative driver."

        if is_stability_idle:
            explanation_summary += " Hold-steady / stability profile (damped signals, small floor)."

        explanation_summary += cua_note

        if all(k in params for k in _hz_required):
            explanation_summary += f" Horizon context: {hz_note}."

        stability_cost = clamp01(r_drift + (0.12 if is_stability_idle else 0.0))

        predicted_effects: dict[str, object] = {
            "U_global_raw": total_raw,
            "utility_mode": mode,
            "utility_adjustment_multiplier": net_mult,
            "policy_switching_cost": policy_switching,
            "stability_hysteresis_bonus": stab_hyst,
            "negative_information_adjustment": ni_delta,
            "negative_information_note": ni_note,
            "horizon_context_adjustment": hz_delta,
            "horizon_context_note": hz_note,
            "mission_stability_idle": is_stability_idle,
            "mission_search_or_recovery": is_search,
            "role_reassignment": role_changed,
            "distance_from_goal": self._compute_distance_from_goal(option, context),
        }

        feasible, constraint_violations = self._check_utility_feasibility(option, context)
        total_out = total_utility
        if not feasible:
            total_out = -1_000_000.0 + total_utility * 0.001
            explanation_summary = f"Infeasible ({', '.join(constraint_violations)}). " + explanation_summary

        return OptionEvaluation(
            option_id=str(getattr(option, "option_id", "")),
            option_type=str(getattr(option, "option_type", "")),
            feasible=feasible,
            constraint_violations=constraint_violations,
            predicted_effects=predicted_effects,
            utility_terms=adj_terms,
            total_utility=total_out,
            confidence_score=confidence,
            stability_cost=stability_cost,
            information_recovery_score=g_ir,
            explanation_summary=explanation_summary,
        )

    def _evaluate_rescue_option(
        self,
        option: object,
        runtime_models: object | None,
        context: object | None,
        mode: str,
    ) -> OptionEvaluation:
        _ = runtime_models
        profile = get_weight_profile(mode)
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}
        ot = self._option_type_lower(option)

        def pfloat(*keys: str, default: float = 0.0) -> float:
            for key in keys:
                if key in params:
                    return safe_float(params.get(key), default)
            return default

        def ptruth(*keys: str) -> bool:
            for key in keys:
                if key not in params:
                    continue
                v = params.get(key)
                if v is True:
                    return True
                if isinstance(v, (int, float)) and v != 0.0:
                    return True
                if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
                    return True
            return False

        p_victim = pfloat("victim_priority")
        c_support = pfloat("support_quality")
        t_delay = pfloat("expected_delay")
        r_route = pfloat("route_risk")
        u_victim = pfloat("victim_uncertainty")
        r_comm = pfloat("communication_risk")

        confidence = safe_float(getattr(option, "confidence", None), 0.5)

        is_confirmation = "confirm" in ot or ptruth("confirmation", "confirm_rescue")
        is_dispatch = "dispatch" in ot or "initiate" in ot or ptruth("dispatch", "initiate_rescue")
        is_delay = "delay" in ot or ptruth("delay_rescue", "postpone_rescue")

        t_delay_eff = t_delay
        if is_delay:
            mitigator = clamp01(max(u_victim, r_comm))
            t_delay_eff = t_delay * max(0.12, 1.0 - 0.65 * mitigator)

        u_eff = u_victim
        c_support_boost = 1.0
        if is_confirmation:
            u_eff = (
                u_victim
                * (1.0 - 0.62 * clamp01(u_victim))
                * (0.32 + 0.68 * clamp01(confidence))
            )
            c_support_boost = 1.0 + 0.22 * clamp01(u_victim)

        p_victim_eff = p_victim
        c_support_eff = c_support * c_support_boost
        r_route_eff = r_route
        if is_dispatch:
            r_route_eff = r_route * (1.0 + 1.15 * (1.0 - clamp01(confidence)))
            gate = 0.28 + 0.72 * clamp01(confidence)
            p_victim_eff = p_victim * gate
            c_support_eff = c_support_eff * gate

        w1 = profile.victim_weight
        w2 = profile.task_support_weight
        w3 = profile.switching_cost_weight
        w4 = profile.collision_risk_weight
        w5 = profile.uncertainty_reduction_weight
        w6 = profile.communication_weight

        raw_terms: list[tuple[str, float, float, str]] = [
            ("P_victim", w1, p_victim_eff, "victim priority"),
            ("C_support", w2, c_support_eff, "rescue support quality"),
            ("T_delay", -w3, t_delay_eff, "expected delay cost"),
            ("R_route", -w4, r_route_eff, "route / ingress risk"),
            ("U_victim_uncertainty", -w5, u_eff, "victim state uncertainty"),
            ("R_comm", -w6, r_comm, "communication risk"),
        ]

        utility_terms: list[UtilityTerm] = []
        for name, coeff, value, hint in raw_terms:
            contrib = coeff * value
            utility_terms.append(
                UtilityTerm(
                    name=name,
                    value=value,
                    weight=abs(coeff),
                    contribution=contrib,
                    explanation=hint,
                )
            )

        total_raw = sum(c * v for _, c, v, _ in raw_terms)
        total_utility, adj_terms, cua_note, net_mult = self._apply_confidence_and_uncertainty_adjustment(
            total_raw, option, tuple(utility_terms), context, profile
        )

        pos = [(t.name, t.contribution) for t in adj_terms if t.contribution > 0.0]
        neg = [(t.name, t.contribution) for t in adj_terms if t.contribution < 0.0]
        best_pos = max(pos, key=lambda x: x[1]) if pos else None
        worst_neg = min(neg, key=lambda x: x[1]) if neg else None

        if best_pos and worst_neg:
            explanation_summary = (
                f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}). "
                f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f})."
            )
        elif best_pos:
            explanation_summary = f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}); negligible penalties."
        elif worst_neg:
            explanation_summary = f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f}); no positive drivers."
        else:
            explanation_summary = "Rescue utility near zero; no dominant positive or negative driver."

        notes: list[str] = []
        if is_confirmation:
            notes.append("confirmation weighting (uncertainty/confidence-aware)")
        if is_dispatch:
            notes.append("dispatch/initiate caution (confidence and route risk)")
        if is_delay:
            notes.append("delay softened when uncertainty or comm risk is high")
        if notes:
            explanation_summary += " (" + "; ".join(notes) + ")."

        explanation_summary += cua_note

        stability_cost = clamp01(max(r_route_eff, r_comm * 0.85))

        predicted_effects: dict[str, object] = {
            "U_rescue_raw": total_raw,
            "utility_mode": mode,
            "utility_adjustment_multiplier": net_mult,
            "rescue_confirmation": is_confirmation,
            "rescue_dispatch": is_dispatch,
            "rescue_delay": is_delay,
            "distance_from_goal": self._compute_distance_from_goal(option, context),
        }

        feasible, constraint_violations = self._check_utility_feasibility(option, context)
        total_out = total_utility
        if not feasible:
            total_out = -1_000_000.0 + total_utility * 0.001
            explanation_summary = f"Infeasible ({', '.join(constraint_violations)}). " + explanation_summary

        return OptionEvaluation(
            option_id=str(getattr(option, "option_id", "")),
            option_type=str(getattr(option, "option_type", "")),
            feasible=feasible,
            constraint_violations=constraint_violations,
            predicted_effects=predicted_effects,
            utility_terms=adj_terms,
            total_utility=total_out,
            confidence_score=confidence,
            stability_cost=stability_cost,
            information_recovery_score=clamp01(1.0 - u_victim),
            explanation_summary=explanation_summary,
        )

    def _evaluate_communication_option(
        self,
        option: object,
        runtime_models: object | None,
        context: object | None,
        mode: str,
    ) -> OptionEvaluation:
        _ = runtime_models
        profile = get_weight_profile(mode)
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}
        ot = self._option_type_lower(option)

        def pfloat(*keys: str, default: float = 0.0) -> float:
            for key in keys:
                if key in params:
                    return safe_float(params.get(key), default)
            return default

        def ptruth(*keys: str) -> bool:
            for key in keys:
                if key not in params:
                    continue
                v = params.get(key)
                if v is True:
                    return True
                if isinstance(v, (int, float)) and v != 0.0:
                    return True
                if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
                    return True
            return False

        q_delivery = pfloat("delivery_quality")
        s_critical = pfloat("critical_support")
        q_sync = pfloat("sync_quality")
        relay_cost = pfloat("relay_cost")
        delay_cost = pfloat("delay_cost")

        delivery_confidence = safe_float(params.get("delivery_confidence"), 0.5)

        is_relay = "relay" in ot or ptruth("relay_mode")
        is_reduced = (
            "reduced" in ot
            or ptruth("reduced_communication", "reduce_bandwidth", "low_power_comm")
        )
        is_critical_priority = (
            ("critical" in ot and "priorit" in ot)
            or ptruth("prioritize_critical_messages", "critical_priority")
        )

        q_delivery_eff = q_delivery
        s_critical_eff = s_critical
        q_sync_eff = q_sync
        relay_eff = relay_cost
        delay_eff = delay_cost

        if is_critical_priority:
            s_critical_eff = s_critical * (1.0 + 0.6 * clamp01(s_critical))

        if is_relay:
            sync_del_min = clamp01(min(delivery_confidence, q_sync))
            relay_eff = relay_cost * (0.22 + 0.78 * sync_del_min)
            q_delivery_eff = q_delivery * (1.0 + 0.28 * (1.0 - sync_del_min))
            q_sync_eff = q_sync * (1.0 + 0.18 * (1.0 - sync_del_min))

        if is_reduced:
            pressure = clamp01(
                max(
                    pfloat("battery_pressure"),
                    pfloat("cost_pressure"),
                    safe_float(getattr(option, "cost_estimate", None), 0.0),
                )
            )
            if pressure > 0.35 and s_critical < 0.28:
                delay_eff = delay_cost * (0.32 + 0.55 * (1.0 - pressure))
                relay_eff *= 0.5 + 0.45 * (1.0 - pressure)
                q_delivery_eff *= 1.0 + 0.2 * pressure

        w1 = profile.communication_weight
        w2 = profile.task_support_weight
        w3 = profile.information_recovery_weight
        w4 = profile.battery_cost_weight
        w5 = profile.switching_cost_weight

        raw_terms: list[tuple[str, float, float, str]] = [
            ("Q_delivery", w1, q_delivery_eff, "message / payload delivery quality"),
            ("S_critical_support", w2, s_critical_eff, "critical traffic / support need"),
            ("Q_sync", w3, q_sync_eff, "state / sync quality"),
            ("Cost_relay", -w4, relay_eff, "relay / hop cost"),
            ("D_delay", -w5, delay_eff, "latency / delay cost"),
        ]

        confidence = safe_float(getattr(option, "confidence", None), 0.5)

        utility_terms: list[UtilityTerm] = []
        for name, coeff, value, hint in raw_terms:
            contrib = coeff * value
            utility_terms.append(
                UtilityTerm(
                    name=name,
                    value=value,
                    weight=abs(coeff),
                    contribution=contrib,
                    explanation=hint,
                )
            )

        total_raw = sum(c * v for _, c, v, _ in raw_terms)
        total_utility, adj_terms, cua_note, net_mult = self._apply_confidence_and_uncertainty_adjustment(
            total_raw, option, tuple(utility_terms), context, profile
        )

        pos = [(t.name, t.contribution) for t in adj_terms if t.contribution > 0.0]
        neg = [(t.name, t.contribution) for t in adj_terms if t.contribution < 0.0]
        best_pos = max(pos, key=lambda x: x[1]) if pos else None
        worst_neg = min(neg, key=lambda x: x[1]) if neg else None

        if best_pos and worst_neg:
            explanation_summary = (
                f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}). "
                f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f})."
            )
        elif best_pos:
            explanation_summary = f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}); negligible penalties."
        elif worst_neg:
            explanation_summary = f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f}); no positive drivers."
        else:
            explanation_summary = "Communication utility near zero; no dominant positive or negative driver."

        notes: list[str] = []
        if is_relay:
            notes.append("relay mode favors weak delivery confidence or sync")
        if is_reduced:
            notes.append("reduced comm when cost pressure high and support need low")
        if is_critical_priority:
            notes.append("critical-message priority scaling")
        if notes:
            explanation_summary += " (" + "; ".join(notes) + ")."

        explanation_summary += cua_note

        stability_cost = clamp01(max(relay_eff, delay_eff))

        predicted_effects: dict[str, object] = {
            "U_comm_raw": total_raw,
            "utility_mode": mode,
            "utility_adjustment_multiplier": net_mult,
            "comm_relay": is_relay,
            "comm_reduced": is_reduced,
            "comm_critical_priority": is_critical_priority,
            "distance_from_goal": self._compute_distance_from_goal(option, context),
        }

        feasible, constraint_violations = self._check_utility_feasibility(option, context)
        total_out = total_utility
        if not feasible:
            total_out = -1_000_000.0 + total_utility * 0.001
            explanation_summary = f"Infeasible ({', '.join(constraint_violations)}). " + explanation_summary

        return OptionEvaluation(
            option_id=str(getattr(option, "option_id", "")),
            option_type=str(getattr(option, "option_type", "")),
            feasible=feasible,
            constraint_violations=constraint_violations,
            predicted_effects=predicted_effects,
            utility_terms=adj_terms,
            total_utility=total_out,
            confidence_score=confidence,
            stability_cost=stability_cost,
            information_recovery_score=q_sync_eff,
            explanation_summary=explanation_summary,
        )

    def _evaluate_failsafe_option(
        self,
        option: object,
        runtime_models: object | None,
        context: object | None,
        mode: str,
    ) -> OptionEvaluation:
        _ = runtime_models
        profile = get_weight_profile(mode)
        params = getattr(option, "parameters", None)
        if not isinstance(params, dict):
            params = {}
        ot = self._option_type_lower(option)

        def pfloat(*keys: str, default: float = 0.0) -> float:
            for key in keys:
                if key in params:
                    return safe_float(params.get(key), default)
            return default

        def ptruth(*keys: str) -> bool:
            for key in keys:
                if key not in params:
                    continue
                v = params.get(key)
                if v is True:
                    return True
                if isinstance(v, (int, float)) and v != 0.0:
                    return True
                if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
                    return True
            return False

        v_mission = pfloat("mission_value")
        s_stability = pfloat("stability_bonus")
        r_energy = pfloat("energy_failure_risk")
        l_support = pfloat("support_loss")

        is_rtb = "return_to_base" in ot or ptruth("return_to_base")
        is_low_power = "low_power" in ot or "low_power_mode" in ot or ptruth("low_power_mode")
        is_rtb_lp = is_rtb or is_low_power

        is_search = "search" in ot or ptruth("search_mode")
        is_hold = "hold_position" in ot or ptruth("hold_position")

        v_eff = v_mission
        s_eff = s_stability
        r_energy_eff = r_energy
        l_eff = l_support

        if is_hold:
            safety = clamp01(
                max(
                    pfloat("safety_risk"),
                    pfloat("collision_risk"),
                    pfloat("route_risk"),
                )
            )
            recovery_need = clamp01(
                max(
                    pfloat("information_recovery"),
                    pfloat("recovery_value"),
                    pfloat("information_recovery_score"),
                )
            )
            hold_scale = 1.0 + 0.52 * safety - 0.48 * recovery_need
            v_eff = v_mission * max(0.32, hold_scale)
            s_eff = s_stability * (1.0 + 0.22 * safety) * max(0.38, 1.0 - 0.42 * recovery_need)

        if is_search:
            recovery_signal = clamp01(
                max(pfloat("information_recovery"), pfloat("recovery_value"))
            )
            v_eff *= 1.0 + 0.45 * recovery_signal

        if is_rtb_lp:
            er = clamp01(r_energy)
            v_eff *= 1.0 + 0.65 * er
            r_energy_eff = r_energy * max(0.1, 1.0 - 0.62 * er)
            s_eff *= 1.0 + 0.18 * er

        w1 = profile.task_support_weight
        w2 = profile.stability_weight
        w3 = profile.battery_cost_weight
        w4 = profile.communication_weight

        raw_terms: list[tuple[str, float, float, str]] = [
            ("V_mission", w1, v_eff, "conservative mission value retention"),
            ("S_stability", w2, s_eff, "stability / hold quality"),
            ("R_energy_failure", -w3, r_energy_eff, "energy depletion / failure risk"),
            ("L_support", -w4, l_eff, "lost coordination / support"),
        ]

        confidence = safe_float(getattr(option, "confidence", None), 0.5)

        utility_terms: list[UtilityTerm] = []
        for name, coeff, value, hint in raw_terms:
            contrib = coeff * value
            utility_terms.append(
                UtilityTerm(
                    name=name,
                    value=value,
                    weight=abs(coeff),
                    contribution=contrib,
                    explanation=hint,
                )
            )

        total_raw = sum(c * v for _, c, v, _ in raw_terms)
        total_utility, adj_terms, cua_note, net_mult = self._apply_confidence_and_uncertainty_adjustment(
            total_raw, option, tuple(utility_terms), context, profile
        )

        pos = [(t.name, t.contribution) for t in adj_terms if t.contribution > 0.0]
        neg = [(t.name, t.contribution) for t in adj_terms if t.contribution < 0.0]
        best_pos = max(pos, key=lambda x: x[1]) if pos else None
        worst_neg = min(neg, key=lambda x: x[1]) if neg else None

        if best_pos and worst_neg:
            explanation_summary = (
                f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}). "
                f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f})."
            )
        elif best_pos:
            explanation_summary = f"Strongest positive driver: {best_pos[0]} ({best_pos[1]:.4f}); negligible penalties."
        elif worst_neg:
            explanation_summary = f"Strongest penalty: {worst_neg[0]} ({worst_neg[1]:.4f}); no positive drivers."
        else:
            explanation_summary = "Fail-safe / battery utility near zero; no dominant driver."

        notes: list[str] = []
        if is_rtb_lp:
            notes.append("RTB / low-power favors high energy-failure risk")
        if is_search:
            notes.append("search mode favors information recovery signals")
        if is_hold:
            notes.append("hold-position trades safety vs recovery need")
        if notes:
            explanation_summary += " (" + "; ".join(notes) + ")."

        explanation_summary += cua_note

        stability_cost = clamp01(max(1.0 - s_eff, r_energy_eff))

        recovery_display = clamp01(
            max(pfloat("information_recovery"), pfloat("recovery_value"), pfloat("information_recovery_score"))
        )

        predicted_effects: dict[str, object] = {
            "U_battery_raw": total_raw,
            "utility_mode": mode,
            "utility_adjustment_multiplier": net_mult,
            "failsafe_rtb_low_power": is_rtb_lp,
            "failsafe_search": is_search,
            "failsafe_hold_position": is_hold,
            "distance_from_goal": self._compute_distance_from_goal(option, context),
        }

        feasible, constraint_violations = self._check_utility_feasibility(option, context)
        total_out = total_utility
        if not feasible:
            total_out = -1_000_000.0 + total_utility * 0.001
            explanation_summary = f"Infeasible ({', '.join(constraint_violations)}). " + explanation_summary

        return OptionEvaluation(
            option_id=str(getattr(option, "option_id", "")),
            option_type=str(getattr(option, "option_type", "")),
            feasible=feasible,
            constraint_violations=constraint_violations,
            predicted_effects=predicted_effects,
            utility_terms=adj_terms,
            total_utility=total_out,
            confidence_score=confidence,
            stability_cost=stability_cost,
            information_recovery_score=recovery_display,
            explanation_summary=explanation_summary,
        )


def build_utility_dashboard_summary(scored_options: Iterable[ScoredOption]) -> str:
    """Human-readable summary over a batch of ``ScoredOption`` results (no side effects)."""
    ranked = sorted(tuple(scored_options), key=lambda s: s.score, reverse=True)
    n = len(ranked)
    if n == 0:
        return "Utility dashboard: no options evaluated."

    best = ranked[0]
    pos_terms: Counter[str] = Counter()
    neg_terms: Counter[str] = Counter()
    conf_sum = 0.0
    infeasible = 0
    for s in ranked:
        ev = s.evaluation
        if not ev.feasible:
            infeasible += 1
        conf_sum += safe_float(ev.confidence_score, 0.0)
        for t in ev.utility_terms:
            if t.contribution > 0.0:
                pos_terms[t.name] += 1
            elif t.contribution < 0.0:
                neg_terms[t.name] += 1

    avg_conf = conf_sum / n

    def _fmt_counter(counter: Counter[str], limit: int = 5) -> str:
        if not counter:
            return "  (none)"
        return "\n".join(f"  {name}: {count}" for name, count in counter.most_common(limit))

    top_lines = "\n".join(
        f"  {i}. {s.evaluation.option_id} [{s.evaluation.option_type}] score={s.score:.4f} feasible={s.evaluation.feasible}"
        for i, s in enumerate(ranked[:5], start=1)
    )

    return "\n".join(
        [
            "Utility dashboard",
            f"- Evaluated options: {n}",
            f"- Best option id: {best.evaluation.option_id}",
            f"- Best option type: {best.evaluation.option_type}",
            f"- Best score: {best.score:.4f}",
            "- Top options (up to 5):",
            top_lines,
            f"- Infeasible options: {infeasible}",
            f"- Average confidence: {avg_conf:.4f}",
            "- Most common positive utility terms (count across options):",
            _fmt_counter(pos_terms),
            "- Most common penalty terms (count across options):",
            _fmt_counter(neg_terms),
        ]
    )


def clamp01(value: float) -> float:
    v = float(value)
    if v <= 0.0:
        return 0.0
    if v >= 1.0:
        return 1.0
    return v


def safe_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def option_to_basic_dict(option: object) -> dict[str, Any]:
    """Best-effort serialization for dataclass options (e.g. AdaptationOption) or id/type fallbacks."""
    if is_dataclass(option) and not isinstance(option, type):
        data: dict[str, Any] = asdict(option)
        scope = data.get("scope")
        if scope is not None and hasattr(scope, "value"):
            data["scope"] = scope.value
        return data
    out: dict[str, Any] = {}
    for key in ("option_id", "option_type", "target_entity"):
        if hasattr(option, key):
            out[key] = getattr(option, key)
    if out:
        return out
    return {"type": type(option).__name__}
