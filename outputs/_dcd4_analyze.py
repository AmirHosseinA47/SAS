#!/usr/bin/env python
"""dcd4 round: read the fourth seed set against the committed arms.

Read-only on every data file; runs no simulation. Harness JSONs are loaded ONE
AT A TIME and reduced to a small per-run summary (--mode controls holds two).

  selftest   reproduce every known reference value from the committed arms and
             the L6 positive controls; one "PASS|FAIL <item> got= want=" line each
  controls   the six d4x* platform/tree controls against the committed JSON
  outcomes   fourth-set table, prior samples, THE GATE, reversal checks, pooled
  mechanism  M1-M5 for d4D/d4A against dfD/dfA
  exposure   E1-E3
  deadlock   D1-D3 and L1-L6, with dcB (fresh) and dfm2ref (canonical) alongside
  all        selftest, controls, outcomes, mechanism, exposure, deadlock

SAMPLES
  canonical 13  east/half 101..505, south/half 101..505, east/default 101/202/303
  fresh 10      east/half 606..1010, south/half 606..1010
  fourth 30     the 30 tuples declared in dcd4_prereg.txt section 1 (FOURTH_PREREG
                below). Cross-checked against the d4off, d4D and d4A lines of
                _dcd4_queue.txt (what the wave actually ran; THE GATE gives no
                verdict unless this matches) and against _dcd4_seeds.choose().
                choose() rejects any seed found in an outputs/ file NAME, and this
                wave writes _ffr_d4*_<seed>.json, so it is called with this wave's
                own files (_ffr_d4*) hidden from that one screen; it is a check
                only, never the source, because any new file carrying a seed
                token would silently change what it returns.
  VALIDITY      a d4* run counts only if _dcd4_validate.check() (the pool's own
                completeness test, read-only) says VALID for its queue line; a
                present-but-invalid run (e.g. GAVEUP, whose files the pool leaves
                in place) is EXCLUDED, never read as zero, and listed. Every run of
                every arm must also carry tag/wind/roles/seed/steps equal to its
                file name, an eval object and 240 uav_steps rows.
  rbgate 18     _rblatch_camp2_<tag><shard>_D_<wind>.json "evals", shard a/b/c
                east, s south. Exact names, never a prefix glob.
  prior 41 = canonical + fresh + rbgate 18 (14 rbgate tuples repeat canonical or
  fresh tuples). prior 27 distinct = canonical + fresh + rbgate shard c.

FRAMES. uav_steps[i] is the state AFTER harness step i+1. burn_intervals[cell] is
a list of half-open [a, b) step intervals (b None = to the horizon); the cell
burns on frame i iff a <= i+1 < b. rtb_log steps are harness step numbers:
VERIFIED on every leg of dfD/dfA/dcB/dcC/dfm2ref that trigger_step == (index of
the leg's first "returning" frame) + 1, arrival_step == (last leg frame) + 2, and
trigger_distance is the distance at frame trigger_step - 2 (before that step's
move). Rows may have 4 fields [uid,pos,role,sd] (ihbase, dimfreshbase): indexed
by position, never unpacked.

DEFINITIONS
  O1  rescued, dead, never_detected (nd), firefighter_deaths (ff_deaths) from
      eval; terminal = resolved runs / total and mean eval.terminal_step over
      the resolved runs.
  M1  return trips = rtb_log records, all UAVs; arrived = arrival_step not None.
  M2  mean return distance = mean trigger_distance over ALL trips.
  M3  return-leg share = sum rtb_counters[*].return_steps / (n_uav * 240),
      n_uav = len(rtb_counters) or 4; raw sum reported too.
  M4  charging = sum rtb_counters[*].charge_steps over the same denominator.
  M5  fallback dock = arrived trip with dock_cell != target_berth. Dock cell
      classified twice, first match wins: other UAV's berth, own berth (not the
      target), firefighter berth, plain depot cell, OUTSIDE every depot. Once
      against HOME berths (base_station.uav_berths, index = UAV order in
      uav_steps) and once against uav_berths_by_depot. Firefighter berths per
      depot are not recorded; they are rebuilt from _build_base_station's
      ranking on the 50x50 grid ONLY where that ranking reproduces the recorded
      uav_berths_by_depot. Depot footprint = size x size from each origin, +x/+y.
      Two-depot arms: trips and mean trigger_distance per target_depot.
  E1  searcher-only (interior-hazard) = (frame,UAV) with role victim_searcher,
      pos not None and pos burning (rebuilt from burn_intervals) / (frame,UAV)
      with role victim_searcher and pos not None. Pooled per sample.
  E2  all-UAV (depot/dock-fix) = sum uav_actions[i][j][2] / all uav_actions
      entries. Cross-check: uav_actions[2] vs the burn_intervals flag.
  E3  per UAV, maximal runs of consecutive frames with the burning flag
      (uav_actions[2]; burn_intervals where absent): counts >=2/>=3/>=5 and max,
      all UAVs, and searchers (flag AND role victim_searcher on that frame).
      SAME-CELL STAY = maximal run of >= 2 consecutive frames on one cell with
      the flag set (its max is over those stays, 0 if none). Split by base_state (flying "", returning, charging/docked):
      a run goes under the state of most of its frames; a tie goes to
      returning, then charging/docked, then flying; mixed runs are counted.
  D1  STUCK = last frame base_state "returning" AND >= 10 trailing frames (from
      the last frame back) on the final position.
  D2  UNARRIVED trip (arrival_step None). HORIZON-TRUNCATED iff the UAV is
      "returning" at the last frame, is not STUCK, and its distance to the
      trip's target_berth at the last frame is strictly less than at the frame
      10 earlier; otherwise NOT-TRUNCATED. That is the classification used.
      Reported alongside, NOT used: a trip-bounded variant that, for a leg of
      <= 10 frames (the frame 10 earlier predates the trigger), compares the
      last-frame distance against trigger_distance instead.
  D3  ZERO-BATT = final battery <= 0 and final position outside every depot.
  L1  return LEG = maximal run of frames with base_state "returning" (positions).
  L2  FREEZE = longest run of one position within the leg >= 3 frames.
  L3  CYCLE = after collapsing consecutive repeats, a cell repeats.
  L4  OSCILLATION = a 10-frame window with <= 2 distinct cells and >= 2 changes.
  L5  REVISIT = in the collapsed list some cell occurs >= 3 times. REVISIT
      implies CYCLE by construction, and a pure freeze collapses to one entry.
  L6  PROGRESS = leg mapped to its trip by trigger_step == first frame + 1;
      d[k] = distance from leg position k to target_berth; violation = any k
      with k+10 in the leg and d[k+10] >= d[k]. Legs counted with >= 1
      violation, split by position k inside / outside the TARGET depot's
      footprint. Longest non-decreasing stretch = most consecutive leg frames
      with d[k+1] >= d[k] throughout.
  Each of L2-L6 is counted once per leg.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import statistics
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = 240
GRID = 50
STUCK_FRAMES = 10
TRUNC_WINDOW = 10
FREEZE_FRAMES = 3
OSC_WIN = 10
REVISIT_COUNT = 3
PROG_WIN = 10
LEG_TRIGGER_OFFSET = 1   # trigger_step - index of the leg's first frame (verified)
SEARCHER = "victim_searcher"
WAVE_PREFIX = "_ffr_d4"

CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "def", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
RB_SHARDS = (("a", "east"), ("b", "east"), ("c", "east"), ("s", "south"))
# dcd4_prereg.txt section 1, in assignment order (13 east/half, 13 south/half, 4 east/default)
FOURTH_PREREG = (
    [("east", "half", s) for s in (1686422896, 339529960, 1323590814, 565244337, 1799457742,
                                   213441142, 1038975554, 899534678, 2116546930, 1659006522,
                                   1626974145, 1465634084, 150314831)]
    + [("south", "half", s) for s in (207893904, 990257450, 301432237, 423146201, 1483537190,
                                      1587703022, 1776294962, 2097141346, 1817334565, 752343876,
                                      1038470813, 1989343762, 3682542)]
    + [("east", "def", s) for s in (737555233, 1266834353, 1756726159, 2111261717)])

# (control tag, committed tag it must reproduce, wind, rr, seed) = _dcd4_queue.CONTROLS
CONTROLS = [
    ("d4xD", "dfD", "east", "half", 303),
    ("d4xD", "dfD", "south", "half", 808),
    ("d4xA", "dfA", "south", "half", 606),
    ("d4xA", "dfA", "east", "def", 202),
    ("d4x0", "dfzero", "east", "half", 404),
    ("d4x0", "dfzero", "south", "half", 1010),
]
FOURTH_ARMS = (("base", "d4off"), ("D", "d4D"), ("A", "d4A"))
PRIOR_ARMS = {"base": ("dcoff", "rbc"), "D": ("dcD", "dcrbD"), "A": ("dcA", "dcrbA")}
STATES = ("flying", "returning", "charging/docked")
STATE_TIE = ("returning", "charging/docked", "flying")


# ------------------------------------------------------------------ loading ----
def load_json(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8-sig"))
    except (OSError, ValueError):
        return None


def ffr_path(tag, wind, rr, seed):
    return os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def tlabel(t):
    return "%s/%s/%d" % t


_FOURTH = None


def _chosen_tuples():
    """_dcd4_seeds.choose() with this wave's own files hidden from its file-name screen."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import _dcd4_seeds as seeds_mod

    real = seeds_mod.filename_tokens

    def tokens_without_this_wave():
        toks = set()
        for name in os.listdir(HERE):
            if name.startswith(WAVE_PREFIX):
                continue
            for tok in re.findall(r"\d+", name):
                if int(tok) >= 100:
                    toks.add(int(tok))
        return toks

    seeds_mod.filename_tokens = tokens_without_this_wave
    try:
        tuples, rejected = seeds_mod.choose()
    finally:
        seeds_mod.filename_tokens = real
    return ([(c.split("|")[0], "def" if c.split("|")[1] == "default" else c.split("|")[1],
              int(s)) for c, s, _cell, _idx in tuples], rejected)


