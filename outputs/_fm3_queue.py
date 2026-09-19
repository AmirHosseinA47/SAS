"""firemech round 2, Part 3: the MINIMAL validation queue.

Scoped deliberately (the maintainer asked for the smallest wave that tests the gate and
the pre-registered predictions; Part 1 already eliminated the other arms):

  f3OFF   no --set                          KILL SWITCH: must equal fmOFF value for value
  f3GATE  E=1 K=1, gate at its default 1    THE GATE ARM: G2/G3/G4 are scored on it
  f3RES   E=1 K=1 MISSION_GATE=0            SEPARABILITY: must equal fmES value for value
                                            (round-1 policy is reproducible from the new code)

NOT RUN, and why:
  - a gated DRY arm: the deaths split is already attributed by the round-2 probes
    (f2GD vs f2GES), and the in-tree gate reproduces the probe gate where their
    predicates agree;
  - the full-configuration and firebreak gated arms: Part 1 measured them failing
    "vegetation rises" on the fresh set in both instruments;
  - a second rbgate control: round 1's fmgOFF shards were produced at 003ed91, whose
    source is a3a24f1's, so they are the control for f3RBG.

Samples: canonical 13 first, then fresh 10. f3RES is canonical only - an identity either
holds or it does not, and 13 seed-matched runs settle it.
rb18 extras: east/half 111-444, the four rbgate tuples that are not in canonical/fresh,
for f3OFF and f3GATE, so E1/E2 can be read on the same 18 seeds round 1 used.

Tags are new (prefix f3, 0 files under outputs/), and no tag is a prefix of another.
LF line endings (windows-bash-tool-gotchas).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _fm2_queue as Q  # noqa: E402

REPO = Q.REPO
E = Q.E
S = Q.S
GATE_OFF = "--set FF_FIREFIGHT_MISSION_GATE=0"

ARMS = {
    "f3OFF": [],
    "f3GATE": [E, S],
    "f3RES": [E, S, GATE_OFF],
}
CANONICAL_ARMS = ["f3OFF", "f3GATE", "f3RES"]
FRESH_ARMS = ["f3OFF", "f3GATE"]
RB_EXTRA = [("east", "half", s) for s in (111, 222, 333, 444)]
RB_EXTRA_ARMS = ["f3OFF", "f3GATE"]

# route_blocked gate: the same four shards round 1 ran, for the gate arm only.
RB_SHARDS = (("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
             ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505"))
RB_TAG = "f3RBG"


def line(tag, wind, roles, seed):
    return "%s|%s|%s|%s|%d|%s" % (tag, REPO, wind, roles, seed,
                                  " ".join(["--uav-actions"] + ARMS[tag]))


def main():
    tags = list(ARMS) + [RB_TAG]
    for a in tags:
        for b in tags:
            if a != b and b.startswith(a):
                raise SystemExit("tag %s is a prefix of %s" % (a, b))
    lines = []
    for tag in CANONICAL_ARMS:
        for w, r, s in Q.CANONICAL:
            lines.append(line(tag, w, r, s))
    for tag in FRESH_ARMS:
        for w, r, s in Q.FRESH:
            lines.append(line(tag, w, r, s))
    for tag in RB_EXTRA_ARMS:
        for w, r, s in RB_EXTRA:
            lines.append(line(tag, w, r, s))
    path = os.path.join(HERE, "_fm3_queue.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for ln in lines:
            f.write(ln + "\n")
    print("%d harness runs -> %s" % (len(lines), path))

    # outputs/_dcd4rb_pool.sh format: kind|tag|repo|wind|roles|seeds|steps|extra
    rb = []
    sets = " ".join(ARMS["f3GATE"])
    for sh, wind, seeds in RB_SHARDS:
        rb.append("rb|%s%s|%s|%s|half|%s|240|%s" % (RB_TAG, sh, REPO, wind, seeds, sets))
    path = os.path.join(HERE, "_fm3_rb_queue.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for ln in rb:
            f.write(ln + "\n")
    print("%d rb shards -> %s" % (len(rb), path))


if __name__ == "__main__":
    main()
