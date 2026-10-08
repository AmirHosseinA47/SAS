"""MVG round analyzer - PRE-REGISTERED (outputs/urgency_part1d.txt 1d.2-1d.9 and amendment C1, 1d.13; the urgency
round's outputs/urgency_part1.txt 15-17 and 22-25 where Part 1d says "as this round"). A port of
urgency:outputs/_ud_analyze.py (5dba5bcb) to the guarded movement screen of 1d.5: arms 0 (mvg0, today's code), G (mvg1,
fixes (a) + (b) with the stranding guard at its default, 1) and N (mvg2, the fixes with FF_FIX_STRANDING_GUARD = 0;
REPORT-ONLY, never gating and never shipping).

READ-ONLY. It reads run files from E:/Projects/SAS_wt/mvg/outputs (or --smoke DIR), the references in
outputs/_mvg_ref/ (sha256 manifest), the W3 replays in outputs/_mvg_w3/ and git objects of this repository, and writes
nothing but --out. Every decision function is pure and is checked on hand-built records by
outputs/_mvg_analyze_selftest.py, which must pass before any real run is read.

usage (mvg worktree root, E:/Projects/SAS/.venv/Scripts/python.exe):
  python outputs/_mvg_analyze.py --head SHA --part2-notes PATH [--out REPORT] [--allow-incomplete | --zeros-only]
  python outputs/_mvg_analyze.py --smoke DIR --smoke-files ARM=FILE[,ARM=FILE...] [--smoke-cell set1/ring/A_N]
                                 [--out REPORT] [--zeros-only]
  --head SHA          the Part 2d commit. THE HEAD RULE (review A-2, rule (a); head_rule): a run is valid when its
                      recorded head starts with SHA, OR its recorded head is an ANCESTOR of SHA (git merge-base
                      --is-ancestor) and every RUN-LOADED file is byte-identical (LF-normalised) between the two commits
                      (run_loaded_changes): every tracked *.py at the repository root, everything under src_extension/,
                      and the outputs/ tooling the probe chain loads, RUN_LOADED_TOOLING (derived from the code:
                      _mvg_probe.py runpy-runs _ut_probe.py -> _fb3_probe.py -> _fx3_probe.py -> _mf2_probe.py ->
                      _sd_probe.py; _fb3_probe.py loads _fm2_probe_harness.py (which runpy-runs _ffr_harness.py) and
                      _bp_inst.py by path; _mvg_probe.py loads the U1 copy _mvg_u1_shadow.py by path; _ffr_harness.py
                      imports _dim_hooks.py with a --dim-* option only - no frozen line passes one; listed
                      conservatively), plus outputs/_mvg_replay.py for a W3 replay. INVALID otherwise. Every source
                      sha the run recorded (dp.src_sha, ud.src_sha, mvg.src_sha, and mvg.u1_shadow_sha of the
                      instrument-only U1 copy) must equal the file at SHA, LF or CRLF form (INVALID otherwise: 'ran
                      uncommitted source'), and so must the instrument itself (review I-9): mvg.probe_sha is the
                      LF-normalised sha256 of outputs/_mvg_probe.py at SHA, and a W3 replay's boards file carries
                      replay_sha / probe_sha = those of outputs/_mvg_replay.py / outputs/_mvg_probe.py at SHA. SHA must
                      descend from the base a20a2ef5 (1d.7)
  --part2-notes PATH  the Part 2d notes: every '<sha256> <outputs/...>' line is verified against the file on disk; the
                      tooling files, the frozen queues (W1, W2, port, smoke, structure) and the mutation record
                      (outputs/_mvg_mutants_result.txt / .json) must be listed. REFUSED on any mismatch. The mutation
                      record is then checked against SHA (review C-1; mutants_check): every file sha its JSON binds
                      (sha256.files, sha256.specs, sha256.engine) must be that file at SHA (LF or CRLF form of the
                      committed blob) and no bound file may have changed during the check - REFUSED otherwise (a
                      record computed on another tree is no evidence for this one).
  --zeros-only        the wave check (1d.9; 1d.13.3: every 20-30 minutes during W1-W3): sections 0-3 and the W3
                      validity, then stop - no outcome section, no verdict, and no outcome VALUE in a zero failure line
                      (field paths only, numbers masked)
  without --allow-incomplete a missing or INVALID run, or a W3 that is not complete, stops the analysis after section 3
                      and the W3 validity (no outcome is printed)
  --allow-incomplete  compute on what exists; the reading is PROVISIONAL, and while W3 is incomplete NO VERDICT is
                      printed at all (1d.13.3)
  --smoke DIR         one cell from DIR (any of sets 1-6, --smoke-cell): ARM in ref (its ud0 record in
                      outputs/_mvg_ref/, for the Z0 smoke), 0, G, N; relaxed validity (no queue, no 360-step, no head
                      checks; an urgency ud_probe v2 record is accepted in DRY mode, read without guard material); the
                      cell stands in for the fresh set 5 (set 6 empty). SMOKE - NOT A SCREEN: it prints sections 0-3,
                      the STRUCTURE counts of 1d.8 (9) (admitted and vetoed (a) / (b) decisions, the guard's and the
                      probe's in-run cost) and each comparison's S6 cost line; every outcome section is suppressed.
exit: 0 report written; 1 STOP (S1 identity failed, an arm-0 failure - 1d.6.2; nothing else is read); 2 REFUSED (a
hashed text differs, a reused function or module is not the committed one, the Part 2d notes differ, the mutation record
is not bound to --head, the seeds file is unusable, a run's scenario / wind / seed is not its frozen cell, or the W3
queue is not what the frozen rule gives on the W2 records).
HASHED SECTIONS (1d.8 (6); hash_checks): 1d.2-1d.9 run to the '1d.10 WHAT THIS MEANS' header; 1d.13 runs to the next
round-section header - the first later line matching '^1d\\.\\d+ [A-Z]' (a later amendment, e.g. '1d.14 ...') - or EOF,
trailing blank and '=' banner lines dropped (review A-1): an appended amendment leaves 1d.13's text unchanged, an edit
inside it is REFUSED.
W3 GENERATION (review A-4): outputs/_mvg_w3_queue.py build calls w2_gate() with its own --head and --part2-notes - the
header checks of section 0 and section 1's validity of all 192 W2 records exactly as here - and refuses unless every
W2 record is present and valid.

SECTIONS
  0 HEADER        commits 74039c54 (Part 1d; 1d.0-1d.12 frozen), 0d5358e3 (amendment C1, 1d.13), a20a2ef5 (the base),
                  HEAD and --head (the Part 2d commit); the hash checks of 1d.2-1d.9 (against 74039c54) and 1d.13
                  (against 0d5358e3); the DPR functions verbatim from cc8d653c and the ud functions this port keeps
                  verbatim from 5dba5bcb; the reused modules byte-identical to cc8d653c's; the Part 2d notes; the seeds
                  (1d.4's rule recomputed for sets 1-6; sets 1-4 = the urgency round's frozen _ud_seeds.txt).
  1 LOAD + PROV   validity per run: INVALID (tooling: the run line, the instrument version, an instrument error, the
                  guard record's own bookkeeping, the _survival_move replica disagreeing with the model, uncommitted
                  source), GATE FAILURE (Z6 in G / N - never INVALID), STOP (an arm-0 crash).
  2 S1 IDENTITY   Z0 (W1): mvg0 on sets 1-2 == outputs/_mvg_ref/_sd_ud0* on DPR's G-ID fields (as ud0 vs dpR), with
                  dp0's M8 reproduced; the PORT IDENTITY (1d.8 (11)): mvg2 on the 8 set-3 ring cells ==
                  outputs/_mvg_ref/_sd_ud2r3_* on 16.7's fields. Code identity only: no outcome value is printed.
  3 ZEROS         1d.6.2: arm-0 failures (Z0, Z5, Z-RB, a crash, a shadow mismatch: STOP); movement-owned Z1-M Z2-M Z-RB
                  Zm-a Zm-b Z-S in G AND N; guard-owned Zg-1 (two-sided) Zg-2 Zg-3 in G; shared Z5 Z6.
  W3 VALIDITY     1d.13.2-1d.13.3: the W3 queue and candidates re-derived from the W2 records by the frozen rule of
                  outputs/_mvg_w3_queue.py; every replay present and valid; every R0 checked against its W2 record.
  4 COMPARISONS   FULL(0 -> G) - THE DECISION (1d.6.1) - with S5 = F1 read as R2 (1d.3.3), L2, L3, L4 (1d.13.2) and
                  the 24 sign-tested counts with Holm; REPORTED: FULL(0 -> N) and HARMLESS(N -> G).
  5 M8 + 22.9     M8, M8-D and the frozen attribution classes per arm and fresh set (the U1 class from the
                  instrument's U1 shadow, 1d.8 (5)).
  6 MEASURES/DIAG 1d.6.5: the urgency round's reported measures (M2, MU1, the ACTED footprint, DIAG, G-L / G-N,
                  6.R1-6.R4) and the guard's (6.G): decisions where a fix would act / admitted / vetoed, legs with a
                  veto by outcome and length, admit / veto alternations and revisits on an unchanged digest, the
                  POST-VETO DIAG (G against N), DIAG of every cell where G is worse than 0 or than N.
  7 W3 / L4       the per-death attribution (1d.13.2): CAUSED and PREVENTED for G (gating) and N (reported), pooled
                  and per set; the run-level variant, KO-LAST, KO-GUARD, review 1.3's classes, downstream candidates
                  and the same-step deaths with the C-NONE check - all reported.
  8 DECISION      1d.6.3's outcomes 1-6 on FULL(0 -> G); the per-switch rule; the scenario STOP as a diagnostic.
Conventions (as _ud_analyze): rows_* index t = the state after step t + 1; detection steps from <out minus
.json>.stdout.txt '[Victim Detection]' lines; a victim's death step = the first rows_vic managed 'dead', a unit's the
first rows_ff dead flag. d["mv"] step = the advance's step (rows_ff index + 1). No outcome of seed sets 1-4 is printed
anywhere (1d.9: no movement outcome on sets 1-4 is read in this round): sections 4-8 read the fresh sets 5-6 only.
Reused, imported unchanged: _sd_analyze.analyze (I2 / I6), _fb3_analyze searcher_o / ff_episodes, _fx3_pockets (via
searcher_o), _ut_analyze._last_detection, _ut_analyze2.ff_status_track, _fx3r_analyze FIELDS / DET_RE,
_fb3_queue.cells, _mf2_pool.signature; and outputs/_mvg_w3_queue.py's pure rule functions (compact, build_plan).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import inspect
import json
import math
import os
import random
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = r"E:\Projects\SAS_wt\mvg"
OUT_DIR = os.path.join(WT, "outputs")
REF_DIR = os.path.join(OUT_DIR, "_mvg_ref")
sys.path.insert(0, HERE)
_ARGV = sys.argv
sys.argv = _ARGV[:1]                       # _fb3_analyze / _ut_analyze* read sys.argv at import
try:
    import _fx3r_analyze as R              # noqa: E402  FIELDS, DET_RE
    import _fb3_analyze as A               # noqa: E402  searcher_o, ff_episodes, det_times
    import _sd_analyze as SD               # noqa: E402  analyze()
    import _ut_analyze as U                # noqa: E402  _last_detection
    import _ut_analyze2 as U2              # noqa: E402  ff_status_track
    import _fb3_queue as FQ                # noqa: E402  cells
    import _mf2_pool as POOL               # noqa: E402  signature
    import _mvg_w3_queue as W3Q            # noqa: E402  the frozen W3 rule (1d.13.2): compact, build_plan
finally:
    sys.argv = _ARGV

PART1D, AMEND_C1, BASE = "74039c54", "0d5358e3", "a20a2ef5"
URGENCY_CODE = "5dba5bcb"                  # urgency Part 2's code commit: the analyzer ported here; its _ud_seeds.txt
DISPATCH = "cc8d653c4a5740c0f04a9e94d6ff48e92a0ca027"
REUSED_MODULES = ("_fx3r_analyze.py", "_fb3_analyze.py", "_sd_analyze.py", "_ut_analyze.py", "_ut_analyze2.py",
                  "_fx3_pockets.py", "_mf2_p3_analyze.py", "_fb3_queue.py", "_mf2_pool.py")
# 1d.8 (6): the sections of this round's pre-registration whose text must not change after data - 1d.2-1d.9 as frozen
# at 74039c54 (and as carried by the amendment commit 0d5358e3), 1d.13 as committed at 0d5358e3. 1d.13 ends at the next
# ROUND-section header ('1d.14 ...' of a later amendment; review A-1), else EOF - never at a top-level 'N. ' header,
# which this document does not use
ROUND_SECTION_RE = re.compile(r"^1d\.\d+ [A-Z]")
HASHED = (("1d.2-1d.9", PART1D, "1d.2 THE STRANDING GUARD", "1d.10 WHAT THIS MEANS"),
          ("1d.2-1d.9", AMEND_C1, "1d.2 THE STRANDING GUARD", "1d.10 WHAT THIS MEANS"),
          ("1d.13", AMEND_C1, "1d.13 AMENDMENT C1", ROUND_SECTION_RE))
NOTES_REQUIRED = ("outputs/_mvg_probe.py", "outputs/_mvg_u1_shadow.py", "outputs/_mvg_replay.py",
                  "outputs/_mvg_probe_check.py", "outputs/_mvg_analyze.py", "outputs/_mvg_analyze_selftest.py",
                  "outputs/_mvg_queue.py", "outputs/_mvg_w3_queue.py", "outputs/_mvg_q_w1.jsonl",
                  "outputs/_mvg_q_w2.jsonl",
                  # Part 2d's own frozen queues (review A-3): the port identity runs are validated against
                  # _mvg_q_port.jsonl; the smoke and the structure check are frozen the same way
                  "outputs/_mvg_q_port.jsonl", "outputs/_mvg_q_smoke.jsonl", "outputs/_mvg_q_structure.jsonl",
                  # the mutation record (review C-1): its bound shas are checked against --head (mutants_check)
                  "outputs/_mvg_mutants_result.txt", "outputs/_mvg_mutants_result.json",
                  # the chain _mvg_probe.py loads (runpy: _ut_probe -> _fb3_probe -> _fx3_probe -> _mf2_probe ->
                  # _sd_probe; _fb3_probe -> _fm2_probe_harness (-> _ffr_harness) and _bp_inst), the frozen seed and
                  # reference lists, the pool, and the mutation / guard tooling
                  "outputs/_ut_probe.py", "outputs/_fb3_probe.py", "outputs/_fx3_probe.py", "outputs/_mf2_probe.py",
                  "outputs/_sd_probe.py", "outputs/_fm2_probe_harness.py", "outputs/_ffr_harness.py",
                  "outputs/_bp_inst.py", "outputs/_mf2_pool.py", "outputs/_mvg_seeds.txt",
                  "outputs/_mvg_ref/_MANIFEST.sha256", "outputs/_mvg_mutants.py", "outputs/_mvg_mutants_mv.py",
                  "outputs/_mvg_guard_diag.py", "outputs/_mvg_make_guard_corpus.py")
MUTANTS_JSON = "outputs/_mvg_mutants_result.json"
MUTANTS_ENGINE = "outputs/_mvg_mutants.py"
# THE HEAD RULE's run-loaded files (review A-2, rule (a)): a run made at an ANCESTOR of --head is valid only when these
# are byte-identical (LF-normalised) between its head and --head. Derived from the code of the probe chain:
# _mvg_probe.py loads _mvg_u1_shadow.py by path and runpy-runs _ut_probe.py, which runs _fb3_probe.py, which loads
# _fm2_probe_harness.py (it runpy-runs _ffr_harness.py) and _bp_inst.py by path and runs _fx3_probe.py -> _mf2_probe.py
# -> _sd_probe.py; _ffr_harness.py imports _dim_hooks.py only with a --dim-* option (no frozen line passes one: listed
# conservatively). The repository side: every tracked *.py at the root (agents, wildfire_model, common_fixed_variables,
# evaluate_scenarios, serve_dashboard, ...) and everything under src_extension/ (git pathspecs).
RUN_LOADED_REPO = (":(glob)*.py", "src_extension")
RUN_LOADED_TOOLING = ("outputs/_mvg_probe.py", "outputs/_mvg_u1_shadow.py", "outputs/_ut_probe.py",
                      "outputs/_fb3_probe.py", "outputs/_fx3_probe.py", "outputs/_mf2_probe.py", "outputs/_sd_probe.py",
                      "outputs/_fm2_probe_harness.py", "outputs/_ffr_harness.py", "outputs/_bp_inst.py",
                      "outputs/_dim_hooks.py")
RUN_LOADED_REPLAY = ("outputs/_mvg_replay.py",)          # a W3 replay line wraps the probe in the replay tool
PROBE_REL, REPLAY_REL = "outputs/_mvg_probe.py", "outputs/_mvg_replay.py"
# the instrument version the SCREEN reads; a urgency ud_probe v2 record is readable in --smoke only (DRY: no guard)
MVG_PROBE = "mvg_probe v1"
UD_PROBE_DRY = "ud_probe v2"
U1_SHADOW_REL = "outputs/_mvg_u1_shadow.py"
MVG_SRC_REQUIRED = ("agents.py", "wildfire_model.py", "common_fixed_variables.py",
                    "src_extension/planning/movement_paths.py", "src_extension/planning/fire_arrival_estimate.py")
H = 360
STUCK, WIN = 20, 30                        # _sd_analyze I2 thresholds (as _dp_analyze)
ALPHA = 0.05
F1_ALPHA = 0.05                            # 1d.3.3 (ii): a set fails when its exact one-sided sign test gives p <= 0.05
EXPECTED_BASES = {"set1": 9601, "set2": 9621, "set3": 573001, "set4": 780001, "set5": 135961, "set6": 287041}
FRESH = ("set5", "set6")
IN_SAMPLE = ("set1", "set2")               # the W1 identity sets (switch 0): no outcome of theirs is printed
WINDS = (("N", "north"), ("S", "south"), ("E", "east"), ("W", "west"))
PLACES = (("r", "ring", 0), ("u", "uniform", 1))
ARMS = ("0", "G", "N")
ARM_TAG = {"0": "mvg0", "G": "mvg1", "N": "mvg2"}
ARM_SW = {"0": set(), "G": {"MOV", "GUARD"}, "N": {"MOV"}}
PORT_KEYS = ("A_N", "A_W", "B_S", "B_W", "C_N", "C_S", "C_W", "D_N")   # 1d.8 (11): set 3 ring (_mvg_queue port-verify)
COMPARISONS = (("0", "G"), ("0", "N"), ("N", "G"))
ADDED = {("0", "G"): {"MOV", "GUARD"}, ("0", "N"): {"MOV"}, ("N", "G"): {"GUARD"}}
# 3.1 / section 3: dp0's M8 per set (FC, futile) - mvg0 reproduces it through ud0 (urgency 16.7 Z0)
DP0_M8 = {"set1": (4, 1), "set2": (7, 1)}
J_ONLY = ("probe", "switches", "src_sha", "j_calls", "j_events", "ledger", "timing", "rc_chain", "j_detail",
          "j_timing")
TERMINAL = ("rescued", "dead", "unreachable")
DISPATCH_RE = re.compile(r"^\[Dispatch\] FF-(\S+) assigned to (\S+) reason=(\S+) manhattan_dist=(\S+)")
STEP_RE = re.compile(r"\bstep=(\d+)")
TRIAGE_TAG = "[UrgencyTriage]"
NEW_TAGS = (TRIAGE_TAG,)                   # 16.7: stdout compared with the urgency round's new tag stripped (none here)
VDEAD_RE = re.compile(r"^\[RescueEvent\] type=victim_dead victim=(\S+)")
ROW_KINDS = ("rows_ff", "rows_vic", "rows_uav", "rows_dec", "rows_trig")
# d["mv"] columns: ud_probe v2's 38 plus the guard's four (mvg_probe v1, MV_SCHEMA)
MV_COLS = ("step", "unit", "victim", "leg", "branch", "pre", "post", "target", "digest",
           "st_pre", "st_post", "tier", "mt", "rb_call", "rb_set",
           "trig", "zrb", "today", "fa", "fb", "fbB", "fc", "acted",
           "dc", "dcx", "df", "dm", "dr", "gesc",
           "cls_pre", "cls_post", "fd_pre", "fd_post", "c1_pre", "c1_post",
           "fix_ms", "inst_ms", "dcb",
           "gA", "gB", "veto", "acted_g")
MV_COLS_DRY = MV_COLS[:38]                 # a ud_probe v2 record (smoke DRY mode only)
# d["mvg"]["guard"] columns (mvg_probe v1, MVG_SCHEMA): c / T_v / admit = the INSTRUMENT's verdict, the frozen-function
# replica's (review I-1); mp_verdict = [admit, c, T_v] of the repo function movement_paths.stranding_guard on the same
# arguments, a cross-check that must equal them (Zg-1 fails on a difference)
GUARD_COLS = ("step", "unit", "victim", "kind", "u", "n", "v", "today", "today_kind", "today_tier", "today_raise",
              "c", "T_v", "admit", "model_admit", "model_verdict", "model_cell", "took", "post", "tier", "raise",
              "pre_writes", "pred_writes", "post_writes", "ms_guard", "ms_inst", "row", "mp_verdict")
# the pre-advance (decision-time) fields of a d["mv"] row: the shadow agreement of Z1-M (iii) and Zg-3, the instrument's
# guard verdicts included
SHADOW_FIELDS = ("step", "unit", "victim", "leg", "pre", "target", "digest", "st_pre", "trig", "zrb", "today", "fa",
                 "fb", "fbB", "fc", "acted", "dc", "dcx", "df", "dm", "dr", "gesc", "cls_pre", "fd_pre", "c1_pre",
                 "dcb", "gA", "gB", "acted_g")
FIX_BRANCHES = ("approach_a", "retreat_b")             # a fix's step TAKEN (guard off, or admitted)
VETO_BRANCHES = ("approach_a_veto", "retreat_b_veto")  # a fix would have acted, the model's guard vetoed: today's step
FIX_TIER = {"a": 7, "b": 10}
EXCLUDED_CARRY = ("c2s", "c3")             # 22.8.3's designed-behaviour exclusion: VOID here (no fix (c), 1d.6.1 S5)
# shadow_mismatch texts of the probe's guard checks (Zg-1 in G)
GUARD_TEXTS = ("guard vetoes (instrument), model did not take today's step", "model guard verdict != instrument verdict",
               "guard evaluated on a cell other than the shadow's", "model guard call where the shadow did not act")
I2_KINDS = (("stuck_approach", "I2_ff_stuck_approach"), ("stuck_carry", "I2_ff_stuck_carry"),
            ("livelock_approach", "I2_ff_livelock_approach"), ("livelock_carry", "I2_ff_livelock_carry"),
            ("noprog_approach", "I2_ff_no_progress_approach"))
# 23.2 as 1d.6.1 S5: the 24 sign-tested counts, family order (F2, F3, F4 x 7, F5 x 13, F6, F8)
SIGN_KEYS = (
    ("never_detected", "F2 never-detected"),
    ("never_finish", "F3 runs that never finish"),
    ("os_broad_before", "F4 searcher broad (O) before the last detection"),
    ("os_broad_after", "F4 searcher broad (O) after it"),
    ("os_pocket_near", "F4 searcher pocket near a depot (r 5)"),
    ("os_pocket_any", "F4 searcher pocket anywhere (r 500)"),
    ("os_i2_livelock", "F4 searcher I2 LIVELOCK"),
    ("os_rtb_noprog", "F4 searcher RTB no-progress"),
    ("os_i2_stuck", "F4 searcher I2 STUCK"),
    ("of_broad", "F5 broad positional"),
    ("of_stuck_approach", "F5 I2 STUCK approach"),
    ("of_stuck_carry", "F5 I2 STUCK carry"),
    ("of_livelock_approach", "F5 I2 LIVELOCK approach"),
    ("of_livelock_carry", "F5 I2 LIVELOCK carry"),
    ("of_noprog_approach", "F5 I2 NO-PROGRESS approach"),
    ("leg_cycle_approach", "F5 CYCLE approach (legs)"),
    ("leg_cycle_carry", "F5 CYCLE carry (legs)"),
    ("leg_osc_approach", "F5 OSCILLATION approach (legs)"),
    ("leg_osc_carry", "F5 OSCILLATION carry (legs)"),
    ("leg_prog_approach", "F5 PROGRESS approach (legs)"),
    ("leg_prog_carry", "F5 PROGRESS carry (legs)"),
    ("leg_noprog_carry", "F5 carry NO-PROGRESS (legs)"),
    ("latch_episodes", "F6 latch episodes"),
    ("escape_writeoffs_det", "F8 escape-sweep write-offs of detected victims"),
)
assert len(SIGN_KEYS) == 24
MOV_ZEROS = ("Z1-M", "Z2-M", "Z-RB", "Zm-a", "Zm-b", "Z-S")
GUARD_ZEROS = ("Zg-1", "Zg-2", "Zg-3")
SHARED_ZEROS = ("Z5", "Z6")
ZERO_ORDER = ("Z1-M", "Z2-M", "Z5", "Z6", "Z-RB", "Zm-a", "Zm-b", "Z-S", "Zg-1", "Zg-2", "Zg-3", "SM")
POST_VETO_WINDOW = 6                       # 1d.6.5: within 6 steps after a veto (as 22.2.4's DIAG)

_LINES: list[str] = []


def out(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    _LINES.append(s)


def head(title):
    out("=" * 118)
    out(title)


# ================================================================================================ DPR functions,
# replicated VERBATIM from dispatch:outputs/_dp_analyze.py at cc8d653c (checked at start-up: verbatim_check)
def same_path(a, b):
    if not a or not b:
        return False
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def q(xs, f):
    """_fb3_analyze's percentile rule: sorted(xs)[min(n - 1, int(f * n))]."""
    return sorted(xs)[min(len(xs) - 1, int(f * len(xs)))] if xs else None


def iqr(xs):
    if not xs:
        return None, None, None
    if len(xs) == 1:
        return xs[0], xs[0], xs[0]
    q1, q2, q3 = statistics.quantiles(xs, n=4, method="inclusive")
    return q1, statistics.median(xs), q3


def fmt(v, f="%.2f"):
    return "n/a" if v is None else (f % v)


def stdout_path(path):
    return path[:-5] + ".stdout.txt" if path.endswith(".json") else path + ".stdout.txt"


def parse_stdout(path):
    """(first detection step per victim, ordered [Dispatch] lines with the last step= marker seen before each)."""
    det, disp, last_step = {}, [], None
    p = stdout_path(path)
    if not os.path.exists(p):
        return None, []
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            m = R.DET_RE.match(s)
            if m and m.group(3) not in det:
                det[m.group(3)] = int(m.group(1))
            m2 = DISPATCH_RE.match(s)
            if m2:
                disp.append((last_step, m2.group(1), m2.group(2), m2.group(3), m2.group(4)))
            m3 = STEP_RE.search(s)
            if m3:
                last_step = int(m3.group(1))
    return det, disp


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_run(path):
    d = load_json(path)
    det, disp = parse_stdout(path)
    d["_det"] = det or {}
    d["_det_file"] = det is not None
    d["_disp"] = disp
    return d


def first_path(x, y, path=""):
    """_bp_analyze.first_path (replicated): the first differing leaf."""
    if x == y:
        return None
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y), key=str):
            if k not in x or k not in y:
                return "%s.%s (only in %s)" % (path, k, "first" if k in x else "second")
            p = first_path(x[k], y[k], "%s.%s" % (path, k))
            if p:
                return p
        return path + " (?)"
    if isinstance(x, list) and isinstance(y, list):
        for i in range(min(len(x), len(y))):
            p = first_path(x[i], y[i], "%s[%d]" % (path, i))
            if p:
                return p
        return "%s (length %d != %d)" % (path, len(x), len(y))
    return "%s: %s != %s" % (path, repr(x)[:70], repr(y)[:70])


def first_div(a, b):
    """(index, item_a, item_b) of the first difference of two sequences, or None when equal."""
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i, a[i], b[i]
    if len(a) != len(b):
        i = min(len(a), len(b))
        return i, (a[i] if i < len(a) else None), (b[i] if i < len(b) else None)
    return None


