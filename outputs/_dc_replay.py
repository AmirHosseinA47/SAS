#!/usr/bin/env python
"""Depot-cost round, Part 1 evidence: replay a candidate return trigger offline.

WHY THIS EXISTS. The decisive question for arms B/C/D is not "how much does a
return leg cost" - that is already measured - but "does a distance-based trigger
FIRE AT ALL inside a 240-step run". A wave costs hours; the recorded per-step UAV
battery and position from the base-station round answer it in seconds.

THE REPLAY IS EXACT UP TO THE FIRST TRIGGER, and only there. Before any UAV turns
for home, an armed run's trajectory is identical to the return-less arm it is
replayed against, because the return code is the only thing that differs and it
has not fired yet. After the first trigger the trajectories diverge and the replay
is a bound, not a prediction. Every number below is therefore reported as
"first trigger per UAV" and nothing is claimed past it.

VALIDATION. Replaying the SHIPPED flat-60 rule against the bsspawn arm must
reproduce the bsret arm's own recorded trigger_step and trigger_distance exactly,
because bsret IS bsspawn plus the return leg. `--validate` does that check.

ORDERING, from agents.py:509-517 - advance() calls _apply_return_to_base() BEFORE
move() and BEFORE _update_battery_after_step(). The harness appends a uav_steps
row AFTER model.step(). So the state the trigger sees on recorded index i is row
i-1 (position and battery after the previous step); index 0 sees the spawn cell at
battery 100.0.

Read-only. Runs no simulation.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))

CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "def", s) for s in (101, 202, 303)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])

HEIGHT = WIDTH = 50
SIZE = 5
DRAIN_STEP = 0.1
DRAIN_MOVE = 0.2
PER_MOVE = DRAIN_STEP + DRAIN_MOVE          # 0.3, exactly agents.py _rtb_trigger_level

# Corner encoding copied from wildfire_model._build_base_station: 0 NW, 1 NE,
# 2 SW, 3 SE, with x on the HEIGHT axis and y on the WIDTH axis.
CORNERS = {"NW": 0, "NE": 1, "SW": 2, "SE": 3}


def corner_origin(corner: int, size: int = SIZE):
    ox = 0 if corner in (0, 2) else HEIGHT - size
    oy = 0 if corner in (2, 3) else WIDTH - size
    return ox, oy


def ranked_berths(origin, size: int = SIZE):
    ox, oy = origin
    cells = [(ox + i, oy + j) for i in range(size) for j in range(size)]
    return sorted(
        cells,
        key=lambda c: (-min(c[0], c[1], HEIGHT - 1 - c[0], WIDTH - 1 - c[1]), c[0], c[1]),
    )


def central_origin(size: int = SIZE):
    """The 5x5 block whose centre is the pre-feature spawn cluster anchor.

    (HEIGHT//2, WIDTH//2) = (25,25) is where the pre-feature UAV cluster starts,
    so origin = (25-2, 25-2) = (23,23) puts (25,25) at the block's centre.
    """
    return (HEIGHT // 2 - size // 2, WIDTH // 2 - size // 2)


def depot_set(name: str):
    """Named depot configurations -> list of (origin, ranked_berths)."""
    if name == "NW":
        origins = [corner_origin(CORNERS["NW"])]
    elif name == "CENTRAL":
        origins = [central_origin()]
    elif name in ("NW+SE", "NW+NE", "NW+SW"):
        a, b = name.split("+")
        origins = [corner_origin(CORNERS[a]), corner_origin(CORNERS[b])]
    else:
        raise SystemExit("unknown depot set %r" % name)
    return [(o, ranked_berths(o)) for o in origins]


def uav_berths(depots, n_uavs: int, split: str):
    """Per-UAV berth in EACH depot, and the depot each UAV spawns at.

    Every UAV holds a dedicated berth in every depot, which is what preserves the
    deadlock-free invariant the source relies on ("distinct berths are what make
    the return leg deadlock-free") when a UAV may return to either one.
    """
    per = []
    for a in range(n_uavs):
        per.append([d[1][a] for d in depots])
    if split == "all-first" or len(depots) == 1:
        home = [0] * n_uavs
    elif split == "alternate":
        home = [a % len(depots) for a in range(n_uavs)]
    elif split == "block":
        half = (n_uavs + len(depots) - 1) // len(depots)
        home = [min(a // half, len(depots) - 1) for a in range(n_uavs)]
    else:
        raise SystemExit("unknown split %r" % split)
    return per, home


def load(tag, wind, roles, seed):
    p = os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, roles, seed))
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_cell(c):
    if c is None:
        return None
    if isinstance(c, (list, tuple)):
        return (int(c[0]), int(c[1]))
    s = str(c).replace("(", "").replace(")", "").split(",")
    try:
        return (int(float(s[0])), int(float(s[1])))
    except (ValueError, IndexError):
        return None


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def exact_battery(rows, col):
    """Reconstruct the UAV's battery as the EXACT float the model held.

    The harness rounds battery_level to 4 decimals, and the shipped flat-60 rule
    lands on a float tie: the model's accumulated value at the crossing step is
    60.000000000000284, which the record stores as 60.0. Comparing against the
    rounded value fires the trigger one step early on 15 of 52 trips. Replaying
    the arithmetic of agents.py _update_battery_after_step in the same order
    reproduces the model's float bit for bit.

    `moved` is recoverable from the record: a successful move always changes the
    cell by exactly one, and a refused move leaves the position untouched, so
    position-unchanged is exactly not-moved. Returns the PRE-step battery for each
    recorded index, i.e. the value the trigger reads on the following step.
    """
    pre = []
    b = 100.0
    prev_pos = None
    for i in range(len(rows)):
        pre.append(b)
        pos = parse_cell(rows[i][col][1])
        moved = prev_pos is not None and pos is not None and pos != prev_pos
        if prev_pos is None:
            # Index 0's move is measured against the spawn cell, which the record
            # does not carry; fall back to the recorded value for that one step.
            rec = rows[i][col][4]
            b = float(rec) if rec is not None else b
        else:
            b -= DRAIN_STEP
            if moved:
                b -= DRAIN_MOVE
            b = max(0.0, min(100.0, float(b)))
        prev_pos = pos
    return pre


E_OUTBOUND = 0.1 + 0.2 * (5.0 / 6.0)   # 0.26667, the conservative move fraction
                                       # the shipped derivation already chose


def horizon_level(d, steps):
    """The horizon term of the shipped derivation, evaluated at the LIVE distance.

    The shipped reserve froze this at the worst case D = 90 and got 60. Evaluated
    at the UAV's actual d it is the same inequality with the same constants:
    the return needs d steps and must finish by `steps`, so
        R >= 100 - e*(steps - d),  e = 0.1 + 0.2m at m = 5/6.
    At d = 90 it returns exactly 60.0, so this is a strict generalisation of the
    shipped rule and is nowhere less conservative than it.
    """
    return 100.0 - E_OUTBOUND * (float(steps) - float(d))


def replay_run(data, berths_per_uav, reserve, margin, horizon_steps=None):
    """First trigger per UAV under
           trigger = max(reserve, 0.3*d_nearest + margin [, horizon_level(d)]).

    d_nearest is the Manhattan distance to the NEAREST of this UAV's berths, which
    is the two-depot rule ("a UAV returns to the nearest one") and degenerates to
    the single-depot rule when there is one berth.

    Index mapping, from agents.py:509-517 and the harness loop: the trigger on
    step k reads the position and battery the UAV held after step k-1, which the
    harness stored at uav_steps[k-2].
    """
    rows = data.get("uav_steps") or []
    if not rows:
        return {}
    order = [str(r[0]) for r in rows[0]]
    idx_of = {uid: i for i, uid in enumerate(order)}
    out = {}
    for uid in order:
        a = idx_of[uid]
        berths = berths_per_uav[a % len(berths_per_uav)]
        exact = exact_battery(rows, a)
        fired = None
        for i in range(1, len(rows)):
            prev = rows[i - 1][a]
            pos = parse_cell(prev[1])
            if pos is None:
                continue
            # exact[i] is the battery BEFORE step i+1 drains it, which is exactly
            # the value _apply_return_to_base compares on step i+1.
            batt = exact[i]
            d = min(manhattan(pos, b) for b in berths)
            level = max(reserve, PER_MOVE * d + margin)
            if horizon_steps is not None:
                level = max(level, horizon_level(d, horizon_steps))
            if batt <= level:
                fired = {"step": i + 1, "battery": batt, "d": d, "level": level, "pos": pos}
                break
        out[uid] = fired
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="bsspawn",
                    help="recorded arm to replay against (bsspawn = depot spawn, NO return leg)")
    ap.add_argument("--sample", default="canonical", choices=("canonical", "fresh", "both"))
    ap.add_argument("--depots", default="NW")
    ap.add_argument("--split", default="all-first", choices=("all-first", "alternate", "block"))
    ap.add_argument("--reserve", type=float, default=0.0)
    ap.add_argument("--margin", type=float, default=5.0)
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--horizon", action="store_true",
                    help="also apply the horizon term at the LIVE distance "
                         "(the shipped derivation's second constraint, unfrozen)")
    ap.add_argument("--validate", action="store_true",
                    help="replay the shipped flat-60 rule and compare with the bsret arm's own rtb_log")
    args = ap.parse_args()

    samples = {"canonical": CANON, "fresh": FRESH}
    names = ["canonical", "fresh"] if args.sample == "both" else [args.sample]

    depots = depot_set(args.depots)
    print("DEPOTS %-8s origins %s" % (args.depots, [d[0] for d in depots]))
    print("  berths (first 6 ranked per depot): %s"
          % [[tuple(c) for c in d[1][:6]] for d in depots])

    if args.validate:
        print("\nVALIDATION - replay the SHIPPED rule max(60, 0.3d+5) against %s and compare"
              % args.arm)
        print("with the bsret arm's OWN recorded rtb_log (bsret == %s + the return leg,"
              % args.arm)
        print("so the two must agree exactly on the FIRST trigger of every UAV).")
        ok = bad = miss = 0
        for name in names:
            for wind, roles, seed in samples[name]:
                spawn = load(args.arm, wind, roles, seed)
                ret = load("bsret", wind, roles, seed)
                if spawn is None or ret is None:
                    miss += 1
                    continue
                bs = spawn.get("base_station") or {}
                bl = [tuple(c) for c in (bs.get("uav_berths") or [])]
                if not bl:
                    miss += 1
                    continue
                per = [[b] for b in bl]
                rep = replay_run(spawn, per, 60.0, 5.0)
                rec = ret.get("rtb_log") or {}
                for uid, trips in sorted(rec.items()):
                    first = trips[0] if trips else None
                    r = rep.get(uid)
                    if first is None and r is None:
                        ok += 1
                        continue
                    if first is None or r is None:
                        bad += 1
                        print("   MISMATCH %s/%s/%s %s: replay=%s recorded=%s"
                              % (wind, roles, seed, uid, r, first))
                        continue
                    if (r["step"] == first["trigger_step"]
                            and r["d"] == first["trigger_distance"]):
                        ok += 1
                    else:
                        bad += 1
                        print("   MISMATCH %s/%s/%s %s: replay step %d d %d | recorded step %s d %s"
                              % (wind, roles, seed, uid, r["step"], r["d"],
                                 first["trigger_step"], first["trigger_distance"]))
        print("   EXACT %d   MISMATCH %d   missing-file %d" % (ok, bad, miss))
        return

    for name in names:
        fired_steps, fired_d, fired_batt = [], [], []
        n_uav = n_fired = 0
        runs = 0
        for wind, roles, seed in samples[name]:
            data = load(args.arm, wind, roles, seed)
            if data is None:
                continue
            runs += 1
            bs = data.get("base_station") or {}
            n = len(bs.get("uav_berths") or []) or 4
            per, _home = uav_berths(depots, n, args.split)
            rep = replay_run(data, per, args.reserve, args.margin,
                             args.steps if args.horizon else None)
            for uid, r in sorted(rep.items()):
                n_uav += 1
                if r is not None:
                    n_fired += 1
                    fired_steps.append(r["step"])
                    fired_d.append(r["d"])
                    fired_batt.append(r["battery"])
        print("\n%s  (%d runs, arm %s, reserve %.1f margin %.2f%s, split %s)"
              % (name.upper(), runs, args.arm, args.reserve, args.margin,
                 ", live horizon" if args.horizon else "", args.split))
        print("  UAV-runs %3d   FIRST TRIGGER FIRES %3d  (%.1f%%)   never fires %3d"
              % (n_uav, n_fired, 100.0 * n_fired / max(n_uav, 1), n_uav - n_fired))
        # The return-leg SHARE is the metric the round is trying to move. A trip
        # that triggers at step s and needs d steps contributes min(d, steps - s)
        # steps inside the horizon; a trip that never triggers contributes none.
        # This is a FIRST-TRIP bound: a second trip can only add to it, and under
        # the shipped rule there was exactly one trip per UAV per run.
        spent = sum(min(d, args.steps - s) for s, d in zip(fired_steps, fired_d))
        print("  RETURN-LEG SHARE (first trip only, bound): %5d of %5d UAV-steps = %5.2f%%"
              % (spent, n_uav * args.steps, 100.0 * spent / max(n_uav * args.steps, 1)))
        if fired_steps:
            print("     trigger step      mean %6.1f  min %3d  max %3d"
                  % (statistics.mean(fired_steps), min(fired_steps), max(fired_steps)))
            print("     trigger distance  mean %6.1f  min %3d  max %3d"
                  % (statistics.mean(fired_d), min(fired_d), max(fired_d)))
            print("     trigger battery   mean %6.2f  min %5.2f  max %5.2f"
                  % (statistics.mean(fired_batt), min(fired_batt), max(fired_batt)))
            # Steps left after the return completes, at 0.3/step over d cells.
            left = [args.steps - (s + d) for s, d in zip(fired_steps, fired_d)]
            print("     steps left after arrival  mean %6.1f  min %4d  max %4d  (negative = still flying at the horizon)"
                  % (statistics.mean(left), min(left), max(left)))


if __name__ == "__main__":
    main()
