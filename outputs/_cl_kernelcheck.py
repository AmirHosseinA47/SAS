"""Carrying-leg round, Part 2: the PRE-WAVE KERNEL CHECK of FF_EXIT_LEG_MODE 2.

Contract: outputs/_cl_tooling_spec.txt section I (all of a-d); design
outputs/carryleg_part1.txt 8.4; review record outputs/_cl_part1_review.txt finding
D1-02. STOP on failure: no wave runs until this prints KERNELCHECK PASS.

(a) BINDING. The driver is the frozen offline replay's drive.replay2(rule="F1F5"),
    which is the implemented mode 2 - NOT fs_counterfactual's F5 branch, which
    completes through a local target reassignment. drive and fs_counterfactual bind
    bfs_first_step BY NAME at import, so rebinding fs_rules.bfs_first_step would test
    nothing (_cl_replay/check_binding.py). The adapter is therefore bound in BOTH
    consumer modules, and `drive.bfs_first_step is adapter` (and the fs_counterfactual
    twin) is asserted before every leg; the originals are restored and re-asserted
    after each pass. F_GUESS is 8.
(b) PER-CALL DIFFERENTIAL, the primary check. On every call the adapter runs the
    replay's ORIGINAL bfs_first_step and the implemented agents.exit_leg_first_step,
    fed the replay's predicates and agents.EXIT_LEG_SEARCH_ORDER, and compares the two
    cells. PASS needs: 1431 calls on list_census.txt and 486 on list_uhD.txt with 0
    mismatches; the call stream identical to a pass-through reference pass; every
    leg's (n, end) - indeed its whole result - equal to the original kernel's; and
    only then the aggregate rows equal to the frozen cf_f1f5.txt / cf_metrics.txt.
(c) CANARY, secondary. The same driver with a mutated kernel - the goal test moved in
    front of the clean (not fire-adjacent, not smoky) filter, the burning filter kept
    in front of it, exactly check_binding.mut_goal_first - must report mismatches and
    turn the census row into the review's 1608 steps / 14 stalled / adj 31. A second
    canary, the implemented kernel itself with its order reversed, must report
    mismatches on BOTH lists: its uhD row is known to stay at 588 (review D1-02), which
    is why the per-call comparison, not the row, is the primary check.
(d) COMPOSITION. A seeded randomized differential over >= 1000 boards: a tiny fake
    model (a real mesa MultiGrid(W, H, False) holding agents.Fire agents set burning /
    smoky) and a real agents.Firefighter placed and exiting with an exit_target.
      - The cell Firefighter._exit_leg_step moves to on a path step equals
        exit_leg_first_step fed predicates computed from the BOARD DESCRIPTION (never
        from the unit's own helpers), and its labels / vars / grid are exactly the
        documented ones.
      - With no clean path, the unit ends exactly where a fresh _move_toward(exit_target)
        on an identical copy ends: vars, labels, grid and route_blocked calls, at
        HOLD 0 and HOLD 1.
      - On 50x50 boards the replay's own bfs_first_step must agree too.
      - The same board through Firefighter.advance() at mode 2: a boundary start
        completes FIRST (no search); any other start lands where the direct
        _exit_leg_step landed, with the victim.
      - No RNG is touched. agents.random, cfv.SYSTEM_RANDOM, agents.SYSTEM_RANDOM and
        the fake model's .random (mesa's Agent.random) are replaced by proxies that LOG
        every attribute access before raising, so a draw inside a broad
        `except Exception` (agents.py has several on this path) is still seen; the log
        must be empty after every call. The global random state and numpy.random's
        state are compared too.
    Boards include burning / smoky / fire-adjacent starts, corners, all-smoky and
    all-fire-adjacent edges, enclosed starts, smoky pockets, order ties (measured: the
    kernel's answer under another order differs), boundary starts, degenerate 1- and
    2-wide grids and 50x50 boards. Coverage floors guard against a vacuous pass, and
    they count only the starts mode 2 can search from (not on the boundary: advance()
    completes a boundary start before any search); the all-start counts are printed
    beside them for reference.

PROVENANCE is enforced, not just printed: HEAD must resolve, and every repo source file
this process imported (agents.py, common_fixed_variables.py, src_extension/..., the
_cl_replay modules) plus the frozen replay files must be tracked and clean vs HEAD, at
the start and again at the end. The full sha256 of agents.py, common_fixed_variables.py
and the kernel source, the full HEAD and the _cl_pool.sh src= digest are recorded, so a
wave's LAUNCH lines can be tied to the source this check passed.

Prints "KERNELCHECK PASS" and writes the record (default outputs/_cl_kernelcheck.txt,
--out to redirect) only if every check passes. The previous record is removed first;
any failure prints the reason, writes a record ending in the KERNELCHECK FAIL line, and
exits 1 - a stale PASS never survives a failed rerun. Deterministic: reruns print the
same bytes.

Read-only on the repo and on outputs/: it opens only the explicit _ffr_*.json names in
the two list files (fs_counterfactual.load asserts the quarantine name is absent) and
the named _cl_replay files; it never lists a directory. It runs no simulation - the
fake boards step nothing but one carrying move.

  .venv/Scripts/python.exe -B outputs/_cl_kernelcheck.py [--out <txt>]
"""
import argparse
import ast
import contextlib
import copy
import hashlib
import inspect
import io
import os
import random
import re
import subprocess
import sys
import traceback
from collections import Counter, deque
from types import SimpleNamespace

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REPLAY = os.path.join(HERE, "_cl_replay")
OUT_TXT = os.path.join(HERE, "_cl_kernelcheck.txt")
QUAR = "_firemech_rewound_20260914"
F_GUESS = 8
LISTS = ("list_census.txt", "list_uhD.txt")

# ---- stated constants (spec I; the pre-registered numbers of design 8.4) ----------
# calls / bfs / fb are drive.run's F5i instrumentation counts in cf_f1f5.txt (F1F5 was
# never instrumented). They are a valid target for this F1F5 driver because the frozen
# F5 and F1F5 rows are identical on both lists - expected_rows() asserts that premise
# instead of assuming it.
PREREG = {
    "list_census.txt": {
        "calls": 1431, "bfs": 1418, "fb": 13,
        "row": {"legs": 212, "steps": 1643, "stalled": 20, "dead": 0, "timeout": 0,
                "shorter": 59, "longer": 0, "adj": 12, "smoke": 3},
        "metrics": {"stall_vs_completion_cell": 2},
    },
    "list_uhD.txt": {
        "calls": 486, "bfs": 486, "fb": 0,
        "row": {"steps": 588},
        "metrics": {},
    },
}
CANARY_GOAL_FIRST_CENSUS = {"steps": 1608, "stalled": 14, "adj": 31}
# Recorded in outputs/_cl_part1_review.txt D1-02 (printed for reference, not gated):
REVIEW_GOAL_FIRST_INFO = "census smoke 6, uhD steps 584"
REVIEW_REVERSED_INFO = "census 1641 steps / 24 stalled / adj 0 / smoke 0; uhD row unchanged at 588"
PINNED_ORDER = ((1, 0), (-1, 0), (0, 1), (0, -1))  # design 2.3.1: +x, -x, +y, -y

# the frozen replay files this check runs or reads (verified against SHA256SUMS.txt)
FROZEN = ("drive.py", "fs_env.py", "fs_rules.py", "fs_counterfactual.py", "check_binding.py",
          "list_census.txt", "list_uhD.txt", "cf_f1f5.txt", "cf_metrics.txt")

ROWKEYS = ("legs", "steps", "stalled", "dead", "timeout", "shorter", "longer", "adj", "smoke")
METRICKEYS = ("stall_vs_exit", "stall_vs_completion_cell", "reversals",
              "legs_with_2plus_reversals", "end_not_exit")
# cf_f1f5.txt meta keys (drive.run's F5i instrumentation) -> this driver's F1F5 counters
METAMAP = (("files_used", "files_used"), ("legs", "legs"), ("base==rec", "base==rec"),
           ("F5_bfs_steps", "bfs"), ("F5_fallback_steps", "fb"),
           ("F5_legs_with_fallback", "legs_with_fallback"),
           ("F5_end_not_orig_exit", "end_not_orig_exit"), ("skipped", "skipped"))

# ---- (d) composition constants ------------------------------------------------------
D_SEED = 20260926
FOUR = ((1, 0), (-1, 0), (0, 1), (0, -1))  # the board's own neighbour set (order-free use)
CATS = ("rand", "rand_interior", "start_burning", "start_smoky", "start_adjacent", "corner",
        "smoky_edges", "adj_edges", "ties", "enclosed", "pocket", "big50", "big50_edge",
        "boundary", "narrow", "route_blocked")
