"""Carrying-leg round, D-10: derive the STOCK rescued tolerance before any run.

The maintainer's rule (2026-09-26): a tolerance "derived, stated before any run", in the
ungated round's shape - an accepted rate scaled to the sample size - applied to STOCK
ONLY (CRN has no re-roll, so a CRN decrease is real and must fail).

WHAT IS MEASURED. The stock gate's noise is the fire re-roll: any change of timing
re-rolls the fire's single RNG stream in the ungated configuration, and a re-rolled
fire moves individual rescues both ways with no change of policy. The recorded pairs
that isolate exactly that are the shipped arm vs its DRY twin: identical decisions,
fire writes suppressed in DRY, so the two differ only by the re-rolled fire
(firemech2_report: "the fire's single RNG stream makes per-run intact signs noise").
For every tuple both arms ran, a victim FLIPS if it is rescued (victim_steps status
at the last step) in exactly one of the two. The flip rate per tuple, phi, is the
accepted rate.

THE TOLERANCE. For a set of n tuples, the null net loss is L = D - U with D, U
independent Poisson(phi * n / 2) (a flip is equally likely to go either way under a
null change). The tolerance T(n) is the smallest t with P(L > t) <= ALPHA, with ALPHA
chosen so the three stock comparisons (C13, U30, N30) together falsely fail a null
fix at most ~10% of the time. A stock loss greater than T(n) FAILS; a loss of 1..T(n)
passes the tolerance but is still listed per victim.

Read-only: opens explicit outputs/_ffr_<tag>_*.json names found by a NON-recursive
listing that skips the quarantine by name.

  .venv/Scripts/python.exe -B outputs/_cl_tolerance.py  -> outputs/_cl_tolerance.txt
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
QUAR = "_firemech_rewound_20260914"
# (shipped arm, DRY twin, label). Stock pairs only - no CRN arm is used here.
PAIRS = [
    ("uhD", "uhY", "U30 stock, 360 steps (ungated horizon round)"),
    ("fmEFS", "fmDRY", "canonical+fresh stock, 240 steps (fire mechanic round 1)"),
]
ALPHA_FAMILY = 0.10
N_COMPARISONS = 3
ALPHA = 1.0 - (1.0 - ALPHA_FAMILY) ** (1.0 / N_COMPARISONS)
SET_SIZES = {"C13": 13, "U30": 30, "N30": 30}


def runs(tag):
    out = {}
    for n in os.listdir(HERE):  # NON-recursive
        if n == QUAR:
            continue
        m = re.match(r"^_ffr_%s_(east|south|west|north)_(half|def)_(\d+)\.json$" % re.escape(tag), n)
        if m:
            out[(m.group(1), m.group(2), int(m.group(3)))] = n
    return out


def rescued(path):
    d = json.load(open(os.path.join(HERE, path), encoding="utf-8"))
    last = (d.get("victim_steps") or [[]])[-1]
    return {str(v[0]) for v in last if str(v[2]).lower() == "rescued"}, d


def poisson_pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def p_loss_gt(t, lam):
    """P(D - U > t), D, U ~ Poisson(lam/2) independent."""
    h = lam / 2.0
    kmax = 60
    pu = [poisson_pmf(k, h) for k in range(kmax)]
    pd = pu
    p = 0.0
    for d in range(kmax):
        for u in range(kmax):
            if d - u > t:
                p += pd[d] * pu[u]
    return p


def main():
    sys.stdout.reconfigure(newline="\n")
    out = []
    say = out.append
    say("CARRYING-LEG ROUND - D-10 STOCK RESCUED TOLERANCE, derived before any run")
    say("")
    tot_flips = tot_tuples = 0
    for a, b, label in PAIRS:
        ra, rb = runs(a), runs(b)
        common = sorted(set(ra) & set(rb))
        flips = down = up = 0
        rows = []
        for t in common:
            sa, da = rescued(ra[t])
            sb, db = rescued(rb[t])
            assert da["steps"] == db["steps"], (t, da["steps"], db["steps"])
            only_a, only_b = sa - sb, sb - sa
            flips += len(only_a) + len(only_b)
            if only_a or only_b:
                rows.append("    %s/%s/%d  rescued only in %s: %s   only in %s: %s" % (
                    t[0], t[1], t[2], a, sorted(only_a), b, sorted(only_b)))
        say("PAIR %s vs %s - %s: %d common tuples, %d victim flips" % (a, b, label, len(common), flips))
        out.extend(rows)
        tot_flips += flips
        tot_tuples += len(common)
    phi = tot_flips / float(tot_tuples)
    say("")
    say("ACCEPTED RATE phi = %d flips / %d tuples = %.4f flips per tuple" % (tot_flips, tot_tuples, phi))
    say("ALPHA per comparison = %.4f (family-wise %.2f over %d stock comparisons)" % (ALPHA, ALPHA_FAMILY, N_COMPARISONS))
    say("")
    say("TOLERANCE per set: T(n) = smallest t with P(net loss > t) <= ALPHA, lambda = phi * n")
    fam = 1.0
    for name, n in SET_SIZES.items():
        lam = phi * n
        t = 0
        while p_loss_gt(t, lam) > ALPHA:
            t += 1
        p0 = p_loss_gt(0, lam)
        pt = p_loss_gt(t, lam)
        fam *= (1.0 - pt)
        say("  %-4s n=%2d lambda=%.3f  T=%d  (null P(loss>0)=%.3f, P(loss>T)=%.4f)" % (name, n, lam, t, p0, pt))
    say("  family-wise null false-fail with these T: %.3f" % (1.0 - fam))
    say("")
    say("RULE (stock only): a stock rescued loss on a set greater than T(n) FAILS G3.")
    say("A loss of 1..T(n) passes the tolerance and is still listed victim by victim.")
    say("CRN: no tolerance; any per-seed CRN decrease FAILS (maintainer D-10).")
    text = "\n".join(out) + "\n"
    print(text, end="")
    with open(os.path.join(HERE, "_cl_tolerance.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


if __name__ == "__main__":
    main()
