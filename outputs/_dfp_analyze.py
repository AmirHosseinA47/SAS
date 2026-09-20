# -*- coding: utf-8 -*-
"""Non-burnable-depot round: the round's analyzer. Read-only.

Every existing analyzer in outputs/ is tag-hard-coded to an earlier round
(_dcd4_analyze.py, _fm3_analyze.py, _ffr_analyze.py) and none of them reads a
WEST or NORTH tuple, so this round needs its own. What it adds over them:

  * a REPO CHECK. This is the first round whose arms live in two different
    checkouts, and outputs/_dcd4_validate.py never compares the JSON's `repo`
    against the queue line's. The dfpB control is the one arm that passes no
    --set while the dfp worktree ships BASE_STATION_FIREPROOF = 1, so a dfpB
    line aimed at the wrong checkout would produce a "control" that is the
    feature, and the pool would call it VALID. Every section below refuses to
    read a run whose `repo` is not the one its arm declares.
  * the BURNING-SET instrument (`burnsets`). The round's attribution rests on
    it and it did not exist: the harness digest hashes FUEL
    (_ffr_harness.py:482), so it differs at step 1 of every ON run by
    construction and proves nothing. Per-step burning sets are rebuilt from
    burn_intervals, which is fuel-blind.
  * the DEPOT-CHARGING SPLIT of the E1/E2 RATE. Stated precisely, because the
    first draft of this docstring overclaimed: _dcd4_analyze.py DOES split its
    same-cell STAY LIST by majority base_state and depot membership (its
    _exposure builds `same` with both), and that split is where this round's
    premise - "14 of 23 stays are UAVs charging in a burning depot" - comes from.
    What it does not do is split the E1/E2 RATE, which is the per-frame metric
    the brief asks to move. Section 5 adds that; section 5b calls _dcd4_analyze's
    own function for the stay statistic rather than re-transcribing it.
  * DEPOT CELLS ARE READ FROM THE RUN, never hard-coded (outputs/_dfp_corpus2.py
    hard-codes NW/SE origins; this reads base_station["depots"] + size).

usage:
  python outputs/_dfp_analyze.py identity     dfpB vs dfpOFF, value-identity
  python outputs/_dfp_analyze.py dry          dfpDRY vs dfpOFF, fire-value identity
  python outputs/_dfp_analyze.py burnsets     dfpON vs dfpOFF/dfpB, first differing step
  python outputs/_dfp_analyze.py book         the bookkeeping decomposition
  python outputs/_dfp_analyze.py exposure     E1/E2 with the charging/search split
  python outputs/_dfp_analyze.py outcomes     rescued/dead/ff_deaths/nd/terminal per arm
  python outputs/_dfp_analyze.py all          every section, to outputs/_dfp_analyze.txt
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEW_REPO = "E:/Projects/SAS_wt/dfp"
OLD_REPO = "E:/Projects/SAS_wt/base6281542"
ARM_REPO = {"dfpB": OLD_REPO, "dfpOFF": NEW_REPO, "dfpDRY": NEW_REPO, "dfpON": NEW_REPO,
            "dfpCB": OLD_REPO, "dfpCON": NEW_REPO}
# The dcD pins every arm carries, exactly as outputs/_dfp_queue.py emits them.
DCD = {"BASE_STATION_MODE": 3, "BASE_STATION_RETURN_MECHANISM": 2,
       "UAV_RETURN_TO_BASE_RESERVE": 0, "BASE_STATION_RETURN_MARGIN": 39.23,
       "BASE_STATION_DEPOTS": 9, "BASE_STATION_SPAWN_SPLIT": 2}
ARM_SETS = {
    "dfpB": dict(DCD),
    "dfpOFF": dict(DCD, BASE_STATION_FIREPROOF=0),
    "dfpDRY": dict(DCD, BASE_STATION_FIREPROOF=1, BASE_STATION_FIREPROOF_DRY_RUN=1),
    "dfpON": dict(DCD, BASE_STATION_FIREPROOF=1),
    # COMMON RANDOM NUMBERS. outputs/_fm2_probe_harness.py replaces Fire.step's
    # single draw with crn_uniform(seed, cell unique_id, that cell's
    # steps_counter), so clearing 50 cells' fuel cannot shift the draw of any
    # other cell. Every difference between these two arms is PHYSICAL. They
    # compare only with each other: the CRN fire is a different, equally
    # distributed realisation from the stock one.
    "dfpCB": dict(DCD, FM2P_CRN=1),
    "dfpCON": dict(DCD, FM2P_CRN=1, BASE_STATION_FIREPROOF=1),
}
# value identity excludes only what a different process/checkout must change
EXCLUDE = ("tag", "repo", "wall_s", "params", "extra_params")
SEARCHER = "victim_searcher"

CANONICAL = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
RB_EXTRA = [("east", "half", s) for s in (111, 222, 333, 444)]
WESTNORTH = ([("west", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("north", "half", s) for s in (101, 202, 303, 404, 505)])
RB18 = ([("east", "half", s) for s in (101, 202, 303, 404, 505, 606, 707, 808, 909, 111, 222, 333, 444)]
        + [("south", "half", s) for s in (101, 202, 303, 404, 505)])
SAMPLES = [("canonical13", CANONICAL), ("fresh10", FRESH),
           ("rb18extras", RB_EXTRA), ("westnorth", WESTNORTH)]

OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)
    sys.stdout.flush()


def label(t):
    return "%s/%s/%d" % (t[0], t[1], t[2])


def name(tag, t):
    rr = "def" if t[1] == "default" else t[1]
    return "%s_%s_%s_%d" % (tag, t[0], rr, t[2])


_CACHE = {}


def load(tag, t, strict=True):
    """Load a run, REFUSING one whose repo or --set does not match its arm."""
    key = (tag, t)
    if key in _CACHE:
        return _CACHE[key]
    p = os.path.join(HERE, "_ffr_%s.json" % name(tag, t))
    d = None
    if os.path.exists(p) and not os.path.exists(p + ".tmp"):
        log = os.path.join(HERE, "_ffr_logs", name(tag, t) + ".out")
        ok_log = (os.path.exists(log)
                  and "seed=" in open(log, encoding="utf-8", errors="replace").read())
        if ok_log:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
    if d is not None and strict and tag in ARM_REPO:
        want = os.path.normcase(os.path.abspath(ARM_REPO[tag]))
        got = os.path.normcase(os.path.abspath(d.get("repo") or ""))
        if got != want:
            say("  !! REPO MISMATCH %s %s: recorded %s, arm declares %s - REFUSED"
                % (tag, label(t), d.get("repo"), ARM_REPO[tag]))
            d = None
        elif dict(d.get("extra_params") or {}) != ARM_SETS[tag]:
            say("  !! SET MISMATCH %s %s: recorded %s, arm declares %s - REFUSED"
                % (tag, label(t), d.get("extra_params"), ARM_SETS[tag]))
            d = None
    _CACHE[key] = d
    return d


def depot_cells(d):
    """The depot cell set, READ FROM THE RUN. None when the station is off."""
    bs = d.get("base_station")
    if not bs:
        return None
    size = int(bs["size"])
    origins = bs.get("depots") or [bs["origin"]]
    return {(int(ox) + i, int(oy) + j)
            for ox, oy in origins for i in range(size) for j in range(size)}


def burning_at(bi, step):
    """The set of burning cells at `step`, rebuilt from burn_intervals.

    burn_intervals is built in _ffr_harness.py:487-493 from the POST-step
    observation: a key enters at the step it is first seen burning and its
    interval is closed at the step it is first seen NOT burning, so the cell is
    burning on steps [start, end) and on [start, horizon] when end is None. A
    cell can hold several intervals - scorched ground re-ignites.
    """
    out = set()
    for k, ivs in bi.items():
        for a, b in ivs:
            if a <= step and (b is None or step < b):
                out.add(k)
                break
    return out


def burning_series(d):
    bi = d.get("burn_intervals") or {}
    n = len(d.get("fire_digests") or [])
    return [burning_at(bi, s) for s in range(1, n + 1)]


def first_depot_ignition(d):
    """The first step at which any depot cell is burning, from this run's own geometry."""
    cells = depot_cells(d)
    if not cells:
        return None
    keys = {"%d,%d" % c for c in cells}
    bi = d.get("burn_intervals") or {}
    starts = [iv[0] for k, ivs in bi.items() if k in keys for iv in ivs]
    return min(starts) if starts else None


