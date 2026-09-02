#!/usr/bin/env bash
# Sequential driver for the recovery-subgraph probe: canonical 13-run sample.
# One process per run (module globals are mutated by apply_scenario_config).
# Ends with one --nopatch control (same combo/seed/steps) so observer-purity of
# the wrappers is checkable by comparing agent_positions_sha256 + eval.
set -u
cd "$(dirname "$0")/.." || exit 1
PY=./.venv/Scripts/python.exe
STEPS=${STEPS:-240}
rm -f outputs/_rh_run_*.json
i=0
run() { # wind roles seed
  i=$((i+1))
  printf '[%s] run %02d/13  %s/%s seed=%s steps=%s\n' "$(date +%H:%M:%S)" "$i" "$1" "$2" "$3" "$STEPS"
  $PY outputs/_rh_probe.py --wind "$1" --roles "$2" --seed "$3" --steps "$STEPS" \
      --out "outputs/_rh_run_$(printf '%02d' $i)_$1_$2_$3.json"
  printf '[%s]   done %02d rc=%s\n' "$(date +%H:%M:%S)" "$i" "$?"
}
for s in 101 202 303 404 505; do run east  half    $s; done
for s in 101 202 303 404 505; do run south half    $s; done
for s in 101 202 303;         do run east  default $s; done
printf '[%s] NOPATCH control: east/half/101\n' "$(date +%H:%M:%S)"
$PY outputs/_rh_probe.py --wind east --roles half --seed 101 --steps "$STEPS" \
    --nopatch --out outputs/_rh_control_nopatch.json
printf '[%s] aggregating\n' "$(date +%H:%M:%S)"
$PY outputs/_rh_probe.py --aggregate --out outputs/_rh_probe.json
printf '[%s] ALL DONE\n' "$(date +%H:%M:%S)"