def hashes(rows):
    return [hashlib.sha1(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()[:12] for r in rows]


def outside_events(x, b, o1, rb_bound, ff_dead, ff_rb_steps):
    """Outside events (14.6 G-T(a); 6.9 o1 / o2 / o3) of the intermediate binder X = x[3] on victim x[4], between its
    bind x and the return b. o1 = a route_blocked-handler unassign of (X, v) (reason containing 'replacement' and
    'blocked'); o2 = X route_blocked while bound to v in the per-step binder rows (sampled after J-post, so a sample at
    the return step itself is after the return unless the return was in the sweep phase); o3 = X dead in rows_ff.
    o2@frame - the one same-frame blind spot of the after-J-post sample: a LATCH-FILL return (reason
    joint_replace_latched) at J-post of the step in whose advance X latched; rows_ff at that step shows X
    route_blocked (the release leaves the flag for the next revalidation, design 7.1 step 3)."""
    xi, xstep, X, v = x[0], x[1], x[3], x[4]
    i, step, phase, reason = b[0], b[1], b[2], b[5]
    found = []
    if any(xi < k < i for k in o1.get((X, v), ())):
        found.append("o1")
    last_sample = step if phase == "sweep" else step - 1
    if any(xstep <= s <= last_sample for s in rb_bound.get((X, v), ())):
        found.append("o2")
    elif reason == "joint_replace_latched" and phase == "post" and step in ff_rb_steps.get(X, ()):
        found.append("o2@frame")
    dstep = ff_dead.get(X)
    if dstep is not None and xstep <= dstep <= (step - 1 if phase == "pre" else step):
        found.append("o3")
    return found


def gt_returns(cmds, binders, ff_dead, ff_rb_steps):
    """G-T: every RETURN reconstructed from the successful assign commands of dp.commands - A..X..A on a victim
    (A bound v before and v's last binder is X != A) or v..w..v on a unit (u bound v before and u's last bind was to
    another victim) - each counted once, with X = v's binder immediately before the return (u itself for a pure unit
    return) and X's outside events. cmds: [[step, phase, action, victim, unit, reason, success, ...]]; binders:
    [[step, [[victim, [[unit, status], ...]], ...]]]; ff_dead {unit: first dead step}; ff_rb_steps {unit: {steps with
    status route_blocked in rows_ff}}."""
    rb_bound = collections.defaultdict(set)
    for step, lst in binders or ():
        for vid, bl in lst:
            for uid, st in bl:
                if str(st).lower() == "route_blocked":
                    rb_bound[(uid, vid)].add(step)
    binds = []
    o1 = collections.defaultdict(list)
    for i, c in enumerate(cmds or ()):
        step, phase, action, vid, uid, reason, ok = c[:7]
        if not ok:
            continue
        reason = str(reason or "")
        if action == "assign":
            binds.append((i, step, phase, uid, vid, reason))
        elif action == "unassign" and "replacement" in reason and "blocked" in reason:
            o1[(uid, vid)].append(i)
    returns = []
    on_v = collections.defaultdict(list)
    of_u = collections.defaultdict(list)
    for b in binds:
        _i, step, phase, uid, vid, reason = b
        prev_v, prev_u = on_v[vid], of_u[uid]
        if any(p[3] == uid for p in prev_v):
            x = prev_v[-1]
            v_ret = x[3] != uid
            u_ret = bool(prev_u) and prev_u[-1][4] != vid
            if v_ret or u_ret:
                ev = outside_events(x, b, o1, rb_bound, ff_dead, ff_rb_steps)
                returns.append({"step": step, "phase": phase, "victim": vid, "unit": uid, "reason": reason,
                                "X": x[3], "x_step": x[1], "kind": "victim" if v_ret else "unit", "outside": ev})
        prev_v.append(b)
        prev_u.append(b)
    return returns


def m8_classify(entries):
    """11.6 / 14.7 M8: each detected-victim death (a dp.m8 entry with a death_step) is FEASIBLE-CRITICAL iff min_d + 1
    <= death step - detection step, else FUTILE. Returns (feasible-critical, futile, rows)."""
    fc = fu = 0
    rows = []
    for e in entries:
        det, dth, md = e.get("detection_step"), e.get("death_step"), e.get("min_d")
        if dth is None:
            continue
        feas = md is not None and det is not None and md + 1 <= dth - det
        fc += feas
        fu += not feas
        rows.append((e.get("victim"), det, dth, md, "FEASIBLE-CRITICAL" if feas else "FUTILE"))
    return fc, fu, rows


def ident_diff(a, b, smoke):
    """G-ID (14.6) rule for one cell: _fx3r_analyze FIELDS + every mf2 section but probe + every dp field that exists
    without J (all dp keys but J_ONLY). Returns (differing fields, note, other sections differing - not gated)."""
    diff = [k for k in R.FIELDS if a.get(k) != b.get(k)]
    for k in sorted(set(a.get("mf2") or {}) | set(b.get("mf2") or {})):
        if k != "probe" and (a.get("mf2") or {}).get(k) != (b.get("mf2") or {}).get(k):
            diff.append("mf2." + k)
    note = ""
    da, db = a.get("dp"), b.get("dp")
    if isinstance(da, dict) and isinstance(db, dict):
        for k in sorted((set(da) | set(db)) - set(J_ONLY)):
            if da.get(k) != db.get(k):
                diff.append("dp." + k)
    elif smoke and not isinstance(da, dict) and isinstance(db, dict):
        note = "reference has no dp section (smoke file older than the instrument) - dp fields not compared"
    else:
        diff.append("dp (missing in %s)" % ("both" if not isinstance(da, dict) and not isinstance(db, dict) else
                                           "the reference" if not isinstance(da, dict) else "dp0"))
    other = []
    for sec in ("fb3", "fx3", "ut", "mr"):
        sa, sb = a.get(sec), b.get(sec)
        if isinstance(sa, dict) and isinstance(sb, dict):
            other += ["%s.%s" % (sec, k) for k in sorted(set(sa) | set(sb)) if k != "probe" and sa.get(k) != sb.get(k)]
        elif sa != sb:
            other.append(sec)
    return diff, note, other


def field_get(d, f):
    if f.startswith("mf2."):
        return (d.get("mf2") or {}).get(f[4:])
    if f.startswith("dp."):
        return (d.get("dp") or {}).get(f[3:])
    return d.get(f.split(" ")[0])


def ff_state(r):
    """G-OF 21.2(f) unit state of one rows_ff row: carry (exiting), approach (bound, incl. a latched binder),
    rb_unbound (route_blocked, unbound), idle (otherwise)."""
    if r[5]:
        return "carry"
    if r[8]:
        return "approach"
    if str(r[3]) == "route_blocked":
        return "rb_unbound"
    return "idle"


def cell_means(pairs):
    """{cell: [delta, ...]} -> {cell: m_c} for cells with at least one pair (14.7 M1)."""
    return {c: sum(v) / len(v) for c, v in pairs.items() if v}


def drop_most_negative(vals):
    if not vals:
        return []
    v = sorted(vals)
    return v[1:]


def wilcoxon(xs):
    """Two-sided Wilcoxon signed-rank test of median 0 (zeros dropped, tied |d| averaged); exact for n <= 25 without
    ties, else the normal approximation with tie and continuity corrections. Reported, never gated (14.7 M1)."""
    d = [x for x in xs if x != 0]
    n = len(d)
    if n == 0:
        return {"n": 0, "w_plus": 0.0, "w_minus": 0.0, "p": None, "method": "no non-zero values"}
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    ties = []
    while i < n:
        j = i
        while j + 1 < n and round(abs(d[order[j + 1]]), 9) == round(abs(d[order[i]]), 9):
            j += 1
        r = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = r
        if j > i:
            ties.append(j - i + 1)
        i = j + 1
    wp = sum(r for r, x in zip(ranks, d) if x > 0)
    wm = n * (n + 1) / 2.0 - wp
    if n <= 25 and not ties:
        counts = [0] * (n * (n + 1) // 2 + 1)
        counts[0] = 1
        for r in range(1, n + 1):
            for s in range(len(counts) - 1, r - 1, -1):
                counts[s] += counts[s - r]
        total = float(2 ** n)
        w = int(round(wp))
        lo = sum(counts[:w + 1]) / total
        hi = sum(counts[w:]) / total
        return {"n": n, "w_plus": wp, "w_minus": wm, "p": min(1.0, 2 * min(lo, hi)), "method": "exact"}
    mu = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0 - sum(t ** 3 - t for t in ties) / 48.0
    if var <= 0:
        return {"n": n, "w_plus": wp, "w_minus": wm, "p": None, "method": "degenerate"}
    z = (wp - mu - math.copysign(0.5, wp - mu)) / math.sqrt(var) if wp != mu else 0.0
    return {"n": n, "w_plus": wp, "w_minus": wm, "p": math.erfc(abs(z) / math.sqrt(2)), "method": "normal z=%.3f" % z}


def wil_str(w):
    return "n=%d W+=%.1f W-=%.1f p=%s (%s)" % (w["n"], w["w_plus"], w["w_minus"], fmt(w["p"], "%.4f"), w["method"])


RB_CUT_PHASES = ("pre", "advance", "post")


def rb_cut_refusals(cmds):
    """A2 22.2: successful assigns stamped init or sweep. The sample cut cannot place them, so a run with one is
    REFUSED as a tooling defect. Rows [step, phase, victim, unit, reason]."""
    return [[c[0], c[1], c[3], c[4], c[5]] for c in cmds or () if c[2] == "assign" and c[6]
            and c[1] not in RB_CUT_PHASES]


def rb_ledgers(cmds, steps):
    """A2 22.2 (R-B): a run's ledger REBUILT from its own assign record, at the sample of each step in `steps`.
    b(u, v) at step s = the successful assign commands of (u, v) at steps < s, plus those at step s stamped pre,
    advance or post. The sample is taken right after _sync_firefighter_marker_status returns, and nothing after it
    assigns. Returns {s: Counter((unit, victim) -> b)}."""
    by_step = collections.defaultdict(list)
    for c in cmds or ():
        if c[2] == "assign" and c[6]:
            by_step[int(c[0])].append((c[1], str(c[4]), str(c[3])))
    keys = sorted(by_step)
    out, before, j = {}, collections.Counter(), 0
    for s in sorted({int(x) for x in steps}):
        while j < len(keys) and keys[j] < s:
            for _ph, u, v in by_step[keys[j]]:
                before[(u, v)] += 1
            j += 1
        cur = collections.Counter(before)
        for ph, u, v in by_step.get(s, ()):
            if ph in RB_CUT_PHASES:
                cur[(u, v)] += 1
        out[s] = cur
    return out


def rb_figures(waiting, binders, m3a, cmds, live):
    """A2 22.2 (R-B): G-B(f), M3(a) and M3(b), with the latch cap applied in EVERY arm.
    live True = the arm keeps a live ledger (dp1): its recorded b is used, and check (i) compares it with the rebuild
    from its own commands. live False (dp0, dpR): b = b0, the rebuild.
    A LATCHED-HELD victim at a sample is a dp.waiting victim that appears in the same step's dp.binders sample (every
    binder route_blocked, since dp.waiting excludes a victim with an active binder). A pair of a latched-held victim is
    ledger-blocked iff b >= 2; a pair of a W victim (no living binder) is never blocked (a FILL is uncapped).
    M3(a) is recomputed from the m3a free-unit ids (dp_probe v2) over EVERY waiting victim of the same step, those
    with no finite route included. The waiting record holds b only for pairs with a finite route, so dp1 uses the
    rebuild for the other pairs; check (i) compares the rebuild with every recorded b.
    Returns (num Counter, lists dict, checks dict). Every check is a TOOLING check:
      (i)   dp1: each recorded b at a waiting sample equals the rebuild;
      (ii)  dp1: the recorded m3a n_ok equals its recomputation from the ids;
      (iii) every arm: each (unit, victim) of a binders sample has b >= 1 under that step's cut;
      refused: successful assigns stamped init or sweep."""
    num, lists = collections.Counter(), collections.defaultdict(list)
    checks = {"i": [], "ii": [], "iii": [], "refused": rb_cut_refusals(cmds), "m3a_noids": 0, "dup": [],
              "n_i": 0, "n_ii": 0, "n_iii": 0}
    bsamp = {int(step): {vid: bl for vid, bl in lst} for step, lst in binders or ()}
    wsamp = {int(step): (n_free, rows) for step, n_free, rows in waiting or ()}
    for name, rows_ in (("binders", binders), ("waiting", waiting), ("m3a", m3a)):
        seen = collections.Counter(int(r[0]) for r in rows_ or ())
        checks["dup"] += [[name, k] for k, n in sorted(seen.items()) if n > 1]
    steps = set(bsamp) | set(wsamp) | {int(r[0]) for r in m3a or ()}
    led = rb_ledgers(cmds, steps)
    for s, sample in sorted(bsamp.items()):
        for vid, bl in sample.items():
            for uid, _st in bl:
                checks["n_iii"] += 1
                if led[s][(str(uid), str(vid))] < 1:
                    checks["iii"].append([s, uid, vid])

    def latched_at(s, vid):
        bl = bsamp.get(s, {}).get(vid)
        return bool(bl) and all(str(st).lower() == "route_blocked" for _, st in bl)

    for s, (n_free, rows) in sorted(wsamp.items()):
        recorded = {}
        u_any, u_ok = set(), set()
        for vid, cand in rows:
            for uid, _dd, bb in cand:
                recorded[(str(uid), str(vid))] = int(bb)
                checks["n_i"] += 1 if live else 0
                if live and int(bb) != led[s][(str(uid), str(vid))]:
                    checks["i"].append([s, uid, vid, int(bb), led[s][(str(uid), str(vid))]])
            if not cand:
                continue
            latched = latched_at(s, vid)
            used = [[uid, dd, int(bb) if live else led[s][(str(uid), str(vid))]] for uid, dd, bb in cand]
            ok = [c for c in used if not (latched and c[2] >= 2)]
            if ok:
                num["gb_f_allowed"] += 1
                num["gb_f_allowed_WL" if latched else "gb_f_allowed_W"] += 1
                lists["gb_f_allowed"].append([s, vid, used])
            else:
                num["gb_f_blocked"] += 1
                lists["gb_f_blocked"].append([s, vid, used])
            for c in used:
                u_any.add(c[0])
                if c in ok:
                    u_ok.add(c[0])
        num["m3b_allowed"] += len(u_ok)
        num["m3b_blocked"] += len(u_any - u_ok)
        wsamp[s] = (n_free, rows, recorded)
    for row in m3a or ():
        s, n_free = int(row[0]), int(row[1])
        num["m3a"] += n_free
        if len(row) < 4 or not isinstance(row[3], list):
            checks["m3a_noids"] += 1
            continue
        ids = [str(u) for u in row[3]]
        entry = wsamp.get(s)
        if not (entry and len(entry) == 3):
            checks["ii"].append([s, "m3a row without a waiting sample at its step"])
            continue
        rows, recorded = entry[1], entry[2]
        checks["n_ii"] += 1 if live else 0

        def b_of(uid, vid, s=s, recorded=recorded):
            if live and (uid, vid) in recorded:
                return recorded[(uid, vid)]
            return led[s][(uid, vid)]
        n_ok = sum(1 for uid in ids if any(not (latched_at(s, vid) and b_of(uid, str(vid)) >= 2) for vid, _ in rows))
        num["m3a_allowed"] += n_ok
        num["m3a_blocked"] += n_free - n_ok
        if len(ids) != n_free:
            checks["ii"].append([s, "n_free %d but %d ids" % (n_free, len(ids))])
        elif live and int(row[2]) != n_ok:
            checks["ii"].append([s, "recorded n_ok %s, recomputed %d" % (row[2], n_ok)])
    return num, lists, checks


def rb_checks_fail(checks):
    """True when any R-B tooling check fails (the R-B figures are then STOPPED, A2 22.2)."""
    return bool(checks["i"] or checks["ii"] or checks["iii"] or checks["refused"] or checks["m3a_noids"]
                or checks["dup"])


DP_VERBATIM = ("same_path", "mean", "q", "iqr", "fmt", "stdout_path", "parse_stdout", "load_json", "load_run",
               "first_path", "first_div", "hashes", "outside_events", "gt_returns", "m8_classify", "ident_diff",
               "field_get", "ff_state", "cell_means", "drop_most_negative", "wilcoxon", "wil_str", "rb_cut_refusals",
               "rb_ledgers", "rb_figures", "rb_checks_fail")
# the urgency analyzer's own functions this port keeps VERBATIM (urgency:outputs/_ud_analyze.py at 5dba5bcb; checked
# at start-up). Every other function below is new or changed for this round, and says so in its docstring.
UD_VERBATIM = ("out", "head", "git", "lf", "tup", "collapse", "man", "sha_file", "sha_lf_file", "parse_sets", "arg_of",
               "sign_test_p", "holm", "s3_rule", "m8_check", "s2_for", "s6_rule", "full_verdict", "z2_mov", "idx_wb",
               "u1_wb", "outside_events_amended", "gt_returns_amended", "z_rb", "unit_rows", "zm_a", "zm_b",
               "ff_cells_by_step", "z_s", "mv_legs", "leg_events", "latch_episodes", "uav_role_at_rtb_start",
               "searcher_kinds", "writeoff_counts", "stuck_carry_excluded", "kick_flag_check", "loop_episodes",
               "free_units_at", "busy_units_at", "vic_pos", "attribute", "m1_compare", "m1_stat", "harrell", "cval",
               "_t_of", "mu3_target", "mu3_outcome", "mu3_verdicts", "mu3_bias", "mu3_concordance", "seed_cluster",
               "seed_bootstrap", "strandings", "bind_legs", "leg_at", "mu4_exposure", "gb_counts", "gt_b_counts",
               "m6_counts", "extract_section", "show_blob", "module_check", "notes_check", "committed_shas",
               "run_crash", "read_stdout_stripped", "value_identity", "_rows_at", "_shadow", "masked", "mask_text",
               "path_only", "usable", "fresh_recs", "_paired", "_subhead", "_m1_print", "_rline", "print_s6",
               "stop_out")


# ================================================================================================ small helpers
def git(*args):
    try:
        r = subprocess.run(["git", "-C", WT, *args], capture_output=True, timeout=120)
        return r.returncode, r.stdout
    except Exception as exc:                # noqa: BLE001 - reported, never raised
        return -1, repr(exc).encode()


def lf(text):
    return text.replace("\r\n", "\n")


def tup(c):
    return None if c is None else (int(c[0]), int(c[1]))


def collapse(cells):
    o = []
    for c in cells:
        if not o or o[-1] != c:
            o.append(c)
    return o


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def sha_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def sha_lf_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def parse_sets(argv):
    """{NAME: value} of every --set NAME=VALUE in a queue line (ints where they parse)."""
    res = {}
    for i, tok in enumerate(argv[:-1]):
        if tok == "--set" and "=" in argv[i + 1]:
            k, v = argv[i + 1].split("=", 1)
            try:
                res[k] = int(v)
            except ValueError:
                try:
                    res[k] = float(v)
                except ValueError:
                    res[k] = v
    return res


def arg_of(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv[:-1] else None


def ran_of(e):
    """NEW: an ACTED event whose fix step RAN (mvg_probe v1 'ran' = live and not vetoed by the model's guard); a
    ud_probe v2 record (smoke DRY mode, no guard) has no 'ran': its 'live' stands in."""
    return bool(e.get("ran")) if "ran" in e else bool(e.get("live"))


# ================================================================================================ statistics (pure)
def sign_test_p(n_plus, n_minus):
    """23.2: p = P(Binomial(n_plus + n_minus, 1/2) >= n_plus), the exact one-sided sign test of 'Y does not raise k';
    p = 1 when n_plus + n_minus = 0."""
    n = int(n_plus) + int(n_minus)
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(int(n_plus), n + 1)) / float(2 ** n)


def holm(pvals, alpha=ALPHA):
    """23.2 Holm within one family: sort ascending (ties by name), reject p_(i) <= alpha / (m - i + 1) and go on; stop
    at the first i that fails. Returns {name: {p, rank, threshold, rejected}}."""
    m = len(pvals)
    order = sorted(pvals, key=lambda k: (pvals[k], str(k)))
    res, going = {}, True
    for i, k in enumerate(order, start=1):
        thr = alpha / (m - i + 1)
        rej = going and pvals[k] <= thr
        if not rej:
            going = False
        res[k] = {"p": pvals[k], "rank": i, "threshold": thr, "rejected": rej}
    return res


def s3_rule(dd_x, dd_y, cell_set, fresh=FRESH):
    """17.2 S3 on per-cell DD: pooled sum DD(Y) < sum DD(X); <= in set 3 AND in set 4; and the pooled difference stays
    < 0 after removing the single cell with the most negative DD(Y) - DD(X)."""
    cells = sorted(set(dd_x) & set(dd_y))
    deltas = {c: dd_y[c] - dd_x[c] for c in cells}
    pooled = sum(deltas.values())
    per = {s: sum(v for c, v in deltas.items() if cell_set[c] == s) for s in fresh}
    worst = min(deltas, key=lambda c: (deltas[c], c)) if deltas else None
    loo = pooled - deltas[worst] if worst is not None else 0
    ok = pooled < 0 and all(per[s] <= 0 for s in fresh) and loo < 0
    return {"pass": bool(ok), "pooled": pooled, "per_set": per, "loo": loo, "worst": worst,
            "worst_delta": deltas.get(worst)}


def cell_seed(cell_id):
    """NEW: the seed of a cell id 'set5/ring/A_N' -> ('set5', 'A_N'): its ring and uniform runs share the fire."""
    parts = str(cell_id).split("/")
    return (parts[0], parts[-1])


def r2_set_test(deltas, alpha=F1_ALPHA):
    """NEW (1d.3.3 (ii), R2): one seed set's per-cell firefighter-death deltas (Y - X) over its DIVERGED cells: the
    one-sided exact paired sign test, n_plus vs n_minus (ties dropped), p = P(Binomial(n_plus + n_minus, 1/2) >= n_plus)
    (p = 1 when n_plus + n_minus = 0; sign_test_p); the set FAILS iff p <= alpha. deltas {cell: delta}."""
    n_plus = sum(1 for v in deltas.values() if v > 0)
    n_minus = sum(1 for v in deltas.values() if v < 0)
    p = sign_test_p(n_plus, n_minus)
    return {"n_plus": n_plus, "n_minus": n_minus, "p": p, "fail": p <= alpha,
            "up": sorted(c for c, v in deltas.items() if v > 0), "down": sorted(c for c, v in deltas.items() if v < 0)}


def compare_counts(nx, ny, cell_set, diverged, fresh=FRESH):
    """CHANGED (1d.6.1 S5 with 1d.3.3's R2): 23.2 on one comparison X -> Y. nx / ny: {cell: num dict}; cell_set {cell:
    set}; diverged: cells whose Y run is not value-identical to the X run. LITERAL: F1 pooled (ff deaths, Y <= X); F1
    per set read as R2 - the set fails iff the exact one-sided sign test of its diverged cells' ff-death deltas gives
    p <= 0.05; L2 (rescued each fresh set, Y >= X); L3 (DD pooled, Y <= X). The 24 SIGN_KEYS by the exact sign test over
    the diverged cells with Holm. REPORTED beside F1 (never gating): each set's n_plus / n_minus by SEED (ring + uniform
    summed, a seed counting when either of its cells diverged; R2s) and the R0 reading (pooled AND each set literal).
    L4 is added by comparison() from W3. Returns the full result (S4 = L2 and L3; S5 here = no literal fails and no
    sign-tested count rejected)."""
    cells = sorted(set(nx) & set(ny))
    tot = lambda nd, k, sel=None: sum(int(nd[c].get(k, 0) or 0) for c in cells     # noqa: E731
                                      if sel is None or cell_set[c] == sel)
    div = [c for c in cells if c in diverged]
    ffd = {c: int(ny[c].get("ff_deaths", 0) or 0) - int(nx[c].get("ff_deaths", 0) or 0) for c in cells}
    literal = collections.OrderedDict()
    x, y = tot(nx, "ff_deaths"), tot(ny, "ff_deaths")
    literal["F1 ff deaths pooled"] = {"x": x, "y": y, "fail": y > x}
    r2, r2s = collections.OrderedDict(), collections.OrderedDict()
    for s in fresh:
        res = r2_set_test({c: ffd[c] for c in div if cell_set[c] == s})
        r2[s] = res
        literal["F1 R2 %s" % s] = {"x": tot(nx, "ff_deaths", s), "y": tot(ny, "ff_deaths", s), "fail": res["fail"],
                                   "r2": res}
        seeds = collections.defaultdict(int)
        dseeds = set()
        for c in cells:
            if cell_set[c] == s:
                seeds[cell_seed(c)] += ffd[c]
                if c in diverged:
                    dseeds.add(cell_seed(c))
        r2s[s] = r2_set_test({"%s/%s" % k: v for k, v in seeds.items() if k in dseeds})
    for s in fresh:
        x, y = tot(nx, "rescued", s), tot(ny, "rescued", s)
        literal["L2 rescued %s" % s] = {"x": x, "y": y, "fail": y < x}
    x, y = tot(nx, "DD"), tot(ny, "DD")
    literal["L3 DD pooled"] = {"x": x, "y": y, "fail": y > x}
    r0 = {"pooled": tot(ny, "ff_deaths") > tot(nx, "ff_deaths")}
    for s in fresh:
        r0[s] = tot(ny, "ff_deaths", s) > tot(nx, "ff_deaths", s)
    sign, pvals = collections.OrderedDict(), {}
    for k, _label in SIGN_KEYS:
        deltas = {c: int(ny[c].get(k, 0) or 0) - int(nx[c].get(k, 0) or 0) for c in div}
        n_plus = sum(1 for v in deltas.values() if v > 0)
        n_minus = sum(1 for v in deltas.values() if v < 0)
        p = sign_test_p(n_plus, n_minus)
        pvals[k] = p
        sign[k] = {"x": tot(nx, k), "y": tot(ny, k), "n_plus": n_plus, "n_minus": n_minus, "p": p,
                   "rising": sorted(c for c, v in deltas.items() if v > 0)}
    hres = holm(pvals)
    for k in sign:
        sign[k].update(threshold=hres[k]["threshold"], rank=hres[k]["rank"], rejected=hres[k]["rejected"])
    lit_fail = [k for k, v in literal.items() if v["fail"]]
    sig_fail = [k for k, v in sign.items() if v["rejected"]]
    s4 = not any(literal[k]["fail"] for k in literal if k.startswith(("L2", "L3")))
    return {"cells": len(cells), "diverged": len(div), "literal": literal, "r2": r2, "r2s": r2s,
            "r0": {"sets": r0, "fail": any(r0.values())}, "sign": sign, "lit_fail": lit_fail, "sig_fail": sig_fail,
            "S4": s4, "S5": not lit_fail and not sig_fail}


def m8_check(per_set):
    """16.7 Z0: ud0 reproduces dp0's M8 exactly - per set (FC, futile) == DP0_M8 over all 32 runs of the set.
    per_set {set: (fc, futile, runs)} -> 'PASS' / 'FAIL' / 'INCOMPLETE'."""
    if any(per_set.get(s, (0, 0, 0))[2] != 32 for s in DP0_M8):
        return "INCOMPLETE"
    return "PASS" if all(tuple(per_set[s][:2]) == DP0_M8[s] for s in DP0_M8) else "FAIL"


def s2_for(zfails, added):
    """S2 of a comparison: no structural-zero failure owned by a switch the comparison adds (22.8.2)."""
    return [f for f in zfails if f[3] not in ("STOP", "REPORTED") and set(f[3]) & set(added)]


def s6_rule(r_values, call_ms):
    """S6: median R <= 2 % and p99 <= 50 ms per call (14; 22.6.3 for the movement fixes). No call at all is vacuous."""
    med = statistics.median(r_values) if r_values else None
    p99 = q(call_ms, 0.99)
    ok = (med is None or med <= 0.02) and (p99 is None or p99 <= 50.0)
    return {"pass": bool(ok), "median_R": med, "p99": p99, "n_runs": len(r_values), "n_calls": len(call_ms)}


def full_verdict(s1, s2, s3, s4, s5, s6):
    """17.3 order: S1 fails -> STOP; S2, S4 or S5 fails -> FAIL; S3 fails -> NOT SHOWN; S6 fails -> NOT READY; PASS."""
    if not s1:
        return "STOP"
    if not (s2 and s4 and s5):
        return "FAIL"
    if not s3:
        return "NOT SHOWN"
    if not s6:
        return "NOT READY"
    return "PASS"


OUTCOME_TEXT = {
    1: "Any arm-0 failure: STOP (1d.6.2) - a base or instrument defect; the wave is re-run after the fix; no outcome "
       "is read.",
    2: "S1 fails: STOP; the identity defect is fixed and W1 re-run (W2 starts only after S1 passes).",
    3: "S2, S4 or S5 fails: FAIL. FF_APPROACH_PATH and FF_RETREAT_KEEP_APPROACH ship 0; the guard switch (1, inert "
       "with both fixes at 0) and all the round's code are NOT merged; the branch is kept with the report; every "
       "failing instance is diagnosed.",
    4: "Otherwise S3 fails (whatever S6 shows): NOT SHOWN. The fixes ship 0; the code is NOT merged (ruling W-8 (a), "
       "a deviation from 17.3's 'may merge at 0'); S6 recorded.",
    5: "Otherwise S6 fails: NOT READY (17.3.4: optimise value-identically, re-measure cost on 8 value-identical cells, "
       "re-apply).",
    6: "Otherwise PASS: recommend shipping FF_APPROACH_PATH = 1 and FF_RETREAT_KEEP_APPROACH = 1 with the guard ON, "
       "then STOP for the maintainer's confirmation before the flip.",
}


def decide(arm0_stop, s1_fail, full):
    """NEW (1d.6.3, exhaustive, in this order): 1 any arm-0 failure; 2 S1 fails (full_verdict's STOP); 3 FAIL (S2, S4
    or S5); 4 NOT SHOWN (S3); 5 NOT READY (S6); 6 PASS. full = FULL(0 -> G)'s full_verdict."""
    if arm0_stop:
        return 1
    if s1_fail or full == "STOP":
        return 2
    return {"FAIL": 3, "NOT SHOWN": 4, "NOT READY": 5, "PASS": 6}[full]


def movement_switch_verdicts(outcome, zm_ok, acted):
    """CHANGED (1d.6.3 PER SWITCH, after 22.8.5): (a) and (b) each ship ON only if the verdict is PASS, its Zm holds in
    every G and N run, and it ACTED (live, admitted: a fix step that RAN in arm G) in at least one fresh cell of EACH
    set; a switch that did not act in both sets is NOT MEASURED - it ships 0 and its code is NOT merged (ruling D-2,
    report 11; a deviation from 22.8.5's 'may merge at 0'). acted {k: {set: cells}}, zm_ok {k: bool}."""
    res = {}
    for k in ("a", "b"):
        sets = acted.get(k) or {}
        if not all(int(sets.get(s, 0) or 0) >= 1 for s in FRESH):
            res[k] = "NOT MEASURED (did not act - live, admitted - in a fresh cell of both sets: %s) - ships 0; its " \
                     "code is NOT merged" % ({s: int(sets.get(s, 0) or 0) for s in FRESH})
        elif outcome == 1:
            res[k] = "STOP (arm-0 failure)"
        elif outcome == 2:
            res[k] = "STOP (S1 failed)"
        elif outcome != 6:
            res[k] = "ships 0 (outcome %d: %s)" % (outcome, {3: "FAIL", 4: "NOT SHOWN", 5: "NOT READY"}[outcome])
        elif not zm_ok.get(k, False):
            res[k] = "ships 0 (Zm-%s fails in a G or N run)" % k
        else:
            res[k] = "ON - recommended (PASS, Zm-%s holds in every G and N run, acted in both sets); STOP for the " \
                     "maintainer's confirmation before the flip" % k
    return res


# ================================================================================================ zeros (pure)
def z2_mov(cmds, cmd_ctx, rels, rel_ctx):
    """Z2-M: assign, unassign, release or mark_unreachable commands issued from movement code ('fix:' context): 0."""
    fx = lambda ctx: any(str(x).startswith("fix:") for x in (ctx or ()))           # noqa: E731
    bad = [["command"] + list(c[:7]) for c, ctx in zip(cmds or (), cmd_ctx or ()) if fx(ctx)]
    bad += [["release"] + list(r[:5]) for r, ctx in zip(rels or (), rel_ctx or ()) if fx(ctx)]
    return bad


def idx_wb(K):
    """The victim the INDEX loop would bind at kick K: the probe's index_wb (v2: the first of K['index'] the planner
    accepts, None if none). A v1 record has no acceptance flags: its list head stands in (smoke only)."""
    if "index_wb" in K:
        return K["index_wb"]
    return (K.get("index") or [None])[0]


def u1_wb(K):
    """The victim the U1 order would bind (v2 u1_wb; v1: the order's head, smoke only)."""
    if "u1_wb" in K:
        return K["u1_wb"]
    return (K.get("u1") or [None])[0]


def outside_events_amended(x, b, o1, rb_bound, ff_dead, ff_rb_steps):
    """16.7 Z5 / section 10 AMENDED: as outside_events, but a post-phase return whose intermediate binder X is
    route_blocked in rows_ff at the return step is a same-frame latch (o2) WHATEVER the bind's reason."""
    xi, xstep, X, v = x[0], x[1], x[3], x[4]
    i, step, phase, reason = b[0], b[1], b[2], b[5]
    found = []
    if any(xi < k < i for k in o1.get((X, v), ())):
        found.append("o1")
    last_sample = step if phase == "sweep" else step - 1
    if any(xstep <= s <= last_sample for s in rb_bound.get((X, v), ())):
        found.append("o2")
    elif phase == "post" and step in ff_rb_steps.get(X, ()):
        found.append("o2@frame")
    dstep = ff_dead.get(X)
    if dstep is not None and xstep <= dstep <= (step - 1 if phase == "pre" else step):
        found.append("o3")
    return found


def gt_returns_amended(cmds, binders, ff_dead, ff_rb_steps):
    """DPR's gt_returns, unchanged, with the amended outside events swapped in (as Part 1's z5_check did)."""
    g = globals()
    orig = g["outside_events"]
    g["outside_events"] = outside_events_amended
    try:
        return gt_returns(cmds, binders, ff_dead, ff_rb_steps)
    finally:
        g["outside_events"] = orig


def z_rb(rows, carry_on):
    """Z-RB: at every approach advance with a _move_toward call the raise (a _mark_route_blocked call) equals today's
    predicate zrb; on every (a)-acted row today's predicate is false (and no raise on a live (a) step); with (c)
    effective, carrier raises = 0."""
    bad = []
    for r in rows:
        if r["leg"] == "approach" and (r.get("mt") or 0) >= 1 and r.get("zrb") is not None:
            if bool(r.get("rb_call")) != bool(r["zrb"]):
                bad.append([r["step"], r["unit"], "raise %s != predicate %s" % (bool(r.get("rb_call")), r["zrb"])])
        if "a" in (r.get("acted") or ""):
            if r.get("zrb"):
                bad.append([r["step"], r["unit"], "(a)-acted with today's raise predicate true"])
            if r.get("branch") == "approach_a" and r.get("rb_call"):
                bad.append([r["step"], r["unit"], "raise on a live (a) step"])
        if carry_on and r["leg"] == "carry" and r.get("rb_call"):
            bad.append([r["step"], r["unit"], "carrier raise with (c) effective (branch %s)" % r.get("branch")])
    return bad


def unit_rows(rows):
    per = collections.defaultdict(list)
    for r in rows:
        per[r["unit"]].append(r)
    for rs in per.values():
        rs.sort(key=lambda r: (r["step"], r["_i"]))
    return per


def zm_a(rows):
    """Zm-a: over consecutive (a)-acted advances (live, branch approach_a) of one unit with equal board digest and
    target, the clean distance falls by exactly 1, or the unit arrives."""
    bad, n = [], 0
    for _u, rs in unit_rows(rows).items():
        for r1, r2 in zip(rs, rs[1:]):
            if r1.get("branch") != "approach_a" or r2["step"] != r1["step"] + 1:
                continue
            if r1.get("post") is not None and r1["post"] == r1.get("target"):
                continue                                            # arrived
            if r2.get("branch") != "approach_a" or r2["leg"] != "approach" or r2.get("victim") != r1.get("victim"):
                continue
            if r2.get("digest") != r1.get("digest") or r2.get("target") != r1.get("target"):
                continue
            n += 1
            if r1.get("dc") is None or r2.get("dc") is None or r2["dc"] != r1["dc"] - 1:
                bad.append([r2["step"], r2["unit"], "D %s -> %s on an unchanged board" % (r1.get("dc"), r2.get("dc"))])
    return bad, n


def zm_b(rows):
    """Zm-b: every (b)-acted step (live, branch retreat_b) lands on a clean cell of B with G-ESC true."""
    bad = []
    for r in rows:
        if r.get("branch") != "retreat_b":
            continue
        B = r.get("fbB") or []
        if r.get("post") not in B or r.get("cls_post") != "C" or r.get("gesc") is not True:
            bad.append([r["step"], r["unit"], "post %s B %s class %s gesc %s" % (r.get("post"), B, r.get("cls_post"),
                                                                              r.get("gesc"))])
    return bad


def ff_cells_by_step(rows_ff):
    """{step: {unit: rows_ff row}} (step = index + 1)."""
    return {t + 1: {r[0]: r for r in row} for t, row in enumerate(rows_ff or ())}


def z_s(rows):
    """Z-S: no fix-acted step onto a burning cell (live fix branches; a C-2 stay is on a non-burning cell); every (a)
    and (b) step onto a clean cell within a G-ESC region. C-3 holds on a burning cell are reported, not gated."""
    bad, holds = [], []
    for r in rows:
        br = r.get("branch")
        if br not in FIX_BRANCHES:
            continue
        if br == "c3":
            if r.get("cls_post") == "B":
                holds.append([r["step"], r["unit"]])
            continue
        if r.get("cls_post") == "B":
            bad.append([r["step"], r["unit"], "%s onto a burning cell %s" % (br, r.get("post"))])
        if br in ("approach_a", "retreat_b") and (r.get("cls_post") != "C" or r.get("gesc") is not True):
            bad.append([r["step"], r["unit"], "%s onto class %s gesc %s" % (br, r.get("cls_post"), r.get("gesc"))])
    return bad, holds


def guard_dicts(d):
    """NEW: d['mvg']['guard'] rows as dicts (u, n, v, today, model_cell, post as tuples); ([], []) when absent."""
    g = (d.get("mvg") or {}).get("guard") if isinstance(d.get("mvg"), dict) else None
    cols = list((g or {}).get("cols") or [])
    rows = []
    for i, raw in enumerate((g or {}).get("rows") or []):
        r = dict(zip(cols, raw))
        r["_gi"] = i
        for k in ("u", "n", "v", "today", "model_cell", "post"):
            r[k] = tup(r.get(k))
        rows.append(r)
    return cols, rows


def mp_crosscheck(grows):
    """NEW (review I-1) - the instrument's CROSS-CHECK at every guard row: the repo function the model calls
    (movement_paths.stranding_guard, the row's mp_verdict = [admit, c, T_v] on the instrument's arguments) against the
    instrument's own verdict (the frozen-function replica: [admit, c, T_v], None when it raised), exactly the probe's
    rule for d['mvg']['mp_mismatch'] (mp_verdict != that). A difference is a defect of the guard function or of the
    instrument: Zg-1 fails on it in G; elsewhere it is reported (Zg-1 outside G). Returns [[step, unit, kind, text,
    guard row index]]."""
    bad = []
    for r in grows:
        adm = r.get("admit")
        inst = None if adm is None else [bool(adm), r.get("c"), r.get("T_v")]
        mp = r.get("mp_verdict")
        if (None if mp is None else list(mp)) != inst:
            bad.append([r.get("step"), r.get("unit"), r.get("kind"),
                        "the repo function movement_paths.stranding_guard (mp_verdict %s) != the instrument's frozen-"
                        "function replica %s" % (mp, inst), r.get("_gi")])
    return bad


def zg1(grows, sw):
    """CHANGED (review I-1) - Zg-1 TWO-SIDED (1d.6.2) in a run whose guard is on: at every decision where a LIVE fix
    (a) / (b) would act (one guard row each), the MODEL's verdict - the step taken (took: 'fix' or 'today') and its
    guard call's verdict (model_admit) - equals the instrument's independently recomputed ADMIT(n) (admit: the FROZEN
    function's verdict - the probe's local replica of _mvg_guard_diag.guard on the U1 copy's helpers, sharing no code
    with the model's guard). An admitted step where ADMIT is false (UNDER-VETO) fails, and so does a veto where ADMIT is
    true (OVER-VETO). Also failing: no instrument verdict; a verdict inconsistent with 1d.2.2 (ADMIT iff c finite and c
    + 1 <= T(v)); the guard not evaluated by the model where a live fix would act; the model's (admit, c_n, T_v) or the
    cell it judged differing from the instrument's; and the repo function's cross-check tuple (mp_verdict) differing
    from the instrument's (mp_crosscheck). sw {"a", "b"}: the fixes' effective switches (a fix that is off has a shadow
    row only). Returns [[step, unit, kind, text]]."""
    bad = []
    for r in grows:
        k = r.get("kind")
        if not sw.get(k):
            continue
        where = [r.get("step"), r.get("unit"), k]
        adm, m, took = r.get("admit"), r.get("model_admit"), r.get("took")
        bad += [x[:4] for x in mp_crosscheck([r])]
        if adm is None:
            bad.append(where + ["no instrument verdict (the instrument's guard raised)"])
            continue
        c, tv = r.get("c"), r.get("T_v")
        if bool(adm) != (c is not None and (tv is None or c + 1 <= tv)):
            bad.append(where + ["instrument verdict %s against c %s, T(v) %s (1d.2.2: ADMIT iff c finite and c + 1 <= "
                                "T(v))" % (adm, c, tv)])
        if m is None:
            bad.append(where + ["the model did not evaluate the guard where live fix %s would act (took %s)" % (k, took)])
        if adm and (m is False or took != "fix"):
            bad.append(where + ["OVER-VETO: ADMIT true (c %s, T(v) %s) but the model %s" % (
                c, tv, "vetoed" if m is False else "took today's step")])
        if not adm and (m is True or took != "today"):
            bad.append(where + ["UNDER-VETO: ADMIT false (c %s, T(v) %s) but the model %s" % (
                c, tv, "admitted" if m is True else "took the fix's step")])
        if m is not None:
            mv = r.get("model_verdict")
            if mv is None or list(mv) != [bool(adm), c, tv]:
                bad.append(where + ["the model's (admit, c_n, T_v) %s != the instrument's %s" % (mv, [bool(adm), c,
                                                                                                    tv])])
            if r.get("model_cell") != r.get("n"):
                bad.append(where + ["the model judged cell %s, the fix's cell is %s" % (r.get("model_cell"),
                                                                                       r.get("n"))])
    return bad


def zg2(grows, sw):
    """NEW - Zg-2 (1d.6.2) at every VETO (the model's verdict False on a live fix): the step taken equals today's shadow
    - the cell (today's cell; the unit's own when today's step does not move), the raise (today's raise predicate),
    the tier where today's path writes one (_move_toward: a greedy or fallback cell; none for _survival_move), and for
    (b) the _idle_retreat_* writes (origin, steps, stalled, last_cell) the PURE replica of _survival_move's writes
    predicts (pred_writes) against the unit's state after the advance (post_writes). Returns [[step, unit, kind,
    text]]."""
    bad = []
    for r in grows:
        k = r.get("kind")
        if not sw.get(k) or r.get("model_admit") is not False:
            continue
        where = [r.get("step"), r.get("unit"), k]
        want = r.get("today") if r.get("today") is not None else r.get("u")
        if r.get("post") != want:
            bad.append(where + ["veto: the cell taken %s != today's %s (%s)" % (r.get("post"), want,
                                                                               r.get("today_kind"))])
        if bool(r.get("raise")) != bool(r.get("today_raise")):
            bad.append(where + ["veto: raise %s != today's raise predicate %s" % (bool(r.get("raise")),
                                                                                 bool(r.get("today_raise")))])
        if r.get("today_kind") in ("greedy", "fallback") and r.get("today") is not None \
                and r.get("tier") != r.get("today_tier"):
            bad.append(where + ["veto: tier %s != the tier today's _move_toward writes %s" % (r.get("tier"),
                                                                                             r.get("today_tier"))])
        if k == "b":
            pw, qw = r.get("pred_writes"), r.get("post_writes")
            if pw is None or qw is None:
                bad.append(where + ["veto (b): no _idle_retreat_* replica / post-advance state"])
            elif list(pw) != list(qw):
                bad.append(where + ["veto (b): _idle_retreat_* after the advance %s != the replica's %s" % (qw, pw)])
    return bad


def guard_record_problems(grows, mv_rows, events, mp_listed=None):
    """NEW - the guard record's own BOOKKEEPING (an instrument error, INVALID - 16.6 as this round): every acting fix of
    every d['mv'] row has exactly one guard row and one ACTED event; each guard row points at its row (step, unit, pre =
    u, target = v, f<k> = n, today's cell, k in acted, g<K> = admit); its event carries the row's guard verdict and
    live / vetoed / ran consistent with the model's verdict (vetoed iff live and model_admit is False; ran iff live and
    not vetoed); n is a 4-neighbour of u; and (review I-1, mp_listed = d['mvg']['mp_mismatch'] when given) the probe's
    own list of cross-check differences names exactly the guard rows mp_crosscheck finds. (Model behaviour - verdicts,
    steps taken - is Zg-1 / Zg-2 / Z1-M, not here; a cross-check difference itself is Zg-1.)"""
    probs = []
    if mp_listed is not None:
        listed = sorted([x[0], x[1], x[2], x[3]] for x in mp_listed if isinstance(x, (list, tuple)) and len(x) >= 4)
        found = sorted([x[0], x[1], x[2], x[4]] for x in mp_crosscheck(grows))
        if len(listed) != len(mp_listed or ()) or listed != found:
            probs.append("guard: d['mvg']['mp_mismatch'] lists %d row(s), the guard rows hold %d cross-check "
                         "difference(s) (mp_verdict != [admit, c, T_v])" % (len(mp_listed or ()), len(found)))
    by_row, ev = {}, {}
    for r in grows:
        key = (r.get("row"), r.get("kind"))
        if key in by_row:
            probs.append("guard: two rows for d['mv'] row %s fix %s" % key)
        by_row[key] = r
    for e in events:
        if e.get("kind") not in ("a", "b"):
            continue
        key = (e.get("row"), e.get("kind"))
        if key in ev:
            probs.append("guard: two ACTED events for d['mv'] row %s fix %s" % key)
        ev[key] = e
    for m in mv_rows:
        for k in m.get("acted") or "":
            if k not in ("a", "b"):
                probs.append("guard: d['mv'] row %s acted %r (a fix this round does not carry)" % (m["_i"], k))
                continue
            if (m["_i"], k) not in by_row:
                probs.append("guard: d['mv'] row %s (step %s %s) acted %s without a guard row" % (
                    m["_i"], m["step"], m["unit"], k))
            if (m["_i"], k) not in ev:
                probs.append("guard: d['mv'] row %s acted %s without an ACTED event" % (m["_i"], k))
    for (i, k), r in by_row.items():
        if not isinstance(i, int) or not 0 <= i < len(mv_rows):
            probs.append("guard: row index %r outside d['mv']" % (i,))
            continue
        m = mv_rows[i]
        today = (m.get("today") or [None, None])[1]
        if (m["step"], m["unit"], m.get("pre"), m.get("target"), m.get("f" + k), today) != (
                r.get("step"), r.get("unit"), r.get("u"), r.get("v"), r.get("n"), r.get("today")):
            probs.append("guard: step %s %s fix %s: the row and its d['mv'] row disagree on step / unit / u / v / n / "
                         "today" % (r.get("step"), r.get("unit"), k))
        if k not in (m.get("acted") or "") or m.get("g" + k.upper()) != r.get("admit"):
            probs.append("guard: step %s %s fix %s: d['mv'] acted %r / g%s %r against the row's admit %r" % (
                r.get("step"), r.get("unit"), k, m.get("acted"), k.upper(), m.get("g" + k.upper()), r.get("admit")))
        u, n = r.get("u"), r.get("n")
        if u is None or n is None or man(u, n) != 1:
            probs.append("guard: step %s %s fix %s: n %s is not a 4-neighbour of u %s" % (r.get("step"), r.get("unit"),
                                                                                        k, n, u))
        e = ev.get((i, k))
        if e is None:
            continue
        want = {"admit": r.get("admit"), "c": r.get("c"), "T_v": r.get("T_v"), "model_admit": r.get("model_admit")}
        live = bool(e.get("live"))
        vet = bool(live and r.get("model_admit") is False)
        if e.get("guard") != want or bool(e.get("vetoed")) != vet or bool(e.get("ran")) != (live and not vet):
            probs.append("guard: step %s %s fix %s: the ACTED event's guard / vetoed / ran disagree with the row" % (
                r.get("step"), r.get("unit"), k))
    for key in ev:
        if key not in by_row:
            probs.append("guard: an ACTED event (d['mv'] row %s fix %s) without a guard row" % key)
    return probs


# ================================================================================================ counts (pure)
def mv_dicts(d):
    """CHANGED (the guard's columns): d["mv"] rows as dicts (cells as tuples) and the column list."""
    mv = d.get("mv") or {}
    cols = list(mv.get("cols") or [])
    rows = []
    for i, r in enumerate(mv.get("rows") or []):
        x = dict(zip(cols, r))
        x["_i"] = i
        for k in ("pre", "post", "target", "fa", "fb"):
            x[k] = tup(x.get(k))
        t = x.get("today")
        x["today"] = None if t is None else [t[0], tup(t[1]), t[2], t[3]]
        x["fbB"] = None if x.get("fbB") is None else [tup(c) for c in x["fbB"]]
        fc = x.get("fc")
        x["fc"] = None if fc is None else [fc[0], tup(fc[1])]
        for k in ("gA", "gB", "veto", "acted_g"):
            x.setdefault(k, None)
        rows.append(x)
    return cols, rows


def mv_legs(rows):
    """Legs: maximal runs of one unit's rows on consecutive steps with the same leg kind and the same victim."""
    legs = []
    for _u, rs in unit_rows(rows).items():
        cur = []
        for r in rs:
            if cur and r["step"] == cur[-1]["step"] + 1 and r["leg"] == cur[-1]["leg"] and r.get("victim") == cur[-1].get(
                    "victim"):
                cur.append(r)
            else:
                if cur:
                    legs.append(cur)
                cur = [r]
        if cur:
            legs.append(cur)
    return legs


def leg_events(leg, win=WIN):
    """22.8.3 leg kinds on one leg (route distance dr): CYCLE (after collapsing repeats a cell recurs), OSCILLATION
    (a 10-frame window on <= 2 cells with >= 2 changes), PROGRESS (dr at k + 10 >= dr at k), carry NO-PROGRESS (a
    30-step window, dr at the end >= at the start, >= 4 moves). Carry PROGRESS / NO-PROGRESS skip the C-2 stay and
    C-3 hold rows (they split the series)."""
    kind = leg[0]["leg"]
    frames = [r["pre"] for r in leg] + ([leg[-1]["post"]] if leg[-1].get("post") is not None else [])
    frames = [f for f in frames if f is not None]
    col = collapse(frames)
    ev = {"cycle": len(col) != len(set(col)), "osc": False, "prog": False, "noprog": False, "noprog_w": [],
          "prog_k": None}
    for i in range(len(frames) - 9):
        w = frames[i:i + 10]
        if len(set(w)) <= 2 and sum(1 for j in range(1, 10) if w[j] != w[j - 1]) >= 2:
            ev["osc"] = True
            break
    segs, cur = [], []
    for r in leg:
        if (kind == "carry" and r.get("branch") in EXCLUDED_CARRY) or r.get("dr") is None or r.get("pre") is None:
            if cur:
                segs.append(cur)
            cur = []
            continue
        cur.append(r)
    if cur:
        segs.append(cur)
    for seg in segs:
        dd = [r["dr"] for r in seg]
        for k in range(len(dd) - 10):
            if dd[k + 10] >= dd[k]:
                ev["prog"] = True
                ev["prog_k"] = ev["prog_k"] or seg[k]["step"]
                break
        if kind == "carry":
            cells = [r["pre"] for r in seg]
            i = 0
            while i + win - 1 < len(seg):
                if dd[i + win - 1] >= dd[i] and len(collapse(cells[i:i + win])) - 1 >= 4:
                    ev["noprog"] = True
                    ev["noprog_w"].append([seg[i]["step"], seg[i + win - 1]["step"]])
                    i += win
                else:
                    i += 1
    return ev


def latch_episodes(binders):
    """F6: maximal runs of consecutive dp.binders samples in which the pair (unit, victim) appears route_blocked."""
    prev, eps = set(), []
    for step, lst in binders or ():
        cur = {(uid, vid) for vid, bl in lst for uid, st in bl if str(st).lower() == "route_blocked"}
        for p in sorted(cur - prev):
            eps.append([step, p[0], p[1]])
        prev = cur
    return eps


def uav_role_at_rtb_start(rows_uav, uid, step):
    """The role of UAV `uid` at the first step of the return leg (rtb and not docked) that holds `step`."""
    t = step
    role = None
    while t >= 1:
        r = next((x for x in rows_uav[t - 1] if x[0] == uid), None)
        if r is None or not (bool(r[5]) and not bool(r[6])):
            break
        role = r[3]
        t -= 1
    return role


def searcher_kinds(sd_out, rows_uav):
    """F4's three _sd_analyze UAV kinds, counted for the victim_searcher role only (22.8.3, V-9): I2 LIVELOCK and I2
    STUCK by the role at the episode start (e[4]); I6 RTB no-progress by the role at the first step of the return leg
    holding the episode (uav_role_at_rtb_start). All-UAV totals are kept for the F4 role-filter report.
    Returns (num Counter, lists)."""
    num, lists = collections.Counter(), collections.defaultdict(list)
    for e in sd_out.get("I2_uav_livelock") or []:
        num["uav_livelock_all"] += 1
        if e[4] == "victim_searcher":
            num["os_i2_livelock"] += 1
            lists["os_i2_livelock"].append(e[:5])
    for e in sd_out.get("I2_uav_stuck") or []:
        num["uav_stuck_all"] += 1
        if e[4] == "victim_searcher":
            num["os_i2_stuck"] += 1
            lists["os_i2_stuck"].append(e[:5])
    for e in sd_out.get("I6_rtb_no_progress") or []:
        num["rtb_noprog_all"] += 1
        role = uav_role_at_rtb_start(rows_uav, e[2], int(e[0]))
        if role == "victim_searcher":
            num["os_rtb_noprog"] += 1
            lists["os_rtb_noprog"].append(list(e) + [role])
    return num, lists


def writeoff_counts(cmds, det):
    """F8 / M2 write-offs from dp.commands: escape-sweep write-offs (successful mark_unreachable in the sweep phase); of
    those, the write-offs of DETECTED victims (a stdout detection at or before the write-off step - F8); and the other
    (dispatch-phase) write-offs. Returns (num Counter, lists)."""
    num, lists = collections.Counter(), collections.defaultdict(list)
    for c in cmds or ():
        if c[2] == "mark_unreachable" and c[6]:
            if c[1] == "sweep":
                num["escape_writeoffs"] += 1
                t_det = (det or {}).get(c[3])
                if t_det is not None and t_det <= c[0]:
                    num["escape_writeoffs_det"] += 1
                    lists["escape_writeoffs_det"].append([c[0], c[3], c[5]])
            else:
                num["dispatch_writeoffs"] += 1
            lists["writeoffs"].append([c[0], c[1], c[3], c[5]])
    return num, lists


def stuck_carry_excluded(label, d, mv_rows):
    """22.8.3 designed-behaviour exclusion for F5's I2 STUCK carry: the (unit, step) rows on which C-2 stayed (c2s) or
    C-3 held (c3) are masked in a copy of rows_ff (assigned and exiting set to 0, which breaks the carry run there) and
    _sd_analyze.analyze is re-run unchanged. Returns (episodes, or None when no row is excluded; excluded rows)."""
    excl = {(r["unit"], r["step"]) for r in mv_rows or () if r["leg"] == "carry" and r.get("branch") in EXCLUDED_CARRY}
    if not excl:
        return None, 0
    rows2 = []
    for t, row in enumerate(d["rows_ff"]):
        if any((r[0], t + 1) in excl for r in row):
            row = [(list(r[:4]) + [0, 0] + list(r[6:])) if (r[0], t + 1) in excl else r for r in row]
        rows2.append(row)
    d2 = dict(d)
    d2["rows_ff"] = rows2
    sd2, _ = SD.analyze(str(label), d2, STUCK, WIN)
    return list(sd2.get("I2_ff_stuck_carry") or []), len(excl)


def kick_flag_check(K):
    """v2 kick-flag consistency (REPORTED tooling check): index_wb / u1_wb are the first accepted victims of K['index']
    / K['u1'] by K['acc']; div_shadow = qualifies and u1_wb != index_wb; divergent = qualifies and the first bound
    victim (None when nothing is bound) != index_wb. Returns the disagreeing names ([] for a v1 record)."""
    if "index_wb" not in K or K.get("acc") is None:
        return []
    acc = K.get("acc") or {}
    first = lambda xs: next((v for v in xs or [] if acc.get(v)), None)           # noqa: E731
    bad = []
    if K.get("index_wb") != first(K.get("index")):
        bad.append("index_wb")
    if K.get("u1_wb") != first(K.get("u1")):
        bad.append("u1_wb")
    q = bool(K.get("qualifies"))
    if bool(K.get("div_shadow")) != (q and K.get("u1_wb") != K.get("index_wb")):
        bad.append("div_shadow")
    b0 = (K.get("bound") or [[None]])[0][0]
    if bool(K.get("divergent")) != (q and b0 != K.get("index_wb")):
        bad.append("divergent")
    return bad


def shadow_mismatch_zeros(rows, mv_events, arm):
    """CHANGED (the guard; no U1 in any arm): route ud.shadow_mismatch (behaviour, never INVALID - urgency 24.1 (g))
    and every live ACTED event that disagrees with the GUARDED pre-advance shadow (mv_events agree False) to the
    structural zeros. Returns {zero: [instance, ...]}:
    - arm 0: every row -> 'SM' (any one is a STOP, 1d.6.2 'ARM-0 FAILURES');
    - arm G: an (a) / (b) row with one of the probe's guard texts (GUARD_TEXTS) -> 'Zg-1' (guard-owned); any other
      (a) / (b) row, and a live disagreement not already in a row -> 'Z1-M' (item (v): the live action equals the
      guarded shadow; movement-owned);
    - arm N: every (a) / (b) row (a guard text there means the guard ran although FF_FIX_STRANDING_GUARD = 0) and every
      live disagreement -> 'Z1-M';
    - a kick-bind row (the U1 shadow's bookkeeping; U1 is in no arm) or a row of unknown kind -> 'SM' (reported outside
      arm 0)."""
    mov, grd, other, seen = [], [], [], set()
    for r in rows or ():
        r = list(r)
        if (len(r) > 4 and str(r[4]).startswith("kick:")) or (len(r) > 3 and "kick" in str(r[3])):
            other.append(["kick bind != the acc shadow (no U1 in the model)"] + r)
        elif len(r) > 2 and r[2] in ("a", "b"):
            if arm == "G" and len(r) > 3 and str(r[3]) in GUARD_TEXTS:
                grd.append(["guard: model verdict / step != the instrument's"] + r)
            else:
                mov.append(["(v) live action != the pre-advance guarded shadow"] + r)
            seen.add((r[0], r[1], r[2]))
        else:
            other.append(["shadow_mismatch of unknown kind"] + r)
    for e in mv_events or ():
        if e.get("live") and e.get("agree") is False and (e.get("step"), e.get("unit"), e.get("kind")) not in seen:
            mov.append(["(v) live ACTED event disagrees with the model", e.get("step"), e.get("unit"), e.get("kind"),
                        e.get("branch"), e.get("cell"), e.get("taken")])
    if arm == "0":
        allr = other + mov + grd
        return {"SM": allr} if allr else {}
    res = {}
    for k, v in (("Zg-1", grd), ("Z1-M", mov), ("SM", other)):
        if v:
            res[k] = v
    return res


def merge_mismatch(Z, smz):
    """CHANGED (no Z7): add shadow_mismatch_zeros' instances to a run's zeros."""
    for zk, items in smz.items():
        Z.setdefault(zk, []).extend(items)


def loop_episodes(rows_ff, unit, victim):
    """mv_cases' rule (scratch mv_cases/gen.py, mvlib.classify_approach): on each leg of `unit` bound to `victim`
    (rows_ff rescued_victim == victim, alive), approach moves before pickup; a revisit is a move onto a cell the unit
    already occupied in the leg; a loop episode holds >= 3 revisits, consecutive ones <= 4 moves apart. Returns
    [(first step, last step)]."""
    ser = []
    for t, row in enumerate(rows_ff or (), start=1):
        ser.append((t, next((r for r in row if r[0] == unit), None)))
    legs, cur = [], []
    for t, r in ser:
        if r is not None and r[8] == victim and not r[6]:
            cur.append(t)
        elif cur:
            legs.append(cur)
            cur = []
    if cur:
        legs.append(cur)
    pos = {t: ((r[1], r[2]) if r is not None and r[1] is not None else None) for t, r in ser}
    exiting = {t: bool(r[5]) if r is not None else False for t, r in ser}
    eps = []
    for steps in legs:
        pk = next((t for t in steps if exiting[t]), None)
        moves, visited = [], []
        if pos.get(steps[0]) is not None:
            visited.append(pos[steps[0]])
        for t in steps[1:]:
            if pk is not None and t > pk:
                break
            p0, p1 = pos.get(t - 1), pos.get(t)
            if p0 is None or p1 is None:
                continue
            moves.append({"t": t, "revisit": p1 != p0 and p1 in visited})
            if p1 not in visited:
                visited.append(p1)
        idx = [i for i, m in enumerate(moves) if m["revisit"]]
        run = []
        for i in idx:
            if run and i - run[-1] > 4:
                if len(run) >= 3:
                    eps.append((moves[run[0]]["t"], moves[run[-1]]["t"]))
                run = []
            run.append(i)
        if len(run) >= 3:
            eps.append((moves[run[0]]["t"], moves[run[-1]]["t"]))
    return eps


def free_units_at(ffs, t):
    """rows_ff proxy of 'free' at step t: alive, on grid, not assigned, not exiting, unbound, not route_blocked."""
    return [r for r in (ffs.get(t) or {}).values() if not r[6] and r[1] is not None and not r[4] and not r[5]
            and not r[8] and str(r[3]).lower() != "route_blocked" and not r[7]]


def busy_units_at(ffs, t, vid):
    return [r for r in (ffs.get(t) or {}).values() if not r[6] and r[1] is not None and r[8] and r[8] != vid
            and (r[4] or r[5])]


def vic_pos(rows_vic, t, vid):
    if t < 1 or t > len(rows_vic or ()):
        return None
    r = next((x for x in rows_vic[t - 1] if x[0] == vid), None)
    return None if r is None or r[1] is None else (r[1], r[2])


def attribute(v, det, death, m8e, decisions, kicks, waiting, ffs, rows_ff, rows_vic, mv_rows, legs_ev, drops, i2,
              cmds, cmd_ctx):
    """22.9: the FIRST class that applies (FUT, U1, PRE, MOV-a, MOV-b, MOV-c, MOV-closure, RP, L3, OTHER) for one
    detected-victim death, from recorded fields; plus M8-D (16.10). Every d is the instrument's non-burning route
    (dp.m8 min_d, dp.waiting, the kick records, dp.commands d_route) - never a Manhattan substitute; PRE(L1) and
    L3(L1) (Manhattan lower bounds) are informational flags only. Returns (class, flags dict, m8d bool)."""
    slack = lambda t: death - t                                                     # noqa: E731
    flags = collections.OrderedDict()
    fc, fu, _rows = m8_classify([dict(m8e, death_step=death)] if m8e else [])
    flags["FUT"] = bool(fu)
    flags["U1"] = False
    by_k = collections.defaultdict(list)
    for dc in decisions or ():
        by_k[dc.get("k")].append(dc)
    for dc in decisions or ():
        if dc.get("vid") != v or dc.get("served") or dc.get("step") is None or dc["step"] >= death:
            continue
        if dc.get("accepted") is False:
            continue        # refused by the planner: she could not be served under either order (coordinator ruling)
        if any(o.get("served") for o in by_k[dc.get("k")]) and dc.get("d") is not None and dc["d"] + 1 <= slack(
                dc["step"]):
            flags["U1"] = True
    reach_free = False
    m8d = False
    pre_busy = pre_busy_l1 = False
    waited = {}
    for t, n_free, rows in waiting or ():
        if t >= death:
            continue
        row = next((x for x in rows if x[0] == v), None)
        if row is None:
            continue
        cand = row[1] or []
        waited[t] = cand
        if cand:
            reach_free = True
        if any(dd is not None and dd + 1 <= slack(t) for _f, dd, _b in cand):
            m8d = True
        if n_free == 0:
            # the record holds a BUSY unit's route d only at detection: dp.m8 min_d over every living unit, all busy
            # when none is free (the Manhattan variant is reported as the flag PRE(L1), never used for the class)
            md = (m8e or {}).get("min_d")
            if t == det and md is not None and md + 1 <= slack(t):
                pre_busy = True
            vp = vic_pos(rows_vic, t, v)
            if vp is not None and any(man((r[1], r[2]), vp) + 1 <= slack(t) for r in busy_units_at(ffs, t, v)):
                pre_busy_l1 = True
    for K in kicks or ():
        dm = (K.get("d") or {}).get(v)
        if K.get("step") is None or K["step"] >= death or not dm:
            continue
        if any(x is not None for x in dm.values()):
            reach_free = True
        if any(x is not None and x + 1 <= slack(K["step"]) for x in dm.values()):
            m8d = True
    flags["PRE"] = pre_busy and not reach_free
    my = [r for r in mv_rows if r.get("victim") == v and r["step"] < death]
    units = sorted({r["unit"] for r in my} | {r[0] for row in rows_ff[:max(0, death - 1)] for r in row if r[8] == v})
    flags["MOV-a"] = False
    for u in units:
        for s0, s1 in loop_episodes(rows_ff[:max(0, death - 1)], u, v):
            if any(r["unit"] == u and s0 <= r["step"] <= s1 and r["leg"] == "approach" and r.get("dc") is not None
                   for r in my):
                flags["MOV-a"] = True
    flags["MOV-b"] = any(r["leg"] == "approach" and r.get("trig") and r.get("fbB") and r.get("today") is not None
                         and r["today"][1] not in r["fbB"] for r in my)
    flags["MOV-c"] = (any(x[2] == v for x in drops) or any(r.get("branch") in ("c2", "c2s", "c3") for r in my)
                      or any(e["victim"] == v and e["noprog"] and e["first"] < death for e in legs_ev
                             if e["leg"] == "carry"))
    flags["MOV-closure"] = any(r.get("today") is not None and r.get("dcx") is None and r.get("df") is None for r in my)
    flags["RP"] = False
    last = None
    for i, c in enumerate(cmds or ()):
        if c[2] == "assign" and c[6] and c[3] == v and c[0] < death:
            last = (i, c)
    if last is not None:
        i, c = last
        others = None
        ctx = (cmd_ctx[i] if cmd_ctx and i < len(cmd_ctx) else []) or []
        if any(str(x).startswith("kick:") for x in ctx):
            K = next((k for k in kicks or () if k.get("step") == c[0] and [v, c[4]] in (k.get("bound") or [])), None)
            if K is not None:
                others = {f: dd for f, dd in ((K.get("d") or {}).get(v) or {}).items() if f != c[4]}
        if others is None:
            prev = next((x for x in waiting or () if x[0] == c[0] - 1), None)
            row = next((x for x in prev[2] if x[0] == v), None) if prev else None
            if row is not None:
                others = {f: dd for f, dd, _b in row[1] or [] if f != c[4]}
        if others:
            mine = c[8] if len(c) > 8 else None
            flags["RP"] = any(dd is not None and (mine is None or dd < mine) for dd in others.values())
    flags["L3"] = False
    l3_l1 = False
    kick_d = collections.defaultdict(list)
    for K in kicks or ():
        if K.get("step") is not None:
            kick_d[K["step"]].extend(x for x in ((K.get("d") or {}).get(v) or {}).values() if x is not None)
    for key, eps in i2.items():
        for e in eps:
            t0, t1, u = int(e[0]), int(e[1]), e[2]
            r0 = (ffs.get(t0) or {}).get(u)
            if r0 is None or r0[8] != v:
                continue
            for t in range(t0, min(t1, death - 1) + 1):
                # a free unit's route d to a BOUND victim is recorded only while she is latched-held (dp.waiting /
                # kick W); the Manhattan variant is reported as the flag L3(L1), never used for the class
                ds = [dd for _f, dd, _b in waited.get(t, []) if dd is not None] + kick_d.get(t, [])
                if any(dd + 1 <= slack(t) for dd in ds):
                    flags["L3"] = True
                vp = vic_pos(rows_vic, t, v)
                if vp is not None and any(man((r[1], r[2]), vp) + 1 <= slack(t) for r in free_units_at(ffs, t)):
                    l3_l1 = True
    flags["OTHER"] = True
    cls = next(k for k, val in flags.items() if val)
    flags["PRE(L1)"] = pre_busy_l1 and not reach_free
    flags["L3(L1)"] = l3_l1
    return cls, flags, m8d


# ================================================================================================ the guard's measures
def leg_window_events(leg, horizon=H):
    """NEW: the step window [leg start, next bind of the unit or the horizon] of a bind leg (bind_legs)."""
    return leg["step"], (leg["end"] if leg["end"] is not None else horizon)


def guard_legs(grows, legs, mv_rows, cmds, ff_dead, vdead, veto_of):
    """NEW (1d.6.5; 1d.2.6's leg table re-measured): every bind leg (bind_legs) holding >= 1 decision where a fix would
    act (a guard row of that unit and victim inside the leg), with: vetoed (any of its decisions vetoed - veto_of(row)),
    n (its fix decisions), and how the leg ENDED, the first in time of: 'pickup' (a d['mv'] pickup row), 'route_blocked
    unassign' (an o1 unassign of the pair), 'unit died', 'victim died' (ties in that order), else 'open'. Returns
    [{unit, victim, start, vetoed, n, outcome}]."""
    res = []
    o1 = collections.defaultdict(list)
    for c in cmds or ():
        if c[2] == "unassign" and c[6] and "replacement" in str(c[5]) and "blocked" in str(c[5]):
            o1[(c[4], c[3])].append(c[0])
    picks = collections.defaultdict(list)
    for r in mv_rows:
        if r.get("branch") == "pickup":
            picks[(r["unit"], r.get("victim"))].append(r["step"])
    for unit, ls in legs.items():
        for leg in ls:
            s0, s1 = leg_window_events(leg)
            dec = [r for r in grows if r.get("unit") == unit and r.get("victim") == leg["victim"]
                   and s0 <= r.get("step") <= s1]
            if not dec:
                continue
            ends = []
            for rank, (name, steps) in enumerate((("pickup", picks.get((unit, leg["victim"]), [])),
                                                  ("route_blocked unassign", o1.get((unit, leg["victim"]), [])),
                                                  ("unit died", [ff_dead[unit]] if unit in ff_dead else []),
                                                  ("victim died", [vdead[leg["victim"]]] if leg["victim"] in vdead
                                                   else []))):
                ok = [s for s in steps if s0 <= s <= s1]
                if ok:
                    ends.append((min(ok), rank, name))
            res.append({"unit": unit, "victim": leg["victim"], "start": s0, "vetoed": any(veto_of(r) for r in dec),
                        "n": len(dec), "outcome": min(ends)[2] if ends else "open"})
    return res


def guard_alternations(grows, mv_rows, veto_of):
    """NEW (1d.2.5 G4, reported): per unit, decisions where a fix would act at CONSECUTIVE steps: admit -> veto
    transitions (an admitted decision followed by a vetoed one on the next step) and admit -> veto -> admit triples; and
    REVISITS ON AN UNCHANGED DIGEST: maximal runs of a unit's consecutive-step d['mv'] rows with an equal board digest and
    target in which a cell recurs (after collapsing repeats), counted when the run holds a fix decision, and among them
    when it holds a veto. veto_of(row) gives the verdict read (the model's in G, the instrument's shadow elsewhere)."""
    per = collections.defaultdict(dict)
    for r in grows:
        per[r.get("unit")].setdefault(r.get("step"), []).append(r)
    av = ava = 0
    for unit, by in per.items():
        verd = {s: ("V" if any(veto_of(r) for r in rs) else "A") for s, rs in by.items()}
        for s, v in verd.items():
            if v == "A" and verd.get(s + 1) == "V":
                av += 1
                if verd.get(s + 2) == "A":
                    ava += 1
    dec = {(r.get("unit"), r.get("step")): r for r in grows}
    cyc = cyc_v = 0
    for _u, rs in unit_rows(mv_rows).items():
        run = []
        for r in rs + [None]:
            if r is not None and run and r["step"] == run[-1]["step"] + 1 and r.get("digest") == run[-1].get(
                    "digest") and r.get("target") == run[-1].get("target"):
                run.append(r)
                continue
            if len(run) >= 2:
                frames = [x["pre"] for x in run] + ([run[-1]["post"]] if run[-1].get("post") is not None else [])
                col = collapse([f for f in frames if f is not None])
                hold = [dec[(x["unit"], x["step"])] for x in run if (x["unit"], x["step"]) in dec]
                if len(col) != len(set(col)) and hold:
                    cyc += 1
                    cyc_v += any(veto_of(h) for h in hold)
            run = [r] if r is not None else []
    return {"admit_veto": av, "admit_veto_admit": ava, "static_cycles": cyc, "static_cycles_with_veto": cyc_v}


def post_veto_material(mv_rows, cmds, ff_dead):
    """NEW (1d.6.5 POST-VETO DIAG material of one run): per unit, the steps of its route_blocked raises (d['mv']
    rb_set), of its o1 unassigns (route_blocked-handler unassigns), and its death step."""
    raises = collections.defaultdict(list)
    for r in mv_rows:
        if r.get("rb_set"):
            raises[r["unit"]].append(r["step"])
    o1 = collections.defaultdict(list)
    for c in cmds or ():
        if c[2] == "unassign" and c[6] and "replacement" in str(c[5]) and "blocked" in str(c[5]):
            o1[c[4]].append(c[0])
    return {"raise": dict(raises), "o1": dict(o1), "dead": dict(ff_dead)}


def post_veto_counts(pvm, unit, s, window=POST_VETO_WINDOW):
    """NEW: within (s, s + window] for one unit of one run: route_blocked raises, strandings (an o1 unassign followed by
    the unit's death within 15 steps, as MU4) and the unit's death."""
    lo, hi = s, s + window
    rs = sum(1 for t in pvm["raise"].get(unit, []) if lo < t <= hi)
    dt = pvm["dead"].get(unit)
    st = sum(1 for t in pvm["o1"].get(unit, []) if lo < t <= hi and dt is not None and 0 <= dt - t <= STRAND_WINDOW)
    return {"raises": rs, "strandings": st, "death": int(dt is not None and lo < dt <= hi)}


def death_chain(unit, t, cmds, mv_rows, ffs, events):
    """NEW - review 1.3's (i) and (iii) for a unit dying at step t in this record (REPORTED; the knockout (ii) comes from
    W3). The DYING LEG runs from U's last successful assign at a step <= t (dp.commands) to t. (i) U took >= 1 live fix
    step (an ACTED event that RAN) on it. (iii) after U's last own fix step on the leg (s_f), the fire closed U's way -
    a route_blocked raise for U (d['mv'] rb_set, or U's rows_ff status turning route_blocked) or U's clean distance to
    its target infinite (d['mv'] dc None on an approach row: the instrument's BFS on the decision board, which R0
    reproduces) - at a step c in (s_f, t], before U reached its target (no pickup row of U in (s_f, c]), and U was not
    re-bound after c to a route it could pass (no successful assign of U in (c, t] with the instrument's BFS verdict
    route_open True)."""
    binds = [c for c in cmds or () if c[2] == "assign" and c[6] and c[4] == unit and c[0] <= t]
    res = {"s_bind": None, "victim": None, "own": [], "s_f": None, "closure": None, "i": False, "iii": False}
    if not binds:
        return res
    res["s_bind"], res["victim"] = binds[-1][0], binds[-1][3]
    own = sorted((int(e["step"]), e.get("kind")) for e in events or () if e.get("unit") == unit and ran_of(e)
                 and e.get("kind") in ("a", "b") and res["s_bind"] <= int(e["step"]) <= t
                 and e.get("victim") == res["victim"])
    res["own"] = [list(x) for x in own]
    if not own:
        return res
    res["i"] = True
    s_f = own[-1][0]
    res["s_f"] = s_f
    mine = [r for r in mv_rows if r["unit"] == unit and s_f < r["step"] <= t]
    marks = {r["step"] for r in mine if r.get("rb_set")}
    marks |= {r["step"] for r in mine if r["leg"] == "approach" and r.get("dc") is None}
    for s in range(s_f + 1, t + 1):
        cur, prev = (ffs.get(s) or {}).get(unit), (ffs.get(s - 1) or {}).get(unit)
        if cur is not None and str(cur[3]) == "route_blocked" and (prev is None or str(prev[3]) != "route_blocked"):
            marks.add(s)
    picks = sorted(r["step"] for r in mine if r.get("branch") == "pickup")
    for c in sorted(marks):
        if any(p <= c for p in picks):
            break                                           # U reached its target first
        res["closure"] = c
        break
    if res["closure"] is not None:
        reb = [c for c in cmds or () if c[2] == "assign" and c[6] and c[4] == unit and res["closure"] < c[0] <= t
               and len(c) > 7 and c[7] is True]
        res["iii"] = not reb
    return res


# ================================================================================================ W3 / L4 (pure)
def alive_at(rows_ff, unit, t, complete=False):
    """CHANGED (review A-5): True / False = the unit is alive / dead in rows_ff at step t (index t - 1). A COMPLETE run
    (complete: not a crash and its rows are the whole run - it stopped at its --steps or AT its terminal step) whose
    rows end before t has a defined state at t: dead if the unit died within the rows, else alive (it survived the
    run). None = not recorded: the unit is absent, or a crashed / incomplete run stopped before t."""
    rows_ff = rows_ff or []
    if t is None or t < 1:
        return None
    if t > len(rows_ff):
        if not complete or not any(x[0] == unit for row in rows_ff for x in row):
            return None
        return first_death(rows_ff, unit) is None
    r = next((x for x in rows_ff[t - 1] if x[0] == unit), None)
    return None if r is None else not bool(r[6])


def first_death(rows_ff, unit):
    """NEW: the unit's first dead step in rows_ff (step = index + 1), None if it never dies there."""
    for t, row in enumerate(rows_ff or ()):
        for r in row:
            if r[0] == unit and r[6]:
                return t + 1
    return None


def l4_counts(items, fresh=FRESH):
    """NEW - 1d.13.2's COUNTS for one arm X from per-candidate evidence. items: [{"set", "kind": "A" | "B", "resolved":
    bool, "own", "others": True / False / None = U ALIVE at step t in KO-OWN / KO-OTHERS (a knockout that is not run,
    its decision set being empty, carries R0's outcome)}]. CAUSED(X) = the (A) candidates with U alive at t in KO-OWN
    or in KO-OTHERS, plus every UNRESOLVED (A); PREVENTED(X) = the RESOLVED (B) candidates with U dead by t in KO-OWN or
    in KO-OTHERS (an unresolved (B) never counts: a hard clause never passes on missing evidence). THE CLAUSE (L4):
    FAIL iff CAUSED > PREVENTED, pooled over the fresh sets; a tie passes. Returns {"caused", "prevented", "per_set":
    {set: [caused, prevented]}, "fail"}."""
    per = {s: [0, 0] for s in fresh}
    caused = prevented = 0
    for it in items:
        if it["kind"] == "A":
            hit = (not it["resolved"]) or it.get("own") is True or it.get("others") is True
            caused += hit
            per.setdefault(it["set"], [0, 0])[0] += hit
        else:
            hit = bool(it["resolved"]) and (it.get("own") is False or it.get("others") is False)
            prevented += hit
            per.setdefault(it["set"], [0, 0])[1] += hit
    return {"caused": caused, "prevented": prevented, "per_set": per, "fail": caused > prevented}


def l4_run_level(items, fresh=FRESH):
    """NEW - the RUN-LEVEL variant of 1d.13.2 (REPORTED, never counted): a unit counts only if it dies somewhere in one
    run and nowhere in the other ((A): dies in X, never in arm 0; (B): dies in arm 0, never in X), and a knockout
    reverses that ((A): U dies nowhere in KO-OWN or in KO-OTHERS; (B): U dies somewhere in KO-OWN or in KO-OTHERS; a
    knockout not run carries R0's outcome); an unresolved (A) counts, an unresolved (B) does not. items as l4_counts plus
    "never_other" (the other arm's death is None) and "own_dies" / "others_dies" (True / False / None)."""
    per = {s: [0, 0] for s in fresh}
    caused = prevented = 0
    for it in items:
        if not it.get("never_other"):
            continue
        if it["kind"] == "A":
            hit = (not it["resolved"]) or it.get("own_dies") is False or it.get("others_dies") is False
            caused += hit
            per.setdefault(it["set"], [0, 0])[0] += hit
        else:
            hit = bool(it["resolved"]) and (it.get("own_dies") is True or it.get("others_dies") is True)
            prevented += hit
            per.setdefault(it["set"], [0, 0])[1] += hit
    return {"caused": caused, "prevented": prevented, "per_set": per}


def review13_class(it, chain):
    """NEW - review 1.3's class of an (A) candidate (REPORTED; the urgency death review's frozen rule): UNRESOLVED; C-PROX
    ((i) a live fix step of U on its dying leg, (ii) U alive at t in KO-OWN, (iii) the route-closure chain - 'single
    step' when U is also alive in KO-LAST); C-BUTFOR ((i) and (ii), not (iii)); else C-DOWN ('via others' fix steps' when
    U is alive in KO-OTHERS). C-NONE cannot apply to an (A) candidate (U is alive at t in arm 0)."""
    if not it["resolved"]:
        return "UNRESOLVED"
    chain = chain or {}
    if chain.get("i") and it.get("own") is True:
        cls = "C-PROX" if chain.get("iii") else "C-BUTFOR"
        return cls + (" single step" if it.get("last") is True else "")
    return "C-DOWN" + (" via others' fix steps" if it.get("others") is True else "")


# ================================================================================================ REPORTED measures
# (pure; 16.8's reported items and 16.9's M1 / M1c, MU3, MU4 - none of them gates any rule or verdict)
BOOT_DRAWS, BOOT_SEED = 2000, 12345        # Part 1 4.2 (scratch choicepts/cp_concord_seed.py): 2000 draws, Random(12345)
STRAND_WINDOW = 15                          # 12.2 G4 / MU4: an o1 unassign followed by the unit's death within 15 steps
UNCLEAN = ("B", "A", "S")                   # d["mv"] cell classes: burning, fire-adjacent, smoky (C = clean)
FF_LEGS = ("approach", "carry", "idle", "rb_unbound")


def m1_compare(rows):
    """16.9 M1 / M1c, as DPR 14.7 (_dp_analyze.sec_measures, ported unchanged in its rules) on one comparison X -> Y.
    rows: [(cell, gx, gy)] of digests holding victims, det (stdout detection step), resc (rows_vic rescued step) and
    censor. M1: per victim rescued in BOTH arms (paired by cell and victim id - same spawn, same CRN fire draws), delta
    = (rescue - detection) in Y minus in X; m_c = the mean delta of the cell. M1c: every victim detected in both arms,
    (rescue step, or the run's censor 361, when not rescued) - detection, paired the same way. Returns {m1, m1c (cell ->
    m_c), victims / victims_c [(cell, victim, delta)], no_pair, only_one, anomalies}."""
    p1, p1c = collections.defaultdict(list), collections.defaultdict(list)
    no_pair, only_one, anomalies, vict, vict_c = [], [], [], [], []
    for c, gx, gy in rows:
        for v in gx["victims"]:
            t0, t1 = gx["det"].get(v), gy["det"].get(v)
            r0, r1 = gx["resc"].get(v), gy["resc"].get(v)
            if r0 and r1:
                if t0 is None or t1 is None:
                    anomalies.append((c["id"], v, "rescued without a detection line", t0, t1))
                else:
                    dl = (r1 - t1) - (r0 - t0)
                    p1[c["id"]].append(dl)
                    vict.append((c, v, dl))
            if t0 is not None and t1 is not None:
                dc = ((r1 or gy["censor"]) - t1) - ((r0 or gx["censor"]) - t0)
                p1c[c["id"]].append(dc)
                vict_c.append((c, v, dc))
            elif (t0 is None) != (t1 is None):
                only_one.append((c["id"], v, t0, t1))
        if not p1.get(c["id"]):
            no_pair.append(c["id"])
    return {"m1": cell_means(p1), "m1c": cell_means(p1c), "victims": vict, "victims_c": vict_c, "no_pair": no_pair,
            "only_one": only_one, "anomalies": anomalies}


def m1_stat(m, cell_set, sets):
    """DPR's s3_statistic figures WITHOUT a verdict (M1 is reported here): per set, T = the unweighted mean of m_c over
    the set's contributing cells and the same after removing its most negative m_c; both again pooled over `sets`."""
    res = {"n": {}, "T": {}, "loo": {}}
    allv = []
    for s in sets:
        vals = [v for c, v in sorted(m.items()) if cell_set.get(c) == s]
        allv += vals
        res["n"][s], res["T"][s], res["loo"][s] = len(vals), mean(vals), mean(drop_most_negative(vals))
    res["n"]["pooled"], res["T"]["pooled"] = len(allv), mean(allv)
    res["loo"]["pooled"] = mean(drop_most_negative(allv))
    return res


def harrell(items):
    """Part 1 4.2 (scratch choicepts/cp_concord.py, unchanged): items [(pred, obs, event)] -> (concordant, tied_pred,
    comparable). A pair is comparable when the shorter observed time is an event (or ties a censored one)."""
    conc = tie = comp = 0
    n = len(items)
    for i in range(n):
        pi, oi, ei = items[i]
        if not ei:
            continue
        for j in range(n):
            if i == j:
                continue
            pj, oj, ej = items[j]
            if oi < oj or (oi == oj and not ej):
                comp += 1
                if pi < pj:
                    conc += 1
                elif pi == pj:
                    tie += 1
    return conc, tie, comp


def cval(t):
    c, ti, n = t
    return (c + 0.5 * ti) / n if n else None


def _t_of(x):
    t = x.get("T")
    return math.inf if t is None or (isinstance(t, float) and math.isinf(t)) else float(t)


def mu3_target(x, target, horizon):
    """(observed time from the decision step, event) of one decision record. 'burn': the first burn of her DECISION
    cell (first_burn), censored at the horizon; 'death': her death, censored at her rescue completion or the horizon."""
    s = int(x["step"])
    if target == "burn":
        fb = x.get("first_burn")
        return ((fb - s) if fb is not None else (horizon - s)), fb is not None
    dth = x.get("death")
    end = x.get("complete") if x.get("complete") is not None else horizon
    return ((dth - s) if dth is not None else (end - s)), dth is not None


def mu3_outcome(x):
    """MU3 outcome of one decision record: (picked up before her decision cell burned / after it burned / never, died
    or not). 'Before' is strict (pickup step < first burn step); a cell that never burned counts as not yet burned."""
    pk, fb = x.get("pickup"), x.get("first_burn")
    if pk is not None and (fb is None or pk < fb):
        picked = "picked before burn"
    elif pk is not None:
        picked = "picked after burn"
    else:
        picked = "never picked"
    return picked, ("died" if x.get("death") is not None else "survived")


def mu3_verdicts(decisions):
    """Counter((verdict P / D, picked class, died class)) over the decision records (16.9 MU3)."""
    c = collections.Counter()
    for x in decisions or ():
        c[("P" if x.get("P") else "D",) + mu3_outcome(x)] += 1
    return c


def mu3_bias(decisions, horizon):
    """The estimator's bias at the decisions, from the CURRENT-cell T: T - (first burn of the decision cell - step),
    the first burn censored at the horizon; and T - (death - step) where she died. Returns (burn biases, death biases,
    censored count, no-estimate count)."""
    burn, death, cens, noest = [], [], 0, 0
    for x in decisions or ():
        t = _t_of(x)
        if math.isinf(t):
            noest += 1
            continue
        fb = x.get("first_burn")
        if fb is None:
            cens += 1
            fb = horizon
        burn.append(t - (fb - int(x["step"])))
        if x.get("death") is not None:
            death.append(t - (x["death"] - int(x["step"])))
    return burn, death, cens, noest


def mu3_concordance(decisions, horizon):
    """Harrell C pieces of one run at the decisions, predictor = the current-cell T: {(scope, target): (conc, tie,
    comp)}. scope 'kick': pairs of victims waiting at the same qualifying kick (the decision's own ranking); scope
    'run': one record per victim - her FIRST decision - with pairs within the run (Part 1 4.2's within-run rule)."""
    res = {}
    by_k = collections.defaultdict(list)
    first = {}
    for x in decisions or ():
        by_k[x.get("k")].append(x)
        key = (int(x["step"]), int(x.get("k") or 0))
        if x["vid"] not in first or key < first[x["vid"]][0]:
            first[x["vid"]] = (key, x)
    for target in ("burn", "death"):
        tot = [0, 0, 0]
        for _k, xs in sorted(by_k.items(), key=lambda kv: str(kv[0])):
            h = harrell([(_t_of(x),) + mu3_target(x, target, horizon) for x in xs])
            tot = [a + b for a, b in zip(tot, h)]
        res[("kick", target)] = tuple(tot)
        res[("run", target)] = harrell([(_t_of(x),) + mu3_target(x, target, horizon)
                                        for _key, x in sorted(first.values(), key=lambda kv: kv[0])])
    return res


def seed_cluster(cell):
    """The bootstrap cluster of a cell: its seed (set, scenario-wind key) - the ring and uniform runs of a seed share
    the fire (Part 1 4.2)."""
    return (cell["set"], cell["key"])


def seed_bootstrap(stats, draws=BOOT_DRAWS, seed=BOOT_SEED):
    """Part 1 4.2 seed-level bootstrap (cp_concord_seed.py): stats {cluster: (conc, tie, comp)} summed per cluster;
    clusters resampled with replacement `draws` times from Random(seed); draws without a comparable pair dropped.
    Returns (C, 2.5 % bound, 97.5 % bound, comparable pairs, draws kept)."""
    keys = sorted(stats, key=str)
    tot = tuple(sum(stats[k][i] for k in keys) for i in range(3)) if keys else (0, 0, 0)
    if not keys:
        return None, None, None, 0, 0
    rng = random.Random(seed)
    bs = []
    for _ in range(draws):
        smp = [stats[keys[rng.randrange(len(keys))]] for _ in keys]
        t2 = tuple(sum(z[i] for z in smp) for i in range(3))
        if t2[2]:
            bs.append(cval(t2))
    bs.sort()
    if not bs:
        return cval(tot), None, None, tot[2], 0
    return cval(tot), bs[int(0.025 * len(bs))], bs[max(0, int(0.975 * len(bs)) - 1)], tot[2], len(bs)


def strandings(cmds, ff_dead, window=STRAND_WINDOW):
    """12.2 G4 / MU4: an o1 route_blocked-handler unassign (reason containing 'replacement' and 'blocked') of unit u
    at step s, followed by u's death within `window` steps (0 <= death - s <= window). Rows [s, unit, victim, death]."""
    res = []
    for c in cmds or ():
        if c[2] == "unassign" and c[6] and "replacement" in str(c[5]) and "blocked" in str(c[5]):
            dt = ff_dead.get(c[4])
            if dt is not None and 0 <= dt - c[0] <= window:
                res.append([c[0], c[4], c[3], dt])
    return res


def bind_legs(cmds, cmd_ctx, kicks, mv_events):
    """MU4 bind legs: each successful assign of unit u to victim v (dp.commands) opens a leg of u that lasts until u's
    next successful assign. 'div': the assign was made at a U1-divergent kick (a kick record at that step that bound
    the pair, flagged divergent - or, in an arm with U1 off, div_shadow: U1 would have bound another victim there);
    'acted': a movement-fix ACTED event of (u, v) inside the leg (d["mv_events"]: live in an arm with the fixes on,
    the would-act shadow otherwise). Returns {unit: [leg, ...]} in command order."""
    legs = collections.defaultdict(list)
    for i, c in enumerate(cmds or ()):
        if c[2] != "assign" or not c[6]:
            continue
        step, phase, vid, uid = c[0], c[1], c[3], c[4]
        ctx = (cmd_ctx[i] if cmd_ctx and i < len(cmd_ctx) else None) or []
        at_kick = [K for K in kicks or () if K.get("step") == step and [vid, uid] in (K.get("bound") or [])]
        if ctx and not any(str(x).startswith("kick:") for x in ctx):
            at_kick = []
        legs[uid].append({"unit": uid, "victim": vid, "step": step, "phase": phase,
                          "div": any(bool(K.get("divergent") or K.get("div_shadow")) for K in at_kick),
                          "acted": False, "end": None})
    for ls in legs.values():
        for a, b in zip(ls, ls[1:]):
            a["end"] = b["step"]
    for e in mv_events or ():
        st = e.get("step")
        if st is None:
            continue
        for leg in legs.get(e.get("unit"), ()):
            if leg["victim"] == e.get("victim") and leg["step"] <= int(st) and (leg["end"] is None
                                                                               or int(st) <= leg["end"]):
                leg["acted"] = True
    return legs


def leg_at(legs, unit, step, victim=None):
    """The unit's bind leg holding `step`: its latest successful assign at an earlier step, or at the same step in a
    phase other than post / sweep (those follow that step's advance); with `victim`, the latest such assign of her."""
    best = None
    for leg in legs.get(unit, ()):
        if leg["step"] < step or (leg["step"] == step and leg["phase"] not in ("post", "sweep")):
            if victim is None or leg["victim"] == victim:
                best = leg
    return best


def mu4_exposure(rows_ff, cmds, cmd_ctx, kicks, mv_rows, mv_events, ff_dead, window=STRAND_WINDOW):
    """16.9 MU4 / 12.2 G4 firefighter exposure of one run, each item split by bind leg: at a U1-divergent kick vs the
    other legs vs no leg; and with a movement fix ACTED vs not vs no leg. Items: unit-steps on legs (d["mv"] rows -
    approach and carry advances; idle units have no row) and those ending on an unclean cell (cls_post B / A / S);
    route_blocked raises (mv rb_set) and route_blocked onsets in rows_ff (status turning route_blocked); strandings
    (one per o1 unassign) and the distinct unit deaths that follow one (charged to the leg of the latest o1);
    firefighter deaths by leg (ff_state of the unit's last row before death: approach / carry / idle / rb_unbound -
    an idle or rb_unbound death is charged to the unit's latest bind). Returns (table {item: Counter}, strandings
    [s, unit, victim, death, div, acted], deaths [step, unit, leg kind, bound victim, div, acted])."""
    legs = bind_legs(cmds, cmd_ctx, kicks, mv_events)
    tab = collections.defaultdict(collections.Counter)

    def add(item, leg, w=1):
        if not w:
            return
        t = tab[item]
        t["n"] += w
        t["div" if leg and leg["div"] else "nodiv" if leg else "noleg_d"] += w
        t["acted" if leg and leg["acted"] else "notacted" if leg else "noleg_a"] += w

    for r in mv_rows or ():
        leg = leg_at(legs, r["unit"], r["step"], r.get("victim"))
        add("unit_steps", leg)
        if r.get("cls_post") in UNCLEAN:
            add("unclean", leg)
            add("unclean_" + r["cls_post"], leg)
        add("raises_mv", leg, int(r.get("rb_set") or 0))
    prev = {}
    for t, row in enumerate(rows_ff or (), start=1):
        for x in row:
            rb = str(x[3]) == "route_blocked"
            if rb and not prev.get(x[0]) and not x[6]:
                add("rb_onsets", leg_at(legs, x[0], t))
            prev[x[0]] = rb
    strand, last_o1 = [], {}
    for s, u, v, dt in strandings(cmds, ff_dead, window):
        leg = leg_at(legs, u, s, v)
        add("strandings", leg)
        strand.append([s, u, v, dt, bool(leg and leg["div"]), bool(leg and leg["acted"])])
        last_o1[u] = leg                    # dp.commands is in step order: the unit's latest o1 before its death
    for u in sorted(last_o1):
        add("stranded_deaths", last_o1[u])  # one per dead unit, charged to the leg of its latest o1 unassign
    deaths = []
    for u, dt in sorted(ff_dead.items(), key=lambda kv: (kv[1], kv[0])):
        idx = max(0, dt - 2)
        r = next((x for x in (rows_ff[idx] if idx < len(rows_ff or ()) else ()) if x[0] == u), None)
        kind = ff_state(r) if r is not None else "idle"
        leg = leg_at(legs, u, dt, r[8] if r is not None and kind in ("approach", "carry") and r[8] else None)
        if leg is None:
            leg = leg_at(legs, u, dt)
        add("deaths_" + kind, leg)
        deaths.append([dt, u, kind, r[8] if r is not None else None, bool(leg and leg["div"]),
                       bool(leg and leg["acted"])])
    tab["legs"]["n"] = sum(len(v) for v in legs.values())
    tab["legs"]["div"] = sum(1 for v in legs.values() for leg in v if leg["div"])
    tab["legs"]["acted"] = sum(1 for v in legs.values() for leg in v if leg["acted"])
    return {k: dict(v) for k, v in tab.items()}, strand, deaths


def gb_counts(binders, invariant):
    """16.8 reported G-B (DPR digest, ported): (a) victim-steps (dp.binders samples) with >= 2 living binders; (b) with
    >= 2 ACTIVE (not route_blocked) binders; (d) captured RescueInvariant lines (dp.invariant)."""
    num, lists = collections.Counter(), collections.defaultdict(list)
    for step, lst in binders or ():
        for vid, bl in lst:
            if len(bl) >= 2:
                num["gb_a"] += 1
                lists["gb_a"].append([step, vid, bl])
            if sum(1 for _, s in bl if str(s).lower() != "route_blocked") >= 2:
                num["gb_b"] += 1
                lists["gb_b"].append([step, vid, bl])
    num["gb_d"] = len(invariant or [])
    lists["gb_d"] = list(invariant or [])[:20]
    return num, lists


def gt_b_counts(rets):
    """16.8 reported G-T(b): every return of gt_returns_amended (A..X..A on a victim, v..w..v on a unit), counted by its
    outside-event set ('none' = a Z5 instance). Returns (Counter gt_b_<events>, rows [step, phase, victim, unit, X,
    kind, outside])."""
    num = collections.Counter()
    for ret in rets or ():
        num["gt_b_" + ("+".join(ret["outside"]) or "none")] += 1
    return num, [[ret["step"], ret["phase"], ret["victim"], ret["unit"], ret["X"], ret["kind"], ret["outside"]]
                 for ret in rets or ()]


def m6_counts(cmds, writeoffs_avoided):
    """16.8 reported M6 (DPR 14.7 M6, ported): escape-sweep write-offs (mark_unreachable in the sweep phase, = F8's
    base); casualty write-offs (mark_unreachable outside the sweep with a casualty reason - today's immediate write-off
    after a firefighter casualty, reason replacement_after_casualty); other write-offs; assigns into a closed route
    (the instrument's BFS verdict route_open False at the assign); DPR's would-have-been casualty write-offs
    (dp.writeoffs_avoided - a J quantity, expected empty without J)."""
    num, lists = collections.Counter(), collections.defaultdict(list)
    for c in cmds or ():
        if c[2] == "assign" and c[6] and len(c) > 7 and c[7] is False:
            num["assign_closed"] += 1
            lists["assign_closed"].append([c[0], c[1], c[3], c[4], c[5]])
        if c[2] == "mark_unreachable" and c[6]:
            if c[1] == "sweep":
                num["m6_escape"] += 1
            elif "casualty" in str(c[5]):
                num["casualty_writeoffs"] += 1
                lists["casualty_writeoffs"].append([c[0], c[1], c[3], c[5]])
            else:
                num["other_writeoffs"] += 1
    num["writeoffs_avoided"] = len(writeoffs_avoided or [])
    return num, lists


# ================================================================================================ 0 HEADER
def extract_section(text, start, end):
    """The lines from the first one starting with `start` to the line before the first later one starting with `end`
    (end None: the next top-level 'N. ' header, or EOF); trailing blank and '=====' lines dropped; LF-normalised."""
    lines = lf(text).split("\n")
    i = next((k for k, ln in enumerate(lines) if ln.startswith(start)), None)
    if i is None:
        return None
    if end:
        j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith(end)), None)
        if j is None:
            return None
    else:
        j = next((k for k in range(i + 1, len(lines)) if re.match(r"^\d{1,2}\. [A-Z]", lines[k])), len(lines))
    while j > i + 1 and (not lines[j - 1].strip() or set(lines[j - 1].strip()) == {"="}):
        j -= 1
    return "\n".join(lines[i:j])