def fourth():
    """(tuples, note, checks). tuples = FOURTH_PREREG, always. checks["queue"] is True only
    if the d4off, d4D and d4A lines of _dcd4_queue.txt each list exactly those tuples in
    that order (None if the queue file is absent); checks["choose"] likewise for
    _dcd4_seeds.choose() with this wave's files hidden."""
    global _FOURTH
    if _FOURTH is not None:
        return _FOURTH
    out = list(FOURTH_PREREG)
    checks = {"queue": None, "choose": None}
    q = os.path.join(HERE, "_dcd4_queue.txt")
    qnote = "_dcd4_queue.txt ABSENT - cannot verify"
    if os.path.exists(q):
        per = {tag: [] for _r, tag in FOURTH_ARMS}
        with open(q, encoding="utf-8") as f:
            for raw in f:
                p = raw.replace("\r", "").rstrip("\n").split("|")
                if len(p) >= 5 and p[0] in per:
                    per[p[0]].append((p[2], "def" if p[3] == "default" else p[3], int(p[4])))
        bad = [tag for tag in per if per[tag] != out]
        checks["queue"] = not bad
        qnote = ("equals the d4off/d4D/d4A lines of _dcd4_queue.txt: %s"
                 % ("YES" if not bad else "NO - WARNING, differs for %s" % bad))
    try:
        chosen, rejected = _chosen_tuples()
        checks["choose"] = chosen == out
        cnote = "_dcd4_seeds.choose() (wave files hidden) gives it: %s, %d rejected" % (
            "YES" if checks["choose"] else "NO - WARNING (check only, not the source)",
            len(rejected))
    except Exception as exc:  # a check, never the source
        cnote = "_dcd4_seeds.choose() FAILED: %s" % type(exc).__name__
    note = "fourth set: %d tuples from dcd4_prereg.txt section 1; %s; %s" % (
        len(out), qnote, cnote)
    _FOURTH = (out, note, checks)
    return _FOURTH


def sample(name):
    return {"canonical": CANON, "fresh": FRESH, "both": CANON + FRESH}.get(name) \
        or fourth()[0]


_CACHE: dict = {}
EXCLUDED: dict = {}     # (tag, wind, rr, seed) -> why a PRESENT file was not counted
_QUEUE_RUNS = None


def _queue_runs():
    """name -> (validator module, queue run) from _dcd4_queue.txt; {} if absent."""
    global _QUEUE_RUNS
    if _QUEUE_RUNS is None:
        _QUEUE_RUNS = {}
        q = os.path.join(HERE, "_dcd4_queue.txt")
        if os.path.exists(q):
            if HERE not in sys.path:
                sys.path.insert(0, HERE)
            import _dcd4_validate as vmod
            for r in vmod.read_queue(q, os.path.join(HERE, "_ffr_"),
                                     os.path.join(HERE, "_ffr_logs")):
                _QUEUE_RUNS[r["name"]] = (vmod, r)
    return _QUEUE_RUNS


def _why_invalid(tag, t, path):
    """None if the present file may be counted, else the reason it may not."""
    if tag.startswith("d4"):
        name = "%s_%s_%s_%d" % (tag, t[0], t[1], t[2])
        qr = _queue_runs().get(name)
        if qr is None:
            return "not a line of _dcd4_queue.txt, cannot be validated"
        status, why = qr[0].check(qr[1])
        if status != "VALID":
            return ("%s %s" % (status, why)).strip()
    return None


def summary(tag, t):
    key = (tag,) + tuple(t)
    if key not in _CACHE:
        _CACHE[key] = None
        path = ffr_path(tag, *t)
        if not os.path.exists(path):
            return None
        why = _why_invalid(tag, t, path)
        d = load_json(path) if why is None else None
        if why is None and d is None:
            why = "json does not parse"
        if d is not None:
            want = (tag, t[0], "default" if t[1] == "def" else t[1], int(t[2]), STEPS)
            got = (d.get("tag"), d.get("wind"), d.get("roles"), d.get("seed"), d.get("steps"))
            if got != want:
                why = "tag/wind/roles/seed/steps %r != file name %r" % (got, want)
            elif not isinstance(d.get("eval"), dict):
                why = "no eval object"
            elif len(d.get("uav_steps") or []) != STEPS:
                why = "uav_steps has %d rows, not %d" % (len(d.get("uav_steps") or []), STEPS)
        if why is not None:
            EXCLUDED[key] = why
        elif d is not None:
            _CACHE[key] = summarize(d, "%s %s" % (tag, tlabel(t)))
        del d
    return _CACHE[key]


def print_excluded(prefix="  "):
    """Every present-but-uncounted run met so far in this process."""
    if not EXCLUDED:
        print("%sEXCLUDED present-but-invalid runs: none" % prefix)
        return
    print("%sEXCLUDED present-but-invalid runs (NOT counted, not zero): %d"
          % (prefix, len(EXCLUDED)))
    for (tag, wind, rr, seed), why in sorted(EXCLUDED.items()):
        print("%s  %s %s/%s/%d: %s" % (prefix, tag, wind, rr, seed, why))


def collect(tag, tuples):
    out = []
    for t in tuples:
        s = summary(tag, t)
        if s is not None:
            out.append((t, s))
    return out


def rbgate(tag, shards="abcs"):
    rows, missing = [], []
    for sh, wind in RB_SHARDS:
        if sh not in shards:
            continue
        p = os.path.join(HERE, "_rblatch_camp2_%s%s_D_%s.json" % (tag, sh, wind))
        d = load_json(p)
        if d is None:
            missing.append(os.path.basename(p))
            continue
        for ev in d.get("evals") or []:
            rows.append(_outcome(ev, "%s%s %s/%s" % (tag, sh, wind, ev.get("seed"))))
        del d
    return rows, missing


# ----------------------------------------------------------------- geometry ----
def geometry(station):
    if not station:
        return None
    size = int(station["size"])
    origins = [tuple(o) for o in (station.get("depots") or [station["origin"]])]
    foot = [frozenset((ox + i, oy + j) for i in range(size) for j in range(size))
            for ox, oy in origins]
    home = [tuple(b) for b in (station.get("uav_berths") or [])]
    bydep = [[tuple(b) for b in bl]
             for bl in (station.get("uav_berths_by_depot") or [[b] for b in home])]
    ff = {tuple(b) for b in (station.get("firefighter_berths") or [])}
    n_u, n_f = len(bydep), len(station.get("firefighter_berths") or [])
    ranked = [sorted(f, key=lambda c: (-min(c[0], c[1], GRID - 1 - c[0], GRID - 1 - c[1]),
                                       c[0], c[1])) for f in foot]
    rank_ok = all(len(bydep[a]) == len(foot) for a in range(n_u)) and all(
        ranked[k][a] == bydep[a][k] for a in range(n_u) for k in range(len(foot)))
    ff_bydep = ({ranked[k][n_u + i] for k in range(len(foot)) for i in range(n_f)
                 if n_u + i < len(ranked[k])} if rank_ok else set())
    return {"foot": foot, "cells": frozenset().union(*foot), "home": home,
            "bydep": bydep, "ff": ff, "ff_bydep": ff_bydep, "rank_ok": rank_ok}


def classify(cell, ai, geo):
    if geo is None:
        return "no station", "no station"
    cells = geo["cells"]

    def pick(other, own, ffs):
        if cell in other:
            return "other-UAV berth"
        if cell in own:
            return "own berth, not target"
        if cell in ffs:
            return "firefighter berth"
        if cell in cells:
            return "plain depot cell"
        return "OUTSIDE every depot"

    home, bydep = geo["home"], geo["bydep"]
    other_h = {b for j, b in enumerate(home) if j != ai}
    own_h = {home[ai]} if ai is not None and ai < len(home) else set()
    other_d = {b for j, bl in enumerate(bydep) if j != ai for b in bl}
    own_d = set(bydep[ai]) if ai is not None and ai < len(bydep) else set()
    return (pick(other_h, own_h, geo["ff"]),
            pick(other_d, own_d, geo["ff"] | geo["ff_bydep"]))


def manh(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def _pos(c):
    return tuple(c[1]) if c[1] is not None else None


def _bstate(c):
    s = str(c[5] or "") if len(c) > 5 else ""
    return {"": "flying", "returning": "returning", "charging": "charging/docked",
            "docked": "charging/docked"}.get(s, s)


def _majority(labels):
    cnt = collections.Counter(labels)
    best = max(cnt.values())
    tied = [s for s in cnt if cnt[s] == best]
    for s in STATE_TIE:
        if s in tied:
            return s, len(cnt) > 1
    return sorted(tied)[0], len(cnt) > 1


def _burning(bi, cell, step):
    for a, b in bi.get("%d,%d" % cell) or ():
        if a <= step and (b is None or step < b):
            return 1
    return 0


def _true_runs(flags):
    out, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i - start))
            start = None
    if start is not None:
        out.append((start, len(flags) - start))
    return out


def _outcome(ev, label):
    ev = ev or {}
    return {"label": label, "rescued": int(ev.get("rescued") or 0),
            "dead": int(ev.get("dead") or 0), "nd": int(ev.get("never_detected") or 0),
            "ffd": int(ev.get("firefighter_deaths") or 0),
            "terminal": ev.get("terminal_step")}


# ---------------------------------------------------------------- summarize ----
def summarize(d, label):
    S = _outcome(d.get("eval"), label)
    rows = d.get("uav_steps") or []
    geo = geometry(d.get("base_station"))
    order = [str(c[0]) for c in rows[0]] if rows else []
    S["rank_ok"] = geo["rank_ok"] if geo else None
    _mechanism(S, d, geo, order)
    _exposure(S, rows, d.get("uav_actions"), d.get("burn_intervals"), geo)
    _deadlock(S, d, rows, geo, order)
    return S


def _mechanism(S, d, geo, order):
    counters = d.get("rtb_counters") or {}
    S["n_uav"] = len(counters) or 4
    S["return_steps"] = sum(int(c.get("return_steps") or 0) for c in counters.values())
    S["charge_steps"] = sum(int(c.get("charge_steps") or 0) for c in counters.values())
    S["berth_mism"] = 0
    if geo:
        for uid, c in counters.items():
            ai = order.index(uid) if uid in order else None
            if (ai is not None and ai < len(geo["home"]) and c.get("berth") is not None
                    and tuple(c["berth"]) != geo["home"][ai]):
                S["berth_mism"] += 1
    trips = []
    for uid, log in (d.get("rtb_log") or {}).items():
        ai = order.index(uid) if uid in order else None
        for t in log or []:
            rec = {"uid": uid, "trigger": t.get("trigger_step"),
                   "d": t.get("trigger_distance"), "depot": int(t.get("target_depot") or 0),
                   "target": (tuple(t["target_berth"]) if t.get("target_berth") is not None
                              else None),
                   "arrival": t.get("arrival_step"),
                   "dock": tuple(t["dock_cell"]) if t.get("dock_cell") is not None else None}
            rec["fallback"] = (rec["arrival"] is not None and rec["target"] is not None
                               and rec["dock"] != rec["target"])
            if rec["fallback"]:
                rec["cls_home"], rec["cls_depot"] = classify(rec["dock"], ai, geo)
            trips.append(rec)
    S["trips"] = trips


