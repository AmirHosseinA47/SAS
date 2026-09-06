"""Lateral-when-pinned round: measure, classify and bound BEFORE any source edit.

Reads the extended _ffr_harness.py records (victim_holds recorded at the hold
decision itself, burn_intervals = the full per-cell burning history) and:

  A  reproduces the hold counters from the per-hold records (must equal the
     source's own counters exactly) and states the anchor-independent count
  B  classifies every lateral-available hold: how close the fire was, when the
     held cell actually ignited, whether the lateral cell the rule would have
     taken ignited later, and whether an omniscient walker could still have
     survived from there (time-expanded backward reachability over the recorded
     fire history)
  C  splits the holds by the fate of the victim that held - the ceiling
  D  replays the victim flee rule OFFLINE against the recorded fire history.
     Victims are inert to fire, so the fire history is the same under any
     victim rule; the replay of the CURRENT rule must reproduce the recorded
     trajectories exactly (validated), after which lateral variants are
     replayed on the same history to bound what each could change for the
     victims that died. Rescue is not modelled, so this is fire-only.

usage:
  _lat_analyze.py --base latbase
  _lat_analyze.py --base latbase --ctrl latoff     # part 3: kill-switch identity
  _lat_analyze.py --base latbase --feat latfeat    # part 3: seed-matched comparison
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
from collections import deque

BASE = os.path.dirname(os.path.abspath(__file__))
COMBOS = (
    [("east", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("east", "default", s) for s in (101, 202, 303)]
)
OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1))
TRIGGER = 3
LEASH = 6
METRICS = ("rescued", "dead", "unreachable", "never_detected", "geographically_isolated",
           "firefighter_deaths", "terminal_step")


def _name(tag, wind, roles, seed):
    rr = "def" if roles == "default" else roles
    return os.path.join(BASE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def load(tag):
    runs = {}
    for wind, roles, seed in COMBOS:
        p = _name(tag, wind, roles, seed)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            print("  MISSING %s" % p)
            continue
        with open(p, encoding="utf-8") as f:
            runs[(wind, roles, seed)] = json.load(f)
    return runs


def label(k):
    return "D/%s/%s %d" % (k[0], k[1], k[2])


def rule(title):
    print("\n" + "=" * 84)
    print(title)
    print("=" * 84)


def tup(c):
    return None if c is None else (int(c[0]), int(c[1]))


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# ----------------------------------------------------------------------------
# fire history
# ----------------------------------------------------------------------------
class FireHistory:
    """Burning set per step from the harness burn_intervals, plus derived fields."""

    def __init__(self, run):
        self.T = int(run["steps"])
        keys = list(run["fire_ground_final"].keys())
        xs = [int(k.split(",")[0]) for k in keys]
        ys = [int(k.split(",")[1]) for k in keys]
        self.W = max(xs) + 1
        self.H = max(ys) + 1
        self.burning = [set() for _ in range(self.T + 2)]
        for key, ivs in run["burn_intervals"].items():
            x, y = (int(v) for v in key.split(","))
            for a, b in ivs:
                end = self.T + 1 if b is None else int(b)
                for s in range(int(a), min(end, self.T + 1)):
                    self.burning[s].add((x, y))
        self._dist = {}
        self._S = None

    def in_bounds(self, c):
        return 0 <= c[0] < self.W and 0 <= c[1] < self.H

    def dist_field(self, t):
        if t in self._dist:
            return self._dist[t]
        fire = self.burning[t]
        if not fire:
            self._dist[t] = None
            return None
        field = {}
        dq = deque()
        for c in fire:
            field[c] = 0
            dq.append(c)
        while dq:
            c = dq.popleft()
            d = field[c]
            for ox, oy in OFFSETS:
                n = (c[0] + ox, c[1] + oy)
                if not self.in_bounds(n) or n in field:
                    continue
                field[n] = d + 1
                dq.append(n)
        self._dist[t] = field
        return field

    def dist(self, c, t):
        f = self.dist_field(t)
        return 999 if f is None else f.get(c, 999)

    def first_ignition_from(self, c, t):
        for s in range(t, self.T + 1):
            if c in self.burning[s]:
                return s
        return None

    def survivable(self):
        """S[t] = cells from which a 1-cell/step 4-connected walker that is alive
        (on a non-burning cell) at step t can stay alive through step T, given
        the recorded fire history. Backward dynamic programme; rescue and the
        leash are not modelled, so membership is an UPPER bound on what any
        victim movement rule could achieve from that cell at that step."""
        if self._S is not None:
            return self._S
        T = self.T
        cells = [(x, y) for x in range(self.W) for y in range(self.H)]
        S = [None] * (T + 2)
        S[T] = set(c for c in cells if c not in self.burning[T])
        for t in range(T - 1, 0, -1):
            nxt = S[t + 1]
            fire = self.burning[t]
            cur = set()
            for c in cells:
                if c in fire:
                    continue
                if c in nxt:
                    cur.add(c)
                    continue
                for ox, oy in OFFSETS:
                    if (c[0] + ox, c[1] + oy) in nxt:
                        cur.add(c)
                        break
            S[t] = cur
        self._S = S
        return S


# ----------------------------------------------------------------------------
# victim facts from the per-step record
# ----------------------------------------------------------------------------
def victim_facts(run):
    facts = {}
    for vid, spawn in run["victim_spawns"].items():
        facts[str(vid)] = {"spawn": tup(spawn), "pos": {}, "status": {}, "death_step": None,
                           "death_cell": None, "rescue_step": None, "custody_step": None,
                           "final": None}
    for i, row in enumerate(run["victim_steps"]):
        t = i + 1
        for vid, cell, status in row:
            f = facts.setdefault(str(vid), {"spawn": None, "pos": {}, "status": {}, "death_step": None,
                                            "death_cell": None, "rescue_step": None,
                                            "custody_step": None, "final": None})
            f["pos"][t] = tup(cell)
            f["status"][t] = status
            f["final"] = status
            if status == "dead" and f["death_step"] is None:
                f["death_step"] = t
                f["death_cell"] = tup(cell)
            if status == "rescued" and f["rescue_step"] is None:
                f["rescue_step"] = t
    # custody: first step at which a live firefighter stood on the victim's cell,
    # or the exit_start for that victim, whichever is earlier. After that the
    # victim's own rule is suppressed (G4) and its position is the carrier's.
    for i, row in enumerate(run["ff_steps"]):
        t = i + 1
        for ff, pos, status, assigned, exiting, dead in row:
            if dead or pos is None:
                continue
            for vid, f in facts.items():
                if f["pos"].get(t) == tup(pos) and f["status"].get(t) not in ("dead", "rescued"):
                    if f["custody_step"] is None or t < f["custody_step"]:
                        f["custody_step"] = t
    for e in run.get("exit_starts", []):
        f = facts.get(str(e.get("victim")))
        if f is not None and (f["custody_step"] is None or int(e["step"]) < f["custody_step"]):
            f["custody_step"] = int(e["step"])
    return facts


# ----------------------------------------------------------------------------
# offline replay of the victim rule
# ----------------------------------------------------------------------------
def replay(fh, spawn, variant, stop_step=None):
    """Replay one victim from `spawn` against the fire history.

    variant = {"mode": "base"|"a"|"b"|"c", "pressed": int, "antiosc": "none"|"lastlat"|"lastcell",
               "budget": int|None}
      base    R6 strict improvement (the rule at dd0a1b9)
      a       also take an equal-distance step when no strictly better one exists
      b       as a, only when d0 <= pressed
      c       as a, only when the lateral cell has more free neighbours than the current cell
      antiosc lastlat  = the cell the victim last LEFT BY A LATERAL move is not a lateral candidate
              lastcell = the cell the victim last left by ANY move is not a lateral candidate
      budget  max consecutive lateral moves before a forced hold (None = unbounded)
    Returns trajectory and mechanism counts. Rescue/custody are not modelled.
    """
    mode = variant.get("mode", "base")
    pressed = int(variant.get("pressed", TRIGGER))
    antiosc = variant.get("antiosc", "none")
    budget = variant.get("budget")
    pos = spawn
    anchor = spawn
    last_cell = None
    last_lat_from = None
    consec_lat = 0
    traj = {0: pos}
    moves = []
    lateral_moves = []
    holds = collections.Counter()
    leash_hits = 0
    reanchors = 0
    dead_step = None
    T = fh.T if stop_step is None else min(fh.T, stop_step)
    for t in range(1, T + 1):
        fire = fh.burning[t]
        if not fire:
            if anchor != pos:
                anchor = pos
                reanchors += 1
            traj[t] = pos
            continue
        d0 = fh.dist(pos, t)
        if d0 > TRIGGER:
            if anchor != pos:
                anchor = pos
                reanchors += 1
            traj[t] = pos
            continue
        cands = []
        leash_blocked = 0
        for order, (ox, oy) in enumerate(OFFSETS):
            n = (pos[0] + ox, pos[1] + oy)
            if not fh.in_bounds(n):
                continue
            if n in fire:
                continue
            fa = manhattan(n, anchor)
            if fa > LEASH:
                leash_blocked += 1
                continue
            has_exit = False
            for ox2, oy2 in OFFSETS:
                onward = (n[0] + ox2, n[1] + oy2)
                if onward == pos or not fh.in_bounds(onward) or onward in fire:
                    continue
                has_exit = True
                break
            cands.append((fh.dist(n, t), fa, order, n, has_exit))
        if leash_blocked:
            leash_hits += 1
        target = None
        strict = False
        if not cands:
            holds["no_candidate"] += 1
        else:
            with_exit = [c for c in cands if c[4]]
            pool = with_exit if with_exit else cands
            best = min(pool, key=lambda c: (-c[0], c[1], c[2]))
            if best[0] > d0:
                target = best[3]
                strict = True
            else:
                lat = [c for c in pool if c[0] == d0]
                allowed = mode != "base" and bool(lat)
                if allowed and mode == "b":
                    allowed = d0 <= pressed
                if allowed and budget is not None and consec_lat >= budget:
                    allowed = False
                if allowed:
                    if antiosc == "lastlat":
                        lat = [c for c in lat if c[3] != last_lat_from]
                    elif antiosc == "lastcell":
                        lat = [c for c in lat if c[3] != last_cell]
                    if mode == "c":
                        def free_nb(cell):
                            return sum(1 for ox, oy in OFFSETS
                                       if fh.in_bounds((cell[0] + ox, cell[1] + oy))
                                       and (cell[0] + ox, cell[1] + oy) not in fire)
                        here = free_nb(pos)
                        lat = [c for c in lat if free_nb(c[3]) > here]
                    if lat:
                        target = min(lat, key=lambda c: (c[1], c[2]))[3]
                if target is None:
                    holds["no_improvement"] += 1
                    holds["no_improvement.lateral_available"] += int(bool([c for c in pool if c[0] == d0]))
        if target is not None:
            moves.append((t, pos, target, d0, fh.dist(target, t), strict))
            if strict:
                consec_lat = 0
            else:
                lateral_moves.append((t, pos, target, d0))
                last_lat_from = pos
                consec_lat += 1
            last_cell = pos
            pos = target
        if pos in fire:
            dead_step = t
            traj[t] = pos
            break
        traj[t] = pos
    return {"traj": traj, "moves": moves, "lateral_moves": lateral_moves, "holds": holds,
            "leash_hits": leash_hits, "reanchors": reanchors, "dead_step": dead_step,
            "final_pos": pos, "max_disp": max(manhattan(p, spawn) for p in traj.values())}


def oscillation(traj_by_step, window=6):
    """From a step->cell trajectory: moves, reversals (a move INTO a cell the
    victim occupied within the previous `window` steps and has since left),
    immediate ping-pongs (return to the cell left one move ago) and the longest
    run of consecutive moves alternating between two cells."""
    steps = sorted(traj_by_step)
    moves = []
    for a, b in zip(steps, steps[1:]):
        if traj_by_step[a] is not None and traj_by_step[b] is not None and traj_by_step[a] != traj_by_step[b]:
            moves.append((b, traj_by_step[a], traj_by_step[b]))
    reversals = 0
    pingpong = 0
    for i, (t, frm, to) in enumerate(moves):
        recent = [traj_by_step.get(s) for s in range(max(1, t - window), t - 1)]
        if to in recent:
            reversals += 1
        if i > 0 and moves[i - 1][1] == to:
            pingpong += 1
    longest = 0
    run = 0
    for i in range(1, len(moves)):
        if moves[i][2] == moves[i - 1][1] and moves[i][0] == moves[i - 1][0] + 1:
            run = run + 1 if run else 2
            longest = max(longest, run)
        else:
            run = 0
    return {"moves": len(moves), "reversals": reversals, "pingpong": pingpong, "longest_alt_run": longest}


# ----------------------------------------------------------------------------
# sections
# ----------------------------------------------------------------------------
def section_a(runs):
    rule("A. HOLD COUNTERS - reproduced from the per-hold records taken AT the decision")
    tot = collections.Counter()
    rec = collections.Counter()
    mismatch = 0
    ai = 0
    ai_runs = collections.Counter()
    for k in COMBOS:
        r = runs.get(k)
        if r is None:
            continue
        tot.update(r.get("victim_flee_hold_counts", {}))
        mismatch += int(r.get("victim_hold_flag_mismatch", 0) or 0)
        for h in r.get("victim_holds", []):
            if "error" in h:
                rec["ERROR"] += 1
                continue
            rec[h["reason"]] += 1
            for fl, v in h.get("flags", {}).items():
                if v:
                    rec["%s.%s" % (h["reason"], fl)] += 1
            if h["reason"] == "no_improvement" and h["flags"].get("lateral_available") and not h["flags"].get("leash_removed"):
                ai += 1
                ai_runs[k] += 1
    print("  %-40s %8s %8s" % ("counter", "source", "records"))
    for key in sorted(set(tot) | set(rec)):
        print("  %-40s %8d %8d %s" % (key, tot.get(key, 0), rec.get(key, 0), "" if tot.get(key, 0) == rec.get(key, 0) else "<-- MISMATCH"))
    print("  recomputed-vs-source lateral flag mismatches: %d" % mismatch)
    print("  Feature 2 report section 11 figures: 231 / 175 / 17")
    print("  ANCHOR-INDEPENDENT holds (no_improvement & lateral_available & NOT leash_removed): %d" % ai)
    print("  runs with anchor-independent holds: %d of %d" % (len(ai_runs), len(runs)))
    for k in COMBOS:
        if ai_runs.get(k):
            print("    %-24s %d" % (label(k), ai_runs[k]))
    return ai


def section_b_c(runs):
    rule("B. CLASSIFICATION of every lateral-available hold (anchor-independent unless marked)")
    dist_hist = collections.Counter()
    tti_hist = collections.Counter()      # time to ignition of the held cell
    lat_delta = collections.Counter()     # ignition(lateral) - ignition(held)
    surv = collections.Counter()
    fate_holds = collections.Counter()
    fate_victims = collections.Counter()
    per_victim = {}
    all_rows = []
    for k in COMBOS:
        r = runs.get(k)
        if r is None:
            continue
        fh = FireHistory(r)
        S = fh.survivable()
        facts = victim_facts(r)
        for h in r.get("victim_holds", []):
            if "error" in h or h["reason"] != "no_improvement" or not h["flags"].get("lateral_available"):
                continue
            leash_involved = bool(h["flags"].get("leash_removed"))
            t = int(h["step"])
            vid = str(h["victim"])
            cell = tup(h["cell"])
            lat = tup(h["best_lateral"])
            d0 = int(h["dist_before"])
            f = facts.get(vid, {})
            ign_c = fh.first_ignition_from(cell, t)
            ign_l = fh.first_ignition_from(lat, t) if lat is not None else None
            in_S_c = cell in S[t]
            in_S_l = (lat in S[t + 1]) if (lat is not None and t + 1 <= fh.T) else False
            fate = f.get("final")
            death = f.get("death_step")
            row = {"run": k, "vid": vid, "step": t, "cell": cell, "d0": d0, "lat": lat,
                   "ign_c": ign_c, "ign_l": ign_l, "S_c": in_S_c, "S_l": in_S_l,
                   "fate": fate, "death_step": death, "leash": leash_involved,
                   "custody": f.get("custody_step")}
            all_rows.append(row)
            if leash_involved:
                continue
            dist_hist[d0] += 1
            tti = None if ign_c is None else ign_c - t
            tti_hist["never" if tti is None else ("<=3" if tti <= 3 else ("4-10" if tti <= 10 else ">10"))] += 1
            if ign_c is None and ign_l is None:
                lat_delta["neither cell ever ignites"] += 1
            elif ign_c is None:
                lat_delta["held cell never ignites, lateral does (worse)"] += 1
            elif ign_l is None:
                lat_delta["lateral never ignites, held does (better)"] += 1
            else:
                dd = ign_l - ign_c
                lat_delta["lateral ignites LATER by %s" % ("1-3" if 0 < dd <= 3 else ">3") if dd > 0 else
                          ("same step" if dd == 0 else "lateral ignites EARLIER")] += 1
            surv[("held cell survivable" if in_S_c else "held cell doomed",
                  "lateral cell survivable" if in_S_l else "lateral cell doomed")] += 1
            fate_holds[fate] += 1
            pv = per_victim.setdefault((k, vid), {"fate": fate, "death_step": death, "holds": [],
                                                  "custody": f.get("custody_step")})
            pv["holds"].append(row)
    print("  fire distance at the hold (d0):        " + "  ".join("d=%d: %d" % (d, n) for d, n in sorted(dist_hist.items())))
    print("  steps until the HELD cell ignited:     " + "  ".join("%s: %d" % (a, n) for a, n in sorted(tti_hist.items())))
    print("  the lateral cell the rule would take, relative to the held cell:")
    for key, n in sorted(lat_delta.items(), key=lambda x: -x[1]):
        print("    %-52s %4d" % (key, n))
    print("  omniscient survivability at the hold (upper bound on ANY movement rule):")
    for key, n in sorted(surv.items()):
        print("    %-28s / %-28s %4d" % (key[0], key[1], n))

    rule("C. FATE of the victims that held - the ceiling")
    for fate, n in sorted(fate_holds.items(), key=lambda x: -x[1]):
        print("  anchor-independent holds by victims that ended %-12s %4d" % (str(fate), n))
    for (k, vid), pv in per_victim.items():
        fate_victims[pv["fate"]] += 1
    print("  distinct victims with >= 1 anchor-independent hold, by fate: %s" % dict(fate_victims))
    total_dead = collections.Counter()
    dead_with_hold = []
    for k in COMBOS:
        r = runs.get(k)
        if r is None:
            continue
        facts = victim_facts(r)
        for vid, f in facts.items():
            if f["final"] == "dead":
                total_dead[k] += 1
    print("  victims dead in this arm: %d" % sum(total_dead.values()))
    print("\n  DEAD victims with anchor-independent holds (one line each):")
    print("  %-22s %-9s %5s %5s %6s %6s %5s %-14s %s" % ("combo", "victim", "holds", "death", "last", "S_c", "S_l", "custody", "hold steps (d0)"))
    ceiling = 0
    for (k, vid), pv in sorted(per_victim.items(), key=lambda x: (COMBOS.index(x[0][0]), x[0][1])):
        if pv["fate"] != "dead":
            continue
        hs = pv["holds"]
        any_sc = any(h["S_c"] for h in hs)
        any_sl = any(h["S_l"] for h in hs)
        if any_sl:
            ceiling += 1
        dead_with_hold.append((k, vid))
        print("  %-22s %-9s %5d %5s %6s %6s %5s %-14s %s" % (
            label(k), vid, len(hs), pv["death_step"], max(h["step"] for h in hs),
            "yes" if any_sc else "no", "yes" if any_sl else "no",
            str(pv["custody"]),
            " ".join("%d(%d)" % (h["step"], h["d0"]) for h in hs[:14]) + (" ..." if len(hs) > 14 else "")))
    print("\n  CEILING: dead victims with at least one anchor-independent hold whose lateral cell was")
    print("  still omnisciently survivable: %d of %d deaths (%d dead victims held at all)" % (
        ceiling, sum(total_dead.values()), len(dead_with_hold)))
    return all_rows, per_victim


def section_d(runs):
    rule("D. OFFLINE REPLAY of the victim rule against the recorded fire history")
    print("  D.1 validation: the CURRENT rule replayed must reproduce every recorded position")
    print("      up to custody / rescue / death (positions after that belong to the carrier).")
    ok_steps = bad = 0
    bad_examples = []
    victims_checked = 0
    deaths_reproduced = 0
    deaths_total = 0
    for k in COMBOS:
        r = runs.get(k)
        if r is None:
            continue
        fh = FireHistory(r)
        facts = victim_facts(r)
        for vid, f in sorted(facts.items()):
            if f["spawn"] is None:
                continue
            limit = min(x for x in (f["custody_step"], f["rescue_step"], f["death_step"], fh.T) if x is not None)
            rp = replay(fh, f["spawn"], {"mode": "base"}, stop_step=limit)
            victims_checked += 1
            for t in range(1, limit + 1):
                rec_pos = f["pos"].get(t)
                rp_pos = rp["traj"].get(t)
                if rec_pos is None and rp_pos is None:
                    continue
                if rec_pos == rp_pos:
                    ok_steps += 1
                else:
                    bad += 1
                    if len(bad_examples) < 6:
                        bad_examples.append((label(k), vid, t, rec_pos, rp_pos, f["custody_step"]))
                    break
            if f["death_step"] is not None and (f["custody_step"] is None or f["custody_step"] > f["death_step"]):
                deaths_total += 1
                if rp["dead_step"] == f["death_step"]:
                    deaths_reproduced += 1
    print("      victims replayed %d, position-steps matched %d, first-mismatch victims %d" % (victims_checked, ok_steps, bad))
    print("      deaths outside custody reproduced at the same step: %d of %d" % (deaths_reproduced, deaths_total))
    for ex in bad_examples:
        print("      MISMATCH %s %s step %d recorded %s replay %s (custody %s)" % ex)

    print("\n  D.2 variants, fire-only, for the victims that DIED outside custody in this arm")
    print("      (a = lateral always, b = lateral only when d0 <= P, c = shape-aware; antiosc = none | lastlat | lastcell;")
    print("       K = consecutive-lateral budget). survive = alive at the horizon in the replay.")
    variants = [
        ("base                       ", {"mode": "base"}),
        ("a  none                    ", {"mode": "a", "antiosc": "none"}),
        ("a  lastlat                 ", {"mode": "a", "antiosc": "lastlat"}),
        ("a  lastcell                ", {"mode": "a", "antiosc": "lastcell"}),
        ("a  lastlat  K=6            ", {"mode": "a", "antiosc": "lastlat", "budget": 6}),
        ("b  P=1 lastlat             ", {"mode": "b", "pressed": 1, "antiosc": "lastlat"}),
        ("b  P=2 lastlat             ", {"mode": "b", "pressed": 2, "antiosc": "lastlat"}),
        ("c  lastlat                 ", {"mode": "c", "antiosc": "lastlat"}),
        ("c  none                    ", {"mode": "c", "antiosc": "none"}),
    ]
    dead_victims = []
    alive_victims = []
    for k in COMBOS:
        r = runs.get(k)
        if r is None:
            continue
        fh = FireHistory(r)
        facts = victim_facts(r)
        for vid, f in sorted(facts.items()):
            if f["spawn"] is None:
                continue
            if f["final"] == "dead" and (f["custody_step"] is None or f["custody_step"] > f["death_step"]):
                dead_victims.append((k, vid, fh, f))
            elif f["final"] != "dead":
                alive_victims.append((k, vid, fh, f))
    print("      dead-outside-custody victims: %d; other victims: %d" % (len(dead_victims), len(alive_victims)))
    print("  %-28s %7s %8s %7s %8s %8s %7s %7s %8s %8s" % ("variant", "survive", "diedlate", "same", "latmoves", "revers", "pingp", "longest", "maxdisp", "caused"))
    detail = {}
    for name, var in variants:
        survive = later = same = lat = rev = pp = longest = 0
        maxdisp = 0
        caused = 0
        rows = []
        for k, vid, fh, f in dead_victims:
            rp = replay(fh, f["spawn"], var)
            osc = oscillation(rp["traj"])
            lat += len(rp["lateral_moves"])
            rev += osc["reversals"]
            pp += osc["pingpong"]
            longest = max(longest, osc["longest_alt_run"])
            maxdisp = max(maxdisp, rp["max_disp"])
            if rp["dead_step"] is None:
                survive += 1
                rows.append((label(k), vid, "SURVIVES", f["death_step"], None, len(rp["lateral_moves"]), rp["max_disp"]))
            elif rp["dead_step"] > f["death_step"]:
                later += 1
                rows.append((label(k), vid, "dies later", f["death_step"], rp["dead_step"], len(rp["lateral_moves"]), rp["max_disp"]))
            else:
                same += 1
        for k, vid, fh, f in alive_victims:
            limit = min(x for x in (f["custody_step"], f["rescue_step"], fh.T) if x is not None)
            rp = replay(fh, f["spawn"], var, stop_step=limit)
            if rp["dead_step"] is not None:
                caused += 1
        detail[name] = rows
        print("  %-28s %7d %8d %7d %8d %8d %7d %7d %8d %8d" % (name, survive, later, same, lat, rev, pp, longest, maxdisp, caused))
    print("\n  per-victim outcome under the variants that change anything:")
    for name, rows in detail.items():
        if not rows:
            continue
        print("  -- %s" % name.strip())
        for row in rows:
            print("     %-22s %-9s %-10s baseline death %s -> replay death %s  lateral moves %d  max displacement %d" % row)
    return dead_victims


# ----------------------------------------------------------------------------
# part 3 comparisons
# ----------------------------------------------------------------------------
def identity(base, ctrl, name):
    rule("KILL-SWITCH IDENTITY: %s vs baseline, every recorded field" % name)
    ok = 0
    for k in COMBOS:
        b, c = base.get(k), ctrl.get(k)
        if b is None or c is None:
            print("  %-24s MISSING" % label(k))
            continue
        checks = {
            "eval": b["eval"] == c["eval"],
            "stdout_sha256": b["stdout_sha256"] == c["stdout_sha256"],
            "fire_digests": b["fire_digests"] == c["fire_digests"],
            "victim_steps": b["victim_steps"] == c["victim_steps"],
            "ff_steps": b["ff_steps"] == c["ff_steps"],
            "hold_counts": b.get("victim_flee_hold_counts") == c.get("victim_flee_hold_counts"),
            "flee_log": b.get("victim_flee_log") == c.get("victim_flee_log"),
            "terminal_step": b.get("terminal_step") == c.get("terminal_step"),
        }
        good = all(checks.values())
        ok += int(good)
        print("  %-24s %s %s" % (label(k), "IDENTICAL" if good else "DIFFERS", "" if good else str([n for n, v in checks.items() if not v])))
    print("  identical runs: %d / %d" % (ok, len(COMBOS)))
    return ok


def fire_identity(base, feat, name):
    rule("FIRE MAP IDENTITY every step: %s vs baseline" % name)
    ok = 0
    for k in COMBOS:
        b, f = base.get(k), feat.get(k)
        if b is None or f is None:
            continue
        same = b["fire_digests"] == f["fire_digests"]
        ok += int(same)
        if not same:
            first = next((i + 1 for i, (x, y) in enumerate(zip(b["fire_digests"], f["fire_digests"])) if x != y), None)
            print("  %-24s DIFFERS first at step %s" % (label(k), first))
    print("  fire map identical on all %d steps: %d / %d runs" % (len(next(iter(base.values()))["fire_digests"]), ok, len(COMBOS)))
    return ok


def metrics(base, feat, name):
    rule("SEED-MATCHED METRICS: baseline -> %s" % name)
    print("  %-22s %-14s %-12s %-12s %-12s %-14s" % ("combo", "rescued", "dead", "ff_deaths", "nvdet", "terminal"))
    tot = collections.Counter()
    for k in COMBOS:
        b, f = base.get(k), feat.get(k)
        if b is None or f is None:
            continue
        be, fe = b["eval"], f["eval"]
        cells = []
        for m in ("rescued", "dead", "firefighter_deaths", "never_detected"):
            cells.append("%2d -> %2d%s" % (be[m], fe[m], (" (%+d)" % (fe[m] - be[m])) if fe[m] != be[m] else "     "))
            tot["b_" + m] += be[m]
            tot["f_" + m] += fe[m]
        cells.append("%4s -> %4s" % (be.get("terminal_step"), fe.get("terminal_step")))
        print("  %-22s %-14s %-12s %-12s %-12s %-14s" % (label(k), *cells))
    print("  TOTAL rescued %d -> %d | dead %d -> %d | ff_deaths %d -> %d | never_detected %d -> %d" % (
        tot["b_rescued"], tot["f_rescued"], tot["b_dead"], tot["f_dead"],
        tot["b_firefighter_deaths"], tot["f_firefighter_deaths"], tot["b_never_detected"], tot["f_never_detected"]))
    return tot


def deaths_split(base, feat, name):
    rule("DEATHS SPLIT: baseline deaths -> %s (prevented / relocated / unchanged / caused)" % name)
    prevented = relocated = unchanged = caused = 0
    rows = []
    for k in COMBOS:
        b, f = base.get(k), feat.get(k)
        if b is None or f is None:
            continue
        bf, ff = victim_facts(b), victim_facts(f)
        flat = collections.defaultdict(int)
        for e in f.get("victim_lateral_log", []):
            flat[str(e.get("victim_id"))] += 1
        for vid in sorted(set(bf) | set(ff)):
            bv, fv = bf.get(vid), ff.get(vid)
            if bv is None or fv is None:
                continue
            bd, fd = bv["final"] == "dead", fv["final"] == "dead"
            if bd and not fd:
                prevented += 1
                rows.append((label(k), vid, "PREVENTED", bv["death_step"], "%s at horizon" % fv["final"], flat[vid]))
            elif bd and fd:
                if bv["death_step"] == fv["death_step"] and bv["death_cell"] == fv["death_cell"]:
                    unchanged += 1
                else:
                    relocated += 1
                    rows.append((label(k), vid, "RELOCATED", bv["death_step"], "dies step %s at %s (baseline %s)" % (fv["death_step"], fv["death_cell"], bv["death_cell"]), flat[vid]))
            elif fd and not bd:
                caused += 1
                rows.append((label(k), vid, "CAUSED", "%s at horizon" % bv["final"], "dies step %s" % fv["death_step"], flat[vid]))
    print("  prevented %d | relocated %d | unchanged %d | caused %d" % (prevented, relocated, unchanged, caused))
    print("  (Feature 2 against its own baseline: 12 prevented / 11 relocated / 0 unchanged / 1 caused)")
    for row in rows:
        print("    %-22s %-9s %-10s baseline %-18s feature %-45s lateral moves %d" % row)
    return prevented, relocated, unchanged, caused


def oscillation_report(runs, name):
    rule("OSCILLATION, measured from trajectories: %s" % name)
    tot = collections.Counter()
    longest = 0
    longest_where = None
    lat_total = 0
    lat_counts = collections.Counter()
    disp = []
    leash_hits = 0
    for k in COMBOS:
        r = runs.get(k)
        if r is None:
            continue
        facts = victim_facts(r)
        for vid, f in facts.items():
            traj = {t: p for t, p in f["pos"].items() if p is not None and f["status"].get(t) not in ("rescued",)}
            limit = f["custody_step"]
            if limit is not None:
                traj = {t: p for t, p in traj.items() if t < limit}
            if f["spawn"] is not None:
                traj[0] = f["spawn"]
            osc = oscillation(traj)
            for key in ("moves", "reversals", "pingpong"):
                tot[key] += osc[key]
            if osc["longest_alt_run"] > longest:
                longest = osc["longest_alt_run"]
                longest_where = (label(k), vid)
            if f["spawn"] is not None and traj:
                disp.append(max(manhattan(p, f["spawn"]) for p in traj.values()))
        lat_total += len(r.get("victim_lateral_log", []))
        lat_counts.update(r.get("victim_lateral_counts", {}))
        for h in r.get("victim_holds", []):
            if "error" not in h and h.get("n_leash_blocked", 0) > 0:
                leash_hits += 1
    print("  victim moves (own power, pre-custody) %d | reversals within 6 steps %d | immediate ping-pongs %d" % (tot["moves"], tot["reversals"], tot["pingpong"]))
    print("  longest run of consecutive alternation between two cells: %d moves %s" % (longest, longest_where or ""))
    print("  lateral moves logged by the source: %d  counters: %s" % (lat_total, dict(lat_counts)))
    if disp:
        print("  max displacement from spawn per victim: n=%d median %s max %d; victims reaching >= 6: %d" % (
            len(disp), statistics.median(disp), max(disp), sum(1 for d in disp if d >= 6)))
    print("  hold decisions where the leash removed a candidate: %d" % leash_hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--ctrl")
    ap.add_argument("--feat")
    ap.add_argument("--skip-replay", action="store_true")
    args = ap.parse_args()
    base = load(args.base)
    print("baseline arm %s: %d runs" % (args.base, len(base)))
    if args.ctrl:
        ctrl = load(args.ctrl)
        identity(base, ctrl, args.ctrl)
    if args.feat:
        feat = load(args.feat)
        fire_identity(base, feat, args.feat)
        metrics(base, feat, args.feat)
        deaths_split(base, feat, args.feat)
        oscillation_report(base, "baseline " + args.base)
        oscillation_report(feat, "feature " + args.feat)
        rule("HOLD COUNTERS in the feature arm")
        section_a(feat)
        return
    section_a(base)
    section_b_c(base)
    oscillation_report(base, "baseline " + args.base)
    if not args.skip_replay:
        section_d(base)


if __name__ == "__main__":
    main()
