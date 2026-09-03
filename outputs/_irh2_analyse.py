"""Analysis for the _reset_idle_retreat_state last_cell hole.

Everything here is computed from DIRECTLY RECORDED EVENTS:
  * LCWRITES - every write to `_idle_retreat_last_cell`, with caller line
  * RESETS   - every `_reset_idle_retreat_state` call, with caller line
  * CAND     - every `_retreat_candidates` call and the set it returned
  * MOVES    - every position change, at the call that made it
  * FFTRACE  - per-step ground truth position

A tight reversal is read off the position ground truth (pos[t-1] == pos[t+1]
!= pos[t]) and then ATTRIBUTED by joining to the write log - never inferred
from a per-step snapshot.
"""
from __future__ import annotations
import collections, glob, json, os, sys

OUT = os.path.dirname(os.path.abspath(__file__))
COMBOS = ([("ed", "east", "default", s) for s in (101, 202, 303)]
          + [("eh", "east", "half", s) for s in (101, 202, 303, 404, 505)]
          + [("sh", "south", "half", s) for s in (101, 202, 303, 404, 505)])
ARMS = ("none", "keeplc")

SITE_NAME = {
    597: "597 advance/standby (idle, ideal standoff)",
    761: "761 _survival_move entry (ideal standoff)",
    832: "832 at_cap, required cell reachable (pre-move)",
    859: "859 post-move: landed on IDEAL standoff",
    863: "863 post-move: landed REQUIRED-safe, at_cap-or-stalled",
    786: "786 leash re-anchor (inline clear, not a reset call)",
    752: "752 the assignment inside _reset_idle_retreat_state",
    854: "854 normal scan: last_cell = cell just before moving",
    994: "994 revalidation: last_cell = cell just before moving",
    397: "397 __init__",
}


def load(tag):
    p = os.path.join(OUT, "_irh2_%s.json" % tag)
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    with open(p) as f:
        return json.load(f)


def key(c):
    return tuple(c) if c else None


# --------------------------------------------------------------- reversals
def tight_reversals(d):
    """pos[t-1] == pos[t+1] != pos[t], on live units, from FFTRACE."""
    by = collections.defaultdict(dict)
    for r in d["fftrace"]:
        by[(r["seed"], r["ff"])][r["step"]] = r
    out = []
    for (seed, ff), steps in by.items():
        ks = sorted(steps)
        for i in range(1, len(ks) - 1):
            a, b, c = ks[i - 1], ks[i], ks[i + 1]
            if b != a + 1 or c != b + 1:
                continue
            ra, rb, rc = steps[a], steps[b], steps[c]
            if ra["dead"] or rb["dead"] or rc["dead"]:
                continue
            pa, pb, pc = key(ra["pos"]), key(rb["pos"]), key(rc["pos"])
            if pa is None or pb is None or pc is None:
                continue
            if pa == pc and pa != pb:
                out.append({"seed": seed, "ff": ff, "t": b,
                            "A": pa, "B": pb,
                            "mfd_A_before": ra["mfd"], "mfd_B": rb["mfd"],
                            "mfd_A_after": rc["mfd"],
                            "cat_t": rb["cat"], "cat_t1": rc["cat"]})
    return out


def move_index(d):
    idx = collections.defaultdict(list)
    for m in d["moves"]:
        if m["moved"]:
            idx[(m["seed"], m["ff"], m["step"])].append(m)
    return idx


def lcwrite_index(d):
    idx = collections.defaultdict(list)
    for w in d["lcwrites"]:
        idx[(w["seed"], w["ff"])].append(w)
    return idx


def reset_sites_paired(d):
    """Pair each in-reset last_cell write with its reset call site.

    `_reset_idle_retreat_state` assigns all four fields unconditionally, so in
    the `none` arm there is exactly ONE in_reset write per reset call, and the
    two lists are appended in execution order: pair them k-th to k-th per
    (seed, ff).  Verified below by checking the counts match.
    """
    wr = collections.defaultdict(list)
    for w in d["lcwrites"]:
        if w["in_reset"]:
            wr[(w["seed"], w["ff"])].append(w)
    rs = collections.defaultdict(list)
    for r in d["resets"]:
        rs[(r["seed"], r["ff"])].append(r)
    ok = True
    for k in set(wr) | set(rs):
        if len(wr.get(k, [])) != len(rs.get(k, [])):
            ok = False
        for w, r in zip(wr.get(k, []), rs.get(k, [])):
            if w["step"] != r["step"]:
                ok = False
            w["reset_site"] = r["site"]
    return ok


