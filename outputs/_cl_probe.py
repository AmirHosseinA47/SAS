"""Carrying-leg round, Part 2: THE D-9 PROBE - last unit standing (spec section L).

Spec: outputs/_cl_tooling_spec.txt section L (maintainer D-9). Out of tree: no source file
is modified. This is outputs/_cl_obs.py (the pass-through sidecar) plus ONE wrap that is
NOT a pass-through: at the END of WildFireModel.step for the step named by
--set CLP_KILL_AT=<step>, the firefighter named by --set CLP_KILL_UNIT=<unit_id> is killed
through the model's own casualty bookkeeping. SERVED rung 1 is only ever engaged when the
OTHER firefighter is already dead (9 of 9 recorded custody markings); the probe manufactures
that situation on a few frozen tuples so SERVED can be observed doing something at all.

COMMAND LINE: exactly the inner harness's, as for _cl_obs_stock.py / _cl_obs_crn.py, e.g.
    _cl_probe.py --repo E:/Projects/SAS --wind south --roles half --seed 1048395951
                 --steps 360 --out outputs/_ffr_clPS0_south_half_1048395951.json --tag clPS0
                 --uav-actions --set BATCH_SIZE=360
                 --set CLP_KILL_AT=132 --set CLP_KILL_UNIT=ff_unit_1
The INSTRUMENT is the one _cl_common.instrument_of() names for the line: "crn" (the fm2
probe harness) iff the line carries --set FM2P_CRN=..., otherwise "stock" (_ffr_harness.py).
_cl_obs.main then applies its own instrument checks unchanged (FM2P_ keys refused on stock;
exactly one FM2P_CRN=1 on crn).
BYTECODE: sys.dont_write_bytecode is set before _cl_obs is imported, as the two launchers do,
so a plain `$PY outputs/_cl_probe.py` (no -B) writes no __pycache__ (rule A3).

THE CLP_* KEYS travel like any other --set key: the harness puts them through
apply_scenario_config (so they land on common_fixed_variables and wildfire_model, and are
recorded in the JSON's params and extra_params), and the kill reads them FROM cfv AT CALL
TIME. The command line is parsed only as a cross-check, before anything runs:
  - the only CLP_ keys are CLP_KILL_AT and CLP_KILL_UNIT, each at most once, both or neither;
  - CLP_KILL_AT is an integer in 1..--steps (as the harness's _parse_value reads it: an int,
    never a bool/float/None); CLP_KILL_UNIT a non-empty string that the harness keeps a str.
  At the first model step (model built, config applied, nothing stepped yet) cfv must hold
  exactly those values with those types and the unit must be a key of
  model.firefighter_marker_agents whose marker's unit_id is that key. Any failure there is
  REFUSED (exit 6, below) before the first step: the harness writes nothing, no sidecar.
With neither key the added wrap is inert (it calls the original and returns its result) and
a run is value-identical to _cl_obs_stock.py / _cl_obs_crn.py on the same line, sidecar
included except json_sha256 (the JSON carries wall_s) and tool_sha256 (it names the
launcher: "_cl_probe.py" here).
ONLY THIS FILE ACTS ON THE CLP_ KEYS. _cl_obs_stock.py / _cl_obs_crn.py run a CLP line
through apply_scenario_config like any key, kill nobody and exit 0 (review 2026-09-26, runs
B and C). A CLP run is therefore trustworthy only with the sidecar evidence that THIS file
ran and resolved the kill: sidecar_problem() below states that check.

REFUSED = EXIT 6. Every refusal raised WHILE THE RUN IS UNDER WAY - the first-step cfv / unit
checks above, and the OFF-GRID and CARRIER refusals at the kill step below - prints
"CLPROBE REFUSED: <reason>" on stderr and exits 6; the harness writes nothing (no JSON, no
.stdout.txt, no sidecar). It is a property of the LINE, not of the attempt: a rerun of the
same line refuses again at the same step, so rc=6 in a pool log is final. (The pool does not
special-case it: the validator reads the job MISSING and the pool retries it up to
MAX_ATTEMPTS, each retry refusing identically.) Command-line refusals, before anything
runs, are exit 2.

THE KILL (model step s == CLP_KILL_AT, after WildFireModel.step returns, i.e. after that
step's post-move cycle, _update_unreachable_victims and _log_step_summary). It is the
firefighter half of wildfire_model.WildFireModel._check_fire_casualties for ONE unit,
statement for statement, WITHOUT the fire-cell test (the probe decides the unit dies, not
the fire), but WITH its pos-is-None precondition (OFF-GRID REFUSAL below):
  victim_ref = rescued_victim; had_active_rescue = assigned or target_pos is not None or
  victim_ref is not None; casualty_vid from _victim_id_from_agent(victim_ref);
  if had_active_rescue and casualty_vid: the unassign THROUGH THE EXECUTOR
      (_execute_physical_rescue_via_executor(PhysicalRescueCommand(action="unassign",
      reason="firefighter_fire_casualty", metadata={"reset_victim_pending": True})), with
      the carrying-leg D2 exception evaluated exactly as the model does - exiting and
      agents.ff_exit_leg_hold() and not _victim_needs_rescue(...) -> metadata {});
  dead=True, status="dead", exiting=False, exit_target=None; managed state
      availability="unavailable", assignment_state="unassigned", route_state="cancelled";
  _rescue_path_clear_requested=True if had_active_rescue;
  _record_rescue_event(casualty_vid, ff_id, "casualty", "firefighter_fire_casualty",
      {"cell": cell}); the firefighter_casualty incident (reason replacement_after_casualty,
      metadata {"cell": cell}) when victim_ref is not None and casualty_vid;
  then, as _check_fire_casualties ends: _sync_firefighter_operational_knowledge(),
      _process_rescue_incidents(), _assert_no_direct_rescue_mutation().
  cell is the unit's own (x, y) - there is no fire cell.
  OFF-GRID REFUSAL: a unit with pos None at step s (a feature-1 absence) is REFUSED (exit 6).
  The model never kills an absent unit (_check_fire_casualties skips pos None), and a dead
  flag set on one does not stick: its return, _return_absent_firefighters ->
  _recycle_firefighter_after_exit, sets dead=False. Measured in this tool's self-test (60
  steps, east/half/101, ff_unit_1 at 30, before this refusal existed): absent 28..32, "dead"
  in rows 30..32, back on the grid "available" and dead=False at 33, assigned victim_2 at 53
  - a resurrected unit.
  CARRIER REFUSAL (the premise; review finding 4): the probe kills the OTHER unit so that the
  carrier is the last unit standing. A kill unit that is exiting at step s IS a carrier:
  killing it unassigns its own victim (reset_victim_pending) and leaves SERVED nothing to
  observe, so the SERVED-0 pre-screen would drop the tuple ("no custody marking") for the
  wrong reason - e.g. a hand-written line with the unit ids swapped. It is REFUSED (exit 6).
  Whether ANOTHER live unit is exiting is not refused but RECORDED in the event's `others`
  field: a tuple the pre-screen drops can be checked for its premise (a live carrier at s)
  before the drop is read as "SERVED has nothing to do here".
  The three frozen spec-L tuples pass both refusals: their recorded rows s-1 have the kill
  unit ON the grid and exiting=False (uhD/ugD south/half/1048395951 ff_unit_1 @132 [4,22],
  carrier ff_unit_0 starting its exit at 132; uhD/ugD east/half/1433805104 ff_unit_0 @206
  [26,40]; ugKD east/def/1420331661 ff_unit_0 @86 [25,22], bound to victim_3, so that kill
  exercises the unassign).
  ONE DELIBERATE DIFFERENCE: the model prints "[Casualty] FF-<unit> reached by fire at
  <cell>", which would be false here; the probe prints "[CLProbe] FF-<unit> killed at step
  <s> at <cell> (CLP_KILL_AT)" at the same point instead (the stdout is hashed into the
  harness JSON; no tool parses "[Casualty]" lines).
  A unit already dead at step s is left alone (counter probe_kill_already_dead; it is the
  last unit standing's premise already).
  TIMING: a fire death of step s happens inside step s's post-move cycle
  (src_extension/adaptation_manager.py run_cycle, phase post_move, _check_fire_casualties);
  the probe kill happens after WildFireModel.step returns. Every stage that FOLLOWS
  _check_fire_casualties in step s therefore sees a fire death at s but a probe death only
  at s+1:
    the rest of the post-move cycle (adaptation_manager.py:183-190):
      _process_rescue_incidents(model) (result "rescue_sync"),
      _sync_firefighter_marker_status() (_revalidate_route_blocked_firefighters, then
      _sync_firefighter_operational_knowledge),
      _sync_victim_agent_status(), _check_rescue_assignment_invariant(model),
      _assert_no_direct_rescue_mutation(); then the summaries _communication_summary and
      _collect_post_move_explanations;
    the rest of WildFireModel.step: _update_unreachable_victims() (so the first
      reachability pass that sees the unit dead is step s+1's), _log_step_summary() (inert:
      the harness sets debug_log False) and latest_dashboard_state (the dashboard's copy;
      the harness's own get_dashboard_state() poll, made while it has no terminal step,
      runs after the kill and does see it).
  The recorded rows agree with a fire death: ff_steps[s-1] (the state after step s) already
  shows the unit dead.
  FOLLOW-ON CHECK (review finding 5): running the five state-changing post-move stages above
  right after the kill, and diffing every ff row (pos, status, assigned, exiting, dead, bound
  victim, dispatch-available), victim marker row (pos, status) and managed victim (status,
  rescue_assigned) before/after, gave NO difference on east/half/101 (60 steps) for
  ff_unit_0 @30 bound to victim_3 (stock and CRN) and ff_unit_1 @40 unbound (review), and
  ff_unit_0 @26 bound to victim_3 while ff_unit_1 carries victim_1 (a live carrier, this
  fix). NOT CHECKED at the three frozen kill steps (132 / 206 / 86 exceed the 60-step
  self-test limit): that check is OWED before the probe wave, per frozen tuple and instrument,
  with this file's argv. Zero differences = the one-step delay changes no recorded row at
  the kill step itself.
  VERIFIED against the model itself (scratch differential, east/half/101, 60 steps, two
  cases: ff_unit_0 @30 bound to victim_3 -> the unassign with reset_victim_pending; ff_unit_1
  @40 unbound): _kill vs model._check_fire_casualties() with the unit's cell added as the
  one burning cell of its fire-cell loop - identical ff/bind/victim rows and fire digests on
  all 60 steps, identical markers, managed firefighter/victim states, rescue event log,
  incident queue and seen keys, path-clear flag and executor audit after the kill; the only
  difference is the one stdout line above.

PROVENANCE PIN: the kill transcribes _check_fire_casualties at 2d5c292 (branch carryleg).
The probe refuses to run (exit 4, before the harness) when that method's source, read with
inspect.getsource, does not hash to CASUALTY_SRC_SHA256 - a changed casualty path would
make the transcription stale silently. This also refuses the 6160438 worktree (no D2
branch). The pin is checked only when the CLP keys are given.

SIDECAR (the _cl_obs one, same path, same shape) plus, ONLY when the CLP keys are given:
  counters probe_kills (the kill applied: 0/1), probe_kill_already_dead (0/1)
  event probe_kill: [step, ff_id, pos, bound_victim_id, had_active_rescue, exiting_before,
                     unassign_metadata_keys (None when no unassign), unassign_success
                     (None when no unassign), others, outcome "killed"|"already_dead"]
      others: [[unit_id, exiting, dead, bound_victim_id ("" if none), pos], ...] for every
      OTHER firefighter marker, sorted by unit id, read BEFORE the kill touches anything
      (pure attribute reads; the bound id read as the harness's ff_bind_steps reads it).
      The outcome is always the LAST field (EVENT_FIELDS).
  A kill that has not resolved by the last step (cannot happen with 1 <= at <= --steps) is
  an observer error -> exit 5, no sidecar.

sidecar_problem(sets, side) -> "" | reason: the check a validator applies to a run of a line
(review finding 1). `sets` is the line's parsed --set dict (typed values, as
_cl_validate's run["sets"]), `side` the parsed sidecar. Pure (reads its arguments only).
  - no CLP_ key: the sidecar must carry no probe_* counter and no probe_* event;
  - CLP_ keys: exactly CLP_KILL_AT (int) and CLP_KILL_UNIT (str); the sidecar written through
    THIS file (tool_sha256 has "_cl_probe.py"); counters probe_kills and
    probe_kill_already_dead exact ints 0/1 summing to 1; exactly one probe_kill event with
    the EVENT_FIELDS layout, its step == CLP_KILL_AT, unit == CLP_KILL_UNIT and outcome
    matching the counter; a "killed" event has exiting_before False, and when it records an
    unassign (metadata keys not None) the pass-through apply wrapper's casualty_unassigns
    holds the same [step, unit, victim, keys].

EXIT CODES: those of _cl_obs.main, plus 2 for a bad CLP_ command line, 4 for the pin and 6
for a refusal during the run (REFUSED above).

REQUIRED OF OTHER TOOLS, NOT HANDLED HERE (review 2026-09-26, findings 1-3):
  - outputs/_cl_obs.py must refuse CLP_ keys when no extra_install is given (the silent
    no-kill path above), and outputs/_cl_validate.py must apply sidecar_problem (or the same
    check) to every ff run;
  - outputs/_cl_pool.sh: under HARNESS=outputs/_cl_probe.py accept an FM2P_ line only with
    --set FM2P_CRN=1 and require a CLP_ key on every line; under any other HARNESS refuse a
    line with a CLP_ key;
  - outputs/_cl_queue.py: a probe stage writing the frozen spec-L tuples as clPS0/clPS1
    (stock) and clKPS0/clKPS1 (CRN) lines, with the arm-line check, the section-C tag
    uniqueness assertion and the seed checks.
"""
from __future__ import annotations

