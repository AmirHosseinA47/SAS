"""Carrying-leg round: choose the NEW INDEPENDENT seed set (N30), reproducibly, BEFORE
any run of the round. Method copied from outputs/_ug_seeds.py (ungated round), which
copied outputs/_dcd4_seeds.py (dcd4 round); the used-seed universe is widened to
everything run since, and the U30 set of the ungated round is now a PRIOR set.

  1. Candidates: SHA-256 in counter mode over a declared label.
     seed_i = first 4 bytes of sha256(LABEL % i), big-endian, & 0x7FFFFFFF.
  2. A candidate is REJECTED only if
       (a) it, or its negative, is a seed used anywhere in this project
           (random.Random(-n) == random.Random(n)): the dcd4 audit list, the dcd4
           fourth set, the U30 set (read from the committed outputs/_ug_seeds.txt),
           every integer >= 100 in any outputs/ or outputs/_ffr_logs/ file NAME
           (tracked or untracked), every integer >= 100 inside any tracked queue
           file, and every literal seed in tests/*.py; or
       (b) its ignition cell equals that of any seed in the canonical 13, fresh 10,
           rbgate 18, the dcd4 fourth set, the U30 set, or a seed already accepted.
     No outcome screen of any kind: a no-spread world is NOT excluded (that cannot be
     known without running the fire, and excluding it after would be selection on
     outcome).
  3. Accepted seeds are assigned IN ORDER: 13 east/half, 13 south/half, 4
     east/default - the U30 / dcd4 composition. One seed per tuple: 30 seeds, 30 fire
     worlds, none shared across winds (the rbgate-sample-overlap lesson).

QUARANTINE. File names come from `git ls-files` - tracked (the index only) and
--others --exclude-standard, which is git's UNTRACKED WALK of outputs/. That walk is kept
out of outputs/_firemech_rewound_20260914/ twice over: by the pathspec
':(exclude)outputs/_firemech_rewound_20260914' passed on the command itself, and by
.git/info/exclude, which lists it (git prunes an excluded directory without opening it).
The only other listings are NON-recursive os.listdir of outputs/ and outputs/_ffr_logs/,
in which the quarantine entry is skipped by name before anything is done with it.
(The first two runs of this file, 2026-09-25 14:37 and 15:03, relied on
.git/info/exclude alone for the untracked walk; the pathspec was added after them and
cannot change the output, since the excluded paths were already pruned.)

THE PRIOR SETS ARE FROZEN LITERALS, not recomputed: the dcd4 fourth set below is
_dcd4_seeds.choose() as it stood on 2026-09-25 (all 30 appear in the committed
outputs/_dcd4_queue.txt), and U30 is read from the committed outputs/_ug_seeds.txt. A
later rerun of either selector under another tag therefore cannot move N30.

SELF-REFERENCE GUARD (the seed-selector self-reference lesson, three occurrences):
names this round writes - basenames starting "_cl", "cl", "carryleg", "_ffr_cl",
"_rblatch_camp2_cl" - are skipped, so a rerun after the waves prints the SAME set. The
guard skipped 2 names at the first freeze (15:03: this file and the redirect-created
_cl_seeds.txt) and 3 at the second (15:35: those two and _cl_replay), none holding a
number >= 100; the seeds are identical in both. The set is ALSO frozen in
outputs/_cl_seeds.txt; analyzers call check_frozen() and must STOP if a fresh choose()
disagrees (compare SEEDS, not the whole printout - the universe size legitimately grows).

usage: .venv/Scripts/python.exe -B outputs/_cl_seeds.py [--queue]
"""
import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _dcd4_seeds as D4  # noqa: E402  (pure: hashlib/os/random/re)

LABEL = "SAS carrying-leg round fresh independent seed set, declared 2026-09-25, candidate %d"
N_EAST_HALF, N_SOUTH_HALF, N_EAST_DEFAULT = 13, 13, 4
QUAR = "_firemech_rewound_20260914"
OWN = ("_cl", "cl", "carryleg", "_ffr_cl", "_rblatch_camp2_cl")
# _dcd4_seeds.choose() on 2026-09-25, frozen (every one is in outputs/_dcd4_queue.txt).
DCD4_FOURTH_SET = (
    1686422896, 339529960, 1323590814, 565244337, 1799457742, 213441142, 1038975554,
    899534678, 2116546930, 1659006522, 1626974145, 1465634084, 150314831, 207893904,
    990257450, 301432237, 423146201, 1483537190, 1587703022, 1776294962, 2097141346,
    1817334565, 752343876, 1038470813, 1989343762, 3682542, 737555233, 1266834353,
    1756726159, 2111261717,
)


def _own(name):
    return os.path.basename(name).lower().startswith(OWN)


def _tokens(text, floor=100):
    return {int(t) for t in re.findall(r"\d+", text) if int(t) >= floor}


def git_names(*args):
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"] + list(args),
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    return [p for p in out.split("\0") if p and QUAR not in p]


