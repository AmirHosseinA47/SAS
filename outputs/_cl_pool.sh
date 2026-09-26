#!/usr/bin/env bash
# CL: carrying-leg round: the wave pool. outputs/_ug_pool.sh verbatim but for the lines
# CL: marked CL (outputs/_cl_tooling_spec.txt section G): PREREG, the SHIPPED and
# CL: SHIPPED-CONTROL lines (+ FF_EXIT_LEG_* constants and accessor values; control =
# CL: the 6160438 worktree), POOL START logs harness= and src=, a start-up guard pairing
# CL: FM2P_ lines with _cl_obs_crn.py, src=/head= on every LAUNCH and DONE line with a
# CL: SOURCE CHANGED stop (no launch, no re-exec; running jobs finish), VAL ->
# CL: outputs/_cl_validate.py. Set HARNESS=outputs/_cl_obs_stock.py or _cl_obs_crn.py
# CL: (outputs/_cl_probe.py for the D-9 probe lines, either instrument).
# CL: REVIEW FIXES (2026-09-26), each marked CL too:
# CL:  - CL-own defaults (LOG outputs/_cl_wave.log, STEM outputs/_cl_pool, TAGPFX cl) and NO
# CL:    QUEUE / HARNESS default; LOG and STEM must be carrying-leg paths (inside outputs/
# CL:    only _cl_*) and LOG untracked - checked BEFORE the log is opened; a refusal
# CL:    then goes to outputs/_cl_wave.log. Every queue tag must be ^cl[A-Za-z0-9]+$ and
# CL:    TAGPFX must be cl: the stricter validator reads any earlier round's run as
# CL:    INVALID, and this pool moves INVALID runs aside.
# CL:  - HARNESS must be one of the CL instruments (_cl_obs_stock.py / _cl_obs_crn.py /
# CL:    _cl_probe.py in outputs/); _cl_probe.py serves both instruments (a line with
# CL:    FM2P_ keys must carry --set FM2P_CRN=1); CLP_ keys only under _cl_probe.py; ff
# CL:    repos only the carryleg checkout or the 6160438 worktree (which must then be
# CL:    at 6160438 and clean); rb lines only the carryleg checkout's campaign.
# CL:  - src= stays the spec's four-file digest (== the sidecar's src12); ext= adds
# CL:    serve_dashboard.py, evaluate_scenarios.py, every tracked src_extension/*.py, the
# CL:    instrument / harness / validator files and the 6160438 worktree's HEAD + tracked
# CL:    status; head= is the FULL HEAD (40 hex, format-checked). Start refuses a dirty
# CL:    rule-A2 frozen file. A change of any of them is SOURCE CHANGED.
# CL:  - a run whose sidecar names another source (validator "SOURCE MISMATCH") makes the
# CL:    start REFUSE, moving nothing; after SOURCE CHANGED a failed run is HELD in place
# CL:    (not moved, not requeued); the final line says complete only with no SOURCE
# CL:    CHANGED (else SOURCE_CHANGED_COMPLETE, exit 3).
# CL:  - launches run the interpreter with -B (rule A3).
# CL: The _ug_pool.sh header follows, unchanged.
# ungated-firefighting round: the wave pool. outputs/_dfp_pool.sh (itself
# _dcd4rb_pool.sh verbatim but for its DFP lines) with FOUR lines changed, each marked
# UG below: the working directory (the live checkout, which holds the round's branch at
# the Part 2 commit and must stay clean for the whole wave), PREREG (this round's
# pre-registration, hashed into the log), the SHIPPED line (now also prints the FF and
# searcher-guard switches, which neither the harness nor the gate records) and the
# SHIPPED-CONTROL line (the 11c3661 control worktree).
# Everything else - no bare wait, validator-backed skip, orphan adoption, detached
# PowerShell launch, bounded re-exec - is unchanged.
#
# queue line: kind|tag|repo|wind|roles|seeds|steps|extra
# NOTE: for kind rb the repo field is NOT used - a shard runs $RBSCRIPT, which imports
# the checkout it lives in. The control shards are run by a separate invocation with
# RBSCRIPT/RBDIR/RBLOGDIR pointing into the control worktree.
# usage (detached; CL: one pool per queue file, each with its own STEM and LOG):
#   powershell -NoProfile -ExecutionPolicy Bypass -File outputs/_dcd4_launch.ps1
#     -Script /e/Projects/SAS/outputs/_cl_pool.sh
#     -Env "QUEUE=outputs/_cl_s1_queue.txt;HARNESS=outputs/_cl_obs_stock.py;STEM=outputs/_cl_s1;LOG=outputs/_cl_s1_wave.log;WAVE=s1"
#   (CRN: QUEUE=outputs/_cl_s1_crn_queue.txt;HARNESS=outputs/_cl_obs_crn.py;STEM=outputs/_cl_s1_crn;LOG=outputs/_cl_s1_crn_wave.log)
cd /e/Projects/SAS || exit 1   # CL: the live checkout on carryleg

