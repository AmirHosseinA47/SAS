"""Carrying-leg round, Part 3: write the two D-9 PROBE queues (spec L; design D-9 (b)).

  _cl_probe_queue.txt      stock: clPS0 x 3 tuples, then clPS1 x 3 tuples        6
  _cl_probe_crn_queue.txt  CRN:   clKPS0 x 3 tuples, then clKPS1 x 3 tuples       6

THE FROZEN TUPLES are spec L's, verbatim (kill the NON-carrying unit at the carrier's
pickup step; U30 tuples):
    south/half/1048395951  kill ff_unit_1 at 132   (uhD: ff_unit_0 carries 132 -> 262)
    east/half/1433805104   kill ff_unit_0 at 206   (uhD: ff_unit_1 carries 206 -> 281)
    east/def/1420331661    kill ff_unit_0 at 86    (ugKD: ff_unit_1 carries 86 -> 156)
Each tuple runs in BOTH instruments (design D-9 (b): "stock and CRN"), SERVED 0 and SERVED 1.
The pre-screen (keep a tuple/instrument only if its SERVED-0 run has a custody marking)
is applied when the runs are READ (outputs/_cl_probe_analyze.py), not by withholding the
SERVED-1 lines: one wave instead of two; the rule is fixed before any run, so running the
SERVED-1 line of a tuple the pre-screen drops buys no freedom. Those runs are reported
as "dropped by the pre-screen", never pooled with the kept ones.

Line shape (the stage files' ff shape + the CLP keys; FM2P_CRN=1 first on CRN lines, as
_cl_queue.ff_line writes it):
  ff|<tag>|E:/Projects/SAS|<wind>|<half|default>|<seed>|360|--uav-actions --set BATCH_SIZE=360
     [--set FM2P_CRN=1] --set CLP_KILL_AT=<s> --set CLP_KILL_UNIT=<unit> [--set FF_EXIT_LEG_SERVED=1]

BEFORE anything is written (every failure is a SystemExit naming it):
  1. the seed freeze checks (outputs/_cl_seedcheck.py); each tuple is in the frozen U30;
  2. every line through _cl_queue.check_line's shape rules (CLP_ keys exempted from the
     cfv declaration test, as _cl_common.EXEMPT_PREFIXES does) AND the analyzer's
     _cl_common.check_arm_line (the probe arm table: clPS0/clPS1/clKPS0/clKPS1);
  3. TAG COLLISIONS: no entry of outputs/ or outputs/_ffr_logs/ (os.listdir, NON-recursive,
     the quarantine entry skipped by name first) starts with _ffr_<tag>_ or <tag>_
     (case-insensitive), and `git ls-files` (quarantine excluded) lists none; the only
     allowed hit is an expected output of a line that stands byte-identical in the queue
     file already on disk (a rerun of this generator) - otherwise STOP;
  4. an existing queue file is left untouched when identical, else STOP (never rewritten
     once written).
Then each file is written (tmp + os.replace, UTF-8, LF) and its line count and sha256
printed (record them in carryleg_prereg.txt before the wave).

QUARANTINE: outputs/_firemech_rewound_20260914/ is never read, listed or traversed.

usage: .venv/Scripts/python.exe -B outputs/_cl_probe_queue.py
"""
import hashlib
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _cl_seedcheck  # noqa: E402
import _cl_common as CC  # noqa: E402
import _cl_queue as Q  # noqa: E402

QUAR = "_firemech_rewound_20260914"
TUPLES = (  # (wind, roles, seed, kill unit, kill step) - spec L, frozen
    ("south", "half", 1048395951, "ff_unit_1", 132),
    ("east", "half", 1433805104, "ff_unit_0", 206),
    ("east", "default", 1420331661, "ff_unit_0", 86),
)
FILES = (("_cl_probe_queue.txt", False, ("clPS0", "clPS1")),
         ("_cl_probe_crn_queue.txt", True, ("clKPS0", "clKPS1")))
SERVED = "FF_EXIT_LEG_SERVED"


def stop(msg):
    raise SystemExit("CL_PROBE_QUEUE STOP: " + msg)


def line(tag, tup, crn):
    w, r, s, unit, at = tup
    extra = Q.COMMON
    if crn:
        extra += " --set %s=%s" % Q.CRN
    extra += " --set CLP_KILL_AT=%d --set CLP_KILL_UNIT=%s" % (at, unit)
    if tag.endswith("1"):
        extra += " --set %s=1" % SERVED
    return "ff|%s|%s|%s|%s|%d|%d|%s" % (tag, Q.REPO, w, r, s, Q.FF_STEPS, extra)


