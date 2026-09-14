"""Merge verification: canonical runs at merged main vs the flip-round arm.

Written 2026-09-14 BEFORE the merge and before any mgD run. Read-only; reuses the
rules of outputs/_flip3_compare.py (see its docstring).

  mgD  = no --set, --uav-actions, 240 steps, at merged main (expected == 6adeb4f)
  flhD = the flip round's no-set arm at afbf8bd (same tree for every non-outputs file)
  dfD  = the explicit --set dcD arm at 7f951cb

Expected: mgD STRICT-H == flhD (every key except tag and wall_s equal - params and
extra_params included, since neither side passes --set) on all three canonical tuples,
and mgD H == dfD on the same three. A missing file is a FAIL.

  python outputs/_merge_verify_compare.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _flip3_compare as F  # noqa: E402

TUPLES = [("east", "half", 101), ("south", "half", 101), ("east", "def", 101)]


def main():
    print("MERGE VERIFY: canonical runs at merged main")
    t = F.Tally()
    t.group("mgD STRICT-H == flhD (flip round, no --set)", F.ff_pair("mgD", "flhD", TUPLES, "STRICT"), 3)
    t.group("mgD H == dfD (explicit dcD --set, 7f951cb)", F.ff_pair("mgD", "dfD", TUPLES, "H"), 3)
    return t.done()


if __name__ == "__main__":
    sys.exit(main())