def _exposure(S, rows, acts, bi, geo):
    have_bi = isinstance(bi, dict)
    bi = bi if have_bi else {}
    acts = acts if isinstance(acts, list) and acts else None
    S["has_acts"], S["has_burn"] = acts is not None, have_bi
    e1n = e1d = e2n = e2d = mism = order_mism = 0
    nf = len(rows)
    nu = len(rows[0]) if rows else 0
    flags = [[0] * nu for _ in range(nf)]
    for i, row in enumerate(rows):
        arow = acts[i] if acts is not None and i < len(acts) else None
        for a, c in enumerate(row):
            pos = _pos(c)
            derived = _burning(bi, pos, i + 1) if pos is not None else 0
            if c[2] == SEARCHER and pos is not None:
                e1d += 1
                e1n += derived
            flag = derived
            if arow is not None:
                if a < len(arow) and str(arow[a][0]) == str(c[0]):
                    flag = int(bool(arow[a][2]))
                    mism += int(flag != derived)
                else:
                    order_mism += 1
            flags[i][a] = flag
    if acts is not None:
        for arow in acts:
            for ent in arow or ():
                e2d += 1
                if len(ent) > 2 and ent[2]:
                    e2n += 1
    S.update(e1n=e1n, e1d=e1d, e2n=e2n, e2d=e2d, e2_mism=mism, e2_order_mism=order_mism)
    runs_all, runs_srch, same = [], [], []
    role_change = 0
    unknown_state = sum(1 for row in rows for c in row
                        if _bstate(c) not in STATES)
    for a in range(nu):
        uid = str(rows[0][a][0])
        roles = [rows[i][a][2] for i in range(nf)]
        role_change += int(len(set(roles)) > 1)
        states = [_bstate(rows[i][a]) for i in range(nf)]
        poss = [_pos(rows[i][a]) for i in range(nf)]
        f = [flags[i][a] for i in range(nf)]
        for st0, n in _true_runs(f):
            runs_all.append((n,) + _majority(states[st0:st0 + n]))
        for st0, n in _true_runs([f[i] and roles[i] == SEARCHER for i in range(nf)]):
            runs_srch.append((n,) + _majority(states[st0:st0 + n]))
        i = 0
        while i < nf:
            if not (f[i] and poss[i] is not None):
                i += 1
                continue
            j = i
            while j + 1 < nf and f[j + 1] and poss[j + 1] == poss[i]:
                j += 1
            n = j - i + 1
            if n >= 2:
                st, mixed = _majority(states[i:j + 1])
                same.append((n, st, mixed, uid, roles[i], poss[i], i + 1,
                             bool(geo and poss[i] in geo["cells"])))
            i = j + 1
    S.update(runs_all=runs_all, runs_srch=runs_srch, same=same, role_change=role_change,
             unknown_state=unknown_state)


def _leg_metrics(uid, f0, leg, trip, geo, nf):
    m = {"uid": uid, "start_step": f0 + 1, "frames": len(leg),
         "horizon": f0 + len(leg) == nf, "last": leg[-1]}
    best, cur, cell = 1, 1, leg[0]
    for i in range(1, len(leg)):
        cur = cur + 1 if leg[i] == leg[i - 1] else 1
        if cur > best:
            best, cell = cur, leg[i]
    m["freeze"], m["freeze_cell"] = best, cell
    collapsed = [c for i, c in enumerate(leg) if i == 0 or c != leg[i - 1]]
    seen, m["cycle"] = set(), None
    for c in collapsed:
        if c in seen:
            m["cycle"] = c
            break
        seen.add(c)
    cnt = collections.Counter(collapsed).most_common(1)
    m["revisit"] = cnt[0] if cnt and cnt[0][1] >= REVISIT_COUNT else None
    m["osc"] = None
    for i in range(0, max(0, len(leg) - OSC_WIN + 1)):
        w = leg[i:i + OSC_WIN]
        moves = sum(1 for j in range(1, len(w)) if w[j] != w[j - 1])
        if len(set(w)) <= 2 and moves >= 2:
            m["osc"] = (f0 + i + 1, w)
            break
    m["target"] = trip.get("target_berth") if trip else None
    m["arrived"] = bool(trip and trip.get("arrival_step") is not None)
    m["prog_in"] = m["prog_out"] = 0
    m["prog_first_out"] = m["prog_first_in"] = None
    m["nd_stretch"] = 0
    if m["target"] is None:
        return m
    tb = tuple(m["target"])
    k_dep = int(trip.get("target_depot") or 0)
    foot = geo["foot"][k_dep] if geo and k_dep < len(geo["foot"]) else frozenset()
    dd = [manh(p, tb) if p is not None else None for p in leg]
    for k in range(len(leg) - PROG_WIN):
        if dd[k] is None or dd[k + PROG_WIN] is None or dd[k + PROG_WIN] < dd[k]:
            continue
        where = "in" if leg[k] in foot else "out"
        m["prog_" + where] += 1
        if m["prog_first_" + where] is None:
            m["prog_first_" + where] = (f0 + k + 1, leg[k], dd[k], dd[k + PROG_WIN])
    best = cur = 1
    for k in range(1, len(leg)):
        ok = dd[k] is not None and dd[k - 1] is not None and dd[k] >= dd[k - 1]
        cur = cur + 1 if ok else 1
        best = max(best, cur)
    m["nd_stretch"] = best
    return m


def _deadlock(S, d, rows, geo, order):
    stuck, zero, unarr, legs = [], [], [], []
    align_miss = 0
    nf = len(rows)
    logs = d.get("rtb_log") or {}
    stuck_uids = set()
    if rows:
        last = rows[-1]
        for a, uid in enumerate(order):
            c = last[a]
            pos = _pos(c)
            batt = float(c[4] or 0.0) if len(c) > 4 and c[4] is not None else None
            if batt is not None and batt <= 0.0 and (geo is None or pos not in geo["cells"]):
                zero.append((uid, pos, batt))
            if len(c) > 5 and str(c[5] or "") == "returning":
                k = 0
                for i in range(nf - 1, -1, -1):
                    if _pos(rows[i][a]) != pos:
                        break
                    k += 1
                if k >= STUCK_FRAMES:
                    stuck.append((uid, pos, k, batt))
                    stuck_uids.add(uid)
    for uid, log in logs.items():
        a = order.index(uid) if uid in order else None
        for t in log or []:
            if t.get("arrival_step") is not None:
                continue
            tb = tuple(t["target_berth"]) if t.get("target_berth") is not None else None
            cls, why = "NOT-TRUNCATED", ""
            cls_trip = "NOT-TRUNCATED"   # trip-bounded variant, reported, never used
            if a is None or tb is None or nf <= TRUNC_WINDOW:
                why = "no frame or no target_berth"
            else:
                cl, cp = rows[-1][a], rows[-1 - TRUNC_WINDOW][a]
                if not (len(cl) > 5 and str(cl[5] or "") == "returning"):
                    why = "not returning at the last frame"
                elif uid in stuck_uids:
                    why = "STUCK"
                elif _pos(cl) is None or _pos(cp) is None:
                    why = "no position"
                else:
                    dn, dt = manh(_pos(cl), tb), manh(_pos(cp), tb)
                    if dn < dt:
                        cls = "HORIZON-TRUNCATED"
                    cls_trip = cls
                    why = "distance to target %d frames earlier %d, at the last frame %d" % (
                        TRUNC_WINDOW, dt, dn)
                    leg_frames = nf - (int(t.get("trigger_step") or 0) - LEG_TRIGGER_OFFSET)
                    if leg_frames <= TRUNC_WINDOW:
                        # The definition is applied as written; this only says what
                        # it compared. A leg this short puts the earlier frame
                        # BEFORE the trigger, so the test reads pre-return flight.
                        td = t.get("trigger_distance")
                        cls_trip = ("HORIZON-TRUNCATED" if td is not None and dn < int(td)
                                    else "NOT-TRUNCATED")
                        why += ("; leg is only %d frames, so the earlier frame predates the "
                                "trigger; trip-bounded variant (last %d vs trigger_distance %s) "
                                "-> %s" % (leg_frames, dn, td, cls_trip))
            unarr.append({"uid": uid, "trigger": t.get("trigger_step"), "target": tb,
                          "cls": cls, "cls_trip": cls_trip, "why": why,
                          "last": _pos(rows[-1][a]) if (rows and a is not None) else None})
    for a, uid in enumerate(order):
        trips = logs.get(uid) or []
        by_trig = {}
        for t in trips:
            by_trig.setdefault(t.get("trigger_step"), t)
        li = 0
        leg, f0 = [], None
        for fi in range(nf + 1):
            ret = fi < nf and len(rows[fi][a]) > 5 and str(rows[fi][a][5] or "") == "returning"
            if ret:
                if f0 is None:
                    f0 = fi
                leg.append(_pos(rows[fi][a]))
                continue
            if f0 is None:
                continue
            t = by_trig.get(f0 + LEG_TRIGGER_OFFSET)
            if t is None:
                align_miss += 1
                t = trips[li] if li < len(trips) else None
            m = _leg_metrics(uid, f0, leg, t, geo, nf)
            m["stuck"] = uid in stuck_uids and m["horizon"]
            legs.append(m)
            li += 1
            leg, f0 = [], None
    S.update(stuck=stuck, zero=zero, unarr=unarr, legs=legs, align_miss=align_miss)


# -------------------------------------------------------------- aggregation ----
def terminal_str(rr):
    got = [int(s["terminal"]) for s in rr if s["terminal"] is not None]
    if not got:
        return "0/%d" % len(rr)
    return "%d/%d mean %.1f" % (len(got), len(rr), statistics.mean(got))


def totals(rr):
    return {k: sum(s[k] for s in rr) for k in ("rescued", "dead", "nd", "ffd")}


def agg_mech(rr):
    A = {"runs": len(rr), "trips": 0, "arrived": 0, "dsum": 0, "dn": 0, "ret": 0,
         "chg": 0, "denom": 0, "fb": 0, "unclass": 0, "home": collections.Counter(),
         "dep": collections.Counter(), "per_depot": {}, "fb_list": [], "berth_mism": 0,
         "rank_bad": 0}
    for s in rr:
        A["ret"] += s["return_steps"]
        A["chg"] += s["charge_steps"]
        A["denom"] += s["n_uav"] * STEPS
        A["berth_mism"] += s["berth_mism"]
        A["rank_bad"] += int(s["rank_ok"] is False)
        for t in s["trips"]:
            A["trips"] += 1
            A["arrived"] += int(t["arrival"] is not None)
            if t["d"] is not None:
                A["dsum"] += t["d"]
                A["dn"] += 1
            pd = A["per_depot"].setdefault(t["depot"], [0, 0])
            pd[0] += 1
            pd[1] += t["d"] or 0
            if t["target"] is None:
                A["unclass"] += 1
            elif t["fallback"]:
                A["fb"] += 1
                A["home"][t["cls_home"]] += 1
                A["dep"][t["cls_depot"]] += 1
                A["fb_list"].append((s["label"], t))
    A["mean_d"] = A["dsum"] / A["dn"] if A["dn"] else None
    A["ret_pct"] = 100.0 * A["ret"] / A["denom"] if A["denom"] else 0.0
    A["chg_pct"] = 100.0 * A["chg"] / A["denom"] if A["denom"] else 0.0
    return A


