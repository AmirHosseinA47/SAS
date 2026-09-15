"""Fire mechanic round 1: the route_blocked gate, read-only. -> outputs/_firemech_rbgate.txt

1. gate-instrument parity: fmgOFF shards (003ed91, feature off) must equal flgD (the
   flip round's gate at the shipped default) seed for seed, record for record
2. the brief's comparison: _ffr_rbcompare.py --new <tag> --old ihrest for fmgOFF,
   fmgEFS, fmgFB. The known G1 regressions at the shipped default are exactly
   east/707, south/101, south/202, south/404 - any other seed is NEW
3. the feature's own delta: --new fmgEFS/fmgFB --old fmgOFF
4. the rbgate-18 harness side (fmOFF/fmEFS/fmF on the 18 tuples): drone exposure
   E1/E2 against drhD (3.55% / 2.42% at the shipped default) and outcomes
"""
from __future__ import annotations

import glob
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _dcd4_analyze as AN  # noqa: E402
import _firemech_analyze as FA  # noqa: E402

PY = sys.executable
KNOWN_G1 = {("east", 707), ("south", 101), ("south", 202), ("south", 404)}
OUT = []


def say(s=""):
    OUT.append(s)
    print(s)


def shards(tag):
    evals = {}
    records = {}
    for p in sorted(glob.glob(os.path.join(HERE, "_rblatch_camp2_%s?_D_*.json" % tag))):
        with open(p) as f:
            d = json.load(f)
        wind = "south" if p.endswith("_south.json") else "east"
        for ev in d.get("evals") or []:
            evals[(wind, int(ev["seed"]))] = ev
        records[os.path.basename(p)[len("_rblatch_camp2_"):]] = d
    return evals, records


def regressions(new, old):
    out = []
    for k, eo in sorted(old.items()):
        en = new.get(k)
        if en is not None and int(en.get("rescued") or 0) < int(eo.get("rescued") or 0):
            out.append((k[0], k[1], int(eo["rescued"]), int(en["rescued"])))
    return out


