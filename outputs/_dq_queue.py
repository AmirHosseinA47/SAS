"""Dispatch round 2 queues and the pre-wave tag check (outputs/dispatch2_part1.txt sections 0.5, 8, 9, 13 (9), 14;
amendment A1 section 19: X-7 (a) - dqR re-measured at main 897e93b5 on sets 7-8). Lines for outputs/_mf2_pool.py
({"name", "argv", "out", "cwd"}). It GENERATES QUEUES ONLY - it never starts a run.

usage (any cwd; E:/Projects/SAS/.venv/Scripts/python.exe):
  python outputs/_dq_queue.py write [--dest DIR]
        the seed check, every wave's lines, the line validation; then writes the FROZEN queues (LF)
        outputs/_dq_q_w1.jsonl (128), _dq_q_w2.jsonl (64), _dq_q_smoke.jsonl (6), _dq_q_struct.jsonl (16).
        A queue file that already exists must be identical (LF-normalised) to the rebuilt lines, else STOP (a frozen
        queue is never re-frozen); new files are written only when the tag check of their lines passes; all or
        nothing. --dest writes the four files into DIR instead (self-tests); the lines are the same.
  python outputs/_dq_queue.py check [WAVE ...] [--range A-B] [--resume] [--all-trees] [--dest DIR]
        before a launch: the frozen file equals the rebuilt lines, the probe exists, the reference checkout is
        897e93b5 (waves with dqR lines), and the TAG CHECK; prints a PASS / FAIL table per wave and an OVERALL line
        (exit 0 = PASS, 1 = FAIL). No WAVE = all four. --range A-B (1-based, inclusive) checks only those lines of
        the (single) wave: the structure check is launched incrementally. --resume: the lines' OWN untracked outputs
        may exist (a re-launch; the pool skips a run whose .argv matches); an out without its .argv is still a FAIL.
  python outputs/_dq_queue.py show WAVE [--range A-B]
        print the wave's lines (name, seed, cwd, switches).
  python outputs/_dq_queue.py slice WAVE A-B PATH [--dest DIR]
        write lines A..B (1-based, inclusive) of the FROZEN queue, unchanged, to PATH (LF) for an incremental launch;
        an existing PATH must be identical, else STOP.
  waves: w1 w2 smoke struct

ARMS (section 9; every arm pins the shipped movement, FF_APPROACH_PATH = FF_RETREAT_KEEP_APPROACH =
FF_FIX_STRANDING_GUARD = 1):
  dqR  E:\\Projects\\SAS_wt\\base897e93b5 (detached main 897e93b5; no DISPATCH_* keys there, none set)
  dq0  E:\\Projects\\SAS_wt\\dispatch     --set DISPATCH_JOINT=0 --set DISPATCH_REASSIGN=0
  dq1  E:\\Projects\\SAS_wt\\dispatch     --set DISPATCH_JOINT=1 --set DISPATCH_REASSIGN=1
RUN LINE (section 9; CRN by the --crn flag, never --set FM2P_CRN; the probe is ALWAYS the dispatch worktree's; cwd =
--repo = the arm's checkout; every --out absolute into E:\\Projects\\SAS_wt\\dispatch\\outputs, dqR included):
  <py> E:\\Projects\\SAS_wt\\dispatch\\outputs\\_dq_probe.py --crn --hazard -- --repo <checkout> --scenario S
       --wind W --seed N --set GLOBAL_PLANNER_MODE=0 --set VICTIM_SPAWN_MODE=<0|1> --set FF_APPROACH_PATH=1
       --set FF_RETREAT_KEEP_APPROACH=1 --set FF_FIX_STRANDING_GUARD=1 [arm's dispatch switches]
       --steps 360 --set BATCH_SIZE=360 --out <outputs>\\_sd_<tag>_<S>_<W>.json --tag <tag>_<S>_<W>
TAGS: dq<a><p><k>, a = R / 0 / 1, p = r (VICTIM_SPAWN_MODE 0) / u (1), k = seed set (7 / 8; smoke and structure
  1 / 2). The run name (= the pool name = --tag) is dq<a><p><k>_<S>_<W>.
WAVES (section 14; 13 (9)):
  w1      dqR + dq0 on sets 7-8, set -> placement -> cell (rows in _dq_seeds.txt order) -> arm R, 0 (the two
          arms of a cell adjacent)                                                                            128
  w2      dq1 on sets 7-8, set -> placement -> cell                                                            64
  smoke   set 1 ring A_N and set 1 uniform A_N, arms R, 0, 1 adjacent per cell                                  6
  struct  STRUCTURE CHECK candidates: dq1 on set 1 ring, set 1 uniform, set 2 ring, set 2 uniform, rows in
          outputs/_dq_seeds.txt order (A_E A_N A_S A_W B_E ... D_W: the file's rows are sorted by key), skipping the
          two smoke cells, the first 16; launched incrementally (slice / check --range)                        16
  The smoke's dq1 lines (dq1r1_A_N, dq1u1_A_N) and the structure lines share the tag FAMILIES dq1r1 / dq1u1 but
  never a run name: the tag check works on run names, so a structure check after the smoke is not refused.
SEEDS: outputs/_dq_seeds.txt (tracked, unmodified), bases EXPECTED_BASES; the rule seed = base + 4*s + w (s A0 B1 C2
  D3, w N0 S1 E2 W3; rows sorted by key) is RECOMPUTED for all eight sets and any mismatch STOPS; sets 1-6 must also
  equal outputs/_mvg_seeds.txt. It never scans for seeds.
TAG CHECK (0.5, 14: "re-checked unused (tracked and untracked, all trees) before each wave"): a run name is IN USE
  when it occurs as a whole token (case-insensitive; not preceded or followed by a letter or digit) in
    - the name of any entry of the TOP-LEVEL listing (os.listdir, never a walk) of outputs/ and outputs/_ffr_logs/ of
      the dispatch, urgency and base897e93b5 worktrees and of the main checkout E:\\Projects\\SAS, and of every
      outputs/_dq* directory of the dispatch worktree (this round's own; one level); --all-trees adds every other
      registered worktree's outputs/ and outputs/_ffr_logs/;
    - any path of `git ls-files` of the dispatch worktree (its index);
    - any path ADDED by any commit reachable from any ref (git log --all -m --no-renames --diff-filter=A
      --name-only; every tracked path was added once);
  the quarantine directory is never listed and is excluded from every git pathspec. A line's own outputs (out,
  .argv, .poollog, .stdout.txt) are judged apart: absent, or with --resume untracked. Each location carries a
  POSITIVE CONTROL - a run name known to exist there (round 1's dp0r_A_N, the urgency round's ud0r1_A_N, the
  movement round's mvg1r5_A_N, the shared _ffr_logs entry base1511_east_def_101) - that the same matcher must find;
  a location whose control is not found is BLIND (FAIL).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

WT = r"E:\Projects\SAS_wt\dispatch"
OUT = os.path.join(WT, "outputs")
REF_WT = r"E:\Projects\SAS_wt\base897e93b5"
REF_SHA = "897e93b5ed14b582789fd3e59501253aebfb911b"
URGENCY_WT = r"E:\Projects\SAS_wt\urgency"
MAIN_WT = r"E:\Projects\SAS"
PROBE = os.path.join(OUT, "_dq_probe.py")
SEEDS = os.path.join(OUT, "_dq_seeds.txt")
MVG_SEEDS = os.path.join(OUT, "_mvg_seeds.txt")
POOL = os.path.join(OUT, "_mf2_pool.py")
PY = os.path.join(MAIN_WT, ".venv", "Scripts", "python.exe")
QUARANTINE_NAME = "_firemech_rewound_20260914"
QUARANTINE_EXCLUDE = ":(exclude)outputs/" + QUARANTINE_NAME

EXPECTED_BASES = {"set1": 9601, "set2": 9621, "set3": 573001, "set4": 780001, "set5": 135961, "set6": 287041,
                  "set7": 575201, "set8": 741141}
SCENARIOS = "ABCD"
WINDS = (("N", "north"), ("S", "south"), ("E", "east"), ("W", "west"))
PLACEMENTS = (("r", 0), ("u", 1))
FF_PINS = ["--set", "FF_APPROACH_PATH=1", "--set", "FF_RETREAT_KEEP_APPROACH=1", "--set", "FF_FIX_STRANDING_GUARD=1"]
ARMS = {
    "R": (REF_WT, []),
    "0": (WT, ["--set", "DISPATCH_JOINT=0", "--set", "DISPATCH_REASSIGN=0"]),
    "1": (WT, ["--set", "DISPATCH_JOINT=1", "--set", "DISPATCH_REASSIGN=1"]),
}
SCREEN_SETS = (7, 8)
SMOKE_CELLS = ((1, "r", "A_N"), (1, "u", "A_N"))
STRUCT_SETS = (1, 2)
STRUCT_MAX = 16
WAVES = ("w1", "w2", "smoke", "struct")
EXPECTED_COUNTS = {"w1": 128, "w2": 64, "smoke": 6, "struct": 16}
WAVE_ARMS = {"w1": ("R", "0"), "w2": ("1",), "smoke": ("R", "0", "1"), "struct": ("1",)}
WAVE_SETS = {"w1": SCREEN_SETS, "w2": SCREEN_SETS, "smoke": (1,), "struct": STRUCT_SETS}
NAME_RE = re.compile(r"^dq([R01])([ru])([1278])_([A-D])_([NSEW])$")
# positive controls: a run name known to exist at each location (verified 2026-10-08)
CONTROL_OUTPUTS = {WT: "dp0r_A_N", URGENCY_WT: "ud0r1_A_N", REF_WT: "mvg1r5_A_N", MAIN_WT: "mvg1r5_A_N"}
CONTROL_FFR = "base1511_east_def_101"
CONTROL_GIT = "dp0r_A_N"


def stop(msg: str) -> None:
    raise SystemExit("STOP: " + msg)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _here_check() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    if _norm(os.path.realpath(here)) != _norm(os.path.realpath(OUT)):
        stop("this script must live in %s (it is in %s): the queue paths are absolute" % (OUT, here))


def _git(args: list[str], cwd: str = WT, check: bool = True) -> bytes:
    proc = subprocess.run(["git", "-C", cwd, "-c", "core.quotepath=off", *args], capture_output=True)
    if check and proc.returncode != 0:
        stop("git -C %s %s failed (rc %d): %s" % (cwd, " ".join(args), proc.returncode,
                                                  proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout


def _lf(data: bytes, what: str) -> bytes:
    """core.autocrlf is true on this machine: a fresh checkout turns the LF files written here into CRLF. Every file
    this script writes is LF, so the content is compared LF-normalised, with a note."""
    if b"\r\n" in data:
        print("note: %s is CRLF on disk (git eol conversion); compared LF-normalised" % what)
        return data.replace(b"\r\n", b"\n")
    return data


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: str) -> str:
    with open(path, "rb") as fh:
        return _sha(fh.read())


# ----------------------------------------------------------------------------------------------------------- seeds
def rule_rows(base: int) -> list[list[str]]:
    rows = []
    for s, scen in enumerate(SCENARIOS):
        for w, (wk, wind) in enumerate(WINDS):
            rows.append(["%s_%s" % (scen, wk), scen, wind, str(base + 4 * s + w)])
    rows.sort(key=lambda r: r[0])
    return rows


_SEEDS_CACHE: dict[int, list[tuple[str, str, str, str]]] = {}


def seeds() -> dict[int, list[tuple[str, str, str, str]]]:
    """outputs/_dq_seeds.txt: tracked and unmodified, bases == EXPECTED_BASES, sets 1-8 exactly, every set's rows ==
    the rule recomputed, no seed in two sets, sets 1-6 == outputs/_mvg_seeds.txt. STOP on any mismatch."""
    if _SEEDS_CACHE:
        return _SEEDS_CACHE
    if _norm(SEEDS) == _norm(os.path.join(OUT, "_dq_seeds.txt")):
        rel = "outputs/_dq_seeds.txt"
        if not _git(["ls-files", "--", rel]).strip():
            stop("%s is not tracked (section 8: frozen and committed)" % SEEDS)
        if _git(["status", "--porcelain", "-uno", "--", rel]).strip():
            stop("%s is modified against the index / HEAD (frozen)" % SEEDS)
    with open(SEEDS, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("bases") != EXPECTED_BASES:
        stop("_dq_seeds.txt bases %r != section 8's %r" % (doc.get("bases"), EXPECTED_BASES))
    sets_in_file = sorted(k for k in doc if k.startswith("set"))
    if sets_in_file != sorted(EXPECTED_BASES):
        stop("_dq_seeds.txt holds sets %s, expected exactly %s" % (sets_in_file, sorted(EXPECTED_BASES)))
    out: dict[int, list[tuple[str, str, str, str]]] = {}
    seen: dict[str, str] = {}
    for name, base in EXPECTED_BASES.items():
        rows = doc.get(name)
        if rows != rule_rows(base):
            stop("_dq_seeds.txt %s does not follow the rule seed = %d + 4*s + w (rows sorted by key)" % (name, base))
        for row in rows:
            if row[3] in seen:
                stop("seed %s appears in %s and %s" % (row[3], seen[row[3]], name))
            seen[row[3]] = name
        out[int(name[3:])] = [tuple(r) for r in rows]
    with open(MVG_SEEDS, encoding="utf-8") as fh:
        mvg = json.load(fh)
    for k in range(1, 7):
        if [tuple(r) for r in mvg.get("set%d" % k, [])] != out[k]:
            stop("set %d of _dq_seeds.txt differs from outputs/_mvg_seeds.txt" % k)
    _SEEDS_CACHE.update(out)
    return _SEEDS_CACHE


def seed_of(k: int, key: str) -> str:
    return dict((r[0], r[3]) for r in seeds()[k])[key]


# ----------------------------------------------------------------------------------------------------------- lines
def probe_line(arm: str, p: str, k: int, key: str, scen: str, wind: str, seed: str) -> dict:
    repo, dispatch_sets = ARMS[arm]
    mode = dict(PLACEMENTS)[p]
    name = "dq%s%s%d_%s" % (arm, p, k, key)
    out = os.path.join(OUT, "_sd_%s.json" % name)
    argv = [PROBE, "--crn", "--hazard", "--", "--repo", repo, "--scenario", scen, "--wind", wind, "--seed", str(seed),
            "--set", "GLOBAL_PLANNER_MODE=0", "--set", "VICTIM_SPAWN_MODE=%d" % mode]
    argv += FF_PINS + dispatch_sets
    argv += ["--steps", "360", "--set", "BATCH_SIZE=360", "--out", out, "--tag", name]
    return {"name": name, "argv": argv, "out": out, "cwd": repo}


def _cells(sets: tuple[int, ...]):
    table = seeds()
    for k in sets:
        for p, _mode in PLACEMENTS:
            for key, scen, wind, seed in table[k]:
                yield k, p, key, scen, wind, seed


def wave_lines(wave: str) -> list[dict]:
    if wave in ("w1", "w2"):
        return [probe_line(a, p, k, key, scen, wind, seed)
                for k, p, key, scen, wind, seed in _cells(SCREEN_SETS) for a in WAVE_ARMS[wave]]
    if wave == "smoke":
        return [probe_line(a, p, k, key, scen, wind, seed)
                for k, p, key, scen, wind, seed in _cells((1,)) if (k, p, key) in SMOKE_CELLS
                for a in WAVE_ARMS[wave]]
    if wave == "struct":
        lines = [probe_line("1", p, k, key, scen, wind, seed)
                 for k, p, key, scen, wind, seed in _cells(STRUCT_SETS) if (k, p, key) not in SMOKE_CELLS]
        return lines[:STRUCT_MAX]
    stop("unknown wave %r (waves: %s)" % (wave, " ".join(WAVES)))
    return []


# ------------------------------------------------------------------------------------------------------ validation
def _expected_sets(arm: str, p: str) -> list[str]:
    """The --set values of a line, in order (section 9), written out independently of probe_line."""
    vals = ["GLOBAL_PLANNER_MODE=0", "VICTIM_SPAWN_MODE=%d" % {"r": 0, "u": 1}[p], "FF_APPROACH_PATH=1",
            "FF_RETREAT_KEEP_APPROACH=1", "FF_FIX_STRANDING_GUARD=1"]
    if arm == "0":
        vals += ["DISPATCH_JOINT=0", "DISPATCH_REASSIGN=0"]
    elif arm == "1":
        vals += ["DISPATCH_JOINT=1", "DISPATCH_REASSIGN=1"]
    return vals + ["BATCH_SIZE=360"]


def validate_line(line: dict, wave: str) -> tuple[str, str, int, str]:
    """One line against section 9, re-derived from the name: STOP on any deviation. Returns (arm, p, k, key)."""
    name = line.get("name", "")
    if sorted(line) != ["argv", "cwd", "name", "out"]:
        stop("%s: keys %s" % (name, sorted(line)))
    m = NAME_RE.match(name)
    if not m:
        stop("%s: not a dq<a><p><k>_<S>_<W> name" % name)
    arm, p, k, scen, wk = m.group(1), m.group(2), int(m.group(3)), m.group(4), m.group(5)
    key = "%s_%s" % (scen, wk)
    if arm not in WAVE_ARMS[wave] or k not in WAVE_SETS[wave]:
        stop("%s: arm %s / set %d is not in wave %s" % (name, arm, k, wave))
    argv = line["argv"]
    if argv[:4] != [PROBE, "--crn", "--hazard", "--"] or not os.path.isabs(argv[0]):
        stop("%s: the probe head %r" % (name, argv[:4]))
    rest = argv[4:]
    if len(rest) % 2:
        stop("%s: odd flag / value list" % name)
    pairs = [(rest[i], rest[i + 1]) for i in range(0, len(rest), 2)]
    flags = [f for f, _v in pairs]
    want_flags = ["--repo", "--scenario", "--wind", "--seed"] + ["--set"] * (len(_expected_sets(arm, p)) - 1) + [
        "--steps", "--set", "--out", "--tag"]
    if flags != want_flags:
        stop("%s: flags %s != %s" % (name, flags, want_flags))
    val = {}
    for f, v in pairs:
        if f != "--set":
            val[f] = v
    sets = [v for f, v in pairs if f == "--set"]
    if sets != _expected_sets(arm, p):
        stop("%s: --set list %s != %s" % (name, sets, _expected_sets(arm, p)))
    if any("FM2P_CRN" in s for s in sets):
        stop("%s: FM2P_CRN set (CRN is the --crn flag only)" % name)
    want_repo = REF_WT if arm == "R" else WT
    if val["--repo"] != want_repo or line["cwd"] != want_repo or not os.path.isabs(want_repo):
        stop("%s: --repo %r / cwd %r, expected %r" % (name, val["--repo"], line["cwd"], want_repo))
    if val["--scenario"] != scen or val["--wind"] != dict(WINDS)[wk]:
        stop("%s: scenario / wind %r %r" % (name, val["--scenario"], val["--wind"]))
    rule_seed = EXPECTED_BASES["set%d" % k] + 4 * SCENARIOS.index(scen) + [w for w, _n in WINDS].index(wk)
    if val["--seed"] != str(rule_seed) or val["--seed"] != seed_of(k, key):
        stop("%s: seed %s, rule %d, file %s" % (name, val["--seed"], rule_seed, seed_of(k, key)))
    if val["--steps"] != "360":
        stop("%s: --steps %s" % (name, val["--steps"]))
    out = val["--out"]
    if (not os.path.isabs(out) or out != line["out"] or _norm(os.path.dirname(out)) != _norm(OUT)
            or os.path.basename(out) != "_sd_%s.json" % name):
        stop("%s: --out %r (out %r) is not %s" % (name, out, line["out"], os.path.join(OUT, "_sd_%s.json" % name)))
    if val["--tag"] != name:
        stop("%s: --tag %r" % (name, val["--tag"]))
    return arm, p, k, key


def validate_wave(wave: str, lines: list[dict]) -> None:
    if len(lines) != EXPECTED_COUNTS[wave]:
        stop("%s: %d lines, expected %d" % (wave, len(lines), EXPECTED_COUNTS[wave]))
    got = [validate_line(line, wave) for line in lines]
    cells = {}
    for arm, p, k, key in got:
        cells.setdefault((k, p, key), []).append(arm)
    # the order, written out per wave: set -> placement -> row of _dq_seeds.txt (sorted by key) -> arm
    if wave in ("w1", "w2"):
        want = [(k, p, key, a) for k in SCREEN_SETS for p, _m in PLACEMENTS for key, *_r in seeds()[k]
                for a in (("R", "0") if wave == "w1" else ("1",))]
    elif wave == "smoke":
        want = [(1, p, "A_N", a) for p in ("r", "u") for a in ("R", "0", "1")]
    else:
        want = [(k, p, key, "1") for k in STRUCT_SETS for p, _m in PLACEMENTS for key, *_r in seeds()[k]
                if (k, p, key) not in SMOKE_CELLS][:STRUCT_MAX]
    if [(k, p, key, a) for a, p, k, key in got] != want:
        stop("%s: the lines are not, in order, %s" % (wave, {
            "w1": "sets 7-8 x r/u x the 16 rows x arms R, 0", "w2": "sets 7-8 x r/u x the 16 rows, arm 1",
            "smoke": "set 1 r / u A_N x arms R, 0, 1",
            "struct": "the first %d set-1/2 cells in _dq_seeds.txt order without the smoke cells, arm 1" % STRUCT_MAX,
        }[wave]))
    if wave == "w1":
        # the S1 premise: dqR and dq0 of a cell differ only in --repo / cwd, --out, --tag and dq0's two switches
        by = {(k, p, key, a): line for (a, p, k, key), line in zip(got, lines)}
        swap = {"--repo": REF_WT}
        for (k, p, key) in cells:
            r, z = by[(k, p, key, "R")], by[(k, p, key, "0")]
            strip, i = [], 0
            while i < len(z["argv"]):
                if z["argv"][i] == "--set" and i + 1 < len(z["argv"]) and z["argv"][i + 1] in (
                        "DISPATCH_JOINT=0", "DISPATCH_REASSIGN=0"):
                    i += 2
                    continue
                strip.append(z["argv"][i])
                i += 1
            swap.update({"--out": r["out"], "--tag": r["name"]})
            mapped = [swap.get(strip[j - 1], t) if j else t for j, t in enumerate(strip)]
            if mapped != r["argv"] or r["cwd"] != REF_WT or z["cwd"] != WT:
                stop("w1: dqR and dq0 of s%d %s %s differ beyond repo / out / tag / dispatch switches" % (k, p, key))


def all_lines() -> dict[str, list[dict]]:
    per = {}
    for wave in WAVES:
        lines = wave_lines(wave)
        validate_wave(wave, lines)
        per[wave] = lines
    every = [ln for wave in WAVES for ln in per[wave]]
    names = [ln["name"].lower() for ln in every]
    outs = [_norm(ln["out"]) for ln in every]
    if len(set(names)) != len(names) or len(set(outs)) != len(outs):
        stop("duplicate run names or outputs across the waves (case-insensitive)")
    return per


def queue_path(wave: str, dest: str | None = None) -> str:
    return os.path.join(os.path.normpath(dest) if dest else OUT, "_dq_q_%s.jsonl" % wave)


def queue_bytes(lines: list[dict]) -> bytes:
    return "".join(json.dumps(line) + "\n" for line in lines).encode("utf-8")


# ------------------------------------------------------------------------------------------------------- tag check
def tag_regex(names) -> re.Pattern:
    alts = "|".join(re.escape(n) for n in sorted(set(names), key=lambda s: (-len(s), s)))
    return re.compile(r"(?<![A-Za-z0-9])(?:%s)(?![A-Za-z0-9])" % alts, re.IGNORECASE)


_CACHE: dict[str, object] = {}


def _listing(folder: str) -> list[str] | None:
    """Names in ONE folder (os.listdir, never a walk); None if absent; never lists the quarantine directory itself."""
    key = "ls:" + _norm(folder)
    if key not in _CACHE:
        if os.path.basename(os.path.normpath(folder)).lower() == QUARANTINE_NAME.lower():
            stop("refusing to list the quarantine directory %s" % folder)
        _CACHE[key] = os.listdir(folder) if os.path.isdir(folder) else None
    return _CACHE[key]  # type: ignore[return-value]


def _git_paths(kind: str) -> list[str]:
    key = "git:" + kind
    if key not in _CACHE:
        if kind == "index":
            raw = _git(["ls-files", "-z", "--", ".", QUARANTINE_EXCLUDE])
        else:
            raw = _git(["log", "--all", "-m", "--no-renames", "--diff-filter=A", "--format=", "--name-only", "-z",
                        "--", ".", QUARANTINE_EXCLUDE])
        paths = sorted({p.strip("\r\n") for p in raw.decode("utf-8", "replace").split("\0") if p.strip("\r\n")})
        if any(QUARANTINE_NAME.lower() in p.lower() for p in paths):
            stop("git %s listed a quarantine path despite the exclude pathspec" % kind)
        _CACHE[key] = paths
    return _CACHE[key]  # type: ignore[return-value]


def _worktrees() -> list[str]:
    out = []
    for row in _git(["worktree", "list", "--porcelain"]).decode("utf-8", "replace").splitlines():
        if row.startswith("worktree "):
            out.append(os.path.normpath(row[len("worktree "):]))
    return out


def locations(all_trees: bool) -> list[tuple[str, str, str | None]]:
    """(label, folder, control run name or None) - top-level listings only."""
    locs: list[tuple[str, str, str | None]] = []
    for tree in (WT, URGENCY_WT, REF_WT, MAIN_WT):
        locs.append((os.path.join(tree, "outputs"), os.path.join(tree, "outputs"), CONTROL_OUTPUTS[tree]))
        locs.append((os.path.join(tree, "outputs", "_ffr_logs"), os.path.join(tree, "outputs", "_ffr_logs"),
                     CONTROL_FFR))
    for name in sorted(_listing(OUT) or []):
        sub = os.path.join(OUT, name)
        if name.lower().startswith("_dq") and name.lower() != QUARANTINE_NAME.lower() and os.path.isdir(sub):
            locs.append((sub, sub, None))
    if all_trees:
        known = {_norm(f) for _l, f, _c in locs}
        for wt in _worktrees():
            for folder in (os.path.join(wt, "outputs"), os.path.join(wt, "outputs", "_ffr_logs")):
                if _norm(folder) not in known:
                    locs.append((folder, folder, None))
                    known.add(_norm(folder))
    return locs


def own_paths(line: dict) -> list[str]:
    base = line["out"]
    stem = base[:-5] if base.endswith(".json") else base
    return [base, base + ".argv", base + ".poollog", stem + ".stdout.txt", base + ".stdout.txt"]


def tag_check(lines: list[dict], resume: bool = False, all_trees: bool = False) -> tuple[list[list[str]], list[str]]:
    """Returns (rows [check, scanned, hits, control, verdict], hit details). A row's verdict is PASS or FAIL."""
    names = [ln["name"] for ln in lines]
    rx = tag_regex(names)
    rows: list[list[str]] = []
    details: list[str] = []
    index = _git_paths("index")
    tracked = {_norm(os.path.join(WT, p.replace("/", os.sep))) for p in index}
    own: set[str] = set()
    n_own = 0
    bad_own = []
    for line in lines:
        paths = own_paths(line)
        own.update(_norm(p) for p in paths)
        for path in paths:
            n_own += 1
            if not os.path.exists(path):
                continue
            is_tracked = _norm(path) in tracked
            if is_tracked or not resume:
                bad_own.append(("TRACKED " if is_tracked else "EXISTS ") + path)
        if resume and os.path.exists(line["out"]) and not os.path.exists(line["out"] + ".argv"):
            bad_own.append("CRASHED OR PARTIAL RECORD (no .argv: copy it aside before re-queuing) " + line["out"])
    rows.append(["own outputs (exact paths%s)" % (", --resume" if resume else ""), str(n_own), str(len(bad_own)), "-",
                 "PASS" if not bad_own else "FAIL"])
    details += bad_own
    for label, folder, control in locations(all_trees):
        names_here = _listing(folder)
        if names_here is None:
            rows.append([label, "absent", "0", "-", "PASS (absent)"])
            continue
        hits = []
        for name in names_here:
            if rx.search(name):
                path = os.path.join(folder, name)
                if _norm(path) in own:
                    continue  # judged by the own-outputs row
                hits.append(("TRACKED " if _norm(path) in tracked else "TAG IN USE ") + path)
        ctl = "-"
        verdict = "PASS" if not hits else "FAIL"
        if control is not None:
            found = any(tag_regex([control]).search(n) for n in names_here)
            ctl = "found" if found else "NOT FOUND"
            if not found:
                verdict = "FAIL (BLIND)"
        rows.append([label, str(len(names_here)), str(len(hits)), ctl, verdict])
        details += hits
    for kind, label in (("index", "git ls-files (dispatch index, quarantine excluded)"),
                        ("history", "git history (all refs, added paths, quarantine excluded)")):
        paths = _git_paths(kind)
        hits = ["TRACKED (%s) %s" % (kind, p) for p in paths if rx.search(p)]
        found = any(tag_regex([CONTROL_GIT]).search(p) for p in paths)
        verdict = "PASS" if not hits else "FAIL"
        if not found:
            verdict = "FAIL (BLIND)"
        rows.append([label, str(len(paths)), str(len(hits)), "found" if found else "NOT FOUND", verdict])
        details += hits
    return rows, sorted(set(details))


