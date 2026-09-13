#!/usr/bin/env bash
# dcd4 round: restartable, heartbeat-logged pool for the fourth-seed-set wave.
#
# Written against the three launch/chain failures this project has recorded:
#   * chain 2 (depot round): a bare `wait` also waited on the never-ending
#     heartbeat. HERE: there is NO bare `wait` anywhere. Runs are reaped with
#     `wait -n -p fin <explicit pids>`, and the heartbeat is disowned AND exits
#     by itself when the sentinel appears or the main shell is gone.
#   * dock-fix wave: `nohup ... &` from the tool shell was orphaned and Git-Bash
#     then failed to fork. HERE: launched detached via PowerShell Start-Process
#     of Git bash (outputs/_dcd4_launch.ps1); a launch only counts if `$!`
#     changed; a runaway failure of the main loop re-execs the pool (bounded),
#     which then ADOPTS still-running orphans instead of double-launching them.
#   * chain 1 (depot round): died with no diagnostic. HERE: every state change
#     is a timestamped log line, the heartbeat prints progress (not just
#     "alive") and flags a stall, and the final marker is written only when the
#     validator says every queued run is complete.
#
# Restartable: a run is skipped only if outputs/_dcd4_validate.py says VALID
# (parsed JSON matching the queue line, stdout sha, .out summary) - not `-s`.
# A run whose --out path is live in ANY python.exe on the box is never
# launched again; it is deferred until it exits and is then validated.
#
# usage (detached): powershell -NoProfile -ExecutionPolicy Bypass -File outputs/_dcd4_launch.ps1
# log: outputs/_dcd4_wave.log
cd /e/Projects/SAS || exit 1

QUEUE=${QUEUE:-outputs/_dcd4_queue.txt}
LOG=${LOG:-outputs/_dcd4_wave.log}
OUTPFX=${OUTPFX:-outputs/_ffr_}
LOGDIR=${LOGDIR:-outputs/_ffr_logs}
HARNESS=${HARNESS:-outputs/_ffr_harness.py}
TAGPFX=${TAGPFX:-d4}
MAXPAR=${MAXPAR:-12}
MINFREE_KB=${MINFREE_KB:-4000000}
LAUNCH_GAP=${LAUNCH_GAP:-12}
HB_SECS=${HB_SECS:-60}
IDLE_SLEEP=${IDLE_SLEEP:-30}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-3}
MAX_RESTARTS=${MAX_RESTARTS:-3}
PREREG=${PREREG:-outputs/dcd4_prereg.txt}
STEM=${STEM:-outputs/_dcd4}
PY=./.venv/Scripts/python.exe
RESTART=${DCD4_RESTART:-0}

mkdir -p "$LOGDIR"
exec >>"$LOG" 2>&1

MAIN=$$
printf -v RUNID '%(%Y%m%d-%H%M%S)T-%s' -1 "$$"
LOCK="${STEM}.lock"
STATE="${STEM}_state.txt"
SENT="${STEM}_hb_${RUNID}.stop"
ATTF="${STEM}_attempts.txt"
QDIR="${STEM}_quarantine"

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

say "POOL START runid=$RUNID restart=$RESTART pid=$$ winpid=$(cat /proc/$$/winpid 2>/dev/null) head=$(git rev-parse --short HEAD) dirty_tracked=$(git status --porcelain --untracked-files=no | wc -l) queue=$QUEUE maxpar=$MAXPAR minfree_kb=$MINFREE_KB"
say "ENV $($PY -c 'import sys, mesa; print(sys.version.split()[0], "mesa", mesa.__version__)' 2>&1)  prereg_sha256=$(sha256sum "$PREREG" 2>/dev/null | cut -c1-16) queue_sha256=$(sha256sum "$QUEUE" | cut -c1-16)"

# ---- queue + attempts --------------------------------------------------------
declare -A LINE_OF ATT RUN_NAME RUN_T0
declare -a PENDING=()
while IFS= read -r ln; do
  ln=${ln//$'\r'/}
  [ -z "$ln" ] && continue
  case "$ln" in \#*) continue;; esac
  IFS='|' read -r tag _repo w r s _extra <<< "$ln"
  rr=$r; [ "$r" = default ] && rr=def
  LINE_OF["${tag}_${w}_${rr}_${s}"]=$ln
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
  printf 'total=%d valid=%d running=%d pending=%d launched=%d failed=%d gaveup=%d forkfail=%d free_kb=%s sims_boxwide=%s last_event_age=%ss last_event_epoch=%s\n' \
    "$TOTAL" "$n_done" "${#RUN_NAME[@]}" "${#PENDING[@]}" "$n_launched" "$n_fail" "$n_gaveup" "$n_forkfail" \
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
  done < <(powershell -NoProfile -ExecutionPolicy Bypass -File outputs/_dcd4_live.ps1 -TagPrefix "$TAGPFX" -HarnessLike "*${HARNESS##*/}*" 2>&1)
}

