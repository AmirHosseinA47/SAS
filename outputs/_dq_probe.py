"""Dispatch round 2 instrument: outputs/_dq_probe.py ("dq_probe v1"; outputs/dispatch2_part1.txt 12.1, 10.1-10.3,
11.2; rulings section 19).

The movement round's outputs/_mvg_probe.py (mvg_probe v1) with round 1's J-point machinery (outputs/_dp_probe.py,
dp_probe v2) restored and ADAPTED to the corrected J API (src_extension/planning/joint_dispatch.py as corrected by
dispatch round 2), plus the round's new recorders. usage (exactly _mvg_probe.py's interface):
    _dq_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args ...>
    --repo is REQUIRED after "--" (every layer below defaults to the main checkout otherwise).
It runs outputs/_ut_probe.py (UNCHANGED, in-process) as _mvg_probe did; every movement / guard / kick recorder of
_mvg_probe is kept with its meaning (d["ud"], d["mv"], d["mv_events"], d["mvg"]), so the movement round's zero checks
port unchanged. It LOADS and RUNS at main 897e93b5 (arm dqR), where no joint_dispatch module and no DISPATCH_* key
exist: every J hook is read through getattr defaults and every J wrap is a pass-through while DISPATCH_JOINT is off.

RECORD-ONLY (as _mvg_probe): no draw from any RNG, no print to stdout of its own (the invariant checker's stderr lines
are re-emitted, as _dp_probe does), no attribute set on the model or an agent. Every wrap is installed at CLASS level
(or on the joint_dispatch MODULE object wildfire_model calls through, _jd.<f>) BEFORE the model is built. The new
recorders are guarded like the shadows: the model's attributes (shallow), every living unit's __dict__ and the RNG
states are compared before and after the instrument's work at every J point and every sample; a difference is an
instrument error (d["dq"]["errors"]). Observer exceptions are caught and listed; an observer never stops a run. d is
written whatever the chain's return code.

WHAT CHANGED FROM mvg_probe v1, AND WHY
  1. RESTORED from _dp_probe v2 (12.1), adapted to the corrected J (no-ops while DISPATCH_JOINT is off):
     - the jpoint wrap of WildFireModel._joint_dispatch_point, with legacy_pairs = 11.2's counterfactual ("today's
       choice": for each detected needy victim without an active binder - W, and W_L as legacy treats it, a second
       claimant - in victim-index order (trailing integer, then the id), the Manhattan-nearest UNCHOSEN free unit,
       any route, ties to the smaller id STRING, exactly select_rescue_assignment's `ff_s < str(best_ff)`);
     - PRE / sets, j_detail (progress before and after, "unevaluated", "initialised");
     - j_timing [step, phase, raw_ms, net_ms, thread_ms, gc_collections]; net = raw minus the instrument's work
       nested inside the J call (the _cap recorders, the command / release recorders); dp.timing j_ms_total (net),
       j_ms_raw_total;
     - the _cap wraps of the corrected J's pure functions solve_fill, progress_step, update_persistence and
       plan_replacements_detail (plan_replacements is NOT wrapped: it calls plan_replacements_detail through the
       module global, and the model never calls it), recording their full inputs and outputs while a J call is open.
  2. NEW AT EVERY J POINT WHERE PRE HOLDS (dq1), in that j_detail entry (see DQ_SCHEMA):
     - "inst": the INSTRUMENT'S OWN independent maps (its own flat 4-connected BFS, its own fire and smoke reads of the
       Fire agents, its own unclean predicate, never the model's helpers): for every living on-grid unit to every
       victim of interest (W, W_L and every contest's victim) [d, D_c, d*, clean]: d = the fire-free BFS from the
       victim's cell (the source never tested) read at the unit's cell with the unit-cell exemption; D_c = the clean
       BFS (cells in bounds, not burning, not smoky, no burning 4-neighbour) from the victim's cell (None for every
       unit when that cell is unclean), read with the same exemption; d* = D_c if finite else d (None when d is None);
       clean = D_c finite. The burning-set and smoke digest (sha1[:16] of the sorted burning cells | the sorted active
       smoke cells), their sizes, every living unit's cell / unclean flag / status, the full ledger at J entry.
     - "contests": each contest's label, open / closed, delta, FROZEN, k and k_L before / after, H before / after,
       the progress verdict and "initialised", as J SAW them (read from the _cap records), plus the instrument's own
       open / delta / frozen.
     - "zr1": Z-R1's mismatches at this J point (10.3): every d / D_c / d* / clean / delta / route-open / FROZEN value
       J passed to its pure functions, and every progress verdict (the next k, k_L, H) and persistence count it
       derived, against the instrument's recomputation from its own maps and its OWN implementation of R-1's history
       rule and C2's counts (hist_progress / persist_generic below - the rule as joint_dispatch.progress_step states
       it, with amendment A2's reading: a metric with no finite value over H is not compared). The literal 2.8 reading
       (a minimum over an empty set is infinite) is counted apart where it would give another verdict
       (d["dq"]["zr1"]["a2_literal_differs"]; reported, never a mismatch).
     - "fp": the ACTED footprint (12.1, 10.9): the decision of the corrected J replayed as a pure function on the
       recorded inputs ("base", J's own module functions; base == "actual", the _cap outputs, is checked), of ROUND
       1's J (the frozen copy outputs/_dq_r1_shadow.py = git show cc8d653c:src_extension/planning/joint_dispatch.py,
       loaded BY PATH as module "dq_r1_shadow", sha256 recorded), and of four single-change reversions (see
       FOOTPRINT_DOC). "acted" lists the variants whose decision differs from base.
  3. NEW IN EVERY ARM - THE ARM-INDEPENDENT PER-STEP SAMPLE (10.1, 12.1): right after
     WildFireModel._sync_firefighter_marker_status returns (once per step), d["dq"]["sample"]: the victims at that
     instant (W = detected needy, no living binder, not in custody; WL = every living binder route_blocked, not in
     custody; custody; active) and, for every unbound, living, on-grid, non-exiting unit of ANY status label (and
     every free unit), its status, free flag, cell, move flag (cell != its cell at the previous sample; None at its
     first), the instrument's own fire-free BFS verdict (unit-cell exemption) to every victim of W + WL, and its rows
     of the model's firefighting log (model._firefight_log, agents.Firefighter._firefight_log_row) appended since the
     previous sample - the advance just sampled - as [action, wrote]. d["dq"]["ff_log"]: the whole firefighting log,
     compact.
  4. THE U1 KICK SHADOW is gated off while DISPATCH_JOINT is on (10.3, 12.1): no kick record is made (d["ud"]["kicks"]
     stays empty; d["dq"]["kick_gated"] counts the gated kicks). Every other shadow row stays.
  5. VERSIONS: d["dq"]["probe"] = d["ud"]["probe"] = d["mvg"]["probe"] = "dq_probe v1" (the instrument); d["dp"]["probe"]
     = "dp_probe v3" (round 1's dp section: every non-J field unchanged; j_calls / j_detail / j_timing / timing in the
     corrected-J form). d["mvg"]["probe_sha"] = d["dq"]["probe_sha"] = the LF sha256 of THIS file read when the run
     starts.

THE MOVEMENT, GUARD AND KICK RECORDERS are _mvg_probe.py's, code unchanged (diffed): its docstring (outputs/_mvg_probe.py)
states their design - the instrument's guard verdict is frozen_guard_replica (a verbatim copy of the frozen guard() of
outputs/_mvg_guard_diag.py on the U1 shadow copy's helpers), movement_paths.stranding_guard the cross-check
(mp_verdict / mp_mismatch), the shadows pure and guarded, the survival_writes replica checked in-run.

d["dp"]   _dp_probe v2's section with the J fields of 1 and 2 (see DP_J_SCHEMA).
d["ud"], d["mv"], d["mv_events"], d["mvg"]   exactly _mvg_probe's (MVG_SCHEMA, MV_SCHEMA, UD_SCHEMA) - kicks gated (4).
d["dq"]   probe, probe_sha, switches, src_sha, r1_shadow_sha / _path / _error, schema, sample, ff_log, zr1, footprint,
          kick_gated, timing, errors (see DQ_SCHEMA).
"""
from __future__ import annotations

import gc
import hashlib
import heapq
import importlib.util
import io
import json
import math
import os
import re
import runpy
import sys
import time
import types
from collections import deque
from math import comb, perm

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "dq_probe v1"
DP_VERSION = "dp_probe v3"
# round 1's J, frozen: git show cc8d653c:src_extension/planning/joint_dispatch.py, saved LF as outputs/_dq_r1_shadow.py
# and loaded BY PATH (never from the repo); sha256 of its LF-normalised bytes (= the cc8d653c blob's sha256)
R1_SHADOW = os.path.join(HERE, "_dq_r1_shadow.py")
R1_SHADOW_MODULE = "dq_r1_shadow"
R1_SHADOW_SHA = "6f5f45fa5acb08c9603332ac5a90274d32961fb95cb35ad48eac3171007145f9"
R1_SHADOW_SOURCE = "cc8d653c:src_extension/planning/joint_dispatch.py"
# d["dq"]["src_sha"]: every repo file the dispatcher, the movement and the instrument's inputs live in
DQ_SHA_FILES = (
    "src_extension/planning/joint_dispatch.py",
    "wildfire_model.py",
    "agents.py",
    "common_fixed_variables.py",
    "src_extension/planning/movement_paths.py",
    "src_extension/planning/fire_arrival_estimate.py",
    "src_extension/adaptation_manager.py",
    "src_extension/execution/rescue_executor.py",
    "src_extension/planning/rescue_planner.py",
    "src_extension/adaptation/local_adaptation_generator.py",
)
DQ_SWITCHES = ("DISPATCH_JOINT", "DISPATCH_REASSIGN", "DISPATCH_STALL_STEPS", "DISPATCH_MARGIN_STEPS",
               "DISPATCH_MARGIN_PERSIST")
# the arm-independent per-step sample (10.1, 12.1): one row per _sync_firefighter_marker_status return
SAMPLE_COLS = ("step", "W", "WL", "custody", "active", "units")
SAMPLE_UNIT_COLS = ("unit", "status", "free", "bound", "cell", "moved", "routes", "log")
FFLOG_COLS = ("step", "ff", "action", "engaged", "plan", "cell", "target", "wrote", "scorched", "dry", "suspend_set")
CONTEST_COLS = ("victim", "incumbent", "label", "latched", "open", "delta", "frozen", "k0", "kL0", "k1", "kL1", "H0",
                "H1", "progressed", "initialised", "unit_unclean", "i_open", "i_delta", "i_frozen")
FP_VARIANTS = ("r1", "C1", "C2", "R1", "R2")
FP_MAX_CONFIGURATIONS = 100_000          # joint_dispatch.MAX_CONFIGURATIONS (design 5.5), the instrument's own copy
U1_SHADOW = os.path.join(HERE, "_mvg_u1_shadow.py")
U1_SHADOW_MODULE = "mvg_u1_shadow"
# the frozen guard whose body frozen_guard_replica() copies verbatim: outputs/_mvg_guard_diag.py (urgency:outputs/
# _mvg_guard_diag.py, Part 1d 1d.2.6), sha256 of its LF-normalised bytes
FROZEN_GUARD_FILE = "outputs/_mvg_guard_diag.py"
FROZEN_GUARD_SHA = "70eeba7877dae6174999ae2a00774bdeeb36ced08d35df407f27318cd3a313b2"
_N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
# _dp_probe v2's list, unchanged (d["dp"]["src_sha"])
SHA_FILES = (
    "src_extension/planning/joint_dispatch.py",
    "src_extension/adaptation_manager.py",
    "src_extension/execution/rescue_executor.py",
    "src_extension/planning/rescue_planner.py",
    "wildfire_model.py",
    "agents.py",
    "common_fixed_variables.py",
)
# the repo files this round's code lives in (d["ud"]["src_sha"] and d["mvg"]["src_sha"]); urgency_dispatch.py is NOT
# here: U1 is not in the repo, its instrument-only copy is hashed apart (d["mvg"]["u1_shadow_sha"])
MVG_SHA_FILES = (
    "agents.py",
    "wildfire_model.py",
    "common_fixed_variables.py",
    "src_extension/planning/movement_paths.py",
    "src_extension/planning/fire_arrival_estimate.py",
)
MVG_SWITCHES = ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_FIX_STRANDING_GUARD")
URGENCY_SWITCHES = ("DISPATCH_URGENCY", "FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_CARRY_REPLAN")
OTHER_SWITCHES = ("FF_EXIT_LEG_MODE", "FF_EXIT_LEG_SERVED", "FF_EXIT_LEG_HOLD", "ROUTE_BLOCK_STALE_CLEAR")
MV_COLS = (
    "step", "unit", "victim", "leg", "branch", "pre", "post", "target", "digest",
    "st_pre", "st_post", "tier", "mt", "rb_call", "rb_set",
    "trig", "zrb", "today", "fa", "fb", "fbB", "fc", "acted",
    "dc", "dcx", "df", "dm", "dr", "gesc",
    "cls_pre", "cls_post", "fd_pre", "fd_post", "c1_pre", "c1_post",
    "fix_ms", "inst_ms", "dcb",
    "gA", "gB", "veto", "acted_g",
)
_INST_MS_I = MV_COLS.index("inst_ms")
GUARD_COLS = (
    "step", "unit", "victim", "kind", "u", "n", "v", "today", "today_kind", "today_tier", "today_raise",
    "c", "T_v", "admit", "model_admit", "model_verdict", "model_cell", "took", "post", "tier", "raise",
    "pre_writes", "pred_writes", "post_writes", "ms_guard", "ms_inst", "row", "mp_verdict",
)
FIX_BRANCH = {"a": "approach_a", "b": "retreat_b"}
VETO_BRANCH = {"a": "approach_a_veto", "b": "retreat_b_veto"}
MV_SCHEMA = (
    "mv cols (v2 meaning unless stated): step = evaluation_timesteps_counter at the advance (rows_ff index + 1); "
    "unit / victim = ids (victim = the bound victim before the advance); leg approach|carry; branch = the branch the "
    "advance TOOK, GUARD-AWARE: approach (today's _move_toward; the fix did not act or is off), approach_a (fix (a)'s "
    "step was taken: guard off, or the guard admitted), approach_a_veto (fix (a)'s pure choice returned a cell, the "
    "guard was on and the MODEL's verdict vetoed it: today's step ran), retreat (today's survival retreat), retreat_fb "
    "(survival with no move -> _move_toward), retreat_b (fix (b)'s step taken), retreat_b_veto (fix (b) would have "
    "acted, the model's guard vetoed: today's survival retreat and its fallback ran), pickup; carry: path / "
    "fallback[_hold|_raise] (MODE 2), greedy[_hold|_raise] (MODE 0/1), complete; other:<fine_category>. pre / post = "
    "cells (a vetoed decision whose fix step was nevertheless taken - post the fix's cell with its tier - is labelled "
    "approach_a / retreat_b: the label is the step TAKEN; veto says what the model's guard said); target = "
    "post-refresh target (approach) or exit_target (carry); digest = sha1[:16] of sorted burning + "
    "sorted active-smoke cells read at the decision; st_pre / st_post = status; tier = _last_move_tier after the "
    "advance (stale when the advance did not set it); mt = _move_toward calls; rb_call = _mark_route_blocked calls; "
    "rb_set = those that set route_blocked; trig = the survival trigger held (approach); zrb = today's raise "
    "predicate (instrument's own BFS); today = TODAY's shadow [kind, cell, tier, raise] (approach: greedy; survival: "
    "survival, or fallback when _survival_choice would not move; carry: path = MODE 2 exit_leg_first_step, else greedy "
    "/ hold / raise); fa / fb = fix (a) / fix (b) cell from the pure methods BEFORE the advance (None where not "
    "evaluated); fbB = the on-route clean neighbours with the smallest clean distance; fc = always None (no fix (c) in "
    "this round; the column keeps v2's indices); acted = letters of the fixes whose UNGUARDED shadow ACTED (22.8.2: a "
    "= fa not None and != today's cell; b = fb not None on a survival step); dc / dcx / df / dm / dr / gesc / cls_* / "
    "fd_* / c1_* / dcb as v2; fix_ms = ms in fix code during the advance (pure choices, _fix_move and the guard) when "
    "the model called it; inst_ms = the instrument's ms for the row. NEW: gA / gB = the INSTRUMENT's guard verdict "
    "(the frozen-function replica, frozen_guard_replica, on the decision board) for fa / fb when that fix would act, "
    "else None; veto = letters of the fixes whose live step the MODEL's guard vetoed in this advance; acted_g = the "
    "letters of acted whose instrument verdict admits (what the fixes do in arm G). None = not applicable / infinite. "
    "NOT GUARDED: acted (above) and mv_events 'live' (the fix's switch is effective) keep v2's unguarded meaning; the "
    "GUARDED fields Part 1d 1d.8 (5) calls acted / live are acted_g (here) and mv_events 'ran'."
)
MVG_SCHEMA = (
    "guard rows (cols GUARD_COLS): one per decision at which fix (a) or (b) WOULD act (the pure choice returns a cell n "
    "!= today's), in EVERY arm: step, unit, victim, kind a|b, u = the unit's cell, n = the fix's cell, v = target_pos "
    "after the refresh (the bound victim's cell), today = today's cell (a: _greedy_choice; b: _survival_choice, or the "
    "fallback greedy cell when survival would not move; None = today's step does not move), today_kind (greedy | "
    "survival | fallback), today_tier (the tier today's _move_toward writes; None for survival), today_raise (today's "
    "raise predicate), c = c_n (None = infinite), T_v = FAE T at v (None = infinite), admit = the INSTRUMENT's verdict "
    "(c / T_v / admit are the FROZEN FUNCTION's: frozen_guard_replica, a verbatim copy of the body of "
    "outputs/_mvg_guard_diag.guard - sha256 70eeba78... of its LF form - on the U1 shadow copy's unclean_cells / "
    "t_star / safe_route_hops and fire_arrival_estimate.arrival_time with FrontPriorityParams(), on the decision "
    "board; it shares no guard code with the model's guard - FAE is common by design; None if it raised), "
    "model_admit = the MODEL's verdict (the return of _stranding_guard_verdict called inside "
    "_guarded) or None when the model did not evaluate the guard (fix off: arm 0; guard off: arm N; a knocked-out "
    "choice), model_verdict = [admit, c, T_v] of that call, model_cell = the cell it was evaluated on, took = 'fix' if "
    "post == n and _last_move_tier after the advance is the fix's tier (7 / 10), else 'today', post = the unit's cell "
    "after the advance, tier = _last_move_tier after it, raise = _mark_route_blocked was called in the advance, "
    "pre_writes / pred_writes / post_writes (kind b; else None) = the _idle_retreat_* state [origin, steps, stalled, "
    "last_cell] before the advance / as a PURE replica of today's _survival_move would leave it (survival_writes) / "
    "after the advance, ms_guard = the model's guard call ms (None if not evaluated), ms_inst = the instrument's guard "
    "ms, row = the index of the advance's d['mv'] row, mp_verdict = [admit, c, T_v] of the REPO function "
    "movement_paths.stranding_guard (the function the model calls) on the same arguments - a CROSS-CHECK column; it "
    "must equal [admit, c, T_v] (None if it raised); mp_mismatch = [step, unit, kind, row index in guard rows, "
    "[admit, c, T_v] (instrument), mp_verdict] for every guard row where they differ (must be empty). "
    "replica: the survival_writes replica checked at EVERY advance "
    "with the survival trigger: where today's _survival_move ran (branch retreat / retreat_fb / retreat_b_veto) the "
    "predicted writes must equal the unit's post-advance state (checked / mismatch), where fix (b)'s step ran "
    "(retreat_b) the state must be unchanged (fix_checked / fix_mismatch), and the replica's destination must be "
    "today's survival cell (_survival_choice; cell_checked / cell_mismatch). timing: guard_ms = every model guard call "
    "(ms), guard_calls, inst_guard_ms = every instrument guard evaluation (ms; the frozen-function replica's). "
    "probe_sha = sha256 of outputs/_dq_probe.py's LF-normalised bytes (dq_probe v1: the instrument that wrote the "
    "record), read when the run starts; u1_shadow_sha = sha256 of the U1 shadow copy's LF-normalised bytes (both "
    "CRLF-checkout safe)."
)
UD_SCHEMA = (
    "ud_probe v2's kick schema, unchanged: kicks (W, F, index, qualifies, u1, rec, d, ms, div_shadow, nB, z4, z4_ok, "
    "acc, index_wb, u1_wb, div_shadow_head, bound, n_cmd, attempts, divergent, divergent_head, ms_model, triage, i, "
    "step, phase, site, switch, inst_ms) - the U1 shadow computed by the instrument-side replicas and the frozen U1 "
    "copy (no U1 in the model: switch always False, ms_model / triage always None); decisions, fates, cmd_ctx, rel_ctx "
    "and shadow_mismatch as v2. shadow_mismatch movement rows: [step, unit, 'a' | 'b', text, branch, cell, taken] - "
    "'shadow acted, model did not' (the guarded shadow expected the fix's step), 'guard vetoes (instrument), model did "
    "not take today's step', 'model acted, shadow did not', 'guard evaluated on a cell other than the shadow's', "
    "'model guard verdict != instrument verdict' (Zg-1). dq_probe v1: NO kick record is made while DISPATCH_JOINT is "
    "on (the U1 kick shadow is gated off, 12.1; d['dq']['kick_gated'] counts the gated kicks)."
)
DP_J_SCHEMA = (
    "dp_probe v3 = dp_probe v2's section with the corrected J's fields. Every non-J field (commands, releases, binders, "
    "waiting, waiting_custody, m3a, invariant, m8, m9, writeoffs_avoided, errors) is v2's, unchanged. J fields (empty "
    "while DISPATCH_JOINT is off): j_calls = every J call: [step, phase, net_ms, new_events(, {'legacy': [[victim, "
    "unit], ...] - 11.2's counterfactual on J's own snapshot (W and W_L), 'j_fills': [[victim, unit], ...] - J's stage-2 "
    "fills, 'stage3': [[kind, victim, unit, [old units]], ...] - replace / latch_fill / nearest_barred events, "
    "'stage4': [[kind, victim, unit], ...] - second fills})]; j_events = the model's _dispatch_events at the end; ledger "
    "= {'unit|victim': binds}; j_timing = every J call: [step, phase, raw_ms, net_ms, thread_ms, gc_collections]; "
    "j_detail = every J call at which PRE held: [step, phase, cur] with cur = {'sets': {free, waiting, latched, contest "
    "(active {victim: unit}), latched_binder ({victim: unit}), fill_victims, binders ({victim: [units]} of every victim "
    "of interest), reassign, post}, 'pre': True, 'calls': the _cap records in call order, 'progress_before' / 'progress' "
    "= {'unit|victim': [H, k, k_L, closed, age, persist]} at J entry (before J's prune) / at J exit, 'unevaluated' = "
    "[[unit, victim]] contests holding a state at entry that got no progress_step call (a structural 0 in the corrected "
    "J), 'initialised' = [[unit, victim]] contests without a state at entry (new_progress, no count), 'inst', "
    "'contests' (CONTEST_COLS), 'zr1', 'fp' (see DQ_SCHEMA)}. _cap records: solve_fill {fn, stage (2 | 4), units, "
    "victims, d {'u|v': d*}, clean {'u|v': bool}, b {'u|v': ledger count, non-zero only}, capped, out [[victim, unit, "
    "distance, reused, clean]]}; progress_step {fn, binding [unit, victim], open, d, c, d_hist, c_hist, cell, frozen, "
    "before [H, k, k_L, closed, age], after [H, k, k_L, closed, age]}; update_persistence {fn, binding, spare_d {unit: "
    "d*}, delta, M, before {unit: count}, after {unit: count}}; plan_replacements_detail {fn, contests [[victim, "
    "incumbent, delta, open, k, k_L, persist, latched]], spares, d, clean, b, S, P, out [[victim, old, new, cause, "
    "distance, latched]], barred [[victim, incumbent, cause, distance, [units]]]}. timing: j_ms_total (net), "
    "j_ms_raw_total, inst_ms_total (the dp recorders)."
)
FOOTPRINT_DOC = (
    "fp (the ACTED footprint, 12.1 / 10.9; reported, never gating). Every decision is recomputed by PURE functions on "
    "the J point's recorded inputs (sets, inst maps, ledger, progress_before and the shadow states r1_before / "
    "rv1_before) - footprint() below; _dq_probe_check.py recomputes it offline from the record. A decision = {'pairs': "
    "sorted [[kind, victim, new unit, [old units]]] - kind fill / latch_fill / replace / second_fill - , 'barred': "
    "[[victim, incumbent, cause, D, [units]]]}. Steps 3-4 assume every planned bind applies and that a released ACTIVE "
    "unit is free again (a released latched unit is route_blocked, not free). "
    "base = the corrected J (joint_dispatch's own functions, captured before the _cap wraps): step 1 progress_step on "
    "progress_before with the inst values (new_progress where none), step 2 solve_fill(free, W - or W + W_L under "
    "Limit 2 alone -, d*, clean), step 3 update_persistence + plan_replacements_detail over the contests (active and "
    "latched; under Limit 3 at J-post), step 4 solve_fill(released active units, W not filled in step 2). "
    "actual = the _cap outputs (base_eq_actual: pairs and barred equal). "
    "r1 = ROUND 1's J (the frozen dq_r1_shadow module): fill free x (W + W_L) on the fire-free d with round 1's key "
    "(L2 = fewest re-used) and W_L capped (LATCH-FILL, old units = the victim's binders) under Limit 3; contests ACTIVE "
    "only, round 1's e-shift progress on d from the r1 shadow state (an instrument-held round-1 Progress per binding, "
    "updated at every J-post on the actual trajectory, initialised at every J bind with new_progress(d, cell), pruned "
    "with J's prune, dropped at every assign), a contest with d or x infinite not evaluated, persistence for FRESH "
    "spares only, round 1's plan_replacements (stall needs a clean approach, margin does not; fresh pairs only); step 4 "
    "over W + W_L, W_L capped. "
    "C1 = base with C1 reverted: the fill key with the ledger as L2 right after L1b (-served, -clean pairs, re-used, "
    "total d*, worst d*, ids) in steps 2 and 4; a replacement takes the NEAREST ALLOWED qualifying spare (the ledger "
    "filters the qualifying spares before the least d* is taken; no Barred record; the contest gain is computed "
    "against that spare) - persistence as base (every spare). "
    "C2 = base with C2 reverted: W_L joins the step-2 fill under the cap (b >= 2 barred; a bind is a LATCH-FILL with "
    "the victim's binders as old units) and step 4 offers W + W_L (W_L capped); the contests are the ACTIVE bindings "
    "whose route is OPEN (round 1's 'not evaluated' for a closed one: no replacement); their counts are base's. "
    "R1 = base with R-1 reverted: the fire-free d in place of d* everywhere (fill L2' / L3', margin d(B) + M <= delta, "
    "stall d(B) < delta + count; delta = d open, G closed) and round 1's e-shift progress from the rv1 shadow state "
    "(best, k, d_prev, cell_prev, k_L, closed, age, persist; held like r1's, for active AND latched contests): route "
    "closed -> k_L + 1 unless FROZEN, the reference untouched; route open -> k_L = 0, and if the reference was never set "
    "(the binding met only closed routes) it is set to (d, cell) without a count, if x (d at cell_prev) is infinite "
    "the frame is round 1's 'not evaluated' (no count, reference untouched), else round 1's e-shift step; persistence "
    "for every spare on d (C1 kept); R-2 kept (L1b and every challenger clean). "
    "R2 = base with R-2 reverted: the fill key without L1b (-served, total d*, worst d*, re-used, ids) and margin "
    "challengers without the clean-approach requirement (stall challengers keep it, round 1's 6.4). "
    "acted = the variants whose pairs differ from base's (barred records are not compared)."
)
DQ_SCHEMA = (
    "d['dq']: probe 'dq_probe v1'; probe_sha (LF sha256 of outputs/_dq_probe.py at run start); switches {raw DISPATCH_* "
    "reprs (None = absent: main), joint_on, reassign_on, S, M, P, FF_APPROACH_PATH, FF_RETREAT_KEEP_APPROACH, "
    "FF_FIX_STRANDING_GUARD (effective)}; src_sha {repo file: sha256 of its bytes} (DQ_SHA_FILES present in the "
    "checkout); r1_shadow_sha / r1_shadow_path / r1_shadow_error (the frozen round-1 J copy, LF sha256); schema; "
    "sample {cols SAMPLE_COLS, unit_cols SAMPLE_UNIT_COLS, rows: [step, W, WL, custody, active, units]} - units = "
    "[[unit, status, free, bound, cell, moved, routes [[victim, d | None], ...] over W + WL, log [[action, wrote], ...]]] "
    "sorted by unit id, victims sorted as strings; ff_log {cols FFLOG_COLS, rows} - every model._firefight_log row, "
    "compact, read at run end; zr1 {jpoints, checked, mismatch (first 200: [step, phase, text]), n_mismatch, "
    "a2_literal_differs}; footprint {jpoints, acted {variant: J points}, base_ne_actual [[step, phase]], errors}; "
    "kick_gated (kicks with no record because DISPATCH_JOINT was on); timing {dq_ms_total, jpoint_ms, footprint_ms, "
    "sample_ms, purity_ms}; errors (observer exceptions and purity-guard failures of the new recorders). inst (per J "
    "point, in d['dp']['j_detail']): {digest, nB, nS, ucell {unit: [x, y, unclean, status]} (every living on-grid "
    "unit), vcell {victim: [x, y, vclean]} and dist {victim: {unit: [d, D_c, d*, clean]}} (every victim of interest: W, "
    "W_L and every contest's victim), hist {'u|v' of every contest: {'H': [[d, D_c] at each cell of the binding's H at "
    "J entry, in H's order], 'x_r1': d at the r1 shadow state's cell_prev, 'x_rv1': d at the rv1 state's cell_prev} "
    "(keys present only where that state exists)}, ledger {'u|v': b} (the full ledger at J entry), SMP [S, M, P]}. "
    + FOOTPRINT_DOC
)

