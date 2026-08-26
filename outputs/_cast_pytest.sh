#!/usr/bin/env bash
# Full test suite - identical command to every prior round in this campaign.
#   usage: _cast_pytest.sh <outfile>
set -u
ROOT="E:/Projects/SAS/.claude/worktrees/c-east-interior-retarget-diagnosis-daa820"
PY="E:/Projects/SAS/.venv/Scripts/python.exe"
OUT="${1:-outputs/_cast_pytest.txt}"
cd "$ROOT" || exit 1
"$PY" -m pytest -q -p no:cacheprovider > "$OUT" 2>&1
echo "pytest rc=$? -> $OUT"
tail -3 "$OUT"
