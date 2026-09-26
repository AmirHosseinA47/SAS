"""Carrying-leg round, Part 2/3: THE LEG-LEVEL SECTIONS of the analyzer (spec
outputs/_cl_tooling_spec.txt H2-H5 and H7-H13; design outputs/carryleg_part1.txt 9.3-9.4;
maintainer answers D-3, D-7, D-8, D-9 of 2026-09-26).

TWO ENTRY POINTS
  sections(ctx)  The hook outputs/_cl_analyze.py calls once G1 has passed (its HOOK
                 CONTRACT). Writes its tables through ctx.say(), raises STOP items through
                 ctx.stop(), routes items to the maintainer through ctx.to_maintainer(), and
                 returns {"gates": {ARM: {"G2": .., "G5": .., "INV": .., "ENG": ..,
                 "CREDIT": ..}}} for the stock fix arms in ctx.GATE_ARMS (a CRN twin's
                 evidence is filed under its stock tag).
  --selftest     .venv/Scripts/python.exe -B outputs/_cl_legs.py --selftest
                 The PRE-WAVE reproduction of the record (spec H5 "before any wave"), the
                 leg / drop / exposure checks on the recorded uhD U30 runs, the recorded
                 relabelled-corpse case (three named south/half/606 runs) and constructed
                 checks of the review-round rules (pair classes, extinguish order, mode-2
                 alignment, the rbcompare rescued line). Prints; writes NOTHING; exit 0 only
                 if every check reproduces ("LEGS SELFTEST PASS").

QUARANTINE (spec A1). outputs/_firemech_rewound_20260914/ is never read, listed or traversed.
The ONLY directory listing in this file is os.listdir(outputs/) (non-recursive; the
quarantine name is skipped by string compare before anything else is done with an entry):
in the self-test census and in the G5 shard-glob check. Every file opened is a named file.
The G5 subprocess (_ffr_rbcompare.py) globs outputs/_rblatch_camp2_<tag>*_D_<wind>.json,
a non-recursive pattern that cannot match the quarantine name.

ROW CONVENTION (spec H). An event stamped s happened DURING model step s. C.ff_row(d, s, F)
is F's row AFTER step s (ff_steps[s-1]); the state at the START of step s is
C.ff_row(d, s-1, F) = ff_steps[s-2] - the spec's "row s-2" (index notation, H3/H5/H11) and
its "row k-1" (step notation, H4/H8) name that same start-of-step row.

WHAT EACH SECTION COMPUTES (all from the run JSON + its sidecar; numbers are counts)
  H2  LEGS (C.legs): per tag/set M1a (n > d_c+5), M1b (n > d+5), M1c (stalled-or-broken),
      broken by cause, horizon, excess, reversals. Per arm vs its control, same instrument:
      matched legs on (tuple, unit, victim, pickup step, pickup cell); first divergence
      (fire_digests + ff_steps); a PRE-divergence leg without a match is an ANALYZER DEFECT
      (STOP). Every matched pair is classified (classify_pair):
        LONGER             the CONTROL leg completed and the arm leg is longer or did not
                           complete: identical fire over [pickup, control end] = AUTOMATIC
                           FAIL, else first differing step + what differed + the feature
                           site that fired first + the arm leg's end cause + the CRN
                           comparison of the same tuple/unit/victim (clK<arm> vs clKC) -> to
                           the maintainer (D-3)
        LONGER-UNFINISHED  NEITHER leg completed and the arm kept custody longer (e.g. a
                           control drop @169 vs a held carrier dying @171): NOT a longer
                           delivery - listed with both victim fates / death steps and both
                           carrier deaths and routed to the maintainer, never auto-failed
                           (review finding 1; consistent with _cl_analyze G3 b, which only
                           counts a LONGER whose control leg completed)
        HORIZON-BROKE      the control is still carrying at the horizon and the arm leg
                           broke: listed on its own line, routed to the maintainer
        CONVERSION / SHORTER / EQUAL
      Conversions, coverage (pre/post-divergence), post-divergence legs side by side. G2
      (design 9.4, D-7): MODE arms and clA: N30 M1c strictly lower, stock + CRN pooled
      (hard); every arm: per set per instrument not higher (both instruments higher ->
      FAIL, one -> maintainer, legs listed); HOLD/SERVED-only arms: N30 pooled not higher
      (hard); none-longer over C13/U30/N30 (RB7, the G5 re-roll instrument with no CRN arm,
      is NOT gated: its LONGER legs are printed in H2 as information only). clOA (D-4):
      C13 + U30 stock vetoes and none-longer only. No per-set verdict at all -> UNTESTED.
  H3  M3: every control carrier drop (replacement_after_blocked unassign of a unit exiting
      at the start of the step) with its class A/B/C/D, matched to the arm's same carry ->
      completed (CONVERTED) / died in custody / isolation release / horizon / drop / other /
      unmatched. Every drop must also be a sidecar enclosure trigger (STOP otherwise). Per drop,
      the D-8 evidence from the run's own rows (report only): replacement assigns of the victim,
      picked up again or not, rescued or not, death step, closest approach of any other unit.
  H4  M-HOLD: held advances derived from rows (start row exiting+alive at p; end row
      exiting+alive at p, or dead with a casualty unassign; no completion; every in-grid
      neighbour burning at the carrier's DECISION time: burning in the post-step
      observation, or put out later in the same step by an extinguish write of a unit that
      acts after the carrier - firefighters advance in ff_steps row order), cross-checked
      with the sidecar holds (HOLD arms: equal sets, and the sidecar's enclosure triggers ==
      its holds; HOLD 0: no sidecar hold, rows = second-raise holds, reported). Episodes,
      lengths, endings (moved on - extinguished / burnt out -, died in custody, isolation,
      horizon, other). Any hold > 30 advances: STOP.
  H5  M4: custody markings (unreachable_escape_log geographically_isolated at s, victim v,
      a unit exiting + alive + on grid in ff_steps[s-2] and bound to v in
      ff_bind_steps[s-2], no other unassign and no completion of v by it at s); M4a with a
      geographically_isolated unassign of (F, v) at s, M4b without; co-marked victims
      separately; per SERVED pair (and the D-9 probe pairs) the matched custody table.
  H7  M6: E1 searcher-only / E2 all UAVs, the _sfx_analyze.sec_exposure computation
      (replicated; asserted equal to _sfx_analyze's own output on the first run loaded).
  H8  M7: in fire at decision time (escaped / died), fire-adjacent at end of step over all
      carrying rows and over the replay window (completed legs, s0+1..s1-1); end-of-step
      in fire for a live carrier is an instrument assertion (must be 0, STOP otherwise).
  H9  M10: completions whose cell burns at the completion step; units dead on their own
      completion step; off-exit completions (mode >= 1).
  H10 M11: sidecar path/fallback steps, fallback legs and their fate vs the matched control
      carry; ONE-SIDED invariant (every path-step destination neither burning nor
      4-adjacent to a burning cell at that step) and the event-vs-row alignment: STOP on
      any breach. Mode-2 arms: the carrying steps are ALSO derived from rows alone (start
      row exiting, alive, on grid, off the boundary) and each must carry exactly one
      exit_leg_steps event from its start cell (none only with an unassign of that unit at
      that step), and no event may fall elsewhere - so a sidecar without the events cannot
      pass vacuously. A sidecar "absent" list is allowed only at the 6160438 worktree.
  H11 INVARIANTS (STOP): HOLD arms 0 carrier drops; SERVED arms M4 = 0; clSN footprint
      (value-identical to clC without a clC custody marking, else first differing at the
      first one, events before it identical); victim "dead" never reverts; victim_dead
      events <= dead victims + RELABELLED CORPSES (a victim row after step s with a live
      status on a cell burning at s: a unit died bound to a victim swept dead in the same
      casualty check, and its reset_victim_pending unassign relabelled the corpse, which is
      killed again - a pre-existing model path, review finding 2). Each relabel must be
      attributed to a firefighter_fire_casualty unassign naming the victim at s (else STOP);
      the unit not exiting at the start of s -> reported and routed to the maintainer as
      pre-existing; exiting in a HOLD >= 1 arm -> STOP (the D2 guard should have omitted
      the flag). Each feature arm's own switch reads non-zero in its sidecar.
  H12 ENGAGEMENT: runs that differ from the control (first differing step over every
      per-step series, or other keys) and the feature site that fired first; NOT ENGAGED
      otherwise. Per arm (stock + CRN twin, every queued run) each switched-on feature's OWN
      site count: MODE = path steps + off-exit completions, HOLD = holds, SERVED =
      served_by_custody_only_not_geo (a prevented isolation-streak increment). A count of 0
      prints "<FEATURE> UNTRIGGERED IN PART 3" at stage 3 - combination arms included - and
      SERVED's goes to the maintainer (D-9: never credited with what it did not do). CREDIT
      uses the same attribution: HOLD only from a converted carry whose arm leg contains a
      hold of that unit, SERVED only from a removed custody marking in a run where SERVED's
      own site fired.
  H13 G5: _ffr_rbcompare.py --new <clG arm> --old ihrest / --old clGC (and clGC vs ihrest)
      as subprocesses; regressions outside {east/707, south/101, south/202, south/404}:
      re-roll status from the arm's and clC's STOCK harness runs of the tuple (C13 or RB7):
      RE-ROLLED iff fire_digests first differ before clC's terminal_step within steps
      1-240; not re-rolled -> NEW FAIL; re-rolled regressions judged on pooled rescued over
      every re-rolled rbgate seed (clG<arm> vs clGC shards), a pooled loss -> CRN pair
      required (maintainer); each regression's 240/360 outcome from the harness runs
      ("delay" when the loss vanishes at 360; never turns a FAIL into a PASS); the latched
      line gated against the control's. The parsed regression lines are checked against
      rbcompare's own "[PASS|FAIL] rescued does not decrease" line (FAIL with none parsed,
      or PASS with some, is a STOP - a format drift cannot make G5 pass vacuously).
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import fnmatch
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import _cl_common as C  # noqa: E402

RANK = {"UNTESTED": 0, "PASS": 1, "TO-MAINTAINER": 2, "FAIL": 3}
HOLD_MAX = 30                      # spec H4: every hold <= 30 advances
SEARCHER = "victim_searcher"       # _sfx_analyze.SEARCHER
LEG_SETS = ("C13", "U30", "N30", "RB7")
G2_SETS = ("C13", "U30", "N30")
RB_KNOWN = frozenset({("east", 707), ("south", 101), ("south", 202), ("south", 404)})
RB_OLD = "ihrest"
RB_CONTROL = "clGC"
RB_PREFIX_HORIZON = 240
RBCOMPARE = os.path.join(HERE, "_ffr_rbcompare.py")
PROBE_PAIRS = (("clPS1", "clPS0"), ("clKPS1", "clKPS0"))
CAST = "firefighter_fire_casualty"
ISO = "geographically_isolated"
RAB = "replacement_after_blocked"
# review finding 4: each feature's OWN site (Analysis.run_sites)
FEATURES = (("MODE", C.MODE), ("HOLD", C.HOLD), ("SERVED", C.SERVED))
SITE_DEF = {"MODE": "mode-2 path steps + off-exit completions",
            "HOLD": "sidecar holds",
            "SERVED": "sidecar served_by_custody_only_not_geo, a prevented isolation-streak increment"}

# the self-test census (spec H5; task: non-recursive _ffr_*.json, _ffr_xs* and .xstrace. excluded;
# _ffr_cl* - this round's own runs - excluded too, so the record reproduction cannot move)
CENSUS_RE = re.compile(r"^_ffr_(.+)_(east|west|north|south)_(half|def)_(\d+)\.json$")
CENSUS_SKIP_PREFIXES = ("_ffr_xs", "_ffr_cl")
CENSUS_RECORDS = 31
CENSUS_DISTINCT = 9
CENSUS_CASE = ("f2cDRY", "east", "def", 101, "victim_0", 177, "ff_unit_1")
CENSUS_M4B = 0
UHD_COMPLETED, UHD_M1B = 102, 5          # task: M1b on recorded uhD U30 = 5 of 102 completed
UHD_M7_WINDOW = 16                       # spec/design M7: fire-adjacent, replay window, uhD
UHD_DROP = (("east", "half", 1291443119), "ff_unit_1", "victim_0", 148, "C")


def merge(verdicts):
    vs = [v for v in verdicts if v is not None]
    return max(vs, key=lambda v: RANK[v]) if vs else "UNTESTED"


def yn(b):
    return "yes" if b else "NO"


def lc(c):
    return "-" if c is None else "(%d,%d)" % (c[0], c[1])


# =============================================================================================
# RUN-LEVEL MEASUREMENTS (pure functions of one run dict [+ its sidecar dict])
# =============================================================================================
def nsteps(d):
    return len(d.get("ff_steps") or [])


def first_dead(d, vid):
    """First step whose victim_steps row shows vid dead, or None."""
    for i, row in enumerate(d.get("victim_steps") or []):
        for v in row:
            if v[0] == vid and v[2] == "dead":
                return i + 1
    return None


def ff_extinguishes(d):
    """{(step, cell): {unit ids}} of firefight_log EXTINGUISH entries with wrote True (for an
    extinguish the written cell is 'target' == the plan cell; agents.py _firefight_execute).
    "clear" writes (fuel removal) never change whether a cell burns and are excluded."""
    out = collections.defaultdict(set)
    for e in d.get("firefight_log") or []:
        if (e.get("action") == "extinguish" and e.get("wrote") and e.get("target") is not None
                and e.get("step") is not None):
            out[(int(e["step"]), C.cell(e["target"]))].add(str(e.get("ff")))
    return dict(out)


def ff_order(d):
    """{unit: index} in ff_steps row order - the firefighters' advance order. The harness
    builds each row from model.firefighter_marker_agents (insertion order); the model adds
    each marker to that dict and to the SimultaneousActivation schedule in the same loop,
    and only DEAD firefighters ever leave the schedule, so among live units the row order
    is the advance order. Asserted constant over every row (ANALYZER DEFECT otherwise)."""
    rows = d.get("ff_steps") or []
    ids = [r[0] for r in rows[0]] if rows else []
    for i, row in enumerate(rows):
        if [r[0] for r in row] != ids:
            C.defect("%s ff_steps row %d unit order %r != row 1 order %r"
                     % (C._runlabel(d), i + 1, [r[0] for r in row], ids))
    return {u: i for i, u in enumerate(ids)}


def enclosing(burn, ext, order, ff, n, k):
    """Neighbour n counts as burning at carrier ff's DECISION time in step k. Every ignition
    happens in the Fire agents' advance, before any firefighter's (the Fire agents are the
    first schedule entries), so n burned at ff's decision iff it burns in the post-step-k
    observation, or an extinguish write at (k, n) came from a unit that acts AFTER ff (an
    extinguish by a unit acting BEFORE ff means ff already saw n clear)."""
    if burn.burning(n, k):
        return True
    me = order.get(ff)
    if me is None:
        return False
    return any(order.get(u, -1) > me for u in ext.get((k, n), ()))


def unassigns_by(d):
    """{(step, ff): [unassign entries]} in list order."""
    out = collections.defaultdict(list)
    for u in d.get("unassigns") or []:
        out[(int(u.get("step", -1)), u.get("ff"))].append(u)
    return out


def drop_class(d, s, ff, vid, p, deaths):
    """Design section 1 C4 drop classes. A: carrier and victim dead at s; B: the carrier stays
    on the drop cell and dies with the victim (same step); C: the carrier moves off alive
    (first row >= s whose cell differs from the drop cell shows it alive); D: other."""
    d_ff, d_v = deaths.get(ff), first_dead(d, vid)
    if d_ff == s and d_v == s:
        return "A"
    for t in range(s, nsteps(d) + 1):
        r = C.ff_row(d, t, ff)
        if r is None or r[5]:
            break
        if C.cell(r[1]) != p:
            return "C"
    if d_ff is not None and d_v is not None and d_ff == d_v:
        return "B"
    return "D"


def drops(d):
    """Spec H3: every replacement_after_blocked unassign at step s whose unit was exiting at
    the START of step s (ff_steps[s-2]). -> [dict(step, ff, vid, cell, cls, ff_death, v_death)]"""
    out = []
    deaths = C.ff_deaths(d)
    for u in d.get("unassigns") or []:
        if u.get("reason") != RAB:
            continue
        s, ff, vid = int(u["step"]), u.get("ff"), u.get("vid")
        r = C.ff_row(d, s - 1, ff) if s >= 2 else None
        if r is None or not r[4]:
            continue
        p = C.cell(r[1])
        rec = dict(step=s, ff=ff, vid=vid, cell=p, cls=drop_class(d, s, ff, vid, p, deaths),
                   ff_death=deaths.get(ff), v_death=first_dead(d, vid))
        rec["help"] = drop_help(d, rec)
        out.append(rec)
    return out


def help_str(dr):
    h = dr["help"]
    cl = h["closest"]
    return ("D-8: replacement assigns %d%s; picked up again %s; rescued %s; victim dead %s%s; closest other unit %s"
            % (len(h["assigns"]), (" (%s)" % ", ".join("%s@%d %s" % (a[1], a[0], a[2]) for a in h["assigns"]))
               if h["assigns"] else "", ("@" + ",".join(str(x) for x in h["repick"])) if h["repick"] else "no",
               yn(h["rescued"]), dr["v_death"], (" (+%d)" % (dr["v_death"] - dr["step"])) if dr["v_death"] else "",
               ("%s at distance %d @%d" % (cl[2], cl[0], cl[1])) if cl else "none alive on grid"))


def drop_help(d, dr):
    """D-8 evidence for one drop, from this run's own rows (report only): replacement assigns of the
    victim at or after the drop step, whether the victim was ever picked up again (an exit_start
    after the drop) or rescued, its death step, and the closest approach of any OTHER unit (alive,
    on grid) to the victim's cell from the drop until its death (or the horizon)."""
    s, ff, v = dr["step"], dr["ff"], dr["vid"]
    assigns = [a for a in d.get("assigns") or [] if a.get("vid") == v and int(a.get("step", -1)) >= s and a.get("ok")]
    repick = [int(e["step"]) for e in d.get("exit_starts") or [] if e.get("victim") == v and int(e["step"]) > s]
    rescued = any(c.get("victim") == v and int(c["step"]) >= s for c in d.get("completions") or [])
    end = dr["v_death"] or nsteps(d)
    best = None
    for t in range(s, end + 1):
        vr = C.victim_row(d, t, v)
        vc = C.cell(vr[1]) if vr else None
        if vc is None:
            continue
        for r in C.row_after(d, "ff_steps", t) or []:
            if r[0] == ff or r[5] or r[1] is None:
                continue
            dist = C.md(C.cell(r[1]), vc)
            if best is None or dist < best[0]:
                best = (dist, t, r[0])
    return dict(assigns=[(int(a["step"]), a.get("ff"), a.get("reason")) for a in assigns], repick=repick,
                rescued=rescued, closest=best)