def e3_counts(runs):
    return (sum(1 for r in runs if r[0] >= 2), sum(1 for r in runs if r[0] >= 3),
            sum(1 for r in runs if r[0] >= 5), max((r[0] for r in runs), default=0))


def agg_exp(rr):
    A = {"runs": len(rr), "e1n": 0, "e1d": 0, "e2n": 0, "e2d": 0, "mism": 0, "omism": 0,
         "acts_runs": 0, "burn_runs": 0, "all": [], "srch": [], "same": [],
         "role_change": 0, "unknown_state": 0}
    for s in rr:
        for k in ("e1n", "e1d", "e2n", "e2d"):
            A[k] += s[k]
        A["mism"] += s["e2_mism"]
        A["omism"] += s["e2_order_mism"]
        A["acts_runs"] += int(s["has_acts"])
        A["burn_runs"] += int(s["has_burn"])
        A["all"] += s["runs_all"]
        A["srch"] += s["runs_srch"]
        A["same"] += [(x[0], x[1], x[2], s["label"]) + x[3:] for x in s["same"]]
        A["role_change"] += s["role_change"]
        A["unknown_state"] += s["unknown_state"]
    return A


def agg_dead(rr):
    A = {"runs": len(rr), "uavs": 0, "stuck": [], "zero": [], "unarr": [], "legs": 0,
         "freeze": 0, "cycle": [], "osc": [], "revisit": [], "prog_any": 0, "prog_in": 0,
         "prog_out": [], "nd_max": 0, "align_miss": 0, "leg_list": []}
    for s in rr:
        lab = s["label"]
        A["uavs"] += s["n_uav"]
        A["align_miss"] += s["align_miss"]
        A["stuck"] += [(lab,) + x for x in s["stuck"]]
        A["zero"] += [(lab,) + x for x in s["zero"]]
        A["unarr"] += [(lab, x) for x in s["unarr"]]
        for m in s["legs"]:
            A["legs"] += 1
            A["leg_list"].append((lab, m))
            A["freeze"] += int(m["freeze"] >= FREEZE_FRAMES)
            if m["cycle"] is not None:
                A["cycle"].append((lab, m))
            if m["osc"] is not None:
                A["osc"].append((lab, m))
            if m["revisit"] is not None:
                A["revisit"].append((lab, m))
            A["prog_any"] += int(m["prog_in"] > 0 or m["prog_out"] > 0)
            A["prog_in"] += int(m["prog_in"] > 0)
            if m["prog_out"] > 0:
                A["prog_out"].append((lab, m))
            A["nd_max"] = max(A["nd_max"], m["nd_stretch"])
    return A


def pct(n, d):
    return "%d/%d = %.2f%%" % (n, d, 100.0 * n / d) if d else "%d/0 = -" % n


def fmt_cell(c):
    return "(%d,%d)" % tuple(c) if c is not None else "None"


# ----------------------------------------------------------------- selftest ----
class Checker:
    def __init__(self):
        self.ok = self.bad = 0

    def item(self, name, got, want):
        good = str(got) == str(want)
        self.ok += int(good)
        self.bad += int(not good)
        print("%s %s got=%s want=%s" % ("PASS" if good else "FAIL", name, got, want))


def _mech_str(A, *fields):
    out = []
    for f in fields:
        if f == "trips":
            out.append("trips %d arrived %d" % (A["trips"], A["arrived"]))
        elif f == "d1":
            out.append("mean_d %.1f" % A["mean_d"])
        elif f == "d2":
            out.append("mean_d %.2f" % A["mean_d"])
        elif f == "ret":
            out.append("return_steps %d (%.2f%%)" % (A["ret"], A["ret_pct"]))
        elif f == "chg":
            out.append("charging %d (%.2f%%)" % (A["chg"], A["chg_pct"]))
        elif f == "fb":
            out.append("fallback %d" % A["fb"])
    return "; ".join(out)


def _out_str(rr):
    t = totals(rr)
    return "%d/%d/%d/%d term %s" % (t["rescued"], t["dead"], t["nd"], t["ffd"],
                                    terminal_str(rr))


