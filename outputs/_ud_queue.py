"""Urgency round queues, reference copies and the pre-wave tag check (outputs/urgency_part1.txt 15.5, 16.1-16.4,
16.11, 16.12, 22.6.3, 22.7). A port of dispatch:outputs/_dp_queue.py. It GENERATES QUEUES ONLY - it never starts a
run.

usage (from the urgency worktree root, with the urgency .venv python):
  python outputs/_ud_queue.py build            the seed rule check, every wave's lines, the tag check; writes the
                                               FROZEN queues outputs/_ud_q_{w1,w2,w3,w4,smoke}.jsonl (LF). A queue
                                               file that already exists must be byte-identical to the rebuilt one,
                                               else STOP (a frozen queue is never re-frozen silently).
  python outputs/_ud_queue.py check <wave>     before a launch: the frozen file equals the rebuilt lines, every
          [--resume] [--all-trees]             script exists, the Z0 configuration identity holds (w1, smoke: needs
                                               `refs`), the tag check passes; prints the pool command.
  python outputs/_ud_queue.py refs             copy the dispatch round's records - dpR (64 runs) and the 11 dpE OFF
                                               runs - from branch dispatch at cc8d653c with `git show` (bytes, never
                                               a text redirect) into outputs/_ud_dpR/ and outputs/_ud_dpE/; writes
                                               outputs/_ud_dpR_sha256.txt; verifies every copy against its git blob.
  python outputs/_ud_queue.py verify-refs      re-verify every copy: the sha256 file, the git blob, no extra file.
  python outputs/_ud_queue.py show <wave>      print the wave's lines (name, seed, switches).
  waves: w1 w2 w3 w4 smoke

RUN LINE (16.4; 22.7 adds the arm switches):
  <py> outputs/_ud_probe.py --crn --hazard -- --repo E:\\Projects\\SAS_wt\\urgency --scenario S --wind W --seed N
       --set GLOBAL_PLANNER_MODE=0 --set VICTIM_SPAWN_MODE=<0|1> [arm switches] --steps 360 --set BATCH_SIZE=360
       --out <absolute> --tag <tag>_<S>_<W>
  arm switches: 0 none | 1 --set DISPATCH_URGENCY=1 | 2 --set FF_APPROACH_PATH=1 --set FF_RETREAT_KEEP_APPROACH=1
  --set FF_CARRY_REPLAN=1 | 3 = 1 then 2. Every path is absolute, cwd = the urgency worktree.
TAGS (22.7): ud<a><p><k>, a = arm 0-3, p = r (VICTIM_SPAWN_MODE 0) / u (1), k = seed set 1-4; files
  outputs/_sd_<tag>_<S>_<W>.json (+ .json.argv, .json.poollog, .stdout.txt). Smoke: uds<a><p><k>.
  Evidence (16.11): udE<case><0|1><c|n> (case 1 = the harness, files _ffr_<tag>_D_south_half_505.json).
WAVES (22.7, 16.12):
  w1    ud0 on sets 1-2 (64) + the 11 dispatch-round evidence OFF lines, re-tagged udE<case>0<c|n>        75
  w2    THE SCREEN: ud0 / ud1 / ud2 / ud3 on sets 3-4, the four arms of each cell adjacent              256
  w3    ud1 on sets 1-2                                                                                  64
  w4    the 11 evidence ON lines (udE<case>1<c|n>; --set DISPATCH_URGENCY=1 replaces the dispatch pair)   11
  smoke 2 cells x 4 arms on set 1 ring A_N and set 1 uniform A_N (none of 3.1's 13 deaths); its arm-0 runs
        (uds0r1_A_N, uds0u1_A_N) are the Z0 smoke against dpRr_A_N / dpRu_A_N (dpr_reference())          8
SEEDS: outputs/_ud_seeds.txt, the rule seed = base + 4*s + w (s A0 B1 C2 D3, w N0 S1 E2 W3; bases 9601 / 9621 /
  573001 / 780001) is RECOMPUTED and any mismatch STOPS; sets 1-2 must also equal dispatch's _dp_seeds.txt at
  cc8d653c. It never scans for seeds.
TAG CHECK: refuses when any target output exists (with --resume: only the wave's own untracked outputs, each with
  its pool .argv); lists and refuses every file whose name starts with a wave tag (patterns _sd_<t>_, _ffr_<t>_,
  _ffr_rb_<t>, _rblatch_camp2_<t>_, <t>_) in this worktree's outputs/ and outputs/_ffr_logs/ (top-level listings,
  never a walk), in `git ls-files` of this worktree, and in every local branch's outputs/ (git ls-tree, one level).
  --all-trees adds a top-level listing of every worktree's outputs/ (16.12: "all trees, tracked and untracked").
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import subprocess
import sys

WT = r"E:\Projects\SAS_wt\urgency"
OUT = os.path.join(WT, "outputs")
PROBE = os.path.join(OUT, "_ud_probe.py")
SEEDS = os.path.join(OUT, "_ud_seeds.txt")
POOL = os.path.join(OUT, "_mf2_pool.py")
DISPATCH_WT = r"E:\Projects\SAS_wt\dispatch"
DISPATCH_OUT = os.path.join(DISPATCH_WT, "outputs")
DISPATCH_COMMIT = "cc8d653c4a5740c0f04a9e94d6ff48e92a0ca027"
DPR_DIR = os.path.join(OUT, "_ud_dpR")
DPE_DIR = os.path.join(OUT, "_ud_dpE")
SHA_FILE = os.path.join(OUT, "_ud_dpR_sha256.txt")
QUARANTINE_NAME = "_firemech_rewound_20260914"

EXPECTED_BASES = {"set1": 9601, "set2": 9621, "set3": 573001, "set4": 780001}
SCENARIOS = "ABCD"
WINDS = (("N", "north"), ("S", "south"), ("E", "east"), ("W", "west"))
PLACEMENTS = (("r", 0), ("u", 1))
U_SWITCH = ["--set", "DISPATCH_URGENCY=1"]
M_SWITCHES = ["--set", "FF_APPROACH_PATH=1", "--set", "FF_RETREAT_KEEP_APPROACH=1", "--set", "FF_CARRY_REPLAN=1"]
ARMS = {0: [], 1: U_SWITCH, 2: M_SWITCHES, 3: U_SWITCH + M_SWITCHES}
DISPATCH_ON_PAIR = ["--set", "DISPATCH_JOINT=1", "--set", "DISPATCH_REASSIGN=1"]
DPR_TAGS = {(1, "r"): "dpRr", (2, "r"): "dpRr2", (1, "u"): "dpRu", (2, "u"): "dpRu2"}
# urgency_part1.txt 3.1: the cells holding the 13 recorded deaths (set, placement, key) -> seed. No movement fix
# runs on any of them (22.7); the smoke must avoid them (22.6.3).
DEATH_CELLS = {(1, "r", "B_N"): 9605, (1, "r", "B_S"): 9606, (1, "r", "B_W"): 9608, (1, "u", "B_E"): 9607,
               (1, "u", "C_E"): 9611, (2, "r", "B_N"): 9625, (2, "r", "B_S"): 9626, (2, "r", "B_W"): 9628,
               (2, "r", "D_N"): 9633, (2, "r", "D_W"): 9636, (2, "u", "A_N"): 9621, (2, "u", "D_N"): 9633}
SMOKE_CELLS = ((1, "r", "A_N"), (1, "u", "A_N"))
EVIDENCE_CASES = ("1", "2", "2f", "x", "3", "4d", "4g")
_EVID_RE = re.compile(r"^dpE(1|2f|2|x|3|4d|4g)([01])([cn])(?:_([A-D]_[NSEW]))?$")
WAVES = ("w1", "w2", "w3", "w4", "smoke")
_PATTERNS = ("_sd_{t}_", "_ffr_{t}_", "_ffr_rb_{t}", "_rblatch_camp2_{t}_", "{t}_")


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


def _dispatch_commit() -> str:
    got = _git(["rev-parse", "--verify", DISPATCH_COMMIT[:8] + "^{commit}"], cwd=DISPATCH_WT).decode().strip()
    if got != DISPATCH_COMMIT:
        stop("cc8d653c resolves to %s, expected %s" % (got, DISPATCH_COMMIT))
    return got


def _dispatch_blob(rel: str) -> bytes:
    """The bytes of dispatch:<rel> at cc8d653c, through `git show`, checked equal to `git cat-file blob`."""
    data = _git(["show", "%s:%s" % (DISPATCH_COMMIT, rel)], cwd=DISPATCH_WT)
    oid = _git(["rev-parse", "%s:%s" % (DISPATCH_COMMIT, rel)], cwd=DISPATCH_WT).decode().strip()
    raw = _git(["cat-file", "blob", oid], cwd=DISPATCH_WT)
    if data != raw or _blob_oid(data) != oid:
        stop("git show of %s is not the raw blob %s" % (rel, oid))
    return data


def _blob_oid(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _lf(data: bytes, what: str) -> bytes:
    """core.autocrlf is true on this machine: a fresh checkout turns the LF files written here into CRLF. Every
    file this script writes is LF (no blob holds a CR), so the content is compared LF-normalised, with a note."""
    if b"\r\n" in data:
        print("note: %s is CRLF on disk (git eol conversion); compared LF-normalised" % what)
        return data.replace(b"\r\n", b"\n")
    return data


# ----------------------------------------------------------------------------------------------------------- seeds
@functools.lru_cache(maxsize=None)
def seeds() -> dict[int, list[tuple[str, str, str, str]]]:
    """outputs/_ud_seeds.txt with the rule recomputed; STOP on any mismatch. Never scans for seeds."""
    with open(SEEDS, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("bases") != EXPECTED_BASES:
        stop("_ud_seeds.txt bases %r != 16.2's %r" % (doc.get("bases"), EXPECTED_BASES))
    extra = sorted(k for k in doc if k.startswith("set") and k not in EXPECTED_BASES)
    if extra:
        stop("_ud_seeds.txt holds unknown sets %s" % extra)
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
            stop("_ud_seeds.txt %s does not follow the rule seed = %d + 4*s + w (rows sorted by key)" % (name, base))
        for row in rows:
            if row[3] in seen:
                stop("seed %s appears in %s and %s" % (row[3], seen[row[3]], name))
            seen[row[3]] = name
        out[int(name[3:])] = [tuple(r) for r in rows]
    dp = json.loads(_dispatch_blob("outputs/_dp_seeds.txt").decode("utf-8"))
    for k in (1, 2):
        if [tuple(r) for r in dp["set%d" % k]] != out[k]:
            stop("set %d differs from dispatch:outputs/_dp_seeds.txt at cc8d653c" % k)
    for (k, _p, key), seed in DEATH_CELLS.items():
        if dict((r[0], r[3]) for r in out[k])[key] != str(seed):
            stop("3.1 death cell s%d %s is not seed %d" % (k, key, seed))
    return out


# ----------------------------------------------------------------------------------------------------------- lines
def probe_line(tag: str, key: str, scen: str, wind: str, seed: str, sets: list[str],
               own: tuple[str, ...] = ("--crn", "--hazard")) -> dict:
    out = os.path.join(OUT, "_sd_%s_%s.json" % (tag, key))
    argv = [PROBE, *own, "--", "--repo", WT, "--scenario", scen, "--wind", wind, "--seed", str(seed)]
    argv += list(sets)
    argv += ["--steps", "360", "--set", "BATCH_SIZE=360", "--out", out, "--tag", "%s_%s" % (tag, key)]
    return {"name": "%s_%s" % (tag, key), "argv": argv, "out": out, "cwd": WT}


def arm_sets(arm: int, mode: int) -> list[str]:
    return ["--set", "GLOBAL_PLANNER_MODE=0", "--set", "VICTIM_SPAWN_MODE=%d" % mode] + ARMS[arm]


def screen(arms: tuple[int, ...], sets: tuple[int, ...], prefix: str = "ud",
           cells: tuple[tuple[int, str, str], ...] | None = None) -> list[dict]:
    """set -> placement -> cell -> arm: the arms of one cell are adjacent (22.7)."""
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


@functools.lru_cache(maxsize=None)
def _dispatch_evidence() -> list[dict]:
    """dispatch:outputs/_dp_q_evidence.jsonl at cc8d653c (22 lines); the dispatch worktree's file must agree.
    Cached: callers never mutate the returned lines."""
    blob = _dispatch_blob("outputs/_dp_q_evidence.jsonl")
    lines = [json.loads(x) for x in blob.decode("utf-8").splitlines() if x.strip()]
    disk = os.path.join(DISPATCH_OUT, "_dp_q_evidence.jsonl")
    if os.path.exists(disk):
        with open(disk, encoding="utf-8") as fh:
            if [json.loads(x) for x in fh if x.strip()] != lines:
                stop("the dispatch worktree's _dp_q_evidence.jsonl differs from cc8d653c's")
    if len(lines) != 22:
        stop("dispatch evidence queue has %d lines, 16.11 says 22" % len(lines))
    return lines


def _retag_evidence(line: dict) -> tuple[str, str, dict]:
    """One dispatch evidence line -> (case, arm, urgency line). Only the script's folder, --repo, --out, --tag, cwd
    and (ON) the switch change (16.11)."""
    m = _EVID_RE.match(line["name"])
    if not m:
        stop("unexpected evidence line name %r" % line["name"])
    case, arm, crn, key = m.groups()
    old_tag = "dpE%s%s%s" % (case, arm, crn)
    new_tag = "udE%s%s%s" % (case, arm, crn)
    if os.path.normcase(line.get("cwd") or "") != os.path.normcase(DISPATCH_WT):
        stop("%s: cwd %r is not the dispatch worktree" % (line["name"], line.get("cwd")))
    argv = list(line["argv"])
    script = os.path.basename(argv[0])
    if os.path.normcase(os.path.dirname(argv[0])) != os.path.normcase(DISPATCH_OUT):
        stop("%s: script %r is not in dispatch outputs/" % (line["name"], argv[0]))
    if script == "_dp_probe.py":
        if key is None:
            stop("%s: a probe line without a cell key" % line["name"])
        argv[0] = PROBE
    elif script in ("_ffr_harness.py", "_fm2_probe_harness.py"):
        if key is not None or case != "1":
            stop("%s: a harness line outside case 1" % line["name"])
        argv[0] = os.path.join(OUT, script)
    else:
        stop("%s: unknown script %r" % (line["name"], script))
    seen = set()
    for i, tok in enumerate(argv[:-1]):
        val = argv[i + 1]
        if tok == "--repo":
            if os.path.normcase(val) != os.path.normcase(DISPATCH_WT):
                stop("%s: --repo %r" % (line["name"], val))
            argv[i + 1] = WT
        elif tok == "--out":
            base = os.path.basename(val)
            if os.path.normcase(os.path.dirname(val)) != os.path.normcase(DISPATCH_OUT) or base.count(old_tag) != 1:
                stop("%s: --out %r" % (line["name"], val))
            if os.path.normcase(val) != os.path.normcase(line["out"]):
                stop("%s: --out differs from the line's out" % line["name"])
            argv[i + 1] = os.path.join(OUT, base.replace(old_tag, new_tag))
        elif tok == "--tag":
            if val != (old_tag if key is None else "%s_%s" % (old_tag, key)):
                stop("%s: --tag %r" % (line["name"], val))
            argv[i + 1] = new_tag if key is None else "%s_%s" % (new_tag, key)
        else:
            continue
        if tok in seen:
            stop("%s: %s given twice" % (line["name"], tok))
        seen.add(tok)
    if seen != {"--repo", "--out", "--tag"}:
        stop("%s: missing one of --repo/--out/--tag" % line["name"])
    pos = [i for i in range(len(argv) - 3) if argv[i:i + 4] == DISPATCH_ON_PAIR]
    if arm == "1":
        if len(pos) != 1:
            stop("%s: the dispatch switch pair is not present exactly once" % line["name"])
        argv[pos[0]:pos[0] + 4] = U_SWITCH
    elif pos:
        stop("%s: an OFF line carries the dispatch switches" % line["name"])
    for tok in argv:
        if "DISPATCH_JOINT" in tok or "DISPATCH_REASSIGN" in tok or "dpE" in tok or "SAS_wt\\dispatch" in tok:
            stop("%s: dispatch residue %r after the re-tag" % (line["name"], tok))
    if arm == "0" and any("DISPATCH_URGENCY" in tok for tok in argv):
        stop("%s: an OFF line carries DISPATCH_URGENCY" % line["name"])
    out = argv[argv.index("--out") + 1]
    name = new_tag if key is None else "%s_%s" % (new_tag, key)
    return case, arm, {"name": name, "argv": argv, "out": out, "cwd": WT}


def evidence(arm: str) -> list[dict]:
    """The 11 OFF (arm "0") or ON (arm "1") evidence lines, in the dispatch file's order; each ON line is its OFF
    line with --set DISPATCH_URGENCY=1 where the dispatch pair stood."""
    off: dict[str, dict] = {}
    on: dict[str, dict] = {}
    for line in _dispatch_evidence():
        case, a, new = _retag_evidence(line)
        (off if a == "0" else on)[new["name"]] = new
    if len(off) != 11 or len(on) != 11:
        stop("evidence: %d OFF and %d ON lines, expected 11 and 11" % (len(off), len(on)))
    for name, ln in on.items():
        twin = off.get(_off_name(name))
        if twin is None:
            stop("evidence ON line %s has no OFF twin" % name)
        argv = list(ln["argv"])
        i = [j for j in range(len(argv) - 1) if argv[j:j + 2] == U_SWITCH]
        if len(i) != 1:
            stop("%s: DISPATCH_URGENCY=1 not present exactly once" % name)
        del argv[i[0]:i[0] + 2]
        norm = [x.replace(_tag_of(name), _tag_of(twin["name"])) for x in argv]
        if norm != twin["argv"]:
            stop("evidence %s is not %s plus the ON switch" % (name, twin["name"]))
    cases = sorted({_EVID_RE.match("dpE" + n[3:]).group(1) for n in off}, key=EVIDENCE_CASES.index)
    if tuple(cases) != EVIDENCE_CASES:
        stop("evidence cases %s != 16.11's %s" % (cases, EVIDENCE_CASES))
    return list((off if arm == "0" else on).values())


def _tag_of(name: str) -> str:
    return name.split("_")[0]


def _off_name(on_name: str) -> str:
    m = re.match(r"^udE(1|2f|2|x|3|4d|4g)1([cn])(.*)$", on_name)
    if not m:
        stop("unexpected ON name %r" % on_name)
    return "udE%s0%s%s" % m.groups()


def wave_lines(wave: str) -> list[dict]:
    if wave == "w1":
        return screen((0,), (1, 2)) + evidence("0")
    if wave == "w2":
        return screen((0, 1, 2, 3), (3, 4))
    if wave == "w3":
        return screen((1,), (1, 2))
    if wave == "w4":
        return evidence("1")
    if wave == "smoke":
        for cell in SMOKE_CELLS:
            if cell in DEATH_CELLS:
                stop("smoke cell %r holds a recorded death (3.1)" % (cell,))
        return screen((0, 1, 2, 3), (1,), prefix="uds", cells=SMOKE_CELLS)
    stop("unknown wave %r (waves: %s)" % (wave, " ".join(WAVES)))
    return []


EXPECTED_COUNTS = {"w1": 75, "w2": 256, "w3": 64, "w4": 11, "smoke": 8}


def queue_path(wave: str) -> str:
    return os.path.join(OUT, "_ud_q_%s.jsonl" % wave)


def queue_bytes(lines: list[dict]) -> bytes:
    return "".join(json.dumps(line) + "\n" for line in lines).encode("utf-8")


def dpr_reference(name: str) -> str | None:
    """A ud0 / uds0 line on sets 1-2 -> its dpR record's out basename (Z0); else None."""
    m = re.match(r"^ud(s?)0([ru])([12])_([A-D]_[NSEW])$", name)
    if not m:
        return None
    return "_sd_%s_%s.json" % (DPR_TAGS[(int(m.group(3)), m.group(2))], m.group(4))


