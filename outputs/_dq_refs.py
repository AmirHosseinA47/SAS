"""Dispatch round 2, THE FLIP: the measurement round's references RE-MEASURED at the flip commit.

WHY (pre-registered):
  - outputs/dispatch2_part1.txt 10.8, THE FLIP (only after a PASS and the maintainer's yes): "the measurement round's
    references re-measured (19.14)".
  - outputs/fix3b_part1.txt 19.14 (c), APPLIED BY ANALOGY: 19.14 (a) says "19.4 IS CLOSED" (the dispatch family had
    ended), and 19.14 (b) names only the three FF switches. 19.14 (c) applied 19.4's consequence ("If dispatch changes
    behaviour, the screen references are re-measured at that commit before the first measurement run") to the MVG
    flip; this tool applies the same consequence to the dispatch round 2 flip (DISPATCH_JOINT = 1,
    DISPATCH_REASSIGN = 1), which changes firefighter dispatch. 19.4 is quoted for its wording only, not as an open
    rule. OUTSIDE THIS TOOL: no amendment names DISPATCH_JOINT / DISPATCH_REASSIGN as shipped settings of the
    measurement round yet; the record needs a 19.15-style amendment (as U-13 required for the MVG flip).
  - outputs/bayesprep_part1.txt 4.4: "the screen's references are re-measured at that commit ... (the 'baseline moved'
    rule)". The flip changes dispatch behaviour, so the rule applies.
THE REFERENCE SET: the Bayesian preparation screen's reference arm bpc = CUR (SEARCHER_TARGETING 0) at the SHIPPED
  defaults, on that screen's 33 cells (outputs/bayesprep_part1.txt 7.1): ring set 1 (VICTIM_SPAWN_MODE 0, seeds
  9601-9616), uniform set 1 (mode 1, 9601-9616) and the single cell uniform set 2 D_W (seed 9636). Its FROZEN lines are
  bpcr_* (16), bpcu_* (16) and bpcu2_D_W in outputs/_bp_q_arms.jsonl (identical lines in outputs/_bp_q_all.jsonl);
  the D_W line exists there, so nothing is derived.

usage (from the dispatch worktree; E:/Projects/SAS/.venv/Scripts/python.exe -B, PYTHONDONTWRITEBYTECODE=1):
  python outputs/_dq_refs.py selftest [--scratch DIR]
        in-process self-test on synthetic records / fake inputs, positive and negative controls for every check; no
        simulator step (a throwaway git index - init + add, never a commit - in a temp dir exercises the freeze)
  python outputs/_dq_refs.py check [--head SHA]
        a DRY RUN of write: the lines, the tree / freeze preconditions and the tag check; writes nothing. Without
        --head the dry run FAILS (write needs --head; HEAD is otherwise unverified). On a FROZEN queue it re-verifies
        the launch state instead: the queue and its launch record, HEAD == the frozen head (== --head when given), and
        the tree re-frozen and compared with the launch record (FREEZE below: hashes, mtimes, blobs, the runtime cfv
        values) - run it right before launching the pool.
  python outputs/_dq_refs.py write --head SHA
        SHA = the flip commit (must resolve to this worktree's HEAD). Freezes the queue outputs/_dq_q_refs.jsonl
        (33 lines, LF, for outputs/_mf2_pool.py) and the launch freeze record outputs/_dq_refs/_freeze_launch.json.
        A queue that exists must be identical (LF-normalised), frozen at the same head, HEAD must still be that head
        and the tree must still be the launch tree (the frozen re-verification of check), else STOP; refuses on a tag
        collision (outputs/_dq_queue.py tag_check, imported: every worktree's outputs/ and outputs/_ffr_logs top level,
        this worktree's index and the paths added anywhere in git history, quarantine excluded, positive controls),
        on any of its own paths in use, on a tree that is not the clean flip commit, on shipped defaults that are not
        the flip's
  python outputs/_dq_refs.py analyze [--head SHA] [--partial]
        VALIDITY only; prints "REFERENCES ... => VALID / INVALID / INCOMPLETE" and writes outputs/_dq_refs_result.txt
        and outputs/_dq_refs/_freeze_complete.json. Only a VALID verdict heads the record list "THE MEASUREMENT
        ROUND'S REFERENCE SET" (the 33 record paths and their LF sha256); any other verdict heads it "NOT A REFERENCE
        SET (verdict X)". INVALID beats INCOMPLETE: one failing present run or one global failure is INVALID (exit 1)
        whatever is missing; INCOMPLETE (--partial, exit 3) only when everything present is valid; without --partial a
        missing run with nothing failing is a STOP (exit 3). It never prints an outcome value (rescued, dead, deaths,
        detection times, MR1): the references are records for the measurement round, not read here.
  exit codes: 0 ok / VALID; 1 INVALID (analyze) or a failed dry run (check); 2 write refused, or a STOP in check
  (a refusal raised inside the imported outputs/_dq_queue.py included); 3 analyze STOP or INCOMPLETE.

THE RUN LINE (one per bpc line, in the frozen file's order): the bpc line VERBATIM except exactly four tokens -
  argv[0] = this worktree's outputs/_ut_probe.py (the bpc line's probe script; it must exist here), --repo = this
  worktree, --out = outputs/_dq_refs/_sd_<tag>.json, --tag = <tag>; cwd = this worktree. <tag> = dqrefc<r|u><1|2>_<S>_<W>
  (bpcr_X -> dqrefcr1_X, bpcu_X -> dqrefcu1_X, bpcu2_D_W -> dqrefcu2_D_W). Every bpc line is first checked equal to an
  independently written 7.1 line (probe flags --crn --hazard --instrument; --set GLOBAL_PLANNER_MODE=0,
  VICTIM_SPAWN_MODE=<0|1>; --steps 360; --set BATCH_SIZE=360; the seed by the rule base + 4*s + w (s A0 B1 C2 D3,
  w N0 S1 E2 W3; set 1 base 9601, set 2 base 9621) and by outputs/_dq_seeds.txt); any deviation STOPS.

WRITE PRECONDITIONS (the freeze; outputs/_mvg_ist.py's convention):
  - --head SHA resolves to a commit and equals HEAD;
  - no RUN-LOADED tracked file modified (git status --porcelain -uno; run-loaded = every tracked file outside outputs/
    except tests/ and *.md / *.txt / *.rst, plus the probe chain CHAIN_FILES); no untracked file under src_extension/;
    every chain file tracked and present;
  - every run-loaded file's content (LF-normalised) equals its blob at the commit (git ls-tree / cat-file): git status
    cannot see a file flagged assume-unchanged or skip-worktree, the blob comparison can;
  - no run-loaded file has an mtime later than the freeze time (FREEZE re-checks every mtime at analysis);
  - the shipped defaults parsed (ast, never imported) from common_fixed_variables.py: DISPATCH_JOINT 1,
    DISPATCH_REASSIGN 1, FF_APPROACH_PATH 1, FF_RETREAT_KEEP_APPROACH 1, FF_FIX_STRANDING_GUARD 1, SEARCHER_TARGETING 0
    (each an int literal bound once, unconditionally, at module level), and GLOBAL_PLANNER_MODE 0 (the line sets 0, so
    any other default would make the line an override). EVERY binding form counts as a binding (assignment, for /
    with / except targets, import [as], def / class, del, walrus, match captures, a `global` statement, an attribute
    target); a dynamic binding anywhere in the file (exec / eval / compile / setattr / delattr / globals / vars /
    locals / __import__, .__dict__, sys.modules, `from x import *`) is a problem: the parse cannot be trusted;
  - THE RUNTIME VALUES: a fresh interpreter imports common_fixed_variables.py from this worktree and every parsed
    literal (the expected keys included) must equal its runtime value, type for type (an import-time side effect the
    parse cannot see, e.g. a helper module mutating the module, is caught here);
  - the tag check (above) and no own path in use (the queue, outputs/_dq_refs/, the result file, the pool log - on disk,
    by name in every worktree's outputs/ top level, or tracked / added in history).
  The freeze record holds HEAD, the tracked status, the raw and LF-normalised sha256 and the mtime of every tracked file
  outside outputs/ and of the chain / tooling files, the freeze time, the blob comparison at the commit, every literal
  module-level constant of common_fixed_variables.py and the runtime comparison, the queue's sha256 and the source
  file's.

ANALYZE - per run (V), each failure listed by name:
  V-done   complete True, a "crashed" key present and None, steps_done == steps == 360 (bayesprep 7.1: 360 steps)
  V-prov   repo == this worktree, head == the frozen head (= SHA), tag == name, scenario / wind / seed == the line's,
           src_sha holds EXACTLY outputs/_sd_probe.py's 11 keys (SRC_SHA_FILES), each 16-hex prefix == the launch
           freeze's raw or LF sha
  V-pin    the pinned runtime: mesa == 1.2.1; the probe version strings the frozen chain writes (sd_probe v1,
           fx3_probe v3, mf2_probe v1, fb3_probe v1, fb3 mr v2, ut_probe v2); python == the venv's (reported by the
           accessor child), and one python version across the runs (a global check)
  V-mr1    the MR1 record shape (outputs/_mvg_ist.py): one mr1_steps row per step 1..360, one literal and one corrected
           count per UAV, mr1_ids one per UAV, n_observations present and > 0, the UAV count == params NUM_AGENTS; and
           fix3b_part1.txt 19.11 (b): mr.mr1_list == outputs/_ist3_analyze.py _mr1_acc of the CORRECTED counts (the
           LITERAL ones if MR1_TRUTHINESS_FIX ships 0), bit for bit. Value-free: no MR1 value is printed
  V-argv   the record's argv == the queue line's argv after "--"; extra_params == the line's --set list (parsed by
           outputs/_sd_probe.py _parse_value); the pool's .argv sidecar == {argv, cwd} of the line
  V-crn    fb3.crn on with crn_draws > 0 (bayesprep 7.1: CRN on; outputs/_fb3_probe.py: 0 draws is invalid)
  V-par    THE RECORDED PARAMETERS EQUAL THE SHIPPED DEFAULTS - no override of a shipped switch:
             params holds only the scenario preset's keys (evaluate_scenarios._scenario_params) and the line's --set
             keys; the line's --set values are recorded; a --set key that is not the placement / horizon
             (VICTIM_SPAWN_MODE, BATCH_SIZE: 7.1's design) equals the parsed shipped default (GLOBAL_PLANNER_MODE 0);
             the switches the run itself recorded equal the parsed shipped defaults: fb3.switches (every FIX3B key;
             VICTIM_SPAWN_MODE = the line's), fb3.eff searcher_targeting / victim_spawn_mode, fb3.bp_switches
             (SEARCHER_TARGETING_FIX, UAV_DOCKED_NOT_OBSTACLE raw + effective, every SEARCHER_FP_* raw), ut.switch
             (SEARCHER_UNTUNED, SEARCHER_END_RECALL, FF_RELEASE_DETECTED_ONLY raw + on), effective.global_planner_mode
  V-inst   instrument error lists PRESENT and empty: fb3.inst error_count the int 0, broken False, errors a list and
           []; mr.errors a list and []; ut.errors a list and []; fx3 / mf2 non-empty (their probe strings, V-pin);
           fb3.coverage a non-empty list with no "ERR" row; every effective.* accessor present and none "ERR ..." /
           "ABSENT"; no observer error marker (outputs/_ist3_analyze.py ERR_RE) ANYWHERE in the record except eval
           (eval is never scanned: it holds the outcomes)
  SW       (outputs/_mvg_ist.py's SW, extended to dispatch) the accessors the run read, rebuilt from its recorded params
           in a fresh interpreter at this worktree: dispatch_joint / dispatch_reassign / ff_approach_path /
           ff_retreat_keep_approach / ff_fix_stranding_guard True, and every other listed accessor as its parsed
           shipped default (victim_spawn_mode = the line's). No probe records the dispatch / movement switches, so this
           and the freeze are the evidence that the flipped defaults ran.
  FREEZE   the launch record must have been clean (and of this format: mtimes, blob comparison, runtime values);
           re-frozen at analysis: a run-loaded file whose LF sha changed FAILS; a run-loaded file whose mtime differs
           from the launch record, or is later than the launch freeze time, FAILS (an edit made after write and
           reverted before analyze leaves the hashes equal - src_sha covers 11 files only, not e.g.
           src_extension/planning/joint_dispatch.py - but not the mtime); a run-loaded file that differs from its
           blob at the frozen head FAILS; a runtime cfv value that differs from the parsed literal FAILS; a change of
           an ANALYSIS file (this tool, outputs/_ist3_analyze.py - ERR_RE, _mr1_acc, full_diff -, outputs/_dq_queue.py,
           the seed table and the two source queues; LF sha) FAILS and is named in the verdict line; any other
           change (tests/, docs, an eol-only change) is a NOTE; HEAD moving is a NOTE when no run-loaded file
           changed; the parsed shipped defaults must be unchanged and still free of shipped problems.
  INFO (never gating, no values): per cell whether the record differs from the old bpc record of the same cell in
           this worktree's outputs/ (outputs/_ist3_analyze.py full_diff: every recorded field except labels and
           wall-clock): equal / differs / absent - the word only. DISCLOSURE: it is expected to read "differs"
           everywhere and carries little information - the old bpc records predate the MR1 fix and the movement and
           dispatch flips (mr.mr1_list alone guarantees "differs"). Those old records sit on seeds 9601-9616 / 9636
           (dispatch seed sets 1 and 2); the tool reads them in full and prints one word per cell.

KNOWN LIMITATIONS: untracked files are looked for under src_extension/ only (listing the repository root is out of
  bounds); `selftest` fakes the tag check, the own-path check, the accessor child and HEAD (the real tag check runs in
  `check` / `write`, the real accessor child in `analyze`; the runtime cfv child runs for real on the selftest's
  synthetic file), and its throwaway index has no commit, so `git status` is emulated there by `git diff
  --name-status` with the same pathspecs and "the commit" is a `git write-tree` of that index; do not commit in this
  worktree while the pool runs (each run records HEAD at its start: a moved HEAD fails V-prov); do not touch (even
  re-save unchanged) a run-loaded file between write and analyze (the mtime check FAILS it). Launch the pool with
  PYTHONDONTWRITEBYTECODE=1 (outputs/_mf2_pool.py runs the probe without -B). SCOPE: only the bpc arm is re-measured;
  bayesprep 7.1's ROUTE_BLOCKED reference (the 4 rb shards against utR) and 7.2's identity references (ut2r / ut2u)
  are not - if "the screen's references" of 4.4 is plural, that is a ruling outside this tool.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import types

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
WT = r"E:\Projects\SAS_wt\dispatch"
BP_WT = r"E:\Projects\SAS_wt\bayesprep"
MAIN = r"E:\Projects\SAS"
PY = os.path.join(MAIN, ".venv", "Scripts", "python.exe")
QUARANTINE_NAME = "_firemech_rewound_20260914"
QUARANTINE_EXCLUDE = ":(exclude)outputs/" + QUARANTINE_NAME

TAG_PREFIX = "dqrefc"
SCENARIOS = "ABCD"
WINDS = (("N", "north"), ("S", "south"), ("E", "east"), ("W", "west"))
KEYS = tuple(sorted("%s_%s" % (s, w) for s in SCENARIOS for w, _n in WINDS))
BASES = {1: 9601, 2: 9621}
STEPS = 360
SOURCE_NAMES = tuple(["bpcr_" + k for k in KEYS] + ["bpcu_" + k for k in KEYS] + ["bpcu2_D_W"])
SRC_RE = re.compile(r"^bpc([ru])(2?)_([A-D])_([NSEW])$")
N_LINES = 33

# the flip (outputs/dispatch2_report.txt section 10) and the MVG flip (fix3b_part1.txt 19.14 (b)); SEARCHER_TARGETING 0
# = CUR (fix3b_part1.txt 19.2: "SEARCHER_TARGETING 0 at the SHIPPED defaults")
EXPECTED_SHIPPED = {"DISPATCH_JOINT": 1, "DISPATCH_REASSIGN": 1, "FF_APPROACH_PATH": 1, "FF_RETREAT_KEEP_APPROACH": 1,
                    "FF_FIX_STRANDING_GUARD": 1, "SEARCHER_TARGETING": 0}
# a --set the bpc line carries that is a switch: it must equal the shipped default (else the line overrides it)
LINE_SWITCH_DEFAULTS = {"GLOBAL_PLANNER_MODE": 0}
# the placement and the horizon the screen design sets (bayesprep_part1.txt 7.1) - not shipped switches
PLACEMENT_KEYS = frozenset({"VICTIM_SPAWN_MODE", "BATCH_SIZE"})
# evaluate_scenarios._scenario_params + serve_dashboard.scenario_extra_params (the preset's team / battery keys)
SCENARIO_KEYS = frozenset({"NUM_AGENTS", "NUM_VICTIMS", "NUM_FIREFIGHTERS", "WIND_DIRECTION", "BATCH_SIZE",
                           "FIRE_SPREAD_MULTIPLIER", "PROBABILITY_MAP", "NUM_FIRE_TRACKERS", "NUM_VICTIM_SEARCHERS",
                           "UAV_LAUNCH_BATTERY_FRACTION", "BATTERY_SCENARIO"})
SUMMARY_KEYS = ("DISPATCH_JOINT", "DISPATCH_REASSIGN", "DISPATCH_STALL_STEPS", "DISPATCH_MARGIN_STEPS",
                "DISPATCH_MARGIN_PERSIST", "FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_FIX_STRANDING_GUARD",
                "SEARCHER_TARGETING", "SEARCHER_TARGETING_FIX", "UAV_DOCKED_NOT_OBSTACLE", "MR1_TRUTHINESS_FIX",
                "NUMPY_SCALAR_FLAGS", "SEARCHER_UNTUNED", "SEARCHER_END_RECALL", "FF_RELEASE_DETECTED_ONLY",
                "GLOBAL_PLANNER_MODE", "VICTIM_SPAWN_MODE", "FF_EXIT_LEG_MODE", "BASE_STATION_MODE", "BATCH_SIZE")
# the probe chain the bpc line runs (outputs/_dq_queue.py RUN_LOADED_PATHS' chain for _ut_probe.py, _dim_hooks.py
# conservatively) + the pool: RUN-LOADED, a change FAILS
CHAIN_FILES = ("outputs/_ut_probe.py", "outputs/_fb3_probe.py", "outputs/_fx3_probe.py", "outputs/_mf2_probe.py",
               "outputs/_sd_probe.py", "outputs/_bp_inst.py", "outputs/_fm2_probe_harness.py", "outputs/_ffr_harness.py",
               "outputs/_dim_hooks.py", "outputs/_mf2_pool.py")
# this tool and what it reads (the ANALYSIS files): hashed at launch, a change (LF sha) by analysis FAILS and is
# named in the verdict line (outputs/_mvg_ist.py and outputs/_dq_ist.py put _ist3_analyze.py in their chain)
TOOLING_FILES = ("outputs/_dq_refs.py", "outputs/_ist3_analyze.py", "outputs/_dq_queue.py", "outputs/_dq_seeds.txt",
                 "outputs/_bp_q_arms.jsonl", "outputs/_bp_q_all.jsonl")
# outputs/_sd_probe.py's src_sha keys (os.path.join on Windows: backslashes in the record; compared with "/")
SRC_SHA_FILES = ("agents.py", "wildfire_model.py", "common_fixed_variables.py", "serve_dashboard.py",
                 "evaluate_scenarios.py", "src_extension/execution/uav_executor.py",
                 "src_extension/adaptation/local_adaptation_generator.py",
                 "src_extension/adaptation/global_adaptation_generator.py",
                 "src_extension/planning/utility_evaluation.py", "src_extension/planning/rescue_planner.py",
                 "src_extension/planning/fail_safe_planner.py")
# the pinned runtime (memory: mesa 1.2.1 in the parent .venv) and the version strings the frozen chain writes:
# (record section or None for the top level, the version, the chain file that writes it)
PINNED_MESA = "1.2.1"
PROBE_VERSIONS = ((None, "sd_probe v1", "_sd_probe.py"), ("fx3", "fx3_probe v3", "_fx3_probe.py"),
                  ("mf2", "mf2_probe v1", "_mf2_probe.py"), ("fb3", "fb3_probe v1", "_fb3_probe.py"),
                  ("mr", "fb3 mr v2", "_fb3_probe.py"), ("ut", "ut_probe v2", "_ut_probe.py"))
# outputs/_sd_probe.py's effective.* accessors
EFFECTIVE_KEYS = ("global_planner_mode", "base_station_mode", "ff_exit_leg_mode", "base_station_depots",
                  "base_station_return_mechanism")
# a run-loaded file may not carry an mtime later than the freeze time by more than this (clock granularity)
MTIME_TOL_NS = 2 * 10 ** 9
# the switch accessors rebuilt by SW; the cfv key each one reads (None: the line's VICTIM_SPAWN_MODE)
ACC_KEY = {"dispatch_joint": "DISPATCH_JOINT", "dispatch_reassign": "DISPATCH_REASSIGN",
           "ff_approach_path": "FF_APPROACH_PATH", "ff_retreat_keep_approach": "FF_RETREAT_KEEP_APPROACH",
           "ff_fix_stranding_guard": "FF_FIX_STRANDING_GUARD", "mr1_truthiness_fix": "MR1_TRUTHINESS_FIX",
           "numpy_scalar_flags": "NUMPY_SCALAR_FLAGS", "searcher_targeting": "SEARCHER_TARGETING",
           "searcher_targeting_fix": "SEARCHER_TARGETING_FIX", "uav_docked_not_obstacle": "UAV_DOCKED_NOT_OBSTACLE",
           "searcher_untuned": "SEARCHER_UNTUNED", "searcher_end_recall": "SEARCHER_END_RECALL",
           "ff_release_detected_only": "FF_RELEASE_DETECTED_ONLY", "global_planner_mode": "GLOBAL_PLANNER_MODE",
           "victim_spawn_mode": None}
INT_ACCESSORS = frozenset({"searcher_targeting", "global_planner_mode", "victim_spawn_mode"})
FLIP_ACCESSORS = ("dispatch_joint", "dispatch_reassign", "ff_approach_path", "ff_retreat_keep_approach",
                  "ff_fix_stranding_guard")
_MISSING = object()


class Stop(Exception):
    pass


def stop(msg: str):
    raise Stop(msg)


# ------------------------------------------------------------------------------------------------------------ helpers
def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _read(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _same_path(a, b) -> bool:
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def _same(a, b) -> bool:
    """Value AND type equal (True is not 1, 1.0 is not 1)."""
    return type(a) is type(b) and a == b


def _canon(v) -> str:
    """A type-strict canonical form of a JSON value (json keeps true / 1 / 1.0 apart)."""
    return json.dumps(v, sort_keys=True)


def _git_oid(data: bytes) -> str:
    """git's blob id (sha1 object format) of these bytes."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _z(text: str) -> list:
    return sorted({p.strip("\r\n") for p in text.split("\0") if p.strip("\r\n")})