def mode_selftest(_args):
    print("SELFTEST  every known reference value, recomputed from the committed arms")
    C = Checker()
    both = CANON + FRESH

    def rr(tag, tuples):
        return [s for _t, s in collect(tag, tuples)]

    # ---- presence
    for tag, tuples, n in (("dfD", both, 23), ("dfA", both, 23), ("dfB", both, 23),
                           ("dfC", both, 23), ("dfzero", both, 23), ("dfkill", both, 23),
                           ("dcoff", both, 23), ("dcA", both, 23), ("dcB", both, 23),
                           ("dcC", both, 23), ("dcD", both, 23), ("dfm2ref", CANON, 13),
                           ("ihbase", CANON, 13), ("dimfreshbase", FRESH, 10)):
        C.item("present %s" % tag, len(rr(tag, tuples)), n)
    _tuples4, note, checks = fourth()
    print("INFO %s" % note)
    C.item("fourth seed set: prereg == d4off/d4D/d4A lines of _dcd4_queue.txt",
           checks["queue"], True)
    C.item("fourth seed set: _dcd4_seeds.choose() (wave files hidden) == prereg",
           checks["choose"], True)

    # ---- M1-M5
    A = agg_mech(rr("dfD", both))
    C.item("M dfD both", _mech_str(A, "trips", "d1", "ret", "chg", "fb"),
           "trips 92 arrived 92; mean_d 29.4; return_steps 2741 (12.41%); "
           "charging 1196 (5.42%); fallback 2")
    C.item("M dfD canonical", _mech_str(agg_mech(rr("dfD", CANON)), "ret", "fb"),
           "return_steps 1560 (12.50%); fallback 2")
    Af = agg_mech(rr("dfD", FRESH))
    C.item("M dfD fresh", "trips %d; %s" % (Af["trips"], _mech_str(Af, "d2", "ret", "fb")),
           "trips 40; mean_d 29.20; return_steps 1181 (12.30%); fallback 0")
    B = agg_mech(rr("dfA", both))
    C.item("M dfA both", "trips %d; %s" % (B["trips"], _mech_str(B, "d1", "ret", "chg", "fb")),
           "trips 90; mean_d 41.0; return_steps 3705 (16.78%); charging 1009 (4.57%); "
           "fallback 2")
    C.item("M dfA fresh return_steps", agg_mech(rr("dfA", FRESH))["ret"], 1523)
    C.item("M dcD both", _mech_str(agg_mech(rr("dcD", both)), "ret", "fb"),
           "return_steps 2735 (12.39%); fallback 1")
    C.item("M dcA both", _mech_str(agg_mech(rr("dcA", both)), "ret", "fb"),
           "return_steps 3711 (16.81%); fallback 1")

    def cls(counter, key):
        return counter.get(key, 0)
    C.item("M5 dfD both by HOME berths (other-UAV, plain depot cell)",
           "%d, %d" % (cls(A["home"], "other-UAV berth"), cls(A["home"], "plain depot cell")),
           "1, 1")
    C.item("M5 dfA both by HOME berths (other-UAV, plain depot cell)",
           "%d, %d" % (cls(B["home"], "other-UAV berth"), cls(B["home"], "plain depot cell")),
           "1, 1")
    C.item("M5 dfD both by uav_berths_by_depot (other-UAV)",
           cls(A["dep"], "other-UAV berth"), 2)
    mism = sum(agg_mech(rr(t, both))["berth_mism"] for t in ("dfD", "dfA", "dcD", "dcA"))
    C.item("M5 uav_berths[i] == rtb_counters[uid].berth (UAV order index), mismatches",
           mism, 0)
    rank_bad = sum(agg_mech(rr(t, both))["rank_bad"] for t in ("dfD", "dcD", "dfA", "dcA"))
    C.item("M5 50x50 ranking reproduces uav_berths_by_depot, runs where it does not",
           rank_bad, 0)

    # ---- E2
    for tag, samp, tuples, want in (
            ("dfD", "canonical", CANON, "439/12480 = 3.52%"),
            ("dfD", "fresh", FRESH, "186/9600 = 1.94%"),
            ("dfA", "canonical", CANON, "382/12480 = 3.06%"),
            ("dfA", "fresh", FRESH, "231/9600 = 2.41%"),
            ("dfzero", "canonical", CANON, "180/12480 = 1.44%"),
            ("dfzero", "fresh", FRESH, "193/9600 = 2.01%")):
        E = agg_exp(rr(tag, tuples))
        C.item("E2 %s %s" % (tag, samp), pct(E["e2n"], E["e2d"]), want)
        print("INFO E2 %s %s uav_actions[2] vs burn_intervals mismatches %d, uid-order "
              "mismatches %d" % (tag, samp, E["mism"], E["omism"]))
    # ---- E1
    for tag, samp, tuples, want in (
            ("dfzero", "canonical", CANON, "115/5520 = 2.08%"),
            ("dfzero", "fresh", FRESH, "152/4800 = 3.17%"),
            ("dfD", "canonical", CANON, "278/5520 = 5.04%"),
            ("dfD", "fresh", FRESH, "156/4800 = 3.25%"),
            ("dfA", "canonical", CANON, "286/5520 = 5.18%"),
            ("dfA", "fresh", FRESH, "203/4800 = 4.23%"),
            ("ihbase", "canonical", CANON, "117/5520 = 2.12%"),
            ("dimfreshbase", "fresh", FRESH, "143/4800 = 2.98%")):
        E = agg_exp(rr(tag, tuples))
        C.item("E1 %s %s" % (tag, samp), pct(E["e1n"], E["e1d"]), want)
    # ---- E3
    for tag, want in (("dfD", "max 18, >=3 65, >=5 25"), ("dfA", "max 13, >=3 57, >=5 21")):
        c = e3_counts(agg_exp(rr(tag, both))["all"])
        C.item("E3 %s both all-UAV" % tag, "max %d, >=3 %d, >=5 %d" % (c[3], c[1], c[2]), want)
    Ec, Ef = agg_exp(rr("dfD", CANON)), agg_exp(rr("dfD", FRESH))
    C.item("E3 dfD canonical all-UAV >=2/>=3/>=5/max", "%d/%d/%d/%d" % e3_counts(Ec["all"]),
           "82/50/18/15")
    C.item("E3 dfD fresh all-UAV >=2/>=3/>=5/max", "%d/%d/%d/%d" % e3_counts(Ef["all"]),
           "26/15/7/18")
    C.item("E3 dfD canonical searchers >=2/>=3/>=5/max", "%d/%d/%d/%d" % e3_counts(Ec["srch"]),
           "49/31/11/15")
    C.item("E3 dfD canonical same-cell stays >=2", len(Ec["same"]), 24)
    C.item("E3 dfD fresh same-cell stays >=2", len(Ef["same"]), 3)
    print("INFO E3 UAVs whose role changes within a run (dfD both): %d"
          % (Ec["role_change"] + Ef["role_change"]))

    # ---- D1 / D2
    def stuck_str(D):
        return "%d %s" % (len(D["stuck"]), ["%s %s %s %d %.1f" % (
            lab.split(" ", 1)[1], uid, fmt_cell(pos), k, b) for lab, uid, pos, k, b in D["stuck"]])
    C.item("D1 dcB fresh STUCK", stuck_str(agg_dead(rr("dcB", FRESH))),
           "1 ['east/half/808 2500 (4,44) 38 35.4']")
    C.item("D1 dcB canonical STUCK", len(agg_dead(rr("dcB", CANON))["stuck"]), 0)
    for tag in ("dfA", "dfB", "dfC", "dfD"):
        for samp, tuples in (("canonical", CANON), ("fresh", FRESH)):
            C.item("D1 %s %s STUCK" % (tag, samp), len(agg_dead(rr(tag, tuples))["stuck"]), 0)
    Dm = agg_dead(rr("dfm2ref", CANON))
    C.item("D1 dfm2ref canonical STUCK",
           "%d uids %s cells %s frames %s" % (
               len(Dm["stuck"]), sorted({x[1] for x in Dm["stuck"]}),
               sorted({fmt_cell(x[2]) for x in Dm["stuck"]}),
               "/".join(str(k) for k in sorted(x[3] for x in Dm["stuck"]))),
           "5 uids ['2502'] cells ['(3,44)'] frames 34/36/43/63/66")
    C.item("D2 dcB fresh unarrived", len(agg_dead(rr("dcB", FRESH))["unarr"]), 1)
    C.item("D2 dcC canonical unarrived", len(agg_dead(rr("dcC", CANON))["unarr"]), 3)
    C.item("D2 dfD both unarrived", len(agg_dead(rr("dfD", both))["unarr"]), 0)
    for tag, tuples in (("dcB", FRESH), ("dcC", CANON)):
        for lab, u in agg_dead(rr(tag, tuples))["unarr"]:
            print("INFO D2 %s %s uid %s trigger %s -> %s (%s)"
                  % (tag, lab, u["uid"], u["trigger"], u["cls"], u["why"]))

    # ---- L2/L3/L4
    for tag, tuples, want in (("dfA", both, "2/0/0"), ("dfB", both, "15/0/0"),
                              ("dfC", both, "20/0/0"), ("dfD", both, "3/0/0"),
                              ("dcB", both, "11/0/0"), ("dfkill", both, "11/0/0"),
                              ("dfm2ref", CANON, "5/0/0")):
        D = agg_dead(rr(tag, tuples))
        C.item("L2/L3/L4 %s %s freeze/cycle/osc" % (tag, "canonical" if tuples is CANON
                                                      else "both"),
               "%d/%d/%d" % (D["freeze"], len(D["cycle"]), len(D["osc"])), want)

    # ---- outcomes
    for tag, tuples, samp, want in (
            ("dfD", both, "both", "68/16/5/10 term 21/23 mean 162.0"),
            ("dcD", CANON, "canonical", "39/10/1/6 term 12/13 mean 151.9"),
            ("dcD", FRESH, "fresh", "29/6/4/4 term 9/10 mean 175.6"),
            ("dcoff", CANON, "canonical", "35/12/0/8 term 10/13 mean 169.6"),
            ("dcoff", FRESH, "fresh", "29/4/1/7 term 6/10 mean 173.2"),
            ("dcA", CANON, "canonical", "38/10/4/4 term 13/13 mean 170.4"),
            ("dcA", FRESH, "fresh", "29/6/4/1 term 9/10 mean 184.3")):
        C.item("O1 %s %s rescued/dead/nd/ffd" % (tag, samp), _out_str(rr(tag, tuples)), want)
    for tag, want in (("rbc", "53/11/2/9 term 14/18 mean 186.8"),
                      ("dcrbA", "48/12/11/6 term 17/18 mean 182.9"),
                      ("dcrbD", "57/11/2/9 term 17/18 mean 149.4")):
        rows, missing = rbgate(tag)
        C.item("O1 rbgate %s rescued/dead/nd/ffd" % tag, _out_str(rows), want)
        if missing:
            print("INFO rbgate %s missing shards %s" % (tag, missing))
    for role, want in (("base", "nd 3 rescued 117"), ("D", "nd 7 rescued 125"),
                       ("A", "nd 19 rescued 115")):
        rows = prior(role, "abcs")[0]
        t = totals(rows)
        C.item("O1 pooled 41 %s (%s+%s)" % (role, PRIOR_ARMS[role][0], PRIOR_ARMS[role][1]),
               "nd %d rescued %d" % (t["nd"], t["rescued"]), want)

    # ---- structural
    miss = sum(agg_dead(rr(t, tuples))["align_miss"]
               for t, tuples in (("dfD", both), ("dfA", both), ("dcB", both), ("dcC", both),
                                 ("dfB", both), ("dfC", both), ("dfkill", both),
                                 ("dfm2ref", CANON)))
    C.item("L6 alignment: every leg's first frame + %d is a trip trigger_step, misses"
           % LEG_TRIGGER_OFFSET, miss, 0)
    viol = 0
    for t, tuples in (("dfD", both), ("dfA", both), ("dcB", both), ("dfB", both),
                      ("dfC", both), ("dfkill", both), ("dfm2ref", CANON)):
        for _lab, m in agg_dead(rr(t, tuples))["leg_list"]:
            viol += int(m["revisit"] is not None and m["cycle"] is None)
    C.item("L5 REVISIT implies L3 CYCLE on every leg, legs violating", viol, 0)

    # ---- reconciled with the independent blind checker (dcd4_blind.py, 2026-09-13):
    # every value below was computed by both implementations and agreed.
    mode2 = [(t, both) for t in ("dcA", "dcB", "dcC", "dcD", "dfA", "dfB", "dfC", "dfD",
                                 "dfkill")] + [("dfm2ref", CANON), ("dfm2fix", CANON)]
    nlegs = miss = frames_vs_ret = 0
    for t, tuples in mode2:
        for s in rr(t, tuples):
            nlegs += len(s["legs"])
            miss += s["align_miss"]
            frames_vs_ret += int(sum(m["frames"] for m in s["legs"]) != s["return_steps"])
    C.item("R leg alignment, all 11 mode>=2 arms: legs / trigger misses / runs where leg "
           "frames != return_steps", "%d/%d/%d" % (nlegs, miss, frames_vs_ret), "920/0/0")

    def split_str(runs):
        parts = " | ".join("%d/%d/%d/%d" % e3_counts([r for r in runs if r[1] == st])
                           for st in STATES)
        return "%d/%d/%d/%d; %s; mixed %d" % (e3_counts(runs) + (parts, sum(
            1 for r in runs if r[0] >= 2 and r[2])))
    for tag, samp, tuples, want_all, want_same in (
            ("dfD", "canonical", CANON, "82/50/18/15; 54/31/11/15 | 14/8/3/9 | 14/11/4/12; mixed 6",
             "24/19/8/15; 11/8/4/15 | 0/0/0/0 | 13/11/4/9; mixed 4"),
            ("dfD", "fresh", FRESH, "26/15/7/18; 19/11/5/11 | 6/3/1/5 | 1/1/1/18; mixed 1",
             "3/2/2/14; 2/1/1/11 | 0/0/0/0 | 1/1/1/14; mixed 1"),
            ("dfA", "canonical", CANON, None, "9/7/4/9; 8/6/4/9 | 0/0/0/0 | 1/1/0/3; mixed 1"),
            ("dfA", "fresh", FRESH, None, "4/4/2/11; 4/4/2/11 | 0/0/0/0 | 0/0/0/0; mixed 0")):
        E = agg_exp(rr(tag, tuples))
        if want_all:
            C.item("R E3 %s %s all-UAV total; flying | returning | charging/docked" % (tag, samp),
                   split_str(E["all"]), want_all)
        C.item("R E3 %s %s same-cell total; flying | returning | charging/docked" % (tag, samp),
               split_str(E["same"]), want_same)
    for tag, samp, tuples, want in (("dfD", "canonical", CANON, "8 (4 inside a depot)"),
                                    ("dfD", "fresh", FRESH, "2 (1 inside a depot)"),
                                    ("dfA", "canonical", CANON, "4 (0 inside a depot)"),
                                    ("dfA", "fresh", FRESH, "2 (0 inside a depot)")):
        ge5 = [x for x in agg_exp(rr(tag, tuples))["same"] if x[0] >= 5]
        C.item("R E3 %s %s same-cell stays >= 5" % (tag, samp),
               "%d (%d inside a depot)" % (len(ge5), sum(1 for x in ge5 if x[-1])), want)
    C.item("R E3 dfD fresh searchers", "%d/%d/%d/%d" % e3_counts(agg_exp(rr("dfD", FRESH))["srch"]),
           "22/14/7/18")
    C.item("R E3 dfA canonical / fresh all-UAV", "%d/%d/%d/%d, %d/%d/%d/%d" % (
        e3_counts(agg_exp(rr("dfA", CANON))["all"]) + e3_counts(agg_exp(rr("dfA", FRESH))["all"])),
        "69/36/13/9, 36/21/8/13")
    C.item("R E3 dfA both searchers", "%d/%d/%d/%d" % e3_counts(agg_exp(rr("dfA", both))["srch"]),
           "81/47/20/13")
    C.item("R E2 ihbase canonical", pct(*[agg_exp(rr("ihbase", CANON))[k] for k in ("e2n", "e2d")]),
           "181/12480 = 1.45%")

    def depot_str(A):
        return "; ".join("depot %d %d trips %.2f" % (k, v[0], v[1] / float(v[0]))
                         for k, v in sorted(A["per_depot"].items()))
    for samp, tuples, want in (("canonical", CANON, "depot 0 31 trips 31.19; depot 1 21 trips 26.95"),
                               ("fresh", FRESH, "depot 0 21 trips 28.48; depot 1 19 trips 30.00"),
                               ("both", both, "depot 0 52 trips 30.10; depot 1 40 trips 28.40")):
        C.item("R M per target depot dfD %s" % samp, depot_str(agg_mech(rr("dfD", tuples))), want)
    C.item("R M5 dfA both by uav_berths_by_depot (other-UAV, plain depot cell)",
           "%d, %d" % (B["dep"].get("other-UAV berth", 0), B["dep"].get("plain depot cell", 0)),
           "1, 1")

    C.item("R D1 dfkill fresh STUCK", stuck_str(agg_dead(rr("dfkill", FRESH))),
           "1 ['east/half/808 2500 (4,44) 38 35.4']")
    C.item("R D1 dfkill canonical / dfm2fix canonical STUCK", "%d/%d" % (
        len(agg_dead(rr("dfkill", CANON))["stuck"]), len(agg_dead(rr("dfm2fix", CANON))["stuck"])),
        "0/0")
    Dc = agg_dead(rr("dcC", CANON))
    C.item("R D2 dcC canonical HORIZON-TRUNCATED/NOT, spec rule | trip-bounded variant",
           "%d/%d | %d/%d" % (
               sum(1 for _l, u in Dc["unarr"] if u["cls"] == "HORIZON-TRUNCATED"),
               sum(1 for _l, u in Dc["unarr"] if u["cls"] != "HORIZON-TRUNCATED"),
               sum(1 for _l, u in Dc["unarr"] if u["cls_trip"] == "HORIZON-TRUNCATED"),
               sum(1 for _l, u in Dc["unarr"] if u["cls_trip"] != "HORIZON-TRUNCATED")),
           "2/1 | 3/0")
    C.item("R D2 dfC canonical unarrived", len(agg_dead(rr("dfC", CANON))["unarr"]), 3)
    C.item("R D3 zero-batt over all 11 mode>=2 arms", sum(
        len(agg_dead(rr(t, tuples))["zero"]) for t, tuples in mode2), 0)
    for tag, tuples, samp, want in (("dfm2fix", CANON, "canonical", "5/0/0"),
                                    ("dcA", both, "both", "1/0/0"), ("dcD", both, "both", "1/0/0"),
                                    ("dcC", both, "both", "0/0/0")):
        D = agg_dead(rr(tag, tuples))
        C.item("R L2/L3/L4 %s %s freeze/cycle/osc" % (tag, samp),
               "%d/%d/%d" % (D["freeze"], len(D["cycle"]), len(D["osc"])), want)
    C.item("R L5 revisit on every leg of the 11 mode>=2 arms", sum(
        len(agg_dead(rr(t, tuples))["revisit"]) for t, tuples in mode2), 0)

    def l6_str(D):
        return "%d/%d/%d/%d" % (D["prog_any"], D["prog_in"], len(D["prog_out"]), D["nd_max"])

    def l6_ids(D):
        return sorted("%s %s %d %d" % (lab.split(" ", 1)[1], m["uid"], m["start_step"], m["frames"])
                      for lab, m in D["leg_list"] if m["prog_in"] or m["prog_out"])
    for tag, samp, tuples, want, ids in (
            ("dcB", "canonical", CANON, "3/0/3/14", ["east/half/202 2502 161 60",
                                                     "south/half/303 2502 165 56",
                                                     "south/half/404 2500 183 35"]),
            ("dcB", "fresh", FRESH, "3/0/3/38", ["east/half/808 2500 168 73",
                                                 "south/half/606 2500 170 50",
                                                 "south/half/909 2500 183 35"]),
            ("dfkill", "both", both, "6/0/6/38", None),
            ("dfm2ref", "canonical", CANON, "5/0/5/66", None),
            ("dcA", "fresh", FRESH, "1/1/0/11", ["south/half/606 2501 135 59"]),
            ("dfD", "canonical", CANON, "0/0/0/4", None), ("dfD", "fresh", FRESH, "0/0/0/2", None),
            ("dfA", "canonical", CANON, "0/0/0/2", None), ("dfA", "fresh", FRESH, "0/0/0/4", None)):
        D = agg_dead(rr(tag, tuples))
        C.item("R L6 %s %s legs any/inside/outside/longest-nd" % (tag, samp), l6_str(D), want)
        if ids:
            C.item("R L6 %s %s violating legs (run uid start_step frames)" % (tag, samp),
                   l6_ids(D), ids)
    C.item("R L6 legs any for dfB both / dfC both / dcC both / dcD both / dfm2fix canonical",
           "/".join(str(agg_dead(rr(t, tuples))["prog_any"]) for t, tuples in (
               ("dfB", both), ("dfC", both), ("dcC", both), ("dcD", both), ("dfm2fix", CANON))),
           "0/0/0/0/0")

    # ---- positive controls (L6 must fire, L5 reported)
    print("")
    print("POSITIVE CONTROLS  L6 must FIRE on every STUCK leg")
    for tag, tuples, samp, want_n in (("dcB", FRESH, "fresh", 1), ("dfm2ref", CANON, "canonical", 5)):
        D = agg_dead(rr(tag, tuples))
        stuck_legs = [(lab, m) for lab, m in D["leg_list"] if m["stuck"]]
        fired_out = [(lab, m) for lab, m in stuck_legs if m["prog_out"] > 0]
        C.item("L6 control %s %s STUCK legs with an OUTSIDE-depot progress violation"
               % (tag, samp), "%d/%d" % (len(fired_out), len(stuck_legs)),
               "%d/%d" % (want_n, want_n))
        for lab, m in stuck_legs:
            print("INFO   %s uid %s leg from step %d, %d frames, freeze %d at %s, "
                  "L6 out %d in %d, nd-stretch %d, L5 revisit %s, L3 cycle %s"
                  % (lab, m["uid"], m["start_step"], m["frames"], m["freeze"],
                     fmt_cell(m["freeze_cell"]), m["prog_out"], m["prog_in"],
                     m["nd_stretch"], m["revisit"], m["cycle"]))
        rev = [x for x in stuck_legs if x[1]["revisit"] is not None]
        print("INFO L5 on %s %s STUCK legs: %d/%d fire. By construction a freeze collapses "
              "to ONE entry, so REVISIT cannot fire on a pure freeze (it implies CYCLE, "
              "whose reference here is 0)." % (tag, samp, len(rev), len(stuck_legs)))
    for tag in ("dfA", "dfD"):
        for samp, tuples in (("canonical", CANON), ("fresh", FRESH)):
            D = agg_dead(rr(tag, tuples))
            print("INFO negative reference %s %s: legs %d, L5 revisit %d, L6 any %d "
                  "(inside target depot %d, outside %d), longest non-decreasing stretch %d"
                  % (tag, samp, D["legs"], len(D["revisit"]), D["prog_any"], D["prog_in"],
                     len(D["prog_out"]), D["nd_max"]))
    print("")
    C.item("present-but-invalid committed runs (excluded; see VALIDITY)", len(EXCLUDED), 0)
    print_excluded("INFO ")
    print("")
    print("SELFTEST %d PASS, %d FAIL, %d items" % (C.ok, C.bad, C.ok + C.bad))


