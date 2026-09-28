"""fix1 (mf1) P3-6(a): a 360-step evaluate_scenarios run with NO --batch-size.

usage: _mf1_eval360.py <out.json>
Runs `evaluate_scenarios.py --scenario D --n 2 --steps 360 --seeds 101,202 --csv` as a
subprocess and records its exit code, stdout and stderr. Exits non-zero unless the run
exited 0 AND printed both seed rows, a summary and steps_run 360 in its CSV - so the
pool cannot record this check as done unless item 1 actually works.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = r"E:\Projects\SAS"


def main() -> int:
    out = sys.argv[1]
    cmd = [os.path.join(REPO, ".venv", "Scripts", "python.exe"), os.path.join(REPO, "evaluate_scenarios.py"),
           "--scenario", "D", "--n", "2", "--steps", "360", "--seeds", "101,202", "--csv"]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=dict(os.environ, MPLBACKEND="Agg"))
    rows = [ln for ln in proc.stdout.splitlines() if ln.startswith("seed=")]
    csv_rows = [ln for ln in proc.stdout.splitlines() if ln[:4] in ("101,", "202,")]
    ok = (proc.returncode == 0 and len(rows) == 2 and "Summary" in proc.stdout
          and all(",360," in ln for ln in csv_rows) and len(csv_rows) == 2)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"cmd": cmd[1:], "returncode": proc.returncode, "ok": ok, "stdout": proc.stdout,
                   "stderr": proc.stderr[-4000:]}, fh)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
