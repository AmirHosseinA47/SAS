"""What ENDS a `_move_toward` dither, and what does it cost?

The round brief asserts _move_toward oscillation is "the only one where there
is no mechanism to repair".  That is a claim about what terminates an episode.
This script answers it from the trace rather than from the source: it finds
every maximal run of consecutive tight reversals, then reads what was different
at the step the run ended.

An episode ends because exactly one of these became true:
  BOARD      the local hazard picture around the pair changed (fire spread or
             burnt out, smoke appeared or cleared) - the world repaired it
  TARGET     the unit's target changed (reassigned, victim died/rescued, unassigned)
  ROLE       the unit started exiting, or left the move_toward path entirely
  ARRIVED    the unit reached its target
  DEATH      the unit died
  HORIZON    the run hit step 240 with the episode still going  <-- the only
             case where nothing repaired it
"""
from __future__ import annotations
import json, os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TAGS = (["ed_%d" % s for s in (101, 202, 303)]
        + ["eh_%d" % s for s in (101, 202, 303, 404, 505)]
        + ["sh_%d" % s for s in (101, 202, 303, 404, 505)])


def T(c):
    return tuple(c) if c is not None else None


def haz(scored):
    return {tuple(s["cell"]): (s["on_fire"], s["adjacent_fire"], s["smoke"])
            for s in scored}