def check(fname, ln, crn, u30):
    p = Q.parse(ln)
    keys = [k for k, _v in p["sets"]]
    if len(set(keys)) != len(keys):
        stop("a --set key repeats: %r" % ln)
    if p["kind"] != "ff" or p["repo"] != Q.REPO or p["steps"] != str(Q.FF_STEPS):
        stop("line shape: %r" % ln)
    if not p["extra"].startswith(Q.COMMON + " ") or p["ua"] != 1 \
            or p["sets"][0] != ("BATCH_SIZE", str(Q.FF_STEPS)):
        stop("line without the common flags: %r" % ln)
    fm2p = {k: v for k, v in p["sets"] if k.startswith("FM2P_")}
    if crn and fm2p != {Q.CRN[0]: Q.CRN[1]}:
        stop("CRN line without exactly FM2P_CRN=1: %r" % ln)
    if not crn and fm2p:
        stop("FM2P_ key on a stock line: %r" % ln)
    clp = {k: v for k, v in p["sets"] if k.startswith("CLP_")}
    if set(clp) != {"CLP_KILL_AT", "CLP_KILL_UNIT"}:
        stop("probe line without exactly CLP_KILL_AT + CLP_KILL_UNIT: %r" % ln)
    for k, v in p["sets"]:
        if k == SERVED and v not in ("0", "1"):
            stop("%s=%s refused (D-1): %r" % (k, v, ln))
        if not k.startswith(CC.EXEMPT_PREFIXES) and k not in Q.cfv_keys(p["repo"]):
            stop("--set %s is not declared in common_fixed_variables.py: %r" % (k, ln))
    tup = (p["wind"], p["roles"], int(p["seeds"]))
    if tup not in u30:
        stop("tuple %s is not in the frozen U30: %r" % (tup, ln))
    # the analyzer's own view of the line (_cl_common.parse_extra + check_arm_line)
    sets, ua = CC.parse_extra(p["extra"], ln)
    why = CC.check_arm_line(dict(kind="ff", tag=p["tag"], repo=p["repo"], wind=p["wind"],
                                 roles=p["roles"], steps=int(p["steps"]), sets=sets, uav_actions=ua))
    if why:
        stop("the analyzer refuses %r: %s" % (ln, "; ".join(why)))
    return p


def listing(d):
    out = []
    for name in os.listdir(d):
        if name == QUAR:
            continue
        out.append(name)
    return out


def tracked():
    r = subprocess.run(["git", "-C", ROOT, "ls-files", "--", "outputs",
                        ":(exclude)outputs/%s" % QUAR], capture_output=True, text=True)
    if r.returncode != 0:
        stop("git ls-files failed: %s" % r.stderr.strip())
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def expected_names(p):
    stem = "_ffr_%s_%s_%s_%s" % (p["tag"], p["wind"], Q.rr(p["roles"]), p["seeds"])
    log = "%s_%s_%s_%s" % (p["tag"], p["wind"], Q.rr(p["roles"]), p["seeds"])
    return {stem + ".json", stem + ".stdout.txt", stem + ".clobs.json"}, {log + ".out", log + ".err"}


def main():
    checked = _cl_seedcheck.run_checks()          # SystemExit(1) on any failure
    u30 = set(CC.seed_sets(checked)["U30"])        # refuses unless == the frozen file
    outdir = HERE
    top = listing(outdir)
    logs = listing(os.path.join(outdir, "_ffr_logs"))
    tr = tracked()
    for fname, crn, tags in FILES:
        lines = [line(tag, t, crn) for tag in tags for t in TUPLES]
        parsed = [check(fname, ln, crn, u30) for ln in lines]
        path = os.path.join(outdir, fname)
        on_disk = None
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", newline="") as f:
                on_disk = f.read()
        body = "\n".join(lines) + "\n"
        if on_disk is not None and on_disk != body:
            stop("%s exists and differs from its regeneration - never rewritten" % fname)
        allowed_top, allowed_log = set(), set()
        if on_disk is not None:
            for p in parsed:
                a, b = expected_names(p)
                allowed_top |= {x.lower() for x in a}
                allowed_log |= {x.lower() for x in b}
        for tag in tags:
            pre1, pre2 = ("_ffr_%s_" % tag).lower(), ("%s_" % tag).lower()
            for name in top:
                n = name.lower()
                if (n.startswith(pre1) or n.startswith(pre2)) and n not in allowed_top:
                    stop("tag collision: outputs/%s" % name)
            for name in logs:
                n = name.lower()
                if (n.startswith(pre1) or n.startswith(pre2)) and n not in allowed_log:
                    stop("tag collision: outputs/_ffr_logs/%s" % name)
            for t in tr:
                b = os.path.basename(t).lower()
                if b.startswith(pre1) or b.startswith(pre2):
                    stop("TRACKED file of tag %s: %s" % (tag, t))
        if on_disk is None:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
            os.replace(tmp, path)
        # read back exactly as the analyzer reads a queue, and re-check every line
        recs = CC.read_queue(path)
        if [r["raw"] for r in recs] != lines:
            stop("%s reads back differently through _cl_common.read_queue" % fname)
        for r in recs:
            why = CC.check_arm_line(r)
            if why:
                stop("the analyzer refuses %s:%d: %s" % (fname, r["lineno"], "; ".join(why)))
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        print("%-26s %3d  %s  %s" % (fname, len(lines), sha, "written" if on_disk is None else "unchanged"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