BOARDS_PER_CAT = 150
# Every floor counts only SEARCHED starts (not on the boundary - the only starts mode 2
# ever searches from), except the two keys in FLOOR_ON_ALL_STARTS.
FLOOR_ON_ALL_STARTS = ("boards", "boundary_start_completed")
MIN_COVERAGE = {
    "boards": 1000,
    "path": 400,
    "fallback": 400,
    "start_burning": 100,
    "start_smoky_with_path": 40,
    "start_adjacent_with_path": 40,
    "corner_or_diag_start": 100,
    "all_smoky_edges": 100,
    "all_adjacent_edges": 100,
    "order_sensitive": 100,
    "fallback_enclosed_hold0": 20,
    "fallback_enclosed_hold1": 20,
    "fallback_tier1to3": 20,
    "fallback_tier4": 20,
    "relabel_on_path": 20,
    "boundary_start_completed": 100,
    "advance_moved_with_victim": 400,
    "board50_replay_kernel_checked": 200,
}

LINES = []
# The record path of the running main(); None outside main(), so a function called
# directly (a probe, a mutation test) never writes a record.
_RUN = {"out": None}


def say(s=""):
    LINES.append(s)
    print(s, flush=True)


def write_record(path):
    """LINES to `path`, atomically (tmp + os.replace), UTF-8 + LF."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(LINES) + "\n")
    os.replace(tmp, path)


def fail(msg):
    say("KERNELCHECK FAIL: " + msg)
    out = _RUN["out"]
    if out is not None:
        try:
            write_record(out)
            print("wrote the FAIL record to %s" % out, flush=True)
        except OSError as exc:
            print("could not write the FAIL record to %s (%s); no record exists" % (out, exc), flush=True)
    raise SystemExit(1)


# ======================================================================================
# provenance
# ======================================================================================
def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def check_frozen():
    sums = {}
    with open(os.path.join(REPLAY, "SHA256SUMS.txt"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            h, n = line.split(None, 1)
            sums[n.lstrip("*")] = h
    out = []
    for n in FROZEN:
        if n not in sums:
            fail("_cl_replay/SHA256SUMS.txt has no entry for %s" % n)
        with open(os.path.join(REPLAY, n), "rb") as f:
            b = f.read()
        if sha256_bytes(b) == sums[n]:
            how = "raw"
        else:
            lf = b.replace(b"\r\n", b"\n")
            if sha256_bytes(lf) == sums[n]:
                how = "LF-normalised"
            elif sha256_bytes(lf.replace(b"\n", b"\r\n")) == sums[n]:
                how = "CRLF-normalised"
            else:
                fail("_cl_replay/%s does not match SHA256SUMS.txt (raw or EOL-normalised)" % n)
        out.append("%s=%s" % (n, how))
    return out


def git(*args):
    """(returncode, stdout, stderr); returncode None if git could not be run at all."""
    try:
        p = subprocess.run(["git", "-C", REPO] + list(args), capture_output=True, text=True,
                           timeout=60)
    except Exception as exc:  # noqa: BLE001
        return None, "", "unavailable (%s)" % type(exc).__name__
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def file_sha256(rel):
    path = os.path.join(REPO, rel)
    if not os.path.isfile(path):
        fail("provenance: %s does not exist" % rel)
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


# The simulation source _cl_pool.sh stamps on every LAUNCH / DONE line as src=: sha256sum
# (Git Bash, binary-mode "<hex> *<name>" lines) of these four files, piped through
# sha256sum, first 12 hex.
POOL_SRC_FILES = ("agents.py", "wildfire_model.py", "common_fixed_variables.py",
                  "src_extension/planning/rescue_planner.py")


def pool_src_digest():
    text = "".join("%s *%s\n" % (file_sha256(n), n) for n in POOL_SRC_FILES)
    return sha256_bytes(text.encode("utf-8"))[:12]


def repo_source_files():
    """Every repo source file this process has imported (sys.modules, not .venv, not
    this script), plus the frozen replay files and their SHA256SUMS.txt; repo-relative,
    forward slashes, sorted."""
    root = os.path.normcase(os.path.abspath(REPO))
    venv = os.path.join(root, ".venv")
    me = os.path.normcase(os.path.abspath(__file__))
    out = set()
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        a = os.path.normcase(os.path.abspath(f))
        if a == me or not a.startswith(root + os.sep) or a.startswith(venv + os.sep):
            continue
        if QUAR in a:
            fail("provenance: a module was imported from the quarantine: %s" % f)
        out.add(os.path.relpath(os.path.abspath(f), REPO).replace(os.sep, "/"))
    for n in FROZEN + ("SHA256SUMS.txt",):
        out.add("outputs/_cl_replay/" + n)
    return sorted(out)


def provenance():
    """Fails loudly (spec A5) unless HEAD resolves and every repo source file this check
    ran is tracked and identical to HEAD. Returns the recorded identities."""
    rc, head, err = git("rev-parse", "HEAD")
    if rc != 0 or not re.match(r"^[0-9a-f]{40}$", head):
        fail("provenance: `git rev-parse HEAD` failed (rc %s: %s) - the checked source cannot be "
             "tied to a commit" % (rc, (err or head).splitlines()[0] if (err or head) else ""))
    files = repo_source_files()
    # Tracked, by EXACT path: a pathspec that matched nothing would make the diff below
    # vacuously clean, so every file must come back from ls-files spelled as given.
    rc, listed, err = git("ls-files", "--error-unmatch", "--", *files)
    missing = [f for f in files if f not in set(listed.splitlines())]
    if rc != 0 or missing:
        fail("provenance: repo source this check ran is not tracked (exact path): %s (git ls-files rc %s%s)"
             % (", ".join(missing) or "?", rc, ": " + err.splitlines()[0] if err else ""))
    rc, _out, err = git("diff", "--quiet", "HEAD", "--", *files)
    if rc != 0:
        rc_names, names, _err = git("diff", "--name-only", "HEAD", "--", *files)
        fail("provenance: repo source differs from HEAD %s (git diff --quiet rc %s%s); DIRTY: %s" % (
            head[:12], rc, ": " + err.splitlines()[0] if err else "",
            ", ".join(names.split()) if rc_names == 0 and names else "(git diff --name-only listed none)"))
    return {
        "head": head,
        "files": files,
        "agents.py": file_sha256("agents.py"),
        "common_fixed_variables.py": file_sha256("common_fixed_variables.py"),
        "kernel": sha256_bytes(inspect.getsource(agents.exit_leg_first_step).encode("utf-8")),
        "pool_src": pool_src_digest(),
    }


def parse_cf_f1f5():
    rows = {}
    cur = None
    with open(os.path.join(REPLAY, "cf_f1f5.txt"), encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            m = re.match(r"^== (\S+) F_GUESS (\d+) (\{.*\})$", line)
            if m:
                cur = m.group(1)
                rows[cur] = {"fg": int(m.group(2)), "meta": ast.literal_eval(m.group(3)), "rules": {}}
                continue
            m = re.match(r"^  (\S+)\s+legs\s+(\d+) steps\s+(\d+) stalled\s+(\d+) dead (\d+) tmo (\d+) "
                         r"shorter\s+(\d+) longer (\d+) adj\s+(\d+) smoke\s+(\d+)$", line)
            if m and cur is not None:
                rows[cur]["rules"][m.group(1)] = dict(zip(ROWKEYS, (int(v) for v in m.groups()[1:])))
                continue
            if line.strip():
                fail("cf_f1f5.txt: unparsed line %r" % line)
    return rows


def parse_cf_metrics():
    rows = {}
    cur = None
    with open(os.path.join(REPLAY, "cf_metrics.txt"), encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            m = re.match(r"^== (\S+)$", line)
            if m:
                cur = m.group(1)
                rows[cur] = {}
                continue
            m = re.match(r"^  (\S+)\s+(\{.*\})$", line)
            if m and cur is not None:
                rows[cur][m.group(1)] = ast.literal_eval(m.group(2))
                continue
            if line.strip():
                fail("cf_metrics.txt: unparsed line %r" % line)
    return rows


def expected_rows():
    """The frozen F1F5 rows, asserted against the spec's stated constants first."""
    cf = parse_cf_f1f5()
    cm = parse_cf_metrics()
    exp = {}
    for lf in LISTS:
        if lf not in cf or "F1F5" not in cf[lf]["rules"]:
            fail("cf_f1f5.txt has no F1F5 row for %s" % lf)
        if cf[lf]["fg"] != F_GUESS:
            fail("cf_f1f5.txt row for %s is F_GUESS %d, not %d" % (lf, cf[lf]["fg"], F_GUESS))
        if lf not in cm or "F1F5" not in cm[lf]:
            fail("cf_metrics.txt has no F1F5 row for %s" % lf)
        row = cf[lf]["rules"]["F1F5"]
        meta = cf[lf]["meta"]
        met = cm[lf]["F1F5"]
        pre = PREREG[lf]
        # the premise that lets F5i's call counts stand for F1F5's (see PREREG)
        if cf[lf]["rules"].get("F5") != row:
            fail("cf_f1f5.txt %s: the F5 row %s != the F1F5 row %s, so the F5i call counts are not "
                 "F1F5's" % (lf, cf[lf]["rules"].get("F5"), row))
        if meta.get("F5==F5i") != row["legs"]:
            fail("cf_f1f5.txt %s: F5==F5i %s != legs %d" % (lf, meta.get("F5==F5i"), row["legs"]))
        for k, v in pre["row"].items():
            if row[k] != v:
                fail("cf_f1f5.txt %s F1F5 %s=%d, the spec states %d" % (lf, k, row[k], v))
        if meta.get("F5_bfs_steps") != pre["bfs"] or meta.get("F5_fallback_steps") != pre["fb"]:
            fail("cf_f1f5.txt %s bfs/fallback %s/%s, the spec states %d/%d" % (
                lf, meta.get("F5_bfs_steps"), meta.get("F5_fallback_steps"), pre["bfs"], pre["fb"]))
        if pre["bfs"] + pre["fb"] != pre["calls"]:
            fail("spec constants inconsistent for %s" % lf)
        for k, v in pre["metrics"].items():
            if met.get(k) != v:
                fail("cf_metrics.txt %s F1F5 %s=%s, the spec states %d" % (lf, k, met.get(k), v))
        if set(met) - set(METRICKEYS):
            fail("cf_metrics.txt %s F1F5 has keys outside %s: %s" % (lf, METRICKEYS, sorted(met)))
        exp[lf] = {"row": row, "meta": meta, "metrics": {k: met.get(k, 0) for k in METRICKEYS},
                   "calls": pre["calls"]}
    return exp


