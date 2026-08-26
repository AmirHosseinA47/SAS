#!/usr/bin/env bash
# Gate 7: classify a POST pytest run against the lane-clamp round's committed
# baseline (outputs/_lane_clamp_pytest.txt = 8 failed / 427 passed).
# PASS requires the failure SET to be unchanged - not merely the same count.
set -u
ROOT="E:/Projects/SAS/.claude/worktrees/c-east-interior-retarget-diagnosis-daa820"
cd "$ROOT" || exit 1
BASE="outputs/_lane_clamp_pytest.txt"
NEW="${1:-outputs/_cast_pytest_POST.txt}"

grep -E '^FAILED' "$BASE" | sed 's/ - .*//' | sort -u > /tmp/_cast_base_fail.txt
grep -E '^FAILED' "$NEW"  | sed 's/ - .*//' | sort -u > /tmp/_cast_new_fail.txt

echo "baseline summary: $(grep -E '^[0-9]+ (failed|passed)' "$BASE" | tail -1)"
echo "new summary:      $(grep -E '^[0-9]+ (failed|passed)' "$NEW"  | tail -1)"
echo ""
echo "baseline failures: $(wc -l < /tmp/_cast_base_fail.txt)"
echo "new failures:      $(wc -l < /tmp/_cast_new_fail.txt)"
echo ""
newly=$(comm -13 /tmp/_cast_base_fail.txt /tmp/_cast_new_fail.txt)
fixed=$(comm -23 /tmp/_cast_base_fail.txt /tmp/_cast_new_fail.txt)
if [ -n "$newly" ]; then
  echo "*** NEWLY FAILING (regressions caused by the edit):"
  echo "$newly" | sed 's/^/    /'
else
  echo "NEWLY FAILING: none"
fi
if [ -n "$fixed" ]; then
  echo "NO LONGER FAILING (were failing at baseline):"
  echo "$fixed" | sed 's/^/    /'
else
  echo "NO LONGER FAILING: none"
fi
echo ""
if [ -z "$newly" ] && [ -z "$fixed" ]; then
  echo "GATE 7: PASS - failure set identical to baseline"
else
  echo "GATE 7: FAIL - failure set changed"
fi
