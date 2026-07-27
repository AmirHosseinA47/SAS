"""Read-only movement transition helpers."""

from __future__ import annotations

from typing import Any


def notable_uav_movement_category(role: str, fine_category: str) -> str:
    role_norm = str(role or "").strip().lower()
    fine = str(fine_category or "")
    if role_norm == "fire_tracker":
        if fine in {"tracker_escape", "tracker_smoke_escape"}:
            return "tracker_escape"
        if fine == "tracker_flank_relocate":
            return "tracker_relocate"
        return "tracker_hold"
    if role_norm in {"victim_searcher", "victim_search"}:
        if fine == "searcher_hazard_retreat":
            return "searcher_hazard_retreat"
        if fine == "searcher_coverage_escape":
            return "searcher_coverage_escape"
        if fine == "searcher_coverage":
            return "searcher_coverage"
        return "searcher_move"
    return fine or "uav_move"


def notable_firefighter_movement_category(fine_category: str) -> str:
    fine = str(fine_category or "")
    if fine in {"exiting_setup", "exiting_with_victim", "exiting_complete"}:
        return "exiting"
    return fine


def movement_transition_key(
    agent_kind: str,
    notable_category: str,
    factors: dict[str, Any] | None,
) -> str:
    factors = factors or {}
    if agent_kind == "uav":
        role = str(factors.get("role", "") or "").strip().lower()
        if role == "fire_tracker" and notable_category == "tracker_hold":
            return f"tracker_hold:{factors.get('flank_side', '')}"
        if role in {"victim_searcher", "victim_search"} and notable_category == "searcher_coverage":
            return f"searcher_coverage:{factors.get('coverage_target', '')}"
    return str(notable_category or "")


def flush_pending_movement_transitions(model: Any) -> None:
    """Commit staged per-step UAV movement labels (last write wins per agent)."""
    pending = getattr(model, "_movement_step_pending", None)
    if not isinstance(pending, dict) or not pending:
        return
    log = getattr(model, "_movement_transition_log", None)
    if not isinstance(log, list):
        log = []
        model._movement_transition_log = log
    schedule = getattr(model, "schedule", None)
    agents_by_id: dict[str, Any] = {}
    if schedule is not None:
        for agent in getattr(schedule, "agents", ()) or ():
            uid = str(getattr(agent, "unique_id", ""))
            if uid:
                agents_by_id[f"uav:{uid}"] = agent
    for _key, entry in pending.items():
        if not isinstance(entry, dict):
            continue
        target_id = str(entry.get("target_id", "") or "")
        agent = agents_by_id.get(f"uav:{target_id}")
        transition_key = str(entry.get("transition_key", "") or "")
        prev_key = str(entry.get("prev_transition_key", "") or "")
        if agent is not None and not prev_key:
            prev_key = str(getattr(agent, "_movement_last_transition_key", "") or "")
        if not transition_key or transition_key == prev_key:
            if agent is not None:
                agent._movement_last_transition_key = transition_key
                agent._movement_last_notable_category = str(
                    entry.get("category", "") or ""
                )
            continue
        prev_notable = str(entry.get("prev_notable_category", "") or "")
        log_entry = dict(entry)
        log_entry["prev_category"] = prev_notable
        log.append(log_entry)
        if agent is not None:
            agent._movement_last_transition_key = transition_key
            agent._movement_last_notable_category = str(
                entry.get("category", "") or ""
            )
    pending.clear()
    model._movement_step_pending = pending