def attribute(d, revs):
    """Classify every tight reversal by what permitted the step back."""
    mi = move_index(d)
    li = lcwrite_index(d)
    cands = collections.defaultdict(list)
    for c in d["cand"]:
        cands[(c["seed"], c["ff"], c["step"])].append(c)
    out = []
    for r in revs:
        seed, ff, t = r["seed"], r["ff"], r["t"]
        mt = mi.get((seed, ff, t), [])
        mt1 = mi.get((seed, ff, t + 1), [])
        path_t = mt[-1]["path"] if mt else "?"
        path_t1 = mt1[-1]["path"] if mt1 else "?"
        rec = dict(r, path_t=path_t, path_t1=path_t1)

        # what did the guard hold when the step-back was decided?
        cc = cands.get((seed, ff, t + 1), [])
        rec["cand_calls"] = len(cc)
        rec["lc_arg"] = key(cc[0]["last_cell"]) if cc else None
        rec["fallback_fired"] = bool(len(cc) > 1)
        rec["cur_dist_t1"] = cc[0]["cur_dist"] if cc else None
        rec["cands_t1"] = cc[-1]["out"] if cc else []

        # THE WRITE LOG, read as a sequence.  The guard is "armed with A" when
        # line 854/994 writes last_cell = A during step t (just before the
        # A -> B move).  The hole is: by the time the step-(t+1) scan reads the
        # field, that value is gone.  Which line erased it is recorded, not
        # assumed - it can be the reset itself (agents.py:752, attributed to
        # its calling site) and/or the inline leash re-anchor (agents.py:786),
        # which fires on step t+1 precisely BECAUSE the reset nulled
        # `_idle_retreat_origin`.
        seq = li.get((seed, ff), [])
        arm_ix = None
        for i, w in enumerate(seq):
            if w["step"] == t and key(w["new"]) == r["A"] and w["site"] in (854, 994):
                arm_ix = i
        clears = []
        if arm_ix is not None:
            for w in seq[arm_ix + 1:]:
                if w["step"] > t + 1 or (w["step"] == t + 1 and w["site"] in (854, 994)):
                    break
                if w["new"] is None and not w.get("suppressed"):
                    clears.append(w)
        rec["lc_armed_with_A_at_t"] = arm_ix is not None
        rec["clear_sites"] = [(w.get("reset_site") if w["in_reset"] else w["site"])
                              for w in clears]
        rec["clear_steps"] = [w["step"] for w in clears]

        if (path_t1 in ("survival", "revalidate")
                and rec["lc_arg"] is None
                and arm_ix is not None and clears):
            rec["class"] = "HOLE: guard armed with A at t, erased before the t+1 scan"
        elif path_t1 in ("survival", "revalidate") and rec["lc_arg"] == r["A"]:
            rec["class"] = ("SANCTIONED c4d5a25 fallback (burning cell)"
                            if rec["fallback_fired"] else
                            "GUARD HELD A but unit still returned - INVESTIGATE")
        elif path_t1 in ("survival", "revalidate") and rec["lc_arg"] is None:
            rec["class"] = "survival with last_cell None, NOT cleared at t"
        else:
            rec["class"] = "%s -> %s (no anti-oscillation term)" % (path_t, path_t1)
        out.append(rec)
    return out


def evals(d):
    return {e["seed"]: (e["rescued"], e["dead"], e["firefighter_deaths"])
            for e in d["evals"]}