def dpe_reference(name: str) -> str | None:
    """An evidence OFF line -> the dispatch round's dpE..0.. record's out basename; else None."""
    if not re.match(r"^udE(1|2f|2|x|3|4d|4g)0[cn]", name):
        return None
    for line in _dispatch_evidence():
        if line["name"] == "dpE" + name[3:]:
            return os.path.basename(line["out"])
    return None


# ------------------------------------------------------------------------------------------------------- tag check
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
    tags = sorted({_tag_of(line["name"]) for line in lines})
    own: set[str] = set()
    bad: list[str] = []
    tracked_rel = _tracked_here()
    tracked = {os.path.normcase(os.path.join(WT, p.replace("/", os.sep))) for p in tracked_rel}
    for line in lines:
        base = line["out"]
        stem = base[:-5] if base.endswith(".json") else base
        paths = (base, base + ".argv", base + ".poollog", stem + ".stdout.txt", base + ".stdout.txt")
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

    folders = [OUT, os.path.join(OUT, "_ffr_logs")]
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


# ------------------------------------------------------------------------------------------------- reference copies
def _ref_runs() -> list[tuple[str, str]]:
    """(dest dir, record out basename) for the 64 dpR runs and the 11 dpE OFF runs."""
    runs = []
    table = seeds()
    for k in (1, 2):
        for p, _mode in PLACEMENTS:
            for key, *_ in table[k]:
                runs.append((DPR_DIR, "_sd_%s_%s.json" % (DPR_TAGS[(k, p)], key)))
    for line in _dispatch_evidence():
        if _EVID_RE.match(line["name"]).group(2) == "0":
            runs.append((DPE_DIR, os.path.basename(line["out"])))
    if len(runs) != 75:
        stop("reference runs: %d, expected 64 + 11" % len(runs))
    return runs