QUEUE=${QUEUE:-}   # CL: no default - a carrying-leg queue must be named
WAVE=${WAVE:-wave}
LOG=${LOG:-outputs/_cl_wave.log}   # CL: this round's own log (opened before any other guard)
OUTPFX=${OUTPFX:-outputs/_ffr_}
LOGDIR=${LOGDIR:-outputs/_ffr_logs}
RBDIR=${RBDIR:-outputs}
RBLOGDIR=${RBLOGDIR:-outputs}
HARNESS=${HARNESS:-}   # CL: no default - one of the CL instruments must be named
RBSCRIPT=${RBSCRIPT:-outputs/_rblatch_campaign2.py}
TAGPFX=${TAGPFX:-cl}   # CL
MAXPAR=${MAXPAR:-18}
MINFREE_KB=${MINFREE_KB:-3500000}
LAUNCH_GAP=${LAUNCH_GAP:-12}
HB_SECS=${HB_SECS:-60}
IDLE_SLEEP=${IDLE_SLEEP:-30}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-3}
MAX_RESTARTS=${MAX_RESTARTS:-3}
PREREG=${PREREG:-outputs/carryleg_prereg.txt}   # CL: this round's pre-registration
STEM=${STEM:-outputs/_cl_pool}   # CL: this round's own lock / state / attempts / quarantine stem
PY=${PY:-/e/Projects/SAS/.venv/Scripts/python.exe}   # DFP: the parent checkout's venv (mesa 1.2.1)
RESTART=${DCD4RB_RESTART:-0}