def _status_path(line: str) -> str:
    p = line[3:].strip()
    if " -> " in p:
        p = p.split(" -> ", 1)[1]
    return p.strip('"')


_MODS: dict = {}


def _mod(file: str):
    """A helper module of this outputs/ directory, loaded by path (stdlib-only top levels: no simulator import)."""
    if file not in _MODS:
        spec = importlib.util.spec_from_file_location("_dqrefs_" + file.replace(".py", "").strip("_"),
                                                      os.path.join(HERE, file))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODS[file] = mod
    return _MODS[file]


def run_loaded(p: str) -> bool:
    if p in CHAIN_FILES:
        return True
    return not (p.startswith("outputs/") or p.startswith("tests/") or p.lower().endswith((".md", ".txt", ".rst")))


# ---------------------------------------------------------------------------------------------------------------- env
class Env:
    """Every path and every external effect of the tool (selftest swaps them for scratch dirs and fakes)."""

    def __init__(self, wt: str = WT, git_cfg=None):
        # absolute: the children get it as their repo and run with it as cwd (a relative path would resolve twice)
        self.wt = os.path.normpath(os.path.abspath(wt))
        self.out = os.path.join(self.wt, "outputs")
        self.queue = os.path.join(self.out, "_dq_q_refs.jsonl")
        self.out_dir = os.path.join(self.out, "_dq_refs")
        self.result = os.path.join(self.out, "_dq_refs_result.txt")
        self.pool_log = os.path.join(self.out, "_mf2_pool_dq_refs.log")
        self.freeze_launch = os.path.join(self.out_dir, "_freeze_launch.json")
        self.freeze_complete = os.path.join(self.out_dir, "_freeze_complete.json")
        self.source = os.path.join(self.out, "_bp_q_arms.jsonl")
        self.source_all = os.path.join(self.out, "_bp_q_all.jsonl")
        self.seeds = os.path.join(self.out, "_dq_seeds.txt")
        self.cfv = os.path.join(self.wt, "common_fixed_variables.py")
        self.probe = os.path.join(self.out, "_ut_probe.py")
        self.old_dir = self.out
        self.git_cfg = list(git_cfg or [])
        self.echo = True
        self.output: list = []

    # -- output
    def emit(self, s: str = "") -> None:
        self.output.append(s)
        if self.echo:
            print(s)

    # -- git (explicit pathspecs only; the quarantine is excluded wherever a pathspec could reach outputs/)
    def git(self, args) -> str:
        r = subprocess.run(["git", "-C", self.wt, "-c", "core.quotepath=off"] + self.git_cfg + list(args),
                           capture_output=True, timeout=900)
        if r.returncode != 0:
            stop("git %s failed (rc %d): %s" % (" ".join(args), r.returncode,
                                                r.stderr.decode("utf-8", "replace").strip()[:300]))
        return r.stdout.decode("utf-8", "replace")

    def head(self) -> str:
        return self.git(["rev-parse", "HEAD"]).strip()

    def git_raw(self, args) -> bytes:
        r = subprocess.run(["git", "-C", self.wt, "-c", "core.quotepath=off"] + self.git_cfg + list(args),
                           capture_output=True, timeout=900)
        if r.returncode != 0:
            stop("git %s failed (rc %d): %s" % (" ".join(args), r.returncode,
                                                r.stderr.decode("utf-8", "replace").strip()[:300]))
        return r.stdout

    def tree_ish(self, commit: str) -> str:
        """What `git ls-tree` reads as "the commit" (the selftest's throwaway index has a write-tree instead)."""
        return commit

    def resolve(self, sha: str):
        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", sha or ""):
            return None
        r = subprocess.run(["git", "-C", self.wt, "rev-parse", "--verify", "--quiet", sha + "^{commit}"],
                           capture_output=True, timeout=120)
        return r.stdout.decode().strip() if r.returncode == 0 else None

    def freeze(self, phase: str, commit=None) -> dict:
        return freeze_record(self, phase, commit)

    # -- the tag check: outputs/_dq_queue.py's, imported (its locations / git sources / controls are the real tree's).
    # Its refusals raise SystemExit (its own stop()); they are turned into this tool's Stop (exit 2 at write).
    def tag_check(self, lines):
        return _dq_call(lambda: _mod("_dq_queue.py").tag_check(lines, resume=False, all_trees=True))

    def own_hits(self) -> list:
        return _dq_call(self._own_hits)

    def _own_hits(self) -> list:
        dq = _mod("_dq_queue.py")
        own = (self.queue, self.out_dir, self.result, self.pool_log)
        names = {os.path.basename(p).lower() for p in own}
        hits = ["EXISTS " + p for p in own if os.path.exists(p)]
        for _label, folder, _ctl in dq.locations(True):
            for n in dq._listing(folder) or []:
                if n.lower() in names:
                    hits.append("NAME IN USE " + os.path.join(folder, n))
        rel = {"outputs/" + os.path.basename(p).lower() for p in (self.queue, self.result, self.pool_log)}
        for kind in ("index", "history"):
            for p in dq._git_paths(kind):
                lp = p.lower()
                if lp in rel or lp.startswith("outputs/_dq_refs/") or lp == "outputs/_dq_refs":
                    hits.append("TRACKED (%s) %s" % (kind, p))
        return sorted(set(hits))

    # -- children in a fresh interpreter at this worktree (no bytecode written)
    def _child(self, mode: str, req: dict) -> dict:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([PY, "-B", os.path.abspath(__file__), mode],
                           input=json.dumps(req), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=self.wt, env=env, timeout=900)
        try:
            out = json.loads(r.stdout.strip().splitlines()[-1])
            if not isinstance(out, dict):
                raise ValueError("not an object")
            return out
        except Exception:
            return {"_error": "%s child failed rc=%s: %s" % (mode, r.returncode, (r.stderr or r.stdout)[-400:])}

    # -- SW: the accessors rebuilt in a fresh interpreter at this worktree
    def accessors(self, runs: dict) -> dict:
        return self._child("_accessors", {"repo": self.wt, "runs": runs})

    # -- the runtime values of common_fixed_variables.py, imported in a fresh interpreter at this worktree
    def cfv_runtime(self, keys: list) -> dict:
        return self._child("_cfv_values", {"repo": self.wt, "keys": list(keys)})


def _dq_call(fn):
    """Call into outputs/_dq_queue.py: its stop() raises SystemExit, which becomes this tool's Stop."""
    try:
        return fn()
    except SystemExit as exc:
        stop("outputs/_dq_queue.py refused: %s" % (exc.code,))


def _cfv_child() -> int:
    """stdin {"repo", "keys"} -> stdout {"values": {key: JSON value}, "absent": [...], "nonjson": [...], "file",
    "python"}: common_fixed_variables.py imported in this fresh interpreter from the repo (never the parse)."""
    req = json.load(sys.stdin)
    repo = os.path.normpath(req["repo"])
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    try:
        import common_fixed_variables as cfv  # noqa: E402
    except BaseException as exc:  # an import that exits or raises is an answer, not a crash
        print(json.dumps({"_error": "import of common_fixed_variables failed: %s %s" % (type(exc).__name__,
                                                                                        str(exc)[:200])}))
        return 3
    if not os.path.abspath(cfv.__file__).lower().startswith(repo.lower() + os.sep):
        print(json.dumps({"_error": "import mismatch %s" % cfv.__file__}))
        return 3
    values, absent, nonjson = {}, [], []
    for k in req["keys"]:
        v = getattr(cfv, k, _MISSING)
        if v is _MISSING:
            absent.append(k)
            continue
        j = _jsonable(v)
        if j is _MISSING:
            nonjson.append(k)
        else:
            values[k] = j
    print(json.dumps({"values": values, "absent": absent, "nonjson": nonjson, "file": cfv.__file__,
                      "python": sys.version.split()[0]}))
    return 0


def runtime_mismatch(parsed_values: dict, rt: dict) -> dict:
    """{"error": str|None, "mismatch": [keys]}: every parsed literal against its runtime value, type for type."""
    if not isinstance(rt, dict) or "_error" in rt or not isinstance(rt.get("values"), dict):
        return {"error": (rt.get("_error") if isinstance(rt, dict) else None) or "no answer", "mismatch": []}
    bad = []
    for k, v in parsed_values.items():
        if k in (rt.get("absent") or []) or k in (rt.get("nonjson") or []) or k not in rt["values"]:
            bad.append(k)
        elif _canon(rt["values"][k]) != _canon(v):
            bad.append(k)
    return {"error": None, "mismatch": sorted(bad)}


def _accessors_child() -> int:
    """stdin {"repo", "runs": {name: params}} -> stdout {name: {accessor: value}}; params applied as
    apply_scenario_config does (setattr on the cfv module), restored after each run."""
    req = json.load(sys.stdin)
    repo = os.path.normpath(req["repo"])
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    for m in (am, cfv):
        if not os.path.abspath(m.__file__).lower().startswith(repo.lower() + os.sep):
            print(json.dumps({"_error": "import mismatch %s" % m.__file__}))
            return 3
    out = {}
    for name, params in req["runs"].items():
        saved = {k: getattr(cfv, k, _MISSING) for k in params}
        for k, v in params.items():
            setattr(cfv, k, v)
        row = {}
        for a in ACC_KEY:
            fn = getattr(am, a, None)
            try:
                v = fn() if callable(fn) else "MISSING"
            except Exception as exc:
                v = "ERR %s" % type(exc).__name__
            row[a] = v if v is None or isinstance(v, (bool, int, float, str)) else repr(v)
        out[name] = row
        for k, v in saved.items():
            if v is _MISSING:
                delattr(cfv, k)
            else:
                setattr(cfv, k, v)
    out["_raw"] = {k: getattr(cfv, k, None) for k in ACC_KEY.values() if k}
    out["_python"] = sys.version.split()[0]
    out["_mesa"] = getattr(sys.modules.get("mesa"), "__version__", None)
    print(json.dumps(out))
    return 0


# ----------------------------------------------------------------------------------------------- shipped defaults
def _jsonable(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        out = [_jsonable(x) for x in v]
        return _MISSING if any(x is _MISSING for x in out) else out
    if isinstance(v, dict) and all(isinstance(k, str) for k in v):
        out = {k: _jsonable(x) for k, x in v.items()}
        return _MISSING if any(x is _MISSING for x in out.values()) else out
    return _MISSING


# a name of these, or an attribute of these, anywhere in the file can bind a module name the parse cannot see
_DYNAMIC_NAMES = frozenset({"exec", "eval", "compile", "setattr", "delattr", "globals", "vars", "locals",
                            "__import__", "__builtins__"})
_DYNAMIC_ATTRS = frozenset({"__dict__", "__builtins__"})


def _target_names(t) -> list:
    """The plain names a binding target binds (nested tuples / lists / starred included)."""
    if isinstance(t, ast.Name):
        return [t.id]
    if isinstance(t, (ast.Tuple, ast.List)):
        return [n for e in t.elts for n in _target_names(e)]
    if isinstance(t, ast.Starred):
        return _target_names(t.value)
    return []


def _attr_targets(t) -> list:
    """The attribute names an assignment / del target rebinds (`x.K = ...` may be this very module)."""
    if isinstance(t, ast.Attribute):
        return [t.attr]
    if isinstance(t, (ast.Tuple, ast.List)):
        return [n for e in t.elts for n in _attr_targets(e)]
    if isinstance(t, ast.Starred):
        return _attr_targets(t.value)
    return []


def _pattern_names(p) -> list:
    """The capture names of a match-case pattern."""
    out = []
    for n in ast.walk(p):
        if type(n).__name__ in ("MatchAs", "MatchStar") and isinstance(getattr(n, "name", None), str):
            out.append(n.name)
        if type(n).__name__ == "MatchMapping" and isinstance(getattr(n, "rest", None), str):
            out.append(n.rest)
    return out


def _module_scope(tree):
    """Every node evaluated in the module's own scope: function and lambda BODIES are pruned (their decorators,
    defaults, annotations stay); class bodies are kept (conservative). A walrus here binds a module name."""
    stack = [tree]
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.extend(list(n.decorator_list) + [n.args] + ([n.returns] if n.returns is not None else []))
        elif isinstance(n, ast.Lambda):
            stack.append(n.args)
        else:
            stack.extend(ast.iter_child_nodes(n))


def parse_cfv(text: str) -> dict:
    """The module-level literal constants of common_fixed_variables.py, parsed with ast (never imported).
    values: names bound exactly once, unconditionally, by a plain assignment of a JSON-able literal; nonliteral: names
    bound to anything else, by any other binding form, or inside a conditional / loop / with / try / match block;
    multiple: names bound more than once, counting EVERY binding form - assignment, augmented / annotated assignment,
    for / with / except / match-capture targets, import [as], def / class names, del, a walrus in the module's scope,
    a `global` statement anywhere (a function may rebind the module name), an attribute target anywhere (`m.K = ...`
    may be this module); dynamic: constructs that can bind any name unseen (exec / eval / compile / setattr / delattr /
    globals / vars / locals / __import__ / __builtins__, .__dict__, `from x import *`) - shipped_problems refuses them.
    Function bodies are otherwise not module level and are ignored."""
    tree = ast.parse(text)
    count: dict = {}
    values: dict = {}
    nonlit: set = set()
    dynamic: list = []

    def bind(names):
        """A binding by a form other than a plain literal assignment: counted, and never a literal value."""
        for n in names:
            count[n] = count.get(n, 0) + 1
            nonlit.add(n)

    def visit(stmts, conditional: bool):
        for st in stmts:
            kind = type(st).__name__
            if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = st.targets if isinstance(st, ast.Assign) else [st.target]
                plain = [t.id for t in targets if isinstance(t, ast.Name)]
                other = [n for t in targets if not isinstance(t, ast.Name) for n in _target_names(t)]
                for n in plain + other:
                    count[n] = count.get(n, 0) + 1
                value = getattr(st, "value", None)
                for n in plain:
                    lit = _MISSING
                    if not conditional and not isinstance(st, ast.AugAssign) and value is not None:
                        try:
                            lit = _jsonable(ast.literal_eval(value))
                        except Exception:
                            lit = _MISSING
                    if lit is _MISSING:
                        nonlit.add(n)
                        values.pop(n, None)
                    else:
                        values[n] = lit
                nonlit.update(other)
            elif isinstance(st, (ast.For, ast.AsyncFor)):
                bind(_target_names(st.target))
                visit(st.body, True)
                visit(st.orelse, True)
            elif isinstance(st, (ast.With, ast.AsyncWith)):
                for item in st.items:
                    if item.optional_vars is not None:
                        bind(_target_names(item.optional_vars))
                visit(st.body, True)
            elif isinstance(st, (ast.If, ast.While)):
                visit(st.body, True)
                visit(st.orelse, True)
            elif kind in ("Try", "TryStar"):
                visit(st.body, True)
                for h in st.handlers:
                    if h.name:
                        bind([h.name])
                    visit(h.body, True)
                visit(st.orelse, True)
                visit(st.finalbody, True)
            elif kind == "Match":
                for case in st.cases:
                    bind(_pattern_names(case.pattern))
                    visit(case.body, True)
            elif isinstance(st, (ast.Import, ast.ImportFrom)):
                for a in st.names:
                    if a.name == "*":
                        dynamic.append("from %s import * (line %d)" % (getattr(st, "module", None), st.lineno))
                    else:
                        bind([a.asname or a.name.split(".")[0]])
            elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bind([st.name])
            elif isinstance(st, ast.Delete):
                for t in st.targets:
                    bind(_target_names(t))
            elif kind == "TypeAlias":
                bind(_target_names(st.name))

    visit(tree.body, False)
    for n in _module_scope(tree):
        if isinstance(n, ast.NamedExpr):
            bind(_target_names(n.target))
    for n in ast.walk(tree):
        if isinstance(n, ast.Global):
            bind(list(n.names))
        elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
            for t in (n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]):
                bind(_attr_targets(t))
        elif isinstance(n, ast.Name) and n.id in _DYNAMIC_NAMES:
            dynamic.append("%s (line %d)" % (n.id, n.lineno))
        elif isinstance(n, ast.Attribute) and n.attr in _DYNAMIC_ATTRS:
            dynamic.append(".%s (line %d)" % (n.attr, n.lineno))
        elif (isinstance(n, ast.Attribute) and n.attr == "modules" and isinstance(n.value, ast.Name)
              and n.value.id == "sys"):
            dynamic.append("sys.modules (line %d)" % n.lineno)
    multiple = sorted(n for n, c in count.items() if c > 1)
    for n in multiple:
        values.pop(n, None)
    return {"values": dict(sorted(values.items())), "nonliteral": sorted(nonlit - set(multiple)),
            "multiple": multiple, "dynamic": sorted(set(dynamic))}


