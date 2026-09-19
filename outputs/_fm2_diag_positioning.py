"""firemech round 2, Part 1 diagnosis, TASK A: THE POSITIONING LOSS (fmDRY vs fmOFF). Read-only.

usage:  _fm2_diag_positioning.py [--out outputs/_fm2_diag_positioning.txt]

Reads ONLY the harness JSON of the two arms, by explicit path:
  outputs/_ffr_fmOFF_<wind>_<rr>_<seed>.json   feature off (control)
  outputs/_ffr_fmDRY_<wind>_<rr>_<seed>.json   full configuration, every fire write suppressed
on the canonical 13 + fresh 10 tuples. Runs no simulation. No glob, no recursion, and
nothing under outputs/_firemech_rewound_20260914/ is ever opened.

FRAMES AND CONVENTIONS (all verified by code below, section 0)
  ff_steps[i], ff_bind_steps[i], victim_steps[i], uav_steps[i]  = state AFTER step i+1.
  assigns/unassigns/exit_starts/completions/planner carry the model step number
  (evaluation_timesteps_counter), i.e. the same step numbering.
  CALL POSITION of an assign at step s. Dispatch runs in three places: the pre-move
  cycle, inside the schedule (a unit's own advance, e.g. route_blocked), and the post-move
  cycle (victim detection, off-grid returns). The rule used:
    - the unit RETURNED from off-grid at s          -> its return cell (post-move)
    - reason "initial" and the unit was idle after s-1 ('available', not assigned)
                                                     -> position after step s (post-move)
    - anything else (replacement, a unit already on a rescue)
                                                     -> position after step s-1
  Section 0 checks the rule against the DRY feature log: an idle-unit initial assign is
  post-move iff that unit has a firefight_log row AT step s (its advance at s ran idle).
  The victim position at the call is read from the same frame.
  IDLE STREAK (DRY): a maximal run of consecutive per-step firefight_log rows of one unit
  (the round-1 analyzer's definition). ANCHOR = the streak's first row cell (the unit's cell
  before its first idle advance). DISPLACEMENT = manhattan(position, anchor).
  IDLE STREAK (OFF): consecutive ff_steps frames with status 'available', not assigned, not
  exiting, not dead, on grid. Anchor = the first such frame's position.
  ENGAGED AT THE CALL (preemption, round-1 definition): the unit's row at s is engaged, or it
  has no row at s and its row at s-1 is engaged.
  CONTACT = exit_starts row (ff, victim) at or after the assign; COMPLETE = completions row.
  EPISODE of an assign = from the assign to the first of: contact, the unit's next assign to
  another victim, the unit's death, the victim's death/rescue, step 240.
  FIRST DIVERGENCE of a per-step series = first step whose frame differs (value equality).
  RESCUE TIMELINE = per step, the set of events (assign ff vid reason ok) (unassign ff vid
  reason) (contact ff vid) (complete ff vid) (return ff) (planner action vid reason, non-assign
  decisions) (victim status change vid status) (unit death ff). Positions are NOT events.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
CANONICAL = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("east", "def", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
ALL = CANONICAL + FRESH
UNITS = ("ff_unit_0", "ff_unit_1")

OUT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def label(t):
    return "%s/%s/%d" % t


def fc(c):
    return "(%d,%d)" % (c[0], c[1]) if c is not None else "None"


def man(a, b):
    if a is None or b is None:
        return None
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def sgn(x):
    return "-" if x is None else ("%+d" % x)


def exit_rule(cell):
    """agents.Firefighter.advance: on reaching the victim, exit_target = nearest boundary cell by
    min(dists, key=dists.get) over {(0,y): x, (H-1,y): H-1-x, (x,0): y, (x,W-1): W-1-y} (H = W = 50;
    a tie keeps the first key in that order)."""
    if cell is None:
        return None
    x, y = cell
    dists = {(0, y): x, (49, y): 49 - x, (x, 0): y, (x, 49): 49 - y}
    return min(dists, key=dists.get)


def path(tag, t):
    return os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], t[1], t[2]))


# ------------------------------------------------------------------ run model ----
class Run:
    def __init__(self, tag, t):
        with open(path(tag, t), encoding="utf-8") as f:
            d = json.load(f)
        self.d, self.tag, self.t = d, tag, t
        self.ev = d["eval"]
        self.term = d.get("terminal_step")
        self.pos = collections.defaultdict(dict)      # ff -> step -> (pos, status, assigned, exiting, dead)
        for i, row in enumerate(d["ff_steps"]):
            for ff, p, st, asg, ex, dead in row:
                self.pos[ff][i + 1] = (tuple(p) if p is not None else None, st, bool(asg), bool(ex), bool(dead))
        self.bind = collections.defaultdict(dict)     # ff -> step -> (vid, avail, rc, offgrid)
        for i, row in enumerate(d["ff_bind_steps"]):
            for ff, vid, av, rc, og in row:
                self.bind[ff][i + 1] = (vid, bool(av), bool(rc), bool(og))
        self.vic = collections.defaultdict(dict)      # vid -> step -> (pos, status)
        for i, row in enumerate(d["victim_steps"]):
            for vid, p, st in row:
                self.vic[vid][i + 1] = (tuple(p) if p is not None else None, st)
        self.vids = sorted(self.vic)
        self.final = {v: self.vic[v][240][1] for v in self.vids}
        self.rows = collections.defaultdict(dict)     # ff -> step -> firefight_log row (DRY only)
        for r in d.get("firefight_log") or []:
            self.rows[r["ff"]][r["step"]] = r
        self.returns = {(e["ff"], e["step"]): tuple(e["cell"]) for e in d["absence_log"]
                        if e["event"] == "returned" and e.get("cell") is not None}
        self.assigns = [a for a in d["assigns"] if a["ok"]]
        self.death = {}
        for ff in UNITS:
            ds = [s for s in sorted(self.pos[ff]) if self.pos[ff][s][4]]
            self.death[ff] = ds[0] if ds else None
        self.vterm = {}                                # vid -> (step, status) first terminal frame
        for v in self.vids:
            self.vterm[v] = next(((s, self.vic[v][s][1]) for s in range(1, 241)
                                  if self.vic[v][s][1] in ("rescued", "dead", "unreachable")), None)
        # DRY idle streaks from the feature log
        self.streaks = collections.defaultdict(list)
        for ff, rows in self.rows.items():
            cur = []
            for s in sorted(rows):
                if cur and s == cur[-1] + 1:
                    cur.append(s)
                else:
                    if cur:
                        self.streaks[ff].append((cur[0], cur[-1]))
                    cur = [s]
            if cur:
                self.streaks[ff].append((cur[0], cur[-1]))
        # OFF-style idle streaks from ff_steps (both arms)
        self.idle_frames = collections.defaultdict(list)
        for ff in UNITS:
            cur = []
            for s in range(1, 241):
                p, st, asg, ex, dead = self.pos[ff][s]
                idle = (st == "available" and not asg and not ex and not dead and p is not None)
                if idle and cur and s == cur[-1] + 1:
                    cur.append(s)
                elif idle:
                    if cur:
                        self.idle_frames[ff].append((cur[0], cur[-1]))
                    cur = [s]
                else:
                    if cur:
                        self.idle_frames[ff].append((cur[0], cur[-1]))
                    cur = []
            if cur:
                self.idle_frames[ff].append((cur[0], cur[-1]))

    # --- fire (from burn_intervals: frame k burning iff a <= k < b, b None = to the horizon)
    def burning(self, k):
        if not hasattr(self, "_burn"):
            frames = [set() for _ in range(242)]
            for key, ivs in (self.d.get("burn_intervals") or {}).items():
                c = tuple(int(v) for v in key.split(","))
                for a, b in ivs:
                    for j in range(a, (241 if b is None else b)):
                        frames[j].add(c)
            self._burn = frames
        return self._burn[k]

    def fire_dist(self, cell, k):
        B = self.burning(k)
        if cell is None or not B:
            return None
        return min(abs(cell[0] - x) + abs(cell[1] - y) for x, y in B)

    def exposure(self, ff, s, end):
        """Unit path over frames s..end: min manhattan distance to a burning cell, frames at <= 1, sampled path."""
        dists, adj, samp = [], 0, []
        for k in range(s, min(end, 240) + 1):
            q = self.p(ff, k)
            fd = self.fire_dist(q, k)
            if fd is not None:
                dists.append(fd)
                adj += int(fd <= 1)
            if (k - s) % 6 == 0:
                samp.append("%d%s" % (k, fc(q)))
        return {"min_fd": min(dists) if dists else None, "adj": adj, "frames": len(dists), "path": " ".join(samp[:14])}

    # --- positions
    def p(self, ff, s):
        if s < 1:
            s = 1
        return self.pos[ff][min(s, 240)][0]

    def vp(self, vid, s):
        if s < 1:
            s = 1
        return self.vic[vid][min(s, 240)][0]

    def streak_at(self, ff, s):
        for a, b in self.streaks.get(ff, []):
            if a <= s <= b:
                return (a, b)
        return None

    def off_streak_at(self, ff, s):
        for a, b in self.idle_frames.get(ff, []):
            if a <= s <= b:
                return (a, b)
        return None

    # --- the call
    def call(self, a):
        s, ff, vid = a["step"], a["ff"], a["vid"]
        prev = self.pos[ff].get(s - 1)
        returned = (ff, s) in self.returns
        prev_idle = prev is not None and prev[1] == "available" and not prev[2] and not prev[3]
        post = returned or (a["reason"] == "initial" and prev_idle)
        idx = s if post else s - 1
        upos = self.returns[(ff, s)] if returned else self.p(ff, idx)
        vpos = self.vp(vid, idx)
        if vpos is None:
            vpos = self.vp(vid, s - 1)
        state = "returned" if returned else ("idle" if prev_idle else ("on_rescue:%s" % (prev[1] if prev else None)))
        C = {"step": s, "ff": ff, "vid": vid, "reason": a["reason"], "post": post, "idx": idx,
             "upos": upos, "vpos": vpos, "dist": man(upos, vpos), "state": state}
        # feature-log view (DRY)
        now, pr = self.rows.get(ff, {}).get(s), self.rows.get(ff, {}).get(s - 1)
        C["row_at_s"] = now is not None
        C["engaged"] = bool((now is not None and now.get("engaged")) or (now is None and pr is not None and pr.get("engaged")))
        st = self.streak_at(ff, s if now is not None else s - 1) if self.rows else None
        C["streak"] = st
        if st is not None:
            anchor = tuple(self.rows[ff][st[0]]["cell"])
            last = min(st[1], idx)
            C["anchor"] = anchor
            C["disp"] = man(upos, anchor)
            C["maxdisp"] = max([0] + [man(self.p(ff, k), anchor) for k in range(st[0], last + 1)])
            eng = [self.rows[ff][k] for k in range(st[0], last + 1) if self.rows[ff][k].get("engaged")]
            C["first_engaged"] = (eng[0]["step"], tuple(eng[0]["cell"])) if eng else None
            C["idle_len"] = last - st[0] + 1
        else:
            ost = self.off_streak_at(ff, s - 1)
            C["anchor"] = self.p(ff, ost[0]) if ost else None
            C["disp"] = man(upos, C["anchor"]) if ost else None
            C["maxdisp"] = (max([0] + [man(self.p(ff, k), C["anchor"]) for k in range(ost[0], s)])
                            if ost else None)
            C["first_engaged"] = None
            C["idle_len"] = (s - ost[0]) if ost else None
        # the other unit at the call
        o = [u for u in UNITS if u != ff][0]
        opos = self.p(o, idx)
        oav = self.bind[o].get(idx, (None, None))[1]
        orow_now, orow_pr = self.rows.get(o, {}).get(s), self.rows.get(o, {}).get(s - 1)
        if self.rows:
            if orow_now is not None:
                ostate = "engaged" if orow_now.get("engaged") else "idle-no-plan"
            elif orow_pr is not None:
                ostate = "engaged" if orow_pr.get("engaged") else "idle-no-plan"
            else:
                ostate = "not-idle"
        else:
            ostate = "standby" if oav else "not-idle"
        C["other"] = {"ff": o, "pos": opos, "avail": oav, "dist": man(opos, vpos),
                      "status": self.pos[o][max(1, idx)][1], "state": ostate}
        # the episode
        nxt = [b["step"] for b in self.assigns if b["ff"] == ff and b["step"] > s and b["vid"] != vid]
        contact = next((e["step"] for e in self.d["exit_starts"]
                        if e["ff"] == ff and e["victim"] == vid and e["step"] >= s), None)
        comp = next((e["step"] for e in self.d["completions"]
                     if e["ff"] == ff and e["victim"] == vid and e["step"] >= s), None)
        end_candidates = [x for x in (min(nxt) if nxt else None, self.death[ff],
                                      self.vterm[vid][0] if self.vterm[vid] else None) if x is not None]
        ep_end = min(end_candidates) if end_candidates else 240
        if contact is not None and contact > ep_end:
            contact = None
        if comp is not None and (contact is None or comp > 240):
            comp = comp if contact is not None else None
        C["contact"] = contact
        C["to_contact"] = (contact - s) if contact is not None else None
        C["complete"] = comp
        C["ep_end"] = ep_end
        C["ep_end_why"] = ("contact" if contact is not None else
                           "unit_dead" if self.death[ff] is not None and self.death[ff] == ep_end else
                           ("victim_%s" % self.vterm[vid][1]) if self.vterm[vid] and self.vterm[vid][0] == ep_end else
                           "reassigned" if nxt and min(nxt) == ep_end else "horizon")
        C["rb_unassigns"] = sum(1 for u in self.d["unassigns"]
                                if u["ff"] == ff and u["vid"] == vid and s <= u["step"] <= ep_end
                                and "blocked" in u["reason"])
        C["rb_frames"] = sum(1 for k in range(s, min(ep_end, 240) + 1) if self.pos[ff][k][1] == "route_blocked")
        return C

    # --- rescue timeline
    def timeline(self):
        ev = collections.defaultdict(set)
        d = self.d
        for a in d["assigns"]:
            ev[a["step"]].add(("assign", a["ff"], a["vid"], a["reason"], a["ok"]))
        for a in d["unassigns"]:
            ev[a["step"]].add(("unassign", a["ff"], a["vid"], a["reason"]))
        for a in d["exit_starts"]:
            ev[a["step"]].add(("contact", a["ff"], a["victim"]))
        for a in d["completions"]:
            ev[a["step"]].add(("complete", a["ff"], a["victim"]))
        for a in d["absence_log"]:
            if a["event"] == "returned":
                ev[a["step"]].add(("return", a["ff"]))
        for a in d["planner"]:
            if a["action"] != "assign":
                ev[a["step"]].add(("planner", a["action"], a["vid"], a["reason"]))
        for v in self.vids:
            prev = None
            for s in range(1, 241):
                st = self.vic[v][s][1]
                if st != prev:
                    ev[s].add(("vstat", v, st))
                    prev = st
        for ff in UNITS:
            if self.death[ff] is not None:
                ev[self.death[ff]].add(("ffdead", ff))
        return ev


def first_div(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i + 1
    return None if len(a) == len(b) else min(len(a), len(b)) + 1


def stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "n=0"
    return "n=%d mean %+.2f median %+.1f  (+%d / -%d / 0:%d)  min %+d max %+d" % (
        len(xs), sum(xs) / len(xs), statistics.median(xs), sum(1 for x in xs if x > 0),
        sum(1 for x in xs if x < 0), sum(1 for x in xs if x == 0), min(xs), max(xs))


def ustats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "n=0"
    return "n=%d mean %.2f median %.1f min %d max %d" % (len(xs), sum(xs) / len(xs), statistics.median(xs),
                                                          min(xs), max(xs))


# ------------------------------------------------------------------ sections ----
def section0(R):
    say("=" * 100)
    say("0. CONVENTION CHECKS (computed)")
    say("=" * 100)
    n_ok = n_bad = 0
    bad = []
    counts = collections.Counter()
    for t in ALL:
        dry = R[("fmDRY", t)]
        for a in dry.assigns:
            C = dry.call(a)
            counts[(a["reason"], C["state"].split(":")[0], "row@s" if C["row_at_s"] else "no-row@s")] += 1
            if C["state"] == "idle":
                if C["row_at_s"] == C["post"]:
                    n_ok += 1
                else:
                    n_bad += 1
                    bad.append((label(t), a))
            if C["row_at_s"]:
                # the row's cell (before acting) must be the position after s-1
                if tuple(dry.rows[a["ff"]][a["step"]]["cell"]) != dry.p(a["ff"], a["step"] - 1):
                    bad.append(("cell!=pos[s-1]", label(t), a))
    say("  DRY ok assigns by (reason, unit state before the call, feature-log row at s):")
    for k, v in sorted(counts.items()):
        say("    %3d  %s" % (v, k))
    say("  idle-unit initial assigns: post-move rule agrees with 'row at s' on %d, disagrees on %d %s"
        % (n_ok, n_bad, bad[:5]))
    spawn_eq = sum(1 for t in ALL if R[("fmOFF", t)].d["victim_spawns"] == R[("fmDRY", t)].d["victim_spawns"])
    fire_eq = sum(1 for t in ALL if R[("fmOFF", t)].d["fire_digests"] == R[("fmDRY", t)].d["fire_digests"])
    say("  victim_spawns identical OFF vs DRY: %d/23;  fire_digests identical 240/240: %d/23" % (spawn_eq, fire_eq))


def section1(R):
    say("")
    say("=" * 100)
    say("1. WHERE fmDRY DIFFERS FROM fmOFF: eval rescued / dead / firefighter_deaths, per-victim final")
    say("   status (last victim_steps frame), and which unit died when")
    say("=" * 100)
    changed = []
    resc, deaths_up, deaths_dn = {}, [], []
    say("  %-16s %-22s %-22s %s" % ("tuple", "OFF r/d/ffd term", "DRY r/d/ffd term", "differences"))
    for t in ALL:
        o, d = R[("fmOFF", t)], R[("fmDRY", t)]
        eo, ed = o.ev, d.ev
        diffs = []
        dr = ed["rescued"] - eo["rescued"]
        dd = ed["dead"] - eo["dead"]
        dff = ed["firefighter_deaths"] - eo["firefighter_deaths"]
        if dr:
            diffs.append("rescued %+d" % dr)
            resc[label(t)] = dr
        if dd:
            diffs.append("dead %+d" % dd)
        if dff:
            diffs.append("ff_deaths %+d" % dff)
            (deaths_up if dff > 0 else deaths_dn).append(label(t))
        vd = [(v, o.final[v], d.final[v]) for v in o.vids if o.final[v] != d.final[v]]
        for v, a, b in vd:
            diffs.append("%s %s->%s" % (v, a, b))
        od = {ff: o.death[ff] for ff in UNITS if o.death[ff] is not None}
        ddd = {ff: d.death[ff] for ff in UNITS if d.death[ff] is not None}
        death_note = ""
        if od != ddd:
            death_note = "  unit deaths OFF %s DRY %s" % (od, ddd)
        say("  %-16s %d/%d/%d %-12s %d/%d/%d %-12s %s%s" % (
            label(t), eo["rescued"], eo["dead"], eo["firefighter_deaths"], "t%s" % o.term,
            ed["rescued"], ed["dead"], ed["firefighter_deaths"], "t%s" % d.term, "; ".join(diffs) or "-", death_note))
        if diffs:
            changed.append(t)
    exp_resc = {"east/half/101": -1, "south/half/404": -1, "east/def/101": -1, "east/half/404": +1,
                "south/half/202": +1, "south/half/909": -1}
    exp_up = {"south/half/404", "south/half/808", "south/half/909", "east/def/303"}
    exp_dn = {"east/half/101", "south/half/202", "east/half/606"}
    say("")
    say("  ROUND-1 LIST CHECK: rescued deltas %s  (%s)" % (
        "MATCH" if resc == exp_resc else "MISMATCH", ", ".join("%s %+d" % kv for kv in sorted(resc.items()))))
    say("  ROUND-1 LIST CHECK: ff deaths +1 %s (%s);  -1 %s (%s)" % (
        "MATCH" if set(deaths_up) == exp_up else "MISMATCH", ", ".join(deaths_up),
        "MATCH" if set(deaths_dn) == exp_dn else "MISMATCH", ", ".join(deaths_dn)))
    say("  counted 23: rescued OFF %d DRY %d; de-duplicated 20 (east/def excluded): OFF %d DRY %d" % (
        sum(R[("fmOFF", t)].ev["rescued"] for t in ALL), sum(R[("fmDRY", t)].ev["rescued"] for t in ALL),
        sum(R[("fmOFF", t)].ev["rescued"] for t in ALL if t[1] != "def"),
        sum(R[("fmDRY", t)].ev["rescued"] for t in ALL if t[1] != "def")))
    say("  runs with ANY difference on these items: %d -> %s" % (len(changed), ", ".join(label(t) for t in changed)))
    return changed


def call_line(C, arm):
    oth = C["other"]
    eng = ""
    if arm == "fmDRY":
        eng = " engaged=%s" % C["engaged"]
    return ("%s s%-3d %-9s->%-8s %-25s unit %-8s victim %-8s d=%-3s [%s%s] anchor %s disp %s max %s idle %s 1st-engaged %s | "
            "other %s at %s avail=%s %s d=%s | contact %s (+%s) complete %s end %s(%s) rb_unassign %d rb_frames %d") % (
        arm, C["step"], C["ff"], C["vid"], C["reason"], fc(C["upos"]), fc(C["vpos"]), C["dist"],
        C["state"], eng, fc(C["anchor"]) if C["anchor"] else "-", C["disp"], C["maxdisp"], C["idle_len"],
        ("s%d %s" % (C["first_engaged"][0], fc(C["first_engaged"][1]))) if C["first_engaged"] else "-",
        oth["ff"], fc(oth["pos"]), oth["avail"], oth["state"], oth["dist"],
        C["contact"], C["to_contact"], C["complete"], C["ep_end"], C["ep_end_why"], C["rb_unassigns"], C["rb_frames"])


def section2(R, changed):
    say("")
    say("=" * 100)
    say("2. PER CHANGED RUN: streaks, the calls that matter, the other unit, the re-timing chain, divergences")
    say("=" * 100)
    facts = {}
    for t in changed:
        o, d = R[("fmOFF", t)], R[("fmDRY", t)]
        F = {}
        say("")
        say("-" * 100)
        say("RUN %s   OFF r/d/ffd %d/%d/%d term %s   DRY %d/%d/%d term %s" % (
            label(t), o.ev["rescued"], o.ev["dead"], o.ev["firefighter_deaths"], o.term,
            d.ev["rescued"], d.ev["dead"], d.ev["firefighter_deaths"], d.term))
        say("-" * 100)
        # (a) idle streaks
        say("(a) DRY idle streaks (feature-log rows): steps, anchor, first engaged row, end cell, max displacement, actions")
        for ff in UNITS:
            for a_, b_ in d.streaks.get(ff, []):
                rows = [d.rows[ff][k] for k in range(a_, b_ + 1)]
                anchor = tuple(rows[0]["cell"])
                eng = [r for r in rows if r.get("engaged")]
                md = max(man(d.p(ff, k), anchor) for k in range(a_, b_ + 1))
                acts = collections.Counter(r["action"] for r in rows)
                say("    %s steps %3d-%3d anchor %-8s first engaged %-14s end %-8s maxdisp %2d  %s" % (
                    ff, a_, b_, fc(anchor), ("s%d %s" % (eng[0]["step"], fc(eng[0]["cell"]))) if eng else "none",
                    fc(d.p(ff, b_)), md, dict(acts)))
        say("    OFF idle frames: " + "; ".join("%s %s" % (ff, ",".join("%d-%d@%s" % (a_, b_, fc(o.p(ff, a_)))
                                                                         for a_, b_ in o.idle_frames[ff]))
                                              for ff in UNITS))
        # all assigns, both arms
        say("(b-d) EVERY ok assign, both arms (call position, distance, anchor/displacement, the other unit, episode):")
        for arm, run in (("fmOFF", o), ("fmDRY", d)):
            for a in run.assigns:
                say("    " + call_line(run.call(a), arm))
        # the changed victims
        vchg = [v for v in o.vids if o.final[v] != d.final[v]]
        dchg = [ff for ff in UNITS if o.death[ff] != d.death[ff]]
        F["vchg"] = [(v, o.final[v], d.final[v]) for v in vchg]
        F["dchg"] = [(ff, o.death[ff], d.death[ff]) for ff in dchg]
        for v in vchg:
            say("  CHANGED VICTIM %s: OFF %s (terminal frame %s)  DRY %s (terminal frame %s)" % (
                v, o.final[v], o.vterm[v], d.final[v], d.vterm[v]))
            for arm, run, other in (("fmOFF", o, d), ("fmDRY", d, o)):
                va = [a for a in run.assigns if a["vid"] == v]
                for a in va:
                    C = run.call(a)
                    say("    %s call s%d %s: unit at %s, victim at %s, d=%s; SAME unit in the other arm at s%d: %s (d=%s)" % (
                        arm, C["step"], C["ff"], fc(C["upos"]), fc(C["vpos"]), C["dist"], C["idx"],
                        fc(other.p(C["ff"], C["idx"])), man(other.p(C["ff"], C["idx"]), C["vpos"])))
            fo = [o.call(a) for a in o.assigns if a["vid"] == v]
            fd = [d.call(a) for a in d.assigns if a["vid"] == v]
            for arm, run in (("fmOFF", o), ("fmDRY", d)):
                for e in run.d["exit_starts"]:
                    if e["victim"] == v:
                        comp = next((c for c in run.d["completions"] if c["victim"] == v and c["step"] >= e["step"]), None)
                        say("    %s contact s%d %s at %s -> exit target by the rule %s; completed %s" % (
                            arm, e["step"], e["ff"], fc(e["ff_pos"]), fc(exit_rule(e["ff_pos"])),
                            ("s%d at %s" % (comp["step"], fc(comp["pos"]))) if comp else "no"))
            for arm, run, calls in (("fmOFF", o, fo), ("fmDRY", d, fd)):
                for C in calls:
                    X = run.exposure(C["ff"], C["step"], C["ep_end"])
                    oth = C["other"]
                    say("    %s s%d episode %s: frames %d, min fire distance %s, frames at fire distance <=1: %d, end %s(%s) | path %s"
                        % (arm, C["step"], C["ff"], X["frames"], X["min_fd"], X["adj"], C["ep_end"], C["ep_end_why"], X["path"]))
                    say("        (d) other unit at this call: %s at %s status %s avail=%s %s d=%s (called unit d=%s)" % (
                        oth["ff"], fc(oth["pos"]), oth["status"], oth["avail"], oth["state"], oth["dist"], C["dist"]))
            if fo and fd:
                F.setdefault("victim_calls", []).append((v, fo[0], fd[0]))
                say("    FIRST CALL  OFF s%d %s d=%s -> contact %s   |  DRY s%d %s d=%s -> contact %s   "
                    "| step delta %s  dist delta %s  to-contact delta %s  same unit %s" % (
                        fo[0]["step"], fo[0]["ff"], fo[0]["dist"], fo[0]["contact"],
                        fd[0]["step"], fd[0]["ff"], fd[0]["dist"], fd[0]["contact"],
                        sgn(fd[0]["step"] - fo[0]["step"]), sgn(fd[0]["dist"] - fo[0]["dist"]),
                        sgn(fd[0]["to_contact"] - fo[0]["to_contact"]) if fd[0]["to_contact"] is not None and fo[0]["to_contact"] is not None else "-",
                        fo[0]["ff"] == fd[0]["ff"]))
        for ff in dchg:
            say("  CHANGED UNIT DEATH %s: OFF %s  DRY %s" % (ff, o.death[ff], d.death[ff]))
            for arm, run in (("fmOFF", o), ("fmDRY", d)):
                if run.death[ff] is None:
                    continue
                la = [a for a in run.assigns if a["ff"] == ff and a["step"] <= run.death[ff]]
                if not la:
                    say("    %s: no assign before death (idle death)" % arm)
                    continue
                C = run.call(la[-1])
                term = run.term
                X = run.exposure(ff, C["step"], run.death[ff])
                say("    %s last assign before death: s%d ->%s  unit at %s d=%s state %s engaged %s disp %s | died s%d at %s "
                    "(status before %s; after terminal %s) | frames at fire distance <=1 from the call: %d | path %s" % (
                        arm, C["step"], C["vid"], fc(C["upos"]), C["dist"], C["state"], C["engaged"], C["disp"],
                        run.death[ff], fc(run.p(ff, run.death[ff])), run.pos[ff][run.death[ff] - 1][1],
                        term is not None and run.death[ff] > term, X["adj"], X["path"]))
                F.setdefault("death_calls", []).append((arm, ff, C, run.death[ff], term))
                other = d if arm == "fmOFF" else o
                sa = [b for b in other.assigns if b["ff"] == ff and b["vid"] == C["vid"]]
                if sa:
                    C2 = other.call(sa[0])
                    X2 = other.exposure(ff, C2["step"], C2["ep_end"])
                    say("      same (unit, victim) in %s: s%d from %s d=%s engaged %s disp %s -> contact %s end %s(%s), "
                        "frames at fire distance <=1: %d | path %s" % (
                            other.tag, C2["step"], fc(C2["upos"]), C2["dist"], C2["engaged"], C2["disp"], C2["contact"],
                            C2["ep_end"], C2["ep_end_why"], X2["adj"], X2["path"]))
                else:
                    say("      %s never assigned %s to %s" % (other.tag, ff, C["vid"]))
        # (e) the chain
        to_, td = o.timeline(), d.timeline()
        steps = sorted(set(to_) | set(td))
        first = next((s for s in steps if to_.get(s, set()) != td.get(s, set())), None)
        F["timeline_div"] = first
        say("(e) RESCUE TIMELINE (events only, no positions): first differing step = %s" % first)
        if first is not None:
            say("      OFF only: %s" % sorted(to_.get(first, set()) - td.get(first, set())))
            say("      DRY only: %s" % sorted(td.get(first, set()) - to_.get(first, set())))
        # first dispatch whose call position differs
        pairs = list(zip(o.assigns, d.assigns))
        fdisp = None
        for ao, ad in pairs:
            co, cd = o.call(ao), d.call(ad)
            if (ao["step"], ao["ff"], ao["vid"]) != (ad["step"], ad["ff"], ad["vid"]) or co["upos"] != cd["upos"]:
                fdisp = (co, cd)
                break
        if fdisp:
            co, cd = fdisp
            say("    first assign that differs (unit, victim, step or call position): OFF s%d %s->%s from %s d=%s | "
                "DRY s%d %s->%s from %s d=%s (DRY unit disp %s, engaged %s)" % (
                    co["step"], co["ff"], co["vid"], fc(co["upos"]), co["dist"],
                    cd["step"], cd["ff"], cd["vid"], fc(cd["upos"]), cd["dist"], cd["disp"], cd["engaged"]))
        F["first_assign_diff"] = fdisp
        # early chain side by side: first two dispatches and their contacts/completions
        say("    FIRST-DISPATCH HEAD START (the first ok assign of each unit):")
        for ff in UNITS:
            ao = next((a for a in o.assigns if a["ff"] == ff), None)
            ad = next((a for a in d.assigns if a["ff"] == ff), None)
            if ao is None or ad is None:
                say("      %s: OFF %s DRY %s" % (ff, ao, ad))
                continue
            co, cd = o.call(ao), d.call(ad)
            say("      %s: OFF s%d ->%s from %s d=%s contact %s complete %s | DRY s%d ->%s from %s d=%s contact %s complete %s "
                "| d delta %s, contact delta %s" % (
                    ff, co["step"], co["vid"], fc(co["upos"]), co["dist"], co["contact"], co["complete"],
                    cd["step"], cd["vid"], fc(cd["upos"]), cd["dist"], cd["contact"], cd["complete"],
                    sgn(cd["dist"] - co["dist"]) if co["vid"] == cd["vid"] else "(other victim)",
                    sgn(cd["contact"] - co["contact"]) if (co["vid"] == cd["vid"] and cd["contact"] and co["contact"]) else "-"))
        say("    completions OFF: %s" % [(c["step"], c["ff"], c["victim"]) for c in o.d["completions"]])
        say("    completions DRY: %s" % [(c["step"], c["ff"], c["victim"]) for c in d.d["completions"]])
        # (f) divergences
        fd_ff = first_div(o.d["ff_steps"], d.d["ff_steps"])
        fd_v = first_div(o.d["victim_steps"], d.d["victim_steps"])
        fd_vp = first_div([[r[1] for r in row] for row in o.d["victim_steps"]], [[r[1] for r in row] for row in d.d["victim_steps"]])
        fd_vs = first_div([[r[2] for r in row] for row in o.d["victim_steps"]], [[r[2] for r in row] for row in d.d["victim_steps"]])
        fd_u = first_div(o.d["uav_steps"], d.d["uav_steps"])
        fd_ua = first_div(o.d["uav_actions"] or [], d.d["uav_actions"] or [])
        fd_part = first_div(o.d["partition_steps"], d.d["partition_steps"])
        flee_o = [(e["step"], e["victim_id"], tuple(e["to"])) for e in o.d["victim_flee_log"]]
        flee_d = [(e["step"], e["victim_id"], tuple(e["to"])) for e in d.d["victim_flee_log"]]
        fflee = next((i for i, (x, y) in enumerate(zip(flee_o, flee_d)) if x != y), None)
        if fflee is not None:
            fflee_s = min(flee_o[fflee][0], flee_d[fflee][0])
        elif len(flee_o) != len(flee_d):
            longer = flee_o if len(flee_o) > len(flee_d) else flee_d
            fflee_s = longer[min(len(flee_o), len(flee_d))][0]
        else:
            fflee_s = None
        F["div"] = {"ff": fd_ff, "victim": fd_v, "uav": fd_u, "uav_actions": fd_ua, "partition": fd_part, "flee": fflee_s}
        say("(f) FIRST DIVERGENCE  ff_steps %s | victim_steps %s (pos %s, status %s) | victim_flee_log %s | uav_steps %s | "
            "uav_actions %s | partition %s | rescue timeline %s" % (fd_ff, fd_v, fd_vp, fd_vs, fflee_s, fd_u, fd_ua, fd_part, first))
        if fd_v is not None:
            for (vo, po, so), (vd, pd, sd) in zip(o.d["victim_steps"][fd_v - 1], d.d["victim_steps"][fd_v - 1]):
                if (po, so) != (pd, sd):
                    ct_o = [e["step"] for e in o.d["exit_starts"] if e["victim"] == vo and e["step"] <= fd_v]
                    ct_d = [e["step"] for e in d.d["exit_starts"] if e["victim"] == vd and e["step"] <= fd_v]
                    say("      victim frame %d: %s OFF %s %s (contact<=: %s) | DRY %s %s (contact<=: %s)" % (
                        fd_v, vo, po, so, ct_o, pd, sd, ct_d))
        det_o = {v: min((p_["step"] for p_ in o.d["planner"] if p_["vid"] == v), default=None) for v in o.vids}
        det_d = {v: min((p_["step"] for p_ in d.d["planner"] if p_["vid"] == v), default=None) for v in d.vids}
        say("      first planner decision per victim (detection proxy) OFF %s | DRY %s" % (det_o, det_d))
        F["det_same"] = det_o == det_d
        facts[t] = F
    # same-count death changes on the other runs
    say("")
    say("-" * 100)
    say("SAME-COUNT UNIT-DEATH CHANGES on runs whose outcome counts agree (which unit died, and when)")
    say("-" * 100)
    for t in ALL:
        if t in changed:
            continue
        o, d = R[("fmOFF", t)], R[("fmDRY", t)]
        if all(o.death[ff] == d.death[ff] for ff in UNITS):
            continue
        say("  %s  OFF %s  DRY %s  (terminal OFF %s DRY %s)" % (
            label(t), {ff: o.death[ff] for ff in UNITS if o.death[ff]}, {ff: d.death[ff] for ff in UNITS if d.death[ff]},
            o.term, d.term))
        for arm, run in (("fmOFF", o), ("fmDRY", d)):
            for ff in UNITS:
                if run.death[ff] is None:
                    continue
                la = [a for a in run.assigns if a["ff"] == ff and a["step"] <= run.death[ff]]
                last = run.call(la[-1]) if la else None
                s = run.death[ff]
                row_prev = run.rows.get(ff, {}).get(s - 1)
                st = run.streak_at(ff, s) or run.streak_at(ff, s - 1)
                streak_eng = bool(st and any(run.rows[ff][k].get("engaged") for k in range(st[0], min(st[1], s) + 1)))
                say("    %s %s died s%d at %s status-before %s after-terminal %s | last assign %s | DRY idle streak engaged before death %s" % (
                    arm, ff, s, fc(run.p(ff, s)), run.pos[ff][s - 1][1], run.term is not None and s > run.term,
                    ("s%d ->%s engaged %s disp %s" % (last["step"], last["vid"], last["engaged"], last["disp"])) if last else "none",
                    streak_eng if arm == "fmDRY" else "-"))
    return facts


def section3(R, changed, facts):
    say("")
    say("=" * 100)
    say("3. CLASSIFICATION OF EVERY CHANGED OUTCOME (rule applied to the computed indicators)")
    say("   M1 displaced-at-the-call: same call step, same unit, the DRY unit was ENGAGED at the call and displaced >= 5")
    say("      from its idle anchor, so its route at the call changed (farther, or a shorter Manhattan distance that the")
    say("      unit's greedy walker could not cover: agents.Firefighter._move_toward steps to the best non-burning")
    say("      neighbour, no global path)")
    say("   M2 re-timed chain: the call that matters happens at a DIFFERENT step because upstream completions moved,")
    say("      and the DRY unit at the call is not materially displaced (not in an idle streak, or displacement <= 3)")
    say("   M3 unit identity: same call step, a different unit takes it (the chooser saw different positions)")
    say("   M4 victim/UAV side: detection timing differs or the UAV series diverges at or before the call")
    say("   M5 post-terminal: a unit death after terminal_step with no rescue involved (where idle units stand)")
    say("   The call that matters = the victim's first ok assign in each arm; for a death, the dead unit's last ok assign")
    say("   (and, for a death only one arm has, the same (unit, victim) assign in the other arm).")
    say("=" * 100)
    out = []
    for t in changed:
        o, d = R[("fmOFF", t)], R[("fmDRY", t)]
        F = facts[t]
        udiv = F["div"]["uav"]
        for v, fo_, fdry in F["vchg"]:
            co = [o.call(a) for a in o.assigns if a["vid"] == v]
            cd = [d.call(a) for a in d.assigns if a["vid"] == v]
            a0, b0 = co[0], cd[0]
            sign = ("LOSS" if fo_ == "rescued" else "GAIN" if fdry == "rescued" else
                    "NEUTRAL-rescued (dead -> unresolved)")
            first_disp = not [x for x in d.assigns if x["ff"] == b0["ff"] and x["step"] < b0["step"]]
            m4 = (not F["det_same"]) or (udiv is not None and udiv <= min(a0["step"], b0["step"]))
            if m4:
                cls = "M4"
            elif a0["step"] == b0["step"] and a0["ff"] != b0["ff"]:
                cls = "M3" + ("+M1(fire-ward start)" if b0["engaged"] and (b0["disp"] or 0) >= 5 else "")
            elif a0["step"] == b0["step"] and b0["engaged"] and (b0["disp"] or 0) >= 5:
                cls = "M1"
            elif a0["step"] != b0["step"] and (b0["disp"] is None or b0["disp"] <= 3):
                cls = "M2"
            else:
                cls = "other"
            # the chain's root, when the call itself is M3 on a later dispatch: a previous identity swap
            prior_swap = [x for x in zip(o.assigns, d.assigns) if x[0]["step"] < a0["step"] and x[0]["ff"] != x[1]["ff"]]
            ev = ("OFF s%d %s d=%s contact %s | DRY s%d %s d=%s engaged %s disp %s contact %s end %s(%s) | DRY call is the "
                  "unit's first dispatch %s | rescue timeline first differs s%s | uav div %s | earlier identity swaps %d" % (
                      a0["step"], a0["ff"], a0["dist"], a0["contact"], b0["step"], b0["ff"], b0["dist"], b0["engaged"],
                      b0["disp"], b0["contact"], b0["ep_end"], b0["ep_end_why"], first_disp, F["timeline_div"], udiv,
                      len(prior_swap)))
            out.append((label(t), "%s %s->%s" % (v, fo_, fdry), cls, sign, ev))
        for arm, ff, C, dstep, term in F.get("death_calls", []):
            other = d if arm == "fmOFF" else o
            sign = "GAIN (ff death avoided)" if arm == "fmOFF" else "LOSS (ff death added)"
            after_term = term is not None and dstep > term
            idle_at_death = d.pos[ff][dstep - 1][1] == "available" if arm == "fmDRY" else o.pos[ff][dstep - 1][1] == "available"
            sa = [b for b in other.assigns if b["ff"] == ff and b["vid"] == C["vid"]]
            C2 = other.call(sa[0]) if sa else None
            dry_c = C if arm == "fmDRY" else C2
            off_c = C if arm == "fmOFF" else C2
            if after_term and idle_at_death:
                cls = "M5"
            elif dry_c is not None and off_c is not None and dry_c["step"] == off_c["step"] and dry_c["engaged"] and (dry_c["disp"] or 0) >= 5:
                cls = "M1"
            elif dry_c is not None and dry_c["engaged"] and (dry_c["disp"] or 0) >= 5:
                cls = "M1"
            else:
                # not engaged / not displaced at its own call: where it stood (or when it was called) came from
                # the upstream chain (a different return cell, a different call step)
                cls = "M2"
            ev = "%s %s died s%d (terminal %s, idle at death %s); its last call s%d ->%s d=%s engaged %s disp %s; other arm: %s" % (
                arm, ff, dstep, term, idle_at_death, C["step"], C["vid"], C["dist"], C["engaged"], C["disp"],
                ("s%d from %s d=%s engaged %s disp %s contact %s" % (C2["step"], fc(C2["upos"]), C2["dist"], C2["engaged"], C2["disp"], C2["contact"]))
                if C2 else "no such assign")
            out.append((label(t), "%s death %s" % (ff, arm), cls, sign, ev))
    for lab, item, cls, sign, ev in out:
        say("  %-16s %-34s %-22s %-38s" % (lab, item, cls, sign))
        say("      %s" % ev)
    cnt = collections.Counter((cls.split("+")[0], sign.split(" ")[0]) for _l, _i, cls, sign, _e in out)
    say("  COUNTS by (class, sign): %s" % dict(sorted(cnt.items())))
    return out


def section4b(R):
    say("")
    say("=" * 100)
    say("4b. ALL 23: where the rescue timeline first differs, and whether it is the first-dispatch head start")
    say("=" * 100)
    kinds = collections.Counter()
    comp_shift = []
    for t in ALL:
        o, d = R[("fmOFF", t)], R[("fmDRY", t)]
        to_, td = o.timeline(), d.timeline()
        steps = sorted(set(to_) | set(td))
        first = next((s for s in steps if to_.get(s, set()) != td.get(s, set())), None)
        first_units = {}
        for run in (o, d):
            for a in run.assigns:
                first_units.setdefault((run.tag, a["ff"]), (a["step"], a["vid"]))
        if first is None:
            kind = "identical"
            evs = ""
        else:
            diff = (to_.get(first, set()) ^ td.get(first, set()))
            evs = sorted(diff)
            first_pairs = {(ff, v) for (tag, ff), (s, v) in first_units.items()}
            first_ffs = {ff for (tag, ff), (s, v) in first_units.items()}

            def in_first_episode(e):
                if e[0] in ("contact", "complete", "unassign"):
                    return (e[1], e[2]) in first_pairs
                if e[0] == "ffdead":
                    run = d if e in td.get(first, set()) else o
                    la = [a for a in run.assigns if a["ff"] == e[1] and a["step"] <= first]
                    return len(la) == 1
                return False
            if any(e[0] == "assign" for e in diff):
                kind = "first-window assign differs" if first <= 20 else "later assign differs"
            elif any(in_first_episode(e) for e in diff):
                kind = "first-dispatch episode (contact/complete/block/death) re-timed"
            else:
                kind = "other"
        kinds[kind] += 1
        fdo = first_div(o.d["ff_steps"], d.d["ff_steps"])
        fdv = first_div(o.d["victim_steps"], d.d["victim_steps"])
        fdu = first_div(o.d["uav_steps"], d.d["uav_steps"])
        det_o = {v: min((p_["step"] for p_ in o.d["planner"] if p_["vid"] == v), default=None) for v in o.vids}
        det_d = {v: min((p_["step"] for p_ in d.d["planner"] if p_["vid"] == v), default=None) for v in d.vids}
        order_ok = (first is None) or ((fdv is None or fdv >= first) and (fdu is None or fdu > first))
        # is the first differing victim frame a rescue effect? every differing victim there either differs in
        # status, or has been contacted (exit_starts) in one of the arms at or before that frame
        rescue_caused = None
        if fdv is not None:
            rescue_caused = True
            for (vo, po, so), (vd, pd, sd) in zip(o.d["victim_steps"][fdv - 1], d.d["victim_steps"][fdv - 1]):
                if (po, so) == (pd, sd):
                    continue
                contacted = any(e["victim"] == vo and e["step"] <= fdv for e in o.d["exit_starts"] + d.d["exit_starts"])
                if so == sd and not contacted:
                    rescue_caused = False
        say("  %-16s ff_steps div %s | timeline div %s: %s | victim_steps div %s (a status change or an escorted victim: %s) "
            "| uav_steps div %s | detection (first planner decision per victim) same %s | victim & UAV series diverge only "
            "at/after the timeline: %s | %s" % (label(t), fdo, first, kind, fdv, rescue_caused, fdu, det_o == det_d,
                                                 order_ok, evs))
        kinds["_order_ok"] += int(order_ok)
        kinds["_detect_same"] += int(det_o == det_d)
        kinds["_victim_div_rescue_caused"] += int(bool(rescue_caused))
        co = {c["victim"]: c["step"] for c in o.d["completions"]}
        cd = {c["victim"]: c["step"] for c in d.d["completions"]}
        for v in sorted(set(co) & set(cd)):
            comp_shift.append(cd[v] - co[v])
    say("  first timeline divergence kinds: %s" % dict(kinds))
    say("  completion step shift DRY-OFF, victims completed in both arms: %s" % stats(comp_shift))
    eng1 = 0
    for t in ALL:
        d = R[("fmDRY", t)]
        firsts = [d.rows[ff].get(1) for ff in UNITS]
        eng1 += sum(1 for r in firsts if r is not None and r.get("engaged"))
    say("  units engaged on their step-1 row: %d of 46" % eng1)


def section4(R):
    say("")
    say("=" * 100)
    say("4. SYSTEMATIC, ALL 23 TUPLES (and the de-duplicated 20): per victim, per assign, per first dispatch")
    say("=" * 100)
    rows = []
    for t in ALL:
        o, d = R[("fmOFF", t)], R[("fmDRY", t)]
        for v in o.vids:
            ao = [o.call(a) for a in o.assigns if a["vid"] == v]
            ad = [d.call(a) for a in d.assigns if a["vid"] == v]
            rows.append((t, v, ao, ad, o.final[v], d.final[v]))
    say("  PER VICTIM (first ok assign in each arm): step OFF/DRY, unit, d at call OFF/DRY, contact delay OFF/DRY, outcome")
    dstep, ddist, dcont = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    flips = collections.Counter()
    for t, v, ao, ad, fo, fd in rows:
        key = "all23"
        if ao and ad:
            a0, b0 = ao[0], ad[0]
            first_kind = "first-dispatch" if (not [x for x in R[("fmOFF", t)].assigns if x["ff"] == a0["ff"] and x["step"] < a0["step"]]) else "later"
            for k in (key, "dedup20" if t[1] != "def" else None, first_kind):
                if k is None:
                    continue
                dstep[k].append(b0["step"] - a0["step"])
                ddist[k].append(b0["dist"] - a0["dist"])
                if a0["to_contact"] is not None and b0["to_contact"] is not None:
                    dcont[k].append(b0["to_contact"] - a0["to_contact"])
            say("    %-16s %-8s s%3d/%-3d %s/%s d %2d/%-2d (%+3d) contact +%s/+%s  %-10s-> %-10s %s" % (
                label(t), v, a0["step"], b0["step"], a0["ff"][-1], b0["ff"][-1], a0["dist"], b0["dist"],
                b0["dist"] - a0["dist"], a0["to_contact"], b0["to_contact"], fo, fd, "" if fo == fd else "<== FLIP"))
        else:
            say("    %-16s %-8s OFF assigns %d DRY assigns %d  %s -> %s %s" % (label(t), v, len(ao), len(ad), fo, fd,
                                                                       "" if fo == fd else "<== FLIP"))
        if fo != fd:
            flips[(fo, fd)] += 1
    for k in ("all23", "dedup20", "first-dispatch", "later"):
        say("  %-15s first-assign STEP delta (DRY-OFF): %s" % (k, stats(dstep[k])))
        say("  %-15s DISTANCE at call delta:            %s" % (k, stats(ddist[k])))
        say("  %-15s ASSIGN->CONTACT delta (both made): %s" % (k, stats(dcont[k])))
    say("  outcome flips (OFF -> DRY): %s" % dict(flips))

    # every ok assign: preemption and displacement
    say("")
    say("  EVERY DRY ok assign: engaged on its latest row (round-1 preemption) and displacement from the idle anchor")
    tot = eng = 0
    disp_all, disp_first, disp_later = [], [], []
    by_state = collections.Counter()
    dist_dry, dist_off = [], []
    for t in ALL:
        d, o = R[("fmDRY", t)], R[("fmOFF", t)]
        for a in d.assigns:
            C = d.call(a)
            tot += 1
            eng += int(C["engaged"])
            by_state[(C["state"].split(":")[0], "engaged" if C["engaged"] else "not-engaged")] += 1
            if C["streak"] is not None:
                disp_all.append(C["disp"])
                (disp_first if C["streak"][0] == 1 else disp_later).append(C["disp"])
            dist_dry.append(C["dist"])
        for a in o.assigns:
            dist_off.append(o.call(a)["dist"])
    say("    DRY ok assigns %d, engaged at the call %d (%.1f%%); by (state before call, engaged): %s" % (
        tot, eng, 100.0 * eng / tot, dict(by_state)))
    say("    displacement at the call, calls on a unit inside a feature-log idle streak: %s" % ustats(disp_all))
    say("        first streak (from the berth, step 1): %s   list %s" % (ustats(disp_first), sorted(disp_first)))
    say("        later streaks (after a rescue):         %s   list %s" % (ustats(disp_later), sorted(disp_later)))
    off_disp = []
    for t in ALL:
        o = R[("fmOFF", t)]
        for a in o.assigns:
            C = o.call(a)
            if C["state"] == "idle" and C["disp"] is not None:
                off_disp.append(C["disp"])
    say("    OFF, same measure on idle-unit calls (only the unchanged idle retreat can move a unit): %s" % ustats(off_disp))
    say("    distance at call over ALL ok assigns: OFF %s | DRY %s" % (ustats(dist_off), ustats(dist_dry)))

    # matched assigns by (victim, ordinal)
    say("")
    say("  EVERY ok assign matched by (tuple, victim, ordinal):")
    dd_, dc_, ds_ = [], [], []
    same_unit = diff_unit = 0
    for t in ALL:
        o, d = R[("fmOFF", t)], R[("fmDRY", t)]
        for v in o.vids:
            ao = [o.call(a) for a in o.assigns if a["vid"] == v]
            ad = [d.call(a) for a in d.assigns if a["vid"] == v]
            for x, y in zip(ao, ad):
                ds_.append(y["step"] - x["step"])
                dd_.append(y["dist"] - x["dist"])
                if x["to_contact"] is not None and y["to_contact"] is not None:
                    dc_.append(y["to_contact"] - x["to_contact"])
                same_unit += int(x["ff"] == y["ff"])
                diff_unit += int(x["ff"] != y["ff"])
    say("    step delta     %s" % stats(ds_))
    say("    distance delta %s" % stats(dd_))
    say("    contact delta  %s" % stats(dc_))
    say("    same unit on the matched assign %d, different unit %d" % (same_unit, diff_unit))

    # first dispatch window: the head start of the walk before the first call
    say("")
    say("  FIRST DISPATCH (each unit's first ok assign, same victim in both arms): distance and time to contact")
    hd, hc, hcomp = [], [], []
    swaps = []
    for t in ALL:
        o, d = R[("fmOFF", t)], R[("fmDRY", t)]
        lines = []
        for ff in UNITS:
            ao = next((a for a in o.assigns if a["ff"] == ff), None)
            # the DRY assign of the same victim as OFF's first assign of this unit
            if ao is None:
                continue
            ad = next((a for a in d.assigns if a["vid"] == ao["vid"]), None)
            if ad is None:
                continue
            co, cd = o.call(ao), d.call(ad)
            same = cd["ff"] == co["ff"]
            if not same:
                swaps.append("%s %s" % (label(t), ao["vid"]))
            hd.append(cd["dist"] - co["dist"])
            if co["to_contact"] is not None and cd["to_contact"] is not None:
                hc.append(cd["contact"] - co["contact"])
            if co["complete"] is not None and cd["complete"] is not None:
                hcomp.append(cd["complete"] - co["complete"])
            lines.append("%s s%d/%d %s/%s d%d/%d contact %s/%s" % (ao["vid"], co["step"], cd["step"], co["ff"][-1],
                                                                   cd["ff"][-1], co["dist"], cd["dist"], co["contact"], cd["contact"]))
        say("    %-16s %s" % (label(t), " | ".join(lines)))
    say("    distance delta DRY-OFF   %s" % stats(hd))
    say("    contact STEP delta       %s" % stats(hc))
    say("    completion STEP delta    %s" % stats(hcomp))
    say("    victims whose first-dispatch unit differs (identity swap): %s" % (swaps or "none"))
    # the walk before the first call: when, how far, and how close the two units stand together
    firsts, dispfirst, sep, oth_d_gap = [], [], [], []
    for t in ALL:
        d = R[("fmDRY", t)]
        a = d.assigns[0]
        C = d.call(a)
        firsts.append(a["step"])
        if C["disp"] is not None:
            dispfirst.append(C["disp"])
        oth = C["other"]
        sep.append(man(C["upos"], oth["pos"]))
        if oth["dist"] is not None:
            oth_d_gap.append(oth["dist"] - C["dist"])
    say("    DRY FIRST ok assign of the run: step %s; displacement of the called unit from its berth %s" % (
        ustats(firsts), ustats(dispfirst)))
    say("    distance between the two units at that call %s   list %s" % (ustats(sep), sorted(sep)))
    say("    the other unit's distance to that victim minus the called unit's: %s   list %s" % (ustats(oth_d_gap), sorted(oth_d_gap)))


def cf_positions(o, d, ff, idx, policy):
    """Counterfactual position of a still-unassigned unit at frame idx inside its FIRST idle streak.
    A unit that does not engage stands at its berth (OFF: an idle unit stands still)."""
    berth = tuple(d.rows[ff][1]["cell"]) if 1 in d.rows.get(ff, {}) else o.p(ff, 1)
    if policy == "OFF":
        return berth
    if policy == "DRY":
        return d.p(ff, idx)
    if policy in ("U0", "U1"):
        return d.p(ff, idx) if ff == "ff_unit_%s" % policy[1] else berth
    if policy in ("L3", "L8"):
        n = int(policy[1:])
        last = berth
        for k in range(1, idx + 1):
            q = d.p(ff, k)
            if man(q, berth) > n:
                break
            last = q
        return last
    raise ValueError(policy)


def section5(R, changed):
    say("")
    say("=" * 100)
    say("5. COUNTERFACTUAL FIRST-DISPATCH CHOICE for the probe arms (f2U0D, f2U1D, f2L3D, f2L8D; f2GD == OFF before")
    say("   terminal). Model: until its first call each unit follows its DRY path (engaged) or stays where OFF has it")
    say("   (not engaged); a leash holds the unit at the last DRY path cell within N of its berth. The chooser is")
    say("   rescue_planner's: lowest confirmed needy victim id, Manhattan-nearest available unit, tie lower id.")
    say("   Calls, victims and victim positions are OFF's (identical in DRY until the first contact). VALIDATION:")
    say("   policy OFF must reproduce OFF's choice and policy DRY must reproduce DRY's.")
    say("=" * 100)
    pols = ("OFF", "DRY", "U0", "U1", "L3", "L8")
    valid = [0, 0]
    table = {}
    for t in ALL:
        o, d = R[("fmOFF", t)], R[("fmDRY", t)]
        # first window: OFF assigns while neither unit had been assigned before, one per unit
        win = []
        seen = set()
        for a in o.assigns:
            if a["ff"] in seen:
                break
            if a["reason"] != "initial":
                break
            seen.add(a["ff"])
            win.append(a)
            if len(seen) == 2:
                break
        res = {}
        for pol in pols:
            taken = set()
            picks = []
            for a in win:
                C = o.call(a)
                idx, vpos = C["idx"], C["vpos"]
                best = None
                for ff in UNITS:
                    if ff in taken:
                        continue
                    q = cf_positions(o, d, ff, idx, pol)
                    dist = man(q, vpos)
                    if best is None or dist < best[1] or (dist == best[1] and ff < best[0]):
                        best = (ff, dist, q)
                taken.add(best[0])
                picks.append((a["step"], a["vid"], best[0], best[2], best[1]))
            res[pol] = picks
        # validation
        off_actual = [(a["step"], a["vid"], a["ff"]) for a in win]
        dry_actual = [(a["step"], a["vid"], a["ff"]) for a in d.assigns[:len(win)]]
        ok_off = [(s, v, f) for s, v, f, _q, _d in res["OFF"]] == off_actual
        ok_dry = [(s, v, f) for s, v, f, _q, _d in res["DRY"]] == dry_actual
        valid[0] += int(ok_off)
        valid[1] += int(ok_dry)
        table[t] = res
        mark = "*" if t in changed else " "
        say("  %s%-16s valid OFF %s DRY %s" % (mark, label(t), ok_off, ok_dry))
        for pol in pols:
            say("      %-3s %s" % (pol, " | ".join("s%d %s <- %s from %s d=%d" % (s, v, f, fc(q), dist)
                                                  for s, v, f, q, dist in res[pol])))
    say("  validation: policy OFF reproduces OFF's first-window choices on %d/23, policy DRY reproduces DRY's on %d/23"
        % tuple(valid))
    return table


HEADER = r"""
====================================================================================================
FIREMECH ROUND 2, PART 1 DIAGNOSIS - TASK A: THE POSITIONING LOSS (fmDRY vs fmOFF)
====================================================================================================
Produced by outputs/_fm2_diag_positioning.py (read-only). Inputs: outputs/_ffr_fmOFF_<t>.json and
outputs/_ffr_fmDRY_<t>.json for the canonical 13 + fresh 10 tuples, opened by explicit path. No f2* file was
opened, no simulation was run. Part A (answers) and Part B (pre-registration) are interpretation written from
the computed sections 0-5 printed below them; every number in A and B is printed in those sections.
Conventions (call position, idle streak, anchor, episode, divergence) are in the script docstring and are
checked in section 0.
"""

NARRATIVE = r"""
====================================================================================================
PART A. ANSWERS
====================================================================================================
A1 WHAT CHANGED (section 1; both round-1 lists re-derived: MATCH)
  9 of 23 runs differ on rescued, dead, ff_deaths or a victim's final status.
    rescued -1   east/half/101  victim_0 rescued -> dead
                 south/half/404 victim_3 rescued -> still assigned at 240
                 east/def/101   victim_3 rescued -> still assigned at 240
                 south/half/909 victim_3 rescued -> still assigned at 240
    rescued +1   east/half/404  victim_1 dead -> rescued
                 south/half/202 victim_0 still assigned at 240 -> rescued
    dead -1 only east/half/606  victim_0 dead -> still assigned at 240 (rescued unchanged)
    ff deaths +1 south/half/404 (ff_unit_1 s72), south/half/808 (ff_unit_0 s51),
                 south/half/909 (ff_unit_0 s36), east/def/303 (ff_unit_1 s141)
    ff deaths -1 east/half/101 (OFF ff_unit_0 s195), south/half/202 (OFF ff_unit_0 s207),
                 east/half/606 (OFF ff_unit_0 s210)
    count-neutral unit-death swaps: east/half/404 (OFF ff_unit_0 s240 -> DRY ff_unit_1 s72), and four runs
      whose counts are unchanged (south/half/101, south/half/303, east/half/909, south/half/1010).
  Totals: rescued 68 -> 66 counted, 59 -> 58 de-duplicated. Fire digests equal 240/240 on 23/23, spawns 23/23.