# CL: the paths this pool writes BEFORE any other guard runs. A path is carrying-leg-own
# CL: iff, normalised (cygpath + realpath, case-folded), it is outside the checkout or is
# CL: outputs/_cl_*; LOG must in addition not be a tracked file. A refusal here cannot go
# CL: to $LOG, so it goes to the round's default log.
cl_own_path() {   # CL
  local p; p=$(cygpath -u -- "$1" 2>/dev/null) || p=$1   # CL
  p=$(realpath -m -- "$p" 2>/dev/null) || return 1   # CL
  p=${p,,}   # CL
  case "$p" in /e/projects/sas/outputs/_cl_*) return 0 ;; /e/projects/sas|/e/projects/sas/*) return 1 ;; esac   # CL
  return 0   # CL
}   # CL
cl_pre_refuse=""   # CL
cl_own_path "$LOG" || cl_pre_refuse="LOG=$LOG is not a carrying-leg path (outputs/_cl_* or outside the checkout)"   # CL
git ls-files --error-unmatch -- "$LOG" >/dev/null 2>&1 && cl_pre_refuse="LOG=$LOG is a TRACKED file"   # CL
cl_own_path "$STEM" || cl_pre_refuse="${cl_pre_refuse:+$cl_pre_refuse; }STEM=$STEM is not a carrying-leg path (outputs/_cl_* or outside the checkout)"   # CL
if [ -n "$cl_pre_refuse" ]; then   # CL
  printf '[%(%H:%M:%S)T] REFUSED: %s - nothing opened, nothing moved (pid=%s)\n' -1 "$cl_pre_refuse" "$$" | tee -a outputs/_cl_wave.log >&2   # CL
  exit 2   # CL
fi   # CL

mkdir -p "$LOGDIR"
exec >>"$LOG" 2>&1

MAIN=$$
printf -v RUNID '%(%Y%m%d-%H%M%S)T-%s' -1 "$$"
LOCK="${STEM}.lock"
STATE="${STEM}_state.txt"
SENT="${STEM}_hb_${RUNID}.stop"
ATTF="${STEM}_attempts.txt"
QDIR="${STEM}_quarantine"
VAL=(outputs/_cl_validate.py --queue "$QUEUE" --outpfx "$OUTPFX" --logdir "$LOGDIR" --rbdir "$RBDIR" --rblogdir "$RBLOGDIR")   # CL: the round's validator (wraps _dcd4rb_validate.py)

ts() { printf '%(%H:%M:%S)T' -1; }
say() { echo "[$(ts)] $*"; }

# CL: the simulation source this wave runs: one sha256 over the four files' sha256sum
# CL: lines (a missing file changes it too), first 12 hex (== the sidecar's src12).
# CL: src_check sets CUR_SRC / CUR_EXT / CUR_HEAD and returns 1 (logging SOURCE CHANGED
# CL: once, SRC_CHANGED=1) if any differs from the POOL START values SRC0 / EXT0 / HEAD0.
src_digest() { sha256sum agents.py wildfire_model.py common_fixed_variables.py src_extension/planning/rescue_planner.py 2>&1 | sha256sum | cut -c1-12; }   # CL
# CL (review): ext= - everything else a run executes or is judged by: the remaining
# CL: rule-A2 frozen files, every TRACKED src_extension/*.py, the instruments, the inner
# CL: harnesses, the rb campaign, the validators, and the 6160438 worktree's HEAD and
# CL: tracked status (its source is fixed by the two). Error text (a missing file, a git
# CL: failure) goes into the digest, so it changes the value rather than hiding.
CL_BASE_WT=/e/Projects/SAS_wt/base6160438   # CL
CL_TOOLS=(outputs/_cl_obs.py outputs/_cl_obs_stock.py outputs/_cl_obs_crn.py outputs/_cl_probe.py outputs/_ffr_harness.py outputs/_fm2_probe_harness.py outputs/_cl_validate.py outputs/_dcd4rb_validate.py outputs/_dcd4_validate.py)   # CL
CL_FROZEN=(agents.py wildfire_model.py common_fixed_variables.py src_extension evaluate_scenarios.py serve_dashboard.py outputs/_ffr_harness.py outputs/_fm2_probe_harness.py outputs/_rblatch_campaign2.py)   # CL: rule A2
ext_digest() {   # CL
  { sha256sum serve_dashboard.py evaluate_scenarios.py "${CL_TOOLS[@]}" "$HARNESS" "$RBSCRIPT" $(git ls-files -- 'src_extension/*.py' 2>&1) 2>&1   # CL
    echo "base_head $(git -C "$CL_BASE_WT" rev-parse HEAD 2>&1)"   # CL
    echo "base_status"; git -C "$CL_BASE_WT" status --porcelain -uno 2>&1; } | sha256sum | cut -c1-12   # CL
}   # CL
head_full() { git rev-parse HEAD 2>&1; }   # CL (review): the FULL hash - --short grows with the object count
SRC_CHANGED=0   # CL
src_check() {   # CL
  CUR_SRC=$(src_digest); CUR_EXT=$(ext_digest); CUR_HEAD=$(head_full)   # CL
  if [ "$CUR_SRC" != "$SRC0" ] || [ "$CUR_EXT" != "$EXT0" ] || [ "$CUR_HEAD" != "$HEAD0" ]; then   # CL
    [ "$SRC_CHANGED" = 0 ] && say "SOURCE CHANGED src=$SRC0->$CUR_SRC ext=$EXT0->$CUR_EXT head=$HEAD0->$CUR_HEAD - launching nothing more; running jobs finish; no re-exec"   # CL
    SRC_CHANGED=1   # CL
    return 1   # CL
  fi   # CL
  return 0   # CL
}   # CL
refuse() { say "REFUSED: $*"; exit 2; }   # CL: a start-up refusal before the lock is taken (nothing to release)

# CL: ---- environment guard (before the lock; read-only) ---------------------------
[ -n "$QUEUE" ] || refuse "QUEUE is not set (no default: name a carrying-leg queue)"   # CL
[ -r "$QUEUE" ] || refuse "QUEUE=$QUEUE is not readable"   # CL
[ "$TAGPFX" = cl ] || refuse "TAGPFX=$TAGPFX, the carrying-leg pool requires cl"   # CL
case "$HARNESS" in *\\*|'') refuse "HARNESS='$HARNESS' - name one of outputs/_cl_obs_stock.py, _cl_obs_crn.py, _cl_probe.py (forward slashes)" ;; esac   # CL
HNORM=$(realpath -m -- "$(cygpath -u -- "$HARNESS" 2>/dev/null || echo "$HARNESS")" 2>/dev/null); HNORM=${HNORM,,}   # CL
case "$HNORM" in /e/projects/sas/outputs/_cl_obs_stock.py|/e/projects/sas/outputs/_cl_obs_crn.py|/e/projects/sas/outputs/_cl_probe.py) ;; *) refuse "HARNESS=$HARNESS is not a CL instrument (outputs/_cl_obs_stock.py, _cl_obs_crn.py, _cl_probe.py)" ;; esac   # CL
HNAME=${HNORM##*/}   # CL
RBNORM=$(realpath -m -- "$(cygpath -u -- "$RBSCRIPT" 2>/dev/null || echo "$RBSCRIPT")" 2>/dev/null); RBNORM=${RBNORM,,}   # CL
[ "$RBNORM" = /e/projects/sas/outputs/_rblatch_campaign2.py ] || refuse "RBSCRIPT=$RBSCRIPT is not the carryleg checkout's outputs/_rblatch_campaign2.py"   # CL
for f in agents.py wildfire_model.py common_fixed_variables.py src_extension/planning/rescue_planner.py serve_dashboard.py evaluate_scenarios.py "${CL_TOOLS[@]}" "$HARNESS" "$RBSCRIPT"; do   # CL
  [ -f "$f" ] || refuse "source/instrument file $f is missing"   # CL
