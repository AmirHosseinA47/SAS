"""Carrying-leg round: the SEED FREEZE CHECKS (outputs/_cl_tooling_spec.txt, section E).

Run before EVERY wave and every analysis; outputs/_cl_queue.py runs it first. All checks
run; any failure prints a "SEEDCHECK FAIL" line and ends in SystemExit(1). Only when every
check passes does it print "SEEDCHECK OK" (exit 0).

  (1) outputs/_ug_seeds.py choose() == the frozen U30 in outputs/_ug_seeds.txt, all 30,
      in order. Needs the OWN fix of 2026-09-26 (the FOURTH recurrence of the selector
      self-reference defect: the exit-stall round's xs* files had shifted all 30 tuples).
  (2) outputs/_cl_seeds.py check_frozen() passes: a fresh choose() reproduces the frozen
      N30 in outputs/_cl_seeds.txt.
  (3) outputs/_dcd4_seeds.py choose() seeds == _cl_seeds.DCD4_FOURTH_SET, in order.
  (4) the synthetic names this round (and the exit-stall round) write are skipped by
      _ug_seeds._own - the guard that keeps (1) stable after the waves. Two foreign names
      must NOT be skipped, so the guard cannot pass by being trivially true.
  Also asserted, from the frozen files themselves: each parses (the spec regex
  "^(east|south)\\|(half|default)\\s+seed (\\d+)") to 30 tuples in the 13 east/half,
  13 south/half, 4 east/default order, no seed repeated, U30 and N30 disjoint, and the
  parses equal _ug_seeds.frozen_u30(), _cl_seeds.frozen_u30() and _cl_seeds.frozen_n30().

Importable: run_checks() returns {"U30": [(wind, roles, seed), ...], "N30": [...]}
(roles "half" | "default", frozen order) once every check has passed; otherwise it
raises SystemExit(1).

QUARANTINE (outputs/_firemech_rewound_20260914/): this module lists no directory itself.
The selectors it calls list outputs/ and outputs/_ffr_logs/ NON-recursively - _ug_seeds
and _cl_seeds skip the quarantine entry by name - and they run `git ls-files`.
_dcd4_seeds.filename_tokens (frozen, not edited; reached through _dcd4_seeds.choose(),
which _ug_seeds.choose() also calls) would tokenize the NAME of every outputs/ entry, the
quarantine's included (A1 forbids even that): this module replaces the `os` global of
_dcd4_seeds ONLY with a stand-in whose listdir drops the quarantine entry by string
compare before the caller sees any entry (every other attribute is the real os). Check
(3) (== the frozen DCD4_FOURTH_SET) and check (1) confirm it changes no seed.
_ug_seeds.git_names' untracked walk carries no exclude pathspec (it relies on
.git/info/exclude, which lists the directory); this module wraps it so every --others
call ALSO carries ':(exclude)outputs/_firemech_rewound_20260914'. That is value-neutral:
git_names already drops every path containing the quarantine name.

usage: .venv/Scripts/python.exe -B outputs/_cl_seedcheck.py
"""
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cl_seeds  # noqa: E402
import _dcd4_seeds  # noqa: E402
import _ug_seeds  # noqa: E402

QUAR = "_firemech_rewound_20260914"
SEED_RE = re.compile(r"^(east|south)\|(half|default)\s+seed (\d+)")
COMPOSITION = ["east|half"] * 13 + ["south|half"] * 13 + ["east|default"] * 4
# spec E(4): names this round writes; each must be skipped by _ug_seeds._own
SYNTHETIC_OWN = ("_ffr_clC_east_half_2070841104.json",
                 "_ffr_clKC_south_half_903347495.json",
                 "clC_east_def_1749069988.out",
                 "_cl_queue.txt",
                 "_ffr_xsTD_east_half_2070841104.json")
# negative control: another round's outputs; the guard must NOT skip them
FOREIGN = ("_ffr_dfD_east_half_101.json", "_ffr_fmDRY_south_half_404.json")


def _guard_ug_git_names():
    """Add the quarantine exclude pathspec to every untracked (--others) git walk that
    _ug_seeds makes. Idempotent."""
    orig = _ug_seeds.git_names
    if getattr(orig, "_cl_quarantine_guard", False):
        return

    def guarded(*args):
        args = list(args)
        if "--others" in args:
            if "--" not in args:
                args.append("--")
            args.append(":(exclude)outputs/" + QUAR)
        return orig(*args)

    guarded._cl_quarantine_guard = True
    _ug_seeds.git_names = guarded


class _QuarantineSkippingOs:
    """Stand-in for the `os` module inside _dcd4_seeds only: every attribute is the real
    os's, except listdir, which drops the quarantine entry by name (spec A1)."""
    _cl_quarantine_guard = True

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def listdir(self, path="."):
        return [n for n in self._real.listdir(path) if n != QUAR]


def _guard_dcd4_listdir():
    """_dcd4_seeds.filename_tokens is that module's only listdir. Idempotent."""
    if getattr(_dcd4_seeds.os, "_cl_quarantine_guard", False):
        return
    _dcd4_seeds.os = _QuarantineSkippingOs(_dcd4_seeds.os)


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def parse_frozen(fname):
    """[(combo, seed)] from a committed seed file, by the spec regex."""
    out = []
    with open(os.path.join(HERE, fname), encoding="utf-8") as f:
        for line in f:
            m = SEED_RE.match(line)
            if m:
                out.append((m.group(1) + "|" + m.group(2), int(m.group(3))))
    return out


