"""Was the reversal HARMFUL, or was it the right move?

For every hole-attributed tight reversal this replays `_pick_improving_retreat`
OFFLINE on the EXACT candidate set the real call returned (recorded by the
probe), twice:

  (i)  with the candidate set as it actually was          -> what the code chose
  (ii) with the just-vacated cell A REMOVED               -> what an intact
                                                             anti-oscillation
                                                             guard would have
                                                             forced instead

That is not inference from a snapshot: the inputs (candidates, their dist/risk/
ideal/required flags, current_dist, current_risk) are all recorded at the call,
and the function being replayed is pure.  The replay is VALIDATED by checking
it reproduces the cell the simulation actually moved to.
"""
from __future__ import annotations
import collections, json, os, sys

OUT = os.path.dirname(os.path.abspath(__file__))
COMBOS = ([("ed", 101), ("ed", 202), ("ed", 303)]
          + [("eh", s) for s in (101, 202, 303, 404, 505)]
          + [("sh", s) for s in (101, 202, 303, 404, 505)])


def load(tag, pre="_irh2_"):
    p = os.path.join(OUT, "%s%s.json" % (pre, tag))
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    with open(p) as f:
        return json.load(f)


def pick_improving(cands, cur_dist, cur_risk):
    """Verbatim re-implementation of agents.py:906-936 `_pick_improving_retreat`."""
    ideal = [c for c in cands if c["ideal"]]
    if ideal:
        return max(ideal, key=lambda c: (c["dist"], -int(c["risk"])))
    improving = [
        c for c in cands
        if int(c["dist"]) - int(cur_dist) > 0
        or (int(c["risk"]) < cur_risk and int(c["dist"]) >= int(cur_dist))
    ]
    if improving:
        return max(improving, key=lambda c: (int(c["dist"]) - int(cur_dist),
                                             int(c["dist"]), -int(c["risk"])))
    return None


def tier3(cands):
    """agents.py:826-830 / 835-841 - take the least-bad neighbour anyway."""
    if not cands:
        return None
    return max(cands, key=lambda c: (int(c["dist"]), -int(c["risk"])))


def main():
    sys.path.insert(0, OUT)
    from _irh2_analyse import tight_reversals, attribute, reset_sites_paired

    rows, validated, mismatched = [], 0, 0
    for tag, seed in COMBOS:
        t = "%s_%s_none" % (tag, seed)
        d = load(t)
        if d is None:
            continue
        reset_sites_paired(d)
        revs = attribute(d, tight_reversals(d))
        cand = collections.defaultdict(list)
        for c in d["cand"]:
            cand[(c["seed"], c["ff"], c["step"])].append(c)
        mv = collections.defaultdict(list)
        for m in d["moves"]:
            if m["moved"]:
                mv[(m["seed"], m["ff"], m["step"])].append(m)
        for r in revs:
            if not r["class"].startswith("HOLE"):
                continue
            k = (r["seed"], r["ff"], r["t"] + 1)
            cc = cand.get(k)
            mm = mv.get(k)
            if not cc or not mm:
                continue
            c0 = cc[-1]
            m0 = mm[-1]
            cur_dist, cur_risk = c0["cur_dist"], m0["pre_risk"]
            cands = c0["out"]
            got = pick_improving(cands, cur_dist, cur_risk)
            chosen_by = "tier1-2(improving/ideal)"
            if got is None:
                got = tier3(cands)
                chosen_by = "tier3(least-bad anyway)"
            ok = bool(got and tuple(got["cell"]) == tuple(r["A"]))
            validated += ok
            mismatched += (not ok)
            # counterfactual: guard intact -> A excluded
            alt = [c for c in cands if tuple(c["cell"]) != tuple(r["A"])]
            g2 = pick_improving(alt, cur_dist, cur_risk)
            how2 = "tier1-2"
            if g2 is None:
                g2 = tier3(alt)
                how2 = "tier3+STALL LATCH"
            distA = next((c["dist"] for c in cands
                          if tuple(c["cell"]) == tuple(r["A"])), None)
            rows.append({
                "run": t, "ff": r["ff"], "t": r["t"], "A": r["A"], "B": r["B"],
                "cur_dist": cur_dist, "cur_risk": cur_risk,
                "distA": distA, "replay_ok": ok, "chosen_by": chosen_by,
                "n_cand": len(cands),
                "alt_cell": (tuple(g2["cell"]) if g2 else None),
                "alt_dist": (g2["dist"] if g2 else None),
                "alt_risk": (g2["risk"] if g2 else None),
                "alt_how": (how2 if g2 else "NO CANDIDATE AT ALL -> stall"),
            })

    print("=" * 78)
    print("REPLAY VALIDATION: does the offline re-implementation reproduce the")
    print("cell the simulation actually moved to?   %d / %d  (mismatch %d)"
          % (validated, validated + mismatched, mismatched))
    print("=" * 78)
    if mismatched:
        print("!! replay is NOT trustworthy where it mismatches; those rows are")
        print("   marked replay_ok=False below and must not be used as evidence")

    print("\nPer hole-attributed reversal: what the step back WAS, and what an")
    print("intact guard would have forced instead.\n")
    print("  run           ff         t    B->A         cur_d  dist(A)  by"
          "                        guard-intact alternative")
    for r in rows:
        print("  %-13s %-10s %3d  %-8s->%-8s %3d %6s   %-24s %s d=%s r=%s [%s]"
              % (r["run"].replace("_none", ""), r["ff"], r["t"] + 1,
                 r["B"], r["A"], r["cur_dist"], r["distA"], r["chosen_by"],
                 r["alt_cell"], r["alt_dist"], r["alt_risk"], r["alt_how"]))

    print("\nSUMMARY")
    n = len(rows)
    t12 = sum(1 for r in rows if r["chosen_by"].startswith("tier1-2"))
    better = sum(1 for r in rows
                 if r["distA"] is not None and r["alt_dist"] is not None
                 and r["distA"] > r["alt_dist"])
    equal = sum(1 for r in rows
                if r["distA"] is not None and r["alt_dist"] is not None
                and r["distA"] == r["alt_dist"])
    worse = sum(1 for r in rows
                if r["distA"] is not None and r["alt_dist"] is not None
                and r["distA"] < r["alt_dist"])
    latch = sum(1 for r in rows if "STALL" in r["alt_how"])
    print("  hole-attributed reversals                                  %d" % n)
    print("  ...where the step back was the code's IMPROVING/IDEAL pick  %d" % t12)
    print("  ...where the step back was the tier-3 least-bad fallback    %d" % (n - t12))
    print("  A is FURTHER from fire than the best guard-intact option    %d" % better)
    print("  A is the SAME distance as the best guard-intact option      %d" % equal)
    print("  A is NEARER the fire than the best guard-intact option      %d" % worse)
    print("  guard-intact would have dropped the unit to tier-3 + LATCH  %d" % latch)


main()
