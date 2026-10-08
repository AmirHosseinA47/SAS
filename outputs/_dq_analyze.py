"""DISPATCH ROUND 2 analyzer - PRE-REGISTERED (outputs/dispatch2_part1.txt sections 10, 11.3 and 12.2; rulings section
19: every option (a)). The movement round's analyzer (outputs/_mvg_analyze.py at main 897e93b5) ported to the
corrected-dispatch screen of section 9: arms dqR (main 897e93b5, the identity reference), dq0 (today's dispatch,
DISPATCH_JOINT = DISPATCH_REASSIGN = 0) and dq1 (the corrected dispatcher, both 1), every arm on the shipped guarded
movement. THE DECISION is dq0 -> dq1 only.

READ-ONLY. It reads run files from E:/Projects/SAS_wt/dispatch/outputs (or --smoke DIR), the frozen queues and seeds,
the W3 replays and git objects of this repository, and writes nothing but --out. Every decision function is pure and is
checked on hand-built records with known answers by outputs/_dq_analyze_selftest.py, which must pass before any real
run is read.

usage (dispatch worktree root, E:/Projects/SAS/.venv/Scripts/python.exe):
  python outputs/_dq_analyze.py --head SHA [--part2-notes PATH] [--out REPORT] [--allow-incomplete | --zeros-only]
  python outputs/_dq_analyze.py --smoke DIR --smoke-files ARM=FILE[,ARM=FILE...] [--smoke-cell set1/ring/A_N]
                                [--out REPORT] [--zeros-only]
  --head SHA          the screen head (the Part 2 commit) every dq0 / dq1 record and every W3 replay must carry. THE
                      HEAD RULE (the movement round's rule (a), head_rule verbatim): valid when the recorded head starts
                      with SHA, or is an ANCESTOR of SHA with every RUN-LOADED file (root *.py, src_extension/, the
                      probe chain RUN_LOADED_TOOLING, and outputs/_dq_replay.py for a replay) byte-identical LF-normalised.
                      A dqR record must carry main 897e93b5 (BASE) itself. Every source sha a record names (dp / ud / mvg /
                      dq .src_sha) must be the file at SHA (dqR: at BASE), LF or CRLF form; the instrument's own shas
                      (dq.probe_sha = mvg.probe_sha, dq.r1_shadow_sha, mvg.u1_shadow_sha) must be outputs/_dq_probe.py,
                      outputs/_dq_r1_shadow.py, outputs/_mvg_u1_shadow.py at SHA (every arm runs the dispatch worktree's
                      probe). SHA must descend from BASE and from the rulings commit 87a93cda.
  --part2-notes PATH  optional: every '<sha256> outputs/...' line verified against the file on disk (notes_check
                      verbatim); the files of NOTES_REQUIRED must be listed. REFUSED on any mismatch.
  --zeros-only        the wave check (14): sections 0-3 and the W3 validity, then stop - no outcome section, no verdict,
                      and no outcome VALUE in a failure line (field paths only, numbers masked)
  --allow-incomplete  compute on what exists; the reading is PROVISIONAL, and while W3 is incomplete NO VERDICT is
                      printed at all (11.3)
  --smoke DIR         ONE cell of the spent sets 1-2 (--smoke-cell) from DIR: ARM in R, 0, 1 (any subset); relaxed
                      validity (no queue, no 360-step, no head checks); the cell stands in for the fresh set 7. SMOKE -
                      NOT A SCREEN (13 (9): structural fields only): sections 0-3, the STRUCTURE counts of 13 (9) (the
                      corrections' paths) and the S6 cost line; every outcome section is suppressed.
exit: 0 report written; 1 STOP (S1 identity failed; a dq0 / dqR failure - 10.3; the DIVERGED assertion - 10.6); 2
REFUSED (a hashed section differs, a reused function or module is not the committed one, the Part 2 notes differ, the
seeds file is unusable, a run's scenario / wind / seed is not its frozen cell, or the W3 queue is not what the frozen
rule gives on the W1 / W2 records).

HASHED SECTIONS (12.2): the LF-normalised text of dispatch2_part1.txt sections 0 and 2-15 and section 19 (the rulings
amendment A1), each from its 'N. ' header to the line before the next top-level 'N. ' header (or EOF), trailing blank
and '=' banner lines dropped, has the sha256 of SECTION_SHA256 - constants computed from the committed file
(git show 87a93cda:outputs/dispatch2_part1.txt, 2026-10-08). The working file AND the blobs at ba647655 (sections 0,
2-15) and 87a93cda (0, 2-15, 19) must give them; any difference REFUSES a verdict. An appended amendment (section 20 =
A2, ...) changes none of them; its sha is printed as information.

SECTIONS
  0 HEADER        commits ba647655 (Part 1), 87a93cda (rulings, A1), 897e93b5 (BASE), HEAD and --head; the hash checks;
                  the functions verbatim from _mvg_analyze.py (897e93b5) and _dp_analyze.py (cc8d653c); the reused
                  modules byte-identical to cc8d653c's; the Part 2 notes (optional); the seeds (0.6 / 8: the rule
                  recomputed for sets 1-8 from the bases, set 7 = 575201, set 8 = 741141; STOP on any mismatch; never
                  re-scanned).
  1 LOAD + PROV   validity per run (INVALID = a tooling defect, re-run), crash material (Z6), the seed-selector STOP.
  2 S1 IDENTITY   10.2: dq0 == dqR value identity on 64 / 64 cells on the FROZEN field list (S1_FIELDS): every listed
                  field present in both records; a missing one is a failure. Field paths only, never values.
  3 ZEROS         10.3: in EVERY arm the movement-owned (Z1-M item (v), Z-RB, Zm-a, Zm-b, Z-S, Z2-M), guard-owned
                  (Zg-1 two-sided, Zg-2) and shared (Z5, Z6) zeros and SM; DISPATCH-OWNED in dq1 (G-B(a) / I7, G-B(b),
                  G-B(c), I4-W, G-T(a), G-T(c), M6, Z-C1a, Z-C1b, Z-C2, Z-R1, Z-R2, Z-C3), each recomputed from the
                  probe's recorded J inputs and the instrument's own maps (never from J's outputs). OWNERS: any zero, SM
                  row or crash in dq0 / dqR is a STOP (a shipped movement or guard zero there: a STOP for a maintainer
                  ruling); a zero failing in dq1 only is an S2 FAIL (X-11 (a)). Z1-M (i)-(iv) and Zg-3 are void.
  W3 VALIDITY     11.2-11.3: the W3 queue and candidates re-derived by the frozen generator outputs/_dq_w3_queue.py
                  from the W1 (dq0) and W2 (dq1) records; every replay present and valid; every R0 checked against its
                  W2 record; the knockout evidence (the first changed J decision in the knockout log).
  4 COMPARISON    FULL(0 -> 1) = S1 to S6 (10.1): S3 (10.4), S4 = L2 + L3, S5 = F1 (R2) + L4 + the sign-tested family
                  of m = 28 (10.6: the movement round's 24 + D1 abandoned waiting, D2 returns of any cause, D3
                  idle-unreachable, D4 route_blocked at run end), Holm 0.05; the DIVERGED assertion; S6 (10.7).
  5 M8 + 22.9     M8, M8-D and the movement round's frozen death classes for every DD.
  6 MEASURES      10.9, reported, never gating.
  7 W3 / L4       11.3: CAUSED and PREVENTED, pooled and per set; the run-level variant, KO-LAST, the hybrid diagnostic,
                  the same-step deaths with the C-NONE check.
  8 DECISION      10.8's outcomes 1-6 on FULL(0 -> 1); the ACTED footprint per correction and set (NOT EXERCISED);
                  the scenario STOP as a diagnostic.

D1-D4 (10.6), read from the ARM-INDEPENDENT per-step sample d['dq']['sample'] (the sample instant of 10.1):
  D1 ABANDONED WAITING  victim-steps at which a victim of W or W_L (detected, needy, no ACTIVE binder, not in custody)
                        has some FREE unit with a finite route (the instrument's fire-free BFS, unit-cell exemption);
                        split W / latch-held (W_L) / nearest-barred (W_L whose contest J nearest-barred at that step's
                        J-post) / other (none expected);
  D2 FLIP-FLOPS         returns of any cause (round 1's G-T(b): gt_returns over dp.commands);
  D3 IDLE-UNREACHABLE   unit-steps of unbound (sampled, bound False: unbound, living, on-grid, non-exiting) units of
                        any status label with NO finite route to any W / W_L victim, while at least one exists, that did
                        NO WORK in the advance just sampled: moved False (cell == the previous sample's; None at the
                        unit's first sample does not count) and no extinguish / clear row with wrote True in its log;
  D4 ROUTE_BLOCKED AT RUN END  units whose rows_ff status is route_blocked at their last recorded step, bound or not
                        (round 1's G-L: _ut_analyze2.ff_status_track).
DIVERGED (10.6): a cell whose per-step rows (rows_ff / vic / uav / dec / trig), eval or command sequence (step, action,
victim, unit, ok - no reason strings) differ between dq0 and dq1; every cell with a non-zero delta in a gated count
(F1, L2, L3 / S3 and the 28) must be DIVERGED, else STOP.

THE W3 TOOLS (outputs/_dq_w3_queue.py, the frozen generator, imported lazily; outputs/_dq_replay.py, the replay tool):
  the analyzer calls the generator's compact(d) (for every fresh dq0 / dq1 record) and build_plan(W1 lines, W2 lines,
  compacts) -> (candidates doc, W3 lines), and reads its Q_W3, CANDS, KO_A, KO_B; the candidates file's entries (cell,
  set, arm, x, zero, A [{unit, t, t0, ko, first, n_changes}], B [{unit, t, t1, ...}], same, replays [{name, suffix,
  rules}]), uncomputable and inputs (w1 / w2 queue sha256, records_sha256) are re-derived and compared. A replay line is
  [<_dq_replay.py>, --kolog PATH, (--ko JSON), '--', <the dq1 line's probe arguments>]; its KNOCKOUT LOG (kolog_problems)
  holds version, replay_sha, probe_sha, argv, ko_rules, ko_log, ko_applied (change keys), jpoints, errors. Rules:
  {'unit': U | '!U' | '*', 'from', 'to', 'phase'?}. THE KNOCKOUT EVIDENCE (11.2): ko_first() - the analyzer's OWN reading
  of 11.2's override on dq1's recorded J decisions (j_decision_points: dp.j_calls' counterfactual, dp.j_events' binds,
  refused and aborted included; override_changes: drop_bind / drop_release / drop_challenger / drop_victim /
  drop_unreleased / ko_today, keys [step, phase, unit, victim, kind]) - gives each knockout's first change; it must
  equal the frozen rule's prediction ('first') and be in the replay's ko_applied, and a knockout the rule did not queue
  must have an empty decision set. Otherwise the candidate is UNRESOLVED (11.2).
W2_GATE (the generator's precondition): w2_gate(head, notes) -> (ok, problems) - section 0 and section 1's validity of
the 64 W1 dq0 and 64 W2 dq1 records, masked, no outcome.
Conventions (as _mvg_analyze): rows_* index t = the state after step t + 1; detection steps from <out minus
.json>.stdout.txt '[Victim Detection]' lines; a victim's death step = the first rows_vic managed 'dead', a unit's the
first rows_ff dead flag. No outcome of seed sets 1-6 is printed anywhere (8: sets 1-2 are read in the smoke and the
structure check, structural fields only): sections 4-8 read the fresh sets 7-8 only.
Reused, imported unchanged: _sd_analyze.analyze, _fb3_analyze searcher_o / ff_episodes, _ut_analyze._last_detection,
_ut_analyze2.ff_status_track, _fx3r_analyze FIELDS / DET_RE, _mf2_pool.signature.
"""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import importlib
import inspect
import json
import math
import os
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = r"E:\Projects\SAS_wt\dispatch"
OUT_DIR = os.path.join(WT, "outputs")
REF_WT = r"E:\Projects\SAS_wt\base897e93b5"
sys.path.insert(0, HERE)
_ARGV = sys.argv
sys.argv = _ARGV[:1]                       # _fb3_analyze / _ut_analyze* read sys.argv at import
try:
    import _fx3r_analyze as R              # noqa: E402  FIELDS, DET_RE
    import _fb3_analyze as A               # noqa: E402  searcher_o, ff_episodes
    import _sd_analyze as SD               # noqa: E402  analyze()
    import _ut_analyze as U                # noqa: E402  _last_detection
    import _ut_analyze2 as U2              # noqa: E402  ff_status_track
    import _mf2_pool as POOL               # noqa: E402  signature
finally:
    sys.argv = _ARGV

PART1, RULINGS = "ba647655", "87a93cda"
PART1_FULL = "ba64765590049ef04cd566e37ccd73f67ac6a2e4"
RULINGS_FULL = "87a93cda95a5e75b58afe67c191c8f72db477f9b"
BASE = "897e93b5ed14b582789fd3e59501253aebfb911b"     # main = tag movement-guard: the dqR checkout and the base
DISPATCH = "cc8d653c4a5740c0f04a9e94d6ff48e92a0ca027"  # round 1's Part 3 head: outputs/_dp_analyze.py (DPR verbatim)
MVG_AT = BASE                              # outputs/_mvg_analyze.py at main 897e93b5 (the functions ported verbatim)
SPEC_REL = "outputs/dispatch2_part1.txt"
SECTION_RE = re.compile(r"^\d{1,2}\. [A-Z]")
# 12.2: sha256 of each hashed section's LF text, computed from git show 87a93cda:outputs/dispatch2_part1.txt (identical
# at ba647655 for sections 0 and 2-15, and in the working file at 71cfe796)
SECTION_SHA256 = {
    0: "bb0ade24dcd44406bac481d99b78d415122d31e17394d9af54d15d48ef7352b4",
    2: "e5a3ce33196661e2511437454b5e01607a9f142d8010b96ceb9155486b87b4be",
    3: "14e4fd90472c995a4e60c1e61369855d3c52c8c9e6b203b96a414661e20ab6c7",
    4: "62442ea6d1c972738f94fa521191a9f3017fe6a7618106f514ea31f215297326",
    5: "696f037a3a936c4e3ad2f46e819023bd155549c01dc9e3f26824f4eebd361550",
    6: "e7cc5abcc45025463ee87f74dfc68c9f6023f4a2a61180e6a86cdb989972b4bf",
    7: "6cbd5fbf5518330d197375d75186ab14fa2478143bd48606d034bc4fadfbd9aa",
    8: "3ea8c94f0c19ba38414775160bbcf22d991dd46e5fd043b8382a3e05ed165ff4",
    9: "e50d1e9844e0c41ac33774829f5b07107ffc9b7dc5d1b721274a17273ff85b53",
    10: "05eac5fce7cc3ec3d5bf0f16d9359e34f3b6cec952cca9f80857ebcc2800f9ff",
    11: "ccb74839e159f9081025cd78675058fcb88bae8b78320620c025b1ee1567a804",
    12: "e2adf28039f19e07d105c2c8c224cff62560245a7ffe72f28aff1e9f1626ba6d",
    13: "c8e8be877b4196c8bf5ef11909565f6aa3c67888680ca6aa653d8488e156a9e0",
    14: "1a374d12d37a25864aabf8efecb70667c35fba931ae495527be04d0ffee8b5da",
    15: "e1655b6bdc71e4108959cce4a0c8335831c6ec8348e20025b407832804928aec",
    19: "806b67dc4137be9de9fcdb9c11d69d466d32fece808f2752338dc36c8e929e0f",
}
SECTION_COMMITS = {n: ((PART1, RULINGS) if n != 19 else (RULINGS,)) for n in SECTION_SHA256}
REUSED_MODULES = ("_fx3r_analyze.py", "_fb3_analyze.py", "_sd_analyze.py", "_ut_analyze.py", "_ut_analyze2.py",
                  "_fx3_pockets.py", "_mf2_p3_analyze.py", "_fb3_queue.py", "_mf2_pool.py")
# --part2-notes (optional): the files the notes must list (the instrument and its chain, the round-1 shadow, the analyzer
# and its self-test, the frozen queues and seeds, the W3 tools)
NOTES_REQUIRED = ("outputs/_dq_probe.py", "outputs/_dq_probe_check.py", "outputs/_dq_r1_shadow.py",
                  "outputs/_dq_analyze.py", "outputs/_dq_analyze_selftest.py", "outputs/_dq_queue.py",
                  "outputs/_dq_q_w1.jsonl", "outputs/_dq_q_w2.jsonl", "outputs/_dq_seeds.txt", "outputs/_dq_replay.py",
                  "outputs/_dq_w3_queue.py", "outputs/_mvg_u1_shadow.py", "outputs/_ut_probe.py",
                  "outputs/_fb3_probe.py", "outputs/_fx3_probe.py", "outputs/_mf2_probe.py", "outputs/_sd_probe.py",
                  "outputs/_fm2_probe_harness.py", "outputs/_ffr_harness.py", "outputs/_bp_inst.py",
                  "outputs/_mf2_pool.py")
# THE HEAD RULE's run-loaded files: _dq_probe.py loads _dq_r1_shadow.py and _mvg_u1_shadow.py by path and runpy-runs
# _ut_probe.py -> _fb3_probe.py (-> _fm2_probe_harness.py -> _ffr_harness.py; _bp_inst.py by path) -> _fx3_probe.py ->
# _mf2_probe.py -> _sd_probe.py; _ffr_harness.py imports _dim_hooks.py only with a --dim-* option (listed
# conservatively). The repository side: every tracked *.py at the root and everything under src_extension/.
RUN_LOADED_REPO = (":(glob)*.py", "src_extension")
RUN_LOADED_TOOLING = ("outputs/_dq_probe.py", "outputs/_dq_r1_shadow.py", "outputs/_mvg_u1_shadow.py",
                      "outputs/_ut_probe.py", "outputs/_fb3_probe.py", "outputs/_fx3_probe.py", "outputs/_mf2_probe.py",
                      "outputs/_sd_probe.py", "outputs/_fm2_probe_harness.py", "outputs/_ffr_harness.py",
                      "outputs/_bp_inst.py", "outputs/_dim_hooks.py")
RUN_LOADED_REPLAY = ("outputs/_dq_replay.py",)
PROBE_REL, REPLAY_REL = "outputs/_dq_probe.py", "outputs/_dq_replay.py"
R1_SHADOW_REL = "outputs/_dq_r1_shadow.py"
U1_SHADOW_REL = "outputs/_mvg_u1_shadow.py"
DQ_PROBE = "dq_probe v1"                   # d['dq'] / d['ud'] / d['mvg'] probe (the instrument; refuses mixed versions)
DP_PROBE = "dp_probe v3"                   # d['dp'] probe (round 1's section, J fields in the corrected-J form)
MVG_SRC_REQUIRED = ("agents.py", "wildfire_model.py", "common_fixed_variables.py",
                    "src_extension/planning/movement_paths.py", "src_extension/planning/fire_arrival_estimate.py")
JD_REL = "src_extension/planning/joint_dispatch.py"
H = 360
STUCK, WIN = 20, 30                        # _sd_analyze I2 thresholds (as _dp_analyze / _mvg_analyze)
ALPHA = 0.05
F1_ALPHA = 0.05                            # 10.5 F1 (ii): a set fails when its exact one-sided sign test gives p <= 0.05
EXPECTED_BASES = {"set1": 9601, "set2": 9621, "set3": 573001, "set4": 780001, "set5": 135961, "set6": 287041,
                  "set7": 575201, "set8": 741141}
FRESH = ("set7", "set8")
SPENT_SMOKE = ("set1", "set2")             # 8 / 13 (9): the smoke and the structure check, structural fields only
WINDS = (("N", "north"), ("S", "south"), ("E", "east"), ("W", "west"))
PLACES = (("r", "ring", 0), ("u", "uniform", 1))
ARMS = ("R", "0", "1")
ARM_TAG = {"R": "dqR", "0": "dq0", "1": "dq1"}
ARM_REPO = {"R": REF_WT, "0": WT, "1": WT}
ARM_DISPATCH = {"R": None, "0": False, "1": True}   # joint_on / reassign_on per arm (R: no DISPATCH_* key at main)
J_ONLY = ("probe", "switches", "src_sha", "j_calls", "j_events", "ledger", "timing", "rc_chain", "j_detail",
          "j_timing")
TERMINAL = ("rescued", "dead", "unreachable")
DISPATCH_RE = re.compile(r"^\[Dispatch\] FF-(\S+) assigned to (\S+) reason=(\S+) manhattan_dist=(\S+)")
STEP_RE = re.compile(r"\bstep=(\d+)")
TRIAGE_TAG = "[UrgencyTriage]"
NEW_TAGS = (TRIAGE_TAG,)                   # stdout compared with the urgency round's tag stripped (none here)
VDEAD_RE = re.compile(r"^\[RescueEvent\] type=victim_dead victim=(\S+)")
ROW_KINDS = ("rows_ff", "rows_vic", "rows_uav", "rows_dec", "rows_trig")
# d["mv"] columns (dq_probe v1 = mvg_probe v1's MV_COLS) and d["mvg"]["guard"] columns, unchanged
MV_COLS = ("step", "unit", "victim", "leg", "branch", "pre", "post", "target", "digest",
           "st_pre", "st_post", "tier", "mt", "rb_call", "rb_set",
           "trig", "zrb", "today", "fa", "fb", "fbB", "fc", "acted",
           "dc", "dcx", "df", "dm", "dr", "gesc",
           "cls_pre", "cls_post", "fd_pre", "fd_post", "c1_pre", "c1_post",
           "fix_ms", "inst_ms", "dcb",
           "gA", "gB", "veto", "acted_g")
GUARD_COLS = ("step", "unit", "victim", "kind", "u", "n", "v", "today", "today_kind", "today_tier", "today_raise",
              "c", "T_v", "admit", "model_admit", "model_verdict", "model_cell", "took", "post", "tier", "raise",
              "pre_writes", "pred_writes", "post_writes", "ms_guard", "ms_inst", "row", "mp_verdict")
SAMPLE_COLS = ("step", "W", "WL", "custody", "active", "units")
SAMPLE_UNIT_COLS = ("unit", "status", "free", "bound", "cell", "moved", "routes", "log")
FFLOG_COLS = ("step", "ff", "action", "engaged", "plan", "cell", "target", "wrote", "scorched", "dry", "suspend_set")
FIX_BRANCHES = ("approach_a", "retreat_b")
VETO_BRANCHES = ("approach_a_veto", "retreat_b_veto")
EXCLUDED_CARRY = ("c2s", "c3")             # 22.8.3's designed-behaviour exclusion: void (no fix (c))
GUARD_TEXTS = ("guard vetoes (instrument), model did not take today's step", "model guard verdict != instrument verdict",
               "guard evaluated on a cell other than the shadow's", "model guard call where the shadow did not act")
I2_KINDS = (("stuck_approach", "I2_ff_stuck_approach"), ("stuck_carry", "I2_ff_stuck_carry"),
            ("livelock_approach", "I2_ff_livelock_approach"), ("livelock_carry", "I2_ff_livelock_carry"),
            ("noprog_approach", "I2_ff_no_progress_approach"))