import sys

# The pool may run `$PY <launcher>` without -B: no __pycache__ for _cl_obs or for the
# --repo checkout's modules it imports (rule A3). Set before any further import.
sys.dont_write_bytecode = True

import hashlib  # noqa: E402
import inspect  # noqa: E402

import _cl_obs  # noqa: E402

KEY_AT = "CLP_KILL_AT"
KEY_UNIT = "CLP_KILL_UNIT"
ALLOWED = (KEY_AT, KEY_UNIT)
# sha256 of inspect.getsource(wildfire_model.WildFireModel._check_fire_casualties) at
# 2d5c292 (185 lines). See PROVENANCE PIN above.
CASUALTY_SRC_SHA256 = "aa5eed85a7cc5811ae9b38edf209a1eae90858288c7e379160b5118f00577def"
EXIT_REFUSED = 6
PROBE_COUNTERS = ("probe_kills", "probe_kill_already_dead")
EVENT_FIELDS = ("step", "ff_id", "pos", "bound_victim_id", "had_active_rescue", "exiting_before",
                "unassign_metadata_keys", "unassign_success", "others", "outcome")
LAUNCHER = "_cl_probe.py"

PROBE: dict = {"cfg": None, "want_steps": None, "checked": False, "resolved": False}


class ProbeUsage(Exception):
    pass


