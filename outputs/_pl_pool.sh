#!/usr/bin/env bash
# PL: planner round: the wave pool. outputs/_cl_pool.sh (itself _ug_pool.sh / _dcd4rb_pool.sh)
# with the carrying-leg specifics replaced; the mechanisms are unchanged: no bare wait
# (wait -n -p), validator-backed skip (outputs/_pl_validate.py), orphan adoption from a
# box-wide process snapshot (outputs/_pl_live.ps1), a disowned self-terminating heartbeat,
# a lock, bounded re-exec, and SOURCE CHANGED: the planner source digest (src=), everything
# else a run executes or is judged by (ext=, incl. the dfbfbe7 worktree's HEAD and tracked
# status) and the full HEAD are logged on every LAUNCH / DONE line, and any change stops
# launches (running jobs finish; no re-exec).
# PL: differences from _cl_pool.sh:
#   - the INSTRUMENT is per line (kind): ff plain outputs/_ffr_harness.py, fo the stock
#     sidecar outputs/_pl_obs_stock.py, fc the CRN sidecar outputs/_pl_obs_crn.py, rb a gate
#     shard run by <repo>/outputs/_rblatch_campaign2.py (the campaign imports and writes into
#     the checkout it lives in; its log goes to outputs/_ffr_rb_<tag>.log here). No HARNESS env.
#   - tags ^pl[A-Za-z0-9]+$; repos E:/Projects/SAS or the pinned E:/Projects/SAS_wt/basedfbfbe7
#     (which must then be at dfbfbe7 and clean); the queue rules (declared --set keys, FM2P_CRN
#     only on fc lines) live in _pl_validate.read_queue, whose failure REFUSES the start.
# queue line: kind|tag|repo|wind|roles|seeds|steps|extra
# usage (detached; one pool per queue file, each with its own STEM and LOG):
#   powershell -NoProfile -ExecutionPolicy Bypass -File outputs/_dcd4_launch.ps1
#     -Script /e/Projects/SAS/outputs/_pl_pool.sh
#     -Env "QUEUE=outputs/_pl_q1.txt;STEM=outputs/_pl_q1;LOG=outputs/_pl_q1_wave.log;WAVE=q1"
cd /e/Projects/SAS || exit 1

QUEUE=${QUEUE:-}
WAVE=${WAVE:-wave}
LOG=${LOG:-outputs/_pl_wave.log}
OUTPFX=outputs/_ffr_
LOGDIR=outputs/_ffr_logs
TAGPFX=pl
MAXPAR=${MAXPAR:-12}
MINFREE_KB=${MINFREE_KB:-3500000}
LAUNCH_GAP=${LAUNCH_GAP:-10}
HB_SECS=${HB_SECS:-60}
IDLE_SLEEP=${IDLE_SLEEP:-30}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-3}
MAX_RESTARTS=${MAX_RESTARTS:-3}
PREREG=${PREREG:-outputs/planner_part1.txt}
STEM=${STEM:-outputs/_pl_pool}
PY=${PY:-/e/Projects/SAS/.venv/Scripts/python.exe}
RESTART=${PL_RESTART:-0}
BASE_WT=/e/Projects/SAS_wt/basedfbfbe7
BASE_SHA=dfbfbe7