def custody_markings(d):
    """Spec H5 / design 9.3 M4. None when the run has no ff_bind_steps; else
    (markings, comarked, skipped):
      markings  [dict(step, victim, units [(ff, 'M4a'|'M4b')], kind, ff, streak)] - one per
                geographically_isolated escape-log entry with >= 1 custody unit
      comarked  [dict(step, victim, cause)] - the other escape entries at a marking's step
      skipped   geographically_isolated entries at step < 2 (no start-of-step row)"""
    binds = d.get("ff_bind_steps")
    if not isinstance(binds, list) or not binds:
        return None
    esc = d.get("unreachable_escape_log") or []
    ua = unassigns_by(d)
    comps = {(int(c["step"]), c.get("ff"), c.get("victim")) for c in d.get("completions") or []}
    marks, skipped = [], 0
    for e in esc:
        if e.get("cause") != ISO:
            continue
        s, v = int(e["step"]), e.get("victim_id")
        fr, br = C.row_after(d, "ff_steps", s - 1), C.row_after(d, "ff_bind_steps", s - 1)
        if s < 2 or fr is None or br is None:
            skipped += 1
            continue
        bound = {b[0] for b in br if b[1] == v}
        units = []
        for r in fr:
            ff = r[0]
            if ff not in bound or not r[4] or r[5] or r[1] is None:
                continue
            mine = ua.get((s, ff), [])
            if any(u.get("reason") != ISO for u in mine) or (s, ff, v) in comps:
                continue
            geo = [u for u in mine if u.get("reason") == ISO and u.get("vid") == v]
            units.append((ff, "M4a" if geo else "M4b"))
        if units:
            kind = "M4a" if any(k == "M4a" for _f, k in units) else "M4b"
            marks.append(dict(step=s, victim=v, units=units, kind=kind, ff=units[0][0],
                              streak=e.get("streak")))
    at = {m["step"] for m in marks}
    got = {(m["step"], m["victim"]) for m in marks}
    comarked = [dict(step=int(e["step"]), victim=e.get("victim_id"), cause=e.get("cause"))
                for e in esc if int(e["step"]) in at and (int(e["step"]), e.get("victim_id")) not in got]
    return marks, comarked, skipped


def held_advances(d, burn, ext):
    """Design M-HOLD from rows: {(k, ff): dict(pos, died)} for every advance k where the start
    row (after k-1) shows ff exiting + alive at p, the end row (after k) shows it exiting +
    alive at p - or dead with a firefighter_fire_casualty unassign at k (died at once) - no
    completion by ff at k, and every in-grid 4-neighbour of p is burning at ff's decision
    time (enclosing)."""
    out = {}
    comps = {(int(c["step"]), c.get("ff")) for c in d.get("completions") or []}
    cas = {(int(u["step"]), u.get("ff")) for u in d.get("unassigns") or [] if u.get("reason") == CAST}
    rows = d.get("ff_steps") or []
    order = ff_order(d)
    for k in range(2, len(rows) + 1):
        cur = {r[0]: r for r in rows[k - 1]}
        for r in rows[k - 2]:
            ff = r[0]
            if not r[4] or r[5] or r[1] is None or (k, ff) in comps:
                continue
            p = C.cell(r[1])
            c = cur.get(ff)
            if c is None:
                continue
            if c[4] and not c[5] and C.cell(c[1]) == p:
                died = False
            elif c[5] and (k, ff) in cas:
                died = True
            else:
                continue
            if all(enclosing(burn, ext, order, ff, n, k) for n in C.neighbours(p)):
                out[(k, ff)] = dict(pos=p, died=died)
    return out


def hold_episodes(d, held, ext):
    """Consecutive held advances per unit -> [dict(ff, start, end, length, pos, ending,
    cleared)]. ending: died_in_custody | horizon | moved_on | isolation | completed | drop |
    stayed | other; cleared (moved_on only): extinguished | burnt_out."""
    out = []
    steps = nsteps(d)
    ua = unassigns_by(d)
    comps = {(int(c["step"]), c.get("ff")) for c in d.get("completions") or []}
    by = collections.defaultdict(list)
    for (k, ff) in sorted(held):
        by[ff].append(k)
    for ff in sorted(by):
        ks = by[ff]
        runs, cur = [], [ks[0]]
        for k in ks[1:]:
            if k == cur[-1] + 1:
                cur.append(k)
            else:
                runs.append(cur)
                cur = [k]
        runs.append(cur)
        for run in runs:
            k0, k1 = run[0], run[-1]
            p = held[(k1, ff)]["pos"]
            ending, cleared = "other", None
            if held[(k1, ff)]["died"]:
                ending = "died_in_custody"
            elif k1 >= steps:
                ending = "horizon"
            else:
                e = k1 + 1
                r = C.ff_row(d, e, ff)
                reasons = [u.get("reason") for u in ua.get((e, ff), [])]
                if r is None:
                    ending = "other"
                elif r[5]:
                    ending = "died_in_custody" if CAST in reasons else "other"
                elif r[4] and C.cell(r[1]) != p:
                    ending = "moved_on"
                    q = C.cell(r[1])
                    cleared = ("extinguished" if any((t, q) in ext for t in range(k0, e + 1))
                               else "burnt_out")
                elif not r[4]:
                    if (e, ff) in comps:
                        ending = "completed"
                    elif ISO in reasons:
                        ending = "isolation"
                    elif RAB in reasons:
                        ending = "drop"
                    else:
                        ending = "other"
                else:
                    ending = "stayed"
            out.append(dict(ff=ff, start=k0, end=k1, length=len(run), pos=p, ending=ending,
                            cleared=cleared))
    return out


def m6(d):
    """_sfx_analyze.sec_exposure's per-run sums (E1 searcher-only, E2 all UAVs): the
    uav_actions burning bit (field 2) per (step, uid), the role from uav_steps (field 2), over
    range(run["steps"]) rows. -> (b1, n1, b2, n2) or None without uav_actions."""
    ua = d.get("uav_actions")
    if not ua:
        return None
    burn = {}
    for i, row in enumerate(ua):
        for r in row:
            burn[(i + 1, r[0])] = int(r[2])
    b1 = n1 = b2 = n2 = 0
    us = d["uav_steps"]
    for i in range(d["steps"]):
        for r in us[i]:
            v = burn.get((i + 1, r[0]), 0)
            n2 += 1
            b2 += v
            if r[2] == SEARCHER:
                n1 += 1
                b1 += v
    return (b1, n1, b2, n2)


def sfx_m6(d, label="RUN"):
    """The same four numbers as printed by _sfx_analyze.sec_exposure itself (imported; its
    stdout captured and parsed). Used only to assert the replication."""
    import _sfx_analyze as SFX  # noqa: E402  (module import lists nothing)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        SFX.sec_exposure([(label, {(d["wind"], d["roles"], d["seed"]): d})])
    for line in buf.getvalue().splitlines():
        parts = line.split()
        if parts and parts[0] == label and len(parts) >= 7:
            return (int(parts[1]), int(parts[2]), int(parts[4]), int(parts[5]))
    raise SystemExit("ANALYZER DEFECT - STOP: _sfx_analyze.sec_exposure printed no row for %s" % label)


def m7(d, burn, legs):
    """Design M7 / spec H8.
      in_fire_escaped / in_fire_died: carrying step k (start row exiting + alive at c), c
          burning at k; row k alive / dead
      adj_all: end-of-step rows exiting + alive at c with an in-grid 4-neighbour burning at k
      adj_window: the same over completed legs' rows s0+1..s1-1 (the replay's window)
      eos_in_fire: end-of-step rows exiting + alive ON a burning cell (instrument assertion 0)"""
    rows = d.get("ff_steps") or []
    esc = died = adj = eos = 0
    for k in range(1, len(rows) + 1):
        cur = {r[0]: r for r in rows[k - 1]}
        if k >= 2:
            for r in rows[k - 2]:
                if r[4] and not r[5] and r[1] is not None and burn.burning(C.cell(r[1]), k):
                    c = cur.get(r[0])
                    if c is not None and c[5]:
                        died += 1
                    else:
                        esc += 1
        for r in rows[k - 1]:
            if r[4] and not r[5] and r[1] is not None:
                c = C.cell(r[1])
                if burn.burning(c, k):
                    eos += 1
                if any(burn.burning(n, k) for n in C.neighbours(c)):
                    adj += 1
    win = 0
    for x in legs:
        if not x["completed"]:
            continue
        for k in range(x["s0"] + 1, x["end"]):
            r = C.ff_row(d, k, x["ff"])
            if r and r[4] and not r[5] and r[1] is not None:
                if any(burn.burning(n, k) for n in C.neighbours(C.cell(r[1]))):
                    win += 1
    return dict(in_fire_escaped=esc, in_fire_died=died, adj_all=adj, adj_window=win, eos_in_fire=eos)


def m10(d, burn):
    """Design M10 / spec H9: completions whose cell burns at the completion step; units dead on
    their own completion step; completions off the recorded exit cell (mode >= 1 only)."""
    deaths = C.ff_deaths(d)
    burning, death_on, off_exit = [], [], []
    for c in d.get("completions") or []:
        s, ff, pos = int(c["step"]), c.get("ff"), C.cell(c.get("pos"))
        if pos is not None and burn.burning(pos, s):
            burning.append((s, ff, c.get("victim"), pos))
        if deaths.get(ff) == s:
            death_on.append((s, ff, c.get("victim"), pos))
        if pos is not None and C.cell(c.get("exit_target")) != pos:
            off_exit.append((s, ff, c.get("victim"), pos, C.cell(c.get("exit_target"))))
    return dict(burning=burning, death_on=death_on, off_exit=off_exit)


def path_breach(burn, to, k):
    """Spec H10 one-sided invariant for a mode-2 path step landing on `to` at step k."""
    if to is None:
        return "no destination cell"
    if burn.burning(to, k):
        return "destination burning"
    hot = [n for n in C.neighbours(to) if burn.burning(n, k)]
    if hot:
        return "destination 4-adjacent to burning %s" % ", ".join(lc(n) for n in hot)
    return None


def m11(d, sc, burn, legs):
    """Spec H10 from the sidecar's exit_leg_steps events [step, unit, from, to, outcome]."""
    ev = ((sc or {}).get("events") or {}).get("exit_leg_steps") or []
    out = dict(path=0, fallback=0, other=0, breaches=[], rowmis=[], fallback_legs=[])
    fb = collections.defaultdict(list)
    for e in ev:
        k, unit, frm, to, outcome = int(e[0]), str(e[1]), C.cell(e[2]), C.cell(e[3]), str(e[4])
        if outcome == "path":
            out["path"] += 1
            why = path_breach(burn, to, k)
            if why:
                out["breaches"].append((k, unit, frm, to, why))
            ra, rb = C.ff_row(d, k, unit), C.ff_row(d, k - 1, unit)
            if ra is None or C.cell(ra[1]) != to or (rb is not None and C.cell(rb[1]) != frm):
                out["rowmis"].append((k, unit, frm, to, C.cell(rb[1]) if rb else None,
                                      C.cell(ra[1]) if ra else None))
        elif outcome == "fallback":
            out["fallback"] += 1
            fb[unit].append(k)
        else:
            out["other"] += 1
    hi_all = nsteps(d)
    for x in legs:
        hi = x["end"] if x["end"] is not None else hi_all
        ks = [k for k in fb.get(x["ff"], []) if x["s0"] < k <= hi]
        if ks:
            out["fallback_legs"].append((x, ks))
    return out


def mode2_carry_steps(d):
    """The mode-2 carrying steps derived from ROWS alone (review finding 3): {(k, ff): start
    cell} for every step k >= 2 whose start row (after k-1) shows ff exiting, alive and on
    grid on a cell off the boundary. Firefighter.advance (agents.py) returns at once for a
    dead or off-grid unit, skips the survival-retreat and firefight branches for an exiting
    one, completes on ANY boundary cell at mode >= 1 (the exit cell is a boundary cell), and
    otherwise calls _exit_leg_step exactly once - unless something earlier in step k (an
    unassign) ended the carry."""
    rows = d.get("ff_steps") or []
    out = {}
    for k in range(2, len(rows) + 1):
        for r in rows[k - 2]:
            if r[4] and not r[5] and r[1] is not None:
                c = C.cell(r[1])
                if not C.on_boundary(c):
                    out[(k, r[0])] = c
    return out


def mode2_alignment(d, sc):
    """Rows vs the sidecar's exit_leg_steps events for a MODE 2 run: every row-derived carrying
    step has exactly one event whose from-cell is the start-row cell (none is accepted only
    when the harness records an unassign of that unit at that step), and no event falls on
    any other (step, unit). -> dict(derived, events, excused, problems [str])."""
    ev = ((sc or {}).get("events") or {}).get("exit_leg_steps") or []
    by = collections.defaultdict(list)
    for e in ev:
        by[(int(e[0]), str(e[1]))].append(e)
    derived = mode2_carry_steps(d)
    ua = unassigns_by(d)
    problems, excused = [], 0
    for key in sorted(derived):
        k, ff = key
        got = by.get(key, [])
        if len(got) == 1:
            if C.cell(got[0][2]) != derived[key]:
                problems.append("%s@%d event from-cell %s != start-row cell %s"
                                % (ff, k, lc(C.cell(got[0][2])), lc(derived[key])))
        elif not got and ua.get(key):
            excused += 1
        else:
            problems.append("%s@%d carrying from %s in the rows: %d exit_leg_step event(s)%s"
                            % (ff, k, lc(derived[key]), len(got),
                               " and no unassign of the unit at that step" if not got else ""))
    for key in sorted(set(by) - set(derived)):
        problems.append("%s@%d: %d exit_leg_step event(s) where the rows show no mode-2 carrying step"
                        % (key[1], key[0], len(by[key])))
    return dict(derived=len(derived), events=len(ev), excused=excused, problems=problems)


def sites(d, sc):
    """Feature sites that fired, [(step, name)] sorted: the ones that can change behaviour."""
    ev = (sc or {}).get("events") or {}
    out = []
    for c in d.get("completions") or []:
        if C.cell(c.get("pos")) is not None and C.cell(c.get("pos")) != C.cell(c.get("exit_target")):
            out.append((int(c["step"]), "off-exit completion (mode>=1)"))
    for e in ev.get("exit_leg_steps") or []:
        if str(e[4]) == "path":
            out.append((int(e[0]), "mode-2 path step"))
    for e in ev.get("holds") or []:
        out.append((int(e[0]), "hold"))
    for e in ev.get("hold_starts") or []:
        out.append((int(e[0]), "hold reachability start"))
    for e in ev.get("casualty_unassigns") or []:
        if "reset_victim_pending" not in (e[3] or []):
            out.append((int(e[0]), "hold casualty guard (no reset_victim_pending)"))
    for e in ev.get("served_by_custody_only") or []:
        if not e[1]:
            out.append((int(e[0]), "custody-served (isolation streak increment prevented)"))
    return sorted(out)


