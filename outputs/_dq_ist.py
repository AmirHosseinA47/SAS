"""Dispatch round 2, THE FLIP: the isTrue 19.12(c) check (outputs/dispatch2_report.txt section 10: "the is-True round's
19.12(c) identity check (triggered because dispatch ships ON)"). A port of outputs/_mvg_ist.py (the MVG round's check,
record outputs/_mvg_ist_result.txt) to the dispatch worktree.

WHAT 19.12(c) REQUIRES (outputs/fix3b_part1.txt 19.12 (c): "if dispatch ships ANY switch on, run a small identity check
at the merged head"), at the merged head - here the dispatch flip commit, given to write as --head SHA and recorded in
the launch freeze record (later commits change only outputs/ and documentation, so every run-loaded file is identical):
  (1) the isTrue reach census (outputs/_ist3_reach.py, the record-only wrapper around outputs/_ut_probe.py that adds
      <out>.reach.json): no numpy value at any F-2 site in the shipped runs;
  (2) shipped vs both isTrue switches 0 (MR1_TRUTHINESS_FIX=0, NUMPY_SCALAR_FLAGS=0) on the 12 configurations of the
      isTrue K arm (outputs/_ist3_configs.json, the configurations flagged k_arm), 24 runs: every recorded field equal
      except mr.mr1_list, which must equal the LITERAL accumulation at 0 and the CORRECTED one when shipped
      (outputs/isTrue_report.txt 4.4: G-A, G-K, G1-a, G1-b).
  Any difference STOPS the measurement round until it is explained.

usage (any cwd, with E:/Projects/SAS/.venv/Scripts/python.exe -B, PYTHONDONTWRITEBYTECODE=1):
  python outputs/_dq_ist.py write --head SHA    writes the FROZEN queue outputs/_dq_q_ist.jsonl (24 lines, for
                                                outputs/_mf2_pool.py) and the launch freeze record
                                                outputs/_dq_ist/_freeze_launch.json (flip_head = SHA resolved to the
                                                full sha, head_arg = SHA as given); refuses to re-write a different
                                                queue or the frozen one under another --head; refuses on a tag
                                                collision, a tree that is not the clean commit SHA, or defaults that
                                                are not the flip's
  python outputs/_dq_ist.py analyze [--head SHA] [--partial]
                                                validity, reach census, S vs K, G1-a / G1-b; prints a per-configuration
                                                table and "19.12(c) => PASS/FAIL"; writes the same text to
                                                outputs/_dq_ist_result.txt (and outputs/_dq_ist/_freeze_complete.json).
                                                The head is the launch record's flip_head; --head, if given, must be a
                                                7-40 hex prefix of it
  python outputs/_dq_ist.py selftest [--tmp DIR]  known answers on synthetic records, fake inputs and a scratch git
                                                repository it creates, in process (no run; git only on that scratch
                                                repository; no listing outside a temp dir under DIR, removed after);
                                                exit 0 iff every case passes
EXIT CODES: write 0 written or unchanged, 2 STOP; analyze 0 PASS, 1 FAIL or INCOMPLETE, 3 STOP. A STOP raised inside a
  helper (a SystemExit "STOP: ..." from k_configs / build_lines, outputs/_dq_queue.py stop()) or an unexpected exception
  exits 2 (write) / 3 (analyze), never 1: an analyze STOP never reads as a FAIL.
PATHS: every path (queue, outputs, result, references, the loaded outputs/ modules) is built from WT, never from
  __file__; write / analyze refuse to run unless this script is WT/outputs/_dq_ist.py.
ORCHESTRATION RULE: NO COMMIT in this worktree between `write` and the end of the 24th run. write needs HEAD ==
  flip_head, every run records the HEAD it ran at and G-V requires it to equal flip_head, so a commit made while the
  runs are pending (even a record-only commit) fails G-V for every later run. Commit records only after the last run.

ARMS (each run through E:/Projects/SAS_wt/dispatch/outputs/_ist3_reach.py with --repo E:/Projects/SAS_wt/dispatch):
  S  the configuration's own --set list = the isTrue F12 line: FF_APPROACH_PATH, FF_RETREAT_KEEP_APPROACH,
     FF_FIX_STRANDING_GUARD, MR1_TRUTHINESS_FIX, NUMPY_SCALAR_FLAGS, DISPATCH_JOINT and DISPATCH_REASSIGN at their
     shipped defaults (1; set by nothing)
  K  + --set MR1_TRUTHINESS_FIX=0 --set NUMPY_SCALAR_FLAGS=0 = the isTrue K line (dispatch and movement still shipped)
THE RUN LINE: the FROZEN isTrue line (outputs/_ist3_q.jsonl: ist3_F12_<cid> for S, ist3_K_<cid> for K; both re-derived
  with outputs/_ist3_queue.py line() and checked equal), verbatim, with exactly four tokens replaced: argv[0] (the
  wrapper: this worktree's outputs/_ist3_reach.py), the --repo value (this worktree), the --out value
  (outputs/_dq_ist/_sd_dqist_<arm>_<cid>.json) and the --tag value (dqist_<arm>_<cid>); cwd = this worktree. The
  configuration's scenario / wind / seed / steps / --set list are the isTrue K configuration's, unchanged; a line that
  sets any key starting DISPATCH_ or FF_ STOPS (the flipped defaults must decide; none of the 384 isTrue lines sets
  one).
TAG CHECK (write): outputs/_dq_queue.py tag_check on the 24 run names (every registered worktree's outputs/ and
  outputs/_ffr_logs/ top level, this worktree's outputs/_dq* directories, the git index and the git history of added
  paths, quarantine excluded, positive controls; own outputs absent), plus _mvg_ist.py's rule on the same listings and
  git paths: no name carrying "dqist_" and no entry named _dq_q_ist.jsonl / _dq_ist / _dq_ist_result.txt; and no
  <out>.reach.json / .reach.tmp, no queue, no outputs/_dq_ist, no result file on disk.
DEFAULTS (write, before anything is written): the switch accessors at the clean tree's own defaults (S) and with the
  K arm's two --set values (K), in a fresh interpreter, are as the arms need (below), and common_fixed_variables'
  DISPATCH_JOINT, DISPATCH_REASSIGN, the three FF_* and the two isTrue switches are each 1.

ANALYZE (comparison and accumulation functions imported from outputs/_ist3_analyze.py: full_diff with its TOP_SKIP /
  SEC_SKIP sets and params compared without the two isTrue keys, _mr1_acc, _poollog):
  G-V   per run: complete, crashed None, steps_done == steps; repo == this worktree; head == the launch record's
        flip_head; src_sha == the launch freeze record; tag / argv / extra_params / .argv sidecar == the queue line;
        the arm took effect (eff searcher_targeting / victim_spawn_mode, FIX3B keys, SEARCHER_FP_* keys,
        global_planner_mode, SEARCHER_TARGETING_FIX, params' MR1_TRUTHINESS_FIX / NUMPY_SCALAR_FLAGS exactly the arm's
        own --set, none of the three FF_* movement switches (FF_KEYS) and no DISPATCH_* key in params or extra_params
        - the defaults decide; extra_params == the line's --set list, which build_lines keeps free of every FF_* key);
        CRN on with draws > 0; fb3.inst error_count 0 and not broken; mr / ut / reach error lists empty; no observer
        error marker in mf2 / fx3; reach chain_exit 0 and f2_present; mr record one row per step; the pool log
        <out>.poollog present and not empty (else LOG would compare two "<missing poollog>" stand-ins and pass).
  SW    the switch accessors the run read, reconstructed from its recorded params in a fresh interpreter at this
        worktree (agents.ff_approach_path / ff_retreat_keep_approach / ff_fix_stranding_guard / mr1_truthiness_fix /
        numpy_scalar_flags / dispatch_joint / dispatch_reassign): S all True; K the two isTrue accessors False, the
        three movement and the two dispatch accessors True. The chain records no movement or dispatch switch, so this
        and the freeze are the evidence that the flipped defaults ran.
  REACH S: no numpy-typed value at any F-2 site (truthy x4, maintain, safe_float, plain_scalar inputs) or any evaluated
        parameter / context value (the isTrue analyzer's per-arm numpy total); K reported.
  SvK   S vs K: every recorded field equal except mr.mr1_list (isTrue G-A / G-K shape; full_diff skip_mr1_list).
  G1-a  S: mr.mr1_list == the CORRECTED accumulation (mr1_steps row[2]), bit-equal.
  G1-b  K: mr.mr1_list == the LITERAL accumulation (mr1_steps row[1]), bit-equal.
  MR1-chg  MR1 differs between S and K exactly where the corrected and literal per-step counts differ.
  LOG   the pool logs of S and K equal line for line (tag, wall= tokens and the checkout path normalised).
  INFO (never gating), two columns per arm:
        ref  S vs the isTrue F12 record and K vs the isTrue K record of the same configuration (outputs/
             _sd_ist3_<F12|K>_<cid>.json, head 6904b1f8, before the movement and dispatch rounds): a "differs" mixes
             the two flips;
        mvg  each arm vs the MVG round's record of the same configuration and arm (the tracked outputs/_mvg_ist/
             _sd_mvgist_<S|K>_<cid>.json, movement flip head 980d9338, same probe chain, before the dispatch flip):
             a "differs" isolates the dispatch round's change.
FREEZE: the launch record hashes every tracked file outside outputs/ and the chain / pool / analysis files in outputs/
  and records each one's [size, mtime_ns]; analyze re-hashes and re-stats them. A change to a run-loaded file (any
  tracked file outside outputs/, tests/ and *.md / *.txt, or a chain file) FAILS the check; anything else is a NOTE. A
  run-loaded file whose content is unchanged but whose size / mtime moved (rewritten since launch: an edit made and
  reverted while the runs were going cannot be excluded) also FAILS - this covers files the records' src_sha does not
  hash, such as src_extension/planning/joint_dispatch.py (the dispatch code itself). Tracked status is
  `git status --porcelain -uno` with a pathspec; untracked files outside outputs/ are found without a git status walk:
  candidates from the root's own listing and a walk of each tracked top-level directory other than outputs/, minus
  `git check-ignore`, and a candidate DIRECTORY counts only if `git ls-files --others --exclude-standard --directory
  --no-empty-directory -z -- :(literal)<candidate>` lists something (git status's normal-mode rule: a directory that
  holds only empty directories, or only files ignored by its own or any .gitignore, is not untracked content).
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import types
from collections import Counter, defaultdict

sys.dont_write_bytecode = True       # before any outputs/ module is loaded: never a .pyc in the repository

HERE = os.path.dirname(os.path.abspath(__file__))   # only for the location check (_here_ok), never for a path
WT = r"E:\Projects\SAS_wt\dispatch"
MAIN = r"E:\Projects\SAS"
PY = os.path.join(MAIN, ".venv", "Scripts", "python.exe")
OUTPUTS = os.path.join(WT, "outputs")            # every queue / record / module path is built from WT (not __file__)
WRAPPER = os.path.join(OUTPUTS, "_ist3_reach.py")
QUEUE = os.path.join(OUTPUTS, "_dq_q_ist.jsonl")
OUT_DIR = os.path.join(OUTPUTS, "_dq_ist")
RESULT = os.path.join(OUTPUTS, "_dq_ist_result.txt")
FREEZE_LAUNCH = os.path.join(OUT_DIR, "_freeze_launch.json")
FREEZE_COMPLETE = os.path.join(OUT_DIR, "_freeze_complete.json")
REF_DIR = OUTPUTS                                # the isTrue records of the same configurations (INFO only)
MVG_REF_DIR = os.path.join(OUTPUTS, "_mvg_ist")  # the MVG round's tracked records of the same configurations (INFO)
MVG_PREFIX = "mvgist_"
TAG_PREFIX = "dqist_"
ARMS = ("S", "K")
SRC_ARM = {"S": "F12", "K": "K"}                 # the isTrue line each arm reproduces
ISTRUE_KEYS = ("MR1_TRUTHINESS_FIX", "NUMPY_SCALAR_FLAGS")
FF_KEYS = ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_FIX_STRANDING_GUARD")
FF_PREFIX = "FF_"                                                 # no key of the family is set by any run line
DISPATCH_KEYS = ("DISPATCH_JOINT", "DISPATCH_REASSIGN")          # the flipped switches (ship 1)
DISPATCH_PREFIX = "DISPATCH_"                                     # no key of the family is set by any run
ACCESSORS = ("ff_approach_path", "ff_retreat_keep_approach", "ff_fix_stranding_guard", "mr1_truthiness_fix",
             "numpy_scalar_flags", "dispatch_joint", "dispatch_reassign")
WANT_ACC = {"S": {a: True for a in ACCESSORS},
            "K": dict({a: True for a in ACCESSORS}, mr1_truthiness_fix=False, numpy_scalar_flags=False)}
WANT_PARAMS = {"S": {}, "K": {"MR1_TRUTHINESS_FIX": 0, "NUMPY_SCALAR_FLAGS": 0}}
CHAIN_FILES = ("outputs/_ist3_reach.py", "outputs/_ut_probe.py", "outputs/_fb3_probe.py", "outputs/_fx3_probe.py",
               "outputs/_mf2_probe.py", "outputs/_sd_probe.py", "outputs/_bp_inst.py", "outputs/_fm2_probe_harness.py",
               "outputs/_ffr_harness.py", "outputs/_mf2_pool.py", "outputs/_ist3_queue.py",
               "outputs/_ist3_configs.json", "outputs/_ist3_q.jsonl", "outputs/_ist3_analyze.py")
SITES = ("fail_safe_planner", "global_mission_planner", "local_uav_path_planner", "rescue_planner")
QUARANTINE_EXCLUDE = ":(exclude)outputs/_firemech_rewound_20260914"
SHA_ARG_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(OUTPUTS, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_DQ: list = []


def _dq():
    """outputs/_dq_queue.py (tag_check, locations, _listing, _git_paths, _print_table), loaded once."""
    if not _DQ:
        _DQ.append(_load("_dq_queue_dqist", "_dq_queue.py"))
    return _DQ[0]


def _git(*args, root=None) -> str:
    r = subprocess.run(["git", "-C", root or WT] + list(args), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    if r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), r.stderr.strip()[:300]))
    return r.stdout


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _same_path(a, b) -> bool:
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def resolve_head(arg, git=None) -> tuple:
    """--head SHA -> (the full sha, None) or (None, why): a hex prefix of 7-40 characters that names a commit here."""
    if not arg or not SHA_ARG_RE.match(str(arg)):
        return None, "--head %r is not a hex commit sha (7-40 characters)" % (arg,)
    try:
        full = (git or _git)("rev-parse", "--verify", "--quiet", "%s^{commit}" % arg).strip().lower()
    except Exception as exc:                     # noqa: BLE001 - an unresolvable head refuses
        return None, "--head %s does not name a commit here (%s)" % (arg, exc)
    if not FULL_SHA_RE.match(full) or not full.startswith(str(arg).lower()):
        return None, "--head %s resolved to %r" % (arg, full)
    return full, None


# ---------------------------------------------------------------------------------------------------------------- queue
def k_configs(Q, frozen_cfg=None):
    """The isTrue K configurations, from _ist3_queue.configs(), checked equal to the frozen _ist3_configs.json."""
    cfgs = Q.configs()
    if frozen_cfg is None:
        with open(os.path.join(OUTPUTS, "_ist3_configs.json"), encoding="utf-8") as fh:
            frozen_cfg = json.load(fh)
    if frozen_cfg.get("configs") != json.loads(json.dumps(cfgs)):
        raise SystemExit("STOP: outputs/_ist3_configs.json differs from _ist3_queue.configs()")
    ks = [c for c in cfgs if c.get("k_arm")]
    if len(ks) != 12:
        raise SystemExit("STOP: %d K configurations, not 12" % len(ks))
    return ks


def ist3_lines():
    with open(os.path.join(OUTPUTS, "_ist3_q.jsonl"), encoding="utf-8") as fh:
        return {ln["name"]: ln for ln in (json.loads(x) for x in fh if x.strip())}


def build_lines(Q, frozen=None, frozen_cfg=None) -> list[dict]:
    frozen = ist3_lines() if frozen is None else frozen
    lines = []
    for c in k_configs(Q, frozen_cfg):
        src = {}
        for arm in ARMS:
            iname = "ist3_%s_%s" % (SRC_ARM[arm], c["cid"])
            ref = frozen.get(iname)
            if ref is None or json.loads(json.dumps(Q.line(c, SRC_ARM[arm]))) != ref:
                raise SystemExit("STOP: the frozen isTrue line %s is missing or differs from _ist3_queue.line()" % iname)
            src[arm] = ref
        # K = S + the two isTrue switches, inserted after the configuration's --set list
        a_s, a_k = src["S"]["argv"], src["K"]["argv"]
        i = a_s.index("--steps")
        exp_k = a_s[:i] + ["--set", "MR1_TRUTHINESS_FIX=0", "--set", "NUMPY_SCALAR_FLAGS=0"] + a_s[i:]
        exp_k[exp_k.index("--out") + 1] = src["K"]["out"]
        exp_k[exp_k.index("--tag") + 1] = src["K"]["name"]
        if a_k != exp_k or src["K"]["cwd"] != src["S"]["cwd"]:
            raise SystemExit("STOP: the isTrue K line of %s is not its F12 line + the two isTrue switches" % c["cid"])
        for arm in ARMS:
            ref = src[arm]
            argv = list(ref["argv"])
            tag = "%s%s_%s" % (TAG_PREFIX, arm, c["cid"])
            out = os.path.join(OUT_DIR, "_sd_%s.json" % tag)
            if argv[0] != Q.PROBE:
                raise SystemExit("STOP: argv[0] of %s is %s" % (ref["name"], argv[0]))
            keys = [argv[j + 1].split("=", 1)[0].strip() for j in range(len(argv) - 1) if argv[j] == "--set"]
            pinned = [k for k in keys if k.startswith(DISPATCH_PREFIX) or k.startswith(FF_PREFIX)]
            if pinned:
                raise SystemExit("STOP: %s sets %s; the flipped defaults must decide" % (ref["name"], pinned))
            argv[0] = WRAPPER
            for flag, old, new in (("--repo", ref["cwd"], WT), ("--out", ref["out"], out), ("--tag", ref["name"], tag)):
                j = argv.index(flag) + 1
                if argv[j] != old or argv.count(flag) != 1:
                    raise SystemExit("STOP: %s of %s is not the expected token" % (flag, ref["name"]))
                argv[j] = new
            changed = [k for k, (x, y) in enumerate(zip(argv, ref["argv"])) if x != y]
            if len(argv) != len(ref["argv"]) or len(changed) != 4:
                raise SystemExit("STOP: %s differs from its isTrue line in %s positions" % (tag, changed))
            lines.append({"name": tag, "argv": argv, "out": out, "cwd": WT})
    return lines


# --------------------------------------------------------------------------------------------------------------- freeze
def check_ignored(paths: list[str], root=None) -> set:
    """The candidates git ignores (.gitignore, info/exclude): `git check-ignore --stdin` on explicit paths, no walk."""
    if not paths:
        return set()
    r = subprocess.run(["git", "-C", root or WT, "check-ignore", "-z", "--stdin"],
                       input="".join(p.rstrip("/") + "\0" for p in paths), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    if r.returncode not in (0, 1):
        raise RuntimeError("git check-ignore failed: %s" % r.stderr.strip()[:300])
    ign = {p for p in r.stdout.split("\0") if p}
    return {p for p in paths if p.rstrip("/") in ign}


def untracked_in(cand: str, root=None) -> list[str]:
    """What git status (normal mode) lists for ONE candidate: `git ls-files --others --exclude-standard --directory
    --no-empty-directory -z -- :(literal)<cand>`. The pathspec is the candidate alone, so git looks inside that
    candidate only. Empty for a directory that holds only empty directories, or only ignored files (its own nested
    .gitignore, such as .pytest_cache/, or an ignored __pycache__/ inside it)."""
    raw = _git("ls-files", "--others", "--exclude-standard", "--directory", "--no-empty-directory", "-z", "--",
               ":(literal)" + cand, root=root)
    return [p for p in raw.split("\0") if p]


def untracked_outside_outputs(root: str, tracked: list[str], ignored=None, others=None) -> list[str]:
    """Untracked, not-ignored entries outside outputs/ - what `git status --untracked-files=normal` lists there - found
    WITHOUT a git status walk: the root's own listing (one level) and a walk of each TRACKED top-level directory other
    than outputs/. A directory nothing tracked lives in is a candidate 'dir/', never entered by this walk; it is
    reported only if `git ls-files --others ... -- :(literal)dir/` (untracked_in) lists something in it."""
    tracked_set = set(tracked)
    tracked_dirs = set()
    for p in tracked:
        parts = p.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            tracked_dirs.add("/".join(parts[:i]))
    tops = sorted(d for d in tracked_dirs if "/" not in d and d != "outputs")
    cands = []
    for name in sorted(os.listdir(root)):
        if name in (".git", "outputs"):
            continue
        if os.path.isdir(os.path.join(root, name)):
            if name not in tops:
                cands.append(name + "/")
        elif name not in tracked_set:
            cands.append(name)
    for top in tops:
        for cur, dirs, files in os.walk(os.path.join(root, top)):
            rel = os.path.relpath(cur, root).replace(os.sep, "/")
            keep = []
            for x in sorted(dirs):
                if rel + "/" + x in tracked_dirs:
                    keep.append(x)
                else:
                    cands.append(rel + "/" + x + "/")
            dirs[:] = keep
            cands += [rel + "/" + f for f in sorted(files) if rel + "/" + f not in tracked_set]
    ign = (ignored or (lambda ps: check_ignored(ps, root)))(cands)
    oth = others or (lambda c: untracked_in(c, root))
    out = []
    for c in cands:
        if c in ign:
            continue
        if c.endswith("/") and not os.listdir(os.path.join(root, *c.rstrip("/").split("/"))):
            continue                             # an empty untracked directory: git status does not list it
        if c.endswith("/") and not oth(c):
            continue                             # only empty directories / ignored files inside: not listed by git
        out.append(c)
    return sorted(out)


def freeze_record(phase: str, root=None) -> dict:
    root = root or WT
    head = _git("rev-parse", "HEAD", root=root).strip()
    status = _git("status", "--porcelain", "-uno", "--", ".", QUARANTINE_EXCLUDE, root=root)
    tracked = [p for p in _git("ls-files", "-z", "--", ".", ":(exclude)outputs", root=root).split("\0") if p]
    untracked = untracked_outside_outputs(root, tracked)
    files = sorted([p for p in tracked if not p.startswith("outputs/")] + list(CHAIN_FILES))
    sha, stat = {}, {}
    for p in files:
        fp = os.path.join(root, *p.split("/"))
        if os.path.exists(fp):
            st = os.stat(fp)
            sha[p], stat[p] = _sha256(fp), [st.st_size, st.st_mtime_ns]
        else:
            sha[p], stat[p] = "missing", None
    return {"phase": phase, "head": head, "status": status, "untracked_outside_outputs": untracked, "sha": sha,
            "stat": stat}


def run_loaded(p: str) -> bool:
    if p in CHAIN_FILES:
        return True
    return not (p.startswith("outputs/") or p.startswith("tests/") or p.lower().endswith((".md", ".txt", ".rst")))


# ---------------------------------------------------------------------------------------------------- tag collision
def collision_check(lines: list[dict]) -> tuple:
    """outputs/_dq_queue.py tag_check (every worktree, index, history; controls) on the run names, plus the
    _mvg_ist.py rule (the tag prefix / this check's own names) and the wrapper's own outputs. (rows, details)."""
    DQ = _dq()
    rows, details = DQ.tag_check(lines, resume=False, all_trees=True)
    own_files = [p for ln in lines for p in (ln["out"] + ".reach.json", ln["out"] + ".reach.tmp")]
    own_files += [QUEUE, OUT_DIR, RESULT]
    present = ["EXISTS " + p for p in own_files if os.path.exists(p)]
    rows.insert(1, ["own reach records, queue, %s, result (exact paths)" % os.path.basename(OUT_DIR),
                    str(len(own_files)), str(len(present)), "-", "PASS" if not present else "FAIL"])
    own = {os.path.basename(p).lower() for p in (QUEUE, OUT_DIR, RESULT)}
    hits, n = [], 0
    for _label, folder, _ctl in DQ.locations(True):
        names = DQ._listing(folder)
        if names is None:
            continue
        n += len(names)
        hits += ["NAME IN USE " + os.path.join(folder, x) for x in names if TAG_PREFIX in x.lower() or x.lower() in own]
    for kind in ("index", "history"):
        paths = DQ._git_paths(kind)
        n += len(paths)
        hits += ["TRACKED (%s) %s" % (kind, p) for p in paths
                 if TAG_PREFIX in p.lower() or (p.lower().startswith("outputs/") and p.lower().split("/")[1] in own)]
    rows.append(["prefix %r / own names %s (the listings above, git index + history)" % (TAG_PREFIX, sorted(own)),
                 str(n), str(len(hits)), "-", "PASS" if not hits else "FAIL"])
    return rows, sorted(set(details + present + hits))


# ---------------------------------------------------------------------------------------------------------------- write
def defaults_problems(acc: dict) -> list[str]:
    """The flip's defaults at the tree, from rebuild_accessors({"_S": {}, "_K": the K arm's --set}) - [] when right."""
    if "_error" in acc:
        return ["accessor child: %s" % acc["_error"]]
    probs = []
    for key, arm in (("_S", "S"), ("_K", "K")):
        got = acc.get(key) or {}
        bad = [a for a in ACCESSORS if got.get(a) is not WANT_ACC[arm][a]]
        if bad:
            probs.append("defaults%s: accessors %s are not as arm %s needs" % (
                " + the K arm's --set" if arm == "K" else "", bad, arm))
    raw = acc.get("_raw") or {}
    for k in DISPATCH_KEYS + FF_KEYS + ISTRUE_KEYS:
        if raw.get(k) != 1:
            probs.append("common_fixed_variables.%s = %r, not the shipped 1" % (k, raw.get(k)))
    return probs


def write(head_arg=None) -> int:
    if not head_arg:
        print("STOP: write needs --head SHA, the dispatch flip commit (recorded in the launch freeze record)")
        return 2
    if not SHA_ARG_RE.match(str(head_arg)):      # before the frozen-queue branch too: never a 1-6 character prefix
        print("STOP: --head %r is not a hex commit sha (7-40 characters)" % (head_arg,))
        return 2
    Q = _load("_ist3_queue_dqist", "_ist3_queue.py")
    lines = build_lines(Q)
    text = "".join(json.dumps(x) + "\n" for x in lines)
    if os.path.exists(QUEUE):
        with open(QUEUE, encoding="utf-8") as fh:
            if fh.read() != text:
                print("STOP: %s exists and differs (frozen; never re-written)" % QUEUE)
                return 2
        try:
            with open(FREEZE_LAUNCH, encoding="utf-8") as fh:
                frozen_head = str(json.load(fh).get("flip_head") or "")
        except (OSError, ValueError) as exc:
            print("STOP: %s is frozen but its launch freeze record is unreadable (%r)" % (QUEUE, exc))
            return 2
        if not frozen_head or not frozen_head.startswith(str(head_arg).lower()):
            print("STOP: %s was frozen for the flip head %s, not --head %s" % (QUEUE, frozen_head[:12], head_arg))
            return 2
        print("unchanged (frozen): %s (%d lines, flip head %s)" % (QUEUE, len(lines), frozen_head[:8]))
        return 0
    flip_head, why = resolve_head(head_arg)
    if flip_head is None:
        print("STOP: %s" % why)
        return 2
    # tag collision: outputs/_dq_queue.py tag_check (every registered worktree's outputs/ and outputs/_ffr_logs/ top
    # level, the git index and history, quarantine excluded) + no name carrying the prefix or an own name anywhere there
    rows, details = collision_check(lines)
    if any(not r[4].startswith("PASS") for r in rows):
        _dq()._print_table(rows)
        print("STOP: tag collision - nothing written:\n  %s" % "\n  ".join(details[:60]))
        return 2
    fr = freeze_record("launch")
    probs = []
    if fr["head"] != flip_head:
        probs.append("HEAD %s != --head %s (%s)" % (fr["head"], head_arg, flip_head))
    if fr["status"].strip():
        probs.append("tracked files modified: %r" % fr["status"][:300])
    if fr["untracked_outside_outputs"]:
        probs.append("untracked files outside outputs/: %s" % fr["untracked_outside_outputs"][:10])
    if any(v == "missing" for v in fr["sha"].values()):
        probs.append("missing files: %s" % [k for k, v in fr["sha"].items() if v == "missing"][:10])
    acc = rebuild_accessors({"_S": {}, "_K": dict(WANT_PARAMS["K"])})
    probs += defaults_problems(acc)
    if probs:
        print("STOP: the tree is not the clean flip commit: %s" % probs)
        return 2
    fr.update({"flip_head": flip_head, "head_arg": head_arg, "defaults": acc})
    os.makedirs(OUT_DIR, exist_ok=False)
    with open(FREEZE_LAUNCH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fr, fh, indent=1, sort_keys=True)
        fh.write("\n")
    with open(QUEUE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote %s (%d lines: S and K x %d configurations) and %s (%d files hashed, flip head %s)"
          % (QUEUE, len(lines), len(lines) // 2, FREEZE_LAUNCH, len(fr["sha"]), fr["head"][:8]))
    print("RULE: no commit in %s until the 24th run has finished - every run records the HEAD it ran at and G-V "
          "requires it to equal flip_head %s" % (WT, fr["head"][:8]))
    return 0


# ------------------------------------------------------------------------------------------------- accessor rebuild
def _accessor_values(am, cfv, runs: dict) -> dict:
    """{name: {accessor: value}} with each run's params applied to cfv (as apply_scenario_config does) and restored."""
    out = {}
    missing = object()
    for name, params in runs.items():
        saved = {k: getattr(cfv, k, missing) for k in params}
        try:
            for k, v in params.items():          # apply_scenario_config: setattr on the cfv module
                setattr(cfv, k, v)
            out[name] = {a: getattr(am, a)() for a in ACCESSORS}
        finally:
            for k, v in saved.items():
                if v is missing:
                    delattr(cfv, k)
                else:
                    setattr(cfv, k, v)
    keys = FF_KEYS + ISTRUE_KEYS + tuple(sorted(set(DISPATCH_KEYS) | {k for k in vars(cfv)
                                                                      if k.startswith(DISPATCH_PREFIX)}))
    out["_raw"] = {k: getattr(cfv, k, None) for k in keys}
    return out


