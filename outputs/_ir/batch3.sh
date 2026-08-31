#!/bin/sh
# Same as batch.sh but drives _ir_probe3.py (adds the recorded
# _idle_retreat_last_cell field so a post-fix run can be audited for
# last_cell violations directly). Trajectory-identical to _ir_probe2.py.
#
# usage: sh batch3.sh <jobsfile> <concurrency> <logdir>
cd /e/Projects/SAS
JOBS="$1"
CONC="${2:-6}"
LOGD="${3:-outputs/_ir}"
PY=.venv/Scripts/python.exe

mkdir -p "$LOGD"
run_one() {
  phase="$1"; wind="$2"; roles="$3"; seed="$4"
  tag="${phase}_${wind}_${roles}_${seed}"
  out="outputs/_ir_p3_${tag}.json"
  err="$LOGD/run3_${tag}.err"
  $PY outputs/_ir_probe3.py --scenario D --wind "$wind" --roles "$roles" \
      --seeds "$seed" --steps 240 --tag "$tag" >/dev/null 2>"$err"
  rc=$?
  if [ $rc -ne 0 ] || [ ! -s "$out" ]; then
    echo "FAIL $tag rc=$rc size=$(stat -c%s "$out" 2>/dev/null || echo none)"
  else
    echo "OK   $tag $(stat -c%s "$out") $(date +%H:%M:%S)"
  fi
}

n=0
while read -r phase wind roles seed; do
  [ -z "$phase" ] && continue
  case "$phase" in \#*) continue ;; esac
  run_one "$phase" "$wind" "$roles" "$seed" &
  n=$((n + 1))
  if [ $((n % CONC)) -eq 0 ]; then
    wait
  fi
done < "$JOBS"
wait
echo "BATCH DONE $(date +%H:%M:%S)"
