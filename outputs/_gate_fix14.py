"""fix14 gate - x-clamp reachability fix + target-hold stability, one change.

Four sides per run, all on disk:

  BASE    _tf_<tag>_BASE.json     pre-x-clamp                (commit 65f5b31)
  XCLAMP  _tf_<tag>_XCLAMP.json   Part 2 only, OLD tree      (commit 65f5b31)
  P2ONLY  _tf_<tag>_P2ONLY.json   Part 2 only, CURRENT tree  (this round)
  FIX14   _tf_<tag>_FIX14.json    Part 2 + Part 3            (this round)

XCLAMP is not a clean A/B for Part 3: it was measured on 65f5b31, which
predates both the finalizer hazard re-validation fix and the position rename
that HEAD carries, so XCLAMP -> FIX14 mixes three changes. P2ONLY re-runs the
same four probes with ONLY Part 2 applied to the current tree, so P2ONLY ->
FIX14 isolates the hold. Both are reported; P2ONLY is the one to read.

The control comparison (condition 4) is taken against P2ONLY for the same
reason.

Gate conditions were declared in advance and are evaluated verbatim:

  1. Mean target hold duration rises materially from the churn baseline
     (~3.3-3.4 steps) toward the pre-clamp-fix level (~11-15), WITHOUT falling
     back to the churn-free-but-wrong-reachability regime (12-15 distinct
     targets total across 240 steps).
  2. x-range still extends past 26 under north and south wind.
  3. Argmax-survival - here "committed target matches what the scorer would
     have chosen at the moment of commit" - stays materially above the
     pre-Part-2 baseline of 2.4-2.9%.
  4. A/west 505 control unchanged on every metric.
  5. D/north 101 and D/south 101 stay at zero never_detected.
  6. The A/north 101 seed-trade (victim_0 recovered, victim_4 newly missed) is
     RE-CHECKED - reported, not assumed either way.

ON CONDITION 3 AND THE HOLD. Raw argmax-survival (does the finalizer's output
equal the scorer's argmax on THIS step) is not the right readout once a hold
exists: holding means deliberately ignoring a new argmax, so the raw rate must
fall by construction. The gate's own parenthetical names the correct metric,
and both are reported: `argmax raw` for continuity with the x-clamp round, and
`argmax at commit` - measured only on the steps where a hold is armed - for
the condition itself.
"""
from __future__ import annotations

import itertools
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS = ["D_north_101", "D_south_101", "A_north_101", "A_west_505"]
TREAT = ["D_north_101", "D_south_101", "A_north_101"]
CONTROL = "A_west_505"
SIDES = [("_BASE", "BASE"), ("_XCLAMP", "XCLAMP"),
         ("_P2ONLY", "P2ONLY"), ("_FIX14", "FIX14")]
CLAMP_X = (8, 41)
PRE_PART2_ARGMAX = (2.4, 2.9)  # D/north, A/north pre-x-clamp
CHURN_MEAN_HOLD = (3.3, 3.4)   # x-clamp-only churn baseline
PRE_CLAMP_HOLD = (11.0, 15.0)  # pre-x-clamp level


def cell(v):
    return (int(v[0]), int(v[1])) if v else None


def load(tag, sfx):
    p = os.path.join(ROOT, "_tf_%s%s.json" % (tag, sfx))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def finalized(rec):
    out = None
    for name, c in rec.get("gen_inner") or []:
        if name == "finalize" and c:
            out = cell(c)
    return out


def pos_at(rec):
    for a in rec.get("advance") or []:
        if a and a[0]:
            return cell(a[0])
    return cell(rec.get("searcher_pos"))


def positions(sr):
    return [cell(a[1]) for r in sr for a in (r.get("advance") or []) if a and a[1]]


def segments(sr):
    rows = [(finalized(r), pos_at(r)) for r in sr]
    rows = [(t, p) for t, p in rows if t is not None and p is not None]
    segs = []
    for tgt, grp in itertools.groupby(rows, key=lambda z: z[0]):
        grp = list(grp)
        segs.append((tgt, len(grp)))
    return segs


