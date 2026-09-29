"""fix2 Part 3 analysis - every pre-registered check (outputs/fix2_part1.txt section 9 and
outputs/fix2_part3_prereg.txt). Read-only. Prints a report; STOP lines are printed where a
pre-registered stop condition is met.

usage: _mf2_p3_analyze.py [section ...]   sections: prov ident item1 fire item2 item3 item4 item5
                                          exposure rbgate crn d9   (default: all that have data)
"""
from __future__ import annotations

import collections
import glob
import hashlib
import json
import os
import re
import statistics
import sys

REPO = r"E:\Projects\SAS"
REF = r"E:\Projects\SAS_wt\mf2_c08456b"
OUT = os.path.join(REPO, "outputs")
SW = ("GLOBAL_ANALYZER_FIRE_SOURCE_FIX", "FAILSAFE_REAL_ALARMS", "UAV_HOLD_STATIONARY",
      "SEARCHER_WIND_COVERAGE_FIX", "SEARCHER_GATE_NEAR_FIELD", "STAGGERED_LAUNCH_BATTERY")
PROBE_FIELDS = ("rows_uav", "rows_ff", "rows_vic", "rows_dec", "rows_trig", "eval", "terminal_step",
                "stdout_sha", "stdout_tags", "steps_done", "complete", "inline_violation_counts")
DET_RE = re.compile(r"^\[Victim Detection\] step=(\d+) UAV-(\S+) detected (\S+) at")
TERMINAL = {"rescued", "dead", "unreachable"}
P = print
LAUNCH_GRACE_STEPS = 20  # common_fixed_variables.py


def pct(a, b):
    return "%6.2f%%" % (100.0 * a / b) if b else "   n/a"


# ------------------------------------------------------------------------------ loading
_CACHE = {}


ALIAS = {}   # --alias mf2ALL=mf2cX: the PROBE sections read that arm's files under the aliased name
            # (probe_runs only; rbgate / CRN arms are named explicitly; do not run 'prov' with an alias -
            # use 'provc', which checks the explicit switch map)


def probe_runs(arm):
    if arm in _CACHE:
        return _CACHE[arm]
    tag = ALIAS.get(arm, arm)
    runs = {}
    for f in sorted(glob.glob(os.path.join(OUT, "_sd_%s_*.json" % tag))):
        base = os.path.basename(f)
        if ".json." in base:
            continue
        cfg = base[len("_sd_%s_" % tag):-5]
        if not re.fullmatch(r"[ABCD]_[ENSW]", cfg):
            continue
        d = json.load(open(f, encoding="utf-8"))
        st = f[:-5] + ".stdout.txt"
        det = {}
        if os.path.exists(st):
            for line in open(st, encoding="utf-8", errors="replace"):
                m = DET_RE.match(line.strip())
                if m and m.group(3) not in det:
                    det[m.group(3)] = int(m.group(1))
        d["_det"] = det
        d["_cfg"] = cfg
        runs[cfg] = d
    _CACHE[arm] = runs
    return runs


