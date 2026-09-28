"""sysdebug round: wave 2 queue (32 runs, 360 steps, BATCH_SIZE=360, shipped defaults).

K_* (8, script hooks): runtime confirmation hooks (outputs/_sd_hooks.py), value-identical
      to plain probe runs. Seeds 9201-9208.
X_* (24, script cf): CRN-pinned fire (FM2P_CRN construction), scenario D legacy roles,
      winds south and east, seeds 9301-9306; arm "crn" = stock code, arm "dd" = the
      wind-search counters made once-per-step (outputs/_sd_cf.py --cf-dedupe).
"""
import json
import sys

BASE = ["--steps", "360", "--set", "BATCH_SIZE=360"]


def main():
    rows = []
    hooks = [
        ("K_D_N", ["--scenario", "D", "--wind", "north"]),
        ("K_D_S", ["--scenario", "D", "--wind", "south"]),
        ("K_D_E", ["--scenario", "D", "--wind", "east"]),
        ("K_D_W", ["--scenario", "D", "--wind", "west"]),
        ("K_Dh_S", ["--scenario", "D", "--wind", "south", "--fire-trackers", "2", "--victim-searchers", "2"]),
        ("K_Dh_E", ["--scenario", "D", "--wind", "east", "--fire-trackers", "2", "--victim-searchers", "2"]),
        ("K_C_W", ["--scenario", "C", "--wind", "west"]),
        ("K_B_N", ["--scenario", "B", "--wind", "north"]),
    ]
    cf = []
    for wind in ("south", "east"):
        for i, seed in enumerate(range(9301, 9307)):
            for arm, flags in (("crn", ["--cf-crn"]), ("dd", ["--cf-crn", "--cf-dedupe"])):
                cf.append(("X_%s_%d_%s" % (wind[0].upper(), seed, arm), flags,
                           ["--scenario", "D", "--wind", wind, "--seed", str(seed)]))
    # interleave: two hook runs, then eight cf runs, ...
    seed = 9201
    hk = []
    for name, args in hooks:
        hk.append({"name": name, "script": "hooks", "args": ["--"] + args + ["--seed", str(seed)] + BASE})
        seed += 1
    cfl = [{"name": n, "script": "cf", "args": flags + ["--"] + args + BASE} for n, flags, args in cf]
    while hk or cfl:
        rows.extend(hk[:2])
        hk = hk[2:]
        rows.extend(cfl[:6])
        cfl = cfl[6:]
    sys.stdout.reconfigure(newline="\n")
    for r in rows:
        print(json.dumps(r))


if __name__ == "__main__":
    main()