def dead_reverts(d):
    """[(vid, first dead step, step it shows non-dead)] - victim_steps 'dead' must never revert."""
    seen, out = {}, []
    for i, row in enumerate(d.get("victim_steps") or []):
        for v in row:
            if v[2] == "dead":
                seen.setdefault(v[0], i + 1)
            elif v[0] in seen and v[0] not in {o[0] for o in out}:
                out.append((v[0], seen[v[0]], i + 1))
    return out


def victim_dead_events(d):
    """(victim_dead rescue events, distinct victims ever dead in victim_steps)."""
    ev = int((d.get("rescue_event_counts") or {}).get("victim_dead", 0) or 0)
    dead = set()
    for row in d.get("victim_steps") or []:
        for v in row:
            if v[2] == "dead":
                dead.add(v[0])
    return ev, len(dead)


def relabelled_corpses(d, burn):
    """Review finding 2: victims killed and RELABELLED within one step. wildfire_model
    _check_fire_casualties kills every victim not dead/rescued whose cell burns, then kills
    the firefighters on burning cells; a unit that dies bound to a victim swept dead just
    above is unassigned WITH reset_victim_pending (the D2 guard omits it only for an exiting
    unit at HOLD 1), which relabels the corpse "confirmed"; the next casualty check kills it
    again - a second victim_dead event for one victim (recorded dimfreshfix / ihofffresh /
    ihrest6fresh south/half/606, victim_3 @129 by the approaching ff_unit_1). Every ignition
    precedes the casualty check, so a row after step s showing a live status on a cell burning
    at s IS such a corpse. -> [dict(step, victim, status, cell, units [(ff, exiting at the start
    of s)], dead_at (first dead row))]; units = the firefighter_fire_casualty unassigns naming
    the victim at s (empty = UNEXPLAINED)."""
    out = []
    cas = collections.defaultdict(list)
    for u in d.get("unassigns") or []:
        if u.get("reason") == CAST:
            cas[(int(u.get("step", -1)), u.get("vid"))].append(u.get("ff"))
    for i, row in enumerate(d.get("victim_steps") or []):
        s = i + 1
        for v in row:
            c = C.cell(v[1])
            if v[2] in ("dead", "rescued") or c is None or not burn.burning(c, s):
                continue
            units = []
            for ff in cas.get((s, v[0]), []):
                r = C.ff_row(d, s - 1, ff) if s >= 2 else None
                units.append((ff, bool(r and r[4])))
            out.append(dict(step=s, victim=v[0], status=v[2], cell=c, units=units, dead_at=first_dead(d, v[0])))
    return out


def classify_pair(x, y):
    """A matched pair (control leg x, arm leg y) -> (category, kind), refining
    _cl_common.compare_legs (review finding 1):
      "LONGER"             x completed and y longer or not completed (compare_legs' LONGER
                           with a completed control) - the spec H2 / D-3 LONGER
      "LONGER-UNFINISHED"  neither completed and y kept custody longer (compare_legs' LONGER,
                           kind "unfinished") - not a longer delivery; to the maintainer
      "HORIZON-BROKE"      x still carrying at the horizon, y broke (compare_legs calls it
                           SHORTER or EQUAL) - a carry the arm lost; to the maintainer
      "CONVERSION" / "SHORTER" / "EQUAL"   as compare_legs"""
    v, kind = C.compare_legs(x, y)
    if v == "LONGER" and not x["completed"]:
        return "LONGER-UNFINISHED", kind
    if (not x["completed"] and x["cause"] == "horizon" and not y["completed"]
            and y["cause"] != "horizon"):
        return "HORIZON-BROKE", "horizon->%s" % y["cause"]
    return v, kind


def fates_str(dc, da, ctrl, arm, x):
    """Both victim fates, victim death steps and carrier death steps of a pair's carry."""
    v, ff = x["victim"], x["ff"]
    return ("victim %s: %s %s (dead @%s) | %s %s (dead @%s); carrier %s dead: %s @%s, %s @%s"
            % (v, ctrl, C.fate_str(C.victim_fate(dc, v)), first_dead(dc, v), arm, C.fate_str(C.victim_fate(da, v)),
               first_dead(da, v), ff, ctrl, C.ff_deaths(dc).get(ff), arm, C.ff_deaths(da).get(ff)))


def site_str(site):
    return "%s @%d" % (site[1], site[0]) if site else "none at or before the first differing step"


RESCUED_LINE_RE = re.compile(r"\[(PASS|FAIL)\] rescued does not decrease on any seed")


def rescued_line_problems(text, regr):
    """Review finding 8: the parsed regression lines must agree with _ffr_rbcompare.py's own
    '[PASS|FAIL] rescued does not decrease on any seed' line (it prints FAIL iff it lists a
    regression), so a format drift cannot turn into an empty regression set and a vacuous G5."""
    m = RESCUED_LINE_RE.search(text)
    if m is None:
        return ["no '[PASS|FAIL] rescued does not decrease' line"]
    if m.group(1) == "FAIL" and not regr:
        return ["rescued line FAIL but no regression line parsed"]
    if m.group(1) == "PASS" and regr:
        return ["rescued line PASS but %d regression line(s) parsed" % len(regr)]
    return []


def leg_outcome(y):
    if y is None:
        return "unmatched"
    if y["completed"]:
        return "completed@%d n=%d (CONVERTED)" % (y["end"], y["n"])
    if y["cause"] == "horizon":
        return "horizon (still carrying, elapsed %d)" % y["n"]
    return "%s@%d" % (y["cause"], y["end"])