A2 ONE PATTERN UNDERLIES ALL 23 RUNS (sections 4, 4b)
  - Both units are engaged on their step-1 feature-log row on 23/23 runs (46/46 units) and walk toward the
    fire. The first dispatch of every run is at step 14-16 (mean 14.57). By then the called unit is a median
    14 cells from its berth (min 2 on east/half/707, where the fire does not spread; max 16). The two units
    stand 1 cell apart on 21/23 runs (2 and 3 on the other two).
  - The rescue timeline (events only, no positions) first differs INSIDE that first-dispatch window on 23/23:
    on 20 runs it is a contact/completion/death of a first-dispatch episode that moved; on 3 it is the first
    assign itself going to the other unit (east/half/202, south/half/404, east/def/202).
  - The walk mostly HELPS the first rescues. First-dispatch distance at the call, DRY-OFF (n=46): mean -8.15,
    median -14 (37 shorter, 8 longer, 1 equal). Contact step (n=38): mean -7.24, median -12.5 (29 earlier,
    8 later). All 8 later contacts are victim_1: runs where the walk went away from it (south/half/303 and
    505 +16, east/def/303 +15, south/half/707 +14, south/half/808 +8, east/half/808 +4, east/half/707 +2),
    and south/half/404 +1, where the other unit took it.
  - Everything after is re-timed: victims completed in both arms complete mean -6.05, median -9.5 steps
    (45 earlier, 16 later, 3 same; n=64).
  - Victims and UAVs do NOT react to firefighter positions. Detection (the first planner decision per
    victim) is identical on 23/23. The first differing victim frame is always an escorted victim or a
    status change (23/23). The UAV series diverges only after the rescue timeline does (23/23): first UAV
    divergence s95-s233, never on 9 runs. Class M4 is empty.
  The east/half/101 scouting is reproduced exactly (both units engage at s1; completions 28 vs 42 and 70 vs
  85; victim_0 assigned s77 vs s90 on a unit idle 2 steps and 2 cells out; route_blocked unassign s135;
  victim dead s138 vs rescued s127). The pattern it suggested - engagement before the first dispatch re-times
  the whole chain - holds on every run.