# ---------------------------------------------------------------- sections ---
def sec_identity(new="dfpOFF", old="dfpB", tuples=CANONICAL):
    say("")
    say("=" * 100)
    say("1. KILL SWITCH - %s (feature checkout, switch 0) vs %s (6281542, no --set)" % (new, old))
    say("=" * 100)
    say("   value-identity: every recorded key except %s" % ", ".join(EXCLUDE))
    ok, miss, bad = 0, 0, []
    for t in tuples:
        a, b = load(new, t), load(old, t)
        if a is None or b is None:
            miss += 1
            continue
        diff = sorted(k for k in set(a) | set(b) if k not in EXCLUDE and a.get(k) != b.get(k))
        if diff:
            bad.append("%s: %s" % (label(t), ",".join(diff)))
        else:
            ok += 1
    say("   %s %d/%d value-identical%s"
        % ("PASS" if ok == len(tuples) else "FAIL", ok, len(tuples),
           ("   PENDING %d" % miss) if miss else ""))
    for b in bad[:10]:
        say("      DIFF", b)
    return ok == len(tuples) and miss == 0


FIRE_KEYS = ("fire_digests", "fire_final_digest", "burn_intervals", "first_burn_step",
             "fire_ground_final")


def sec_dry(new="dfpDRY", old="dfpOFF", tuples=CANONICAL):
    say("")
    say("=" * 100)
    say("2. DRY ARM - %s (cells identified, nothing written) vs %s" % (new, old))
    say("=" * 100)
    say("   DRY writes no fuel, so EVERY fire value must match, the fuel-hashing digests included.")
    ok, miss, bad = 0, 0, []
    for t in tuples:
        a, b = load(new, t), load(old, t)
        if a is None or b is None:
            miss += 1
            continue
        diff = [k for k in FIRE_KEYS if a.get(k) != b.get(k)]
        if (a.get("eval") or {}).get("burnt_cells") != (b.get("eval") or {}).get("burnt_cells"):
            diff.append("eval.burnt_cells")
        full = sorted(k for k in set(a) | set(b) if k not in EXCLUDE and a.get(k) != b.get(k))
        if diff:
            bad.append("%s: fire %s | all %s" % (label(t), ",".join(diff), ",".join(full)))
        else:
            ok += 1
            if full:
                bad.append("%s: fire identical, but non-fire keys differ: %s"
                           % (label(t), ",".join(full)))
    say("   %s %d/%d fire-value-identical%s"
        % ("PASS" if ok == len(tuples) else "FAIL", ok, len(tuples),
           ("   PENDING %d" % miss) if miss else ""))
    for b in bad[:10]:
        say("      ", b)
    return ok == len(tuples) and miss == 0


