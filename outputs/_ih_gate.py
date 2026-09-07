"""Interior-hazard round, Part 3: the three-arm comparison and the gate, from the
arm files. Missing arms are reported, not fatal, so it can run mid-pool.

Arms (outputs/_ffr_<tag>_*.json):
  canonical 13:  ihbase (8520706)  ihfix (e76c806)  ihrest99 (patched, default)  ihrest6 (patched, --set 6)
                 ihoff (patched, --set 0)  ihdeadC7C6 (the harness-side replay)   ihdeadC7 (live-scored gate)
  fresh 10:      dimfreshbase (8520706)  dimfreshfix (e76c806)  ihrest99fresh  ihrest6fresh  ihofffresh  ihbasefresh
usage: _ih_gate.py
"""
from __future__ import annotations

import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ih_arms as A  # noqa: E402

BASE = A.BASE


def outcomes(tag, combos):
    R = A.load(tag, combos)
    tot = collections.Counter()
    per = {}
    for k in combos:
        r = R.get(k)
        if r is None:
            continue
        e = r["eval"]
        row = (int(e["rescued"]), int(e["dead"]), int(e["firefighter_deaths"]), int(e.get("never_detected", 0) or 0))
        per[k] = row
        for m, v in zip(("r", "d", "ff", "nd"), row):
            tot[m] += v
    return per, tot, len(R)


def exposure(tag, combos):
    R = A.load(tag, combos)
    c = collections.Counter()
    per = {}
    for k in combos:
        r = R.get(k)
        if r is None:
            continue
        by = A.burning_by_step(r)
        n = onf = le3 = 0
        dsum = dn = 0
        for i, row in enumerate(r["uav_steps"]):
            b = by.get(i + 1, set())
            for uid, pos, role, sd in row:
                if role != "victim_searcher" or pos is None:
                    continue
                d = min((abs(pos[0] - fx) + abs(pos[1] - fy) for fx, fy in b), default=99)
                n += 1
                onf += int(d == 0)
                le3 += int(d <= 3)
                if d < 99:
                    dsum += min(d, 30)
                    dn += 1
        strict = None
        if r.get("uav_actions"):
            roles = {uid: role for row in r["uav_steps"] for uid, pos, role, sd in row}
            strict = sum(int(bu or vs) for row in r["uav_actions"] for uid, act, bu, vs, asm, fd in row if roles.get(uid) == "victim_searcher")
        per[k] = (n, onf, le3, strict)
        c["n"] += n
        c["onf"] += onf
        c["le3"] += le3
        c["dsum"] += dsum
        c["dn"] += dn
        if strict is not None:
            c["strict"] += strict
            c["strict_n"] += n
    return per, c


def fmt(row):
    return "%d/%d/%d/%d" % row if row else "   -   "


def section(title):
    print("\n" + title)
    print("-" * len(title))


def table(sample_name, combos, arms):
    section("%s: r/d/ff/nd per seed, then searcher steps on a burning cell" % sample_name)
    O = {t: outcomes(t, combos) for t in arms}
    X = {t: exposure(t, combos) for t in arms}
    print("  %-22s" % "combo" + "".join("%-14s" % t[:13] for t in arms) + " | burning: " + " ".join("%-6s" % t[:6] for t in arms))
    for k in combos:
        print("  %-22s" % A.label(k) + "".join("%-14s" % fmt(O[t][0].get(k)) for t in arms)
              + " | " + "         " + " ".join("%-6s" % (X[t][0][k][1] if k in X[t][0] else "-") for t in arms))
    print("  %-22s" % "TOTAL" + "".join("%-14s" % ("%d/%d/%d/%d" % (O[t][1]["r"], O[t][1]["d"], O[t][1]["ff"], O[t][1]["nd"]) if O[t][2] else "-") for t in arms)
          + " | " + "         " + " ".join("%-6s" % X[t][1]["onf"] for t in arms))
    print("  runs present: " + ", ".join("%s %d/%d" % (t, O[t][2], len(combos)) for t in arms))
    print("  exposure: " + "; ".join("%s %.2f%% (<=3 %.1f%%, dist %.2f%s)" % (
        t, 100.0 * X[t][1]["onf"] / max(1, X[t][1]["n"]), 100.0 * X[t][1]["le3"] / max(1, X[t][1]["n"]),
        X[t][1]["dsum"] / max(1, X[t][1]["dn"]),
        (", strict %.2f%%" % (100.0 * X[t][1]["strict"] / max(1, X[t][1]["strict_n"])) if X[t][1]["strict_n"] else "")) for t in arms))
    return O, X


def identity_line(tag_a, tag_b, combos):
    Ra, Rb = A.load(tag_a, combos), A.load(tag_b, combos)
    n = same = 0
    diffs = []
    for k in combos:
        a, b = Ra.get(k), Rb.get(k)
        if a is None or b is None:
            continue
        n += 1
        d = [f for f in sorted(set(a) | set(b)) if f not in A.SKIP and a.get(f) != b.get(f)]
        if not d:
            same += 1
        else:
            diffs.append((A.label(k), d))
    print("  %-38s %d/%d identical%s" % ("%s == %s" % (tag_a, tag_b), same, n, "" if not diffs else "  DIFFERS: %s" % diffs[:3]))
    return same, n


