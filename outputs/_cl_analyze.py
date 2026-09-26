"""Carrying-leg round, Part 2/3: THE ANALYZER (spec outputs/_cl_tooling_spec.txt section H;
design outputs/carryleg_part1.txt 9.1-9.4; maintainer answers D-1..D-10 of 2026-09-26).

  .venv/Scripts/python.exe -B outputs/_cl_analyze.py --stage 1|2|3|all [--out TXT]
                                                     [--extra-queue Q ...] [--replace]
  default --out: outputs/_cl_analysis_s<stage>.txt (s1, s2, s3, sall)
  An existing report is NEVER replaced silently (spec A4, the tag-collision lesson): the
  run is REFUSED if --out is tracked in git (git ls-files --error-unmatch, one named path)
  or if the new text differs from the file's; --replace overrides both. A rerun that
  produces the identical text leaves the file untouched.

WHAT IT READS. Only the files named by the queue files of stages 1..N (cumulative: every
stage is judged against the stage-1 controls; --stage all = 1..3), plus any --extra-queue
(e.g. the D-9 probe's), plus the RECORDED references it names explicitly (uhD, ugD, ugKD,
uhC runs; the ugGD rbgate shards), plus outputs/_cl_tolerance.txt and the frozen seed
files. Before anything else it runs the seed freeze checks (_cl_seedcheck.run_checks,
spec E) and takes U30/N30 from them.
DIRECTORY LISTINGS. This file and _cl_common.py list no directory. Two things it runs do,
NON-recursively and skipping the quarantine name by string compare first:
_cl_seedcheck.run_checks (outputs/ and outputs/_ffr_logs/ entry names; its git
`ls-files --others` carries the quarantine exclude pathspec) and the hook _cl_legs.py
(os.listdir(outputs/) for the G5 shard-glob check; its _ffr_rbcompare.py subprocess globs
outputs/_rblatch_camp2_<tag>*_D_<wind>.json).

REFUSALS (SystemExit, spec A5 / H): a queue line outside the pre-registered arm table
(_cl_common.ARMS / RB_ARMS) or without the common flags; FF_EXIT_LEG_SERVED=2 anywhere
(D-1); an FM2P_ key on a stock line or a CRN line without FM2P_CRN=1; a tuple in no frozen
set; any --set key not declared ("^KEY = ") in common_fixed_variables.py of the line's
repo (FM2P_* and CLP_* exempt); and, for every queued run, a JSON whose tag / wind / roles /
seed / steps / repo / extra_params (value TYPES compared) / fm2p state is not its line's,
or whose sidecar (<stem>.clobs.json) is missing, is not version 1 of the line's instrument,
or reports switches other than the line's (ABSENT x3 required at the 6160438 worktree).
A missing run file is a refusal too: analyse a stage only once its queues are complete.

SECTIONS
  H1  IDENTITY (G1), STOP on failure: (a) clB == clC C13 13/13 (every key but tag/repo/wall_s
      + sidecar hashes); (b) clC U30 == recorded uhD 30/30 (every key but tag/wall_s; queue
      line == uhD's line in outputs/_uh_queue.txt with the tag changed); (c) clC C13+U30 steps
      1-240 == recorded ugD 43/43 (the _uh_analyze P2 method); (d) clKC U30 steps 1-240 ==
      recorded ugKD 30/30 (fm2p excluded; fm2p.config == {"FM2P_CRN": 1} on both); (e) clGC
      shards == ugGD 4/4, evals 18/18 (wall_s dropped); (f) every clC sidecar: switches
      0/False/0 and holds, path_steps, fallback_steps, hold_starts, custody_victim_steps,
      served_by_custody_only all 0 (+ design 9.1 f: exit_leg_step_other, custody_calls,
      in_custody_calls, served_by_custody_only_not_geo all 0 - each is reached only behind
      a non-zero switch); (g) info only: clOC U30 vs recorded uhC.
  H6  OUTCOMES at cuts 240/270/300/330/360 per arm/set/instrument, from victim_steps /
      ff_steps / unreachable_escape_log (eval only as the 360 cross-check; a mismatch is a
      STOP item).
  G3  (D-10) per set per instrument, arm vs its control at 360. STOCK: loss = control
      rescued - arm rescued; FAIL if loss > T, T read from outputs/_cl_tolerance.txt and
      asserted == 2 for C13, U30 and N30; a loss of 1..T passes and is listed victim by
      victim. CRN (revised on the maintainer's ruling, carryleg_prereg.txt section 0): the
      PER-SET TOTAL, zero tolerance - FAIL if the arm's set total rescued is lower than the
      control's; per-seed moves are not a failure on their own and are reported beside the
      total (seeds down / seeds up, and every flipped victim) so a one-sided pattern shows.
      Every victim rescued in the control and not in the arm, in every comparison, is
      attributed: both fates and steps, fire-digest match up to the earlier fate, first
      differing step and what differed, and the victim's own carry (the M3 match). A lost
      victim is ATTRIBUTABLE - AUTOMATIC FAIL (design 9.4 G3 b: "its matched carry is
      longer or broken in the arm on a fire identical up to that point") - when one of its
      matched carries is, in the arm, EITHER longer (compare_legs LONGER: completed in the
      control and broken / at the horizon in the arm, or longer n, finished or not) OR
      broken differently from the control (arm leg broken, not at the horizon, with an end
      (n, cause) other than the control leg's: e.g. the control drops and the victim is
      rescued later, while HOLD keeps custody and dies, or MODE 2 dies sooner) - AND the
      fire digests are identical over [pickup, the EARLIER of the two legs' ends] (the
      point where the arm's carry became the worse one; a horizon leg ends at 360).
      clSN (no CRN arm): any stock loss goes to the maintainer.
      REQUIRED SETS per stage (spec D): stage 2 = C13, stage 3 = C13 + U30 + N30 (clOA:
      C13 + U30), in the stock instrument and, for an arm with a CRN twin, in CRN. A
      required set with no run queued is noted "<set> <inst> NOT QUEUED" and is UNTESTED,
      and UNTESTED outranks PASS (merge), so such a gate cannot read PASS.
  G4  ff_deaths at 360 per set per instrument. Where the arm is higher, every extra death
      (a unit dead in the arm run and alive in the control run of the same tuple) is
      classified M10-EDGE (it died on its own completion step, arm MODE >= 1: the mode-1
      edge), CRN-PAIR (stock only: the stock fire diverged before the death and the CRN
      pair of that tuple has no such extra death), COMPLETION-STEP-M0 (died on its own
      completion step in a MODE-0 arm - the pre-existing exit-cell edge case (i), not M10 -
      and no CRN-PAIR: to the maintainer) or UNEXPLAINED; any UNEXPLAINED -> FAIL, else any
      COMPLETION-STEP-M0 -> TO-MAINTAINER. clSN (no CRN twin, design 9.4) higher on stock ->
      TO-MAINTAINER whatever the classes (the EXTRA lines are the attribution). Required
      sets as in G3.
  HOOK  outputs/_cl_legs.py (below), if present.
  GATE  per fix arm (clE2 clH clSN clA clE1 clA2 clOA): G1..G5 PASS / FAIL / TO-MAINTAINER /
      UNTESTED, the hook's extra rows, then the STOP items and the maintainer items.
Output is deterministic: reruns on the same files print byte-identical text.
EXIT: 0 report written, no STOP item; 2 report written WITH STOP items (G1 failure, a
cross-check mismatch, an analyzer defect reported by the hook, an invariant breach);
SystemExit(message) = refused before any report.

======================================================================================
HOOK CONTRACT - outputs/_cl_legs.py (written by a second agent; OPTIONAL)
======================================================================================
If outputs/_cl_legs.py exists it is loaded FROM THAT PATH (importlib spec_from_file_location,
registered as sys.modules["_cl_legs"]; a module already there is reused only if it is that
same file - never a cached or shadowing _cl_legs from elsewhere on sys.path) after H1 (only
when G1 passed), H6, G3 and G4, and its module-level function

    sections(ctx) -> dict | None

is called once. It writes its own tables (spec H2-H5, H7-H13: legs/M1, M3 drops, M-HOLD,
M4 custody markings, M6/M7 exposure, M10, M11, invariants, engagement, G5 rbgate) through
ctx.say(), and returns None or

    {"gates": {ARM: {GATE: (VERDICT, [note, ...]), ...}, ...}}

  ARM      a stock fix tag from ctx.GATE_ARMS ("clE2", "clH", "clSN", "clA", "clE1",
           "clA2", "clOA"); its CRN twin's evidence belongs under the stock tag.
  GATE     "G2" and "G5" fill those columns; any other key (e.g. "INV", "ENG") is printed
           as an extra row under the arm. "G1", "G3", "G4" are this file's and may not be
           returned (ANALYZER DEFECT).
  VERDICT  "PASS" | "FAIL" | "TO-MAINTAINER" | "UNTESTED" (anything else: ANALYZER DEFECT).
It may also call ctx.stop(msg) (a STOP item: printed, exit 2) and
ctx.to_maintainer(arm, msg) (routed to the maintainer, D-3/D-9/G2 one-instrument rises).
A missing _cl_legs.py leaves G2 and G5 UNTESTED ("_cl_legs.py absent").

ctx (class Ctx below) - everything is read-only; never mutate a returned run dict:
  ctx.C                   the _cl_common module: legs(), match_legs(), compare_legs(),
                          leg_key(), leg_str(), first_diff(), first_diff_detail(),
                          fire_identical(), series_equal(), Burn, neighbours(),
                          on_boundary(), edge_dist(), exit_target(), md(), ff_row(),
                          bind_row(), victim_row(), row_after(), row_at_start(),
                          statuses(), unassigns_at(), end_cause(), completions_of(),
                          victim_fate(), fate_str(), ff_deaths(), cut_outcomes(),
                          label(), constants (H, PREFIX, GRID, CUTS, STALL_MARGIN, C13,
                          RB7, RB_SHARDS, ARMS, RB_ARMS, CONTROL_OF, CRN_OF, RB_OF)
  ctx.stage               1, 2 or 3 ("all" -> 3)
  ctx.sets                {"C13", "U30", "N30", "RB7"} -> [(wind, roles, seed)] frozen order
  ctx.T                   {"C13": 2, "U30": 2, "N30": 2} (the D-10 stock tolerance)
  ctx.GATE_ARMS           the stock fix arms queued at this stage (subset of C.GATE_ARMS)
  ctx.tags()              every ff tag queued
  ctx.tuples(tag, set)    tuples queued for tag in that set (frozen order); set None = all
  ctx.has(tag, tup)
  ctx.line(tag, tup)      the queue line dict (tag, repo, sets, set, instrument, raw, ...)
  ctx.load(tag, tup)      the run JSON (provenance-checked; LRU cache of 48)
  ctx.sidecar(tag, tup)   the .clobs.json dict
  ctx.legs(tag, tup)      C.legs() of the run (cached)
  ctx.first_div(a, b, tup)  C.first_diff(run a, run b) on fire_digests + ff_steps (cached)
  ctx.control_of(tag) / ctx.crn_of(tag) / ctx.rb_of(tag)   C.CONTROL_OF / CRN_OF / RB_OF,
                          None when that tag is not queued
  ctx.rb_tags()           rb shard tags queued; ctx.load_rb(tag) its JSON (checked)
  ctx.ref(tag, tup)       a recorded reference run (C.REFS: uhD uhC uhY ugD ugKD)
  ctx.say(line="")        append one report line
  ctx.stop(msg)           record a STOP item
  ctx.to_maintainer(arm, msg)
  ctx.g1                  True (the hook only runs when G1 passed)
  ctx.results             {"G3": {arm: (verdict, notes)}, "G4": {...}} of this file
======================================================================================
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cl_common as C  # noqa: E402

HEADER = "CARRYING-LEG ROUND - ANALYSIS (outputs/_cl_analyze.py; spec outputs/_cl_tooling_spec.txt H)"
VERDICTS = ("PASS", "FAIL", "TO-MAINTAINER", "UNTESTED")
# G3/G4 merge order: a gate with an untested required set cannot read PASS
RANK = {"PASS": 0, "UNTESTED": 1, "TO-MAINTAINER": 2, "FAIL": 3}
OWN_GATES = ("G1", "G3", "G4")
SIDE_ZERO = ("holds", "path_steps", "fallback_steps", "hold_starts", "custody_victim_steps",
             "served_by_custody_only")
# design 9.1 (f): "every feature counter at 0 except the enclosure-trigger count" - the
# sidecar's other feature counters, each reached only behind a non-zero switch
# (_exit_leg_step at mode 2; _exit_leg_custody and the in_custody flag at served >= 1)
SIDE_ZERO_DESIGN = ("exit_leg_step_other", "custody_calls", "in_custody_calls",
                    "served_by_custody_only_not_geo")


def merge(verdicts):
    """Worst of a list of verdicts (FAIL > TO-MAINTAINER > UNTESTED > PASS); empty -> UNTESTED."""
    vs = [v for v in verdicts if v is not None]
    return max(vs, key=lambda v: RANK[v]) if vs else "UNTESTED"


def yn(b):
    return "yes" if b else "NO"


# ------------------------------------------------------------------ context ----
class Ctx:
    def __init__(self, stage, idx, sets, T, selftest):
        self.C = C
        self.stage = stage
        self.idx = idx
        self.sets = sets
        self.T = T
        self.selftest = selftest
        self.lines = []
        self.stops = []
        self.maint = []
        self.g1 = False
        self.results = {}
        self._legs = {}
        self._div = {}
        self._refs = collections.OrderedDict()
        present = set(idx.tags())
        rb_prefixes = {t[:-1] for t in idx.rb}
        self.GATE_ARMS = tuple(a for a in C.GATE_ARMS
                               if a in present or (C.CRN_OF.get(a) in present)
                               or C.RB_OF.get(a) in rb_prefixes)

    # reporting
    def say(self, s=""):
        self.lines.append(str(s))

    def stop(self, msg):
        self.stops.append(str(msg))

    def to_maintainer(self, arm, msg):
        self.maint.append((str(arm), str(msg)))

    # data
    def tags(self):
        return self.idx.tags()

    def tuples(self, tag, set_name=None):
        return self.idx.tuples(tag, set_name)

    def has(self, tag, tup):
        return self.idx.has(tag, tup)

    def line(self, tag, tup):
        return self.idx.line(tag, tup)

    def load(self, tag, tup):
        return self.idx.load(tag, tup)

    def sidecar(self, tag, tup):
        return self.idx.sidecar(tag, tup)

    def legs(self, tag, tup):
        key = (tag, tuple(tup))
        if key not in self._legs:
            self._legs[key] = C.legs(self.load(tag, tup))
        return self._legs[key]

    def first_div(self, a, b, tup):
        key = (a, b, tuple(tup))
        if key not in self._div:
            self._div[key] = C.first_diff(self.load(a, tup), self.load(b, tup))
        return self._div[key]

    def _present(self, tag):
        return tag if tag is not None and tag in set(self.idx.tags()) else None

    def control_of(self, tag):
        return self._present(C.CONTROL_OF.get(tag))

    def crn_of(self, tag):
        return self._present(C.CRN_OF.get(tag))

    def rb_of(self, tag):
        """The rb shard tag PREFIX of a stock arm (e.g. "clGE2"), None if no shard of it is queued."""
        p = C.RB_OF.get(tag)
        return p if p and any(t[:-1] == p and t[-1:] in C.RB_SHARDS for t in self.idx.rb) else None

    def rb_tags(self):
        return list(self.idx.rb)

    def load_rb(self, tag):
        return self.idx.load_rb(tag)

    def ref(self, tag, tup):
        key = (tag, tuple(tup))
        if key in self._refs:
            self._refs.move_to_end(key)
            return self._refs[key]
        d = C.load_ref(tag, tup)
        self._refs[key] = d
        if len(self._refs) > 24:
            self._refs.popitem(last=False)
        return d


# ---------------------------------------------------------------- tolerance ----
def read_tolerance():
    """T per set from outputs/_cl_tolerance.txt; asserted == 2 for C13, U30, N30 (D-10)."""
    path = os.path.join(HERE, "_cl_tolerance.txt")
    if not os.path.isfile(path):
        C.refuse("outputs/_cl_tolerance.txt missing (D-10: the tolerance is stated before any run)")
    T = {}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for m in re.finditer(r"^\s+(C13|U30|N30)\s+n=\s*(\d+)\s+lambda=\S+\s+T=(\d+)", text, re.M):
        T[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    want_n = {"C13": 13, "U30": 30, "N30": 30}
    for k, n in want_n.items():
        if k not in T:
            C.refuse("_cl_tolerance.txt states no T for %s" % k)
        if T[k][0] != n:
            C.refuse("_cl_tolerance.txt %s n=%d, set size %d" % (k, T[k][0], n))
        if T[k][1] != 2:
            C.refuse("_cl_tolerance.txt %s T=%d, the pre-registered value is 2" % (k, T[k][1]))
    if "CRN: no tolerance" not in text:
        C.refuse("_cl_tolerance.txt lacks the 'CRN: no tolerance' rule")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {k: v[1] for k, v in T.items()}, sha


def sha_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def git_tracked(path):
    """True if `path` is tracked in the repo: `git ls-files --error-unmatch -- <one path>`
    (reads the index for that one named path; no walk). A path outside the repo (another
    drive, or above it) is untracked. Any git failure other than "no match" refuses."""
    p = os.path.abspath(path)
    try:
        rel = os.path.relpath(p, C.ROOT)
    except ValueError:        # another drive
        return False
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return False
    r = subprocess.run(["git", "-C", C.ROOT, "ls-files", "--error-unmatch", "--", rel.replace("\\", "/")],
                       capture_output=True, text=True)
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    C.refuse("git ls-files --error-unmatch %s failed (rc %d): %s" % (rel, r.returncode, r.stderr.strip()))


# ----------------------------------------------------------------------- H1 ----
def sec_h1(ctx):
    say = ctx.say
    say("")
    say("=" * 96)
    say("H1. IDENTITY (G1) - every item STOPs the round on failure")
    say("=" * 96)
    res = {}
    idx = ctx.idx
    sets = ctx.sets

    # (a) clB == clC on C13
    ok = 0
    rows = []
    for t in sets["C13"]:
        if not (idx.has("clB", t) and idx.has("clC", t)):
            rows.append("    %-18s MISSING %s" % (C.label(t), "clB" if not idx.has("clB", t) else "clC"))
            continue
        a, b = ctx.load("clB", t), ctx.load("clC", t)
        dk = C.diff_keys(a, b, ("tag", "repo", "wall_s"))
        sa, sb = ctx.sidecar("clB", t), ctx.sidecar("clC", t)
        hk = [k for k in ("transition_log_sha256", "movement_reason_sha256") if sa.get(k) != sb.get(k)]
        if dk or hk:
            rows.append("    %-18s DIFFERS keys %s%s" % (C.label(t), dk, ("; sidecar %s" % hk) if hk else ""))
        else:
            ok += 1
    res["a"] = ok == 13
    say("(a) clB (6160438 worktree) == clC (branch defaults), C13, every key but tag/repo/wall_s,")
    say("    params and extra_params EQUAL, + sidecar transition_log / movement_reason hashes:  %d/13  %s"
        % (ok, "PASS" if res["a"] else "FAIL"))
    for r in rows:
        say(r)

    # (b) clC U30 == recorded uhD
    uh_lines = {}
    for ln in C.read_queue(os.path.join(HERE, "_uh_queue.txt")):
        if ln["kind"] == "ff" and ln["tag"] == "uhD":
            uh_lines[ln["tup"]] = ln["raw"]
    ok = 0
    rows = []
    for t in sets["U30"]:
        if not idx.has("clC", t):
            rows.append("    %-18s MISSING clC" % C.label(t))
            continue
        parts = ctx.line("clC", t)["raw"].split("|")
        parts[1] = "uhD"
        if uh_lines.get(t) != "|".join(parts):
            rows.append("    %-18s PRECONDITION: queue line != outputs/_uh_queue.txt uhD line with the tag changed"
                        % C.label(t))
            continue
        dk = C.diff_keys(ctx.load("clC", t), ctx.ref("uhD", t), ("tag", "wall_s"))
        if dk:
            rows.append("    %-18s DIFFERS keys %s" % (C.label(t), dk))
        else:
            ok += 1
    res["b"] = ok == 30
    say("(b) clC U30 (through the sidecar) == recorded uhD (without it), every key but tag/wall_s")
    say("    (repo, params, extra_params, eval, terminal_step, burn_intervals, stdout included); queue")
    say("    line == the uhD line of outputs/_uh_queue.txt with the tag changed:  %d/30  %s"
        % (ok, "PASS" if res["b"] else "FAIL"))
    for r in rows:
        say(r)

    # (c) prefix vs ugD, C13 + U30
    ok = 0
    n = 0
    rows = []
    skipped = set()
    for t in sets["C13"] + sets["U30"]:
        n += 1
        if not idx.has("clC", t):
            rows.append("    %-18s MISSING clC" % C.label(t))
            continue
        diffs, sk = C.prefix_diff(ctx.load("clC", t), ctx.ref("ugD", t), C.PREFIX)
        skipped.update(sk)
        if diffs:
            rows.append("    %-18s DIFFERS %s" % (C.label(t), "; ".join(diffs)))
        else:
            ok += 1
    res["c"] = ok == n == 43
    say("(c) prefix: clC C13+U30 steps 1-%d == recorded ugD (the _uh_analyze P2 method: every"
        % C.PREFIX)
    say("    per-step series [:%d]; every event list cut at step <= %d):  %d/%d  %s"
        % (C.PREFIX, C.PREFIX, ok, n, "PASS" if res["c"] else "FAIL"))
    if skipped:
        say("    event lists not cut (entries without a step key): %s" % ", ".join(sorted(skipped)))
    for r in rows:
        say(r)

    # (d) CRN prefix vs ugKD, U30
    ok = 0
    rows = []
    skipped = set()
    for t in sets["U30"]:
        if not idx.has("clKC", t):
            rows.append("    %-18s MISSING clKC" % C.label(t))
            continue
        a, b = ctx.load("clKC", t), ctx.ref("ugKD", t)
        why = []
        for nm, dd in (("clKC", a), ("ugKD", b)):
            if not C.typed_equal((dd.get("fm2p") or {}).get("config"), {"FM2P_CRN": 1}):
                why.append("%s fm2p.config %r" % (nm, (dd.get("fm2p") or {}).get("config")))
        diffs, sk = C.prefix_diff(a, b, C.PREFIX)
        skipped.update(sk)
        if why or diffs:
            rows.append("    %-18s DIFFERS %s" % (C.label(t), "; ".join(why + diffs)))
        else:
            ok += 1
    res["d"] = ok == 30
    say("(d) CRN prefix: clKC U30 steps 1-%d == recorded ugKD (fm2p excluded; fm2p.config ==" % C.PREFIX)
    say("    {\"FM2P_CRN\": 1} asserted on both):  %d/30  %s" % (ok, "PASS" if res["d"] else "FAIL"))
    if skipped:
        say("    event lists not cut (entries without a step key): %s" % ", ".join(sorted(skipped)))
    for r in rows:
        say(r)

    # (e) rbgate shards
    ok = ev_ok = ev_n = 0
    rows = []
    for sfx in ("a", "b", "c", "s"):
        tag = "clGC" + sfx
        if tag not in idx.rb:
            rows.append("    %-6s MISSING" % tag)
            ev_n += len(C.RB_SHARDS[sfx][1].split(","))
            continue
        a = ctx.load_rb(tag)
        b = C.load_rb_ref("ugGD", sfx)
        diffs = C.rb_diff(a, b)
        ev_ok += C.rb_evals_equal(a, b)
        ev_n += len(b.get("evals") or [])
        if diffs:
            rows.append("    %-6s DIFFERS %s" % (tag, "; ".join(diffs)))
        else:
            ok += 1
    res["e"] = ok == 4 and ev_ok == ev_n == 18
    say("(e) rbgate: clGC{a,b,c,s} == recorded ugGD{a,b,c,s} (every key but tag; evals element by")
    say("    element without wall_s):  shards %d/4, evals %d/%d  %s" % (ok, ev_ok, ev_n, "PASS" if res["e"] else "FAIL"))
    for r in rows:
        say(r)

    # (f) clC sidecars
    n = 0
    rows = []
    enc = rb = 0
    for t in ctx.tuples("clC"):
        n += 1
        sc = ctx.sidecar("clC", t)
        sw = sc.get("switches") or {}
        why = []
        if not C.typed_equal(sw, {"mode": 0, "hold": False, "served": 0}):
            why.append("switches %r" % (sw,))
        cnt = sc.get("counters") or {}
        for k in SIDE_ZERO + SIDE_ZERO_DESIGN:
            if k not in cnt:
                why.append("counter %s absent" % k)
            elif cnt[k] != 0:
                why.append("%s=%r" % (k, cnt[k]))
        enc += int(cnt.get("enclosure_triggers") or 0)
        rb += int(cnt.get("carrier_route_blocked") or 0)
        if why:
            rows.append("    %-18s %s" % (C.label(t), "; ".join(why)))
    res["f"] = n > 0 and not rows
    say("(f) every clC sidecar: switches mode 0 / hold False / served 0; %s all 0" % ", ".join(SIDE_ZERO))
    say("    (spec H1 f) and %s all 0 (design 9.1 f: every feature counter but the" % ", ".join(SIDE_ZERO_DESIGN))
    say("    enclosure triggers):")
    say("    %d/%d runs  %s   (not gated: enclosure_triggers %d, carrier_route_blocked %d over the %d runs)"
        % (n - len(rows), n, "PASS" if res["f"] else "FAIL", enc, rb, n))
    for r in rows:
        say(r)

    # (g) info: clOC U30 vs uhC
    tl = ctx.tuples("clOC", "U30")
    if tl:
        same = 0
        keys = collections.Counter()
        for t in tl:
            dk = C.diff_keys(ctx.load("clOC", t), ctx.ref("uhC", t), ("tag", "repo", "wall_s", "params", "extra_params"))
            same += not dk
            keys.update(dk)
        say("(g) INFO clOC U30 (mechanic OFF, branch) vs recorded uhC (gated control, 11c3661), every key but")
        say("    tag/repo/wall_s/params/extra_params: %d/%d identical; keys differing (runs): %s"
            % (same, len(tl), ", ".join("%s %d" % kv for kv in sorted(keys.items())) or "none"))
    else:
        say("(g) INFO clOC U30 vs uhC: clOC not queued at this stage")

    g1 = all(res[k] for k in "abcdef")
    say("G1 VERDICT: %s  (%s)" % ("PASS" if g1 else "FAIL - STOP EVERYTHING",
                                  " ".join("%s=%s" % (k, "ok" if res[k] else "FAIL") for k in "abcdef")))
    if not g1:
        ctx.stop("G1 identity failed (%s)" % ", ".join("(%s)" % k for k in "abcdef" if not res[k]))
    return g1


# ----------------------------------------------------------------------- H6 ----
def sec_h6(ctx):
    say = ctx.say
    say("")
    say("=" * 96)
    say("H6. M5 OUTCOMES per arm / set / instrument at cuts %s (victim_steps + ff_steps +"
        % "/".join(str(c) for c in C.CUTS))
    say("    unreachable_escape_log; eval read only at 360 as a cross-check). RB7 is a G5 instrument only.")
    say("    cols: n rescued dead ff_deaths candidate(non-terminal) unreachable(geo/nd/other, by the latest")
    say("          escape-log cause) never_detected(log: ever marked, step<=cut; includes a victim marked")
    say("          and later dead) all_terminal(runs) mean terminal_step(terminal runs)")
    say("=" * 96)
    order = [t for t in C.ARMS if t in set(ctx.tags())]
    xmis = []
    for set_name in C.G3_SETS:
        for tag in order:
            tl = ctx.tuples(tag, set_name)
            if not tl:
                continue
            for cut in C.CUTS:
                agg = collections.Counter()
                terms = []
                for t in tl:
                    o = ctx_outcome(ctx, tag, t, cut)
                    for k in ("rescued", "dead", "ff_deaths", "candidate", "unreachable",
                              "geographically_isolated", "never_detected_status", "unreachable_other",
                              "never_detected"):
                        agg[k] += o[k]
                    agg["all_terminal"] += o["all_terminal"]
                    if o["terminal_step"] is not None:
                        terms.append(o["terminal_step"])
                mt = ("%.1f" % (sum(terms) / float(len(terms)))) if terms else "-"
                say("  %-4s %-6s %-5s @%3d  n=%-2d rescued %3d  dead %3d  ff_deaths %2d  candidate %2d  "
                    "unreachable %2d (%d/%d/%d)  never_detected %2d  all_terminal %2d/%-2d  terminal %s"
                    % (set_name, tag, C.ARMS[tag]["instrument"], cut, len(tl), agg["rescued"], agg["dead"],
                       agg["ff_deaths"], agg["candidate"], agg["unreachable"], agg["geographically_isolated"],
                       agg["never_detected_status"], agg["unreachable_other"], agg["never_detected"],
                       agg["all_terminal"], len(tl), mt))
            for t in tl:
                mm = C.eval_crosscheck(ctx.load(tag, t))
                if mm:
                    xmis.append("%s %s %s" % (tag, C.label(t), mm))
    rb7 = [t for t in order if ctx.tuples(t, "RB7")]
    if rb7:
        say("  (RB7 queued for %s: read by G5 only, not tabulated here)" % ", ".join(rb7))
    for t in order:
        for tup in ctx.tuples(t, "RB7"):
            mm = C.eval_crosscheck(ctx.load(t, tup))
            if mm:
                xmis.append("%s %s %s" % (t, C.label(tup), mm))
    say("  eval cross-check at 360 (rows vs eval, every queued run): %s"
        % ("all agree" if not xmis else "%d MISMATCH(ES) - STOP" % len(xmis)))
    for x in xmis:
        say("    MISMATCH %s" % x)
    if xmis:
        ctx.stop("H6 eval cross-check: %d run(s) where victim_steps/ff_steps disagree with eval at 360" % len(xmis))


_OUTC = {}


def ctx_outcome(ctx, tag, tup, cut):
    key = (tag, tuple(tup), cut)
    if key not in _OUTC:
        _OUTC[key] = C.cut_outcomes(ctx.load(tag, tup), cut)
    return _OUTC[key]


def rescued_by_victim(ctx, tag, tup, cut=C.H):
    return {v for v, s in C.statuses(ctx.load(tag, tup), cut).items() if s == "rescued"}


# ----------------------------------------------------------------------- G3 ----
def carry_worse(x, y, verdict):
    """Design 9.4 G3 (b) on one matched carry (control leg x, arm leg y): the arm's carry is
    LONGER (compare_legs: completed -> broken / horizon, longer n, finished or not), or it is
    BROKEN in the arm (not at the horizon) with an end other than the control's (n, cause) -
    e.g. the control drops at 110 and the victim is rescued later, while the arm holds and
    dies in custody at 125 (LONGER) or dies at 105 (SHORTER, broken differently).
    -> (bool, why) ; why "" when not worse or plain LONGER."""
    if verdict == "LONGER":
        return True, ""
    if (not y["completed"] and y["cause"] != "horizon"
            and (y["n"], y["cause"]) != (x["n"], x["cause"])):
        return True, "arm carry broken differently"
    return False, ""


def attribute(ctx, ctrl, arm, tup, vid):
    """Per-victim attribution of a victim rescued in ctrl and not in arm (spec H6 / 9.4 G3).
    Returns (lines, attributable)."""
    c, a = ctx.load(ctrl, tup), ctx.load(arm, tup)
    fc, fa = C.victim_fate(c, vid, C.H), C.victim_fate(a, vid, C.H)
    m = min(fc["step"] or C.H, fa["step"] or C.H)
    same = C.fire_identical(c, a, 1, m)
    ffire = C.first_diff(c, a, ("fire_digests",))
    s, keys = C.first_diff_detail(c, a)
    out = ["%s %s  %s %s | %s %s  fire identical to step %d: %s (first fire diff %s)  first differing step %s [%s]"
           % (C.label(tup), vid, ctrl, C.fate_str(fc), arm, C.fate_str(fa), m, yn(same), ffire, s,
              ", ".join(keys) or "-")]
    lc = [x for x in ctx.legs(ctrl, tup) if x["victim"] == vid]
    la = [x for x in ctx.legs(arm, tup) if x["victim"] == vid]
    pairs, conly, aonly = C.match_legs(lc, la)
    attributable = False
    if not lc and not la:
        out.append("      carry: none of this victim in either run")
    for x, y in pairs:
        verdict, kind = C.compare_legs(x, y)
        worse, why = carry_worse(x, y, verdict)
        # "on a fire identical up to that point": the point where the arm's carry became the
        # worse one = the earlier of the two ends (a horizon leg ends at H)
        s1 = min(x["end"] if x["end"] is not None else C.H, y["end"] if y["end"] is not None else C.H)
        fid = C.fire_identical(c, a, x["s0"], s1)
        att = worse and fid
        attributable = attributable or att
        out.append("      carry MATCHED: %s: %s | %s: %s  [%s %s%s; fire identical over [%d,%d]: %s]%s"
                   % (ctrl, C.leg_str(x), arm, C.leg_str(y), verdict, kind, ("; " + why) if why else "",
                      x["s0"], s1, yn(fid), "  => ATTRIBUTABLE (G3 b)" if att else ""))
    for x in conly:
        out.append("      carry in %s only (unmatched in %s): %s" % (ctrl, arm, C.leg_str(x)))
    for y in aonly:
        out.append("      carry in %s only (unmatched in %s): %s" % (arm, ctrl, C.leg_str(y)))
    return out, attributable


def compare_set(ctx, ctrl, arm, set_name, instrument):
    """One set, one instrument. Returns dict(verdict, lines, loss, tested, lower_tuples,
    attributable) or None when the arm has no tuple of the set queued."""
    tl = ctx.tuples(arm, set_name)
    if not tl:
        return None
    full = ctx.sets[set_name]
    lines = []
    if tl != full or ctx.tuples(ctrl, set_name) != full:
        lines.append("    %s %s %s vs %s: INCOMPLETE (%d/%d arm, %d/%d control runs queued) - UNTESTED"
                     % (set_name, instrument, arm, ctrl, len(tl), len(full), len(ctx.tuples(ctrl, set_name)), len(full)))
        return dict(verdict="UNTESTED", lines=lines, loss=None, tested=False, attributable=[], lower_tuples=[])
    Rc = Ra = 0
    lost, gained, lower, higher = [], [], [], []
    by_cut = {cut: [0, 0] for cut in C.CUTS}
    for t in full:
        rc, ra = rescued_by_victim(ctx, ctrl, t), rescued_by_victim(ctx, arm, t)
        Rc += len(rc)
        Ra += len(ra)
        if len(ra) < len(rc):
            lower.append((t, len(rc), len(ra)))
        elif len(ra) > len(rc):
            higher.append((t, len(rc), len(ra)))
        lost += [(t, v) for v in sorted(rc - ra)]
        gained += [(t, v) for v in sorted(ra - rc)]
        for cut in C.CUTS:
            by_cut[cut][0] += ctx_outcome(ctx, ctrl, t, cut)["rescued"]
            by_cut[cut][1] += ctx_outcome(ctx, arm, t, cut)["rescued"]
    loss = Rc - Ra
    verdict = "PASS"
    if instrument == "stock":
        T = ctx.T[set_name]
        if loss > T:
            verdict = "FAIL"
            rule = "loss %d > T=%d -> FAIL" % (loss, T)
        elif loss > 0:
            rule = "loss %d within T=%d -> passes the tolerance, listed victim by victim" % (loss, T)
        else:
            rule = "not lower"
    else:
        # CRN: the set TOTAL, zero tolerance (maintainer's ruling, prereg section 0).
        if loss > 0:
            verdict = "FAIL"
            rule = "CRN set total lower -> FAIL (zero tolerance)"
        else:
            rule = "CRN set total not lower"
        rule += "; per seed: %d down, %d up" % (len(lower), len(higher))
    lines.append("    %s %-5s %s %d -> %s %d  loss %+d  %s" % (set_name, instrument, ctrl, Rc, arm, Ra, loss, rule))
    lines.append("        rescued by cut %s: %s" % ("/".join(str(c) for c in C.CUTS),
                 "  ".join("%d->%d" % (by_cut[c][0], by_cut[c][1]) for c in C.CUTS)))
    if instrument == "crn":
        for t, a, b in lower:
            lines.append("        SEED DOWN %s: %d -> %d" % (C.label(t), a, b))
        for t, a, b in higher:
            lines.append("        SEED UP   %s: %d -> %d" % (C.label(t), a, b))
    att_list = []
    for t, v in lost:
        rows, att = attribute(ctx, ctrl, arm, t, v)
        lines.append("        LOST   " + rows[0])
        lines += ["        " + r for r in rows[1:]]
        if att:
            att_list.append((t, v))
    for t, v in gained:
        fc = C.victim_fate(ctx.load(ctrl, t), v, C.H)
        fa = C.victim_fate(ctx.load(arm, t), v, C.H)
        lines.append("        GAINED %s %s  %s %s | %s %s" % (C.label(t), v, ctrl, C.fate_str(fc), arm, C.fate_str(fa)))
    if att_list:
        verdict = "FAIL"
        lines.append("        ATTRIBUTABLE LOST VICTIM(S) (G3 b, automatic FAIL): %s"
                     % ", ".join("%s %s" % (C.label(t), v) for t, v in att_list))
    return dict(verdict=verdict, lines=lines, loss=loss, tested=True, attributable=att_list,
                lower_tuples=lower, higher_tuples=higher)


def required_sets(stage, arm):
    """The sets a fix arm's G3/G4 must cover at this stage (spec D, design 9.4): stage 2 is
    the C13 screen; stage 3 adds U30 and N30 (clOA, the D-4 mechanic-OFF arm: C13 + U30)."""
    if stage < 2:
        return ()
    if stage == 2:
        return ("C13",)
    return arm_sets(arm)


def arm_sets(arm):
    return ("C13", "U30") if arm == "clOA" else C.G3_SETS


def channels(ctx, arm):
    """[(instrument, arm tag | None, control tag | None)] a fix arm is judged in: stock always,
    CRN when the arm has a CRN twin (C.CRN_OF). A tag not queued at this stage is None."""
    ch = [("stock", ctx._present(arm), ctx.control_of(arm))]
    if C.CRN_OF.get(arm):
        ch.append(("crn", ctx.crn_of(arm), ctx._present("clKC")))
    return ch


def not_queued(ctx, arm, set_name, inst, a_tag, c_tag, verdicts, notes):
    """A REQUIRED set with no run of the arm (or of its control) queued: UNTESTED, said so."""
    a_name = a_tag or (arm if inst == "stock" else C.CRN_OF.get(arm))
    c_name = c_tag or (C.CONTROL_OF.get(arm) if inst == "stock" else "clKC")
    ctx.say("    %s %-5s NOT QUEUED (%s %d/%d, %s %d/%d runs of the set queued) - UNTESTED"
            % (set_name, inst, a_name, len(ctx.tuples(a_name, set_name)), len(ctx.sets[set_name]),
               c_name, len(ctx.tuples(c_name, set_name)), len(ctx.sets[set_name])))
    verdicts.append("UNTESTED")
    notes.append("%s %s %s NOT QUEUED" % (set_name, inst, a_name))


def req_banner(ctx):
    return ("    required sets at stage %d: %s (clOA %s), stock + the CRN twin; a required set not "
            "queued is UNTESTED (outranks PASS)" % (ctx.stage, "+".join(required_sets(ctx.stage, "clA")) or "none",
                                                   "+".join(required_sets(ctx.stage, "clOA")) or "none"))


def sec_g3(ctx):
    say = ctx.say
    say("")
    say("=" * 96)
    say("G3. RESCUED AT STEP %d (D-10): stock loss > T fails (T = %s, outputs/_cl_tolerance.txt);"
        % (C.H, ", ".join("%s %d" % kv for kv in sorted(ctx.T.items()))))
    say("    CRN: the set TOTAL lower fails (zero tolerance; per-seed detail beside it, not gated);")
    say("    a lost victim attributable to the fix fails in either instrument (9.4 G3 b);")
    say("    instruments are never pooled. Every lost victim is attributed in every comparison.")
    say(req_banner(ctx))
    say("=" * 96)
    out = {}
    for arm in ctx.GATE_ARMS:
        ctrl = ctx.control_of(arm)
        crn = ctx.crn_of(arm)
        notes, verdicts = [], []
        say("  %s (control %s%s)" % (arm, ctrl or "-", (", CRN %s vs clKC" % crn) if crn else (
            ", CRN %s NOT QUEUED" % C.CRN_OF[arm]) if C.CRN_OF.get(arm) else ", no CRN arm"))
        if arm not in set(ctx.tags()) or ctrl is None:
            say("    stock arm or its control not queued at this stage")
        req = required_sets(ctx.stage, arm)
        for set_name in arm_sets(arm):
            for inst, a_tag, c_tag in channels(ctx, arm):
                r = compare_set(ctx, c_tag, a_tag, set_name, inst) if a_tag and c_tag else None
                if r is None:
                    if set_name in req:
                        not_queued(ctx, arm, set_name, inst, a_tag, c_tag, verdicts, notes)
                    continue
                for ln in r["lines"]:
                    say(ln)
                v = r["verdict"]
                if arm == "clSN" and inst == "stock" and r["tested"] and r["loss"] > 0 and v == "PASS":
                    v = "TO-MAINTAINER"
                    ctx.to_maintainer(arm, "G3 clSN stock loss %d on %s (footprint attribution above)" % (r["loss"], set_name))
                verdicts.append(v)
                notes.append("%s %s %s" % (set_name, inst, v if not r["tested"] else
                                           "%s (loss %+d)" % (v, r["loss"])))
        verdict = merge(verdicts)
        out[arm] = (verdict, notes)
        say("    => %s G3 %s  [%s]" % (arm, verdict, "; ".join(notes) or "nothing tested"))
    if not ctx.GATE_ARMS:
        say("  no fix arm queued at this stage")
    ctx.results["G3"] = out
    return out


# ----------------------------------------------------------------------- G4 ----
def classify_death(ctx, ctrl, arm, tup, ff, step, instrument, crn_pair):
    """-> (class, detail). M10-EDGE: the unit died on its own completion step in the arm run
    and the arm runs MODE >= 1 (the mode-1 edge, design 9.3 M10). CRN-PAIR (stock): the stock
    fire diverged before the death and the CRN pair of the tuple shows no extra death of that
    unit. COMPLETION-STEP-M0: died on its own completion step in a MODE-0 arm (clH, clSN,
    clKH ...) - the pre-existing exit-cell edge case (i), which M10 does not pre-explain - and
    not CRN-PAIR: to the maintainer. Otherwise UNEXPLAINED."""
    a, c = ctx.load(arm, tup), ctx.load(ctrl, tup)
    mode = ctx.line(arm, tup)["sets"].get(C.MODE, 0)
    prev = C.ff_row(a, step - 1, ff)
    carrying = bool(prev and prev[4])
    cell = C.cell(prev[1]) if prev else None
    comp = [x for x in C.completions_of(a, ff=ff) if int(x["step"]) == step]
    ffire = C.first_diff(c, a, ("fire_digests",))
    s, keys = C.first_diff_detail(c, a)
    detail = ("%s died @%d at %s (carrying at the start of the step: %s); fire identical to %d: %s; "
              "first differing step %s [%s]" % (ff, step, list(cell) if cell else None, yn(carrying), step,
                                                 yn(ffire is None or ffire > step), s, ", ".join(keys) or "-"))
    if comp:
        burn = C.Burn(a)
        pos = C.cell(comp[0].get("pos"))
        detail += "; completion @%d at %s (burning there: %s; arm MODE %d)" % (
            step, list(pos) if pos else None, yn(pos is not None and burn.burning(pos, step)), mode)
        if mode >= 1:
            return "M10-EDGE", detail
    if instrument == "stock" and ffire is not None and ffire < step and crn_pair is not None:
        k_arm, k_ctrl = crn_pair
        if ctx.has(k_arm, tup) and ctx.has(k_ctrl, tup):
            da, dc = C.ff_deaths(ctx.load(k_arm, tup)), C.ff_deaths(ctx.load(k_ctrl, tup))
            extra = ff in da and ff not in dc
            detail += "; CRN pair %s/%s: %s dead %s / %s" % (k_arm, k_ctrl, ff, da.get(ff), dc.get(ff))
            if not extra:
                return "CRN-PAIR", detail
            detail += " (the CRN pair repeats the extra death)"
        else:
            detail += "; CRN pair not queued for this tuple"
    if comp:
        return "COMPLETION-STEP-M0", detail + "; MODE 0: the pre-existing exit-cell edge case (i), not M10"
    return "UNEXPLAINED", detail


def sec_g4(ctx):
    say = ctx.say
    say("")
    say("=" * 96)
    say("G4. FIREFIGHTER DEATHS at step %d per set per instrument (ff_steps rows); every extra death" % C.H)
    say("    where the arm is higher: M10-EDGE (MODE >= 1) / CRN-PAIR / COMPLETION-STEP-M0 (maintainer) /")
    say("    UNEXPLAINED (any -> FAIL); clSN stock higher -> maintainer (no CRN twin, design 9.4)")
    say(req_banner(ctx))
    say("=" * 96)
    out = {}
    for arm in ctx.GATE_ARMS:
        crn = ctx.crn_of(arm)
        kc = ctx._present("clKC")
        verdicts, notes = [], []
        say("  %s" % arm)
        req = required_sets(ctx.stage, arm)
        for set_name in arm_sets(arm):
            for inst, a_tag, c_tag in channels(ctx, arm):
                tl = ctx.tuples(a_tag, set_name) if a_tag and c_tag else []
                if not tl:
                    if set_name in req:
                        not_queued(ctx, arm, set_name, inst, a_tag, c_tag, verdicts, notes)
                    continue
                full = ctx.sets[set_name]
                if tl != full or ctx.tuples(c_tag, set_name) != full:
                    say("    %s %-5s INCOMPLETE - UNTESTED" % (set_name, inst))
                    verdicts.append("UNTESTED")
                    notes.append("%s %s UNTESTED" % (set_name, inst))
                    continue
                Dc = Da = 0
                changes, extra = [], []
                for t in full:
                    dc, da = C.ff_deaths(ctx.load(c_tag, t)), C.ff_deaths(ctx.load(a_tag, t))
                    Dc += len(dc)
                    Da += len(da)
                    for ff in sorted(set(da) - set(dc)):
                        extra.append((t, ff, da[ff]))
                        changes.append("%s +%s@%d" % (C.label(t), ff, da[ff]))
                    for ff in sorted(set(dc) - set(da)):
                        changes.append("%s -%s@%d" % (C.label(t), ff, dc[ff]))
                say("    %s %-5s %s %d -> %s %d%s" % (set_name, inst, c_tag, Dc, a_tag, Da,
                                                    ("   changes: " + ", ".join(changes)) if changes else ""))
                v = "PASS"
                if Da > Dc:
                    cls = collections.Counter()
                    for t, ff, st in extra:
                        k, det = classify_death(ctx, c_tag, a_tag, t, ff, st, inst,
                                                (crn, kc) if (inst == "stock" and crn and kc) else None)
                        cls[k] += 1
                        say("        EXTRA %s %s: %s" % (C.label(t), k, det))
                    if arm == "clSN" and inst == "stock":
                        # design 9.4: clSN has no CRN twin, so ANY extra death on stock goes to
                        # the maintainer with its attribution - never an automatic verdict
                        v, why = "TO-MAINTAINER", "TO-MAINTAINER (clSN, no CRN twin: design 9.4; classes are its attribution)"
                        ctx.to_maintainer(arm, "G4 clSN extra deaths on %s (%d -> %d; %s; EXTRA lines above)" % (
                            set_name, Dc, Da, dict(sorted(cls.items()))))
                    elif cls["UNEXPLAINED"]:
                        v, why = "FAIL", "FAIL (unexplained death)"
                    elif cls["COMPLETION-STEP-M0"]:
                        v, why = "TO-MAINTAINER", "TO-MAINTAINER (a MODE-0 completion-step death is not M10)"
                        ctx.to_maintainer(arm, "G4 %s %s: %d completion-step death(s) in a MODE-0 arm "
                                               "(EXTRA lines above)" % (set_name, inst, cls["COMPLETION-STEP-M0"]))
                    else:
                        why = "every extra death attributed"
                    say("        higher by %d: %s -> %s" % (Da - Dc, dict(sorted(cls.items())), why))
                verdicts.append(v)
                notes.append("%s %s %s (%d->%d)" % (set_name, inst, v, Dc, Da))
        verdict = merge(verdicts)
        out[arm] = (verdict, notes)
        say("    => %s G4 %s  [%s]" % (arm, verdict, "; ".join(notes) or "nothing tested"))
    if not ctx.GATE_ARMS:
        say("  no fix arm queued at this stage")
    ctx.results["G4"] = out
    return out


# --------------------------------------------------------------------- hook ----
def _same_file(f, path):
    return bool(f) and os.path.isfile(f) and os.path.samefile(f, path)


def load_hook(path):
    """The module AT `path`, registered as sys.modules["_cl_legs"]. A module already under that
    name is reused only if it was loaded from this same file (so a caller that imported the
    hook first, e.g. to patch it, gets its own object); anything else - a cached or shadowing
    _cl_legs from another directory on sys.path - is replaced by the file at `path`."""
    mod = sys.modules.get("_cl_legs")
    if mod is None or not _same_file(getattr(mod, "__file__", None), path):
        spec = importlib.util.spec_from_file_location("_cl_legs", path)
        if spec is None or spec.loader is None:
            C.defect("cannot load the hook from %s" % path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_cl_legs"] = mod
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            sys.modules.pop("_cl_legs", None)
            raise
    if not _same_file(getattr(mod, "__file__", None), path):
        C.defect("the hook module is %r, not %s" % (getattr(mod, "__file__", None), path))
    return mod


def run_hook(ctx):
    path = os.path.join(HERE, "_cl_legs.py")
    if not os.path.isfile(path):
        ctx.say("")
        ctx.say("HOOK: outputs/_cl_legs.py absent - H2-H5 and H7-H13 not computed; G2 and G5 UNTESTED")
        return None, "_cl_legs.py absent"
    mod = load_hook(path)
    fn = getattr(mod, "sections", None)
    if not callable(fn):
        C.defect("outputs/_cl_legs.py has no callable sections(ctx)")
    ctx.say("")
    ctx.say("HOOK: outputs/_cl_legs.py sections(ctx)")
    res = fn(ctx)
    if res is None:
        return {}, None
    if not isinstance(res, dict) or not isinstance(res.get("gates", {}), dict):
        C.defect("_cl_legs.sections returned %r, not {'gates': {...}}" % type(res).__name__)
    gates = res.get("gates", {})
    for arm, g in gates.items():
        if arm not in C.GATE_ARMS or not isinstance(g, dict):
            C.defect("_cl_legs gates: unknown arm %r" % arm)
        for gate, val in g.items():
            if gate in OWN_GATES:
                C.defect("_cl_legs returned %s for %s: that gate is _cl_analyze's" % (gate, arm))
            if (not isinstance(val, (tuple, list)) or len(val) != 2 or val[0] not in VERDICTS
                    or not isinstance(val[1], (list, tuple))):
                C.defect("_cl_legs gate %s/%s value %r is not (VERDICT, [notes])" % (arm, gate, val))
    return gates, None


# --------------------------------------------------------------------- gate ----
def sec_gate(ctx, g1, hook_gates, hook_note):
    say = ctx.say
    say("")
    say("=" * 96)
    say("GATE BLOCK - stage %d  (G1 identity | G2 stalls fall / M1c not higher (hook) | G3 rescued |"
        % ctx.stage)
    say("                         G4 ff deaths | G5 route_blocked (hook))")
    say("=" * 96)
    if ctx.selftest:
        say("  SELF-TEST MODE: %s - NOT A GATE REPORT" % ctx.selftest)
    say("  G1 (all arms): %s" % ("PASS" if g1 else "FAIL - STOP EVERYTHING"))
    if not ctx.GATE_ARMS:
        say("  no fix arm queued at this stage (stage 1 is the identity stage)")
    for arm in ctx.GATE_ARMS:
        row = {"G1": ("PASS" if g1 else "FAIL", [])}
        if g1:
            row["G3"] = ctx.results.get("G3", {}).get(arm, ("UNTESTED", []))
            row["G4"] = ctx.results.get("G4", {}).get(arm, ("UNTESTED", []))
            hg = (hook_gates or {}).get(arm, {})
            for g in ("G2", "G5"):
                row[g] = tuple(hg[g]) if g in hg else ("UNTESTED", [hook_note or "not returned by _cl_legs"])
            extra = sorted(k for k in hg if k not in ("G2", "G5"))
        else:
            for g in ("G2", "G3", "G4", "G5"):
                row[g] = ("UNTESTED", ["not evaluated: G1 failed"])
            extra = []
        crn = C.CRN_OF.get(arm)
        say("  %-5s %-6s G1 %-13s G2 %-13s G3 %-13s G4 %-13s G5 %-13s" % (
            arm, ("+" + crn) if crn else "", row["G1"][0], row["G2"][0], row["G3"][0], row["G4"][0], row["G5"][0]))
        for g in ("G2", "G3", "G4", "G5"):
            for n in row[g][1]:
                say("        %s: %s" % (g, n))
        for k in extra:
            v = tuple(hook_gates[arm][k])
            say("        %s %s%s" % (k, v[0], ("  " + "; ".join(str(x) for x in v[1])) if v[1] else ""))
    say("")
    say("STOP ITEMS: %d" % len(ctx.stops))
    for s in ctx.stops:
        say("  STOP %s" % s)
    say("TO THE MAINTAINER: %d" % len(ctx.maint))
    for arm, m in ctx.maint:
        say("  %s: %s" % (arm, m))


# --------------------------------------------------------------------- main ----
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=("1", "2", "3", "all"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--extra-queue", action="append", default=[])
    ap.add_argument("--replace", action="store_true",
                    help="overwrite an existing report of this analyzer even if it is tracked in git "
                         "or its text changes (otherwise both are refused)")
    ap.add_argument("--selftest-outdir", default=None,
                    help="SELF-TEST ONLY: read the stage queues, runs and sidecars from this directory")
    ap.add_argument("--selftest-no-seedcheck", action="store_true",
                    help="SELF-TEST ONLY: skip _cl_seedcheck.run_checks (frozen files still parsed)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(newline="\n")
    stage = 3 if a.stage == "all" else int(a.stage)
    outdir = os.path.abspath(a.selftest_outdir) if a.selftest_outdir else None
    selftest = []
    if outdir:
        selftest.append("runs/queues read from %s" % outdir.replace("\\", "/"))
    if a.selftest_no_seedcheck:
        selftest.append("seed freeze checks NOT run")
    out = a.out or os.path.join(outdir or HERE, "_cl_analysis_s%s.txt" % a.stage)
    C._guard(out)
    old_text = None
    if os.path.exists(out):
        try:
            with open(out, encoding="utf-8", newline="") as f:
                old_text = f.read()
        except UnicodeDecodeError:
            C.refuse("%s exists and is not UTF-8 text, so not a report of this analyzer (spec A4)" % out)
        if old_text.split("\n", 1)[0] != HEADER:
            C.refuse("%s exists and is not a report of this analyzer (spec A4: never overwrite)" % out)
        if git_tracked(out) and not a.replace:
            C.refuse("%s is TRACKED in git - a committed report is never overwritten (the tag-collision "
                     "lesson); pass --replace to overwrite it, or --out another path" % out)

    # seeds, tolerance, queues, provenance - every failure is a SystemExit
    seedlines = []
    if a.selftest_no_seedcheck:
        sets = C.seed_sets()
    else:
        import _cl_seedcheck  # noqa: E402
        checked = _cl_seedcheck.run_checks(say=seedlines.append)
        sets = C.seed_sets(checked)
    T, tsha = read_tolerance()
    queues = C.stage_queues(stage, outdir) + [os.path.abspath(q) for q in a.extra_queue]
    idx = C.RunIndex(queues, sets, outdir=outdir)
    counts = idx.verify_all()

    ctx = Ctx(stage, idx, sets, T, "; ".join(selftest))
    say = ctx.say
    say(HEADER)
    say("stage %s (queues of stages 1..%d%s)" % (a.stage, stage, " + extra" if a.extra_queue else ""))
    if selftest:
        say("SELF-TEST MODE: %s - NOT A GATE REPORT" % "; ".join(selftest))
    say("")
    say("SEED FREEZE (_cl_seedcheck.run_checks): %s" % ("NOT RUN (self-test)" if a.selftest_no_seedcheck else "SEEDCHECK OK"))
    for s in seedlines:
        say("  " + s)
    say("TOLERANCE outputs/_cl_tolerance.txt sha256 %s: T %s (asserted 2 each); CRN no tolerance"
        % (tsha, ", ".join("%s=%d" % kv for kv in sorted(T.items()))))
    say("QUEUES")
    for q in queues:
        say("  %s sha256 %s" % (os.path.basename(q), sha_file(q)))
    say("PROVENANCE: %d harness runs + %d rbgate shards, every one checked against its queue line and"
        % (counts["ff"], counts["rb"]))
    say("  the arm table (repo, tuple, steps, extra_params with types, fm2p state, sidecar version /")
    say("  instrument / switches / argv, --set keys declared in common_fixed_variables): all conform")
    for tag in idx.tags():
        per = ["%s %d" % (n, len(idx.tuples(tag, n))) for n in C.SET_NAMES if idx.tuples(tag, n)]
        say("  %-6s %-5s %s" % (tag, C.ARMS[tag]["instrument"], ", ".join(per)))
    if idx.rb:
        say("  rb shards: %s" % ", ".join(idx.rb))

    g1 = sec_h1(ctx)
    ctx.g1 = g1
    hook_gates, hook_note = None, None
    if g1:
        sec_h6(ctx)
        sec_g3(ctx)
        sec_g4(ctx)
        hook_gates, hook_note = run_hook(ctx)
    else:
        say("")
        say("G1 FAILED: outcomes, G2-G5 and the hook are NOT evaluated (STOP everything, design 9.6)")
    sec_gate(ctx, g1, hook_gates, hook_note)

    text = "\n".join(ctx.lines) + "\n"
    if old_text is not None and old_text != text and not a.replace:
        C.refuse("%s exists and this run's report DIFFERS from it (spec A4: never overwrite); pass "
                 "--replace to overwrite it, or --out another path" % out)
    if old_text != text:
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, out)
    print(text, end="")
    print("REPORT %s%s" % (out.replace("\\", "/"), "  (unchanged: identical to the existing file)"
                           if old_text == text else ""))
    return 2 if ctx.stops else 0


if __name__ == "__main__":
    sys.exit(main())
