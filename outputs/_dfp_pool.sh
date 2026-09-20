#!/usr/bin/env bash
# non-burnable-depot round: the wave pool. outputs/_dcd4rb_pool.sh VERBATIM except
# for the two lines marked DFP below - the working directory (this round runs out
# of the depotfireproof WORKTREE, /e/Projects/SAS_wt/dfp, so the shared checkout
# at /e/Projects/SAS is never touched by it) and the interpreter (the worktree has
# no .venv of its own; the parent checkout's is the one with mesa 1.2.1).
# Everything else - no bare wait, validator-backed skip, orphan adoption, detached
# PowerShell launch, bounded re-exec - is that file's, unchanged.
#
# queue line: kind|tag|repo|wind|roles|seeds|steps|extra
# usage (detached):
#   powershell -NoProfile -ExecutionPolicy Bypass -File outputs/_dcd4_launch.ps1 \n#     -Script /e/Projects/SAS_wt/dfp/outputs/_dfp_pool.sh \n#     -Env "QUEUE=outputs/_dfp_queue.txt;STEM=outputs/_dfp;TAGPFX=dfp;LOG=outputs/_dfp_wave.log;WAVE=w1"
cd /e/Projects/SAS_wt/dfp || exit 1   # DFP: the round's worktree, not the shared checkout

QUEUE=${QUEUE:-outputs/_dcd4rb_queue.txt}
WAVE=${WAVE:-wave}
LOG=${LOG:-outputs/_dcd4rb_wave.log}
OUTPFX=${OUTPFX:-outputs/_ffr_}
LOGDIR=${LOGDIR:-outputs/_ffr_logs}
RBDIR=${RBDIR:-outputs}
RBLOGDIR=${RBLOGDIR:-outputs}
HARNESS=${HARNESS:-outputs/_ffr_harness.py}
RBSCRIPT=${RBSCRIPT:-outputs/_rblatch_campaign2.py}
TAGPFX=${TAGPFX:-dr}
MAXPAR=${MAXPAR:-18}
MINFREE_KB=${MINFREE_KB:-3500000}
LAUNCH_GAP=${LAUNCH_GAP:-12}
HB_SECS=${HB_SECS:-60}
IDLE_SLEEP=${IDLE_SLEEP:-30}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-3}
MAX_RESTARTS=${MAX_RESTARTS:-3}
PREREG=${PREREG:-outputs/dfp_prereg.txt}   # DFP: this round's prereg, not dcd4rb's
STEM=${STEM:-outputs/_dcd4rb}
PY=${PY:-/e/Projects/SAS/.venv/Scripts/python.exe}   # DFP: the parent checkout's venv (mesa 1.2.1)
RESTART=${DCD4RB_RESTART:-0}

mkdir -p "$LOGDIR"
exec >>"$LOG" 2>&1

MAIN=$$
printf -v RUNID '%(%Y%m%d-%H%M%S)T-%s' -1 "$$"
LOCK="${STEM}.lock"
STATE="${STEM}_state.txt"
SENT="${STEM}_hb_${RUNID}.stop"
ATTF="${STEM}_attempts.txt"
QDIR="${STEM}_quarantine"
VAL=(outputs/_dcd4rb_validate.py --queue "$QUEUE" --outpfx "$OUTPFX" --logdir "$LOGDIR" --rbdir "$RBDIR" --rblogdir "$RBLOGDIR")

ts() { printf '%(%H:%M:%S)T' -1; }
say() { echo "[$(ts)] $*"; }

# ---- lock: refuse to run twice ---------------------------------------------
if [ -e "$LOCK" ]; then
  read -r lpid lwin < "$LOCK"
  if [ "$lpid" != "$$" ] && [ -n "$lwin" ] && tasklist //FI "PID eq $lwin" //NH 2>/dev/null | grep -qi bash; then
    say "REFUSED: lock $LOCK held by live pool pid=$lpid winpid=$lwin"
    exit 1
  fi
fi
echo "$$ $(cat /proc/$$/winpid 2>/dev/null)" > "$LOCK"

