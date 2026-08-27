"""BUG #6 acceptance gate, re-run after the _is_delay_or_cancel_option repair.

Counts, per the brief:
  - delay decisions SELECTED by the planner            (baseline: 0)
  - reaching RescueExecutor.execute() with non-empty victim_id
  - refused on a SPECIFIC victim match vs the GENERIC-id fallback
  - invariant-violation logging already present from BUG #6's fix
    ([RescueDelayRefused] on stderr / execution-log failure entries)

Run:
    python outputs/_delaybonus_gate.py --scenario D --wind east --steps 240 \
        --seeds 101,202,303,404,505 --tag post_Deast
"""

from __future__ import annotations

import argparse
import contextlib
import io as _io
import json
import os
import random
import sys
from collections import Counter

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am  # noqa: E402
import common_fixed_variables as cfv  # noqa: E402
import wildfire_model as wf  # noqa: E402
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402
from wildfire_model import WildFireModel  # noqa: E402
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation, _resolve_role_count_params  # noqa: E402

from src_extension.planning import rescue_planner as rp  # noqa: E402
from src_extension.planning.planner_selection import option_parameters, option_id  # noqa: E402
from src_extension.execution.rescue_executor import RescueExecutor, _GENERIC_VICTIM_IDS  # noqa: E402

C: Counter = Counter()
SELECTED_IDS: Counter = Counter()
EXEC_ACTIONS: Counter = Counter()
SAMPLES: list[str] = []
GATE_OPEN_STEPS = 0


def install() -> None:
    global GATE_OPEN_STEPS
    orig_select = rp._select_rescue_option
    orig_execute = RescueExecutor.execute
    orig_pairing = RescueExecutor._active_physical_pairing

    def probe_select(scored, options, signals):
        global GATE_OPEN_STEPS
        C["planning_calls"] += 1
        if signals["route_risk"] >= rp._HIGH_ROUTE_RISK or signals["communication_risk"] >= rp._HIGH_COMM_RISK:
            GATE_OPEN_STEPS += 1
            C["bonus_gate_open"] += 1
        if signals["victim_confidence"] < rp._LOW_VICTIM_CONFIDENCE or signals["uncertainty"] >= rp._HIGH_UNCERTAINTY:
            C["confirmation_gate_open"] += 1

        selected = orig_select(scored, options, signals)
        if selected is None:
            C["selected_none"] += 1
            return selected

        oid = option_id(selected)
        SELECTED_IDS[oid] += 1
        params = option_parameters(selected)
        ot = str(getattr(selected, "option_type", "") or "").lower()
        action = str(params.get("rescue_action", "") or "").strip().lower()

        # the repaired predicate, as it now lives in source
        if rp._is_delay_or_cancel_option(ot, params):
            C["selected_delay_or_cancel_predicate_true"] += 1
        if "delay" in action:
            C["SELECTED_DELAY"] += 1
        if "cancel" in action:
            C["SELECTED_CANCEL"] += 1
        return selected

    def probe_pairing(self, model, victim_id, firefighter_id):
        vid = str(victim_id or "").strip()
        generic = vid.lower() in _GENERIC_VICTIM_IDS
        C["pairing_checks"] += 1
        C["pairing_generic_id" if generic else "pairing_specific_id"] += 1
        res = orig_pairing(self, model, victim_id, firefighter_id)
        if res is not None:
            C["pairing_matched_generic_branch" if generic else "pairing_matched_specific_branch"] += 1
        return res

    def probe_execute(self, decision, timestamp=0.0):
        if decision is not None:
            act = str(getattr(decision, "rescue_action", "") or "").strip().lower()
            EXEC_ACTIONS[act or "(empty)"] += 1
            kind = RescueExecutor._classify_rescue_action(act)
            if kind == "delay":
                C["EXEC_DELAY_ARRIVED"] += 1
                vid = str(getattr(decision, "victim_id", "") or "").strip()
                if vid:
                    C["EXEC_DELAY_NONEMPTY_VICTIM_ID"] += 1
                    if vid.lower() not in _GENERIC_VICTIM_IDS:
                        C["EXEC_DELAY_REAL_VICTIM_ID"] += 1
                else:
                    C["EXEC_DELAY_EMPTY_VICTIM_ID"] += 1
        res = orig_execute(self, decision, timestamp)
        if isinstance(res, dict) and res.get("reason") == "delay_refused_active_physical_pairing":
            C["DELAY_REFUSED_TOTAL"] += 1
            if len(SAMPLES) < 10:
                SAMPLES.append(json.dumps(res.get("payload", {}), default=str)[:400])
        return res

    rp._select_rescue_option = probe_select
    RescueExecutor.execute = probe_execute
    RescueExecutor._active_physical_pairing = probe_pairing


