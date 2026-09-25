"""Read-only: does sim.move_toward reproduce the RECORDED carrying moves before each drop?
One-step replay from each recorded position; smoke variants S0 / S4."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim  # noqa: E402

OUT_DIR = r"E:\Projects\SAS\outputs"
CASES = [
    ("_ffr_uhY_east_half_1291443119.json", "ff_unit_1", 84, 148),
    ("_ffr_uhD_east_half_1291443119.json", "ff_unit_1", 84, 148),
    ("_ffr_fmDRY_east_half_101.json", "ff_unit_0", 100, 135),
    ("_ffr_f2cEFS_east_half_404.json", "ff_unit_1", 104, 133),
    ("_ffr_fmOFF_east_half_606.json", "ff_unit_0", 165, 205),
    ("_ffr_f2cOFF_east_def_202.json", "ff_unit_0", 92, 169),
]


def exit_target(p):
    x, y = p
    dists = {(0, y): x, (49, y): 49 - x, (x, 0): y, (x, 49): 49 - y}
    return min(dists, key=dists.get)


for n, ff, s0, drop in CASES:
    with open(os.path.join(OUT_DIR, n), encoding="utf-8") as f:
        d = json.load(f)
    bi = d.get("burn_intervals") or {}

    def pos(s):
        r = next(x for x in d["ff_steps"][s - 1] if x[0] == ff)
        return tuple(r[1])

    tgt = exit_target(pos(s0))
    res = {}
    for tail in (0, 4):
        ok = bad = 0
        mism = []
        for s in range(s0 + 1, drop):
            p, _t = sim.move_toward(bi, pos(s - 1), tgt, s, tail)
            if p == pos(s):
                ok += 1
            else:
                bad += 1
                mism.append((s, pos(s - 1), p, pos(s)))
        res[tail] = (ok, bad, mism[:4])
    print(n, ff, "carry", s0, "->", drop, "exit", tgt, "| S0 match %d/%d" % (res[0][0], res[0][0] + res[0][1]),
          "| S4 match %d/%d" % (res[4][0], res[4][0] + res[4][1]), "| S0 first mismatches", res[0][2])