A3 IS THERE A SYSTEMATIC LATENCY COST? NO (section 4)
  - Per victim, first ok assign (n=81): distance at the call DRY-OFF mean -5.44, median -6 (18 longer, 54
    shorter, 9 equal). Assign->contact (n=62): mean -5.90, median -6.5 (11 slower, 44 faster). De-duplicated
    20: distance -5.18, contact -6.22.
  - Calls after each unit's first dispatch (n=35): distance mean -1.89, median 0 (10 longer, 17 shorter, 8
    equal). Contact (n=24): mean -3.79, median -1 (3 slower, 15 faster, 6 equal).
  - Every ok assign matched by (victim, ordinal), n=100: distance mean -3.66, median -4; contact (n=66) mean
    -6.30, median -6.5; a different unit on 24 of 100.
  - 62 of 104 DRY ok assigns (59.6%) land on a unit engaged on its latest row. Displacement from the idle
    anchor at calls inside a feature-log idle streak: median 15, mean 14.17 (first streak median 15, later
    streaks median 12). OFF, same measure: mean 0.03. Yet the distance at the call is not longer: all ok
    assigns mean 35.70 DRY vs 38.38 OFF, median 39 vs 39.
  - The units walk toward the fire, and the victims are near the fire, so the Manhattan distance the chooser
    uses mostly shrinks. The outcome flips are not the tail of a latency distribution: 2 rescue gains and 4
    losses (plus 1 dead -> unresolved), while 45 of 64 shared completions came earlier.