# =============================================================================================
# THE HOOK
# =============================================================================================
class Analysis:
    def __init__(self, ctx):
        self.ctx = ctx
        self.say = ctx.say
        self.present = set(ctx.tags())
        self.tags = [t for t in C.ARMS if t in self.present]
        self.sw = {t: self._switches(t) for t in self.tags}
        self.S = {}
        self.P = {}
        self.pairs = []            # (arm tag, control tag, instrument, stock arm it is filed under)
        for arm in ctx.GATE_ARMS:
            ctrl = ctx.control_of(arm)
            if arm in self.present and ctrl:
                self.pairs.append((arm, ctrl, "stock", arm))
            k = ctx.crn_of(arm)
            kc = ctx.control_of(k) if k else None
            if k and kc:
                self.pairs.append((k, kc, "crn", arm))
        self.probe = [(a, c) for a, c in PROBE_PAIRS if a in self.present and c in self.present]
        self.gates = collections.OrderedDict((a, collections.OrderedDict()) for a in ctx.GATE_ARMS)
        self.m6_checked = None

    # ------------------------------------------------------------------ helpers --
    def _switches(self, tag):
        tl = self.ctx.tuples(tag)
        if not tl:
            return {}
        s = self.ctx.line(tag, tl[0])["sets"]
        return {k: s[k] for k in C.SWITCH_KEYS if k in s}

    def mode(self, tag):
        return int(self.sw.get(tag, {}).get(C.MODE, 0) or 0)

    def hold(self, tag):
        return int(self.sw.get(tag, {}).get(C.HOLD, 0) or 0) != 0

    def served(self, tag):
        return int(self.sw.get(tag, {}).get(C.SERVED, 0) or 0) != 0

    def inst(self, tag):
        return C.ARMS[tag]["instrument"]

    def stop(self, sec, msg):
        self.ctx.stop("%s %s" % (sec, msg))

    # --------------------------------------------------------------- collection --
    def collect(self):
        ctx = self.ctx
        for set_name in LEG_SETS:
            for tup in ctx.sets[set_name]:
                here = [t for t in self.tags if ctx.has(t, tup)]
                for t in here:
                    self.S[(t, tup)] = self._summ(t, tup, set_name)
                for a, c, inst, sarm in self.pairs:
                    if ctx.has(a, tup) and ctx.has(c, tup):
                        self.P[(a, c, tup)] = self._pair(a, c, tup, inst, sarm, set_name)
                for a, c in self.probe:
                    if ctx.has(a, tup) and ctx.has(c, tup):
                        self.P[(a, c, tup)] = self._pair(a, c, tup, self.inst(a), None, set_name)

    def filed_under(self, tag):
        """The stock gate arm a tag's evidence is filed under (a CRN twin -> its stock arm);
        a control or probe tag -> itself."""
        if tag in self.ctx.GATE_ARMS:
            return tag
        for arm in self.ctx.GATE_ARMS:
            if self.ctx.crn_of(arm) == tag:
                return arm
        return tag

    def _summ(self, tag, tup, set_name):
        ctx = self.ctx
        d = ctx.load(tag, tup)
        sc = ctx.sidecar(tag, tup)
        burn = C.Burn(d)
        ext = ff_extinguishes(d)
        legs = ctx.legs(tag, tup)
        steps = nsteps(d)
        s = dict(tag=tag, tup=tup, set=set_name, steps=steps, legs=legs)
        # review finding 3: only the 6160438 worktree (clB) may lack a wrapped name
        s["base"] = C.norm_repo(ctx.line(tag, tup)["repo"]) == C.norm_repo(C.BASE_REPO)
        absent = list(sc.get("absent") or [])
        if absent and not s["base"]:
            self.stop("H3/H10", "%s %s sidecar lists ABSENT wraps %s at repo %s (allowed only at %s): its event-based "
                             "checks would pass vacuously" % (tag, C.label(tup), absent, ctx.line(tag, tup)["repo"],
                                                              C.BASE_REPO))
        s["drops"] = drops(d)
        cm = custody_markings(d)
        if cm is None:
            self.stop("H5", "ANALYZER DEFECT: %s %s has no ff_bind_steps - custody markings cannot be read"
                      % (tag, C.label(tup)))
            cm = ([], [], 0)
        s["custody"], s["comarked"], s["custody_skipped"] = cm
        held = held_advances(d, burn, ext)
        s["held"] = held
        ev = sc.get("events") or {}
        cnt = sc.get("counters") or {}
        s["counters"] = cnt
        s["events_dropped"] = int(cnt.get("events_dropped", 0) or 0)
        side = {}
        for e in ev.get("holds") or []:
            side[(int(e[0]), str(e[1]))] = (C.cell(e[2]), e[3])
        s["holds_side"] = side
        encl = {(int(e[0]), str(e[1]), C.cell(e[2])) for e in ev.get("enclosure_triggers") or []}
        mis = []
        if self.hold(tag):
            for key in sorted(set(side) | set(held)):
                if key not in held:
                    mis.append("sidecar hold %s@%d at %s not a held advance in the rows" % (key[1], key[0], lc(side[key][0])))
                elif key not in side:
                    mis.append("rows show %s held @%d at %s, no sidecar hold" % (key[1], key[0], lc(held[key]["pos"])))
                elif side[key][0] != held[key]["pos"]:
                    mis.append("%s@%d sidecar cell %s != rows %s" % (key[1], key[0], lc(side[key][0]), lc(held[key]["pos"])))
            # review finding 3: at HOLD 1 every enclosure trigger IS a hold (agents.py _move_toward:
            # `if self._exit_leg_enclosed() and ff_exit_leg_hold(): self._exit_leg_hold()`)
            hs = {(k, u, side[(k, u)][0]) for (k, u) in side}
            if not s["events_dropped"] and encl != hs:
                for k, u, c in sorted(encl - hs, key=lambda t: (t[0], t[1])):
                    mis.append("sidecar enclosure trigger %s@%d at %s without a hold at HOLD 1" % (u, k, lc(c)))
                for k, u, c in sorted(hs - encl, key=lambda t: (t[0], t[1])):
                    mis.append("sidecar hold %s@%d at %s without an enclosure trigger" % (u, k, lc(c)))
            if int(cnt.get("enclosure_triggers", 0) or 0) != int(cnt.get("holds", 0) or 0):
                mis.append("sidecar counters enclosure_triggers %s != holds %s at HOLD 1"
                           % (cnt.get("enclosure_triggers"), cnt.get("holds")))
        elif side:
            mis.append("%d sidecar hold(s) at HOLD 0" % len(side))
        s["hold_mis"] = mis
        s["episodes"] = hold_episodes(d, held, ext)
        s["enc"] = {(k, u) for k, u, _c in encl}
        s["enc_wrapped"] = not s["base"]
        s["m6"] = m6(d)
        if self.m6_checked is None and s["m6"] is not None:
            theirs = sfx_m6(d)
            self.m6_checked = (tag, tup, s["m6"], theirs)
            if theirs != s["m6"]:
                self.stop("H7", "ANALYZER DEFECT: M6 replica %r != _sfx_analyze.sec_exposure %r on %s %s"
                          % (s["m6"], theirs, tag, C.label(tup)))
        s["m7"] = m7(d, burn, legs)
        s["m10"] = m10(d, burn)
        s["m11"] = m11(d, sc, burn, legs)
        s["m2align"] = mode2_alignment(d, sc) if self.mode(tag) == 2 else None
        s["sites"] = sites(d, sc)
        s["dead_revert"] = dead_reverts(d)
        s["vdead"] = victim_dead_events(d)
        s["relabel"] = relabelled_corpses(d, burn)
        s["switches_side"] = sc.get("switches")
        s["term240"] = C.terminal_step(d, min(RB_PREFIX_HORIZON, steps))
        s["resc"] = {cut: C.cut_outcomes(d, cut)["rescued"] for cut in (RB_PREFIX_HORIZON, steps)
                     if cut <= steps}
        return s

    def _pair(self, a, c, tup, inst, sarm, set_name):
        ctx = self.ctx
        da, dc = ctx.load(a, tup), ctx.load(c, tup)
        p = dict(arm=a, ctrl=c, tup=tup, inst=inst, sarm=sarm, set=set_name)
        p["div"] = ctx.first_div(c, a, tup)
        p["first_any"], p["any_keys"] = C.first_diff_detail(dc, da, keys=C.SERIES)
        p["other_keys"] = C.diff_keys(dc, da, ("tag", "wall_s", "params", "extra_params") + tuple(C.SERIES))
        p["fire240"] = C.first_diff(dc, da, ("fire_digests",), upto=RB_PREFIX_HORIZON)
        p["fire_first"] = C.first_diff(dc, da, ("fire_digests",))
        # H12 engagement site (computed first: it is also the cause a D-3 item carries)
        engaged = p["first_any"] is not None or bool(p["other_keys"])
        p["engaged"] = engaged
        p["site"] = None
        if engaged:
            lim = p["first_any"]
            st = [x for x in self.S[(a, tup)]["sites"] if lim is None or x[0] <= lim]
            p["site"] = st[0] if st else None
        lcl, lal = ctx.legs(c, tup), ctx.legs(a, tup)
        pairs, conly, aonly = C.match_legs(lcl, lal)
        p["matched"], p["conly"], p["aonly"] = pairs, conly, aonly
        div = p["div"]
        pre = [("control", x) for x in conly if div is None or x["s0"] < div]
        pre += [("arm", y) for y in aonly if div is None or y["s0"] < div]
        for side, x in pre:
            self.stop("H2", "ANALYZER DEFECT: %s vs %s %s: PRE-divergence %s leg without a match (first divergence %s): %s"
                      % (a, c, C.label(tup), side, div, C.leg_str(x)))
        p["pre_unmatched"] = pre
        longer, unfin, hbroke, conv, verdicts = [], [], [], [], collections.Counter()
        for x, y in pairs:
            v, kind = classify_pair(x, y)
            verdicts[v] += 1
            if v == "CONVERSION":
                conv.append((x, y))
            elif v in ("LONGER", "LONGER-UNFINISHED", "HORIZON-BROKE"):
                s1 = x["end"] if x["end"] is not None else nsteps(dc)
                fid = C.fire_identical(dc, da, x["s0"], s1)
                rec = dict(c=x, a=y, kind=kind, s1=s1, identical=fid, site=p["site"])
                if not fid:
                    rec["fire_first"] = p["fire_first"]
                    rec["detail"] = C.first_diff_detail(dc, da)
                    rec["crn"] = self._crn_cmp(sarm, inst, tup, x["ff"], x["victim"])
                if v == "LONGER":
                    longer.append(rec)
                else:
                    rec["fates"] = fates_str(dc, da, c, a, x)
                    (unfin if v == "LONGER-UNFINISHED" else hbroke).append(rec)
        p["longer"], p["unfinished"], p["hbroke"] = longer, unfin, hbroke
        p["conv"], p["verdicts"] = conv, verdicts
        ak = {C.leg_key(y): y for y in lal}
        # M3: the control's drops -> the arm's same carry
        m3 = []
        for dr in self.S[(c, tup)]["drops"]:
            lx = [x for x in lcl if x["ff"] == dr["ff"] and x["victim"] == dr["vid"]
                  and x["end"] == dr["step"] and x["cause"] == "drop"]
            if len(lx) != 1:
                self.stop("H3", "ANALYZER DEFECT: %s %s drop %s/%s@%d pairs with %d legs ending 'drop' there"
                          % (c, C.label(tup), dr["ff"], dr["vid"], dr["step"], len(lx)))
                continue
            y = ak.get(C.leg_key(lx[0]))
            m3.append(dict(drop=dr, leg=lx[0], arm_leg=y, outcome=leg_outcome(y),
                           post_div=div is not None and lx[0]["s0"] >= div))
        p["m3"] = m3
        # H5: the control's custody markings -> the arm's same carry
        ct = []
        for mk in self.S[(c, tup)]["custody"]:
            lx = [x for x in lcl if x["ff"] == mk["ff"] and x["victim"] == mk["victim"]
                  and x["s0"] < mk["step"] and (x["end"] is None or x["end"] >= mk["step"])]
            if len(lx) != 1:
                self.stop("H5", "ANALYZER DEFECT: %s %s custody marking %s/%s@%d pairs with %d carrying legs"
                          % (c, C.label(tup), mk["ff"], mk["victim"], mk["step"], len(lx)))
                continue
            y = ak.get(C.leg_key(lx[0]))
            ct.append(dict(mark=mk, leg=lx[0], arm_leg=y, outcome=leg_outcome(y)))
        p["custody_table"] = ct
        # H11 footprint (clSN vs clC)
        if a == "clSN" and c == "clC":
            p["footprint"] = self._footprint(dc, da, tup)
        return p

    def _footprint(self, dc, da, tup):
        marks = self.S[("clC", tup)]["custody"]
        why = []
        pk = sorted(k for k in set(dc.get("params") or {}) | set(da.get("params") or {})
                    if (dc.get("params") or {}).get(k, "<absent>") != (da.get("params") or {}).get(k, "<absent>"))
        if pk != [C.SERVED]:
            why.append("params differ in %s (expected exactly %s)" % (pk, C.SERVED))
        if not marks:
            dk = C.diff_keys(dc, da, ("tag", "wall_s", "params", "extra_params"))
            if dk:
                why.append("not value-identical without a clC custody marking: keys %s" % dk)
            sa, sb = self.ctx.sidecar("clC", tup), self.ctx.sidecar("clSN", tup)
            hk = [k for k in ("transition_log_sha256", "movement_reason_sha256") if sa.get(k) != sb.get(k)]
            if hk:
                why.append("sidecar %s differ" % hk)
            return dict(anchor=None, first=None, why=why)
        s0 = min(m["step"] for m in marks)
        f, keys = C.first_diff_detail(dc, da, keys=C.SERIES)
        if f != s0:
            why.append("first differing step %s [%s] != clC's first custody marking @%d" % (f, ", ".join(keys), s0))
        for k in C.EVENTS:
            ea = [e for e in dc.get(k) or [] if isinstance(e, dict) and e.get("step") is not None and e["step"] < s0]
            eb = [e for e in da.get(k) or [] if isinstance(e, dict) and e.get("step") is not None and e["step"] < s0]
            if ea != eb:
                why.append("event list %s differs before @%d" % (k, s0))
        return dict(anchor=s0, first=f, why=why)

    def _crn_cmp(self, sarm, inst, tup, ff, vid):
        """D-3: the same tuple/unit/victim in the CRN arms (clK<arm> vs clKC)."""
        ctx = self.ctx
        if inst == "crn":
            return "this comparison IS the CRN instrument"
        if sarm is None:
            return "no CRN pair (probe arm)"
        k = ctx.crn_of(sarm)
        kc = ctx.control_of(k) if k else None
        if not k or not kc:
            return "no CRN arm for %s" % sarm
        if not (ctx.has(k, tup) and ctx.has(kc, tup)):
            return "%s / %s not queued for %s" % (k, kc, C.label(tup))
        lk = [x for x in ctx.legs(kc, tup) if x["ff"] == ff and x["victim"] == vid]
        la = [x for x in ctx.legs(k, tup) if x["ff"] == ff and x["victim"] == vid]
        pairs, oc, oa = C.match_legs(lk, la)
        parts = []
        for x, y in pairs:
            v, kind = classify_pair(x, y)
            parts.append("%s %s | %s %s [%s %s]" % (kc, C.leg_str(x), k, C.leg_str(y), v, kind))
        parts += ["%s only: %s" % (kc, C.leg_str(x)) for x in oc]
        parts += ["%s only: %s" % (k, C.leg_str(y)) for y in oa]
        if parts:
            return "; ".join(parts)
        # the same victim carried by ANOTHER unit under the CRN fire (labelled; not a unit match)
        vk = ["%s %s" % (kc, C.leg_str(x)) for x in ctx.legs(kc, tup) if x["victim"] == vid]
        va = ["%s %s" % (k, C.leg_str(y)) for y in ctx.legs(k, tup) if y["victim"] == vid]
        return ("no leg of %s/%s in either CRN run; legs of %s by any unit: %s"
                % (ff, vid, vid, "; ".join(vk + va) or "none"))

    # ------------------------------------------------------------------ report --
    def hdr(self, title, *more):
        self.say("")
        self.say("=" * 96)
        self.say(title)
        for m in more:
            self.say("    " + m)
        self.say("=" * 96)

    def m1(self, tag, set_name):
        tl = self.ctx.tuples(tag, set_name)
        if not tl:
            return None
        r = dict(runs=len(tl), complete=tl == self.ctx.sets[set_name], legs=0, completed=0, m1a=0, m1b=0,
                 m1c=0, horizon=0, broken=collections.Counter(), excess=0, excess_max=0, reversals=0,
                 m1c_legs=[])
        for t in tl:
            for x in self.S[(tag, t)]["legs"]:
                r["legs"] += 1
                r["completed"] += x["completed"]
                r["m1a"] += x["m1a"]
                r["m1b"] += x["m1b"]
                r["m1c"] += x["m1c"]
                r["reversals"] += x["reversals"]
                if x["completed"]:
                    r["excess"] += x["excess"]
                    r["excess_max"] = max(r["excess_max"], x["excess"])
                elif x["cause"] == "horizon":
                    r["horizon"] += 1
                else:
                    r["broken"][x["cause"]] += 1
                if x["m1c"]:
                    r["m1c_legs"].append((t, x))
        return r

    def m1_line(self, set_name, tag, r):
        br = ", ".join("%s %d" % kv for kv in sorted(r["broken"].items())) or "none"
        return ("  %-4s %-6s %-5s runs %2d%s  legs %3d completed %3d | M1a %2d  M1b %2d | M1c %2d | broken %2d (%s) "
                "horizon %d | excess %d max %d | reversals %d"
                % (set_name, tag, self.inst(tag), r["runs"], "" if r["complete"] else " (INCOMPLETE)", r["legs"],
                   r["completed"], r["m1a"], r["m1b"], r["m1c"], sum(r["broken"].values()), br, r["horizon"],
                   r["excess"], r["excess_max"], r["reversals"]))

    def pair_list(self, a, c, sets=LEG_SETS):
        return [self.P[(a, c, t)] for s in sets for t in self.ctx.sets[s] if (a, c, t) in self.P]

    def _longer_report(self, p, a, c):
        """H2 lines for one pair's LONGER / LONGER-UNFINISHED / HORIZON-BROKE legs. -> count."""
        say = self.say
        info = "  [RB7: INFORMATION ONLY - not gated by G2 (G5 re-roll instrument, no CRN arm)]" if p["set"] == "RB7" else ""
        n = 0
        for rec in p["longer"]:
            n += 1
            x, y = rec["c"], rec["a"]
            if rec["identical"]:
                say("    LONGER on an IDENTICAL fire over [%d,%d] - %s: %s  %s: %s | %s: %s%s"
                    % (x["s0"], rec["s1"], "AUTOMATIC FAIL" if p["set"] != "RB7" else "not gated",
                       C.label(p["tup"]), c, C.leg_str(x), a, C.leg_str(y), info))
            else:
                fs, keys = rec["detail"]
                say("    LONGER on a CHANGED fire (D-3): %s  %s: %s | %s: %s%s"
                    % (C.label(p["tup"]), c, C.leg_str(x), a, C.leg_str(y), info))
                say("        fire first differs @%s; first differing step %s [%s]; cause (feature site that fired "
                    "first): %s; arm leg ends: %s" % (rec["fire_first"], fs, ", ".join(keys) or "-",
                                                      site_str(rec["site"]), y["cause"]))
                say("        CRN comparison: %s" % rec["crn"])
        for what, lst in (("LONGER-UNFINISHED (neither leg completed; the arm kept custody longer - not a longer "
                           "delivery, to the maintainer)", p["unfinished"]),
                          ("HORIZON-BROKE (the control still carrying at the horizon, the arm leg broke - to the "
                           "maintainer)", p["hbroke"])):
            for rec in lst:
                n += 1
                x, y = rec["c"], rec["a"]
                say("    %s: %s  %s: %s | %s: %s%s" % (what, C.label(p["tup"]), c, C.leg_str(x), a, C.leg_str(y), info))
                say("        %s" % rec["fates"])
                if rec["identical"]:
                    say("        fire identical over [%d,%d]; first differing feature site: %s"
                        % (x["s0"], rec["s1"], site_str(rec["site"])))
                else:
                    fs, keys = rec["detail"]
                    say("        fire first differs @%s; first differing step %s [%s]; cause: %s; CRN comparison: %s"
                        % (rec["fire_first"], fs, ", ".join(keys) or "-", site_str(rec["site"]), rec["crn"]))
        return n

    # ---------------------------------------------------------------------- H2 --
    def h2(self):
        say = self.say
        self.hdr("H2. EXIT LEGS - M1a (n > d_c+5, to the completion cell) / M1b (n > d+5, to the fixed exit) /",
                 "M1c STALLED-OR-BROKEN per exit_start (M1a-stalled, or broken, or horizon with elapsed > d+5).",
                 "D-7: M1c is the HOLD/SERVED gate count; M1a/M1b (completed legs only) are reported beside it.",
                 "excess = n - (d_c+1) over completed legs; reversals = steps back to the cell two rows earlier.")
        for set_name in LEG_SETS:
            for tag in self.tags:
                r = self.m1(tag, set_name)
                if r is not None:
                    say(self.m1_line(set_name, tag, r))
        for a, c, inst, sarm in self.pairs + [(a, c, self.inst(a), None) for a, c in self.probe]:
            plist = self.pair_list(a, c)
            if not plist:
                continue
            say("")
            say("  %s vs %s (%s)" % (a, c, inst))
            for set_name in LEG_SETS:
                ra, rc = self.m1(a, set_name), self.m1(c, set_name)
                if ra is None or rc is None:
                    continue
                say("    %-4s M1c %d -> %d   M1a %d -> %d   M1b %d -> %d   legs %d -> %d   broken %d -> %d   excess %d -> %d%s"
                    % (set_name, rc["m1c"], ra["m1c"], rc["m1a"], ra["m1a"], rc["m1b"], ra["m1b"], rc["legs"], ra["legs"],
                       sum(rc["broken"].values()), sum(ra["broken"].values()), rc["excess"], ra["excess"],
                       "" if (ra["complete"] and rc["complete"]) else "  (INCOMPLETE set)"))
            nm = sum(len(p["matched"]) for p in plist)
            nc = sum(len(p["matched"]) + len(p["conly"]) for p in plist)
            na = sum(len(p["matched"]) + len(p["aonly"]) for p in plist)
            pre_c = post_c = 0
            post = {"ctrl": [], "arm": []}
            for p in plist:
                div = p["div"]
                for x in [x for x, _y in p["matched"]] + p["conly"]:
                    if div is not None and x["s0"] >= div:
                        post_c += 1
                        post["ctrl"].append((p["tup"], x))
                    else:
                        pre_c += 1
                for y in [y for _x, y in p["matched"]] + p["aonly"]:
                    if div is not None and y["s0"] >= div:
                        post["arm"].append((p["tup"], y))
            ndiv = sum(1 for p in plist if p["div"] is not None)
            vc = collections.Counter()
            for p in plist:
                vc.update(p["verdicts"])
            say("    COVERAGE: matched %d of %d control legs / %d arm legs; control legs pre-divergence %d, post %d;"
                % (nm, nc, na, pre_c, post_c))
            say("      runs diverged (fire_digests or ff_steps) %d of %d; matched pairs: %s"
                % (ndiv, len(plist), ", ".join("%s %d" % kv for kv in sorted(vc.items())) or "none"))
            for side in ("ctrl", "arm"):
                lst = post[side]
                ex = [x["excess"] for _t, x in lst if x["completed"]]
                say("      post-divergence %-4s %-6s legs %3d  broken %2d  horizon %d  excess total %d max %d  M1c %d"
                    % (side, c if side == "ctrl" else a, len(lst),
                       sum(1 for _t, x in lst if not x["completed"] and x["cause"] != "horizon"),
                       sum(1 for _t, x in lst if x["cause"] == "horizon"), sum(ex), max(ex) if ex else 0,
                       sum(1 for _t, x in lst if x["m1c"])))
            for p in plist:
                if p["div"] is None:
                    continue
                for y in p["aonly"]:
                    say("      arm leg without a control counterpart %s: %s" % (C.label(p["tup"]), C.leg_str(y)))
            for p in plist:
                for x, y in p["conv"]:
                    say("    CONVERSION %s: %s -> %s (length %d, d %d)"
                        % (C.label(p["tup"]), C.leg_str(x), C.leg_str(y), y["n"], y["d"]))
            nl = 0
            for p in plist:
                nl += self._longer_report(p, a, c)
            if not nl:
                say("    LONGER / LONGER-UNFINISHED / HORIZON-BROKE: none (%d matched pairs)" % nm)
        g2 = {}
        for arm in self.ctx.GATE_ARMS:
            g2[arm] = self.g2(arm)
        return g2

    def g2(self, arm):
        """Design 9.4 G2 + D-7. Returns (verdict, notes) and prints the evaluation."""
        say, ctx = self.say, self.ctx
        say("")
        items, notes = [], []
        ctrl = ctx.control_of(arm)
        k = ctx.crn_of(arm)
        kc = ctx.control_of(k) if k else None
        if arm not in self.present and not k:
            return ("UNTESTED", ["stock arm not queued"])
        sw = self.sw.get(arm) or (self.sw.get(k) if k else {}) or {}
        is_mode = int(sw.get(C.MODE, 0) or 0) != 0
        rule = "MODE (N30 strictly lower)" if is_mode else "HOLD/SERVED (D-7: N30 not higher)"
        if arm == "clOA":
            rule = "D-4 mechanic-OFF screen (C13+U30 stock vetoes + none-longer; no N30 evidence)"
        say("  G2 %s - rule: %s; control %s%s" % (arm, rule, ctrl or "-", (", CRN %s vs %s" % (k, kc)) if k else ", no CRN arm"))
        sets = ("C13", "U30") if arm == "clOA" else G2_SETS
        n30 = {}
        for set_name in sets:
            vals = {}
            for inst, a_t, c_t in (("stock", arm, ctrl), ("crn", k, kc)):
                if not a_t or not c_t or a_t not in self.present or c_t not in self.present:
                    continue
                ra, rc = self.m1(a_t, set_name), self.m1(c_t, set_name)
                if ra is None or rc is None:
                    continue
                if not (ra["complete"] and rc["complete"]):
                    say("    %s %-5s INCOMPLETE - not tested" % (set_name, inst))
                    continue
                vals[inst] = (rc["m1c"], ra["m1c"], rc, ra, a_t, c_t)
            if not vals:
                continue
            hi = [i for i, v in vals.items() if v[1] > v[0]]
            txt = "  ".join("%s M1c %d -> %d (M1a %d -> %d, M1b %d -> %d)" % (i, v[0], v[1], v[2]["m1a"], v[3]["m1a"],
                                                                         v[2]["m1b"], v[3]["m1b"]) for i, v in vals.items())
            if len(hi) == 2:
                verdict = "FAIL"
            elif len(hi) == 1:
                verdict = "TO-MAINTAINER"
            else:
                verdict = "PASS"
            say("    %s not higher per instrument: %s  -> %s%s" % (set_name, txt, verdict,
                                                                "" if len(vals) == 2 else "  (one instrument measured)"))
            if hi:
                for i in hi:
                    rc, ra, a_t, c_t = vals[i][2], vals[i][3], vals[i][4], vals[i][5]
                    for t, x in rc["m1c_legs"]:
                        say("        %s M1c leg %s: %s" % (c_t, C.label(t), C.leg_str(x)))
                    for t, x in ra["m1c_legs"]:
                        say("        %s M1c leg %s: %s" % (a_t, C.label(t), C.leg_str(x)))
                if verdict == "TO-MAINTAINER":
                    ctx.to_maintainer(arm, "G2 %s M1c higher in ONE instrument only (%s): %s" % (set_name, hi[0], txt))
            items.append(verdict)
            notes.append("%s %s %s" % (set_name, "/".join("%s %d->%d" % (i, v[0], v[1]) for i, v in vals.items()), verdict))
            if set_name == "N30":
                n30 = vals
        set_verdicts = len(items)          # per-set M1c verdicts produced (review finding 6)
        # the N30 evidence
        evidence_tested = False
        if arm != "clOA":
            want_crn = k is not None
            if "stock" in n30 and (("crn" in n30) or not want_crn):
                evidence_tested = True
                pc = sum(v[0] for v in n30.values())
                pa = sum(v[1] for v in n30.values())
                pooled = "+".join(sorted(n30))
                if is_mode:
                    if pc == 0:
                        ev = "TO-MAINTAINER"
                        ctx.to_maintainer(arm, "G2 N30 control M1c (%s) is 0: the fall is NOT MEASURABLE OUT OF SAMPLE" % pooled)
                        say("    N30 EVIDENCE (%s pooled): control M1c 0 - NOT MEASURABLE OUT OF SAMPLE -> TO-MAINTAINER" % pooled)
                    else:
                        ev = "PASS" if pa < pc else "FAIL"
                        say("    N30 EVIDENCE (%s pooled): M1c %d -> %d, strictly lower required (hard) -> %s" % (pooled, pc, pa, ev))
                else:
                    ev = "PASS" if pa <= pc else "FAIL"
                    say("    N30 (%s pooled): M1c %d -> %d, not higher required (hard, D-7) -> %s" % (pooled, pc, pa, ev))
                items.append(ev)
                notes.append("N30 pooled %s %d->%d %s" % (pooled, pc, pa, ev))
            else:
                say("    N30 EVIDENCE: not tested at this stage (N30 %s)" % (
                    "stock and CRN not both complete" if want_crn else "stock not complete"))
                notes.append("N30 evidence not yet tested")
        # none longer - over the gated sets only (RB7 is the G5 re-roll instrument: no CRN arm
        # exists for it, so a D-3 item could never carry its CRN comparison; its LONGER legs
        # are printed in H2 as information only)
        auto, changed, unfin, hbroke, nm = 0, 0, 0, 0, 0
        for a_t, c_t in ((arm, ctrl), (k, kc)):
            if not a_t or not c_t:
                continue
            for p in self.pair_list(a_t, c_t, sets):
                nm += len(p["matched"])
                for rec in p["longer"]:
                    x, y = rec["c"], rec["a"]
                    if rec["identical"]:
                        auto += 1
                    else:
                        changed += 1
                        fs, keys = rec["detail"]
                        ctx.to_maintainer(arm, "D-3 LONGER on a changed fire %s %s vs %s: %s | %s; fire first differs @%s, "
                                               "first differing step %s [%s]; cause (feature site that fired first): %s; "
                                               "arm leg ends %s; CRN: %s"
                                          % (C.label(p["tup"]), a_t, c_t, C.leg_str(x), C.leg_str(y), rec["fire_first"],
                                             fs, ", ".join(keys) or "-", site_str(rec["site"]), y["cause"], rec["crn"]))
                for what, lst in (("LONGER-UNFINISHED (neither leg completed, the arm kept custody longer; "
                                   "not auto-failed - review finding 1)", p["unfinished"]),
                                  ("HORIZON-BROKE (control still carrying at the horizon, the arm leg broke)",
                                   p["hbroke"])):
                    for rec in lst:
                        x, y = rec["c"], rec["a"]
                        if lst is p["unfinished"]:
                            unfin += 1
                        else:
                            hbroke += 1
                        if rec["identical"]:
                            fire = "fire identical over [%d,%d]" % (x["s0"], rec["s1"])
                        else:
                            fs, keys = rec["detail"]
                            fire = ("fire first differs @%s, first differing step %s [%s]; CRN: %s"
                                    % (rec["fire_first"], fs, ", ".join(keys) or "-", rec["crn"]))
                        ctx.to_maintainer(arm, "%s %s %s vs %s: %s | %s; %s; %s; cause: %s"
                                          % (what, C.label(p["tup"]), a_t, c_t, C.leg_str(x), C.leg_str(y), rec["fates"],
                                             fire, site_str(rec["site"])))
        nl = "PASS"
        if auto:
            nl = "FAIL"
        elif changed or unfin or hbroke:
            nl = "TO-MAINTAINER"
        say("    NONE LONGER over %d matched pairs (%s, both instruments; RB7 not gated): control-completed LONGER on an "
            "identical fire %d (AUTOMATIC FAIL), on a changed fire %d (D-3, to the maintainer); LONGER-UNFINISHED %d and "
            "HORIZON-BROKE %d (to the maintainer) -> %s" % (nm, "+".join(sets), auto, changed, unfin, hbroke, nl))
        items.append(nl)
        notes.append("none-longer %s (identical %d, changed %d, both-unfinished %d, horizon-broke %d)"
                     % (nl, auto, changed, unfin, hbroke))
        v = merge(items)
        if not set_verdicts and v in ("PASS", "UNTESTED"):
            # review finding 6: no per-set M1c verdict at all (e.g. clOA with no complete set)
            v = "UNTESTED"
            notes.append("UNTESTED: no complete set measured")
        elif arm != "clOA" and not evidence_tested and v in ("PASS", "UNTESTED"):
            v = "UNTESTED"
            notes.append("UNTESTED until the N30 evidence is in")
        say("    => %s G2 %s" % (arm, v))
        return (v, notes)

    # ---------------------------------------------------------------------- H3 --
    def h3(self):
        say = self.say
        self.hdr("H3. M3 CARRIER DROPS (replacement_after_blocked of a unit exiting at the start of the step),",
                 "class A (carrier and victim dead that step) / B (stays on the drop cell, dies with the victim) /",
                 "C (moves off alive) / D (other); each control drop matched to the arm's same carry.")
        for tag in self.tags:
            for set_name in LEG_SETS:
                tl = self.ctx.tuples(tag, set_name)
                if not tl:
                    continue
                ds = [(t, dr) for t in tl for dr in self.S[(tag, t)]["drops"]]
                cls = collections.Counter(dr["cls"] for _t, dr in ds)
                enc = sum(len(self.S[(tag, t)]["enc"]) for t in tl)
                say("  %-4s %-6s drops %d (%s)   sidecar enclosure triggers %d"
                    % (set_name, tag, len(ds), ", ".join("%s %d" % kv for kv in sorted(cls.items())) or "-", enc))
                for t, dr in ds:
                    say("      %s %s %s @%d at %s  class %s  carrier dead %s  victim dead %s"
                        % (C.label(t), dr["ff"], dr["vid"], dr["step"], lc(dr["cell"]), dr["cls"], dr["ff_death"], dr["v_death"]))
                    say("          %s" % help_str(dr))
                for t in tl:
                    s = self.S[(tag, t)]
                    if not s["enc_wrapped"]:
                        continue
                    for dr in s["drops"]:
                        if (dr["step"], dr["ff"]) not in s["enc"]:
                            self.stop("H3", "%s %s drop %s@%d has no sidecar enclosure trigger at that step - a carrier "
                                            "drop through another site (design 3.1 premise)" % (tag, C.label(t), dr["ff"], dr["step"]))
        for a, c, inst, sarm in self.pairs:
            plist = self.pair_list(a, c)
            rows = [(p["tup"], m) for p in plist for m in p["m3"]]
            if not plist:
                continue
            oc = collections.Counter(m["outcome"].split("@")[0].split(" ")[0] for _t, m in rows)
            say("")
            say("  %s vs %s (%s): %d control drop(s) -> %s" % (a, c, inst, len(rows),
                                                            ", ".join("%s %d" % kv for kv in sorted(oc.items())) or "-"))
            for t, m in rows:
                dr = m["drop"]
                say("      %s %s %s drop @%d class %s | %s carry: %s%s"
                    % (C.label(t), dr["ff"], dr["vid"], dr["step"], dr["cls"], a, m["outcome"],
                       "  (pickup post-divergence)" if m["post_div"] else ""))

    # ---------------------------------------------------------------------- H4 --
    def h4(self):
        say = self.say
        self.hdr("H4. M-HOLD - held advances from ff_steps + unassigns + burn_intervals (+ firefight_log for an",
                 "extinguish later in the same step by a unit acting after the carrier), cross-checked with the sidecar",
                 "holds (HOLD 1: and its enclosure triggers == its holds); episodes, lengths, endings.",
                 "Every hold <= %d advances (else STOP). HOLD 0 arms: any held advance is a second-raise hold." % HOLD_MAX)
        for tag in self.tags:
            for set_name in LEG_SETS:
                tl = self.ctx.tuples(tag, set_name)
                if not tl:
                    continue
                eps = [(t, e) for t in tl for e in self.S[(tag, t)]["episodes"]]
                adv = sum(len(self.S[(tag, t)]["held"]) for t in tl)
                side = sum(len(self.S[(tag, t)]["holds_side"]) for t in tl)
                cnt = sum(int(self.S[(tag, t)]["counters"].get("holds", 0) or 0) for t in tl)
                endings = collections.Counter(e["ending"] + ("/" + e["cleared"] if e["cleared"] else "") for _t, e in eps)
                say("  %-4s %-6s HOLD %d  held advances (rows) %d  sidecar hold events %d (counter %d)  episodes %d  max %d  "
                    "endings %s" % (set_name, tag, int(self.hold(tag)), adv, side, cnt, len(eps),
                                    max([e["length"] for _t, e in eps] or [0]),
                                    ", ".join("%s %d" % kv for kv in sorted(endings.items())) or "-"))
                for t, e in eps:
                    say("      %s %s held %d-%d (%d) at %s -> %s%s"
                        % (C.label(t), e["ff"], e["start"], e["end"], e["length"], lc(e["pos"]), e["ending"],
                           (" (" + e["cleared"] + ")") if e["cleared"] else ""))
                    if e["length"] > HOLD_MAX:
                        self.stop("H4", "%s %s %s hold of %d advances > %d" % (tag, C.label(t), e["ff"], e["length"], HOLD_MAX))
                    if not self.hold(tag):
                        say("        (HOLD 0: a second-raise hold, reported)")
                for t in tl:
                    for m in self.S[(tag, t)]["hold_mis"]:
                        say("      CROSS-CHECK MISMATCH %s: %s" % (C.label(t), m))
                        self.stop("H4", "%s %s hold cross-check: %s" % (tag, C.label(t), m))
                    if int(self.S[(tag, t)]["counters"].get("holds", 0) or 0) != len(self.S[(tag, t)]["holds_side"]) \
                            and not self.S[(tag, t)]["events_dropped"]:
                        self.stop("H4", "%s %s sidecar holds counter %s != %d hold events" % (
                            tag, C.label(t), self.S[(tag, t)]["counters"].get("holds"), len(self.S[(tag, t)]["holds_side"])))

    # ---------------------------------------------------------------------- H5 --
    def h5(self):
        say = self.say
        self.hdr("H5. M4 CUSTODY MARKINGS - geographically_isolated escape entry at s for victim v with a unit exiting,",
                 "alive, on grid in ff_steps[s-2] and bound to v in ff_bind_steps[s-2], no other unassign and no",
                 "completion of v by it at s. M4a: with its isolated unassign; M4b: without. Co-marked victims apart.",
                 "The pre-wave census reproduction is `_cl_legs.py --selftest` (not re-run here).")
        for tag in self.tags:
            for set_name in LEG_SETS:
                tl = self.ctx.tuples(tag, set_name)
                if not tl:
                    continue
                mk = [(t, m) for t in tl for m in self.S[(tag, t)]["custody"]]
                co = [(t, m) for t in tl for m in self.S[(tag, t)]["comarked"]]
                if not mk and not self.served(tag) and tag not in ("clC", "clKC"):
                    continue
                say("  %-4s %-6s SERVED %d  custody markings %d (M4a %d, M4b %d)  co-marked %d"
                    % (set_name, tag, int(self.served(tag)), len(mk), sum(1 for _t, m in mk if m["kind"] == "M4a"),
                       sum(1 for _t, m in mk if m["kind"] == "M4b"), len(co)))
                for t, m in mk:
                    say("      %s %s @%d by %s (%s) streak %s" % (C.label(t), m["victim"], m["step"],
                                                                 ", ".join("%s %s" % u for u in m["units"]), m["kind"], m["streak"]))
                for t, m in co:
                    say("      co-marked %s %s @%d cause %s" % (C.label(t), m["victim"], m["step"], m["cause"]))
        tabs = [(a, c) for a, c, _i, _s in self.pairs if self.served(a)] + list(self.probe)
        for a, c in tabs:
            plist = self.pair_list(a, c)
            if not plist:
                continue
            say("")
            say("  MATCHED CUSTODY TABLE %s vs %s (every %s custody marking -> the same carry in %s):" % (a, c, c, a))
            n = 0
            for p in plist:
                for r in p["custody_table"]:
                    n += 1
                    mk = r["mark"]
                    say("      %s %s marked @%d (%s, carrier %s, pickup %d) | %s carry: %s"
                        % (C.label(p["tup"]), mk["victim"], mk["step"], mk["kind"], mk["ff"], r["leg"]["s0"], a, r["outcome"]))
            if not n:
                say("      none: %s has no custody marking on the queued tuples" % c)
            for set_name in G2_SETS + ("RB7",):
                tl = [t for t in self.ctx.tuples(a, set_name) if (a, c, t) in self.P]
                if not tl:
                    continue
                mc = sum(len(self.S[(c, t)]["custody"]) for t in tl)
                ma = sum(len(self.S[(a, t)]["custody"]) for t in tl)
                if mc == 0:
                    say("      %s: control M4 0 -> untested there (no opportunity)" % set_name)
                else:
                    say("      %s: M4 %d -> %d  %s" % (set_name, mc, ma, "removed" if ma == 0 else "NOT removed"))

    # ------------------------------------------------------------------- H7/H8 --
    def h7(self):
        say = self.say
        self.hdr("H7. M6 DRONE STEPS IN FIRE (interior-hazard definition, _sfx_analyze.sec_exposure): E1 searcher-only,",
                 "E2 all UAVs, the uav_actions burning bit with the role from uav_steps, every frame of every UAV.")
        if self.m6_checked is not None:
            tag, tup, mine, theirs = self.m6_checked
            say("  replication asserted on %s %s: this file %r, _sfx_analyze.sec_exposure %r -> %s"
                % (tag, C.label(tup), mine, theirs, "EQUAL" if mine == theirs else "DIFFERENT (STOP)"))
        for set_name in LEG_SETS:
            for tag in self.tags:
                tl = self.ctx.tuples(tag, set_name)
                if not tl:
                    continue
                b1 = n1 = b2 = n2 = 0
                miss = 0
                for t in tl:
                    v = self.S[(tag, t)]["m6"]
                    if v is None:
                        miss += 1
                        continue
                    b1, n1, b2, n2 = b1 + v[0], n1 + v[1], b2 + v[2], n2 + v[3]
                say("  %-4s %-6s %-5s E1 %5d / %6d = %6.3f%%   E2 %5d / %6d = %6.3f%%%s"
                    % (set_name, tag, self.inst(tag), b1, n1, 100.0 * b1 / max(1, n1), b2, n2, 100.0 * b2 / max(1, n2),
                       ("   (%d run(s) without uav_actions)" % miss) if miss else ""))

    def h8(self):
        say = self.say
        self.hdr("H8. M7 CARRIER EXPOSURE - IN FIRE at decision time (start row exiting+alive at c, c burning that step;",
                 "escaped / died); FIRE-ADJACENT at end of step over all carrying rows and over the replay window",
                 "(completed legs, s0+1..s1-1). End-of-step in fire of a live carrier: instrument assertion, must be 0.")
        for set_name in LEG_SETS:
            for tag in self.tags:
                tl = self.ctx.tuples(tag, set_name)
                if not tl:
                    continue
                agg = collections.Counter()
                for t in tl:
                    agg.update(self.S[(tag, t)]["m7"])
                    if self.S[(tag, t)]["m7"]["eos_in_fire"]:
                        self.stop("H8", "%s %s: %d end-of-step rows with a live carrier on a burning cell (must be 0)"
                                  % (tag, C.label(t), self.S[(tag, t)]["m7"]["eos_in_fire"]))
                say("  %-4s %-6s %-5s in fire %3d (escaped %3d, died %2d)   fire-adjacent all rows %3d, replay window %3d   "
                    "end-of-step in fire %d" % (set_name, tag, self.inst(tag), agg["in_fire_escaped"] + agg["in_fire_died"],
                                                agg["in_fire_escaped"], agg["in_fire_died"], agg["adj_all"], agg["adj_window"],
                                                agg["eos_in_fire"]))

    # ------------------------------------------------------------------- H9/H10 --
    def h9(self):
        say = self.say
        self.hdr("H9. M10 MODE-1 EDGE - completions whose cell burns at the completion step; units dead on their own",
                 "completion step; completions off the recorded exit cell (possible only at mode >= 1).")
        for set_name in LEG_SETS:
            for tag in self.tags:
                tl = self.ctx.tuples(tag, set_name)
                if not tl:
                    continue
                rows = {k: [(t, x) for t in tl for x in self.S[(tag, t)]["m10"][k]] for k in ("burning", "death_on", "off_exit")}
                say("  %-4s %-6s mode %d  burning completions %d  deaths on own completion step %d  off-exit completions %d"
                    % (set_name, tag, self.mode(tag), len(rows["burning"]), len(rows["death_on"]), len(rows["off_exit"])))
                for k in ("burning", "death_on"):
                    for t, x in rows[k]:
                        say("      %s %s %s %s @%d at %s" % (k, C.label(t), x[1], x[2], x[0], lc(x[3])))
                if self.mode(tag) == 0:
                    for t, x in rows["off_exit"]:
                        self.stop("H9", "%s %s mode 0 completion off the exit cell: %s %s @%d at %s (exit %s)"
                                  % (tag, C.label(t), x[1], x[2], x[0], lc(x[3]), lc(x[4])))

    def h10(self):
        say = self.say
        self.hdr("H10. M11 MODE-2 RESIDUAL - sidecar path / fallback steps, fallback legs and their fate vs the matched",
                 "control carry; ONE-SIDED invariant: every path-step destination is neither burning nor 4-adjacent",
                 "to a burning cell at that step (burn_intervals); event cell vs ff_steps rows; the rows' own carrying",
                 "steps (start row exiting, alive, on grid, off the boundary) each carry exactly one event (none only",
                 "with an unassign of the unit that step) and no event falls elsewhere. Any breach: STOP.")
        any_mode2 = False
        for tag in self.tags:
            if self.mode(tag) != 2:
                for set_name in LEG_SETS:
                    for t in self.ctx.tuples(tag, set_name):
                        m = self.S[(tag, t)]["m11"]
                        if m["path"] or m["fallback"] or m["other"]:
                            self.stop("H10", "%s %s: %d path / %d fallback / %d other exit_leg_step events at mode %d"
                                      % (tag, C.label(t), m["path"], m["fallback"], m["other"], self.mode(tag)))
                continue
            any_mode2 = True
            for set_name in LEG_SETS:
                tl = self.ctx.tuples(tag, set_name)
                if not tl:
                    continue
                agg = collections.Counter()
                fl = []
                for t in tl:
                    s = self.S[(tag, t)]
                    m = s["m11"]
                    agg["path"] += m["path"]
                    agg["fallback"] += m["fallback"]
                    agg["other"] += m["other"]
                    agg["c_path"] += int(s["counters"].get("path_steps", 0) or 0)
                    agg["c_fallback"] += int(s["counters"].get("fallback_steps", 0) or 0)
                    fl += [(t, x, ks) for x, ks in m["fallback_legs"]]
                    for b in m["breaches"]:
                        self.stop("H10", "%s %s ONE-SIDED INVARIANT BREACH: %s @%d %s -> %s: %s"
                                  % (tag, C.label(t), b[1], b[0], lc(b[2]), lc(b[3]), b[4]))
                    for r in m["rowmis"]:
                        self.stop("H10", "%s %s path event %s @%d %s -> %s disagrees with ff_steps (%s -> %s)"
                                  % (tag, C.label(t), r[1], r[0], lc(r[2]), lc(r[3]), lc(r[4]), lc(r[5])))
                    if m["other"]:
                        self.stop("H10", "%s %s: %d exit_leg_step events neither path nor fallback" % (tag, C.label(t), m["other"]))
                    if not s["events_dropped"] and (m["path"] != int(s["counters"].get("path_steps", 0) or 0)
                                                    or m["fallback"] != int(s["counters"].get("fallback_steps", 0) or 0)):
                        self.stop("H10", "%s %s sidecar counters path/fallback %s/%s != events %d/%d" % (
                            tag, C.label(t), s["counters"].get("path_steps"), s["counters"].get("fallback_steps"),
                            m["path"], m["fallback"]))
                    # review finding 3: the rows' own carrying steps vs the events (no vacuous pass)
                    al = s["m2align"]
                    agg["derived"] += al["derived"]
                    agg["excused"] += al["excused"]
                    if s["events_dropped"]:
                        continue            # an H11 breach already; the alignment cannot be read
                    for msg in al["problems"]:
                        self.stop("H10", "%s %s mode-2 rows/events alignment: %s" % (tag, C.label(t), msg))
                    agg["misaligned"] += len(al["problems"])
                say("  %-4s %-6s path steps %d  fallback steps %d (counters %d / %d)  fallback legs %d  their reversals %d"
                    % (set_name, tag, agg["path"], agg["fallback"], agg["c_path"], agg["c_fallback"], len(fl),
                       sum(x["reversals"] for _t, x, _k in fl)))
                say("        rows-derived carrying steps %d; exit_leg_step events %d; derived steps with no event and an "
                    "unassign of the unit that step %d; misaligned %d%s"
                    % (agg["derived"], agg["path"] + agg["fallback"], agg["excused"], agg["misaligned"],
                       " (STOP)" if agg["misaligned"] else ""))
                ctrl = self.ctx.control_of(tag)
                for t, x, ks in fl:
                    other = "no control run"
                    if ctrl and (tag, ctrl, t) in self.P:
                        p = self.P[(tag, ctrl, t)]
                        cm = [cx for cx, ay in p["matched"] if ay is x]
                        other = ("%s %s" % (ctrl, C.leg_str(cm[0]))) if cm else "unmatched in %s" % ctrl
                    say("      fallback leg %s %s (fallback steps %s; reversals %d) | %s"
                        % (C.label(t), C.leg_str(x), ",".join(str(k) for k in ks), x["reversals"], other))
        if not any_mode2:
            say("  no mode-2 arm queued at this stage")

    # --------------------------------------------------------------------- H11 --
    def h11(self):
        say = self.say
        self.hdr("H11. INVARIANTS (STOP on any breach): HOLD arms 0 carrier drops; SERVED arms M4 = 0; clSN footprint;",
                 "victim 'dead' never reverts; victim_dead events <= dead victims + attributed relabelled corpses (a",
                 "live status after step s on a cell burning at s: a casualty unassign's reset_victim_pending relabelled",
                 "a victim swept dead in the same check - pre-existing, to the maintainer; unattributed, or by an",
                 "exiting unit at HOLD 1: STOP); own switch non-zero in the sidecar; sidecar events not capped.")
        inv = collections.defaultdict(list)
        relabels = []
        for tag in self.tags:
            n = 0
            for set_name in LEG_SETS:
                for t in self.ctx.tuples(tag, set_name):
                    n += 1
                    s = self.S[(tag, t)]
                    if self.hold(tag) and s["drops"]:
                        inv[tag].append("%s %d carrier drop(s) at HOLD 1: %s" % (
                            C.label(t), len(s["drops"]), ", ".join("%s@%d" % (dr["ff"], dr["step"]) for dr in s["drops"])))
                    if self.served(tag) and s["custody"]:
                        inv[tag].append("%s %d custody marking(s) at SERVED 1" % (C.label(t), len(s["custody"])))
                    if s["dead_revert"]:
                        inv[tag].append("%s victim dead reverts: %s" % (C.label(t), s["dead_revert"]))
                    # review finding 2: a relabelled corpse (pre-existing model path) explains one
                    # extra victim_dead event; everything else about it is checked
                    ev, nd = s["vdead"]
                    explained = 0
                    for rl in s["relabel"]:
                        desc = ("%s %s shows %r after step %d on %s, burning at %d (first dead row @%s)"
                                % (C.label(t), rl["victim"], rl["status"], rl["step"], lc(rl["cell"]), rl["step"],
                                   rl["dead_at"]))
                        if not rl["units"]:
                            inv[tag].append("%s: UNEXPLAINED relabelled corpse - no firefighter_fire_casualty unassign "
                                            "naming it at that step" % desc)
                            continue
                        explained += 1
                        exiting = [ff for ff, ex in rl["units"] if ex]
                        if exiting and self.hold(tag):
                            inv[tag].append("%s: relabelled by the casualty unassign of EXITING %s at HOLD 1 (the D2 "
                                            "guard should have omitted reset_victim_pending)" % (desc, ", ".join(exiting)))
                            continue
                        relabels.append((tag, t, desc, rl["units"]))
                    if ev > nd + explained:
                        inv[tag].append("%s %d victim_dead events for %d dead victims + %d attributed relabelled "
                                        "corpse(s)" % (C.label(t), ev, nd, explained))
                    sw = s["switches_side"] or {}
                    for key, name in ((C.MODE, "mode"), (C.HOLD, "hold"), (C.SERVED, "served")):
                        if int(self.sw[tag].get(key, 0) or 0) != 0:
                            val = sw.get(name)
                            if val in (0, False, "ABSENT", None):
                                inv[tag].append("%s sidecar switch %s=%r in a %s arm" % (C.label(t), name, val, key))
                    if s["events_dropped"]:
                        inv[tag].append("%s sidecar dropped %d events (EVENT_CAP): event-based checks incomplete"
                                        % (C.label(t), s["events_dropped"]))
            say("  %-6s runs %3d  %s" % (tag, n, "all hold" if not inv[tag] else "%d BREACH(ES)" % len(inv[tag])))
            for b in inv[tag]:
                say("      BREACH %s" % b)
                self.stop("H11", "%s %s" % (tag, b))
        say("  RELABELLED CORPSES attributed to a casualty unassign of a unit NOT exiting at the start of the step (or")
        say("  exiting at HOLD 0) - the pre-existing path, each one extra victim_dead event: %d" % len(relabels))
        for tag, t, desc, units in relabels:
            who = ", ".join("%s (%s)" % (ff, "exiting" if ex else "approaching") for ff, ex in units)
            say("      %s %s by %s" % (tag, desc, who))
            self.ctx.to_maintainer(self.filed_under(tag), "H11 pre-existing relabelled corpse (reset_victim_pending of a "
                                                          "casualty unassign, not a switch effect): %s %s by %s"
                                   % (tag, desc, who))
        # footprint
        fp = [(t, self.P[("clSN", "clC", t)]["footprint"]) for s in LEG_SETS for t in self.ctx.sets[s]
              if ("clSN", "clC", t) in self.P]
        if fp:
            anch = [(t, f) for t, f in fp if f["anchor"] is not None]
            bad = [(t, f) for t, f in fp if f["why"]]
            say("  clSN FOOTPRINT vs clC: %d runs; %d without a clC custody marking (value-identical required), %d with one"
                % (len(fp), len(fp) - len(anch), len(anch)))
            for t, f in anch:
                say("      %s anchored @%d, first differing step %s" % (C.label(t), f["anchor"], f["first"]))
            for t, f in bad:
                say("      BREACH %s: %s" % (C.label(t), "; ".join(f["why"])))
                self.stop("H11", "clSN footprint %s: %s" % (C.label(t), "; ".join(f["why"])))
                inv["clSN"].append("footprint %s" % C.label(t))
            if not bad:
                say("      footprint holds on every run")
        for arm in self.ctx.GATE_ARMS:
            tags = [x for x in (arm, self.ctx.crn_of(arm)) if x and x in self.present]
            bad = [b for x in tags for b in inv.get(x, [])]
            self.gates[arm]["INV"] = ("FAIL" if bad else ("PASS" if tags else "UNTESTED"),
                                      ["%d breach(es)" % len(bad)] if bad else [])

    # --------------------------------------------------------------------- H12 --
    def run_sites(self, tag, tup):
        """One run's OWN feature-site counts (review finding 4): MODE = mode-2 path steps (sidecar
        counter) + off-exit completions (rows; possible only at mode >= 1), HOLD = holds (sidecar),
        SERVED = served_by_custody_only_not_geo (sidecar: custody alone made the victim served
        while it was not geo-reachable - a prevented isolation-streak increment)."""
        s = self.S[(tag, tup)]
        cnt = s["counters"]
        return {"MODE": int(cnt.get("path_steps", 0) or 0) + len(s["m10"]["off_exit"]),
                "HOLD": int(cnt.get("holds", 0) or 0),
                "SERVED": int(cnt.get("served_by_custody_only_not_geo", 0) or 0)}

    def feature_sites(self, tags):
        """{feature: own-site total} over every queued run of `tags`, for each feature switched
        on in them (FEATURES order), and the run count."""
        on = [f for f, key in FEATURES if any(int((self.sw.get(x) or {}).get(key, 0) or 0) != 0 for x in tags)]
        tot, runs = collections.OrderedDict((f, 0) for f in on), 0
        for x in tags:
            for t in self.ctx.tuples(x):
                if (x, t) not in self.S:
                    continue
                runs += 1
                rs = self.run_sites(x, t)
                for f in on:
                    tot[f] += rs[f]
        return tot, runs

    def h12(self):
        say = self.say
        self.hdr("H12. ENGAGEMENT - runs that differ from the control (first differing step over every per-step series,",
                 "or other keys only) and the feature site that fired first (at or before that step). NOT ENGAGED if none;",
                 "a SERVED arm not engaged is 'UNTRIGGERED IN PART 3' (D-9: its credit comes from the probe only).",
                 "Per arm, each switched-on feature's OWN site count over the stock arm + its CRN twin (MODE: path steps",
                 "+ off-exit completions; HOLD: holds; SERVED: served_by_custody_only_not_geo); 0 at stage 3 ->",
                 "'<FEATURE> UNTRIGGERED IN PART 3', combination arms included (D-9: never credited with it).")
        final = self.ctx.stage >= 3
        for arm in self.ctx.GATE_ARMS:
            tags = [x for x in (arm, self.ctx.crn_of(arm)) if x and x in self.present]
            fs, fruns = self.feature_sites(tags)
            site_notes, served_untrig = [], False
            if fs and fruns:
                say("  %s own feature sites (%s, %d run(s)): %s" % (arm, " + ".join(tags), fruns,
                                                                 ", ".join("%s %d" % kv for kv in fs.items())))
                for f, cnt in fs.items():
                    if cnt:
                        continue
                    lab = ("%s UNTRIGGERED IN PART 3" % f) if final else ("%s untriggered on the sets queued so far" % f)
                    site_notes.append(lab)
                    say("  => %s %s (0 own sites: %s)" % (arm, lab, SITE_DEF[f]))
                    served_untrig = served_untrig or f == "SERVED"
            eng, notes, n = 0, [], 0
            for a, c, inst, sarm in self.pairs:
                if sarm != arm:
                    continue
                plist = self.pair_list(a, c)
                n += len(plist)
                for p in plist:
                    if not p["engaged"]:
                        continue
                    eng += 1
                    site = p.get("site")
                    other = (("other keys %s" % p["other_keys"]) if p["first_any"] is None
                             else "%d other key(s) differ" % len(p["other_keys"]))
                    if site is None:
                        why = "NO FEATURE SITE fired at or before the first differing step"
                        self.stop("H12", "%s vs %s %s differs (first step %s [%s], %s) but %s - an unobserved switch path"
                                  % (a, c, C.label(p["tup"]), p["first_any"], ", ".join(p["any_keys"]), other, why))
                    else:
                        why = "site %s @%d" % (site[1], site[0])
                    say("  %-6s vs %-5s %-18s first differing step %-4s [%s] %s;  %s"
                        % (a, c, C.label(p["tup"]), p["first_any"], ", ".join(p["any_keys"]) or "-", other, why))
            arm_item = False
            if not n:
                self.gates[arm]["ENG"] = ("UNTESTED", ["no run of the arm and its control queued"] + site_notes)
            elif eng:
                self.gates[arm]["ENG"] = ("PASS", ["ENGAGED in %d of %d run(s)" % (eng, n)] + site_notes)
                say("  => %s ENGAGED in %d of %d run(s)" % (arm, eng, n))
            else:
                only_served = all((k == C.SERVED) for k in (self.sw.get(arm) or {}))
                if only_served and self.sw.get(arm):
                    label = ("NOT ENGAGED - UNTRIGGERED IN PART 3" if final
                             else "not engaged on the sets queued so far (untriggered)")
                    arm_item = final
                else:
                    label = "NOT ENGAGED" if final else "not engaged on the sets queued so far"
                self.gates[arm]["ENG"] = ("UNTESTED", ["%s (0 of %d runs differ from the control)" % (label, n)]
                                          + site_notes)
                say("  => %s %s (0 of %d runs differ)" % (arm, label, n))
                if final:
                    self.ctx.to_maintainer(arm, "%s: 0 of %d runs differ from the control (D-9: not demonstrated in Part 3)"
                                           % (label, n))
            if final and served_untrig and not arm_item:
                self.ctx.to_maintainer(arm, "SERVED UNTRIGGERED IN PART 3: 0 own sites (%s) over %d run(s) of %s - "
                                            "documented so that no round credits SERVED with what it did not do (D-9)"
                                       % (SITE_DEF["SERVED"], fruns, " + ".join(tags)))
        for a, c in self.probe:
            fs, fruns = self.feature_sites([a])
            say("  probe %s vs %s (D-9 evidence, not a Part 3 arm): own feature sites %s over %d run(s)"
                % (a, c, ", ".join("%s %d" % kv for kv in fs.items()) or "none switched on", fruns))

    # --------------------------------------------------------------------- CREDIT --
    def credit(self):
        say = self.say
        say("")
        say("  CREDIT (design 9.4: from outcomes only - M3 conversions / M-HOLD for HOLD, M4 removed + the matched")
        say("  custody table for SERVED; never from a count the code change forces). Each feature is credited only")
        say("  where its OWN site fired (review finding 4): HOLD from a converted carry whose arm leg contains a hold")
        say("  of that unit; SERVED from a custody marking removed in a run where served_by_custody_only_not_geo > 0.")
        final = self.ctx.stage >= 3
        for arm in self.ctx.GATE_ARMS:
            notes, demo, opp = [], False, False
            served_sites = None
            for a, c, inst, sarm in self.pairs:
                if sarm != arm:
                    continue
                plist = self.pair_list(a, c)
                if self.hold(a):
                    m3, conv, held_conv = 0, 0, 0
                    for p in plist:
                        side = self.S[(a, p["tup"])]["holds_side"]
                        for m in p["m3"]:
                            m3 += 1
                            y = m["arm_leg"]
                            if y is None or not y["completed"]:
                                continue
                            conv += 1
                            if any(u == y["ff"] and y["s0"] < k <= y["end"] for (k, u) in side):
                                held_conv += 1
                    eps = sum(len(self.S[(a, p["tup"])]["episodes"]) for p in plist)
                    opp = opp or bool(m3)
                    demo = demo or bool(held_conv)
                    notes.append("%s HOLD: control drops %d, converted %d (with a hold in the arm leg %d), hold "
                                 "episodes %d" % (inst, m3, conv, held_conv, eps))
                if self.served(a):
                    mc = ma = removed = removed_fired = sv = 0
                    for p in plist:
                        mct = len(self.S[(c, p["tup"])]["custody"])
                        mat = len(self.S[(a, p["tup"])]["custody"])
                        svt = self.run_sites(a, p["tup"])["SERVED"]
                        mc, ma, sv = mc + mct, ma + mat, sv + svt
                        if mct and not mat:
                            removed += 1
                            removed_fired += bool(svt)
                    served_sites = (served_sites or 0) + sv
                    opp = opp or mc > 0
                    demo = demo or bool(removed_fired)
                    notes.append("%s SERVED: control M4 %d -> arm %d%s; runs with every marking removed %d, of which "
                                 "SERVED's own site fired %d; SERVED own sites %d"
                                 % (inst, mc, ma, "" if mc else " (no opportunity)", removed, removed_fired, sv))
            if not notes:
                continue
            if served_sites == 0:
                notes.append(("SERVED UNTRIGGERED IN PART 3" if final else "SERVED untriggered so far")
                             + " - no M4 change is credited to SERVED")
            v = "PASS" if demo else "UNTESTED"
            if not demo:
                notes.append("not demonstrated in Part 3" if opp or self.ctx.stage >= 3 else "not demonstrated so far")
            self.gates[arm]["CREDIT"] = (v, notes)
            say("    %-5s %s  [%s]" % (arm, "demonstrated" if demo else "NOT demonstrated", "; ".join(notes)))

    # --------------------------------------------------------------------- H13 --
    def _rb_files(self, prefix):
        want = set()
        for tag in self.ctx.rb_tags():
            if tag[:-1] == prefix and tag[-1:] in C.RB_SHARDS:
                want.add("_rblatch_camp2_%s_D_%s.json" % (tag, C.RB_SHARDS[tag[-1:]][0]))
        return want

    def _glob_ok(self, prefix, expected):
        """The files _ffr_rbcompare.py's glob _rblatch_camp2_<prefix>*_D_<wind>.json will merge,
        from a NON-recursive listing (quarantine skipped by name first), must be exactly `expected`."""
        got = set()
        for n in sorted(os.listdir(C.OUT)):
            if n == C.QUAR:
                continue
            for wind in ("east", "south"):
                if fnmatch.fnmatchcase(n, "_rblatch_camp2_%s*_D_%s.json" % (prefix, wind)):
                    got.add(n)
        return got == set(expected), sorted(got - set(expected)), sorted(set(expected) - got)

    def _rbcompare(self, new, old):
        r = subprocess.run([sys.executable, "-B", RBCOMPARE, "--new", new, "--old", old], capture_output=True,
                           text=True, cwd=C.ROOT, timeout=600)
        text = (r.stdout or "") + (r.stderr or "")
        regr = []
        for line in text.splitlines():
            m = re.search(r"regression: D/(\w+) seed (\d+)\s+rescued (\d+) -> (\d+)", line)
            if m:
                regr.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
        latched = None
        m = re.search(r"\[(PASS|FAIL)\] no unit left latched as route_blocked at end of run", text)
        if m:
            latched = m.group(1)
        problems = rescued_line_problems(text, regr)
        if r.returncode != 0:
            problems.append("exit code %d" % r.returncode)
        if "SEED SET MISMATCH" in text:
            problems.append("SEED SET MISMATCH")
        if "no %s shards yet" % new in text:
            problems.append("no %s shards" % new)
        if latched is None:
            problems.append("no latched line")
        return dict(text=text, regr=regr, latched=latched, problems=problems)

    def _shard_evals(self, prefix):
        out = {}
        for tag in self.ctx.rb_tags():
            if tag[:-1] != prefix:
                continue
            wind = C.RB_SHARDS[tag[-1:]][0]
            for e in self.ctx.load_rb(tag).get("evals") or []:
                out[(wind, int(e["seed"]))] = e
        return out

    def h13(self):
        say = self.say
        self.hdr("H13. G5 ROUTE_BLOCKED GATE - _ffr_rbcompare.py (subprocess) --new clG<arm> --old ihrest / --old clGC;",
                 "regressions outside {east/707, south/101, south/202, south/404}: re-roll status from the arm's and",
                 "clC's STOCK 360-step runs (C13 or RB7): RE-ROLLED iff fire_digests first differ before clC's",
                 "terminal_step within steps 1-240; not re-rolled -> NEW FAIL; re-rolled -> pooled rescued over every",
                 "re-rolled rbgate seed (clG<arm> vs clGC shards), a pooled loss -> CRN pair required (maintainer).")
        ctx = self.ctx
        ctrl_files = self._rb_files(RB_CONTROL)
        ctrl_res = None
        if len(ctrl_files) == 4:
            ok, extra, miss = self._glob_ok(RB_CONTROL, ctrl_files)
            ok2, extra2, miss2 = self._glob_ok(RB_OLD, {"_rblatch_camp2_%s%s_D_%s.json" % (RB_OLD, s, w)
                                                       for s, (w, _x) in C.RB_SHARDS.items()})
            if not (ok and ok2):
                self.stop("H13", "rbgate glob collision: %s extra %s missing %s; %s extra %s missing %s"
                          % (RB_CONTROL, extra, miss, RB_OLD, extra2, miss2))
            else:
                ctrl_res = self._rbcompare(RB_CONTROL, RB_OLD)
                say("  %s vs %s: regressions %s; latched line %s%s" % (
                    RB_CONTROL, RB_OLD, ["%s/%d %d->%d" % r for r in ctrl_res["regr"]] or "none", ctrl_res["latched"],
                    ("; PROBLEMS %s" % ctrl_res["problems"]) if ctrl_res["problems"] else ""))
                if ctrl_res["problems"]:
                    self.stop("H13", "rbcompare %s vs %s: %s" % (RB_CONTROL, RB_OLD, ctrl_res["problems"]))
        else:
            say("  %s shards queued: %d of 4" % (RB_CONTROL, len(ctrl_files)))
        for arm in ctx.GATE_ARMS:
            self.gates[arm]["G5"] = self.g5(arm, ctrl_files, ctrl_res)

    def g5(self, arm, ctrl_files, ctrl_res):
        say, ctx = self.say, self.ctx
        say("")
        prefix = C.RB_OF.get(arm)
        if prefix is None:
            say("  %s: no rbgate arm (D-4 mechanic-OFF screen) - G5 not applicable" % arm)
            return ("UNTESTED", ["no rbgate arm (D-4 screen)"])
        files = self._rb_files(prefix)
        if len(files) != 4 or len(ctrl_files) != 4 or ctrl_res is None:
            say("  %s: %s shards queued %d of 4, %s %d of 4 - UNTESTED" % (arm, prefix, len(files), RB_CONTROL, len(ctrl_files)))
            return ("UNTESTED", ["rbgate shards not queued (%s %d/4, %s %d/4)" % (prefix, len(files), RB_CONTROL, len(ctrl_files))])
        ok, extra, miss = self._glob_ok(prefix, files)
        if not ok:
            self.stop("H13", "rbgate glob collision for %s: extra %s missing %s" % (prefix, extra, miss))
            return ("UNTESTED", ["glob collision (STOP)"])
        r_old = self._rbcompare(prefix, RB_OLD)
        r_ctl = self._rbcompare(prefix, RB_CONTROL)
        for nm, r in (("--old " + RB_OLD, r_old), ("--old " + RB_CONTROL, r_ctl)):
            say("  %s: _ffr_rbcompare.py --new %s %s -> regressions %s; latched line %s%s"
                % (arm, prefix, nm, ["%s/%d %d->%d" % x for x in r["regr"]] or "none", r["latched"],
                   ("; PROBLEMS %s" % r["problems"]) if r["problems"] else ""))
            if r["problems"]:
                self.stop("H13", "rbcompare --new %s %s: %s" % (prefix, nm, r["problems"]))
        if r_old["problems"] or r_ctl["problems"]:
            return ("UNTESTED", ["rbcompare problems (STOP)"])
        items, notes = [], []
        # re-roll status of every classifiable rbgate seed
        rer = collections.OrderedDict()
        for sfx in ("a", "b", "c", "s"):
            wind, seeds = C.RB_SHARDS[sfx]
            for sd in seeds.split(","):
                key = (wind, int(sd))
                t = (wind, "half", int(sd))
                if C.set_of(t, {k: ctx.sets[k] for k in ("C13", "RB7")}) is None:
                    rer[key] = None
                    continue
                p = self.P.get((arm, "clC", t))
                if p is None:
                    rer[key] = None
                    continue
                cs = self.S[("clC", t)]
                term = cs["term240"] if cs["term240"] is not None else RB_PREFIX_HORIZON
                rer[key] = dict(rerolled=p["fire240"] is not None and p["fire240"] < term, div=p["fire240"],
                                term=cs["term240"], resc_c=cs["resc"], resc_a=self.S[(arm, t)]["resc"], tup=t)
        rolled = [k for k, v in rer.items() if v and v["rerolled"]]
        say("    re-roll status (stock %s vs clC, fire_digests steps 1-%d before clC's terminal_step):" % (arm, RB_PREFIX_HORIZON))
        for k, v in rer.items():
            if v is None:
                say("      %s/%-4d no stock harness pair queued%s" % (k[0], k[1], " (known-set seed)" if k in RB_KNOWN else ""))
            else:
                say("      %s/%-4d clC terminal %-4s first fire divergence %-4s -> %s" % (
                    k[0], k[1], v["term"], v["div"], "RE-ROLLED" if v["rerolled"] else "same fire until decided"))
        regr = [(w, s) for w, s, _a, _b in r_old["regr"]]
        new = sorted(k for k in regr if k not in RB_KNOWN)
        say("    regressions vs %s: %s; outside the known four: %s" % (RB_OLD, sorted(regr) or "none", new or "NONE"))
        for k in sorted(regr):
            v = rer.get(k)
            if not v:
                say("      %s/%d no stock harness pair: no 240/360 outcome to report" % k)
                continue
            ra, rc = v["resc_a"], v["resc_c"]
            last = max(rc)
            delay = (last != RB_PREFIX_HORIZON and ra.get(last, 0) >= rc.get(last, 0)
                     and ra.get(RB_PREFIX_HORIZON, 0) < rc.get(RB_PREFIX_HORIZON, 0))
            say("      %s/%d harness rescued clC -> %s: @%d %s -> %s%s%s"
                % (k[0], k[1], arm, RB_PREFIX_HORIZON, rc.get(RB_PREFIX_HORIZON), ra.get(RB_PREFIX_HORIZON),
                   (", @%d %s -> %s" % (last, rc.get(last), ra.get(last))) if last != RB_PREFIX_HORIZON else "",
                   "  (delay: the loss vanishes at %d; never turns a FAIL into a PASS)" % last if delay else ""))
        hinge = []
        for k in new:
            v = rer.get(k)
            if v is None:
                items.append("FAIL")
                notes.append("%s/%d regression, no harness pair - cannot classify" % k)
                say("    NEW FAILURE %s/%d: no stock harness pair - cannot classify" % k)
            elif not v["rerolled"]:
                items.append("FAIL")
                notes.append("%s/%d NOT re-rolled: NEW FAIL" % k)
                say("    NEW FAILURE %s/%d: NOT re-rolled - the same fire, a worse outcome" % k)
            else:
                hinge.append(k)
                say("    %s/%d: RE-ROLLED - judged on the pooled re-rolled set" % k)
        ga, gc = self._shard_evals(prefix), self._shard_evals(RB_CONTROL)
        pa = sum(int(ga[k].get("rescued") or 0) for k in rolled if k in ga)
        pc = sum(int(gc[k].get("rescued") or 0) for k in rolled if k in gc)
        say("    pooled rescued over the %d re-rolled seeds: %s %d -> %s %d (%+d)" % (len(rolled), RB_CONTROL, pc, prefix, pa, pa - pc))
        if hinge and pa < pc:
            items.append("TO-MAINTAINER")
            notes.append("re-rolled regression(s) %s with a pooled loss %d -> %d: CRN pair required" % (hinge, pc, pa))
            ctx.to_maintainer(arm, "G5 re-rolled regression(s) %s and the pooled re-rolled set loses rescues (%d -> %d): "
                                   "the verdict hinges on them - CRN pair required" % (hinge, pc, pa))
            say("    CRN PAIR REQUIRED for %s: the pooled re-rolled set loses rescues" % hinge)
        elif hinge:
            notes.append("re-rolled regression(s) %s offset in the pooled set (%d -> %d)" % (hinge, pc, pa))
        # the latched line, against the control's
        if r_old["latched"] == "FAIL":
            if ctrl_res["latched"] == "FAIL":
                items.append("TO-MAINTAINER")
                notes.append("latched line FAIL (the control's too)")
                ctx.to_maintainer(arm, "G5 latched line FAIL in both %s and %s" % (prefix, RB_CONTROL))
            else:
                items.append("FAIL")
                notes.append("unit left latched as route_blocked at end (the control has none)")
        say("    latched line: %s %s, %s %s" % (prefix, r_old["latched"], RB_CONTROL, ctrl_res["latched"]))
        say("    vs %s (the fix's own delta, reported): regressions %s"
            % (RB_CONTROL, ["%s/%d %d->%d" % x for x in r_ctl["regr"]] or "none"))
        v = merge(items + ["PASS"])
        notes.insert(0, "regressions outside the known four: %s" % (["%s/%d" % k for k in new] or "none"))
        say("    => %s G5 %s" % (arm, v))
        return (v, notes)


