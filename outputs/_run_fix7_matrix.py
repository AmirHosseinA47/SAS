"""Sequential UTF-8 matrix runner for fix7 (default 16 + multi-searcher 8)."""
from __future__ import annotations

import subprocess
import sys
import time

PY = r"C:\Users\ahrar\AppData\Local\Programs\Python\Python310\python.exe"
SEEDS = "101,202,303,404,505"
SCENARIOS = ("A", "B", "C", "D")
WINDS = ("north", "south", "east", "west")


def run_combo(args: list[str], out_path: str) -> int:
    print("RUN %s -> %s" % (" ".join(args), out_path), flush=True)
    t0 = time.time()
    proc = subprocess.run(
        args,
        capture_output=True,
    )
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
    elapsed = time.time() - t0
    print("DONE %s exit=%d elapsed=%.1fs" % (out_path, proc.returncode, elapsed), flush=True)
    return proc.returncode


def main() -> int:
    rc_all = 0
    for s in SCENARIOS:
        for w in WINDS:
            out = "outputs/fix7_%s_%s.txt" % (s, w)
            rc = run_combo(
                [
                    PY,
                    "evaluate_scenarios.py",
                    "--scenario", s,
                    "--wind", w,
                    "--n", "5",
                    "--steps", "240",
                    "--seeds", SEEDS,
                    "--csv",
                ],
                out,
            )
            rc_all = rc_all or rc
    for w in WINDS:
        rc = run_combo(
            [
                PY, "evaluate_scenarios.py",
                "--scenario", "C", "--wind", w,
                "--n", "5", "--steps", "240", "--seeds", SEEDS, "--csv",
                "--uavs", "5", "--fire-trackers", "3", "--victim-searchers", "2",
            ],
            "outputs/fix7ms_C_%s.txt" % w,
        )
        rc_all = rc_all or rc
    for w in WINDS:
        rc = run_combo(
            [
                PY, "evaluate_scenarios.py",
                "--scenario", "D", "--wind", w,
                "--n", "5", "--steps", "240", "--seeds", SEEDS, "--csv",
                "--uavs", "4", "--fire-trackers", "2", "--victim-searchers", "2",
            ],
            "outputs/fix7ms_D_%s.txt" % w,
        )
        rc_all = rc_all or rc
    print("ALL_DONE rc=%d" % rc_all, flush=True)
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
