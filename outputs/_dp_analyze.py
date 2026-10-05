"""Dispatch round Part 3 analyzer - PRE-REGISTERED (outputs/dispatch_part1.txt 14.5, 14.6, 14.7, 15; amendment A1
21.2(f) G-N / G-OF reported additions, 21.2(g) the M8 bias definition, 21.2(h) M9; amendment A2 22.2 R-B (dp0's
ledger rebuilt from its own assigns, the latch cap in both arms, three tooling checks), 22.3 R-C (dp0 drives M8's
trigger), 22.4 P2-7 / 22.5(3) (stage-4 binds apart)). READ-ONLY: it reads run files from this worktree's outputs/
(or --smoke DIR) and writes nothing but --out. The R-B and R-C rules are pure functions (rb_ledgers, rb_figures,
m8_classify, m8_trigger) checked on hand-built records by outputs/_dp_analyze_selftest.py (A2 22.5(4)).

usage (dispatch worktree root):
  .venv/Scripts/python.exe outputs/_dp_analyze.py [--out REPORT] [--smoke DIR] [--suite-log PATH] [--allow-incomplete]
                                                  [--gate-ref TAG] [--head-b SHA] [--head-dp SHA] [--smoke-gate TAG]
  --smoke DIR         DIR holds ref.json (= dpR), dp0.json, dp1.json of ONE cell (+ <name>.stdout.txt): every
                      computation on that cell; completeness, 360-step and queue-signature checks relaxed
  --suite-log PATH    the full-suite pytest log for G-S / G-INV (else NOT RUN)
  --allow-incomplete  compute on what exists; the verdict is then PROVISIONAL (without it: INCOMPLETE)
  --gate-ref TAG      the route_blocked gate reference tag (default dpGR; 14.5 - sec_rbgate hard-codes fx3gS)
  --head-b / --head-dp  expected head prefixes of dpR / of dp0 + dp1; a mismatch is INVALID when given
  --smoke-gate TAG    smoke only: exercise the gate-shard code on an existing shard tag (the same files on every side)
exit: 0 report done; 1 S1 STOP (identity failed - nothing else is read); 2 REFUSED (section 15 differs from the Part 1
commit, or outputs/_dp_seeds.txt is unusable).

Sections: 0 HEADER  1 LOAD + PROV (14.5)  2 G-ID (14.6)  3 GATES (14.6)  4 MEASURES (14.7, 21.2(g)(h))
          5 EVIDENCE (14.8)  6 DECISION (15).
Conventions: rows_* index t = the state after step t+1. Detection steps from <out minus .json>.stdout.txt
'[Victim Detection]' lines (never rows_vic, which reads 'candidate' after detection). Rescue step = first rows_vic
managed == 'rescued'. Run files are digested one at a time (a 360-step record is ~15 MB in memory); only the digests
are kept.
Reused measures (imported functions, never a main()): _sd_analyze.analyze (I2 firefighter stuck / livelock /
no-progress, I5), _fb3_analyze.searcher_o / ff_episodes / det_times, _fx3_pockets (via searcher_o),
_ut_analyze._last_detection, _ut_analyze2.ff_status_track, _fx3r_analyze.FIELDS / DET_RE / strip_rb,
_dp_queue line builders, _fb3_queue.cells, _mf2_pool.signature. _bp_analyze's prov_check / ident / first_path are
replicated, not imported (its module guard parses argv and calls git at import).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(HERE)
SHARED_CHECKOUT = r"E:\Projects\SAS"      # the shared main checkout - never an arm's repo (worktree rule)
sys.path.insert(0, HERE)
_ARGV = sys.argv
sys.argv = _ARGV[:1]                       # _fb3_analyze / _ut_analyze* read sys.argv at import
try:
    import _fx3r_analyze as R              # noqa: E402  FIELDS, DET_RE, strip_rb
    import _fb3_analyze as A               # noqa: E402  searcher_o, ff_episodes, det_times
    import _sd_analyze as SD               # noqa: E402  analyze()
    import _ut_analyze as U                # noqa: E402  _last_detection
    import _ut_analyze2 as U2              # noqa: E402  ff_status_track
    import _dp_queue as Q                  # noqa: E402  probe_line, shards, evidence (line builders only)
    import _fb3_queue as FQ                # noqa: E402  cells
    import _mf2_pool as POOL               # noqa: E402  signature
finally:
    sys.argv = _ARGV

PART1 = "2f0509dc"
AMENDMENTS = ("1cf70598", "9b219455", "695fa4b1")   # A1, the A1 ruling, A2 (dispatch_part1.txt sections 21-22)
A2 = "695fa4b1"
H = 360
STUCK, WIN = 20, 30                        # _sd_analyze I2 thresholds (14.6 G-OF)
PLACES = (("r", "ring", 0, "set1"), ("r2", "ring", 0, "set2"),
          ("u", "uniform", 1, "set1"), ("u2", "uniform", 1, "set2"))
SMOKE_FILES = {"dpR": "ref.json", "dp0": "dp0.json", "dp1": "dp1.json"}
ON = {"DISPATCH_JOINT": 1, "DISPATCH_REASSIGN": 1}
ON_SETS = ["--set", "DISPATCH_JOINT=1", "--set", "DISPATCH_REASSIGN=1"]
SHARDS = (("a", "east"), ("b", "east"), ("c", "east"), ("s", "south"))
J_ONLY = ("probe", "switches", "src_sha", "j_calls", "j_events", "ledger", "timing", "rc_chain", "j_detail",
          "j_timing")
EXPECTED_FAILS = {"tests/test_uav_sector_assignment.py::test_fire_tracker_uavs_receive_different_target_sets"}
TINV = "tests/test_dispatch_information.py::test_tinv_invariants_hold_at_every_frame_of_a_real_run"
TERMINAL = ("rescued", "dead", "unreachable")
I2_KINDS = (("stuck_approach", "I2_ff_stuck_approach"), ("stuck_carry", "I2_ff_stuck_carry"),
            ("livelock_approach", "I2_ff_livelock_approach"), ("livelock_carry", "I2_ff_livelock_carry"),
            ("noprog_approach", "I2_ff_no_progress_approach"))
FF_STATES = ("approach", "carry", "idle", "rb_unbound")
DISPATCH_RE = re.compile(r"^\[Dispatch\] FF-(\S+) assigned to (\S+) reason=(\S+) manhattan_dist=(\S+)")
STEP_RE = re.compile(r"\bstep=(\d+)")
KEYS16 = {s + "_" + w for s in "ABCD" for w in "ENSW"}
GROUPS = (("pooled", lambda c: True), ("set1", lambda c: c["set"] == "set1"), ("set2", lambda c: c["set"] == "set2"),
          ("ring", lambda c: c["plc"] == "ring"), ("uniform", lambda c: c["plc"] == "uniform"))
SCEN_GROUPS = tuple((s, (lambda s_: lambda c: c["scen"] == s_)(s)) for s in "ABCD")

_LINES: list[str] = []


def out(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    _LINES.append(s)


def head(title):
    out("=" * 118)
    out(title)


# ================================================================================================ small helpers
def same_path(a, b):
    if not a or not b:
        return False
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def git(*args):
    try:
        r = subprocess.run(["git", "-C", WT, *args], capture_output=True, timeout=120)
        return r.returncode, r.stdout
    except Exception as exc:                # noqa: BLE001 - reported, never raised
        return -1, repr(exc).encode()


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


def first_state_div(ga, gb):
    """First step (t + 1) at which the per-step rows differ (ff / vic / uav), or None."""
    best = None
    for k in ("h_ff", "h_vic", "h_uav"):
        fd = first_div(ga.get(k) or [], gb.get(k) or [])
        if fd is not None and (best is None or fd[0] < best[0]):
            best = (fd[0], k[2:])
    return None if best is None else (best[0] + 1, best[1])


def first_cmd_div(ga, gb):
    """First dispatch decision (assign / unassign: step, unit, victim, success; reasons ignored) that differs."""
    fd = first_div(ga.get("cmd_seq") or [], gb.get("cmd_seq") or [])
    if fd is None:
        return None
    i, x, y = fd
    steps = [z[0] for z in (x, y) if z is not None]
    return min(steps) if steps else None, x, y


# ================================================================================================ statistics (pure)
def cell_means(pairs):
    """{cell: [delta, ...]} -> {cell: m_c} for cells with at least one pair (14.7 M1)."""
    return {c: sum(v) / len(v) for c, v in pairs.items() if v}


def drop_most_negative(vals):
    if not vals:
        return []
    v = sorted(vals)
    return v[1:]


def s3_statistic(m_by_set, n_cells, min_cells=24):
    """Section 15 S3 on {set: {cell: m_c}}: T(set) = unweighted mean of m_c; each set < 0 and < 0 after removing
    its most negative m_c; T(pooled) < 0 after removing the overall most negative m_c; NOT SHOWN when a set has fewer
    than min_cells of its n_cells contributing."""
    res = {"n": {}, "T": {}, "loo": {}}
    allv = []
    for s in ("set1", "set2"):
        vals = list((m_by_set.get(s) or {}).values())
        allv += vals
        res["n"][s] = len(vals)
        res["T"][s] = mean(vals)
        res["loo"][s] = mean(drop_most_negative(vals))
    res["T"]["pooled"] = mean(allv)
    res["loo"]["pooled"] = mean(drop_most_negative(allv))
    lt0 = lambda x: x is not None and x < 0              # noqa: E731
    if any(res["n"][s] < min_cells for s in ("set1", "set2")):
        res["verdict"] = "NOT SHOWN (fewer than %d of %d cells contributing: set1 %d, set2 %d)" % (
            min_cells, n_cells, res["n"]["set1"], res["n"]["set2"])
        res["pass"] = False
    else:
        ok = (lt0(res["T"]["set1"]) and lt0(res["T"]["set2"]) and lt0(res["loo"]["set1"]) and lt0(res["loo"]["set2"])
              and lt0(res["loo"]["pooled"]))
        res["pass"] = bool(ok)
        res["verdict"] = "PASS" if ok else "FAIL"
    return res


def s4_statistic(m_by_set):
    """Section 15 S4: the same statistic (T, the unweighted per-cell mean) on M1c is <= 0 pooled and in each set."""
    res = {"n": {}, "T": {}}
    allv = []
    for s in ("set1", "set2"):
        vals = list((m_by_set.get(s) or {}).values())
        allv += vals
        res["n"][s] = len(vals)
        res["T"][s] = mean(vals)
    res["T"]["pooled"] = mean(allv)
    le0 = lambda x: x is not None and x <= 0             # noqa: E731
    res["pass"] = all(le0(res["T"][k]) for k in ("set1", "set2", "pooled"))
    res["verdict"] = "PASS" if res["pass"] else "FAIL"
    return res


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


# ================================================================================================ G-T (pure)
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


# ================================================================================================ R-B (pure; A2 22.2)
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


# ================================================================================================ M8 (pure; R-C, A2 22.3)
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


def m8_trigger(by_set):
    """R-C (A2 22.3): the urgency-round trigger, evaluated on dp0 only. by_set = {set: (feasible-critical, futile)}.
    MET iff, in BOTH seed sets, there is at least one detected-victim death AND feasible-critical deaths are at least
    25% of them (a set with no detected-victim death does not meet it)."""
    return all(fc + fu > 0 and 4 * fc >= fc + fu for fc, fu in (by_set.get(s, (0, 0)) for s in ("set1", "set2")))


# ================================================================================================ 0 HEADER
def section15(text):
    """The text between the '15. DECISION RULE' header block and the '16. RE-CHECK' header block."""
    lines = text.replace("\r\n", "\n").split("\n")
    i = next((k for k, ln in enumerate(lines) if ln.startswith("15. DECISION RULE")), None)
    j = next((k for k, ln in enumerate(lines) if ln.startswith("16. RE-CHECK")), None)
    if i is None or j is None or j <= i + 2:
        return None
    if not (lines[i + 1].startswith("=====") and lines[j - 1].startswith("=====")):
        return None
    return "\n".join(lines[i + 2:j - 1])


def outcome_bullets(sec15):
    """The OUTCOMES bullets of section 15 as {first words: full text}."""
    bullets, cur = [], None
    for ln in sec15.split("\n"):
        if ln.startswith("  - "):
            cur = [ln[4:].strip()]
            bullets.append(cur)
        elif cur is not None and ln.startswith("    ") and ln.strip():
            cur.append(ln.strip())
        else:
            cur = None
    return [" ".join(b) for b in bullets]


def sec_header(opts):
    head("DISPATCH ROUND - PART 3 ANALYZER (outputs/dispatch_part1.txt 14.5-14.7 and 15; amendment A1 21.2(f)(g)(h);"
         " amendment A2 22.2-22.5)")
    if opts.smoke:
        out("SMOKE - NOT A SCREEN  (one cell from %s; completeness / 360-step / queue-signature checks relaxed)" % (
            opts.smoke,))
    rc, txt = git("log", "-1", "--format=%H %ad %s", "--date=short", PART1)
    out("Part 1 (pre-registration) commit: %s  %s" % (PART1, txt.decode("utf-8", "replace").strip() if rc == 0 else
                                                       "NOT FOUND"))
    for c in AMENDMENTS:
        rc, txt = git("log", "-1", "--format=%H %ad %s", "--date=short", c)
        out("amendment commit:                 %s  %s" % (c, txt.decode("utf-8", "replace").strip() if rc == 0 else
                                                          "NOT FOUND"))
    if opts.head_dp:
        # A2 22.5(5): the commit that builds A2 is Part 3's --head-dp; it must descend from the A2 amendment commit
        rc, txt = git("log", "-1", "--format=%H %ad %s", "--date=short", opts.head_dp)
        anc, _ = git("merge-base", "--is-ancestor", A2, opts.head_dp)
        out("A2 build commit (= --head-dp):    %s  %s | descends from A2 %s: %s" % (
            opts.head_dp, txt.decode("utf-8", "replace").strip() if rc == 0 else "NOT FOUND", A2,
            "yes" if anc == 0 else "NO"))
        if anc != 0 and not opts.smoke:
            out("REFUSED: --head-dp %s does not descend from the A2 amendment %s (22.5(5))" % (opts.head_dp, A2))
            return None
    rc, head_b = git("rev-parse", "HEAD")
    out("analyzer worktree %s at %s" % (WT, head_b.decode().strip() if rc == 0 else "?"))
    rc, blob = git("show", "%s:outputs/dispatch_part1.txt" % PART1)
    if rc != 0:
        out("REFUSED: cannot read outputs/dispatch_part1.txt at %s" % PART1)
        return None
    s_old = section15(blob.decode("utf-8", "replace"))
    try:
        with open(os.path.join(HERE, "dispatch_part1.txt"), encoding="utf-8") as fh:
            s_new = section15(fh.read())
    except OSError:
        s_new = None
    if s_old is None or s_new is None or s_old != s_new:
        out("REFUSED: section 15 of the working outputs/dispatch_part1.txt differs from %s (or is unreadable) - no edit"
            " of a pre-registered rule after data (13.1 step 0)" % PART1)
        return None
    out("section 15 identical to %s (sha256 %s, %d lines)" % (
        PART1, hashlib.sha256(s_new.encode()).hexdigest()[:16], s_new.count("\n") + 1))
    return s_new


def load_seeds():
    """outputs/_dp_seeds.txt -> {set: [[key, scen, wind, seed], ...]} or None (STOP)."""
    path = os.path.join(HERE, "_dp_seeds.txt")
    try:
        frozen = load_json(path)
    except Exception as exc:                 # noqa: BLE001
        out("STOP: outputs/_dp_seeds.txt unreadable (%r)" % (exc,))
        return None
    bad = []
    if not isinstance(frozen, dict) or set(frozen) != {"set1", "set2"}:
        bad.append("keys %s" % (sorted(frozen) if isinstance(frozen, dict) else type(frozen).__name__))
    else:
        for s in ("set1", "set2"):
            rows = frozen[s]
            if not isinstance(rows, list) or len(rows) != 16:
                bad.append("%s has %s cells" % (s, len(rows) if isinstance(rows, list) else "no"))
                continue
            keys = set()
            for row in rows:
                if not (isinstance(row, list) and len(row) == 4 and all(isinstance(x, str) for x in row)):
                    bad.append("%s row %r" % (s, row))
                    continue
                key, scen, wind, seed = row
                if (key not in KEYS16 or scen != key[0] or not wind or wind[0].upper() != key[2]
                        or not seed.isdigit()):
                    bad.append("%s row %r" % (s, row))
                keys.add(key)
            if keys != KEYS16:
                bad.append("%s keys %s" % (s, sorted(keys)))
    if bad:
        out("STOP: outputs/_dp_seeds.txt does not parse to set1 / set2 of 16 cells each: %s" % bad[:6])
        return None
    out("frozen cells outputs/_dp_seeds.txt: set1 %d, set2 %d (seeds %s..%s / %s..%s)" % (
        len(frozen["set1"]), len(frozen["set2"]), min(int(r[3]) for r in frozen["set1"]),
        max(int(r[3]) for r in frozen["set1"]), min(int(r[3]) for r in frozen["set2"]),
        max(int(r[3]) for r in frozen["set2"])))
    try:   # the queue's own source (fx3mS / fx3mS2 argv cells): a different set is the seed-selector defect - STOP
        fresh = {"set1": [list(c) for c in FQ.cells("fx3mS")], "set2": [list(c) for c in FQ.cells("fx3mS2")]}
        if fresh != frozen:
            out("STOP: outputs/_dp_seeds.txt differs from the fx3mS / fx3mS2 argv cells (seed-selector rule)")
            return None
        out("  == the fx3mS / fx3mS2 argv cells (_fb3_queue.cells)")
    except (Exception, SystemExit) as exc:   # noqa: BLE001
        out("  WARNING: reference argv cells unreadable (%r) - parse check only" % (exc,))
    return frozen


# ================================================================================================ 1 LOAD + PROV
def screen_cells(frozen, smoke, smoke_cell="set2/ring/D_N"):
    cells = []
    for suffix, plc, mode, which in PLACES:
        for key, scen, wind, seed in frozen[which]:
            cells.append({"id": "%s/%s/%s" % (which, plc, key), "set": which, "plc": plc, "suffix": suffix,
                          "mode": mode, "key": key, "scen": scen, "wind": wind, "seed": int(seed)})
    if smoke:     # the smoke cell: by default scenario D, wind north, seed 9633, ring = set 2 ring D_N (--smoke-cell)
        cells = [c for c in cells if c["id"] == smoke_cell]
    return cells


def run_path(arm, cell, opts):
    if opts.smoke:
        return os.path.join(opts.smoke, SMOKE_FILES[arm])
    return os.path.join(HERE, "_sd_%s%s_%s.json" % (arm, cell["suffix"], cell["key"]))


def expected_extra(arm, cell):
    ex = {"GLOBAL_PLANNER_MODE": 0, "VICTIM_SPAWN_MODE": cell["mode"], "BATCH_SIZE": 360}
    if arm == "dp1":
        ex.update(ON)
    return ex


def expected_line(arm, cell, repo):
    sets = ["--set", "GLOBAL_PLANNER_MODE=0", "--set", "VICTIM_SPAWN_MODE=%d" % cell["mode"]]
    if arm == "dp1":
        sets += ON_SETS
    return Q.probe_line(arm + cell["suffix"], cell["key"], cell["scen"], cell["wind"], cell["seed"], repo, sets)


def prov_probe(d, arm, cell, path, opts):
    """14.5 validity of one screen run: (tooling defects -> INVALID, crash text or None). A dp1 crash or a dp1 run that
    stops neither terminal nor at the last step is a GATE FAILURE (S2), never INVALID."""
    why = []
    if d.get("dp_only"):
        if not isinstance(d.get("dp"), dict):
            why.append("dp section missing")
        return why, "no sd record (dp_only - the chain wrote no JSON)"
    repo = d.get("repo")
    sd_argv = list(d.get("argv") or [])
    repo_raw = sd_argv[sd_argv.index("--repo") + 1] if "--repo" in sd_argv[:-1] else repo
    if not same_path(repo_raw, repo):
        why.append("argv --repo %s is not the recorded repo %s" % (repo_raw, repo))
    dp_rec = d.get("dp") if isinstance(d.get("dp"), dict) else {}
    crashed_run = bool(d.get("crashed")) or dp_rec.get("rc_chain") not in (0, None)
    if not opts.smoke:
        if arm == "dpR":
            if same_path(repo, WT):
                why.append("dpR repo is the dispatch worktree (must be the B worktree)")
            if same_path(repo, SHARED_CHECKOUT):
                why.append("dpR repo is the shared main checkout (must be the detached B worktree)")
        elif not same_path(repo, WT):
            why.append("repo %s != %s" % (repo, WT))
        want = opts.head_b if arm == "dpR" else opts.head_dp
        if want and not str(d.get("head") or "").startswith(want):
            why.append("head %s != %s" % (str(d.get("head"))[:10], want))
    ex = expected_extra(arm, cell)
    if d.get("extra_params") != ex:
        why.append("extra_params %s != %s" % (json.dumps(d.get("extra_params"), sort_keys=True),
                                              json.dumps(ex, sort_keys=True)))
    if not opts.smoke:
        line = expected_line(arm, cell, repo_raw if arm == "dpR" else WT)
        if d.get("argv") != line["argv"][line["argv"].index("--") + 1:]:
            why.append("sd argv differs from the queue line")
        if crashed_run:
            # the pool writes .argv only for rc 0 (_mf2_pool.py): a crashed run is checked on its recorded argv
            # alone and is never INVALID for lacking one - a dp1 crash is a GATE FAILURE (14.5)
            pass
        else:
            try:
                with open(path + ".argv", encoding="utf-8") as fh:
                    if fh.read() != POOL.signature(line):
                        why.append(".argv signature differs from the queue line")
            except OSError:
                why.append("no .argv (not a pool run of this line)")
    fb = d.get("fb3") or {}
    crn = fb.get("crn") or {}
    if not crn.get("on"):
        why.append("CRN off (fb3.crn.on %s)" % crn.get("on"))
    elif not int(crn.get("crn_draws") or 0) > 0:
        why.append("CRN on with crn_draws %s" % crn.get("crn_draws"))
    if (fb.get("eff") or {}).get("victim_spawn_mode") != cell["mode"]:
        why.append("fb3.eff.victim_spawn_mode %s != %s" % ((fb.get("eff") or {}).get("victim_spawn_mode"),
                                                           cell["mode"]))
    dp = d.get("dp")
    if not isinstance(dp, dict):
        if not (opts.smoke and arm == "dpR"):
            why.append("dp section missing")
    else:
        if dp.get("probe") != "dp_probe v2":
            why.append("dp.probe %r (A2 22.2: dp_probe v2, whose m3a record carries the free-unit ids)" % dp.get("probe"))
        refused = rb_cut_refusals(dp.get("commands"))
        if refused and not (arm == "dp1" and crashed_run):    # a dp1 crash is a gate failure, never INVALID (14.5)
            why.append("REFUSED (A2 22.2, tooling defect): successful assign stamped init / sweep %s - fix the "
                       "instrument or the analyzer's cut first (under CRN a re-run reproduces it)" % refused[:3])
        sw = dp.get("switches") or {}
        want_on = arm == "dp1"
        if bool(sw.get("joint_on")) is not want_on or bool(sw.get("reassign_on")) is not want_on:
            why.append("dp.switches joint_on %s reassign_on %s, the arm means %s" % (
                sw.get("joint_on"), sw.get("reassign_on"), want_on))
    if (d.get("scenario"), d.get("wind"), d.get("seed")) != (cell["scen"], cell["wind"], cell["seed"]):
        why.append("SEED MISMATCH (STOP - seed-selector rule): %s/%s/%s != frozen %s/%s/%s" % (
            d.get("scenario"), d.get("wind"), d.get("seed"), cell["scen"], cell["wind"], cell["seed"]))
    exp_steps = d.get("steps") if opts.smoke else H
    if d.get("steps") != exp_steps:
        why.append("steps %s != %s" % (d.get("steps"), exp_steps))
    so = stdout_path(path)
    if not os.path.exists(so):
        why.append("stdout record missing (%s)" % os.path.basename(so))
    else:
        with open(so, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        if d.get("stdout_sha") and sha[:len(str(d["stdout_sha"]))] != str(d["stdout_sha"]):
            why.append("stdout record sha differs from stdout_sha")
    crash = None
    stop, term = d.get("steps_done"), d.get("terminal_step")
    if d.get("crashed"):
        crash = "crashed %s at step %s" % ((d.get("crashed") or {}).get("type"), (d.get("crashed") or {}).get("step"))
    elif not (stop == exp_steps or (term is not None and stop == term)):
        crash = "stopped at step %s (terminal %s, expected %s)" % (stop, term, exp_steps)
    return why, crash


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


# ================================================================================================ digest
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


def digest(d, arm, label, censor):
    """Everything sections 3-5 read from one run, computed once (the run dict is dropped afterwards)."""
    g = {"arm": arm, "label": label, "dp_only": bool(d.get("dp_only")), "crashed": d.get("crashed")}
    dp = d.get("dp") if isinstance(d.get("dp"), dict) else {}
    timing = dp.get("timing") or {}
    g["j_ms_total"] = float(timing.get("j_ms_total") or 0.0)
    g["j_ms"] = [float(c[2]) for c in dp.get("j_calls") or [] if len(c) > 2]
    g["dp_errors"] = list(dp.get("errors") or [])
    g["has_dp"] = bool(dp)
    if g["dp_only"] or not d.get("rows_ff"):
        g["usable"] = False
        return g
    g["usable"] = True
    g["eval"] = dict(d.get("eval") or {})
    g["terminal"] = d.get("terminal_step")
    g["steps_done"] = d.get("steps_done")
    g["wall_s"] = float(d.get("wall_s") or 0.0)
    g["n_ff"] = int((d.get("params") or {}).get("NUM_FIREFIGHTERS") or 0)
    g["censor"] = censor
    rows_ff, rows_vic = d["rows_ff"], d["rows_vic"]
    g["victims"] = [r[0] for r in rows_vic[0]] if rows_vic else []
    det = d.get("_det") or {}
    g["det"] = {v: det.get(v) for v in g["victims"]}
    g["det_file"] = d.get("_det_file", False)
    resc, vdead = {}, {}
    for t, row in enumerate(rows_vic):
        for r in row:
            if r[4] == "rescued" and r[0] not in resc:
                resc[r[0]] = t + 1
            if r[4] == "dead" and r[0] not in vdead:
                vdead[r[0]] = t + 1
    g["resc"], g["vdead"] = resc, vdead
    g["end_status"] = {r[0]: r[4] for r in rows_vic[-1]} if rows_vic else {}
    ff_dead, ff_rb = {}, collections.defaultdict(set)
    pick_u, pickups, first_bound = [], {}, {}
    prev_exit = {}
    by_step = []
    for t, row in enumerate(rows_ff):
        m = {}
        for r in row:
            fid = r[0]
            m[fid] = r
            if r[6] and fid not in ff_dead:
                ff_dead[fid] = t + 1
            if str(r[3]) == "route_blocked":
                ff_rb[fid].add(t + 1)
            if r[5] and not prev_exit.get(fid) and r[8]:
                pick_u.append((t + 1, fid, r[8]))
                pickups.setdefault(r[8], t + 1)
            prev_exit[fid] = r[5]
            if r[8] and r[8] not in first_bound:
                first_bound[r[8]] = (t + 1, fid)
        by_step.append(m)
    g["ff_dead"], g["pickups"], g["first_bound"] = ff_dead, pickups, first_bound
    num = collections.Counter()
    lists = collections.defaultdict(list)
    num["never"] = int(d.get("terminal_step") is None)
    # ---- G-L (rows_ff, cross-checked with ut.rb.latched_end)
    g["latched_end"] = sorted(U2.ff_status_track(d)[2])
    g["ut_latched_end"] = sorted(((d.get("ut") or {}).get("rb") or {}).get("latched_end") or [])
    # ---- G-OS: _fb3_analyze.searcher_o; before / after the run's own last detection (_ut_analyze2.sec_gates' rule)
    broad, near, anyw = A.searcher_o(d)
    last = U._last_detection(d)
    for e in broad:
        when = "after" if last is not None and e[1] >= last else "before"
        num["os_broad_" + when] += 1
        lists["os_broad_" + when].append([e[0], e[1], e[2], e[3], e[4]])
    num["os_pocket_near"], num["os_pocket_any"] = near, anyw
    g["last_det"] = last
    # ---- G-OF: _fb3_analyze.ff_episodes (broad) + _sd_analyze I2 kinds
    for fid, s0, s1, n in A.ff_episodes(d):
        st = collections.Counter(ff_state(by_step[s - 1][fid]) for s in range(s0, s1 + 1) if fid in by_step[s - 1])
        state = max(FF_STATES, key=lambda k: (st.get(k, 0), -FF_STATES.index(k)))
        num["of_broad"] += 1
        num["of_steps_broad"] += n
        num["of_state_" + state] += 1
        lists["of_broad"].append([fid, s0, s1, n, state])
    sd_out, sd_info = SD.analyze(label, d, STUCK, WIN)
    for short, key in I2_KINDS:
        eps = sd_out.get(key) or []
        num["of_" + short] = len(eps)
        num["of_steps_" + short] = sum(e[1] - e[0] + 1 for e in eps)
        lists["of_" + short] = [e[:3] for e in eps]
    num["i5_double"] = len(sd_out.get("I5_double_binding") or [])
    num["gb_e"] = sum(int(v or 0) for v in (d.get("inline_violation_counts") or {}).values())
    # ---- dp-based measures
    cmds = dp.get("commands") or []
    binders = dp.get("binders") or []
    sw = dp.get("switches") or {}
    g["reassign_on"] = bool(sw.get("reassign_on"))
    bsteps = {}
    for step, lst in binders:
        sample = {}
        for vid, bl in lst:
            sample[vid] = bl
            if len(bl) >= 2:
                num["gb_a"] += 1
                lists["gb_a"].append([step, vid, bl])
            if sum(1 for _, s in bl if str(s).lower() != "route_blocked") >= 2:
                num["gb_b"] += 1
                lists["gb_b"].append([step, vid, bl])
        bsteps[step] = sample
    # G-B(c) I3: a replace / latch_fill whose victim has no binder at the same step's sample (after J-post; a J-pre
    # event is excused only by an outside event or a terminal victim in between)
    vic_rows = {t + 1: {r[0]: r for r in row} for t, row in enumerate(rows_vic)}
    for e in dp.get("j_events") or []:
        if e.get("kind") not in ("replace", "latch_fill"):
            continue
        step, vid, uid = e.get("step"), e.get("victim_id"), e.get("unit")
        sample = bsteps.get(step)
        if sample is None:
            lists["gb_c_nosample"].append([step, e.get("phase"), vid, uid])
            continue
        if vid in sample:
            continue
        excused = ""
        if e.get("phase") == "pre":
            if any(c[0] == step and c[2] == "unassign" and c[6] and c[3] == vid and c[4] == uid
                   and "replacement" in str(c[5]) and "blocked" in str(c[5]) for c in cmds):
                excused = "o1"
            elif ff_dead.get(uid) == step:
                excused = "o3"
            elif str((vic_rows.get(step, {}).get(vid) or [None] * 5)[4]) in TERMINAL:
                excused = "victim terminal"
        if excused:
            lists["gb_c_excused"].append([step, e.get("phase"), e.get("kind"), vid, uid, excused])
        else:
            num["gb_c"] += 1
            lists["gb_c"].append([step, e.get("phase"), e.get("kind"), vid, uid, e.get("old_units")])
    num["gb_d"] = len(dp.get("invariant") or [])
    lists["gb_d"] = list(dp.get("invariant") or [])[:20]
    # G-B(f) + M3 from dp.waiting / dp.m3a (same instant as the binders sample), the latch cap applied in every arm
    # and dp0's ledger rebuilt from its own assigns (R-B, A2 22.2)
    live = bool(sw.get("joint_on"))
    rb_num, rb_lists, g["rb_checks"] = rb_figures(dp.get("waiting"), binders, dp.get("m3a"), cmds, live)
    num.update(rb_num)
    lists.update(rb_lists)
    # G-T
    rets = gt_returns(cmds, binders, ff_dead, ff_rb)
    num["gt_b"] = len(rets)
    num["gt_a"] = sum(1 for r in rets if not r["outside"])
    num["gt_a_strict"] = sum(1 for r in rets if not [o for o in r["outside"] if o != "o2@frame"])
    lists["gt_a"] = [r for r in rets if not r["outside"]]
    lists["gt_b"] = rets
    viol, reused, bcount = ledger_check(cmds)
    num["gt_c"] = len(viol)
    lists["gt_c"] = viol
    num["reused_binds"] = len(reused)
    led = dp.get("ledger") or {}
    if g["reassign_on"] or led:
        mism = sorted(k for k in set(led) | {"%s|%s" % kv for kv in bcount}
                      if int(led.get(k, 0)) != bcount.get(tuple(k.split("|", 1)), 0))
        lists["ledger_mismatch"] = mism
    # M4 - binds made by the SECOND FILL (stage 4: second fills and, under A2, LATCH-FILLs of the units a REPLACE
    # released) are counted apart, with the cause of the REPLACE that released the unit (22.4 P2-7, 22.5(3))
    evs = dp.get("j_events") or []
    for e in evs:
        k = str(e.get("kind") or "")
        if k == "replace":
            num["replace_" + ("stall" if e.get("reason") == "reassign_stall" else
                              "margin" if e.get("reason") == "reassign_margin" else "other")] += 1
        elif k in ("fill", "latch_fill", "second_fill"):
            if e.get("stage") == 4:
                num[k + "_s4"] += 1
                cause = next((x.get("reason") for x in evs if x.get("kind") == "replace"
                              and x.get("step") == e.get("step") and x.get("phase") == e.get("phase")
                              and e.get("unit") in (x.get("old_units") or [])), None)
                lists["stage4"].append([e.get("step"), e.get("phase"), k, e.get("victim_id"), e.get("unit"),
                                        e.get("old_units"), cause])
            else:
                num[k] += 1
        elif k.endswith("_refused"):
            num["refused"] += 1
        elif k.endswith("_aborted"):
            num["aborted"] += 1
    # what J saw (14.4; dp.j_detail): PRE points, progress evaluations, FROZEN frames (6.3), bindings left
    # unevaluated because d or x was infinite (6.3 / Part 2 note P2-3), stall counts reaching S
    for _step, _phase, cur in dp.get("j_detail") or []:
        num["j_pre_points"] += 1
        for c in cur.get("calls") or []:
            if c.get("fn") == "progress_step":
                num["prog_evals"] += 1
                num["prog_frozen"] += 1 if c.get("frozen") else 0
        num["prog_unevaluated"] += len(cur.get("unevaluated") or [])
        lists["prog_unevaluated"] += [[_step, b] for b in cur.get("unevaluated") or []]
    for c in dp.get("j_calls") or []:
        if len(c) > 4 and isinstance(c[4], dict):
            num["cf_points"] += 1
            leg = sorted(tuple(x) for x in c[4].get("legacy") or [])
            jf = sorted(tuple(x) for x in c[4].get("j_fills") or [])
            if leg != jf:
                num["cf_diff"] += 1
                lists["cf_diff"].append([c[0], c[1], leg, jf])
    # M5 latency + realised steps to pickup minus d at binding
    first_assign = {}
    for c in cmds:
        if c[2] == "assign" and c[6] and c[3] not in first_assign:
            first_assign[c[3]] = c[0]
    g["lat"] = {v: (g["det"].get(v), first_assign.get(v), pickups.get(v), resc.get(v)) for v in g["victims"]}
    rmd = []
    for i, c in enumerate(cmds):
        if c[2] != "assign" or not c[6]:
            continue
        s_a, vid, uid, d_route = c[0], c[3], c[4], c[8]
        if d_route is None:
            num["rmd_closed"] += 1
            continue
        end = next((x[0] for x in cmds[i + 1:] if x[2] == "unassign" and x[6] and x[3] == vid and x[4] == uid), None)
        p = next((s for s, f, v in pick_u if f == uid and v == vid and s >= s_a and (end is None or s <= end)), None)
        if p is None:
            num["rmd_nopickup"] += 1
        else:
            rmd.append((p - s_a) - int(d_route))
    g["rmd"] = rmd
    # M6
    for c in cmds:
        if c[2] == "assign" and c[6] and c[7] is False:
            num["assign_closed"] += 1
            lists["assign_closed"].append([c[0], c[1], c[3], c[4], c[5]])
        if c[2] == "mark_unreachable" and c[6]:
            if c[1] == "sweep":
                num["escape_writeoffs"] += 1
            else:
                num["dispatch_writeoffs"] += 1
            lists["writeoffs"].append([c[0], c[1], c[3], c[5]])
    num["writeoffs_avoided"] = len(dp.get("writeoffs_avoided") or [])
    # M8 / M9
    g["m8"] = list(dp.get("m8") or [])
    g["m9"] = [list(e) + [g["end_status"].get(e[2])] for e in dp.get("m9") or []]
    # divergence + evidence
    g["h_ff"], g["h_vic"], g["h_uav"] = hashes(rows_ff), hashes(rows_vic), hashes(d["rows_uav"])
    g["cmd_seq"] = [(c[0], c[2], c[3], c[4], bool(c[6])) for c in cmds if c[2] in ("assign", "unassign")]
    g["cmds"] = [c[:7] + [c[8]] for c in cmds]
    g["j_events"] = [{k: e.get(k) for k in ("step", "phase", "kind", "stage", "victim_id", "unit", "old_units",
                                             "reason", "distance")} for e in dp.get("j_events") or []]
    g["num"], g["lists"] = num, lists
    return g


# ================================================================================================ the screen pass
def process(cells, opts):
    """Per cell: dpR + dp0 -> PROV, G-ID, digest dp0; dp1 -> PROV, digest. One run in memory at a time beyond the
    identity pair."""
    recs = []
    for c in cells:
        rec = {"cell": c, "prov": {}, "crash": {}, "missing": [], "ident": None, "d0": None, "d1": None,
               "repo": {}, "head": {}, "src": {}, "rb_dpR": None}
        loaded = {}
        for arm in ("dpR", "dp0"):
            p = run_path(arm, c, opts)
            if not os.path.exists(p):
                rec["missing"].append(arm)
                continue
            try:
                d = load_run(p)
            except Exception as exc:          # noqa: BLE001
                rec["prov"][arm] = ["unreadable JSON %r" % (exc,)]
                continue
            rec["prov"][arm], rec["crash"][arm] = prov_probe(d, arm, c, p, opts)
            rec["repo"][arm], rec["head"][arm] = d.get("repo"), str(d.get("head") or "")[:10]
            rec["src"][arm] = (json.dumps(d.get("src_sha"), sort_keys=True),
                               json.dumps((d.get("dp") or {}).get("src_sha"), sort_keys=True))
            if arm == "dpR" and isinstance(d.get("dp"), dict):
                # R-B check (iii) runs in EVERY arm (A2 22.2); dpR is not digested otherwise
                dpr = d["dp"]
                rec["rb_dpR"] = rb_figures(dpr.get("waiting"), dpr.get("binders"), dpr.get("m3a"),
                                           dpr.get("commands"), False)[2]
            loaded[arm] = d
        if "dpR" in loaded and "dp0" in loaded:
            a, b = loaded["dpR"], loaded["dp0"]
            if a.get("dp_only") or b.get("dp_only"):
                rec["ident"] = (["sd record missing (crash)"], "", [], "")
            else:
                diff, note, other = ident_diff(a, b, bool(opts.smoke))
                fp = first_path(field_get(a, diff[0]), field_get(b, diff[0]), diff[0]) if diff else ""
                rec["ident"] = (diff, note, other, fp)
        if "dp0" in loaded:
            rec["d0"] = digest(loaded["dp0"], "dp0", "dp0_" + c["id"], censor(loaded["dp0"], opts))
        loaded.clear()
        p = run_path("dp1", c, opts)
        if not os.path.exists(p):
            rec["missing"].append("dp1")
        else:
            try:
                d = load_run(p)
                rec["prov"]["dp1"], rec["crash"]["dp1"] = prov_probe(d, "dp1", c, p, opts)
                rec["repo"]["dp1"], rec["head"]["dp1"] = d.get("repo"), str(d.get("head") or "")[:10]
                rec["src"]["dp1"] = (json.dumps(d.get("src_sha"), sort_keys=True),
                                     json.dumps((d.get("dp") or {}).get("src_sha"), sort_keys=True))
                rec["d1"] = digest(d, "dp1", "dp1_" + c["id"], censor(d, opts))
            except Exception as exc:          # noqa: BLE001
                rec["prov"]["dp1"] = ["unreadable JSON %r" % (exc,)]
            d = None
        recs.append(rec)
    return recs


def censor(d, opts):
    """M1c censoring step: 361 (H + 1); in smoke mode the run's own last step + 1."""
    return (int(d.get("steps_done") or 0) + 1) if opts.smoke else H + 1


