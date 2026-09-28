"""fix1 (mf1) P3-4: item 4 alone (mf1Un) vs all off (mf1Zp), sysdebug-probe runs (read-only).

Detection comes from the model's own [Victim Detection] stdout events (the marker status
'candidate' is not a detection signal - memory: victim-candidate-not-undetected).
Per run: victims written off while never detected (must be 0 in mf1Un), victims alive and
undetected at step 210 (== the long_undetected label count by construction), and what the
labelled victims did afterwards.
"""
from __future__ import annotations

import json
import os
import re
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
DET = re.compile(r"\[Victim Detection\] step=(\d+) UAV-(\d+) detected (\w+)")
NAMES = ["AE9103", "DEv10_9122", "DhN9127", "DEv10_9123", "DEv10_9124", "DEv10_9125"]


def load(name):
    d = json.load(open(os.path.join(OUT, "_sd_%s.json" % name), encoding="utf-8"))
    first = {}
    for ln in open(os.path.join(OUT, "_sd_%s.stdout.txt" % name), encoding="utf-8"):
        m = DET.search(ln)
        if m and m.group(3) not in first:
            first[m.group(3)] = int(m.group(1))
    return d, first


def analyse(d, first):
    # rows_vic: [vid, x, y, marker_status, managed_status, ff_id, rescue_assigned, unreachable, cancelled, rescued]
    undetected_writeoffs = []
    alive_undetected_210 = []
    for t, row in enumerate(d["rows_vic"], start=1):
        for r in row:
            vid, unreachable = r[0], bool(r[7])
            detected = vid in first and first[vid] <= t
            if unreachable and not detected and vid not in [w[0] for w in undetected_writeoffs]:
                undetected_writeoffs.append((vid, t, r[4]))
            if t == 210 and not detected and r[4] not in ("dead", "rescued"):
                alive_undetected_210.append(vid)
    final = {r[0]: r[4] for r in d["rows_vic"][-1]}
    return undetected_writeoffs, alive_undetected_210, final


def main() -> int:
    lines = []

    def say(s=""):
        lines.append(s)
        print(s)

    say("P3-4 ITEM 4 ALONE (mf1Un) vs ALL OFF (mf1Zp), 360 steps, the sysdebug write-off configurations + 3")
    tot = {"labelled": 0, "later_detected": 0, "later_rescued": 0, "never_at_end": 0, "writeoffs_un": 0,
           "writeoffs_zp": 0, "resc_un": 0, "resc_zp": 0, "crash": 0}
    for n in NAMES:
        un, fu = load("mf1Un_" + n)
        zp, fz = load("mf1Zp_" + n)
        wu, a210u, finu = analyse(un, fu)
        wz, a210z, finz = analyse(zp, fz)
        eu, ez = un["eval"], zp["eval"]
        tot["crash"] += int(bool(un.get("crashed"))) + int(bool(zp.get("crashed")))
        tot["labelled"] += eu["long_undetected"]
        tot["later_detected"] += eu["long_undetected_detected"]
        tot["later_rescued"] += eu["long_undetected_rescued"]
        tot["never_at_end"] += eu["never_detected"]
        tot["writeoffs_un"] += len(wu)
        tot["writeoffs_zp"] += len(wz)
        tot["resc_un"] += eu["rescued"]
        tot["resc_zp"] += ez["rescued"]
        label_ok = eu["long_undetected"] == len(a210u)
        say("  %-12s ON: undetected write-offs %d | alive+undetected at 210: %s = labels %d (%s) | labelled later "
            "detected %d, rescued %d | never_detected at end %d | rescued %d dead %d terminal %s"
            % (n, len(wu), a210u, eu["long_undetected"], "consistent" if label_ok else "MISMATCH",
               eu["long_undetected_detected"], eu["long_undetected_rescued"], eu["never_detected"],
               eu["rescued"], eu["dead"], un["terminal_step"]))
        say("  %-12s OFF: undetected write-offs %s | never_detected %d | rescued %d dead %d terminal %s | causes %s"
            % ("", [(v, s) for v, s, _ in wz], ez["never_detected"], ez["rescued"], ez["dead"], zp["terminal_step"],
               ez["unreachable_causes"] or "-"))
        for vid in a210u:
            say("      labelled %s: first detected %s, final status %s" % (vid, fu.get(vid), finu.get(vid)))
    say("  TOTAL: ON undetected write-offs %d (must be 0) | OFF undetected write-offs %d | labelled %d, later detected %d, "
        "later rescued %d, never detected at end %d | rescued OFF %d -> ON %d | crashed runs %d"
        % (tot["writeoffs_un"], tot["writeoffs_zp"], tot["labelled"], tot["later_detected"], tot["later_rescued"],
           tot["never_at_end"], tot["resc_zp"], tot["resc_un"], tot["crash"]))
    say("  P3-4: %s" % ("PASS" if tot["writeoffs_un"] == 0 and tot["later_rescued"] >= 1 and tot["crash"] == 0 else "FAIL"))
    with open(os.path.join(OUT, "_mf1_item4_analysis.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
