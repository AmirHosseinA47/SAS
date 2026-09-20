"""Depot-fireproof Part 1, second pass - the numbers a verifier corrected, recomputed.

  * FINAL state of every depot cell that ever burned (fire_ground_final is recorded
    per cell: [has_burned, burnt, burning]) -> the by-construction shift in
    burnt_cells is the BURNT count, not the ever-burned count
  * distinct fire histories (the same seed shares its fire across role splits)
  * the same statistics restricted to the 23-run gate sample (canonical 13 + fresh
    10 = the 27 minus the four rb18 extras east/half 111, 222, 333, 444)
  * cells outside a corner depot block whose ignition probability a depot cell can
    contribute to: Moore radius 3, CUT at Euclidean distance 3 (distance_rate)

usage: _dfp_corpus2.py            -> outputs/_dfp_corpus2.txt
"""
from __future__ import annotations
import glob, hashlib, json, math, os

BASE = os.path.dirname(os.path.abspath(__file__))
W = H = 50
DEPOTS = {"NW": (0, 45), "SE": (45, 0)}
EXTRAS = {"east_half_111", "east_half_222", "east_half_333", "east_half_444"}
OUT = []


def P(s=""):
    OUT.append(s); print(s)


def cells(o):
    return {(o[0] + i, o[1] + j) for i in range(5) for j in range(5)}


def main() -> int:
    depot = set().union(*[cells(o) for o in DEPOTS.values()])
    runs = []
    for fp in sorted(glob.glob(os.path.join(BASE, "_ffr_f3OFF_*.json"))):
        d = json.load(open(fp)); name = os.path.basename(fp)[len("_ffr_f3OFF_"):-5]
        bi = d["burn_intervals"]; gf = d["fire_ground_final"]
        ever = {tuple(int(v) for v in k.split(",")): min(s for s, _ in iv) for k, iv in bi.items() if iv}
        hit = {c: ever[c] for c in depot if c in ever}
        fin = {"burnt": 0, "scorched": 0, "burning": 0}
        for c in hit:
            hb, bt, bg = gf["%d,%d" % c]
            fin["burning" if bg else ("burnt" if bt else "scorched")] += 1
        fire_id = hashlib.sha256(json.dumps(sorted((k, v) for k, v in bi.items())).encode()).hexdigest()[:10]
        runs.append({"name": name, "first": min(hit.values()) if hit else None, "n": len(hit), "fin": fin,
                     "term": d.get("terminal_step"), "fire": fire_id, "spread": len(ever),
                     "burnt_cells": (d.get("eval") or {}).get("burnt_cells")})

    def report(title, rs):
        P(title)
        reach = [r for r in rs if r["first"] is not None]
        nofire = [r for r in rs if r["spread"] <= 1]
        P("  runs %d | fire reaches a depot %d | never %d (of which the fire died on its first tick - ONE cell ever burned: %s)"
          % (len(rs), len(reach), len(rs) - len(reach), [r["name"] for r in nofire]))
        bt = [r for r in reach if r["term"] is not None and r["first"] < r["term"]]
        nt = [r for r in reach if r["term"] is None]
        af = [r for r in reach if r["term"] is not None and r["first"] >= r["term"]]
        P("  first depot ignition strictly before a recorded terminal_step %d; no terminal step at all %d (%s); after %d"
          % (len(bt), len(nt), [r["name"] for r in nt], len(af)))
        fs = sorted(r["first"] for r in reach)
        P("  first depot ignition step: min %d, median %s, max %d" % (fs[0], fs[len(fs) // 2], fs[-1]))
        tot = {k: sum(r["fin"][k] for r in rs) for k in ("burnt", "scorched", "burning")}
        ever = sum(r["n"] for r in rs)
        P("  depot cells that ever burned: %d (mean %.1f per run) -> at step 240: burnt %d, scorched %d, still burning %d"
          % (ever, ever / float(len(rs)), tot["burnt"], tot["scorched"], tot["burning"]))
        P("  => by-construction shift per run: untouched vegetation +%.1f, burnt_cells -%.1f (range %d..%d)"
          % (ever / float(len(rs)), tot["burnt"] / float(len(rs)), min(r["fin"]["burnt"] for r in rs), max(r["fin"]["burnt"] for r in rs)))
        fires = {}
        for r in rs:
            fires.setdefault(r["fire"], []).append(r["name"])
        dup = [v for v in fires.values() if len(v) > 1]
        reach_f = len({r["fire"] for r in reach})
        P("  DISTINCT fire histories: %d (shared: %s); distinct fires reaching a depot: %d" % (len(fires), dup, reach_f))
        P()

    report("ALL 27 RECORDED f3OFF RUNS", runs)
    report("THE 23-RUN GATE SAMPLE (canonical 13 + fresh 10; the four rb18 extras removed)",
           [r for r in runs if r["name"] not in EXTRAS])
    P("PER RUN (name, first depot ignition, terminal, ever-burned depot cells, of which burnt at step 240):")
    for r in runs:
        P("  %-18s %5s %5s %3d %3d%s" % (r["name"], r["first"], r["term"], r["n"], r["fin"]["burnt"],
                                        "   [rb18 extra, not in the 23]" if r["name"] in EXTRAS else ""))
    # neighbours a corner depot can contribute to
    for name, o in DEPOTS.items():
        blk = cells(o)
        moore = {(x + dx, y + dy) for (x, y) in blk for dx in range(-3, 4) for dy in range(-3, 4)
                 if (x + dx, y + dy) not in blk and 0 <= x + dx < W and 0 <= y + dy < H}
        eucl = {c for c in moore if any(math.hypot(c[0] - b[0], c[1] - b[1]) <= 3 for b in blk)}
        P("%s block: %d cells within Moore radius 3, of which %d within Euclidean 3 of a depot cell"
          % (name, len(moore), len(eucl)))
    open(os.path.join(BASE, "_dfp_corpus2.txt"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