done   # CL
cl_dirty=$(git status --porcelain -uno -- "${CL_FROZEN[@]}" 2>&1)   # CL: tracked files only (-uno)
[ -z "$cl_dirty" ] || refuse "a rule-A2 frozen file is dirty (the src/ext digests would name an uncommitted source): $(echo "$cl_dirty" | tr '\n' ' ')"   # CL

# ---- lock: refuse to run twice ---------------------------------------------
if [ -e "$LOCK" ]; then
  read -r lpid lwin < "$LOCK"
  if [ "$lpid" != "$$" ] && [ -n "$lwin" ] && tasklist //FI "PID eq $lwin" //NH 2>/dev/null | grep -qi bash; then
    say "REFUSED: lock $LOCK held by live pool pid=$lpid winpid=$lwin"
    exit 1
  fi
fi
echo "$$ $(cat /proc/$$/winpid 2>/dev/null)" > "$LOCK"

SRC0=${CL_POOL_SRC0:-$(src_digest)}; EXT0=${CL_POOL_EXT0:-$(ext_digest)}; HEAD0=${CL_POOL_HEAD0:-$(head_full)}   # CL: a re-exec inherits the first POOL START values
# CL (review): a git failure must not put the same error text on both sides of every later
# CL: comparison - HEAD0 is a full 40-hex hash, the digests 12 hex, and they equal NOW
if ! [[ "$HEAD0" =~ ^[0-9a-f]{40}$ && "$SRC0" =~ ^[0-9a-f]{12}$ && "$EXT0" =~ ^[0-9a-f]{12}$ ]]; then   # CL
  say "REFUSED: bad POOL START values head=$HEAD0 src=$SRC0 ext=$EXT0"; rm -f "$LOCK"; exit 2   # CL