def main():
    runs = {}
    for tag in TAGS:
        p = os.path.join(HERE, "_mto_%s.json" % tag)
        if os.path.exists(p) and os.path.getsize(p):
            runs[tag] = json.load(open(p))
    print("runs loaded: %d/%d" % (len(runs), len(TAGS)))

    episodes = []
    unit_stats = {}
    for tag, d in runs.items():
        trace = defaultdict(dict)
        dead = defaultdict(dict)
        for t in d["fftrace"]:
            trace[t["ff"]][t["step"]] = T(t["pos"])
            dead[t["ff"]][t["step"]] = bool(t["dead"])
        ftr = {(t["step"], t["ff"]): t for t in d["fftrace"]}
        lastmove = {}
        for m in d["moves"]:
            lastmove[(m["step"], m["ff"])] = m
        mt = {(c["step"], c["ff"]): c for c in d["mtcalls"]}
        maxstep = max(t["step"] for t in d["fftrace"])

        for ff, seq in trace.items():
            revs = []
            for s in sorted(seq):
                if s - 1 not in seq or s + 1 not in seq:
                    continue
                if dead[ff].get(s - 1) or dead[ff].get(s) or dead[ff].get(s + 1):
                    continue
                a, b, c = seq[s - 1], seq[s], seq[s + 1]
                if a and b and c and a == c and a != b:
                    po = (lastmove.get((s, ff)) or {}).get("path")
                    pb = (lastmove.get((s + 1, ff)) or {}).get("path")
                    if po == "move_toward" and pb == "move_toward":
                        revs.append(s)
            alive_steps = sum(1 for s in seq if not dead[ff].get(s))
            died = any(dead[ff].get(s) for s in seq)
            unit_stats[(tag, ff)] = {
                "revs": len(revs), "alive": alive_steps, "died": died,
            }
            if not revs:
                continue
            # maximal consecutive runs
            i = 0
            while i < len(revs):
                j = i
                while j + 1 < len(revs) and revs[j + 1] == revs[j] + 1:
                    j += 1
                s0, s1 = revs[i], revs[j]
                # The episode occupies positions pos[s0-1] .. pos[s1+1], an
                # alternation A,B,A,B,...  The last reversal at s1 leaves the
                # unit at A = pos[s1+1].  The cycle broke on the NEXT decision,
                # at step brk = s1+2.
                end = s1 + 1
                brk = s1 + 2
                cells = {seq[s] for s in range(s0 - 1, end + 1) if s in seq}
                A = seq.get(end)
                # COMPARE LIKE WITH LIKE.  The unit also stood on A two steps
                # earlier, at step s1.  `_move_toward` is deterministic in
                # (pos, target, board), so comparing the pool scored AT A at
                # step s1 with the pool scored AT A at step brk isolates
                # exactly what changed.  Comparing the pools of the two
                # DIFFERENT cells A and B would be vacuous: on a 4-connected
                # grid two adjacent cells share no neighbours at all.
                why = "HORIZON"
                if brk > maxstep:
                    why = "HORIZON"
                elif dead[ff].get(brk):
                    why = "DEATH"
                else:
                    before = mt.get((s1, ff))
                    after = mt.get((brk, ff))
                    pathbrk = (lastmove.get((brk, ff)) or {}).get("path")
                    if after is None or T(after["pre"]) != A:
                        if pathbrk in ("survival", "assigned_one_step", "revalidate"):
                            why = "SURVIVAL"
                        elif seq.get(end) == T((ftr.get((end, ff)) or {}).get("target")):
                            why = "ARRIVED"
                        elif pathbrk is None:
                            why = "STOOD_STILL"
                        else:
                            why = "ROLE"
                    elif before is None or T(before["pre"]) != A:
                        why = "UNCOMPARABLE"
                    elif T(before["target"]) != T(after["target"]):
                        why = "TARGET"
                    elif bool(before["exiting"]) != bool(after["exiting"]):
                        why = "ROLE"
                    elif haz(before["scored"]) != haz(after["scored"]):
                        why = "BOARD"
                    else:
                        why = "SAME_INPUTS"
                episodes.append({
                    "tag": tag, "ff": ff, "s0": s0, "s1": s1,
                    "len": j - i + 1, "cells": sorted(cells), "why": why,
                })
                i = j + 1

    print()
    print("=" * 78)
    print("EPISODES OF CONSECUTIVE move_toward <-> move_toward REVERSAL")
    print("=" * 78)
    print("  %d episodes, %d reversal-steps total"
          % (len(episodes), sum(e["len"] for e in episodes)))
    print()
    print("  BY LENGTH")
    for k, v in sorted(Counter(e["len"] for e in episodes).items()):
        print("      length %-3d : %4d episode(s)" % (k, v))
    print()
    print("  BY WHAT ENDED IT")
    tot = len(episodes)
    for k, v in Counter(e["why"] for e in episodes).most_common():
        lbl = {
            "BOARD": "the fire/smoke picture around the pair CHANGED",
            "TARGET": "the unit's target changed (reassign / victim gone)",
            "ROLE": "the unit changed role (exiting flipped)",
            "SURVIVAL": "_survival_move took over (hazard closed in)",
            "ARRIVED": "the unit reached its target",
            "DEATH": "the unit died",
            "HORIZON": "NOTHING - still cycling when the run hit step 240",
            "STOOD_STILL": "no move at all that step",
            "SAME_INPUTS": "!! inputs identical yet it broke - would be a probe bug",
            "UNCOMPARABLE": "no comparable earlier pool at the same cell",
        }.get(k, k)
        print("      %4d  (%5.1f%%)  %-8s %s" % (v, 100.0 * v / max(tot, 1), k, lbl))

    print()
    print("  LONGEST EPISODES")
    print("  %-10s %-11s %7s %6s %-9s %-28s" % ("run", "unit", "steps", "len", "ended by", "cells"))
    for e in sorted(episodes, key=lambda z: -z["len"])[:15]:
        print("  %-10s %-11s %3d-%-3d %6d %-9s %s"
              % (e["tag"], e["ff"], e["s0"], e["s1"], e["len"], e["why"],
                 " ".join(str(c) for c in e["cells"])))

    print()
    print("=" * 78)
    print("COST: HOW MUCH OF A UNIT'S LIFE GOES INTO DITHERING")
    print("=" * 78)
    tot_alive = sum(u["alive"] for u in unit_stats.values())
    tot_rev = sum(u["revs"] for u in unit_stats.values())
    print("  firefighter-steps alive across the sample : %d" % tot_alive)
    print("  of which are a move_toward reversal step  : %d  (%.2f%%)"
          % (tot_rev, 100.0 * tot_rev / max(tot_alive, 1)))
    print()
    print("  DID DITHERING UNITS DIE MORE?")
    dith = [u for u in unit_stats.values() if u["revs"] > 0]
    nod = [u for u in unit_stats.values() if u["revs"] == 0]
    for lbl, grp in (("units with >=1 reversal", dith), ("units with none", nod)):
        n = len(grp)
        dd = sum(1 for u in grp if u["died"])
        print("      %-24s n=%-3d died=%-3d (%.0f%%)"
              % (lbl, n, dd, 100.0 * dd / max(n, 1)))

    with open(os.path.join(HERE, "_mto_episodes.json"), "w") as f:
        json.dump(episodes, f, separators=(",", ":"), default=str)
    print()
    print("  episodes written to _mto_episodes.json")


main()
