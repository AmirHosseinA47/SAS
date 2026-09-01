"""Seed-matched arm comparison for defect #9-A1 (scorched-ground risk term).

Reads outputs/_sc_<arm>_<wind>_<roles>_<seed>.json from _sc_probe.py.
Only cells present in EVERY arm compared are pooled, so no arm is advantaged by
a missing run.  Read-only.
"""
from __future__ import annotations
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

BASE13 = [("east", "default", 101), ("east", "default", 202), ("east", "default", 303),
          ("east", "half", 101), ("east", "half", 202), ("east", "half", 303),
          ("east", "half", 404), ("east", "half", 505),
          ("south", "half", 101), ("south", "half", 202), ("south", "half", 303),
          ("south", "half", 404), ("south", "half", 505)]
FRESH10 = [("east", "half", s) for s in (606, 707, 808, 909, 1010)] + \
          [("south", "half", s) for s in (606, 707, 808, 909, 1010)]
ALL23 = BASE13 + FRESH10

ARMS = ["none", "a", "b", "c"]
PEN = {"stock": "-", "none": 0, "a": 1, "b": 10, "c": 100}

# The three deaths defect #9 Part 2 attributed to scorched ground igniting under
# a stationary unit (outputs/burntcells_part1.txt section 2.1).
NAMED = [(("east", "half", 404), "ff_unit_0", (31, 38), 33),
         (("east", "default", 101), "ff_unit_0", (41, 41), 42),
         (("east", "default", 202), "ff_unit_0", (34, 49), 225)]


def load(arm, cell):
    w, r, s = cell
    p = os.path.join(HERE, "_sc_%s_%s_%s_%d.json" % (arm, w, r, s))
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    return d


def one(arm, cell):
    d = load(arm, cell)
    return None if d is None else d["runs"][0]


def present(arm, cells):
    return set(c for c in cells if one(arm, c) is not None)


def last_alive_ground(run, unit):
    best = None
    for row in run["fftrace"]:
        if row["unit"] == unit and (best is None or row["step"] > best["step"]):
            best = row
    return best


def deaths_on(run):
    """Deaths classified by the ground the unit last STOOD on while alive.

    At the death step the cell is by definition burning, so classifying the
    death step itself would report every death as "burning" and hide the
    distinction the round is about.
    """
    out = []
    for dth in run["deaths"]:
        la = last_alive_ground(run, dth["unit"])
        g = la["ground"] if la else None
        same = bool(la and dth["cell"] and list(la["cell"]) == list(dth["cell"]))
        out.append({"unit": dth["unit"], "step": dth["step"], "cell": dth["cell"],
                    "ground_at_death": dth["ground"],
                    "ground_last_alive": g, "died_in_place": same})
    return out


def agg(arm, cells):
    t = defaultdict(int)
    t["runs"] = 0
    dscorch = []
    for c in cells:
        r = one(arm, c)
        if r is None:
            continue
        t["runs"] += 1
        e = r["eval"]
        t["ff"] += int(e["firefighter_deaths"])
        t["rescued"] += int(e["rescued"])
        t["dead"] += int(e["dead"])
        for k in ("total", "burnt", "scorched", "burning", "green"):
            t["occ_" + k] += int(r["occ"][k])
        for k in ("total", "onto_burnt", "onto_scorched", "onto_burning", "onto_green"):
            t["mv_" + k] += int(r["mv"][k])
        for d in deaths_on(r):
            if d["ground_last_alive"] == "scorched":
                t["deaths_scorched"] += 1
                dscorch.append(("%s_%s_%d" % c, d))
            elif d["ground_last_alive"] == "burnt":
                t["deaths_burnt"] += 1
            elif d["ground_last_alive"] == "green":
                t["deaths_green"] += 1
            elif d["ground_last_alive"] == "burning":
                t["deaths_burning"] += 1
    return t, dscorch


def hdr(s):
    print()
    print("=" * 78)
    print(s)
    print("=" * 78)


