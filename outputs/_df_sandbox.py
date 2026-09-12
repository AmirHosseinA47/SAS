#!/usr/bin/env python
"""Docking-deadlock round, Part 1: replay the deadlock under candidate rules.

WHY THIS IS EXACT AND NOT A BOUND, for scenario `modetwo`. In the mode-2 arm
(_ffr_bsret_*) the other three UAVs are DOCKED, and BASE_STATION_MODE 2 has no
release path at all - agents.py:503 gates the release on `mode >= 3` - so they
provably never move again. The stalled UAV is therefore alone in a static world,
and stepping it forward under a candidate rule reproduces what the model would
do, exactly. Scenario `modethree` freezes the blockers by hand and is a WORST
CASE rather than a replay: at mode 3 the blockers would eventually recharge and
leave, so a rule that terminates here terminates there too.

This runs no simulation and imports nothing from the model; the steering under
test is transcribed from agents.py so the candidates can be compared before any
of them is implemented.

  R0  HEAD, verbatim. Reproduces the deadlock.
  R1  "when stalled, do not re-pick a direction the grid already refused."
      The obvious minimal fix. IT PING-PONGS - kept here because it is the
      first thing anyone will propose and the replay is what rules it out.
  R2  the recommended rule: when stalled, LATCH the nearest free cell of the
      target depot and steer to that, choosing among free directions only.

usage: _df_sandbox.py [--scenario modetwo|modethree|both] [--limit 40] [--k 3]
"""
from __future__ import annotations

import argparse

H = W = 50
MOVE_X = [1, 0, -1, 0]
MOVE_Y = [0, -1, 0, 1]
DIRN = {0: "+x", 1: "-y", 2: "-x", 3: "+y"}

SCENARIOS = {
    # bsret east/half/101 from frame 207. 2502 is returning; the rest are docked
    # at mode 2 and never move again. 2502's OWN BERTH IS FREE - nobody stole it.
    # It is stuck because the only cell on its pure-axis path holds a docked UAV.
    "modetwo": {
        "who": "2502",
        "start": (3, 44),
        "berth": (3, 46),
        "depot_origin": (0, 45),
        "blockers": {(4, 45): "2500 docked", (3, 45): "2501 docked",
                     (4, 46): "2503 docked"},
        "note": "berth is FREE; the PATH cell (3,45) is permanently occupied",
    },
    # dcB east/half/808 from frame 203, with the blockers frozen. Here the berth
    # ITSELF is occupied - by the UAV that took the transient-occupancy fallback -
    # so no amount of routing reaches it and the rule has to find another way to
    # terminate the trip.
    "modethree": {
        "who": "2500",
        "start": (4, 44),
        "berth": (4, 45),
        "depot_origin": (0, 45),
        "blockers": {(4, 45): "2502 fallback-docked ON THIS UAV'S BERTH",
                     (3, 45): "2501 docked", (4, 46): "2503 docked"},
        "note": "the berth itself is taken; termination must come from elsewhere",
    },
}


def depot_of(origin, size=5):
    ox, oy = origin
    return {(ox + i, oy + j) for i in range(size) for j in range(size)}


def make_free(blockers):
    def free(c):
        return 0 <= c[0] < H and 0 <= c[1] < W and c not in blockers
    return free


def greedy(pos, tgt, stalled):
    """agents.UAV._rtb_direction at HEAD, as a pure function."""
    x, y = pos
    dx, dy = tgt[0] - x, tgt[1] - y
    x_dir = 0 if dx > 0 else (2 if dx < 0 else None)
    y_dir = 3 if dy > 0 else (1 if dy < 0 else None)
    if abs(dx) >= abs(dy):
        primary, secondary = x_dir, y_dir
    else:
        primary, secondary = y_dir, x_dir
    if stalled and secondary is not None:
        primary, secondary = secondary, primary
    return primary, secondary


def R0(st, env):
    p, s = greedy(st["pos"], env["berth"], st["stalled"])
    return p if p is not None else (s if s is not None else 0)


