"""MVG follow-up round, Part 1d (outputs/urgency_part1d.txt 1d.3): the CHANCE-FAILURE RATE of each candidate reading
of the firefighter-death guard, and of the literal core it sits in, measured as 22.8.4 did.

DATA (descriptive only; sets 3-4 are in-sample and decide nothing): the urgency screen's per-cell deltas of arm M
against arm 0 on the 64 fresh cells (outputs/_ud_deaths.json, written by _ud_deaths.py from the committed records):
    d_c = (firefighter deaths, rescued, detected-victim deaths)_M - (...)_0, per cell c, set 3 and set 4.
Cells with d_c = 0 change nothing below.

NULL (no true effect), as 22.8.4's anchor: sign-flip resampling - one random sign per cell applied to all three counts
of that cell (their correlation is kept), N_DRAWS draws. P(chance FAIL) of a reading = the share of draws in which
the reading fails.

ALTERNATIVE ("a fix like arm M"): the observed per-cell deltas taken as the truth; each draw resamples 32 cells WITH
replacement within each set (a new pair of 32-cell sets). P(FAIL) = the share of draws in which the reading fails.
This is a description of this round's in-sample effect, not a prediction for (a)+(b)+guard.

READINGS of the firefighter-death guard (F1), each HARD (a failure fails the comparison):
  R0  pooled literal AND set A literal AND set B literal (this round, V-1(b) / V-7)
  R1  pooled literal only
  R2  pooled literal AND, per set, a one-sided exact SIGN test (cells up vs down) rejects at 0.05
  R3  pooled literal AND, per set, a one-sided sign-flip PERMUTATION test of the set's sum rejects at 0.05
  R4  R3 with Holm over the two sets (family-wise 0.05)
  R5  no literal clause: pooled permutation test at 0.05 AND R3's per-set tests (statistical only)
The LITERAL CORE adds L2 (rescued >= in each set) and L3 (DD pooled does not rise), both literal, as ruled.

usage: _mvg_guard_rates.py [--draws N] [--seed S]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ALPHA = 0.05
PERM_DRAWS = 4000          # the per-set permutation p-value: exact enumeration when n_nonzero <= 14, else this many


def cells():
    with open(os.path.join(HERE, "_ud_deaths.json"), encoding="utf-8") as fh:
        table = json.load(fh)
    out = {"set3": [], "set4": []}
    for e in table:
        s = e["cell"].split("/")[0]
        a0, am = e["arms"]["0"], e["arms"]["M"]
        out[s].append((len(am["ff"]) - len(a0["ff"]), int(am["rescued"]) - int(a0["rescued"]),
                       len(am["DD"]) - len(a0["DD"])))
    return {k: np.array(v, dtype=np.int64) for k, v in out.items()}


def sign_p(deltas):
    """One-sided exact sign test of 'no rise': P(Bin(n+ + n-, 1/2) >= n+); 1 when no non-zero cell."""
    n_plus = int((deltas > 0).sum())
    n_minus = int((deltas < 0).sum())
    n = n_plus + n_minus
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(n_plus, n + 1)) / 2 ** n


def perm_p(deltas, rng):
    """One-sided sign-flip permutation p of the sum (magnitudes kept): P(sum of s_c |d_c| >= observed sum)."""
    nz = np.abs(deltas[deltas != 0])
    obs = int(deltas.sum())
    if nz.size == 0:
        return 1.0
    if nz.size <= 14:
        signs = ((np.arange(2 ** nz.size)[:, None] >> np.arange(nz.size)) & 1) * 2 - 1
        sums = signs @ nz
        return float((sums >= obs).mean())
    signs = rng.choice((-1, 1), size=(PERM_DRAWS, nz.size))
    return float(((signs @ nz) >= obs).mean())


def holm2(p1, p2, alpha=ALPHA):
    lo, hi = sorted((p1, p2))
    if lo > alpha / 2:
        return False, False
    rej_lo, rej_hi = True, hi <= alpha
    return (rej_lo if p1 <= p2 else rej_hi), (rej_hi if p1 <= p2 else rej_lo)


def readings(ff3, ff4, rng, cache):
    """{reading: fails} for one draw's per-cell firefighter-death deltas of set 3 and set 4."""
    s3, s4 = int(ff3.sum()), int(ff4.sum())
    pooled_rise = s3 + s4 > 0
    key3, key4 = tuple(sorted(ff3[ff3 != 0].tolist())), tuple(sorted(ff4[ff4 != 0].tolist()))

    def memo(kind, key, arr):
        k = (kind, key, int(arr.sum()))
        if k not in cache:
            cache[k] = sign_p(arr) if kind == "sign" else perm_p(arr, rng)
        return cache[k]

    sp3, sp4 = memo("sign", key3, ff3), memo("sign", key4, ff4)
    pp3, pp4 = memo("perm", key3, ff3), memo("perm", key4, ff4)
    both = np.concatenate([ff3, ff4])
    ppool = memo("perm", tuple(sorted(both[both != 0].tolist())), both)
    h3, h4 = holm2(pp3, pp4)
    return {
        "R0": pooled_rise or s3 > 0 or s4 > 0,
        "R1": pooled_rise,
        "R2": pooled_rise or sp3 <= ALPHA or sp4 <= ALPHA,
        "R3": pooled_rise or pp3 <= ALPHA or pp4 <= ALPHA,
        "R4": pooled_rise or h3 or h4,
        "R5": ppool <= ALPHA or pp3 <= ALPHA or pp4 <= ALPHA,
        "_set_literal_only": s3 > 0 or s4 > 0,
    }