def sec_prov(recs, opts):
    head("1 LOAD + PROV (14.5) - arms dpR (B worktree), dp0 (dispatch, switches 0), dp1 (DISPATCH_JOINT=1 "
         "DISPATCH_REASSIGN=1); files outputs/_sd_<arm><r|r2|u|u2>_<S>_<W>.json")
    st = {"missing": [], "invalid": [], "crash_dp1": [], "crash_other": []}
    for arm in ("dpR", "dp0", "dp1"):
        present = sum(1 for r in recs if arm in r["prov"])
        miss = [r["cell"]["id"] for r in recs if arm in r["missing"]]
        inv = [(r["cell"]["id"], r["prov"][arm]) for r in recs if r["prov"].get(arm)]
        crash = [(r["cell"]["id"], r["crash"][arm]) for r in recs if r["crash"].get(arm)]
        repos = collections.Counter(str(r["repo"].get(arm)) for r in recs if arm in r["repo"])
        heads = collections.Counter(r["head"].get(arm) for r in recs if arm in r["head"])
        srcs = collections.Counter(r["src"][arm] for r in recs if arm in r["src"])
        out("  %-4s present %2d / %d | missing %d | INVALID %d | crash / early stop %d | repo %s | head %s | "
            "src_sha variants %d" % (arm, present, len(recs), len(miss), len(inv), len(crash), dict(repos),
                                     dict(heads), len(srcs)))
        for cid, why in inv:
            out("       INVALID %s %s: %s" % (arm, cid, "; ".join(why)))
        for cid in miss[:64]:
            out("       MISSING %s %s" % (arm, cid))
        for cid, why in crash:
            out("       %s %s %s: %s" % ("GATE FAILURE (S2)" if arm == "dp1" else "CRASH", arm, cid, why))
        st["missing"] += [(arm, c) for c in miss]
        st["invalid"] += [(arm, c, w) for c, w in inv]
        if arm == "dp1":
            st["crash_dp1"] += crash
        else:
            st["crash_other"] += [(arm, c, w) for c, w in crash]
        if arm in ("dp0", "dp1") and len(srcs) > 1:
            out("       WARNING %s runs carry %d different source records (src_sha + dp.src_sha)" % (arm, len(srcs)))
        if arm == "dpR" and not opts.smoke and (len(repos) > 1 or len(srcs) > 1):
            why = "dpR runs come from %d checkouts / %d source records (14.5: exactly one B)" % (len(repos), len(srcs))
            out("       INVALID dpR (all cells): %s" % why)
            st["invalid"] += [("dpR", r["cell"]["id"], [why]) for r in recs if "dpR" in r["prov"]]
    s0 = {r["src"]["dp0"] for r in recs if "dp0" in r["src"]}
    s1 = {r["src"]["dp1"] for r in recs if "dp1" in r["src"]}
    if s0 and s1 and s0 != s1:
        out("  WARNING dp0 and dp1 source records differ (they must run at the same Part 2 commit)")
    errs = [(g["label"], g["dp_errors"]) for r in recs for g in (r["d0"], r["d1"]) if g and g.get("dp_errors")]
    out("  instrument errors (dp.errors, reported - not a 14.5 validity rule): %d runs %s" % (
        len(errs), errs[:4] if errs else ""))
    nodet = [g["label"] for r in recs for g in (r["d0"], r["d1"]) if g and g.get("usable") and not g.get("det_file")]
    if nodet:
        out("  WARNING runs without a stdout detection record: %s" % nodet[:8])
    return st


