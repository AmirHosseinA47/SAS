"""Managing system: fail-safe planner.

Responsibility: choose safest adaptation under hazard/uncertainty by
producing ``FailSafeDecision``. Does not bypass execution to mutate
managed state; does not perform operational actions here.

TODO: Policy inputs from triggers, knowledge snapshots, operator overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..analysis.trigger_objects import TriggerBatch, TriggerSignal, normalize_triggers
from ..execution.failsafe_modes import FailSafeMode, FailSafeReason
from ..execution.fallback_strategy import FallbackStrategy, FallbackStrategyLibrary
from ..execution.safety_checker import SafetyChecker
from .decision_objects import FailSafeDecision
from .planner_selection import find_maintain_option, option_confidence, option_id, option_parameters
from .utility_evaluation import ScoredOption, UtilityEvaluation

_SEARCH_TRIGGER_MARKERS = ("SEARCH_MODE_REQUIRED", "INFORMATION_INSUFFICIENT")
_CRITICAL_TRIGGER_MARKERS = (
    "CRITICAL",
    "SAFETY",
    "RESOURCE",
    "COMMUNICATION",
    "BATTERY",
    "MAYDAY",
    "EMERGENCY",
)
_SEARCH_BONUS = 0.75
_CRITICAL_BONUS = 0.75
_MAINTAIN_FAILSAFE_MARKERS = (
    "maintain_current_failsafe",
    "maintain_failsafe_state",
    "hold_failsafe",
    "keep_failsafe_state",
)
_MODE_PREFERENCE_BONUS = 2.0
_MODE_PREFERRED_ACTIONS: dict[str, tuple[str, ...]] = {
    FailSafeMode.INFORMATION_RECOVERY.value: (
        "activate_search_mode",
        "search_mode",
        "information_recovery",
        "move_to_last_known_fire_region",
        "explore_high_uncertainty_regions",
    ),
    FailSafeMode.EMERGENCY.value: ("safe_hold", "return_to_base"),
    FailSafeMode.SAFETY_FIRST.value: (
        "safe_hold",
        "retreat_to_safe_region",
        "collision_avoidance_override",
    ),
    FailSafeMode.DEGRADED.value: ("critical_tasks_only", "reduce_mission_scope"),
}
_RESCUE_UNSAFE_PREFERRED = ("delay_rescue", "cancel_unsafe_rescue", "escalate_to_operator")


@dataclass
class _FallbackPlanOption:
    option_id: str
    option_type: str
    target_entity: str
    parameters: dict[str, Any]
    confidence: float = 0.55
    scope: str = "system"


@dataclass
class FailSafePlanner:
    """Adaptation planner: conservative intent (not direct actuation)."""

    utility_evaluator: UtilityEvaluation = field(default_factory=UtilityEvaluation)
    safety_checker: SafetyChecker = field(default_factory=SafetyChecker)
    fallback_library: FallbackStrategyLibrary = field(default_factory=FallbackStrategyLibrary)

    def plan(
        self,
        step_index: int,
        triggers: TriggerBatch | None = None,
        *,
        fail_safe_space: object | None = None,
        analysis_snapshot: object | None = None,
        runtime_models: object | None = None,
        context: object | None = None,
        timestamp: float | None = None,
    ) -> FailSafeDecision | None:
        """Produce fail-safe decision when warranted (planning only)."""
        ts = float(timestamp) if timestamp is not None else 0.0
        analysis_input = _analysis_input(analysis_snapshot, triggers)
        reasons = self.safety_checker.extract_fail_safe_reasons(
            analysis_snapshot=analysis_input,
            runtime_models=runtime_models,
        )
        step11_active = bool(reasons)
        classified_mode = (
            self.safety_checker.classify_mode(
                reasons,
                current_mode=_resolve_utility_mode(analysis_snapshot) or FailSafeMode.NORMAL.value,
            )
            if step11_active
            else FailSafeMode.NORMAL.value
        )

        options = _fail_safe_options(fail_safe_space)
        fail_safe_options = tuple(o for o in options if _is_fail_safe_option(o))

        mode = _resolve_utility_mode(analysis_snapshot)
        planning_context = context if context is not None else analysis_snapshot

        scored = self.utility_evaluator.score_options(
            fail_safe_options,
            runtime_models=runtime_models,
            context=planning_context,
            mode=mode,
        )
        if step11_active and _needs_fallback_options(fail_safe_options, scored):
            affected_entities = _collect_affected_entities(analysis_input, triggers)
            strategies = self.fallback_library.strategies_for_mode(
                classified_mode,
                reasons,
                affected_entities,
                ts,
            )
            fallback_options = tuple(_fallback_option_from_strategy(s) for s in strategies)
            fail_safe_options = fail_safe_options + fallback_options
            scored = self.utility_evaluator.score_options(
                fail_safe_options,
                runtime_models=runtime_models,
                context=planning_context,
                mode=mode,
            )

        policy = _fail_safe_policy(triggers, analysis_snapshot, planning_context)
        if step11_active:
            policy = {
                **policy,
                "step11": True,
                "classified_mode": classified_mode,
                "reasons": tuple(reasons),
                "preferred_actions": _preferred_actions(classified_mode, reasons),
                "override_utility": self.safety_checker.should_override_utility(
                    reasons,
                    classified_mode,
                ),
            }

        if step11_active and policy.get("override_utility"):
            selected = _select_fail_safe_option_mode_override(scored, fail_safe_options, policy)
        else:
            selected = _select_fail_safe_option(scored, fail_safe_options, policy)
        comparison_text = _comparison_summary_text(scored, policy)

        decision_id = f"fs-{step_index}"
        if not selected:
            return FailSafeDecision(
                decision_id=decision_id,
                comparison_summary={"summary": comparison_text},
                explanation="No fail-safe options available; maintain current fail-safe state.",
            )

        params = option_parameters(selected)
        scored_entry = _scored_entry_for(scored, selected)
        explanation = (
            scored_entry.evaluation.explanation_summary
            if scored_entry is not None
            else str(params.get("explanation", "") or "")
        )
        pref_note = _preference_note(selected, policy)
        if pref_note:
            explanation = f"{pref_note} {explanation}".strip()
        if step11_active:
            step11_note = _step11_preference_note(classified_mode, reasons)
            if step11_note:
                explanation = f"{step11_note} {explanation}".strip()

        confidence = (
            scored_entry.evaluation.confidence_score
            if scored_entry is not None
            else option_confidence(selected)
        )

        fail_safe_action = _fail_safe_action(selected, params)
        search_mode_active = _search_mode_active(selected, params)
        mission_mode = str(params.get("mission_mode", "") or "")
        if step11_active:
            fail_safe_action, search_mode_active, mission_mode = _apply_step11_decision_fields(
                classified_mode,
                reasons,
                fail_safe_action,
                search_mode_active,
                mission_mode,
                selected,
                params,
            )

        uncertainty_context = _uncertainty_context(params, analysis_snapshot)
        if step11_active:
            uncertainty_context = {
                **uncertainty_context,
                "fail_safe_mode": classified_mode,
                "fail_safe_reasons": list(reasons),
            }

        return FailSafeDecision(
            decision_id=decision_id,
            selected_option_id=option_id(selected),
            fail_safe_action=fail_safe_action,
            search_mode_active=search_mode_active,
            target_region=str(params.get("target_region", "") or ""),
            mission_mode=mission_mode,
            actions=(dict(params),),
            confidence_score=confidence,
            uncertainty_context=uncertainty_context,
            comparison_summary={"summary": comparison_text},
            explanation=explanation,
        )


def _fail_safe_options(space: object | None) -> tuple[object, ...]:
    if space is None:
        return ()
    options = getattr(space, "options", None)
    if options is not None:
        return tuple(options)
    if isinstance(space, (list, tuple)):
        return tuple(space)
    return ()


def _is_fail_safe_option(option: object) -> bool:
    if isinstance(option, _FallbackPlanOption):
        return True
    if type(option).__name__ in {"FailSafeAdaptationOption", "FailsafeAdaptationOption"}:
        return True
    scope = _scope_value(option)
    if scope == "system":
        return True
    ot = str(getattr(option, "option_type", "") or "").lower()
    return any(token in ot for token in ("fail_safe", "failsafe", "fail-safe", "search", "return_to_base"))


def _scope_value(option: object) -> str | None:
    scope = getattr(option, "scope", None)
    if scope is None:
        return None
    raw = getattr(scope, "value", scope)
    return str(raw).lower()


def _fail_safe_policy(
    triggers: TriggerBatch | None,
    analysis: object | None,
    context: object | None,
) -> dict[str, bool]:
    names = _trigger_names(triggers, analysis, context)
    prefer_search = any(_matches_trigger_marker(name, _SEARCH_TRIGGER_MARKERS) for name in names)
    prefer_critical = any(_matches_trigger_marker(name, _CRITICAL_TRIGGER_MARKERS) for name in names)
    return {"prefer_search": prefer_search, "prefer_critical": prefer_critical}


def _trigger_names(
    triggers: TriggerBatch | None,
    analysis: object | None,
    context: object | None,
) -> set[str]:
    names: set[str] = set()
    for source in (triggers, analysis, context):
        if source is None:
            continue
        batch = normalize_triggers(source)
        for signal in batch.triggers:
            name = signal.name.strip()
            if name:
                names.add(name)
    return names


def _iter_triggers(batch: object) -> tuple[TriggerSignal, ...]:
    return normalize_triggers(batch).triggers


def _trigger_label(trigger: object) -> str:
    normalized = normalize_triggers(trigger)
    if normalized.triggers:
        return normalized.triggers[0].name
    if isinstance(trigger, dict):
        for key in ("trigger_type", "name", "kind", "code", "id"):
            raw = trigger.get(key)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
        return str(trigger)
    for attr in ("trigger_type", "name", "kind", "code", "id"):
        value = getattr(trigger, attr, None)
        if value is None:
            continue
        raw = getattr(value, "value", value)
        text = str(raw).strip()
        if text:
            return text
    return str(trigger)


def _matches_trigger_marker(name: str, markers: tuple[str, ...]) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in markers)


def _select_fail_safe_option(
    scored: tuple[ScoredOption, ...],
    options: tuple[object, ...],
    policy: dict[str, bool],
) -> object | None:
    feasible = [entry for entry in scored if entry.evaluation.feasible]
    if feasible:
        return max(feasible, key=lambda entry: (_preference_adjustment(entry, policy), entry.score)).option
    return _find_maintain_fail_safe_option(options)


def _preference_adjustment(entry: ScoredOption, policy: dict[str, bool]) -> float:
    bonus = 0.0
    option = entry.option
    params = option_parameters(option)
    ot = str(getattr(option, "option_type", "") or "").lower()

    if policy.get("prefer_search") and _is_search_option(ot, params):
        bonus += _SEARCH_BONUS
    if policy.get("prefer_critical") and _is_critical_fail_safe_option(ot, params):
        bonus += _CRITICAL_BONUS
    return bonus


def _is_search_option(option_type: str, params: dict[str, Any]) -> bool:
    if "search" in option_type:
        return True
    return _is_truthy(params.get("search_mode"))


def _is_critical_fail_safe_option(option_type: str, params: dict[str, Any]) -> bool:
    critical_tokens = (
        "critical",
        "emergency",
        "evade",
        "escape",
        "mayday",
        "return_to_base",
        "low_power",
    )
    if any(token in option_type for token in critical_tokens):
        return True
    return _is_truthy(params.get("critical_trigger")) or _is_truthy(params.get("emergency"))


def _find_maintain_fail_safe_option(options: tuple[object, ...]) -> object | None:
    for option in options:
        ot = str(getattr(option, "option_type", "") or "").lower()
        if any(marker in ot for marker in _MAINTAIN_FAILSAFE_MARKERS):
            return option
        params = option_parameters(option)
        for key in _MAINTAIN_FAILSAFE_MARKERS:
            if _is_truthy(params.get(key)):
                return option
    return find_maintain_option(options)


def _scored_entry_for(
    scored: tuple[ScoredOption, ...],
    selected: object,
) -> ScoredOption | None:
    for entry in scored:
        if entry.option is selected:
            return entry
    sel_id = option_id(selected)
    if not sel_id:
        return None
    for entry in scored:
        if entry.evaluation.option_id == sel_id:
            return entry
    return None


def _comparison_summary_text(scored: tuple[ScoredOption, ...], policy: dict[str, Any]) -> str:
    if not scored:
        return "Fail-safe planner: no options evaluated."
    lines = [
        "Fail-safe option comparison",
        f"- Candidates evaluated: {len(scored)}",
        f"- Prefer search-mode options: {policy.get('prefer_search', False)}",
        f"- Prefer critical fail-safe options: {policy.get('prefer_critical', False)}",
    ]
    if policy.get("step11"):
        lines.append(f"- Classified fail-safe mode: {policy.get('classified_mode', 'normal')}")
        lines.append(f"- Fail-safe reasons: {', '.join(policy.get('reasons', ())) or 'none'}")
        lines.append(f"- Utility override active: {policy.get('override_utility', False)}")
    for i, entry in enumerate(scored[:5], start=1):
        ev = entry.evaluation
        adj = _preference_adjustment(entry, policy)
        lines.append(
            f"  {i}. {ev.option_id} [{ev.option_type}] score={entry.score:.4f} "
            f"pref_bonus={adj:.3f} feasible={ev.feasible}"
        )
    best = scored[0]
    lines.append(f"- Top utility-ranked id: {best.evaluation.option_id} (feasible={best.evaluation.feasible})")
    return "\n".join(lines)


def _preference_note(option: object, policy: dict[str, bool]) -> str:
    params = option_parameters(option)
    ot = str(getattr(option, "option_type", "") or "").lower()
    notes: list[str] = []
    if policy.get("prefer_search") and _is_search_option(ot, params):
        notes.append("search-mode policy applied")
    if policy.get("prefer_critical") and _is_critical_fail_safe_option(ot, params):
        notes.append("critical fail-safe policy applied")
    if not notes:
        return ""
    return "; ".join(notes) + "."


def _resolve_utility_mode(analysis_snapshot: object | None) -> str | None:
    if analysis_snapshot is None:
        return None
    for key in ("utility_mode", "operational_mode", "mission_mode"):
        value = _snapshot_value(analysis_snapshot, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _snapshot_value(snapshot: object, key: str) -> object | None:
    if isinstance(snapshot, dict):
        return snapshot.get(key)
    return getattr(snapshot, key, None)


def _fail_safe_action(option: object, params: dict[str, Any]) -> str:
    for key in ("failsafe_action", "fail_safe_action"):
        value = params.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return str(getattr(option, "option_type", "") or "")


def _search_mode_active(option: object, params: dict[str, Any]) -> bool:
    if _is_truthy(params.get("search_mode")):
        return True
    ot = str(getattr(option, "option_type", "") or "").lower()
    if "search" in ot:
        return True
    mission_mode = str(params.get("mission_mode", "") or "").lower()
    return mission_mode in {"search", "information_recovery"}


def _uncertainty_context(params: dict[str, Any], analysis_snapshot: object | None) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key in ("uncertainty_level", "knowledge_confidence", "information_collapse"):
        if key in params:
            context[key] = params[key]
    if analysis_snapshot is not None:
        for key in ("uncertainty_level", "knowledge_confidence", "information_collapse"):
            if key in context:
                continue
            value = _snapshot_value(analysis_snapshot, key)
            if value is not None:
                context[key] = value
    return context


def _is_truthy(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value != 0.0:
        return True
    if isinstance(value, str) and value.strip().lower() in ("1", "true", "yes", "on"):
        return True
    return False


def _analysis_input(
    analysis_snapshot: object | None,
    triggers: TriggerBatch | None,
) -> object | None:
    if analysis_snapshot is None:
        if triggers is None:
            return None
        return normalize_triggers(triggers)
    if normalize_triggers(analysis_snapshot).triggers:
        return analysis_snapshot
    if triggers is not None:
        return triggers
    return analysis_snapshot


def _needs_fallback_options(
    options: tuple[object, ...],
    scored: tuple[ScoredOption, ...],
) -> bool:
    if not options:
        return True
    feasible = [entry for entry in scored if entry.evaluation.feasible]
    if not feasible:
        return True
    best_score = max((entry.score for entry in feasible), default=0.0)
    return best_score <= 0.0


def _collect_affected_entities(
    analysis_snapshot: object | None,
    triggers: TriggerBatch | None,
) -> tuple[str, ...]:
    entities: list[str] = []
    _extend_entity_ids(entities, _snapshot_value(analysis_snapshot, "affected_entities"))
    for source in (analysis_snapshot, triggers):
        if source is None:
            continue
        batch = normalize_triggers(source)
        for signal in batch.triggers:
            raw_entities = signal.metadata.get("affected_entities")
            _extend_entity_ids(entities, raw_entities)
    return tuple(entities)


def _extend_entity_ids(target: list[str], raw_entities: object | None) -> None:
    if raw_entities is None:
        return
    if isinstance(raw_entities, str):
        if raw_entities and raw_entities not in target:
            target.append(raw_entities)
        return
    for entity in raw_entities:
        entity_id = str(entity)
        if entity_id and entity_id not in target:
            target.append(entity_id)


def _fallback_option_from_strategy(strategy: FallbackStrategy) -> _FallbackPlanOption:
    params = dict(FallbackStrategyLibrary.strategy_to_fail_safe_action(strategy))
    params.update(
        {
            "fail_safe_action": strategy.action,
            "mission_mode": strategy.mode,
            "target_entity": strategy.target_entity,
            "fallback_strategy": True,
            "explanation": strategy.explanation,
        }
    )
    if strategy.mode == FailSafeMode.INFORMATION_RECOVERY.value:
        params["search_mode"] = True
    return _FallbackPlanOption(
        option_id=strategy.strategy_id,
        option_type=f"fail_safe_{strategy.action}",
        target_entity=strategy.target_entity,
        parameters=params,
    )


def _preferred_actions(classified_mode: str, reasons: tuple[str, ...]) -> tuple[str, ...]:
    preferred = list(_MODE_PREFERRED_ACTIONS.get(classified_mode, ()))
    reason_set = {reason.strip().lower().replace("-", "_") for reason in reasons}
    if FailSafeReason.RESCUE_ROUTE_UNSAFE.value in reason_set:
        preferred.extend(_RESCUE_UNSAFE_PREFERRED)
    return tuple(dict.fromkeys(preferred))


def _select_fail_safe_option_mode_override(
    scored: tuple[ScoredOption, ...],
    options: tuple[object, ...],
    policy: dict[str, Any],
) -> object | None:
    feasible = [entry for entry in scored if entry.evaluation.feasible]
    if feasible:
        return max(
            feasible,
            key=lambda entry: (
                _mode_preference_bonus(entry.option, policy),
                _preference_adjustment(entry, policy),
                entry.score,
            ),
        ).option
    return _select_preferred_fallback_option(options, policy) or _find_maintain_fail_safe_option(options)


def _select_preferred_fallback_option(
    options: tuple[object, ...],
    policy: dict[str, Any],
) -> object | None:
    preferred = policy.get("preferred_actions", ())
    best: object | None = None
    best_rank = -1
    for option in options:
        rank = _mode_preference_bonus(option, policy)
        if rank > best_rank:
            best = option
            best_rank = rank
    if best_rank > 0:
        return best
    for option in options:
        if isinstance(option, _FallbackPlanOption):
            return option
    return None


def _mode_preference_bonus(option: object, policy: dict[str, Any]) -> float:
    preferred = policy.get("preferred_actions", ())
    if not preferred:
        return 0.0
    params = option_parameters(option)
    action = _fail_safe_action(option, params).lower()
    option_type = str(getattr(option, "option_type", "") or "").lower()
    for index, marker in enumerate(preferred):
        marker_key = marker.lower()
        if marker_key in action or marker_key in option_type:
            return _MODE_PREFERENCE_BONUS + (len(preferred) - index) * 0.01
    return 0.0


def _apply_step11_decision_fields(
    classified_mode: str,
    reasons: tuple[str, ...],
    fail_safe_action: str,
    search_mode_active: bool,
    mission_mode: str,
    selected: object,
    params: dict[str, Any],
) -> tuple[str, bool, str]:
    preferred = _preferred_actions(classified_mode, reasons)
    if classified_mode == FailSafeMode.INFORMATION_RECOVERY.value:
        search_mode_active = True
        mission_mode = "information_recovery"
        if not _action_matches_preferred(fail_safe_action, preferred):
            fail_safe_action = _pick_preferred_action(selected, params, preferred) or "activate_search_mode"
    elif classified_mode == FailSafeMode.EMERGENCY.value:
        if not _action_matches_preferred(fail_safe_action, preferred):
            fail_safe_action = _pick_preferred_action(selected, params, preferred) or "safe_hold"
    elif classified_mode == FailSafeMode.SAFETY_FIRST.value:
        if not _action_matches_preferred(fail_safe_action, preferred):
            fail_safe_action = _pick_preferred_action(selected, params, preferred) or "safe_hold"
    elif classified_mode == FailSafeMode.DEGRADED.value:
        if not _action_matches_preferred(fail_safe_action, preferred):
            fail_safe_action = (
                _pick_preferred_action(selected, params, preferred) or "critical_tasks_only"
            )
    reason_set = {reason.strip().lower().replace("-", "_") for reason in reasons}
    if FailSafeReason.RESCUE_ROUTE_UNSAFE.value in reason_set and not _action_matches_preferred(
        fail_safe_action,
        _RESCUE_UNSAFE_PREFERRED,
    ):
        fail_safe_action = (
            _pick_preferred_action(selected, params, _RESCUE_UNSAFE_PREFERRED) or fail_safe_action
        )
    return fail_safe_action, search_mode_active, mission_mode


def _action_matches_preferred(action: str, preferred: tuple[str, ...]) -> bool:
    action_key = action.strip().lower().replace("-", "_")
    return any(marker in action_key for marker in preferred)


def _pick_preferred_action(
    selected: object,
    params: dict[str, Any],
    preferred: tuple[str, ...],
) -> str:
    candidates = [
        _fail_safe_action(selected, params),
        str(getattr(selected, "option_type", "") or ""),
    ]
    for candidate in candidates:
        action_key = candidate.strip().lower().replace("-", "_")
        for marker in preferred:
            if marker in action_key:
                return marker
    return preferred[0] if preferred else ""


def _step11_preference_note(classified_mode: str, reasons: tuple[str, ...]) -> str:
    reason_text = ", ".join(reasons) if reasons else "none"
    return f"step11 mode={classified_mode}; reasons={reason_text}."
