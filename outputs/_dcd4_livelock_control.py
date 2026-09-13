"""dcd4 round: synthetic POSITIVE CONTROLS for the livelock detectors.

The recorded deadlocks (dcB east/half/808, dfm2ref's five) are FREEZES. A freeze
collapses to one cell, so CYCLE, REVISIT and OSCILLATION cannot fire on it by
construction - only FREEZE and DISTANCE-PROGRESS can. The prereg's "the new
checks must fire on the recorded deadlock" is therefore right for PROGRESS and
wrong for REVISIT. The movement detectors need a movement failure to prove they
see one, and none has ever been recorded in this project. So they are fed one:
the exact livelock the dock-fix round replayed for the rejected minimal fix,
(3,44) -> (4,44) -> (3,44) ... against berth (4,45) (memory: dockfix-livelock-gate),
plus a freeze, a 4-cell loop and a clean approach as the negative.

Uses _dcd4_analyze._leg_metrics itself - the function every armed run went
through - not a re-implementation.

usage: .venv/Scripts/python.exe outputs/_dcd4_livelock_control.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _dcd4_analyze as A  # noqa: E402

NW = frozenset((x, y) for x in range(0, 5) for y in range(45, 50))
GEO = {"foot": [NW]}
TRIP = {"target_berth": [4, 45], "target_depot": 0, "arrival_step": None}

CASES = [
    # name, leg, which detectors MUST fire, which must NOT
    ("ping-pong livelock (3,44)<->(4,44), 40 frames",
     [(3, 44) if i % 2 == 0 else (4, 44) for i in range(40)],
     {"cycle", "revisit", "osc", "prog_out"}, {"freeze3"}),
    ("pure freeze at (4,44), 38 frames (the dcB 808 shape)",
     [(10, 44 - 0)] + [(9, 44), (8, 44), (7, 44), (6, 44), (5, 44)] + [(4, 44)] * 38,
     {"freeze3", "prog_out"}, {"cycle", "revisit", "osc"}),
    ("4-cell loop outside the depot, 40 frames",
     [[(6, 42), (7, 42), (7, 43), (6, 43)][i % 4] for i in range(40)],
     {"cycle", "revisit", "prog_out"}, {"osc", "freeze3"}),
    ("clean monotone approach, 20 frames",
     [(24 - i, 45) if i <= 20 else (4, 45) for i in range(20)],
     set(), {"cycle", "revisit", "osc", "prog_out", "prog_in", "freeze3"}),
]


def fired(m):
    out = set()
    if m["freeze"] >= 3:
        out.add("freeze3")
    for k in ("cycle", "revisit", "osc"):
        if m[k] is not None:
            out.add(k)
    if m["prog_out"]:
        out.add("prog_out")
    if m["prog_in"]:
        out.add("prog_in")
    return out


def main():
    sys.stdout.reconfigure(newline="\n")
    bad = 0
    print("LIVELOCK DETECTOR POSITIVE CONTROLS (REVISIT_COUNT=%d, OSC_WIN=%d, PROG_WIN=%d)"
          % (A.REVISIT_COUNT, A.OSC_WIN, A.PROG_WIN))
    for name, leg, must, must_not in CASES:
        m = A._leg_metrics("synthetic", 100, leg, TRIP, GEO, 10 ** 6)
        f = fired(m)
        ok = must <= f and not (must_not & f)
        bad += not ok
        print("%s  %s\n      fired=%s  must=%s  must_not=%s  freeze=%d nd_stretch=%d prog_out=%d prog_in=%d"
              % ("PASS" if ok else "FAIL", name, sorted(f), sorted(must), sorted(must_not),
                 m["freeze"], m["nd_stretch"], m["prog_out"], m["prog_in"]))
    print("CONTROLS %d/%d PASS" % (len(CASES) - bad, len(CASES)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