_MISSING = object()


# ---------------------------------------------------------------------------------------------- pure helpers
def _bfs(source, grid, blocked):
    """The instrument's own 4-connected BFS from `source` over in-bounds cells not in `blocked` (_dp_probe)."""
    start = (int(source[0]), int(source[1]))
    dist = {start: 0}
    queue = deque([start])
    while queue:
        cx, cy = queue.popleft()
        for ox, oy in _N4:
            cell = (cx + ox, cy + oy)
            if cell in dist or cell in blocked or grid.out_of_bounds(cell):
                continue
            dist[cell] = dist[(cx, cy)] + 1
            queue.append(cell)
    return dist


def _at(dist, cell, blocked):
    """d at a unit's cell, the unit's own cell exempt like the route test's source (_dp_probe)."""
    cell = (int(cell[0]), int(cell[1]))
    if cell in dist:
        return dist[cell]
    if cell not in blocked:
        return None
    near = [dist[(cell[0] + ox, cell[1] + oy)] for ox, oy in _N4 if (cell[0] + ox, cell[1] + oy) in dist]
    return min(near) + 1 if near else None


def _cell(pos):
    return None if pos is None else (int(pos[0]), int(pos[1]))


def _jc(cell):
    return None if cell is None else [int(cell[0]), int(cell[1])]


def _fin(value):
    value = float(value)
    return None if math.isinf(value) else value


def _is_boundary(cell, oob):
    return any(oob((cell[0] + ox, cell[1] + oy)) for ox, oy in _N4)


def _unclean(burning, smoky, oob):
    """Burning, 4-adjacent to burning (in bounds) or active-smoke cells: the complement of CLEAN in the grid."""
    out = set()
    for c in burning:
        out.add(c)
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if not oob(n):
                out.add(n)
    out.update(smoky)
    return out


def _cls(cell, burning, smoky):
    if cell in burning:
        return "B"
    if any((cell[0] + ox, cell[1] + oy) in burning for ox, oy in _N4):
        return "A"
    if cell in smoky:
        return "S"
    return "C"


def _mfd(cell, burning):
    if not burning:
        return 999
    return min(abs(cell[0] - x) + abs(cell[1] - y) for x, y in burning)


def _digest(burning, smoky):
    h = hashlib.sha1()
    h.update(repr(sorted(burning)).encode())
    h.update(b"|")
    h.update(repr(sorted(smoky)).encode())
    return h.hexdigest()[:16]


def _clean_field(target, unclean, oob):
    """(D, has_exit): BFS over CLEAN cells from `target` (which must be clean, else empty), and whether the region
    touches the grid boundary (G-ESC). The instrument's own code."""
    if oob(target) or target in unclean:
        return {}, False
    dist = {target: 0}
    queue = deque([target])
    has_exit = False
    while queue:
        c = queue.popleft()
        if not has_exit and _is_boundary(c, oob):
            has_exit = True
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if n in dist or oob(n) or n in unclean:
                continue
            dist[n] = dist[c] + 1
            queue.append(n)
    return dist, has_exit


def _dist_boundary(start, passable, oob):
    """Hops from `start` (exempt) to the nearest passable boundary cell; 0 if start is a boundary cell; None if none."""
    if _is_boundary(start, oob):
        return 0
    dist = {start: 0}
    queue = deque([start])
    while queue:
        c = queue.popleft()
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if n in dist or oob(n) or not passable(n):
                continue
            dist[n] = dist[c] + 1
            if _is_boundary(n, oob):
                return dist[n]
            queue.append(n)
    return None


def _c1_cost(start, burning, smoky, oob):
    """[fire-adjacent cells entered, smoky cells entered, length] of a least-exposure path (lexicographic) from
    `start` (exempt) over non-burning cells to a non-burning boundary cell; [0, 0, 0] on a boundary cell; None when no
    such cell is reachable (a pocket). The instrument's own Dijkstra."""
    if _is_boundary(start, oob):
        return [0, 0, 0]
    best = {start: (0, 0, 0)}
    heap = [(0, 0, 0, start)]
    while heap:
        fa, sm, ln, c = heapq.heappop(heap)
        if best.get(c) != (fa, sm, ln):
            continue
        if c != start and _is_boundary(c, oob):
            return [fa, sm, ln]
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if oob(n) or n in burning:
                continue
            adj = any((n[0] + px, n[1] + py) in burning for px, py in _N4)
            key = (fa + (1 if adj else 0), sm + (1 if n in smoky else 0), ln + 1)
            if n not in best or key < best[n]:
                best[n] = key
                heapq.heappush(heap, (key[0], key[1], key[2], n))
    return None


def _greedy_tier(cell, target, chosen, burning, smoky):
    """The tier _move_toward reports for `chosen` (exact: the first clean-ish pool holding it, else 4)."""
    if chosen is None:
        return None
    before = abs(cell[0] - target[0]) + abs(cell[1] - target[1])
    after = abs(chosen[0] - target[0]) + abs(chosen[1] - target[1])
    adj = any((chosen[0] + ox, chosen[1] + oy) in burning for ox, oy in _N4)
    if not adj and chosen not in smoky:
        return 1 if after < before else 2 if after == before else 3
    return 4


def _safe_hops(src, x_size, y_size, unclean, t_grid):
    """The instrument's own time-expanded clean BFS (8.2), for Z4's independent recomputation."""
    def inb(c):
        return 0 <= c[0] < x_size and 0 <= c[1] < y_size

    def tstar(c):
        best = float(t_grid[c[0], c[1]])
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if inb(n):
                best = min(best, float(t_grid[n[0], n[1]]))
        return best

    hops = {src: 0}
    queue = deque([src])
    while queue:
        c = queue.popleft()
        k = hops[c] + 1
        for ox, oy in _N4:
            n = (c[0] + ox, c[1] + oy)
            if n in hops or not inb(n) or n in unclean:
                continue
            if not tstar(n) > k:
                continue
            hops[n] = k
            queue.append(n)
    return hops