# 10.6: THE MOVEMENT ROUND'S 24 (urgency_part1.txt 23.2; _mvg_analyze SIGN_KEYS, verbatim) ...
SIGN_KEYS_MVG = (
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
assert len(SIGN_KEYS_MVG) == 24
# ... plus the brief's dispatch counts (10.6 ADDED, ruling X-10 (a)): THE FAMILY, m = 28
D_KEYS = (
    ("d1_abandoned", "D1 abandoned waiting (victim-steps)"),
    ("d2_returns", "D2 flip-flops: returns of any cause"),
    ("d3_idle_unreachable", "D3 idle-unreachable (unit-steps)"),
    ("d4_rb_end", "D4 route_blocked at run end (units)"),
)
SIGN_KEYS = SIGN_KEYS_MVG + D_KEYS
assert len(SIGN_KEYS) == 28
GATED_LITERAL_KEYS = ("ff_deaths", "rescued", "DD")   # F1, L2, L3 / S3: with SIGN_KEYS the DIVERGED assertion's counts
# the zeros (10.3) and their printing order
MOV_ZEROS = ("Z1-M", "Z2-M", "Z-RB", "Zm-a", "Zm-b", "Z-S")
GUARD_ZEROS = ("Zg-1", "Zg-2")
SHARED_ZEROS = ("Z5", "Z6")
DISPATCH_ZEROS = ("G-B(a)/I7", "G-B(b)", "G-B(c)", "I4-W", "G-T(a)", "G-T(c)", "M6", "Z-C1a", "Z-C1b", "Z-C2", "Z-R1",
                  "Z-R2", "Z-C3")
ZERO_ORDER = MOV_ZEROS + GUARD_ZEROS + SHARED_ZEROS + ("SM",) + DISPATCH_ZEROS
# J's reasons (wildfire_model): the fill (_DISPATCH_FILL_REASONS), a REPLACE (reassign_<cause>), a LATCH-FILL
FILL_REASONS = ("joint_initial", "joint_replacement_after_blocked", "joint_replacement_after_casualty")
REPLACE_REASONS = ("reassign_stall", "reassign_margin")
LATCH_REASON = "joint_replace_latched"
J_REASONS = FILL_REASONS + REPLACE_REASONS + (LATCH_REASON,)
J_EVENT_KINDS = ("fill", "second_fill", "replace", "latch_fill", "nearest_barred", "fill_refused",
                 "second_fill_refused", "replace_aborted", "latch_fill_aborted")
J_BIND_KINDS = ("fill", "second_fill", "replace", "latch_fill")
PHASE_RANK = {"init": -1, "pre": 0, "advance": 1, "post": 2, "sweep": 3}
RB_CUT_PHASES = ("pre", "advance", "post")  # round 1's R-B sample cut (rb_ledgers / rb_cut_refusals, verbatim)
FILL_MAX_CONFIGURATIONS = 100_000          # joint_dispatch.MAX_CONFIGURATIONS (design 5.5): the analyzer's own copy
FF_WORK_ACTIONS = ("extinguish", "clear")  # D3: a firefighting WRITE (wrote True) of these actions is work
FP_VARIANTS = ("r1", "C1", "C2", "R1", "R2")
FP_CORRECTIONS = (("C1", "C1 nearest wins"), ("C2", "C2 a latched unit is an incumbent"), ("R1", "R-1 one route "
                                                                                                     "metric d*"),
                  ("R2", "R-2 clean approach first"))

_LINES: list[str] = []
_BLOB_SHAS: dict = {}
_LF_SHAS: dict = {}
_RUN_LOADED: dict = {}


# ================================================================================================ VERBATIM: outputs/_mvg_analyze.py at 897e93b5
# (copied by line range, never retyped; checked at start-up against the committed blob: verbatim_check)


def out(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    _LINES.append(s)


def head(title):
    out("=" * 118)
    out(title)


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


def decide(arm0_stop, s1_fail, full):
    """NEW (1d.6.3, exhaustive, in this order): 1 any arm-0 failure; 2 S1 fails (full_verdict's STOP); 3 FAIL (S2, S4
    or S5); 4 NOT SHOWN (S3); 5 NOT READY (S6); 6 PASS. full = FULL(0 -> G)'s full_verdict."""
    if arm0_stop:
        return 1
    if s1_fail or full == "STOP":
        return 2
    return {"FAIL": 3, "NOT SHOWN": 4, "NOT READY": 5, "PASS": 6}[full]


def z2_mov(cmds, cmd_ctx, rels, rel_ctx):
    """Z2-M: assign, unassign, release or mark_unreachable commands issued from movement code ('fix:' context): 0."""
    fx = lambda ctx: any(str(x).startswith("fix:") for x in (ctx or ()))           # noqa: E731
    bad = [["command"] + list(c[:7]) for c, ctx in zip(cmds or (), cmd_ctx or ()) if fx(ctx)]
    bad += [["release"] + list(r[:5]) for r, ctx in zip(rels or (), rel_ctx or ()) if fx(ctx)]
    return bad


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


def show_blob(commit, rel):
    rc, blob = git("show", "%s:%s" % (commit, rel))
    return blob.decode("utf-8", "replace") if rc == 0 else None


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


def fresh_recs(recs):
    return [r for r in recs if r["cell"]["fresh"]]


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


def _rline(label, cells, x, y, key, sets=FRESH):
    groups = (("pooled", lambda c: True),) + tuple((s, (lambda c, s=s: c["set"] == s)) for s in sets) + (
        ("ring", lambda c: c["plc"] == "ring"), ("uniform", lambda c: c["plc"] == "uniform"))
    v = {gname: tuple(sum(int(r["g"][a]["num"].get(key, 0) or 0) for r in cells if sel(r["cell"])) for a in (x, y))
         for gname, sel in groups}
    out("    %-58s pooled %5d -> %5d (reported) | %s" % (label, v["pooled"][0], v["pooled"][1], " | ".join(
        "%s %d->%d" % (k, a, b) for k, (a, b) in v.items() if k != "pooled")))


def _median(xs):
    return statistics.median(xs) if xs else None


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


def _text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


# ================================================================================================ VERBATIM: outputs/_dp_analyze.py at cc8d653c (round 1, DPR)


def ledger_check(cmds):
    """G-T(c) + M4 re-used pairs: b_before = successful binds of the pair earlier in dp.commands (the single sink,
    design 5.6). Violations: reassign_stall / reassign_margin with b_before >= 1, joint_replace_latched with
    b_before >= 2."""
    b = collections.Counter()
    viol, reused = [], []
    for c in cmds or ():
        step, phase, action, vid, uid, reason, ok = c[:7]
        if action != "assign" or not ok:
            continue
        before = b[(uid, vid)]
        if reason in ("reassign_stall", "reassign_margin") and before >= 1:
            viol.append([step, phase, uid, vid, reason, before])
        if reason == "joint_replace_latched" and before >= 2:
            viol.append([step, phase, uid, vid, reason, before])
        if before >= 1:
            reused.append([step, uid, vid, reason, before])
        b[(uid, vid)] += 1
    return viol, reused, b


# ================================================================================================ (this port's own code)
# Every function below is NEW or CHANGED for dispatch round 2 and says so in its docstring; the ones above are verbatim.
MVG_VERBATIM = (
    "out", "head",
    "same_path", "mean", "q", "iqr", "fmt", "stdout_path", "parse_stdout", "load_json", "load_run", "first_path",
    "first_div", "hashes", "outside_events", "gt_returns", "m8_classify", "ident_diff", "field_get", "ff_state",
    "cell_means", "drop_most_negative", "wilcoxon", "wil_str", "rb_cut_refusals", "rb_ledgers", "rb_figures",
    "rb_checks_fail",
    "git", "lf", "tup", "collapse", "man", "sha_file", "sha_lf_file", "parse_sets", "arg_of", "ran_of",
    "sign_test_p", "holm", "s3_rule", "cell_seed", "r2_set_test", "compare_counts", "s6_rule", "full_verdict", "decide",
    "z2_mov", "outside_events_amended", "gt_returns_amended", "z_rb", "unit_rows", "zm_a", "zm_b", "ff_cells_by_step",
    "z_s", "guard_dicts", "mp_crosscheck", "zg1", "zg2", "guard_record_problems",
    "mv_dicts", "mv_legs", "leg_events", "latch_episodes", "uav_role_at_rtb_start", "searcher_kinds",
    "writeoff_counts", "stuck_carry_excluded", "kick_flag_check", "shadow_mismatch_zeros", "merge_mismatch",
    "loop_episodes", "free_units_at", "busy_units_at", "vic_pos", "attribute",
    "alive_at", "first_death", "l4_counts", "l4_run_level",
    "m1_compare", "m1_stat",
    "gb_counts", "gt_b_counts", "m6_counts",
    "extract_section", "show_blob", "notes_check", "committed_shas", "lf_sha_at", "run_loaded_changes", "head_rule",
    "run_crash", "read_stdout_stripped", "value_identity",
    "masked", "mask_text", "path_only", "usable", "fresh_recs", "_paired", "_subhead", "_m1_print", "_rline",
    "_median", "module_check", "_text",
)
# the DPR functions (round 1's analyzer) among them, and round 1's ledger_check, checked against _dp_analyze at cc8d653c
DPR_VERBATIM = ("same_path", "mean", "q", "iqr", "fmt", "stdout_path", "parse_stdout", "load_json", "load_run",
                "first_path", "first_div", "hashes", "outside_events", "gt_returns", "m8_classify", "ident_diff",
                "field_get", "ff_state", "cell_means", "drop_most_negative", "wilcoxon", "wil_str", "rb_cut_refusals",
                "rb_ledgers", "rb_figures", "rb_checks_fail", "ledger_check")
# ported from the movement round's analyzer with a change (named in each docstring)
OUTCOME_TEXT = {
    1: "STOP, nothing read (10.8 (1)): an INVALID or missing run in any arm (a tooling defect, re-run), or a zero, SM "
       "row or crash in dq0 or dqR (10.3: a base or instrument defect - fix it, re-run the wave, read nothing; a SHIPPED "
       "movement or guard zero there is a STOP for a maintainer ruling).",
    2: "S1 fails: STOP; the identity defect is fixed and W1 re-run. W2 starts only after S1 passes.",
    3: "S2, S4 or S5 fails: FAIL. DISPATCH_JOINT and DISPATCH_REASSIGN stay 0, and the round's code is NOT merged "
       "(decision 0.2). The measurement round follows with today's dispatch, and there is NO further dispatch round. "
       "Every failing instance is diagnosed, as a report, not a design input.",
    4: "Otherwise S3 fails: NOT SHOWN. Its consequences are those of 3 (decision 0.2): DISPATCH_JOINT and "
       "DISPATCH_REASSIGN stay 0, the round's code is NOT merged, the measurement round follows with today's dispatch, "
       "and there is NO further dispatch round.",
    5: "Otherwise S6 fails: NOT READY. Optimise value-identically (for example by caching J's maps), re-measure the "
       "cost on 8 value-identical cells, and re-apply the rule.",
    6: "Otherwise PASS: recommend shipping DISPATCH_JOINT = 1 and DISPATCH_REASSIGN = 1, then STOP for the maintainer's "
       "confirmation before the flip (only (1, 1) can ship; no sub-switches, X-14).",
}
L4_KEY = "L4 CAUSED vs PREVENTED (W3)"
Q_W1 = os.path.join(HERE, "_dq_q_w1.jsonl")
Q_W2 = os.path.join(HERE, "_dq_q_w2.jsonl")
SMOKE_SUPPRESSED = "SMOKE: outcome sections suppressed (13 (9): smoke outcomes are never read and enter no gate)"
ZEROS_ONLY_LINE = ("ZEROS-ONLY (the wave check, 14): sections 0-3 and the W3 validity only - no outcome section and no "
                   "verdict printed")


# ================================================================================================ small helpers (new)
def id_index(identifier):
    """NEW: the integer tie-break key - the analyzer's own copy of joint_dispatch.id_index's rule: the trailing integer of
    an id, then the id; an id without one sorts after every numbered id."""
    text = str(identifier)
    m = re.search(r"(\d+)$", text)
    return (int(m.group(1)) if m else 10 ** 9, text)


def pkey(u, v):
    """NEW: the 'unit|victim' key of the probe's records."""
    return "%s|%s" % (u, v)


def ukey(key):
    """NEW: 'unit|victim' -> (unit, victim)."""
    u, v = str(key).split("|", 1)
    return u, v


def grid_g(a, b):
    """NEW: G (5.2), the grid (Manhattan) distance - the analyzer's own copy."""
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))


def phase_key(step, phase):
    """NEW: the order of J points: by step, J-pre before J-post."""
    return (int(step), PHASE_RANK.get(str(phase), 9))


def spells(steps):
    """NEW: maximal runs of consecutive integers in `steps` -> [[first, last, length]]."""
    out_ = []
    for s in sorted(set(int(x) for x in steps)):
        if out_ and s == out_[-1][1] + 1:
            out_[-1][1] = s
            out_[-1][2] += 1
        else:
            out_.append([s, s, 1])
    return out_


# ================================================================================================ 0 HEADER
def spec_section(text, n):
    """NEW (12.2): section n of dispatch2_part1.txt - the lines from its top-level header 'n. <Capital>' to the line
    before the next top-level header (SECTION_RE, '^\\d{1,2}\\. [A-Z]') or EOF, trailing blank and '=' banner lines
    dropped, LF-normalised; None when the text or the section is absent."""
    if text is None:
        return None
    lines = lf(text).split("\n")
    i = next((k for k, ln in enumerate(lines) if SECTION_RE.match(ln) and ln.startswith("%d. " % n)), None)
    if i is None:
        return None
    j = next((k for k in range(i + 1, len(lines)) if SECTION_RE.match(lines[k])), len(lines))
    while j > i + 1 and (not lines[j - 1].strip() or set(lines[j - 1].strip()) == {"="}):
        j -= 1
    return "\n".join(lines[i:j])


def section_sha(text, n):
    """NEW: the sha256 of spec_section(text, n)'s UTF-8 bytes, None when absent."""
    s = spec_section(text, n)
    return None if s is None else hashlib.sha256(s.encode("utf-8")).hexdigest()


def hash_checks(current_text=None, blobs=None):
    """NEW (12.2): every hashed section (0, 2-15 and 19) of the working outputs/dispatch2_part1.txt AND of its committed
    blobs (ba647655: sections 0 and 2-15; 87a93cda: 0, 2-15 and 19) has the frozen SECTION_SHA256. A later appended
    amendment (section 20, ...) is reported, never hashed. Returns (ok, lines)."""
    lines, ok = [], True
    if current_text is None:
        try:
            with open(os.path.join(HERE, "dispatch2_part1.txt"), encoding="utf-8") as fh:
                current_text = fh.read()
        except OSError as exc:
            return False, ["  outputs/dispatch2_part1.txt unreadable: %r" % (exc,)]
    if blobs is None:
        blobs = {c: show_blob(c, SPEC_REL) for c in (PART1, RULINGS)}
    for n, want in sorted(SECTION_SHA256.items()):
        got = section_sha(current_text, n)
        refs = {c: section_sha(blobs.get(c), n) for c in SECTION_COMMITS[n]}
        same = got == want and all(v == want for v in refs.values())
        ok = ok and same
        lines.append("  section %2d: frozen sha256 %s | working file %s | %s => %s" % (
            n, want[:16], "==" if got == want else "DIFFERS (%s)" % (got or "absent")[:16],
            ", ".join("%s %s" % (c, "==" if v == want else "DIFFERS (%s)" % (v or "absent")[:16]) for c, v in
                      refs.items()), "identical" if same else "DIFFERS (or unreadable)"))
    for n in range(20, 100):
        s = section_sha(current_text, n)
        if s is not None:
            lines.append("  info: section %d (a later amendment - not hashed) sha256 %s" % (n, s[:16]))
    return ok, lines


def verbatim_check():
    """CHANGED: each function this port claims VERBATIM is a verbatim substring (LF) of its source: MVG_VERBATIM of
    outputs/_mvg_analyze.py at 897e93b5, DPR_VERBATIM of outputs/_dp_analyze.py at cc8d653c."""
    lines, ok = [], True
    for names, commit, rel, what in ((MVG_VERBATIM, MVG_AT, "outputs/_mvg_analyze.py", "mvg"),
                                     (DPR_VERBATIM, DISPATCH, "outputs/_dp_analyze.py", "DPR")):
        blob = show_blob(commit, rel)
        if blob is None:
            ok = False
            lines.append("  cannot read %s at %s" % (rel, commit[:8]))
            continue
        blob = lf(blob)
        bad = [n for n in names if lf(inspect.getsource(globals()[n])) not in blob]
        ok = ok and not bad
        lines.append("  %d %s functions verbatim from %s at %s: %s" % (len(names) - len(bad), what, rel, commit[:8],
                                                                      "all" if not bad else "DIFFER: %s" % bad))
        if what == "mvg":
            try:
                tree = ast.parse(blob)
                node = next(n for n in tree.body if isinstance(n, ast.Assign)
                            and any(getattr(t, "id", None) == "SIGN_KEYS" for t in n.targets))
                theirs = tuple(tuple(x) for x in ast.literal_eval(node.value))
            except Exception as exc:         # noqa: BLE001
                theirs = "unreadable %r" % (exc,)
            same = theirs == SIGN_KEYS_MVG
            ok = ok and same
            lines.append("  SIGN_KEYS: the movement round's 24 %s %s's (+ D1-D4 = the family of %d)" % (
                "==" if same else "DIFFER from", MVG_AT[:8], len(SIGN_KEYS)))
    return ok, lines


def seed_rows(base):
    """NEW (0.6): the rule's rows of one set - [key, scenario, wind, seed] for s in ABCD, w in NSEW, seed = base + 4*s +
    w, sorted by key."""
    return sorted([["%s_%s" % (s, wk), s, wind, str(base + 4 * i + j)] for i, s in enumerate("ABCD")
                   for j, (wk, wind) in enumerate(WINDS)], key=lambda r: r[0])


def load_seeds(path=None, mvg_path=None):
    """NEW (0.6 (7), 8): outputs/_dq_seeds.txt with the rule RECOMPUTED for sets 1-8 from EXPECTED_BASES (set 7 =
    575201, set 8 = 741141); sets 1-6 must equal outputs/_mvg_seeds.txt. STOP (None) on any mismatch; it never scans for
    seeds (the seed-selector self-reference rule)."""
    path = path or os.path.join(HERE, "_dq_seeds.txt")
    mvg_path = mvg_path or os.path.join(HERE, "_mvg_seeds.txt")
    try:
        doc = load_json(path)
    except Exception as exc:                 # noqa: BLE001
        out("STOP: %s unreadable (%r)" % (os.path.basename(path), exc))
        return None
    bad = []
    if doc.get("bases") != EXPECTED_BASES:
        bad.append("bases %r != %r" % (doc.get("bases"), EXPECTED_BASES))
    extra = sorted(k for k in doc if re.fullmatch(r"set\d+", str(k)) and k not in EXPECTED_BASES)
    if extra:
        bad.append("unknown sets %s" % extra)
    seen = {}
    for name, base in EXPECTED_BASES.items():
        expect = seed_rows(base)
        if doc.get(name) != expect:
            bad.append("%s does not follow the rule seed = %d + 4*s + w" % (name, base))
            continue
        for row in expect:
            if row[3] in seen:
                bad.append("seed %s in %s and %s" % (row[3], seen[row[3]], name))
            seen[row[3]] = name
    try:
        mvg = load_json(mvg_path)
        for name in ("set1", "set2", "set3", "set4", "set5", "set6"):
            if mvg.get(name) != doc.get(name):
                bad.append("%s differs from outputs/_mvg_seeds.txt" % name)
    except Exception as exc:                 # noqa: BLE001
        bad.append("outputs/_mvg_seeds.txt unreadable (%r)" % (exc,))
    if bad:
        out("STOP: outputs/_dq_seeds.txt: %s" % bad[:6])
        return None
    out("  frozen cells outputs/_dq_seeds.txt: the rule recomputed for sets 1-8 (bases %s) - identical, 128 distinct "
        "seeds; sets 1-6 == outputs/_mvg_seeds.txt; set 7 = %d-%d, set 8 = %d-%d (fresh)" % (
            EXPECTED_BASES, min(int(r[3]) for r in doc["set7"]), max(int(r[3]) for r in doc["set7"]),
            min(int(r[3]) for r in doc["set8"]), max(int(r[3]) for r in doc["set8"])))
    return {k: doc[k] for k in EXPECTED_BASES}


def sec_header(opts):
    """CHANGED: the round's commits (Part 1 ba647655, the rulings 87a93cda, the base 897e93b5, HEAD, --head), the hash
    checks of 12.2, the verbatim and module checks, the Part 2 notes when given."""
    head("DISPATCH ROUND 2 - THE CORRECTED-DISPATCH SCREEN'S ANALYZER (outputs/dispatch2_part1.txt 10, 11.3, 12.2; "
         "rulings section 19, every option (a))")
    if opts.smoke:
        out("SMOKE - NOT A SCREEN (one cell of the spent sets 1-2 from %s; queue / 360-step / head checks relaxed; the "
            "cell stands in for the fresh set 7; structural fields only, 13 (9))" % opts.smoke)
    for c, what in ((PART1, "Part 1 (sections 0-18, frozen)"), (RULINGS, "rulings amendment A1 (section 19)"),
                    (BASE[:8], "base (main 897e93b5 = dqR's checkout)")):
        rc, txt = git("log", "-1", "--format=%H %ad %s", "--date=short", c)
        out("%-38s %s  %s" % (what + ":", c, txt.decode("utf-8", "replace").strip()[:110] if rc == 0 else "NOT FOUND"))
    rc, hd = git("rev-parse", "HEAD")
    out("%-38s %s" % ("analyzer worktree HEAD:", hd.decode().strip() if rc == 0 else "?"))
    if opts.head:
        rc, txt = git("log", "-1", "--format=%H %ad %s", "--date=short", opts.head)
        anc, _ = git("merge-base", "--is-ancestor", BASE, opts.head)
        anc2, _ = git("merge-base", "--is-ancestor", RULINGS, opts.head)
        out("%-38s %s  %s | descends from the base: %s, from the rulings: %s" % (
            "Part 2 commit (--head, the screen head):", opts.head,
            txt.decode("utf-8", "replace").strip()[:70] if rc == 0 else "NOT FOUND", "yes" if anc == 0 else "NO",
            "yes" if anc2 == 0 else "NO"))
        if anc != 0 or anc2 != 0:
            out("REFUSED: --head %s does not descend from the base %s and the rulings %s" % (opts.head, BASE[:8],
                                                                                            RULINGS))
            return False
    ok, lines = hash_checks()
    for ln in lines:
        out(ln)
    if not ok:
        out("REFUSED: a hashed section of outputs/dispatch2_part1.txt differs from its frozen text (12.2) - no edit of "
            "a pre-registered rule after data; no verdict")
        return False
    vok, lines = verbatim_check()
    mok, mlines = module_check()
    for ln in lines + mlines:
        out(ln)
    if not (vok and mok):
        out("REFUSED: a reused function or module is not the committed one (12.2)")
        return False
    if getattr(opts, "part2_notes", None):
        nok, lines = notes_check(opts.part2_notes)
        for ln in lines:
            out(ln)
        if not nok:
            out("REFUSED: a tooling file or frozen queue differs from the Part 2 notes")
            return False
    else:
        out("  Part 2 notes: NOT CHECKED (no --part2-notes)")
    return True


# ================================================================================================ 1 LOAD + PROV
def screen_cells(frozen, opts):
    """CHANGED: the screen = sets 7-8 x placements ring / uniform x 16 keys = 64 cells, arms R / 0 / 1 (fresh). --smoke:
    the one cell --smoke-cell of the spent sets 1-2, standing in for the fresh set 7."""
    def cell(k, p, plc, mode, key, scen, wind, seed, kind):
        return {"id": "set%d/%s/%s" % (k, plc, key), "set": "set%d" % k, "k": k, "plc": plc, "p": p, "mode": mode,
                "key": key, "scen": scen, "wind": wind, "seed": int(seed), "fresh": kind == "screen", "kind": kind,
                "arms": ARMS}
    allc = []
    for k in (1, 2, 7, 8):
        for p, plc, mode in PLACES:
            for key, scen, wind, seed in frozen["set%d" % k]:
                allc.append((k, p, plc, mode, key, scen, wind, seed))
    if getattr(opts, "smoke", None):
        return [dict(cell(*x, "smoke"), set="set7", fresh=True, spent_id="set%d/%s/%s" % (x[0], x[2], x[4]))
                for x in allc if x[0] in (1, 2) and "set%d/%s/%s" % (x[0], x[2], x[4]) == opts.smoke_cell]
    return [cell(*x, "screen") for x in allc if x[0] in (7, 8)]


def run_path(arm, cell, opts):
    """CHANGED: outputs/_sd_dq<a><p><k>_<S>_<W>.json; --smoke: DIR/<the file given for the arm>."""
    if getattr(opts, "smoke", None):
        f = (opts.smoke_files or {}).get(arm)
        return os.path.join(opts.smoke, f) if f else None
    return os.path.join(HERE, "_sd_%s%s%d_%s.json" % (ARM_TAG[arm], cell["p"], cell["k"], cell["key"]))


def line_name(arm, cell):
    """NEW: the frozen queue's run name dq<a><p><k>_<S>_<W> (= --tag = the pool name)."""
    return "%s%s%d_%s" % (ARM_TAG[arm], cell["p"], cell["k"], cell["key"])


def load_queues():
    """CHANGED: {normcase(out): (wave, line)} over the FROZEN queues outputs/_dq_q_w1.jsonl (dqR + dq0) and
    outputs/_dq_q_w2.jsonl (dq1)."""
    idx = {}
    for wave, p in (("w1", Q_W1), ("w2", Q_W2)):
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip():
                    line = json.loads(ln)
                    idx[os.path.normcase(line["out"])] = (wave, line)
    return idx


def sd_args(argv_l):
    """CHANGED: the _sd_probe.py arguments of a queue line: after the line's first '--' (a _dq_probe.py line), after its
    second (a _dq_replay.py line: replay args -- probe args -- sd args)."""
    if not argv_l or "--" not in argv_l:
        return []
    rest = argv_l[argv_l.index("--") + 1:]
    if os.path.basename(str(argv_l[0])) == "_dq_replay.py":
        rest = rest[rest.index("--") + 1:] if "--" in rest else []
    return rest


def expected_switches(line_sets):
    """CHANGED (section 9): the three movement switches are pinned 1 on every line (ON only on an exact 1; the guard OFF
    only on an exact 0)."""
    return {"FF_APPROACH_PATH": line_sets.get("FF_APPROACH_PATH") == 1,
            "FF_RETREAT_KEEP_APPROACH": line_sets.get("FF_RETREAT_KEEP_APPROACH") == 1,
            "FF_FIX_STRANDING_GUARD": line_sets.get("FF_FIX_STRANDING_GUARD", 1) != 0}


def src_check(d, commit, arm):
    """CHANGED: every source sha the run recorded (dp / ud / mvg / dq .src_sha) equals the file at `commit` (dqR: BASE;
    dq0 / dq1 / replays: --head), LF or CRLF form; ud / mvg / dq name every MVG_SRC_REQUIRED file and dq (dq0 / dq1)
    the joint dispatcher; a dqR record names NO joint_dispatch.py (main has none). INVALID otherwise ('ran uncommitted
    source'). Returns the reasons."""
    why = []
    for sec in ("dp", "ud", "mvg", "dq"):
        shas = (d.get(sec) or {}).get("src_sha") if isinstance(d.get(sec), dict) else None
        if not isinstance(shas, dict) or not shas:
            why.append("ran uncommitted source? %s.src_sha not recorded" % sec)
            continue
        if sec in ("ud", "mvg", "dq"):
            need = MVG_SRC_REQUIRED + ((JD_REL,) if (sec == "dq" and arm != "R") else ())
            miss = [r for r in need if r not in shas]
            if miss:
                why.append("%s.src_sha does not name %s" % (sec, miss))
        if arm == "R" and JD_REL in shas:
            why.append("dqR's %s.src_sha names %s (main 897e93b5 has no joint_dispatch module)" % (sec, JD_REL))
        bad = [rel for rel, sha in sorted(shas.items()) if sha not in (committed_shas(commit, rel) or ())]
        if bad:
            why.append("ran uncommitted source: %s.src_sha differs from %s for %s" % (sec, commit[:10], bad[:4]))
    return why


