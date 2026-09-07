"""Interior-hazard round, Part 1: what the accidental override was doing.

Reads the recorded dimension-round arms (no simulation is run):
  outputs/_ffr_diminst_*.json   per-call counterfactual rows for the hazard gate
                                (C7), the near-edge flag (C5) and the retreat (C6)
  outputs/_ffr_dimbase_*.json   8520706 trajectories (override always on)
  outputs/_ffr_dimfix_*.json    e76c806 trajectories (override edge-only)
  outputs/_ffr_dimfresh{base,fix}_*.json   the 10 fresh seeds
Fire history comes from burn_intervals, which is identical across arms of a seed
(fire never depends on UAVs; digests identical 13/13 and 10/10 in the held round).

Sections:
  decisions   the C7 override, per unique (run, step, uav) changed decision in the
              interior: what was chosen, what the override did instead, the fire
              distance of each next cell, and the geometry (away/toward/lateral,
              reversal of the previous move, on a "wind_aware" vs "retarget" label)
  trajectory  base vs fix searcher steps: on burning cell, within 1/2/3 of fire,
              unique cells, mean fire distance, reversals, victims first-seen
usage: _ih_characterise.py decisions|trajectory|all
"""
from __future__ import annotations

import collections
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
MOVE_X = [1, 0, -1, 0]
MOVE_Y = [0, -1, 0, 1]
H = W = 50