def extract_hashed(text, start, end):
    """NEW (review A-1): a hashed section. `end` a string: extract_section's rule (verbatim, up to the line before the
    first later one starting with it). `end` a compiled pattern (ROUND_SECTION_RE for 1d.13): the lines from the first
    one starting with `start` to the line before the first LATER line the pattern matches (the next round-section
    header, e.g. a later amendment '1d.14 ...'), or EOF; trailing blank and '=====' banner lines dropped (so a banner
    before an appended section is not part of 1d.13); LF-normalised. None when `start` is absent."""
    if end is None or isinstance(end, str):
        return extract_section(text, start, end)
    lines = lf(text).split("\n")
    i = next((k for k, ln in enumerate(lines) if ln.startswith(start)), None)
    if i is None:
        return None
    j = next((k for k in range(i + 1, len(lines)) if end.match(lines[k])), len(lines))
    while j > i + 1 and (not lines[j - 1].strip() or set(lines[j - 1].strip()) == {"="}):
        j -= 1
    return "\n".join(lines[i:j])


def show_blob(commit, rel):
    rc, blob = git("show", "%s:%s" % (commit, rel))
    return blob.decode("utf-8", "replace") if rc == 0 else None


def hash_checks(current_text=None):
    """CHANGED (1d.8 (6)): each hashed section of the working outputs/urgency_part1d.txt equals its reference commit's -
    1d.2-1d.9 at 74039c54 (where 1d.0-1d.12 were frozen) and at 0d5358e3, and 1d.13 at 0d5358e3 (the rulings amendment
    C1), 1d.13 bounded by the next round-section header or EOF (extract_hashed, review A-1: a later amendment section
    appended after it leaves it unchanged); the whole document against 0d5358e3 is reported (info: a later amendment
    section may follow). Returns (ok, lines)."""
    lines, ok = [], True
    if current_text is None:
        try:
            with open(os.path.join(HERE, "urgency_part1d.txt"), encoding="utf-8") as fh:
                current_text = fh.read()
        except OSError as exc:
            return False, ["urgency_part1d.txt unreadable: %r" % (exc,)]
    blobs = {}
    for name, commit, start, end in HASHED:
        if commit not in blobs:
            blobs[commit] = show_blob(commit, "outputs/urgency_part1d.txt")
        ref = extract_hashed(blobs[commit], start, end) if blobs[commit] else None
        cur = extract_hashed(current_text, start, end)
        same = ref is not None and cur is not None and ref == cur
        ok = ok and same
        lines.append("  section %-10s vs %s: %s (sha256 %s, %d lines)" % (
            name, commit, "identical" if same else "DIFFERS (or unreadable)",
            hashlib.sha256((cur or "").encode()).hexdigest()[:16], (cur or "").count("\n") + 1))
    whole = blobs.get(AMEND_C1)
    lines.append("  info: the whole document %s %s's" % ("==" if whole is not None and lf(whole) == lf(current_text)
                                                         else "DIFFERS from", AMEND_C1))
    return ok, lines