def R1(st, env):
    """Stalled: take the first candidate direction that is actually free."""
    pos, free = st["pos"], env["free"]
    p, s = greedy(pos, env["berth"], st["stalled"])
    if not st["stalled"]:
        return p if p is not None else (s if s is not None else 0)
    order = [d for d in (p, s) if d is not None]
    dx, dy = env["berth"][0] - pos[0], env["berth"][1] - pos[1]
    perp = [0, 2] if dx == 0 else ([3, 1] if dy == 0 else [])
    for d in perp + [0, 1, 2, 3]:
        if d not in order:
            order.append(d)
    for d in order:
        if free((pos[0] + MOVE_X[d], pos[1] + MOVE_Y[d])):
            return d
    return p if p is not None else 0


def R2(st, env):
    """Stalled and OUTSIDE the depot: latch the nearest free depot cell, go there.

    Two properties do the work.

    THE LATCH is what stops the ping-pong. Without it the UAV steps aside and the
    next, UNSTALLED, greedy step walks it straight back - which is exactly what
    R1 does. With a fixed target the greedy is monotone: every successful move
    strictly reduces Manhattan distance to a cell that does not move.

    THE SCOPE is "outside the depot only". Once the UAV is inside its target
    depot the berth is the target again and the DEBOUNCED FALLBACK is what
    terminates the trip. Letting the recovery keep re-latching inside the depot
    makes the UAV wander back out - which an earlier draft of this rule did, and
    which this replay is what caught.
    """
    pos, free, depot = st["pos"], env["free"], env["depot"]
    inside = pos in depot
    if inside:
        st["rc"] = None
    elif st["stalled"]:
        rc = st.get("rc")
        if rc is None or not free(rc) or rc == pos:
            cand = sorted((c for c in depot if free(c) and c != pos),
                          key=lambda c: (abs(c[0] - pos[0]) + abs(c[1] - pos[1]),
                                         c[0], c[1]))
            st["rc"] = cand[0] if cand else None
    rc = st.get("rc")
    tgt = rc if (rc is not None and not inside) else env["berth"]
    p, s = greedy(pos, tgt, st["stalled"])
    if st["stalled"] and not inside:
        # Obstacle-aware greedy toward the LATCHED cell: among the directions
        # that are actually free, the one that gets closest to it.
        best = None
        for d in range(4):
            c = (pos[0] + MOVE_X[d], pos[1] + MOVE_Y[d])
            if not free(c):
                continue
            dist = abs(c[0] - tgt[0]) + abs(c[1] - tgt[1])
            if best is None or dist < best[0]:
                best = (dist, d)
        if best is not None:
            return best[1]
    return p if p is not None else (s if s is not None else 0)


def R3(st, env):
    """The adversarially-reviewed alternative: DO NOT TOUCH THE STEER.

    Leave _rtb_direction exactly as it is - it is distance-monotone, and that is
    what makes a consecutive-stall counter a valid termination variant - and put
    the terminator one level up: after L consecutive refused steps, dock on
    whatever cell the UAV is standing on, provided it is inside the depot OR on
    its one-cell doorstep. Optionally take ONE sideways step per trip first.

    Its termination is cheap and real. Its cost is the DOORSTEP DOCK, which is
    what the head-to-head below is for.
    """
    return R0(st, env)          # the steer is unchanged; termination is in run()


def R4(st, env):
    """R2 corrected: the latch is STICKY, not stall-gated.

    R2 as first drafted engaged the recovery only on the step where the UAV was
    stalled, and let the shipped greedy steer run on every other step. That is
    the ping-pong: the escape step moves the UAV, so the NEXT step it is not
    stalled, the greedy toward the berth runs, and it walks straight back. The
    latch has to steer EVERY step until the depot is reached, not just the
    stalled ones.
    """
    pos, free, depot = st["pos"], env["free"], env["depot"]
    inside = pos in depot
    prev_tgt = st.get("tgt")
    if inside:
        st["rc"] = None
    else:
        rc = st.get("rc")
        if st["stalled"] and (rc is None or rc == pos or not free(rc)):
            cand = sorted((c for c in depot if free(c) and c != pos),
                          key=lambda c: (abs(c[0] - pos[0]) + abs(c[1] - pos[1]),
                                         c[0], c[1]))
            st["rc"] = cand[0] if cand else None
    rc = st.get("rc")
    tgt = rc if (rc is not None and not inside) else env["berth"]
    st["tgt"] = tgt
    # THE STALL IS RELATIVE TO A TARGET. The shipped swap exists to break a
    # deadlock against the cell we were refused moving toward; applying it to a
    # target we have not yet been refused against just picks the wrong axis - and
    # in the (4,44) case it picks the blocked one. Only carry the stall forward
    # when the target is the same one we stalled against.
    p, s = greedy(pos, tgt, st["stalled"] and tgt == prev_tgt)
    return p if p is not None else (s if s is not None else 0)