def _run_files(out_base: str) -> list[str]:
    stem = out_base[:-5]
    return [out_base, out_base + ".argv", out_base + ".poollog", stem + ".stdout.txt"]


def _rel(path: str) -> str:
    try:
        return os.path.relpath(path, WT).replace(os.sep, "/")
    except ValueError:  # another drive
        return path


def refs() -> int:
    _dispatch_commit()
    listing = set(_git(["ls-tree", "--name-only", DISPATCH_COMMIT, "--", "outputs/"], cwd=DISPATCH_WT)
                  .decode("utf-8", "replace").splitlines())
    rows = []
    missing_optional = []
    for folder, out_base in _ref_runs():
        os.makedirs(folder, exist_ok=True)
        for i, name in enumerate(_run_files(out_base)):
            rel = "outputs/" + name
            if rel not in listing:
                if i == 0:
                    stop("dispatch record %s is not in cc8d653c" % rel)
                missing_optional.append(rel)
                continue
            data = _dispatch_blob(rel)
            dest = os.path.join(folder, name)
            if not os.path.exists(dest):
                with open(dest, "wb") as fh:
                    fh.write(data)
            with open(dest, "rb") as fh:
                back = fh.read()
            if back != data:
                back = _lf(back, _rel(dest))
            if back != data or hashlib.sha256(back).hexdigest() != hashlib.sha256(data).hexdigest():
                stop("%s differs from the git blob (an existing copy is never overwritten)" % dest)
            rows.append((hashlib.sha256(data).hexdigest(), len(data), _rel(dest)))
    rows.sort(key=lambda r: r[2])
    text = "".join("%s  %d  %s\n" % r for r in rows).encode("utf-8")
    if os.path.exists(SHA_FILE):
        with open(SHA_FILE, "rb") as fh:
            if _lf(fh.read(), _rel(SHA_FILE)) != text:
                stop("%s exists and differs (never re-written)" % SHA_FILE)
    else:
        with open(SHA_FILE, "wb") as fh:
            fh.write(text)
    n_dpr = sum(1 for r in rows if r[2].startswith("outputs/_ud_dpR/"))
    print("refs: %d files copied from dispatch@%s (%d in _ud_dpR, %d in _ud_dpE); %d optional files absent"
          % (len(rows), DISPATCH_COMMIT[:8], n_dpr, len(rows) - n_dpr, len(missing_optional)))
    for rel in missing_optional:
        print("  absent in cc8d653c: " + rel)
    return verify_refs()


