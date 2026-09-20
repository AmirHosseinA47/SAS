# -*- coding: utf-8 -*-
"""Non-burnable-depot round: build the PRE-REGISTRATION table, before any wave run.

Every number here comes from the EXISTING corpus - the 27 recorded f3OFF runs
(outputs/_ffr_f3OFF_*.json, d3640e3 at the shipped default) - and from source
text. No run of this round is read, and none exists when this is generated; the
pool records this file's sha256 in its PREREG line, so the predictions below are
timestamped against the wave.

  -> outputs/dfp_prereg.txt
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = []


def P(s=""):
    OUT.append(str(s))
    print(s)


CANONICAL = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
RB_EXTRA = [("east", "half", s) for s in (111, 222, 333, 444)]
RB18 = ([("east", "half", s) for s in (101, 202, 303, 404, 505, 606, 707, 808, 909,
                                       111, 222, 333, 444)]
        + [("south", "half", s) for s in (101, 202, 303, 404, 505)])
KNOWN_G1 = [("east", 707), ("south", 101), ("south", 202), ("south", 404)]


def nm(t):
    rr = "def" if t[1] == "default" else t[1]
    return "f3OFF_%s_%s_%d" % (t[0], rr, t[2])


def load(t):
    p = os.path.join(HERE, "_ffr_%s.json" % nm(t))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def depot_cells(d):
    bs = d.get("base_station")
    if not bs:
        return set()
    size = int(bs["size"])
    origins = bs.get("depots") or [bs["origin"]]
    return {"%d,%d" % (int(ox) + i, int(oy) + j)
            for ox, oy in origins for i in range(size) for j in range(size)}


def row(t):
    d = load(t)
    if d is None:
        return None
    dep = depot_cells(d)
    bi = d.get("burn_intervals") or {}
    starts = [iv[0] for k, ivs in bi.items() if k in dep for iv in ivs]
    fd = min(starts) if starts else None
    ts = (d.get("eval") or {}).get("terminal_step")
    g = d.get("fire_ground_final") or {}
    ever = sum(1 for k in dep if k in g and (g[k][0] or g[k][1] or g[k][2]))
    burnt = sum(1 for k in dep if k in g and g[k][1])
    # re-rolled = the fire diverges while a victim outcome can still move
    rr = fd is not None and (ts is None or fd < ts)
    return dict(t=t, first=fd, term=ts, ever=ever, burnt=burnt, rr=rr,
                n_depot=len(dep), digest=d.get("fire_final_digest"))


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def main():
    head = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    P("=" * 96)
    P("NON-BURNABLE DEPOTS - PRE-REGISTRATION")
    P("=" * 96)
    P("Written BEFORE the wave. Every number is from the EXISTING f3OFF corpus (27 runs at")
    P("d3640e3, the shipped default) or from source text. Nothing from this round is read.")
    P("worktree %s at %s | python %s" % (ROOT, head, sys.version.split()[0]))
    for f in ("_dfp_queue.py", "_dfp_analyze.py", "_dfp_colour.py", "_dfp_pool.sh"):
        P("  %-18s sha256[:16] %s" % (f, sha(os.path.join(HERE, f))))
    for f in ("common_fixed_variables.py", "agents.py", "wildfire_model.py",
              "serve_dashboard.py", "main.py"):
        P("  %-26s sha256[:16] %s" % (f, sha(os.path.join(ROOT, f))))

    P("")
    P("-" * 96)
    P("A. SEED PROVENANCE - the samples, and how much of them is actually distinct")
    P("-" * 96)
    cset, fset, rset = set(CANONICAL), set(FRESH), set(RB18)
    P("  canonical 13 : %d tuples" % len(cset))
    P("  fresh 10     : %d tuples" % len(fset))
    P("  rb18 gate    : %d tuples" % len(rset))
    P("  rb18 that are ALSO canonical : %d  %s"
      % (len(rset & cset), sorted("%s/%d" % (a, c) for a, _b, c in (rset & cset))))
    P("  rb18 that are ALSO fresh     : %d  %s"
      % (len(rset & fset), sorted("%s/%d" % (a, c) for a, _b, c in (rset & fset))))
    P("  rb18 in neither (the extras) : %d  %s"
      % (len(rset - cset - fset), sorted("%s/%d" % (a, c) for a, _b, c in (rset - cset - fset))))
    P("  DISTINCT over canonical + fresh + rb18 : %d  (13 + 10 + 4; NOT 41)"
      % len(cset | fset | rset))
    P("  Every one of the %d already ran in the fire-mechanic round as f3OFF, so the corpus below" % len(cset | fset | rset))
    P("  covers this round's whole ff sample. The 20 WEST/NORTH runs are NEW: no west or north")
    P("  harness run exists anywhere in outputs/ at the shipped default, which is exactly why")
    P("  decision 6.4 asked for them. They have no corpus row and no prediction below.")
    P("")
    P("  FIRES SHARED BETWEEN RUNS: a fire is a function of (seed, wind) only - set_fire_agents")
    P("  draws the ignition cell and the per-cell fuel from SYSTEM_RANDOM before any role split -")
    P("  so east/default/N and east/half/N share a fire and differ only in the role split.")
    shared = sorted(s for s in (101, 202, 303))
    P("  In the canonical 13 that is %s: 13 runs, 10 distinct fires." % ["east/%d" % s for s in shared])

    P("")
    P("-" * 96)
    P("B. THE 6.5 PARTITION - which seeds are pinned-comparable and which are not")
    P("-" * 96)
    P("  A run is RE-ROLLED when its controls first depot ignition happens while a victim")
    P("  outcome can still move - strictly before terminal_step, or the run has no terminal step")
    P("  at all. From that step the two arms consume the shared RNG stream at different rates,")
    P("  so per-seed rescued / dead / never_detected signs are NOISE and are read POOLED only.")
    P("  A run whose depot ignition is AFTER terminal_step is pinned for VICTIM OUTCOMES by")
    P("  construction - but NOT for burnt_cells or vegetation, which keep moving after it.")
    P("  A run with NO depot ignition at all is pinned end to end and is a VACUOUS null.")
    P("")
    rows = {}
    for grp, tuples in (("canonical13", CANONICAL), ("fresh10", FRESH), ("rb18extra", RB_EXTRA)):
        P("  -- %s" % grp)
        P("     %-20s %7s %8s %6s %6s  %s" % ("run", "1st dep", "terminal", "ever", "burnt", "class"))
        for t in tuples:
            r = row(t)
            if r is None:
                P("     %-20s  MISSING FROM THE CORPUS" % ("%s/%s/%d" % t))
                continue
            rows[t] = r
            cls = ("RE-ROLLED" if r["rr"] else
                   ("VACUOUS (no depot ignition)" if r["first"] is None else "pinned for outcomes"))
            P("     %-20s %7s %8s %6d %6d  %s"
              % ("%s/%s/%d" % t, r["first"], r["term"], r["ever"], r["burnt"], cls))
    P("")
    for label, tuples in (("canonical 13", CANONICAL), ("fresh 10", FRESH),
                          ("the 23 (canonical+fresh)", CANONICAL + FRESH),
                          ("rb18 gate seeds", RB18)):
        rr = [t for t in tuples if t in rows and rows[t]["rr"]]
        pin = [t for t in tuples if t in rows and not rows[t]["rr"]]
        P("  %-26s re-rolled %2d / pinned %2d   pinned: %s"
          % (label, len(rr), len(pin), ", ".join("%s/%d" % (t[0], t[2]) for t in pin)))
    P("")
    P("  THE FOUR KNOWN route_blocked G1 REGRESSIONS, classified:")
    for w, s in KNOWN_G1:
        t = (w, "half", s)
        r = rows.get(t)
        if r is None:
            P("    %-12s no corpus row" % ("%s/%d" % (w, s)))
            continue
        P("    %-12s first depot %-5s terminal %-5s -> %s"
          % ("%s/%d" % (w, s), r["first"], r["term"],
             "RE-ROLLED, so a move here is NOT attributable" if r["rr"]
             else "PINNED - a move here IS attributable"))

    P("")
    P("-" * 96)
    P("C. PRE-REGISTERED PREDICTIONS")
    P("-" * 96)
    P("  P1 KILL SWITCH. dfpOFF equals dfpB on every recorded key except tag / repo / wall_s /")
    P("     params / extra_params, 13 of 13 on the canonical sample. (Value-identity, not byte:")
    P("     one dict's key order varies between processes.)")
    P("  P2 DRY. dfpDRY equals dfpOFF on fire_digests, fire_final_digest, burn_intervals,")
    P("     first_burn_step, fire_ground_final and eval.burnt_cells, 13 of 13. DRY writes no")
    P("     fuel, and the digest hashes fuel, so this is the one identity the digest CAN test.")
    P("  P3 ATTRIBUTION. For every run with a depot ignition, dfpON's per-step BURNING SET is")
    P("     identical to dfpOFF's on every step before that run's first depot ignition and")
    P("     differs AT it, and the first difference is control-only depot cells. The harness")
    P("     digest cannot test this: it hashes fuel and so differs at step 1 of every ON run.")
    P("     Earliest predicted first difference on the 23: step 54 (south/half/1010).")
    P("  P4 BOOKKEEPING. Zero depot cells ever burn in dfpON. The control's own per-run counts")
    P("     above are the EXACT predicted shifts: untouched vegetation +ever, burnt_cells -burnt.")
    P("     NO one-signed prediction is registered on the whole grid: the guaranteed term is")
    P("     ~26 cells per run and the re-roll noise is ~155 with no systematic sign")
    P("     (outputs/firemech2_part1.txt, measured with a write-free draw-stream offset).")
    P("  P5 DRONE STEPS IN FIRE falls, and its DEPOT component falls to ZERO - no UAV can stand")
    P("     on a burning depot cell if no depot cell burns. The SEARCH component (outside the")
    P("     depot) is not predicted in either direction: it is a different problem.")
    P("  P6 RESCUED does not decrease, judged POOLED on each sample. Per-seed moves on the")
    P("     re-rolled seeds listed in B are not attributable and are not reported as such.")
    P("  P7 ROUTE_BLOCKED. No NEW G1 failure beyond the four known. Of those four, only")
    P("     east/707 is pinned-comparable; the other three re-roll and could move either way.")
    P("  P8 TESTS. The failing NAME SET is unchanged from 6281542 (count alone is not enough -")
    P("     this project has three recorded cases of counts agreeing while sets differed).")
    P("  P9 COLOUR. #193cff, 12.85 dE normal / 6.69 dE worst chromatic against the 162-entry")
    P("     effective palette, no exact-hex collision. outputs/_dfp_colour.txt.")
    P("  P10 LAYOUT. Full-page capture at display scales 1, 1.25 and 1.5: every table's row")
    P("     heights equal within the page, and no panel's scrollWidth exceeds its clientWidth.")

    P("")
    P("-" * 96)
    P("D. WHAT WOULD FALSIFY THE ROUND")
    P("-" * 96)
    P("  * P1 fails  -> the switch is not a kill switch; the round stops.")
    P("  * P3 fails  -> 'the depot stopped burning' is NOT what changed, and every outcome")
    P("                 number below it is uninterpretable. This is the load-bearing one.")
    P("  * P5 fails on the depot component -> the change does not do the thing it exists for.")
    P("  * P6 fails pooled -> ships OFF, on the fire mechanic's precedent.")

    p = os.path.join(HERE, "dfp_prereg.txt")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")
    print("\nwrote %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
