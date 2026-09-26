"""Carrying-leg round, Part 2 tooling: write the SIX stage queues from the pre-registered
arm table (outputs/_cl_tooling_spec.txt sections C and D; design outputs/carryleg_part1.txt
9.5-9.6) and the frozen seed sets.

  _cl_s1_queue.txt      stage 1 stock: rb clGC a/b/c/s; clB C13, clC C13, clC U30         60
  _cl_s1_crn_queue.txt  stage 1 CRN:   clKC U30                                           30
  _cl_s2_queue.txt      stage 2 stock: clE2 clH clSN clA on C13                           52
  _cl_s2_crn_queue.txt  stage 2 CRN:   clKC clKE2 clKH clKA on C13                        52
  _cl_s3_queue.txt      stage 3 stock: rb clGE2 clGH clGSN clGA a/b/c/s; clC N30+RB7;
                        clE2 clH clSN clA U30+N30+RB7; clOC clOA C13+U30                 407
  _cl_s3_crn_queue.txt  stage 3 CRN:   clKC N30+RB7; clKE2 clKH clKA U30+N30+RB7         238

REVIEW AMENDMENTS (2026-09-26; each departs from the spec D text, which needs amending):
  R1 the combination arm clA2/clKA2 (a fix dropped, >= 2 still pass) ALSO runs C13 (stock
     and CRN): clA's C13 runs were in stage 2 and the combination has none, yet G3/G4 need
     its C13 comparison and G5 needs its stock C13 harness pair of each rbgate tuple (else
     every regression there is an unclassifiable NEW FAILURE). Design 9.5 already costs
     the combination re-run at "~150 runs" = 80 stock + 73 CRN, i.e. with C13.
  R2 --drop needs an explicit --offarm keep|combo (D-4's mechanic-OFF arm is chosen,
     never defaulted to a combination that will not ship).
  R3 RB7 CRN lines: clKC and every live CRN arm also run RB7 (+28 lines), so a stage-3
     "longer on a changed fire" leg on an RB7 tuple - where MODE 1/2 is recorded to change
     the fire (design 9.2: east 111, 222, 909) - reaches the maintainer WITH its CRN
     comparison (D-3). RB7 stays a G5 instrument: never pooled, never in G3.
  R9 rb shards are queued FIRST in each stock file: the pool launches first-in-first-out
     and a shard runs ~2.45 ks, so queued last they add a tail. Order changes no result.
  (+ G1(c)/(d) preconditions, the base worktree's cleanliness, tracked hits judged by the
   owner + VALID rule, the rbcompare-glob family check, the stage-3 flag inference.)

Order is deterministic: stage by stage; in each stock file the rb shards a/b/c/s first
(arm by arm), then the ff lines arm by arm in the spec table order, set C13 then U30 then
N30 then RB7, the tuples of each set in their frozen order. Files are UTF-8 with LF line
endings (a CR in a queue field breaks argparse - windows-bash-tool-gotchas).

queue line  kind|tag|repo|wind|roles|seeds|steps|extra        (roles: half | default)
  ff  steps 360, extra "--uav-actions --set BATCH_SIZE=360 [--set FM2P_CRN=1] [--set K=V ...]"
      (FM2P_CRN=1 on, and only on, the CRN files; repo E:/Projects/SAS, except clB:
      E:/Projects/SAS_wt/base6160438)
  rb  steps 240, roles half, seeds a comma list, extra "[--set K=V ...]"

BEFORE anything is written, in this order (every failure is a SystemExit naming it):
  1. the seed freeze checks (outputs/_cl_seedcheck.py, spec E); U30 and N30 come from it;
  2. every generated line is checked: field shape; the common flags on every ff line;
     FF_EXIT_LEG_SERVED=2 REFUSED on any line (D-1), MODE only 0/1/2, HOLD only 0/1;
     no FM2P_ key on a stock or rb line; exactly FM2P_CRN=1 on every CRN line; every
     other --set key declared ("^KEY = ") in common_fixed_variables.py of the line's repo;
     AND against the analyzer's own table (outputs/_cl_common.py, imported - it lists no
     directory): check_arm_line, the instrument vs the file, the tuple in a frozen set
     (seed_sets, whose C13/RB7 must equal this file's), every non-control arm's control
     (CONTROL_OF) queued, every non-control stock arm a GATE_ARMS row. A tag the analyzer
     would refuse therefore STOPs here, before a wave;
  3. recorded provenance: each clC U30 line equals the recorded uhD line of
     outputs/_uh_queue.txt with only the tag changed (G1(b)); each clC C13+U30 line equals
     the recorded ugD line of outputs/_ug_queue.txt but for the tag, steps 240 and the
     BATCH_SIZE=360 pair (G1(c)); each clKC U30 line likewise equals the recorded ugKD line
     of outputs/_ug_crn_queue.txt (G1(d)); each clGC shard line equals the recorded ugGD
     line of outputs/_ug_rbD_queue.txt with only the tag changed (G1(e)); every recorded
     reference file those comparisons read exists (opened by name, nothing listed); the
     base worktree is at 6160438 AND clean (git status --porcelain -uno empty);
  4. no run name repeats across the six files and the four sets share no tuple; without
     --drop, the line counts equal the ones above (60/30, 52/52, 407/238);
  5. TAG COLLISIONS for the tags of the stages being written: no entry of outputs/ or
     outputs/_ffr_logs/ (both listed NON-recursively, the quarantine entry skipped by
     name before anything else) may start with _ffr_<tag>_ / <tag>_ /
     _rblatch_camp2_<tag>_ / _ffr_rb_<tag>. (case-insensitive: NTFS is), nor, for every
     rb family written, with _ffr_rbcompare.py's glob _rblatch_camp2_<family> or that of
     a shorter family it extends (clGA for clGA2: `--new clGA` would merge clGA2 shards).
     A hit is allowed only if it is an expected output file of a line that stands,
     byte-identical, both in a stage queue file of THIS round already on disk and in its
     regeneration, AND outputs/_cl_validate.py --one reports that run VALID. A TRACKED hit
     (git ls-files) is judged by the same rule and must also exist in the working tree
     (else a run would recreate a tracked file - the mgD lesson). Anything else - a
     foreign file, a .tmp, a line that changed - STOPs.
  6. an existing queue file is left untouched when its content is identical; it is
     rewritten only if no output of any of its old lines exists; a stage file that is not
     being written must, if present, equal its regeneration.
Then each file is written (tmp + os.replace) and its line count and sha256 are printed,
and a STAGE-3 FLAGS line (record it in the prereg).

--drop TAG (repeatable or comma list; TAG in clE2 clH clSN clA): an arm halted by the
stage-2 screen leaves stage 3 with its stock, CRN and rb lines. If a FIX arm is dropped,
clA/clKA/clGA are replaced by the combination of the still-passing fixes, tags
clA2/clKA2/clGA2 - only if at least two fixes still pass (one would duplicate its single
arm) - and clA2/clKA2 run C13 + U30 + N30 + RB7 (R1). Dropping clA alone removes the
combination (clA failing while every fix passes singly goes to the maintainer).
--offarm keep|combo: REQUIRED with any --drop and refused without one (R2).
  keep   clOA unchanged: OFF + MODE=2 HOLD=1 SERVED=1 - after a drop NOT the configuration
         that would ship; a NOTE says so.
  combo  clOA replaced by clOM = OFF + the switches of clA2, C13 + U30 (needs clA2). clOM
         must be registered in outputs/_cl_common.py (ARMS, CONTROL_OF -> clOC, GATE_ARMS)
         and the spec amended, or step 2 STOPs.
With --only-stage 1|2, --drop/--offarm only describe the stage-3 files already on disk
(which must equal their regeneration). A stage-3 mismatch STOP names the flags whose
regeneration DOES equal the files on disk.
--only-stage N writes only stage N's two files (the others are still regenerated in
memory and must equal any copy on disk).
--selftest-outdir / --selftest-scandir / --selftest-validator / --selftest-tracked:
SELF-TEST ONLY - redirect the queue directory, the directory listed by the collision
check, the validator, and the tracked-file list (a file of repo-relative paths, one per
line, used instead of `git ls-files`).

QUARANTINE: outputs/_firemech_rewound_20260914/ is never read, listed or traversed. The
only listings are os.listdir of outputs/ and outputs/_ffr_logs/ (entry named QUAR skipped
first) and `git ls-files` (index only) with ':(exclude)outputs/_firemech_rewound_20260914'.
Recorded reference files are opened by explicit name only.

usage: .venv/Scripts/python.exe -B outputs/_cl_queue.py [--only-stage 1|2|3]
                                   [--drop TAG ... --offarm keep|combo]
"""
import argparse
import hashlib
import itertools
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _cl_seedcheck  # noqa: E402
import _cl_common as CC  # noqa: E402  (pure: lists no directory, writes nothing)