say "POOL START wave=$WAVE runid=$RUNID restart=$RESTART pid=$$ winpid=$(cat /proc/$$/winpid 2>/dev/null) head=$(git rev-parse --short HEAD) dirty_tracked=$(git status --porcelain --untracked-files=no | wc -l) queue=$QUEUE maxpar=$MAXPAR minfree_kb=$MINFREE_KB"
say "ENV $($PY -c 'import sys, mesa; print(sys.version.split()[0], "mesa", mesa.__version__)' 2>&1)  prereg_sha256=$(sha256sum "$PREREG" 2>/dev/null | cut -c1-16) queue_sha256=$(sha256sum "$QUEUE" | cut -c1-16)"
# the harness and the gate record neither the effective BASE_STATION_* values nor
# the commit (dcd4_report.txt section 8); the wave log does
say "SHIPPED $($PY -c 'import common_fixed_variables as c; print(" ".join("%s=%s" % (k, getattr(c, k, "ABSENT")) for k in ("BASE_STATION_MODE","BASE_STATION_RETURN_MECHANISM","BASE_STATION_DEPOTS","BASE_STATION_SPAWN_SPLIT","UAV_RETURN_TO_BASE_RESERVE","BASE_STATION_RETURN_MARGIN","BASE_STATION_DOCK_FIX","BASE_STATION_RETURN_STALL_LIMIT","BASE_STATION_WAYPOINT_FIX","ROUTE_BLOCK_STALE_CLEAR","VICTIM_SEARCHER_HAZARD_RETREAT_RANGE","BASE_STATION_FIREPROOF","BASE_STATION_FIREPROOF_DRY_RUN")))' 2>&1)"

say "SHIPPED-CONTROL $(cd /e/Projects/SAS_wt/base6281542 && $PY -c 'import common_fixed_variables as c; print(" ".join("%s=%s" % (k, getattr(c, k, "ABSENT")) for k in ("BASE_STATION_MODE","BASE_STATION_DEPOTS","BASE_STATION_FIREPROOF")))' 2>&1)"

# ---- queue + attempts --------------------------------------------------------
declare -A LINE_OF OUT_OF ATT RUN_NAME RUN_T0
declare -a PENDING=()
while IFS= read -r ln; do
  ln=${ln//$'\r'/}
  [ -z "$ln" ] && continue
  case "$ln" in \#*) continue;; esac
  IFS='|' read -r kind tag _repo w r s _steps _extra <<< "$ln"
  case "$kind" in
    ff) rr=$r; [ "$r" = default ] && rr=def
        nm="${tag}_${w}_${rr}_${s}"; OUT_OF[$nm]="${OUTPFX}${nm}.json" ;;
    rb) nm="${tag}_D_${w}"; OUT_OF[$nm]="${RBDIR}/_rblatch_camp2_${nm}.json" ;;
    *)  say "BAD QUEUE LINE (kind '$kind'): $ln"; rm -f "$LOCK"; exit 2 ;;
  esac
  LINE_OF[$nm]=$ln
done < "$QUEUE"
TOTAL=${#LINE_OF[@]}
if [ -e "$ATTF" ]; then
  while read -r n k; do [ -n "$n" ] && ATT[$n]=$k; done < "$ATTF"
fi

n_fail=0; n_launched=0; n_gaveup=0; n_forkfail=0
free_kb=0; sims=0
declare -A LIVE=()
printf -v last_event '%(%s)T' -1

write_state() {
  local now; printf -v now '%(%s)T' -1
  printf 'wave=%s total=%d valid=%d running=%d pending=%d launched=%d failed=%d gaveup=%d forkfail=%d free_kb=%s sims_boxwide=%s last_event_age=%ss last_event_epoch=%s\n' \
    "$WAVE" "$TOTAL" "$n_done" "${#RUN_NAME[@]}" "${#PENDING[@]}" "$n_launched" "$n_fail" "$n_gaveup" "$n_forkfail" \
    "$free_kb" "$sims" "$((now-last_event))" "$last_event" > "$STATE.tmp" && mv -f "$STATE.tmp" "$STATE"
}

snapshot() {   # FREE / SIMS / LIVE from one PowerShell call
  LIVE=()
  local k v
  while read -r k v; do
    v=${v//$'\r'/}
    case "$k" in
      FREE) free_kb=$v ;;
      SIMS) sims=$v ;;
      LIVE) v=${v//\\//}; v=${v#./}; LIVE["$v"]=1 ;;
      ERROR) say "SNAPSHOT ERROR $v"; free_kb=0 ;;
    esac
  done < <(powershell -NoProfile -ExecutionPolicy Bypass -File outputs/_dcd4rb_live.ps1 -TagPrefix "$TAGPFX" -HarnessLike "*${HARNESS##*/}*" -RbLike "*${RBSCRIPT##*/}*" -RbDir "$RBDIR" 2>&1)
}

