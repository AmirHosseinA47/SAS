#!/usr/bin/env bash
# Depot-cost round: confirm the test baseline the brief cites (8 failed / 545
# passed at e703861) before Part 3 relies on it. The COUNT is not the gate - the
# failing NAME SET is, because outputs/dimension_report.txt:430-432 records a case
# where the counts matched by coincidence while the sets differed by two tests.
# Run from the repo root.
cd "$(dirname "$0")/.." || exit 1
export MPLBACKEND=Agg
./.venv/Scripts/python.exe -m pytest tests -p no:cacheprovider -q \
  > outputs/_dc_pytest_e703861.log 2>&1
echo "DC_PYTEST_BASELINE_COMPLETE rc=$?" >> outputs/_dc_pytest_e703861.log