def raw_sha(path):
    """_sd_probe's own hash (raw bytes, first 16 hex): a run's src_sha equals this for the working
    tree it ran on, which is unchanged for the whole of Part 3."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


# ------------------------------------------------------------------------------ P3-0
def sec_prov(arms):
    P("=" * 100)
    P("P3-0 PROVENANCE - head, LF-normalised source hashes and the fix2 switches each run ran with")
    now = None
    for arm, want in arms.items():
        runs = probe_runs(arm)
        if not runs:
            continue
        heads = collections.Counter(str(d.get("head"))[:7] for d in runs.values())
        bad = []
        for cfg, d in runs.items():
            ss = d.get("src_sha") or {}
            if now is None:
                now = {k: raw_sha(os.path.join(REPO, k)) for k in ss}
            if any(ss[k] != now.get(k) for k in ss):
                bad.append(cfg + ":src")
            ex = d.get("extra_params") or {}
            for s in SW:
                got = ex.get(s, "shipped(1)")
                exp = want.get(s, "shipped(1)")
                if got != exp:
                    bad.append("%s:%s=%s" % (cfg, s, got))
        P("  %-7s %2d runs  heads %s  %s" % (arm, len(runs), dict(heads), "OK" if not bad else "MISMATCH %s" % bad[:6]))


# ------------------------------------------------------------------------------ P3-1
def compare_probe(a_runs, b_runs, fields=PROBE_FIELDS):
    res = {}
    for cfg in sorted(set(a_runs) & set(b_runs)):
        diffs = [k for k in fields if a_runs[cfg].get(k) != b_runs[cfg].get(k)]
        res[cfg] = diffs
    return res


def sec_ident():
    P("=" * 100)
    P("P3-1 ALL SWITCHES OFF == c08456b")
    z, ref = probe_runs("mf2Z"), probe_runs("mf1P")
    if z:
        r = compare_probe(z, ref)
        ok = sum(1 for v in r.values() if not v)
        P("  (a) probe mf2Z vs recorded mf1P (c08456b): %d/%d identical on every field %s" % (
            ok, len(r), "" if ok == len(r) else {k: v for k, v in r.items() if v}))
    hz = sorted(glob.glob(os.path.join(OUT, "_ffr_mf2hZ_*.json")))
    if hz:
        ok = tot = 0
        bad = {}
        skip = {"tag", "repo", "wall_s", "params", "extra_params"}
        for f in hz:
            g = f.replace("_ffr_mf2hZ_", "_ffr_mf2hR_")
            if not os.path.exists(g):
                continue
            a, b = json.load(open(f, encoding="utf-8")), json.load(open(g, encoding="utf-8"))
            pa = {k: v for k, v in a.get("params", {}).items() if k not in SW}
            pb = {k: v for k, v in b.get("params", {}).items() if k not in SW}
            diffs = [k for k in sorted(set(a) | set(b)) if k not in skip and a.get(k) != b.get(k)]
            if pa != pb:
                diffs.append("params(non-fix2)")
            tot += 1
            ok += int(not diffs)
            if diffs:
                bad[os.path.basename(f)] = diffs[:8]
        P("  (b) harness mf2hZ vs mf2hR (c08456b checkout): %d/%d identical on every field but tag/repo/wall_s/"
          "params %s" % (ok, tot, bad if bad else ""))
    gz = sorted(glob.glob(os.path.join(OUT, "_rblatch_camp2_mf2gZ*_D_*.json")))
    if gz:
        ok = tot = 0
        bad = {}
        for f in gz:
            tag = os.path.basename(f).split("_")[3]
            g = os.path.join(OUT, os.path.basename(f).replace("mf2gZ", "mf2gR"))
            if not os.path.exists(g):
                g = os.path.join(REF, "outputs", os.path.basename(f).replace("mf2gZ", "mf2gR"))
            if not os.path.exists(g):
                continue
            a, b = json.load(open(f, encoding="utf-8")), json.load(open(g, encoding="utf-8"))
            for x in (a, b):     # per-seed wall-clock time is run metadata (P3-1: every key but tag / wall_s)
                x["evals"] = [{k: v for k, v in e.items() if k != "wall_s"} for e in (x.get("evals") or [])]
            diffs = [k for k in sorted(set(a) | set(b)) if k not in ("tag", "params") and a.get(k) != b.get(k)]
            pa = {k: v for k, v in a.get("params", {}).items() if k not in SW}
            pb = {k: v for k, v in b.get("params", {}).items() if k not in SW}
            if pa != pb:
                diffs.append("params(non-fix2)")
            tot += 1
            ok += int(not diffs)
            if diffs:
                bad[tag] = diffs
        P("  (c) rbgate mf2gZ vs mf2gR: %d/%d shards identical on every key but tag/params %s" % (ok, tot, bad if bad else ""))
    a4, k = probe_runs("mf2A4"), probe_runs("mf2K")
    if a4 and k:
        r = compare_probe(a4, k)
        ok = sum(1 for v in r.values() if not v)
        P("  (d) mf2A4 (final commit) vs mf2K (checkpoint): %d/%d identical %s" % (
            ok, len(r), "" if ok == len(r) else {k2: v for k2, v in r.items() if v}))


# ------------------------------------------------------------------------------ helpers over rows
def mode_shares(runs):
    c = collections.Counter()
    n = 0
    for d in runs.values():
        for r in d["rows_dec"]:
            c[r.get("mode")] += 1
            n += 1
    return c, n


def reason_shares(runs):
    c = collections.Counter()
    n = 0
    for d in runs.values():
        for r in d["rows_dec"]:
            n += 1
            for w in r.get("why") or ():
                c[w] += 1
    return c, n


def alarm_rates(runs):
    """D-2: each alarm's firing, separately. Local alarms per UAV-step (analysis instances / UAV-steps),
    global ones per step. From the analysis snapshot's trigger list (rows_trig: all scopes) and, when
    present, the mf2 per-scope counts."""
    out = collections.Counter()
    steps = uav_steps = 0
    for d in runs.values():
        n_uav = len(d["rows_uav"][0]) if d["rows_uav"] else 0
        m = d.get("mf2") or {}
        fleet = m.get("fleet") or []
        for t, row in enumerate(d["rows_trig"]):
            steps += 1
            uav_steps += n_uav
            if t < len(fleet) and isinstance(fleet[t], list) and len(fleet[t]) >= 4 and isinstance(fleet[t][3], dict):
                for key, v in fleet[t][3].items():
                    out[key] += v
                    out[key + "#steps"] += 1
            else:
                for key in ("COLLISION_RISK", "DRIFT_TOO_HIGH", "CRITICAL_LINK_UNRELIABLE", "SEARCH_MODE_REQUIRED"):
                    if row.get(key):
                        out[key + "|all"] += row[key]
                        out[key + "|all#steps"] += 1
    return out, steps, uav_steps


def refused_windows(d):
    """Per step t (0-based row), per uid: number of refused moves among the UAV's last 5 move outcomes
    up to and including row t (mf2 uav rows)."""
    hist = collections.defaultdict(list)
    out = []
    for row in (d.get("mf2") or {}).get("uav") or []:
        cur = {}
        for u in row:
            uid, cls = u[0], u[3]
            hist[uid].append(1 if cls in ("refused_occupied", "refused_oob") else 0)
            cur[uid] = sum(hist[uid][-5:])
        out.append(cur)
    return out


def airborne_close(prev_row, radius=2):
    """UAV ids that are airborne (not docked) with another airborne UAV within `radius` (rows_uav)."""
    air = [(u[0], u[1], u[2]) for u in prev_row if not u[6] and u[1] is not None]
    close = set()
    for i, (a, ax, ay) in enumerate(air):
        for b, bx, by in air:
            if a != b and abs(ax - bx) + abs(ay - by) <= radius:
                close.add(a)
    return close


# ------------------------------------------------------------------------------ P3-3 item 1
def sec_item1():
    P("=" * 100)
    P("P3-3 ITEM 1 - THE FAIL-SAFE MODE AND THE FOUR ALARMS (D-2: each alarm separately, before/after)")
    for arm in ("mf1P", "mf2Z", "mf2A1", "mf2ALL"):
        runs = probe_runs(arm)
        if not runs:
            continue
        c, n = mode_shares(runs)
        rs, _ = reason_shares(runs)
        P("  %-7s %2d runs %5d steps  modes: %s" % (arm, len(runs), n, "  ".join(
            "%s %s" % (k, pct(v, n)) for k, v in c.most_common())))
        P("          reasons (share of steps): %s" % "  ".join("%s %s" % (k, pct(v, n)) for k, v in rs.most_common()))
        ar, steps, uav_steps = alarm_rates(runs)
        for key in ("COLLISION_RISK|local", "DRIFT_TOO_HIGH|local", "DRIFT_TOO_HIGH|global",
                    "CRITICAL_LINK_UNRELIABLE|global", "SEARCH_MODE_REQUIRED|local", "SEARCH_MODE_REQUIRED|global",
                    "COLLISION_RISK|all", "DRIFT_TOO_HIGH|all", "CRITICAL_LINK_UNRELIABLE|all",
                    "SEARCH_MODE_REQUIRED|all"):
            if key in ar:
                denom = uav_steps if key.endswith("|local") else steps
                P("          %-32s instances %6d (%s of %s)  steps with any %s" % (
                    key, ar[key], pct(ar[key], denom), "UAV-steps" if key.endswith("|local") else "steps",
                    pct(ar[key + "#steps"], steps)))
    # the invariants on mf2A1 and mf2ALL, per NAMED UAV (the probe records each alarm's affected ids).
    # The alarms of step t come from the pre-move analysis, i.e. positions / dock states at the end of
    # step t-1 = rows_uav[t-1], and the move outcomes of steps <= t-1 = mf2 uav rows [.. t-1].
    for arm in ("mf2A1", "mf2ALL"):
        runs = probe_runs(arm)
        if not runs:
            continue
        cnt = collections.Counter()
        for d in runs.values():
            fleet = (d.get("mf2") or {}).get("fleet") or []
            wins = refused_windows(d)
            for t in range(1, len(d["rows_dec"])):
                if t >= len(fleet) or not isinstance(fleet[t], list) or len(fleet[t]) < 6:
                    cnt["no_record"] += 1
                    continue
                counts, noop, named = fleet[t][3], fleet[t][4], fleet[t][5]
                cnt["steps"] += 1
                prev = {u[0]: u for u in d["rows_uav"][t - 1]}
                real = airborne_close(d["rows_uav"][t - 1])
                # (iv)
                for uid in named.get("COLLISION_RISK|local", ()):
                    cnt["coll_named"] += 1
                    if uid not in real:
                        cnt["coll_VIOL"] += 1
                # the model drops every COLLISION_RISK while evaluation_timesteps_counter <
                # LAUNCH_GRACE_STEPS (20; wildfire_model.py _run_analysis) - missed counts from step 20
                if t + 1 >= LAUNCH_GRACE_STEPS:
                    cnt["coll_missed"] += len(real - set(named.get("COLLISION_RISK|local", ())))
                    cnt["coll_real"] += len(real)
                cnt["coll_global"] += counts.get("COLLISION_RISK|global", 0)
                # (v)
                win = wins[t - 1] if t - 1 < len(wins) else {}
                for key in ("DRIFT_TOO_HIGH|local", "DRIFT_TOO_HIGH|global"):
                    for uid in named.get(key, ()):
                        cnt["drift_named"] += 1
                        p = prev.get(uid)
                        if win.get(uid, 0) < 2:
                            cnt["drift_VIOL_window"] += 1
                        if p is not None and p[6]:
                            cnt["drift_VIOL_docked"] += 1
                cnt["drift_missed"] += len({u for u, v in win.items() if v >= 2}
                                           - set(named.get("DRIFT_TOO_HIGH|local", ())))
                # (iii)
                if counts.get("CRITICAL_LINK_UNRELIABLE|global", 0) or counts.get("CRITICAL_LINK_UNRELIABLE|local", 0):
                    cnt["link_VIOL_steps"] += 1
                # (vi)
                g = named.get("SEARCH_MODE_REQUIRED|global", ())
                cnt["search_global_other"] += sum(1 for x in g if x != "FLEET_FIRE_LOST")
                why = d["rows_dec"][t].get("why") or ()
                if "search_mode_required" in why:
                    cnt["search_reason_steps"] += 1
                    if "FLEET_FIRE_LOST" not in g:
                        cnt["search_VIOL"] += 1
                # (vii)
                if d["rows_dec"][t].get("mode") == "normal":
                    cnt["normal_steps"] += 1
                    if noop != 1:
                        cnt["noop_VIOL"] += 1
        P("  %s invariants over %d steps (%d without a record):" % (arm, cnt["steps"], cnt["no_record"]))
        P("    (iii) steps with CRITICAL_LINK_UNRELIABLE: %d" % cnt["link_VIOL_steps"])
        P("    (iv)  COLLISION_RISK|local named %d, naming a UAV without an airborne UAV within 2: %d VIOLATIONS;"
          " from step 20 (launch grace), real-condition UAV-steps %d, not named (reported) %d;"
          " COLLISION_RISK|global (same cell) %d" % (
              cnt["coll_named"], cnt["coll_VIOL"], cnt["coll_real"], cnt["coll_missed"], cnt["coll_global"]))
        P("    (v)   DRIFT_TOO_HIGH named %d, naming a UAV refused on < 2 of its last 5 moves: %d VIOLATIONS; naming"
          " a docked UAV: %d VIOLATIONS; qualifying UAVs not named (reported) %d" % (
              cnt["drift_named"], cnt["drift_VIOL_window"], cnt["drift_VIOL_docked"], cnt["drift_missed"]))
        P("    (vi)  steps with the reason search_mode_required %d, without a FLEET_FIRE_LOST trigger: %d VIOLATIONS;"
          " global SEARCH_MODE_REQUIRED not from FLEET_FIRE_LOST %d" % (
              cnt["search_reason_steps"], cnt["search_VIOL"], cnt["search_global_other"]))
        P("    (vii) normal steps %d, without the no-op fail-safe decision: %d VIOLATIONS" % (
            cnt["normal_steps"], cnt["noop_VIOL"]))


def sec_fire():
    P("=" * 100)
    P("P3-3B FIRE SOURCE - trigger types that fire (share of steps) in mf2Z / mf2FS / mf2ALL")
    types = ("HIGH_PRIORITY_FIRE_REGION", "STALE_HIGH_PRIORITY_REGION", "FIRE_SPREAD_ACCELERATING",
             "FIRE_DIRECTION_SHIFT", "POOR_FIRE_COVERAGE", "TREND_WORSENING", "TREND_IMPROVING")
    base = {}
    for arm in ("mf2Z", "mf2FS", "mf2ALL"):
        runs = probe_runs(arm)
        if not runs:
            continue
        c = collections.Counter()
        n = 0
        allt = set()
        for d in runs.values():
            for row in d["rows_trig"]:
                n += 1
                allt.update(row)
                for k in row:
                    c[k] += 1
        base[arm] = (c, n, allt)
        P("  %-7s %s" % (arm, "  ".join("%s %s" % (t, pct(c[t], n)) for t in types)))
    if "mf2Z" in base and "mf2FS" in base:
        z, fs = probe_runs("mf2Z"), probe_runs("mf2FS")
        same = sum(1 for cfg in fs if cfg in z and [r.get("mode") for r in fs[cfg]["rows_dec"]]
                   == [r.get("mode") for r in z[cfg]["rows_dec"]])
        firstdiff = {}
        for cfg in fs:
            if cfg in z:
                for t, (a, b) in enumerate(zip(fs[cfg]["rows_uav"], z[cfg]["rows_uav"])):
                    if a != b:
                        firstdiff[cfg] = t + 1
                        break
        P("  mf2FS vs mf2Z: fail-safe mode identical per step in %d/%d runs; first differing UAV row per run %s" % (
            same, len(fs), firstdiff))
        allz = base["mf2Z"][2]
        P("  types that fire in mf2FS and never in mf2Z: %s" % sorted(base["mf2FS"][2] - allz))


# ------------------------------------------------------------------------------ P3-4 item 2
def sec_item2():
    P("=" * 100)
    P("P3-4 ITEM 2 - HOLDS THAT MOVE; STAYS; YIELDS (the yield of step t is decided on the positions of"
      " row t-1; returning / docked UAVs excluded from the hold counts)")
    for arm in ("mf1P", "mf2Z", "mf2A2", "mf2ALL"):
        runs = probe_runs(arm)
        if not runs:
            continue
        c = collections.Counter()
        by_mode = collections.Counter()
        y_act = collections.Counter()
        stays = stay_moved = yields = y_bad = y_long = y_moved = 0
        for d in runs.values():
            rows = d["rows_uav"]
            m = (d.get("mf2") or {}).get("uav") or []
            streak = collections.Counter()
            for t in range(1, len(rows)):
                prev = {u[0]: u for u in rows[t - 1]}
                ylist = {mu[0] for mu in (m[t] if t < len(m) else ()) if mu[9] == 1}
                mode = (d["rows_dec"][t] if t < len(d["rows_dec"]) else {}).get("mode")
                for u in rows[t]:
                    uid, x, y, role, bat, rtb, dock, berth, act = u
                    p = prev.get(uid)
                    if p is None or rtb or dock:
                        continue
                    moved = (x, y) != (p[1], p[2])
                    if act in ("hold", "fire_flank_hold"):
                        c[(act, moved)] += 1
                    if act == "hold":
                        # review R9: with item 1 the fleet is mostly in normal mode, so a 'hold'
                        # there is the UAV's own planner's, and now stationary
                        by_mode[(mode, "yield" if uid in ylist else "planner", "moved" if moved else "stayed")] += 1
                if t < len(m):
                    for mu in m[t]:
                        uid = mu[0]
                        p = prev.get(uid)
                        cur = next((u for u in rows[t] if u[0] == uid), None)
                        if mu[2] == 1:
                            stays += 1
                            if p is not None and cur is not None and (cur[1], cur[2]) != (p[1], p[2]) and not cur[5]:
                                stay_moved += 1
                        if mu[9] == 1:
                            yields += 1
                            streak[uid] += 1
                            if streak[uid] > 3:
                                y_long += 1
                            if cur is not None:
                                y_act[cur[8]] += 1
                                if p is not None and (cur[1], cur[2]) != (p[1], p[2]):
                                    y_moved += 1       # review R6: a yield that escapes moves
                            me = p
                            if me is None or me[5] or me[6]:
                                y_bad += 1
                            else:
                                lower = any(int(o[0]) < int(uid) and not o[6] and not o[5] and
                                            abs(o[1] - me[1]) + abs(o[2] - me[2]) <= 2 for o in rows[t - 1] if o[0] != uid)
                                if not lower:
                                    y_bad += 1
                        else:
                            streak[uid] = 0
        P("  %-7s hold %d moved %d | fire_flank_hold %d moved %d | stay steps %d moved %d | yields %d "
          "(violations: not a lower-id airborne non-returning pair, or the yielder returning/docked %d;"
          " > 3 in a row %d) | yields that moved %d, executed as %s" % (
              arm, c[("hold", True)] + c[("hold", False)], c[("hold", True)],
              c[("fire_flank_hold", True)] + c[("fire_flank_hold", False)], c[("fire_flank_hold", True)],
              stays, stay_moved, yields, y_bad, y_long, y_moved, dict(y_act.most_common(6))))
        P("          'hold' by (mode, source, outcome): %s" % dict(by_mode.most_common(12)))


# ------------------------------------------------------------------------------ oscillation / episodes
def oscillations(d, window=10):
    """Per UAV, windows of `window` frames on <= 2 distinct cells with >= 2 cell changes, outside return
    legs and docking, before the terminal step (dockfix-livelock-gate definition). Counted by kind:
    'flank' when every frame's action is the lateral patrol step (fire_flank_hold, D-4 - back and forth
    by design), 'hold' when any frame is a 'hold', else 'other'."""
    rows = d["rows_uav"]
    term = d.get("terminal_step") or len(rows)
    per = collections.defaultdict(list)
    for t, row in enumerate(rows[:term]):
        for u in row:
            per[u[0]].append((u[1], u[2], u[5] or u[6], u[8]))
    out = collections.Counter()
    for uid, seq in per.items():
        t = 0
        while t + window <= len(seq):
            w = seq[t:t + window]
            if not any(r for _, _, r, _ in w):
                cells = {(x, y) for x, y, _, _ in w}
                changes = sum(1 for i in range(1, window) if w[i][:2] != w[i - 1][:2])
                if len(cells) <= 2 and changes >= 2:
                    acts = [a for _, _, _, a in w]
                    kind = ("flank" if all("fire_flank" in a for a in acts)
                            else "hold" if any(a == "hold" for a in acts) else "other")
                    out[kind] += 1
                    t += window
                    continue
            t += 1
    return out


def sec_osc():
    P("=" * 100)
    P("P3-4 / P3-9 OSCILLATION WINDOWS (10 frames, <= 2 cells, >= 2 changes; not returning / docked; before"
      " the terminal step) - per arm against mf2Z on the same configurations")
    z = probe_runs("mf2Z")
    for arm in ("mf1P", "mf2A1", "mf2A2", "mf2A3a", "mf2A3b", "mf2A4", "mf2FS", "mf2ALL"):
        runs = probe_runs(arm)
        common = sorted(set(runs) & set(z))
        if not common:
            continue
        a = collections.Counter()
        b = collections.Counter()
        worse = []
        for c in common:
            oa, ob = oscillations(runs[c]), oscillations(z[c])
            a += oa
            b += ob
            if oa["hold"] + oa["other"] > ob["hold"] + ob["other"]:
                worse.append((c, dict(ob), dict(oa)))
        P("  %-7s vs mf2Z (%2d configs): %s vs %s | configs with more non-flank windows: %s" % (
            arm, len(common), dict(a), dict(b), worse[:8]))


# ------------------------------------------------------------------------------ P3-5 item 3
def sec_item3():
    P("=" * 100)
    P("P3-5 ITEM 3 - WIND SEARCH, THE B/WEST LOOP, THE GATE")
    for arm in ("mf2Z", "mf2A3a", "mf2A3b", "mf2ALL"):
        runs = probe_runs(arm)
        if not runs:
            continue
        viol = upwind_commits = latch_viol = 0
        far = gate_calls = replaced = 0
        for d in runs.values():
            m = d.get("mf2") or {}
            g = m.get("gate") or {}
            far += g.get("replaced_far", 0)
            gate_calls += g.get("calls", 0)
            replaced += g.get("replaced", 0)
            wind = d.get("wind")
            if wind not in ("north", "south"):
                continue
            reached = collections.defaultdict(bool)
            last = {}
            for srow in m.get("search") or []:
                for uid, commit, n_done, s_done, w_done, e_done, lw, y in srow:
                    if y is not None and ((wind == "north" and y >= 43) or (wind == "south" and y <= 6)):
                        reached[uid] = True
                    up = "south" if wind == "north" else "north"
                    down_latch = n_done if wind == "north" else s_done
                    if commit == up and last.get(uid) != up:
                        upwind_commits += 1
                        if not reached[uid]:
                            viol += 1
                        if not down_latch:
                            latch_viol += 1      # the pre-registered form (latch recorded when 3a is on)
                    last[uid] = commit
        P("  %-7s N/S upwind commits %d, of them BEFORE the downwind strip was reached (position) %d, with the"
          " downwind latch unset %s | gate calls %d replaced %d replaced far (> 6 from hazard) %d" % (
              arm, upwind_commits, viol, latch_viol if arm in ("mf2A3a", "mf2ALL") else "n/a (no latch)",
              gate_calls, replaced, far))
    for arm in ("mf2Z", "mf2A3b", "mf2ALL"):
        d = probe_runs(arm).get("B_W")
        if d is None:
            continue
        rows = d["rows_uav"]
        per = []
        for t, row in enumerate(rows):
            for u in row:
                if u[3] == "victim_searcher" and not u[5] and not u[6]:
                    per.append((t + 1, u[1], u[2]))
        edge = [p for p in per if p[1] >= 44]
        loop = 0
        for i in range(0, len(per) - 30):
            w = per[i:i + 30]
            cells = {(x, y) for _, x, y in w}
            ch = sum(1 for j in range(1, 30) if (w[j][1], w[j][2]) != (w[j - 1][1], w[j - 1][2]))
            if len(cells) <= 3 and ch >= 8 and all(x >= 43 for _, x, _ in w):
                loop += 1
        P("  B/west %-7s searcher steps at x >= 44: %d; 30-step east-edge 2-cycle windows: %d; never_detected %s" % (
            arm, len(edge), loop, (d.get("eval") or {}).get("never_detected")))
    for arm in ("mf2Z", "mf2A3a", "mf2A3b", "mf2ALL"):
        runs = probe_runs(arm)
        if not runs:
            continue
        cells = set()
        dets = []
        for d in runs.values():
            for row in d["rows_uav"]:
                for u in row:
                    if u[3] == "victim_searcher":
                        cells.add((d["_cfg"], u[1], u[2]))
            dets += list(d["_det"].values())
        P("  %-7s searcher cells covered %d; victims first detected %d, median first-detection step %s" % (
            arm, len(cells), len(dets), statistics.median(dets) if dets else None))


# ------------------------------------------------------------------------------ P3-6 / P3-7 item 4 / item 5
def gap_stats(d):
    rows_u, rows_v, det = d["rows_uav"], d["rows_vic"], d["_det"]
    gap = und = whole = 0
    flying_s = retleg_s = dock_s = retleg_all = dock_all = 0
    returns = collections.Counter()
    prev_rtb = {}
    for t, row in enumerate(rows_u):
        s = [u for u in row if u[3] == "victim_searcher"]
        fly = [u for u in s if not u[5] and not u[6]]
        if s and not fly:
            gap += 1
            vrow = rows_v[t]
            if any((v[4] or v[3]) not in TERMINAL and det.get(v[0], 10 ** 9) > t + 1 for v in vrow):
                und += 1
        if row and all(u[5] or u[6] for u in row):
            whole += 1
        flying_s += len(fly)
        for u in row:
            if u[5] and not u[6]:
                retleg_all += 1
                if u[3] == "victim_searcher":
                    retleg_s += 1
            if u[6]:
                dock_all += 1
                if u[3] == "victim_searcher":
                    dock_s += 1
            if u[5] and not prev_rtb.get(u[0]):
                returns[u[0]] += 1
            prev_rtb[u[0]] = bool(u[5])
    return {"gap": gap, "gap_undetected": und, "whole_out": whole, "searcher_flying": flying_s,
            "searcher_return_leg": retleg_s, "searcher_docked": dock_s, "return_leg_all": retleg_all,
            "docked_all": dock_all, "returns": sum(returns.values()),
            "never_detected": (d.get("eval") or {}).get("never_detected"),
            "rescued": (d.get("eval") or {}).get("rescued"), "dead": (d.get("eval") or {}).get("dead")}


def mean_excess(runs, cfgs):
    tot = n = 0
    for c in cfgs:
        for e in leg_excess(runs[c]):
            tot += e
            n += 1
    return "%.2f (%d legs)" % (tot / n, n) if n else "n/a"


def leg_excess(d):
    """Excess of every completed return leg: steps from the leg's first frame to docking minus the
    Manhattan distance from the leg's first cell to its berth."""
    out = []
    open_ = {}
    for t, row in enumerate(d["rows_uav"]):
        for u in row:
            uid, x, y, role, bat, rtb, dock, berth, act = u
            if rtb and not dock and uid not in open_:
                open_[uid] = (t + 1, (x, y), berth)
            elif dock and uid in open_:
                s0, c0, b = open_.pop(uid)
                if b is not None:
                    out.append((t + 1 - s0) - (abs(c0[0] - b[0]) + abs(c0[1] - b[1])))
    return out