# ----------------------------------------------------------------- controls ----
def _short(v):
    s = json.dumps(v, sort_keys=False) if not isinstance(v, str) else repr(v)
    return s if len(s) <= 60 else s[:57] + "..."


def first_diff(a, b, path):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return "%s: keys only in control %s, only in committed %s" % (
                path, sorted(set(a) - set(b))[:4], sorted(set(b) - set(a))[:4])
        for k in a:
            if a[k] != b[k]:
                return first_diff(a[k], b[k], "%s.%s" % (path, k))
        return "%s: equal" % path
    if isinstance(a, list) and isinstance(b, list):
        for i in range(min(len(a), len(b))):
            if a[i] != b[i]:
                return first_diff(a[i], b[i], "%s[%d]" % (path, i))
        return "%s: length %d (control) != %d (committed)" % (path, len(a), len(b))
    return "%s: control %s != committed %s" % (path, _short(a), _short(b))


def mode_controls(_args):
    print("CONTROLS  d4x* vs the committed arm, every top-level field except tag, wall_s")
    q = os.path.join(HERE, "_dcd4_queue.txt")
    if os.path.exists(q):
        with open(q, encoding="utf-8") as f:
            ql = [ln.replace("\r", "").split("|") for ln in f if ln.startswith("d4x")]
        qt = [(p[0], p[2], "def" if p[3] == "default" else p[3], int(p[4])) for p in ql]
        mine = [(c, w, r, s) for c, _ref, w, r, s in CONTROLS]
        print("  control list equals the d4x* lines of _dcd4_queue.txt: %s"
              % ("YES" if qt == mine else "NO - WARNING %s" % qt))
    present = identical = 0
    for ctag, ref, wind, rr_, seed in CONTROLS:
        t = (wind, rr_, seed)
        head = "  %-5s %-22s vs %-6s:" % (ctag, tlabel(t), ref)
        if not os.path.exists(ffr_path(ctag, *t)):
            print("%s MISSING (not on disk yet)" % head)
            continue
        why = _why_invalid(ctag, t, ffr_path(ctag, *t))
        if why is not None:
            print("%s PRESENT BUT NOT VALID, not compared: %s" % (head, why))
            continue
        dc = load_json(ffr_path(ctag, *t))
        if dc is None:
            print("%s PRESENT BUT DOES NOT PARSE, not compared" % head)
            continue
        dr = load_json(ffr_path(ref, *t))
        if dr is None:
            print("%s COMMITTED ARM FILE MISSING" % head)
            del dc
            continue
        present += 1
        keys = [k for k in dict.fromkeys(list(dc) + list(dr)) if k not in ("tag", "wall_s")]
        diffs = []
        for k in keys:
            if k not in dc or k not in dr:
                diffs.append("%s: absent in %s" % (k, "control" if k not in dc else "committed"))
            elif dc[k] != dr[k]:
                diffs.append(first_diff(dc[k], dr[k], k))
        if not diffs:
            identical += 1
            print("%s IDENTICAL (%d fields)" % (head, len(keys)))
        else:
            print("%s DIFFERS in %d of %d fields" % (head, len(diffs), len(keys)))
            for line in diffs:
                print("        %s" % line)
        del dc, dr
    print("CONTROLS %d/6 IDENTICAL (%d present)" % (identical, present))


# ----------------------------------------------------------------- outcomes ----
def prior(role, shards):
    tag, rbtag = PRIOR_ARMS[role]
    rows = [s for _t, s in collect(tag, CANON + FRESH)]
    rb, missing = rbgate(rbtag, shards)
    return rows + rb, missing


def paired(tuples, x, y):
    pairs = [(t, summary(x, t), summary(y, t)) for t in tuples]
    pairs = [(t, a, b) for t, a, b in pairs if a is not None and b is not None]
    dl = {k: sum(a[k] - b[k] for _t, a, b in pairs) for k in ("rescued", "dead", "nd", "ffd")}
    cmp_ = {}
    for k, lower_better in (("nd", True), ("rescued", False)):
        better = sum(1 for _t, a, b in pairs if (a[k] < b[k] if lower_better else a[k] > b[k]))
        worse = sum(1 for _t, a, b in pairs if (a[k] > b[k] if lower_better else a[k] < b[k]))
        cmp_[k] = (better, worse, len(pairs) - better - worse)
    return len(pairs), dl, cmp_


