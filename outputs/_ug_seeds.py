"""Ungated-firefighting round: choose the FRESH INDEPENDENT seed set, reproducibly,
BEFORE any run. Method copied from outputs/_dcd4_seeds.py (dcd4 round), with the
used-seed universe widened to everything run since.

  1. Candidates: SHA-256 in counter mode over a declared label.
     seed_i = first 4 bytes of sha256(LABEL % i), big-endian, & 0x7FFFFFFF.
  2. A candidate is REJECTED only if
       (a) it, or its negative, is a seed used anywhere in this project
           (random.Random(-n) == random.Random(n)): the dcd4 audit list, the dcd4
           fourth set itself, every integer >= 100 in any outputs/ file NAME (tracked
           or untracked), every integer >= 100 inside any tracked queue file, and every
           literal seed in tests/*.py; or
       (b) its ignition cell equals that of any seed in the canonical 13, fresh 10,
           rbgate 18, the dcd4 fourth set, or a seed already accepted here.
     No outcome screen of any kind: a no-spread world is NOT excluded (that cannot be
     known without running the fire, and excluding it after would be selection on
     outcome).
  3. Accepted seeds are assigned IN ORDER: 13 east/half, 13 south/half, 4
     east/default - the dcd4 composition, which mirrors canonical+fresh (20 half on
     both winds + 3 east/default, 13% legacy roles). One seed per tuple: 30 seeds, 30
     fire worlds, none shared across winds.

QUARANTINE-SAFE: no directory is walked. File names come from `git ls-files` (tracked
and --others --exclude-standard; git does not descend into
outputs/_firemech_rewound_20260914/ because .git/info/exclude lists it) and from a
NON-recursive listing of outputs/ and outputs/_ffr_logs/ in which the quarantine
entry is skipped by name before anything is done with it.

SELF-REFERENCE GUARD (the dcd4 selftest lesson): names this round writes (tags
starting "ug", files "_ug*", "ungated*", "_ffr_ug*", "_rblatch_camp2_ug*") are
skipped, so a rerun after the wave prints the SAME set.

usage: .venv/Scripts/python.exe -B outputs/_ug_seeds.py [--queue]
"""
import hashlib
import os
import random
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _dcd4_seeds as D4  # noqa: E402  (pure: hashlib/os/random/re)

LABEL = "SAS ungated-firefighting fresh independent seed set, declared 2026-09-21, candidate %d"
N_EAST_HALF, N_SOUTH_HALF, N_EAST_DEFAULT = 13, 13, 4
QUAR = "_firemech_rewound_20260914"
OWN = ("_ug", "ungated", "_ffr_ug", "_rblatch_camp2_ug", "ug")


def _own(name):
    base = os.path.basename(name).lower()
    return base.startswith(OWN)


def _tokens(text, floor=100):
    return {int(t) for t in re.findall(r"\d+", text) if int(t) >= floor}


def git_names(*args):
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"] + list(args),
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    return [p for p in out.split("\0") if p and QUAR not in p]


def used_universe():
    used = set(D4.USED_SEEDS)
    d4_tuples, _rej = D4.choose()
    d4_seeds = [s for _c, s, _cell, _i in d4_tuples]
    used |= set(d4_seeds)
    sources = {"dcd4 audit list": len(D4.USED_SEEDS), "dcd4 fourth set": len(d4_seeds)}
    names = set()
    for p in git_names("--", "outputs") + git_names("--others", "--exclude-standard", "--", "outputs"):
        if not _own(p):
            names.add(p)
    for d in ("outputs", os.path.join("outputs", "_ffr_logs")):
        full = os.path.join(ROOT, d)
        if not os.path.isdir(full):
            continue
        for n in os.listdir(full):           # NON-recursive
            if n == QUAR or _own(n):
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
    return used, d4_seeds, sources


def choose():
    used, d4_seeds, sources = used_universe()
    taken = {}
    for s in list(D4.PRIOR_SAMPLE_SEEDS) + d4_seeds:
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
