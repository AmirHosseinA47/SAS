"""Latch-fix round: aggregate the 17-seed x 2-mode sweep run through _lf_assert.py.

Three questions, in order of what the gate needs:

  1. LATCH COUNTS at mode 0 and mode 3, before vs after. "Before" is the
     diagnosis round's own artifacts (outputs/_l808sw2_*.json, produced by
     _l808_sweep.py at f4e79d5); "after" is _lfsw_*_sw2.json. Fire-enclosed
     units and horizon flags are reported SEPARATELY and never folded into the
     count, per outputs/latchfix_part1.txt sections 0.2 and 6.2.

  2. ACCOUNTABILITY: every unit the fix cleared must end DISPATCHABLE, DEAD,
     OFF_GRID, RE_DISPATCHED or IDLE_NO_WORK. Any UNACCOUNTED verdict fails the
     round - that is gate item 5, asserted rather than inferred.

  3. OUTCOME MOVEMENT: rescued / dead / unreachable / never_detected /
     firefighter_deaths / terminal_step, seed-matched against the pre-fix
     artifacts. The branch's own trigger predicts zero movement; this measures it.

Also cross-checks the switch-0 control runs against the pre-fix artifacts, which
proves the NEW instrument agrees with the OLD one on the runs that latch today -
without that, a change in latch count could be an instrument artefact.

usage: _lf_sweepanalyze.py
Read-only.
"""
from __future__ import annotations

import glob
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
METRICS = ("rescued", "dead", "unreachable", "never_detected",
           "firefighter_deaths", "terminal_step")


def load_after():
    out = {}
    for p in sorted(glob.glob(os.path.join(BASE, "_lfsw_s*_m*_*_sw*.json"))):
        with open(p) as f:
            d = json.load(f)
        key = (int(d["seed"]), int(d["mode"]), str(d["wind"]), int(d["switch"]))
        out[key] = d
    return out


def load_before():
    out = {}
    for p in sorted(glob.glob(os.path.join(BASE, "_l808sw2_s*_m*_*.json"))):
        with open(p) as f:
            d = json.load(f)
        out[(int(d["seed"]), int(d["mode"]), str(d["wind"]))] = d
    return out