def shipped_problems(shipped: dict) -> list:
    probs = []
    if shipped.get("dynamic"):
        probs.append("common_fixed_variables.py can bind names dynamically, so its parse cannot be trusted: %s"
                     % shipped["dynamic"][:10])
    vals = shipped.get("values") or {}
    for k, want in list(EXPECTED_SHIPPED.items()) + list(LINE_SWITCH_DEFAULTS.items()):
        if k in (shipped.get("multiple") or []):
            probs.append("%s is assigned more than once in common_fixed_variables.py" % k)
        elif k in (shipped.get("nonliteral") or []):
            probs.append("%s is not a plain module-level literal in common_fixed_variables.py" % k)
        elif k not in vals:
            probs.append("%s is missing from common_fixed_variables.py" % k)
        elif not _same(vals[k], want):
            what = ("the flip ships %r" % want) if k in EXPECTED_SHIPPED else (
                "the reference line sets %s=%r, so a shipped default of %r would make it an override" % (k, want,
                                                                                                         vals[k]))
            probs.append("%s = %r: %s" % (k, vals[k], what))
    return probs


# ------------------------------------------------------------------------------------------------------------- lines
def _jsonl(path: str) -> list:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def seed_table(env: Env) -> dict:
    """outputs/_dq_seeds.txt sets 1 and 2: bases 9601 / 9621 and every row == the rule (rows sorted by key)."""
    with open(env.seeds, encoding="utf-8") as fh:
        doc = json.load(fh)
    table = {}
    for k, base in BASES.items():
        if (doc.get("bases") or {}).get("set%d" % k) != base:
            stop("_dq_seeds.txt base of set %d is %r, not %d" % (k, (doc.get("bases") or {}).get("set%d" % k), base))
        want = sorted([["%s_%s" % (s, w), s, wind, str(base + 4 * si + wi)]
                       for si, s in enumerate(SCENARIOS) for wi, (w, wind) in enumerate(WINDS)], key=lambda r: r[0])
        if doc.get("set%d" % k) != want:
            stop("_dq_seeds.txt set %d does not follow the rule seed = %d + 4*s + w" % (k, base))
        for key, scen, wind, seed in want:
            table[(k, key)] = (scen, wind, seed)
    return table


def expected_source_line(name: str, table: dict) -> dict:
    """bayesprep_part1.txt 7.1's bpc line, written out independently of the frozen file."""
    m = SRC_RE.match(name)
    if not m:
        stop("%s is not a bpc<r|u>[2]_<S>_<W> name" % name)
    p, k = m.group(1), (2 if m.group(2) else 1)
    key = "%s_%s" % (m.group(3), m.group(4))
    if k == 2 and (p, key) != ("u", "D_W"):
        stop("%s: set 2 holds only the uniform D_W cell (7.1)" % name)
    scen, wind, seed = table[(k, key)]
    rule = BASES[k] + 4 * SCENARIOS.index(m.group(3)) + [w for w, _n in WINDS].index(m.group(4))
    if seed != str(rule):
        stop("%s: seed %s != rule %d" % (name, seed, rule))
    out = os.path.join(BP_WT, "outputs", "_sd_%s.json" % name)
    argv = [os.path.join(BP_WT, "outputs", "_ut_probe.py"), "--crn", "--hazard", "--instrument", "--",
            "--repo", BP_WT, "--scenario", scen, "--wind", wind, "--seed", seed,
            "--set", "GLOBAL_PLANNER_MODE=0", "--set", "VICTIM_SPAWN_MODE=%d" % (0 if p == "r" else 1),
            "--steps", str(STEPS), "--set", "BATCH_SIZE=%d" % STEPS, "--out", out, "--tag", name]
    return {"name": name, "argv": argv, "out": out, "cwd": BP_WT}


def source_lines(env: Env) -> list:
    bpc = [ln for ln in _jsonl(env.source) if str(ln.get("name", "")).startswith("bpc")]
    names = [ln.get("name") for ln in bpc]
    if tuple(names) != SOURCE_NAMES:
        stop("%s: the bpc lines are %d %s, not the 33 of 7.1 in order (bpcr_*, bpcu_*, bpcu2_D_W)"
             % (env.source, len(names), names[:3]))
    other = [ln for ln in _jsonl(env.source_all) if str(ln.get("name", "")).startswith("bpc")]
    if other != bpc:
        stop("%s: its bpc lines differ from %s" % (env.source_all, env.source))
    table = seed_table(env)
    for ln in bpc:
        if ln != expected_source_line(ln["name"], table):
            stop("%s: the frozen line differs from bayesprep_part1.txt 7.1's line" % ln["name"])
    return bpc


def ref_tag(src_name: str) -> str:
    m = SRC_RE.match(src_name)
    return "%s%s%d_%s_%s" % (TAG_PREFIX, m.group(1), 2 if m.group(2) else 1, m.group(3), m.group(4))


def ref_line(env: Env, src: dict) -> dict:
    tag = ref_tag(src["name"])
    out = os.path.join(env.out_dir, "_sd_%s.json" % tag)
    argv = list(src["argv"])
    if os.path.basename(argv[0]) != "_ut_probe.py":
        stop("%s: argv[0] %s is not _ut_probe.py" % (src["name"], argv[0]))
    argv[0] = env.probe
    pos = [0]
    for flag, old, new in (("--repo", BP_WT, env.wt), ("--out", src["out"], out), ("--tag", src["name"], tag)):
        if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != old:
            stop("%s: %s is not the expected token" % (src["name"], flag))
        j = argv.index(flag) + 1
        argv[j] = new
        pos.append(j)
    changed = [i for i, (a, b) in enumerate(zip(argv, src["argv"])) if a != b]
    if len(argv) != len(src["argv"]) or changed != sorted(pos):
        stop("%s differs from its bpc line in positions %s, not exactly %s" % (tag, changed, sorted(pos)))
    return {"name": tag, "argv": argv, "out": out, "cwd": env.wt}


def build_lines(env: Env) -> list:
    lines = [ref_line(env, s) for s in source_lines(env)]
    names = [ln["name"].lower() for ln in lines]
    if len(lines) != N_LINES or len(set(names)) != N_LINES or len({os.path.normcase(ln["out"]) for ln in lines}) != N_LINES:
        stop("the reference queue has %d lines / %d distinct names, not %d" % (len(lines), len(set(names)), N_LINES))
    return lines


def queue_bytes(lines: list) -> bytes:
    return "".join(json.dumps(ln) + "\n" for ln in lines).encode("utf-8")


def line_sets(after: list, parse_value) -> dict:
    sets = {}
    for i, tok in enumerate(after):
        if tok == "--set":
            k, v = after[i + 1].split("=", 1)
            sets[k.strip()] = parse_value(v)
    return sets


# ------------------------------------------------------------------------------------------------------------ freeze
def _blob_same(env: Env, data: bytes, oid: str) -> bool:
    """The file's content equals the blob, LF-normalised (a CRLF working copy of an LF blob is the same content)."""
    if oid in (_git_oid(data), _git_oid(_lf(data))):
        return True
    try:
        return _lf(env.git_raw(["cat-file", "blob", oid])) == _lf(data)
    except Stop:
        return False


def freeze_record(env: Env, phase: str, commit=None) -> dict:
    """The tree's state. commit: the commit the run-loaded files are compared with blob by blob (default HEAD)."""
    time_ns = time.time_ns()
    chain = list(CHAIN_FILES) + list(TOOLING_FILES)
    tracked = _z(env.git(["ls-files", "-z", "--", ".", ":(exclude)outputs", QUARANTINE_EXCLUDE]))
    chain_tracked = set(_z(env.git(["ls-files", "-z", "--"] + chain + [QUARANTINE_EXCLUDE])))
    st = env.git(["status", "--porcelain", "-uno", "--", ".", ":(exclude)outputs", QUARANTINE_EXCLUDE])
    st += "\n" + env.git(["status", "--porcelain", "-uno", "--"] + chain + [QUARANTINE_EXCLUDE])
    untracked = _z(env.git(["ls-files", "--others", "--exclude-standard", "-z", "--", "src_extension"]))
    head = env.head()
    commit = commit or head
    # the blobs of the commit: the top-level entries of the tracked files outside outputs/ (ls-tree takes no exclude
    # magic, so outputs/ - and the quarantine in it - is never named) plus the chain files by exact path
    top = sorted({p.split("/", 1)[0] for p in tracked if p.split("/", 1)[0] != "outputs"})
    blobs = {}
    for ent in env.git(["ls-tree", "-r", "-z", env.tree_ish(commit), "--"] + top + list(CHAIN_FILES)).split("\0"):
        if "\t" in ent:
            meta, path = ent.split("\t", 1)
            parts = meta.split()
            if len(parts) == 3 and parts[1] == "blob":
                blobs[path.strip("\r\n")] = parts[2]
    sha, sha_lf, mtime_ns, blob_mismatch = {}, {}, {}, []
    tracked_set = set(tracked)
    for p in sorted(tracked_set | set(chain)):
        fp = os.path.join(env.wt, *p.split("/"))
        if os.path.isfile(fp):
            data = _read(fp)
            sha[p], sha_lf[p] = _sha(data), _sha(_lf(data))
            mtime_ns[p] = os.stat(fp).st_mtime_ns
            if run_loaded(p) and (p in tracked_set or p in CHAIN_FILES):
                if p not in blobs:
                    blob_mismatch.append("%s (no blob at the commit)" % p)
                elif not _blob_same(env, data, blobs[p]):
                    blob_mismatch.append(p)
        else:
            sha[p] = sha_lf[p] = "missing"
            mtime_ns[p] = None
    try:
        shipped = parse_cfv(_read(env.cfv).decode("utf-8"))
    except Exception as exc:
        shipped = {"values": {}, "nonliteral": [], "multiple": [], "dynamic": [], "error": repr(exc)[:200]}
    keys = sorted(set(shipped.get("values") or {}) | set(EXPECTED_SHIPPED) | set(LINE_SWITCH_DEFAULTS))
    runtime = runtime_mismatch(shipped.get("values") or {}, env.cfv_runtime(keys))
    runtime["n_keys"] = len(shipped.get("values") or {})
    return {"phase": phase, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "time_ns": time_ns, "head": head,
            "wt": env.wt, "status": sorted({ln for ln in st.splitlines() if ln.strip()}),
            "untracked_src_extension": untracked,
            "untracked_chain": sorted(p for p in chain if p not in chain_tracked),
            "n_tracked_outside_outputs": len(tracked), "sha": sha, "sha_lf": sha_lf, "mtime_ns": mtime_ns,
            "blob_commit": commit, "blob_mismatch": sorted(blob_mismatch), "shipped": shipped, "runtime": runtime}


def _format_problems(fr: dict) -> list:
    """The freeze record holds every field this version of the tool checks."""
    probs = []
    if not isinstance(fr.get("time_ns"), int) or not isinstance(fr.get("mtime_ns"), dict):
        probs.append("the freeze record has no mtimes (time_ns / mtime_ns)")
    if not isinstance(fr.get("blob_mismatch"), list):
        probs.append("the freeze record has no blob comparison")
    if not isinstance(fr.get("runtime"), dict):
        probs.append("the freeze record has no runtime comparison of common_fixed_variables.py")
    return probs


def _runtime_problems(fr: dict) -> list:
    rt = fr.get("runtime") if isinstance(fr.get("runtime"), dict) else {}
    if rt.get("error"):
        return ["the runtime import of common_fixed_variables.py failed: %s" % str(rt["error"])[:300]]
    if rt.get("mismatch"):
        return ["common_fixed_variables.py values at runtime differ from the parsed literals: %s" % rt["mismatch"][:10]]
    return []


def launch_problems(fr: dict, head_full) -> tuple:
    """(problems, notes) of a freeze record as the launch state of the flip commit."""
    probs, notes = [], []
    probs += _format_problems(fr)
    if head_full is not None and fr.get("head") != head_full:
        probs.append("HEAD is %s, --head resolves to %s" % (fr.get("head"), head_full))
    if fr.get("blob_mismatch"):
        probs.append("run-loaded files differ from their blob at %s (git status cannot see an assume-unchanged / "
                     "skip-worktree file): %s" % (str(fr.get("blob_commit"))[:12], fr["blob_mismatch"][:10]))
    if isinstance(fr.get("time_ns"), int) and isinstance(fr.get("mtime_ns"), dict):
        late = sorted(p for p, v in fr["mtime_ns"].items() if run_loaded(p) and isinstance(v, int)
                      and v > fr["time_ns"] + MTIME_TOL_NS)
        if late:
            probs.append("run-loaded files with an mtime later than the freeze time: %s" % late[:10])
    probs += _runtime_problems(fr)
    rl = [ln for ln in fr.get("status") or [] if run_loaded(_status_path(ln))]
    other = [ln for ln in fr.get("status") or [] if not run_loaded(_status_path(ln))]
    if rl:
        probs.append("run-loaded tracked files modified: %s" % rl[:10])
    if other:
        notes.append("non-run-loaded tracked files modified: %s" % other[:10])
    if fr.get("untracked_src_extension"):
        probs.append("untracked files under src_extension/: %s" % fr["untracked_src_extension"][:10])
    bad_chain = [p for p in fr.get("untracked_chain") or [] if p in CHAIN_FILES]
    if bad_chain:
        probs.append("chain files not tracked: %s" % bad_chain)
    if [p for p in fr.get("untracked_chain") or [] if p not in CHAIN_FILES]:
        notes.append("tooling files not tracked yet: %s" % [p for p in fr["untracked_chain"] if p not in CHAIN_FILES])
    missing = [p for p, v in (fr.get("sha") or {}).items() if v == "missing" and run_loaded(p)]
    if missing:
        probs.append("run-loaded files missing: %s" % missing[:10])
    if (fr.get("shipped") or {}).get("error"):
        probs.append("common_fixed_variables.py did not parse: %s" % fr["shipped"]["error"])
    probs += shipped_problems(fr.get("shipped") or {})
    return probs, notes


def tooling_changed(f0: dict, f1: dict) -> list:
    """The analysis files (TOOLING_FILES) whose LF sha differs between the launch record and now."""
    s0, s1 = f0.get("sha_lf") or {}, f1.get("sha_lf") or {}
    return sorted(p for p in TOOLING_FILES if s0.get(p) != s1.get(p))


def compare_freeze(f0: dict, f1: dict) -> tuple:
    """(fails, notes): the analysis-time (or pre-launch) re-freeze against the launch record. Every caller also runs
    launch_problems(f0) (the launch record's own format and cleanliness)."""
    fails, notes = [], []
    fails += ["now: %s" % x for x in _format_problems(f1)]
    s0, s1 = f0.get("sha_lf") or {}, f1.get("sha_lf") or {}
    r0, r1 = f0.get("sha") or {}, f1.get("sha") or {}
    changed = sorted(p for p in set(s0) | set(s1) if s0.get(p) != s1.get(p))
    eol_only = sorted(p for p in set(r0) | set(r1) if r0.get(p) != r1.get(p) and p not in changed)
    bad = [p for p in changed if run_loaded(p)]
    if bad:
        fails.append("run-loaded files changed since launch: %s" % bad[:10])
    tool = tooling_changed(f0, f1)
    if tool:
        fails.append("analysis files changed since launch (LF sha): %s" % tool)
    other = [p for p in changed if not run_loaded(p) and p not in TOOLING_FILES]
    if other:
        notes.append("non-run-loaded files changed since launch: %s" % other[:10])
    if eol_only:
        notes.append("line endings only changed since launch: %s" % eol_only[:10])
    m0, m1 = f0.get("mtime_ns"), f1.get("mtime_ns")
    if isinstance(m0, dict) and isinstance(m1, dict):
        t0 = f0.get("time_ns") if isinstance(f0.get("time_ns"), int) else None
        touched = sorted(p for p in set(m0) | set(m1) if run_loaded(p) and (
            m0.get(p) != m1.get(p) or (t0 is not None and isinstance(m1.get(p), int) and m1[p] > t0 + MTIME_TOL_NS)))
        if touched:
            fails.append("run-loaded files touched since launch (mtime differs from the launch record or is later "
                         "than the launch freeze; an edit FAILS even when reverted): %s" % touched[:10])
    if f1.get("head") != f0.get("head"):
        notes.append("HEAD moved since launch: %s -> %s (run-loaded files %s)"
                     % (str(f0.get("head"))[:12], str(f1.get("head"))[:12], "unchanged" if not bad else "CHANGED"))
    rl = [ln for ln in f1.get("status") or [] if run_loaded(_status_path(ln))]
    if rl:
        fails.append("run-loaded tracked files modified at analysis: %s" % rl[:10])
    if f1.get("untracked_src_extension"):
        fails.append("untracked files under src_extension/ at analysis: %s" % f1["untracked_src_extension"][:10])
    if f1.get("blob_mismatch"):
        fails.append("run-loaded files differ from their blob at the frozen head %s: %s"
                     % (str(f1.get("blob_commit"))[:12], f1["blob_mismatch"][:10]))
    if f1.get("blob_commit") is not None and f1.get("blob_commit") != f0.get("head"):
        fails.append("the re-freeze compared blobs at %s, not the frozen head %s"
                     % (str(f1.get("blob_commit"))[:12], str(f0.get("head"))[:12]))
    fails += ["now: %s" % x for x in _runtime_problems(f1)]
    if (f1.get("shipped") or {}).get("values") != (f0.get("shipped") or {}).get("values"):
        fails.append("the parsed shipped defaults changed since launch")
    fails += ["now: %s" % x for x in shipped_problems(f1.get("shipped") or {})]
    return fails, notes


