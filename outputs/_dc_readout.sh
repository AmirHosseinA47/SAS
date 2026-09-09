#!/usr/bin/env bash
# Depot-cost round: every measurement the report makes, in one command.
#
# The point is that the report can be checked rather than trusted: each section
# below is the exact invocation whose output the corresponding report section
# quotes. Read-only - runs no simulation.
cd /e/Projects/SAS || exit 1
PY=./.venv/Scripts/python.exe
rule() { echo; echo "=============================================================="; echo "$*"; echo "=============================================================="; }

rule "1. KILL SWITCH - mode 0 against the same-instrument e703861 reference"
$PY outputs/_dc_arms.py --mode identity --a dcoff --b dcref --sample canonical

rule "2. THE REFACTOR IS INERT WITH THE FEATURE ARMED - dcA vs e703861 at mode 3"
echo "(the three rtb_log keys this round added are written by the SOURCE's own"
echo " agents.py, so they are absent on the pre-refactor side by construction and"
echo " are excluded; every pre-existing key is still compared)"
$PY outputs/_dc_arms.py --mode identity --a dcA --b dcAref --sample canonical --rtb-new-keys

rule "3. OUTCOMES - canonical 13"
$PY outputs/_dc_arms.py --mode outcomes --a dcoff,dcA,dcB,dcC,dcD --sample canonical
rule "3b. OUTCOMES - fresh 10"
$PY outputs/_dc_arms.py --mode outcomes --a dcoff,dcA,dcB,dcC,dcD --sample fresh
rule "3c. OUTCOMES - canonical + fresh, 23 runs (the never_detected baseline is 1)"
$PY outputs/_dc_arms.py --mode outcomes --a dcoff,dcA,dcB,dcC,dcD --sample both

rule "4. MECHANISM - the return leg, against the 17.5% this round exists to move"
$PY outputs/_dc_arms.py --mode mechanism --a dcA,dcB,dcC,dcD --sample canonical
echo
$PY outputs/_dc_arms.py --mode mechanism --a dcA,dcB,dcC,dcD --sample both

rule "5. DEPOTS - geometry actually used, and per-depot trip attribution"
$PY outputs/_dc_arms.py --mode depots --a dcA,dcB,dcC,dcD --sample both

rule "6. STRANDING - the redefined gate (positional, not battery)"
echo "VALIDATION FIRST: the detector must find the five legs the old gate missed."
$PY outputs/_dc_arms.py --mode stranded --a bsret --sample canonical
echo
$PY outputs/_dc_arms.py --mode stranded --a dcoff,dcA,dcB,dcC,dcD --sample both

rule "7. EXPOSURE - UAV-steps on a burning cell / in smoke"
$PY outputs/_dc_arms.py --mode exposure --a dcoff,dcA,dcB,dcC,dcD --sample both

rule "8. ROUTE_BLOCKED GATE - the --set passthrough must be inert first"
$PY outputs/_dc_rbinert.py --new dcinerta --old rbca --wind east

rule "9. ROUTE_BLOCKED GATE - the brief's comparison, per arm"
for a in dcrbA dcrbB dcrbC dcrbD; do
  echo "--- $a vs ihrest ---"
  $PY outputs/_ffr_rbcompare.py --new "$a" --old ihrest 2>&1 | tail -25
  echo
done

rule "10. ROUTE_BLOCKED SAMPLE as the round's THIRD SAMPLE (never_detected)"
$PY outputs/_dc_rbread.py --arms dcrbA,dcrbB,dcrbC,dcrbD --old rbc

rule "11. TESTS"
echo "--- baseline at e703861 ---"
tail -3 outputs/_dc_pytest_e703861.log
echo "--- at the Part 2 tree ---"
tail -3 outputs/_dc_pytest_part2.log 2>/dev/null || echo "(not yet run)"
