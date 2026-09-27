#!/usr/bin/env bash
# planner round Part 1, wave 2: the break-testing modes only (observe, arm_role_str,
# arm_role_dict) on the canonical 13 at 240 steps, pinned dfbfbe7 worktree. nopatch was cut
# to the 6 runs already done/in flight (observer-purity check on those seeds only).
WT=/home/user/sas_dfbfbe7
PY=/home/user/SAS/.venv/bin/python
OUT=/home/user/SAS/outputs/_pl_verify
cd "$WT" || exit 1
while pgrep -f "_gp_probe.py --mode nopatch" >/dev/null; do sleep 10; done
echo "WAVE2 START $(date -Is) head=$(git -C $WT rev-parse HEAD) dirty=$(git -C $WT status --porcelain | wc -l)"
jobs_list() {
  for mode in observe arm_role_str arm_role_dict; do
    for s in 101 202 303 404 505; do echo "$mode east half $s"; done
    for s in 101 202 303 404 505; do echo "$mode south half $s"; done
    for s in 101 202 303; do echo "$mode east default $s"; done
  done
}
jobs_list | xargs -P 3 -L 1 bash -c 'mode=$0; wind=$1; roles=$2; seed=$3; f='"$OUT"'/_pl_v_${mode}_${wind}_${roles}_${seed}.json; [ -s "$f" ] && exit 0; '"$PY"' -B outputs/_gp_probe.py --mode $mode --wind $wind --roles $roles --seed $seed --steps 240 --out $f > '"$OUT"'/_pl_v_${mode}_${wind}_${roles}_${seed}.log 2>&1; echo "DONE $(date -Is) $mode $wind $roles $seed rc=$?"'
echo "WAVE2 END $(date -Is)"
