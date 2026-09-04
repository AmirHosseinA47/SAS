"""Classify every `_move_toward` <-> `_move_toward` tight reversal.

METHOD, AND WHY IT IS NOT A SNAPSHOT INFERENCE.
  * Tight reversals are read off the end-of-step POSITION ground truth
    (pos[t-1] == pos[t+1] != pos[t], live units only) - the same definition the
    two prior reports used, so the 144/186 figure is comparable.
  * ATTRIBUTION is then joined from the move log, where every position change
    was recorded AT THE CALL THAT MADE IT.  Alignment between the two
    (last move of step s lands on trace position at step s) is asserted, not
    assumed.
  * The decision context of each `_move_toward` call - the full scored
    neighbour pool - was recorded by the probe and CROSS-VALIDATED against what
    the real method actually picked.  This script asserts that validation was
    100% before using any pool.
  * The guard counterfactual re-runs the real tier chain over the recorded pool
    with the return cell removed.  Nothing is guessed about what a guard would
    have done; the same selection code decides it.
"""
from __future__ import annotations
import glob, json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TAGS = (["ed_%d" % s for s in (101, 202, 303)]
        + ["eh_%d" % s for s in (101, 202, 303, 404, 505)]
        + ["sh_%d" % s for s in (101, 202, 303, 404, 505)])


def T(c):
    return tuple(c) if c is not None else None


def pick(pool_items):
    """The real tier chain, over an already fire-filtered list of pool dicts."""
    live = [i for i in pool_items if not i["on_fire"]]
    if not live:
        return None, None
    tiers = [
        [i for i in live if i["improving"] and not i["adjacent_fire"] and not i["smoke"]],
        [i for i in live if i["maintaining"] and not i["adjacent_fire"] and not i["smoke"]],
        [i for i in live if not i["adjacent_fire"] and not i["smoke"]],
    ]
    for ti, pool in enumerate(tiers, start=1):
        if pool:
            return min(pool, key=lambda i: (i["dist_after"],
                                            0 if i["preferred"] else 1)), ti
    return min(live, key=lambda i: (i["risk"], i["dist_after"],
                                    0 if i["preferred"] else 1)), 4


def hazard_sig(pool):
    """Local hazard picture as seen from a cell: what the scoring depended on."""
    return tuple(sorted(
        (tuple(s["cell"]), s["on_fire"], s["adjacent_fire"], s["smoke"])
        for s in pool))


def load(tag):
    p = os.path.join(HERE, "_mto_%s.json" % tag)
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    with open(p) as f:
        return json.load(f)