def ref_checkout_row() -> list[str]:
    """dqR's checkout: HEAD 897e93b5 (section 9, X-7 (a)), no joint_dispatch module, run-loaded tracked code clean."""
    if not os.path.isdir(REF_WT):
        return ["reference checkout " + REF_WT, "-", "-", "-", "FAIL (absent)"]
    head = _git(["rev-parse", "HEAD"], cwd=REF_WT, check=False).decode().strip()
    jd = os.path.exists(os.path.join(REF_WT, "src_extension", "planning", "joint_dispatch.py"))
    dirty = _git(["status", "--porcelain", "-uno", "--", "agents.py", "wildfire_model.py", "common_fixed_variables.py",
                  "src_extension"], cwd=REF_WT, check=False).decode("utf-8", "replace").strip()
    ok = head == REF_SHA and not jd and not dirty
    note = "HEAD %s%s%s" % (head[:8] or "?", ", joint_dispatch.py PRESENT" if jd else "",
                            ", tracked code MODIFIED" if dirty else "")
    return ["reference checkout " + REF_WT, "-", "-", "-", ("PASS (%s)" if ok else "FAIL (%s)") % note]


# ------------------------------------------------------------------------------------------------------------ main
def _range(arg: str | None, n: int) -> tuple[int, int]:
    if arg is None:
        return 1, n
    m = re.match(r"^(\d+)-(\d+)$", arg)
    if not m or not 1 <= int(m.group(1)) <= int(m.group(2)) <= n:
        stop("range %r: give A-B with 1 <= A <= B <= %d" % (arg, n))
    return int(m.group(1)), int(m.group(2))