def _refuse(msg: str):
    """A refusal during the run: reason on stderr, exit 6 (see REFUSED in the docstring).
    SystemExit is a BaseException: it passes through the harness and the fm2 probe harness,
    which propagate an int code unchanged."""
    print("CLPROBE REFUSED: " + msg, file=sys.stderr)
    raise SystemExit(EXIT_REFUSED)


def _harness_int(raw: str):
    """The harness's _parse_value, restricted to what CLP_KILL_AT may be: an int."""
    text = str(raw).strip()
    if text.lower() in ("true", "false", "none", "null"):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _harness_keeps_str(raw: str) -> bool:
    """True when the harness's _parse_value leaves `raw` a str (not bool/None/int/float)."""
    text = str(raw).strip()
    if text.lower() in ("true", "false", "none", "null"):
        return False
    for conv in (int, float):
        try:
            conv(text)
            return False
        except ValueError:
            pass
    return True


def parse_probe_args(argv: list):
    """-> None (no CLP keys) or {"at": int, "unit": str}; ProbeUsage on anything else."""
    clp = [(k, v) for k, v in _cl_obs._set_items(argv) if k.startswith("CLP_")]
    if not clp:
        return None
    keys = [k for k, _ in clp]
    unknown = sorted(set(k for k in keys if k not in ALLOWED))
    if unknown:
        raise ProbeUsage("unknown CLP_ key(s) %s (only %s)" % (unknown, list(ALLOWED)))
    dups = sorted(set(k for k in keys if keys.count(k) > 1))
    if dups:
        raise ProbeUsage("CLP_ key(s) given more than once: %s" % dups)
    if set(keys) != set(ALLOWED):
        raise ProbeUsage("both %s and %s are required, got %s" % (KEY_AT, KEY_UNIT, keys))
    raw = dict(clp)
    at = _harness_int(raw[KEY_AT])
    if at is None:
        raise ProbeUsage("%s=%r is not an integer" % (KEY_AT, raw[KEY_AT]))
    steps_raw = _cl_obs._argv_value(argv, "--steps")
    try:
        want = int(steps_raw) if steps_raw is not None else 240  # the harness default
    except ValueError:
        raise ProbeUsage("bad --steps %r" % (steps_raw,))
    if not 1 <= at <= want:
        raise ProbeUsage("%s=%d outside 1..%d (--steps)" % (KEY_AT, at, want))
    unit = str(raw[KEY_UNIT]).strip()
    if not unit or not _harness_keeps_str(raw[KEY_UNIT]):
        raise ProbeUsage("%s=%r is not a unit id the harness keeps as a string" % (KEY_UNIT, raw[KEY_UNIT]))
    return {"at": at, "unit": unit, "want_steps": want}


