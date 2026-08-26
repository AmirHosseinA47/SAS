#!/usr/bin/env bash
# Byte-identity gate: every default n<=1 combo must equal the lane-clamp
# round's committed file exactly.
set -u
ROOT="E:/Projects/SAS/.claude/worktrees/c-east-interior-retarget-diagnosis-daa820"
cd "$ROOT" || exit 1
same=0; diff_n=0; missing=0
for sc in A B C D; do
  for wind in east west north south; do
    new="outputs/cast_default_${sc}_${wind}.txt"
    old="outputs/lane_clamp_default_${sc}_${wind}.txt"
    if [ ! -s "$new" ]; then
      echo "  MISSING/EMPTY  ${sc}_${wind}"
      missing=$((missing+1))
      continue
    fi
    if cmp -s "$new" "$old"; then
      echo "  IDENTICAL      ${sc}_${wind}  ($(wc -c < "$new") bytes)"
      same=$((same+1))
    else
      echo "  *** DIFFERS    ${sc}_${wind}"
      diff -u "$old" "$new" | head -20
      diff_n=$((diff_n+1))
    fi
  done
done
echo ""
echo "BYTE-IDENTITY: ${same}/16 identical, ${diff_n} differ, ${missing} missing"
[ "$same" -eq 16 ] && echo "GATE 6: PASS" || echo "GATE 6: FAIL"
