#!/usr/bin/env bash
# Fill the 5 runs missing from the prior session's 13x3 matrix.
# One seed per process (safe per sas-eval-runtime memory); plain & + wait.
cd /e/Projects/SAS || exit 1
PY=./.venv/Scripts/python.exe
mkdir -p outputs/_bg_logs

go () { # mode wind roles seed
  local m=$1 w=$2 r=$3 s=$4
  local rr=$r; [ "$r" = "default" ] && rr=def
  local tag="${m}_${w}_${rr}_${s}"
  $PY outputs/_bg_probe.py --mode "$m" --wind "$w" --roles "$r" --seed "$s" \
      --steps 240 --out "outputs/_bg_run_${tag}.json" \
      > "outputs/_bg_logs/fill_${tag}.out" 2> "outputs/_bg_logs/fill_${tag}.err"
  echo "DONE $tag rc=$? size=$(stat -c%s "outputs/_bg_run_${tag}.json" 2>/dev/null || echo 0)"
}

go observe east  half 202 &
go observe south half 303 &
go observe south half 505 &
go nopatch south half 404 &
go arm     east  half 404 &
wait
echo "ALL_FILL_COMPLETE"