def _opt(flag: str) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 >= len(sys.argv):
            stop("%s needs a value" % flag)
        return sys.argv[i + 1]
    return None


def _print_table(rows: list[list[str]]) -> None:
    head = ["check", "scanned", "hits", "control", "verdict"]
    width = [max(len(r[i]) for r in rows + [head]) for i in range(5)]
    for r in [head] + rows:
        print("  " + "  ".join(r[i].ljust(width[i]) if i in (0, 4) else r[i].rjust(width[i]) for i in range(5))
              .rstrip())


def write(dest: str | None) -> int:
    _here_check()
    per = all_lines()
    target = os.path.normpath(dest) if dest else OUT
    if not os.path.isdir(target):
        stop("--dest %s is not a directory" % target)
    probe_ok = os.path.exists(PROBE)
    print("probe %s: %s" % (PROBE, ("present, sha256 %s" % _file_sha(PROBE)) if probe_ok else "MISSING"))
    if not probe_ok and dest is None:
        stop("the probe %s does not exist: the frozen queues are written after the instrument exists" % PROBE)
    print("seeds outputs/_dq_seeds.txt sha256 %s (rule recomputed for sets 1-8, sets 1-6 == _mvg_seeds.txt)"
          % _file_sha(SEEDS))
    plan = []
    new_lines: list[dict] = []
    for wave in WAVES:
        data = queue_bytes(per[wave])
        path = queue_path(wave, dest)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                if _lf(fh.read(), path) != data:
                    stop("%s exists and differs from the rebuilt lines (frozen; never re-written)" % path)
            plan.append((wave, path, data, "unchanged (frozen)"))
        else:
            plan.append((wave, path, data, "written"))
            new_lines += per[wave]
    if new_lines:
        rows, details = tag_check(new_lines)
        if any(not r[4].startswith("PASS") for r in rows):
            _print_table(rows)
            stop("TAG CHECK FAILED - nothing written:\n  " + "\n  ".join(details[:60]))
    for wave, path, data, state in plan:
        if state == "written":
            with open(path, "wb") as fh:
                fh.write(data)
        print("%-6s %3d lines  sha256 %s  %s  %s" % (wave, len(per[wave]), _sha(data), path, state))
    print("total %d lines" % sum(len(per[w]) for w in WAVES))
    return 0