def instrument_check(d, head_sha):
    """CHANGED: the instrument that wrote the run is the committed one at --head (every arm runs the dispatch worktree's
    probe, dqR included): dq.probe_sha == mvg.probe_sha == outputs/_dq_probe.py's LF sha256 at --head; dq.r1_shadow_sha
    == outputs/_dq_r1_shadow.py's; mvg.u1_shadow_sha == outputs/_mvg_u1_shadow.py at --head (LF or CRLF form). INVALID
    otherwise."""
    why = []
    dq = d.get("dq") if isinstance(d.get("dq"), dict) else {}
    mvg = d.get("mvg") if isinstance(d.get("mvg"), dict) else {}
    want = lf_sha_at(head_sha, PROBE_REL)
    if want is None:
        return ["%s is not in %s" % (PROBE_REL, head_sha[:10])]
    for name, got in (("dq.probe_sha", dq.get("probe_sha")), ("mvg.probe_sha", mvg.get("probe_sha"))):
        if got != want:
            why.append("ran an uncommitted instrument: %s %s is not %s at %s (LF %s)" % (name, str(got)[:16], PROBE_REL,
                                                                                       head_sha[:10], want[:16]))
    r1 = lf_sha_at(head_sha, R1_SHADOW_REL)
    if dq.get("r1_shadow_sha") != r1:
        why.append("ran an uncommitted round-1 shadow: dq.r1_shadow_sha %s is not %s at %s" % (
            str(dq.get("r1_shadow_sha"))[:16], R1_SHADOW_REL, head_sha[:10]))
    if mvg.get("u1_shadow_sha") not in (committed_shas(head_sha, U1_SHADOW_REL) or ()):
        why.append("ran an uncommitted U1 shadow copy: mvg.u1_shadow_sha %s is not %s at %s" % (
            str(mvg.get("u1_shadow_sha"))[:16], U1_SHADOW_REL, head_sha[:10]))
    return why


def j_record_problems(d, arm):
    """NEW: the J record's own bookkeeping (an instrument problem, INVALID): with J off (dqR, dq0) every J field is
    empty and no J point is recorded; with J on (dq1) j_calls and j_timing are aligned, zr1.jpoints counts the j_detail
    entries, every j_detail entry is complete, and the U1 kick shadow is gated off (12.1: no kick record)."""
    dp = d.get("dp") if isinstance(d.get("dp"), dict) else {}
    dq = d.get("dq") if isinstance(d.get("dq"), dict) else {}
    why = []
    jc, jt, jdl = dp.get("j_calls") or [], dp.get("j_timing") or [], dp.get("j_detail") or []
    if arm in ("R", "0"):
        for name in ("j_calls", "j_detail", "j_timing", "j_events"):
            if dp.get(name):
                why.append("J off: dp.%s holds %d entries" % (name, len(dp.get(name))))
        if (dq.get("zr1") or {}).get("jpoints") or (dq.get("footprint") or {}).get("jpoints"):
            why.append("J off: J points recorded in d['dq']")
        return why
    if len(jc) != len(jt) or any(list(a[:2]) != list(b[:2]) for a, b in zip(jc, jt)):
        why.append("dp.j_calls (%d) and dp.j_timing (%d) are not aligned" % (len(jc), len(jt)))
    if (dq.get("zr1") or {}).get("jpoints") != len(jdl):
        why.append("dq.zr1.jpoints %r != %d j_detail entries" % ((dq.get("zr1") or {}).get("jpoints"), len(jdl)))
    need = ("sets", "pre", "calls", "progress_before", "progress", "unevaluated", "initialised", "inst", "contests",
            "zr1", "fp")
    for row in jdl:
        if len(row) < 3 or not isinstance(row[2], dict):
            why.append("a j_detail entry is not [step, phase, cur]")
            break
        miss = [k for k in need if k not in row[2]]
        if miss:
            why.append("j_detail step %s %s: missing %s" % (row[0], row[1], miss))
            break
    if (d.get("ud") or {}).get("kicks"):
        why.append("J on but the U1 kick shadow made %d kick records (12.1: gated off)" % len(d["ud"]["kicks"]))
    if (dq.get("footprint") or {}).get("errors"):
        why.append("instrument errors dq.footprint.errors %s" % (dq["footprint"]["errors"][:2],))
    if dq.get("r1_shadow_error"):
        why.append("the round-1 J shadow did not load: %s" % str(dq.get("r1_shadow_error"))[:120])
    return why


def prov_run(d, path, line, cell, arm, opts):
    """CHANGED (the movement round's validity, for the three arms of section 9): (INVALID reasons, crash text or None,
    STOP reason or None). A crashed run (crash flag, chain exit code != 0, or an early stop) is Z6 material - an S2 FAIL
    in dq1, a STOP in dq0 / dqR - so the CRN-draw and stdout reasons a crash itself causes are NOT added. INVALID (a
    tooling defect, re-run): no frozen queue line; repo / argv / .argv signature / steps / extra_params differing from
    the line; a head the head rule rejects (dqR: not BASE itself); uncommitted source or instrument (src_check,
    instrument_check); 0 CRN draws; dp not dp_probe v3 or with errors or a successful assign stamped init / sweep (R-B's
    cut); dq / ud / mvg not dq_probe v1 or with errors; the movement switches not the pinned ones; the dispatch switches
    not the arm's (dqR: no DISPATCH_* key; dq0: both 0, off; dq1: both 1, on); the J record's bookkeeping
    (j_record_problems); the schemas (mv, guard, sample, ff_log); the _survival_move replica disagreeing with the model.
    ud.shadow_mismatch is behaviour (SM / Z1-M / Zg-1), never INVALID."""
    why, stop = [], None
    if d.get("dp_only"):
        return ["the chain wrote no sd JSON"] if not isinstance(d.get("dp"), dict) else [], \
            "no sd record (dp_only - crashed)", None
    smoke = bool(getattr(opts, "smoke", None))
    argv_l = (line or {}).get("argv") or []
    sd_argv = sd_args(argv_l)
    sets = parse_sets(sd_argv) if line else dict(d.get("extra_params") or {})
    dp = d.get("dp") if isinstance(d.get("dp"), dict) else None
    crashed_run = bool(d.get("crashed")) or ((dp or {}).get("rc_chain") not in (0, None))
    exp_steps = d.get("steps") if smoke else int(arg_of(sd_argv, "--steps") or H)
    crash = run_crash(d, exp_steps)
    replay = bool(argv_l) and os.path.basename(str(argv_l[0])) == "_dq_replay.py"
    if not smoke:
        if line is None:
            why.append("no line in the frozen queues outputs/_dq_q_w1 / w2 / w3.jsonl")
        else:
            want_repo = ARM_REPO[arm]
            if not same_path(d.get("repo"), want_repo) or not same_path(arg_of(sd_argv, "--repo"), want_repo):
                why.append("repo %s (argv %s) != %s" % (d.get("repo"), arg_of(sd_argv, "--repo"), want_repo))
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
            if arm == "R":
                if not str(d.get("head") or "").startswith(BASE):
                    why.append("dqR head %s is not main %s" % (str(d.get("head"))[:10], BASE[:10]))
            else:
                why += head_rule(d.get("head"), opts.head, replay)
    if opts.head:
        why += src_check(d, BASE if arm == "R" else opts.head, arm)
        why += instrument_check(d, opts.head)
    if d.get("extra_params") != sets:
        why.append("extra_params %s != the queue line's %s" % (json.dumps(d.get("extra_params"), sort_keys=True),
                                                              json.dumps(sets, sort_keys=True)))
    crn = (d.get("fb3") or {}).get("crn") or {}
    want_crn = ("--crn" in argv_l) if line else True
    if crash is None and want_crn and not (crn.get("on") and int(crn.get("crn_draws") or 0) > 0):
        why.append("CRN on %s with crn_draws %s (section 9: 0 draws is INVALID)" % (crn.get("on"),
                                                                                    crn.get("crn_draws")))
    if not want_crn and crn.get("on"):
        why.append("CRN on in a CRN-off line")
    if "VICTIM_SPAWN_MODE" in sets and (d.get("fb3") or {}).get("eff", {}).get("victim_spawn_mode") != sets[
            "VICTIM_SPAWN_MODE"]:
        why.append("fb3.eff.victim_spawn_mode %s" % (d.get("fb3") or {}).get("eff", {}).get("victim_spawn_mode"))
    want_sw = expected_switches(sets)
    want_j = ARM_DISPATCH[arm]
    if dp is None:
        why.append("dp section missing")
    else:
        if dp.get("probe") != DP_PROBE:
            why.append("dp.probe %r (the screen reads %r records only)" % (dp.get("probe"), DP_PROBE))
        if dp.get("errors"):
            why.append("instrument errors dp.errors %s" % dp["errors"][:2])
        refused = rb_cut_refusals(dp.get("commands"))
        if refused and not (arm == "1" and crashed_run):
            why.append("REFUSED (R-B cut, tooling): successful assign stamped init / sweep %s" % refused[:3])
        sw = dp.get("switches") or {}
        if bool(sw.get("joint_on")) is not bool(want_j) or bool(sw.get("reassign_on")) is not bool(want_j):
            why.append("dp.switches joint_on %s reassign_on %s, the arm %s means %s" % (
                sw.get("joint_on"), sw.get("reassign_on"), arm, bool(want_j)))
    ud = d.get("ud") if isinstance(d.get("ud"), dict) else None
    if ud is None:
        why.append("ud section missing")
    else:
        if ud.get("probe") != DQ_PROBE:
            why.append("ud.probe %r (the screen reads %r records only)" % (ud.get("probe"), DQ_PROBE))
        if ud.get("errors"):
            why.append("instrument errors ud.errors %s" % ud["errors"][:2])
        usw = ud.get("switches") or {}
        got = {k: bool(usw.get(k)) for k in want_sw}
        if got != want_sw:
            why.append("ud effective switches %s != the line's %s" % (got, want_sw))
        if usw.get("DISPATCH_URGENCY") or usw.get("FF_CARRY_REPLAN"):
            why.append("U1 or fix (c) effective (not in this round)")
        if dp is not None:
            if len(ud.get("cmd_ctx") or []) != len(dp.get("commands") or []):
                why.append("ud.cmd_ctx not aligned with dp.commands")
            if len(ud.get("rel_ctx") or []) != len(dp.get("releases") or []):
                why.append("ud.rel_ctx not aligned with dp.releases")
    mvg = d.get("mvg") if isinstance(d.get("mvg"), dict) else None
    if mvg is None:
        why.append("mvg section missing")
    else:
        if mvg.get("probe") != DQ_PROBE:
            why.append("mvg.probe %r" % mvg.get("probe"))
        if mvg.get("errors"):
            why.append("instrument errors mvg.errors %s" % mvg["errors"][:2])
        msw = mvg.get("switches") or {}
        got = {k: bool(msw.get(k)) for k in want_sw}
        if got != want_sw:
            why.append("mvg effective switches %s != the line's %s" % (got, want_sw))
        if tuple((mvg.get("guard") or {}).get("cols") or ()) != GUARD_COLS:
            why.append("d['mvg']['guard'] columns differ from the instrument's schema")
        rp = mvg.get("replica") or {}
        for k_ in ("mismatch", "cell_mismatch"):
            if rp.get(k_):
                why.append("instrument: the _survival_move replica disagrees with the model (replica.%s %s)" % (
                    k_, rp[k_][:2]))
    dq = d.get("dq") if isinstance(d.get("dq"), dict) else None
    if dq is None:
        why.append("dq section missing")
    else:
        if dq.get("probe") != DQ_PROBE:
            why.append("dq.probe %r" % dq.get("probe"))
        if dq.get("errors"):
            why.append("instrument errors dq.errors %s" % dq["errors"][:2])
        qsw = dq.get("switches") or {}
        raw = qsw.get("raw") or {}
        if arm == "R":
            if any(raw.get(k) not in ("None", None) for k in ("DISPATCH_JOINT", "DISPATCH_REASSIGN")) or \
                    any(k.startswith("DISPATCH_") for k in sets):
                why.append("dqR: a DISPATCH_* key exists or is set (main 897e93b5 has none)")
        else:
            want_raw = "1" if want_j else "0"
            if raw.get("DISPATCH_JOINT") != want_raw or raw.get("DISPATCH_REASSIGN") != want_raw or \
                    sets.get("DISPATCH_JOINT") != int(want_raw) or sets.get("DISPATCH_REASSIGN") != int(want_raw):
                why.append("dispatch switches recorded %s / pinned %s, the arm %s pins both %s" % (
                    {k: raw.get(k) for k in ("DISPATCH_JOINT", "DISPATCH_REASSIGN")},
                    {k: sets.get(k) for k in ("DISPATCH_JOINT", "DISPATCH_REASSIGN")}, arm, want_raw))
        if bool(qsw.get("joint_on")) is not bool(want_j) or bool(qsw.get("reassign_on")) is not bool(want_j):
            why.append("dq.switches joint_on %s reassign_on %s, the arm %s means %s" % (
                qsw.get("joint_on"), qsw.get("reassign_on"), arm, bool(want_j)))
        got = {k: bool(qsw.get(k)) for k in want_sw}
        if got != want_sw:
            why.append("dq effective switches %s != the line's %s" % (got, want_sw))
        smp = dq.get("sample") or {}
        if tuple(smp.get("cols") or ()) != SAMPLE_COLS or tuple(smp.get("unit_cols") or ()) != SAMPLE_UNIT_COLS:
            why.append("d['dq']['sample'] columns differ from the instrument's schema")
        if tuple((dq.get("ff_log") or {}).get("cols") or ()) != FFLOG_COLS:
            why.append("d['dq']['ff_log'] columns differ from the instrument's schema")
        if crash is None and not smp.get("rows"):
            why.append("d['dq']['sample'] holds no row")
    why += j_record_problems(d, arm)
    mv = d.get("mv")
    if not isinstance(mv, dict) or tuple(mv.get("cols") or ()) != MV_COLS:
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


# ================================================================================================ S1 (10.2; pure)
S1_DP_REQUIRED = ("binders", "waiting", "waiting_custody", "m3a", "invariant", "commands", "releases", "m8", "m9",
                  "writeoffs_avoided")
S1_SECTIONS = ("fb3", "mr", "ut")
MV_DROP = ("fix_ms", "inst_ms")
GUARD_DROP = ("ms_guard", "ms_inst")
MISSING = "<MISSING>"


def _drop_cols(rows, cols, drop):
    """NEW: rows without the named columns."""
    keep = [i for i, c in enumerate(cols) if c not in drop]
    return [[r[i] for i in keep] for r in rows]


def s1_fields(d):
    """NEW (10.2): {field: value} of one record on the FROZEN S1 field list - round 1's G-ID fields (_fx3r_analyze
    FIELDS; every mf2 section but its probe string; stdout_sha; every non-J dp field: S1_DP_REQUIRED by name, plus any
    other dp key outside J_ONLY, as round 1's ident_diff compares them); eval and rows_uav / ff / vic / dec / trig; fb3,
    mr and ut; the movement record (mv rows without fix_ms / inst_ms and mv cols, mv_events, the guard rows without
    ms_guard / ms_inst); the arm-independent per-step sample and the firefighting log. A field absent from the record
    reads MISSING (an S1 failure even when absent from both). NOT compared: tag, repo, head, out, argv, extra_params,
    wall_s, params (the cfv keys absent at main), and the J-only fields (dp J_ONLY, d['dq'] but its sample and ff_log,
    ud, mvg but its guard rows)."""
    res = {}
    for f in tuple(R.FIELDS) + tuple(x for x in ("eval", "stdout_sha") + ROW_KINDS if x not in R.FIELDS):
        res[f] = d[f] if f in d else MISSING
    mf2 = d.get("mf2")
    if not isinstance(mf2, dict):
        res["mf2"] = MISSING
    else:
        for k in sorted(mf2):
            if k != "probe":
                res["mf2." + k] = mf2[k]
    dp = d.get("dp")
    if not isinstance(dp, dict):
        res["dp"] = MISSING
    else:
        for k in S1_DP_REQUIRED:
            res["dp." + k] = dp[k] if k in dp else MISSING
        for k in sorted(set(dp) - set(J_ONLY) - set(S1_DP_REQUIRED)):
            res["dp." + k] = dp[k]
    for sec in S1_SECTIONS:
        res[sec] = d[sec] if sec in d else MISSING
    mv = d.get("mv")
    res["mv.rows (no fix_ms / inst_ms)"] = MISSING if not isinstance(mv, dict) else _drop_cols(
        mv.get("rows") or [], mv.get("cols") or [], MV_DROP)
    res["mv.cols"] = MISSING if not isinstance(mv, dict) else mv.get("cols")
    res["mv_events"] = d["mv_events"] if "mv_events" in d else MISSING
    g = (d.get("mvg") or {}).get("guard") if isinstance(d.get("mvg"), dict) else None
    res["mvg.guard.rows (no ms_guard / ms_inst)"] = MISSING if not isinstance(g, dict) else _drop_cols(
        g.get("rows") or [], g.get("cols") or list(GUARD_COLS), GUARD_DROP)
    dq = d.get("dq") if isinstance(d.get("dq"), dict) else {}
    res["dq.sample"] = dq["sample"] if "sample" in dq else MISSING
    res["dq.ff_log"] = dq["ff_log"] if "ff_log" in dq else MISSING
    return res


def s1_compare(fa, fb):
    """NEW (10.2): (failing field names, [(name, ok, path)]) of two s1_fields maps: a field fails when it differs or is
    MISSING from either record; path = the first differing leaf's path (first_path), never a value."""
    rows, bad = [], []
    for k in sorted(set(fa) | set(fb)):
        x, y = fa.get(k, MISSING), fb.get(k, MISSING)
        ok = x == y and x != MISSING
        detail = ""
        if not ok:
            if x == MISSING or y == MISSING:
                detail = "MISSING in %s" % ("both" if x == y else "dqR" if x == MISSING else "dq0")
            else:
                detail = path_only(first_path(x, y, k))
            bad.append(k)
        rows.append((k, ok, detail))
    return bad, rows


# ================================================================================================ DIVERGED (10.6; pure)
def cmd_sequence(cmds):
    """NEW (10.6): the command sequence as DIVERGED compares it - (step, action, victim, unit, ok), no reason strings."""
    return [[c[0], c[2], c[3], c[4], bool(c[6])] for c in cmds or ()]


def diverged(gx, gy):
    """NEW (10.6): (diverged, what) - a cell is DIVERGED when its per-step rows (rows_ff / vic / uav / dec / trig, as
    row hashes), eval or command sequence differ between the two arms."""
    what = [k for k in ROW_KINDS if (gx.get("h") or {}).get(k) != (gy.get("h") or {}).get(k)]
    if gx.get("eval") != gy.get("eval"):
        what.append("eval")
    if gx.get("cmd_seq") != gy.get("cmd_seq"):
        what.append("commands")
    return bool(what), what


def diverged_assertion(nx, ny, div):
    """NEW (10.6): every cell with a non-zero delta in a gated count (F1 ff deaths, L2 rescued, L3 / S3 DD and the 28
    sign-tested counts) must be DIVERGED. Returns the offending [cell, count] pairs ([] = the assertion holds)."""
    keys = GATED_LITERAL_KEYS + tuple(k for k, _l in SIGN_KEYS)
    bad = []
    for c in sorted(set(nx) & set(ny)):
        if c in div:
            continue
        for k in keys:
            if int(nx[c].get(k, 0) or 0) != int(ny[c].get(k, 0) or 0):
                bad.append([c, k])
    return bad


# ================================================================================================ the J point (pure)
def jp_dist(cur, v, u, i):
    """NEW: the instrument's own value i (0 d, 1 D_c, 2 d*, 3 clean) of unit u to victim v at a J point; None when absent
    (or infinite)."""
    row = ((((cur.get("inst") or {}).get("dist") or {}).get(v)) or {}).get(u)
    return None if row is None else row[i]


def jp_has(cur, v, u):
    """NEW: whether the instrument recorded unit u's values to victim v at the J point."""
    return u in ((((cur.get("inst") or {}).get("dist") or {}).get(v)) or {})


def own_progress(before, route_open, d_now, c_now, d_hist, c_hist, cell, frozen):
    """NEW - the analyzer's OWN implementation of R-1's history rule with C2's counts (2.8, 5.2), with amendment A2's
    reading (section 20; joint_dispatch.progress_step's): a metric with no finite value over H is not compared. before =
    [H, k, k_L, ...]. CLOSED route: H grows by the cell, k unchanged, k_L + 1 unless FROZEN. OPEN: k_L = 0; PROGRESS
    iff d = 0, or d beats the least finite d over H, or a finite D_c beats the least finite D_c over H; progress -> H =
    [cell], k = 0; else H grows, k + 1 unless FROZEN. Returns (H', k', k_L', closed', progressed or None, the LITERAL 2.8
    verdict - an empty minimum read as infinite - or None)."""
    H, k, kl = before[0], int(before[1]), int(before[2])
    here = (int(cell[0]), int(cell[1]))
    grown = sorted({(int(c[0]), int(c[1])) for c in H} | {here})
    if not route_open:
        return [list(c) for c in grown], k, kl + (0 if frozen else 1), True, None, None
    fd = [int(x) for x in d_hist if x is not None]
    fc = [int(x) for x in c_hist if x is not None]
    bd, bc = (min(fd) if fd else None), (min(fc) if fc else None)
    prog = d_now is not None and (int(d_now) == 0 or (bd is not None and int(d_now) < bd)
                                  or (c_now is not None and bc is not None and int(c_now) < bc))
    lit = d_now is not None and (int(d_now) == 0 or int(d_now) < (bd if bd is not None else math.inf)
                                 or (c_now is not None and int(c_now) < (bc if bc is not None else math.inf)))
    if prog:
        return [list(here)], 0, 0, False, True, lit
    return [list(c) for c in grown], k + (0 if frozen else 1), 0, False, False, lit


def own_persist(prev, spare_d, delta, margin):
    """NEW (6.5, C1): the margin persistence counters, the analyzer's own copy: spare B's count = its previous count + 1
    where d*(B) + M <= delta, else dropped (every spare, fresh or re-used; an absent spare drops)."""
    res = {}
    for unit, dd in (spare_d or {}).items():
        if dd is None or delta is None:
            continue
        if int(dd) + int(margin) <= int(delta):
            res[str(unit)] = int((prev or {}).get(unit, 0) or 0) + 1
    return res


def own_fill(units, victims, dist, clean, ledger, capped=()):
    """NEW (4.2; Z-C1a's reference): the fill by exhaustive enumeration over the VICTIMS (a different traversal from
    joint_dispatch's): the lexicographically best injective matching by L1 most victims served, L1b most clean-approach
    pairs, L2' least total d*, L3' least worst d*, L4' fewest re-used pairs (ledger b >= 1), L5 the smallest sorted
    (victim index, unit index) list (id_index). dist[(u, v)] = d* (None = no route), clean[(u, v)], ledger[(u, v)] = b;
    a capped victim refuses b >= 2 (none in round 2). Returns sorted [(victim, unit)], or None above
    FILL_MAX_CONFIGURATIONS (design 5.5)."""
    us = sorted({str(u) for u in units}, key=id_index)
    vs = sorted({str(v) for v in victims}, key=id_index)
    n_configs = sum(math.comb(len(us), k) * math.perm(len(vs), k) for k in range(min(len(us), len(vs)) + 1))
    if n_configs > FILL_MAX_CONFIGURATIONS:
        return None
    cap = {str(v) for v in capped}
    options = {}
    for v in vs:
        row = []
        for u in us:
            dd = dist.get((u, v))
            b = int(ledger.get((u, v), 0) or 0)
            if dd is None or (v in cap and b >= 2):
                continue
            row.append((u, int(dd), b >= 1, bool(clean.get((u, v), False))))
        options[v] = row
    best = [None, []]

    def walk(i, used, chosen):
        if i == len(vs):
            key = (-len(chosen), -sum(1 for c in chosen if c[4]), sum(c[2] for c in chosen),
                   max((c[2] for c in chosen), default=0), sum(1 for c in chosen if c[3]),
                   sorted((id_index(c[0]), id_index(c[1])) for c in chosen))
            if best[0] is None or key < best[0]:
                best[0], best[1] = key, list(chosen)
            return
        v = vs[i]
        walk(i + 1, used, chosen)
        for u, dd, reused, cl in options[v]:
            if u in used:
                continue
            chosen.append((v, u, dd, reused, cl))
            walk(i + 1, used | {u}, chosen)
            chosen.pop()

    walk(0, frozenset(), [])
    return sorted([(c[0], c[1]) for c in best[1]], key=lambda p: (id_index(p[0]), id_index(p[1])))