def core(d3, d4):
    """L2 (rescued >= in each set) and L3 (DD pooled does not rise) fail flags."""
    l2 = int(d3[:, 1].sum()) < 0 or int(d4[:, 1].sum()) < 0
    l3 = int(d3[:, 2].sum()) + int(d4[:, 2].sum()) > 0
    return l2, l3


def run(kind, data, draws, rng):
    names = ("R0", "R1", "R2", "R3", "R4", "R5", "_set_literal_only")
    fail = {n: 0 for n in names}
    fail_core = {n: 0 for n in names}
    l2n = l3n = 0
    cache = {}
    D3, D4 = data["set3"], data["set4"]
    for _ in range(draws):
        if kind == "null":
            d3 = D3 * rng.choice((-1, 1), size=(D3.shape[0], 1))
            d4 = D4 * rng.choice((-1, 1), size=(D4.shape[0], 1))
        else:
            d3 = D3[rng.integers(0, D3.shape[0], D3.shape[0])]
            d4 = D4[rng.integers(0, D4.shape[0], D4.shape[0])]
        r = readings(d3[:, 0], d4[:, 0], rng, cache)
        l2, l3 = core(d3, d4)
        l2n += l2
        l3n += l3
        for n in names:
            fail[n] += r[n]
            fail_core[n] += r[n] or l2 or l3
    return ({n: fail[n] / draws for n in names}, {n: fail_core[n] / draws for n in names},
            l2n / draws, l3n / draws)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20261007)
    o = ap.parse_args()
    data = cells()
    print("DATA: per-cell M - 0 deltas, fresh sets 3-4 (in-sample; descriptive only)")
    for s in ("set3", "set4"):
        D = data[s]
        print("  %s: cells %d | ff deaths: sum %+d, cells up %d down %d | rescued: sum %+d | DD: sum %+d | "
              "non-zero |ff| values %s" % (s, D.shape[0], D[:, 0].sum(), (D[:, 0] > 0).sum(), (D[:, 0] < 0).sum(),
                                           D[:, 1].sum(), D[:, 2].sum(), sorted(np.abs(D[D[:, 0] != 0, 0]).tolist())))
    for kind in ("null", "alt"):
        rng = np.random.default_rng(o.seed)
        f, fc, l2, l3 = run(kind, data, o.draws, rng)
        title = ("NULL - no true effect (sign-flip of the observed per-cell deltas)" if kind == "null" else
                 "ALTERNATIVE - arm M's in-sample per-cell effect taken as true (bootstrap of 32 cells per set)")
        print("\n%s, %d draws" % (title, o.draws))
        print("  L2 rescued >= in each set fails: %.3f   L3 DD pooled rises: %.3f" % (l2, l3))
        print("  %-6s %-62s %-12s %s" % ("", "reading", "F1 alone", "F1 + L2 + L3 (literal core)"))
        lab = {"R0": "pooled AND per-set literal (this round)", "R1": "pooled literal only",
               "R2": "pooled literal + per-set exact sign test 0.05",
               "R3": "pooled literal + per-set permutation test 0.05",
               "R4": "pooled literal + per-set permutation test, Holm over 2 sets",
               "R5": "pooled permutation 0.05 + per-set permutation 0.05 (no literal)",
               "_set_literal_only": "(per-set literal clauses alone)"}
        for n in ("R0", "R1", "R2", "R3", "R4", "R5", "_set_literal_only"):
            print("  %-6s %-62s %-12.3f %.3f" % (n, lab[n], f[n], fc[n]))
    extended(o)
    return 0


