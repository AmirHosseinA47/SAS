"""fix14 - the UNSAFE prediction, checked per step rather than per release.

The prediction in outputs/fix14_part1.txt section 4 says the hazard
re-validation fix (measured hazard-target share 31.4% -> 1.3% AT PROPOSAL
TIME) should not fully protect a target that is HELD for many steps while the
fire and smoke fields move under it.

Counting release reasons answers that with n = 16. The probe records, on every
step, whether the ISSUED target and the HELD target are sitting in fire or
smoke right now (tgt_in_hazard, held_in_hazard), which answers it with n = 240
per run.

  tgt_in_hazard    the target the generator issued this step is in hazard NOW
  held_in_hazard   the cell currently under hold is in hazard NOW (FIX14 only)

P2ONLY is the control for this question: same tree, same hazard fix, no hold.
If the hold creates no new exposure, the two share the same rate.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS = ["D_north_101", "D_south_101", "A_north_101", "A_west_505"]
SIDES = [("_P2ONLY", "P2ONLY"), ("_FIX14", "FIX14")]


def load(tag, sfx):
    p = os.path.join(ROOT, "_tf_%s%s.json" % (tag, sfx))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rate(sr, key):
    vals = [r.get(key) for r in sr]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, 0
    return 100.0 * sum(1 for v in vals if v) / len(vals), len(vals)


def main() -> int:
    lines: list = []

    def log(m: str = "") -> None:
        print(m, flush=True)
        lines.append(m)

    log("=" * 78)
    log("UNSAFE EXPOSURE, PER STEP - ISSUED TARGET vs HELD TARGET")
    log("=" * 78)
    log("")
    log("For reference, the hazard re-validation round measured the")
    log("hazard-target share at proposal time as 31.4%% -> 1.3%%.")
    log("")
    hdr = ("%-13s %-7s %10s %8s %11s %8s"
           % ("run", "side", "issued%", "n", "held%", "n"))
    log(hdr)
    log("-" * len(hdr))
    for tag in RUNS:
        for sfx, side in SIDES:
            d = load(tag, sfx)
            if d is None:
                continue
            sr = d["step_records"]
            tr, tn = rate(sr, "tgt_in_hazard")
            hr, hn = rate(sr, "held_in_hazard")
            log("%-13s %-7s %10s %8d %11s %8d"
                % (tag, side,
                   "-" if tr is None else "%.1f" % tr, tn,
                   "-" if hr is None else "%.1f" % hr, hn))
        log("")

    log("=" * 78)
    log("AGGREGATE OVER THE FOUR PROBE RUNS")
    log("=" * 78)
    log("")
    for sfx, side in SIDES:
        ti = th = ni = nh = 0
        for tag in RUNS:
            d = load(tag, sfx)
            if d is None:
                continue
            sr = d["step_records"]
            for key in ("tgt_in_hazard", "held_in_hazard"):
                vals = [r.get(key) for r in sr]
                vals = [v for v in vals if v is not None]
                if key == "tgt_in_hazard":
                    ti += sum(1 for v in vals if v)
                    ni += len(vals)
                else:
                    th += sum(1 for v in vals if v)
                    nh += len(vals)
        log("%-7s issued-in-hazard %5d/%-5d = %5.1f%%    held-in-hazard %5d/%-5d = %s"
            % (side, ti, ni, (100.0 * ti / ni) if ni else 0.0, th, nh,
               ("%5.1f%%" % (100.0 * th / nh)) if nh else "n/a"))
    log("")

    out = os.path.join(ROOT, "fix14_hazard_check.txt")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