# ================================================================================================ 2 G-ID
def shard_path(tag, sid, wind):
    return os.path.join(HERE, "_rblatch_camp2_%s%s_D_%s.json" % (tag, sid, wind))


def prov_shard(tag_prefix, sid, wind, s, path, opts):
    why = []
    if s.get("tag") != tag_prefix + sid:
        why.append("tag %s != %s" % (s.get("tag"), tag_prefix + sid))
    if opts.smoke:
        return why
    if s.get("steps") != 240 or s.get("scenario") != "D" or s.get("wind") != wind:
        why.append("steps/scenario/wind %s/%s/%s" % (s.get("steps"), s.get("scenario"), s.get("wind")))
    params = s.get("params") or {}
    want_on = tag_prefix == opts.gate_tags[2]
    for k in ON:
        if want_on and params.get(k) != 1:
            why.append("params %s %s, the arm means 1" % (k, params.get(k)))
        if not want_on and k in params:
            why.append("params has %s" % k)
    try:
        with open(path + ".argv", encoding="utf-8") as fh:
            sig = fh.read()
        cwd = json.loads(sig).get("cwd")
        if tag_prefix == opts.gate_tags[0]:
            if same_path(cwd, WT):
                why.append("reference shard cwd is the dispatch worktree")
        elif not same_path(cwd, WT):
            why.append("cwd %s" % cwd)
        line = next(x for x in Q.shards(tag_prefix, cwd if tag_prefix == opts.gate_tags[0] else WT,
                                        ON_SETS if want_on else []) if x["name"] == tag_prefix + sid)
        if sig != POOL.signature(line):
            why.append(".argv signature differs from the queue line")
    except (OSError, ValueError, StopIteration) as exc:
        why.append("no usable .argv (%r)" % (exc,))
    return why


