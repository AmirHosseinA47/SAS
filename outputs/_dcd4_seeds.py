"""dcd4 round: choose the FOURTH independent seed set, reproducibly, before any run.

The rule is fixed here, in code, and nothing about it looks at a simulation
outcome. Run it again and it prints the same set.

  1. Candidates come from SHA-256 in counter mode over a declared label, so the
     seeds are not a hand-picked family (the 101 x k and 111 x k families are
     both already used, and the fresh-10 "never used" claim turned out wrong
     for 8 of 10 tuples - dcd4_report.txt records that).
     seed_i = first 4 bytes of sha256(LABEL % i), big-endian, & 0x7FFFFFFF.
  2. A candidate is REJECTED only if
       (a) it, or its negative, is a seed used anywhere in this project
           (random.Random(-n) == random.Random(n), so the negative aliases); or
       (b) its ignition cell equals the ignition cell of any seed in the
           canonical 13, fresh 10 or rbgate 18, or of a seed already accepted
           into this set.
     No other screen. In particular a degenerate no-spread world (like
     D/east/707) is NOT excluded: that cannot be known without running the
     fire, and excluding it afterwards would be selection on outcome.
  3. Accepted seeds are assigned IN ORDER: the first 13 to east/half, the next
     13 to south/half, the last 4 to east/default. One seed per tuple, never
     reused across winds - the same seed under east and south shares its
     ignition cell and all 2,500 fuel draws, so a paired-wind design gives N
     independent worlds for 2N runs. This one gives 30 for 30.

Composition mirrors canonical+fresh (20 half on both winds + 3 east/default,
13%): 26 half + 4 east/default (13%).

Ignition is reproduced exactly as wildfire_model.set_fire_agents draws it: the
first two draws of random.Random(seed), randint(10, 39) for x then y, 50x50.

usage: .venv/Scripts/python.exe outputs/_dcd4_seeds.py [--queue]
"""
import hashlib
import os
import random
import re
import sys

LABEL = "SAS dcd4 fourth independent seed set, declared 2026-09-13, candidate %d"
N_EAST_HALF, N_SOUTH_HALF, N_EAST_DEFAULT = 13, 13, 4

# Every seed of the three samples this set must be independent of.
PRIOR_SAMPLE_SEEDS = [101, 202, 303, 404, 505, 606, 707, 808, 909, 1010, 111, 222, 333, 444]

# Every distinct seed value found anywhere in outputs/ by the seed-history
# audit (file names, JSON seed fields, report seed lists), plus test seeds.
USED_SEEDS = set(PRIOR_SAMPLE_SEEDS) | {
    7, 42,
    616, 727, 838, 949, 1061,
    1111, 1212, 1313, 1414, 1515, 1616, 1717,
    2222, 3333, 4444, 5555,
    57742961, 84494718, 139081978, 217174294, 239310745, 261177822, 264705592,
    272443423, 316584448, 336437909, 445438282, 448813646, 468640929, 477607446,
    508531896, 578319661, 594526399, 630564030, 685664587, 732967006, 769646284,
    862985854, 867485794, 870829672, 901318389, 1015267046, 1065888689,
    1107548553, 1195753828, 1209521880, 1270580750, 1305067864, 1313111159,
    1340308450, 1349913430, 1367381807, 1416956391, 1444649734, 1462886287,
    1594923033, 1649072871, 1749998135, 1934278034, 1999215441, 2047520934,
    2050058487, 2068398154, 2073566897,
}


def filename_tokens():
    """Belt and braces: every integer token >= 100 in any outputs/ name.

    Names this round itself writes (_ffr_d4*, _dcd4*, dcd4*) are skipped. Without
    that the rule is self-referential: once the wave has written
    _ffr_d4off_east_half_1686422896.json, a rerun rejects 1686422896 as "used"
    and prints a DIFFERENT set (caught by the analysis round's selftest, mid-wave).
    The set below was chosen before any such file existed, so skipping them
    reproduces it exactly; _dcd4_analyze.py pins the 30 tuples independently.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    toks = set()
    for name in os.listdir(here):
        if name.lower().startswith(("_ffr_d4", "_dcd4", "dcd4")):
            continue
        for t in re.findall(r"\d+", name):
            v = int(t)
            if v >= 100:
                toks.add(v)
    return toks


def ignition(seed):
    rng = random.Random(seed)
    return (rng.randint(10, 39), rng.randint(10, 39))


def choose():
    used = USED_SEEDS | filename_tokens()
    taken_cells = {ignition(s): s for s in PRIOR_SAMPLE_SEEDS}
    need = N_EAST_HALF + N_SOUTH_HALF + N_EAST_DEFAULT
    accepted, rejected = [], []
    i = 0
    while len(accepted) < need:
        seed = int.from_bytes(hashlib.sha256((LABEL % i).encode()).digest()[:4], "big") & 0x7FFFFFFF
        cell = ignition(seed)
        if seed in used or -seed in used:
            rejected.append((i, seed, cell, "used"))
        elif cell in taken_cells:
            rejected.append((i, seed, cell, "ignition cell of %d" % taken_cells[cell]))
        else:
            accepted.append((i, seed, cell))
            taken_cells[cell] = seed
        i += 1
    combos = (["east|half"] * N_EAST_HALF + ["south|half"] * N_SOUTH_HALF
              + ["east|default"] * N_EAST_DEFAULT)
    return [(c, s, cell, idx) for c, (idx, s, cell) in zip(combos, accepted)], rejected


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    tuples, rejected = choose()
    if "--queue" in sys.argv:
        for c, s, _cell, _idx in tuples:
            print("%s|%d" % (c, s))
    else:
        print("label: %r" % LABEL)
        for c, s, cell, idx in tuples:
            print("  %-13s seed %-10d ignition %s  (candidate %d)" % (c.replace("|", "/"), s, cell, idx))
        print("rejected: %d" % len(rejected))
        for r in rejected:
            print("  candidate %d seed %d ignition %s: %s" % r)