def verify_refs() -> int:
    """Every line of the sha256 file: size, sha256, and the bytes are dispatch's blob at cc8d653c; no extra file."""
    _dispatch_commit()
    with open(SHA_FILE, "rb") as fh:
        raw = _lf(fh.read(), _rel(SHA_FILE))
    rows = [r.split("  ") for r in raw.decode("utf-8").splitlines() if r]
    listed = set()
    for sha, size, rel in rows:
        path = os.path.join(WT, rel.replace("/", os.sep))
        with open(path, "rb") as fh:
            data = fh.read()
        if len(data) != int(size) or hashlib.sha256(data).hexdigest() != sha:
            data = _lf(data, rel)
        if len(data) != int(size) or hashlib.sha256(data).hexdigest() != sha:
            stop("%s: size or sha256 differs from %s" % (rel, SHA_FILE))
        oid = _git(["rev-parse", "%s:outputs/%s" % (DISPATCH_COMMIT, os.path.basename(path))],
                   cwd=DISPATCH_WT).decode().strip()
        if _blob_oid(data) != oid:
            stop("%s is not dispatch's blob %s" % (rel, oid))
        listed.add(os.path.normcase(path))
    expected = {os.path.normcase(os.path.join(f, n)) for f, b in _ref_runs() for n in _run_files(b)}
    for folder in (DPR_DIR, DPE_DIR):
        for name in _listing(folder):
            p = os.path.normcase(os.path.join(folder, name))
            if p not in listed:
                stop("unlisted file in %s: %s" % (folder, name))
    jsons = [p for p in listed if p.endswith(".json")]
    if len(jsons) != 75 or not listed <= expected:
        stop("reference set: %d records (expected 75) or an unexpected file" % len(jsons))
    n_dpr = sum(1 for p in listed if os.path.normcase(DPR_DIR) in p)
    print("verify-refs: %d files OK (%d dpR, %d dpE) - sha256, size and git blob (dispatch@%s)"
          % (len(listed), n_dpr, len(listed) - n_dpr, DISPATCH_COMMIT[:8]))
    return 0


