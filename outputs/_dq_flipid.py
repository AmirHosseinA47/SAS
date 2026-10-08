"""Dispatch round 2, THE FLIP: the FLIP IDENTITY (outputs/dispatch2_part1.txt 10.8 THE FLIP: "flip identity against dq1
on 4 + 4 cells"). The flipped defaults (common_fixed_variables.py DISPATCH_JOINT = 1, DISPATCH_REASSIGN = 1) must
reproduce the screen's dq1 arm EXACTLY on 8 frozen cells. A port of outputs/_mvg_flip.py (the movement round's flip
identity: the W2 line minus its switch pairs, a fixed cell list, every field equal but labels and wall-clock, positive
controls) and outputs/_mvg_ist.py (the launch freeze record and its re-hash), with outputs/_dq_replay.py's R0 rule
(r0_reproduces, 11.2) as the identity and its json_diff / classify_diff as the full-record diff.

usage (E:/Projects/SAS/.venv/Scripts/python.exe -B, PYTHONDONTWRITEBYTECODE=1; any cwd):
  _dq_flipid.py show                        the 8 derived lines checked against their W2 lines, the dq1 references'
                                            validity and J decision coverage; writes nothing, runs nothing
  _dq_flipid.py write --head SHA [--dry-run]
                                            freezes outputs/_dq_q_flipid.jsonl (8 lines for outputs/_mf2_pool.py) and
                                            the launch record outputs/_dq_flipid/_freeze_launch.json; every refusal is
                                            listed (exit 2); --dry-run runs every check and writes nothing; a re-run
                                            on an identical frozen queue + freeze prints "unchanged (frozen)"
  _dq_flipid.py analyze                     (a) validity, (b) identity, (c) the freeze re-hash, per cell; the positive
                                            controls; prints the table and the verdict line and writes the same text to
                                            outputs/_dq_flipid_result.txt (exit 0 PASS, 1 FAIL, 2 STOP)
  _dq_flipid.py selftest [--tmp DIR]        in-process on synthetic inputs (a fake git, a fake tag check, a synthetic
                                            tree and records in a temporary directory): no simulator step, nothing
                                            written under outputs/
LAUNCH (after write; write prints the command and the warning below):
  PYTHONDONTWRITEBYTECODE=1 <py> -B outputs/_mf2_pool.py outputs/_dq_q_flipid.jsonl outputs/_mf2_pool_dq_flipid.log
  --maxpar 8 --min-free-gb 3. The pool spawns each run as <py> + argv with no -B, so the environment variable (inherited
  by the 8 runs) is what keeps .pyc out of the worktree; -B covers the pool itself. NO COMMIT MAY LAND BETWEEN WRITE AND
  THE END OF THE 8 RUNS (not the queue, the freeze or the flip's own test edits): every record's head must equal the
  frozen --head SHA ((a)). Nothing under the run-loaded files may change between write and analyze ((c)); neither may
  outputs/_dq_replay.py or this tool (analyze STOPS).

THE CELLS (frozen; 4 per fresh set, chosen for the widest J decision coverage from outputs/_dq_screen_analysis.txt
section 6, the reason beside each), in the frozen W2 queue's order (set -> placement -> cell):
  set 7: ring A_E (3 REPLACEs + nearest-barred spells), ring C_S (margin REPLACE, the PREVENTED death), uniform B_S
         (stall + margin REPLACE, the L4 death), uniform C_W (the longest nearest-barred spell);
  set 8: ring B_S (stall + margin), ring D_S (the DIAG cell), uniform A_E (latch episode), uniform A_N (stall + margin +
         nearest-barred + latch episode).
  Tags dqF<r|u><7|8>_<S>_<W> (the dq1 name with "dq1" -> "dqF"); records outputs/_dq_flipid/_sd_<tag>.json.
THE RUN LINE: the frozen W2 line of the cell (outputs/_dq_q_w2.jsonl, name dq1<p><k>_<S>_<W>; its LF sha256 frozen
  below = the screen analyzer's b1ccbc0d2eaf6eed), verbatim, EXCEPT exactly four changes: the pairs "--set
  DISPATCH_JOINT=1" and "--set DISPATCH_REASSIGN=1" REMOVED (the flipped defaults decide), --out ->
  outputs/_dq_flipid/_sd_<tag>.json, --tag -> <tag>. Same probe (outputs/_dq_probe.py), same --repo and cwd
  (E:\\Projects\\SAS_wt\\dispatch). Line keys {"name", "argv", "out", "cwd"} (the pool's; no extra key).

WRITE (--head SHA, the flip commit's full 40-hex sha) refuses - listing every reason - when: SHA is not 40 hex; git HEAD
  != SHA; SHA does not descend from the dq1 head (git merge-base --is-ancestor <dq1 head> SHA is not 0); a run-loaded
  file is modified (git status --porcelain -uno on RUN_LOADED_GLOBS + CHAIN, quarantine excluded); a probe-chain file
  (CHAIN) is not tracked (git ls-files --error-unmatch: an untracked chain file is invisible to the -uno clean check,
  so HEAD == SHA would not pin it); git ls-files lists a quarantine path; any git command the check needs fails;
  common_fixed_variables.py (parsed with ast, never imported) does not assign DISPATCH_JOINT and DISPATCH_REASSIGN
  exactly once each, at module level, to the int literal 1; A RUN-LOADED FILE CHANGED BETWEEN THE DQ1 HEAD AND SHA (git
  diff --name-only <dq1 head> SHA: every commit in between, bounded by the ancestry gate) WHOSE AST SCOPE VERDICT IS NOT
  EXACTLY ITS ALLOWED ONE (ALLOWED_SCOPE: agents.py "code-identical (docstrings / comments / layout only)";
  common_fixed_variables.py "code-identical except DISPATCH_JOINT 0 -> 1, DISPATCH_REASSIGN 0 -> 1"; any other file,
  and "CODE CHANGED", "added or removed", "UNPARSABLE", refuse); outputs/_dq_replay.py (the identity rule) differs
  from its blob at SHA (LF-normalised) or that blob is missing; the W2 queue's LF sha256 is not the frozen one; a line
  does not derive or does not validate token for token against its W2 line (only the four changes); a dq1 reference
  record or its stdout is missing or invalid, or a src_sha value of it is neither the LF nor the CRLF form of that
  file's blob at the dq1 head (the reference did not run the dq1 head's content); the tag check fails
  (outputs/_dq_queue.py tag_check, imported: every run name and output path unused in every registered worktree's
  outputs/ and
  outputs/_ffr_logs/ top level and every outputs/_dq* directory, the git index and the git history of added paths,
  quarantine excluded, positive controls per location); the queue / freeze / result / pool log exists or is tracked, or
  outputs/_dq_flipid/ exists and is not empty; a frozen queue exists that differs (never re-frozen). THE FREEZE RECORD:
  head, the dq1 head, the ancestry (True), the cfv values (literal, line), the queue's and W2's LF sha256, the cells,
  the LF and the raw sha256 of every run-loaded file (the tracked root *.py, the tracked src_extension/**/*.py and the
  probe chain CHAIN in outputs/), the sha256 of the analysis tooling (TOOLING) and outputs/_dq_replay.py's LF sha256 at
  SHA, the sha256 of every dq1 reference record and its stdout, the run-loaded files changed between the dq1 head and
  SHA with the ast scope verdict of each (all ALLOWED), for every file the dq1 references hash the sha256 of the LF and
  of the CRLF form of its blob at the dq1 head (dq1_forms), the tag check table and the references' J decision coverage.

ANALYZE, per cell (the cell PASSES iff (a), (b) and (c) all hold):
  (a) VALIDITY of the flip record: present; complete True; crashed None; steps_done 360; CRN on with crn_draws > 0;
      head == the frozen SHA; repo == the worktree; tag == the line's name; argv == the queue line's probe arguments
      (argv[4:]); the pool's <out>.argv sidecar == the line's signature (argv + cwd); NO DISPATCH_* token on either argv
      and NO DISPATCH_* key in extra_params or params (the defaults decided); the switches the run READ: dq.switches
      joint_on and reassign_on True and dq.switches.raw DISPATCH_JOINT / DISPATCH_REASSIGN == repr(the frozen cfv value)
      ('1'), dp.switches the same; dq.probe_sha == mvg.probe_sha == the frozen LF sha256 of outputs/_dq_probe.py;
      dq.r1_shadow_sha / mvg.u1_shadow_sha == the frozen LF sha256 of their shadow files; every src_sha entry (top level:
      16-hex prefix; dq / dp / ud / mvg: full) == the frozen RAW sha256 of that file (the probes hash raw bytes) and
      every hashed file is a frozen run-loaded file. The dq1 REFERENCE is checked too: complete, crashed None,
      steps_done 360, CRN draws > 0, head == the screen head 11d62410, repo, tag == its W2 name, argv == its W2 line's,
      sidecar == its W2 signature, extra_params DISPATCH_JOINT == DISPATCH_REASSIGN == 1, joint_on / reassign_on True.
  (b) IDENTITY against the dq1 record: outputs/_dq_replay.py r0_reproduces(dq1, flip, stdout, stdout) == [] (every
      per-step row rows_ff / vic / uav / dec / trig, dp.commands, dp.j_events, mv_events, eval and stdout - 11.2's R0
      rule, as W3 validity used it), AND the full-record diff (_dq_replay.json_diff(dq1, flip), unlimited) split by
      _dq_replay.classify_diff and then by the classes below: EVERY differing path must fall in an ALLOWED class whose
      condition holds; anything else is OTHER and fails the cell. THE ALLOWED CLASSES (exhaustive), each justified:
        T  WALL-CLOCK / MS (classify_diff's volatile set minus .tag / .argv): .wall_s, every .timing / .j_timing value,
           .dp.j_calls[i][2] (net ms), .mv.rows[i][fix_ms | inst_ms], .mvg.guard.rows[i][ms_guard | ms_inst].
           The .ud.kicks ms columns are NOT in T: classify_diff is called with kick_cols None, so any .ud.kicks
           difference is OTHER (ud.kicks is empty in all 8 dq1 references; J is on, so a kick there is a behaviour
           difference anyway). Condition: a LEAF difference with a number on both sides; a length or key-set
           difference inside a timing field, or a non-number, is OTHER (a different count of timed calls is a
           behaviour difference). Justification: measured by the clock, never read by the model. NOT EVERY T LEAF IS A
           CLOCK READING: the .dp.j_timing rows [step, phase, raw_ms, net_ms, thread_ms, gc_collections] also carry the
           step and a gc-collection count; a step difference there is a number and falls in T, but the same step is
           compared outside T in .dp.j_calls[i][0] (and r0_reproduces compares the J events), the row count is compared
           (a length difference is OTHER) and the phase is a string (OTHER), so T admits no decision difference; the gc
           count is interpreter bookkeeping, not a model decision.
        N  .tag: the run's name (--tag), dq1<p><k>_<S>_<W> vs dqF<p><k>_<S>_<W>. Condition: dq1's tag == its W2 name and
           the flip's == its queue name.
        A  .argv (its length and elements): the probe arguments. Condition: dq1's argv == its W2 line's argv[4:] and the
           flip's == its queue line's argv[4:], the two lines differing by exactly the four frozen changes (validated
           token for token at write and again at analyze). The record holds --out only here (no separate out field).
        K  .params.DISPATCH_JOINT, .params.DISPATCH_REASSIGN, .extra_params.DISPATCH_JOINT, .extra_params.
           DISPATCH_REASSIGN - present in dq1 ONLY. Condition: dq1's value is the int 1 and the flip record lacks the
           key. Justification: outputs/_sd_probe.py builds extra_params from the --set values and params =
           evaluate_scenarios._scenario_params + extra_params; the flip line no longer sets the two keys.
        H  .head: git HEAD at the run. Condition: dq1's == the screen head 11d62410 (the analyzer's Part 2 commit) and
           the flip's == the frozen SHA.
        S  a src_sha leaf (top level, dq, dp, ud, mvg) of a file F. Condition: the flip record's value is F's frozen
           raw sha256 (top level: its 16-hex prefix) AND dq1's value is the sha256 of the LF or of the CRLF form of F's
           blob at the dq1 head (dq1_forms; top level: the 16-hex prefix) AND EITHER (i) F is in the freeze's changed
           list (git diff --name-only <dq1 head> SHA) with its frozen ast scope verdict EXACTLY ALLOWED_SCOPE[F]
           (agents.py: docstrings / comments / layout only; common_fixed_variables.py: only DISPATCH_JOINT 0 -> 1 and
           DISPATCH_REASSIGN 0 -> 1) - any other verdict or file is OTHER - OR (ii) F is not in the changed list and the
           change is line endings only, IN EITHER DIRECTION: F's blob at the dq1 head, LF-normalised, has F's frozen LF
           sha256 (the same content). Justification: the probes hash the RAW bytes of the checkout's files
           (_sd_probe._sha, _dq_probe._file_shas), so a file re-checked-out with other line endings, or edited only in
           its docstrings / comments / layout, or in the two flipped values the flip line no longer --sets, changes its
           hash without changing what runs; nothing else does (write refuses any other scope).
      THE RAW SWITCH PROVENANCE STRINGS (dq.switches.raw.DISPATCH_*, dp.switches.DISPATCH_*) ARE NOT AN ALLOWED CLASS:
      they are repr(cfv.<key>) - '1' in dq1 (the --set value parsed to the int 1 by _sd_probe._parse_value and set by
      apply_scenario_config) and '1' at the flip (the int literal 1 default) - so they must be EQUAL; any difference is
      OTHER. Every other provenance field (repo, python, mesa, probe, shadow paths, effective, the FF_* switches, S / M /
      P, stdout_sha, stdout_tags, warnings, errors) must be equal.
  (c) THE FREEZE RE-HASH: every run-loaded file now (the same git ls-files rule + CHAIN) has the frozen LF and raw
      sha256 - a changed content, a line-endings-only change (the probes hash raw bytes), a new or a missing file FAILS
      every cell; the cfv values re-parsed are still the frozen ones; and THIS cell's dq1 reference record and stdout
      have their frozen sha256 (an extension: the reference must not move under the comparison). THE IDENTITY RULE IS
      PINNED (TOOLING_STOP): analyze STOPS (exit 2, nothing read) when outputs/_dq_replay.py's LF sha256 differs from
      the frozen one or from its blob at SHA, or when this tool's own LF sha256 differs from the frozen one (both are
      printed); the rest of TOOLING (_dq_queue.py, _mf2_pool.py: write / launch only) is re-hashed and a change is a
      NOTE.
POSITIVE CONTROLS (the movement round's flip identity convention, outputs/mvg_report.txt 11.2 (b): "16 / 16
  detected"): each flip record is compared, by the same (b), with the SAME cell's dq0 record (outputs/_dq_q_w1.jsonl:
  J off) and with the NEXT frozen cell's dq1 record; every one of the 16 comparisons must be DETECTED BY THE BEHAVIOUR
  RULE: r0_reproduces must report a difference (both kinds give one: dq0 has no J events in these cells, the next
  cell's rows differ). An OTHER path alone does not count: the dq0 control always trips K and the raw switch strings,
  the next-cell control the seed / scenario, so counting OTHER would let a blind r0 rule pass 16 / 16. A control not
  detected (or unavailable) makes the verdict FAIL: the comparison would not be shown sensitive.
VERDICT (last line of the result): "FLIP IDENTITY => PASS 8/8" only if every cell passes and the controls are 16 / 16
  detected; otherwise "FLIP IDENTITY => FAIL n/8" (n = cells passing) with the reason.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True          # never write .pyc into the repo (the modules below are loaded by path)

import ast  # noqa: E402
import copy  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402

VERSION = "dq_flipid v2"
HERE = os.path.dirname(os.path.abspath(__file__))
WT = r"E:\Projects\SAS_wt\dispatch"
MAIN = r"E:\Projects\SAS"
PY = os.path.join(MAIN, ".venv", "Scripts", "python.exe")
# the screen's frozen W2 queue (outputs/_dq_screen_analysis.txt header: LF sha256 b1ccbc0d2eaf6eed == 11d62410)
W2_LF_SHA256 = "b1ccbc0d2eaf6eed6eacf367d23e60e30e12da84de2028fc542e35840376ac50"
# the dq1 records' head: the screen's Part 2 commit (outputs/_dq_screen_analysis.txt: "Part 2 commit (--head, the
# screen head): 11d62410")
DQ1_HEAD = "11d6241034b8288159a79c72c5c141c867a05d29"
QUARANTINE_NAME = "_firemech_rewound_20260914"
QUARANTINE_EXCLUDE = ":(exclude)outputs/" + QUARANTINE_NAME
FLIP_KEYS = ("DISPATCH_JOINT", "DISPATCH_REASSIGN")
FLIP_SETS = ("DISPATCH_JOINT=1", "DISPATCH_REASSIGN=1")
STEPS = 360
FLIP_CELLS = (
    ("dq1r7_A_E", "3 REPLACEs + nearest-barred spells"),
    ("dq1r7_C_S", "margin REPLACE, the PREVENTED death"),
    ("dq1u7_B_S", "stall + margin REPLACE, the L4 death"),
    ("dq1u7_C_W", "the longest nearest-barred spell"),
    ("dq1r8_B_S", "stall + margin"),
    ("dq1r8_D_S", "the DIAG cell"),
    ("dq1u8_A_E", "latch episode"),
    ("dq1u8_A_N", "stall + margin + nearest-barred + latch episode"),
)
REF_RE = re.compile(r"^dq1([ru])([78])_([A-D])_([NSEW])$")
FLIP_RE = re.compile(r"^dqF([ru])([78])_([A-D])_([NSEW])$")
WIND = {"N": "north", "S": "south", "E": "east", "W": "west"}
LINE_KEYS = ["name", "argv", "out", "cwd"]
# the run-loaded files (the task's list): the tracked root *.py, the tracked src_extension/**/*.py (git glob magic: '*'
# never crosses a '/'; '**/' matches zero or more directories) and the probe chain the run loads in outputs/
RUN_LOADED_GLOBS = (":(glob)*.py", ":(glob)src_extension/**/*.py")
CHAIN = ("outputs/_dq_probe.py", "outputs/_dq_r1_shadow.py", "outputs/_mvg_u1_shadow.py", "outputs/_ut_probe.py",
         "outputs/_fb3_probe.py", "outputs/_fx3_probe.py", "outputs/_mf2_probe.py", "outputs/_sd_probe.py",
         "outputs/_fm2_probe_harness.py", "outputs/_ffr_harness.py", "outputs/_bp_inst.py")
# the analysis tooling this verdict rests on (re-hashed at analyze): a change of the identity rule (_dq_replay.py) or of
# this tool STOPS analyze (TOOLING_STOP); a change of the write / launch tooling is a NOTE
TOOLING = ("outputs/_dq_flipid.py", "outputs/_dq_replay.py", "outputs/_dq_queue.py", "outputs/_mf2_pool.py")
REPLAY_REL = "outputs/_dq_replay.py"
SELF_REL = "outputs/_dq_flipid.py"
TOOLING_STOP = (SELF_REL, REPLAY_REL)
# the ONLY ast scope verdicts a run-loaded file changed between the dq1 head and SHA may have (write refuses any other
# file or verdict; analyze classifies an S path of any other as OTHER): the flip edits agents.py docstrings and the two
# common_fixed_variables.py values, nothing else
ALLOWED_SCOPE = {
    "agents.py": "code-identical (docstrings / comments / layout only)",
    "common_fixed_variables.py": "code-identical except DISPATCH_JOINT 0 -> 1, DISPATCH_REASSIGN 0 -> 1",
}
SECTIONS = ("dq", "dp", "ud", "mvg")
K_PATHS = tuple(".%s.%s (only in X)" % (sec, k) for sec in ("params", "extra_params") for k in FLIP_KEYS)
SRC_RE = re.compile(r"^\.(?:(dq|dp|ud|mvg)\.)?src_sha\.(.+)$")
CLASSES = ("T", "N", "A", "K", "H", "S")
CLASS_TEXT = {
    "T": "wall-clock / ms leaves (numbers on both sides)",
    "N": ".tag (the run's name)",
    "A": ".argv (the queue lines' four frozen changes)",
    "K": "params / extra_params DISPATCH_JOINT / DISPATCH_REASSIGN present in dq1 only (the line no longer sets them)",
    "H": ".head (screen head 11d62410 -> the frozen flip SHA)",
    "S": "src_sha of a file changed since the dq1 head with its ALLOWED scope verdict, or line endings only (either "
         "direction); flip value = the frozen raw sha256, dq1 value = an LF / CRLF form of the dq1-head blob",
}
LAUNCH_WARNING = ("WARNING: NO COMMIT MAY LAND BETWEEN THIS WRITE AND THE END OF THE 8 RUNS (not the queue, the freeze "
                  "or the flip's test edits): every record's head must equal the frozen --head SHA, or (a) fails on "
                  "all 8 cells. Commit the queue / freeze / records only after analyze.")


# ================================================================================================= small helpers
def _norm(path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def file_hashes(path: str):
    """{"lf", "raw"} sha256 of a file (LF-normalised and raw bytes), or None if it does not exist."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    return {"lf": _sha(_lf(data)), "raw": _sha(data)}


