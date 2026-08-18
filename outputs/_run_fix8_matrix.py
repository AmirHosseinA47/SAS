"""Sequential UTF-8 matrix runner for fix8 (16 default combos)."""
from __future__ import annotations

import os
import subprocess
import sys
import time

PY = r"C:\Users\ahrar\AppData\Local\Programs\Python\Python310\python.exe"
SEEDS = "101,202,303,404,505"
SCENARIOS = ("A", "B", "C", "D")
WINDS = ("north", "south", "east", "west")


def complete(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return False
    return "REPRODUCE:" in text and "ERROR" not in text.split("REPRODUCE:")[0]


def run_combo(args: list[str], out_path: str) -> int:
    print("RUN %s -> %s" % (" ".join(args), out_path), flush=True)
    t0 = time.time()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        proc = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT, env=env)
        if proc.returncode != 0:
            f.write("\n--- EXIT %d ---\n" % proc.returncode)
    elapsed = time.time() - t0
    print("DONE %s exit=%d elapsed=%.1fs" % (out_path, proc.returncode, elapsed), flush=True)
    return proc.returncode


def main() -> int:
    rc_all = 0
    for s in SCENARIOS:
        for w in WINDS:
            out = "outputs/fix8_%s_%s.txt" % (s, w)
            if complete(out):
                print("SKIP %s" % out, flush=True)
                continue
            rc = run_combo(
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
                    SEEDS,
                    "--csv",
                ],
                out,
            )
            rc_all = rc_all or rc
    print("ALL_DONE rc=%d" % rc_all, flush=True)
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