# ======================================================================================
# imports: the frozen replay (from _cl_replay) and the implemented kernel (repo root)
# ======================================================================================
# An F_GUESS in the environment that is not this check's is refused in main(), after the
# previous record is removed (the replay modules read F_GUESS only in their own mains;
# this check passes f_guess explicitly).
sys.path.insert(0, REPO)
sys.path.insert(0, REPLAY)
os.environ.setdefault("MPLBACKEND", "Agg")

import fs_env  # noqa: E402
import fs_rules  # noqa: E402
import fs_counterfactual as fc  # noqa: E402
import drive  # noqa: E402
from fs_env import Env  # noqa: E402
import agents  # noqa: E402
from mesa.space import MultiGrid  # noqa: E402
import mesa  # noqa: E402
import numpy  # noqa: E402

ORIG = fs_rules.bfs_first_step
CONSUMERS = (drive, fc)


def _same_dir(path, d):
    return os.path.normcase(os.path.dirname(os.path.abspath(path))) == os.path.normcase(os.path.abspath(d))


def check_modules():
    for m in (fs_env, fs_rules, fc, drive):
        if not _same_dir(m.__file__, REPLAY):
            fail("%s imported from %s, not _cl_replay" % (m.__name__, m.__file__))
    if not _same_dir(agents.__file__, REPO):
        fail("agents imported from %s, not the checkout %s" % (agents.__file__, REPO))
    for m in CONSUMERS:
        if m.bfs_first_step is not ORIG:
            fail("%s.bfs_first_step is not fs_rules' original at start" % m.__name__)
    if tuple(agents.EXIT_LEG_SEARCH_ORDER) != PINNED_ORDER:
        fail("agents.EXIT_LEG_SEARCH_ORDER %r != the design's (+x,-x,+y,-y)" % (agents.EXIT_LEG_SEARCH_ORDER,))
    if tuple(fs_env.ORDER) != PINNED_ORDER:
        fail("fs_env.ORDER %r != (+x,-x,+y,-y)" % (fs_env.ORDER,))
    if fs_env.N != 50:
        fail("fs_env.N is %r, not 50" % fs_env.N)


@contextlib.contextmanager
def bound(adapter):
    """Bind `adapter` IN THE CONSUMER MODULES; assert it; restore and re-assert."""
    for m in CONSUMERS:
        if m.bfs_first_step is not ORIG:
            fail("%s.bfs_first_step not at the original before binding" % m.__name__)
    try:
        for m in CONSUMERS:
            m.bfs_first_step = adapter
        for m in CONSUMERS:
            if m.bfs_first_step is not adapter:
                fail("%s.bfs_first_step is not the adapter after binding" % m.__name__)
        if fs_rules.bfs_first_step is not ORIG:
            fail("fs_rules.bfs_first_step was rebound; the check binds the consumers only")
        yield
    finally:
        for m in CONSUMERS:
            m.bfs_first_step = ORIG
    for m in CONSUMERS:
        if m.bfs_first_step is not ORIG:
            fail("%s.bfs_first_step not restored" % m.__name__)


# ---- the kernels the adapter can run ---------------------------------------------
def _replay_passable(env, k):
    return lambda n: not env.burning(n, k) and not env.adj(n, k) and not env.smoky(n, k)


def _replay_oob(c):
    return not fs_env.inb(c)


def call_implemented(env, pos, k):
    """Spec I(b), verbatim: the implemented kernel fed the replay's predicates."""
    return agents.exit_leg_first_step(
        pos,
        passable=_replay_passable(env, k),
        is_boundary=fs_rules.on_boundary,
        out_of_bounds=_replay_oob,
        order=agents.EXIT_LEG_SEARCH_ORDER,
    )


def canary_goal_first(start, passable, is_boundary, out_of_bounds, order, burning):
    """MUTANT of agents.exit_leg_first_step: the goal test runs BEFORE the clean filter
    (a fire-adjacent or smoky boundary cell becomes a goal); the burning filter stays in
    front of it. Identical in behaviour to _cl_replay/check_binding.py mut_goal_first."""
    prev = {start: None}
    queue = deque([start])
    while queue:
        cx, cy = queue.popleft()
        for ox, oy in order:
            cell = (cx + ox, cy + oy)
            if cell in prev or out_of_bounds(cell) or burning(cell):
                continue
            if is_boundary(cell):
                prev[cell] = (cx, cy)
                while prev[cell] != start:
                    cell = prev[cell]
                return cell
            if not passable(cell):
                continue
            prev[cell] = (cx, cy)
            queue.append(cell)
    return None


def call_canary_goal_first(env, pos, k):
    return canary_goal_first(
        pos,
        passable=_replay_passable(env, k),
        is_boundary=fs_rules.on_boundary,
        out_of_bounds=_replay_oob,
        order=agents.EXIT_LEG_SEARCH_ORDER,
        burning=lambda n: env.burning(n, k),
    )


def call_canary_reversed(env, pos, k):
    return agents.exit_leg_first_step(
        pos,
        passable=_replay_passable(env, k),
        is_boundary=fs_rules.on_boundary,
        out_of_bounds=_replay_oob,
        order=tuple(reversed(agents.EXIT_LEG_SEARCH_ORDER)),
    )