fi   # CL
if ! src_check; then   # CL: a re-exec whose source moved since the first POOL START
  say "REFUSED: the source is not the POOL START source (see SOURCE CHANGED above)"; rm -f "$LOCK"; exit 2   # CL
fi   # CL
say "POOL START wave=$WAVE runid=$RUNID restart=$RESTART pid=$$ winpid=$(cat /proc/$$/winpid 2>/dev/null) head=$HEAD0 src=$SRC0 ext=$EXT0 harness=$HARNESS dirty_tracked=$(git status --porcelain --untracked-files=no | wc -l) queue=$QUEUE maxpar=$MAXPAR minfree_kb=$MINFREE_KB"   # CL: harness= src= ext=
say "ENV $($PY -c 'import sys, mesa; print(sys.version.split()[0], "mesa", mesa.__version__)' 2>&1)  prereg_sha256=$(sha256sum "$PREREG" 2>/dev/null | cut -c1-16) queue_sha256=$(sha256sum "$QUEUE" | cut -c1-16)"
# the harness and the gate record neither the effective BASE_STATION_* values nor
# the commit (dcd4_report.txt section 8); the wave log does
say "SHIPPED $($PY -B -c 'import common_fixed_variables as c, agents as a; print(" ".join(["%s=%s" % (k, getattr(c, k, "ABSENT")) for k in ("BASE_STATION_MODE","BASE_STATION_RETURN_MECHANISM","BASE_STATION_DEPOTS","BASE_STATION_SPAWN_SPLIT","UAV_RETURN_TO_BASE_RESERVE","BASE_STATION_RETURN_MARGIN","BASE_STATION_DOCK_FIX","BASE_STATION_RETURN_STALL_LIMIT","BASE_STATION_WAYPOINT_FIX","ROUTE_BLOCK_STALE_CLEAR","VICTIM_SEARCHER_HAZARD_RETREAT_RANGE","BASE_STATION_FIREPROOF","BASE_STATION_FIREPROOF_DRY_RUN","VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX","FF_FIREFIGHT_EXTINGUISH","FF_FIREFIGHT_FIREBREAK","FF_FIREFIGHT_ENGAGED_RETREAT_RANGE","FF_FIREFIGHT_MISSION_GATE","FF_FIREFIGHT_DRY_RUN","FF_EXIT_LEG_MODE","FF_EXIT_LEG_HOLD","FF_EXIT_LEG_SERVED")] + ["%s()=%s" % (f, getattr(a, f)() if hasattr(a, f) else "ABSENT") for f in ("ff_exit_leg_mode","ff_exit_leg_hold","ff_exit_leg_served")]))' 2>&1)"   # UG + CL: + FF_EXIT_LEG_* constants and the agents.ff_exit_leg_*() accessor values

