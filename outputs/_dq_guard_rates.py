"""Dispatch round 2, Part 2 item (6): THE CHANCE-RATE TABLE (outputs/dispatch2_part1.txt 13 (6), 15; method
outputs/urgency_part1d.txt 1d.3.2). THIS DECIDES NOTHING. Committed before W1.

WHAT IT MEASURES. The chance rates of THIS round's guards (dispatch2_part1.txt 10.4 / 10.5, rulings 19):
  F1  firefighter deaths, the movement round's reading R2 (urgency_part1d.txt 1d.3.3): FAIL iff the pooled count rises
      OR, in either set, the one-sided exact paired sign test of the set's per-cell deltas gives p <= 0.05;
  L2  rescued, literal: FAIL iff rescued falls in either set;
  L3  detected-victim deaths (DD), literal: FAIL iff pooled DD rises (the carried guard, accepted as written);
  S3  the primary: pooled DD falls, DD does not rise in either set, and the pooled fall survives removing the single
      cell with the most negative delta.
  "literal core" = F1 + L2 + L3; "chance PASS" = S3 and none of F1 / L2 / L3 (before the 28 sign-tested counts, the
  structural zeros, L4 and S6, which can only lower it). R0 (pooled AND per-set literal) is printed beside F1 as 10.5
  reports it: never gating.

DATA. TABLE 1: round 1's per-cell deltas dp1 - dp0 (outputs/_sd_dp{0,1}{r,u,r2,u2}_<S>_<W>.json + .stdout.txt; seed
sets 1-2, 64 cells; in-sample; round 1 ran BEFORE the movement fixes, with round 1's uncorrected J). Per cell:
(eval.firefighter_deaths, eval.rescued, DD) of dp1 minus dp0, where DD = victims with a '[Victim Detection]' line in the
run's .stdout.txt whose rows_vic managed status (column 4) becomes 'dead' at any recorded step (<= 360).
TABLE 2: the movement screen's G arm (outputs/_sd_mvg1{r,u}{5,6}_<S>_<W>.json + .stdout.txt; seed sets 5-6; today's
dispatch on the shipped guarded movement): a DESCRIPTION of today's arm's death density, beside round 1's dp0 / dp1;
then the same guards on round 1's deltas with the firefighter-death column THINNED to today's density (a stated
model, see 2b), and the exact reach of F1 for m unit deltas (2c).

MODELS (as 1d.3.2; the drivers below replicate _mvg_guard_rates.py's random-stream use draw for draw, and the
self-test reproduces 1d.3.2's published table from its own data):
  NULL, one sign per CELL: each cell's three deltas multiplied by one random sign (their correlation kept); F1 also
      EXACTLY (every sign pattern of the non-zero firefighter-death cells).
  NULL, one sign per SEED: the ring and uniform cells of a seed share the fire under CRN, so one random sign per seed
      multiplies both of its cells; F1 also exactly.
  ALTERNATIVE "a change like round 1's J": the observed per-cell deltas taken as the truth; 32 cells per set (cell
      bootstrap) or 16 seeds per set with both of their cells (seed bootstrap) resampled with replacement.
The F1 / L2 / L3 / S3 functions are _mvg_guard_rates.py's own (imported by path, LF sha256 pinned below): sign_p,
readings (its 'R2' is F1, its 'R0' the literal reading), core (L2, L3) and s3_pass (S3).

usage: _dq_guard_rates.py [--draws N] [--seed S] [--out PATH] [--selftest-ud PATH --selftest-published PATH]
  --draws               Monte Carlo draws per section (default 20000)
  --seed                base seed (default 20261008); stream k of the report uses numpy default_rng(seed + k)
  --out                 the report (default outputs/_dq_guard_rates.txt; written UTF-8 with LF line ends)
  --selftest-ud         the movement round's per-cell table (urgency worktree outputs/_ud_deaths.json): reproduces
                        1d.3.2 - _mvg_guard_rates.main on that file must print the published text exactly, and this
                        tool's drivers must equal _mvg_guard_rates.run and the published E1 / E2 / E3 numbers
  --selftest-published  the published output (urgency worktree outputs/_ud_replay/_mvg_guard_rates.txt)
exit: 0 report written; 1 a self-test failed (report written, marked); 2 STOP (an input, anchor or pin mismatch;
nothing written).
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import datetime
import hashlib
import importlib.util
import io
import itertools
import json
import math
import os
import platform
import re
import subprocess
import sys
from fractions import Fraction

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MG_FILE = os.path.join(HERE, "_mvg_guard_rates.py")
MG_SHA_LF = "192eab388bd60773fb61a1a95fd782d1e26eeb35802685507010ba229df90b70"   # = main's copy (raw f90439c6...)
SEED_FILE = os.path.join(HERE, "_dq_seeds.txt")
DEFAULT_OUT = os.path.join(HERE, "_dq_guard_rates.txt")
ALPHA = 0.05
READ = ("R0", "R1", "R2", "R3", "R4", "R5")
CELLS = sorted("%s_%s" % (s, w) for s in "ABCD" for w in "NSEW")          # A_E, A_N, A_S, A_W, B_E, ...
WIND = {"N": "north", "S": "south", "E": "east", "W": "west"}
S_IDX = {"A": 0, "B": 1, "C": 2, "D": 3}
W_IDX = {"N": 0, "S": 1, "E": 2, "W": 3}
PLACEMENTS = (("r", "ring", 0), ("u", "uniform", 1))
DET_RE = re.compile(r"^\[Victim Detection\] step=(\d+) UAV-(\S+) detected (\S+) at")   # _mf2_p3_analyze.DET_RE
# Stream offsets (default_rng(seed + k)).
K_T1 = {"null_cell": 0, "null_seed": 1, "alt_cell": 2, "alt_seed": 3}
K_T2 = {"null_cell": 4, "null_seed": 5, "alt_cell": 6, "alt_seed": 7}
K_SELF = 99

# ANCHORS - committed numbers the loaded records must reproduce (STOP on any mismatch).
#   round 1: outputs/dispatch_report.txt 5.3 (M2: rescued, dead, ff deaths per set), 5.9 (DD: dp0 5 / 8; dp1 "4 / 5
#   and 8 / 8"), the result page ("32 of the 64 cells are identical in dp0 and dp1"); outputs/dispatch2_part1.txt 14
#   ("round 1 changed firefighter deaths in 11 of 64 cells") and 15 ("J left DD unchanged (13 -> 13)").
#   G arm: outputs/mvg_report.txt "THE NUMBERS" (DD 13 (10 + 3), rescued 226 (109 + 117), ff deaths 7 (3 + 4)).
ANCHOR_R1 = {
    ("dp0", "rescued"): {"set1": 109, "set2": 107}, ("dp1", "rescued"): {"set1": 108, "set2": 110},
    ("dp0", "dead"): {"set1": 19, "set2": 17}, ("dp1", "dead"): {"set1": 19, "set2": 17},
    ("dp0", "ff"): {"set1": 11, "set2": 15}, ("dp1", "ff"): {"set1": 11, "set2": 9},
    ("dp0", "DD"): {"set1": 5, "set2": 8}, ("dp1", "DD"): {"set1": 5, "set2": 8},
}
ANCHOR_R1_IDENTICAL = 32
ANCHOR_R1_FF_CHANGED = 11
ANCHOR_G = {"DD": {"set5": 10, "set6": 3}, "rescued": {"set5": 109, "set6": 117}, "ff": {"set5": 3, "set6": 4}}


class Stop(Exception):
    pass


# ------------------------------------------------------------------------------------------------ the imported method
def lf_sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def load_mg():
    got = lf_sha(MG_FILE)
    if got != MG_SHA_LF:
        raise Stop("outputs/_mvg_guard_rates.py LF sha256 %s != pinned %s" % (got, MG_SHA_LF))
    spec = importlib.util.spec_from_file_location("_mvg_guard_rates_dq", MG_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------------ inputs
def seed_table():
    """outputs/_dq_seeds.txt rows of sets 1, 2, 5, 6, with the rule recomputed (STOP on mismatch)."""
    with open(SEED_FILE, encoding="utf-8") as fh:
        sf = json.load(fh)
    out = {}
    for k in (1, 2, 5, 6):
        name = "set%d" % k
        base = int(sf["bases"][name])
        rows = {r[0]: int(r[3]) for r in sf[name]}
        want = {c: base + 4 * S_IDX[c[0]] + W_IDX[c[2]] for c in CELLS}
        if rows != want:
            raise Stop("%s in _dq_seeds.txt differs from the rule seed = base + 4*s + w" % name)
        for r in sf[name]:
            if r[1] != r[0][0] or r[2] != WIND[r[0][2]]:
                raise Stop("%s row %s: scenario / wind columns differ from the cell key" % (name, r))
        out[name] = want
    return out


def record_path(group, setname, p, cell):
    if group in ("dp0", "dp1"):
        return os.path.join(HERE, "_sd_%s%s%s_%s.json" % (group, p, "" if setname == "set1" else "2", cell))
    return os.path.join(HERE, "_sd_mvg1%s%s_%s.json" % (p, setname[-1], cell))


def read_run(group, setname, p, mode, cell, seed, digest):
    """Counts of one run (the record is dropped after reading). Validity per 13 (6)'s scope: complete, not crashed,
    360 steps done, CRN on with draws, the cell's seed / scenario / wind / placement, the arm's switches; else STOP."""
    path = record_path(group, setname, p, cell)
    stdout = path[:-5] + ".stdout.txt"
    bad = []
    for f in (path, stdout):
        if not os.path.isfile(f):
            raise Stop("missing input %s" % f)
    with open(path, "rb") as fh:
        raw = fh.read()
    digest.append((os.path.basename(path), hashlib.sha256(raw).hexdigest()))
    d = json.loads(raw.decode("utf-8"))
    raw = None
    with open(stdout, "rb") as fh:
        sraw = fh.read()
    digest.append((os.path.basename(stdout), hashlib.sha256(sraw).hexdigest()))
    det = {}
    for line in sraw.decode("utf-8", errors="replace").splitlines():
        m = DET_RE.match(line.strip())
        if m and m.group(3) not in det:
            det[m.group(3)] = int(m.group(1))
    sraw = None
    if d.get("complete") is not True:
        bad.append("complete != True")
    if d.get("crashed"):
        bad.append("crashed")
    if d.get("steps_done") != 360:
        bad.append("steps_done %r" % d.get("steps_done"))
    crn = (d.get("fb3") or {}).get("crn") or {}
    if crn.get("on") is not True or not int(crn.get("crn_draws") or 0) > 0:
        bad.append("CRN not on with draws (%r)" % crn)
    if int(d.get("seed")) != seed or d.get("scenario") != cell[0] or d.get("wind") != WIND[cell[2]]:
        bad.append("seed / scenario / wind %r %r %r" % (d.get("seed"), d.get("scenario"), d.get("wind")))
    if int((d.get("params") or {}).get("VICTIM_SPAWN_MODE", -1)) != mode:
        bad.append("VICTIM_SPAWN_MODE")
    sw = (d.get("dp") or {}).get("switches") or {}
    if group in ("dp0", "dp1"):
        want = "0" if group == "dp0" else "1"
        if str(sw.get("DISPATCH_JOINT")) != want or str(sw.get("DISPATCH_REASSIGN")) != want:
            bad.append("dispatch switches %r" % sw)
    else:
        if sw.get("joint_on") is not False or sw.get("reassign_on") is not False:
            bad.append("dispatch not off in G %r" % sw)
        ms = (d.get("mvg") or {}).get("switches") or {}
        if not all(ms.get(k) is True for k in ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH",
                                                 "FF_FIX_STRANDING_GUARD")):
            bad.append("movement switches not all on %r" % ms)
    if bad:
        raise Stop("%s: %s" % (os.path.basename(path), "; ".join(bad)))
    ev = d["eval"]
    vdead = set()
    for row in d["rows_vic"]:
        for r in row:
            if r[4] == "dead":
                vdead.add(r[0])
    dd = sorted(v for v in vdead if v in det)
    out = {"ff": int(ev["firefighter_deaths"]), "rescued": int(ev["rescued"]), "DD": len(dd),
           "dead": int(ev["dead"]), "victims": int(ev["total_victims"]), "never_detected": int(ev["never_detected"]),
           "seed": seed, "cell": cell, "placement": p}
    if group in ("dp0", "dp1"):
        cmd_seq = [(c[0], c[2], c[3], c[4], bool(c[6])) for c in (d.get("dp") or {}).get("commands") or []
                   if c[2] in ("assign", "unassign")]
        blob = json.dumps([d["rows_uav"], d["rows_ff"], d["rows_vic"], ev, cmd_seq], sort_keys=True, default=str)
        out["fp"] = hashlib.sha256(blob.encode()).hexdigest()
    return out


def load_all():
    seeds = seed_table()
    digest = []
    runs = {}
    for group, sets in (("dp0", ("set1", "set2")), ("dp1", ("set1", "set2")), ("G", ("set5", "set6"))):
        for s in sets:
            for p, _pl, mode in PLACEMENTS:
                for c in CELLS:
                    runs[(group, s, p, c)] = read_run(group, s, p, mode, c, seeds[s][c], digest)
    h = hashlib.sha256("".join("%s %s\n" % x for x in sorted(digest)).encode()).hexdigest()
    return runs, seeds, len(digest), h


def r1_deltas(runs):
    """{set: rows} in a fixed order (ring cells A_E..D_W, then uniform), each row: seed, placement, cell, (ff, resc,
    DD) of dp1 - dp0, diverged (per-step rows, eval or the (step, action, victim, unit, ok) command sequence)."""
    out = {}
    for s in ("set1", "set2"):
        rows = []
        for p, _pl, _m in PLACEMENTS:
            for c in CELLS:
                a, b = runs[("dp0", s, p, c)], runs[("dp1", s, p, c)]
                rows.append({"seed": a["seed"], "placement": p, "cell": c,
                             "d": (b["ff"] - a["ff"], b["rescued"] - a["rescued"], b["DD"] - a["DD"]),
                             "div": a["fp"] != b["fp"]})
        out[s] = rows
    return out


def arrays(rows_by_set):
    C = {s: np.array([r["d"] for r in rows], dtype=np.int64) for s, rows in rows_by_set.items()}
    seeds = {s: [r["seed"] for r in rows] for s, rows in rows_by_set.items()}
    return C, seeds


# ------------------------------------------------------------------------------------------------ anchors
def check_anchors(runs, r1):
    bad = []
    for (group, key), want in ANCHOR_R1.items():
        for s, v in want.items():
            got = sum(runs[(group, s, p, c)][key] for p, _x, _m in PLACEMENTS for c in CELLS)
            if got != v:
                bad.append("%s %s %s: %d != %d" % (group, s, key, got, v))
    ident = sum(not r["div"] for s in r1 for r in r1[s])
    if ident != ANCHOR_R1_IDENTICAL:
        bad.append("round 1 identical cells %d != %d" % (ident, ANCHOR_R1_IDENTICAL))
    ffc = sum(r["d"][0] != 0 for s in r1 for r in r1[s])
    if ffc != ANCHOR_R1_FF_CHANGED:
        bad.append("round 1 cells with a firefighter-death change %d != %d" % (ffc, ANCHOR_R1_FF_CHANGED))
    for key, want in ANCHOR_G.items():
        for s, v in want.items():
            got = sum(runs[("G", s, p, c)][key] for p, _x, _m in PLACEMENTS for c in CELLS)
            if got != v:
                bad.append("G %s %s: %d != %d" % (s, key, got, v))
    if bad:
        raise Stop("ANCHOR mismatch: " + "; ".join(bad))
    return ("round 1 rescued / dead / ff deaths / DD per set and arm (dispatch_report 5.3, 5.9), 32 identical cells, "
            "11 cells with a firefighter-death change (dispatch2_part1 14), DD 13 -> 13 (15); G: DD 10 + 3, "
            "rescued 109 + 117, ff deaths 3 + 4 (mvg_report)")


# ------------------------------------------------------------------------------------------------ the drivers
def thin_rows(D, rho, rng):
    """THINNING (2b): each non-zero entry of column 0 (firefighter deaths) / column 2 (DD) is kept with probability
    rho_ff / rho_dd, else set to 0; a rho >= 1 draws nothing and changes nothing."""
    D = D.copy()
    for col, r in ((0, rho[0]), (2, rho[1])):
        if r < 1.0:
            drop = rng.random(D.shape[0]) >= r
            D[drop & (D[:, col] != 0), col] = 0
    return D


def simulate(MG, kind, C, seeds, draws, rng, thin=None):
    """Shares of draws in which each guard fails / the comparison passes. kind: null_cell / alt_cell (as
    _mvg_guard_rates.run), null_seed / alt_seed (as its E2); the random calls are made in the same order, so with
    thin=None the stream is the movement tool's draw for draw. Returns {key: share}."""
    names = list(C)
    tal = collections.Counter()
    cache = {}
    uniq = {s: sorted(set(seeds[s])) for s in names}
    rows_of = {s: {x: [j for j, y in enumerate(seeds[s]) if y == x] for x in uniq[s]} for s in names}
    for _ in range(draws):
        base = C if thin is None else {s: thin_rows(C[s], thin, rng) for s in names}
        d = {}
        for s in names:
            D = base[s]
            if kind == "null_cell":
                d[s] = D * rng.choice((-1, 1), size=(D.shape[0], 1))
            elif kind == "alt_cell":
                d[s] = D[rng.integers(0, D.shape[0], D.shape[0])]
            elif kind == "null_seed":
                sign = dict(zip(uniq[s], rng.choice((-1, 1), size=len(uniq[s]))))
                d[s] = D * np.array([[sign[x]] for x in seeds[s]])
            elif kind == "alt_seed":
                pick = rng.integers(0, len(uniq[s]), len(uniq[s]))
                idx = [j for i in pick for j in rows_of[s][uniq[s][i]]]
                d[s] = D[idx]
            else:
                raise ValueError(kind)
        a, b = d[names[0]], d[names[1]]
        r = MG.readings(a[:, 0], b[:, 0], rng, cache)
        l2, l3 = MG.core(a, b)
        s3 = bool(MG.s3_pass(a, b))
        tal["L2"] += bool(l2)
        tal["L3"] += bool(l3)
        tal["S3"] += s3
        for n in READ:
            core = bool(r[n]) or bool(l2) or bool(l3)
            tal["F1_" + n] += bool(r[n])
            tal["core_" + n] += core
            tal["pass_" + n] += s3 and not core
    return {k: v / draws for k, v in tal.items()}