def standoffs(d):
    rows = d["rows_uav"]
    depot = {tuple(c) for c in ((d.get("depots") or {}).get("cells") or [])}
    legs = {}
    worst = []
    for t, row in enumerate(rows):
        for u in row:
            uid, x, y, role, bat, rtb, dock, berth, act = u
            L = legs.setdefault(uid, [])
            if rtb and not dock:
                if not L or L[-1].get("done"):
                    L.append({"start": t + 1, "cell": (x, y), "berth": berth, "path": [(x, y)]})
                else:
                    L[-1]["path"].append((x, y))
            elif dock and L and not L[-1].get("done"):
                L[-1]["done"] = t + 1
    n_legs = 0
    for uid, L in legs.items():
        for leg in L:
            if leg["berth"] is None:
                continue
            n_legs += 1
            b = leg["berth"]
            d0 = abs(leg["cell"][0] - b[0]) + abs(leg["cell"][1] - b[1])
            if leg.get("done"):
                ex = (leg["done"] - leg["start"]) - d0
            else:
                # a leg still open at the horizon: steps spent minus the progress made (the P2-5
                # checkpoint counted completed legs only and could not see one of these)
                last = leg["path"][-1]
                ex = (len(rows) - leg["start"]) - (d0 - (abs(last[0] - b[0]) + abs(last[1] - b[1])))
            run = best = 0
            prev = None
            for c in leg["path"]:
                near = c not in depot and any(abs(c[0] - q[0]) + abs(c[1] - q[1]) == 1 for q in depot)
                run = run + 1 if (c == prev and near) else 0
                best = max(best, run)
                prev = c
            if ex >= 10 or best >= 5:
                worst.append((uid, leg["start"], ex, best, "done" if leg.get("done") else "OPEN at horizon"))
    return n_legs, worst