def provenance():
    hdr("PROVENANCE  arm 'stock' (no monkeypatch at all) vs arm 'none' (harness, pen=0)")
    ok = bad = miss = 0
    ffs = ffn = 0
    for c in BASE13:
        a, b = one("stock", c), one("none", c)
        if a is None or b is None:
            print("  %-20s MISSING (%s/%s)" % ("%s_%s_%d" % c,
                                               "ok" if a else "-", "ok" if b else "-"))
            miss += 1
            continue
        ffs += int(a["eval"]["firefighter_deaths"])
        ffn += int(b["eval"]["firefighter_deaths"])
        same_sig = a["sig"] == b["sig"]
        same_out = (a["eval"]["rescued"], a["eval"]["dead"],
                    a["eval"]["firefighter_deaths"]) == \
                   (b["eval"]["rescued"], b["eval"]["dead"],
                    b["eval"]["firefighter_deaths"])
        good = same_sig and same_out
        ok += good
        bad += (not good)
        print("  %-20s ff=%d  sig %s (%d steps)  outcomes %s"
              % ("%s_%s_%d" % c, a["eval"]["firefighter_deaths"],
                 "IDENTICAL" if same_sig else "DIFFER", len(a["sig"]),
                 "same" if same_out else "DIFFER"))
    print("  ---")
    print("  %d identical, %d differ, %d missing" % (ok, bad, miss))
    print("  firefighter_deaths  stock=%d  none=%d   (committed figure at e02377b: 6)"
          % (ffs, ffn))


def outcome_table(cells, label):
    hdr("%s  --  per-run outcomes  r=rescued d=victims-dead ff=firefighter deaths" % label)
    avail = {a: present(a, cells) for a in ARMS}
    common = [c for c in cells if all(c in avail[a] for a in ARMS)]
    for a in ARMS:
        m = sorted(set(cells) - avail[a])
        if m:
            print("  arm %-5s MISSING %s" % (a, ["%s_%s_%d" % x for x in m]))
    print("  %-22s %s" % ("run", "  ".join("%-16s" % ("arm %s (+%s)" % (a, PEN[a]))
                                           for a in ARMS)))
    for c in common:
        line = "  %-22s" % ("%s_%s_%d" % c)
        vals = []
        for a in ARMS:
            r = one(a, c)
            e = r["eval"]
            vals.append((e["rescued"], e["dead"], e["firefighter_deaths"]))
            line += "  %-16s" % ("r%d/d%d/ff%d" % vals[-1])
        print(line + ("" if len(set(vals)) == 1 else "   <-- differs"))
    return common


def summary(cells, label):
    hdr("%s  --  arm summary (%d runs)" % (label, len(cells)))
    pairs = {a: agg(a, cells) for a in ARMS}
    rows = {a: pairs[a][0] for a in ARMS}
    scorch_rows = {a: pairs[a][1] for a in ARMS}
    keys = [
        ("firefighter_deaths", lambda t: t["ff"]),
        ("victims rescued", lambda t: t["rescued"]),
        ("victims dead", lambda t: t["dead"]),
        ("", None),
        ("deaths on SCORCHED ground", lambda t: t["deaths_scorched"]),
        ("deaths on green ground", lambda t: t["deaths_green"]),
        ("deaths on burnt ground", lambda t: t["deaths_burnt"]),
        ("deaths on burning ground", lambda t: t["deaths_burning"]),
        ("", None),
        ("ff-steps alive (total)", lambda t: t["occ_total"]),
        ("  on SCORCHED ground", lambda t: t["occ_scorched"]),
        ("  on UNBURNT GREEN ground", lambda t: t["occ_green"]),
        ("  on BURNT ground", lambda t: t["occ_burnt"]),
        ("  on BURNING ground", lambda t: t["occ_burning"]),
        ("", None),
        ("moves executed", lambda t: t["mv_total"]),
        ("  onto SCORCHED", lambda t: t["mv_onto_scorched"]),
        ("  onto GREEN", lambda t: t["mv_onto_green"]),
        ("  onto BURNT", lambda t: t["mv_onto_burnt"]),
    ]
    print("  %-30s %s" % ("", "  ".join("%-14s" % ("arm %s (+%s)" % (a, PEN[a]))
                                        for a in ARMS)))
    for name, fn in keys:
        if fn is None:
            print()
            continue
        print("  %-30s %s" % (name, "  ".join("%-14d" % fn(rows[a]) for a in ARMS)))
    print()
    print("  DISPLACEMENT CHECK, as %% of alive-steps (raw counts move with survival)")
    for name, k in (("green", "occ_green"), ("scorched", "occ_scorched"),
                    ("burnt", "occ_burnt"), ("burning", "occ_burning")):
        print("  %-30s %s" % ("  " + name + " share",
                              "  ".join("%-14s" % ("%.2f%%" % (100.0 * rows[a][k]
                                                               / max(1, rows[a]["occ_total"])))
                                         for a in ARMS)))
    print()
    print("  DEATHS WHOSE LAST ALIVE STEP WAS ON SCORCHED GROUND")
    for a in ARMS:
        if not scorch_rows[a]:
            print("    arm %-5s none" % a)
        for tag, d in scorch_rows[a]:
            print("    arm %-5s %-22s %s step %d cell %s"
                  % (a, tag, d["unit"], d["step"], tuple(d["cell"]) if d["cell"] else None))
    return rows


