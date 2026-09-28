"""sysdebug round: writes the Part 4 smoke-run queue (27 runs, 360 steps each).

Block S (16): every scenario A-D x every wind, evaluate_scenarios defaults (preset
counts, legacy roles), GLOBAL_PLANNER_MODE balanced by a Latin square (each scenario
and each wind: two runs at 0, two at 1).
Block T (9): team sizes above/below the scenario-D defaults (4 UAV / 4 victims / 2 FF).
Block H (2): scenario D with the measured 2+2 role split, west and north.
Every run: --steps 360 --set BATCH_SIZE=360 (BATCH_SIZE 300 makes model.step()
sys.exit(0) at the 302nd call - the planner round used the same pin).
Seeds 9101.. in queue order, one fresh seed per run (invariant checks, not outcomes).
"""
import json
import sys

LATIN = {  # scenario -> {wind: GPM}
    "A": {"north": 0, "south": 1, "east": 0, "west": 1},
    "B": {"north": 1, "south": 0, "east": 1, "west": 0},
    "C": {"north": 0, "south": 1, "east": 1, "west": 0},
    "D": {"north": 1, "south": 0, "east": 0, "west": 1},
}
TEAM = [  # name, scenario, wind, gpm, extra args
    ("T1_uav2", "D", "west", 0, ["--uavs", "2"]),
    ("T2_uav8", "D", "north", 1, ["--uavs", "8"]),
    ("T3_ff1", "D", "north", 0, ["--firefighters", "1"]),
    ("T4_ff5", "D", "west", 1, ["--firefighters", "5"]),
    ("T5_vic1", "D", "south", 1, ["--victims", "1"]),
    ("T6_vic10", "D", "east", 0, ["--victims", "10"]),
    ("T7_alllow", "D", "north", 1, ["--uavs", "2", "--firefighters", "1", "--victims", "2"]),
    ("T8_allhigh", "D", "west", 0, ["--uavs", "8", "--firefighters", "5", "--victims", "10",
                                    "--fire-trackers", "4", "--victim-searchers", "4"]),
    ("T9_uav1", "D", "south", 0, ["--uavs", "1"]),
]
HALF = [
    ("H1_half", "D", "west", 0, ["--fire-trackers", "2", "--victim-searchers", "2"]),
    ("H2_half", "D", "north", 1, ["--fire-trackers", "2", "--victim-searchers", "2"]),
]


def line(name, scen, wind, gpm, extra, seed):
    args = ["--scenario", scen, "--wind", wind, "--seed", str(seed), "--steps", "360",
            "--set", "BATCH_SIZE=360", "--set", "GLOBAL_PLANNER_MODE=%d" % gpm] + list(extra)
    return {"name": name, "args": args}


def main():
    rows = []
    seed = 9101
    for scen in "ABCD":
        for wind in ("north", "south", "east", "west"):
            gpm = LATIN[scen][wind]
            rows.append(line("S_%s_%s_g%d" % (scen, wind[0].upper(), gpm), scen, wind, gpm, [], seed))
            seed += 1
    for name, scen, wind, gpm, extra in TEAM + HALF:
        rows.append(line("%s_%s_g%d" % (name, wind[0].upper(), gpm), scen, wind, gpm, extra, seed))
        seed += 1
    sys.stdout.reconfigure(newline="\n")
    for r in rows:
        print(json.dumps(r))


if __name__ == "__main__":
    main()
