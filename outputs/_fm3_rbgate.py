"""firemech round 2, Part 3: the route_blocked gate for the mission-gate arm. Read-only.

  1. the brief's reading: _ffr_rbcompare.py --new f3RBG --old ihrest. The G1 NEW set must
     stay exactly the four known at the shipped default (east/707, south/101, south/202,
     south/404) - any other seed is a new failure.
  2. the gate's own delta vs round 1's control shards fmgOFF (003ed91, feature off, whose
     source is a3a24f1's and which round 1 proved equal to the flip round's flgD field for
     field). BY CONSTRUCTION rescued and dead must be identical on all 18 seeds: the gate
     cannot act until every victim is rescued or dead. Firefighter deaths may differ.

-> outputs/_fm3_rbgate.txt
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
KNOWN_G1 = {("east", 707), ("south", 101), ("south", 202), ("south", 404)}
NEW = "f3RBG"
OLD = "fmgOFF"
OUT = []


def say(s=""):
    OUT.append(s)
    print(s)


def shards(tag):
    evals = {}
    for p in sorted(glob.glob(os.path.join(HERE, "_rblatch_camp2_%s?_D_*.json" % tag))):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        wind = "south" if p.endswith("_south.json") else "east"
        for ev in d.get("evals") or []:
            evals[(wind, int(ev["seed"]))] = ev
    return evals


def main():
    new, old = shards(NEW), shards(OLD)
    say("ROUTE_BLOCKED GATE - fire mechanic round 2 (mission gate, extinguish + suppression)")
    say("=" * 78)
    say("%s: %d seed records | %s: %d seed records" % (NEW, len(new), OLD, len(old)))
    if len(new) < 18:
        say("PENDING - only %d of 18 shard records present" % len(new))
        return 1
    say("")
    say("1. THE BRIEF'S G1 READING (_ffr_rbcompare.py --new <tag> --old ihrest)")
    for tag in (OLD, NEW):
        r = subprocess.run([PY, os.path.join(HERE, "_ffr_rbcompare.py"), "--new", tag, "--old", "ihrest"],
                           capture_output=True, text=True, cwd=os.path.dirname(HERE))
        text = (r.stdout or "") + (r.stderr or "")
        regr = set()
        for line in text.splitlines():
            for wind in ("east", "south"):
                if line.strip().startswith(wind + "/") and "->" in line and "G1" in line.upper():
                    pass
        say("   --- %s ---" % tag)
        for line in text.splitlines():
            if line.strip():
                say("   " + line.rstrip())
    say("")
    say("2. THE GATE'S OWN DELTA vs %s (round 1's control shards)" % OLD)
    keys = sorted(set(new) & set(old))
    say("   seeds compared: %d" % len(keys))
    bad = []
    changed = []
    tot_n = [0, 0, 0]
    tot_o = [0, 0, 0]
    for k in keys:
        a, b = new[k], old[k]
        an = (a["rescued"], a["dead"], a["firefighter_deaths"])
        bn = (b["rescued"], b["dead"], b["firefighter_deaths"])
        for i in range(3):
            tot_n[i] += an[i]
            tot_o[i] += bn[i]
        if an[:2] != bn[:2]:
            bad.append("%s/%s rescued/dead %s -> %s" % (k[0], k[1], bn[:2], an[:2]))
        if an != bn:
            changed.append("%s/%s r%+d d%+d ff%+d" % (k[0], k[1], an[0] - bn[0], an[1] - bn[1], an[2] - bn[2]))
    say("   totals rescued/dead/ff_deaths: %s %d/%d/%d   %s %d/%d/%d" % (
        NEW, tot_n[0], tot_n[1], tot_n[2], OLD, tot_o[0], tot_o[1], tot_o[2]))
    say("   seeds whose rescued or dead differ (MUST BE NONE - the gate cannot act before")
    say("   every victim is rescued or dead): %s" % (bad if bad else "NONE"))
    say("   seeds changed at all (firefighter deaths may move, post-terminal): %s"
        % (", ".join(changed) if changed else "none"))
    with open(os.path.join(HERE, "_fm3_rbgate.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