def post_items():
    section("GATE ITEMS FROM THE POST (tests, route_blocked)")
    p = os.path.join(BASE, "_ih_pytest_rest99.log")
    if os.path.exists(p):
        txt = open(p, encoding="utf-8", errors="replace").read()
        fails = re.findall(r"^FAILED (\S+)", txt, re.M)
        tail = txt.strip().splitlines()[-1] if txt.strip() else ""
        print("  pytest (patched tree, default): %s" % tail)
        for f in fails:
            print("    FAILED %s" % f)
    else:
        print("  pytest: not finished")
    p = os.path.join(BASE, "_ih_flips.txt")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            print("  " + line.rstrip()[:180])
    else:
        print("  flips: not finished")
    p = os.path.join(BASE, "_ih_rbgate_ihrest.txt")
    if os.path.exists(p):
        txt = open(p, encoding="utf-8", errors="replace").read().splitlines()
        for line in txt:
            if "[PASS]" in line or "[FAIL]" in line or line.startswith("ALL") or "D/east" in line[:8] or "D/south" in line[:9]:
                print("  rb: " + line.rstrip()[:160])
    else:
        print("  route_blocked gate: not finished")


def main():
    print("INTERIOR-HAZARD ROUND - PART 3 GATE (generated by outputs/_ih_gate.py)")
    section("IDENTITY PROOFS")
    identity_line("ihoff", "dimfix", A.CANON)
    identity_line("ihoff", "ihfix", A.CANON)
    identity_line("ihofffresh", "dimfreshfix", A.FRESH)
    identity_line("ihrest99", "ihdeadC7C6", A.CANON)
    identity_line("ihbasefresh", "dimfreshbase", A.FRESH)

    Oc, Xc = table("CANONICAL 13", A.CANON, ["ihbase", "ihfix", "ihrest99", "ihrest6", "ihdeadC7"])
    Of, Xf = table("FRESH 10", A.FRESH, ["dimfreshbase", "dimfreshfix", "ihrest99fresh", "ihrest6fresh"])

    section("GATE ITEMS FROM THE ARMS")
    def pct(X, t):
        return 100.0 * X[t][1]["onf"] / max(1, X[t][1]["n"])
    for arm_c, arm_f, name in (("ihrest99", "ihrest99fresh", "range 99"), ("ihrest6", "ihrest6fresh", "range 6")):
        if not Oc[arm_c][2] or not Of[arm_f][2]:
            print("  %s: arms incomplete (%d/13, %d/10)" % (name, Oc[arm_c][2], Of[arm_f][2]))
            continue
        e1 = pct(Xc, arm_c) <= pct(Xc, "ihbase") + 1e-9 and pct(Xf, arm_f) <= pct(Xf, "dimfreshbase") + 1e-9
        e3 = Of[arm_f][1]["d"] <= 3
        e5 = Oc[arm_c][1]["r"] >= Oc["ihbase"][1]["r"] and Of[arm_f][1]["r"] >= Of["dimfreshbase"][1]["r"]
        print("  %s:" % name)
        print("    [%s] item 1 burning-cell exposure <= 8520706 on both samples: canonical %.2f%% vs %.2f%%, fresh %.2f%% vs %.2f%%" % (
            "PASS" if e1 else "FAIL", pct(Xc, arm_c), pct(Xc, "ihbase"), pct(Xf, arm_f), pct(Xf, "dimfreshbase")))
        print("    [%s] item 3 fresh victims dead <= 3: %d" % ("PASS" if e3 else "FAIL", Of[arm_f][1]["d"]))
        print("    [%s] item 5 rescued >= 8520706 on both samples: canonical %d vs %d, fresh %d vs %d" % (
            "PASS" if e5 else "FAIL", Oc[arm_c][1]["r"], Oc["ihbase"][1]["r"], Of[arm_f][1]["r"], Of["dimfreshbase"][1]["r"]))
    # does 6 recover most of 99's benefit?
    if Oc["ihrest6"][2] and Oc["ihrest99"][2]:
        fix, b99, b6 = pct(Xc, "ihfix"), pct(Xc, "ihrest99"), pct(Xc, "ihrest6")
        base = pct(Xc, "ihbase")
        print("  canonical exposure: fix %.2f%%, range 6 %.2f%%, range 99 %.2f%%, base %.2f%% -> range 6 recovers %.0f%% of the fix->99 reduction" % (
            fix, b6, b99, base, 100.0 * (fix - b6) / (fix - b99) if fix != b99 else float("nan")))
    if Of["ihrest6fresh"][2] and Of["ihrest99fresh"][2]:
        fix, b99, b6 = pct(Xf, "dimfreshfix"), pct(Xf, "ihrest99fresh"), pct(Xf, "ihrest6fresh")
        base = pct(Xf, "dimfreshbase")
        print("  fresh exposure:     fix %.2f%%, range 6 %.2f%%, range 99 %.2f%%, base %.2f%% -> range 6 recovers %.0f%% of the fix->99 reduction" % (
            fix, b6, b99, base, 100.0 * (fix - b6) / (fix - b99) if fix != b99 else float("nan")))
    post_items()
    return 0


if __name__ == "__main__":
    sys.exit(main())