def verbatim_check():
    """CHANGED: each DPR function replicated here is a verbatim substring of dispatch:outputs/_dp_analyze.py at cc8d653c,
    and each ud function kept unchanged one of urgency:outputs/_ud_analyze.py at 5dba5bcb (LF)."""
    lines, ok = [], True
    for names, commit, rel, what in ((DP_VERBATIM, DISPATCH, "outputs/_dp_analyze.py", "DPR"),
                                     (UD_VERBATIM, URGENCY_CODE, "outputs/_ud_analyze.py", "ud")):
        blob = show_blob(commit, rel)
        if blob is None:
            ok = False
            lines.append("  cannot read %s at %s" % (rel, commit[:8]))
            continue
        blob = lf(blob)
        bad = [n for n in names if lf(inspect.getsource(globals()[n])) not in blob]
        ok = ok and not bad
        lines.append("  %d %s functions verbatim from %s: %s" % (len(names) - len(bad), what, commit[:8],
                                                                "all" if not bad else "DIFFER: %s" % bad))
    return ok, lines


def module_check():
    """16.6: the reused modules are byte-identical (LF) to cc8d653c's."""
    lines, ok = [], True
    for name in REUSED_MODULES:
        p = os.path.join(HERE, name)
        rc, blob = git("show", "%s:outputs/%s" % (DISPATCH, name))
        if rc != 0 or not os.path.exists(p):
            lines.append("  %-20s MISSING (file %s, blob rc %s)" % (name, os.path.exists(p), rc))
            ok = False
            continue
        a = sha_lf_file(p)
        b = hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest()
        ok = ok and a == b
        lines.append("  %-20s sha256 %s %s" % (name, a[:16], "== cc8d653c" if a == b else "DIFFERS from cc8d653c %s"
                                                % b[:16]))
    return ok, lines


def notes_check(path):
    """15.5: every '<sha256> outputs/...' line of the Part 2 notes is verified (LF-normalised on a CRLF checkout);
    the tooling files and the frozen queues must be listed."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        return False, ["Part 2 notes unreadable: %r" % (exc,)]
    rows = re.findall(r"\b([0-9a-f]{64})\b\s+(?:\d+\s+)?(\S*outputs/\S+)", text)
    lines, ok, seen = [], True, set()
    for sha, rel in rows:
        rel = rel.strip("`'\",;()")
        rel = rel[rel.index("outputs/"):]
        seen.add(rel)
        p = os.path.join(WT, rel.replace("/", os.sep))
        if not os.path.exists(p):
            ok = False
            lines.append("  MISSING %s" % rel)
            continue
        if sha not in (sha_file(p), sha_lf_file(p)):
            ok = False
            lines.append("  DIFFERS %s (notes %s, file %s)" % (rel, sha[:16], sha_file(p)[:16]))
    missing = [r for r in NOTES_REQUIRED if r not in seen]
    if missing:
        ok = False
        lines.append("  not listed in the notes: %s" % missing)
    lines.insert(0, "  Part 2 notes %s: %d sha256 lines verified => %s" % (path, len(rows), "PASS" if ok else "FAIL"))
    return ok, lines


def repo_rel(path):
    """NEW: a path as a worktree-relative POSIX path ('outputs/x.py'), None when it lies outside the worktree."""
    p = str(path or "")
    if not p:
        return None
    full = os.path.normpath(p if os.path.isabs(p) else os.path.join(WT, p))
    try:
        rel = os.path.relpath(full, WT)
    except ValueError:                       # another drive
        return None
    if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
        return None
    return rel.replace(os.sep, "/")


def mutants_check(head, path=None):
    """NEW (review C-1): the mutation record outputs/_mvg_mutants_result.json (listed in the Part 2d notes, so the file
    read here is the frozen one) must be evidence for THIS tree: every file sha it binds - sha256.files (worktree-
    relative paths), sha256.specs (the spec files, absolute paths inside the worktree) and sha256.engine
    (outputs/_mvg_mutants.py) - equals that file at --head (the committed blob, LF or CRLF form: the engine hashes the
    copied file's bytes, whose line endings core.autocrlf decides), and sha256.changed_during_run is empty. Any
    mismatch, a missing binding or an unreadable record REFUSES (the record must be re-run on the tree at --head).
    Returns (ok, lines)."""
    path = path or os.path.join(WT, MUTANTS_JSON.replace("/", os.sep))
    try:
        doc = load_json(path)
    except Exception as exc:                 # noqa: BLE001
        return False, ["  mutation record %s unreadable: %r" % (path, exc)]
    sha = doc.get("sha256") if isinstance(doc, dict) else None
    sha = sha if isinstance(sha, dict) else {}
    bound, bad = [], []
    files = sha.get("files") if isinstance(sha.get("files"), dict) else {}
    specs = sha.get("specs") if isinstance(sha.get("specs"), dict) else {}
    for rel, s in sorted(files.items()):
        bound.append(("file", repo_rel(rel), rel, s))
    for p, s in sorted(specs.items()):
        bound.append(("spec", repo_rel(p), p, s))
    if sha.get("engine"):
        bound.append(("engine", MUTANTS_ENGINE, MUTANTS_ENGINE, sha["engine"]))
    if not files or not specs or not sha.get("engine"):
        bad.append("the record binds no %s" % "/".join(k for k, v in (("files", files), ("specs", specs),
                                                                       ("engine", sha.get("engine"))) if not v))
    if sha.get("changed_during_run"):
        bad.append("bound files changed during the check: %s" % list(sha["changed_during_run"])[:4])
    for what, rel, given, s in bound:
        if rel is None:
            bad.append("%s %s lies outside the worktree" % (what, given))
            continue
        forms = committed_shas(head, rel)
        if forms is None:
            bad.append("%s %s is not in %s" % (what, rel, head[:10]))
        elif s not in forms:
            bad.append("%s %s: bound sha256 %s is not the file at %s" % (what, rel, str(s)[:16], head[:10]))
    ok = not bad
    lines = ["  mutation record %s: %d bound shas (files %d, specs %d, engine %d) vs --head %s => %s" % (
        MUTANTS_JSON, len(bound), len(files), len(specs), int(bool(sha.get("engine"))), head[:10],
        "PASS" if ok else "FAIL")]
    lines += ["    %s" % b for b in bad[:12]]
    return ok, lines


def load_seeds():
    """CHANGED (1d.4): outputs/_mvg_seeds.txt with the rule RECOMPUTED for sets 1-6 (seed = base + 4*s + w); STOP (None)
    on any mismatch. Sets 1-4 must equal the urgency round's frozen outputs/_ud_seeds.txt at 5dba5bcb, and sets 1-2 the
    fx3mS / fx3mS2 argv cells (_fb3_queue.cells). It never scans for seeds (the seed-selector self-reference rule)."""
    try:
        doc = load_json(os.path.join(HERE, "_mvg_seeds.txt"))
    except Exception as exc:                 # noqa: BLE001
        out("STOP: outputs/_mvg_seeds.txt unreadable (%r)" % (exc,))
        return None
    bad = []
    if doc.get("bases") != EXPECTED_BASES:
        bad.append("bases %r" % doc.get("bases"))
    extra = sorted(k for k in doc if k.startswith("set") and k not in EXPECTED_BASES)
    if extra:
        bad.append("unknown sets %s" % extra)
    seen = {}
    for name, base in EXPECTED_BASES.items():
        expect = sorted([["%s_%s" % (s, wk), s, wind, str(base + 4 * i + j)] for i, s in enumerate("ABCD")
                         for j, (wk, wind) in enumerate(WINDS)], key=lambda r: r[0])
        if doc.get(name) != expect:
            bad.append("%s does not follow the rule seed = %d + 4*s + w" % (name, base))
            continue
        for row in expect:
            if row[3] in seen:
                bad.append("seed %s in %s and %s" % (row[3], seen[row[3]], name))
            seen[row[3]] = name
    ud = show_blob(URGENCY_CODE, "outputs/_ud_seeds.txt")
    try:
        ud = json.loads(ud) if ud else None
    except ValueError:
        ud = None
    if ud is None:
        bad.append("urgency:outputs/_ud_seeds.txt at %s unreadable" % URGENCY_CODE)
    else:
        for name in ("set1", "set2", "set3", "set4"):
            if ud.get(name) != doc.get(name):
                bad.append("%s differs from urgency:outputs/_ud_seeds.txt at %s" % (name, URGENCY_CODE))
    if bad:
        out("STOP: outputs/_mvg_seeds.txt: %s" % bad[:6])
        return None
    out("  frozen cells outputs/_mvg_seeds.txt: rule recomputed for sets 1-6 (bases %s) - identical, 96 distinct "
        "seeds; sets 1-4 == urgency:outputs/_ud_seeds.txt at %s" % (EXPECTED_BASES, URGENCY_CODE))
    try:
        ref = {"set1": [list(c) for c in FQ.cells("fx3mS")], "set2": [list(c) for c in FQ.cells("fx3mS2")]}
        if ref["set1"] != doc["set1"] or ref["set2"] != doc["set2"]:
            out("STOP: sets 1-2 differ from the fx3mS / fx3mS2 argv cells (seed-selector rule)")
            return None
        out("  sets 1-2 == the fx3mS / fx3mS2 argv cells (_fb3_queue.cells)")
    except (Exception, SystemExit) as exc:   # noqa: BLE001
        out("  WARNING: the fx3mS / fx3mS2 argv cells are unreadable (%r) - rule check only" % (exc,))
    return {k: doc[k] for k in EXPECTED_BASES}


def sec_header(opts):
    """CHANGED: the round's commits, the hash checks, the verbatim and module checks, the Part 2d notes, and (with
    --head) the mutation record's binding to the tree at --head (mutants_check, review C-1)."""
    head("MVG ROUND - THE GUARDED MOVEMENT SCREEN'S ANALYZER (outputs/urgency_part1d.txt 1d.2-1d.9; amendment C1 1d.13: "
         "F1 read as R2, the causal clause L4, W3 before the verdict)")
    if opts.smoke:
        out("SMOKE - NOT A SCREEN (one cell from %s; queue / 360-step / head checks relaxed; the cell stands in for the "
            "fresh set 5)" % opts.smoke)
    for c, what in ((PART1D, "Part 1d (1d.0-1d.12 frozen)"), (AMEND_C1, "amendment C1 (1d.13, the rulings)"),
                    (BASE, "base (1d.7: main at a20a2ef5)")):
        rc, txt = git("log", "-1", "--format=%H %ad %s", "--date=short", c)
        out("%-34s %s  %s" % (what + ":", c, txt.decode("utf-8", "replace").strip()[:110] if rc == 0 else "NOT FOUND"))
    rc, hd = git("rev-parse", "HEAD")
    out("%-34s %s" % ("analyzer worktree HEAD:", hd.decode().strip() if rc == 0 else "?"))
    if opts.head:
        rc, txt = git("log", "-1", "--format=%H %ad %s", "--date=short", opts.head)
        anc, _ = git("merge-base", "--is-ancestor", BASE, opts.head)
        out("%-34s %s  %s | descends from the base: %s" % ("Part 2d commit (--head):", opts.head,
                                                            txt.decode("utf-8", "replace").strip()[:80] if rc == 0
                                                            else "NOT FOUND", "yes" if anc == 0 else "NO"))
        if anc != 0:
            out("REFUSED: --head %s does not descend from the base %s (1d.7)" % (opts.head, BASE))
            return False
    ok, lines = hash_checks()
    for ln in lines:
        out(ln)
    if not ok:
        out("REFUSED: a hashed section of outputs/urgency_part1d.txt differs from its committed text (1d.8 (6)) - no "
            "edit of a pre-registered rule after data")
        return False
    vok, lines = verbatim_check()
    mok, mlines = module_check()
    for ln in lines + mlines:
        out(ln)
    if not (vok and mok):
        out("REFUSED: a reused DPR / ud function or module is not the committed one (16.6 as this round)")
        return False
    if opts.part2_notes:
        nok, lines = notes_check(opts.part2_notes)
        for ln in lines:
            out(ln)
        if not nok:
            out("REFUSED: a tooling file or frozen queue differs from the Part 2d notes")
            return False
    else:
        out("  Part 2d notes: NOT CHECKED (smoke)")
    if opts.head:
        mok, lines = mutants_check(opts.head)
        for ln in lines:
            out(ln)
        if not mok:
            out("REFUSED: the mutation record is not bound to the tree at --head (review C-1): re-run "
                "outputs/_mvg_mutants.py on it and re-freeze the notes")
            return False
    else:
        out("  mutation record: NOT CHECKED (smoke)")
    return True


