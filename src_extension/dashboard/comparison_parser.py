"""Parse planner comparison_summary text into structured option entries."""

from __future__ import annotations

import re
from typing import Any

# Matches: "  N. option_id [option_type] score=X.XXXX feasible=True/False"
# Optional pref_bonus between score and feasible (rescue / fail_safe planners).
_OPTION_LINE_RE = re.compile(
    r"^\s*(\d+)\.\s+(\S+)\s+\[([^\]]+)\]\s+"
    r"score=([\d.+-]+)"
    r"(?:\s+pref_bonus=([\d.+-]+))?"
    r"\s+feasible=(\w+)",
    re.MULTILINE,
)


def parse_comparison_summary(summary: object | None) -> dict[str, Any]:
    """Return parsed alternatives and metadata from a comparison_summary dict or str."""
    text = _summary_text(summary)
    if not text.strip():
        return {
            "summary_text": "",
            "alternatives": [],
            "has_scored_options": False,
            "ranking_reason": "No comparable option summary available from planner.",
        }

    alternatives: list[dict[str, Any]] = []
    for match in _OPTION_LINE_RE.finditer(text):
        rank = int(match.group(1))
        option_id = match.group(2)
        option_type = match.group(3)
        score = float(match.group(4))
        pref_bonus_raw = match.group(5)
        feasible_raw = match.group(6).strip().lower()
        entry: dict[str, Any] = {
            "rank": rank,
            "option_id": option_id,
            "option_type": option_type,
            "score": score,
            "feasible": feasible_raw in {"true", "1", "yes"},
        }
        if pref_bonus_raw is not None:
            entry["pref_bonus"] = float(pref_bonus_raw)
        alternatives.append(entry)

    has_scored = bool(alternatives)
    ranking_reason = text if not has_scored else ""
    if has_scored:
        top = alternatives[0]
        ranking_reason = (
            f"Top ranked option: {top['option_id']} "
            f"[{top['option_type']}] score={top['score']:.4f} "
            f"feasible={top['feasible']}"
        )

    return {
        "summary_text": text,
        "alternatives": alternatives,
        "has_scored_options": has_scored,
        "ranking_reason": ranking_reason,
    }


def find_selected_score(
    alternatives: list[dict[str, Any]],
    selected_option_id: str,
) -> float | None:
    if not selected_option_id:
        return alternatives[0]["score"] if alternatives else None
    for alt in alternatives:
        if alt.get("option_id") == selected_option_id:
            return float(alt["score"])
    return alternatives[0]["score"] if alternatives else None


def build_tradeoff_pairs(
    alternatives: list[dict[str, Any]],
    selected_option_id: str,
) -> list[dict[str, Any]]:
    """Build tradeoffs from rejected scored options only (no fabricated reasons)."""
    if len(alternatives) < 2:
        return []
    selected = None
    for alt in alternatives:
        if alt.get("option_id") == selected_option_id:
            selected = alt
            break
    if selected is None:
        selected = alternatives[0]
    selected_id = str(selected.get("option_id", ""))
    selected_type = str(selected.get("option_type", ""))
    selected_score = float(selected.get("score", 0.0))

    tradeoffs: list[dict[str, Any]] = []
    for alt in alternatives:
        if alt.get("option_id") == selected_id:
            continue
        rejected_id = str(alt.get("option_id", ""))
        rejected_type = str(alt.get("option_type", ""))
        rejected_score = float(alt.get("score", 0.0))
        tradeoff_type = _tradeoff_type_from_option_types(selected_type, rejected_type)
        tradeoffs.append(
            {
                "tradeoff_type": tradeoff_type,
                "selected_side": selected_id,
                "rejected_side": rejected_id,
                "reason": (
                    f"chose {selected_id} [{selected_type}] over {rejected_id} "
                    f"[{rejected_type}]: score {selected_score:.4f} vs {rejected_score:.4f}"
                ),
                "evidence": {
                    "selected_option_type": selected_type,
                    "rejected_option_type": rejected_type,
                    "selected_score": selected_score,
                    "rejected_score": rejected_score,
                },
            }
        )
    return tradeoffs


def _summary_text(summary: object | None) -> str:
    if summary is None:
        return ""
    if isinstance(summary, dict):
        return str(summary.get("summary", "") or "")
    return str(summary)


def _tradeoff_type_from_option_types(selected_type: str, rejected_type: str) -> str:
    sel = selected_type.strip().lower()
    rej = rejected_type.strip().lower()
    pairs = {
        ("explore", "stability"): "mission_progress_vs_safety",
        ("explore", "hold"): "exploration_vs_battery_conservation",
        ("search", "stability"): "mission_progress_vs_safety",
        ("assign", "delay"): "rescue_speed_vs_fire_risk",
        ("assign", "mark_unreachable"): "rescue_speed_vs_safety",
        ("fail_safe_priority", "normal"): "communication_reliability_vs_message_load",
    }
    return pairs.get((sel, rej), f"{sel}_vs_{rej}")