A4 MECHANISM OF EACH CHANGED OUTCOME (section 3: rule on computed indicators; details in section 2)
  M1 displaced at the call: same call, same unit, DRY unit engaged and >= 5 cells out, so its route changed.
  M2 re-timed chain: the call comes at another step (or finds the unit elsewhere) because upstream
     completions moved; no material displacement at the call.
  M3 a different unit takes the same call.
  M4 victim/UAV side (empty).
  M5 post-terminal idle death (no rescue involved).
  LOSSES
   south/half/909  victim_3 and ff_unit_0 death - M1 at the FIRST dispatch (s14). Same call, unit and victim.
     The DRY unit was engaged, 14 cells out at (10,39) vs (2,45) in OFF, and Manhattan-CLOSER (51 vs 65). Its
     greedy walk ran down x=10 into the fire's west flank and it died at (9,23) at s36. OFF's walk went down
     x=2, reached the victim at s203, rescued s218. The other unit stood 1 cell away at (9,39), engaged, d=52.
   south/half/808  ff_unit_0 death - M1 at the first dispatch (s14). Start (6,35) vs (2,45), d 51 vs 65.
     route_blocked unassign s49, died s51 at (14,17). OFF's same assignment never reached the victim either,
     but that unit survived. The other unit was at (5,35), d=52.
   south/half/404  victim_3 and ff_unit_1 death - M3+M1 at the first dispatch (s14). The chooser took
     ff_unit_1 at (8,42), d=56, over ff_unit_0 at (6,41), d=57; OFF took ff_unit_0 from the berth, d=65.
     ff_unit_1: route_blocked unassign s58, died s72 at (0,8). victim_3 waited until s208 and was not reached
     by 240. OFF re-assigned victim_3 at s118 and rescued it at s189.
   east/half/101  victim_0 - M2. The first two rescues ran 14 and 15 steps early (contacts 26/66 vs 40/81),
     so ff_unit_0 was back at s75 instead of s90. victim_0 (confirmed s77 in both; OFF delayed at s77 and s85
     with no unit free) was assigned at s77, not s90. At that call the unit was 2 cells from its return cell,
     d 28 vs 24 (+4), time to contact 23 vs 24: no latency cost. Contact came at s100 at (35,14) instead of
     s114 at (36,12). The exit rule (nearest edge; a tie keeps the first key) sends (35,14) EAST to (49,14)
     (a 14/14 tie) and (36,12) SOUTH to (36,0). The DRY escort went east, spent 12 frames at fire distance
     <= 1, was route_blocked (unassign s135), and the victim died s138. OFF completed at s127.
   east/def/101  victim_3 - M3+M1 at a LATER call, on top of an 86-step first streak. ff_unit_0 was not
     dispatched for 86 steps and walked 31 cells toward the fire (28 at the call). At s86 it was nearer
     victim_0 (d=30) than ff_unit_1 (d=32, idle without a plan at (32,49)), so it took victim_0 (OFF:
     ff_unit_1, d=39). victim_3's call at s117 then went to ff_unit_1, engaged 12 cells from its return cell,
     at (36,48), d=56 (OFF: ff_unit_0 from the berth, d=65). ff_unit_1 walked down x=37 to (37,15) by s159,
     then crept south-west along the fire's edge: (27,7) at s219, (23,7) at s237. It never reached the victim,
     which had moved to (18,1) by s237 (min fire distance 2, 0 route_blocked frames over 124 frames). OFF's
     unit reached the victim in 65 steps.
   east/def/303  ff_unit_1 death - M2. The step-1 walk went SOUTH along x=2 to (2,30)/(2,31). That shortened
     victim_2 (d 13 vs 28) and lengthened victim_1 (d 40 vs 25). The swapped return times gave victim_0 to
     ff_unit_0 at s49 (OFF: ff_unit_1) and made ff_unit_1 a second claimant on its return (s63/s64). It spent
     19 frames route_blocked and died at s141. It was not engaged at its own call.
   east/half/404  ff_unit_1 death (count-neutral) - M2, downstream of the victim_1 gain. It came back at
     (32,49), was assigned victim_2 at s53 from (30,49), and died at s72 after 18 route_blocked frames.
  GAINS
   east/half/404  victim_1 dead -> rescued - M1 at the first dispatch, helpful direction. ff_unit_1 was 11
     cells out at (10,43), d 20 vs 25, and made contact at s41. In OFF the unit was route_blocked at s46 and
     the victim died at s48.
   south/half/202  victim_0 -> rescued, and OFF's ff_unit_0 death - M2. ff_unit_0's first rescue ran 13 steps
     early (contact 59 vs 72), so victim_0 was assigned at s68, not s81 (OFF delayed at s68 and s76). The DRY
     unit was blocked, re-assigned at s96, and made contact at s166. OFF's unit, called at s81, died en
     route at s207.
   east/half/606  OFF's ff_unit_0 death avoided (victim_0 dead -> unresolved) - M1 at a later call, the
     classic preempted-far case. At s139 the same unit had been engaged for 66 steps and was 32 cells out at
     (20,27), d 37 vs 29. It never reached the victim: it held at (21,22) from about s163 to s181, and was
     route_blocked (unassign s204). OFF's unit made contact at s165;
     its escort was route_blocked at s205, the victim died s207 and the unit s210.
   east/half/101 and east/half/404  OFF's post-terminal idle deaths (s195 at (39,0), s240 at (27,0)) do not
     occur in DRY - M5.
  COUNTS (section 3): M1 loss 4 / gain 2 / neutral 1; M2 loss 3 / gain 2; M3(+M1) loss 2; M5 gain 2; M4 0.

