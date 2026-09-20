"""Depot-fireproof question, Part 1: how often does fire reach a depot in the
EXISTING corpus, and WHEN relative to the mission?

Reads recorded seed-matched harness runs at the shipped default (tag f3OFF =
d3640e3 with every FF_FIREFIGHT action switch 0; value-identical to fmOFF 23/23).
No model import, no simulation. Every run records burn_intervals: "x,y" ->
[[start, end], ...] per cell, plus terminal_step and the evaluation dict.

Two effects the maintainer asked to keep apart:
  BOOKKEEPING  depot cells that burned in the control can no longer burn. The
               exact per-run count is "depot cells that ever burned".
  BEHAVIOURAL  clearing fuel draws no RNG and a fuel-less cell KEEPS drawing its
               number each tick (agents.py firefighter_remove_fuel), so a real
               arm's fire equals the control's EXACTLY until the first depot cell
               that would have ignited. If that first ignition falls AFTER
               terminal_step, no rescue outcome can move, by construction.

usage: _dfp_corpus.py [tag ...]        default: f3OFF
"""
from __future__ import annotations
import glob, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
W = H = 50; SIZE = 5
DEPOTS = {"NW": (0, 45), "SE": (45, 0)}


def cells(o):
    return {(o[0] + i, o[1] + j) for i in range(SIZE) for j in range(SIZE)}


def ring(o, k=1):
    """Cells within Chebyshev k of the block but outside it and on the grid."""
    blk = cells(o)
    out = set()
    for (x, y) in blk:
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                c = (x + dx, y + dy)
                if c not in blk and 0 <= c[0] < W and 0 <= c[1] < H:
                    out.add(c)
    return out


def main() -> int:
    tags = sys.argv[1:] or ["f3OFF"]
    for tag in tags:
        files = sorted(glob.glob(os.path.join(BASE, "_ffr_%s_*.json" % tag)))
        print("=" * 100)
        print("tag %s: %d recorded runs" % (tag, len(files)))
        print("%-22s %5s %5s | %-16s %-16s | first depot  vs terminal | depot cells burned  | burnt_cells"
              % ("run", "steps", "term", "NW first/cells", "SE first/cells"))
        n = reach = before = 0; tot_cells = []; firsts = []; rows = []
        for fp in files:
            d = json.load(open(fp))
            bi = d.get("burn_intervals") or {}
            burned = {}
            for k, iv in bi.items():
                x, y = (int(v) for v in k.split(","))
                if iv:
                    burned[(x, y)] = min(s for s, _e in iv)
            term = d.get("terminal_step"); steps = d.get("steps")
            per = {}
            for name, o in DEPOTS.items():
                hit = {c: burned[c] for c in cells(o) if c in burned}
                per[name] = (min(hit.values()) if hit else None, len(hit))
            first = min([v[0] for v in per.values() if v[0] is not None], default=None)
            ncell = sum(v[1] for v in per.values())
            ev = d.get("eval") or {}
            n += 1
            if first is not None:
                reach += 1; firsts.append(first)
                if term is None or first < term:
                    before += 1
            tot_cells.append(ncell)
            name = os.path.basename(fp)[len("_ffr_%s_" % tag):-5]
            rel = "never" if first is None else ("BEFORE" if (term is None or first < term) else "after")
            rows.append((name, first, term, ncell))
            print("%-22s %5s %5s | %-16s %-16s | %5s  %-6s %5s | %3d of 50            | %s"
                  % (name, steps, term, "%s / %d" % per["NW"], "%s / %d" % per["SE"],
                     first, rel, term, ncell, ev.get("burnt_cells")))
        print("-" * 100)
        print("fire reaches a depot block (>=1 depot cell ever burns): %d of %d runs (%.0f%%)"
              % (reach, n, 100.0 * reach / n))
        print("  of those, the FIRST depot ignition is BEFORE the mission's terminal step (or no terminal step): %d of %d"
              % (before, reach))
        print("  runs where a rescue outcome could move at all (reach AND before terminal): %d of %d (%.0f%%)"
              % (before, n, 100.0 * before / n))
        if firsts:
            fs = sorted(firsts)
            print("  first depot ignition step: min %d, median %d, max %d" % (fs[0], fs[len(fs) // 2], fs[-1]))
        tc = sorted(tot_cells)
        print("BOOKKEEPING: depot cells that ever burned per run: min %d, median %d, max %d, mean %.1f of 50; total %d over %d runs"
              % (tc[0], tc[len(tc) // 2], tc[-1], sum(tc) / float(len(tc)), sum(tc), len(tc)))
    print("(the 50 depot cells are 2.0%% of the %d-cell grid)" % (W * H))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