def own_plan(contests, spares, dist, clean, ledger, stall_steps, margin_persist):
    """NEW (4.3, 5.2, 2.8 R-2 (a); Z-C1b's reference) - step 3, the analyzer's own copy of the rule: contests = dicts
    {victim, incumbent, delta, open, k, k_closed, persist, latched}; count = k if open else k_closed. QUALIFYING spares
    (the ledger not consulted): unused in this frame, a clean approach, a route, and STALL d*(B) < delta + count (count
    >= S) or MARGIN persistence >= P. The new unit is the lowest-id ledger-ALLOWED spare (REPLACE b = 0, LATCH-FILL b
    <= 1) at the least d* (D); if every qualifying spare at D is barred: no replacement, a barred record. Stalled
    contests first by largest count, then largest gain (delta - D), then victim id; then margin contests (ordered after
    the stall decisions) by largest gain, then victim id. Returns (replacements [[victim, old, new, cause, D,
    latched]], barred [[victim, incumbent, cause, D, [units]]])."""
    sp = sorted({str(s) for s in spares}, key=id_index)
    used, reps, barred = set(), [], []

    def count(c):
        return int(c["k"]) if c["open"] else int(c["k_closed"])

    def qual(c, stall):
        found = []
        for u in sp:
            if u in used or not clean.get((u, c["victim"]), False):
                continue
            dd = dist.get((u, c["victim"]))
            if dd is None:
                continue
            if stall:
                if not int(dd) < int(c["delta"]) + count(c):
                    continue
            elif int((c["persist"] or {}).get(u, 0) or 0) < int(margin_persist):
                continue
            found.append((int(dd), u))
        return found

    def gain(c, stall):
        q_ = qual(c, stall)
        return (int(c["delta"]) - min(d for d, _ in q_)) if q_ else -(10 ** 9)

    def decide(c, stall):
        q_ = qual(c, stall)
        if not q_:
            return
        least = min(d for d, _ in q_)
        ties = sorted((u for d, u in q_ if d == least), key=id_index)
        b_ok = [u for u in ties if (int(ledger.get((u, c["victim"]), 0) or 0) <= 1 if c["latched"]
                                    else int(ledger.get((u, c["victim"]), 0) or 0) == 0)]
        cause = "stall" if stall else "margin"
        if not b_ok:
            barred.append([c["victim"], c["incumbent"], cause, least, list(ties)])
            return
        used.add(b_ok[0])
        reps.append([c["victim"], c["incumbent"], b_ok[0], cause, least, bool(c["latched"])])

    stalled = [c for c in contests if count(c) >= int(stall_steps)]
    margins = [c for c in contests if count(c) < int(stall_steps)]
    for c in sorted(stalled, key=lambda c: (-count(c), -gain(c, True), id_index(c["victim"]))):
        decide(c, True)
    for c in sorted(margins, key=lambda c: (-gain(c, False), id_index(c["victim"]))):
        decide(c, False)
    return reps, barred


def _prow(row):
    """NEW: a progress row [H, k, k_L, closed, age, persist] in a canonical form (None stays None)."""
    if row is None:
        return None
    return [[[int(c[0]), int(c[1])] for c in row[0]], int(row[1]), int(row[2]), bool(row[3]), int(row[4]),
            {str(u): int(n) for u, n in (row[5] or {}).items()}]


def jpoint_zeros(cur, step, phase, ev):
    """NEW (10.3) - the dispatch-owned zeros of ONE J point (a j_detail entry: PRE held), recomputed from the probe's
    recorded J inputs (the _cap records' candidate sets and ledger counts) and the instrument's OWN maps (cur['inst']:
    d, D_c, d*, clean for every living unit to every victim of interest; the d / D_c of the state's H cells), never
    from J's outputs, which are what is checked. ev = the model's J events of this J point (dp.j_events at its step and
    phase). Zeros:
      Z-R1  every d, D_c, d*, clean, delta, FROZEN, the state passed and every progress verdict and persistence count J
            passed to or got from its pure functions equals the analyzer's recomputation (own_progress / own_persist on
            the instrument's values); every contest with a state at entry evaluated exactly once; the plan's contest
            rows and spare values; the state J keeps at exit (the verdict, a bind's fresh state); the probe's own in-run
            Z-R1 list and 'unevaluated' empty;
      Z-C1a every fill (stage 2 and 4) over its own candidate sets (stage 2: the free units x the fill victims; stage
            4: the units released by an applied REPLACE x W not filled in step 2) attains own_fill's optimum; capped
            empty; every applied fill bind was chosen;
      Z-C1b the plan's spares are the free units not bound in step 2; J's replacements and nearest-barred records equal
            own_plan's (nearest qualifying spare, lowest-id ALLOWED at D, else the incumbent kept); every applied
            replacement was planned, every nearest-barred record has its event;
      Z-C2  every planned replacement meets its rule with 5.2's delta and count on the analyzer's recomputation: STALL
            count >= S and d*(B) < delta + count (open: d*, k; closed: G, k_L); MARGIN count < S, persistence >= P and
            d*(B) + M <= delta; the distance is the instrument's d*(B); the kind matches the incumbent's label;
      Z-R2  every challenger (planned or applied) had a clean approach;
      I4-W  at the end of the J call no free unit and unserved W victim form a pair with a finite route (W is never
            capped, so every finite pair is allowed);
      Z-C3  (here) every planned replacement was applied or aborted, and J called only its four pure functions.
    Returns (Z {zero: [[step, phase, text]]}, stats Counter)."""
    Z = collections.defaultdict(list)
    st = collections.Counter()

    def bad(z, text):
        Z[z].append([step, phase, str(text)[:300]])

    miss = [k for k in ("sets", "calls", "progress_before", "progress", "inst") if k not in cur]
    if miss:
        bad("Z-R1", "j_detail entry incomplete: %s" % miss)
        return Z, st
    s, inst = cur["sets"], cur["inst"]
    S_, M_, P_ = (list(inst.get("SMP") or []) + [None, None, None])[:3]
    if S_ is None or M_ is None or P_ is None:
        bad("Z-R1", "S, M, P not recorded at the J point (inst.SMP %r)" % (inst.get("SMP"),))
        return Z, st
    free = [str(u) for u in s.get("free") or []]
    W = [str(v) for v in s.get("waiting") or []]
    reassign, post = bool(s.get("reassign")), bool(s.get("post"))
    ucell, vcell = inst.get("ucell") or {}, inst.get("vcell") or {}

    def dv(v, u, i):
        return jp_dist(cur, v, u, i)

    def clean(u, v):
        return bool(dv(v, u, 3))

    applied = [e for e in ev if e.get("kind") in J_BIND_KINDS]
    s2 = [e for e in applied if e.get("stage") == 2]
    s3 = [e for e in applied if e.get("stage") == 3]
    s4 = [e for e in applied if e.get("stage") == 4]
    s2_u = {str(e.get("unit")) for e in s2}
    s2_v = {str(e.get("victim_id")) for e in s2}
    for p in cur.get("zr1") or []:
        bad("Z-R1", "the probe's in-run Z-R1: %s" % p)
    for row in cur.get("unevaluated") or []:
        bad("Z-R1", "contest %s held a state at J entry and got no progress verdict" % pkey(*row[:2]))
    by_fn = collections.defaultdict(list)
    for c in cur.get("calls") or []:
        by_fn[c.get("fn")].append(c)
    other = sorted(str(f) for f in by_fn if f not in ("solve_fill", "progress_step", "update_persistence",
                                                      "plan_replacements_detail"))
    if other:
        bad("Z-C3", "J called an unknown pure function %s" % other)
    prog_rec, pers_rec = collections.defaultdict(list), collections.defaultdict(list)
    for fn, store in (("progress_step", prog_rec), ("update_persistence", pers_rec)):
        for c in by_fn[fn]:
            b = c.get("binding")
            if not b:
                bad("Z-R1", "a %s record without its binding" % fn)
                continue
            store[pkey(b[0], b[1])].append(c)
    # ---- 1 PROGRESS: the analyzer's verdict for every contest (active and latched, open and closed)
    pairs = (list((s.get("contest") or {}).items()) + list((s.get("latched_binder") or {}).items())) \
        if (reassign and post) else []
    model = collections.OrderedDict()
    for v, a in pairs:
        v, a = str(v), str(a)
        key = pkey(a, v)
        if a not in ucell or v not in vcell or not jp_has(cur, v, a):
            bad("Z-R1", "contest %s: no instrument value" % key)
            continue
        uc = ucell[a]
        cell = [int(uc[0]), int(uc[1])]
        d = dv(v, a, 0)
        op = d is not None
        c_ = dv(v, a, 1) if op else None
        delta = dv(v, a, 2) if op else grid_g(cell, vcell[v])
        fz = not (clean(a, v) or any(clean(f, v) for f in free))
        before = _prow(cur["progress_before"].get(key))
        m = {"v": v, "a": a, "cell": cell, "open": op, "d": d, "c": c_, "delta": delta, "frozen": fz,
             "latched": str(uc[3]).strip().lower() == "route_blocked", "unclean": bool(uc[2]), "before": before}
        if before is None:
            m.update(after=[[cell], 0, 0, False, 0], evaluated=False, progressed=None, persist0={})
        else:
            hrow = ((inst.get("hist") or {}).get(key) or {}).get("H")
            if hrow is None or len(hrow) != len(before[0]):
                bad("Z-R1", "contest %s: the instrument's H reads (%s) do not cover the state's H (%d cells)" % (
                    key, None if hrow is None else len(hrow), len(before[0])))
                hrow = hrow or []
            dh, ch = [h[0] for h in hrow], [h[1] for h in hrow]
            H1, k1, kl1, cl1, prog, lit = own_progress(before, op, d, c_, dh, ch, cell, fz)
            m.update(after=[H1, k1, kl1, cl1, before[4] + 1], evaluated=True, progressed=prog, dh=dh, ch=ch,
                     persist0=dict(before[5]))
            st["progress evaluations"] += 1
            if lit is not None and lit != prog:
                st["A2 literal reading differs"] += 1
        st["contests"] += 1
        st["contests, route closed"] += 0 if op else 1
        st["contests, latched incumbent"] += 1 if m["latched"] else 0
        model[key] = m
    for key, rs in prog_rec.items():
        m = model.get(key)
        if m is None:
            bad("Z-R1", "progress_step on %s, not a contest at this J point" % key)
            continue
        if not m["evaluated"]:
            bad("Z-R1", "progress_step on %s, a contest initialised here (no state at entry)" % key)
            continue
        if len(rs) != 1:
            bad("Z-R1", "%d progress_step calls on %s" % (len(rs), key))
        c = rs[0]
        want = {"open": m["open"], "d": m["d"], "c": m["c"], "d_hist": m["dh"], "c_hist": m["ch"], "cell": m["cell"],
                "frozen": m["frozen"]}
        for f, w in want.items():
            got = c.get(f)
            if f in ("d_hist", "c_hist", "cell"):
                got = list(got or [])
            if got != w:
                bad("Z-R1", "progress_step %s: %s passed %r != the instrument's %r" % (key, f, got, w))
        cb = list(c.get("before") or [])
        if len(cb) < 5 or _prow(cb[:5] + [{}])[:5] != m["before"][:5]:
            bad("Z-R1", "progress_step %s: the state passed %r is not the state held at J entry %r" % (
                key, cb[:5], m["before"][:5]))
        ca = list(c.get("after") or [])
        if len(ca) < 5 or _prow(ca[:5] + [{}])[:5] != m["after"]:
            bad("Z-R1", "progress_step %s: the verdict [H, k, k_L, closed, age] %r != the analyzer's %r" % (
                key, ca[:5], m["after"]))
    for key, m in model.items():
        if m["evaluated"] and key not in prog_rec:
            bad("Z-R1", "contest %s (a state at J entry) got no progress_step call" % key)
    # ---- 3 the spares and the persistence counters (J runs step 3 whenever a contest exists)
    spares = [u for u in free if u not in s2_u]
    step3 = bool(pairs)
    for key, m in model.items():
        m["spare_d"] = {b: dv(m["v"], b, 2) for b in spares}
        m["persist"] = own_persist(m["persist0"], m["spare_d"], m["delta"], M_) if step3 else dict(m["persist0"])
        rs = pers_rec.get(key) or []
        if step3 and len(rs) != 1:
            bad("Z-R1", "contest %s: %d update_persistence calls (1 expected)" % (key, len(rs)))
        for c in rs[:1]:
            sd = {str(u): x for u, x in (c.get("spare_d") or {}).items()}
            if sd != m["spare_d"]:
                bad("Z-R1", "update_persistence %s: spare d* passed %r != the instrument's %r" % (key, sd, m["spare_d"]))
            if c.get("delta") != m["delta"]:
                bad("Z-R1", "update_persistence %s: delta passed %r != the analyzer's %r (5.2: d* open, G closed)" % (
                    key, c.get("delta"), m["delta"]))
            if c.get("M") != M_:
                bad("Z-R1", "update_persistence %s: M %r != %r" % (key, c.get("M"), M_))
            if {str(u): int(n) for u, n in (c.get("before") or {}).items()} != m["persist0"]:
                bad("Z-R1", "update_persistence %s: the counts passed %r are not the state's %r" % (
                    key, c.get("before"), m["persist0"]))
            if {str(u): int(n) for u, n in (c.get("after") or {}).items()} != m["persist"]:
                bad("Z-R1", "update_persistence %s: counts %r != the analyzer's %r" % (key, c.get("after"),
                                                                                     m["persist"]))
    for key in pers_rec:
        if key not in model:
            bad("Z-R1", "update_persistence on %s, not a contest" % key)
    # ---- 2 / 4 THE FILLS (Z-C1a, and Z-R1 on the values passed)
    for c in by_fn["solve_fill"]:
        stage = c.get("stage")
        units = sorted({str(u) for u in c.get("units") or []}, key=id_index)
        victims = sorted({str(v) for v in c.get("victims") or []}, key=id_index)
        if stage == 2:
            want_u = sorted(set(free), key=id_index)
            want_v = sorted({str(v) for v in s.get("fill_victims") or []}, key=id_index)
            if units != want_u or victims != want_v:
                bad("Z-C1a", "the step-2 fill ran over units %s x victims %s, its candidate sets are %s x %s" % (
                    units, victims, want_u, want_v))
        elif stage == 4:
            olds = {str(o) for e in s3 for o in e.get("old_units") or []}
            olds_active = {str(o) for e in s3 if e.get("kind") == "replace" for o in e.get("released") or []}
            want_v = sorted({v for v in W if v not in s2_v}, key=id_index)
            if not (set(units) <= olds and olds_active <= set(units)) or victims != want_v:
                bad("Z-C1a", "the step-4 fill ran over units %s x victims %s; the released units are %s (active %s), "
                             "W not filled in step 2 %s" % (units, victims, sorted(olds), sorted(olds_active), want_v))
        else:
            bad("Z-C1a", "a fill record of stage %r" % (stage,))
            continue
        if c.get("capped"):
            bad("Z-C1a", "the fill was passed capped victims %s (none in round 2: a latched-held victim is a contest)"
                % c.get("capped"))
        dist = {(u, v): dv(v, u, 2) for u in units for v in victims}
        cl = {(u, v): clean(u, v) for u in units for v in victims}
        for u in units:
            for v in victims:
                k2 = pkey(u, v)
                if not jp_has(cur, v, u):
                    bad("Z-R1", "solve_fill %s: no instrument value" % k2)
                    continue
                if (c.get("d") or {}).get(k2) != dist[(u, v)]:
                    bad("Z-R1", "solve_fill %s: d* passed %r != the instrument's %r" % (k2, (c.get("d") or {}).get(k2),
                                                                                      dist[(u, v)]))
                if k2 not in (c.get("clean") or {}) or bool(c["clean"][k2]) != cl[(u, v)]:
                    bad("Z-R1", "solve_fill %s: clean passed %r != the instrument's %r" % (
                        k2, (c.get("clean") or {}).get(k2), cl[(u, v)]))
        ledger = {ukey(k): int(b) for k, b in (c.get("b") or {}).items()}
        mine = own_fill(units, victims, dist, cl, ledger)
        got = sorted([(str(p[0]), str(p[1])) for p in c.get("out") or []], key=lambda p: (id_index(p[0]),
                                                                                         id_index(p[1])))
        st["fills"] += 1
        if mine is None:
            bad("Z-C1a", "the fill has more than %d configurations (design 5.5: J must refuse it)" %
                FILL_MAX_CONFIGURATIONS)
        elif mine != got:
            bad("Z-C1a", "stage %s: J chose %s; the ledger-blind optimum (L1 served, L1b clean pairs, L2' total d*, L3' "
                         "worst d*; then L4' re-used, L5 ids) is %s" % (stage, got, mine))
        kinds = ("fill", "latch_fill") if stage == 2 else ("second_fill", "latch_fill")
        for e in (s2 if stage == 2 else s4):
            if e.get("kind") in kinds and (str(e.get("victim_id")), str(e.get("unit"))) not in set(got):
                bad("Z-C1a", "stage %s: applied bind %s -> %s was not chosen" % (stage, e.get("unit"),
                                                                              e.get("victim_id")))
        # 13 (9) STRUCTURE: a fill where a RE-USED pair is nearest (a C1 path) / a re-used pair chosen
        for v in victims:
            fin = [(dist[(u, v)], u) for u in units if dist[(u, v)] is not None]
            if fin:
                least = min(x for x, _ in fin)
                if any(x == least and int(ledger.get((u, v), 0) or 0) >= 1 for x, u in fin):
                    st["fills with a re-used pair nearest (C1 path)"] += 1
                    break
        st["re-used pairs chosen"] += sum(1 for p in c.get("out") or [] if p[3])
    # ---- 3 THE PLAN (Z-C1b, Z-C2, Z-R2; Z-R1 on its inputs)
    plans = by_fn["plan_replacements_detail"]
    want_plan = bool(spares) and bool(pairs)
    if len(plans) != (1 if want_plan else 0):
        bad("Z-R1", "%d plan_replacements_detail calls (%d expected: spares %d, contests %d)" % (
            len(plans), 1 if want_plan else 0, len(spares), len(pairs)))
    j_reps, j_barred = [], []
    if plans:
        c = plans[0]
        if sorted(str(u) for u in c.get("spares") or []) != sorted(spares):
            bad("Z-C1b", "the plan's spares %s are not the free units unbound by step 2 %s" % (c.get("spares"), spares))
        rows = {str(r[0]): r for r in c.get("contests") or []}
        for key, m in model.items():
            r = rows.get(m["v"])
            if r is None:
                bad("Z-R1", "contest %s missing from the plan" % key)
                continue
            got = [str(r[0]), str(r[1]), r[2], bool(r[3]), r[4], r[5], {str(u): int(n) for u, n in (r[6] or {}).items()},
                   bool(r[7])]
            want = [m["v"], m["a"], m["delta"], m["open"], m["after"][1], m["after"][2], m["persist"], m["latched"]]
            if got != want:
                bad("Z-R1", "plan contest %s: [victim, incumbent, delta, open, k, k_L, persist, latched] passed %r != "
                            "the analyzer's %r" % (key, got, want))
        for v in sorted(set(rows) - {m["v"] for m in model.values()}):
            bad("Z-R1", "the plan holds a contest on %s, not a contest at this J point" % v)
        for k2, x in (c.get("d") or {}).items():
            b, v = ukey(k2)
            if x != dv(v, b, 2) or bool((c.get("clean") or {}).get(k2)) != clean(b, v):
                bad("Z-R1", "plan %s: d* %r / clean %r passed != the instrument's %r / %r" % (
                    k2, x, (c.get("clean") or {}).get(k2), dv(v, b, 2), clean(b, v)))
        ledger3 = {ukey(k): int(b) for k, b in (c.get("b") or {}).items()}
        plan_c = [{"victim": m["v"], "incumbent": m["a"], "delta": m["delta"], "open": m["open"], "k": m["after"][1],
                   "k_closed": m["after"][2], "persist": m["persist"], "latched": m["latched"]} for m in model.values()]
        dist3 = {(b, m["v"]): dv(m["v"], b, 2) for b in spares for m in model.values()}
        clean3 = {(b, m["v"]): clean(b, m["v"]) for b in spares for m in model.values()}
        my_reps, my_barred = own_plan(plan_c, spares, dist3, clean3, ledger3, S_, P_)
        j_reps = [[str(r[0]), str(r[1]), str(r[2]), str(r[3]), r[4], bool(r[5])] for r in c.get("out") or []]
        j_barred = [[str(b[0]), str(b[1]), str(b[2]), b[3], [str(x) for x in b[4]]] for b in c.get("barred") or []]
        if sorted(j_reps) != sorted(my_reps):
            bad("Z-C1b", "J planned %s; the nearest-or-incumbent rule (4.3) gives %s" % (j_reps, my_reps))
        if sorted(j_barred) != sorted(my_barred):
            bad("Z-C1b", "J's nearest-barred records %s != the analyzer's %s" % (j_barred, my_barred))
        for v, old, new, cause, dist_, latched in j_reps:
            m = model.get(pkey(old, v))
            if not clean(new, v):
                bad("Z-R2", "challenger %s for %s had no clean approach at the replacement" % (new, v))
            if m is None:
                bad("Z-C2", "replacement on %s: %s is not its contest incumbent" % (v, old))
                continue
            dn = dv(v, new, 2)
            count = m["after"][1] if m["open"] else m["after"][2]
            if dn is None or dn != dist_:
                bad("Z-C2", "replacement %s -> %s on %s: distance %r != the instrument's d* %r" % (old, new, v, dist_,
                                                                                                  dn))
            if bool(latched) != m["latched"]:
                bad("Z-C2", "replacement on %s: latched %r but the incumbent's label says %r" % (v, latched,
                                                                                               m["latched"]))
            if cause == "stall":
                ok = count >= int(S_) and dn is not None and dn < m["delta"] + count
            elif cause == "margin":
                pc = int(m["persist"].get(new, 0) or 0)
                ok = count < int(S_) and pc >= int(P_) and dn is not None and dn + int(M_) <= m["delta"]
            else:
                ok = False
            if not ok:
                bad("Z-C2", "%s replacement %s -> %s on %s fails its rule: route %s, delta %s (%s), count %s (%s), d*(B) "
                            "%s, persistence %s; S %s M %s P %s" % (
                                str(cause).upper(), old, new, v, "open" if m["open"] else "closed", m["delta"],
                                "d*" if m["open"] else "G", count, "k" if m["open"] else "k_L", dn,
                                m["persist"].get(new), S_, M_, P_))
            st["replacements planned, " + str(cause)] += 1
            if cause == "margin" and (m["unclean"] or bool((ucell.get(new) or [None, None, False])[2])):
                st["margin decisions with a unit on an unclean cell"] += 1
        if j_barred:
            st["nearest-barred frames"] += 1
    planned = {(r[0], r[2], r[1]) for r in j_reps}
    for e in s3:
        olds = [str(o) for o in e.get("old_units") or []]
        if not clean(str(e.get("unit")), str(e.get("victim_id"))):
            bad("Z-R2", "applied %s %s -> %s: no clean approach" % (e.get("kind"), olds, e.get("unit")))
        if len(olds) != 1 or (str(e.get("victim_id")), str(e.get("unit")), olds[0]) not in planned:
            bad("Z-C1b", "applied %s on %s (%s -> %s) was not planned" % (e.get("kind"), e.get("victim_id"), olds,
                                                                          e.get("unit")))
    aborted = {(str(e.get("victim_id")), str(e.get("unit"))) for e in ev
               if str(e.get("kind") or "").endswith("_aborted")}
    done = {(str(e.get("victim_id")), str(e.get("unit"))) for e in s3}
    for v, new, old in sorted(planned):
        if (v, new) not in done and (v, new) not in aborted:
            bad("Z-C3", "planned replacement %s -> %s on %s neither applied nor aborted" % (old, new, v))
    nb_ev = sorted([str(e.get("victim_id")), str(e.get("unit")), sorted(str(x) for x in e.get("barred") or [])]
                   for e in ev if e.get("kind") == "nearest_barred")
    nb_rec = sorted([b[0], b[1], sorted(b[4])] for b in j_barred)
    if nb_ev != nb_rec:
        bad("Z-C1b", "nearest-barred events %s != J's planned barred records %s" % (nb_ev, nb_rec))
    # ---- the state J keeps at exit (Z-R1)
    prog_exit = {k: _prow(v) for k, v in (cur.get("progress") or {}).items()}
    replaced_v = {str(e.get("victim_id")) for e in s3}
    for key, m in model.items():
        if m["v"] in replaced_v:
            if key in prog_exit:
                bad("Z-R1", "the replaced contest %s still holds a state at J exit" % key)
            continue
        want = list(m["after"]) + [m["persist"]]
        if prog_exit.get(key) != want:
            bad("Z-R1", "the state J kept for %s, %r, != the analyzer's verdict %r" % (key, prog_exit.get(key), want))
    for e in applied:
        u, v = str(e.get("unit")), str(e.get("victim_id"))
        uc = ucell.get(u)
        want = None if uc is None else [[[int(uc[0]), int(uc[1])]], 0, 0, False, 0, {}]
        if want is None or prog_exit.get(pkey(u, v)) != want:
            bad("Z-R1", "J's bind %s -> %s: the state at exit %r != the bind state %r" % (u, v, prog_exit.get(pkey(u, v)),
                                                                                       want))
    # ---- I4-W at the end of the J call
    w_end = [v for v in W if v not in {str(e.get("victim_id")) for e in s2 + s4}]
    bound_u = {str(e.get("unit")) for e in applied}
    s4rec = [c for c in by_fn["solve_fill"] if c.get("stage") == 4]
    released_free = ({str(u) for c in s4rec for u in c.get("units") or []} if s4rec else
                     {str(o) for e in s3 if e.get("kind") == "replace" for o in e.get("released") or []})
    free_end = sorted(({u for u in free if u not in bound_u} | released_free) - bound_u, key=id_index)
    for u in free_end:
        for v in w_end:
            if dv(v, u, 0) is not None:
                bad("I4-W", "end of the J call: free %s and waiting %s form an allowed pair with a finite route (d %s)" %
                    (u, v, dv(v, u, 0)))
    return Z, st