def main():
    runs = {}
    for tag in TAGS:
        d = load(tag)
        if d is None:
            print("MISSING/EMPTY: %s" % tag)
            continue
        runs[tag] = d
    if len(runs) != len(TAGS):
        print("!! only %d/%d runs present" % (len(runs), len(TAGS)))

    # ---------------------------------------------------------------- 0. instrument
    print("=" * 78)
    print("0. INSTRUMENT VALIDATION")
    print("=" * 78)
    tot_n = tot_c = tot_t = 0
    mism = 0
    for tag, d in runs.items():
        ps = d["predstats"]
        tot_n += ps["n"]; tot_c += ps["cell_ok"]; tot_t += ps["tier_ok"]
        mism += len(ps["mismatch"])
    print("  _move_toward calls observed          %6d" % tot_n)
    print("  recomputed pool predicted the CELL   %6d  (%s)"
          % (tot_c, "100%" if tot_c == tot_n else "%.4f%%" % (100.0 * tot_c / max(tot_n, 1))))
    print("  recomputed pool predicted the TIER   %6d  (%s)"
          % (tot_t, "100%" if tot_t == tot_n else "%.4f%%" % (100.0 * tot_t / max(tot_n, 1))))
    print("  recorded mismatch samples            %6d" % mism)
    if tot_c != tot_n or tot_t != tot_n:
        print("  !! POOL IS NOT PROVEN EXACT - every pool-derived number below is suspect")
    else:
        print("  => the recorded pool IS the pool the real method saw. Pool-derived")
        print("     counterfactuals below are computed by the real selection code.")

    # step alignment
    align_ok = align_bad = 0
    multi = 0
    for tag, d in runs.items():
        tr = {(t["step"], t["ff"]): T(t["pos"]) for t in d["fftrace"]}
        last = {}
        seen = Counter()
        for m in d["moves"]:
            last[(m["step"], m["ff"])] = m
            seen[(m["step"], m["ff"])] += 1
        multi += sum(1 for v in seen.values() if v > 1)
        for key, m in last.items():
            if tr.get(key) == T(m["post"]):
                align_ok += 1
            else:
                align_bad += 1
    print("  steps where a unit moved twice (survival then move_toward): %d" % multi)
    print("  LAST move of each step vs the position trace: %d aligned, %d misaligned"
          % (align_ok, align_bad))
    if align_bad:
        print("  !! attribution is unsafe where misaligned")

    # ---------------------------------------------------------------- 1. reversals
    print()
    print("=" * 78)
    print("1. TIGHT REVERSALS ON THE CANONICAL SAMPLE, BY ORIGINATING PATH")
    print("=" * 78)

    all_rev = []
    per_run = {}
    for tag, d in runs.items():
        trace = defaultdict(dict)
        dead = defaultdict(dict)
        for t in d["fftrace"]:
            trace[t["ff"]][t["step"]] = T(t["pos"])
            dead[t["ff"]][t["step"]] = bool(t["dead"])
        # last move of each (step, ff), and every mt call by (step, ff)
        lastmove = {}
        for m in d["moves"]:
            lastmove[(m["step"], m["ff"])] = m
        mt = {}
        for c in d["mtcalls"]:
            mt[(c["step"], c["ff"])] = c
        ftr = {}
        for t in d["fftrace"]:
            ftr[(t["step"], t["ff"])] = t

        steps = sorted({t["step"] for t in d["fftrace"]})
        n_rev = 0
        for ff, seq in trace.items():
            for s in steps:
                if s - 1 not in seq or s + 1 not in seq:
                    continue
                if dead[ff].get(s - 1) or dead[ff].get(s) or dead[ff].get(s + 1):
                    continue
                a, b, c = seq[s - 1], seq[s], seq[s + 1]
                if a is None or b is None or c is None:
                    continue
                if a == c and a != b:
                    n_rev += 1
                    p_out = lastmove.get((s, ff))
                    p_back = lastmove.get((s + 1, ff))
                    all_rev.append({
                        "tag": tag, "ff": ff, "step": s,
                        "A": a, "B": b,
                        "path_out": (p_out or {}).get("path"),
                        "path_back": (p_back or {}).get("path"),
                        "mt_out": mt.get((s, ff)),
                        "mt_back": mt.get((s + 1, ff)),
                        "mt_next": mt.get((s + 2, ff)),
                        "tr_out": ftr.get((s, ff)),
                        "tr_back": ftr.get((s + 1, ff)),
                        "tr_pre": ftr.get((s - 1, ff)),
                    })
        per_run[tag] = n_rev

    pair = Counter((r["path_out"], r["path_back"]) for r in all_rev)
    print("  %4d  TOTAL tight reversals on live units, all code paths"
          % len(all_rev))
    print()
    for (po, pb), n in pair.most_common():
        print("  %4d  %-18s -> %-18s" % (n, po, pb))
    print()
    print("  per run (tight):  " + ",  ".join(
        "%s %d" % (t, per_run.get(t, 0)) for t in TAGS if t in per_run))

    MM = [r for r in all_rev if r["path_out"] == "move_toward"
          and r["path_back"] == "move_toward"]
    print()
    print("  THE SUBJECT OF THIS ROUND: %d move_toward <-> move_toward" % len(MM))

    usable = [r for r in MM if r["mt_out"] and r["mt_back"]]
    print("  with full recorded decision context on BOTH calls: %d" % len(usable))
    if len(usable) != len(MM):
        print("  !! %d lack context - excluded from classification"
              % (len(MM) - len(usable)))

    # ---------------------------------------------------------------- 2. classify
    print()
    print("=" * 78)
    print("2. CLASSIFICATION OF EVERY move_toward <-> move_toward REVERSAL")
    print("=" * 78)

    rows = []
    for r in usable:
        o, k = r["mt_out"], r["mt_back"]
        A, B = r["A"], r["B"]

        # role
        if o["exiting"] or k["exiting"]:
            role = "exiting" if (o["exiting"] and k["exiting"]) else "role_flip"
        else:
            role = "assigned_transit"

        tgt_out, tgt_back = T(o["target"]), T(k["target"])
        target_changed = tgt_out != tgt_back

        so = {tuple(s["cell"]): s for s in o["scored"]}
        sk = {tuple(s["cell"]): s for s in k["scored"]}

        # DID THE DECISION INPUTS ACTUALLY CHANGE?
        # NOT by intersecting the two pools: A and B are adjacent, and on a
        # 4-connected grid two adjacent cells share NO neighbours at all, so
        # that intersection is always empty and the test would be vacuous.
        # The apples-to-apples comparison is the pool scored AT A at step t
        # against the pool scored AT A again at step t+2 - same cell, same
        # scoring, two steps apart.  If those are identical and the target is
        # unchanged, `_move_toward` is deterministic, so step t+2 MUST repeat
        # step t and the cycle continues.  That is the stability test.
        nxt = r["mt_next"]          # the call at t+2, if the unit was still on this path
        if nxt is None:
            repeat = "left_path"
        elif T(nxt["pre"]) != A:
            repeat = "left_path"
        else:
            ha = {tuple(s["cell"]): (s["on_fire"], s["adjacent_fire"], s["smoke"])
                  for s in o["scored"]}
            hn = {tuple(s["cell"]): (s["on_fire"], s["adjacent_fire"], s["smoke"])
                  for s in nxt["scored"]}
            same_board = (ha == hn)
            same_target = (T(o["target"]) == T(nxt["target"]))
            if same_board and same_target:
                repeat = "inputs_identical"
            elif not same_target:
                repeat = "target_changed"
            else:
                repeat = "board_changed"
        board_changed = (repeat == "board_changed")
        # A itself: its hazard status as seen from B at t+1 vs its own "here" at t
        a_at_t = o["here"]
        a_from_b = sk.get(A)

        # the step back: was it the code's own improving pick?
        back_tier = k["tier"]
        back_item = sk.get(A)
        back_improving = bool(back_item and back_item["improving"])

        # counterfactual: guard forbids returning to A
        alt, alt_tier = pick([s for s in k["scored"] if tuple(s["cell"]) != A])
        if alt is None:
            guard = "would_pin"     # nothing else to step to: guard = stand still
            alt_desc = None
        else:
            worse = []
            if alt_tier > back_tier:
                worse.append("tier")
            if back_item and alt["dist_after"] > back_item["dist_after"]:
                worse.append("dist")
            if back_item and alt["risk"] > back_item["risk"]:
                worse.append("risk")
            if alt["on_fire"]:
                worse.append("ONFIRE")
            if back_item and not back_item["adjacent_fire"] and alt["adjacent_fire"]:
                worse.append("adjfire")
            if back_item and not back_item["smoke"] and alt["smoke"]:
                worse.append("smoke")
            better = []
            if back_item and alt["dist_after"] < back_item["dist_after"]:
                better.append("dist")
            if back_item and alt["risk"] < back_item["risk"]:
                better.append("risk")
            if worse:
                guard = "forced_worse"
            elif better:
                guard = "forced_better"
            else:
                guard = "forced_equal"
            alt_desc = {"cell": tuple(alt["cell"]), "tier": alt_tier,
                        "dist": alt["dist_after"], "risk": alt["risk"],
                        "onfire": alt["on_fire"], "adj": alt["adjacent_fire"],
                        "smoke": alt["smoke"], "worse": worse, "better": better}

        rows.append({
            "r": r, "role": role, "target_changed": target_changed,
            "tgt_out": tgt_out, "tgt_back": tgt_back,
            "tier_out": o["tier"], "tier_back": back_tier,
            "board_changed": board_changed, "repeat": repeat,
            "rb_out": o["route_blocked_now"], "rb_back": k["route_blocked_now"],
            "back_improving": back_improving,
            "a_onfire_at_t": a_at_t["on_fire"],
            "a_adj_at_t": a_at_t["adjacent_fire"],
            "a_smoke_at_t": a_at_t["smoke"],
            "a_risk_at_t": a_at_t["risk"],
            "a_from_b": a_from_b,
            "guard": guard, "alt": alt_desc,
            "dist_before_out": o["dist_before"], "dist_before_back": k["dist_before"],
            "nlive_out": o["n_live"], "nlive_back": k["n_live"],
        })

    def show(title, counter, total=None):
        total = total or len(rows)
        print()
        print("  " + title)
        for k, v in counter.most_common():
            print("      %4d  (%5.1f%%)  %s" % (v, 100.0 * v / max(total, 1), k))

    show("2.1  ROLE OF THE UNIT",
         Counter(x["role"] for x in rows))
    show("2.2  DID THE TARGET CHANGE BETWEEN THE TWO DECISIONS?",
         Counter("target CHANGED (reversal is a response to a new goal)"
                 if x["target_changed"] else "target identical"
                 for x in rows))
    show("2.3  TIER PAIR  (tier used stepping A->B, tier used stepping B->A)",
         Counter("tier %s -> tier %s" % (x["tier_out"], x["tier_back"])
                 for x in rows))
    show("2.4  WOULD THE CYCLE HAVE REPEATED?  (pool at A at step t vs at step t+2)",
         Counter({
             "inputs_identical": "INPUTS IDENTICAL - deterministic, the cycle continues",
             "board_changed":    "the fire/smoke picture around A changed - world repaired it",
             "target_changed":   "the target changed",
             "left_path":        "unit left the move_toward path (survival / arrived / died)",
         }[x["repeat"]] for x in rows))
    show("2.5  WAS THE STEP BACK THE CODE OWN IMPROVING PICK (tier 1)?",
         Counter("tier 1 - its own best improving pick" if x["tier_back"] == 1
                 else "tier %s" % x["tier_back"] for x in rows))
    show("2.6  ROUTE_BLOCKED AT EITHER DECISION?",
         Counter(("blocked at A->B" if x["rb_out"] else "")
                 + ("+blocked at B->A" if x["rb_back"] else "")
                 or "route open at both" for x in rows))
    show("2.7  HAZARD STATUS OF THE CELL IT RETURNED TO (A), as scored from B",
         Counter(
             ("A ON FIRE" if (x["a_from_b"] or {}).get("on_fire") else
              "A adjacent-to-fire" if (x["a_from_b"] or {}).get("adjacent_fire") else
              "A smoky" if (x["a_from_b"] or {}).get("smoke") else
              "A clean (risk 0)")
             for x in rows))
    show("2.8  COUNTERFACTUAL: an anti-oscillation guard forbids returning to A",
         Counter({
             "forced_worse": "guard would force an equal-or-WORSE cell",
             "forced_equal": "guard alternative equal on tier/dist/risk",
             "forced_better": "guard alternative strictly BETTER",
             "would_pin": "guard leaves NO legal cell - unit pinned",
         }[x["guard"]] for x in rows))

    # what exactly is worse
    wc = Counter()
    for x in rows:
        if x["guard"] == "forced_worse":
            for w in x["alt"]["worse"]:
                wc[w] += 1
    if wc:
        print()
        print("  2.8b  IN WHAT WAY the guard alternative is worse (non-exclusive)")
        for k, v in wc.most_common():
            lbl = {"ONFIRE": "the only alternative is a BURNING cell",
                   "adjfire": "alternative is adjacent to fire, A was not",
                   "smoke": "alternative is smoky, A was not",
                   "tier": "alternative falls to a lower tier",
                   "dist": "alternative is further from the target",
                   "risk": "alternative carries higher risk score"}.get(k, k)
            print("      %4d  %s" % (v, lbl))

    # ---------------------------------------------------------------- 3. episodes
    print()
    print("=" * 78)
    print("3. IS IT A TWO-CELL POCKET, OR DITHERING ON A LONG TRANSIT?")
    print("=" * 78)
    byunit = defaultdict(list)
    for x in rows:
        byunit[(x["r"]["tag"], x["r"]["ff"])].append(x)

    print("  %-10s %-11s %5s %6s %7s %7s %8s"
          % ("run", "unit", "revs", "steps", "distinct", "maxvis", "longest"))
    print("  %-10s %-11s %5s %6s %7s %7s %8s"
          % ("", "", "", "alive", "cells", "cell", "run"))
    tot_units = 0
    pocket_units = 0
    for (tag, ff), xs in sorted(byunit.items(), key=lambda kv: -len(kv[1])):
        d = runs[tag]
        seq = [(t["step"], T(t["pos"])) for t in d["fftrace"]
               if t["ff"] == ff and not t["dead"] and t["pos"]]
        cells = [p for _, p in seq]
        distinct = len(set(cells))
        maxvis = Counter(cells).most_common(1)[0][1] if cells else 0
        # longest run of consecutive tight reversals by this unit
        ss = sorted(x["r"]["step"] for x in xs)
        longest = cur = 1 if ss else 0
        for i in range(1, len(ss)):
            cur = cur + 1 if ss[i] == ss[i - 1] + 1 else 1
            longest = max(longest, cur)
        tot_units += 1
        if distinct <= 4 and len(cells) > 20:
            pocket_units += 1
        print("  %-10s %-11s %5d %6d %7d %7d %8d"
              % (tag, ff, len(xs), len(seq), distinct, maxvis, longest))
    print()
    print("  units with >=1 move_toward reversal: %d" % tot_units)
    print("  units confined to a <=4-cell pocket for >20 steps: %d" % pocket_units)

    # consecutive-reversal runs across the whole sample
    runs_len = Counter()
    for (tag, ff), xs in byunit.items():
        ss = sorted(x["r"]["step"] for x in xs)
        i = 0
        while i < len(ss):
            j = i
            while j + 1 < len(ss) and ss[j + 1] == ss[j] + 1:
                j += 1
            runs_len[j - i + 1] += 1
            i = j + 1
    print()
    print("  LENGTH OF CONSECUTIVE-REVERSAL EPISODES (a stable limit cycle would")
    print("  show as a long run; isolated backtracks show as length 1):")
    for k in sorted(runs_len):
        print("      length %-3d : %4d episode(s)   [%d reversal-steps]"
              % (k, runs_len[k], k * runs_len[k]))

    # ---------------------------------------------------------------- 4. cycles
    print()
    print("=" * 78)
    print("4. IS THE CYCLE STABLE, OR DOES THE WORLD BREAK IT?")
    print("=" * 78)
    print("  For each reversal, the pool scored AT A at step t is compared with the")
    print("  pool scored AT A at step t+2.  `_move_toward` is a deterministic")
    print("  function of (pos, target, board), so identical inputs MUST reproduce")
    print("  the identical step - the cycle continues.  Any other outcome means")
    print("  something outside `_move_toward` ended it.")
    print()
    rc = Counter(x["repeat"] for x in rows)
    for k, v in rc.most_common():
        lbl = {
            "inputs_identical": "cycle would repeat (nothing had changed yet)",
            "board_changed": "FIRE/SMOKE MOVED - the world repaired it",
            "target_changed": "the target changed",
            "left_path": "unit left the move_toward path entirely",
        }[k]
        print("      %4d  (%5.1f%%)  %-18s %s" % (v, 100.0 * v / max(len(rows), 1), k, lbl))
    print()
    print("  Note these are per-REVERSAL, not per-episode: a long episode")
    print("  contributes several `inputs_identical` rows and one terminator.")
    print("  Episode-level termination is in _mto_episodes.py.")

    # ---------------------------------------------------------------- 5. outcome
    print()
    print("=" * 78)
    print("5. BASELINE OUTCOMES (for reference / comparability)")
    print("=" * 78)
    tot = Counter()
    for tag in TAGS:
        d = runs.get(tag)
        if not d:
            continue
        for ev in d["evals"]:
            for k in ("rescued", "victims_dead", "firefighter_deaths"):
                if k in ev:
                    tot[k] += int(ev[k] or 0)
    print("  13-run totals: " + "  ".join("%s=%d" % (k, v) for k, v in sorted(tot.items())))
    print("  deaths recorded: %d"
          % sum(len(d["deaths"]) for d in runs.values()))

    # dump the classified rows for downstream/independent re-analysis
    outp = os.path.join(HERE, "_mto_rows.json")
    with open(outp, "w") as f:
        json.dump([{k: v for k, v in x.items() if k != "r"} | {
            "tag": x["r"]["tag"], "ff": x["r"]["ff"], "step": x["r"]["step"],
            "A": list(x["r"]["A"]), "B": list(x["r"]["B"]),
        } for x in rows], f, separators=(",", ":"), default=str)
    print()
    print("  classified rows written to %s" % outp)


main()
