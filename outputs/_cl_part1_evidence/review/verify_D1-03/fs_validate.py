"""Validate fs_env (fire + reconstructed smoke) against the probe's ground-truth 7x7
fire windows on every carrying advance of the xstrace files that exist (read-only),
and validate the reproduced _move_toward rule against the recorded choice."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fs_env import Env  # noqa: E402
from fs_rules import move_toward  # noqa: E402

OUT = r"E:/Projects/SAS/outputs"
RUNS = sys.argv[1:] or [
    "xsTD_east_def_1749069988", "xsTD_east_half_2070841104", "xsTD_east_half_294124329",
    "xsTD_south_half_1048395951", "xsTK_east_def_1420331661", "xsTK_south_half_903347495",
    "xsTY_east_half_2070841104",
]

tot = Counter()
for r in RUNS:
    jp = os.path.join(OUT, "_ffr_%s.json" % r)
    tp = os.path.join(OUT, "_ffr_%s.xstrace.json" % r)
    if not (os.path.isfile(jp) and os.path.isfile(tp)):
        print("skip", r)
        continue
    with open(jp, encoding="utf-8") as f:
        d = json.load(f)
    with open(tp, encoding="utf-8") as f:
        t = json.load(f)
    for fg in (7, 8, 10):
        env = Env(d, f_guess=fg)
        c = Counter()
        for a in t["advances"]:
            if not a.get("carrying"):
                continue
            k = a["step"]
            px, py = a["pos"]
            for i, row in enumerate(a["fire"]):
                dy = 3 - i
                for j, ch in enumerate(row):
                    dx = j - 3
                    if ch == "#":
                        continue
                    cell = (px + dx, py + dy)
                    tb = ch in ("F",)
                    ts = ch in ("s", "S")
                    mb = env.burning(cell, k)
                    ms = env.smoky(cell, k)
                    c["cells"] += 1
                    c["burn_ok"] += tb == mb
                    c["smoke_ok"] += ts == ms
                    if ts != ms:
                        c["smoke_fp" if ms else "smoke_fn"] += 1
                        if not env.exact_f.get(cell, True):
                            c["smoke_err_on_guessed_F"] += 1
            # rule check from reconstructed env
            for mt in a.get("move_toward") or []:
                ch, tier = move_toward(env, tuple(a["pos"]), tuple(mt["target"]), k)
                c["mt"] += 1
                c["mt_ok"] += (list(ch) if ch else None) == mt["chosen"]
                c["tier_ok"] += tier == mt["tier"]
        print("%-32s F_GUESS=%-2d cells %6d burn_ok %6d smoke_ok %6d (fp %d fn %d, on guessed F %d)  rule %d/%d tier %d/%d" % (
            r, fg, c["cells"], c["burn_ok"], c["smoke_ok"], c["smoke_fp"], c["smoke_fn"], c["smoke_err_on_guessed_F"],
            c["mt_ok"], c["mt"], c["tier_ok"], c["mt"]))
        if fg == 8:
            for kk in ("cells", "burn_ok", "smoke_ok", "mt", "mt_ok", "tier_ok"):
                tot[kk] += c[kk]
print("TOTAL (F_GUESS=8):", dict(tot))