def sec_item4(pairs=(("mf1P", "mf2K"), ("mf2Z", "mf2A4"), ("mf2Z", "mf2ALL"), ("mf2Z", "mf2cK"),
                    ("mf2Z", "mf2cX"), ("mf2cX", "mf2cS"))):
    P("=" * 100)
    P("P3-6 ITEM 4 - THE NO-SEARCHER GAP (per scenario, summed over its runs) and P3-7 ITEM 5 standoffs")
    for base, arm in pairs:
        A, B = probe_runs(base), probe_runs(arm)
        common = sorted(set(A) & set(B))
        if not common:
            continue
        P("  %s -> %s (%d paired runs)" % (base, arm, len(common)))
        for sc in "ABCD":
            ra = [gap_stats(A[c]) for c in common if c.startswith(sc)]
            rb = [gap_stats(B[c]) for c in common if c.startswith(sc)]
            if not ra:
                continue
            s = lambda rs, k: sum((r[k] or 0) for r in rs)
            P("    %s  gap %4d -> %4d | with alive undetected %3d -> %3d | whole-fleet-out %3d -> %3d | searcher flying"
              " %5d -> %5d | searcher return-leg %4d -> %4d, docked %4d -> %4d | all-UAV return-leg %4d -> %4d | "
              "returns %2d -> %2d | never_detected %d -> %d | rescued %d -> %d | dead %d -> %d" % (
                  sc, s(ra, "gap"), s(rb, "gap"), s(ra, "gap_undetected"), s(rb, "gap_undetected"),
                  s(ra, "whole_out"), s(rb, "whole_out"), s(ra, "searcher_flying"), s(rb, "searcher_flying"),
                  s(ra, "searcher_return_leg"), s(rb, "searcher_return_leg"), s(ra, "searcher_docked"),
                  s(rb, "searcher_docked"), s(ra, "return_leg_all"), s(rb, "return_leg_all"),
                  s(ra, "returns"), s(rb, "returns"), s(ra, "never_detected"), s(rb, "never_detected"),
                  s(ra, "rescued"), s(rb, "rescued"), s(ra, "dead"), s(rb, "dead")))
        tot_legs = 0
        allw = []
        for c in common:
            n, w = standoffs(B[c])
            tot_legs += n
            allw += [(c,) + x for x in w]
        P("    standoffs in %s (excess >= 10 or outside-depot wait >= 5): %d of %d legs %s | mean excess"
          " per leg %s -> %s (review R3: a yield in front of a return leg shows here)" % (
              arm, len(allw), tot_legs, allw[:6], mean_excess(A, common), mean_excess(B, common)))


