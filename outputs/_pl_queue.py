"""Planner round: write the queue file of one Part 3 wave (outputs/planner_part1.txt section 7).

usage: python outputs/_pl_queue.py <wave> [--plq wind/roles/seed]   -> outputs/_pl_<wave>_queue.txt
waves (the ORDER of section 7, with plRB moved beside plRC/plRG because it is never dropped -
the maintainer's ruling of 2026-09-28 - and a never-dropped arm runs before any droppable one):
  q1  7.1 identity: plB C13 + plD (east/half/101, south/half/101) on the pinned dfbfbe7
      worktree through the sidecar; plC C13 (sidecar); plP east/half/101 (plain); plZ x3
      (plain, --set GLOBAL_PLANNER_MODE=0); plJ x3 (sidecar, --set GLOBAL_PLANNER_MODE=0.5)
  q2  plG C13 (sidecar, --set GLOBAL_PLANNER_MODE=1)
  qQ  plQ (plain, mode 1) on the tuple given by --plq (chosen by _pl_analyze.py plq)
  q3  plC N30 + plG N30 (sidecar)
  q4  plC RB7 + plG RB7 (sidecar); rbgate plRC (branch, mode 0), plRG (branch, mode 1),
      plRB (the dfbfbe7 worktree) - 4 shards each
  q5  the CRN pair plKC / plKG on N30 (CRN sidecar, --set FM2P_CRN=1)
  q6  plF (FF_FIREFIGHT_EXTINGUISH=0, FF_FIREFIGHT_FIREBREAK=0) and plS (BASE_STATION_MODE=0), N30
N30 is read from the frozen outputs/_cl_seeds.txt (never choose()): its content, LF-normalised
(the Windows checkout holds it with CRLF; the committed blob is LF), must hash to the
pre-registered e6fe0698...; anything else STOPS.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = "E:/Projects/SAS"
BASE = "E:/Projects/SAS_wt/basedfbfbe7"
N30_SHA = "e6fe0698f794549729e4fdd40ef6d41722a171c1bcd9289b3a17ce794f01b81f"
EXTRA = "--uav-actions --set BATCH_SIZE=360"
STEPS = 360
C13 = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("east", "default", s) for s in (101, 202, 303)])
RB7 = [("east", "half", s) for s in (111, 222, 333, 444, 606, 808, 909)]
RB_SHARDS = [("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
             ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505")]
ZTUPLES = [("east", "half", 101), ("south", "half", 101), ("east", "default", 101)]


def n30():
    raw = open(os.path.join(HERE, "_cl_seeds.txt"), "rb").read()
    digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    if digest != N30_SHA:
        raise SystemExit("N30 STOP: outputs/_cl_seeds.txt (LF-normalised) hashes to %s, not %s" % (digest, N30_SHA))
    out = []
    for line in raw.decode("utf-8").splitlines():
        m = re.match(r"^(east|south)\|(half|default)\s+seed (\d+)", line)
        if m:
            out.append((m.group(1), m.group(2), int(m.group(3))))
    if len(out) != 30:
        raise SystemExit("N30 STOP: %d tuples" % len(out))
    return out


def ff(kind, tag, repo, tup, sets=""):
    w, r, s = tup
    extra = EXTRA + ("" if not sets else " " + sets)
    return "%s|%s|%s|%s|%s|%d|%d|%s" % (kind, tag, repo, w, r, s, STEPS, extra)


def rb(tag, repo, sets=""):
    return ["rb|%s%s|%s|%s|half|%s|240|%s" % (tag, sh, repo, w, seeds, sets) for sh, w, seeds in RB_SHARDS]


def wave(name, plq=None):
    G1 = "--set GLOBAL_PLANNER_MODE=1"
    if name == "q1":
        lines = [ff("fo", "plB", BASE, t) for t in C13]
        lines += [ff("fo", "plD", BASE, t) for t in (("east", "half", 101), ("south", "half", 101))]
        lines += [ff("fo", "plC", MAIN, t) for t in C13]
        lines += [ff("ff", "plP", MAIN, ("east", "half", 101))]
        lines += [ff("ff", "plZ", MAIN, t, "--set GLOBAL_PLANNER_MODE=0") for t in ZTUPLES]
        lines += [ff("fo", "plJ", MAIN, t, "--set GLOBAL_PLANNER_MODE=0.5") for t in ZTUPLES]
    elif name == "q2":
        lines = [ff("fo", "plG", MAIN, t, G1) for t in C13]
    elif name == "qQ":
        w, r, s = plq.split("/")
        lines = [ff("ff", "plQ", MAIN, (w, r, int(s)), G1)]
    elif name == "q3":
        N = n30()
        lines = [ff("fo", "plC", MAIN, t) for t in N] + [ff("fo", "plG", MAIN, t, G1) for t in N]
    elif name == "q4":
        lines = [ff("fo", "plC", MAIN, t) for t in RB7] + [ff("fo", "plG", MAIN, t, G1) for t in RB7]
        lines += rb("plRC", MAIN) + rb("plRG", MAIN, G1) + rb("plRB", BASE)
    elif name == "q5":
        N = n30()
        crn = "--set FM2P_CRN=1"
        lines = [ff("fc", "plKC", MAIN, t, crn) for t in N] + [ff("fc", "plKG", MAIN, t, G1 + " " + crn) for t in N]
    elif name == "q6":
        N = n30()
        lines = [ff("fo", "plF", MAIN, t, "--set FF_FIREFIGHT_EXTINGUISH=0 --set FF_FIREFIGHT_FIREBREAK=0") for t in N]
        lines += [ff("fo", "plS", MAIN, t, "--set BASE_STATION_MODE=0") for t in N]
    else:
        raise SystemExit("unknown wave %r" % name)
    return lines


if __name__ == "__main__":
    name = sys.argv[1]
    plq = sys.argv[sys.argv.index("--plq") + 1] if "--plq" in sys.argv else None
    lines = wave(name, plq)
    path = os.path.join(HERE, "_pl_%s_queue.txt" % name)
    if os.path.exists(path):
        raise SystemExit("REFUSED: %s exists" % path)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# planner round wave %s (outputs/_pl_queue.py); kind|tag|repo|wind|roles|seeds|steps|extra\n" % name)
        for ln in lines:
            f.write(ln + "\n")
    print("%s: %d lines -> %s" % (name, len(lines), path))
