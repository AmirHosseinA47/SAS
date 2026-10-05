"""Dispatch round Part 3 queues (outputs/dispatch_part1.txt section 14; amendment A1 section 21). Lines for
outputs/_mf2_pool.py ({"name", "argv", "out", "cwd"}). GENERATES QUEUES ONLY - it never starts a run.

usage (dispatch worktree root): .venv/Scripts/python.exe outputs/_dp_queue.py <wave> --base <B worktree> [--resume]
  seeds     freeze the screen's cells into outputs/_dp_seeds.txt (set 1 = cells("fx3mS"), set 2 = cells("fx3mS2"));
            if the file exists it must be identical, else STOP (the seed-selector self-reference rule)
  identity  dpR (B worktree) + dp0 (dispatch, switches 0) - 64 + 64 probe lines - and the gate shards dpGR (B) +
            dpG0 (dispatch, switches 0): G-ID first; nothing else is read until it passes (14.9)
  on        dp1 (dispatch, --set DISPATCH_JOINT=1 --set DISPATCH_REASSIGN=1) - 64 probe lines
  gate      dpG1 - the four route_blocked shards with both switches on
  evidence  dpE - the evidence cases of 14.8 / 21.2(a): 22 lines (case 2 in both of 14.8's configurations:
            BD-R = SEARCHER_TARGETING 2, tags dpE2..; BF-R = SEARCHER_TARGETING 3, tags dpE2f..)
  all       identity + on + gate + evidence, in that order
  --base    the detached B worktree (E:/Projects/SAS_wt/base<B>), REQUIRED for identity / all
  --resume  allow existing files of the wave's tags when they belong to one of the wave's own lines (the pool skips a
            run whose .argv matches); without it any existing file of a wave tag is a hard failure, and a TRACKED one
            always is.

EVERY probe line: <dispatch>/outputs/_dp_probe.py --crn --hazard -- --repo <checkout> ... --steps 360
--set BATCH_SIZE=360 --set GLOBAL_PLANNER_MODE=0 --set VICTIM_SPAWN_MODE=<0|1>, --out an ABSOLUTE path in the
dispatch worktree's outputs/ (dpR included), cwd = the --repo checkout. Tags: <arm><placement>, placement r = ring
set 1, r2 = ring set 2, u = uniform set 1, u2 = uniform set 2 (dpRr, dpRr2, dpRu, dpRu2, dp0r ... dp1u2).
Gate shards: <checkout>/outputs/_rblatch_campaign2.py (no --repo: it imports its own parent checkout and writes
beside itself), cwd and out in that checkout's outputs/; the dpGR files are copied into the dispatch outputs/ with
their sha256 before the B worktree is removed (14.1, 21.2(e)).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(HERE)
PROBE = os.path.join(HERE, "_dp_probe.py")
SEEDS = os.path.join(HERE, "_dp_seeds.txt")
ON = ["--set", "DISPATCH_JOINT=1", "--set", "DISPATCH_REASSIGN=1"]
PLACEMENTS = (("r", 0, "set1"), ("r2", 0, "set2"), ("u", 1, "set1"), ("u2", 1, "set2"))
SHARDS = (("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
          ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505"))
# 21.2(d): identity-control --set lists for original configurations
PRE_BAYES = ["--set", "SEARCHER_TARGETING_FIX=0", "--set", "UAV_DOCKED_NOT_OBSTACLE=0"]
PRE_UNTUNE = ["--set", "SEARCHER_UNTUNED=0"] + PRE_BAYES


def _cells_from_argv(ref_tag: str) -> list[tuple[str, str, str, str]]:
    sys.path.insert(0, HERE)
    from _fb3_queue import cells  # noqa: E402  (reads outputs/_sd_<ref>_<key>.json.argv)
    return [tuple(c) for c in cells(ref_tag)]


def seeds() -> dict[str, list[list[str]]]:
    fresh = {"set1": [list(c) for c in _cells_from_argv("fx3mS")], "set2": [list(c) for c in _cells_from_argv("fx3mS2")]}
    text = json.dumps(fresh, indent=1, sort_keys=True)
    if os.path.exists(SEEDS):
        with open(SEEDS, encoding="utf-8") as fh:
            frozen = json.load(fh)
        if frozen != fresh:
            raise SystemExit("STOP: outputs/_dp_seeds.txt differs from the reference argv cells (never re-select)")
        return frozen
    with open(SEEDS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text + "\n")
    return fresh


def probe_line(tag, key, scen, wind, seed, repo, sets, *, own=("--crn", "--hazard")):
    out = os.path.join(HERE, "_sd_%s_%s.json" % (tag, key))
    argv = [PROBE, *own, "--", "--repo", repo, "--scenario", scen, "--wind", wind, "--seed", str(seed)]
    argv += list(sets)
    argv += ["--steps", "360", "--set", "BATCH_SIZE=360", "--out", out, "--tag", "%s_%s" % (tag, key)]
    return {"name": "%s_%s" % (tag, key), "argv": argv, "out": out, "cwd": repo}


def screen(arm: str, repo: str, extra: list[str]) -> list[dict]:
    frozen = seeds()
    lines = []
    for suffix, mode, which in PLACEMENTS:
        tag = arm + suffix
        for key, scen, wind, seed in frozen[which]:
            sets = ["--set", "GLOBAL_PLANNER_MODE=0", "--set", "VICTIM_SPAWN_MODE=%d" % mode] + extra
            lines.append(probe_line(tag, key, scen, wind, seed, repo, sets))
    return lines


def shards(tag_prefix: str, repo: str, extra: list[str]) -> list[dict]:
    lines = []
    for sid, wind, seed_list in SHARDS:
        tag = tag_prefix + sid
        script = os.path.join(repo, "outputs", "_rblatch_campaign2.py")
        out = os.path.join(repo, "outputs", "_rblatch_camp2_%s_D_%s.json" % (tag, wind))
        argv = [script, "--scenario", "D", "--wind", wind, "--steps", "240", "--seeds", seed_list, "--tag", tag] + extra
        lines.append({"name": tag, "argv": argv, "out": out, "cwd": repo})
    return lines


def evidence() -> list[dict]:
    """14.8 + 21.2(a): every original configuration OFF and ON; CRN-off originals also with CRN on."""
    lines: list[dict] = []
    # CASE 1 - fix3a D/south/505, half roles: the _ffr harness (no dp layer); CRN via _fm2_probe_harness.
    for arm, sw in (("0", []), ("1", ON)):
        for crn in ("n", "c"):
            tag = "dpE1%s%s" % (arm, crn)
            out = os.path.join(HERE, "_ffr_%s_D_south_half_505.json" % tag)
            script = os.path.join(HERE, "_ffr_harness.py" if crn == "n" else "_fm2_probe_harness.py")
            argv = [script, "--repo", WT, "--scenario", "D", "--wind", "south", "--roles", "half", "--seed", "505",
                    "--steps", "360", "--out", out, "--tag", tag] + PRE_UNTUNE + sw
            if crn == "c":
                argv += ["--set", "FM2P_CRN=1"]
            lines.append({"name": tag, "argv": argv, "out": out, "cwd": WT})
    # CASE 2 - fix3b re-screen ring set 2 D_W 9636, originally _fb3_probe CRN off, in BOTH configurations 14.8
    # pre-registers: BD-R (SEARCHER_TARGETING 2, tags dpE2..) and BF-R (SEARCHER_TARGETING 3, tags dpE2f..; R3
    # finding 8). EXTRA - fix3b re-screen ring set 2 D_N 9633, BD-R (its step-39 firefighter death; the ST=3 original
    # is identical up to that death, so ST=2 stands for both).
    for case, key, wind, seed, st in (("2", "D_W", "west", "9636", "2"), ("2f", "D_W", "west", "9636", "3"),
                                      ("x", "D_N", "north", "9633", "2")):
        for arm, sw in (("0", []), ("1", ON)):
            for crn in ("n", "c"):
                tag = "dpE%s%s%s" % (case, arm, crn)
                own = ("--crn", "--hazard") if crn == "c" else ("--hazard",)
                sets = ["--set", "GLOBAL_PLANNER_MODE=0", "--set", "SEARCHER_TARGETING=%s" % st] + PRE_UNTUNE + sw
                lines.append(probe_line(tag, key, "D", wind, seed, WT, sets, own=own))
    # CASE 3 - untune re-screen ring set 2 D_N 9633, the ut0r2 configuration (pre-untune), originally CRN on.
    for arm, sw in (("0", []), ("1", ON)):
        tag = "dpE3%sc" % arm
        sets = ["--set", "GLOBAL_PLANNER_MODE=0", "--set", "VICTIM_SPAWN_MODE=0"] + PRE_UNTUNE + sw
        lines.append(probe_line(tag, "D_N", "D", "north", "9633", WT, sets))
    # CASE 4 - bayesprep ring set 1 D_N 9613: BD (SEARCHER_TARGETING 2) and GP (GLOBAL_PLANNER_MODE 1 +
    # SEARCHER_TARGETING 3), at B's defaults, CRN on (21.2(a)); tags dpE4d0c / dpE4d1c / dpE4g0c / dpE4g1c.
    for conf, conf_sets in (("d", ["--set", "GLOBAL_PLANNER_MODE=0", "--set", "SEARCHER_TARGETING=2"]),
                            ("g", ["--set", "GLOBAL_PLANNER_MODE=1", "--set", "SEARCHER_TARGETING=3"])):
        for arm, sw in (("0", []), ("1", ON)):
            tag = "dpE4%s%sc" % (conf, arm)
            sets = conf_sets + ["--set", "VICTIM_SPAWN_MODE=0"] + sw
            lines.append(probe_line(tag, "D_N", "D", "north", "9613", WT, sets))
    return lines


def _tracked(path: str) -> bool:
    """git ls-files in the repository that HOLDS the path (a dpR line's cwd is the B worktree, its out is here)."""
    folder = os.path.dirname(os.path.abspath(path))
    return subprocess.run(["git", "-C", folder, "ls-files", "--error-unmatch", os.path.basename(path)],
                          capture_output=True).returncode == 0


# 0.4 / 14.9 reserved name patterns, per wave tag (top-level listings of outputs/ and outputs/_ffr_logs only)
_PATTERNS = ("_sd_{t}_", "_ffr_{t}_", "_ffr_rb_{t}", "_rblatch_camp2_{t}_", "_ffr_logs/{t}_")


def _tag_check(lines: list[dict], resume: bool) -> None:
    """Every output of the wave: absent, or (with --resume) present only as one of the wave's own lines; never
    tracked by git (in the repository that holds it); a crashed or partial record (an out without the pool's .argv)
    is never re-queued until it has been copied aside (21.2(j); R3 finding 2). Also every file matching the wave's
    tags under the reserved patterns, in this worktree's outputs/ and in each line's checkout's outputs/ (R3
    finding 7) - top-level listings only, never a recursive walk."""
    bad = []
    own = set()
    tags = set()
    for line in lines:
        base = line["out"]
        stem = base[:-5] if base.endswith(".json") else base
        tags.add(line["name"].split("_")[0])
        # the probe chain writes <out minus .json>.stdout.txt (_sd_probe.py:369); the other spelling is checked too
        paths = (base, base + ".argv", base + ".poollog", stem + ".stdout.txt", base + ".stdout.txt")
        own.update(os.path.normcase(os.path.abspath(x)) for x in paths)
        for path in paths:
            if not os.path.exists(path):
                continue
            tracked = _tracked(path)
            if tracked or not resume:
                bad.append(("TRACKED " if tracked else "EXISTS ") + path)
        if resume and os.path.exists(base) and not os.path.exists(base + ".argv"):
            bad.append("CRASHED OR PARTIAL RECORD (no .argv - copy it aside before re-queuing, 21.2(j)) " + base)
    folders = {HERE} | {os.path.join(line["cwd"], "outputs") for line in lines}
    for folder in sorted(folders):
        for sub in ("", "_ffr_logs"):
            where = os.path.join(folder, sub) if sub else folder
            if not os.path.isdir(where):
                continue
            for name in os.listdir(where):
                rel = (sub + "/" + name) if sub else name
                if not any(rel.startswith(pat.format(t=t)) for t in tags for pat in _PATTERNS):
                    continue
                path = os.path.join(where, name)
                if os.path.normcase(os.path.abspath(path)) in own:
                    continue          # one of the wave's own outputs: judged above
                bad.append(("TRACKED " if _tracked(path) else "TAG IN USE ") + path)
    if bad:
        raise SystemExit("TAG CHECK FAILED:\n  " + "\n  ".join(sorted(set(bad))[:40]))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    wave = sys.argv[1]
    resume = "--resume" in sys.argv
    base = None
    if "--base" in sys.argv:
        # one spelling of B's path everywhere: argv, .argv signature, the recorded repo (R3 finding 6)
        base = os.path.abspath(sys.argv[sys.argv.index("--base") + 1])
    if wave == "seeds":
        frozen = seeds()
        print("seeds frozen: set1 %d cells, set2 %d cells" % (len(frozen["set1"]), len(frozen["set2"])))
        return 0
    waves = {
        "identity": lambda: screen("dpR", base, []) + screen("dp0", WT, []) + shards("dpGR", base, [])
        + shards("dpG0", WT, []),
        "on": lambda: screen("dp1", WT, ON),
        "gate": lambda: shards("dpG1", WT, ON),
        "evidence": evidence,
    }
    if wave in ("identity", "all") and not base:
        raise SystemExit("--base <B worktree> is required for the identity wave")
    if wave == "all":
        lines = waves["identity"]() + waves["on"]() + waves["gate"]() + waves["evidence"]()
    elif wave in waves:
        lines = waves[wave]()
    else:
        raise SystemExit("unknown wave %r" % wave)
    names = [line["name"] for line in lines]
    if len(names) != len(set(names)):
        raise SystemExit("duplicate line names")
    _tag_check(lines, resume)
    path = os.path.join(HERE, "_dp_q_%s.jsonl" % wave)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
    print("%s: %d lines -> %s" % (wave, len(lines), path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