def first_divergence(a, b):
    ka = [(r["seed"], r["step"], r["ff"], key(r["pos"]), r["dead"]) for r in a["fftrace"]]
    kb = [(r["seed"], r["step"], r["ff"], key(r["pos"]), r["dead"]) for r in b["fftrace"]]
    for i, (x, y) in enumerate(zip(ka, kb)):
        if x != y:
            return x, y
    if len(ka) != len(kb):
        return ("len", len(ka)), ("len", len(kb))
    return None


def main():
    have, missing = [], []
    for tag, wind, roles, seed in COMBOS:
        for arm in ARMS:
            t = "%s_%s_%s" % (tag, seed, arm)
            if load(t) is None:
                missing.append(t)
            else:
                have.append(t)
    print("runs present: %d   MISSING: %d %s"
          % (len(have), len(missing), missing if missing else ""))
    if missing:
        print("!! analysis below covers only the runs present")

    per = {}
    for tag, wind, roles, seed in COMBOS:
        for arm in ARMS:
            t = "%s_%s_%s" % (tag, seed, arm)
            d = load(t)
            if d is None:
                continue
            paired = reset_sites_paired(d)
            revs = tight_reversals(d)
            per[t] = {"d": d, "paired_ok": paired,
                      "revs": attribute(d, revs), "ev": evals(d)}

    # -------------------------------------------------- 1. reset site census
    print("\n" + "=" * 78)
    print("1. RESET / CLEAR SITE CENSUS  (arm none, all runs pooled)")
    print("=" * 78)
    cnt = collections.Counter()
    cleared = collections.Counter()
    idle_cnt = collections.Counter()
    wsites = collections.Counter()
    pair_bad = []
    for t, v in per.items():
        if not t.endswith("_none"):
            continue
        if not v["paired_ok"]:
            pair_bad.append(t)
        for r in v["d"]["resets"]:
            cnt[r["site"]] += 1
            if r["cleared_lc"]:
                cleared[r["site"]] += 1
            if r["idle"]:
                idle_cnt[r["site"]] += 1
        for w in v["d"]["lcwrites"]:
            wsites[w["site"]] += 1
    print("reset<->write pairing verified on all runs:", not pair_bad,
          pair_bad if pair_bad else "")
    print("\n  site   calls  cleared-a-real-last_cell  idle   meaning")
    for s in sorted(cnt):
        print("  %-5s  %5d  %11d              %5d  %s"
              % (s, cnt[s], cleared[s], idle_cnt[s], SITE_NAME.get(s, "?")))
    print("\n  all writes to _idle_retreat_last_cell, by source line:")
    for s in sorted(wsites):
        print("    %-5s %6d   %s" % (s, wsites[s], SITE_NAME.get(s, "?")))

    # ------------------------------------------------------- 2. reversals
    print("\n" + "=" * 78)
    print("2. TIGHT REVERSALS  (pos[t-1] == pos[t+1] != pos[t], live units)")
    print("=" * 78)
    for arm in ARMS:
        tot = collections.Counter()
        n = 0
        for t, v in per.items():
            if not t.endswith("_" + arm):
                continue
            n += len(v["revs"])
            for r in v["revs"]:
                tot[r["class"]] += 1
        print("\n  arm=%-7s total tight reversals: %d" % (arm, n))
        for k, c in tot.most_common():
            print("      %4d  %s" % (c, k))

    print("\n  per-run, arm none:")
    print("    run              tight  HOLE  other")
    for tag, wind, roles, seed in COMBOS:
        t = "%s_%s_none" % (tag, seed)
        if t not in per:
            continue
        rv = per[t]["revs"]
        h = sum(1 for r in rv if r["class"].startswith("HOLE"))
        print("    %-16s %5d %5d %6d" % (t, len(rv), h, len(rv) - h))

    # ---------------------------------------------- 3. the hole in detail
    print("\n" + "=" * 78)
    print("3. HOLE-ATTRIBUTED REVERSALS IN DETAIL  (arm none)")
    print("=" * 78)
    holes = []
    for tag, wind, roles, seed in COMBOS:
        t = "%s_%s_none" % (tag, seed)
        if t not in per:
            continue
        for r in per[t]["revs"]:
            if r["class"].startswith("HOLE"):
                r["run"] = t
                holes.append(r)
    print("total: %d" % len(holes))
    bysite = collections.Counter()
    for r in holes:
        for s in r["clear_sites"]:
            bysite[s] += 1
    print("clearing site of the reset that opened it:")
    for s, c in bysite.most_common():
        print("   %4d  site %s  %s" % (c, s, SITE_NAME.get(s, "?")))
    print("\n  run              ff          t    A         B        "
          "mfd A(t-1)/B(t)/A(t+1)  cur_dist(t+1)  paths")
    for r in holes:
        print("  %-16s %-10s %4d %-9s %-9s   %2s / %2s / %2s"
              "              %2s          %s->%s"
              % (r["run"], r["ff"], r["t"], r["A"], r["B"],
                 r["mfd_A_before"], r["mfd_B"], r["mfd_A_after"],
                 r["cur_dist_t1"], r["path_t"], r["path_t1"]))

    # deaths of the units involved
    print("\n  did the units involved in a hole reversal come to harm?")
    seen = set()
    for r in holes:
        k = (r["run"], r["ff"])
        if k in seen:
            continue
        seen.add(k)
        d = per[r["run"]]["d"]
        dth = [x for x in d["deaths"] if x["ff"] == r["ff"]]
        tr = [x for x in d["fftrace"] if x["ff"] == r["ff"] and not x["dead"]]
        last = tr[-1] if tr else None
        print("    %-16s %-10s  deaths=%s  last-live step=%s mfd=%s status=%s"
              % (r["run"], r["ff"],
                 ([(x["step"], x["pos"]) for x in dth] or "none"),
                 (last["step"] if last else "?"),
                 (last["mfd"] if last else "?"),
                 (last["status"] if last else "?")))

    # ---------------------------------------------------- 4. A/B none vs keeplc
    print("\n" + "=" * 78)
    print("4. A/B  arm none vs arm keeplc   (rescued / victims dead / ff deaths)")
    print("=" * 78)
    tn = [0, 0, 0]
    tk = [0, 0, 0]
    nrun = 0
    print("  run           none          keeplc        trace")
    for tag, wind, roles, seed in COMBOS:
        a, b = "%s_%s_none" % (tag, seed), "%s_%s_keeplc" % (tag, seed)
        if a not in per or b not in per:
            print("  %-13s %s" % ("%s_%s" % (tag, seed), "INCOMPLETE"))
            continue
        ea, eb = per[a]["ev"][seed], per[b]["ev"][seed]
        fd = first_divergence(per[a]["d"], per[b]["d"])
        for i in range(3):
            tn[i] += ea[i]
            tk[i] += eb[i]
        nrun += 1
        print("  %-13s r%d/d%d/ff%d    r%d/d%d/ff%d    %s"
              % ("%s_%s" % (tag, seed), ea[0], ea[1], ea[2],
                 eb[0], eb[1], eb[2],
                 "same" if fd is None else "DIFFERS from %s" % (fd[0],)))
    print("  %-13s r%d/d%d/ff%d    r%d/d%d/ff%d    (%d runs)"
          % ("TOTAL", tn[0], tn[1], tn[2], tk[0], tk[1], tk[2], nrun))

    print("\n  tight reversals, none vs keeplc, per run:")
    sn = sk = shn = shk = 0
    for tag, wind, roles, seed in COMBOS:
        a, b = "%s_%s_none" % (tag, seed), "%s_%s_keeplc" % (tag, seed)
        if a not in per or b not in per:
            continue
        ra, rb = per[a]["revs"], per[b]["revs"]
        ha = sum(1 for r in ra if r["class"].startswith("HOLE"))
        hb = sum(1 for r in rb if r["class"].startswith("HOLE"))
        sn += len(ra); sk += len(rb); shn += ha; shk += hb
        print("    %-13s tight %2d -> %2d    hole %2d -> %2d"
              % ("%s_%s" % (tag, seed), len(ra), len(rb), ha, hb))
    print("    %-13s tight %2d -> %2d    hole %2d -> %2d"
          % ("TOTAL", sn, sk, shn, shk))


if __name__ == "__main__":
    main()