def _name(tag, wind, roles, seed):
    rr = "def" if roles == "default" else roles
    return os.path.join(BASE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def load(tag, combos):
    runs = {}
    for k in combos:
        p = _name(tag, *k)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            with open(p, encoding="utf-8") as f:
                runs[k] = json.load(f)
    return runs


def label(k):
    return "D/%s/%s %d" % (k[0], k[1], k[2])


def edge_dist(x, y):
    return min(x, y, H - 1 - x, W - 1 - y)


class Fire:
    """burning set per step from burn_intervals ([start, end) half-open, end None = horizon)."""

    def __init__(self, run):
        self.by_step = collections.defaultdict(set)
        for key, ivs in run["burn_intervals"].items():
            x, y = key.split(",")
            cell = (int(x), int(y))
            for start, end in ivs:
                e = end if end is not None else run["steps"] + 1
                for s in range(start, e):
                    self.by_step[s].add(cell)
        self._cache = {}

    def burning(self, step):
        return self.by_step.get(step, set())

    def dist(self, cell, step):
        """manhattan distance from cell to the nearest cell burning at `step` (99 if none)."""
        b = self.by_step.get(step)
        if not b:
            return 99
        cx, cy = cell
        return min(abs(cx - fx) + abs(cy - fy) for fx, fy in b)


# ---------------------------------------------------------------------------
def decisions(combos, tag_inst="diminst"):
    I = load(tag_inst, combos)
    print("=== C7 HAZARD-GATE OVERRIDE, PER UNIQUE CHANGED DECISION (%s, %d runs) ===" % (tag_inst, len(I)))
    print("  the gate runs twice per searcher step (resolve branch + final gate in execute); rows are")
    print("  deduplicated by (run, step, uav). Fire = burning set after step s-1 (what the decision saw).")
    tot = collections.Counter()
    delta_hist = collections.Counter()
    kinds = collections.Counter()
    labels = collections.Counter()
    geom = collections.Counter()
    ex_rows = []
    per_run = {}
    c5_rows = collections.Counter()
    c6_rows = 0
    dup_factor = []
    for k in combos:
        r = I.get(k)
        if r is None or not r.get("dim"):
            continue
        fire = Fire(r)
        ch = r["dim"]["consumers_changed"]
        c7 = [row for row in ch if row[5] == "_apply_victim_searcher_hazard_gate"]
        seen = set()
        uniq = []
        for row in c7:
            key = (row[0], row[1])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(row)
        dup_factor.append((len(c7), len(uniq)))
        c5_rows[k] = sum(1 for row in ch if row[5] == "_victim_near_edge_escape_required")
        c6_rows += sum(1 for row in ch if row[5] == "_retreat_to_safe_interior_direction")
        stats = collections.Counter()
        for row in uniq:
            step, uid, role, x, y, name, real, cf, changed, extra = row
            if edge_dist(x, y) < 6:
                stats["edge_band"] += 1
                continue
            chosen_dir, action_in = int(extra[0]), str(extra[1])
            real_dir, real_lbl = int(real[0]), str(real[1])
            cf_dir, cf_lbl = int(cf[0]), str(cf[1])
            # the accidental override: what the dead world executed instead of the live choice
            if real_dir == chosen_dir and cf_dir != chosen_dir:
                kind = "override_removed"
            elif real_dir != chosen_dir and cf_dir == chosen_dir:
                kind = "override_added"
            else:
                kind = "different_override"
            kinds[kind] += 1
            labels[action_in.replace("victim_search_", "")] += 1
            s_seen = step - 1
            here = (x, y)
            c_live = (x + MOVE_X[real_dir], y + MOVE_Y[real_dir])
            c_dead = (x + MOVE_X[cf_dir], y + MOVE_Y[cf_dir])
            d_here = fire.dist(here, s_seen)
            d_live = fire.dist(c_live, s_seen)
            d_dead = fire.dist(c_dead, s_seen)
            delta = d_dead - d_live
            delta_hist[max(-3, min(3, delta))] += 1
            tot["n"] += 1
            if d_here >= 99:
                geom["no_fire_yet"] += 1
            # did the live choice step toward the fire, away, or lateral?
            if d_live < d_here:
                geom["live_toward"] += 1
            elif d_live > d_here:
                geom["live_away"] += 1
            else:
                geom["live_lateral"] += 1
            if d_dead < d_here:
                geom["dead_toward"] += 1
            elif d_dead > d_here:
                geom["dead_away"] += 1
            else:
                geom["dead_lateral"] += 1
            if (cf_dir + 2) % 4 == real_dir:
                geom["dead_is_reverse_of_live"] += 1
            # would the live step have landed on a cell burning at arrival (after step s) or the next?
            if c_live in fire.burning(step) or c_live in fire.burning(step + 1):
                geom["live_cell_burning_at_arrival"] += 1
            if c_dead in fire.burning(step) or c_dead in fire.burning(step + 1):
                geom["dead_cell_burning_at_arrival"] += 1
            if d_live <= 2:
                geom["live_within_2"] += 1
            if d_dead <= 2:
                geom["dead_within_2"] += 1
            if d_live <= 4:
                geom["live_within_4"] += 1
            if d_dead <= 4:
                geom["dead_within_4"] += 1
            stats[kind] += 1
            stats["delta>0"] += int(delta > 0)
            stats["delta<0"] += int(delta < 0)
            stats["delta=0"] += int(delta == 0)
            if len(ex_rows) < 40 and d_here < 99:
                ex_rows.append((label(k), step, uid, (x, y), action_in.replace("victim_search_", ""),
                                real_dir, cf_dir, d_here, d_live, d_dead, kind))
        # previous executed dirs need the trajectory; approximate from uav_steps of the same run
        per_run[k] = stats
    print("  gate rows per run (all C7 changed rows -> unique (step,uav)): %s" % dup_factor)
    print("  interior (>=6 from any edge) unique changed C7 decisions: %d   (edge band <6: %d)" % (
        tot["n"], sum(v.get("edge_band", 0) for v in per_run.values())))
    print("  kind: %s" % dict(kinds))
    print("  input action label at the gate: %s" % dict(labels.most_common()))
    print("  fire-distance delta of the dead-world step minus the live step (next cell, capped +-3):")
    for d in sorted(delta_hist):
        print("    %+d: %5d  (%.1f%%)" % (d, delta_hist[d], 100.0 * delta_hist[d] / max(1, tot["n"])))
    print("  geometry relative to the nearest burning cell (n=%d):" % tot["n"])
    for key in ("no_fire_yet", "live_toward", "live_lateral", "live_away", "dead_toward", "dead_lateral", "dead_away",
                "dead_is_reverse_of_live", "live_within_2", "dead_within_2", "live_within_4", "dead_within_4",
                "live_cell_burning_at_arrival", "dead_cell_burning_at_arrival"):
        print("    %-32s %5d  (%.1f%%)" % (key, geom[key], 100.0 * geom[key] / max(1, tot["n"])))
    print("  per run: interior changed / delta>0 (dead safer) / delta<0 (dead closer) / =0")
    for k in combos:
        s = per_run.get(k)
        if s is None:
            continue
        n = s["override_removed"] + s["override_added"] + s["different_override"]
        print("    %-22s %4d   %4d / %4d / %4d   edge-band %d   C5 flag rows %d" % (
            label(k), n, s["delta>0"], s["delta<0"], s["delta=0"], s.get("edge_band", 0), c5_rows[k]))
    print("  C6 (retreat direction re-ranked by the live boundary terms) rows: %d" % c6_rows)
    print("  examples (run, step, uav, pos, label, live_dir, dead_dir, fire dist here/live/dead, kind):")
    for e in ex_rows[:40]:
        print("    %s" % (e,))


# ---------------------------------------------------------------------------
def trajectory(combos, tag_a, tag_b):
    A, B = load(tag_a, combos), load(tag_b, combos)
    print("=== SEARCHER TRAJECTORIES vs FIRE: %s -> %s (%d runs) ===" % (tag_a, tag_b, len(A)))
    print("  per searcher step (position after the step vs burning set after the same step)")
    agg = {tag_a: collections.Counter(), tag_b: collections.Counter()}
    dsum = {tag_a: 0.0, tag_b: 0.0}
    rows = []
    for k in combos:
        a, b = A.get(k), B.get(k)
        if a is None or b is None:
            continue
        fire = Fire(a)
        line = [label(k)]
        for tag, run in ((tag_a, a), (tag_b, b)):
            c = collections.Counter()
            cells = collections.defaultdict(set)
            prev = {}
            prevdir = {}
            for i, row in enumerate(run["uav_steps"]):
                s = i + 1
                for uid, pos, role, sd in row:
                    if role != "victim_searcher" or pos is None:
                        continue
                    cell = (pos[0], pos[1])
                    c["steps"] += 1
                    d = fire.dist(cell, s)
                    if d == 0:
                        c["on_fire"] += 1
                    if d <= 1:
                        c["le1"] += 1
                    if d <= 2:
                        c["le2"] += 1
                    if d <= 3:
                        c["le3"] += 1
                    if d < 99:
                        c["dsum"] += min(d, 30)
                        c["dn"] += 1
                    cells[uid].add(cell)
                    if edge_dist(*cell) <= 5:
                        c["edge5"] += 1
                    p = prev.get(uid)
                    if p is not None:
                        dx, dy = cell[0] - p[0], cell[1] - p[1]
                        if (dx, dy) == (0, 0):
                            c["hold"] += 1
                        else:
                            mv = None
                            for di in range(4):
                                if (MOVE_X[di], MOVE_Y[di]) == (dx, dy):
                                    mv = di
                            pdm = prevdir.get(uid)
                            if mv is not None and pdm is not None and (pdm + 2) % 4 == mv:
                                c["reversal"] += 1
                            if mv is not None:
                                prevdir[uid] = mv
                    prev[uid] = cell
            c["unique_cells"] = sum(len(v) for v in cells.values())
            agg[tag].update(c)
            line.append("%s on_fire %3d le1 %3d le2 %3d le3 %3d meanD %5.1f edge5 %4.1f%% uniq %4d rev %3d hold %3d" % (
                tag[:7], c["on_fire"], c["le1"], c["le2"], c["le3"], (c["dsum"] / c["dn"]) if c["dn"] else 0.0,
                100.0 * c["edge5"] / max(1, c["steps"]), c["unique_cells"], c["reversal"], c["hold"]))
        rows.append(line)
    for line in rows:
        print("  %-22s | %s\n  %-22s | %s" % (line[0], line[1], "", line[2]))
    for tag in (tag_a, tag_b):
        c = agg[tag]
        n = max(1, c["steps"])
        print("  TOTAL %-12s steps %5d  on burning cell %4d (%.2f%%)  <=1 %4d (%.2f%%)  <=2 %4d (%.2f%%)  <=3 %4d (%.2f%%)  mean fire dist %.2f  edge<=5 %.1f%%  unique cells %d  reversals %d  holds %d" % (
            tag, c["steps"], c["on_fire"], 100.0 * c["on_fire"] / n, c["le1"], 100.0 * c["le1"] / n, c["le2"], 100.0 * c["le2"] / n,
            c["le3"], 100.0 * c["le3"] / n, c["dsum"] / max(1, c["dn"]), 100.0 * c["edge5"] / n, c["unique_cells"], c["reversal"], c["hold"]))


def main(argv):
    sec = argv[0] if argv else "all"
    if sec in ("decisions", "all"):
        decisions(CANON)
    if sec in ("trajectory", "all"):
        trajectory(CANON, "dimbase", "dimfix")
        trajectory(FRESH, "dimfreshbase", "dimfreshfix")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