# ---------------------------------------------------------------------------------------------- write / check
def _tag_rows(env: Env, lines: list) -> tuple:
    rows, details = env.tag_check(lines)
    own = env.own_hits()
    rows = [list(r) for r in rows] + [["own paths (queue, outputs/_dq_refs/, result, pool log)", "4", str(len(own)),
                                       "-", "PASS" if not own else "FAIL"]]
    return all(str(r[4]).startswith("PASS") for r in rows), rows, list(details) + own


def _table(env: Env, rows: list) -> None:
    head = ["check", "scanned", "hits", "control", "verdict"]
    width = [max(len(str(r[i])) for r in rows + [head]) for i in range(5)]
    for r in [head] + rows:
        env.emit("  " + "  ".join(str(r[i]).ljust(width[i]) if i in (0, 4) else str(r[i]).rjust(width[i])
                                  for i in range(5)).rstrip())


def _summary(shipped: dict) -> str:
    vals = shipped.get("values") or {}
    return ", ".join("%s %s" % (k, vals.get(k, "-")) for k in SUMMARY_KEYS)


def frozen_problems(env: Env, data: bytes, full) -> tuple:
    """(problems, notes, f0) of a FROZEN queue right before (or while) the pool runs: the queue identical, its launch
    record present and matching, --head (when given) == the frozen head, HEAD == the frozen head, the launch record
    clean, and the tree re-frozen now equal to the launch record (compare_freeze: hashes, mtimes, blobs at the frozen
    head, runtime cfv values, analysis files)."""
    probs, notes = [], []
    if _lf(_read(env.queue)) != data:
        return ["%s exists and differs from the rebuilt lines (frozen; never re-written)" % env.queue], notes, None
    if not os.path.exists(env.freeze_launch):
        return ["%s is frozen but %s is missing" % (env.queue, env.freeze_launch)], notes, None
    with open(env.freeze_launch, encoding="utf-8") as fh:
        f0 = json.load(fh)
    if f0.get("queue_sha256") != _sha(data):
        probs.append("the launch record's queue sha %s != the queue's %s" % (str(f0.get("queue_sha256"))[:16],
                                                                             _sha(data)[:16]))
    if full is not None and f0.get("head") != full:
        probs.append("the frozen queue was written at head %s, --head resolves to %s" % (f0.get("head"), full))
    head = env.head()
    if head != f0.get("head"):
        probs.append("HEAD is %s, not the frozen head %s (every run records HEAD at its start)"
                     % (head, f0.get("head")))
    lp, ln = launch_problems(f0, None)
    probs += ["launch record: %s" % x for x in lp]
    notes += ["launch record: %s" % x for x in ln]
    f1 = env.freeze("check", commit=f0.get("head"))
    cf, cn = compare_freeze(f0, f1)
    probs += cf
    notes += cn
    return probs, notes, f0


def write(env: Env, head_arg) -> int:
    if not head_arg:
        stop("write needs --head SHA (the flip commit)")
    lines = build_lines(env)
    data = queue_bytes(lines)
    full = env.resolve(head_arg)
    if not full:
        stop("--head %s does not name a commit of %s" % (head_arg, env.wt))
    if os.path.exists(env.queue):
        probs, notes, _f0 = frozen_problems(env, data, full)
        for n in notes:
            env.emit("NOTE %s" % n)
        if probs:
            stop("the frozen queue no longer stands on its launch tree - nothing written, do not launch:\n  "
                 + "\n  ".join(probs))
        env.emit("unchanged (frozen; HEAD and the tree re-verified against the launch record): %s (%d lines, sha256 %s,"
                 " head %s)" % (env.queue, len(lines), _sha(data), full))
        env.emit("pool (PYTHONDONTWRITEBYTECODE=1): %s %s %s %s --maxpar 12 --min-free-gb 3"
                 % (PY, os.path.join(env.out, "_mf2_pool.py"), env.queue, env.pool_log))
        return 0
    if os.path.exists(env.out_dir):
        stop("%s exists without a frozen queue (a partial or foreign write): nothing written" % env.out_dir)
    if not os.path.isfile(env.probe):
        stop("the probe %s does not exist in this worktree" % env.probe)
    fr = env.freeze("launch", commit=full)
    probs, notes = launch_problems(fr, full)
    for n in notes:
        env.emit("NOTE %s" % n)
    if probs:
        stop("the tree is not the clean flip commit - nothing written:\n  " + "\n  ".join(probs))
    ok, rows, details = _tag_rows(env, lines)
    _table(env, rows)
    if not ok:
        stop("TAG CHECK FAILED - nothing written:\n  " + "\n  ".join(details[:60]))
    src = _read(env.source)
    fr.update(head_arg=head_arg, queue=env.queue, queue_sha256=_sha(data), n_lines=len(lines),
              source=env.source, source_sha256_lf=_sha(_lf(src)), probe=env.probe, probe_sha256=_sha(_read(env.probe)),
              names=[ln["name"] for ln in lines])
    os.makedirs(env.out_dir, exist_ok=False)
    with open(env.freeze_launch, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fr, fh, indent=1, sort_keys=True)
        fh.write("\n")
    with open(env.queue, "wb") as fh:
        fh.write(data)
    env.emit("shipped (parsed from common_fixed_variables.py): %s" % _summary(fr["shipped"]))
    env.emit("wrote %s (%d lines, sha256 %s) and %s (head %s, %d files hashed)"
             % (env.queue, len(lines), _sha(data), env.freeze_launch, full, len(fr["sha"])))
    env.emit("pool (PYTHONDONTWRITEBYTECODE=1): %s %s %s %s --maxpar 12 --min-free-gb 3"
             % (PY, os.path.join(env.out, "_mf2_pool.py"), env.queue, env.pool_log))
    return 0


def check(env: Env, head_arg) -> int:
    """The dry run of write: nothing is written. On a frozen queue: the pre-launch re-verification."""
    lines = build_lines(env)
    data = queue_bytes(lines)
    env.emit("lines: %d (%s .. %s), queue sha256 %s" % (len(lines), lines[0]["name"], lines[-1]["name"], _sha(data)))
    ok = True
    full = None
    if head_arg:
        full = env.resolve(head_arg)
        if not full:
            env.emit("FAIL --head %s does not name a commit" % head_arg)
            ok = False
    if os.path.exists(env.queue):
        probs, notes, f0 = frozen_problems(env, data, full)
        env.emit("queue %s exists (frozen at %s): re-verified against the launch record"
                 % (env.queue, (f0 or {}).get("head")))
        for n in notes:
            env.emit("NOTE %s" % n)
        for pr in probs:
            env.emit("FAIL %s" % pr)
        ok &= not probs
        env.emit("CHECK (frozen) => %s" % ("PASS (the launch state holds)" if ok else "FAIL (do not launch)"))
        return 0 if ok else 1
    if not head_arg:
        env.emit("FAIL no --head: HEAD %s is not verified (write needs --head SHA, the flip commit)" % env.head())
        ok = False
    env.emit("probe %s: %s" % (env.probe, "present" if os.path.isfile(env.probe) else "MISSING"))
    ok &= os.path.isfile(env.probe)
    fr = env.freeze("check", commit=full)
    env.emit("HEAD %s; shipped: %s" % (fr["head"], _summary(fr["shipped"])))
    probs, notes = launch_problems(fr, full)
    for n in notes:
        env.emit("NOTE %s" % n)
    for pr in probs:
        env.emit("FAIL %s" % pr)
    ok &= not probs
    tok, rows, details = _tag_rows(env, lines)
    _table(env, rows)
    for d in details[:60]:
        env.emit("    " + d)
    ok &= tok
    env.emit("CHECK => %s" % ("PASS (write would freeze)" if ok else "FAIL"))
    return 0 if ok else 1


# ----------------------------------------------------------------------------------------------------------- analyze
def want_accessors(parsed: dict, vsm) -> dict:
    want = {}
    for a, k in ACC_KEY.items():
        if k is None:
            want[a] = vsm
            continue
        v = parsed.get(k, _MISSING)
        if a in INT_ACCESSORS:
            if type(v) is int:
                want[a] = v
        elif type(v) is int and v in (0, 1):
            want[a] = bool(v)
    for a in FLIP_ACCESSORS:
        want[a] = True
    return want


def _mr1_problems(mr: dict, params, parsed: dict, mr1_acc) -> list:
    """V-mr1: the MR1 record shape (outputs/_mvg_ist.py) and fix3b_part1.txt 19.11 (b)'s accumulation identity.
    Value-free: the problems name shapes and the verdict of the identity, never an MR1 value."""
    p = []
    ms, lst, ids, nobs = mr.get("mr1_steps"), mr.get("mr1_list"), mr.get("mr1_ids"), mr.get("n_observations")
    n_uav = len(lst) if isinstance(lst, list) else -1
    n_agents = params.get("NUM_AGENTS") if isinstance(params, dict) else None
    shape_ok = (isinstance(ms, list) and len(ms) == STEPS and n_uav > 0
                and all(isinstance(x, list) and len(x) == 3 and isinstance(x[1], list) and isinstance(x[2], list)
                        and len(x[1]) == n_uav and len(x[2]) == n_uav for x in ms)
                and [x[0] for x in ms] == list(range(1, STEPS + 1))
                and isinstance(ids, list) and len(ids) == n_uav
                and type(nobs) in (int, float) and nobs > 0
                and type(n_agents) is int and n_uav == n_agents)
    if not shape_ok:
        p.append("mr record malformed (%s mr1_steps rows, %s UAVs in mr1_list, %s ids, n_observations %s, NUM_AGENTS "
                 "%s)" % (len(ms) if isinstance(ms, list) else None, n_uav, len(ids) if isinstance(ids, list) else None,
                          "present" if type(nobs) in (int, float) and nobs > 0 else "MISSING", n_agents))
        return p
    fix = parsed.get("MR1_TRUTHINESS_FIX", _MISSING)
    if not (type(fix) is int and fix in (0, 1)):
        p.append("MR1_TRUTHINESS_FIX has no 0 / 1 shipped literal: the MR1 identity cannot be checked")
        return p
    col = 2 if fix == 1 else 1
    try:
        want = mr1_acc(n_uav, [x[col] for x in ms], float(nobs))
    except Exception as exc:
        p.append("the MR1 accumulation could not be rebuilt (%s)" % type(exc).__name__)
        return p
    if list(lst) != want or any(type(a) is not float for a in lst):
        p.append("mr.mr1_list != the %s accumulation of mr1_steps (fix3b_part1.txt 19.11 (b))"
                 % ("CORRECTED" if fix == 1 else "LITERAL"))
    return p


def validate_record(line: dict, d: dict, sidecar, f0: dict, fb3_keys, parse_value, err_re, wt: str,
                    mr1_acc) -> list:
    """Every V-check of one run; a list of problems (labels / parameters / counts only - never an outcome value)."""
    p = []
    argv = line["argv"]
    after = argv[argv.index("--") + 1:]
    sets = line_sets(after, parse_value)

    def val(flag):
        return after[after.index(flag) + 1]

    vsm = sets.get("VICTIM_SPAWN_MODE")
    parsed = (f0.get("shipped") or {}).get("values") or {}
    # V-done (the keys must be PRESENT: a missing key is never read as a pass)
    if d.get("complete") is not True:
        p.append("complete %r" % d.get("complete"))
    if "crashed" not in d:
        p.append("crashed key missing")
    elif d["crashed"] is not None:
        p.append("crashed (%s)" % ((d["crashed"] or {}).get("type") if isinstance(d["crashed"], dict) else "?"))
    if not (_same(d.get("steps_done"), STEPS) and _same(d.get("steps"), STEPS) and val("--steps") == str(STEPS)):
        p.append("steps_done %r / steps %r, not %d" % (d.get("steps_done"), d.get("steps"), STEPS))
    # V-prov
    if not _same_path(d.get("repo"), wt):
        p.append("repo %s" % d.get("repo"))
    if d.get("head") != f0.get("head"):
        p.append("head %s != the frozen head %s" % (d.get("head"), f0.get("head")))
    if d.get("tag") != line["name"]:
        p.append("tag %s" % d.get("tag"))
    if d.get("scenario") != val("--scenario") or d.get("wind") != val("--wind") or not _same(d.get("seed"),
                                                                                           int(val("--seed"))):
        p.append("scenario / wind / seed %s %s %s != the line's" % (d.get("scenario"), d.get("wind"), d.get("seed")))
    ss = d.get("src_sha")
    if not isinstance(ss, dict):
        p.append("src_sha missing")
    else:
        keys = sorted(str(k).replace("\\", "/") for k in ss)
        if keys != sorted(SRC_SHA_FILES):
            p.append("src_sha keys %s != outputs/_sd_probe.py's 11 (missing %s, extra %s)"
                     % (len(keys), sorted(set(SRC_SHA_FILES) - set(keys)), sorted(set(keys) - set(SRC_SHA_FILES))))
        for fname, h in ss.items():
            rel = str(fname).replace("\\", "/")
            if h not in (str((f0.get("sha") or {}).get(rel))[:16], str((f0.get("sha_lf") or {}).get(rel))[:16]):
                p.append("src_sha %s != the launch freeze" % rel)
    # V-pin: the pinned runtime and the probe versions the frozen chain writes (python: analyze, vs the venv)
    if d.get("mesa") != PINNED_MESA:
        p.append("mesa %r, not the pinned %s" % (d.get("mesa"), PINNED_MESA))
    for sec, ver, _src in PROBE_VERSIONS:
        holder = d if sec is None else d.get(sec)
        got = holder.get("probe") if isinstance(holder, dict) else None
        if got != ver:
            p.append("%s probe version %r, not %r" % (sec or "record", got, ver))
    # V-argv
    if d.get("argv") != after:
        p.append("argv differs from the queue line")
    if d.get("extra_params") != sets:
        p.append("extra_params differ from the line's --set list")
    try:
        if json.loads(sidecar) != {"argv": argv, "cwd": line["cwd"]}:
            p.append(".argv sidecar differs from the queue line")
    except Exception:
        p.append(".argv sidecar missing or unreadable")
    # V-crn
    fb3 = d.get("fb3") if isinstance(d.get("fb3"), dict) else {}
    crn = fb3.get("crn") if isinstance(fb3.get("crn"), dict) else {}
    if not (crn.get("on") is True and type(crn.get("crn_draws")) is int and crn["crn_draws"] > 0):
        p.append("CRN not on with draws > 0 (on %r, draws %r)" % (crn.get("on"), crn.get("crn_draws")))
    # V-par: params
    params = d.get("params")
    if not isinstance(params, dict):
        p.append("params missing")
    else:
        extra = sorted(k for k in params if k not in SCENARIO_KEYS and k not in sets)
        if extra:
            p.append("parameters outside the scenario preset and the line's --set list: %s" % extra)
        for k, v in sets.items():
            if not _same(params.get(k), v):
                p.append("params %s = %r, the line sets %r" % (k, params.get(k), v))
            if k not in PLACEMENT_KEYS:
                if k not in parsed:
                    p.append("--set %s: no literal shipped default to compare with" % k)
                elif not _same(v, parsed[k]):
                    p.append("--set %s=%r overrides the shipped default %r" % (k, v, parsed[k]))
        if params.get("WIND_DIRECTION") != val("--wind"):
            p.append("params WIND_DIRECTION %r" % params.get("WIND_DIRECTION"))
    # V-par: the switches the run recorded
    sw = fb3.get("switches")
    if not isinstance(sw, dict) or sorted(sw) != sorted(fb3_keys):
        p.append("fb3.switches missing or its keys differ from _fb3_probe.FIX3B_KEYS")
    else:
        for k in fb3_keys:
            want = vsm if k == "VICTIM_SPAWN_MODE" else parsed.get(k, _MISSING)
            if want is _MISSING:
                p.append("fb3.switches %s: no literal shipped default to compare with" % k)
            elif not _same(sw[k], want):
                p.append("fb3.switches %s = %r, shipped %r" % (k, sw[k], want))
    eff = fb3.get("eff") if isinstance(fb3.get("eff"), dict) else {}
    if not _same(eff.get("searcher_targeting"), parsed.get("SEARCHER_TARGETING", _MISSING)):
        p.append("fb3.eff searcher_targeting %r" % eff.get("searcher_targeting"))
    if not _same(eff.get("victim_spawn_mode"), vsm):
        p.append("fb3.eff victim_spawn_mode %r" % eff.get("victim_spawn_mode"))
    bp = fb3.get("bp_switches")
    if not isinstance(bp, dict):
        p.append("fb3.bp_switches missing (the --instrument flag)")
    else:
        for k in ("SEARCHER_TARGETING_FIX", "UAV_DOCKED_NOT_OBSTACLE"):
            rec = bp.get(k) if isinstance(bp.get(k), dict) else {}
            want = parsed.get(k, _MISSING)
            if want is _MISSING or not _same(rec.get("raw"), want):
                p.append("fb3.bp_switches %s raw %r, shipped %r" % (k, rec.get("raw"), None if want is _MISSING
                                                                     else want))
            elif type(want) is int and want in (0, 1) and rec.get("eff") is not bool(want):
                p.append("fb3.bp_switches %s effective %r" % (k, rec.get("eff")))
        fp_rec = sorted(k for k in bp if k.startswith("SEARCHER_FP_"))
        fp_cfv = sorted(k for k in parsed if k.startswith("SEARCHER_FP_"))
        if fp_rec != fp_cfv:
            p.append("SEARCHER_FP_* keys recorded %s != shipped %s" % (fp_rec, fp_cfv))
        for k in fp_rec:
            if not _same((bp[k] or {}).get("raw") if isinstance(bp[k], dict) else None, parsed.get(k, _MISSING)):
                p.append("fb3.bp_switches %s raw differs from the shipped default" % k)
    ut = d.get("ut") if isinstance(d.get("ut"), dict) else None
    if ut is None:
        p.append("ut section missing")
    else:
        s = ut.get("switch") if isinstance(ut.get("switch"), dict) else {}
        for raw_k, on_k, ck in (("raw", "on", "SEARCHER_UNTUNED"), ("recall_raw", "recall_on", "SEARCHER_END_RECALL"),
                                ("ffrel_raw", "ffrel_on", "FF_RELEASE_DETECTED_ONLY")):
            want = parsed.get(ck, _MISSING)
            if want is _MISSING or not _same(s.get(raw_k), want):
                p.append("ut.switch %s %r, shipped %s %r" % (raw_k, s.get(raw_k), ck, None if want is _MISSING
                                                             else want))
            elif type(want) is int and want in (0, 1) and s.get(on_k) is not bool(want):
                p.append("ut.switch %s %r" % (on_k, s.get(on_k)))
    eff_all = d.get("effective") if isinstance(d.get("effective"), dict) else None
    gpm = eff_all.get("global_planner_mode") if eff_all is not None else None
    if not _same(gpm, parsed.get("GLOBAL_PLANNER_MODE", _MISSING)):
        p.append("effective global_planner_mode %r" % (gpm,))
    # V-inst: every error list PRESENT and empty; a missing key is never read as "no error"
    if eff_all is None:
        p.append("effective section missing")
    else:
        bad_eff = sorted(k for k in EFFECTIVE_KEYS if k not in eff_all or (isinstance(eff_all[k], str) and (
            eff_all[k].startswith("ERR") or eff_all[k] == "ABSENT")))
        if bad_eff:
            p.append("effective accessors missing / ERR / ABSENT: %s" % bad_eff)
    inst = fb3.get("inst")
    if not isinstance(inst, dict):
        p.append("fb3.inst missing (the --instrument flag)")
    elif not (type(inst.get("error_count")) is int and inst["error_count"] == 0 and inst.get("broken") is False
              and isinstance(inst.get("errors"), list) and not inst["errors"]):
        p.append("fb3.inst error_count %r broken %r errors %s" % (
            inst.get("error_count"), inst.get("broken"),
            len(inst["errors"]) if isinstance(inst.get("errors"), list) else "MISSING"))
    mr = d.get("mr")
    if not isinstance(mr, dict):
        p.append("mr section missing")
    else:
        if not (isinstance(mr.get("errors"), list) and not mr["errors"]):
            p.append("mr errors: %s" % (("%d entries" % len(mr["errors"])) if isinstance(mr.get("errors"), list)
                                        else "MISSING"))
        p += _mr1_problems(mr, d.get("params"), parsed, mr1_acc)
    if ut is not None and not (isinstance(ut.get("errors"), list) and not ut["errors"]):
        p.append("ut errors: %s" % (("%d entries" % len(ut["errors"])) if isinstance(ut.get("errors"), list)
                                    else "MISSING"))
    for sec in ("fx3", "mf2"):
        if not isinstance(d.get(sec), dict) or not d[sec]:
            p.append("%s section missing or empty" % sec)
    cov = fb3.get("coverage")
    if not isinstance(cov, list) or not cov or any(isinstance(r, list) and len(r) > 1 and r[1] == "ERR" for r in cov):
        p.append("fb3.coverage missing, empty or carrying an observer ERR row")
    marked = sorted(k for k, v in d.items() if k != "eval" and err_re.search(json.dumps(v)))
    if marked:
        p.append("observer error marker (ERR_RE) in: %s" % marked)
    return p