A5 THE CRUX
  THE LOSS IS NOT A PER-ASSIGNMENT "FAR AWAY" COST.
   - At the calls that lost a rescue, DRY's unit was Manhattan-CLOSER than OFF's in 3 of 4: south/404 -9,
     east/def/101 -9, south/909 -14. In the fourth (east/half/101) it was +4, and contact came 1 step sooner.
   - The only preempted-far call in the sample (east/half/606: +8, 32 cells out) cost no rescue and avoided a
     unit death.
   - There is no systematic latency cost (A3).
  IT IS WHERE THE UNITS ALREADY ARE WHEN THE CHAIN STARTS: the walk of steps 1-14/16, before any victim is
  confirmed.
   - Directly from that window: 2 of 4 rescue losses (south/404, south/909), 3 of 4 added deaths (south/404,
     south/808, south/909) and one gain (east/half/404).
   - Through the re-timing it causes: east/half/101 (loss), east/def/303 (death), south/half/202 (gain), and
     the count-neutral east/half/404 death.
   - Only east/def/101 (loss) and east/half/606 (death avoided) are decided at a later call, and both come
     out of long idle streaks. In east/def/101, ff_unit_0 walked for 86 steps (28 cells out at s86), and the
     s117 call landed on ff_unit_1 after 84 idle rows, 12 cells out. In east/half/606 the streak was 66
     steps, 32 cells out.
  WHAT A CHOOSER CAN AND CANNOT DO
   - At the first dispatch the two units stand together: 1 cell apart on 21/23 runs, and the other unit is
     exactly 1 cell farther from the victim on 22/23. Picking the other unit changes nothing. No chooser
     among available units could have avoided south/909 or south/808, nor south/404 beyond a 1-cell tie.
   - Manhattan distance is the wrong cost. Units walk greedily: agents.Firefighter._move_toward takes the
     best non-burning neighbour, with no path planning. A fire-ward start with a SHORTER distance walks into
     the flank (909, 808, 404) or stalls behind the fire (east/def/101). A fire-aware path cost could see a
     stall, but at the first dispatch there was no alternative unit to choose.
   - Re-timing (east/half/101, south/half/202, east/def/303) has no signature at the call: displacement 2, or
     not engaged. It cuts both ways. In rescued: one gain (south/half/202) against one loss (east/half/101).
     In unit deaths: one avoided (south/half/202) against one added (east/def/303). No chooser can target it.
   - A commitment limit works on the cause, not the call. A leash of N caps the pre-dispatch walk and so the
     first-dispatch head start at N cells. It should remove the first-dispatch M1 losses AND the re-timing
     gains and losses together. f2GD removes the walk entirely.
  WOULD ONE IDLE UNIT GOING (INSTEAD OF BOTH) HAVE AVOIDED EACH LOSS? (section 5 counterfactual first-window
  choices; validated 23/23 against both arms)
   - south/half/909, south/half/808: NO. A single engaged unit is 14-15 cells Manhattan-closer to victim_3
     than the berth unit (U0: 51 vs 66; U1: 52 vs 65), so the chooser still sends it from the flank. Under U1
     it starts at (9,39) / (5,35), one cell from DRY's fatal start.
   - south/half/404: NO under U1 (ff_unit_1 from (8,42), DRY's exact start). Unknown under U0 (ff_unit_0 from
     (6,41), a start no arm has run).
   - east/half/101: plausibly YES under either. U1: victim_3 is served from the berth (d=65), so ff_unit_0
     returns on OFF's schedule. U0: ff_unit_0 takes victim_1 (d=12) and ff_unit_1 serves victim_3 from the
     berth (d=66), which again puts victim_0's server back around OFF's s90.
   - east/def/101: plausibly YES under either. It needs one unit left undispatched on a long engaged walk
     while the other serves victim_1. With only one engaged unit, that unit takes victim_1 at s14 (d=11 or
     12), and the berth unit is the one left for victim_3.
   - Deaths: east/def/303 plausibly avoided under U0 (OFF's identities at s49); unknown under U1.
"""

PREREG = r"""
====================================================================================================
PART B. PRE-REGISTRATION FOR THE RUNNING PROBES (all DRY): f2U0D, f2U1D, f2L3D, f2L8D, f2GD
====================================================================================================
Written before any f2 output was opened; this script reads none. Under the conclusion of A5, per changed run.
"OFF" = the fmOFF outcome on that item, "DRY" = the fmDRY outcome, "?" = no confident prediction.
Confidence in brackets: H high, M medium, L low.
Assumptions (not verified):
  - a lone engaged unit follows its DRY path until its first call (the paths of the two units do not interact)
  - later behaviour is argued qualitatively from the first-window choices of section 5
A leash of N holds the unit at the last DRY path cell within N of its berth (section 5 L3/L8 rows).

f2GD (engage only while no victim is unresolved)
  - value-identical to fmOFF through OFF's terminal_step on 23/23 runs; there is nothing to engage before
  - every victim's final status equals OFF on 23/23: rescued 68 counted, 59 de-duplicated
  - unit deaths may differ only after terminal_step. Candidates are OFF's post-terminal idle deaths:
    east/half/101 s195, east/half/404 s240, south/half/303 s216, east/half/909 s189   [H]
  It removes the walk wholesale, so it cannot tell M1 from M2. It is the positive control for "the walk is
  the cause".

run / item                        f2U0D           f2U1D              f2L3D          f2L8D
south/half/909 v3 + ff death      DRY [H-M]       DRY, ff_unit_1     OFF [M]        ? [L]
                                                  dies [M]
south/half/808 ff death           DRY [H-M]       DRY, ff_unit_1     OFF [M]        OFF [L]
                                                  dies [M]
south/half/404 v3 + ff death      ? [-]           DRY [M]            OFF [M-L]      ? [L]
east/half/101 v0                  OFF [M]         OFF [M]            OFF [L]        ? [L]
east/def/101 v3                   OFF [M]         OFF [M]            OFF [M]        OFF [M-L]
east/def/303 ff death             OFF [M]         OFF [L]            OFF [L]        DRY [L]
east/half/404 v1 (gain)           OFF = lost [H]  OFF = lost [H]     ? [L]          ? [L]
south/half/202 v0 (gain)          DRY = kept [M]  DRY = kept [L]     OFF = lost [L] ? [L]
east/half/606 ff death avoided    OFF [M-L]       OFF [M]            OFF [M]        ? [L]

WHY, per column (the first-window choices come from section 5):
  f2U0D - ff_unit_0 still starts the first call for victim_3 from the flank in 909 (10,39) and 808 (6,35).
          It takes victim_1 at s14 in east/half/101, 606 and def/101, which returns their chains to OFF's
          identities. victim_1 in east/half/404 goes to ff_unit_1 from the berth (d=25, OFF's call). The
          south/half/202 head start on victim_3 is ff_unit_0's own.
  f2U1D - ff_unit_1 takes victim_3 from (9,39) / (5,35) / (8,42) in 909 / 808 / 404 (d 52 / 52 / 56 vs the
          berth unit's 65). In east/half/404 it takes victim_3 at s15, so victim_1 goes to ff_unit_0 from the
          berth (d=26, one more than OFF). In east/half/606, ff_unit_0 is never engaged: it stands at (25,0) at
          s139 as in OFF.
  f2L3D - first calls start at most 3 cells out: 909 (4,44), 808 (2,42), 404 (5,45) for victim_3. Head starts
          shrink to <= 3 steps, so the re-timed chains land within a few steps of OFF, and the gains go with
          them.
  f2L8D - starts at most 8 cells out: 909 (7,42), 808 (3,38), 404 (7,42). Some are on the flank corridor and
          some are not. Re-timing of up to 8 steps is enough to flip the timing-sensitive items either way.

WHAT WOULD REFUTE A5
  - f2U0D and f2U1D BOTH recover south/half/909 (victim_3 rescued, no death) and south/half/808 (no death).
    That would mean the first-dispatch flank start is not the mechanism.
  - f2L8D recovers every loss while keeping both gains. That would favour a per-assignment cost of the
    engaged unit over the pre-dispatch walk.
  - f2L3D differs from OFF on the changed items as often as fmDRY does.
  - f2GD differs from OFF on any victim before terminal_step. That would mean something other than
    engagement moves the chain.
  Pooled totals are NOT predicted for the U and L arms. Every one of them re-times all 23 chains differently,
  so new flips on the 14 unchanged runs are expected in both directions. Read them per run, against this
  table.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    R = {}
    for t in ALL:
        for tag in ("fmOFF", "fmDRY"):
            R[(tag, t)] = Run(tag, t)
    for block in (HEADER, NARRATIVE, PREREG):
        for line in block.strip("\n").split("\n"):
            say(line)
        say("")
    say("=" * 100)
    say("COMPUTED SECTIONS")
    say("=" * 100)
    section0(R)
    changed = section1(R)
    facts = section2(R, changed)
    section3(R, changed, facts)
    section4(R)
    section4b(R)
    section5(R, changed)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
