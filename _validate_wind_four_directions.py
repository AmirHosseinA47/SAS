"""Validation harness: victim_searcher scenario matrix (role-based)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

from victim_searcher_scenario_validation import run_scenario_matrix


def main() -> int:
    results = run_scenario_matrix()
    payload = [
        {
            "scenario": r.scenario_name,
            "wind": r.wind,
            "variable_wind": r.variable_wind,
            "victim_searcher_id": r.victim_searcher_id,
            "pass": r.pass_run,
            "failures": r.failures,
            "metrics": r.metrics,
        }
        for r in results
    ]
    print(json.dumps(payload, indent=2))
    return 0 if all(r.pass_run for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