def check(waves: list[str], rng: str | None, resume: bool, all_trees: bool, dest: str | None) -> int:
    _here_check()
    per = all_lines()
    if rng is not None and len(waves) != 1:
        stop("--range needs exactly one wave")
    head = _git(["rev-parse", "HEAD"]).decode().strip()
    print("dispatch HEAD %s; seeds sha256 %s (rule recomputed, sets 1-6 == _mvg_seeds.txt)" % (head, _file_sha(SEEDS)))
    overall = True
    for wave in waves:
        lines = per[wave]
        a, b = _range(rng, len(lines))
        sel = lines[a - 1:b]
        tags = sorted({ln["name"].split("_")[0] for ln in sel})
        print("\n[%s] lines %d-%d of %d, %d run names, tag families %s" % (wave, a, b, len(lines), len(sel),
                                                                        " ".join(tags)))
        rows: list[list[str]] = []
        path = queue_path(wave, dest)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                frozen = _lf(fh.read(), path)
            same = frozen == queue_bytes(lines)
            rows.append(["frozen file " + path, "-", "-", "-",
                         ("PASS (identical, sha256 %s)" % _sha(frozen)[:16]) if same else "FAIL (DIFFERS)"])
        else:
            rows.append(["frozen file " + path, "-", "-", "-", "FAIL (not frozen: run write)"])
        rows.append(["probe " + PROBE, "-", "-", "-",
                     ("PASS (present, sha256 %s)" % _file_sha(PROBE)[:16]) if os.path.exists(PROBE)
                     else "FAIL (missing)"])
        if any(ln["name"].startswith("dqR") for ln in sel):
            rows.append(ref_checkout_row())
        trows, details = tag_check(sel, resume=resume, all_trees=all_trees)
        rows += trows
        _print_table(rows)
        ok = all(r[4].startswith("PASS") for r in rows)
        overall &= ok
        for d in details[:60]:
            print("    " + d)
        if len(details) > 60:
            print("    ... %d more" % (len(details) - 60))
        print("  => %s %s" % (wave, "PASS" if ok else "FAIL"))
        if ok:
            print("  pool: %s %s %s %s --maxpar 12 --min-free-gb 3" % (
                PY, POOL, path if (a, b) == (1, len(lines)) else "<slice of lines %d-%d>" % (a, b),
                os.path.join(OUT, "_mf2_pool_dq_%s.log" % wave)))
    print("\nOVERALL %s" % ("PASS" if overall else "FAIL"))
    return 0 if overall else 1