def main():
    after, before = load_after(), load_before()
    fix = {k: v for k, v in after.items() if k[3] == 2}
    ctl = {k: v for k, v in after.items() if k[3] == 0}

    print("=" * 92)
    print("1. LATCH COUNTS  (genuine = alive, on grid, not enclosed, no live referent,")
    print("                  and undispatchable.  enclosed/horizon reported separately)")
    print("=" * 92)
    print("  %-6s %-6s %-6s | %-22s | %-30s" % ("", "", "", "BEFORE (f4e79d5)", "AFTER (fix, switch 2)"))
    print("  %-6s %-6s %-6s | %-22s | %s" % ("seed", "mode", "wind", "latched units", "latched  encl  horiz  cleared"))
    print("  " + "-" * 88)
    tot = {0: [0, 0, 0, 0], 3: [0, 0, 0, 0]}   # before_units, after_units, runs, cleared
    changed = []
    for (seed, mode, wind, _sw), d in sorted(fix.items()):
        b = before.get((seed, mode, wind))
        b_units = len(b.get("latched") or []) if b else None
        a_units = len(d.get("latched") or [])
        enc = len(d.get("enclosed_held") or [])
        hor = len(d.get("horizon") or [])
        cl = int((d.get("counters") or {}).get("stale_cleared_total", 0))
        tot[mode][0] += (b_units or 0)
        tot[mode][1] += a_units
        tot[mode][2] += 1
        tot[mode][3] += cl
        flag = ""
        if b_units or a_units or cl:
            flag = "  <<<"
            changed.append((seed, mode, wind, b_units, a_units, cl))
        print("  %-6d %-6d %-6s | %-22s | %-7d %-5d %-6d %-7d%s"
              % (seed, mode, wind, str(b_units), a_units, enc, hor, cl, flag))
    print("  " + "-" * 88)
    for mode in (0, 3):
        b_u, a_u, runs, cl = tot[mode]
        print("  MODE %d over %2d runs:  latched units BEFORE=%d  AFTER=%d   flags cleared=%d"
              % (mode, runs, b_u, a_u, cl))

    print()
    print("=" * 92)
    print("2. ACCOUNTABILITY - every cleared unit must be accounted for (gate item 5)")
    print("=" * 92)
    verdicts, unacc, n_clear = {}, [], 0
    for (seed, mode, wind, _sw), d in sorted(fix.items()):
        for c in d.get("clears") or []:
            n_clear += 1
            v = str(c.get("verdict"))
            verdicts[v] = verdicts.get(v, 0) + 1
            if v.startswith("UNACCOUNTED"):
                unacc.append((seed, mode, wind, c.get("unit"), v))
            print("  s%-5d m%d %-5s  %-10s cleared at step %-4s  before=%s/%s  "
                  "after=%s/%s dispatchable=%s  work_after=%s  -> %s"
                  % (seed, mode, wind, c.get("unit"), c.get("step"),
                     c["before"]["status"], c["before"]["assigned"],
                     c["after"]["status"], c["after"]["assigned"],
                     c["after"]["dispatchable"],
                     c.get("ever_had_work_after_clear"), v))
    if not n_clear:
        print("  (no unit was cleared in this sample)")
    print("  " + "-" * 88)
    print("  verdicts: %s" % (verdicts or "none"))
    print("  UNACCOUNTED: %s" % (unacc or "NONE"))

    print()
    print("=" * 92)
    print("3. OUTCOME MOVEMENT vs the pre-fix artifacts, seed-matched")
    print("=" * 92)
    moved = []
    for (seed, mode, wind, _sw), d in sorted(fix.items()):
        b = before.get((seed, mode, wind))
        if not b:
            print("  s%-5d m%d %-5s  NO BASELINE" % (seed, mode, wind))
            continue
        be, ae = b.get("eval") or {}, d.get("eval") or {}
        diff = {k: (be.get(k), ae.get(k)) for k in METRICS if be.get(k) != ae.get(k)}
        if diff:
            moved.append((seed, mode, wind, diff))
    if moved:
        for seed, mode, wind, diff in moved:
            print("  s%-5d m%d %-5s  MOVED %s" % (seed, mode, wind, diff))
    else:
        print("  NO METRIC MOVED on any of the %d runs, on any of: %s"
              % (len(fix), ", ".join(METRICS)))

    print()
    print("=" * 92)
    print("4. INSTRUMENT CONSISTENCY - switch-0 control vs the pre-fix artifacts")
    print("=" * 92)
    bad = 0
    for (seed, mode, wind, _sw), d in sorted(ctl.items()):
        b = before.get((seed, mode, wind))
        b_units = len(b.get("latched") or []) if b else None
        a_units = len(d.get("latched") or [])
        hor = len(d.get("horizon") or [])
        be, ae = (b.get("eval") or {}) if b else {}, d.get("eval") or {}
        same = all(be.get(k) == ae.get(k) for k in METRICS)
        ok = (b_units == a_units + hor) and same
        bad += 0 if ok else 1
        print("  s%-5d m%d %-5s  old_latched=%s  new latched=%d horizon=%d  "
              "metrics_match=%s  -> %s"
              % (seed, mode, wind, str(b_units), a_units, hor, same,
                 "OK" if ok else "DIVERGES"))
    print("  " + "-" * 88)
    print("  control runs diverging from the old instrument: %d" % bad)

    print()
    print("=" * 92)
    genuine = sum(tot[m][1] for m in (0, 3))
    print("SWEEP VERDICT: latched units after the fix = %d (mode 0 = %d, mode 3 = %d)"
          % (genuine, tot[0][1], tot[3][1]))
    print("               units cleared = %d, unaccounted = %d, metrics moved on %d runs"
          % (n_clear, len(unacc), len(moved)))
    print("               GATE: %s"
          % ("PASS" if (genuine == 0 and not unacc and not moved) else "SEE ABOVE"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