def death_diff(cells):
    hdr("PER-DEATH DIFF vs arm none")
    any_diff = False
    for c in cells:
        base = one("none", c)
        bd = sorted((d["step"], d["unit"], tuple(d["cell"]) if d["cell"] else None,
                     d["ground_last_alive"]) for d in deaths_on(base))
        for a in ARMS[1:]:
            r = one(a, c)
            ad = sorted((d["step"], d["unit"], tuple(d["cell"]) if d["cell"] else None,
                         d["ground_last_alive"]) for d in deaths_on(r))
            if ad != bd:
                any_diff = True
                print("  %-22s arm %s" % ("%s_%s_%d" % c, a))
                print("      none: %s" % (bd,))
                print("      arm%s: %s" % (a, ad))
    if not any_diff:
        print("  no death moved in any arm on any run in the pool")


def named_cases():
    hdr("THE THREE NAMED APPROACH CASES - does the unit still enter the death cell?")
    print("  A penalty that only acts at the death step is too late; the window")
    print("  that matters is the APPROACH.  'entered' = the unit occupied that cell")
    print("  at any step, with the first such step and the ground it was then.")
    for cell, unit, target, dstep in NAMED:
        print()
        print("  %s  %s  cell %s  (stock death at step %d)"
              % ("%s_%s_%d" % cell, unit, target, dstep))
        for a in ["stock"] + ARMS:
            r = one(a, cell)
            if r is None:
                print("    arm %-6s MISSING" % a)
                continue
            occ = [row for row in r["fftrace"]
                   if row["unit"] == unit and tuple(row["cell"]) == target]
            dth = [d for d in deaths_on(r) if d["unit"] == unit]
            first = occ[0]["step"] if occ else None
            last = occ[-1]["step"] if occ else None
            grounds = sorted(set(row["ground"] for row in occ))
            print("    arm %-6s entered=%-5s steps=%s..%s (%d) ground=%s | death: %s"
                  % (a, bool(occ), first, last, len(occ), grounds,
                     ("step %d on %s at %s" % (dth[0]["step"], dth[0]["ground_last_alive"],
                                               tuple(dth[0]["cell"]) if dth[0]["cell"] else None))
                     if dth else "SURVIVED"))


def trajectory_divergence(cells):
    hdr("TRAJECTORY DIVERGENCE vs arm none (first step whose signature differs)")
    for c in cells:
        base = one("none", c)
        if base is None:
            continue
        line = "  %-22s" % ("%s_%s_%d" % c)
        for a in ARMS[1:]:
            r = one(a, c)
            if r is None:
                line += "  arm %s: MISSING" % a
                continue
            d = None
            for i, (x, y) in enumerate(zip(base["sig"], r["sig"]), start=1):
                if x != y:
                    d = i
                    break
            line += "  arm %s: %s" % (a, ("step %d" % d) if d else "IDENTICAL")
        print(line)


def opportunity():
    hdr("OPPORTUNITY COUNT - how often the scorched term was non-zero at all")
    print("  Counted in EVERY arm, including the pen=0 control, so the control")
    print("  reports how often the term WOULD have applied had it been enabled.")
    for a in ARMS:
        tc = ts = ta = 0
        n = 0
        for c in ALL23:
            d = load(a, c)
            if d is None:
                continue
            n += 1
            tc += int(d["counters"]["risk_calls"])
            ts += int(d["counters"]["risk_calls_scorched"])
            ta += int(d["counters"]["risk_calls_scorched_applied"])
        print("  arm %-5s (+%-2s)  %d runs  risk-calls=%d  scorched=%d (%.2f%%)  applied=%d"
              % (a, PEN[a], n, tc, ts, 100.0 * ts / max(1, tc), ta))


def arm_identity(cells):
    hdr("ARM-vs-ARM IDENTITY (per-step signatures, all runs in the pool)")
    print("  Two arms that are trajectory-identical have not tested two")
    print("  magnitudes; they have tested one, twice.")
    for i in range(1, len(ARMS)):
        for j in range(i + 1, len(ARMS)):
            x, y = ARMS[i], ARMS[j]
            same, diff, dl = 0, 0, []
            for c in cells:
                a, b = one(x, c), one(y, c)
                if a is None or b is None:
                    continue
                if a["sig"] == b["sig"]:
                    same += 1
                else:
                    diff += 1
                    dl.append("%s_%s_%d" % c)
            print("  arm %s (+%s) vs arm %s (+%s):  %d identical, %d differ  %s"
                  % (x, PEN[x], y, PEN[y], same, diff, dl if dl else ""))


