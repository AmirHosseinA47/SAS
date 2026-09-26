#!/usr/bin/env bash
# Carrying-leg round: the full suite, SERIAL, with the campaign's standard command
# (copied from outputs/_ug_pytest.sh; every change from it is marked CL). Serial is
# not optional: tests/test_wind_aware_trajectory_regression.py records
# order-dependent siblings, so a sharded run can move the failing NAME SET by itself.
#   VARIANT=base  no plugin - the checkout as it is
#   VARIANT=p0    plugin loaded, CL_SIM=0 (control for the plugin's early import)
#   VARIANT=sim   plugin loaded, CL_SIM=<comma list of FF_EXIT_LEG_*=V> (switches ON),
#                 SIMNAME=<label> required, part of the log name. The label is TIED to
#                 the list (design 8.5 pre-names the expected failures per variant),
#                 exact string, order MODE,HOLD,SERVED:
#                   E1  FF_EXIT_LEG_MODE=1                (only if clE1 runs)
#                   E2  FF_EXIT_LEG_MODE=2
#                   H   FF_EXIT_LEG_HOLD=1
#                   SN  FF_EXIT_LEG_SERVED=1
#                   A   FF_EXIT_LEG_MODE=2,FF_EXIT_LEG_HOLD=1,FF_EXIT_LEG_SERVED=1
#                   A2  the clA2 re-run (design 9.6: >= 2 still-passing fixes, not A):
#                       one of MODE=2+HOLD=1, MODE=2+SERVED=1, HOLD=1+SERVED=1,
#                       MODE=1+HOLD=1, MODE=1+SERVED=1, MODE=1+HOLD=1+SERVED=1
#                 Anything else is REFUSED (SERVED=2 is not built, D-1).
#   VARIANT=post  no plugin, after the source flip (Part 3)
#   CLTAG         log tag, default cl1; must start with "cl" (this round's names)
# Logs: outputs/_<CLTAG>_pytest_<VARIANT>[_<SIMNAME>].log / .xml  (SIMNAME only for sim)
# Refused: PYTEST_ADDOPTS / PYTEST_PLUGINS set (they change the collected set).
# Launch detached, e.g.:
#   powershell -File outputs/_dcd4_launch.ps1 \
#     -Env "VARIANT=sim;SIMNAME=A;CL_SIM=FF_EXIT_LEG_MODE=2,FF_EXIT_LEG_HOLD=1,FF_EXIT_LEG_SERVED=1" \
#     -Script /e/Projects/SAS/outputs/_cl_pytest.sh
set -u
cd /e/Projects/SAS || exit 1
export MPLBACKEND=Agg
V="${VARIANT:?VARIANT unset}"
# CL: an inherited -k / -x / plugin would silently change the collected set, and G6a /
# G6b compare failing-name sets and passed counts (review finding 5).
for e in PYTEST_ADDOPTS PYTEST_PLUGINS; do
  if [ -n "${!e:-}" ]; then
    echo "CL_PYTEST REFUSED: $e is set ('${!e}'); unset it" >&2; exit 2
  fi