def exact_f1(MG, ffA, seedsA, ffB, seedsB, unit, rho=1.0):
    """EXACT chance FAIL of each F1 reading: every sign pattern (one sign per cell, unit='cell', or per seed,
    unit='seed') of the non-zero firefighter-death cells; with rho < 1 every kept-subset of those cells, weighted
    rho^k (1 - rho)^(n - k) (the thinning of 2b). Returns ({reading: probability}, patterns enumerated)."""
    rng = np.random.default_rng(0)     # never drawn from: at most 11 non-zero cells (perm_p is exact up to 14)
    cache = {}
    nzA = [(int(v), sd) for v, sd in zip(ffA, seedsA) if v != 0]
    nzB = [(int(v), sd) for v, sd in zip(ffB, seedsB) if v != 0]
    cells_all = [("A", v, sd) for v, sd in nzA] + [("B", v, sd) for v, sd in nzB]
    n = len(cells_all)
    tot = {k: Fraction(0) for k in READ}
    patterns = 0
    rho_f = Fraction(rho).limit_denominator(10 ** 9)
    for keep in itertools.product((1, 0), repeat=n) if rho < 1.0 else [(1,) * n]:
        k = sum(keep)
        w = rho_f ** k * (1 - rho_f) ** (n - k) if rho < 1.0 else Fraction(1)
        kept = [c for c, x in zip(cells_all, keep) if x]
        units = sorted(set(i for i in range(len(kept)))) if unit == "cell" else sorted(set(c[2] for c in kept))
        sub = {k2: 0 for k2 in READ}
        cnt = 0
        for signs in itertools.product((-1, 1), repeat=len(units)):
            sg = dict(zip(units, signs))
            a = [c[1] * sg[i if unit == "cell" else c[2]] for i, c in enumerate(kept) if c[0] == "A"]
            b = [c[1] * sg[i if unit == "cell" else c[2]] for i, c in enumerate(kept) if c[0] == "B"]
            r = MG.readings(np.array(a, dtype=np.int64), np.array(b, dtype=np.int64), rng, cache)
            for k2 in READ:
                sub[k2] += bool(r[k2])
            cnt += 1
        patterns += cnt
        for k2 in READ:
            tot[k2] += w * Fraction(sub[k2], cnt)
    return {k2: float(v) for k2, v in tot.items()}, patterns