def main():
    say("ROUTE_BLOCKED GATE - fire mechanic round 1")
    say("=" * 78)
    ih, _ = shards("ihrest")
    fl, flrec = shards("flgD")
    for tag in ("fmgOFF", "fmgEFS", "fmgFB"):
        ev, _ = shards(tag)
        say("%s: %d seed records" % (tag, len(ev)))

    say("")
    say("1. GATE-INSTRUMENT PARITY  fmgOFF (003ed91, feature off) vs flgD (shipped default gate)")
    off, offrec = shards("fmgOFF")
    def nowall(e):
        return {k: v for k, v in (e or {}).items() if k != "wall_s"}

    same_ev = sum(1 for k in fl if k in off and nowall(off[k]) == nowall(fl[k]))
    say("   per-seed eval records identical (all fields but wall_s): %d/%d" % (same_ev, len(fl)))
    for name, d in sorted(offrec.items()):
        other = flrec.get(name.replace("fmgOFF", "flgD"))
        if other is None:
            say("   %s: no flgD counterpart" % name)
            continue
        diff = sorted(k for k in set(d) | set(other) if k not in ("tag", "evals") and d.get(k) != other.get(k))
        if [nowall(e) for e in d.get("evals") or []] != [nowall(e) for e in other.get("evals") or []]:
            diff.append("evals")
        say("   %-18s fields differing from flgD (excluding tag/wall): %s" % (name, diff or "none"))

    say("")
    say("2. THE BRIEF'S G1 READING vs ihrest (known at the shipped default: %s)" % sorted(KNOWN_G1))
    for tag in ("fmgOFF", "fmgEFS", "fmgFB"):
        ev, _ = shards(tag)
        reg = regressions(ev, ih)
        seeds = {(w, s) for w, s, _a, _b in reg}
        new = sorted(seeds - KNOWN_G1)
        gone = sorted(KNOWN_G1 - seeds)
        tot = [sum(int(e.get(k) or 0) for e in ev.values()) for k in ("rescued", "dead", "firefighter_deaths")]
        say("   %-7s G1 regressions on %d seeds: %s" % (tag, len(reg), ", ".join("%s/%d %d->%d" % r for r in reg)))
        say("           NEW beyond the known four: %s   known four no longer regressing: %s" % (new or "none", gone or "none"))
        say("           totals rescued/dead/ff_deaths %d/%d/%d" % tuple(tot))

    say("")
    say("3. THE FEATURE'S OWN DELTA ON THE 18 GATE SEEDS (vs fmgOFF)")
    for tag in ("fmgEFS", "fmgFB"):
        ev, _ = shards(tag)
        rows = []
        for k in sorted(off):
            a, b = off[k], ev.get(k)
            if b is None:
                continue
            da = tuple(int(b.get(x) or 0) - int(a.get(x) or 0) for x in ("rescued", "dead", "firefighter_deaths"))
            if any(da):
                rows.append("%s/%d r%+d d%+d ff%+d" % ((k[0], k[1]) + da))
        say("   %-7s seeds changed: %d  %s" % (tag, len(rows), "; ".join(rows)))

    for new, old in (("fmgOFF", "ihrest"), ("fmgEFS", "ihrest"), ("fmgFB", "ihrest"), ("fmgEFS", "fmgOFF"), ("fmgFB", "fmgOFF")):
        say("")
        say("-" * 78)
        say("_ffr_rbcompare.py --new %s --old %s" % (new, old))
        say("-" * 78)
        r = subprocess.run([PY, os.path.join(HERE, "_ffr_rbcompare.py"), "--new", new, "--old", old],
                           capture_output=True, text=True, cwd=os.path.dirname(HERE))
        for line in (r.stdout + r.stderr).splitlines():
            say("  " + line)

    say("")
    say("4. RBGATE-18 HARNESS SIDE")
    rb = FA.RB18
    missing = [(tag, t) for tag in ("fmOFF", "fmEFS", "fmF") for t in rb if FA.load(tag, t) is None]
    say("   missing harness runs: %s" % (missing or "none"))
    same = 0
    for t in rb:
        a = FA.load("fmOFF", t)
        b = json.load(open(os.path.join(HERE, "_ffr_drhD_%s_%s_%d.json" % t))) if os.path.exists(
            os.path.join(HERE, "_ffr_drhD_%s_%s_%d.json" % t)) else None
        if a is not None and b is not None and not FA.diff_keys(a, b, ("tag", "repo", "wall_s", "params", "extra_params")):
            same += 1
    say("   fmOFF == drhD (every field but tag/repo/wall_s/params/extra_params): %d/%d" % (same, len(rb)))
    for tag in ("fmOFF", "fmEFS", "fmF"):
        S = [FA.run_summary(FA.load(tag, t), FA.load("fmOFF", t) if tag != "fmOFF" else None)
             for t in rb if FA.load(tag, t) is not None]
        say("   %-6s runs %2d  rescued %d dead %d ff_deaths %d nevdet %d | E1 %s  E2 %s | deaths engaged %d streak %d preempted %d" % (
            tag, len(S), sum(s["rescued"] for s in S), sum(s["dead"] for s in S), sum(s["ffd"] for s in S),
            sum(s["nd"] for s in S), AN.pct(sum(s["e1n"] for s in S), sum(s["e1d"] for s in S)),
            AN.pct(sum(s["e2n"] for s in S), sum(s["e2d"] for s in S)),
            sum(1 for s in S for x in s["deaths"] if x["engaged"]),
            sum(1 for s in S for x in s["deaths"] if x["streak_engaged"]),
            sum(1 for s in S for x in s["deaths"] if x["preempted"])))
    with open(os.path.join(HERE, "_firemech_rbgate.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
