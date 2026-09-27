#!/usr/bin/env bash
# planner round Part 1, wave 3: the break-testing modes on the canonical 13 at 240 steps, pinned
# dfbfbe7 worktree. observe runs via outputs/_pl_verify/_pl_shadow.py (the _gp_probe observe hooks
# + a read-only per-step ingredient recorder); arm_role_str / arm_role_dict via _gp_probe.py
# unchanged. nopatch was cut to the 6 runs already done/in flight (observer purity on those seeds).
WT=/home/user/sas_dfbfbe7
PY=/home/user/SAS/.venv/bin/python
OUT=/home/user/SAS/outputs/_pl_verify
cd "$WT" || exit 1
while pgrep -f "_gp_probe.py --mode nopatch" >/dev/null; do sleep 10; done
echo "WAVE3 START $(date -Is) head=$(git -C $WT rev-parse HEAD) dirty=$(git -C $WT status --porcelain | wc -l)"
jobs_list() {
  for mode in observe arm_role_str arm_role_dict; do
    for s in 101 202 303 404 505; do echo "$mode east half $s"; done
    for s in 101 202 303 404 505; do echo "$mode south half $s"; done
    for s in 101 202 303; do echo "$mode east default $s"; done
  done
}
run_one() {
  mode=$1; wind=$2; roles=$3; seed=$4
  f=$OUT/_pl_v_${mode}_${wind}_${roles}_${seed}.json
  [ -s "$f" ] && return 0
  if [ "$mode" = observe ]; then
    $PY -B $OUT/_pl_shadow.py --repo $WT --wind $wind --roles $roles --seed $seed --steps 240 --out $f > $OUT/_pl_v_${mode}_${wind}_${roles}_${seed}.log 2>&1
  else
    $PY -B outputs/_gp_probe.py --mode $mode --wind $wind --roles $roles --seed $seed --steps 240 --out $f > $OUT/_pl_v_${mode}_${wind}_${roles}_${seed}.log 2>&1
  fi
  echo "DONE $(date -Is) $mode $wind $roles $seed rc=$?"
}
export -f run_one; export OUT PY WT
jobs_list | xargs -P 3 -L 1 bash -c 'run_one "$@"' _
echo "WAVE3 END $(date -Is)"
