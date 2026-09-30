"""fix3a revert check driver: for each fix3a switch, run tests/test_fix3a.py with that switch forced to 0
(outputs/_fx3_revert_plugin.py) and list the tests that FAIL. Every rule must have at least one failing
test when its switch is off, and the failures must belong to that rule (the test names).

usage (repo root): .venv/Scripts/python.exe outputs/_fx3_revert_check.py [> outputs/_fx3_revert_check.txt]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWITCHES = ["SEARCHER_ROUTE_FIRE_FIELD", "SEARCHER_SWEEP_IN_BOUNDS", "SEARCHER_CORNER_ESCAPE",
            "FREE_CELL_DOCKING", "SCENARIO_B_TEAM", "SCENARIO_B_STAGGERED_LAUNCH", "SCENARIO_B_RETURN_DELAY"]


def main():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(REPO, "outputs") + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("MPLBACKEND", "Agg")
    rc_all = 0
    for name in SWITCHES:
        env["FX3_REVERT"] = name
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "_fx3_revert_plugin", "-rf",
                               "tests/test_fix3a.py"], cwd=REPO, env=env, capture_output=True, text=True)
        failed = sorted(set(re.findall(r"FAILED tests/test_fix3a.py::(\S+)", proc.stdout)))
        summary = (proc.stdout.strip().splitlines() or ["?"])[-1]
        print("%-28s %d failing: %s" % (name, len(failed), summary))
        for t in failed:
            print("    %s" % t)
        if not failed:
            rc_all = 1
            print("    *** NO TEST FAILS - the rule is not covered ***")
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