def _cell_out(s):
    if s is None:
        return "%-19s" % "   (missing)"
    term = "%3d" % s["terminal"] if s["terminal"] is not None else "  -"
    return "%3d %3d %3d %3d %s" % (s["rescued"], s["dead"], s["nd"], s["ffd"], term)


def mode_outcomes(_args):
    tuples, note, checks = fourth()
    print("OUTCOMES")
    print("  %s" % note)
    print("")
    print("(1) FOURTH SET per tuple   cells: rescued dead nd ff_deaths terminal_step")
    print("  %-24s | %-19s | %-19s | %-19s" % ("tuple", "d4off", "d4D", "d4A"))
    for t in tuples:
        print("  %-24s | %s | %s | %s" % (tlabel(t), _cell_out(summary("d4off", t)),
                                         _cell_out(summary("d4D", t)),
                                         _cell_out(summary("d4A", t))))
    print("")
    for _role, tag in FOURTH_ARMS:
        rows = [s for _t, s in collect(tag, tuples)]
        t = totals(rows)
        print("  TOTAL %-6s present %2d/%d  rescued %3d dead %3d nd %3d ff_deaths %3d  "
              "terminal %s" % (tag, len(rows), len(tuples), t["rescued"], t["dead"], t["nd"],
                               t["ffd"], terminal_str(rows)))
    print("")
    print("  SEED-MATCHED DELTAS (x - y over tuples where both are present)")
    for x, y in (("d4D", "d4off"), ("d4A", "d4off"), ("d4D", "d4A")):
        n, dl, cmp_ = paired(tuples, x, y)
        if not n:
            print("  %-5s - %-5s  no pairs yet" % (x, y))
            continue
        print("  %-5s - %-5s  pairs %2d  " % (x, y, n) + "  ".join(
            "%s %+d (%+.3f/run)" % (k, dl[k], dl[k] / float(n))
            for k in ("rescued", "dead", "nd", "ffd")))
        print("  %15s nd: %s better %d / worse %d / equal %d    rescued: %s better %d / "
              "worse %d / equal %d" % ("", x, cmp_["nd"][0], cmp_["nd"][1], cmp_["nd"][2],
                                        x, cmp_["rescued"][0], cmp_["rescued"][1],
                                        cmp_["rescued"][2]))
    print("")
    print("(2) PRIOR SAMPLES   base = dcoff | rbc   D = dcD | dcrbD   A = dcA | dcrbA")
    print("  %-12s %-5s %-7s %5s %7s %5s %4s %4s  %s"
          % ("sample", "arm", "tag", "runs", "rescued", "dead", "nd", "ffd", "terminal"))
    tot41 = {r: [] for r in ("base", "D", "A")}
    for samp, tuples_p in (("canonical13", CANON), ("fresh10", FRESH), ("rbgate18", None)):
        for role in ("base", "D", "A"):
            tag, rbtag = PRIOR_ARMS[role]
            if tuples_p is None:
                rows, missing = rbgate(rbtag)
                shown = rbtag + ("  MISSING %s" % missing if missing else "")
            else:
                rows = [s for _t, s in collect(tag, tuples_p)]
                shown = tag
            tot41[role] += rows
            t = totals(rows)
            print("  %-12s %-5s %-7s %5d %7d %5d %4d %4d  %s"
                  % (samp, role, shown, len(rows), t["rescued"], t["dead"], t["nd"],
                     t["ffd"], terminal_str(rows)))
    for role in ("base", "D", "A"):
        rows = tot41[role]
        t = totals(rows)
        print("  %-12s %-5s %-7s %5d %7d %5d %4d %4d  %s"
              % ("TOTAL 41", role, "", len(rows), t["rescued"], t["dead"], t["nd"], t["ffd"],
                 terminal_str(rows)))
    print("")
    n, dl, _c = paired(tuples, "d4D", "d4off")
    print("(3) THE GATE  on the fourth set ALONE, seed-matched d4D vs d4off, %d/%d pairs"
          % (n, len(tuples)))
    # A verdict needs all 30 VALID seed-matched pairs AND the seed set verified against
    # what the wave ran; missing or invalid runs are excluded from the pairs, never zero.
    verified = checks["queue"] is True
    complete = verified and len(tuples) == 30 and n >= 30
    pending = "INCOMPLETE" if verified else "NO VERDICT"
    c1, c2 = dl["nd"] <= 2, dl["rescued"] >= 0
    tag1 = ("PASS" if c1 else "FAIL") if complete else pending
    tag2 = ("PASS" if c2 else "FAIL") if complete else pending
    print("  clause 1  nd(d4D) - nd(d4off)           = %+d  (<= +2)   %s  [%+.3f/run]"
          % (dl["nd"], tag1, dl["nd"] / float(n) if n else 0.0))
    print("  clause 2  rescued(d4D) - rescued(d4off) = %+d  (>= 0)    %s  [%+.3f/run]"
          % (dl["rescued"], tag2, dl["rescued"] / float(n) if n else 0.0))
    if complete:
        print("  GATE %s" % ("PASS" if (c1 and c2) else "FAIL"))
    elif not verified:
        print("  GATE NO VERDICT (the seed set does not match _dcd4_queue.txt, or it is absent;"
              " %d valid pairs)" % n)
    else:
        print("  GATE INCOMPLETE (%d of 30 valid seed-matched pairs; the partial deltas above"
              " are not a verdict)" % n)
    print("")
    trip = [t for t in tuples if all(summary(tag, t) is not None for _r, tag in FOURTH_ARMS)]
    print("(4) REVERSAL CHECKS")
    r1 = dl["rescued"] < 0
    print("  R1 rescued(d4D) < rescued(d4off): %+d over %d pairs -> %s"
          % (dl["rescued"], n, ("REVERSED" if r1 else "not reversed") if complete
             else pending))
    ndD = sum(summary("d4D", t)["nd"] - summary("d4off", t)["nd"] for t in trip)
    ndA = sum(summary("d4A", t)["nd"] - summary("d4off", t)["nd"] for t in trip)
    print("  R2 nd(d4D)-nd(d4off) = %+d  >=  nd(d4A)-nd(d4off) = %+d  over %d complete "
          "triples -> %s" % (ndD, ndA, len(trip), ("REVERSED" if ndD >= ndA else "not reversed")
                              if (verified and len(trip) >= 30) else pending))
    print("")
    print("(5) POOLED  (fourth set = tuples where d4off, d4D and d4A are ALL present: %d)"
          % len(trip))
    fourth_rows = {role: [summary(tag, t) for t in trip] for role, tag in FOURTH_ARMS}
    p41 = {r: prior(r, "abcs")[0] for r in ("base", "D", "A")}
    p27 = {r: prior(r, "c")[0] for r in ("base", "D", "A")}
    cols = [("fourth", fourth_rows),
            ("prior 41", p41),
            ("41+fourth=71", {r: p41[r] + fourth_rows[r] for r in p41}),
            ("prior 27", p27),
            ("27+fourth=57", {r: p27[r] + fourth_rows[r] for r in p27})]
    print("  %-22s" % "" + "".join("%14s" % c for c, _x in cols))
    print("  %-22s" % "runs base/D/A" + "".join(
        "%14s" % ("%d/%d/%d" % tuple(len(x[r]) for r in ("base", "D", "A"))) for _c, x in cols))
    for k, name in (("nd", "never_detected"), ("rescued", "rescued"), ("dead", "dead"),
                    ("ffd", "ff_deaths")):
        tt = [{r: totals(x[r])[k] for r in ("base", "D", "A")} for _c, x in cols]
        for r in ("base", "D", "A"):
            print("  %-22s" % ("%s %s" % (name, r)) + "".join("%14d" % v[r] for v in tt))
        print("  %-22s" % ("%s D-base" % name) + "".join("%+14d" % (v["D"] - v["base"])
                                                          for v in tt))
        print("  %-22s" % ("%s A-base" % name) + "".join("%+14d" % (v["A"] - v["base"])
                                                          for v in tt))
    print("")
    print_excluded()


# ---------------------------------------------------------------- mechanism ----
def mode_mechanism(_args):
    tuples, note, _m = fourth()
    print("MECHANISM  M1-M5   share denominator = n_uav x 240 per run")
    print("  %s" % note)
    print("  %-6s %-9s %6s %6s %7s %7s %9s %8s %9s %8s %8s"
          % ("arm", "sample", "runs", "trips", "arrived", "mean d", "ret steps", "ret %",
             "chg steps", "chg %", "fallback"))
    plan = [("d4D", "fourth"), ("d4A", "fourth"), ("d4off", "fourth"),
            ("dfD", "canonical"), ("dfD", "fresh"), ("dfD", "both"),
            ("dfA", "canonical"), ("dfA", "fresh"), ("dfA", "both")]
    aggs = {}
    for tag, samp in plan:
        tt = sample(samp)
        A = agg_mech([s for _t, s in collect(tag, tt)])
        aggs[(tag, samp)] = A
        print("  %-6s %-9s %6s %6d %7d %7s %9d %7.2f%% %9d %7.2f%% %8d"
              % (tag, samp, "%d/%d" % (A["runs"], len(tt)), A["trips"], A["arrived"],
                 "%.2f" % A["mean_d"] if A["mean_d"] is not None else "-", A["ret"],
                 A["ret_pct"], A["chg"], A["chg_pct"], A["fb"]))
    A0 = aggs[("d4off", "fourth")]
    print("  d4off zero-trip check: %d trips, %d return steps over %d runs -> %s"
          % (A0["trips"], A0["ret"], A0["runs"],
             "OK" if A0["trips"] == 0 and A0["ret"] == 0 else "NOT ZERO"))
    print("")
    print("  FALLBACK DOCK CLASSIFICATION (first match: other-UAV berth, own berth not target,")
    print("  firefighter berth, plain depot cell, OUTSIDE)")
    for (tag, samp), A in aggs.items():
        if not A["fb"] and not A["unclass"]:
            continue
        print("  %-6s %-9s by HOME berths %s | by uav_berths_by_depot %s%s"
              % (tag, samp, dict(A["home"]), dict(A["dep"]),
                 ("  unclassifiable trips %d" % A["unclass"]) if A["unclass"] else ""))
        if samp != "both":
            for lab, t in A["fb_list"]:
                print("      %-30s uid %s trigger %s target depot %d berth %s -> dock %s  "
                      "[%s | %s]" % (lab, t["uid"], t["trigger"], t["depot"],
                                     fmt_cell(t["target"]), fmt_cell(t["dock"]),
                                     t["cls_home"], t["cls_depot"]))
    if any(A["rank_bad"] for A in aggs.values()):
        print("  WARNING: the 50x50 ranking did not reproduce uav_berths_by_depot on some "
              "runs; firefighter by-depot berths were not used there")
    print("")
    print("  PER TARGET DEPOT (trips, mean trigger_distance)")
    for tag, samp in (("d4D", "fourth"), ("dfD", "canonical"), ("dfD", "fresh"),
                      ("dfD", "both"), ("d4A", "fourth"), ("dfA", "both")):
        A = aggs[(tag, samp)]
        print("  %-6s %-9s %s" % (tag, samp, "   ".join(
            "depot %d: %d trips, mean d %.2f" % (k, v[0], v[1] / float(v[0]))
            for k, v in sorted(A["per_depot"].items())) or "(no trips)"))
    print("")
    print_excluded()