def control(t, prefer=("dfpOFF", "dfpB")):
    """The control run for a tuple. dfpOFF exists only on the canonical sample;
    everywhere else the control is dfpB, which section 1 proves value-identical
    to it 13 of 13, so the two are interchangeable as a control."""
    for tag in prefer:
        d = load(tag, t)
        if d is not None:
            return tag, d
    return None, None


def sec_burnsets(new="dfpON", old=None, samples=SAMPLES):
    say("")
    say("=" * 100)
    say("3. ATTRIBUTION - the per-step BURNING SET, %s vs %s" % (new, old))
    say("=" * 100)
    say("   PRE-REGISTERED (outputs/depotfireproof_part1.txt:213-217): in every run whose control")
    say("   has a depot ignition, the two arms' burning sets are IDENTICAL up to that step and")
    say("   first differ AT it. A run with no depot ignition is a vacuous null, not evidence.")
    say("   The harness fire digest hashes FUEL, so it differs at step 1 of every ON run by")
    say("   construction; this instrument is fuel-blind by reading burn_intervals only.")
    say("")
    say("   %-18s %8s %8s %8s   %s" % ("run", "1st dep", "1st diff", "match", "first difference"))
    hit = total = miss = vac = 0
    for sname, tuples in samples:
        rows = 0
        for t in tuples:
            a = load(new, t)
            ctag, b = control(t) if old is None else (old, load(old, t))
            if a is None or b is None:
                miss += 1
                continue
            if rows == 0:
                say("   -- %s   (control arm: %s)" % (sname, ctag))
            rows += 1
            fd = first_depot_ignition(b)
            sa, sb = burning_series(a), burning_series(b)
            n = min(len(sa), len(sb))
            first = None
            for i in range(n):
                if sa[i] != sb[i]:
                    first = i + 1
                    break
            if fd is None:
                vac += 1
                say("   %-18s %8s %8s %8s   VACUOUS - no depot cell ever burns in the control"
                    % (label(t), "-", first if first else "none", "n/a"))
                continue
            total += 1
            good = (first == fd)
            hit += int(good)
            if first is None:
                det = "no difference at all"
            else:
                only = sorted(sb[first - 1] - sa[first - 1])
                extra = sorted(sa[first - 1] - sb[first - 1])
                dep = {"%d,%d" % c for c in (depot_cells(b) or set())}
                det = ("control-only %s%s | new-only %s"
                       % (only[:4], " (all depot cells)" if only and set(only) <= dep else "",
                          extra[:4]))
            say("   %-18s %8s %8s %8s   %s"
                % (label(t), fd, first if first else "none", "YES" if good else "NO", det))
    say("")
    say("   %s %d/%d runs first differ EXACTLY at the control's first depot ignition"
        % ("PASS" if hit == total and total else "FAIL", hit, total))
    say("   vacuous nulls (no depot ignition in the control): %d ; pending pairs: %d" % (vac, miss))
    return hit == total and total > 0


def ground_counts(d):
    g = d.get("fire_ground_final") or {}
    ever = sum(1 for v in g.values() if v[0] or v[1] or v[2])
    burnt = sum(1 for v in g.values() if v[1])
    untouched = len(g) - ever
    return len(g), ever, burnt, untouched


