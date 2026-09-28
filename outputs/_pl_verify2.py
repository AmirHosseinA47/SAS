"""Planner round, Part 3: the numbers the review of 2026-09-28 corrected, recomputed from the raw files.

Read-only. Fixes the analyzer's DETECTION defect: a victim marker keeps reading 'candidate' after the
victim is detected, until a firefighter is assigned, so 'candidate' is NOT 'undetected'. Here a victim's
DETECTION STEP is the first of
  - its '[Victim Detection] step=t UAV-u detected <vid>' line in the run's .stdout.txt - the code path
    that sets managed_victims[vid].confirmed = True (wildfire_model.py, the proximity detection), and
  - the first harness row whose marker status is neither candidate, dead nor unreachable (an assignment
    implies a confirmed victim; covers the rescue executor's 'confirm' path).
Row k of victim_steps / uav_steps is the state after harness step k; the detection line's step is the
same counter, so a victim is UNDETECTED at row k iff its detection step > k. ALIVE-UNDETECTED at row k:
marker status 'candidate' (not dead, not unreachable, not rescued) and undetected.

usage: python outputs/_pl_verify2.py  (prints; --out FILE writes too)
"""
from __future__ import annotations

import collections
import json
import os
import re
import statistics
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _pl_analyze as A  # noqa: E402  (loading / seed sets / repo check only)

OUT: list = []
DET_RE = re.compile(r"^\[Victim Detection\] step=(\d+) UAV-\S+ detected (\S+) at")


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)


def stdout_path(tag, t):
    w, r, s = t
    return os.path.join(HERE, "_ffr_%s_%s_%s_%s.stdout.txt" % (tag, w, A.rr(r), s))


