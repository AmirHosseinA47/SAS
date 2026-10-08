"""Dispatch round 2: THE DISPATCH FLIP RUNNER REGISTER. Writes outputs/dispatch_flip_register.txt.

THE FLIP (outputs/dispatch2_report.txt section 10; the maintainer's confirmation 2026-10-08): DISPATCH_JOINT 0 -> 1 and
DISPATCH_REASSIGN 0 -> 1 in common_fixed_variables.py. The accessors are UNCHANGED (agents.dispatch_joint /
dispatch_reassign): ON ONLY ON AN EXACT 1 (agents._exact_integer; a MISSING key reads OFF), and DISPATCH_REASSIGN is
ENFORCED OFF while DISPATCH_JOINT is off (ruling D-4). That is VERIFIED, not assumed: THE HEAD CHECK requires
agents._exact_integer / dispatch_joint / dispatch_reassign to be AST-identical (docstrings apart) at THE FLIP, at its
first parent and in this tool's replicas, and the replica check requires the same of the working copy. This is the MVG
round's register (outputs/_mvg_flip_register.py -> outputs/movement_flip_register.txt) ported to this flip.

RULE. The classifier RUNS the accessor replicas on a line's --set values (read as the harness reads them: a replica of
outputs/_ffr_harness._parse_value; the last --set of a key wins) twice - over the parent's defaults (0, 0) and over THE
FLIP's (1, 1) - and a job line is FLIP-SAFE iff the two (dispatch_joint(), dispatch_reassign()) pairs are equal. That
is: it sets DISPATCH_JOINT explicitly (DISPATCH_JOINT=0 alone restores today's dispatch: REASSIGN is enforced off) and,
when that value turns J ON (an exact 1), sets DISPATCH_REASSIGN as well - a line with DISPATCH_JOINT=1 alone ran J
WITHOUT reassignment before the flip and runs both after it (REASSIGN-FLIPS, counted SILENT-CHANGE). Otherwise a run
launched after the flip from an AFFECTED checkout measures the corrected dispatcher: SILENT-CHANGE, unless a validator
refuses it: FAILS-LOUDLY (the LOUD table: outputs/_dq_analyze.py's section-9 check on the screen queues,
outputs/_dp_analyze.py's prov_probe on round 1's identity / on queues). AFFECTED is a CONSTANT, whichever checkout runs
this tool: E:/Projects/SAS_wt/dispatch (where THE FLIP is committed) and E:/Projects/SAS (once main is fast-forwarded to
it). A line whose repo is another checkout is OTHER-REPO. A line of a queue-named .jsonl that is not a pool line is
UNCLASSIFIED (counted, never dropped). This round's post-flip queues - EXACTLY outputs/_dq_q_flipid.jsonl,
_dq_q_ist.jsonl and _dq_q_refs.jsonl, the names outputs/_dq_flipid.py / _dq_ist.py / _dq_refs.py write (no slice, no
case variant) - are POST-FLIP. A file's class: POST-FLIP by name; else SILENT-CHANGE if any line is; else UNCLASSIFIED
if any line is; else FAILS-LOUDLY; else FLIP-SAFE; else OTHER-REPO; a queue file without a job line is NO-JOB-LINES.
The four replicas (_parse_value, _exact_integer, dispatch_joint, dispatch_reassign) are verified VERBATIM (AST,
docstrings apart; the LAST top-level definition of the name, a later rebinding never matches) against the checkout
before every write (REFUSED on drift) and analyze (K5 FAIL on drift).

SCANNED (deterministic; ONE os.listdir, of outputs/ - never a walk, no subdirectory; the quarantine entry skipped by
name, and any path containing its name refused before a filesystem call):
  A   outputs/*queue*.txt  pipe lines in the two pool formats:
        kind|tag|repo|wind|roles|seeds|steps|extra  (at least 7 '|', field 2 not a path; the _pl / _ug / _cl / _dcd4rb /
            _dfp pools): the repo is field 3 for the kinds every pool launches with --repo "$repo" (ff, fo, fc); an rb
            line's checkout is pool-dependent (most pools run $RBSCRIPT from their own checkout and ignore the field),
            so rb lines count as AFFECTED (the MVG register's convention: over-flag, never under-flag);
        tag|repo|wind|roles|seed|extra  (at least 5 '|', any other line; outputs/_dcd4_pool.sh and outputs/_dim_pool.sh:
            IFS='|' read -r tag repo w r s extra, then _ffr_harness.py --repo "$repo" ... $extra): the repo is field 2.
      A repo field is read as Git Bash hands it to the native harness (/e/Projects/SAS -> E:/Projects/SAS); a relative
      or driveless one is unknown (treated as affected). The extra field is split as bash splits an UNQUOTED $extra:
      on whitespace, with NO quote removal (quotes that come from an expansion stay), so --set 'DISPATCH_JOINT=0'
      reaches the harness as the key 'DISPATCH_JOINT - not a pin. Its --set tokens decide.
  A2  outputs/*.jsonl whose NAME marks a queue (_q_, _q.jsonl, queue): every pool line is classified - {"argv":
      [script, ...], "cwd"} (outputs/_mf2_pool.py: Popen([PY] + argv, cwd=cwd or E:/Projects/SAS)) or {"args": [...]}
      (outputs/_sd_pool.py, which runs in E:/Projects/SAS) - and every other non-empty line is UNCLASSIFIED; a file
      with no pool line at all is listed as not a pool queue. Repo = the --repo value (the harness: os.path.abspath,
      i.e. against the run's working directory: the line's cwd, else the pool's; a relative cwd is the pool process's
      own, unknown; several distinct --repo values: unknown), else the checkout of an .../outputs/<script>.py argv[0]
      (such scripts put their own checkout on sys.path), else the working directory, else unknown (treated as
      affected). Other .jsonl files are NOT READ (analysis outputs may hold outcomes of seed sets 1-6).
  B   outputs/*.sh, *.ps1  by what they launch; FLIP-SAFE iff the text pins DISPATCH_JOINT (and DISPATCH_REASSIGN when
                           it pins JOINT to 1) - a TEXT HEURISTIC, as the MVG register's
  C   the TRACKED root *.py that build the model (git ls-files ':(glob)*.py') and the tracked tests/ files that name
      the dispatch keys (git ls-files tests); what test_shipped_defaults ASSERTS for both keys
  D   outputs/*.py that run the model (the MVG register's import / runpy patterns), the same text heuristic
Pure text: it imports nothing from the model. Every git call names its pathspec or object (ls-files / log with the
quarantine excluded; rev-parse, show <sha>:common_fixed_variables.py, show <sha>:agents.py, rev-list -n 1, merge-base,
worktree list).

usage (any cwd; E:/Projects/SAS/.venv/Scripts/python.exe -B with PYTHONDONTWRITEBYTECODE=1):
  python -B outputs/_dq_flip_register.py selftest
        in-process, no simulator step: synthetic lines / trees / a fake git (positive and negative controls for every
        check), plus read-only smokes of the real git plumbing and the real outputs/ scan. Exit 0 iff all pass.
  python -B outputs/_dq_flip_register.py write --head SHA [--out PATH] [--replace]
        THE HEAD CHECK (SHA is THE FLIP commit: both keys 1 at SHA and 0 at its first parent; the three accessors
        AST-identical at SHA, at its parent and in the replicas; SHA is HEAD or an ancestor of HEAD, and HEAD still has
        both 1; the working common_fixed_variables.py has both 1) and the replica check, then the scan; writes the
        register (LF) recording --head SHA. FROZEN: an existing register that differs is never re-written without
        --replace; an absent one that git tracks or once added is not re-created without --replace; a file of the same
        name with other content in ANY other registered worktree's outputs/ is a collision (REFUSED, no override) -
        unless it is an earlier version of this same record (this tool's header and the same recorded THE FLIP head),
        which is reported as a note. Identical content -> 'unchanged', exit 0.
  python -B outputs/_dq_flip_register.py analyze [--head SHA] [--register PATH] [--out PATH] [--replace]
        reads the register, re-checks it and prints one VERDICT line; writes the result file (default
        outputs/_dq_flip_register_check.txt, LF) under the SAME frozen-file and collision rules as write (a different
        existing or tracked result file needs --replace; REFUSED -> the verdict is printed, nothing is written, exit 2):
          K1 HEAD     the recorded --head passes THE HEAD CHECK (and equals --head when given)
          K2 CURRENT  the register equals a fresh scan rendered at that head (else STALE: write --replace)
          K3 ROUND    this round's queues (outputs/_dq_q_*.jsonl, the three POST-FLIP names apart; section 9's run line
                      pins DISPATCH_JOINT and DISPATCH_REASSIGN in dq0 / dq1, dqR runs in base897e93b5): at least one
                      pool queue, no SILENT-CHANGE, no FAILS-LOUDLY, no UNCLASSIFIED line, no file without a pool line
          K4 QUAR     the analysis listed exactly one folder (outputs/) - counted both by the scan's own listing and by
                      a spy on os.listdir / os.scandir (os.walk and glob go through os.scandir) for the whole analysis
                      - and touched no quarantine path. Not seen by the spy: pathlib (Python 3.10 binds os.listdir /
                      os.scandir at import; this tool does not use it), C-level listings and child processes (git)
          K5 REPLICA  the four replicas are verbatim in the working copy
          K6 POST     (INFO) the POST-FLIP queues found
        VERDICT PASS iff K1-K5 PASS.
  python -B outputs/_dq_flip_register.py preview [--head SHA]
        prints the rendering to stdout and writes nothing (without --head: a PREVIEW header, no head check).
exit: 0 written / unchanged / PASS; 1 analyze FAIL or a self-test failure; 2 REFUSED (head, replica, frozen file,
collision, usage).

REVISION (2026-10-08, after the adversarial review): a malformed round queue fails K3 (UNCLASSIFIED lines, no-pool-line
files); pipe quotes stay literal; relative / MSYS repo paths resolve as the run resolves them; the tag|repo pipe format
is classified; the affected set is a constant; the accessors are AST-checked across THE FLIP and run by the classifier;
POST-FLIP is the three exact names; the result file is frozen; K4 has an os-level spy and negative controls; an earlier
version of the same record in another worktree is no collision; HEAD must still hold 1 / 1; test_shipped_defaults is
read for its asserted values; several distinct --repo values are unknown (affected).
"""
from __future__ import annotations

import argparse
import ast
import collections
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAIN = r"E:\Projects\SAS"
DISPATCH_WT = r"E:\Projects\SAS_wt\dispatch"
# the checkouts whose module defaults THE FLIP changes - a CONSTANT, never derived from where this tool runs: the
# dispatch worktree (THE FLIP is committed there) and main once fast-forwarded to it
AFFECTED = (DISPATCH_WT, MAIN)
QUAR = "_firemech_rewound_20260914"
REGISTER_NAME = "dispatch_flip_register.txt"
CHECK_NAME = "_dq_flip_register_check.txt"
REGISTER_HEADER = ("DISPATCH FLIP RUNNER REGISTER - tooling whose meaning changes at the DISPATCH_JOINT / "
                   "DISPATCH_REASSIGN flip.")
CHECK_HEADER = "DISPATCH FLIP REGISTER CHECK - outputs/_dq_flip_register.py analyze"
CFV = "common_fixed_variables.py"
AGENTS = "agents.py"
KJ = "DISPATCH_JOINT"
KR = "DISPATCH_REASSIGN"
SCREEN_HEAD = "11d62410"

SAFE, SILENT, LOUDLY, OTHER = "FLIP-SAFE", "SILENT-CHANGE", "FAILS-LOUDLY", "OTHER-REPO"
UNCL = "UNCLASSIFIED"
POST, NOJOB, NOTSIM = "POST-FLIP", "NO-JOB-LINES", "NOT-A-SIMULATION"
LINE_CLASSES = (SAFE, SILENT, LOUDLY, OTHER)
ALL_LINE_CLASSES = LINE_CLASSES + (UNCL,)

# EXACTLY the names the sibling tools write (outputs/_dq_flipid.py, _dq_ist.py, _dq_refs.py) - case-sensitive, no slices
POST_FLIP_NAMES = ("_dq_q_flipid.jsonl", "_dq_q_ist.jsonl", "_dq_q_refs.jsonl")
ROUND_QUEUE_RE = re.compile(r"^_dq_q_[A-Za-z0-9_]+\.jsonl$", re.I)
QUEUE_NAME_RE = re.compile(r"_q_|_q\.jsonl$|queue", re.I)
PIPE_QUEUE_RE = re.compile(r"queue.*\.txt$")
REPO_KINDS = ("ff", "fo", "fc")  # pipe kinds the pools launch with --repo "$repo" (ff everywhere; fo / fc: _pl_pool)
# (file-name rule, the launched script's basename or None = any, the validator) - a SILENT line of such a file is
# refused by that validator when re-run: FAILS-LOUDLY
LOUD = (
    (re.compile(r"^_dq_q_(?:w1|w2|w3|smoke)\.jsonl$", re.I), None,
     "outputs/_dq_analyze.py prov_run -> s9_problems (section 9)"),
    (re.compile(r"^_dp_q_(?:identity|on)\.jsonl$", re.I), "_dp_probe.py",
     "outputs/_dp_analyze.py prov_probe (dp.switches)"),
)
LAUNCH = (("_ffr_harness", "harness"), ("_fm2_probe_harness", "crn-harness"), ("_mvg_probe", "mvg-probe"),
          ("_dq_probe", "dq-probe"), ("_dp_probe", "dp-probe"), ("_dq_replay", "dq-replay"),
          ("_ud_probe", "ud-probe"), ("_ut_probe", "ut-probe"), ("_rblatch_campaign2", "rb-campaign"),
          ("evaluate_scenarios", "evaluate"), ("pytest", "pytest"), ("_pool", "pool"),
          ("serve_dashboard", "dashboard"))
SIM_RE = re.compile(r"^\s*(from|import)\s+(wildfire_model|evaluate_scenarios|_ffr_harness|_rblatch_campaign2)\b"
                    r"|runpy\.run_path\([^)]*(_ffr_harness|_fm2_probe_harness|_ut_probe|_sd_probe)", re.M)
NOT_ENTRY = {"wildfire_model.py", "common_fixed_variables.py", "agents.py"}
ACCESSORS = ("_exact_integer", "dispatch_joint", "dispatch_reassign")
REPLICAS = (("_parse_value", "outputs/_ffr_harness.py"),) + tuple((fn, AGENTS) for fn in ACCESSORS)
MODEL_MODULES = ("wildfire_model", "agents", "common_fixed_variables", "mesa")
PRE_DEFAULTS, POST_DEFAULTS = (0, 0), (1, 1)


class Refused(Exception):
    pass


