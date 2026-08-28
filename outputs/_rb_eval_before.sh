#!/bin/sh
PY="E:/Projects/SAS/.venv/Scripts/python.exe"
OUT="E:/Projects/SAS/.claude/worktrees/route-blocked-fire-suppression-57e3a2/outputs"
cd "C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS--claude-worktrees-route-blocked-fire-suppression-57e3a2/e7c28b7e-5f54-47f9-9fe2-42550a317021/scratchpad/pristine"
for w in south east; do
  "$PY" evaluate_scenarios.py --scenario D --wind $w --n 5 --steps 240       --seeds 101,202,303,404,505 > "$OUT/_rb_eval_before_D_$w.txt" 2> "$OUT/_rb_eval_before_D_$w.err"
  echo "eval-before D/$w exit=$? size=$(wc -c < "$OUT/_rb_eval_before_D_$w.txt")"
done