def sections(ctx):
    """The _cl_analyze.py hook (see its HOOK CONTRACT)."""
    A = Analysis(ctx)
    A.collect()
    g2 = A.h2()
    for arm, v in g2.items():
        A.gates[arm]["G2"] = v
    A.h3()
    A.h4()
    A.h5()
    A.h7()
    A.h8()
    A.h9()
    A.h10()
    A.h11()
    A.h12()
    A.credit()
    A.h13()
    return {"gates": {arm: dict(g) for arm, g in A.gates.items()}}


# =============================================================================================
# THE PRE-WAVE SELF-TEST (CLI)
# =============================================================================================
def _read_run(path):
    """-> (dict | None if it does not mention geographically_isolated, error | None)."""
    with open(C._guard(path), "rb") as f:
        raw = f.read()
    try:
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            text = raw.decode("utf-16")
            if ISO not in text:
                return None, None
            return json.loads(text), None
        if ISO.encode("ascii") not in raw:
            return None, None
        return json.loads(raw.decode("utf-8-sig")), None
    except ValueError as exc:
        return None, "%s: %s" % (os.path.basename(path), exc)


def census(out=print):
    """Spec H5 pre-wave reproduction over the recorded tags. Returns (ok, lines)."""
    names = []
    for n in sorted(os.listdir(C.OUT)):
        if n == C.QUAR:            # quarantine: skipped by name before anything else
            continue
        m = CENSUS_RE.match(n)
        if not m or n.startswith(CENSUS_SKIP_PREFIXES) or ".xstrace." in n:
            continue
        names.append((n, m))
    recs, errors = [], []
    geo_files = nobind_files = 0
    for n, m in names:
        d, err = _read_run(os.path.join(C.OUT, n))
        if err:
            errors.append(err)
            continue
        if d is None:
            continue
        if not any(e.get("cause") == ISO for e in d.get("unreachable_escape_log") or []):
            continue
        geo_files += 1
        res = custody_markings(d)
        if res is None:
            nobind_files += 1
            continue
        marks, comarked, _sk = res
        for mk in marks:
            recs.append(dict(tag=m.group(1), wind=m.group(2), roles=m.group(3), seed=int(m.group(4)),
                             comarked=len([c for c in comarked if c["step"] == mk["step"]]), **mk))
        del d
    groups = collections.OrderedDict()
    for r in recs:
        groups.setdefault((r["wind"], r["roles"], r["seed"], r["victim"], r["step"]), []).append(r)
    m4b = sum(1 for r in recs if r["kind"] == "M4b")
    case = any((r["tag"], r["wind"], r["roles"], r["seed"], r["victim"], r["step"], r["ff"]) == CENSUS_CASE for r in recs)
    out("H5 CENSUS (non-recursive outputs/_ffr_*.json; _ffr_xs*, _ffr_cl* and .xstrace. excluded; quarantine skipped)")
    out("  files listed %d; files with a geographically_isolated escape entry %d (%d without ff_bind_steps, not counted);"
        % (len(names), geo_files, nobind_files))
    out("  unreadable %d%s" % (len(errors), (": " + "; ".join(errors)) if errors else ""))
    out("  custody markings (files with ff_bind_steps) %d [expect %d]; distinct (wind, roles, seed, victim, step) %d "
        "[expect %d]; M4b %d [expect %d]" % (len(recs), CENSUS_RECORDS, len(groups), CENSUS_DISTINCT, m4b, CENSUS_M4B))
    for k, g in groups.items():
        units = sorted({r["ff"] for r in g})
        out("    %s/%s/%d %s @%d  records %d  carrier %s  kinds %s  co-marked %d  tags %s"
            % (k[0], k[1], k[2], k[3], k[4], len(g), ",".join(units), sorted({r["kind"] for r in g}),
               max(r["comarked"] for r in g), " ".join(sorted(r["tag"] for r in g))))
    out("  %s east/def/101 victim_0 @177 by ff_unit_1 present: %s" % (CENSUS_CASE[0], yn(case)))
    ok = (len(recs) == CENSUS_RECORDS and len(groups) == CENSUS_DISTINCT and m4b == CENSUS_M4B and case
          and not errors)
    out("  CENSUS %s" % ("REPRODUCED" if ok else "MISMATCH"))
    return ok