def _accessors_child() -> int:
    """Child mode: stdin {"repo", "runs": {name: params}} -> stdout {name: {accessor: value}} (fresh interpreter)."""
    req = json.load(sys.stdin)
    repo = req["repo"]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    try:
        import agents as am  # noqa: E402
        import common_fixed_variables as cfv  # noqa: E402
        for m in (am, cfv):
            if not os.path.abspath(m.__file__).lower().startswith(repo.lower() + os.sep):
                print(json.dumps({"_error": "import mismatch %s" % m.__file__}))
                return 3
        out = _accessor_values(am, cfv, req["runs"])
    except Exception as exc:                     # noqa: BLE001 - reported to the parent, which fails the check
        print(json.dumps({"_error": "accessor child: %r" % (exc,)}))
        return 3
    print(json.dumps(out))
    return 0


def rebuild_accessors(runs: dict) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([PY, "-B", os.path.abspath(__file__), "_accessors"], input=json.dumps({"repo": WT, "runs": runs}),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=WT, env=env,
                       timeout=600)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"_error": "accessor child failed rc=%s: %s" % (r.returncode, (r.stderr or r.stdout)[-400:])}


# -------------------------------------------------------------------------------------------------------------- analyze
def _paths_only(diffs):
    out = []
    for s in diffs:
        out.append(s.split(": ", 1)[0] if ": " in s else s)
    return out


