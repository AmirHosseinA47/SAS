"""Summarise / compare _ffr_harness.py waves.

usage:
  _ffr_analyze.py --base base1511                      # baseline mechanism report
  _ffr_analyze.py --base base1511 --feat ffabs         # seed-matched feature comparison
  _ffr_analyze.py --base base1511 --ctrl ffoff         # feature-off control: byte identity
All three may be combined. Reads outputs/_ffr_<tag>_<wind>_<half|def>_<seed>.json.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics

BASE = os.path.dirname(os.path.abspath(__file__))
COMBOS = (
    [("east", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("east", "default", s) for s in (101, 202, 303)]
)
METRICS = ("rescued", "dead", "unreachable", "never_detected", "geographically_isolated",
           "firefighter_deaths", "terminal_step")


def _name(tag, wind, roles, seed):
    rr = "def" if roles == "default" else roles
    return os.path.join(BASE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def load(tag):
    runs = {}
    for wind, roles, seed in COMBOS:
        p = _name(tag, wind, roles, seed)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            print("  MISSING %s" % p)
            continue
        with open(p, encoding="utf-8") as f:
            runs[(wind, roles, seed)] = json.load(f)
    return runs


def label(k):
    return "D/%s/%s %d" % (k[0], k[1], k[2])


def fmt_ts(v):
    return "-" if v is None else str(v)


def metrics_table(tag, runs):
    print("  %-22s %7s %5s %6s %6s %5s %8s %5s %5s" % (
        "combo", "rescued", "dead", "unrch", "nvdet", "ffdd", "terminal", "compl", "recyc"))
    tot = collections.Counter()
    for k in COMBOS:
        r = runs.get(k)
        if r is None:
            continue
        e = r["eval"]
        print("  %-22s %7d %5d %6d %6d %5d %8s %5d %5d" % (
            label(k), e["rescued"], e["dead"], e["unreachable"], e.get("never_detected", 0),
            e["firefighter_deaths"], fmt_ts(e["terminal_step"]),
            len(r["completions"]), len(r["recycles"])))
        for m in ("rescued", "dead", "unreachable", "never_detected", "firefighter_deaths"):
            tot[m] += int(e.get(m, 0) or 0)
        tot["completions"] += len(r["completions"])
        tot["recycles"] += len(r["recycles"])
    print("  %-22s %7d %5d %6d %6d %5d %8s %5d %5d" % (
        "TOTAL", tot["rescued"], tot["dead"], tot["unreachable"], tot["never_detected"],
        tot["firefighter_deaths"], "", tot["completions"], tot["recycles"]))
    return tot


def mechanism(runs, steps=240):
    recycles = [x for r in runs.values() for x in r["recycles"]]
    on_b = sum(1 for x in recycles if x["on_boundary"])
    print("  recycles: %d, landing on a boundary cell: %d (%s)" % (
        len(recycles), on_b, ("%.0f%%" % (100.0 * on_b / len(recycles))) if recycles else "n/a"))
    moved = sum(1 for x in recycles if x["pos_before"] != x["pos_after"])
    print("  recycles whose landing cell differs from the exit cell: %d" % moved)
    idle = idle_edge = absent = 0
    for r in runs.values():
        idle += r["idle"]["idle_steps"]
        idle_edge += r["idle"]["idle_edge_steps"]
        absent += r["idle"]["absent_steps"]
    print("  idle firefighter-steps: %d, of which on a grid edge: %d (%.1f%%); off-grid steps: %d" % (
        idle, idle_edge, (100.0 * idle_edge / idle) if idle else 0.0, absent))
    gaps = [g["gap"] for r in runs.values() for g in r["recycle_to_next_assign"]]
    have = [g for g in gaps if g is not None]
    never = sum(1 for g in gaps if g is None)
    if have:
        print("  recycle -> next successful assign of that unit: n=%d never-again=%d  min=%d median=%.0f max=%d  <=5 steps: %d" % (
            len(gaps), never, min(have), statistics.median(have), max(have), sum(1 for g in have if g <= 5)))
        print("    gaps: %s" % sorted(have))
        # the feature's direct exposure: a unit needed again within 5 steps of its recycle
        soon = []
        for r in runs.values():
            for g in r["recycle_to_next_assign"]:
                if g["gap"] is not None and g["gap"] <= 5:
                    reasons = [a["reason"] for a in r["assigns"] if a["ok"] and a["ff"] == g["ff"] and a["step"] == g["next_assign_step"]]
                    soon.append((r["wind"], r["roles"], r["seed"], g["ff"], g["recycle_step"], g["gap"], reasons))
        print("  re-dispatched within 5 steps of the recycle (would be delayed by the absence): %d" % len(soon))
        for item in soon:
            print("    D/%s/%s %d %s recycle@%d gap=%d reason=%s" % item)
    late = [(k, c["step"]) for k, r in runs.items() for c in r["completions"] if c["step"] > steps - 5]
    print("  completions in the last 5 steps (return would be truncated by the horizon): %d %s" % (len(late), late))
    # planner decisions taken with an empty pool
    empty = collections.Counter()
    for r in runs.values():
        for d in r["planner"]:
            if d["n_available"] == 0:
                empty[(d["reason"], d["action"])] += 1
    print("  planner decisions with NO available firefighter, by (reason -> action):")
    for (reason, action), n in sorted(empty.items()):
        print("    %-32s -> %-18s %d" % (reason, action, n))
    print("  rescue_failed events (mark_unreachable) by reason:")
    reasons = collections.Counter()
    for r in runs.values():
        for e in r["rescue_failed"]:
            reasons[e["reason"]] += 1
    for reason, n in sorted(reasons.items()):
        print("    %-40s %d" % (reason, n))


def first_divergence(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i + 1
    if len(a) != len(b):
        return n + 1
    return None


def compare(base, other, tag, strict_identity=False):
    print("  %-22s %-16s %-12s %-12s %-12s %-12s %-14s %s" % (
        "combo", "rescued", "dead", "unreach", "nvdet", "ff_deaths", "terminal", "fire-map"))
    diff_tot = collections.Counter()
    fire_ident = 0
    n = 0
    for k in COMBOS:
        a, b = base.get(k), other.get(k)
        if a is None or b is None:
            print("  %-22s MISSING" % label(k))
            continue
        n += 1
        ea, eb = a["eval"], b["eval"]
        div = first_divergence(a["fire_digests"], b["fire_digests"])
        if div is None:
            fire_ident += 1
        cells = []
        for m in ("rescued", "dead", "unreachable", "never_detected", "firefighter_deaths"):
            x, y = int(ea.get(m, 0) or 0), int(eb.get(m, 0) or 0)
            diff_tot[m] += y - x
            cells.append("%d -> %d%s" % (x, y, (" (%+d)" % (y - x)) if y != x else ""))
        ta, tb = ea["terminal_step"], eb["terminal_step"]
        tcell = "%s -> %s" % (fmt_ts(ta), fmt_ts(tb))
        print("  %-22s %-16s %-12s %-12s %-12s %-12s %-14s %s" % (
            label(k), cells[0], cells[1], cells[2], cells[3], cells[4], tcell,
            "identical" if div is None else ("DIVERGES@%d" % div)))
    print("  TOTAL delta: rescued %+d, dead %+d, unreachable %+d, never_detected %+d, ff_deaths %+d   fire-map identical on %d/%d runs" % (
        diff_tot["rescued"], diff_tot["dead"], diff_tot["unreachable"], diff_tot["never_detected"],
        diff_tot["firefighter_deaths"], fire_ident, n))
    if strict_identity:
        ident = 0
        for k in COMBOS:
            a, b = base.get(k), other.get(k)
            if a is None or b is None:
                continue
            same = (a["fire_digests"] == b["fire_digests"] and a["ff_steps"] == b["ff_steps"]
                    and a["stdout_sha256"] == b["stdout_sha256"] and a["eval"] == b["eval"]
                    and a["planner"] == b["planner"] and a["assigns"] == b["assigns"])
            ident += int(same)
            if not same:
                print("    NOT IDENTICAL: %s  fire=%s ff_steps=%s stdout=%s eval=%s planner=%s assigns=%s" % (
                    label(k), a["fire_digests"] == b["fire_digests"], a["ff_steps"] == b["ff_steps"],
                    a["stdout_sha256"] == b["stdout_sha256"], a["eval"] == b["eval"],
                    a["planner"] == b["planner"], a["assigns"] == b["assigns"]))
        print("  byte-identical (fire map, ff trajectories, stdout sha, eval, planner, assigns): %d/%d runs" % (ident, n))
    return diff_tot


def absence_report(runs, steps=240):
    removals = returns = 0
    durations = []
    placements = collections.Counter()
    per_run_ok = True
    print("  %-22s %8s %7s %9s %-24s %s" % ("combo", "removals", "returns", "pending", "durations", "verdict"))
    for k in COMBOS:
        r = runs.get(k)
        if r is None:
            continue
        log = r["absence_log"]
        rem = [x for x in log if x.get("event") == "removed"]
        ret = [x for x in log if x.get("event") == "returned"]
        removals += len(rem)
        returns += len(ret)
        durs = [int(x["duration"]) for x in ret]
        durations.extend(durs)
        for x in ret:
            placements[x.get("placement", "?")] += 1
        pending = r["absence_counters"].get("absent_now") or []
        # a unit still absent at the horizon is only legitimate if its return step lies beyond it
        trunc = [x for x in rem if int(x.get("return_step", 0) or 0) > steps and x.get("ff") in pending]
        genuine_missing = len(rem) - len(ret) - len(trunc)
        verdict = "OK" if len(ret) == len(rem) else ("HORIZON-TRUNCATED %d" % len(trunc) if genuine_missing == 0 else "FAIL: %d never returned" % genuine_missing)
        if genuine_missing != 0:
            per_run_ok = False
        print("  %-22s %8d %7d %9d %-24s %s" % (label(k), len(rem), len(ret), len(pending), durs, verdict))
    print("  TOTAL removals=%d returns=%d  returns==removals: %s" % (
        removals, returns, "YES" if removals == returns else "NO"))
    if durations:
        dist = collections.Counter(durations)
        print("  absence durations: %s  min=%d max=%d  all within [3,5]: %s" % (
            dict(sorted(dist.items())), min(durations), max(durations),
            "YES" if all(3 <= d <= 5 for d in durations) else "NO"))
    print("  return placement: %s" % dict(placements))
    return per_run_ok


def planner_delta(base, feat):
    print("  planner decisions with NO available firefighter (reason -> action), base vs feat:")
    cb, cf = collections.Counter(), collections.Counter()
    for r in base.values():
        for d in r["planner"]:
            if d["n_available"] == 0:
                cb[(d["reason"], d["action"])] += 1
    for r in feat.values():
        for d in r["planner"]:
            if d["n_available"] == 0:
                cf[(d["reason"], d["action"])] += 1
    for key in sorted(set(cb) | set(cf)):
        print("    %-32s -> %-18s %3d -> %3d" % (key[0], key[1], cb.get(key, 0), cf.get(key, 0)))
    held = sum(1 for r in feat.values() for d in r["planner"]
               if d["n_available"] == 0 and d["n_offgrid_alive"] > 0)
    print("  feat decisions taken while a unit was off-grid and none available: %d" % held)
    for k in COMBOS:
        r = feat.get(k)
        if r is None:
            continue
        for d in r["planner"]:
            if d["n_available"] == 0 and d["n_offgrid_alive"] > 0:
                print("    %s step %d reason=%s -> %s victim=%s" % (label(k), d["step"], d["reason"], d["action"], d["vid"]))


def _victim_outcome(run, vid):
    if any(c["victim"] == vid for c in run["completions"]):
        step = min(c["step"] for c in run["completions"] if c["victim"] == vid)
        return "rescued@%d" % step
    marks = [m for m in run["unreachable_marks"] if m["ok"] and m["vid"] == vid]
    if marks:
        return "unreachable@%d" % min(m["step"] for m in marks)
    return "dead/other" if run["eval"].get("all_terminal") else "unresolved"


def exposure_report(base, feat, steps=240):
    """Trace every baseline re-dispatch within 5 steps of a recycle into the feature arm."""
    print("  baseline re-dispatches within 5 steps of a recycle, traced into the feature arm:")
    print("  %-22s %-9s %-9s %-9s %-16s %-16s %s" % (
        "combo", "recycle", "base asg", "feat asg", "base outcome", "feat outcome", "victim"))
    for k in COMBOS:
        b, f = base.get(k), feat.get(k)
        if b is None or f is None:
            continue
        for g in b["recycle_to_next_assign"]:
            if g["gap"] is None or g["gap"] > 5:
                continue
            asg = [a for a in b["assigns"] if a["ok"] and a["ff"] == g["ff"] and a["step"] == g["next_assign_step"]]
            if not asg:
                continue
            vid = asg[0]["vid"]
            f_asg = [a["step"] for a in f["assigns"] if a["ok"] and a["vid"] == vid and a["step"] >= g["recycle_step"]]
            f_step = min(f_asg) if f_asg else None
            print("  %-22s %-9d %-9d %-9s %-16s %-16s %s" % (
                label(k), g["recycle_step"], g["next_assign_step"],
                ("%d (%+d)" % (f_step, f_step - g["next_assign_step"])) if f_step is not None else "never",
                _victim_outcome(b, vid), _victim_outcome(f, vid), vid))


def per_seed_explanations(base, feat):
    print("  seeds whose rescued/dead/ff_deaths changed, with both timelines:")
    any_change = False
    for k in COMBOS:
        b, f = base.get(k), feat.get(k)
        if b is None or f is None:
            continue
        eb, ef = b["eval"], f["eval"]
        if (eb["rescued"], eb["dead"], eb["firefighter_deaths"]) == (ef["rescued"], ef["dead"], ef["firefighter_deaths"]):
            continue
        any_change = True
        print("  %s  rescued %d->%d dead %d->%d ff_deaths %d->%d terminal %s->%s" % (
            label(k), eb["rescued"], ef["rescued"], eb["dead"], ef["dead"],
            eb["firefighter_deaths"], ef["firefighter_deaths"], fmt_ts(eb["terminal_step"]), fmt_ts(ef["terminal_step"])))
        for tag, r in (("base", b), ("feat", f)):
            asg = ["%s->%s@%d(%s)" % (a["ff"][-1:], a["vid"][-1:], a["step"], a["reason"][:4]) for a in r["assigns"] if a["ok"]]
            comp = ["%s@%d" % (c["victim"], c["step"]) for c in r["completions"]]
            dead = sorted({row[0] for st in r["ff_steps"] for row in st if row[5]})
            print("     %s assigns: %s" % (tag, " ".join(asg)))
            print("     %s completions: %s | ff dead: %s | unreachable marks: %s" % (
                tag, comp, dead, [(m["vid"], m["step"]) for m in r["unreachable_marks"] if m["ok"]]))
            if tag == "feat":
                print("     feat absence: %s" % ["%s %s@%d d=%s" % (e["event"][:3], e["ff"], e["step"], e.get("duration")) for e in r["absence_log"]])
    if not any_change:
        print("  (none)")


def reachability_report(runs):
    """Steps where every alive unit was off-grid (BFS start set empty because of the absence)."""
    empty_due_to_absence = 0
    empty_anyway = 0
    for r in runs.values():
        for st in r["ff_steps"]:
            present = sum(1 for row in st if not row[5] and row[1] is not None and not row[4])
            absent = sum(1 for row in st if not row[5] and row[1] is None)
            if present == 0 and absent > 0:
                empty_due_to_absence += 1
            elif present == 0:
                empty_anyway += 1
    print("  steps with no reachability start (all alive units off-grid): %d; empty for other reasons (all dead/exiting): %d" % (
        empty_due_to_absence, empty_anyway))
    geo = []
    for k, r in runs.items():
        windows = [(e["step"], e["return_step"]) for e in r["absence_log"] if e["event"] == "removed"]
        for e in r["unreachable_escape_log"]:
            if e.get("cause") != "geographically_isolated":
                continue
            s, streak = int(e["step"]), int(e.get("streak", 0) or 0)
            overlap = any(w0 <= s and w1 >= s - streak + 1 for w0, w1 in windows)
            geo.append((label(k), e["victim_id"], s, streak, overlap))
    print("  geographically_isolated marks: %d %s" % (len(geo), geo if geo else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="base1511")
    ap.add_argument("--feat", default=None)
    ap.add_argument("--ctrl", default=None)
    ap.add_argument("--steps", type=int, default=240)
    a = ap.parse_args()

    print("=" * 96)
    print("BASELINE %s" % a.base)
    print("=" * 96)
    base = load(a.base)
    metrics_table(a.base, base)
    print()
    mechanism(base, a.steps)

    if a.ctrl:
        print()
        print("=" * 96)
        print("CONTROL %s (feature source, feature OFF) vs BASELINE %s - expected byte-identical" % (a.ctrl, a.base))
        print("=" * 96)
        ctrl = load(a.ctrl)
        compare(base, ctrl, a.ctrl, strict_identity=True)

    if a.feat:
        print()
        print("=" * 96)
        print("FEATURE %s vs BASELINE %s (seed-matched)" % (a.feat, a.base))
        print("=" * 96)
        feat = load(a.feat)
        compare(base, feat, a.feat)
        print()
        print("  mechanism (feature):")
        absence_report(feat, a.steps)
        print()
        planner_delta(base, feat)
        print()
        exposure_report(base, feat, a.steps)
        print()
        per_seed_explanations(base, feat)
        print()
        reachability_report(feat)
        print()
        print("  feature metrics table:")
        metrics_table(a.feat, feat)
        print()
        print("  feature idle/recycle mechanism:")
        mechanism(feat, a.steps)


main()