RULES = [(R0, "R0 HEAD (verbatim)"),
         (R1, "R1 refuse-known-blocked"),
         (R2, "R2 latched + obstacle-aware (1st draft)"),
         (R3, "R3 leave steer alone + doorstep dock"),
         (R4, "R4 latched STICKY (RECOMMENDED)")]


def doorstep(env):
    """The depot plus every cell one step outside it."""
    out = set(env["depot"])
    for c in env["depot"]:
        for d in range(4):
            out.add((c[0] + MOVE_X[d], c[1] + MOVE_Y[d]))
    return out


def run(rule, env, k, limit, doorstep_dock=False):
    """Step one returning UAV forward under `rule`.

    `doorstep_dock` selects R3's terminator: dock after k CONSECUTIVE refused
    steps anywhere inside the depot or on its doorstep. Otherwise the terminator
    is the shipped one, re-keyed to the same consecutive-stall witness but scoped
    to the depot INTERIOR - which is the whole difference between the two.
    """
    st = {"pos": env["start"], "stalled": False, "rc": None}
    stall = 0
    log = []
    visits = {}
    for t in range(limit):
        pos = st["pos"]
        visits[pos] = visits.get(pos, 0) + 1
        if pos == env["berth"]:
            return t, "DOCKED AT ITS OWN BERTH %s" % (pos,), log, visits
        if stall >= k:
            if doorstep_dock and pos in doorstep(env):
                where = "INSIDE the depot" if pos in env["depot"] else "on the DOORSTEP, OUTSIDE the depot"
                return t, "dock at %s after %d stalled steps - %s" % (pos, stall, where), log, visits
            if not doorstep_dock and pos in env["depot"]:
                return t, "dock at %s after %d stalled steps - INSIDE the depot" % (pos, stall), log, visits
        d = rule(st, env)
        nxt = (pos[0] + MOVE_X[d], pos[1] + MOVE_Y[d])
        moved = env["free"](nxt)
        log.append("    step %2d: at %-8s %s -> %-8s %s"
                   % (t, str(pos), DIRN[d], str(nxt), "move" if moved else "BLOCKED"))
        st["stalled"] = not moved
        stall = 0 if moved else stall + 1
        if moved:
            st["pos"] = nxt
    worst = max(visits.values())
    if len(visits) == 1:
        kind = "FROZEN on one cell - what HEAD does"
    elif worst > 2:
        kind = ("LIVELOCK - it keeps MOVING and revisits a cell %d times, which "
                "a consecutive-no-move stall gate scores as ZERO" % worst)
    else:
        kind = "wandering"
    return None, "NEVER TERMINATED in %d steps (%s)" % (limit, kind), log, visits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="both",
                    choices=sorted(SCENARIOS) + ["both"])
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--k", type=int, default=3,
                    help="BASE_STATION_DOCK_BLOCK_STEPS under test")
    args = ap.parse_args()
    names = sorted(SCENARIOS) if args.scenario == "both" else [args.scenario]
    for name in names:
        sc = SCENARIOS[name]
        env = {"berth": sc["berth"], "start": sc["start"],
               "depot": depot_of(sc["depot_origin"]),
               "free": make_free(set(sc["blockers"]))}
        print("=" * 74)
        print("SCENARIO %s   UAV %s at %s, berth %s"
              % (name, sc["who"], sc["start"], sc["berth"]))
        print("  %s" % sc["note"])
        for cell, why in sorted(sc["blockers"].items()):
            print("    blocker %-8s %s" % (str(cell), why))
        print("")
        for rule, label in RULES:
            t, verdict, log, visits = run(rule, env, args.k, args.limit,
                                          doorstep_dock=(rule is R3))
            print("  %-34s %s" % (label, verdict))
            for line in log[:10]:
                print(line)
            if len(log) > 10:
                print("    ... (%d steps in total)" % len(log))
            print("")


if __name__ == "__main__":
    main()
