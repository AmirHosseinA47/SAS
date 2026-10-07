"""MVG round queues and the pre-wave tag check (outputs/urgency_part1d.txt 1d.4, 1d.7, 1d.8 (9) and (11), 1d.9;
amendment 1d.13). A port of urgency:outputs/_ud_queue.py (5dba5bcb). It GENERATES QUEUES ONLY - it never starts a run.

usage (from the mvg worktree root, with E:/Projects/SAS/.venv/Scripts/python.exe):
  python outputs/_mvg_queue.py build           the seed rule check, the W1 and W2 lines, the Z0 configuration identity
                                               and the tag check; writes the FROZEN queues outputs/_mvg_q_w1.jsonl (64
                                               lines) and outputs/_mvg_q_w2.jsonl (192) (LF). A queue file that already
                                               exists must be identical (LF-normalised) to the rebuilt one, else STOP (a
                                               frozen queue is never re-frozen silently); its tag check is then not
                                               repeated (`check` does that before a launch).
  python outputs/_mvg_queue.py check <wave>    before a launch: the frozen file equals the rebuilt lines, every script
          [--resume] [--all-trees]             exists, the configuration identity holds (w1: the ud0 references; port:
                                               the ud2 references), the tag check passes; prints the pool command.
  python outputs/_mvg_queue.py show <wave>     print the wave's lines (name, seed, switches).
  python outputs/_mvg_queue.py write <wave>    Part 2d's own runs ONLY (port, smoke, structure N): write the FROZEN
                                               outputs/_mvg_q_<wave>.jsonl the same way `build` writes w1 / w2.
  python outputs/_mvg_queue.py port-verify     re-derive 1d.8 (11)'s port-identity cells from the urgency round's ud2
                                               records (outputs/ of the urgency worktree, read by exact name; only
                                               d["mv_events"]' live flags are read - no outcome) and compare with
                                               PORT_KEYS.
  waves: w1 w2 port smoke structure

RUN LINE (1d.7; CRN on; 360 steps; every path absolute; cwd = the mvg worktree):
  <py> outputs/_mvg_probe.py --crn --hazard -- --repo E:\\Projects\\SAS_wt\\mvg --scenario S --wind W --seed N
       --set GLOBAL_PLANNER_MODE=0 --set VICTIM_SPAWN_MODE=<0|1> [--set FF_APPROACH_PATH=1
       --set FF_RETREAT_KEEP_APPROACH=1] [--set FF_FIX_STRANDING_GUARD=0] --steps 360 --set BATCH_SIZE=360
       --out <absolute> --tag <tag>_<S>_<W>
  arm switches (1d.5): 0 (mvg0) none | G (mvg1) --set FF_APPROACH_PATH=1 --set FF_RETREAT_KEEP_APPROACH=1 (the guard at
  its default, 1) | N (mvg2) as G plus --set FF_FIX_STRANDING_GUARD=0.
TAGS (1d.5): mvg<a><p><k>, a = 0 / 1 / 2, p = r (VICTIM_SPAWN_MODE 0) / u (1), k = seed set; files
  outputs/_sd_<tag>_<S>_<W>.json (+ .json.argv, .json.poollog, .stdout.txt).
WAVES (1d.9, 1d.13.5):
  w1        mvg0 on sets 1-2 (64), against the urgency round's ud0 records (outputs/_mvg_ref/, W-6 (a))         64
  w2        THE SCREEN: mvg0 / mvg1 / mvg2 on sets 5-6, the three arms of each cell adjacent                    192
  port      1d.8 (11) PORT IDENTITY: mvg2 on the set-3 ring cells PORT_KEYS (the first 8 set-3/4 cells, in
            outputs/_mvg_seeds.txt order, where ud2's fixes acted; `port-verify` re-derives them), tags
            mvg2r3_<S>_<W>, compared with outputs/_mvg_ref/_sd_ud2r3_<S>_<W>.json                               8
  smoke     1d.8 (9): set 1 ring A_N and set 1 uniform A_N x the three arms, tags mvgs<a><p>1_A_N (neither cell
            holds a recorded death, urgency Part 1 3.1)                                                           6
  structure 1d.8 (9) STRUCTURE CHECK candidates: mvg1 on set-1/2 cells in the order of outputs/_mvg_seeds.txt (set 1
            ring, set 1 uniform, set 2 ring, set 2 uniform; rows in the file's order), skipping the 12 recorded-death
            cells and the two smoke cells, tags mvgs1<p><k>_<S>_<W>; `write structure N` freezes the first N (N <= 16)
  The W3 queue (the per-death attribution, 1d.13.2) is written by outputs/_mvg_w3_queue.py from the W2 records.
SEEDS: outputs/_mvg_seeds.txt, the rule seed = base + 4*s + w (s A0 B1 C2 D3, w N0 S1 E2 W3; bases 9601 / 9621 /
  573001 / 780001 / 135961 / 287041) is RECOMPUTED and any mismatch STOPS; sets 1-4 must also equal the urgency round's
  frozen outputs/_ud_seeds.txt at 5dba5bcb (1d.4). It never scans for seeds.
TAG CHECK: refuses when any target output exists (with --resume: only the wave's own untracked outputs, each with its
  pool .argv); lists and refuses every file whose name starts with a wave tag (patterns _sd_<t>_, _ffr_<t>_,
  _ffr_rb_<t>, _rblatch_camp2_<t>_, <t>_, and _bd_<t>_ for the W3 replays' boards files) in this worktree's outputs/,
  outputs/_ffr_logs/ and outputs/_mvg_w3/
  (top-level listings, never a walk), in `git ls-files` of this worktree, and in every local branch's outputs/ (git
  ls-tree, one level). --all-trees adds a top-level listing of every worktree's outputs/ ("all trees, tracked and
  untracked"); the quarantine directory is never listed.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import subprocess
import sys

WT = r"E:\Projects\SAS_wt\mvg"
OUT = os.path.join(WT, "outputs")
PROBE = os.path.join(OUT, "_mvg_probe.py")
SEEDS = os.path.join(OUT, "_mvg_seeds.txt")
POOL = os.path.join(OUT, "_mf2_pool.py")
REF_DIR = os.path.join(OUT, "_mvg_ref")
W3_DIR = os.path.join(OUT, "_mvg_w3")
URGENCY_WT = r"E:\Projects\SAS_wt\urgency"
URGENCY_CODE = "5dba5bcb"                      # the urgency round's code commit: its frozen _ud_seeds.txt
QUARANTINE_NAME = "_firemech_rewound_20260914"

EXPECTED_BASES = {"set1": 9601, "set2": 9621, "set3": 573001, "set4": 780001, "set5": 135961, "set6": 287041}
SCENARIOS = "ABCD"
WINDS = (("N", "north"), ("S", "south"), ("E", "east"), ("W", "west"))
PLACEMENTS = (("r", 0), ("u", 1))
G_SWITCHES = ["--set", "FF_APPROACH_PATH=1", "--set", "FF_RETREAT_KEEP_APPROACH=1"]
GUARD_OFF = ["--set", "FF_FIX_STRANDING_GUARD=0"]
ARMS = {0: [], 1: G_SWITCHES, 2: G_SWITCHES + GUARD_OFF}
# urgency_part1.txt 3.1: the cells holding the 13 recorded deaths (set, placement, key) -> seed (12 cells). The smoke and
# the structure check avoid them (1d.8 (9)).
DEATH_CELLS = {(1, "r", "B_N"): 9605, (1, "r", "B_S"): 9606, (1, "r", "B_W"): 9608, (1, "u", "B_E"): 9607,
               (1, "u", "C_E"): 9611, (2, "r", "B_N"): 9625, (2, "r", "B_S"): 9626, (2, "r", "B_W"): 9628,
               (2, "r", "D_N"): 9633, (2, "r", "D_W"): 9636, (2, "u", "A_N"): 9621, (2, "u", "D_N"): 9633}
SMOKE_CELLS = ((1, "r", "A_N"), (1, "u", "A_N"))
# 1d.8 (11): the first 8 set-3/4 cells, in outputs/_mvg_seeds.txt order (set 3 ring, set 3 uniform, set 4 ring, set 4
# uniform; rows in the file's order), where ud2's fixes acted - all eight are set-3 ring cells (port-verify)
PORT_KEYS = ("A_N", "A_W", "B_S", "B_W", "C_N", "C_S", "C_W", "D_N")
STRUCTURE_MAX = 16
WAVES = ("w1", "w2", "port", "smoke", "structure")
EXPECTED_COUNTS = {"w1": 64, "w2": 192, "port": 8, "smoke": 6}
_PATTERNS = ("_sd_{t}_", "_ffr_{t}_", "_ffr_rb_{t}", "_rblatch_camp2_{t}_", "{t}_", "_bd_{t}_")


def stop(msg: str) -> None:
    raise SystemExit("STOP: " + msg)


def _here_check() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.normcase(os.path.realpath(here)) != os.path.normcase(os.path.realpath(OUT)):
        stop("this script must live in %s (it is in %s): the queue paths are absolute" % (OUT, here))


def _git(args: list[str], cwd: str = WT, check: bool = True) -> bytes:
    proc = subprocess.run(["git", "-C", cwd, *args], capture_output=True)
    if check and proc.returncode != 0:
        stop("git %s failed (rc %d): %s" % (" ".join(args), proc.returncode,
                                            proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout


def _lf(data: bytes, what: str) -> bytes:
    """core.autocrlf is true on this machine: a fresh checkout turns the LF files written here into CRLF. Every
    file this script writes is LF (no blob holds a CR), so the content is compared LF-normalised, with a note."""
    if b"\r\n" in data:
        print("note: %s is CRLF on disk (git eol conversion); compared LF-normalised" % what)
        return data.replace(b"\r\n", b"\n")
    return data


def _rel(path: str) -> str:
    try:
        return os.path.relpath(path, WT).replace(os.sep, "/")
    except ValueError:  # another drive
        return path


# ----------------------------------------------------------------------------------------------------------- seeds
@functools.lru_cache(maxsize=None)
def seeds() -> dict[int, list[tuple[str, str, str, str]]]:
    """outputs/_mvg_seeds.txt with the rule recomputed for sets 1-6; STOP on any mismatch. Sets 1-4 must equal the
    urgency round's frozen outputs/_ud_seeds.txt at 5dba5bcb (1d.4). Never scans for seeds."""
    with open(SEEDS, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("bases") != EXPECTED_BASES:
        stop("_mvg_seeds.txt bases %r != 1d.4's %r" % (doc.get("bases"), EXPECTED_BASES))
    extra = sorted(k for k in doc if k.startswith("set") and k not in EXPECTED_BASES)
    if extra:
        stop("_mvg_seeds.txt holds unknown sets %s" % extra)
    out: dict[int, list[tuple[str, str, str, str]]] = {}
    seen: dict[str, str] = {}
    for name, base in EXPECTED_BASES.items():
        rows = doc.get(name)
        expect = []
        for s, scen in enumerate(SCENARIOS):
            for w, (wk, wind) in enumerate(WINDS):
                expect.append(["%s_%s" % (scen, wk), scen, wind, str(base + 4 * s + w)])
        expect.sort(key=lambda r: r[0])
        if rows != expect:
            stop("_mvg_seeds.txt %s does not follow the rule seed = %d + 4*s + w (rows sorted by key)" % (name, base))
        for row in rows:
            if row[3] in seen:
                stop("seed %s appears in %s and %s" % (row[3], seen[row[3]], name))
            seen[row[3]] = name
        out[int(name[3:])] = [tuple(r) for r in rows]
    ud = json.loads(_git(["show", "%s:outputs/_ud_seeds.txt" % URGENCY_CODE]).decode("utf-8"))
    for k in (1, 2, 3, 4):
        if [tuple(r) for r in ud["set%d" % k]] != out[k]:
            stop("set %d differs from urgency:outputs/_ud_seeds.txt at %s" % (k, URGENCY_CODE))
    for (k, _p, key), seed in DEATH_CELLS.items():
        if dict((r[0], r[3]) for r in out[k])[key] != str(seed):
            stop("3.1 death cell s%d %s is not seed %d" % (k, key, seed))
    return out


# ----------------------------------------------------------------------------------------------------------- lines
def probe_line(tag: str, key: str, scen: str, wind: str, seed: str, sets: list[str]) -> dict:
    out = os.path.join(OUT, "_sd_%s_%s.json" % (tag, key))
    argv = [PROBE, "--crn", "--hazard", "--", "--repo", WT, "--scenario", scen, "--wind", wind, "--seed", str(seed)]
    argv += list(sets)
    argv += ["--steps", "360", "--set", "BATCH_SIZE=360", "--out", out, "--tag", "%s_%s" % (tag, key)]
    return {"name": "%s_%s" % (tag, key), "argv": argv, "out": out, "cwd": WT}


def arm_sets(arm: int, mode: int) -> list[str]:
    return ["--set", "GLOBAL_PLANNER_MODE=0", "--set", "VICTIM_SPAWN_MODE=%d" % mode] + ARMS[arm]


def screen(arms: tuple[int, ...], sets: tuple[int, ...], prefix: str = "mvg",
           cells: tuple[tuple[int, str, str], ...] | None = None) -> list[dict]:
    """set -> placement -> cell -> arm: the arms of one cell are adjacent (1d.9)."""
    table = seeds()
    lines = []
    for k in sets:
        for p, mode in PLACEMENTS:
            for key, scen, wind, seed in table[k]:
                if cells is not None and (k, p, key) not in cells:
                    continue
                for a in arms:
                    lines.append(probe_line("%s%d%s%d" % (prefix, a, p, k), key, scen, wind, seed, arm_sets(a, mode)))
    return lines


def structure_lines() -> list[dict]:
    """1d.8 (9) STRUCTURE CHECK candidates, in order: mvg1 on set 1 ring, set 1 uniform, set 2 ring, set 2 uniform
    (rows in outputs/_mvg_seeds.txt order), skipping the 12 recorded-death cells and the two smoke cells; at most 16."""
    table = seeds()
    lines = []
    for k in (1, 2):
        for p, mode in PLACEMENTS:
            for key, scen, wind, seed in table[k]:
                if (k, p, key) in DEATH_CELLS or (k, p, key) in SMOKE_CELLS:
                    continue
                lines.append(probe_line("mvgs1%s%d" % (p, k), key, scen, wind, seed, arm_sets(1, mode)))
    return lines[:STRUCTURE_MAX]


def wave_lines(wave: str, n: int | None = None) -> list[dict]:
    if wave == "w1":
        return screen((0,), (1, 2))
    if wave == "w2":
        return screen((0, 1, 2), (5, 6))
    if wave == "port":
        return screen((2,), (3,), cells=tuple((3, "r", k) for k in PORT_KEYS))
    if wave == "smoke":
        for cell in SMOKE_CELLS:
            if cell in DEATH_CELLS:
                stop("smoke cell %r holds a recorded death (3.1)" % (cell,))
        return screen((0, 1, 2), (1,), prefix="mvgs", cells=SMOKE_CELLS)
    if wave == "structure":
        lines = structure_lines()
        return lines if n is None else lines[:n]
    stop("unknown wave %r (waves: %s)" % (wave, " ".join(WAVES)))
    return []


def queue_path(wave: str) -> str:
    return os.path.join(OUT, "_mvg_q_%s.jsonl" % wave)


def queue_bytes(lines: list[dict]) -> bytes:
    return "".join(json.dumps(line) + "\n" for line in lines).encode("utf-8")


def ref_reference(name: str) -> tuple[str, str] | None:
    """A W1 line (mvg0 on sets 1-2) or a smoke arm-0 line -> (the ud0 reference record's basename in
    outputs/_mvg_ref/, 'ud0'); a port line -> (the ud2r3 reference, 'ud2'); else None."""
    m = re.match(r"^mvg(s?)0([ru])([12])_([A-D]_[NSEW])$", name)
    if m:
        return "_sd_ud0%s%s_%s.json" % (m.group(2), m.group(3), m.group(4)), "ud0"
    m = re.match(r"^mvg2r3_([A-D]_[NSEW])$", name)
    if m:
        return "_sd_ud2r3_%s.json" % m.group(1), "ud2"
    return None


def config_identity(lines: list[dict]) -> int:
    """Each W1 / smoke arm-0 line equals its ud0 reference record's argv (outputs/_mvg_ref/<ref>.json.argv), and each
    port line its ud2r3 reference's argv with FF_CARRY_REPLAN=1 replaced by FF_FIX_STRANDING_GUARD=0 (the guard off:
    arm N); only the probe path (_ud_probe.py -> _mvg_probe.py), --repo, --out, --tag and cwd change."""
    n = 0
    for line in lines:
        ref = ref_reference(line["name"])
        if ref is None:
            continue
        base, kind = ref
        with open(os.path.join(REF_DIR, base + ".argv"), encoding="utf-8") as fh:
            rec = json.load(fh)
        argv = list(rec["argv"])
        old_tag = argv[argv.index("--tag") + 1]
        new_tag = line["argv"][line["argv"].index("--tag") + 1]
        if os.path.basename(argv[0]) != "_ud_probe.py":
            stop("config identity: %s's reference %s was not run by _ud_probe.py" % (line["name"], base))
        mapped = [PROBE]
        for i in range(1, len(argv)):
            prev, tok = argv[i - 1], argv[i]
            if prev == "--repo":
                tok = WT
            elif prev == "--out":
                tok = line["out"]
            elif prev == "--tag":
                tok = new_tag
            elif prev == "--set" and kind == "ud2" and tok == "FF_CARRY_REPLAN=1":
                tok = "FF_FIX_STRANDING_GUARD=0"
            mapped.append(tok)
        if mapped != line["argv"] or not old_tag.startswith(kind) or rec.get("cwd") != URGENCY_WT:
            stop("configuration identity: %s differs from its reference %s" % (line["name"], base))
        n += 1
    return n


# ------------------------------------------------------------------------------------------------------- tag check
def _tag_of(name: str) -> str:
    return name.split("_")[0]


def _tracked_here() -> list[str]:
    return [p for p in _git(["ls-files", "--", "outputs/"]).decode("utf-8", "replace").splitlines() if p]


def _branch_outputs() -> list[tuple[str, str]]:
    """(branch, outputs/<entry>) for every local branch: one level of outputs/ (git ls-tree, no -r)."""
    rows = []
    for ref in _git(["for-each-ref", "--format=%(refname)", "refs/heads"]).decode().split():
        for p in _git(["ls-tree", "--name-only", ref, "--", "outputs/"]).decode("utf-8", "replace").splitlines():
            rows.append((ref, p))
    return rows


def _worktrees() -> list[str]:
    out = []
    for row in _git(["worktree", "list", "--porcelain"]).decode("utf-8", "replace").splitlines():
        if row.startswith("worktree "):
            out.append(os.path.normpath(row[len("worktree "):]))
    return out


def _listing(folder: str) -> list[str]:
    """Names in ONE folder (os.listdir, never a walk); never lists the quarantine directory itself."""
    if os.path.basename(os.path.normpath(folder)) == QUARANTINE_NAME or not os.path.isdir(folder):
        return []
    return os.listdir(folder)


def tag_check(lines: list[dict], resume: bool = False, all_trees: bool = False) -> list[str]:
    """The pre-wave tag check (1d.9 / 16.12: tags re-checked unused before each wave). A line's own outputs are its
    out, .argv, .poollog, stdout and (a W3 replay line) its --boards file."""
    tags = sorted({_tag_of(line["name"]) for line in lines})
    own: set[str] = set()
    bad: list[str] = []
    tracked_rel = _tracked_here()
    tracked = {os.path.normcase(os.path.join(WT, p.replace("/", os.sep))) for p in tracked_rel}
    for line in lines:
        base = line["out"]
        stem = base[:-5] if base.endswith(".json") else base
        paths = [base, base + ".argv", base + ".poollog", stem + ".stdout.txt", base + ".stdout.txt"]
        if "--boards" in line["argv"]:
            paths.append(line["argv"][line["argv"].index("--boards") + 1])
        own.update(os.path.normcase(p) for p in paths)
        for path in paths:
            if not os.path.exists(path):
                continue
            is_tracked = os.path.normcase(path) in tracked
            if is_tracked or not resume:
                bad.append(("TRACKED " if is_tracked else "EXISTS ") + path)
        if resume and os.path.exists(base) and not os.path.exists(base + ".argv"):
            bad.append("CRASHED OR PARTIAL RECORD (no .argv: copy it aside before re-queuing) " + base)

    def hit(name: str) -> bool:
        return any(name.startswith(pat.format(t=t)) for t in tags for pat in _PATTERNS)

    folders = [OUT, os.path.join(OUT, "_ffr_logs"), W3_DIR]
    if all_trees:
        for wt in _worktrees():
            folders += [os.path.join(wt, "outputs"), os.path.join(wt, "outputs", "_ffr_logs")]
    done = set()
    for folder in folders:
        key = os.path.normcase(os.path.normpath(folder))
        if key in done:
            continue
        done.add(key)
        for name in _listing(folder):
            if not hit(name):
                continue
            path = os.path.join(folder, name)
            if os.path.normcase(path) in own:
                continue
            bad.append(("TRACKED " if os.path.normcase(path) in tracked else "TAG IN USE ") + path)
    for rel in tracked_rel:
        if hit(rel.rsplit("/", 1)[-1]):
            bad.append("TRACKED (git ls-files) " + rel)
    for ref, rel in _branch_outputs():
        if hit(rel.rsplit("/", 1)[-1]):
            bad.append("TRACKED IN %s %s" % (ref, rel))
    return sorted(set(bad))


# --------------------------------------------------------------------------------------------------- port-verify
def port_verify() -> int:
    """1d.8 (11)'s selection re-derived: the urgency round's ud2 records of sets 3-4 in outputs/_mvg_seeds.txt order
    (set 3 ring, set 3 uniform, set 4 ring, set 4 uniform; rows in the file's order), the first 8 cells with a LIVE
    fix (a) / (b) ACTED event (d["mv_events"]; nothing else is read). Prints the list and whether it is PORT_KEYS."""
    table = seeds()
    chosen = []
    for k in (3, 4):
        for p, _mode in PLACEMENTS:
            for key, *_ in table[k]:
                if len(chosen) == 8:
                    break
                path = os.path.join(URGENCY_WT, "outputs", "_sd_ud2%s%d_%s.json" % (p, k, key))
                with open(path, encoding="utf-8") as fh:
                    d = json.load(fh)
                if any(e.get("live") and e.get("kind") in ("a", "b") for e in d.get("mv_events") or []):
                    chosen.append((k, p, key))
                d = None
    want = [(3, "r", key) for key in PORT_KEYS]
    print("port identity cells re-derived: %s" % ["s%d%s_%s" % c for c in chosen])
    print("PORT_KEYS (set 3 ring): %s => %s" % (list(PORT_KEYS), "IDENTICAL" if chosen == want else "DIFFERENT"))
    return 0 if chosen == want else 1


# ------------------------------------------------------------------------------------------------------------ main
def _freeze(wave: str, lines: list[dict]) -> str:
    data = queue_bytes(lines)
    path = queue_path(wave)
    if os.path.exists(path):
        with open(path, "rb") as fh:
            if _lf(fh.read(), _rel(path)) != data:
                stop("%s exists and differs from the rebuilt lines (frozen; never re-written)" % path)
        state = "unchanged (frozen)"
    else:
        bad = tag_check(lines)
        if bad:
            stop("TAG CHECK FAILED:\n  " + "\n  ".join(bad[:60]))
        with open(path, "wb") as fh:
            fh.write(data)
        state = "written"
    print("%-9s %3d lines  sha256 %s  %s  %s" % (wave, len(lines), hashlib.sha256(data).hexdigest()[:16], _rel(path),
                                                state))
    return state


def build() -> int:
    _here_check()
    per = {}
    for wave in ("w1", "w2"):
        lines = wave_lines(wave)
        if len(lines) != EXPECTED_COUNTS[wave]:
            stop("%s: %d lines, expected %d" % (wave, len(lines), EXPECTED_COUNTS[wave]))
        per[wave] = lines
    every = per["w1"] + per["w2"] + wave_lines("port") + wave_lines("smoke") + structure_lines()
    names = [ln["name"] for ln in every]
    outs = [os.path.normcase(ln["out"]) for ln in every]
    if len(set(names)) != len(names) or len(set(outs)) != len(outs):
        stop("duplicate line names or outputs across the waves")
    n = config_identity(per["w1"])
    print("Z0 configuration identity: %d W1 lines equal their ud0 reference's argv (probe, --repo, --out, --tag, cwd "
          "changed)" % n)
    if n != 64:
        stop("Z0 configuration identity: %d of 64 W1 lines checked" % n)
    for wave in ("w1", "w2"):
        _freeze(wave, per[wave])
    print("total %d lines (w1 %d, w2 %d)" % (len(per["w1"]) + len(per["w2"]), len(per["w1"]), len(per["w2"])))
    return 0


def write(wave: str, n: int | None) -> int:
    _here_check()
    if wave not in ("port", "smoke", "structure"):
        stop("write is for Part 2d's own runs (port, smoke, structure); w1 / w2 are written by build")
    lines = wave_lines(wave, n)
    if wave in EXPECTED_COUNTS and len(lines) != EXPECTED_COUNTS[wave]:
        stop("%s: %d lines, expected %d" % (wave, len(lines), EXPECTED_COUNTS[wave]))
    if wave == "structure" and not lines:
        stop("structure: give N, 1 <= N <= %d" % STRUCTURE_MAX)
    if wave in ("port", "smoke"):
        print("configuration identity: %d lines" % config_identity(lines))
    _freeze(wave, lines)
    return 0


def check(wave: str, resume: bool, all_trees: bool) -> int:
    _here_check()
    path = queue_path(wave)
    if not os.path.exists(path):
        stop("%s is not frozen yet (run build / write)" % path)
    with open(path, "rb") as fh:
        frozen = _lf(fh.read(), _rel(path))
    n = None
    if wave == "structure":
        n = frozen.count(b"\n")
    lines = wave_lines(wave, n)
    if frozen != queue_bytes(lines):
        stop("%s differs from the rebuilt lines" % path)
    for script in sorted({ln["argv"][0] for ln in lines}):
        if not os.path.exists(script):
            stop("script missing: %s" % script)
    if wave in ("w1", "port", "smoke"):
        print("configuration identity: %d lines" % config_identity(lines))
    bad = tag_check(lines, resume=resume, all_trees=all_trees)
    if bad:
        stop("TAG CHECK FAILED:\n  " + "\n  ".join(bad[:60]))
    print("%s: %d lines, frozen file identical, scripts present, tags unused%s" % (
        wave, len(lines), " (all trees)" if all_trees else ""))
    print("pool: <py> %s %s %s --maxpar 12 --min-free-gb 3" % (
        POOL, path, os.path.join(OUT, "_mf2_pool_mvg_%s.log" % wave)))
    return 0


def show(wave: str, n: int | None) -> int:
    for ln in wave_lines(wave, n):
        a = ln["argv"]
        seed = a[a.index("--seed") + 1]
        sets = [a[i + 1] for i, t in enumerate(a[:-1]) if t == "--set"]
        print("%-16s seed %-7s %s  %s" % (ln["name"], seed, os.path.basename(a[0]), " ".join(sets)))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "build":
        return build()
    if cmd == "port-verify":
        return port_verify()
    if cmd in ("check", "show", "write"):
        if len(sys.argv) < 3 or sys.argv[2] not in WAVES:
            stop("%s needs a wave: %s" % (cmd, " ".join(WAVES)))
        wave = sys.argv[2]
        n = None
        if wave == "structure" and cmd in ("show", "write"):
            n = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else (None if cmd == "show" else 0)
            if n is not None and not 0 <= n <= STRUCTURE_MAX:
                stop("structure N must be 1..%d" % STRUCTURE_MAX)
        if cmd == "show":
            return show(wave, n)
        if cmd == "write":
            return write(wave, n)
        return check(wave, "--resume" in sys.argv, "--all-trees" in sys.argv)
    stop("unknown command %r" % cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