pl_own_path() {
  local p; p=$(cygpath -u -- "$1" 2>/dev/null) || p=$1
  p=$(realpath -m -- "$p" 2>/dev/null) || return 1
  p=${p,,}
  case "$p" in /e/projects/sas/outputs/_pl_*) return 0 ;; /e/projects/sas|/e/projects/sas/*) return 1 ;; esac
  return 0
}
pre_refuse=""
pl_own_path "$LOG" || pre_refuse="LOG=$LOG is not a planner path (outputs/_pl_*)"
git ls-files --error-unmatch -- "$LOG" >/dev/null 2>&1 && pre_refuse="LOG=$LOG is a TRACKED file"
pl_own_path "$STEM" || pre_refuse="${pre_refuse:+$pre_refuse; }STEM=$STEM is not a planner path"
if [ -n "$pre_refuse" ]; then
  printf '[%(%H:%M:%S)T] REFUSED: %s (pid=%s)\n' -1 "$pre_refuse" "$$" | tee -a outputs/_pl_wave.log >&2
  exit 2
fi

mkdir -p "$LOGDIR"
exec >>"$LOG" 2>&1

MAIN=$$
printf -v RUNID '%(%Y%m%d-%H%M%S)T-%s' -1 "$$"
LOCK="${STEM}.lock"
STATE="${STEM}_state.txt"
SENT="${STEM}_hb_${RUNID}.stop"
ATTF="${STEM}_attempts.txt"
QDIR="${STEM}_quarantine"
VAL=(outputs/_pl_validate.py --queue "$QUEUE")

ts() { printf '%(%H:%M:%S)T' -1; }
say() { echo "[$(ts)] $*"; }

PL_SRC=(agents.py common_fixed_variables.py wildfire_model.py src_extension/adaptation/global_adaptation_generator.py
        src_extension/adaptation/role_option_values.py src_extension/planning/global_mission_planner.py
        src_extension/execution/global_executor.py src_extension/planning/utility_evaluation.py
        src_extension/planning/local_uav_path_planner.py src_extension/execution/decision_dispatcher.py)
PL_TOOLS=(outputs/_pl_obs.py outputs/_pl_obs_stock.py outputs/_pl_obs_crn.py outputs/_ffr_harness.py
          outputs/_fm2_probe_harness.py outputs/_rblatch_campaign2.py outputs/_pl_validate.py
          outputs/_dcd4rb_validate.py outputs/_dcd4_validate.py outputs/_pl_live.ps1)
PL_FROZEN=(agents.py wildfire_model.py common_fixed_variables.py src_extension evaluate_scenarios.py serve_dashboard.py
           outputs/_ffr_harness.py outputs/_fm2_probe_harness.py outputs/_rblatch_campaign2.py)
src_digest() { sha256sum "${PL_SRC[@]}" 2>&1 | sha256sum | cut -c1-12; }
ext_digest() {
  { sha256sum serve_dashboard.py evaluate_scenarios.py "${PL_TOOLS[@]}" $(git ls-files -- 'src_extension/*.py' 2>&1) 2>&1
    echo "base_head $(git -C "$BASE_WT" rev-parse HEAD 2>&1)"
    echo "base_status"; git -C "$BASE_WT" status --porcelain -uno 2>&1; } | sha256sum | cut -c1-12
}
head_full() { git rev-parse HEAD 2>&1; }
SRC_CHANGED=0
src_check() {
  CUR_SRC=$(src_digest); CUR_EXT=$(ext_digest); CUR_HEAD=$(head_full)
  if [ "$CUR_SRC" != "$SRC0" ] || [ "$CUR_EXT" != "$EXT0" ] || [ "$CUR_HEAD" != "$HEAD0" ]; then
    [ "$SRC_CHANGED" = 0 ] && say "SOURCE CHANGED src=$SRC0->$CUR_SRC ext=$EXT0->$CUR_EXT head=$HEAD0->$CUR_HEAD - launching nothing more; running jobs finish; no re-exec"
    SRC_CHANGED=1
    return 1
  fi
  return 0
}
refuse() { say "REFUSED: $*"; exit 2; }

[ -n "$QUEUE" ] || refuse "QUEUE is not set"
[ -r "$QUEUE" ] || refuse "QUEUE=$QUEUE is not readable"
for f in "${PL_SRC[@]}" "${PL_TOOLS[@]}" serve_dashboard.py evaluate_scenarios.py; do
  [ -f "$f" ] || refuse "source/instrument file $f is missing"
done
dirty=$(git status --porcelain -uno -- "${PL_FROZEN[@]}" 2>&1)
[ -z "$dirty" ] || refuse "a frozen source file is dirty: $(echo "$dirty" | tr '\n' ' ')"

if [ -e "$LOCK" ]; then
  read -r lpid lwin < "$LOCK"
  if [ "$lpid" != "$$" ] && [ -n "$lwin" ] && tasklist //FI "PID eq $lwin" //NH 2>/dev/null | grep -qi bash; then
    say "REFUSED: lock $LOCK held by live pool pid=$lpid winpid=$lwin"
    exit 1
  fi
fi
echo "$$ $(cat /proc/$$/winpid 2>/dev/null)" > "$LOCK"

SRC0=${PL_POOL_SRC0:-$(src_digest)}; EXT0=${PL_POOL_EXT0:-$(ext_digest)}; HEAD0=${PL_POOL_HEAD0:-$(head_full)}
if ! [[ "$HEAD0" =~ ^[0-9a-f]{40}$ && "$SRC0" =~ ^[0-9a-f]{12}$ && "$EXT0" =~ ^[0-9a-f]{12}$ ]]; then
  say "REFUSED: bad POOL START values head=$HEAD0 src=$SRC0 ext=$EXT0"; rm -f "$LOCK"; exit 2
fi
if ! src_check; then
  say "REFUSED: the source is not the POOL START source"; rm -f "$LOCK"; exit 2
fi
say "POOL START wave=$WAVE runid=$RUNID restart=$RESTART pid=$$ winpid=$(cat /proc/$$/winpid 2>/dev/null) head=$HEAD0 src=$SRC0 ext=$EXT0 dirty_tracked=$(git status --porcelain --untracked-files=no | wc -l) queue=$QUEUE maxpar=$MAXPAR minfree_kb=$MINFREE_KB"
say "ENV $($PY -c 'import sys, mesa; print(sys.version.split()[0], "mesa", mesa.__version__)' 2>&1)  prereg_sha256=$(sha256sum "$PREREG" 2>/dev/null | cut -c1-16) queue_sha256=$(sha256sum "$QUEUE" | cut -c1-16)"
SHIPPED_PY='import common_fixed_variables as c, agents as a; print(" ".join(["%s=%s" % (k, getattr(c, k, "ABSENT")) for k in ("GLOBAL_PLANNER_MODE","BASE_STATION_MODE","FF_EXIT_LEG_MODE","FF_EXIT_LEG_HOLD","FF_EXIT_LEG_SERVED","FF_FIREFIGHT_EXTINGUISH","FF_FIREFIGHT_FIREBREAK","ROUTE_BLOCK_STALE_CLEAR")] + ["%s()=%s" % (f, getattr(a, f)() if hasattr(a, f) else "ABSENT") for f in ("global_planner_mode","ff_exit_leg_mode","ff_exit_leg_served")]))'
say "SHIPPED $($PY -B -c "$SHIPPED_PY" 2>&1)"
say "SHIPPED-CONTROL $(cd "$BASE_WT" 2>/dev/null && echo head=$(git rev-parse --short HEAD) && $PY -B -c "$SHIPPED_PY" 2>&1)"

declare -A LINE_OF OUT_OF ATT RUN_NAME RUN_T0
declare -a PENDING=()
NEED_BASE=0
while IFS= read -r ln; do
  ln=${ln//$'\r'/}
  [ -z "$ln" ] && continue
  case "$ln" in \#*) continue;; esac
  IFS='|' read -r kind tag repo w r s _steps _extra <<< "$ln"
  [[ "$tag" =~ ^pl[A-Za-z0-9]+$ ]] || { say "REFUSED: non-planner tag '$tag'"; rm -f "$LOCK"; exit 2; }
  case "$repo" in E:/Projects/SAS) ;; E:/Projects/SAS_wt/basedfbfbe7) NEED_BASE=1 ;; *) say "REFUSED: repo $repo"; rm -f "$LOCK"; exit 2 ;; esac
  case "$kind" in
    ff|fo|fc) rr=$r; [ "$r" = default ] && rr=def
              nm="${tag}_${w}_${rr}_${s}"; OUT_OF[$nm]="${OUTPFX}${nm}.json" ;;
    rb) nm="${tag}_D_${w}"; OUT_OF[$nm]="${repo}/outputs/_rblatch_camp2_${nm}.json" ;;
    *)  say "BAD QUEUE LINE (kind '$kind'): $ln"; rm -f "$LOCK"; exit 2 ;;
  esac
  LINE_OF[$nm]=$ln
done < "$QUEUE"
TOTAL=${#LINE_OF[@]}
declare -A OWN=()
for nm in "${!OUT_OF[@]}"; do OWN[${OUT_OF[$nm]}]=1; done
if [ "$NEED_BASE" = 1 ]; then
  bh=$(git -C "$BASE_WT" rev-parse HEAD 2>&1); bs=$(git -C "$BASE_WT" status --porcelain -uno 2>&1)
  [[ "$bh" =~ ^${BASE_SHA}[0-9a-f]{33}$ ]] || { say "REFUSED: the dfbfbe7 worktree is at '$bh'"; rm -f "$LOCK"; exit 2; }
  [ -z "$bs" ] || { say "REFUSED: the dfbfbe7 worktree has tracked changes: $(echo "$bs" | tr '\n' ' ')"; rm -f "$LOCK"; exit 2; }
fi
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

snapshot() {
  LIVE=()
  local k v
  while read -r k v; do
    v=${v//$'\r'/}
    case "$k" in
      FREE) free_kb=$v ;;
      SIMS) sims=$v ;;
      LIVE) v=${v//\\//}; v=${v#./}; [ -n "${OWN[$v]}" ] && LIVE["$v"]=1 ;;   # PL: only THIS queue's jobs - another pl pool's job is not an orphan of this one
      ERROR) say "SNAPSHOT ERROR $v"; free_kb=0 ;;
    esac
  done < <(powershell -NoProfile -ExecutionPolicy Bypass -File outputs/_pl_live.ps1 -TagPrefix "$TAGPFX" 2>&1)
}

save_attempts() {
  local n
  : > "$ATTF.tmp"
  for n in "${!ATT[@]}"; do echo "$n ${ATT[$n]}" >> "$ATTF.tmp"; done
  mv -f "$ATTF.tmp" "$ATTF"
}

validate_one() { $PY -B "${VAL[@]}" --one "$1" "${@:2}" 2>&1; }

snapshot
n_done=0
start_val=$($PY -B "${VAL[@]}" --all 2>&1); vrc=$?
if [ "$vrc" != 0 ] || ! grep -q '^SUMMARY ' <<< "$start_val"; then
  say "REFUSED: the start validator pass failed rc=$vrc: $(tail -3 <<< "$start_val" | tr '\r\n' '  ')"; rm -f "$LOCK"; exit 2
fi
srcmis=$(grep '^INVALID [^ ]* SOURCE MISMATCH' <<< "$start_val")
if [ -n "$srcmis" ]; then
  sed "s/^/[$(ts)] SOURCE-MISMATCH-AT-START /" <<< "$srcmis"
  say "REFUSED: run(s) made under another source - nothing moved"; rm -f "$LOCK"; exit 2
fi
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
done <<< "$start_val"
# keep the queue's order for launches (the validator prints in queue order)
say "START STATE wave=$WAVE total=$TOTAL valid=$n_done pending=${#PENDING[@]} live_orphans_this_wave=${#LIVE[@]} sims_boxwide=$sims free_kb=$free_kb"

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

launch() {
  local name=$1 ln=${LINE_OF[$1]} kind tag repo w r s steps extra prev pid stepsarg="" inst
  IFS='|' read -r kind tag repo w r s steps extra <<< "$ln"
  prev=$!
  case "$kind" in
    ff|fo|fc)
      case "$kind" in ff) inst=outputs/_ffr_harness.py ;; fo) inst=outputs/_pl_obs_stock.py ;; fc) inst=outputs/_pl_obs_crn.py ;; esac
      # shellcheck disable=SC2086
      $PY -B "$inst" --repo "$repo" --wind "$w" --roles "$r" --seed "$s" --steps "$steps" \
          --out "${OUT_OF[$name]}" --tag "$tag" $extra \
          > "$LOGDIR/${name}.out" 2> "$LOGDIR/${name}.err" & ;;
    rb)
      [ "$steps" != 240 ] && stepsarg="--steps $steps"
      # shellcheck disable=SC2086
      $PY -B "$repo/outputs/_rblatch_campaign2.py" --wind "$w" --seeds "$s" --tag "$tag" $stepsarg $extra \
          > "outputs/_ffr_rb_${tag}.log" 2>&1 & ;;
  esac
  pid=$!
  if [ -z "$pid" ] || [ "$pid" = "$prev" ]; then
    return 1
  fi
  RUN_NAME[$pid]=$name
  printf -v RUN_T0[$pid] '%(%s)T' -1
  return 0
}

summary_of() {
  local name=$1 ln=${LINE_OF[$1]} kind tag
  IFS='|' read -r kind tag _ <<< "$ln"
  if [ "$kind" = rb ]; then
    grep ' done ' "outputs/_ffr_rb_${tag}.log" 2>/dev/null | tr -d '\r' | sed 's/^/| /' | tr '\n' ' '
  else
    tr -d '\r' < "$LOGDIR/${name}.out" 2>/dev/null
  fi
}

judge() {
  local pid=$1 rc=$2 name=${RUN_NAME[$1]} t0=${RUN_T0[$1]} now v errtail
  unset "RUN_NAME[$pid]" "RUN_T0[$pid]"
  printf -v now '%(%s)T' -1
  src_check
  v=$(validate_one "$name")
  last_event=$now
  case "$v" in
    VALID*)
      n_done=$((n_done+1))
      say "DONE $name rc=$rc $((now-t0))s $(summary_of "$name") [valid $n_done/$TOTAL] src=$CUR_SRC ext=$CUR_EXT head=$CUR_HEAD" ;;
    *)
      if [ "$SRC_CHANGED" = 1 ]; then
        PENDING+=("$name")
        say "HELD $name rc=$rc $((now-t0))s validator: $v - SOURCE CHANGED: files left in place"
        write_state; return
      fi
      n_fail=$((n_fail+1))
      ATT[$name]=$(( ${ATT[$name]:-0} + 1 )); save_attempts
      case "${LINE_OF[$name]}" in
        rb\|*) errtail=$(tail -3 "outputs/_ffr_rb_$(cut -d'|' -f2 <<< "${LINE_OF[$name]}").log" 2>/dev/null | tr '\r\n' '  ') ;;
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
    if [ "$SRC_CHANGED" = 1 ]; then
      [ ${#RUN_NAME[@]} -eq 0 ] && break
      reap_blocking; continue
    fi
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
          if ! src_check; then continue; fi
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
            say "LAUNCH $name running=${#RUN_NAME[@]} free_kb=$free_kb sims_boxwide=$sims attempt=$(( ${ATT[$name]:-0} + 1 )) src=$CUR_SRC ext=$CUR_EXT head=$CUR_HEAD"
            write_state
            sleep "$LAUNCH_GAP"
          else
            n_forkfail=$((n_forkfail+1))
            local back=$(( 30 * (2 ** (n_forkfail > 4 ? 4 : n_forkfail-1)) ))
            say "FORKFAIL $name count=$n_forkfail - backing off ${back}s"
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
          if ! src_check; then continue; fi
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

src_check
final=$($PY -B "${VAL[@]}" --all 2>&1)
summary=$(echo "$final" | grep '^SUMMARY')
echo "$final" | grep -v '^VALID' | sed "s/^/[$(ts)] FINAL /"
snapshot
say "FINAL wave=$WAVE $summary live_this_wave=${#LIVE[@]} sims_boxwide=$sims"
valid=${summary#*valid=}; valid=${valid%% *}
touch "$SENT"
if [ "$valid" = "$TOTAL" ] && [ ${#LIVE[@]} -eq 0 ] && [ "$SRC_CHANGED" = 0 ]; then
  rm -f "$LOCK"
  say "ALL_PL_COMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL launched=$n_launched failed=$n_fail forkfail=$n_forkfail src=$SRC0 ext=$EXT0 head=$HEAD0"
  exit 0
fi
if [ "$valid" = "$TOTAL" ] && [ ${#LIVE[@]} -eq 0 ]; then
  rm -f "$LOCK"
  say "SOURCE_CHANGED_COMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL src=$SRC0->$CUR_SRC ext=$EXT0->$CUR_EXT head=$HEAD0->$CUR_HEAD - NOT a clean wave"
  exit 3
fi
if [ "$RESTART" -lt "$MAX_RESTARTS" ] && [ "$n_gaveup" -eq 0 ] && [ "$SRC_CHANGED" = 0 ]; then
  say "POOL INCOMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL - re-exec in 60s (restart $((RESTART+1))/$MAX_RESTARTS)"
  sleep 60
  export PL_RESTART=$((RESTART+1))
  export PL_POOL_SRC0=$SRC0 PL_POOL_EXT0=$EXT0 PL_POOL_HEAD0=$HEAD0
  exec bash "$0"
fi
rm -f "$LOCK"
say "PL_POOL_INCOMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL gaveup=$n_gaveup - NOT restarting"
exit 2