def chain_zeros(jdl):
    """NEW (Z-R1, run level): the state J reads at a J point is the state it left - every binding in a j_detail entry's
    progress_before equals its state in the previous entry's progress (J's exit state; between two PRE J points the
    model only removes states: J-post's prune and the sink's pop at a bind); the first entry's progress_before is
    empty (only J creates states). Returns [[step, phase, text]]."""
    bad = []
    prev = None
    for row in jdl or ():
        step, phase, cur = row[0], row[1], row[2]
        pb = {k: _prow(v) for k, v in (cur.get("progress_before") or {}).items()}
        if prev is None:
            if pb:
                bad.append([step, phase, "the first PRE J point holds %d states before any J bind" % len(pb)])
        else:
            for k, v in sorted(pb.items()):
                if k not in prev:
                    bad.append([step, phase, "state %s at entry was not left by the previous J point" % k])
                elif prev[k] != v:
                    bad.append([step, phase, "state %s at entry %r != the state the previous J point left %r" % (
                        k, v, prev[k])])
        prev = {k: _prow(v) for k, v in (cur.get("progress") or {}).items()}
    return bad


def i4w_sample(rows):
    """NEW (I4-W at the sample instant = D1's W part, 10.6): every sample victim-step of W (no living binder, not in
    custody) with a FREE unit holding a finite route (the sample is taken right after J-post). Returns [[step, 'sample',
    victim, [units]]]."""
    res = []
    for row in rows or ():
        step, W = row[0], row[1]
        units = row[5]
        for v in W:
            reach = [u[0] for u in units if u[2] and any(x == v and dd is not None for x, dd in u[6])]
            if reach:
                res.append([step, "sample", v, reach])
    return res


def gb_c_check(j_events, binders, cmds, ff_dead, rows_vic):
    """PORTED (round 1's digest, its rule unchanged; outputs/_dp_analyze.py at cc8d653c): G-B(c) I3, dispatch
    abandonment - a replace / latch_fill event whose victim has no binder at the same step's binders sample (after
    J-post); a J-pre event is excused only by an outside event in between (o1: an unassign of the pair with a
    'replacement ... blocked' reason; o3: the unit's death at that step) or a terminal victim. Returns (instances,
    excused, no-sample)."""
    bsteps = {int(step): {vid: bl for vid, bl in lst} for step, lst in binders or ()}
    vic_rows = {t + 1: {r[0]: r for r in row} for t, row in enumerate(rows_vic or ())}
    inst_, exc, nos = [], [], []
    for e in j_events or ():
        if e.get("kind") not in ("replace", "latch_fill"):
            continue
        step, vid, uid = e.get("step"), e.get("victim_id"), e.get("unit")
        sample = bsteps.get(step)
        if sample is None:
            nos.append([step, e.get("phase"), vid, uid])
            continue
        if vid in sample:
            continue
        excused = ""
        if e.get("phase") == "pre":
            if any(c[0] == step and c[2] == "unassign" and c[6] and c[3] == vid and c[4] == uid
                   and "replacement" in str(c[5]) and "blocked" in str(c[5]) for c in cmds or ()):
                excused = "o1"
            elif ff_dead.get(uid) == step:
                excused = "o3"
            elif str((vic_rows.get(step, {}).get(vid) or [None] * 5)[4]) in TERMINAL:
                excused = "victim terminal"
        if excused:
            exc.append([step, e.get("phase"), e.get("kind"), vid, uid, excused])
        else:
            inst_.append([step, e.get("phase"), e.get("kind"), vid, uid, e.get("old_units")])
    return inst_, exc, nos


def zc3_run(cmds, releases, j_events, j_calls, reassign_on):
    """NEW (Z-C3, 6.5; run level) - a CODE-STRUCTURE regression check: every J command is the assign of a FILL /
    REPLACE / LATCH-FILL / second fill, or the release inside an atomic replacement. J's commands are those with a J
    reason (J_REASONS); at every J point (dp.j_calls) the successful J assigns are exactly the applied bind events, the
    successful J unassigns exactly the units the applied replacements released (each after its replacement's assign:
    bind first, then release), a failed J assign is matched by a refused / aborted event; no J command or event outside
    a J point; only J's event kinds and stages (fill 2, second_fill 4, replace / latch_fill / nearest_barred 3 under
    Limit 3); every single-unit release (only_ff_id) is a J replacement's. Returns [[step, phase, text]]."""
    bad = []
    jpts = {(int(c[0]), str(c[1])) for c in j_calls or ()}
    stage_of = {"fill": (2,), "second_fill": (4,), "replace": (3,), "latch_fill": (3,) if reassign_on else (2, 4),
                "nearest_barred": (3,), "fill_refused": (2,), "second_fill_refused": (4,), "replace_aborted": (3,),
                "latch_fill_aborted": (3,) if reassign_on else (2, 4)}
    ev_at = collections.defaultdict(list)
    for e in j_events or ():
        pt = (int(e.get("step") or -1), str(e.get("phase")))
        k = e.get("kind")
        if k not in J_EVENT_KINDS:
            bad.append([pt[0], pt[1], "a J event of unknown kind %r" % k])
        elif e.get("stage") not in stage_of[k]:
            bad.append([pt[0], pt[1], "a %s event at stage %r" % (k, e.get("stage"))])
        if pt not in jpts:
            bad.append([pt[0], pt[1], "a J event (%s) outside a J point" % k])
        ev_at[pt].append(e)
    cm_at = collections.defaultdict(list)
    for i, c in enumerate(cmds or ()):
        reason = str(c[5] or "")
        if reason not in J_REASONS:
            continue
        pt = (int(c[0]), str(c[1]))
        if c[2] not in ("assign", "unassign"):
            bad.append([pt[0], pt[1], "a J command of action %r" % c[2]])
        if c[2] == "unassign" and reason in FILL_REASONS:
            bad.append([pt[0], pt[1], "an unassign with a fill reason %r" % reason])
        if pt not in jpts:
            bad.append([pt[0], pt[1], "a J command (%s %s %s) outside a J point" % (c[2], c[3], c[4])])
        cm_at[pt].append((i, c))
    for pt in sorted(set(ev_at) | set(cm_at)):
        es, cs = ev_at.get(pt, []), cm_at.get(pt, [])
        want_a = collections.Counter((str(e.get("victim_id")), str(e.get("unit"))) for e in es
                                     if e.get("kind") in J_BIND_KINDS)
        got_a = collections.Counter((str(c[3]), str(c[4])) for _i, c in cs if c[2] == "assign" and c[6])
        if want_a != got_a:
            bad.append([pt[0], pt[1], "successful J assigns %s != the applied bind events %s" % (dict(got_a),
                                                                                               dict(want_a))])
        failed = {(str(e.get("victim_id")), str(e.get("unit"))) for e in es
                  if str(e.get("kind") or "").endswith(("_refused", "_aborted"))}
        for _i, c in cs:
            if c[2] == "assign" and not c[6] and (str(c[3]), str(c[4])) not in failed:
                bad.append([pt[0], pt[1], "a failed J assign %s -> %s without a refused / aborted event" % (c[4], c[3])])
        want_u = collections.Counter((str(e.get("victim_id")), str(o)) for e in es
                                     if e.get("kind") in ("replace", "latch_fill") for o in e.get("released") or [])
        got_u = collections.Counter((str(c[3]), str(c[4])) for _i, c in cs if c[2] == "unassign" and c[6])
        if want_u != got_u:
            bad.append([pt[0], pt[1], "successful J unassigns %s != the units the replacements released %s" % (
                dict(got_u), dict(want_u))])
        for i, c in cs:
            if c[2] == "unassign" and c[6]:
                if not any(j < i and c2[2] == "assign" and c2[6] and c2[3] == c[3] for j, c2 in cs):
                    bad.append([pt[0], pt[1], "release of %s from %s before its replacement's bind" % (c[4], c[3])])
    for r in releases or ():
        step, phase, vid, _keep, reason, only = r[0], r[1], r[2], r[3], r[4], r[5]
        if not only:
            if str(reason) in J_REASONS:
                bad.append([step, phase, "a J-reason release of %s that is not a single-unit release" % vid])
            continue
        es = ev_at.get((int(step), str(phase)), [])
        if not any(e.get("kind") in ("replace", "latch_fill") and str(e.get("victim_id")) == str(vid)
                   and str(only) in [str(o) for o in e.get("old_units") or []] for e in es) \
                or str(reason) not in REPLACE_REASONS + (LATCH_REASON,):
            bad.append([step, phase, "a single-unit release of %s from %s (%s) outside an atomic replacement" % (
                only, vid, reason)])
    return bad


def dispatch_zeros(dp, sample_rows, rows_vic, ff_dead, ff_rb, reassign_on):
    """NEW (10.3): every dispatch-owned zero of one run (computed in every arm; only dq1's gate - section 3 owners):
    G-B(a) / I7 and G-B(b) (gb_counts, dp.binders), G-B(c) (gb_c_check), I4-W (every J point's end, and the sample),
    G-T(a) (round 1's reading: gt_returns with no outside event), G-T(c) (ledger_check), M6 (a successful assign the
    instrument's BFS found closed), Z-C1a / Z-C1b / Z-C2 / Z-R1 / Z-R2 (jpoint_zeros, chain_zeros), Z-C3 (zc3_run).
    Returns (Z {zero: instances}, stats Counter, extras)."""
    Z = collections.defaultdict(list)
    st = collections.Counter()
    cmds = dp.get("commands") or []
    binders = dp.get("binders") or []
    events = list(dp.get("j_events") or [])
    _n, gbl = gb_counts(binders, dp.get("invariant"))
    Z["G-B(a)/I7"] = list(gbl.get("gb_a") or [])
    Z["G-B(b)"] = list(gbl.get("gb_b") or [])
    Z["G-B(c)"], exc, nos = gb_c_check(events, binders, cmds, ff_dead, rows_vic)
    rets = gt_returns(cmds, binders, ff_dead, ff_rb)
    Z["G-T(a)"] = [[r["step"], r["phase"], r["victim"], r["unit"], r["X"], r["kind"]] for r in rets if not r["outside"]]
    viol, _reused, _b = ledger_check(cmds)
    Z["G-T(c)"] = viol
    Z["M6"] = [[c[0], c[1], c[3], c[4], c[5]] for c in cmds if c[2] == "assign" and c[6] and len(c) > 7 and c[7] is False]
    Z["I4-W"] = i4w_sample(sample_rows)
    Z["Z-C3"] = zc3_run(cmds, dp.get("releases"), events, dp.get("j_calls"), reassign_on)
    ev_at = collections.defaultdict(list)
    for e in events:
        ev_at[(e.get("step"), str(e.get("phase")))].append(e)
    jdl = dp.get("j_detail") or []
    jp_pts = set()
    for row in jdl:
        step, phase, cur = row[0], str(row[1]), row[2]
        jp_pts.add((step, phase))
        jz, jst = jpoint_zeros(cur, step, phase, ev_at.get((step, phase), []))
        for k, v in jz.items():
            Z[k] += v
        st.update(jst)
    for (step, phase), es in sorted(ev_at.items(), key=lambda kv: phase_key(*kv[0])):
        if any(e.get("kind") in J_BIND_KINDS for e in es) and (step, phase) not in jp_pts:
            Z["Z-C3"].append([step, phase, "J bound at a J point with no recorded PRE (j_detail)"])
    Z["Z-R1"] += chain_zeros(jdl)
    st["J points with PRE"] = len(jdl)
    return Z, st, {"gb_c_excused": exc, "gb_c_nosample": nos}


# ================================================================================================ D1-D4 (10.6; pure)
def nearest_barred_at(j_events):
    """NEW: {(step, victim): cause} of the nearest_barred events at J-post (the J point right before the sample)."""
    return {(int(e.get("step")), str(e.get("victim_id"))): str(e.get("reason") or "").replace("nearest_barred_", "")
            for e in j_events or () if e.get("kind") == "nearest_barred" and str(e.get("phase")) == "post"}


def d_counts(rows, nb=None, binders=None):
    """NEW (10.6) - D1 and D3 on the ARM-INDEPENDENT per-step sample (d['dq']['sample'] rows [step, W, WL, custody,
    active, units]; unit rows [unit, status, free, bound, cell, moved, routes [[victim, d | None] over W + WL], log
    [[action, wrote]]]). nb = nearest_barred_at(...) (dq1; empty elsewhere); binders = dp.binders (the same instant).
    D1 ABANDONED WAITING: a victim-step of W or W_L with some FREE unit holding a finite route; split W / nearest-barred
    (W_L whose contest J nearest-barred at that step's J-post) / latch-held (W_L, one binder) / other (W_L with two or
    more binders). D3 IDLE-UNREACHABLE: a unit-step of an UNBOUND sampled unit (any status label) with no finite route to
    any W / W_L victim while one exists, that did no work in the advance just sampled: moved False (None, the unit's
    first sample, does not count) and no extinguish / clear row with wrote True. Also: the action-blind count (D3
    without the work condition), the firefighting action split of unbound units while victims wait, D1's victim spells.
    Returns (num Counter, lists)."""
    num, lists = collections.Counter(), collections.defaultdict(list)
    nb = nb or {}
    nbind = {int(step): {vid: len(bl) for vid, bl in lst} for step, lst in binders or ()}
    d1_steps = collections.defaultdict(list)
    for row in rows or ():
        step, W, WL, units = row[0], list(row[1]), list(row[2]), row[5]
        targets = W + WL
        reach = collections.defaultdict(list)
        for u in units:
            if u[2]:
                for v, dd in u[6]:
                    if dd is not None:
                        reach[v].append(u[0])
        for v in W:
            if reach.get(v):
                num["d1_abandoned"] += 1
                num["d1_W"] += 1
                lists["d1"].append([step, v, "W", reach[v]])
                d1_steps[v].append(step)
        for v in WL:
            if reach.get(v):
                if (int(step), v) in nb:
                    cat = "nearest-barred"
                elif nbind.get(int(step), {}).get(v, 1) <= 1:
                    cat = "latch-held"
                else:
                    cat = "other"
                num["d1_abandoned"] += 1
                num["d1_" + cat] += 1
                lists["d1"].append([step, v, cat, reach[v]])
                d1_steps[v].append(step)
        if not targets:
            continue
        for u in units:
            if u[3]:
                continue
            if any(dd is not None for _v, dd in u[6]):
                continue
            num["d3_blind"] += 1
            work = any(a in FF_WORK_ACTIONS and w for a, w in u[7])
            if u[5] is False and not work:
                num["d3_idle_unreachable"] += 1
                num["d3_status_" + str(u[1])] += 1
                lists["d3"].append([step, u[0], u[1]])
        for u in units:
            if u[3]:
                continue
            num["wait_unbound_unit_steps"] += 1
            if not u[7]:
                num["wait_action_none_logged"] += 1
            for a, w in u[7]:
                num["wait_action_%s%s" % (a, "_wrote" if w else "")] += 1
    lists["d1_spells"] = [[v, sp[0], sp[1], sp[2]] for v, ss in sorted(d1_steps.items()) for sp in spells(ss)]
    return num, lists


def d4_route_blocked_end(d):
    """NEW (10.6 D4; round 1's G-L read from the label): the units whose rows_ff status is route_blocked at their last
    recorded step (_ut_analyze2.ff_status_track), bound or not; returns (units, bound units)."""
    latched = sorted(U2.ff_status_track(d)[2])
    last = {}
    for row in d.get("rows_ff") or ():
        for r in row:
            last[r[0]] = r
    bound = sorted(u for u in latched if last.get(u) is not None and last[u][8])
    return latched, bound


# ================================================================================================ J measures (10.9; pure)
def j_measures(dp, terminal):
    """NEW (10.9; reported, never gating; round 1's M4 measures ported to the corrected J): replacements by kind and
    cause (a LATCH-FILL's cause from the plan record that chose it), fills and second fills, refusals / aborts;
    nearest-barred victim-steps (J-post events) with their spells and whether the run finished; fills differing from the
    legacy counterfactual (round 1's cf_diff on dp.j_calls); re-used-pair binds (ledger_check); the ACTED footprint per
    variant (J points where reverting that one change alone changes J's decision) and base != actual. Returns (num,
    lists)."""
    num, lists = collections.Counter(), collections.defaultdict(list)
    plan_cause = {}
    for row in dp.get("j_detail") or ():
        step, phase, cur = row[0], str(row[1]), row[2]
        for c in cur.get("calls") or []:
            if c.get("fn") == "plan_replacements_detail":
                for r in c.get("out") or []:
                    plan_cause[(step, phase, str(r[0]), str(r[2]))] = str(r[3])
        fp = cur.get("fp") or {}
        for name in fp.get("acted") or []:
            num["fp_acted_" + str(name)] += 1
            lists["fp_acted_" + str(name)].append([step, phase])
        if fp.get("base_eq_actual") is False:
            num["fp_base_ne_actual"] += 1
    nb = collections.defaultdict(list)
    for e in dp.get("j_events") or ():
        k = str(e.get("kind") or "")
        step, phase, v, u = e.get("step"), str(e.get("phase")), str(e.get("victim_id")), str(e.get("unit"))
        if k == "replace":
            cause = str(e.get("reason") or "").replace("reassign_", "")
            num["replace_" + cause] += 1
            lists["replacements"].append([step, phase, "REPLACE", cause, v, e.get("old_units"), u, e.get("distance")])
        elif k == "latch_fill":
            cause = plan_cause.get((step, phase, v, u), "?")
            num["latch_fill_" + cause] += 1
            lists["replacements"].append([step, phase, "LATCH-FILL", cause, v, e.get("old_units"), u,
                                          e.get("distance")])
        elif k in ("fill", "second_fill"):
            num[k] += 1
        elif k == "nearest_barred":
            num["nearest_barred_" + str(e.get("reason") or "").replace("nearest_barred_", "")] += 1
            if phase == "post":
                nb[v].append(int(step))
        elif k.endswith("_refused"):
            num["refused"] += 1
        elif k.endswith("_aborted"):
            num["aborted"] += 1
    num["nearest_barred_victim_steps"] = sum(len(set(s)) for s in nb.values())
    lists["nb_spells"] = [[v, sp[0], sp[1], sp[2], terminal is not None] for v, ss in sorted(nb.items())
                          for sp in spells(ss)]
    for c in dp.get("j_calls") or ():
        if len(c) > 4 and isinstance(c[4], dict):
            num["cf_points"] += 1
            leg = sorted(tuple(x) for x in c[4].get("legacy") or [])
            jf = sorted(tuple(x) for x in c[4].get("j_fills") or [])
            if leg != jf:
                num["cf_diff"] += 1
                lists["cf_diff"].append([c[0], c[1], leg, jf])
    _viol, reused, _b = ledger_check(dp.get("commands") or [])
    num["reused_binds"] = len(reused)
    lists["reused"] = reused
    return num, lists


def latch_spells(binders, ff_dead, vdead, resc):
    """NEW (10.9; reported): every latch episode (latch_episodes' rule: a pair (unit, victim) route_blocked in
    consecutive dp.binders samples) with its length in samples and its ENDING at the first sample without it:
    'recovered' (the unit still bound to her, active), 'replaced' (she is bound to another unit), 'unit died', 'victim
    terminal' (dead or rescued by then), 'released' (otherwise), or 'run end'. Rows [start, unit, victim, samples,
    ending]."""
    open_, res = {}, []
    for step, lst in binders or ():
        cur = {(uid, vid) for vid, bl in lst for uid, st in bl if str(st).lower() == "route_blocked"}
        sample = {vid: {uid for uid, _st in bl} for vid, bl in lst}
        for p in list(open_):
            if p in cur:
                open_[p][1] += 1
                continue
            uid, vid = p
            bl = sample.get(vid, set())
            if uid in bl:
                end = "recovered"
            elif bl:
                end = "replaced"
            elif ff_dead.get(uid) is not None and ff_dead[uid] <= step:
                end = "unit died"
            elif min(vdead.get(vid) or 10 ** 9, resc.get(vid) or 10 ** 9) <= step:
                end = "victim terminal"
            else:
                end = "released"
            res.append([open_[p][0], uid, vid, open_[p][1], end])
            del open_[p]
        for p in sorted(cur - set(open_)):
            open_[p] = [step, 1]
    for p, (s0, n) in sorted(open_.items()):
        res.append([s0, p[0], p[1], n, "run end"])
    return sorted(res)


# ================================================================================================ W3 material (pure)
KO_KINDS = ("drop_bind", "drop_release", "drop_challenger", "drop_victim", "drop_unreleased", "ko_today")


def j_decision_points(dp):
    """NEW (11.2): dq1's RECORDED J decisions per J point, in J-point order (pre before post): [[step, phase, legacy,
    s2, s3, s4]] - legacy = the recorded counterfactual (dp.j_calls' 'legacy', [[victim, unit]]: 11.2's legacy_pairs on
    J's own snapshot); s2 / s4 = J's stage-2 fill / stage-4 second-fill attempts [[victim, unit, ok]] (ok False =
    refused); s3 = J's stage-3 replacements [[kind, victim, new, [olds], ok]] (ok False = aborted), from dp.j_events (a
    nearest_barred record carries no bind)."""
    by = {}

    def slot(step, phase):
        return by.setdefault((int(step), str(phase)), {"legacy": [], "s2": [], "s3": [], "s4": []})

    for c in dp.get("j_calls") or ():
        if len(c) > 4 and isinstance(c[4], dict) and c[4].get("legacy"):
            slot(c[0], c[1])["legacy"] = [[str(v), str(u)] for v, u in c[4]["legacy"]]
    for e in dp.get("j_events") or ():
        kind = str(e.get("kind") or "")
        if kind == "nearest_barred":
            continue
        ok = not kind.endswith(("_refused", "_aborted"))
        base = kind.rsplit("_", 1)[0] if not ok else kind
        v, u, stage = str(e.get("victim_id")), str(e.get("unit")), e.get("stage")
        s = slot(e.get("step"), e.get("phase"))
        if stage == 3:
            s["s3"].append([base, v, u, [str(o) for o in e.get("old_units") or []], ok])
        elif stage == 2:
            s["s2"].append([v, u, ok])
        elif stage == 4:
            s["s4"].append([v, u, ok])
    return [[s, p, by[(s, p)]["legacy"], by[(s, p)]["s2"], by[(s, p)]["s3"], by[(s, p)]["s4"]]
            for s, p in sorted(by, key=lambda k: phase_key(*k))]


def change_key_order(key):
    """NEW: the canonical order of change keys [step, phase, unit, victim, kind] (step, J-pre before J-post, unit,
    victim, then KO_KINDS' order)."""
    return (int(key[0]), PHASE_RANK.get(str(key[1]), 9), id_index(key[2]), id_index(key[3]),
            KO_KINDS.index(key[4]) if key[4] in KO_KINDS else 99)


def override_changes(step, phase, legacy, s2, s3, s4, K):
    """NEW - 11.2's OVERRIDE on one J point's RECORDED decisions, the analyzer's own reading (K = the knocked-out
    units): the counterfactual's pairs with a unit of K are bound 'ko_today' before J's binds, except a pair equal to
    one of J's own stage-2 fill decisions (J's choice: unchanged); their victims are the KO victims. J's stage-2 bind
    of a unit of K -> drop_bind (1), else of a KO victim -> drop_victim (3); a stage-3 replacement whose challenger is
    in K -> drop_challenger (2), else whose released unit is in K -> drop_release (1), else on a KO victim ->
    drop_victim (3) - a dropped replacement's incumbent is not released; a stage-4 bind of a unit of K -> drop_bind, of
    a KO victim -> drop_victim, of a dropped replacement's incumbent -> drop_unreleased; every other decision unchanged
    (4). Returns the change keys [step, phase, unit, victim, kind] in change_key_order."""
    K = {str(u) for u in K}
    ko = [(str(v), str(u)) for v, u in legacy if str(u) in K]
    s2pairs = {(str(r[0]), str(r[1])) for r in s2}
    same = {p for p in ko if p in s2pairs}
    today = [p for p in ko if p not in same]
    ko_v = {v for v, _u in today}
    res = []
    for r in s2:
        v, u = str(r[0]), str(r[1])
        if (v, u) in same:
            continue
        if u in K:
            res.append([step, phase, u, v, "drop_bind"])
        elif v in ko_v:
            res.append([step, phase, u, v, "drop_victim"])
    unreleased = set()
    for r in s3:
        v, new, olds = str(r[1]), str(r[2]), [str(o) for o in r[3]]
        hit = None
        if new in K:
            hit = [step, phase, new, v, "drop_challenger"]
        elif any(o in K for o in olds):
            hit = [step, phase, next(o for o in olds if o in K), v, "drop_release"]
        elif v in ko_v:
            hit = [step, phase, new, v, "drop_victim"]
        if hit:
            res.append(hit)
            unreleased |= set(olds)
    for r in s4:
        v, u = str(r[0]), str(r[1])
        if u in K:
            res.append([step, phase, u, v, "drop_bind"])
        elif v in ko_v:
            res.append([step, phase, u, v, "drop_victim"])
        elif u in unreleased:
            res.append([step, phase, u, v, "drop_unreleased"])
    res += [[step, phase, u, v, "ko_today"] for v, u in today]
    return sorted(res, key=change_key_order)


def rule_k(rules, step, phase, units):
    """NEW (11.2): K at the J point - the union of the units the ACTIVE rules name (rule {'unit': U | '*' | '!U',
    'from', 'to', 'phase'?} active when from <= step <= to and its phase, if given, matches)."""
    K = set()
    for r in rules or ():
        if not int(r.get("from", 0)) <= int(step) <= int(r.get("to", 10 ** 9)):
            continue
        if "phase" in r and r["phase"] != phase:
            continue
        uu = str(r.get("unit", "*"))
        K |= set(units) if uu == "*" else (set(units) - {uu[1:]}) if uu.startswith("!") else {uu}
    return K