def uhd_checks(out=print):
    """M1b / M7 / M3 / M6 / detector checks on the recorded uhD U30 runs."""
    ok = True
    u30 = C.frozen_u30()
    completed = m1b = m1a = nlegs = win = 0
    drops_all, custody_all, held_all, eos, vdead_eq, relab = [], 0, 0, 0, 0, 0
    m10n = collections.Counter()
    first = None
    for t in u30:
        d = C.load_ref("uhD", t)
        legs = C.legs(d)
        burn = C.Burn(d)
        ext = ff_extinguishes(d)
        nlegs += len(legs)
        for x in legs:
            if x["completed"]:
                completed += 1
                m1b += x["m1b"]
                m1a += x["m1a"]
        mm = m7(d, burn, legs)
        win += mm["adj_window"]
        eos += mm["eos_in_fire"]
        drops_all += [(t, dr) for dr in drops(d)]
        cm = custody_markings(d)
        custody_all += len(cm[0]) if cm else 0
        held_all += len(held_advances(d, burn, ext))
        ev, nd = victim_dead_events(d)
        vdead_eq += ev == nd
        rl = relabelled_corpses(d, burn)
        relab += len(rl)
        explained = sum(1 for r in rl if r["units"])
        if ev > nd + explained or dead_reverts(d) or explained != len(rl):
            ok = False
            out("  INVARIANT BREACH on recorded uhD %s: victim_dead %d / dead %d + relabelled %s, reverts %s"
                % (C.label(t), ev, nd, rl, dead_reverts(d)))
        r10 = m10(d, burn)
        for k in r10:
            m10n[k] += len(r10[k])
        if first is None and t == UHD_DROP[0]:
            first = d
    out("uhD U30 (recorded, 30 runs)")
    c1 = completed == UHD_COMPLETED and m1b == UHD_M1B
    out("  H2 legs %d, completed %d, M1b %d, M1a %d  [expect M1b %d of %d completed] %s"
        % (nlegs, completed, m1b, m1a, UHD_M1B, UHD_COMPLETED, "OK" if c1 else "MISMATCH"))
    c2 = win == UHD_M7_WINDOW
    out("  H8 M7 fire-adjacent over the replay window %d [expect %d] %s; end-of-step in fire %d [must be 0]"
        % (win, UHD_M7_WINDOW, "OK" if c2 else "MISMATCH", eos))
    c3 = False
    for t, dr in drops_all:
        hit = (t, dr["ff"], dr["vid"], dr["step"], dr["cls"]) == UHD_DROP
        c3 = c3 or hit
        out("  H3 drop %s %s %s @%d at %s class %s  carrier dead %s  victim dead %s%s"
            % (C.label(t), dr["ff"], dr["vid"], dr["step"], lc(dr["cell"]), dr["cls"], dr["ff_death"], dr["v_death"],
               "  <- expected" if hit else ""))
        out("      %s" % help_str(dr))
    out("  H3 %s drop @148 class C listed: %s" % (C.label(UHD_DROP[0]), "OK" if c3 else "MISSING"))
    out("  H5 custody markings %d (the ungated record has none); H4 rows-derived held advances at HOLD 0 %d [expect 0]"
        % (custody_all, held_all))
    out("  H9 M10 burning completions %d, deaths on own completion step %d, off-exit completions %d [mode 0: expect 0]"
        % (m10n["burning"], m10n["death_on"], m10n["off_exit"]))
    out("  H11 victim_dead events == dead victims in %d of 30 runs (invariant: <= dead + attributed relabelled "
        "corpses); relabelled corpses %d" % (vdead_eq, relab))
    c4 = held_all == 0 and eos == 0 and m10n["off_exit"] == 0
    # M6 replication on one recorded run
    mine, theirs = m6(first), sfx_m6(first)
    c5 = mine == theirs
    out("  H7 M6 on uhD %s: this file %r, _sfx_analyze.sec_exposure %r -> %s"
        % (C.label(UHD_DROP[0]), mine, theirs, "EQUAL" if c5 else "DIFFERENT"))
    # the H10 one-sided invariant on constructed events (a burning cell must breach, a clean one not)
    burn = C.Burn(first)
    k_hot, hot = None, None
    for key in sorted(first["burn_intervals"]):
        a, _b = first["burn_intervals"][key][0]
        k_hot, hot = int(a), tuple(int(v) for v in key.split(","))
        break
    clean = next(((x, y) for x in range(C.GRID) for y in range(C.GRID)
                  if path_breach(burn, (x, y), k_hot) is None), None)
    b_hot, b_clean = path_breach(burn, hot, k_hot), path_breach(burn, clean, k_hot)
    c6 = b_hot is not None and b_clean is None and clean is not None
    out("  H10 one-sided check on constructed path steps @%d: burning %s -> %r; clean %s -> %r  %s"
        % (k_hot, lc(hot), b_hot, lc(clean), b_clean, "OK" if c6 else "MISMATCH"))
    return ok and c1 and c2 and c3 and c4 and c5 and c6


