"""Managing system: rescue planner.

Responsibility: choose what rescue coordination should change (assignments,
feasibility flags) via ``RescueDecision``. Does not update managed
operational firefighter state directly, execution applies outcomes after
planning.

TODO: Coordinate with ``knowledge.firefighter_model`` and route-risk evaluation.

Pairing policy (closest available firefighter) lives in
``select_rescue_assignment``; ``RescueExecutor`` applies outcomes via
``apply_physical_rescue_command``. ``wildfire_model`` supplies read-only
``get_rescue_operational_snapshot()`` and enqueues incidents only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..analysis.trigger_objects import TriggerBatch
from .decision_objects import RescueDecision
from .planner_selection import find_maintain_option, option_confidence, option_id, option_parameters
from .mission_goal_integration import resolve_utility_mode as _resolve_utility_mode_from_goals
from .utility_evaluation import ScoredOption, UtilityEvaluation, safe_float

_NON_RESCUE_SCOPES = frozenset({"global", "local", "system"})
_NON_RESCUE_TYPE_MARKERS = ("fail_safe", "failsafe", "fail-safe", "mission", "path", "movement")
_MAINTAIN_RESCUE_MARKERS = (
    "maintain_current_rescue",
    "maintain_rescue_state",
    "hold_rescue",
    "keep_rescue_state",
)
_DELAY_CANCEL_MARKERS = ("delay", "cancel", "postpone", "abort")
_LOW_VICTIM_CONFIDENCE = 0.45
_HIGH_UNCERTAINTY = 0.55
_HIGH_ROUTE_RISK = 0.55
_HIGH_COMM_RISK = 0.55
_CONFIRMATION_BONUS = 0.75
_DELAY_CANCEL_BONUS = 0.75

# Geographic isolation: fuel 7-10 depletes every FIRE_SPREAD_SPEED=3 steps, so a
# burning barrier lasts ~21-30 steps before the cell is burnt (passable). N=30
# exceeds one full burn-out so a temporary front does not permanently write off
# a victim that a firefighter can still reach.
UNREACHABLE_STREAK_STEPS = 30
# Never-detected / never-approached: UAVs can first find a still-candidate
# victim late (A/west seed 101 detects victim_0 at step 108). This timeout must
# exceed that search window — and the 120-step cutoff that zeroed D/west 505
# rescues — while still firing inside the 240-step cap (240 - 30).
UNDETECTED_STREAK_STEPS = 210
UNREACHABLE_CAUSE_GEOGRAPHIC = "geographically_isolated"
UNREACHABLE_CAUSE_UNDETECTED = "never_detected"
_UNREACHABLE_ESCAPE_TERMINAL = frozenset({"rescued", "dead", "unreachable", "cancelled"})


@dataclass
class RescuePlanner:
    """Adaptation planner: rescue coordination intent (not operational execution)."""

    utility_evaluator: UtilityEvaluation = field(default_factory=UtilityEvaluation)

    def plan(
        self,
        step_index: int,
        triggers: TriggerBatch | None = None,
        *,
        rescue_space: object | None = None,
        analysis_snapshot: object | None = None,
        runtime_models: object | None = None,
        context: object | None = None,
        timestamp: float | None = None,
    ) -> RescueDecision | None:
        """Produce a rescue decision from rescue adaptation options (planning only)."""
        _ = triggers
        _ = timestamp

        options = _rescue_options(rescue_space)
        rescue_options = tuple(o for o in options if _is_rescue_option(o))

        mode = _resolve_utility_mode_from_goals(analysis_snapshot, runtime_models)
        planning_context = context if context is not None else analysis_snapshot

        scored = self.utility_evaluator.score_options(
            rescue_options,
            runtime_models=runtime_models,
            context=planning_context,
            mode=mode,
        )
        signals = _rescue_signals(analysis_snapshot, planning_context, rescue_options)
        selected = _select_rescue_option(scored, rescue_options, signals)
        comparison_text = _comparison_summary_text(scored, signals)

        decision_id = f"r-{step_index}"
        if not selected:
            return RescueDecision(
                decision_id=decision_id,
                comparison_summary={"summary": comparison_text},
                explanation="No rescue options available; maintain current rescue state.",
            )

        params = option_parameters(selected)
        scored_entry = _scored_entry_for(scored, selected)
        explanation = (
            scored_entry.evaluation.explanation_summary
            if scored_entry is not None
            else str(params.get("explanation", "") or "")
        )
        pref_note = _preference_note(selected, signals)
        if pref_note:
            explanation = f"{pref_note} {explanation}".strip()

        confidence = (
            scored_entry.evaluation.confidence_score
            if scored_entry is not None
            else option_confidence(selected)
        )

        return RescueDecision(
            decision_id=decision_id,
            selected_option_id=option_id(selected),
            rescue_action=_rescue_action(selected, params),
            victim_id=_entity_id(selected, params, "victim_id", "victim"),
            firefighter_id=_entity_id(selected, params, "firefighter_id", "firefighter"),
            route_choice=str(params.get("route_choice", "") or ""),
            payload=dict(params),
            confidence_score=confidence,
            uncertainty_context=_uncertainty_context(params, analysis_snapshot),
            comparison_summary={"summary": comparison_text},
            explanation=explanation,
        )


def _rescue_options(space: object | None) -> tuple[object, ...]:
    if space is None:
        return ()
    options = getattr(space, "options", None)
    if options is not None:
        return tuple(options)
    if isinstance(space, (list, tuple)):
        return tuple(space)
    return ()


def _is_rescue_option(option: object) -> bool:
    if type(option).__name__ == "RescueAdaptationOption":
        return not _is_clearly_non_rescue(option)
    if _is_clearly_non_rescue(option):
        return False
    scope = _scope_value(option)
    if scope == "rescue":
        return True
    ot = str(getattr(option, "option_type", "") or "").lower()
    return "rescue" in ot or "victim" in ot or "confirm" in ot or "dispatch" in ot


def _is_clearly_non_rescue(option: object) -> bool:
    scope = _scope_value(option)
    if scope in _NON_RESCUE_SCOPES:
        return True
    ot = str(getattr(option, "option_type", "") or "").lower()
    return any(marker in ot for marker in _NON_RESCUE_TYPE_MARKERS)


def _scope_value(option: object) -> str | None:
    scope = getattr(option, "scope", None)
    if scope is None:
        return None
    raw = getattr(scope, "value", scope)
    return str(raw).lower()


def _rescue_signals(
    analysis: object | None,
    context: object | None,
    options: tuple[object, ...],
) -> dict[str, float]:
    signals = {
        "victim_confidence": _signal_value(
            analysis,
            context,
            ("victim_confidence", "knowledge_confidence"),
            default=0.5,
        ),
        "uncertainty": _signal_value(
            analysis,
            context,
            ("uncertainty_level", "victim_uncertainty"),
            default=0.0,
        ),
        "route_risk": _signal_value(analysis, context, ("route_risk",), default=0.0),
        "communication_risk": _signal_value(
            analysis,
            context,
            ("communication_risk", "comm_risk"),
            default=0.0,
        ),
    }
    for option in options:
        params = option_parameters(option)
        signals["victim_confidence"] = min(
            signals["victim_confidence"],
            safe_float(params.get("victim_confidence"), signals["victim_confidence"]),
        )
        signals["uncertainty"] = max(
            signals["uncertainty"],
            safe_float(params.get("victim_uncertainty"), 0.0),
            safe_float(params.get("uncertainty_level"), 0.0),
        )
        signals["route_risk"] = max(signals["route_risk"], safe_float(params.get("route_risk"), 0.0))
        signals["communication_risk"] = max(
            signals["communication_risk"],
            safe_float(params.get("communication_risk"), 0.0),
        )
    return signals


def _signal_value(
    analysis: object | None,
    context: object | None,
    keys: tuple[str, ...],
    *,
    default: float,
) -> float:
    for source in (context, analysis):
        if source is None:
            continue
        for key in keys:
            raw = _snapshot_value(source, key)
            if raw is not None:
                return safe_float(raw, default)
    return default


def _select_rescue_option(
    scored: tuple[ScoredOption, ...],
    options: tuple[object, ...],
    signals: dict[str, float],
) -> object | None:
    feasible = [entry for entry in scored if entry.evaluation.feasible]
    if feasible:
        return max(feasible, key=lambda entry: (_preference_adjustment(entry, signals), entry.score)).option
    return _find_maintain_rescue_option(options)


def _preference_adjustment(entry: ScoredOption, signals: dict[str, float]) -> float:
    bonus = 0.0
    option = entry.option
    params = option_parameters(option)
    ot = str(getattr(option, "option_type", "") or "").lower()

    low_confidence = signals["victim_confidence"] < _LOW_VICTIM_CONFIDENCE
    high_uncertainty = signals["uncertainty"] >= _HIGH_UNCERTAINTY
    if low_confidence or high_uncertainty:
        if _is_confirmation_option(ot, params):
            bonus += _CONFIRMATION_BONUS

    high_route_risk = signals["route_risk"] >= _HIGH_ROUTE_RISK
    high_comm_risk = signals["communication_risk"] >= _HIGH_COMM_RISK
    if high_route_risk or high_comm_risk:
        if _is_delay_or_cancel_option(ot, params):
            bonus += _DELAY_CANCEL_BONUS

    return bonus


def _is_confirmation_option(option_type: str, params: dict[str, Any]) -> bool:
    if "confirm" in option_type:
        return True
    return _is_truthy(params.get("confirmation")) or _is_truthy(params.get("confirm_rescue"))


def _is_delay_or_cancel_option(option_type: str, params: dict[str, Any]) -> bool:
    if any(token in option_type for token in _DELAY_CANCEL_MARKERS):
        return True
    # The real options carry the decision as a VALUE under "rescue_action"
    # (``rescue_decision`` + ``{"rescue_action": "delay_rescue"}``), not as a key and
    # not in ``option_type`` — match the same way ``_rescue_action`` and
    # ``RescueExecutor._classify_rescue_action`` already do.
    action = str(params.get("rescue_action", "") or "").strip().lower()
    if any(token in action for token in _DELAY_CANCEL_MARKERS):
        return True
    return _is_truthy(params.get("delay_rescue")) or _is_truthy(params.get("postpone_rescue")) or _is_truthy(
        params.get("cancel_rescue")
    )


def _find_maintain_rescue_option(options: tuple[object, ...]) -> object | None:
    for option in options:
        ot = str(getattr(option, "option_type", "") or "").lower()
        if any(marker in ot for marker in _MAINTAIN_RESCUE_MARKERS):
            return option
        params = option_parameters(option)
        for key in _MAINTAIN_RESCUE_MARKERS:
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


def _comparison_summary_text(scored: tuple[ScoredOption, ...], signals: dict[str, float]) -> str:
    if not scored:
        return "Rescue planner: no options evaluated."
    lines = [
        "Rescue option comparison",
        f"- Candidates evaluated: {len(scored)}",
        (
            "- Signals: "
            f"victim_confidence={signals['victim_confidence']:.3f}, "
            f"uncertainty={signals['uncertainty']:.3f}, "
            f"route_risk={signals['route_risk']:.3f}, "
            f"communication_risk={signals['communication_risk']:.3f}"
        ),
    ]
    for i, entry in enumerate(scored[:5], start=1):
        ev = entry.evaluation
        adj = _preference_adjustment(entry, signals)
        lines.append(
            f"  {i}. {ev.option_id} [{ev.option_type}] score={entry.score:.4f} "
            f"pref_bonus={adj:.3f} feasible={ev.feasible}"
        )
    best = scored[0]
    lines.append(f"- Top utility-ranked id: {best.evaluation.option_id} (feasible={best.evaluation.feasible})")
    return "\n".join(lines)


def _preference_note(option: object, signals: dict[str, float]) -> str:
    params = option_parameters(option)
    ot = str(getattr(option, "option_type", "") or "").lower()
    notes: list[str] = []
    if (signals["victim_confidence"] < _LOW_VICTIM_CONFIDENCE or signals["uncertainty"] >= _HIGH_UNCERTAINTY) and (
        _is_confirmation_option(ot, params)
    ):
        notes.append("confirmation-first policy applied")
    if (signals["route_risk"] >= _HIGH_ROUTE_RISK or signals["communication_risk"] >= _HIGH_COMM_RISK) and (
        _is_delay_or_cancel_option(ot, params)
    ):
        notes.append("delay/cancel favored under route or communication risk")
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


def _rescue_action(option: object, params: dict[str, Any]) -> str:
    action = params.get("rescue_action")
    if action is not None and str(action).strip():
        return str(action).strip()
    return str(getattr(option, "option_type", "") or "")


def _entity_id(option: object, params: dict[str, Any], param_key: str, attr_key: str) -> str:
    value = params.get(param_key)
    if value is not None and str(value).strip():
        return str(value).strip()
    entity = getattr(option, attr_key, None)
    if entity is not None and str(entity).strip():
        return str(entity).strip()
    return ""


def _uncertainty_context(params: dict[str, Any], analysis_snapshot: object | None) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key in ("uncertainty_level", "victim_uncertainty", "knowledge_confidence", "victim_confidence"):
        if key in params:
            context[key] = params[key]
    if analysis_snapshot is not None:
        for key in ("uncertainty_level", "victim_uncertainty", "knowledge_confidence", "victim_confidence"):
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


def _manhattan_distance(
    pos_a: tuple[int, int] | tuple[float, float],
    pos_b: tuple[int, int] | tuple[float, float],
) -> int:
    return abs(int(pos_a[0]) - int(pos_b[0])) + abs(int(pos_a[1]) - int(pos_b[1]))


def _normalize_reason(reason: str) -> str:
    return str(reason or "").strip().lower()


def _is_initial_reason(reason: str) -> bool:
    reason_l = _normalize_reason(reason)
    return reason_l in ("initial", "test_initial", "victim_confirmed") or (
        "initial" in reason_l and "replacement" not in reason_l
    )


def _is_terminal_flags(flags: dict[str, Any]) -> bool:
    if bool(flags.get("terminal", False)):
        return True
    status = str(flags.get("status", "") or "").strip().lower()
    return status in _UNREACHABLE_ESCAPE_TERMINAL


def _is_productively_served(flags: dict[str, Any]) -> bool:
    if bool(flags.get("assigned", False)) and bool(flags.get("assigned_approaching", False)):
        return True
    if bool(flags.get("approaching", False)):
        return True
    return False


def _is_never_confirmed(flags: dict[str, Any]) -> bool:
    if bool(flags.get("confirmed", False)):
        return False
    status = str(flags.get("status", "") or "").strip().lower()
    return status in ("", "candidate", "unknown")


def unreachable_escape_victims(
    victim_flags: dict[str, dict[str, Any]],
    geo_streaks: dict[str, int] | None = None,
    undetected_streaks: dict[str, int] | None = None,
    *,
    geo_threshold: int = UNREACHABLE_STREAK_STEPS,
    undetected_threshold: int = UNDETECTED_STREAK_STEPS,
) -> tuple[list[tuple[str, str]], dict[str, int], dict[str, int]]:
    """Return ``(victim_id, cause)`` pairs whose consecutive streak reached a threshold.

    Causes:
    - ``geographically_isolated``: no safe BFS path for ``geo_threshold`` steps
    - ``never_detected``: never confirmed and unserved for ``undetected_threshold``

    Geographic isolation is preferred when both geo and never-detected would fire.
    Leftover non-terminal victims at a step cap are left as-is.
    """
    if not isinstance(victim_flags, dict):
        victim_flags = {}
    if geo_streaks is None:
        geo_streaks = {}
    if undetected_streaks is None:
        undetected_streaks = {}
    geo_limit = max(1, int(geo_threshold))
    und_limit = max(1, int(undetected_threshold))
    marked: list[tuple[str, str]] = []
    seen: set[str] = set()
    for vid, flags in victim_flags.items():
        vid_s = str(vid or "").strip()
        if not vid_s:
            continue
        seen.add(vid_s)
        entry = flags if isinstance(flags, dict) else {}
        if _is_terminal_flags(entry):
            geo_streaks[vid_s] = 0
            undetected_streaks[vid_s] = 0
            continue
        served = _is_productively_served(entry)
        geo_reachable = bool(entry.get("geo_reachable", entry.get("reachable", False)))
        assigned = bool(entry.get("assigned", False))

        if (not served) and (not geo_reachable):
            geo_streaks[vid_s] = int(geo_streaks.get(vid_s, 0) or 0) + 1
        else:
            geo_streaks[vid_s] = 0

        if (not served) and (not assigned) and _is_never_confirmed(entry):
            undetected_streaks[vid_s] = int(undetected_streaks.get(vid_s, 0) or 0) + 1
        else:
            undetected_streaks[vid_s] = 0

        if geo_streaks[vid_s] >= geo_limit:
            marked.append((vid_s, UNREACHABLE_CAUSE_GEOGRAPHIC))
        elif undetected_streaks[vid_s] >= und_limit:
            marked.append((vid_s, UNREACHABLE_CAUSE_UNDETECTED))
    for vid in list(geo_streaks.keys()):
        if vid not in seen:
            geo_streaks.pop(vid, None)
    for vid in list(undetected_streaks.keys()):
        if vid not in seen:
            undetected_streaks.pop(vid, None)
    marked.sort(key=lambda item: item[0])
    return marked, geo_streaks, undetected_streaks


def select_rescue_assignment(
    snapshot: dict[str, Any],
    reason: str,
    *,
    victim_id: str | None = None,
) -> RescueDecision | dict[str, Any]:
    """Choose victim/firefighter pairing from a read-only operational snapshot."""
    step = int(snapshot.get("step", 0) or 0)
    reason_s = str(reason or "")
    reason_l = _normalize_reason(reason_s)
    victims = snapshot.get("victims")
    firefighters = snapshot.get("firefighters")
    if not isinstance(victims, dict):
        victims = {}
    if not isinstance(firefighters, dict):
        firefighters = {}

    target_vid = str(victim_id or "").strip()
    needy: list[tuple[str, tuple[int, int]]] = []
    for vid, entry in victims.items():
        vid_s = str(vid or "").strip()
        if not vid_s:
            continue
        if target_vid and vid_s != target_vid:
            continue
        if not isinstance(entry, dict):
            continue
        if not bool(entry.get("confirmed", False)):
            continue
        if bool(entry.get("rescued", False)):
            continue
        if bool(entry.get("dead", False)):
            continue
        if bool(entry.get("cancelled", False)):
            continue
        if bool(entry.get("unreachable", False)):
            continue
        active_ff = entry.get("active_firefighter_id")
        if active_ff:
            continue
        if bool(entry.get("rescue_assigned", False)) and active_ff:
            continue
        pos = entry.get("position")
        if pos is None or len(pos) < 2:
            continue
        needy.append((vid_s, (int(pos[0]), int(pos[1]))))

    needy.sort(key=lambda item: item[0])
    if not needy:
        return {
            "action": "none",
            "victim_id": target_vid,
            "firefighter_id": None,
            "reason": reason_s,
            "distance": None,
        }

    chosen_vid, victim_pos = needy[0]

    available: list[tuple[str, tuple[int, int]]] = []
    for ff_id, entry in firefighters.items():
        ff_s = str(ff_id or "").strip()
        if not ff_s or not isinstance(entry, dict):
            continue
        if bool(entry.get("dead", False)):
            continue
        if bool(entry.get("assigned", False)):
            continue
        if bool(entry.get("route_blocked", False)):
            continue
        if not bool(entry.get("available", True)):
            continue
        pos = entry.get("position")
        if pos is None or len(pos) < 2:
            continue
        available.append((ff_s, (int(pos[0]), int(pos[1]))))

    if not available:
        # Feature 1: a unit that is off the grid for a rescue hand-over comes
        # back within a few steps, and its return re-runs dispatch for every
        # waiting victim. Giving the victim up now would turn that wait into a
        # lost rescue, so an empty pool with a returning unit delays regardless
        # of the reason - casualty replacement included.
        returning = sorted(
            str(ff_id)
            for ff_id, entry in firefighters.items()
            if isinstance(entry, dict)
            and bool(entry.get("off_grid", False))
            and not bool(entry.get("dead", False))
        )
        if returning:
            action = "delay"
        elif _is_initial_reason(reason_s) or reason_l == "victim_confirmed":
            action = "delay"
        elif reason_l in (
            "replacement_after_blocked",
            "route_blocked",
        ) or "blocked" in reason_l:
            action = "delay"
        else:
            action = "mark_unreachable"
        payload: dict[str, Any] = {"reason": reason_s, "distance": None}
        explanation = f"No available firefighter; {action}"
        if returning:
            payload["returning_firefighters"] = returning
            explanation = (
                f"No available firefighter; {len(returning)} unit(s) off-grid "
                f"and returning ({', '.join(returning)}); {action}"
            )
        return RescueDecision(
            decision_id=f"physical-pair-{action}-{chosen_vid}-{step}",
            selected_option_id="physical_pairing",
            rescue_action=action,
            victim_id=chosen_vid,
            firefighter_id="",
            route_choice="",
            payload=payload,
            confidence_score=1.0,
            uncertainty_context={"physical_pairing": True},
            comparison_summary={"summary": f"No firefighter for {chosen_vid}"},
            explanation=explanation,
        )

    best_ff: str | None = None
    best_dist: int | None = None
    for ff_s, ff_pos in available:
        dist = _manhattan_distance(victim_pos, ff_pos)
        if best_dist is None or dist < best_dist or (dist == best_dist and ff_s < str(best_ff)):
            best_ff = ff_s
            best_dist = dist

    return RescueDecision(
        decision_id=f"physical-pair-assign-{chosen_vid}-{best_ff}-{step}",
        selected_option_id="physical_pairing",
        rescue_action="assign",
        victim_id=chosen_vid,
        firefighter_id=str(best_ff or ""),
        route_choice="",
        payload={"reason": reason_s, "distance": best_dist},
        confidence_score=1.0,
        uncertainty_context={"physical_pairing": True},
        comparison_summary={"summary": f"Closest FF {best_ff} for {chosen_vid}"},
        explanation=f"Assign closest firefighter (dist={best_dist})",
    )