save_attempts() {
  local n
  : > "$ATTF.tmp"
  for n in "${!ATT[@]}"; do echo "$n ${ATT[$n]}" >> "$ATTF.tmp"; done
  mv -f "$ATTF.tmp" "$ATTF"
}

validate_one() { $PY "${VAL[@]}" --one "$1" "${@:2}" 2>&1; }

# one validator pass over the whole queue. An INVALID job is moved aside ONLY if
# no process on the box is still writing it.
snapshot
n_done=0
while read -r status name rest; do
  case "$status" in
    VALID) n_done=$((n_done+1)) ;;
    INVALID)
      if [ -n "${LIVE[${OUT_OF[$name]}]}" ]; then
        say "INVALID-AT-START $name but LIVE in an orphan - left alone: $rest"
      else
        say "INVALID-AT-START $name $rest -> $(validate_one "$name" --quarantine "$QDIR/$RUNID")"
      fi
      PENDING+=("$name") ;;
    MISSING) PENDING+=("$name") ;;
    SUMMARY) say "VALIDATE $name $rest" ;;
  esac
done < <($PY "${VAL[@]}" --all)
say "START STATE wave=$WAVE total=$TOTAL valid=$n_done pending=${#PENDING[@]} live_orphans_this_wave=${#LIVE[@]} sims_boxwide=$sims free_kb=$free_kb"

# ---- heartbeat: separate, disowned, self-terminating -----------------------
heartbeat() {
  local stall=$(( 3*IDLE_SLEEP + LAUNCH_GAP + 600 )) st age pend run
  while :; do
    sleep "$HB_SECS"
    if [ -e "$SENT" ]; then echo "[$(ts)] HEARTBEAT EXIT wave=$WAVE runid=$RUNID (sentinel)"; return; fi
    if ! kill -0 "$MAIN" 2>/dev/null; then echo "[$(ts)] HEARTBEAT EXIT wave=$WAVE runid=$RUNID (MAIN SHELL GONE - pool died; restart with the launcher, completed jobs are kept)"; return; fi
    st=$(cat "$STATE" 2>/dev/null)
    pend=${st#*pending=}; pend=${pend%% *}
    run=${st#*running=}; run=${run%% *}
    local ep=${st##*last_event_epoch=} now; printf -v now '%(%s)T' -1
    age=0; [ -n "$ep" ] && age=$((now-ep))
    if [ "${run:-0}" = 0 ] && [ "${pend:-0}" != 0 ] && [ "${age:-0}" -gt "$stall" ]; then
      echo "[$(ts)] .. alive runid=$RUNID STALL? nothing running, $pend pending, no event for ${age}s | $st"
    else
      echo "[$(ts)] .. alive runid=$RUNID event_age=${age}s | $st"
    fi
  done
}
write_state
heartbeat &
HB=$!
disown "$HB"
say "HEARTBEAT pid=$HB every ${HB_SECS}s -> $LOG ; state file $STATE ; sentinel $SENT"

# ---- launch / reap ----------------------------------------------------------
launch() {   # name -> 0 launched, 1 fork failure
  local name=$1 ln=${LINE_OF[$1]} kind tag repo w r s steps extra prev pid stepsarg=""
  IFS='|' read -r kind tag repo w r s steps extra <<< "$ln"
  prev=$!
  if [ "$kind" = ff ]; then
    # shellcheck disable=SC2086
    $PY "$HARNESS" --repo "$repo" --wind "$w" --roles "$r" --seed "$s" --steps "$steps" \
        --out "${OUT_OF[$name]}" --tag "$tag" $extra \
        > "$LOGDIR/${name}.out" 2> "$LOGDIR/${name}.err" &
  else
    # exactly _ffr_rbgate.sh's per-shard command; --steps only if not the default
    [ "$steps" != 240 ] && stepsarg="--steps $steps"
    # shellcheck disable=SC2086
    $PY "$RBSCRIPT" --wind "$w" --seeds "$s" --tag "$tag" $stepsarg $extra \
        > "$RBLOGDIR/_ffr_rb_${tag}.log" 2>&1 &
  fi
  pid=$!
  if [ -z "$pid" ] || [ "$pid" = "$prev" ]; then
    return 1
  fi
  RUN_NAME[$pid]=$name
  printf -v RUN_T0[$pid] '%(%s)T' -1
  return 0
}

summary_of() {  # one-line result for the DONE line
  local name=$1 ln=${LINE_OF[$1]} kind tag
  IFS='|' read -r kind tag _ <<< "$ln"
  if [ "$kind" = ff ]; then
    tr -d '\r' < "$LOGDIR/${name}.out" 2>/dev/null
  else
    grep ' done ' "$RBLOGDIR/_ffr_rb_${tag}.log" 2>/dev/null | tr -d '\r' | sed 's/^/| /' | tr '\n' ' '
  fi
}

judge() {    # pid rc
  local pid=$1 rc=$2 name=${RUN_NAME[$1]} t0=${RUN_T0[$1]} now v errtail
  unset "RUN_NAME[$pid]" "RUN_T0[$pid]"
  printf -v now '%(%s)T' -1
  v=$(validate_one "$name")
  last_event=$now
  case "$v" in
    VALID*)
      n_done=$((n_done+1))
      say "DONE $name rc=$rc $((now-t0))s $(summary_of "$name") [valid $n_done/$TOTAL]" ;;
    *)
      n_fail=$((n_fail+1))
      ATT[$name]=$(( ${ATT[$name]:-0} + 1 )); save_attempts
      case "${LINE_OF[$name]}" in
        rb\|*) errtail=$(tail -3 "$RBLOGDIR/_ffr_rb_$(cut -d'|' -f2 <<< "${LINE_OF[$name]}").log" 2>/dev/null | tr '\r\n' '  ') ;;
        *)     errtail=$(tail -3 "$LOGDIR/${name}.err" 2>/dev/null | tr '\r\n' '  ') ;;
      esac
      say "FAIL $name rc=$rc $((now-t0))s attempt=${ATT[$name]}/$MAX_ATTEMPTS validator: $v --- err tail: $errtail"
      if [ "${ATT[$name]}" -lt "$MAX_ATTEMPTS" ]; then
        validate_one "$name" --quarantine "$QDIR/$RUNID" > /dev/null
        PENDING+=("$name"); say "REQUEUE $name"
      else
        n_gaveup=$((n_gaveup+1)); say "GAVEUP $name after ${ATT[$name]} attempts"
      fi ;;
  esac
  write_state
}