def metrics(d) -> dict:
    sr = d["step_records"]
    segs = segments(sr)
    lens = [n for _, n in segs] or [0]
    xs = [p[0] for p in positions(sr) if p]

    fins = [(finalized(r), cell(r.get("prefinal_target"))) for r in sr]
    fins = [(f, pre) for f, pre in fins if f]
    scored = [(f, pre) for f, pre in fins if pre is not None]
    survived = [1 for f, pre in scored if f == pre]

    # steps on which a hold was armed: commit_issued ticked up
    at_commit_hit = at_commit_n = 0
    prev_issued = None
    for r in sr:
        ws = r.get("ws_entry") or {}
        issued = ws.get("commit_issued")
        if issued is None:
            continue
        issued = int(issued)
        if prev_issued is not None and issued > prev_issued:
            f, pre = finalized(r), cell(r.get("prefinal_target"))
            if f is not None and pre is not None:
                at_commit_n += 1
                at_commit_hit += 1 if f == pre else 0
        prev_issued = issued

    breaks, issued_total = {}, 0
    for r in reversed(sr):
        ws = r.get("ws_entry") or {}
        if ws.get("commit_breaks") is not None or ws.get("commit_issued") is not None:
            breaks = dict(ws.get("commit_breaks") or {})
            issued_total = int(ws.get("commit_issued", 0) or 0)
            break

    return dict(
        n_segments=len(segs),
        distinct_final=len(set(t for t, _ in segs)),
        distinct_prefinal=len(set(
            cell(r.get("prefinal_target")) for r in sr if r.get("prefinal_target")
        )),
        mean_hold=sum(lens) / float(len(lens)),
        median_hold=sorted(lens)[len(lens) // 2],
        max_hold=max(lens),
        clamp_hits=sum(1 for f, _ in fins if f[0] in CLAMP_X),
        clamp_frac=(100.0 * sum(1 for f, _ in fins if f[0] in CLAMP_X) / len(fins))
        if fins else 0.0,
        argmax_frac=(100.0 * len(survived) / len(scored)) if scored else 0.0,
        argmax_scored=len(scored),
        at_commit_frac=(100.0 * at_commit_hit / at_commit_n) if at_commit_n else None,
        at_commit_n=at_commit_n,
        x_lo=min(xs) if xs else 0,
        x_hi=max(xs) if xs else 0,
        nd=sorted(d.get("nd") or []),
        breaks=breaks,
        issued=issued_total,
    )


def control_identical(a_d, b_d) -> tuple[bool, list]:
    """Behavioural equality, ignoring instrumentation-only keys."""
    a, b = a_d["step_records"], b_d["step_records"]
    diffs = []
    if len(a) != len(b):
        return False, ["step count %d vs %d" % (len(a), len(b))]
    for i, (ra, rb) in enumerate(zip(a, b)):
        if finalized(ra) != finalized(rb):
            diffs.append("step %d finalize %s vs %s" % (i, finalized(ra), finalized(rb)))
        elif cell(ra.get("searcher_pos")) != cell(rb.get("searcher_pos")):
            diffs.append("step %d searcher_pos %s vs %s"
                         % (i, cell(ra.get("searcher_pos")), cell(rb.get("searcher_pos"))))
        if len(diffs) >= 5:
            break
    if sorted(a_d.get("nd") or []) != sorted(b_d.get("nd") or []):
        diffs.append("nd %s vs %s" % (a_d.get("nd"), b_d.get("nd")))
    return (not diffs), diffs


def main() -> int:
    lines: list = []

    def log(m: str = "") -> None:
        print(m, flush=True)
        lines.append(m)

    M: dict = {}
    for tag in RUNS:
        M[tag] = {}
        for sfx, side in SIDES:
            d = load(tag, sfx)
            if d is None:
                log("%-13s %-7s MISSING _tf_%s%s.json" % (tag, side, tag, sfx))
                continue
            M[tag][side] = (metrics(d), d)

    log("=" * 78)
    log("fix14 GATE - BASE (pre-x-clamp) / XCLAMP (Part 2) / FIX14 (Part 2+3)")
    log("=" * 78)
    log("")
    hdr = ("%-13s %-7s %5s %6s %6s %8s %7s %7s %7s %6s %6s %9s %11s"
           % ("run", "side", "segs", "dstF", "dstP", "meanhold", "medhold",
              "maxhold", "clampX", "x_lo", "x_hi", "argmax raw", "argmax@commit"))
    log(hdr)
    log("-" * len(hdr))
    for tag in RUNS:
        for _, side in SIDES:
            if side not in M[tag]:
                continue
            m = M[tag][side][0]
            ac = ("-" if m["at_commit_frac"] is None
                  else "%.1f (n=%d)" % (m["at_commit_frac"], m["at_commit_n"]))
            log("%-13s %-7s %5d %6d %6d %8.1f %7d %7d %7d %6d %6d %9.1f %11s"
                % (tag, side, m["n_segments"], m["distinct_final"],
                   m["distinct_prefinal"], m["mean_hold"], m["median_hold"],
                   m["max_hold"], m["clamp_hits"], m["x_lo"], m["x_hi"],
                   m["argmax_frac"], ac))
        nds = " | ".join(
            "%s %s" % (side, ",".join(M[tag][side][0]["nd"]) or "-")
            for _, side in SIDES if side in M[tag]
        )
        log("%-13s never_detected: %s" % ("", nds))
        log("")

    log("=" * 78)
    log("HOLD RELEASE CONDITIONS - fix14 only, counted per run")
    log("=" * 78)
    log("")
    log("%-13s %8s %9s %9s %9s %9s %9s"
        % ("run", "issued", "arrival", "unsafe", "stalled", "timeout", "released"))
    log("-" * 70)
    for tag in RUNS:
        if "FIX14" not in M[tag]:
            continue
        b = M[tag]["FIX14"][0]["breaks"]
        tot = sum(int(v) for v in b.values())
        log("%-13s %8d %9d %9d %9d %9d %9d"
            % (tag, M[tag]["FIX14"][0]["issued"],
               int(b.get("arrival", 0)), int(b.get("unsafe", 0)),
               int(b.get("stalled", 0)), int(b.get("timeout", 0)), tot))
    log("")
    log("%-13s %8s %9s %9s %9s %9s" % ("run", "", "arrival%", "unsafe%", "stalled%", "timeout%"))
    log("-" * 62)
    for tag in RUNS:
        if "FIX14" not in M[tag]:
            continue
        b = M[tag]["FIX14"][0]["breaks"]
        tot = sum(int(v) for v in b.values()) or 1
        log("%-13s %8s %9.1f %9.1f %9.1f %9.1f"
            % (tag, "", 100.0 * int(b.get("arrival", 0)) / tot,
               100.0 * int(b.get("unsafe", 0)) / tot,
               100.0 * int(b.get("stalled", 0)) / tot,
               100.0 * int(b.get("timeout", 0)) / tot))

    log("")
    log("=" * 78)
    log("VERDICT - conditions as declared")
    log("=" * 78)
    log("")

    def fx(tag, key):
        return M[tag]["FIX14"][0][key]

    # 1 mean hold rises materially from ~3.3-3.4 toward ~11-15, without
    #   collapsing back to the 12-15-distinct-targets degenerate regime
    holds = {t: round(fx(t, "mean_hold"), 1) for t in TREAT if "FIX14" in M[t]}
    dstF = {t: fx(t, "distinct_final") for t in TREAT if "FIX14" in M[t]}
    risen = {t: v > max(CHURN_MEAN_HOLD) * 2 for t, v in holds.items()}
    degenerate = {t: v <= 15 for t, v in dstF.items()}
    g1 = all(risen.values()) and not any(degenerate.values())

    # 2 x-range past 26 under north and south
    xhi = {t: fx(t, "x_hi") for t in TREAT if "FIX14" in M[t]}
    g2 = all(v > 26 for v in xhi.values())

    # 3 argmax-at-commit materially above 2.4-2.9%
    ac = {t: (None if fx(t, "at_commit_frac") is None
              else round(fx(t, "at_commit_frac"), 1))
          for t in TREAT if "FIX14" in M[t]}
    g3 = all(v is not None and v > max(PRE_PART2_ARGMAX) * 2 for v in ac.values())

    # 4 control unchanged on every metric
    if CONTROL in M and "P2ONLY" in M[CONTROL] and "FIX14" in M[CONTROL]:
        g4, ctl_diffs = control_identical(M[CONTROL]["P2ONLY"][1], M[CONTROL]["FIX14"][1])
    else:
        g4, ctl_diffs = False, ["control artifacts missing"]

    # 5 D/north 101 and D/south 101 at zero never_detected
    nd5 = {t: fx(t, "nd") for t in ("D_north_101", "D_south_101") if "FIX14" in M[t]}
    g5 = all(len(v) == 0 for v in nd5.values())

    # 6 A/north seed-trade re-checked (reported, not a pass/fail)
    an = M.get("A_north_101", {})
    trade = {side: an[side][0]["nd"] for _, side in SIDES if side in an}

    for name, ok, detail in [
        ("1 mean hold rises, no degenerate collapse", g1,
         "mean_hold=%s distinct_final=%s" % (holds, dstF)),
        ("2 x-range past 26 under N/S", g2, xhi),
        ("3 argmax-at-commit above 2.4-2.9%%", g3, ac),
        ("4 A/west 505 control unchanged", g4, (ctl_diffs[:3] if ctl_diffs else "identical")),
        ("5 D/north+D/south zero never_detected", g5, nd5),
    ]:
        log("  %-42s %s   %s" % (name, "PASS" if ok else "FAIL", detail))
    log("  %-42s %s   %s"
        % ("6 A/north seed-trade re-checked", "REPORT", trade))
    n_pass = sum([g1, g2, g3, g4, g5])
    log("")
    log("VERDICT: %d of 5 pass/fail conditions passed -> %s"
        % (n_pass, "GATE PASSED" if n_pass == 5 else "GATE FAILED"))
    log("")

    log("never_detected, all sides, all runs:")
    for tag in RUNS:
        for _, side in SIDES:
            if side in M[tag]:
                log("  %-13s %-7s %s" % (tag, side, ",".join(M[tag][side][0]["nd"]) or "-"))

    out = os.path.join(ROOT, "fix14_gate_report.txt")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("\nwrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
