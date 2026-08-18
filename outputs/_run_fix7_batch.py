"""Run remaining fix7 combos in batches of 4 (skip already-complete files)."""
from __future__ import annotations

import os
import subprocess
import sys
import time

PY = r"C:\Users\ahrar\AppData\Local\Programs\Python\Python310\python.exe"
SEEDS = "101,202,303,404,505"
BATCH = 4


def jobs() -> list[tuple[list[str], str]]:
    out = []
    for s in ("A", "B", "C", "D"):
        for w in ("north", "south", "east", "west"):
            out.append(
                (
                    [
                        PY, "evaluate_scenarios.py",
                        "--scenario", s, "--wind", w,
                        "--n", "5", "--steps", "240", "--seeds", SEEDS, "--csv",
                    ],
                    "outputs/fix7_%s_%s.txt" % (s, w),
                )
            )
    for w in ("north", "south", "east", "west"):
        out.append(
            (
                [
                    PY, "evaluate_scenarios.py",
                    "--scenario", "C", "--wind", w,
                    "--n", "5", "--steps", "240", "--seeds", SEEDS, "--csv",
                    "--uavs", "5", "--fire-trackers", "3", "--victim-searchers", "2",
                ],
                "outputs/fix7ms_C_%s.txt" % w,
            )
        )
    for w in ("north", "south", "east", "west"):
        out.append(
            (
                [
                    PY, "evaluate_scenarios.py",
                    "--scenario", "D", "--wind", w,
                    "--n", "5", "--steps", "240", "--seeds", SEEDS, "--csv",
                    "--uavs", "4", "--fire-trackers", "2", "--victim-searchers", "2",
                ],
                "outputs/fix7ms_D_%s.txt" % w,
            )
        )
    return out


def complete(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return False
    return "REPRODUCE:" in text and "ERROR" not in text.split("REPRODUCE:")[0]


def run_one(args: list[str], out_path: str) -> tuple[str, int, float]:
    t0 = time.time()
    proc = subprocess.run(args, capture_output=True)
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    body = stdout
    if stderr.strip():
        body += "\n--- STDERR ---\n" + stderr
    if proc.returncode != 0:
        body += "\n--- EXIT %d ---\n" % proc.returncode
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
        if not body.endswith("\n"):
            f.write("\n")
    return out_path, proc.returncode, time.time() - t0


def main() -> int:
    pending = [(a, p) for a, p in jobs() if not complete(p)]
    print("pending=%d" % len(pending), flush=True)
    rc_all = 0
    from concurrent.futures import ThreadPoolExecutor, as_completed

    for i in range(0, len(pending), BATCH):
        chunk = pending[i : i + BATCH]
        print("BATCH %d-%d" % (i + 1, i + len(chunk)), flush=True)
        for _, p in chunk:
            print("  RUN %s" % p, flush=True)
        with ThreadPoolExecutor(max_workers=BATCH) as ex:
            futs = [ex.submit(run_one, a, p) for a, p in chunk]
            for fut in as_completed(futs):
                path, rc, elapsed = fut.result()
                print("  DONE %s exit=%d elapsed=%.1fs" % (path, rc, elapsed), flush=True)
                rc_all = rc_all or rc
    print("ALL_DONE rc=%d" % rc_all, flush=True)
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