def _cfv_config(cfv):
    """The CLP values as the model sees them NOW (None when neither is set)."""
    have_at = hasattr(cfv, KEY_AT)
    have_unit = hasattr(cfv, KEY_UNIT)
    if not have_at and not have_unit:
        return None
    return {"at": getattr(cfv, KEY_AT, None), "unit": getattr(cfv, KEY_UNIT, None)}


def _check_cfv(cfv, where: str):
    """cfv must hold exactly the command line's values and types (refused otherwise)."""
    cfg = PROBE["cfg"]
    now = _cfv_config(cfv)
    if cfg is None:
        if now is not None:
            _refuse("%s: cfv carries %r but the command line has no CLP_ key" % (where, now))
        return None
    if (now is None or type(now["at"]) is not int or now["at"] != cfg["at"]
            or type(now["unit"]) is not str or now["unit"] != cfg["unit"]):
        _refuse("%s: cfv holds %r, the command line says at=%r unit=%r"
                % (where, now, cfg["at"], cfg["unit"]))
    return now


def _is_dead(marker) -> bool:
    return bool(getattr(marker, "dead", False)) or \
        str(getattr(marker, "status", "") or "").strip().lower() == "dead"


def _others(model, ff_markers: dict, ff_id: str) -> list:
    """[[unit_id, exiting, dead, bound victim id, pos], ...] of every OTHER unit, by id.
    Pure attribute reads (the bound id as the harness's ff_bind_steps reads it)."""
    out = []
    for oid, m in sorted(ff_markers.items(), key=lambda kv: str(kv[0])):
        if str(oid) == str(ff_id):
            continue
        out.append([str(oid), bool(getattr(m, "exiting", False)), _is_dead(m),
                    _cl_obs._vid(model, getattr(m, "rescued_victim", None)),
                    _cl_obs.cell(getattr(m, "pos", None))])
    return out


