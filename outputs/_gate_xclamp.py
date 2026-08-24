"""Gate for the x-clamp (strip-latch) change, measured BASE vs POST.

WHICH GATE APPLIES TO WHICH CHANGE
----------------------------------
_gate_commitment.py belongs to the TARGET-COMMITMENT round (commit cfaeb21,
reverted). Its conditions - impossible-segment rate and median slack - test
whether a searcher can physically reach the target it is holding, which is the
thing target commitment changed. Its BASE dict is hardcoded from the
PRE-COMMITMENT tree, so running it against x-clamp artifacts compares two
different trees and its deltas are not the x-clamp fix's own A/B.

This script implements the conditions the X-CLAMP round declared, derived from
the Step 0 diagnosis (outputs/step0_target_following.txt, Q6): failing runs
proposed only 12/14/13 DISTINCT target cells while the succeeding run proposed
37, and the generator never proposed a cell inside the missed victim's legal
observation-post set. The x-clamp fix attacks that by removing the west-clamp
re-fire that pins proposals to x in {8, 41}.

Both metric sets are reported here, and BOTH are computed BASE vs POST on the
same artifacts, so the impossible-segment question is answered on the x-clamp
fix's own baseline rather than the commitment round's.

  BASE = outputs/_tf_<tag>_BASE.json   (pre-x-clamp, same tree as POST otherwise)
  POST = outputs/_tf_<tag>.json        (x-clamp applied)

Clamp goals for a 50x50 grid: west_goal = 8, east_goal = 41.
"""
from __future__ import annotations

import itertools
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS = [("D", "north", 101), ("D", "south", 101), ("A", "north", 101), ("A", "west", 505)]
CONTROL = "A_west_505"
CLAMP_X = (8, 41)


def load(tag: str, suffix: str):
    p = os.path.join(ROOT, "_tf_%s%s.json" % (tag, suffix))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def cell(v):
    return (int(v[0]), int(v[1])) if v else None


def finalize_out(rec):
    """Last finalize output recorded in the step."""
    out = None
    for name, c in rec.get("gen_inner") or []:
        if name == "finalize" and c:
            out = cell(c)
    return out


def proposed(rec):
    t = rec.get("gen_target_exec") or rec.get("gen_target_planner")
    return cell(t)


def positions(sr):
    return [cell(a[1]) for r in sr for a in (r.get("advance") or []) if a and a[1]]


# ---- commitment-round metrics (impossible-segment rate, median slack) ----
def segments(sr):
    rows = []
    for r in sr:
        t = proposed(r)
        pos = None
        for a in r.get("advance") or []:
            if a and a[0]:
                pos = cell(a[0])
        rows.append((t, pos))
    out = []
    for key, grp in itertools.groupby(rows, key=lambda z: z[0]):
        grp = list(grp)
        if key is None:
            continue
        start = next((p for _, p in grp if p), None)
        if start is None:
            continue
        need = abs(key[0] - start[0]) + abs(key[1] - start[1])
        out.append((len(grp), need))
    return out