# ======================================================================================
# (a)-(c): one replay pass over one list with one adapter
# ======================================================================================
def run_pass(listfile, kernel_call):
    """kernel_call None = pass-through reference (the original kernel only)."""
    st = {"calls": 0, "mism": 0, "first": None, "stream": []}
    ctx = {}

    def adapter(env, pos, k, strict=True):
        if strict is not True:
            fail("the replay called bfs_first_step with strict=%r" % (strict,))
        want = ORIG(env, pos, k, strict)
        got = want if kernel_call is None else kernel_call(env, pos, k)
        st["calls"] += 1
        st["stream"].append((ctx["file"], ctx["victim"], ctx["s0"], tuple(pos), k))
        if got != want or type(got) is not type(want):
            st["mism"] += 1
            if st["first"] is None:
                st["first"] = "file=%s victim=%s s0=%s pos=%s k=%d original=%s implemented=%s" % (
                    ctx["file"], ctx["victim"], ctx["s0"], tuple(pos), k, want, got)
        return got

    with open(os.path.join(REPLAY, listfile), encoding="utf-8") as f:
        files = [ln.strip() for ln in f if ln.strip()]
    row = Counter({k: 0 for k in ROWKEYS})
    meta = Counter()
    met = Counter({k: 0 for k in METRICKEYS})
    per_leg = []
    skipped = []
    with bound(adapter):
        for name in files:
            if QUAR in name or "/" in name or "\\" in name:
                fail("%s names a path outside outputs/ or the quarantine: %r" % (listfile, name))
            d = drive.load(name)
            if d is None or "burn_intervals" not in d:
                skipped.append(name)
                meta["skipped"] += 1
                continue
            meta["files_used"] += 1
            env = Env(d, f_guess=F_GUESS)
            for leg in drive.legs(d):
                ctx.update(file=name, victim=leg["victim"], s0=leg["s0"])
                rec = leg["s1"] - leg["s0"]
                c0 = st["calls"]
                b = drive.orig_replay(env, leg, "base")["n"]
                if st["calls"] != c0:
                    fail("the base replay called the kernel (%s %s)" % (name, leg["victim"]))
                for m in CONSUMERS:
                    if m.bfs_first_step is not adapter:
                        fail("%s.bfs_first_step is not the adapter before a leg" % m.__name__)
                r = drive.replay2(env, leg, "F1F5")
                ncalls = st["calls"] - c0
                meta["legs"] += 1
                meta["base==rec"] += b == rec
                n = r.get("n")
                row["legs"] += 1
                if n is None:
                    row["dead" if "dead" in r else "timeout"] += 1
                    met["none"] += 1
                    per_leg.append((name, leg["victim"], leg["s0"], None, None, dict(sorted(r.items()))))
                    continue
                if ncalls != r["fb"] + r["bfs"]:
                    fail("adapter counted %d calls on %s %s s0=%d but replay2 reports fb %d + bfs %d"
                         % (ncalls, name, leg["victim"], leg["s0"], r["fb"], r["bfs"]))
                meta["bfs"] += r["bfs"]
                meta["fb"] += r["fb"]
                meta["legs_with_fallback"] += r["fb"] > 0
                meta["end_not_orig_exit"] += r["end"] != leg["exit"]
                row["steps"] += n
                row["stalled"] += n > leg["dist"] + 5
                row["adj"] += r["adj"]
                row["smoke"] += r["smoke"]
                if b is not None:
                    row["shorter"] += n < b
                    row["longer"] += n > b
                dend = fs_rules.md(leg["p0"], r["end"])
                met["stall_vs_exit"] += n > leg["dist"] + 5
                met["stall_vs_completion_cell"] += n > dend + 5
                met["reversals"] += r["rev"]
                met["legs_with_2plus_reversals"] += r["rev"] >= 2
                met["end_not_exit"] += r["end"] != leg["exit"]
                per_leg.append((name, leg["victim"], leg["s0"], n, tuple(r["end"]), dict(sorted(r.items()))))
    return {"calls": st["calls"], "mism": st["mism"], "first": st["first"], "stream": st["stream"],
            "row": dict(row), "meta": dict(meta), "metrics": dict(met), "per_leg": per_leg,
            "skipped": skipped}


def fmt_row(r):
    return ("legs %d steps %d stalled %d dead %d tmo %d shorter %d longer %d adj %d smoke %d"
            % tuple(r.get(k, 0) for k in ROWKEYS))


def fmt_met(m):
    return " ".join("%s %d" % (k, m.get(k, 0)) for k in METRICKEYS)


def compare_to_frozen(tag, lf, res, exp):
    """The aggregate rows vs cf_f1f5.txt / cf_metrics.txt; returns a list of diffs."""
    diffs = []
    for k in ROWKEYS:
        if res["row"].get(k, 0) != exp["row"][k]:
            diffs.append("row %s %d != frozen %d" % (k, res["row"].get(k, 0), exp["row"][k]))
    for k in METRICKEYS:
        if res["metrics"].get(k, 0) != exp["metrics"][k]:
            diffs.append("metric %s %d != frozen %d" % (k, res["metrics"].get(k, 0), exp["metrics"][k]))
    if res["metrics"].get("none", 0):
        diffs.append("metric none %d != 0" % res["metrics"]["none"])
    for ck, mk in METAMAP:
        if res["meta"].get(mk, 0) != exp["meta"].get(ck, 0):
            diffs.append("meta %s %d != frozen %s %d" % (mk, res["meta"].get(mk, 0), ck, exp["meta"].get(ck, 0)))
    frozen_skips = sorted(k.split(":", 1)[1] for k in exp["meta"] if k.startswith("skipped:"))
    if sorted(res["skipped"]) != frozen_skips:
        diffs.append("skipped files %s != frozen %s" % (sorted(res["skipped"]), frozen_skips))
    if res["calls"] != exp["calls"]:
        diffs.append("kernel calls %d != pre-registered %d" % (res["calls"], exp["calls"]))
    return diffs


def replay_checks():
    say("== (a)-(c) THE REPLAY DIFFERENTIAL (drive.replay2 rule F1F5, F_GUESS %d)" % F_GUESS)
    exp = expected_rows()
    for lf in LISTS:
        e = exp[lf]
        say("  frozen %-16s F1F5 %s | %s | calls %d (F5i bfs %d + fallback %d; F5 row == F1F5 row)" % (
            lf, fmt_row(e["row"]), fmt_met(e["metrics"]), e["calls"],
            e["meta"]["F5_bfs_steps"], e["meta"]["F5_fallback_steps"]))
    results = {}
    passes = (("REFERENCE", None), ("CANARY-GOALFIRST", call_canary_goal_first),
              ("CANARY-REVERSED", call_canary_reversed), ("IMPLEMENTED", call_implemented))
    for label, kern in passes:
        for lf in LISTS:
            results[(label, lf)] = run_pass(lf, kern)

    # ---- reference: the original kernel, pass-through; the replay must still be itself
    say("")
    say("  REFERENCE (adapter bound in drive + fs_counterfactual, original kernel only)")
    for lf in LISTS:
        res = results[("REFERENCE", lf)]
        say("    %-16s calls %d | %s | %s" % (lf, res["calls"], fmt_row(res["row"]), fmt_met(res["metrics"])))
        diffs = compare_to_frozen("REFERENCE", lf, res, exp[lf])
        if diffs:
            fail("the frozen replay no longer reproduces its own outputs on %s (not a kernel finding): %s"
                 % (lf, "; ".join(diffs)))
        if res["calls"] == 0:
            fail("REFERENCE: 0 adapter calls on %s - the binding is vacuous" % lf)
    say("    reference == cf_f1f5.txt / cf_metrics.txt on both lists; calls == pre-registered")

    # ---- canary 1: goal test before the clean filter
    say("")
    say("  CANARY-GOALFIRST (goal test before the clean filter; burning filter kept first)")
    ref_legs = {lf: [(x[0], x[1], x[2], x[3], x[4]) for x in results[("REFERENCE", lf)]["per_leg"]] for lf in LISTS}
    for lf in LISTS:
        res = results[("CANARY-GOALFIRST", lf)]
        nd = sum(1 for a, b in zip(ref_legs[lf], [(x[0], x[1], x[2], x[3], x[4]) for x in res["per_leg"]]) if a != b)
        say("    %-16s calls %d mismatches %d legs with different (n,end) %d | %s" % (
            lf, res["calls"], res["mism"], nd, fmt_row(res["row"])))
    cres = results[("CANARY-GOALFIRST", "list_census.txt")]
    if cres["mism"] == 0:
        fail("CANARY-GOALFIRST produced 0 mismatches on the census: the adapter is not wired in")
    got = {k: cres["row"].get(k, 0) for k in CANARY_GOAL_FIRST_CENSUS}
    if got != CANARY_GOAL_FIRST_CENSUS:
        fail("CANARY-GOALFIRST census row %s != expected %s" % (got, CANARY_GOAL_FIRST_CENSUS))
    if cres["row"] == results[("REFERENCE", "list_census.txt")]["row"]:
        fail("CANARY-GOALFIRST left the census row unchanged")
    say("    census: mismatches > 0 and row steps %d / stalled %d / adj %d == expected (PASS)"
        % (got["steps"], got["stalled"], got["adj"]))
    say("    for reference, review record D1-02 also measured: %s" % REVIEW_GOAL_FIRST_INFO)

    # ---- canary 2: the implemented kernel with its order reversed
    say("")
    say("  CANARY-REVERSED (the implemented kernel, order reversed)")
    for lf in LISTS:
        res = results[("CANARY-REVERSED", lf)]
        nd = sum(1 for a, b in zip(ref_legs[lf], [(x[0], x[1], x[2], x[3], x[4]) for x in res["per_leg"]]) if a != b)
        same = res["row"] == results[("REFERENCE", lf)]["row"]
        say("    %-16s calls %d mismatches %d legs with different (n,end) %d | %s | row %s" % (
            lf, res["calls"], res["mism"], nd, fmt_row(res["row"]), "UNCHANGED" if same else "changed"))
        if res["mism"] == 0:
            fail("CANARY-REVERSED produced 0 mismatches on %s: the per-call comparison is blind to order" % lf)
    say("    mismatches > 0 on both lists (PASS); review record D1-02: %s" % REVIEW_REVERSED_INFO)

    # ---- the real run
    say("")
    say("  IMPLEMENTED (agents.exit_leg_first_step vs the original, every call)")
    for lf in LISTS:
        res = results[("IMPLEMENTED", lf)]
        ref = results[("REFERENCE", lf)]
        say("    %-16s calls %d mismatches %d" % (lf, res["calls"], res["mism"]))
        if res["mism"]:
            fail("SOURCE FINDING - the implemented kernel disagrees with the replay's on %s: %d mismatches; "
                 "FIRST MISMATCH %s" % (lf, res["mism"], res["first"]))
        if res["calls"] != exp[lf]["calls"]:
            fail("IMPLEMENTED: %d kernel calls on %s, pre-registered %d" % (res["calls"], lf, exp[lf]["calls"]))
        if res["stream"] != ref["stream"]:
            fail("IMPLEMENTED: the call stream on %s differs from the reference pass" % lf)
        nel = [(a[:5], b[:5]) for a, b in zip(ref["per_leg"], res["per_leg"]) if a[:5] != b[:5]]
        full = [(a, b) for a, b in zip(ref["per_leg"], res["per_leg"]) if a != b]
        if len(ref["per_leg"]) != len(res["per_leg"]) or nel:
            fail("IMPLEMENTED: per-leg (n, end) differs from the original on %s: %d legs, first %s"
                 % (lf, len(nel), nel[:1]))
        if full:
            fail("IMPLEMENTED: a per-leg result differs from the original on %s: first %s" % (lf, full[:1]))
        say("      call stream == reference (%d calls); per-leg (n, end) and full result == original on %d/%d legs"
            % (len(res["stream"]), len(res["per_leg"]), len(ref["per_leg"])))
    for lf in LISTS:
        res = results[("IMPLEMENTED", lf)]
        diffs = compare_to_frozen("IMPLEMENTED", lf, res, exp[lf])
        say("    %-16s %s | %s | bfs %d fallback %d" % (lf, fmt_row(res["row"]), fmt_met(res["metrics"]),
                                                        res["meta"].get("bfs", 0), res["meta"].get("fb", 0)))
        if diffs:
            fail("IMPLEMENTED aggregate on %s differs from the frozen rows: %s" % (lf, "; ".join(diffs)))
    say("    aggregate == cf_f1f5.txt / cf_metrics.txt on both lists (census 1643 / 20 / 2 reached / "
        "12 / 3 / 59 shorter / 0 longer / 0 dead; uhD 588)")
    return results


