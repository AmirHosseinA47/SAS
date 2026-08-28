#!/bin/sh
PY="E:/Projects/SAS/.venv/Scripts/python.exe"
cd "E:/Projects/SAS/.claude/worktrees/route-blocked-fire-suppression-57e3a2"
for w in south east; do
  "$PY" evaluate_scenarios.py --scenario D --wind $w --n 5 --steps 240 \
      --seeds 101,202,303,404,505 > outputs/_rb_eval_after_D_$w.txt 2> outputs/_rb_eval_after_D_$w.err
  echo "eval-after D/$w exit=$? size=$(wc -c < outputs/_rb_eval_after_D_$w.txt)"
done