def sec_d9():
    """P3-13: STOP if C > G in C or D, or C > 5% of the baseline searcher flying steps in A or B."""
    P("=" * 100)
    P("P3-13 D-9 CONDITION - the stagger's cost (searcher flying steps lost, C) against its gain (gap closed, G)")
    for base, arm in (("mf1P", "mf2K"), ("mf2Z", "mf2A4")):
        A, B = probe_runs(base), probe_runs(arm)
        common = sorted(set(A) & set(B))
        if not common:
            continue
        for sc in "ABCD":
            ra = [gap_stats(A[c]) for c in common if c.startswith(sc)]
            rb = [gap_stats(B[c]) for c in common if c.startswith(sc)]
            if not ra:
                continue
            G = sum(r["gap"] for r in ra) - sum(r["gap"] for r in rb)
            base_fly = sum(r["searcher_flying"] for r in ra)
            C = base_fly - sum(r["searcher_flying"] for r in rb)
            if sc in "CD":
                stop = C > G
                rule = "C > G"
            else:
                stop = C > 0.05 * base_fly
                rule = "C > 5%% of %d" % base_fly
            P("  %s -> %s  %s: G = %d gap steps closed, C = %d searcher flying steps lost (%s)  %s" % (
                base, arm, sc, G, C, rule, "STOP" if stop else "ok"))


# ------------------------------------------------------------------------------ P3-8 exposure
def exposure(runs):
    b_s = b_a = s_s = s_a = n_s = n_a = 0
    for d in runs.values():
        for row in (d.get("mf2") or {}).get("uav") or []:
            for u in row:
                n_a += 1
                b_a += u[4]
                s_a += u[5]
                if u[1] == "victim_searcher":
                    n_s += 1
                    b_s += u[4]
                    s_s += u[5]
    return b_s, n_s, b_a, n_a, s_s, s_a


def sec_exposure():
    P("=" * 100)
    P("P3-8 DRONE STEPS IN FIRE (burning cell) - searcher-only and all-UAV; smoke separately")
    base = None
    for arm in ("mf2Z", "mf2A3b", "mf2A1", "mf2A2", "mf2A3a", "mf2A4", "mf2FS", "mf2ALL"):
        runs = probe_runs(arm)
        if not runs:
            continue
        b_s, n_s, b_a, n_a, s_s, s_a = exposure(runs)
        P("  %-7s searcher %s (%d of %d) all-UAV %s (%d of %d) | smoke: searcher %s all %s" % (
            arm, pct(b_s, n_s), b_s, n_s, pct(b_a, n_a), b_a, n_a, pct(s_s, n_s), pct(s_a, n_a)))
    # the P3-8 bound compares against the all-off arm on the SAME configurations
    z = probe_runs("mf2Z")
    for arm in ("mf2A3b", "mf2ALL"):
        runs = probe_runs(arm)
        if not runs or not z:
            continue
        sub = {c: z[c] for c in runs if c in z}
        zb_s, zn_s, zb_a, zn_a, _, _ = exposure(sub)
        b_s, n_s, b_a, n_a, _, _ = exposure(runs)
        ds = 100.0 * (b_s / n_s - zb_s / zn_s) if n_s and zn_s else 0.0
        da = 100.0 * (b_a / n_a - zb_a / zn_a) if n_a and zn_a else 0.0
        P("  %s vs mf2Z (same %d configs): searcher %+.2f points (bound +1.0), all-UAV %+.2f points (bound +0.5)  %s" % (
            arm, len(sub), ds, da, "FINDING" if (ds > 1.0 or da > 0.5) else "within bounds"))


# ------------------------------------------------------------------------------ P3-10 rbgate
def sec_rbgate(arms=(("mf2gS", "all on, EVEN stagger (b8581db)"), ("mf2gC", "all on, COMPACT stagger"),
                     ("mf2gX", "all on but item 4"), ("mf2gY", "all on but item 4, STATIONARY_YIELD_FIX"),
                     ("mf2gM", "all on but items 4 and 2 (the moving hold)"))):
    for arm, label in arms:
        _rbgate_arm(arm, label)


def _rbgate_arm(arm, label):
    P("=" * 100)
    P("P3-10 ROUTE_BLOCKED GATE - %s (%s) vs mf2gZ (all off); known losses east/707, south/101, 202, 404" % (arm, label))
    pooled = collections.Counter()
    for sh, w in (("a", "east"), ("b", "east"), ("c", "east"), ("s", "south")):
        fz = os.path.join(OUT, "_rblatch_camp2_mf2gZ%s_D_%s.json" % (sh, w))
        fs = os.path.join(OUT, "_rblatch_camp2_%s%s_D_%s.json" % (arm, sh, w))
        if not (os.path.exists(fz) and os.path.exists(fs)):
            P("  shard %s %-5s MISSING" % (sh, w))
            continue
        z, s = json.load(open(fz, encoding="utf-8")), json.load(open(fs, encoding="utf-8"))
        ez = {int(e["seed"]): e for e in (z.get("evals") or [])}
        es = {int(e["seed"]): e for e in (s.get("evals") or [])}
        known = {("east", 707), ("south", 101), ("south", 202), ("south", 404)}
        loss, gain, new = [], [], []
        for seed in sorted(set(ez) & set(es)):
            rz, rs = ez[seed].get("rescued"), es[seed].get("rescued")
            if rs < rz:
                loss.append((seed, rz, rs))
                if (w, seed) not in known:
                    new.append(seed)
            elif rs > rz:
                gain.append((seed, rz, rs))
        dz = sum(int(e.get("dead", 0)) for e in ez.values())
        ds = sum(int(e.get("dead", 0)) for e in es.values())
        P("  shard %s %-5s seeds %s | rescued off %d shipped %d | dead off %d shipped %d | losses %s gains %s | NEW"
          " losses %s | recoveries off %d shipped %d | latched at end shipped %d  %s" % (
              sh, w, sorted(es), sum(e["rescued"] for e in ez.values()), sum(e["rescued"] for e in es.values()),
              dz, ds, loss, gain, new or "none", len(z.get("recoveries") or []), len(s.get("recoveries") or []),
              len(s.get("latched") or []), "NEW LOSS" if new else ("LATCHED" if (s.get("latched") or []) else "ok")))
        pooled["new"] += len(new)
        pooled["rec_off"] += len(z.get("recoveries") or [])
        pooled["rec_on"] += len(s.get("recoveries") or [])
        pooled["latched"] += len(s.get("latched") or [])
        pooled["resc_off"] += sum(e["rescued"] for e in ez.values())
        pooled["resc_on"] += sum(e["rescued"] for e in es.values())
    # the pre-registered P3-10 rule, pooled over the 18 seeds: no NEW loss, recoveries > 0, 0 latched
    P("  POOLED: rescued %d -> %d | NEW losses %d | recoveries %d -> %d (> 0 required) | latched at end %d  => %s" % (
        pooled["resc_off"], pooled["resc_on"], pooled["new"], pooled["rec_off"], pooled["rec_on"], pooled["latched"],
        "PASS" if (pooled["new"] == 0 and pooled["rec_on"] > 0 and pooled["latched"] == 0) else "FAIL"))


# ------------------------------------------------------------------------------ P3-12 CRN D-7
def crn_arm(arm):
    out = {}
    for f in sorted(glob.glob(os.path.join(OUT, "_ffr_%s_*.json" % arm))):
        if ".json." in os.path.basename(f):
            continue
        d = json.load(open(f, encoding="utf-8"))
        key = os.path.basename(f)[len("_ffr_%s_" % arm):-5]
        steps_rows = d.get("uav_steps") or []
        b_s = n_s = b_a = n_a = s_a = 0
        for i, row in enumerate(d.get("uav_actions") or []):
            # the role of each UAV at this step: uav_steps[i] = [uid, [x, y], role, ...] (same frame)
            role = {str(r[0]): r[2] for r in (steps_rows[i] if i < len(steps_rows) else ())}
            for uid, act, burning, vsm, asm, fdist in row:
                is_s = role.get(str(uid)) == "victim_searcher"
                n_a += 1
                b_a += burning
                s_a += int(bool(vsm or asm))
                if is_s:
                    n_s += 1
                    b_s += burning
        ev = d.get("eval") or {}
        out[key] = {"dead": ev.get("dead", 0), "rescued": ev.get("rescued", 0), "b_s": b_s, "n_s": n_s,
                    "b_a": b_a, "n_a": n_a, "smoke": s_a, "crn": bool((d.get("extra_params") or {}).get("FM2P_CRN"))}
    return out