def detection_steps(tag, t):
    d = A.load(tag, t)
    det = {}
    with open(stdout_path(tag, t), "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            m = DET_RE.match(ln)
            if m and m.group(2) not in det:
                det[m.group(2)] = int(m.group(1))
    for k, row in enumerate(d["victim_steps"], start=1):
        for v in row:
            if str(v[2]) not in ("candidate", "dead", "unreachable") and (v[0] not in det or det[v[0]] > k):
                det[v[0]] = k
    return det


def alive_undetected(d, det, k):
    """victims alive and not yet detected at row k (1-based)."""
    row = d["victim_steps"][k - 1]
    return [v[0] for v in row if str(v[2]) == "candidate" and det.get(v[0], 10 ** 9) > k]


def undetected_any(d, det, k):
    return [v[0] for v in d["victim_steps"][k - 1] if det.get(v[0], 10 ** 9) > k]


def no_flying_searcher(row):
    return not any(u[2] == A.VS and (u[5] if len(u) > 5 else "") == "" for u in row)


def main():
    N = A.n30()
    say("=" * 90)
    say("REVIEW CORRECTIONS (2026-09-28) - detection from the model's detection events")
    say("=" * 90)
    # 1. first detection per victim
    for tag in ("plC", "plG"):
        v = []
        for t in A.C13 + N:
            v.extend(detection_steps(tag, t).values())
        say("first detection per victim %s: n %d, mean %.1f, median %s" % (tag, len(v), statistics.mean(v), statistics.median(v)))
    # 2. 7.5 (f) exposure and 8 (a) runs
    for tag in ("plC", "plG"):
        tot = collections.Counter()
        per = {}
        runs_block = []
        for label, tuples in (("C13", A.C13), ("N30", N), ("RB7", A.RB7)):
            for t in tuples:
                d = A.load(tag, t)
                det = detection_steps(tag, t)
                n = 0
                for k, row in enumerate(d["uav_steps"], start=1):
                    if no_flying_searcher(row) and alive_undetected(d, det, k):
                        n += 1
                per[(label, t)] = n
                tot[label] += n
                if label != "RB7" and n:
                    runs_block.append(A.tl(t))
        say("7.5 (f) steps with NO flying searcher AND an alive victim not yet detected, %s: %s, pooled %d"
            % (tag, dict(tot), sum(tot.values())))
        say("   8 (a) C13+N30 runs with such a step: %d %s" % (len(runs_block), runs_block))
        if tag == "plC":
            per_c = per
        else:
            diff = [(A.tl(k[1]), per_c[k], per[k]) for k in per if per[k] != per_c[k]]
            say("   runs where plC and plG differ on it: %s" % diff)
    # 3. the 45 searcher -> tracker switches: alive-undetected vs dead-undetected
    rows = []
    for t in A.C13 + N:
        s = A.load("plG", t, side=True)
        d = A.load("plG", t)
        det = detection_steps("plG", t)
        ex = {e["t"]: e for e in s["exec"]}
        for r in s["plan"]:
            if r["cat"] != "SWITCH" or r["sel_params"]["to"] != A.FT:
                continue
            k = r["t"]
            vc = float(r["nine"][r["sel"]]["victim_contribution"])
            n_vs = sum(1 for u, roles in ex[k]["pre"].items() if roles[0] == A.VS)
            planner_undet = round(-vc * n_vs * len(d["victim_steps"][0])) if vc else 0
            prev = k - 1 if k > 1 else 1
            und = undetected_any(d, det, prev)
            alive = alive_undetected(d, det, prev)
            rows.append((A.tl(t), k, r["margin"], planner_undet, len(und), len(alive), n_vs))
    und16 = [x for x in rows if x[3] > 0]
    say("searcher -> tracker switches: %d; with the planner's own count of undetected > 0: %d" % (len(rows), len(und16)))
    agree = sum(1 for x in rows if x[3] == x[4])
    say("   planner's count == event-based undetected count at row t-1 on %d/%d switches" % (agree, len(rows)))
    alive_rows = [x for x in und16 if x[5] > 0]
    dead_rows = [x for x in und16 if x[5] == 0]
    say("   of the %d: an ALIVE victim not yet detected in %d; only dead/unreachable undetected victims in %d %s"
        % (len(und16), len(alive_rows), len(dead_rows), [(x[0], x[1]) for x in dead_rows]))
    if alive_rows:
        ms = [x[2] for x in alive_rows]
        ts = [x[1] for x in alive_rows]
        say("   alive cases: steps %d-%d (median %s), margins %+.4f to %+.4f" % (min(ts), max(ts), statistics.median(ts), min(ms), max(ms)))
    mism = [x for x in rows if x[3] != x[4]]
    for x in mism:
        say("   count mismatch: %s step %d planner %d events %d alive %d" % (x[0], x[1], x[3], x[4], x[5]))
    say("   searcher holders before the %d undetected switches: %s" % (len(und16), dict(collections.Counter(x[6] for x in und16))))
    # 4. firefighter deaths before / after the terminal step
    for tag in ("plC", "plG", "plF", "plS"):
        for label, tuples in (("N30", N),) + ((("C13", A.C13),) if tag in ("plC", "plG") else ()):
            pre = post = 0
            for t in tuples:
                d = A.load(tag, t)
                term = d.get("terminal_step") or 10 ** 9
                seen = set()
                for k, row in enumerate(d["ff_steps"], start=1):
                    for f in row:
                        if f[2] == "dead" and f[0] not in seen:
                            seen.add(f[0])
                            if k <= term:
                                pre += 1
                            else:
                                post += 1
            say("firefighter deaths %s %s: at or before the terminal step %d, after it %d" % (tag, label, pre, post))
    # 5. unreachable and per-seed rescued splits for the reference arms, and firefight blocks
    for tag in ("plC", "plF", "plS", "plG"):
        un = sum(A.load(tag, t)["eval"]["unreachable"] for t in N)
        nd = sum(A.load(tag, t)["eval"]["never_detected"] for t in N)
        ff_block = sum(1 for t in N if A.load(tag, t).get("firefight_counters") is not None)
        ff_nonzero = sum(1 for t in N if any((A.load(tag, t).get("firefight_counters") or {}).values()))
        say("%s N30: unreachable %d (never_detected cause %d); runs with a firefight block %d, non-zero %d" % (tag, un, nd, ff_block, ff_nonzero))
    for tag in ("plF", "plS"):
        up = sum(1 for t in N if A.load(tag, t)["eval"]["rescued"] > A.load("plC", t)["eval"]["rescued"])
        dn = sum(1 for t in N if A.load(tag, t)["eval"]["rescued"] < A.load("plC", t)["eval"]["rescued"])
        say("%s vs plC per seed rescued: %s higher %d, plC higher %d" % (tag, tag, up, dn))
    # 6. utility modes seed-matched
    flips = collections.Counter()
    for t in A.C13 + N:
        c, g = A.load("plC", t, side=True), A.load("plG", t, side=True)
        for rc, rg in zip(c["plan"], g["plan"]):
            if rc["mode"] != rg["mode"]:
                flips["%s->%s" % (rc["mode"], rg["mode"])] += 1
    say("utility-mode differences plC -> plG, seed-matched steps: %s" % dict(flips))
    # 7. terminal means
    for tag in ("plC", "plG"):
        v = [A.load(tag, t)["terminal_step"] for t in N]
        say("N30 terminal mean %s %.2f (sum %d)" % (tag, statistics.mean(v), sum(v)))
    for tag in ("plC", "plG"):
        say("pooled C13+N30 unreachable %s %d" % (tag, sum(A.load(tag, t)["eval"]["unreachable"] for t in A.C13 + N)))


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    main()
    if "--out" in sys.argv:
        with open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(OUT) + "\n")