save_attempts() {
  local n
  : > "$ATTF.tmp"
  for n in "${!ATT[@]}"; do echo "$n ${ATT[$n]}" >> "$ATTF.tmp"; done
  mv -f "$ATTF.tmp" "$ATTF"
}

validate_one() { $PY outputs/_dcd4_validate.py --queue "$QUEUE" --outpfx "$OUTPFX" --logdir "$LOGDIR" --one "$1" "${@:2}" 2>&1; }

# one validator pass over the whole queue, in queue order. An INVALID run is
# moved aside ONLY if no process on the box is still writing it (a live orphan
# of a dead pool can look invalid mid-write, and its files are open).
snapshot
n_done=0
while read -r status name rest; do
  case "$status" in
    VALID) n_done=$((n_done+1)) ;;
    INVALID)
      if [ -n "${LIVE[${OUTPFX}${name}.json]}" ]; then
        say "INVALID-AT-START $name but LIVE in an orphan - left alone: $rest"
      else
        say "INVALID-AT-START $name $rest -> $(validate_one "$name" --quarantine "$QDIR/$RUNID")"
      fi
      PENDING+=("$name") ;;
    MISSING) PENDING+=("$name") ;;
    SUMMARY) say "VALIDATE $name $rest" ;;
  esac
done < <($PY outputs/_dcd4_validate.py --queue "$QUEUE" --outpfx "$OUTPFX" --logdir "$LOGDIR" --all)
say "START STATE total=$TOTAL valid=$n_done pending=${#PENDING[@]} live_orphans_this_wave=${#LIVE[@]} sims_boxwide=$sims free_kb=$free_kb"

