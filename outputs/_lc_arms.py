"""Seed-matched comparison of the four last_cell arms, plus an oscillation audit.

arms: none (stock b6527f7) / a / b / c  -- see _lc_probe.py docstring.
Only cells present in EVERY arm requested are compared, so no arm is
advantaged by a missing run.

Read-only.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _lc_p1 import BASE13, load, tup  # noqa: E402

ARMS = ["none", "a", "b", "c"]


def present(arm, cells):
    return set(c for c in cells if load(arm, *c) is not None)


def osc(d):
    """Oscillation audit over survival-move moves."""
    mv = defaultdict(list)
    for x in d["surv"]:
        if x["moved"] and x["pos"] and x["post"]:
            mv[(int(x["seed"]), str(x["ff"]))].append(
                (int(x["step"]), tup(x["pos"]), tup(x["post"])))
    tot = defaultdict(int)
    for k, seq in mv.items():
        seq.sort()
        tot["moves"] += len(seq)
        for i in range(len(seq)):
            for j in range(i + 1, len(seq)):
                if seq[j][1] == seq[i][2] and seq[j][2] == seq[i][1]:
                    tot["reversals_any"] += 1
                    if seq[j][0] - seq[i][0] == 1:
                        tot["reversals_tight_step"] += 1
                    if j == i + 1:
                        tot["reversals_next_move"] += 1
        # longest run of alternation between two cells
        run = 1
        for i in range(1, len(seq)):
            if (seq[i][1] == seq[i - 1][2] and seq[i][2] == seq[i - 1][1]
                    and seq[i][0] - seq[i - 1][0] <= 2):
                run += 1
                tot["max_alt_run"] = max(tot["max_alt_run"], run)
            else:
                run = 1
    return tot


def readmits(d):
    n = sum(1 for c in d["cand"] if c.get("readmitted"))
    n_taken_d0 = sum(1 for c in d["cand"]
                     if c.get("readmitted") and int(c["cur_dist"]) == 0)
    # arm 'a' drops the filter rather than re-admitting; detect its effect via
    # calls where the stock chain would have been non-empty-but-different
    a_calls = sum(1 for c in d["cand"]
                  if d["arm"] == "a" and int(c["cur_dist"]) == 0
                  and c["lc_admissible"])
    return n, n_taken_d0, a_calls


def main(cells, label):
    avail = {a: present(a, cells) for a in ARMS}
    common = sorted(set(cells) & set.intersection(*[avail[a] for a in ARMS]),
                    key=lambda c: (c[0], c[1], c[2]))
    print("=" * 78)
    print("%s  --  %d cells common to all four arms" % (label, len(common)))
    for a in ARMS:
        missing = sorted(set(cells) - avail[a])
        if missing:
            print("  arm %-4s MISSING: %s" % (a, missing))
    print("=" * 78)
    print("  %-20s %s" % ("cell", "  ".join("%-14s" % ("arm " + a) for a in ARMS)))
    agg = {a: defaultdict(int) for a in ARMS}
    oagg = {a: defaultdict(int) for a in ARMS}
    per_cell = {}
    for c in common:
        line = "  %-20s" % ("%s_%s_%d" % c)
        row = {}
        for a in ARMS:
            d = load(a, *c)
            e = d["evals"][0]
            row[a] = (e["rescued"], e["dead"], e["firefighter_deaths"])
            agg[a]["rescued"] += e["rescued"]
            agg[a]["dead"] += e["dead"]
            agg[a]["ff"] += e["firefighter_deaths"]
            o = osc(d)
            for k, v in o.items():
                if k == "max_alt_run":
                    oagg[a][k] = max(oagg[a][k], v)
                else:
                    oagg[a][k] += v
            r, r0, ac = readmits(d)
            agg[a]["readmits"] += r
            agg[a]["readmits_d0"] += r0
            agg[a]["a_d0_calls"] += ac
            line += "  %-14s" % ("r%d/d%d/ff%d" % row[a])
        per_cell["%s_%s_%d" % c] = row
        flag = "" if len(set(row.values())) == 1 else "   <-- differs"
        print(line + flag)
    print("  " + "-" * 74)
    print("  %-20s %s" % ("TOTAL",
                          "  ".join("%-14s" % ("r%d/d%d/ff%d"
                                               % (agg[a]["rescued"], agg[a]["dead"],
                                                  agg[a]["ff"])) for a in ARMS)))
    print()
    print("  OSCILLATION AUDIT (survival-move moves only)")
    keys = ["moves", "reversals_any", "reversals_tight_step",
            "reversals_next_move", "max_alt_run"]
    print("    %-24s %s" % ("", "  ".join("%-8s" % a for a in ARMS)))
    for k in keys:
        print("    %-24s %s" % (k, "  ".join("%-8d" % oagg[a][k] for a in ARMS)))
    print()
    print("  RE-ADMISSION EVENTS (arms b/c) / cur_dist==0 scans (arm a)")
    print("    %-24s %s" % ("readmitted (set was empty)",
                            "  ".join("%-8d" % agg[a]["readmits"] for a in ARMS)))
    print("    %-24s %s" % ("  of those, cur_dist==0",
                            "  ".join("%-8d" % agg[a]["readmits_d0"] for a in ARMS)))
    print("    %-24s %s" % ("arm-a d0 scans w/ lc adm.",
                            "  ".join("%-8d" % agg[a]["a_d0_calls"] for a in ARMS)))
    return common, per_cell


def deaths_diff(common):
    print()
    print("  PER-DEATH DIFF vs arm none")
    for c in common:
        base = load("none", *c)
        bd = sorted((int(x["step"]), str(x["ff"]), tuple(x["pos"]) if x["pos"] else None)
                    for x in base["deaths"])
        for a in ARMS[1:]:
            d = load(a, *c)
            ad = sorted((int(x["step"]), str(x["ff"]),
                         tuple(x["pos"]) if x["pos"] else None) for x in d["deaths"])
            if ad != bd:
                print("    %-20s arm %-4s  none=%s  arm=%s"
                      % ("%s_%s_%d" % c, a, bd, ad))


if __name__ == "__main__":
    common, _ = main(BASE13, "BASELINE 13-RUN SAMPLE")
    deaths_diff(common)
