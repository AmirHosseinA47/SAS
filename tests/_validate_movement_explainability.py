"""Validate movement explainability is read-only (trajectory unchanged)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from serve_dashboard import _build_evaluation
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.dashboard.explanation_engine import ExplanationEngine
from wildfire_model import WildFireModel

STEPS = 150


def _agent_positions(model: WildFireModel) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for agent in model.schedule.agents:
        pos = getattr(agent, "pos", None)
        if pos is None:
            continue
        name = type(agent).__name__
        if name == "UAV":
            out[f"uav:{agent.unique_id}"] = (int(pos[0]), int(pos[1]))
        elif name == "Firefighter":
            out[f"ff:{agent.unit_id}"] = (int(pos[0]), int(pos[1]))
    return out


def run(seed: int = 42, *, collect_explanations: bool = False) -> dict:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    am.random = rng
    params = dict(
        NUM_AGENTS=3,
        NUM_VICTIMS=5,
        NUM_FIREFIGHTERS=3,
        WIND_DIRECTION="east",
        BATCH_SIZE=300,
        FIRE_SPREAD_MULTIPLIER=0.75,
        PROBABILITY_MAP=False,
    )
    apply_scenario_config(cfv, wf, **params)
    engine = ExplanationEngine()
    transitions: list[dict] = []
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(STEPS):
            model.step()
            if collect_explanations:
                state = model.latest_dashboard_state or {}
                for entry in state.get("explanation_list", []):
                    if entry.get("decision_type") == "movement_transition":
                        transitions.append(entry)
        ev = _build_evaluation(model, None, STEPS, params)
    return {
        "positions": _agent_positions(model),
        "ev": ev,
        "transitions": transitions,
        "transition_log": list(getattr(model, "_movement_transition_log", None) or []),
    }


if __name__ == "__main__":
    # Trajectory check: two runs with same seed must match exactly.
    a = run(42, collect_explanations=False)
    b = run(42, collect_explanations=False)
    same = a["positions"] == b["positions"] and a["ev"] == b["ev"]
    print("trajectory_reproducible", same)
    print("end_positions", a["positions"])
    print("outcomes", a["ev"])

    c = run(42, collect_explanations=True)
    mt = c["transitions"]
    print("movement_transitions_150_dashboard", len(mt))
    for sample in mt[:5]:
        print(" sample:", json.dumps(sample, default=str)[:280])

    # 300-step transition volume from cumulative log (read-only observational store).
    rng = random.Random(42)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(
        cfv, wf,
        NUM_AGENTS=3, NUM_VICTIMS=5, NUM_FIREFIGHTERS=3,
        WIND_DIRECTION="east", BATCH_SIZE=300,
        FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(300):
            model.step()
    log = list(getattr(model, "_movement_transition_log", None) or [])
    print("movement_transitions_300_log", len(log))

    engine = ExplanationEngine()
    bundle = engine.collect_bundle(model)
    mt_export = [
        e for e in bundle.decision_explanations
        if e.get("decision_type") == "movement_transition"
    ]
    print("movement_transitions_300_export", len(mt_export))
    print("json_export_entries", len(bundle.decision_explanations))
    print("json_valid", isinstance(bundle.to_dict(), dict))

    # Sample categories for report
    ff_retreat = next((e for e in log if e.get("category") == "survival_retreat"), None)
    tracker_escape = next((e for e in log if "escape" in str(e.get("category", ""))), None)
    searcher = next(
        (e for e in log if str(e.get("category", "")).startswith("searcher_")), None
    )
    for label, entry in [
        ("ff_retreat", ff_retreat),
        ("tracker_escape", tracker_escape),
        ("searcher", searcher),
    ]:
        if entry:
            print(label, json.dumps(entry, default=str)[:320])