def load_shards(tag, opts):
    res = {}
    for sid, wind in SHARDS:
        p = shard_path(tag, sid, wind)
        if not os.path.exists(p):
            res[sid] = None
            continue
        s = load_json(p)
        with open(p, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()[:16]
        res[sid] = {"data": s, "prov": prov_shard(tag, sid, wind, s, p, opts), "sha": sha, "wind": wind}
    return res


def sec_ident(recs, opts):
    head("2 G-ID (14.6) - dp0 == dpR value identity per cell on _fx3r_analyze.FIELDS + every mf2 section (not probe) "
         "+ every dp field that exists without J (not %s)" % "/".join(J_ONLY))
    n = len(recs)
    same = sum(1 for r in recs if r["ident"] is not None and not r["ident"][0])
    compared = sum(1 for r in recs if r["ident"] is not None)
    for r in recs:
        if r["ident"] is None:
            continue
        diff, note, other, fp = r["ident"]
        if diff:
            out("    %s DIFFER %s | first path %s" % (r["cell"]["id"], diff[:8], fp))
        if note:
            out("    %s note: %s" % (r["cell"]["id"], note))
        if other:
            out("    %s other sections differing (reported, not part of G-ID): %s" % (r["cell"]["id"], other[:6]))
    probe_ok = same == compared == n
    out("  probe arms: %d / %d cells identical (%d compared)  => %s" % (
        same, n, compared, "PASS" if probe_ok else ("FAIL" if same < compared else "INCOMPLETE")))
    # gate shards: dpG0 vs the reference (harness identity, _fx3r_analyze.strip_rb)
    ref_tag, g0_tag = opts.gate_tags[0], opts.gate_tags[1]
    shards_ok, shard_lines = None, []
    if opts.smoke and not opts.smoke_gate:
        out("  gate shards: NOT RUN (smoke)")
        return {"probe": probe_ok, "probe_same": same, "probe_compared": compared, "shards": None,
                "mismatch": compared - same}
    ref, g0 = load_shards(ref_tag, opts), load_shards(g0_tag, opts)
    n_same = n_cmp = 0
    for sid, wind in SHARDS:
        a, b = ref.get(sid), g0.get(sid)
        if a is None or b is None:
            shard_lines.append("    shard %s MISSING (%s %s, %s %s)" % (sid, ref_tag, "ok" if a else "missing",
                                                                     g0_tag, "ok" if b else "missing"))
            continue
        for tag, x in ((ref_tag, a), (g0_tag, b)):
            if x["prov"]:
                shard_lines.append("    INVALID %s%s: %s" % (tag, sid, "; ".join(x["prov"])))
        n_cmp += 1
        sa, sb = R.strip_rb(a["data"]), R.strip_rb(b["data"])
        sa.pop("extra_params", None)          # the brief's skip list; the campaign writes none today
        sb.pop("extra_params", None)
        diff = [k for k in sorted(set(sa) | set(sb)) if sa.get(k) != sb.get(k)]
        n_same += not diff
        shard_lines.append("    shard %s %-5s %s%s sha %s vs %s%s sha %s: %s" % (
            sid, wind, ref_tag, sid, a["sha"], g0_tag, sid, b["sha"],
            "identical" if not diff else "DIFFER %s | first path %s" % (diff[:6], first_path(sa.get(diff[0]),
                                                                                          sb.get(diff[0]), diff[0]))))
    for ln in shard_lines:
        out(ln)
    # tri-state: True all four identical, False a compared pair differs (S1 STOP), None incomplete without a difference
    shards_ok = True if n_same == n_cmp == len(SHARDS) else (False if n_same < n_cmp else None)
    out("  gate shards %s vs %s: %d / %d identical (tag / params / per-seed wall_s dropped)  => %s" % (
        g0_tag, ref_tag, n_same, len(SHARDS), {True: "PASS", False: "FAIL", None: "INCOMPLETE"}[shards_ok]))
    return {"probe": probe_ok, "probe_same": same, "probe_compared": compared, "shards": shards_ok,
            "mismatch": (compared - same) + (n_cmp - n_same),
            "shard_invalid": any(x and x["prov"] for x in list(ref.values()) + list(g0.values())),
            "shard_missing": any(ref.get(s) is None or g0.get(s) is None for s, _ in SHARDS)}


# ================================================================================================ 3 GATES
def pairs(recs):
    """Cells whose dp0 and dp1 are both usable digests - the gated comparison set."""
    return [r for r in recs if r["d0"] and r["d1"] and r["d0"].get("usable") and r["d1"].get("usable")]


def agg(cells, fn, arm, groups=GROUPS):
    return {name: sum(fn(r[arm]) for r in cells if sel(r["cell"])) for name, sel in groups}


def num_of(name):
    return lambda g: g["num"].get(name, 0)


def gate_line(label, cells, name, structural=False, report_only=False):
    f = num_of(name) if isinstance(name, str) else name
    v0, v1 = agg(cells, f, "d0"), agg(cells, f, "d1")
    if report_only:
        verdict = "(reported)"
    elif structural:
        verdict = "PASS" if v1["pooled"] == 0 else "FAIL"
    else:
        verdict = "PASS" if v1["pooled"] <= v0["pooled"] else "FAIL"
    tail = " | ".join("%s %s->%s%s" % (k, v0[k], v1[k], "" if structural or v1[k] <= v0[k] else " RISE")
                      for k in ("set1", "set2", "ring", "uniform"))
    out("  %-40s pooled %5s -> %5s %-10s | %s%s" % (label, v0["pooled"], v1["pooled"], verdict, tail,
                                                  " | structural: dp1 must be 0" if structural else ""))
    return None if report_only else verdict == "PASS"


def sec_gates(recs, opts, st):
    cells = pairs(recs)
    head("3 GATES (14.6) - dp0 -> dp1, pooled over %d paired cells (gate) and per seed set / placement (reported); "
         "every item must not rise, structural items exactly 0 in dp1" % len(cells))
    G = collections.OrderedDict()
    out("G-N   never finish (terminal_step None)")
    G["G-N"] = gate_line("runs that never finish", cells, "never")
    for r in cells:
        if r["d0"]["num"]["never"] or r["d1"]["num"]["never"]:
            out("        %s never-finish dp0 %d dp1 %d" % (r["cell"]["id"], r["d0"]["num"]["never"],
                                                           r["d1"]["num"]["never"]))
    out("G-OS  searcher oscillation (_fb3_analyze.searcher_o; before / after the run's own last detection as in "
        "_ut_analyze2.sec_gates)")
    for name, label in (("os_broad_before", "broad (O) before the last detection"),
                        ("os_broad_after", "broad (O) after the last detection"),
                        ("os_pocket_near", "pocket near a depot (r 5)"), ("os_pocket_any", "pocket anywhere (r 500)")):
        G["G-OS " + label] = gate_line(label, cells, name)
    out("G-OF  firefighter oscillation (_fb3_analyze.ff_episodes broad; _sd_analyze I2 stuck %d / window %d)" % (
        STUCK, WIN))
    G["G-OF broad"] = gate_line("broad positional (10-step, <=2 cells, >=4)", cells, "of_broad")
    for short, _key in I2_KINDS:
        G["G-OF " + short] = gate_line("I2 " + short.replace("_", " "), cells, "of_" + short)
    out("  21.2(f) reported: episode-steps (sum of episode lengths) and broad episodes by unit state, per arm per set")
    for arm in ("d0", "d1"):
        for gname in ("set1", "set2", "pooled"):
            sel = dict(GROUPS)[gname]
            sub = [r for r in cells if sel(r["cell"])]
            steps = {k: sum(r[arm]["num"].get("of_steps_" + k, 0) for r in sub)
                     for k in ["broad"] + [s for s, _ in I2_KINDS]}
            states = {s: sum(r[arm]["num"].get("of_state_" + s, 0) for r in sub) for s in FF_STATES}
            out("    %s %-6s episode-steps %s | broad by state %s" % ("dp0" if arm == "d0" else "dp1", gname,
                                                                      steps, states))
    out("G-L   latched units: a dp1 run ending (last recorded step, rows_ff) with a route_blocked unit dp0 lacks")
    new_l, xchk = [], []
    for r in cells:
        extra = sorted(set(r["d1"]["latched_end"]) - set(r["d0"]["latched_end"]))
        if extra:
            new_l.append((r["cell"]["id"], extra))
        for g in (r["d0"], r["d1"]):
            if g["latched_end"] != g["ut_latched_end"]:
                xchk.append((g["label"], g["latched_end"], g["ut_latched_end"]))
    G["G-L"] = not new_l
    out("  %-40s dp0 runs ending latched %d, dp1 %d | NEW in dp1 %s  %s" % (
        "new latched units", sum(1 for r in cells if r["d0"]["latched_end"]),
        sum(1 for r in cells if r["d1"]["latched_end"]), new_l or "none", "PASS" if not new_l else "FAIL"))
    if xchk:
        out("    rows_ff vs ut.rb.latched_end disagree: %s" % xchk[:6])
    out("G-B   binding, sampled after J-post (dp.binders / dp.waiting / dp.invariant / inline_violations)")
    G["G-B(a)"] = gate_line("(a) victim-steps >= 2 living binders", cells, "gb_a")
    G["G-B(b)"] = gate_line("(b) victim-steps >= 2 ACTIVE binders", cells, "gb_b", structural=True)
    G["G-B(c)"] = gate_line("(c) dispatch abandonment I3", cells, "gb_c", structural=True)
    G["G-B(d)"] = gate_line("(d) captured RescueInvariant lines", cells, "gb_d")
    G["G-B(e)"] = gate_line("(e) inline_violations", cells, "gb_e")
    rb_fail = rb_report(recs)
    G["_rb_fail"] = rb_fail
    if rb_fail:
        gate_line("(f) abandoned waiting, ledger-allowed [STOPPED]", cells, "gb_f_allowed", report_only=True)
        gate_line("(f) abandoned waiting, ledger-blocked [STOPPED]", cells, "gb_f_blocked", report_only=True)
        G["G-B(f) allowed"] = G["G-B(f) blocked"] = "STOPPED (R-B tooling check failed - A2 22.2)"
        out("    G-B(f) allowed / blocked STOPPED (and every R-B figure in section 4) until the analyzer or instrument "
            "is fixed (no run is re-run for it); the counts above are NOT gate results")
    else:
        G["G-B(f) allowed"] = gate_line("(f) abandoned waiting, ledger-allowed", cells, "gb_f_allowed",
                                        structural=True)
        G["G-B(f) blocked"] = gate_line("(f) abandoned waiting, ledger-blocked", cells, "gb_f_blocked")
    out("    (f) is counted with the latch cap in BOTH arms; dp0's b is its ledger REBUILT from its own assigns, dp1's "
        "its live ledger (R-B, A2 22.2); the ledger-allowed zero is I4 as amended by A2 22.1")
    blk = [(r["cell"]["id"], arm, x) for r in cells for arm in ("d0", "d1")
           for x in r[arm]["lists"].get("gb_f_blocked", [])]
    out("    every ledger-blocked victim-step, by cell (dp0 and dp1; [step, victim, [[unit, d, b], ...]]): %s" % (
        "none" if not blk else ""))
    for cid, arm, x in blk:
        out("      %s %s %s" % (cid, "dp0" if arm == "d0" else "dp1", x))
    gate_line("    cross-check: _sd_analyze I5 double binding", cells, "i5_double", report_only=True)
    for key in ("gb_b", "gb_c", "gb_f_allowed", "gb_f_blocked"):
        rows = [(r["cell"]["id"], x) for r in cells for x in r["d1"]["lists"].get(key, [])[:3]]
        if rows:
            out("    dp1 %s examples: %s" % (key, rows[:6]))
    exc = [(r["cell"]["id"], x) for r in cells for x in r["d1"]["lists"].get("gb_c_excused", [])]
    nos = [(r["cell"]["id"], x) for r in cells for x in r["d1"]["lists"].get("gb_c_nosample", [])]
    if exc or nos:
        out("    G-B(c) J-pre events excused by an outside event %s | events without a binders sample %s" % (exc[:6],
                                                                                                         nos[:6]))
    out("G-T   flip-flops from dp.commands (returns A..X..A / v..w..v; outside = o1 handler unassign, o2 route_blocked "
        "while bound, o3 death)")
    G["G-T(a)"] = gate_line("(a) returns without an outside event", cells, "gt_a", structural=True)
    gate_line("    the same, o2@frame NOT accepted (strict)", cells, "gt_a_strict", report_only=True)
    G["G-T(b)"] = gate_line("(b) all returns, any cause", cells, "gt_b")
    G["G-T(c)"] = gate_line("(c) ledger violations", cells, "gt_c", structural=True)
    for r in cells:
        for x in r["d1"]["lists"].get("gt_a", []):
            out("    dp1 G-T(a) %s %s" % (r["cell"]["id"], x))
        for x in r["d1"]["lists"].get("gt_c", []):
            out("    dp1 G-T(c) %s %s" % (r["cell"]["id"], x))
        frame = [x for x in r["d1"]["lists"].get("gt_b", []) if "o2@frame" in x["outside"]]
        for x in frame:
            out("    dp1 return explained by o2@frame only-or-also %s %s" % (r["cell"]["id"], x))
        mism = r["d1"]["lists"].get("ledger_mismatch")
        if mism:
            out("    dp1 %s dp.ledger vs successful assigns in dp.commands disagree: %s" % (r["cell"]["id"], mism[:6]))
    G["dp1 crashes"] = not st["crash_dp1"]
    out("  %-40s %d %s  %s" % ("dp1 crashes / early stops (S2)", len(st["crash_dp1"]), st["crash_dp1"][:4],
                               "PASS" if not st["crash_dp1"] else "FAIL"))
    return G


def rb_report(recs):
    """A2 22.2: print the three R-B tooling checks over every run of every arm; True when one fails."""
    tot, cmp_n = collections.Counter(), collections.Counter()
    ex = collections.defaultdict(list)
    for r in recs:
        for arm, chk in (("dpR", r.get("rb_dpR")), ("dp0", (r["d0"] or {}).get("rb_checks")),
                         ("dp1", (r["d1"] or {}).get("rb_checks"))):
            if not chk:
                continue
            for k in ("i", "ii", "iii", "refused", "dup"):
                tot[(k, arm)] += len(chk[k])
                ex[(k, arm)] += [(r["cell"]["id"], x) for x in chk[k][:2]]
            tot[("noids", arm)] += chk["m3a_noids"]
            for k in ("n_i", "n_ii", "n_iii"):
                cmp_n[(k, arm)] += int(chk.get(k) or 0)
    fail = any(tot.values())
    out("R-B   tooling checks of the rebuilt ledger (A2 22.2; a failure STOPS the R-B figures, no run is re-run) - "
        "failures / comparisons made: (i) dp1 recorded b != rebuild %d / %d | (ii) m3a n_ok or ids inconsistent dpR %d "
        "dp0 %d dp1 %d (dp1 n_ok compared %d) | (iii) binder with b < 1 under the step's cut dpR %d / %d, dp0 %d / %d, "
        "dp1 %d / %d | init / sweep assigns (refused) dpR %d dp0 %d dp1 %d | m3a rows without ids %d | duplicate "
        "sample steps %d  => %s" % (
            tot[("i", "dp1")], cmp_n[("n_i", "dp1")], tot[("ii", "dpR")], tot[("ii", "dp0")], tot[("ii", "dp1")],
            cmp_n[("n_ii", "dp1")], tot[("iii", "dpR")], cmp_n[("n_iii", "dpR")], tot[("iii", "dp0")],
            cmp_n[("n_iii", "dp0")], tot[("iii", "dp1")], cmp_n[("n_iii", "dp1")],
            tot[("refused", "dpR")], tot[("refused", "dp0")], tot[("refused", "dp1")],
            sum(tot[("noids", a)] for a in ("dpR", "dp0", "dp1")),
            sum(tot[("dup", a)] for a in ("dpR", "dp0", "dp1")), "FAIL" if fail else "PASS"))
    for key, rows in sorted(ex.items()):
        if rows:
            out("    %s %s examples: %s" % (key[1], key[0], rows[:4]))
    return fail


def sec_rbgate(opts):
    ref_tag, g0_tag, g1_tag = opts.gate_tags
    head("G-RB route_blocked gate (14.6, D-15): %s vs %s - pooled rescued over the 18 runs not lower, 0 latched, every"
         " per-seed loss listed for diagnosis (CRN off)" % (g1_tag, ref_tag))
    if opts.smoke and not opts.smoke_gate:
        out("  NOT RUN (smoke)")
        return {"status": "NOT RUN", "latched": None}
    ref, g1 = load_shards(ref_tag, opts), load_shards(g1_tag, opts)
    pooled = collections.Counter()
    losses, missing, invalid = [], [], []
    for sid, wind in SHARDS:
        a, b = ref.get(sid), g1.get(sid)
        if a is None or b is None:
            missing.append(sid)
            out("  shard %s MISSING" % sid)
            continue
        if b["prov"]:
            invalid.append((sid, b["prov"]))
            out("  INVALID %s%s: %s" % (g1_tag, sid, "; ".join(b["prov"])))
        z, s = a["data"], b["data"]
        ez = {int(e["seed"]): e for e in z.get("evals") or []}
        es = {int(e["seed"]): e for e in s.get("evals") or []}
        ls = []
        for seed in sorted(set(ez) | set(es)):
            rz, rs = (ez.get(seed) or {}).get("rescued"), (es.get(seed) or {}).get("rescued")
            if rz is None or rs is None:
                ls.append((seed, rz, rs, "seed missing in one arm"))
            elif rs < rz:
                ls.append((seed, rz, rs, ""))
        out("  shard %s %-5s rescued %d -> %d | dead %d -> %d | ff deaths %d -> %d | latched %d -> %d | losses %s" % (
            sid, wind, sum(e.get("rescued") or 0 for e in ez.values()), sum(e.get("rescued") or 0 for e in es.values()),
            sum(e.get("dead") or 0 for e in ez.values()), sum(e.get("dead") or 0 for e in es.values()),
            sum(e.get("firefighter_deaths") or 0 for e in ez.values()),
            sum(e.get("firefighter_deaths") or 0 for e in es.values()), len(z.get("latched") or []),
            len(s.get("latched") or []), [x[:3] for x in ls] or "none"))
        pooled["r0"] += sum(e.get("rescued") or 0 for e in ez.values())
        pooled["r1"] += sum(e.get("rescued") or 0 for e in es.values())
        pooled["n"] += len(es)
        pooled["latched"] += len(s.get("latched") or [])
        for seed, rz, rs, note in ls:
            losses.append((sid, wind, seed))
            out("    LOSS shard %s seed %s: rescued %s -> %s %s" % (sid, seed, rz, rs, note))
            for tag, dd in ((ref_tag, z), (g1_tag, s)):
                e = next((x for x in dd.get("evals") or [] if int(x["seed"]) == seed), {})
                out("      %-5s eval rescued %s dead %s ff_deaths %s terminal %s unreachable %s" % (
                    tag, e.get("rescued"), e.get("dead"), e.get("firefighter_deaths"), e.get("terminal_step"),
                    e.get("unreachable")))
                for k in ("assigns", "fires", "recoveries", "deaths", "latched"):
                    rows = [x for x in dd.get(k) or [] if int(x.get("seed", -1)) == seed]
                    brief = [(x.get("step"), x.get("ff"), x.get("vid"), x.get("reason"),
                              x.get("reachable_at_assign")) if k == "assigns" else
                             (x.get("step"), x.get("ff"), x.get("pos")) for x in rows]
                    out("        %-10s %d %s" % (k, len(rows), brief[:14]))
            az = [(x.get("step"), x.get("ff"), x.get("vid")) for x in z.get("assigns") or [] if int(x["seed"]) == seed]
            as_ = [(x.get("step"), x.get("ff"), x.get("vid")) for x in s.get("assigns") or [] if int(x["seed"]) == seed]
            fd = first_div(az, as_)
            out("      first dispatch decision differing from %s: %s | fire-stream divergence: NOT RECORDED by "
                "_rblatch_campaign2 (no fire digest) - D-15 adjudication by hand" % (
                    ref_tag, "none" if fd is None else "step %s (%s vs %s)" % (
                        min(x[0] for x in (fd[1], fd[2]) if x), fd[1], fd[2])))
    complete = not missing and pooled["n"] == 18
    ok = pooled["r1"] >= pooled["r0"] and pooled["latched"] == 0
    if pooled["latched"]:
        status = "FAIL"                      # a structural zero, failing whatever else is missing
    elif not complete:
        status = "MISSING"
    elif invalid:
        status = "INVALID"
    else:
        status = "PASS" if ok else "FAIL"
    if opts.smoke:
        status = "EXERCISED (smoke: same files on every side)"
    out("  POOLED %d runs: rescued %d -> %d | latched at end %d | per-seed losses %d %s  => %s" % (
        pooled["n"], pooled["r0"], pooled["r1"], pooled["latched"], len(losses), losses or "", status))
    return {"status": status, "latched": pooled["latched"] if complete else None}


def read_text_any(path):
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or raw[:200].count(b"\x00") > 20:
        return raw.decode("utf-16", "replace")
    return raw.decode("utf-8", "replace")


def sec_suite(opts):
    head("G-S / G-INV - full suite at the final source: exactly B's failing set %s; T-INV and the dispatch unit tests "
         "green" % sorted(EXPECTED_FAILS))
    if not opts.suite_log:
        out("  G-S NOT RUN (no --suite-log) | G-INV NOT RUN")
        return "NOT RUN", "NOT RUN"
    try:
        text = read_text_any(opts.suite_log)
    except OSError as exc:
        out("  G-S suite log unreadable %r" % (exc,))
        return "FAIL", "FAIL"
    failed, summary = set(), None
    for ln in text.splitlines():
        s = ln.strip()
        m = re.match(r"^(FAILED|ERROR)\s+(\S+)", s)
        if m and m.group(2).replace("\\", "/").startswith("tests/"):     # not captured-log 'ERROR <logger>' lines
            failed.add(m.group(2).replace("\\", "/"))
        if re.search(r"\b\d+ (passed|failed)\b", s) and (" in " in s or s.startswith("=")):
            summary = s.strip("= ")
    ok = summary is not None and failed == EXPECTED_FAILS
    inv_bad = sorted(f for f in failed if f.startswith("tests/test_dispatch_") or f == TINV)
    inv = "PASS" if summary is not None and not inv_bad else "FAIL"
    out("  summary: %s" % summary)
    out("  failing set %s  => G-S %s | G-INV (T-INV + tests/test_dispatch_*) %s %s" % (
        sorted(failed), "PASS" if ok else "FAIL", inv, inv_bad or ""))
    return ("PASS" if ok else "FAIL"), inv


# ================================================================================================ 4 MEASURES
def sec_measures(recs, opts, s1="?", rb_fail=False):
    cells = pairs(recs)
    M = {}
    head("4 MEASURES (14.7) - M1 PRIMARY: per victim rescued in BOTH arms, delta = (rescue - detection) dp1 minus dp0;"
         " m_c = mean delta per cell; T = unweighted mean of m_c")
    n_cells = {s: sum(1 for r in recs if r["cell"]["set"] == s) for s in ("set1", "set2")}
    p1, p1c = collections.defaultdict(list), collections.defaultdict(list)
    no_pair, only_one, anomalies, vict = [], [], [], []
    for r in cells:
        c, g0, g1 = r["cell"], r["d0"], r["d1"]
        for v in g0["victims"]:
            t0, t1 = g0["det"].get(v), g1["det"].get(v)
            r0, r1 = g0["resc"].get(v), g1["resc"].get(v)
            if r0 and r1:
                if t0 is None or t1 is None:
                    anomalies.append((c["id"], v, "rescued without a detection line", t0, t1))
                else:
                    dl = (r1 - t1) - (r0 - t0)
                    p1[c["id"]].append(dl)
                    vict.append((c, v, dl))
            if t0 is not None and t1 is not None:
                p1c[c["id"]].append(((r1 or g1["censor"]) - t1) - ((r0 or g0["censor"]) - t0))
            elif (t0 is None) != (t1 is None):
                only_one.append((c["id"], v, t0, t1))
        if not p1.get(c["id"]):
            no_pair.append(c["id"])
    by_id = {r["cell"]["id"]: r["cell"] for r in recs}
    m1 = cell_means(p1)
    m1c = cell_means(p1c)
    m_by_set = {s: {k: v for k, v in m1.items() if by_id[k]["set"] == s} for s in ("set1", "set2")}
    mc_by_set = {s: {k: v for k, v in m1c.items() if by_id[k]["set"] == s} for s in ("set1", "set2")}
    s3 = s3_statistic(m_by_set, 32 if not opts.smoke else len(recs))
    s4 = s4_statistic(mc_by_set)
    M["S3"], M["S4"] = s3, s4
    out("  contributing cells: set1 %d / %d, set2 %d / %d | cells without a pair (listed, excluded): %s" % (
        s3["n"]["set1"], n_cells["set1"], s3["n"]["set2"], n_cells["set2"], no_pair or "none"))
    out("  T(set1) %s  T(set2) %s  T(pooled) %s | after removing the most negative m_c: set1 %s set2 %s pooled %s" % (
        fmt(s3["T"]["set1"]), fmt(s3["T"]["set2"]), fmt(s3["T"]["pooled"]), fmt(s3["loo"]["set1"]),
        fmt(s3["loo"]["set2"]), fmt(s3["loo"]["pooled"])))
    out("  S3 => %s" % s3["verdict"])
    for name, sel in (("ring", lambda c: c["plc"] == "ring"), ("uniform", lambda c: c["plc"] == "uniform")) + \
            SCEN_GROUPS:
        vals = [v for k, v in m1.items() if sel(by_id[k])]
        out("    T(%-7s) %s over %d cells" % (name, fmt(mean(vals)), len(vals)))
    allv = [x[2] for x in vict]
    out("  victim-pooled: n %d mean %s median %s | Wilcoxon signed-rank on m_c (reported): pooled %s" % (
        len(allv), fmt(mean(allv)), fmt(statistics.median(allv) if allv else None),
        wil_str(wilcoxon(list(m1.values())))))
    for s in ("set1", "set2"):
        out("    Wilcoxon %s %s" % (s, wil_str(wilcoxon(list(m_by_set[s].values())))))
    out("  m_c per cell: %s" % ", ".join("%s %+.1f" % (k, v) for k, v in sorted(m1.items())))
    if anomalies:
        out("  ANOMALY rescued victims without a stdout detection: %s" % anomalies[:8])
    out("M1c CENSORED (rescue step or %s) - detection, all victims detected in both arms; the same per-cell "
        "statistic" % (
        "361" if not opts.smoke else "last step + 1"))
    out("  T(set1) %s  T(set2) %s  T(pooled) %s | contributing cells set1 %d, set2 %d | S4 (<= 0 pooled and per set)"
        " => %s" % (fmt(s4["T"]["set1"]), fmt(s4["T"]["set2"]), fmt(s4["T"]["pooled"]), s4["n"]["set1"],
                    s4["n"]["set2"], s4["verdict"]))
    out("  victims detected in one arm only (listed, excluded): %s" % (only_one or "none"))
    # ---------------------------------------------------------------- M2
    out("M2 outcomes from eval (rescued / dead / firefighter deaths / never_detected / unreachable by cause)")
    keys = ("rescued", "dead", "firefighter_deaths", "never_detected", "unreachable", "geographically_isolated",
            "no_firefighter_available", "unreachable_other")
    tot = {}
    for gname, sel in GROUPS + SCEN_GROUPS:
        for arm in ("d0", "d1"):
            tot[(gname, arm)] = {k: sum(int(r[arm]["eval"].get(k) or 0) for r in cells if sel(r["cell"])) for k in keys}
        out("  %-8s dp0 %s" % (gname, " ".join("%s=%d" % (k, v) for k, v in tot[(gname, "d0")].items())))
        out("  %-8s dp1 %s" % ("", " ".join("%s=%d" % (k, v) for k, v in tot[(gname, "d1")].items())))
    s5 = {"rescued set1": tot[("set1", "d1")]["rescued"] >= tot[("set1", "d0")]["rescued"],
          "rescued set2": tot[("set2", "d1")]["rescued"] >= tot[("set2", "d0")]["rescued"],
          "dead pooled": tot[("pooled", "d1")]["dead"] <= tot[("pooled", "d0")]["dead"],
          "ff deaths pooled": (tot[("pooled", "d1")]["firefighter_deaths"]
                               <= tot[("pooled", "d0")]["firefighter_deaths"])}
    M["S5"] = {"pass": all(s5.values()), "items": s5}
    out("  S5 outcome guards: %s  => %s" % (s5, "PASS" if all(s5.values()) else "FAIL"))
    stop = [(s, tot[(s, "d0")]["rescued"], tot[(s, "d1")]["rescued"]) for s in "ABCD"
            if tot[(s, "d1")]["rescued"] - tot[(s, "d0")]["rescued"] <= -2]
    M["scenario_stop"] = stop
    out("  per-scenario pooled rescued dp0 -> dp1: %s | falls by >= 2: %s" % (
        {s: "%d->%d" % (tot[(s, "d0")]["rescued"], tot[(s, "d1")]["rescued"]) for s in "ABCD"}, stop or "none"))
    # ---------------------------------------------------------------- G-N 21.2(f)
    out("G-N reported addition 21.2(f): cells differing in rescued by >= 2 or in firefighter deaths, cells where all "
        "units die, cells switching between never-finishes and finishes-with-a-death")
    listed = 0
    for r in cells:
        g0, g1 = r["d0"], r["d1"]
        e0, e1 = g0["eval"], g1["eval"]
        why = []
        if abs(int(e1.get("rescued") or 0) - int(e0.get("rescued") or 0)) >= 2:
            why.append("rescued %s->%s" % (e0.get("rescued"), e1.get("rescued")))
        if int(e1.get("firefighter_deaths") or 0) != int(e0.get("firefighter_deaths") or 0):
            why.append("ff deaths %s->%s" % (e0.get("firefighter_deaths"), e1.get("firefighter_deaths")))
        for arm, g, e in (("dp0", g0, e0), ("dp1", g1, e1)):
            if g["n_ff"] and int(e.get("firefighter_deaths") or 0) >= g["n_ff"]:
                why.append("all units die in %s" % arm)
        fin = lambda g, e: g["terminal"] is not None and int(e.get("dead") or 0) >= 1      # noqa: E731
        if (g0["terminal"] is None and fin(g1, e1)) or (g1["terminal"] is None and fin(g0, e0)):
            why.append("never-finishes <-> finishes with a death (terminal %s -> %s)" % (g0["terminal"],
                                                                                          g1["terminal"]))
        if why:
            listed += 1
            diagnose(r, why)
    if not listed:
        out("  none")
    # ---------------------------------------------------------------- M3 / M4
    out("M3 idle while a detected victim waits (dp.waiting, sampled as G-B(f)): (a) unit-steps free while a detected "
        "needy victim without an active binder exists (recomputed in both arms from the m3a free-unit ids); (b) the "
        "same with a finite d; both ledger-allowed / ledger-blocked with the latch cap in BOTH arms and dp0's ledger "
        "rebuilt from its own assigns (R-B, A2 22.2)")
    if rb_fail:
        out("  STOPPED (an R-B tooling check failed, A2 22.2): the M3 ledger-allowed / ledger-blocked split is not read")
        gate_line("m3a", cells, "m3a", report_only=True)
    else:
        for name in ("m3a", "m3a_allowed", "m3a_blocked", "m3b_allowed", "m3b_blocked"):
            gate_line(name, cells, name, report_only=True)
    out("G-B(f) ledger-allowed split (the structural count above, by victim set - W = no living binder, W_L = "
        "latched-held; under A2 (22.1) the second fill also serves W_L with the latch cap, so both are structural "
        "zeros in dp1)")
    if rb_fail:
        out("  STOPPED (an R-B tooling check failed, A2 22.2)")
    else:
        for name in ("gb_f_allowed_W", "gb_f_allowed_WL"):
            gate_line(name, cells, name, report_only=True)
    out("M4 reassignments (dp1 j_events) per scenario; LATCH-FILLs apart from REPLACEs; the SECOND FILL's binds (stage "
        "4: second_fill_s4, latch_fill_s4 - units a REPLACE released, A2) apart, with the cause of that REPLACE; "
        "counterfactual (dp.j_calls legacy vs j_fills, stage-4 binds excluded - 22.4 P2-7); re-used-pair binds "
        "(b_before >= 1, dp.commands); ledger-blocked victim-steps for BOTH arms (gb_f_blocked dp1, gb_f_blocked_dp0 "
        "with the rebuilt ledger - R-B, A2 22.2); what J saw (dp.j_detail): PRE points, progress evaluations, FROZEN "
        "evaluations, bindings left unevaluated (d or x infinite - note P2-3)")
    for s, sel in SCEN_GROUPS:
        sub = [r for r in cells if sel(r["cell"])]
        c = collections.Counter()
        for r in sub:
            for k in ("replace_stall", "replace_margin", "replace_other", "latch_fill", "fill", "second_fill",
                      "second_fill_s4", "latch_fill_s4", "refused", "aborted", "cf_points", "cf_diff", "reused_binds",
                      "gb_f_blocked", "j_pre_points", "prog_evals", "prog_frozen", "prog_unevaluated"):
                if not (rb_fail and k == "gb_f_blocked"):
                    c[k] += r["d1"]["num"].get(k, 0)
            if not rb_fail:
                c["gb_f_blocked_dp0"] += r["d0"]["num"].get("gb_f_blocked", 0)
            c["reused_dp0"] += r["d0"]["num"].get("reused_binds", 0)
        out("  %s %s%s" % (s, dict(c), " (ledger-blocked victim-steps STOPPED - R-B, A2 22.2)" if rb_fail else ""))
    s4 = [(r["cell"]["id"], x) for r in cells for x in r["d1"]["lists"].get("stage4", [])]
    out("  stage-4 binds (%d) [step, phase, kind, victim, unit, units released by this bind (a LATCH-FILL's latched "
        "binders), cause of the REPLACE that released the unit]: %s" % (len(s4), "none" if not s4 else ""))
    for cid, x in s4:
        out("    %s %s" % (cid, x))
    cf = [(r["cell"]["id"], x) for r in cells for x in r["d1"]["lists"].get("cf_diff", [])]
    out("  counterfactual differences (first 8 of %d): %s" % (len(cf), cf[:8]))
    # ---------------------------------------------------------------- M5
    out("M5 latency detection -> assignment (dp.commands) -> pickup (rows_ff exiting False->True) -> rescue "
        "(rows_vic), "
        "rescued victims; realised steps to pickup minus d_route at binding (step difference)")
    for arm in ("d0", "d1"):
        comp = collections.defaultdict(list)
        rmd, nop, clo = [], 0, 0
        for r in cells:
            g = r[arm]
            for v, (t, a, p, s) in g["lat"].items():
                if None in (t, a, p, s):
                    continue
                comp["det->assign"].append(a - t)
                comp["assign->pickup"].append(p - a)
                comp["pickup->rescue"].append(s - p)
            rmd += g["rmd"]
            nop += g["num"].get("rmd_nopickup", 0)
            clo += g["num"].get("rmd_closed", 0)
        out("  %s %s | realised - d: n %d median %s mean %s (negative %d, zero %d, positive %d); bindings without "
            "pickup %d, closed at bind %d" % (
                "dp0" if arm == "d0" else "dp1",
                " ".join("%s median %s mean %s (n %d)" % (k, fmt(statistics.median(v) if v else None, "%.1f"),
                                                          fmt(mean(v), "%.1f"), len(v)) for k, v in comp.items()),
                len(rmd), fmt(statistics.median(rmd) if rmd else None, "%.1f"), fmt(mean(rmd), "%.1f"),
                sum(1 for x in rmd if x < 0), sum(1 for x in rmd if x == 0), sum(1 for x in rmd if x > 0), nop, clo))
    paired = collections.defaultdict(list)
    for r in cells:
        for v in r["d0"]["victims"]:
            a, b = r["d0"]["lat"].get(v), r["d1"]["lat"].get(v)
            if a and b and None not in a and None not in b:
                paired["det->assign"].append((b[1] - b[0]) - (a[1] - a[0]))
                paired["assign->pickup"].append((b[2] - b[1]) - (a[2] - a[1]))
                paired["pickup->rescue"].append((b[3] - b[2]) - (a[3] - a[2]))
    out("  paired dp1 - dp0 (victims rescued in both): %s" % " ".join(
        "%s mean %s" % (k, fmt(mean(v), "%+.2f")) for k, v in paired.items()))
    # ---------------------------------------------------------------- M6
    out("M6 write-offs: escape sweep (mark_unreachable in the sweep phase), dispatch write-offs (other phases), "
        "would-have-been casualty write-offs (dp.writeoffs_avoided), assigns into a closed route (dp.commands "
        "route_open "
        "False, the instrument's BFS)")
    for name in ("escape_writeoffs", "dispatch_writeoffs", "writeoffs_avoided", "assign_closed"):
        gate_line(name, cells, name, report_only=True)
    # ---------------------------------------------------------------- M7 / S6
    rr, jms = [], []
    for r in recs:
        g = r.get("d1")
        if not g:
            continue
        jms += g["j_ms"]
        if g.get("usable") and g.get("wall_s"):
            rr.append(g["j_ms_total"] / (g["wall_s"] * 1000.0))
    w0 = sum(r["d0"]["wall_s"] for r in cells)
    w1 = sum(r["d1"]["wall_s"] for r in cells)
    ratios = [r["d1"]["wall_s"] / r["d0"]["wall_s"] for r in cells if r["d0"]["wall_s"]]
    med_r = statistics.median(rr) if rr else None
    p99 = q(jms, 0.99)
    s6 = med_r is not None and p99 is not None and med_r <= 0.02 and p99 <= 50.0
    M["S6"] = {"pass": s6, "median_R": med_r, "p99": p99}
    out("M7 dispatch cost: R = dp.timing.j_ms_total / (wall_s x 1000) over %d dp1 runs: median %s (max %s) | J ms "
        "per J "
        "point over %d points: p50 %s p99 %s max %s | wall dp1 / dp0 pooled %s, per-cell median %s" % (
            len(rr), fmt(None if med_r is None else 100 * med_r, "%.3f%%"),
            fmt(None if not rr else 100 * max(rr), "%.3f%%"), len(jms), fmt(q(jms, 0.5), "%.3f"), fmt(p99, "%.3f"),
            fmt(max(jms) if jms else None, "%.3f"), fmt(w1 / w0 if w0 else None, "%.3f"),
            fmt(statistics.median(ratios) if ratios else None, "%.3f")))
    out("  S6 (median R <= 2%%, p99 J <= 50 ms) => %s" % ("PASS" if s6 else "FAIL"))
    # ---------------------------------------------------------------- M8
    out("M8 (D-11 ACTIVE) detected-victim deaths by the TRUE arrival (dp.m8): FEASIBLE-CRITICAL iff min_d + 1 <= "
        "death - detection, else FUTILE. The urgency-round trigger is read on dp0 ONLY (R-C, A2 22.3), over EVERY "
        "usable dp0 run of the 64 cells (not only paired cells): MET iff in BOTH seed sets there is at least one "
        "detected-victim death and feasible-critical >= 25%% of them. Read only after S1 passes (S1 here: %s)" % s1)
    for arm in ("d0", "d1"):
        name = "dp0" if arm == "d0" else "dp1"
        # every VALID run that finished (14.5): INVALID runs and crashed / early-stopped runs are left out, counted
        usable = [r for r in recs if r[arm] and r[arm].get("usable") and not r["prov"].get(name)
                  and not r["crash"].get(name)]
        excl = sum(1 for r in recs if r[arm] and (r["prov"].get(name) or r["crash"].get(name)))
        out("  %s: %d valid finished runs used, %d INVALID or crashed runs left out" % (name, len(usable), excl))
        counts = {}
        for s in ("set1", "set2"):
            rows = []
            bias_burn, bias_death, cens, nofire = [], [], 0, 0
            fc = fu = 0
            sub = [r for r in usable if r["cell"]["set"] == s]
            for r in sub:
                g = r[arm]
                for e in g["m8"]:
                    det, dth, tf = e.get("detection_step"), e.get("death_step"), e.get("t_fire")
                    if tf is None:
                        nofire += 1
                    else:
                        fb = e.get("first_burn_step")
                        if fb is None:
                            cens += 1
                            fb = g["steps_done"] if opts.smoke else H
                        bias_burn.append(tf - (fb - det))
                        if dth is not None:
                            bias_death.append(tf - (dth - det))
                a, b, rws = m8_classify(g["m8"])
                fc += a
                fu += b
                rows += [(r["cell"]["id"],) + x for x in rws]
            counts[s] = (fc, fu)
            n = fc + fu
            q1b, mb, q3b = iqr(bias_burn)
            q1d, md_, q3d = iqr(bias_death)
            out("  %s %s over %d usable runs: detected-victim deaths %d: feasible-critical %d futile %d (%s) | T_fire "
                "bias vs first burn (censored at %d: %d; no estimate %d) median %s IQR [%s, %s] n %d | vs death median "
                "%s IQR [%s, %s] n %d"
                % ("dp0" if arm == "d0" else "dp1", s, len(sub), n, fc, fu, fmt(100.0 * fc / n if n else None, "%.0f%%"),
                   H, cens, nofire, fmt(mb, "%.1f"), fmt(q1b, "%.1f"), fmt(q3b, "%.1f"), len(bias_burn),
                   fmt(md_, "%.1f"), fmt(q1d, "%.1f"), fmt(q3d, "%.1f"), len(bias_death)))
            for row in rows[:12]:
                out("      %s" % (row,))
        if arm == "d0":
            M["M8"] = {"met": m8_trigger(counts), "counts": counts, "read": s1 == "PASS"}
            out("  dp0 25%% TRIGGER (both sets, at least one death each): %s" % (
                ("MET - propose an urgency round" if M["M8"]["met"] else "not met") if s1 == "PASS"
                else "NOT READ (S1 not established - 22.3)"))
        else:
            out("  dp1: reported, not the trigger")
    # ---------------------------------------------------------------- M9
    out("M9 (K13, record only): fills binding a unit freed by an o1 raise on v to w != v while d(., v) infinite: "
        "[step, unit, v, w, frames_finite (P = 3 samples), v's end status]")
    m9 = [(r["cell"]["id"], x) for r in cells for x in r["d1"]["m9"]]
    for cid, x in m9:
        out("  %s %s -> v finite within P: %s" % (cid, x, any(bool(f) for f in (x[4] or []))))
    if not m9:
        out("  none")
    return M


def diagnose(r, why):
    g0, g1 = r["d0"], r["d1"]
    cd = first_cmd_div(g0, g1)
    sd = first_state_div(g0, g1)
    out("  %s: %s" % (r["cell"]["id"], "; ".join(why)))
    out("     first dispatch-decision divergence %s | first state divergence %s" % (
        "none" if cd is None else "step %s (dp0 %s / dp1 %s)" % cd, "none" if sd is None else "step %s (%s)" % sd))
    for arm, g in (("dp0", g0), ("dp1", g1)):
        out("     %s eval rescued %s dead %s ff_deaths %s terminal %s | ff deaths at %s | victim deaths %s" % (
            arm, g["eval"].get("rescued"), g["eval"].get("dead"), g["eval"].get("firefighter_deaths"), g["terminal"],
            g["ff_dead"], g["vdead"]))
        out("        binds %s" % [(c[0], c[1], c[4], c[3], c[5]) for c in g["cmds"] if c[2] == "assign" and c[6]][:12])


# ================================================================================================ 5 EVIDENCE
EV_RE = re.compile(r"^dpE(1|2|2f|x|3|4d|4g)([01])([nc])$")
ORIGINALS = {("1", "n"): "_ffr_fx3hS_D_south_half_505.json", ("2", "n"): "_sd_fb3bdr2_D_W.json",
             ("2f", "n"): "_sd_fb3bfr2_D_W.json",
             ("x", "n"): "_sd_fb3bdr2_D_N.json", ("3", "c"): "_sd_ut0r2_D_N.json",
             ("4d", "c"): "_sd_bpdr_D_N.json", ("4g", "c"): "_sd_bpgr_D_N.json"}


def ev_digest(path):
    """A light digest of one evidence or original run (probe JSON with or without d['dp'], or an _ffr harness JSON)."""
    d = load_json(path)
    det, disp = parse_stdout(path)
    e = {"path": os.path.basename(path), "det": det or {}, "disp": disp, "eval": d.get("eval") or {},
         "terminal": d.get("terminal_step"), "extra": d.get("extra_params")}
    if "ff_steps" in d:            # _ffr harness record (or _fm2_probe_harness: the same plus d["fm2p"])
        e["kind"] = "harness"
        if isinstance(d.get("fm2p"), dict):      # 21.2(e): a CRN case-1 run must show crn_draws > 0
            e["crn"] = {"fm2p crn_draws": ((d["fm2p"].get("counters") or {}).get("crn_draws"))}
        e["assigns"] = [(a["step"], a["ff"], a["vid"], a.get("reason"), bool(a.get("ok"))) for a in d.get("assigns")
                        or []]
        e["unassigns"] = [(a["step"], a["ff"], a["vid"], a.get("reason"), bool(a.get("ok"))) for a in
                          d.get("unassigns") or []]
        fb = {}
        for s, ff, v, _r, ok in e["assigns"]:
            if ok and v not in fb:
                fb[v] = (s, ff)
        e["first_dispatch"] = fb
        e["cmd_seq"] = sorted([(s, "assign", v, ff, ok) for s, ff, v, _r, ok in e["assigns"]] +
                              [(s, "unassign", v, ff, ok) for s, ff, v, _r, ok in e["unassigns"]])
        n = len(d.get("ff_steps") or [])
        e["h"] = hashes([[(d.get("ff_steps") or [None] * n)[t], (d.get("victim_steps") or [None] * n)[t]
                          if t < len(d.get("victim_steps") or []) else None,
                          (d.get("uav_steps") or [None] * n)[t] if t < len(d.get("uav_steps") or []) else None]
                         for t in range(n)])
        e["j_events"] = []
        e["seq"] = sorted([(s, "assign", ff, v, r) for s, ff, v, r, ok in e["assigns"] if ok] +
                          [(s, "unassign", ff, v, r) for s, ff, v, r, ok in e["unassigns"] if ok])
        e["fire"] = d.get("fire_digests") or []
        return e
    e["kind"] = "probe"
    fb = {}
    for t, row in enumerate(d.get("rows_ff") or []):
        for r in row:
            if r[8] and r[8] not in fb:
                fb[r[8]] = (t + 1, r[0])
    e["first_dispatch"] = fb
    e["h"] = hashes([[a, b, c] for a, b, c in zip(d.get("rows_ff") or [], d.get("rows_vic") or [],
                                                   d.get("rows_uav") or [])])
    dp = d.get("dp") if isinstance(d.get("dp"), dict) else {}
    cmds = dp.get("commands") or []
    e["cmd_seq"] = [(c[0], c[2], c[3], c[4], bool(c[6])) for c in cmds if c[2] in ("assign", "unassign")]
    e["seq"] = [(c[0], c[1], c[2], c[4], c[3], c[5], c[8], c[9]) for c in cmds if c[2] in ("assign", "unassign")
                and c[6]]
    e["j_events"] = [(x.get("step"), x.get("phase"), x.get("kind"), x.get("unit"), x.get("victim_id"),
                      x.get("old_units"), x.get("distance")) for x in dp.get("j_events") or []]
    e["has_dp"] = bool(dp)
    e["crn"] = ((d.get("fb3") or {}).get("crn") or {})
    e["fire"] = []
    e["j_detail"] = list(dp.get("j_detail") or [])
    return e


def j_alternatives(j_detail, limit=12):
    """The J calls that ACTED, with what J saw (14.4): the sets, the d matrix and ledger of each fill, the contests
    (d, k, persistence) and spares of each replacement plan, and each binding's progress evaluation - so an evidence
    case can be described by the alternatives J rejected, not only by its outcome."""
    rows = []
    for step, phase, cur in j_detail:
        calls = cur.get("calls") or []
        acted = [c for c in calls if c.get("fn") in ("solve_fill", "plan_replacements") and c.get("out")]
        if not acted:
            continue
        parts = ["sets %s" % {k: v for k, v in (cur.get("sets") or {}).items() if v}]
        for c in calls:
            if c.get("fn") == "solve_fill":
                parts.append("fill d %s b %s capped %s -> %s" % (c.get("d"), c.get("b"), c.get("capped"), c.get("out")))
            elif c.get("fn") == "plan_replacements":
                parts.append("plan contests %s spares %s d %s clean %s -> %s" % (
                    c.get("contests"), c.get("spares"), c.get("d"), c.get("clean"), c.get("out")))
            elif c.get("fn") == "progress_step":
                parts.append("progress %s d %s x %s frozen %s %s->%s" % (
                    c.get("binding"), c.get("d"), c.get("x"), c.get("frozen"), c.get("before"), c.get("after")))
        if cur.get("unevaluated"):
            parts.append("unevaluated %s" % cur["unevaluated"])
        rows.append("%s %s: %s" % (step, phase, " | ".join(parts)))
        if len(rows) >= limit:
            break
    return rows


def ev_print(tag, e):
    out("  %s  %s | eval rescued %s dead %s ff_deaths %s terminal %s%s" % (
        tag, e["path"], e["eval"].get("rescued"), e["eval"].get("dead"), e["eval"].get("firefighter_deaths"),
        e["terminal"], " | crn %s" % e.get("crn") if e.get("crn") else ""))
    out("     extra_params %s" % json.dumps(e.get("extra"), sort_keys=True))
    crn = e.get("crn") or {}
    if tag.endswith("c") and not (int(crn.get("crn_draws") or 0) > 0 or int(crn.get("fm2p crn_draws") or 0) > 0):
        out("     WARNING: a CRN-on evidence line with 0 CRN draws (invalid evidence run, re-run it)")
    out("     first detections: %s" % ", ".join("%s %s" % (v, s) for v, s in sorted(e["det"].items(),
                                                                             key=lambda x: x[1])))
    out("     stdout [Dispatch] (after step marker, unit, victim, reason, manhattan): %s" % e["disp"][:10])
    out("     step-stamped dispatch sequence (%s): %s" % ("harness assigns/unassigns" if e["kind"] == "harness" else
                                                        "dp.commands" if e.get("has_dp") else "no dp layer",
                                                        e["seq"][:16]))
    if e["j_events"]:
        out("     dp.j_events (step, phase, kind, unit, victim, old units, d): %s" % e["j_events"][:12])
    for row in j_alternatives(e.get("j_detail") or []):
        out("     J saw at %s" % row)


def ev_divergence(a, b):
    cd = first_div(a["cmd_seq"], b["cmd_seq"])
    sd = first_div(a["h"], b["h"])
    fd = first_div(a.get("fire") or [], b.get("fire") or []) if a.get("fire") and b.get("fire") else None
    return ("none" if cd is None else "step %s (%s vs %s)" % (
        min(x[0] for x in (cd[1], cd[2]) if x), cd[1], cd[2]),
        "none" if sd is None else "step %d" % (sd[0] + 1),
        None if fd is None else "step %d" % (fd[0] + 1))


def mid_advance_check(e):
    """14.8 general check: replacements paired mid-advance (legacy route_blocked replacements; dp phase 'advance') that
    coincide with a same-step detection."""
    hits = []
    if e["kind"] == "harness":
        for s, ff, v, r, ok in e["assigns"]:
            if ok and "replacement" in str(r) and "blocked" in str(r):
                same = [x for x, t in e["det"].items() if t == s]
                if same:
                    hits.append((s, ff, v, r, same))
    else:
        for row in e["seq"]:
            if row[2] == "assign" and row[1] == "advance" and "replacement" in str(row[5]):
                same = [x for x, t in e["det"].items() if t == row[0]]
                if same:
                    hits.append((row[0], row[3], row[4], row[5], same))
    return hits


def sec_evidence(opts, smoke_pair=None):
    head("5 EVIDENCE (14.8, 21.2(a)) - described, not gated: first detections, dispatch sequence, first OFF/ON "
         "divergence, outcomes; ORIGINAL-CRN-mode OFF arms vs the recorded originals")
    if opts.smoke:
        out("  SMOKE EXERCISE: the smoke cell's dp0 (OFF) / dp1 (ON) as one configuration; reproduction check dp0 vs "
            "ref (both B defaults); the case-1 harness reader on the recorded original")
        e0, e1, er = (ev_digest(p) for p in smoke_pair)
        ev_print("dp0", e0)
        ev_print("dp1", e1)
        cd, sd, _fd = ev_divergence(e0, e1)
        out("     OFF vs ON first dispatch-decision divergence %s | first state divergence %s" % (cd, sd))
        rep = e0["det"] == er["det"] and e0["first_dispatch"] == er["first_dispatch"]
        out("     reproduction (dp0 vs ref): first detections %s, first dispatches %s => %s" % (
            "equal" if e0["det"] == er["det"] else "DIFFER", "equal" if e0["first_dispatch"] == er["first_dispatch"]
            else "DIFFER", "REPRODUCED" if rep else "NOT REPRODUCIBLE AT B"))
        p = os.path.join(HERE, ORIGINALS[("1", "n")])
        if os.path.exists(p):
            ev_print("orig case 1", ev_digest(p))
            out("     mid-advance replacements coinciding with a same-step detection: %s" % (
                mid_advance_check(ev_digest(p)) or "none"))
        return
    lines = Q.evidence()
    conf = collections.OrderedDict()
    for ln in lines:
        a = ln["argv"]
        tag = a[a.index("--tag") + 1].split("_")[0]
        m = EV_RE.match(tag)
        if not m:
            out("  UNPARSED evidence tag %s" % tag)
            continue
        conf.setdefault((m.group(1), m.group(3)), {})[m.group(2)] = (tag, ln["out"])
    for (case, crn), arms in conf.items():
        out("-- case %s, CRN %s" % (case, "on" if crn == "c" else "off"))
        dig = {}
        for arm in ("0", "1"):
            tag, path = arms.get(arm, (None, None))
            if tag is None or not os.path.exists(path):
                out("  %s MISSING (%s)" % (tag, os.path.basename(path or "?")))
                continue
            dig[arm] = ev_digest(path)
            ev_print(tag, dig[arm])
        if "0" in dig and "1" in dig:
            cd, sd, fd = ev_divergence(dig["0"], dig["1"])
            out("     OFF vs ON: first dispatch-decision divergence %s | first state divergence %s%s" % (
                cd, sd, "" if fd is None else " | first fire-digest divergence %s" % fd))
        if (case, crn) in ORIGINALS and "0" in dig:
            p = os.path.join(HERE, ORIGINALS[(case, crn)])
            if not os.path.exists(p):
                out("     original %s MISSING" % ORIGINALS[(case, crn)])
                continue
            o = ev_digest(p)
            det_eq = o["det"] == dig["0"]["det"]
            fd_eq = o["first_dispatch"] == dig["0"]["first_dispatch"]
            out("     ORIGINAL %s: detections %s | first dispatches (%s) %s" % (
                os.path.basename(p), sorted(o["det"].items(), key=lambda x: x[1]),
                "harness assigns" if o["kind"] == "harness" else "rows_ff first bound",
                sorted(o["first_dispatch"].items(), key=lambda x: x[1])))
            if not det_eq:
                out("       detections differ: %s" % sorted((v, o["det"].get(v), dig["0"]["det"].get(v))
                                                         for v in set(o["det"]) | set(dig["0"]["det"])
                                                         if o["det"].get(v) != dig["0"]["det"].get(v)))
            if not fd_eq:
                out("       first dispatches differ: %s" % sorted(
                    (v, o["first_dispatch"].get(v), dig["0"]["first_dispatch"].get(v))
                    for v in set(o["first_dispatch"]) | set(dig["0"]["first_dispatch"])
                    if o["first_dispatch"].get(v) != dig["0"]["first_dispatch"].get(v)))
            out("     => %s" % ("REPRODUCED" if det_eq and fd_eq else "NOT REPRODUCIBLE AT B"))
            hits = mid_advance_check(o)
            out("     general check (original): mid-advance replacements coinciding with a same-step detection: %s" % (
                hits or "none"))


# ================================================================================================ 6 DECISION
def bullet(bullets, prefix):
    return next((b for b in bullets if b.startswith(prefix)), "(outcome text not found)")


def sec_decision(sec15, ident, st, G, M, gs, ginv, rb, opts):
    head("6 DECISION RULE (section 15, pre-registered at %s)" % PART1)
    bullets = outcome_bullets(sec15)
    incomplete = bool(st["missing"] or st["invalid"] or ident.get("shard_invalid") or ident.get("shard_missing"))
    if opts.smoke:
        incomplete = False
    structural = collections.OrderedDict((
        ("G-ID mismatches", ident.get("mismatch", 0)),
        ("G-B(b) dp1", G.get("_v", {}).get("gb_b")),
        ("G-B(c) dp1", G.get("_v", {}).get("gb_c")),
        ("G-B(f) ledger-allowed dp1", G.get("_v", {}).get("gb_f_allowed")),
        ("G-T(a) dp1", G.get("_v", {}).get("gt_a")),
        ("G-T(c) dp1", G.get("_v", {}).get("gt_c")),
        ("dp1 crashes", len(st["crash_dp1"])),
        ("latched at the end of the gate shards", rb.get("latched"))))
    out("STRUCTURAL ZEROS (14.6): %s" % ", ".join("%s %s" % (k, "n/a" if v is None else v) for k, v in
                                                  structural.items()))
    # S1
    s1 = ident["probe"] and (ident["shards"] is True or (opts.smoke and ident["shards"] is None))
    s1_fail = ident["probe_same"] < ident["probe_compared"] or ident["shards"] is False
    out("S1 IDENTITY  %s (probe %d / %d, shards %s)" % ("PASS" if s1 else "FAIL" if s1_fail else "INCOMPLETE",
                                                        ident["probe_same"], ident["probe_compared"], ident["shards"]))
    gates = collections.OrderedDict((k, ("PASS" if v is True else "FAIL" if v is False else str(v)))
                                    for k, v in G.items() if not k.startswith("_"))
    gates["G-RB"] = rb["status"]
    gates["G-S"] = gs
    gates["G-INV"] = ginv
    fails = [k for k, v in gates.items() if v == "FAIL"]
    stopped = [k for k, v in gates.items() if str(v).startswith("STOPPED")]
    pend = [k for k, v in gates.items() if v not in ("PASS", "FAIL") and not str(v).startswith(("EXERCISED", "STOPPED"))]
    s2 = "FAIL" if fails else "PENDING" if (pend or stopped) else "PASS"
    out("S2 GATES     %s | failing %s | not run / missing %s | STOPPED by a failed R-B tooling check (A2 22.2) %s" % (
        s2, fails or "none", pend or "none", stopped or "none"))
    s3, s4, s5, s6 = M["S3"], M["S4"], M["S5"], M["S6"]
    out("S3 PRIMARY   %s" % s3["verdict"])
    out("S4 HARD-VICTIM TRADE %s" % s4["verdict"])
    out("S5 OUTCOME GUARDS %s %s" % ("PASS" if s5["pass"] else "FAIL", s5["items"]))
    out("S6 COST      %s (median R %s, p99 J %s ms)" % ("PASS" if s6["pass"] else "FAIL",
                                                       fmt(None if s6["median_R"] is None else 100 * s6["median_R"],
                                                           "%.3f%%"), fmt(s6["p99"], "%.3f")))
    if s1_fail:
        verdict, key = "STOP (S1 IDENTITY FAILED)", "S1 fails"
    elif s2 == "FAIL" or not s5["pass"]:
        verdict, key = "FAIL", "S2 or S5 fails"
    elif not s3["pass"] or not s4["pass"]:
        verdict, key = "NOT SHOWN", "S3 or S4 fails"
    elif not s6["pass"]:
        verdict, key = "NOT READY", "S6 fails alone"
    else:
        verdict, key = "PASS", "ALL pass"
    if not s1_fail and not s1:
        verdict = "INCOMPLETE (S1 not established: identity wave incomplete) - would be %s" % verdict
    elif stopped and verdict != "FAIL":
        verdict = ("INCOMPLETE (%s STOPPED: an R-B tooling check failed, A2 22.2) - the outcome is undetermined until "
                   "the analyzer or instrument is fixed" % ", ".join(stopped))
    elif s2 == "PENDING" and verdict != "FAIL":
        verdict = "INCOMPLETE (%s not run / missing) - would be %s" % (", ".join(pend), verdict)
    if incomplete:
        verdict = ("PROVISIONAL (incomplete data, --allow-incomplete) - %s" % verdict if opts.allow_incomplete
                   else "INCOMPLETE (%d missing, %d invalid runs - re-run them)" % (len(st["missing"]),
                                                                                    len(st["invalid"])))
    if opts.smoke:
        verdict = "SMOKE - NOT A SCREEN (computed: %s)" % verdict
    out("")
    out("VERDICT: %s" % verdict)
    if verdict.startswith("INCOMPLETE (") and "would be" not in verdict:
        out("  section 15: no outcome - the rule is applied only to the complete, valid screen")
    elif "would be" in verdict or verdict.startswith(("PROVISIONAL", "SMOKE")):
        out("  section 15 (NOT yet the outcome): %s" % bullet(bullets, key))
    else:
        out("  section 15: %s" % bullet(bullets, key))
    if M.get("scenario_stop"):
        out("PER-SCENARIO STOP: %s - %s" % (M["scenario_stop"], bullet(bullets, "Any scenario whose")))
    else:
        out("per-scenario STOP: no scenario's pooled rescued falls by 2 or more")
    return verdict


# ================================================================================================ main
def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--out")
    ap.add_argument("--smoke")
    ap.add_argument("--smoke-cell", default="set2/ring/D_N")
    ap.add_argument("--suite-log")
    ap.add_argument("--allow-incomplete", action="store_true")
    ap.add_argument("--gate-ref", default="dpGR")
    ap.add_argument("--head-b")
    ap.add_argument("--head-dp")
    ap.add_argument("--smoke-gate")
    opts = ap.parse_args(_ARGV[1:])
    opts.gate_tags = (opts.gate_ref, "dpG0", "dpG1")
    if not opts.smoke and not (opts.head_b and opts.head_dp):
        ap.error("--head-b <B commit> and --head-dp <dispatch commit> are required outside --smoke (14.5: every "
                 "run's recorded head must be exactly its arm's)")
    if opts.smoke_gate:
        if not opts.smoke:
            ap.error("--smoke-gate needs --smoke")
        opts.gate_tags = (opts.smoke_gate,) * 3
    rc = 0
    try:
        sec15 = sec_header(opts)
        if sec15 is None:
            return 2
        frozen = load_seeds()
        if frozen is None:
            return 2
        cells = screen_cells(frozen, bool(opts.smoke), opts.smoke_cell)
        recs = process(cells, opts)
        st = sec_prov(recs, opts)
        if any("SEED MISMATCH" in w for _a, _c, why in st["invalid"] for w in why):
            out("STOP: a run's scenario / wind / seed differs from the frozen cell (seed-selector rule)")
            return 2
        ident = sec_ident(recs, opts)
        if ident["probe_same"] < ident["probe_compared"] or ident["shards"] is False:
            head("6 DECISION RULE (section 15)")
            out("VERDICT: STOP (S1 IDENTITY FAILED) - %s" % bullet(outcome_bullets(sec15), "S1 fails"))
            return 1
        G = sec_gates(recs, opts, st)
        cells_p = pairs(recs)
        G["_v"] = {k: sum(r["d1"]["num"].get(k, 0) for r in cells_p) for k in ("gb_b", "gb_c", "gb_f_allowed", "gt_a",
                                                                              "gt_c")}
        rb = sec_rbgate(opts)
        gs, ginv = sec_suite(opts)
        s1 = ("PASS" if ident["probe"] and (ident["shards"] is True or (opts.smoke and ident["shards"] is None))
              else "not established")
        M = sec_measures(recs, opts, s1, bool(G.get("_rb_fail")))
        smoke_pair = None
        if opts.smoke:
            smoke_pair = tuple(os.path.join(opts.smoke, SMOKE_FILES[a]) for a in ("dp0", "dp1", "dpR"))
        sec_evidence(opts, smoke_pair)
        sec_decision(sec15, ident, st, G, M, gs, ginv, rb, opts)
    finally:
        if opts.out:
            with open(opts.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(_LINES) + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