def sec_crn():
    P("=" * 100)
    P("P3-12 D-7 CONDITION - 3b against the range-99 behaviour, CRN (FM2P_CRN=1), fresh seeds 9701-9716")
    arms = {a: crn_arm(a) for a in ("mf2hcZ", "mf2hc3", "mf2hcX", "mf2hcS")}
    for a, r in arms.items():
        if not r:
            continue
        P("  %-7s %2d runs (CRN %d)  deaths %d  rescued %d  searcher in fire %s  all-UAV in fire %s" % (
            a, len(r), sum(v["crn"] for v in r.values()), sum(v["dead"] for v in r.values()),
            sum(v["rescued"] for v in r.values()), pct(sum(v["b_s"] for v in r.values()), sum(v["n_s"] for v in r.values())),
            pct(sum(v["b_a"] for v in r.values()), sum(v["n_a"] for v in r.values()))))
    for on, off, label in (("mf2hc3", "mf2hcZ", "3b alone"), ("mf2hcS", "mf2hcX", "all switches together")):
        A, B = arms.get(on) or {}, arms.get(off) or {}
        keys = sorted(set(A) & set(B))
        if not keys:
            continue
        dd = sum(A[k]["dead"] for k in keys) - sum(B[k]["dead"] for k in keys)
        worse = sum(1 for k in keys if A[k]["dead"] > B[k]["dead"])
        better = sum(1 for k in keys if A[k]["dead"] < B[k]["dead"])
        ds = 100.0 * (sum(A[k]["b_s"] for k in keys) / max(1, sum(A[k]["n_s"] for k in keys))
                      - sum(B[k]["b_s"] for k in keys) / max(1, sum(B[k]["n_s"] for k in keys)))
        da = 100.0 * (sum(A[k]["b_a"] for k in keys) / max(1, sum(A[k]["n_a"] for k in keys))
                      - sum(B[k]["b_a"] for k in keys) / max(1, sum(B[k]["n_a"] for k in keys)))
        stop = (ds > 1.0 or da > 0.5) or (dd >= 2 and worse > better)
        per = [(k, B[k]["dead"], A[k]["dead"]) for k in keys if A[k]["dead"] != B[k]["dead"]]
        P("  %-22s (%s vs %s, %d CRN pairs): deaths %+d (seeds worse %d, better %d) | searcher fire %+.2f pts | "
          "all-UAV fire %+.2f pts  => %s" % (label, on, off, len(keys), dd, worse, better, ds, da,
                                             "STOP" if stop else "no material rise"))
        P("      per-seed deaths that differ (config, range-99, near-field): %s" % per)


def sec_outcomes():
    """Reported per arm, never gated (canonical-13 rule): each arm against mf2Z on the SAME configs."""
    P("=" * 100)
    P("OUTCOMES, DETECTION AND SEARCH (reported, not gated) - each arm vs mf2Z on the same configurations")
    z = probe_runs("mf2Z")

    def agg(runs, cfgs):
        out = collections.Counter()
        dets = []
        cells = set()
        for c in cfgs:
            d = runs[c]
            ev = d.get("eval") or {}
            for k in ("rescued", "dead", "never_detected", "firefighter_deaths", "unreachable"):
                out[k] += int(ev.get(k) or 0)
            out["terminal_missing"] += int(d.get("terminal_step") is None)
            dets += list(d["_det"].values())
            for row in d["rows_uav"]:
                for u in row:
                    if u[3] == "victim_searcher":
                        cells.add((c, u[1], u[2]))
        return out, dets, len(cells)

    for arm in ("mf2A1", "mf2FS", "mf2A2", "mf2A3a", "mf2A3b", "mf2A4", "mf2ALL"):
        runs = probe_runs(arm)
        cfgs = sorted(set(runs) & set(z))
        if not cfgs:
            continue
        oa, da, ca = agg(runs, cfgs)
        oz, dz, cz = agg(z, cfgs)
        P("  %-7s (%2d cfgs) rescued %d/%d dead %d/%d never_detected %d/%d ff_deaths %d/%d unreachable %d/%d"
          " no-terminal %d/%d | victims detected %d/%d, median first detection %s/%s | searcher cells %d/%d"
          "   (arm/mf2Z)" % (
              arm, len(cfgs), oa["rescued"], oz["rescued"], oa["dead"], oz["dead"], oa["never_detected"],
              oz["never_detected"], oa["firefighter_deaths"], oz["firefighter_deaths"], oa["unreachable"],
              oz["unreachable"], oa["terminal_missing"], oz["terminal_missing"], len(da), len(dz),
              statistics.median(da) if da else None, statistics.median(dz) if dz else None, ca, cz))
    P("  P3-5(d) x-strip pulls by wind (not changed, D-8):")
    for arm in ("mf2Z", "mf2ALL"):
        c = collections.Counter()
        for d in probe_runs(arm).values():
            for k, v in ((d.get("mf2") or {}).get("strips") or {}).items():
                parts = k.split("|")
                c["%s|%s" % (parts[1], parts[2]) if len(parts) >= 3 else k] += v
        P("    %-7s %s" % (arm, dict(sorted(c.items()))))


def _term(d):
    t = d.get("terminal_step")
    return 361 if t is None else int(t)


def _window(d, last_step):
    """(no-searcher steps, searcher flying UAV-steps) over steps 1 .. last_step (rows 0 .. last_step-1)."""
    gap = fly = 0
    for row in d["rows_uav"][:max(0, last_step)]:
        s = [u for u in row if u[3] == "victim_searcher"]
        f = [u for u in s if not u[5] and not u[6]]
        if s and not f:
            gap += 1
        fly += len(f)
    return gap, fly


def _depot_dist_fn(d):
    cells = [tuple(c) for c in ((d.get("depots") or {}).get("cells") or [])]
    cache = {}

    def dist(x, y):
        if x is None or not cells:
            return 99
        k = (x, y)
        if k not in cache:
            cache[k] = min(abs(x - a) + abs(y - b) for a, b in cells)
        return cache[k]
    return dist


def _merge(steps, gap):
    """Maximal intervals over sorted step numbers, merging neighbours at most `gap` apart."""
    out = []
    for s in sorted(set(steps)):
        if out and s - out[-1][1] <= gap:
            out[-1][1] = s
        else:
            out.append([s, s])
    return [(a, b, b - a + 1) for a, b in out]


def yield_metrics(d):
    """Amendment 4 metrics for one probe run (steps are 1-based; row i = after step i+1).
      depot_yields_pre   yield steps by UAVs within 5 cells of a depot (at the start of the step)
                         before the run's terminal step
      depot_clusters     maximal intervals of steps in which such a yield occurs, merging gaps <= 3
      stalls             per UAV, maximal intervals of its yield steps, merging gaps <= 2 (the cap's
                         free step), with the steps it spans
      drift_by_yield     DRIFT_TOO_HIGH (local) names whose last-5-move window has >= 2 refusals only
                         because refusals made ON YIELD STEPS are counted
    """
    m = (d.get("mf2") or {})
    mu, fleet, R = m.get("uav") or [], m.get("fleet") or [], d["rows_uav"]
    term = d.get("terminal_step") or 361
    dist = _depot_dist_fn(d)
    depot_steps, per_uav = [], collections.defaultdict(list)
    out = collections.Counter()
    hist = collections.defaultdict(list)       # uid -> [(refused, on_yield_step)]
    for t in range(len(mu)):
        step = t + 1
        before = {u[0]: u for u in (R[t - 1] if t >= 1 else R[0])}
        for u in mu[t]:
            uid = u[0]
            refused = u[3] in ("refused_occupied", "refused_oob")
            hist[uid].append((refused, bool(u[9])))
            if u[9]:
                per_uav[uid].append(step)
                p = before.get(uid)
                if p is not None and dist(p[1], p[2]) <= 5:
                    depot_steps.append(step)
                    if step < term:
                        out["depot_yields_pre"] += 1
                if step < term:
                    out["yields_pre"] += 1
                out["yields"] += 1
        if 1 <= t < len(fleet) and isinstance(fleet[t], list) and len(fleet[t]) >= 6:
            for uid in fleet[t][5].get("DRIFT_TOO_HIGH|local", ()):
                win = hist[uid][max(0, t - 5):t]   # the moves of steps t-4 .. t (rows t-5 .. t-1)
                total = sum(1 for r, y in win if r)
                non_yield = sum(1 for r, y in win if r and not y)
                out["drift_named"] += 1
                if total >= 2 and non_yield < 2:
                    out["drift_by_yield"] += 1
    # clipped to the pre-terminal window - the steps while a victim remains (amendment 4)
    clusters = [(a, min(b, term - 1), min(b, term - 1) - a + 1) for a, b, n in _merge(depot_steps, 3) if a < term]
    stalls = []
    for uid, st in per_uav.items():
        for a, b, n in _merge(st, 2):
            if a < term:
                stalls.append((min(b, term - 1) - a + 1, uid, a, min(b, term - 1)))
    return out, clusters, sorted(stalls, reverse=True), term