say "SHIPPED-CONTROL $(cd /e/Projects/SAS_wt/base6160438 && echo head=$(git rev-parse --short HEAD) && $PY -B -c 'import common_fixed_variables as c, agents as a; print(" ".join(["%s=%s" % (k, getattr(c, k, "ABSENT")) for k in ("BASE_STATION_MODE","BASE_STATION_RETURN_MECHANISM","BASE_STATION_DEPOTS","BASE_STATION_SPAWN_SPLIT","UAV_RETURN_TO_BASE_RESERVE","BASE_STATION_RETURN_MARGIN","BASE_STATION_DOCK_FIX","BASE_STATION_RETURN_STALL_LIMIT","BASE_STATION_WAYPOINT_FIX","ROUTE_BLOCK_STALE_CLEAR","VICTIM_SEARCHER_HAZARD_RETREAT_RANGE","BASE_STATION_FIREPROOF","BASE_STATION_FIREPROOF_DRY_RUN","VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX","FF_FIREFIGHT_EXTINGUISH","FF_FIREFIGHT_FIREBREAK","FF_FIREFIGHT_ENGAGED_RETREAT_RANGE","FF_FIREFIGHT_MISSION_GATE","FF_FIREFIGHT_DRY_RUN","FF_EXIT_LEG_MODE","FF_EXIT_LEG_HOLD","FF_EXIT_LEG_SERVED")] + ["%s()=%s" % (f, getattr(a, f)() if hasattr(a, f) else "ABSENT") for f in ("ff_exit_leg_mode","ff_exit_leg_hold","ff_exit_leg_served")]))' 2>&1)"   # CL: the 6160438 control worktree, the SHIPPED line's keys (ABSENT expected for the FF_EXIT_LEG_* ones)

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
# CL: start-up guard - every tag a carrying-leg tag, and the instrument must match the
# CL: harness: _cl_obs_stock.py takes no FM2P_ key; _cl_obs_crn.py requires --set
# CL: FM2P_CRN=1; _cl_probe.py serves both (FM2P_ keys -> --set FM2P_CRN=1 required); CLP_
# CL: keys only under _cl_probe.py. ff repos: the carryleg checkout or the 6160438
# CL: worktree; rb lines: the carryleg checkout (the campaign imports its own checkout).
cl_guard_fail() { say "REFUSED: $1: $2"; rm -f "$LOCK"; exit 2; }   # CL
NEED_BASE=0   # CL
for nm in "${!LINE_OF[@]}"; do   # CL
  IFS='|' read -r gkind gtag grepo _ _ _ _ gextra <<< "${LINE_OF[$nm]}"   # CL
  [[ "$gtag" =~ ^cl[A-Za-z0-9]+$ ]] || cl_guard_fail "$nm has a non-carrying-leg tag '$gtag'" "${LINE_OF[$nm]}"   # CL
  if [ "$gkind" = rb ]; then   # CL
    [ "$grepo" = E:/Projects/SAS ] || cl_guard_fail "$nm: an rb shard runs $RBSCRIPT (the carryleg checkout), not repo $grepo" "${LINE_OF[$nm]}"   # CL
    continue   # CL
  fi   # CL
  case "$grepo" in E:/Projects/SAS) ;; E:/Projects/SAS_wt/base6160438) NEED_BASE=1 ;; *) cl_guard_fail "$nm: repo $grepo is neither the carryleg checkout nor the 6160438 worktree" "${LINE_OF[$nm]}" ;; esac   # CL
  case "$gextra" in *CLP_*) [ "$HNAME" = _cl_probe.py ] || cl_guard_fail "$nm carries a CLP_ key but HARNESS=$HARNESS is not _cl_probe.py" "${LINE_OF[$nm]}" ;; esac   # CL
  case "$HNAME" in   # CL
    _cl_obs_stock.py)   # CL
      case "$gextra" in *FM2P_*) cl_guard_fail "$nm carries an FM2P_ key but HARNESS=$HARNESS is the stock instrument" "${LINE_OF[$nm]}" ;; esac ;;   # CL
    _cl_obs_crn.py)   # CL
      case " $gextra " in *" --set FM2P_CRN=1 "*) ;; *) cl_guard_fail "$nm lacks --set FM2P_CRN=1 under HARNESS=$HARNESS" "${LINE_OF[$nm]}" ;; esac ;;   # CL
    _cl_probe.py)   # CL
      case "$gextra" in *FM2P_*) case " $gextra " in *" --set FM2P_CRN=1 "*) ;; *) cl_guard_fail "$nm carries an FM2P_ key without --set FM2P_CRN=1 under HARNESS=$HARNESS" "${LINE_OF[$nm]}" ;; esac ;; esac ;;   # CL
    *) cl_guard_fail "HARNESS=$HARNESS is not a CL instrument" "${LINE_OF[$nm]}" ;;   # CL
  esac   # CL