def frozen_u30():
    """The ungated round's PRE-REGISTERED U30, read from its committed seed file."""
    out = []
    for line in open(os.path.join(HERE, "_ug_seeds.txt"), encoding="utf-8"):
        m = re.match(r"^(east|south)\|(half|default)\s+seed (\d+)", line)
        if m:
            out.append((m.group(1) + "|" + m.group(2), int(m.group(3))))
    assert len(out) == 30, len(out)
    return out


def used_universe():
    used = set(D4.USED_SEEDS)
    d4_seeds = list(DCD4_FOURTH_SET)
    u30_seeds = [s for _c, s in frozen_u30()]
    used |= set(d4_seeds) | set(u30_seeds)
    sources = {"dcd4 audit list": len(D4.USED_SEEDS), "dcd4 fourth set": len(d4_seeds),
               "U30 set": len(u30_seeds)}
    names = set()
    own_skipped = []
    untracked = git_names("--others", "--exclude-standard", "--", "outputs", ":(exclude)outputs/" + QUAR)
    for p in git_names("--", "outputs") + untracked:
        if _own(p):
            own_skipped.append(p)
            continue
        names.add(p)
    for d in ("outputs", os.path.join("outputs", "_ffr_logs")):
        full = os.path.join(ROOT, d)
        if not os.path.isdir(full):
            continue
        for n in os.listdir(full):           # NON-recursive
            if n == QUAR:
                continue
            if _own(n):
                own_skipped.append(d + "/" + n)
                continue
            names.add(d + "/" + n)
    name_tok = set()
    for p in names:
        name_tok |= _tokens(os.path.basename(p))
    used |= name_tok
    sources["outputs/ file-name tokens"] = len(name_tok)
    queue_tok = set()
    for p in git_names("--", "outputs"):
        b = os.path.basename(p).lower()
        if b.endswith(".txt") and "queue" in b and not _own(p):
            queue_tok |= _tokens(open(os.path.join(ROOT, p), "rb").read().decode("utf-8", "replace"))
    used |= queue_tok
    sources["tracked queue-file tokens"] = len(queue_tok)
    test_tok = set()
    for p in git_names("--", "tests"):
        if p.endswith(".py"):
            t = open(os.path.join(ROOT, p), "rb").read().decode("utf-8", "replace")
            for m in re.finditer(r"(?:seed\s*[=:]\s*|Random\(\s*|SEED\s*=\s*)(-?\d+)", t):
                test_tok.add(abs(int(m.group(1))))
    used |= test_tok
    sources["tests/ literal seeds"] = len(test_tok)
    sources["own-guard names skipped"] = len(sorted(set(own_skipped)))
    return used, d4_seeds, u30_seeds, sources


def choose():
    used, d4_seeds, u30_seeds, sources = used_universe()
    taken = {}
    for s in list(D4.PRIOR_SAMPLE_SEEDS) + d4_seeds + u30_seeds:
        taken.setdefault(D4.ignition(s), s)
    need = N_EAST_HALF + N_SOUTH_HALF + N_EAST_DEFAULT
    accepted, rejected = [], []
    i = 0
    while len(accepted) < need:
        seed = int.from_bytes(hashlib.sha256((LABEL % i).encode()).digest()[:4], "big") & 0x7FFFFFFF
        cell = D4.ignition(seed)
        if seed in used or -seed in used:
            rejected.append((i, seed, cell, "used"))
        elif cell in taken:
            rejected.append((i, seed, cell, "ignition cell of %d" % taken[cell]))
        else:
            accepted.append((i, seed, cell))
            taken[cell] = seed
        i += 1
    combos = (["east|half"] * N_EAST_HALF + ["south|half"] * N_SOUTH_HALF
              + ["east|default"] * N_EAST_DEFAULT)
    return [(c, s, cell, idx) for c, (idx, s, cell) in zip(combos, accepted)], rejected, sources, len(used)


def frozen_n30():
    """The PRE-REGISTERED N30, read from outputs/_cl_seeds.txt (committed before any run)."""
    out = []
    for line in open(os.path.join(HERE, "_cl_seeds.txt"), encoding="utf-8"):
        m = re.match(r"^(east|south)\|(half|default)\s+seed (\d+)", line)
        if m:
            out.append((m.group(1) + "|" + m.group(2), int(m.group(3))))
    assert len(out) == 30, len(out)
    return out


def check_frozen():
    """STOP (SystemExit) if a fresh choose() no longer reproduces the frozen seeds."""
    fresh = [(c, s) for c, s, _cell, _idx in choose()[0]]
    frozen = frozen_n30()
    if fresh != frozen:
        raise SystemExit("N30 MISMATCH: fresh choose() differs from outputs/_cl_seeds.txt - "
                         "the selector's universe changed; read the frozen file, investigate, STOP")
    return frozen


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    tuples, rejected, sources, n_used = choose()
    if "--queue" in sys.argv:
        for c, s, _cell, _idx in tuples:
            print("%s|%d" % (c, s))
        sys.exit(0)
    print("label: %r" % LABEL)
    print("used-seed universe: %d distinct values  %s" % (n_used, sources))
    print("rejected: %d  %s" % (len(rejected), rejected))
    for c, s, cell, idx in tuples:
        print("%-13s seed %-10d ignition %s  (candidate %d)" % (c, s, cell, idx))