# ======================================================================================
# (d) composition on fake boards
# ======================================================================================
class FakeModel:
    """What a carrying step reads: a real mesa MultiGrid, a schedule list, a step
    counter, and a route_blocked handler that only records the call."""

    def __init__(self, W, H):
        self.grid = MultiGrid(W, H, False)
        self.schedule = SimpleNamespace(agents=[])
        self.evaluation_timesteps_counter = 0
        self.route_blocked_calls = []

    def _on_firefighter_route_blocked(self, ff):
        self.route_blocked_calls.append(str(ff.unit_id))


# Every RNG access through a proxy, appended BEFORE the proxy raises: a draw inside a
# broad `except Exception` (agents.py has several on the carrying path) is still seen.
RNG_LOG = []


class _NoRNG:
    """A raising stand-in for an RNG that logs every attribute access first. Dunder
    lookups (protocol probes such as copy's __deepcopy__) are not draws and fall
    through as a plain AttributeError, unlogged."""

    def __init__(self, label):
        self._label = label

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        RNG_LOG.append("%s.%s" % (self._label, name))
        raise AssertionError("RNG draw during a carrying step: %s.%s" % (self._label, name))


def _np_state_equal(a, b):
    return (a[0] == b[0] and numpy.array_equal(a[1], b[1]) and tuple(a[2:]) == tuple(b[2:]))


@contextlib.contextmanager
def no_rng(model):
    """No RNG may be touched inside: agents.random, cfv.SYSTEM_RANDOM,
    agents.SYSTEM_RANDOM (the star-imported name) and model.random (what mesa's
    Agent.random returns) are logging proxies; the access log must stay empty, and the
    global random and numpy.random states must not change."""
    cfv = agents.cfv
    del RNG_LOG[:]
    saved_random = agents.random
    saved_sys_cfv = cfv.SYSTEM_RANDOM
    has_sys_agents = "SYSTEM_RANDOM" in vars(agents)
    saved_sys_agents = vars(agents).get("SYSTEM_RANDOM")
    model_had = "random" in vars(model)
    saved_model = vars(model).get("random")
    state = random.getstate()
    np_state = numpy.random.get_state()
    agents.random = _NoRNG("agents.random")
    cfv.SYSTEM_RANDOM = _NoRNG("cfv.SYSTEM_RANDOM")
    if has_sys_agents:
        agents.SYSTEM_RANDOM = _NoRNG("agents.SYSTEM_RANDOM")
    model.random = _NoRNG("model.random")
    try:
        yield
    finally:
        agents.random = saved_random
        cfv.SYSTEM_RANDOM = saved_sys_cfv
        if has_sys_agents:
            agents.SYSTEM_RANDOM = saved_sys_agents
        if model_had:
            model.random = saved_model
        else:
            del model.random
    if RNG_LOG:
        raise AssertionError("RNG accessed during a carrying step (an except may have swallowed it): %s"
                             % ", ".join(RNG_LOG[:5]))
    if random.getstate() != state:
        raise AssertionError("the global random state changed during a carrying step")
    if not _np_state_equal(numpy.random.get_state(), np_state):
        raise AssertionError("the numpy.random state changed during a carrying step")


def board_preds(b):
    W, H = b["W"], b["H"]
    burn = {c for c, (bu, _s) in b["fire"].items() if bu}
    smk = {c for c, (_bu, s) in b["fire"].items() if s}

    def inb(c):
        return 0 <= c[0] < W and 0 <= c[1] < H

    def burning(c):
        return c in burn

    def adj(c):
        return any((c[0] + ox, c[1] + oy) in burn for ox, oy in FOUR)

    def smoky(c):
        return c in smk and c not in burn

    def passable(c):
        return not burning(c) and not adj(c) and not smoky(c)

    def is_boundary(c):
        return any(not inb((c[0] + ox, c[1] + oy)) for ox, oy in FOUR)

    return SimpleNamespace(inb=inb, burning=burning, adj=adj, smoky=smoky, passable=passable,
                           is_boundary=is_boundary, oob=lambda c: not inb(c), burn=burn, smk=smk)


class BoardEnv:
    """A 50x50 board as an fs_env.Env look-alike, for the replay's own kernel."""

    def __init__(self, p):
        self.p = p

    def burning(self, c, k):
        return self.p.burning(c)

    def adj(self, c, k):
        return self.p.adj(c)

    def smoky(self, c, k):
        return self.p.smoky(c)


def kernel_on_board(p, start, order):
    return agents.exit_leg_first_step(start, passable=p.passable, is_boundary=p.is_boundary,
                                      out_of_bounds=p.oob, order=order)


def build(b, with_victim=False):
    m = FakeModel(b["W"], b["H"])
    uid = 1000
    for cell in sorted(b["fire"]):
        bu, sm = b["fire"][cell]
        f = agents.Fire(uid, m, burning=bool(bu))
        uid += 1
        f.smoke.smoke = bool(sm)
        m.grid.place_agent(f, cell)
        m.schedule.agents.append(f)
    ff = agents.Firefighter(1, m, "ff_kc", b["start"])
    ff.assigned = b["assigned"]
    ff.status = b["status"]
    ff.target_pos = b["start"]
    ff.exiting = True
    ff.exit_target = b["exit"]
    m.grid.place_agent(ff, b["start"])
    m.schedule.agents.append(ff)
    victim = None
    if with_victim:
        victim = mesa.Agent(2, m)
        m.grid.place_agent(victim, b["start"])
        ff.rescued_victim = victim
    return m, ff, victim


def snap(ff):
    return {k: copy.deepcopy(v) for k, v in vars(ff).items() if k != "model"}


def perimeter(W, H):
    return sorted({(x, y) for x in range(W) for y in range(H) if x in (0, W - 1) or y in (0, H - 1)})


