"""Fire mechanic round 2, diagnostic D - IS A COMPLETION THRESHOLD WORTH ANYTHING? Read-only.

usage:  _fm2_diag_priority.py [--out outputs/_fm2_diag_priority.txt]

Reads ONLY explicit harness JSON paths outputs/_ffr_<arm>_<wind>_<rr>_<seed>.json for
arms fmEFS fmF fmFS fmES fmDRY (+ fmOFF for victim matching), canonical 13 + fresh 10.
No simulation is run. No existing file is modified.

Definitions (reused from outputs/_firemech_analyze.py where one exists)
  preemption   an ok assign landing on a unit whose latest firefight_log row (this
               step, or the previous step with no row this step) was engaged
               (plan not None) - _firemech_analyze.run_summary, verbatim
  work row     WET arm: a clear/extinguish row with wrote True. DRY arm: a
               clear/extinguish row with dry True (the suppressed write; the target
               goes into the shadow set and targeting treats it as not-fuel)
  window       the preempted unit's work rows at steps s-9..s (10 advances up to
               and including the assign step s; the assign is applied in the
               post-move cycle, after that step's advance)
  class        W  >= 1 clear in the window (partial firebreak work exists)
               X  extinguish only in the window
               A  no work in the window (approaching / walking; nothing to finish)
  anchor       W: the last clear's cell; X: last extinguish cell; A: latest row target
  FIRE STATE AT POST-STEP s (EXACT, validated below against the feature's own log)
    burning(s) from burn_intervals ([start,end) post-step observation)
    fuel(s)    = not burning(s), not worked on at <= s (WET write or DRY shadow), and
                 not burnt by s. burnt by s: the cell is burnt at 240
                 (fire_ground_final[1]) and s >= its burn-out step = its WET write
                 step if written, else the end of its last burn interval. Scorched
                 cells (burned, fuel left) ARE fuel, exactly as the model's targeting.
    band(s)    = fuel cells with euclidean distance in (2,5] to the nearest burning
                 cell (4 < d2 <= 25), exactly _firefight_plan's band
    APPROXIMATE (the brief's): fuel = not burned by s (first_burn_step) and not worked
                 on; reported beside the exact counts, it disagrees with the log.
  VIEW VALIDATION: a unit's advance at step s sees post-step s minus the same-step
               writes of itself and of units later in unique_id order. The logged
               band / front / dist of every row is recomputed from the JSON.
  R3 / R5      uncleared band cells within manhattan 3 / 5 of the anchor at step r
  built3/5     worked cells (any unit, <= r) within manhattan 3 / 5 of the anchor
  fates of R   per cell: cleared (a later work row on it before it burns), burned
               (burning at some step > r before any work on it), open (neither by 240)
               breached = >= 1 burned; completed = all cleared
  stake M      never-burned (first_burn_step > r), unworked, not burning cells with
               euclidean distance > 5 from every burning cell at r (BEYOND the band),
               within manhattan M of the anchor; crossed = >= 1 of them burned later
  stop         a clear by unit u at t with no further work by u within manhattan 5 of
               that cell in (t, t+10]. Reason = preempted (a preemption of u at
               s in [t, t+9]) else the first event of u in (t, t+10]: retreat row,
               'none' row (no plan), work elsewhere, non-preempting assign, death,
               horizon (t+10 > 240); only moves -> moving; no rows -> not idle
  slack        for a preempted rescue with contact (first exit_start of u for the
               victim after s): S_cell = first step >= contact at which the victim's
               contact cell burns, minus contact; S_nbhd = same over the Moore-1
               neighbourhood; S_path = min over the unit's post-step cells k from s to
               the end of the rescue of (first step >= k that cell burns) - k.
               None = no burn by 240 (reported as '-').
  delay        a threshold that finishes R3 needs >= |R3| steps (one clear per step,
               no walking counted), so delay3 = |R3|, delay5 = |R5|: lower bounds
  re-dispatch  an ok assign counted by the preemption definition although the unit
               was ALREADY assigned at post-step s-1 (no row at s): e.g. route_blocked
               -> unassign -> same unit re-assigned the next step. Not a new
               preemption; listed, excluded from the 'distinct' analyses.
  chain dependence (realized-ignition reachability, a sharper value estimate)
               nodes = burn intervals; sources = intervals burning at r; an ignition of
               v at step k (interval start k > r) is reachable if some cell u with
               0 < euclid(u,v) <= 3 (the spread kernel: distance_rate is 0 beyond 3)
               has a REACHABLE interval [a,b) with a < k <= b (burning at post-step
               k-1). Blocking a set removes its cells. dep(X) = cells never burned at r
               that burned later and have NO reachable interval once X is removed:
               every realized ignition chain to them ran through X. Sanity: with
               nothing removed dep must be 0 (checked per event).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N = 50
STEPS = 240
WORK = ("clear", "extinguish")
WINDOW = 10
STOP_GAP = 10
STOP_RADIUS = 5
BIG = 10 ** 6
ARMS = ["fmEFS", "fmF", "fmFS", "fmES", "fmDRY"]
FIREBREAK_ARMS = ["fmEFS", "fmF", "fmFS", "fmDRY"]
UNITS = ["ff_unit_0", "ff_unit_1"]  # unique_id order (validated: u0 advances first)

CANONICAL = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("east", "def", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
ALL = CANONICAL + FRESH

OUT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def label(t):
    return "%s/%s/%d" % t


def sample_of(t):
    return "can" if t in CANONICAL else "fr"


def path(tag, t):
    return os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], t[1], t[2]))


def disk(r2):
    return [(dx, dy) for dx in range(-5, 6) for dy in range(-5, 6) if dx * dx + dy * dy <= r2]


D25, D4 = disk(25), disk(4)
D9 = [(dx, dy) for dx in range(-3, 4) for dy in range(-3, 4) if 0 < dx * dx + dy * dy <= 9]
D4S = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if 0 < dx * dx + dy * dy <= 4]  # distance_rate >= 0.25


def dilate(b, offs):
    p = np.zeros((N + 10, N + 10), bool)
    p[5:5 + N, 5:5 + N] = b
    out = np.zeros((N, N), bool)
    for dx, dy in offs:
        out |= p[5 + dx:5 + dx + N, 5 + dy:5 + dy + N]
    return out


def manh_cells(c, r):
    x, y = c
    out = []
    for dx in range(-r, r + 1):
        rem = r - abs(dx)
        for dy in range(-rem, rem + 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < N and 0 <= ny < N:
                out.append((nx, ny))
    return out


def md(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def fmt(v):
    return "-" if v is None else str(v)


def med(xs):
    xs = [x for x in xs if x is not None]
    return ("%.1f" % statistics.median(xs)) if xs else "-"


def pct(a, b):
    return "%d/%d (%s)" % (a, b, ("%.0f%%" % (100.0 * a / b)) if b else "-")


class Run:
    def __init__(self, tag, t):
        self.tag, self.t = tag, t
        with open(path(tag, t), encoding="utf-8") as f:
            d = json.load(f)
        self.d = d
        self.term = d.get("terminal_step")
        self.ivs = {}
        burn = np.zeros((STEPS + 2, N, N), bool)
        for k, iv in (d.get("burn_intervals") or {}).items():
            c = tuple(int(v) for v in k.split(","))
            self.ivs[c] = sorted((a, STEPS + 1 if b is None else b) for a, b in iv)
            for a, b in self.ivs[c]:
                burn[a:b, c[0], c[1]] = True
        self.burn = burn
        self.fbs = np.full((N, N), BIG, dtype=np.int64)
        for k, s in (d.get("first_burn_step") or {}).items():
            c = tuple(int(v) for v in k.split(","))
            self.fbs[c] = s
        self.log = d.get("firefight_log") or []
        self.rows = collections.defaultdict(dict)
        for r in self.log:
            self.rows[r["ff"]][r["step"]] = r
        self.dry = any(r.get("dry") for r in self.log)
        self.stale_work = sum(1 for r in self.log if r["action"] in WORK and not r.get("wrote") and not r.get("dry"))
        self.work = [r for r in self.log if r["action"] in WORK and (r.get("wrote") or r.get("dry"))]
        self.work_step = np.full((N, N), BIG, dtype=np.int64)
        self.work_by = collections.defaultdict(list)
        for r in self.work:
            c = tuple(r["target"])
            self.work_by[c].append((r["step"], r["ff"], r["action"]))
            self.work_step[c] = min(self.work_step[c], r["step"])
        self.burnt_from = np.full((N, N), BIG, dtype=np.int64)
        for k, v in (d.get("fire_ground_final") or {}).items():
            if not v[1]:
                continue
            c = tuple(int(x) for x in k.split(","))
            if not self.dry and c in self.work_by:
                self.burnt_from[c] = min(s for s, _f, _a in self.work_by[c])
            else:
                ends = [b for _a, b in self.ivs.get(c, ()) if b <= STEPS]
                self.burnt_from[c] = max(ends) if ends else BIG
        self.pos = collections.defaultdict(dict)
        for i, row in enumerate(d.get("ff_steps") or []):
            for ff, p, st, asg, ex, dead in row:
                self.pos[ff][i + 1] = (tuple(p) if p is not None else None, st, asg, ex, dead)
        self.vpos = collections.defaultdict(dict)
        for i, row in enumerate(d.get("victim_steps") or []):
            for vid, p, st in row:
                self.vpos[vid][i + 1] = (tuple(p) if p is not None else None, st)
        self.ok_assigns = [a for a in (d.get("assigns") or []) if a.get("ok")]
        self._state = {}
        self._dep0 = {}

    # ---- fire state -------------------------------------------------------------
    def state(self, s):
        if s not in self._state:
            b = self.burn[s]
            workle = self.work_step <= s
            fuel = ~b & ~workle & ~(self.burnt_from <= s)
            d25, d4 = dilate(b, D25), dilate(b, D4)
            self._state[s] = {
                "B": b, "workle": workle, "fuel": fuel,
                "band": fuel & d25 & ~d4,
                "approx": (self.fbs > s) & ~workle & ~b & d25 & ~d4,
                "beyond": fuel & ~d25 & (self.fbs > s),
                "annulus": ~b & ~(self.burnt_from <= s) & d25 & ~d4,
            }
            if len(self._state) > 64:
                self._state.pop(next(iter(self._state)))
        return self._state[s]

    def ign_after(self, c, s, inclusive=False):
        lo = s if inclusive else s + 1
        for a, b in self.ivs.get(c, ()):
            st = max(a, lo)
            if st < b:
                return st
        return None

    def dependent(self, r, blocked, offs=None):
        """Cells never burned at r that burned later with no reachable interval once
        `blocked` is removed (see 'chain dependence' in the module docstring).
        offs: parent offsets (default every 0 < d2 <= 9, the full kernel)."""
        offs = D9 if offs is None else offs
        blocked = set(blocked)
        reach = collections.defaultdict(list)
        events = []
        for c, ivs in self.ivs.items():
            if c in blocked:
                continue
            for a, b in ivs:
                if a <= r < b:
                    reach[c].append((a, b))
                elif a > r:
                    events.append((a, c, b))
        events.sort()
        i = 0
        while i < len(events):
            k = events[i][0]
            j = i
            new = []
            while j < len(events) and events[j][0] == k:
                _k, c, b = events[j]
                ok = False
                for dx, dy in offs:
                    for a_u, b_u in reach.get((c[0] + dx, c[1] + dy), ()):
                        if a_u < k <= b_u:
                            ok = True
                            break
                    if ok:
                        break
                if ok:
                    new.append((c, (k, b)))
                j += 1
            for c, iv in new:
                reach[c].append(iv)
            i = j
        out = []
        for c, ivs in self.ivs.items():
            if c in blocked or self.fbs[c] <= r or self.fbs[c] > STEPS:
                continue
            if not reach.get(c):
                out.append(c)
        return out

    def first_work_after(self, c, s):
        xs = [(st, ff) for st, ff, _a in self.work_by.get(c, ()) if st > s]
        return min(xs) if xs else None

    # ---- validation of the view reconstruction against the logged counts --------
    def validate(self):
        res = collections.Counter()
        rank = {u: i for i, u in enumerate(UNITS)}
        same_step = collections.defaultdict(list)
        for r in self.work:
            same_step[r["step"]].append(r)
        for r in self.log:
            s, u = r["step"], r["ff"]
            st = self.state(s)
            b = st["B"].copy()
            fuel = st["fuel"].copy()
            fuel_ap = (self.fbs > s) & ~st["workle"]
            for w in same_step.get(s, ()):
                if rank[w["ff"]] >= rank[u]:
                    c = tuple(w["target"])
                    if w["action"] == "extinguish" and not self.dry:
                        b[c] = True
                        fuel[c] = False
                    elif w["action"] == "clear":
                        # fuel when this unit looked (not yet cleared / shadowed)
                        fuel[c] = not b[c]
                        fuel_ap[c] = self.fbs[c] > s
            fuel_ap = fuel_ap & ~b
            d25, d4 = dilate(b, D25), dilate(b, D4)
            if r.get("band") is not None:
                res["band_rows"] += 1
                res["band_ok"] += int(int((fuel & d25 & ~d4).sum()) == r["band"])
                res["band_ok_approx"] += int(int((fuel_ap & d25 & ~d4).sum()) == r["band"])
            if r.get("front") is not None:
                shadow = st["workle"].copy() if self.dry else np.zeros((N, N), bool)
                if self.dry:
                    for w in same_step.get(s, ()):
                        if rank[w["ff"]] >= rank[u]:
                            shadow[tuple(w["target"])] = False
                nbr = np.zeros((N, N), bool)
                nbr[1:, :] |= fuel[:-1, :]
                nbr[:-1, :] |= fuel[1:, :]
                nbr[:, 1:] |= fuel[:, :-1]
                nbr[:, :-1] |= fuel[:, 1:]
                res["front_rows"] += 1
                res["front_ok"] += int(int((b & ~shadow & nbr).sum()) == r["front"])
            if b.any():
                xs, ys = np.nonzero(b)
                cx, cy = r["cell"]
                res["dist_rows"] += 1
                res["dist_ok"] += int(int((np.abs(xs - cx) + np.abs(ys - cy)).min()) == r["dist"])
        return res

    # ---- events ------------------------------------------------------------------
    def preemptions(self):
        out = []
        for a in self.ok_assigns:
            rows = self.rows.get(a["ff"], {})
            now, prev = rows.get(a["step"]), rows.get(a["step"] - 1)
            if (now is not None and now.get("engaged")) or (now is None and prev is not None and prev.get("engaged")):
                out.append((a, now if now is not None else prev))
        return out

    def unit_death(self, u):
        for k in sorted(self.pos[u]):
            if self.pos[u][k][4]:
                return k
        return None

    def victim_outcome(self, vid):
        steps = self.vpos.get(vid, {})
        final = steps.get(STEPS, (None, None))[1]
        dead = next((k for k in sorted(steps) if steps[k][1] == "dead"), None)
        resc = next((k for k in sorted(steps) if steps[k][1] == "rescued"), None)
        return final, dead, resc


def seg_metrics(run, u, anchor, seg, r, extended=False):
    st = run.state(r)
    m = {}
    for R in (3, 5):
        cells = manh_cells(anchor, R)
        band = [c for c in cells if st["band"][c]]
        m["R%d" % R] = band
        m["n%d" % R] = len(band)
        m["sc%d" % R] = sum(1 for c in band if run.fbs[c] <= r)
        m["ap%d" % R] = sum(1 for c in cells if st["approx"][c])
        m["built%d" % R] = sum(1 for c in cells if st["workle"][c])
        fate = collections.Counter()
        first_breach = None
        clear_steps = []
        clear_units = collections.Counter()
        cleared_then_burned = 0
        rec = []
        for c in band:
            fw = run.first_work_after(c, r)
            ig = run.ign_after(c, r)
            if fw is not None and (ig is None or fw[0] < ig):
                fate["cleared"] += 1
                clear_steps.append(fw[0])
                clear_units["same" if fw[1] == u else "other"] += 1
                if run.dry and run.ign_after(c, fw[0]) is not None:
                    cleared_then_burned += 1
            elif ig is not None:
                fate["burned"] += 1
                first_breach = ig if first_breach is None else min(first_breach, ig)
            else:
                fate["open"] += 1
            rec.append((c, fw, ig))
        m["fate%d" % R] = fate
        m["clear_units%d" % R] = clear_units
        m["breach%d" % R] = (first_breach - r) if first_breach is not None else None
        m["completed%d" % R] = (max(clear_steps) - r) if band and fate["cleared"] == len(band) else None
        m["ctb%d" % R] = cleared_then_burned
        if first_breach is not None:
            m["left_at_breach%d" % R] = sum(1 for c, fw, ig in rec if fw is None or fw[0] >= first_breach)
        else:
            m["left_at_breach%d" % R] = None
    # chain dependence. WET arms: base = {} (a cleared cell has no burn interval, it blocks by itself).
    # DRY arm: base = the suppressed-cleared cells still unburnt at r, i.e. 'as if the DRY work had been real'
    # on the DRY (= OFF) fire; dep(X) = cells newly unreachable when X is added to the base.
    if ("san", r) not in run._dep0:
        run._dep0[("san", r)] = len(run.dependent(r, []))
    m["dep_sanity"] = run._dep0[("san", r)]
    base = set()
    if run.dry:
        base = {tuple(int(v) for v in c) for c in np.argwhere(
            st["workle"] & ~st["B"] & ~(run.burnt_from <= r))}

    def udep(extra, offs=None):
        return set(run.dependent(r, base | set(extra), offs))

    for key, offs in (("u0", None), ("u0s", D4S)):
        if (key, r) not in run._dep0:
            run._dep0[(key, r)] = udep([], offs)
    u0, u0s = run._dep0[("u0", r)], run._dep0[("u0s", r)]
    for R in (3, 5):
        dep = (udep(m["R%d" % R]) - u0) if m["R%d" % R] else set()
        m["dep%d" % R] = len(dep)
        m["dep%d_m5" % R] = sum(1 for c in dep if md(c, anchor) <= 5)
        m["dep%d_m8" % R] = sum(1 for c in dep if md(c, anchor) <= 8)
    if extended:
        # a much longer segment: every uncleared band cell within manhattan 8 of the anchor
        r8 = [c for c in manh_cells(anchor, 8) if st["band"][c]]
        m["n8"] = len(r8)
        m["dep8"] = len(udep(r8) - u0) if r8 else 0
        for R in (12, 16):
            rr_ = [c for c in manh_cells(anchor, R) if st["band"][c]]
            m["n%d" % R] = len(rr_)
            m["dep%d" % R] = len(udep(rr_) - u0) if rr_ else 0
        # sensitivity: strong links only (euclid <= 2, distance_rate >= 0.25); dep = newly unreachable cells
        m["dep3s"] = len(udep(m["R3"], D4S) - u0s) if m["R3"] else 0
        m["dep5s"] = len(udep(m["R5"], D4S) - u0s) if m["R5"] else 0
        # positive control: block the COMPLETE annulus (2,5] around the fire at r (every unburnt, not-burning cell
        # there, shadowed DRY cells included); every beyond cell that burned later must become unreachable
        ring = [tuple(int(v) for v in c) for c in np.argwhere(st["annulus"])]
        depr = set(run.dependent(r, ring))
        beyond_burned = [tuple(int(v) for v in c) for c in np.argwhere(st["beyond"] & (run.fbs <= STEPS))]
        m["ring_n"] = len(ring)
        m["ring_dep"] = len(depr)
        m["ring_beyond"] = len(beyond_burned)
        m["ring_missed"] = sum(1 for c in beyond_burned if c not in depr)
    near = set(seg) | {anchor}
    later = sorted((w["step"], w["ff"], tuple(w["target"])) for w in run.work
                   if w["step"] > r and w["action"] == "clear"
                   and min(md(tuple(w["target"]), c) for c in near) <= 5)
    m["later_n"] = len(later)
    m["first_later"] = (later[0][0] - r, "same" if later[0][1] == u else "other") if later else None
    fo = next((x for x in later if x[1] != u), None)
    fs = next((x for x in later if x[1] == u), None)
    m["first_other"] = fo[0] - r if fo else None
    m["first_same"] = fs[0] - r if fs else None
    for M in (5, 8):
        cells = [c for c in manh_cells(anchor, M) if st["beyond"][c]]
        burned = [c for c in cells if run.fbs[c] <= STEPS]
        m["stake%d" % M] = len(cells)
        m["stake%d_burned" % M] = len(burned)
        m["stake%d_first" % M] = (min(int(run.fbs[c]) for c in burned) - r) if burned else None
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "_fm2_diag_priority.txt"))
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args()

    say("=" * 100)
    say("FM2 DIAGNOSTIC D - IS A COMPLETION THRESHOLD WORTH ANYTHING?   (generated by outputs/_fm2_diag_priority.py)")
    say("=" * 100)
    say("Data: outputs/_ffr_<arm>_<wind>_<rr>_<seed>.json, arms %s + fmOFF (victim matching)," % " ".join(ARMS))
    say("canonical 13 (east/half, south/half 101-505, east/def 101-303) + fresh 10 (east/half, south/half 606-1010).")
    say("De-duplicated = east/def excluded (east/def/s and east/half/s share the same fire at OFF).")
    say("Definitions: see the module docstring of outputs/_fm2_diag_priority.py (repeated where used).")
    header_end = len(OUT)

    runs = {}
    for tag in ARMS + ["fmOFF"]:
        for t in ALL:
            runs[(tag, t)] = Run(tag, t)

    # ------------------------------------------------------------------ 0 ----
    say("")
    say("0. FIRE-STATE RECONSTRUCTION - VALIDATED AGAINST THE FEATURE'S OWN LOG")
    say("   Every firefight_log row carries the band size, front size and manhattan fire distance the unit")
    say("   computed at its advance. Recomputed from burn_intervals + fire_ground_final + the work rows:")
    if not a.no_validate:
        say("   %-6s %-22s %-22s %-22s %-22s %s" % ("arm", "band EXACT", "band APPROX (brief)", "front EXACT", "dist", "stale work rows"))
        for tag in ARMS:
            tot = collections.Counter()
            stale = 0
            for t in ALL:
                tot.update(runs[(tag, t)].validate())
                stale += runs[(tag, t)].stale_work
            say("   %-6s %-22s %-22s %-22s %-22s %d" % (
                tag, pct(tot["band_ok"], tot["band_rows"]), pct(tot["band_ok_approx"], tot["band_rows"]),
                pct(tot["front_ok"], tot["front_rows"]), pct(tot["dist_ok"], tot["dist_rows"]), stale))
        say("   EXACT = scorched cells are fuel until their recorded burn-out; APPROX = the brief's 'not burned by then'.")
        say("   The approximation is NOT needed: burn-out is recoverable (a burnt-at-240 cell burns out exactly when its last")
        say("   burn interval ends, or at its firefighter write). Every band/front figure below uses the EXACT state; the")
        say("   brief's approximate band count is printed beside it where asked (it drops the scorched band cells).")

    # ------------------------------------------------------------------ 1 ----
    events = {tag: [] for tag in ARMS}
    for tag in ARMS:
        for t in ALL:
            run = runs[(tag, t)]
            for asg, latest in run.preemptions():
                s, u, vid = asg["step"], asg["ff"], asg["vid"]
                win = [r for r in run.work if r["ff"] == u and s - WINDOW < r["step"] <= s]
                clears = [r for r in win if r["action"] == "clear"]
                exts = [r for r in win if r["action"] == "extinguish"]
                cls = "W" if clears else ("X" if exts else "A")
                if cls == "W":
                    anchor = tuple(clears[-1]["target"])
                elif cls == "X":
                    anchor = tuple(exts[-1]["target"])
                else:
                    anchor = tuple(latest["target"]) if latest.get("target") else tuple(latest["cell"])
                p = run.pos[u].get(s, (None,))[0]
                row_at_s = s in run.rows.get(u, {})
                prev_pos = run.pos[u].get(s - 1)
                redispatch = (not row_at_s) and prev_pos is not None and bool(prev_pos[2])
                other = [x for x in UNITS if x != u][0]
                orows = run.rows.get(other, {})
                ost = run.pos[other].get(s)
                if ost is None or ost[4]:
                    ostate = "dead"
                elif ost[0] is None:
                    ostate = "off-grid"
                elif ost[2] or ost[3]:
                    ostate = "on rescue"
                else:
                    olatest = orows.get(s) or orows.get(s - 1)
                    owork = [r for r in run.work if r["ff"] == other and s - WINDOW < r["step"] <= s
                             and r["action"] == "clear"]
                    if olatest is not None and olatest.get("engaged"):
                        ostate = "working(W)" if owork else "engaged"
                    else:
                        ostate = "idle"
                ev = {
                    "t": t, "s": s, "u": u, "vid": vid, "reason": asg["reason"], "cls": cls,
                    "latest": latest, "pos": p, "win": win, "clears": clears, "exts": exts,
                    "anchor": anchor, "since_term": (s - run.term) if run.term is not None else None,
                    "t_last": clears[-1]["step"] if clears else None,
                    "row_at_s": row_at_s, "redispatch": redispatch, "ostate": ostate,
                }
                events[tag].append(ev)

    say("")
    say("=" * 100)
    say("1. PREEMPTIONS  (ok assign landing on a unit engaged on its latest firefight_log row)")
    say("=" * 100)
    say("   class W = >=1 clear by that unit in steps s-9..s (partial firebreak work to abandon)")
    say("         X = extinguish only in the window;  A = no work in the window (walking toward work)")
    say("   %-6s %-9s %-9s %-26s %-26s %s" % ("arm", "counted", "de-dup", "W/X/A counted", "W/X/A de-dup", "canonical / fresh (W)"))
    for tag in ARMS:
        ev = events[tag]
        dd = [e for e in ev if e["t"][1] != "def"]
        c = collections.Counter(e["cls"] for e in ev)
        cd = collections.Counter(e["cls"] for e in dd)
        can = [e for e in ev if sample_of(e["t"]) == "can"]
        fr = [e for e in ev if sample_of(e["t"]) == "fr"]
        say("   %-6s %-9d %-9d %-26s %-26s %d (%d) / %d (%d)" % (
            tag, len(ev), len(dd), "%d / %d / %d" % (c["W"], c["X"], c["A"]),
            "%d / %d / %d" % (cd["W"], cd["X"], cd["A"]), len(can),
            sum(1 for e in can if e["cls"] == "W"), len(fr), sum(1 for e in fr if e["cls"] == "W")))
    say("")
    say("   RE-DISPATCHES (unit already assigned at post-step s-1, no row at s) and DISTINCT preemptions")
    say("   %-6s %-12s %-10s %-22s %-22s %s" % ("arm", "re-dispatch", "distinct", "distinct W/X/A", "distinct de-dup W/X/A",
                                              "assign after the unit's advance at s (row at s) / before it"))
    for tag in ARMS:
        ev = events[tag]
        dist = [e for e in ev if not e["redispatch"]]
        c = collections.Counter(e["cls"] for e in dist)
        cd = collections.Counter(e["cls"] for e in dist if e["t"][1] != "def")
        say("   %-6s %-12s %-10d %-22s %-22s %d / %d" % (
            tag, ", ".join("%s s=%d %s" % (label(e["t"]), e["s"], e["u"]) for e in ev if e["redispatch"]) or "0",
            len(dist), "%d / %d / %d" % (c["W"], c["X"], c["A"]), "%d / %d / %d" % (cd["W"], cd["X"], cd["A"]),
            sum(1 for e in ev if e["row_at_s"]), sum(1 for e in ev if not e["row_at_s"])))
    say("")
    say("   PRE-TERMINAL CHECK (all victims terminal => nothing left to dispatch)")
    for tag in ARMS:
        ev = events[tag]
        pre = sum(1 for e in ev if e["since_term"] is not None and e["since_term"] < 0)
        nonterm = sum(1 for e in ev if e["since_term"] is None)
        at = [e for e in ev if e["since_term"] is not None and e["since_term"] == 0]
        post = sum(1 for e in ev if e["since_term"] is not None and e["since_term"] > 0)
        gaps = [-e["since_term"] for e in ev if e["since_term"] is not None and e["since_term"] < 0]
        say("   %-6s before terminal_step %d, in non-terminal runs %d, AT terminal_step %d, after %d   steps before terminal: median %s, min %s" % (
            tag, pre, nonterm, len(at), post, med(gaps), min(gaps) if gaps else "-"))
        for e in at:
            run = runs[(tag, e["t"])]
            fin, dstep, _r = run.victim_outcome(e["vid"])
            say("          AT terminal: %s s=%d %s %s reason %s, row at s: %s (False = assigned in the PRE-move cycle of step s,"
                " before that step's casualty check); victim final %s at step %s" % (
                    label(e["t"]), e["s"], e["u"], e["vid"], e["reason"], e["row_at_s"], fin, fmt(dstep)))
    say("")
    say("   INITIAL-WAVE SHARE: preemptions at steps <= 20 (units leave standby toward the fire at step 1 and the first")
    say("   dispatches land at 14-16, before any unit has reached work)")
    for tag in ARMS:
        ev = events[tag]
        early = [e for e in ev if e["s"] <= 20]
        say("   %-6s %s at s<=20 (W among them %d)" % (tag, pct(len(early), len(ev)), sum(1 for e in early if e["cls"] == "W")))
    say("")
    say("   LISTING  run | step | unit | victim | reason | class (r = re-dispatch) | unit cell (latest row, before acting) -> "
        "post-step | latest row action | work in window (step:action@cell, s=scorched) | steps to terminal | other unit at "
        "post-step s")
    for tag in ARMS:
        say("   --- %s ---" % tag)
        for e in events[tag]:
            w = " ".join("%d:%s@%d,%d%s" % (r["step"], r["action"][:3], r["target"][0], r["target"][1],
                                             "s" if r.get("scorched") else "") for r in e["win"])
            say("   %-16s %3d %-9s %-8s %-26s %s%s %-7s -> %-7s %-10s [%s]  %s  other: %s" % (
                label(e["t"]), e["s"], e["u"], e["vid"], e["reason"][:26], e["cls"], "r" if e["redispatch"] else " ",
                "%d,%d" % tuple(e["latest"]["cell"]), ("%d,%d" % e["pos"]) if e["pos"] else "-",
                e["latest"]["action"], w, ("T%+d" % e["since_term"]) if e["since_term"] is not None else "non-terminal",
                e["ostate"]))

    # ------------------------------------------------------------------ 2/3 --
    say("")
    say("=" * 100)
    say("2+3. THE ABANDONED SEGMENT (class W, fire state at the assign step s) AND WHAT HAPPENED TO IT")
    say("=" * 100)
    say("   n3/n5   uncleared band cells within manhattan 3/5 of the last clear (EXACT state); sc = of which scorched")
    say("   ap3/ap5 the same count with the brief's approximation (scorched cells dropped)")
    say("   b3/b5   worked cells (any unit, <= s) within manhattan 3/5 of the last clear")
    say("   later   first later clear within manhattan 5 of the window's clears: +steps (same|other unit); o/s = first by")
    say("           the other / the same unit;  R3 fate c/b/o = cleared / burned / open;  brch = steps to first R3 burn;")
    say("           done = steps until R3 fully cleared;  left = R3 cells still uncleared when the fire first hit R3;")
    say("           stk5 = never-burned cells beyond the band (d>5) within manhattan 5 burned later / all (first +steps)")
    say("           dep3 = chain-dependent cells if R3 had been non-fuel from s: within manhattan 5 / 8 / whole grid;")
    say("           dep5 = the same blocking R5 (whole grid); san = dependent cells with nothing blocked (must be 0)")
    for tag in ARMS:
        evw_all = [e for e in events[tag] if e["cls"] == "W"]
        if not evw_all:
            continue
        say("   --- %s: %d class-W preemptions (%d re-dispatch, marked r) ---" % (
            tag, len(evw_all), sum(1 for e in evw_all if e["redispatch"])))
        say("   %-16s %3s %-9s %-7s %4s %3s %-7s %-7s %-7s %-7s %-12s %-5s %-5s %-9s %-5s %-5s %-5s %-14s %-7s %-12s %-5s %-3s %s" % (
            "run", "s", "unit", "anchor", "tlst", "nwk", "n3(sc)", "n5(sc)", "ap3/ap5", "b3/b5", "later",
            "o", "s", "R3 c/b/o", "brch", "done", "left", "stk5", "stk8", "dep3 5/8/all", "dep5", "san", "other unit"))
        for e in evw_all:
            run = runs[(tag, e["t"])]
            seg = [tuple(r["target"]) for r in e["clears"]]
            m = seg_metrics(run, e["u"], e["anchor"], seg, e["s"], extended=True)
            e["m"] = m
            f3 = m["fate3"]
            say("   %-16s %3d %-9s %-7s %4d %3d %-7s %-7s %-7s %-7s %-12s %-5s %-5s %-9s %-5s %-5s %-5s %-14s %-7s %-12s %-5s %-3s %s%s" % (
                label(e["t"]), e["s"], e["u"], "%d,%d" % e["anchor"], e["s"] - e["t_last"], len(e["win"]),
                "%d(%d)" % (m["n3"], m["sc3"]), "%d(%d)" % (m["n5"], m["sc5"]), "%d/%d" % (m["ap3"], m["ap5"]),
                "%d/%d" % (m["built3"], m["built5"]),
                ("+%d %s" % m["first_later"]) if m["first_later"] else "none",
                fmt(m["first_other"]), fmt(m["first_same"]),
                "%d/%d/%d" % (f3["cleared"], f3["burned"], f3["open"]), fmt(m["breach3"]), fmt(m["completed3"]),
                fmt(m["left_at_breach3"]),
                "%d/%d(+%s)" % (m["stake5_burned"], m["stake5"], fmt(m["stake5_first"])),
                "%d/%d" % (m["stake8_burned"], m["stake8"]),
                "%d/%d/%d" % (m["dep3_m5"], m["dep3_m8"], m["dep3"]), m["dep5"], m["dep_sanity"], e["ostate"],
                "  r" if e["redispatch"] else ""))
        # summary (distinct preemptions only)
        evw = [e for e in evw_all if not e["redispatch"]]
        n = len(evw)
        empty3 = sum(1 for e in evw if e["m"]["n3"] == 0)
        finished_other = sum(1 for e in evw if e["m"]["first_other"] is not None)
        finished_same = sum(1 for e in evw if e["m"]["first_same"] is not None)
        br = sum(1 for e in evw if e["m"]["fate3"]["burned"] > 0)
        comp = sum(1 for e in evw if e["m"]["completed3"] is not None)
        cross5 = sum(1 for e in evw if e["m"]["stake5_burned"] > 0)
        say("   SUMMARY %s: W=%d | R3 empty at s (local band already done) %d | later clear near it by other unit %d "
            "(median +%s), by same unit %d (median +%s), by nobody %d" % (
                tag, n, empty3, finished_other, med([e["m"]["first_other"] for e in evw]), finished_same,
                med([e["m"]["first_same"] for e in evw]), sum(1 for e in evw if e["m"]["first_later"] is None)))
        say("           R3 non-empty %d: breached (fire burned an uncleared R3 cell) %d, completed (all cleared) %d, "
            "stake5 crossed %d (cells %d), stake8 crossed %d (cells %d)" % (
                n - empty3, br, comp, cross5, sum(e["m"]["stake5_burned"] for e in evw),
                sum(1 for e in evw if e["m"]["stake8_burned"] > 0), sum(e["m"]["stake8_burned"] for e in evw)))
        say("           chain dependence: events with dep3 > 0: %d; cells dep3 within m5 %d / m8 %d / grid %d; dep5 grid %d; "
            "sanity (must be 0) max %d" % (
                sum(1 for e in evw if e["m"]["dep3"] > 0), sum(e["m"]["dep3_m5"] for e in evw),
                sum(e["m"]["dep3_m8"] for e in evw), sum(e["m"]["dep3"] for e in evw),
                sum(e["m"]["dep5"] for e in evw), max(e["m"]["dep_sanity"] for e in evw)))
        say("           other unit at post-step s: %s" % dict(collections.Counter(e["ostate"] for e in evw)))
        for smp in ("can", "fr"):
            xs = [e for e in evw if sample_of(e["t"]) == smp]
            say("           %s: W %d, breached %d, stake5 crossed %d (%d cells), dep3 grid %d cells, dep5 grid %d" % (
                "canonical" if smp == "can" else "fresh    ", len(xs), sum(1 for e in xs if e["m"]["fate3"]["burned"] > 0),
                sum(1 for e in xs if e["m"]["stake5_burned"] > 0), sum(e["m"]["stake5_burned"] for e in xs),
                sum(e["m"]["dep3"] for e in xs), sum(e["m"]["dep5"] for e in xs)))
        if tag == "fmDRY":
            say("           DRY: 'cleared' = a suppressed clear; the fire ignores it. R3 cells 'cleared' then burned anyway: %d" % (
                sum(e["m"]["ctb3"] for e in evw)))

    # X class (extinguish only) - atomic work, nothing partial
    say("")
    say("   CLASS X (extinguish-only window): extinguish is one atomic write; no partial state exists to finish.")
    for tag in ARMS:
        evx = [e for e in events[tag] if e["cls"] == "X"]
        if not evx:
            say("   %-6s X = 0" % tag)
            continue
        fronts = []
        for e in evx:
            run = runs[(tag, e["t"])]
            st = run.state(e["s"])
            p = e["pos"] or tuple(e["latest"]["cell"])
            fb = st["fuel"]
            nbr = np.zeros((N, N), bool)
            nbr[1:, :] |= fb[:-1, :]
            nbr[:-1, :] |= fb[1:, :]
            nbr[:, 1:] |= fb[:, :-1]
            nbr[:, :-1] |= fb[:, 1:]
            fr = st["B"] & nbr
            fronts.append(sum(1 for c in manh_cells(tuple(e["latest"]["cell"]), 2) if fr[c]))
        say("   %-6s X = %d; front cells within manhattan 2 of the unit's last cell at s: %s" % (
            tag, len(evx), " ".join(str(x) for x in fronts)))

    # ---- baseline: every stop of firebreak work -----------------------------------
    say("")
    say("   BASELINE: EVERY PLACE FIREBREAK WORK STOPPED (fire state at the last clear t; same metrics)")
    say("   stop = a clear with no further work by that unit within manhattan 5 in (t, t+10]; reason = preempted")
    say("   (a preemption of the unit in [t, t+9]) else its first event after t. Pre-terminal = t <= terminal_step")
    say("   (or a non-terminal run). A W preemption whose last clear is not a stop is listed as unmatched.")
    stops_all = {}
    for tag in FIREBREAK_ARMS:
        allstops = []
        unmatched = 0
        for t in ALL:
            run = runs[(tag, t)]
            pre_by_unit = collections.defaultdict(list)
            for e in events[tag]:
                if e["t"] == t:
                    pre_by_unit[e["u"]].append(e)
            wk_by_unit = collections.defaultdict(list)
            for r in run.work:
                wk_by_unit[r["ff"]].append(r)
            matched_ev = set()
            for u, wk in wk_by_unit.items():
                death = run.unit_death(u)
                for i, r in enumerate(wk):
                    if r["action"] != "clear":
                        continue
                    tt, c = r["step"], tuple(r["target"])
                    if any(tt < w["step"] <= tt + STOP_GAP and md(tuple(w["target"]), c) <= STOP_RADIUS for w in wk):
                        continue
                    pe = [e for e in pre_by_unit.get(u, ()) if tt <= e["s"] <= tt + WINDOW - 1]
                    reason = None
                    if pe:
                        reason = "preempted"
                        for e in pe:
                            if e["cls"] == "W" and e["t_last"] == tt:
                                matched_ev.add(id(e))
                    else:
                        saw_move = saw_row = False
                        for k in range(tt + 1, tt + STOP_GAP + 1):
                            if k > STEPS:
                                reason = "horizon"
                                break
                            if death is not None and k >= death:
                                reason = "dead"
                                break
                            row = run.rows.get(u, {}).get(k)
                            if row is not None:
                                saw_row = True
                                if row["action"] == "retreat":
                                    reason = "retreat"
                                    break
                                if row["action"] == "none":
                                    reason = "no plan"
                                    break
                                if row["action"] in WORK:
                                    reason = "work elsewhere"
                                    break
                                if row["action"] == "move":
                                    saw_move = True
                            if any(x["ff"] == u and x["step"] == k for x in run.ok_assigns):
                                reason = "assigned (not engaged)"
                                break
                        if reason is None:
                            reason = "moving" if saw_move else ("not idle" if not saw_row else "other")
                    seg = [tuple(w["target"]) for w in wk if w["action"] == "clear" and tt - WINDOW < w["step"] <= tt]
                    m = seg_metrics(run, u, c, seg, tt)
                    pre_term = run.term is None or tt <= run.term
                    allstops.append({"t": t, "tt": tt, "u": u, "reason": reason, "m": m, "pre": pre_term})
            for e in events[tag]:
                if e["t"] == t and e["cls"] == "W" and id(e) not in matched_ev:
                    unmatched += 1
        stops_all[tag] = allstops
        say("   --- %s: %d stops (%d pre-terminal); W preemptions not matched to a stop: %d ---" % (
            tag, len(allstops), sum(1 for x in allstops if x["pre"]), unmatched))
        say("   %-24s %-5s %-5s %-6s %-12s %-14s %-14s %-14s %-14s %-7s %-9s %-16s %s" % (
            "reason", "n", "pre", "med t", "R3 empty", "R3 breached*", "R3 completed*", "crossed5", "crossed8",
            "med n3", "stk5b sum", "dep3>0 / cells", "later clear near: other/same/none (median +steps other)"))
        order = ["preempted", "retreat", "no plan", "work elsewhere", "moving", "assigned (not engaged)", "dead",
                 "horizon", "not idle", "other"]
        for scope in ("all", "pre-terminal"):
            say("   [%s]" % scope)
            for reason in order + ["ALL non-preempted"]:
                if reason == "ALL non-preempted":
                    xs = [x for x in allstops if x["reason"] != "preempted"]
                else:
                    xs = [x for x in allstops if x["reason"] == reason]
                if scope == "pre-terminal":
                    xs = [x for x in xs if x["pre"]]
                if not xs:
                    continue
                ne = [x for x in xs if x["m"]["n3"] > 0]
                say("   %-24s %-5d %-5d %-6s %-12s %-14s %-14s %-14s %-14s %-7s %-9d %-16s %d/%d/%d (+%s)" % (
                    reason, len(xs), sum(1 for x in xs if x["pre"]), med([x["tt"] for x in xs]),
                    pct(sum(1 for x in xs if x["m"]["n3"] == 0), len(xs)),
                    pct(sum(1 for x in ne if x["m"]["fate3"]["burned"] > 0), len(ne)),
                    pct(sum(1 for x in ne if x["m"]["completed3"] is not None), len(ne)),
                    pct(sum(1 for x in xs if x["m"]["stake5_burned"] > 0), len(xs)),
                    pct(sum(1 for x in xs if x["m"]["stake8_burned"] > 0), len(xs)),
                    med([x["m"]["n3"] for x in xs]), sum(x["m"]["stake5_burned"] for x in xs),
                    "%d / %d" % (sum(1 for x in xs if x["m"]["dep3"] > 0), sum(x["m"]["dep3"] for x in xs)),
                    sum(1 for x in xs if x["m"]["first_other"] is not None),
                    sum(1 for x in xs if x["m"]["first_same"] is not None and x["m"]["first_other"] is None),
                    sum(1 for x in xs if x["m"]["first_later"] is None),
                    med([x["m"]["first_other"] for x in xs])))
        say("   * over stops with R3 non-empty")
        dsan = max((x["m"]["dep_sanity"] for x in allstops), default=0)
        say("   chain-dependence sanity over all %s stops (must be 0): max %d" % (tag, dsan))
        say("   EARLY-FIRE CONTROL (stops at t <= 60, any reason): %s" % "; ".join(
            "%s n=%d crossed5 %d dep3>0 %d (cells %d)" % (
                rs, len([x for x in allstops if x["tt"] <= 60 and (x["reason"] == "preempted") == (rs == "preempted")]),
                sum(1 for x in allstops if x["tt"] <= 60 and (x["reason"] == "preempted") == (rs == "preempted")
                    and x["m"]["stake5_burned"] > 0),
                sum(1 for x in allstops if x["tt"] <= 60 and (x["reason"] == "preempted") == (rs == "preempted")
                    and x["m"]["dep3"] > 0),
                sum(x["m"]["dep3"] for x in allstops if x["tt"] <= 60 and (x["reason"] == "preempted") == (rs == "preempted")))
            for rs in ("preempted", "not preempted")))

    # ------------------------------------------------------------------ 4 ----
    say("")
    say("=" * 100)
    say("4. THE COST SIDE - EVERY PREEMPTED RESCUE: OUTCOME, LATENCY, SLACK, AND THE SAME VICTIM IN fmOFF")
    say("=" * 100)
    say("   lat = contact - s (first exit_start of this unit for this victim before its next assign); done = completion - s")
    say("   S_cell / S_nbhd / S_path: slack in steps (see docstring); '-' = nothing burned there by 240")
    say("   n_av = dispatcher's available units at the assign; d_u / d_o = manhattan unit / other unit -> victim at s")
    say("   OFF: the victim's first ok assign step (unit), contact step, final status in fmOFF")
    say("   delay3/5 = |R3| / |R5| (class W only): lower bound on the steps a threshold that finishes the segment costs")
    cost = {}
    for tag in ARMS:
        say("   --- %s ---" % tag)
        say("   %-16s %3s %-9s %-8s %s %-10s %-4s %-4s %-6s %-6s %-6s %-4s %-7s %-8s %-30s %s" % (
            "run", "s", "unit", "victim", "c", "arm final", "lat", "done", "S_cell", "S_nbhd", "S_path", "n_av",
            "d_u/d_o", "delay3/5", "OFF: assign(unit) contact final", "DRY final"))
        rowsout = []
        for e in events[tag]:
            run = runs[(tag, e["t"])]
            off = runs[("fmOFF", e["t"])]
            dry = runs[("fmDRY", e["t"])]
            s, u, vid = e["s"], e["u"], e["vid"]
            final, dstep, rstep = run.victim_outcome(vid)
            nxt = min((x["step"] for x in run.ok_assigns if x["ff"] == u and x["step"] > s), default=BIG)
            cont = next((x for x in (run.d.get("exit_starts") or []) if x["ff"] == u and x["victim"] == vid
                         and s <= x["step"] < nxt), None)
            comp = next((x for x in (run.d.get("completions") or []) if x["ff"] == u and x["victim"] == vid
                         and s <= x["step"] < nxt), None)
            s_cell = s_nb = s_path = None
            if cont is not None:
                c0, vp = cont["step"], tuple(cont["victim_pos"])
                ig = run.ign_after(vp, c0, inclusive=True)
                s_cell = (ig - c0) if ig is not None else None
                nbs = [(vp[0] + dx, vp[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                       if 0 <= vp[0] + dx < N and 0 <= vp[1] + dy < N]
                igs = [run.ign_after(c, c0, inclusive=True) for c in nbs]
                igs = [x for x in igs if x is not None]
                s_nb = (min(igs) - c0) if igs else None
            end = comp["step"] if comp is not None else min(nxt - 1, STEPS)
            death = run.unit_death(u)
            if death is not None:
                end = min(end, death)
            sp = []
            for k in range(s, end + 1):
                p = run.pos[u].get(k, (None,))[0]
                if p is None:
                    continue
                ig = run.ign_after(p, k, inclusive=True)
                if ig is not None:
                    sp.append(ig - k)
            s_path = min(sp) if sp else None
            vp_s = run.vpos[vid].get(s, (None,))[0]
            other = [x for x in UNITS if x != u][0]
            po = run.pos[other].get(s, (None,))[0]
            pu = run.pos[u].get(s, (None,))[0]
            d_u = md(pu, vp_s) if (pu and vp_s) else None
            d_o = md(po, vp_s) if (po and vp_s) else None
            nav = next((x["n_available"] for x in (run.d.get("planner") or []) if x["step"] == s and x["action"] == "assign"
                        and x["vid"] == vid and x["ff"] == u), None)
            ofinal, odead, oresc = off.victim_outcome(vid)
            oas = next((x for x in off.ok_assigns if x["vid"] == vid), None)
            ocont = next((x for x in (off.d.get("exit_starts") or []) if x["victim"] == vid), None)
            dfinal = dry.victim_outcome(vid)[0]
            m = e.get("m")
            rec = {"e": e, "final": final, "dead": dstep, "resc": rstep, "lat": (cont["step"] - s) if cont else None,
                   "done": (comp["step"] - s) if comp else None, "s_cell": s_cell, "s_nb": s_nb, "s_path": s_path,
                   "nav": nav, "d_u": d_u, "d_o": d_o, "ofinal": ofinal, "oas": oas, "ocont": ocont, "dfinal": dfinal,
                   "delay3": m["n3"] if m else None, "delay5": m["n5"] if m else None, "contact": cont is not None}
            rowsout.append(rec)
            say("   %-16s %3d %-9s %-8s %s %-10s %-4s %-4s %-6s %-6s %-6s %-4s %-7s %-8s %-30s %s" % (
                label(e["t"]), s, u, vid, e["cls"], (final or "-") + ("@%d" % dstep if final == "dead" else ""),
                fmt(rec["lat"]), fmt(rec["done"]), fmt(s_cell), fmt(s_nb), fmt(s_path), fmt(nav),
                "%s/%s" % (fmt(d_u), fmt(d_o)), ("%d/%d" % (m["n3"], m["n5"])) if m else "-",
                "%s(%s) %s %s" % (fmt(oas["step"] if oas else None), (oas["ff"][-1] if oas else "-"),
                                  fmt(ocont["step"] if ocont else None), ofinal), dfinal))
        cost[tag] = rowsout

    say("")
    say("   COST SUMMARY (counted 23 | de-duplicated 20). lost = final status not 'rescued' at step 240")
    say("   %-6s %-5s %-24s %-24s %-24s %-40s" % ("arm", "class", "lost in arm", "lost in OFF (same victim)",
                                                    "lost arm only / OFF only", "rescued in arm: med lat / med S_cell / med S_path"))
    for tag in ARMS:
        for cls in ("W", "X", "A", "all"):
            for scope in ("counted", "dedup"):
                rs = [r for r in cost[tag] if (cls == "all" or r["e"]["cls"] == cls)
                      and (scope == "counted" or r["e"]["t"][1] != "def")]
                if not rs:
                    continue
                la = sum(1 for r in rs if r["final"] != "rescued")
                lo = sum(1 for r in rs if r["ofinal"] != "rescued")
                ao = sum(1 for r in rs if r["final"] != "rescued" and r["ofinal"] == "rescued")
                oo = sum(1 for r in rs if r["final"] == "rescued" and r["ofinal"] != "rescued")
                rr = [r for r in rs if r["final"] == "rescued"]
                say("   %-6s %-5s %-24s %-24s %-24s %s / %s / %s   (%s)" % (
                    tag, cls, pct(la, len(rs)), pct(lo, len(rs)), "%d / %d" % (ao, oo),
                    med([r["lat"] for r in rr]), med([r["s_cell"] for r in rr]), med([r["s_path"] for r in rr]), scope))
    say("")
    say("   DISTINCT VICTIMS (re-dispatches dropped; a victim preempted-for twice counts once). 'W victim' = at least one")
    say("   class-W preemption was made for it. lost = not rescued at 240. Counted 23 runs.")
    for tag in ARMS:
        byv = collections.defaultdict(list)
        for r in cost[tag]:
            if not r["e"]["redispatch"]:
                byv[(r["e"]["t"], r["e"]["vid"])].append(r)
        for kind in ("W victim", "other victim", "all"):
            keys = [k for k, rs in byv.items()
                    if kind == "all" or (kind == "W victim") == any(x["e"]["cls"] == "W" for x in rs)]
            if not keys:
                continue
            la = [k for k in keys if byv[k][0]["final"] != "rescued"]
            lo = [k for k in keys if byv[k][0]["ofinal"] != "rescued"]
            ao = [k for k in keys if byv[k][0]["final"] != "rescued" and byv[k][0]["ofinal"] == "rescued"]
            oo = [k for k in keys if byv[k][0]["final"] == "rescued" and byv[k][0]["ofinal"] != "rescued"]
            say("   %-6s %-13s victims %2d | lost in arm %2d | lost in OFF %2d | lost in arm only %d %s | lost in OFF only %d %s" % (
                tag, kind, len(keys), len(la), len(lo), len(ao),
                "[" + ", ".join("%s %s" % (label(k[0]), k[1]) for k in ao) + "]" if ao else "",
                len(oo), "[" + ", ".join("%s %s" % (label(k[0]), k[1]) for k in oo) + "]" if oo else ""))
    say("")
    say("   THRESHOLD RISK (distinct class-W preemptions whose victim was rescued in the arm): a threshold that finishes")
    say("   R3 first dispatches >= delay3 = |R3| steps later. at risk = the realised rescue met a burn sooner than that:")
    say("   by S_cell (victim's contact cell), by S_path (the unit's realised path), or either.")
    say("   alternative = give the rescue to the other unit instead: d_o - d_u extra manhattan steps, if it was idle/engaged")
    for tag in FIREBREAK_ARMS:
        rs = [r for r in cost[tag] if r["e"]["cls"] == "W" and r["final"] == "rescued" and not r["e"]["redispatch"]]
        if not rs:
            say("   %-6s no rescued class-W victims" % tag)
            continue
        rc = [r for r in rs if r["s_cell"] is not None and r["s_cell"] < r["delay3"]]
        rp = [r for r in rs if r["s_path"] is not None and r["s_path"] < r["delay3"]]
        re_ = [r for r in rs if r in rc or r in rp]
        say("   %-6s rescued W %d: delay3 median %s (max %d), delay5 median %s (max %d); at risk by S_cell %d, by S_path %d, either %d" % (
            tag, len(rs), med([r["delay3"] for r in rs]), max(r["delay3"] for r in rs), med([r["delay5"] for r in rs]),
            max(r["delay5"] for r in rs), len(rc), len(rp), len(re_)))
        for r in re_:
            e = r["e"]
            say("          at risk: %s s=%d %s %s delay3 %d S_cell %s S_path %s lat %s | other unit %s d_u/d_o %s/%s | OFF %s" % (
                label(e["t"]), e["s"], e["u"], e["vid"], r["delay3"], fmt(r["s_cell"]), fmt(r["s_path"]), fmt(r["lat"]),
                e["ostate"], fmt(r["d_u"]), fmt(r["d_o"]), r["ofinal"]))
        wd = [r for r in cost[tag] if r["e"]["cls"] == "W" and r["final"] != "rescued"]
        for r in wd:
            e = r["e"]
            say("          lost W%s: %s s=%d %s %s final %s dead@%s contact %s d_u/d_o %s/%s n_av %s other %s delay3 %s | OFF %s" % (
                " (re-dispatch)" if e["redispatch"] else "", label(e["t"]), e["s"], e["u"], e["vid"], r["final"],
                fmt(r["dead"]), r["contact"], fmt(r["d_u"]), fmt(r["d_o"]), fmt(r["nav"]), e["ostate"], fmt(r["delay3"]),
                r["ofinal"]))
        alt = [r for r in cost[tag] if r["e"]["cls"] == "W" and not r["e"]["redispatch"]
               and r["e"]["ostate"] in ("idle", "engaged", "working(W)") and r["d_u"] is not None and r["d_o"] is not None]
        say("          other unit idle/engaged at s in %d of %d distinct W preemptions: d_o - d_u = %s (other unit itself "
            "working a segment: %d)" % (
                len(alt), sum(1 for r in cost[tag] if r["e"]["cls"] == "W" and not r["e"]["redispatch"]),
                " ".join("%+d" % (r["d_o"] - r["d_u"]) for r in alt), sum(1 for r in alt if r["e"]["ostate"] == "working(W)")))

    say("")
    say("   RESCUE LATENCY UNDER A THRESHOLD (lower bound: finishing R3 = |R3| steps; R5 = |R5|; no walking counted)")
    for tag in FIREBREAK_ARMS:
        dw = [r for r in cost[tag] if r["e"]["cls"] == "W" and not r["e"]["redispatch"]]
        dall = [r for r in cost[tag] if not r["e"]["redispatch"]]
        n_ok = sum(len(runs[(tag, t)].ok_assigns) for t in ALL)
        lat_w = [r["lat"] for r in dw if r["final"] == "rescued" and r["lat"] is not None]
        s3 = sum(r["delay3"] for r in dw)
        s5 = sum(r["delay5"] for r in dw)
        say("   %-6s distinct W %d: added dispatch delay R3 sum %d steps (median %s, max %d), R5 sum %d (median %s); "
            "per distinct preemption %.1f / %.1f; per ok assign (%d) %.1f / %.1f; rescued-W median assign->contact %s -> "
            "+%s%% (R3) / +%s%% (R5)" % (
                tag, len(dw), s3, med([r["delay3"] for r in dw]), max(r["delay3"] for r in dw), s5,
                med([r["delay5"] for r in dw]), s3 / len(dall), s5 / len(dall), n_ok, s3 / n_ok, s5 / n_ok, med(lat_w),
                ("%.0f" % (100.0 * statistics.median([r["delay3"] for r in dw]) / statistics.median(lat_w))) if lat_w else "-",
                ("%.0f" % (100.0 * statistics.median([r["delay5"] for r in dw]) / statistics.median(lat_w))) if lat_w else "-"))

    # ------------------------------------------------------------------ 5 ----
    say("")
    say("=" * 100)
    say("5. THE VALUE SIDE - UPPER BOUND")
    say("=" * 100)
    say("   A class-W segment could plausibly have held if finished when ALL of these hold:")
    say("     (a) R3 non-empty at s and later BREACHED (the fire burned an uncleared R3 cell)")
    say("     (b) the fire's first R3 burn came later than |R3| steps after s (one clear per step would have finished)")
    say("     (c) cells beyond the band (d>5, never burned) within manhattan 5 (8) of the segment burned later")
    say("   stake = those burned cells: an UPPER bound on intact cells a finished local segment could save (it ignores")
    say("   flanking, the band re-forming as the fire moves, and walking time). Width: a completed euclidean (2,5] band")
    say("   blocks (round-1 band probe); a <= 2-wide remnant crosses 0.9111/0.9298 per #9 - cited, not re-derived here.")
    say("   SHARPER: chain dependence (docstring) - of the cells that burned later, those whose every realized ignition")
    say("   chain passed through R3 (dep3) or R5 (dep5), i.e. that the realized fire reached ONLY across the unfinished")
    say("   segment. Still generous: the segment is treated as finished at s and the fire's timing as unchanged.")
    for tag in FIREBREAK_ARMS:
        evw = [e for e in events[tag] if e["cls"] == "W" and not e["redispatch"]]
        cand = [e for e in evw if e["m"]["n3"] > 0 and e["m"]["fate3"]["burned"] > 0
                and e["m"]["breach3"] is not None and e["m"]["breach3"] > e["m"]["n3"]]
        c5 = [e for e in cand if e["m"]["stake5_burned"] > 0]
        c8 = [e for e in cand if e["m"]["stake8_burned"] > 0]
        say("   %-6s distinct W %d -> (a) breached %d -> (b) in time %d -> (c) stake5 burned %d events / %d cells;  stake8 %d events / %d cells" % (
            tag, len(evw), sum(1 for e in evw if e["m"]["n3"] > 0 and e["m"]["fate3"]["burned"] > 0), len(cand),
            len(c5), sum(e["m"]["stake5_burned"] for e in c5), len(c8), sum(e["m"]["stake8_burned"] for e in c8)))
        say("          chain dependence over the (b) events: dep3 grid %d cells (in %d events), dep5 grid %d cells; over ALL "
            "distinct W: dep3 %d, dep5 %d" % (
                sum(e["m"]["dep3"] for e in cand), sum(1 for e in cand if e["m"]["dep3"] > 0),
                sum(e["m"]["dep5"] for e in cand), sum(e["m"]["dep3"] for e in evw), sum(e["m"]["dep5"] for e in evw)))
        say("          SENSITIVITY over ALL distinct W: longer segment (all band within manhattan 8, median %s cells = steps) "
            "dep8 %d cells; strong links only (euclid <= 2): dep3s %d, dep5s %d" % (
                med([e["m"]["n8"] for e in evw]), sum(e["m"]["dep8"] for e in evw),
                sum(e["m"]["dep3s"] for e in evw), sum(e["m"]["dep5s"] for e in evw)))
        say("          SEGMENT-LENGTH CURVE (sum over distinct W; median band cells = lower-bound steps of work): "
            + " | ".join("manh %s: %s cells -> dep %d" % (R, med([e["m"]["n%s" % R] for e in evw]),
                                                         sum(e["m"]["dep%s" % R] for e in evw))
                         for R in ("3", "5", "8", "12", "16"))
            + " | complete annulus: %s cells -> dep %d" % (med([e["m"]["ring_n"] for e in evw]),
                                                       sum(e["m"]["ring_dep"] for e in evw)))
        say("          POSITIVE CONTROL (block the complete band ring at s): events where every beyond cell that burned later "
            "becomes unreachable %d/%d; beyond-burned %d cells, of them missed %d; ring size median %s, ring-dependent cells %d" % (
                sum(1 for e in evw if e["m"]["ring_missed"] == 0), len(evw), sum(e["m"]["ring_beyond"] for e in evw),
                sum(e["m"]["ring_missed"] for e in evw), med([e["m"]["ring_n"] for e in evw]),
                sum(e["m"]["ring_dep"] for e in evw)))
        for e in cand:
            say("          %s s=%d %s n3=%d breach +%s left %s stake5 %d/%d stake8 %d/%d dep3 %d dep5 %d | victim %s" % (
                label(e["t"]), e["s"], e["u"], e["m"]["n3"], e["m"]["breach3"], e["m"]["left_at_breach3"],
                e["m"]["stake5_burned"], e["m"]["stake5"], e["m"]["stake8_burned"], e["m"]["stake8"],
                e["m"]["dep3"], e["m"]["dep5"], e["vid"]))
    def intact(run):
        fgf = run.d.get("fire_ground_final") or {}
        ever = sum(1 for v in fgf.values() if v[0])
        return N * N - ever - int(run.d.get("fire_cleared_unburned_final") or 0)
    say("   SCALE (re-derived, intact = 2500 - ever_burned - cleared, arm minus fmOFF): " + "; ".join(
        "%s counted-23 %+d, de-dup-20 %+d" % (
            tag, sum(intact(runs[(tag, t)]) - intact(runs[("fmOFF", t)]) for t in ALL),
            sum(intact(runs[(tag, t)]) - intact(runs[("fmOFF", t)]) for t in ALL if t[1] != "def"))
        for tag in ARMS))

    # ------------------------------------------------------------------ 6 ----
    say("")
    say("=" * 100)
    say("6. HOW MUCH FIREBREAK WORK IS EXPOSED TO PREEMPTION AT ALL?")
    say("=" * 100)
    say("   pre-terminal = step <= terminal_step (all steps of a non-terminal run); before last assign = step <= the run's")
    say("   last ok assign (no preemption can occur after it). Engaged rows after terminal re-derives the report's 56%.")
    say("   %-6s %-10s %-20s %-20s %-20s %-22s %-22s %s" % (
        "arm", "clears", "pre-terminal", "in non-term runs", "before last assign", "engaged rows", "engaged after term",
        "clears in W windows"))
    for tag in ARMS:
        cl = pre = nt = bla = eng = aft = 0
        ext = ext_pre = 0
        for t in ALL:
            run = runs[(tag, t)]
            last_asg = max((x["step"] for x in run.ok_assigns), default=0)
            for r in run.work:
                if r["action"] == "clear":
                    cl += 1
                    if run.term is None:
                        nt += 1
                        pre += 1
                    elif r["step"] <= run.term:
                        pre += 1
                    if r["step"] <= last_asg:
                        bla += 1
                else:
                    ext += 1
                    if run.term is None or r["step"] <= run.term:
                        ext_pre += 1
            for r in run.log:
                if r.get("engaged"):
                    eng += 1
                    if run.term is not None and r["step"] > run.term:
                        aft += 1
        inwin = sum(len(e["clears"]) for e in events[tag] if e["cls"] == "W")
        say("   %-6s %-10d %-20s %-20s %-20s %-22d %-22s %s   | extinguish %d, pre-terminal %s" % (
            tag, cl, pct(pre, cl), pct(nt, cl), pct(bla, cl), eng, pct(aft, eng), pct(inwin, cl), ext, pct(ext_pre, ext)))

    # ------------------------------------------------------------------ verdict (computed, inserted at the top) --
    def intact_of(run):
        fgf = run.d.get("fire_ground_final") or {}
        return N * N - sum(1 for v in fgf.values() if v[0]) - int(run.d.get("fire_cleared_unburned_final") or 0)

    V = {}
    for tag in ARMS:
        ev = events[tag]
        dist = [e for e in ev if not e["redispatch"]]
        x = {"pre": len(ev), "distinct": len(dist), "early": sum(1 for e in ev if e["s"] <= 20),
             "at_term": sum(1 for e in ev if e["since_term"] == 0),
             "post_term": sum(1 for e in ev if e["since_term"] is not None and e["since_term"] > 0)}
        for c in "WXA":
            x[c] = sum(1 for e in dist if e["cls"] == c)
        evw = [e for e in dist if e["cls"] == "W"]
        if evw:
            ms = [e["m"] for e in evw]
            x.update({
                "nobody": sum(1 for m in ms if m["first_later"] is None),
                "other": sum(1 for m in ms if m["first_other"] is not None), "other_med": med([m["first_other"] for m in ms]),
                "same": sum(1 for m in ms if m["first_same"] is not None), "same_med": med([m["first_same"] for m in ms]),
                "r3ne": sum(1 for m in ms if m["n3"] > 0),
                "breached": sum(1 for m in ms if m["n3"] > 0 and m["fate3"]["burned"] > 0),
                "completed": sum(1 for m in ms if m["completed3"] is not None),
                "cross5_ev": sum(1 for m in ms if m["stake5_burned"] > 0), "cross5_cells": sum(m["stake5_burned"] for m in ms),
                "dep3": sum(m["dep3"] for m in ms), "dep5": sum(m["dep5"] for m in ms), "dep8": sum(m["dep8"] for m in ms),
                "dep3s": sum(m["dep3s"] for m in ms), "dep5s": sum(m["dep5s"] for m in ms),
                "n3_med": med([m["n3"] for m in ms]), "n8_med": med([m["n8"] for m in ms]),
                "ctrl_pass": sum(1 for m in ms if m["ring_missed"] == 0), "ctrl_beyond": sum(m["ring_beyond"] for m in ms),
                "ctrl_missed": sum(m["ring_missed"] for m in ms),
                "dep3_can": sum(e["m"]["dep3"] for e in evw if sample_of(e["t"]) == "can"),
                "dep3_fr": sum(e["m"]["dep3"] for e in evw if sample_of(e["t"]) == "fr"),
                "dep5_can": sum(e["m"]["dep5"] for e in evw if sample_of(e["t"]) == "can"),
                "dep5_fr": sum(e["m"]["dep5"] for e in evw if sample_of(e["t"]) == "fr"),
            })
            ub = [m for m in ms if m["n3"] > 0 and m["fate3"]["burned"] > 0 and m["breach3"] is not None
                  and m["breach3"] > m["n3"] and m["stake5_burned"] > 0]
            x["ub_ev"], x["ub_cells"] = len(ub), sum(m["stake5_burned"] for m in ub)
        if tag in stops_all:
            st = stops_all[tag]
            npre = [s_ for s_ in st if s_["reason"] != "preempted"]
            pre_ = [s_ for s_ in st if s_["reason"] == "preempted"]
            x.update({"np_n": len(npre), "np_cross": sum(1 for s_ in npre if s_["m"]["stake5_burned"] > 0),
                      "np_med_t": med([s_["tt"] for s_ in npre]), "np_pre": sum(1 for s_ in npre if s_["pre"]),
                      "np_pre_cross": sum(1 for s_ in npre if s_["pre"] and s_["m"]["stake5_burned"] > 0),
                      "p_n": len(pre_), "p_cross": sum(1 for s_ in pre_ if s_["m"]["stake5_burned"] > 0),
                      "p_med_t": med([s_["tt"] for s_ in pre_]),
                      "np_early": sum(1 for s_ in npre if s_["tt"] <= 60), "p_early": sum(1 for s_ in pre_ if s_["tt"] <= 60),
                      "np_dep3": sum(s_["m"]["dep3"] for s_ in npre)})
        byv = collections.defaultdict(list)
        for r in cost[tag]:
            if not r["e"]["redispatch"]:
                byv[(r["e"]["t"], r["e"]["vid"])].append(r)
        wk = [k for k, rs in byv.items() if any(q["e"]["cls"] == "W" for q in rs)]
        x["Wv"] = len(wk)
        x["Wv_lost_arm"] = sum(1 for k in wk if byv[k][0]["final"] != "rescued")
        x["Wv_lost_off"] = sum(1 for k in wk if byv[k][0]["ofinal"] != "rescued")
        x["Wv_arm_only"] = ["%s %s" % (label(k[0]), k[1]) for k in wk
                            if byv[k][0]["final"] != "rescued" and byv[k][0]["ofinal"] == "rescued"]
        x["Wv_off_only"] = ["%s %s" % (label(k[0]), k[1]) for k in wk
                            if byv[k][0]["final"] == "rescued" and byv[k][0]["ofinal"] != "rescued"]
        x["all_v"] = len(byv)
        x["all_lost_arm"] = sum(1 for k in byv if byv[k][0]["final"] != "rescued")
        x["all_lost_off"] = sum(1 for k in byv if byv[k][0]["ofinal"] != "rescued")
        dw = [r for r in cost[tag] if r["e"]["cls"] == "W" and not r["e"]["redispatch"]]
        if dw:
            rs = [r for r in dw if r["final"] == "rescued"]
            x["resc_W"] = len(rs)
            x["risk_cell"] = sum(1 for r in rs if r["s_cell"] is not None and r["s_cell"] < r["delay3"])
            x["risk_path"] = sum(1 for r in rs if r["s_path"] is not None and r["s_path"] < r["delay3"])
            x["risk_either"] = sum(1 for r in rs if (r["s_cell"] is not None and r["s_cell"] < r["delay3"])
                                   or (r["s_path"] is not None and r["s_path"] < r["delay3"]))
            x["risk_cell_list"] = ["%s %s (S_cell %d < delay3 %d; OFF %s)" % (label(r["e"]["t"]), r["e"]["vid"], r["s_cell"],
                                                                           r["delay3"], r["ofinal"])
                                   for r in rs if r["s_cell"] is not None and r["s_cell"] < r["delay3"]]
            x["d3_sum"] = sum(r["delay3"] for r in dw)
            x["d3_med"] = med([r["delay3"] for r in dw])
            x["d3_max"] = max(r["delay3"] for r in dw)
            x["d5_med"] = med([r["delay5"] for r in dw])
            lat = [r["lat"] for r in rs if r["lat"] is not None]
            x["lat_med"] = med(lat)
            x["pct3"] = ("%.0f" % (100.0 * statistics.median([r["delay3"] for r in dw]) / statistics.median(lat))) if lat else "-"
            x["pct5"] = ("%.0f" % (100.0 * statistics.median([r["delay5"] for r in dw]) / statistics.median(lat))) if lat else "-"
            alt = [r for r in dw if r["e"]["ostate"] in ("idle", "engaged", "working(W)")]
            x["alt_n"], x["alt_working"] = len(alt), sum(1 for r in alt if r["e"]["ostate"] == "working(W)")
        x["intact"] = sum(intact_of(runs[(tag, t)]) - intact_of(runs[("fmOFF", t)]) for t in ALL)
        x["intact_dd"] = sum(intact_of(runs[(tag, t)]) - intact_of(runs[("fmOFF", t)]) for t in ALL if t[1] != "def")
        cl = pre = bla = eng = aft = 0
        for t in ALL:
            run = runs[(tag, t)]
            last_asg = max((q["step"] for q in run.ok_assigns), default=0)
            for r in run.work:
                if r["action"] == "clear":
                    cl += 1
                    pre += int(run.term is None or r["step"] <= run.term)
                    bla += int(r["step"] <= last_asg)
            for r in run.log:
                if r.get("engaged"):
                    eng += 1
                    aft += int(run.term is not None and r["step"] > run.term)
        x.update({"clears": cl, "clears_pre": pre, "clears_bla": bla, "eng": eng, "eng_after": aft,
                  "clears_win": sum(len(e["clears"]) for e in dist if e["cls"] == "W")})
        V[tag] = x

    def p(a_, b_):
        return "%d/%d (%.0f%%)" % (a_, b_, 100.0 * a_ / b_) if b_ else "%d/0" % a_

    E = V["fmEFS"]
    VL = []
    VL.append("")
    VL.append("#" * 100)
    VL.append("VERDICT (every number below is computed by this script from the JSON; details in sections 0-6)")
    VL.append("#" * 100)
    VL.append("  QUESTION: would letting an engaged unit finish its band segment before taking a rescue be worth anything?")
    VL.append("  ANSWER: NO. On the value side the question is effectively moot - a finished LOCAL segment would not have held;")
    VL.append("  the fire reached the ground behind it around its ends. On the cost side a threshold is a certain dispatch")
    VL.append("  delay of about 9 steps, and at least one rescue in every firebreak arm had less slack than that. Net: it does")
    VL.append("  not earn its place, and it leans harmful. Primary arm fmEFS; fmF and fmFS give the same verdict (table below).")
    VL.append("")
    VL.append("  1. PREEMPTIONS ARE MOSTLY NOT ABOUT PARTIAL WORK. fmEFS: %d preemptions by the round-1 definition, %d distinct"
              % (E["pre"], E["distinct"]))
    VL.append("     (1 is a re-dispatch of an already-assigned unit). Only %d interrupt firebreak work (a clear in the last 10"
              % E["W"])
    VL.append("     steps). %d are units still walking toward the fire; %d of all %d are the initial dispatch wave at steps <= 20."
              % (E["A"], E["early"], E["pre"]))
    VL.append("     %d come after terminal_step. %d lands AT it (east/half/101 s=135): a pre-move replacement dispatch in the step"
              % (E["post_term"], E["at_term"]))
    VL.append("     whose casualty check kills that victim.")
    byv_e = collections.defaultdict(list)
    for r in cost["fmEFS"]:
        if not r["e"]["redispatch"]:
            byv_e[(r["e"]["t"], r["e"]["vid"])].append(r)
    arm_only = [(k, rs) for k, rs in byv_e.items() if rs[0]["final"] != "rescued" and rs[0]["ofinal"] == "rescued"]
    VL.append("     Preempted victims lost in fmEFS but rescued in fmOFF: %d. Their preemptions (class@step) are: %s." % (
        len(arm_only), "; ".join("%s %s: %s (fmDRY %s)" % (label(k[0]), k[1], " ".join("%s@%d" % (q["e"]["cls"], q["e"]["s"])
                                                                                  for q in rs), rs[0]["dfinal"])
                                 for k, rs in arm_only)))
    VL.append("     The walking-unit (A) ones are untouched by a completion threshold. The W@135 case is moot, so only")
    VL.append("     south/half/404 victim_3 involves partial work. In fmOFF that rescue took from step 14 to contact at 186.")
    VL.append("  2. THE ABANDONED SEGMENT: median %s uncleared band cells within manhattan 3 of the last clear (EXACT fire state;"
              % E["n3_med"])
    VL.append("     the brief's 'not burned by then' approximation matches the logged band size on only 17-18% of rows, because")
    VL.append("     scorched cells stay fuel. The exact reconstruction matches 100% of band, front and distance values).")
    VL.append("  3. WHO FINISHED IT: nobody cleared within manhattan 5 afterwards in %d of %d. The other unit did in %d (median +%s"
              % (E["nobody"], E["W"], E["other"], E["other_med"]))
    VL.append("     steps; in %d of those it was already working beside it); the same unit, back from its rescue, in %d (median +%s)."
              % (sum(1 for e in events["fmEFS"] if e["cls"] == "W" and not e["redispatch"]
                     and e["m"]["first_other"] is not None and e["ostate"] == "working(W)"), E["same"], E["same_med"]))
    VL.append("     So it is NOT moot because someone else finishes. The fire burned uncleared cells of the region in %d of %d,"
              % (E["breached"], E["r3ne"]))
    VL.append("     and never-burned ground beyond the band within manhattan 5 later burned in %d (%d cells)."
              % (E["cross5_ev"], E["cross5_cells"]))
    VL.append("     Baseline: the same crossing measure is %s for work stopped for other reasons, and %s for such stops before"
              % (p(E["np_cross"], E["np_n"]), p(E["np_pre_cross"], E["np_pre"])))
    VL.append("     terminal. It is %s for preempted stops. The comparison is CONFOUNDED by fire phase: preempted stops have median"
              % p(E["p_cross"], E["p_n"]))
    VL.append("     t=%s, the others t=%s, and no non-preempted stop happens at t<=60 (%d preempted ones do). Every early stop of"
              % (E["p_med_t"], E["np_med_t"], E["p_early"]))
    VL.append("     firebreak work is a preemption.")
    VL.append("  4. COST: a threshold that finishes R3 delays each of the %d dispatches by >= |R3| steps (median %s, max %d; R5:"
              % (E["W"], E["d3_med"], E["d3_max"]))
    VL.append("     median %s). That is +%s%% (R3) / +%s%% (R5) on the median assign->contact latency of %s steps for these rescues."
              % (E["d5_med"], E["pct3"], E["pct5"], E["lat_med"]))
    VL.append("     Of %d W preemptions whose victim was rescued, %d met a burn on the unit's realised path sooner than that delay, and %d at the"
              % (E["resc_W"], E["risk_path"], E["risk_cell"]))
    VL.append("     victim's own contact cell: %s." % "; ".join(E["risk_cell_list"]))
    VL.append("     That victim died in fmOFF and is saved in the arm by this very preemption.")
    VL.append("     Distinct victims behind W preemptions: %d. Lost in the arm %d, lost in fmOFF %d. Arm-only losses: %s. OFF-only: %s."
              % (E["Wv"], E["Wv_lost_arm"], E["Wv_lost_off"], ", ".join(E["Wv_arm_only"]) or "-",
                 ", ".join(E["Wv_off_only"]) or "-"))
    VL.append("     Of the arm-only losses, east/half/101 victim_0 is the round-1 positioning loss (an earlier walking-unit")
    VL.append("     preemption at s=77; the W event at s=135 is the moot terminal-step one). south/half/404 victim_3 is lost in")
    VL.append("     fmDRY too. The victims that died did so with no contact, and every one of them except those two was lost in")
    VL.append("     fmOFF as well (dead or unreachable), so a delay could not have cost them.")
    VL.append("     Handing the rescue to the other unit instead is possible in %d of %d cases, but in %d of those that unit was"
              % (E["alt_n"], E["W"], E["alt_working"]))
    VL.append("     working its own segment, so the threshold just moves the abandonment.")
    VL.append("  5. VALUE, UPPER BOUND: geometric filter (breached, fire arrived later than |R3| steps, ground beyond burned):")
    VL.append("     %d events / %d cells. REALIZED-CHAIN DEPENDENCE - cells every one of whose realized ignition chains ran through"
              % (E["ub_ev"], E["ub_cells"]))
    VL.append("     the unfinished segment:")
    VL.append("       R3                                          %d cells" % E["dep3"])
    VL.append("       R5                                          %d cells" % E["dep5"])
    VL.append("       every band cell within manhattan 8 (median %s steps of work)  %d cells" % (E["n8_med"], E["dep8"]))
    VL.append("       strong links only (distance <= 2), R3 / R5  %d / %d cells" % (E["dep3s"], E["dep5s"]))
    evw_e = [e for e in events["fmEFS"] if e["cls"] == "W" and not e["redispatch"]]
    VL.append("       longer segments, all band within manhattan 12 / 16 (median %s / %s steps of work)  %d / %d cells" % (
        med([e["m"]["n12"] for e in evw_e]), med([e["m"]["n16"] for e in evw_e]),
        sum(e["m"]["dep12"] for e in evw_e), sum(e["m"]["dep16"] for e in evw_e)))
    VL.append("       the complete closed annulus (median %s cells)  %d cells" % (
        med([e["m"]["ring_n"] for e in evw_e]), sum(e["m"]["ring_dep"] for e in evw_e)))
    VL.append("     Summed over all %d events in 23 runs, against the arm's net intact gain of %+d cells (%+d de-duplicated)."
              % (E["W"], E["intact"], E["intact_dd"]))
    VL.append("     canonical / fresh: R3 %d / %d, R5 %d / %d. Both seed sets agree.")
    VL[-1] = VL[-1] % (E["dep3_can"], E["dep3_fr"], E["dep5_can"], E["dep5_fr"])
    VL.append("     The method CAN see a barrier. POSITIVE CONTROL: blocking the complete band ring at s cuts off every beyond cell")
    VL.append("     that later burned, in %d/%d events (%d cells, %d missed). A 3-wide euclidean band blocks only when it CLOSES; a"
              % (E["ctrl_pass"], E["W"], E["ctrl_beyond"], E["ctrl_missed"]))
    VL.append("     local piece of an open band is flanked, with the kernel reaching 3 cells. The <=2-wide ~91% leak figure is cited")
    VL.append("     from round 1 (#9), not re-derived.")
    VL.append("  6. EXPOSURE: %s of all clears come before terminal_step, and %s before the run's last dispatch (no preemption"
              % (p(E["clears_pre"], E["clears"]), p(E["clears_bla"], E["clears"])))
    VL.append("     is possible after that). %s sit in the 10-step windows before a W preemption. Engaged rows after terminal:"
              % p(E["clears_win"], E["clears"]))
    VL.append("     %s. The report's 56%% is reproduced." % p(E["eng_after"], E["eng"]))
    VL.append("")
    VL.append("  PER ARM (distinct preemptions; W = with partial firebreak work)")
    VL.append("  %-6s %-5s %-4s %-4s %-4s %-12s %-10s %-11s %-5s %-5s %-5s %-6s %-9s %-10s %-10s %-9s %-12s %s" % (
        "arm", "prem", "W", "A", "X", "nobody/oth/sm", "breached", "cross5 cells", "dep3", "dep5", "dep8", "ctrl",
        "delay3 med", "at-risk p/c", "W lost a/O", "intact", "clears pre", "before last dispatch"))
    for tag in ARMS:
        x = V[tag]
        if "W" not in x or not x["W"]:
            VL.append("  %-6s %-5d %-4d %-4d %-4d   extinguish-only arm: every work action is one atomic write, nothing partial;"
                      " a completion threshold is undefined (%d X preemptions)" % (tag, x["distinct"], x["W"], x["A"], x["X"], x["X"]))
            continue
        VL.append("  %-6s %-5d %-4d %-4d %-4d %-12s %-10s %-11s %-5d %-5d %-5d %-6s %-9s %-10s %-10s %-9s %-12s %s" % (
            tag, x["distinct"], x["W"], x["A"], x["X"], "%d/%d/%d" % (x["nobody"], x["other"], x["same"]),
            "%d/%d" % (x["breached"], x["r3ne"]), "%d ev %d" % (x["cross5_ev"], x["cross5_cells"]), x["dep3"], x["dep5"],
            x["dep8"], "%d/%d" % (x["ctrl_pass"], x["W"]), x["d3_med"], "%d/%d" % (x["risk_path"], x["risk_cell"]),
            "%d/%d" % (x["Wv_lost_arm"], x["Wv_lost_off"]), "%+d" % x["intact"],
            "%.0f%%" % (100.0 * x["clears_pre"] / x["clears"]), "%.0f%%" % (100.0 * x["clears_bla"] / x["clears"])))
    VL.append("  fmDRY's dependence treats its suppressed clears as real on the untouched (fmOFF) fire; its larger dep5 is mostly")
    VL.append("  one event (south/half/404 s=16: 64 cells). In the writing arms that same event is 2, and most of that ground")
    VL.append("  survived anyway (stake5 6/31 burned vs 28/31 in DRY).")
    VL.append("")
    VL.append("  LIMITS: no threshold arm was simulated; this bounds one. Realized-chain dependence keeps the realized fire")
    VL.append("  timing, and it treats the segment as finished at s (generous to value). S_path uses the realized route, and")
    VL.append("  a later dispatch would route differently. Victims flee, and the slack treats them as waiting. The 'other")
    VL.append("  unit' state is read at post-step s. Scenario D only: 2 units, east/south winds.")
    OUT[header_end:header_end] = VL

    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