# ---------------------------------------------------------------------------------------------------------------------
# EXTENDED SECTIONS (added after the Part 1d review, 2026-10-07; the sections above are unchanged and print the same
# numbers). They use their own random stream (seed + 1), so the original sections are untouched.
#   E1 the EXACT cell-level null of each F1 reading (all sign patterns of the non-zero firefighter-death cells);
#   E2 a SEED-level null and alternative: the ring and uniform cells of a seed share the fire under CRN (Part 1 4.2), so
#      one sign (null) or one resampled seed (alternative) moves both cells together; plus seed-unit variants R2s / R3s
#      of the per-set tests (the set's per-seed sums are the units);
#   E3 the chance PASS of a fix with NO effect: S3 (17.2: pooled DD < 0, DD <= 0 in each set, still < 0 without the
#      most favourable cell) AND F1 AND L2 AND L3 - what a gentler F1 reading buys a null fix;
#   E4 the per-set clause's reach: the smallest attainable p with m non-zero cells, and the pooled literal's chance
#      FAIL (1 - P(tie)) / 2 for m unit deltas per set.
# ---------------------------------------------------------------------------------------------------------------------
def cells_with_seed():
    with open(os.path.join(HERE, "_ud_deaths.json"), encoding="utf-8") as fh:
        table = json.load(fh)
    out = {"set3": [], "set4": []}
    for e in table:
        s = e["cell"].split("/")[0]
        a0, am = e["arms"]["0"], e["arms"]["M"]
        out[s].append((int(e["seed"]), len(am["ff"]) - len(a0["ff"]), int(am["rescued"]) - int(a0["rescued"]),
                       len(am["DD"]) - len(a0["DD"])))
    return out


def s3_pass(d3, d4):
    """17.2 S3 on per-unit DD deltas (column 2): pooled < 0; each set <= 0; < 0 without the most negative unit."""
    dd = np.concatenate([d3[:, 2], d4[:, 2]])
    pooled = int(dd.sum())
    if pooled >= 0 or int(d3[:, 2].sum()) > 0 or int(d4[:, 2].sum()) > 0:
        return False
    return pooled - int(dd.min()) < 0 if dd.size else False


def seed_units(rows):
    """Sum each seed's ring and uniform deltas: [(ff, resc, dd)] per seed."""
    acc = {}
    for seed, ff, resc, dd in rows:
        a = acc.setdefault(seed, [0, 0, 0])
        a[0] += ff
        a[1] += resc
        a[2] += dd
    return np.array([acc[k] for k in sorted(acc)], dtype=np.int64)


def f1_fail(ff3, ff4, rng, cache, units3=None, units4=None):
    r = readings(ff3, ff4, rng, cache)
    if units3 is not None:
        k = ("sign_s", tuple(sorted(units3[units3 != 0].tolist())), int(units3.sum()))
        k4 = ("sign_s", tuple(sorted(units4[units4 != 0].tolist())), int(units4.sum()))
        for kk, arr in ((k, units3), (k4, units4)):
            if kk not in cache:
                cache[kk] = (sign_p(arr), perm_p(arr, rng))
        pooled_rise = int(ff3.sum()) + int(ff4.sum()) > 0
        r["R2s"] = pooled_rise or cache[k][0] <= ALPHA or cache[k4][0] <= ALPHA
        r["R3s"] = pooled_rise or cache[k][1] <= ALPHA or cache[k4][1] <= ALPHA
    return r