def fill_random(b, rng, p_agent, p_b, p_s):
    for x in range(b["W"]):
        for y in range(b["H"]):
            if rng.random() < p_agent:
                b["fire"][(x, y)] = [rng.random() < p_b, rng.random() < p_s]


def set_cell(b, c, burning=None, smoke=None):
    f = b["fire"].setdefault(c, [False, False])
    if burning is not None:
        f[0] = bool(burning)
    if smoke is not None:
        f[1] = bool(smoke)


def patches50(b, rng, center, n_patches, radius):
    cx, cy = center
    for _ in range(n_patches):
        px = min(49, max(0, cx + rng.randint(-radius, radius)))
        py = min(49, max(0, cy + rng.randint(-radius, radius)))
        w, h = rng.randint(1, 6), rng.randint(1, 6)
        kind = rng.choice(("burn", "smoke", "mixed"))
        for x in range(px, min(50, px + w)):
            for y in range(py, min(50, py + h)):
                if kind == "burn":
                    set_cell(b, (x, y), burning=True)
                elif kind == "smoke":
                    set_cell(b, (x, y), smoke=True)
                else:
                    set_cell(b, (x, y), burning=rng.random() < 0.4, smoke=rng.random() < 0.5)
    for _ in range(rng.randint(0, 30)):
        x = min(49, max(0, cx + rng.randint(-10, 10)))
        y = min(49, max(0, cy + rng.randint(-10, 10)))
        set_cell(b, (x, y), burning=True)