def ko_first(jpoints, rules, units):
    """CHANGED (11.2; the movement round's ko_first for dispatch knockouts): the first of dq1's J decisions a knockout
    with these rules CHANGES - the first override_changes key over the recorded J points, as [step, phase, unit,
    victim, kind] - or None (an EMPTY decision set). The replay equals dq1 before it, so it must be in the replay's
    ko_applied (the KO-evidence check)."""
    for step, phase, legacy, s2, s3, s4 in jpoints or ():
        K = rule_k(rules, step, phase, units)
        if K:
            ch = override_changes(step, phase, legacy, s2, s3, s4, K)
            if ch:
                return ch[0]
    return None


def r0_reproduces(x, r0, x_stdout, r0_stdout):
    """CHANGED (11.2: 'every per-step row, the commands, the J events, the movement events, eval and stdout'): R0 must
    reproduce dq1's record exactly. Returns the differing fields ([] = reproduces)."""
    diff = [k for k in ROW_KINDS if x.get(k) != r0.get(k)]
    if (x.get("dp") or {}).get("commands") != (r0.get("dp") or {}).get("commands"):
        diff.append("dp.commands")
    if (x.get("dp") or {}).get("j_events") != (r0.get("dp") or {}).get("j_events"):
        diff.append("dp.j_events")
    if x.get("mv_events") != r0.get("mv_events"):
        diff.append("mv_events")
    if x.get("eval") != r0.get("eval"):
        diff.append("eval")
    if x_stdout is None or x_stdout != r0_stdout:
        diff.append("stdout")
    return diff


# ================================================================================================ digest
def sample_rows_of(d):
    """NEW: d['dq']['sample'] rows ([] when absent)."""
    dq = d.get("dq") if isinstance(d.get("dq"), dict) else {}
    return list((dq.get("sample") or {}).get("rows") or [])


def digest(d, arm, label, path, cell_set=None, censor=H + 1):
    """CHANGED (the movement round's digest for three arms that all run the shipped guarded movement, plus round 1's J
    measures and the round's dispatch zeros and D1-D4): everything later sections read from one probe run, computed once
    (the run dict is dropped afterwards). censor: M1c's censoring step (361 = H + 1; in smoke mode the run's own last
    step + 1)."""
    g = {"arm": arm, "label": label, "path": path, "set": cell_set, "dp_only": bool(d.get("dp_only")),
         "crashed": d.get("crashed"), "censor": censor, "horizon": censor - 1}
    dp = d.get("dp") if isinstance(d.get("dp"), dict) else {}
    ud = d.get("ud") if isinstance(d.get("ud"), dict) else {}
    mvg = d.get("mvg") if isinstance(d.get("mvg"), dict) else {}
    dq = d.get("dq") if isinstance(d.get("dq"), dict) else {}
    sw = mvg.get("switches") or {}
    g["sw"] = {"a": bool(sw.get("FF_APPROACH_PATH")), "b": bool(sw.get("FF_RETREAT_KEEP_APPROACH")),
               "g": bool(sw.get("FF_FIX_STRANDING_GUARD"))}
    dsw = dp.get("switches") or {}          # round 1's live = dp.switches.joint_on (prov_run checks dq's agree)
    g["joint_on"], g["reassign_on"] = bool(dsw.get("joint_on")), bool(dsw.get("reassign_on"))
    g["wall_s"] = float(d.get("wall_s") or 0.0)
    tm = dp.get("timing") or {}
    g["j_ms_total"] = float(tm.get("j_ms_total") or 0.0)
    g["j_ms_raw_total"] = float(tm.get("j_ms_raw_total") or 0.0)
    g["j_net_ms"] = [float(r[3]) for r in dp.get("j_timing") or [] if len(r) > 3]
    g["dq_timing"] = dict(dq.get("timing") or {})
    g["guard_ms"] = [float(x) for x in (mvg.get("timing") or {}).get("guard_ms") or []]
    g["probe_frac"] = (ud.get("timing") or {}).get("probe_frac_of_wall")
    g["u1_shadow_error"] = mvg.get("u1_shadow_error")
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
    g["living_unit_steps"] = sum(1 for row in rows_ff for r in row if not r[6] and r[1] is not None)
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
    # ---- F4 searcher (G-OS + I2 / I6, searcher role)
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
    # ---- F5 firefighter (G-OF + I2 + the 7 leg kinds)
    by_step = [{r[0]: r for r in row} for row in rows_ff]
    for fid, s0, s1, n in A.ff_episodes(d):
        stc = collections.Counter(ff_state(by_step[s - 1][fid]) for s in range(s0, s1 + 1) if fid in by_step[s - 1])
        num["of_broad"] += 1
        lists["of_broad"].append([fid, s0, s1, n, stc.most_common(1)[0][0] if stc else "?"])
    i2 = {}
    for short, key in I2_KINDS:
        eps = sd_out.get(key) or []
        i2[short] = [e[:3] for e in eps]
        num["of_" + short] = len(eps)
        lists["of_" + short] = [e[:3] for e in eps]
    _cols, mv_rows = mv_dicts(d)
    eps, g["n_excluded_carry"] = stuck_carry_excluded(label, d, mv_rows)
    if eps is not None:
        num["of_stuck_carry"] = len(eps)
        lists["of_stuck_carry"] = [e[:3] for e in eps]
    legs_ev = []
    for leg in mv_legs(mv_rows):
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
    binders = dp.get("binders") or []
    lat = latch_episodes(binders)
    num["latch_episodes"] = len(lat)
    lists["latch_episodes"] = lat
    cmds = dp.get("commands") or []
    won, wol = writeoff_counts(cmds, g["det"])
    num.update(won)
    lists.update(wol)
    # ---- 10.4's latency decomposition (detection -> first assign -> pickup -> rescue; round 1's M5 material)
    first_assign, pick, prev_exit = {}, {}, {}
    for c in cmds:
        if c[2] == "assign" and c[6] and c[3] not in first_assign:
            first_assign[c[3]] = c[0]
    for t, row in enumerate(rows_ff):
        for r in row:
            if r[5] and not prev_exit.get(r[0]) and r[8] and r[8] not in pick:
                pick[r[8]] = t + 1
            prev_exit[r[0]] = r[5]
    g["lat"] = {v: (g["det"].get(v), first_assign.get(v), pick.get(v), resc.get(v)) for v in g["victims"]}
    # ---- D1-D4 (10.6) from the arm-independent sample, dp.commands and rows_ff
    srows = sample_rows_of(d)
    nb = nearest_barred_at(dp.get("j_events")) if g["joint_on"] else {}
    dn, dl = d_counts(srows, nb, binders)
    num.update(dn)
    lists.update(dl)
    rets = gt_returns_amended(cmds, binders, ff_dead, ff_rb)
    num["d2_returns"] = len(rets)
    num["gt_returns"] = len(rets)
    lat_end, lat_bound = d4_route_blocked_end(d)
    num["d4_rb_end"] = len(lat_end)
    num["d4_rb_end_bound"] = len(lat_bound)
    g["latched_end"] = lat_end
    # ---- identity / DIVERGED material
    g["h"] = {k: hashes(d.get(k) or []) for k in ROW_KINDS}
    g["cmd_seq"] = cmd_sequence(cmds)
    g["decisions"] = list(ud.get("decisions") or [])
    g["kicks"] = list(ud.get("kicks") or [])
    g["cmd_ctx"] = list(ud.get("cmd_ctx") or [])
    rels = [list(r) for r in dp.get("releases") or []]
    rel_ctx = list(ud.get("rel_ctx") or [])
    mv_events = list(d.get("mv_events") or [])
    _gcols, grows = guard_dicts(d)
    # ---- the movement, guard and shared zeros (10.3; owners in section 3) - every arm runs the guarded fixes
    Z = {}
    Z["Z2-M"] = z2_mov(cmds, g["cmd_ctx"], rels, rel_ctx)
    Z["Z5"] = [r for r in rets if not r["outside"]]
    Z["Z-RB"] = z_rb(mv_rows, False)
    drops_all = []
    for c in cmds:
        prev = (ffs.get(c[0] - 1) or {}).get(c[4])
        if c[2] == "unassign" and c[6] and prev is not None and prev[5] and "replacement" in str(c[5]) and "blocked" in \
                str(c[5]):
            drops_all.append([c[0], c[4], c[3]])
    if g["sw"]["a"]:
        Z["Zm-a"], num["zm_a_pairs"] = zm_a(mv_rows)
    if g["sw"]["b"]:
        Z["Zm-b"] = zm_b(mv_rows)
        Z["Zm-b"] += [[x[0], x[1], "a (b) step changed the _idle_retreat_* state %s -> %s" % (x[3], x[4])]
                      for x in (mvg.get("replica") or {}).get("fix_mismatch") or []]
    if g["sw"]["a"] or g["sw"]["b"]:
        Z["Z-S"], lists["c3_on_burning"] = z_s(mv_rows)
    fix_sw = {"a": g["sw"]["a"], "b": g["sw"]["b"]}
    if g["sw"]["g"] and (g["sw"]["a"] or g["sw"]["b"]):
        Z["Zg-1"] = zg1(grows, fix_sw)
        Z["Zg-1"] += [x[:4] for x in mp_crosscheck(grows) if not fix_sw.get(x[2])]
        Z["Zg-2"] = zg2(grows, fix_sw)
    else:
        Z["Zg-1"] = [x[:4] for x in mp_crosscheck(grows)]
    ran_guard = [[r["step"], r["unit"], r["kind"], "the model evaluated the guard although %s" % (
        "the fix is off" if not fix_sw.get(r["kind"]) else "FF_FIX_STRANDING_GUARD is 0")]
        for r in grows if r.get("model_admit") is not None and not (g["sw"]["g"] and fix_sw.get(r["kind"]))]
    if ran_guard:
        Z.setdefault("Z1-M", []).extend(ran_guard)
    merge_mismatch(Z, shadow_mismatch_zeros(ud.get("shadow_mismatch"), mv_events, "G"))
    g["inst_problems"] = guard_record_problems(grows, mv_rows, mv_events, mvg.get("mp_mismatch") or [])
    # ---- the dispatch-owned zeros (10.3; computed in every arm, gating in dq1)
    jz, jst, jx = dispatch_zeros(dp, srows, rows_vic, ff_dead, ff_rb, g["reassign_on"])
    for k, v in jz.items():
        Z[k] = list(v)
    g["Z"] = Z
    g["jst"] = jst
    lists["gb_c_excused"], lists["gb_c_nosample"] = jx["gb_c_excused"], jx["gb_c_nosample"]
    led = dp.get("ledger") or {}
    if g["joint_on"] or led:
        _v, _r, bcount = ledger_check(cmds)
        lists["ledger_mismatch"] = sorted(k for k in set(led) | {"%s|%s" % kv for kv in bcount}
                                          if int(led.get(k, 0)) != bcount.get(tuple(k.split("|", 1)), 0))
    # ---- the J measures (10.9; reported)
    jn, jl = j_measures(dp, g["terminal"])
    g["jnum"], g["jlists"] = jn, jl
    g["latch_spells"] = latch_spells(binders, ff_dead, vdead, resc)
    # ---- REPORTED items: G-B (a)(b)(d), G-T(b), M6, M3 (round 1's rb_figures with live = joint_on)
    gbn, gbl = gb_counts(binders, dp.get("invariant"))
    num.update(gbn)
    gtn, lists["gt_b"] = gt_b_counts(rets)
    num.update(gtn)
    m6n, m6l = m6_counts(cmds, dp.get("writeoffs_avoided"))
    num.update(m6n)
    lists.update(m6l)
    rbn, rbl, rbc = rb_figures(dp.get("waiting"), binders, dp.get("m3a"), cmds, g["joint_on"])
    num.update(rbn)
    num["m3b"] = num.get("m3b_allowed", 0) + num.get("m3b_blocked", 0)
    g["rb_checks"] = {k_: (len(v_) if isinstance(v_, list) else v_) for k_, v_ in rbc.items()}
    g["rb_fail"] = rb_checks_fail(rbc)
    # ---- M8 / M8-D / the movement round's frozen 22.9 classes for every DD
    g["m8"] = list(dp.get("m8") or [])
    m8 = {e.get("victim"): e for e in g["m8"]}
    deaths = []
    for v in g["DD"]:
        cls, flags, m8d = attribute(v, g["det"].get(v), vdead[v], m8.get(v), g["decisions"], g["kicks"],
                                    dp.get("waiting"), ffs, rows_ff, rows_vic, mv_rows, legs_ev, drops_all, i2, cmds,
                                    g["cmd_ctx"])
        fc, fu, _r = m8_classify([dict(m8[v], death_step=vdead[v])] if v in m8 else [])
        deaths.append({"victim": v, "det": g["det"].get(v), "death": vdead[v],
                       "m8": "FC" if fc else "futile" if fu else "no-m8", "m8d": m8d, "cls": cls,
                       "flags": [k for k, val in flags.items() if val and k != "OTHER"]})
    g["deaths"] = deaths
    # ---- W3 material: dq1's recorded J decisions (the knockout evidence); every dead unit's rows (the C-NONE check)
    g["jpoints"] = j_decision_points(dp) if g["joint_on"] else []
    g["units"] = sorted({str(r[0]) for row in rows_ff for r in row}, key=id_index)
    g["dead_unit_h"] = {u: hashes([next((r for r in rows_ff[s] if r[0] == u), None) for s in range(t)])
                        for u, t in ff_dead.items()}
    g["num"], g["lists"] = num, lists
    return g


def slim(g):
    """CHANGED: drop the heavy material once the cell's pair checks are done (the row hashes stay: the W3 hybrid
    diagnostic compares a knockout's rows with dq0's)."""
    for k in ("cmd_seq", "cmd_ctx", "decisions", "kicks"):
        g.pop(k, None)


_W3Q = {}


def w3_module():
    """NEW: the frozen W3 generator outputs/_dq_w3_queue.py, imported lazily (it is built separately): (module, None)
    or (None, reason)."""
    if "mod" not in _W3Q:
        saved = sys.argv
        sys.argv = saved[:1]
        try:
            _W3Q["mod"], _W3Q["why"] = importlib.import_module("_dq_w3_queue"), None
        except Exception as exc:             # noqa: BLE001 - reported: W3 is then not evaluated (no verdict)
            _W3Q["mod"], _W3Q["why"] = None, repr(exc)[:200]
        finally:
            sys.argv = saved
    return _W3Q["mod"], _W3Q["why"]


def process(cells, opts, queues):
    """CHANGED: load, validate and digest every run of every cell; S1 (dqR vs dq0 on the frozen field list) while both
    records are in memory; DIVERGED (dq0 vs dq1); the W3 generator's compact of every fresh dq0 / dq1 record."""
    w3q, _why = (None, None) if getattr(opts, "smoke", None) else w3_module()
    recs = []
    for c in cells:
        rec = {"cell": c, "g": {}, "prov": {}, "crash": {}, "missing": [], "ident": None, "stop": [], "div": None}
        raw = {}
        for arm in c["arms"]:
            p = run_path(arm, c, opts)
            if p is None:
                continue                      # --smoke: no file given for this arm
            if not os.path.exists(p):
                rec["missing"].append(arm)
                continue
            try:
                d = load_run(p)
            except Exception as exc:          # noqa: BLE001
                rec["prov"][arm] = ["unreadable JSON %r" % (exc,)]
                continue
            line = None if getattr(opts, "smoke", None) else (queues.get(os.path.normcase(p)) or (None, None))[1]
            why, crash, stop = prov_run(d, p, line, None if getattr(opts, "smoke", None) else c, arm, opts)
            rec["crash"][arm] = crash
            if stop:
                rec["stop"].append((arm, stop))
            g = digest(d, arm, "%s_%s" % (ARM_TAG[arm], c["id"]), p, c["set"],
                       censor=(int(d.get("steps_done") or 0) + 1) if getattr(opts, "smoke", None) else H + 1)
            g["line_name"] = line_name(arm, c)
            if c["fresh"] and w3q is not None and arm in ("0", "1"):
                try:
                    g["w3c"] = w3q.compact(d)
                except Exception as exc:      # noqa: BLE001 - W3 is then REFUSED / incomplete (validity only)
                    g["w3c_error"] = repr(exc)[:200]
            rec["prov"][arm] = why + list(g.get("inst_problems") or [])
            rec["g"][arm] = g
            if arm in ("R", "0"):
                raw[arm] = d
            d = None
        if "R" in raw and "0" in raw:
            a, b = raw["R"], raw["0"]
            if a.get("dp_only") or b.get("dp_only"):
                rec["ident"] = (["sd record missing (crash)"], [])
            else:
                rec["ident"] = s1_compare(s1_fields(a), s1_fields(b))
        raw.clear()
        G = rec["g"]
        if "0" in G and "1" in G and G["0"].get("usable") and G["1"].get("usable"):
            rec["div"] = diverged(G["0"], G["1"])
        for g in G.values():
            slim(g)
        recs.append(rec)
    return recs


def sec_prov(recs, opts):
    """CHANGED (three arms; the screen sets 7-8): the validity summary."""
    head("1 LOAD + PROV - arms R (dqR, main 897e93b5), 0 (dq0), 1 (dq1): the 64 screen cells (sets 7-8); files "
         "outputs/_sd_dq<a><r|u><k>_<S>_<W>.json; validity against the frozen queues")
    st = {"missing": [], "invalid": [], "gate": [], "stop": [], "seed": []}
    for arm in ARMS:
        sub = [r for r in recs if arm in r["g"] or arm in r["missing"] or arm in r["prov"]]
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
            out("       %s %s %s: %s" % ("STOP (a crash in dq0 / dqR: a base defect, 10.3)" if arm in ("R", "0") else
                                        "S2 FAILURE (Z6)", arm, cid, mask_text(why) if masked(opts) else why))
        st["missing"] += [(arm, c) for c in miss]
        st["invalid"] += [(arm, c, w) for c, w in inv]
        (st["stop"] if arm in ("R", "0") else st["gate"]).extend((arm, c, w) for c, w in crash)
    for r in recs:
        for arm, why in r["stop"]:
            st["seed"].append((arm, r["cell"]["id"], why))
            out("       STOP (seed-selector rule) %s %s: %s" % (arm, r["cell"]["id"], why))
    nou1 = [g["label"] for r in recs for g in r["g"].values() if g.get("u1_shadow_error")]
    out("  U1 shadow (22.9's U1 class; dqR / dq0 kick records): %s" % (
        "loaded in every run" if not nou1 else "NOT COMPUTED in %d run(s), e.g. %s" % (len(nou1), nou1[:4])))
    return st


def sec_s1(recs, opts):
    """NEW (10.2): S1 = dq0 == dqR value identity on 64 / 64 cells on the FROZEN field list; field paths only."""
    head("2 S1 IDENTITY (10.2) - dq0 == dqR value identity on the FROZEN field list (_fx3r_analyze FIELDS, every mf2 "
         "section, stdout_sha, the non-J dp fields %s, fb3 / mr / ut, the movement record without its timing columns, "
         "the per-step sample and the firefighting log); a listed field missing from either record fails. Field paths "
         "only, never values" % "/".join(S1_DP_REQUIRED))
    comp = [r for r in recs if r["ident"] is not None]
    same = sum(1 for r in comp if not r["ident"][0])
    for r in comp:
        bad, rows = r["ident"]
        if bad:
            detail = [(k, dt) for k, ok, dt in rows if not ok][:8]
            out("    %s DIFFER %s" % (r["cell"]["id"], detail))
    if getattr(opts, "smoke", None):
        want = sum(1 for r in recs if run_path("R", r["cell"], opts) and run_path("0", r["cell"], opts))
    else:
        want = 64
    n_fields = len(comp[0]["ident"][1]) if comp and comp[0]["ident"][1] else 0
    s1 = same == len(comp) == want
    fail = same < len(comp)
    out("  S1: %d / %d cells identical on %d fields (%d compared, %d expected)  => %s" % (
        same, len(comp), n_fields, len(comp), want, "PASS" if s1 else ("FAIL" if fail else "INCOMPLETE")))
    return {"pass": s1, "fail": fail}


def zero_owners(zero, arm):
    """CHANGED (10.3 OWNERSHIP; X-11 (a)): in dqR / dq0 - a SHIPPED movement or guard zero -> 'STOP-RULING' (a defect of
    main's code: STOP for a maintainer ruling; fixing it would be a movement change after the last movement round);
    Z5, Z6, SM -> 'STOP' (a base or instrument defect: fix it, re-run the wave, read nothing); a dispatch-owned zero ->
    'REPORTED' (J is off there: these count today's dispatch). In dq1 every zero -> 'S2' (an S2 FAIL of the
    comparison)."""
    if arm == "1":
        return "S2"
    if zero in MOV_ZEROS or zero in GUARD_ZEROS:
        return "STOP-RULING"
    if zero in DISPATCH_ZEROS:
        return "REPORTED"
    return "STOP"


def sec_zeros(recs, st, opts):
    """CHANGED (10.3's zeros and owners)."""
    head("3 STRUCTURAL ZEROS (10.3) - exact, on every run; IN EVERY ARM the movement (Z1-M item (v), Z2-M, Z-RB, Zm-a, "
         "Zm-b, Z-S), guard (Zg-1 two-sided, Zg-2) and shared (Z5, Z6) zeros and SM; DISPATCH-OWNED in dq1 (G-B(a)/I7 "
         "G-B(b) G-B(c) I4-W G-T(a) G-T(c) M6 Z-C1a Z-C1b Z-C2 Z-R1 Z-R2 Z-C3). Owners: any failure in dq0 / dqR STOPS "
         "(a shipped movement / guard zero there: for a maintainer ruling); a dq1 failure is an S2 FAIL; dispatch zeros "
         "in dq0 / dqR are reported (J off)")
    fails = []
    counts, checked = collections.Counter(), collections.Counter()

    def add(zero, arm, where, items):
        checked[(zero, arm)] += 1
        for it in items:
            counts[(zero, arm)] += 1
            fails.append((zero, arm, where, zero_owners(zero, arm), it))

    for r in recs:
        for arm, g in r["g"].items():
            where = "%s %s" % (arm, r["cell"]["id"])
            add("Z6", arm, where, [r["crash"][arm]] if r["crash"].get(arm) else [])
            if not g.get("usable"):
                continue
            for zero in ZERO_ORDER:
                if zero != "Z6":
                    add(zero, arm, where, (g.get("Z") or {}).get(zero) or [])
    for z in ZERO_ORDER:
        cells = " | ".join("%s %d/%d" % (a, counts[(z, a)], checked[(z, a)]) for a in ARMS if checked[(z, a)])
        out("  %-10s violations / runs checked: %s" % (z, cells or "not applicable"))
    out("  (Z1-M items (i)-(iv) and Zg-3 compare arms that do not exist here and are void, 10.3; SM = a kick / unknown "
        "shadow-mismatch row - none can exist in dq1, whose kick shadow is gated off; dispatch-owned zeros are "
        "recomputed from the probe's recorded J inputs and the instrument's own maps)")
    mask = masked(opts)
    for zero, arm, where, owner, it in fails:
        if owner == "REPORTED":
            continue
        out("    %-11s %-10s %-26s %s" % (owner if owner != "S2" else "S2 FAIL", zero, where,
                                         mask_text(str(it)[:240]) if mask else str(it)[:240]))
    rep = collections.Counter((f[0], f[1]) for f in fails if f[3] == "REPORTED")
    if rep:
        out("  reported (dispatch-owned measures with J off, never gating): %s" % ", ".join(
            "%s %s %d" % (z, a, n) for (z, a), n in sorted(rep.items())))
    a2 = sum(int((g.get("jst") or {}).get("A2 literal reading differs", 0)) for r in recs for g in r["g"].values()
             if g.get("usable"))
    out("  Z-R1's progress rule follows amendment A2 (section 20: a metric with no finite value over H is not "
        "compared); evaluations where 2.8's literal text would give another verdict: %d (reported)" % a2)
    lm = [(g["label"], g["lists"].get("ledger_mismatch")) for r in recs for g in r["g"].values()
          if g.get("usable") and g["lists"].get("ledger_mismatch")]
    if lm:
        out("  reported tooling check: dp.ledger vs the successful assigns of dp.commands disagree in %d run(s): %s" % (
            len(lm), lm[:4]))
    stop = [f for f in fails if f[3] in ("STOP", "STOP-RULING")]
    return {"fails": fails, "stop": stop, "ruling": [f for f in stop if f[3] == "STOP-RULING"],
            "s2": [f for f in fails if f[3] == "S2"]}


# ================================================================================================ W3 (11.2-11.3)
KO_KEYS = {"KOown": "own", "KOothers": "others", "KOlast": "last"}
REPLAY_VERSION = "dq_replay v1"