def analyze(partial: bool, head_arg=None) -> int:
    lines_out: list[str] = []

    def say(s=""):
        lines_out.append(s)
        print(s)

    if head_arg is not None and not SHA_ARG_RE.match(str(head_arg)):
        print("STOP: --head %r is not a hex commit sha (7-40 characters)" % (head_arg,))
        return 3
    Q = _load("_ist3_queue_dqist", "_ist3_queue.py")
    A = _load("_ist3_analyze_dqist", "_ist3_analyze.py")
    SD = _load("_sd_probe_dqist", "_sd_probe.py")
    FB3 = _load("_fb3_probe_keys_dqist", "_fb3_probe.py")
    lines = build_lines(Q)
    if not os.path.exists(QUEUE) or not os.path.exists(FREEZE_LAUNCH):
        print("STOP: %s or %s is missing (write --head SHA first)" % (QUEUE, FREEZE_LAUNCH))
        return 3
    with open(QUEUE, encoding="utf-8") as fh:
        qfile = [json.loads(x) for x in fh if x.strip()]
    if qfile != json.loads(json.dumps(lines)):
        print("STOP: %s differs from the re-derived queue" % QUEUE)
        return 3
    with open(FREEZE_LAUNCH, encoding="utf-8") as fh:
        f0 = json.load(fh)
    HEAD = str(f0.get("flip_head") or "")
    if not FULL_SHA_RE.match(HEAD) or (head_arg and not HEAD.startswith(str(head_arg).lower())):
        print("STOP: the launch record's flip head %r is not a full sha or does not match --head %s" % (HEAD, head_arg))
        return 3
    ks = k_configs(Q)
    say("isTrue 19.12(c) CHECK at the dispatch flip head %s (outputs/fix3b_part1.txt 19.12 (c); dispatch2_report.txt "
        "section 10)" % HEAD)
    say("QUEUE OK: %s, %d lines = S and K x %d isTrue K configurations (seeds %s)"
        % (QUEUE, len(lines), len(ks), ", ".join(str(c["seed"]) for c in ks)))

    # ---- freeze
    global_probs, notes = [], []
    f1 = freeze_record("complete")
    with open(FREEZE_COMPLETE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(f1, fh, indent=1, sort_keys=True)
        fh.write("\n")
    if f0["head"] != HEAD or f0["status"].strip() or f0["untracked_outside_outputs"]:
        global_probs.append("launch record: head %s, status %r, untracked %s"
                            % (f0["head"][:8], f0["status"][:80], f0["untracked_outside_outputs"][:5]))
    changed = sorted(p for p in set(f0["sha"]) | set(f1["sha"]) if f0["sha"].get(p) != f1["sha"].get(p))
    bad_changed = [p for p in changed if run_loaded(p)]
    if bad_changed:
        global_probs.append("run-loaded files changed since launch: %s" % bad_changed[:10])
    if [p for p in changed if not run_loaded(p)]:
        notes.append("non-run-loaded files changed since launch: %s" % [p for p in changed if not run_loaded(p)][:10])
    st0, st1 = f0.get("stat"), f1.get("stat") or {}
    if not isinstance(st0, dict):
        global_probs.append("launch record has no stat block: a same-content rewrite of a run-loaded file during the "
                            "runs cannot be checked")
    else:
        rewritten = sorted(p for p in set(st0) | set(st1) if p not in changed and st0.get(p) != st1.get(p))
        if [p for p in rewritten if run_loaded(p)]:
            global_probs.append("run-loaded files rewritten since launch with the same content (size / mtime moved; an "
                                "edit reverted during the runs cannot be excluded): %s"
                                % [p for p in rewritten if run_loaded(p)][:10])
        if [p for p in rewritten if not run_loaded(p)]:
            notes.append("non-run-loaded files rewritten since launch with the same content: %s"
                         % [p for p in rewritten if not run_loaded(p)][:10])
    if f1["head"] != f0["head"]:
        notes.append("HEAD moved since launch: %s -> %s (run-loaded files %s)"
                     % (f0["head"][:8], f1["head"][:8], "unchanged" if not bad_changed else "CHANGED"))
    if f1["status"].strip():
        st_bad = [ln for ln in f1["status"].splitlines() if run_loaded(ln[3:])]
        (global_probs if st_bad else notes).append("tracked status at analysis: %r" % f1["status"][:300])
    if f1["untracked_outside_outputs"]:
        global_probs.append("untracked files outside outputs/ at analysis: %s" % f1["untracked_outside_outputs"][:10])
    say("FREEZE: %d files hashed at launch (head %s); at analysis %d changed, %d of them run-loaded"
        % (len(f0["sha"]), f0["head"][:8], len(changed), len(bad_changed)))

    # ---- per run validity (G-V)
    runs, logs, reach, gv = {}, {}, {}, {}
    missing = []
    for ln in lines:
        name, out = ln["name"], ln["out"]
        arm = name.split("_")[1]
        if not os.path.exists(out):
            missing.append(name)
            continue
        probs = []
        try:
            with open(out, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception as exc:
            gv[name] = ["unparseable (%r)" % (exc,)]
            continue
        after = ln["argv"][ln["argv"].index("--") + 1:]
        sets = {}
        for i, tok in enumerate(after):
            if tok == "--set":
                k, v = after[i + 1].split("=", 1)
                sets[k.strip()] = SD._parse_value(v)
        steps = int(after[after.index("--steps") + 1])
        if not d.get("complete") or d.get("crashed") is not None or d.get("steps_done") != steps:
            probs.append("complete=%s crashed=%s steps_done=%s" % (d.get("complete"), d.get("crashed") is not None,
                                                                   d.get("steps_done")))
        if not _same_path(d.get("repo"), WT):
            probs.append("repo %s" % d.get("repo"))
        if d.get("head") != HEAD:
            probs.append("head %s != %s (the launch record's flip_head; no commit may land between write and the end "
                         "of the 24 runs)" % (d.get("head"), HEAD))
        if d.get("tag") != name:
            probs.append("tag %s" % d.get("tag"))
        ss = d.get("src_sha") or {}
        if not ss:
            probs.append("src_sha missing")
        for fname, h in ss.items():
            rel = fname.replace("\\", "/")
            if (f0["sha"].get(rel) or "")[:16] != h:
                probs.append("src_sha %s %s != launch freeze %s" % (rel, h, (f0["sha"].get(rel) or "")[:16]))
        if d.get("extra_params") != sets:
            probs.append("extra_params %s != %s" % (d.get("extra_params"), sets))
        if d.get("argv") != after:
            probs.append("argv differs from the queue line")
        try:
            with open(out + ".argv", encoding="utf-8") as fh:
                sig = json.load(fh)
            if sig != {"argv": ln["argv"], "cwd": ln["cwd"]}:
                probs.append(".argv sidecar differs")
        except Exception:
            probs.append(".argv sidecar missing")
        fb3 = d.get("fb3") or {}
        eff = fb3.get("eff") or {}
        if eff.get("searcher_targeting") != int(sets.get("SEARCHER_TARGETING", 0)):
            probs.append("eff searcher_targeting %s" % eff.get("searcher_targeting"))
        if eff.get("victim_spawn_mode") != int(sets.get("VICTIM_SPAWN_MODE", 0)):
            probs.append("eff victim_spawn_mode %s" % eff.get("victim_spawn_mode"))
        for k, v in sets.items():
            if k in FB3.FIX3B_KEYS and (fb3.get("switches") or {}).get(k) != v:
                probs.append("switch %s recorded %s != %s" % (k, (fb3.get("switches") or {}).get(k), v))
            if k.startswith("SEARCHER_FP_"):
                rec = (fb3.get("bp_switches") or {}).get(k) or {}
                if rec.get("raw") != v or rec.get("eff") is None or float(rec["eff"]) != float(v):
                    probs.append("FP %s recorded %s != %s" % (k, rec, v))
        gpm_eff = (d.get("effective") or {}).get("global_planner_mode")
        if gpm_eff != int(sets.get("GLOBAL_PLANNER_MODE", 0)):
            probs.append("effective global_planner_mode %s" % gpm_eff)
        stf = (fb3.get("bp_switches") or {}).get("SEARCHER_TARGETING_FIX") or {}
        want_stf = sets.get("SEARCHER_TARGETING_FIX", 1)
        if stf.get("raw") != want_stf or stf.get("eff") is not (want_stf != 0):
            probs.append("SEARCHER_TARGETING_FIX recorded %s != %s" % (stf, want_stf))
        params = d.get("params") or {}
        for k in ISTRUE_KEYS:
            if params.get(k) != WANT_PARAMS[arm].get(k):
                probs.append("params %s = %s, the arm sets %s" % (k, params.get(k), WANT_PARAMS[arm].get(k)))
        for k in FF_KEYS:
            if k in params or k in (d.get("extra_params") or {}):
                probs.append("movement switch %s set explicitly (%s)" % (k, params.get(k)))
        disp = sorted(str(k) for k in set(params) | set(d.get("extra_params") or {})
                      if str(k).startswith(DISPATCH_PREFIX))
        if disp:
            probs.append("dispatch switch(es) %s set explicitly (the flipped defaults must decide)" % disp)
        crn = fb3.get("crn") or {}
        if not (crn.get("on") and (crn.get("crn_draws") or 0) > 0):
            probs.append("CRN not on with draws > 0: %s" % crn)
        inst = fb3.get("inst")
        if not isinstance(inst, dict) or inst.get("error_count") or inst.get("broken"):
            probs.append("fb3.inst missing / error_count / broken")
        mr = d.get("mr") or {}
        if mr.get("errors"):
            probs.append("mr errors %s" % mr["errors"][:2])
        if (d.get("ut") or {}).get("errors"):
            probs.append("ut errors %s" % d["ut"]["errors"][:2])
        for sec in ("mf2", "fx3"):
            if A.ERR_RE.search(json.dumps(d.get(sec))):
                probs.append("%s carries an observer error marker" % sec)
        ms = mr.get("mr1_steps")
        n_uav = len(mr.get("mr1_list") or [])
        if not (isinstance(ms, list) and len(ms) == steps and [x[0] for x in ms] == list(range(1, steps + 1))
                and all(len(x[1]) == n_uav and len(x[2]) == n_uav for x in ms) and mr.get("n_observations")
                and n_uav == int(params.get("NUM_AGENTS", n_uav))):
            probs.append("mr record malformed (%s rows, %s UAVs)" % (len(ms or []), n_uav))
        try:
            with open(out + ".reach.json", encoding="utf-8") as fh:
                rch = json.load(fh)
            if rch.get("chain_exit") not in (0, None) or rch.get("errors"):
                probs.append("reach exit %s errors %s" % (rch.get("chain_exit"), (rch.get("errors") or [])[:2]))
            if rch.get("f2_present") is not True:
                probs.append("reach f2_present %s" % rch.get("f2_present"))
            if not _same_path(rch.get("repo"), WT):
                probs.append("reach repo %s" % rch.get("repo"))
            reach[name] = rch
        except Exception as exc:
            probs.append("reach record missing (%r)" % (exc,))
        if not os.path.isfile(out + ".poollog") or os.path.getsize(out + ".poollog") == 0:
            probs.append("poollog missing or empty (%s.poollog): LOG would compare stand-ins"
                         % os.path.basename(out))
        gv[name] = probs
        runs[name] = d
        logs[name] = A._poollog(out + ".poollog", (WT,), name)
    n_gv_fail = sum(1 for p in gv.values() if p)
    say("RUNS present %d / %d; G-V failures %d; global problems %d"
        % (len(runs), len(lines), n_gv_fail, len(global_probs)))
    for g in global_probs:
        say("  GLOBAL FAIL %s" % g)
    for name, p in gv.items():
        if p:
            say("  G-V FAIL %s: %s" % (name, "; ".join(p)))
    for nn in notes:
        say("  NOTE %s" % nn)
    if missing and not partial:
        say("STOP: %d runs missing (e.g. %s); use --partial for an interim report" % (len(missing), missing[:3]))
        return 3

    # ---- SW: the accessors the run read, reconstructed from its recorded params
    acc = rebuild_accessors({n: d.get("params") or {} for n, d in runs.items()})
    sw = {}
    if "_error" in acc:
        global_probs.append("SW: %s" % acc["_error"])
        say("  GLOBAL FAIL SW: %s" % acc["_error"])
    else:
        for n in runs:
            arm = n.split("_")[1]
            got = acc.get(n) or {}
            sw[n] = [a for a in ACCESSORS if got.get(a) is not WANT_ACC[arm][a]]
        say("SW: module defaults at this worktree: %s" % acc.get("_raw"))

    # ---- gates per configuration
    gates = {g: [0, 0] for g in ("SvK", "G1-a", "G1-b", "MR1-chg", "LOG", "SW")}
    fails, table, info = [], [], []
    lit_after3, lit_nz = 0, []

    def numpy_count(rch):
        n = 0
        for site in SITES:
            n += sum(v for k, v in ((rch.get("truthy") or {}).get(site) or {}).items() if k.startswith("numpy."))
        for key in ("maintain", "safe_float", "plain_scalar", "plain_scalar_converted"):
            n += sum(v for k, v in (rch.get(key) or {}).items() if k.startswith("numpy."))
        for key in ("params", "context"):
            for cnt in (rch.get(key) or {}).values():
                n += sum(cnt.values())
        return n

    for c in ks:
        names = {arm: "%s%s_%s" % (TAG_PREFIX, arm, c["cid"]) for arm in ARMS}
        r = {arm: runs.get(names[arm]) for arm in ARMS}
        row = {"cid": c["cid"], "seed": c["seed"]}

        def gate(g, ok, why=""):
            gates[g][0 if ok else 1] += 1
            if not ok:
                fails.append("%s %s: %s" % (g, c["cid"], why))
            return "ok" if ok else "FAIL"

        for arm in ARMS:
            row["gv" + arm] = "-" if r[arm] is None else ("ok" if not gv.get(names[arm]) else "FAIL")
            row["np" + arm] = numpy_count(reach[names[arm]]) if names[arm] in reach else "-"
            if names[arm] in sw:
                row["sw" + arm] = gate("SW", not sw[names[arm]], "%s accessors %s not as the arm"
                                       % (arm, sw[names[arm]]))
            else:
                row["sw" + arm] = "-"
        d_s, d_k = r["S"], r["K"]
        if d_s is not None:
            mr = d_s["mr"]
            nobs = float(mr["n_observations"])
            cor = A._mr1_acc(len(mr["mr1_list"]), [x[2] for x in mr["mr1_steps"]], nobs)
            row["g1a"] = gate("G1-a", cor == list(mr["mr1_list"]), "S mr1_list != corrected accumulation")
        if d_k is not None:
            mr = d_k["mr"]
            nobs = float(mr["n_observations"])
            lit = A._mr1_acc(len(mr["mr1_list"]), [x[1] for x in mr["mr1_steps"]], nobs)
            row["g1b"] = gate("G1-b", lit == list(mr["mr1_list"]), "K mr1_list != literal accumulation")
            lit_after3 += sum(1 for x in mr["mr1_steps"] if x[0] > 3 and any(x[1]))
            nz = sum(1 for x in mr["mr1_steps"] if any(x[1]))
            if nz:
                lit_nz.append("%s:%d" % (c["cid"], nz))
        if d_s is not None and d_k is not None:
            dd = A.full_diff(d_s, d_k, skip_mr1_list=True)
            row["svk"] = gate("SvK", not dd, "; ".join(dd[:6]))
            ch = d_s["mr"]["mr1_list"] != d_k["mr"]["mr1_list"]
            expect = any(x[1] != x[2] for x in d_s["mr"]["mr1_steps"])
            row["chg"] = gate("MR1-chg", ch == expect, "MR1 changed %s, corrected != literal on some step %s"
                              % (ch, expect)) + ("(chg)" if ch else "(same)")
            ls, lk = logs.get(names["S"]), logs.get(names["K"])
            row["log"] = gate("LOG", ls == lk, "S vs K pool log differs (first: %s)"
                              % (next((p for p in zip(ls or [], lk or []) if p[0] != p[1]), "length"),))
        # INFO, never gating: ref = the isTrue record of the same configuration (before the movement and dispatch
        # rounds); mvg = the MVG round's record of the same configuration and arm (the movement flip, before the
        # dispatch flip: a difference there isolates the dispatch round)
        for col, ref_dir, label in (("ref", REF_DIR, "isTrue %s"), ("mvg", MVG_REF_DIR, "MVG %s")):
            for arm in ARMS:
                if col == "ref":
                    ref_path = os.path.join(ref_dir, "_sd_ist3_%s_%s.json" % (SRC_ARM[arm], c["cid"]))
                    what = label % SRC_ARM[arm]
                else:
                    ref_path = os.path.join(ref_dir, "_sd_%s%s_%s.json" % (MVG_PREFIX, arm, c["cid"]))
                    what = label % arm
                if r[arm] is None or not os.path.exists(ref_path):
                    row[col + arm] = "-"
                    continue
                with open(ref_path, encoding="utf-8") as fh:
                    ref = json.load(fh)
                dd = A.full_diff(r[arm], ref, skip_mr1_list=False)
                row[col + arm] = "same" if not dd else "differs"
                if dd:
                    info.append("%s %s %s vs %s: %d%s differing fields, first %s"
                                % (col, c["cid"], arm, what, len(dd), "+ (listing capped)" if len(dd) >= 12 else "",
                                   _paths_only(dd)[:5]))
        table.append(row)

    say("")
    say("PER CONFIGURATION (G-V / SW per arm; np = numpy-typed values at the F-2 sites and evaluated params/context;")
    say("  SvK = S vs K every field except mr.mr1_list; G1-a = S corrected; G1-b = K literal; MR1-chg; LOG;")
    say("  ref = INFO only: the run vs the isTrue record of the same configuration at 6904b1f8;")
    say("  mvg = INFO only: the run vs the MVG round's record of the same configuration and arm at 980d9338)")
    fmt = "%-18s %6s | %-4s %-4s | %-4s %-4s | %5s %5s | %-4s | %-4s | %-4s | %-9s | %-4s | %-7s %-7s | %-7s %-7s"
    hdr = fmt % ("config", "seed", "GV-S", "GV-K", "SW-S", "SW-K", "np-S", "np-K", "SvK", "G1-a", "G1-b", "MR1-chg",
                 "LOG", "ref-S", "ref-K", "mvg-S", "mvg-K")
    say(hdr)
    say("-" * len(hdr))
    for row in table:
        say(fmt % (row["cid"], row["seed"], row["gvS"], row["gvK"], row["swS"], row["swK"], row["npS"], row["npK"],
                   row.get("svk", "-"), row.get("g1a", "-"), row.get("g1b", "-"), row.get("chg", "-"),
                   row.get("log", "-"), row["refS"], row["refK"], row["mvgS"], row["mvgK"]))

    # ---- reach census per arm
    say("")
    say("REACH CENSUS (record-only, outputs/_ist3_reach.py), summed per arm: calls = values seen at the site; numpy =")
    say("  numpy-typed values there (maintain: calls of _is_maintain_option; plain_scalar: every call)")
    per_arm = defaultdict(lambda: defaultdict(Counter))
    calls = defaultdict(Counter)
    np_total = Counter()
    for name, rch in reach.items():
        arm = name.split("_")[1]
        rc = rch.get("calls") or {}
        for site in SITES:
            cnt = (rch.get("truthy") or {}).get(site) or {}
            per_arm[arm]["truthy." + site].update({k: v for k, v in cnt.items() if k.startswith("numpy.")})
            calls[arm]["truthy." + site] += sum(cnt.values())
        for key in ("maintain", "safe_float", "plain_scalar", "plain_scalar_converted"):
            cnt = rch.get(key) or {}
            per_arm[arm][key].update({k: v for k, v in cnt.items() if k.startswith("numpy.")})
            if key == "plain_scalar":
                calls[arm][key] += int(rc.get("plain_scalar", 0))
            elif key == "maintain":
                calls[arm][key] += int(rc.get("_is_maintain_option", 0))
            else:
                calls[arm][key] += sum(cnt.values())
        calls[arm]["evaluate_option"] += int(rc.get("evaluate_option", 0))
        calls[arm]["runs"] += 1
        for key in ("params", "context"):
            for k2, cnt in (rch.get(key) or {}).items():
                per_arm[arm]["%s.%s" % (key, k2)].update(cnt)
        np_total[arm] += numpy_count(rch)
    for arm in ARMS:
        if arm not in calls:
            continue
        say("  arm %s (%d runs):" % (arm, calls[arm]["runs"]))
        for site in sorted((set(per_arm[arm]) | set(calls[arm])) - {"runs"}):
            say("    %-40s calls %10d  numpy %s" % (site, calls[arm].get(site, 0), dict(per_arm[arm].get(site, {}))))
    say("numpy-typed values at any F-2 site or evaluated parameter / context value, per arm: %s"
        % {a: np_total[a] for a in ARMS if a in calls})
    census_ok = "S" in calls and np_total["S"] == 0 and calls["S"]["runs"] == len(ks)

    say("")
    say("K literal MR1 counts after step 3 (expected 0): %d; K runs with a non-zero literal count: %d %s"
        % (lit_after3, len(lit_nz), lit_nz))
    say("")
    say("INFO (not gating): runs that differ from an earlier record of the same configuration (n / %d; '-' = no "
        "record to compare):" % len(table))

    def n_of(col, arm, val):
        return sum(1 for t in table if t[col + arm] == val)
    say("  ref (isTrue, head 6904b1f8, before the movement and dispatch rounds; mixes both flips): S %d / %d, K %d / %d"
        " (no record: S %d, K %d)" % (n_of("ref", "S", "differs"), len(table), n_of("ref", "K", "differs"), len(table),
                                      n_of("ref", "S", "-"), n_of("ref", "K", "-")))
    say("  mvg (MVG round, head 980d9338, the movement flip before the dispatch flip; isolates dispatch): S %d / %d, "
        "K %d / %d (no record: S %d, K %d)" % (n_of("mvg", "S", "differs"), len(table), n_of("mvg", "K", "differs"),
                                              len(table), n_of("mvg", "S", "-"), n_of("mvg", "K", "-")))
    for x in info:
        say("  %s" % x)

    say("")
    say("GATES (pass / fail):")
    for g, (p, f) in gates.items():
        say("  %-8s %3d / %d" % (g, p, f))
    say("  G-V      %3d / %d (runs)" % (len(runs) - n_gv_fail, n_gv_fail))
    say("  REACH-S  %s (numpy values in arm S: %s; arm K: %s)" % ("PASS" if census_ok else "FAIL", np_total.get("S"),
                                                                 np_total.get("K")))
    for f in fails:
        say("  FAIL %s" % f)
    ok = (not missing and not global_probs and not n_gv_fail and census_ok
          and not any(f for _p, f in gates.values())
          and gates["SvK"][0] == len(ks) and gates["G1-a"][0] == len(ks) and gates["G1-b"][0] == len(ks)
          and gates["SW"][0] == 2 * len(ks))
    say("")
    say("19.12(c) => %s" % ("PASS" if ok else ("INCOMPLETE" if missing else "FAIL")))
    with open(RESULT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines_out) + "\n")
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------------------ self-test
@contextlib.contextmanager
def _patched(**kw):
    """Rebind module globals (paths, and the functions that touch git, listings or a child interpreter) for a test."""
    g = globals()
    saved = {k: g[k] for k in kw}
    g.update(kw)
    try:
        yield
    finally:
        g.update(saved)


def _paths(root: str) -> dict:
    os.makedirs(root, exist_ok=True)
    out_dir = os.path.join(root, "_dq_ist")
    return {"QUEUE": os.path.join(root, "_dq_q_ist.jsonl"), "OUT_DIR": out_dir,
            "RESULT": os.path.join(root, "_dq_ist_result.txt"),
            "FREEZE_LAUNCH": os.path.join(out_dir, "_freeze_launch.json"),
            "FREEZE_COMPLETE": os.path.join(out_dir, "_freeze_complete.json"), "REF_DIR": os.path.join(root, "refs"),
            "MVG_REF_DIR": os.path.join(root, "mvgrefs")}


def _exit_code(fn) -> int:
    """The process exit code fn() would give as `raise SystemExit(fn())` (Python's rule: a non-int code exits 1)."""
    try:
        code = fn()
    except SystemExit as exc:
        code = exc.code
    except Exception:                            # noqa: BLE001 - an uncaught exception exits 1
        return 1
    if code is None:
        return 0
    return code if isinstance(code, int) else 1


def _scratch_repo(root: str) -> str:
    """A fresh `git init` repository under the self-test's temp dir (git runs only there)."""
    os.makedirs(root)
    for args in (["-c", "init.defaultBranch=main", "init", "-q"], ["config", "core.autocrlf", "false"],
                 ["config", "core.fsmonitor", "false"]):        # no daemon holding the temp dir open
        r = subprocess.run(["git", "-C", root] + args, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError("scratch git %s failed: %s" % (args, r.stderr.strip()[:200]))
    return root


def _rm_tree(path: str) -> None:
    """shutil.rmtree that also removes read-only files (git writes its objects read-only on Windows)."""
    def onerror(fn, p, _exc):
        os.chmod(p, 0o700)
        fn(p)
    if os.path.exists(path):
        shutil.rmtree(path, onerror=onerror)


def _run(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            code = fn(*a)
        except SystemExit as exc:
            code = "SystemExit"
            print(str(exc))
    return code, buf.getvalue()


def _fake_freeze(fr: dict):
    return lambda phase: dict(copy.deepcopy(fr), phase=phase)


def _fake_acc(override=None, raw=None, error=None):
    """rebuild_accessors stand-in: each run's accessors as its arm needs (K = MR1_TRUTHINESS_FIX 0 in its params),
    with per-run overrides."""
    def fake(runs):
        if error:
            return {"_error": error}
        out = {}
        for n, params in runs.items():
            arm = "K" if params.get("MR1_TRUTHINESS_FIX") == 0 else "S"
            out[n] = dict(WANT_ACC[arm], **((override or {}).get(n) or {}))
        out["_raw"] = dict({k: 1 for k in FF_KEYS + ISTRUE_KEYS + DISPATCH_KEYS}, DISPATCH_STALL_STEPS=10,
                           **(raw or {}))
        return out
    return fake


def _synth(lines, head, sha0, A, SD, FB3, same_cid=None, n_uav=3) -> dict:
    """Mutually consistent synthetic records for queue lines (no run): {name: (record, sidecar, reach, poollog)}. S and
    K of a configuration share the per-step counts; S carries the corrected and K the literal accumulation; labels and
    wall-clock fields differ between the arms (the comparison must skip them)."""
    out = {}
    for ln in lines:
        name = ln["name"]
        arm, cid = name.split("_", 2)[1], name.split("_", 2)[2]
        after = ln["argv"][ln["argv"].index("--") + 1:]
        sets = {}
        for i, tok in enumerate(after):
            if tok == "--set":
                k, v = after[i + 1].split("=", 1)
                sets[k.strip()] = SD._parse_value(v)
        steps = int(after[after.index("--steps") + 1])
        rnd = random.Random(int(cid.split("_")[0]) + 7)
        rows = []
        for t in range(1, steps + 1):
            lit = [rnd.randint(0, 2) if t <= 3 else 0 for _u in range(n_uav)]
            cor = list(lit) if cid == same_cid else [rnd.randint(0, 3) for _u in range(n_uav)]
            rows.append([t, lit, cor])
        nobs = 8
        mr1 = A._mr1_acc(n_uav, [x[2] if arm == "S" else x[1] for x in rows], float(nobs))
        stf = sets.get("SEARCHER_TARGETING_FIX", 1)
        bp = {k: {"raw": v, "eff": float(v)} for k, v in sets.items() if k.startswith("SEARCHER_FP_")}
        bp["SEARCHER_TARGETING_FIX"] = {"raw": stf, "eff": stf != 0}
        w = 1.0 if arm == "S" else 2.5
        uv = os.path.join("src_extension", "planning", "utility_evaluation.py")
        d = {"probe": "sd synthetic", "tag": name, "repo": WT, "head": head,
             "src_sha": {"agents.py": sha0["agents.py"][:16],
                         "common_fixed_variables.py": sha0["common_fixed_variables.py"][:16],
                         uv: sha0["src_extension/planning/utility_evaluation.py"][:16]},
             "argv": after, "extra_params": dict(sets), "wall_s": 100 * w, "python": "3.12 " + arm, "mesa": "1.2.1",
             "_det": arm, "complete": True, "crashed": None, "steps_done": steps,
             "params": dict({"NUM_AGENTS": n_uav, "NUM_VICTIMS": 5, "SCEN": after[after.index("--scenario") + 1]},
                            **sets),
             "effective": {"global_planner_mode": int(sets.get("GLOBAL_PLANNER_MODE", 0)), "base_station_mode": 3},
             "eval": {"rescued": 4, "dead": 1, "burnt_cells": 321, "terminal_step": None},
             "fb3": {"eff": {"searcher_targeting": int(sets.get("SEARCHER_TARGETING", 0)),
                             "victim_spawn_mode": int(sets.get("VICTIM_SPAWN_MODE", 0))},
                     "switches": {k: v for k, v in sets.items() if k in FB3.FIX3B_KEYS}, "bp_switches": bp,
                     "crn": {"on": True, "crn_draws": 777},
                     "inst": {"error_count": 0, "broken": False, "overhead": w, "src": {"root": WT + arm, "n": 4}},
                     "timing": {"wall": w}, "probe": "fb3 " + arm, "coverage": [[1, 0.5], [2, 0.75]]},
             "mr": {"mr1_list": mr1, "mr1_steps": rows, "n_observations": nobs, "errors": [], "probe": "mr " + arm},
             "ut": {"errors": [], "probe": "ut " + arm, "n": 3},
             "mf2": {"probe": "mf2 " + arm, "rows": [[1, 2]]},
             "fx3": {"probe": "fx3 " + arm, "ws": {"1": {"steps_since_detection": 3}}}}
        reach = {"probe": "ist3 reach v1", "repo": WT, "f2_present": True, "chain_exit": 0,
                 "truthy": {"fail_safe_planner": {"bool": 40, "None": 4}, "global_mission_planner": {"bool": 12},
                            "local_uav_path_planner": {"bool": 30}},
                 "maintain": {}, "safe_float": {"float": 900, "int": 12}, "params": {}, "context": {},
                 "plain_scalar": {}, "plain_scalar_callers": {}, "plain_scalar_converted": {},
                 "calls": {"plain_scalar": 912, "_is_maintain_option": 0, "evaluate_option": 77}, "errors": []}
        log = ("[%s] start repo=%s\n%s: step %d wall=%.3fs\nchain exit 0 in %s wall=%ss\n"
               % (name, WT, name, steps, w, WT.replace("\\", "/"), 2 * w))
        out[name] = (d, {"argv": ln["argv"], "cwd": ln["cwd"]}, reach, log)
    return out


def _write_recs(lines, recs) -> None:
    by = {ln["name"]: ln for ln in lines}
    for name, (d, sig, reach, log) in recs.items():
        o = by[name]["out"]
        for path, obj in ((o, d), (o + ".argv", sig), (o + ".reach.json", reach)):
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(obj, fh)
        with open(o + ".poollog", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(log)


@contextlib.contextmanager
def _mutated(path, fn=None, text=None, remove=False):
    """Temporarily change a JSON file (fn(d) in place), replace its text, or remove it; restored after."""
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        if remove:
            os.remove(path)
        elif text is not None:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        else:
            d = json.loads(raw.decode("utf-8"))
            fn(d)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(d, fh)
        yield
    finally:
        with open(path, "wb") as fh:
            fh.write(raw)


def _selftest_body(base: str, case) -> None:
    Q = _load("_ist3_queue_dqist_st", "_ist3_queue.py")
    A = _load("_ist3_analyze_dqist_st", "_ist3_analyze.py")
    SD = _load("_sd_probe_dqist_st", "_sd_probe.py")
    FB3 = _load("_fb3_probe_dqist_st", "_fb3_probe.py")
    orig_build = build_lines
    H = "ab12cd34" + "5e" * 16
    H2 = "f0" * 20
    sha0 = {p: hashlib.sha256(p.encode()).hexdigest() for p in (
        "agents.py", "common_fixed_variables.py", "wildfire_model.py", "src_extension/planning/utility_evaluation.py",
        "src_extension/planning/joint_dispatch.py", "tests/test_dispatch.py", "docs/notes.md") + CHAIN_FILES}
    stat0 = {p: [1000 + i, 1700000000000000000 + i] for i, p in enumerate(sorted(sha0))}
    fr0 = {"phase": "launch", "head": H, "status": "", "untracked_outside_outputs": [], "sha": sha0, "stat": stat0}

    # ---- F: run-loaded classification (the freeze's FAIL / NOTE split)
    case("F1 run_loaded: root *.py, src_extension/ and the chain files are run-loaded; outputs/ (not chain), tests/, "
         "*.md / *.txt are not",
         run_loaded("agents.py") and run_loaded("src_extension/planning/joint_dispatch.py")
         and run_loaded("outputs/_ist3_reach.py") and run_loaded("outputs/_ist3_analyze.py")
         and not run_loaded("outputs/_dq_ist_result.txt") and not run_loaded("outputs/_dq_ist.py")
         and not run_loaded("tests/test_dispatch.py") and not run_loaded("docs/notes.md")
         and not run_loaded("README.md"))

    # ---- P: every path is built from WT, not from __file__ (review MINOR 6)
    me = os.path.abspath(__file__)
    recased = os.path.join(os.path.dirname(me).swapcase(), os.path.basename(me))
    spec = importlib.util.spec_from_file_location("_dq_ist_recased_st", recased)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                 # definitions only: the __main__ block does not run
    want_p = {"WRAPPER": os.path.join(WT, "outputs", "_ist3_reach.py"),
              "QUEUE": os.path.join(WT, "outputs", "_dq_q_ist.jsonl"),
              "OUT_DIR": os.path.join(WT, "outputs", "_dq_ist"),
              "RESULT": os.path.join(WT, "outputs", "_dq_ist_result.txt"),
              "FREEZE_LAUNCH": os.path.join(WT, "outputs", "_dq_ist", "_freeze_launch.json"),
              "FREEZE_COMPLETE": os.path.join(WT, "outputs", "_dq_ist", "_freeze_complete.json"),
              "REF_DIR": os.path.join(WT, "outputs"), "MVG_REF_DIR": os.path.join(WT, "outputs", "_mvg_ist")}
    got_p = {k: getattr(mod, k, None) for k in want_p}
    case("P1 (negative control of the input) the module loaded under a differently cased path has a __file__ whose "
         "directory differs from WT/outputs as a string", mod.HERE != os.path.join(WT, "outputs")
         and os.path.normcase(mod.HERE) == os.path.normcase(HERE), (mod.HERE, HERE))
    case("P2 ...and still builds every queue / record / reference path exactly from WT (a write or analyze invoked "
         "through another spelling freezes the same 'out' strings)", got_p == want_p,
         {k: v for k, v in got_p.items() if v != want_p[k]})

    # ---- X: a STOP raised inside a helper exits with the documented code, never 1 (review MINOR 3)
    def raiser(exc):
        def fn(*_a):
            raise exc
        return fn
    PX = _paths(os.path.join(base, "x"))         # never the real outputs/ paths, even if a STOP stopped firing
    reached = []

    def guard(name, ret=None):
        def fn(*_a, **_k):
            reached.append(name)
            return ret
        return fn
    XG = dict(PX, _here_ok=lambda: True, collision_check=guard("collision_check", ([], [])),
              freeze_record=guard("freeze_record", {}), rebuild_accessors=guard("rebuild_accessors", {}),
              resolve_head=guard("resolve_head", (None, "guard")))
    xs, xbuf = [], io.StringIO()
    with contextlib.redirect_stdout(xbuf), contextlib.redirect_stderr(xbuf):
        with _patched(**dict(XG, analyze=raiser(SystemExit("STOP: k_configs")),
                             write=raiser(SystemExit("STOP: build_lines")))):
            xs.append(("analyze SystemExit('STOP: ...')", _exit_code(lambda: main(["x", "analyze"])), 3))
            xs.append(("write SystemExit('STOP: ...')",
                       _exit_code(lambda: main(["x", "write", "--head", "ab12cd34"])), 2))
        with _patched(**dict(XG, analyze=lambda *a: _dq().stop("git failed"))):
            xs.append(("analyze _dq_queue.stop()", _exit_code(lambda: main(["x", "analyze"])), 3))
        with _patched(**dict(XG, analyze=raiser(RuntimeError("git rev-parse failed")))):
            xs.append(("analyze RuntimeError", _exit_code(lambda: main(["x", "analyze"])), 3))
        with _patched(**dict(XG, build_lines=lambda Qm: k_configs(Qm, {"configs": []}))):
            xs.append(("analyze, the real k_configs STOP", _exit_code(lambda: main(["x", "analyze"])), 3))
            xs.append(("write, the real k_configs STOP",
                       _exit_code(lambda: main(["x", "write", "--head", "ab12cd34"])), 2))
    bad_x = [x for x in xs if x[1] != x[2]]
    case("X1 a STOP inside write / analyze (SystemExit from k_configs / build_lines, _dq_queue.stop(), a crash) exits "
         "2 / 3, never Python's 1 (analyze's FAIL); the STOP text is printed; nothing past the STOP ran",
         not bad_x and xbuf.getvalue().count("STOP (") == 6 and "STOP: k_configs" in xbuf.getvalue()
         and not reached and not os.path.exists(PX["QUEUE"]) and not os.path.exists(PX["OUT_DIR"]),
         (bad_x, reached, xbuf.getvalue()[-400:]))
    ctl = []
    with contextlib.redirect_stdout(io.StringIO()):
        with _patched(**dict(XG, analyze=lambda *a: 1, write=lambda *a: 0)):
            ctl.append(_exit_code(lambda: main(["x", "analyze"])))
            ctl.append(_exit_code(lambda: main(["x", "write", "--head", "ab12cd34"])))
        with _patched(**dict(XG, analyze=lambda *a: 0)):
            ctl.append(_exit_code(lambda: main(["x", "analyze"])))
        with _patched(**dict(XG, _here_ok=lambda: False)):
            ctl.append(_exit_code(lambda: main(["x", "analyze"])))
            ctl.append(_exit_code(lambda: main(["x", "write"])))
    case("X2 (positive controls) analyze FAIL stays 1, PASS 0, write 0; the location refusal is 3 / 2", ctl
         == [1, 0, 0, 3, 2], ctl)

    # ---- B: the run lines (the real frozen isTrue inputs, read only)
    PB = _paths(os.path.join(base, "b"))
    with _patched(**PB):
        frozen = ist3_lines()
        ks = k_configs(Q)
        lines = build_lines(Q)
        ok, why = len(lines) == 24, []
        want_names = ["%s%s_%s" % (TAG_PREFIX, arm, c["cid"]) for c in ks for arm in ARMS]
        if [ln["name"] for ln in lines] != want_names:
            ok, why = False, why + ["names / order"]
        for ln in lines:
            arm, cid = ln["name"].split("_", 2)[1], ln["name"].split("_", 2)[2]
            ref = frozen["ist3_%s_%s" % (SRC_ARM[arm], cid)]["argv"]
            pos = [k for k in range(len(ref)) if ref[k] != ln["argv"][k]]
            want = [0, ref.index("--repo") + 1, ref.index("--out") + 1, ref.index("--tag") + 1]
            sets = [ln["argv"][j + 1] for j in range(len(ln["argv"]) - 1) if ln["argv"][j] == "--set"]
            if (len(ref) != len(ln["argv"]) or pos != sorted(want) or ln["argv"][0] != WRAPPER or ln["cwd"] != WT
                    or ln["argv"][want[1]] != WT or ln["argv"][want[3]] != ln["name"]
                    or ln["out"] != os.path.join(PB["OUT_DIR"], "_sd_%s.json" % ln["name"])
                    or ln["argv"][want[2]] != ln["out"]
                    or any(s.startswith(DISPATCH_PREFIX) or s.split("=")[0] in FF_KEYS for s in sets)
                    or (("MR1_TRUTHINESS_FIX=0" in sets and "NUMPY_SCALAR_FLAGS=0" in sets) != (arm == "K"))):
                ok, why = False, why + [ln["name"]]
        case("B1 build_lines: 24 lines dqist_<S|K>_<cid> in isTrue K order; each = its frozen isTrue line with exactly "
             "argv[0], --repo, --out, --tag replaced; cwd the worktree; K alone carries the two isTrue switches; no "
             "DISPATCH_* / FF_* --set", ok, why[:5])
        lines_b = lines

        class FakeQ:                                # _ist3_queue stand-in for the negative controls
            def __init__(self, probe=None, line=None):
                self.PROBE = Q.PROBE if probe is None else probe
                self.configs = Q.configs
                self._line = line or Q.line

            def line(self, c, arm):
                return self._line(c, arm)

        def consistent(line_fn):
            fz = dict(frozen)
            for c in ks:
                for arm in ("F12", "K"):
                    ln = json.loads(json.dumps(line_fn(c, arm)))
                    fz[ln["name"]] = ln
            return fz

        code, outp = _run(build_lines, FakeQ(), consistent(Q.line))
        case("B2 (positive control of the stand-in) FakeQ with the real line() and a consistent frozen set builds the "
             "same 24 lines", code == lines_b, outp[-200:])
        tamper = copy.deepcopy(frozen)
        name0 = "ist3_F12_%s" % ks[0]["cid"]
        tamper[name0]["argv"][tamper[name0]["argv"].index("--seed") + 1] = "1"
        code, outp = _run(build_lines, Q, tamper)
        case("B3 a frozen isTrue line that differs from _ist3_queue.line() STOPS", code == "SystemExit"
             and "differs from _ist3_queue.line()" in outp, outp[-200:])

        def k_short(c, arm):
            ln = Q.line(c, arm)
            if arm == "K":
                i = ln["argv"].index("NUMPY_SCALAR_FLAGS=0")
                del ln["argv"][i - 1:i + 1]
            return ln
        code, outp = _run(build_lines, FakeQ(line=k_short), consistent(k_short))
        case("B4 an isTrue K line that is not its F12 line + the two isTrue switches STOPS", code == "SystemExit"
             and "is not its F12 line" in outp, outp[-200:])

        def with_set(item):
            def fn(c, arm):
                ln = Q.line(c, arm)
                i = ln["argv"].index("--set", ln["argv"].index("--seed")) + 4      # after VICTIM_SPAWN_MODE
                ln["argv"][i:i] = ["--set", item]
                return ln
            return fn
        for label, item in (("B5", "DISPATCH_JOINT=1"), ("B6", "DISPATCH_STALL_STEPS=10"),
                            ("B7", "FF_APPROACH_PATH=1"),
                            ("B10 (an FF_* key outside the three movement switches)", "FF_RELEASE_DETECTED_ONLY=1"),
                            ("B11 (an FF_* key outside the three movement switches)", "FF_EXIT_LEG_MODE=0")):
            code, outp = _run(build_lines, FakeQ(line=with_set(item)), consistent(with_set(item)))
            case("%s a source line that sets %s STOPS (the flipped defaults must decide)" % (label, item),
                 code == "SystemExit" and item.split("=")[0] in outp and "flipped defaults" in outp, outp[-200:])
        code, outp = _run(build_lines, FakeQ(probe=r"X:\other\_ist3_reach.py"), frozen)
        case("B8 a source line whose argv[0] is not _ist3_queue.PROBE STOPS",
             code == "SystemExit" and "argv[0]" in outp, outp[-200:])
        code, outp = _run(k_configs, Q, {"configs": []})
        case("B9 an _ist3_configs.json that differs from _ist3_queue.configs() STOPS",
             code == "SystemExit" and "differs" in outp, outp[-200:])

    # ---- C: the accessor reconstruction (in process, fake agents / common_fixed_variables)
    cfv = types.SimpleNamespace(FF_APPROACH_PATH=1, FF_RETREAT_KEEP_APPROACH=1, FF_FIX_STRANDING_GUARD=1,
                                MR1_TRUTHINESS_FIX=1, NUMPY_SCALAR_FLAGS=1, DISPATCH_JOINT=1, DISPATCH_REASSIGN=1,
                                DISPATCH_STALL_STEPS=10)

    def fix2(key):
        return lambda: getattr(cfv, key, 1) != 0

    am = types.SimpleNamespace(**{a: fix2(k) for a, k in zip(ACCESSORS[:5], FF_KEYS + ISTRUE_KEYS)})
    am.dispatch_joint = lambda: getattr(cfv, "DISPATCH_JOINT", 0) == 1
    am.dispatch_reassign = lambda: am.dispatch_joint() and getattr(cfv, "DISPATCH_REASSIGN", 0) == 1
    got = _accessor_values(am, cfv, {"S": {"NUM_AGENTS": 5}, "K": dict(WANT_PARAMS["K"]),
                                     "J0": {"DISPATCH_JOINT": 0}, "R0": {"DISPATCH_REASSIGN": 0}})
    case("C1 accessors from params: S all True; K the two isTrue False, dispatch + movement True",
         got["S"] == WANT_ACC["S"] and got["K"] == WANT_ACC["K"], got)
    case("C2 (negative) DISPATCH_JOINT=0 in params turns dispatch_joint AND dispatch_reassign off; DISPATCH_REASSIGN=0 "
         "turns dispatch_reassign off - the SW comparison flags exactly those",
         [a for a in ACCESSORS if got["J0"][a] is not WANT_ACC["S"][a]] == ["dispatch_joint", "dispatch_reassign"]
         and [a for a in ACCESSORS if got["R0"][a] is not WANT_ACC["S"][a]] == ["dispatch_reassign"], got)
    case("C3 params are restored after each run (an added key removed, a changed key reset); _raw lists every "
         "DISPATCH_* key",
         cfv.DISPATCH_JOINT == 1 and cfv.MR1_TRUTHINESS_FIX == 1 and not hasattr(cfv, "NUM_AGENTS")
         and got["_raw"].get("DISPATCH_JOINT") == 1 and got["_raw"].get("DISPATCH_STALL_STEPS") == 10, got["_raw"])
    good = {"_S": got["S"], "_K": got["K"], "_raw": got["_raw"]}
    case("C4 defaults_problems: the flip's defaults pass", defaults_problems(good) == [], defaults_problems(good))
    cfv.DISPATCH_JOINT = 0
    bad = _accessor_values(am, cfv, {"_S": {}, "_K": dict(WANT_PARAMS["K"])})
    cfv.DISPATCH_JOINT = 1
    pb = defaults_problems(bad)
    case("C5 (negative) defaults with DISPATCH_JOINT = 0 (the pre-flip tree) are refused: both arms' dispatch "
         "accessors and the raw value",
         len(pb) == 3 and "dispatch_joint" in pb[0] and "DISPATCH_JOINT = 0" in pb[2], pb)
    pe = defaults_problems({"_error": "boom"})
    case("C6 (negative) an accessor child error is refused", pe == ["accessor child: boom"], pe)

    # ---- G: --head resolution
    def raise_git(*_a):
        raise RuntimeError("unknown revision")
    case("G1 resolve_head: a hex prefix that git resolves to a full sha starting with it is accepted",
         resolve_head(H[:8], git=lambda *a: H + "\n") == (H, None))
    case("G2 (negative) a non-hex, a too-short, an unresolvable or a mis-resolved --head is refused",
         resolve_head("xyz1234", git=lambda *a: H)[0] is None and resolve_head("ab12", git=lambda *a: H)[0] is None
         and resolve_head(H[:8], git=raise_git)[0] is None and resolve_head(H[:8], git=lambda *a: H2)[0] is None
         and resolve_head(None)[0] is None)

    # ---- D: untracked files outside outputs/ without a git status walk
    tree = os.path.join(base, "tree")

    def mk(rel, data="x"):
        p = os.path.join(tree, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(data)
    for rel in ("agents.py", "new_root.py", ".venv/Lib/site.py", ".git", "outputs/dqist_x.json", "outputs/y.txt",
                "src_extension/a.py", "src_extension/sub/b.py", "src_extension/sub/new.py",
                "src_extension/sub/__pycache__/b.cpython-312.pyc", "src_extension/newpkg/c.py", "tests/test_a.py",
                "docs/d.md"):
        mk(rel)
    os.makedirs(os.path.join(tree, "src_extension", "emptydir"))
    tracked = ["agents.py", "src_extension/a.py", "src_extension/sub/b.py", "tests/test_a.py", "docs/d.md",
               "outputs/y.txt"]
    seen, asked = [], []

    def ign(paths):
        seen.extend(paths)
        return {p for p in paths if p.rstrip("/").rsplit("/", 1)[-1] in (".venv", "__pycache__")}

    def oth_all(c):                              # stand-in for untracked_in: every non-empty candidate has content
        asked.append(c)
        return [c]
    got_u = untracked_outside_outputs(tree, tracked, ign, oth_all)
    case("D1 untracked outside outputs/: an untracked root file, an untracked file in a tracked directory and a wholly "
         "untracked directory ('dir/', not entered) are found; ignored entries, an empty directory and outputs/ "
         "are not",
         got_u == ["new_root.py", "src_extension/newpkg/", "src_extension/sub/new.py"]
         and not any(p.startswith("outputs") or (p.startswith(".venv/") and p != ".venv/") for p in seen)
         and asked == ["src_extension/newpkg/"], (got_u, seen, asked))
    for rel in ("new_root.py", "src_extension/sub/new.py", "src_extension/newpkg/c.py"):
        os.remove(os.path.join(tree, *rel.split("/")))
    os.rmdir(os.path.join(tree, "src_extension", "newpkg"))
    got_u = untracked_outside_outputs(tree, tracked, ign, oth_all)
    case("D2 (positive control) the same tree without them reports nothing", got_u == [], got_u)

    # ---- D3-D8: git status's normal-mode rule, on a REAL scratch git repository (review MAJOR M1)
    R = _scratch_repo(os.path.join(base, "gitrepo"))

    def mkr(rel, data="x\n"):
        p = os.path.join(R, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(data)
    r_tracked = (".gitignore", "agents.py", "src_extension/a.py", "src_extension/sub/b.py", "tests/test_a.py",
                 "outputs/y.txt")
    for rel in r_tracked:
        mkr(rel, "__pycache__/\n.venv/\n" if rel == ".gitignore" else "x\n")
    _git("add", "--", *r_tracked, root=R)
    for d in ("ProjectsSAS_wt_dqmut/_base", "emptyonly/a/b"):                  # (a) only empty directories
        os.makedirs(os.path.join(R, *d.split("/")))
    mkr(".pytest_cache/.gitignore", "# Created by pytest automatically.\n*\n")  # (b) its own .gitignore: all ignored
    mkr(".pytest_cache/v/cache/lastfailed", "{}\n")
    mkr(".pytest_cache/README.md")
    mkr("pkg/__pycache__/m.cpython-310.pyc")                                    # (c) only ignored files, root level
    mkr("src_extension/newpkg2/__pycache__/x.cpython-310.pyc")                  # (c) in a tracked directory
    mkr(".venv/Lib/site.py")                                                    # an ignored directory
    for rel in ("real_untracked.py", "deepdir/a/b/r.txt", "src_extension/newpkg/c.py", "src_extension/sub/new.py",
                "mixed/__pycache__/z.pyc", "mixed/keep.txt", "outputs/dqist_x.json"):
        mkr(rel)                                                                # real untracked content (controls)
    real_u = ["deepdir/", "mixed/", "real_untracked.py", "src_extension/newpkg/", "src_extension/sub/new.py"]
    r_list = [p for p in _git("ls-files", "-z", "--", ".", ":(exclude)outputs", root=R).split("\0") if p]
    calls = []

    def oth_rec(c):
        calls.append(c)
        return untracked_in(c, R)
    got_r = untracked_outside_outputs(R, r_list, None, oth_rec)
    case("D3 (a) an untracked directory holding only empty directories (the ProjectsSAS_wt_dqmut/_base shape) is not "
         "reported", "ProjectsSAS_wt_dqmut/" not in got_r and "emptyonly/" not in got_r, got_r)
    case("D4 (b) an untracked directory whose contents its own nested .gitignore ignores (.pytest_cache/) is not "
         "reported", ".pytest_cache/" not in got_r, got_r)
    case("D5 (c) a non-ignored untracked directory holding only ignored files (pkg/__pycache__/, and the same inside a "
         "tracked directory) is not reported", "pkg/" not in got_r and "src_extension/newpkg2/" not in got_r, got_r)
    case("D6 (positive control) every real untracked entry IS reported: a root file, a directory whose only file is "
         "nested under subdirectories, a wholly untracked directory and a file in tracked directories, a directory "
         "holding ignored AND real files", all(p in got_r for p in real_u), (got_r, real_u))
    oracle = sorted(p for p in _git("ls-files", "--others", "--exclude-standard", "--directory", "--no-empty-directory",
                                    "-z", "--", ".", ":(exclude)outputs", root=R).split("\0") if p)
    case("D7 the result equals git's own normal-mode listing on the scratch repository exactly (ls-files --others "
         "--exclude-standard --directory --no-empty-directory -- . ':(exclude)outputs')",
         got_r == oracle == real_u, (got_r, oracle))
    case("D8 git is asked once per surviving candidate DIRECTORY, with that candidate alone as the pathspec (never "
         "'.', an ignored directory or outputs/)", sorted(calls) == sorted(
             ["ProjectsSAS_wt_dqmut/", "emptyonly/", ".pytest_cache/", "pkg/", "src_extension/newpkg2/", "deepdir/",
              "mixed/", "src_extension/newpkg/"]), sorted(calls))

    # ---- F2: freeze_record (real git on the scratch repository) records [size, mtime_ns] (review MINOR 7)
    real_git = _git

    def git_r(*a, root=None):                    # the scratch repository has no commit: HEAD is answered here
        return H + "\n" if a[:2] == ("rev-parse", "HEAD") else real_git(*a, root=root)
    with _patched(_git=git_r):
        fa = freeze_record("launch", root=R)
        ap = os.path.join(R, "agents.py")
        sa = os.stat(ap)
        os.utime(ap, ns=(sa.st_atime_ns, sa.st_mtime_ns + 2 * 10 ** 9))     # rewritten with the same content
        fb = freeze_record("complete", root=R)
    moved = sorted(p for p in fa["stat"] if fa["stat"][p] != fb["stat"].get(p))
    case("F2 freeze_record records sha AND [size, mtime_ns] per hashed file (None for a missing chain file); a "
         "same-content rewrite moves the stat only; its untracked list is D7's",
         fa["sha"]["agents.py"] == _sha256(ap) == fb["sha"]["agents.py"] and fa["stat"]["agents.py"] == [
             sa.st_size, sa.st_mtime_ns] and moved == ["agents.py"] and fa["sha"] == fb["sha"]
         and fa["stat"]["outputs/_ist3_reach.py"] is None and fa["untracked_outside_outputs"] == real_u,
         (moved, fa.get("stat", {}).get("agents.py"), fa.get("untracked_outside_outputs")))

    # ---- E: the tag collision check (the real _dq_queue.tag_check on synthetic listings / git paths)
    DQ = _dq()
    wto = os.path.join(DQ.WT, "outputs")
    loc = [(wto, wto, "dp0r_A_N"), (os.path.join(wto, "_ffr_logs"), os.path.join(wto, "_ffr_logs"),
                                    "base1511_east_def_101"),
           (os.path.join(MAIN, "outputs"), os.path.join(MAIN, "outputs"), "mvg1r5_A_N"),
           (os.path.join(wto, "_dq_w3"), os.path.join(wto, "_dq_w3"), None)]
    base_ls = {wto: ["_sd_dp0r_A_N.json", "_dq_ist.py", "_dq_queue.py", "_mvg_ist_result.txt"],
               os.path.join(wto, "_ffr_logs"): ["base1511_east_def_101.out"],
               os.path.join(MAIN, "outputs"): ["_sd_mvg1r5_A_N.json", "_mvg_ist", "_mvg_q_ist.jsonl"],
               os.path.join(wto, "_dq_w3"): ["_sd_dq1r7_A_N_KOown.json"]}
    base_git = {"index": ["outputs/_sd_dp0r_A_N.json", "outputs/_dq_ist.py", "outputs/_mvg_ist_result.txt"],
                "history": ["outputs/_sd_dp0r_A_N.json", "outputs/_dq_ist.py",
                            "outputs/_mvg_ist/_sd_mvgist_S_000_CUR_r_AN.json"]}
    cur = {}
    saved = (DQ.locations, DQ._listing, DQ._git_paths)
    PE = _paths(os.path.join(base, "e"))
    try:
        DQ.locations = lambda all_trees=False: list(loc)
        DQ._listing = lambda folder: None if cur["ls"].get(folder) is None else list(cur["ls"][folder])
        DQ._git_paths = lambda kind: list(cur["git"][kind])
        with _patched(**PE):
            lines_e = build_lines(Q)

            def check(ls_add=None, git_add=None, ls_set=None):
                cur["ls"] = copy.deepcopy(base_ls)
                cur["git"] = copy.deepcopy(base_git)
                for k, v in (ls_add or {}).items():
                    cur["ls"][k] = cur["ls"][k] + v
                for k, v in (ls_set or {}).items():
                    cur["ls"][k] = v
                for k, v in (git_add or {}).items():
                    cur["git"][k] = cur["git"][k] + v
                rows, det = collision_check(lines_e)
                return [r[4] for r in rows], det
            v, det = check()
            case("E1 (positive control) clean listings with every control present: every row PASSES; the tool's own "
                 "file _dq_ist.py and the MVG round's mvgist_ names are not hits", all(x.startswith("PASS") for x in v)
                 and len(v) == 9, (v, det))
            hit = "_sd_dqist_K_%s.json.poollog" % ks[2]["cid"]
            v, det = check(ls_add={os.path.join(MAIN, "outputs"): [hit]})
            case("E2 a run name in another tree's outputs/ listing FAILS", any(x == "FAIL" for x in v)
                 and any(hit in d_ for d_ in det), (v, det))
            v, det = check(git_add={"history": ["outputs/_dq_ist/_sd_dqist_S_%s.json" % ks[0]["cid"]]})
            case("E3 a run name added anywhere in git history FAILS (tag row and own-name row)",
                 sum(1 for x in v if x == "FAIL") == 2, (v, det))
            v, det = check(ls_add={wto: ["dqist_notes.txt"]})
            case("E4 a name carrying only the prefix 'dqist_' FAILS by the _mvg_ist rule alone",
                 v[-1] == "FAIL" and all(x.startswith("PASS") for x in v[:-1]), (v, det))
            v, det = check(ls_add={wto: ["_dq_ist"]})
            case("E5 an existing outputs/_dq_ist entry in a listing FAILS", v[-1] == "FAIL", (v, det))
            v, det = check(git_add={"index": ["outputs/_dq_q_ist.jsonl"]})
            case("E6 a tracked outputs/_dq_q_ist.jsonl FAILS", v[-1] == "FAIL", (v, det))
            v, det = check(ls_set={os.path.join(wto, "_ffr_logs"): ["other.out"]})
            case("E7 a listing whose positive control is missing is BLIND (FAIL)", "FAIL (BLIND)" in v, (v, det))
            os.makedirs(PE["OUT_DIR"])
            with open(lines_e[0]["out"], "w", encoding="utf-8") as fh:
                fh.write("{}")
            v, det = check()
            case("E8 a run's own output already on disk FAILS (_dq_queue's own-outputs row)", v[0] == "FAIL"
                 and any(lines_e[0]["out"] in d_ for d_ in det), (v, det))
            os.remove(lines_e[0]["out"])
            with open(lines_e[1]["out"] + ".reach.json", "w", encoding="utf-8") as fh:
                fh.write("{}")
            v, det = check()
            case("E9 a run's .reach.json (or the output directory) already on disk FAILS", v[1] == "FAIL"
                 and any(d_.endswith(".reach.json") for d_ in det) and any(d_.endswith("_dq_ist") for d_ in det),
                 (v, det))
            shutil.rmtree(PE["OUT_DIR"])
            with open(PE["RESULT"], "w", encoding="utf-8") as fh:
                fh.write("x")
            v, det = check()
            case("E10 an existing result file FAILS", v[1] == "FAIL", (v, det))
            os.remove(PE["RESULT"])
    finally:
        DQ.locations, DQ._listing, DQ._git_paths = saved

    # ---- W: write
    ok_coll = lambda lines_: ([["fake tag check", "1", "0", "-", "PASS"]], [])         # noqa: E731
    fake_head = lambda arg: (H, None) if H.startswith(str(arg).lower()) else (None, "not a commit here")  # noqa: E731
    common = {"freeze_record": _fake_freeze(fr0), "rebuild_accessors": _fake_acc(), "collision_check": ok_coll,
              "resolve_head": fake_head}
    PW = _paths(os.path.join(base, "w"))
    with _patched(**dict(common, **PW)):
        code, outp = _run(write, None)
        case("W1 write without --head STOPS, nothing written", code == 2 and "needs --head" in outp
             and not os.path.exists(PW["QUEUE"]) and not os.path.exists(PW["OUT_DIR"]), outp[-200:])
        code, outp = _run(write, "ffff0000")
        case("W2 write with a --head that does not resolve STOPS, nothing written", code == 2
             and "not a commit" in outp and not os.path.exists(PW["QUEUE"]), outp[-200:])
        code, outp = _run(write, H[:8])
        with open(PW["QUEUE"], "rb") as fh:
            qraw = fh.read()
        with open(PW["FREEZE_LAUNCH"], encoding="utf-8") as fh:
            f0w = json.load(fh)
        case("W3 (positive) write --head <prefix>: the 24-line LF queue == build_lines; the launch record holds "
             "flip_head (full), head_arg (as given) and the defaults read",
             code == 0 and b"\r" not in qraw and [json.loads(x) for x in qraw.decode().splitlines()]
             == json.loads(json.dumps(build_lines(Q))) and f0w.get("flip_head") == H and f0w.get("head_arg") == H[:8]
             and "_S" in (f0w.get("defaults") or {}) and f0w.get("head") == H, outp[-300:])
        case("W3-RULE (review MINOR 5) the orchestration rule is stated where the orchestrator reads it: write's "
             "success output and the docstring say no commit may land between write and the end of the 24th run",
             "RULE: no commit in %s until the 24th run has finished" % WT in outp
             and "NO COMMIT in this worktree between `write` and the end of the 24th run" in (__doc__ or ""),
             outp[-300:])
        code, outp = _run(write, H[:12])
        case("W4 write again with the same head: unchanged (frozen)", code == 0 and "unchanged" in outp, outp[-200:])
        code, outp = _run(write, "ffff0000")
        case("W5 write again under another --head STOPS (frozen for its flip head)", code == 2
             and "frozen for the flip head" in outp, outp[-200:])
        bad_h = []
        for arg in (H[:2], H[:6], H[:3] + "z" * 5, H + "0"):
            code, outp = _run(write, arg)
            if code != 2 or "not a hex commit sha" not in outp:
                bad_h.append((arg, code, outp[-120:]))
        case("W5-SHA (review MINOR 7) on the FROZEN queue, a --head that is a 1-6 character prefix of the flip head, "
             "non-hex or over 40 characters STOPS before the frozen-head comparison (it used to pass as 'unchanged')",
             not bad_h, bad_h)
        with _mutated(PW["QUEUE"], text=qraw.decode() + "{}\n"):
            code, outp = _run(write, H[:8])
            with open(PW["QUEUE"], "rb") as fh:
                kept = fh.read() == qraw + b"{}\n"
        case("W6 a frozen queue that differs STOPS and is not re-written", code == 2 and "differs" in outp and kept,
             outp[-200:])
    refusals = (
        ("W7 a tag collision", {"collision_check": lambda lines_: ([["x", "1", "1", "-", "FAIL"]], ["TAG IN USE x"])},
         "tag collision"),
        ("W8 HEAD is not --head", {"freeze_record": _fake_freeze(dict(fr0, head=H2))}, "HEAD"),
        ("W9 a modified tracked file", {"freeze_record": _fake_freeze(dict(fr0, status=" M tests/test_dispatch.py\n"))},
         "tracked files modified"),
        ("W10 an untracked file outside outputs/", {"freeze_record": _fake_freeze(
            dict(fr0, untracked_outside_outputs=["x.py"]))}, "untracked files outside outputs/"),
        ("W11 a missing chain file", {"freeze_record": _fake_freeze(
            dict(fr0, sha=dict(sha0, **{"outputs/_ist3_reach.py": "missing"})))}, "missing files"),
        ("W12 pre-flip defaults (DISPATCH_JOINT 0: both dispatch accessors off)", {"rebuild_accessors": _fake_acc(
            override={"_S": {"dispatch_joint": False, "dispatch_reassign": False},
                      "_K": {"dispatch_joint": False, "dispatch_reassign": False}}, raw={"DISPATCH_JOINT": 0})},
         "DISPATCH_JOINT = 0"),
        ("W13 dispatch_reassign off at the defaults", {"rebuild_accessors": _fake_acc(
            override={"_S": {"dispatch_reassign": False}}, raw={"DISPATCH_REASSIGN": 0})}, "dispatch_reassign"),
        ("W14 a movement default off", {"rebuild_accessors": _fake_acc(
            override={"_K": {"ff_fix_stranding_guard": False}}, raw={"FF_FIX_STRANDING_GUARD": 0})},
         "FF_FIX_STRANDING_GUARD"),
        ("W15 the accessor child failed", {"rebuild_accessors": _fake_acc(error="boom")}, "boom"),
    )
    for i, (label, over, expect) in enumerate(refusals):
        P = _paths(os.path.join(base, "w%d" % i))
        with _patched(**dict(common, **P, **over)):
            code, outp = _run(write, H[:8])
        case("%s STOPS write and nothing is written" % label, code == 2 and expect in outp
             and not os.path.exists(P["QUEUE"]) and not os.path.exists(P["OUT_DIR"]), outp[-300:])

    # ---- H: analyze end to end on synthetic records
    PA = _paths(os.path.join(base, "a"))
    same_cid = ks[8]["cid"]
    with _patched(**dict(common, **PA)):
        code, outp = _run(write, H[:8])
        if code != 0:
            case("H setup: write for the analyze tests", False, outp[-300:])
            return
        lines_a = build_lines(Q)
        recs = _synth(lines_a, H, sha0, A, SD, FB3, same_cid=same_cid)
        _write_recs(lines_a, recs)
        os.makedirs(PA["REF_DIR"])
        ref_same = copy.deepcopy(recs["%sS_%s" % (TAG_PREFIX, ks[0]["cid"])][0])
        ref_same.update(tag="ist3_F12_x", head="6904b1f8", wall_s=1.0)
        ref_diff = copy.deepcopy(recs["%sK_%s" % (TAG_PREFIX, ks[1]["cid"])][0])
        ref_diff["eval"]["rescued"] = 99
        for fname, obj in (("_sd_ist3_F12_%s.json" % ks[0]["cid"], ref_same),
                           ("_sd_ist3_K_%s.json" % ks[1]["cid"], ref_diff)):
            with open(os.path.join(PA["REF_DIR"], fname), "w", encoding="utf-8") as fh:
                json.dump(obj, fh)
        # the MVG round's records (INFO column mvg): S and K of ks[2] equal (labels / head / wall aside), S of ks[3]
        # differs in an outcome field
        os.makedirs(PA["MVG_REF_DIR"])
        mvg_refs = {}
        for arm in ARMS:
            m = copy.deepcopy(recs["%s%s_%s" % (TAG_PREFIX, arm, ks[2]["cid"])][0])
            m.update(tag="%s%s_%s" % (MVG_PREFIX, arm, ks[2]["cid"]), head="980d9338" + "0" * 32, wall_s=3.0)
            mvg_refs["_sd_%s%s_%s.json" % (MVG_PREFIX, arm, ks[2]["cid"])] = m
        m = copy.deepcopy(recs["%sS_%s" % (TAG_PREFIX, ks[3]["cid"])][0])
        m["eval"]["dead"] = 3
        mvg_refs["_sd_%sS_%s.json" % (MVG_PREFIX, ks[3]["cid"])] = m
        for fname, obj in mvg_refs.items():
            with open(os.path.join(PA["MVG_REF_DIR"], fname), "w", encoding="utf-8") as fh:
                json.dump(obj, fh)
    n0s, n0k = "%sS_%s" % (TAG_PREFIX, ks[0]["cid"]), "%sK_%s" % (TAG_PREFIX, ks[0]["cid"])
    n1s, n1k = "%sS_%s" % (TAG_PREFIX, ks[1]["cid"]), "%sK_%s" % (TAG_PREFIX, ks[1]["cid"])
    n8k = "%sK_%s" % (TAG_PREFIX, same_cid)
    out_of = {ln["name"]: ln["out"] for ln in lines_a}
    acommon = dict(common, **PA, freeze_record=_fake_freeze(dict(fr0, phase="complete")))

    def an(partial=False, head=None, **over):
        with _patched(**dict(acommon, **over)):
            return _run(analyze, partial, head)

    code, outp = an()
    with open(PA["RESULT"], encoding="utf-8") as fh:
        res_text = fh.read()
    case("H1 (positive) consistent synthetic records: 19.12(c) => PASS, every gate n / 0, the result file is the "
         "printed text; labels / wall-clock / timing differ between the arms and are skipped",
         code == 0 and "19.12(c) => PASS" in outp and res_text == outp and "SvK       12 / 0" in outp
         and "SW        24 / 0" in outp and "G-V       24 / 0 (runs)" in outp and "REACH-S  PASS" in outp
         and "LOG       12 / 0" in outp and "MR1-chg   12 / 0" in outp, outp[-1500:])
    rowline = [x for x in outp.splitlines() if x.startswith(same_cid)]
    case("H2 MR1-chg: a configuration whose corrected and literal counts agree on every step passes as '(same)'; the "
         "others as '(chg)'", len(rowline) == 1 and "ok(same)" in rowline[0] and outp.count("ok(chg)") == 11, rowline)
    ref_line = [x for x in outp.splitlines() if x.startswith("  ref (isTrue")]
    case("H3 INFO never gates: one isTrue record equal (labels aside), one differing - counted, verdict still PASS",
         len(ref_line) == 1 and "S 0 / 12, K 1 / 12 (no record: S 11, K 11)" in ref_line[0]
         and "same" in [x for x in outp.splitlines() if x.startswith(ks[0]["cid"])][0] and code == 0, ref_line)
    mvg_line = [x for x in outp.splitlines() if x.startswith("  mvg (MVG round")]
    row2 = [x for x in outp.splitlines() if x.startswith(ks[2]["cid"])]
    row3 = [x for x in outp.splitlines() if x.startswith(ks[3]["cid"])]
    case("H3-MVG (review MINOR 1) a second INFO column against the MVG round's records of the same configuration and "
         "arm: equal records (labels / head / wall aside) 'same', an outcome change 'differs' with its field named, "
         "no record '-'; never gating (verdict PASS)",
         code == 0 and "19.12(c) => PASS" in outp and len(mvg_line) == 1
         and "S 1 / 12, K 0 / 12 (no record: S 10, K 11)" in mvg_line[0]
         and len(row2) == 1 and row2[0].split("|")[-1].split() == ["same", "same"]
         and len(row3) == 1 and row3[0].split("|")[-1].split() == ["differs", "-"]
         and any(x.startswith("  mvg %s S vs MVG S: 1 differing fields, first ['eval.dead']" % ks[3]["cid"])
                 for x in outp.splitlines()), (mvg_line, row2, row3))
    code, outp = an(head=H[:10])
    case("H4 analyze --head <matching prefix> runs; analyze --head <other> STOPS", code == 0
         and an(head="ffff0000")[0] == 3)
    bad_h = [(arg, an(head=arg)[0]) for arg in (H[:2], H[:6], "zz" + H[2:10])]
    case("H4-SHA (review MINOR 7) analyze --head that is a 1-6 character prefix of the flip head or non-hex STOPS "
         "(exit 3)", all(c_ == 3 for _a, c_ in bad_h), bad_h)

    def gv_case(label, name, expect, fn=None, path_suffix="", text=None, remove=False):
        with _mutated(out_of[name] + path_suffix, fn=fn, text=text, remove=remove):
            code_, outp_ = an()
        line_ = [x for x in outp_.splitlines() if x.startswith("  G-V FAIL %s: " % name)]
        case("H-GV %s FAILS G-V" % label, code_ == 1 and "19.12(c) => FAIL" in outp_ and len(line_) == 1
             and expect in line_[0], line_ or outp_[-600:])

    def put(path, value):
        def fn(d):
            cur_ = d
            for k in path[:-1]:
                cur_ = cur_[k]
            cur_[path[-1]] = value
        return fn

    gv_case("complete False", n0s, "complete=False", put(["complete"], False))
    gv_case("crashed", n0s, "crashed=True", put(["crashed"], "Traceback"))
    gv_case("steps_done short", n0k, "steps_done=359", put(["steps_done"], 359))
    gv_case("another repo", n0s, "repo ", put(["repo"], MAIN))
    gv_case("another head (a commit landed while the runs were pending)", n0s,
            "head %s != %s (the launch record's flip_head; no commit may land between write and the end of the 24 runs)"
            % (H2, H), put(["head"], H2))
    gv_case("another tag", n0s, "tag x", put(["tag"], "x"))
    gv_case("src_sha != the launch freeze", n0s, "src_sha agents.py", put(["src_sha", "agents.py"], "0" * 16))
    gv_case("src_sha missing", n0s, "src_sha missing", put(["src_sha"], {}))
    gv_case("extra_params != the line", n0s, "extra_params", put(["extra_params", "X"], 1))
    gv_case("argv != the line", n0s, "argv differs", put(["argv"], ["x"]))
    gv_case(".argv sidecar differs", n0s, ".argv sidecar differs", put(["cwd"], MAIN), ".argv")
    gv_case(".argv sidecar missing", n0s, ".argv sidecar missing", path_suffix=".argv", remove=True)
    gv_case("eff searcher_targeting", n1s, "eff searcher_targeting", put(["fb3", "eff", "searcher_targeting"], 9))
    gv_case("eff victim_spawn_mode", n1s, "eff victim_spawn_mode", put(["fb3", "eff", "victim_spawn_mode"], 9))
    gv_case("a FIX3B switch not recorded as set", n1s, "switch SEARCHER_TARGETING recorded",
            put(["fb3", "switches", "SEARCHER_TARGETING"], 0))
    gv_case("effective global_planner_mode", n0s, "effective global_planner_mode",
            put(["effective", "global_planner_mode"], 1))
    gv_case("SEARCHER_TARGETING_FIX recorded wrong", n0s, "SEARCHER_TARGETING_FIX recorded",
            put(["fb3", "bp_switches", "SEARCHER_TARGETING_FIX", "eff"], False))
    gv_case("S params carry an isTrue switch", n0s, "params MR1_TRUTHINESS_FIX = 0",
            put(["params", "MR1_TRUTHINESS_FIX"], 0))
    gv_case("K params lack an isTrue switch", n0k, "params NUMPY_SCALAR_FLAGS = 1",
            put(["params", "NUMPY_SCALAR_FLAGS"], 1))
    gv_case("a movement switch in params", n0s, "movement switch FF_APPROACH_PATH",
            put(["params", "FF_APPROACH_PATH"], 1))
    gv_case("DISPATCH_JOINT in params", n0s, "dispatch switch(es) ['DISPATCH_JOINT']",
            put(["params", "DISPATCH_JOINT"], 1))
    gv_case("DISPATCH_REASSIGN in K's extra_params", n0k, "dispatch switch(es) ['DISPATCH_REASSIGN']",
            put(["extra_params", "DISPATCH_REASSIGN"], 1))
    gv_case("any DISPATCH_* key (DISPATCH_STALL_STEPS) in params", n1k, "dispatch switch(es) ['DISPATCH_STALL_STEPS']",
            put(["params", "DISPATCH_STALL_STEPS"], 10))
    gv_case("CRN off", n0s, "CRN not on", put(["fb3", "crn", "on"], False))
    gv_case("CRN without draws", n0s, "CRN not on", put(["fb3", "crn", "crn_draws"], 0))
    gv_case("fb3.inst errors", n0s, "fb3.inst", put(["fb3", "inst", "error_count"], 2))
    gv_case("fb3.inst broken", n0s, "fb3.inst", put(["fb3", "inst", "broken"], True))
    gv_case("mr errors", n0s, "mr errors", put(["mr", "errors"], ["boom"]))
    gv_case("ut errors", n0s, "ut errors", put(["ut", "errors"], ["boom"]))
    gv_case("an mf2 observer error marker", n0s, "mf2 carries", put(["mf2", "x"], "HOOK_ERR y"))
    gv_case("an fx3 observer error marker", n0k, "fx3 carries", put(["fx3", "x"], "ERR z"))
    gv_case("mr1_steps one row short", n0s, "mr record malformed", lambda d: d["mr"]["mr1_steps"].pop())
    gv_case("NUM_AGENTS != the MR1 list length", n0s, "mr record malformed", put(["params", "NUM_AGENTS"], 4))
    gv_case("reach chain_exit 1", n0s, "reach exit 1", put(["chain_exit"], 1), ".reach.json")
    gv_case("reach errors", n0s, "reach exit", put(["errors"], ["observer"]), ".reach.json")
    gv_case("reach f2_present False", n0s, "reach f2_present False", put(["f2_present"], False), ".reach.json")
    gv_case("reach repo another", n0s, "reach repo", put(["repo"], MAIN), ".reach.json")
    gv_case("reach record missing", n0s, "reach record missing", path_suffix=".reach.json", remove=True)
    gv_case("pool log missing (review MINOR 4)", n0s, "poollog missing or empty", path_suffix=".poollog",
            remove=True)
    gv_case("pool log empty (review MINOR 4)", n0k, "poollog missing or empty", path_suffix=".poollog", text="")
    with _mutated(out_of[n1s] + ".poollog", remove=True), _mutated(out_of[n1k] + ".poollog", remove=True):
        code, outp = an()
    gvl = [x for x in outp.splitlines() if x.startswith("  G-V FAIL ") and "poollog missing or empty" in x]
    case("H-GV-LOG2 (review MINOR 4) both pool logs of a configuration missing: LOG alone compares two '<missing "
         "poollog>' stand-ins and passes, so G-V must fail both runs", code == 1 and "19.12(c) => FAIL" in outp
         and len(gvl) == 2 and "LOG       12 / 0" in outp, (gvl, outp[-500:]))
    gv_case("an unparseable record", n0s, "unparseable", text="{")

    # the SEARCHER_FP_* branch: none of the 12 lines sets one, so a stand-in line set (queue re-frozen to match)
    fp_cid = ks[4]["cid"]

    def fp_build(Qm, frozen=None, frozen_cfg=None):
        ls = orig_build(Qm, frozen, frozen_cfg)
        for ln in ls:
            if ln["name"].endswith("_" + fp_cid):
                i = ln["argv"].index("--steps")
                ln["argv"][i:i] = ["--set", "SEARCHER_FP_KAPPA=3"]
        return ls
    with _patched(**PA):
        fp_lines = fp_build(Q)
    fp_recs = _synth([ln for ln in fp_lines if ln["name"].endswith("_" + fp_cid)], H, sha0, A, SD, FB3)
    fp_names = sorted(fp_recs)
    with open(PA["QUEUE"], "rb") as fh:
        q_orig = fh.read()
    saved_recs = {}
    for n in fp_names:
        for suf in ("", ".argv", ".reach.json", ".poollog"):
            with open(out_of[n] + suf, "rb") as fh:
                saved_recs[out_of[n] + suf] = fh.read()
    try:
        with open(PA["QUEUE"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(json.dumps(x) + "\n" for x in fp_lines))
        _write_recs(fp_lines, fp_recs)
        code, outp = an(build_lines=fp_build)
        case("H-FP (positive control) a line with SEARCHER_FP_KAPPA=3 recorded raw 3 / eff 3.0 passes", code == 0,
             outp[-600:])
        fps = [n for n in fp_names if "_S_" in n][0]
        with _mutated(out_of[fps], fn=put(["fb3", "bp_switches", "SEARCHER_FP_KAPPA", "eff"], 2.0)):
            code, outp = an(build_lines=fp_build)
        case("H-FP (negative) SEARCHER_FP_KAPPA recorded eff 2.0 FAILS G-V", code == 1
             and "FP SEARCHER_FP_KAPPA recorded" in outp, outp[-600:])
        with _mutated(out_of[fps], fn=lambda d: d["fb3"]["bp_switches"].pop("SEARCHER_FP_KAPPA")):
            code, outp = an(build_lines=fp_build)
        case("H-FP (negative) a dead SEARCHER_FP_KAPPA (not recorded) FAILS G-V", code == 1
             and "FP SEARCHER_FP_KAPPA recorded {}" in outp, outp[-600:])
    finally:
        with open(PA["QUEUE"], "wb") as fh:
            fh.write(q_orig)
        for p, raw in saved_recs.items():
            with open(p, "wb") as fh:
                fh.write(raw)

    # SW
    for label, over, expect in (
            ("S dispatch_joint False", {n0s: {"dispatch_joint": False}}, "S accessors ['dispatch_joint']"),
            ("S dispatch_reassign False", {n1s: {"dispatch_reassign": False}}, "S accessors ['dispatch_reassign']"),
            ("K dispatch_joint False", {n0k: {"dispatch_joint": False}}, "K accessors ['dispatch_joint']"),
            ("K dispatch_reassign False", {n1k: {"dispatch_reassign": False}}, "K accessors ['dispatch_reassign']"),
            ("K mr1_truthiness_fix True", {n1k: {"mr1_truthiness_fix": True}}, "K accessors ['mr1_truthiness_fix']"),
            ("S numpy_scalar_flags False", {n0s: {"numpy_scalar_flags": False}}, "S accessors ['numpy_scalar_flags']"),
            ("S ff_approach_path False", {n0s: {"ff_approach_path": False}}, "S accessors ['ff_approach_path']")):
        code, outp = an(rebuild_accessors=_fake_acc(override=over))
        case("H-SW %s FAILS SW (23 / 1)" % label, code == 1 and "SW        23 / 1" in outp and expect in outp,
             outp[-500:])
    code, outp = an(rebuild_accessors=_fake_acc(error="boom"))
    case("H-SW an accessor child error is a GLOBAL FAIL", code == 1 and "GLOBAL FAIL SW: boom" in outp, outp[-300:])

    # REACH
    for label, name, fn, ok_expected in (
            ("S numpy bool at a truthy site", n0s, put(["truthy", "fail_safe_planner", "numpy.bool_"], 1), False),
            ("S numpy in evaluated params", n1s, put(["params"], {"w": {"numpy.float64": 2}}), False),
            ("S numpy in context", n1s, put(["context"], {"w": {"numpy.int64": 1}}), False),
            ("S numpy at safe_float", n0s, put(["safe_float", "numpy.float32"], 3), False),
            ("S numpy plain_scalar input", n0s, put(["plain_scalar", "numpy.int64"], 3), False),
            ("S numpy maintain marker", n0s, put(["maintain", "numpy.bool_"], 1), False),
            ("K numpy (reported, not gating)", n0k, put(["truthy", "rescue_planner"], {"numpy.bool_": 5}), True)):
        with _mutated(out_of[name] + ".reach.json", fn=fn):
            code, outp = an()
        case("H-REACH %s => %s" % (label, "PASS" if ok_expected else "REACH-S FAIL"),
             (code == 0 and "REACH-S  PASS" in outp) if ok_expected else (code == 1 and "REACH-S  FAIL" in outp),
             outp[-400:])

    # SvK, G1-a, G1-b, MR1-chg, LOG
    with _mutated(out_of[n0s], fn=put(["eval", "rescued"], 5)):
        code, outp = an()
    case("H-SvK an outcome field that differs between S and K FAILS SvK", code == 1 and "FAIL SvK %s: eval.rescued"
         % ks[0]["cid"] in outp, outp[-400:])
    with _mutated(out_of[n0k], fn=put(["fb3", "coverage"], [[1, 0.5]])):
        code, outp = an()
    case("H-SvK a section field that differs FAILS SvK",
         code == 1 and "FAIL SvK %s: fb3.coverage" % ks[0]["cid"] in outp, outp[-400:])
    with _mutated(out_of[n0s], fn=lambda d: d["mr"]["mr1_list"].__setitem__(0, d["mr"]["mr1_list"][0] + 1e-9)):
        code, outp = an()
    case("H-G1a S mr1_list off the corrected accumulation by 1e-9 FAILS G1-a (alone)", code == 1
         and "G1-a      11 / 1" in outp and "SvK       12 / 0" in outp and "MR1-chg   12 / 0" in outp, outp[-500:])
    with _mutated(out_of[n0k], fn=lambda d: d["mr"]["mr1_list"].__setitem__(0, d["mr"]["mr1_list"][0] + 1e-9)):
        code, outp = an()
    case("H-G1b K mr1_list off the literal accumulation FAILS G1-b (alone)", code == 1 and "G1-b      11 / 1" in outp
         and "MR1-chg   12 / 0" in outp, outp[-500:])
    with _mutated(out_of[n0k], fn=lambda d: d["mr"].__setitem__("mr1_list", recs[n0s][0]["mr"]["mr1_list"])):
        code, outp = an()
    case("H-MR1chg K == S where the counts differ on some step FAILS MR1-chg (and G1-b)", code == 1
         and "FAIL MR1-chg %s: MR1 changed False" % ks[0]["cid"] in outp and "G1-b      11 / 1" in outp, outp[-500:])
    with _mutated(out_of[n8k], fn=lambda d: d["mr"]["mr1_list"].__setitem__(0, d["mr"]["mr1_list"][0] + 0.5)):
        code, outp = an()
    case("H-MR1chg K != S where the counts agree on every step FAILS MR1-chg", code == 1
         and "FAIL MR1-chg %s: MR1 changed True" % same_cid in outp, outp[-500:])
    with open(out_of[n0k] + ".poollog", encoding="utf-8") as fh:
        log_k = fh.read()
    with _mutated(out_of[n0k] + ".poollog", text=log_k + "Traceback (most recent call last)\n"):
        code, outp = an()
    case("H-LOG an extra line in K's pool log FAILS LOG (tag / wall / checkout normalised otherwise)", code == 1
         and "LOG       11 / 1" in outp, outp[-400:])

    # FREEZE
    for label, f1, expect, ok_expected in (
            ("a run-loaded file changed", dict(fr0, sha=dict(sha0, **{"agents.py": "0" * 64})),
             "GLOBAL FAIL run-loaded files changed since launch: ['agents.py']", False),
            ("a chain file changed", dict(fr0, sha=dict(sha0, **{"outputs/_ist3_analyze.py": "0" * 64})),
             "GLOBAL FAIL run-loaded files changed since launch: ['outputs/_ist3_analyze.py']", False),
            ("a src_extension file added", dict(fr0, sha=dict(sha0, **{"src_extension/new.py": "0" * 64})),
             "GLOBAL FAIL run-loaded files changed since launch: ['src_extension/new.py']", False),
            ("a test changed", dict(fr0, sha=dict(sha0, **{"tests/test_dispatch.py": "0" * 64})),
             "NOTE non-run-loaded files changed since launch: ['tests/test_dispatch.py']", True),
            ("HEAD moved, run-loaded files unchanged", dict(fr0, head=H2), "NOTE HEAD moved since launch", True),
            ("a run-loaded file modified at analysis", dict(fr0, status=" M agents.py\n"),
             "GLOBAL FAIL tracked status at analysis", False),
            ("a test modified at analysis", dict(fr0, status=" M tests/test_dispatch.py\n"),
             "NOTE tracked status at analysis", True),
            ("an untracked file outside outputs/ at analysis", dict(fr0, untracked_outside_outputs=["x.py"]),
             "GLOBAL FAIL untracked files outside outputs/ at analysis", False),
            ("(review MINOR 7) the dispatch code rewritten with the same content (stat moved, sha equal: an edit "
             "reverted during the runs, invisible to the records' src_sha)",
             dict(fr0, stat=dict(stat0, **{"src_extension/planning/joint_dispatch.py": [5, 6]})),
             "GLOBAL FAIL run-loaded files rewritten since launch with the same content (size / mtime moved; an edit "
             "reverted during the runs cannot be excluded): ['src_extension/planning/joint_dispatch.py']", False),
            ("(review MINOR 7) a chain file rewritten with the same content",
             dict(fr0, stat=dict(stat0, **{"outputs/_ist3_reach.py": [5, 6]})),
             "GLOBAL FAIL run-loaded files rewritten since launch with the same content", False),
            ("(review MINOR 7, control) a test rewritten with the same content",
             dict(fr0, stat=dict(stat0, **{"tests/test_dispatch.py": [5, 6]})),
             "NOTE non-run-loaded files rewritten since launch with the same content: ['tests/test_dispatch.py']",
             True)):
        code, outp = an(freeze_record=_fake_freeze(dict(f1, phase="complete")))
        case("H-FREEZE %s => %s" % (label, "NOTE, PASS" if ok_expected else "FAIL"),
             expect in outp and ((code == 0 and "=> PASS" in outp) if ok_expected
                                 else (code == 1 and "=> FAIL" in outp)), outp[-500:])
    for label, fn in (("launch record HEAD != flip_head", put(["head"], H2)),
                      ("launch record tree not clean", put(["status"], " M agents.py\n")),
                      ("launch record with an untracked file", put(["untracked_outside_outputs"], ["x.py"]))):
        with _mutated(PA["FREEZE_LAUNCH"], fn=fn):
            code, outp = an()
        case("H-FREEZE %s => GLOBAL FAIL" % label, code == 1 and "GLOBAL FAIL launch record" in outp, outp[-400:])
    with _mutated(PA["FREEZE_LAUNCH"], fn=lambda d: d.pop("stat")):
        code, outp = an()
    case("H-FREEZE (review MINOR 7) a launch record without the stat block => GLOBAL FAIL", code == 1
         and "GLOBAL FAIL launch record has no stat block" in outp, outp[-400:])
    with _mutated(PA["FREEZE_LAUNCH"], fn=put(["flip_head"], H2)):
        code, outp = an()
    case("H-FREEZE a launch record naming another flip head: every run's head FAILS G-V", code == 1
         and "G-V        0 / 24 (runs)" in outp, outp[-400:])
    with _mutated(PA["FREEZE_LAUNCH"], fn=put(["flip_head"], "abc")):
        code, outp = an()
    case("H-FREEZE a launch record whose flip_head is not a full sha STOPS", code == 3, outp[-300:])

    # completeness and the frozen inputs
    with _mutated(out_of[n1k], remove=True):
        code, outp = an()
        code_p, outp_p = an(partial=True)
    case("H-MISSING a missing run STOPS without --partial; with --partial the verdict is INCOMPLETE", code == 3
         and "1 runs missing" in outp and code_p == 1 and "19.12(c) => INCOMPLETE" in outp_p,
         (outp[-200:], outp_p[-200:]))
    with open(PA["QUEUE"], encoding="utf-8") as fh:
        q_text = fh.read()
    with _mutated(PA["QUEUE"], text=q_text.replace("dqist_K_", "dqist_k_", 1)):
        code, outp = an()
    case("H-QUEUE a frozen queue that differs from the re-derived lines STOPS", code == 3 and "differs" in outp,
         outp[-200:])
    with _mutated(PA["FREEZE_LAUNCH"], remove=True):
        code, outp = an()
    case("H-QUEUE no launch freeze record STOPS", code == 3 and "missing" in outp, outp[-200:])
    code, outp = an()
    case("H-RESTORE after every mutation the synthetic set passes again (nothing leaked between cases)",
         code == 0 and "19.12(c) => PASS" in outp, outp[-300:])


def selftest(tmp_root=None) -> int:
    res, fails = [], []

    def case(name, cond, detail=""):
        res.append("%-4s %s%s" % ("PASS" if cond else "FAIL", name,
                                  ("  | " + str(detail)[:600]) if (detail and not cond) else ""))
        if not cond:
            fails.append(name)

    if tmp_root:
        os.makedirs(tmp_root, exist_ok=True)
    base = tempfile.mkdtemp(prefix="dq_ist_selftest_", dir=tmp_root or None)
    try:
        _selftest_body(base, case)
    except Exception:                            # noqa: BLE001 - a crashed self-test is a failure, never a pass
        case("the self-test body completed without an exception", False, traceback.format_exc()[-1500:])
    finally:
        try:
            _rm_tree(base)
        except OSError as exc:
            case("the self-test's temp dir is removable", False, repr(exc))
    case("the self-test's temp dir (with its scratch git repository) is removed after the run",
         not os.path.exists(base), base)
    for r in res:
        print(r)
    print("SELFTEST %s: %d passed, %d failed => %s" % (os.path.basename(__file__), len(res) - len(fails), len(fails),
                                                       "PASS" if not fails else "FAIL"))
    return 0 if not fails else 1


# ----------------------------------------------------------------------------------------------------------------- main
def _opt(flag, argv=None):
    argv = sys.argv if argv is None else argv
    if flag in argv:
        i = argv.index(flag)
        return argv[i + 1] if i + 1 < len(argv) else ""
    return None


def _here_ok() -> bool:
    if os.path.normcase(os.path.realpath(HERE)) != os.path.normcase(os.path.realpath(os.path.join(WT, "outputs"))):
        print("STOP: this script must live in %s (its queue paths are absolute); it is in %s"
              % (os.path.join(WT, "outputs"), HERE))
        return False
    return True


STOP_RC = {"write": 2, "analyze": 3}


def _run_cmd(cmd: str, fn, *args) -> int:
    """write / analyze with every STOP on its documented exit code: a SystemExit raised by a helper (k_configs /
    build_lines "STOP: ...", outputs/_dq_queue.py stop()) or an unexpected exception exits 2 (write) / 3 (analyze) -
    never Python's 1, which for analyze means FAIL."""
    try:
        rc = fn(*args)
    except SystemExit as exc:
        print("STOP (%s): %s" % (cmd, exc.code))
        return STOP_RC[cmd]
    except Exception:                            # noqa: BLE001 - a crash is a STOP, never a verdict
        traceback.print_exc(file=sys.stdout)
        print("STOP (%s): unexpected exception (above)" % cmd)
        return STOP_RC[cmd]
    return rc if isinstance(rc, int) else STOP_RC[cmd]


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "write":
        return _run_cmd("write", write, _opt("--head", argv)) if _here_ok() else STOP_RC["write"]
    if cmd == "analyze":
        return (_run_cmd("analyze", analyze, "--partial" in argv[2:], _opt("--head", argv)) if _here_ok()
                else STOP_RC["analyze"])
    if cmd == "selftest":
        return selftest(_opt("--tmp", argv))
    if cmd == "_accessors":
        return _accessors_child()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    raise SystemExit(main(sys.argv))