def blob_forms(data: bytes) -> dict:
    """{"lf", "crlf"}: the sha256 of a blob's LF-normalised form and of that form with CRLF line endings (the two ways
    a checkout can hold it)."""
    lf = _lf(data)
    return {"lf": _sha(lf), "crlf": _sha(lf.replace(b"\n", b"\r\n"))}


def is_form(value, forms, top) -> bool:
    """dq1's recorded src_sha value is the LF or the CRLF form of the file's dq1-head blob (top level: 16-hex
    prefix)."""
    if not forms:
        return False
    want = (forms["lf"][:16], forms["crlf"][:16]) if top else (forms["lf"], forms["crlf"])
    return value in want


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def signature(line: dict) -> str:
    """The pool's <out>.argv content for a line (outputs/_mf2_pool.py signature)."""
    return json.dumps({"argv": line["argv"], "cwd": line.get("cwd") or MAIN}, sort_keys=True)


def stdout_path(out: str) -> str:
    return out[:-5] + ".stdout.txt" if out.endswith(".json") else out + ".stdout.txt"


def queue_text(lines) -> str:
    return "".join(json.dumps(ln) + "\n" for ln in lines)


def _load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_REPLAY = {}


def replay_module():
    """outputs/_dq_replay.py (r0_reproduces, json_diff, classify_diff), loaded by path from this tool's directory."""
    if "m" not in _REPLAY:
        _REPLAY["m"] = _load_module("dq_replay_flipid", os.path.join(HERE, "_dq_replay.py"))
    return _REPLAY["m"]


def resolve(obj, path: str):
    """The value at a json_diff path ('.key' / '[i]'; a key may contain '.', the longest matching key wins)."""
    cur, rest = obj, path
    while rest:
        if rest.startswith("["):
            m = re.match(r"\[(\d+)\]", rest)
            if not m or not isinstance(cur, list):
                raise KeyError(path)
            cur, rest = cur[int(m.group(1))], rest[m.end():]
        elif rest.startswith(".") and isinstance(cur, dict):
            best = None
            for k in cur:
                ks = "." + str(k)
                if rest.startswith(ks) and (len(rest) == len(ks) or rest[len(ks)] in ".[") and (
                        best is None or len(str(k)) > len(str(best))):
                    best = k
            if best is None:
                raise KeyError(path)
            cur, rest = cur[best], rest[len(str(best)) + 1:]
        else:
            raise KeyError(path)
    return cur


# ================================================================================================= environment
def real_git(wt: str):
    def run(args):
        proc = subprocess.run(["git", "-C", wt, "-c", "core.quotepath=off"] + list(args), capture_output=True,
                              timeout=900)
        return proc.returncode, proc.stdout, proc.stderr
    return run


def real_tag_check(lines):
    """outputs/_dq_queue.py tag_check (every registered worktree; quarantine excluded), imported by path."""
    q = _load_module("dq_queue_flipid", os.path.join(HERE, "_dq_queue.py"))
    return q.tag_check(lines, resume=False, all_trees=True)


class Env:
    """Every path and side effect the tool touches: the real dispatch worktree by default; the self-test builds a
    synthetic tree with a fake git and a fake tag check."""

    def __init__(self, wt=WT, git=None, tag_check=None, w2_sha=W2_LF_SHA256, dq1_head=DQ1_HEAD, real=True):
        self.wt = os.path.normpath(wt)
        self.out = os.path.join(self.wt, "outputs")
        self.probe = os.path.join(self.out, "_dq_probe.py")
        self.w2 = os.path.join(self.out, "_dq_q_w2.jsonl")
        self.w1 = os.path.join(self.out, "_dq_q_w1.jsonl")
        self.queue = os.path.join(self.out, "_dq_q_flipid.jsonl")
        self.out_dir = os.path.join(self.out, "_dq_flipid")
        self.freeze = os.path.join(self.out_dir, "_freeze_launch.json")
        self.result = os.path.join(self.out, "_dq_flipid_result.txt")
        self.pool_log = os.path.join(self.out, "_mf2_pool_dq_flipid.log")
        self.git = git or real_git(self.wt)
        self.tag_check = tag_check or real_tag_check
        self.w2_sha = w2_sha
        self.dq1_head = dq1_head
        self.real = real

    def rel(self, path: str) -> str:
        return os.path.relpath(path, self.wt).replace(os.sep, "/")

    def abs(self, rel: str) -> str:
        return os.path.join(self.wt, *rel.split("/"))


def _git_text(env, args):
    rc, out, err = env.git(args)
    return rc, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def run_loaded_list(env):
    """(sorted rel paths, problems): the tracked root *.py and src_extension/**/*.py (git ls-files with explicit
    pathspecs, quarantine excluded) + CHAIN."""
    rc, out, err = _git_text(env, ["ls-files", "-z", "--", *RUN_LOADED_GLOBS, QUARANTINE_EXCLUDE])
    if rc != 0:
        return None, ["git ls-files failed (rc %d): %s" % (rc, err.strip()[:300])]
    paths = {p.strip("\r\n") for p in out.split("\0") if p.strip("\r\n")}
    if any(QUARANTINE_NAME.lower() in p.lower() for p in paths):
        return None, ["git ls-files listed a quarantine path despite the exclude pathspec"]
    return sorted(paths | set(CHAIN)), []


def hash_rels(env, rels):
    return {rel: file_hashes(env.abs(rel)) for rel in rels}


def run_loaded_dirty(env):
    rc, out, err = _git_text(env, ["status", "--porcelain", "-uno", "--", *RUN_LOADED_GLOBS, *CHAIN,
                                   QUARANTINE_EXCLUDE])
    if rc != 0:
        return ["git status failed (rc %d): %s" % (rc, err.strip()[:300])]
    return ["MODIFIED (run-loaded) " + ln.strip() for ln in out.splitlines() if ln.strip()]


def chain_untracked(env) -> list:
    """Every probe-chain file must be in the index (git ls-files --error-unmatch): an untracked chain file is invisible
    to the status -uno clean check, so HEAD == SHA would not pin it."""
    rc, out, err = _git_text(env, ["ls-files", "-z", "--error-unmatch", "--", *CHAIN])
    tracked = {p.strip("\r\n") for p in out.split("\0") if p.strip("\r\n")}
    missing = [c for c in CHAIN if c not in tracked]
    if rc != 0 or missing:
        return ["probe-chain file(s) NOT TRACKED (git ls-files --error-unmatch rc %d): %s %s" % (
            rc, missing, err.strip()[:200])]
    return []


def src_files(rec) -> list:
    """[(block label, normalised file, top, value)] of every src_sha entry of a record (top level + SECTIONS)."""
    out = []
    if not isinstance(rec, dict):
        return out
    blocks = [("src_sha", rec.get("src_sha"), True)] + [
        ("%s.src_sha" % s, (rec.get(s) or {}).get("src_sha"), False) for s in SECTIONS]
    for label, src, top in blocks:
        if isinstance(src, dict):
            for f, v in src.items():
                out.append((label, str(f).replace("\\", "/"), top, v))
    return out


def dq1_forms(env, files):
    """({file: {"lf", "crlf"} or None}, problems): the two checkout forms of each file's blob at the dq1 head."""
    forms, probs = {}, []
    for fn in sorted(set(files)):
        rc, blob, err = env.git(["show", "%s:%s" % (env.dq1_head, fn)])
        if rc != 0:
            forms[fn] = None
            probs.append("git show %s:%s failed (rc %d): %s" % (env.dq1_head[:8], fn, rc,
                                                                err.decode("utf-8", "replace").strip()[:200]))
        else:
            forms[fn] = blob_forms(blob)
    return forms, probs


def replay_at(env, rev):
    """(LF sha256 of outputs/_dq_replay.py's blob at rev, problem)."""
    rc, blob, err = env.git(["show", "%s:%s" % (rev, REPLAY_REL)])
    if rc != 0:
        return None, "git show %s:%s failed (rc %d): %s" % (rev[:8], REPLAY_REL, rc,
                                                          err.decode("utf-8", "replace").strip()[:200])
    return _sha(_lf(blob)), None