# ---- heartbeat: separate, disowned, self-terminating -----------------------
heartbeat() {
  local stall=$(( 3*IDLE_SLEEP + LAUNCH_GAP + 600 )) st age pend run
  while :; do
    sleep "$HB_SECS"
    if [ -e "$SENT" ]; then echo "[$(ts)] HEARTBEAT EXIT runid=$RUNID (sentinel)"; return; fi
    if ! kill -0 "$MAIN" 2>/dev/null; then echo "[$(ts)] HEARTBEAT EXIT runid=$RUNID (MAIN SHELL GONE - pool died; restart with the launcher, completed runs are kept)"; return; fi
    st=$(cat "$STATE" 2>/dev/null)
    age=${st##*last_event_age=}; age=${age%%s*}
    pend=${st#*pending=}; pend=${pend%% *}
    run=${st#*running=}; run=${run%% *}
    local ep=${st##*last_event_epoch=} now; printf -v now '%(%s)T' -1
    [ -n "$ep" ] && age=$((now-ep))
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
  local name=$1 ln=${LINE_OF[$1]} tag repo w r s extra prev pid
  IFS='|' read -r tag repo w r s extra <<< "$ln"
  prev=$!
  # shellcheck disable=SC2086
  $PY "$HARNESS" --repo "$repo" --wind "$w" --roles "$r" --seed "$s" --steps 240 \
      --out "${OUTPFX}${name}.json" --tag "$tag" $extra \
      > "$LOGDIR/${name}.out" 2> "$LOGDIR/${name}.err" &
  pid=$!
  if [ -z "$pid" ] || [ "$pid" = "$prev" ]; then
    return 1
  fi
  RUN_NAME[$pid]=$name
  printf -v RUN_T0[$pid] '%(%s)T' -1
  return 0
}

judge() {    # pid rc
  local pid=$1 rc=$2 name=${RUN_NAME[$1]} t0=${RUN_T0[$1]} now v
  unset "RUN_NAME[$pid]" "RUN_T0[$pid]"
  printf -v now '%(%s)T' -1
  v=$($PY outputs/_dcd4_validate.py --queue "$QUEUE" --outpfx "$OUTPFX" --logdir "$LOGDIR" --one "$name" 2>&1)
  last_event=$now
  case "$v" in
    VALID*)
      n_done=$((n_done+1))
      say "DONE $name rc=$rc $((now-t0))s $(tr -d '\r' < "$LOGDIR/${name}.out" 2>/dev/null) [valid $n_done/$TOTAL]" ;;
    *)
      n_fail=$((n_fail+1))
      ATT[$name]=$(( ${ATT[$name]:-0} + 1 )); save_attempts
      say "FAIL $name rc=$rc $((now-t0))s attempt=${ATT[$name]}/$MAX_ATTEMPTS validator: $v --- err tail: $(tail -3 "$LOGDIR/${name}.err" 2>/dev/null | tr '\r\n' '  ')"
      if [ "${ATT[$name]}" -lt "$MAX_ATTEMPTS" ]; then
        $PY outputs/_dcd4_validate.py --queue "$QUEUE" --outpfx "$OUTPFX" --logdir "$LOGDIR" --one "$name" --quarantine "$QDIR/$RUNID" > /dev/null 2>&1
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
        # first pending run that is not live anywhere on the box
        local i picked=-1
        for i in "${!PENDING[@]}"; do
          if [ -z "${LIVE[${OUTPFX}${PENDING[$i]}.json]}" ]; then picked=$i; break; fi
        done
        if [ "$picked" -ge 0 ]; then
          name=${PENDING[$picked]}
          # never launch over a result: an orphan may have finished it since the
          # last look, or a failed attempt may have left files behind
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
        # every pending run is live somewhere: an orphan from a dead pool
        if [ $((deferred_round % 10)) -eq 0 ]; then
          say "DEFERRED ${#PENDING[@]} pending run(s) are live in orphaned processes: ${!LIVE[*]}"
        fi
        deferred_round=$((deferred_round+1))
        if [ ${#RUN_NAME[@]} -eq 0 ]; then
          sleep "$IDLE_SLEEP"
          # an orphan that has exited is VALID (drop it) or not (keep it pending)
          local keep=() n
          for n in "${PENDING[@]}"; do
            if $PY outputs/_dcd4_validate.py --queue "$QUEUE" --outpfx "$OUTPFX" --logdir "$LOGDIR" --one "$n" 2>/dev/null | grep -q '^VALID'; then
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

# drop GAVEUP runs from PENDING before starting
keep=()
for n in "${PENDING[@]}"; do
  if [ "${ATT[$n]:-0}" -ge "$MAX_ATTEMPTS" ]; then say "SKIP-GAVEUP $n (attempts=${ATT[$n]})"; n_gaveup=$((n_gaveup+1)); else keep+=("$n"); fi
done
PENDING=("${keep[@]}")

main_loop
say "MAIN LOOP LEFT pending=${#PENDING[@]} running=${#RUN_NAME[@]}"

# ---- final: validate everything, check the box, then (and only then) mark ----
final=$($PY outputs/_dcd4_validate.py --queue "$QUEUE" --outpfx "$OUTPFX" --logdir "$LOGDIR" --all 2>&1)
summary=$(echo "$final" | grep '^SUMMARY')
echo "$final" | grep -v '^VALID' | sed "s/^/[$(ts)] FINAL /"
snapshot
say "FINAL $summary live_this_wave=${#LIVE[@]} sims_boxwide=$sims"
valid=${summary#*valid=}; valid=${valid%% *}
touch "$SENT"
if [ "$valid" = "$TOTAL" ] && [ ${#LIVE[@]} -eq 0 ]; then
  rm -f "$LOCK"
  say "ALL_DCD4_COMPLETE runid=$RUNID valid=$valid/$TOTAL launched=$n_launched failed=$n_fail forkfail=$n_forkfail"
  exit 0
fi
if [ "$RESTART" -lt "$MAX_RESTARTS" ] && [ "$n_gaveup" -eq 0 ]; then
  say "POOL INCOMPLETE runid=$RUNID valid=$valid/$TOTAL - re-exec in 60s (restart $((RESTART+1))/$MAX_RESTARTS); orphans, if any, are adopted"
  sleep 60
  export DCD4_RESTART=$((RESTART+1))
  exec bash "$0"
fi
rm -f "$LOCK"
say "DCD4_POOL_INCOMPLETE runid=$RUNID valid=$valid/$TOTAL gaveup=$n_gaveup - NOT restarting; relaunch with outputs/_dcd4_launch.ps1 after reading the FAIL lines"
exit 2