def z0_config_identity(lines: list[dict]) -> int:
    """Each ud0 / uds0 line on sets 1-2 equals its dpR record's argv, and each evidence OFF line its dpE record's,
    with only the probe path, --repo, --out, --tag and cwd changed. Reads the copies (run `refs` first)."""
    n = 0
    for line in lines:
        ref = dpr_reference(line["name"])
        folder = DPR_DIR
        if ref is None:
            ref = dpe_reference(line["name"])
            folder = DPE_DIR
        if ref is None:
            continue
        with open(os.path.join(folder, ref + ".argv"), encoding="utf-8") as fh:
            rec = json.load(fh)
        argv = list(rec["argv"])
        old_tag = argv[argv.index("--tag") + 1]
        new_tag = line["argv"][line["argv"].index("--tag") + 1]
        mapped = [os.path.join(os.path.dirname(line["argv"][0]), os.path.basename(argv[0]).replace("_dp_probe.py",
                                                                                                   "_ud_probe.py"))]
        for i in range(1, len(argv)):
            prev, tok = argv[i - 1], argv[i]
            if prev == "--repo":
                tok = WT
            elif prev == "--out":
                tok = line["out"]
            elif prev == "--tag":
                tok = new_tag
            mapped.append(tok)
        if mapped != line["argv"] or old_tag.split("_")[0][:3] not in ("dpR", "dpE"):
            stop("Z0 configuration: %s differs from its reference %s" % (line["name"], ref))
        n += 1
    return n