# ================================================================================================= cfv (ast, never imported)
def cfv_values(src: str):
    """({key: {"value", "line", "source"}}, problems): DISPATCH_JOINT and DISPATCH_REASSIGN must each be bound exactly
    once in the module, by a plain module-level assignment to the int literal 1 (type int: not True, 1.0 or "1")."""
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {}, ["common_fixed_variables.py does not parse: %s" % exc]
    found = {k: [] for k in FLIP_KEYS}
    probs = []
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
            targets = [node.target]
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            targets = [node.target]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets = [it.optional_vars for it in node.items if it.optional_vars is not None]
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if alias.name == "*" or bound in found:
                    probs.append("line %d: an import that can bind %s" % (node.lineno, alias.name))
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for n in node.names:
                if n in found:
                    probs.append("line %d: a global / nonlocal declaration of %s" % (node.lineno, n))
        for t in targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name) and n.id in found:
                    found[n.id].append(node)
    vals = {}
    for k, nodes in found.items():
        if len(nodes) != 1:
            probs.append("%s is bound %d times (exactly one module-level assignment required)" % (k, len(nodes)))
            continue
        node = nodes[0]
        if not (isinstance(node, ast.Assign) and node in tree.body and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            probs.append("%s (line %d) is not a plain module-level assignment" % (k, node.lineno))
            continue
        try:
            v = ast.literal_eval(node.value)
        except ValueError:
            probs.append("%s (line %d) is not a literal" % (k, node.lineno))
            continue
        if type(v) is not int or v != 1:
            probs.append("%s = %r (line %d): the flip ships the int literal 1" % (k, v, node.lineno))
            continue
        vals[k] = {"value": v, "line": node.lineno, "source": ast.get_source_segment(src, node)}
    return vals, probs


def read_cfv(env):
    data = None
    try:
        with open(env.abs("common_fixed_variables.py"), "rb") as fh:
            data = fh.read()
    except OSError as exc:
        return {}, ["common_fixed_variables.py unreadable: %s" % exc]
    return cfv_values(data.decode("utf-8", "replace"))


# ================================================================================================= scope (ast)
def _strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(
                    first.value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
    return tree


def _neutralise_flip(tree):
    """The module-level assignments of the flip keys with their value replaced by a marker; returns their values."""
    vals = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and \
                node.targets[0].id in FLIP_KEYS:
            try:
                vals[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                vals[node.targets[0].id] = "<non-literal>"
            node.value = ast.Constant("<flip value>")
    return vals


def scope_of(old_src, new_src) -> str:
    """What the flip commit changed in one Python file, by its ast (docstrings, comments and layout ignored)."""
    try:
        t0, t1 = ast.parse(old_src), ast.parse(new_src)
    except SyntaxError as exc:
        return "UNPARSABLE (%s)" % exc
    _strip_docstrings(t0)
    _strip_docstrings(t1)
    if ast.dump(t0) == ast.dump(t1):
        return "code-identical (docstrings / comments / layout only)"
    v0, v1 = _neutralise_flip(t0), _neutralise_flip(t1)
    if ast.dump(t0) == ast.dump(t1):
        moved = ["%s %r -> %r" % (k, v0.get(k), v1.get(k)) for k in FLIP_KEYS if v0.get(k) != v1.get(k)]
        return "code-identical except " + (", ".join(moved) if moved else "nothing")
    n0, n1 = [ast.dump(s) for s in t0.body], [ast.dump(s) for s in t1.body]
    return "CODE CHANGED (%d of %d / %d top-level statements differ)" % (
        len(set(n0) ^ set(n1)), len(n0), len(n1))


def scope_report(env, head, changed):
    out = {}
    for rel in changed:
        if not rel.endswith(".py"):
            out[rel] = "not a Python file"
            continue
        rc0, old, _e0 = env.git(["show", "%s:%s" % (env.dq1_head, rel)])
        rc1, new, _e1 = env.git(["show", "%s:%s" % (head, rel)])
        if rc0 != 0 or rc1 != 0:
            out[rel] = "added or removed (no blob at %s)" % ("the dq1 head" if rc0 else "SHA")
            continue
        out[rel] = scope_of(old.decode("utf-8", "replace"), new.decode("utf-8", "replace"))
    return out


# ================================================================================================= the lines
def _pairs(argv):
    rest = argv[4:]
    return [(rest[i], rest[i + 1]) for i in range(0, len(rest) - 1, 2)], len(rest) % 2


def validate_w2_line(env, w) -> list:
    """The dq1 W2 line as the screen froze it (outputs/_dq_queue.py section 9 shape), re-checked."""
    p = []
    name = w.get("name", "?")
    if list(w) != LINE_KEYS:
        p.append("keys %s" % list(w))
        return p
    m = REF_RE.match(name)
    if not m:
        return ["not a dq1<p><k>_<S>_<W> name"]
    argv = w["argv"]
    if argv[:4] != [env.probe, "--crn", "--hazard", "--"]:
        p.append("probe head %r" % argv[:4])
    pairs, odd = _pairs(argv)
    if odd:
        p.append("odd flag / value list")
    val = {}
    for f, v in pairs:
        if f != "--set":
            if f in val:
                p.append("flag %s repeated" % f)
            val[f] = v
    if _norm(val.get("--repo", "")) != _norm(env.wt) or _norm(w["cwd"]) != _norm(env.wt):
        p.append("--repo %r / cwd %r is not %s" % (val.get("--repo"), w["cwd"], env.wt))
    want_out = os.path.join(env.out, "_sd_%s.json" % name)
    if val.get("--out") != w["out"] or _norm(w["out"]) != _norm(want_out):
        p.append("--out %r / out %r is not %s" % (val.get("--out"), w["out"], want_out))
    if val.get("--tag") != name:
        p.append("--tag %r" % val.get("--tag"))
    if val.get("--scenario") != m.group(3) or val.get("--wind") != WIND[m.group(4)]:
        p.append("scenario / wind %r %r" % (val.get("--scenario"), val.get("--wind")))
    if val.get("--steps") != str(STEPS):
        p.append("--steps %r" % val.get("--steps"))
    sets = [v for f, v in pairs if f == "--set"]
    for s in FLIP_SETS:
        if sets.count(s) != 1:
            p.append("the pair --set %s occurs %d times (exactly once)" % (s, sets.count(s)))
    other = [t for t in argv if "DISPATCH_" in str(t) and t not in FLIP_SETS]
    if other:
        p.append("other DISPATCH_ tokens %s" % other)
    return p


def flip_line(env, w) -> dict:
    """The flip line of a W2 line: the two DISPATCH pairs removed, --out and --tag replaced (ValueError if the W2 line
    does not hold each pair exactly once)."""
    argv = list(w["argv"])
    for s in FLIP_SETS:
        idx = [i for i in range(1, len(argv)) if argv[i] == s and argv[i - 1] == "--set"]
        if len(idx) != 1:
            raise ValueError("%s: the pair --set %s occurs %d times" % (w.get("name"), s, len(idx)))
        del argv[idx[0] - 1:idx[0] + 1]
    tag = "dqF" + w["name"][3:]
    out = os.path.join(env.out_dir, "_sd_%s.json" % tag)
    for flag, new in (("--out", out), ("--tag", tag)):
        if argv.count(flag) != 1:
            raise ValueError("%s: %s occurs %d times" % (w.get("name"), flag, argv.count(flag)))
        argv[argv.index(flag) + 1] = new
    return {"name": tag, "argv": argv, "out": out, "cwd": w["cwd"]}


def validate_flip_line(env, w, ln) -> list:
    """Token for token against the W2 line, written independently of flip_line: walking both argv lists, the only
    differences are the two removed pairs and the --out / --tag values (exactly four)."""
    p = []
    if list(ln) != LINE_KEYS:
        return ["keys %s (exactly %s)" % (list(ln), LINE_KEYS)]
    name = ln["name"]
    if not FLIP_RE.match(name) or name != "dqF" + w["name"][3:]:
        p.append("name %r is not dqF + %s" % (name, w["name"][3:]))
    want_out = os.path.join(env.out_dir, "_sd_%s.json" % name)
    if ln["out"] != want_out or not os.path.isabs(ln["out"]):
        p.append("out %r is not %s" % (ln["out"], want_out))
    if ln["cwd"] != w["cwd"] or _norm(ln["cwd"]) != _norm(env.wt):
        p.append("cwd %r differs from the W2 line's %r / %s" % (ln["cwd"], w["cwd"], env.wt))
    a, b = w["argv"], ln["argv"]
    i = j = 0
    removed, replaced = [], []
    while i < len(a):
        # the pair removal is tried BEFORE the equal-token step: a "--set" of a removed DISPATCH pair must not be
        # matched greedily against the "--set" of the next pair on the flip line (a correct line would be refused)
        if a[i] == "--set" and i + 1 < len(a) and a[i + 1] in FLIP_SETS:
            removed.append(a[i + 1])
            i += 2
            continue
        if j < len(b) and a[i] == b[j]:
            i += 1
            j += 1
            continue
        if j < len(b) and i > 0 and j > 0 and a[i - 1] in ("--out", "--tag") and b[j - 1] == a[i - 1]:
            replaced.append((a[i - 1], b[j]))
            i += 1
            j += 1
            continue
        p.append("W2 token %d %r vs flip token %d %r: not one of the four changes" % (
            i, a[i], j, b[j] if j < len(b) else None))
        break
    if not p and j != len(b):
        p.append("the flip line has %d extra tokens %s" % (len(b) - j, b[j:]))
    if sorted(removed) != sorted(FLIP_SETS):
        p.append("removed pairs %s (exactly %s)" % (removed, list(FLIP_SETS)))
    if sorted(replaced) != sorted([("--out", ln["out"]), ("--tag", name)]):
        p.append("replaced values %s (exactly --out -> out, --tag -> name)" % replaced)
    if any("DISPATCH_" in str(t) for t in b):
        p.append("a DISPATCH_ token on the flip line")
    if not p and len(removed) + len(replaced) != 4:
        p.append("%d changes (exactly 4)" % (len(removed) + len(replaced)))
    return p


def cells_problems() -> list:
    p = []
    names = [c for c, _r in FLIP_CELLS]
    if len(set(names)) != 8 or any(not REF_RE.match(n) for n in names):
        p.append("FLIP_CELLS: 8 distinct dq1 names required")
    per = Counter(REF_RE.match(n).group(2) for n in names if REF_RE.match(n))
    if per != Counter({"7": 4, "8": 4}):
        p.append("FLIP_CELLS: 4 per fresh set required, got %s" % dict(per))
    return p


def load_queue_lines(path):
    with open(path, "rb") as fh:
        data = fh.read()
    lines = [json.loads(x) for x in _lf(data).decode("utf-8").splitlines() if x.strip()]
    return data, lines


def derive_all(env):
    """(lines, w2 lines, problems): the W2 queue (its LF sha256 frozen), the 8 lines derived and validated."""
    p = cells_problems()
    try:
        data, w2 = load_queue_lines(env.w2)
    except (OSError, ValueError) as exc:
        return [], [], p + ["the W2 queue %s: %s" % (env.w2, exc)]
    if _sha(_lf(data)) != env.w2_sha:
        p.append("the W2 queue's LF sha256 %s is not the frozen %s" % (_sha(_lf(data)), env.w2_sha))
    by = {}
    for w in w2:
        if w.get("name") in by:
            p.append("W2 name %s repeated" % w.get("name"))
        by[w.get("name")] = w
    lines, refs = [], []
    for ref_name, _reason in FLIP_CELLS:
        w = by.get(ref_name)
        if w is None:
            p.append("%s is not in the W2 queue" % ref_name)
            continue
        p += ["W2 %s: %s" % (ref_name, x) for x in validate_w2_line(env, w)]
        try:
            ln = flip_line(env, w)
        except ValueError as exc:
            p.append(str(exc))
            continue
        p += ["%s: %s" % (ln["name"], x) for x in validate_flip_line(env, w, ln)]
        lines.append(ln)
        refs.append(w)
    if len({ln["name"].lower() for ln in lines}) != len(lines) or len({_norm(ln["out"]) for ln in lines}) != len(lines):
        p.append("duplicate flip names or outputs")
    return lines, refs, p


# ================================================================================================= record checks
def _crn_ok(rec) -> bool:
    crn = ((rec.get("fb3") or {}).get("crn") or {}) if isinstance(rec, dict) else {}
    draws = crn.get("crn_draws")
    return crn.get("on") is True and type(draws) is int and draws > 0


def ref_validity(env, w, ref, sidecar) -> list:
    """The dq1 reference record of a cell (the screen's own run of the W2 line)."""
    if not isinstance(ref, dict):
        return ["dq1 record missing or unreadable"]
    p = []
    if ref.get("complete") is not True or ref.get("crashed") is not None or ref.get("steps_done") != STEPS:
        p.append("incomplete (complete %r, crashed %r, steps_done %r)" % (
            ref.get("complete"), ref.get("crashed"), ref.get("steps_done")))
    if not _crn_ok(ref):
        p.append("CRN not on with draws > 0")
    if ref.get("head") != env.dq1_head:
        p.append("head %r is not the screen head %s" % (ref.get("head"), env.dq1_head))
    if _norm(ref.get("repo", "")) != _norm(env.wt):
        p.append("repo %r" % ref.get("repo"))
    if ref.get("tag") != w["name"] or ref.get("argv") != w["argv"][4:]:
        p.append("tag / argv are not its W2 line's")
    if sidecar != signature(w):
        p.append("the pool .argv sidecar is not its W2 line's signature")
    for sec in ("extra_params", "params"):
        for k in FLIP_KEYS:
            v = (ref.get(sec) or {}).get(k)
            if type(v) is not int or v != 1:
                p.append("%s.%s = %r (dq1 set it to 1)" % (sec, k, v))
    sw = (ref.get("dq") or {}).get("switches") or {}
    if sw.get("joint_on") is not True or sw.get("reassign_on") is not True:
        p.append("dq.switches joint_on / reassign_on not both True")
    return p


def validity(env, line, rec, sidecar, fz) -> list:
    """(a) the flip record."""
    if not isinstance(rec, dict):
        return ["flip record missing or unreadable"]
    p = []
    if rec.get("complete") is not True:
        p.append("complete %r" % rec.get("complete"))
    if rec.get("crashed") is not None:
        p.append("crashed %r" % (rec.get("crashed"),))
    if type(rec.get("steps_done")) is not int or rec.get("steps_done") != STEPS:
        p.append("steps_done %r (%d)" % (rec.get("steps_done"), STEPS))
    if not _crn_ok(rec):
        p.append("CRN not on with crn_draws > 0: %r" % ((rec.get("fb3") or {}).get("crn"),))
    if rec.get("head") != fz.get("head"):
        p.append("head %r is not the frozen SHA %s" % (rec.get("head"), fz.get("head")))
    if _norm(rec.get("repo", "")) != _norm(env.wt):
        p.append("repo %r" % rec.get("repo"))
    if rec.get("tag") != line["name"]:
        p.append("tag %r is not %s" % (rec.get("tag"), line["name"]))
    if rec.get("argv") != line["argv"][4:]:
        p.append("argv is not the queue line's probe arguments")
    if sidecar != signature(line):
        p.append("the pool .argv sidecar is not the queue line's signature")
    disp = [t for t in list(line["argv"]) + list(rec.get("argv") or []) if "DISPATCH_" in str(t)]
    if disp:
        p.append("DISPATCH_ tokens on the argv: %s" % disp)
    for sec in ("extra_params", "params"):
        keys = [k for k in (rec.get(sec) or {}) if str(k).startswith("DISPATCH_")]
        if keys:
            p.append("%s holds %s (the defaults must decide)" % (sec, keys))
    cfv = fz.get("cfv") or {}
    dq = rec.get("dq") or {}
    sw = dq.get("switches") or {}
    raw = sw.get("raw") or {}
    dp_sw = (rec.get("dp") or {}).get("switches") or {}
    for flag in ("joint_on", "reassign_on"):
        if sw.get(flag) is not True or dp_sw.get(flag) is not True:
            p.append("%s not True in dq.switches / dp.switches (%r / %r)" % (flag, sw.get(flag), dp_sw.get(flag)))
    for k in FLIP_KEYS:
        if k not in cfv:
            p.append("the freeze has no cfv value for %s" % k)
            continue
        want = repr(cfv[k]["value"])
        if raw.get(k) != want or dp_sw.get(k) != want:
            p.append("the raw %s read %r (dq) / %r (dp); the frozen default reads %r" % (k, raw.get(k), dp_sw.get(k),
                                                                                       want))
    rl = fz.get("run_loaded") or {}

    def lf_of(rel):
        return (rl.get(rel) or {}).get("lf")
    mvg = rec.get("mvg") or {}
    if not lf_of("outputs/_dq_probe.py") or dq.get("probe_sha") != lf_of("outputs/_dq_probe.py") or \
            mvg.get("probe_sha") != lf_of("outputs/_dq_probe.py"):
        p.append("probe_sha (dq %r, mvg %r) is not the frozen LF sha256 of outputs/_dq_probe.py" % (
            str(dq.get("probe_sha"))[:16], str(mvg.get("probe_sha"))[:16]))
    if dq.get("r1_shadow_sha") != lf_of("outputs/_dq_r1_shadow.py"):
        p.append("dq.r1_shadow_sha is not the frozen LF sha256 of outputs/_dq_r1_shadow.py")
    if mvg.get("u1_shadow_sha") != lf_of("outputs/_mvg_u1_shadow.py"):
        p.append("mvg.u1_shadow_sha is not the frozen LF sha256 of outputs/_mvg_u1_shadow.py")
    blocks = [("src_sha", rec.get("src_sha"), True)] + [
        ("%s.src_sha" % s, (rec.get(s) or {}).get("src_sha"), False) for s in SECTIONS]
    for label, src, top in blocks:
        if not isinstance(src, dict) or not src:
            p.append("%s missing or empty" % label)
            continue
        for f, v in src.items():
            fn = str(f).replace("\\", "/")
            h = rl.get(fn)
            if h is None:
                p.append("%s[%s]: not a frozen run-loaded file" % (label, fn))
            elif v != (h["raw"][:16] if top else h["raw"]):
                p.append("%s[%s] %s is not the frozen raw sha256 %s" % (label, fn, str(v)[:16], h["raw"][:16]))
    return p


def classify_path(p, vol, ref, rec, ctx):
    """(class, why): one json_diff path of dq1 (X) vs the flip record (R0); class OTHER when no allowed class's
    condition holds (see the module docstring)."""
    base, sep, _suffix = p.partition(" (")
    if vol:
        if base == ".tag":
            ok = ref.get("tag") == ctx["w2"]["name"] and rec.get("tag") == ctx["line"]["name"]
            return ("N", "") if ok else ("OTHER", "the tags are not the two lines' names")
        if base == ".argv" or base.startswith(".argv["):
            ok = ref.get("argv") == ctx["w2"]["argv"][4:] and rec.get("argv") == ctx["line"]["argv"][4:]
            return ("A", "") if ok else ("OTHER", "the argv lists are not the two lines'")
        if sep:
            return "OTHER", "a length / key-set difference inside a timing field (a different count of timed calls)"
        try:
            a, b = resolve(ref, base), resolve(rec, base)
        except (KeyError, IndexError, TypeError):
            return "OTHER", "an unresolvable timing path"
        if _num(a) and _num(b):
            return "T", ""
        return "OTHER", "a timing field without a number on both sides (%r / %r)" % (a, b)
    if p in K_PATHS:
        sec, k = base.split(".")[1], base.split(".")[2]
        v = (ref.get(sec) or {}).get(k)
        ok = type(v) is int and v == 1 and k not in (rec.get(sec) or {})
        return ("K", "") if ok else ("OTHER", "%s.%s: dq1 %r, flip %r" % (sec, k, v, (rec.get(sec) or {}).get(k)))
    if p == ".head":
        ok = ref.get("head") == ctx["dq1_head"] and rec.get("head") == ctx["head"]
        return ("H", "") if ok else ("OTHER", "head dq1 %r / flip %r" % (ref.get("head"), rec.get("head")))
    m = SRC_RE.match(p)
    if m and not sep:
        sec, f = m.group(1), m.group(2)
        top = sec is None
        src_ref = (ref.get("src_sha") if top else (ref.get(sec) or {}).get("src_sha")) or {}
        src_rec = (rec.get("src_sha") if top else (rec.get(sec) or {}).get("src_sha")) or {}
        if f not in src_ref or f not in src_rec:
            return "OTHER", "an unresolvable src_sha path"
        fn = f.replace("\\", "/")
        h = (ctx["hashes"] or {}).get(fn)
        if h is None:
            return "OTHER", "%s is not a frozen run-loaded file" % fn
        if src_rec[f] != (h["raw"][:16] if top else h["raw"]):
            return "OTHER", "the flip record's %s hash is not the frozen raw sha256" % fn
        forms = (ctx.get("dq1_forms") or {}).get(fn)
        if not is_form(src_ref[f], forms, top):
            return "OTHER", "dq1's %s hash is neither the LF nor the CRLF form of its blob at the dq1 head" % fn
        if fn in ctx["changed"]:
            want, got = ALLOWED_SCOPE.get(fn), (ctx.get("scope") or {}).get(fn)
            if want is None or got != want:
                return "OTHER", "%s changed since the dq1 head with scope %r (S only for exactly %r)" % (fn, got, want)
            return "S", "%s: changed, scope %s" % (fn, got)
        if forms["lf"] == h["lf"]:
            return "S", "%s: line endings only" % fn
        return "OTHER", "%s's content changed but it is not in the changed list" % fn
    return "OTHER", "not an allowed difference"


def identity(ref, rec, ref_stdout, rec_stdout, ctx):
    """(b): {"r0": r0_reproduces differences, "classes": {class: [paths]}, "other": [[path, why]], "n": paths}."""
    R = replay_module()
    r0 = R.r0_reproduces(ref, rec, ref_stdout, rec_stdout)
    paths = R.json_diff(ref, rec, limit=10 ** 9)
    mv_cols = (ref.get("mv") or {}).get("cols")
    g_cols = ((ref.get("mvg") or {}).get("guard") or {}).get("cols")
    vol, oth = R.classify_diff(paths, mv_cols, g_cols, None)
    vol_set = set(vol)
    classes = {c: [] for c in CLASSES}
    other, why_s = [], Counter()
    for p in paths:
        cls, why = classify_path(p, p in vol_set, ref, rec, ctx)
        if cls == "OTHER":
            other.append([p, why])
        else:
            classes[cls].append(p)
            if cls == "S":
                why_s[why] += 1
    assert len(vol) + len(oth) == len(paths)
    return {"r0": r0, "classes": classes, "other": other, "n": len(paths), "s_why": dict(why_s)}


def shape(path: str) -> str:
    """A json_diff path with its list indices folded ([i]) - a row / column path keeps its column ([i][35]); a ' (...)'
    suffix kept."""
    base, sep, suffix = path.partition(" (")
    m = re.search(r"(?<=\])\[\d+\]$", base)
    head, tail = (base[:m.start()], base[m.start():]) if m else (base, "")
    return re.sub(r"\[\d+\]", "[i]", head) + tail + sep + suffix


def coverage(ref) -> Counter:
    """J decisions in a dq1 record: dp.j_events (kind / reason)."""
    c = Counter()
    for e in ((ref or {}).get("dp") or {}).get("j_events") or []:
        if isinstance(e, dict):
            c["%s/%s" % (e.get("kind"), e.get("reason"))] += 1
    return c


# ================================================================================================= freeze
def build_freeze(env, head, lines, refs, cfv, rels, hashes, changed, ancestor, scope, tag_rows, cov, forms,
                 replay_head_lf):
    ref_sha = {}
    for w in refs:
        h = file_hashes(w["out"])
        s = file_hashes(stdout_path(w["out"]))
        ref_sha[w["name"]] = {"record": h and h["raw"], "stdout": s and s["raw"]}
    with open(env.w2, "rb") as fh:
        w2_lf = _sha(_lf(fh.read()))
    return {
        "tool": VERSION,
        "written": time.strftime("%Y-%m-%d %H:%M:%S"),
        "head": head,
        "dq1_head": env.dq1_head,
        "descends_from_dq1_head": ancestor,
        "cfv": cfv,
        "queue": {"path": env.rel(env.queue), "lf_sha256": _sha(queue_text(lines).encode("utf-8")), "lines": len(lines)},
        "w2": {"path": env.rel(env.w2), "lf_sha256": w2_lf},
        "cells": [[ln["name"], w["name"], dict(FLIP_CELLS)[w["name"]]] for ln, w in zip(lines, refs)],
        "run_loaded_rule": {"globs": list(RUN_LOADED_GLOBS), "chain": list(CHAIN), "exclude": QUARANTINE_EXCLUDE},
        "run_loaded": {rel: hashes[rel] for rel in rels},
        "tooling": {rel: file_hashes(env.abs(rel)) for rel in TOOLING},
        "replay_at_head_lf": replay_head_lf,
        "refs": ref_sha,
        "flip_changed": changed,
        "scope": scope,
        "allowed_scope": dict(ALLOWED_SCOPE),
        "dq1_forms": forms,
        "tag_check": tag_rows,
        "coverage": {w["name"]: dict(sorted(cov.get(w["name"], Counter()).items())) for w in refs},
    }


def _print_rows(say, rows):
    head = ["check", "scanned", "hits", "control", "verdict"]
    width = [max(len(str(r[i])) for r in list(rows) + [head]) for i in range(5)]
    for r in [head] + list(rows):
        say("    " + "  ".join(str(r[i]).ljust(width[i]) for i in range(5)).rstrip())


def write(env, head, dry_run=False, say=print) -> int:
    if not re.fullmatch(r"[0-9a-f]{40}", head or ""):
        say("REFUSED: --head must be the flip commit's full 40-hex sha (got %r)" % head)
        return 2
    if env.real and _norm(os.path.dirname(os.path.abspath(__file__))) != _norm(env.out):
        say("REFUSED: this tool must live in %s (the queue paths are absolute)" % env.out)
        return 2
    probs, notes = [], []
    lines, refs, p = derive_all(env)
    probs += p
    text = queue_text(lines)
    q_exists, f_exists = os.path.exists(env.queue), os.path.exists(env.freeze)
    if q_exists or f_exists:
        if q_exists and f_exists and p:
            say("REFUSED: a frozen queue + freeze exist and the lines no longer derive: %s" % p[:10])
            return 2
        if q_exists and f_exists:
            with open(env.queue, "rb") as fh:
                same_q = _lf(fh.read()).decode("utf-8") == text
            fz = _load_json(env.freeze) or {}
            rels, rp = run_loaded_list(env)
            same_h = not rp and fz.get("head") == head and fz.get("run_loaded") == hash_rels(env, rels)
            if same_q and same_h:
                say("unchanged (frozen): %s and %s (head %s)" % (env.queue, env.freeze, head[:8]))
                for x in launch_lines(env):
                    say(x)
                return 0
            say("REFUSED: a frozen queue / freeze exists and differs (never re-frozen): queue %s, freeze head and "
                "hashes %s" % ("identical" if same_q else "DIFFERS", "identical" if same_h else "DIFFER"))
            return 2
        say("REFUSED: a partial freeze exists (queue %s, freeze %s) - inspect it; never re-frozen" % (
            "present" if q_exists else "absent", "present" if f_exists else "absent"))
        return 2
    for path in (env.result, env.pool_log):
        if os.path.exists(path):
            probs.append("%s exists (a stale attempt?)" % path)
    if os.path.isdir(env.out_dir) and os.listdir(env.out_dir):
        probs.append("%s exists and is not empty" % env.out_dir)
    rc, out, err = _git_text(env, ["ls-files", "--", env.rel(env.queue), env.rel(env.out_dir), env.rel(env.result),
                                   env.rel(env.pool_log)])
    if rc != 0 or out.strip():
        probs.append("the queue / output directory / result / pool log is TRACKED or git failed: %r %r" % (
            out.strip()[:200], err.strip()[:200]))
    # git: HEAD and the run-loaded files
    rc, out, err = _git_text(env, ["rev-parse", "HEAD"])
    now = out.strip()
    if rc != 0 or now != head:
        probs.append("git HEAD %s is not --head %s" % (now or "?", head))
    probs += run_loaded_dirty(env)
    cfv, cp = read_cfv(env)
    probs += cp
    rels, rp = run_loaded_list(env)
    probs += rp
    hashes = hash_rels(env, rels or [])
    probs += ["run-loaded file missing: %s" % r for r, h in hashes.items() if h is None]
    rc, out, err = _git_text(env, ["diff", "--name-only", "-z", env.dq1_head, head, "--", *RUN_LOADED_GLOBS, *CHAIN,
                                   QUARANTINE_EXCLUDE])
    if rc != 0:
        probs.append("git diff %s..%s failed: %s" % (env.dq1_head[:8], head[:8], err.strip()[:200]))
        changed = []
    else:
        changed = sorted(x for x in out.split("\0") if x.strip())
    rc_a, _o, e_a = env.git(["merge-base", "--is-ancestor", env.dq1_head, head])
    ancestor = {0: True, 1: False}.get(rc_a, None)
    if ancestor is not True:
        probs.append("SHA %s does not descend from the dq1 head %s (git merge-base --is-ancestor rc %d%s): the "
                     "changed list would not bound the S class" % (
                         head[:8], env.dq1_head[:8], rc_a, (": " + e_a.decode("utf-8", "replace").strip()[:200])
                         if rc_a not in (0, 1) else ""))
    scope = scope_report(env, head, changed) if rc == 0 else {}
    for rel in changed:
        want, got = ALLOWED_SCOPE.get(rel), scope.get(rel)
        if want is None:
            probs.append("run-loaded file %s changed between the dq1 head and SHA (scope %r): only %s may change" % (
                rel, got, sorted(ALLOWED_SCOPE)))
        elif got != want:
            probs.append("%s changed between the dq1 head and SHA with scope %r: only %r is allowed" % (rel, got, want))
    probs += chain_untracked(env)
    # the identity rule: outputs/_dq_replay.py must be its committed blob at SHA
    replay_head_lf, rp_err = replay_at(env, head)
    replay_now = (file_hashes(env.abs(REPLAY_REL)) or {}).get("lf")
    if rp_err:
        probs.append(rp_err)
    elif replay_now != replay_head_lf:
        probs.append("%s (LF %s) is not its blob at SHA (LF %s): the identity rule must be committed" % (
            REPLAY_REL, str(replay_now)[:16], str(replay_head_lf)[:16]))
    # the dq1 references
    cov = {}
    ref_recs = {}
    for w in refs:
        ref = _load_json(w["out"])
        ref_recs[w["name"]] = ref
        probs += ["dq1 %s: %s" % (w["name"], x) for x in ref_validity(env, w, ref, _read_text(w["out"] + ".argv"))]
        if file_hashes(stdout_path(w["out"])) is None:
            probs.append("dq1 %s: its stdout file is missing" % w["name"])
        cov[w["name"]] = coverage(ref)
    # the checkout forms of every file the dq1 references hash, at the dq1 head (the S class's dq1 side)
    forms, fp = dq1_forms(env, [fn for ref in ref_recs.values() for _l, fn, _t, _v in src_files(ref)])
    probs += fp
    for name, ref in ref_recs.items():
        bad = sorted({"%s[%s]" % (label, fn) for label, fn, top, v in src_files(ref)
                      if forms.get(fn) and not is_form(v, forms[fn], top)})
        if bad:
            probs.append("dq1 %s: src_sha %s is neither the LF nor the CRLF form of the file at the dq1 head" % (
                name, bad[:8]))
    # the tag check (only on fully derived lines)
    tag_rows = []
    if len(lines) == len(FLIP_CELLS):
        try:
            tag_rows, details = env.tag_check(lines)
        except SystemExit as exc:
            tag_rows, details = [["tag check", "-", "-", "-", "FAIL (%s)" % exc]], []
        if any(not str(r[4]).startswith("PASS") for r in tag_rows):
            probs.append("TAG CHECK FAILED: %s" % (details[:20] or [r for r in tag_rows if not str(r[4]).startswith(
                "PASS")]))
    # report
    say("FLIP IDENTITY - WRITE (%s) at --head %s%s" % (VERSION, head, " [DRY RUN]" if dry_run else ""))
    say("  cfv (parsed, never imported): %s" % ", ".join(
        "%s = %r (line %d)" % (k, v["value"], v["line"]) for k, v in sorted(cfv.items())))
    say("  W2 %s (LF sha256 frozen %s)" % (env.w2, env.w2_sha[:16]))
    for ln, w in zip(lines, refs):
        say("  %-10s <- %-10s %-48s J decisions %s" % (ln["name"], w["name"], dict(FLIP_CELLS)[w["name"]],
                                                        dict(sorted(cov.get(w["name"], Counter()).items()))))
    union = Counter()
    for c in cov.values():
        union.update(c)
    say("  coverage, the 8 references together: %s" % dict(sorted(union.items())))
    say("  run-loaded files hashed: %d (tracked root *.py + src_extension/**/*.py + %d chain files)" % (
        len(rels or []), len(CHAIN)))
    say("  descends from the dq1 head %s: %s (required)" % (env.dq1_head[:8], ancestor))
    say("  run-loaded files changed between the dq1 head and SHA: %s" % (changed or "none"))
    for rel, verdict in sorted(scope.items()):
        say("    %-40s %s [%s]" % (rel, verdict, "ALLOWED" if ALLOWED_SCOPE.get(rel) == verdict else "REFUSED"))
    say("  %s LF %s, its blob at SHA LF %s" % (REPLAY_REL, str(replay_now)[:16], str(replay_head_lf)[:16]))
    say("  dq1-head forms of the %d files the dq1 references hash: %s" % (
        len(forms), "all found" if forms and all(forms.values()) else "MISSING %s" % [
            f for f, v in sorted(forms.items()) if not v]))
    if tag_rows:
        say("  tag check (outputs/_dq_queue.py tag_check, every registered worktree):")
        _print_rows(say, tag_rows)
    for n in notes:
        say("  NOTE " + n)
    if probs:
        say("REFUSED (%d):" % len(probs))
        for x in probs:
            say("  - " + x)
        return 2
    if dry_run:
        say("DRY RUN: every check passes; nothing written")
        for x in launch_lines(env):
            say("  (after a real write) " + x)
        return 0
    fz = build_freeze(env, head, lines, refs, cfv, rels, hashes, changed, ancestor, scope, tag_rows, cov, forms,
                      replay_head_lf)
    os.makedirs(env.out_dir, exist_ok=True)
    tq, tf = env.queue + ".tmp", env.freeze + ".tmp"
    with open(tq, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    with open(tf, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fz, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tf, env.freeze)
    os.replace(tq, env.queue)
    say("wrote %s (%d lines, LF sha256 %s) and %s (%d run-loaded files hashed, head %s)" % (
        env.queue, len(lines), fz["queue"]["lf_sha256"][:16], env.freeze, len(rels), head[:8]))
    for x in launch_lines(env):
        say(x)
    return 0


def launch_lines(env) -> list:
    """The launch command (bytecode off: the pool spawns <py> + argv without -B, so the inherited environment variable
    is what keeps .pyc out of the worktree) and the no-commit warning."""
    def fwd(p):
        return str(p).replace("\\", "/")
    tail = "%s -B %s %s %s --maxpar 8 --min-free-gb 3" % (fwd(PY), fwd(os.path.join(env.out, "_mf2_pool.py")),
                                                          fwd(env.queue), fwd(env.pool_log))
    return ["launch (bash): PYTHONDONTWRITEBYTECODE=1 " + tail,
            "launch (PowerShell): $env:PYTHONDONTWRITEBYTECODE = '1'; & " + tail,
            LAUNCH_WARNING]


# ================================================================================================= analyze
def rehash(env, fz):
    """(c), global: (problems, notes)."""
    p, notes = [], []
    rels, rp = run_loaded_list(env)
    p += rp
    now = hash_rels(env, rels or [])
    frozen = fz.get("run_loaded") or {}
    if not frozen:
        p.append("the freeze holds no run-loaded hashes")
    for rel in sorted(set(frozen) | set(now)):
        a, b = frozen.get(rel), now.get(rel)
        if a is None:
            p.append("NEW run-loaded file %s" % rel)
        elif b is None:
            p.append("MISSING run-loaded file %s" % rel)
        elif a["lf"] != b["lf"]:
            p.append("CHANGED %s (content)" % rel)
        elif a["raw"] != b["raw"]:
            p.append("CHANGED %s (line endings only; the probes hash raw bytes)" % rel)
    cfv, cp = read_cfv(env)
    p += cp
    if cfv != fz.get("cfv"):
        p.append("the cfv values re-parsed %s are not the frozen %s" % (cfv, fz.get("cfv")))
    for rel, h in sorted((fz.get("tooling") or {}).items()):
        if rel in TOOLING_STOP:
            continue                    # pinned: tooling_stop() STOPS on these
        now_h = file_hashes(env.abs(rel))
        if (now_h or {}).get("lf") != (h or {}).get("lf"):
            notes.append("TOOLING DRIFT: %s changed since write (frozen %s, now %s)" % (
                rel, str((h or {}).get("lf"))[:16], str((now_h or {}).get("lf"))[:16]))
    return p, notes


def tooling_stop(env, fz):
    """(STOP reasons, report lines): the identity rule (outputs/_dq_replay.py) must have its frozen LF sha256 and be
    its blob at SHA; this tool must have its frozen LF sha256."""
    stop, info = [], []
    frozen = fz.get("tooling") or {}
    head = fz.get("head") or ""
    for rel in TOOLING_STOP:
        want = (frozen.get(rel) or {}).get("lf")
        now = (file_hashes(env.abs(rel)) or {}).get("lf")
        info.append("%s LF sha256 now %s (frozen %s)" % (rel, now, want))
        if not want or now != want:
            stop.append("%s changed since write (frozen LF %s, now %s)" % (rel, str(want)[:16], str(now)[:16]))
    at_head, err = replay_at(env, head) if re.fullmatch(r"[0-9a-f]{40}", head) else (None, "no frozen head")
    info.append("%s LF sha256 of its blob at SHA %s" % (REPLAY_REL, at_head))
    if err:
        stop.append(err)
    elif at_head != (file_hashes(env.abs(REPLAY_REL)) or {}).get("lf") or at_head != fz.get("replay_at_head_lf"):
        stop.append("%s is not its blob at SHA (blob LF %s, frozen at-SHA LF %s)" % (
            REPLAY_REL, str(at_head)[:16], str(fz.get("replay_at_head_lf"))[:16]))
    return stop, info


def analyze(env, say=None) -> int:
    out_lines = []

    def emit(s=""):
        out_lines.append(s)
        (say or print)(s)

    fz = _load_json(env.freeze)
    if not isinstance(fz, dict):
        emit("STOP: no freeze record %s (run write first)" % env.freeze)
        return 2
    if env.real and _norm(HERE) != _norm(env.out):
        emit("STOP: this tool must run from %s (it loads outputs/_dq_replay.py beside itself)" % env.out)
        return 2
    t_stop, t_info = tooling_stop(env, fz)
    if t_stop:
        emit("STOP: the identity rule or this tool changed between write and analyze (nothing read): %s" % t_stop)
        for x in t_info:
            emit("  " + x)
        return 2
    lines, refs, p = derive_all(env)
    if p:
        emit("STOP: the lines do not re-derive: %s" % p[:10])
        return 2
    try:
        qdata, qlines = load_queue_lines(env.queue)
    except (OSError, ValueError) as exc:
        emit("STOP: the frozen queue %s: %s" % (env.queue, exc))
        return 2
    text = queue_text(lines)
    if _lf(qdata).decode("utf-8") != text or _sha(text.encode("utf-8")) != (fz.get("queue") or {}).get("lf_sha256") \
            or qlines != lines:
        emit("STOP: the frozen queue differs from the re-derived lines or from the freeze's sha256")
        return 2
    head = fz.get("head") or ""
    emit("=" * 118)
    emit("FLIP IDENTITY (outputs/dispatch2_part1.txt 10.8 THE FLIP: \"flip identity against dq1 on 4 + 4 cells\") - %s"
         % VERSION)
    emit("flip head (frozen --head): %s | dq1 head (the screen's Part 2 commit): %s | descends: %s" % (
        head, fz.get("dq1_head"), fz.get("descends_from_dq1_head")))
    emit("cfv (frozen, parsed): %s" % ", ".join("%s = %r (line %s)" % (k, v.get("value"), v.get("line"))
                                                 for k, v in sorted((fz.get("cfv") or {}).items())))
    emit("queue %s: %d lines, LF sha256 %s (re-derived from W2 %s, LF sha256 %s: identical)" % (
        env.queue, len(lines), fz["queue"]["lf_sha256"][:16], env.w2, env.w2_sha[:16]))
    for x in t_info:
        emit("tooling (pinned): " + x)
    emit("run-loaded files changed between the dq1 head and SHA, and their ast scope (S only for the ALLOWED ones):")
    for rel in fz.get("flip_changed") or []:
        verdict = (fz.get("scope") or {}).get(rel, "?")
        emit("  %-40s %s [%s]" % (rel, verdict, "ALLOWED" if ALLOWED_SCOPE.get(rel) == verdict else "NOT ALLOWED"))
    if not fz.get("flip_changed"):
        emit("  none")
    c_glob, notes = rehash(env, fz)
    emit("(c) THE FREEZE RE-HASH (global): %d run-loaded files - %s" % (
        len(fz.get("run_loaded") or {}), "unchanged" if not c_glob else "FAIL: %s" % c_glob[:12]))
    for n in notes:
        emit("NOTE " + n)
    ctx_base = {"head": head, "dq1_head": env.dq1_head, "changed": set(fz.get("flip_changed") or []),
                "hashes": fz.get("run_loaded") or {}, "scope": fz.get("scope") or {},
                "dq1_forms": fz.get("dq1_forms") or {}}
    emit("=" * 118)
    emit("PER CELL: (a) validity | (b) R0 rule + full-record diff (paths per allowed class; OTHER fails) | (c) re-hash")
    n_pass = 0
    union = {c: Counter() for c in CLASSES}
    s_why = Counter()
    details = []
    recs = {}
    for ln, w in zip(lines, refs):
        rec = _load_json(ln["out"])
        ref = _load_json(w["out"])
        recs[ln["name"]] = rec
        a = validity(env, ln, rec, _read_text(ln["out"] + ".argv"), fz) if rec is not None else [
            "flip record %s missing or unreadable" % ln["out"]]
        a_ref = ref_validity(env, w, ref, _read_text(w["out"] + ".argv"))
        c_cell = list(c_glob)
        fr = (fz.get("refs") or {}).get(w["name"]) or {}
        if (file_hashes(w["out"]) or {}).get("raw") != fr.get("record") or \
                (file_hashes(stdout_path(w["out"])) or {}).get("raw") != fr.get("stdout"):
            c_cell.append("the dq1 reference record / stdout changed since write")
        b = None
        if isinstance(rec, dict) and isinstance(ref, dict):
            b = identity(ref, rec, _read_text(stdout_path(w["out"])), _read_text(stdout_path(ln["out"])),
                         dict(ctx_base, w2=w, line=ln))
            for cls in CLASSES:
                union[cls].update(shape(x) for x in b["classes"][cls])
            s_why.update(b["s_why"])
        b_ok = b is not None and not b["r0"] and not b["other"]
        ok = not a and not a_ref and b_ok and not c_cell
        n_pass += ok
        counts = " ".join("%s %d" % (c, len(b["classes"][c])) for c in CLASSES) if b else "-"
        emit("  %-10s vs %-10s (a) %-7s (b) %-10s diff %5s paths: %s OTHER %s (c) %-4s => %s" % (
            ln["name"], w["name"], "VALID" if not a and not a_ref else "INVALID",
            "-" if b is None else ("REPRODUCES" if not b["r0"] else "DIFFERS"),
            b["n"] if b else "-", counts, len(b["other"]) if b else "-", "PASS" if not c_cell else "FAIL",
            "PASS" if ok else "FAIL"))
        if not ok:
            details.append("  %s:" % ln["name"])
            details += ["    (a) " + x for x in a] + ["    (a) dq1 reference: " + x for x in a_ref]
            if b is not None:
                if b["r0"]:
                    details.append("    (b) r0_reproduces differs: %s" % b["r0"])
                details += ["    (b) OTHER %s - %s" % (x, why) for x, why in b["other"][:40]]
                if len(b["other"]) > 40:
                    details.append("    (b) ... %d more OTHER paths" % (len(b["other"]) - 40))
            details += ["    (c) " + x for x in c_cell if x not in c_glob]
    if details:
        emit("FAILURES:")
        for d in details:
            emit(d)
    emit("ALLOWED DIFFERENCES SEEN (every path shape, all cells; the classes and their conditions: module docstring):")
    for cls in CLASSES:
        shapes = sorted(union[cls].items())
        emit("  %s %-100s %s" % (cls, CLASS_TEXT[cls], "none" if not shapes else ""))
        for sh, n in shapes:
            emit("      %6d  %s" % (n, sh))
    if s_why:
        emit("  S by file: %s" % dict(sorted(s_why.items())))
    emit("  raw switch provenance strings (dq.switches.raw / dp.switches DISPATCH_*): NOT an allowed class - repr of the "
         "int 1 in both arms, required equal")
    # the positive controls
    emit("=" * 118)
    emit("POSITIVE CONTROLS (outputs/mvg_report.txt 11.2 (b) convention): each flip record vs the same cell's dq0 (J off)"
         " and vs the next cell's dq1 - each must be DETECTED by r0_reproduces (an OTHER path alone does not count)")
    w1 = {}
    try:
        _d, w1_lines = load_queue_lines(env.w1)
        w1 = {x.get("name"): x for x in w1_lines}
    except (OSError, ValueError) as exc:
        emit("  the W1 queue %s: %s" % (env.w1, exc))
    n_det, n_ctl = 0, 0
    for i, (ln, w) in enumerate(zip(lines, refs)):
        rec = recs.get(ln["name"])
        nxt = refs[(i + 1) % len(refs)]
        z = w1.get("dq0" + w["name"][3:])
        for label, cw in (("dq0 same cell", z), ("dq1 %s" % nxt["name"], nxt)):
            n_ctl += 1
            ctl = _load_json(cw["out"]) if cw else None
            if not isinstance(rec, dict) or not isinstance(ctl, dict):
                emit("  %-10s vs %-16s UNAVAILABLE (not detected)" % (ln["name"], label))
                continue
            b = identity(ctl, rec, _read_text(stdout_path(cw["out"])), _read_text(stdout_path(ln["out"])),
                         dict(ctx_base, w2=cw, line=ln))
            det = bool(b["r0"])         # the behaviour rule must see it; OTHER (provenance) alone never counts
            n_det += det
            emit("  %-10s vs %-16s %s (r0 %s; OTHER %d)" % (ln["name"], label, "detected" if det else "NOT DETECTED",
                                                           b["r0"][:4], len(b["other"])))
    controls_ok = n_det == n_ctl == 2 * len(FLIP_CELLS)
    emit("  controls detected %d / %d => %s" % (n_det, 2 * len(FLIP_CELLS), "PASS" if controls_ok else "FAIL"))
    emit("=" * 118)
    passed = n_pass == len(FLIP_CELLS) and controls_ok
    why = []
    if n_pass != len(FLIP_CELLS):
        why.append("%d cell(s) fail" % (len(FLIP_CELLS) - n_pass))
    if not controls_ok:
        why.append("positive controls %d / %d detected" % (n_det, 2 * len(FLIP_CELLS)))
    emit("FLIP IDENTITY => %s %d/%d%s" % ("PASS" if passed else "FAIL", n_pass, len(FLIP_CELLS),
                                         "" if passed else " (%s)" % "; ".join(why)))
    tmp = env.result + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out_lines) + "\n")
    os.replace(tmp, env.result)
    return 0 if passed else 1


def show(env, say=print) -> int:
    lines, refs, p = derive_all(env)
    say("FLIP IDENTITY - SHOW (%s): the 8 lines derived from %s (nothing written)" % (VERSION, env.w2))
    ref_recs = {}
    for ln, w in zip(lines, refs):
        ref = _load_json(w["out"])
        ref_recs[w["name"]] = ref
        rv = ref_validity(env, w, ref, _read_text(w["out"] + ".argv"))
        sets = [ln["argv"][j + 1] for j, t in enumerate(ln["argv"][:-1]) if t == "--set"]
        say("  %-10s <- %-10s seed %-7s %-48s ref %s" % (ln["name"], w["name"], ln["argv"][ln["argv"].index("--seed") + 1],
                                                         dict(FLIP_CELLS)[w["name"]], "valid" if not rv else rv))
        say("      --set %s | J decisions %s" % (" ".join(sets), dict(sorted(coverage(ref).items()))))
        p += ["dq1 %s: %s" % (w["name"], x) for x in rv]
    # read-only git show: is every dq1 src_sha value the LF or the CRLF form of the file's blob at the dq1 head?
    forms, fp = dq1_forms(env, [fn for ref in ref_recs.values() for _l, fn, _t, _v in src_files(ref)])
    p += fp
    n_ent, kinds = 0, Counter()
    for name, ref in ref_recs.items():
        for label, fn, top, v in src_files(ref):
            n_ent += 1
            fm = forms.get(fn)
            kind = "neither" if not is_form(v, fm, top) else (
                "LF" if v in (fm["lf"], fm["lf"][:16]) else "CRLF")
            kinds[kind] += 1
            if kind == "neither":
                p.append("dq1 %s: %s[%s] is neither form of the file at the dq1 head" % (name, label, fn))
    say("  dq1 src_sha vs the dq1-head blob forms: %d entries over %d files: %s" % (n_ent, len(forms),
                                                                                  dict(sorted(kinds.items()))))
    cfv, cp = read_cfv(env)
    say("  cfv (parsed): %s %s" % (cfv and {k: v["value"] for k, v in cfv.items()}, cp or ""))
    for x in p:
        say("  PROBLEM " + x)
    say("SHOW %s" % ("OK" if not p and not cp else "PROBLEMS"))
    return 0 if not p and not cp else 2


# ================================================================================================= self-test
class _FakeGit:
    """A scripted git for the self-test (no repository touched)."""

    def __init__(self, state):
        self.s = state
        self.calls = []

    def __call__(self, args):
        self.calls.append(list(args))
        s = self.s
        key = args[0] + ("-chain" if "--error-unmatch" in args else "")
        if key in s.get("fail", ()):
            return 128, b"", b"fatal: scripted failure of git " + key.encode()
        if args[:2] == ["rev-parse", "HEAD"]:
            return 0, (s["head"] + "\n").encode(), b""
        if args[:1] == ["status"]:
            return 0, s["status"].encode(), b""
        if args[:1] == ["ls-files"] and "--error-unmatch" in args:
            asked = args[args.index("--") + 1:]
            have = [a for a in asked if a in s["chain_tracked"]]
            return (0 if len(have) == len(asked) else 1), "\0".join(have).encode(), (
                b"" if len(have) == len(asked) else b"error: pathspec did not match any file(s) known to git")
        if args[:2] == ["ls-files", "-z"]:
            return 0, "\0".join(s["files"]).encode(), b""
        if args[:1] == ["ls-files"]:
            return 0, s["tracked_own"].encode(), b""
        if args[:1] == ["diff"]:
            return 0, "\0".join(s["changed"]).encode(), b""
        if args[:1] == ["merge-base"]:
            return s["ancestor_rc"], b"", b""
        if args[:1] == ["show"]:
            rev, _c, path = args[1].partition(":")
            blob = s["blobs"].get((rev, path))
            return (0, blob, b"") if blob is not None else (128, b"", b"fatal: no such path")
        return 1, b"", b"unscripted git call"


OLD_CFV = "# config\nX = 3\nDISPATCH_JOINT = 0\nDISPATCH_REASSIGN = 0\n"
NEW_CFV = "# config (flipped)\nX = 3\nDISPATCH_JOINT = 1\nDISPATCH_REASSIGN = 1\n"
OLD_AGENTS = 'def f():\n    """Ships 0."""\n    return 1\n'
NEW_AGENTS = 'def f():\n    """Ships 1 since the flip,\n    two lines."""\n    return 1\n'


def _st_tree(root):
    """A synthetic dispatch tree: root .py files, src_extension, the chain, W1 / W2 queues and the dq1 / dq0 references
    of the 8 cells. Returns (env, git state, ref data)."""
    wt = os.path.join(root, "wt")
    files = {"agents.py": NEW_AGENTS, "common_fixed_variables.py": NEW_CFV, "wildfire_model.py": "Y = 2\n",
             "src_extension/planning/joint_dispatch.py": "Z = 1\n", "src_extension/execution/uav_executor.py": "U = 1\n"}
    for rel in CHAIN:
        files[rel] = "# %s\n" % rel
    for rel, txt in files.items():
        path = os.path.join(wt, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    for rel in TOOLING:
        path = os.path.join(wt, *rel.split("/"))
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# tooling %s\n" % rel)
    head = "f" * 40
    dq1_head = "1" * 40
    blobs = {}
    for rel, txt in files.items():             # every file at both heads (the repo stores LF)
        blobs[(dq1_head, rel)] = blobs[(head, rel)] = txt.encode()
    blobs.update({(dq1_head, "agents.py"): OLD_AGENTS.encode(), (head, "agents.py"): NEW_AGENTS.encode(),
                  (dq1_head, "common_fixed_variables.py"): OLD_CFV.encode(),
                  (head, "common_fixed_variables.py"): NEW_CFV.encode()})
    for rel in TOOLING:
        if rel != SELF_REL:                    # the tool itself is untracked
            blobs[(head, rel)] = blobs[(dq1_head, rel)] = ("# tooling %s\n" % rel).encode()
    state = {"head": head, "status": "", "files": [r for r in files if not r.startswith("outputs/")],
             "tracked_own": "", "changed": ["agents.py", "common_fixed_variables.py"], "ancestor_rc": 0,
             "chain_tracked": list(CHAIN), "fail": set(), "blobs": blobs,
             "tag_rows": [["own outputs", "40", "0", "-", "PASS"], ["git index", "9", "0", "found", "PASS"]],
             "tag_details": []}
    git = _FakeGit(state)

    def tag_check(lines):
        state["tag_seen"] = [ln["name"] for ln in lines]
        return state["tag_rows"], state["tag_details"]
    env = Env(wt=wt, git=git, tag_check=tag_check, w2_sha="0" * 64, dq1_head=dq1_head, real=False)
    old_raw = {"agents.py": _sha(OLD_AGENTS.encode()), "common_fixed_variables.py": _sha(OLD_CFV.encode())}
    # the W2 / W1 lines (the _dq_queue section 9 shape) for the 8 cells + 2 more
    names = [c for c, _r in FLIP_CELLS] + ["dq1r7_A_N", "dq1u8_D_W"]
    w2, w1 = [], []
    for i, name in enumerate(names):
        m = REF_RE.match(name)
        for arm, dest in (("1", w2), ("0", w1)):
            nm = "dq%s%s" % (arm, name[3:])
            out = os.path.join(env.out, "_sd_%s.json" % nm)
            argv = [env.probe, "--crn", "--hazard", "--", "--repo", env.wt, "--scenario", m.group(3), "--wind",
                    WIND[m.group(4)], "--seed", str(575201 + i), "--set", "GLOBAL_PLANNER_MODE=0", "--set",
                    "VICTIM_SPAWN_MODE=%d" % (m.group(1) == "u"), "--set", "FF_APPROACH_PATH=1", "--set",
                    "FF_RETREAT_KEEP_APPROACH=1", "--set", "FF_FIX_STRANDING_GUARD=1", "--set",
                    "DISPATCH_JOINT=%s" % arm, "--set", "DISPATCH_REASSIGN=%s" % arm, "--steps", "360", "--set",
                    "BATCH_SIZE=360", "--out", out, "--tag", nm]
            dest.append({"name": nm, "argv": argv, "out": out, "cwd": env.wt})
    for path, lines in ((env.w2, w2), (env.w1, w1)):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(queue_text(lines))
    with open(env.w2, "rb") as fh:
        env.w2_sha = _sha(_lf(fh.read()))
    # the reference records (dq1: as the screen ran them, at the dq1 head, with the OLD agents / cfv bytes)
    cur = hash_rels(env, state["files"] + list(CHAIN))
    for i, w in enumerate(w2 + w1):
        arm = w["name"][2]
        rec = _st_record(env, w, arm, dq1_head, cur, old_raw, seed_shift=i % len(w2) if arm == "1" else 100 + i)
        _st_dump(w, rec, stdout="stdout of %s\n" % (w["name"][3:] if arm == "1" else w["name"]))
    return env, state, {"w2": {x["name"]: x for x in w2}, "w1": {x["name"]: x for x in w1}, "old_raw": old_raw}


def _st_record(env, line, arm, head, cur, old_raw, seed_shift=0):
    """A synthetic probe record with every field the checks read."""
    def raw_of(rel):
        if rel in old_raw:
            return old_raw[rel]
        return cur[rel]["raw"]
    files_top = ["agents.py", "common_fixed_variables.py", "wildfire_model.py", "src_extension\\execution\\uav_executor.py"]
    sec_files = ["agents.py", "common_fixed_variables.py", "wildfire_model.py",
                 "src_extension/planning/joint_dispatch.py"]
    on = arm == "1"
    extra = {"GLOBAL_PLANNER_MODE": 0, "VICTIM_SPAWN_MODE": 0, "FF_APPROACH_PATH": 1}
    if arm in "01":
        extra.update({"DISPATCH_JOINT": int(arm), "DISPATCH_REASSIGN": int(arm)})
    extra["BATCH_SIZE"] = 360
    params = dict({"NUM_AGENTS": 3, "NUM_VICTIMS": 5}, **extra)
    sw = "1" if on else "0"
    k = seed_shift
    rec = {
        "probe": "sd_probe v1", "tag": line["name"], "repo": env.wt, "head": head,
        "src_sha": {f: raw_of(f.replace("\\", "/"))[:16] for f in files_top},
        "python": "3.10.11", "mesa": "1.2.1", "argv": line["argv"][4:], "params": params, "extra_params": extra,
        "effective": {"global_planner_mode": 0}, "eval": {"rescued": 4 + k, "dead": 1},
        "terminal_step": 200, "steps_done": 360, "crashed": None, "wall_s": 400.5, "complete": True,
        "warnings": [], "warning_count": 0, "stdout_sha": "s%d" % k,
        "rows_ff": [[["ff_unit_0", 5 + k, 6, "available"]]] * 3, "rows_vic": [[["victim_0", 1, 2]]] * 3,
        "rows_uav": [[["2500", 1, 1]]] * 3, "rows_dec": [{"m": "x"}] * 3, "rows_trig": [{"T": 1}] * 3,
        "fb3": {"probe": "fb3_probe v1", "crn": {"on": True, "crn_draws": 1000 + k}, "timing": {}},
        "dp": {"probe": "dp_probe v3",
               "switches": {"DISPATCH_JOINT": sw, "DISPATCH_REASSIGN": sw, "joint_on": on, "reassign_on": on,
                            "S": 10, "M": 5, "P": 3},
               "src_sha": {f: raw_of(f) for f in sec_files},
               "commands": [[12, "assign", "victim_1", "ff_unit_0"]],
               "j_events": [{"kind": "fill", "reason": "joint_initial", "step": 12}] if on else [],
               "j_calls": [[1, "pre", 0.015, 0], [1, "post", 0.020, 1]], "j_timing": [[1, "pre", 0.015, 0.015, 0, 0]],
               "timing": {"j_ms_total": 5.5}},
        "ud": {"switches": {"FF_APPROACH_PATH": True}, "src_sha": {f: raw_of(f) for f in sec_files[:3]},
               "kicks": [], "timing": {"wall_s": 400.5, "fix_calls": {"a": [0.1, 0.2]}}},
        "mv": {"cols": ["step", "unit", "fix_ms", "inst_ms"], "rows": [[80, "ff_unit_1", 0.01, 0.02]]},
        "mv_events": [{"step": 80, "kind": "a", "ran": True}],
        "mvg": {"probe": "dq_probe v1", "probe_sha": cur["outputs/_dq_probe.py"]["lf"],
                "switches": {"FF_APPROACH_PATH": True}, "src_sha": {f: raw_of(f) for f in sec_files[:3]},
                "u1_shadow_sha": cur["outputs/_mvg_u1_shadow.py"]["lf"], "u1_shadow_path": "x",
                "guard": {"cols": ["step", "admit", "ms_guard", "ms_inst"], "rows": [[80, True, 0.3, 0.4]]},
                "timing": {"guard_ms": [0.3], "guard_ms_total": 0.3}},
        "dq": {"probe": "dq_probe v1", "probe_sha": cur["outputs/_dq_probe.py"]["lf"],
               "switches": {"raw": {"DISPATCH_JOINT": sw, "DISPATCH_REASSIGN": sw, "DISPATCH_STALL_STEPS": "10"},
                            "joint_on": on, "reassign_on": on, "S": 10, "M": 5, "P": 3},
               "src_sha": {f: raw_of(f) for f in sec_files},
               "r1_shadow_sha": cur["outputs/_dq_r1_shadow.py"]["lf"], "sample": {"rows": [[1, [], [], [], [], []]]},
               "timing": {"dq_ms_total": 9.9, "jpoint_ms": 3.3}, "errors": []},
    }
    return rec


def _st_dump(line, rec, stdout="stdout\n", sidecar=True):
    os.makedirs(os.path.dirname(line["out"]), exist_ok=True)
    with open(line["out"], "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh)
    with open(stdout_path(line["out"]), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(stdout)
    if sidecar:
        with open(line["out"] + ".argv", "w", encoding="utf-8") as fh:
            fh.write(signature(line))


def _st_flip_record(env, ln, ref, fz):
    """The flip record a correct flip run would write: dq1's values, the four line changes, the frozen head and file
    hashes, new wall-clock values."""
    rec = copy.deepcopy(ref)
    rl = fz["run_loaded"]
    rec["tag"] = ln["name"]
    rec["argv"] = ln["argv"][4:]
    rec["head"] = fz["head"]
    for sec in ("params", "extra_params"):
        for k in FLIP_KEYS:
            rec[sec].pop(k, None)
    rec["src_sha"] = {f: rl[f.replace("\\", "/")]["raw"][:16] for f in rec["src_sha"]}
    for s in SECTIONS:
        rec[s]["src_sha"] = {f: rl[f]["raw"] for f in rec[s]["src_sha"]}
    rec["wall_s"] = 512.25
    rec["dq"]["timing"] = {"dq_ms_total": 11.1, "jpoint_ms": 4.4}
    rec["dp"]["j_calls"][1][2] = 0.031
    rec["dp"]["j_timing"][0][2] = 0.04
    rec["dp"]["timing"]["j_ms_total"] = 7.25
    rec["mv"]["rows"][0][2] = 0.05
    rec["mvg"]["guard"]["rows"][0][3] = 0.9
    rec["mvg"]["timing"]["guard_ms"] = [0.7]
    rec["ud"]["timing"]["fix_calls"]["a"] = [0.3, 0.1]
    rec["ud"]["timing"]["wall_s"] = 512.25
    return rec


def selftest(tmp_root=None) -> int:
    fails, out = [], []

    def case(name, cond, detail=""):
        out.append("%-4s %s%s" % ("PASS" if cond else "FAIL", name, ("  | " + str(detail)[:400]) if detail and not cond
                                  else ""))
        if not cond:
            fails.append(name)

    base = tempfile.mkdtemp(prefix="dq_flipid_st_", dir=tmp_root)
    quiet = []
    try:
        # ---------------------------------------------------------------- C1 the cells
        case("C1 FLIP_CELLS: 8 distinct dq1 cells, 4 per fresh set (7 / 8), each with its reason; tags dqF<p><k>_<S>_<W>"
             " (positive) - and the rule refuses a 9th / a set-6 cell (negative)",
             not cells_problems() and all(FLIP_RE.match("dqF" + c[3:]) for c, _r in FLIP_CELLS)
             and not REF_RE.match("dq1r6_A_E") and len(FLIP_CELLS) == 8)
        env, st, data = _st_tree(os.path.join(base, "t1"))
        lines, refs, p = derive_all(env)
        case("L1 derive: the 8 lines derive from the W2 queue and validate token for token (positive)",
             len(lines) == 8 and not p and [ln["name"] for ln in lines] == ["dqF" + c[3:] for c, _r in FLIP_CELLS], p)
        w, ln = refs[0], lines[0]
        diffs = len(w["argv"]) - len(ln["argv"])
        case("L2 the flip line = the W2 line minus exactly the two DISPATCH pairs, --out / --tag replaced, cwd kept",
             diffs == 4 and ln["argv"][ln["argv"].index("--tag") + 1] == ln["name"] and "DISPATCH" not in json.dumps(
                 ln["argv"]) and ln["cwd"] == w["cwd"] and ln["out"] == os.path.join(env.out_dir, "_sd_%s.json" %
                                                                                       ln["name"]))
        neg = {}
        bad = copy.deepcopy(ln)
        bad["argv"][bad["argv"].index("--seed") + 1] = "1"
        neg["seed changed"] = validate_flip_line(env, w, bad)
        bad = copy.deepcopy(ln)
        i = bad["argv"].index("--steps")
        bad["argv"][i:i] = ["--set", "DISPATCH_JOINT=1"]
        neg["a DISPATCH pair kept"] = validate_flip_line(env, w, bad)
        bad = copy.deepcopy(ln)
        bad["out"] = os.path.join(env.out, "_sd_%s.json" % ln["name"])
        bad["argv"][bad["argv"].index("--out") + 1] = bad["out"]
        neg["out outside _dq_flipid"] = validate_flip_line(env, w, bad)
        bad = copy.deepcopy(ln)
        bad["argv"][bad["argv"].index("--tag") + 1] = "dqFr7_A_X"
        neg["tag not the name"] = validate_flip_line(env, w, bad)
        bad = copy.deepcopy(ln)
        bad["cwd"] = env.out
        neg["cwd changed"] = validate_flip_line(env, w, bad)
        bad = dict(ln, ref="x")
        neg["an extra key"] = validate_flip_line(env, w, bad)
        bad = copy.deepcopy(ln)
        bad["argv"] = bad["argv"][:-2]
        neg["--tag pair dropped"] = validate_flip_line(env, w, bad)
        bad = copy.deepcopy(ln)
        bad["argv"].insert(bad["argv"].index("--steps"), "--set")
        neg["a stray --set"] = validate_flip_line(env, w, bad)
        missed = [k for k, v in neg.items() if not v]
        case("L3 validate_flip_line REFUSES 8 deviations (seed changed, a DISPATCH pair kept, out outside _dq_flipid, tag "
             "!= name, cwd changed, an extra key, the --tag pair dropped, a stray --set) (negative)", not missed, missed)
        w_bad = copy.deepcopy(w)
        j = w_bad["argv"].index("DISPATCH_REASSIGN=1")
        del w_bad["argv"][j - 1:j + 1]
        try:
            flip_line(env, w_bad)
            raised = False
        except ValueError:
            raised = True
        w_dup = copy.deepcopy(w)
        w_dup["argv"][w_dup["argv"].index("--steps"):w_dup["argv"].index("--steps")] = ["--set", "DISPATCH_JOINT=1"]
        case("L4 a W2 line without one pair, or with a pair twice, does not derive and fails its own validation "
             "(negative); the real W2 shape validates (positive)",
             raised and validate_w2_line(env, w_bad) and validate_w2_line(env, w_dup) and not validate_w2_line(env, w))
        # finding 10: a DISPATCH pair followed by another --set pair (the greedy walk refused this correct line)
        w_mod = copy.deepcopy(w)
        k = w_mod["argv"].index("--steps")
        steps_pair = w_mod["argv"][k:k + 2]
        del w_mod["argv"][k:k + 2]
        k = w_mod["argv"].index("--out")
        w_mod["argv"][k:k] = steps_pair
        ln_mod = flip_line(env, w_mod)
        dj = w_mod["argv"].index("DISPATCH_REASSIGN=1")
        follows = w_mod["argv"][dj + 1:dj + 3] == ["--set", "BATCH_SIZE=360"]
        kept = copy.deepcopy(ln_mod)
        k = kept["argv"].index("BATCH_SIZE=360") - 1
        kept["argv"][k:k] = ["--set", "DISPATCH_REASSIGN=1"]
        case("L6 (finding 10) a W2 line whose DISPATCH pair is followed by another --set pair: its flip line VALIDATES "
             "(positive; the greedy walk refused it); the same line keeping that pair is still REFUSED (negative)",
             follows and not validate_w2_line(env, w_mod) and validate_flip_line(env, w_mod, ln_mod) == []
             and validate_flip_line(env, w_mod, kept) != [],
             (follows, validate_flip_line(env, w_mod, ln_mod), validate_flip_line(env, w_mod, kept)))
        with open(env.w2, "rb") as fh:
            w2_bytes = fh.read()
        with open(env.w2, "wb") as fh:
            fh.write(w2_bytes.replace(b'"--steps", "360"', b'"--steps", "361"', 1))
        _l, _r, p_edit = derive_all(env)
        with open(env.w2, "wb") as fh:
            fh.write(w2_bytes)
        _l, _r, p_restored = derive_all(env)
        _l, _r, p_other = derive_all(Env(wt=env.wt, git=env.git, tag_check=env.tag_check, w2_sha="0" * 64,
                                         dq1_head=env.dq1_head, real=False))
        case("L5 the W2 queue must have its frozen LF sha256: an edited W2 (one token) and another frozen sha are refused "
             "(negative); the frozen bytes derive cleanly (positive)",
             any("LF sha256" in x for x in p_edit) and any("LF sha256" in x for x in p_other) and not p_restored,
             (p_edit[:2], p_other[:2], p_restored[:2]))
        # ---------------------------------------------------------------- cfv
        good, gp = cfv_values(NEW_CFV)
        negs = {}
        for label, src in (("= 0", NEW_CFV.replace("DISPATCH_JOINT = 1", "DISPATCH_JOINT = 0")),
                           ("= True", NEW_CFV.replace("DISPATCH_JOINT = 1", "DISPATCH_JOINT = True")),
                           ("= 1.0", NEW_CFV.replace("DISPATCH_JOINT = 1", "DISPATCH_JOINT = 1.0")),
                           ("= '1'", NEW_CFV.replace("DISPATCH_JOINT = 1", "DISPATCH_JOINT = '1'")),
                           ("missing", NEW_CFV.replace("DISPATCH_REASSIGN = 1\n", "")),
                           ("twice", NEW_CFV + "DISPATCH_JOINT = 1\n"),
                           ("in an if", NEW_CFV + "if X:\n    DISPATCH_REASSIGN = 0\n"),
                           ("augmented", NEW_CFV + "DISPATCH_JOINT += 0\n"),
                           ("star import", NEW_CFV + "from os import *\n"),
                           ("unparsable", NEW_CFV + "def (:\n")):
            negs[label] = cfv_values(src)[1]
        missed = [k for k, v in negs.items() if not v]
        case("F1 cfv parse: the int literal 1, once each, at module level (positive: values 1 / 1 with their line)",
             not gp and good["DISPATCH_JOINT"]["value"] == 1 and good["DISPATCH_REASSIGN"]["line"] == 4, (good, gp))
        case("F2 cfv parse REFUSES 10 forms (0, True, 1.0, '1', missing, twice, inside an if, augmented, a star import, "
             "unparsable) (negative)", not missed, missed)
        # ---------------------------------------------------------------- scope
        s1 = scope_of(OLD_AGENTS, NEW_AGENTS)
        s2 = scope_of(OLD_CFV, NEW_CFV)
        s3 = scope_of(OLD_AGENTS, OLD_AGENTS.replace("return 1", "return 2"))
        s4 = scope_of(OLD_CFV, NEW_CFV.replace("X = 3", "X = 4"))
        case("G1 ast scope: a docstring-only edit is code-identical; the cfv flip is 'code-identical except "
             "DISPATCH_JOINT 0 -> 1, DISPATCH_REASSIGN 0 -> 1' (positive); a code edit and a flip + another value are "
             "CODE CHANGED (negative)",
             s1.startswith("code-identical (") and s2 == "code-identical except DISPATCH_JOINT 0 -> 1, "
             "DISPATCH_REASSIGN 0 -> 1" and s3.startswith("CODE CHANGED") and s4.startswith("CODE CHANGED"),
             (s1, s2, s3, s4))
        # ---------------------------------------------------------------- write
        head = st["head"]
        rc_bad_head = write(env, "abc", say=quiet.append)
        st["head"] = "e" * 40
        rc_head = write(env, head, dry_run=True, say=quiet.append)
        st["head"] = head
        st["status"] = " M agents.py\n"
        rc_dirty = write(env, head, dry_run=True, say=quiet.append)
        st["status"] = ""
        st["tag_rows"] = [["own outputs", "40", "1", "-", "FAIL"]]
        st["tag_details"] = ["TAG IN USE x/_sd_dqFr7_A_E.json"]
        rc_tag = write(env, head, dry_run=True, say=quiet.append)
        st["tag_rows"] = [["own outputs", "40", "0", "-", "PASS"]]
        st["tag_details"] = []
        cfv_path = env.abs("common_fixed_variables.py")
        with open(cfv_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(OLD_CFV)
        rc_cfv = write(env, head, dry_run=True, say=quiet.append)
        with open(cfv_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(NEW_CFV)
        st["tracked_own"] = "outputs/_dq_q_flipid.jsonl\n"
        rc_tracked = write(env, head, dry_run=True, say=quiet.append)
        st["tracked_own"] = ""
        ref_path = refs[2]["out"]
        os.replace(ref_path, ref_path + ".aside")
        rc_ref = write(env, head, dry_run=True, say=quiet.append)
        os.replace(ref_path + ".aside", ref_path)
        os.makedirs(env.out_dir, exist_ok=True)
        with open(os.path.join(env.out_dir, "junk.txt"), "w") as fh:
            fh.write("x")
        rc_dir = write(env, head, dry_run=True, say=quiet.append)
        os.remove(os.path.join(env.out_dir, "junk.txt"))
        with open(env.result, "w") as fh:
            fh.write("old")
        rc_res = write(env, head, dry_run=True, say=quiet.append)
        os.remove(env.result)
        quiet.clear()
        rc_dry = write(env, head, dry_run=True, say=quiet.append)
        nothing = not os.path.exists(env.queue) and not os.path.exists(env.freeze)
        case("W1 write REFUSES (exit 2) on: a short --head, HEAD != SHA, a modified run-loaded file, a failed tag check, "
             "cfv not 1, a tracked queue path, a missing dq1 reference, a non-empty output directory, a stale result "
             "(negative)", [rc_bad_head, rc_head, rc_dirty, rc_tag, rc_cfv, rc_tracked, rc_ref, rc_dir, rc_res] ==
             [2] * 9, [rc_bad_head, rc_head, rc_dirty, rc_tag, rc_cfv, rc_tracked, rc_ref, rc_dir, rc_res])
        case("W2 --dry-run passes every check and writes nothing (positive); the tag check saw the 8 flip names",
             rc_dry == 0 and nothing and st.get("tag_seen") == [ln["name"] for ln in lines],
             (rc_dry, quiet[-3:]))

        # ---------------------------------------------------------------- write: the review's findings 1, 2, 5, 6, 11
        def dry(sub):
            quiet.clear()
            rc_ = write(env, head, dry_run=True, say=quiet.append)
            return rc_, any(sub in x for x in quiet)
        blobs = st["blobs"]
        blobs_saved, changed_saved = dict(blobs), list(st["changed"])

        def restore():
            blobs.clear()
            blobs.update(blobs_saved)
            st["changed"] = list(changed_saved)
        sneg = {}
        blobs[(head, "agents.py")] = NEW_AGENTS.replace("return 1", "return 1 if True else 2").encode()
        sneg["agents.py CODE CHANGED (E1)"] = dry("agents.py changed between the dq1 head and SHA with scope 'CODE CHANGED")
        restore()
        blobs[(head, "common_fixed_variables.py")] = NEW_CFV.replace("X = 3", "X = 4").encode()
        sneg["cfv flip + a third value"] = dry(
            "common_fixed_variables.py changed between the dq1 head and SHA with scope 'CODE CHANGED")
        restore()
        blobs[(head, "agents.py")] = b"def (:\n"
        sneg["agents.py UNPARSABLE"] = dry("agents.py changed between the dq1 head and SHA with scope 'UNPARSABLE")
        restore()
        st["changed"] = changed_saved + ["src_extension/other.py"]
        blobs[(env.dq1_head, "src_extension/other.py")] = b'"""a."""\nQ = 1\n'
        blobs[(head, "src_extension/other.py")] = b'"""b."""\nQ = 1\n'
        sneg["a third file, docstring only"] = dry(
            "src_extension/other.py changed between the dq1 head and SHA (scope 'code-identical")
        restore()
        st["changed"] = changed_saved + ["src_extension/added.py"]
        blobs[(head, "src_extension/added.py")] = b"A = 1\n"
        sneg["a file added"] = dry("src_extension/added.py changed between the dq1 head and SHA (scope 'added or removed")
        restore()
        rc_back = dry("DRY RUN: every check passes")
        missed = [k for k, v in sneg.items() if v != (2, True)]
        case("S1 (finding 1, MAJOR) write REFUSES a run-loaded change since the dq1 head whose ast scope is not exactly "
             "its ALLOWED one: agents.py CODE CHANGED (E1), the cfv flip + a third value, agents.py UNPARSABLE, a "
             "docstring-only edit of a third file, a file added (negative); the allowed pair passes (positive)",
             not missed and rc_back == (0, True), (missed, sneg, rc_back))
        anc = {}
        for rc_m in (1, 128):
            st["ancestor_rc"] = rc_m
            anc[rc_m] = dry("does not descend from the dq1 head")
        st["ancestor_rc"] = 0
        case("W5 (finding 5) write REFUSES a SHA that does not descend from the dq1 head (merge-base rc 1) or whose "
             "ancestry check fails (rc 128) (negative); a descendant passes (S1's positive)",
             anc == {1: (2, True), 128: (2, True)}, anc)
        st["chain_tracked"] = [c for c in CHAIN if c != "outputs/_bp_inst.py"]
        ch = dry("NOT TRACKED")
        ch_name = any("outputs/_bp_inst.py" in x for x in quiet if "NOT TRACKED" in x)
        st["chain_tracked"] = list(CHAIN)
        case("W6 (finding 6) write REFUSES when a probe-chain file is not tracked (git ls-files --error-unmatch) and "
             "names it (negative); the fully tracked chain passes (S1's positive)", ch == (2, True) and ch_name, ch)
        blobs[(head, REPLAY_REL)] = b"# another replay rule\n"
        rp_diff = dry("the identity rule must be committed")
        del blobs[(head, REPLAY_REL)]
        rp_gone = dry("git show %s:%s failed" % (head[:8], REPLAY_REL))
        restore()
        case("T0 (finding 2) write REFUSES when outputs/_dq_replay.py is not its blob at SHA, or that blob is missing "
             "(negative)", rp_diff == (2, True) and rp_gone == (2, True), (rp_diff, rp_gone))
        st["files"].append("outputs/%s/x.py" % QUARANTINE_NAME)
        qg = dry("quarantine path")
        rl_q, rl_qp = run_loaded_list(env)
        st["files"].pop()
        rl_ok, rl_okp = run_loaded_list(env)
        case("G2 (finding 11) the quarantine guard: git ls-files listing a quarantine path fails run_loaded_list and "
             "REFUSES write (negative); without it the list is clean (positive)",
             qg == (2, True) and rl_q is None and rl_qp and rl_ok and not rl_okp, (qg, rl_qp))
        gf = {}
        for key in ("rev-parse", "status", "ls-files", "ls-files-chain", "diff", "merge-base", "show"):
            st["fail"] = {key}
            gf[key] = dry("scripted failure")[0]
        st["fail"] = set()
        case("G3 (finding 11) every git command write needs, failing (rev-parse, status, ls-files, ls-files "
             "--error-unmatch, diff, merge-base, show), REFUSES write (negative)", set(gf.values()) == {2}, gf)
        wneg = {}
        with open(env.pool_log, "w") as fh:
            fh.write("old")
        wneg["a stale pool log"] = dry("_mf2_pool_dq_flipid.log exists")
        os.remove(env.pool_log)
        so4 = stdout_path(refs[4]["out"])
        os.replace(so4, so4 + ".aside")
        wneg["a missing dq1 stdout"] = dry("its stdout file is missing")
        os.replace(so4 + ".aside", so4)
        tc_saved = env.tag_check

        def tc_raise(_lines):
            raise SystemExit("tag check aborted")
        env.tag_check = tc_raise
        wneg["a tag check that raises"] = dry("TAG CHECK FAILED")
        env.tag_check = tc_saved
        blobs[(env.dq1_head, "wildfire_model.py")] = b"Y = 9\n"
        wneg["a dq1 src_sha that is no checkout form of the dq1-head blob"] = dry(
            "is neither the LF nor the CRLF form of the file at the dq1 head")
        restore()
        missed = [k for k, v in wneg.items() if v != (2, True)]
        case("W9 (finding 11) write REFUSES on a stale pool log, a missing dq1 stdout, a tag check that raises, a dq1 "
             "src_sha that is neither checkout form of the file at the dq1 head (negative)", not missed, (missed, wneg))
        quiet.clear()
        rc_w = write(env, head, say=quiet.append)
        w_out = list(quiet)
        fz = _load_json(env.freeze)
        with open(env.queue, "rb") as fh:
            qb = fh.read()
        case("W3 write freezes the queue (LF, 8 lines, == the derived lines) and the launch record (head, cfv 1 / 1, LF + "
             "raw sha256 of every run-loaded file incl. the chain, refs, flip-changed + ALLOWED scope, ancestry True, "
             "dq1-head forms of every hashed file, _dq_replay.py at SHA, tag rows) (positive)",
             rc_w == 0 and b"\r\n" not in qb and qb.decode() == queue_text(lines) and fz["head"] == head
             and fz["cfv"]["DISPATCH_JOINT"]["value"] == 1 and set(CHAIN) <= set(fz["run_loaded"])
             and "agents.py" in fz["run_loaded"] and fz["flip_changed"] == ["agents.py", "common_fixed_variables.py"]
             and all(fz["scope"][r] == ALLOWED_SCOPE[r] for r in fz["flip_changed"]) and len(fz["refs"]) == 8
             and fz["descends_from_dq1_head"] is True and fz["replay_at_head_lf"] == fz["tooling"][REPLAY_REL]["lf"]
             and set(fz["dq1_forms"]) >= {"agents.py", "wildfire_model.py", "src_extension/execution/uav_executor.py"}
             and all(fz["dq1_forms"].values()) and fz["queue"]["lf_sha256"] == _sha(qb), (rc_w, w_out[-4:]))
        case("W7 (finding 8) a real write prints the warning that no commit may land between write and the end of the "
             "runs (every record's head must equal SHA)",
             LAUNCH_WARNING in w_out and "NO COMMIT MAY LAND BETWEEN THIS WRITE AND THE END OF THE 8 RUNS" in
             LAUNCH_WARNING, w_out[-4:])
        case("W8 (finding 9) the printed launch command keeps bytecode off for the pool and its 8 runs: "
             "'PYTHONDONTWRITEBYTECODE=1 <py> -B <pool> <queue> <log> --maxpar 8 --min-free-gb 3' and the PowerShell "
             "form",
             any(x.startswith("launch (bash): PYTHONDONTWRITEBYTECODE=1 ") and " -B " in x and "_mf2_pool.py" in x
                 and x.endswith("--maxpar 8 --min-free-gb 3") for x in w_out)
             and any(x.startswith("launch (PowerShell): $env:PYTHONDONTWRITEBYTECODE = '1'; & ") and " -B " in x
                     for x in w_out), w_out[-4:])
        rc_again = write(env, head, say=quiet.append)
        with open(env.queue, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("{}\n")
        rc_differ = write(env, head, say=quiet.append)
        with open(env.queue, "wb") as fh:
            fh.write(qb)
        os.replace(env.freeze, env.freeze + ".aside")
        rc_partial = write(env, head, say=quiet.append)
        os.replace(env.freeze + ".aside", env.freeze)
        case("W4 a re-write on the identical frozen queue + freeze is 'unchanged' (exit 0, positive); a differing queue "
             "and a partial freeze are REFUSED (exit 2, negative)", (rc_again, rc_differ, rc_partial) == (0, 2, 2),
             (rc_again, rc_differ, rc_partial))
        # ---------------------------------------------------------------- records
        recs = {}
        for ln_, w_ in zip(lines, refs):
            ref = _load_json(w_["out"])
            recs[ln_["name"]] = _st_flip_record(env, ln_, ref, fz)
            _st_dump(ln_, recs[ln_["name"]], stdout=_read_text(stdout_path(w_["out"])))
        ln, w = lines[0], refs[0]
        ref = _load_json(w["out"])
        rec = recs[ln["name"]]
        sidecar = _read_text(ln["out"] + ".argv")
        case("V1 (a) validity of a correct flip record: none (positive); the dq1 reference is valid",
             not validity(env, ln, rec, sidecar, fz) and not ref_validity(env, w, ref, _read_text(w["out"] + ".argv")),
             validity(env, ln, rec, sidecar, fz))

        def mut(fn):
            r = copy.deepcopy(rec)
            fn(r)
            return validity(env, ln, r, sidecar, fz)
        vneg = {
            "crashed": mut(lambda r: r.__setitem__("crashed", "boom")),
            "steps 359": mut(lambda r: r.__setitem__("steps_done", 359)),
            "incomplete": mut(lambda r: r.__setitem__("complete", False)),
            "crn draws 0": mut(lambda r: r["fb3"]["crn"].__setitem__("crn_draws", 0)),
            "crn off": mut(lambda r: r["fb3"]["crn"].__setitem__("on", False)),
            "head": mut(lambda r: r.__setitem__("head", "e" * 40)),
            "repo": mut(lambda r: r.__setitem__("repo", "E:/elsewhere")),
            "tag": mut(lambda r: r.__setitem__("tag", "dq1r7_A_E")),
            "argv": mut(lambda r: r["argv"].append("--set")),
            "DISPATCH in extra_params": mut(lambda r: r["extra_params"].__setitem__("DISPATCH_JOINT", 1)),
            "DISPATCH in params": mut(lambda r: r["params"].__setitem__("DISPATCH_REASSIGN", 1)),
            "joint_on False": mut(lambda r: r["dq"]["switches"].__setitem__("joint_on", False)),
            "reassign_on False": mut(lambda r: r["dq"]["switches"].__setitem__("reassign_on", False)),
            "dp joint_on False": mut(lambda r: r["dp"]["switches"].__setitem__("joint_on", False)),
            "raw '0'": mut(lambda r: r["dq"]["switches"]["raw"].__setitem__("DISPATCH_JOINT", "0")),
            "raw 'True'": mut(lambda r: r["dp"]["switches"].__setitem__("DISPATCH_REASSIGN", "True")),
            "probe_sha": mut(lambda r: r["dq"].__setitem__("probe_sha", "0" * 64)),
            "r1 shadow sha": mut(lambda r: r["dq"].__setitem__("r1_shadow_sha", "0" * 64)),
            "u1 shadow sha": mut(lambda r: r["mvg"].__setitem__("u1_shadow_sha", "0" * 64)),
            "top src_sha": mut(lambda r: r["src_sha"].__setitem__("agents.py", "0" * 16)),
            "dq src_sha": mut(lambda r: r["dq"]["src_sha"].__setitem__("wildfire_model.py", "0" * 64)),
            "unfrozen src file": mut(lambda r: r["ud"]["src_sha"].__setitem__("outside.py", "0" * 64)),
            "empty src_sha": mut(lambda r: r["mvg"].__setitem__("src_sha", {})),
        }
        vneg["sidecar"] = validity(env, ln, rec, sidecar.replace("dqF", "dq1"), fz)
        vneg["no record"] = validity(env, ln, None, sidecar, fz)
        bad_line = copy.deepcopy(ln)
        bad_line["argv"].insert(5, "DISPATCH_JOINT=1")
        vneg["DISPATCH token on the line"] = validity(env, bad_line, rec, sidecar, fz)
        missed = [k for k, v in vneg.items() if not v]
        case("V2 (a) REFUSES 26 invalid flip records (crash, steps, incomplete, CRN x2, head, repo, tag, argv, DISPATCH "
             "key in extra_params / params, joint_on / reassign_on x3, raw '0' / 'True', probe / r1 / u1 sha, top / "
             "section / unfrozen / empty src_sha, sidecar, no record, a DISPATCH token on the line) (negative)",
             not missed, missed)
        rneg = {}
        for label, fn in (("head", lambda r: r.__setitem__("head", "e" * 40)),
                          ("extra 0", lambda r: r["extra_params"].__setitem__("DISPATCH_JOINT", 0)),
                          ("joint off", lambda r: r["dq"]["switches"].__setitem__("joint_on", False)),
                          ("steps", lambda r: r.__setitem__("steps_done", 300)),
                          ("crn", lambda r: r["fb3"]["crn"].__setitem__("crn_draws", 0))):
            r = copy.deepcopy(ref)
            fn(r)
            rneg[label] = ref_validity(env, w, r, _read_text(w["out"] + ".argv"))
        rneg["sidecar"] = ref_validity(env, w, ref, "x")
        missed = [k for k, v in rneg.items() if not v]
        case("V3 the dq1 reference check REFUSES 6 invalid references (head, extra_params 0, joint off, steps, CRN, "
             "sidecar) (negative)", not missed, missed)
        # ---------------------------------------------------------------- identity
        ctx = {"head": fz["head"], "dq1_head": env.dq1_head, "changed": set(fz["flip_changed"]),
               "hashes": fz["run_loaded"], "scope": fz["scope"], "dq1_forms": fz["dq1_forms"], "w2": w, "line": ln}
        so = _read_text(stdout_path(w["out"]))
        b = identity(ref, rec, so, so, ctx)
        n_cls = {c: len(b["classes"][c]) for c in CLASSES}
        case("I1 (b) a correct flip record REPRODUCES (r0 []) with no OTHER path; the allowed classes all occur: T "
             "(wall_s, timing, j_calls[i][2], mv / guard ms), N, A, K = 4, H = 1, S (agents.py / cfv in 5 blocks) "
             "(positive)", not b["r0"] and not b["other"] and n_cls["K"] == 4 and n_cls["H"] == 1 and n_cls["N"] == 1
             and n_cls["A"] > 0 and n_cls["T"] >= 10 and n_cls["S"] == 10, (b["r0"], b["other"][:5], n_cls))

        def ident(fn, so_rec=so, ctx_=ctx):
            r = copy.deepcopy(rec)
            fn(r)
            return identity(ref, r, so, so_rec, ctx_)
        ineg = {
            "rows_ff": ident(lambda r: r["rows_ff"].__setitem__(1, [["ff_unit_0", 9, 9, "busy"]])),
            "dp.commands": ident(lambda r: r["dp"]["commands"].append([13, "release"])),
            "dp.j_events": ident(lambda r: r["dp"]["j_events"].clear()),
            "mv_events": ident(lambda r: r["mv_events"][0].__setitem__("ran", False)),
            "eval": ident(lambda r: r["eval"].__setitem__("rescued", 99)),
            "stdout": ident(lambda r: None, so_rec=so + "x"),
        }
        missed = [k for k, v in ineg.items() if not v["r0"]]
        case("I2 (b) r0_reproduces flags 6 decision differences (a row, commands, J events, movement events, eval, "
             "stdout) (negative)", not missed, missed)
        oneg = {
            "crn draws": ident(lambda r: r["fb3"]["crn"].__setitem__("crn_draws", 1)),
            "dq.sample": ident(lambda r: r["dq"]["sample"]["rows"].append([2])),
            "params DISPATCH_JOINT = 0": ident(lambda r: r["params"].__setitem__("DISPATCH_JOINT", 0)),
            "raw switch string": ident(lambda r: r["dq"]["switches"]["raw"].__setitem__("DISPATCH_JOINT", "True")),
            "dp switch string": ident(lambda r: r["dp"]["switches"].__setitem__("DISPATCH_REASSIGN", "True")),
            "S/M/P": ident(lambda r: r["dq"]["switches"].__setitem__("S", 11)),
            "src of an unedited file": ident(lambda r: r["dq"]["src_sha"].__setitem__("wildfire_model.py", "0" * 64)),
            "src not the frozen raw": ident(lambda r: r["dp"]["src_sha"].__setitem__("agents.py", "0" * 64)),
            "head not the SHA": ident(lambda r: r.__setitem__("head", "e" * 40)),
            "timing length": ident(lambda r: r["mvg"]["timing"]["guard_ms"].append(0.1)),
            "timing None": ident(lambda r: r["dq"]["timing"].__setitem__("jpoint_ms", None)),
            "a timing key only in one": ident(lambda r: r["dq"]["timing"].__setitem__("new_ms", 1.0)),
            "tag not the line": ident(lambda r: r.__setitem__("tag", "dqFr7_A_Z")),
            "repo": ident(lambda r: r.__setitem__("repo", "E:/x")),
            "python": ident(lambda r: r.__setitem__("python", "3.11.0")),
            "warnings": ident(lambda r: r["warnings"].append("agents.py:12: W")),
            "an extra src file": ident(lambda r: r["dq"]["src_sha"].__setitem__("new.py", "0" * 64)),
        }
        ref_u = copy.deepcopy(ref)
        ref_u["dq"]["src_sha"]["wildfire_model.py"] = "9" * 64       # dq1 read another wildfire_model.py
        oneg["an unedited file whose bytes changed"] = identity(ref_u, rec, so, so, ctx)
        missed = [k for k, v in oneg.items() if not v["other"]]
        why_u = [o[1] for o in oneg["an unedited file whose bytes changed"]["other"]]
        case("I3 (b) the full-record diff flags 18 non-volatile differences as OTHER (CRN draws, the J sample, params "
             "DISPATCH 0, the raw / dp switch strings, S/M/P, a src hash that is not the frozen raw (x2), a head that is "
             "not SHA, a timing length / None / extra key, a tag that is not the line's, repo, python, warnings, an extra "
             "src file, a file the flip did not edit whose bytes changed) (negative)",
             not missed and why_u == ["dq1's wildfire_model.py hash is neither the LF nor the CRLF form of its blob at "
                                      "the dq1 head"], (missed, why_u))
        # finding 4: the line-endings-only S path, BOTH directions, on wildfire_model.py (not changed since the dq1 head)
        wm_lf = b"Y = 2\n"
        sha_lf, sha_crlf = _sha(wm_lf), _sha(wm_lf.replace(b"\n", b"\r\n"))

        def eol(ref_val, flip_val, frozen_raw, forms_wm=None):
            r_, x_ = copy.deepcopy(rec), copy.deepcopy(ref)
            x_["dq"]["src_sha"]["wildfire_model.py"] = ref_val
            r_["dq"]["src_sha"]["wildfire_model.py"] = flip_val
            hz = copy.deepcopy(fz["run_loaded"])
            hz["wildfire_model.py"]["raw"] = frozen_raw
            fm = dict(fz["dq1_forms"])
            if forms_wm is not None:
                fm["wildfire_model.py"] = forms_wm
            b_ = identity(x_, r_, so, so, dict(ctx, hashes=hz, dq1_forms=fm))
            if any(".dq.src_sha.wildfire_model.py" == p_ for p_ in b_["classes"]["S"]):
                return "S"
            return [o[1] for o in b_["other"] if o[0] == ".dq.src_sha.wildfire_model.py"]
        e_lf2crlf = eol(sha_lf, sha_crlf, sha_crlf)          # dq1 hashed LF bytes, the checkout is CRLF now
        e_crlf2lf = eol(sha_crlf, sha_lf, sha_lf)            # dq1 hashed CRLF bytes, the checkout is LF now (E10)
        e_random = eol("9" * 64, sha_lf, sha_lf)             # dq1 hashed bytes that are no form of the blob
        e_notraw = eol(sha_crlf, "c" * 64, sha_lf)           # the flip value is not the frozen raw sha256
        e_content = eol(_sha(b"Y = 9\r\n"), sha_lf, sha_lf, blob_forms(b"Y = 9\n"))   # the dq1-head content differs
        case("I4 (finding 4) S, line endings only, BOTH directions: dq1 LF -> CRLF now and dq1 CRLF -> LF now (E10) are "
             "S (positive); dq1 bytes that are no form of the dq1-head blob, a flip value that is not the frozen raw, "
             "and a dq1-head content that differs from the frozen content are OTHER (negative)",
             e_lf2crlf == "S" and e_crlf2lf == "S" and e_random != "S" and e_notraw != "S" and e_content != "S"
             and e_content == ["wildfire_model.py's content changed but it is not in the changed list"],
             (e_lf2crlf, e_crlf2lf, e_random, e_notraw, e_content))
        # finding 1 at analyze: S for a changed file only with its FROZEN scope verdict exactly the allowed one
        sv = {}
        for label, scope_ in (("CODE CHANGED", "CODE CHANGED (1 of 1 / 1 top-level statements differ)"),
                              ("added or removed", "added or removed (no blob at the dq1 head)"),
                              ("UNPARSABLE", "UNPARSABLE (invalid syntax)"),
                              ("the cfv verdict on agents.py", ALLOWED_SCOPE["common_fixed_variables.py"]),
                              ("no verdict", None)):
            sc = dict(fz["scope"])
            if scope_ is None:
                sc.pop("agents.py")
            else:
                sc["agents.py"] = scope_
            b_ = identity(ref, rec, so, so, dict(ctx, scope=sc))
            sv[label] = (len([p_ for p_ in b_["classes"]["S"] if "agents.py" in p_]),
                         len([o for o in b_["other"] if "agents.py" in o[0]]))
        r_wm = copy.deepcopy(rec)
        r_wm["dq"]["src_sha"]["wildfire_model.py"] = "d" * 64
        hz = copy.deepcopy(fz["run_loaded"])
        hz["wildfire_model.py"]["raw"] = "d" * 64
        b_third = identity(ref, r_wm, so, so, dict(ctx, hashes=hz, changed=ctx["changed"] | {"wildfire_model.py"},
                                                    scope=dict(fz["scope"], **{"wildfire_model.py": ALLOWED_SCOPE[
                                                        "agents.py"]})))
        third_other = [o[1] for o in b_third["other"] if o[0] == ".dq.src_sha.wildfire_model.py"]
        case("S2 (finding 1, MAJOR) at analyze an S path of a changed file is OTHER unless its FROZEN scope verdict is "
             "exactly ALLOWED_SCOPE[file]: agents.py with CODE CHANGED / added or removed / UNPARSABLE / the cfv verdict "
             "/ no verdict, and a third file with an allowed-looking verdict, are OTHER (negative); the allowed verdicts "
             "are S (I1, positive)",
             all(v == (0, 5) for v in sv.values()) and n_cls["S"] == 10 and len(third_other) == 1
             and "S only for exactly None" in third_other[0], (sv, third_other))
        # finding 7: the docstring's T class matches the code (no kick ms column is allowed)
        r_k, x_k = copy.deepcopy(rec), copy.deepcopy(ref)
        x_k["ud"]["kicks"] = [[80, "ff_unit_1", 0.5, 0.25, 0.75]]
        r_k["ud"]["kicks"] = [[80, "ff_unit_1", 0.6, 0.35, 0.95]]
        b_k = identity(x_k, r_k, so, so, ctx)
        kick_other = [o[0] for o in b_k["other"] if o[0].startswith(".ud.kicks")]
        doc = __doc__ or ""
        case("D1 (finding 7) the T class as documented is the T class the code applies: a .ud.kicks ms difference is "
             "OTHER (kick_cols None), the docstring says the kick ms columns are NOT in T and no longer lists them as "
             "allowed, and names the j_timing step / gc columns",
             len(kick_other) == 3 and not any(p_.startswith(".ud.kicks") for p_ in b_k["classes"]["T"])
             and "The .ud.kicks ms columns are NOT in T" in doc
             and ".ud.kicks[i][ms | inst_ms | ms_model] (none while J is on)" not in doc
             and "gc-collection count" in doc, (kick_other, b_k["classes"]["T"][:3]))
        # ---------------------------------------------------------------- analyze end to end
        quiet.clear()
        rc_a = analyze(env, say=quiet.append)
        res = _read_text(env.result) or ""
        case("A1 analyze on 8 correct flip records: every cell PASS, controls 16 / 16 detected, verdict 'FLIP IDENTITY "
             "=> PASS 8/8' as the result file's last line (positive)",
             rc_a == 0 and res.rstrip().splitlines()[-1] == "FLIP IDENTITY => PASS 8/8"
             and "controls detected 16 / 16 => PASS" in res, quiet[-6:])
        bad_rec = copy.deepcopy(recs[lines[3]["name"]])
        bad_rec["rows_vic"][2] = [["victim_0", 9, 9]]
        _st_dump(lines[3], bad_rec, stdout=_read_text(stdout_path(refs[3]["out"])))
        rc_b = analyze(env, say=quiet.append)
        res_b = (_read_text(env.result) or "").rstrip().splitlines()[-1]
        _st_dump(lines[3], recs[lines[3]["name"]], stdout=_read_text(stdout_path(refs[3]["out"])))
        os.replace(lines[5]["out"], lines[5]["out"] + ".aside")
        rc_m = analyze(env, say=quiet.append)
        res_m = (_read_text(env.result) or "").rstrip().splitlines()[-1]
        os.replace(lines[5]["out"] + ".aside", lines[5]["out"])
        case("A2 one decision difference -> 'FLIP IDENTITY => FAIL 7/8' (exit 1); a missing record -> FAIL 7/8 and its "
             "controls unavailable (negative)",
             rc_b == 1 and res_b.startswith("FLIP IDENTITY => FAIL 7/8") and rc_m == 1 and
             res_m.startswith("FLIP IDENTITY => FAIL 7/8 (1 cell(s) fail; positive controls 14 / 16"), (res_b, res_m))
        # a blind control: the next cell's dq1 record replaced by a copy equal to the flip record of this cell
        nxt = refs[1]
        save = {p_: open(p_, "rb").read() for p_ in (nxt["out"], stdout_path(nxt["out"]), nxt["out"] + ".argv")}
        _st_dump(nxt, recs[lines[0]["name"]], stdout=_read_text(stdout_path(lines[0]["out"])))
        rc_c = analyze(env, say=quiet.append)
        res_c = (_read_text(env.result) or "").rstrip().splitlines()[-1]
        for p_, b_ in save.items():
            with open(p_, "wb") as fh:
                fh.write(b_)
        case("A3 a control that is not detected fails the verdict (negative): the result names the controls",
             rc_c == 1 and "positive controls 15 / 16" in res_c, res_c)
        # (c) re-hash
        quiet.clear()
        rc_ok = analyze(env, say=quiet.append)
        wm = env.abs("wildfire_model.py")
        with open(wm, "rb") as fh:
            wm_b = fh.read()
        with open(wm, "wb") as fh:
            fh.write(wm_b.replace(b"\n", b"\r\n"))
        rc_eol = analyze(env, say=quiet.append)
        res_eol = _read_text(env.result) or ""
        with open(wm, "wb") as fh:
            fh.write(wm_b + b"Y = 3\n")
        rc_content = analyze(env, say=quiet.append)
        with open(wm, "wb") as fh:
            fh.write(wm_b)
        os.remove(env.abs("outputs/_bp_inst.py"))
        rc_gone = analyze(env, say=quiet.append)
        with open(env.abs("outputs/_bp_inst.py"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# outputs/_bp_inst.py\n")
        st["files"].append("src_extension/new_module.py")
        with open(env.abs("src_extension/new_module.py"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("N = 1\n")
        rc_new = analyze(env, say=quiet.append)
        st["files"].remove("src_extension/new_module.py")
        ref_b = None
        with open(refs[6]["out"], "rb") as fh:
            ref_b = fh.read()
        with open(refs[6]["out"], "wb") as fh:
            fh.write(ref_b + b" ")
        rc_ref = analyze(env, say=quiet.append)
        res_ref = (_read_text(env.result) or "").rstrip().splitlines()[-1]
        with open(refs[6]["out"], "wb") as fh:
            fh.write(ref_b)
        case("R1 (c) the re-hash: unchanged passes (positive); an EOL-only change, a content change, a missing chain "
             "file and a new run-loaded file each FAIL every cell (negative)",
             rc_ok == 0 and rc_eol == 1 and "line endings only" in res_eol and rc_content == 1 and rc_gone == 1
             and rc_new == 1, (rc_ok, rc_eol, rc_content, rc_gone, rc_new))
        case("R2 (c) a dq1 reference record changed since write fails its cell (negative)",
             rc_ref == 1 and res_ref.startswith("FLIP IDENTITY => FAIL 7/8"), res_ref)

        # finding 2: the identity rule and this tool are pinned between write and analyze
        def drifted(rel, extra=b"# drift\n"):
            path = env.abs(rel)
            with open(path, "rb") as fh:
                saved = fh.read()
            with open(path, "wb") as fh:
                fh.write(saved + extra)
            quiet.clear()
            try:
                return analyze(env, say=quiet.append), list(quiet)
            finally:
                with open(path, "wb") as fh:
                    fh.write(saved)
        rc_qd, q_qd = drifted("outputs/_dq_queue.py")
        rc_rd, q_rd = drifted(REPLAY_REL)
        rc_sd, q_sd = drifted(SELF_REL)
        blobs[(head, REPLAY_REL)] = b"# the rule at SHA differs\n"
        quiet.clear()
        rc_bd = analyze(env, say=quiet.append)
        q_bd = list(quiet)
        restore()
        st["fail"] = {"show"}
        quiet.clear()
        rc_gs = analyze(env, say=quiet.append)
        st["fail"] = set()

        def stopped(q, sub):
            return any(x.startswith("STOP: the identity rule or this tool changed") and sub in x for x in q)
        case("T1 (finding 2) analyze STOPS (exit 2, nothing read) when outputs/_dq_replay.py changed since write, when "
             "this tool changed since write, when _dq_replay.py is not its blob at SHA, or when that blob cannot be read "
             "(negative); a _dq_queue.py change is only a NOTE and the pinned hashes are printed (exit 0, positive)",
             rc_qd == 0 and any("TOOLING DRIFT: outputs/_dq_queue.py" in x for x in q_qd)
             and any(x.startswith("tooling (pinned): %s LF sha256 now " % SELF_REL) for x in q_qd)
             and rc_rd == 2 and stopped(q_rd, REPLAY_REL + " changed since write")
             and rc_sd == 2 and stopped(q_sd, SELF_REL + " changed since write")
             and rc_bd == 2 and stopped(q_bd, "is not its blob at SHA") and rc_gs == 2,
             (rc_qd, rc_rd, rc_sd, rc_bd, rc_gs, q_rd[:1]))
        # finding 3: a control counts only when the behaviour rule (r0_reproduces) sees it
        R_ = replay_module()
        r0_saved = R_.r0_reproduces
        R_.r0_reproduces = lambda *a, **k: []
        try:
            quiet.clear()
            rc_blind = analyze(env, say=quiet.append)
        finally:
            R_.r0_reproduces = r0_saved
        res_blind = _read_text(env.result) or ""
        case("P1 (finding 3) a positive control is DETECTED only when r0_reproduces reports a difference: with the r0 "
             "rule blinded (returns []) the controls are 0 / 16 and the verdict FAILs though every cell passes the "
             "full-record diff (negative); with the real rule 16 / 16 (A1, positive)",
             rc_blind == 1 and "controls detected 0 / 16 => FAIL" in res_blind
             and res_blind.rstrip().splitlines()[-1] == "FLIP IDENTITY => FAIL 8/8 (positive controls 0 / 16 detected)"
             and "controls detected 16 / 16 => PASS" in res, res_blind.rstrip().splitlines()[-3:])
        # finding 1 end to end: a freeze whose agents.py scope is not the allowed verdict fails every cell
        with open(env.freeze, "rb") as fh:
            fz_bytes = fh.read()
        fz_bad = json.loads(fz_bytes.decode("utf-8"))
        fz_bad["scope"]["agents.py"] = "CODE CHANGED (1 of 1 / 1 top-level statements differ)"
        with open(env.freeze, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(fz_bad, fh)
        quiet.clear()
        rc_sc = analyze(env, say=quiet.append)
        res_sc = (_read_text(env.result) or "").rstrip().splitlines()[-1]
        with open(env.freeze, "wb") as fh:
            fh.write(fz_bytes)
        case("S3 (finding 1, MAJOR) analyze end to end: a freeze whose agents.py scope verdict is CODE CHANGED (E1's "
             "shape) gives 'FLIP IDENTITY => FAIL 0/8' (negative; the allowed freeze passes in A1, positive)",
             rc_sc == 1 and res_sc.startswith("FLIP IDENTITY => FAIL 0/8"), res_sc)
        with open(env.queue, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n")
        rc_q = analyze(env, say=quiet.append)
        case("R3 analyze STOPS (exit 2) on a queue file that differs from the re-derived lines (negative)", rc_q == 2,
             rc_q)
        # ---------------------------------------------------------------- the real tool's own constants
        R = replay_module()
        vol, oth = R.classify_diff([".wall_s", ".tag", ".argv (len 30 != 26)", ".dp.j_calls[3][2]", ".head",
                                    ".params.DISPATCH_JOINT (only in X)"], None, None, None)
        case("X1 the imported outputs/_dq_replay.py: classify_diff puts wall_s / tag / argv / j_calls ms in volatile and "
             "head / params in other (the split this tool refines); json_diff labels a dq1-only key '(only in X)'",
             len(vol) == 4 and len(oth) == 2 and R.json_diff({"params": {"DISPATCH_JOINT": 1}}, {"params": {}})
             == [".params.DISPATCH_JOINT (only in X)"], (vol, oth))
        case("X3 shape folds list indices but keeps a row path's column and a ' (...)' suffix",
             shape(".mv.rows[12][35]") == ".mv.rows[i][35]" and shape(".argv[3]") == ".argv[i]"
             and shape(".argv (len 30 != 26)") == ".argv (len 30 != 26)"
             and shape(".ud.timing.fix_calls.a[7]") == ".ud.timing.fix_calls.a[i]",
             [shape(x) for x in (".mv.rows[12][35]", ".argv[3]", ".argv (len 30 != 26)")])
        case("X2 the frozen constants: W2 LF sha256 = the screen analyzer's b1ccbc0d2eaf6eed..., the dq1 head = "
             "11d62410..., K_PATHS the 4 dq1-only keys, CHAIN the task's 11 probe-chain files",
             W2_LF_SHA256.startswith("b1ccbc0d2eaf6eed") and DQ1_HEAD.startswith("11d62410") and len(K_PATHS) == 4
             and len(CHAIN) == 11 and len(set(CHAIN)) == 11)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    out.append("")
    n = sum(1 for x in out if x[:4] in ("PASS", "FAIL"))
    out.append("DQ FLIPID SELF-TEST %s (%d cases: %d passed, %d failed)" % ("PASS" if not fails else "FAIL", n,
                                                                          n - len(fails), len(fails)))
    print("\n".join(out))
    return 1 if fails else 0


# ================================================================================================= main
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else ""
    if cmd == "selftest":
        tmp = argv[argv.index("--tmp") + 1] if "--tmp" in argv and argv.index("--tmp") + 1 < len(argv) else None
        return selftest(tmp)
    if cmd == "show":
        return show(Env())
    if cmd == "write":
        if "--head" not in argv or argv.index("--head") + 1 >= len(argv):
            print("usage: _dq_flipid.py write --head SHA [--dry-run]")
            return 2
        return write(Env(), argv[argv.index("--head") + 1], dry_run="--dry-run" in argv)
    if cmd == "analyze":
        return analyze(Env())
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