# ----------------------------------------------------------------- exposure ----
def _e3_row(runs):
    return "%4d %4d %4d %4d" % e3_counts(runs)


def mode_exposure(_args):
    tuples, note, _m = fourth()
    print("EXPOSURE")
    print("  %s" % note)
    plan = [("d4off", "fourth"), ("d4D", "fourth"), ("d4A", "fourth"),
            ("dfzero", "canonical"), ("dfzero", "fresh"), ("dfD", "canonical"),
            ("dfD", "fresh"), ("dfA", "canonical"), ("dfA", "fresh"),
            ("ihbase", "canonical"), ("dimfreshbase", "fresh")]
    aggs = {}
    for tag, samp in plan:
        tt = sample(samp)
        aggs[(tag, samp)] = (agg_exp([s for _t, s in collect(tag, tt)]), len(tt))
    print("")
    print("  E1 searcher-only (IH definition; references 8520706 2.12% canonical / 2.98% fresh)")
    print("  E2 all-UAV uav_actions[2] (dc/df definition), with the burn_intervals cross-check")
    print("  %-13s %-9s %6s %-24s %-24s %s"
          % ("arm", "sample", "runs", "E1 searcher", "E2 all-UAV", "E2 flag mismatches"))
    for (tag, samp), (E, n) in aggs.items():
        e2 = pct(E["e2n"], E["e2d"]) if E["acts_runs"] and tag != "dimfreshbase" else "n/a"
        mm = ("%d (uid-order %d)" % (E["mism"], E["omism"])) if e2 != "n/a" else "-"
        print("  %-13s %-9s %6s %-24s %-24s %s" % (tag, samp, "%d/%d" % (E["runs"], n),
                                                  pct(E["e1n"], E["e1d"]), e2, mm))
    print("")
    print("  E3 CONSECUTIVE BURNING   columns >=2 >=3 >=5 max")
    print("  state = base_state on most of the run's frames; ties -> returning, then")
    print("  charging/docked, then flying. 'mixed' = runs (>=2) spanning more than one state.")
    e3plan = [("d4off", "fourth"), ("d4D", "fourth"), ("d4A", "fourth"),
              ("dfD", "canonical"), ("dfD", "fresh"), ("dfA", "canonical"), ("dfA", "fresh")]
    listing = []
    for tag, samp in e3plan:
        E, n = aggs[(tag, samp)]
        print("  %-6s %-9s runs %s" % (tag, samp, "%d/%d" % (E["runs"], n)))
        for scope, runs in (("all UAVs", E["all"]), ("searchers", E["srch"]),
                            ("same-cell", E["same"])):
            parts = []
            for st in STATES:
                sub = [r for r in runs if r[1] == st]
                parts.append("%s %s" % (st, _e3_row(sub)))
            mixed = sum(1 for r in runs if r[0] >= 2 and r[2])
            print("      %-9s total %s | %s | mixed %d" % (scope, _e3_row(runs),
                                                         " | ".join(parts), mixed))
        if E["role_change"]:
            print("      note: %d UAVs change role within a run" % E["role_change"])
        if E["unknown_state"]:
            print("      WARNING: %d (frame,UAV) base_state values outside flying/returning/"
                  "charging/docked; per-state columns will not sum to the total"
                  % E["unknown_state"])
        listing += [(tag, samp) + x for x in E["same"] if x[0] >= 5]
    print("")
    print("  EVERY SAME-CELL STAY OF >= 5 FRAMES (start step = harness step of the first frame)")
    if not listing:
        print("    none")
    for tag, samp, n, st, mixed, lab, uid, role, cell, step, inside in listing:
        print("    %-6s %-9s %-30s uid %s %-16s cell %-8s start step %3d length %2d "
              "state %s%s  inside depot: %s" % (tag, samp, lab, uid, role, fmt_cell(cell),
                                                step, n, st, " (mixed)" if mixed else "",
                                                inside))
    print("")
    print_excluded()


# ----------------------------------------------------------------- deadlock ----
def mode_deadlock(_args):
    tuples, note, _m = fourth()
    print("DEADLOCK  D1 STUCK (>= %d trailing frames), D2 unarrived, D3 zero-batt,"
          % STUCK_FRAMES)
    print("          L2 freeze >= %d, L3 cycle, L4 oscillation (%d-frame window), L5 revisit"
          % (FREEZE_FRAMES, OSC_WIN))
    print("          (>= %d in the collapsed leg), L6 progress (%d-frame window)"
          % (REVISIT_COUNT, PROG_WIN))
    print("  %s" % note)
    print("  L6 alignment: leg first frame index + %d == trip trigger_step (verified)"
          % LEG_TRIGGER_OFFSET)
    plan = [("d4D", "fourth"), ("d4A", "fourth"), ("d4off", "fourth"),
            ("dfD", "canonical"), ("dfD", "fresh"), ("dfA", "canonical"), ("dfA", "fresh"),
            ("dcB", "fresh"), ("dfm2ref", "canonical")]
    print("  %-7s %-9s %6s %5s %5s %-11s %4s %5s %6s %5s %4s %5s %-12s %5s %5s"
          % ("arm", "sample", "runs", "UAVs", "STUCK", "unarr T/NOT", "zero", "legs",
             "freeze", "cycle", "osc", "revis", "L6 any/in/out", "ndmax", "align"))
    aggs = []
    for tag, samp in plan:
        tt = sample(samp)
        D = agg_dead([s for _t, s in collect(tag, tt)])
        aggs.append((tag, samp, D))
        tr = sum(1 for _l, u in D["unarr"] if u["cls"] == "HORIZON-TRUNCATED")
        print("  %-7s %-9s %6s %5d %5d %-11s %4d %5d %6d %5d %4d %5d %-12s %5d %5d"
              % (tag, samp, "%d/%d" % (D["runs"], len(tt)), D["uavs"], len(D["stuck"]),
                 "%d/%d" % (tr, len(D["unarr"]) - tr), len(D["zero"]), D["legs"], D["freeze"],
                 len(D["cycle"]), len(D["osc"]), len(D["revisit"]),
                 "%d/%d/%d" % (D["prog_any"], D["prog_in"], len(D["prog_out"])), D["nd_max"],
                 D["align_miss"]))
    print("  (dcB fresh and dfm2ref canonical are POSITIVE CONTROLS: L6 must fire there)")
    for tag, samp, D in aggs:
        diff = [(lab, u) for lab, u in D["unarr"] if u["cls_trip"] != u["cls"]]
        if diff:
            print("  D2 %s %s: the trip-bounded variant (not used) reclassifies %d of %d "
                  "unarrived trips; see the UNARRIVED lines" % (tag, samp, len(diff),
                                                                 len(D["unarr"])))
    print_excluded()
    print("")
    for tag, samp, D in aggs:
        pre = "  %-7s %-9s" % (tag, samp)
        for lab, uid, pos, k, b in D["stuck"]:
            print("%s STUCK      %-30s uid %s at %s for %d frames, battery %s"
                  % (pre, lab, uid, fmt_cell(pos), k, "%.1f" % b if b is not None else "-"))
        for lab, u in D["unarr"]:
            print("%s UNARRIVED  %-30s uid %s trigger %s target %s last %s -> %s (%s)"
                  % (pre, lab, u["uid"], u["trigger"], fmt_cell(u["target"]),
                     fmt_cell(u["last"]), u["cls"], u["why"]))
        for lab, uid, pos, b in D["zero"]:
            print("%s ZERO-BATT  %-30s uid %s at %s battery %.1f" % (pre, lab, uid,
                                                                    fmt_cell(pos), b))
        for lab, m in D["cycle"]:
            print("%s CYCLE      %-30s uid %s leg step %d (%d frames) returns to %s"
                  % (pre, lab, m["uid"], m["start_step"], m["frames"], fmt_cell(m["cycle"])))
        for lab, m in D["osc"]:
            print("%s OSCILLATE  %-30s uid %s leg step %d window from step %d %s"
                  % (pre, lab, m["uid"], m["start_step"], m["osc"][0],
                     [fmt_cell(c) for c in m["osc"][1]]))
        for lab, m in D["revisit"]:
            print("%s REVISIT    %-30s uid %s leg step %d cell %s x%d"
                  % (pre, lab, m["uid"], m["start_step"], fmt_cell(m["revisit"][0]),
                     m["revisit"][1]))
        for lab, m in D["prog_out"]:
            s0, c0, d0, d1 = m["prog_first_out"]
            print("%s PROGRESS   %-30s uid %s leg step %d (%d frames, %s) target %s: %d "
                  "outside-depot k (first at step %d %s, d %d -> %d), %d inside; freeze %d "
                  "at %s; nd-stretch %d%s"
                  % (pre, lab, m["uid"], m["start_step"], m["frames"],
                     "arrived" if m["arrived"] else "NOT arrived", fmt_cell(m["target"]),
                     m["prog_out"], s0, fmt_cell(c0), d0, d1, m["prog_in"], m["freeze"],
                     fmt_cell(m["freeze_cell"]), m["nd_stretch"],
                     "  [STUCK leg]" if m["stuck"] else ""))
    print("")
    for tag, samp, D in aggs:
        if tag in ("dcB", "dfm2ref"):
            sl = [m for _l, m in D["leg_list"] if m["stuck"]]
            print("  POSITIVE CONTROL %s %s: L6 fires (outside) on %d of %d STUCK legs; "
                  "L5 fires on %d of them (a pure freeze collapses to one cell)"
                  % (tag, samp, sum(1 for m in sl if m["prog_out"] > 0), len(sl),
                     sum(1 for m in sl if m["revisit"] is not None)))


MODES = [("selftest", mode_selftest), ("controls", mode_controls),
         ("outcomes", mode_outcomes), ("mechanism", mode_mechanism),
         ("exposure", mode_exposure), ("deadlock", mode_deadlock)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=[m for m, _f in MODES] + ["all"])
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(newline="\n")
    except AttributeError:
        pass
    todo = MODES if args.mode == "all" else [m for m in MODES if m[0] == args.mode]
    for i, (_name, fn) in enumerate(todo):
        if i:
            print("")
            print("=" * 78)
            print("")
        fn(args)


if __name__ == "__main__":
    main()