# ================================================================================================ 1 LOAD + PROV
def screen_cells(frozen, opts):
    """CHANGED: W1 (sets 1-2, arm 0), the screen (sets 5-6, arms 0 / G / N; fresh) and the port identity (set 3 ring,
    PORT_KEYS, arm N). --smoke: the one cell --smoke-cell of any set 1-6, standing in for fresh set 5."""
    def cell(k, p, plc, mode, key, scen, wind, seed, kind, arms):
        return {"id": "set%d/%s/%s" % (k, plc, key), "set": "set%d" % k, "k": k, "plc": plc, "p": p, "mode": mode,
                "key": key, "scen": scen, "wind": wind, "seed": int(seed), "fresh": kind == "screen", "kind": kind,
                "arms": arms}
    allc = []
    for k in (1, 2, 3, 4, 5, 6):
        for p, plc, mode in PLACES:
            for key, scen, wind, seed in frozen["set%d" % k]:
                allc.append((k, p, plc, mode, key, scen, wind, seed))
    if opts.smoke:
        return [dict(cell(*x, "smoke", ARMS), set="set5", fresh=True) for x in allc
                if "set%d/%s/%s" % (x[0], x[2], x[4]) == opts.smoke_cell]
    cells = [cell(*x, "w1", ("0",)) for x in allc if x[0] in (1, 2)]
    cells += [cell(*x, "screen", ARMS) for x in allc if x[0] in (5, 6)]
    cells += [cell(*x, "port", ("N",)) for x in allc if x[0] == 3 and x[1] == "r" and x[4] in PORT_KEYS]
    return cells


def run_path(arm, cell, opts):
    if opts.smoke:
        f = opts.smoke_files.get(arm)
        return os.path.join(opts.smoke, f) if f else os.path.join(opts.smoke, "__missing_%s__.json" % arm)
    return os.path.join(HERE, "_sd_%s%s%d_%s.json" % (ARM_TAG[arm], cell["p"], cell["k"], cell["key"]))


def ref_path(cell, opts):
    """CHANGED: the W1 reference (outputs/_mvg_ref/_sd_ud0<p><k>_<S>_<W>.json, ruling W-6 (a)) and the port identity
    reference (outputs/_mvg_ref/_sd_ud2r3_<S>_<W>.json, 1d.8 (11)); --smoke: the 'ref' file."""
    if opts.smoke:
        f = opts.smoke_files.get("ref")
        return os.path.join(opts.smoke, f) if f else None
    if cell["kind"] == "w1":
        return os.path.join(REF_DIR, "_sd_ud0%s%d_%s.json" % (cell["p"], cell["k"], cell["key"]))
    if cell["kind"] == "port":
        return os.path.join(REF_DIR, "_sd_ud2r3_%s.json" % cell["key"])
    return None


def load_queues():
    """CHANGED: {normcase(out): (wave, line)} over the FROZEN queues outputs/_mvg_q_{w1,w2,port}.jsonl."""
    idx = {}
    for wave in ("w1", "w2", "port"):
        p = os.path.join(HERE, "_mvg_q_%s.jsonl" % wave)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip():
                    line = json.loads(ln)
                    idx[os.path.normcase(line["out"])] = (wave, line)
    return idx


def expected_switches(line_sets):
    """CHANGED (1d.7's switch table): the fixes ON only on an exact 1; the guard OFF only on an exact 0 (it ships 1)."""
    return {"FF_APPROACH_PATH": line_sets.get("FF_APPROACH_PATH") == 1,
            "FF_RETREAT_KEEP_APPROACH": line_sets.get("FF_RETREAT_KEEP_APPROACH") == 1,
            "FF_FIX_STRANDING_GUARD": line_sets.get("FF_FIX_STRANDING_GUARD", 1) != 0}


_BLOB_SHAS: dict = {}


def committed_shas(head, rel):
    """The sha256 forms of `rel` at commit `head` (git show): the blob itself, its LF form and its CRLF form (the probe
    hashes the file on disk, whose line endings core.autocrlf decides). None when the file is not in that commit."""
    key = (head, rel)
    if key not in _BLOB_SHAS:
        rc, blob = git("show", "%s:%s" % (head, rel))
        if rc != 0:
            _BLOB_SHAS[key] = None
        else:
            lfb = blob.replace(b"\r\n", b"\n")
            _BLOB_SHAS[key] = {hashlib.sha256(x).hexdigest() for x in (blob, lfb, lfb.replace(b"\n", b"\r\n"))}
    return _BLOB_SHAS[key]


def src_check(d, head):
    """CHANGED (R2 M-2 as this round): every source sha the run recorded (dp.src_sha, ud.src_sha, mvg.src_sha) equals
    the file at --head (its LF or CRLF form); ud.src_sha and mvg.src_sha name every MVG_SRC_REQUIRED file; and the
    instrument-only U1 copy the probe loaded (mvg.u1_shadow_sha) is outputs/_mvg_u1_shadow.py at --head. A mismatch
    means the run executed source that is not the committed one: INVALID. Returns the reasons."""
    why = []
    for sec in ("ud", "dp", "mvg"):
        shas = (d.get(sec) or {}).get("src_sha") if isinstance(d.get(sec), dict) else None
        if not isinstance(shas, dict) or not shas:
            why.append("ran uncommitted source? %s.src_sha not recorded" % sec)
            continue
        if sec in ("ud", "mvg"):
            miss = [r for r in MVG_SRC_REQUIRED if r not in shas]
            if miss:
                why.append("%s.src_sha does not name %s" % (sec, miss))
        bad = [rel for rel, sha in sorted(shas.items()) if sha not in (committed_shas(head, rel) or ())]
        if bad:
            why.append("ran uncommitted source: %s.src_sha differs from %s for %s" % (sec, head[:10], bad[:4]))
    u1 = (d.get("mvg") or {}).get("u1_shadow_sha") if isinstance(d.get("mvg"), dict) else None
    if u1 not in (committed_shas(head, U1_SHADOW_REL) or ()):
        why.append("ran an uncommitted U1 shadow copy: mvg.u1_shadow_sha %s is not %s at %s" % (
            str(u1)[:16], U1_SHADOW_REL, head[:10]))
    return why


_LF_SHAS: dict = {}
_RUN_LOADED: dict = {}


def lf_sha_at(head, rel):
    """NEW (review I-9): the sha256 of `rel`'s LF-normalised blob at commit `head` (git show); None when the file is not
    in that commit. The instrument records its own file's sha the same way (mvg.probe_sha; the replay tool's boards
    replay_sha / probe_sha)."""
    key = (head, rel)
    if key not in _LF_SHAS:
        rc, blob = git("show", "%s:%s" % (head, rel))
        _LF_SHAS[key] = hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest() if rc == 0 else None
    return _LF_SHAS[key]


def run_loaded_changes(a, b, replay=False):
    """NEW (review A-2): the RUN-LOADED files that differ between commits a and b, LF-normalised - the repository's
    RUN_LOADED_REPO (every tracked *.py at the root, everything under src_extension/), the probe chain's
    RUN_LOADED_TOOLING and, for a W3 replay, RUN_LOADED_REPLAY. git diff --name-only --no-renames lists the candidates
    (any byte differing, a file added or deleted); a candidate whose LF-normalised content is the same at both commits
    is not a change, one missing at either commit is. Returns the sorted list ([] = identical), None when git cannot
    compare the two commits."""
    key = (a, b, bool(replay))
    if key not in _RUN_LOADED:
        specs = list(RUN_LOADED_REPO) + list(RUN_LOADED_TOOLING) + (list(RUN_LOADED_REPLAY) if replay else [])
        rc, outb = git("diff", "--name-only", "--no-renames", "--no-ext-diff", a, b, "--", *specs)
        res = None
        if rc == 0:
            res = []
            for rel in outb.decode("utf-8", "replace").splitlines():
                rel = rel.strip()
                if not rel:
                    continue
                ra, xa = git("show", "%s:%s" % (a, rel))
                rb, xb = git("show", "%s:%s" % (b, rel))
                if ra != 0 or rb != 0 or xa.replace(b"\r\n", b"\n") != xb.replace(b"\r\n", b"\n"):
                    res.append(rel)
            res.sort()
        _RUN_LOADED[key] = res
    return _RUN_LOADED[key]


def head_rule(run_head, head, replay=False):
    """NEW (review A-2) - THE HEAD RULE, rule (a): a run is valid when its recorded head starts with --head, OR its
    recorded head is an ANCESTOR of --head (git merge-base --is-ancestor) and every RUN-LOADED file is byte-identical,
    LF-normalised, between the two commits (run_loaded_changes; replay: a W3 replay line, outputs/_mvg_replay.py
    included). So a run made at a build commit stays valid across a later commit that changes no run-loaded file (the
    Part 2d notes commit, a report), and is INVALID when any file it loaded changed. Returns [] (valid) or the INVALID
    reasons. src_check and instrument_check still compare the run's recorded shas with the files at --head."""
    rh = str(run_head or "")
    if rh.startswith(head):
        return []
    if not re.fullmatch(r"[0-9a-f]{7,40}", rh):
        return ["head %s != %s (no commit id recorded)" % (rh[:10] or None, head)]
    rc, _o = git("merge-base", "--is-ancestor", rh, head)
    if rc != 0:
        return ["head %s != %s and is not an ancestor of it (git merge-base --is-ancestor rc %s)" % (rh[:10], head, rc)]
    changed = run_loaded_changes(rh, head, replay)
    if changed is None:
        return ["head %s (an ancestor of %s): its run-loaded files cannot be compared" % (rh[:10], head)]
    if changed:
        return ["head %s is an ancestor of %s but run-loaded files differ (LF-normalised): %s" % (rh[:10], head,
                                                                                             changed[:6])]
    return []


def instrument_check(d, head):
    """NEW (review I-9): the instrument that wrote the run is the committed one - mvg.probe_sha (the probe's sha256 of
    its own LF-normalised bytes, read when the run started) equals outputs/_mvg_probe.py's LF sha256 at --head (by the
    head rule, the same file as at the run's own head). INVALID otherwise. A record without an mvg section is reported
    by prov_run itself."""
    mvg = d.get("mvg") if isinstance(d.get("mvg"), dict) else None
    if mvg is None:
        return []
    want, got = lf_sha_at(head, PROBE_REL), mvg.get("probe_sha")
    if want is None:
        return ["%s is not in %s" % (PROBE_REL, head[:10])]
    if got != want:
        return ["ran an uncommitted instrument: mvg.probe_sha %s is not %s at %s (LF %s)" % (
            str(got)[:16], PROBE_REL, head[:10], want[:16])]
    return []


def run_crash(d, exp_steps):
    """Z6 material of one run: a crash flag, a non-zero chain exit code, or a stop neither terminal nor at the expected
    last step. Returns the text or None."""
    stop_at, term = d.get("steps_done"), d.get("terminal_step")
    rc = (d.get("dp") or {}).get("rc_chain") if isinstance(d.get("dp"), dict) else None
    if d.get("crashed"):
        return "crashed %s at step %s" % ((d.get("crashed") or {}).get("type"), (d.get("crashed") or {}).get("step"))
    if rc not in (0, None):
        return "chain exit code %s" % rc
    if not (stop_at == exp_steps or (term is not None and stop_at == term)):
        return "stopped at step %s (terminal %s, expected %s)" % (stop_at, term, exp_steps)
    return None


def sd_args(argv_l):
    """NEW: the _sd_probe.py arguments of a queue line: after the line's first '--' (a _mvg_probe.py line), after its
    second (a _mvg_replay.py line: replay args -- probe args -- sd args)."""
    if not argv_l or "--" not in argv_l:
        return []
    rest = argv_l[argv_l.index("--") + 1:]
    if os.path.basename(str(argv_l[0])) == "_mvg_replay.py":
        rest = rest[rest.index("--") + 1:] if "--" in rest else []
    return rest


def prov_run(d, path, line, cell, opts):
    """CHANGED (16.6 as this round): validity of one probe (or W3 replay) run - (INVALID reasons, crash text or None,
    STOP reason or None). A crashed run (crash flag, chain exit code != 0, or an early stop) is Z6 material - a GATE
    FAILURE in G / N, a STOP in arm 0 - so the CRN-draw and stdout reasons a crash itself causes are NOT added. INVALID
    (a tooling defect: the run is re-run after the fix): no frozen queue line; repo / argv / .argv signature / steps /
    extra_params differing from the line; a head the HEAD RULE rejects (head_rule: neither --head nor an ancestor of it
    with every run-loaded file identical); uncommitted source; an instrument that is not outputs/_mvg_probe.py at --head
    (instrument_check, mvg.probe_sha); 0 CRN draws; a dp section that is not dp_probe v2
    or holds errors; ud or mvg not mvg_probe v1 (a urgency ud_probe v2 record only in --smoke DRY mode); instrument
    errors (dp / ud / mvg); effective switches differing from the line's (1d.7); the guard table's columns; the
    _survival_move replica disagreeing with the model where today's survival move ran (d['mvg']['replica'] mismatch /
    cell_mismatch: an instrument defect); d['mv']'s columns. ud.shadow_mismatch is behaviour, never INVALID (urgency
    24.1 (g)); a U1 shadow that failed to load is reported (22.9's U1 class not computed), not INVALID."""
    why, stop = [], None
    if d.get("dp_only"):
        return ["the chain wrote no sd JSON"] if not isinstance(d.get("dp"), dict) else [], \
            "no sd record (dp_only - crashed)", None
    argv_l = (line or {}).get("argv") or []
    sd_argv = sd_args(argv_l)
    sets = parse_sets(sd_argv) if line else dict(d.get("extra_params") or {})
    crashed_run = bool(d.get("crashed")) or ((d.get("dp") or {}).get("rc_chain") not in (0, None))
    exp_steps = d.get("steps") if opts.smoke else int(arg_of(sd_argv, "--steps") or H)
    crash = run_crash(d, exp_steps)
    ud = d.get("ud") if isinstance(d.get("ud"), dict) else None
    dry = bool(opts.smoke) and not isinstance(d.get("mvg"), dict) and (ud or {}).get("probe") == UD_PROBE_DRY
    if not opts.smoke:
        if line is None:
            why.append("no line in the frozen queues outputs/_mvg_q_w1 / w2 / port / w3.jsonl")
        else:
            if not same_path(d.get("repo"), WT) or not same_path(arg_of(sd_argv, "--repo"), WT):
                why.append("repo %s (argv %s) != %s" % (d.get("repo"), arg_of(sd_argv, "--repo"), WT))
            if d.get("argv") != sd_argv:
                why.append("sd argv differs from the queue line")
            if not crashed_run:
                try:
                    with open(path + ".argv", encoding="utf-8") as fh:
                        if fh.read() != POOL.signature(line):
                            why.append(".argv signature differs from the queue line")
                except OSError:
                    why.append("no .argv (not a pool run of this line)")
            if d.get("steps") != int(arg_of(sd_argv, "--steps") or H):
                why.append("steps %s != %s" % (d.get("steps"), arg_of(sd_argv, "--steps")))
        if opts.head:
            replay = bool(argv_l) and os.path.basename(str(argv_l[0])) == "_mvg_replay.py"
            why += head_rule(d.get("head"), opts.head, replay)
    if opts.head:
        why += src_check(d, opts.head)
        why += instrument_check(d, opts.head)
    if d.get("extra_params") != sets:
        why.append("extra_params %s != the queue line's %s" % (json.dumps(d.get("extra_params"), sort_keys=True),
                                                              json.dumps(sets, sort_keys=True)))
    crn = (d.get("fb3") or {}).get("crn") or {}
    want_crn = ("--crn" in argv_l) if line else True
    if crash is None and want_crn and not (crn.get("on") and int(crn.get("crn_draws") or 0) > 0):
        why.append("CRN on %s with crn_draws %s (1d.7: 0 draws is INVALID)" % (crn.get("on"), crn.get("crn_draws")))
    if not want_crn and crn.get("on"):
        why.append("CRN on in a CRN-off line")
    if "VICTIM_SPAWN_MODE" in sets and (d.get("fb3") or {}).get("eff", {}).get("victim_spawn_mode") != sets[
            "VICTIM_SPAWN_MODE"]:
        why.append("fb3.eff.victim_spawn_mode %s" % (d.get("fb3") or {}).get("eff", {}).get("victim_spawn_mode"))
    dp = d.get("dp")
    if not isinstance(dp, dict):
        why.append("dp section missing")
    else:
        if dp.get("probe") != "dp_probe v2":
            why.append("dp.probe %r" % dp.get("probe"))
        if dp.get("errors"):
            why.append("instrument errors dp.errors %s" % dp["errors"][:2])
    want = expected_switches(sets)
    if ud is None:
        why.append("ud section missing")
    else:
        if ud.get("probe") != MVG_PROBE and not dry:
            why.append("ud.probe %r (the screen reads %r records only)" % (ud.get("probe"), MVG_PROBE))
        if ud.get("errors"):
            why.append("instrument errors ud.errors %s" % ud["errors"][:2])
        sw = ud.get("switches") or {}
        keys = ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH") if dry else tuple(want)
        got = {k: bool(sw.get(k)) for k in keys}
        if got != {k: want[k] for k in keys}:
            why.append("effective switches %s != the line's %s" % (got, {k: want[k] for k in keys}))
        if not dry and (sw.get("DISPATCH_URGENCY") or sw.get("FF_CARRY_REPLAN")):
            why.append("U1 or fix (c) effective (not in this round, 1d.7)")
        if isinstance(dp, dict):
            if len(ud.get("cmd_ctx") or []) != len(dp.get("commands") or []):
                why.append("ud.cmd_ctx not aligned with dp.commands")
            if len(ud.get("rel_ctx") or []) != len(dp.get("releases") or []):
                why.append("ud.rel_ctx not aligned with dp.releases")
    mvg = d.get("mvg")
    if not dry:
        if not isinstance(mvg, dict):
            why.append("mvg section missing")
        else:
            if mvg.get("probe") != MVG_PROBE:
                why.append("mvg.probe %r" % mvg.get("probe"))
            if mvg.get("errors"):
                why.append("instrument errors mvg.errors %s" % mvg["errors"][:2])
            msw = mvg.get("switches") or {}
            got = {k: bool(msw.get(k)) for k in want}
            if got != want:
                why.append("mvg effective switches %s != the line's %s" % (got, want))
            if tuple((mvg.get("guard") or {}).get("cols") or ()) != GUARD_COLS:
                why.append("d['mvg']['guard'] columns differ from the instrument's schema")
            rp = mvg.get("replica") or {}
            for k_ in ("mismatch", "cell_mismatch"):
                if rp.get(k_):
                    why.append("instrument: the _survival_move replica disagrees with the model (replica.%s %s)" % (
                        k_, rp[k_][:2]))
    mv = d.get("mv")
    cols = tuple(mv.get("cols") or ()) if isinstance(mv, dict) else ()
    if cols != (MV_COLS_DRY if dry else MV_COLS):
        why.append("d['mv'] missing or its columns differ from the instrument's schema")
    if cell is not None and (d.get("scenario"), d.get("wind"), d.get("seed")) != (cell["scen"], cell["wind"],
                                                                                   cell["seed"]):
        stop = "SEED MISMATCH: %s/%s/%s != frozen %s/%s/%s" % (d.get("scenario"), d.get("wind"), d.get("seed"),
                                                               cell["scen"], cell["wind"], cell["seed"])
    so = stdout_path(path)
    if not os.path.exists(so):
        if crash is None:
            why.append("stdout record missing (%s)" % os.path.basename(so))
    elif d.get("stdout_sha") and not sha_file(so).startswith(str(d["stdout_sha"])):
        why.append("stdout record sha differs from stdout_sha")
    return why, crash, stop


