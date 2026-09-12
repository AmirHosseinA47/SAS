#!/usr/bin/env python
"""Docking-deadlock round, Part 1 evidence. Read-only; runs no simulation.

Every number quoted in outputs/dockfix_part1.txt is produced here, from the
depot-cost round's own recorded artifacts (outputs/_ffr_dc*_*.json).

  trace     the dcB east/half/808 deadlock, frame by frame, with the
            single-step transit that triggers it
  steer     symbolic execution of agents.UAV._rtb_direction, verbatim, showing
            that the stall sidestep is a NO-OP on a pure-axis approach
  fallback  fallback docks per arm, counted from EXISTING recorded fields only
            (dock_cell != target_berth); reproduces dcA 1 / dcB 6 / dcC 26 / dcD 1
  occupancy the duration of every episode in which one UAV stands on another
            UAV's berth. This is what justifies the persistence threshold: the
            distribution is bimodal with an EMPTY GAP between 6 and 13 steps.
  geometry  the depot footprint, and which cells of the approach are outside it
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SEED_RUN = os.path.join(HERE, "_ffr_dcB_east_half_808.json")

# uav_steps row:   [uid, pos, role, selected_dir, battery, base_state]
# uav_actions row: [uid, action, burning, vis_smoke, agent_smoke, fire_dist]
MOVE_X = [1, 0, -1, 0]
MOVE_Y = [0, -1, 0, 1]
DIRN = {0: "+x", 1: "-y", 2: "-x", 3: "+y", None: "--"}


def load(path):
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8-sig"))


def depot_cells(station):
    size = int(station["size"])
    out = set()
    for ox, oy in (station.get("depots") or [station["origin"]]):
        out |= {(ox + i, oy + j) for i in range(size) for j in range(size)}
    return out


# ------------------------------------------------------------------- steer ----
def rtb_direction(pos, berth, last_pos, selected_dir=0):
    """Verbatim re-implementation of agents.UAV._rtb_direction at HEAD 9f77178."""
    x, y = pos
    dx, dy = berth[0] - x, berth[1] - y
    x_dir = 0 if dx > 0 else (2 if dx < 0 else None)
    y_dir = 3 if dy > 0 else (1 if dy < 0 else None)
    if abs(dx) >= abs(dy):
        primary, secondary = x_dir, y_dir
    else:
        primary, secondary = y_dir, x_dir
    stalled = last_pos is not None and last_pos == (x, y)
    if stalled and secondary is not None:
        primary, secondary = secondary, primary
    trace = ("dx=%s dy=%s x_dir=%s y_dir=%s stalled=%s -> primary=%s secondary=%s"
             % (dx, dy, x_dir, y_dir, stalled, primary, secondary))
    if primary is not None:
        return primary, trace
    if secondary is not None:
        return secondary, trace
    return int(selected_dir), trace


def mode_steer(_args):
    print("STEER  agents.UAV._rtb_direction, symbolically executed")
    print("  The stall sidestep swaps primary/secondary. On a PURE-AXIS approach")
    print("  one delta is 0, so that axis' direction is None, `secondary` is None,")
    print("  the swap is skipped and the ORIGINAL BLOCKED direction is returned.")
    print("")
    cases = [
        ("pure axis   (4,44)  -> (4,45)  fresh  ", (4, 44), (4, 45), None),
        ("pure axis   (4,44)  -> (4,45)  STALLED", (4, 44), (4, 45), (4, 44)),
        ("pure axis   (3,44)  -> (3,46)  STALLED", (3, 44), (3, 46), (3, 44)),
        ("two axis    (10,48) -> (4,45)  fresh  ", (10, 48), (4, 45), None),
        ("two axis    (10,48) -> (4,45)  STALLED", (10, 48), (4, 45), (10, 48)),
    ]
    for label, pos, berth, last in cases:
        d, tr = rtb_direction(pos, berth, last)
        print("  %s -> %s   [%s]" % (label, DIRN[d], tr))
    print("")
    print("  The two-axis case CHANGES direction when stalled (-x becomes -y); the")
    print("  pure-axis case does NOT. That is the defect.")


# ------------------------------------------------------------------- trace ----
def mode_trace(args):
    d = load(SEED_RUN)
    rows = d["uav_steps"]
    station = d["base_station"]
    cells = depot_cells(station)
    order = [str(r[0]) for r in rows[0]]
    berths = {uid: tuple(station["uav_berths"][i]) for i, uid in enumerate(order)}
    print("TRACE  dcB east/half/808   terminal_step=%s" % d.get("terminal_step"))
    print("  depot footprint x %d..%d  y %d..%d"
          % (min(c[0] for c in cells), max(c[0] for c in cells),
             min(c[1] for c in cells), max(c[1] for c in cells)))
    print("  berths: %s" % {u: berths[u] for u in order})
    print("  (4,44) inside depot: %s   <- the stall cell is OUTSIDE"
          % ((4, 44) in cells))
    print("")
    print("  recorded rtb_log:")
    for uid, log in (d.get("rtb_log") or {}).items():
        for t in log:
            fb = (t.get("dock_cell") is not None
                  and list(t["dock_cell"]) != list(t["target_berth"]))
            print("    %s trigger=%s target_berth=%s arrival=%s dock_cell=%s%s"
                  % (uid, t["trigger_step"], t["target_berth"], t["arrival_step"],
                     t["dock_cell"], "   <== FALLBACK DOCK" if fb else ""))
    print("")
    hdr = "  %-5s " % "frame"
    for uid in order:
        hdr += "| %-33s " % ("%s berth%s" % (uid, berths[uid]))
    print(hdr)
    prev = {}
    for fi in range(args.frm, min(args.to, len(rows))):
        line = "  %-5d " % fi
        for a, uid in enumerate(order):
            r = rows[fi][a]
            pos, sd, bat, bs = tuple(r[1]), r[3], r[4], r[5] or "-"
            tgt = (pos[0] + MOVE_X[sd], pos[1] + MOVE_Y[sd]) if sd is not None else None
            mv = "   " if uid not in prev else ("mv " if prev[uid] != pos else "BLK")
            line += "| %-8s %s->%-8s %s b%5.1f %-9s " % (
                pos, DIRN[sd], tgt, mv, bat, bs)
            prev[uid] = pos
        print(line)
    print("")
    print("  READ IT AT FRAME 202: 2501 steps INTO (3,46) - 2502's berth - in transit")
    print("  to its own berth (3,45), which it reaches at frame 203. It stands there")
    print("  for EXACTLY ONE FRAME. mesa's SimultaneousActivation advances agents in")
    print("  insertion order inside the advance() sweep, and 2501 precedes 2502, so")
    print("  2502 - already inside the depot at (4,45) - sees its berth occupied and")
    print("  takes the docking fallback, parking PERMANENTLY on (4,45), which is")
    print("  2500's berth. 2500 reaches (4,44) the same frame and from 203 onward")
    print("  re-picks the same blocked +y for the rest of the run.")
    print("")
    print("  AND NOTE FRAME 215 ONWARD: 2502 releases (base_state goes blank, the")
    print("  battery resumes draining at the no-move rate) but NEVER LEAVES (4,45),")
    print("  because it and 2503 are now head-on, each wanting the cell the other")
    print("  holds. The stolen berth is therefore not returned when charging ends.")


# ---------------------------------------------------------------- fallback ----
def _arm_runs(pattern="_ffr_dc*_*.json"):
    for p in sorted(glob.glob(os.path.join(HERE, pattern))):
        tag = os.path.basename(p).split("_")[2]
        try:
            yield tag, p, load(p)
        except Exception:
            continue


def mode_fallback(args):
    print("FALLBACK DOCKS  counted from EXISTING recorded fields only")
    print("  a fallback dock is        dock_cell != target_berth")
    print("  a trip that never ended is  arrival_step is None")
    print("")
    rows = collections.defaultdict(lambda: dict(runs=0, trips=0, fb=0, un=0, old=0))
    for tag, _p, d in _arm_runs(args.glob):
        if not (d.get("rtb_log") or {}):
            continue
        r = rows[tag]
        r["runs"] += 1
        for _uid, log in d["rtb_log"].items():
            for t in log:
                r["trips"] += 1
                # target_berth was added by the depot-cost round. An arm recorded
                # from a checkout that predates it cannot be classified, and is
                # counted separately rather than silently treated as no-fallback.
                if "target_berth" not in t:
                    r["old"] += 1
                elif t.get("arrival_step") is None:
                    r["un"] += 1
                elif list(t["dock_cell"]) != list(t["target_berth"]):
                    r["fb"] += 1
    print("  %-8s %5s %7s %16s %15s %14s"
          % ("arm", "runs", "trips", "fallback docks", "never arrived",
             "unclassifiable"))
    for tag in sorted(rows):
        r = rows[tag]
        print("  %-8s %5d %7d %16d %15d %14s"
              % (tag, r["runs"], r["trips"], r["fb"], r["un"],
                 (r["old"] or "-")))
    print("")
    print("  'unclassifiable' are trips recorded before target_berth existed")
    print("  (the pre-depot-round schema); they are excluded, not assumed clean.")


# --------------------------------------------------------------- occupancy ----
def mode_occupancy(_args):
    print("BERTH-OCCUPANCY EPISODES  one UAV standing on ANOTHER UAV's berth")
    print("  Measured over every recorded frame of every armed run.")
    print("  This is the evidence for the persistence threshold.")
    print("")
    epis = collections.Counter()
    states = collections.defaultdict(collections.Counter)
    longs = []
    for tag, p, d in _arm_runs(args.glob):
        station = d.get("base_station")
        rows = d.get("uav_steps") or []
        if not station or not rows:
            continue
        order = [str(r[0]) for r in rows[0]]
        berths = {uid: tuple(station["uav_berths"][i])
                  for i, uid in enumerate(order)
                  if i < len(station["uav_berths"])}
        open_ep = {}
        for fi, row in enumerate(rows):
            pos = {str(c[0]): tuple(c[1]) for c in row}
            bst = {str(c[0]): str(c[5] or "") for c in row}
            for uid, b in berths.items():
                occ = [o for o in pos if o != uid and pos[o] == b]
                if occ:
                    open_ep.setdefault((uid, occ[0]), (fi, bst.get(occ[0], "")))
                else:
                    for k in [k for k in open_ep if k[0] == uid]:
                        s, st = open_ep.pop(k)
                        epis[fi - s] += 1
                        states[fi - s][st or "(idle)"] += 1
                        if fi - s >= 5:
                            longs.append((fi - s, tag, os.path.basename(p), k, st))
        for k, (s, st) in open_ep.items():
            L = len(rows) - s
            epis[L] += 1
            states[L][(st or "(idle)") + " open-to-end"] += 1
            if L >= 5:
                longs.append((L, tag, os.path.basename(p), k, st + " open-to-end"))
    print("  %8s %10s   occupier base_state when the episode began"
          % ("length", "episodes"))
    for L in sorted(epis):
        print("  %8d %10d   %s" % (L, epis[L], dict(states[L])))
    short = sum(n for L, n in epis.items() if L <= 2)
    tot = sum(epis.values())
    print("")
    print("  episodes of 1-2 steps:   %d of %d (%.1f%%)  <- transits"
          % (short, tot, 100.0 * short / tot))
    print("  episodes of >= 14 steps: %d              <- genuine blocks"
          % sum(n for L, n in epis.items() if L >= 14))
    gap = [L for L in range(3, 14) if epis.get(L)]
    print("  lengths seen between 3 and 13: %s"
          % (gap or "NONE - the distribution is bimodal"))
    print("")
    print("  every episode of 5 steps or more:")
    for L, tag, fn, k, st in sorted(longs):
        print("    len=%-4d %-5s %-38s berth_of=%s occupied_by=%s state=%s"
              % (L, tag, fn, k[0], k[1], st or "(idle)"))


# ---------------------------------------------------------------- geometry ----
def mode_geometry(_args):
    d = load(SEED_RUN)
    st = d["base_station"]
    cells = depot_cells(st)
    print("GEOMETRY  dcB east/half/808")
    print("  origin=%s size=%s  footprint x %d..%d  y %d..%d"
          % (st["origin"], st["size"],
             min(c[0] for c in cells), max(c[0] for c in cells),
             min(c[1] for c in cells), max(c[1] for c in cells)))
    print("  uav_berths         = %s" % st["uav_berths"])
    print("  firefighter_berths = %s" % st["firefighter_berths"])
    print("")
    print("  Every UAV berth sits on the depot's y=45 boundary row. A UAV whose x")
    print("  already matches its berth therefore makes its FINAL APPROACH from")
    print("  (x,44) straight up the y axis - the pure-axis case - from a cell that")
    print("  is OUTSIDE the footprint and so cannot use the docking fallback:")
    for c in [(4, 45), (3, 45), (3, 46), (4, 46), (4, 44), (3, 44), (5, 45)]:
        print("    %-8s inside depot: %s" % (str(c), c in cells))


# ------------------------------------------------------------------ stalls ----
def mode_stalls(args):
    """Every episode in which a RETURNING UAV stands still for >= --run steps.

    Split by whether the UAV is inside its depot (where the docking fallback can
    still rescue it) or outside it (where nothing can), and by whether its
    approach to the berth is pure-axis (where the stall sidestep is a no-op) or
    two-axis (where it fires). OUTSIDE + pure-axis is the mechanism-2 hole, and
    it is the metric to re-measure after the fix.
    """
    print("RETURNING-UAV STALL EPISODES  >= %d consecutive steps without moving"
          % args.run)
    print("  'OUTSIDE' means outside the depot footprint, where the docking")
    print("  fallback cannot fire. 'pure-axis' means one delta to the berth is 0,")
    print("  where the stall sidestep cannot fire. OUTSIDE + pure-axis is the hole.")
    print("")
    res = collections.Counter()
    detail = []
    for tag, p, d in _arm_runs(args.glob):
        station = d.get("base_station")
        rows = d.get("uav_steps") or []
        if not station or not rows:
            continue
        cells = depot_cells(station)
        order = [str(r[0]) for r in rows[0]]
        berths = {u: tuple(station["uav_berths"][i]) for i, u in enumerate(order)
                  if i < len(station["uav_berths"])}
        for a, uid in enumerate(order):
            b = berths.get(uid)
            if not b:
                continue
            run = 0
            for fi in range(1, len(rows)):
                cur = tuple(rows[fi][a][1])
                prev = tuple(rows[fi - 1][a][1])
                if str(rows[fi][a][5] or "") != "returning" or cur != prev:
                    run = 0
                    continue
                run += 1
                if run != args.run:
                    continue
                dx, dy = b[0] - cur[0], b[1] - cur[1]
                where = "inside" if cur in cells else "OUTSIDE"
                axis = "pure-axis" if (dx == 0 or dy == 0) else "two-axis"
                res[(where, axis)] += 1
                if where == "OUTSIDE" and axis == "pure-axis":
                    n = run
                    for fj in range(fi + 1, len(rows)):
                        if (tuple(rows[fj][a][1]) != cur
                                or str(rows[fj][a][5] or "") != "returning"):
                            break
                        n += 1
                    detail.append((n, tag, os.path.basename(p), uid, cur, b))
    for k in sorted(res):
        print("  %-8s %-10s : %d" % (k[0], k[1], res[k]))
    print("")
    print("  OUTSIDE + pure-axis episodes - the mechanism-2 hole - by duration:")
    for n, tag, fn, uid, cur, b in sorted(detail, reverse=True):
        print("    len=%-4d %-5s %-38s uid=%s stalled_at=%s berth=%s"
              % (n, tag, fn, uid, str(cur), str(b)))
    if detail:
        print("")
        print("  The stall cell is always one row OUTSIDE the depot's boundary row.")
        print("  That is not a coincidence: _build_base_station ranks berths by")
        print("  DESCENDING distance from the grid edge (wildfire_model.py:645-648),")
        print("  so berths are handed out on the depot's interior-facing boundary -")
        print("  exactly where a final approach from the grid interior is pure-axis.")
        print("  An episode that ends before the horizon did so only because the")
        print("  blocker happened to move; it is the same defect either way.")


# ------------------------------------------------------------------ refusals ----
def mode_refusals(args):
    """Length of every run of CONSECUTIVE REFUSED STEPS on a return leg.

    This is what derives BASE_STATION_RETURN_STALL_LIMIT. It is the statistic the
    re-keyed terminator actually consults - "has this leg stopped moving" - as
    opposed to the berth-occupancy statistic in --mode occupancy, which is what a
    berth-debounce would consult. The separation here is cleaner.
    """
    print("CONSECUTIVE REFUSED STEPS on a return leg, every armed run")
    print("  A returning UAV whose position is unchanged from the previous frame")
    print("  had its move refused. These are the run lengths of that condition.")
    print("")
    runs = collections.Counter()
    if True:
        for tag, _p, d in _arm_runs(args.glob):
            rows = d.get("uav_steps") or []
            if not rows:
                continue
            for a in range(len(rows[0])):
                run = 0
                for fi in range(1, len(rows)):
                    cur = tuple(rows[fi][a][1])
                    prev = tuple(rows[fi - 1][a][1])
                    if str(rows[fi][a][5] or "") != "returning" or cur != prev:
                        if run:
                            runs[run] += 1
                        run = 0
                    else:
                        run += 1
                if run:
                    runs[run] += 1
    total = sum(runs.values()) or 1
    cum = 0
    for L in sorted(runs):
        cum += runs[L]
        print("  %3d steps : %5d   (cumulative %6.2f%%)"
              % (L, runs[L], 100.0 * cum / total))
    print("  total episodes: %d" % total)
    print("")
    gap = [L for L in range(3, 9) if runs.get(L)]
    print("  lengths seen between 3 and 8: %s"
          % (gap or "NONE - the distribution is bimodal"))
    for L in (2, 3, 4):
        ge = sum(n for k, n in runs.items() if k >= L)
        print("  episodes reaching >= %d consecutive refusals: %d (%.2f%%)"
              % (L, ge, 100.0 * ge / total))
    print("")
    print("  A one-step transit through a berth produces at most ONE refused step,")
    print("  so a limit of 3 cannot be reached by one.")
    long_ones = sorted(L for L in runs if L > 4)
    if long_ones:
        print("  Episodes longer than the limit: %s." % long_ones)
        print("  Each of those is a stall the UAV never recovers from on its own -")
        print("  the signature the fix exists to remove.")
    else:
        print("  NO EPISODE EXCEEDS 4 STEPS. Every stall is capped at the limit and")
        print("  then recovered, which is the fix working: the leg stalls, the")
        print("  counter reaches the threshold, and the recovery or the terminator")
        print("  fires instead of the UAV sitting there to the horizon.")


# ----------------------------------------------------------------- livelock ----
def _return_legs(rows, a):
    """Maximal runs of frames on which agent index `a` is 'returning'."""
    leg = []
    for fi in range(len(rows)):
        if str(rows[fi][a][5] or "") == "returning":
            leg.append(tuple(rows[fi][a][1]))
        elif leg:
            yield leg
            leg = []
    if leg:
        yield leg


def mode_livelock(args):
    """The gate a 'position unchanged for N steps' stall counter cannot provide.

    THIS IS THE THIRD TIME IN THIS CAMPAIGN A GATE HAS ASKED THE WRONG QUESTION.
    Seed 909 was counted as a latch when it was a horizon artifact; the old
    zero-battery stranding gate scored the dcB deadlock as 0 because the UAV ended
    with 35.4 battery in hand. Here: a UAV that MOVES every step while getting
    nowhere has an unchanged-position count of ZERO, so the positional stranding
    gate scores a livelock clean. The obvious minimal fix for the pure-axis hole
    does exactly that (outputs/_df_sandbox.py rule R1), which is why this is
    mandatory rather than optional.

    Three outcomes, counted per arm over every return leg:
      FREEZE       >= --run frames on ONE cell. What HEAD does; the existing gate
                   sees this and only this.
      CYCLE        the leg returns to a cell it had LEFT. Consecutive repeats are
                   collapsed first, because standing still while a stall counter
                   runs is not a cycle.
      OSCILLATION  a --win frame window inside a leg spent on at most 2 distinct
                   cells while changing cell at least twice - a moving UAV going
                   nowhere, which is the R1 signature specifically.
    """
    print("LIVELOCK GATE  freeze >= %d frames / cycle / oscillation in a %d-frame window"
          % (args.run, args.win))
    print("  A CYCLE or an OSCILLATION is invisible to the positional stranding")
    print("  gate, because the UAV keeps moving. At HEAD both are zero: the")
    print("  recorded failures are freezes. Any non-zero result is caused by a fix.")
    print("")
    print("  %-9s %5s %8s %8s %13s" % ("arm", "runs", "freezes", "cycles", "oscillations"))
    detail = []
    for tag in sorted({t for t, _p, _d in _arm_runs(args.glob)}):
        runs = freezes = cycles = oscill = 0
        for t2, p, d in _arm_runs(args.glob):
            if t2 != tag:
                continue
            rows = d.get("uav_steps") or []
            if not rows:
                continue
            runs += 1
            order = [str(r[0]) for r in rows[0]]
            for a, uid in enumerate(order):
                for leg in _return_legs(rows, a):
                    visited = [c for i, c in enumerate(leg)
                               if i == 0 or c != leg[i - 1]]
                    best = 1
                    cur = 1
                    for i in range(1, len(leg)):
                        cur = cur + 1 if leg[i] == leg[i - 1] else 1
                        best = max(best, cur)
                    if best >= args.run:
                        freezes += 1
                    if len(visited) != len(set(visited)):
                        cycles += 1
                        detail.append(("CYCLE", tag, os.path.basename(p), uid, leg))
                    for i in range(0, max(0, len(leg) - args.win + 1)):
                        window = leg[i:i + args.win]
                        moves = sum(1 for j in range(1, len(window))
                                    if window[j] != window[j - 1])
                        if len(set(window)) <= 2 and moves >= 2:
                            oscill += 1
                            detail.append(("OSCILLATION", tag,
                                           os.path.basename(p), uid, window))
                            break
        print("  %-9s %5d %8d %8d %13d" % (tag, runs, freezes, cycles, oscill))
    if detail:
        print("")
        print("  every cycle or oscillation found:")
        for kind, tag, fn, uid, leg in detail[:40]:
            print("    %-11s %-8s %-38s uid=%s %s"
                  % (kind, tag, fn, uid, leg[:12]))
        if len(detail) > 40:
            print("    ... and %d more" % (len(detail) - 40))
    else:
        print("")
        print("  no cycles and no oscillations.")


# ---------------------------------------------------------------- burnstreak ----
def mode_burnstreak(args):
    """Consecutive steps a UAV spends standing on a BURNING cell.

    The exposure SHARE (_dc_arms.py --mode exposure) is the headline number and
    is comparable across rounds, but it cannot distinguish a UAV that crosses
    many burning cells once each from one that sits on a single burning cell for
    twenty steps. The fix moves UAVs around near the depot, so the second case is
    the one worth seeing. UAVs are fire-immune - there is no casualty path for
    them - so this is a search-quality signal, not a survival one.

    Read from the per-UAV per-step `burning` flag the harness already records at
    uav_actions[i][2]. No new instrument.
    """
    print("BURNING-CELL STREAKS  consecutive steps a UAV stands on a burning cell")
    print("  %-9s %5s %9s %9s %9s" % ("arm", "runs", "max", ">=3", ">=5"))
    for tag in sorted({t for t, _p, _d in _arm_runs(args.glob)}):
        runs = worst = ge3 = ge5 = 0
        for t2, _p, d in _arm_runs(args.glob):
            if t2 != tag:
                continue
            acts = d.get("uav_actions") or []
            if not acts:
                continue
            runs += 1
            order = [str(r[0]) for r in acts[0]]
            for a in range(len(order)):
                streak = 0
                for fi in range(len(acts)):
                    row = acts[fi]
                    if a >= len(row):
                        continue
                    burning = len(row[a]) > 2 and row[a][2]
                    if burning:
                        streak += 1
                        worst = max(worst, streak)
                    else:
                        if streak >= 3:
                            ge3 += 1
                        if streak >= 5:
                            ge5 += 1
                        streak = 0
                if streak >= 3:
                    ge3 += 1
                if streak >= 5:
                    ge5 += 1
        if runs:
            print("  %-9s %5d %9d %9d %9d" % (tag, runs, worst, ge3, ge5))


MODES = {"trace": mode_trace, "steer": mode_steer, "fallback": mode_fallback,
         "occupancy": mode_occupancy, "geometry": mode_geometry,
         "stalls": mode_stalls, "refusals": mode_refusals,
         "livelock": mode_livelock, "burnstreak": mode_burnstreak}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=sorted(MODES) + ["all"])
    ap.add_argument("--frm", type=int, default=198)
    ap.add_argument("--to", type=int, default=225)
    ap.add_argument("--run", type=int, default=3,
                    help="stall length, in steps, that counts as an episode")
    ap.add_argument("--glob", default="_ffr_dc*_*.json",
                    help="which arms to read; '_ffr_bsret_*.json' is the mode-2 arm")
    ap.add_argument("--win", type=int, default=10,
                    help="window, in frames, for the oscillation test")
    args = ap.parse_args()
    names = sorted(MODES) if args.mode == "all" else [args.mode]
    for i, n in enumerate(names):
        if i:
            print("")
            print("=" * 78)
            print("")
        MODES[n](args)


if __name__ == "__main__":
    main()
