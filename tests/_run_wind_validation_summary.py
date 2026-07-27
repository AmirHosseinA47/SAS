"""Compact four-direction victim_searcher validation summary."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _validate_wind_four_directions import WINDS, run_wind  # noqa: E402


def main() -> int:
    all_pass = True
    for wind in WINDS:
        result = run_wind(wind)
        ok = bool(result["pass"])
        all_pass = all_pass and ok
        status = "PASS" if ok else "FAIL"
        print(
            f"{wind.upper()}: {status} | unique_targets={result['unique_targets']} "
            f"max_same={result['max_same_target_streak']} "
            f"max_hold={result['max_hold_streak']} "
            f"max_edge={result['max_edge_streak']} "
            f"strict_fire/smoke={result['strict_fire_smoke_steps']} "
            f"failures={result.get('failures', [])}"
        )
    print("ALL_PASS:", all_pass)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