def extended(o):
    import itertools
    names = ("R0", "R1", "R2", "R3", "R4", "R5")
    data = cells()
    print("\nE1 EXACT CELL-LEVEL NULL of F1 (every sign pattern of the non-zero firefighter-death cells)")
    ff3, ff4 = data["set3"][:, 0], data["set4"][:, 0]
    nz3, nz4 = ff3[ff3 != 0], ff4[ff4 != 0]
    tot = {n: 0 for n in names}
    cache = {}
    rng = np.random.default_rng(o.seed + 1)
    count = 0
    for s3 in itertools.product((-1, 1), repeat=nz3.size):
        a3 = np.abs(nz3) * np.array(s3)
        for s4 in itertools.product((-1, 1), repeat=nz4.size):
            a4 = np.abs(nz4) * np.array(s4)
            r = readings(a3, a4, rng, cache)
            for n in names:
                tot[n] += r[n]
            count += 1
    print("  " + " | ".join("%s %.4f" % (n, tot[n] / count) for n in names) + "   (%d patterns)" % count)

    rows = cells_with_seed()
    U = {s: seed_units(rows[s]) for s in rows}
    print("\nE2 SEED LEVEL: per-seed sums of the ring and uniform deltas (16 seeds per set)")
    for s in ("set3", "set4"):
        u = U[s]
        print("  %s: firefighter deaths per seed, non-zero: %s | rescued %+d | DD %+d" % (
            s, sorted(u[u[:, 0] != 0, 0].tolist()), u[:, 1].sum(), u[:, 2].sum()))
    for kind in ("null", "alt"):
        rng = np.random.default_rng(o.seed + 1)
        fail = collections.Counter()
        fail_core = collections.Counter()
        passes = collections.Counter()
        cache = {}
        C3 = {s: np.array([r[1:] for r in rows[s]], dtype=np.int64) for s in rows}
        seeds = {s: [r[0] for r in rows[s]] for s in rows}
        for _ in range(o.draws):
            d = {}
            for s in ("set3", "set4"):
                uniq = sorted(set(seeds[s]))
                if kind == "null":
                    sign = dict(zip(uniq, rng.choice((-1, 1), size=len(uniq))))
                    d[s] = C3[s] * np.array([[sign[x]] for x in seeds[s]])
                else:
                    pick = rng.integers(0, len(uniq), len(uniq))
                    chosen = [uniq[i] for i in pick]
                    idx = [j for x in chosen for j, y in enumerate(seeds[s]) if y == x]
                    d[s] = C3[s][idx]
            us = {}
            for s in ("set3", "set4"):
                if kind == "null":
                    sign_rows = d[s]
                    acc = {}
                    for x, r in zip(seeds[s], sign_rows.tolist()):
                        a = acc.setdefault(x, [0, 0, 0])
                        for i in range(3):
                            a[i] += r[i]
                    us[s] = np.array([acc[k] for k in sorted(acc)], dtype=np.int64)
                else:
                    us[s] = np.array([d[s][2 * i:2 * i + 2].sum(axis=0) for i in range(len(d[s]) // 2)],
                                     dtype=np.int64)
            r = f1_fail(d["set3"][:, 0], d["set4"][:, 0], rng, cache, us["set3"][:, 0], us["set4"][:, 0])
            l2, l3 = core(d["set3"], d["set4"])
            s3ok = s3_pass(d["set3"], d["set4"])
            for n in names + ("R2s", "R3s"):
                fail[n] += r[n]
                fail_core[n] += r[n] or l2 or l3
                passes[n] += s3ok and not (r[n] or l2 or l3)
            passes["S3"] += s3ok
        print("  %s (%d draws, seed %d): F1 chance FAIL | literal core FAIL | chance PASS of S3 + F1 + L2 + L3" % (
            "NULL, one sign per SEED" if kind == "null" else "ALT, seeds resampled with both cells", o.draws,
            o.seed + 1))
        for n in names + ("R2s", "R3s"):
            print("    %-4s %.3f | %.3f | %.3f" % (n, fail[n] / o.draws, fail_core[n] / o.draws, passes[n] / o.draws))
        print("    S3 alone passes: %.3f" % (passes["S3"] / o.draws))

    print("\nE3 CELL-LEVEL NULL (as the first table: one sign per cell), chance PASS of S3 + F1 + L2 + L3")
    rng = np.random.default_rng(o.seed + 1)
    D3, D4 = data["set3"], data["set4"]
    passes = collections.Counter()
    cache = {}
    for _ in range(o.draws):
        d3 = D3 * rng.choice((-1, 1), size=(D3.shape[0], 1))
        d4 = D4 * rng.choice((-1, 1), size=(D4.shape[0], 1))
        r = readings(d3[:, 0], d4[:, 0], rng, cache)
        l2, l3 = core(d3, d4)
        s3ok = s3_pass(d3, d4)
        passes["S3"] += s3ok
        for n in names:
            passes[n] += s3ok and not (r[n] or l2 or l3)
    print("    S3 alone %.3f | " % (passes["S3"] / o.draws) + " | ".join(
        "%s %.3f" % (n, passes[n] / o.draws) for n in names))

    print("\nE4 THE PER-SET CLAUSE'S REACH (one-sided exact tests at 0.05; unit deltas)")
    for m in (3, 4, 5, 6, 8, 10, 16):
        need = next((k for k in range(m + 1) if sum(math.comb(m, j) for j in range(k, m + 1)) / 2 ** m <= ALPHA), None)
        p_tie = math.comb(2 * m, m) / 2 ** (2 * m)
        print("    m = %2d non-zero cells in a set: smallest p %.4f; rejects iff >= %s of %d rise | pooled literal over "
              "2m = %d unit deltas: chance FAIL %.3f" % (m, 2.0 ** -m, need, m, 2 * m, (1 - p_tie) / 2))


if __name__ == "__main__":
    raise SystemExit(main())
