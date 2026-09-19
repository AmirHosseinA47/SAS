"""firemech round 2, Part 3: score the gate arm against the pre-registered predictions.

Read-only. Per-run metrics come from outputs/_firemech_analyze.run_summary (round-1
definitions: intact = 2500 - ever_burned - cleared, E1/E2 via _dcd4_analyze, the death
classification), so nothing here re-implements a definition round 1 already fixed.

  G1  f3OFF  == fmOFF   value identity, 23/23        (kill switch)
      f3RES  == fmES    value identity, canonical 13 (separability: gate 0 == round 1)
  G2  rescued does not decrease vs fmOFF, per sample
  G3  untouched vegetation rises, per sample, against the pre-registered numbers
  G4  firefighter deaths do not increase; every death classified
  G5  handled by outputs/_fm3_rbgate.py (the shards)
  G6  handled by the pytest run
  Plus: the gate opening step vs terminal_step, engaged rows and writes before/after it,
  E1/E2 on canonical+fresh and on the rbgate 18, and the cross-check against the round-2
  probe arm f2GES (same policy, measured out of tree with the looser predicate).

usage: _fm3_analyze.py [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _firemech_analyze as FA  # noqa: E402

CANON = FA.CANONICAL
FRESH = FA.FRESH
RB18 = FA.RB18
EXCLUDE = ("tag", "repo", "wall_s")
# Pre-registered in outputs/firemech2_part1.txt section 0 (strict-predicate projection
# of the probe arm f2GES), frozen before this wave ran.
PREREG = {
    "canonical": {"intact": 1269, "dirs": (8, 1, 4), "ffd": (6, 4), "rescued": 39, "dead": 10},
    "fresh": {"intact": 639, "dirs": (5, 0, 5), "ffd": (4, 3), "rescued": 29, "dead": 6},
}
# Runs where the strict predicate never opens but the probe's looser one did (or where
# neither opens): the cross-check expects f3GATE == fmOFF on these.
STRICT_CLOSED = {("east", "default", 101), ("east", "half", 707),
                 ("south", "half", 606), ("south", "half", 1010),
                 ("south", "half", 101), ("south", "half", 202), ("south", "half", 808)}
OUT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def rr(r):
    return "def" if r == "default" else r


def name(tag, t):
    return "%s_%s_%s_%d" % (tag, t[0], rr(t[1]), t[2])


def load(tag, t):
    p = os.path.join(HERE, "_ffr_%s.json" % name(tag, t))
    if not os.path.exists(p) or os.path.exists(p + ".tmp"):
        return None
    log = os.path.join(HERE, "_ffr_logs", name(tag, t) + ".out")
    if tag.startswith("f3") and (not os.path.exists(log)
                                 or "seed=" not in open(log, encoding="utf-8", errors="replace").read()):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def victims(d):
    return {v: st for v, _p, st in d["victim_steps"][-1]}


def identity(new, old, tuples, label):
    ok = miss = 0
    bad = []
    for t in tuples:
        a, b = load(new, t), load(old, t)
        if a is None or b is None:
            miss += 1
            continue
        diff = sorted(k for k in set(a) | set(b) if k not in EXCLUDE and a.get(k) != b.get(k))
        # params/extra_params legitimately differ when the arms pass different --set
        real = [k for k in diff if k not in ("params", "extra_params")]
        if real:
            bad.append("%s: %s" % (FA.label(t), ",".join(real)))
        else:
            ok += 1
    say("  %-28s %s %d/%d identical%s" % (
        label, "PASS" if ok == len(tuples) else "FAIL", ok, len(tuples),
        ("  pending %d" % miss) if miss else ""))
    for b in bad[:8]:
        say("      DIFF", b)
    return ok == len(tuples)


def gate_open_step(d):
    rows = d.get("firefight_log") or []
    return rows[0]["step"] if rows else None


def block(sample, tuples):
    say("")
    say("=" * 108)
    say("SAMPLE %s (%d tuples)" % (sample, len(tuples)))
    say("=" * 108)
    have = [t for t in tuples if load("f3GATE", t) and load("fmOFF", t)]
    if not have:
        say("  no complete pairs yet")
        return
    tot = {k: 0 for k in ("r", "d", "f", "i", "rr", "rd", "rf", "ri", "e1n", "e1d", "e2n", "e2d",
                          "re1n", "re1d", "re2n", "re2d", "rows", "ext", "pre")}
    up = dn = eq = 0
    vflips = []
    deaths = []
    say("  %-16s %-12s %-12s %8s %8s  %s" % ("run", "f3GATE r/d/ffd", "fmOFF r/d/ffd",
                                             "intact d", "gate@", "engaged rows (writes)"))
    for t in have:
        a, o = load("f3GATE", t), load("fmOFF", t)
        A, O = FA.run_summary(a, o), FA.run_summary(o, o)
        di = A["intact"] - O["intact"]
        up += di > 0
        dn += di < 0
        eq += di == 0
        for k, s in (("r", "rescued"), ("d", "dead"), ("f", "ffd"), ("i", "intact")):
            tot[k] += A[s]
            tot["r" + k] += O[s]
        for k in ("e1n", "e1d", "e2n", "e2d"):
            tot[k] += A[k]
            tot["r" + k] += O[k]
        rows = a.get("firefight_log") or []
        eng = sum(1 for x in rows if x["engaged"])
        wr = sum(1 for x in rows if x.get("wrote"))
        tot["rows"] += eng
        tot["ext"] += wr
        g = gate_open_step(a)
        term = o.get("terminal_step")
        pre = sum(1 for x in rows if term is not None and x["step"] <= term)
        tot["pre"] += pre
        if victims(a) != victims(o):
            vflips.append("%s %s -> %s" % (FA.label(t), victims(o), victims(a)))
        say("  %-16s %-12s %-12s %+8d %8s  %d (%d)%s" % (
            FA.label(t), "%d/%d/%d" % (A["rescued"], A["dead"], A["ffd"]),
            "%d/%d/%d" % (O["rescued"], O["dead"], O["ffd"]), di,
            ("%s/T%s" % (g, term)) if g else ("none/T%s" % term), eng, wr,
            "  PRE-TERMINAL ROWS %d" % pre if pre else ""))
        for arm, tag in ((a, "f3GATE"), (o, "fmOFF")):
            for i, row in enumerate(arm["ff_steps"]):
                for ff, pos, st, asg, ex, dead in row:
                    if dead and not any(x[0] == ff and x[5] for x in arm["ff_steps"][i - 1]) if i else dead:
                        deaths.append((FA.label(t), tag, ff, i + 1, tuple(pos) if pos else None))
    say("")
    say("  TOTALS  f3GATE %d/%d/%d   fmOFF %d/%d/%d   intact %+d (up/down/unchanged %d/%d/%d)" % (
        tot["r"], tot["d"], tot["f"], tot["rr"], tot["rd"], tot["rf"],
        tot["i"] - tot["ri"], up, dn, eq))
    say("  ENGAGED rows %d, writes %d, rows at or before terminal_step %d (must be 0)" % (
        tot["rows"], tot["ext"], tot["pre"]))
    say("  E1 %d/%d = %.2f%% vs fmOFF %.2f%%   E2 %d/%d = %.2f%% vs fmOFF %.2f%%" % (
        tot["e1n"], tot["e1d"], 100.0 * tot["e1n"] / max(1, tot["e1d"]),
        100.0 * tot["re1n"] / max(1, tot["re1d"]),
        tot["e2n"], tot["e2d"], 100.0 * tot["e2n"] / max(1, tot["e2d"]),
        100.0 * tot["re2n"] / max(1, tot["re2d"])))
    say("  victim final-status flips vs fmOFF: %s" % (vflips if vflips else "NONE (G2 holds per victim)"))
    pr = PREREG.get(sample)
    if pr and len(have) == len(tuples):
        say("")
        say("  PRE-REGISTERED (outputs/firemech2_part1.txt section 0, frozen before this wave)")
        say("    intact   predicted %+d (%d/%d/%d)   measured %+d (%d/%d/%d)   %s" % (
            pr["intact"], pr["dirs"][0], pr["dirs"][1], pr["dirs"][2],
            tot["i"] - tot["ri"], up, dn, eq,
            "MATCH" if (tot["i"] - tot["ri"] == pr["intact"] and (up, dn, eq) == pr["dirs"]) else "DIFFERS"))
        say("    rescued  predicted %d (= fmOFF)     measured %d (fmOFF %d)   %s" % (
            pr["rescued"], tot["r"], tot["rr"], "MATCH" if tot["r"] == tot["rr"] == pr["rescued"] else "DIFFERS"))
        say("    dead     predicted %d (= fmOFF)     measured %d (fmOFF %d)   %s" % (
            pr["dead"], tot["d"], tot["rd"], "MATCH" if tot["d"] == tot["rd"] == pr["dead"] else "DIFFERS"))
        say("    ffd      predicted %d -> %d          measured %d -> %d   %s" % (
            pr["ffd"][0], pr["ffd"][1], tot["rf"], tot["f"],
            "MATCH" if (tot["rf"], tot["f"]) == pr["ffd"] else "DIFFERS"))


def crosscheck():
    say("")
    say("=" * 108)
    say("CROSS-CHECK: the in-tree gate vs the round-2 probe arm f2GES (same policy, looser predicate)")
    say("=" * 108)
    same = diff = closed_ok = closed_bad = pending = 0
    for t in CANON + FRESH:
        a = load("f3GATE", t)
        if a is None:
            pending += 1
            continue
        if t in STRICT_CLOSED:
            o = load("fmOFF", t)
            d = sorted(k for k in set(a) | set(o)
                       if k not in EXCLUDE + ("params", "extra_params") and a.get(k) != o.get(k))
            if d:
                closed_bad += 1
                say("    %-16s strict-closed but DIFFERS from fmOFF: %s" % (FA.label(t), ",".join(d)))
            else:
                closed_ok += 1
        else:
            p = load("f2GES", t)
            if p is None:
                pending += 1
                continue
            d = sorted(k for k in set(a) | set(p)
                       if k not in EXCLUDE + ("params", "extra_params", "fm2p") and a.get(k) != p.get(k))
            if d:
                diff += 1
                say("    %-16s DIFFERS from f2GES: %s" % (FA.label(t), ",".join(d)))
            else:
                same += 1
    say("  == f2GES on %d runs where both predicates open at the same step" % same)
    say("  == fmOFF on %d of the %d runs the strict predicate never opens" % (closed_ok, closed_ok + closed_bad))
    say("  differences %d, pending %d" % (diff + closed_bad, pending))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    say("FM3 VALIDATION - the mission gate (strict predicate) with extinguish + suppression")
    say("arms: f3OFF (kill switch), f3GATE (E=1 K=1, gate default 1), f3RES (E=1 K=1 gate=0)")
    say("")
    say("G1 IDENTITIES (every recorded value except tag/repo/wall_s; params/extra_params carry the arm's own switches)")
    identity("f3OFF", "fmOFF", CANON + FRESH, "f3OFF == fmOFF (kill switch)")
    identity("f3RES", "fmES", CANON, "f3RES == fmES (gate 0 == round 1)")
    for sample, tuples in (("canonical", CANON), ("fresh", FRESH), ("both", CANON + FRESH)):
        block(sample, tuples)
    crosscheck()
    say("")
    say("RBGATE 18 (E1/E2 on the same seeds round 1 used)")
    have = [t for t in RB18 if load("f3GATE", t) and load("fmOFF", t)]
    if len(have) == len(RB18):
        n = {k: 0 for k in ("e1n", "e1d", "e2n", "e2d", "re1n", "re1d", "re2n", "re2d")}
        for t in have:
            A = FA.run_summary(load("f3GATE", t), load("fmOFF", t))
            O = FA.run_summary(load("fmOFF", t), load("fmOFF", t))
            for k in ("e1n", "e1d", "e2n", "e2d"):
                n[k] += A[k]
                n["r" + k] += O[k]
        say("  f3GATE E1 %.2f%% E2 %.2f%%   fmOFF E1 %.2f%% E2 %.2f%%  (round 1 control: 3.55%% / 2.42%%)" % (
            100.0 * n["e1n"] / n["e1d"], 100.0 * n["e2n"] / n["e2d"],
            100.0 * n["re1n"] / n["re1d"], 100.0 * n["re2n"] / n["re2d"]))
    else:
        say("  pending (%d of %d tuples)" % (len(have), len(RB18)))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(OUT) + "\n")
        print("\nwritten %s" % a.out)


if __name__ == "__main__":
    main()
