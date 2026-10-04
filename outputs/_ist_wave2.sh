#!/usr/bin/env bash
# isTrue round Part 1, census wave 2 (probe v2): scenarios A / B / C at shipped defaults, a v2 repeat of wave 1's
# S east 101 (safe_float key attribution; its harness JSON must equal wave 1's), and a BARE harness run of the same
# seed with no probe at all (the record-only check: eval, fire digests and ff_steps must equal the probe runs').
cd /e/Projects/SAS_wt/istrue || exit 1
PY=/e/Projects/SAS_wt/istrue/.venv/Scripts/python.exe
REPO=E:/Projects/SAS_wt/istrue
run() {  # arm wind seed [harness args...]
  local arm=$1 wind=$2 seed=$3; shift 3
  local stem=outputs/_ist_${arm}_${wind}_${seed}
  "$PY" outputs/_ist_probe.py --census-out ${stem}_census.json -- --repo "$REPO" --wind "$wind" --seed "$seed" \
    --steps 360 --out ${stem}.json --tag ist${arm} "$@" > ${stem}.log 2> ${stem}.err
  echo "DONE $arm $wind $seed exit=$? $(tail -1 ${stem}.log)"
}
bare() {  # wind seed
  local stem=outputs/_ist_bare_$1_$2
  "$PY" outputs/_ffr_harness.py --repo "$REPO" --wind "$1" --seed "$2" --steps 360 --out ${stem}.json \
    --tag istbare > ${stem}.log 2> ${stem}.err
  echo "DONE bare $1 $2 exit=$? $(tail -1 ${stem}.log)"
}
run A east 104 --scenario A &
run Bsc east 104 --scenario B &
run C east 104 --scenario C &
run S2 east 101 &
bare east 101 &
wait
echo "WAVE2 COMPLETE"