# ================================================================================================ digest
def read_stdout_stripped(path):
    """(lines with the new tags stripped, their step markers, victim_dead counts, triage lines)."""
    lines, marks, vdead, triage = [], [], collections.Counter(), []
    p = stdout_path(path)
    if not os.path.exists(p):
        return None, [], vdead, triage
    with open(p, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            s = raw.rstrip("\r\n")
            st = s.strip()
            m = VDEAD_RE.match(st)
            if m:
                vdead[m.group(1)] += 1
            if st.startswith(NEW_TAGS):
                if st.startswith(TRIAGE_TAG):
                    triage.append(st)
                continue
            lines.append(hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()[:12])
            m3 = STEP_RE.search(st)
            marks.append(int(m3.group(1)) if m3 else None)
    return lines, marks, vdead, triage


def digest(d, arm, label, path, cell_set=None, censor=H + 1):
    """CHANGED (the guard; no U1 or fix (c) in any arm): everything later sections read from one probe run, computed
    once (the run dict is dropped afterwards). censor: M1c's censoring step (361 = H + 1; in smoke mode the run's own
    last step + 1). A urgency ud_probe v2 record (smoke DRY mode) is read without guard material."""
    g = {"arm": arm, "label": label, "path": path, "set": cell_set, "dp_only": bool(d.get("dp_only")),
         "crashed": d.get("crashed"), "censor": censor, "horizon": censor - 1}
    dp = d.get("dp") if isinstance(d.get("dp"), dict) else {}
    ud = d.get("ud") if isinstance(d.get("ud"), dict) else {}
    mvg = d.get("mvg") if isinstance(d.get("mvg"), dict) else None
    g["dry"] = mvg is None
    sw = ((mvg or {}).get("switches") if mvg is not None else ud.get("switches")) or {}
    g["sw"] = {"a": bool(sw.get("FF_APPROACH_PATH")), "b": bool(sw.get("FF_RETREAT_KEEP_APPROACH")),
               "g": bool(sw.get("FF_FIX_STRANDING_GUARD")) if mvg is not None else False}
    tm = ud.get("timing") or {}
    gt = (mvg or {}).get("timing") or {}
    g["wall_s"] = float(d.get("wall_s") or 0.0)
    g["fix_ms"] = float(sum((tm.get("fix_ms_total") or {}).values()) or 0.0)
    g["fix_calls"] = {f: list(v or []) for f, v in (tm.get("fix_calls") or {}).items()}
    g["guard_ms"] = [float(x) for x in gt.get("guard_ms") or []]
    g["inst_guard_ms"] = [float(x) for x in gt.get("inst_guard_ms") or []]
    g["probe_frac"] = tm.get("probe_frac_of_wall")
    g["u1_shadow_error"] = (mvg or {}).get("u1_shadow_error")
    g["inst_problems"] = []
    if g["dp_only"] or not d.get("rows_ff"):
        g["usable"] = False
        return g
    g["usable"] = True
    rows_ff, rows_vic = d["rows_ff"], d["rows_vic"]
    g["eval"] = dict(d.get("eval") or {})
    g["terminal"] = d.get("terminal_step")
    g["steps_done"] = d.get("steps_done")
    g["n_ff"] = int((d.get("params") or {}).get("NUM_FIREFIGHTERS") or 0)
    g["victims"] = [r[0] for r in rows_vic[0]] if rows_vic else []
    det = d.get("_det") or {}
    g["det"] = {v: det.get(v) for v in g["victims"]}
    resc, vdead = {}, {}
    for t, row in enumerate(rows_vic):
        for r in row:
            if r[4] == "rescued" and r[0] not in resc:
                resc[r[0]] = t + 1
            if r[4] == "dead" and r[0] not in vdead:
                vdead[r[0]] = t + 1
    g["resc"], g["vdead"] = resc, vdead
    ff_dead, ff_rb = {}, collections.defaultdict(set)
    for t, row in enumerate(rows_ff):
        for r in row:
            if r[6] and r[0] not in ff_dead:
                ff_dead[r[0]] = t + 1
            if str(r[3]) == "route_blocked":
                ff_rb[r[0]].add(t + 1)
    g["ff_dead"] = ff_dead
    ffs = ff_cells_by_step(rows_ff)
    num = collections.Counter()
    lists = collections.defaultdict(list)
    ev = g["eval"]
    num["rescued"] = int(ev.get("rescued") or 0)
    num["ff_deaths"] = int(ev.get("firefighter_deaths") or 0)
    num["dead"] = int(ev.get("dead") or 0)
    num["never_detected"] = int(ev.get("never_detected") or 0)
    num["never_finish"] = int(d.get("terminal_step") is None)
    g["DD"] = sorted(v for v in vdead if g["det"].get(v) is not None)
    num["DD"] = len(g["DD"])
    # ---- F4 searcher: G-OS (DPR) + I2 / I6 (searcher role)
    broad, near, anyw = A.searcher_o(d)
    last = U._last_detection(d)
    for e in broad:
        when = "after" if last is not None and e[1] >= last else "before"
        num["os_broad_" + when] += 1
        lists["os_broad_" + when].append([e[0], e[1], e[2], e[3], e[4]])
    num["os_pocket_near"], num["os_pocket_any"] = near, anyw
    sd_out, _info = SD.analyze(label, d, STUCK, WIN)
    skn, skl = searcher_kinds(sd_out, d["rows_uav"])
    num.update(skn)
    lists.update(skl)
    # ---- F5 firefighter: G-OF (DPR) + I2 + the 7 leg kinds
    by_step = [{r[0]: r for r in row} for row in rows_ff]
    for fid, s0, s1, n in A.ff_episodes(d):
        st = collections.Counter(ff_state(by_step[s - 1][fid]) for s in range(s0, s1 + 1) if fid in by_step[s - 1])
        num["of_broad"] += 1
        lists["of_broad"].append([fid, s0, s1, n, st.most_common(1)[0][0] if st else "?"])
    i2 = {}
    for short, key in I2_KINDS:
        eps = sd_out.get(key) or []
        i2[short] = [e[:3] for e in eps]
        num["of_" + short] = len(eps)
        lists["of_" + short] = [e[:3] for e in eps]
    _cols, mv_rows = mv_dicts(d)
    eps, g["n_excluded_carry"] = stuck_carry_excluded(label, d, mv_rows)
    if eps is not None:            # 22.8.3's exclusion (void here: no C-2 stay / C-3 hold row exists without fix (c))
        num["of_stuck_carry"] = len(eps)
        lists["of_stuck_carry"] = [e[:3] for e in eps]
        num["of_stuck_carry_unexcluded"] = len(sd_out.get("I2_ff_stuck_carry") or [])
    legs = mv_legs(mv_rows)
    legs_ev = []
    for leg in legs:
        e = leg_events(leg)
        kind = leg[0]["leg"]
        rec = {"unit": leg[0]["unit"], "victim": leg[0].get("victim"), "leg": kind, "first": leg[0]["step"],
               "last": leg[-1]["step"], "cycle": e["cycle"], "osc": e["osc"], "prog": e["prog"], "noprog": e["noprog"],
               "noprog_w": e["noprog_w"], "prog_k": e["prog_k"]}
        legs_ev.append(rec)
        num["legs_" + kind] += 1
        for k in ("cycle", "osc", "prog"):
            if e[k]:
                num["leg_%s_%s" % (k, kind)] += 1
                lists["leg_%s_%s" % (k, kind)].append([rec["unit"], rec["victim"], rec["first"], rec["last"]])
        if kind == "carry" and e["noprog"]:
            num["leg_noprog_carry"] += 1
            lists["leg_noprog_carry"].append([rec["unit"], rec["victim"], rec["first"], rec["last"], e["noprog_w"]])
    # ---- F6, F8
    lat = latch_episodes(dp.get("binders"))
    num["latch_episodes"] = len(lat)
    lists["latch_episodes"] = lat
    g["latched_end"] = sorted(U2.ff_status_track(d)[2])
    cmds = dp.get("commands") or []
    won, wol = writeoff_counts(cmds, g["det"])
    num.update(won)
    lists.update(wol)
    # ---- identity material (16.7's fields: every per-step row, the commands, eval, stdout with the new tags stripped)
    g["h"] = {k: hashes(d.get(k) or []) for k in ROW_KINDS}
    g["cmds"] = [list(c) for c in cmds]
    g["rels"] = [list(r) for r in dp.get("releases") or []]
    g["cmd_ctx"] = list(ud.get("cmd_ctx") or [])
    g["rel_ctx"] = list(ud.get("rel_ctx") or [])
    so, marks, vdead_ev, _triage = read_stdout_stripped(path)
    g["so"], g["so_marks"] = so, marks
    g["vdead_events"] = dict(vdead_ev)
    g["kicks"] = list(ud.get("kicks") or [])
    g["decisions"] = list(ud.get("decisions") or [])
    g["fates"] = dict(ud.get("fates") or {})
    g["mv_rows"] = mv_rows
    g["mv_events"] = list(d.get("mv_events") or [])
    g["legs_ev"] = legs_ev
    g["m8"] = list(dp.get("m8") or [])
    _gcols, grows = guard_dicts(d)
    # ---- per-run structural zeros (owners applied in section 3)
    Z = {}
    Z["Z2-M"] = z2_mov(cmds, g["cmd_ctx"], g["rels"], g["rel_ctx"])
    lists["kick_flag_bad"] = [[K.get("step"), K.get("i"), kick_flag_check(K)] for K in g["kicks"] if kick_flag_check(K)]
    rets = gt_returns_amended(cmds, dp.get("binders"), ff_dead, ff_rb)
    Z["Z5"] = [r for r in rets if not r["outside"]]
    num["gt_returns"] = len(rets)
    Z["Z-RB"] = z_rb(mv_rows, False)
    drops_all = []
    for c in cmds:
        prev = (ffs.get(c[0] - 1) or {}).get(c[4])
        if c[2] == "unassign" and c[6] and prev is not None and prev[5] and "replacement" in str(c[5]) and "blocked" in \
                str(c[5]):
            drops_all.append([c[0], c[4], c[3]])
    g["drops"] = drops_all
    if g["sw"]["a"]:
        Z["Zm-a"], num["zm_a_pairs"] = zm_a(mv_rows)
    if g["sw"]["b"]:
        Z["Zm-b"] = zm_b(mv_rows)
        # 22.3.5: a (b) step writes no _idle_retreat_* state (the replica's fix_checked rows, d['mvg']['replica'])
        Z["Zm-b"] += [[x[0], x[1], "a (b) step changed the _idle_retreat_* state %s -> %s" % (x[3], x[4])]
                      for x in ((mvg or {}).get("replica") or {}).get("fix_mismatch") or []]
    if g["sw"]["a"] or g["sw"]["b"]:
        Z["Z-S"], lists["c3_on_burning"] = z_s(mv_rows)
    fix_sw = {"a": g["sw"]["a"], "b": g["sw"]["b"]}
    if g["sw"]["g"] and (g["sw"]["a"] or g["sw"]["b"]):
        Z["Zg-1"] = zg1(grows, fix_sw)
        # the cross-check on the shadow rows of a fix that is off (zg1 checks the live ones)
        Z["Zg-1"] += [x[:4] for x in mp_crosscheck(grows) if not fix_sw.get(x[2])]
        Z["Zg-2"] = zg2(grows, fix_sw)
    elif mvg is not None:
        # review I-1: outside G (arm 0, arm N) the repo function is still cross-checked against the frozen-function
        # replica on every decision board (shadow rows); a difference is REPORTED there (Zg-1's owner outside G)
        Z["Zg-1"] = [x[:4] for x in mp_crosscheck(grows)]
    # the guard evaluated where it must not be (fix off, or guard off): an identity breach of the arm
    ran_guard = [[r["step"], r["unit"], r["kind"], "the model evaluated the guard although %s" % (
        "the fix is off" if not fix_sw.get(r["kind"]) else "FF_FIX_STRANDING_GUARD is 0")]
        for r in grows if r.get("model_admit") is not None and not (g["sw"]["g"] and fix_sw.get(r["kind"]))]
    if g["guard_ms"] and not (g["sw"]["g"] and (g["sw"]["a"] or g["sw"]["b"])):
        ran_guard.append([None, None, None, "%d model guard calls timed although %s" % (
            len(g["guard_ms"]), "FF_FIX_STRANDING_GUARD is 0" if not g["sw"]["g"] else "both fixes are off")])
    if ran_guard:
        Z.setdefault("SM" if arm == "0" else "Z1-M", []).extend(ran_guard)
    merge_mismatch(Z, shadow_mismatch_zeros(ud.get("shadow_mismatch"), g["mv_events"], "0" if arm == "0" else
                                            ("G" if g["sw"]["g"] else "N")))
    g["Z"] = Z
    if mvg is not None:
        g["inst_problems"] = guard_record_problems(grows, mv_rows, g["mv_events"], mvg.get("mp_mismatch") or [])
    # ---- ACTED footprint (would-act shadows, live, ran, vetoed) and the guard's decisions
    for e in g["mv_events"]:
        k = e.get("kind")
        num[("live_" if e.get("live") else "shadow_") + str(k)] += 1
        if e.get("live") and ran_of(e):
            num["ran_" + str(k)] += 1
        if e.get("vetoed"):
            num["vetoed_" + str(k)] += 1
    g["acted_ran"] = {k: bool(any(e.get("live") and ran_of(e) and e.get("kind") == k for e in g["mv_events"]))
                      for k in ("a", "b")}
    veto_model = arm == "G" or (g["sw"]["g"] and (g["sw"]["a"] or g["sw"]["b"]))
    veto_of = (lambda r: r.get("model_admit") is False) if veto_model else (lambda r: r.get("admit") is False)
    gnum = collections.Counter()
    for r in grows:
        k = r.get("kind")
        gnum["rows_" + k] += 1
        gnum[("inst_admit_" if r.get("admit") else "inst_veto_" if r.get("admit") is False else "inst_none_") + k] += 1
        if r.get("model_admit") is not None:
            gnum[("model_admit_" if r.get("model_admit") else "model_veto_") + k] += 1
        if r.get("took") == "fix":
            gnum["took_fix_" + k] += 1
    g["gnum"] = gnum
    g["veto_model"] = veto_model
    bl = bind_legs(cmds, g["cmd_ctx"], g["kicks"], [])
    g["guard_legs"] = guard_legs(grows, bl, mv_rows, cmds, ff_dead, vdead, veto_of)
    g["guard_alt"] = guard_alternations(grows, mv_rows, veto_of)
    g["pvm"] = post_veto_material(mv_rows, cmds, ff_dead)
    g["vetoes"] = sorted([int(e["step"]), e.get("unit"), e.get("kind")] for e in g["mv_events"] if e.get("vetoed"))
    # ---- W3 material: each dead unit's review-1.3 chain and its rows (the C-NONE check of a same-step death)
    g["death_chain"] = {u: death_chain(u, t, cmds, mv_rows, ffs, g["mv_events"]) for u, t in ff_dead.items()}
    g["dead_unit_h"] = {u: hashes([next((r for r in rows_ff[s] if r[0] == u), None) for s in range(t)])
                        for u, t in ff_dead.items()}
    # ---- U1 shadow decisions (MU1 / MU2: U1 is in no arm, the kick records are the instrument's shadow)
    num["kicks"] = len(g["kicks"])
    num["kicks_qualifying"] = sum(1 for K in g["kicks"] if K.get("qualifies"))
    num["kicks_div_shadow"] = sum(1 for K in g["kicks"] if K.get("div_shadow"))
    num["kicks_divergent"] = sum(1 for K in g["kicks"] if K.get("divergent"))
    num["kicks_scarce_multi"] = sum(1 for K in g["kicks"] if K.get("W") is not None and len(K.get("F") or []) >= 2
                                    and len(K.get("W") or []) > len(K.get("F") or []))
    num["promotions"] = sum(1 for x in g["decisions"] if x.get("P"))
    num["deferrals"] = sum(1 for x in g["decisions"] if x.get("P") is False)
    num["kicks_refused_head"] = sum(1 for K in g["kicks"] if K.get("qualifies") and "index_wb" in K and (
        K.get("index_wb") != (K.get("index") or [None])[0] or K.get("u1_wb") != (K.get("u1") or [None])[0]))
    num["decisions_refused"] = sum(1 for x in g["decisions"] if x.get("accepted") is False)
    # ---- M8 / M8-D / 22.9 attribution of every detected-victim death
    m8 = {e.get("victim"): e for e in g["m8"]}
    deaths = []
    for v in g["DD"]:
        cls, flags, m8d = attribute(v, g["det"].get(v), vdead[v], m8.get(v), g["decisions"], g["kicks"],
                                    dp.get("waiting"), ffs, rows_ff, rows_vic, mv_rows, legs_ev, drops_all, i2, cmds,
                                    g["cmd_ctx"])
        fc, fu, _r = m8_classify([dict(m8[v], death_step=vdead[v])] if v in m8 else [])
        deaths.append({"victim": v, "det": g["det"].get(v), "death": vdead[v],
                       "m8": "FC" if fc else "futile" if fu else "no-m8",
                       "m8d": m8d, "cls": cls, "flags": [k for k, val in flags.items() if val and k != "OTHER"]})
    g["deaths"] = deaths
    # ---- DIAG material: raises / strandings within 6 steps after an (a) step that RAN (22.2.4)
    live_a = [(r["step"], r["unit"]) for r in mv_rows if r.get("branch") == "approach_a"]
    raises = [(r["step"], r["unit"]) for r in mv_rows if r.get("rb_set")]
    o1 = [(c[0], c[4], c[3]) for c in cmds if c[2] == "unassign" and c[6] and "replacement" in str(c[5])
          and "blocked" in str(c[5])]
    strand = [(s, u, v) for s, u, v in o1 if ff_dead.get(u) is not None and 0 <= ff_dead[u] - s <= 15]
    near_a = []
    for s, u in sorted(set(live_a)):
        for t, w in raises:
            if w == u and s < t <= s + 6:
                near_a.append(["raise", u, s, t])
        for t, w, v in strand:
            if w == u and s < t <= s + 6:
                near_a.append(["stranding", u, s, t, v, ff_dead[u]])
    lists["near_a"] = near_a
    deferred = {}
    for x in g["decisions"]:
        if x.get("P") is False and not x.get("served"):
            deferred.setdefault(x["vid"], x["step"])
    lists["deferred_writeoffs"] = [[c[0], c[1], c[3], c[5], "deferred@%s" % deferred[c[3]]] for c in cmds
                                   if c[2] == "mark_unreachable" and c[6] and c[3] in deferred
                                   and c[0] >= deferred[c[3]]]
    # ---- REPORTED items, never gated: 16.8 G-B (a)(b)(d), G-T(b), M6, M3 (DPR's rb_figures, live=False); MU4 exposure
    gbn, gbl = gb_counts(dp.get("binders"), dp.get("invariant"))
    num.update(gbn)
    for k_, v_ in gbl.items():
        lists[k_] = v_[:20]
    gtn, lists["gt_b"] = gt_b_counts(rets)
    num.update(gtn)
    m6n, m6l = m6_counts(cmds, dp.get("writeoffs_avoided"))
    num.update(m6n)
    lists.update(m6l)
    rbn, rbl, rbc = rb_figures(dp.get("waiting"), dp.get("binders"), dp.get("m3a"), cmds, False)
    num.update(rbn)
    num["m3b"] = num.get("m3b_allowed", 0) + num.get("m3b_blocked", 0)
    lists["gb_f_blocked"] = list(rbl.get("gb_f_blocked") or [])[:20]
    g["rb_checks"] = {k_: (len(v_) if isinstance(v_, list) else v_) for k_, v_ in rbc.items()}
    g["rb_refused"] = list(rbc.get("refused") or [])[:6]
    g["rb_fail"] = rb_checks_fail(rbc)
    # MU4's ACTED legs: a fix step that RAN in G / N (a vetoed decision is today's step), the would-act shadow in arm 0
    g["mu4"], lists["mu4_strandings"], lists["mu4_deaths"] = mu4_exposure(
        rows_ff, cmds, g["cmd_ctx"], g["kicks"], mv_rows,
        [e for e in g["mv_events"] if not e.get("live") or ran_of(e)], ff_dead)
    g["num"], g["lists"] = num, lists
    return g


def idigest(d, path):
    """NEW: the identity material of a reference record (16.7's fields only): row hashes, the commands, eval, stdout
    with the new tags stripped - for the port identity against a urgency ud2 record."""
    so, marks, _vd, _tr = read_stdout_stripped(path)
    return {"h": {k: hashes(d.get(k) or []) for k in ROW_KINDS},
            "cmds": [list(c) for c in (d.get("dp") or {}).get("commands") or []], "eval": dict(d.get("eval") or {}),
            "so": so, "so_marks": marks}


# ================================================================================================ pair checks
def value_identity(gx, gy):
    """16.7 Z1 fields: every per-step row, the commands, eval, stdout with the new tags stripped. Returns
    (identical, D = first differing step from rows / commands or None, stdout upper bound U or None, what differs).
    U: when the stripped stdouts differ, the first step marker at or after the first differing line (either run) -
    the difference provably happened at or before U; markers lag, so stdout never places a difference later."""
    what, steps = [], []
    for k in sorted(set(gx.get("h") or {}) | set(gy.get("h") or {})):
        fd = first_div((gx.get("h") or {}).get(k) or [], (gy.get("h") or {}).get(k) or [])
        if fd is not None:
            what.append(k)
            steps.append(fd[0] + 1)
    if "cmds" in gx or "cmds" in gy:
        fd = first_div(gx.get("cmds") or [], gy.get("cmds") or [])
        if fd is not None:
            what.append("commands")
            s = [z[0] for z in (fd[1], fd[2]) if z is not None]
            if s:
                steps.append(min(s))
    for k in ("assigns", "unassigns"):
        if k in gx or k in gy:
            fd = first_div(gx.get(k) or [], gy.get(k) or [])
            if fd is not None:
                what.append(k)
                s = [z[0] for z in (fd[1], fd[2]) if z is not None]
                if s:
                    steps.append(min(s))
    if gx.get("eval") != gy.get("eval"):
        what.append("eval")
    ub = None
    sx, sy = gx.get("so"), gy.get("so")
    if sx is None or sy is None:
        if sx != sy:
            what.append("stdout (missing)")
    else:
        fd = first_div(sx, sy)
        if fd is not None:
            what.append("stdout")
            i = fd[0]
            cand = [m for marks in (gx.get("so_marks") or [], gy.get("so_marks") or [])
                    for m in [next((x for x in marks[i:] if x is not None), None)] if m is not None]
            ub = min(cand) if cand else None
    return not what, (min(steps) if steps else None), ub, what


def _rows_at(g, step):
    return [r for r in g.get("mv_rows") or [] if r["step"] == step]


def _shadow(r):
    return {k: r.get(k) for k in SHADOW_FIELDS}


GUARD_SHADOW = ("gA", "gB", "acted_g")


def shadow_diff(ra, rb, dry=False):
    """NEW: None when two d['mv'] rows agree on the pre-advance shadow fields, else the first differing path. dry (a
    urgency ud_probe v2 record, --smoke only): the guard's columns, which that record lacks, and fix (c)'s shadow (fc,
    a 'c' in acted), which this round's instrument does not compute, are not compared."""
    a, b = _shadow(ra), _shadow(rb)
    if dry:
        for x in (a, b):
            for k in GUARD_SHADOW + ("fc",):
                x.pop(k, None)
            x["acted"] = "".join(ch for ch in (x.get("acted") or "") if ch != "c")
    return None if a == b else first_path(a, b)


def z1_mov(gx, gy):
    """CHANGED (1d.6.2: ACTED = a LIVE fix step that RAN - after the guard, in G): Z1-M on the pair X (arm 0) -> Y (G or
    N): (i) no ran event in Y -> identical end to end (in G, a vetoed decision is today's step); (ii) identical before
    s* (the first step with a ran event); (iii) cross-arm shadow agreement at s* (X's would-act event with the same
    fix, unit, cell and today's shadow; X's rows at s* up to Y's first acting row equal on the pre-advance shadow fields,
    the instrument's guard verdicts included); (iv) an (a) cell change at s* -> the first difference at s* (no fix (c)
    in this round)."""
    ident, D, ub, what = value_identity(gx, gy)
    live = [e for e in gy.get("mv_events") or [] if e.get("live") and ran_of(e) and e.get("kind") in ("a", "b")]
    viol = []
    if not live:
        if not ident:
            viol.append("no fix step ran but the runs differ (%s; first at step %s)" % (what, D))
        return {"s": None, "ident": ident, "D": D, "viol": viol, "what": what, "first": None}
    s = min(int(e["step"]) for e in live)
    at = [e for e in live if int(e["step"]) == s]
    if D is not None and D < s:
        viol.append("first difference at step %s, before s* = %s (%s)" % (D, s, what))
    if ub is not None and ub < s:
        viol.append("stdout differs by step %s, before s* = %s" % (ub, s))
    xev = [e for e in gx.get("mv_events") or [] if int(e.get("step") or -1) == s and not e.get("live")]
    ry, rx = _rows_at(gy, s), _rows_at(gx, s)
    for e in at:
        k = e.get("kind")
        match = [x for x in xev if x.get("kind") == k and x.get("unit") == e.get("unit")
                 and x.get("cell") == e.get("cell") and x.get("today") == e.get("today")]
        pos = next((j for j, r in enumerate(ry) if r["_i"] == e.get("row")), None)
        if pos is None:
            viol.append("ran (%s) event at s* = %s without its row" % (k, s))
        else:
            dry = bool(gx.get("dry") or gy.get("dry"))
            for j in range(pos + 1):
                fp = shadow_diff(rx[j], ry[j], dry) if j < len(rx) else "missing in X"
                if fp:
                    viol.append("shadow fields differ at s* = %s, row %d (%s)" % (s, j, fp))
                    break
        if not match:
            viol.append("no matching would-act (%s) shadow in X at s* = %s (unit %s)" % (k, s, e.get("unit")))
    if any(e.get("kind") == "a" for e in at) and D != s:
        viol.append("an (a) cell change at s* = %s but the first difference is at %s" % (s, D))
    return {"s": s, "ident": ident, "D": D, "viol": viol, "what": what, "first": sorted({str(e.get("kind")) for e in at})}


def zg3(gn, gg):
    """NEW - Zg-3 (1d.6.2; 1d.2.5 G1) on the pair N (the fixes, the guard off) -> G (the same with the guard): identical
    up to the first VETO in G (the first ACTED event the MODEL vetoed); the first difference AT that step when it is an
    (a) veto (an acting (a) step's n differs from today's cell by definition) or a (b) veto whose today's retreat cell r
    is defined (today's shadow kind 'survival': r is not in B, n is); AT OR AFTER it otherwise (today's retreat would
    not move and its _move_toward fallback can reach n); at that step N ran the fix's step for the same decision (same
    unit, fix, cell and today's shadow), with the same instrument verdict, and N's rows up to G's vetoed row equal G's
    on the pre-advance shadow fields; a cell with no veto identical end to end. Fields: 16.7's (value_identity)."""
    ident, D, ub, what = value_identity(gn, gg)
    vet = [e for e in gg.get("mv_events") or [] if e.get("vetoed") and e.get("kind") in ("a", "b")]
    viol = []
    if not vet:
        if not ident:
            viol.append("no veto in G but G differs from N (%s; first at step %s)" % (what, D))
        return {"s": None, "ident": ident, "D": D, "viol": viol, "what": what, "first": None}
    s = min(int(e["step"]) for e in vet)
    at = [e for e in vet if int(e["step"]) == s]
    strict = any(e.get("kind") == "a" or (e.get("kind") == "b" and (e.get("today") or [None])[0] == "survival")
                 for e in at)
    if D is not None and D < s:
        viol.append("first difference at step %s, before the first veto at %s (%s)" % (D, s, what))
    if ub is not None and ub < s:
        viol.append("stdout differs by step %s, before the first veto at %s" % (ub, s))
    if strict and D != s:
        viol.append("an (a) veto / a (b) veto with today's retreat cell defined at %s, but the first difference is at "
                    "%s" % (s, D))
    nev = [e for e in gn.get("mv_events") or [] if int(e.get("step") or -1) == s]
    rn, rg = _rows_at(gn, s), _rows_at(gg, s)
    for e in at:
        match = [x for x in nev if x.get("kind") == e.get("kind") and x.get("unit") == e.get("unit")
                 and x.get("cell") == e.get("cell") and x.get("today") == e.get("today") and ran_of(x)]
        if not match:
            viol.append("N has no ran (%s) step of %s at the first veto %s with the same cell and today's shadow" % (
                e.get("kind"), e.get("unit"), s))
        elif (match[0].get("guard") or {}).get("admit") != (e.get("guard") or {}).get("admit"):
            viol.append("N's instrument verdict %s != G's %s at the first veto %s" % (
                (match[0].get("guard") or {}).get("admit"), (e.get("guard") or {}).get("admit"), s))
        pos = next((j for j, r in enumerate(rg) if r["_i"] == e.get("row")), None)
        if pos is None:
            viol.append("the vetoed (%s) event at %s has no row" % (e.get("kind"), s))
            continue
        dry = bool(gn.get("dry") or gg.get("dry"))
        for j in range(pos + 1):
            fp = shadow_diff(rn[j], rg[j], dry) if j < len(rn) else "missing in N"
            if fp:
                viol.append("shadow fields differ at the first veto %s, row %d (%s)" % (s, j, fp))
                break
    return {"s": s, "ident": ident, "D": D, "viol": viol, "what": what,
            "first": sorted({str(e.get("kind")) for e in at})}


# ================================================================================================ the screen pass
def slim(g):
    """Drop the heavy per-step material once the cell's pair checks are done."""
    for k in ("h", "so", "so_marks", "mv_rows", "cmd_ctx", "rel_ctx", "cmds", "rels", "mv_events"):
        g.pop(k, None)


_REF_SHAS: dict = {}


def ref_bad(path, opts):
    """CHANGED: a reference copy (outputs/_mvg_ref/) must exist and match outputs/_mvg_ref/_MANIFEST.sha256 ('<sha256>
    <name>' lines, '#' comments; LF-tolerant): returns None or the reason (a tooling problem - S1 is then INCOMPLETE,
    never a FAIL)."""
    if not os.path.exists(path):
        return "reference record missing %s" % os.path.basename(path)
    if opts.smoke:
        return None
    if not _REF_SHAS:
        try:
            with open(os.path.join(REF_DIR, "_MANIFEST.sha256"), encoding="utf-8") as fh:
                for ln in fh:
                    parts = ln.split()
                    if len(parts) == 2 and not ln.startswith("#"):
                        _REF_SHAS[os.path.normcase(os.path.join(REF_DIR, parts[1]))] = parts[0]
        except OSError:
            _REF_SHAS["__none__"] = ""
    for p in (path, stdout_path(path)):
        want = _REF_SHAS.get(os.path.normcase(p))
        if want is None:
            return "%s not listed in outputs/_mvg_ref/_MANIFEST.sha256" % os.path.basename(p)
        if want not in (sha_file(p), sha_lf_file(p)):
            return "%s differs from outputs/_mvg_ref/_MANIFEST.sha256" % os.path.basename(p)
    return None


def w2_name(arm, cell):
    """NEW: the W2 line name of a cell's arm (mvg<a><p><k>_<S>_<W>)."""
    return "%s%s%d_%s" % (ARM_TAG[arm], cell["p"], cell["k"], cell["key"])


def process(cells, opts, queues):
    """CHANGED: load, validate and digest every run; S1 material (W1 against the ud0 references, the port identity
    against ud2); the pair checks Z1-M (0 -> N, 0 -> G) and Zg-3 (N -> G); W3's inputs (W3Q.compact)."""
    recs = []
    for c in cells:
        rec = {"cell": c, "g": {}, "prov": {}, "crash": {}, "missing": [], "ident": None, "port": None, "stop": [],
               "pairs": {}, "ref_bad": None}
        rp = ref_path(c, opts)
        ref = None
        ref_arm = "N" if c["kind"] == "port" else "0"
        if rp is not None and ref_arm in c["arms"] and os.path.exists(run_path(ref_arm, c, opts)):
            rec["ref_bad"] = ref_bad(rp, opts)
            if rec["ref_bad"] is None:
                try:
                    ref = load_run(rp)
                except Exception as exc:      # noqa: BLE001
                    rec["ref_bad"] = "reference unreadable %r" % (exc,)
        for arm in c["arms"]:
            p = run_path(arm, c, opts)
            if not os.path.exists(p):
                rec["missing"].append(arm)
                continue
            try:
                d = load_run(p)
            except Exception as exc:          # noqa: BLE001
                rec["prov"][arm] = ["unreadable JSON %r" % (exc,)]
                continue
            line = None if opts.smoke else (queues.get(os.path.normcase(p)) or (None, None))[1]
            why, crash, stop = prov_run(d, p, line, None if opts.smoke else c, opts)
            rec["crash"][arm] = crash
            if stop:
                rec["stop"].append((arm, stop))
            if arm == ref_arm and ref is not None and c["kind"] in ("w1", "smoke"):
                if ref.get("dp_only") or d.get("dp_only"):
                    rec["ident"] = (["sd record missing (crash)"], "", [], "")
                else:
                    diff, note, other = ident_diff(ref, d, bool(opts.smoke))
                    fp = first_path(field_get(ref, diff[0]), field_get(d, diff[0]), diff[0]) if diff else ""
                    rec["ident"] = (diff, note, other, fp)
            g = digest(d, arm, "%s_%s" % (ARM_TAG[arm], c["id"]), p, c["set"],
                       censor=(int(d.get("steps_done") or 0) + 1) if opts.smoke else H + 1)
            if c["fresh"]:
                g["w3c"] = W3Q.compact(d)
                g["w2_name"] = w2_name(arm, c)
            if arm == ref_arm and ref is not None and c["kind"] == "port" and g.get("usable"):
                ident, D, _ub, what = value_identity(idigest(ref, rp), g)
                rec["port"] = {"ident": ident, "D": D, "what": what}
            rec["prov"][arm] = why + list(g.get("inst_problems") or [])
            rec["g"][arm] = g
            d = None
        ref = None
        G = rec["g"]
        for x, y, kind in (("0", "N", "mov"), ("0", "G", "mov"), ("N", "G", "zg3")):
            if x in G and y in G and G[x].get("usable") and G[y].get("usable"):
                rec["pairs"][(x, y)] = z1_mov(G[x], G[y]) if kind == "mov" else zg3(G[x], G[y])
        for g in G.values():
            slim(g)
        recs.append(rec)
    return recs


# ================================================================================================ sections
def masked(opts):
    """--smoke and --zeros-only print no outcome VALUE anywhere (22.6.3; 16.12; R2 m-2)."""
    return bool(getattr(opts, "smoke", None) or getattr(opts, "zeros_only", False))


def mask_text(s):
    """A failure instance with every number masked (masked modes): the kind of failure survives, no value does."""
    return re.sub(r"\d+(\.\d+)?", "#", str(s))


def path_only(fp):
    """The field path of a first_path() result, without the differing values or lengths (masked modes)."""
    return re.split(r": | \(", str(fp or ""), maxsplit=1)[0] + " differs"


def usable(rec, arm):
    g = rec["g"].get(arm)
    return g is not None and g.get("usable") and not rec["prov"].get(arm) and not rec["crash"].get(arm)


def sec_prov(recs, opts):
    """CHANGED (three arms; no evidence runs): the validity summary."""
    head("1 LOAD + PROV (16.6 as this round) - arms 0 (mvg0), G (mvg1), N (mvg2): W1 (arm 0, sets 1-2), the screen (sets "
         "5-6), the port identity (arm N, set 3 ring); files outputs/_sd_mvg<a><r|u><k>_<S>_<W>.json; validity "
         "against the frozen queues")
    st = {"missing": [], "invalid": [], "gate": [], "stop": [], "seed": []}
    for arm in ARMS:
        sub = [r for r in recs if arm in r["cell"]["arms"]]
        if not sub:
            continue
        present = sum(1 for r in sub if arm in r["g"])
        miss = [r["cell"]["id"] for r in sub if arm in r["missing"]]
        inv = [(r["cell"]["id"], r["prov"][arm]) for r in sub if r["prov"].get(arm)]
        crash = [(r["cell"]["id"], r["crash"][arm]) for r in sub if r["crash"].get(arm)]
        out("  %-3s present %3d / %d | missing %d | INVALID %d | crash / early stop %d" % (
            arm, present, len(sub), len(miss), len(inv), len(crash)))
        for cid, why in inv:
            out("       INVALID %s %s: %s" % (arm, cid, "; ".join(str(w) for w in why[:8])))
        for cid in miss[:64]:
            out("       MISSING %s %s" % (arm, cid))
        for cid, why in crash:
            out("       %s %s %s: %s" % ("STOP (base defect: an arm-0 crash, 16.6)" if arm == "0" else "GATE FAILURE (Z6)",
                                        arm, cid, mask_text(why) if masked(opts) else why))
        st["missing"] += [(arm, c) for c in miss]
        st["invalid"] += [(arm, c, w) for c, w in inv]
        (st["stop"] if arm == "0" else st["gate"]).extend((arm, c, w) for c, w in crash)
    for r in recs:
        for arm, why in r["stop"]:
            st["seed"].append((arm, r["cell"]["id"], why))
            out("       STOP (seed-selector rule) %s %s: %s" % (arm, r["cell"]["id"], why))
    nou1 = [g["label"] for r in recs for g in r["g"].values() if g.get("u1_shadow_error")]
    out("  U1 shadow (22.9's U1 class, 1d.8 (5)): %s" % ("loaded in every run" if not nou1 else
                                                        "NOT COMPUTED in %d run(s), e.g. %s" % (len(nou1), nou1[:4])))
    nodet = [g["label"] for r in fresh_recs(recs) for g in r["g"].values() if g.get("usable") and not any(
        v is not None for v in (g.get("det") or {}).values()) and g.get("eval", {}).get("never_detected", 0) == 0]
    if nodet:
        out("  WARNING fresh runs without any stdout detection: %s" % nodet[:8])
    return st


def w2_records_gate(cells, opts, queues):
    """NEW (review A-4): section 1's validity of the W2 records of `cells` exactly as the analysis reads them -
    process() (prov_run against the frozen queues: the run line, the .argv signature, the head rule, the recorded
    source and instrument shas at --head, CRN, the instrument's errors and schemas, the guard bookkeeping, the
    _survival_move replica) and sec_prov(); printed in the masked mode of --zeros-only (no outcome value). OK iff all 3
    arms of every cell are present and readable, none is INVALID and no run's scenario / wind / seed differs from its
    frozen cell. A crash is not a refusal (Z6 material: the W3 rule makes its cell-arm UNCOMPUTABLE). Returns (ok,
    problems)."""
    recs = process(cells, opts, queues)
    st = sec_prov(recs, opts)
    want = 3 * len(cells)
    present = sum(1 for r in recs for arm in ARMS if arm in r["g"])
    probs = []
    if present != want:
        probs.append("%d of %d W2 records present and readable" % (present, want))
    probs += ["MISSING %s %s" % (a, c) for a, c in st["missing"]]
    probs += ["INVALID %s %s: %s" % (a, c, "; ".join(str(w) for w in why[:4])) for a, c, why in st["invalid"]]
    probs += ["SEED MISMATCH %s %s: %s" % x for x in st["seed"]]
    return not probs, probs


def w2_gate(head, notes):
    """NEW (review A-4) - the W3 generator's precondition (outputs/_mvg_w3_queue.py build): the analyzer's own header
    checks (section 0 with --head and --part2-notes: the hashed sections, the verbatim / module checks, the Part 2d
    notes, the mutation record at --head; --head must descend from the base) and section 1's validity of all 192 W2
    records (w2_records_gate on the 64 screen cells). Prints sections 0-1 only, masked; never an outcome. Returns (ok,
    problems)."""
    opts = argparse.Namespace(head=head, part2_notes=notes, smoke=None, smoke_cell=None, smoke_files={},
                              zeros_only=True, allow_incomplete=False, out=None)
    if not head or not notes:
        return False, ["--head and --part2-notes are both required"]
    if not sec_header(opts):
        return False, ["the analyzer's header checks REFUSED (section 0 above)"]
    frozen = load_seeds()
    if frozen is None:
        return False, ["outputs/_mvg_seeds.txt is unusable"]
    cells = [c for c in screen_cells(frozen, opts) if c["kind"] == "screen"]
    if len(cells) != 64:
        return False, ["%d screen cells, 64 expected" % len(cells)]
    return w2_records_gate(cells, opts, load_queues())


def sec_z0(recs, opts):
    """CHANGED (1d.6.1 S1 = Z0 on W1 + the port identity of 1d.8 (11)); no value of sets 1-4 is printed."""
    head("2 S1 IDENTITY (1d.6.1 S1) - Z0 (W1, 1d.9): mvg0 on sets 1-2 == the urgency round's ud0 records "
         "(outputs/_mvg_ref/, ruling W-6 (a)) on DPR's G-ID fields (_fx3r_analyze FIELDS + every mf2 section but probe "
         "+ every dp field but %s), and dp0's M8 reproduced; the PORT IDENTITY (1d.8 (11)): mvg2 on the 8 set-3 ring "
         "cells == ud2 on 16.7's fields. Code identity only: field paths, never values" % "/".join(J_ONLY))
    comp = [r for r in recs if r["ident"] is not None]
    same = sum(1 for r in comp if not r["ident"][0])
    for r in recs:
        if r.get("ref_bad"):
            out("    %s reference NOT USABLE (S1 incomplete, a tooling matter): %s" % (r["cell"]["id"], r["ref_bad"]))
    for r in comp:
        diff, note, other, fp = r["ident"]
        if diff:
            out("    %s DIFFER %s | first path %s" % (r["cell"]["id"], diff[:8], path_only(fp)))
        if note:
            out("    %s note: %s" % (r["cell"]["id"], note))
        if other:
            out("    %s other sections differing (reported): %s" % (r["cell"]["id"], other[:6]))
    smoke_w1 = sum(1 for r in recs if r["cell"]["kind"] == "smoke" and ref_path(r["cell"], opts))
    want = smoke_w1 if opts.smoke else 64
    probe_ok = same == len(comp) == want
    out("  Z0 W1 cells: %d / %d identical (%d compared, %d expected)  => %s" % (
        same, len(comp), len(comp), want, "PASS" if probe_ok else ("FAIL" if same < len(comp) else "INCOMPLETE")))
    m8 = {}
    for s in IN_SAMPLE:
        fc = fu = n = 0
        for r in recs:
            if r["cell"]["set"] != s or r["cell"]["kind"] != "w1" or not usable(r, "0"):
                continue
            n += 1
            a, b, _rows = m8_classify(r["g"]["0"]["m8"])
            fc += a
            fu += b
        m8[s] = (fc, fu, n)
    if opts.smoke:
        m8_ok, m8_state = True, "PASS"
        out("  mvg0 M8 reproduction: NOT RUN (smoke)")
    else:
        m8_state = m8_check(m8)
        m8_ok = m8_state == "PASS"
        out("  mvg0 M8 reproduction of dp0's (13 deaths, 11 FC) over %d + %d runs  => %s (counts never printed: sets 1-2)"
            % (m8["set1"][2], m8["set2"][2], m8_state))
    ports = [r for r in recs if r["cell"]["kind"] == "port"]
    p_same = sum(1 for r in ports if r["port"] is not None and r["port"]["ident"])
    p_cmp = sum(1 for r in ports if r["port"] is not None)
    for r in ports:
        if r["port"] is not None and not r["port"]["ident"]:
            out("    port %s DIFFERS from ud2 in %s, first at step %s" % (r["cell"]["id"], r["port"]["what"][:6],
                                                                       r["port"]["D"]))
    p_want = 0 if opts.smoke else len(PORT_KEYS)
    port_ok = p_same == p_cmp == p_want
    out("  PORT IDENTITY: %d / %d identical (%d compared, %d expected)  => %s" % (
        p_same, p_cmp, p_cmp, p_want, "PASS" if port_ok else ("FAIL" if p_same < p_cmp else "INCOMPLETE")))
    fail = same < len(comp) or m8_state == "FAIL" or p_same < p_cmp
    s1 = probe_ok and m8_ok and port_ok
    out("  S1 IDENTITY => %s" % ("PASS" if s1 else "FAIL" if fail else "INCOMPLETE"))
    return {"pass": s1, "fail": fail}


def zero_owners(zero, arm):
    """CHANGED (1d.6.2): any failure in ARM 0 of Z0, Z5, Z-RB, a crash (Z6) or a shadow mismatch (SM) is a STOP;
    movement-owned zeros (Z1-M Z2-M Z-RB Zm-a Zm-b Z-S) bind in G AND N ({MOV}: the same code ships in both); guard-owned
    zeros (Zg-1 Zg-2 Zg-3) bind in G ({GUARD}; a guard row elsewhere is a shadow, REPORTED); Z5 / Z6 are owned by the
    switches of the arm in which they occur (G: MOV + GUARD; N: MOV). A failure of a movement-owned zero or of Z6 in G
    OR N, or of a guard zero in G, fails S2 of FULL(0 -> G)."""
    sw = ARM_SW.get(arm, set())
    if zero == "SM":
        return "STOP" if arm == "0" else "REPORTED"
    if arm == "0":
        return "STOP" if zero in ("Z5", "Z-RB", "Z6", "Z0") else "REPORTED"
    if zero in GUARD_ZEROS:
        return {"GUARD"} if "GUARD" in sw else "REPORTED"
    if zero in MOV_ZEROS:
        return {"MOV"} if "MOV" in sw else "REPORTED"
    return set(sw)


def sec_zeros(recs, st, opts):
    """CHANGED (1d.6.2's zeros and owners)."""
    head("3 STRUCTURAL ZEROS (1d.6.2) - exact, on every run of the round; owners: movement (Z1-M Z2-M Z-RB Zm-a Zm-b Z-S) "
         "in G AND N, the guard (Zg-1 two-sided, Zg-2, Zg-3) in G, Z5 / Z6 by the arm's switches - each fails S2 of "
         "FULL(0 -> G); any arm-0 failure STOPS")
    fails = []                                  # (zero, arm, where, owners, detail)
    counts = collections.Counter()
    checked = collections.Counter()

    def add(zero, arm, where, items):
        checked[(zero, arm)] += 1
        for it in items:
            counts[(zero, arm)] += 1
            fails.append((zero, arm, where, zero_owners(zero, arm), it))

    for r in recs:
        for arm, g in r["g"].items():
            if not g.get("usable"):
                continue
            for zero, items in (g.get("Z") or {}).items():
                add(zero, arm, "%s %s" % (arm, r["cell"]["id"]), items)
        for (x, y), res in r["pairs"].items():
            add("Zg-3" if (x, y) == ("N", "G") else "Z1-M", y, "%s->%s %s" % (x, y, r["cell"]["id"]), res["viol"])
    for arm, cid, why in st["gate"] + st["stop"]:
        add("Z6", arm if arm in ARM_SW else "0", "%s %s" % (arm, cid), [why])
    for z in ZERO_ORDER:
        cells = " | ".join("%s %d/%d" % (a, counts[(z, a)], checked[(z, a)]) for a in ARMS if checked[(z, a)])
        out("  %-5s violations / runs-or-pairs checked: %s" % (z, cells or "not applicable"))
    out("  (ud.shadow_mismatch is behaviour, never INVALID: in G a guard-text row is a Zg-1 instance and any other "
        "(a) / (b) row or live disagreement a Z1-M item (v) instance; in N every such row is Z1-M; SM = any row in arm 0 "
        "(STOP) or a kick / unknown row elsewhere (reported); the guard evaluated where it is off: Z1-M (N) / SM (0))")
    out("  (Zg-1 also holds the cross-check of every guard row: the repo function movement_paths.stranding_guard's "
        "tuple (mp_verdict) against the instrument's frozen-function replica - a Zg-1 failure in G, reported in 0 / N)")
    mask = masked(opts)
    for zero, arm, where, owners, it in fails:
        out("    %s %-5s %-30s owner %s: %s" % ("STOP" if owners == "STOP" else "FAIL" if owners != "REPORTED"
                                              else "rep.", zero, where, owners if isinstance(owners, str)
                                              else "+".join(sorted(owners)),
                                              mask_text(str(it)[:220]) if mask else str(it)[:220]))
    kf = [(a, r["cell"]["id"], x) for r in recs for a, g in r["g"].items() if g.get("usable")
          for x in (g.get("lists") or {}).get("kick_flag_bad", [])]
    out("  reported tooling check: the U1 shadow's kick flags (index_wb, u1_wb, div_shadow, divergent) inconsistent "
        "with acc / bound: %d%s" % (len(kf), "" if not kf else " %s" % [mask_text(x) if mask else x for x in kf[:6]]))
    for (x, y) in (("0", "N"), ("0", "G"), ("N", "G")):
        prs = [r["pairs"][(x, y)] for r in recs if (x, y) in r["pairs"]]
        if not prs:
            continue
        acted = sum(1 for p in prs if p["s"] is not None)
        at_s = sum(1 for p in prs if p["s"] is not None and p["D"] == p["s"])
        if (x, y) == ("N", "G"):
            out("  Zg-3 N->G: %d pairs, %d with a veto in G, first difference at the first veto in %d, identical end "
                "to end %d" % (len(prs), acted, at_s, sum(1 for p in prs if p["ident"])))
            continue
        out("  Z1-M %s->%s: %d pairs, %d with a fix step that ran, first difference at s* in %d, identical end to end "
            "%d" % (x, y, len(prs), acted, at_s, sum(1 for p in prs if p["ident"])))
        firsts = collections.Counter("+".join(p.get("first") or []) for p in prs if p["s"] is not None)
        out("      first acting fix at s*: %s" % dict(firsts))
    stop = [f for f in fails if f[3] == "STOP"]
    return {"fails": fails, "stop": stop}


def fresh_recs(recs):
    return [r for r in recs if r["cell"]["fresh"]]


# ================================================================================================ W3 (1d.13.2-1d.13.3)
Q_W2 = os.path.join(HERE, "_mvg_q_w2.jsonl")


def ko_first(events, rules):
    """NEW: the first of X's decisions a knockout CHANGES - for kinds a / b the first matched ACTED event that RAN, for
    g the first matched VETO (the _mvg_replay.py match: unit U, '*' or '!U'; from <= step <= to) - as [step, unit, kind]
    (kind 'g' for a veto), or None. The replay equals X before it, so that decision must be in its ko_applied."""
    cand = []
    for st, u, k, ran, vet in events:
        for r in rules:
            uu = r.get("unit", "*")
            hit = uu == "*" or (uu.startswith("!") and u != uu[1:]) or u == uu
            if not hit or not int(r.get("from", 0)) <= st <= int(r.get("to", 10 ** 9)):
                continue
            if ran and k in r.get("kinds", "ab"):
                cand.append([st, u, k])
            if vet and "g" in r.get("kinds", "ab"):
                cand.append([st, u, "g"])
    return min(cand) if cand else None


def r0_reproduces(x, r0, x_stdout, r0_stdout):
    """NEW (1d.13.2): R0 must reproduce X's record exactly - every per-step row (rows_ff / vic / uav / dec / trig), the
    commands, the movement events, eval and stdout. Returns the differing fields ([] = reproduces)."""
    diff = [k for k in ROW_KINDS if x.get(k) != r0.get(k)]
    if (x.get("dp") or {}).get("commands") != (r0.get("dp") or {}).get("commands"):
        diff.append("dp.commands")
    if x.get("mv_events") != r0.get("mv_events"):
        diff.append("mv_events")
    if x.get("eval") != r0.get("eval"):
        diff.append("eval")
    if x_stdout is None or x_stdout != r0_stdout:
        diff.append("stdout")
    return diff


def boards_problems(line, head=None):
    """NEW: a W3 replay's boards file exists, carries the line's knockout rules and argv, and recorded no error; with
    head (--head; review I-9) it names the committed tools: replay_sha / probe_sha (the sha256 of outputs/_mvg_replay.py
    / outputs/_mvg_probe.py's LF-normalised bytes, as the replay tool read them) equal those files' at --head."""
    argv = line["argv"]
    own = argv[1:argv.index("--")] if "--" in argv else []
    bpath = own[own.index("--boards") + 1] if "--boards" in own else None
    if bpath is None or not os.path.exists(bpath):
        return ["boards file missing"], None
    try:
        b = load_json(bpath)
    except Exception as exc:                 # noqa: BLE001
        return ["boards file unreadable %r" % (exc,)], None
    rules = json.loads(own[own.index("--ko") + 1]) if "--ko" in own else []
    probs = []
    if b.get("ko_rules") != rules:
        probs.append("boards ko_rules %s != the line's %s" % (b.get("ko_rules"), rules))
    if b.get("argv") != argv[1:]:
        probs.append("boards argv differs from the line")
    if b.get("errors"):
        probs.append("boards recorder errors %s" % b["errors"][:2])
    if head:
        for key, rel in (("replay_sha", REPLAY_REL), ("probe_sha", PROBE_REL)):
            want = lf_sha_at(head, rel)
            if want is None or b.get(key) != want:
                probs.append("ran an uncommitted tool: boards %s %s is not %s at %s (LF %s)" % (
                    key, str(b.get(key))[:16], rel, head[:10], str(want)[:16]))
    return probs, b


def _text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def w3_validity(recs, opts):
    """NEW (1d.13.2-1d.13.3): the W3 queue and candidates re-derived from the W2 records by outputs/_mvg_w3_queue.py's
    frozen rule (REFUSED when they differ, or when a W2 input changed since the queue was generated); every replay
    present and valid (16.6 as this round, plus its boards file); every R0 checked against its W2 record; per candidate
    the knockout evidence. Prints validity only (no outcome); returns the evidence for section 7 and the decision."""
    head("W3 VALIDITY (1d.13.2-1d.13.3) - the per-death attribution replays: the queue re-derived by the frozen rule "
         "(outputs/_mvg_w3_queue.py) from the W2 records; every replay present and valid; every R0 against its W2 record")
    res = {"state": None, "complete": False, "refused": False, "items": {"G": [], "N": []}, "same": [],
           "uncomputable": [], "r0": {}, "conflicts": [], "n_lines": 0}
    comp, bad = {}, []
    for r in fresh_recs(recs):
        for arm in ARMS:
            g = r["g"].get(arm)
            if g is None or r["prov"].get(arm) or "w3c" not in g:
                bad.append("%s %s" % (arm, r["cell"]["id"]))
            else:
                comp[g["w2_name"]] = g["w3c"]
    want = 3 * len(fresh_recs(recs))         # 192 on the screen's 64 fresh cells
    if bad or not want or len(comp) != want:
        res["state"] = "W2 incomplete or INVALID (%d of %d runs not usable, e.g. %s): W3 is not evaluated" % (
            want - len(comp), want, bad[:3])
        out("  " + res["state"])
        return res
    if not os.path.exists(W3Q.Q_W3) and not os.path.exists(W3Q.CANDS):
        res["state"] = "W3 NOT GENERATED (outputs/_mvg_w3_queue.py build, after the W2 wave check)"
        out("  " + res["state"])
        return res
    problems = []
    try:
        frozen = load_json(W3Q.CANDS)
        with open(W3Q.Q_W3, "rb") as fh:
            q_raw = fh.read().replace(b"\r\n", b"\n")
        with open(Q_W2, "rb") as fh:
            w2_raw = fh.read().replace(b"\r\n", b"\n")
        w2_lines = [json.loads(x) for x in w2_raw.decode("utf-8").splitlines() if x.strip()]
        doc, lines = W3Q.build_plan(w2_lines, comp)
    except (Exception, SystemExit) as exc:   # noqa: BLE001 - a W3 that cannot be re-derived is REFUSED
        problems.append("the W3 files or the W2 queue cannot be read / re-derived: %r" % (exc,))
        frozen, lines, doc = {}, [], {}
    w2_out = {ln["name"]: ln["out"] for ln in w2_lines} if not problems else {}
    if not problems:
        norm = lambda v: json.loads(json.dumps(v, sort_keys=True))                   # noqa: E731
        for k in ("version", "rule", "entries", "uncomputable", "counts"):
            if norm(frozen.get(k)) != norm(doc.get(k)):
                problems.append("candidates file field %r differs from the frozen rule's re-derivation" % k)
        if q_raw != "".join(json.dumps(ln) + "\n" for ln in lines).encode("utf-8"):
            problems.append("outputs/_mvg_q_w3.jsonl differs from the frozen rule's re-derivation")
        inp = frozen.get("inputs") or {}
        if inp.get("w2_queue_sha256") != hashlib.sha256(w2_raw).hexdigest():
            problems.append("the W2 queue changed since W3 was generated")
        shas = inp.get("records_sha256") or {}
        changed = [ln["name"] for ln in w2_lines if shas.get(ln["name"]) != (sha_file(ln["out"]) if os.path.exists(
            ln["out"]) else None)]
        if changed:
            problems.append("%d W2 record(s) differ from those W3 was generated from, e.g. %s" % (len(changed),
                                                                                                 changed[:4]))
    if problems:
        res["refused"] = True
        res["state"] = "REFUSED: " + "; ".join(problems)
        out("  REFUSED: the W3 queue is not the one the frozen rule gives on these W2 records (1d.13.3):")
        for p in problems:
            out("    " + p)
        return res
    res["n_lines"] = len(lines)
    res["uncomputable"] = list(frozen.get("uncomputable") or [])
    by_name = {ln["name"]: ln for ln in lines}
    cells = {r["cell"]["id"]: r for r in fresh_recs(recs)}
    owner = {x["name"]: e for e in frozen.get("entries") or [] for x in e["replays"]}
    loaded, missing, invalid = {}, [], []

    def load_w3(name):
        """One replay: None when missing or INVALID (listed), else its rows_ff, completeness, ko_applied and (R0) the
        record and stdout for the reproduction check."""
        if name in loaded:
            return loaded[name]
        line = by_name[name]
        p = line["out"]
        loaded[name] = None
        if not os.path.exists(p):
            missing.append(name)
            return None
        try:
            d = load_run(p)
        except Exception as exc:              # noqa: BLE001
            invalid.append((name, ["unreadable JSON %r" % (exc,)]))
            return None
        why, crash, stop = prov_run(d, p, line, cells[owner[name]["cell"]]["cell"], opts)
        bprobs, b = boards_problems(line, getattr(opts, "head", None))
        if why or bprobs or stop:
            invalid.append((name, why + bprobs + ([stop] if stop else [])))
            return None
        is_r0 = name.endswith("_R0")
        rows = d.get("rows_ff") or []
        # COMPLETE (review A-5): not a crash by run_crash (not crashed, chain exit 0, stopped at its --steps or AT its
        # terminal step) and its rows are the whole run (one per step done): its rows end where the run ended
        loaded[name] = {"rows_ff": rows, "complete": crash is None and len(rows) == d.get("steps_done"),
                        "ko_applied": (b or {}).get("ko_applied") or [], "d": d if is_r0 else None,
                        "stdout": _text(stdout_path(p)) if is_r0 else None}
        return loaded[name]

    for e in frozen.get("entries") or []:
        r = cells.get(e["cell"])
        gx, g0 = r["g"][e["arm"]], r["g"]["0"]
        for s_ in e["same"]:
            u = s_["unit"]
            res["same"].append({"cell": e["cell"], "set": e["set"], "arm": e["arm"], "unit": u, "t": s_["t"],
                                "c_none": g0["dead_unit_h"].get(u) == gx["dead_unit_h"].get(u)})
        if not (e["A"] or e["B"]):
            continue
        r0name = next(x["name"] for x in e["replays"] if x["suffix"] == "R0")
        r0 = load_w3(r0name)
        r0_diff = None
        if r0 is not None:
            xp = w2_out[e["x"]]
            try:
                xd = load_json(xp)
                r0_diff = r0_reproduces(xd, r0["d"], _text(stdout_path(xp)), r0["stdout"])
            except Exception as exc:          # noqa: BLE001
                r0_diff = ["the W2 record unreadable %r" % (exc,)]
            xd = None
            r0["d"] = None
        res["r0"][(e["cell"], e["arm"])] = r0_diff
        events = gx["w3c"]["events"]
        rules_of = {x["name"]: x["rules"] for x in e["replays"]}
        for kind in ("A", "B"):
            for c in e[kind]:
                u, t = c["unit"], c["t"]
                x_dead = gx["ff_dead"].get(u)
                other = c.get("t0") if kind == "A" else c.get("tx")
                it = {"cell": e["cell"], "set": e["set"], "arm": e["arm"], "kind": kind, "unit": u, "t": t,
                      "other": other, "never_other": other is None, "resolved": True, "why": [],
                      "chain": gx["death_chain"].get(u) if kind == "A" else None}
                if r0_diff is None:
                    it["resolved"] = False
                    it["why"].append("R0 missing or INVALID")
                elif r0_diff:
                    it["resolved"] = False
                    it["why"].append("R0 does not reproduce X (%s)" % r0_diff[:4])
                for ko in (W3Q.KO_A if kind == "A" else W3Q.KO_B):
                    if ko == "KOguard" and e["arm"] != "G":
                        continue
                    name = c["ko"].get(ko)
                    key = {"KOown": "own", "KOothers": "others", "KOlast": "last", "KOguard": "guard"}[ko]
                    if name is None:
                        # not run - its decision set is empty in X: it equals R0, and R0's (= X's) outcome is used: an
                        # (A) unit is dead at t in X, a (B) unit alive at t (1d.13.2)
                        it[key] = kind == "B"
                        it[key + "_dies"] = x_dead is not None
                        it[key + "_run"] = False
                        continue
                    rec = load_w3(name)
                    it[key + "_run"] = True
                    if rec is None:
                        it[key], it[key + "_dies"] = None, None
                        if ko in ("KOown", "KOothers"):
                            it["resolved"] = False
                            it["why"].append("%s missing or INVALID" % ko)
                        continue
                    it[key] = alive_at(rec["rows_ff"], u, t, rec["complete"])
                    dth = first_death(rec["rows_ff"], u)
                    it[key + "_dies"] = True if dth is not None else (False if rec["complete"] else None)
                    first = ko_first(events, rules_of[name])
                    applied = [list(a[:3]) for a in rec["ko_applied"]]
                    if first is not None and first not in applied:
                        res["conflicts"].append([name, first])
                        if ko in ("KOown", "KOothers"):
                            it["resolved"] = False
                            it["why"].append("%s did not knock out X's first changed decision %s" % (ko, first))
                        else:
                            it[key] = None            # a reported knockout with conflicting evidence: unknown
                    if it[key] is None and ko in ("KOown", "KOothers"):
                        it["resolved"] = False
                        it["why"].append("%s stopped before step %s" % (ko, t))
                res["items"][e["arm"]].append(it)
    for name in by_name:                     # every line is read and validated, referenced or not
        load_w3(name)
    n_r0 = len(res["r0"])
    bad_r0 = {k: v for k, v in res["r0"].items() if v}
    out("  W3 queue: %d lines (frozen, identical to the rule's re-derivation from the W2 records); cell-arms with a "
        "candidate %d; uncomputable cell-arms %d%s" % (len(lines), n_r0, len(res["uncomputable"]),
                                                       "" if not res["uncomputable"] else " %s" % [
                                                           (u["cell"], u["arm"]) for u in res["uncomputable"][:6]]))
    out("  replays present and valid %d / %d | missing %d | INVALID %d" % (
        sum(1 for v in loaded.values() if v is not None), len(lines), len(missing), len(invalid)))
    for name, why in invalid:
        out("       INVALID %s: %s" % (name, "; ".join(str(w) for w in why[:6])))
    for name in missing[:40]:
        out("       MISSING %s" % name)
    out("  R0 reproduces its W2 record (rows, commands, movement events, eval, stdout): %d / %d%s" % (
        sum(1 for v in res["r0"].values() if v == []), n_r0,
        "" if not bad_r0 else " - NOT: %s (their candidates are UNRESOLVED)" % [
            (k, v if v is None else v[:4]) for k, v in sorted(bad_r0.items())][:8]))
    out("  knockout evidence conflicts (a replay that did not knock out X's first changed decision): %s" % (
        res["conflicts"][:8] or "none"))
    res["complete"] = not missing and not invalid
    res["state"] = "COMPLETE" if res["complete"] else "INCOMPLETE (%d missing, %d INVALID replays)" % (len(missing),
                                                                                                      len(invalid))
    out("  W3 => %s" % res["state"])
    if res["complete"]:
        res["l4"] = {}
        for arm in ("G", "N"):
            l4 = l4_counts(res["items"][arm])
            if any(u["arm"] == arm for u in res["uncomputable"]):
                l4["uncomputable"] = True
                l4["fail"] = True             # a hard clause never passes on missing evidence (a crashed W2 run)
            res["l4"][arm] = l4
    return res


# ================================================================================================ 4 COMPARISONS
L4_KEY = "L4 CAUSED vs PREVENTED (W3)"


def comparison(recs, x, y, zfails, s1_pass, w3=None):
    """CHANGED: one comparison X -> Y on the fresh cells (sets 5-6): S2 (zeros owned by the switches Y adds), S3, S4,
    S5 (F1 as R2, L2, L3, the 24 sign-tested counts with Holm; for 0 -> G and 0 -> N also L4 from W3: CAUSED(Y) >
    PREVENTED(Y) fails - 1d.13.2; an incomplete W3 leaves S5 and the verdict INCOMPLETE), S6 (R and p99 per fix-code
    call: the fixes' choices and the guard as its own call)."""
    cells = [r for r in fresh_recs(recs) if usable(r, x) and usable(r, y)]
    nx = {r["cell"]["id"]: r["g"][x]["num"] for r in cells}
    ny = {r["cell"]["id"]: r["g"][y]["num"] for r in cells}
    cset = {r["cell"]["id"]: r["cell"]["set"] for r in cells}
    diverged = {r["cell"]["id"] for r in cells if (x, y) in r["pairs"] and not r["pairs"][(x, y)]["ident"]}
    res = compare_counts(nx, ny, cset, diverged)
    res["S3"] = s3_rule({c: n["DD"] for c, n in nx.items()}, {c: n["DD"] for c, n in ny.items()}, cset)
    res["L4_incomplete"] = False
    if x == "0" and y in ("G", "N"):
        l4 = ((w3 or {}).get("l4") or {}).get(y)
        if l4 is None:
            res["literal"][L4_KEY] = {"x": None, "y": None, "fail": False, "l4": None}
            res["L4_incomplete"] = True
        else:
            res["literal"][L4_KEY] = {"x": l4["prevented"], "y": l4["caused"], "fail": bool(l4["fail"]), "l4": l4}
        res["lit_fail"] = [k for k, v in res["literal"].items() if v["fail"]]
        res["S5"] = not res["lit_fail"] and not res["sig_fail"]
    added = ADDED[(x, y)]
    s2f = s2_for(zfails, added)
    res["S2"] = not s2f
    res["S2_fails"] = s2f
    gy = [r["g"][y] for r in cells]
    rr = [g["fix_ms"] / (g["wall_s"] * 1000.0) for g in gy if g.get("wall_s")]
    s6 = {}
    if "MOV" in added:
        s6["FIX"] = s6_rule(rr, [ms for g in gy for f in ("a", "b") for ms in (g.get("fix_calls") or {}).get(f) or []])
    if "GUARD" in added:
        s6["GUARD"] = s6_rule(rr, [ms for g in gy for ms in (g.get("fix_calls") or {}).get("g") or []])
    res["S6"] = all(v["pass"] for v in s6.values())
    res["S6_detail"] = s6
    if res["L4_incomplete"]:
        res["full"] = "INCOMPLETE (W3: L4 not established)"
    else:
        res["full"] = full_verdict(s1_pass, res["S2"], res["S3"]["pass"], res["S4"], res["S5"], res["S6"])
    res["harmless"] = res["S2"] and res["S4"] and res["S5"] and not res["L4_incomplete"]
    res["n_cells"] = len(cells)
    res["cells"] = cells
    res["diverged_cells"] = diverged
    return res


def print_comparison(x, y, res, label="FRESH sets 5-6"):
    """CHANGED (F1 read as R2 with its per-set detail; the R0 reading reported; L4)."""
    out("-- %s -> %s (%s): %d paired cells, %d diverged (Y not value-identical to X on 16.7's fields)" % (
        x, y, label, res["n_cells"], len(res["diverged_cells"])))
    for k, v in res["literal"].items():
        if k == L4_KEY:
            if v["l4"] is None:
                out("    LITERAL %-22s INCOMPLETE (W3 not complete - no verdict, 1d.13.3)" % k)
            else:
                l4 = v["l4"]
                out("    LITERAL %-22s CAUSED %d vs PREVENTED %d (per set %s)%s  %s" % (
                    k, l4["caused"], l4["prevented"], {s: "%d / %d" % tuple(cp) for s, cp in l4["per_set"].items()},
                    " - uncomputable cell-arms (a crashed W2 run)" if l4.get("uncomputable") else "",
                    "FAIL" if v["fail"] else "ok"))
            continue
        if k.startswith("F1 R2"):
            r2 = v["r2"]
            out("    LITERAL %-22s %4d -> %4d  diverged cells: n+ %d n- %d, one-sided exact sign test p %.5f (fails at "
                "<= %.2f)  %s | up %s down %s" % (k, v["x"], v["y"], r2["n_plus"], r2["n_minus"], r2["p"], F1_ALPHA,
                                                 "FAIL" if v["fail"] else "ok", r2["up"][:6], r2["down"][:6]))
            continue
        out("    LITERAL %-22s %4d -> %4d  %s" % (k, v["x"], v["y"], "FAIL" if v["fail"] else "ok"))
    out("    REPORTED beside F1 (never gating): by SEED (ring + uniform summed; R2s) %s | the R0 reading (pooled AND each "
        "set literal) %s" % (
            {s: "n+ %d n- %d p %.4f" % (v["n_plus"], v["n_minus"], v["p"]) for s, v in res["r2s"].items()},
            "FAIL" if res["r0"]["fail"] else "holds"))
    out("    SIGN-TESTED (23.2; Holm over m = 24, alpha 0.05):")
    for k, label_ in SIGN_KEYS:
        v = res["sign"][k]
        out("      %-50s %4d -> %4d | n+ %2d n- %2d p %.5f | rank %2d thr %.5f %s%s" % (
            label_, v["x"], v["y"], v["n_plus"], v["n_minus"], v["p"], v["rank"], v["threshold"],
            "REJECTED (FAIL)" if v["rejected"] else "not rejected",
            " | rising in %s" % v["rising"][:6] if v["rising"] else ""))
    s3 = res["S3"]
    out("    S3 (17.2 as 1d.6.1): pooled DD delta %+d | set5 %+d set6 %+d | without the most favourable cell (%s %s) %+d  "
        "=> %s" % (s3["pooled"], s3["per_set"].get("set5", 0), s3["per_set"].get("set6", 0), s3["worst"],
                   s3["worst_delta"], s3["loo"], "PASS" if s3["pass"] else "FAIL"))
    out("    S2 %s%s | S4 %s | S5 %s (literal fails %s, sign-test rejections %s) | S6 %s %s" % (
        "PASS" if res["S2"] else "FAIL", "" if res["S2"] else " %s" % [(f[0], f[2]) for f in res["S2_fails"][:6]],
        "PASS" if res["S4"] else "FAIL",
        "INCOMPLETE" if res["L4_incomplete"] else "PASS" if res["S5"] else "FAIL", res["lit_fail"] or "none",
        res["sig_fail"] or "none", "PASS" if res["S6"] else "FAIL",
        {k: "median R %s p99 %s ms (runs %d, calls %d)" % (fmt(None if v["median_R"] is None else 100 * v["median_R"],
                                                              "%.3f%%"), fmt(v["p99"], "%.2f"), v["n_runs"],
                                                          v["n_calls"]) for k, v in res["S6_detail"].items()}))
    out("    FULL(%s -> %s) = %s | HARMLESS(%s -> %s) = %s" % (x, y, res["full"], x, y,
                                                              "PASS" if res["harmless"] else "FAIL"))


def sec_comparisons(recs, zres, s1_pass, w3=None):
    """CHANGED: FULL(0 -> G) decides; FULL(0 -> N) and HARMLESS(N -> G) are REPORTED (1d.6.1)."""
    head("4 COMPARISONS (1d.6.1) - the 64 FRESH cells (sets 5-6). FULL(0 -> G) DECIDES; FULL(0 -> N) and HARMLESS(N -> "
         "G) are REPORTED, never gating. LITERAL: F1 pooled; F1 per set read as R2 (1d.3.3: the exact one-sided sign test "
         "of the set's diverged cells, p <= 0.05 fails); L2 (rescued set 5, set 6); L3 (DD pooled); L4 (1d.13.2, 0 -> G "
         "gating, 0 -> N reported); 24 counts by the exact one-sided sign test over the diverged cells, Holm family-wise "
         "alpha 0.05")
    C = {}
    for x, y in COMPARISONS:
        C[(x, y)] = comparison(recs, x, y, zres["fails"], s1_pass, w3)
        print_comparison(x, y, C[(x, y)], "FRESH sets 5-6%s" % (" - THE DECISION" if (x, y) == ("0", "G")
                                                                 else " - REPORTED"))
    return C


def sec_m8(recs, opts=None):
    """CHANGED (fresh sets only: no outcome of sets 1-4 is read in this round; the W1 positive control of 22.9 is not
    run)."""
    head("5 M8, M8-D AND THE FROZEN ATTRIBUTION OF 22.9 - every detected-victim death in every arm on the FRESH sets: "
         "the FIRST of FUT, U1, PRE, MOV-a, MOV-b, MOV-c, MOV-closure, RP, L3, OTHER (recorded fields only; the U1 class "
         "from the instrument's U1 shadow, 1d.8 (5))")
    classes = ("FUT", "U1", "PRE", "MOV-a", "MOV-b", "MOV-c", "MOV-closure", "RP", "L3", "OTHER")
    for arm in ARMS:
        for s in FRESH:
            sub = [r for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, arm)]
            if not sub:
                continue
            ds = [dd for r in sub for dd in r["g"][arm]["deaths"]]
            fc = sum(1 for dd in ds if dd["m8"] == "FC")
            cnt = collections.Counter(dd["cls"] for dd in ds)
            out("  arm %-2s %s (%2d runs): DD %2d | M8 FC %2d futile %2d (FC %s) | M8-D %2d | classes %s" % (
                arm, s, len(sub), len(ds), fc, len(ds) - fc, fmt(100.0 * fc / len(ds) if ds else None, "%.0f%%"),
                sum(1 for dd in ds if dd["m8d"]), " ".join("%s %d" % (k, cnt[k]) for k in classes if cnt[k])))
    out("  per death [cell, victim, detection, death, M8, M8-D, class, every class that applies]:")
    for r in fresh_recs(recs):
        for arm, g in r["g"].items():
            for dd in g.get("deaths") or []:
                out("    %-2s %-22s %-9s det %4s death %4s %-6s M8-D %-5s %-11s %s" % (
                    arm, r["cell"]["id"], dd["victim"], dd["det"], dd["death"], dd["m8"], dd["m8d"], dd["cls"],
                    dd["flags"]))
    nou1 = sum(1 for r in fresh_recs(recs) for g in r["g"].values() if g.get("u1_shadow_error"))
    if nou1:
        out("  the U1 class is NOT COMPUTED in %d fresh run(s) (the U1 shadow did not load, 1d.8 (5))" % nou1)