def decode(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = data.decode("utf-16", "replace")
    else:
        text = data.decode("utf-8", "replace")
        if text.startswith("\ufeff"):
            text = text[1:]
    return text.replace("\r", "")


def norm(path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------- replicas (verified verbatim by replica_check)
def _parse_value(raw: str):
    text = str(raw).strip()
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _exact_integer(raw) -> int | None:
    """Replica of agents._exact_integer (the AST of its body is compared with the checkout's by replica_check)."""
    try:
        if isinstance(raw, int):
            return int.__int__(raw)
        if isinstance(raw, float):
            return float.__int__(raw) if float.is_integer(raw) else None
        if isinstance(raw, str):
            try:
                return int(str.strip(raw))
            except ValueError:
                return None
        value = int.__int__(int(raw))
        return value if raw == value else None
    except Exception:
        return None


class _Switches:
    """The namespace the accessor replicas read as `cfv`: the module defaults plus one line's --set values, built by
    switch_state for one evaluation (never the model's module)."""


cfv = _Switches()


def dispatch_joint() -> bool:
    """Replica of agents.dispatch_joint (AST-verified, docstrings apart): ON ONLY ON AN EXACT 1; missing reads OFF."""
    return _exact_integer(getattr(cfv, "DISPATCH_JOINT", 0)) == 1


def dispatch_reassign() -> bool:
    """Replica of agents.dispatch_reassign: ON only on an exact 1; ENFORCED OFF while dispatch_joint() is off (D-4)."""
    if not dispatch_joint():
        return False
    return _exact_integer(getattr(cfv, "DISPATCH_REASSIGN", 0)) == 1


def switch_state(sets: dict, defaults: tuple) -> tuple:
    """(dispatch_joint(), dispatch_reassign()) as a run reads them: the replicas run on the module defaults overridden by
    the line's --set values (parsed as the harness parses them; apply_scenario_config sets every key by setattr)."""
    global cfv
    ns = _Switches()
    for key, default in zip((KJ, KR), defaults):
        setattr(ns, key, _parse_value(sets[key]) if key in sets else default)
    saved, cfv = cfv, ns
    try:
        return dispatch_joint(), dispatch_reassign()
    finally:
        cfv = saved


def is_on(value_text: str) -> bool:
    """An explicit --set value as the accessors read it: ON only on an exact 1."""
    return _exact_integer(_parse_value(value_text)) == 1


def _binds(node, name: str) -> bool:
    """A top-level statement other than a def that (re)binds `name`."""
    if isinstance(node, ast.ClassDef):
        return node.name == name
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return any((a.asname or a.name.split(".")[0]) == name for a in node.names)
    targets = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    return any(isinstance(n, ast.Name) and n.id == name for tgt in targets for n in ast.walk(tgt))


def _fn_shape(source, name: str) -> str | None:
    """The AST of the LAST top-level definition of a function (the one in effect at import): arguments, decorators,
    return annotation and body without its docstring. A later top-level rebinding of the name gives '<rebound>' (never
    equal to a shape); a missing function or an unparsable source gives None."""
    if source is None:
        return None
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    shape = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = list(node.body)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body = body[1:]
            shape = "%s|%s|%s|%s" % (ast.dump(node.args), "".join(ast.dump(d) for d in node.decorator_list),
                                     ast.dump(node.returns) if node.returns else "",
                                     "".join(ast.dump(b) for b in body))
        elif isinstance(node, ast.AsyncFunctionDef) and node.name == name or _binds(node, name):
            shape = "<rebound>"
    return shape


def _own_text() -> str:
    with open(os.path.abspath(__file__), "rb") as fh:
        return decode(fh.read())


def replica_check(ctx, own_text: str | None = None) -> list[str]:
    own = _own_text() if own_text is None else own_text
    problems = []
    for fn, rel in REPLICAS:
        mine = _fn_shape(own, fn)
        path = os.path.join(ctx.root, *rel.split("/"))
        try:
            theirs = _fn_shape(ctx.read(path), fn)
        except OSError:
            theirs = None
        if mine is None or theirs is None or mine != theirs:
            problems.append("the replica %s differs from %s's (or is missing): the classifier would not read --set "
                            "values as the run does" % (fn, path))
    return problems


# --------------------------------------------------------------------------------------------- the line classifier
def set_pairs(argv) -> list[tuple[str, str]]:
    """(key, value text) of every --set KEY=VALUE / --set=KEY=VALUE token, in order (the key stripped, as the
    harness strips it; quote characters are part of the token)."""
    out = []
    i, n = 0, len(argv)
    while i < n:
        tok = str(argv[i])
        if tok == "--set" and i + 1 < n:
            kv, i = str(argv[i + 1]), i + 2
        elif tok.startswith("--set="):
            kv, i = tok[len("--set="):], i + 1
        else:
            i += 1
            continue
        if "=" in kv:
            key, val = kv.split("=", 1)
            out.append((key.strip(), val))
    return out


def dispatch_meaning(argv) -> tuple[str, str]:
    """(class, code): FLIP-SAFE (JOINT-OFF / BOTH-SET) or SILENT-CHANGE (UNPINNED / REASSIGN-FLIPS) - the accessor
    replicas run over the parent's defaults and over THE FLIP's; equal pairs are FLIP-SAFE."""
    sets = {}
    for key, val in set_pairs(argv):
        sets[key] = val  # the harness applies them in order: the last wins
    before, after = switch_state(sets, PRE_DEFAULTS), switch_state(sets, POST_DEFAULTS)
    if before != after:
        return SILENT, ("UNPINNED" if KJ not in sets else "REASSIGN-FLIPS")
    return SAFE, ("BOTH-SET" if after[0] else "JOINT-OFF")


def flag_values(argv, flag: str) -> list[str]:
    """Every value of `flag VALUE` / `flag=VALUE`, in order."""
    out = []
    for i, tok in enumerate(argv):
        tok = str(tok)
        if tok == flag and i + 1 < len(argv):
            out.append(str(argv[i + 1]))
        elif tok.startswith(flag + "="):
            out.append(tok[len(flag) + 1:])
    return out


def _has_drive(path: str) -> bool:
    drive, rest = os.path.splitdrive(str(path))
    return bool(drive) and rest[:1] in ("\\", "/")


def resolve_dir(path, base=None):
    """A path as the OS resolves it for a process whose working directory is `base`: with a drive (or UNC share) and a
    root, as given; any other path (relative, or rooted without a drive) against an absolute `base`; else None
    (unknown)."""
    if path is None:
        return None
    p = str(path)
    if not p:
        return os.path.normpath(str(base)) if base is not None and _has_drive(str(base)) else None
    if _has_drive(p):
        return os.path.normpath(p)
    if base is not None and _has_drive(str(base)):
        joined = os.path.normpath(os.path.join(str(base), p))
        return joined if _has_drive(joined) else None
    return None


def _flag_repo(argv, base) -> tuple[bool, str | None]:
    """(False, None) without --repo; else (True, the checkout or None): every value resolved against the run's working
    directory (the harness: os.path.abspath(args.repo)); several distinct values are unknown (the probes import from
    the first, the harness from the last - an IMPORT MISMATCH; counted affected, never under-flagged)."""
    vals = flag_values(argv, "--repo")
    if not vals:
        return False, None
    got = [resolve_dir(v, base) for v in vals]
    if any(g is None for g in got) or len({norm(g) for g in got}) != 1:
        return True, None
    return True, got[-1]


def argv_repo(argv, cwd=None, pool_cwd=None):
    """The checkout a pool line's run imports the model from (None: unknown). The run's working directory is the line's
    cwd, else the pool's (outputs/_mf2_pool.py: Popen(cwd=ln.get("cwd") or REPO), REPO = E:/Projects/SAS); a relative
    cwd is relative to the pool process's own (unknown)."""
    base = resolve_dir(cwd) if cwd else resolve_dir(pool_cwd)
    found, repo = _flag_repo(argv, base)
    if found:
        return repo
    a0 = resolve_dir(str(argv[0]), base) if argv and str(argv[0]) else None
    if a0 and a0.lower().endswith(".py") and os.path.basename(os.path.dirname(a0)).lower() == "outputs":
        return os.path.dirname(os.path.dirname(a0))
    return base


def loud_rule(fname: str, script):
    for rx, scr, label in LOUD:
        if rx.match(fname) and (scr is None or (script or "").lower() == scr.lower()):
            return label
    return None


def classify_job(ctx, fname: str, argv, repo, script) -> tuple[str, str]:
    if repo is not None and norm(repo) not in ctx.affected:
        return OTHER, "OTHER-REPO"
    cls, code = dispatch_meaning(argv)
    if cls == SILENT and loud_rule(fname, script) is not None:
        return LOUDLY, code
    return cls, code


_MSYS_RE = re.compile(r"^/([A-Za-z])(?=/|$)")


def _pathish(field: str) -> bool:
    f = field.strip()
    return bool(f) and any(ch in f for ch in ":/\\")


def pipe_repo(field: str):
    """A pipe line's repo field as the native harness receives it from bash: Git Bash converts /e/... to E:/...; a path
    without a drive and a root is unknown (None: treated as affected)."""
    p = _MSYS_RE.sub(lambda m: m.group(1).upper() + ":", field.strip(), count=1)
    return os.path.normpath(p) if _has_drive(p) else None


def pipe_job(line: str):
    """(format, kind, repo or None, tokens) of a pipe-format job line, else None.
    '8f' kind|tag|repo|wind|roles|seeds|steps|extra (at least 7 '|', field 2 not a path): the repo field is trusted only
         for the kinds every pool launches with --repo "$repo" (REPO_KINDS); an rb line's checkout is pool-dependent
         (_pl_pool.sh runs <repo>/outputs/_rblatch_campaign2.py, the _ug / _cl / _dcd4rb / _dfp pools run $RBSCRIPT from
         their own checkout and ignore the field), so it is None: treated as affected (the MVG register's convention).
    '6f' tag|repo|wind|roles|seed|extra (any other line with at least 5 '|'; outputs/_dcd4_pool.sh and _dim_pool.sh run
         _ffr_harness.py --repo "$repo" ... $extra, the last field taking the rest of the line).
    The extra field is split as bash splits an unquoted $extra: on whitespace, quote characters kept."""
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    parts = line.split("|")
    if len(parts) >= 8 and not _pathish(parts[1]):
        f = line.split("|", 7)
        kind = f[0].strip()
        return "8f", kind, (pipe_repo(f[2]) if kind in REPO_KINDS else None), f[7].split()
    if len(parts) >= 6:
        f = line.split("|", 5)
        return "6f", "-", pipe_repo(f[1]), f[5].split()
    return None


def jsonl_jobs(ctx, text: str):
    """([(argv, repo, format)], UNCLASSIFIED line count) of a queue-named .jsonl: every non-empty line that is a pool
    line is classified; any other (not JSON, not an object, no argv / args list) is counted UNCLASSIFIED."""
    jobs, bad = [], 0
    for ln in text.split("\n"):
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except (ValueError, RecursionError):
            bad += 1
            continue
        if not isinstance(d, dict):
            bad += 1
        elif isinstance(d.get("argv"), list) and d["argv"]:
            argv = [str(x) for x in d["argv"]]
            jobs.append((argv, argv_repo(argv, d.get("cwd"), ctx.main), "argv"))
        elif isinstance(d.get("args"), list):
            args = [str(x) for x in d["args"]]
            found, repo = _flag_repo(args, resolve_dir(ctx.sd_repo))
            jobs.append((args, repo if found else ctx.sd_repo, "args"))
        else:
            bad += 1
    return jobs, bad


def is_post_flip(name: str) -> bool:
    return name in POST_FLIP_NAMES


def is_round_queue(name: str) -> bool:
    return bool(ROUND_QUEUE_RE.match(name)) and not is_post_flip(name)


def file_class(name: str, counts) -> str:
    if is_post_flip(name):
        return POST
    for cls in (SILENT, UNCL, LOUDLY, SAFE, OTHER):
        if counts[cls]:
            return cls
    return NOJOB


def _key_set_res(key: str):
    k = re.escape(key)
    return (re.compile(r"--set[ \t=]+[\"']?%s=" % k), re.compile(r"[\"']%s=" % k),
            re.compile(r"setattr\(\s*[\w.]+\s*,\s*[\"']%s[\"']" % k), re.compile(r"\b\w+\.%s\s*=(?!=)" % k))


SET_J, SET_R = _key_set_res(KJ), _key_set_res(KR)
J_ON = (re.compile(r"%s=[\"']?\s*(?:1|1\.0|true)(?![\w.])" % KJ, re.I),
        re.compile(r"setattr\(\s*[\w.]+\s*,\s*[\"']%s[\"']\s*,\s*(?:1|True)\b" % KJ),
        re.compile(r"\b\w+\.%s\s*=\s*(?:1|True)\b" % KJ))


def text_meaning(text: str) -> tuple[str, str]:
    """A runner's / script's text: FLIP-SAFE (PINS-JOINT) or SILENT-CHANGE (UNPINNED / REASSIGN-FLIPS). Heuristic."""
    if not any(r.search(text) for r in SET_J):
        return SILENT, "UNPINNED"
    if any(r.search(text) for r in J_ON) and not any(r.search(text) for r in SET_R):
        return SILENT, "REASSIGN-FLIPS"
    return SAFE, "PINS-JOINT"


# ------------------------------------------------------------------------------------------------- git and context
class Git:
    def __init__(self, root: str, quarantine: str = QUAR):
        self.root = root
        self.exclude = ":(exclude)outputs/" + quarantine

    def _run(self, *args):
        proc = subprocess.run(["git", "-C", self.root, "-c", "core.quotepath=off", *args], capture_output=True)
        return proc.returncode, proc.stdout

    def resolve(self, rev):
        if not rev or str(rev).startswith("-"):
            return None
        rc, out = self._run("rev-parse", "--verify", "--quiet", "%s^{commit}" % rev)
        sha = out.decode("ascii", "replace").strip()
        return sha if rc == 0 and re.fullmatch(r"[0-9a-f]{40}", sha) else None

    def show(self, sha: str, rel: str):
        rc, out = self._run("show", "%s:%s" % (sha, rel))
        return decode(out) if rc == 0 else None

    def first_parent(self, sha: str):
        rc, out = self._run("rev-list", "--parents", "-n", "1", sha)
        parts = out.decode("ascii", "replace").split()
        return parts[1] if rc == 0 and len(parts) > 1 else None

    def is_ancestor(self, a: str, b: str) -> bool:
        rc, _out = self._run("merge-base", "--is-ancestor", a, b)
        return rc == 0

    def ls_files(self, specs) -> list[str]:
        rc, out = self._run("ls-files", "-z", "--", *specs, self.exclude)
        if rc != 0:
            raise Refused("git ls-files %s failed in %s" % (" ".join(specs), self.root))
        return sorted(p for p in out.decode("utf-8", "replace").split("\0") if p)

    def added_in_history(self, rel: str) -> bool:
        rc, out = self._run("log", "--all", "--diff-filter=A", "--format=%H", "--", rel, self.exclude)
        return rc == 0 and bool(out.strip())

    def worktrees(self) -> list[str]:
        _rc, out = self._run("worktree", "list", "--porcelain")
        return [ln[len("worktree "):].strip() for ln in out.decode("utf-8", "replace").splitlines()
                if ln.startswith("worktree ")]


class Ctx:
    def __init__(self, root: str, git=None, main: str = MAIN, quarantine: str = QUAR, sd_repo: str | None = None,
                 affected=None):
        self.root = os.path.normpath(root)
        self.outputs = os.path.join(self.root, "outputs")
        self.main = os.path.normpath(main)
        self.quarantine = quarantine
        # the constant AFFECTED unless a synthetic test names its own (never derived from root)
        self.affected_names = [os.path.normpath(p) for p in (AFFECTED if affected is None else affected)]
        self.affected = {norm(p) for p in self.affected_names}
        self.git = git if git is not None else Git(self.root, quarantine)
        self.sd_repo = sd_repo or self.main
        self.listed: list[str] = []
        self.refused = 0

    def guard(self, path) -> None:
        if self.quarantine.lower() in str(path).lower():
            self.refused += 1
            raise Refused("refusing to touch a path containing the quarantine name: %s" % path)

    def listdir(self, folder: str) -> list[str]:
        self.guard(folder)
        self.listed.append(os.path.normpath(folder))
        return sorted(n for n in os.listdir(folder) if n.lower() != self.quarantine.lower())

    def read(self, path: str) -> str:
        self.guard(path)
        with open(path, "rb") as fh:
            return decode(fh.read())

    def isfile(self, path: str) -> bool:
        self.guard(path)
        return os.path.isfile(path)

    def isdir(self, path: str) -> bool:
        self.guard(path)
        return os.path.isdir(path)


class ListingSpy:
    """Records every os.listdir / os.scandir call while active (os.walk and glob list through os.scandir), whoever makes
    it - K4 counts these, not only the scan's own listing."""

    def __init__(self):
        self.calls: list = []
        self._saved = None

    def _rec(self, path):
        self.calls.append(os.path.normpath(path) if isinstance(path, str) else repr(path))

    def __enter__(self):
        real_ld, real_sd = os.listdir, os.scandir
        self._saved = (real_ld, real_sd)

        def listdir(path=None):
            self._rec(path if path is not None else ".")
            return real_ld(path)

        def scandir(path=None):
            self._rec(path if path is not None else ".")
            return real_sd(path)

        os.listdir, os.scandir = listdir, scandir
        return self

    def __exit__(self, *exc):
        os.listdir, os.scandir = self._saved
        return False


# ------------------------------------------------------------------------------------------------------ head check
def cfv_values(text) -> dict:
    """The module-level assignments of the two keys in a common_fixed_variables.py text (the last one wins)."""
    vals: dict = {}
    if text is None:
        return vals
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {"<syntax error>": True}
    for node in tree.body:
        targets, value = [], None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for tgt in targets:
            if isinstance(tgt, ast.Name) and tgt.id in (KJ, KR):
                try:
                    vals[tgt.id] = ast.literal_eval(value)
                except ValueError:
                    vals[tgt.id] = "<not a literal>"
    return vals


def _both(vals: dict, want: int) -> bool:
    return all(type(vals.get(k)) is int and vals.get(k) == want for k in (KJ, KR))


def accessor_problems(ctx, sha: str, parent: str, own_text: str | None = None) -> list[str]:
    """The three accessors must be AST-identical (docstrings apart) at THE FLIP and at its first parent - the register's
    rule assumes THE FLIP changes the defaults only - and equal to this tool's replicas, which the classifier runs."""
    own = _own_text() if own_text is None else own_text
    at, before = ctx.git.show(sha, AGENTS), ctx.git.show(parent, AGENTS)
    out = []
    for fn in ACCESSORS:
        a, b = _fn_shape(at, fn), _fn_shape(before, fn)
        if a is None or b is None or a != b:
            out.append("agents.%s differs between THE FLIP %s and its parent %s (docstrings apart), or is missing: the "
                       "register's rule needs the accessors unchanged by THE FLIP" % (fn, sha[:10], parent[:10]))
        elif a != _fn_shape(own, fn):
            out.append("agents.%s at THE FLIP %s is not this tool's replica (docstrings apart): the classifier would "
                       "not read the switches as the run does" % (fn, sha[:10]))
    return out


def head_check(ctx, head_arg) -> tuple[dict, list[str]]:
    """THE HEAD CHECK: --head is THE FLIP commit. Returns (info {sha, parent, head}, problems)."""
    info = {"sha": None, "parent": None, "head": None}
    sha = ctx.git.resolve(head_arg) if head_arg else None
    if sha is None:
        return info, ["--head %r is not a commit of %s" % (head_arg, ctx.root)]
    info["sha"] = sha
    problems = []
    at = cfv_values(ctx.git.show(sha, CFV))
    if not _both(at, 1):
        problems.append("at %s, %s has %s = %r and %s = %r (THE FLIP ships both = 1)" % (
            sha[:10], CFV, KJ, at.get(KJ), KR, at.get(KR)))
    parent = ctx.git.first_parent(sha)
    info["parent"] = parent
    if parent is None:
        problems.append("%s has no parent" % sha[:10])
    else:
        before = cfv_values(ctx.git.show(parent, CFV))
        if not _both(before, 0):
            problems.append("its first parent %s has %s = %r and %s = %r: %s is not THE FLIP commit (the commit "
                            "that changes both 0 -> 1)" % (parent[:10], KJ, before.get(KJ), KR, before.get(KR),
                                                          sha[:10]))
        problems += accessor_problems(ctx, sha, parent)
    head = ctx.git.resolve("HEAD")
    info["head"] = head
    if head is None or not ctx.git.is_ancestor(sha, head):
        problems.append("%s is not HEAD or an ancestor of HEAD %s" % (sha[:10], (head or "?")[:10]))
    elif head != sha:
        now = cfv_values(ctx.git.show(head, CFV))
        if not _both(now, 1):
            problems.append("HEAD %s has %s = %r and %s = %r: a commit after THE FLIP changed the defaults back (the "
                            "register describes the flipped tree: both 1 at HEAD)" % (head[:10], KJ, now.get(KJ), KR,
                                                                                     now.get(KR)))
    try:
        work = cfv_values(ctx.read(os.path.join(ctx.root, CFV)))
    except OSError:
        work = {}
    if not _both(work, 1):
        problems.append("the working %s has %s = %r and %s = %r (the register describes the flipped tree: both 1)"
                        % (CFV, KJ, work.get(KJ), KR, work.get(KR)))
    return info, problems


# ------------------------------------------------------------------------------------------------------------ scan
def _new_row(name: str) -> dict:
    return {"name": name, "counts": collections.Counter(), "flips": 0, "fmts": collections.Counter(), "cls": None}


def _add(res: dict, row: dict, cls: str, code: str, repo) -> None:
    row["counts"][cls] += 1
    if code == "REASSIGN-FLIPS":
        row["flips"] += 1
    if cls == OTHER:
        key = norm(repo)
        res["other_repos"][key] += 1
        res["other_names"].setdefault(key, str(repo))


def _asserted(body: str, key: str) -> list[str]:
    """The right-hand sides of `<...>KEY == X` in a test body (what it asserts the shipped value is)."""
    return re.findall(r"\b%s\s*==\s*([^\s#),;]+)" % re.escape(key), body)


def scan(ctx) -> dict:
    res = {"queues": [], "pools": [], "notread": [], "notpool": [], "runners": [], "simpy": {}, "entry": None,
           "tests": None, "shipped_test": None, "other_repos": collections.Counter(), "other_names": {}}
    names = ctx.listdir(ctx.outputs)
    files = [n for n in names if ctx.isfile(os.path.join(ctx.outputs, n))]
    # ---- A. pipe-format queue files
    for n in files:
        if not PIPE_QUEUE_RE.search(n):
            continue
        row = _new_row(n)
        for ln in ctx.read(os.path.join(ctx.outputs, n)).split("\n"):
            job = pipe_job(ln)
            if job is None:
                continue
            fmt, _kind, repo, toks = job
            cls, code = classify_job(ctx, n, toks, repo, None)
            _add(res, row, cls, code, repo)
            row["fmts"][fmt] += 1
        row["cls"] = file_class(n, row["counts"])
        res["queues"].append(row)
    # ---- A2. JSONL pool queues
    for n in files:
        if not n.lower().endswith(".jsonl"):
            continue
        if not QUEUE_NAME_RE.search(n):
            res["notread"].append(n)
            continue
        jobs, bad = jsonl_jobs(ctx, ctx.read(os.path.join(ctx.outputs, n)))
        if not jobs:
            res["notpool"].append(n)
            continue
        row = _new_row(n)
        row["counts"][UNCL] += bad
        for argv, repo, fmt in jobs:
            script = os.path.basename(argv[0].replace("\\", "/")) if fmt == "argv" else None
            cls, code = classify_job(ctx, n, argv, repo, script)
            _add(res, row, cls, code, repo)
            row["fmts"][fmt] += 1
        row["cls"] = file_class(n, row["counts"])
        res["pools"].append(row)
    # ---- D. python in outputs/ that runs the model (needed by B)
    for n in files:
        if n.lower().endswith(".py"):
            text = ctx.read(os.path.join(ctx.outputs, n))
            if SIM_RE.search(text):
                res["simpy"][n] = text_meaning(text)
    # ---- B. runners
    for n in files:
        if not n.lower().endswith((".sh", ".ps1")):
            continue
        text = ctx.read(os.path.join(ctx.outputs, n))
        kinds = [k for pat, k in LAUNCH if pat in text]
        for py in sorted(set(re.findall(r"([A-Za-z0-9_./\\-]+\.py)\b", text))):
            base = os.path.basename(py.replace("\\", "/"))
            if base in res["simpy"] and base not in kinds:
                kinds.append(base)
        if not kinds:
            cls, code = NOTSIM, "-"
        else:
            cls, code = text_meaning(text)
        res["runners"].append((n, cls, code, kinds))
    # ---- C. entry points and the suite (tracked files, named by git; never a listing of the root)
    entry = []
    for rel in ctx.git.ls_files([":(glob)*.py"]):
        if "/" in rel or rel in NOT_ENTRY:
            continue
        path = os.path.join(ctx.root, rel)
        if ctx.isfile(path) and SIM_RE.search(ctx.read(path)):
            entry.append(rel)
    res["entry"] = entry
    tests = []
    for rel in ctx.git.ls_files(["tests"]):
        if not rel.endswith(".py"):
            continue
        path = os.path.join(ctx.root, *rel.split("/"))
        if not ctx.isfile(path):
            continue
        text = ctx.read(path)
        nj = len(re.findall(r"\b%s\b" % KJ, text))
        nr = len(re.findall(r"\b%s\b" % KR, text))
        if nj or nr:
            tests.append((rel, nj, nr))
        m = re.search(r"^def test_shipped_defaults\b.*?(?=^def |\Z)", text, re.S | re.M)
        if m:
            res["shipped_test"] = (rel, _asserted(m.group(0), KJ), _asserted(m.group(0), KR))
    res["tests"] = tests
    return res


# ---------------------------------------------------------------------------------------------------------- render
def _row_text(row: dict) -> str:
    c = row["counts"]
    extra = "  (REASSIGN-FLIPS %d)" % row["flips"] if row["flips"] else ""
    if c[UNCL]:
        extra += "  (UNCLASSIFIED %d)" % c[UNCL]
    if row["fmts"]["6f"]:
        extra += "  (tag|repo format)"
    if row["fmts"]["args"]:
        extra += "  (args-format)"
    return "  %-44s %4d / %4d / %4d / %4d  %s%s" % (row["name"], c[SAFE], c[SILENT], c[LOUDLY], c[OTHER],
                                                      row["cls"], extra)


def _wrap_names(names, width: int = 112) -> list[str]:
    lines, cur = [], ""
    for n in names:
        add = n if not cur else cur + ", " + n
        if cur and len(add) > width:
            lines.append(cur + ",")
            cur = n
        else:
            cur = add
    if cur:
        lines.append(cur)
    return lines


def summary(res: dict) -> dict:
    rows = res["queues"] + res["pools"]
    tot = collections.Counter()
    for row in rows:
        for cls in ALL_LINE_CLASSES:
            tot[cls] += row["counts"][cls]
        tot["flips"] += row["flips"]
    rq = [r for r in res["pools"] if is_round_queue(r["name"])]
    rn = [n for n in res["notpool"] if is_round_queue(n)]
    tot["round_pool_files"] = len(rq)
    tot["round_notpool"] = len(rn)
    tot["round_files"] = len(rq) + len(rn)
    tot["round_lines"] = sum(sum(r["counts"][c] for c in ALL_LINE_CLASSES) for r in rq)
    tot["round_bad"] = sum(r["counts"][SILENT] + r["counts"][LOUDLY] for r in rq)
    tot["round_uncl"] = sum(r["counts"][UNCL] for r in rq)
    tot["post_files"] = sum(1 for r in res["pools"] if r["cls"] == POST)
    tot["six_lines"] = sum(r["fmts"]["6f"] for r in res["queues"])
    return tot


def round_clean(tot) -> bool:
    return bool(tot["round_pool_files"]) and not (tot["round_bad"] or tot["round_uncl"] or tot["round_notpool"])


def render(ctx, res: dict, head) -> list[str]:
    out: list[str] = []
    say = out.append
    say(REGISTER_HEADER)
    if head and head.get("sha"):
        say("Generated by outputs/_dq_flip_register.py write --head %s" % head["sha"])
        say("(dispatch round 2's flip: outputs/dispatch2_report.txt section 10; the maintainer's confirmation "
            "2026-10-08).")
    else:
        say("PREVIEW - NOT THE REGISTER (outputs/_dq_flip_register.py preview without --head; no head check).")
    say("Scanned: %s (top level only; the quarantine entry skipped by name)." % ctx.outputs)
    say("")
    if head and head.get("sha"):
        say("THE FLIP %s (its parent %s has both keys 0): DISPATCH_JOINT 0 -> 1 and DISPATCH_REASSIGN 0 -> 1"
            % (head["sha"][:10], (head.get("parent") or "?")[:10]))
        say("in common_fixed_variables.py. The accessors are UNCHANGED - VERIFIED by the head check: agents._exact_integer,")
        say("dispatch_joint and dispatch_reassign are AST-identical (docstrings apart) at THE FLIP, at its parent and in")
        say("this tool's replicas (and in the working copy: K5): on only on an exact 1 (a MISSING key reads OFF), and")
    else:
        say("THE FLIP: DISPATCH_JOINT 0 -> 1 and DISPATCH_REASSIGN 0 -> 1 in common_fixed_variables.py. The accessors")
        say("(agents._exact_integer, dispatch_joint, dispatch_reassign; NOT verified across THE FLIP in a PREVIEW): on")
        say("only on an exact 1 (a MISSING key reads OFF), and")
    say("DISPATCH_REASSIGN is enforced off while DISPATCH_JOINT is off (ruling D-4). A run that sets neither key reads the")
    say("module defaults, now 1 and 1: the corrected dispatcher (C1-C3, R-1, R-2).")
    say("AFFECTED CHECKOUTS (a constant, the same whichever checkout runs this tool): %s" % ", ".join(ctx.affected_names))
    say("- the dispatch worktree, where THE FLIP is committed, and main once fast-forwarded to it. An rb pipe line counts")
    say("as affected whatever its repo field says (most pools run the campaign from their own checkout and ignore it).")
    say("RULE: the classifier runs the accessor replicas on a line's --set values over the parent's defaults (0, 0) and")
    say("over THE FLIP's (1, 1); a job line is FLIP-SAFE iff the two (dispatch_joint, dispatch_reassign) pairs are equal:")
    say("it sets DISPATCH_JOINT explicitly - DISPATCH_JOINT=0 alone restores today's dispatch (REASSIGN is enforced off)")
    say("- and, when its DISPATCH_JOINT is an exact 1, sets DISPATCH_REASSIGN as well: a line with DISPATCH_JOINT=1 alone")
    say("ran J without reassignment before the flip and runs both after it (REASSIGN-FLIPS, counted SILENT-CHANGE).")
    say("Otherwise a run launched from an affected checkout after the flip measures the corrected dispatcher -")
    say("SILENT-CHANGE - unless a validator refuses it (FAILS-LOUDLY, below). A line whose repo is another checkout is")
    say("OTHER-REPO (that checkout's own defaults). A line of a queue-named .jsonl that is not a pool line is UNCLASSIFIED.")
    say("POST-FLIP: exactly %s - this round's post-flip queues," % ", ".join(POST_FLIP_NAMES))
    say("written for the flipped tree (no slice, no case variant). A file is POST-FLIP by name, else SILENT-CHANGE if")
    say("any line is, else UNCLASSIFIED, FAILS-LOUDLY, FLIP-SAFE, OTHER-REPO in that order. --set values are read as the")
    say("harness reads them (_ffr_harness._parse_value; verified verbatim); the last --set of a key wins. Pipe extras are")
    say("split as bash splits an unquoted $extra (quote characters stay: --set 'DISPATCH_JOINT=0' pins nothing); a repo")
    say("is resolved as the run resolves it (Git Bash /e/... -> E:/...; relative to the run's working directory;")
    say("unknown -> affected).")
    say("FAILS-LOUDLY - the validators that refuse a re-run whose recorded dispatch switches differ from its line:")
    say("  outputs/_dq_analyze.py  prov_run -> s9_problems (dispatch2_part1.txt section 9) on _dq_q_w1 / w2 / w3 / smoke:")
    say("                          a record's --set tokens must be section 9's exactly (dq0 DISPATCH_JOINT=0")
    say("                          DISPATCH_REASSIGN=0, dq1 both 1, dqR none) and dq.switches (raw, joint_on, reassign_on)")
    say("                          the arm's; its head rule also refuses a record whose head descends from the screen")
    say("                          head %s." % SCREEN_HEAD)
    say("  outputs/_dp_analyze.py  prov_probe on _dp_q_identity / _dp_q_on lines run by _dp_probe.py: dp.switches")
    say("                          joint_on / reassign_on must be the arm's (dp1 on, every other arm off) - a dp0 line")
    say("                          re-run after the flip records joint_on True: INVALID.")
    say("  NOT loud (counted SILENT-CHANGE): _dp_analyze.py prov_shard checks only a shard's recorded --set params, so a")
    say("  re-run dpG0 shard passes and then fails G-ID - a false identity STOP that blames the round's code;")
    say("  _dp_q_evidence lines are digested without a switch check; outputs/_mvg_analyze.py checks no dispatch switch")
    say("  (main 897e93b5 had no DISPATCH_* key).")
    say("")
    tot = summary(res)
    say("SUMMARY: A + A2 job lines FLIP-SAFE %d, SILENT-CHANGE %d (of which REASSIGN-FLIPS %d), FAILS-LOUDLY %d,"
        % (tot[SAFE], tot[SILENT], tot["flips"], tot[LOUDLY]))
    say("OTHER-REPO %d, UNCLASSIFIED %d; POST-FLIP files %d. This round's queues (outputs/_dq_q_*.jsonl, POST-FLIP apart):"
        % (tot[OTHER], tot[UNCL], tot["post_files"]))
    say("%d files, %d lines, SILENT-CHANGE or FAILS-LOUDLY %d, UNCLASSIFIED %d, files with no pool line %d"
        % (tot["round_files"], tot["round_lines"], tot["round_bad"], tot["round_uncl"], tot["round_notpool"]))
    if round_clean(tot):
        say("(dq0 / dq1 / W3 pin both keys; dqR runs in base897e93b5).")
    else:
        say("(K3 FAILS: this round's queues are not all pinned and parsable - see A2).")
    say("")
    # ---- A
    rows, ft = res["queues"], collections.Counter()
    say("A. QUEUE FILES (outputs/*queue*.txt, %d files): job lines FLIP-SAFE / SILENT-CHANGE / FAILS-LOUDLY / "
        "OTHER-REPO" % len(rows))
    say("   formats: kind|tag|repo|wind|roles|seeds|steps|extra (the _pl / _ug / _cl / _dcd4rb / _dfp pools) and")
    say("   tag|repo|wind|roles|seed|extra (outputs/_dcd4_pool.sh, _dim_pool.sh: marked 'tag|repo format')")
    for row in rows:
        ft[row["cls"]] += 1
        say(_row_text(row))
    lt = collections.Counter()
    for row in rows:
        lt.update(row["counts"])
        lt["flips"] += row["flips"]
    say("  TOTAL lines: FLIP-SAFE %d, SILENT-CHANGE %d (REASSIGN-FLIPS %d), FAILS-LOUDLY %d, OTHER-REPO %d"
        % (lt[SAFE], lt[SILENT], lt["flips"], lt[LOUDLY], lt[OTHER]))
    say("  of which in the tag|repo format: %d lines" % tot["six_lines"])
    say("  files: " + (", ".join("%s %d" % kv for kv in sorted(ft.items())) or "none"))
    say("  (NO-JOB-LINES: other formats - read them by hand before any re-run)")
    say("")
    # ---- A2
    prow = res["pools"]
    pt = collections.Counter(r["cls"] for r in prow)
    say("A2. POOL QUEUES (outputs/*.jsonl named as queues with at least one pool line, %d files): lines FLIP-SAFE /"
        % len(prow))
    say("    SILENT-CHANGE / FAILS-LOUDLY / OTHER-REPO (a line that is not a pool line: UNCLASSIFIED)")
    for row in prow:
        say(_row_text(row))
    say("  files: " + (", ".join("%s %d" % kv for kv in sorted(pt.items())) or "none"))
    if any(r["fmts"]["args"] for r in prow):
        say("  (args-format: {\"name\", \"args\"} lines that outputs/_sd_pool.py runs in E:\\Projects\\SAS)")
    say("  POST-FLIP queues of this round (exactly these names):")
    for name in POST_FLIP_NAMES:
        r = next((r for r in prow if r["name"] == name), None)
        if r is not None:
            n_lines = sum(r["counts"][c] for c in ALL_LINE_CLASSES)
            say("    %-40s %d lines (unpinned %d, pinned %d, other repo %d%s)" % (
                name, n_lines, r["counts"][SILENT] + r["counts"][LOUDLY], r["counts"][SAFE], r["counts"][OTHER],
                (", UNCLASSIFIED %d" % r["counts"][UNCL]) if r["counts"][UNCL] else ""))
        elif name in res["notpool"]:
            say("    %-40s PRESENT, no pool line" % name)
        else:
            say("    %-40s ABSENT (not written yet)" % name)
    say("  not pool queues (no line is a pool line: not JSON, not an object, or without an argv / args list): %d"
        % len(res["notpool"]))
    for chunk in _wrap_names(res["notpool"]):
        say("    " + chunk)
    say("  NOT READ (.jsonl whose name is not a queue name; analysis outputs may hold outcomes): %d" % len(res["notread"]))
    for chunk in _wrap_names(res["notread"]):
        say("    " + chunk)
    say("")
    # ---- A3
    say("A3. OTHER-REPO CHECKOUTS named by A / A2 lines (%d): lines, present on disk" % len(res["other_repos"]))
    for key in sorted(res["other_repos"]):
        path = res["other_names"][key]
        try:
            present = "present" if ctx.isdir(path) else "ABSENT"
        except Refused:
            present = "REFUSED (quarantine name)"
        say("  %-52s %5d  %s" % (path, res["other_repos"][key], present))
    say("")
    # ---- B
    runners = res["runners"]
    say("B. RUNNERS (outputs/*.sh, outputs/*.ps1, %d files)" % len(runners))
    cnt = collections.Counter()
    for n, cls, code, kinds in runners:
        cnt[cls] += 1
        tag = cls + (" (REASSIGN-FLIPS)" if code == "REASSIGN-FLIPS" else "")
        say("  %-40s %-18s %s" % (n, tag, ",".join(kinds) or "-"))
    say("  " + (", ".join("%s %d" % kv for kv in sorted(cnt.items())) or "none"))
    say("  (a runner that feeds the pool takes the meaning of the queue it feeds: A / A2)")
    say("")
    # ---- C
    say("C. ENTRY POINTS AND THE SUITE (tracked root *.py that build the model: git ls-files ':(glob)*.py')")
    for rel in res["entry"] or []:
        say("  %-40s runs the model -> the SHIPPED values (intended: this is the ship)" % rel)
    say("  tests/ (the suite)                       runs on the flipped tree; report section 10: every test pinning")
    say("                                           today's dispatch is pinned to DISPATCH_JOINT = 0 explicitly with")
    say("                                           its ON counterpart, and the T-NT scope pins re-based (the suite")
    say("                                           returns to {T5}).")
    say("  tracked tests/ files naming DISPATCH_JOINT / DISPATCH_REASSIGN (%d):" % len(res["tests"] or []))
    for rel, nj, nr in res["tests"] or []:
        say("    %-50s %s x%d, %s x%d" % (rel, KJ, nj, KR, nr))
    st = res["shipped_test"]
    if st:
        say("  test_shipped_defaults (%s) asserts %s == 1: %s; %s == 1: %s" % (
            st[0], KJ, _assert_text(st[1]), KR, _assert_text(st[2])))
    else:
        say("  test_shipped_defaults: NOT FOUND in the tracked tests/")
    say("")
    # ---- D
    outpy = sorted(res["simpy"].items())
    say("D. PYTHON IN outputs/ THAT RUNS THE MODEL (non-recursive: %d files)" % len(outpy))
    say("  FLIP-SAFE (the text pins DISPATCH_JOINT) %d, SILENT-CHANGE %d:" % (
        sum(1 for _n, (c, _k) in outpy if c == SAFE), sum(1 for _n, (c, _k) in outpy if c != SAFE)))
    for n, (cls, code) in outpy:
        say("  %-44s %s%s" % (n, cls, " (REASSIGN-FLIPS)" if code == "REASSIGN-FLIPS" else ""))
    say("  (the harnesses and probes pass the queue line's --set through; their meaning is the line's, A / A2)")
    say("")
    say("WHAT TO DO BEFORE RE-RUNNING ANY SILENT-CHANGE LINE: add --set DISPATCH_JOINT=0 (and --set")
    say("DISPATCH_REASSIGN=0) to reproduce its recorded pre-flip meaning - today's dispatch exactly (the screen's S1:")
    say("dq0 == dqR on 64 / 64 cells). A REASSIGN-FLIPS line keeps its DISPATCH_JOINT=1 and adds --set")
    say("DISPATCH_REASSIGN=0 (J without reassignment, as recorded). A FAILS-LOUDLY line is refused by its analyzer as it")
    say("stands: re-run it only through a new, pinned queue. An UNCLASSIFIED line is read by hand. This register covers")
    say("THIS flip only (the earlier flips: outputs/movement_flip_register.txt and its predecessors). The recorded runs")
    say("themselves are unaffected (they are files); only a re-run changes meaning.")
    return out


def _assert_text(vals) -> str:
    if vals and all(v == "1" for v in vals):
        return "yes"
    return ("NO (asserts == %s)" % " / ".join(vals)) if vals else "NO (no == assert)"


def render_bytes(ctx, res, head) -> bytes:
    return ("\n".join(render(ctx, res, head)) + "\n").encode("utf-8")


# ----------------------------------------------------------------------------------------------- write and analyze
def _read_lf_bytes(ctx, path: str) -> bytes:
    ctx.guard(path)
    with open(path, "rb") as fh:
        return fh.read().replace(b"\r\n", b"\n")


def recorded_head(text: str):
    m = re.search(r"write --head ([0-9a-f]{40})\b", text or "")
    return m.group(1) if m else None


def same_record(old: bytes, new: bytes) -> bool:
    """`old` is an earlier version of the record `new`: the same first line - this tool's register or check header -
    and the same recorded THE FLIP head."""
    o, n = old.decode("utf-8", "replace"), new.decode("utf-8", "replace")
    first = o.split("\n", 1)[0]
    head = recorded_head(o)
    return first == n.split("\n", 1)[0] and first in (REGISTER_HEADER, CHECK_HEADER) and head is not None \
        and head == recorded_head(n)


def in_use_check(ctx, path: str, data: bytes, replace: bool) -> tuple[str, list[str]]:
    """('unchanged' or 'write', notes); raises Refused. The frozen-file and name-in-use rules (see write)."""
    problems, notes = [], []
    inside = norm(os.path.dirname(os.path.abspath(path))) == norm(ctx.outputs)
    if inside:
        # the name in every other registered worktree's outputs/ (a named path, never a listing) - checked first, so an
        # unchanged record still reports a collision
        for wt in ctx.git.worktrees():
            if norm(wt) == norm(ctx.root):
                continue
            other = os.path.join(wt, "outputs", os.path.basename(path))
            if not ctx.isfile(other):
                continue
            old = _read_lf_bytes(ctx, other)
            if old == data:
                continue
            if same_record(old, data):
                notes.append("%s holds an earlier version of this record (this tool, the same flip %s): not a "
                             "collision" % (other, recorded_head(data.decode("utf-8", "replace"))[:10]))
                continue
            problems.append("%s holds a different %s: the name is in use in another checkout (no override)"
                            % (other, os.path.basename(path)))
    state = "write"
    if ctx.isfile(path):
        old = _read_lf_bytes(ctx, path)
        if old == data:
            state = "unchanged"
        elif not replace:
            problems.append("%s exists and differs (on disk sha256 %s, new %s): frozen - pass --replace to re-write it"
                            % (path, sha256(old)[:16], sha256(data)[:16]))
    elif inside and not replace:
        rel = "outputs/" + os.path.basename(path)
        if ctx.git.ls_files([rel]) or ctx.git.added_in_history(rel):
            problems.append("%s is absent but git tracks it or once added it: restore it from git, or pass --replace"
                            % rel)
    if problems:
        raise Refused("; ".join(problems))
    return state, notes


def write_atomic(path: str, data: bytes) -> None:
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def do_write(ctx, head_arg, out_path, replace: bool) -> tuple[str, bytes, dict, list[str]]:
    problems = replica_check(ctx)
    info, hp = head_check(ctx, head_arg)
    problems += hp
    if problems:
        raise Refused("; ".join(problems))
    res = scan(ctx)
    data = render_bytes(ctx, res, info)
    state, notes = in_use_check(ctx, out_path, data, replace)
    if state == "write":
        write_atomic(out_path, data)
    return state, data, res, notes


def _krow(rows, key, ok, detail):
    rows.append((key, "PASS" if ok else "FAIL", detail))


def do_analyze(ctx, register_path: str, out_path: str | None, head_arg=None,
               replace: bool = False) -> tuple[bool, list[str], str | None, list[str]]:
    """(ok, lines, the result file's state - None / 'write' / 'unchanged' / 'REFUSED: ...', notes)."""
    rows: list[tuple[str, str, str]] = []
    listed_before, refused_before = len(ctx.listed), ctx.refused
    with ListingSpy() as spy:
        reg = ctx.read(register_path) if ctx.isfile(register_path) else None
        recorded = recorded_head(reg)
        # K1
        if reg is None:
            info, hp = {"sha": None, "parent": None, "head": None}, ["the register %s does not exist" % register_path]
        elif recorded is None:
            info, hp = {"sha": None, "parent": None, "head": None}, ["no 'write --head <40-hex sha>' line in the register"]
        else:
            info, hp = head_check(ctx, recorded)
        if head_arg is not None and recorded is not None and ctx.git.resolve(head_arg) != recorded:
            hp.append("--head %s is not the recorded head %s" % (head_arg, recorded))
        _krow(rows, "K1 HEAD", not hp,
              ("the recorded --head %s is THE FLIP commit (parent %s; the accessors unchanged), an ancestor of HEAD %s; "
               "the working values are 1 / 1" % (recorded, (info["parent"] or "?")[:10], (info["head"] or "?")[:10]))
              if not hp else "; ".join(hp))
        # K2 / K3 / K4: one fresh scan
        res = scan(ctx)
        if reg is not None and info["sha"]:
            fresh = render_bytes(ctx, res, info).decode("utf-8")
            if fresh == reg:
                _krow(rows, "K2 CURRENT", True, "the register equals a fresh scan rendered at %s (%d lines)" % (
                    info["sha"][:10], fresh.count("\n")))
            else:
                diff = [d for d in difflib.unified_diff(reg.split("\n"), fresh.split("\n"), "register", "fresh scan",
                                                        n=0, lineterm="") if not d.startswith(("---", "+++", "@@"))]
                _krow(rows, "K2 CURRENT", False, "STALE: %d lines differ (re-run write --replace); first: %s" % (
                    len(diff), " | ".join(d[:100] for d in diff[:6])))
        else:
            _krow(rows, "K2 CURRENT", False, "not evaluated (no register or no recorded head)")
        tot = summary(res)
        rn = [n for n in res["notpool"] if is_round_queue(n)]
        _krow(rows, "K3 ROUND", round_clean(tot),
              "this round's queues (_dq_q_*.jsonl, POST-FLIP apart): %d files, %d lines: SILENT-CHANGE or "
              "FAILS-LOUDLY %d, UNCLASSIFIED %d; files with no pool line %d%s; pool queues %d" % (
                  tot["round_files"], tot["round_lines"], tot["round_bad"], tot["round_uncl"], tot["round_notpool"],
                  (" (%s)" % ", ".join(rn)) if rn else "", tot["round_pool_files"]))
        rp = replica_check(ctx)
    listed = ctx.listed[listed_before:]
    want = [os.path.normpath(ctx.outputs)]
    _krow(rows, "K4 QUAR", listed == want and spy.calls == want and ctx.refused == refused_before,
          "folders listed by the scan %s; os.listdir / os.scandir calls seen %s; quarantine paths refused %d" % (
              listed, spy.calls, ctx.refused - refused_before))
    _krow(rows, "K5 REPLICA", not rp, "%s verbatim" % " / ".join(fn for fn, _rel in REPLICAS) if not rp
          else "; ".join(rp))
    post = []
    for name in POST_FLIP_NAMES:
        r = next((r for r in res["pools"] if r["name"] == name), None)
        if r is not None:
            post.append("%s %d lines" % (name, sum(r["counts"][c] for c in ALL_LINE_CLASSES)))
        elif name in res["notpool"]:
            post.append("%s present, no pool line" % name)
    missing = [n for n in POST_FLIP_NAMES if n not in res["notpool"] and not any(r["name"] == n for r in res["pools"])]
    rows.append(("K6 POST", "INFO", "POST-FLIP queues: %s; not found: %s" % (", ".join(post) or "none",
                                                                          ", ".join(missing) or "none")))
    ok = all(v == "PASS" for _k, v, _t in rows if v != "INFO")
    failed = [k for k, v, _t in rows if v == "FAIL"]
    verdict = ("VERDICT: PASS - the register is current at THE FLIP %s; this round's queues keep their meaning; "
               "SILENT-CHANGE lines elsewhere %d (listed with the fix)" % ((info["sha"] or "?")[:10], tot[SILENT])
               if ok else "VERDICT: FAIL - %s" % ", ".join(failed))
    lines = [CHECK_HEADER,
             "register: %s%s" % (register_path, (" (sha256 %s)" % sha256(reg.encode("utf-8"))) if reg else ""),
             "recorded: %s" % (("outputs/_dq_flip_register.py write --head %s" % recorded) if recorded else "none")]
    lines += ["%-11s %-5s %s" % row for row in rows]
    lines.append(verdict)
    wstate, notes = None, []
    if out_path:
        data = ("\n".join(lines) + "\n").encode("utf-8")
        try:
            wstate, notes = in_use_check(ctx, out_path, data, replace)
        except Refused as exc:
            wstate = "REFUSED: %s" % exc
        else:
            if wstate == "write":
                write_atomic(out_path, data)
    return ok, lines, wstate, notes


# ------------------------------------------------------------------------------------------------------- self-test
class _T:
    def __init__(self):
        self.passed = 0
        self.failed: list[str] = []

    def ok(self, name: str, cond, detail: str = "") -> None:
        if cond:
            self.passed += 1
        else:
            self.failed.append("%s %s" % (name, detail))


class FakeGit:
    """A dict-backed git for the self-test: commits {sha: (parents, {rel: text})}."""

    def __init__(self, commits, head, ls=(), history=(), worktrees=()):
        self.commits, self.head = commits, head
        self.ls, self.history, self.wts = list(ls), set(history), list(worktrees)

    def resolve(self, rev):
        if rev == "HEAD":
            return self.head
        hits = [s for s in self.commits if rev and s.startswith(rev)]
        return hits[0] if len(hits) == 1 else None

    def show(self, sha, rel):
        return self.commits.get(sha, ((), {}))[1].get(rel)

    def first_parent(self, sha):
        parents = self.commits.get(sha, ((), {}))[0]
        return parents[0] if parents else None

    def is_ancestor(self, a, b):
        todo, seen = [b], set()
        while todo:
            s = todo.pop()
            if s == a:
                return True
            if s in seen or s not in self.commits:
                continue
            seen.add(s)
            todo.extend(self.commits[s][0])
        return False

    def ls_files(self, specs):
        out = set()
        for spec in specs:
            for p in self.ls:
                if spec == ":(glob)*.py":
                    if "/" not in p and p.endswith(".py"):
                        out.add(p)
                elif p == spec or p.startswith(spec.rstrip("/") + "/"):
                    out.add(p)
        return sorted(out)

    def added_in_history(self, rel):
        return rel in self.history

    def worktrees(self):
        return list(self.wts)


def _cfv(j, r, extra=""):
    return "X = 1\n%s%s = %s\n%s = %s\n" % (extra, KJ, j, KR, r)


def _segments(own: str, names) -> dict:
    """The source of the LAST top-level def of each name in this tool's text."""
    seg = {}
    for node in ast.parse(own).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            seg[node.name] = ast.get_source_segment(own, node)
    return seg


def _agents_text(own=None, joint_default: int = 0, joint_doc=None) -> str:
    """A synthetic agents.py holding the three accessors (from this tool's replicas); joint_default != 0 changes
    dispatch_joint's semantics (missing reads ON), joint_doc replaces its docstring only."""
    own = _own_text() if own is None else own
    seg = _segments(own, ACCESSORS)
    joint = seg["dispatch_joint"]
    if joint_default != 0:
        joint = joint.replace('"DISPATCH_JOINT", 0)', '"DISPATCH_JOINT", %d)' % joint_default)
    if joint_doc is not None:
        joint = re.sub(r'"""[\s\S]*?"""', lambda _m: '"""%s"""' % joint_doc, joint, count=1)
    return "import os\n\n\n" + "\n\n\n".join((seg["_exact_integer"], joint, seg["dispatch_reassign"])) + "\n"


def _msys_form(path: str) -> str:
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", path)
    return "/%s/%s" % (m.group(1).lower(), m.group(2).replace("\\", "/")) if m else path.replace("\\", "/")


def _kst(lines, key: str):
    """The status (PASS / FAIL / INFO) of a K row ('K3' -> its status), else None."""
    for ln in lines:
        parts = ln.split()
        if parts[:1] == [key] and len(parts) > 2:
            return parts[2]
    return None


def _kline(lines, key: str) -> str:
    return next((ln for ln in lines if ln.split()[:1] == [key]), "")


def _st_values(t):
    for v in ("1", "true", "TRUE", "1.0", " 1 ", "+1"):
        t.ok("T1 value on %r" % v, is_on(v))
    for v in ("0", "2", "0.5", "on", "none", "", "false", "-1", "1.5", "yes", "1e0x"):
        t.ok("T1 value off %r" % v, not is_on(v))


def _st_meaning(t):
    p = ["E:\\x\\outputs\\_dq_probe.py", "--crn", "--", "--seed", "1"]
    cases = [
        (p, (SILENT, "UNPINNED")),
        (p + ["--set", "BATCH_SIZE=360"], (SILENT, "UNPINNED")),
        (p + ["--set", "DISPATCH_JOINT=0"], (SAFE, "JOINT-OFF")),
        (p + ["--set", "DISPATCH_JOINT=0", "--set", "DISPATCH_REASSIGN=1"], (SAFE, "JOINT-OFF")),
        (p + ["--set", "DISPATCH_JOINT=1", "--set", "DISPATCH_REASSIGN=1"], (SAFE, "BOTH-SET")),
        (p + ["--set", "DISPATCH_JOINT=1", "--set", "DISPATCH_REASSIGN=0"], (SAFE, "BOTH-SET")),
        (p + ["--set", "DISPATCH_JOINT=1", "--set", "DISPATCH_REASSIGN=x"], (SAFE, "BOTH-SET")),
        (p + ["--set", "DISPATCH_JOINT=1"], (SILENT, "REASSIGN-FLIPS")),
        (p + ["--set", "DISPATCH_JOINT=true"], (SILENT, "REASSIGN-FLIPS")),
        (p + ["--set", "DISPATCH_JOINT=2"], (SAFE, "JOINT-OFF")),
        (p + ["--set", "DISPATCH_REASSIGN=0"], (SILENT, "UNPINNED")),
        (p + ["--set", "DISPATCH_REASSIGN=1"], (SILENT, "UNPINNED")),
        (p + ["--set", "DISPATCH_JOINT=1", "--set", "DISPATCH_JOINT=0"], (SAFE, "JOINT-OFF")),
        (p + ["--set", "DISPATCH_JOINT=0", "--set", "DISPATCH_JOINT=1"], (SILENT, "REASSIGN-FLIPS")),
        (p + ["--set=DISPATCH_JOINT=0"], (SAFE, "JOINT-OFF")),
        (p + ["--set", " DISPATCH_JOINT =0"], (SAFE, "JOINT-OFF")),
        (p + ["DISPATCH_JOINT=0"], (SILENT, "UNPINNED")),
        (p + ["--set", "DISPATCH_JOINTX=0"], (SILENT, "UNPINNED")),
        (p + ["--set", "'DISPATCH_JOINT=0'"], (SILENT, "UNPINNED")),
        (p + ["--set"], (SILENT, "UNPINNED")),
    ]
    for argv, want in cases:
        t.ok("T2 meaning %s" % " ".join(argv[5:]), dispatch_meaning(argv) == want, "got %s" % (dispatch_meaning(argv),))
    # MINOR-6: the classifier RUNS the accessor replicas - a changed replica changes the class
    g = globals()
    saved = g["dispatch_joint"]
    g["dispatch_joint"] = lambda: True  # a JOINT read ON whatever the value
    try:
        got = dispatch_meaning(p + ["--set", "DISPATCH_JOINT=0"])
    finally:
        g["dispatch_joint"] = saved
    t.ok("MINOR6 the classifier runs the accessor replicas", got == (SILENT, "REASSIGN-FLIPS"), "got %s" % (got,))
    t.ok("MINOR6 switch_state restores the namespace", not hasattr(cfv, KJ) and
         switch_state({KJ: "1"}, PRE_DEFAULTS) == (True, False) and switch_state({}, POST_DEFAULTS) == (True, True))


def _st_repo(t):
    root, main, other = r"C:\synthetic\wt", r"C:\synthetic\main", r"C:\synthetic\other"
    ctx = Ctx(root, git=FakeGit({}, None), main=main, quarantine="_qsyn_quarantine", affected=(root, main))
    pin0 = ["--set", "DISPATCH_JOINT=0"]
    probe = root + r"\outputs\_dq_probe.py"
    cases = [
        ([probe, "--", "--repo", other], None, OTHER, "T3"),
        ([probe, "--", "--repo", "c:/SYNTHETIC/main/"], None, SILENT, "T3"),
        ([probe, "--", "--repo", root] + pin0, None, SAFE, "T3"),
        ([other + r"\outputs\_rblatch_campaign2.py", "--tag", "x"], root, OTHER, "T3"),
        ([root + r"\outputs\_rblatch_campaign2.py", "--tag", "x"], other, SILENT, "T3"),
        (["outputs/_x.py"], other, OTHER, "T3"),
        (["outputs/_x.py"], None, SILENT, "T3"),
        ([probe, "--repo=" + other], None, OTHER, "T3"),
        ([probe, "--repo", other, "--repo", other.lower()], None, OTHER, "T3"),
        # NIT-4: several distinct --repo values (the probes import from the first, the harness from the last): unknown
        ([probe, "--repo", root, "--repo", other], None, SILENT, "NIT4"),
        ([probe, "--repo", other, "--repo", root], None, SILENT, "NIT4"),
        # MINOR-3: a relative --repo / cwd resolves as the run resolves it (against the run's working directory)
        ([probe, "--", "--repo", "."], root, SILENT, "MINOR3"),
        ([probe, "--", "--repo", ".."], root + r"\outputs", SILENT, "MINOR3"),
        ([probe, "--", "--repo", "..\\other"], root, OTHER, "MINOR3"),
        ([probe, "--", "--repo", "."], other, OTHER, "MINOR3"),
        ([probe, "--", "--repo", ""], other, OTHER, "MINOR3"),
        (["outputs/_x.py"], ".", SILENT, "MINOR3"),
        (["outputs/_x.py", "--repo", "."], "rel\\dir", SILENT, "MINOR3"),
        (["outputs/_x.py"], other + "\\sub\\..", OTHER, "MINOR3"),
    ]
    for argv, cwd, want, fid in cases:
        got = classify_job(ctx, "_z_q_a.jsonl", argv, argv_repo(argv, cwd), os.path.basename(argv[0]))[0]
        t.ok("%s repo %s cwd %s" % (fid, argv[1:], cwd), got == want, "got %s want %s" % (got, want))
    jobs, bad = jsonl_jobs(ctx, json.dumps({"name": "S", "args": ["--seed", "1"]}) + "\n")
    t.ok("T3 args-format runs in main", len(jobs) == 1 and not bad and norm(jobs[0][1]) == norm(main) and
         jobs[0][2] == "args")
    jobs, bad = jsonl_jobs(ctx, json.dumps({"name": "S", "args": ["--repo", other]}) + "\n")
    t.ok("T3 args-format with --repo", len(jobs) == 1 and norm(jobs[0][1]) == norm(other))
    jobs, bad = jsonl_jobs(ctx, json.dumps({"name": "S", "args": ["--repo", "..\\other"]}) + "\n")
    t.ok("MINOR3 args-format relative --repo resolves against E:/Projects/SAS (the pool's cwd)",
         len(jobs) == 1 and norm(jobs[0][1]) == norm(other), str(jobs))
    jobs, bad = jsonl_jobs(ctx, json.dumps({"name": "S", "argv": ["outputs/_dq_probe.py", "--repo", "."]}) + "\n")
    t.ok("MINOR3 a line without cwd runs in the pool's cwd (Popen(cwd=... or REPO))",
         len(jobs) == 1 and jobs[0][1] is not None and norm(jobs[0][1]) == norm(main), str(jobs))
    jobs, bad = jsonl_jobs(ctx, json.dumps({"name": "S", "argv": ["outputs/_dq_probe.py", "--repo", "."],
                                            "cwd": other}) + "\n")
    t.ok("MINOR3 control: the line's cwd wins over the pool's", len(jobs) == 1 and norm(jobs[0][1]) == norm(other))
    # MAJOR-1: the parsable lines are classified, the rest counted UNCLASSIFIED - never a silent drop
    jobs, bad = jsonl_jobs(ctx, '{"name": "a", "argv": ["x"]}\n{"a": 1}\n')
    t.ok("MAJOR1 a non-pool line is UNCLASSIFIED, the pool line kept", len(jobs) == 1 and bad == 1, str((jobs, bad)))
    jobs, bad = jsonl_jobs(ctx, '{"argv": []}\n[1, 2]\n"s"\nnot json\n{"name": "b", "argv": ["x"]}\n')
    t.ok("MAJOR1 every non-pool line counts", len(jobs) == 1 and bad == 4, str((jobs, bad)))
    t.ok("MAJOR1 junk alone: no job, UNCLASSIFIED", jsonl_jobs(ctx, "not json\n") == ([], 1))
    t.ok("T3 empty is not a queue", jsonl_jobs(ctx, "\n\n") == ([], 0))
    # pipe lines
    pl = [
        # 8-field kind|tag|repo|wind|roles|seeds|steps|extra
        ("ff|xA|C:/synthetic/main|east|half|101|360|--set BATCH_SIZE=360", SILENT, "T4"),
        ("ff|xA|C:/synthetic/wt|east|half|101|360|--set DISPATCH_JOINT=0", SAFE, "T4"),
        ("rb|xB|C:/synthetic/other|east|half|101|240|", SILENT, "T4"),
        ("rb|xB|C:/synthetic/other|east|half|101|240|--set DISPATCH_JOINT=0", SAFE, "T4"),
        ("ff|xB|C:/synthetic/other|east|half|101|240|", OTHER, "T4"),
        ("fo|xC|C:/synthetic/other|east|half|101|360|--uav-actions", OTHER, "T4"),
        ("fc|xC|C:/synthetic/other|east|half|101|360|", OTHER, "T4"),
        ("ff|xD|C:/synthetic/wt|east|half|101|360|--set DISPATCH_JOINT=1", SILENT, "T4"),
        ("ff|xE|east|half|101|360|a|b", SILENT, "T4"),
        # MINOR-2: bash does not remove quotes that come from an unquoted $extra expansion
        ("ff|xA|C:/synthetic/wt|east|half|101|360|--set 'DISPATCH_JOINT=0'", SILENT, "MINOR2"),
        ('ff|xA|C:/synthetic/wt|east|half|101|360|--set "DISPATCH_JOINT=0"', SILENT, "MINOR2"),
        ("ff|xA|C:/synthetic/wt|east|half|101|360|--set DISPATCH_JOINT='0'", SAFE, "MINOR2"),
        # MINOR-3 (pipe): Git Bash hands /c/... to the native harness as C:/...; a relative repo is unknown
        ("ff|xF|/c/synthetic/main|east|half|101|360|", SILENT, "MINOR3"),
        ("ff|xF|/c/synthetic/other|east|half|101|360|", OTHER, "MINOR3"),
        ("ff|xF|../synthetic/other|east|half|101|360|", SILENT, "MINOR3"),
        # MINOR-4: tag|repo|wind|roles|seed|extra (outputs/_dcd4_pool.sh, outputs/_dim_pool.sh: --repo "$repo")
        ("t6|C:/synthetic/main|east|half|101|--set BATCH_SIZE=360", SILENT, "MINOR4"),
        ("t6|C:/synthetic/wt|east|half|101|--set DISPATCH_JOINT=0", SAFE, "MINOR4"),
        ("t6|C:/synthetic/other|east|half|101|", OTHER, "MINOR4"),
        ("t6|/c/synthetic/main|east|half|101|", SILENT, "MINOR4"),
        ("t6|/c/synthetic/other|east|half|101|--set DISPATCH_JOINT=0", OTHER, "MINOR4"),
        ("t6|./wt|east|half|101|", SILENT, "MINOR4"),
        ("t6|C:/synthetic/wt|east|half|101|--set DISPATCH_JOINT=1", SILENT, "MINOR4"),
        ("t6|C:/synthetic/other|east|half|101|--set DISPATCH_JOINT=0 | x | y", OTHER, "MINOR4"),
    ]
    for ln, want, fid in pl:
        job = pipe_job(ln)
        got = classify_job(ctx, "_x_queue.txt", job[3], job[2], None)[0] if job else None
        t.ok("%s pipe %s" % (fid, ln[:48]), got == want, "got %s" % got)
    t.ok("MINOR4 the two formats are told apart",
         (pipe_job("t6|C:/a|east|half|1|x") or ("",))[0] == "6f" and
         (pipe_job("ff|t|C:/a|east|half|1|360|x") or ("",))[0] == "8f")
    for ln in ("# ff|xA|C:/synthetic/main|east|half|101|360|", "bsbase|east|101|x", "a|b|c|d|e", "l808|east|1",
               "", "   "):
        t.ok("T4 not a job line %r" % ln[:20], pipe_job(ln) is None)


def _st_affected(t):
    """MINOR-5: the affected set is the constant, whichever checkout the tool runs from (no filesystem access)."""
    want = {norm(DISPATCH_WT), norm(MAIN)}
    for root in (MAIN, DISPATCH_WT, ROOT, r"C:\somewhere\else"):
        ctx = Ctx(root, git=FakeGit({}, None))
        t.ok("MINOR5 the affected set is the constant from %s" % root, ctx.affected == want, str(ctx.affected))
    ctx = Ctx(MAIN, git=FakeGit({}, None))
    probe = DISPATCH_WT + r"\outputs\_dq_probe.py"
    line = [probe, "--", "--repo", DISPATCH_WT]
    t.ok("MINOR5 run from main, a dispatch-worktree line is affected",
         classify_job(ctx, "_dq_q_struct.jsonl", line, argv_repo(line), "_dq_probe.py")[0] == SILENT)
    t.ok("MINOR5 run from main, an unpinned W2 line is FAILS-LOUDLY (not OTHER-REPO)",
         classify_job(ctx, "_dq_q_w2.jsonl", line, argv_repo(line), "_dq_probe.py")[0] == LOUDLY)
    base = r"E:\Projects\SAS_wt\base897e93b5"
    t.ok("MINOR5 control: another checkout is OTHER-REPO",
         classify_job(ctx, "_dq_q_w1.jsonl", [probe, "--repo", base], base, "_dq_probe.py")[0] == OTHER)


def _st_loud(t):
    root, other = r"C:\synthetic\wt", r"C:\synthetic\other"
    ctx = Ctx(root, git=FakeGit({}, None), main=r"C:\synthetic\main", quarantine="_qsyn_quarantine",
              affected=(root, r"C:\synthetic\main"))
    un = ["x.py", "--repo", root]
    cases = [
        ("_dq_q_w1.jsonl", un, "_dq_probe.py", LOUDLY),
        ("_dq_q_w2.jsonl", un + ["--set", "DISPATCH_JOINT=1"], "_dq_probe.py", LOUDLY),
        ("_dq_q_w3.jsonl", un, "_dq_replay.py", LOUDLY),
        ("_dq_q_smoke.jsonl", un, "_dq_probe.py", LOUDLY),
        ("_dq_q_w1.jsonl", un + ["--set", "DISPATCH_JOINT=0"], "_dq_probe.py", SAFE),
        ("_dq_q_w1.jsonl", ["x.py", "--repo", other], "_dq_probe.py", OTHER),
        ("_dq_q_struct.jsonl", un, "_dq_probe.py", SILENT),
        ("_dp_q_identity.jsonl", un, "_dp_probe.py", LOUDLY),
        ("_dp_q_on.jsonl", un, "_dp_probe.py", LOUDLY),
        ("_dp_q_identity.jsonl", un, "_rblatch_campaign2.py", SILENT),
        ("_dp_q_evidence.jsonl", un, "_dp_probe.py", SILENT),
        ("_mvg_q_w1.jsonl", un, "_mvg_probe.py", SILENT),
    ]
    for fname, argv, script, want in cases:
        got = classify_job(ctx, fname, argv, argv_repo(argv), script)[0]
        t.ok("T5 loud %s %s" % (fname, script), got == want, "got %s want %s" % (got, want))
    c = collections.Counter
    fc = [("_dq_q_flipid.jsonl", c({SILENT: 3}), POST, "T6"), ("_dq_q_refs.jsonl", c({SAFE: 1}), POST, "T6"),
          ("_dq_q_ist.jsonl", c(), POST, "T6"), ("_dq_q_refsx.jsonl", c({SAFE: 1}), SAFE, "T6"),
          ("_dq_q_refs_s1.jsonl", c({SILENT: 1}), SILENT, "MINOR7"),
          ("_dq_q_ist_s1.jsonl", c({SAFE: 1}), SAFE, "MINOR7"),
          ("_DQ_Q_FLIPID.JSONL", c({SILENT: 1}), SILENT, "MINOR7"),
          ("_a.jsonl", c({SILENT: 1, LOUDLY: 5}), SILENT, "T6"), ("_a.jsonl", c({LOUDLY: 1, SAFE: 5}), LOUDLY, "T6"),
          ("_a.jsonl", c({SAFE: 1, OTHER: 5}), SAFE, "T6"), ("_a.jsonl", c({OTHER: 1}), OTHER, "T6"),
          ("_a.txt", c(), NOJOB, "T6"),
          ("_a.jsonl", c({SAFE: 3, UNCL: 1}), UNCL, "MAJOR1"), ("_a.jsonl", c({LOUDLY: 3, UNCL: 1}), UNCL, "MAJOR1"),
          ("_a.jsonl", c({SILENT: 1, UNCL: 1}), SILENT, "MAJOR1")]
    for name, counts, want, fid in fc:
        t.ok("%s file class %s %s" % (fid, name, dict(counts)), file_class(name, counts) == want,
             "got %s" % file_class(name, counts))
    t.ok("T6 round queue rule", is_round_queue("_dq_q_w1.jsonl") and not is_round_queue("_dp_q_on.jsonl") and
         not is_round_queue("_dq_q_ist.jsonl"))
    t.ok("MINOR7 a slice of a post-flip name is a round queue", is_round_queue("_dq_q_ist_s1.jsonl") and
         is_round_queue("_dq_q_flipid_w1_extra.jsonl") and is_round_queue("_DQ_Q_REFS.JSONL"))
    t.ok("T6 queue-name rule", all(QUEUE_NAME_RE.search(n) for n in ("_bp_q_all.jsonl", "_ist3_q.jsonl",
                                                                     "_sd_queue_p4.jsonl")) and
         not any(QUEUE_NAME_RE.search(n) for n in ("_bp_metrics.jsonl", "_mf2_an_mf2A1.jsonl")))


def _st_text(t):
    h = "python outputs/_ffr_harness.py --repo X "
    cases = [
        (h, (SILENT, "UNPINNED")),
        (h + "--set DISPATCH_JOINT=0", (SAFE, "PINS-JOINT")),
        (h + "'--set','DISPATCH_JOINT=0'", (SAFE, "PINS-JOINT")),
        (h + "--set DISPATCH_JOINT=1", (SILENT, "REASSIGN-FLIPS")),
        (h + "--set DISPATCH_JOINT=1.0", (SILENT, "REASSIGN-FLIPS")),
        (h + "--set DISPATCH_JOINT=1 --set DISPATCH_REASSIGN=0", (SAFE, "PINS-JOINT")),
        (h + "--set DISPATCH_JOINT=10", (SAFE, "PINS-JOINT")),
        ("cfv.DISPATCH_JOINT = 0\n", (SAFE, "PINS-JOINT")),
        ("cfv.DISPATCH_JOINT = 1\n", (SILENT, "REASSIGN-FLIPS")),
        ("setattr(cfv, 'DISPATCH_JOINT', 1)\nsetattr(cfv, 'DISPATCH_REASSIGN', 1)\n", (SAFE, "PINS-JOINT")),
        ("if cfv.DISPATCH_JOINT == 1:\n", (SILENT, "UNPINNED")),
        ("# while DISPATCH_JOINT is on\n", (SILENT, "UNPINNED")),
        ('"DISPATCH_JOINT": repr(x)\n', (SILENT, "UNPINNED")),
    ]
    for text, want in cases:
        t.ok("T7 text %r" % text[-40:], text_meaning(text) == want, "got %s" % (text_meaning(text),))


def _mk(path: str, text) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(text if isinstance(text, bytes) else text.encode("utf-8"))


def _pl(argv, cwd=None):
    d = {"name": "n", "argv": argv, "out": "o"}
    if cwd:
        d["cwd"] = cwd
    return json.dumps(d) + "\n"


SHIPPED_TEST = ("def test_other():\n    pass\n\n\ndef test_shipped_defaults():\n    assert cfv.DISPATCH_JOINT == %s\n"
                "    assert cfv.DISPATCH_REASSIGN == %s\n\n\ndef test_after():\n    pass\n")


def _synthetic_tree(tmp: str) -> tuple:
    """A synthetic checkout: (ctx, fake git, shas, second worktree, other repo)."""
    root = os.path.join(tmp, "wt")
    main = os.path.join(tmp, "mainco")
    other = os.path.join(tmp, "elsewhere")
    wt2 = os.path.join(tmp, "wt2")
    q = "_qsyn_quarantine"
    o = os.path.join(root, "outputs")
    own = _own_text()
    seg = _segments(own, ("_parse_value",))
    ag = _agents_text(own)
    _mk(os.path.join(root, AGENTS), ag)
    _mk(os.path.join(o, "_ffr_harness.py"), "import os\n\n\n" + seg["_parse_value"] + "\n")
    _mk(os.path.join(root, CFV), _cfv(1, 1))
    _mk(os.path.join(root, "main.py"), "import os\nfrom wild" + "fire_model import WildFireModel\n")
    _mk(os.path.join(root, "helper.py"), "import os\n")
    _mk(os.path.join(root, "wildfire_model.py"), "import agents\n")
    _mk(os.path.join(root, "tests", "test_a.py"), "def test_x():\n    run(['--set', 'DISPATCH_JOINT=0'])\n")
    _mk(os.path.join(root, "tests", "test_base_station.py"), SHIPPED_TEST % (1, 1))
    rq = lambda r: r.replace("\\", "/")  # noqa: E731
    _mk(os.path.join(o, "_x_queue.txt"), "# a comment\n"
        "ff|xA|%s|east|half|101|360|--set BATCH_SIZE=360\n" % rq(main) +
        "ff|xA|%s|east|half|101|360|--set DISPATCH_JOINT=0\n" % rq(root) +
        "rb|xB|%s|east|half|101|240|\n" % rq(other) +
        "fo|xC|%s|east|half|101|360|--uav-actions\n" % rq(other) +
        "ff|xD|%s|east|half|101|360|--set DISPATCH_JOINT=1\n" % rq(root))
    _mk(os.path.join(o, "_six_queue.txt"), "# tag|repo|wind|roles|seed|extra\n"
        "t6|%s|east|half|101|--set BATCH_SIZE=360\n" % rq(main) +
        "t6|%s|east|half|101|--set DISPATCH_JOINT=0\n" % _msys_form(root) +
        "t6|%s|east|half|101|\n" % rq(other) +
        "t6|%s|east|half|101|--set 'DISPATCH_JOINT=0'\n" % rq(root))
    _mk(os.path.join(o, "_old_queue.txt"), "bsbase|east|101\n")
    _mk(os.path.join(o, "_safe_queue.txt"), "ff|s|%s|east|half|1|360|--set DISPATCH_JOINT=0\n" % rq(root))
    probe = os.path.join(o, "_dq_probe.py")
    _mk(os.path.join(o, "_dq_q_w1.jsonl"),
        _pl([probe, "--", "--repo", root, "--set", "DISPATCH_JOINT=0", "--set", "DISPATCH_REASSIGN=0"], root) +
        _pl([probe, "--", "--repo", other], other))
    _mk(os.path.join(o, "_dq_q_smoke.jsonl"), _pl([probe, "--", "--repo", root], root))
    _mk(os.path.join(o, "_dp_q_identity.jsonl"),
        _pl([os.path.join(o, "_dp_probe.py"), "--", "--repo", root], root) +
        _pl([os.path.join(o, "_rblatch_campaign2.py"), "--tag", "g"], root))
    _mk(os.path.join(o, "_dp_q_on.jsonl"), _pl([os.path.join(o, "_dp_probe.py"), "--", "--repo", root], root))
    _mk(os.path.join(o, "_dq_q_flipid.jsonl"), _pl([probe, "--", "--repo", root], root))
    _mk(os.path.join(o, "_sd_queue_x.jsonl"), json.dumps({"name": "a", "args": ["--seed", "1"]}) + "\n" +
        json.dumps({"name": "b", "args": ["--seed", "2"]}) + "\n")
    _mk(os.path.join(o, "_mixed_q.jsonl"), _pl([probe, "--", "--repo", root], root) + '{"name": "x"}\n')
    _mk(os.path.join(o, "_mixed2_q.jsonl"), _pl([probe, "--", "--repo", root] + ["--set", "DISPATCH_JOINT=0"], root) +
        "junk\n")
    _mk(os.path.join(o, "_metrics.jsonl"), json.dumps({"rescued": 3}) + "\n")
    _mk(os.path.join(o, "_bad_q.jsonl"), "not json\n")
    _mk(os.path.join(o, "_r1.sh"), "python outputs/_ffr_harness.py --repo X\n")
    _mk(os.path.join(o, "_r2.sh"), "python outputs/_ffr_harness.py --set DISPATCH_JOINT=0\n")
    _mk(os.path.join(o, "_r3.ps1"), "Write-Host hi\n")
    _mk(os.path.join(o, "_r4.sh"), "python outputs/_ffr_harness.py '--set','DISPATCH_JOINT=1'\n")
    _mk(os.path.join(o, "_r5.sh"), "python outputs/_p1.py\n")
    _mk(os.path.join(o, "_p1.py"), "import os\nimport wild" + "fire_model as wf\n")
    _mk(os.path.join(o, "_p2.py"), "import wild" + "fire_model as wf\ncfv.DISPATCH_JOINT = 0\n")
    _mk(os.path.join(o, "_p3.py"), "print('DISPATCH_JOINT is on')\n")
    _mk(os.path.join(o, q, "_evil_queue.txt"), "ff|e|%s|east|half|1|360|\n" % rq(root))
    _mk(os.path.join(o, q, "_evil_q_a.jsonl"), _pl([probe, "--repo", root]))
    _mk(os.path.join(o, "_sub", "_sub_queue.txt"), "ff|s|%s|east|half|1|360|\n" % rq(root))
    os.makedirs(os.path.join(o, "_dir_queue.txt"), exist_ok=True)
    os.makedirs(os.path.join(wt2, "outputs"), exist_ok=True)
    c0, c1, c2, side = "a" * 40, "b" * 40, "c" * 40, "d" * 40
    commits = {c0: ((), {CFV: _cfv(0, 0), AGENTS: ag}), c1: ((c0,), {CFV: _cfv(1, 1), AGENTS: ag}),
               c2: ((c1,), {CFV: _cfv(1, 1), AGENTS: ag}), side: ((c0,), {CFV: _cfv(0, 0), AGENTS: ag})}
    ls = ["agents.py", CFV, "helper.py", "main.py", "wildfire_model.py", "tests/test_a.py",
          "tests/test_base_station.py", "tests/data.txt", "outputs/_dq_probe.py"]
    git = FakeGit(commits, c2, ls=ls, worktrees=[root, wt2])
    ctx = Ctx(root, git=git, main=main, quarantine=q, affected=(root, main))
    return ctx, git, (c0, c1, c2, side), wt2, other


def _row(res, name):
    for row in res["queues"] + res["pools"]:
        if row["name"] == name:
            return row
    return None


def _st_scan(t, tmp):
    ctx, git, _shas, _wt2, other = _synthetic_tree(tmp)
    calls = []
    real_listdir = os.listdir

    def spy(path="."):
        calls.append(os.path.normpath(path))
        return real_listdir(path)

    os.listdir = spy
    try:
        with ListingSpy() as lspy:
            res = scan(ctx)
        try:
            ctx.listdir(os.path.join(ctx.outputs, ctx.quarantine))
            guarded = False
        except Refused:
            guarded = True
    finally:
        os.listdir = real_listdir
    t.ok("T8 one listing, of outputs/", calls == [os.path.normpath(ctx.outputs)], "calls %s" % calls)
    t.ok("MINOR9 the os-level spy sees the scan's one listing", lspy.calls == [os.path.normpath(ctx.outputs)],
         str(lspy.calls))
    t.ok("T8 quarantine guard refuses before any listing", guarded and len(calls) == 1 and ctx.refused == 1)
    names = {r["name"] for r in res["queues"] + res["pools"]}
    t.ok("T8 nothing from inside the quarantine or a subdirectory",
         not names & {"_evil_queue.txt", "_evil_q_a.jsonl", "_sub_queue.txt", "_dir_queue.txt"}, str(names))

    def want(name, safe, silent, loud, oth, cls, flips=0, uncl=0, fid="T8"):
        r = _row(res, name)
        got = r and (r["counts"][SAFE], r["counts"][SILENT], r["counts"][LOUDLY], r["counts"][OTHER], r["cls"],
                     r["flips"], r["counts"][UNCL])
        t.ok("%s row %s" % (fid, name), got == (safe, silent, loud, oth, cls, flips, uncl), "got %s" % (got,))

    want("_x_queue.txt", 1, 3, 0, 1, SILENT, 1)
    want("_six_queue.txt", 1, 2, 0, 1, SILENT, fid="MINOR4")
    want("_old_queue.txt", 0, 0, 0, 0, NOJOB)
    want("_safe_queue.txt", 1, 0, 0, 0, SAFE)
    want("_dq_q_w1.jsonl", 1, 0, 0, 1, SAFE)
    want("_dq_q_smoke.jsonl", 0, 0, 1, 0, LOUDLY)
    want("_dp_q_identity.jsonl", 0, 1, 1, 0, SILENT)
    want("_dp_q_on.jsonl", 0, 0, 1, 0, LOUDLY)
    want("_dq_q_flipid.jsonl", 0, 1, 0, 0, POST)
    want("_sd_queue_x.jsonl", 0, 2, 0, 0, SILENT)
    want("_mixed_q.jsonl", 0, 1, 0, 0, SILENT, uncl=1, fid="MAJOR1")
    want("_mixed2_q.jsonl", 1, 0, 0, 0, UNCL, uncl=1, fid="MAJOR1")
    t.ok("MINOR4 the tag|repo rows are marked", (_row(res, "_six_queue.txt") or {"fmts": {}})["fmts"].get("6f") == 4)
    t.ok("T8 non-queue .jsonl not read", res["notread"] == ["_metrics.jsonl"], str(res["notread"]))
    t.ok("T8 invalid queue file reported", res["notpool"] == ["_bad_q.jsonl"], str(res["notpool"]))
    rn = {n: (cls, code, kinds) for n, cls, code, kinds in res["runners"]}
    t.ok("T8 runner unpinned", rn.get("_r1.sh", (None,))[0] == SILENT)
    t.ok("T8 runner pinned", rn.get("_r2.sh", (None,))[0] == SAFE)
    t.ok("T8 runner not a simulation", rn.get("_r3.ps1", (None,))[0] == NOTSIM)
    t.ok("T8 runner JOINT=1 alone", rn.get("_r4.sh", (None, None))[:2] == (SILENT, "REASSIGN-FLIPS"))
    t.ok("T8 runner of a model script", rn.get("_r5.sh", (None, None, []))[0] == SILENT and
         "_p1.py" in rn.get("_r5.sh", (None, None, []))[2])
    t.ok("T8 D unpinned", res["simpy"].get("_p1.py", (None,))[0] == SILENT)
    t.ok("T8 D pinned", res["simpy"].get("_p2.py", (None,))[0] == SAFE)
    t.ok("T8 D excludes non-model", "_p3.py" not in res["simpy"] and "_ffr_harness.py" not in res["simpy"])
    t.ok("T8 entry points", res["entry"] == ["main.py"], str(res["entry"]))
    t.ok("T8 tests naming the keys", [r[0] for r in res["tests"]] == ["tests/test_a.py", "tests/test_base_station.py"],
         str(res["tests"]))
    t.ok("NIT2 test_shipped_defaults: the asserted values are read",
         res["shipped_test"] == ("tests/test_base_station.py", ["1"], ["1"]), str(res["shipped_test"]))
    t.ok("T8 other repos", dict(res["other_repos"]) == {norm(other): 3}, str(dict(res["other_repos"])))
    tot = summary(res)
    got = (tot[SAFE], tot[SILENT], tot[LOUDLY], tot[OTHER], tot["flips"], tot["round_files"], tot["round_bad"],
           tot["post_files"], tot[UNCL], tot["round_uncl"], tot["round_notpool"], tot["six_lines"])
    t.ok("T8 summary", got == (5, 10, 3, 3, 1, 2, 1, 1, 2, 0, 0, 4), str(got))
    head = {"sha": "b" * 40, "parent": "a" * 40}
    r1, r2 = render(ctx, res, head), render(ctx, scan(ctx), head)
    t.ok("T8 deterministic rendering", r1 == r2)
    text = "\n".join(r1)
    t.ok("T8 rendering records --head", ("write --head " + "b" * 40) in text)
    t.ok("T8 rendering lists ABSENT post-flip queues", "_dq_q_ist.jsonl" in text and "ABSENT" in text)
    t.ok("T8 rendering closes with the fix", "add --set DISPATCH_JOINT=0 (and --set" in text)
    t.ok("T8 rendering is ASCII", all(ord(ch) < 128 for ch in text))
    t.ok("NIT1 the summary does not claim pinned queues when K3 fails",
         "pin both keys" not in text and "K3 FAILS" in text)
    t.ok("MINOR4 the rendering counts the tag|repo format", "tag|repo format: 4 lines" in text)
    t.ok("MINOR5 the rendering names the constant affected set", "AFFECTED CHECKOUTS (a constant" in text)
    t.ok("NIT2 rendering: asserts == 1 yes", "asserts DISPATCH_JOINT == 1: yes; DISPATCH_REASSIGN == 1: yes" in text)
    _mk(os.path.join(ctx.root, "tests", "test_base_station.py"), SHIPPED_TEST % (0, 0))
    text0 = "\n".join(render(ctx, scan(ctx), head))
    t.ok("NIT2 a pre-flip test_shipped_defaults (== 0) reads NO",
         "asserts DISPATCH_JOINT == 1: NO (asserts == 0); DISPATCH_REASSIGN == 1: NO (asserts == 0)" in text0)
    _mk(os.path.join(ctx.root, "tests", "test_base_station.py"), SHIPPED_TEST % (1, 1))
    os.remove(os.path.join(ctx.outputs, "_dq_q_smoke.jsonl"))
    text1 = "\n".join(render(ctx, scan(ctx), head))
    t.ok("NIT1 control: clean round queues keep the pinned note", "pin both keys" in text1 and "K3 FAILS" not in text1)
    # a sub-guard: a file path containing the quarantine name is refused before open
    try:
        ctx.read(os.path.join(ctx.outputs, ctx.quarantine, "_evil_queue.txt"))
        t.ok("T8 read guard", False)
    except Refused:
        t.ok("T8 read guard", True)


def _st_head(t, tmp):
    ctx, git, (c0, c1, c2, side), _wt2, _other = _synthetic_tree(tmp)
    info, p = head_check(ctx, c1)
    t.ok("T9 the flip commit passes", not p and info["sha"] == c1 and info["parent"] == c0, str(p))
    t.ok("T9 a short sha resolves", not head_check(ctx, c1[:10])[1])
    t.ok("T9 the pre-flip commit fails", bool(head_check(ctx, c0)[1]))
    t.ok("T9 a later commit (parent already 1 / 1) fails", bool(head_check(ctx, c2)[1]))
    t.ok("T9 an unknown sha fails", bool(head_check(ctx, "f" * 40)[1]))
    t.ok("T9 no --head fails", bool(head_check(ctx, None)[1]))
    git.head = side
    t.ok("T9 not an ancestor of HEAD fails", bool(head_check(ctx, c1)[1]))
    git.head = c2
    _mk(os.path.join(ctx.root, CFV), _cfv(0, 0))
    t.ok("T9 working values 0 / 0 fail", bool(head_check(ctx, c1)[1]))
    _mk(os.path.join(ctx.root, CFV), _cfv(1, 1))
    t.ok("T9 working values restored pass", not head_check(ctx, c1)[1])
    # NIT-3: HEAD itself must still hold 1 / 1 (a later revert is not hidden by a 1 / 1 working copy)
    c3 = "e" * 40
    git.commits[c3] = ((c2,), {CFV: _cfv(0, 0), AGENTS: _agents_text()})
    git.head = c3
    hp = head_check(ctx, c1)[1]
    t.ok("NIT3 a HEAD that reverted the defaults fails (working copy 1 / 1)", any("HEAD eeeeeeeeee" in x for x in hp),
         str(hp))
    git.head = c2
    t.ok("NIT3 control: HEAD with 1 / 1 passes", not head_check(ctx, c1)[1])
    # MINOR-6: the accessors at THE FLIP vs its parent (and vs the replicas the classifier runs)
    own = _own_text()
    ag_ok, ag_on = _agents_text(own), _agents_text(own, joint_default=1)
    ag_doc = _agents_text(own, joint_doc="Ships 1 since THE FLIP (a docstring-only edit).")
    t.ok("MINOR6 self-check: the synthetic mutations applied", ag_on != ag_ok and ag_doc != ag_ok and
         _fn_shape(ag_doc, "dispatch_joint") == _fn_shape(ag_ok, "dispatch_joint") and
         _fn_shape(ag_on, "dispatch_joint") != _fn_shape(ag_ok, "dispatch_joint"))
    p1, f1, f2, p3, f3, f4 = "1" * 40, "2" * 40, "3" * 40, "4" * 40, "5" * 40, "6" * 40
    git.commits[p1] = ((), {CFV: _cfv(0, 0), AGENTS: ag_ok})
    git.commits[f1] = ((p1,), {CFV: _cfv(1, 1), AGENTS: ag_on})
    git.commits[f2] = ((p1,), {CFV: _cfv(1, 1), AGENTS: ag_doc})
    git.commits[p3] = ((), {CFV: _cfv(0, 0), AGENTS: ag_on})
    git.commits[f3] = ((p3,), {CFV: _cfv(1, 1), AGENTS: ag_on})
    git.commits[f4] = ((p1,), {CFV: _cfv(1, 1)})
    for sha, label, bad, needle in (
            (f1, "an accessor changed by THE FLIP (missing reads ON) fails", True, "differs between THE FLIP"),
            (f2, "control: a docstring-only accessor edit passes", False, ""),
            (f3, "accessors unchanged but not the replica fail", True, "is not this tool's replica"),
            (f4, "agents.py missing at THE FLIP fails", True, "differs between THE FLIP")):
        git.head = sha
        hp = head_check(ctx, sha)[1]
        t.ok("MINOR6 %s" % label, (any(needle in x for x in hp) if bad else not hp), str(hp))
    git.head = c2
    # MINOR-6 (working copy): the replica check covers dispatch_joint / dispatch_reassign; the LAST def is compared
    _mk(os.path.join(ctx.root, AGENTS), ag_on)
    t.ok("MINOR6 a drifted dispatch_joint in the working copy fails the replica check",
         any("dispatch_joint" in x for x in replica_check(ctx)), str(replica_check(ctx)))
    _mk(os.path.join(ctx.root, AGENTS), ag_ok + "\n\ndef dispatch_reassign() -> bool:\n    return True\n")
    t.ok("MINOR6 a later def of the same name is the one compared",
         any("dispatch_reassign" in x for x in replica_check(ctx)), str(replica_check(ctx)))
    _mk(os.path.join(ctx.root, AGENTS), ag_ok + "\n\ndispatch_joint = lambda: True\n")
    t.ok("MINOR6 a later rebinding of the name fails", any("dispatch_joint" in x for x in replica_check(ctx)))
    _mk(os.path.join(ctx.root, AGENTS), ag_doc)
    t.ok("MINOR6 control: a docstring-only working edit passes the replica check", not replica_check(ctx),
         str(replica_check(ctx)))
    _mk(os.path.join(ctx.root, AGENTS), ag_ok)
    t.ok("T9 parser: a comment is not an assignment",
         cfv_values("# DISPATCH_JOINT = 1\nDISPATCH_JOINT = 0\nDISPATCH_REASSIGN = 0\n") == {KJ: 0, KR: 0})
    t.ok("T9 parser: the last assignment wins", cfv_values(_cfv(0, 0) + _cfv(1, 1))[KJ] == 1)
    t.ok("T9 parser: True is not the literal 1", not _both(cfv_values(_cfv("True", 1)), 1))
    t.ok("T9 parser: indented assignments are not module level",
         cfv_values("def f():\n    DISPATCH_JOINT = 1\n") == {})
    t.ok("T9 parser: a missing key fails", not _both(cfv_values("DISPATCH_JOINT = 1\n"), 1))


def _st_write_analyze(t, tmp):
    ctx, git, (c0, c1, c2, side), wt2, _other = _synthetic_tree(tmp)
    reg = os.path.join(ctx.outputs, REGISTER_NAME)
    chk = os.path.join(ctx.outputs, CHECK_NAME)
    probe = os.path.join(ctx.outputs, "_dq_probe.py")
    pinned = [probe, "--", "--repo", ctx.root, "--set", "DISPATCH_JOINT=0", "--set", "DISPATCH_REASSIGN=0"]
    unpinned = [probe, "--", "--repo", ctx.root]
    # the synthetic tree has an unpinned smoke line: K3 must FAIL until it is pinned
    os.remove(os.path.join(ctx.outputs, "_dq_q_smoke.jsonl"))

    def refused(fn):
        try:
            fn()
            return False
        except Refused:
            return True

    def rewrite_analyze():
        do_write(ctx, c1, reg, True)
        return do_analyze(ctx, reg, None)

    state, data, _res, _notes = do_write(ctx, c1, reg, False)
    t.ok("T10 first write", state == "write" and os.path.isfile(reg))
    with open(reg, "rb") as fh:
        raw = fh.read()
    t.ok("T10 the register is LF", b"\r" not in raw and raw == data)
    t.ok("T10 identical re-write is unchanged", do_write(ctx, c1, reg, False)[0] == "unchanged")
    ok, lines, wstate, _n = do_analyze(ctx, reg, chk)
    t.ok("T11 analyze PASS on a current register", ok and lines[-1].startswith("VERDICT: PASS") and wstate == "write",
         "\n".join(lines))
    with open(chk, "rb") as fh:
        t.ok("T11 the result file is written, LF", fh.read() == ("\n".join(lines) + "\n").encode("utf-8"))
    t.ok("MINOR9 control: K4 PASS on one listing seen by the spy", _kst(lines, "K4") == "PASS", _kline(lines, "K4"))
    t.ok("T11 analyze --head equal passes", do_analyze(ctx, reg, None, head_arg=c1[:12])[0])
    t.ok("T11 analyze --head different fails", not do_analyze(ctx, reg, None, head_arg=c0)[0])
    _mk(os.path.join(ctx.outputs, "_new_q_a.jsonl"), _pl(["x.py", "--repo", ctx.root]))
    ok, lines = do_analyze(ctx, reg, None)[:2]
    t.ok("T11 a new queue makes the register STALE", not ok and _kst(lines, "K2") == "FAIL", "\n".join(lines))
    t.ok("T10 a different register is frozen", refused(lambda: do_write(ctx, c1, reg, False)))
    t.ok("T10 --replace re-writes it", do_write(ctx, c1, reg, True)[0] == "write")
    t.ok("T11 PASS again after --replace", do_analyze(ctx, reg, None)[0])
    w2 = os.path.join(ctx.outputs, "_dq_q_w2.jsonl")
    _mk(w2, _pl(unpinned))
    ok, lines = rewrite_analyze()[:2]
    t.ok("T11 an unpinned screen line fails K3 (K2 current)", not ok and _kst(lines, "K3") == "FAIL" and
         _kst(lines, "K2") == "PASS", "\n".join(lines))
    # MAJOR-1: a malformed round queue can never leave K3
    _mk(w2, _pl(pinned) * 3)
    ok, lines = rewrite_analyze()[:2]
    t.ok("MAJOR1 control: a pinned round queue passes K3", ok and _kst(lines, "K3") == "PASS", _kline(lines, "K3"))
    _mk(w2, _pl(pinned) * 3 + '{"name": "x"}\n')
    ok, lines = rewrite_analyze()[:2]
    t.ok("MAJOR1 a pinned round queue with one non-pool line FAILS K3 (UNCLASSIFIED)",
         not ok and _kst(lines, "K3") == "FAIL" and "UNCLASSIFIED 1" in _kline(lines, "K3"), _kline(lines, "K3"))
    _mk(w2, _pl(unpinned) * 3 + '{"name": "x"}\n')
    ok, lines = rewrite_analyze()[:2]
    t.ok("MAJOR1 the review's case (3 unpinned lines + 1 name-only line) FAILS K3",
         not ok and _kst(lines, "K3") == "FAIL" and "FAILS-LOUDLY 3" in _kline(lines, "K3"), _kline(lines, "K3"))
    _mk(w2, "not json\n")
    ok, lines = rewrite_analyze()[:2]
    t.ok("MAJOR1 a round queue with no pool line FAILS K3", not ok and _kst(lines, "K3") == "FAIL" and
         "files with no pool line 1 (_dq_q_w2.jsonl)" in _kline(lines, "K3"), _kline(lines, "K3"))
    os.remove(w2)
    # MINOR-7: only the three exact names are POST-FLIP
    ist_s1 = os.path.join(ctx.outputs, "_dq_q_ist_s1.jsonl")
    _mk(ist_s1, _pl(unpinned))
    ok, lines = rewrite_analyze()[:2]
    t.ok("MINOR7 a stray _dq_q_ist_s1.jsonl is no POST-FLIP queue: K3 FAILS", not ok and _kst(lines, "K3") == "FAIL",
         _kline(lines, "K3"))
    os.remove(ist_s1)
    ist = os.path.join(ctx.outputs, "_dq_q_ist.jsonl")
    _mk(ist, _pl(unpinned))
    ok, lines = rewrite_analyze()[:2]
    t.ok("MINOR7 control: _dq_q_ist.jsonl is POST-FLIP (K3 PASS, K6 lists it)",
         ok and _kst(lines, "K3") == "PASS" and "_dq_q_ist.jsonl 1 lines" in _kline(lines, "K6"), "\n".join(lines))
    os.remove(ist)
    # MINOR-9: K4 negative controls
    do_write(ctx, c1, reg, True)
    g = globals()
    real_scan = g["scan"]

    def with_listdir(c):
        r = real_scan(c)
        os.listdir(c.root)
        return r

    def with_scandir(c):
        r = real_scan(c)
        with os.scandir(c.root) as it:
            list(it)
        return r

    def with_walk(c):
        r = real_scan(c)
        for _top, _dirs, _files in os.walk(os.path.join(c.root, "tests")):
            pass
        return r

    for label, fn in (("an extra os.listdir", with_listdir), ("an os.scandir", with_scandir),
                      ("an os.walk", with_walk)):
        g["scan"] = fn
        try:
            ok, lines = do_analyze(ctx, reg, None)[:2]
        finally:
            g["scan"] = real_scan
        t.ok("MINOR9 %s during analyze FAILS K4" % label, not ok and _kst(lines, "K4") == "FAIL", _kline(lines, "K4"))
    kq = os.path.join(ctx.outputs, "_k4_queue.txt")
    _mk(kq, "ff|q|C:/x/%s/wt|east|half|1|360|\n" % ctx.quarantine)
    ok, lines = rewrite_analyze()[:2]
    t.ok("MINOR9 a quarantine-named path met by the scan FAILS K4 (refused before any filesystem call)",
         not ok and _kst(lines, "K4") == "FAIL" and "refused 1" in _kline(lines, "K4"), _kline(lines, "K4"))
    os.remove(kq)
    ok, lines = rewrite_analyze()[:2]
    t.ok("MINOR9 control: K4 PASS again", ok and _kst(lines, "K4") == "PASS", _kline(lines, "K4"))
    # MINOR-8: the result file is frozen like the register
    _mk(chk, "a committed PASS record\n")
    ok, lines, wstate, _n = do_analyze(ctx, reg, chk)
    with open(chk, "rb") as fh:
        kept = fh.read() == b"a committed PASS record\n"
    t.ok("MINOR8 analyze does not overwrite a different result file", ok and kept and
         str(wstate).startswith("REFUSED"), str(wstate))
    ok, lines, wstate, _n = do_analyze(ctx, reg, chk, replace=True)
    with open(chk, "rb") as fh:
        t.ok("MINOR8 --replace re-writes it", wstate == "write" and
             fh.read() == ("\n".join(lines) + "\n").encode("utf-8"), str(wstate))
    t.ok("MINOR8 an identical result is unchanged", do_analyze(ctx, reg, chk)[2] == "unchanged")
    os.remove(chk)
    git.history.add("outputs/" + CHECK_NAME)
    t.ok("MINOR8 a result file git once added is not re-created", str(do_analyze(ctx, reg, chk)[2]).startswith(
        "REFUSED") and not os.path.isfile(chk))
    t.ok("MINOR8 --replace re-creates it", do_analyze(ctx, reg, chk, replace=True)[2] == "write")
    git.history.discard("outputs/" + CHECK_NAME)
    # the register: absent but once added
    os.remove(reg)
    t.ok("T11 a missing register fails", not do_analyze(ctx, reg, None)[0])
    git.history.add("outputs/" + REGISTER_NAME)
    t.ok("T10 a register git once added is not re-created", refused(lambda: do_write(ctx, c1, reg, False)))
    t.ok("T10 --replace re-creates it", do_write(ctx, c1, reg, True)[0] == "write")
    git.history.discard("outputs/" + REGISTER_NAME)
    with open(reg, "rb") as fh:
        cur = fh.read()
    with open(reg, "rb") as fh:
        good = fh.read()
    _mk(reg, good.replace(("write --head " + c1).encode(), ("write --head " + c2).encode()))
    ok, lines = do_analyze(ctx, reg, None)[:2]
    t.ok("T11 a forged head fails K1", not ok and _kst(lines, "K1") == "FAIL")
    _mk(reg, good)
    t.ok("T11 PASS restored", do_analyze(ctx, reg, None)[0])
    # MINOR-10 and the collision rule (another registered worktree's outputs/)
    wt2reg = os.path.join(wt2, "outputs", REGISTER_NAME)
    earlier = cur.replace(b"SUMMARY: ", b"SUMMARY (an earlier version): ")
    t.ok("MINOR10 self-check: the earlier version differs", earlier != cur)
    _mk(wt2reg, earlier)
    try:
        st, _d, _r, notes = do_write(ctx, c1, reg, True)
        t.ok("MINOR10 an earlier register of this tool and flip in another worktree is no collision",
             st in ("write", "unchanged") and any("earlier version" in x for x in notes), str(notes))
    except Refused as exc:
        t.ok("MINOR10 an earlier register of this tool and flip in another worktree is no collision", False, str(exc))
    _mk(wt2reg, cur.replace(c1.encode(), c2.encode()))
    t.ok("MINOR10 a register of another flip head in another worktree is refused",
         refused(lambda: do_write(ctx, c1, reg, True)))
    _mk(wt2reg, "another round's register\n")
    t.ok("T10 a collision in another worktree is refused, even with --replace",
         refused(lambda: do_write(ctx, c1, reg, True)))
    _mk(wt2reg, cur)
    t.ok("T10 the same content in another worktree is no collision", do_write(ctx, c1, reg, False)[0] == "unchanged")
    os.remove(wt2reg)
    ok, lines, wstate, _n = do_analyze(ctx, reg, chk, replace=True)
    with open(chk, "rb") as fh:
        cur_chk = fh.read()
    wt2chk = os.path.join(wt2, "outputs", CHECK_NAME)
    _mk(wt2chk, cur_chk.replace(b"K6 POST", b"K6 POST (earlier)"))
    ok, lines, wstate, notes = do_analyze(ctx, reg, chk)
    t.ok("MINOR10 an earlier result file of this flip in another worktree is no collision",
         wstate == "unchanged" and any("earlier version" in x for x in notes), "%s %s" % (wstate, notes))
    _mk(wt2chk, "another round's check\n")
    t.ok("MINOR10 control: another round's result file in another worktree is refused",
         str(do_analyze(ctx, reg, chk)[2]).startswith("REFUSED"))
    os.remove(wt2chk)
    t.ok("T10 a bad head is refused", refused(lambda: do_write(ctx, c0, reg, True)))
    out2 = os.path.join(tmp, "elsewhere_reg.txt")
    t.ok("T10 --out outside outputs/ skips the git rules", do_write(ctx, c1, out2, False)[0] == "write")
    with open(os.path.join(ctx.root, AGENTS), "rb") as fh:
        ag = fh.read()
    _mk(os.path.join(ctx.root, AGENTS), ag.decode("utf-8").replace("float.is_integer(raw)", "True"))
    t.ok("T13 a drifted replica refuses write", refused(lambda: do_write(ctx, c1, reg, True)))
    t.ok("T13 a drifted replica fails analyze K5", not do_analyze(ctx, reg, None)[0])
    _mk(os.path.join(ctx.root, AGENTS), ag.decode("utf-8").replace('"DISPATCH_JOINT", 0)', '"DISPATCH_JOINT", 1)'))
    t.ok("MINOR6 a drifted dispatch_joint refuses write", refused(lambda: do_write(ctx, c1, reg, True)))
    with open(os.path.join(ctx.root, AGENTS), "wb") as fh:
        fh.write(ag)
    t.ok("T13 the restored replica passes", not replica_check(ctx))


def _st_real(t):
    """Read-only smokes of the real checkout: git plumbing, the replicas, the outputs/ scan (no run, no write)."""
    ctx = Ctx(ROOT)
    t.ok("T13 replicas verbatim in this checkout", not replica_check(ctx), str(replica_check(ctx)))
    own = _own_text()
    t.ok("T13 a mutated replica is caught", bool(replica_check(ctx, own.replace("float.is_integer(raw)", "True"))))
    t.ok("T12 this tool is not counted as running the model", not SIM_RE.search(own))
    g = ctx.git
    head = g.resolve("HEAD")
    t.ok("T14 git resolves HEAD", bool(head) and len(head) == 40)
    vals = cfv_values(g.show(head, CFV)) if head else {}
    t.ok("T14 git show parses both keys at HEAD", all(type(vals.get(k)) is int and vals.get(k) in (0, 1)
                                                       for k in (KJ, KR)), str(vals))
    ag = g.show(head, AGENTS) if head else None
    t.ok("T14 the accessor replicas match agents.py at HEAD (docstrings apart)",
         ag is not None and all(_fn_shape(ag, fn) == _fn_shape(own, fn) is not None for fn in ACCESSORS))
    t.ok("T14 an unknown sha does not resolve", g.resolve("0" * 40) is None and g.resolve("-x") is None)
    t.ok("T14 HEAD is its own ancestor", bool(head) and g.is_ancestor(head, head))
    parent = g.first_parent(head) if head else None
    t.ok("T14 first parent", bool(parent) and len(parent) == 40)
    rp = g.ls_files([":(glob)*.py"])
    t.ok("T14 ls-files of the root *.py", "wildfire_model.py" in rp and all("/" not in p for p in rp))
    with ListingSpy() as spy:
        res = scan(ctx)
    t.ok("T15 real scan: one listing, no quarantine path", ctx.listed == [os.path.normpath(ctx.outputs)] and
         spy.calls == [os.path.normpath(ctx.outputs)] and ctx.refused == 0, str(spy.calls))
    for name in ("_dq_q_w1.jsonl", "_dq_q_w2.jsonl"):
        r = _row(res, name)
        if r is not None:
            t.ok("T15 real %s keeps its meaning" % name, r["counts"][SILENT] + r["counts"][LOUDLY] +
                 r["counts"][UNCL] == 0 and sum(r["counts"][c] for c in LINE_CLASSES) == 128 // (
                     2 if name.endswith("w2.jsonl") else 1), str(dict(r["counts"])))
    t.ok("T15 real scan renders", len(render(ctx, res, None)) > 20)


def _guarded(t, fn, *args) -> None:
    """A test group that raises is a FAILURE, never a crash (e.g. the quarantine guard refusing mid-scan)."""
    try:
        fn(t, *args)
    except Exception as exc:  # noqa: BLE001 - every exception is a test failure
        t.ok("%s raised" % fn.__name__, False, "%s: %s" % (type(exc).__name__, exc))


def selftest() -> int:
    t = _T()
    for fn in (_st_values, _st_meaning, _st_repo, _st_affected, _st_loud, _st_text):
        _guarded(t, fn)
    with tempfile.TemporaryDirectory(prefix="dqflipreg_") as tmp:
        _guarded(t, _st_scan, os.path.join(tmp, "s"))
        _guarded(t, _st_head, os.path.join(tmp, "h"))
        _guarded(t, _st_write_analyze, os.path.join(tmp, "w"))
    _guarded(t, _st_real)
    loaded = [m for m in MODEL_MODULES if m in sys.modules]
    t.ok("T12 no model module imported", not loaded, str(loaded))
    sys.modules["wildfire_model"] = type(sys)("wildfire_model")
    try:
        t.ok("T12 the import detector sees a model module", "wildfire_model" in [m for m in MODEL_MODULES
                                                                                 if m in sys.modules])
    finally:
        del sys.modules["wildfire_model"]
    for f in t.failed:
        print("FAIL " + f)
    print("SELFTEST %s: %d passed, %d failed" % ("PASS" if not t.failed else "FAIL", t.passed, len(t.failed)))
    return 0 if not t.failed else 1


# ------------------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="_dq_flip_register.py", description="the dispatch flip runner register")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    w = sub.add_parser("write")
    w.add_argument("--head", required=True)
    w.add_argument("--out", default=None)
    w.add_argument("--replace", action="store_true")
    a = sub.add_parser("analyze")
    a.add_argument("--head", default=None)
    a.add_argument("--register", default=None)
    a.add_argument("--out", default=None)
    a.add_argument("--replace", action="store_true")
    p = sub.add_parser("preview")
    p.add_argument("--head", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    ctx = Ctx(ROOT)
    try:
        if args.cmd == "write":
            out = os.path.abspath(args.out) if args.out else os.path.join(ctx.outputs, REGISTER_NAME)
            state, data, res, notes = do_write(ctx, args.head, out, args.replace)
            tot = summary(res)
            print("%s %s (sha256 %s, %d lines): A %d queue files, A2 %d pool queues; lines SILENT-CHANGE %d "
                  "(REASSIGN-FLIPS %d), FAILS-LOUDLY %d, FLIP-SAFE %d, OTHER-REPO %d, UNCLASSIFIED %d; POST-FLIP "
                  "files %d; B %d runners; D %d model-running .py" % (
                      "wrote" if state == "write" else "unchanged", out, sha256(data), data.count(b"\n"),
                      len(res["queues"]), len(res["pools"]), tot[SILENT], tot["flips"], tot[LOUDLY], tot[SAFE],
                      tot[OTHER], tot[UNCL], tot["post_files"], len(res["runners"]), len(res["simpy"])))
            for note in notes:
                print("note: " + note)
            return 0
        if args.cmd == "analyze":
            reg = os.path.abspath(args.register) if args.register else os.path.join(ctx.outputs, REGISTER_NAME)
            out = os.path.abspath(args.out) if args.out else os.path.join(ctx.outputs, CHECK_NAME)
            ok, lines, wstate, notes = do_analyze(ctx, reg, out, args.head, args.replace)
            for ln in lines:
                print(ln)
            for note in notes:
                print("note: " + note)
            if wstate and wstate.startswith("REFUSED"):
                print("%s - the result file %s was NOT written" % (wstate, out))
                return 2
            print("result: %s (%s)" % (out, wstate))
            return 0 if ok else 1
        if args.cmd == "preview":
            info = None
            if args.head:
                info, hp = head_check(ctx, args.head)
                if hp:
                    raise Refused("; ".join(hp))
            sys.stdout.write("\n".join(render(ctx, scan(ctx), info)) + "\n")
            return 0
    except Refused as exc:
        print("REFUSED: %s" % exc)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
