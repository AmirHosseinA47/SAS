"""Managing system: explainability (Option-comparison and tradeoffs)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import agents

from .movement_explainability import flush_pending_movement_transitions

from .comparison_parser import (
    build_tradeoff_pairs,
    find_selected_score,
    parse_comparison_summary,
)
from .contracts import DecisionExplanation
from .display_utils import display_wind_vector
from .explanation_types import (
    ExplanationBundle,
    OptionComparisonExplanation,
    TradeoffExplanation,
    UncertaintyExplanation,
)

_NO_ALTERNATIVES_REASON = "No comparable option summary available from planner."

_PLANNER_DECISIONS: tuple[tuple[str, str, str], ...] = (
    ("mission_decision", "mission", "global_mission_planner"),
    ("rescue_decision", "rescue", "rescue_planner"),
    ("fail_safe_decision", "fail_safe", "fail_safe_planner"),
)


@dataclass
class ExplanationEngine:
    """Collects planner comparisons, logs, and model fields into structured explanations."""

    explanations: list[DecisionExplanation] = field(default_factory=list)
    bundle: ExplanationBundle = field(default_factory=ExplanationBundle)

    def collect_explanations(self, model: Any) -> list[DecisionExplanation]:
        flush_pending_movement_transitions(model)
        step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        records: list[DecisionExplanation] = []
        structured: list[dict[str, Any]] = []
        idx = 0

        def add_decision(
            *,
            source_module: str,
            decision_type: str,
            target_id: str,
            selected_action: str,
            reason: str,
            chosen_option: str = "",
            alternatives_considered: list[dict[str, Any]] | None = None,
            key_factors: list[str] | None = None,
            tradeoffs: list[dict[str, Any]] | None = None,
            confidence: float | None = None,
            uncertainty: dict[str, Any] | None = None,
            before_after: dict[str, Any] | None = None,
            source_data_refs: list[str] | None = None,
            evidence: dict[str, Any] | None = None,
            expected_effect: str = "",
            actual_outcome: str = "",
        ) -> DecisionExplanation:
            nonlocal idx
            alts = list(alternatives_considered or [])
            if not alts and reason != _NO_ALTERNATIVES_REASON and not reason:
                return records[-1] if records else DecisionExplanation(
                    explanation_id="", step=step, source_module="", decision_type="",
                    target_id="", selected_action="", reason="",
                )
            entry = DecisionExplanation(
                explanation_id=f"expl:{step}:{source_module}:{idx}",
                step=step,
                source_module=source_module,
                decision_type=decision_type,
                target_id=target_id,
                selected_action=selected_action,
                reason=reason,
                evidence=dict(evidence or {}),
                alternatives_considered=alts,
                key_factors=list(key_factors or []),
                expected_effect=expected_effect,
                actual_outcome=actual_outcome,
                chosen_option=chosen_option,
                tradeoffs=list(tradeoffs or []),
                confidence=confidence,
                uncertainty=dict(uncertainty or {}),
                before_after=dict(before_after or {}),
                source_data_refs=list(source_data_refs or []),
            )
            records.append(entry)
            idx += 1
            return entry

        structured.extend(self._planning_comparisons(model, step, add_decision, structured))
        structured.extend(self._uncertainty_explanations(model, step))
        structured.extend(self._rescue_assignment_explanations(model, step, add_decision))
        structured.extend(self._communication_explanations(model, step, add_decision))
        self._uav_executor_explanations(model, step, add_decision)
        structured.extend(self._movement_transition_explanations(model, step, add_decision))
        self._legacy_summaries(model, step, add_decision)
        self._rescue_log_explanations(model, step, add_decision)
        self._failsafe_snapshot_explanation(model, step, add_decision)

        self.explanations = records
        option_count = sum(
            1 for s in structured if s.get("explanation_kind") == "option_comparison"
        )
        uncertainty_count = sum(
            1 for s in structured if s.get("explanation_kind") == "uncertainty"
        )
        tradeoff_count = sum(
            1 for s in structured if s.get("explanation_kind") == "tradeoff"
        )
        self.bundle = ExplanationBundle(
            decision_explanations=[e.to_dict() for e in records],
            structured_explanations=structured,
            option_comparison_count=option_count,
            uncertainty_count=uncertainty_count,
            tradeoff_count=tradeoff_count,
            before_after_count=0,
        )
        return records

    def collect_bundle(self, model: Any) -> ExplanationBundle:
        self.collect_explanations(model)
        self._merge_movement_transition_log(model)
        return self.bundle

    def _planning_comparisons(
        self,
        model: Any,
        step: int,
        add_decision: Any,
        structured: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        planning = getattr(model, "latest_planning_result", None)
        if not isinstance(planning, dict):
            return out

        for key, decision_type, planner in _PLANNER_DECISIONS:
            decision = planning.get(key)
            if decision is None:
                continue
            out.extend(
                self._explain_decision_object(
                    decision,
                    step=step,
                    planner=planner,
                    decision_type=decision_type,
                    target_id=self._decision_target_id(decision, decision_type),
                    source_ref=f"latest_planning_result.{key}",
                    add_decision=add_decision,
                    structured=structured,
                )
            )

        path_decisions = planning.get("path_decisions")
        if isinstance(path_decisions, dict):
            for uav_id, decision in path_decisions.items():
                if decision is None:
                    continue
                out.extend(
                    self._explain_decision_object(
                        decision,
                        step=step,
                        planner="local_uav_path_planner",
                        decision_type="path",
                        target_id=str(uav_id),
                        source_ref=f"latest_planning_result.path_decisions[{uav_id}]",
                        add_decision=add_decision,
                        structured=structured,
                    )
                )
        return out

    def _explain_decision_object(
        self,
        decision: Any,
        *,
        step: int,
        planner: str,
        decision_type: str,
        target_id: str,
        source_ref: str,
        add_decision: Any,
        structured: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        selected_option = str(getattr(decision, "selected_option_id", "") or "")
        comparison = getattr(decision, "comparison_summary", None)
        parsed = parse_comparison_summary(comparison)
        alternatives = list(parsed["alternatives"])
        confidence = getattr(decision, "confidence_score", None)
        conf_val = float(confidence) if confidence is not None else None

        if alternatives:
            selected_score = find_selected_score(alternatives, selected_option)
            alt_scores = [float(a["score"]) for a in alternatives]
            ranking_reason = str(parsed.get("ranking_reason", "") or "")
            key_factors = self._key_factors_from_decision(decision, alternatives)

            reason = self._option_comparison_reason(
                planner=planner,
                selected_option=selected_option,
                selected_score=selected_score,
                alternatives=alternatives,
                decision=decision,
            )

            opt_expl = OptionComparisonExplanation(
                step=step,
                planner=planner,
                selected_option=selected_option,
                alternatives=alternatives,
                selected_score=selected_score,
                alternative_scores=alt_scores,
                ranking_reason=ranking_reason,
                key_factors=key_factors,
                target_id=target_id,
                source_data_refs=[source_ref, f"{source_ref}.comparison_summary"],
            )
            opt_dict = opt_expl.to_dict()
            structured.append(opt_dict)
            created.append(opt_dict)

            tradeoff_pairs = build_tradeoff_pairs(alternatives, selected_option)
            for pair in tradeoff_pairs:
                t_expl = TradeoffExplanation(
                    step=step,
                    tradeoff_type=str(pair["tradeoff_type"]),
                    selected_side=str(pair["selected_side"]),
                    rejected_side=str(pair["rejected_side"]),
                    reason=str(pair["reason"]),
                    evidence=dict(pair.get("evidence") or {}),
                    source_data_refs=[source_ref, f"{source_ref}.comparison_summary"],
                )
                t_dict = t_expl.to_dict()
                structured.append(t_dict)
                created.append(t_dict)

            add_decision(
                source_module=planner,
                decision_type=f"{decision_type}_option_comparison",
                target_id=target_id,
                selected_action=str(getattr(decision, "next_action", "") or getattr(decision, "rescue_action", "") or getattr(decision, "fail_safe_action", "") or selected_option),
                reason=reason,
                chosen_option=selected_option,
                alternatives_considered=alternatives,
                key_factors=key_factors,
                tradeoffs=tradeoff_pairs,
                confidence=conf_val,
                source_data_refs=[source_ref, f"{source_ref}.comparison_summary"],
                evidence={"ranking_reason": ranking_reason, "summary_text": parsed.get("summary_text", "")},
            )
        else:
            summary_text = str(parsed.get("summary_text", "") or "")
            reason = summary_text.strip() or _NO_ALTERNATIVES_REASON
            if summary_text.strip():
                ranking_reason = summary_text
                add_decision(
                    source_module=planner,
                    decision_type=f"{decision_type}_option_comparison",
                    target_id=target_id,
                    selected_action=selected_option,
                    reason=reason,
                    chosen_option=selected_option,
                    alternatives_considered=[],
                    key_factors=[f"raw_summary={summary_text[:200]}"],
                    confidence=conf_val,
                    source_data_refs=[source_ref, f"{source_ref}.comparison_summary"],
                    evidence={"ranking_reason": ranking_reason},
                )
                opt_expl = OptionComparisonExplanation(
                    step=step,
                    planner=planner,
                    selected_option=selected_option,
                    alternatives=[],
                    selected_score=None,
                    alternative_scores=[],
                    ranking_reason=ranking_reason,
                    key_factors=[f"raw_summary={summary_text[:200]}"],
                    target_id=target_id,
                    source_data_refs=[source_ref, f"{source_ref}.comparison_summary"],
                )
                opt_dict = opt_expl.to_dict()
                structured.append(opt_dict)
                created.append(opt_dict)
            else:
                add_decision(
                    source_module=planner,
                    decision_type=f"{decision_type}_option_comparison",
                    target_id=target_id,
                    selected_action=selected_option,
                    reason=_NO_ALTERNATIVES_REASON,
                    chosen_option=selected_option,
                    source_data_refs=[source_ref],
                )
        return created

    @staticmethod
    def _decision_target_id(decision: Any, decision_type: str) -> str:
        if decision_type == "path":
            return str(getattr(decision, "uav_id", "") or "unknown")
        if decision_type == "rescue":
            return str(getattr(decision, "victim_id", "") or "mission")
        return "mission"

    @staticmethod
    def _key_factors_from_decision(
        decision: Any,
        alternatives: list[dict[str, Any]],
    ) -> list[str]:
        factors: list[str] = []
        explanation = str(getattr(decision, "explanation", "") or "").strip()
        if explanation:
            factors.append(explanation)
        feasible_count = sum(1 for a in alternatives if a.get("feasible"))
        factors.append(f"feasible_options={feasible_count}/{len(alternatives)}")
        ctx = getattr(decision, "uncertainty_context", None)
        if isinstance(ctx, dict) and ctx:
            factors.append(f"uncertainty_context_keys={sorted(ctx.keys())}")
        return factors

    @staticmethod
    def _option_comparison_reason(
        *,
        planner: str,
        selected_option: str,
        selected_score: float | None,
        alternatives: list[dict[str, Any]],
        decision: Any,
    ) -> str:
        if selected_score is not None and selected_option:
            return (
                f"{planner} selected {selected_option} with score {selected_score:.4f} "
                f"from {len(alternatives)} evaluated option(s)."
            )
        if alternatives and selected_option:
            top = alternatives[0]
            if top.get("option_id") == selected_option:
                return (
                    f"{planner} selected top-ranked feasible option {selected_option} "
                    f"(score {float(top.get('score', 0.0)):.4f})."
                )
        expl = str(getattr(decision, "explanation", "") or "").strip()
        if expl:
            return expl
        return f"{planner} selected {selected_option or 'unknown option'}."

    def _uncertainty_explanations(self, model: Any, step: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        fs = getattr(model, "latest_failsafe_state", None)
        if fs is None:
            return out

        mode = getattr(fs, "mode", None)
        mode_value = str(getattr(mode, "value", mode) or "")
        reasons = [
            str(getattr(r, "value", r)) for r in (getattr(fs, "active_reasons", ()) or ())
        ]
        if not reasons and mode_value in {"", "normal"}:
            return out

        triggers = reasons or [mode_value]
        for trigger in triggers:
            if trigger in {"", "normal"}:
                continue
            recovery = mode_value or "unknown"
            evidence: dict[str, Any] = {
                "mode": mode_value,
                "active_reasons": reasons,
                "explanation": str(getattr(fs, "explanation", "") or ""),
            }
            analysis = getattr(model, "latest_analysis_snapshot", None)
            if analysis is not None:
                all_triggers = getattr(analysis, "all_triggers", ()) or ()
                evidence["analysis_trigger_count"] = len(all_triggers)

            planning = getattr(model, "latest_planning_result", None)
            if isinstance(planning, dict):
                fsd = planning.get("fail_safe_decision")
                if fsd is not None and bool(getattr(fsd, "search_mode_active", False)):
                    evidence["search_mode_active"] = True
                    recovery = str(getattr(fsd, "mission_mode", recovery) or recovery)

            expl = UncertaintyExplanation(
                step=step,
                uncertainty_metric=trigger,
                trigger=trigger,
                affected_area="fleet",
                selected_recovery_action=recovery,
                evidence=evidence,
                source_data_refs=["latest_failsafe_state", "latest_planning_result.fail_safe_decision"],
            )
            out.append(expl.to_dict())
        return out

    def _rescue_assignment_explanations(
        self,
        model: Any,
        step: int,
        add_decision: Any,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        dispatch_types = {"dispatch_initial", "dispatch_replacement_after_blocked", "dispatch_replacement_after_casualty"}
        for event in list(getattr(model, "_rescue_event_log", None) or []):
            event_type = str(event.get("event_type", "") or "")
            if event_type not in dispatch_types:
                continue
            vid = str(event.get("victim_id", "") or "unknown")
            ff_id = str(event.get("firefighter_id", "") or "unknown")
            event_step = int(event.get("step", step) or step)
            reason = str(event.get("reason", "") or event_type)
            message = f"Firefighter {ff_id} assigned to {vid} ({event_type} event in rescue log)."
            add_decision(
                source_module="rescue_pipeline",
                decision_type="rescue_assignment",
                target_id=vid,
                selected_action="assign",
                reason=message,
                chosen_option=ff_id,
                evidence={"event": event, "event_type": event_type},
                actual_outcome=event_type,
                source_data_refs=["_rescue_event_log"],
            )
            out.append({"explanation_kind": "rescue_assignment", "step": event_step, "message": message})
        return out

    def _communication_explanations(
        self,
        model: Any,
        step: int,
        add_decision: Any,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        comm = getattr(model, "communication_model", None)
        if comm is None:
            return out
        for entry in list(getattr(comm, "_communication_command_log", None) or []):
            if not isinstance(entry, dict):
                continue
            previous = str(entry.get("previous_mode", "") or "")
            current = str(entry.get("communication_mode", "") or "")
            if not current or previous == current:
                continue
            ts = entry.get("timestamp")
            event_step = int(ts) if isinstance(ts, (int, float)) and ts >= 0 else step
            reason = str(entry.get("reason", "") or "")
            message = reason or f"Communication mode changed to {current} (logged communication event)."
            add_decision(
                source_module="communication_model",
                decision_type="communication_mode_changed",
                target_id="communication",
                selected_action=current,
                reason=message,
                evidence={"previous_mode": previous, "communication_mode": current, "log_entry": entry},
                source_data_refs=["communication_model._communication_command_log"],
            )
            out.append({"explanation_kind": "communication", "step": event_step, "message": message})
        return out

    def _uav_executor_explanations(self, model: Any, step: int, add_decision: Any) -> None:
        for agent in getattr(model.schedule, "agents", []) or []:
            if type(agent) is not agents.UAV:
                continue
            uav_id = str(getattr(agent, "unique_id", ""))
            expl = getattr(agent, "last_explanation", None)
            if not isinstance(expl, dict):
                continue
            decision = str(expl.get("decision", "") or "uav_decision")
            reason = str(expl.get("reason", "") or "")
            wind = str(expl.get("wind_direction", "") or "")
            key_factors = []
            if wind:
                vec = display_wind_vector(wind)
                key_factors.append(f"wind={wind} display_vector={list(vec)}")
            target = expl.get("target")
            if target is not None:
                key_factors.append(f"target={target}")

            planning = getattr(model, "latest_planning_result", None)
            path_alts: list[dict[str, Any]] = []
            selected = ""
            if isinstance(planning, dict):
                path_decisions = planning.get("path_decisions")
                if isinstance(path_decisions, dict) and uav_id in path_decisions:
                    pd = path_decisions[uav_id]
                    selected = str(getattr(pd, "selected_option_id", "") or "")
                    parsed = parse_comparison_summary(getattr(pd, "comparison_summary", None))
                    path_alts = list(parsed["alternatives"])

            if path_alts:
                score = find_selected_score(path_alts, selected)
                if score is not None:
                    reason = (
                        f"UAV selected {decision} because it had the highest feasible utility "
                        f"(score {score:.4f}) over alternatives."
                    )
                add_decision(
                    source_module="uav_executor",
                    decision_type=decision,
                    target_id=uav_id,
                    selected_action=decision,
                    reason=reason,
                    chosen_option=selected,
                    alternatives_considered=path_alts,
                    key_factors=key_factors,
                    source_data_refs=[f"agent.last_explanation", f"latest_planning_result.path_decisions[{uav_id}]"],
                    evidence={"raw": expl},
                )
            elif reason:
                add_decision(
                    source_module=str(expl.get("source", "uav_executor")),
                    decision_type=decision,
                    target_id=uav_id,
                    selected_action=decision,
                    reason=reason,
                    key_factors=key_factors,
                    source_data_refs=["agent.last_explanation"],
                    evidence={"raw": expl},
                )

    def _movement_transition_explanations(
        self,
        model: Any,
        step: int,
        add_decision: Any,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        emitted = getattr(model, "_movement_explained_keys", None)
        if not isinstance(emitted, set):
            emitted = set()

        schedule = getattr(model, "schedule", None)
        if schedule is None:
            model._movement_explained_keys = emitted
            return out

        for agent in getattr(schedule, "agents", ()) or ():
            agent_type = type(agent)
            if agent_type is agents.Firefighter:
                mr = getattr(agent, "movement_reason", None)
                if not isinstance(mr, dict):
                    continue
                uid = str(getattr(agent, "unit_id", getattr(agent, "unique_id", "")))
                cat = str(mr.get("category", "") or "")
                prev = str(mr.get("prev_category", "") or "")
                if not cat or cat == prev:
                    continue
                dedupe_key = f"ff:{uid}:{step}:{cat}"
                if dedupe_key in emitted:
                    continue
                emitted.add(dedupe_key)
                factors = mr.get("key_factors", {})
                key_factors = [
                    f"{fk}={fv}" for fk, fv in factors.items()
                ] if isinstance(factors, dict) else []
                message = str(mr.get("reason", "") or cat)
                add_decision(
                    source_module="firefighter_move",
                    decision_type="movement_transition",
                    target_id=uid,
                    selected_action=cat,
                    reason=message,
                    key_factors=key_factors,
                    evidence={
                        "movement_reason": mr,
                        "previous_category": prev,
                    },
                    source_data_refs=["agent.movement_reason"],
                )
                out.append(
                    {
                        "explanation_kind": "movement_transition",
                        "step": step,
                        "agent_kind": "firefighter",
                        "target_id": uid,
                        "category": cat,
                        "message": message,
                    }
                )
            elif agent_type is agents.UAV:
                mr = getattr(agent, "movement_reason", None)
                if not isinstance(mr, dict):
                    continue
                uid = str(getattr(agent, "unique_id", ""))
                cat = str(mr.get("category", "") or "")
                prev = str(mr.get("prev_category", "") or "")
                if not cat or cat == prev:
                    continue
                dedupe_key = f"uav:{uid}:{step}:{cat}"
                if dedupe_key in emitted:
                    continue
                emitted.add(dedupe_key)
                factors = mr.get("key_factors", {})
                key_factors = [
                    f"{fk}={fv}" for fk, fv in factors.items()
                ] if isinstance(factors, dict) else []
                message = str(mr.get("reason", "") or cat)
                add_decision(
                    source_module="uav_move",
                    decision_type="movement_transition",
                    target_id=uid,
                    selected_action=cat,
                    reason=message,
                    key_factors=key_factors,
                    evidence={
                        "movement_reason": mr,
                        "previous_category": prev,
                    },
                    source_data_refs=["agent.movement_reason"],
                )
                out.append(
                    {
                        "explanation_kind": "movement_transition",
                        "step": step,
                        "agent_kind": "uav",
                        "target_id": uid,
                        "category": cat,
                        "message": message,
                    }
                )

        model._movement_explained_keys = emitted
        return out

    def _merge_movement_transition_log(self, model: Any) -> None:
        """Append historical movement transitions into the export bundle."""
        log = getattr(model, "_movement_transition_log", None)
        if not isinstance(log, list) or not log:
            return
        existing = {
            (int(e.step), e.target_id, e.selected_action)
            for e in self.explanations
            if e.decision_type == "movement_transition"
        }
        idx = len(self.explanations)
        structured = list(self.bundle.structured_explanations)
        for entry in log:
            if not isinstance(entry, dict):
                continue
            entry_step = int(entry.get("step", 0) or 0)
            target_id = str(entry.get("target_id", "") or "")
            category = str(entry.get("category", "") or "")
            if not target_id or not category:
                continue
            key = (entry_step, target_id, category)
            if key in existing:
                continue
            existing.add(key)
            source_module = str(
                entry.get("source_module", "")
                or (
                    "firefighter_move"
                    if entry.get("agent_kind") == "firefighter"
                    else "uav_move"
                )
            )
            factors = entry.get("key_factors", {})
            key_factors = [
                f"{fk}={fv}" for fk, fv in factors.items()
            ] if isinstance(factors, dict) else []
            message = str(entry.get("reason", "") or category)
            prev = str(entry.get("prev_category", "") or "")
            self.explanations.append(
                DecisionExplanation(
                    explanation_id=f"expl:{entry_step}:{source_module}:{idx}",
                    step=entry_step,
                    source_module=source_module,
                    decision_type="movement_transition",
                    target_id=target_id,
                    selected_action=category,
                    reason=message,
                    evidence={
                        "movement_reason": entry,
                        "previous_category": prev,
                    },
                    key_factors=key_factors,
                    source_data_refs=["model._movement_transition_log"],
                )
            )
            structured.append(
                {
                    "explanation_kind": "movement_transition",
                    "step": entry_step,
                    "agent_kind": entry.get("agent_kind", ""),
                    "target_id": target_id,
                    "category": category,
                    "message": message,
                }
            )
            idx += 1
        self.bundle = ExplanationBundle(
            decision_explanations=[e.to_dict() for e in self.explanations],
            structured_explanations=structured,
            option_comparison_count=self.bundle.option_comparison_count,
            uncertainty_count=self.bundle.uncertainty_count,
            tradeoff_count=self.bundle.tradeoff_count,
            before_after_count=self.bundle.before_after_count,
        )

    def _legacy_summaries(self, model: Any, step: int, add_decision: Any) -> None:
        post_move = getattr(model, "latest_post_move_cycle_result", None)
        if isinstance(post_move, dict):
            summary = str(post_move.get("dashboard_summary", "") or "").strip()
            if summary:
                add_decision(
                    source_module="post_move_cycle",
                    decision_type="post_move_summary",
                    target_id="mission",
                    selected_action="post_move",
                    reason=summary,
                    source_data_refs=["latest_post_move_cycle_result"],
                )

    def _rescue_log_explanations(self, model: Any, step: int, add_decision: Any) -> None:
        skip_types = {
            "dispatch_initial",
            "dispatch_replacement_after_blocked",
            "dispatch_replacement_after_casualty",
        }
        for event in list(getattr(model, "_rescue_event_log", None) or [])[-30:]:
            event_type = str(event.get("event_type", "") or "rescue_event")
            if event_type in skip_types:
                continue
            vid = str(event.get("victim_id", "") or "unknown")
            ff_id = str(event.get("firefighter_id", "") or "")
            reason = str(event.get("reason", "") or "")
            if not reason:
                reason = f"Rescue event {event_type} for victim {vid}"
            add_decision(
                source_module="rescue_pipeline",
                decision_type=event_type,
                target_id=vid,
                selected_action=event_type,
                reason=reason,
                evidence={
                    "firefighter_id": ff_id,
                    "victim_pos": event.get("victim_pos"),
                    "firefighter_pos": event.get("firefighter_pos"),
                    "metadata": event.get("metadata"),
                },
                actual_outcome=event_type,
                source_data_refs=["_rescue_event_log"],
            )

    def _failsafe_snapshot_explanation(self, model: Any, step: int, add_decision: Any) -> None:
        fs = getattr(model, "latest_failsafe_state", None)
        if fs is None:
            return
        mode = getattr(fs, "mode", None)
        mode_value = str(getattr(mode, "value", mode) or "")
        explanation = str(getattr(fs, "explanation", "") or "").strip()
        fs_summary = str(getattr(model, "latest_failsafe_dashboard_summary", "") or "").strip()
        reason = explanation or fs_summary
        if not reason and mode_value in {"", "normal"}:
            return
        if not reason:
            reason = f"Fail-safe mode active: {mode_value}"
        reasons = [str(getattr(r, "value", r)) for r in (getattr(fs, "active_reasons", ()) or ())]
        add_decision(
            source_module="mode_manager",
            decision_type="fail_safe",
            target_id="fleet",
            selected_action=mode_value or "fail_safe",
            reason=reason,
            key_factors=reasons,
            uncertainty={"active_reasons": reasons, "mode": mode_value},
            source_data_refs=["latest_failsafe_state", "latest_failsafe_dashboard_summary"],
            expected_effect="Safer operational posture under uncertainty",
        )

    def explain(self, topic: str, context: dict[str, Any] | None = None) -> str:
        ctx = context or {}
        return str(ctx.get("reason", "") or f"Explanation topic: {topic}")
