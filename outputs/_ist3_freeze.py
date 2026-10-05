"""isTrue round Part 3: the FREEZE RECORD of both checkouts - taken before the pool launches and again after it completes.

usage: _ist3_freeze.py <phase: launch | complete>      writes outputs/_ist3_freeze_<phase>.json
       _ist3_freeze.py --compare                         exit 0 iff launch == complete (every field but the phase)

For each checkout (B = E:/Projects/SAS_wt/basef686, I = E:/Projects/SAS_wt/istrue): git HEAD, `git status --porcelain
-uno` (tracked changes only; the untracked walk is never run), and sha256[:16] of the RAW bytes (as _sd_probe's
src_sha) of every tracked file outside outputs/ (git ls-files, pathspec ':(exclude)outputs'). For I also the run-loaded
probe and pool files in outputs/ (the chain, the reach wrapper, the pool, the queue and the frozen list). The record
covers the three changed planner files that src_sha does not hash (review F3).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKOUTS = {"B": r"E:\Projects\SAS_wt\basef686", "I": r"E:\Projects\SAS_wt\istrue"}
RUN_LOADED = ("_ist3_reach.py", "_ut_probe.py", "_fb3_probe.py", "_fx3_probe.py", "_mf2_probe.py", "_sd_probe.py",
              "_bp_inst.py", "_fm2_probe_harness.py", "_mf2_pool.py", "_ist3_queue.py", "_ist3_configs.json",
              "_ist3_q.jsonl")


def _git(repo, *args) -> str:
    return subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True, check=True).stdout


def _sha(path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def record() -> dict:
    out = {}
    for key, repo in CHECKOUTS.items():
        files = [f for f in _git(repo, "ls-files", "-z", "--", ".", ":(exclude)outputs").split("\0") if f]
        out[key] = {
            "repo": repo,
            "head": _git(repo, "rev-parse", "HEAD").strip(),
            "status": _git(repo, "status", "--porcelain", "-uno"),
            "n_files": len(files),
            "sha": {f: _sha(os.path.join(repo, f)) for f in sorted(files)},
        }
    out["I"]["run_loaded"] = {f: _sha(os.path.join(HERE, f)) for f in RUN_LOADED}
    return out


def main() -> int:
    sys.stdout.reconfigure(newline="\n")
    if sys.argv[1:] == ["--compare"]:
        a = json.load(open(os.path.join(HERE, "_ist3_freeze_launch.json"), encoding="utf-8"))
        b = json.load(open(os.path.join(HERE, "_ist3_freeze_complete.json"), encoding="utf-8"))
        a.pop("phase", None)
        b.pop("phase", None)
        same = a == b
        if not same:
            for k in sorted(set(a) | set(b)):
                if a.get(k) != b.get(k):
                    print("DIFFERS:", k)
        print("FREEZE", "HELD" if same else "BROKEN")
        return 0 if same else 1
    if len(sys.argv) != 2 or sys.argv[1] not in ("launch", "complete"):
        print(__doc__)
        return 2
    rec = record()
    rec["phase"] = sys.argv[1]
    for key in ("B", "I"):
        print("%s %s head %s status %r files %d" % (key, rec[key]["repo"], rec[key]["head"][:8], rec[key]["status"],
                                                   rec[key]["n_files"]))
    path = os.path.join(HERE, "_ist3_freeze_%s.json" % sys.argv[1])
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=1)
    print("wrote", path)
    return 0 if all(not rec[k]["status"] for k in ("B", "I")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