def scenario_params(scenario: str, wind: str):
    preset = BUILTIN_SCENARIOS.get(scenario, {})
    num_agents = int(preset.get("NUM_AGENTS", 3))
    ft, vs = _resolve_role_count_params(num_agents, None, None)
    return {
        "NUM_AGENTS": num_agents,
        "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
        "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)),
        "WIND_DIRECTION": str(wind),
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": ft,
        "NUM_VICTIM_SEARCHERS": vs,
    }


def run_seed(seed: int, params: dict, steps: int, err: _io.StringIO) -> dict:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    terminal_step = None
    step = 0
    with contextlib.redirect_stdout(_io.StringIO()), contextlib.redirect_stderr(err):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            model.step()
            step += 1
            if terminal_step is None:
                m = (model.get_dashboard_state().get("mission_status", {}) or {})
                if m.get("all_victims_terminal"):
                    terminal_step = step
    ev = _build_evaluation(model, terminal_step, step, params)
    ev["seed"] = seed
    return ev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", default="101,202,303,404,505")
    ap.add_argument("--tag", default="gate")
    a = ap.parse_args()

    seeds = [int(s) for s in a.seeds.split(",")]
    params = scenario_params(a.scenario, a.wind)
    install()

    err = _io.StringIO()
    evals = [run_seed(s, params, a.steps, err) for s in seeds]
    stderr_text = err.getvalue()
    refused_lines = [ln for ln in stderr_text.splitlines() if "RescueDelayRefused" in ln]

    o: list[str] = []
    o.append(f"=== BUG #6 ACCEPTANCE GATE [{a.tag}] {a.scenario}/{a.wind} "
             f"seeds={seeds} steps={a.steps} ===")
    o.append(f"python={sys.version.split()[0]}")
    o.append("")
    o.append("--- THE FOUR GATE COUNTERS ---")
    o.append(f"  1. delay decisions SELECTED by the planner .............. {C['SELECTED_DELAY']}   (baseline: 0)")
    o.append(f"     cancel decisions SELECTED by the planner ............. {C['SELECTED_CANCEL']}")
    o.append(f"  2. reaching RescueExecutor.execute() as a delay ......... {C['EXEC_DELAY_ARRIVED']}")
    o.append(f"       of those, with a NON-EMPTY victim_id .............. {C['EXEC_DELAY_NONEMPTY_VICTIM_ID']}")
    o.append(f"       of those, with a NON-GENERIC (real) victim_id ..... {C['EXEC_DELAY_REAL_VICTIM_ID']}")
    o.append(f"       of those, with an EMPTY victim_id ................. {C['EXEC_DELAY_EMPTY_VICTIM_ID']}")
    o.append(f"  3. refused, SPECIFIC victim match ....................... {C['pairing_matched_specific_branch']}")
    o.append(f"     refused, GENERIC-id fallback ......................... {C['pairing_matched_generic_branch']}")
    o.append(f"     total delay refusals ................................. {C['DELAY_REFUSED_TOTAL']}")
    o.append(f"  4. BUG #6 invariant logs ([RescueDelayRefused] stderr) .. {len(refused_lines)}")
    o.append("")
    o.append("--- SUPPORTING ---")
    o.append(f"  planning calls .......................................... {C['planning_calls']}")
    o.append(f"  DELAY/CANCEL bonus gate OPEN ............................ {C['bonus_gate_open']}")
    o.append(f"  CONFIRMATION gate OPEN .................................. {C['confirmation_gate_open']}")
    o.append(f"  selection where repaired predicate was TRUE ............. {C['selected_delay_or_cancel_predicate_true']}")
    o.append(f"  _active_physical_pairing checks ......................... {C['pairing_checks']} "
             f"(generic-id={C['pairing_generic_id']}, specific-id={C['pairing_specific_id']})")
    o.append("")
    o.append(f"  options SELECTED by the planner: {dict(SELECTED_IDS)}")
    o.append(f"  rescue_action values reaching the executor: {dict(EXEC_ACTIONS)}")
    if SAMPLES:
        o.append("  sample refusal payloads:")
        o.extend(f"    {s}" for s in SAMPLES)
    if refused_lines[:5]:
        o.append("  sample [RescueDelayRefused] lines:")
        o.extend(f"    {ln}" for ln in refused_lines[:5])
    o.append("")
    o.append("--- SCENARIO METRICS ---")
    for ev in evals:
        o.append(f"  seed={ev['seed']} rescued={ev.get('rescued')} dead={ev.get('dead')} "
                 f"ff_deaths={ev.get('firefighter_deaths')} never_detected={ev.get('never_detected')} "
                 f"unreachable={ev.get('unreachable')} terminal_step={ev.get('terminal_step')}")

    text = "\n".join(o)
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"_delaybonus_gate_{a.tag}.txt")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    with open(dest.replace(".txt", ".json"), "w", encoding="utf-8") as fh:
        json.dump({"counters": dict(C), "selected": dict(SELECTED_IDS),
                   "exec_actions": dict(EXEC_ACTIONS), "evals": evals}, fh)
    print(text)
    print(f"\n[written] {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
