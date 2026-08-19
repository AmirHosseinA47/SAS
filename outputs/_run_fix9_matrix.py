"""Sequential/batched UTF-8 matrix runner for fix9.

Batches of at most 4 to avoid the 16-combo memory death.
Writes UTF-8 via Python (never PowerShell redirection).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

PY = r"C:\Users\ahrar\AppData\Local\Programs\Python\Python310\python.exe"
SCENARIOS = ("A", "B", "C", "D")
WINDS = ("north", "south", "east", "west")
BATCH = 4


def complete(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return False
    return "REPRODUCE:" in text and "ERROR" not in text.split("REPRODUCE:")[0]


def run_combo(args: list[str], out_path: str) -> tuple[str, int, float]:
    t0 = time.time()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        proc = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT, env=env)
        if proc.returncode != 0:
            f.write("\n--- EXIT %d ---\n" % proc.returncode)
    return out_path, proc.returncode, time.time() - t0


def jobs(prefix: str, seeds: str) -> list[tuple[list[str], str]]:
    out = []
    for s in SCENARIOS:
        for w in WINDS:
            out.append(
                (
                    [
                        PY,
                        "evaluate_scenarios.py",
                        "--scenario",
                        s,
                        "--wind",
                        w,
                        "--n",
                        "5",
                        "--steps",
                        "240",
                        "--seeds",
                        seeds,
                        "--csv",
                    ],
                    "outputs/%s_%s_%s.txt" % (prefix, s, w),
                )
            )
    return out


def main() -> int:
    prefix = sys.argv[1] if len(sys.argv) > 1 else "fix9"
    seeds = sys.argv[2] if len(sys.argv) > 2 else "101,202,303,404,505"
    pending = [(a, p) for a, p in jobs(prefix, seeds) if not complete(p)]
    print("prefix=%s seeds=%s pending=%d" % (prefix, seeds, len(pending)), flush=True)
    rc_all = 0
    for i in range(0, len(pending), BATCH):
        chunk = pending[i : i + len(pending[i : i + BATCH])]
        print("BATCH %d-%d" % (i + 1, i + len(chunk)), flush=True)
        for _, p in chunk:
            print("  RUN %s" % p, flush=True)
        with ThreadPoolExecutor(max_workers=BATCH) as ex:
            futs = [ex.submit(run_combo, a, p) for a, p in chunk]
            for fut in as_completed(futs):
                path, rc, elapsed = fut.result()
                print("  DONE %s exit=%d elapsed=%.1fs" % (path, rc, elapsed), flush=True)
                rc_all = rc_all or rc
    print("ALL_DONE rc=%d" % rc_all, flush=True)
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
