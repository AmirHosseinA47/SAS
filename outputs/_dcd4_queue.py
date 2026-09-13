"""dcd4 round: emit the wave queue for outputs/_dcd4_pool.sh.

queue line: tag|repo|wind|roles|seed|extra harness args

ORDER IS DELIBERATE.
  1. PLATFORM/TREE CONTROLS FIRST - six committed dock-fix-round runs re-run on
     this interpreter at HEAD. They must be byte-identical to the committed JSON
     (every field but tag and wall_s) or the wave is not comparable with the 41:
     the FOV commits after 7f951cb touched serve_dashboard.py, which the harness
     takes _build_evaluation from, and that was only proven inert at mode 0.
  2. d4off + d4D per tuple, interleaved - the pair that decides the gate.
  3. d4A - the single-NW reference, last, so a lost tail costs the reference and
     never the decision.

Every arm is config-only on the live tree (no per-arm code), recorded with
--uav-actions like every dc*/df* arm. The --set strings are the dock-fix
round's dfzero / dfD / dfA lines verbatim (outputs/_df_queue.txt:1, :142, :96):
BASE_STATION_DOCK_FIX is NOT set, so it takes its shipped default 2 - which is
what makes d4D the dfD configuration, not dcD's fix-absent one.

usage: .venv/Scripts/python.exe outputs/_dcd4_queue.py > outputs/_dcd4_queue.txt
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dcd4_seeds import choose  # noqa: E402

REPO = "E:/Projects/SAS"
COMMON = "--uav-actions"
ARMED = "--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=2"
DIST = "--set UAV_RETURN_TO_BASE_RESERVE=0 --set BASE_STATION_RETURN_MARGIN=39.23"
TWO_DEPOT = "--set BASE_STATION_DEPOTS=9 --set BASE_STATION_SPAWN_SPLIT=2"

ARMS = {
    "d4off": "%s --set BASE_STATION_MODE=0" % COMMON,
    "d4D": "%s %s %s %s" % (COMMON, ARMED, DIST, TWO_DEPOT),
    "d4A": "%s %s" % (COMMON, ARMED),
}

# (control tag, the committed tag it must reproduce, extra of that arm, wind, roles, seed)
CONTROLS = [
    ("d4xD", "dfD", ARMS["d4D"], "east", "half", 303),     # moved dcD->dfD: exercises the dock fix
    ("d4xD", "dfD", ARMS["d4D"], "south", "half", 808),
    ("d4xA", "dfA", ARMS["d4A"], "south", "half", 606),    # moved dcA->dfA
    ("d4xA", "dfA", ARMS["d4A"], "east", "default", 202),  # legacy roles
    ("d4x0", "dfzero", ARMS["d4off"], "east", "half", 404),
    ("d4x0", "dfzero", ARMS["d4off"], "south", "half", 1010),
]


def lines():
    out = []
    for tag, _ref, extra, w, r, s in CONTROLS:
        out.append("%s|%s|%s|%s|%d|%s" % (tag, REPO, w, r, s, extra))
    tuples, _rej = choose()
    for combo, seed, _cell, _idx in tuples:
        w, r = combo.split("|")
        for tag in ("d4off", "d4D"):
            out.append("%s|%s|%s|%s|%d|%s" % (tag, REPO, w, r, seed, ARMS[tag]))
    for combo, seed, _cell, _idx in tuples:
        w, r = combo.split("|")
        out.append("%s|%s|%s|%s|%d|%s" % ("d4A", REPO, w, r, seed, ARMS["d4A"]))
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    for ln in lines():
        print(ln)
