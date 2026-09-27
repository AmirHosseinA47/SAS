#!/usr/bin/env bash
# planner round Part 1, wave 4: recorder v2 (exact target cells, instability triggers) on the
# canonical 13 at 240 steps, observe mode, pinned dfbfbe7 worktree -> _pl_v2_observe_*.json.
# Added after the final document check found that the v1 recorder's tracker distance counted
# stale cells, so the open-loop battery_cost could only be bracketed, and not correctly.
WT=/home/user/sas_dfbfbe7
PY=/home/user/SAS/.venv/bin/python
OUT=/home/user/SAS/outputs/_pl_verify
cd "$WT" || exit 1
echo "WAVE4 START $(date -Is) head=$(git -C $WT rev-parse HEAD) dirty=$(git -C $WT status --porcelain | wc -l)"
jobs_list() {
  for s in 101 202 303 404 505; do echo "east half $s"; done
  for s in 101 202 303 404 505; do echo "south half $s"; done
  for s in 101 202 303; do echo "east default $s"; done
}
run_one() {
  wind=$1; roles=$2; seed=$3
  f=$OUT/_pl_v2_observe_${wind}_${roles}_${seed}.json
  [ -s "$f" ] && return 0
  $PY -B $OUT/_pl_shadow.py --repo $WT --wind $wind --roles $roles --seed $seed --steps 240 --out $f > $OUT/_pl_v2_observe_${wind}_${roles}_${seed}.log 2>&1
  echo "DONE $(date -Is) v2 observe $wind $roles $seed rc=$?"
}
export -f run_one; export OUT PY WT
jobs_list | xargs -P 4 -L 1 bash -c 'run_one "$@"' _
echo "WAVE4 END $(date -Is)"
