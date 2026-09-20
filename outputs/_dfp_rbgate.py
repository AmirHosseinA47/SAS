"""Non-burnable-depot round: the route_blocked gate, both readings, to a file.

  1. THE BRIEF'S READING - _ffr_rbcompare.py --new <tag> --old ihrest. The G1 NEW
     set must stay exactly the four known at the shipped default (east/707,
     south/101, south/202, south/404). Run for the ARMED arm AND for this round's
     own control arm, because "no NEW failure" only means something if the control
     produces the same four - i.e. if they are carried, not caused.
  2. THE STRONGER READING - --new dfpRBG --old dfpRBC: the feature against the
     KILL SWITCH AT THE SAME COMMIT, same 18 seeds, same pins. Against ihrest the
     four known are present in both arms and can never show up as regressions;
     against dfpRBC they can.

-> outputs/_dfp_rbgate.txt
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
KNOWN = {("east", 707), ("south", 101), ("south", 202), ("south", 404)}
OUT = []


def say(s=""):
    OUT.append(str(s))
    print(s)


def run(new, old):
    r = subprocess.run([PY, os.path.join(HERE, "_ffr_rbcompare.py"), "--new", new, "--old", old],
                       capture_output=True, text=True, cwd=os.path.dirname(HERE))
    return (r.stdout or "") + (r.stderr or "")


def regressions(text):
    out = set()
    for line in text.splitlines():
        t = line.strip()
        if t.startswith("regression: D/"):
            wind = t.split("D/")[1].split()[0]
            seed = int(t.split("seed")[1].split()[0])
            out.add((wind, seed))
    return out


def main():
    say("=" * 96)
    say("ROUTE_BLOCKED GATE - non-burnable depots")
    say("=" * 96)
    for tag, what in (("dfpRBC", "the KILL SWITCH at this commit (the control arm)"),
                      ("dfpRBG", "the FEATURE")):
        text = run(tag, "ihrest")
        got = regressions(text)
        say("")
        say("-" * 96)
        say("1. %s vs ihrest   (%s)" % (tag, what))
        say("-" * 96)
        for line in text.splitlines():
            if line.strip():
                say("   " + line.rstrip())
        say("   G1 regression set: %s" % sorted(got))
        say("   == the four known: %s" % (got == KNOWN))
    text = run("dfpRBG", "dfpRBC")
    got = regressions(text)
    say("")
    say("-" * 96)
    say("2. dfpRBG vs dfpRBC   (feature vs kill switch, SAME commit, same 18 seeds)")
    say("-" * 96)
    for line in text.splitlines():
        if line.strip():
            say("   " + line.rstrip())
    say("   G1 regression set: %s   (empty is the strongest possible result)" % sorted(got))
    with open(os.path.join(HERE, "_dfp_rbgate.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