def sec_yfix(arms=("mf2cX", "mf2ALL", "mf2cS", "mf2rX", "mf2rS", "mf2rC", "mf2rM")):
    """Amendment 4 - the stationary-yield fixes (maintainer ruling after FOLLOW-UP 2)."""
    P("=" * 100)
    P("AMENDMENT 4 - YIELD METRICS (pre-terminal; depot = within 5 cells of a depot cell)")
    for arm in arms:
        runs = probe_runs(arm)
        if not runs:
            continue
        tot = collections.Counter()
        all_cl, all_st = [], []
        for cfg, d in sorted(runs.items()):
            o, cl, st, term = yield_metrics(d)
            tot += o
            all_cl += [(n, cfg, a, b) for a, b, n in cl]
            all_st += [(n, cfg, uid, a, b) for n, uid, a, b in st]
        all_cl.sort(reverse=True)
        all_st.sort(reverse=True)
        long_cl = [c for c in all_cl if c[0] >= 10]
        long_st = [s for s in all_st if s[0] >= 10]
        P("  %-7s yields %d (pre-terminal %d) | DEPOT yields pre-terminal %d | depot clusters >= 10 steps: %d,"
          " longest %s | yield stalls >= 10 steps: %d, longest %s | drift alarms caused by yield-step"
          " refusals %d of %d named" % (
              arm, tot["yields"], tot["yields_pre"], tot["depot_yields_pre"], len(long_cl),
              all_cl[0] if all_cl else None, len(long_st), all_st[0] if all_st else None,
              tot["drift_by_yield"], tot["drift_named"]))
        if long_cl:
            P("          depot clusters >= 10: %s" % long_cl[:8])
        if long_st:
            P("          yield stalls >= 10: %s" % long_st[:8])


def sec_r(base="mf2cX", cand="mf2rS", others=("mf2rC", "mf2rM")):
    """Amendment 4 - provenance, identity, the ruled decision and the validation list."""
    import runpy
    import subprocess
    q = runpy.run_path(os.path.join(OUT, "_mf2_r_queue.py"), run_name="mf2_r_queue")
    P("=" * 100)
    P("AMENDMENT 4 - PROVENANCE (source hashes vs the files AT THE RUN'S OWN COMMIT, switches) AND IDENTITY")
    at_head = {}

    def head_shas(head, path):
        key = (head, path)
        if key not in at_head:
            blob = subprocess.run(["git", "-C", REPO, "show", "%s:%s" % (head, path.replace("\\", "/"))],
                                  capture_output=True).stdout
            lf = blob.replace(b"\r\n", b"\n")
            at_head[key] = {hashlib.sha256(lf).hexdigest()[:16],
                            hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest()[:16]}
        return at_head[key]

    for arm, want in q["ARMS"].items():
        runs = probe_runs(arm)
        if not runs:
            P("  %-6s no runs" % arm)
            continue
        bad = []
        for cfg, d in runs.items():
            ss = d.get("src_sha") or {}
            if any(ss[k] not in head_shas(str(d.get("head")), k) for k in ss):
                bad.append(cfg + ":src")
            ex = d.get("extra_params") or {}
            bad += ["%s:%s=%s" % (cfg, s, ex.get(s)) for s, v in want.items() if ex.get(s) != v]
            if not d.get("complete") or d.get("crashed"):
                bad.append(cfg + ":incomplete")
        heads = collections.Counter(str(d.get("head"))[:7] for d in runs.values())
        P("  %-6s %2d runs heads %s  %s" % (arm, len(runs), dict(heads), "OK" if not bad else "MISMATCH %s" % bad[:6]))
    for new, old in (("mf2rX", "mf2cX"), ("mf2rZ", "mf2Z"), ("mf2rZ", "mf1P")):
        a, b = probe_runs(new), probe_runs(old)
        if a and b:
            r = compare_probe(a, b)
            ok = sum(1 for v in r.values() if not v)
            P("  identity %s == %s: %d/%d identical on every _sd_probe field %s" % (
                new, old, ok, len(r), "" if ok == len(r) else {k: v for k, v in r.items() if v}))

    def summary(arm):
        runs = probe_runs(arm)
        tot = collections.Counter()
        cl_all, st_all, near_refusal_runs = [], [], []
        for cfg, d in sorted(runs.items()):
            o, cl, st, term = yield_metrics(d)
            tot += o
            cl_all += [(n, cfg, a, b) for a, b, n in cl]
            st_all += [(n, cfg, uid, a, b) for n, uid, a, b in st]
            ev = d.get("eval") or {}
            for k in ("rescued", "dead", "never_detected", "firefighter_deaths", "unreachable"):
                tot[k] += int(ev.get(k) or 0)
            tot["no_terminal"] += int(d.get("terminal_step") is None)
            for r in d["rows_dec"]:
                tot["steps"] += 1
                tot["normal"] += int(r.get("mode") == "normal")
            dist = _depot_dist_fn(d)
            R, mu = d["rows_uav"], (d.get("mf2") or {}).get("uav") or []
            run = collections.Counter()
            for t in range(1, len(mu)):
                prev = {u[0]: u for u in R[t - 1]}
                cur = {u[0]: u for u in R[t]}
                for u in mu[t]:
                    uid = u[0]
                    p = prev.get(uid)
                    if u[9]:
                        continue
                    if p is None or p[5] or p[6] or cur[uid][5] or cur[uid][6] or t + 1 >= _term(d):
                        run[uid] = 0
                        continue
                    if dist(p[1], p[2]) <= 5 and u[3] in ("refused_occupied", "refused_oob"):
                        tot["near_depot_refusals_pre"] += 1
                        run[uid] += 1
                        near_refusal_runs.append((run[uid], cfg, uid, t + 1))
                    else:
                        run[uid] = 0
                act = {u[0]: u[8] for u in R[t]}
                tot["step_aside"] += sum(1 for v in act.values() if v == "yield_step_aside")
                tot["hold_escape"] += sum(1 for v in act.values() if v == "hold_escape")
        cl_all.sort(reverse=True)
        st_all.sort(reverse=True)
        near_refusal_runs.sort(reverse=True)
        return tot, cl_all, st_all, near_refusal_runs

    P("=" * 100)
    P("AMENDMENT 4 - THE VALIDATION (pre-terminal; depot = within 5 cells of a depot cell)")
    rows = {}
    for arm in (base, cand) + tuple(others):
        if probe_runs(arm):
            rows[arm] = summary(arm)
    for arm, (tot, cl, st, nr) in rows.items():
        P("  %-6s depot yields pre %4d | depot clusters >=10: %d (longest %s) | stalls >=10: %d (longest %s) |"
          " drift by yield-step refusals %d of %d | step asides %d, hold_escapes %d | near-depot refusals pre %d,"
          " longest near-depot refusal run %s | normal %.2f%% | rescued %d dead %d never_detected %d ff deaths %d"
          " unreachable %d no-terminal %d" % (
              arm, tot["depot_yields_pre"], sum(1 for c in cl if c[0] >= 10), cl[0] if cl else None,
              sum(1 for s in st if s[0] >= 10), st[0] if st else None, tot["drift_by_yield"], tot["drift_named"],
              tot["step_aside"], tot["hold_escape"], tot["near_depot_refusals_pre"], nr[0] if nr else None,
              100.0 * tot["normal"] / max(1, tot["steps"]), tot["rescued"], tot["dead"], tot["never_detected"],
              tot["firefighter_deaths"], tot["unreachable"], tot["no_terminal"]))
        long_st = [s for s in st if s[0] >= 10]
        if long_st:
            P("         stalls >= 10: %s" % long_st[:10])
        long_cl = [c for c in cl if c[0] >= 10]
        if long_cl:
            P("         depot clusters >= 10: %s" % long_cl[:10])
    if cand in rows:
        tot, cl, st, nr = rows[cand]
        long_cl = [c for c in cl if c[0] >= 10]
        P("  => DECISION (the ruling): %s" % (
            "ITEM 2 STAYS ON with STATIONARY_YIELD_FIX - no depot cluster >= 10 steps before the terminal step"
            if not long_cl else "SHIP ITEM 2 OFF - %d depot cluster(s) >= 10 steps remain: %s" % (len(long_cl), long_cl[:4])))
        stall_ok = not any(s[0] >= 10 for s in st)
        P("     validation: no yield stall >= 10 steps before the terminal step - %s; drift alarms caused by"
          " yield-step refusals = 0 - %s" % ("PASS" if stall_ok else "FAIL", "PASS" if tot["drift_by_yield"] == 0 else "FAIL"))