def metrics(d) -> dict:
    sr = d["step_records"]
    segs = segments(sr)
    imposs = sum(1 for L, need in segs if L < need)
    slack = sorted(L - need for L, need in segs)
    xs = [p[0] for p in positions(sr) if p]

    props = [proposed(r) for r in sr]
    props = [p for p in props if p]
    fins = [(finalize_out(r), cell(r.get("prefinal_target"))) for r in sr]
    fins = [(f, pre) for f, pre in fins if f]
    clamped = [1 for f, _ in fins if f[0] in CLAMP_X]
    relocated_to_clamp = [
        1 for f, pre in fins if f[0] in CLAMP_X and pre is not None and f != pre
    ]
    scored = [(f, pre) for f, pre in fins if pre is not None]
    survived = [1 for f, pre in scored if f == pre]

    return dict(
        # x-clamp round conditions
        distinct_proposed=len(set(props)),
        n_proposed=len(props),
        clamp_hits=len(clamped),
        clamp_frac=(100.0 * len(clamped) / len(fins)) if fins else 0.0,
        reloc_to_clamp=len(relocated_to_clamp),
        argmax_survives=len(survived),
        argmax_scored=len(scored),
        argmax_frac=(100.0 * len(survived) / len(scored)) if scored else 0.0,
        x_lo=min(xs) if xs else 0,
        x_hi=max(xs) if xs else 0,
        nd=sorted(d.get("nd") or []),
        # commitment-round metrics
        segs=len(segs),
        imposs_pct=(100.0 * imposs / len(segs)) if segs else 0.0,
        med_slack=slack[len(slack) // 2] if slack else 0,
    )


def control_identical(base_d, post_d) -> tuple[bool, list]:
    """Behavioural equality for the control, ignoring instrumentation-only keys.

    The probe gained west_strip_done / east_strip_done keys, so the raw JSON
    differs even when behaviour does not. Compare the behavioural trace instead.
    """
    b, p = base_d["step_records"], post_d["step_records"]
    diffs = []
    if len(b) != len(p):
        return False, ["step count %d vs %d" % (len(b), len(p))]
    for i, (rb, rp) in enumerate(zip(b, p)):
        if proposed(rb) != proposed(rp):
            diffs.append("step %d proposed %s vs %s" % (i, proposed(rb), proposed(rp)))
        elif finalize_out(rb) != finalize_out(rp):
            diffs.append("step %d finalize %s vs %s" % (i, finalize_out(rb), finalize_out(rp)))
        elif cell(rb.get("searcher_pos")) != cell(rp.get("searcher_pos")):
            diffs.append("step %d searcher_pos differs" % i)
        if len(diffs) >= 5:
            break
    if sorted(base_d.get("nd") or []) != sorted(post_d.get("nd") or []):
        diffs.append("nd %s vs %s" % (base_d.get("nd"), post_d.get("nd")))
    return (not diffs), diffs


def main() -> int:
    lines: list = []

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lines.append(msg)

    M: dict = {}
    for s, w, sd in RUNS:
        tag = "%s_%s_%d" % (s, w, sd)
        base_d, post_d = load(tag, "_BASE"), load(tag, "")
        if base_d is None or post_d is None:
            log("%-13s MISSING (base=%s post=%s)"
                % (tag, base_d is not None, post_d is not None))
            continue
        M[tag] = (metrics(base_d), metrics(post_d), base_d, post_d)

    log("=" * 78)
    log("X-CLAMP GATE - conditions declared for THIS round, BASE vs POST")
    log("=" * 78)
    log("")
    log("%-13s %-22s %10s %10s %9s" % ("run", "metric", "BASE", "POST", "delta"))
    log("-" * 68)
    for tag, (b, p, _, _) in M.items():
        rows = [
            ("distinct proposed cells", b["distinct_proposed"], p["distinct_proposed"]),
            ("relocations to x{8,41}", b["clamp_hits"], p["clamp_hits"]),
            ("  as %% of finalizes", round(b["clamp_frac"], 1), round(p["clamp_frac"], 1)),
            ("argmax-survives %", round(b["argmax_frac"], 1), round(p["argmax_frac"], 1)),
            ("searcher x_hi", b["x_hi"], p["x_hi"]),
            ("searcher x_lo", b["x_lo"], p["x_lo"]),
        ]
        for i, (name, bv, pv) in enumerate(rows):
            log("%-13s %-22s %10s %10s %+9.1f"
                % (tag if i == 0 else "", name, bv, pv, float(pv) - float(bv)))
        log("%-13s %-22s %10s %10s" % ("", "never_detected",
                                       ",".join(b["nd"]) or "-",
                                       ",".join(p["nd"]) or "-"))
        log("")

    log("=" * 78)
    log("COMMITMENT-ROUND METRICS on the SAME artifacts (correct BASE vs POST)")
    log("=" * 78)
    log("")
    log("These are _gate_commitment.py's two conditions. They belong to the")
    log("target-commitment round, but computed here on the x-clamp fix's own")
    log("baseline rather than the hardcoded pre-commitment numbers.")
    log("")
    log("%-13s %10s %10s %9s   %10s %10s %9s"
        % ("run", "imposs%B", "imposs%P", "delta", "medslackB", "medslackP", "delta"))
    log("-" * 78)
    for tag, (b, p, _, _) in M.items():
        log("%-13s %10.1f %10.1f %+9.1f   %10d %10d %+9d"
            % (tag, b["imposs_pct"], p["imposs_pct"], p["imposs_pct"] - b["imposs_pct"],
               b["med_slack"], p["med_slack"], p["med_slack"] - b["med_slack"]))
    log("")
    log("For contrast, _gate_commitment.py's hardcoded PRE-COMMITMENT baseline was")
    log("imposs 94/100/86/98 and med_slack -23/-26/-26/-23 for")
    log("D_north_101 / D_south_101 / A_north_101 / A_west_505.")

    log("")
    log("=" * 78)
    log("X-CLAMP GATE VERDICT")
    log("=" * 78)
    log("")
    treat = [t for t in M if t != CONTROL]

    c1 = {t: M[t][1]["distinct_proposed"] - M[t][0]["distinct_proposed"] for t in treat}
    g1 = all(v > 0 for v in c1.values())
    c2 = {t: M[t][1]["clamp_hits"] - M[t][0]["clamp_hits"] for t in treat}
    g2 = all(v < 0 for v in c2.values())
    c3 = {t: round(M[t][1]["argmax_frac"] - M[t][0]["argmax_frac"], 1) for t in treat}
    g3 = all(v > 0 for v in c3.values())
    c4 = {t: M[t][1]["x_hi"] for t in treat}
    g4 = any(v > 26 for v in c4.values())
    ok_ctl, ctl_diffs = (True, ["control artifacts missing"])
    if CONTROL in M:
        ok_ctl, ctl_diffs = control_identical(M[CONTROL][2], M[CONTROL][3])
    g5 = ok_ctl
    detected = {
        t: sorted(set(M[t][0]["nd"]) - set(M[t][1]["nd"])) for t in treat
    }
    g6 = any(detected.values())

    for name, ok, detail in [
        ("1 distinct proposed targets rise", g1, c1),
        ("2 relocations to x{8,41} fall", g2, c2),
        ("3 argmax-survives rate rises", g3, c3),
        ("4 searcher x-range widens past 26", g4, c4),
        ("5 control unchanged", g5, (ctl_diffs[:3] if ctl_diffs else "identical")),
        ("6 >=1 missed victim now detected", g6, detected),
    ]:
        log("  %-36s %s   %s" % (name, "PASS" if ok else "FAIL", detail))
    n_pass = sum([g1, g2, g3, g4, g5, g6])
    log("")
    log("VERDICT: %d of 6 passed -> %s"
        % (n_pass, "GATE PASSED" if n_pass == 6 else "GATE FAILED"))
    log("")
    log("NEW misses introduced (present in POST, absent in BASE):")
    for t in treat:
        new = sorted(set(M[t][1]["nd"]) - set(M[t][0]["nd"]))
        log("  %-13s %s" % (t, ",".join(new) or "none"))

    out = os.path.join(ROOT, "xclamp_gate_report.txt")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    log("")
    log("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