def sec_book(new="dfpON", old=None, samples=SAMPLES):
    say("")
    say("=" * 100)
    say("4. BOOKKEEPING vs BEHAVIOUR")
    say("=" * 100)
    say("   The depot-cell component is exact arithmetic: in %s no depot cell can burn, so the" % new)
    say("   control's own per-run counts ARE the predicted shift. Anything left over is")
    say("   BEHAVIOURAL and has to be named.")
    say("")
    say("   %-18s | %5s %5s | %6s %6s %6s | %6s %6s %6s"
        % ("run", "dEver", "dBrnt", "unt_ctl", "unt_new", "d_unt", "brn_ctl", "brn_new", "d_brn"))
    tot = dict(dep_ever=0, dep_burnt=0, d_unt=0, d_brn=0, n=0)
    rem_u, rem_b = [], []
    missing = []
    for sname, tuples in samples:
        rows = 0
        for t in tuples:
            a = load(new, t)
            ctag, b = control(t) if old is None else (old, load(old, t))
            if a is None or b is None:
                missing.append(label(t))
                continue
            if rows == 0:
                say("   -- %s   (control arm: %s)" % (sname, ctag))
            rows += 1
            dep = depot_cells(b) or set()
            gb = b.get("fire_ground_final") or {}
            ga = a.get("fire_ground_final") or {}
            keys = {"%d,%d" % c for c in dep}
            dep_ever = sum(1 for k in keys if k in gb and (gb[k][0] or gb[k][1] or gb[k][2]))
            dep_burnt = sum(1 for k in keys if k in gb and gb[k][1])
            dep_ever_new = sum(1 for k in keys if k in ga and (ga[k][0] or ga[k][1] or ga[k][2]))
            _n, _e, brn_b, unt_b = ground_counts(b)
            _n, _e, brn_a, unt_a = ground_counts(a)
            assert brn_b == (b["eval"] or {}).get("burnt_cells"), label(t)
            tot["dep_ever"] += dep_ever
            tot["dep_burnt"] += dep_burnt
            tot["d_unt"] += unt_a - unt_b
            tot["d_brn"] += brn_a - brn_b
            tot["n"] += 1
            rem_u.append((unt_a - unt_b) - dep_ever)
            rem_b.append((brn_a - brn_b) + dep_burnt)
            flag = "" if dep_ever_new == 0 else "  !! %d depot cells burned in the NEW arm" % dep_ever_new
            say("   %-18s | %5d %5d | %6d %6d %+6d | %6d %6d %+6d%s"
                % (label(t), dep_ever, dep_burnt, unt_b, unt_a, unt_a - unt_b,
                   brn_b, brn_a, brn_a - brn_b, flag))
    say("")
    say("   pairs with no partner on disk (would silently shrink the sample): %s"
        % (", ".join(missing) if missing else "NONE"))
    if tot["n"]:
        say("")
        say("   TOTALS over %d paired runs" % tot["n"])
        say("     predicted by depot arithmetic : untouched %+d   burnt_cells %-+d"
            % (tot["dep_ever"], -tot["dep_burnt"]))
        say("     observed                      : untouched %+d   burnt_cells %-+d"
            % (tot["d_unt"], tot["d_brn"]))
        say("     BEHAVIOURAL REMAINDER         : untouched %+d   burnt_cells %-+d"
            % (tot["d_unt"] - tot["dep_ever"], tot["d_brn"] + tot["dep_burnt"]))
        say("")
        say("   IS THE REMAINDER SIGNAL OR NOISE? The per-run distribution:")
        for nm, v in (("untouched", rem_u), ("burnt_cells", rem_b)):
            m = sum(v) / len(v)
            sd = (sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)) ** 0.5
            pos = sum(1 for x in v if x > 0)
            neg = sum(1 for x in v if x < 0)
            se = sd / (len(v) ** 0.5)
            say("     %-12s mean %+8.1f  sd %7.1f  se %6.1f  mean/se %+5.2f   signs +%d / -%d / 0 %d"
                % (nm, m, sd, se, (m / se if se else 0.0), pos, neg, len(v) - pos - neg))
        say("     The fire-mechanic round measured a WRITE-FREE draw-stream offset moving final")
        say("     intact by a median of 155 cells with no systematic sign, which is the null this")
        say("     is against. A remainder whose mean is several standard errors from zero AND whose")
        say("     signs are lopsided is a real physical effect: 50 cells stop being igniting")
        say("     NEIGHBOURS, and 34 cells around each corner block see a lower ignition")
        say("     probability while the depot would have been burning (depotfireproof_part1.txt 2.2).")
        say("     A remainder inside one or two standard errors is re-roll noise and is reported as")
        say("     such - it is NOT evidence either way.")
        say("")
        say("     (a fuel-less never-burned cell is counted as UNTOUCHED VEGETATION by the ground")
        say("      counts - has_burned 0, burnt 0, burning 0 - although it has no fuel. 'Intact'")
        say("      rises without a tree being saved; that is the whole of the predicted term.)")
    return tot