done   # CL
if [ "$NEED_BASE" = 1 ]; then   # CL: a clB line - the control worktree must BE 6160438, clean
  cl_bh=$(git -C "$CL_BASE_WT" rev-parse HEAD 2>&1); cl_bs=$(git -C "$CL_BASE_WT" status --porcelain -uno 2>&1)   # CL
  [[ "$cl_bh" =~ ^6160438[0-9a-f]{33}$ ]] || cl_guard_fail "the 6160438 worktree is at '$cl_bh'" "$CL_BASE_WT"   # CL
  [ -z "$cl_bs" ] || cl_guard_fail "the 6160438 worktree has tracked changes: $(echo "$cl_bs" | tr '\n' ' ')" "$CL_BASE_WT"   # CL
fi   # CL
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
# CL (review): the pass is read in full BEFORE anything is moved. A failed pass refuses; a
# CL: run whose sidecar names another source than its repo holds now (validator reason
# CL: "SOURCE MISMATCH") refuses the start and moves NOTHING - recorded evidence of this
# CL: round is never moved aside for a source change; a human decides.
cl_start_val=$($PY "${VAL[@]}" --all 2>&1); cl_vrc=$?   # CL
if [ "$cl_vrc" != 0 ] || ! grep -q '^SUMMARY ' <<< "$cl_start_val"; then   # CL
  say "REFUSED: the start validator pass failed rc=$cl_vrc: $(tail -3 <<< "$cl_start_val" | tr '\r\n' '  ')"; rm -f "$LOCK"; exit 2   # CL
fi   # CL
cl_srcmis=$(grep '^INVALID [^ ]* SOURCE MISMATCH' <<< "$cl_start_val")   # CL
if [ -n "$cl_srcmis" ]; then   # CL
  sed "s/^/[$(ts)] SOURCE-MISMATCH-AT-START /" <<< "$cl_srcmis"   # CL
  say "REFUSED: $(wc -l <<< "$cl_srcmis") run(s) were made under another source than their repo holds now - nothing moved; restore the source or re-plan the wave"; rm -f "$LOCK"; exit 2   # CL