def _kill(model, mods: dict, ff_id: str, step: int) -> list:
    """The firefighter half of _check_fire_casualties for one unit, minus the fire test."""
    am, wf = mods["am"], mods["wf"]
    ff_markers = getattr(model, "firefighter_marker_agents", {}) or {}
    ff_marker = ff_markers[ff_id]
    pos = getattr(ff_marker, "pos", None)
    cell = (int(pos[0]), int(pos[1])) if pos is not None else None
    victim_ref = getattr(ff_marker, "rescued_victim", None)
    exiting_before = bool(getattr(ff_marker, "exiting", False))
    bound = model._victim_id_from_agent(victim_ref) if victim_ref is not None else ""
    others = _others(model, ff_markers, ff_id)
    if _is_dead(ff_marker):
        return [step, ff_id, _cl_obs.cell(pos), str(bound or ""), None, exiting_before, None, None,
                others, "already_dead"]
    if pos is None:
        # An absent unit cannot die in the model, and a dead flag set on one does not
        # stick: _return_absent_firefighters -> _recycle_firefighter_after_exit sets
        # dead=False (see OFF-GRID REFUSAL in the docstring). Refuse loudly; the harness
        # writes nothing.
        _refuse("%s is off the grid at step %d (status %r, off_grid %r): the model cannot kill an "
                "absent unit - choose a step where it is on the grid"
                % (ff_id, step, getattr(ff_marker, "status", None), getattr(ff_marker, "off_grid", None)))
    if exiting_before:
        # The kill unit is a carrier: the probe's premise is the OTHER unit dying (see
        # CARRIER REFUSAL in the docstring). Refuse before anything is touched.
        _refuse("%s is exiting (a carrier, bound to %r) at step %d: the probe kills the OTHER unit "
                "so that the carrier is the last unit standing - check %s (others: %r)"
                % (ff_id, str(bound or ""), step, KEY_UNIT, others))

    # ---- from here: wildfire_model._check_fire_casualties, the per-unit body ----------
    had_active_rescue = bool(
        getattr(ff_marker, "assigned", False)
        or getattr(ff_marker, "target_pos", None) is not None
        or victim_ref is not None
    )
    casualty_vid = (
        model._victim_id_from_agent(victim_ref) if victim_ref is not None else ""
    )
    meta_keys = None
    unassign_ok = None
    if had_active_rescue and casualty_vid:
        casualty_meta = {"reset_victim_pending": True}
        if (
            getattr(ff_marker, "exiting", False)
            and am.ff_exit_leg_hold()
            and not model._victim_needs_rescue(casualty_vid, victim_ref)
        ):
            casualty_meta = {}
        meta_keys = sorted(casualty_meta)
        result = model._execute_physical_rescue_via_executor(
            wf.PhysicalRescueCommand(
                action="unassign",
                victim_id=casualty_vid,
                firefighter_id=str(ff_id),
                reason="firefighter_fire_casualty",
                metadata=casualty_meta,
            )
        )
        unassign_ok = bool(result.get("success")) if isinstance(result, dict) else False
    ff_marker.dead = True
    ff_marker.status = "dead"
    ff_marker.exiting = False
    ff_marker.exit_target = None
    managed_ff = getattr(model, "managed_firefighters", None)
    if isinstance(managed_ff, dict):
        ff_state = managed_ff.get(ff_id)
        if ff_state is not None:
            try:
                ff_state.availability = "unavailable"
            except Exception:
                pass
            try:
                ff_state.assignment_state = "unassigned"
            except Exception:
                pass
            try:
                ff_state.route_state = "cancelled"
            except Exception:
                pass
    if had_active_rescue:
        model._rescue_path_clear_requested = True
    unit_id = str(getattr(ff_marker, "unit_id", ff_id) or ff_id)
    # the model prints "[Casualty] FF-<unit> reached by fire at <cell>" here (see docstring)
    print(f"[CLProbe] FF-{unit_id} killed at step {step} at {cell} (CLP_KILL_AT)")
    model._record_rescue_event(
        casualty_vid,
        ff_id,
        "casualty",
        "firefighter_fire_casualty",
        {"cell": cell},
    )
    if victim_ref is not None:
        if casualty_vid:
            model._enqueue_rescue_incident(
                {
                    "type": "firefighter_casualty",
                    "victim_id": casualty_vid,
                    "firefighter_id": ff_id,
                    "reason": "replacement_after_casualty",
                    "metadata": {"cell": cell},
                }
            )

    model._sync_firefighter_operational_knowledge()
    model._process_rescue_incidents()
    model._assert_no_direct_rescue_mutation()
    # ---- end of the transcription ----------------------------------------------------
    return [step, ff_id, _cl_obs.cell(pos), str(casualty_vid or ""), had_active_rescue, exiting_before,
            meta_keys, unassign_ok, others, "killed"]