# ------------------------------------------------------------------------------------------------------------ main
def build() -> int:
    _here_check()
    all_lines: list[dict] = []
    per = {}
    for wave in WAVES:
        lines = wave_lines(wave)
        if len(lines) != EXPECTED_COUNTS[wave]:
            stop("%s: %d lines, expected %d" % (wave, len(lines), EXPECTED_COUNTS[wave]))
        per[wave] = lines
        all_lines += lines
    names = [ln["name"] for ln in all_lines]
    outs = [os.path.normcase(ln["out"]) for ln in all_lines]
    if len(set(names)) != len(names) or len(set(outs)) != len(outs):
        stop("duplicate line names or outputs across the waves")
    bad = tag_check(all_lines)
    if bad:
        stop("TAG CHECK FAILED:\n  " + "\n  ".join(bad[:60]))
    for wave in WAVES:
        data = queue_bytes(per[wave])
        path = queue_path(wave)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                if _lf(fh.read(), _rel(path)) != data:
                    stop("%s exists and differs from the rebuilt lines (frozen; never re-written)" % path)
            state = "unchanged (frozen)"
        else:
            with open(path, "wb") as fh:
                fh.write(data)
            state = "written"
        print("%-5s %3d lines  sha256 %s  %s  %s" % (wave, len(per[wave]), hashlib.sha256(data).hexdigest()[:16],
                                                   _rel(path), state))
    print("total %d lines (w1-w4 %d, smoke %d)" % (len(all_lines), len(all_lines) - len(per["smoke"]),
                                                  len(per["smoke"])))
    if os.path.exists(SHA_FILE):
        n = z0_config_identity(per["w1"] + per["smoke"])
        print("Z0 configuration identity: %d lines equal their dpR / dpE record's argv" % n)
    return 0