def lf_sha256(path):
    """sha256 of a file's LF-normalised bytes (every CRLF read as LF): the same value for an LF and a CRLF checkout
    (core.autocrlf = true writes CRLF on a re-checkout), as T-G4 / T-G7 and the check tool's frozen-guard load hash."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def load_u1_shadow(path=U1_SHADOW):
    """(module, sha256 of the file's LF-normalised bytes - lf_sha256): the frozen instrument-only copy of
    urgency_dispatch.py, loaded BY PATH under the module name "mvg_u1_shadow" (never as
    src_extension.planning.urgency_dispatch, never from the repo). It imports only
    src_extension.planning.fire_arrival_estimate (the repo's FAE, the estimator U1 read)."""
    sha = lf_sha256(path)
    spec = importlib.util.spec_from_file_location(U1_SHADOW_MODULE, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[U1_SHADOW_MODULE] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(U1_SHADOW_MODULE, None)
        raise
    return module, sha


def shadow_funcs(ag):
    """The Firefighter class functions the shadows call, captured BEFORE any wrap (pure methods)."""
    F = ag.Firefighter
    return {"needs": F._needs_immediate_survival_retreat, "greedy": F._greedy_choice, "survival": F._survival_choice,
            "fix_a": F._approach_path_choice, "fix_b": F._retreat_on_route_choice,
            "on_boundary": F._on_grid_boundary}


def guard_inputs(model, cfv):
    """(wind vector, x_size, y_size) exactly as the guard's 1d.2.2 reads them: cfv.wind_vector_from_direction of the
    model's wind label (U1's view, WM:3106-3110) and the grid's extents."""
    label = getattr(getattr(model, "wind", None), "wind_direction", None)
    return cfv.wind_vector_from_direction(label), int(model.grid.width), int(model.grid.height)


def frozen_guard_replica(udm, fae):
    """The INSTRUMENT's guard: a LOCAL REPLICA of the frozen function guard() of outputs/_mvg_guard_diag.py (sha256
    70eeba7877dae617... of its LF form, FROZEN_GUARD_SHA; = urgency:outputs/_mvg_guard_diag.py, Part 1d 1d.2.6). The
    inner function below is that guard() copied VERBATIM (name, signature, docstring and body; _mvg_probe_check.py
    synthetic compares its AST and its dedented source text with the frozen file's). Its free names are bound here to
    the frozen function's own dependencies, never to the model's guard code:
        arrival_time, FrontPriorityParams      = fae.arrival_time, fae.FrontPriorityParams (the repo's FAE, the
                                                 estimator the frozen file imports; byte-identical to urgency 5dba5bcb)
        unclean_cells, t_star, safe_route_hops = udm.<same names>, udm = the U1 shadow copy outputs/_mvg_u1_shadow.py
                                                 loaded by path (byte-identical to the urgency_dispatch.py the frozen
                                                 file imports them from)
    so the verdict shares no guard code with movement_paths.stranding_guard (the port the model runs; the FAE estimator
    is common by design - the frozen function reads it too). PURE (no model, grid or RNG access)."""
    arrival_time, FrontPriorityParams = fae.arrival_time, fae.FrontPriorityParams
    unclean_cells, t_star, safe_route_hops = udm.unclean_cells, udm.t_star, udm.safe_route_hops

    def guard(u, n, v, burning, smoky, wind, w, h):
        """(admit, c_n, T(v)) - G-T with `wind` (a vector) or G-W with wind None."""
        u, n, v = tuple(u), tuple(n), tuple(v)
        T = arrival_time(w, h, list(burning), wind, FrontPriorityParams())
        unclean = unclean_cells(burning, smoky, w, h)
        t_v = float(T[v[0], v[1]])
        if n in unclean or not t_star(T, n, w, h) > 1:
            return False, None, t_v
        hops = safe_route_hops(n, w, h, unclean | {u}, lambda x: t_star(T, x, w, h) - 1)
        if v not in hops:
            return False, None, t_v
        c_n = 1 + hops[v]
        return (c_n + 1) <= t_v, c_n, t_v

    return guard


def guard_shadow(gfn, u, n, v, burning, smoky, wind, x_size, y_size):
    """The INSTRUMENT's guard verdict (1d.2.2) at one decision: [admit, c_n, T_v (None = infinite), ms]. gfn is the
    frozen-function replica (frozen_guard_replica; pure)."""
    t0 = time.perf_counter()
    admit, c_n, t_v = gfn(u, n, v, burning, smoky, wind, x_size, y_size)
    ms = (time.perf_counter() - t0) * 1000.0
    return [bool(admit), None if c_n is None else int(c_n), _fin(t_v), ms]


def mp_shadow(mpfn, u, n, v, burning, smoky, wind, x_size, y_size):
    """The CROSS-CHECK at one decision: [admit, c_n, T_v (None = infinite)] of the repo function the model calls,
    movement_paths.stranding_guard (pure), on the instrument's arguments - normalised exactly as guard_shadow's."""
    admit, c_n, t_v = mpfn(u, n, v, burning, smoky, wind, x_size, y_size)
    return [bool(admit), None if c_n is None else int(c_n), _fin(t_v)]


def writes_of(unit):
    """The unit's _idle_retreat_* state as [origin, steps, stalled, last_cell] (JSON form), read with the model's own
    defaults (getattr ..., None / 0 / False / None)."""
    origin = getattr(unit, "_idle_retreat_origin", None)
    last = getattr(unit, "_idle_retreat_last_cell", None)
    return [_jc(origin), int(getattr(unit, "_idle_retreat_steps", 0) or 0),
            bool(getattr(unit, "_idle_retreat_stalled", False)), _jc(last)]


def survival_writes(unit, ag):
    """PURE replica of Firefighter._survival_move's _idle_retreat_* WRITES (Zg-2 for (b), 1d.8 (5)): returns
    (writes, cell) - the [origin, steps, stalled, last_cell] state today's _survival_move would leave, and the cell it
    would step to (None = it would not move; for an assigned unit its _assigned_one_step_retreat counts as a move).

    HOW IT IS PURE: the unit's four _idle_retreat_* values are COPIED into a local dict `st`, and _survival_move's
    control flow (agents.py, the method and its _revalidate_idle_retreat_stall / _assigned_one_step_retreat callees) is
    re-run against `st` - every write of the method becomes a write to `st`; every move becomes the returned cell. The
    only model calls are the unit's READ helpers (_fire_cells, _cell_is_ideal_idle_standoff, _retreat_candidates,
    _pick_improving_retreat, _min_fire_distance, _firefighter_cell_risk, _cell_meets_required_idle_safety,
    _neighbor_cells, _cell_contains_active_fire, _cell_adjacent_to_fire, _cell_has_active_smoke), none of which moves
    or writes. The post-move standoff tests read only Fire agents, which the unit's own move does not change, so they
    are evaluated on the destination before any move. It is checked (1) by the in-run purity guard around every shadow
    (unit __dict__, model attributes, RNG states), (2) by _mvg_probe_check.py synthetic (a deep snapshot of every agent,
    the model to depth 3, the grid and the RNGs around the shadow on hand-built boards, with positive controls), and
    (3) against the model itself on every advance where today's _survival_move ran (d["mvg"]["replica"])."""
    st = {"origin": getattr(unit, "_idle_retreat_origin", None),
          "steps": getattr(unit, "_idle_retreat_steps", 0),
          "stalled": getattr(unit, "_idle_retreat_stalled", False),
          "last_cell": getattr(unit, "_idle_retreat_last_cell", None)}

    def out(cell):
        return [_jc(st["origin"]), int(st["steps"] or 0), bool(st["stalled"]), _jc(st["last_cell"])], _cell(cell)

    if unit.pos is None:
        return out(None)
    cell = (int(unit.pos[0]), int(unit.pos[1]))
    fire_cells = unit._fire_cells()
    max_cells = ag.IDLE_RETREAT_MAX_CELLS
    has_target = bool(unit.target_pos)

    def reset():
        st.update(origin=None, steps=0, stalled=False, last_cell=None)

    def one_step():
        # _assigned_one_step_retreat's destination (it moves, and returns True, iff this is not None)
        best = None
        best_score = -1
        for ncell in unit._neighbor_cells():
            if unit._cell_contains_active_fire(ncell):
                continue
            if unit._cell_adjacent_to_fire(ncell):
                continue
            if unit._cell_has_active_smoke(ncell):
                continue
            score = unit._min_fire_distance(ncell, fire_cells)
            if score > best_score:
                best_score = score
                best = ncell
        return best if best is not None and best != cell else None

    def key(c):
        return (int(c["dist"]), -int(c["risk"]))

    if unit._cell_is_ideal_idle_standoff(cell, fire_cells):
        reset()
        return out(None)
    origin = st["origin"]
    if origin is None or (not has_target and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) > max_cells):
        st.update(origin=cell, steps=0, stalled=False, last_cell=None)
        origin = cell
    if bool(st["stalled"]):
        if has_target:
            return out(one_step())
        # _revalidate_idle_retreat_stall
        current_dist = unit._min_fire_distance(cell, fire_cells)
        current_risk = unit._firefighter_cell_risk(cell)
        chosen = unit._pick_improving_retreat(
            unit._retreat_candidates(cell, origin, st["last_cell"], fire_cells, current_dist), current_dist,
            current_risk)
        if chosen is None:
            return out(None)
        steps = int(st["steps"] or 0)
        st.update(last_cell=cell, steps=steps + 1, stalled=False)
        return out(chosen["cell"])
    steps = int(st["steps"] or 0)
    at_cap = steps >= max_cells
    current_dist = unit._min_fire_distance(cell, fire_cells)
    current_risk = unit._firefighter_cell_risk(cell)
    candidates = unit._retreat_candidates(cell, origin, st["last_cell"], fire_cells, current_dist)
    if not candidates:
        if has_target:
            step = one_step()
            if step is not None:
                return out(step)
        st["stalled"] = True
        return out(None)
    chosen = None
    if not at_cap:
        chosen = unit._pick_improving_retreat(candidates, current_dist, current_risk)
        if chosen is None:
            chosen = max(candidates, key=key)
            if not has_target:
                st["stalled"] = True
    else:
        required = [c for c in candidates if c["required"]]
        if required:
            chosen = max(required, key=key)
            if not has_target:
                reset()
        else:
            chosen = max(candidates, key=key)
            if not has_target:
                st["stalled"] = True
    if chosen is None:
        if has_target:
            step = one_step()
            if step is not None:
                return out(step)
        st["stalled"] = True
        return out(None)
    target = chosen["cell"]
    if target == cell:
        if has_target:
            step = one_step()
            if step is not None:
                return out(step)
        st["stalled"] = True
        return out(None)
    st["last_cell"] = cell
    st["steps"] = steps + 1
    if unit._cell_is_ideal_idle_standoff(target, fire_cells):
        reset()
    elif unit._cell_meets_required_idle_safety(target, fire_cells) and (
            (at_cap or st["stalled"]) and not has_target):
        reset()
    return out(target)


def mv_shadow(unit, model, ag, fn, gfn=None, cfv=None, mpfn=None):
    """PURE pre-advance shadow for one unit (after its target refresh). None = no row (idle / off-grid / dead).
    v2's shadow without fix (c), plus, at every decision where fix (a) or (b) would act, the instrument's guard verdict
    (gfn = frozen_guard_replica: S["ga"] / S["gb"] = [admit, c, T_v, ms], None where the fix would not act, gfn is
    None or it raised) and the cross-check of the repo function (mpfn = movement_paths.stranding_guard: S["ga_mp"] /
    S["gb_mp"] = [admit, c, T_v], None likewise), and on every survival step the survival_writes replica (S["sv"] =
    {"pre", "pred", "cell"}). S["gerr"] = the list of guard exceptions (None: none)."""
    pos = getattr(unit, "pos", None)
    if pos is None or getattr(unit, "dead", False):
        return None
    exiting = bool(getattr(unit, "exiting", False))
    target = getattr(unit, "target_pos", None)
    if exiting:
        leg = "carry"
    elif target:
        leg = "approach"
    else:
        return None
    cell = _cell(pos)
    grid = model.grid
    oob = grid.out_of_bounds
    burning, smoky = ag.fire_board_sets(model)
    S = {"leg": leg, "pre": cell, "burning": burning, "smoky": smoky, "digest": _digest(burning, smoky),
         "cls_pre": _cls(cell, burning, smoky), "fd_pre": _mfd(cell, burning), "kind": None, "target": None,
         "trig": None, "zrb": None, "today": None, "fa": None, "fb": None, "fbB": None, "fc": None, "acted": "",
         "dc": None, "dcx": None, "df": None, "dm": None, "dr": None, "gesc": None, "c1_pre": None,
         "ga": None, "gb": None, "ga_mp": None, "gb_mp": None, "sv": None, "gerr": None}
    unclean = _unclean(burning, smoky, oob)
    # dcb (v2, R3 D-16): clean distance to the boundary on EVERY row, the unit's own cell exempt
    S["dcb"] = _dist_boundary(cell, lambda c: c not in unclean, oob)
    if leg == "approach":
        tgt = _cell(target)
        S["target"] = tgt
        dm = abs(cell[0] - tgt[0]) + abs(cell[1] - tgt[1])
        # advance() tests the survival trigger BEFORE the pickup (a unit on its victim's unclean cell retreats)
        trig = bool(fn["needs"](unit))
        if cell == tgt and not trig:
            S.update(kind="pickup", trig=False, dm=0, df=0, dr=0)
            return S
        field, has_exit = _clean_field(tgt, unclean, oob)
        dc = field.get(cell)
        if dc is None:
            near = [field[(cell[0] + ox, cell[1] + oy)] for ox, oy in _N4 if (cell[0] + ox, cell[1] + oy) in field]
            dcx = min(near) + 1 if near else None
        else:
            dcx = dc
        df = _at(_bfs(tgt, grid, burning), cell, burning)
        nbrs = [(cell[0] + ox, cell[1] + oy) for ox, oy in _N4 if not oob((cell[0] + ox, cell[1] + oy))]
        zrb = (not any(n not in burning for n in nbrs)) or df is None
        g = fn["greedy"](unit, tgt, burning, smoky)
        g = _cell(g)
        gt = _greedy_tier(cell, tgt, g, burning, smoky)
        if trig:
            r = _cell(fn["survival"](unit))
            b = _cell(fn["fix_b"](unit))
            B = None
            if field and has_exit:
                fin = [n for n in nbrs if n not in unclean and n in field]
                if fin:
                    low = min(field[n] for n in fin)
                    B = sorted(n for n in fin if field[n] == low)
                else:
                    B = []
            today = ["survival", r, None, False] if r is not None else ["fallback", g, gt, bool(zrb)]
            S.update(kind="retreat", fb=b, fbB=B, acted="b" if b is not None else "")
            pred, pred_cell = survival_writes(unit, ag)
            S["sv"] = {"pre": writes_of(unit), "pred": pred, "cell": _jc(pred_cell)}
        else:
            a = _cell(fn["fix_a"](unit))
            today = ["greedy", g, gt, bool(zrb)]
            S.update(kind="approach", fa=a, acted="a" if (a is not None and a != g) else "")
        S.update(trig=trig, zrb=bool(zrb), today=today, dc=dc, dcx=dcx, df=df, dm=dm, gesc=bool(has_exit),
                 dr=dcx if dcx is not None else df if df is not None else dm)
        if (gfn is not None or mpfn is not None) and S["acted"]:
            f = S["acted"]
            n = S["fa"] if f == "a" else S["fb"]
            errs = []
            try:
                wind, xs, ys = guard_inputs(model, cfv)
            except Exception as exc:  # recorded as a guard error; both verdicts stay None
                errs.append(("guard_inputs: %r" % (exc,))[:300])
            else:
                if gfn is not None:
                    try:
                        S["g" + f] = guard_shadow(gfn, cell, n, tgt, burning, smoky, wind, xs, ys)
                    except Exception as exc:  # recorded as a guard error; the verdict stays None
                        errs.append(("guard_shadow (frozen replica): %r" % (exc,))[:300])
                if mpfn is not None:
                    try:
                        S["g" + f + "_mp"] = mp_shadow(mpfn, cell, n, tgt, burning, smoky, wind, xs, ys)
                    except Exception as exc:  # recorded as a guard error; the cross-check stays None
                        errs.append(("mp_shadow (movement_paths.stranding_guard): %r" % (exc,))[:300])
            S["gerr"] = errs or None
        return S
    # carry (no fix (c) in this round: today's carry step only)
    et = getattr(unit, "exit_target", None)
    S["target"] = _cell(et)
    dm = min(cell[0], int(grid.width) - 1 - cell[0], cell[1], int(grid.height) - 1 - cell[1])
    S["dm"] = dm
    if et is None:
        S.update(kind="noexit", dr=dm)
        return S
    mode = ag.ff_exit_leg_mode()
    if cell == S["target"] or (mode != 0 and _is_boundary(cell, oob)):
        S.update(kind="complete", dr=0)
        return S
    dc = S["dcb"]   # the same call: _dist_boundary(cell, clean, oob), start exempt
    df = _dist_boundary(cell, lambda c: c not in burning, oob)

    def greedy_today():
        g = _cell(fn["greedy"](unit, S["target"], burning, smoky))
        if g is None:
            if ag.ff_exit_leg_hold():
                return ["hold", cell, 6, False]
            return ["raise", cell, None, True]
        return ["greedy", g, _greedy_tier(cell, S["target"], g, burning, smoky), False]

    if mode == 2:
        first = ag.exit_leg_first_step(cell, lambda c: c not in unclean, lambda c: fn["on_boundary"](unit, c), oob)
        today = ["path", _cell(first), 5, False] if first is not None else greedy_today()
    else:
        today = greedy_today()
    S.update(kind="carry", today=today, dc=dc, dcx=dc, df=df, gesc=dc is not None,
             c1_pre=_c1_cost(cell, burning, smoky, oob), dr=dc if dc is not None else df if df is not None else dm)
    return S


def waiting_replica(model, managed, markers):
    """INSTRUMENT-SIDE replica of the urgency round's WildFireModel._urgency_waiting (urgency:wildfire_model.py at
    5dba5bcb; = today's kick loop's three predicates, in today's index order): W."""
    out = []
    for vid, state in managed.items():
        marker = markers.get(vid)
        if not model._victim_needs_rescue(vid, marker):
            continue
        confirmed = bool(getattr(state, "confirmed", False) if state is not None else False)
        ms = str(getattr(marker, "status", "") or "").strip().lower() if marker is not None else ""
        if not confirmed and ms != "confirmed":
            continue
        if model._find_active_firefighter_for_victim(vid, marker):
            continue
        out.append((vid, marker))
    return out


def view_replica(model, waiting, unit, ag, cfv):
    """INSTRUMENT-SIDE replica of the urgency round's WildFireModel._urgency_dispatch_view (urgency:wildfire_model.py
    at 5dba5bcb, its 11.1 reads made AFTER W is built): each waiting victim's live cell, the free unit's cell, the true
    burning and active-smoke sets (agents.fire_board_sets), the wind vector (cfv.wind_vector_from_direction of the
    model's wind label) and the grid's extents."""
    burning, smoky = ag.fire_board_sets(model)
    cells = []
    for vid, marker in waiting:
        pos = getattr(marker, "pos", None)
        if pos is None:
            continue
        cells.append((vid, (int(pos[0]), int(pos[1]))))
    wind_label = getattr(getattr(model, "wind", None), "wind_direction", None)
    return {
        "waiting": cells,
        "unit_cell": (int(unit.pos[0]), int(unit.pos[1])),
        "burning": burning,
        "smoky": smoky,
        "wind": cfv.wind_vector_from_direction(wind_label),
        "x_size": int(model.grid.width),
        "y_size": int(model.grid.height),
    }


def decision_action(decision):
    """The action of a select_rescue_assignment result, parsed exactly as RescueExecutor.apply_physical_pairing_decision
    parses it: a dict's "action" (the planner's {"action": "none", ...}), else a RescueDecision's rescue_action;
    stripped and lower-cased."""
    if isinstance(decision, dict):
        return str(decision.get("action", "") or "").strip().lower()
    return str(getattr(decision, "rescue_action", "") or "").strip().lower()


def planner_accepts(model, select_fn, waiting):
    """{vid: bool} for every (vid, marker) of W: whether the planner call _dispatch_firefighter_to_victim makes for
    her - select_fn(model.get_rescue_operational_snapshot(), "initial", victim_id=str(vid or "")) - yields "assign".
    One fresh snapshot per victim, as the model takes one per call (before any bind the state is the same). PURE: the
    snapshot is the model's read-only planner view and select_rescue_assignment a pure function of it."""
    out = {}
    for vid, _marker in waiting:
        snapshot = model.get_rescue_operational_snapshot()
        out[str(vid)] = decision_action(select_fn(snapshot, "initial", victim_id=str(vid or ""))) == "assign"
    return out


def first_accepted(order, acc):
    """The first vid of `order` the planner accepts (acc True); None when there is none, or order / acc is None."""
    if order is None or acc is None:
        return None
    return next((v for v in order if acc.get(v)), None)


def kick_flags(K):
    """The v2 shadow flags of a kick record (pure, set in K) from its index / u1 / acc / qualifies:
    index_wb / u1_wb = the victim each order WOULD BIND (its first accepted victim); div_shadow (16.5's U1-divergent,
    in shadow) = qualifies and u1_wb != index_wb; div_shadow_head = v1's head-based value (u1[0] != index[0])."""
    K["index_wb"] = first_accepted(K.get("index"), K.get("acc"))
    K["u1_wb"] = first_accepted(K.get("u1"), K.get("acc"))
    K["div_shadow"] = bool(K.get("qualifies") and K["u1_wb"] != K["index_wb"])
    K["div_shadow_head"] = bool(K.get("qualifies") and K.get("u1") and K.get("index")
                                and K["u1"][0] != K["index"][0])
    return K


def bind_flags(K, bound):
    """The v2 bind flags of a kick record (pure, set in K): divergent = qualifies and the victim the kick actually
    bound first (None if none) != index_wb; divergent_head = v1's value (bound[0][0] != index[0])."""
    first = bound[0][0] if bound else None
    K["divergent"] = bool(K.get("qualifies") and first != K.get("index_wb"))
    K["divergent_head"] = bool(K.get("qualifies") and bound and K.get("index") and bound[0][0] != K["index"][0])
    return K


def kick_shadow(model, ag, ud, fae, order_fn, select_fn=None, cfv=None):
    """PURE kick record: W (today's predicates, waiting_replica), F, qualifies (U1's exact predicate), the U1 order and
    per-victim [T, c, promotable] from a pure urgency_order call of the frozen U1 copy (whenever |F| = 1, |W| >= 1 and
    a cell burns), with the planner's acceptance of every W victim (acc, v2; when select_fn is given) and the flags of
    kick_flags, the non-burning d from each waiting victim to each free unit, and at a qualifying kick Z4's independent
    recomputation. The view is view_replica (U1 is not in the model)."""
    K = {"W": None, "F": None, "index": None, "qualifies": False, "u1": None, "rec": {}, "d": {}, "ms": None,
         "div_shadow": False, "nB": None, "z4": None, "z4_ok": None, "acc": None, "index_wb": None, "u1_wb": None,
         "div_shadow_head": False}
    managed = getattr(model, "managed_victims", None)
    markers = getattr(model, "victim_marker_agents", None)
    if not isinstance(managed, dict) or not isinstance(markers, dict):
        return K
    waiting = waiting_replica(model, managed, markers)
    units = getattr(model, "firefighter_marker_agents", None) or {}
    free = [(str(fid), u) for fid, u in units.items() if model._firefighter_available_for_dispatch(u)]
    K["W"] = [[str(vid), _jc(_cell(getattr(mk, "pos", None)))] for vid, mk in waiting]
    K["F"] = [[fid, _jc(_cell(getattr(u, "pos", None)))] for fid, u in free]
    K["index"] = [str(vid) for vid, _mk in waiting]
    view = None
    if len(free) == 1 and len(waiting) >= 1:
        view = view_replica(model, waiting, free[0][1], ag, cfv)
    if view is not None and len(waiting) >= 2:
        K["qualifies"] = bool(ud.qualifies(len(view["waiting"]), len(free), bool(view["burning"]))
                              and len(view["waiting"]) == len(waiting))
    burning = view["burning"] if view is not None else ag.fire_board_sets(model)[0]
    K["nB"] = len(burning)
    if view is not None and view["burning"] and view["waiting"]:
        t0 = time.perf_counter()
        ordered, records = order_fn(view["waiting"], view["unit_cell"], view["burning"], view["smoky"],
                                    view["wind"], view["x_size"], view["y_size"])
        K["ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
        K["u1"] = [str(v) for v in ordered]
        K["rec"] = {str(v): [_fin(r["T"]), r["c"], bool(r["promotable"])] for v, r in records.items()}
        if select_fn is not None:
            K["acc"] = planner_accepts(model, select_fn, waiting)
    kick_flags(K)
    grid = model.grid
    for vid, mk in waiting:
        if getattr(mk, "pos", None) is None:
            continue
        dmap = _bfs(mk.pos, grid, burning)
        K["d"][str(vid)] = {fid: _at(dmap, u.pos, burning) for fid, u in free if getattr(u, "pos", None) is not None}
    if K["qualifies"]:
        xs, ys = int(view["x_size"]), int(view["y_size"])
        t_grid = fae.arrival_time(xs, ys, list(view["burning"]), view["wind"], fae.FrontPriorityParams())
        oob = grid.out_of_bounds
        unclean = _unclean(set(view["burning"]), set(view["smoky"]), oob)
        hops = _safe_hops(tuple(view["unit_cell"]), xs, ys, unclean, t_grid)
        z4 = {}
        for vid, vc in view["waiting"]:
            vc = (int(vc[0]), int(vc[1]))
            t_v = float(t_grid[vc[0], vc[1]])
            c = None if vc in unclean else hops.get(vc)
            z4[str(vid)] = [_fin(t_v), c, bool(c is not None and c + 1 <= t_v)]
        K["z4"] = z4
        K["z4_ok"] = all(K["rec"].get(v) == z for v, z in z4.items())
    return K


def rng_states(ag, model):
    """A cheap fingerprint of every RNG a shadow could touch (agents.random, model.random, numpy's global)."""
    out = []
    for r in (getattr(ag, "random", None), getattr(model, "random", None)):
        try:
            out.append(r.getstate())
        except Exception:
            out.append(None)
    try:
        import numpy as np
        st = np.random.get_state()
        out.append((st[0], st[1].tobytes(), st[2], st[3], st[4]))
    except Exception:
        out.append(None)
    return out


def dict_changed(before, after):
    """Keys whose value is no longer the same object (or equal value) - a shallow purity check."""
    bad = sorted(set(before) ^ set(after))
    for k, v in before.items():
        if k not in after:
            continue
        w = after[k]
        if w is v:
            continue
        try:
            if bool(w == v):
                continue
        except Exception:
            pass
        bad.append(k)
    return bad


# ============================================================================== dq: pure helpers (12.1, 10.3, 11.2)
def load_r1_shadow(path=R1_SHADOW):
    """(module, sha256 of the file's LF-normalised bytes): the FROZEN copy of round 1's joint_dispatch.py
    (git show cc8d653c:src_extension/planning/joint_dispatch.py), loaded BY PATH under the module name "dq_r1_shadow"
    (never from the repo; it imports only the standard library)."""
    sha = lf_sha256(path)
    spec = importlib.util.spec_from_file_location(R1_SHADOW_MODULE, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[R1_SHADOW_MODULE] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(R1_SHADOW_MODULE, None)
        raise
    return module, sha


_TRAILING_INT = re.compile(r"(\d+)$")


def id_index(identifier):
    """The integer tie-break key (the instrument's own copy of joint_dispatch.id_index's rule): the trailing integer
    of an id, then the id; an id without one sorts after every numbered id."""
    text = str(identifier)
    match = _TRAILING_INT.search(text)
    return (int(match.group(1)) if match else 10**9, text)


def vindex(v):
    """Round 1's legacy victim order (_dp_probe.legacy_pairs): the integer after the last '_', then the id."""
    tail = str(v).rsplit("_", 1)[-1]
    return (int(tail) if tail.isdigit() else 10**9, str(v))


def legacy_pairs_data(victims, vcell, free, ucell):
    """11.2's counterfactual ("today's choice") on plain data: the victims (W and W_L) in victim-index order (vindex),
    each to the Manhattan-nearest UNCHOSEN free unit, any route (closed included), ties to the smaller id STRING -
    select_rescue_assignment's `dist < best_dist or (dist == best_dist and ff_s < str(best_ff))`. No replacement of any
    kind. Returns [[victim, unit], ...] in victim order."""
    used, pairs = set(), []
    for vid in sorted(victims, key=vindex):
        vc = vcell[vid]
        best = None
        for uid in free:
            if uid in used:
                continue
            uc = ucell[uid]
            dist = abs(int(uc[0]) - int(vc[0])) + abs(int(uc[1]) - int(vc[1]))
            if best is None or dist < best[0] or (dist == best[0] and uid < best[1]):
                best = (dist, uid)
        if best is not None:
            used.add(best[1])
            pairs.append([vid, best[1]])
    return pairs


def legacy_pairs(view):
    """legacy_pairs_data on J's own snapshot (WildFireModel._dispatch_view): W + W_L, the free units' cells."""
    units = view["units"]
    victims = list(view["waiting"]) + list(view["latched"])
    vcell = {v: view["victims"][v]["cell"] for v in victims}
    ucell = {u: (int(units[u].pos[0]), int(units[u].pos[1])) for u in view["free"]}
    return legacy_pairs_data(victims, vcell, list(view["free"]), ucell)


def fire_reads(model, ag):
    """The instrument's OWN read of the board (never the model's helpers): burning = the Fire agents with a position
    whose is_burning() is truthy; smoky = the Fire agents with a position whose smoke.is_smoke_active() is truthy."""
    burning, smoky = set(), set()
    for a in model.schedule.agents:
        if type(a) is not ag.Fire:
            continue
        pos = getattr(a, "pos", None)
        if pos is None:
            continue
        cell = (int(pos[0]), int(pos[1]))
        if a.is_burning():
            burning.add(cell)
        smoke = getattr(a, "smoke", None)
        if smoke is not None and smoke.is_smoke_active():
            smoky.add(cell)
    return burning, smoky


def inst_unclean(burning, smoky, w, h):
    """The instrument's own unclean predicate (2.8 R-1): burning, active-smoke, or a 4-neighbour of a burning cell (in
    bounds)."""
    out = set(burning) | set(smoky)
    for x, y in burning:
        for ox, oy in _N4:
            nx, ny = x + ox, y + oy
            if 0 <= nx < w and 0 <= ny < h:
                out.add((nx, ny))
    return out


def inst_map(source, w, h, blocked):
    """The instrument's own 4-connected BFS (a flat list, index x * h + y, -1 = not reached) from `source` over in-bounds
    cells not in `blocked`; the source itself is never tested (the destination exemption of the units' route test)."""
    dist = [-1] * (w * h)
    sx, sy = int(source[0]), int(source[1])
    if not (0 <= sx < w and 0 <= sy < h):
        return dist
    dist[sx * h + sy] = 0
    queue = deque([(sx, sy)])
    while queue:
        x, y = queue.popleft()
        nd = dist[x * h + y] + 1
        for ox, oy in _N4:
            nx, ny = x + ox, y + oy
            if 0 <= nx < w and 0 <= ny < h:
                i = nx * h + ny
                if dist[i] == -1 and (nx, ny) not in blocked:
                    dist[i] = nd
                    queue.append((nx, ny))
    return dist


def inst_at(dist, w, h, cell, blocked):
    """A map's value at a unit's cell with the UNIT-CELL EXEMPTION: a reached cell reads its distance; an unreached cell
    that is not blocked has no route (None); a blocked cell reads 1 + its best reached 4-neighbour (None if none).
    dist None (no map: the victim's cell is unclean for a clean map) reads None."""
    if dist is None or cell is None:
        return None
    x, y = int(cell[0]), int(cell[1])
    if not (0 <= x < w and 0 <= y < h):
        return None
    v = dist[x * h + y]
    if v >= 0:
        return v
    if (x, y) not in blocked:
        return None
    best = None
    for ox, oy in _N4:
        nx, ny = x + ox, y + oy
        if 0 <= nx < w and 0 <= ny < h:
            nv = dist[nx * h + ny]
            if nv >= 0 and (best is None or nv < best):
                best = nv
    return None if best is None else best + 1


def grid_g(a, b):
    """G (5.2): the Manhattan distance - the instrument's own copy."""
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))


def _fmin(values):
    finite = [int(v) for v in values if v is not None]
    return min(finite) if finite else None


def hist_progress(H, k, k_l, route_open, d_now, c_now, d_hist, c_hist, cell, frozen):
    """The instrument's OWN implementation of R-1's history rule with C2's counts (2.8, 5.2) - Z-R1's reference.
    Returns (H', k', k_L', closed', progressed) with progressed None on a closed route.
    CLOSED: H grows by the cell, k unchanged, k_L + 1 unless FROZEN. OPEN: k_L = 0; PROGRESS iff d = 0, or d beats the
    least FINITE d over H, or c (finite) beats the least FINITE c over H - a metric with no finite value over H is not
    compared (joint_dispatch.progress_step's amendment A2 reading); progress -> H = [cell], k = 0; else H grows and
    k + 1 unless FROZEN. H is a sorted list of unique [x, y]."""
    cell = (int(cell[0]), int(cell[1]))
    grown = sorted({(int(c[0]), int(c[1])) for c in H} | {cell})
    if not route_open:
        return [list(c) for c in grown], int(k), int(k_l) + (0 if frozen else 1), True, None
    bd, bc = _fmin(d_hist), _fmin(c_hist)
    prog = d_now is not None and (int(d_now) == 0 or (bd is not None and int(d_now) < bd)
                                  or (c_now is not None and bc is not None and int(c_now) < bc))
    if prog:
        return [list(cell)], 0, 0, False, True
    return [list(c) for c in grown], int(k) + (0 if frozen else 1), 0, False, False


def literal_progress(route_open, d_now, c_now, d_hist, c_hist):
    """2.8's LITERAL text (a minimum over an empty set is infinite): the progress verdict it gives (reported only)."""
    if not route_open:
        return None
    inf = float("inf")
    bd = min([int(v) for v in d_hist if v is not None], default=inf)
    bc = min([int(v) for v in c_hist if v is not None], default=inf)
    return bool(d_now is not None and (int(d_now) == 0 or int(d_now) < bd or (c_now is not None and int(c_now) < bc)))


def persist_generic(prev, spare_d, delta, margin, fresh=None):
    """The margin persistence counters (6.5): spare B's count = previous + 1 where d(B) + M <= delta, else dropped (an
    absent spare drops too); fresh (a {unit: bool} map) restricts the counting to fresh pairs (round 1). The instrument's
    own copy. Returns {unit: count}."""
    out = {}
    for unit, d in spare_d.items():
        if d is None or delta is None:
            continue
        if fresh is not None and not fresh.get(unit, False):
            continue
        if int(d) + int(margin) <= int(delta):
            out[unit] = int(prev.get(unit, 0) or 0) + 1
    return out


FILL_KEYS = {
    # (n, n_clean, total, worst, reused, ids) -> the key; lower is better
    "cor": lambda n, nc, tot, wst, ru, ids: (-n, -nc, tot, wst, ru, ids),     # round 2 (C1 + R-2 (b)): L1 L1b L2' L3' L4' L5
    "c1rev": lambda n, nc, tot, wst, ru, ids: (-n, -nc, ru, tot, wst, ids),   # C1 reverted: the ledger as L2, after L1b
    "r2rev": lambda n, nc, tot, wst, ru, ids: (-n, tot, wst, ru, ids),        # R-2 reverted: no L1b
    "r1": lambda n, nc, tot, wst, ru, ids: (-n, ru, tot, wst, ids),           # round 1: L1 L2 (re-used) L3 L4 L5
}


def fill_generic(units, victims, dist, ledger, clean, capped=(), key="cor"):
    """The fill by exhaustive enumeration under one of FILL_KEYS (the instrument's own solver; key "cor" reproduces
    joint_dispatch.solve_fill, key "r1" round 1's - checked by _dq_probe_check.py selftest). dist[(u, v)] = the route
    metric (None / missing = no pair), ledger[(u, v)] = b, clean[(u, v)] = a clean approach; a capped victim refuses a
    pair with b >= 2. Returns [(victim, unit, distance, reused, clean)] in victim order."""
    unit_list = sorted({str(u) for u in units}, key=id_index)
    victim_list = sorted({str(v) for v in victims}, key=id_index)
    capped_set = {str(v) for v in capped}
    n_configs = sum(comb(len(unit_list), k) * perm(len(victim_list), k)
                    for k in range(min(len(unit_list), len(victim_list)) + 1))
    if n_configs > FP_MAX_CONFIGURATIONS:
        raise ValueError("fill_generic: %d configurations" % n_configs)
    keyf = FILL_KEYS[key]
    options = {}
    for unit in unit_list:
        row = []
        for victim in victim_list:
            d = dist.get((unit, victim))
            if d is None:
                continue
            b = int(ledger.get((unit, victim), 0) or 0)
            if victim in capped_set and b >= 2:
                continue
            row.append((victim, int(d), b >= 1, bool(clean.get((unit, victim), False))))
        options[unit] = row
    best = [None, []]

    def score(pairs):
        n = len(pairs)
        nc = sum(1 for p in pairs if p[4])
        tot = sum(p[2] for p in pairs)
        wst = max((p[2] for p in pairs), default=0)
        ru = sum(1 for p in pairs if p[3])
        ids = sorted((id_index(p[0]), id_index(p[1])) for p in pairs)
        return keyf(n, nc, tot, wst, ru, ids)

    def walk(i, used, chosen):
        if i == len(unit_list):
            k = score(chosen)
            if best[0] is None or k < best[0]:
                best[0] = k
                best[1] = list(chosen)
            return
        unit = unit_list[i]
        walk(i + 1, used, chosen)
        for victim, d, reused, is_clean in options[unit]:
            if victim in used:
                continue
            chosen.append((victim, unit, d, reused, is_clean))
            walk(i + 1, used | {victim}, chosen)
            chosen.pop()

    walk(0, frozenset(), [])
    return sorted(best[1], key=lambda p: id_index(p[0]))


def plan_generic(contests, spares, dist, ledger, clean, stall_steps, margin_persist, nearest_allowed=False,
                 margin_clean=True):
    """Step 3's replacements (4.3, 5.2, R-2 (a)) - the instrument's own planner; with the defaults it reproduces
    joint_dispatch.plan_replacements_detail (checked by the selftest). contests: dicts {victim, incumbent, delta, open,
    k, k_closed, persist, latched}; count = k if open else k_closed. nearest_allowed: the ledger filters the qualifying
    spares BEFORE the least distance is taken (C1 reverted; no Barred record). margin_clean False: a margin challenger
    needs no clean approach (R-2 reverted; a stall challenger keeps it). Returns (replacements [[victim, old, new,
    cause, distance, latched]], barred [[victim, incumbent, cause, distance, [units]]])."""
    spare_list = sorted({str(s) for s in spares}, key=id_index)
    used = set()
    out, barred = [], []

    def count(c):
        return int(c["k"]) if c["open"] else int(c["k_closed"])

    def allowed(u, c):
        b = int(ledger.get((u, c["victim"]), 0) or 0)
        return b <= 1 if c["latched"] else b == 0

    def qualifying(c, stall):
        found = []
        for u in spare_list:
            if u in used:
                continue
            if (stall or margin_clean) and not clean.get((u, c["victim"]), False):
                continue
            d = dist.get((u, c["victim"]))
            if d is None:
                continue
            if stall:
                if not int(d) < int(c["delta"]) + count(c):
                    continue
            elif int(c["persist"].get(u, 0) or 0) < margin_persist:
                continue
            if nearest_allowed and not allowed(u, c):
                continue
            found.append((int(d), u))
        return found

    def nearest(c, stall):
        q = qualifying(c, stall)
        return min(d for d, _ in q) if q else None

    def decide(c, stall):
        q = qualifying(c, stall)
        if not q:
            return
        least = min(d for d, _ in q)
        ties = sorted((u for d, u in q if d == least), key=id_index)
        ok = [u for u in ties if allowed(u, c)]
        cause = "stall" if stall else "margin"
        if not ok:
            barred.append([c["victim"], c["incumbent"], cause, least, list(ties)])
            return
        used.add(ok[0])
        out.append([c["victim"], c["incumbent"], ok[0], cause, least, bool(c["latched"])])

    stalled = [c for c in contests if count(c) >= stall_steps]
    margins = [c for c in contests if count(c) < stall_steps]

    def stall_order(c):
        d = nearest(c, True)
        gain = (int(c["delta"]) - d) if d is not None else -(10**9)
        return (-count(c), -gain, id_index(c["victim"]))

    for c in sorted(stalled, key=stall_order):
        decide(c, True)

    def margin_order(c):
        d = nearest(c, False)
        gain = (int(c["delta"]) - d) if d is not None else -(10**9)
        return (-gain, id_index(c["victim"]))

    for c in sorted(margins, key=margin_order):
        decide(c, False)
    return out, barred


def eshift_hybrid(st, route_open, d_now, x_now, cell, frozen):
    """The R-1-reverted progress (round 1's e-shift on d, with C2's closed-route count kept) - FOOTPRINT_DOC's rv1
    state: {best, k, d_prev, cell_prev, k_closed, closed, age, persist}. Returns a new dict."""
    s = dict(st)
    s["age"] = int(s.get("age", 0)) + 1
    cell = [int(cell[0]), int(cell[1])]
    if not route_open:
        s["k_closed"] = int(s["k_closed"]) + (0 if frozen else 1)
        s["closed"] = True
        return s
    s["k_closed"] = 0
    s["closed"] = False
    if s.get("best") is None or s.get("d_prev") is None:
        s.update(best=int(d_now), d_prev=int(d_now), cell_prev=cell)
        return s
    if x_now is None:
        return s     # round 1's 'not evaluated' frame: no count, the reference untouched
    best = int(s["best"]) + (int(x_now) - int(s["d_prev"]))
    k = int(s["k"])
    if int(d_now) == 0:
        best, k = 0, 0
    elif int(d_now) < best:
        best, k = int(d_now), 0
    elif not frozen:
        k += 1
    s.update(best=best, k=k, d_prev=int(d_now), cell_prev=cell)
    return s


def rv1_new(d, cell):
    """The rv1 state at a bind (or at a contest's first sight): reference (d, cell), counts 0."""
    return {"best": None if d is None else int(d), "k": 0, "d_prev": None if d is None else int(d),
            "cell_prev": [int(cell[0]), int(cell[1])], "k_closed": 0, "closed": d is None, "age": 0, "persist": {}}


def _ukey(key):
    u, v = key.split("|", 1)
    return u, v


def _pkey(u, v):
    return "%s|%s" % (u, v)


def _dist_get(cur, v, u, i):
    row = ((cur["inst"]["dist"].get(v) or {}).get(u))
    return None if row is None else row[i]


def _decision(pairs, barred):
    return {"pairs": sorted([list(p) for p in pairs], key=lambda p: (id_index(p[1]), p[0], id_index(p[2]))),
            "barred": sorted([list(b) for b in barred], key=lambda b: id_index(b[0]))}


def _jd_progress(jd, row):
    """A corrected joint_dispatch.Progress from its JSON row [H, k, k_L, closed, age, persist]."""
    H, k, kl, closed, age, persist = row
    return jd.Progress(history=tuple((int(c[0]), int(c[1])) for c in H), k=int(k), k_closed=int(kl),
                       closed=bool(closed), age=int(age),
                       persist=tuple(sorted(((str(u), int(n)) for u, n in persist.items()), key=lambda kv: id_index(kv[0]))))


def jd_progress_row(state):
    return [[list(c) for c in state.history], int(state.k), int(state.k_closed), bool(state.closed), int(state.age),
            dict(state.persist_map())]


def r1_progress_row(state):
    return [int(state.best), int(state.k), int(state.d_prev), [int(state.cell_prev[0]), int(state.cell_prev[1])],
            int(state.age), dict(state.persist_map())]


def _r1_progress(r1m, row):
    best, k, d_prev, cell_prev, age, persist = row
    return r1m.Progress(best=int(best), k=int(k), d_prev=int(d_prev), cell_prev=(int(cell_prev[0]), int(cell_prev[1])),
                        age=int(age),
                        persist=tuple(sorted(((str(u), int(n)) for u, n in persist.items()), key=lambda kv: id_index(kv[0]))))


def _fp_sets(cur):
    s = cur["sets"]
    reassign, post = bool(s["reassign"]), bool(s["post"])
    contests = list(s["contest"].items()) + list(s["latched_binder"].items()) if (reassign and post) else []
    return s, reassign, post, contests


def _fp_corrected(cur, jd, variant):
    """base (variant "base", joint_dispatch's own functions) and the C1 / C2 / R2 / R1 reversions (FOOTPRINT_DOC).
    Returns (decision, rv1_after or None)."""
    s, reassign, post, contests = _fp_sets(cur)
    inst = cur["inst"]
    S, M, P = inst["SMP"]
    free, W, WL = list(s["free"]), list(s["waiting"]), list(s["latched"])
    binders = s["binders"]
    ledger = {_ukey(k): int(b) for k, b in inst["ledger"].items()}
    metric = 0 if variant == "R1" else 2
    ucell = {u: (int(r[0]), int(r[1])) for u, r in inst["ucell"].items()}
    vcell = {v: (int(r[0]), int(r[1])) for v, r in inst["vcell"].items()}

    def dist_of(u, v):
        return _dist_get(cur, v, u, metric)

    def clean_of(u, v):
        return bool(_dist_get(cur, v, u, 3))

    c2 = variant == "C2"
    fill_v = (W + WL) if (c2 or not reassign) else list(W)
    capped = list(WL) if (c2 and reassign) else []
    # 1 PROGRESS (counts)
    rows = []          # [victim, incumbent, open, delta, k, k_closed, persist_prev, latched]
    rv1_after = {} if variant == "R1" else None
    for v, a in contests:
        key = _pkey(a, v)
        cell = ucell[a]
        d_now = _dist_get(cur, v, a, 0)
        is_open = d_now is not None
        frozen = not (clean_of(a, v) or any(clean_of(f, v) for f in free))
        latched = str(inst["ucell"][a][3]).strip().lower() == "route_blocked"
        if variant == "R1":
            delta = int(d_now) if is_open else grid_g(cell, vcell[v])
            prev = (cur["fp"].get("rv1_before") or {}).get(key)
            if prev is None:
                st = rv1_new(d_now, cell)
            else:
                st = eshift_hybrid(prev, is_open, d_now, (inst["hist"].get(key) or {}).get("x_rv1"), cell, frozen)
            rv1_after[key] = st
            rows.append([v, a, is_open, delta, st["k"], st["k_closed"], dict(st["persist"]), latched])
            continue
        c_now = _dist_get(cur, v, a, 1) if is_open else None
        delta = (int(c_now) if c_now is not None else int(d_now)) if is_open else grid_g(cell, vcell[v])
        prev = cur["progress_before"].get(key)
        if prev is None:
            state = jd.new_progress(cell)
        else:
            hist = (inst["hist"].get(key) or {}).get("H") or []
            state = jd.progress_step(_jd_progress(jd, prev), is_open, d_now, c_now, tuple(h[0] for h in hist),
                                     tuple(h[1] for h in hist), cell, frozen)
        if c2 and (v not in s["contest"] or not is_open):
            continue
        rows.append([v, a, is_open, delta, state.k, state.k_closed, dict(state.persist_map()), latched, state])
    # 2 FILL
    dist2 = {(u, v): dist_of(u, v) for u in free for v in fill_v}
    clean2 = {(u, v): clean_of(u, v) for u in free for v in fill_v}
    pairs = []
    if free and fill_v:
        if variant == "base":
            got = [(p.victim, p.unit, p.distance, p.reused, p.clean)
                   for p in jd.solve_fill(free, fill_v, dist2, ledger, clean=clean2)]
        else:
            key = {"C1": "c1rev", "R2": "r2rev"}.get(variant, "cor")
            got = fill_generic(free, fill_v, dist2, ledger, clean2, capped=capped, key=key)
        for v, u, _d, _r, _c in got:
            if v in capped:
                pairs.append(["latch_fill", v, u, sorted(binders.get(v) or [], key=id_index)])
            else:
                pairs.append(["fill", v, u, []])
    bound_u = {p[2] for p in pairs}
    bound_v = {p[1] for p in pairs}
    barred = []
    if not contests:
        return _decision(pairs, barred), rv1_after
    # 3 REPLACE
    spares = [u for u in free if u not in bound_u]
    plan_c = []
    for row in rows:
        v, a, is_open, delta, k, kl, prev_persist, latched = row[:8]
        spare_d = {b: dist_of(b, v) for b in spares}
        if variant == "base":
            persist = dict(jd.update_persistence(row[8], spare_d, delta, M).persist_map())
        else:
            persist = persist_generic(prev_persist, spare_d, delta, M)
        if variant == "R1":
            rv1_after[_pkey(a, v)]["persist"] = dict(persist)
        plan_c.append({"victim": v, "incumbent": a, "delta": int(delta), "open": bool(is_open), "k": int(k),
                       "k_closed": int(kl), "persist": persist, "latched": bool(latched)})
    reps = []
    if spares and plan_c:
        dist3 = {(b, c["victim"]): dist_of(b, c["victim"]) for b in spares for c in plan_c}
        clean3 = {(b, c["victim"]): clean_of(b, c["victim"]) for b in spares for c in plan_c}
        if variant == "base":
            objs = [jd.Contest(victim=c["victim"], incumbent=c["incumbent"], delta=c["delta"], route_open=c["open"],
                               k=c["k"], k_closed=c["k_closed"], persist=c["persist"], latched=c["latched"])
                    for c in plan_c]
            plan, bar = jd.plan_replacements_detail(objs, spares, dist3, ledger, clean3, stall_steps=S,
                                                    margin_persist=P)
            reps = [[r.victim, r.old_unit, r.new_unit, r.cause, r.distance, bool(r.latched)] for r in plan]
            barred = [[b.victim, b.incumbent, b.cause, b.distance, list(b.units)] for b in bar]
        else:
            reps, barred = plan_generic(plan_c, spares, dist3, ledger, clean3, S, P,
                                        nearest_allowed=(variant == "C1"), margin_clean=(variant != "R2"))
    for v, old, new, _cause, _dist, latched in reps:
        pairs.append(["latch_fill" if latched else "replace", v, new, [old]])
    # 4 SECOND FILL: released ACTIVE units x the fill victims not bound in step 2
    again = [old for v, old, new, _c, _d, latched in reps if not latched]
    still = [v for v in fill_v if v not in bound_v]
    if again and still:
        dist4 = {(u, v): dist_of(u, v) for u in again for v in still}
        clean4 = {(u, v): clean_of(u, v) for u in again for v in still}
        capped4 = [v for v in still if v in capped]
        if variant == "base":
            got = [(p.victim, p.unit, p.distance, p.reused, p.clean)
                   for p in jd.solve_fill(again, still, dist4, ledger, clean=clean4)]
        else:
            key = {"C1": "c1rev", "R2": "r2rev"}.get(variant, "cor")
            got = fill_generic(again, still, dist4, ledger, clean4, capped=capped4, key=key)
        for v, u, _d, _r, _c in got:
            if v in capped4:
                pairs.append(["latch_fill", v, u, sorted(binders.get(v) or [], key=id_index)])
            else:
                pairs.append(["second_fill", v, u, []])
    return _decision(pairs, barred), rv1_after


def _fp_r1(cur, r1m):
    """Round 1's J (the frozen dq_r1_shadow module) on the J point's recorded inputs and the r1 shadow states (
    FOOTPRINT_DOC). Returns (decision, r1_after {key: row})."""
    s, reassign, post, _contests = _fp_sets(cur)
    inst = cur["inst"]
    S, M, P = inst["SMP"]
    free, W, WL = list(s["free"]), list(s["waiting"]), list(s["latched"])
    binders = s["binders"]
    ledger = {_ukey(k): int(b) for k, b in inst["ledger"].items()}
    ucell = {u: (int(r[0]), int(r[1])) for u, r in inst["ucell"].items()}

    def d_of(u, v):
        return _dist_get(cur, v, u, 0)

    def clean_of(u, v):
        return bool(_dist_get(cur, v, u, 3))

    active = list(s["contest"].items()) if (reassign and post) else []
    r1_before = cur["fp"].get("r1_before") or {}
    r1_after = {}
    states = {}
    current_d = {}
    for v, a in active:
        key = _pkey(a, v)
        cell = ucell[a]
        d_now = d_of(a, v)
        current_d[v] = d_now
        prev = r1_before.get(key)
        if prev is None:
            if d_now is not None:
                states[key] = r1m.new_progress(d_now, cell)
                r1_after[key] = r1_progress_row(states[key])
            continue
        st = _r1_progress(r1m, prev)
        x_now = (inst["hist"].get(key) or {}).get("x_r1")
        if d_now is None or x_now is None:
            r1_after[key] = list(prev)       # not evaluated: the state untouched
            continue
        frozen = not (clean_of(a, v) or any(clean_of(f, v) for f in free))
        states[key] = r1m.progress_step(st, d_now, x_now, cell, frozen)
        r1_after[key] = r1_progress_row(states[key])
    fill_v = W + WL
    capped = list(WL) if reassign else []
    pairs = []
    if free and fill_v:
        dist = {(u, v): d_of(u, v) for u in free for v in fill_v}
        for p in r1m.solve_fill(free, fill_v, dist, ledger, capped=capped):
            if reassign and p.victim in WL:
                pairs.append(["latch_fill", p.victim, p.unit, sorted(binders.get(p.victim) or [], key=id_index)])
            else:
                pairs.append(["fill", p.victim, p.unit, []])
    if not active:
        return _decision(pairs, []), r1_after
    bound_u = {p[2] for p in pairs}
    bound_v = {p[1] for p in pairs}
    spares = [u for u in free if u not in bound_u]
    contests = []
    dist3, clean3 = {}, {}
    for v, a in active:
        key = _pkey(a, v)
        st = states.get(key)
        if st is None or current_d.get(v) is None:
            continue
        spare_d = {b: d_of(b, v) for b in spares}
        fresh = {b: int(ledger.get((b, v), 0) or 0) == 0 for b in spares}
        st = r1m.update_persistence(st, spare_d, current_d[v], M, fresh)
        r1_after[key] = r1_progress_row(st)
        for b in spares:
            dist3[(b, v)] = spare_d[b]
            clean3[(b, v)] = clean_of(b, v)
        contests.append(r1m.Contest(victim=v, incumbent=a, d=int(current_d[v]), k=st.k, persist=st.persist_map()))
    released = []
    if spares and contests:
        for rep in r1m.plan_replacements(contests, spares, dist3, ledger, clean3, stall_steps=S, margin_persist=P):
            pairs.append(["replace", rep.victim, rep.new_unit, [rep.old_unit]])
            released.append(rep.old_unit)
    if released:
        still = [v for v in fill_v if v not in bound_v]
        if still:
            still_latched = [v for v in WL if v not in bound_v]
            dist4 = {(u, v): d_of(u, v) for u in released for v in still}
            for p in r1m.solve_fill(released, still, dist4, ledger, capped=still_latched):
                if p.victim in WL:
                    pairs.append(["latch_fill", p.victim, p.unit, sorted(binders.get(p.victim) or [], key=id_index)])
                else:
                    pairs.append(["second_fill", p.victim, p.unit, []])
    return _decision(pairs, []), r1_after


def _fp_actual(cur):
    """J's own planned decision, from the _cap outputs (stage-2 / stage-4 solve_fill, plan_replacements_detail)."""
    pairs, barred = [], []
    for c in cur.get("calls") or []:
        if c.get("fn") == "solve_fill":
            kind = "second_fill" if c.get("stage") == 4 else "fill"
            for v, u, _d, _r, _cl in c.get("out") or []:
                pairs.append([kind, v, u, []])
        elif c.get("fn") == "plan_replacements_detail":
            for v, old, new, _cause, _dist, latched in c.get("out") or []:
                pairs.append(["latch_fill" if latched else "replace", v, new, [old]])
            barred += [list(b) for b in c.get("barred") or []]
    return _decision(pairs, barred)


def footprint(cur, jd, r1m):
    """The ACTED footprint of one J point (FOOTPRINT_DOC): PURE on the recorded entry `cur`. Returns (fp fields,
    r1_after, rv1_after)."""
    base, _ = _fp_corrected(cur, jd, "base")
    actual = _fp_actual(cur)
    out = {"base": base, "base_eq_actual": base == actual, "alt": {}, "acted": []}
    if base != actual:
        out["actual"] = actual
    r1_after, rv1_after = {}, {}
    for name in FP_VARIANTS:
        if name == "r1":
            if r1m is None:
                continue
            dec, r1_after = _fp_r1(cur, r1m)
        elif name == "R1":
            dec, rv1_after = _fp_corrected(cur, jd, "R1")
        else:
            dec, _ = _fp_corrected(cur, jd, name)
        if dec["pairs"] != base["pairs"]:
            out["alt"][name] = dec
            out["acted"].append(name)
    return out, r1_after, rv1_after


def zr1_check(cur):
    """Z-R1 (10.3) at one J point, from the entry alone: every value J passed to its pure functions (the _cap records)
    against the instrument's independent recomputation (cur['inst']: its own maps; hist_progress / persist_generic: its
    own rules). Returns (problems, n_checked, a2_literal_differs, contest rows (CONTEST_COLS))."""
    inst = cur["inst"]
    s = cur["sets"]
    free = list(s["free"])
    probs = []
    n = 0
    a2 = 0
    ucell = inst["ucell"]
    vcell = inst["vcell"]
    hist = inst.get("hist") or {}

    def val(v, u, i):
        return _dist_get(cur, v, u, i)

    def has(v, u):
        return u in ((inst["dist"].get(v)) or {})

    def i_open(a, v):
        return val(v, a, 0) is not None

    def i_delta(a, v):
        if i_open(a, v):
            return val(v, a, 2)
        return grid_g(ucell[a], vcell[v])

    def i_frozen(a, v):
        return not (bool(val(v, a, 3)) or any(bool(val(v, f, 3)) for f in free))

    def bad(text):
        probs.append(text[:300])

    mine = {}       # binding -> (H', k', kL', closed', progressed) by the instrument's rule
    pers = {}       # binding -> persistence after (J's update_persistence output)
    prog_rows = {}  # binding -> the progress_step record
    for c in cur.get("calls") or []:
        fn = c.get("fn")
        if fn == "solve_fill":
            for u in c["units"]:
                for v in c["victims"]:
                    k = _pkey(u, v)
                    n += 1
                    if not has(v, u):
                        bad("solve_fill %s: no instrument value" % k)
                        continue
                    if c["d"].get(k) != val(v, u, 2):
                        bad("solve_fill %s: d* passed %r != instrument %r" % (k, c["d"].get(k), val(v, u, 2)))
                    if bool(c["clean"].get(k)) != bool(val(v, u, 3)) or k not in c["clean"]:
                        bad("solve_fill %s: clean passed %r != instrument %r" % (k, c["clean"].get(k), val(v, u, 3)))
        elif fn == "progress_step":
            if not c.get("binding"):
                bad("progress_step: binding unknown")
                continue
            a, v = c["binding"]
            k = _pkey(a, v)
            n += 1
            if not has(v, a):
                bad("progress_step %s: no instrument value" % k)
                continue
            if c["cell"] != list(ucell[a][:2]):
                bad("progress_step %s: cell %r != the unit's %r" % (k, c["cell"], ucell[a][:2]))
            o = i_open(a, v)
            if c["open"] != o:
                bad("progress_step %s: open %r != instrument %r" % (k, c["open"], o))
            if c["d"] != val(v, a, 0):
                bad("progress_step %s: d %r != instrument %r" % (k, c["d"], val(v, a, 0)))
            want_c = val(v, a, 1) if o else None
            if c["c"] != want_c:
                bad("progress_step %s: D_c %r != instrument %r" % (k, c["c"], want_c))
            hrow = (hist.get(k) or {}).get("H")
            before = cur["progress_before"].get(k)
            if before is None or hrow is None:
                bad("progress_step %s: no state at J entry" % k)
                continue
            if c["before"][0] != before[0] or c["before"][1:4] != before[1:4]:
                bad("progress_step %s: the state passed is not the state held at J entry" % k)
            dh, ch = [h[0] for h in hrow], [h[1] for h in hrow]
            if list(c["d_hist"]) != dh:
                bad("progress_step %s: d over H %r != instrument %r" % (k, c["d_hist"], dh))
            if list(c["c_hist"]) != ch:
                bad("progress_step %s: D_c over H %r != instrument %r" % (k, c["c_hist"], ch))
            fz = i_frozen(a, v)
            if bool(c["frozen"]) != fz:
                bad("progress_step %s: FROZEN %r != instrument %r" % (k, c["frozen"], fz))
            H1, k1, kl1, closed1, progressed = hist_progress(before[0], before[1], before[2], o, val(v, a, 0),
                                                             want_c, dh, ch, ucell[a][:2], fz)
            mine[k] = (H1, k1, kl1, closed1, progressed)
            prog_rows[k] = c
            if [c["after"][0], c["after"][1], c["after"][2], c["after"][3]] != [H1, k1, kl1, closed1]:
                bad("progress_step %s: verdict [H, k, k_L, closed] %r != instrument %r" % (
                    k, c["after"][:4], [H1, k1, kl1, closed1]))
            if int(c["after"][4]) != int(c["before"][4]) + 1:
                bad("progress_step %s: age %r -> %r" % (k, c["before"][4], c["after"][4]))
            lit = literal_progress(o, val(v, a, 0), want_c, dh, ch)
            if lit is not None and lit != progressed:
                a2 += 1
        elif fn == "update_persistence":
            if not c.get("binding"):
                bad("update_persistence: binding unknown")
                continue
            a, v = c["binding"]
            k = _pkey(a, v)
            n += 1
            if not has(v, a):
                bad("update_persistence %s: no instrument value" % k)
                continue
            for b, d in c["spare_d"].items():
                if d != val(v, b, 2):
                    bad("update_persistence %s: spare %s d* %r != instrument %r" % (k, b, d, val(v, b, 2)))
            dl = i_delta(a, v)
            if c["delta"] != dl:
                bad("update_persistence %s: delta %r != instrument %r" % (k, c["delta"], dl))
            want = persist_generic(c["before"], {b: val(v, b, 2) for b in c["spare_d"]}, dl, c["M"])
            if c["after"] != want:
                bad("update_persistence %s: counts %r != instrument %r" % (k, c["after"], want))
            pers[k] = c["after"]
        elif fn == "plan_replacements_detail":
            for row in c["contests"]:
                v, a, delta, op, kk, kl, persist, latched = row
                k = _pkey(a, v)
                n += 1
                if not has(v, a):
                    bad("plan %s: no instrument value" % k)
                    continue
                if op != i_open(a, v):
                    bad("plan %s: open %r != instrument %r" % (k, op, i_open(a, v)))
                if delta != i_delta(a, v):
                    bad("plan %s: delta %r != instrument %r" % (k, delta, i_delta(a, v)))
                want = mine.get(k)
                wk = (want[1], want[2]) if want is not None else (0, 0)
                if want is None and k in cur["progress_before"]:
                    bad("plan %s: a contest with a state at entry and no progress verdict" % k)
                if (kk, kl) != wk:
                    bad("plan %s: [k, k_L] %r != instrument %r" % (k, [kk, kl], list(wk)))
                if k in pers and persist != pers[k]:
                    bad("plan %s: persistence %r != update_persistence's %r" % (k, persist, pers[k]))
                lab = str(ucell[a][3]).strip().lower() == "route_blocked"
                if bool(latched) != lab:
                    bad("plan %s: latched %r != the label %r" % (k, latched, ucell[a][3]))
            for kk2, d in c["d"].items():
                b, v = _ukey(kk2)
                n += 1
                if d != val(v, b, 2):
                    bad("plan %s: d* %r != instrument %r" % (kk2, d, val(v, b, 2)))
                if bool(c["clean"].get(kk2)) != bool(val(v, b, 3)):
                    bad("plan %s: clean %r != instrument %r" % (kk2, c["clean"].get(kk2), val(v, b, 3)))
    # the contest rows (CONTEST_COLS), as J saw them
    rows = []
    _s, reassign, post, contests = _fp_sets(cur)
    after = cur.get("progress") or {}
    calls = cur.get("calls") or []
    for v, a in contests:
        k = _pkey(a, v)
        pr = prog_rows.get(k)
        b0 = cur["progress_before"].get(k)
        a1 = after.get(k)
        ucl = ucell.get(a) or [None, None, None, None]
        # delta as J saw it: the plan's Contest.delta, else the delta J passed to update_persistence
        j_delta = next((r[2] for c in calls if c.get("fn") == "plan_replacements_detail" for r in c["contests"]
                        if r[0] == v), None)
        if j_delta is None:
            j_delta = next((c["delta"] for c in calls if c.get("fn") == "update_persistence"
                            and c.get("binding") == [a, v]), None)
        j_open = pr["open"] if pr is not None else next(
            (r[3] for c in calls if c.get("fn") == "plan_replacements_detail" for r in c["contests"] if r[0] == v), None)
        rows.append([v, a, ucl[3], str(ucl[3]).strip().lower() == "route_blocked", j_open, j_delta,
                     None if pr is None else pr["frozen"],
                     None if b0 is None else b0[1], None if b0 is None else b0[2],
                     None if a1 is None else a1[1], None if a1 is None else a1[2],
                     None if b0 is None else b0[0], None if a1 is None else a1[0],
                     None if k not in mine else mine[k][4], b0 is None, ucl[2],
                     i_open(a, v) if has(v, a) else None, i_delta(a, v) if has(v, a) else None,
                     i_frozen(a, v) if has(v, a) else None])
    return probs, n, a2, rows


def purity_snapshot(model, ag):
    """The new recorders' purity guard (as the kick guard): the model's attributes (shallow), the RNG states, and the
    __dict__ of every firefighter / victim marker and managed victim state."""
    objs = []
    for name in ("firefighter_marker_agents", "victim_marker_agents", "managed_victims"):
        coll = getattr(model, name, None)
        if isinstance(coll, dict):
            for key, obj in coll.items():
                dd = getattr(obj, "__dict__", None)
                if isinstance(dd, dict):
                    objs.append((name, str(key), obj, dict(dd)))
    return dict(vars(model)), rng_states(ag, model), objs


def purity_diff(before, model, ag):
    bad = []
    changed = dict_changed(before[0], vars(model))
    if changed:
        bad.append("model attrs %r" % changed[:5])
    if before[1] != rng_states(ag, model):
        bad.append("rng state")
    for name, key, obj, dd in before[2]:
        changed = dict_changed(dd, getattr(obj, "__dict__", None) or {})
        if changed:
            bad.append("%s[%s] %r" % (name, key, changed[:5]))
    return bad


# ------------------------------------------------------------------------------------------------- recorders
def install(ag, cfv, wf, amod, gen, fae, udm, mpm=None, r1m=None):
    """Install every recorder (class-level wraps; call BEFORE the model is built). udm = the frozen U1 copy (or None:
    no kick shadow, and no instrument guard verdict - its frozen-function replica runs on udm's helpers; an mvg error
    is then recorded), mpm = src_extension.planning.movement_paths (the round's guard is in the model; None: no guard
    shadow at all). The instrument's verdict is frozen_guard_replica(udm, fae); movement_paths.stranding_guard,
    captured here (before any test can rebind the module attribute), is the cross-check (mp_verdict).
    r1m = the frozen round-1 J copy (load_r1_shadow; None: no r1 footprint, a dq error is recorded).
    Returns the record dict `rec` that sections() turns into d["dp"], d["ud"], d["mv"], d["mv_events"], d["mvg"],
    d["dq"]. Installs a gc callback (counting collections inside J calls) that main() removes."""
    WM = wf.WildFireModel
    FF = ag.Firefighter
    rec = {
        # _dp_probe v2's recorders
        "model": None, "phase": "init", "commands": [], "releases": [], "j_calls": [], "binders": [], "waiting": [],
        "waiting_custody": [], "m3a": [], "invariant": [], "m8": {}, "m9": [], "m9_open": [], "last_release": {},
        "errors": [], "inst_ms": 0.0, "j_detail": [], "j_timing": [], "in_j": False, "j_phase": None,
        # restored J-point machinery (_dp_probe v2, adapted) + dq
        "j_cur": None, "j_model": None, "j_plan_seen": False, "nest_ms": 0.0, "gc_n": 0, "j_ms": 0.0,
        "j_raw_ms": 0.0, "dq_errors": [], "dq_sample": [], "dq_last_cell": {}, "dq_log_cursor": [None, 0],
        "kick_gated": 0, "zr1": {"jpoints": 0, "checked": 0, "mismatch": [], "n_mismatch": 0, "a2_literal_differs": 0},
        "fp": {"jpoints": 0, "acted": {k: 0 for k in FP_VARIANTS}, "base_ne_actual": [], "errors": []},
        "shadow_r1": {}, "shadow_rv1": {}, "gc_cb": None,
        "dq_ms": {"jpoint_ms": 0.0, "footprint_ms": 0.0, "sample_ms": 0.0, "purity_ms": 0.0},
        # ud (v2)
        "ud_errors": [], "ud_ms": 0.0, "ctx": [], "inst": 0, "site": [], "adv": None, "kicks": [],
        "decisions": [], "burn_watch": [], "cmd_ctx": [], "rel_ctx": [], "mv_rows": [], "mv_events": [],
        "mismatch": [], "fix_calls": {"a": [], "b": [], "g": []}, "fix_depth": 0,
        "u1_shadow_ms": 0.0, "mv_ms": 0.0,
        "kick_ms": 0.0, "fid": {}, "vid": {}, "pickups": {}, "completes": {}, "kick_att": [],
        # mvg
        "mvg_errors": [], "guard_rows": [], "guard_ms": [], "inst_guard_ms": [], "mp_mismatch": [],
        "replica": {"checked": 0, "mismatch": [], "fix_checked": 0, "fix_mismatch": [], "cell_checked": 0,
                    "cell_mismatch": []},
    }
    joint_on = getattr(ag, "dispatch_joint", None) or (lambda: False)
    fn = shadow_funcs(ag)
    # the guard: the instrument's verdict = the frozen-function replica (on the U1 copy's helpers); the repo function
    # the model calls = the cross-check only
    mpfn = getattr(mpm, "stranding_guard", None) if mpm is not None else None
    gfn = None
    if mpm is not None:
        if udm is None:
            rec["mvg_errors"].append("install: no U1 shadow module - the instrument's guard verdict (the frozen-function "
                                     "replica on its helpers) cannot be computed; admit stays None")
        else:
            gfn = frozen_guard_replica(udm, fae)
    o_uorder = getattr(udm, "urgency_order", None) if udm is not None else None
    fix_tier = {"a": getattr(ag, "APPROACH_PATH_TIER", 7), "b": getattr(ag, "RETREAT_ON_ROUTE_TIER", 10)}
    # v2: the planner function _dispatch_firefighter_to_victim calls, imported the way wildfire_model imports it - the
    # rescue_planner module's own function, never wildfire_model's module global (a harness in the chain rebinds that
    # global to a recorder; a shadow call through it would add records to the harness)
    try:
        from src_extension.planning.rescue_planner import select_rescue_assignment as o_select
    except Exception as exc:  # recorded; acc stays None
        o_select = None
        rec["ud_errors"].append(("install_select: %r" % (exc,))[:300])
    sw_fn = {"a": getattr(ag, "ff_approach_path", lambda: False),
             "b": getattr(ag, "ff_retreat_keep_approach", lambda: False),
             "g": getattr(ag, "ff_fix_stranding_guard", lambda: False)}

    def err(where, exc):
        if len(rec["errors"]) < 30:
            rec["errors"].append(f"{where}: {exc!r}"[:240])

    def uerr(where, exc):
        if len(rec["ud_errors"]) < 60:
            rec["ud_errors"].append(f"{where}: {exc!r}"[:300])

    def gerr(where, exc):
        if len(rec["mvg_errors"]) < 60:
            rec["mvg_errors"].append(f"{where}: {exc!r}"[:300])

    def qerr(where, exc):
        if len(rec["dq_errors"]) < 60:
            rec["dq_errors"].append(f"{where}: {exc!r}"[:300])

    reassign_on = getattr(ag, "dispatch_reassign", None) or (lambda: False)
    jd_mod = getattr(wf, "_jd", None)
    # the corrected J's pure functions as the model calls them (_jd.<f>), captured BEFORE the _cap wraps: footprint()'s
    # base replay calls these originals (never a recorder)
    jd_orig = None
    if jd_mod is not None:
        jd_orig = types.SimpleNamespace(**{name: getattr(jd_mod, name) for name in (
            "solve_fill", "progress_step", "update_persistence", "plan_replacements_detail", "new_progress",
            "Progress", "Contest")})
    if r1m is None and jd_mod is not None:
        rec["dq_errors"].append("install: no round-1 shadow module - the r1 footprint is not computed")

    def gc_cb(phase, info):
        if rec["in_j"] and phase == "start":
            rec["gc_n"] += 1

    gc.callbacks.append(gc_cb)
    rec["gc_cb"] = gc_cb

    def step_of(m):
        return int(getattr(m, "evaluation_timesteps_counter", 0) or 0)

    def burning_cells(m):
        cells = set()
        for a in m.schedule.agents:
            if type(a) is ag.Fire and a.pos is not None and a.is_burning():
                cells.add((int(a.pos[0]), int(a.pos[1])))
        return cells

    def living_units(m):
        out = {}
        for fid, fm in (getattr(m, "firefighter_marker_agents", None) or {}).items():
            if getattr(fm, "dead", False) or str(getattr(fm, "status", "") or "").lower() == "dead":
                continue
            out[str(fid)] = fm
        return out

    def needy(m, vid, marker):
        state = (getattr(m, "managed_victims", None) or {}).get(vid)
        ms = str(getattr(marker, "status", "") or "").lower()
        ss = str(getattr(state, "status", "") or "").lower() if state is not None else ""
        if state is None or getattr(marker, "pos", None) is None:
            return False
        if getattr(state, "rescued", False) or "rescued" in (ms, ss) or "dead" in (ms, ss):
            return False
        if getattr(state, "cancelled", False) or ms == "cancelled":
            return False
        if getattr(state, "unreachable", False) or ms == "unreachable":
            return False
        return True

    def fid_of(m, unit):
        key = rec["fid"].get(id(unit))
        if key is None:
            for fid, fm in (getattr(m, "firefighter_marker_agents", None) or {}).items():
                rec["fid"][id(fm)] = str(fid)
            key = rec["fid"].get(id(unit), str(getattr(unit, "unit_id", "?")))
        return key

    def vid_of(m, marker):
        if marker is None:
            return None
        key = rec["vid"].get(id(marker))
        if key is None:
            for vid, mk in (getattr(m, "victim_marker_agents", None) or {}).items():
                rec["vid"][id(mk)] = str(vid)
            key = rec["vid"].get(id(marker), "?")
        return key

    # ================================================================== _dp_probe v2 recorders (unchanged meaning)
    am_cls = None
    for obj in vars(amod).values():
        if isinstance(obj, type) and hasattr(obj, "_run_post_move_cycle") and hasattr(obj, "_run_pre_move_cycle"):
            am_cls = obj
            break
    if am_cls is not None:
        o_pre, o_post = am_cls._run_pre_move_cycle, am_cls._run_post_move_cycle

        def pre_cycle(self, model, *a, **k):
            rec["phase"] = "pre"
            r = o_pre(self, model, *a, **k)
            rec["phase"] = "advance"
            return r

        def post_cycle(self, model, *a, **k):
            rec["phase"] = "post"
            r = o_post(self, model, *a, **k)
            rec["phase"] = "sweep"
            return r

        am_cls._run_pre_move_cycle = pre_cycle
        am_cls._run_post_move_cycle = post_cycle

    # ------------------------------------------------------------------ commands (the sink)
    o_apply = WM.apply_physical_rescue_command

    def apply_cmd(self, cmd):
        info = None
        extra = [None, None, None]
        t0 = time.perf_counter()
        try:
            action = str(cmd.action or "").strip().lower()
            vid = str(cmd.victim_id or "")
            fid = str(cmd.firefighter_id or "")
            # the record first: an observer error below can never drop it (R3 finding 1)
            info = [step_of(self), rec["phase"], action, vid, fid, str(cmd.reason or "")]
        except Exception as exc:
            err("apply_pre", exc)
        if info is not None and info[2] == "assign":
            try:
                vm = (cmd.metadata or {}).get("victim_marker") or (self.victim_marker_agents or {}).get(vid)
                fm = (self.firefighter_marker_agents or {}).get(fid)
                if vm is not None and fm is not None and vm.pos is not None and fm.pos is not None:
                    blocked = burning_cells(self)
                    d_route = _at(_bfs(vm.pos, self.grid, blocked), fm.pos, blocked)
                    extra = [d_route is not None, d_route,
                             abs(int(vm.pos[0]) - int(fm.pos[0])) + abs(int(vm.pos[1]) - int(fm.pos[1]))]
                    # K13 / M9: a unit freed by its first route_blocked raise on v, now bound to w != v
                    last = rec["last_release"].get(fid)
                    if joint_on() and last and last[0] == "o1" and last[1] != vid:
                        v_old = (self.victim_marker_agents or {}).get(last[1])
                        if v_old is not None and v_old.pos is not None and needy(self, last[1], v_old):
                            dmap = _bfs(v_old.pos, self.grid, blocked)
                            closed = all(_at(dmap, u.pos, blocked) is None
                                         for u in living_units(self).values() if u.pos is not None)
                            if closed:
                                entry = [step_of(self), fid, last[1], vid, []]
                                rec["m9"].append(entry)
                                rec["m9_open"].append((entry, step_of(self), rec["j_phase"] if rec["in_j"] else None))
            except Exception as exc:
                err("apply_obs", exc)
        uctx = list(rec["ctx"])
        spent = (time.perf_counter() - t0) * 1000.0
        ok = o_apply(self, cmd)
        t1 = time.perf_counter()
        try:
            if info is not None:
                rec["commands"].append(info + [bool(ok)] + extra)
                rec["cmd_ctx"].append(uctx)
                if info[2] == "unassign" and ok:
                    kind = "o1" if "replacement" in info[5] and "blocked" in info[5] else "other"
                    rec["last_release"][info[4]] = (kind, info[3], info[0])
                elif info[2] == "assign" and ok:
                    rec["last_release"].pop(info[4], None)
                    # dq: every bind resets the binding's footprint shadow states (as the model's ledger sink resets
                    # its progress state); a J bind re-initialises them after the J call
                    rec["shadow_r1"].pop(_pkey(info[4], info[3]), None)
                    rec["shadow_rv1"].pop(_pkey(info[4], info[3]), None)
        except Exception as exc:
            err("apply_post", exc)
        spent += (time.perf_counter() - t1) * 1000.0
        rec["inst_ms"] += spent
        if rec["in_j"]:
            rec["nest_ms"] += spent
        return ok

    WM.apply_physical_rescue_command = apply_cmd

    # ------------------------------------------------------------------ releases
    o_release = WM._release_other_claimants

    def release(self, *args, **kwargs):
        uctx = list(rec["ctx"])
        out = o_release(self, *args, **kwargs)
        t0 = time.perf_counter()
        try:
            vid = args[0] if args else kwargs.get("victim_id")
            keep = args[2] if len(args) > 2 else kwargs.get("keep_ff_id")
            reason = args[3] if len(args) > 3 else kwargs.get("reason")
            rec["releases"].append([step_of(self), rec["phase"], str(vid), str(keep or ""), str(reason or ""),
                                    str(kwargs.get("only_ff_id", "") or ""), list(out or [])])
            rec["rel_ctx"].append(uctx)
            for fid in out or []:
                rec["last_release"][str(fid)] = ("release", str(vid), step_of(self))
        except Exception as exc:
            err("release", exc)
        if rec["in_j"]:
            rec["nest_ms"] += (time.perf_counter() - t0) * 1000.0
        return out

    WM._release_other_claimants = release

    # ================================================================== J points (_dp_probe v2's, adapted; 12.1)
    o_jpoint = getattr(WM, "_joint_dispatch_point", None)

    def binding_of(state):
        """The (unit, victim) key holding `state` in the model's _dispatch_progress (identity), or None."""
        m = rec["j_model"]
        for key, st in (getattr(m, "_dispatch_progress", None) or {}).items():
            if st is state:
                return [str(key[0]), str(key[1])]
        return None

    def _cap(fn_name, record):
        """Wrap one pure J function on the module object wildfire_model calls through (WM reads _jd.<f> at call time).
        Records inputs and outputs only while a J call with PRE is open; its own time is nested (net J excludes it)."""
        original = getattr(jd_mod, fn_name)

        def wrapper(*args, **kwargs):
            out = original(*args, **kwargs)
            if rec["in_j"] and rec["j_cur"] is not None:
                t = time.perf_counter()
                try:
                    rec["j_cur"]["calls"].append(record(args, kwargs, out))
                except Exception as exc:
                    qerr("cap_" + fn_name, exc)
                rec["nest_ms"] += (time.perf_counter() - t) * 1000.0
            return out

        setattr(jd_mod, fn_name, wrapper)

    def _args(names, args, kwargs):
        vals = dict(zip(names, args))
        vals.update(kwargs)
        return vals

    def _nonzero_b(ledger, pairs):
        out = {}
        for u, v in pairs:
            b = int(ledger.get((u, v), 0) or 0)
            if b:
                out[_pkey(u, v)] = b
        return out

    def rec_fill(args, kwargs, out):
        a = _args(("units", "victims", "distance", "ledger", "clean", "capped"), args, kwargs)
        units, victims, dist, ledger = list(a["units"]), list(a["victims"]), a["distance"], a["ledger"]
        clean = a.get("clean") or {}
        pairs = [(u, v) for u in units for v in victims]
        return {"fn": "solve_fill", "stage": 4 if rec["j_plan_seen"] else 2, "units": units, "victims": victims,
                "d": {_pkey(u, v): dist.get((u, v)) for u, v in pairs},
                "clean": {_pkey(u, v): bool(clean[(u, v)]) for u, v in pairs if (u, v) in clean},
                "b": _nonzero_b(ledger, pairs), "capped": sorted(a.get("capped") or []),
                "out": [[p.victim, p.unit, p.distance, bool(p.reused), bool(getattr(p, "clean", False))] for p in out]}

    def rec_prog(args, kwargs, out):
        a = _args(("state", "route_open", "d_now", "c_now", "d_hist", "c_hist", "cell_now", "frozen"), args, kwargs)
        st = a["state"]
        return {"fn": "progress_step", "binding": binding_of(st), "open": bool(a["route_open"]), "d": a["d_now"],
                "c": a["c_now"], "d_hist": list(a["d_hist"]), "c_hist": list(a["c_hist"]),
                "cell": [int(a["cell_now"][0]), int(a["cell_now"][1])], "frozen": bool(a["frozen"]),
                "before": jd_progress_row(st)[:5], "after": jd_progress_row(out)[:5]}

    def rec_pers(args, kwargs, out):
        a = _args(("state", "spare_distance", "delta_incumbent", "margin"), args, kwargs)
        st = a["state"]
        return {"fn": "update_persistence", "binding": binding_of(st),
                "spare_d": {str(u): d for u, d in a["spare_distance"].items()}, "delta": a["delta_incumbent"],
                "M": a["margin"], "before": dict(st.persist_map()), "after": dict(out.persist_map())}

    def rec_plan(args, kwargs, out):
        rec["j_plan_seen"] = True
        a = _args(("contests", "spares", "distance", "ledger", "clean"), args, kwargs)
        contests, spares, dist, ledger, clean = list(a["contests"]), list(a["spares"]), a["distance"], a["ledger"], \
            a["clean"]
        reps, barred = out
        pairs = [(b, c.victim) for b in spares for c in contests]
        return {"fn": "plan_replacements_detail",
                "contests": [[c.victim, c.incumbent, c.delta, bool(c.route_open), c.k, c.k_closed, dict(c.persist),
                              bool(c.latched)] for c in contests],
                "spares": spares, "d": {_pkey(b, v): dist.get((b, v)) for b, v in pairs},
                "clean": {_pkey(b, v): bool(clean.get((b, v), False)) for b, v in pairs},
                "b": _nonzero_b(ledger, pairs), "S": a.get("stall_steps"), "P": a.get("margin_persist"),
                "out": [[r.victim, r.old_unit, r.new_unit, r.cause, r.distance, bool(r.latched)] for r in reps],
                "barred": [[b.victim, b.incumbent, b.cause, b.distance, list(b.units)] for b in barred]}

    def smp():
        return [getattr(ag, "dispatch_stall_steps", lambda: None)(), getattr(ag, "dispatch_margin_steps", lambda: None)(),
                getattr(ag, "dispatch_margin_persist", lambda: None)()]

    def jpoint_pre(self, phase):
        """The instrument's work BEFORE J (record-only): J's own snapshot (_dispatch_view), the counterfactual, PRE and
        the sets as the corrected J forms them, the shadow prune (J-post), and - where PRE holds - the j_detail entry
        with the instrument's independent maps (inst). Returns (legacy pairs, cur or None)."""
        view = self._dispatch_view()
        legacy = legacy_pairs(view)
        reassign = bool(reassign_on())
        post = str(phase) == "post"
        contest = dict(view["contest"]) if (reassign and post) else {}
        lb = dict(view.get("latched_binder") or {}) if (reassign and post) else {}
        fill_victims = list(view["waiting"]) if reassign else list(view["waiting"]) + list(view["latched"])
        pre = bool((view["free"] and fill_victims) or contest or lb)
        prog = getattr(self, "_dispatch_progress", None) or {}
        if post:
            live = {_pkey(u, v) for v, info in view["victims"].items() for u in info["binders"]}
            for sh in (rec["shadow_r1"], rec["shadow_rv1"]):
                for key in list(sh):
                    if key not in live:
                        sh.pop(key, None)
        if not pre:
            return legacy, None
        units = view["units"]
        voi = []
        for v in list(view["waiting"]) + list(view["latched"]) + list(contest) + list(lb):
            if v not in voi:
                voi.append(v)
        cur = {"sets": {"free": list(view["free"]), "waiting": list(view["waiting"]),
                        "latched": list(view["latched"]), "contest": contest, "latched_binder": lb,
                        "fill_victims": fill_victims,
                        "binders": {v: sorted(view["victims"][v]["binders"], key=id_index) for v in voi},
                        "reassign": reassign, "post": post},
               "pre": True, "calls": [],
               "progress_before": {_pkey(u, v): jd_progress_row(st) for (u, v), st in prog.items()}}
        w, h = int(self.grid.width), int(self.grid.height)
        burning, smoky = fire_reads(self, ag)
        unclean = inst_unclean(burning, smoky, w, h)
        ucell = {}
        for uid, um in units.items():
            if getattr(um, "pos", None) is None:
                continue
            c = (int(um.pos[0]), int(um.pos[1]))
            ucell[str(uid)] = [c[0], c[1], c in unclean, str(getattr(um, "status", "") or "")]
        vcell, dist, maps = {}, {}, {}
        for v in voi:
            vc = (int(view["victims"][v]["cell"][0]), int(view["victims"][v]["cell"][1]))
            fmap = inst_map(vc, w, h, burning)
            cmap = None if vc in unclean else inst_map(vc, w, h, unclean)
            maps[v] = (fmap, cmap)
            vcell[v] = [vc[0], vc[1], vc not in unclean]
            row = {}
            for uid, uc in ucell.items():
                cell = (uc[0], uc[1])
                d = inst_at(fmap, w, h, cell, burning)
                dc = inst_at(cmap, w, h, cell, unclean)
                row[uid] = [d, dc, None if d is None else (dc if dc is not None else d), dc is not None]
            dist[v] = row
        hist = {}
        ckeys = [_pkey(a, v) for v, a in list(contest.items()) + list(lb.items())]
        for v, a in list(contest.items()) + list(lb.items()):
            key = _pkey(a, v)
            fmap, cmap = maps[v]
            entry = {}
            st = prog.get((a, v))
            if st is not None:
                entry["H"] = [[inst_at(fmap, w, h, c, burning), inst_at(cmap, w, h, c, unclean)] for c in st.history]
            r1s = rec["shadow_r1"].get(key)
            if r1s is not None:
                entry["x_r1"] = inst_at(fmap, w, h, r1s.cell_prev, burning)
            rvs = rec["shadow_rv1"].get(key)
            if rvs is not None and rvs.get("cell_prev") is not None:
                entry["x_rv1"] = inst_at(fmap, w, h, rvs["cell_prev"], burning)
            hist[key] = entry
        cur["inst"] = {"digest": _digest(burning, smoky), "nB": len(burning), "nS": len(smoky), "ucell": ucell,
                       "vcell": vcell, "dist": dist, "hist": hist,
                       "ledger": {_pkey(u, v): int(b) for (u, v), b in
                                  (getattr(self, "_dispatch_ledger", None) or {}).items()},
                       "SMP": smp()}
        cur["fp"] = {"r1_before": {k: r1_progress_row(s) for k, s in rec["shadow_r1"].items() if k in ckeys},
                     "rv1_before": {k: dict(s, persist=dict(s["persist"])) for k, s in rec["shadow_rv1"].items()
                                    if k in ckeys}}
        return legacy, cur

    def jpoint_post(self, phase, n0, legacy, cur, ms, raw, thread_ms, gcn):
        """The instrument's work AFTER J (record-only): j_calls / j_timing (every J call), and where PRE held the
        progress after, Z-R1, the contest rows, the footprint and the shadow-state update, then the j_detail entry."""
        step = step_of(self)
        new = (getattr(self, "_dispatch_events", None) or [])[n0:]
        fills = sorted([e.get("victim_id"), e.get("unit")] for e in new
                       if e.get("kind") in ("fill", "latch_fill") and e.get("stage") == 2)
        stage3 = sorted([e.get("kind"), e.get("victim_id"), e.get("unit"), list(e.get("old_units") or [])]
                        for e in new if e.get("stage") == 3)
        stage4 = sorted([e.get("kind"), e.get("victim_id"), e.get("unit")] for e in new
                        if e.get("kind") in ("latch_fill", "second_fill") and e.get("stage") == 4)
        entry = [step, str(phase), round(ms, 3), len(new)]
        if fills or legacy or stage3 or stage4:
            entry.append({"legacy": sorted(legacy or []), "j_fills": fills, "stage3": stage3, "stage4": stage4})
        rec["j_calls"].append(entry)
        rec["j_timing"].append([step, str(phase), round(raw, 3), round(ms, 3), round(thread_ms, 3), gcn])
        if cur is None:
            return
        prog = getattr(self, "_dispatch_progress", None) or {}
        cur["progress"] = {_pkey(u, v): jd_progress_row(st) for (u, v), st in prog.items()}
        evaluated = {tuple(c["binding"]) for c in cur["calls"] if c.get("fn") == "progress_step" and c.get("binding")}
        ckeys = list(cur["sets"]["contest"].items()) + list(cur["sets"]["latched_binder"].items())
        cur["unevaluated"] = sorted([u, v] for v, u in ckeys
                                    if _pkey(u, v) in cur["progress_before"] and (u, v) not in evaluated)
        cur["initialised"] = sorted([u, v] for v, u in ckeys if _pkey(u, v) not in cur["progress_before"])
        try:
            probs, n, a2, rows = zr1_check(cur)
        except Exception as exc:
            probs, n, a2, rows = ["zr1_check raised %r" % (exc,)], 0, 0, []
        cur["zr1"] = probs
        cur["contests"] = rows
        z = rec["zr1"]
        z["jpoints"] += 1
        z["checked"] += n
        z["a2_literal_differs"] += a2
        z["n_mismatch"] += len(probs)
        for p in probs:
            if len(z["mismatch"]) < 200:
                z["mismatch"].append([step, str(phase), p])
        r1_after, rv1_after = {}, {}
        try:
            fp, r1_after, rv1_after = footprint(cur, jd_orig, r1m)
            cur["fp"].update(fp)
            f = rec["fp"]
            f["jpoints"] += 1
            for name in fp["acted"]:
                f["acted"][name] += 1
            if not fp["base_eq_actual"]:
                f["base_ne_actual"].append([step, str(phase)])
        except Exception as exc:
            if len(rec["fp"]["errors"]) < 30:
                rec["fp"]["errors"].append([step, str(phase), repr(exc)[:240]])
        # the footprint's shadow states: a contest binding still bound after J takes its after-state; J's binds
        # re-initialise (round 1's new_progress(d, cell) at the bind; the rv1 reference likewise)
        ffm = getattr(self, "firefighter_marker_agents", None) or {}
        vmk = getattr(self, "victim_marker_agents", None) or {}
        for v, u in ckeys:
            key = _pkey(u, v)
            um, vm = ffm.get(u), vmk.get(v)
            if um is not None and vm is not None and getattr(um, "rescued_victim", None) is vm:
                if key in r1_after and r1m is not None:
                    rec["shadow_r1"][key] = _r1_progress(r1m, r1_after[key])
                if key in rv1_after:
                    rec["shadow_rv1"][key] = rv1_after[key]
            else:
                rec["shadow_r1"].pop(key, None)
                rec["shadow_rv1"].pop(key, None)
        for e in new:
            if e.get("kind") not in ("fill", "second_fill", "replace", "latch_fill"):
                continue
            u, v = str(e.get("unit")), str(e.get("victim_id"))
            d = _dist_get(cur, v, u, 0)
            uc = cur["inst"]["ucell"].get(u)
            if d is None or uc is None:
                qerr("shadow_init", "step %s: J bound %s -> %s with no instrument d" % (step, u, v))
                continue
            if r1m is not None:
                rec["shadow_r1"][_pkey(u, v)] = r1m.new_progress(int(d), (int(uc[0]), int(uc[1])))
            rec["shadow_rv1"][_pkey(u, v)] = rv1_new(d, (uc[0], uc[1]))
        rec["j_detail"].append([step, str(phase), cur])

    if o_jpoint is not None:
        if jd_mod is not None:
            _cap("solve_fill", rec_fill)
            _cap("progress_step", rec_prog)
            _cap("update_persistence", rec_pers)
            _cap("plan_replacements_detail", rec_plan)

        def jpoint(self, phase):
            if not joint_on():
                return o_jpoint(self, phase)
            t_a = time.perf_counter()
            legacy, cur, snap = None, None, None
            try:
                snap = purity_snapshot(self, ag)
            except Exception as exc:
                qerr("jpoint_purity_snapshot", exc)
            t_b = time.perf_counter()
            try:
                legacy, cur = jpoint_pre(self, phase)
            except Exception as exc:
                qerr("jpoint_pre", exc)
                cur = None
            t_c = time.perf_counter()
            if snap is not None:
                try:
                    bad = purity_diff(snap, self, ag)
                    if bad:
                        qerr("jpoint_purity", "the J-point recorder changed state: %s" % "; ".join(bad))
                except Exception as exc:
                    qerr("jpoint_purity", exc)
            rec["dq_ms"]["jpoint_ms"] += (t_c - t_b) * 1000.0
            rec["dq_ms"]["purity_ms"] += ((t_b - t_a) + (time.perf_counter() - t_c)) * 1000.0
            n0 = len(getattr(self, "_dispatch_events", None) or [])
            rec["in_j"], rec["j_phase"], rec["j_cur"], rec["j_model"] = True, str(phase), cur, self
            rec["j_plan_seen"] = False
            rec["nest_ms"], rec["gc_n"] = 0.0, 0
            t0, c0 = time.perf_counter(), time.thread_time()
            try:
                r = o_jpoint(self, phase)
            finally:
                raw = (time.perf_counter() - t0) * 1000.0
                thread_ms = (time.thread_time() - c0) * 1000.0
                rec["in_j"], rec["j_cur"] = False, None
            nest, gcn = rec["nest_ms"], rec["gc_n"]
            ms = max(0.0, raw - nest)
            rec["j_ms"] += ms
            rec["j_raw_ms"] += raw
            t_d = time.perf_counter()
            snap = None
            try:
                snap = purity_snapshot(self, ag)
            except Exception as exc:
                qerr("jpoint_purity_snapshot", exc)
            t_e = time.perf_counter()
            try:
                jpoint_post(self, phase, n0, legacy, cur, ms, raw, thread_ms, gcn)
            except Exception as exc:
                qerr("jpoint_post", exc)
            t_f = time.perf_counter()
            if snap is not None:
                try:
                    bad = purity_diff(snap, self, ag)
                    if bad:
                        qerr("jpoint_purity", "the J-point recorder changed state (post): %s" % "; ".join(bad))
                except Exception as exc:
                    qerr("jpoint_purity", exc)
            rec["dq_ms"]["footprint_ms"] += (t_f - t_e) * 1000.0
            rec["dq_ms"]["purity_ms"] += ((t_e - t_d) + (time.perf_counter() - t_f)) * 1000.0
            return r

        WM._joint_dispatch_point = jpoint

    # ================================================================== the arm-independent per-step sample (10.1)
    def dq_sample(self):
        """One sample at the sample instant (right after _sync_firefighter_marker_status returns), in EVERY arm."""
        step = step_of(self)
        units = living_units(self)
        vmarkers = getattr(self, "victim_marker_agents", None) or {}
        by_id = {id(mk): str(v) for v, mk in vmarkers.items()}
        bound = {}
        for fid, fm in units.items():
            rv = getattr(fm, "rescued_victim", None)
            if rv is not None and id(rv) in by_id:
                bound.setdefault(by_id[id(rv)], []).append(fid)
        W, WL, custody, active = [], [], [], []
        vcell = {}
        for vid in sorted(str(v) for v in gen._detected_victim_ids(self)):
            mk = vmarkers.get(vid)
            if mk is None or not needy(self, vid, mk):
                continue
            cell = (int(mk.pos[0]), int(mk.pos[1]))
            bl = bound.get(vid, [])
            if any(getattr(units[f], "exiting", False) or getattr(units[f], "rescue_completed", False)
                   or (units[f].pos is not None and (int(units[f].pos[0]), int(units[f].pos[1])) == cell)
                   for f in bl):
                custody.append(vid)
                continue
            if not bl:
                W.append(vid)
            elif all(str(getattr(units[f], "status", "") or "").strip().lower() == "route_blocked" for f in bl):
                WL.append(vid)
            else:
                active.append(vid)
            vcell[vid] = cell
        targets = sorted(W + WL)
        w, h = int(self.grid.width), int(self.grid.height)
        burning = set()
        maps = {}
        if targets:
            burning, _smoky = fire_reads(self, ag)
            for v in targets:
                maps[v] = inst_map(vcell[v], w, h, burning)
        log = getattr(self, "_firefight_log", None)
        new_rows = []
        if isinstance(log, list):
            lid, pos = rec["dq_log_cursor"]
            if lid != id(log):
                pos = 0
            new_rows = log[pos:]
            rec["dq_log_cursor"] = [id(log), len(log)]
        by_ff = {}
        for r in new_rows:
            if isinstance(r, dict):
                wrote = r.get("wrote")
                by_ff.setdefault(str(r.get("ff")), []).append([r.get("action"), None if wrote is None else bool(wrote)])
        rows = []
        for fid in sorted(units, key=id_index):
            fm = units[fid]
            cell = None if getattr(fm, "pos", None) is None else (int(fm.pos[0]), int(fm.pos[1]))
            prev = rec["dq_last_cell"].get(fid, _MISSING)
            rec["dq_last_cell"][fid] = cell
            if cell is None:
                continue
            is_bound = getattr(fm, "rescued_victim", None) is not None
            exiting = bool(getattr(fm, "exiting", False) or getattr(fm, "rescue_completed", False))
            free = bool(self._firefighter_available_for_dispatch(fm))
            if not ((not is_bound and not exiting) or free):
                continue
            moved = None if (prev is _MISSING or prev is None) else (cell != prev)
            routes = [[v, inst_at(maps[v], w, h, cell, burning)] for v in targets]
            rows.append([fid, str(getattr(fm, "status", "") or ""), free, is_bound, [cell[0], cell[1]], moved, routes,
                         by_ff.get(fid, [])])
        rec["dq_sample"].append([step, W, WL, custody, active, rows])

    # ------------------------------------------------------------------ post-J sampling (no J here: the same instant)
    o_sync = WM._sync_firefighter_marker_status

    def sync(self, *a, **k):
        r = o_sync(self, *a, **k)
        t0 = time.perf_counter()
        try:
            step = step_of(self)
            units = living_units(self)
            vmarkers = getattr(self, "victim_marker_agents", None) or {}
            by_id = {id(mk): str(v) for v, mk in vmarkers.items()}
            bound: dict[str, list] = {}
            for fid, fm in units.items():
                rv = getattr(fm, "rescued_victim", None)
                if rv is not None and id(rv) in by_id:
                    bound.setdefault(by_id[id(rv)], []).append([fid, str(getattr(fm, "status", "") or "")])
            rec["binders"].append([step, sorted([v, sorted(b)] for v, b in bound.items())])
            free = [fid for fid, fm in units.items() if self._firefighter_available_for_dispatch(fm)]
            detected = gen._detected_victim_ids(self)
            ledger = getattr(self, "_dispatch_ledger", None) or {}
            rows = []
            custody_rows = []
            blocked = None
            for vid in sorted(detected):
                mk = vmarkers.get(vid)
                if mk is None or not needy(self, vid, mk):
                    continue
                if any(str(s).lower() != "route_blocked" for _, s in bound.get(vid, [])):
                    continue
                # custody (design 5.2, J's _dispatch_view): a binder exiting, rescue_completed or on the victim's cell
                cell = (int(mk.pos[0]), int(mk.pos[1]))
                if any(getattr(units[f], "exiting", False) or getattr(units[f], "rescue_completed", False)
                       or (units[f].pos is not None and (int(units[f].pos[0]), int(units[f].pos[1])) == cell)
                       for f, _ in bound.get(vid, [])):
                    custody_rows.append(vid)
                    continue
                if blocked is None:
                    blocked = burning_cells(self)
                dmap = _bfs(mk.pos, self.grid, blocked)
                cand = []
                for fid in free:
                    d = _at(dmap, units[fid].pos, blocked)
                    if d is not None:
                        cand.append([fid, d, int(ledger.get((fid, vid), 0) or 0)])
                rows.append([vid, cand])
            rec["waiting"].append([step, len(free), rows])
            if custody_rows:
                rec["waiting_custody"].append([step, custody_rows])
            if rows:
                cap = bool(getattr(ag, "dispatch_reassign", lambda: False)())
                held = {v for v, _ in rows if bound.get(v)}
                n_ok = sum(1 for fid in free
                           if any(not (cap and v in held and int(ledger.get((fid, v), 0) or 0) >= 2) for v, _ in rows))
                rec["m3a"].append([step, len(free), n_ok, sorted(free)])
            still = []
            for item in rec["m9_open"]:
                entry, bind_step, bind_phase = item
                if bind_phase == "post" and bind_step == step:
                    still.append(item)
                    continue
                vm = vmarkers.get(entry[2])
                if vm is None or vm.pos is None:
                    entry[4].append(None)
                else:
                    if blocked is None:
                        blocked = burning_cells(self)
                    dmap = _bfs(vm.pos, self.grid, blocked)
                    entry[4].append(any(_at(dmap, u.pos, blocked) is not None
                                        for u in units.values() if u.pos is not None))
                if len(entry[4]) < 3:
                    still.append(item)
            rec["m9_open"] = still
        except Exception as exc:
            err("sync", exc)
        rec["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        # dq: the arm-independent per-step sample, guarded like the shadows
        t_a = time.perf_counter()
        snap = None
        try:
            snap = purity_snapshot(self, ag)
        except Exception as exc:
            qerr("sample_purity_snapshot", exc)
        t_b = time.perf_counter()
        try:
            dq_sample(self)
        except Exception as exc:
            qerr("sample", exc)
        t_c = time.perf_counter()
        if snap is not None:
            try:
                bad = purity_diff(snap, self, ag)
                if bad:
                    qerr("sample_purity", "the sample changed state: %s" % "; ".join(bad))
            except Exception as exc:
                qerr("sample_purity", exc)
        rec["dq_ms"]["sample_ms"] += (t_c - t_b) * 1000.0
        rec["dq_ms"]["purity_ms"] += ((t_b - t_a) + (time.perf_counter() - t_c)) * 1000.0
        return r

    WM._sync_firefighter_marker_status = sync

    # ------------------------------------------------------------------ invariant capture
    o_inv = amod._check_rescue_assignment_invariant

    def inv(model):
        buf = io.StringIO()
        real = sys.stderr
        sys.stderr = buf
        try:
            o_inv(model)
        finally:
            sys.stderr = real
            text = buf.getvalue()
            if text:
                real.write(text)
                try:
                    step = step_of(model)
                    for line in text.splitlines():
                        if line.strip():
                            rec["invariant"].append([step, line.strip()[:300]])
                except Exception as exc:
                    err("inv", exc)

    amod._check_rescue_assignment_invariant = inv

    # ------------------------------------------------------------------ M8 at detection
    o_detect = WM._detect_victims_in_uav_radius

    def detect(self, *a, **k):
        try:
            before = set(gen._detected_victim_ids(self))
        except Exception as exc:
            err("detect_pre", exc)
            before = None
        r = o_detect(self, *a, **k)
        t0 = time.perf_counter()
        try:
            if before is not None:
                new = sorted(set(gen._detected_victim_ids(self)) - before)
                for vid in new:
                    mk = (self.victim_marker_agents or {}).get(vid)
                    if mk is None or mk.pos is None or vid in rec["m8"]:
                        continue
                    cell = (int(mk.pos[0]), int(mk.pos[1]))
                    blocked = burning_cells(self)
                    dmap = _bfs(cell, self.grid, blocked)
                    ds = [_at(dmap, u.pos, blocked) for u in living_units(self).values() if u.pos is not None]
                    ds = [d for d in ds if d is not None]
                    t_fire = None
                    try:
                        burning, _smoke = self._fix3b_true_fire()
                        wind = cfv.wind_vector_from_direction(getattr(getattr(self, "wind", None), "wind_direction", None))
                        grid_t = fae.arrival_time(int(self.grid.width), int(self.grid.height), set(burning), wind,
                                                  fae.front_priority_params())
                        value = float(grid_t[cell[0], cell[1]])
                        t_fire = None if value == float("inf") else round(value, 3)
                    except Exception as exc:
                        err("m8_tfire", exc)
                    rec["m8"][vid] = {"victim": vid, "detection_step": step_of(self), "cell": list(cell),
                                      "t_fire": t_fire, "min_d": min(ds) if ds else None,
                                      "first_burn_step": None, "death_step": None}
        except Exception as exc:
            err("detect", exc)
        rec["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        return r

    WM._detect_victims_in_uav_radius = detect

    # ------------------------------------------------------------------ per step: model capture, M8 + ud follow-up
    o_step = WM.step

    def step(self, *a, **k):
        rec["model"] = self
        r = o_step(self, *a, **k)
        t0 = time.perf_counter()
        try:
            if rec["m8"]:
                burning = None
                for vid, e in rec["m8"].items():
                    if e["first_burn_step"] is None:
                        if burning is None:
                            burning = burning_cells(self)
                        if tuple(e["cell"]) in burning:
                            e["first_burn_step"] = step_of(self)
                    if e["death_step"] is None:
                        mk = (self.victim_marker_agents or {}).get(vid)
                        state = (self.managed_victims or {}).get(vid)
                        ms = str(getattr(mk, "status", "") or "").lower() if mk is not None else ""
                        ss = str(getattr(state, "status", "") or "").lower() if state is not None else ""
                        if "dead" in (ms, ss):
                            e["death_step"] = step_of(self)
        except Exception as exc:
            err("step", exc)
        rec["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        t1 = time.perf_counter()
        try:
            if rec["burn_watch"]:
                burning = burning_cells(self)
                keep = []
                for dec in rec["burn_watch"]:
                    if tuple(dec["cell"]) in burning:
                        dec["first_burn"] = step_of(self)
                    else:
                        keep.append(dec)
                rec["burn_watch"] = keep
        except Exception as exc:
            uerr("step", exc)
        rec["ud_ms"] += (time.perf_counter() - t1) * 1000.0
        return r

    WM.step = step

    # ================================================================== ud: kicks (the U1 SHADOW, 16.5 / 22.9)
    def site_wrap(name, label):
        original = getattr(WM, name, None)
        if original is None:
            return

        def wrapper(self, *a, **k):
            rec["site"].append(label)
            try:
                return original(self, *a, **k)
            finally:
                rec["site"].pop()

        setattr(WM, name, wrapper)

    site_wrap("_process_pending_agent_removals", "K1")
    site_wrap("_revalidate_route_blocked_firefighters", "K2")

    o_kick = WM._try_dispatch_unresolved_confirmed_victims

    def guard_state(m):
        """The kick purity guard's reading: the model's attributes (shallow: the same names, the same objects), the
        RNG states, and the __dict__ of every agent / state object a kick shadow reads (firefighter and victim
        markers, managed victim and firefighter states)."""
        objs = []
        for name in ("firefighter_marker_agents", "victim_marker_agents", "managed_victims", "managed_firefighters"):
            coll = getattr(m, name, None)
            if isinstance(coll, dict):
                for key, obj in coll.items():
                    dd = getattr(obj, "__dict__", None)
                    if isinstance(dd, dict):
                        objs.append((name, str(key), obj, dict(dd)))
        return dict(vars(m)), rng_states(ag, m), objs

    def guard_diff(before, m):
        bad = []
        changed = dict_changed(before[0], vars(m))
        if changed:
            bad.append("model attrs %r" % changed[:5])
        if before[1] != rng_states(ag, m):
            bad.append("rng state")
        for name, key, obj, dd in before[2]:
            changed = dict_changed(dd, getattr(obj, "__dict__", None) or {})
            if changed:
                bad.append("%s[%s] %r" % (name, key, changed[:5]))
        return bad

    def kick(self, *a, **k):
        t0 = time.perf_counter()
        K = None
        try:
            site = rec["site"][-1] if rec["site"] else "other"
            rec["inst"] += 1
            try:
                if joint_on():
                    # dq_probe v1 (12.1): the U1 kick shadow is gated off while DISPATCH_JOINT is on (its acc check
                    # would append spurious mismatch rows in a J arm); the kick itself runs unchanged
                    rec["kick_gated"] += 1
                else:
                    before = guard_state(self)
                    K = kick_shadow(self, ag, udm, fae, o_uorder, o_select, cfv) if udm is not None else None
                    bad = guard_diff(before, self)
                    if bad:
                        uerr("kick_purity", "the kick shadow changed state: %s" % "; ".join(bad))
            finally:
                rec["inst"] -= 1
            if K is not None:
                K.update(i=len(rec["kicks"]), step=step_of(self), phase=rec["phase"], site=site,
                         switch=bool(getattr(ag, "dispatch_urgency", lambda: False)()))
                rec["u1_shadow_ms"] += K["ms"] or 0.0
        except Exception as exc:
            uerr("kick_pre", exc)
            K = None
        n0 = len(rec["commands"])
        att = []
        rec["kick_att"].append(att)
        rec["ctx"].append("kick:" + (rec["site"][-1] if rec["site"] else "other"))
        spent = (time.perf_counter() - t0) * 1000.0
        try:
            r = o_kick(self, *a, **k)
        finally:
            rec["ctx"].pop()
            rec["kick_att"].pop()
        t1 = time.perf_counter()
        try:
            if K is not None:
                bound = [[c[3], c[4]] for c in rec["commands"][n0:] if c[2] == "assign" and c[6]]
                K["bound"] = bound
                K["n_cmd"] = len(rec["commands"]) - n0
                K["attempts"] = att
                bind_flags(K, bound)
                K["ms_model"] = None    # no U1 in the model
                K["triage"] = None
                served = bound[0][0] if bound else None
                if K["acc"] is not None:
                    # the kick's first bind must be the shadow's: U1's at a qualifying kick of an ON arm (never in
                    # this round: U1 is not in the model), the index order's at every other kick
                    on_u1 = bool(K["switch"] and K["qualifies"])
                    expected = K["u1_wb"] if on_u1 else K["index_wb"]
                    if served != expected:
                        rec["mismatch"].append([K["step"], K["F"][0][0] if K["F"] else None,
                                                "u1" if on_u1 else "index", "kick bind differs from the acc shadow",
                                                "kick:%d" % K["i"], expected, served])
                if K["qualifies"]:
                    free_id = K["F"][0][0] if K["F"] else None
                    pos = {v: c for v, c in K["W"]}
                    acc = K["acc"]
                    for vid in K["index"]:
                        r3 = K["rec"].get(vid) or [None, None, None]
                        dec = {"k": K["i"], "step": K["step"], "vid": vid, "cell": pos.get(vid), "T": r3[0],
                               "c": r3[1], "P": r3[2], "d": (K["d"].get(vid) or {}).get(free_id), "unit": free_id,
                               "served": vid == served, "u1_first": bool(K["u1"]) and K["u1"][0] == vid,
                               "index_first": K["index"][0] == vid,
                               "accepted": None if acc is None else bool(acc.get(vid)),
                               "index_wb": vid == K["index_wb"], "u1_wb": vid == K["u1_wb"],
                               "first_burn": None, "pickup": None, "death": None, "complete": None}
                        rec["decisions"].append(dec)
                        if dec["cell"] is not None:
                            rec["burn_watch"].append(dec)
                K["inst_ms"] = round(spent + (time.perf_counter() - t1) * 1000.0, 3)
                rec["kicks"].append(K)
        except Exception as exc:
            uerr("kick_post", exc)
        tot = spent + (time.perf_counter() - t1) * 1000.0
        rec["ud_ms"] += tot
        rec["kick_ms"] += tot
        return r

    WM._try_dispatch_unresolved_confirmed_victims = kick

    # v2: every _dispatch_firefighter_to_victim call made during a kick, in call order, with its return value
    # (record-only; a call outside any kick, or from a shadow, is not recorded)
    o_dispatch = getattr(WM, "_dispatch_firefighter_to_victim", None)
    if o_dispatch is not None:
        def dispatch(self, *a, **k):
            slot = None
            if rec["kick_att"] and not rec["inst"]:
                try:
                    slot = [str(a[0] if a else k.get("victim_id")), None]
                    for lst in rec["kick_att"]:
                        lst.append(slot)
                except Exception as exc:
                    uerr("dispatch_pre", exc)
                    slot = None
            out = o_dispatch(self, *a, **k)
            if slot is not None:
                slot[1] = bool(out)
            return out

        WM._dispatch_firefighter_to_victim = dispatch

    # ================================================================== movement (22.6.3) + the guard (1d.8 (5))
    o_advance = FF.advance
    o_refresh = FF._refresh_target_from_victim

    def refresh(self, *a, **k):
        r = o_refresh(self, *a, **k)
        ctx = rec["adv"]
        if ctx is not None and ctx["unit"] is self and ctx["S"] is None and not ctx["done"]:
            ctx["done"] = True
            t0 = time.perf_counter()
            model = self.model
            rec["inst"] += 1
            try:
                before = (dict(self.__dict__), dict(vars(model)), rng_states(ag, model))
                S = mv_shadow(self, model, ag, fn, gfn, cfv, mpfn)
                bad = dict_changed(before[0], self.__dict__)
                bad_m = dict_changed(before[1], vars(model))
                bad_r = before[2] != rng_states(ag, model)
                if bad or bad_m or bad_r:
                    uerr("mv_purity", "shadow changed state: unit keys %r, model attrs %r, rng %s" % (
                        bad[:5], bad_m[:5], bad_r))
                ctx["S"] = S
                if S is not None:
                    for text in S.get("gerr") or ():
                        gerr("guard step %s" % step_of(model), text)
                    for f in ("a", "b"):
                        if S.get("g" + f) is not None:
                            rec["inst_guard_ms"].append(round(S["g" + f][3], 3))
            except Exception as exc:
                uerr("mv_shadow", exc)
            finally:
                rec["inst"] -= 1
            ctx["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        return r

    def advance(self, *a, **k):
        t0 = time.perf_counter()
        ctx = None
        try:
            if getattr(self, "pos", None) is not None and not getattr(self, "dead", False):
                ctx = {"unit": self, "S": None, "done": False, "mt": 0, "rb_call": 0, "rb_set": 0,
                       "st_pre": str(getattr(self, "status", "") or ""),
                       "victim": vid_of(self.model, getattr(self, "rescued_victim", None)),
                       "fix_ms": 0.0, "fix_by": {}, "exit_kind": None,
                       "model_a": _MISSING, "model_b": _MISSING, "model_g": [], "inst_ms": 0.0}
        except Exception as exc:
            uerr("advance_pre", exc)
            ctx = None
        prev = rec["adv"]
        rec["adv"] = ctx
        rec["ctx"].append("adv:" + (fid_of(self.model, self) if ctx is not None else "?"))
        pre_ms = (time.perf_counter() - t0) * 1000.0
        try:
            r = o_advance(self, *a, **k)
        finally:
            rec["ctx"].pop()
            rec["adv"] = prev
        t1 = time.perf_counter()
        try:
            if ctx is not None and ctx["S"] is not None:
                mv_row(self, ctx)
        except Exception as exc:
            uerr("advance_post", exc)
        post_ms = (time.perf_counter() - t1) * 1000.0
        tot = pre_ms + post_ms + (ctx["inst_ms"] if ctx is not None else 0.0)
        rec["ud_ms"] += pre_ms + post_ms
        rec["mv_ms"] += tot
        if ctx is not None and rec["mv_rows"] and ctx.get("row_i") is not None:
            rec["mv_rows"][ctx["row_i"]][_INST_MS_I] = round(tot, 3)
        if ctx is not None:
            rec["ud_ms"] += ctx["inst_ms"]
        return r

    def mv_row(unit, ctx):
        S = ctx["S"]
        model = unit.model
        post = _cell(getattr(unit, "pos", None))
        burning, smoky = S["burning"], S["smoky"]
        oob = model.grid.out_of_bounds
        fine = str((getattr(unit, "movement_reason", None) or {}).get("fine_category", "") or "")
        tier = int(getattr(unit, "_last_move_tier", 0) or 0)
        leg = S["leg"]
        # the MODEL's guard calls in this advance (at most one: (b) at the survival retreat, or (a) at the approach)
        mg = {}
        for call in ctx["model_g"]:
            if call["kind"] in mg:
                gerr("model_guard step %s" % step_of(model), "more than one model guard call for fix %s in one advance"
                     % call["kind"])
            mg[call["kind"]] = call
        vetoed = {f: not c["verdict"][0] for f, c in mg.items()}
        if leg == "approach":
            if fine == "exiting_setup":
                br = "pickup"
            elif fine == "survival_retreat_on_route":
                br = "retreat_b"
            elif fine == "survival_retreat":
                br = "retreat_b_veto" if vetoed.get("b") else "retreat"
            elif fine == "moving_to_victim":
                if S["trig"]:
                    br = "retreat_b_veto" if vetoed.get("b") else "retreat_fb"
                elif ctx["model_a"] is not _MISSING and ctx["model_a"] is not None:
                    # the label says which step was TAKEN: a vetoed decision whose fix step was nevertheless taken (a
                    # defect) stays approach_a, and the guarded agreement below fails it
                    took_fix = post == _cell(ctx["model_a"]) and tier == fix_tier["a"]
                    br = "approach_a_veto" if (vetoed.get("a") and not took_fix) else "approach_a"
                else:
                    br = "approach"
            else:
                br = "other:" + fine
        else:
            if fine == "exiting_complete":
                br = "complete"
            elif fine == "exiting_with_victim":
                base = ("path" if ctx["exit_kind"] == "path" else "fallback") if ctx["exit_kind"] else "greedy"
                if base != "path":
                    if ctx["rb_call"]:
                        base += "_raise"
                    elif tier == 6 and post == S["pre"]:
                        base += "_hold"
                br = base
            else:
                br = "other:" + fine
        c1_post = None
        if S["kind"] == "carry" and post is not None:
            c1_post = _c1_cost(post, burning, smoky, oob)
        step = step_of(model)
        uid = fid_of(model, unit)
        ga = S["ga"][0] if S.get("ga") is not None else None
        gb = S["gb"][0] if S.get("gb") is not None else None
        inst_admit = {"a": ga, "b": gb}
        veto = "".join(f for f in "ab" if vetoed.get(f))
        acted_g = "".join(f for f in S["acted"] if inst_admit.get(f) is True)
        row = [step, uid, ctx["victim"], leg, br, _jc(S["pre"]), _jc(post), _jc(S["target"]), S["digest"],
               ctx["st_pre"], str(getattr(unit, "status", "") or ""), tier, ctx["mt"], ctx["rb_call"], ctx["rb_set"],
               S["trig"], S["zrb"],
               None if S["today"] is None else [S["today"][0], _jc(S["today"][1]), S["today"][2], S["today"][3]],
               _jc(S["fa"]), _jc(S["fb"]), None if S["fbB"] is None else [_jc(c) for c in S["fbB"]],
               None, S["acted"],
               S["dc"], S["dcx"], S["df"], S["dm"], S["dr"], S["gesc"],
               S["cls_pre"], None if post is None else _cls(post, burning, smoky),
               S["fd_pre"], None if post is None else _mfd(post, burning), S["c1_pre"], c1_post,
               round(ctx["fix_ms"], 3), None, S["dcb"],
               ga, gb, veto, acted_g]
        ctx["row_i"] = len(rec["mv_rows"])
        rec["mv_rows"].append(row)
        if br == "pickup" and ctx["victim"]:
            rec["pickups"].setdefault(ctx["victim"], []).append(step)
        if br == "complete" and ctx["victim"]:
            rec["completes"].setdefault(ctx["victim"], step)
        for f, ms in ctx["fix_by"].items():
            rec["fix_calls"].setdefault(f, []).append(round(ms, 3))
        post_w = writes_of(unit)
        # the survival_writes replica against the model (every advance with the survival trigger)
        sv = S.get("sv")
        if leg == "approach" and S["trig"] and sv is not None:
            rp = rec["replica"]
            if br in ("retreat", "retreat_fb", "retreat_b_veto"):
                rp["checked"] += 1
                if sv["pred"] != post_w:
                    if len(rp["mismatch"]) < 30:
                        rp["mismatch"].append([step, uid, br, sv["pre"], sv["pred"], post_w])
            elif br == "retreat_b":
                rp["fix_checked"] += 1
                if sv["pre"] != post_w:
                    if len(rp["fix_mismatch"]) < 30:
                        rp["fix_mismatch"].append([step, uid, br, sv["pre"], post_w])
            today_cell = S["today"][1] if S["today"] is not None else None
            want = _jc(today_cell) if S["today"] is not None and S["today"][0] == "survival" else None
            rp["cell_checked"] += 1
            if sv["cell"] != want:
                if len(rp["cell_mismatch"]) < 30:
                    rp["cell_mismatch"].append([step, uid, sv["cell"], S["today"]])
        # ACTED events (the UNGUARDED shadow, every arm), guard-aware agreement, and one guard row per acting fix
        guard_on = bool(sw_fn["g"]())
        for f in S["acted"]:
            live = bool(sw_fn[f]())
            cell = S["fa"] if f == "a" else S["fb"]
            gs = S.get("g" + f)
            call = mg.get(f)
            model_admit = None if call is None else bool(call["verdict"][0])
            was_vetoed = bool(live and call is not None and not call["verdict"][0])
            t_cell = S["today"][1] if S["today"][1] is not None else S["pre"]
            agree = None
            expect_fix = None
            if live:
                if not guard_on:
                    expect_fix = True
                elif gs is not None:
                    expect_fix = bool(gs[0])
                if expect_fix is True:
                    agree = br == FIX_BRANCH[f] and post == cell
                elif expect_fix is False:
                    agree = br == VETO_BRANCH[f] and post == t_cell
            ev = {"step": step, "kind": f, "unit": uid, "victim": ctx["victim"], "live": live, "row": ctx["row_i"],
                  "cell": _jc(cell), "today": row[17], "taken": _jc(post), "branch": br, "detail": None,
                  "agree": agree,
                  "guard": {"admit": None if gs is None else gs[0], "c": None if gs is None else gs[1],
                            "T_v": None if gs is None else gs[2], "model_admit": model_admit},
                  "vetoed": was_vetoed, "ran": bool(live and not was_vetoed)}
            rec["mv_events"].append(ev)
            if live and agree is False:
                if expect_fix:
                    rec["mismatch"].append([step, uid, f, "shadow acted, model did not", br, _jc(cell), _jc(post)])
                else:
                    rec["mismatch"].append([step, uid, f, "guard vetoes (instrument), model did not take today's step",
                                            br, _jc(t_cell), _jc(post)])
            if call is not None:
                if call["cell"] != cell:
                    rec["mismatch"].append([step, uid, f, "guard evaluated on a cell other than the shadow's", br,
                                            _jc(cell), _jc(call["cell"])])
                if gs is not None and bool(call["verdict"][0]) != bool(gs[0]):
                    rec["mismatch"].append([step, uid, f, "model guard verdict != instrument verdict", br,
                                            [bool(call["verdict"][0]), call["verdict"][1], call["verdict"][2]],
                                            [gs[0], gs[1], gs[2]]])
            took = "fix" if (post == cell and tier == fix_tier[f]) else "today"
            # the cross-check: the repo function's tuple against the instrument's (frozen-function replica's)
            gm = S.get("g" + f + "_mp")
            inst = None if gs is None else [gs[0], gs[1], gs[2]]
            if gm != inst:
                rec["mp_mismatch"].append([step, uid, f, len(rec["guard_rows"]), inst, gm])
            rec["guard_rows"].append([
                step, uid, ctx["victim"], f, _jc(S["pre"]), _jc(cell), _jc(S["target"]),
                _jc(S["today"][1]), S["today"][0], S["today"][2], bool(S["today"][3]),
                None if gs is None else gs[1], None if gs is None else gs[2], None if gs is None else gs[0],
                model_admit, None if call is None else list(call["verdict"]),
                None if call is None else _jc(call["cell"]), took, _jc(post), tier, bool(ctx["rb_call"]),
                sv["pre"] if (f == "b" and sv) else None, sv["pred"] if (f == "b" and sv) else None,
                post_w if f == "b" else None,
                None if call is None else round(call["ms"], 3), None if gs is None else round(gs[3], 3),
                ctx["row_i"], None if gm is None else list(gm)])
        for f in ("a", "b"):
            if f in mg and f not in S["acted"]:
                # the model evaluated the guard on a fix the (unguarded) shadow says does not act
                rec["mismatch"].append([step, uid, f, "model guard call where the shadow did not act", br,
                                        _jc(S["fa"] if f == "a" else S["fb"]), _jc(mg[f]["cell"])])
        if leg == "approach" and S["kind"] == "approach" and sw_fn["a"]() and br in ("approach_a", "approach_a_veto") \
                and "a" not in S["acted"]:
            rec["mismatch"].append([step, uid, "a", "model acted, shadow did not", br, _jc(S["fa"]), _jc(post)])
        if leg == "approach" and br in ("retreat_b", "retreat_b_veto") and "b" not in S["acted"]:
            rec["mismatch"].append([step, uid, "b", "model acted, shadow did not", br, _jc(S["fb"]), _jc(post)])

    FF.advance = advance
    FF._refresh_target_from_victim = refresh

    def thin(name, before=None, after=None):
        original = getattr(FF, name)

        def wrapper(self, *a, **k):
            ctx = rec["adv"]
            if ctx is not None and ctx["unit"] is not self:
                ctx = None
            if ctx is not None and before is not None:
                before(self, ctx, a)
            out = original(self, *a, **k)
            if ctx is not None and after is not None:
                after(self, ctx, out)
            return out

        setattr(FF, name, wrapper)

    def mt_before(self, ctx, a):
        ctx["mt"] += 1

    def rb_before(self, ctx, a):
        ctx["rb_call"] += 1
        if str(getattr(self, "status", "") or "").strip().lower() != "route_blocked":
            ctx["rb_set"] += 1

    def exit_after(self, ctx, out):
        ctx["exit_kind"] = out

    thin("_move_toward", before=mt_before)
    thin("_mark_route_blocked", before=rb_before)
    thin("_exit_leg_step", after=exit_after)

    def fix_wrap(name, fix, slot=None):
        original = getattr(FF, name)

        def wrapper(self, *a, **k):
            ctx = rec["adv"]
            if rec["inst"] or rec["fix_depth"] or ctx is None or ctx["unit"] is not self:
                return original(self, *a, **k)
            f = fix
            if f is None:   # _fix_move: the tier says which fix called it
                tier = a[1] if len(a) > 1 else k.get("tier")
                f = "a" if tier == fix_tier["a"] else "b" if tier == fix_tier["b"] else "x"
                if f == "x":
                    gerr("fix_move", "a _fix_move call with tier %r (neither fix's)" % (tier,))
            rec["fix_depth"] += 1
            rec["ctx"].append("fix:" + (name if fix is None else f))
            t0 = time.perf_counter()
            try:
                out = original(self, *a, **k)
            finally:
                ms = (time.perf_counter() - t0) * 1000.0
                rec["ctx"].pop()
                rec["fix_depth"] -= 1
                ctx["fix_ms"] += ms
                ctx["fix_by"][f] = ctx["fix_by"].get(f, 0.0) + ms
            if slot is not None:
                ctx[slot] = out
            return out

        setattr(FF, name, wrapper)

    if hasattr(FF, "_approach_path_choice"):
        fix_wrap("_approach_path_choice", "a", "model_a")
        fix_wrap("_retreat_on_route_choice", "b", "model_b")
        fix_wrap("_fix_move", None)

    # the guard, timed as its OWN fix-code call ("g"); its return is the MODEL's verdict (model_admit)
    o_verdict = getattr(FF, "_stranding_guard_verdict", None)
    if o_verdict is not None:
        def verdict(self, step_cell, *a, **k):
            ctx = rec["adv"]
            if rec["inst"] or rec["fix_depth"] or ctx is None or ctx["unit"] is not self:
                return o_verdict(self, step_cell, *a, **k)
            rec["fix_depth"] += 1
            rec["ctx"].append("fix:g")
            t0 = time.perf_counter()
            try:
                out = o_verdict(self, step_cell, *a, **k)
            finally:
                ms = (time.perf_counter() - t0) * 1000.0
                rec["ctx"].pop()
                rec["fix_depth"] -= 1
                ctx["fix_ms"] += ms
                ctx["fix_by"]["g"] = ctx["fix_by"].get("g", 0.0) + ms
                rec["guard_ms"].append(round(ms, 3))
            try:
                # which fix's step is judged: (b) when this advance called fix (b)'s choice (the survival branch),
                # else (a) - the two branches are exclusive within one advance
                kind = "b" if ctx["model_b"] is not _MISSING else "a"
                ctx["model_g"].append({"kind": kind, "cell": _cell(step_cell), "ms": ms,
                                       "verdict": [bool(out[0]), None if out[1] is None else int(out[1]),
                                                   _fin(out[2])]})
            except Exception as exc:
                gerr("model_verdict", exc)
            return out

        FF._stranding_guard_verdict = verdict
    else:
        gerr("install", "agents.Firefighter has no _stranding_guard_verdict")

    return rec


def _file_shas(repo, rels):
    out = {}
    for rel in rels:
        path = os.path.join(repo, rel)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def sections(rec, ag, cfv, wf, repo, rc=None, chain_exc=None, wall_s=None, process_s=None, u1=None, probe_sha=None):
    """(d["dp"], d["ud"], d["mv"], d["mv_events"], d["mvg"]) from the record `install` filled. u1 = {"sha", "path",
    "error"} of the U1 shadow load; probe_sha = lf_sha256 of this file, read when the run started."""
    m = rec["model"]
    ledger = getattr(m, "_dispatch_ledger", None) or {} if m is not None else {}
    dp = {
        "probe": DP_VERSION,
        "rc_chain": rc,
        "chain_exception": repr(chain_exc) if chain_exc is not None else None,
        "switches": {
            "DISPATCH_JOINT": repr(getattr(cfv, "DISPATCH_JOINT", None)),
            "DISPATCH_REASSIGN": repr(getattr(cfv, "DISPATCH_REASSIGN", None)),
            "joint_on": bool(getattr(ag, "dispatch_joint", lambda: False)()),
            "reassign_on": bool(getattr(ag, "dispatch_reassign", lambda: False)()),
            "S": getattr(ag, "dispatch_stall_steps", lambda: None)(),
            "M": getattr(ag, "dispatch_margin_steps", lambda: None)(),
            "P": getattr(ag, "dispatch_margin_persist", lambda: None)(),
        },
        "src_sha": _file_shas(repo, SHA_FILES),
        "commands": rec["commands"],
        "releases": rec["releases"],
        "j_calls": rec["j_calls"],
        "j_events": list(getattr(m, "_dispatch_events", None) or []) if m is not None else [],
        "ledger": {f"{u}|{v}": int(b) for (u, v), b in ledger.items()},
        "binders": rec["binders"],
        "waiting": rec["waiting"],
        "waiting_custody": rec["waiting_custody"],
        "m3a": rec["m3a"],
        "invariant": rec["invariant"],
        "m8": sorted(rec["m8"].values(), key=lambda e: e["victim"]),
        "m9": rec["m9"],
        "j_detail": rec["j_detail"],
        "j_timing": rec["j_timing"],
        "writeoffs_avoided": list(getattr(m, "dispatch_writeoffs_avoided", None) or []) if m is not None else [],
        "timing": {"j_ms_total": round(rec["j_ms"], 3), "j_ms_raw_total": round(rec["j_raw_ms"], 3),
                   "inst_ms_total": round(rec["inst_ms"], 3)},
        "errors": rec["errors"],
    }
    # fates of every victim the record met, and the decisions' outcome fields
    deaths = {e["victim"]: e["death_step"] for e in rec["m8"].values()}
    fates = {}
    for v in sorted(set(rec["pickups"]) | set(rec["completes"]) | set(deaths)):
        fates[v] = {"pickups": rec["pickups"].get(v, []), "complete": rec["completes"].get(v),
                    "death": deaths.get(v)}
    for dec in rec["decisions"]:
        later = [s for s in rec["pickups"].get(dec["vid"], []) if s >= dec["step"]]
        dec["pickup"] = later[0] if later else None
        dec["death"] = deaths.get(dec["vid"])
        c = rec["completes"].get(dec["vid"])
        dec["complete"] = c if c is not None and c >= dec["step"] else None

    def acc(name, default=None):
        f = getattr(ag, name, None)
        try:
            return f() if callable(f) else default
        except Exception as exc:  # recorded, not swallowed
            return "ERR %s" % type(exc).__name__

    try:
        stale = wf.WildFireModel._route_block_stale_clear_mode()
    except Exception as exc:
        stale = "ERR %s" % type(exc).__name__
    other = {
        "FF_EXIT_LEG_MODE": acc("ff_exit_leg_mode"),
        "FF_EXIT_LEG_SERVED": acc("ff_exit_leg_served"),
        "FF_EXIT_LEG_HOLD": acc("ff_exit_leg_hold"),
        "ROUTE_BLOCK_STALE_CLEAR": stale,
    }
    probe_ms = rec["inst_ms"] + rec["ud_ms"]
    ud = {
        "probe": VERSION,
        "rc_chain": rc,
        "switches": dict({
            "DISPATCH_URGENCY": bool(acc("dispatch_urgency", False)),
            "FF_APPROACH_PATH": bool(acc("ff_approach_path", False)),
            "FF_RETREAT_KEEP_APPROACH": bool(acc("ff_retreat_keep_approach", False)),
            "FF_CARRY_REPLAN": bool(acc("ff_carry_replan", False)),
            "FF_FIX_STRANDING_GUARD": bool(acc("ff_fix_stranding_guard", False)),
        }, **other, raw={name: repr(getattr(cfv, name, None))
                         for name in URGENCY_SWITCHES + ("FF_FIX_STRANDING_GUARD",) + OTHER_SWITCHES}),
        "src_sha": _file_shas(repo, MVG_SHA_FILES),
        "schema": UD_SCHEMA,
        "kicks": rec["kicks"],
        "decisions": rec["decisions"],
        "fates": fates,
        "cmd_ctx": rec["cmd_ctx"],
        "rel_ctx": rec["rel_ctx"],
        "shadow_mismatch": rec["mismatch"],
        "timing": {
            "probe_ms_total": round(probe_ms, 3),
            "dp_inst_ms": round(rec["inst_ms"], 3),
            "ud_ms": round(rec["ud_ms"], 3),
            "kick_ms": round(rec["kick_ms"], 3),
            "mv_ms": round(rec["mv_ms"], 3),
            "u1_shadow_ms": round(rec["u1_shadow_ms"], 3),
            "u1_model_ms": 0.0,
            "fix_ms_total": {f: round(sum(v), 3) for f, v in rec["fix_calls"].items()},
            "fix_calls": rec["fix_calls"],
            "wall_s": wall_s,
            "process_s": None if process_s is None else round(process_s, 3),
            "probe_frac_of_wall": round(probe_ms / (float(wall_s) * 1000.0), 5) if wall_s else None,
        },
        "errors": rec["ud_errors"],
    }
    u1 = u1 or {}
    mvg = {
        "probe": VERSION,
        "probe_sha": probe_sha,
        "switches": dict({
            "FF_APPROACH_PATH": bool(acc("ff_approach_path", False)),
            "FF_RETREAT_KEEP_APPROACH": bool(acc("ff_retreat_keep_approach", False)),
            "FF_FIX_STRANDING_GUARD": bool(acc("ff_fix_stranding_guard", False)),
        }, **other, raw={name: repr(getattr(cfv, name, None)) for name in MVG_SWITCHES + OTHER_SWITCHES}),
        "src_sha": _file_shas(repo, MVG_SHA_FILES),
        "u1_shadow_sha": u1.get("sha"),
        "u1_shadow_path": u1.get("path"),
        "u1_shadow_error": u1.get("error"),
        "schema": MVG_SCHEMA + " | " + MV_SCHEMA,
        "guard": {"cols": list(GUARD_COLS), "rows": rec["guard_rows"]},
        "mp_mismatch": rec["mp_mismatch"],
        "replica": rec["replica"],
        "timing": {
            "guard_ms": rec["guard_ms"],
            "guard_calls": len(rec["guard_ms"]),
            "guard_ms_total": round(sum(rec["guard_ms"]), 3),
            "inst_guard_ms": rec["inst_guard_ms"],
            "inst_guard_calls": len(rec["inst_guard_ms"]),
        },
        "errors": rec["mvg_errors"],
    }
    return dp, ud, {"cols": list(MV_COLS), "rows": rec["mv_rows"]}, rec["mv_events"], mvg


def ff_log_rows(m):
    """The model's firefighting log (model._firefight_log), compact (FFLOG_COLS); bools normalised (a numpy bool
    would otherwise be written as a string)."""
    out = []
    for r in (getattr(m, "_firefight_log", None) or []) if m is not None else []:
        if not isinstance(r, dict):
            continue
        row = []
        for c in FFLOG_COLS:
            v = r.get(c)
            if c in ("engaged", "wrote", "scorched", "dry", "suspend_set") and v is not None:
                v = bool(v)
            row.append(v)
        out.append(row)
    return out


def dq_section(rec, ag, cfv, repo, probe_sha=None, r1=None):
    """d["dq"] (DQ_SCHEMA) from the record `install` filled. r1 = {"sha", "path", "error"} of the round-1 shadow."""
    m = rec["model"]
    r1 = r1 or {}

    def acc(name, default=None):
        f = getattr(ag, name, None)
        try:
            return f() if callable(f) else default
        except Exception as exc:  # recorded, not swallowed
            return "ERR %s" % type(exc).__name__

    t = rec["dq_ms"]
    return {
        "probe": VERSION,
        "probe_sha": probe_sha,
        "switches": {
            "raw": {name: repr(getattr(cfv, name, None)) for name in DQ_SWITCHES + MVG_SWITCHES},
            "joint_on": bool(acc("dispatch_joint", False)),
            "reassign_on": bool(acc("dispatch_reassign", False)),
            "S": acc("dispatch_stall_steps"),
            "M": acc("dispatch_margin_steps"),
            "P": acc("dispatch_margin_persist"),
            "FF_APPROACH_PATH": bool(acc("ff_approach_path", False)),
            "FF_RETREAT_KEEP_APPROACH": bool(acc("ff_retreat_keep_approach", False)),
            "FF_FIX_STRANDING_GUARD": bool(acc("ff_fix_stranding_guard", False)),
        },
        "src_sha": _file_shas(repo, DQ_SHA_FILES),
        "r1_shadow_sha": r1.get("sha"),
        "r1_shadow_path": r1.get("path"),
        "r1_shadow_error": r1.get("error"),
        "schema": DQ_SCHEMA + " | " + DP_J_SCHEMA,
        "sample": {"cols": list(SAMPLE_COLS), "unit_cols": list(SAMPLE_UNIT_COLS), "rows": rec["dq_sample"]},
        "ff_log": {"cols": list(FFLOG_COLS), "rows": ff_log_rows(m)},
        "zr1": rec["zr1"],
        "footprint": rec["fp"],
        "kick_gated": rec["kick_gated"],
        "timing": {"dq_ms_total": round(sum(t.values()), 3), **{k: round(v, 3) for k, v in t.items()}},
        "errors": rec["dq_errors"],
    }


# ------------------------------------------------------------------------------------------------- main
def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _dq_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args>", file=sys.stderr)
        return 2
    probe_args = argv[argv.index("--") + 1:]
    if "--repo" not in probe_args:
        print("DQ REFUSED: --repo is required (every layer defaults to the main checkout)", file=sys.stderr)
        return 3
    repo = probe_args[probe_args.index("--repo") + 1]
    out_path = probe_args[probe_args.index("--out") + 1]
    # the instrument that writes this record (d["dq"]["probe_sha"] = d["mvg"]["probe_sha"]), read before anything runs
    probe_sha = lf_sha256(os.path.abspath(__file__))
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    t_process = time.perf_counter()
    import agents as ag  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.adaptation_manager as amod  # noqa: E402
    import src_extension.adaptation.local_adaptation_generator as gen  # noqa: E402
    from src_extension.planning import fire_arrival_estimate as fae  # noqa: E402
    from src_extension.planning import movement_paths as mpm  # noqa: E402

    u1 = {"sha": None, "path": U1_SHADOW, "error": None}
    try:
        udm, u1["sha"] = load_u1_shadow(U1_SHADOW)
    except Exception as exc:  # recorded: the kick shadow (and 22.9's U1 class) is then not computed
        udm = None
        u1["error"] = repr(exc)[:300]
    r1 = {"sha": None, "path": R1_SHADOW, "error": None}
    try:
        r1m, r1["sha"] = load_r1_shadow(R1_SHADOW)
    except Exception as exc:  # recorded: the r1 footprint is then not computed
        r1m = None
        r1["error"] = repr(exc)[:300]

    rec = install(ag, cfv, wf, amod, gen, fae, udm, mpm, r1m)

    # A record already at --out (an earlier attempt's) is moved aside, never written into (as _dp_probe).
    if os.path.exists(out_path):
        n = 0
        while os.path.exists("%s.prev%d" % (out_path, n)):
            n += 1
        os.replace(out_path, "%s.prev%d" % (out_path, n))
    rc = None
    chain_exc = None
    try:
        ut = runpy.run_path(os.path.join(HERE, "_ut_probe.py"), run_name="ut_probe_module")
        sys.argv = [os.path.join(HERE, "_ut_probe.py")] + argv
        rc = ut["main"]()
    except BaseException as exc:  # noqa: BLE001 - the record is written whatever happened
        chain_exc = exc
        rc = 9
        print("DQ CHAIN RAISED %r" % (exc,), file=sys.stderr)
    finally:
        try:
            gc.callbacks.remove(rec["gc_cb"])
        except ValueError:
            pass
    process_s = time.perf_counter() - t_process

    try:
        wall_s = None
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as fh:
                d = json.load(fh)
            wall_s = d.get("wall_s")
        else:
            d = {"dp_only": True, "crashed": True}
        d["dp"], d["ud"], d["mv"], d["mv_events"], d["mvg"] = sections(rec, ag, cfv, wf, repo, rc, chain_exc, wall_s,
                                                                       process_s, u1, probe_sha)
        d["dq"] = dq_section(rec, ag, cfv, repo, probe_sha, r1)
        tmp = out_path + ".dqtmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"), default=str)
        os.replace(tmp, out_path)
    except Exception as exc:
        print("DQ WRITE FAILED %r" % (exc,), file=sys.stderr)
        return 8
    return rc


if __name__ == "__main__":
    sys.exit(main())
