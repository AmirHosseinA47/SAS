"""Part 1 Q5 instrumentation: quantify the utility gap for rescue_decision/delay.

Live-instruments RescuePlanner over a real scenario run and records, per step:
  - the rescue signals dict (route_risk / communication_risk gate the bonus)
  - every scored rescue option (score, feasible, current pref bonus)
  - the winner, and what the winner WOULD be if _is_delay_or_cancel_option were repaired

Does not modify any source file: the repaired predicate is applied here as a shadow
computation only. Run:
    python outputs/_delaybonus_probe.py --scenario D --wind east --steps 240 \
        --seeds 101,202,303,404,505 --tag pre
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

# ---------------------------------------------------------------- shadow predicate
_DELAY_CANCEL_ACTIONS = frozenset({"delay_rescue", "cancel_rescue"})


def repaired_is_delay_or_cancel(option_type: str, params: dict) -> bool:
    """The candidate repair: match the rescue_action VALUE, keep the legacy fallbacks."""
    action = str(params.get("rescue_action", "") or "").strip().lower()
    if action in _DELAY_CANCEL_ACTIONS:
        return True
    if any(token in option_type for token in ("delay", "cancel", "postpone", "abort")):
        return True
    return (
        rp._is_truthy(params.get("delay_rescue"))
        or rp._is_truthy(params.get("postpone_rescue"))
        or rp._is_truthy(params.get("cancel_rescue"))
    )


# ---------------------------------------------------------------- instrumentation
RECORDS: list[dict] = []
STATE = {"step": 0, "seed": 0}


def install_probe() -> None:
    orig_signals = rp._rescue_signals
    orig_select = rp._select_rescue_option
    pending: dict = {}

    def probe_signals(analysis, context, options):
        sig = orig_signals(analysis, context, options)
        pending["signals"] = dict(sig)
        return sig

    def probe_select(scored, options, signals):
        selected = orig_select(scored, options, signals)

        high_route = signals["route_risk"] >= rp._HIGH_ROUTE_RISK
        high_comm = signals["communication_risk"] >= rp._HIGH_COMM_RISK
        gate_open = high_route or high_comm

        rows = []
        for entry in scored:
            opt = entry.option
            params = option_parameters(opt)
            ot = str(getattr(opt, "option_type", "") or "").lower()
            cur = rp._is_delay_or_cancel_option(ot, params)
            fix = repaired_is_delay_or_cancel(ot, params)
            rows.append(
                {
                    "id": entry.evaluation.option_id,
                    "type": ot,
                    "action": str(params.get("rescue_action", "") or ""),
                    "score": round(float(entry.score), 6),
                    "feasible": bool(entry.evaluation.feasible),
                    "pref_now": round(float(rp._preference_adjustment(entry, signals)), 6),
                    "pred_now": cur,
                    "pred_fixed": fix,
                    # what the bonus WOULD be if the predicate were repaired
                    "pref_fixed": round(
                        float(rp._preference_adjustment(entry, signals))
                        + (rp._DELAY_CANCEL_BONUS if (gate_open and fix and not cur) else 0.0),
                        6,
                    ),
                }
            )

        feasible = [r for r in rows if r["feasible"]]
        winner_now = option_id(selected) if selected is not None else ""
        winner_fixed = ""
        if feasible:
            best = max(feasible, key=lambda r: (r["pref_fixed"], r["score"]))
            winner_fixed = best["id"]

        delay_rows = [r for r in rows if r["action"] == "delay_rescue"]
        best_delay = max(delay_rows, key=lambda r: r["score"]) if delay_rows else None
        win_row = next((r for r in rows if r["id"] == winner_now), None)

        RECORDS.append(
            {
                "seed": STATE["seed"],
                "step": STATE["step"],
                "signals": pending.get("signals", dict(signals)),
                "gate_open": gate_open,
                "n_options": len(rows),
                "n_delay_options": len(delay_rows),
                "winner_now": winner_now,
                "winner_fixed": winner_fixed,
                "flipped": bool(winner_fixed and winner_fixed != winner_now),
                "win_score": win_row["score"] if win_row else None,
                "best_delay_score": best_delay["score"] if best_delay else None,
                "gap": (
                    round(win_row["score"] - best_delay["score"], 6)
                    if (win_row and best_delay)
                    else None
                ),
                "rows": rows,
            }
        )
        return selected

    rp._rescue_signals = probe_signals
    rp._select_rescue_option = probe_select


# ---------------------------------------------------------------- run
def scenario_params(scenario: str, wind: str):
    """Byte-for-byte mirror of evaluate_scenarios._scenario_params at CLI defaults."""
    preset = BUILTIN_SCENARIOS.get(scenario, {})
    num_agents = int(preset.get("NUM_AGENTS", 3))
    fire_trackers, victim_searchers = _resolve_role_count_params(num_agents, None, None)
    return {
        "NUM_AGENTS": num_agents,
        "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
        "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)),
        "WIND_DIRECTION": str(wind),
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": fire_trackers,
        "NUM_VICTIM_SEARCHERS": victim_searchers,
    }


def run_seed(seed: int, params: dict, steps: int) -> dict:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    STATE["seed"] = seed
    terminal_step = None
    step = 0
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            STATE["step"] = step
            model.step()
            step += 1
            if terminal_step is None:
                panel = model.get_dashboard_state()
                mission = panel.get("mission_status", {}) or {}
                if mission.get("all_victims_terminal"):
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
    ap.add_argument("--tag", default="probe")
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(",")]
    params = scenario_params(args.scenario, args.wind)

    install_probe()
    evals = []
    for sd in seeds:
        evals.append(run_seed(sd, params, args.steps))

    label = f"{args.scenario}/{args.wind}"
    out = []
    out.append(f"=== DELAY-BONUS PROBE [{args.tag}] {label} seeds={seeds} steps={args.steps} ===")
    out.append(f"python={sys.version.split()[0]}  planning calls recorded={len(RECORDS)}")
    out.append("")

    # --- signal distribution: the gate on the bonus
    rr = [r["signals"]["route_risk"] for r in RECORDS]
    cr = [r["signals"]["communication_risk"] for r in RECORDS]
    vc = [r["signals"]["victim_confidence"] for r in RECORDS]
    un = [r["signals"]["uncertainty"] for r in RECORDS]

    def dist(name, vals, thr):
        if not vals:
            out.append(f"{name}: no samples")
            return
        over = sum(1 for v in vals if v >= thr)
        out.append(
            f"{name:20s} min={min(vals):.4f} max={max(vals):.4f} "
            f"mean={sum(vals)/len(vals):.4f}  >= {thr}: {over}/{len(vals)} "
            f"({100.0*over/len(vals):.2f}%)   distinct={sorted(set(round(v,4) for v in vals))[:8]}"
        )

    out.append("--- SIGNALS (these gate the bonus) ---")
    dist("route_risk", rr, rp._HIGH_ROUTE_RISK)
    dist("communication_risk", cr, rp._HIGH_COMM_RISK)
    dist("victim_confidence(<)", vc, rp._LOW_VICTIM_CONFIDENCE)
    dist("uncertainty", un, rp._HIGH_UNCERTAINTY)
    out.append("")

    gate_open = sum(1 for r in RECORDS if r["gate_open"])
    out.append(f"BONUS GATE OPEN (route>=%.2f or comm>=%.2f): %d / %d steps"
               % (rp._HIGH_ROUTE_RISK, rp._HIGH_COMM_RISK, gate_open, len(RECORDS)))
    out.append("")

    # --- option population
    n_delay = sum(r["n_delay_options"] for r in RECORDS)
    out.append(f"rescue_decision/delay options generated: {n_delay} "
               f"(present in {sum(1 for r in RECORDS if r['n_delay_options'])}/{len(RECORDS)} planning calls)")

    pred_now_true = sum(1 for r in RECORDS for row in r["rows"] if row["pred_now"])
    pred_fix_true = sum(1 for r in RECORDS for row in r["rows"] if row["pred_fixed"])
    out.append(f"_is_delay_or_cancel_option TRUE  (current) : {pred_now_true}")
    out.append(f"_is_delay_or_cancel_option TRUE  (repaired): {pred_fix_true}")
    out.append("")

    # --- selection
    wins_now = Counter(r["winner_now"] for r in RECORDS)
    wins_fixed = Counter(r["winner_fixed"] for r in RECORDS)
    out.append("--- WINNERS (current predicate) ---")
    for k, v in wins_now.most_common():
        out.append(f"  {v:6d}  {k}")
    out.append("--- WINNERS (repaired predicate, shadow) ---")
    for k, v in wins_fixed.most_common():
        out.append(f"  {v:6d}  {k}")
    flipped = sum(1 for r in RECORDS if r["flipped"])
    out.append("")
    out.append(f"SELECTIONS THAT WOULD FLIP with the repair: {flipped} / {len(RECORDS)}")
    delay_selected_now = sum(1 for r in RECORDS if "delay" in r["winner_now"])
    delay_selected_fix = sum(1 for r in RECORDS if "delay" in r["winner_fixed"])
    out.append(f"DELAY selected now: {delay_selected_now}   DELAY selected if repaired: {delay_selected_fix}")
    out.append("")

    # --- utility gap
    gaps = [r["gap"] for r in RECORDS if r["gap"] is not None]
    if gaps:
        out.append("--- UTILITY GAP: winner.score - best_delay.score ---")
        out.append(f"  n={len(gaps)} min={min(gaps):.6f} max={max(gaps):.6f} mean={sum(gaps)/len(gaps):.6f}")
        out.append(f"  gap == 0 (exact tie): {sum(1 for g in gaps if abs(g) < 1e-12)} / {len(gaps)}")
        out.append(f"  _DELAY_CANCEL_BONUS = {rp._DELAY_CANCEL_BONUS}")
        big = sum(1 for g in gaps if g > rp._DELAY_CANCEL_BONUS)
        out.append(f"  gaps LARGER than the bonus: {big} / {len(gaps)}")
    out.append("")

    # --- sample steps
    out.append("--- SAMPLE PLANNING CALLS (first 3 seeds, steps 0/40/120/239) ---")
    want = {0, 40, 120, 239}
    shown = 0
    for r in RECORDS:
        if r["step"] not in want or shown >= 12:
            continue
        shown += 1
        s = r["signals"]
        out.append(
            f"  seed={r['seed']} step={r['step']} route_risk={s['route_risk']:.3f} "
            f"comm_risk={s['communication_risk']:.3f} vic_conf={s['victim_confidence']:.3f} "
            f"unc={s['uncertainty']:.3f} gate_open={r['gate_open']}"
        )
        for row in r["rows"]:
            mark = "<== WINNER" if row["id"] == r["winner_now"] else ""
            out.append(
                f"      {row['id']:52s} score={row['score']:.4f} feas={row['feasible']!s:5s} "
                f"pref={row['pref_now']:.3f} pred_now={row['pred_now']!s:5s} "
                f"pred_fix={row['pred_fixed']!s:5s} {mark}"
            )
    out.append("")

    # --- scenario metrics
    out.append("--- SCENARIO METRICS ---")
    for ev in evals:
        out.append(
            f"  seed={ev['seed']} rescued={ev.get('rescued')} dead={ev.get('dead')} "
            f"ff_deaths={ev.get('firefighter_deaths')} never_detected={ev.get('never_detected')} "
            f"unreachable={ev.get('unreachable')} terminal_step={ev.get('terminal_step')}"
        )

    text = "\n".join(out)
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f"_delaybonus_probe_{args.tag}.txt")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    with open(dest.replace(".txt", ".json"), "w", encoding="utf-8") as fh:
        json.dump({"records": RECORDS, "evals": evals}, fh)
    print(text)
    print(f"\n[written] {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