def rb_parse_check(out=print):
    """The G5 parser on the recorded ugGD vs ihrest shards (spec H1 e: the control's regression set is
    ugGD's {east/707, south/101, south/404}), including the rescued-line consistency (finding 8)."""
    r = subprocess.run([sys.executable, "-B", RBCOMPARE, "--new", "ugGD", "--old", RB_OLD], capture_output=True,
                       text=True, cwd=C.ROOT, timeout=600)
    full = [(m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))) for m in re.finditer(
        r"regression: D/(\w+) seed (\d+)\s+rescued (\d+) -> (\d+)", r.stdout or "")]
    regr = sorted((w, s) for w, s, _a, _b in full)
    lat = re.search(r"\[(PASS|FAIL)\] no unit left latched", r.stdout or "")
    resc = RESCUED_LINE_RE.search(r.stdout or "")
    probs = rescued_line_problems(r.stdout or "", full)
    ok = (r.returncode == 0 and regr == [("east", 707), ("south", 101), ("south", 404)] and lat is not None
          and not probs and resc is not None and resc.group(1) == "FAIL")
    out("H13 parser on recorded ugGD vs ihrest: regressions %s, rescued line %s (consistency: %s), latched %s -> %s"
        % (regr, resc.group(1) if resc else None, "; ".join(probs) or "OK", lat.group(1) if lat else None,
           "OK" if ok else "MISMATCH"))
    return ok


