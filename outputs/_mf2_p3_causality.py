"""fix2 Part 3, P3-5(a): switch causality for T7 / T8 in one pytest run per setting.

usage: _mf2_p3_causality.py KEY=VALUE [KEY=VALUE ...] -- <pytest args ...>

Sets each KEY on common_fixed_variables BEFORE pytest collects (every fix2 switch is read at call
time through getattr(cfv, name)), then runs pytest in-process. Pre-registered:
  3a = 3b = 0      -> T7 and T8 FAIL
  3a = 1, 3b = 0   -> T8 FAILS
  shipped (no KEY) -> both PASS
"""
import os
import sys

REPO = r"E:\Projects\SAS"


def main() -> int:
    args = sys.argv[1:]
    sep = args.index("--")
    sets, pytest_args = args[:sep], args[sep + 1:]
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import common_fixed_variables as cfv
    for kv in sets:
        k, v = kv.split("=", 1)
        if not hasattr(cfv, k):
            print("MF2 CAUSALITY: unknown switch %s" % k)
            return 2
        setattr(cfv, k, int(v))
    print("MF2 CAUSALITY SETTINGS: %s" % (" ".join(sets) or "shipped"))
    import pytest
    return int(pytest.main(pytest_args))


if __name__ == "__main__":
    raise SystemExit(main())