def kolog_problems(line, head_sha=None):
    """CHANGED (the movement round's boards_problems for outputs/_dq_replay.py's KNOCKOUT LOG): a W3 replay's --kolog
    file exists, is dq_replay v1, carries the line's argv and knockout rules, recorded no error (a rule naming no model
    unit, rules given but J never on), and with head_sha (--head) names the committed tools: replay_sha / probe_sha (the
    sha256 of outputs/_dq_replay.py / outputs/_dq_probe.py's LF-normalised bytes, as the replay read them) equal those
    files' at --head. Returns (problems, the log or None)."""
    argv = line["argv"]
    own = argv[1:argv.index("--")] if "--" in argv else []
    kpath = own[own.index("--kolog") + 1] if "--kolog" in own[:-1] else None
    if kpath is None or not os.path.exists(kpath):
        return ["knockout log missing"], None
    try:
        k = load_json(kpath)
    except Exception as exc:                 # noqa: BLE001
        return ["knockout log unreadable %r" % (exc,)], None
    rules = json.loads(own[own.index("--ko") + 1]) if "--ko" in own[:-1] else []
    probs = []
    if k.get("version") != REPLAY_VERSION:
        probs.append("knockout log version %r (the screen reads %r)" % (k.get("version"), REPLAY_VERSION))
    if k.get("ko_rules") != rules:
        probs.append("knockout log ko_rules %s != the line's %s" % (k.get("ko_rules"), rules))
    if k.get("argv") != argv[1:]:
        probs.append("knockout log argv differs from the line")
    if k.get("errors"):
        probs.append("knockout log errors %s" % (k["errors"][:2],))
    if head_sha:
        for key, rel in (("replay_sha", REPLAY_REL), ("probe_sha", PROBE_REL)):
            want = lf_sha_at(head_sha, rel)
            if want is None or k.get(key) != want:
                probs.append("ran an uncommitted tool: knockout log %s %s is not %s at %s (LF %s)" % (
                    key, str(k.get(key))[:16], rel, head_sha[:10], str(want)[:16]))
    return probs, k


def w2_records_gate(cells, opts, queues):
    """CHANGED (the W3 generator's precondition; the movement round's w2_records_gate for the records W3 reads): section
    1's validity of the W1 dq0 and the W2 dq1 records of `cells` exactly as the analysis reads them (process() and
    sec_prov(): the queue line, the .argv signature, the head rule, the source and instrument shas at --head, CRN, the
    instrument's versions, errors, schemas and J record), printed masked (no outcome value). OK iff both arms of every
    cell are present and readable, none is INVALID and no run's scenario / wind / seed differs from its frozen cell. A
    crash is not a refusal (Z6 material: the W3 rule makes its cell UNCOMPUTABLE). Returns (ok, problems)."""
    recs = process([dict(c, arms=("0", "1")) for c in cells], opts, queues)
    st = sec_prov(recs, opts)
    want = 2 * len(cells)
    present = sum(1 for r in recs for arm in ("0", "1") if arm in r["g"])
    probs = []
    if present != want:
        probs.append("%d of %d W1 dq0 / W2 dq1 records present and readable" % (present, want))
    probs += ["MISSING %s %s" % (a, c) for a, c in st["missing"]]
    probs += ["INVALID %s %s: %s" % (a, c, "; ".join(str(w) for w in why[:4])) for a, c, why in st["invalid"]]
    probs += ["SEED MISMATCH %s %s: %s" % x for x in st["seed"]]
    return not probs, probs


def w2_gate(head_sha, notes):
    """NEW (the contract outputs/_dq_w3_queue.py build relies on: UA.w2_gate(head, notes) -> (ok, problems)): the
    analyzer's own header checks (section 0 with --head and --part2-notes: the hashed sections, the verbatim / module
    checks, the Part 2 notes; --head must descend from the base and the rulings) and section 1's validity of the 64 W1
    dq0 and 64 W2 dq1 records (w2_records_gate on the 64 screen cells). Prints sections 0-1 only, masked; never an
    outcome."""
    opts = argparse.Namespace(head=head_sha, part2_notes=notes, smoke=None, smoke_cell=None, smoke_files={},
                              zeros_only=True, allow_incomplete=False, out=None)
    if not head_sha or not notes:
        return False, ["--head and --part2-notes are both required"]
    if not sec_header(opts):
        return False, ["the analyzer's header checks REFUSED (section 0 above)"]
    frozen = load_seeds()
    if frozen is None:
        return False, ["outputs/_dq_seeds.txt is unusable"]
    cells = screen_cells(frozen, opts)
    if len(cells) != 64:
        return False, ["%d screen cells, 64 expected" % len(cells)]
    return w2_records_gate(cells, opts, load_queues())


def w3_validity(recs, opts):
    """CHANGED (11.2-11.3; the movement round's w3_validity for one gating arm, dq1 against dq0, and dispatch knockouts):
    the W3 queue and candidates re-derived from the W1 (dq0) and W2 (dq1) records by the frozen generator
    outputs/_dq_w3_queue.py (build_plan(W1 lines, W2 lines, compacts); REFUSED when they differ, or when a W1 / W2
    input changed since the queue was generated); every replay present and valid (prov_run against its line as a dq1
    run, plus its knockout log, kolog_problems); every R0 checked against its W2 record (r0_reproduces); per candidate
    THE KNOCKOUT EVIDENCE - the first change ko_first gives on dq1's recorded J decisions (the analyzer's own reading of
    11.2) must equal the frozen rule's prediction (the candidates file's 'first') and be in the replay's ko_applied, and
    a knockout the rule did not queue must have an empty decision set - and the hybrid diagnostic (the knockout's rows
    equal dq0's up to t). Prints validity only (no outcome); returns the evidence for section 7 and the decision."""
    head("W3 VALIDITY (11.2-11.3) - the dispatch knockout replays: the queue re-derived by the frozen rule "
         "(outputs/_dq_w3_queue.py) from the W1 / W2 records; every replay present and valid; every R0 against its W2 "
         "record")
    res = {"state": None, "complete": False, "refused": False, "items": [], "same": [], "uncomputable": [], "r0": {},
           "conflicts": [], "n_lines": 0}
    w3q, why_mod = w3_module()
    comp, bad = {}, []
    for r in fresh_recs(recs):
        for arm in ("0", "1"):
            g = r["g"].get(arm)
            if g is None or r["prov"].get(arm) or "w3c" not in g:
                bad.append("%s %s" % (arm, r["cell"]["id"]))
            else:
                comp[g["line_name"]] = g["w3c"]
    want = 2 * len(fresh_recs(recs))
    if w3q is None:
        res["state"] = "the W3 generator outputs/_dq_w3_queue.py is not importable (%s): W3 is not evaluated" % why_mod
        out("  " + res["state"])
        return res
    if bad or not want or len(comp) != want:
        res["state"] = "W1 / W2 incomplete or INVALID (%d of %d dq0 / dq1 runs not usable, e.g. %s): W3 is not " \
                       "evaluated" % (want - len(comp), want, bad[:3])
        out("  " + res["state"])
        return res
    if not os.path.exists(w3q.Q_W3) and not os.path.exists(w3q.CANDS):
        res["state"] = "W3 NOT GENERATED (outputs/_dq_w3_queue.py, after the W2 wave check)"
        out("  " + res["state"])
        return res
    problems = []
    try:
        frozen = load_json(w3q.CANDS)
        with open(w3q.Q_W3, "rb") as fh:
            q_raw = fh.read().replace(b"\r\n", b"\n")
        raws, waves = {}, {}
        for wave, p in (("w1", Q_W1), ("w2", Q_W2)):
            with open(p, "rb") as fh:
                raws[wave] = fh.read().replace(b"\r\n", b"\n")
            waves[wave] = [json.loads(y) for y in raws[wave].decode("utf-8").splitlines() if y.strip()]
        lines_in = [x for x in waves["w1"] + waves["w2"] if x["name"] in comp]
        doc, lines = w3q.build_plan(waves["w1"], waves["w2"], comp)
    except (Exception, SystemExit) as exc:   # noqa: BLE001 - a W3 that cannot be re-derived is REFUSED
        problems.append("the W3 files or the W1 / W2 queues cannot be read / re-derived: %r" % (exc,))
        frozen, lines, doc, lines_in, raws = {}, [], {}, [], {}
    if not problems:
        norm = lambda v: json.loads(json.dumps(v, sort_keys=True))                   # noqa: E731
        for k in ("version", "rule", "entries", "uncomputable", "counts"):
            if norm(frozen.get(k)) != norm(doc.get(k)):
                problems.append("candidates file field %r differs from the frozen rule's re-derivation" % k)
        if q_raw != "".join(json.dumps(ln) + "\n" for ln in lines).encode("utf-8"):
            problems.append("outputs/_dq_q_w3.jsonl differs from the frozen rule's re-derivation")
        inp = frozen.get("inputs") or {}
        for wave in ("w1", "w2"):
            if inp.get("%s_queue_sha256" % wave) != hashlib.sha256(raws[wave]).hexdigest():
                problems.append("the %s queue changed since W3 was generated" % wave.upper())
        shas = inp.get("records_sha256") or {}
        changed = [ln["name"] for ln in lines_in if shas.get(ln["name"]) != (sha_file(ln["out"]) if os.path.exists(
            ln["out"]) else None)]
        if changed:
            problems.append("%d W1 / W2 record(s) differ from those W3 was generated from, e.g. %s" % (len(changed),
                                                                                                    changed[:4]))
    if problems:
        res["refused"] = True
        res["state"] = "REFUSED: " + "; ".join(problems)
        out("  REFUSED: the W3 queue is not the one the frozen rule gives on these W1 / W2 records (11.3):")
        for p in problems:
            out("    " + p)
        return res
    res["n_lines"] = len(lines)
    res["uncomputable"] = list(frozen.get("uncomputable") or [])
    by_name = {ln["name"]: ln for ln in lines}
    cells = {r["cell"]["id"]: r for r in fresh_recs(recs)}
    owner = {x["name"]: e for e in frozen.get("entries") or [] for x in e["replays"]}
    out_of = {ln["name"]: ln["out"] for ln in lines_in}
    ko_a = tuple(getattr(w3q, "KO_A", ("KOown", "KOlast", "KOothers")))
    ko_b = tuple(getattr(w3q, "KO_B", ("KOown", "KOothers")))
    loaded, missing, invalid = {}, [], []

    def load_w3(name):
        """One replay: None when missing or INVALID (listed), else its rows, completeness, ko_applied and (R0) the
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
        why, crash, stop = prov_run(d, p, line, cells[owner[name]["cell"]]["cell"], "1", opts)
        bprobs, b = kolog_problems(line, getattr(opts, "head", None))
        if why or bprobs or stop:
            invalid.append((name, why + bprobs + ([stop] if stop else [])))
            return None
        is_r0 = name.endswith("_R0")
        rows = d.get("rows_ff") or []
        loaded[name] = {"rows_ff": rows, "complete": crash is None and len(rows) == d.get("steps_done"),
                        "ko_applied": (b or {}).get("ko_applied") or [], "d": d if is_r0 else None,
                        "stdout": _text(stdout_path(p)) if is_r0 else None,
                        "h": {k: hashes(d.get(k) or []) for k in ROW_KINDS}}
        return loaded[name]

    for e in frozen.get("entries") or []:
        r = cells.get(e["cell"])
        g1, g0 = r["g"]["1"], r["g"]["0"]
        for s_ in e.get("same") or []:
            u = s_["unit"]
            res["same"].append({"cell": e["cell"], "set": e["set"], "unit": u, "t": s_["t"],
                                "c_none": g0["dead_unit_h"].get(u) == g1["dead_unit_h"].get(u)})
        if not (e.get("A") or e.get("B")):
            continue
        r0name = next(x["name"] for x in e["replays"] if x["suffix"] == "R0")
        r0 = load_w3(r0name)
        r0_diff = None
        if r0 is not None:
            xp = out_of[e["x"]]
            try:
                xd = load_json(xp)
                r0_diff = r0_reproduces(xd, r0["d"], _text(stdout_path(xp)), r0["stdout"])
            except Exception as exc:          # noqa: BLE001
                r0_diff = ["the W2 record unreadable %r" % (exc,)]
            xd = None
            r0["d"] = None
        res["r0"][e["cell"]] = r0_diff
        jpoints, units = g1.get("jpoints") or [], g1.get("units") or []
        rules_of = {x["name"]: x["rules"] for x in e["replays"]}
        for kind in ("A", "B"):
            for c in e.get(kind) or []:
                u, t = c["unit"], int(c["t"])
                x_dead = g1["ff_dead"].get(u)
                other = c.get("t0") if kind == "A" else c.get("t1", c.get("tx"))
                it = {"cell": e["cell"], "set": e["set"], "kind": kind, "unit": u, "t": t, "other": other,
                      "never_other": other is None, "resolved": True, "why": [], "hybrid": {}}
                if r0_diff is None:
                    it["resolved"] = False
                    it["why"].append("R0 missing or INVALID")
                elif r0_diff:
                    it["resolved"] = False
                    it["why"].append("R0 does not reproduce dq1 (%s)" % r0_diff[:4])
                for ko in (ko_a if kind == "A" else ko_b):
                    key = KO_KEYS.get(ko)
                    if key is None:
                        continue
                    name = (c.get("ko") or {}).get(ko)
                    if name is None and ko in ("KOown", "KOothers"):
                        # the rule did not queue it (an EMPTY decision set): the analyzer's own reading must agree
                        mine = ko_first(jpoints, [{"unit": u if ko == "KOown" else "!" + u, "from": 0, "to": t}],
                                        units)
                        if mine is not None:
                            res["conflicts"].append(["%s %s %s not queued" % (e["cell"], u, ko), mine])
                            it["resolved"] = False
                            it["why"].append("%s not queued, but its decision set is not empty (%s)" % (ko, mine))
                    if name is None:
                        # not run - its decision set is empty in dq1: it equals R0, and R0's (= dq1's) outcome is
                        # used: an (A) unit is dead at t in dq1, a (B) unit alive at t (11.2 EMPTY KNOCKOUT)
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
                    it["hybrid"][ko] = all(rec["h"][k][:t] == (g0.get("h") or {}).get(k, [])[:t] for k in ROW_KINDS)
                    first = ko_first(jpoints, rules_of[name], units)
                    predicted = (c.get("first") or {}).get(ko, first)
                    predicted = None if predicted is None else list(predicted)[:5]
                    applied = [list(a[:5]) for a in rec["ko_applied"]]
                    if first is None or predicted != first or first not in applied:
                        res["conflicts"].append([name, first, predicted])
                        why_ = ("its decision set is empty on dq1's record (it should not have been queued)"
                                if first is None else
                                "the frozen rule's first change %s != the analyzer's %s" % (predicted, first)
                                if predicted != first else
                                "it did not knock out dq1's first changed J decision %s" % (first,))
                        if ko in ("KOown", "KOothers"):
                            it["resolved"] = False
                            it["why"].append("%s: %s" % (ko, why_))
                        else:
                            it[key] = None            # a reported knockout with conflicting evidence: unknown
                    if it[key] is None and ko in ("KOown", "KOothers"):
                        it["resolved"] = False
                        it["why"].append("%s stopped before step %s" % (ko, t))
                res["items"].append(it)
    for name in by_name:                     # every line is read and validated, referenced or not
        load_w3(name)
    n_r0 = len(res["r0"])
    bad_r0 = {k: v for k, v in res["r0"].items() if v}
    out("  W3 queue: %d lines (frozen, identical to the rule's re-derivation from the W1 / W2 records); cells with a "
        "candidate %d; uncomputable cells %d%s" % (len(lines), n_r0, len(res["uncomputable"]),
                                                  "" if not res["uncomputable"] else " %s" % [
                                                      u.get("cell") for u in res["uncomputable"][:6]]))
    out("  replays present and valid %d / %d | missing %d | INVALID %d" % (
        sum(1 for v in loaded.values() if v is not None), len(lines), len(missing), len(invalid)))
    for name, why in invalid:
        out("       INVALID %s: %s" % (name, "; ".join(str(w) for w in why[:6])))
    for name in missing[:40]:
        out("       MISSING %s" % name)
    out("  R0 reproduces its W2 record (rows, commands, J events, movement events, eval, stdout): %d / %d%s" % (
        sum(1 for v in res["r0"].values() if v == []), n_r0,
        "" if not bad_r0 else " - NOT: %s (their candidates are UNRESOLVED)" % [
            (k, v if v is None else v[:4]) for k, v in sorted(bad_r0.items())][:8]))
    out("  knockout evidence conflicts ([replay, the analyzer's first change, the frozen rule's]: a replay that did not "
        "knock out dq1's first changed J decision, a first change the rule predicts otherwise, an empty or a "
        "non-queued non-empty decision set): %s" % (res["conflicts"][:8] or "none"))
    res["complete"] = not missing and not invalid
    res["state"] = "COMPLETE" if res["complete"] else "INCOMPLETE (%d missing, %d INVALID replays)" % (len(missing),
                                                                                                      len(invalid))
    out("  W3 => %s" % res["state"])
    if res["complete"]:
        l4 = l4_counts(res["items"])
        if res["uncomputable"]:
            l4["uncomputable"] = True
            l4["fail"] = True                 # an uncomputable cell counts against (11.3)
        res["l4"] = l4
    return res


# ================================================================================================ 4 COMPARISON
def s6_values(cells):
    """NEW (10.7): S6's inputs over dq1's runs - R = J net ms (the instrument's nested time removed: dp.timing
    j_ms_total) / wall ms per run, and the net ms of every J point (dp.j_timing)."""
    gy = [r["g"]["1"] for r in cells]
    rr = [g["j_ms_total"] / (g["wall_s"] * 1000.0) for g in gy if g.get("wall_s")]
    ms = [x for g in gy for x in g.get("j_net_ms") or []]
    return rr, ms


def comparison(recs, zres, s1_pass, w3=None):
    """CHANGED (10.1-10.7): FULL(0 -> 1) on the fresh cells (sets 7-8): S2 (every zero owned by dq1, 'S2'), S3 (s3_rule
    on DD), S4 = L2 (rescued set 7, set 8) + L3 (DD pooled), S5 = F1 (pooled + R2 per set) + L4 (W3: CAUSED >
    PREVENTED fails; an incomplete W3 leaves S5 and the verdict INCOMPLETE) + the 28 sign-tested counts with Holm
    (compare_counts verbatim over the DIVERGED cells), S6 (median R <= 2 %, p99 <= 50 ms per J point). Also the DIVERGED
    assertion (10.6): its offending [cell, count] pairs in res['div_assert'] (any = STOP)."""
    cells = [r for r in fresh_recs(recs) if usable(r, "0") and usable(r, "1")]
    nx = {r["cell"]["id"]: r["g"]["0"]["num"] for r in cells}
    ny = {r["cell"]["id"]: r["g"]["1"]["num"] for r in cells}
    cset = {r["cell"]["id"]: r["cell"]["set"] for r in cells}
    div = {r["cell"]["id"] for r in cells if r.get("div") and r["div"][0]}
    res = compare_counts(nx, ny, cset, div)
    res["div_assert"] = diverged_assertion(nx, ny, div)
    res["S3"] = s3_rule({c: n["DD"] for c, n in nx.items()}, {c: n["DD"] for c, n in ny.items()}, cset)
    l4 = (w3 or {}).get("l4")
    res["L4_incomplete"] = l4 is None
    res["literal"][L4_KEY] = {"x": None if l4 is None else l4["prevented"], "y": None if l4 is None else l4["caused"],
                              "fail": bool(l4 and l4["fail"]), "l4": l4}
    res["lit_fail"] = [k for k, v in res["literal"].items() if v["fail"]]
    res["S5"] = not res["lit_fail"] and not res["sig_fail"]
    s2f = list(zres.get("s2") or [])
    res["S2"] = not s2f
    res["S2_fails"] = s2f
    rr, ms = s6_values(cells)
    res["S6_detail"] = s6_rule(rr, ms)
    res["S6"] = res["S6_detail"]["pass"]
    if res["L4_incomplete"]:
        res["full"] = "INCOMPLETE (W3: L4 not established)"
    else:
        res["full"] = full_verdict(s1_pass, res["S2"], res["S3"]["pass"], res["S4"], res["S5"], res["S6"])
    res["n_cells"] = len(cells)
    res["cells"] = cells
    res["diverged_cells"] = div
    return res


def print_comparison(res):
    """CHANGED (one comparison, dq0 -> dq1; m = 28; L4)."""
    out("-- dq0 -> dq1 (FRESH sets 7-8 - THE DECISION): %d paired cells, %d DIVERGED (rows, eval or command sequence "
        "differ, 10.6)" % (res["n_cells"], len(res["diverged_cells"])))
    for k, v in res["literal"].items():
        if k == L4_KEY:
            if v["l4"] is None:
                out("    LITERAL %-22s INCOMPLETE (W3 not complete - no verdict, 11.3)" % k)
            else:
                l4 = v["l4"]
                out("    LITERAL %-22s CAUSED %d vs PREVENTED %d (per set %s)%s  %s" % (
                    k, l4["caused"], l4["prevented"], {s: "%d / %d" % tuple(cp) for s, cp in l4["per_set"].items()},
                    " - uncomputable cells (a crashed W2 run) count against" if l4.get("uncomputable") else "",
                    "FAIL" if v["fail"] else "ok (a tie passes)"))
            continue
        if k.startswith("F1 R2"):
            r2 = v["r2"]
            out("    LITERAL %-22s %4d -> %4d  diverged cells: n+ %d n- %d, one-sided exact sign test p %.5f (fails at "
                "<= %.2f)  %s | up %s down %s" % (k, v["x"], v["y"], r2["n_plus"], r2["n_minus"], r2["p"], F1_ALPHA,
                                                 "FAIL" if v["fail"] else "ok", r2["up"][:6], r2["down"][:6]))
            continue
        out("    LITERAL %-22s %4d -> %4d  %s" % (k, v["x"], v["y"], "FAIL" if v["fail"] else "ok"))
    out("    REPORTED beside F1 (never gating): by SEED (ring + uniform summed) %s | the R0 reading (pooled AND each set "
        "literal) %s" % ({s: "n+ %d n- %d p %.4f" % (v["n_plus"], v["n_minus"], v["p"]) for s, v in res["r2s"].items()},
                         "FAIL" if res["r0"]["fail"] else "holds"))
    out("    SIGN-TESTED (10.6; Holm over m = %d, alpha 0.05; reach: 10 changed cells all rising, from 13 one fall):" %
        len(SIGN_KEYS))
    for k, label_ in SIGN_KEYS:
        v = res["sign"][k]
        out("      %-50s %5d -> %5d | n+ %2d n- %2d p %.5f | rank %2d thr %.5f %s%s" % (
            label_, v["x"], v["y"], v["n_plus"], v["n_minus"], v["p"], v["rank"], v["threshold"],
            "REJECTED (FAIL)" if v["rejected"] else "not rejected",
            " | rising in %s" % v["rising"][:6] if v["rising"] else ""))
    s3 = res["S3"]
    out("    S3 (10.4): pooled DD delta %+d | set7 %+d set8 %+d | without the most favourable cell (%s %s) %+d  => %s" % (
        s3["pooled"], s3["per_set"].get("set7", 0), s3["per_set"].get("set8", 0), s3["worst"], s3["worst_delta"],
        s3["loo"], "PASS" if s3["pass"] else "FAIL"))
    s6 = res["S6_detail"]
    out("    S2 %s%s | S4 %s | S5 %s (literal fails %s, sign-test rejections %s) | S6 %s (median R %s, p99 %s ms per J "
        "point; %d runs, %d J points)" % (
            "PASS" if res["S2"] else "FAIL", "" if res["S2"] else " %s" % [(f[0], f[2]) for f in res["S2_fails"][:6]],
            "PASS" if res["S4"] else "FAIL", "INCOMPLETE" if res["L4_incomplete"] else "PASS" if res["S5"] else "FAIL",
            res["lit_fail"] or "none", res["sig_fail"] or "none", "PASS" if res["S6"] else "FAIL",
            fmt(None if s6["median_R"] is None else 100 * s6["median_R"], "%.3f%%"), fmt(s6["p99"], "%.2f"),
            s6["n_runs"], s6["n_calls"]))
    out("    FULL(0 -> 1) = %s" % res["full"])


def sec_comparison(recs, zres, s1_pass, w3=None):
    """CHANGED: the one comparison FULL(0 -> 1) (THE DECISION), after the DIVERGED assertion."""
    head("4 COMPARISON (10.1-10.7) - the 64 FRESH cells (sets 7-8), dq0 -> dq1. LITERAL: F1 pooled; F1 per set read as "
         "R2 (the exact one-sided sign test of the set's diverged cells, p <= 0.05 fails); L2 (rescued set 7, set 8); L3 "
         "(DD pooled); L4 (11.3); 28 counts by the exact one-sided sign test over the DIVERGED cells, Holm family-wise "
         "alpha 0.05")
    C = comparison(recs, zres, s1_pass, w3)
    if C["div_assert"]:
        out("  DIVERGED ASSERTION FAILED (10.6): a cell that is NOT diverged (identical rows, eval and command sequence) "
            "shows a non-zero delta in a gated count - a defect of the counts or of the divergence test: %s" %
            C["div_assert"][:12])
        return C
    out("  DIVERGED assertion (10.6): every cell with a non-zero delta in a gated count is DIVERGED - holds")
    print_comparison(C)
    return C


# ================================================================================================ 5 M8 + 22.9
def sec_m8(recs):
    """CHANGED (dq0 and dq1, fresh sets only)."""
    head("5 M8, M8-D AND THE MOVEMENT ROUND'S FROZEN DEATH CLASSES (22.9) - every detected-victim death in dq0 and dq1 "
         "on the FRESH sets (10.9; reported)")
    classes = ("FUT", "U1", "PRE", "MOV-a", "MOV-b", "MOV-c", "MOV-closure", "RP", "L3", "OTHER")
    for arm in ("0", "1"):
        for s in FRESH:
            sub = [r for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, arm)]
            if not sub:
                continue
            ds = [dd for r in sub for dd in r["g"][arm]["deaths"]]
            fc = sum(1 for dd in ds if dd["m8"] == "FC")
            cnt = collections.Counter(dd["cls"] for dd in ds)
            out("  %s %s (%2d runs): DD %2d | M8 FC %2d futile %2d | M8-D %2d | classes %s" % (
                ARM_TAG[arm], s, len(sub), len(ds), fc, len(ds) - fc, sum(1 for dd in ds if dd["m8d"]),
                " ".join("%s %d" % (k, cnt[k]) for k in classes if cnt[k])))
    out("  per death [arm, cell, victim, detection, death, M8, M8-D, class, every class that applies]:")
    for r in fresh_recs(recs):
        for arm in ("0", "1"):
            g = r["g"].get(arm)
            if not g or not g.get("usable"):
                continue
            for dd in g.get("deaths") or []:
                out("    %s %-22s %-9s det %4s death %4s %-6s M8-D %-5s %-11s %s" % (
                    ARM_TAG[arm], r["cell"]["id"], dd["victim"], dd["det"], dd["death"], dd["m8"], dd["m8d"],
                    dd["cls"], dd["flags"]))


# ================================================================================================ 6 MEASURES (10.9)
def _sum(cells, arm, key):
    return sum(int(r["g"][arm]["num"].get(key, 0) or 0) for r in cells)


def _jsum(cells, arm, key):
    return sum(int(r["g"][arm]["jnum"].get(key, 0) or 0) for r in cells)


def sec_measures(recs, C):
    """NEW (10.9 - reported, never gating; FRESH sets 7-8 only)."""
    head("6 REPORTED, NEVER GATING (10.9) - FRESH sets 7-8")
    cells = C["cells"]
    if not cells:
        out("  no paired usable cell")
        return
    out("M1 / M1c - TIME FROM DETECTION TO RESCUE (10.4; reported beside S3): M1 per victim rescued in BOTH arms, delta "
        "= (rescue - detection) in dq1 minus in dq0; m_c = the cell's mean; T = the unweighted mean of m_c. M1c: every "
        "victim detected in both arms, censored at 361")
    res = m1_compare([(r["cell"], r["g"]["0"], r["g"]["1"]) for r in cells])
    cset = {r["cell"]["id"]: r["cell"]["set"] for r in cells}
    by_id = {r["cell"]["id"]: r["cell"] for r in cells}
    _m1_print("M1", res["m1"], res["victims"], cset, by_id, FRESH)
    _m1_print("M1c", res["m1c"], res["victims_c"], cset, by_id, FRESH)
    out("     cells without a rescued pair: %s | detected in one arm only: %s | anomalies: %s" % (
        res["no_pair"] or "none", res["only_one"][:8] or "none", res["anomalies"][:4] or "none"))
    for arm in ("0", "1"):
        legs = collections.defaultdict(list)
        for r in cells:
            for det_, a_, p_, r_ in r["g"][arm]["lat"].values():
                for name, x, y in (("detection -> assignment", det_, a_), ("assignment -> pickup", a_, p_),
                                   ("pickup -> rescue", p_, r_), ("detection -> rescue", det_, r_)):
                    if x is not None and y is not None and y >= x:
                        legs[name].append(y - x)
        out("     latency decomposition %s (medians, victims reaching each stage): %s" % (ARM_TAG[arm], " | ".join(
            "%s %s (n %d)" % (k, fmt(_median(v), "%.1f"), len(v)) for k, v in legs.items()) or "none"))
    out("M4 J's decisions (dq1) per set: REPLACE stall / margin, LATCH-FILL stall / margin, fills, second fills, "
        "refused, aborted, nearest-barred (stall / margin) events, fills differing from the legacy counterfactual, "
        "re-used-pair binds (dq0's re-used binds beside)")
    for s in FRESH:
        sub = [r for r in cells if r["cell"]["set"] == s]
        out("  %s: REPLACE %d / %d | LATCH-FILL %d / %d | fill %d second_fill %d | refused %d aborted %d | "
            "nearest-barred %d / %d | cf points %d differing %d | re-used binds dq1 %d (dq0 %d)" % (
                s, _jsum(sub, "1", "replace_stall"), _jsum(sub, "1", "replace_margin"), _jsum(sub, "1", "latch_fill_stall"),
                _jsum(sub, "1", "latch_fill_margin"), _jsum(sub, "1", "fill"), _jsum(sub, "1", "second_fill"),
                _jsum(sub, "1", "refused"), _jsum(sub, "1", "aborted"), _jsum(sub, "1", "nearest_barred_stall"),
                _jsum(sub, "1", "nearest_barred_margin"), _jsum(sub, "1", "cf_points"), _jsum(sub, "1", "cf_diff"),
                _jsum(sub, "1", "reused_binds"), _jsum(sub, "0", "reused_binds")))
    for scen in "ABCD":
        sub = [r for r in cells if r["cell"]["scen"] == scen]
        reps = [x for r in sub for x in r["g"]["1"]["jlists"].get("replacements", [])]
        out("  scenario %s: replacements %s" % (scen, collections.Counter((x[2], x[3]) for x in reps) or "none"))
    for r in cells:
        for x in r["g"]["1"]["jlists"].get("replacements", []):
            out("    %s %s" % (r["cell"]["id"], x))
    out("  NEAREST-BARRED victim-steps (4.5; J-post): spells [victim, first, last, steps, run finished]:")
    for r in cells:
        sp = r["g"]["1"]["jlists"].get("nb_spells") or []
        if sp:
            out("    %s %s" % (r["cell"]["id"], sp))
    out("  margin decisions with either unit on an unclean cell (2.8): %d of %d margin replacements planned" % (
        sum(int(r["g"]["1"]["jst"].get("margin decisions with a unit on an unclean cell", 0)) for r in cells),
        sum(int(r["g"]["1"]["jst"].get("replacements planned, margin", 0)) for r in cells)))
    out("ACTED FOOTPRINT (12.1): J points where reverting ONE change alone changes J's decision, and the cells with one, "
        "per set (r1 = round 1's J; C1 / C2 / R-1 / R-2); base != actual J points (an instrument check)")
    for s in FRESH:
        sub = [r for r in cells if r["cell"]["set"] == s]
        out("  %s: %s | base != actual %d" % (s, " | ".join(
            "%s J points %d cells %d" % (v, _jsum(sub, "1", "fp_acted_" + v),
                                         sum(1 for r in sub if r["g"]["1"]["jnum"].get("fp_acted_" + v)))
            for v in FP_VARIANTS), _jsum(sub, "1", "fp_base_ne_actual")))
    out("M6 / M3 (round 1's measures): escape-sweep write-offs, casualty write-offs, other write-offs, closed-route "
        "assigns; M3(a) free unit-steps while a needy victim waits unbound, M3(b) units with a finite route to such a "
        "victim")
    for key in ("m6_escape", "casualty_writeoffs", "other_writeoffs", "assign_closed", "m3a", "m3b"):
        _rline(key, cells, "0", "1", key)
    out("D1 ABANDONED WAITING split (dq0 -> dq1): W / latch-held / nearest-barred / other; D3 beside it: the action-blind "
        "count, the per-status split, the rate per living unit-step; D4's bound / unbound split")
    for key in ("d1_abandoned", "d1_W", "d1_latch-held", "d1_nearest-barred", "d1_other", "d2_returns",
                "d3_idle_unreachable", "d3_blind", "d4_rb_end", "d4_rb_end_bound"):
        _rline(key, cells, "0", "1", key)
    for arm in ("0", "1"):
        lus = sum(r["g"][arm].get("living_unit_steps", 0) for r in cells)
        out("  %s D3 rate per living unit-step: %s (%d / %d)" % (ARM_TAG[arm], fmt(
            _sum(cells, arm, "d3_idle_unreachable") / lus if lus else None, "%.4f"),
            _sum(cells, arm, "d3_idle_unreachable"), lus))
        sp = [x[3] for r in cells for x in r["g"][arm]["lists"].get("d1_spells", [])]
        out("  %s D1 spells: %d, lengths median %s max %s" % (ARM_TAG[arm], len(sp), fmt(_median(sp), "%.1f"),
                                                              max(sp) if sp else None))
    out("THE FIREFIGHTING ACTION SPLIT of unbound units while a victim waits (unit-steps by logged action; 'wrote' = an "
        "extinguish / clear write):")
    for arm in ("0", "1"):
        acts = collections.Counter()
        for r in cells:
            for k, v in r["g"][arm]["num"].items():
                if k.startswith("wait_"):
                    acts[k[5:]] += v
        out("  %s %s" % (ARM_TAG[arm], dict(sorted(acts.items())) or "none"))
    out("LATCH EPISODES (F6) with durations and endings [start, unit, victim, samples, ending]:")
    for arm in ("0", "1"):
        ends = collections.Counter(x[4] for r in cells for x in r["g"][arm]["latch_spells"])
        lens = [x[3] for r in cells for x in r["g"][arm]["latch_spells"]]
        out("  %s episodes %d | endings %s | samples median %s max %s" % (
            ARM_TAG[arm], len(lens), dict(ends) or "none", fmt(_median(lens), "%.1f"), max(lens) if lens else None))
    for r in cells:
        x = r["g"]["1"]["latch_spells"]
        if x:
            out("    dq1 %s %s" % (r["cell"]["id"], x[:8]))
    out("DIAG every fresh cell where dq1 is WORSE than dq0 in DD, rescued or firefighter deaths (10.9):")
    n = 0
    for r in cells:
        n0, n1 = r["g"]["0"]["num"], r["g"]["1"]["num"]
        w = [k for k, worse in (("DD", n1["DD"] > n0["DD"]), ("rescued", n1["rescued"] < n0["rescued"]),
                                ("ff_deaths", n1["ff_deaths"] > n0["ff_deaths"])) if worse]
        if not w:
            continue
        n += 1
        out("  %s worse in %s | DD / rescued / ff deaths dq0 %d/%d/%d dq1 %d/%d/%d | diverged %s" % (
            r["cell"]["id"], w, n0["DD"], n0["rescued"], n0["ff_deaths"], n1["DD"], n1["rescued"], n1["ff_deaths"],
            (r.get("div") or [False, []])[1]))
        out("     dq1 deaths %s | ff deaths dq0 %s dq1 %s | J replacements %s" % (
            [(dd["victim"], dd["death"], dd["cls"]) for dd in r["g"]["1"]["deaths"]], r["g"]["0"]["ff_dead"],
            r["g"]["1"]["ff_dead"], r["g"]["1"]["jlists"].get("replacements", [])[:4]))
    if not n:
        out("  none")
    rising = [(k, C["sign"][k]["rising"]) for k, _l in SIGN_KEYS if C["sign"][k]["rising"]]
    out("DIAG rising instances dq0 -> dq1 (every sign-tested count, whatever the test says): %s" % (
        "none" if not rising else ""))
    for k, cl in rising:
        out("    %-22s %s" % (k, cl[:12]))
    sc = {s: (sum(r["g"]["0"]["num"]["rescued"] for r in cells if r["cell"]["scen"] == s),
              sum(r["g"]["1"]["num"]["rescued"] for r in cells if r["cell"]["scen"] == s)) for s in "ABCD"}
    out("SCENARIO rescued dq0 -> dq1: %s" % {s: "%d->%d" % v for s, v in sc.items()})


# ================================================================================================ 7 W3 / L4
def sec_w3_report(w3):
    """CHANGED (11.3): the L4 counts both ways (CAUSED and PREVENTED, pooled and per set) with every candidate's
    evidence; REPORTED, never counted: the run-level variant, KO-LAST, the hybrid diagnostic (whether each knockout's rows
    equal dq0's up to t), and the same-step deaths with the C-NONE check."""
    head("7 W3 / L4 - THE PER-DEATH ATTRIBUTION (11.3): CAUSED and PREVENTED for dq1, pooled and per set (FAIL iff "
         "CAUSED > PREVENTED); the rest reported, never counted")
    if not w3 or not w3.get("complete"):
        out("  W3 %s - no count is printed" % ((w3 or {}).get("state") or "not evaluated"))
        return
    items, l4 = w3["items"], w3["l4"]
    rl = l4_run_level(items)
    out("-- CAUSED %d vs PREVENTED %d pooled (per set %s)%s => %s | RUN-LEVEL variant (reported): CAUSED %d PREVENTED %d "
        "(per set %s)" % (l4["caused"], l4["prevented"], {s: "%d / %d" % tuple(v) for s, v in l4["per_set"].items()},
                          " | uncomputable cells: counted as not passing" if l4.get("uncomputable") else "",
                          "FAIL" if l4["fail"] else "holds (a tie passes)", rl["caused"], rl["prevented"],
                          {s: "%d / %d" % tuple(v) for s, v in rl["per_set"].items()}))
    for it in sorted(items, key=lambda z: (z["kind"], z["cell"], z["unit"])):
        if it["kind"] == "A":
            counted = (not it["resolved"]) or it.get("own") is True or it.get("others") is True
        else:
            counted = bool(it["resolved"]) and (it.get("own") is False or it.get("others") is False)
        out("   (%s) %-22s %-9s t %3s (other arm %s) | %s | alive at t: KO-OWN %s%s KO-OTHERS %s%s%s | %s | hybrid "
            "(rows == dq0's up to t) %s" % (
                it["kind"], it["cell"], it["unit"], it["t"], it["other"],
                "RESOLVED" if it["resolved"] else "UNRESOLVED (%s)" % "; ".join(it["why"][:3]),
                it.get("own"), "" if it.get("own_run") else " (not run: R0)", it.get("others"),
                "" if it.get("others_run") else " (not run: R0)",
                " KO-LAST %s" % it.get("last") if it["kind"] == "A" else "",
                ("CAUSED" if it["kind"] == "A" else "PREVENTED") if counted else
                ("not caused" if it["kind"] == "A" else "not prevented"), it.get("hybrid") or "-"))
    if w3["uncomputable"]:
        out("   uncomputable cells (a crashed W2 run): %s" % [u.get("cell") for u in w3["uncomputable"]])
    same = w3.get("same") or []
    out("-- deaths at the same step in dq1 and dq0 (neither candidate; the C-NONE check - the unit's own rows identical "
        "up to t): %s" % ("none" if not same else ""))
    for s_ in same:
        out("   %-22s %-9s t %3s: %s" % (s_["cell"], s_["unit"], s_["t"], "C-NONE" if s_["c_none"] else
                                        "the unit's rows differ before t (not C-NONE)"))


# ================================================================================================ 8 DECISION
def acted_footprint(recs):
    """NEW (10.8): per correction (C1, C2, R-1, R-2) and fresh set, the dq1 cells where reverting it alone changed J's
    decision at some J point (the instrument's ACTED footprint)."""
    res = {}
    for v, _name in FP_CORRECTIONS:
        res[v] = {s: sum(1 for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, "1")
                         and r["g"]["1"]["jnum"].get("fp_acted_" + v)) for s in FRESH}
    return res


