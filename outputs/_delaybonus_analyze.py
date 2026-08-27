"""Post-process a _delaybonus_probe_*.json into the Q5 answer.

Adds a THIRD counterfactual the probe itself does not compute:
  what would be selected if BOTH the predicate were repaired AND the risk-signal
  gate were forced open. That isolates how much of the dead behaviour is owed to
  the predicate vs. to the missing route_risk/communication_risk plumbing.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

BONUS = 0.75


def analyse(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    recs = blob["records"]
    out: list[str] = []

    n = len(recs)
    out.append(f"planning calls: {n}")

    rr = [r["signals"]["route_risk"] for r in recs]
    cr = [r["signals"]["communication_risk"] for r in recs]
    vc = [r["signals"]["victim_confidence"] for r in recs]
    un = [r["signals"]["uncertainty"] for r in recs]

    def d(name, vals, thr, cmp_ge=True):
        hit = sum(1 for v in vals if (v >= thr if cmp_ge else v < thr))
        op = ">=" if cmp_ge else "<"
        out.append(
            f"  {name:22s} min={min(vals):.4f} max={max(vals):.4f} "
            f"distinct={sorted(set(round(v,4) for v in vals))[:6]}  {op}{thr}: {hit}/{len(vals)}"
        )

    out.append("SIGNALS:")
    d("route_risk", rr, 0.55)
    d("communication_risk", cr, 0.55)
    d("victim_confidence", vc, 0.45, cmp_ge=False)
    d("uncertainty", un, 0.55)

    gate = sum(1 for r in recs if r["gate_open"])
    out.append(f"DELAY/CANCEL BONUS GATE OPEN: {gate}/{n}")
    conf_gate = sum(1 for r in recs if r["signals"]["victim_confidence"] < 0.45
                    or r["signals"]["uncertainty"] >= 0.55)
    out.append(f"(for contrast) CONFIRMATION gate open: {conf_gate}/{n}")

    pn = sum(1 for r in recs for w in r["rows"] if w["pred_now"])
    pf = sum(1 for r in recs for w in r["rows"] if w["pred_fixed"])
    out.append(f"predicate TRUE  current={pn}   repaired={pf}")

    out.append(f"winners (current) : {dict(Counter(r['winner_now'] for r in recs))}")
    out.append(f"winners (repaired): {dict(Counter(r['winner_fixed'] for r in recs))}")
    out.append(f"selections that FLIP with the repair alone: "
               f"{sum(1 for r in recs if r['flipped'])}/{n}")

    # ---- counterfactual C: repaired predicate AND gate forced open
    flips_c = 0
    wins_c: Counter = Counter()
    for r in recs:
        feas = [w for w in r["rows"] if w["feasible"]]
        if not feas:
            continue
        best = max(feas, key=lambda w: (w["pref_now"] + (BONUS if w["pred_fixed"] else 0.0),
                                        w["score"]))
        wins_c[best["id"]] += 1
        if best["id"] != r["winner_now"]:
            flips_c += 1
    out.append("")
    out.append("COUNTERFACTUAL C - repaired predicate AND risk-gate forced open:")
    out.append(f"  winners: {dict(wins_c)}")
    out.append(f"  selections that would flip: {flips_c}/{n}")

    gaps = [r["gap"] for r in recs if r["gap"] is not None]
    if gaps:
        ties = sum(1 for g in gaps if abs(g) < 1e-12)
        out.append("")
        out.append("UTILITY GAP  winner.score - best_delay.score:")
        out.append(f"  n={len(gaps)} min={min(gaps):.6f} max={max(gaps):.6f} "
                   f"mean={sum(gaps)/len(gaps):.6f}")
        out.append(f"  EXACT TIES (gap==0): {ties}/{len(gaps)}")
        out.append(f"  gaps larger than _DELAY_CANCEL_BONUS={BONUS}: "
                   f"{sum(1 for g in gaps if g > BONUS)}/{len(gaps)}")

    scores = [w["score"] for r in recs for w in r["rows"]]
    out.append(f"  all option scores: min={min(scores):.6f} max={max(scores):.6f} "
               f"distinct={sorted(set(round(s,6) for s in scores))[:6]}")
    feas_all = all(w["feasible"] for r in recs for w in r["rows"])
    out.append(f"  every option feasible: {feas_all}")

    out.append("")
    out.append("SCENARIO METRICS:")
    for ev in blob["evals"]:
        out.append(f"  seed={ev['seed']} rescued={ev.get('rescued')} dead={ev.get('dead')} "
                   f"ff_deaths={ev.get('firefighter_deaths')} "
                   f"never_detected={ev.get('never_detected')} "
                   f"unreachable={ev.get('unreachable')}")
    return "\n".join(out)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(f"\n===================== {p} =====================")
        print(analyse(p))