# ================================================================================================ 6 MEASURES
def sec_measures(recs, C, opts=None):
    """CHANGED (three arms; fresh sets only; the ACTED footprint split into would-act, ran and vetoed; no fix (c)
    SHELTER / HOLD; the guard's measures in 6.G and the DIAG of every cell where G is worse than 0 or N)."""
    head("6 MEASURES AND DIAG (1d.6.5; the urgency round's 16.9 / 22.2.4 / 22.8.3 / 23.2 items) - reported, never gated; "
         "FRESH sets 5-6 only")
    keys = ("rescued", "dead", "DD", "ff_deaths", "never_detected", "escape_writeoffs", "dispatch_writeoffs")
    out("M2 outcomes per arm, fresh set and placement:")
    for arm in ARMS:
        for s in FRESH:
            for plc in ("ring", "uniform"):
                sub = [r for r in fresh_recs(recs) if r["cell"]["set"] == s and r["cell"]["plc"] == plc
                       and usable(r, arm)]
                if sub:
                    out("  %-2s %s %-7s %s" % (arm, s, plc, " ".join("%s=%d" % (k, sum(r["g"][arm]["num"].get(k, 0)
                                                                                 for r in sub)) for k in keys)))
    out("MU1 the U1 SHADOW's decisions per arm and set (U1 is in no arm: the instrument's shadow, 22.9's U1 class): "
        "kicks, qualifying, shadow-divergent, promotions, deferrals, scarce kicks with |F| >= 2:")
    for arm in ARMS:
        for s in FRESH:
            sub = [r for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, arm)]
            if sub:
                t = lambda k: sum(r["g"][arm]["num"].get(k, 0) for r in sub)      # noqa: E731
                out("  %-2s %s kicks %d qualifying %d shadow-divergent %d promotions %d deferrals %d scarce |F|>=2 %d | "
                    "qualifying kicks with a planner-refused order head %d, refused decision records %d" % (
                        arm, s, t("kicks"), t("kicks_qualifying"), t("kicks_div_shadow"), t("promotions"),
                        t("deferrals"), t("kicks_scarce_multi"), t("kicks_refused_head"), t("decisions_refused")))
    out("F4 role filter (reported): _sd_analyze UAV I2 LIVELOCK / I2 STUCK / I6 RTB no-progress over ALL UAVs vs the "
        "victim_searcher episodes the gate counts:")
    for arm in ARMS:
        sub = [r for r in fresh_recs(recs) if usable(r, arm)]
        if sub:
            t = lambda k: sum(r["g"][arm]["num"].get(k, 0) for r in sub)          # noqa: E731
            out("  %-2s fresh: livelock all %d searcher %d | stuck all %d searcher %d | rtb no-progress all %d "
                "searcher %d" % (arm, t("uav_livelock_all"), t("os_i2_livelock"), t("uav_stuck_all"), t("os_i2_stuck"),
                                 t("rtb_noprog_all"), t("os_rtb_noprog")))
    out("ACTED footprint (d['mv_events']) per arm and set: cells with a would-act shadow event / a live event / a fix "
        "step that RAN / a VETOED decision, per fix")
    for arm in ARMS:
        for s in FRESH:
            sub = [r for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, arm)]
            if sub:
                out("  %-2s %s %s" % (arm, s, " | ".join("%s shadow %d live %d ran %d vetoed %d" % (
                    k, sum(1 for r in sub if r["g"][arm]["num"].get("shadow_" + k)),
                    sum(1 for r in sub if r["g"][arm]["num"].get("live_" + k)),
                    sum(1 for r in sub if r["g"][arm]["num"].get("ran_" + k)),
                    sum(1 for r in sub if r["g"][arm]["num"].get("vetoed_" + k))) for k in ("a", "b"))))
    out("DIAG every fresh cell where the arms differ in rescued, DD, firefighter deaths or write-offs (first divergence "
        "per pair):")
    for r in fresh_recs(recs):
        vals = {a: r["g"][a]["num"] for a in ARMS if usable(r, a)}
        if len(vals) < 2:
            continue
        diff = [k for k in ("rescued", "DD", "ff_deaths", "escape_writeoffs", "dispatch_writeoffs")
                if len({v.get(k, 0) for v in vals.values()}) > 1]
        if not diff:
            continue
        out("  %s differs in %s: %s" % (r["cell"]["id"], diff, " | ".join("%s %s" % (a, {k: v.get(k, 0) for k in diff})
                                                                          for a, v in vals.items())))
        for (x, y), p in r["pairs"].items():
            if not p["ident"]:
                out("     %s->%s first difference step %s (%s), first %s step %s" % (
                    x, y, p["D"], p["what"][:4], "veto" if (x, y) == ("N", "G") else "ran fix", p["s"]))
        for a, g in r["g"].items():
            if g.get("usable"):
                out("     %-2s deaths %s | ff deaths %s | write-offs %s" % (
                    a, [(dd["victim"], dd["death"], dd["cls"]) for dd in g["deaths"]], g["ff_dead"],
                    g["lists"].get("writeoffs", [])[:4]))
    for (x, y), res in C.items():
        new_l = [(r["cell"]["id"], sorted(set(r["g"][y]["latched_end"]) - set(r["g"][x]["latched_end"])))
                 for r in res["cells"] if set(r["g"][y]["latched_end"]) - set(r["g"][x]["latched_end"])]
        out("G-L (DPR, reported with F6) %s -> %s: runs ending latched X %d, Y %d | units latched at the end in Y and "
            "not in X: %s" % (x, y, sum(1 for r in res["cells"] if r["g"][x]["latched_end"]),
                              sum(1 for r in res["cells"] if r["g"][y]["latched_end"]), new_l or "none"))
        gn = []
        for r in res["cells"]:
            gx, gy = r["g"][x], r["g"][y]
            ex, ey = gx["eval"], gy["eval"]
            why = []
            if abs(int(ey.get("rescued") or 0) - int(ex.get("rescued") or 0)) >= 2:
                why.append("rescued %s->%s" % (ex.get("rescued"), ey.get("rescued")))
            if int(ey.get("firefighter_deaths") or 0) != int(ex.get("firefighter_deaths") or 0):
                why.append("ff deaths %s->%s" % (ex.get("firefighter_deaths"), ey.get("firefighter_deaths")))
            for nm, g_, e_ in ((x, gx, ex), (y, gy, ey)):
                if g_["n_ff"] and int(e_.get("firefighter_deaths") or 0) >= g_["n_ff"]:
                    why.append("all units die in %s" % nm)
            fin = lambda g_, e_: g_["terminal"] is not None and int(e_.get("dead") or 0) >= 1      # noqa: E731
            if (gx["terminal"] is None and fin(gy, ey)) or (gy["terminal"] is None and fin(gx, ex)):
                why.append("never-finishes <-> finishes with a death (terminal %s -> %s)" % (gx["terminal"],
                                                                                              gy["terminal"]))
            if why:
                gn.append((r["cell"]["id"], why))
        out("G-N 21.2(f) (DPR, reported) %s -> %s: %s" % (x, y, gn or "none"))
        rising = [(k, res["sign"][k]["rising"]) for k, _l in SIGN_KEYS if res["sign"][k]["rising"]]
        out("DIAG rising instances %s -> %s (every sign-tested count, whatever the test says): %s" % (
            x, y, "none" if not rising else ""))
        for k, cells in rising:
            for cid in cells:
                r = next(z for z in recs if z["cell"]["id"] == cid)
                out("    %-22s %-22s %s: %s -> %s" % (k, cid, "", r["g"][x]["lists"].get(k, [])[:3],
                                                     r["g"][y]["lists"].get(k, [])[:3]))
        ffd = [(r["cell"]["id"], y, r["g"][y]["ff_dead"]) for r in res["cells"] if r["cell"]["id"] in
               res["diverged_cells"] and r["g"][y]["ff_dead"]]
        out("  firefighter deaths in diverged cells (%s -> %s, Y arm): %s" % (x, y, ffd or "none"))
    for arm in ("G", "N"):
        near = [(r["cell"]["id"], x) for r in fresh_recs(recs) if usable(r, arm) for x in r["g"][arm]["lists"].get(
            "near_a", [])]
        out("DIAG %s route_blocked raises / strandings within 6 steps after an (a) step that RAN (22.2.4): %s" % (
            arm, near[:20] or "none"))
    dw = [(r["cell"]["id"], a, x) for r in fresh_recs(recs) for a, g in r["g"].items() if g.get("usable")
          for x in g["lists"].get("deferred_writeoffs", [])]
    out("DIAG write-offs of a victim the U1 shadow deferred: %s" % (dw or "none"))
    sec_m1(recs)
    sec_mu3(recs)
    sec_mu4(recs)
    sec_dp_items(recs, C)
    sec_guard(recs)
    sec_worse(recs)


# ------------------------------------------------------------------------------------------------ 6.R1-6.R4 (reported)
def _paired(recs, x, y, fresh=True):
    return [r for r in recs if bool(r["cell"]["fresh"]) == fresh and usable(r, x) and usable(r, y)]


def _subhead(title):
    out("-" * 118)
    out(title)


def _m1_print(tag, m, vict, cset, by_id, sets):
    st = m1_stat(m, cset, sets)
    out("     %-3s T: %s | after removing the most negative m_c: %s" % (
        tag, ", ".join("%s %s" % (s, fmt(st["T"][s])) for s in sets + ("pooled",)),
        ", ".join("%s %s" % (s, fmt(st["loo"][s])) for s in sets + ("pooled",))))
    parts = []
    for name, sel in (("ring", lambda c: c["plc"] == "ring"), ("uniform", lambda c: c["plc"] == "uniform")) + tuple(
            (s, (lambda c, s=s: c["scen"] == s)) for s in "ABCD"):
        vals = [v for k, v in sorted(m.items()) if sel(by_id[k])]
        parts.append("%s %s (%d)" % (name, fmt(mean(vals)), len(vals)))
    out("         T per placement / scenario (contributing cells): %s" % " | ".join(parts))
    allv = [v[2] for v in vict]
    out("         victim-pooled: n %d mean %s median %s | Wilcoxon signed-rank on m_c (reported): pooled %s; %s" % (
        len(allv), fmt(mean(allv)), fmt(statistics.median(allv) if allv else None),
        wil_str(wilcoxon([v for _k, v in sorted(m.items())])),
        "; ".join("%s %s" % (s, wil_str(wilcoxon([v for k, v in sorted(m.items()) if cset[k] == s]))) for s in sets)))
    out("         m_c per cell: %s" % (", ".join("%s %+.1f" % (k, v) for k, v in sorted(m.items())) or "none"))
    return st