def sec_decision(recs, st, s1, zres, C, w3, opts):
    """CHANGED (10.8 on FULL(0 -> 1); no verdict until W3 is complete and every R0 checked, 11.3)."""
    head("8 DECISION (10.8: FULL(0 -> 1); S4 = L2 + L3, S5 = F1 (R2), L4 and the 28 sign-tested counts)")
    incomplete = bool(st["missing"] or st["invalid"])
    arm0_stop = bool(zres["stop"]) or bool(st["stop"])
    full = C["full"]
    out("S1 IDENTITY %s | dq0 / dqR STOP items %d (for a maintainer ruling %d)" % (
        "PASS" if s1["pass"] else "FAIL" if s1["fail"] else "INCOMPLETE", len(zres["stop"]) + len(st["stop"]),
        len(zres.get("ruling") or [])))
    out("FULL(0 -> 1) (THE DECISION): %s | S2 %s S3 %s S4 %s S5 %s S6 %s" % (
        full, C["S2"], C["S3"]["pass"], C["S4"], "INCOMPLETE" if C["L4_incomplete"] else C["S5"], C["S6"]))
    af = acted_footprint(recs)
    for v, name in FP_CORRECTIONS:
        sets = af[v]
        out("  %-38s ACTED cells %s%s" % (name, sets, "" if all(sets[s] for s in FRESH) else " - NOT EXERCISED in %s "
                                                                                            "(no verdict changes)" % [
                                                                                                s for s in FRESH
                                                                                                if not sets[s]]))
    if not all(af["C2"][s] for s in FRESH):
        out("  DISCLOSED (10.8): C2 is NOT EXERCISED in a fresh set - if it ships, the latch rule shipped untested on "
            "the screen, supported only by its tests, its zeros and the offline mechanism check (5.4)")
    cells = C["cells"]
    sc = {s: (sum(r["g"]["0"]["num"]["rescued"] for r in cells if r["cell"]["scen"] == s),
              sum(r["g"]["1"]["num"]["rescued"] for r in cells if r["cell"]["scen"] == s)) for s in "ABCD"}
    drop = [(s, a, b) for s, (a, b) in sc.items() if b - a <= -2]
    out("scenario rescued dq0 -> dq1: %s | %s" % ({s: "%d->%d" % v for s, v in sc.items()},
                                                   "SCENARIO STOP (DIAGNOSTIC, 10.8: reported with its diagnosis; the "
                                                   "verdict stands) %s" % drop if drop else "no fall of 2 or more"))
    w3_done = bool(w3 and w3.get("complete") and not C["L4_incomplete"])
    outcome = decide(arm0_stop, s1["fail"], full) if (w3_done or arm0_stop or s1["fail"]) else None
    if outcome is None:
        verdict = "NO VERDICT - W3 is %s (11.3: the analyzer prints no verdict until W3 is complete and every R0 has " \
                  "been checked)" % ((w3 or {}).get("state") or "not evaluated")
    else:
        verdict = "OUTCOME %d: %s" % (outcome, OUTCOME_TEXT[outcome])
        if not s1["pass"] and not s1["fail"]:
            verdict = "INCOMPLETE (S1 not established: the identity wave is incomplete) - would be %s" % verdict
        if incomplete:
            verdict = ("PROVISIONAL (incomplete data, --allow-incomplete) - %s" % verdict
                       if getattr(opts, "allow_incomplete", False) else
                       "INCOMPLETE (%d missing, %d invalid runs - re-run them; no outcome is read)" % (
                           len(st["missing"]), len(st["invalid"])))
    out("")
    out("VERDICT: %s" % verdict)
    return outcome


# ================================================================================================ outcome gate
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


def structure_counts(g):
    """NEW (13 (9) STRUCTURE CHECK): the corrections' paths one dq1 run exercised - a C1 fill where a re-used pair is
    nearest, a contest with a closed route, a stall and a margin replacement (planned), a nearest-barred frame - and
    the C2 / latch material (contests with a latched incumbent, LATCH-FILLs), with the ACTED footprint."""
    j = g.get("jst") or {}
    n = g.get("jnum") or {}
    return collections.OrderedDict([
        ("C1 fill with a re-used pair nearest", int(j.get("fills with a re-used pair nearest (C1 path)", 0))),
        ("contest with a closed route", int(j.get("contests, route closed", 0))),
        ("stall replacement", int(j.get("replacements planned, stall", 0))),
        ("margin replacement", int(j.get("replacements planned, margin", 0))),
        ("nearest-barred frame", int(j.get("nearest-barred frames", 0))),
        ("contest with a latched incumbent", int(j.get("contests, latched incumbent", 0))),
        ("LATCH-FILL", int(n.get("latch_fill_stall", 0)) + int(n.get("latch_fill_margin", 0))),
        ("J points with PRE", int(j.get("J points with PRE", 0))),
        ("progress evaluations", int(j.get("progress evaluations", 0))),
        ("fills", int(j.get("fills", 0))),
    ])


STRUCTURE_PATHS = ("C1 fill with a re-used pair nearest", "contest with a closed route", "stall replacement",
                   "margin replacement", "nearest-barred frame")


def print_structure(recs):
    """NEW (13 (9), smoke): per dq1 run the paths exercised (STRUCTURE) and every run's in-run cost (J net ms total and
    p99 per J point, R, the instrument's own time, the wall time); structural fields only, no outcome."""
    for r in recs:
        for arm in ARMS:
            g = r["g"].get(arm)
            if not g or not g.get("usable"):
                continue
            jm = g.get("j_net_ms") or []
            out("  COST %s %s: J points %d, J net ms total %.1f (raw %.1f), p99 per J point %s, max %s | R %s | dq "
                "instrument ms %s | probe share of wall %s | wall %s s" % (
                    r["cell"].get("spent_id", r["cell"]["id"]), ARM_TAG[arm], len(jm), g["j_ms_total"],
                    g["j_ms_raw_total"], fmt(q(jm, 0.99)), fmt(max(jm) if jm else None),
                    fmt(100.0 * g["j_ms_total"] / (g["wall_s"] * 1000.0) if g.get("wall_s") else None, "%.3f%%"),
                    fmt((g.get("dq_timing") or {}).get("dq_ms_total"), "%.1f"),
                    fmt(None if g.get("probe_frac") is None else 100.0 * g["probe_frac"], "%.3f%%"),
                    fmt(g.get("wall_s"), "%.0f")))
            if arm == "1":
                sc = structure_counts(g)
                out("  STRUCTURE %s dq1: %s | paths NOT EXERCISED in this run: %s" % (
                    r["cell"].get("spent_id", r["cell"]["id"]), dict(sc),
                    [p for p in STRUCTURE_PATHS if not sc[p]] or "none"))


def outcome_sections(recs, st, s1, zres, w3, opts):
    """CHANGED: sections 4-8, gated:
    - --zeros-only (the wave check): nothing after the W3 validity but ZEROS_ONLY_LINE;
    - --smoke: the STRUCTURE and COST lines, then SMOKE_SUPPRESSED - no literal clause, sign-tested count, S2-S5,
      FULL, M8, measure, DIAG, L4 or decision;
    - a missing or INVALID run, or a W3 that is not complete, without --allow-incomplete: the INCOMPLETE line only;
    - otherwise every section (PROVISIONAL with --allow-incomplete; NO VERDICT while W3 is incomplete). The DIVERGED
      assertion failing is a STOP (exit 1)."""
    if getattr(opts, "zeros_only", False):
        out(ZEROS_ONLY_LINE)
        return None
    s1_pass = not s1["fail"] or bool(opts.smoke)
    if opts.smoke:
        head("4 SMOKE - the STRUCTURE of 13 (9) and the in-run COST only (no verdict)")
        print_structure(recs)
        out(SMOKE_SUPPRESSED)
        return None
    w3_ok = bool(w3 and w3.get("complete"))
    if (st["missing"] or st["invalid"] or not w3_ok) and not getattr(opts, "allow_incomplete", False):
        head("8 DECISION")
        out("VERDICT: %s" % incomplete_line(st, w3))
        return None
    C = sec_comparison(recs, zres, s1_pass, w3)
    if C["div_assert"]:
        stop_out(opts, "STOP - the DIVERGED assertion failed (10.6): fix the counts or the divergence test; no outcome "
                       "is read")
        return "STOP"
    sec_m8(recs)
    sec_measures(recs, C)
    sec_w3_report(w3)
    return sec_decision(recs, st, {"pass": s1["pass"], "fail": s1["fail"]}, zres, C, w3, opts)


# ================================================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--out")
    ap.add_argument("--head")
    ap.add_argument("--part2-notes")
    ap.add_argument("--allow-incomplete", action="store_true")
    ap.add_argument("--smoke")
    ap.add_argument("--smoke-cell", default="set1/ring/A_N")
    ap.add_argument("--smoke-files", default="")
    ap.add_argument("--zeros-only", action="store_true")
    opts = ap.parse_args(_ARGV[1:] if argv is None else argv)
    opts.smoke_files = dict(x.split("=", 1) for x in opts.smoke_files.split(",") if "=" in x)
    if not opts.smoke and not opts.head:
        ap.error("--head <the screen head> is required outside --smoke")
    if opts.zeros_only and opts.allow_incomplete:
        ap.error("--zeros-only prints no outcome: --allow-incomplete does not apply")
    if opts.smoke and (set(opts.smoke_files) - set(ARMS) or not opts.smoke_files):
        ap.error("--smoke-files takes ARM=FILE with ARM in R, 0, 1")
    if os.path.normcase(os.path.realpath(HERE)) != os.path.normcase(os.path.realpath(OUT_DIR)):
        print("REFUSED: this analyzer must live in %s (it is in %s)" % (OUT_DIR, HERE))
        return 2
    del _LINES[:]
    try:
        if not sec_header(opts):
            return 2
        frozen = load_seeds()
        if frozen is None:
            return 2
        queues = {} if opts.smoke else load_queues()
        cells = screen_cells(frozen, opts)
        if opts.smoke and not cells:
            out("REFUSED: --smoke-cell %s is not a cell of the spent sets 1-2" % opts.smoke_cell)
            return 2
        recs = process(cells, opts, queues)
        st = sec_prov(recs, opts)
        if st["seed"]:
            out("STOP: a run's scenario / wind / seed differs from its frozen cell (seed-selector rule)")
            return 2
        s1 = sec_s1(recs, opts)
        if s1["fail"] and not opts.smoke:
            stop_out(opts, "STOP (S1 IDENTITY FAILED) - %s" % OUTCOME_TEXT[2])
            return 1
        zres = sec_zeros(recs, st, opts)
        if (st["stop"] or zres["stop"]) and not opts.smoke:
            stop_out(opts, "STOP - %s%s" % (OUTCOME_TEXT[1], " FOR A MAINTAINER RULING (a shipped movement / guard zero "
                                                             "failed in dq0 / dqR)" if zres["ruling"] else ""))
            return 1
        w3 = None if opts.smoke else w3_validity(recs, opts)
        if w3 is not None and w3.get("refused"):
            stop_out(opts, "REFUSED - the W3 queue is not the one the frozen rule gives on these W1 / W2 records (11.3)")
            return 2
        res = outcome_sections(recs, st, s1, zres, w3, opts)
        if res == "STOP":
            return 1
    finally:
        if opts.out:
            with open(opts.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(_LINES) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
