#!/usr/bin/env bash
# Dimension round, after the pool: the route_blocked gate (4 shards, ~45-60 min)
# and the full test suite (~55-65 min), concurrently (4 + 1 processes), then the
# gate merge. Both run against the PATCHED working tree.
cd /e/Projects/SAS || exit 1
PY=./.venv/Scripts/python.exe
LOG=outputs/_dim_post.log
{
  echo "POST START $(date '+%Y-%m-%d %H:%M:%S')  tree: $(git diff --stat | tail -1)"
  ( MPLBACKEND=Agg $PY -m pytest tests -p no:cacheprovider -q > outputs/_dim_pytest_fix.log 2>&1; echo "PYTEST DONE rc=$? $(date +%H:%M:%S) $(tail -1 outputs/_dim_pytest_fix.log)" ) &
  bash outputs/_ffr_rbgate.sh dimfix
  echo "RBGATE SHARDS DONE $(date +%H:%M:%S)"
  $PY outputs/_ir_rbmerge.py --prefix dimfix > outputs/_dim_rbgate_dimfix.txt 2>&1
  echo "RBMERGE DONE rc=$? $(date +%H:%M:%S)"
  wait
  echo "ALL_DIM_POST_COMPLETE $(date '+%Y-%m-%d %H:%M:%S')"
} > "$LOG" 2>&1
