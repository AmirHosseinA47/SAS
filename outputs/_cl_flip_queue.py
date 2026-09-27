"""Carrying-leg round: write the FLIP GATE queue (carryleg_prereg.txt section 10, G7 (1)-(3)).

  _cl_flip_queue.txt   stock, 360 steps, the carryleg checkout (the FLIPPED tree):   69
    clFZ  C13        --set FF_EXIT_LEG_MODE=0 --set FF_EXIT_LEG_HOLD=0 --set FF_EXIT_LEG_SERVED=0
                     (the kill switch as it ships; must == clB)
    clFD  C13 + U30  no switch --set (the shipped defaults; must == clA, which == clE2)
    clFJ  C13        --set FF_EXIT_LEG_MODE=0.5 --set FF_EXIT_LEG_SERVED=0.5
                     (junk takes the shipped value after the flip; must == clA)

BEFORE anything is written (every failure is a SystemExit naming it):
  1. the seed freeze checks (outputs/_cl_seedcheck.py); C13 / U30 from _cl_common.seed_sets;
  2. the checkout is FLIPPED: common_fixed_variables.py reads FF_EXIT_LEG_MODE = 2,
     FF_EXIT_LEG_HOLD = 0, FF_EXIT_LEG_SERVED = 1 (a flip-gate wave on the unflipped tree
     would compare the wrong thing);
  3. every line read back through _cl_common.read_queue and checked by check_arm_line
     (the flip arms' exact --set dicts);
  4. TAG COLLISIONS: no entry of outputs/ or outputs/_ffr_logs/ (os.listdir, NON-recursive,
     the quarantine entry skipped by name first) starts with _ffr_<tag>_ or <tag>_
     (case-insensitive) unless it is an expected output of a line standing byte-identical
     in the file already on disk; `git ls-files` (quarantine excluded) lists none;
  5. an existing queue file is never rewritten: identical -> "unchanged", else STOP.
Written tmp + os.replace, UTF-8, LF; line count and sha256 printed.

QUARANTINE: outputs/_firemech_rewound_20260914/ is never read, listed or traversed.

usage: .venv/Scripts/python.exe -B outputs/_cl_flip_queue.py
"""
import hashlib
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _cl_seedcheck  # noqa: E402
import _cl_common as CC  # noqa: E402

QUAR = "_firemech_rewound_20260914"
FNAME = "_cl_flip_queue.txt"
REPO = "E:/Projects/SAS"
COMMON = "--uav-actions --set BATCH_SIZE=360"
FLIPPED = {"FF_EXIT_LEG_MODE": "2", "FF_EXIT_LEG_HOLD": "0", "FF_EXIT_LEG_SERVED": "1"}
ARMS = (("clFZ", ("C13",), " --set FF_EXIT_LEG_MODE=0 --set FF_EXIT_LEG_HOLD=0 --set FF_EXIT_LEG_SERVED=0"),
        ("clFD", ("C13", "U30"), ""),
        ("clFJ", ("C13",), " --set FF_EXIT_LEG_MODE=0.5 --set FF_EXIT_LEG_SERVED=0.5"))
EXPECTED_LINES = 69


def stop(msg):
    raise SystemExit("CL_FLIP_QUEUE STOP: " + msg)


def rr(roles):
    return "def" if roles == "default" else roles


def flipped():
    with open(os.path.join(ROOT, "common_fixed_variables.py"), "rb") as f:
        text = f.read().decode("utf-8", "replace").replace("\r", "")
    got = {k: re.findall(r"^%s = (\S+)\s*$" % k, text, re.M) for k in FLIPPED}
    bad = {k: v for k, v in got.items() if v != [FLIPPED[k]]}
    if bad:
        stop("the checkout is not the flipped tree: common_fixed_variables.py has %r, want %r" % (bad, FLIPPED))


def listing(d):
    return [n for n in os.listdir(d) if n != QUAR]


def tracked():
    r = subprocess.run(["git", "-C", ROOT, "ls-files", "--", "outputs", ":(exclude)outputs/%s" % QUAR],
                       capture_output=True, text=True)
    if r.returncode != 0:
        stop("git ls-files failed: %s" % r.stderr.strip())
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def main():
    checked = _cl_seedcheck.run_checks()
    sets = CC.seed_sets(checked)
    flipped()
    lines = []
    for tag, set_names, extra in ARMS:
        for sn in set_names:
            for w, r, s in sets[sn]:
                lines.append("ff|%s|%s|%s|%s|%d|360|%s%s" % (tag, REPO, w, r, s, COMMON, extra))
    if len(lines) != EXPECTED_LINES or len(set(lines)) != len(lines):
        stop("%d lines (%d distinct), want %d" % (len(lines), len(set(lines)), EXPECTED_LINES))
    body = "\n".join(lines) + "\n"
    path = os.path.join(HERE, FNAME)
    on_disk = None
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", newline="") as f:
            on_disk = f.read()
        if on_disk != body:
            stop("%s exists and differs from its regeneration - never rewritten" % FNAME)
    allowed_top, allowed_log = set(), set()
    if on_disk is not None:
        for ln in lines:
            _k, tag, _repo, w, r, s, _st, _ex = ln.split("|", 7)
            stem = "_ffr_%s_%s_%s_%s" % (tag, w, rr(r), s)
            allowed_top |= {(stem + x).lower() for x in (".json", ".stdout.txt", ".clobs.json")}
            allowed_log |= {("%s_%s_%s_%s%s" % (tag, w, rr(r), s, x)).lower() for x in (".out", ".err")}
    top, logs, tr = listing(HERE), listing(os.path.join(HERE, "_ffr_logs")), tracked()
    for tag, _s, _e in ARMS:
        pre = (("_ffr_%s_" % tag).lower(), ("%s_" % tag).lower())
        for name in top:
            if name.lower().startswith(pre) and name.lower() not in allowed_top:
                stop("tag collision: outputs/%s" % name)
        for name in logs:
            if name.lower().startswith(pre) and name.lower() not in allowed_log:
                stop("tag collision: outputs/_ffr_logs/%s" % name)
        for t in tr:
            if os.path.basename(t).lower().startswith(pre):
                stop("TRACKED file of tag %s: %s" % (tag, t))
    if on_disk is None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        os.replace(tmp, path)
    recs = CC.read_queue(path)
    if [x["raw"] for x in recs] != lines:
        stop("%s reads back differently through _cl_common.read_queue" % FNAME)
    for x in recs:
        why = CC.check_arm_line(x)
        if why:
            stop("the analyzer refuses %s:%d: %s" % (FNAME, x["lineno"], "; ".join(why)))
        if CC.set_of(x["tup"], sets) not in ("C13", "U30"):
            stop("%s:%d tuple outside C13/U30" % (FNAME, x["lineno"]))
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    print("%s %d  %s  %s" % (FNAME, len(lines), sha, "written" if on_disk is None else "unchanged"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