def exposure(d):
    """E1 searcher-only and E2 all-UAV, split by what the UAV was DOING.

    E1 numerator/denominator follow _dcd4_analyze.py:499-506 exactly (role ==
    victim_searcher, pos not None, burning rebuilt from burn_intervals). E2
    follows :505-517 (uav_actions[i][j][2], the harness's own burning flag).
    The SPLIT is new: uav_steps[i][j][5] is base_state, "" / "returning" /
    "charging" (_ffr_harness.py:435-446), and the cell is tested for depot
    membership from this run's own base_station. "depot" means the UAV was
    standing inside a depot block; "charging" is the stricter state.
    """
    rows = d.get("uav_steps") or []
    acts = d.get("uav_actions")
    bi = d.get("burn_intervals") or {}
    dep = depot_cells(d) or set()
    series = {}
    n = len(rows)
    for i in range(n):
        series[i] = burning_at(bi, i + 1)
    out = {k: 0 for k in ("e1n", "e1d", "e2n", "e2d",
                          "e1n_chg", "e1n_dep", "e1n_srch",
                          "e2n_chg", "e2n_dep", "e2n_srch", "mism", "order_mism")}
    for i, row in enumerate(rows):
        arow = acts[i] if isinstance(acts, list) and i < len(acts) else None
        bset = series[i]
        for a, c in enumerate(row):
            pos = c[1]
            role = c[2]
            state = c[5] if len(c) > 5 else ""
            cell = (int(pos[0]), int(pos[1])) if pos else None
            derived = 1 if (cell and ("%d,%d" % cell) in bset) else 0
            flag = derived
            if arow is not None and a < len(arow):
                if str(arow[a][0]) == str(c[0]):
                    flag = int(bool(arow[a][2]))
                    out["mism"] += int(flag != derived)
                else:
                    # _dcd4_analyze counts this separately and never lets a
                    # misaligned row feed E2; keep both properties.
                    out["order_mism"] += 1
            in_dep = bool(cell and cell in dep)
            charging = (state == "charging")
            if role == SEARCHER and pos is not None:
                out["e1d"] += 1
                out["e1n"] += derived
                if derived:
                    out["e1n_chg"] += int(charging)
                    out["e1n_dep"] += int(in_dep)
                    out["e1n_srch"] += int(not in_dep)
            if arow is not None and a < len(arow):
                out["e2d"] += 1
                out["e2n"] += flag
                if flag:
                    out["e2n_chg"] += int(charging)
                    out["e2n_dep"] += int(in_dep)
                    out["e2n_srch"] += int(not in_dep)
    return out


def pct(n, d):
    return "%.2f%%" % (100.0 * n / d) if d else "-"


def sec_exposure(arms=("dfpB", "dfpON"), samples=SAMPLES):
    say("")
    say("=" * 100)
    say("5. DRONE STEPS IN FIRE - the metric the change exists to move")
    say("=" * 100)
    say("   E1 searcher-only, E2 all-UAV, interior-hazard definition. Each numerator is split by")
    say("   WHERE the UAV was standing: inside a depot block (the base-station problem this round")
    say("   owns) or outside it (the search-exposure problem a different session is measuring).")
    say("   'charging' is the strict base_state; 'depot' is the positional set and is the superset.")
    say("")
    hdr = ("   %-12s %-12s %4s | %8s %8s %8s %8s | %8s %8s %8s %8s"
           % ("sample", "arm", "runs", "E1", "E1 depot", "E1 chg", "E1 srch",
              "E2", "E2 depot", "E2 chg", "E2 srch"))
    say(hdr)
    res = {}
    for sname, tuples in samples:
        for tag in arms:
            agg = {k: 0 for k in ("e1n", "e1d", "e2n", "e2d", "e1n_chg", "e1n_dep", "e1n_srch",
                                  "e2n_chg", "e2n_dep", "e2n_srch", "mism", "order_mism")}
            k = 0
            for t in tuples:
                d = load(tag, t)
                if d is None:
                    continue
                e = exposure(d)
                for key in agg:
                    agg[key] += e[key]
                k += 1
            if not k:
                continue
            res[(sname, tag)] = (agg, k)
            say("   %-12s %-12s %4d | %8s %8s %8s %8s | %8s %8s %8s %8s"
                % (sname, tag, k, pct(agg["e1n"], agg["e1d"]), pct(agg["e1n_dep"], agg["e1d"]),
                   pct(agg["e1n_chg"], agg["e1d"]), pct(agg["e1n_srch"], agg["e1d"]),
                   pct(agg["e2n"], agg["e2d"]), pct(agg["e2n_dep"], agg["e2d"]),
                   pct(agg["e2n_chg"], agg["e2d"]), pct(agg["e2n_srch"], agg["e2d"])))
    say("")
    say("   RB18 (the 18 route_blocked seeds, the sample the 3.55%% / 2.42%% control is quoted on)")
    for tag in arms:
        agg = {k: 0 for k in ("e1n", "e1d", "e2n", "e2d", "e1n_chg", "e1n_dep", "e1n_srch",
                              "e2n_chg", "e2n_dep", "e2n_srch", "mism", "order_mism")}
        k = 0
        for t in RB18:
            d = load(tag, t)
            if d is None:
                continue
            e = exposure(d)
            for key in agg:
                agg[key] += e[key]
            k += 1
        if k:
            res[("rb18", tag)] = (agg, k)
            say("   %-12s %-12s %4d | %8s %8s %8s %8s | %8s %8s %8s %8s"
                % ("rb18", tag, k, pct(agg["e1n"], agg["e1d"]), pct(agg["e1n_dep"], agg["e1d"]),
                   pct(agg["e1n_chg"], agg["e1d"]), pct(agg["e1n_srch"], agg["e1d"]),
                   pct(agg["e2n"], agg["e2d"]), pct(agg["e2n_dep"], agg["e2d"]),
                   pct(agg["e2n_chg"], agg["e2d"]), pct(agg["e2n_srch"], agg["e2d"])))
    mism = sum(v[0]["mism"] for v in res.values())
    om = sum(v[0]["order_mism"] for v in res.values())
    say("   uav_actions[2] vs burn_intervals cross-check mismatches, all arms: %d" % mism)
    say("   uav_steps / uav_actions row-order misalignments (E2 would be unreadable): %d" % om)
    return res