QUAR = "_firemech_rewound_20260914"
REPO = "E:/Projects/SAS"
BASE = "E:/Projects/SAS_wt/base6160438"
BASE_COMMIT = "6160438"
FF_STEPS, RB_STEPS = 360, 240
PREFIX_STEPS = 240          # the recorded ugD / ugKD references (G1(c)/(d))
COMMON = "--uav-actions --set BATCH_SIZE=360"
BATCH = ("--set", "BATCH_SIZE=%d" % FF_STEPS)
CRN = ("FM2P_CRN", "1")

C13 = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("east", "default", s) for s in (101, 202, 303)])
RB7 = [("east", "half", s) for s in (111, 222, 333, 444, 606, 808, 909)]
SHARDS = (("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
          ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505"))

MODE2 = ("FF_EXIT_LEG_MODE", "2")
HOLD1 = ("FF_EXIT_LEG_HOLD", "1")
SERVED1 = ("FF_EXIT_LEG_SERVED", "1")
OFF = (("FF_FIREFIGHT_EXTINGUISH", "0"), ("FF_FIREFIGHT_FIREBREAK", "0"))
ALLOWED_SWITCH = {"FF_EXIT_LEG_MODE": ("0", "1", "2"), "FF_EXIT_LEG_HOLD": ("0", "1"),
                  "FF_EXIT_LEG_SERVED": ("0", "1")}
# (fix, stock tag, CRN tag or None, rb tag prefix, switch) in spec table order
FIXES = (("MODE", "clE2", "clKE2", "clGE2", MODE2),
         ("HOLD", "clH", "clKH", "clGH", HOLD1),
         ("SERVED", "clSN", None, "clGSN", SERVED1))
DROPPABLE = ("clE2", "clH", "clSN", "clA")
OFFARM = ("keep", "combo")
OFF_COMBO_TAG = "clOM"      # R2: the mechanic-OFF twin of clA2 (--offarm combo)
# every rb family this tool can write (the _ffr_rbcompare.py glob is _rblatch_camp2_<family>*)
RB_FAMILIES = ("clGC", "clGE2", "clGH", "clGSN", "clGA", "clGA2")

FILES = {1: ("_cl_s1_queue.txt", "_cl_s1_crn_queue.txt"),
         2: ("_cl_s2_queue.txt", "_cl_s2_crn_queue.txt"),
         3: ("_cl_s3_queue.txt", "_cl_s3_crn_queue.txt")}
ALL_FILES = [f for s in (1, 2, 3) for f in FILES[s]]
EXPECTED = {"_cl_s1_queue.txt": 60, "_cl_s1_crn_queue.txt": 30,
            "_cl_s2_queue.txt": 52, "_cl_s2_crn_queue.txt": 52,
            "_cl_s3_queue.txt": 407, "_cl_s3_crn_queue.txt": 238}


def stop(msg):
    raise SystemExit("CL_QUEUE STOP: " + msg)


def rr(roles):
    return "def" if roles == "default" else roles


# ---------------------------------------------------------------- building ----
def ff_line(tag, tup, switches, crn=False, repo=REPO):
    w, r, s = tup
    extra = COMMON
    for k, v in ((CRN,) if crn else ()) + tuple(switches):
        extra += " --set %s=%s" % (k, v)
    return "ff|%s|%s|%s|%s|%d|%d|%s" % (tag, repo, w, r, s, FF_STEPS, extra)


def rb_lines(prefix, switches):
    extra = " ".join("--set %s=%s" % kv for kv in switches)
    return ["rb|%s%s|%s|%s|half|%s|%d|%s" % (prefix, sfx, REPO, wind, seeds, RB_STEPS, extra)
            for sfx, wind, seeds in SHARDS]


def combination(drop):
    """-> (stock, crn, rb tags, switches) of stage 3's combination arm, or None; + notes."""
    notes = []
    failed = [fx for fx in FIXES if fx[1] in drop]
    passing = [fx for fx in FIXES if fx[1] not in drop]
    if not failed:
        if "clA" in drop:
            notes.append("clA dropped while every single fix still stands: no combination arm "
                         "in stage 3 (a clA failure with all fixes passing singly goes to the maintainer)")
            return None, notes
        return ("clA", "clKA", "clGA", tuple(fx[4] for fx in FIXES)), notes
    names = "+".join(fx[0] for fx in passing) or "none"
    if len(passing) < 2:
        notes.append("fix(es) %s dropped: the still-passing set (%s) has fewer than 2 fixes, so "
                     "clA is removed and NO clA2 is written" % ([fx[1] for fx in failed], names))
        return None, notes
    notes.append("fix(es) %s dropped: clA/clKA/clGA replaced by clA2/clKA2/clGA2 = %s, which run "
                 "C13 + U30 + N30 + RB7 (stock and CRN; R1)" % ([fx[1] for fx in failed], names))
    return ("clA2", "clKA2", "clGA2", tuple(fx[4] for fx in passing)), notes


def build(seeds, drop, offarm=None):
    """-> ({file: [lines]}, sets, notes). SystemExit on an invalid --drop/--offarm pairing."""
    if drop and offarm not in OFFARM:
        stop("--drop %s needs an explicit --offarm keep|combo (D-4; R2): keep = clOA unchanged "
             "(OFF + MODE=2 HOLD=1 SERVED=1 - after a drop NOT the configuration that would ship); "
             "combo = %s = OFF + the combination arm clA2's switches (needs clA2; %s must be "
             "registered in _cl_common)" % (",".join(drop), OFF_COMBO_TAG, OFF_COMBO_TAG))
    if not drop and offarm is not None:
        stop("--offarm is meaningful only with --drop (without one clOA is the combination that ships)")
    sets = {"C13": C13, "U30": seeds["U30"], "N30": seeds["N30"], "RB7": RB7}

    def arm(tag, switches, names, crn=False, repo=REPO):
        return [ff_line(tag, t, switches, crn, repo) for n in names for t in sets[n]]

    allfix = tuple(fx[4] for fx in FIXES)
    q = {}
    q["_cl_s1_queue.txt"] = (rb_lines("clGC", ()) + arm("clB", (), ["C13"], repo=BASE)
                             + arm("clC", (), ["C13", "U30"]))
    q["_cl_s1_crn_queue.txt"] = arm("clKC", (), ["U30"], crn=True)
    s2 = []
    for _fx, tag, _k, _g, sw in FIXES:
        s2 += arm(tag, (sw,), ["C13"])
    q["_cl_s2_queue.txt"] = s2 + arm("clA", allfix, ["C13"])
    s2k = arm("clKC", (), ["C13"], crn=True)
    for _fx, _t, ktag, _g, sw in FIXES:
        if ktag:
            s2k += arm(ktag, (sw,), ["C13"], crn=True)
    q["_cl_s2_crn_queue.txt"] = s2k + arm("clKA", allfix, ["C13"], crn=True)

    combo, notes = combination(drop)
    live = [fx for fx in FIXES if fx[1] not in drop]
    # R1: a combination that replaces clA has no stage-2 C13 runs of its own
    combo_sets = (["C13"] if combo and combo[0] != "clA" else []) + ["U30", "N30", "RB7"]
    if offarm == "combo" and not (combo and combo[0] == "clA2"):
        stop("--offarm combo needs the combination arm clA2 (a fix dropped and >= 2 fixes still "
             "passing); with --drop %s there is none - the mechanic-OFF arm for this outcome is a "
             "maintainer decision (--offarm keep keeps clOA)" % ",".join(drop))
    s3 = []
    for _fx, _t, _k, gtag, sw in live:           # R9: rb shards first
        s3 += rb_lines(gtag, (sw,))
    if combo:
        s3 += rb_lines(combo[2], combo[3])
    s3 += arm("clC", (), ["N30", "RB7"])
    for _fx, tag, _k, _g, sw in live:
        s3 += arm(tag, (sw,), ["U30", "N30", "RB7"])
    if combo:
        s3 += arm(combo[0], combo[3], combo_sets)
    s3 += arm("clOC", OFF, ["C13", "U30"])
    if offarm == "combo":
        s3 += arm(OFF_COMBO_TAG, OFF + combo[3], ["C13", "U30"])
        notes.append("--offarm combo: clOA replaced by %s = FF_FIREFIGHT_EXTINGUISH=0 "
                     "FF_FIREFIGHT_FIREBREAK=0 + %s, C13 + U30 (control clOC)"
                     % (OFF_COMBO_TAG, " ".join("%s=%s" % kv for kv in combo[3])))
    else:
        s3 += arm("clOA", OFF + allfix, ["C13", "U30"])
        if drop:
            notes.append("NOTE --offarm keep: clOA still carries MODE=2 HOLD=1 SERVED=1 - with %s "
                         "dropped that is NOT the configuration that would ship, so D-4's "
                         "mechanic-OFF evidence does not cover what ships" % ",".join(drop))
    q["_cl_s3_queue.txt"] = s3
    s3k = arm("clKC", (), ["N30", "RB7"], crn=True)          # R3: RB7 CRN
    for _fx, _t, ktag, _g, sw in live:
        if ktag:
            s3k += arm(ktag, (sw,), ["U30", "N30", "RB7"], crn=True)
    if combo:
        s3k += arm(combo[1], combo[3], combo_sets, crn=True)
    q["_cl_s3_crn_queue.txt"] = s3k
    return q, sets, notes


def flags_str(drop, offarm):
    return "--drop %s --offarm %s" % (",".join(drop), offarm) if drop else "(no --drop, no --offarm)"


def infer_stage3(seeds, disk):
    """R8: every --drop/--offarm whose stage-3 regeneration equals the stage-3 files on disk."""
    have = [f for f in FILES[3] if f in disk]
    if not have:
        return []
    found = []
    for k in range(len(DROPPABLE) + 1):
        for dr in itertools.combinations(DROPPABLE, k):
            for off in ((None,) if not dr else OFFARM):
                try:
                    q, _s, _n = build(seeds, list(dr), off)
                except SystemExit:
                    continue
                if all(q[f] == disk[f] for f in have):
                    found.append(flags_str(list(dr), off))
    return found


# ---------------------------------------------------------------- checking ----
_CFV = {}


def cfv_keys(repo):
    if repo not in _CFV:
        path = os.path.join(repo, "common_fixed_variables.py")
        if not os.path.isfile(path):
            stop("no common_fixed_variables.py at %s" % repo)
        with open(path, "rb") as f:
            text = f.read().decode("utf-8", "replace").replace("\r", "")
        _CFV[repo] = set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*) = ", text, re.M))
    return _CFV[repo]


def parse(line):
    """-> dict of the queue line's fields + sets [(k, v)] + uav-actions count."""
    if "\r" in line or "\t" in line or line != line.strip() or '"' in line or "'" in line:
        stop("bad characters or whitespace in line %r" % line)
    parts = line.split("|")
    if len(parts) != 8:
        stop("line has %d fields, want 8: %r" % (len(parts), line))
    kind, tag, repo, wind, roles, seeds, steps, extra = parts
    toks = extra.split()
    sets, ua, i = [], 0, 0
    while i < len(toks):
        if toks[i] == "--set" and i + 1 < len(toks) and "=" in toks[i + 1]:
            k, v = toks[i + 1].split("=", 1)
            sets.append((k, v))
            i += 2
        elif toks[i] == "--uav-actions":
            ua += 1
            i += 1
        else:
            stop("unexpected token %r in line %r" % (toks[i], line))
    return {"kind": kind, "tag": tag, "repo": repo, "wind": wind, "roles": roles, "seeds": seeds,
            "steps": steps, "extra": extra, "sets": sets, "ua": ua}


def run_name(p):
    if p["kind"] == "ff":
        return "%s_%s_%s_%s" % (p["tag"], p["wind"], rr(p["roles"]), p["seeds"])
    return "%s_D_%s" % (p["tag"], p["wind"])


def check_line(fname, line):
    p = parse(line)
    crn_file = "_crn_" in fname
    keys = [k for k, _v in p["sets"]]
    if len(set(keys)) != len(keys):
        stop("a --set key repeats: %r" % line)
    if p["wind"] not in ("east", "south"):
        stop("wind %r: %r" % (p["wind"], line))
    if p["kind"] == "ff":
        if p["repo"] != (BASE if p["tag"] == "clB" else REPO):
            stop("repo %r is not the arm's: %r" % (p["repo"], line))
        if p["roles"] not in ("half", "default") or not p["seeds"].isdigit():
            stop("roles/seed field: %r" % line)
        if p["steps"] != str(FF_STEPS):
            stop("ff line without --steps %d: %r" % (FF_STEPS, line))
        if (p["extra"] != COMMON and not p["extra"].startswith(COMMON + " ")) or p["ua"] != 1 \
                or not p["sets"] or p["sets"][0] != ("BATCH_SIZE", str(FF_STEPS)):
            stop("ff line without the common flags %r: %r" % (COMMON, line))
    elif p["kind"] == "rb":
        if crn_file:
            stop("rb line in a CRN queue: %r" % line)
        if p["roles"] != "half" or p["steps"] != str(RB_STEPS) or p["ua"] != 0 \
                or not re.match(r"^\d+(,\d+)*$", p["seeds"]) or p["repo"] != REPO:
            stop("rb line shape: %r" % line)
    else:
        stop("unknown kind: %r" % line)
    fm2p = {k: v for k, v in p["sets"] if k.startswith("FM2P_")}
    for k, v in p["sets"]:
        if k == "FF_EXIT_LEG_SERVED" and v == "2":
            stop("FF_EXIT_LEG_SERVED=2 REFUSED (D-1: rung 2 not built): %r" % line)
        if k in ALLOWED_SWITCH and v not in ALLOWED_SWITCH[k]:
            stop("%s=%s is not an allowed value %s: %r" % (k, v, ALLOWED_SWITCH[k], line))
        if not k.startswith("FM2P_") and k not in cfv_keys(p["repo"]):
            stop("--set %s is not declared in %s/common_fixed_variables.py: %r" % (k, p["repo"], line))
    if crn_file:
        if fm2p != {CRN[0]: CRN[1]}:
            stop("CRN line without exactly FM2P_CRN=1 (has %r): %r" % (fm2p, line))
    elif fm2p:
        stop("FM2P_ key on a stock line: %r" % line)
    return p


def arm_table_check(regen, seeds):
    """Step 2b: every line as the ANALYZER will see it (_cl_common, the RunIndex checks)."""
    sets = CC.seed_sets(checked=seeds)
    if sets["C13"] != C13 or sets["RB7"] != RB7:
        stop("C13/RB7 of this file differ from _cl_common's")
    combos, tags, n = {}, {}, 0
    for fname in ALL_FILES:
        crn_file = CC.is_crn_queue(fname)
        for i, ln in enumerate(regen[fname], 1):
            where = "%s:%d" % (fname, i)
            kind, tag, repo, wind, roles, seedf, steps, extra = ln.split("|", 7)
            s, uav = CC.parse_extra(extra, where)
            rec = dict(kind=kind, tag=tag, repo=repo, wind=wind, roles=roles, steps=int(steps),
                       extra=extra, sets=s, raw=ln, queue=fname, lineno=i)
            if kind == "ff":
                rec.update(seed=int(seedf), tup=(wind, roles, int(seedf)), uav_actions=uav)
            else:
                rec.update(seeds=seedf, seed_list=[int(x) for x in seedf.split(",")])
            why = list(CC.check_arm_line(rec, combos))
            if kind == "ff" and tag in CC.ARMS:
                inst = CC.instrument_of(s)
                if inst != CC.ARMS[tag]["instrument"] or (inst == "crn") != crn_file:
                    why.append("instrument %s in %s, the arm table says %s" % (inst, fname, CC.ARMS[tag]["instrument"]))
                if CC.set_of(rec["tup"], sets) is None:
                    why.append("tuple %s is in no frozen set" % CC.label(rec["tup"]))
                tags.setdefault(tag, fname)
            bad = CC.undeclared(s, repo)
            if bad:
                why.append("--set keys not declared in %s/common_fixed_variables.py: %s" % (repo, bad))
            if why:
                stop("%s %s does not conform to the analyzer's arm table (outputs/_cl_common.py): %s"
                     % (where, ln, "; ".join(why)))
            n += 1
    for tag, fname in sorted(tags.items()):
        arm = CC.ARMS[tag]
        if arm["kind"] == "control":
            continue
        ctl = CC.CONTROL_OF.get(tag)
        if ctl is None or ctl not in tags:
            stop("%s (%s) has no queued control in _cl_common.CONTROL_OF (%r) - the analyzer could "
                 "not judge it" % (tag, fname, ctl))
        if arm["instrument"] == "stock" and tag not in CC.GATE_ARMS:
            stop("%s is not a GATE block row (_cl_common.GATE_ARMS) - register it first" % tag)
    print("arm table: %d lines conform to outputs/_cl_common.py (check_arm_line, instrument, frozen "
          "set, declared keys); %d ff tags, every non-control one with its queued control"
          % (n, len(tags)))


def _recorded(fname):
    with open(os.path.join(HERE, fname), "rb") as f:
        text = f.read().decode("utf-8")
    out = []
    for raw in text.split("\n"):
        parts = raw.rstrip("\r").split("|")
        if len(parts) == 8:
            out.append(parts)
    return out


def _index(rows, tag, fname):
    idx = {}
    for p in rows:
        if p[1] != tag:
            continue
        key = (p[3], p[4], p[5])
        if key in idx:
            stop("%s holds two %s lines for %s - ambiguous reference" % (fname, tag, "/".join(key)))
        idx[key] = p
    return idx


def _minus_batch(extra):
    toks = extra.split()
    for i in range(len(toks) - 1):
        if (toks[i], toks[i + 1]) == BATCH:
            return " ".join(toks[:i] + toks[i + 2:])
    stop("no %s in %r" % (" ".join(BATCH), extra))


def _prefix_match(fname, rtag, lines, want_n, label):
    """G1(c)/(d): each line == the recorded 240-step line but for tag, steps and BATCH_SIZE."""
    idx = _index(_recorded(fname), rtag, fname)
    order, n = [], 0
    for ln in lines:
        parts = ln.split("|")
        rec = idx.get((parts[3], parts[4], parts[5]))
        ok = (rec is not None and rec[0] == parts[0] == "ff" and rec[2] == parts[2]
              and rec[6] == str(PREFIX_STEPS) and rec[7] == _minus_batch(parts[7]))
        if not ok:
            stop("%s line is not the recorded %s line of outputs/%s but for the tag, steps %d and "
                 "the BATCH_SIZE pair: %r vs %r" % (label, rtag, fname, PREFIX_STEPS, ln, rec))
        order.append((parts[3], parts[4], parts[5]))
        n += 1
    if n != want_n:
        stop("found %d %s lines matched to %s, want %d" % (n, label, rtag, want_n))
    rec_order = [k for k in idx if k in set(order)]
    return n, rec_order == order


def recorded_provenance(q, u30):
    """G1(b)/(c)/(d)/(e) preconditions against the recorded queue files, and the recorded
    reference files those comparisons read (opened by name, nothing listed)."""
    def same_but_tag(a, b):
        return a[:1] + a[2:] == b[:1] + b[2:]

    uhd = _index(_recorded("_uh_queue.txt"), "uhD", "_uh_queue.txt")
    u30keys = {(w, r, str(s)) for w, r, s in u30}
    c13keys = {(w, r, str(s)) for w, r, s in C13}
    s1 = [ln.split("|") for ln in q["_cl_s1_queue.txt"]]
    n = 0
    for parts in s1:
        if parts[1] != "clC" or (parts[3], parts[4], parts[5]) not in u30keys:
            continue
        rec = uhd.get((parts[3], parts[4], parts[5]))
        if rec is None or not same_but_tag(rec, parts):
            stop("clC U30 line is not the recorded uhD line with the tag changed: %r vs %r" % ("|".join(parts), rec))
        n += 1
    if n != 30:
        stop("found %d clC U30 lines matched to uhD, want 30" % n)
    clc = ["|".join(p) for p in s1 if p[1] == "clC" and (p[3], p[4], p[5]) in (u30keys | c13keys)]
    nc, _o = _prefix_match("_ug_queue.txt", "ugD", clc, len(C13) + 30, "clC C13+U30")
    clkc = [ln for ln in q["_cl_s1_crn_queue.txt"] if ln.split("|")[1] == "clKC"]
    nd, same_order = _prefix_match("_ug_crn_queue.txt", "ugKD", clkc, 30, "clKC U30")
    ugd = {p[1]: p for p in _recorded("_ug_rbD_queue.txt") if p[0] == "rb"}
    m = 0
    for parts in s1:
        if parts[0] != "rb":
            continue
        rec = ugd.get("ugGD" + parts[1][len("clGC"):])
        if rec is None or not same_but_tag(rec, parts):
            stop("clGC shard line is not the recorded ugGD line with the tag changed: %r vs %r" % ("|".join(parts), rec))
        m += 1
    if m != 4:
        stop("found %d clGC shard lines matched to ugGD, want 4" % m)
    # the recorded reference files themselves (explicit names only)
    want = [("uhD", u30), ("ugD", list(C13) + list(u30)), ("ugKD", u30)]
    missing, have = [], {}
    for tag, tups in want:
        for w, r, s in tups:
            name = "_ffr_%s_%s_%s_%d.json" % (tag, w, rr(r), s)
            if os.path.isfile(os.path.join(HERE, name)):
                have[tag] = have.get(tag, 0) + 1
            else:
                missing.append(name)
    for sfx, wind, _seeds in SHARDS:
        name = "_rblatch_camp2_ugGD%s_D_%s.json" % (sfx, wind)
        if os.path.isfile(os.path.join(HERE, name)):
            have["ugGD"] = have.get("ugGD", 0) + 1
        else:
            missing.append(name)
    if missing:
        stop("recorded reference file(s) missing - G1 could not be evaluated: %s" % missing[:10])
    print("provenance: G1(b) 30/30 clC U30 == recorded uhD (_uh_queue.txt) but for the tag; "
          "G1(c) %d/%d clC C13+U30 == recorded ugD (_ug_queue.txt) but for tag, steps %d, BATCH_SIZE; "
          "G1(d) %d/30 clKC U30 == recorded ugKD (_ug_crn_queue.txt) likewise (same order: %s); "
          "G1(e) 4/4 clGC shards == recorded ugGD (_ug_rbD_queue.txt) but for the tag"
          % (nc, len(C13) + 30, PREFIX_STEPS, nd, "yes" if same_order else "no"))
    print("recorded reference files present: %s"
          % ", ".join("%s %d" % (t, have.get(t, 0)) for t in ("uhD", "ugD", "ugKD", "ugGD")))


def base_worktree():
    if not os.path.isdir(BASE):
        stop("base worktree %s is missing" % BASE)
    head = subprocess.run(["git", "-C", BASE, "rev-parse", "HEAD"], capture_output=True, text=True)
    if head.returncode != 0 or not head.stdout.strip().startswith(BASE_COMMIT):
        stop("base worktree %s is not at %s (HEAD %r)" % (BASE, BASE_COMMIT, head.stdout.strip()))
    st = subprocess.run(["git", "-C", BASE, "status", "--porcelain", "-uno"], capture_output=True, text=True)
    if st.returncode != 0 or st.stdout.strip():
        stop("base worktree %s is not clean (git status --porcelain -uno): %r - clB would fail G1(a)"
             % (BASE, (st.stdout.strip() or st.stderr.strip())[:300]))
    mine = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    br = subprocess.run(["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    print("repo %s HEAD %s (%s); base worktree %s HEAD %s, clean (0 tracked changes)"
          % (REPO, mine.stdout.strip(), br.stdout.strip(), BASE, head.stdout.strip()[:12]))


# --------------------------------------------------------------- collisions ----
def listing(scandir):
    """{(dirkey, lower basename): basename} of outputs/ and outputs/_ffr_logs/, NON-recursive."""
    out = {}
    for dirkey, d in (("outputs", scandir), ("_ffr_logs", os.path.join(scandir, "_ffr_logs"))):
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):      # NON-recursive
            if n == QUAR:            # skipped by name before anything else
                continue
            out[(dirkey, n.lower())] = n
    return out


def tracked(selftest_file=""):
    """Repo-relative paths of tracked files directly in outputs/ or outputs/_ffr_logs/."""
    if selftest_file:
        with open(selftest_file, "rb") as f:
            raw = [p.strip() for p in f.read().decode("utf-8").replace("\r", "").split("\n")]
    else:
        res = subprocess.run(["git", "-C", ROOT, "ls-files", "-z", "--", "outputs",
                              ":(exclude)outputs/" + QUAR], capture_output=True, check=True)
        raw = res.stdout.decode("utf-8", "replace").split("\0")
    out = []
    for p in raw:
        if not p or QUAR in p:
            continue
        d = os.path.dirname(p)
        if d in ("outputs", "outputs/_ffr_logs"):
            out.append(p)
    return out


def tag_prefixes(tag):
    return ["_ffr_%s_" % tag, "%s_" % tag, "_rblatch_camp2_%s_" % tag, "_ffr_rb_%s." % tag]


def rb_glob_prefixes(families):
    """R4: _ffr_rbcompare.py merges _rblatch_camp2_<family>*_D_<wind>.json, so for every rb
    family written, that glob and the glob of every shorter family it extends (clGA for
    clGA2) may hold only this round's owned VALID outputs."""
    out = set()
    for f in families:
        for q in RB_FAMILIES + (f,):
            if f.startswith(q):
                out.add("_rblatch_camp2_%s" % q)
    return sorted(out)


def expected_files(p):
    """[(dirkey, basename)] a finished run of this line leaves (pool + sidecar names)."""
    n = run_name(p)
    if p["kind"] == "ff":
        return [("outputs", "_ffr_%s.json" % n), ("outputs", "_ffr_%s.stdout.txt" % n),
                ("outputs", "_ffr_%s.clobs.json" % n),
                ("_ffr_logs", "%s.out" % n), ("_ffr_logs", "%s.err" % n)]
    return [("outputs", "_rblatch_camp2_%s.json" % n), ("outputs", "_ffr_rb_%s.log" % p["tag"])]


def line_file_prefixes(p):
    """[(dirkey, prefix)] - anything a run of this line (finished or not) may leave."""
    n = run_name(p)
    if p["kind"] == "ff":
        return [("outputs", "_ffr_%s." % n), ("_ffr_logs", "%s." % n)]
    return [("outputs", "_rblatch_camp2_%s." % n), ("outputs", "_ffr_rb_%s." % p["tag"])]


def read_disk(outdir):
    disk = {}
    for fname in ALL_FILES:
        path = os.path.join(outdir, fname)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8")
        if "\r" in text or not text.endswith("\n"):
            stop("%s on disk is not LF-terminated LF text" % path)
        disk[fname] = text[:-1].split("\n")
    return disk


def validate_one(validator, qpath, name, cache):
    key = (qpath, name)
    if key not in cache:
        if not os.path.isfile(validator):
            stop("an earlier-stage output of %s exists but the validator %s is missing - cannot "
                 "confirm it is a VALID run of the identical queue line" % (name, validator))
        res = subprocess.run([sys.executable, "-B", validator, "--queue", qpath, "--one", name],
                             cwd=ROOT, capture_output=True, text=True)
        lines = [ln.strip() for ln in res.stdout.replace("\r", "").split("\n") if ln.strip()]
        cache[key] = (res.returncode == 0 and ("VALID " + name) in lines, lines[-1:] if lines else res.stderr[-200:])
    return cache[key]


def collisions(regen, disk, stages, outdir, scandir, validator, tr, s3_hint):
    ents = listing(scandir)
    parsed = [parse(ln) for s in stages for f in FILES[s] for ln in regen[f]]
    tags = sorted({p["tag"] for p in parsed})
    families = sorted({p["tag"][:-1] for p in parsed if p["kind"] == "rb"})
    globs = rb_glob_prefixes(families)
    prefixes = tuple(sorted({pf.lower() for t in tags for pf in tag_prefixes(t)} | {g.lower() for g in globs}))
    hits = sorted((dk, name) for (dk, low), name in ents.items() if low.startswith(prefixes))
    thits = sorted(p for p in tr if os.path.basename(p).lower().startswith(prefixes))
    for p in thits:
        dk = "outputs" if os.path.dirname(p) == "outputs" else "_ffr_logs"
        if (dk, os.path.basename(p).lower()) not in ents:
            stop("TRACKED %s carries a tag prefix of this round but is not in the working tree - a "
                 "run would recreate a tracked file (the mgD lesson)" % p)
    # owners: expected output files of every line of this round's queue files on disk
    owner = {}
    for fname, lines in disk.items():
        for ln in lines:
            p = parse(ln)
            for dk, base in expected_files(p):
                k = (dk, base.lower())
                if k in owner and owner[k][1] != ln:
                    stop("two on-disk queue lines own %s: %r / %r" % (base, owner[k][1], ln))
                owner[k] = (fname, ln, run_name(p))
    allowed_runs, cache = {}, {}
    for dk, name in hits:            # every tracked hit is also here (it exists on disk)
        own = owner.get((dk, name.lower()))
        if own is None:
            stop("TAG COLLISION: %s/%s starts with a tag prefix or rbcompare glob of this round and "
                 "is not an output of any line in this round's queue files on disk" % (dk, name))
        fname, ln, rn = own
        if ln not in set(regen[fname]):
            stop("%s/%s belongs to a line of %s on disk that the regeneration no longer contains: %r%s"
                 % (dk, name, fname, ln, s3_hint if fname in FILES[3] else ""))
        ok, why = validate_one(validator, os.path.join(outdir, fname), rn, cache)
        if not ok:
            stop("%s/%s: its run %s is not VALID (%s)" % (dk, name, rn, why))
        allowed_runs.setdefault(fname, set()).add(rn)
    # a queue file on disk that is being rewritten with different content must have no outputs
    for s in stages:
        for fname in FILES[s]:
            if fname in disk and disk[fname] != regen[fname]:
                for ln in disk[fname]:
                    for dk, pf in line_file_prefixes(parse(ln)):
                        low = pf.lower()
                        if any(k[0] == dk and k[1].startswith(low) for k in ents):
                            stop("%s differs from its regeneration but its line %r already has "
                                 "output files - refusing to rewrite%s"
                                 % (fname, ln, s3_hint if fname in FILES[3] else ""))
    print("tag collisions: %d tags, %d prefixes (%d rbcompare globs), %d entries listed (outputs/ + "
          "_ffr_logs/, non-recursive), %d tracked checked (%d tracked hit(s)); %d hit(s)%s"
          % (len(tags), len(prefixes), len(globs), len(ents), len(tr), len(thits), len(hits),
             "" if not hits else ", all outputs of VALID runs of identical lines in this round's queue "
             "files on disk: %s" % {k: len(v) for k, v in sorted(allowed_runs.items())}))


# --------------------------------------------------------------------- main ----
def summary(fname, lines, setname):
    groups = []
    for ln in lines:
        p = parse(ln)
        if p["kind"] == "rb":
            key = ("rb", re.sub(r"[abcs]$", "", p["tag"]), "shards")
        else:
            key = ("ff", p["tag"], setname[(p["wind"], p["roles"], int(p["seeds"]))])
        if groups and groups[-1][0] == key:
            groups[-1][1] += 1
        else:
            groups.append([key, 1])
    return ", ".join("%s%s %s %d" % ("rb " if k[0] == "rb" else "", k[1], k[2], c) for k, c in groups)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only-stage", type=int, choices=(1, 2, 3))
    ap.add_argument("--drop", action="append", default=[])
    ap.add_argument("--offarm", choices=OFFARM)
    ap.add_argument("--selftest-outdir", default="")
    ap.add_argument("--selftest-scandir", default="")
    ap.add_argument("--selftest-validator", default="")
    ap.add_argument("--selftest-tracked", default="")
    a = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    drop = []
    for d in a.drop:
        drop += [x.strip() for x in d.split(",") if x.strip()]
    bad = [d for d in drop if d not in DROPPABLE]
    if bad:
        stop("--drop accepts only %s, got %s" % (list(DROPPABLE), bad))
    drop = sorted(set(drop), key=DROPPABLE.index)
    outdir = a.selftest_outdir or HERE
    scandir = a.selftest_scandir or HERE
    validator = a.selftest_validator or os.path.join(HERE, "_cl_validate.py")
    if a.selftest_outdir or a.selftest_scandir or a.selftest_validator or a.selftest_tracked:
        print("SELF-TEST PATHS IN USE: outdir=%s scandir=%s validator=%s tracked=%s"
              % (outdir, scandir, validator, a.selftest_tracked or "git ls-files"))
    stages = [a.only_stage] if a.only_stage else [1, 2, 3]
    if drop and a.only_stage in (1, 2):
        print("--drop/--offarm with --only-stage %d: they describe the stage-3 files on disk only"
              % a.only_stage)

    # 1. seed freeze checks first
    seeds = _cl_seedcheck.run_checks()
    print("seed checks passed")

    # 2-4. build and check every line of all six files
    regen, sets, notes = build(seeds, drop, a.offarm)
    for n in notes:
        print(n)
    setname = {}
    for sname, tups in sets.items():
        for t in tups:
            if t in setname:
                stop("tuple %s is in both %s and %s" % (t, setname[t], sname))
            setname[t] = sname
    names = {}
    for fname in ALL_FILES:
        for ln in regen[fname]:
            p = check_line(fname, ln)
            rn = run_name(p)
            if rn in names:
                stop("run name %s repeats (%s and %s)" % (rn, names[rn], fname))
            names[rn] = fname
    arm_table_check(regen, seeds)
    if not drop:
        for fname in ALL_FILES:
            if len(regen[fname]) != EXPECTED[fname]:
                stop("%s has %d lines, the table says %d" % (fname, len(regen[fname]), EXPECTED[fname]))
    recorded_provenance(regen, seeds["U30"])
    base_worktree()

    # 5-6. on-disk state and tag collisions
    disk = read_disk(outdir)
    s3_hint = ""
    if any(f in disk and disk[f] != regen[f] for f in FILES[3]):
        found = infer_stage3(seeds, disk)
        s3_hint = ("; the stage-3 files on disk are the regeneration of: %s (this run: %s)"
                   % (" OR ".join(found) if found else "NO --drop/--offarm (foreign or hand-edited)",
                      flags_str(drop, a.offarm)))
        if 3 in stages:
            print("NOTE stage 3 on disk differs from this run's regeneration%s" % s3_hint)
    for s in (1, 2, 3):
        if s in stages:
            continue
        for fname in FILES[s]:
            if fname in disk and disk[fname] != regen[fname]:
                stop("%s on disk differs from its regeneration (stage %d is not being written)%s"
                     % (fname, s, s3_hint if s == 3 else ""))
    tr = tracked(a.selftest_tracked)
    collisions(regen, disk, stages, outdir, scandir, validator, tr, s3_hint)

    # write
    for s in stages:
        for fname in FILES[s]:
            path = os.path.join(outdir, fname)
            body = ("\n".join(regen[fname]) + "\n").encode("utf-8")
            if fname in disk and disk[fname] == regen[fname]:
                state = "unchanged"
            else:
                tmp = path + ".tmp"
                if os.path.exists(tmp):
                    stop("%s exists (a leftover); remove it by hand after checking it" % tmp)
                with open(tmp, "wb") as f:
                    f.write(body)
                os.replace(tmp, path)
                state = "rewritten" if fname in disk else "written"
            with open(path, "rb") as f:
                got = f.read()
            if got != body:
                stop("%s does not read back as written" % path)
            print("%-22s %-9s %4d lines  sha256 %s" % (fname, state, len(regen[fname]),
                                                        hashlib.sha256(got).hexdigest()))
            print("    %s" % summary(fname, regen[fname], setname))
    ff_n = sum(1 for s in stages for f in FILES[s] for ln in regen[f] if ln.startswith("ff|"))
    rb_n = sum(1 for s in stages for f in FILES[s] for ln in regen[f] if ln.startswith("rb|"))
    print("stages %s: %d ff lines (all with %r, steps %d), %d rb shard lines"
          % (stages, ff_n, COMMON, FF_STEPS, rb_n))
    s3_state = ("written by this run" if 3 in stages else
                "on disk, equal to this regeneration" if any(f in disk for f in FILES[3]) else "not on disk")
    print("STAGE-3 FLAGS: %s  (stage 3 %s; record in the prereg)" % (flags_str(drop, a.offarm), s3_state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