done
TAG="${CLTAG:-cl1}"                                   # CL: CLTAG, default cl1
SN="${SIMNAME:-}"                                     # CL: SIMNAME
PY=/e/Projects/SAS/.venv/Scripts/python.exe           # CL: absolute interpreter path
P=()
# CL: tag / label must be plain words (they become file names).
case "$TAG" in *[!A-Za-z0-9]*|"") echo "CL_PYTEST REFUSED: bad CLTAG '$TAG'" >&2; exit 2 ;; esac
# CL: and the tag must carry this round's prefix (review finding 6: CLTAG=ug1 would
# write beside the ungated round's tracked logs).
case "$TAG" in cl*) ;; *) echo "CL_PYTEST REFUSED: CLTAG '$TAG' does not start with cl" >&2; exit 2 ;; esac
case "$V" in
  base|post|p0)
    if [ -n "$SN" ]; then                             # CL: SIMNAME only labels a sim
      echo "CL_PYTEST REFUSED: SIMNAME='$SN' given for VARIANT=$V (sim only)" >&2; exit 2
    fi
    SUFFIX="$V" ;;
  sim)
    case "$SN" in *[!A-Za-z0-9]*|"") echo "CL_PYTEST REFUSED: VARIANT=sim needs SIMNAME=[A-Za-z0-9]+ (got '$SN')" >&2; exit 2 ;; esac
    CS="${CL_SIM:-}"
    case "$CS" in
      ""|0) echo "CL_PYTEST REFUSED: VARIANT=sim needs a non-zero CL_SIM switch list" >&2; exit 2 ;;
    esac
    # CL: only NAME=INT list characters (no newline / CR / space: the value goes into
    # the START line; review finding 2).
    case "$CS" in
      *[!ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_=,]*)
        echo "CL_PYTEST REFUSED: CL_SIM has a character outside [A-Z0-9_=,]" >&2; exit 2 ;;
    esac
    # CL: the label is tied to the switch list (review finding 1).
    KM=FF_EXIT_LEG_MODE; KH=FF_EXIT_LEG_HOLD; KS=FF_EXIT_LEG_SERVED
    case "$SN" in
      E1) OKS="$KM=1" ;;
      E2) OKS="$KM=2" ;;
      H)  OKS="$KH=1" ;;
      SN) OKS="$KS=1" ;;
      A)  OKS="$KM=2,$KH=1,$KS=1" ;;
      A2) OKS="$KM=2,$KH=1 $KM=2,$KS=1 $KH=1,$KS=1 $KM=1,$KH=1 $KM=1,$KS=1 $KM=1,$KH=1,$KS=1" ;;
      *) echo "CL_PYTEST REFUSED: unknown SIMNAME '$SN' (E1 E2 H SN A A2)" >&2; exit 2 ;;
    esac
    hit=0
    for w in $OKS; do [ "$CS" = "$w" ] && hit=1; done
    if [ "$hit" -ne 1 ]; then
      echo "CL_PYTEST REFUSED: SIMNAME=$SN needs CL_SIM in {$OKS} (got '$CS')" >&2; exit 2
    fi
    SUFFIX="${V}_${SN}" ;;
  *) echo "CL_PYTEST REFUSED: unknown VARIANT $V" >&2; exit 2 ;;
esac
LOG="outputs/_${TAG}_pytest_${SUFFIX}.log"
XML="outputs/_${TAG}_pytest_${SUFFIX}.xml"
# CL: never write into a path that already exists (tag-collision lesson; spec A4).
for f in "$LOG" "$XML"; do
  if [ -e "$f" ]; then echo "CL_PYTEST REFUSED: $f already exists" >&2; exit 2; fi
done
case "$V" in
  base|post) unset CL_SIM ;;                          # CL: plugin not loaded
  p0)  export CL_SIM=0; P=(-p outputs._cl_simplugin) ;;
  sim) export CL_SIM; P=(-p outputs._cl_simplugin) ;;
esac
# CL: claim the log atomically (review finding 7): under noclobber bash creates it
# with O_EXCL, so of two identical launches only one gets past here; the loser exits
# before writing anything. Every later write to "$LOG" appends.
set -o noclobber
if ! : > "$LOG"; then
  echo "CL_PYTEST REFUSED: $LOG was created by another launch (noclobber)" >&2; exit 2
fi
{
  echo "CL_PYTEST START variant=$V simname=${SN:--} cl_sim=${CL_SIM:--} tag=$TAG" \
       "head=$(git rev-parse --short HEAD)" \
       "branch=$(git branch --show-current)" \
       "dirty_tracked=$(git status --porcelain -uno | wc -l)" \
       "bashpid=$$ start=$(date '+%F %T')"
  "$PY" -B -c "import sys, mesa; print('python', sys.version); print('mesa', mesa.__version__)"
  # CL: the source's own switch values, from a SEPARATE process without the plugin, so
  # a base/post log shows the tree it ran on (review finding 4; the pool's SHIPPED
  # line is the precedent). Cannot affect the suite.
  "$PY" -B -c "import common_fixed_variables as c, agents as a; print('CL_PYTEST SHIPPED cfv', c.FF_EXIT_LEG_MODE, c.FF_EXIT_LEG_HOLD, c.FF_EXIT_LEG_SERVED, 'accessors', a.ff_exit_leg_mode(), a.ff_exit_leg_hold(), a.ff_exit_leg_served(), 'files', c.__file__, a.__file__)"
  git status --porcelain -uno
} >> "$LOG" 2>&1
# CL: -B (spec A3: no __pycache__ written into the repo).
"$PY" -B -m pytest tests -p no:cacheprovider -q ${P[@]+"${P[@]}"} --junitxml="$XML" >> "$LOG" 2>&1
rc=$?
# CL: the plugin's end-of-session check (none for base/post).
if [ ${#P[@]} -eq 0 ]; then
  chk=none
elif grep -q '^CLSIM END CHECK OK' "$LOG"; then
  chk=OK
elif grep -q '^CLSIM END CHECK MISMATCH' "$LOG"; then
  chk=MISMATCH
else
  chk=ABSENT
fi
echo "CL_PYTEST_COMPLETE variant=$V simname=${SN:--} rc=$rc clsim_check=$chk end=$(date '+%F %T')" >> "$LOG"