def info_word(env: Env, src_line: dict, d: dict, full_diff) -> str:
    old = os.path.join(env.old_dir, os.path.basename(src_line["out"]))
    if not os.path.isfile(old):
        return "absent"
    try:
        with open(old, encoding="utf-8") as fh:
            ref = json.load(fh)
        return "equal" if not full_diff(d, ref, skip_mr1_list=False) else "differs"
    except Exception:
        return "unreadable"


def analyze(env: Env, head_arg=None, partial: bool = False) -> int:
    text: list = []

    def say(s=""):
        text.append(s)
        env.emit(s)

    try:
        srcs = source_lines(env)
        lines = build_lines(env)
        if not os.path.exists(env.queue):
            stop("%s does not exist (run write first)" % env.queue)
        qb = _lf(_read(env.queue))
        if qb != queue_bytes(lines):
            stop("%s differs from the re-derived queue" % env.queue)
        if not os.path.exists(env.freeze_launch):
            stop("%s is missing" % env.freeze_launch)
        with open(env.freeze_launch, encoding="utf-8") as fh:
            f0 = json.load(fh)
        if f0.get("queue_sha256") != _sha(qb):
            stop("the launch freeze's queue sha256 %s != the queue's %s" % (f0.get("queue_sha256"), _sha(qb)))
        if head_arg:
            full = env.resolve(head_arg)
            if full != f0.get("head"):
                stop("--head %s resolves to %s, the queue was frozen at %s" % (head_arg, full, f0.get("head")))
    except Stop as exc:
        env.emit("STOP: %s" % exc)
        return 3
    fb3_keys = tuple(_mod("_fb3_probe.py").FIX3B_KEYS)
    parse_value = _mod("_sd_probe.py")._parse_value
    ist = _mod("_ist3_analyze.py")
    head = f0.get("head")
    say("REFERENCES RE-MEASURED at the flip head %s (outputs/dispatch2_part1.txt 10.8 THE FLIP;" % head)
    say("  fix3b_part1.txt 19.14 (c) applied by analogy - 19.4 is CLOSED by 19.14 (a); bayesprep_part1.txt 4.4 and 7.1:")
    say("  the bpc arm, CUR at the shipped defaults, 33 cells). VALIDITY ONLY - no outcome value is read out.")
    say("QUEUE OK: %s, %d lines, sha256 %s (re-derived from %s)" % (env.queue, len(lines), _sha(qb), env.source))
    say("SHIPPED (launch freeze): %s" % _summary(f0.get("shipped") or {}))

    # ---- freeze
    global_fails, notes = [], []
    lp, ln_notes = launch_problems(f0, None)
    global_fails += ["launch record: %s" % x for x in lp]
    notes += ["launch record: %s" % x for x in ln_notes]
    tool_word = "analysis files NOT re-hashed (the analysis-time freeze failed)"
    try:
        f1 = env.freeze("complete", commit=head)
    except Stop as exc:
        f1 = None
        global_fails.append("the analysis-time freeze failed: %s" % exc)
    if f1 is not None:
        os.makedirs(env.out_dir, exist_ok=True)
        with open(env.freeze_complete, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(f1, fh, indent=1, sort_keys=True)
            fh.write("\n")
        cf, cn = compare_freeze(f0, f1)
        global_fails += cf
        notes += cn
        tool = tooling_changed(f0, f1)
        tool_word = ("analysis files CHANGED since launch: %s" % ", ".join(tool)) if tool else \
            "analysis files as launched"
    say("FREEZE: %d files hashed at launch; %d global failures, %d notes; %s"
        % (len(f0.get("sha") or {}), len(global_fails), len(notes), tool_word))

    # ---- per run
    runs, gv, missing = {}, {}, []
    for ln in lines:
        name = ln["name"]
        if not os.path.exists(ln["out"]):
            missing.append(name)
            continue
        try:
            with open(ln["out"], encoding="utf-8") as fh:
                d = json.load(fh)
            if not isinstance(d, dict):
                raise ValueError("not an object")
        except Exception:
            gv[name] = ["record unparseable"]
            continue
        try:
            with open(ln["out"] + ".argv", encoding="utf-8") as fh:
                sidecar = fh.read()
        except OSError:
            sidecar = None
        gv[name] = validate_record(ln, d, sidecar, f0, fb3_keys, parse_value, ist.ERR_RE, env.wt, ist._mr1_acc)
        runs[name] = d

    # ---- SW (+ the venv's python / mesa, reported by the same fresh interpreter)
    parsed = (f0.get("shipped") or {}).get("values") or {}
    vsm_of = {ln["name"]: line_sets(ln["argv"][ln["argv"].index("--") + 1:], parse_value).get("VICTIM_SPAWN_MODE")
              for ln in lines}
    sw = {}
    if runs:
        acc = env.accessors({n: (d.get("params") if isinstance(d.get("params"), dict) else {})
                             for n, d in runs.items()})
        if not isinstance(acc, dict) or "_error" in acc:
            global_fails.append("SW: %s" % (acc.get("_error") if isinstance(acc, dict) else "no answer"))
        else:
            for n in runs:
                got = acc.get(n) if isinstance(acc.get(n), dict) else {}
                want = want_accessors(parsed, vsm_of[n])
                sw[n] = [a for a, w in want.items() if not _same(got.get(a, _MISSING), w)]
            venv_py = acc.get("_python")
            if not isinstance(venv_py, str) or not venv_py:
                global_fails.append("V-pin: the accessor child reported no python version")
            else:
                for n, d in runs.items():
                    if d.get("python") != venv_py:
                        gv[n].append("python %r, not the venv's %s" % (d.get("python"), venv_py))
            if acc.get("_mesa") != PINNED_MESA:
                global_fails.append("V-pin: the venv's mesa is %r, not the pinned %s" % (acc.get("_mesa"), PINNED_MESA))
        pys = sorted({str(d.get("python")) for d in runs.values()})
        if len(pys) > 1:
            global_fails.append("V-pin: %d python versions across the runs: %s" % (len(pys), pys))
    # ---- INFO
    info = {}
    for src, ln in zip(srcs, lines):
        info[ln["name"]] = info_word(env, src, runs[ln["name"]], ist.full_diff) if ln["name"] in runs else "-"

    # ---- report
    n_v_fail = sum(1 for n in gv if gv[n])
    n_sw_fail = sum(1 for n in sw if sw[n])
    say("RUNS present %d / %d; V failures %d; SW failures %d; global failures %d"
        % (len(gv), len(lines), n_v_fail, n_sw_fail, len(global_fails)))
    say("")
    say("PER RUN (V = validity; SW = accessors rebuilt from the recorded params; INFO = vs the old bpc record of the")
    say("  same cell in this worktree's outputs/: equal / differs / absent - never gating)")
    hdr = "%-16s %-13s %6s | %-4s | %-4s | %s" % ("run", "old bpc", "seed", "V", "SW", "INFO")
    say(hdr)
    say("-" * (len(hdr) + 6))
    for src, ln in zip(srcs, lines):
        n = ln["name"]
        seed = ln["argv"][ln["argv"].index("--seed") + 1]
        v = "-" if n not in gv else ("ok" if not gv[n] else "FAIL")
        s = "-" if n not in sw else ("ok" if not sw[n] else "FAIL")
        say("%-16s %-13s %6s | %-4s | %-4s | %s" % (n, src["name"], seed, v, s, info[n]))
    say("")
    for g in global_fails:
        say("GLOBAL FAIL %s" % g)
    for n in gv:
        if gv[n]:
            say("V FAIL %s: %s" % (n, "; ".join(gv[n])))
    for n in sw:
        if sw[n]:
            say("SW FAIL %s: accessors not as shipped: %s" % (n, sw[n]))
    for x in notes:
        say("NOTE %s" % x)
    if missing:
        say("MISSING %d: %s" % (len(missing), ", ".join(missing)))
    counts = {w: sum(1 for x in info.values() if x == w) for w in ("equal", "differs", "absent", "unreadable")}
    say("INFO (not gating): vs the old bpc records: %s" % ", ".join("%s %d" % kv for kv in counts.items()))
    # INVALID beats INCOMPLETE: a definite failure of a present run, or a global failure, decides the set whatever is
    # still missing; only a set with nothing failing can be INCOMPLETE (--partial) or STOP (missing, no --partial)
    failed = bool(global_fails or n_v_fail or n_sw_fail)
    if missing and not failed and not partial:
        say("STOP: %d runs missing (nothing failed so far); use --partial for an interim report" % len(missing))
        return 3
    n_valid = sum(1 for n in gv if not gv[n] and n in sw and not sw[n])
    ok = (not missing and not failed and len(sw) == len(lines) and n_valid == len(lines))
    verdict = "VALID" if ok else ("INVALID" if failed or not missing else "INCOMPLETE")
    say("")
    say("REFERENCES (dispatch2_part1.txt 10.8; fix3b_part1.txt 19.14 (c) by analogy) at %s => %s: %d / %d records "
        "valid%s; %s" % (str(head)[:12], verdict, n_valid, len(lines),
                         (" (and %d global failures)" % len(global_fails)) if global_fails else "", tool_word))
    # ---- result file: the measurement round's new reference set ONLY on VALID
    if verdict == "VALID":
        ref = ["", "THE MEASUREMENT ROUND'S REFERENCE SET (bpc re-measured at %s; record path, LF sha256):" % head]
    else:
        ref = ["", "NOT A REFERENCE SET (verdict %s): the record paths and their LF sha256 at %s, for diagnosis only:"
               % (verdict, head)]
    for ln in lines:
        rel = os.path.relpath(ln["out"], env.wt).replace("\\", "/")
        ref.append("  %s  %s" % (rel, _sha(_lf(_read(ln["out"]))) if os.path.exists(ln["out"]) else "MISSING"))
    for r in ref:
        env.emit(r)
    with open(env.result, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(text + ref) + "\n")
    return 0 if verdict == "VALID" else (1 if verdict == "INVALID" else 3)


# ----------------------------------------------------------------------------------------------------------- selftest
SENTINELS = ("918273", "918274", "918275", "918276", "918277")
SENT_RE = re.compile(r"(?<![0-9A-Za-z])(%s)(?![0-9A-Za-z])" % "|".join(SENTINELS))
SYN_NOBS = 289          # the synthetic n_observations
SYN_UAVS = 3            # == the synthetic params NUM_AGENTS


def _synth_cfv(fb3_keys, overrides=None, extra_text="") -> str:
    vals = {"BATCH_SIZE": 300, "GLOBAL_PLANNER_MODE": 0, "VICTIM_SPAWN_MODE": 0, "SEARCHER_UNTUNED": 1,
            "SEARCHER_END_RECALL": 1, "FF_RELEASE_DETECTED_ONLY": 1, "SEARCHER_TARGETING_FIX": 1,
            "UAV_DOCKED_NOT_OBSTACLE": 1, "MR1_TRUTHINESS_FIX": 1, "NUMPY_SCALAR_FLAGS": 1, "SEARCHER_FP_U10_KMH": 20.0,
            "SEARCHER_FP_KAPPA": 1.0, "DISPATCH_STALL_STEPS": 10}
    vals.update(EXPECTED_SHIPPED)
    for i, k in enumerate(fb3_keys):
        vals.setdefault(k, 0.25 if i % 3 == 0 else i)
    vals.update(overrides or {})
    out = ["# synthetic common_fixed_variables.py (selftest)", "import os", "",
           "def helper():", "    DISPATCH_JOINT = 0  # function-local: not module level", "    return DISPATCH_JOINT", "",
           "if os.environ.get('NEVER_SET_DQREFS'):", "    CONDITIONAL_KEY = 1", "",
           "COMPUTED_KEY = int('3')"]
    out += ["%s = %r" % (k, v) for k, v in vals.items() if v is not _MISSING]
    return "\n".join(out) + "\n" + extra_text


def _synth_mr1_steps() -> list:
    """360 rows [t, literal per UAV, corrected per UAV] (literal 0 from the start, as the model's MR1 bug had it)."""
    return [[t, [0] * SYN_UAVS, [t % 3, (7 * t) % 5, 1]] for t in range(1, STEPS + 1)]


def _synth_record(line, f0, fb3_keys, parse_value, mr1_acc) -> dict:
    after = line["argv"][line["argv"].index("--") + 1:]
    sets = line_sets(after, parse_value)
    parsed = f0["shipped"]["values"]

    def val(flag):
        return after[after.index(flag) + 1]

    vsm = sets["VICTIM_SPAWN_MODE"]
    params = {"NUM_AGENTS": SYN_UAVS, "NUM_VICTIMS": 5, "NUM_FIREFIGHTERS": 3, "WIND_DIRECTION": val("--wind"),
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False, "NUM_FIRE_TRACKERS": None,
              "NUM_VICTIM_SEARCHERS": None, "UAV_LAUNCH_BATTERY_FRACTION": 1.0, "BATTERY_SCENARIO": 0}
    params.update(sets)
    fp = {k: {"raw": parsed[k], "eff": parsed[k]} for k in parsed if k.startswith("SEARCHER_FP_")}
    steps = _synth_mr1_steps()
    return {
        "probe": "sd_probe v1", "tag": line["name"], "repo": line["cwd"], "head": f0["head"],
        "src_sha": {n.replace("/", "\\"): f0["sha"][n][:16] for n in SRC_SHA_FILES},
        "python": "3.x", "mesa": "1.2.1", "scenario": val("--scenario"), "wind": val("--wind"),
        "seed": int(val("--seed")), "steps": STEPS, "argv": after, "params": params, "extra_params": dict(sets),
        "effective": {"global_planner_mode": parsed["GLOBAL_PLANNER_MODE"], "base_station_mode": 3,
                      "ff_exit_leg_mode": 2, "base_station_depots": 1, "base_station_return_mechanism": 1},
        "grid": [50, 50], "depots": None,
        "eval": {"rescued": int(SENTINELS[0]), "dead": int(SENTINELS[1]), "firefighter_deaths": int(SENTINELS[2]),
                 "detection_times": {"victim_0": int(SENTINELS[3])}},
        "terminal_step": int(SENTINELS[4]), "steps_done": STEPS, "crashed": None, "wall_s": 12.5,
        "inline_violations": {}, "inline_violation_counts": {}, "stdout_tags": {}, "warnings": [],
        "warning_count": 0, "stdout_sha": "0" * 64, "rows_uav": [], "rows_ff": [],
        "rows_vic": [[["victim_0", 1, 2, "rescued", "rescued", "ff_0", 1, 0, 0, int(SENTINELS[0])]]],
        "rows_dec": [], "rows_trig": [], "complete": True,
        "fx3": {"ev": {"1": [["F", [1, 2], True, "", 0, [0, 0, 0, 0]]]}, "ws": {}, "rtb": {}, "probe": "fx3_probe v3"},
        "mf2": {"uav": [], "fleet": [], "search": [], "gate": {}, "route": {}, "strips": {}, "probe": "mf2_probe v1"},
        "fb3": {"probe": "fb3_probe v1", "crn": {"on": True, "crn_draws": 4321}, "coverage": [[10, 0.12, None]],
                "spawn": {}, "stats": {}, "issued": [], "timing": {"belief": {"n": 1, "raw": [1.5]}},
                "switches": {k: (vsm if k == "VICTIM_SPAWN_MODE" else parsed[k]) for k in fb3_keys},
                "eff": {"searcher_targeting": parsed["SEARCHER_TARGETING"], "victim_spawn_mode": vsm,
                        "belief_built": False, "rw_stream_built": False, "spawn_stream_built": False},
                "inst": {"errors": [], "error_count": 0, "broken": False, "overhead": {"ms": 1.0},
                         "src": {"root": "x"}},
                "bp_switches": dict({"SEARCHER_TARGETING_FIX": {"raw": parsed["SEARCHER_TARGETING_FIX"], "eff": True},
                                     "UAV_DOCKED_NOT_OBSTACLE": {"raw": parsed["UAV_DOCKED_NOT_OBSTACLE"],
                                                                 "eff": True}}, **fp)},
        "mr": {"probe": "fb3 mr v2", "steps": [], "errors": [], "mr1_ids": [str(i) for i in range(SYN_UAVS)],
               "mr1_steps": steps, "n_observations": SYN_NOBS,
               "mr1_list": mr1_acc(SYN_UAVS, [x[2] for x in steps], float(SYN_NOBS)), "mr2_value": 0,
               "security_distance": 1},
        "ut": {"probe": "ut_probe v2", "phases": [], "rows": [], "sweep": {}, "corridor": {}, "errors": [],
               "rb": {}, "recall": {},
               "switch": {"raw": parsed["SEARCHER_UNTUNED"], "on": True, "recall_raw": parsed["SEARCHER_END_RECALL"],
                          "recall_on": True, "ffrel_raw": parsed["FF_RELEASE_DETECTED_ONLY"], "ffrel_on": True}},
    }


def selftest(scratch=None) -> int:
    if scratch:
        os.makedirs(scratch, exist_ok=True)
    root = os.path.abspath(tempfile.mkdtemp(prefix="dqrefs_st_", dir=scratch))
    tally = {"pass": 0, "fail": 0}
    failed = []

    def expect(name, cond):
        if cond:
            tally["pass"] += 1
        else:
            tally["fail"] += 1
            failed.append(name)
            print("  SELFTEST FAIL %s" % name)

    def stops(fn) -> bool:
        """True only for this tool's Stop (a SystemExit escaping is a failure of the case, not a crash)."""
        try:
            fn()
        except Stop:
            return True
        except SystemExit:
            return False
        return False

    fb3_keys = tuple(_mod("_fb3_probe.py").FIX3B_KEYS)
    parse_value = _mod("_sd_probe.py")._parse_value
    ist = _mod("_ist3_analyze.py")
    mr1_acc = ist._mr1_acc
    dq = _mod("_dq_queue.py")
    FAKE = "ab" * 20
    OTHER = "cd" * 20
    OLD_NS = (time.time_ns() // 10 ** 9 - 100000) * 10 ** 9     # "an untouched file": a whole second, long ago

    # ---------------------------------------------------------------- A: the source lines and the run lines
    env_a = Env(os.path.join(root, "wtA"))
    os.makedirs(env_a.out)
    for n in ("_bp_q_arms.jsonl", "_bp_q_all.jsonl", "_dq_seeds.txt"):
        shutil.copyfile(os.path.join(HERE, n), os.path.join(env_a.out, n))
    with open(env_a.probe, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# stub probe\n")
    lines = build_lines(env_a)
    src = source_lines(env_a)
    want_names = tuple(["dqrefcr1_" + k for k in KEYS] + ["dqrefcu1_" + k for k in KEYS] + ["dqrefcu2_D_W"])
    expect("A1 33 lines, names dqrefc<r|u><1|2>_<S>_<W> in the frozen order", tuple(x["name"] for x in lines)
           == want_names)
    ok4 = True
    for s, x in zip(src, lines):
        ch = [i for i, (a, b) in enumerate(zip(x["argv"], s["argv"])) if a != b]
        ok4 &= (len(ch) == 4 and ch[0] == 0 and x["argv"][0] == env_a.probe and x["cwd"] == env_a.wt
                and x["argv"][x["argv"].index("--repo") + 1] == env_a.wt
                and x["out"] == x["argv"][x["argv"].index("--out") + 1]
                and _same_path(os.path.dirname(x["out"]), env_a.out_dir)
                and x["argv"][x["argv"].index("--tag") + 1] == x["name"])
    expect("A2 each line = its bpc line with exactly argv[0] / --repo / --out / --tag replaced", ok4)
    seed_of = {x["name"]: x["argv"][x["argv"].index("--seed") + 1] for x in lines}
    seeds_ok = all(sorted(int(seed_of["dqrefc%s1_%s" % (p, k)]) for k in KEYS) == list(range(9601, 9617))
                   for p in "ru") and seed_of["dqrefcr1_A_N"] == "9601" and seed_of["dqrefcu1_D_W"] == "9616"
    expect("A3 seeds 9601-9616 per placement (rule) and 9636 for uniform set 2 D_W",
           seeds_ok and seed_of["dqrefcu2_D_W"] == "9636")
    vsm_ok = all(("VICTIM_SPAWN_MODE=%d" % (0 if x["name"][len(TAG_PREFIX)] == "r" else 1)) in x["argv"]
                 for x in lines) and sum(1 for x in lines if "VICTIM_SPAWN_MODE=1" in x["argv"]) == 17
    expect("A4 VICTIM_SPAWN_MODE 0 for ring, 1 for uniform", vsm_ok)
    expect("A5 queue bytes are LF only and parse back", b"\r" not in queue_bytes(lines)
           and [json.loads(t) for t in queue_bytes(lines).decode().splitlines()] == lines)
    raw_arms = _read(env_a.source)
    raw_all = _read(env_a.source_all)
    raw_seeds = _read(env_a.seeds)

    def mutate_arms(fn, which="arms"):
        path = env_a.source if which == "arms" else env_a.source_all
        rows = _jsonl(path)
        rows = fn(rows)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in rows))
        try:
            return stops(lambda: build_lines(env_a))
        finally:
            with open(env_a.source, "wb") as fh:
                fh.write(raw_arms)
            with open(env_a.source_all, "wb") as fh:
                fh.write(raw_all)

    def idx(rows, name):
        return [i for i, r in enumerate(rows) if r["name"] == name][0]

    def seed_change(rows):
        r = rows[idx(rows, "bpcr_B_S")]
        r["argv"][r["argv"].index("--seed") + 1] = "9699"
        return rows

    def extra_set(rows):
        r = rows[idx(rows, "bpcu_C_N")]
        i = r["argv"].index("--steps")
        r["argv"][i:i] = ["--set", "FF_APPROACH_PATH=0"]
        return rows

    def drop(rows):
        return [r for r in rows if r["name"] != "bpcu_A_W"]

    def dup(rows):
        return rows[:5] + [rows[4]] + rows[5:]

    def rename(rows):
        r = rows[idx(rows, "bpcu2_D_W")]
        r["name"] = "bpcr2_D_W"
        return rows

    def swap_vsm(rows):
        r = rows[idx(rows, "bpcr_D_E")]
        r["argv"][r["argv"].index("VICTIM_SPAWN_MODE=0")] = "VICTIM_SPAWN_MODE=1"
        return rows

    def no_instrument(rows):
        r = rows[idx(rows, "bpcr_A_N")]
        r["argv"].remove("--instrument")
        return rows

    def steps240(rows):
        r = rows[idx(rows, "bpcu_B_E")]
        r["argv"][r["argv"].index("--steps") + 1] = "240"
        return rows

    def wrong_out(rows):
        r = rows[idx(rows, "bpcr_C_W")]
        r["out"] = r["out"].replace("bpcr_C_W", "bpcr_C_E")
        return rows

    for nm, fn, which in (("seed changed", seed_change, "arms"), ("extra --set", extra_set, "arms"),
                          ("line removed", drop, "arms"), ("line duplicated", dup, "arms"),
                          ("bpcu2 renamed bpcr2", rename, "arms"), ("VICTIM_SPAWN_MODE swapped", swap_vsm, "arms"),
                          ("--instrument dropped", no_instrument, "arms"), ("steps 240", steps240, "arms"),
                          ("out path of another cell", wrong_out, "arms"),
                          ("_bp_q_all.jsonl differs", seed_change, "all")):
        expect("A6 STOP on a source deviation: %s" % nm, mutate_arms(fn, which))
    with open(env_a.seeds, "w", encoding="utf-8", newline="\n") as fh:
        doc = json.loads(raw_seeds)
        doc["set1"][3][3] = "9999"
        json.dump(doc, fh)
    expect("A7 STOP when _dq_seeds.txt set 1 breaks the rule", stops(lambda: build_lines(env_a)))
    with open(env_a.seeds, "wb") as fh:
        fh.write(raw_seeds)
    expect("A8 restored sources build again", len(build_lines(env_a)) == N_LINES)
    expect("A9 Env makes its worktree absolute (the children get it as repo and cwd; a relative --scratch broke them)",
           os.path.isabs(Env(os.path.join("rel_dqrefs_never_created", "wt")).wt))

    # ---------------------------------------------------------------- B: the shipped defaults parser
    good = parse_cfv(_synth_cfv(fb3_keys))
    expect("B1 the flipped synthetic file has no shipped problem and no dynamic binding",
           shipped_problems(good) == [] and good["dynamic"] == [])
    expect("B2 function-local / conditional / computed assignments are not module literals",
           good["values"].get("DISPATCH_JOINT") == 1 and "CONDITIONAL_KEY" in good["nonliteral"]
           and "COMPUTED_KEY" in good["nonliteral"] and "CONDITIONAL_KEY" not in good["values"])
    for nm, txt in (("DISPATCH_JOINT = 0", _synth_cfv(fb3_keys, {"DISPATCH_JOINT": 0})),
                    ("DISPATCH_REASSIGN = True (a bool)", _synth_cfv(fb3_keys, {"DISPATCH_REASSIGN": True})),
                    ("FF_FIX_STRANDING_GUARD = 0", _synth_cfv(fb3_keys, {"FF_FIX_STRANDING_GUARD": 0})),
                    ("SEARCHER_TARGETING = 3", _synth_cfv(fb3_keys, {"SEARCHER_TARGETING": 3})),
                    ("GLOBAL_PLANNER_MODE = 1", _synth_cfv(fb3_keys, {"GLOBAL_PLANNER_MODE": 1})),
                    ("DISPATCH_JOINT assigned twice", _synth_cfv(fb3_keys, extra_text="DISPATCH_JOINT = 1\n")),
                    ("FF_APPROACH_PATH non-literal", _synth_cfv(fb3_keys, {"FF_APPROACH_PATH": _MISSING},
                                                                extra_text="FF_APPROACH_PATH = int('1')\n")),
                    ("DISPATCH_REASSIGN conditional", _synth_cfv(fb3_keys, {"DISPATCH_REASSIGN": _MISSING},
                                                                 extra_text="if True:\n    DISPATCH_REASSIGN = 1\n")),
                    ("FF_RETREAT_KEEP_APPROACH missing", _synth_cfv(fb3_keys, {"FF_RETREAT_KEEP_APPROACH":
                                                                               _MISSING}))):
        expect("B3 shipped problem detected: %s" % nm, len(shipped_problems(parse_cfv(txt))) >= 1)
    # finding 5: EVERY binding form is a binding (each of these rebinds a flipped key at runtime; the unfixed parser
    # counted only Assign / AnnAssign / AugAssign and returned 0 problems for them)
    rebinds = (
        ("for-target", "for DISPATCH_JOINT in (0,):\n    pass\n"),
        ("import ... as K", "import os as DISPATCH_JOINT\n"),
        ("from ... import ... as K", "from os import sep as DISPATCH_REASSIGN\n"),
        ("walrus at module level", "_w = (DISPATCH_JOINT := 0)\n"),
        ("walrus in a module-level comprehension", "_c = [(FF_APPROACH_PATH := 0) for _ in (1,)]\n"),
        ("globals()[K] = 0", "globals()['DISPATCH_JOINT'] = 0\n"),
        ("vars()[K] = 0", "vars()['DISPATCH_JOINT'] = 0\n"),
        ("del K", "del DISPATCH_JOINT\n"),
        ("def K", "def DISPATCH_JOINT():\n    return 0\n"),
        ("class K", "class FF_FIX_STRANDING_GUARD:\n    pass\n"),
        ("with ... as K", "with open(__file__) as DISPATCH_JOINT:\n    pass\n"),
        ("except ... as K", "try:\n    pass\nexcept Exception as SEARCHER_TARGETING:\n    pass\n"),
        ("global K in a function called at import", "def _f():\n    global DISPATCH_JOINT\n    DISPATCH_JOINT = 0\n"
                                                     "_f()\n"),
        ("from x import *", "from os.path import *\n"),
        ("setattr on the module", "import sys as _s\nsetattr(_s.modules[__name__], 'DISPATCH_JOINT', 0)\n"),
        ("exec", "exec('DISPATCH_JOINT = 0')\n"),
        ("an attribute target (a self-import)", "import common_fixed_variables as _me\n_me.DISPATCH_JOINT = 0\n"),
        ("sys.modules / __dict__", "import sys as _s2\n_s2.modules[__name__].__dict__['FF_APPROACH_PATH'] = 0\n"),
        ("a match capture", "match 0:\n    case DISPATCH_JOINT:\n        pass\n"),
    )
    for nm, extra in rebinds:
        expect("B4 rebinding detected (finding 5): %s" % nm,
               len(shipped_problems(parse_cfv(_synth_cfv(fb3_keys, extra_text=extra)))) >= 1)
    local_only = ("def _g():\n    for DISPATCH_JOINT in (0,):\n        pass\n    import os as DISPATCH_REASSIGN\n"
                  "    return [(FF_APPROACH_PATH := 0) for _ in (1,)]\n")
    expect("B5 bindings inside a function body are not module bindings (positive control)",
           shipped_problems(parse_cfv(_synth_cfv(fb3_keys, extra_text=local_only))) == [])

    # ---------------------------------------------------------------- C: the freeze on a throwaway git index
    env_c = Env(os.path.join(root, "wtC"), git_cfg=["-c", "core.autocrlf=false", "-c", "core.safecrlf=false"])
    env_c.echo = False

    def path_c(rel):
        return os.path.join(env_c.wt, *rel.split("/"))

    def put(rel, text):
        """Write the file now (a new mtime)."""
        fp = path_c(rel)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    def put_old(rel, text):
        """Write the file as an UNTOUCHED file: its mtime is OLD_NS (the setup's and every restore's)."""
        put(rel, text)
        os.utime(path_c(rel), ns=(OLD_NS, OLD_NS))

    def git_c_run(*args):
        subprocess.run(["git", "-C", env_c.wt, "-c", "core.autocrlf=false"] + list(args), check=True,
                       capture_output=True)

    STUB = {}
    for rel in SRC_SHA_FILES:
        STUB[rel] = "# %s\n" % rel
    STUB["src_extension/planning/joint_dispatch.py"] = "# joint dispatch (not in src_sha)\n"
    STUB["common_fixed_variables.py"] = _synth_cfv(fb3_keys)
    STUB["src_extension/__init__.py"] = ""
    STUB["tests/test_x.py"] = "def test_x():\n    pass\n"
    STUB["README.md"] = "readme\n"
    for rel in CHAIN_FILES:
        STUB[rel] = "# stub %s\n" % rel
    for rel in TOOLING_FILES:
        if not rel.endswith((".jsonl", ".txt")):
            STUB[rel] = "# stub %s\n" % rel
    for rel, text in STUB.items():
        put_old(rel, text)
    for rel in TOOLING_FILES:
        if rel.endswith((".jsonl", ".txt")):
            shutil.copyfile(os.path.join(HERE, os.path.basename(rel)), path_c(rel))
            os.utime(path_c(rel), ns=(OLD_NS, OLD_NS))

    def restore(rel):
        put_old(rel, STUB[rel])

    subprocess.run(["git", "init", "-q", env_c.wt], check=True, capture_output=True)
    git_c_run("add", "-A")
    # "the commit": the throwaway index is never committed; a write-tree of it is the tree ls-tree reads
    tree_c = subprocess.run(["git", "-C", env_c.wt, "write-tree"], check=True, capture_output=True,
                            text=True).stdout.strip()
    # the throwaway index is never committed, so `git status` would call every entry "A " (added against no HEAD):
    # here status is the worktree-vs-index diff (git diff --name-status), in porcelain form, with the SAME pathspecs.
    # Every other git call (ls-files over the index, ls-files --others, ls-tree of the write-tree) is the real one.
    real_git = env_c.git

    def git_c(args):
        if args and args[0] == "status":
            raw = real_git(["diff", "--name-status", "-z", "--"] + list(args[args.index("--") + 1:]))
            toks = [t for t in raw.split("\0") if t]
            return "".join(" %s %s\n" % (toks[i][0], toks[i + 1]) for i in range(0, len(toks) - 1, 2))
        return real_git(args)

    env_c.git = git_c
    env_c.tree_ish = lambda commit: tree_c
    env_c.head = lambda: FAKE
    env_c.resolve = lambda s: FAKE if s and FAKE.startswith(s.lower()) else (OTHER if s and OTHER.startswith(s.lower())
                                                                            else None)
    env_c.tag_check = lambda ls: ([["fake tag check", str(len(ls)), "0", "found", "PASS"]], [])
    env_c.own_hits = lambda: []
    fr = env_c.freeze("launch")
    p0, n0 = launch_problems(fr, FAKE)
    expect("C1 a clean index: no launch problem", p0 == [] and fr["status"] == [])
    expect("C2 the freeze hashes run-loaded root / src_extension files and the chain",
           all(fr["sha"].get(r, "missing") != "missing" for r in ("agents.py", "src_extension/__init__.py",
                                                                   "outputs/_ut_probe.py", "outputs/_mf2_pool.py"))
           and fr["shipped"]["values"].get("DISPATCH_JOINT") == 1)
    expect("C2b the freeze records the freeze time, every mtime, the blob comparison at the commit (empty) and the "
           "runtime comparison (no mismatch, no error)",
           isinstance(fr.get("time_ns"), int) and fr["mtime_ns"].get("src_extension/planning/joint_dispatch.py")
           == OLD_NS and fr["blob_mismatch"] == [] and fr["blob_commit"] == FAKE
           and fr["runtime"].get("error") is None and fr["runtime"].get("mismatch") == []
           and fr["runtime"].get("n_keys", 0) > 10)
    expect("C3 --head mismatch is a problem", any("HEAD" in x for x in launch_problems(fr, OTHER)[0]))
    put("agents.py", "# modified\n")
    fr_ag = env_c.freeze("launch")
    expect("C4 a modified run-loaded file is a problem", any("run-loaded" in x for x in launch_problems(fr_ag, FAKE)[0]))
    expect("C5 compare: a run-loaded change FAILS", bool(compare_freeze(fr, fr_ag)[0]))
    restore("agents.py")
    put("tests/test_x.py", "def test_x():\n    assert True\n")
    fr_t = env_c.freeze("launch")
    pt, nt = launch_problems(fr_t, FAKE)
    ct = compare_freeze(fr, fr_t)
    expect("C6 a modified tests/ file is a NOTE, not a problem", pt == [] and nt != [] and ct[0] == [] and ct[1] != [])
    restore("tests/test_x.py")
    put("src_extension/new_mod.py", "X = 1\n")
    expect("C7 an untracked src_extension file is a problem",
           any("untracked" in x for x in launch_problems(env_c.freeze("launch"), FAKE)[0]))
    os.remove(path_c("src_extension/new_mod.py"))
    os.remove(path_c("outputs/_fb3_probe.py"))
    expect("C8 a deleted chain file is a problem", len(launch_problems(env_c.freeze("launch"), FAKE)[0]) >= 1)
    restore("outputs/_fb3_probe.py")
    f_eol = json.loads(json.dumps(fr))
    f_eol["sha"]["agents.py"] = "0" * 64
    ce = compare_freeze(fr, f_eol)
    expect("C9 an eol-only change (raw sha differs, LF sha equal) is a NOTE", ce[0] == [] and any("line endings" in x
                                                                                             for x in ce[1]))
    f_head = dict(fr, head=OTHER)
    ch = compare_freeze(fr, f_head)
    expect("C10 HEAD moved with run-loaded files unchanged is a NOTE", ch[0] == [] and any("HEAD moved" in x
                                                                                          for x in ch[1]))
    expect("C11 back to clean", launch_problems(env_c.freeze("launch"), FAKE)[0] == [])
    # finding 8: git status cannot see an assume-unchanged / skip-worktree file; the blob comparison can
    for flag, rel in (("--assume-unchanged", "agents.py"), ("--skip-worktree", "wildfire_model.py")):
        git_c_run("update-index", flag, rel)
        put(rel, "# changed behind a %s flag\n" % flag)
        fr_f = env_c.freeze("launch")
        pf = launch_problems(fr_f, FAKE)[0]
        expect("C12 %s: git status sees nothing (the gap) but the blob comparison is a problem" % flag,
               fr_f["status"] == [] and rel in fr_f["blob_mismatch"]
               and any("differ from their blob" in x for x in pf))
        expect("C12b %s: compare at analysis FAILS on the blob" % flag,
               any("differ from their blob" in x for x in compare_freeze(fr, fr_f)[0]))
        restore(rel)
        git_c_run("update-index", flag.replace("--", "--no-"), rel)
    lf_data = b"line one\nline two\n"
    expect("C13 a CRLF working copy of an LF blob is the same content; other content is not (positive / negative)",
           _blob_same(env_c, lf_data.replace(b"\n", b"\r\n"), _git_oid(lf_data))
           and not _blob_same(env_c, b"line one\nline 2\n", _git_oid(lf_data)))
    # finding 5 (runtime): a fresh interpreter imports the file; a rebinding the parse cannot see is a problem
    rt = env_c.cfv_runtime(["DISPATCH_JOINT", "FF_APPROACH_PATH", "SEARCHER_FP_KAPPA"])
    expect("C14 the runtime child imports the worktree's file (positive: the flipped values, type for type)",
           rt.get("values") == {"DISPATCH_JOINT": 1, "FF_APPROACH_PATH": 1, "SEARCHER_FP_KAPPA": 1.0}
           and _same_path(os.path.dirname(rt.get("file", "")), env_c.wt))
    put("_dqrefs_mutator.py", "import sys\nsys.modules['common_fixed_variables'].DISPATCH_JOINT = 0\n")
    put("common_fixed_variables.py", STUB["common_fixed_variables.py"] + "import _dqrefs_mutator\n")
    fr_m = env_c.freeze("launch")
    expect("C15 a helper module mutating the file at import: the parse sees nothing, the runtime comparison is a "
           "problem", shipped_problems(fr_m["shipped"]) == [] and fr_m["runtime"]["mismatch"] == ["DISPATCH_JOINT"]
           and any("at runtime" in x for x in launch_problems(fr_m, FAKE)[0])
           and any("at runtime" in x for x in compare_freeze(fr, fr_m)[0]))
    put("common_fixed_variables.py", STUB["common_fixed_variables.py"] + "raise RuntimeError('boom')\n")
    expect("C16 an import that raises is a problem (the runtime values are unknown)",
           any("runtime import" in x for x in launch_problems(env_c.freeze("launch"), FAKE)[0]))
    os.remove(path_c("_dqrefs_mutator.py"))
    restore("common_fixed_variables.py")
    # finding 4 (mtime-before-launch): a run-loaded file dated after the freeze time is a problem
    os.utime(path_c("agents.py"), ns=(OLD_NS, time.time_ns() + 3600 * 10 ** 9))
    expect("C17 a run-loaded file with an mtime later than the freeze time is a problem",
           any("mtime later" in x for x in launch_problems(env_c.freeze("launch"), FAKE)[0]))
    restore("agents.py")
    expect("C18 back to clean (blobs, mtimes, runtime)", launch_problems(env_c.freeze("launch"), FAKE)[0] == [])

    # ---------------------------------------------------------------- D: write and check
    def reset_written():
        for p in (env_c.queue, env_c.result):
            if os.path.exists(p):
                os.remove(p)
        if os.path.isdir(env_c.out_dir):
            shutil.rmtree(env_c.out_dir)

    def code_or_stop(fn):
        """The return code, or the Stop as a value (an unexpected refusal fails its case, it does not crash)."""
        try:
            return fn()
        except Stop as exc:
            print("  (selftest) unexpected STOP: %s" % str(exc)[:300])
            return "STOP"

    def run_check(head_arg):
        env_c.output = []
        code = code_or_stop(lambda: check(env_c, head_arg))
        return code, "\n".join(env_c.output)

    expect("D0 write refuses without --head", stops(lambda: write(env_c, None)))
    code, out = run_check(None)
    expect("D0b check without --head FAILS on an unfrozen queue (HEAD unverified; finding 4)",
           code == 1 and "FAIL no --head" in out)
    code, out = run_check(FAKE[:12])
    expect("D0c check --head FAKE on the clean tree PASSES (positive)", code == 0 and "PASS (write would freeze)" in out
           and not os.path.exists(env_c.queue))
    expect("D1 write freezes", code_or_stop(lambda: write(env_c, FAKE[:12])) == 0 and os.path.exists(env_c.queue)
           and os.path.exists(env_c.freeze_launch))
    qbytes = _read(env_c.queue)
    lines_c = build_lines(env_c)
    with open(env_c.freeze_launch, encoding="utf-8") as fh:
        f0c = json.load(fh)
    expect("D2 the queue: 33 LF lines == the rebuilt lines; the freeze records head and queue sha",
           qbytes == queue_bytes(lines_c) and b"\r" not in qbytes and f0c["head"] == FAKE
           and f0c["queue_sha256"] == _sha(qbytes) and f0c["n_lines"] == N_LINES)
    expect("D3 a second write is 'unchanged' (the launch state re-verified)",
           code_or_stop(lambda: write(env_c, FAKE)) == 0 and _read(env_c.queue) == qbytes)
    code, out = run_check(None)
    code2, _out2 = run_check(FAKE[:10])
    expect("D3b check on the frozen clean tree PASSES, with and without --head (positive)",
           code == 0 and code2 == 0 and "CHECK (frozen) => PASS" in out)
    code, out = run_check(OTHER[:12])
    expect("D3c check --head <another commit> on a frozen queue FAILS (finding 4)", code == 1 and "--head" in out)
    env_c.head = lambda: OTHER
    code, out = run_check(None)
    expect("D3d HEAD moved after the freeze: write STOPS and check FAILS (finding 4)",
           stops(lambda: write(env_c, FAKE)) and code == 1 and "not the frozen head" in out)
    env_c.head = lambda: FAKE
    put("wildfire_model.py", "# dirty after the freeze\n")
    code, out = run_check(None)
    expect("D3e a dirty run-loaded file after the freeze: write STOPS and check FAILS (finding 4)",
           stops(lambda: write(env_c, FAKE)) and code == 1)
    restore("wildfire_model.py")
    put("src_extension/planning/joint_dispatch.py", "# edited\n")
    put("src_extension/planning/joint_dispatch.py", STUB["src_extension/planning/joint_dispatch.py"])
    code, out = run_check(None)
    expect("D3f an edit reverted after the freeze (hashes equal, mtime not): check FAILS (finding 4)",
           code == 1 and "touched since launch" in out and stops(lambda: write(env_c, FAKE)))
    restore("src_extension/planning/joint_dispatch.py")
    code, out = run_check(None)
    expect("D3g restored: check PASSES again (positive)", code == 0)
    with open(env_c.queue, "ab") as fh:
        fh.write(b"\n")
    expect("D4 a tampered frozen queue STOPS", stops(lambda: write(env_c, FAKE)))
    with open(env_c.queue, "wb") as fh:
        fh.write(qbytes)
    expect("D5 a frozen queue at another head STOPS", stops(lambda: write(env_c, OTHER)))
    saved_freeze = _read(env_c.freeze_launch)
    reset_written()
    env_c.tag_check = lambda ls: ([["fake tag check", "33", "1", "found", "FAIL"]], ["TAG IN USE x"])
    expect("D6 a tag collision refuses and writes nothing", stops(lambda: write(env_c, FAKE))
           and not os.path.exists(env_c.queue) and not os.path.exists(env_c.out_dir))
    env_c.tag_check = lambda ls: ([["fake tag check", "33", "0", "NOT FOUND", "FAIL (BLIND)"]], [])
    expect("D7 a blind tag check refuses", stops(lambda: write(env_c, FAKE)) and not os.path.exists(env_c.queue))
    env_c.tag_check = lambda ls: ([["fake tag check", str(len(ls)), "0", "found", "PASS"]], [])
    env_c.own_hits = lambda: ["EXISTS somewhere/_dq_q_refs.jsonl"]
    expect("D8 an own path in use refuses", stops(lambda: write(env_c, FAKE)) and not os.path.exists(env_c.queue))
    env_c.own_hits = lambda: []
    os.makedirs(env_c.out_dir)
    expect("D9 an output directory without a queue refuses", stops(lambda: write(env_c, FAKE)))
    reset_written()
    put("common_fixed_variables.py", _synth_cfv(fb3_keys, {"DISPATCH_JOINT": 0}))
    git_c_run("add", "common_fixed_variables.py")
    expect("D10 shipped defaults that are not the flip refuse", stops(lambda: write(env_c, FAKE))
           and not os.path.exists(env_c.queue))
    reset_written()     # every refusal case leaves nothing behind, even when it fails (no state leaks onward)
    restore("common_fixed_variables.py")
    git_c_run("add", "common_fixed_variables.py")
    put("wildfire_model.py", "# dirty\n")
    expect("D11 a dirty run-loaded file refuses", stops(lambda: write(env_c, FAKE)))
    reset_written()
    restore("wildfire_model.py")
    git_c_run("update-index", "--assume-unchanged", "agents.py")
    put("agents.py", "# changed behind assume-unchanged\n")
    expect("D11b a run-loaded file changed behind assume-unchanged refuses (finding 8)",
           stops(lambda: write(env_c, FAKE)) and not os.path.exists(env_c.queue))
    reset_written()
    restore("agents.py")
    git_c_run("update-index", "--no-assume-unchanged", "agents.py")
    expect("D12 --head that is not HEAD refuses", stops(lambda: write(env_c, OTHER)))
    reset_written()
    os.rename(env_c.probe, env_c.probe + ".x")
    expect("D13 a missing probe refuses", stops(lambda: write(env_c, FAKE)))
    reset_written()
    os.rename(env_c.probe + ".x", env_c.probe)
    expect("D14 the clean tree writes again", code_or_stop(lambda: write(env_c, FAKE[:12])) == 0)
    skip = ("time", "time_ns")
    fa = {k: v for k, v in json.loads(_read(env_c.freeze_launch)).items() if k not in skip}
    fb = {k: v for k, v in json.loads(saved_freeze).items() if k not in skip}
    expect("D15 the re-written freeze equals the first (same tree; differing keys %s)"
           % sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k)), fa == fb)

    # ---------------------------------------------------------------- E: analyze on synthetic records
    with open(env_c.freeze_launch, encoding="utf-8") as fh:
        f0c = json.load(fh)
    parsed_c = f0c["shipped"]["values"]
    acc_state = {"mode": "ok"}

    def fake_acc(runs):
        if acc_state["mode"] == "error":
            return {"_error": "child failed"}
        out = {"_python": "3.x", "_mesa": "1.2.1" if acc_state["mode"] != "mesa_bad" else "1.3.0"}
        for n, params in runs.items():
            out[n] = want_accessors(parsed_c, params.get("VICTIM_SPAWN_MODE"))
            if acc_state["mode"] == "dj_off" and n == lines_c[3]["name"]:
                out[n]["dispatch_joint"] = False
            if acc_state["mode"] == "reassign_int" and n == lines_c[3]["name"]:
                out[n]["dispatch_reassign"] = 1
        return out

    env_c.accessors = fake_acc
    env_c.old_dir = os.path.join(root, "old")
    os.makedirs(env_c.old_dir)
    base = {}
    for ln in lines_c:
        d = _synth_record(ln, f0c, fb3_keys, parse_value, mr1_acc)
        data = json.dumps(d, separators=(",", ":")).encode("utf-8")
        base[ln["name"]] = data
        with open(ln["out"], "wb") as fh:
            fh.write(data)
        with open(ln["out"] + ".argv", "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"argv": ln["argv"], "cwd": ln["cwd"]}, sort_keys=True))

    def run_an(**kw):
        env_c.output = []
        code = analyze(env_c, **kw)
        return code, "\n".join(env_c.output)

    def verdict_line(out):
        return ([x for x in out.splitlines() if x.startswith("REFERENCES (")] or [""])[-1]

    code, out = run_an()
    expect("E1 33 valid synthetic records => VALID, exit 0", code == 0 and "=> VALID: 33 / 33" in out)
    res = _read(env_c.result).decode("utf-8")
    shas_ok = all(("outputs/_dq_refs/_sd_%s.json  %s" % (ln["name"], _sha(base[ln["name"]]))) in res
                  for ln in lines_c)
    expect("E2 the result file lists the 33 record paths with their LF sha256 under THE REFERENCE SET heading",
           shas_ok and res.count("outputs/_dq_refs/_sd_dqrefc") == N_LINES
           and "THE MEASUREMENT ROUND'S REFERENCE SET" in res and "NOT A REFERENCE SET" not in res)
    expect("E3 no outcome value printed or written (sentinels absent)", not SENT_RE.search(out)
           and not SENT_RE.search(res))
    expect("E4 the sentinel detector sees an outcome value (negative control)",
           bool(SENT_RE.search("rescued %s" % SENTINELS[0])) and not SENT_RE.search("sha a%sb" % SENTINELS[0]))
    expect("E5 INFO absent for every cell when no old record exists", out.count("| absent") == N_LINES)
    vl = verdict_line(out)
    expect("E5b the verdict line cites dispatch2_part1.txt 10.8 and 19.14 (c) by analogy, never 19.4 as an open "
           "rule, and says the analysis files are as launched (findings 11, 6)",
           "dispatch2_part1.txt 10.8" in vl and "19.14 (c) by analogy" in vl and "19.4 /" not in out
           and "analysis files as launched" in vl)
    target = lines_c[5]

    def mut(fn):
        d = json.loads(base[target["name"]])
        fn(d)
        with open(target["out"], "wb") as fh:
            fh.write(json.dumps(d).encode("utf-8"))
        try:
            return run_an()
        finally:
            with open(target["out"], "wb") as fh:
                fh.write(base[target["name"]])

    def setp(path, value):
        def fn(d):
            cur = d
            for k in path[:-1]:
                cur = cur[k]
            cur[path[-1]] = value
        return fn

    def popp(path):
        def fn(d):
            cur = d
            for k in path[:-1]:
                cur = cur[k]
            cur.pop(path[-1])
        return fn

    def mr1_literal(d):
        ms = d["mr"]["mr1_steps"]
        d["mr"]["mr1_list"] = mr1_acc(SYN_UAVS, [x[1] for x in ms], float(SYN_NOBS))

    def mr1_nudge(d):
        d["mr"]["mr1_list"][1] += 1e-9

    def steps_swap(d):
        ms = d["mr"]["mr1_steps"]
        ms[10], ms[11] = ms[11], ms[10]

    negatives = (
        ("complete False", setp(["complete"], False)),
        ("crashed", setp(["crashed"], {"step": 5, "type": "KeyError", "msg": "x", "tb": "y"})),
        ("steps_done 359", setp(["steps_done"], 359)),
        ("steps 240", setp(["steps"], 240)),
        ("CRN off", setp(["fb3", "crn", "on"], False)),
        ("CRN 0 draws", setp(["fb3", "crn", "crn_draws"], 0)),
        ("crn missing", setp(["fb3", "crn"], None)),
        ("head differs", setp(["head"], OTHER)),
        ("repo differs", setp(["repo"], r"E:\Projects\SAS")),
        ("tag differs", setp(["tag"], "dqrefcr1_X_Y")),
        ("seed differs", setp(["seed"], 1)),
        ("seed a string", setp(["seed"], "9606")),
        ("argv differs", lambda d: d["argv"].append("--uavs")),
        ("extra_params differ", setp(["extra_params", "GLOBAL_PLANNER_MODE"], 1)),
        ("params DISPATCH_JOINT 0 (an override)", setp(["params", "DISPATCH_JOINT"], 0)),
        ("params FF_APPROACH_PATH 1 (set explicitly)", setp(["params", "FF_APPROACH_PATH"], 1)),
        ("params unknown key", setp(["params", "FOO_SWITCH"], 1)),
        ("params GLOBAL_PLANNER_MODE 1", setp(["params", "GLOBAL_PLANNER_MODE"], 1)),
        ("params WIND_DIRECTION", setp(["params", "WIND_DIRECTION"], "nowhere")),
        ("params missing", setp(["params"], None)),
        ("fb3.switches SEARCHER_TARGETING 3", setp(["fb3", "switches", "SEARCHER_TARGETING"], 3)),
        ("fb3.switches VICTIM_SPAWN_MODE wrong", setp(["fb3", "switches", "VICTIM_SPAWN_MODE"], 7)),
        ("fb3.switches a key missing", lambda d: d["fb3"]["switches"].pop(fb3_keys[1])),
        ("fb3.eff searcher_targeting 3", setp(["fb3", "eff", "searcher_targeting"], 3)),
        ("fb3.eff victim_spawn_mode wrong", setp(["fb3", "eff", "victim_spawn_mode"], 9)),
        ("bp_switches missing", setp(["fb3", "bp_switches"], None)),
        ("bp_switches SEARCHER_TARGETING_FIX raw 0", setp(["fb3", "bp_switches", "SEARCHER_TARGETING_FIX", "raw"], 0)),
        ("bp_switches UAV_DOCKED_NOT_OBSTACLE eff False",
         setp(["fb3", "bp_switches", "UAV_DOCKED_NOT_OBSTACLE", "eff"], False)),
        ("bp_switches FP raw changed", setp(["fb3", "bp_switches", "SEARCHER_FP_KAPPA", "raw"], 3.0)),
        ("bp_switches FP key extra", setp(["fb3", "bp_switches", "SEARCHER_FP_NEW"], {"raw": 1, "eff": 1})),
        ("ut.switch raw 0", setp(["ut", "switch", "raw"], 0)),
        ("ut.switch recall_on False", setp(["ut", "switch", "recall_on"], False)),
        ("ut missing", setp(["ut"], None)),
        ("effective.global_planner_mode 1", setp(["effective", "global_planner_mode"], 1)),
        ("fb3.inst error_count 1", setp(["fb3", "inst", "error_count"], 1)),
        ("fb3.inst broken", setp(["fb3", "inst", "broken"], True)),
        ("fb3.inst errors listed", setp(["fb3", "inst", "errors"], ["boom"])),
        ("fb3.inst missing", setp(["fb3", "inst"], None)),
        ("mr.errors", setp(["mr", "errors"], ["boom"])),
        ("mr missing", setp(["mr"], None)),
        ("ut.errors", setp(["ut", "errors"], ["boom"])),
        ("fx3 ERR marker", setp(["fx3", "ws"], {"7": {"ERR": "KeyError()"}})),
        ("fx3 ERR blocked_next", setp(["fx3", "ev"], {"3": [["F", [1, 1], True, "", 0, "ERR KeyError()"]]})),
        ("mf2 HOOK_ERR", setp(["mf2", "strips"], {"HOOK_ERR KeyError()": 1})),
        ("mf2 missing", setp(["mf2"], None)),
        ("fb3.coverage ERR row", setp(["fb3", "coverage"], [[10, "ERR", "x"]])),
        ("src_sha mismatch", setp(["src_sha", "agents.py"], "0" * 16)),
        ("src_sha missing", setp(["src_sha"], {})),
        # finding 1: a MISSING key is never read as a pass; an ERR marker anywhere but eval is a failure
        ("F1 crashed key missing", popp(["crashed"])),
        ("F1 fb3.inst errors key missing", popp(["fb3", "inst", "errors"])),
        ("F1 fb3.inst error_count False (not the int 0)", setp(["fb3", "inst", "error_count"], False)),
        ("F1 fb3.inst error_count key missing", popp(["fb3", "inst", "error_count"])),
        ("F1 mr.errors key missing", popp(["mr", "errors"])),
        ("F1 ut.errors key missing", popp(["ut", "errors"])),
        ("F1 fx3 an empty section", setp(["fx3"], {})),
        ("F1 mf2 an empty section", setp(["mf2"], {})),
        ("F1 fb3.coverage an empty list", setp(["fb3", "coverage"], [])),
        ("F1 effective.base_station_mode 'ERR KeyError'", setp(["effective", "base_station_mode"], "ERR KeyError")),
        ("F1 effective.ff_exit_leg_mode 'ABSENT'", setp(["effective", "ff_exit_leg_mode"], "ABSENT")),
        ("F1 effective accessor key missing", popp(["effective", "base_station_depots"])),
        ("F1 HOOK_ERR marker in fb3.stats", setp(["fb3", "stats"], {"HOOK_ERR KeyError()": 1})),
        ("F1 HOOK_ERR marker in ut.rows", setp(["ut", "rows"], [[5, "HOOK_ERR KeyError()"]])),
        ("F1 an ERR marker in rows_dec", setp(["rows_dec"], [[5, "ERR ValueError()"]])),
        # finding 9: src_sha must hold all 11 _sd_probe keys
        ("F9 src_sha one of the 11 keys missing (a subset)", popp(["src_sha",
                                                                   "src_extension\\planning\\rescue_planner.py"])),
        # finding 10: the pinned runtime and the MR1 record
        ("F10 mesa 1.2.2", setp(["mesa"], "1.2.2")),
        ("F10 python differs from the venv's", setp(["python"], "3.y")),
        ("F10 record probe sd_probe v2", setp(["probe"], "sd_probe v2")),
        ("F10 fx3 probe v4", setp(["fx3", "probe"], "fx3_probe v4")),
        ("F10 mf2 probe v2", setp(["mf2", "probe"], "mf2_probe v2")),
        ("F10 fb3 probe v2", setp(["fb3", "probe"], "fb3_probe v2")),
        ("F10 mr probe v3", setp(["mr", "probe"], "fb3 mr v3")),
        ("F10 ut probe v3", setp(["ut", "probe"], "ut_probe v3")),
        ("F10 mr1_steps 359 rows", lambda d: d["mr"]["mr1_steps"].pop()),
        ("F10 mr1_steps a row with 2 UAV counts", setp(["mr", "mr1_steps", 7, 2], [1, 1])),
        ("F10 mr1_steps rows out of step order", steps_swap),
        ("F10 n_observations missing", popp(["mr", "n_observations"])),
        ("F10 mr1_ids one short", setp(["mr", "mr1_ids"], ["0", "1"])),
        ("F10 NUM_AGENTS 4 (UAV count != the recorded team)", setp(["params", "NUM_AGENTS"], 4)),
        ("F10 mr1_list = the LITERAL accumulation (shipped MR1_TRUTHINESS_FIX 1)", mr1_literal),
        ("F10 mr1_list off by 1e-9", mr1_nudge),
    )
    for nm, fn in negatives:
        code, out = mut(fn)
        expect("E6 INVALID on one record: %s" % nm, code == 1 and ("V FAIL %s" % target["name"]) in out
               and "=> INVALID" in out and not SENT_RE.search(out))
    code, out = mut(setp(["eval", "note"], "ERR inside eval"))
    expect("E6b eval is never scanned: an ERR-looking string there leaves the run valid (positive control)",
           code == 0 and "=> VALID: 33 / 33" in out)
    probe_src_ok = all(('"probe": "%s"' % ver) in _read(os.path.join(HERE, srcf)).decode("utf-8")
                       for _sec, ver, srcf in PROBE_VERSIONS)
    expect("E6c the pinned probe versions are the strings the frozen chain writes (positive control)", probe_src_ok)
    with open(target["out"], "wb") as fh:
        fh.write(b"{not json")
    code, out = run_an()
    expect("E7 an unparseable record is INVALID", code == 1 and "record unparseable" in out)
    with open(target["out"], "wb") as fh:
        fh.write(base[target["name"]])
    side = _read(target["out"] + ".argv")
    with open(target["out"] + ".argv", "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": target["argv"][:-1], "cwd": target["cwd"]}, sort_keys=True))
    expect("E8 a sidecar that differs is INVALID", run_an()[0] == 1)
    os.remove(target["out"] + ".argv")
    expect("E9 a missing sidecar is INVALID", run_an()[0] == 1)
    with open(target["out"] + ".argv", "wb") as fh:
        fh.write(side)
    for mode, nm in (("dj_off", "dispatch_joint False"), ("reassign_int", "dispatch_reassign 1 (not True)"),
                     ("error", "the accessor child fails"), ("mesa_bad", "the venv's mesa is not 1.2.1 (finding 10)")):
        acc_state["mode"] = mode
        code, out = run_an()
        expect("E10 SW / pin: %s => INVALID" % nm, code == 1 and ("SW FAIL" in out or "GLOBAL FAIL" in out))
    acc_state["mode"] = "ok"
    os.rename(target["out"], target["out"] + ".away")
    code, out = run_an()
    expect("E11 a missing record STOPS (nothing failed) without --partial", code == 3 and "STOP" in out)
    code, out = run_an(partial=True)
    res = _read(env_c.result).decode()
    expect("E12 with --partial (nothing failed) the verdict is INCOMPLETE", code == 3 and "=> INCOMPLETE" in out
           and "MISSING" in res)
    expect("E12b an INCOMPLETE result file is headed NOT A REFERENCE SET (finding 3)",
           "NOT A REFERENCE SET (verdict INCOMPLETE)" in res and "THE MEASUREMENT ROUND'S REFERENCE SET" not in res)
    # finding 2: INVALID beats INCOMPLETE - a definite failure is not hidden by a missing run
    other = lines_c[9]
    d_bad = json.loads(base[other["name"]])
    d_bad["complete"] = False
    with open(other["out"], "wb") as fh:
        fh.write(json.dumps(d_bad).encode("utf-8"))
    code, out = run_an(partial=True)
    res = _read(env_c.result).decode()
    expect("E12c one V FAIL + one missing, --partial => INVALID exit 1, not INCOMPLETE (finding 2)",
           code == 1 and "=> INVALID" in out and "=> INCOMPLETE" not in out)
    expect("E12d that INVALID result file is headed NOT A REFERENCE SET (finding 3)",
           "NOT A REFERENCE SET (verdict INVALID)" in res and "THE MEASUREMENT ROUND'S REFERENCE SET" not in res)
    code, out = run_an()
    expect("E12e one V FAIL + one missing, no --partial => INVALID exit 1, not a STOP (finding 2)",
           code == 1 and "=> INVALID" in out)
    with open(other["out"], "wb") as fh:
        fh.write(base[other["name"]])
    acc_state["mode"] = "error"
    code, out = run_an(partial=True)
    expect("E12f a global failure + one missing, --partial => INVALID (finding 2)", code == 1 and "=> INVALID" in out)
    acc_state["mode"] = "ok"
    os.rename(target["out"] + ".away", target["out"])
    # the freeze re-hash
    put("agents.py", "# changed after launch\n")
    expect("E13 a run-loaded file changed since launch => INVALID", run_an()[0] == 1)
    restore("agents.py")
    put("tests/test_x.py", "def test_x():\n    assert 1\n")
    code, out = run_an()
    expect("E14 a tests/ change is a NOTE and the verdict stays VALID", code == 0 and "NOTE" in out)
    restore("tests/test_x.py")
    env_c.head = lambda: OTHER
    code, out = run_an()
    expect("E15 HEAD moved (run-loaded unchanged) is a NOTE, VALID", code == 0 and "HEAD moved" in out)
    env_c.head = lambda: FAKE
    put("common_fixed_variables.py", _synth_cfv(fb3_keys, {"SEARCHER_FP_KAPPA": 3.0}))
    git_c_run("add", "common_fixed_variables.py")
    expect("E16 the parsed shipped defaults changed since launch => INVALID", run_an()[0] == 1)
    restore("common_fixed_variables.py")
    git_c_run("add", "common_fixed_variables.py")
    # finding 4: an edit made after write and reverted before analyze (every hash equal again; not in src_sha)
    put("src_extension/planning/joint_dispatch.py", "# edited after launch\n")
    put("src_extension/planning/joint_dispatch.py", STUB["src_extension/planning/joint_dispatch.py"])
    code, out = run_an()
    expect("E16b an edit reverted between write and analyze => INVALID by the mtime (finding 4)",
           code == 1 and "touched since launch" in out)
    restore("src_extension/planning/joint_dispatch.py")
    expect("E16c restored mtime => VALID again (positive)", run_an()[0] == 0)
    # finding 8 at analysis: a change behind assume-unchanged
    git_c_run("update-index", "--assume-unchanged", "agents.py")
    put("agents.py", "# changed behind assume-unchanged after launch\n")
    os.utime(path_c("agents.py"), ns=(OLD_NS, OLD_NS))
    code, out = run_an()
    expect("E16d a run-loaded file changed behind assume-unchanged (mtime restored) => INVALID by the blob "
           "(finding 8)", code == 1 and "differ from their blob" in out)
    restore("agents.py")
    git_c_run("update-index", "--no-assume-unchanged", "agents.py")
    # finding 6: the analysis files are frozen too
    for rel in ("outputs/_ist3_analyze.py", "outputs/_dq_refs.py"):
        put(rel, "# weakened after launch\n")
        code, out = run_an()
        expect("E16e an analysis file (%s) changed since launch => INVALID, named in the verdict line (finding 6)"
               % rel, code == 1 and ("analysis files CHANGED since launch: %s" % rel) in verdict_line(out))
        restore(rel)
    put("outputs/_ist3_analyze.py", STUB["outputs/_ist3_analyze.py"].replace("\n", "\r\n"))
    code, out = run_an()
    expect("E16f an eol-only change of an analysis file is a NOTE, VALID (positive)",
           code == 0 and "analysis files as launched" in verdict_line(out) and "line endings" in out)
    restore("outputs/_ist3_analyze.py")
    fz = _read(env_c.freeze_launch)
    f_bad = json.loads(fz)
    f_bad["status"] = [" M agents.py"]
    with open(env_c.freeze_launch, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(f_bad, fh)
    expect("E17 a launch record that was not clean => INVALID", run_an()[0] == 1)
    f_bad = json.loads(fz)
    f_bad.pop("mtime_ns")
    with open(env_c.freeze_launch, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(f_bad, fh)
    expect("E17b a launch record without mtimes (an older format) => INVALID", run_an()[0] == 1)
    f_bad = json.loads(fz)
    f_bad["queue_sha256"] = "0" * 64
    with open(env_c.freeze_launch, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(f_bad, fh)
    expect("E18 the launch freeze's queue sha differs => STOP", run_an()[0] == 3)
    with open(env_c.freeze_launch, "wb") as fh:
        fh.write(fz)
    expect("E19 --head that is not the frozen head => STOP", run_an(head_arg=OTHER[:10])[0] == 3)
    expect("E20 --head equal to the frozen head => VALID", run_an(head_arg=FAKE[:10])[0] == 0)
    qb = _read(env_c.queue)
    with open(env_c.queue, "wb") as fh:
        fh.write(qb.replace(b"dqrefcr1_A_E\"", b"dqrefcr1_A_X\"", 1))
    expect("E21 a tampered queue => STOP", run_an()[0] == 3)
    with open(env_c.queue, "wb") as fh:
        fh.write(qb.replace(b"\n", b"\r\n"))
    expect("E22 a CRLF copy of the frozen queue (git eol) is still the frozen queue", run_an()[0] == 0)
    with open(env_c.queue, "wb") as fh:
        fh.write(qb)
    # INFO
    old0 = json.loads(base[lines_c[0]["name"]])
    old0.update(tag="bpcr_A_E", repo=BP_WT, head=OTHER, argv=["x"], wall_s=99.0, python="3.y")
    old0["fb3"]["timing"] = {"belief": {"n": 2}}
    old0["fb3"]["inst"]["overhead"] = {"ms": 7.0}
    with open(os.path.join(env_c.old_dir, os.path.basename(src[0]["out"])), "w", encoding="utf-8") as fh:
        json.dump(old0, fh)
    old1 = json.loads(base[lines_c[1]["name"]])
    old1["eval"]["rescued"] = 3
    with open(os.path.join(env_c.old_dir, os.path.basename(src[1]["out"])), "w", encoding="utf-8") as fh:
        json.dump(old1, fh)
    code, out = run_an()
    rows = {r.split()[0]: r for r in out.splitlines() if r.startswith(TAG_PREFIX)}
    expect("E23 INFO: equal for a label / wall-clock-only difference", rows[lines_c[0]["name"]].endswith("| equal"))
    expect("E24 INFO: differs for a value difference, and INFO never gates", rows[lines_c[1]["name"]].endswith(
        "| differs") and code == 0 and "=> VALID" in out and not SENT_RE.search(out))
    expect("E25 INFO: absent where no old record exists", rows[lines_c[2]["name"]].endswith("| absent"))
    # a CRLF record: the LF sha256 is the LF content's
    k = lines_c[7]
    with open(k["out"], "wb") as fh:
        fh.write(base[k["name"]] + b"\r\n")
    code, out = run_an()
    res = _read(env_c.result).decode()
    expect("E26 a CRLF-terminated record: valid, listed with the LF sha256", code == 0
           and _sha(base[k["name"]] + b"\n") in res and _sha(base[k["name"]] + b"\r\n") not in res)
    with open(k["out"], "wb") as fh:
        fh.write(base[k["name"]])

    # ---------------------------------------------------------------- F: the imported tag check's matcher
    rx = dq.tag_regex([ln["name"] for ln in lines_c])
    expect("F1 the tag matcher finds a run name as a whole token", bool(rx.search("_sd_dqrefcr1_A_E.json"))
           and bool(rx.search("_sd_DQREFCU2_D_W.stdout.txt")))
    expect("F2 the tag matcher ignores a longer token", not rx.search("_sd_dqrefcr1_A_EX.json")
           and not rx.search("_sd_xdqrefcr1_A_E.json") and not rx.search("_sd_dqrefcr12_A_E.json"))
    own = dq.own_paths(lines_c[0])
    expect("F3 the own paths cover the record, .argv, .poollog and .stdout.txt",
           lines_c[0]["out"] in own and lines_c[0]["out"] + ".argv" in own and lines_c[0]["out"] + ".poollog" in own
           and lines_c[0]["out"][:-5] + ".stdout.txt" in own)
    want_t = want_accessors({"DISPATCH_JOINT": 1, "SEARCHER_TARGETING": 0, "MR1_TRUTHINESS_FIX": 1,
                             "GLOBAL_PLANNER_MODE": 0}, 1)
    expect("F4 want_accessors: the five flipped accessors True, ints as ints, the line's spawn mode",
           all(want_t[a] is True for a in FLIP_ACCESSORS) and want_t["searcher_targeting"] == 0
           and want_t["victim_spawn_mode"] == 1 and want_t["mr1_truthiness_fix"] is True)

    # ---------------------------------------------------------------- G: a refusal inside outputs/_dq_queue.py
    # (finding 7) its stop() raises SystemExit; the tool turns it into its own Stop, so write exits 2, not 1
    def sys_exit(*_a, **_k):
        raise SystemExit("STOP: git failed (selftest fake)")

    fake_dq = types.SimpleNamespace(tag_check=sys_exit, locations=sys_exit, _listing=sys_exit, _git_paths=sys_exit)
    saved_dq = _MODS.get("_dq_queue.py")
    _MODS["_dq_queue.py"] = fake_dq
    try:
        def code_of(fn):
            try:
                return _run_cmd("write", fn)
            except SystemExit:
                return "SystemExit escaped"
        expect("G1 a SystemExit in _dq_queue.tag_check is a Stop: exit 2",
               code_of(lambda: Env.tag_check(env_c, lines_c)) == 2)
        expect("G2 a SystemExit in _dq_queue.locations (own-path check) is a Stop: exit 2",
               code_of(lambda: Env.own_hits(env_c)) == 2)
        reset_written()
        env_c.tag_check = lambda ls: Env.tag_check(env_c, ls)
        expect("G3 write reaching the real tag check: a _dq_queue refusal exits 2 and writes nothing",
               code_of(lambda: write(env_c, FAKE)) == 2 and not os.path.exists(env_c.queue)
               and not os.path.exists(env_c.out_dir))
    finally:
        if saved_dq is None:
            _MODS.pop("_dq_queue.py", None)
        else:
            _MODS["_dq_queue.py"] = saved_dq

    print("SELFTEST %d passed / %d failed%s" % (tally["pass"], tally["fail"],
                                                (": " + ", ".join(failed)) if failed else ""))
    if not tally["fail"]:
        _rm_tree(root)
        if os.path.exists(root):
            print("note: the self-test scratch %s could not be removed" % root)
    else:
        print("scratch kept: %s" % root)
    return 0 if not tally["fail"] else 1


def _rm_tree(path: str) -> None:
    """Remove the self-test's own temp tree; git writes its object files read-only on Windows."""
    def retry(func, p, _exc):
        try:
            os.chmod(p, 0o666)
            func(p)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


# ------------------------------------------------------------------------------------------------------------- main
def _opt(flag: str):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 >= len(sys.argv):
            stop("%s needs a value" % flag)
        return sys.argv[i + 1]
    return None


def _run_cmd(cmd: str, fn) -> int:
    """A command's exit code: a Stop (this tool's, or outputs/_dq_queue.py's SystemExit turned into one by _dq_call) is
    2 (write refused / check stopped), 3 for analyze."""
    try:
        return fn()
    except Stop as exc:
        print("STOP: %s" % exc)
        return 3 if cmd == "analyze" else 2


def main() -> int:
    sys.stdout.reconfigure(newline="\n")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "_accessors":
        return _accessors_child()
    if cmd == "_cfv_values":
        return _cfv_child()

    def run() -> int:
        if cmd == "selftest":
            return selftest(_opt("--scratch"))
        here = Env()
        if not _same_path(HERE, here.out):
            stop("this tool must live in %s (it is in %s): the queue paths are absolute" % (here.out, HERE))
        if cmd == "write":
            return write(here, _opt("--head"))
        if cmd == "check":
            return check(here, _opt("--head"))
        if cmd == "analyze":
            return analyze(here, _opt("--head"), "--partial" in sys.argv[2:])
        print(__doc__)
        return 2

    return _run_cmd(cmd, run)


if __name__ == "__main__":
    raise SystemExit(main())