RELABEL_RECORD = ("dimfreshfix", "ihofffresh", "ihrest6fresh")    # _ffr_<tag>_south_half_606.json
RELABEL_EXPECT = [(129, "victim_3", "confirmed", (2, 0), [("ff_unit_1", False)], 130)]


def _load_named(name):
    """One NAMED recorded run in outputs/ (UTF-8 or UTF-16 with a BOM)."""
    path = C._guard(os.path.join(C.OUT, name))
    if not os.path.isfile(path):
        C.refuse("missing recorded file %s" % path)
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    return json.loads(text)


def relabel_check(out=print):
    """Finding 2 on the record: the three recorded south/half/606 runs with 2 victim_dead events for one
    dead victim are each explained by exactly one relabelled corpse (victim_3 @129, the approaching
    ff_unit_1's casualty unassign)."""
    ok = True
    for tag in RELABEL_RECORD:
        d = _load_named("_ffr_%s_south_half_606.json" % tag)
        rl = relabelled_corpses(d, C.Burn(d))
        got = [(r["step"], r["victim"], r["status"], r["cell"], r["units"], r["dead_at"]) for r in rl]
        ev, nd = victim_dead_events(d)
        good = got == RELABEL_EXPECT and ev == 2 and nd == 1 and ev <= nd + sum(1 for r in rl if r["units"])
        ok = ok and good
        out("H11 relabelled corpse on recorded %s south/half/606: %s; victim_dead %d, dead victims %d -> %s"
            % (tag, got, ev, nd, "OK (explained, pre-existing)" if good else "MISMATCH"))
    return ok


def constructed_checks(out=print):
    """Constructed inputs for the review-round rules (findings 1, 3, 5, 8)."""
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        out("  %-62s %r %s" % (name, got, "OK" if good else "MISMATCH (want %r)" % (want,)))

    out("CONSTRUCTED CHECKS")

    def leg(completed, cause, n):
        return dict(completed=completed, cause=cause, n=n)

    check("classify: drop n=97 vs died_in_custody n=99", classify_pair(leg(False, "drop", 97), leg(False, "died_in_custody", 99))[0],
          "LONGER-UNFINISHED")
    check("classify: completed n=10 vs completed n=12", classify_pair(leg(True, "completed", 10), leg(True, "completed", 12))[0],
          "LONGER")
    check("classify: completed n=10 vs drop n=5", classify_pair(leg(True, "completed", 10), leg(False, "drop", 5))[0], "LONGER")
    check("classify: horizon n=50 vs drop n=20", classify_pair(leg(False, "horizon", 50), leg(False, "drop", 20))[0],
          "HORIZON-BROKE")
    check("classify: drop n=20 vs completed n=30", classify_pair(leg(False, "drop", 20), leg(True, "completed", 30))[0],
          "CONVERSION")
    check("classify: died_in_custody n=99 vs drop n=97",
          classify_pair(leg(False, "died_in_custody", 99), leg(False, "drop", 97))[0], "SHORTER")
    # finding 5: extinguish order and the clear-write exclusion
    fl = {"firefight_log": [
        {"step": 5, "ff": "ff_unit_1", "action": "extinguish", "wrote": True, "target": [1, 1]},
        {"step": 5, "ff": "ff_unit_1", "action": "clear", "wrote": True, "target": [3, 3]},
        {"step": 6, "ff": "ff_unit_0", "action": "extinguish", "wrote": True, "target": [2, 2]},
        {"step": 6, "ff": "ff_unit_0", "action": "extinguish", "wrote": False, "target": [4, 4]}]}
    ext = ff_extinguishes(fl)
    check("ff_extinguishes keeps wrote extinguishes only", sorted(ext), [(5, (1, 1)), (6, (2, 2))])
    burn = C.Burn({"burn_intervals": {"7,7": [[5, 6]]}})
    order = {"ff_unit_0": 0, "ff_unit_1": 1}
    check("enclosing: put out later in the step by a unit acting after", enclosing(burn, ext, order, "ff_unit_0", (1, 1), 5), True)
    check("enclosing: put out earlier in the step by a unit acting before",
          enclosing(burn, ext, order, "ff_unit_1", (2, 2), 6), False)
    check("enclosing: burning in the post-step observation", enclosing(burn, ext, order, "ff_unit_1", (7, 7), 5), True)
    check("enclosing: not burning, no write", enclosing(burn, ext, order, "ff_unit_0", (7, 7), 6), False)
    # finding 3: mode-2 rows/events alignment
    rows = [[["ff_unit_0", [10, 10], "assigned", True, True, False]],
            [["ff_unit_0", [11, 10], "assigned", True, True, False]],
            [["ff_unit_0", [12, 10], "assigned", True, True, False]],
            [["ff_unit_0", [12, 10], "assigned", True, False, False]]]
    d = {"ff_steps": rows, "unassigns": []}
    evs = [[2, "ff_unit_0", [10, 10], [11, 10], "path"], [3, "ff_unit_0", [11, 10], [12, 10], "path"],
           [4, "ff_unit_0", [12, 10], [12, 10], "fallback"]]
    good = mode2_alignment(d, {"events": {"exit_leg_steps": evs}})
    check("mode2 alignment: one event per derived step", (good["derived"], good["problems"]), (3, []))
    check("mode2 alignment: an event missing -> problem",
          len(mode2_alignment(d, {"events": {"exit_leg_steps": evs[:2]}})["problems"]), 1)
    d2 = {"ff_steps": rows, "unassigns": [{"step": 4, "ff": "ff_unit_0", "vid": "victim_1", "reason": "x"}]}
    al = mode2_alignment(d2, {"events": {"exit_leg_steps": evs[:2]}})
    check("mode2 alignment: missing event excused by an unassign", (al["excused"], al["problems"]), (1, []))
    check("mode2 alignment: no events at all -> 3 problems", len(mode2_alignment(d, {"events": {}})["problems"]), 3)
    check("mode2 alignment: an extra event elsewhere -> problem",
          len(mode2_alignment(d, {"events": {"exit_leg_steps": evs + [[5, "ff_unit_0", [12, 10], [12, 11], "path"]]}})
              ["problems"]), 1)
    check("mode2 alignment: wrong from-cell -> problem",
          len(mode2_alignment(d, {"events": {"exit_leg_steps": [evs[0], [3, "ff_unit_0", [9, 9], [12, 10], "path"],
                                                                evs[2]]}})["problems"]), 1)
    rows_b = [[["ff_unit_0", [48, 10], "assigned", True, True, False]],
              [["ff_unit_0", [49, 10], "assigned", True, True, False]],
              [["ff_unit_0", [49, 10], "available", False, False, False]]]
    check("mode2 carry steps: a boundary start cell completes (no step)",
          mode2_carry_steps({"ff_steps": rows_b}), {(2, "ff_unit_0"): (48, 10)})
    # finding 8: the rescued line against the parsed regressions
    fail, pas = "  [FAIL] rescued does not decrease on any seed vs ihrest", "  [PASS] rescued does not decrease on any seed vs x"
    check("rescued line FAIL + no regression -> problem", len(rescued_line_problems(fail, [])), 1)
    check("rescued line FAIL + a regression -> ok", rescued_line_problems(fail, [("east", 1, 2, 1)]), [])
    check("rescued line PASS + a regression -> problem", len(rescued_line_problems(pas, [("east", 1, 2, 1)])), 1)
    check("rescued line PASS + none -> ok", rescued_line_problems(pas, []), [])
    check("no rescued line -> problem", len(rescued_line_problems("nothing", [])), 1)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description="carrying-leg analyzer, leg-level sections (hook) + pre-wave self-test")
    ap.add_argument("--selftest", action="store_true", help="the pre-wave record reproduction (prints; writes nothing)")
    a = ap.parse_args(argv)
    if not a.selftest:
        ap.error("this module is the _cl_analyze.py hook; run it directly only with --selftest")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(newline="\n")
    ok1 = census()
    print("")
    ok2 = uhd_checks()
    print("")
    ok3 = rb_parse_check()
    print("")
    ok4 = relabel_check()
    print("")
    ok5 = constructed_checks()
    ok = ok1 and ok2 and ok3 and ok4 and ok5
    print("")
    print("LEGS SELFTEST %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