def changed_runs(arm, cells):
    return [c for c in cells
            if one("none", c) is not None and one(arm, c) is not None
            and one("none", c)["sig"] != one(arm, c)["sig"]]


def displacement_on_changed(cells):
    hdr("DISPLACEMENT CHECK, restricted to the runs each arm actually perturbed")
    print("  On a run the arm left trajectory-identical the delta is zero by")
    print("  construction, so pooling all 23 dilutes the effect.  Firefighter-")
    print("  steps moving OFF burnt/scorched ground and ONTO unburnt green is")
    print("  the specific failure mode this round was told to guard against.")
    for arm in ARMS[1:]:
        ch = changed_runs(arm, cells)
        print()
        print("  arm %s (+%s): perturbed %d of %d runs  %s"
              % (arm, PEN[arm], len(ch), len(cells), ["%s_%s_%d" % x for x in ch]))
        if not ch:
            continue
        nt = sum(one("none", c)["occ"]["total"] for c in ch)
        at = sum(one(arm, c)["occ"]["total"] for c in ch)
        for k in ("total", "green", "scorched", "burnt", "burning"):
            n = sum(one("none", c)["occ"][k] for c in ch)
            a = sum(one(arm, c)["occ"][k] for c in ch)
            sh = ""
            if k != "total":
                sh = "%.2f%% -> %.2f%%  (%+0.2f pp)" % (
                    100.0 * n / max(1, nt), 100.0 * a / max(1, at),
                    100.0 * a / max(1, at) - 100.0 * n / max(1, nt))
            print("    ff-steps %-10s none=%-6d arm=%-6d %-8s %s"
                  % (k, n, a, "%+d" % (a - n), sh))
        for c in ch:
            n, a = one("none", c), one(arm, c)
            print("      %-20s r%d/d%d/ff%d -> r%d/d%d/ff%d   burnt %d->%d  "
                  "scorched %d->%d  green %d->%d"
                  % ("%s_%s_%d" % c, n["eval"]["rescued"], n["eval"]["dead"],
                     n["eval"]["firefighter_deaths"], a["eval"]["rescued"],
                     a["eval"]["dead"], a["eval"]["firefighter_deaths"],
                     n["occ"]["burnt"], a["occ"]["burnt"],
                     n["occ"]["scorched"], a["occ"]["scorched"],
                     n["occ"]["green"], a["occ"]["green"]))


def gateway(cells):
    hdr("IS SCORCHED GROUND THE ONLY DOOR INTO THE BLACK?  (arm none)")
    from collections import Counter
    entry, trans = Counter(), Counter()
    spells = 0
    for c in cells:
        r = one("none", c)
        if r is None:
            continue
        per = defaultdict(list)
        for row in r["fftrace"]:
            per[row["unit"]].append(row)
        for _u, rows in per.items():
            rows.sort(key=lambda x: x["step"])
            prev_cell = prev_g = None
            in_burnt = False
            for row in rows:
                cell, g = tuple(row["cell"]), row["ground"]
                if prev_cell is not None and cell != prev_cell:
                    trans[(prev_g, g)] += 1
                    if g == "burnt" and not in_burnt:
                        entry[prev_g] += 1
                        spells += 1
                if cell != prev_cell or prev_cell is None:
                    in_burnt = (g == "burnt")
                prev_cell, prev_g = cell, g
    print("  ground a unit stepped FROM on first reaching burnt ground"
          "  (%d spells)" % spells)
    for g, n in entry.most_common():
        print("    from %-10s %4d  (%.1f%%)" % (g, n, 100.0 * n / max(1, spells)))
    gs = ["green", "scorched", "burnt", "burning"]
    print("  full ground-to-ground firefighter step transition matrix")
    print("    %-10s %s" % ("from \\ to", "  ".join("%-9s" % g for g in gs)))
    for a in gs:
        print("    %-10s %s" % (a, "  ".join("%-9d" % trans[(a, b)] for b in gs)))


if __name__ == "__main__":
    provenance()
    c13 = outcome_table(BASE13, "13-RUN CANONICAL SAMPLE")
    r13 = summary(c13, "13-RUN CANONICAL SAMPLE")
    c23 = [c for c in ALL23
           if all(one(a, c) is not None for a in ARMS)]
    outcome_table(FRESH10, "10 EXTRA SEEDS (last_cell round)")
    r23 = summary(c23, "POOLED 23-RUN SAMPLE")
    death_diff(c23)
    named_cases()
    trajectory_divergence(c23)
    arm_identity(c23)
    displacement_on_changed(c23)
    gateway(c23)
    opportunity()
