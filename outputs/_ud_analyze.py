"""Urgency round Part 3 analyzer - PRE-REGISTERED (outputs/urgency_part1.txt 16.5-16.11, 17.2 S3, 22.5-22.9 and the
guard policy of amendment B2, section 23). A port of dispatch:outputs/_dp_analyze.py (cc8d653c) to the 2 x 2 factorial
screen of 22.7: arms 0 (ud0), U (ud1, DISPATCH_URGENCY=1), M (ud2, the three movement switches) and MU (ud3, all four).

READ-ONLY. It reads run files from E:/Projects/SAS_wt/urgency/outputs (or --smoke DIR) and git objects of this worktree's
repository, and writes nothing but --out. Every decision function is pure and is checked on hand-built records by
outputs/_ud_analyze_selftest.py, which must pass before any real run is read (16.6).

usage (urgency worktree root, the urgency .venv python):
  python outputs/_ud_analyze.py --head SHA --part2-notes PATH [--out REPORT] [--allow-incomplete | --zeros-only]
  python outputs/_ud_analyze.py --smoke DIR --smoke-files ARM=FILE[,ARM=FILE...] [--smoke-cell set1/ring/D_W]
                                [--out REPORT] [--zeros-only]
  --head SHA          the Part 2 commit: every run's recorded head must start with it, and every source sha it
                      recorded (ud.src_sha, dp.src_sha) must equal the file at SHA, LF or CRLF form (16.6; R2 M-2;
                      INVALID otherwise: 'ran uncommitted source')
  --zeros-only        the 16.12 wave check: sections 0-3 and validity, then stop - no outcome section, no verdict, and
                      no outcome VALUE in a Z0 / zero failure line (field paths only, numbers masked)
  without --allow-incomplete a missing or INVALID run stops the analysis after section 3 (no outcome is printed)
  --part2-notes PATH  the Part 2 notes: every '<sha256> <outputs/...>' line is verified against the file on disk; the
                      tooling files and the frozen queues must be listed (15.5). REFUSED on any mismatch.
  --allow-incomplete  compute on what exists; the verdict is then PROVISIONAL (without it: INCOMPLETE, and no outcome
                      section is printed)
  --smoke DIR         one cell from DIR: ARM in ref (the dpR record), 0, U, M, MU, E0, E1; relaxed validity (no queue,
                      no 360-step, no head checks); the cell's runs stand in for BOTH fresh sets (set 3; set 4 empty).
                      SMOKE - NOT A SCREEN. It prints sections 0-3 and each comparison's S6 cost line (R, p99) only:
                      every outcome section is suppressed (22.6.3: no movement outcome on sets 1-2 is read).
exit: 0 report written; 1 STOP (S1 identity failed, an arm-0 failure, a crash in arm 0 - 22.8.2; nothing else is
read); 2 REFUSED (a hashed text differs, a reused function or module is not the committed one, the Part 2 notes
differ, the seeds file is unusable, or a run's scenario / wind / seed is not its frozen cell).

SECTIONS
  0 HEADER        commits c59b5058 (Part 1), 4a44d2a3 (Part 1b), 7ecb6c77 (B2), HEAD and --head; the hash checks of
                  16.5-16.11 and 17 (against c59b5058) and 21, 22.5-22.9 and 23 (against 7ecb6c77); the DPR functions
                  replicated verbatim from cc8d653c; the reused modules byte-identical to cc8d653c's; the Part 2
                  notes; the seeds (16.2 rule recomputed; sets 1-2 = the fx3mS / fx3mS2 argv cells).
  1 LOAD + PROV   16.6 validity per run: INVALID (tooling: a ud_probe v1 record, uncommitted source, ...), GATE
                  FAILURE (Z6: a crash, a non-zero chain exit or an early stop in U / M / MU - never INVALID), STOP (an
                  arm-0 crash).
  2 Z0 IDENTITY   ud0 on sets 1-2 == outputs/_ud_dpR/ (DPR's G-ID field set); the evidence OFF runs ==
                  outputs/_ud_dpE/; ud0 reproduces dp0's M8 (13 deaths, 11 FC).
  3 ZEROS         22.8.2: arm-0 failures; U1-owned Z1 Z2 Z3 Z4 Z7 Z8; movement-owned Z1-M Z-RB Zm-a Zm-b Zm-c Z-S
                  Z2-M (in U / E1: REPORTED, R3 D-12); shared Z5 (amended outside events, section 10) and Z6. Every
                  failing instance is listed. Divergence = the victim each order WOULD BIND (v2 index_wb / u1_wb: the
                  first planner-accepted victim), not the list head (R2 B-1). Z7 gates by Z7_READING ('acc': the maintainer's
                  ruling (ii), urgency_part1.txt 25); the literal 16.7 reading is reported beside it (R3 D-24).
  4 COMPARISONS   0->M, 0->U, 0->MU, M->MU, U->MU on the 64 FRESH cells: literal L1-L3 and the 24 sign-tested counts
                  (23.2: exact one-sided sign test over the diverged cells, Holm within the comparison's family of
                  24); S3 (17.2); S6 (cost); FULL and HARMLESS. In-sample 0->U on sets 1-2: reported.
  5 M8 + 22.9     M8 (FC / futile), M8-D and the frozen attribution classes per arm and set; the positive control
                  against 3.1's tally of the 13 deaths (W1).
  6 MEASURES/DIAG MU1 / MU2 decisions and fates; ACTED footprint; M2 outcomes; every cell where arms differ; every
                  rising instance; raises / strandings near (a)-acted steps; SHELTER / HOLD episodes; deferred
                  victims written off; firefighter deaths in diverged cells. REPORTED subsections (never gated):
                  6.R1 M1 / M1c (DPR 14.7) per comparison; 6.R2 MU3 verdict quality, bias and Harrell C with the
                  seed-level bootstrap; 6.R3 MU4 firefighter exposure split by U1-divergent / fix-ACTED bind legs;
                  6.R4 16.8's dispatch-round items G-B (a)(b)(d), G-T(b), M6, M3.
  7 EVIDENCE      16.11 cases OFF vs ON (described, not gated).
  8 DECISION      R-M, R-U, R-MU; outcomes 1-6 of 22.8.5; per-switch verdicts; the per-movement-switch rule (NOT
                  MEASURED); I(c) reported; the scenario STOP as a diagnostic.
Conventions (as _dp_analyze): rows_* index t = the state after step t + 1; detection steps from <out minus
.json>.stdout.txt '[Victim Detection]' lines; a death step = the first rows_vic managed 'dead'. d["mv"] step = the
advance's step (rows_ff index + 1). Reused, imported unchanged: _sd_analyze.analyze (I2 / I6), _fb3_analyze
searcher_o / ff_episodes, _fx3_pockets (via searcher_o), _ut_analyze._last_detection, _ut_analyze2.ff_status_track,
_fx3r_analyze FIELDS / DET_RE, _fb3_queue.cells, _mf2_pool.signature.
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
WT = r"E:\Projects\SAS_wt\urgency"
OUT_DIR = os.path.join(WT, "outputs")
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
finally:
    sys.argv = _ARGV

PART1, PART1B, B2 = "c59b5058", "4a44d2a3", "7ecb6c77"
DISPATCH = "cc8d653c4a5740c0f04a9e94d6ff48e92a0ca027"
REUSED_MODULES = ("_fx3r_analyze.py", "_fb3_analyze.py", "_sd_analyze.py", "_ut_analyze.py", "_ut_analyze2.py",
                  "_fx3_pockets.py", "_mf2_p3_analyze.py", "_fb3_queue.py", "_mf2_pool.py")
HASHED = (("16.5-16.11", PART1, "16.5 THE INSTRUMENT", "16.12 WAVES"),
          ("17", PART1, "17. DECISION RULE", "18. RISKS"),
          ("21", B2, "21. RULINGS", "22. AMENDMENT B1"),
          ("22.5-22.9", B2, "22.5 SWITCHES", "22.10 DECISIONS"),
          ("23", B2, "23. AMENDMENT B2", None))
NOTES_REQUIRED = ("outputs/_ud_probe.py", "outputs/_ud_analyze.py", "outputs/_ud_analyze_selftest.py",
                  "outputs/_ud_queue.py", "outputs/_ud_q_w1.jsonl", "outputs/_ud_q_w2.jsonl", "outputs/_ud_q_w3.jsonl",
                  "outputs/_ud_q_w4.jsonl",
                  # R2 m-4 / R3 D-15: the chain _ud_probe.py loads (runpy / importlib: _ut_probe -> _fb3_probe ->
                  # _fx3_probe -> _mf2_probe -> _sd_probe; _fb3_probe -> _fm2_probe_harness (-> _ffr_harness) and
                  # _bp_inst), the frozen seed and reference lists, the smoke queue, and the check / mutation tooling
                  "outputs/_ut_probe.py", "outputs/_fb3_probe.py", "outputs/_fx3_probe.py", "outputs/_mf2_probe.py",
                  "outputs/_sd_probe.py", "outputs/_fm2_probe_harness.py", "outputs/_ffr_harness.py",
                  "outputs/_bp_inst.py", "outputs/_ud_seeds.txt", "outputs/_ud_dpR_sha256.txt",
                  "outputs/_ud_q_smoke.jsonl", "outputs/_ud_probe_check.py", "outputs/_ud_mutants.py",
                  "outputs/_ud_mutants_u1.py", "outputs/_ud_mutants_mv.py")
# The instrument version the SCREEN reads (16.6). v2 adds, per kick: acc (the planner would assign her, at kick entry;
# None when the U1 shadow is not computed), index_wb / u1_wb (the first ACCEPTED victim of each order), div_shadow /
# divergent defined on them (the head-based values kept as div_shadow_head / divergent_head) and attempts; per decision:
# accepted; per d["mv"] row: dcb. A v1 record is INVALID for the screen; --smoke may still read one.
UD_PROBE = "ud_probe v2"
UD_PROBE_SMOKE_OK = ("ud_probe v1", "ud_probe v2")
# Z7 READING - RULED (maintainer, 2026-10-06; urgency_part1.txt 25, amendment B4): reading (ii) GATES, Z7-ACC ("U binds
# u1_wb, the first victim of its order the planner accepts - none iff u1_wb is None - to f"). 16.7's literal reading
# ("the first in its order") is REPORTED beside it. "literal" would swap the two.
Z7_READING = "acc"
H = 360
STUCK, WIN = 20, 30                        # _sd_analyze I2 thresholds (as _dp_analyze)
ALPHA = 0.05
EXPECTED_BASES = {"set1": 9601, "set2": 9621, "set3": 573001, "set4": 780001}
FRESH = ("set3", "set4")
WINDS = (("N", "north"), ("S", "south"), ("E", "east"), ("W", "west"))
PLACES = (("r", "ring", 0), ("u", "uniform", 1))
ARMS = ("0", "U", "M", "MU")
ARM_TAG = {"0": "ud0", "U": "ud1", "M": "ud2", "MU": "ud3"}
ARM_SW = {"0": set(), "U": {"U1"}, "M": {"MOV"}, "MU": {"U1", "MOV"}, "E0": set(), "E1": {"U1"}}
DPR_TAGS = {(1, "r"): "dpRr", (2, "r"): "dpRr2", (1, "u"): "dpRu", (2, "u"): "dpRu2"}
COMPARISONS = (("0", "M"), ("0", "U"), ("0", "MU"), ("M", "MU"), ("U", "MU"))
ADDED = {("0", "M"): {"MOV"}, ("0", "U"): {"U1"}, ("0", "MU"): {"U1", "MOV"}, ("M", "MU"): {"U1"},
         ("U", "MU"): {"MOV"}}
# 3.1 / section 3: dp0's M8 per set (FC, futile) - ud0 must reproduce it (16.7 Z0)
DP0_M8 = {"set1": (4, 1), "set2": (7, 1)}
# 3.1's hand tally of the 13 dp0 deaths: (set, placement, key, victim) -> (#, death step, manual class)
TALLY_31 = {("set1", "ring", "B_N", "victim_1"): (1, 186, "L3"), ("set1", "ring", "B_S", "victim_3"): (2, 57, "FUT"),
            ("set1", "ring", "B_W", "victim_3"): (3, 72, "MOV"), ("set1", "uniform", "B_E", "victim_0"): (4, 96, "MOV"),
            ("set1", "uniform", "C_E", "victim_0"): (5, 78, "FUT-in-practice"),
            ("set2", "ring", "B_N", "victim_0"): (6, 165, "MOV"),
            ("set2", "ring", "B_N", "victim_1"): (7, 39, "FUT-in-practice"),
            ("set2", "ring", "B_S", "victim_0"): (8, 93, "MOV"), ("set2", "ring", "B_W", "victim_2"): (9, 33, "MOV"),
            ("set2", "ring", "D_N", "victim_1"): (10, 162, "MOV"), ("set2", "ring", "D_W", "victim_2"): (11, 270, "MOV"),
            ("set2", "uniform", "A_N", "victim_1"): (12, 123, "MOV"),
            ("set2", "uniform", "D_N", "victim_3"): (13, 162, "FUT")}
J_ONLY = ("probe", "switches", "src_sha", "j_calls", "j_events", "ledger", "timing", "rc_chain", "j_detail",
          "j_timing")
TERMINAL = ("rescued", "dead", "unreachable")
DISPATCH_RE = re.compile(r"^\[Dispatch\] FF-(\S+) assigned to (\S+) reason=(\S+) manhattan_dist=(\S+)")
STEP_RE = re.compile(r"\bstep=(\d+)")
TRIAGE_TAG = "[UrgencyTriage]"
NEW_TAGS = (TRIAGE_TAG,)                   # 16.7 Z1: stdout compared with the new tags stripped
TRIAGE_RE = re.compile(r"^\[UrgencyTriage\] step=(\d+) unit=(\S*) order=\[(.*)\] served=(\S*)$")
TRIAGE_ITEM_RE = re.compile(r"(\S+?)\(T=([^,]+),c=([^,]+),([PD])\)")
VDEAD_RE = re.compile(r"^\[RescueEvent\] type=victim_dead victim=(\S+)")
ROW_KINDS = ("rows_ff", "rows_vic", "rows_uav", "rows_dec", "rows_trig")
MV_COLS = ("step", "unit", "victim", "leg", "branch", "pre", "post", "target", "digest",
           "st_pre", "st_post", "tier", "mt", "rb_call", "rb_set",
           "trig", "zrb", "today", "fa", "fb", "fbB", "fc", "acted",
           "dc", "dcx", "df", "dm", "dr", "gesc",
           "cls_pre", "cls_post", "fd_pre", "fd_post", "c1_pre", "c1_post",
           "fix_ms", "inst_ms")
MV_EXTRA_V2 = ("dcb",)                     # v2: the clean distance to the boundary on every row (R3 D-16)
SHADOW_FIELDS = ("step", "unit", "victim", "leg", "pre", "target", "digest", "st_pre", "trig", "zrb", "today", "fa",
                 "fb", "fbB", "fc", "acted", "dc", "dcx", "df", "dm", "dr", "gesc", "cls_pre", "fd_pre", "c1_pre")
KICK_SHADOW = ("step", "phase", "site", "W", "F", "index", "qualifies", "u1", "rec", "d", "nB", "z4", "div_shadow",
               "acc", "index_wb", "u1_wb", "div_shadow_head")      # the pre-bind (kick-entry) fields; v1: absent
FIX_BRANCHES = ("approach_a", "retreat_b", "c1", "c2", "c2s", "c3")
EXCLUDED_CARRY = ("c2s", "c3")             # 22.8.3 designed-behaviour exclusion (C-2 stay, C-3 hold)
I2_KINDS = (("stuck_approach", "I2_ff_stuck_approach"), ("stuck_carry", "I2_ff_stuck_carry"),
            ("livelock_approach", "I2_ff_livelock_approach"), ("livelock_carry", "I2_ff_livelock_carry"),
            ("noprog_approach", "I2_ff_no_progress_approach"))
# 23.2: the 24 sign-tested counts, family order (F2, F3, F4 x 7, F5 x 13, F6, F8)
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
    ("of_stuck_carry", "F5 I2 STUCK carry (excl. C-2 stay / C-3 hold)"),
    ("of_livelock_approach", "F5 I2 LIVELOCK approach"),
    ("of_livelock_carry", "F5 I2 LIVELOCK carry"),
    ("of_noprog_approach", "F5 I2 NO-PROGRESS approach"),
    ("leg_cycle_approach", "F5 CYCLE approach (legs)"),
    ("leg_cycle_carry", "F5 CYCLE carry (legs)"),
    ("leg_osc_approach", "F5 OSCILLATION approach (legs)"),
    ("leg_osc_carry", "F5 OSCILLATION carry (legs)"),
    ("leg_prog_approach", "F5 PROGRESS approach (legs)"),
    ("leg_prog_carry", "F5 PROGRESS carry (legs, excl.)"),
    ("leg_noprog_carry", "F5 carry NO-PROGRESS (legs, excl.)"),
    ("latch_episodes", "F6 latch episodes"),
    ("escape_writeoffs_det", "F8 escape-sweep write-offs of detected victims"),
)
assert len(SIGN_KEYS) == 24
U1_ZEROS = ("Z1", "Z2", "Z3", "Z4", "Z7", "Z8")
MOV_ZEROS = ("Z1-M", "Z2-M", "Z-RB", "Zm-a", "Zm-b", "Zm-c", "Z-S")
SHARED_ZEROS = ("Z5", "Z6")

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


# ================================================================================================ small helpers (new)
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


def compare_counts(nx, ny, cell_set, diverged, fresh=FRESH):
    """23.2 on one comparison X -> Y. nx / ny: {cell: num dict}; cell_set {cell: set}; diverged: cells whose Y run is
    not value-identical to the X run. Literal L1 (ff_deaths pooled + each fresh set, Y <= X), L2 (rescued each fresh
    set, Y >= X), L3 (DD pooled, Y <= X); the 24 SIGN_KEYS by the exact sign test over the diverged cells with Holm.
    Returns the full result (S4 = L2 and L3; S5 = no literal fails and no sign-tested count rejected)."""
    cells = sorted(set(nx) & set(ny))
    tot = lambda nd, k, sel=None: sum(int(nd[c].get(k, 0) or 0) for c in cells     # noqa: E731
                                      if sel is None or cell_set[c] == sel)
    lit = collections.OrderedDict()
    lit["L1 ff deaths pooled"] = (tot(nx, "ff_deaths"), tot(ny, "ff_deaths"), "le")
    for s in fresh:
        lit["L1 ff deaths %s" % s] = (tot(nx, "ff_deaths", s), tot(ny, "ff_deaths", s), "le")
    for s in fresh:
        lit["L2 rescued %s" % s] = (tot(nx, "rescued", s), tot(ny, "rescued", s), "ge")
    lit["L3 DD pooled"] = (tot(nx, "DD"), tot(ny, "DD"), "le")
    literal = collections.OrderedDict()
    for k, (x, y, rel) in lit.items():
        literal[k] = {"x": x, "y": y, "fail": (y > x) if rel == "le" else (y < x)}
    div = [c for c in cells if c in diverged]
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
    return {"cells": len(cells), "diverged": len(div), "literal": literal, "sign": sign, "lit_fail": lit_fail,
            "sig_fail": sig_fail, "S4": s4, "S5": not lit_fail and not sig_fail}


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


def rmu_verdict(full_0_mu, harmless_m_mu, harmless_u_mu):
    """R-MU = FULL(0 -> MU) AND HARMLESS(M -> MU) AND HARMLESS(U -> MU)."""
    if full_0_mu in ("STOP", "FAIL"):
        return full_0_mu
    if not (harmless_m_mu and harmless_u_mu):
        return "FAIL"
    return full_0_mu


OUTCOME_TEXT = {
    1: "Any arm-0 failure: STOP (22.8.2) - a base or instrument defect; fixed, then the wave is re-run. No outcome "
       "is read.",
    2: "R-M, R-U and R-MU all hold: recommend both, then STOP for the maintainer's confirmation.",
    3: "R-M and R-U hold but R-MU fails: STOP for a ruling. Pre-registered default: ship the single arm with the "
       "larger pooled DD reduction; on a tie, M.",
    4: "R-M only: recommend movement (per switch). U1's verdict per 17.3 decides only whether its code merges at 0.",
    5: "R-U only: recommend U1. The movement code merges at 0 only if its verdict is NOT SHOWN.",
    6: "Neither: both ship 0, whatever MU shows. An MU-only pass is reported, never shipped.",
}


def decide(arm0_stop, rm, ru, rmu, dd_red_m=0, dd_red_u=0):
    """22.8.5 outcomes 1-6, applied in order. rm / ru / rmu are verdict strings ('PASS' = holds).
    Returns (outcome, default arm for outcome 3 or None)."""
    if arm0_stop:
        return 1, None
    m, u, mu = rm == "PASS", ru == "PASS", rmu == "PASS"
    if m and u and mu:
        return 2, None
    if m and u:
        return 3, ("M" if dd_red_m >= dd_red_u else "U")
    if m:
        return 4, None
    if u:
        return 5, None
    return 6, None


def movement_switch_verdicts(outcome, default_arm, rm, rmu, zm_ok, acted):
    """22.8.5 PER MOVEMENT SWITCH: k ships ON only if R-M passes (and R-MU if both are to ship), Zm-k holds, and fix k
    ACTED in >= 1 fresh cell of EACH seed set; a switch that did not act in both sets is NOT MEASURED (ships 0; its
    code may merge at 0). acted {k: {set: cells}}, zm_ok {k: bool}."""
    res = {}
    both_ship = outcome == 2
    movement_recommended = outcome in (2, 4) or (outcome == 3 and default_arm == "M")
    for k in ("a", "b", "c"):
        sets = acted.get(k) or {}
        if not all(int(sets.get(s, 0) or 0) >= 1 for s in FRESH):
            res[k] = "NOT MEASURED (did not act in both fresh sets: %s) - ships 0; its code may merge at 0" % (
                {s: int(sets.get(s, 0) or 0) for s in FRESH})
        elif rm != "PASS":
            res[k] = "ships 0 (R-M %s)" % rm
        elif not zm_ok.get(k, False):
            res[k] = "ships 0 (Zm-%s fails)" % k
        elif both_ship and rmu != "PASS":
            res[k] = "ships 0 (R-MU %s while both are to ship)" % rmu
        elif outcome == 1:
            res[k] = "STOP (arm-0 failure)"
        elif movement_recommended:
            res[k] = "ON - recommended (R-M PASS, Zm-%s holds, acted in both sets); STOP for confirmation" % k
        elif outcome == 3:
            res[k] = "ships 0 under the outcome-3 default (U); STOP for a ruling"
        else:
            res[k] = "ships 0 (outcome %d)" % outcome
    return res


# ================================================================================================ zeros (pure)
def z2_u1(cmds, cmd_ctx, rels, rel_ctx):
    """Z2: unbinds, releases and write-offs issued from U1 code (call-site context 'u1pass'): 0."""
    bad = [["command"] + list(c[:7]) for c, ctx in zip(cmds or (), cmd_ctx or ())
           if c[2] != "assign" and "u1pass" in (ctx or ())]
    bad += [["release"] + list(r[:5]) for r, ctx in zip(rels or (), rel_ctx or ()) if "u1pass" in (ctx or ())]
    return bad


def z2_mov(cmds, cmd_ctx, rels, rel_ctx):
    """Z2-M: assign, unassign, release or mark_unreachable commands issued from movement code ('fix:' context): 0."""
    fx = lambda ctx: any(str(x).startswith("fix:") for x in (ctx or ()))           # noqa: E731
    bad = [["command"] + list(c[:7]) for c, ctx in zip(cmds or (), cmd_ctx or ()) if fx(ctx)]
    bad += [["release"] + list(r[:5]) for r, ctx in zip(rels or (), rel_ctx or ()) if fx(ctx)]
    return bad


def _subsequence(xs, ys):
    it = iter(ys)
    return all(any(x == y for y in it) for x in xs)


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


def z3_kicks(kicks):
    """Z3 at every NON-qualifying kick of a run with DISPATCH_URGENCY on: the binds are the index-order loop's - the
    ordering function was not entered (no model ms, no triage line); the dispatch ATTEMPTS (v2 K['attempts'], in call
    order) visit the victims in K['index'] order (restricted to the attempted victims, each once); the binds equal the
    accepted attempts (the same victims, in the same order); the bound units are distinct free units (and THE free unit
    when |F| = 1). A v1 record (no attempts) is checked by the bound victims being a subsequence of the index order."""
    bad = []
    for K in kicks or ():
        if K.get("qualifies") or K.get("W") is None:
            continue
        bound = K.get("bound") or []
        fids = [f[0] for f in K.get("F") or []]
        why = []
        if K.get("ms_model") is not None or K.get("triage") is not None:
            why.append("ordering function entered at a non-qualifying kick")
        index = list(K.get("index") or [])
        if "attempts" in K:
            att = [a[0] for a in K.get("attempts") or []]
            if att != [v for v in index if v in set(att)]:
                why.append("attempts %s not in index order %s" % (att, index))
            ok = [a[0] for a in K.get("attempts") or [] if a[1]]
            if [b[0] for b in bound] != ok:
                why.append("bound victims %s != the accepted attempts %s" % ([b[0] for b in bound], ok))
        elif not _subsequence([b[0] for b in bound], index):
            why.append("bound victims %s not in index order %s" % ([b[0] for b in bound], index))
        units = [b[1] for b in bound]
        if len(set(units)) != len(units) or any(u not in fids for u in units):
            why.append("bound units %s not distinct free units %s" % (units, fids))
        elif len(fids) == 1 and units and units[0] != fids[0]:
            why.append("bound unit %s is not the free unit %s" % (units[0], fids[0]))
        if why:
            bad.append([K.get("step"), K.get("i"), "; ".join(why)])
    return bad


def parse_triage(line):
    """[UrgencyTriage] line -> (step, unit, [(vid, T or inf, c or None, P bool)], served) or None."""
    m = TRIAGE_RE.match(str(line or "").strip())
    if not m:
        return None
    items = []
    for vid, t, c, p in TRIAGE_ITEM_RE.findall(m.group(3)):
        items.append((vid, float("inf") if t == "inf" else float(t), None if c == "inf" else int(c), p == "P"))
    return int(m.group(1)), m.group(2), items, m.group(4)


def z4_kicks(kicks, on):
    """Z4 at every qualifying kick: no promotion without a finite safe-in-time route or with c + 1 > T (both ways: the
    verdict follows the rule); the instrument's independent recomputation (z4) agrees with the logged record; ON:
    the [UrgencyTriage] line agrees with the record and the U1 order (T to 0.1, c, P/D, served)."""
    bad = []
    for K in kicks or ():
        if not K.get("qualifies"):
            continue
        rec = K.get("rec") or {}
        for vid, r3 in rec.items():
            T, c, P = r3[0], r3[1], bool(r3[2])
            rule = c is not None and (T is None or c + 1 <= T)
            if P != rule:
                bad.append([K.get("step"), vid, "verdict %s but the rule gives %s (T %s, c %s)" % (P, rule, T, c)])
        if K.get("z4_ok") is not True:
            bad.append([K.get("step"), None, "independent recomputation disagrees: rec %s z4 %s" % (rec, K.get("z4"))])
        if on:
            tr = parse_triage(K.get("triage"))
            if tr is None:
                bad.append([K.get("step"), None, "no [UrgencyTriage] line at a qualifying ON kick"])
                continue
            if [x[0] for x in tr[2]] != list(K.get("u1") or []):
                bad.append([K.get("step"), None, "triage order %s != U1 order %s" % ([x[0] for x in tr[2]],
                                                                                    K.get("u1"))])
            for vid, t, c, p in tr[2]:
                r3 = rec.get(vid)
                if r3 is None:
                    bad.append([K.get("step"), vid, "triage victim not in the record"])
                    continue
                t_rec = float("inf") if r3[0] is None else float(r3[0])
                t_ok = (math.isinf(t) and math.isinf(t_rec)) or (not math.isinf(t_rec) and abs(t - t_rec) <= 0.05 + 1e-9)
                if not t_ok or c != r3[1] or p != bool(r3[2]):
                    bad.append([K.get("step"), vid, "triage (T %s, c %s, %s) != record %s" % (t, c, "P" if p else "D",
                                                                                         r3)])
    return bad


def z7_kicks(kicks):
    """Z7: at every qualifying kick (switch on) exactly one victim is bound - the first of its order - to the unit f."""
    bad = []
    for K in kicks or ():
        if not K.get("qualifies"):
            continue
        bound = K.get("bound") or []
        f = (K.get("F") or [[None]])[0][0]
        u1 = K.get("u1") or []
        tr = parse_triage(K.get("triage"))
        why = []
        if len(bound) != 1:
            why.append("%d binds" % len(bound))
        else:
            if not u1 or bound[0][0] != u1[0]:
                why.append("bound %s is not the first of the order %s" % (bound[0][0], u1))
            if bound[0][1] != f:
                why.append("bound unit %s is not f %s" % (bound[0][1], f))
            if tr is not None and tr[3] != bound[0][0]:
                why.append("triage served %s != bound %s" % (tr[3], bound[0][0]))
        if why:
            bad.append([K.get("step"), K.get("i"), "; ".join(why)])
    return bad


def z7_acc_kicks(kicks):
    """Z7-ACC (R3 D-24's reading, REPORTED unless Z7_READING = 'acc'): at every qualifying kick (switch on) U binds
    u1_wb - the first victim of its order the planner accepts - to the unit f, and nothing when u1_wb is None; the
    triage line serves that victim ('none' when None). Needs v2's u1_wb (a v1 record is not checked)."""
    bad = []
    for K in kicks or ():
        if not K.get("qualifies") or "u1_wb" not in K:
            continue
        bound = K.get("bound") or []
        f = (K.get("F") or [[None]])[0][0]
        want = K.get("u1_wb")
        why = []
        if want is None:
            if bound:
                why.append("%d binds although no victim of the order is accepted" % len(bound))
        elif [list(b) for b in bound] != [[want, f]]:
            why.append("bound %s != [[%s, %s]] (the first accepted victim of the order, to f)" % (bound, want, f))
        tr = parse_triage(K.get("triage"))
        if tr is not None and tr[3] != ("none" if want is None else want):
            why.append("triage served %s != %s" % (tr[3], "none" if want is None else want))
        if why:
            bad.append([K.get("step"), K.get("i"), "; ".join(why)])
    return bad


def z7_readings(kicks, reading=None):
    """Both Z7 readings of one run: {'reading', 'gate': the violations of the reading that GATES (Z7_READING), 'reported':
    the other reading's}."""
    reading = reading or Z7_READING
    lit, acc = z7_kicks(kicks), z7_acc_kicks(kicks)
    return {"reading": reading, "gate": lit if reading == "literal" else acc,
            "reported": acc if reading == "literal" else lit}


def z8_kicks(kicks):
    """Z8: binds per kick equal the index-order counterfactual's count. At a qualifying kick (|F| = 1) the index loop
    binds index_wb - the first victim of the index order the planner accepts - so the count is 1 if index_wb is not
    None, else 0 (a v1 record: 1). At a non-qualifying kick U runs the index loop itself: its count is that of the
    accepted dispatch attempts (v2 K['attempts']); always at most min(|W|, |F|)."""
    bad = []
    for K in kicks or ():
        if K.get("W") is None:
            continue
        nb = len(K.get("bound") or [])
        if K.get("qualifies"):
            cf = (0 if K.get("index_wb") is None else 1) if "index_wb" in K else 1
            if nb != cf:
                bad.append([K.get("step"), K.get("i"), "qualifying kick bound %d (counterfactual %d)" % (nb, cf)])
        else:
            if "attempts" in K:
                cf = sum(1 for a in K.get("attempts") or [] if a[1])
                if nb != cf:
                    bad.append([K.get("step"), K.get("i"), "bound %d != accepted attempts %d" % (nb, cf)])
            if nb > min(len(K.get("W") or []), len(K.get("F") or [])):
                bad.append([K.get("step"), K.get("i"), "bound %d > min(|W|, |F|)" % nb])
    return bad


def lemma2_offarm(kicks):
    """Reported in arms with the switch off: qualifying kicks (shadow) whose bind count differs from the index loop's
    counterfactual (1 if index_wb is not None, else 0; v1: 1)."""
    res = []
    for K in kicks or ():
        if not K.get("qualifies"):
            continue
        cf = (0 if K.get("index_wb") is None else 1) if "index_wb" in K else 1
        if len(K.get("bound") or []) != cf:
            res.append([K.get("step"), K.get("i"), len(K.get("bound") or []), cf])
    return res


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


def custody_at(ffs, step, vid):
    """Units exiting with `vid` (alive) in the rows_ff row of `step`."""
    return [u for u, r in (ffs.get(step) or {}).items() if r[5] and r[8] == vid and not r[6]]


def zm_c(rows, cmds, ffs, vdead, vdead_events):
    """Zm-c: 0 drops (an unassign of the route_blocked pathway - reason replacement_after_blocked - to a unit exiting on
    the previous row; casualty and rescue-completion unassigns are excluded and reported); 0 dispatches to a victim in
    custody; at most one victim_dead per victim who died in custody; every C-1 step on a non-burning cell with its cost
    falling (hazard components not rising, length - 1) on its decision board; no carry cycle on an equal digest.
    Returns (violations, excluded unassigns reported)."""
    bad, excluded = [], []
    for c in cmds or ():
        step, phase, action, vid, uid, reason, ok = c[:7]
        if action != "unassign" or not ok:
            continue
        prev = (ffs.get(step - 1) or {}).get(uid)
        if prev is None or not prev[5]:
            continue
        reason = str(reason or "")
        if "replacement" in reason and "blocked" in reason:
            bad.append([step, uid, "DROP of %s (%s, %s)" % (vid, reason, phase)])
        else:
            excluded.append([step, uid, vid, reason])
    for c in cmds or ():
        step, phase, action, vid, uid, reason, ok = c[:7]
        if action != "assign" or not ok:
            continue
        keep = [u for u in custody_at(ffs, step - 1, vid) if u != uid and u in custody_at(ffs, step, vid)]
        if keep:
            bad.append([step, uid, "dispatch to %s in custody of %s (%s)" % (vid, keep, reason)])
    for vid, dstep in (vdead or {}).items():
        if custody_at(ffs, dstep - 1, vid) and int(vdead_events.get(vid, 0)) > 1:
            bad.append([dstep, None, "%d victim_dead events for %s, who died in custody" % (vdead_events[vid], vid)])
    for r in rows:
        if r.get("branch") != "c1":
            continue
        a, b = r.get("c1_pre"), r.get("c1_post")
        if r.get("cls_post") == "B":
            bad.append([r["step"], r["unit"], "C-1 step onto a burning cell"])
        if a is None or b is None or not (b[0] <= a[0] and b[1] <= a[1] and b[2] == a[2] - 1):
            bad.append([r["step"], r["unit"], "C-1 cost %s -> %s does not fall" % (a, b)])
    for _u, rs in unit_rows(rows).items():
        run = []
        for r in rs + [None]:
            if (r is not None and r["leg"] == "carry" and run and r["step"] == run[-1]["step"] + 1
                    and r.get("digest") == run[-1].get("digest") and r.get("victim") == run[-1].get("victim")):
                run.append(r)
                continue
            if len(run) >= 2:
                frames = [x["pre"] for x in run] + ([run[-1]["post"]] if run[-1].get("post") is not None else [])
                col = collapse([f for f in frames if f is not None])
                if len(col) != len(set(col)):
                    bad.append([run[0]["step"], run[0]["unit"], "carry cycle on an equal digest, steps %d-%d" % (
                        run[0]["step"], run[-1]["step"])])
            run = [r] if (r is not None and r["leg"] == "carry") else []
    return bad, excluded


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


# ================================================================================================ counts (pure)
def mv_dicts(d):
    """d["mv"] rows as dicts (cells as tuples) and the column list."""
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


def shadow_mismatch_zeros(rows, mv_events, arm0):
    """Route ud.shadow_mismatch (coordinator ruling on 16.6: behaviour, never INVALID) and every live ACTED event that
    disagrees with the model (mv_events agree False) to the structural zeros. Returns {zero: [instance, ...]}:
    - arm 0 / E0: every row -> 'SM' (impossible by construction; any one is a STOP, 22.8.2 'ANY failure in ARM 0');
    - otherwise a KICK bind row ([step, unit, 'u1' | 'index', 'kick bind differs from the acc shadow', 'kick:<i>',
      expected, bound]) -> 'Z7' (U1-owned; listed under BOTH Z7 readings by the caller); a MOVEMENT row ([step, unit,
      'a' | 'b' | 'c', text, branch, ...]) or a live ACTED disagreement not already in a row -> 'Z1-M' (item (v):
      the live action equals the pre-advance shadow; movement-owned); any other row -> 'SM' (reported)."""
    kick, mov, other, seen = [], [], [], set()
    for r in rows or ():
        r = list(r)
        if (len(r) > 4 and str(r[4]).startswith("kick:")) or (len(r) > 3 and "kick" in str(r[3])):
            kick.append(["kick bind != the acc shadow"] + r)
        elif len(r) > 2 and r[2] in ("a", "b", "c"):
            mov.append(["(v) live action != the pre-advance shadow"] + r)
            seen.add((r[0], r[1], r[2]))
        else:
            other.append(["shadow_mismatch of unknown kind"] + r)
    for e in mv_events or ():
        if e.get("live") and e.get("agree") is False and (e.get("step"), e.get("unit"), e.get("kind")) not in seen:
            mov.append(["(v) live ACTED event disagrees with the model", e.get("step"), e.get("unit"), e.get("kind"),
                        e.get("branch"), e.get("cell"), e.get("taken")])
    if arm0:
        allr = kick + mov + other
        return {"SM": allr} if allr else {}
    res = {}
    for k, v in (("Z7", kick), ("Z1-M", mov), ("SM", other)):
        if v:
            res[k] = v
    return res


def merge_mismatch(Z, z7_other, smz):
    """Add shadow_mismatch_zeros' instances to a run's zeros: 'Z7' instances join BOTH the gating Z7 list and the
    reported other-reading list (a kick bind mismatch fails Z7 whichever reading gates). Returns the new z7_other."""
    z7_other = list(z7_other or [])
    for zk, items in smz.items():
        Z.setdefault(zk, []).extend(items)
        if zk == "Z7":
            z7_other += items
    return z7_other


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


def show_blob(commit, rel):
    rc, blob = git("show", "%s:%s" % (commit, rel))
    return blob.decode("utf-8", "replace") if rc == 0 else None


def hash_checks(current_text=None):
    """16.6 / 22.6.3 / 23.3: each hashed section of the working outputs/urgency_part1.txt equals its reference commit's.
    Returns (ok, lines)."""
    lines, ok = [], True
    if current_text is None:
        try:
            with open(os.path.join(HERE, "urgency_part1.txt"), encoding="utf-8") as fh:
                current_text = fh.read()
        except OSError as exc:
            return False, ["urgency_part1.txt unreadable: %r" % (exc,)]
    blobs = {}
    for name, commit, start, end in HASHED:
        if commit not in blobs:
            blobs[commit] = show_blob(commit, "outputs/urgency_part1.txt")
        ref = extract_section(blobs[commit], start, end) if blobs[commit] else None
        cur = extract_section(current_text, start, end)
        same = ref is not None and cur is not None and ref == cur
        ok = ok and same
        lines.append("  section %-10s vs %s: %s (sha256 %s, %d lines)" % (
            name, commit, "identical" if same else "DIFFERS (or unreadable)",
            hashlib.sha256((cur or "").encode()).hexdigest()[:16], (cur or "").count("\n") + 1))
    b1 = show_blob(PART1B, "outputs/urgency_part1.txt")
    for name, commit, start, end in HASHED:
        if commit == B2 and name != "23" and b1:
            same = extract_section(b1, start, end) == extract_section(blobs.get(B2) or "", start, end)
            lines.append("  info: section %s at %s %s %s's" % (name, PART1B, "==" if same else "WARNING != ", B2))
    return ok, lines


def verbatim_check():
    """Each DPR function replicated here is a verbatim substring of _dp_analyze.py at cc8d653c (LF)."""
    blob = show_blob(DISPATCH, "outputs/_dp_analyze.py")
    if blob is None:
        return False, ["cannot read dispatch:outputs/_dp_analyze.py at %s" % DISPATCH[:8]]
    blob = lf(blob)
    bad = [n for n in DP_VERBATIM if lf(inspect.getsource(globals()[n])) not in blob]
    return not bad, ["  %d DPR functions verbatim from %s: %s" % (len(DP_VERBATIM) - len(bad), DISPATCH[:8],
                                                                   "all" if not bad else "DIFFER: %s" % bad)]


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


def load_seeds():
    """outputs/_ud_seeds.txt with the 16.2 rule RECOMPUTED (seed = base + 4*s + w); STOP (None) on any mismatch.
    Sets 1-2 must also equal the fx3mS / fx3mS2 argv cells (_fb3_queue.cells). It never scans for seeds."""
    try:
        doc = load_json(os.path.join(HERE, "_ud_seeds.txt"))
    except Exception as exc:                 # noqa: BLE001
        out("STOP: outputs/_ud_seeds.txt unreadable (%r)" % (exc,))
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
    if bad:
        out("STOP: outputs/_ud_seeds.txt: %s" % bad[:6])
        return None
    out("  frozen cells outputs/_ud_seeds.txt: rule recomputed for sets 1-4 (bases %s) - identical, 64 distinct "
        "seeds" % EXPECTED_BASES)
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
    head("URGENCY ROUND - PART 3 ANALYZER (outputs/urgency_part1.txt 16.5-16.11, 17.2 S3, 22.5-22.9; amendment B2 "
         "section 23: literal L1-L3 + one-sided sign test with Holm)")
    if opts.smoke:
        out("SMOKE - NOT A SCREEN (one cell from %s; queue / 360-step / head checks relaxed; the cell stands in for "
            "the fresh set 3)" % opts.smoke)
    for c, what in ((PART1, "Part 1 (U1 design + screen)"), (PART1B, "Part 1b (amendment B1)"),
                    (B2, "amendment B2 (rulings on 22.10)")):
        rc, txt = git("log", "-1", "--format=%H %ad %s", "--date=short", c)
        out("%-34s %s  %s" % (what + ":", c, txt.decode("utf-8", "replace").strip()[:110] if rc == 0 else "NOT FOUND"))
    rc, hd = git("rev-parse", "HEAD")
    out("%-34s %s" % ("analyzer worktree HEAD:", hd.decode().strip() if rc == 0 else "?"))
    if opts.head:
        rc, txt = git("log", "-1", "--format=%H %ad %s", "--date=short", opts.head)
        anc, _ = git("merge-base", "--is-ancestor", B2, opts.head)
        out("%-34s %s  %s | descends from B2: %s" % ("Part 2 commit (--head):", opts.head,
                                                      txt.decode("utf-8", "replace").strip()[:80] if rc == 0
                                                      else "NOT FOUND", "yes" if anc == 0 else "NO"))
        if anc != 0:
            out("REFUSED: --head %s does not descend from the B2 amendment %s" % (opts.head, B2))
            return False
    ok, lines = hash_checks()
    for ln in lines:
        out(ln)
    if not ok:
        out("REFUSED: a hashed section of outputs/urgency_part1.txt differs from its committed text (16.6, 22.6.3, "
            "23.3) - no edit of a pre-registered rule after data")
        return False
    vok, lines = verbatim_check()
    mok, mlines = module_check()
    for ln in lines + mlines:
        out(ln)
    if not (vok and mok):
        out("REFUSED: a reused DPR function or module is not the committed one (16.6)")
        return False
    if opts.part2_notes:
        nok, lines = notes_check(opts.part2_notes)
        for ln in lines:
            out(ln)
        if not nok:
            out("REFUSED: a tooling file or frozen queue differs from the Part 2 notes (15.5)")
            return False
    else:
        out("  Part 2 notes: NOT CHECKED (smoke)")
    return True


# ================================================================================================ 1 LOAD + PROV
def screen_cells(frozen, opts):
    cells = []
    for k in (1, 2, 3, 4):
        for p, plc, mode in PLACES:
            for key, scen, wind, seed in frozen["set%d" % k]:
                cells.append({"id": "set%d/%s/%s" % (k, plc, key), "set": "set%d" % k, "k": k, "plc": plc, "p": p,
                              "mode": mode, "key": key, "scen": scen, "wind": wind, "seed": int(seed),
                              "fresh": k >= 3, "arms": ARMS if k >= 3 else ("0", "U")})
    if opts.smoke:
        cells = [dict(c, set="set3", fresh=True, arms=ARMS) for c in cells if c["id"] == opts.smoke_cell]
    return cells


def run_path(arm, cell, opts):
    if opts.smoke:
        f = opts.smoke_files.get(arm)
        return os.path.join(opts.smoke, f) if f else os.path.join(opts.smoke, "__missing_%s__.json" % arm)
    return os.path.join(HERE, "_sd_%s%s%d_%s.json" % (ARM_TAG[arm], cell["p"], cell["k"], cell["key"]))


def ref_path(cell, opts):
    if opts.smoke:
        f = opts.smoke_files.get("ref")
        return os.path.join(opts.smoke, f) if f else None
    if cell["k"] > 2:
        return None
    return os.path.join(HERE, "_ud_dpR", "_sd_%s_%s.json" % (DPR_TAGS[(cell["k"], cell["p"])], cell["key"]))


def load_queues():
    """{normcase(out): (wave, line)} over the FROZEN queues outputs/_ud_q_w{1,2,3,4}.jsonl."""
    idx = {}
    for wave in ("w1", "w2", "w3", "w4"):
        p = os.path.join(HERE, "_ud_q_%s.jsonl" % wave)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip():
                    line = json.loads(ln)
                    idx[os.path.normcase(line["out"])] = (wave, line)
    return idx


def expected_switches(line_sets):
    return {"DISPATCH_URGENCY": line_sets.get("DISPATCH_URGENCY") == 1,
            "FF_APPROACH_PATH": line_sets.get("FF_APPROACH_PATH") == 1,
            "FF_RETREAT_KEEP_APPROACH": line_sets.get("FF_RETREAT_KEEP_APPROACH") == 1,
            "FF_CARRY_REPLAN": line_sets.get("FF_CARRY_REPLAN") == 1}


UD_SRC_REQUIRED = ("src_extension/planning/urgency_dispatch.py", "src_extension/planning/movement_paths.py",
                   "src_extension/planning/fire_arrival_estimate.py", "agents.py", "wildfire_model.py",
                   "common_fixed_variables.py")
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
    """R2 M-2 (15.1, 16.6): every source sha the run recorded (ud.src_sha and dp.src_sha) equals the file at --head (its
    LF or CRLF form), and ud.src_sha names every UD_SRC_REQUIRED file. A mismatch means the run executed source that is
    not the committed one: INVALID. Returns the reasons."""
    why = []
    for sec in ("ud", "dp"):
        shas = (d.get(sec) or {}).get("src_sha") if isinstance(d.get(sec), dict) else None
        if not isinstance(shas, dict) or not shas:
            why.append("ran uncommitted source? %s.src_sha not recorded" % sec)
            continue
        if sec == "ud":
            miss = [r for r in UD_SRC_REQUIRED if r not in shas]
            if miss:
                why.append("ud.src_sha does not name %s" % miss)
        bad = [rel for rel, sha in sorted(shas.items()) if sha not in (committed_shas(head, rel) or ())]
        if bad:
            why.append("ran uncommitted source: %s.src_sha differs from %s for %s" % (sec, head[:10], bad[:4]))
    return why


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


def prov_run(d, path, line, cell, opts):
    """16.6 validity of one probe run: (INVALID reasons, crash text or None, STOP reason or None). A crashed run
    (crash flag, chain exit code != 0, or an early stop) is Z6 material - a GATE FAILURE in U / M / MU, a STOP in arm 0
    - so the CRN-draw and stdout reasons a crash itself causes are NOT added (R2 m-1: it is never re-run as INVALID)."""
    why, stop = [], None
    if d.get("dp_only"):
        return ["the chain wrote no sd JSON"] if not isinstance(d.get("dp"), dict) else [], \
            "no sd record (dp_only - crashed)", None
    argv_l = (line or {}).get("argv") or []
    sd_argv = argv_l[argv_l.index("--") + 1:] if "--" in argv_l else []
    sets = parse_sets(sd_argv) if line else dict(d.get("extra_params") or {})
    crashed_run = bool(d.get("crashed")) or ((d.get("dp") or {}).get("rc_chain") not in (0, None))
    exp_steps = d.get("steps") if opts.smoke else int(arg_of(sd_argv, "--steps") or H)
    crash = run_crash(d, exp_steps)
    if not opts.smoke:
        if line is None:
            why.append("no line in the frozen queues outputs/_ud_q_w1..w4.jsonl")
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
        if opts.head and not str(d.get("head") or "").startswith(opts.head):
            why.append("head %s != %s" % (str(d.get("head"))[:10], opts.head))
    if opts.head:
        why += src_check(d, opts.head)
    if d.get("extra_params") != sets:
        why.append("extra_params %s != the queue line's %s" % (json.dumps(d.get("extra_params"), sort_keys=True),
                                                              json.dumps(sets, sort_keys=True)))
    crn = (d.get("fb3") or {}).get("crn") or {}
    want_crn = ("--crn" in argv_l) if line else True
    if crash is None and want_crn and not (crn.get("on") and int(crn.get("crn_draws") or 0) > 0):
        why.append("CRN on %s with crn_draws %s (16.4: 0 draws is INVALID)" % (crn.get("on"), crn.get("crn_draws")))
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
    ud = d.get("ud")
    if not isinstance(ud, dict):
        why.append("ud section missing")
    else:
        if ud.get("probe") != UD_PROBE and not (opts.smoke and ud.get("probe") in UD_PROBE_SMOKE_OK):
            why.append("ud.probe %r (the screen reads %r records only)" % (ud.get("probe"), UD_PROBE))
        if ud.get("errors"):
            why.append("instrument errors ud.errors %s" % ud["errors"][:2])
        # ud.shadow_mismatch is NOT an instrument error (coordinator ruling on 16.6): it is the model disagreeing with
        # its own pure shadow - behaviour, routed to the structural zeros by shadow_mismatch_zeros (Z7 / Z1-M / SM)
        sw = ud.get("switches") or {}
        want = expected_switches(sets)
        got = {k: bool(sw.get(k)) for k in want}
        if got != want:
            why.append("effective switches %s != the line's %s" % (got, want))
        if want["FF_CARRY_REPLAN"] and (sw.get("FF_EXIT_LEG_MODE") != 2 or sw.get("FF_EXIT_LEG_SERVED") != 1):
            why.append("FF_CARRY_REPLAN requested with MODE %s SERVED %s" % (sw.get("FF_EXIT_LEG_MODE"),
                                                                           sw.get("FF_EXIT_LEG_SERVED")))
        if isinstance(dp, dict):
            if len(ud.get("cmd_ctx") or []) != len(dp.get("commands") or []):
                why.append("ud.cmd_ctx not aligned with dp.commands")
            if len(ud.get("rel_ctx") or []) != len(dp.get("releases") or []):
                why.append("ud.rel_ctx not aligned with dp.releases")
    mv = d.get("mv")
    cols = list(mv.get("cols") or ()) if isinstance(mv, dict) else []
    want_cols = set(MV_COLS) | (set(MV_EXTRA_V2) if (ud or {}).get("probe") == UD_PROBE else set())
    if not isinstance(mv, dict) or len(cols) != len(set(cols)) or set(cols) != want_cols:
        why.append("d['mv'] missing or its columns differ from the instrument's schema")
    # a live ACTED event disagreeing with the model is behaviour too: Z1-M item (v), not INVALID (ruling on 16.6)
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


def prov_harness(d, path, line, opts):
    """Validity of the case-1 harness record (no head field is recorded by the harness)."""
    why = []
    if line is None and not opts.smoke:
        return ["no line in the frozen queues"], None
    argv_l = (line or {}).get("argv") or []
    sets = parse_sets(argv_l)
    if not opts.smoke:
        if not same_path(d.get("repo"), WT):
            why.append("repo %s" % d.get("repo"))
        try:
            with open(path + ".argv", encoding="utf-8") as fh:
                if fh.read() != POOL.signature(line):
                    why.append(".argv signature differs from the queue line")
        except OSError:
            why.append("no .argv")
    if d.get("extra_params") != sets:
        why.append("extra_params %s != %s" % (d.get("extra_params"), sets))
    if sets.get("FM2P_CRN") == 1 and not int(((d.get("fm2p") or {}).get("counters") or {}).get("crn_draws") or 0):
        why.append("CRN-on harness with 0 crn_draws")
    crash = None
    if d.get("terminal_step") is None and d.get("steps") != H:
        crash = "harness stopped early (steps %s)" % d.get("steps")
    return why, crash


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
    """Everything later sections read from one probe run, computed once (the run dict is dropped afterwards).
    censor: M1c's censoring step (361 = H + 1; in smoke mode the run's own last step + 1, as DPR's censor())."""
    g = {"arm": arm, "label": label, "path": path, "set": cell_set, "dp_only": bool(d.get("dp_only")),
         "crashed": d.get("crashed"), "censor": censor, "horizon": censor - 1}
    dp = d.get("dp") if isinstance(d.get("dp"), dict) else {}
    ud = d.get("ud") if isinstance(d.get("ud"), dict) else {}
    sw = ud.get("switches") or {}
    g["sw"] = {"U1": bool(sw.get("DISPATCH_URGENCY")), "a": bool(sw.get("FF_APPROACH_PATH")),
               "b": bool(sw.get("FF_RETREAT_KEEP_APPROACH")), "c": bool(sw.get("FF_CARRY_REPLAN"))}
    tm = ud.get("timing") or {}
    g["wall_s"] = float(d.get("wall_s") or 0.0)
    g["u1_ms"] = float(tm.get("u1_model_ms") or 0.0)
    g["fix_ms"] = float(sum((tm.get("fix_ms_total") or {}).values()) or 0.0)
    g["fix_calls"] = {f: list(v or []) for f, v in (tm.get("fix_calls") or {}).items()}
    g["probe_frac"] = tm.get("probe_frac_of_wall")
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
    if eps is not None:            # 22.8.3 designed-behaviour exclusion: the C-2 stay / C-3 hold steps break the run
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
    # ---- identity material (Z1 fields: every per-step row, the commands, eval, stdout with the new tags stripped)
    g["h"] = {k: hashes(d.get(k) or []) for k in ROW_KINDS}
    g["cmds"] = [list(c) for c in cmds]
    g["rels"] = [list(r) for r in dp.get("releases") or []]
    g["cmd_ctx"] = list(ud.get("cmd_ctx") or [])
    g["rel_ctx"] = list(ud.get("rel_ctx") or [])
    so, marks, vdead_ev, triage = read_stdout_stripped(path)
    g["so"], g["so_marks"], g["so_triage"] = so, marks, triage
    g["vdead_events"] = dict(vdead_ev)
    g["kicks"] = list(ud.get("kicks") or [])
    g["decisions"] = list(ud.get("decisions") or [])
    g["fates"] = dict(ud.get("fates") or {})
    g["mv_rows"] = mv_rows
    g["mv_events"] = list(d.get("mv_events") or [])
    g["legs_ev"] = legs_ev
    g["m8"] = list(dp.get("m8") or [])
    # ---- per-run structural zeros (owners applied in section 3)
    Z = {}
    Z["Z2"] = z2_u1(cmds, g["cmd_ctx"], g["rels"], g["rel_ctx"])
    Z["Z2-M"] = z2_mov(cmds, g["cmd_ctx"], g["rels"], g["rel_ctx"])
    Z["Z4"] = z4_kicks(g["kicks"], g["sw"]["U1"])
    g["z7_other"] = []
    if g["sw"]["U1"]:
        Z["Z3"] = z3_kicks(g["kicks"])
        z7 = z7_readings(g["kicks"])
        Z["Z7"] = z7["gate"]               # Z7_READING gates; the other reading is REPORTED (R3 D-24)
        g["z7_other"] = z7["reported"]
        Z["Z8"] = z8_kicks(g["kicks"])
    else:
        lists["lemma2_offarm"] = lemma2_offarm(g["kicks"])
    lists["kick_flag_bad"] = [[K.get("step"), K.get("i"), kick_flag_check(K)] for K in g["kicks"] if kick_flag_check(K)]
    rets = gt_returns_amended(cmds, dp.get("binders"), ff_dead, ff_rb)
    Z["Z5"] = [r for r in rets if not r["outside"]]
    num["gt_returns"] = len(rets)
    Z["Z-RB"] = z_rb(mv_rows, g["sw"]["c"])
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
    if g["sw"]["c"]:
        Z["Zm-c"], lists["zm_c_excluded"] = zm_c(mv_rows, cmds, ffs, vdead, g["vdead_events"])
    if g["sw"]["a"] or g["sw"]["b"] or g["sw"]["c"]:
        Z["Z-S"], lists["c3_on_burning"] = z_s(mv_rows)
    # ud.shadow_mismatch + live ACTED disagreements: behaviour, routed to Z7 (both readings) / Z1-M (v) / SM (ruling)
    g["z7_other"] = merge_mismatch(Z, g["z7_other"], shadow_mismatch_zeros(ud.get("shadow_mismatch"), g["mv_events"],
                                                                           arm in ("0", "E0")))
    g["Z"] = Z
    # ---- ACTED footprint (live events) and shadows
    for e in g["mv_events"]:
        k = e.get("kind")
        tag = ("live_" if e.get("live") else "shadow_") + str(k)
        num[tag] += 1
    g["acted_live"] = {k: bool(any(e.get("live") and (e.get("kind") == k or (k == "c" and e.get("kind") in ("C4", "C5")))
                                   for e in g["mv_events"])) for k in ("a", "b", "c")}
    # ---- U1 decisions (MU1 / MU2)
    num["kicks"] = len(g["kicks"])
    num["kicks_qualifying"] = sum(1 for K in g["kicks"] if K.get("qualifies"))
    num["kicks_div_shadow"] = sum(1 for K in g["kicks"] if K.get("div_shadow"))
    num["kicks_divergent"] = sum(1 for K in g["kicks"] if K.get("divergent"))
    num["kicks_scarce_multi"] = sum(1 for K in g["kicks"] if K.get("W") is not None and len(K.get("F") or []) >= 2
                                    and len(K.get("W") or []) > len(K.get("F") or []))
    num["promotions"] = sum(1 for x in g["decisions"] if x.get("P"))
    num["deferrals"] = sum(1 for x in g["decisions"] if x.get("P") is False)
    # v2: qualifying kicks where a planner-REFUSED victim heads either order (R2 B-1 / R3 D-24), and refused records
    num["kicks_refused_head"] = sum(1 for K in g["kicks"] if K.get("qualifies") and "index_wb" in K and (
        K.get("index_wb") != (K.get("index") or [None])[0] or K.get("u1_wb") != (K.get("u1") or [None])[0]))
    num["decisions_refused"] = sum(1 for x in g["decisions"] if x.get("accepted") is False)
    g["u1_kick_ms"] = [float(K["ms_model"]) for K in g["kicks"] if K.get("qualifies") and K.get("ms_model") is not None]
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
    # ---- DIAG material: raises / strandings within 6 steps after a live (a) step; SHELTER / HOLD episodes
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
    eps = []
    for leg in legs:
        if leg[0]["leg"] != "carry":
            continue
        run = []
        for r in leg + [None]:
            if r is not None and r.get("branch") in ("c2", "c2s", "c3") and (not run or r["branch"][:2] ==
                                                                             run[-1]["branch"][:2]):
                run.append(r)
                continue
            if run:
                v = run[0].get("victim")
                eps.append(["SHELTER" if run[0]["branch"].startswith("c2") else "HOLD", run[0]["unit"], v,
                            run[0]["step"], run[-1]["step"], "rescued@%s" % resc[v] if v in resc else
                            "dead@%s" % vdead[v] if v in vdead else "open"])
            run = [r] if (r is not None and r.get("branch") in ("c2", "c2s", "c3")) else []
    lists["shelter_hold"] = eps
    deferred = {}
    for x in g["decisions"]:
        if x.get("P") is False and not x.get("served"):
            deferred.setdefault(x["vid"], x["step"])
    lists["deferred_writeoffs"] = [[c[0], c[1], c[3], c[5], "deferred@%s" % deferred[c[3]]] for c in cmds
                                   if c[2] == "mark_unreachable" and c[6] and c[3] in deferred
                                   and c[0] >= deferred[c[3]]]
    # ---- REPORTED items, never gated: 16.8 G-B (a)(b)(d), G-T(b), M6, M3 (DPR's rb_figures; no J ledger exists here,
    # so every arm is read with live=False - the rebuild); 16.9 MU4 exposure (MU3 reads g["decisions"], M1 det / resc)
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
    g["mu4"], lists["mu4_strandings"], lists["mu4_deaths"] = mu4_exposure(
        rows_ff, cmds, g["cmd_ctx"], g["kicks"], mv_rows, g["mv_events"], ff_dead)
    g["num"], g["lists"] = num, lists
    return g


def hdigest(d, label, path):
    """A light digest of the case-1 harness record (_ffr_harness / _fm2_probe_harness)."""
    g = {"arm": "H", "label": label, "path": path, "usable": "ff_steps" in d, "kind": "harness"}
    g["eval"] = dict(d.get("eval") or {})
    g["terminal"] = d.get("terminal_step")
    g["assigns"] = [(a["step"], a["ff"], a["vid"], a.get("reason"), bool(a.get("ok"))) for a in d.get("assigns") or []]
    g["unassigns"] = [(a["step"], a["ff"], a["vid"], a.get("reason"), bool(a.get("ok"))) for a in
                      d.get("unassigns") or []]
    n = len(d.get("ff_steps") or [])
    g["h"] = {"steps": hashes([[(d.get("ff_steps") or [None] * n)[t],
                                (d.get("victim_steps") or [None] * n)[t] if t < len(d.get("victim_steps") or []) else None,
                                (d.get("uav_steps") or [None] * n)[t] if t < len(d.get("uav_steps") or []) else None]
                               for t in range(n)])}
    so, marks, _vd, triage = read_stdout_stripped(path)
    g["so"], g["so_marks"], g["so_triage"] = so, marks, triage
    det, _disp = parse_stdout(path)
    g["det"] = det or {}
    return g


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


def _kick_shadow(K):
    return {k: K.get(k) for k in KICK_SHADOW}


def z1_u1(gx, gy):
    """Z1 for U1 on the pair X (switch off) -> Y (= X + DISPATCH_URGENCY): identical up to the first U1-divergent
    kick of Y, the first difference at that kick's step, and X's shadow verdict at that kick equal to Y's.
    Returns {"s": first divergent step or None, "ident", "D", "viol": [...]}."""
    ident, D, ub, what = value_identity(gx, gy)
    ky, kx = gy.get("kicks") or [], gx.get("kicks") or []
    first = next(((i, K) for i, K in enumerate(ky) if K.get("divergent")), None)
    viol = []
    if first is None:
        if not ident:
            viol.append("no U1-divergent kick but the runs differ (%s; first at step %s)" % (what, D))
        return {"s": None, "ident": ident, "D": D, "viol": viol, "what": what}
    i, K = first
    s = K.get("step")
    if ident:
        viol.append("a U1-divergent kick at step %s but the runs are identical" % s)
    if D is not None and D != s:
        viol.append("first difference at step %s, the divergent kick at step %s (%s)" % (D, s, what))
    if D is None and not ident:
        viol.append("the runs differ only in %s; nothing at the divergent kick's step %s" % (what, s))
    if ub is not None and ub < s:
        viol.append("stdout differs by step %s, before the divergent kick at %s" % (ub, s))
    for j in range(i):
        if j >= len(kx) or _kick_shadow(kx[j]) != _kick_shadow(ky[j]):
            viol.append("kick record %d differs before the divergent kick" % j)
            break
    if i >= len(kx):
        viol.append("X has no kick %d (the divergent kick's counterpart)" % i)
    else:
        a, b = _kick_shadow(kx[i]), _kick_shadow(ky[i])
        if a != b:
            viol.append("cross-arm shadow at the divergent kick differs: %s" % first_path(a, b))
        if not kx[i].get("div_shadow"):
            viol.append("X's shadow does not flag the kick at step %s as divergent" % s)
    return {"s": s, "ident": ident, "D": D, "viol": viol, "what": what}


def _rows_at(g, step):
    return [r for r in g.get("mv_rows") or [] if r["step"] == step]


def _shadow(r):
    return {k: r.get(k) for k in SHADOW_FIELDS}


def z1_mov(gx, gy):
    """Z1-M on the pair X (movement off) -> Y (= X + the three movement switches): (i) no live ACTED event in Y ->
    identical end to end; (ii) identical before s* (the first live ACTED step); (iii) cross-arm shadow agreement at
    s* (X's would-act event with the same fix, unit and cell / victim; X's rows at s* up to Y's first acting row
    equal on the shadow fields); (iv) an (a) or (c) cell change at s* -> the first difference at s*."""
    ident, D, ub, what = value_identity(gx, gy)
    live = [e for e in gy.get("mv_events") or [] if e.get("live") and e.get("kind") in ("a", "b", "c", "C4", "C5")]
    viol = []
    if not live:
        if not ident:
            viol.append("no movement switch ACTED but the runs differ (%s; first at step %s)" % (what, D))
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
        if k in ("a", "b", "c"):
            match = [x for x in xev if x.get("kind") == k and x.get("unit") == e.get("unit")
                     and x.get("cell") == e.get("cell") and x.get("today") == e.get("today")]
            pos = next((j for j, r in enumerate(ry) if r["_i"] == e.get("row")), None)
            if pos is None:
                viol.append("live (%s) event at s* = %s without its row" % (k, s))
            else:
                for j in range(pos + 1):
                    if j >= len(rx) or _shadow(rx[j]) != _shadow(ry[j]):
                        viol.append("shadow fields differ at s* = %s, row %d (%s)" % (
                            s, j, first_path(_shadow(rx[j]), _shadow(ry[j])) if j < len(rx) else "missing in X"))
                        break
        else:
            match = [x for x in xev if x.get("kind") == k and x.get("unit") == e.get("unit")
                     and x.get("victim") == e.get("victim")]
        if not match:
            viol.append("no matching would-act (%s) shadow in X at s* = %s (unit %s)" % (k, s, e.get("unit")))
    if any(e.get("kind") in ("a", "c") for e in at) and D != s:
        viol.append("an (a) / (c) cell change at s* = %s but the first difference is at %s" % (s, D))
    return {"s": s, "ident": ident, "D": D, "viol": viol, "what": what,
            "first": sorted({str(e.get("kind")) for e in at})}


def off_bound_at(gx, step, unit):
    """The victim the OFF harness run bound at `step` by `unit` (its exact assign record: step = the model's
    evaluation_timesteps_counter, as the triage line's); None when it bound nothing there. A unit id the OFF record
    never names falls back to any OFF bind at that step (|F| = 1 at a qualifying kick)."""
    assigns = [a for a in gx.get("assigns") or [] if a[4]]
    known = {a[1] for a in assigns}
    for a in assigns:
        if a[0] == step and (a[1] == unit or unit not in known):
            return a[2]
    return None


def z1_harness(gx, gy):
    """Evidence case 1 (harness, no kick record; R2 M-1): identical end to end unless an ON [UrgencyTriage] line is
    DIVERGENT - it served a victim (served != 'none') other than the one the OFF run bound at that kick (the OFF
    harness's exact assign record for that step and unit); then the first difference is at that step. served=none, or
    a refused lowest-index victim with the same victim bound in both arms, is not a divergence."""
    ident, D, ub, what = value_identity(gx, gy)
    div = None
    for ln in gy.get("so_triage") or []:
        tr = parse_triage(ln)
        if tr is None or tr[3] in ("none", "", None):
            continue
        if tr[3] != off_bound_at(gx, tr[0], tr[1]):
            div = tr[0]
            break
    viol = []
    if div is None and not ident:
        viol.append("ON differs from OFF (%s, first at %s) without a divergent [UrgencyTriage] line" % (what, D))
    if div is not None and D is not None and D != div:
        viol.append("first difference at %s, the divergent triage line at %s" % (D, div))
    return {"s": div, "ident": ident, "D": D, "viol": viol, "what": what}


# ================================================================================================ the screen pass
def slim(g):
    """Drop the heavy per-step material once the cell's pair checks are done."""
    for k in ("h", "so", "so_marks", "mv_rows", "cmd_ctx", "rel_ctx", "cmds", "rels", "mv_events"):
        g.pop(k, None)


_REF_SHAS: dict = {}


def ref_bad(path, opts):
    """A reference copy (outputs/_ud_dpR, _ud_dpE) must exist and match outputs/_ud_dpR_sha256.txt (LF-tolerant):
    returns None or the reason (a tooling problem - Z0 is then INCOMPLETE, never a FAIL)."""
    if not os.path.exists(path):
        return "reference record missing %s" % os.path.basename(path)
    if opts.smoke:
        return None
    if not _REF_SHAS:
        try:
            with open(os.path.join(HERE, "_ud_dpR_sha256.txt"), encoding="utf-8") as fh:
                for ln in fh:
                    parts = ln.split()
                    if len(parts) == 3:
                        _REF_SHAS[os.path.normcase(os.path.join(WT, parts[2].replace("/", os.sep)))] = parts[0]
        except OSError:
            _REF_SHAS["__none__"] = ""
    for p in (path, stdout_path(path)):
        want = _REF_SHAS.get(os.path.normcase(p))
        if want is None:
            return "%s not listed in outputs/_ud_dpR_sha256.txt" % os.path.basename(p)
        if want not in (sha_file(p), sha_lf_file(p)):
            return "%s differs from outputs/_ud_dpR_sha256.txt" % os.path.basename(p)
    return None


def process(cells, opts, queues):
    recs = []
    for c in cells:
        rec = {"cell": c, "g": {}, "prov": {}, "crash": {}, "missing": [], "ident": None, "stop": [],
               "pairs": {}, "ref_bad": None}
        rp = ref_path(c, opts)
        ref = None
        if rp is not None and os.path.exists(run_path("0", c, opts)):
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
            rec["prov"][arm], rec["crash"][arm] = why, crash
            if stop:
                rec["stop"].append((arm, stop))
            if arm == "0" and ref is not None:
                if ref.get("dp_only") or d.get("dp_only"):
                    rec["ident"] = (["sd record missing (crash)"], "", [], "")
                else:
                    diff, note, other = ident_diff(ref, d, bool(opts.smoke))
                    fp = first_path(field_get(ref, diff[0]), field_get(d, diff[0]), diff[0]) if diff else ""
                    rec["ident"] = (diff, note, other, fp)
                ref = None
            rec["g"][arm] = digest(d, arm, "%s_%s" % (ARM_TAG[arm], c["id"]), p, c["set"],
                                   censor=(int(d.get("steps_done") or 0) + 1) if opts.smoke else H + 1)
            d = None
        ref = None
        G = rec["g"]
        for x, y, kind in (("0", "U", "u1"), ("M", "MU", "u1"), ("0", "M", "mov"), ("U", "MU", "mov")):
            if x in G and y in G and G[x].get("usable") and G[y].get("usable"):
                rec["pairs"][(x, y)] = z1_u1(G[x], G[y]) if kind == "u1" else z1_mov(G[x], G[y])
        for x, y in COMPARISONS:
            if (x, y) not in rec["pairs"] and x in G and y in G and G[x].get("usable") and G[y].get("usable"):
                ident, D, _ub, what = value_identity(G[x], G[y])
                rec["pairs"][(x, y)] = {"s": None, "ident": ident, "D": D, "viol": [], "what": what}
        for g in G.values():
            slim(g)
        recs.append(rec)
    return recs


def process_evidence(opts, queues):
    """16.11: the 11 OFF (W1) and 11 ON (W4) evidence runs, paired by case and CRN mode; OFF vs outputs/_ud_dpE/."""
    pairs = collections.OrderedDict()
    for _key, (wave, line) in queues.items():
        m = re.match(r"^udE(1|2f|2|x|3|4d|4g)([01])([cn])(?:_([A-D]_[NSEW]))?$", line["name"])
        if not m:
            continue
        pairs.setdefault((m.group(1), m.group(3)), {})[m.group(2)] = line
    res = []
    for (case, crn), arms in pairs.items():
        e = {"case": case, "crn": crn, "g": {}, "prov": {}, "crash": {}, "missing": [], "z0": None, "pair": None,
             "ref_bad": None}
        for arm in ("0", "1"):
            line = arms.get(arm)
            if line is None:
                e["missing"].append(arm)
                continue
            p = line["out"]
            if not os.path.exists(p):
                e["missing"].append(arm)
                continue
            d = load_run(p)
            harness = "ff_steps" in d
            if harness:
                why, crash = prov_harness(d, p, line, opts)
                g = hdigest(d, line["name"], p)
            else:
                why, crash, _stop = prov_run(d, p, line, None, opts)
                g = digest(d, "E" + arm, line["name"], p, "evidence")
            e["prov"][arm], e["crash"][arm] = why, crash
            if arm == "0":
                ref = os.path.join(HERE, "_ud_dpE", os.path.basename(p).replace("udE", "dpE", 1))
                e["ref_bad"] = ref_bad(ref, opts)
                if e["ref_bad"] is None:
                    r = load_run(ref)
                    if harness:
                        diff = [k for k in ("eval", "assigns", "unassigns", "terminal_step") if r.get(k) != d.get(k)]
                        e["z0"] = (diff, first_path(r.get(diff[0]), d.get(diff[0]), diff[0]) if diff else "")
                    else:
                        diff, _note, _other = ident_diff(r, d, False)
                        e["z0"] = (diff, first_path(field_get(r, diff[0]), field_get(d, diff[0]), diff[0])
                                   if diff else "")
            e["g"][arm] = g
        if "0" in e["g"] and "1" in e["g"] and e["g"]["0"].get("usable") and e["g"]["1"].get("usable"):
            if e["g"]["0"].get("kind") == "harness":
                e["pair"] = z1_harness(e["g"]["0"], e["g"]["1"])
            else:
                e["pair"] = z1_u1(e["g"]["0"], e["g"]["1"])
        for g in e["g"].values():
            slim(g)
        res.append(e)
    return res


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


def sec_prov(recs, ev, opts):
    head("1 LOAD + PROV (16.6) - arms 0 (ud0), U (ud1), M (ud2), MU (ud3); files outputs/_sd_ud<a><r|u><k>_<S>_<W>.json; "
         "validity against the frozen queues")
    st = {"missing": [], "invalid": [], "gate": [], "stop": [], "seed": []}
    for arm in ARMS:
        sub = [r for r in recs if arm in r["cell"]["arms"]]
        present = sum(1 for r in sub if arm in r["g"])
        miss = [r["cell"]["id"] for r in sub if arm in r["missing"]]
        inv = [(r["cell"]["id"], r["prov"][arm]) for r in sub if r["prov"].get(arm)]
        crash = [(r["cell"]["id"], r["crash"][arm]) for r in sub if r["crash"].get(arm)]
        out("  %-3s present %3d / %d | missing %d | INVALID %d | crash / early stop %d" % (
            arm, present, len(sub), len(miss), len(inv), len(crash)))
        for cid, why in inv:
            out("       INVALID %s %s: %s" % (arm, cid, "; ".join(why)))
        for cid in miss[:64]:
            out("       MISSING %s %s" % (arm, cid))
        for cid, why in crash:
            out("       %s %s %s: %s" % ("STOP (base defect: a C crash, 16.6)" if arm == "0" else "GATE FAILURE (Z6)",
                                        arm, cid, mask_text(why) if masked(opts) else why))
        st["missing"] += [(arm, c) for c in miss]
        st["invalid"] += [(arm, c, w) for c, w in inv]
        (st["stop"] if arm == "0" else st["gate"]).extend((arm, c, w) for c, w in crash)
    for r in recs:
        for arm, why in r["stop"]:
            st["seed"].append((arm, r["cell"]["id"], why))
            out("       STOP (seed-selector rule) %s %s: %s" % (arm, r["cell"]["id"], why))
    for e in ev:
        for arm in ("0", "1"):
            tag = "udE%s%s%s" % (e["case"], arm, e["crn"])
            if arm in e["missing"]:
                st["missing"].append(("E" + arm, tag))
                out("       MISSING evidence %s" % tag)
            if e["prov"].get(arm):
                st["invalid"].append(("E" + arm, tag, e["prov"][arm]))
                out("       INVALID evidence %s: %s" % (tag, "; ".join(e["prov"][arm])))
            if e["crash"].get(arm):
                (st["stop"] if arm == "0" else st["gate"]).append(("E" + arm, tag, e["crash"][arm]))
                out("       %s evidence %s: %s" % ("STOP (base defect)" if arm == "0" else "GATE FAILURE (Z6)", tag,
                                                  mask_text(e["crash"][arm]) if masked(opts) else e["crash"][arm]))
    out("  evidence runs: %d configurations (OFF %d, ON %d present)" % (
        len(ev), sum(1 for e in ev if "0" in e["g"]), sum(1 for e in ev if "1" in e["g"])))
    nodet = [g["label"] for r in recs for g in r["g"].values() if g.get("usable") and not any(
        v is not None for v in (g.get("det") or {}).values()) and g.get("eval", {}).get("never_detected", 0) == 0]
    if nodet:
        out("  WARNING runs without any stdout detection: %s" % nodet[:8])
    return st


def sec_z0(recs, ev, opts):
    head("2 Z0 IDENTITY (16.7 Z0, S1) - ud0 == dpR (outputs/_ud_dpR/) on sets 1-2 on DPR's G-ID fields (_fx3r_analyze "
         "FIELDS + every mf2 section but probe + every dp field but %s); evidence OFF == outputs/_ud_dpE/; ud0's M8 == "
         "dp0's (13 deaths, 11 FC)" % "/".join(J_ONLY))
    comp = [r for r in recs if r["ident"] is not None]
    same = sum(1 for r in comp if not r["ident"][0])
    for r in recs:
        if r.get("ref_bad"):
            out("    %s reference NOT USABLE (Z0 incomplete, a tooling matter): %s" % (r["cell"]["id"], r["ref_bad"]))
    for e in ev:
        if e.get("ref_bad"):
            out("    evidence udE%s0%s reference NOT USABLE: %s" % (e["case"], e["crn"], e["ref_bad"]))
    for r in comp:
        diff, note, other, fp = r["ident"]
        if diff:
            out("    %s DIFFER %s | first path %s" % (r["cell"]["id"], diff[:8], path_only(fp) if masked(opts) else fp))
        if note:
            out("    %s note: %s" % (r["cell"]["id"], note))
        if other:
            out("    %s other sections differing (reported): %s" % (r["cell"]["id"], other[:6]))
    want = 1 if opts.smoke else 64
    probe_ok = same == len(comp) == want
    out("  probe cells: %d / %d identical (%d compared, %d expected)  => %s" % (
        same, len(comp), len(comp), want, "PASS" if probe_ok else ("FAIL" if same < len(comp) else "INCOMPLETE")))
    # M8 reproduction
    m8 = {}
    for s in ("set1", "set2"):
        fc = fu = n = 0
        for r in recs:
            if r["cell"]["set"] != s or not usable(r, "0"):
                continue
            n += 1
            a, b, _rows = m8_classify(r["g"]["0"]["m8"])
            fc += a
            fu += b
        m8[s] = (fc, fu, n)
    m8_state = m8_check(m8)
    m8_ok = m8_state == "PASS"
    if not opts.smoke and masked(opts):
        out("  ud0 M8 reproduction of dp0's (13 deaths, 11 FC) over %d + %d runs  => %s (values not printed: "
            "--zeros-only)" % (m8["set1"][2], m8["set2"][2], m8_state))
    elif not opts.smoke:
        out("  ud0 M8: set1 FC %d futile %d (%d runs) | set2 FC %d futile %d (%d runs) | dp0: set1 %s set2 %s (13 "
            "deaths, 11 FC)  => %s" % (m8["set1"][0], m8["set1"][1], m8["set1"][2], m8["set2"][0], m8["set2"][1],
                                       m8["set2"][2], DP0_M8["set1"], DP0_M8["set2"], m8_state))
    else:
        m8_ok, m8_state = True, "PASS"
        out("  ud0 M8 reproduction: NOT RUN (smoke)")
    ev_cmp = [e for e in ev if e["z0"] is not None]
    ev_same = sum(1 for e in ev_cmp if not e["z0"][0])
    for e in ev_cmp:
        if e["z0"][0]:
            out("    evidence udE%s0%s DIFFERS from dpE: %s | first path %s" % (
                e["case"], e["crn"], e["z0"][0][:6], path_only(e["z0"][1]) if masked(opts) else e["z0"][1]))
    ev_want = 0 if opts.smoke else 11
    ev_ok = ev_same == len(ev_cmp) == ev_want
    out("  evidence OFF: %d / %d identical (probe cases: the same fields; harness case 1: eval, assigns, unassigns, "
        "terminal step)  => %s" % (ev_same, len(ev_cmp), "PASS" if ev_ok else ("FAIL" if ev_same < len(ev_cmp)
                                                                               else "INCOMPLETE")))
    fail = same < len(comp) or ev_same < len(ev_cmp) or m8_state == "FAIL"
    s1 = probe_ok and ev_ok and m8_ok
    out("  S1 IDENTITY => %s" % ("PASS" if s1 else "FAIL" if fail else "INCOMPLETE"))
    return {"pass": s1, "fail": fail}


def zero_owners(zero, arm):
    """22.8.2's map: U1-owned zeros fail R-U and R-MU; movement-owned fail R-M and R-MU; Z5 / Z6 are owned by the
    switches of the arm in which they occur. An arm-0 (or evidence-OFF) failure is a STOP - 22.8.2 makes STOP arm-0
    only. A U1-owned zero in an arm without U1, and a movement-owned zero (Z-RB included, R3 D-12) in an arm without
    the movement switches (U, E1), are REPORTED."""
    sw = ARM_SW.get(arm, set())
    if zero == "SM":                    # a shadow_mismatch row: STOP in arm 0 / E0; an unknown kind elsewhere: reported
        return "STOP" if arm in ("0", "E0") else "REPORTED"
    if arm in ("0", "E0"):
        return "STOP" if zero in ("Z5", "Z-RB", "Z6", "Z0") else "REPORTED"
    if zero in U1_ZEROS:
        return {"U1"} if "U1" in sw else "REPORTED"
    if zero in MOV_ZEROS:
        return {"MOV"} if "MOV" in sw else "REPORTED"
    return set(sw)


def sec_zeros(recs, ev, st, opts):
    head("3 STRUCTURAL ZEROS (16.7, 22.8.2) - exact, on every run; owners: U1 (Z1 Z2 Z3 Z4 Z7 Z8) fail R-U and R-MU; "
         "movement (Z1-M Z2-M Z-RB Zm-a Zm-b Zm-c Z-S) fail R-M and R-MU; Z5 / Z6 by the arm's switches; any arm-0 "
         "failure STOPS")
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
            if (x, y) in (("0", "U"), ("M", "MU")):
                add("Z1", y, "%s->%s %s" % (x, y, r["cell"]["id"]), res["viol"])
            elif (x, y) in (("0", "M"), ("U", "MU")):
                add("Z1-M", y, "%s->%s %s" % (x, y, r["cell"]["id"]), res["viol"])
    for arm, cid, why in st["gate"] + st["stop"]:
        a = arm if arm in ARM_SW else "0"
        add("Z6", a, "%s %s" % (arm, cid), [why])
    for e in ev:
        for arm, g in e["g"].items():
            if g.get("usable") and g.get("kind") != "harness":
                for zero, items in (g.get("Z") or {}).items():
                    add(zero, "E" + arm, "evidence udE%s%s%s" % (e["case"], arm, e["crn"]), items)
        if e["pair"] is not None:
            add("Z1", "E1", "evidence udE%s %s" % (e["case"], e["crn"]), e["pair"]["viol"])
    zeros = ("Z1", "Z1-M", "Z2", "Z2-M", "Z3", "Z4", "Z5", "Z6", "Z7", "Z8", "Z-RB", "Zm-a", "Zm-b", "Zm-c", "Z-S",
             "SM")
    for z in zeros:
        cells = " | ".join("%s %d/%d" % (a, counts[(z, a)], checked[(z, a)]) for a in ARMS + ("E0", "E1")
                           if checked[(z, a)])
        out("  %-5s violations / runs-or-pairs checked: %s" % (z, cells or "not applicable"))
    out("  (ud.shadow_mismatch is behaviour, never INVALID: a kick-bind row is a Z7 instance under BOTH readings, a "
        "movement row or live ACTED disagreement a Z1-M item (v) instance; SM = any row in arm 0 / E0 (STOP) or of an "
        "unknown kind (reported))")
    mask = masked(opts)
    for zero, arm, where, owners, it in fails:
        out("    %s %-5s %-30s owner %s: %s" % ("STOP" if owners == "STOP" else "FAIL" if owners != "REPORTED"
                                              else "rep.", zero, where, owners if isinstance(owners, str)
                                              else "+".join(sorted(owners)),
                                              mask_text(str(it)[:220]) if mask else str(it)[:220]))
    # R3 D-24: the Z7 reading that does not gate is REPORTED; v2 kick-flag consistency (a tooling check, reported)
    other = "Z7-ACC (the first planner-ACCEPTED victim of the order, to f)" if Z7_READING == "literal" else \
        "Z7 literal (16.7: the first victim of the order, to f)"
    z7o = [(a, r["cell"]["id"], x) for r in recs for a, g in r["g"].items() if g.get("usable")
           for x in g.get("z7_other") or []]
    z7o += [("E" + a, "evidence udE%s %s" % (e["case"], e["crn"]), x) for e in ev for a, g in e["g"].items()
            if g.get("usable") for x in g.get("z7_other") or []]
    out("  Z7 gating reading: %s | REPORTED, not gating: %s - instances %d%s" % (
        "literal (16.7)" if Z7_READING == "literal" else "Z7-ACC", other, len(z7o),
        "" if not z7o else ": %s" % [mask_text(x) if mask else x for x in z7o[:6]]))
    kf = [(a, r["cell"]["id"], x) for r in recs for a, g in r["g"].items() if g.get("usable")
          for x in (g.get("lists") or {}).get("kick_flag_bad", [])]
    out("  reported tooling check: v2 kick flags (index_wb, u1_wb, div_shadow, divergent) inconsistent with acc / "
        "bound: %d%s" % (len(kf), "" if not kf else " %s" % [mask_text(x) if mask else x for x in kf[:6]]))
    # Z1 summaries
    for (x, y) in (("0", "U"), ("M", "MU"), ("0", "M"), ("U", "MU")):
        prs = [r["pairs"][(x, y)] for r in recs if (x, y) in r["pairs"]]
        if not prs:
            continue
        acted = sum(1 for p in prs if p["s"] is not None)
        at_s = sum(1 for p in prs if p["s"] is not None and p["D"] == p["s"])
        out("  Z1%s %s->%s: %d pairs, %d with a divergent kick / ACTED event, first difference at s* in %d, identical "
            "end to end %d" % ("" if y in ("U",) or (x, y) == ("M", "MU") else "-M", x, y, len(prs), acted, at_s,
                               sum(1 for p in prs if p["ident"])))
        if (x, y) in (("0", "M"), ("U", "MU")):
            firsts = collections.Counter("+".join(p.get("first") or []) for p in prs if p["s"] is not None)
            out("      first acting fix at s*: %s" % dict(firsts))
    lem = [(r["cell"]["id"], a, x) for r in recs for a, g in r["g"].items() for x in (g.get("lists") or {}).get(
        "lemma2_offarm", [])]
    out("  reported: qualifying kicks in arms with the switch off whose bind count differs from the index loop's "
        "counterfactual (1 if index_wb exists, else 0) [step, i, bound, counterfactual]: %s" % (
            ([mask_text(x) for x in lem[:6]] if mask else lem[:6]) or "none"))
    stop = [f for f in fails if f[3] == "STOP"]
    return {"fails": fails, "stop": stop}


def fresh_recs(recs):
    return [r for r in recs if r["cell"]["fresh"]]


def comparison(recs, x, y, zfails, s1_pass):
    """One comparison X -> Y on the fresh cells: S2 (zeros owned by the switches Y adds), S3, S4, S5 (23.2), S6."""
    cells = [r for r in fresh_recs(recs) if usable(r, x) and usable(r, y)]
    nx = {r["cell"]["id"]: r["g"][x]["num"] for r in cells}
    ny = {r["cell"]["id"]: r["g"][y]["num"] for r in cells}
    cset = {r["cell"]["id"]: r["cell"]["set"] for r in cells}
    diverged = {r["cell"]["id"] for r in cells if (x, y) in r["pairs"] and not r["pairs"][(x, y)]["ident"]}
    res = compare_counts(nx, ny, cset, diverged)
    res["S3"] = s3_rule({c: n["DD"] for c, n in nx.items()}, {c: n["DD"] for c, n in ny.items()}, cset)
    added = ADDED[(x, y)]
    s2f = s2_for(zfails, added)
    res["S2"] = not s2f
    res["S2_fails"] = s2f
    gy = [r["g"][y] for r in cells]
    s6 = {}
    if "U1" in added:
        s6["U1"] = s6_rule([g["u1_ms"] / (g["wall_s"] * 1000.0) for g in gy if g.get("wall_s")],
                           [ms for g in gy for ms in g.get("u1_kick_ms") or []])
    if "MOV" in added:
        s6["MOV"] = s6_rule([g["fix_ms"] / (g["wall_s"] * 1000.0) for g in gy if g.get("wall_s")],
                            [ms for g in gy for v in (g.get("fix_calls") or {}).values() for ms in v])
    res["S6"] = all(v["pass"] for v in s6.values())
    res["S6_detail"] = s6
    res["full"] = full_verdict(s1_pass, res["S2"], res["S3"]["pass"], res["S4"], res["S5"], res["S6"])
    res["harmless"] = res["S2"] and res["S4"] and res["S5"]
    res["n_cells"] = len(cells)
    res["cells"] = cells
    res["diverged_cells"] = diverged
    return res


def print_comparison(x, y, res, label="FRESH sets 3-4"):
    out("-- %s -> %s (%s): %d paired cells, %d diverged (Y not value-identical to X on the Z1 fields)" % (
        x, y, label, res["n_cells"], len(res["diverged_cells"])))
    for k, v in res["literal"].items():
        out("    LITERAL %-22s %4d -> %4d  %s" % (k, v["x"], v["y"], "FAIL" if v["fail"] else "ok"))
    out("    SIGN-TESTED (23.2; Holm over m = 24, alpha 0.05):")
    for k, label_ in SIGN_KEYS:
        v = res["sign"][k]
        out("      %-50s %4d -> %4d | n+ %2d n- %2d p %.5f | rank %2d thr %.5f %s%s" % (
            label_, v["x"], v["y"], v["n_plus"], v["n_minus"], v["p"], v["rank"], v["threshold"],
            "REJECTED (FAIL)" if v["rejected"] else "not rejected",
            " | rising in %s" % v["rising"][:6] if v["rising"] else ""))
    s3 = res["S3"]
    out("    S3 (17.2): pooled DD delta %+d | set3 %+d set4 %+d | without the most favourable cell (%s %s) %+d  => %s" % (
        s3["pooled"], s3["per_set"].get("set3", 0), s3["per_set"].get("set4", 0), s3["worst"], s3["worst_delta"],
        s3["loo"], "PASS" if s3["pass"] else "FAIL"))
    out("    S2 %s%s | S4 %s | S5 %s (literal fails %s, sign-test rejections %s) | S6 %s %s" % (
        "PASS" if res["S2"] else "FAIL", "" if res["S2"] else " %s" % [(f[0], f[2]) for f in res["S2_fails"][:6]],
        "PASS" if res["S4"] else "FAIL", "PASS" if res["S5"] else "FAIL", res["lit_fail"] or "none",
        res["sig_fail"] or "none", "PASS" if res["S6"] else "FAIL",
        {k: "median R %s p99 %s ms (runs %d, calls %d)" % (fmt(None if v["median_R"] is None else 100 * v["median_R"],
                                                              "%.3f%%"), fmt(v["p99"], "%.2f"), v["n_runs"],
                                                          v["n_calls"]) for k, v in res["S6_detail"].items()}))
    out("    FULL(%s -> %s) = %s | HARMLESS(%s -> %s) = %s" % (x, y, res["full"], x, y,
                                                              "PASS" if res["harmless"] else "FAIL"))


def sec_comparisons(recs, zres, s1_pass):
    head("4 COMPARISONS (22.8.1, 23.2) - the 64 FRESH cells; LITERAL L1 (ff deaths pooled, set 3, set 4), L2 (rescued "
         "set 3, set 4), L3 (DD pooled); 24 counts by the exact one-sided sign test over the diverged cells, Holm "
         "family-wise alpha 0.05")
    C = {}
    for x, y in COMPARISONS:
        C[(x, y)] = comparison(recs, x, y, zres["fails"], s1_pass)
        print_comparison(x, y, C[(x, y)])
    # in-sample U1 replay, reported only
    ins = [r for r in recs if not r["cell"]["fresh"] and usable(r, "0") and usable(r, "U")]
    if ins:
        nx = {r["cell"]["id"]: r["g"]["0"]["num"] for r in ins}
        ny = {r["cell"]["id"]: r["g"]["U"]["num"] for r in ins}
        cset = {r["cell"]["id"]: r["cell"]["set"] for r in ins}
        div = {r["cell"]["id"] for r in ins if ("0", "U") in r["pairs"] and not r["pairs"][("0", "U")]["ident"]}
        res = compare_counts(nx, ny, cset, div, fresh=("set1", "set2"))
        res["S3"] = s3_rule({c: n["DD"] for c, n in nx.items()}, {c: n["DD"] for c, n in ny.items()}, cset,
                            fresh=("set1", "set2"))
        out("-- 0 -> U IN-SAMPLE sets 1-2 (W1 / W3 U1 replay; REPORTED, never gated): %d cells, %d diverged | literal "
            "fails %s | sign-test rejections %s | DD %d -> %d" % (len(ins), len(div), res["lit_fail"] or "none",
                                                                  res["sig_fail"] or "none",
                                                                  sum(n["DD"] for n in nx.values()),
                                                                  sum(n["DD"] for n in ny.values())))
    return C


def sec_m8(recs, opts):
    head("5 M8, M8-D AND THE FROZEN ATTRIBUTION OF 22.9 - every detected-victim death in every arm: the FIRST of FUT, "
         "U1, PRE, MOV-a, MOV-b, MOV-c, MOV-closure, RP, L3, OTHER (recorded fields only)")
    classes = ("FUT", "U1", "PRE", "MOV-a", "MOV-b", "MOV-c", "MOV-closure", "RP", "L3", "OTHER")
    for arm in ARMS:
        for s in ("set1", "set2", "set3", "set4"):
            sub = [r for r in recs if r["cell"]["set"] == s and usable(r, arm)]
            if not sub:
                continue
            ds = [dd for r in sub for dd in r["g"][arm]["deaths"]]
            fc = sum(1 for dd in ds if dd["m8"] == "FC")
            cnt = collections.Counter(dd["cls"] for dd in ds)
            out("  arm %-2s %s (%2d runs): DD %2d | M8 FC %2d futile %2d (FC %s) | M8-D %2d | classes %s" % (
                arm, s, len(sub), len(ds), fc, len(ds) - fc, fmt(100.0 * fc / len(ds) if ds else None, "%.0f%%"),
                sum(1 for dd in ds if dd["m8d"]), " ".join("%s %d" % (k, cnt[k]) for k in classes if cnt[k])))
    out("  per death [cell, victim, detection, death, M8, M8-D, class, every class that applies]:")
    for r in recs:
        for arm, g in r["g"].items():
            for dd in g.get("deaths") or []:
                out("    %-2s %-22s %-9s det %4s death %4s %-6s M8-D %-5s %-11s %s" % (
                    arm, r["cell"]["id"], dd["victim"], dd["det"], dd["death"], dd["m8"], dd["m8d"], dd["cls"],
                    dd["flags"]))
    out("  POSITIVE CONTROL (22.9; W1 arm 0 sets 1-2 vs 3.1's hand tally - agreement reported, rules NOT tuned):")
    agree = n = 0
    for (s, plc, key, v), (no, dstep, manual) in sorted(TALLY_31.items(), key=lambda kv: kv[1][0]):
        r = next((x for x in recs if x["cell"]["id"] == "%s/%s/%s" % (s, plc, key)), None)
        g = r["g"].get("0") if r else None
        dd = next((x for x in (g or {}).get("deaths") or [] if x["victim"] == v), None)
        if dd is None:
            out("    #%-2d %s/%s/%s %s: manual %s | code: no such death in ud0 (%s)" % (
                no, s, plc, key, v, manual, "run missing" if g is None else "deaths %s" % [x["victim"] for x in
                                                                                       g.get("deaths") or []]))
            continue
        ok = (manual == dd["cls"]) or (manual == "MOV" and dd["cls"].startswith("MOV"))
        if manual != "FUT-in-practice":
            n += 1
            agree += ok
        out("    #%-2d %s/%s/%s %s death %s (3.1: %s): manual %-16s code %-11s %s | applies %s" % (
            no, s, plc, key, v, dd["death"], dstep, manual, dd["cls"],
            "agree" if ok else "(FUT in practice: reported)" if manual == "FUT-in-practice" else "DIFFER", dd["flags"]))
    out("  positive control: %d / %d agree (the 2 'FUT in practice' cases are M8-FC and reported only)" % (agree, n))


def sec_measures(recs, C, opts=None):
    head("6 MEASURES AND DIAG (16.9, 22.2.4, 22.8.3, 23.2) - reported, never gated")
    keys = ("rescued", "dead", "DD", "ff_deaths", "never_detected", "escape_writeoffs", "dispatch_writeoffs")
    out("M2 outcomes per arm, fresh set and placement:")
    for arm in ARMS:
        for s in FRESH + ("set1", "set2"):
            for plc in ("ring", "uniform"):
                sub = [r for r in recs if r["cell"]["set"] == s and r["cell"]["plc"] == plc and usable(r, arm)]
                if sub:
                    out("  %-2s %s %-7s %s" % (arm, s, plc, " ".join("%s=%d" % (k, sum(r["g"][arm]["num"].get(k, 0)
                                                                                 for r in sub)) for k in keys)))
    out("MU1 decisions per arm and set: kicks, qualifying, U1-divergent (Y) / shadow-divergent (v2: the victim each "
        "order WOULD BIND differs - the first planner-accepted one, not the list head), promotions, deferrals, scarce "
        "kicks with |F| >= 2:")
    for arm in ARMS:
        for s in ("set1", "set2", "set3", "set4"):
            sub = [r for r in recs if r["cell"]["set"] == s and usable(r, arm)]
            if sub:
                t = lambda k: sum(r["g"][arm]["num"].get(k, 0) for r in sub)      # noqa: E731
                out("  %-2s %s kicks %d qualifying %d divergent %d shadow-divergent %d promotions %d deferrals %d "
                    "scarce |F|>=2 %d | qualifying kicks with a planner-refused order head %d, refused decision "
                    "records %d" % (arm, s, t("kicks"), t("kicks_qualifying"), t("kicks_divergent"),
                                    t("kicks_div_shadow"), t("promotions"), t("deferrals"), t("kicks_scarce_multi"),
                                    t("kicks_refused_head"), t("decisions_refused")))
    out("MU1 T class of each divergence (Y: U1-divergent kicks; X: shadow-divergent kicks): both T beyond 360 - t, or "
        "not | MU2 fates of the victims at qualifying kicks (promoted P / deferred D: rescued, died, still waiting) and "
        "of the victim passed over at each divergent kick:")
    for arm in ARMS:
        for s in ("set1", "set2", "set3", "set4"):
            sub = [r for r in recs if r["cell"]["set"] == s and usable(r, arm)]
            if not sub:
                continue
            tcls, fates, passed = collections.Counter(), collections.Counter(), collections.Counter()
            for r in sub:
                g = r["g"][arm]
                for K in g.get("kicks") or []:
                    if not (K.get("divergent") or K.get("div_shadow")):
                        continue
                    t_left = H - int(K.get("step") or 0)
                    # R2 B-1: the two victims of a divergence are the ones each order WOULD BIND (u1_wb, index_wb)
                    ts = [(K.get("rec") or {}).get(v, [None])[0] for v in (u1_wb(K), idx_wb(K)) if v is not None]
                    tcls["both T beyond" if all(t is None or t > t_left for t in ts) else "not"] += 1
                    pv = idx_wb(K)
                    dec = next((x for x in g.get("decisions") or [] if x.get("k") == K.get("i") and x["vid"] == pv),
                               None)
                    if dec is not None:
                        passed["rescued" if dec.get("complete") is not None else "died" if dec.get("death") is not None
                               else "waiting"] += 1
                for x in g.get("decisions") or []:
                    fates[("P" if x.get("P") else "D") + ":" + ("rescued" if x.get("complete") is not None else "died"
                                                               if x.get("death") is not None else "waiting")] += 1
            out("  %-2s %s divergences %s | fates %s | passed-over %s" % (arm, s, dict(tcls) or "-", dict(fates) or "-",
                                                                          dict(passed) or "-"))
    out("F4 role filter (reported): _sd_analyze UAV I2 LIVELOCK / I2 STUCK / I6 RTB no-progress over ALL UAVs vs the "
        "victim_searcher episodes the gate counts:")
    for arm in ARMS:
        sub = [r for r in fresh_recs(recs) if usable(r, arm)]
        if sub:
            t = lambda k: sum(r["g"][arm]["num"].get(k, 0) for r in sub)          # noqa: E731
            out("  %-2s fresh: livelock all %d searcher %d | stuck all %d searcher %d | rtb no-progress all %d "
                "searcher %d" % (arm, t("uav_livelock_all"), t("os_i2_livelock"), t("uav_stuck_all"), t("os_i2_stuck"),
                                 t("rtb_noprog_all"), t("os_rtb_noprog")))
    out("ACTED footprint (d['mv_events']; live = the fix ran) per arm and set: cells with a live / shadow event per fix")
    for arm in ARMS:
        for s in ("set1", "set2", "set3", "set4"):
            sub = [r for r in recs if r["cell"]["set"] == s and usable(r, arm)]
            if sub:
                out("  %-2s %s %s" % (arm, s, " ".join("%s live %d shadow %d" % (
                    k, sum(1 for r in sub if r["g"][arm]["num"].get("live_" + k)),
                    sum(1 for r in sub if r["g"][arm]["num"].get("shadow_" + k))) for k in ("a", "b", "c", "C4", "C5"))))
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
                out("     %s->%s first difference step %s (%s), first acting step %s" % (x, y, p["D"], p["what"][:4],
                                                                                        p["s"]))
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
    for arm in ("M", "MU"):
        near = [(r["cell"]["id"], x) for r in fresh_recs(recs) if usable(r, arm) for x in r["g"][arm]["lists"].get(
            "near_a", [])]
        out("DIAG %s route_blocked raises / strandings within 6 steps after an (a)-acted step: %s" % (arm, near[:20] or
                                                                                                    "none"))
        sh = [(r["cell"]["id"], x) for r in fresh_recs(recs) if usable(r, arm) for x in r["g"][arm]["lists"].get(
            "shelter_hold", [])]
        out("DIAG %s SHELTER / HOLD episodes [kind, unit, victim, first, last, outcome]: %s" % (arm, sh[:20] or "none"))
        exc = [(r["cell"]["id"], x) for r in fresh_recs(recs) if usable(r, arm) for x in r["g"][arm]["lists"].get(
            "zm_c_excluded", [])]
        out("  Zm-c excluded (casualty / rescue-completion) unassigns of carriers in %s: %s" % (arm, exc[:12] or "none"))
    dw = [(r["cell"]["id"], a, x) for r in recs for a, g in r["g"].items() if g.get("usable")
          for x in g["lists"].get("deferred_writeoffs", [])]
    out("DIAG write-offs of a previously deferred victim: %s" % (dw or "none"))
    sec_m1(recs)
    sec_mu3(recs)
    sec_mu4(recs)
    sec_dp_items(recs, C)


# ------------------------------------------------------------------------------------------------ 6.R1-6.R4 (reported)
IN_SAMPLE = ("set1", "set2")


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
    _subhead("6.R1 REPORTED - M1 / M1c DETECTION-TO-RESCUE TIME (16.9, as DPR 14.7; never a guard - urgency may lengthen "
             "some times): M1 per victim rescued in BOTH arms, delta = (rescue - detection) in Y minus in X (paired by "
             "cell and victim id; CRN); m_c = the cell's mean delta; T = the UNWEIGHTED mean of m_c. M1c: every victim "
             "detected in both arms, (rescue step or the censor 361; smoke: the run's last step + 1) - detection, the "
             "same per-cell statistic")
    for x, y, fresh in [(a, b, True) for a, b in (("0", "U"), ("0", "M"), ("0", "MU"), ("M", "MU"), ("U", "MU"))] + [
            ("0", "U", False)]:
        cells = _paired(recs, x, y, fresh)
        sets = FRESH if fresh else IN_SAMPLE
        lbl = "FRESH sets 3-4" if fresh else "IN-SAMPLE sets 1-2, W1 / W3 replay"
        if not cells:
            if fresh:
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
    _subhead("6.R2 REPORTED - MU3 VERDICT QUALITY (16.9): every U1 decision record (d['ud']['decisions']: each waiting "
             "detected victim at a qualifying kick; in an arm with U1 off, the SHADOW verdict) against her outcome - "
             "picked up before her DECISION cell burned (strictly earlier), after, or never; died or not. The "
             "estimator's bias at the decisions from the CURRENT-cell T: T - (first burn of the decision cell - step), "
             "censored at 360, and T - (death - step). Harrell C at the decisions (predictor T; target the first burn, "
             "and death censored at rescue completion or 360) with a SEED-level bootstrap: clusters = seeds (the ring "
             "and uniform runs of a seed share the fire), %d draws, Random(%d), 95 %% percentile interval (Part 1 4.2)"
             % (BOOT_DRAWS, BOOT_SEED))
    for arm in ARMS:
        for gname, sets in (("fresh sets 3-4", FRESH), ("in-sample sets 1-2", IN_SAMPLE)):
            sub = [r for r in recs if r["cell"]["set"] in sets and usable(r, arm)]
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
            out("  arm %-2s %s (%d runs, %d seeds): decision records %d (promotable P %d, deferred D %d)" % (
                arm, gname, len(sub), len(stats), nP + nD, nP, nD))
            for ver in ("P", "D"):
                out("     %s: %s" % (ver, " | ".join("%s %d (died %d)" % (
                    pc, vc[(ver, pc, "died")] + vc[(ver, pc, "survived")], vc[(ver, pc, "died")])
                    for pc in ("picked before burn", "picked after burn", "never picked"))))
            q1b, mb, q3b = iqr(burn)
            q1d, md_, q3d = iqr(death)
            out("     bias T - (first burn - step): median %s IQR [%s, %s] n %d (first burn censored at the horizon 360 "
                "- smoke: the run's last step: %d; no estimate, T infinite: %d) | T - (death - step): median %s IQR "
                "[%s, %s] n %d" % (
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
    _subhead("6.R3 REPORTED - MU4 FIREFIGHTER EXPOSURE (16.9; 12.2 G4) per arm and set, each item split by BIND LEG (a "
             "successful assign of unit u to v, until u's next assign): legs bound at a U1-divergent kick (U1 arms: the "
             "kick's divergent flag; U1-off arms: div_shadow, the kick where U1 would have bound another victim) vs the "
             "other legs vs no leg; and legs where a movement fix ACTED (d['mv_events'] of that unit and victim inside "
             "the leg: live in M / MU, the would-act shadow in 0 / U) vs the others. Deaths by the unit's state on its "
             "last row before death (_dp_analyze.ff_state); an idle / rb_unbound death is charged to the unit's latest "
             "bind")
    for arm in ARMS:
        for s in FRESH + IN_SAMPLE:
            sub = [r for r in recs if r["cell"]["set"] == s and usable(r, arm)]
            if not sub:
                continue
            tab = collections.defaultdict(collections.Counter)
            for r in sub:
                for k, v in (r["g"][arm].get("mu4") or {}).items():
                    tab[k].update(v)
            lg = tab.get("legs") or {}
            out("  arm %-2s %s (%d runs): bind legs %d (at a U1-divergent kick %d; with a movement fix ACTED %d)" % (
                arm, s, len(sub), lg.get("n", 0), lg.get("div", 0), lg.get("acted", 0)))
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
    _subhead("6.R4 REPORTED - THE DISPATCH ROUND'S ITEMS OF 16.8 (U1 does not touch binding mechanics; never gated): "
             "G-B (a)(b)(d) from dp.binders / dp.invariant; G-T(b) every return with the AMENDED outside events (Z5's "
             "gt_returns_amended); M6 write-offs and closed-route assigns (dp.commands); M3 idle-while-waiting from "
             "dp.m3a / dp.waiting via DPR's rb_figures with live=False in every arm (no J ledger exists here, so the "
             "latch-cap split is DPR's counterfactual reading on the rebuilt ledger)")
    comps = [((x, y), C[(x, y)]["cells"], FRESH, "FRESH") for x, y in COMPARISONS]
    ins = _paired(recs, "0", "U", fresh=False)
    if ins:
        comps.append((("0", "U"), ins, IN_SAMPLE, "IN-SAMPLE sets 1-2"))
    for (x, y), cells, sets, lbl in comps:
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
        sub = [r for r in recs if usable(r, arm)]
        if not sub:
            continue
        gt = collections.Counter()
        for r in sub:
            for k, v in r["g"][arm]["num"].items():
                if k.startswith("gt_b_"):
                    gt[k[5:]] += v
        fails = [(r["cell"]["id"], {k: v for k, v in r["g"][arm]["rb_checks"].items() if v and not k.startswith("n_")})
                 for r in sub if r["g"][arm].get("rb_fail")]
        out("  arm %-2s all sets (%d runs): G-T(b) returns by outside events %s | R-B tooling checks failing in %d "
            "run(s)%s" % (arm, len(sub), dict(gt) or "none", len(fails), (": %s" % fails[:3]) if fails else ""))
        for key, label in (("gb_b", "G-B (b) instances"), ("gb_d", "G-B (d) invariant lines"),
                           ("assign_closed", "closed-route assigns"), ("casualty_writeoffs", "casualty write-offs")):
            xs = [(r["cell"]["id"], x) for r in sub for x in r["g"][arm]["lists"].get(key, [])]
            if xs:
                out("    %s (%d): %s" % (label, len(xs), xs[:6]))


def sec_evidence(ev):
    head("7 EVIDENCE (16.11) - each case OFF (W1) and ON (W4) in its original configuration; described, not gated")
    for e in ev:
        out("-- case %s, CRN %s" % (e["case"], "on" if e["crn"] == "c" else "off"))
        for arm in ("0", "1"):
            g = e["g"].get(arm)
            if g is None:
                out("   %s MISSING" % ("OFF" if arm == "0" else "ON"))
                continue
            ev_ = g.get("eval") or {}
            out("   %s %s | rescued %s dead %s ff_deaths %s terminal %s" % (
                "OFF" if arm == "0" else "ON ", g["label"], ev_.get("rescued"), ev_.get("dead"),
                ev_.get("firefighter_deaths"), g.get("terminal")))
            for ln in (g.get("so_triage") or [])[:8]:
                out("       %s" % ln)
            if g.get("kind") != "harness":
                for K in g.get("kicks") or []:
                    if K.get("qualifies"):
                        out("       qualifying kick step %s site %s W %s F %s U1 %s index %s rec %s acc %s would bind: "
                            "U1 %s index %s | bound %s%s" % (
                                K.get("step"), K.get("site"), [w[0] for w in K.get("W") or []],
                                [f[0] for f in K.get("F") or []], K.get("u1"), K.get("index"), K.get("rec"),
                                K.get("acc", "n/a (v1)"), u1_wb(K), idx_wb(K), K.get("bound"),
                                " DIVERGENT" if K.get("divergent") or K.get("div_shadow") else ""))
        if e["pair"] is not None:
            p = e["pair"]
            out("   OFF vs ON: %s | first difference step %s (%s) | divergent step %s | Z1 %s" % (
                "identical" if p["ident"] else "differ", p["D"], p["what"][:4], p["s"],
                "holds" if not p["viol"] else "VIOLATED %s" % p["viol"]))
        if e["z0"] is not None:
            out("   Z0 OFF vs the dispatch round's dpE record: %s" % ("identical" if not e["z0"][0] else
                                                                     "DIFFERS %s" % e["z0"][0][:6]))


def sec_decision(recs, st, s1, zres, C, opts):
    head("8 DECISION (22.8.5; FULL / HARMLESS of 22.8.1 with S5 = 23.2)")
    incomplete = bool(st["missing"] or st["invalid"])
    arm0_stop = bool(zres["stop"]) or bool(st["stop"])
    rm, ru = C[("0", "M")]["full"], C[("0", "U")]["full"]
    rmu = rmu_verdict(C[("0", "MU")]["full"], C[("M", "MU")]["harmless"], C[("U", "MU")]["harmless"])
    dd0 = sum(r["g"]["0"]["num"]["DD"] for r in C[("0", "M")]["cells"])
    red_m = dd0 - sum(r["g"]["M"]["num"]["DD"] for r in C[("0", "M")]["cells"])
    dd0u = sum(r["g"]["0"]["num"]["DD"] for r in C[("0", "U")]["cells"])
    red_u = dd0u - sum(r["g"]["U"]["num"]["DD"] for r in C[("0", "U")]["cells"])
    outcome, default = decide(arm0_stop or s1["fail"], rm, ru, rmu, red_m, red_u)
    out("S1 IDENTITY %s | arm-0 STOP items %d" % ("PASS" if s1["pass"] else "FAIL" if s1["fail"] else "INCOMPLETE",
                                                 len(zres["stop"]) + len(st["stop"])))
    out("R-M  = FULL(0 -> M)                                        : %s" % rm)
    out("R-U  = FULL(0 -> U)                                        : %s" % ru)
    out("R-MU = FULL(0 -> MU) %s AND HARMLESS(M -> MU) %s AND HARMLESS(U -> MU) %s : %s" % (
        C[("0", "MU")]["full"], "PASS" if C[("M", "MU")]["harmless"] else "FAIL",
        "PASS" if C[("U", "MU")]["harmless"] else "FAIL", rmu))
    out("pooled DD reduction (0 - Y): M %+d, U %+d" % (red_m, red_u))
    zm = {}
    for k, z in (("a", "Zm-a"), ("b", "Zm-b"), ("c", "Zm-c")):
        zm[k] = not any(f[0] == z and f[1] in ("M", "MU") for f in zres["fails"])
    acted = {k: {s: sum(1 for r in fresh_recs(recs) if r["cell"]["set"] == s and usable(r, "M")
                        and r["g"]["M"]["acted_live"].get(k)) for s in FRESH} for k in ("a", "b", "c")}
    sw = movement_switch_verdicts(outcome, default, rm, rmu, zm, acted)
    out("per movement switch (fresh cells of arm M with a live ACTED event per set: %s; Zm holds: %s):" % (acted, zm))
    for k, name in (("a", "FF_APPROACH_PATH"), ("b", "FF_RETREAT_KEEP_APPROACH"), ("c", "FF_CARRY_REPLAN")):
        out("  %-25s %s" % (name, sw[k]))
    out("  DISPATCH_URGENCY          %s (R-U %s; U1 gets no second chance through FULL(M -> MU))" % (
        "ON - recommended; STOP for confirmation" if outcome in (2, 5) or (outcome == 3 and default == "U")
        else "ships 0 (code may merge at 0: verdict NOT SHOWN)" if ru == "NOT SHOWN"
        else "ships 0 (NOT READY: optimise, re-measure on 8 value-identical cells, re-apply the rules)"
        if ru == "NOT READY" else "ships 0", ru))
    if rm == "NOT READY":
        out("  movement block NOT READY: optimised, cost re-measured on 8 value-identical cells, rules re-applied "
            "(17.3.4); its code is never discarded on S6 alone")
    # I(c), reported
    ic = []
    u1div = []
    for r in fresh_recs(recs):
        if all(usable(r, a) for a in ARMS):
            y = {a: r["g"][a]["num"]["DD"] for a in ARMS}
            ic.append(y["MU"] - y["M"] - y["U"] + y["0"])
            if (("0", "U") in r["pairs"] and r["pairs"][("0", "U")]["s"] is not None) or (
                    ("M", "MU") in r["pairs"] and r["pairs"][("M", "MU")]["s"] is not None):
                u1div.append((r["cell"]["id"], ic[-1]))
    out("I(c) = Y_MU - Y_M - Y_U + Y_0 (DD; REPORTED, never gated): sum %+d over %d cells; where U1 diverged (%d cells): "
        "%s" % (sum(ic), len(ic), len(u1div), u1div[:16]))
    # scenario STOP (diagnostic)
    for x, y in (("0", "M"), ("0", "U"), ("0", "MU")):
        cells = C[(x, y)]["cells"]
        sc = {s: (sum(r["g"][x]["num"]["rescued"] for r in cells if r["cell"]["scen"] == s),
                  sum(r["g"][y]["num"]["rescued"] for r in cells if r["cell"]["scen"] == s)) for s in "ABCD"}
        drop = [(s, a, b) for s, (a, b) in sc.items() if b - a <= -2]
        out("scenario rescued %s -> %s: %s | %s" % (x, y, {s: "%d->%d" % v for s, v in sc.items()},
                                                    "SCENARIO STOP (DIAGNOSTIC, 22.8.4: reported with its diagnosis; "
                                                    "the verdict stands) %s" % drop if drop else "no fall of 2 or more"))
    verdict = "OUTCOME %d: %s" % (outcome, OUTCOME_TEXT[outcome])
    if outcome == 3:
        verdict += " Default here: %s." % default
    if not s1["pass"] and not s1["fail"]:
        verdict = "INCOMPLETE (S1 not established: the identity wave is incomplete) - would be %s" % verdict
    if incomplete:
        verdict = ("PROVISIONAL (incomplete data, --allow-incomplete) - %s" % verdict if opts.allow_incomplete else
                   "INCOMPLETE (%d missing, %d invalid runs - re-run them; no outcome is read)" % (len(st["missing"]),
                                                                                                  len(st["invalid"])))
    if opts.smoke:
        verdict = "SMOKE - NOT A SCREEN (computed: %s)" % verdict
    out("")
    out("VERDICT: %s" % verdict)
    return outcome


# ================================================================================================ outcome gate (smoke)
SMOKE_SUPPRESSED = "SMOKE: outcome sections suppressed (22.6.3: no movement outcome on sets 1-2 is read)"


def print_s6(x, y, res):
    """The S6 COST line of one comparison: median R and p99 per added switch group - no verdict, no outcome count."""
    out("  S6 COST %s -> %s: %s" % (x, y, " | ".join(
        "%s median R %s p99 %s ms (runs %d, calls %d)" % (
            k, fmt(None if v["median_R"] is None else 100 * v["median_R"], "%.3f%%"), fmt(v["p99"], "%.2f"),
            v["n_runs"], v["n_calls"]) for k, v in res["S6_detail"].items()) or "no added switch"))


ZEROS_ONLY_LINE = ("ZEROS-ONLY (16.12 wave check): sections 0-3 and validity only - no outcome section and no verdict "
                   "printed")


def incomplete_line(st):
    return ("INCOMPLETE (%d missing, %d invalid runs) - the outcome sections are NOT printed (16.6 / 16.12: no screen "
            "outcome is looked at before every run is valid and present); re-run them, or pass --allow-incomplete for a "
            "PROVISIONAL reading" % (len(st["missing"]), len(st["invalid"])))


def stop_out(opts, text):
    """A STOP after section 1, 2 or 3: a VERDICT line, or (--zeros-only, which prints no verdict) a stop condition."""
    if getattr(opts, "zeros_only", False):
        out("ZEROS-ONLY STOP CONDITION: %s" % text)
    else:
        head("8 DECISION")
        out("VERDICT: %s" % text)


def outcome_sections(recs, ev, st, s1, zres, opts):
    """Sections 4-8, gated (R2 M-3, 22.6.3):
    - --zeros-only (the 16.12 wave check): nothing after section 3 but ZEROS_ONLY_LINE;
    - --smoke: only each comparison's S6 cost line (R and p99), then SMOKE_SUPPRESSED - no literal clause, sign-tested
      count, S2-S5, FULL / HARMLESS, M8, measure, DIAG, evidence outcome or decision;
    - a missing or INVALID run without --allow-incomplete: the INCOMPLETE line only;
    - otherwise every section (PROVISIONAL with --allow-incomplete when runs are missing or invalid)."""
    if getattr(opts, "zeros_only", False):
        out(ZEROS_ONLY_LINE)
        return None
    s1_pass = not s1["fail"] or bool(opts.smoke)
    if not opts.smoke and (st["missing"] or st["invalid"]) and not getattr(opts, "allow_incomplete", False):
        head("8 DECISION")
        out("VERDICT: %s" % incomplete_line(st))
        return None
    if opts.smoke:
        head("4 COMPARISONS - SMOKE: the S6 COST line per comparison only (median R and p99; no verdict)")
        for x, y in COMPARISONS:
            print_s6(x, y, comparison(recs, x, y, zres["fails"], s1_pass))
        out(SMOKE_SUPPRESSED)
        return None
    C = sec_comparisons(recs, zres, s1_pass)
    sec_m8(recs, opts)
    sec_measures(recs, C, opts)
    sec_evidence(ev)
    return sec_decision(recs, st, {"pass": s1["pass"], "fail": s1["fail"]}, zres, C, opts)


# ================================================================================================ main
def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--out")
    ap.add_argument("--head")
    ap.add_argument("--part2-notes")
    ap.add_argument("--allow-incomplete", action="store_true")
    ap.add_argument("--smoke")
    ap.add_argument("--smoke-cell", default="set1/ring/D_W")
    ap.add_argument("--smoke-files", default="")
    ap.add_argument("--zeros-only", action="store_true")
    opts = ap.parse_args(_ARGV[1:])
    opts.smoke_files = dict(x.split("=", 1) for x in opts.smoke_files.split(",") if "=" in x)
    if not opts.smoke and not (opts.head and opts.part2_notes):
        ap.error("--head <Part 2 commit> and --part2-notes <path> are required outside --smoke (16.6, 15.5)")
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
        recs = process(cells, opts, queues)
        ev = [] if opts.smoke else process_evidence(opts, queues)
        if opts.smoke and ("E0" in opts.smoke_files or "E1" in opts.smoke_files):
            ev = smoke_evidence(opts)
        st = sec_prov(recs, ev, opts)
        if st["seed"]:
            out("STOP: a run's scenario / wind / seed differs from its frozen cell (seed-selector rule)")
            return 2
        s1 = sec_z0(recs, ev, opts)
        if s1["fail"] and not opts.smoke:
            stop_out(opts, "STOP (S1 IDENTITY FAILED) - %s" % OUTCOME_TEXT[1])
            return 1
        if st["stop"] and not opts.smoke:
            stop_out(opts, "STOP - a crash or early stop in arm 0 is a defect of the base code: diagnose before any "
                     "outcome is read (16.6)")
            return 1
        zres = sec_zeros(recs, ev, st, opts)
        if zres["stop"] and not opts.smoke:
            stop_out(opts, "STOP - %s" % OUTCOME_TEXT[1])
            return 1
        # S1 has not failed here (a failure STOPs above): an INCOMPLETE identity wave is carried as "would be"
        outcome_sections(recs, ev, st, s1, zres, opts)
    finally:
        if opts.out:
            with open(opts.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(_LINES) + "\n")
    return rc


def smoke_evidence(opts):
    """Smoke only: an E0 / E1 pair from --smoke-files exercises the evidence path (no reference comparison)."""
    e = {"case": "smoke", "crn": "c", "g": {}, "prov": {}, "crash": {}, "missing": [], "z0": None, "pair": None,
         "ref_bad": None}
    for arm in ("0", "1"):
        f = opts.smoke_files.get("E" + arm)
        if not f:
            e["missing"].append(arm)
            continue
        p = os.path.join(opts.smoke, f)
        d = load_run(p)
        why, crash, _s = prov_run(d, p, None, None, opts)
        e["prov"][arm], e["crash"][arm] = why, crash
        e["g"][arm] = digest(d, "E" + arm, "E%s_smoke" % arm, p, "evidence")
    if len(e["g"]) == 2:
        e["pair"] = z1_u1(e["g"]["0"], e["g"]["1"])
    for g in e["g"].values():
        slim(g)
    return [e]


if __name__ == "__main__":
    sys.exit(main())