def check(wave: str, resume: bool, all_trees: bool) -> int:
    _here_check()
    lines = wave_lines(wave)
    path = queue_path(wave)
    if not os.path.exists(path):
        stop("%s is not frozen yet (run build)" % path)
    with open(path, "rb") as fh:
        if _lf(fh.read(), _rel(path)) != queue_bytes(lines):
            stop("%s differs from the rebuilt lines" % path)
    for script in sorted({ln["argv"][0] for ln in lines}):
        if not os.path.exists(script):
            stop("script missing: %s" % script)
    if wave in ("w1", "smoke"):
        print("Z0 configuration identity: %d lines" % z0_config_identity(lines))
    bad = tag_check(lines, resume=resume, all_trees=all_trees)
    if bad:
        stop("TAG CHECK FAILED:\n  " + "\n  ".join(bad[:60]))
    print("%s: %d lines, frozen file identical, scripts present, tags unused%s" % (
        wave, len(lines), " (all trees)" if all_trees else ""))
    print("pool: <py> %s %s %s --maxpar 12 --min-free-gb 3" % (
        POOL, path, os.path.join(OUT, "_mf2_pool_ud_%s.log" % wave)))
    return 0


def show(wave: str) -> int:
    for ln in wave_lines(wave):
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
    if cmd == "refs":
        _here_check()
        return refs()
    if cmd == "verify-refs":
        _here_check()
        return verify_refs()
    if cmd in ("check", "show"):
        if len(sys.argv) < 3 or sys.argv[2] not in WAVES:
            stop("%s needs a wave: %s" % (cmd, " ".join(WAVES)))
        if cmd == "show":
            return show(sys.argv[2])
        return check(sys.argv[2], "--resume" in sys.argv, "--all-trees" in sys.argv)
    stop("unknown command %r" % cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