def m_table(MG, ms=range(1, 13)):
    """2c: m unit firefighter-death deltas, ceil(m/2) in one set and floor(m/2) in the other, every sign pattern:
    exact chance FAIL of F1 (R2) and of the pooled literal alone (R1); R1 must equal (1 - P(tie)) / 2."""
    rng = np.random.default_rng(0)
    out = []
    for m in ms:
        ma, mb = (m + 1) // 2, m // 2
        f1 = r1 = 0
        cache = {}
        for signs in itertools.product((-1, 1), repeat=m):
            r = MG.readings(np.array(signs[:ma], dtype=np.int64), np.array(signs[ma:], dtype=np.int64), rng, cache)
            f1 += bool(r["R2"])
            r1 += bool(r["R1"])
        p_tie = math.comb(m, m // 2) / 2 ** m if m % 2 == 0 else 0.0
        out.append((m, ma, mb, f1 / 2 ** m, r1 / 2 ** m, (1 - p_tie) / 2))
    return out


def s3_table(MG, ks=range(1, 13)):
    """2d: k unit DD deltas (and nothing else), ceil(k/2) in one set and floor(k/2) in the other, every sign pattern:
    exact chance PASS of S3 (which implies L3) and chance FAIL of L3."""
    out = []
    for k in ks:
        ka, kb = (k + 1) // 2, k // 2
        s3 = l3 = 0
        for signs in itertools.product((-1, 1), repeat=k):
            a = np.zeros((ka, 3), dtype=np.int64)
            b = np.zeros((kb, 3), dtype=np.int64)
            a[:, 2] = signs[:ka]
            b[:, 2] = signs[ka:]
            s3 += bool(MG.s3_pass(a, b))
            l3 += bool(MG.core(a, b)[1])
        out.append((k, ka, kb, s3 / 2 ** k, l3 / 2 ** k))
    return out


# ------------------------------------------------------------------------------------------------ in-run self-tests
def spec_f1(ffA, ffB):
    """F1 read from dispatch2_part1.txt 10.5 directly (exact fractions), for the equivalence check."""
    if int(ffA.sum()) + int(ffB.sum()) > 0:
        return True
    for ff in (ffA, ffB):
        npl, nmi = int((ff > 0).sum()), int((ff < 0).sum())
        n = npl + nmi
        if n and Fraction(sum(math.comb(n, k) for k in range(npl, n + 1)), 2 ** n) <= Fraction(1, 20):
            return True
    return False


def spec_s3(a, b):
    """S3 read from 10.4 directly."""
    dd = [int(x) for x in a[:, 2]] + [int(x) for x in b[:, 2]]
    pooled = sum(dd)
    if not pooled < 0 or int(a[:, 2].sum()) > 0 or int(b[:, 2].sum()) > 0:
        return False
    return pooled - min(dd) < 0


def spec_core(a, b):
    return int(a[:, 1].sum()) < 0 or int(b[:, 1].sum()) < 0, int(a[:, 2].sum()) + int(b[:, 2].sum()) > 0


def run_inrun_selftests(MG, C, seeds, r1, mtab, ex, mc, seed, draws):
    """Checks that need no outside file. Returns [(name, ok, detail)]."""
    res = []
    rng = np.random.default_rng(seed + K_SELF)
    cache = {}
    bad_f1 = bad_s3 = bad_core = 0
    vals = (-2, -1, 0, 0, 0, 0, 0, 0, 1, 2)
    for _ in range(10000):
        a = rng.choice(vals, size=(int(rng.integers(1, 17)), 3))
        b = rng.choice(vals, size=(int(rng.integers(1, 17)), 3))
        r = MG.readings(a[:, 0], b[:, 0], np.random.default_rng(1), cache)
        bad_f1 += bool(r["R2"]) != spec_f1(a[:, 0], b[:, 0])
        bad_s3 += bool(MG.s3_pass(a, b)) != spec_s3(a, b)
        bad_core += tuple(bool(x) for x in MG.core(a, b)) != spec_core(a, b)
    res.append(("F1 = 10.5 read directly (readings 'R2' vs an exact-fraction sign test), 10 000 random tables",
                bad_f1 == 0, "%d mismatches" % bad_f1))
    res.append(("S3 = 10.4 read directly (s3_pass), 10 000 random tables", bad_s3 == 0, "%d mismatches" % bad_s3))
    res.append(("L2 / L3 = 10.5 read directly (core), 10 000 random tables", bad_core == 0,
                "%d mismatches" % bad_core))
    worst = max(abs(t[4] - t[5]) for t in mtab)
    res.append(("2c: the pooled literal's exact enumeration equals (1 - P(tie)) / 2 for m = 1..12", worst < 1e-12,
                "max |difference| %.2e" % worst))
    for unit in ("cell", "seed"):
        e = ex[("T1", unit)][0]["R2"]
        m = mc[("T1", "null_" + unit)]["F1_R2"]
        se = math.sqrt(max(e * (1 - e), 1e-9) / draws)
        res.append(("table 1 F1 (R2), %s null: Monte Carlo within 4 SE of the exact value" % unit,
                    abs(m - e) <= 4 * se + 1e-12, "exact %.4f MC %.4f (SE %.4f)" % (e, m, se)))
        e2 = ex[("T2", unit)][0]["R2"]
        m2 = mc[("T2", "null_" + unit)]["F1_R2"]
        se2 = math.sqrt(max(e2 * (1 - e2), 1e-9) / draws)
        res.append(("table 2b F1 (R2), %s null, thinned: Monte Carlo within 4 SE of the exact value" % unit,
                    abs(m2 - e2) <= 4 * se2 + 1e-12, "exact %.4f MC %.4f (SE %.4f)" % (e2, m2, se2)))
    one = exact_f1(MG, C["set1"][:, 0], seeds["set1"], C["set2"][:, 0], seeds["set2"], "cell", rho=0.9999999)[0]
    res.append(("thinning at rho -> 1 converges to the unthinned exact F1 (cell null)",
                all(abs(one[k] - ex[("T1", "cell")][0][k]) < 1e-5 for k in READ),
                "R2 %.6f vs %.6f" % (one["R2"], ex[("T1", "cell")][0]["R2"])))
    # Constructed cases with known answers: one seed whose ring and uniform cells both rose by 1 (set A), nothing in
    # set B. Cell null: the pooled count rises only on (+, +): 1/4. Seed null: one sign moves both: 1/2. A single +1
    # cell thinned at rho 1/2: kept and rising, 1/4.
    a2, s2 = np.array([1, 1], dtype=np.int64), [7, 7]
    e0 = np.array([], dtype=np.int64)
    got = (exact_f1(MG, a2, s2, e0, [], "cell")[0]["R1"], exact_f1(MG, a2, s2, e0, [], "seed")[0]["R1"],
           exact_f1(MG, np.array([1], dtype=np.int64), [7], e0, [], "cell", rho=0.5)[0]["R1"])
    res.append(("exact_f1 on constructed cases: cell null 1/4, seed null 1/2, thinned at rho 1/2 1/4",
                got == (0.25, 0.5, 0.25), "got %s" % (got,)))
    # Thinning statistics: kept non-zero firefighter-death cells average n * rho_ff; DD and rescued columns untouched.
    trng = np.random.default_rng(seed + K_SELF + 1)
    rho = ex["rho"]
    nzc = int(sum((C[s][:, 0] != 0).sum() for s in C))
    kept, untouched = [], True
    for _ in range(draws):
        t = {s: thin_rows(C[s], rho, trng) for s in C}
        kept.append(sum(int((t[s][:, 0] != 0).sum()) for s in t))
        untouched &= all(np.array_equal(t[s][:, 1:], C[s][:, 1:]) for s in t) if rho[1] >= 1.0 else True
    mean = float(np.mean(kept))
    se = math.sqrt(nzc * rho[0] * (1 - rho[0]) / draws)
    res.append(("thin_rows keeps n * rho_ff non-zero ff cells on average (within 4 SE) and leaves rescued / DD as is",
                abs(mean - nzc * rho[0]) <= 4 * se and untouched,
                "mean %.4f vs %.4f (SE %.4f); other columns untouched %s" % (mean, nzc * rho[0], se, untouched)))
    pairs_ok = all(sorted(collections.Counter(seeds[s]).values()) == [2] * 16 for s in seeds)
    res.append(("every seed has exactly its ring and its uniform cell in each set (the seed null's unit)", pairs_ok,
                "16 seeds x 2 cells per set"))
    undiv = [(s, r["placement"], r["cell"]) for s in r1 for r in r1[s] if any(r["d"]) and not r["div"]]
    res.append(("every cell with a non-zero delta is DIVERGED (10.6's assertion)", not undiv, "%s" % (undiv or "none")))
    return res


# ------------------------------------------------------------------------------------------------ --selftest-ud
def ud_tables(path):
    """_mvg_guard_rates.cells / cells_with_seed, re-read from an explicit path (same order)."""
    with open(path, encoding="utf-8") as fh:
        table = json.load(fh)
    rows = {"set3": [], "set4": []}
    for e in table:
        s = e["cell"].split("/")[0]
        a0, am = e["arms"]["0"], e["arms"]["M"]
        rows[s].append({"seed": int(e["seed"]), "d": (len(am["ff"]) - len(a0["ff"]),
                                                       int(am["rescued"]) - int(a0["rescued"]),
                                                       len(am["DD"]) - len(a0["DD"]))})
    return rows


def parse_published(text):
    t = text.replace("\r\n", "\n")
    out = {}
    i_null, i_alt, i_e1 = t.index("\nNULL - no true effect"), t.index("\nALTERNATIVE - arm M"), t.index("\nE1 EXACT")
    for name, blk in (("null", t[i_null:i_alt]), ("alt", t[i_alt:i_e1])):
        m = re.search(r"L2 rescued >= in each set fails: (\d\.\d{3})\s+L3 DD pooled rises: (\d\.\d{3})", blk)
        out[(name, "L2")], out[(name, "L3")] = m.group(1), m.group(2)
        for line in blk.split("\n"):
            m = re.match(r"^\s+(R[0-5])\s.*?(\d\.\d{3})\s+(\d\.\d{3})\s*$", line)
            if m:
                out[(name, m.group(1), "F1")], out[(name, m.group(1), "core")] = m.group(2), m.group(3)
    m = re.search(r"R0 (\d\.\d{4}) \| R1 (\d\.\d{4}) \| R2 (\d\.\d{4}) \| R3 (\d\.\d{4}) \| R4 (\d\.\d{4}) \| "
                  r"R5 (\d\.\d{4})\s+\((\d+) patterns\)", t)
    for i, k in enumerate(READ):
        out[("E1", k)] = m.group(i + 1)
    out[("E1", "patterns")] = m.group(7)
    i_n, i_a, i_e3 = t.index("NULL, one sign per SEED"), t.index("ALT, seeds resampled"), t.index("\nE3 CELL-LEVEL")
    for name, blk in (("E2null", t[i_n:i_a]), ("E2alt", t[i_a:i_e3])):
        for line in blk.split("\n"):
            m = re.match(r"^\s+(R[0-5])\s+(\d\.\d{3}) \| (\d\.\d{3}) \| (\d\.\d{3})\s*$", line)
            if m:
                out[(name, m.group(1), "F1")] = m.group(2)
                out[(name, m.group(1), "core")] = m.group(3)
                out[(name, m.group(1), "pass")] = m.group(4)
        out[(name, "S3")] = re.search(r"S3 alone passes: (\d\.\d{3})", blk).group(1)
    m = re.search(r"S3 alone (\d\.\d{3}) \| R0 (\d\.\d{3}) \| R1 (\d\.\d{3}) \| R2 (\d\.\d{3}) \| R3 (\d\.\d{3}) \| "
                  r"R4 (\d\.\d{3}) \| R5 (\d\.\d{3})", t[i_e3:])
    out[("E3", "S3")] = m.group(1)
    for i, k in enumerate(READ):
        out[("E3", k)] = m.group(i + 2)
    return out


def run_ud_selftests(MG, ud_path, pub_path, draws):
    """1d.3.2 reproduced: (i) _mvg_guard_rates.main on its own data prints the published text exactly; (ii) this
    tool's drivers equal _mvg_guard_rates.run value for value; (iii) its drivers and exact F1 print the published E1 /
    E2 / E3 numbers. Uses the movement round's seeds (20261007; extended 20261008) and 20 000 draws."""
    res = []
    if draws != 20000:
        return [("--selftest-ud needs --draws 20000 (the published table's)", False, "draws %d" % draws)]
    with open(pub_path, "rb") as fh:
        pub = fh.read().decode("utf-8").replace("\r\n", "\n")
    # (i) the movement tool itself, on its data (its HERE pointed at the file's directory; argv as published).
    old_here, old_argv = MG.HERE, sys.argv
    try:
        MG.HERE = os.path.dirname(os.path.abspath(ud_path))
        sys.argv = [MG_FILE, "--draws", "20000", "--seed", "20261007"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            MG.main()
    finally:
        MG.HERE, sys.argv = old_here, old_argv
    got = buf.getvalue()
    same = got.rstrip("\n") == pub.rstrip("\n")
    res.append(("_mvg_guard_rates.main on %s prints the published %s exactly" % (
        os.path.basename(ud_path), os.path.basename(pub_path)), same,
        "identical (%d lines)" % got.count("\n") if same else "DIFFERS"))
    rows = ud_tables(ud_path)
    C, seeds = arrays(rows)
    data = {"set3": C["set3"], "set4": C["set4"]}
    P = parse_published(pub)
    # (ii) drivers == MG.run, value for value.
    for kind, mk in (("null", "null_cell"), ("alt", "alt_cell")):
        f, fc, l2, l3 = MG.run(kind, data, 20000, np.random.default_rng(20261007))
        mine = simulate(MG, mk, C, seeds, 20000, np.random.default_rng(20261007))
        eq = all(f[n] == mine["F1_" + n] and fc[n] == mine["core_" + n] for n in READ) and \
            l2 == mine["L2"] and l3 == mine["L3"]
        res.append(("driver %s == _mvg_guard_rates.run('%s') for R0-R5, L2, L3 (exact equality)" % (mk, kind), eq,
                    "equal" if eq else "DIFFERS"))
        pub_ok = all("%.3f" % mine["F1_" + n] == P[(kind, n, "F1")] and "%.3f" % mine["core_" + n] == P[(kind, n,
                     "core")] for n in READ) and "%.3f" % mine["L2"] == P[(kind, "L2")] and \
            "%.3f" % mine["L3"] == P[(kind, "L3")]
        res.append(("driver %s prints the published %s table (R0-R5 F1 / core, L2, L3)" % (mk, kind.upper()), pub_ok,
                    "R2 %.3f / %.3f" % (mine["F1_R2"], mine["core_R2"])))
    # (iii) E1 exact, E2 seed null / alt, E3 cell-null PASS.
    e1, pats = exact_f1(MG, C["set3"][:, 0], seeds["set3"], C["set4"][:, 0], seeds["set4"], "cell")
    ok = all("%.4f" % e1[k] == P[("E1", k)] for k in READ) and str(pats) == P[("E1", "patterns")]
    res.append(("exact_f1 (cell) prints the published E1 line (R0-R5, 1024 patterns)", ok,
                "R2 %.4f, %d patterns" % (e1["R2"], pats)))
    for kind, name in (("null_seed", "E2null"), ("alt_seed", "E2alt")):
        mine = simulate(MG, kind, C, seeds, 20000, np.random.default_rng(20261008))
        ok = all("%.3f" % mine["F1_" + n] == P[(name, n, "F1")] and "%.3f" % mine["core_" + n] == P[(name, n, "core")]
                 and "%.3f" % mine["pass_" + n] == P[(name, n, "pass")] for n in READ) and \
            "%.3f" % mine["S3"] == P[(name, "S3")]
        res.append(("driver %s prints the published %s rows (R0-R5 F1 / core / PASS, S3 alone)" % (kind, name), ok,
                    "R2 %.3f / %.3f / %.3f, S3 %.3f" % (mine["F1_R2"], mine["core_R2"], mine["pass_R2"],
                                                          mine["S3"])))
    mine = simulate(MG, "null_cell", C, seeds, 20000, np.random.default_rng(20261008))
    ok = "%.3f" % mine["S3"] == P[("E3", "S3")] and all("%.3f" % mine["pass_" + n] == P[("E3", n)] for n in READ)
    res.append(("driver null_cell prints the published E3 line (S3 alone, PASS R0-R5)", ok,
                "S3 %.3f, PASS R2 %.3f" % (mine["S3"], mine["pass_R2"])))
    ex_seed = exact_f1(MG, C["set3"][:, 0], seeds["set3"], C["set4"][:, 0], seeds["set4"], "seed")[0]
    m2 = simulate(MG, "null_seed", C, seeds, 20000, np.random.default_rng(20261008))["F1_R2"]
    se = math.sqrt(ex_seed["R2"] * (1 - ex_seed["R2"]) / 20000)
    res.append(("exact_f1 (seed) agrees with the published seed-null Monte Carlo F1 (R2) within 4 SE",
                abs(ex_seed["R2"] - m2) <= 4 * se, "exact %.4f, MC %.4f" % (ex_seed["R2"], m2)))
    return res


# ------------------------------------------------------------------------------------------------ description (2a)
def density(runs, group, sets):
    """Per set, placement and pooled: counts and per-cell distributions of one arm."""
    out = collections.OrderedDict()
    keys = [(s, p) for s in sets for p in ("r", "u")]
    scopes = [("%s %s" % (s, pl), [(s, p)]) for s in sets for p, pl, _m in PLACEMENTS] + \
        [(s, [(s, "r"), (s, "u")]) for s in sets] + [("pooled", keys)]
    for label, ks in scopes:
        rs = [runs[(group, s, p, c)] for s, p in ks for c in CELLS]
        ffh = collections.Counter(r["ff"] for r in rs)
        ddh = collections.Counter(r["DD"] for r in rs)
        seeds_ff = len(set((s, runs[(group, s, p, c)]["seed"]) for s, p in ks for c in CELLS
                           if runs[(group, s, p, c)]["ff"] > 0))
        out[label] = {"cells": len(rs), "victims": sum(r["victims"] for r in rs),
                      "rescued": sum(r["rescued"] for r in rs), "dead": sum(r["dead"] for r in rs),
                      "DD": sum(r["DD"] for r in rs), "nd": sum(r["never_detected"] for r in rs),
                      "ff": sum(r["ff"] for r in rs), "ff_cells": sum(r["ff"] > 0 for r in rs),
                      "dd_cells": sum(r["DD"] > 0 for r in rs), "ff_seeds": seeds_ff,
                      "ffh": dict(sorted(ffh.items())), "ddh": dict(sorted(ddh.items()))}
    return out


def by_scenario(runs, group, sets):
    out = {}
    for sc in "ABCD":
        rs = [runs[(group, s, p, c)] for s in sets for p in ("r", "u") for c in CELLS if c[0] == sc]
        out[sc] = (sum(r["ff"] for r in rs), sum(r["DD"] for r in rs), sum(r["rescued"] for r in rs),
                   sum(r["victims"] for r in rs))
    return out


# ------------------------------------------------------------------------------------------------ report
def fmt_h(h):
    return " ".join("%d:%d" % kv for kv in h.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20261008)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--selftest-ud", default=None)
    ap.add_argument("--selftest-published", default=None)
    o = ap.parse_args()
    if bool(o.selftest_ud) != bool(o.selftest_published):
        ap.error("--selftest-ud and --selftest-published go together")
    try:
        MG = load_mg()
        runs, seeds_tab, n_files, in_sha = load_all()
        r1 = r1_deltas(runs)
        anchors = check_anchors(runs, r1)
    except Stop as e:
        print("STOP: %s" % e, file=sys.stderr)
        return 2
    C, seeds = arrays(r1)
    D0 = density(runs, "dp0", ("set1", "set2"))
    D1 = density(runs, "dp1", ("set1", "set2"))
    DG = density(runs, "G", ("set5", "set6"))
    ff_r1_mean = (D0["pooled"]["ff"] + D1["pooled"]["ff"]) / 2.0
    dd_r1_mean = (D0["pooled"]["DD"] + D1["pooled"]["DD"]) / 2.0
    rho_ff = DG["pooled"]["ff"] / ff_r1_mean
    rho_dd = DG["pooled"]["DD"] / dd_r1_mean
    thin = (min(rho_ff, 1.0), min(rho_dd, 1.0))

    mc = {}
    for kind, k in K_T1.items():
        mc[("T1", kind)] = simulate(MG, kind, C, seeds, o.draws, np.random.default_rng(o.seed + k))
    for kind, k in K_T2.items():
        mc[("T2", kind)] = simulate(MG, kind, C, seeds, o.draws, np.random.default_rng(o.seed + k), thin=thin)
    ex = {}
    for unit in ("cell", "seed"):
        ex[("T1", unit)] = exact_f1(MG, C["set1"][:, 0], seeds["set1"], C["set2"][:, 0], seeds["set2"], unit)
        ex[("T2", unit)] = exact_f1(MG, C["set1"][:, 0], seeds["set1"], C["set2"][:, 0], seeds["set2"], unit,
                                    rho=thin[0])
    mtab = m_table(MG)
    ex["rho"] = thin
    tests = run_inrun_selftests(MG, C, seeds, r1, mtab, ex, mc, o.seed, o.draws)
    if o.selftest_ud:
        tests += run_ud_selftests(MG, o.selftest_ud, o.selftest_published, o.draws)
    all_ok = all(t[1] for t in tests)
    ffc_r1 = sum(r["d"][0] != 0 for s in r1 for r in r1[s])
    ddc_r1 = sum(r["d"][2] != 0 for s in r1 for r in r1[s])
    rsc_r1 = sum(r["d"][1] != 0 for s in r1 for r in r1[s])

    L = []
    w = L.append
    try:
        head = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=30).stdout.strip() or "?"
    except Exception:   # noqa: BLE001 - provenance only
        head = "?"
    w("_dq_guard_rates.txt - dispatch round 2, Part 2 item (6): THE CHANCE-RATE TABLE (outputs/dispatch2_part1.txt")
    w("13 (6) and 15; the movement round's method, outputs/urgency_part1d.txt 1d.3.2). THIS DECIDES NOTHING.")
    w("generated %s by outputs/_dq_guard_rates.py (sha256 LF %s) at worktree HEAD %s" % (
        datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z"), lf_sha(os.path.abspath(__file__)), head))
    w("python %s, numpy %s; %d draws per Monte Carlo section; base seed %d (streams: table 1 cell null +0, seed null"
      % (platform.python_version(), np.__version__, o.draws, o.seed))
    w("+1, cell bootstrap +2, seed bootstrap +3; table 2b +4..+7; in-run self-test +99)")
    w("method imported from outputs/_mvg_guard_rates.py (LF sha256 %s, pinned; = main's copy): sign_p," % MG_SHA_LF)
    w("readings ('R2' = this round's F1, 'R0' = the literal reading), core (L2, L3), s3_pass (S3)")
    w("inputs: %d files (round 1 dp0 / dp1, sets 1-2: 128 records + their stdout; G arm mvg1, sets 5-6: 64 + 64);" %
      n_files)
    w("combined sha256 %s" % in_sha)
    w("seed file outputs/_dq_seeds.txt: the rule seed = base + 4*s + w recomputed for sets 1, 2, 5, 6 - equal; every")
    w("record's seed / scenario / wind / placement / switches / CRN / 360 steps checked against it")
    w("ANCHORS (the committed numbers, all reproduced): %s" % anchors)
    w("SELF-TEST: %s (%d checks; section 4)" % ("PASS" if all_ok else "FAIL", len(tests)))
    w("")
    w("THE GUARDS AS READ HERE (dispatch2_part1.txt 10.4-10.5, rulings 19; per-cell deltas arm 1 - arm 0)")
    w("  F1 (R2, HARD)   FAIL iff pooled firefighter deaths rise, OR in either set the one-sided exact sign test of the")
    w("                  set's per-cell deltas gives p = P(Bin(n+ + n-, 1/2) >= n+) <= 0.05 (p = 1 if nothing changed)")
    w("  L2 (literal)    FAIL iff rescued falls in either set")
    w("  L3 (literal)    FAIL iff pooled DD rises (the carried guard, accepted as written)")
    w("  S3 (primary)    PASS iff pooled DD falls, DD rises in neither set, and the pooled fall survives removing the")
    w("                  single cell with the most negative DD delta")
    w("  literal core = F1 + L2 + L3.  chance PASS = S3 and none of F1, L2, L3 - before the 28 sign-tested counts, the")
    w("  structural zeros (S2), L4 and S6, each of which can only lower it.  R0 = pooled AND per-set literal")
    w("  (reported beside F1 by 10.5, never gating).  L4 has no chance rate (a mechanistic clause, 11).")
    w("")
    w("CAVEATS (each applies to every number below)")
    w("  - THIS DECIDES NOTHING. It states, before W1, how often the rule fails or passes by chance; no threshold,")
    w("    reading, set or seed of this round is chosen from it.")
    w("  - Table 1 is IN-SAMPLE: sets 1-2 were round 1's screen sets, and the deltas are round 1's J (uncorrected: the")
    w("    fresh-pair key, the immediate LATCH-FILL, fire-free d and e-shift progress) against its dp0.")
    w("  - Round 1 ran BEFORE the movement fixes (records at ea737eb4; FF_APPROACH_PATH / FF_RETREAT_KEEP_APPROACH /")
    w("    FF_FIX_STRANDING_GUARD did not exist). Its arms had 26 / 20 firefighter deaths on 64 cells; today's arm (G,")
    w("    table 2) had 7. Table 1's firefighter-death column therefore over-states today's density; 2b re-states the")
    w("    rates with that column thinned to today's density (a model), 2c gives the exact reach by count.")
    w("  - The cell null treats a set's 32 cells as independent; the seed null keeps the CRN pairing of a seed's ring")
    w("    and uniform cells and models no other dependence. Both keep each cell's observed |delta| (sign-flip), so")
    w("    they describe a no-effect change that moves exactly the cells round 1's J moved. The alternative is the")
    w("    in-sample effect resampled: a description, not a prediction for the corrected dispatcher.")
    w("  - Monte Carlo standard error <= 0.0036 at 20 000 draws (exact columns are exact).")
    w("  - Table 2 reads the G arm's counts only (eval, rows_vic, detection lines) from the movement screen's")
    w("    records (sets 5-6, mvg_probe v1 instrument, worktree mvg at 21b3b857). Section 8 of the pre-registration")
    w("    lists round 1's set 1-2 records as diagnostics; this read of sets 5-6 is the one 13 (6) itself names (and")
    w("    15 already quotes its totals); the seed file's 'never read in this round' role text is descriptive, not")
    w("    enforced. No set 3-4 or 7-8 file is read.")
    w("")

    # ---------------------------------------------------------------- 0 DATA
    w("0 DATA - round 1's per-cell deltas dp1 - dp0 (sets 1-2; 32 cells per set: ring A_E..D_W, then uniform)")
    for s in ("set1", "set2"):
        D = C[s]
        div = sum(r["div"] for r in r1[s])
        w("  %s: diverged %d of 32 | ff deaths: sum %+d, cells up %d down %d, non-zero |values| %s | rescued: sum %+d,"
          " up %d down %d | DD: sum %+d, up %d down %d" % (
              s, div, D[:, 0].sum(), (D[:, 0] > 0).sum(), (D[:, 0] < 0).sum(),
              sorted(np.abs(D[D[:, 0] != 0, 0]).tolist()), D[:, 1].sum(), (D[:, 1] > 0).sum(), (D[:, 1] < 0).sum(),
              D[:, 2].sum(), (D[:, 2] > 0).sum(), (D[:, 2] < 0).sum()))
        per_seed = collections.Counter()
        for r in r1[s]:
            per_seed[r["seed"]] += r["d"][0]
        w("         ff deaths per SEED (ring + uniform), non-zero: %s" % sorted(v for v in per_seed.values() if v))
    w("  non-zero cells (set placement cell seed: ff / rescued / DD):")
    nz = ["%s %s %s %d: %+d / %+d / %+d" % (s[-1], r["placement"], r["cell"], r["seed"], *r["d"])
          for s in ("set1", "set2") for r in r1[s] if any(r["d"])]
    for i in range(0, len(nz), 3):
        w("    " + " | ".join(nz[i:i + 3]))
    w("")

    # ---------------------------------------------------------------- 1 TABLE 1
    w("1 TABLE 1 - THIS ROUND'S GUARDS ON ROUND 1'S DELTAS (sets 1-2, in-sample; %d draws unless 'exact')" % o.draws)
    w("  NO-EFFECT CHANGE (null)       | F1 chance FAIL (R2)        | literal core FAIL | chance PASS of")
    w("                                |                            | (F1 + L2 + L3)    | S3 + F1 + L2 + L3")
    for unit in ("cell", "seed"):
        m = mc[("T1", "null_" + unit)]
        e, pats = ex[("T1", unit)]
        w("  one sign per %-4s             | %.3f exact (MC %.3f)      | %.3f             | %.3f" % (
            unit.upper(), e["R2"], m["F1_R2"], m["core_R2"], m["pass_R2"]))
    for unit in ("cell", "seed"):
        m = mc[("T1", "null_" + unit)]
        e, pats = ex[("T1", unit)]
        w("    %s null components: L2 fails %.3f | L3 fails %.3f | S3 alone passes %.3f | R0 (never gating): F1 %.3f"
          " exact, core %.3f, PASS %.3f | exact over %d patterns" % (
              unit, m["L2"], m["L3"], m["S3"], e["R0"], m["core_R0"], m["pass_R0"], pats))
    w("  A CHANGE LIKE ROUND 1'S J     | P(F1 FAIL)                 | P(core FAIL)      | P(PASS of S3 + literals)")
    for kind, lab in (("alt_cell", "cell bootstrap (32 / set)"), ("alt_seed", "seed bootstrap (16 / set)")):
        m = mc[("T1", kind)]
        w("  %-29s | %.3f                      | %.3f             | %.3f" % (lab, m["F1_R2"], m["core_R2"],
                                                                             m["pass_R2"]))
    for kind in ("alt_cell", "alt_seed"):
        m = mc[("T1", kind)]
        w("    %s components: L2 fails %.3f | L3 fails %.3f | S3 alone passes %.3f | R0 (never gating): F1 %.3f,"
          " core %.3f, PASS %.3f" % (kind, m["L2"], m["L3"], m["S3"], m["F1_R0"], m["core_R0"], m["pass_R0"]))
    m1 = int((C["set1"][:, 0] != 0).sum())
    m2 = int((C["set2"][:, 0] != 0).sum())
    w("  F1's per-set clause (ii) here: set 1 has %d changed cells (smallest p %.4f), set 2 %d (smallest p %.4f); a set"
      % (m1, 2.0 ** -m1 if m1 else 1.0, m2, 2.0 ** -m2 if m2 else 1.0))
    w("  with 4 or fewer can never fail it, 5 only if all 5 rise. Exact, cell null: F1 (R2) %.4f against the pooled" %
      ex[("T1", "cell")][0]["R2"])
    w("  literal alone (R1) %.4f - the per-set clause adds %.4f; seed null %.4f against %.4f." % (
        ex[("T1", "cell")][0]["R1"], ex[("T1", "cell")][0]["R2"] - ex[("T1", "cell")][0]["R1"],
        ex[("T1", "seed")][0]["R2"], ex[("T1", "seed")][0]["R1"]))
    w("  READING: under the cell null F1 fails by chance %.3f (exact); the literal core %.3f; a no-effect change passes"
      % (ex[("T1", "cell")][0]["R2"], mc[("T1", "null_cell")]["core_R2"]))
    w("  S3 + the literals %.3f (cell) / %.3f (seed). The movement round's anchor (1d.3.2, R2): 0.50 / 0.81-0.83 /"
      % (mc[("T1", "null_cell")]["pass_R2"], mc[("T1", "null_seed")]["pass_R2"]))
    w("  0.11-0.14. The core is carried by L2 (%.3f alone): the non-zero rescued deltas are" %
      mc[("T1", "null_cell")]["L2"])
    w("  %s in set 1 and %s in set 2; under the cell null a set's rescued sum falls with probability" % (
        sorted(C["set1"][C["set1"][:, 1] != 0, 1].tolist()), sorted(C["set2"][C["set2"][:, 1] != 0, 1].tolist())))
    w("  (1 - P(tie)) / 2, which is 1/2 when its total |delta| is odd. S3 rests on round 1's %d DD-changing cells (2d)."
      % ddc_r1)
    w("")

    # ---------------------------------------------------------------- 2 TABLE 2
    w("2 TABLE 2 - TODAY'S ARM: the movement screen's G arm (mvg1, sets 5-6: today's dispatch on the shipped guarded")
    w("  movement), a DESCRIPTION of its death density, beside round 1's arms (sets 1-2, pre-movement-fix)")
    w("2a COUNTS (cells; victims; rescued; victim deaths; DD; never detected; ff deaths; cells / seeds with >= 1 ff death;")
    w("   cells with >= 1 DD; per-cell histograms value:cells)")
    for name, Dd in (("G   (mvg1)", DG), ("dp0 (rd 1)", D0), ("dp1 (rd 1)", D1)):
        for label, x in Dd.items():
            w("  %s %-12s cells %2d | victims %3d | rescued %3d | dead %2d | DD %2d | never det. %d | ff %2d | "
              "ff cells %2d, ff seeds %2d | DD cells %2d | ff/cell %s | DD/cell %s" % (
                  name, label, x["cells"], x["victims"], x["rescued"], x["dead"], x["DD"], x["nd"], x["ff"],
                  x["ff_cells"], x["ff_seeds"], x["dd_cells"], fmt_h(x["ffh"]), fmt_h(x["ddh"])))
    sg = by_scenario(runs, "G", ("set5", "set6"))
    w("  G by scenario (ff deaths / DD / rescued / victims, sets 5 + 6): " + " | ".join(
        "%s %d / %d / %d / %d" % (sc, *sg[sc]) for sc in "ABCD"))
    w("  round 1's deltas: %d cells changed ff deaths, %d DD, %d rescued, of 64; %d ff deaths in its two arms, so %.3f"
      % (ffc_r1, ddc_r1, rsc_r1, D0["pooled"]["ff"] + D1["pooled"]["ff"],
         ffc_r1 / float(D0["pooled"]["ff"] + D1["pooled"]["ff"])))
    w("  changed cells per firefighter death.")
    w("  DENSITY RATIOS, today's arm / round 1 (mean of its two arms): ff deaths %d / %.1f = %.3f; DD %d / %.1f = %.3f;"
      % (DG["pooled"]["ff"], ff_r1_mean, rho_ff, DG["pooled"]["DD"], dd_r1_mean, rho_dd))
    w("  rescued per cell %.2f / %.2f." % (DG["pooled"]["rescued"] / 64.0,
                                           (D0["pooled"]["rescued"] + D1["pooled"]["rescued"]) / 128.0))
    w("")
    w("2b THE GUARDS AT TODAY'S DENSITY - A MODEL (descriptive): table 1's data with each non-zero firefighter-death")
    w("   delta kept with probability rho_ff = %.3f (else 0), independently per cell and draw;" % thin[0])
    w("   DD %s;" % ("kept as observed (rho_DD = %.3f: today's DD density equals round 1's)" % rho_dd
                    if thin[1] >= 1.0 else "thinned at rho_DD = %.3f" % thin[1]))
    w("   rescued unchanged. Then the same nulls / alternatives. Expected changed ff cells %.2f of %d (Binomial(%d,"
      " %.3f))." % (ffc_r1 * thin[0], ffc_r1, ffc_r1, thin[0]))
    w("   'exact over N patterns' counts the (kept subset, sign pattern) pairs enumerated, each weighted by its")
    w("   subset's probability.")
    w("  NO-EFFECT CHANGE (null)       | F1 chance FAIL (R2)        | literal core FAIL | chance PASS of")
    w("                                |                            | (F1 + L2 + L3)    | S3 + F1 + L2 + L3")
    for unit in ("cell", "seed"):
        m = mc[("T2", "null_" + unit)]
        e, pats = ex[("T2", unit)]
        w("  one sign per %-4s             | %.3f exact (MC %.3f)      | %.3f             | %.3f" % (
            unit.upper(), e["R2"], m["F1_R2"], m["core_R2"], m["pass_R2"]))
    for unit in ("cell", "seed"):
        m = mc[("T2", "null_" + unit)]
        e, pats = ex[("T2", unit)]
        w("    %s null components: L2 fails %.3f | L3 fails %.3f | S3 alone passes %.3f | R0 (never gating): F1 %.3f"
          " exact, core %.3f, PASS %.3f | exact over %d patterns" % (
              unit, m["L2"], m["L3"], m["S3"], e["R0"], m["core_R0"], m["pass_R0"], pats))
    w("  A CHANGE LIKE ROUND 1'S J     | P(F1 FAIL)                 | P(core FAIL)      | P(PASS of S3 + literals)")
    for kind, lab in (("alt_cell", "cell bootstrap (32 / set)"), ("alt_seed", "seed bootstrap (16 / set)")):
        m = mc[("T2", kind)]
        w("  %-29s | %.3f                      | %.3f             | %.3f" % (lab, m["F1_R2"], m["core_R2"],
                                                                             m["pass_R2"]))
    w("")
    w("2c F1'S EXACT REACH BY COUNT: m unit firefighter-death deltas, ceil(m/2) in one set and floor(m/2) in the other,")
    w("   every sign pattern (a no-effect change). Pooled literal alone = (1 - P(tie)) / 2; F1 adds the per-set test.")
    w("     m | split | F1 (R2) chance FAIL | pooled literal alone | (1 - P(tie)) / 2")
    for m, ma, mb, f1, r1v, an in mtab:
        w("    %2d | %d + %d | %.4f              | %.4f               | %.4f" % (m, ma, mb, f1, r1v, an))
    pm = [math.comb(ffc_r1, k) * thin[0] ** k * (1 - thin[0]) ** (ffc_r1 - k) for k in range(ffc_r1 + 1)]
    w("   At today's density (2b) m ~ Binomial(%d, %.3f): P(m = 0..%d) = %s." % (
        ffc_r1, thin[0], min(ffc_r1, 7), " ".join("%.3f" % x for x in pm[:8])))

    def p_ge(n, k, r):
        return sum(math.comb(n, j) * r ** j * (1 - r) ** (n - j) for j in range(k, n + 1))
    p5 = 1 - (1 - p_ge(m1, 5, thin[0])) * (1 - p_ge(m2, 5, thin[0]))
    w("   Under 2b's model a set keeps 5 or more changed cells (the least that can fail F1 (ii)) with probability %.4f"
      % p5)
    w("   (round 1 changed %d cells in set 1 and %d in set 2, each kept with probability rho_ff); exact, cell null:"
      % (m1, m2))
    w("   F1 (R2) %.4f against the pooled literal alone" % ex[("T2", "cell")][0]["R2"])
    w("   (R1) %.4f. READING: at G's density F1 is in effect the pooled literal, which fails a no-effect change with"
      % ex[("T2", "cell")][0]["R1"])
    w("   probability 0.5 when the total of changed deaths is odd and less when it is even (the table above).")
    w("")
    w("2d S3'S EXACT REACH BY COUNT (descriptive): k unit DD deltas and nothing else, ceil(k/2) + floor(k/2), every")
    w("   sign pattern. Table 1's S3 rate rests on round 1's %d DD-changing cells; G's DD density equals round 1's, but"
      % ddc_r1)
    w("   how many cells a change moves is the change's, not the density's.")
    w("     k | split | S3 chance PASS (implies L3 holds) | L3 chance FAIL")
    for k, ka, kb, s3v, l3v in s3_table(MG):
        w("    %2d | %d + %d | %.4f                            | %.4f" % (k, ka, kb, s3v, l3v))
    w("")

    # ---------------------------------------------------------------- 3 summary
    t1c, t1s = mc[("T1", "null_cell")], mc[("T1", "null_seed")]
    t2c, t2s = mc[("T2", "null_cell")], mc[("T2", "null_seed")]
    w("3 SUMMARY (cell null / seed null; this decides nothing)")
    w("  round 1's deltas:           F1 chance FAIL %.3f / %.3f (exact); literal core FAIL %.3f / %.3f; chance PASS of"
      % (ex[("T1", "cell")][0]["R2"], ex[("T1", "seed")][0]["R2"], t1c["core_R2"], t1s["core_R2"]))
    w("                              S3 + literals %.3f / %.3f; a change like round 1's J: P(PASS) %.3f / %.3f" % (
        t1c["pass_R2"], t1s["pass_R2"], mc[("T1", "alt_cell")]["pass_R2"], mc[("T1", "alt_seed")]["pass_R2"]))
    w("  at today's ff density (2b): F1 chance FAIL %.3f / %.3f (exact); literal core FAIL %.3f / %.3f; chance PASS"
      % (ex[("T2", "cell")][0]["R2"], ex[("T2", "seed")][0]["R2"], t2c["core_R2"], t2s["core_R2"]))
    w("                              %.3f / %.3f; a change like round 1's J: P(PASS) %.3f / %.3f" % (
        t2c["pass_R2"], t2s["pass_R2"], mc[("T2", "alt_cell")]["pass_R2"], mc[("T2", "alt_seed")]["pass_R2"]))
    w("  dispatch2_part1.txt 15 expected 0.38-0.5 for the pooled literal and about 0.8 for the literal core.")
    w("")

    # ---------------------------------------------------------------- 4 self-test
    w("4 SELF-TEST (%s)" % ("PASS" if all_ok else "FAIL"))
    for name, ok, detail in tests:
        w("  [%s] %s: %s" % ("ok" if ok else "FAIL", name, detail))
    if o.selftest_ud:
        w("  --selftest-ud inputs: %s (sha256 %s), %s (sha256 %s)" % (
            o.selftest_ud, hashlib.sha256(open(o.selftest_ud, "rb").read()).hexdigest()[:16],
            o.selftest_published, hashlib.sha256(open(o.selftest_published, "rb").read()).hexdigest()[:16]))
    else:
        w("  (the 1d.3.2 reproduction checks run only with --selftest-ud / --selftest-published)")
    w("")
    w("CLI: <py> outputs/_dq_guard_rates.py --draws %d --seed %d%s" % (
        o.draws, o.seed, " --selftest-ud <ud_deaths.json> --selftest-published <_mvg_guard_rates.txt>"
        if o.selftest_ud else ""))
    text = "\n".join(L) + "\n"
    with open(o.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    sys.stdout.write(text)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