def make_extra_install(cfg):
    def extra_install(mods: dict) -> None:
        wf, cfv, note = mods["wf"], mods["cfv"], mods["note"]
        Model = wf.WildFireModel
        if cfg is not None:
            src = inspect.getsource(Model._check_fire_casualties)
            got = hashlib.sha256(src.encode("utf-8")).hexdigest()
            if got != CASUALTY_SRC_SHA256:
                print("CLPROBE PROVENANCE: WildFireModel._check_fire_casualties at %s hashes %s, "
                      "the transcription is of %s - refusing" % (mods["repo"], got, CASUALTY_SRC_SHA256),
                      file=sys.stderr)
                raise SystemExit(4)
            for counter in PROBE_COUNTERS:
                note(counter, add=0)
            mods["state"]["events"].setdefault("probe_kill", [])

        def make_step(orig):
            def step(self, *a, **k):
                if not PROBE["checked"]:
                    # model built, apply_scenario_config done, nothing stepped yet
                    _check_cfv(cfv, "first step")
                    if cfg is not None:
                        markers = getattr(self, "firefighter_marker_agents", {}) or {}
                        marker = markers.get(cfg["unit"]) if isinstance(markers, dict) else None
                        if marker is None or str(getattr(marker, "unit_id", "") or "") != cfg["unit"]:
                            _refuse("%s=%r is not a firefighter of this model (units %s)"
                                    % (KEY_UNIT, cfg["unit"], sorted(markers) if isinstance(markers, dict) else markers))
                    PROBE["checked"] = True
                result = orig(self, *a, **k)
                if cfg is None:
                    return result
                s = int(getattr(self, "evaluation_timesteps_counter", 0) or 0)
                if not PROBE["resolved"] and s == cfg["at"]:
                    now = _check_cfv(cfv, "kill step")   # read from cfv at call time
                    PROBE["resolved"] = True
                    ev = _kill(self, mods, now["unit"], s)   # model-path exceptions propagate
                    try:
                        note("probe_kills" if ev[-1] == "killed" else "probe_kill_already_dead",
                             "probe_kill", ev)
                    except Exception as exc:
                        _cl_obs._error("probe note", exc)
                elif not PROBE["resolved"] and s >= cfg["want_steps"]:
                    _cl_obs._error("probe", RuntimeError("kill at %d unresolved at step %d" % (cfg["at"], s)))
                return result
            return step

        _cl_obs._wrap(Model, "step", "WildFireModel.step[probe]", make_step)
    return extra_install