def _shape_problems(name, pairs):
    probs = []
    if len(pairs) != 30:
        probs.append("%s: %d tuples, want 30" % (name, len(pairs)))
    if [c for c, _s in pairs] != COMPOSITION:
        probs.append("%s: combo order is not 13 east|half, 13 south|half, 4 east|default" % name)
    seeds = [s for _c, s in pairs]
    if len(set(seeds)) != len(seeds):
        probs.append("%s: a seed repeats" % name)
    return probs


def _first_diff(a, b):
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else None
        y = b[i] if i < len(b) else None
        if x != y:
            return i, x, y
    return None


def run_checks(say=print):
    _guard_ug_git_names()
    _guard_dcd4_listdir()
    fails = []

    def fail(msg):
        fails.append(msg)
        say("SEEDCHECK FAIL " + msg)

    # frozen files, parsed independently
    u30 = parse_frozen("_ug_seeds.txt")
    n30 = parse_frozen("_cl_seeds.txt")
    say("frozen U30 outputs/_ug_seeds.txt sha256 %s  %d tuples" % (_sha(os.path.join(HERE, "_ug_seeds.txt")), len(u30)))
    say("frozen N30 outputs/_cl_seeds.txt sha256 %s  %d tuples" % (_sha(os.path.join(HERE, "_cl_seeds.txt")), len(n30)))
    for p in _shape_problems("U30", u30) + _shape_problems("N30", n30):
        fail("(shape) " + p)
    both = sorted({s for _c, s in u30} & {s for _c, s in n30})
    if both:
        fail("(shape) U30 and N30 share seeds %s" % both)
    for label, fn in (("_ug_seeds.frozen_u30()", _ug_seeds.frozen_u30),
                      ("_cl_seeds.frozen_u30()", _cl_seeds.frozen_u30),
                      ("_cl_seeds.frozen_n30()", _cl_seeds.frozen_n30)):
        want = n30 if "n30" in label else u30
        try:
            got = fn()
        except (Exception, SystemExit) as exc:  # noqa: BLE001 - report, never skip
            fail("(parse) %s raised %s: %s" % (label, type(exc).__name__, exc))
            continue
        if got != want:
            fail("(parse) %s disagrees with the spec-regex parse at %r" % (label, _first_diff(got, want)))

    # (1) U30 selector reproduces the frozen set
    try:
        tuples = _ug_seeds.choose()[0]
        got = [(c, s) for c, s, _cell, _idx in tuples]
        if got == u30 and len(got) == 30:
            say("(1) U30  _ug_seeds.choose() == outputs/_ug_seeds.txt  30/30 in order  PASS")
        else:
            same = sum(1 for a, b in zip(got, u30) if a == b)
            fail("(1) U30  _ug_seeds.choose() != outputs/_ug_seeds.txt: %d/30 positions equal, "
                 "first difference %r" % (same, _first_diff(got, u30)))
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        fail("(1) U30  _ug_seeds.choose() raised %s: %s" % (type(exc).__name__, exc))

    # (2) N30 selector reproduces the frozen set
    try:
        frozen = _cl_seeds.check_frozen()
        if frozen == n30 and len(frozen) == 30:
            say("(2) N30  _cl_seeds.check_frozen()  30/30  PASS")
        else:
            fail("(2) N30  check_frozen() returned a set that differs from the spec-regex parse")
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        fail("(2) N30  _cl_seeds.check_frozen() failed: %s: %s" % (type(exc).__name__, exc))

    # (3) the dcd4 fourth set
    try:
        d4 = [s for _c, s, _cell, _idx in _dcd4_seeds.choose()[0]]
        want = list(_cl_seeds.DCD4_FOURTH_SET)
        if d4 == want and len(d4) == 30:
            say("(3) DCD4 _dcd4_seeds.choose() == _cl_seeds.DCD4_FOURTH_SET  30/30 in order  PASS")
        else:
            fail("(3) DCD4 _dcd4_seeds.choose() != DCD4_FOURTH_SET, first difference %r" % (_first_diff(d4, want),))
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        fail("(3) DCD4 _dcd4_seeds.choose() raised %s: %s" % (type(exc).__name__, exc))

    # (4) the self-reference guard skips this round's names
    not_skipped = [n for n in SYNTHETIC_OWN if not _ug_seeds._own(n)]
    wrongly = [n for n in FOREIGN if _ug_seeds._own(n)]
    if not not_skipped and not wrongly:
        say("(4) GUARD _ug_seeds._own skips %d/%d synthetic names, %d/%d foreign names  PASS"
            % (len(SYNTHETIC_OWN), len(SYNTHETIC_OWN), len(wrongly), len(FOREIGN)))
    else:
        if not_skipped:
            fail("(4) GUARD _ug_seeds._own does NOT skip %s" % not_skipped)
        if wrongly:
            fail("(4) GUARD _ug_seeds._own skips foreign names %s (guard trivially true?)" % wrongly)

    if fails:
        say("SEEDCHECK FAIL: %d check(s) failed - STOP" % len(fails))
        raise SystemExit(1)

    def split(pairs):
        return [(c.split("|")[0], c.split("|")[1], s) for c, s in pairs]

    return {"U30": split(u30), "N30": split(n30)}


def main():
    sys.stdout.reconfigure(newline="\n")
    run_checks()
    print("SEEDCHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