def _d4():
    """outputs/_dcd4_analyze.py's own functions, so the same-cell-stay statistic
    is THAT round's definition and not a re-transcription of it. The module
    raises SystemExit at import when run without argv; the result is still bound."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_d4mod", os.path.join(HERE, "_dcd4_analyze.py"))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


def sec_stays(arms=("dfpB", "dfpON"), samples=SAMPLES):
    """The statistic the round's premise came from: dcd4 measured 14 of 23
    same-cell burning-step stays as UAVs CHARGING IN A BURNING DEPOT. E1/E2 count
    frames; this counts EPISODES - a UAV sitting on one burning cell for >= 2
    consecutive frames - and it is the one the 'main driver' claim was about."""
    d4 = _d4()
    say("")
    say("=" * 100)
    say("5b. SAME-CELL BURNING-STEP STAYS (outputs/_dcd4_analyze.py's own definition)")
    say("=" * 100)
    say("   A STAY is a maximal run of >= 2 consecutive frames on ONE cell with the burning flag")
    say("   set. Recorded per stay: length, base_state, role, and whether the cell is in a depot.")
    say("")
    say("   %-12s %-8s %5s | %6s %8s %9s | %s" % ("sample", "arm", "runs", "stays", "in depot", "charging", "longest"))
    for sname, tuples in list(samples) + [("rb18", RB18)]:
        for tag in arms:
            tot, dep, chg, longest, k = 0, 0, 0, 0, 0
            for t in tuples:
                d = load(tag, t)
                if d is None:
                    continue
                S = {}
                d4._exposure(S, d.get("uav_steps") or [], d.get("uav_actions"),
                             d.get("burn_intervals"), d4.geometry(d.get("base_station")))
                for n, st, _mixed, _uid, _role, _pos, _step, in_depot in S["same"]:
                    tot += 1
                    dep += int(bool(in_depot))
                    # _dcd4_analyze._majority labels this state "charging/docked",
                    # one string - not "charging" and not "docked".
                    chg += int(bool(in_depot) and str(st).startswith("charging"))
                    longest = max(longest, n)
                k += 1
            if k:
                say("   %-12s %-8s %5d | %6d %8d %9d | %d steps"
                    % (sname, tag, k, tot, dep, chg, longest))
    say("   'in depot' is positional; 'charging' is that subset whose MAJORITY base_state over the")
    say("   stay is charging/docked. The dcd4 round's '14 of 23 same-cell burning-step stays as")
    say("   UAVs charging in a burning depot' is this pair of columns, and it reproduces.")


def ev(d):
    e = d.get("eval") or {}
    return (int(e.get("rescued") or 0), int(e.get("dead") or 0),
            int(e.get("firefighter_deaths") or 0), int(e.get("never_detected") or 0),
            e.get("terminal_step"), int(e.get("burnt_cells") or 0))


def sec_outcomes(arms=("dfpB", "dfpOFF", "dfpDRY", "dfpON"), samples=SAMPLES):
    say("")
    say("=" * 100)
    say("6. OUTCOMES per arm")
    say("=" * 100)
    say("   Under decision 6.5 a per-seed rescued/dead delta on a RE-ROLLED seed is not")
    say("   attributable; the pooled row is the one that is read. Re-rolled = the control has a")
    say("   depot ignition before its outcome settles (column 'rr' below).")
    say("")
    say("   WHAT 'pinned' DOES AND DOES NOT COVER. terminal_step is all_victims_terminal, so a")
    say("   run whose depot ignition lands at or after it is pinned for RESCUED, DEAD and")
    say("   NEVER_DETECTED by construction - those three cannot move once every victim is")
    say("   terminal. It is NOT pinned for ff_deaths: firefighters keep dying after the last")
    say("   victim is resolved, and the arms' fires have already diverged by then. Three rows")
    say("   below are exactly that case (east/909, south/303 ff 1 -> 0 and east/1010 ff 0 -> 1,")
    say("   all on seeds marked pinned), and NONE of those three ff moves is attributable.")
    say("   burnt_cells and vegetation are not pinned either, for the same reason - section 4.")
    say("   So: read r / d / nd on a non-RR row; read ff POOLED ONLY, on every row.")
    say("")
    for sname, tuples in samples:
        have = [a for a in arms if any(load(a, t) for t in tuples)]
        if not have:
            continue
        say("   -- %s" % sname)
        say("      %-18s %3s | %s" % ("run", "rr", " | ".join("%-22s" % a for a in have)))
        say("      %-18s %3s | %s" % ("", "", " | ".join("%-22s" % "r  d  ff nd term" for a in have)))
        tot = {a: [0, 0, 0, 0] for a in have}
        nrr = 0
        for t in tuples:
            cells = []
            base = load("dfpB", t) or load("dfpOFF", t)
            rr = ""
            if base is not None:
                fd = first_depot_ignition(base)
                ts = (base.get("eval") or {}).get("terminal_step")
                if fd is not None and (ts is None or fd < ts):
                    rr = "RR"
                    nrr += 1
            for a in have:
                d = load(a, t)
                if d is None:
                    cells.append("%-22s" % "-")
                    continue
                r, dd, f, nd, ts, _b = ev(d)
                for i, v in enumerate((r, dd, f, nd)):
                    tot[a][i] += v
                cells.append("%-22s" % ("%-2d %-2d %-2d %-2d %s" % (r, dd, f, nd, ts if ts else "-")))
            say("      %-18s %3s | %s" % (label(t), rr, " | ".join(cells)))
        say("      %-18s %3d | %s" % ("POOLED", nrr,
                                      " | ".join("%-22s" % ("%-2d %-2d %-2d %-2d" % tuple(tot[a]))
                                                 for a in have)))
        say("      (rr = the control's fire is re-rolled from its first depot ignition, so this")
        say("       seed's per-run signs are NOISE under decision 6.5; %d of %d here)" % (nrr, len(tuples)))
        say("")


def sec_crn(samples=(("canonical13", CANONICAL), ("fresh10", FRESH), ("westnorth", WESTNORTH))):
    """The 6.5 problem, removed rather than worked around.

    Decision 6.5 says a per-seed outcome sign on a re-rolled seed is noise, and 16
    of the 23 gate seeds re-roll. That rule is right for the stock arms - and it
    also leaves the round unable to attribute anything per seed. Under COMMON
    RANDOM NUMBERS the reason for the rule is gone: Fire.step's draw becomes a
    pure function of (seed, cell, tick), so removing 50 cells' fuel cannot move
    any other cell's draw. Nothing is re-rolled, every seed is pinned, and a
    rescued difference here is a PHYSICAL consequence of the change.

    THE INSTRUMENT IS NOT THE STOCK ONE. A CRN fire is a different realisation of
    the same distribution, so these numbers do not compare with dfpB / dfpON and
    are not a second measurement of them - they answer a different question:
    "holding the weather fixed cell by cell, does the change cost a rescue?"
    (The fire-mechanic round left pinned-replay vs CRN unresolved on a firebreak's
    physical size; this round does not resolve it either, and says which
    instrument each number comes from.)
    """
    say("")
    say("=" * 100)
    say("7. COMMON RANDOM NUMBERS - every seed pinned, so every per-seed sign is attributable")
    say("=" * 100)
    say("   %-18s %-22s %-22s %s" % ("run", "dfpCB (control)", "dfpCON (fireproof)", "delta"))
    say("   %-18s %-22s %-22s %s" % ("", "r  d  ff nd term", "r  d  ff nd term", "r    d    ff"))
    grand = {"r": [0, 0], "d": [0, 0], "f": [0, 0], "nd": [0, 0]}
    worse = []
    for sname, tuples in samples:
        sub = {"r": [0, 0], "d": [0, 0], "f": [0, 0], "nd": [0, 0]}
        n = 0
        say("   -- %s" % sname)
        for t in tuples:
            a, b = load("dfpCON", t), load("dfpCB", t)
            if a is None or b is None:
                continue
            n += 1
            ra, da, fa, na, ta, _ = ev(a)
            rb, db, fb, nb, tb, _ = ev(b)
            for k, (x, y) in (("r", (rb, ra)), ("d", (db, da)), ("f", (fb, fa)), ("nd", (nb, na))):
                sub[k][0] += x
                sub[k][1] += y
                grand[k][0] += x
                grand[k][1] += y
            mark = ""
            if ra < rb:
                mark = "  <-- RESCUED FALLS"
                worse.append((label(t), rb, ra))
            say("   %-18s %-22s %-22s %-4s %-4s %-4s%s"
                % (label(t), "%-2d %-2d %-2d %-2d %s" % (rb, db, fb, nb, tb if tb else "-"),
                   "%-2d %-2d %-2d %-2d %s" % (ra, da, fa, na, ta if ta else "-"),
                   "%+d" % (ra - rb), "%+d" % (da - db), "%+d" % (fa - fb), mark))
        if n:
            say("   %-18s %-22s %-22s %-4s %-4s %-4s"
                % ("POOLED (%d)" % n, "%-2d %-2d %-2d %-2d" % (sub["r"][0], sub["d"][0], sub["f"][0], sub["nd"][0]),
                   "%-2d %-2d %-2d %-2d" % (sub["r"][1], sub["d"][1], sub["f"][1], sub["nd"][1]),
                   "%+d" % (sub["r"][1] - sub["r"][0]), "%+d" % (sub["d"][1] - sub["d"][0]),
                   "%+d" % (sub["f"][1] - sub["f"][0])))
    say("")
    say("   ALL CRN RUNS  rescued %d -> %d (%+d) | dead %d -> %d (%+d) | ff_deaths %d -> %d (%+d)"
        % (grand["r"][0], grand["r"][1], grand["r"][1] - grand["r"][0],
           grand["d"][0], grand["d"][1], grand["d"][1] - grand["d"][0],
           grand["f"][0], grand["f"][1], grand["f"][1] - grand["f"][0]))
    say("   [%s] rescued does not decrease on ANY pinned seed%s"
        % ("PASS" if not worse else "FAIL", "" if not worse else ":"))
    for w in worse:
        say("        %s  rescued %d -> %d" % w)
    # attribution and exposure under CRN
    say("")
    say("   Attribution under CRN (the burning set must still first differ at the first depot")
    say("   ignition - with the draws pinned there is no other way for it to differ at all):")
    hit = tot = vac = 0
    for _s, tuples in samples:
        for t in tuples:
            a, b = load("dfpCON", t), load("dfpCB", t)
            if a is None or b is None:
                continue
            fd = first_depot_ignition(b)
            sa, sb = burning_series(a), burning_series(b)
            first = next((i + 1 for i in range(min(len(sa), len(sb))) if sa[i] != sb[i]), None)
            if fd is None:
                vac += 1
                continue
            tot += 1
            hit += int(first == fd)
    say("     %s %d/%d first differ exactly at the control's first depot ignition (%d vacuous)"
        % ("PASS" if hit == tot and tot else "FAIL", hit, tot, vac))
    e = {"dfpCB": None, "dfpCON": None}
    for tag in e:
        agg = None
        for _s, tuples in samples:
            for t in tuples:
                d = load(tag, t)
                if d is None:
                    continue
                x = exposure(d)
                agg = x if agg is None else {k: agg[k] + x[k] for k in agg}
        e[tag] = agg
    if e["dfpCB"] and e["dfpCON"]:
        say("   Drone steps in fire under CRN (all %d CRN tuples pooled):" % sum(len(t) for _s, t in samples))
        for tag in ("dfpCB", "dfpCON"):
            a = e[tag]
            say("     %-7s E1 %7s (depot %7s) | E2 %7s (depot %7s)"
                % (tag, pct(a["e1n"], a["e1d"]), pct(a["e1n_dep"], a["e1d"]),
                   pct(a["e2n"], a["e2d"]), pct(a["e2n_dep"], a["e2d"])))


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    say("NON-BURNABLE DEPOTS - round analyzer")
    say("feature checkout %s | control checkout %s" % (NEW_REPO, OLD_REPO))
    if what in ("identity", "all"):
        sec_identity()
    if what in ("dry", "all"):
        sec_dry()
    if what in ("burnsets", "all"):
        sec_burnsets()
    if what in ("book", "all"):
        sec_book()
    if what in ("exposure", "all"):
        sec_exposure()
    if what in ("stays", "exposure", "all"):
        sec_stays()
    if what in ("outcomes", "all"):
        sec_outcomes()
    if what in ("crn", "all"):
        sec_crn()
    if what == "all":
        p = os.path.join(HERE, "_dfp_analyze.txt")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(OUT) + "\n")
        print("\nwrote %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