def sidecar_problem(sets, side) -> str:
    """"" when the sidecar `side` is a sound record of the line whose parsed --set dict is
    `sets` (see the docstring); otherwise the reason. Pure."""
    if not isinstance(side, dict):
        return "sidecar is not a JSON object"
    counters, events = side.get("counters"), side.get("events")
    if not isinstance(counters, dict) or not isinstance(events, dict):
        return "sidecar has no counters/events objects"
    pc = {k: v for k, v in counters.items() if str(k).startswith("probe_")}
    pe = {k: v for k, v in events.items() if str(k).startswith("probe_")}
    clp = {k: v for k, v in dict(sets or {}).items() if str(k).startswith("CLP_")}
    if not clp:
        if pc or pe:
            return "probe counters/events %s on a line without CLP_ keys" % sorted(set(pc) | set(pe))
        return ""
    if set(clp) != set(ALLOWED):
        return "CLP_ keys %s, the probe takes exactly %s" % (sorted(clp), list(ALLOWED))
    at, unit = clp[KEY_AT], clp[KEY_UNIT]
    if type(at) is not int or type(unit) is not str:
        return "%s=%r / %s=%r are not an int / a str" % (KEY_AT, at, KEY_UNIT, unit)
    tools = side.get("tool_sha256")
    if not isinstance(tools, dict) or LAUNCHER not in tools:
        return ("the line has CLP_ keys but the sidecar was not written through %s (tool_sha256 %r): "
                "no kill was applied" % (LAUNCHER, sorted(tools) if isinstance(tools, dict) else tools))
    if (set(pc) != set(PROBE_COUNTERS)
            or any(type(pc[k]) is not int or pc[k] not in (0, 1) for k in PROBE_COUNTERS)
            or pc["probe_kills"] + pc["probe_kill_already_dead"] != 1):
        return "probe counters %r: want exactly %s, 0/1 each, summing to 1" % (pc, list(PROBE_COUNTERS))
    evs = pe.get("probe_kill")
    if set(pe) != {"probe_kill"} or not isinstance(evs, list) or len(evs) != 1:
        return "probe events %r: want exactly one probe_kill event" % (pe,)
    ev = evs[0]
    if not isinstance(ev, list) or len(ev) != len(EVENT_FIELDS):
        return "probe_kill event %r does not have the %d-field layout %s" % (ev, len(EVENT_FIELDS), list(EVENT_FIELDS))
    outcome = "killed" if pc["probe_kills"] == 1 else "already_dead"
    if type(ev[0]) is not int or ev[0] != at or ev[1] != unit or ev[-1] != outcome:
        return ("probe_kill event step %r unit %r outcome %r != line %s=%d %s=%r, counters say %s"
                % (ev[0], ev[1], ev[-1], KEY_AT, at, KEY_UNIT, unit, outcome))
    if outcome == "killed":
        if ev[5] is not False:
            return "probe_kill event %r: the killed unit was exiting (the probe refuses that)" % (ev,)
        if ev[6] is not None:
            want = [ev[0], unit, ev[3], ev[6]]
            cu = events.get("casualty_unassigns")
            if not isinstance(cu, list) or want not in cu:
                return ("probe_kill records an unassign but casualty_unassigns %r has no %r"
                        % (cu, want))
    return ""


def main() -> int:
    argv = list(sys.argv[1:])
    try:
        cfg = parse_probe_args(argv)
    except ProbeUsage as exc:
        print("CLPROBE: %s" % exc, file=sys.stderr)
        return 2
    PROBE["cfg"] = cfg
    harness = "crn" if any(k == "FM2P_CRN" for k, _ in _cl_obs._set_items(argv)) else "stock"
    return _cl_obs.main(harness, extra_install=make_extra_install(cfg))


if __name__ == "__main__":
    raise SystemExit(main())