def sec_m1(recs):
    """CHANGED (this round's comparisons; fresh sets only)."""
    _subhead("6.R1 REPORTED - M1 / M1c DETECTION-TO-RESCUE TIME (16.9, as DPR 14.7; never a guard): M1 per victim rescued "
             "in BOTH arms, delta = (rescue - detection) in Y minus in X (paired by cell and victim id; CRN); m_c = the "
             "cell's mean delta; T = the UNWEIGHTED mean of m_c. M1c: every victim detected in both arms, (rescue step "
             "or the censor 361) - detection, the same per-cell statistic")
    for x, y in COMPARISONS:
        cells = _paired(recs, x, y, True)
        sets = FRESH
        lbl = "FRESH sets 5-6"
        if not cells:
            out("  -- %s -> %s (%s): no paired usable cell" % (x, y, lbl))
            continue
        res = m1_compare([(r["cell"], r["g"][x], r["g"][y]) for r in cells])
        cset = {r["cell"]["id"]: r["cell"]["set"] for r in cells}
        by_id = {r["cell"]["id"]: r["cell"] for r in cells}
        n_cells = {s: sum(1 for r in cells if r["cell"]["set"] == s) for s in sets}
        st = m1_stat(res["m1"], cset, sets)
        out("  -- %s -> %s (%s): contributing cells %s | cells without a pair (listed, excluded): %s" % (
            x, y, lbl, ", ".join("%s %d / %d" % (s, st["n"][s], n_cells[s]) for s in sets), res["no_pair"] or "none"))
        _m1_print("M1", res["m1"], res["victims"], cset, by_id, sets)
        if res["anomalies"]:
            out("         ANOMALY rescued victims without a stdout detection: %s" % res["anomalies"][:8])
        stc = m1_stat(res["m1c"], cset, sets)
        out("     M1c contributing cells %s" % ", ".join("%s %d / %d" % (s, stc["n"][s], n_cells[s]) for s in sets))
        _m1_print("M1c", res["m1c"], res["victims_c"], cset, by_id, sets)
        out("         victims detected in one arm only (listed, excluded): %s" % (res["only_one"] or "none"))


def sec_mu3(recs):
    """CHANGED (fresh sets only; the U1 shadow's verdicts in every arm)."""
    _subhead("6.R2 REPORTED - MU3 VERDICT QUALITY (16.9) of the U1 SHADOW (U1 is in no arm): every shadow decision record "
             "(each waiting detected victim at a qualifying kick) against her outcome - picked up before her DECISION "
             "cell burned (strictly earlier), after, or never; died or not. The estimator's bias at the decisions from "
             "the CURRENT-cell T: T - (first burn of the decision cell - step), censored at 360, and T - (death - step). "
             "Harrell C at the decisions with a SEED-level bootstrap: clusters = seeds, %d draws, Random(%d), 95 %% "
             "percentile interval (Part 1 4.2)" % (BOOT_DRAWS, BOOT_SEED))
    for arm in ARMS:
        sub = [r for r in fresh_recs(recs) if usable(r, arm)]
        if not sub:
            continue
        vc = collections.Counter()
        burn, death, cens, noest = [], [], 0, 0
        stats = {}
        for r in sub:
            g = r["g"][arm]
            decs = g.get("decisions") or []
            vc.update(mu3_verdicts(decs))
            b_, d_, c_, n_ = mu3_bias(decs, g["horizon"])
            burn += b_
            death += d_
            cens += c_
            noest += n_
            cl = seed_cluster(r["cell"])
            h = mu3_concordance(decs, g["horizon"])
            prev = stats.get(cl) or {}
            stats[cl] = {k: tuple(a + b for a, b in zip(prev.get(k, (0, 0, 0)), v)) for k, v in h.items()}
        nP = sum(v for k, v in vc.items() if k[0] == "P")
        nD = sum(v for k, v in vc.items() if k[0] == "D")
        out("  arm %-2s fresh sets 5-6 (%d runs, %d seeds): decision records %d (promotable P %d, deferred D %d)" % (
            arm, len(sub), len(stats), nP + nD, nP, nD))
        for ver in ("P", "D"):
            out("     %s: %s" % (ver, " | ".join("%s %d (died %d)" % (
                pc, vc[(ver, pc, "died")] + vc[(ver, pc, "survived")], vc[(ver, pc, "died")])
                for pc in ("picked before burn", "picked after burn", "never picked"))))
        q1b, mb, q3b = iqr(burn)
        q1d, md_, q3d = iqr(death)
        out("     bias T - (first burn - step): median %s IQR [%s, %s] n %d (censored at 360: %d; no estimate: %d) | "
            "T - (death - step): median %s IQR [%s, %s] n %d" % (
                fmt(mb, "%.1f"), fmt(q1b, "%.1f"), fmt(q3b, "%.1f"), len(burn), cens, noest, fmt(md_, "%.1f"),
                fmt(q1d, "%.1f"), fmt(q3d, "%.1f"), len(death)))
        for scope, sname in (("kick", "per decision (pairs at one kick)"),
                             ("run", "per run (each victim's first decision)")):
            parts = []
            for target, tname in (("burn", "first burn"), ("death", "death")):
                c, lo, hi, n, kept = seed_bootstrap({cl: v[(scope, target)] for cl, v in stats.items()})
                parts.append("%s C %s 95%% [%s, %s] pairs %d (draws kept %d)" % (
                    tname, fmt(c, "%.3f"), fmt(lo), fmt(hi), n, kept))
            out("     Harrell C %-38s %s" % (sname + ":", " | ".join(parts)))


MU4_ITEMS = (("unit_steps", "unit-steps on legs (d['mv'] rows)"),
             ("unclean", "  ending on an unclean cell (B + A + S)"),
             ("unclean_B", "    burning (B)"), ("unclean_A", "    fire-adjacent (A)"), ("unclean_S", "    smoky (S)"),
             ("raises_mv", "route_blocked raises (mv rb_set)"),
             ("rb_onsets", "route_blocked onsets (rows_ff status)"),
             ("strandings", "strandings (o1 unassign -> death <= %d)" % STRAND_WINDOW),
             ("stranded_deaths", "  deaths after a stranding (distinct units)"),
             ("deaths_approach", "firefighter deaths on an approach leg"),
             ("deaths_carry", "firefighter deaths on a carry leg"),
             ("deaths_idle", "firefighter deaths idle"),
             ("deaths_rb_unbound", "firefighter deaths route_blocked unbound"))


def sec_mu4(recs):
    """CHANGED (fresh sets only; ACTED legs = a fix step that RAN in G / N, the would-act shadow in arm 0)."""
    _subhead("6.R3 REPORTED - MU4 FIREFIGHTER EXPOSURE (16.9; 12.2 G4) per arm and fresh set, each item split by BIND "
             "LEG (a successful assign of unit u to v, until u's next assign): legs bound at a U1-shadow-divergent kick "
             "vs the others; and legs where a movement fix ACTED (G / N: a fix step that RAN for that unit and victim "
             "inside the leg - a vetoed decision is today's step; arm 0: the would-act shadow) vs the others. Deaths by "
             "the unit's state on its last row before death; an idle / rb_unbound death is charged to the unit's latest "
             "bind. The 15-step stranding window undercounts (urgency death review 6.1)")
    for arm in ARMS:
        for s in FRESH:
            sub = [r for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, arm)]
            if not sub:
                continue
            tab = collections.defaultdict(collections.Counter)
            for r in sub:
                for k, v in (r["g"][arm].get("mu4") or {}).items():
                    tab[k].update(v)
            lg = tab.get("legs") or {}
            out("  arm %-2s %s (%d runs): bind legs %d (at a U1-shadow-divergent kick %d; with a movement fix ACTED %d)"
                % (arm, s, len(sub), lg.get("n", 0), lg.get("div", 0), lg.get("acted", 0)))
            for key, label in MU4_ITEMS:
                t = tab.get(key) or {}
                out("     %-42s %5d | U1-div legs %4d other %4d no leg %3d | ACTED legs %4d other %4d no leg %3d" % (
                    label, t.get("n", 0), t.get("div", 0), t.get("nodiv", 0), t.get("noleg_d", 0), t.get("acted", 0),
                    t.get("notacted", 0), t.get("noleg_a", 0)))
    st = [(r["cell"]["id"], a, x) for r in fresh_recs(recs) for a in ARMS if usable(r, a)
          for x in r["g"][a]["lists"].get("mu4_strandings", [])]
    out("  fresh strandings [cell, arm, [o1 step, unit, victim, death, U1-div leg, ACTED leg]]: %s" % (
        "none" if not st else ""))
    for x in st[:40]:
        out("    %s %-2s %s" % x)
    dd = [(r["cell"]["id"], a, x) for r in fresh_recs(recs) for a in ARMS if usable(r, a)
          for x in r["g"][a]["lists"].get("mu4_deaths", [])]
    out("  fresh firefighter deaths [cell, arm, [death, unit, leg, bound victim, U1-div leg, ACTED leg]]: %s" % (
        "none" if not dd else ""))
    for x in dd[:60]:
        out("    %s %-2s %s" % x)


def _rline(label, cells, x, y, key, sets=FRESH):
    groups = (("pooled", lambda c: True),) + tuple((s, (lambda c, s=s: c["set"] == s)) for s in sets) + (
        ("ring", lambda c: c["plc"] == "ring"), ("uniform", lambda c: c["plc"] == "uniform"))
    v = {gname: tuple(sum(int(r["g"][a]["num"].get(key, 0) or 0) for r in cells if sel(r["cell"])) for a in (x, y))
         for gname, sel in groups}
    out("    %-58s pooled %5d -> %5d (reported) | %s" % (label, v["pooled"][0], v["pooled"][1], " | ".join(
        "%s %d->%d" % (k, a, b) for k, (a, b) in v.items() if k != "pooled")))


DP_ITEMS = (("gb_a", "G-B (a) victim-steps with >= 2 living binders"),
            ("gb_b", "G-B (b) victim-steps with >= 2 ACTIVE binders"),
            ("gb_d", "G-B (d) captured RescueInvariant lines"),
            ("gt_returns", "G-T (b) all returns (amended outside events, section 10)"),
            ("m6_escape", "M6 escape-sweep write-offs (sweep phase)"),
            ("casualty_writeoffs", "M6 casualty write-offs (replacement_after_casualty)"),
            ("other_writeoffs", "M6 other write-offs"),
            ("assign_closed", "M6 assigns into a closed route (dp BFS route_open False)"),
            ("writeoffs_avoided", "M6 would-have-been casualty write-offs (J only; 0 here)"),
            ("m3a", "M3 (a) unit-steps free while a needy victim waits unbound"),
            ("m3b", "M3 (b) units with a finite d to such a victim (unit-steps)"))
RB_SPLIT = (("m3a_allowed", "  M3 (a) latch-cap split (DPR R-B, rebuilt ledger): allowed"),
            ("m3a_blocked", "  M3 (a) latch-cap split: ledger-blocked"),
            ("gb_f_allowed", "  G-B (f) waiting victim-steps with an allowed unit"),
            ("gb_f_blocked", "  G-B (f) waiting victim-steps, every unit ledger-blocked"))


def sec_dp_items(recs, C):
    """CHANGED (this round's comparisons; fresh sets only)."""
    _subhead("6.R4 REPORTED - THE DISPATCH ROUND'S ITEMS OF 16.8 (never gated): G-B (a)(b)(d) from dp.binders / "
             "dp.invariant; G-T(b) every return with the AMENDED outside events (Z5's gt_returns_amended); M6 write-offs "
             "and closed-route assigns (dp.commands); M3 idle-while-waiting from dp.m3a / dp.waiting via DPR's "
             "rb_figures with live=False in every arm")
    for (x, y), cells, sets, lbl in [((x, y), C[(x, y)]["cells"], FRESH, "FRESH") for x, y in COMPARISONS]:
        out("  -- %s -> %s (%s, %d paired cells)%s" % (x, y, lbl, len(cells), "" if cells else ": no paired usable cell"))
        if not cells:
            continue
        for key, label in DP_ITEMS:
            _rline(label, cells, x, y, key, sets)
        bad = sorted({(r["cell"]["id"], a) for r in cells for a in (x, y) if r["g"][a].get("rb_fail")})
        if bad:
            out("    latch-cap split STOPPED: an R-B tooling check fails in %d run(s) (DPR A2 22.2), e.g. %s" % (
                len(bad), bad[:4]))
        else:
            for key, label in RB_SPLIT:
                _rline(label, cells, x, y, key, sets)
    for arm in ARMS:
        sub = [r for r in fresh_recs(recs) if usable(r, arm)]
        if not sub:
            continue
        gt = collections.Counter()
        for r in sub:
            for k, v in r["g"][arm]["num"].items():
                if k.startswith("gt_b_"):
                    gt[k[5:]] += v
        fails = [(r["cell"]["id"], {k: v for k, v in r["g"][arm]["rb_checks"].items() if v and not k.startswith("n_")})
                 for r in sub if r["g"][arm].get("rb_fail")]
        out("  arm %-2s fresh (%d runs): G-T(b) returns by outside events %s | R-B tooling checks failing in %d "
            "run(s)%s" % (arm, len(sub), dict(gt) or "none", len(fails), (": %s" % fails[:3]) if fails else ""))
        for key, label in (("gb_b", "G-B (b) instances"), ("gb_d", "G-B (d) invariant lines"),
                           ("assign_closed", "closed-route assigns"), ("casualty_writeoffs", "casualty write-offs")):
            xs = [(r["cell"]["id"], x) for r in sub for x in r["g"][arm]["lists"].get(key, [])]
            if xs:
                out("    %s (%d): %s" % (label, len(xs), xs[:6]))


def _median(xs):
    return statistics.median(xs) if xs else None


def sec_guard(recs):
    """NEW - 6.G, the guard's reported measures (1d.6.5; never gating)."""
    _subhead("6.G REPORTED - THE STRANDING GUARD (1d.6.5 NEW; 1d.2.5 G4; 1d.2.6's tables on the fresh sets). The verdict "
             "read is the MODEL's in G (equal to the instrument's by Zg-1) and the instrument's SHADOW in 0 and N")
    out("  decisions where a fix would act (guard rows) per arm and set, by fix: rows | the instrument admits / vetoes "
        "(none = its guard raised) | G: the model's verdicts and the fix steps taken")
    for arm in ARMS:
        for s in FRESH:
            sub = [r for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, arm)]
            if not sub:
                continue
            gn = collections.Counter()
            for r in sub:
                gn.update(r["g"][arm].get("gnum") or {})
            out("  %-2s %s %s" % (arm, s, " | ".join(
                "(%s) rows %d admit %d veto %d none %d%s" % (
                    k, gn["rows_" + k], gn["inst_admit_" + k], gn["inst_veto_" + k], gn["inst_none_" + k],
                    "" if arm != "G" else " | model admit %d veto %d, fix steps taken %d" % (
                        gn["model_admit_" + k], gn["model_veto_" + k], gn["took_fix_" + k])) for k in ("a", "b"))))
    out("  LEGS with >= 1 decision where a fix would act (bind legs), by whether a decision was vetoed and how the leg "
        "ended (the first of: pickup, route_blocked unassign, unit died, victim died; else open), with the median number "
        "of fix decisions per leg:")
    for arm in ARMS:
        for s in FRESH:
            legs = [x for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, arm)
                    for x in r["g"][arm].get("guard_legs") or []]
            if not legs:
                continue
            for vet in (True, False):
                sel = [x for x in legs if x["vetoed"] == vet]
                cnt = collections.Counter(x["outcome"] for x in sel)
                out("  %-2s %s %-16s legs %3d | %s | median fix decisions %s" % (
                    arm, s, "a step vetoed" if vet else "admitted only", len(sel),
                    " ".join("%s %d" % (k, cnt[k]) for k in ("pickup", "route_blocked unassign", "unit died",
                                                              "victim died", "open")),
                    fmt(_median([x["n"] for x in sel]), "%.1f")))
    out("  G4 (1d.2.5): admit -> veto on the next step, admit -> veto -> admit, and revisits on an unchanged digest "
        "(a run of a unit's rows with one board digest and target in which a cell recurs, holding a fix decision; and "
        "of those holding a veto):")
    for arm in ARMS:
        for s in FRESH:
            sub = [r for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, arm)]
            if not sub:
                continue
            al = collections.Counter()
            for r in sub:
                al.update(r["g"][arm].get("guard_alt") or {})
            out("  %-2s %s admit->veto %d | admit->veto->admit %d | static-board revisits %d (with a veto %d)" % (
                arm, s, al["admit_veto"], al["admit_veto_admit"], al["static_cycles"], al["static_cycles_with_veto"]))
    out("  POST-VETO DIAG (1d.6.5): per veto in G, the vetoed unit's route_blocked raises, strandings and death within "
        "%d steps after it, in G against the same unit and window in N:" % POST_VETO_WINDOW)
    for s in FRESH:
        tot = {"G": collections.Counter(), "N": collections.Counter()}
        inst = []
        nv = 0
        for r in fresh_recs(recs):
            if r["cell"]["set"] != s or not (usable(r, "G") and usable(r, "N")):
                continue
            for st_, u, k in r["g"]["G"].get("vetoes") or []:
                nv += 1
                cg = post_veto_counts(r["g"]["G"]["pvm"], u, st_)
                cn = post_veto_counts(r["g"]["N"]["pvm"], u, st_)
                tot["G"].update(cg)
                tot["N"].update(cn)
                if any(cg.values()) or any(cn.values()):
                    inst.append((r["cell"]["id"], st_, u, k, "G %s" % cg, "N %s" % cn))
        out("  %s vetoes %d | G: raises %d strandings %d deaths %d | N (same unit, same window): raises %d strandings %d "
            "deaths %d" % (s, nv, tot["G"]["raises"], tot["G"]["strandings"], tot["G"]["death"], tot["N"]["raises"],
                           tot["N"]["strandings"], tot["N"]["death"]))
        for x in inst[:30]:
            out("    %s veto %s %s (%s): %s | %s" % x)
    gms = [ms for r in fresh_recs(recs) if usable(r, "G") for ms in r["g"]["G"].get("guard_ms") or []]
    ims = [ms for r in fresh_recs(recs) for a in ARMS if usable(r, a) for ms in r["g"][a].get("inst_guard_ms") or []]
    out("  the guard's cost in G: %d model guard calls, p50 %s p99 %s max %s ms | the instrument's guard evaluations "
        "(every arm): %d, p50 %s p99 %s max %s ms" % (
            len(gms), fmt(q(gms, 0.5)), fmt(q(gms, 0.99)), fmt(max(gms) if gms else None), len(ims), fmt(q(ims, 0.5)),
            fmt(q(ims, 0.99)), fmt(max(ims) if ims else None)))


def sec_worse(recs):
    """NEW (1d.6.5): DIAG of every fresh cell where G is worse than arm 0, or than N, in DD, rescued or firefighter
    deaths (as urgency report 4.3): the counts, each pair's first difference and the first ran-fix / veto step."""
    out("DIAG every fresh cell where G is WORSE than 0 or than N in DD, rescued or firefighter deaths (1d.6.5):")
    n = 0
    for r in fresh_recs(recs):
        if not usable(r, "G"):
            continue
        ng = r["g"]["G"]["num"]
        why = []
        for other in ("0", "N"):
            if not usable(r, other):
                continue
            no = r["g"][other]["num"]
            w = [k for k, worse in (("DD", ng["DD"] > no["DD"]), ("rescued", ng["rescued"] < no["rescued"]),
                                    ("ff_deaths", ng["ff_deaths"] > no["ff_deaths"])) if worse]
            if w:
                why.append("than %s in %s" % (other, w))
        if not why:
            continue
        n += 1
        out("  %s G worse %s | DD / rescued / ff deaths: %s" % (r["cell"]["id"], "; ".join(why), " ".join(
            "%s %d/%d/%d" % (a, r["g"][a]["num"]["DD"], r["g"][a]["num"]["rescued"], r["g"][a]["num"]["ff_deaths"])
            for a in ARMS if usable(r, a))))
        for (x, y), p in r["pairs"].items():
            out("     %s->%s first difference step %s (%s), first %s step %s" % (
                x, y, p["D"], p["what"][:4], "veto" if (x, y) == ("N", "G") else "ran fix", p["s"]))
        out("     G deaths %s | ff deaths %s | vetoes %s" % (
            [(dd["victim"], dd["death"], dd["cls"]) for dd in r["g"]["G"]["deaths"]], r["g"]["G"]["ff_dead"],
            (r["g"]["G"].get("vetoes") or [])[:8]))
    if not n:
        out("  none")


# ================================================================================================ 7 W3 / L4
def sec_w3_report(recs, w3):
    """NEW - section 7 (1d.13.2): the L4 counts both ways (CAUSED and PREVENTED, pooled and per set) for G (gating) and N
    (reported), with every candidate's evidence; REPORTED, never counted: the run-level variant, KO-LAST, KO-GUARD,
    review 1.3's class of every (A) candidate, candidates no knockout reverses, and the same-step deaths with the C-NONE
    check."""
    head("7 W3 / L4 - THE PER-DEATH ATTRIBUTION (1d.13.2): CAUSED(X) and PREVENTED(X) for G (gating: FAIL iff CAUSED > "
         "PREVENTED) and N (reported), pooled and per set; the rest reported, never counted")
    if not w3 or not w3.get("complete"):
        out("  W3 %s - no count is printed" % ((w3 or {}).get("state") or "not evaluated"))
        return
    for arm in ("G", "N"):
        items = w3["items"][arm]
        l4 = w3["l4"][arm]
        rl = l4_run_level(items)
        out("-- arm %s (%s): CAUSED %d vs PREVENTED %d pooled (per set %s)%s => %s | RUN-LEVEL variant (reported): "
            "CAUSED %d PREVENTED %d (per set %s)" % (
                arm, "GATING" if arm == "G" else "reported", l4["caused"], l4["prevented"],
                {s: "%d / %d" % tuple(v) for s, v in l4["per_set"].items()},
                " | uncomputable cell-arms: counted as not passing" if l4.get("uncomputable") else "",
                "FAIL" if l4["fail"] else "holds (a tie passes)", rl["caused"], rl["prevented"],
                {s: "%d / %d" % tuple(v) for s, v in rl["per_set"].items()}))
        for it in sorted(items, key=lambda z: (z["kind"], z["cell"], z["unit"])):
            if it["kind"] == "A":
                counted = (not it["resolved"]) or it.get("own") is True or it.get("others") is True
                cls = review13_class(it, it.get("chain"))
                extra = " | KO-LAST alive %s%s | review 1.3 class %s" % (
                    it.get("last"), " | KO-GUARD alive %s (a VETO caused it, reported)" % it.get("guard")
                    if arm == "G" else "", cls)
            else:
                counted = bool(it["resolved"]) and (it.get("own") is False or it.get("others") is False)
                extra = ""
            reversed_ = counted if it["resolved"] else None
            out("   (%s) %-22s %-9s t %3s (other arm %s) | %s | alive at t: KO-OWN %s%s KO-OTHERS %s%s | %s%s%s" % (
                it["kind"], it["cell"], it["unit"], it["t"], it["other"],
                "RESOLVED" if it["resolved"] else "UNRESOLVED (%s)" % "; ".join(it["why"][:3]),
                it.get("own"), "" if it.get("own_run") else " (not run: R0)", it.get("others"),
                "" if it.get("others_run") else " (not run: R0)",
                ("CAUSED" if it["kind"] == "A" else "PREVENTED") if counted else
                ("not caused" if it["kind"] == "A" else "not prevented"),
                " (downstream: no knockout reverses it)" if reversed_ is False else "", extra))
        if any(u["arm"] == arm for u in w3["uncomputable"]):
            out("   uncomputable cell-arms (a crashed W2 run): %s" % [u["cell"] for u in w3["uncomputable"]
                                                                     if u["arm"] == arm])
    same = w3.get("same") or []
    out("-- deaths at the same step in X and in arm 0 (neither candidate; review 1.3's C-NONE check - the unit's own rows "
        "identical up to t): %s" % ("none" if not same else ""))
    for s_ in same:
        out("   %s %-22s %-9s t %3s: %s" % (s_["arm"], s_["cell"], s_["unit"], s_["t"],
                                         "C-NONE" if s_["c_none"] else "the unit's rows differ before t (not C-NONE)"))


# ================================================================================================ 8 DECISION
def sec_decision(recs, st, s1, zres, C, w3, opts):
    """CHANGED (1d.6.3 on FULL(0 -> G); no verdict until W3 is complete, 1d.13.3)."""
    head("8 DECISION (1d.6.3 as amended by 1d.13.3: FULL(0 -> G), S5 = F1 (R2), L2, L3, L4 and the 24 sign-tested counts)")
    incomplete = bool(st["missing"] or st["invalid"])
    arm0_stop = bool(zres["stop"]) or bool(st["stop"])
    cg = C[("0", "G")]
    full = cg["full"]
    out("S1 IDENTITY %s | arm-0 STOP items %d" % ("PASS" if s1["pass"] else "FAIL" if s1["fail"] else "INCOMPLETE",
                                                 len(zres["stop"]) + len(st["stop"])))
    out("FULL(0 -> G) (THE DECISION)  : %s | S2 %s S3 %s S4 %s S5 %s S6 %s" % (
        full, cg["S2"], cg["S3"]["pass"], cg["S4"], "INCOMPLETE" if cg["L4_incomplete"] else cg["S5"], cg["S6"]))
    out("FULL(0 -> N) (reported)      : %s" % C[("0", "N")]["full"])
    out("HARMLESS(N -> G) (reported)  : %s" % ("PASS" if C[("N", "G")]["harmless"] else "FAIL"))
    zm = {}
    for k, z in (("a", "Zm-a"), ("b", "Zm-b")):
        zm[k] = not any(f[0] == z and f[1] in ("G", "N") for f in zres["fails"])
    acted = {k: {s: sum(1 for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, "G")
                        and r["g"]["G"]["acted_ran"].get(k)) for s in FRESH} for k in ("a", "b")}
    w3_done = bool(w3 and w3.get("complete") and not cg["L4_incomplete"])
    outcome = decide(arm0_stop, s1["fail"], full) if (w3_done or arm0_stop or s1["fail"]) else None
    sw = movement_switch_verdicts(outcome if outcome is not None else 0, zm, acted) if outcome is not None else None
    out("per switch (fresh cells of arm G where the fix's step RAN, per set: %s; Zm holds in every G and N run: %s):" % (
        acted, zm))
    for k, name in (("a", "FF_APPROACH_PATH"), ("b", "FF_RETREAT_KEEP_APPROACH")):
        out("  %-25s %s" % (name, sw[k] if sw else "no verdict yet (W3 incomplete)"))
    out("  %-25s ships 1 (inert with both fixes at 0); its code is merged only with a PASS" % "FF_FIX_STRANDING_GUARD")
    for x, y in (("0", "G"), ("0", "N")):
        cells = C[(x, y)]["cells"]
        sc = {s: (sum(r["g"][x]["num"]["rescued"] for r in cells if r["cell"]["scen"] == s),
                  sum(r["g"][y]["num"]["rescued"] for r in cells if r["cell"]["scen"] == s)) for s in "ABCD"}
        drop = [(s, a, b) for s, (a, b) in sc.items() if b - a <= -2]
        out("scenario rescued %s -> %s: %s | %s" % (x, y, {s: "%d->%d" % v for s, v in sc.items()},
                                                    "SCENARIO STOP (DIAGNOSTIC, 1d.6.3 / 22.8.4: reported with its "
                                                    "diagnosis; the verdict stands) %s" % drop if drop else
                                                    "no fall of 2 or more"))
    if outcome is None:
        verdict = "NO VERDICT - W3 is %s (1d.13.3: the analyzer prints no verdict until W3 is complete and every R0 " \
                  "has been checked)" % ((w3 or {}).get("state") or "not evaluated")
    else:
        verdict = "OUTCOME %d: %s" % (outcome, OUTCOME_TEXT[outcome])
        if not s1["pass"] and not s1["fail"]:
            verdict = "INCOMPLETE (S1 not established: the identity wave is incomplete) - would be %s" % verdict
        if incomplete:
            verdict = ("PROVISIONAL (incomplete data, --allow-incomplete) - %s" % verdict if opts.allow_incomplete else
                       "INCOMPLETE (%d missing, %d invalid runs - re-run them; no outcome is read)" % (
                           len(st["missing"]), len(st["invalid"])))
    out("")
    out("VERDICT: %s" % verdict)
    return outcome


# ================================================================================================ outcome gate
SMOKE_SUPPRESSED = "SMOKE: outcome sections suppressed (1d.8 (9): smoke outcomes are never read and enter no gate)"


def print_s6(x, y, res):
    """The S6 COST line of one comparison: median R and p99 per added switch group - no verdict, no outcome count."""
    out("  S6 COST %s -> %s: %s" % (x, y, " | ".join(
        "%s median R %s p99 %s ms (runs %d, calls %d)" % (
            k, fmt(None if v["median_R"] is None else 100 * v["median_R"], "%.3f%%"), fmt(v["p99"], "%.2f"),
            v["n_runs"], v["n_calls"]) for k, v in res["S6_detail"].items()) or "no added switch"))


ZEROS_ONLY_LINE = ("ZEROS-ONLY (the wave check, 1d.9 / 1d.13.3): sections 0-3 and the W3 validity only - no outcome "
                   "section and no verdict printed")


def incomplete_line(st, w3=None):
    """CHANGED (W3)."""
    return ("INCOMPLETE (%d missing, %d invalid runs; W3 %s) - the outcome sections are NOT printed (no screen outcome "
            "is looked at before every run is valid and present, and no verdict before W3 is complete); re-run them, or "
            "pass --allow-incomplete for a PROVISIONAL reading" % (len(st["missing"]), len(st["invalid"]),
                                                                   (w3 or {}).get("state") or "not evaluated"))


def stop_out(opts, text):
    """A STOP after section 1, 2 or 3: a VERDICT line, or (--zeros-only, which prints no verdict) a stop condition."""
    if getattr(opts, "zeros_only", False):
        out("ZEROS-ONLY STOP CONDITION: %s" % text)
    else:
        head("8 DECISION")
        out("VERDICT: %s" % text)


def print_structure(recs):
    """NEW (1d.8 (9), smoke): the STRUCTURE the smoke must exercise - per arm, the decisions where a fix would act, the
    (a) / (b) steps that RAN and the VETOED ones (structural fields, no outcome) - and the measured in-run cost: the
    model's guard calls, the instrument's guard evaluations, the probe's share of wall time, R, the run's wall time."""
    for r in recs:
        for arm in ARMS:
            g = r["g"].get(arm)
            if not g or not g.get("usable"):
                continue
            gn, nm = g.get("gnum") or {}, g.get("num") or {}
            out("  STRUCTURE %s %-2s%s: would act (a) %d (b) %d | ran (a) %d (b) %d | vetoed (a) %d (b) %d | model guard "
                "calls %d p50 %s p99 %s max %s ms | instrument guard %d p99 %s ms | probe %s of wall | R %s | wall %s s" % (
                    r["cell"]["id"], arm, " (DRY: urgency record)" if g.get("dry") else "", gn.get("rows_a", 0),
                    gn.get("rows_b", 0), nm.get("ran_a", 0), nm.get("ran_b", 0), nm.get("vetoed_a", 0),
                    nm.get("vetoed_b", 0), len(g.get("guard_ms") or []), fmt(q(g.get("guard_ms") or [], 0.5)),
                    fmt(q(g.get("guard_ms") or [], 0.99)), fmt(max(g["guard_ms"]) if g.get("guard_ms") else None),
                    len(g.get("inst_guard_ms") or []), fmt(q(g.get("inst_guard_ms") or [], 0.99)),
                    fmt(None if g.get("probe_frac") is None else 100.0 * g["probe_frac"], "%.3f%%"),
                    fmt(100.0 * g["fix_ms"] / (g["wall_s"] * 1000.0) if g.get("wall_s") else None, "%.3f%%"),
                    fmt(g.get("wall_s"), "%.0f")))


def outcome_sections(recs, st, s1, zres, w3, opts):
    """CHANGED: sections 4-8, gated:
    - --zeros-only (the wave check): nothing after the W3 validity but ZEROS_ONLY_LINE;
    - --smoke: the STRUCTURE counts and each comparison's S6 cost line, then SMOKE_SUPPRESSED - no literal clause,
      sign-tested count, S2-S5, FULL / HARMLESS, M8, measure, DIAG, L4 or decision;
    - a missing or INVALID run, or a W3 that is not complete, without --allow-incomplete: the INCOMPLETE line only;
    - otherwise every section (PROVISIONAL with --allow-incomplete; NO VERDICT while W3 is incomplete)."""
    if getattr(opts, "zeros_only", False):
        out(ZEROS_ONLY_LINE)
        return None
    s1_pass = not s1["fail"] or bool(opts.smoke)
    if opts.smoke:
        head("4 COMPARISONS - SMOKE: the STRUCTURE of 1d.8 (9) and the S6 COST line per comparison only (no verdict)")
        print_structure(recs)
        for x, y in COMPARISONS:
            print_s6(x, y, comparison(recs, x, y, zres["fails"], s1_pass, None))
        out(SMOKE_SUPPRESSED)
        return None
    w3_ok = bool(w3 and w3.get("complete"))
    if (st["missing"] or st["invalid"] or not w3_ok) and not getattr(opts, "allow_incomplete", False):
        head("8 DECISION")
        out("VERDICT: %s" % incomplete_line(st, w3))
        return None
    C = sec_comparisons(recs, zres, s1_pass, w3)
    sec_m8(recs, opts)
    sec_measures(recs, C, opts)
    sec_w3_report(recs, w3)
    return sec_decision(recs, st, {"pass": s1["pass"], "fail": s1["fail"]}, zres, C, w3, opts)


# ================================================================================================ main
def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--out")
    ap.add_argument("--head")
    ap.add_argument("--part2-notes")
    ap.add_argument("--allow-incomplete", action="store_true")
    ap.add_argument("--smoke")
    ap.add_argument("--smoke-cell", default="set1/ring/A_N")
    ap.add_argument("--smoke-files", default="")
    ap.add_argument("--zeros-only", action="store_true")
    opts = ap.parse_args(_ARGV[1:])
    opts.smoke_files = dict(x.split("=", 1) for x in opts.smoke_files.split(",") if "=" in x)
    if not opts.smoke and not (opts.head and opts.part2_notes):
        ap.error("--head <Part 2d commit> and --part2-notes <path> are required outside --smoke")
    if opts.zeros_only and opts.allow_incomplete:
        ap.error("--zeros-only prints no outcome: --allow-incomplete does not apply")
    if os.path.normcase(os.path.realpath(HERE)) != os.path.normcase(os.path.realpath(OUT_DIR)):
        print("REFUSED: this analyzer must live in %s (it is in %s)" % (OUT_DIR, HERE))
        return 2
    rc = 0
    try:
        if not sec_header(opts):
            return 2
        frozen = load_seeds()
        if frozen is None:
            return 2
        queues = {} if opts.smoke else load_queues()
        cells = screen_cells(frozen, opts)
        if opts.smoke and not cells:
            out("REFUSED: --smoke-cell %s is not a cell of sets 1-6" % opts.smoke_cell)
            return 2
        recs = process(cells, opts, queues)
        st = sec_prov(recs, opts)
        if st["seed"]:
            out("STOP: a run's scenario / wind / seed differs from its frozen cell (seed-selector rule)")
            return 2
        s1 = sec_z0(recs, opts)
        if s1["fail"] and not opts.smoke:
            stop_out(opts, "STOP (S1 IDENTITY FAILED) - %s" % OUTCOME_TEXT[2])
            return 1
        if st["stop"] and not opts.smoke:
            stop_out(opts, "STOP - a crash or early stop in arm 0 is a defect of the base code: diagnose before any "
                     "outcome is read (16.6)")
            return 1
        zres = sec_zeros(recs, st, opts)
        if zres["stop"] and not opts.smoke:
            stop_out(opts, "STOP - %s" % OUTCOME_TEXT[1])
            return 1
        w3 = None if opts.smoke else w3_validity(recs, opts)
        if w3 is not None and w3.get("refused"):
            stop_out(opts, "REFUSED - the W3 queue is not the one the frozen rule gives on these W2 records (1d.13.3)")
            return 2
        outcome_sections(recs, st, s1, zres, w3, opts)
    finally:
        if opts.out:
            with open(opts.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(_LINES) + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
