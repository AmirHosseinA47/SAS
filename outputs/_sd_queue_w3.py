"""sysdebug round: wave 3 queue (24 runs, 360 steps, BATCH_SIZE=360, CRN fire in every arm).

N_* (12, cf2 --cf2-noartifact): the three artifact fail-safe reasons suppressed; pairs with
      wave 2's X_<wind>_<seed>_crn (same seeds 9301-9306, D legacy, south/east).
F_* (6, cf2 --cf2-allowfire): the move_toward_fire tracker family let through the filter;
      pairs with X_S_<seed>_crn.
U_* (6, cf2 [--cf2-undetected-off]): the three Part 4 configurations that produced
      never_detected write-offs (S_A_E_g0, T6_vic10_E_g0, H2_half_N_g1), each as a CRN stock
      arm (uc) and a CRN arm with the 210-step write-off disabled (uo).
"""
import json
import sys

BASE = ["--steps", "360", "--set", "BATCH_SIZE=360"]


def main():
    rows = []
    for wind in ("south", "east"):
        for seed in range(9301, 9307):
            rows.append({"name": "N_%s_%d" % (wind[0].upper(), seed), "script": "cf2",
                         "args": ["--cf2-noartifact", "--cf-crn", "--", "--scenario", "D", "--wind", wind,
                                  "--seed", str(seed)] + BASE})
    for seed in range(9301, 9307):
        rows.append({"name": "F_S_%d" % seed, "script": "cf2",
                     "args": ["--cf2-allowfire", "--cf-crn", "--", "--scenario", "D", "--wind", "south",
                              "--seed", str(seed)] + BASE})
    cfgs = [
        ("AE9103", ["--scenario", "A", "--wind", "east", "--seed", "9103", "--set", "GLOBAL_PLANNER_MODE=0"]),
        ("DEv10_9122", ["--scenario", "D", "--wind", "east", "--seed", "9122", "--set", "GLOBAL_PLANNER_MODE=0",
                        "--victims", "10"]),
        ("DhN9127", ["--scenario", "D", "--wind", "north", "--seed", "9127", "--set", "GLOBAL_PLANNER_MODE=1",
                     "--fire-trackers", "2", "--victim-searchers", "2"]),
    ]
    for tag, args in cfgs:
        rows.append({"name": "U_%s_uc" % tag, "script": "cf2", "args": ["--cf-crn", "--"] + args + BASE})
        rows.append({"name": "U_%s_uo" % tag, "script": "cf2",
                     "args": ["--cf2-undetected-off", "--cf-crn", "--"] + args + BASE})
    sys.stdout.reconfigure(newline="\n")
    for r in rows:
        print(json.dumps(r))


if __name__ == "__main__":
    main()
