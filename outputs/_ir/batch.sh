#!/bin/sh
# Parallel batch runner for _ir_probe2.py.
# One seed per process so a failure is isolated to one run, and so the
# zero-byte-output failure mode recorded in the project notes is caught
# per-run rather than per-combo.
#
# usage: sh batch.sh <jobsfile> <concurrency> <logdir>
#   jobsfile lines:  <phase> <wind> <roles> <seed>
cd /e/Projects/SAS
JOBS="$1"
CONC="${2:-6}"
LOGD="${3:-outputs/_ir}"
PY=.venv/Scripts/python.exe

mkdir -p "$LOGD"
run_one() {
  phase="$1"; wind="$2"; roles="$3"; seed="$4"
  tag="${phase}_${wind}_${roles}_${seed}"
  out="outputs/_ir_p2_${tag}.json"
  err="$LOGD/run_${tag}.err"
  $PY outputs/_ir_probe2.py --scenario D --wind "$wind" --roles "$roles" \
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