reap_blocking() {
  local fin rc
  [ ${#RUN_NAME[@]} -eq 0 ] && return 1
  wait -n -p fin "${!RUN_NAME[@]}"; rc=$?
  if [ -z "$fin" ] || [ -z "${RUN_NAME[$fin]}" ]; then
    say "WAIT returned rc=$rc with no known pid (fin='$fin'); re-checking children"
    local p
    for p in "${!RUN_NAME[@]}"; do
      if ! kill -0 "$p" 2>/dev/null; then wait "$p"; judge "$p" "$?"; fi
    done
    return 0
  fi
  judge "$fin" "$rc"
}

reap_nonblocking() {
  local p
  for p in "${!RUN_NAME[@]}"; do
    if ! kill -0 "$p" 2>/dev/null; then wait "$p"; judge "$p" "$?"; fi
  done
}

main_loop() {
  local name deferred_round=0
  while [ ${#PENDING[@]} -gt 0 ] || [ ${#RUN_NAME[@]} -gt 0 ]; do
    reap_nonblocking
    if [ ${#PENDING[@]} -gt 0 ] && [ ${#RUN_NAME[@]} -lt "$MAXPAR" ]; then
      snapshot
      write_state
      if [ "${free_kb:-0}" -gt "$MINFREE_KB" ]; then
        local i picked=-1
        for i in "${!PENDING[@]}"; do
          if [ -z "${LIVE[${OUT_OF[${PENDING[$i]}]}]}" ]; then picked=$i; break; fi
        done
        if [ "$picked" -ge 0 ]; then
          name=${PENDING[$picked]}
          local pre; pre=$(validate_one "$name")
          case "$pre" in
            VALID*)
              unset "PENDING[$picked]"; PENDING=("${PENDING[@]}")
              n_done=$((n_done+1)); printf -v last_event '%(%s)T' -1
              say "ADOPTED $name (already VALID - finished by an orphan) [valid $n_done/$TOTAL]"
              write_state; continue ;;
            INVALID*)
              say "PRE-LAUNCH $name was $pre -> $(validate_one "$name" --quarantine "$QDIR/$RUNID")" ;;
          esac
          if launch "$name"; then
            unset "PENDING[$picked]"; PENDING=("${PENDING[@]}")
            n_launched=$((n_launched+1)); printf -v last_event '%(%s)T' -1
            say "LAUNCH $name running=${#RUN_NAME[@]} free_kb=$free_kb sims_boxwide=$sims attempt=$(( ${ATT[$name]:-0} + 1 ))"
            write_state
            sleep "$LAUNCH_GAP"
          else
            n_forkfail=$((n_forkfail+1))
            local back=$(( 30 * (2 ** (n_forkfail > 4 ? 4 : n_forkfail-1)) ))
            say "FORKFAIL $name (\$! unchanged) count=$n_forkfail - backing off ${back}s"
            write_state
            sleep "$back"
          fi
          continue
        fi
        if [ $((deferred_round % 10)) -eq 0 ]; then
          say "DEFERRED ${#PENDING[@]} pending job(s) are live in orphaned processes: ${!LIVE[*]}"
        fi
        deferred_round=$((deferred_round+1))
        if [ ${#RUN_NAME[@]} -eq 0 ]; then
          sleep "$IDLE_SLEEP"
          snapshot
          local keep=() n
          for n in "${PENDING[@]}"; do
            if [ -z "${LIVE[${OUT_OF[$n]}]}" ] && validate_one "$n" | grep -q '^VALID'; then
              n_done=$((n_done+1)); printf -v last_event '%(%s)T' -1; say "ADOPTED $n (orphan finished, VALID) [valid $n_done/$TOTAL]"
            else
              keep+=("$n")
            fi
          done
          PENDING=("${keep[@]}")
          write_state
          continue
        fi
      else
        say "THROTTLE free_kb=$free_kb <= $MINFREE_KB running=${#RUN_NAME[@]}"
        if [ ${#RUN_NAME[@]} -eq 0 ]; then sleep "$IDLE_SLEEP"; continue; fi
      fi
    fi
    if [ ${#RUN_NAME[@]} -gt 0 ]; then
      reap_blocking
    else
      sleep "$IDLE_SLEEP"
    fi
  done
}

keep=()
for n in "${PENDING[@]}"; do
  if [ "${ATT[$n]:-0}" -ge "$MAX_ATTEMPTS" ]; then say "SKIP-GAVEUP $n (attempts=${ATT[$n]})"; n_gaveup=$((n_gaveup+1)); else keep+=("$n"); fi
done
PENDING=("${keep[@]}")

main_loop
say "MAIN LOOP LEFT pending=${#PENDING[@]} running=${#RUN_NAME[@]}"

# ---- final: validate everything, check the box, then (and only then) mark ----
final=$($PY "${VAL[@]}" --all 2>&1)
summary=$(echo "$final" | grep '^SUMMARY')
echo "$final" | grep -v '^VALID' | sed "s/^/[$(ts)] FINAL /"
snapshot
say "FINAL wave=$WAVE $summary live_this_wave=${#LIVE[@]} sims_boxwide=$sims"
valid=${summary#*valid=}; valid=${valid%% *}
touch "$SENT"
if [ "$valid" = "$TOTAL" ] && [ ${#LIVE[@]} -eq 0 ]; then
  rm -f "$LOCK"
  say "ALL_DCD4RB_COMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL launched=$n_launched failed=$n_fail forkfail=$n_forkfail"
  exit 0
fi
if [ "$RESTART" -lt "$MAX_RESTARTS" ] && [ "$n_gaveup" -eq 0 ]; then
  say "POOL INCOMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL - re-exec in 60s (restart $((RESTART+1))/$MAX_RESTARTS); orphans, if any, are adopted"
  # the lock is KEPT: exec preserves $$, so the re-exec passes its own lock check
  sleep 60
  export DCD4RB_RESTART=$((RESTART+1))
  exec bash "$0"
fi
rm -f "$LOCK"
say "DCD4RB_POOL_INCOMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL gaveup=$n_gaveup - NOT restarting; relaunch with outputs/_dcd4_launch.ps1 after reading the FAIL lines"
exit 2