def gen_board(cat, rng):
    """One board of category `cat`. Returns the board dict (start / fire / W / H);
    status, HOLD and exit_target are drawn by the caller."""
    def new(W, H):
        return {"W": W, "H": H, "fire": {}, "cat": cat}

    def interior(b):
        return (rng.randint(1, b["W"] - 2), rng.randint(1, b["H"] - 2))

    if cat in ("rand", "route_blocked"):
        b = new(rng.randint(2, 12), rng.randint(2, 12))
        fill_random(b, rng, rng.choice((0.5, 0.8, 1.0)), rng.uniform(0, 0.35), rng.uniform(0, 0.4))
        b["start"] = (rng.randrange(b["W"]), rng.randrange(b["H"]))
    elif cat == "rand_interior":
        b = new(rng.randint(3, 12), rng.randint(3, 12))
        fill_random(b, rng, rng.choice((0.5, 0.8, 1.0)), rng.uniform(0, 0.3), rng.uniform(0, 0.35))
        b["start"] = interior(b)
    elif cat == "start_burning":
        b = new(rng.randint(3, 12), rng.randint(3, 12))
        fill_random(b, rng, rng.choice((0.5, 1.0)), rng.uniform(0, 0.3), rng.uniform(0, 0.3))
        b["start"] = (rng.randrange(b["W"]), rng.randrange(b["H"]))
        set_cell(b, b["start"], burning=True, smoke=rng.random() < 0.5)
    elif cat == "start_smoky":
        b = new(rng.randint(3, 12), rng.randint(3, 12))
        fill_random(b, rng, 1.0, rng.uniform(0, 0.08), rng.uniform(0, 0.15))
        b["start"] = interior(b)
        set_cell(b, b["start"], burning=False, smoke=True)
    elif cat == "start_adjacent":
        b = new(rng.randint(3, 12), rng.randint(3, 12))
        fill_random(b, rng, 1.0, rng.uniform(0, 0.05), rng.uniform(0, 0.15))
        b["start"] = interior(b)
        set_cell(b, b["start"], burning=False, smoke=rng.random() < 0.3)
        nb = [(b["start"][0] + ox, b["start"][1] + oy) for ox, oy in FOUR]
        for c in rng.sample(nb, rng.randint(1, 2)):
            set_cell(b, c, burning=True)
    elif cat == "corner":
        b = new(rng.randint(3, 12), rng.randint(3, 12))
        fill_random(b, rng, rng.choice((0.5, 1.0)), rng.uniform(0, 0.2), rng.uniform(0, 0.3))
        W, H = b["W"], b["H"]
        b["start"] = rng.choice(((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1),
                                 (1, 1), (W - 2, 1), (1, H - 2), (W - 2, H - 2)))
    elif cat == "smoky_edges":
        b = new(rng.randint(4, 12), rng.randint(4, 12))
        fill_random(b, rng, 1.0, rng.uniform(0, 0.1), rng.uniform(0, 0.15))
        for c in perimeter(b["W"], b["H"]):
            set_cell(b, c, burning=False, smoke=True)
        b["start"] = interior(b)
    elif cat == "adj_edges":
        b = new(rng.randint(4, 12), rng.randint(4, 12))
        fill_random(b, rng, 1.0, rng.uniform(0, 0.1), rng.uniform(0, 0.15))
        for c in perimeter(b["W"], b["H"]):
            set_cell(b, c, burning=(c[0] + c[1]) % 2 == 0, smoke=rng.random() < 0.2)
        b["start"] = interior(b)
    elif cat == "ties":
        n = rng.choice((3, 5, 7, 9, 11, 13))
        b = new(n, n)
        if rng.random() < 0.5:
            fill_random(b, rng, 1.0, 0.0, rng.uniform(0, 0.1))
        k = rng.randrange(n)
        b["start"] = rng.choice(((n // 2, n // 2), (k, k), (k, n - 1 - k), (n // 2, k), (k, n // 2)))
        set_cell(b, b["start"], burning=False)
    elif cat == "enclosed":
        b = new(rng.randint(3, 12), rng.randint(3, 12))
        fill_random(b, rng, 1.0, rng.uniform(0, 0.3), rng.uniform(0, 0.3))
        b["start"] = interior(b)
        set_cell(b, b["start"], burning=False)
        for ox, oy in FOUR:
            set_cell(b, (b["start"][0] + ox, b["start"][1] + oy), burning=True)
    elif cat == "pocket":
        r = rng.choice((1, 2))
        b = new(rng.randint(2 * r + 3, 12), rng.randint(2 * r + 3, 12))
        fill_random(b, rng, 1.0, rng.uniform(0, 0.08), rng.uniform(0, 0.1))
        sx = rng.randint(r, b["W"] - 1 - r)
        sy = rng.randint(r, b["H"] - 1 - r)
        b["start"] = (sx, sy)
        for x in range(sx - r, sx + r + 1):
            for y in range(sy - r, sy + r + 1):
                if max(abs(x - sx), abs(y - sy)) == r:
                    set_cell(b, (x, y), burning=False, smoke=True)
                else:
                    set_cell(b, (x, y), burning=False, smoke=False)
    elif cat == "big50":
        b = new(50, 50)
        roll = rng.random()
        if roll < 0.3:
            b["start"] = (rng.randrange(50), rng.randrange(50))
        elif roll < 0.6:
            b["start"] = (rng.randint(1, 48), rng.randint(1, 48))
        else:
            cx, cy = rng.choice(((0, 0), (49, 0), (0, 49), (49, 49)))
            b["start"] = (abs(cx - rng.randint(0, 4)), abs(cy - rng.randint(0, 4)))
        patches50(b, rng, b["start"], rng.randint(1, 8), 8)
        if rng.random() < 0.3:
            set_cell(b, b["start"], burning=False, smoke=rng.random() < 0.5)
    elif cat == "big50_edge":
        b = new(50, 50)
        d = rng.randint(0, 4)
        side = rng.randrange(4)
        t = rng.randrange(50)
        b["start"] = ((d, t), (49 - d, t), (t, d), (t, 49 - d))[side]
        patches50(b, rng, b["start"], rng.randint(1, 8), 6)
    elif cat == "boundary":
        b = new(rng.randint(2, 12), rng.randint(2, 12))
        fill_random(b, rng, rng.choice((0.5, 1.0)), rng.uniform(0, 0.3), rng.uniform(0, 0.3))
        b["start"] = rng.choice(perimeter(b["W"], b["H"]))
    elif cat == "narrow":
        if rng.random() < 0.5:
            b = new(rng.choice((1, 2)), rng.randint(1, 12))
        else:
            b = new(rng.randint(1, 12), rng.choice((1, 2)))
        fill_random(b, rng, 1.0, rng.uniform(0, 0.3), rng.uniform(0, 0.3))
        b["start"] = (rng.randrange(b["W"]), rng.randrange(b["H"]))
    else:
        raise AssertionError(cat)
    return b


def pickup_exit(W, H, cell):
    """The pickup's nearest-projection rule (agents.py exiting_setup), with x bounded by
    the grid's width and y by its height."""
    x, y = cell
    dists = {(0, y): x, (W - 1, y): W - 1 - x, (x, 0): y, (x, H - 1): H - 1 - y}
    return min(dists, key=dists.get)


def composition():
    say("")
    say("== (d) COMPOSITION: Firefighter._exit_leg_step on fake boards vs the kernel on the board")
    rng = random.Random(D_SEED)
    random.seed(D_SEED)  # Fire.__init__ draws its fuel from the global stream; fixed here
    cfv = agents.cfv
    missing = object()
    saved = {k: getattr(cfv, k, missing) for k in ("FF_EXIT_LEG_MODE", "FF_EXIT_LEG_HOLD")}
    cov = Counter()   # all starts
    covs = Counter()  # SEARCHED starts only: not on the boundary (mode 2 searches from nothing else)
    by_cat = {c: Counter() for c in CATS}
    errors = []
    info = Counter()
    orders = [tuple(PINNED_ORDER[i] for i in perm)
              for perm in ((1, 0, 2, 3), (2, 3, 0, 1), (3, 2, 1, 0), (0, 1, 3, 2))]

    def bump(key, searched):
        cov[key] += 1
        if searched:
            covs[key] += 1

    def err(i, b, msg):
        if len(errors) < 8:
            errors.append("board %d cat=%s W=%d H=%d start=%s exit=%s status=%s assigned=%s hold=%d: %s" % (
                i, b["cat"], b["W"], b["H"], b["start"], b["exit"], b["status"], b["assigned"], b["hold"], msg))
        cov["errors"] += 1

    def guarded(i, b, what, fn):
        """Run one source call; an exception (or a drawn RNG) is a board error, not a crash."""
        try:
            return True, fn()
        except (AssertionError, Exception) as exc:  # noqa: BLE001
            err(i, b, "%s raised %s: %s" % (what, type(exc).__name__, exc))
            return False, None

    def set_mode(v):
        if v is missing:
            if hasattr(cfv, "FF_EXIT_LEG_MODE"):
                delattr(cfv, "FF_EXIT_LEG_MODE")
        else:
            cfv.FF_EXIT_LEG_MODE = v

    def run_direct(ff):
        with no_rng(ff.model):
            return ff._exit_leg_step()

    def run_move_toward(ff, target):
        with no_rng(ff.model):
            return ff._move_toward(target)

    def run_advance(ff):
        set_mode(2)
        try:
            if agents.ff_exit_leg_mode() != 2:
                raise AssertionError("could not set FF_EXIT_LEG_MODE=2 on cfv")
            with no_rng(ff.model), contextlib.redirect_stdout(io.StringIO()):
                ff.advance()
        finally:
            set_mode(saved["FF_EXIT_LEG_MODE"])

    try:
        i = -1
        for cat in CATS:
            for _ in range(BOARDS_PER_CAT):
                i += 1
                b = gen_board(cat, rng)
                W, H = b["W"], b["H"]
                if rng.random() < 0.5:
                    b["exit"] = pickup_exit(W, H, b["start"])
                else:
                    b["exit"] = rng.choice(perimeter(W, H))
                if cat == "route_blocked" or rng.random() < 0.15:
                    b["status"] = "route_blocked"
                else:
                    b["status"] = "assigned"
                b["assigned"] = rng.random() < 0.85
                b["hold"] = rng.randrange(2)
                cfv.FF_EXIT_LEG_HOLD = b["hold"]
                if agents.ff_exit_leg_hold() != bool(b["hold"]):
                    fail("could not set FF_EXIT_LEG_HOLD=%d on cfv" % b["hold"])
                p = board_preds(b)
                start = b["start"]
                searched = not p.is_boundary(start)
                bump("boards", searched)
                by_cat[cat]["boards"] += 1
                by_cat[cat]["boundary_start"] += not searched

                K = kernel_on_board(p, start, agents.EXIT_LEG_SEARCH_ORDER)
                if any(kernel_on_board(p, start, o) != K for o in orders):
                    bump("order_sensitive", searched)
                if W == 50 and H == 50:
                    R = ORIG(BoardEnv(p), start, 0)
                    bump("board50_replay_kernel_checked", searched)
                    if R != K:
                        err(i, b, "replay bfs_first_step %s != implemented kernel %s" % (R, K))
                start_burning = p.burning(start)
                start_smoky = p.smoky(start)
                start_adj = (not start_burning) and p.adj(start)
                if start_burning:
                    bump("start_burning", searched)
                    if K is not None:
                        err(i, b, "a burning start returned a path %s" % (K,))
                if cat in ("smoky_edges", "adj_edges", "enclosed") and K is not None:
                    err(i, b, "category %s must have no clean path, kernel gave %s" % (cat, K))
                if cat == "smoky_edges":
                    bump("all_smoky_edges", searched)
                if cat == "adj_edges":
                    bump("all_adjacent_edges", searched)
                if start in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1),
                             (1, 1), (W - 2, 1), (1, H - 2), (W - 2, H - 2)):
                    bump("corner_or_diag_start", searched)

                # ---- A: the direct carrying step
                mA, ffA, _ = build(b)
                before = snap(ffA)
                ok, ret = guarded(i, b, "_exit_leg_step", lambda: run_direct(ffA))
                if not ok:
                    continue
                if ret not in ("path", "fallback"):
                    err(i, b, "_exit_leg_step returned %r" % (ret,))
                    continue
                if (ret == "path") != (K is not None):
                    err(i, b, "_exit_leg_step returned %s but the kernel on the board gave %s" % (ret, K))
                    continue
                if ret == "path":
                    bump("path", searched)
                    by_cat[cat]["path"] += 1
                    if start_smoky:
                        bump("start_smoky_with_path", searched)
                    if start_adj:
                        bump("start_adjacent_with_path", searched)
                    want = dict(before)
                    want["pos"] = K
                    want["_last_move_tier"] = agents.EXIT_LEG_PATH_TIER
                    want["_last_move_risk"] = 0
                    if str(before["status"]).strip().lower() == "route_blocked":
                        want["status"] = "assigned" if before["assigned"] else "available"
                        bump("relabel_on_path", searched)
                    after = snap(ffA)
                    if ffA.pos != K:
                        err(i, b, "path step moved to %s, kernel on the board gives %s" % (ffA.pos, K))
                    elif after != want:
                        keys = sorted(k for k in set(after) | set(want) if after.get(k) != want.get(k))
                        err(i, b, "path step changed vars beyond pos/labels/status: %s" % keys)
                    if ffA not in mA.grid.get_cell_list_contents([K]) or \
                            ffA in mA.grid.get_cell_list_contents([start]):
                        err(i, b, "grid placement after the path step is not the kernel cell")
                    if mA.route_blocked_calls:
                        err(i, b, "a path step raised route_blocked")
                    if agents.EXIT_LEG_PATH_TIER != 5:
                        err(i, b, "EXIT_LEG_PATH_TIER is %r, the design's label is 5" % agents.EXIT_LEG_PATH_TIER)
                else:
                    bump("fallback", searched)
                    by_cat[cat]["fallback"] += 1
                    mB, ffB, _ = build(b)
                    ok, _r = guarded(i, b, "_move_toward on the copy", lambda: run_move_toward(ffB, b["exit"]))
                    if not ok:
                        continue
                    sa, sb = snap(ffA), snap(ffB)
                    if sa != sb:
                        keys = sorted(k for k in set(sa) | set(sb) if sa.get(k) != sb.get(k))
                        err(i, b, "fallback != a fresh _move_toward on a copy: %s (%s vs %s)" % (
                            keys, [sa.get(k) for k in keys], [sb.get(k) for k in keys]))
                    if mA.route_blocked_calls != mB.route_blocked_calls:
                        err(i, b, "route_blocked calls %s vs %s" % (mA.route_blocked_calls, mB.route_blocked_calls))
                    if (ffA in mA.grid.get_cell_list_contents([ffB.pos])) is not True:
                        err(i, b, "fallback grid placement differs from _move_toward's")
                    enclosed = not any(p.inb(c) and not p.burning(c)
                                       for c in ((start[0] + ox, start[1] + oy) for ox, oy in FOUR))
                    if enclosed:
                        if b["hold"]:
                            bump("fallback_enclosed_hold1", searched)
                            if ffA._last_move_tier != agents.EXIT_LEG_HOLD_TIER or ffA.pos != start:
                                err(i, b, "enclosed at HOLD 1 did not hold (tier %s pos %s)" % (ffA._last_move_tier, ffA.pos))
                        else:
                            bump("fallback_enclosed_hold0", searched)
                            if ffA.pos != start:
                                err(i, b, "enclosed at HOLD 0 moved")
                    elif ffA._last_move_tier in (1, 2, 3):
                        bump("fallback_tier1to3", searched)
                    elif ffA._last_move_tier == 4:
                        bump("fallback_tier4", searched)
                    else:
                        err(i, b, "non-enclosed fallback with tier %r" % (ffA._last_move_tier,))
                    if W == 50 and H == 50:
                        cell, _t = fs_rules.move_toward(BoardEnv(p), start, b["exit"], 0)
                        info["fb50"] += 1
                        info["fb50_replay_move_toward_agrees"] += (ffB.pos == (cell if cell is not None else start))

                # ---- C: the same board through advance() at mode 2 (completion first)
                mC, ffC, vic = build(b, with_victim=True)
                ok, _r = guarded(i, b, "advance() at mode 2", lambda: run_advance(ffC))
                if not ok:
                    continue
                reason = ffC.movement_reason or {}
                pending = getattr(mC, "_agents_pending_removal", [])
                if p.is_boundary(start):
                    ok = (ffC.rescue_completed is True and ffC.pos == start and ffC in pending
                          and vic in pending and reason.get("fine_category") == "exiting_complete"
                          and (("exit_cell" in reason.get("key_factors", {})) == (start != b["exit"])))
                    if not ok:
                        err(i, b, "boundary start did not complete first (completed=%s pos=%s reason=%s)" % (
                            ffC.rescue_completed, ffC.pos, reason.get("fine_category")))
                    else:
                        bump("boundary_start_completed", searched)
                else:
                    ok = (ffC.rescue_completed is False and ffC.pos == ffA.pos and vic.pos == ffC.pos
                          and ffC not in pending and reason.get("fine_category") == "exiting_with_victim"
                          and reason.get("key_factors", {}).get("risk_tier") == ffA._last_move_tier
                          and ffC._last_move_tier == ffA._last_move_tier
                          and mC.route_blocked_calls == mA.route_blocked_calls)
                    if not ok:
                        err(i, b, "advance() at mode 2 differs from the direct step (pos %s vs %s, victim %s, "
                                  "completed %s, reason %s)" % (ffC.pos, ffA.pos, vic.pos, ffC.rescue_completed,
                                                                reason.get("fine_category")))
                    elif ffC.pos != start:
                        bump("advance_moved_with_victim", searched)
    finally:
        for k, v in saved.items():
            if v is missing:
                if hasattr(cfv, k):
                    delattr(cfv, k)
            else:
                setattr(cfv, k, v)
    if agents.ff_exit_leg_mode() != 0 or agents.ff_exit_leg_hold() is not False:
        fail("the exit-leg switches were not restored to their shipped values")

    say("  boards %d (seed %d, %d categories x %d); path %d, fallback %d; boundary starts %d "
        "(advance() completes them before any search)" % (
            cov["boards"], D_SEED, len(CATS), BOARDS_PER_CAT, cov["path"], cov["fallback"],
            cov["boards"] - covs["boards"]))
    for c in CATS:
        say("    %-15s boards %3d path %3d fallback %3d boundary-start %3d" % (
            c, by_cat[c]["boards"], by_cat[c]["path"], by_cat[c]["fallback"], by_cat[c]["boundary_start"]))
    say("  coverage: SEARCHED = starts mode 2 can search from (not on the boundary); ALL = every start.")
    say("  Each floor applies to SEARCHED, except %s (ALL)." % " and ".join(FLOOR_ON_ALL_STARTS))
    say("    %-32s %8s %5s  %s" % ("", "SEARCHED", "ALL", "floor"))
    short = []
    for k, floor in MIN_COVERAGE.items():
        gated = cov[k] if k in FLOOR_ON_ALL_STARTS else covs[k]
        say("    %-32s %8d %5d  >= %d on %s" % (k, covs[k], cov[k], floor,
                                              "ALL" if k in FLOOR_ON_ALL_STARTS else "SEARCHED"))
        if gated < floor:
            short.append("%s %d < %d" % (k, gated, floor))
    say("  info: 50x50 fallback boards where the replay's move_toward transcription picks the same cell: %d/%d"
        % (info["fb50_replay_move_toward_agrees"], info["fb50"]))
    say("  errors %d" % cov["errors"])
    for e in errors:
        say("    " + e)
    if cov["errors"]:
        fail("COMPOSITION: %d board(s) disagree - see above (a SOURCE finding if the board is valid)" % cov["errors"])
    if short:
        fail("COMPOSITION coverage below floor: %s" % "; ".join(short))
    say("  every path step == the kernel on the board; every fallback == _move_toward on a copy; "
        "boundary starts complete first")
    say("  no RNG touched: 0 accesses logged on agents.random / cfv.SYSTEM_RANDOM / agents.SYSTEM_RANDOM / "
        "model.random; global random and numpy.random states unchanged")


# ======================================================================================
PROV_KEYS = ("head", "agents.py", "common_fixed_variables.py", "kernel", "pool_src")


def run_checks(out):
    say("CARRYING-LEG PART 2 - PRE-WAVE KERNEL CHECK (outputs/_cl_kernelcheck.py; spec I, design 8.4)")
    env_fg = os.environ.get("F_GUESS")
    if env_fg is not None and env_fg != str(F_GUESS):
        fail("F_GUESS=%s in the environment; this check is F_GUESS %d" % (env_fg, F_GUESS))
    check_modules()
    frozen = check_frozen()
    prov = provenance()
    say("  checkout HEAD %s" % prov["head"])
    say("  %d repo source files this check ran - every imported repo module + the frozen replay files - "
        "are tracked and identical to HEAD:" % len(prov["files"]))
    for k in range(0, len(prov["files"]), 4):
        say("    " + ", ".join(prov["files"][k:k + 4]))
    say("  agents.py sha256                 %s" % prov["agents.py"])
    say("  common_fixed_variables.py sha256 %s" % prov["common_fixed_variables.py"])
    say("  kernel source sha256             %s  (inspect.getsource(agents.exit_leg_first_step))" % prov["kernel"])
    say("  _cl_pool.sh src= for this source %s  (%s)" % (prov["pool_src"], " ".join(POOL_SRC_FILES)))
    say("  EXIT_LEG_SEARCH_ORDER %s == the design's (+x,-x,+y,-y) == fs_env.ORDER" % (agents.EXIT_LEG_SEARCH_ORDER,))
    say("  frozen replay files vs _cl_replay/SHA256SUMS.txt: %s" % ", ".join(frozen))
    say("  binding: adapter bound in %s; fs_rules.bfs_first_step left at the original"
        % " + ".join("%s.bfs_first_step" % m.__name__ for m in CONSUMERS))
    say("")
    replay_checks()
    composition()
    say("")
    prov2 = provenance()
    changed = [k for k in PROV_KEYS if prov2[k] != prov[k]]
    if changed:
        fail("provenance: the source changed during the check (%s)" % ", ".join(
            "%s %s -> %s" % (k, prov[k], prov2[k]) for k in changed))
    extra = sorted(set(prov2["files"]) - set(prov["files"]))
    say("== PROVENANCE RE-CHECK at the end: HEAD, the three sha256 and src= unchanged; %d repo source files "
        "tracked and identical to HEAD%s" % (len(prov2["files"]),
                                             "; imported during the run: " + ", ".join(extra) if extra else ""))
    say("")
    say("KERNELCHECK PASS")
    write_record(out)
    print("wrote %s" % out)


def main(argv=()):
    """argv () = the defaults (a probe calling main() directly); the command line passes
    sys.argv[1:]."""
    ap = argparse.ArgumentParser(description="carrying-leg pre-wave kernel check (spec I)")
    ap.add_argument("--out", default=None,
                    help="record path (default outputs/_cl_kernelcheck.txt); removed at the start of the run")
    args = ap.parse_args(list(argv))
    out = os.path.abspath(args.out or OUT_TXT)
    if QUAR in os.path.normcase(out):
        raise SystemExit("KERNELCHECK FAIL: --out names the quarantine")
    del LINES[:]
    # A previous record never survives this run: removed before any check, rewritten
    # only as PASS (all passed) or as the lines so far + the FAIL line.
    for pth in (out, out + ".tmp"):
        try:
            if os.path.exists(pth):
                os.remove(pth)
        except OSError as exc:
            raise SystemExit("KERNELCHECK FAIL: cannot remove the previous record %s (%s)" % (pth, exc))
    _RUN["out"] = out
    try:
        run_checks(out)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - a crash is a FAIL with a record, never a silent stale state
        traceback.print_exc()
        fail("unexpected %s: %s" % (type(exc).__name__, exc))
    finally:
        _RUN["out"] = None


if __name__ == "__main__":
    main(sys.argv[1:])
