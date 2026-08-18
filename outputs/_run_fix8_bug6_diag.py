"""Sequential UTF-8 runner for BUG #6 D/east and D/west diagnostic combos."""
from __future__ import annotations

import subprocess
import sys
import time

PY = r"C:\Users\ahrar\AppData\Local\Programs\Python\Python310\python.exe"
SEEDS = "101,202,303,404,505"


def run_one(scenario: str, wind: str, out_path: str) -> tuple[str, int, float]:
    args = [
        PY,
        "evaluate_scenarios.py",
        "--scenario",
        scenario,
        "--wind",
        wind,
        "--n",
        "5",
        "--steps",
        "240",
        "--seeds",
        SEEDS,
        "--csv",
    ]
    t0 = time.time()
    env = dict(__import__("os").environ)
    env["PYTHONUNBUFFERED"] = "1"
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        proc = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT, env=env)
        if proc.returncode != 0:
            f.write("\n--- EXIT %d ---\n" % proc.returncode)
    return out_path, proc.returncode, time.time() - t0


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "before"
    jobs = [
        ("D", "east", "outputs/fix8_bug6_%s_D_east.txt" % tag),
        ("D", "west", "outputs/fix8_bug6_%s_D_west.txt" % tag),
    ]
    rc_all = 0
    for s, w, path in jobs:
        print("RUN %s/%s -> %s" % (s, w, path), flush=True)
        out, rc, elapsed = run_one(s, w, path)
        print("DONE %s exit=%d elapsed=%.1fs" % (out, rc, elapsed), flush=True)
        rc_all = rc_all or rc
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