def show(wave: str, rng: str | None) -> int:
    lines = all_lines()[wave]
    a, b = _range(rng, len(lines))
    for i, ln in enumerate(lines[a - 1:b], start=a):
        av = ln["argv"]
        sets = [av[j + 1] for j, t in enumerate(av[:-1]) if t == "--set"]
        print("%3d %-12s seed %-7s cwd %-30s %s" % (i, ln["name"], av[av.index("--seed") + 1], ln["cwd"],
                                                   " ".join(sets)))
    return 0


def slice_(wave: str, rng: str, target: str, dest: str | None) -> int:
    _here_check()
    lines = all_lines()[wave]
    path = queue_path(wave, dest)
    if not os.path.exists(path):
        stop("%s is not frozen yet (run write)" % path)
    with open(path, "rb") as fh:
        if _lf(fh.read(), path) != queue_bytes(lines):
            stop("%s differs from the rebuilt lines" % path)
    a, b = _range(rng, len(lines))
    data = queue_bytes(lines[a - 1:b])
    if os.path.exists(target):
        with open(target, "rb") as fh:
            if _lf(fh.read(), target) != data:
                stop("%s exists and differs" % target)
        state = "unchanged"
    else:
        with open(target, "wb") as fh:
            fh.write(data)
        state = "written"
    print("%s lines %d-%d (%d) -> %s %s, sha256 %s" % (wave, a, b, b - a + 1, target, state, _sha(data)))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    dest = _opt("--dest")
    rng = _opt("--range")
    if cmd == "write":
        return write(dest)
    if cmd == "check":
        skip = {"--range", "--dest"}
        pos = [t for i, t in enumerate(sys.argv[2:], start=2) if not t.startswith("--") and sys.argv[i - 1] not in skip]
        for w in pos:
            if w not in WAVES:
                stop("unknown wave %r (waves: %s)" % (w, " ".join(WAVES)))
        return check(pos or list(WAVES), rng, "--resume" in sys.argv, "--all-trees" in sys.argv, dest)
    if cmd == "show":
        if len(sys.argv) < 3 or sys.argv[2] not in WAVES:
            stop("show needs a wave: %s" % " ".join(WAVES))
        return show(sys.argv[2], rng)
    if cmd == "slice":
        if len(sys.argv) < 5 or sys.argv[2] not in WAVES:
            stop("usage: slice WAVE A-B PATH [--dest DIR]")
        return slice_(sys.argv[2], sys.argv[3], sys.argv[4], dest)
    stop("unknown command %r" % cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