def sec_provc():
    """Amendment 3: provenance and identity of the compact-stagger arms."""
    import runpy
    q = runpy.run_path(os.path.join(OUT, "_mf2_c_queue.py"), run_name="mf2_c_queue")
    P("=" * 100)
    P("AMENDMENT 3 - PROVENANCE (head, source hashes vs the files AT THE RUN'S OWN COMMIT, recorded switches) AND IDENTITY")
    import subprocess

    at_head = {}

    def head_shas(head, path):
        """The file as committed at the run's own head, in either line ending (the probe hashes the
        raw working-tree bytes; the working tree mixes CRLF and LF)."""
        key = (head, path)
        if key not in at_head:
            blob = subprocess.run(["git", "-C", REPO, "show", "%s:%s" % (head, path.replace("\\", "/"))],
                                  capture_output=True).stdout
            lf = blob.replace(b"\r\n", b"\n")
            at_head[key] = {hashlib.sha256(lf).hexdigest()[:16],
                            hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest()[:16]}
        return at_head[key]

    for arm, want in q["ARMS"].items():
        runs = probe_runs(arm)
        if not runs:
            P("  %-6s no runs" % arm)
            continue
        heads = collections.Counter(str(d.get("head"))[:7] for d in runs.values())
        bad = []
        for cfg, d in runs.items():
            ss = d.get("src_sha") or {}
            if any(ss[k] not in head_shas(str(d.get("head")), k) for k in ss):
                bad.append(cfg + ":src")
            ex = d.get("extra_params") or {}
            for s, v in want.items():
                if ex.get(s) != v:
                    bad.append("%s:%s=%s" % (cfg, s, ex.get(s)))
            if not d.get("complete"):
                bad.append(cfg + ":incomplete")
        P("  %-6s %2d runs heads %s  %s" % (arm, len(runs), dict(heads), "OK" if not bad else "MISMATCH %s" % bad[:6]))
    for new, old in (("mf2cZ", "mf2Z"), ("mf2cZ", "mf1P"), ("mf2cE", "mf2A4")):
        a, b = probe_runs(new), probe_runs(old)
        if a and b:
            r = compare_probe(a, b)
            ok = sum(1 for v in r.values() if not v)
            P("  identity %s == %s: %d/%d identical on every _sd_probe field %s" % (
                new, old, ok, len(r), "" if ok == len(r) else {k: v for k, v in r.items() if v}))


def sec_d9c(pairs=(("mf2Z", "mf2cK", "DECISIVE: item 4 compact alone vs all off"),
                   ("mf2Z", "mf2A4", "reference: item 4 EVEN alone vs all off (8 configs)"),
                   ("mf1P", "mf2K", "reference: item 4 EVEN alone vs c08456b (16 configs)"),
                   ("mf2cX", "mf2cS", "in-system: all on with compact vs all on but item 4"))):
    """Amendment 3: the compact stagger judged on the pre-terminal window (the maintainer's refinement
    of D-9) - steps both runs of a pair have victims left: 1 .. min(T_off, T_on) - 1."""
    P("=" * 100)
    P("D-9 (amendment 3) - THE STAGGER ON THE PRE-TERMINAL WINDOW; SHIP COMPACT ON iff in BOTH C and D"
      " C_pre <= G_pre and never_detected does not rise (decisive pair only)")
    for off_arm, on_arm, label in pairs:
        A, B = probe_runs(off_arm), probe_runs(on_arm)
        common = sorted(set(A) & set(B))
        if not common:
            continue
        P("  %s  (%s -> %s, %d pairs)" % (label, off_arm, on_arm, len(common)))
        verdict = {}
        for sc in "ABCD":
            cfgs = [c for c in common if c.startswith(sc)]
            if not cfgs:
                continue
            acc = collections.Counter()
            for c in cfgs:
                a, b = A[c], B[c]
                ta, tb = _term(a), _term(b)
                w = min(ta, tb) - 1
                ga, fa = _window(a, w)
                gb, fb = _window(b, w)
                acc["G_pre"] += ga - gb
                acc["C_pre"] += fa - fb
                ga0, fa0 = _window(a, ta - 1)
                gb0, fb0 = _window(b, ta - 1)
                acc["G_offwin"] += ga0 - gb0
                acc["C_offwin"] += fa0 - fb0
                gbo, fbo = _window(b, tb - 1)
                acc["G_own"] += ga0 - gbo
                acc["C_own"] += fa0 - fbo
                gA, fA = _window(a, 360)
                gB, fB = _window(b, 360)
                acc["G_360"] += gA - gB
                acc["C_360"] += fA - fB
                acc["nd_off"] += int((a.get("eval") or {}).get("never_detected") or 0)
                acc["nd_on"] += int((b.get("eval") or {}).get("never_detected") or 0)
                acc["resc_off"] += int((a.get("eval") or {}).get("rescued") or 0)
                acc["resc_on"] += int((b.get("eval") or {}).get("rescued") or 0)
                acc["dead_off"] += int((a.get("eval") or {}).get("dead") or 0)
                acc["dead_on"] += int((b.get("eval") or {}).get("dead") or 0)
                acc["win"] += w
            ok = acc["C_pre"] <= acc["G_pre"] and acc["nd_on"] <= acc["nd_off"]
            if sc in "CD":
                verdict[sc] = ok
            P("    %s  PRE (common window, %d steps over %d runs): G %4d  C %4d  -> %s | off-run window: G %4d"
              " C %4d | own windows: G %4d C %4d | FULL 360: G %4d C %4d | never_detected %d -> %d |"
              " rescued %d -> %d | dead %d -> %d" % (
                  sc, acc["win"], len(cfgs), acc["G_pre"], acc["C_pre"],
                  ("PASS" if ok else "FAIL") if sc in "CD" else "(A/B: reported)",
                  acc["G_offwin"], acc["C_offwin"], acc["G_own"], acc["C_own"], acc["G_360"], acc["C_360"],
                  acc["nd_off"], acc["nd_on"], acc["resc_off"], acc["resc_on"], acc["dead_off"], acc["dead_on"]))
        if on_arm == "mf2cK":
            # review (compact reviewer R1): a decision only from a complete decisive sample - both
            # scenarios' four configurations, every run complete, uncrashed, with an eval, seed-matched
            problems = []
            for sc in "CD":
                cf = [c for c in common if c.startswith(sc)]
                if len(cf) != 4:
                    problems.append("%s has %d pairs, not 4" % (sc, len(cf)))
                for c in cf:
                    for nm, d in ((off_arm, A[c]), (on_arm, B[c])):
                        if not d.get("complete") or d.get("crashed") or not d.get("eval"):
                            problems.append("%s %s incomplete/crashed/no eval" % (nm, c))
                    if A[c].get("seed") != B[c].get("seed"):
                        problems.append("%s seed mismatch" % c)
            if problems:
                P("    => NO DECISION (incomplete decisive sample): %s" % problems[:6])
            else:
                P("    => DECISION: %s" % ("SHIP COMPACT ON (C and D both pass)" if verdict.get("C") and verdict.get("D")
                                            else "SHIP ITEM 4 OFF (%s)" % ", ".join(
                                                "%s %s" % (k, "pass" if v else "FAIL") for k, v in sorted(verdict.items()))))


SECTIONS = {"prov": None, "ident": sec_ident, "item1": sec_item1, "fire": sec_fire, "item2": sec_item2,
            "item3": sec_item3, "osc": sec_osc, "item4": sec_item4, "d9": sec_d9, "exposure": sec_exposure,
            "rbgate": sec_rbgate, "crn": sec_crn, "outcomes": sec_outcomes, "d9c": sec_d9c, "provc": sec_provc, "yfix": sec_yfix, "r": sec_r}


def main():
    args = sys.argv[1:]
    while "--alias" in args:
        i = args.index("--alias")
        k, v = args[i + 1].split("=", 1)
        ALIAS[k] = v
        del args[i:i + 2]
    for k, v in ALIAS.items():
        P("ALIAS: every '%s' below is the arm %s" % (k, v))
    want = args or list(SECTIONS)
    arms = {"mf2Z": {s: 0 for s in SW}, "mf2ALL": {}}
    for arm, s in (("mf2A1", "FAILSAFE_REAL_ALARMS"), ("mf2FS", "GLOBAL_ANALYZER_FIRE_SOURCE_FIX"),
                   ("mf2A2", "UAV_HOLD_STATIONARY"), ("mf2A3a", "SEARCHER_WIND_COVERAGE_FIX"),
                   ("mf2A3b", "SEARCHER_GATE_NEAR_FIELD"), ("mf2A4", "STAGGERED_LAUNCH_BATTERY")):
        d = {x: 0 for x in SW}
        d[s] = 1
        arms[arm] = d
    for w in want:
        if w == "prov":
            sec_prov(arms)
        else:
            SECTIONS[w]()


if __name__ == "__main__":
    main()