fi   # CL
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
done <<< "$cl_start_val"   # CL: the pass read above
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
    # CL: -B (rule A3: the instruments import the checkout's modules - no __pycache__ there)
    # shellcheck disable=SC2086
    $PY -B "$HARNESS" --repo "$repo" --wind "$w" --roles "$r" --seed "$s" --steps "$steps" \
        --out "${OUT_OF[$name]}" --tag "$tag" $extra \
        > "$LOGDIR/${name}.out" 2> "$LOGDIR/${name}.err" &
  else
    # exactly _ffr_rbgate.sh's per-shard command; --steps only if not the default
    # CL: plus -B on both launch lines (rule A3: no __pycache__ in the checkout/worktree)
    [ "$steps" != 240 ] && stepsarg="--steps $steps"
    # shellcheck disable=SC2086
    $PY -B "$RBSCRIPT" --wind "$w" --seeds "$s" --tag "$tag" $stepsarg $extra \
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
  src_check   # CL: sets CUR_SRC/CUR_EXT/CUR_HEAD; a change stops launching. FIRST: see HELD below
  v=$(validate_one "$name")
  last_event=$now
  case "$v" in
    VALID*)
      n_done=$((n_done+1))
      say "DONE $name rc=$rc $((now-t0))s $(summary_of "$name") [valid $n_done/$TOTAL] src=$CUR_SRC ext=$CUR_EXT head=$CUR_HEAD" ;;   # CL: src= ext= head=
    *)
      if [ "$SRC_CHANGED" = 1 ]; then   # CL (review): the run may be sound under the POOL START source - never move it for a later change
        PENDING+=("$name")   # CL: counted as pending; nothing more is launched
        say "HELD $name rc=$rc $((now-t0))s validator: $v - SOURCE CHANGED (src=$CUR_SRC ext=$CUR_EXT head=$CUR_HEAD): files left in place, not moved, not requeued, no attempt counted"   # CL
        write_state; return   # CL
      fi   # CL
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
    if [ "$SRC_CHANGED" = 1 ]; then   # CL: SOURCE CHANGED - launch nothing more, let the running jobs finish
      [ ${#RUN_NAME[@]} -eq 0 ] && break   # CL
      reap_blocking; continue   # CL
    fi   # CL
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
          if ! src_check; then continue; fi   # CL: checked BEFORE the pre-launch validation - a change adopts, moves and launches nothing
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
            say "LAUNCH $name running=${#RUN_NAME[@]} free_kb=$free_kb sims_boxwide=$sims attempt=$(( ${ATT[$name]:-0} + 1 )) src=$CUR_SRC ext=$CUR_EXT head=$CUR_HEAD"   # CL: src= ext= head=
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
          if ! src_check; then continue; fi   # CL: no orphan adoption under a changed source
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
src_check   # CL (review): the last word on the source, before the final judgement
final=$($PY "${VAL[@]}" --all 2>&1)
summary=$(echo "$final" | grep '^SUMMARY')
echo "$final" | grep -v '^VALID' | sed "s/^/[$(ts)] FINAL /"
snapshot
say "FINAL wave=$WAVE $summary live_this_wave=${#LIVE[@]} sims_boxwide=$sims"
valid=${summary#*valid=}; valid=${valid%% *}
touch "$SENT"
if [ "$valid" = "$TOTAL" ] && [ ${#LIVE[@]} -eq 0 ] && [ "$SRC_CHANGED" = 0 ]; then   # CL: complete only under an unchanged source
  rm -f "$LOCK"
  say "ALL_DCD4RB_COMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL launched=$n_launched failed=$n_fail forkfail=$n_forkfail src=$SRC0 ext=$EXT0 head=$HEAD0"   # CL: + src= ext= head=
  exit 0
fi
if [ "$valid" = "$TOTAL" ] && [ ${#LIVE[@]} -eq 0 ]; then   # CL (review): every run VALID, but the source moved during the wave
  rm -f "$LOCK"   # CL
  say "SOURCE_CHANGED_COMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL src=$SRC0->$CUR_SRC ext=$EXT0->$CUR_EXT head=$HEAD0->$CUR_HEAD - NOT a clean wave: read the SOURCE CHANGED line and the DONE lines' src=/ext=/head= before using any run"   # CL
  exit 3   # CL
fi   # CL
if [ "$RESTART" -lt "$MAX_RESTARTS" ] && [ "$n_gaveup" -eq 0 ] && [ "$SRC_CHANGED" = 0 ]; then   # CL: never re-exec after SOURCE CHANGED
  say "POOL INCOMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL - re-exec in 60s (restart $((RESTART+1))/$MAX_RESTARTS); orphans, if any, are adopted"
  # the lock is KEPT: exec preserves $$, so the re-exec passes its own lock check
  sleep 60
  export DCD4RB_RESTART=$((RESTART+1))
  export CL_POOL_SRC0=$SRC0 CL_POOL_EXT0=$EXT0 CL_POOL_HEAD0=$HEAD0   # CL: the re-exec compares against THIS pool's POOL START values
  exec bash "$0"
fi
[ "$SRC_CHANGED" = 1 ] && say "SOURCE CHANGED during the wave (POOL START src=$SRC0 ext=$EXT0 head=$HEAD0, last seen src=$CUR_SRC ext=$CUR_EXT head=$CUR_HEAD) - NOT restarting; the source must be restored, or the wave re-planned, before a deliberate relaunch"   # CL
rm -f "$LOCK"
say "DCD4RB_POOL_INCOMPLETE wave=$WAVE runid=$RUNID valid=$valid/$TOTAL gaveup=$n_gaveup - NOT restarting; relaunch with outputs/_dcd4_launch.ps1 after reading the FAIL lines"
exit 2
