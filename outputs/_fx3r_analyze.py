"""fix3a ROUND 2 analyzer (read-only) - GENERATED from outputs/_fx3_p3_analyze.py by the tag map fx3<arm> -> fx3r<arm>
(references fx3v / fx3hR / fx3gR unchanged; outputs/fix3a_r2_prereg.txt), then extended below. Part 3 analyzer - every pre-registered check of outputs/fix3a_part1.txt section 7 and
outputs/fix3a_part3_prereg.txt amendment 1.

usage: _fx3_p3_analyze.py [section ...] [--head <commit>]
sections: prov ident gates a1 a2 b b1checks exposure yields attrib outcomes rbgate (default: all)
Windows: PRE = steps 1 .. terminal_step - 1 (all 360 without a terminal step); paired costs on the COMMON
pre-terminal window 1 .. min(T_a, T_b) - 1.
"""
from __future__ import annotations

import collections
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _fx3_pockets as P  # noqa: E402
import _mf2_p3_analyze as M  # noqa: E402

DET_RE = M.DET_RE
WAIT = "victim_search_wind_aware_retarget_to_interior_fire_wait"
RETREAT = "victim_search_wind_aware_retarget_to_interior_fire_retreat"
NEW = ["SEARCHER_ROUTE_FIRE_FIELD", "SEARCHER_SWEEP_IN_BOUNDS", "SEARCHER_CORNER_ESCAPE", "FREE_CELL_DOCKING",
       "SCENARIO_B_TEAM", "SCENARIO_B_STAGGERED_LAUNCH", "SCENARIO_B_RETURN_DELAY",
       "SEARCHER_FIRE_ROUTE_OWNER", "SEARCHER_ROUTE_BOUNDED_WAIT"]
A1_ARMS = ("fx3rS", "fx3rS2", "fx3rA1", "fx3rB0", "fx3rB2", "fx3rB3", "fx3rB23")     # arms that contain A1
ALL_ARMS = ("fx3rZ", "fx3rX", "fx3rS", "fx3rS2", "fx3rSZ2", "fx3rA1", "fx3rA2", "fx3rB0", "fx3rB2", "fx3rB3",
            "fx3rB23", "fx3rW", "fx3rW2")   # fx3rX identity arm, fx3rW / fx3rW2 sensitivity: reported, never gated
LOW = 30.0
_CACHE = {}


def out(*a):
    print(*a)


def load(tag):
    if tag in _CACHE:
        return _CACHE[tag]
    runs = {}
    for f in sorted(glob.glob(os.path.join(HERE, "_sd_%s_*.json" % tag))):
        base = os.path.basename(f)
        if ".json." in base:
            continue
        key = base[len("_sd_%s_" % tag):-5]
        if not re.fullmatch(r"[ABCD]_[ENSW](_\d+)?", key):
            continue
        d = json.load(open(f, encoding="utf-8"))
        det = {}
        st = f[:-5] + ".stdout.txt"
        if os.path.exists(st):
            for line in open(st, encoding="utf-8", errors="replace"):
                m = DET_RE.match(line.strip())
                if m and m.group(3) not in det:
                    det[m.group(3)] = int(m.group(1))
        d["_det"] = det
        runs[key] = d
    _CACHE[tag] = runs
    return runs


def pre_end(d):
    t = d.get("terminal_step")
    return (t - 1) if t else len(d["rows_uav"])


def raw_sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


# ================================================================================================ prov
def sec_prov(head=None):
    out("=" * 100)
    out("P3-0 PROVENANCE - every run's head, source hashes against the files of this tree, and its switch values")
    for tag in ALL_ARMS:
        runs = load(tag)
        if not runs:
            out("  %-7s (no runs)" % tag)
            continue
        heads = collections.Counter(str(d.get("head"))[:8] for d in runs.values())
        bad_src = 0
        for d in runs.values():
            for rel, sha in (d.get("src_sha") or {}).items():
                p = os.path.join(REPO, rel)
                if os.path.exists(p) and raw_sha(p) != sha:
                    bad_src += 1
        zero = collections.Counter()
        for d in runs.values():
            for n in NEW:
                if (d.get("params") or {}).get(n) == 0:
                    zero[n] += 1
        out("  %-7s runs %3d heads %s | src hashes differing from this tree: %d | switches at 0 (runs): %s" % (
            tag, len(runs), dict(heads), bad_src, dict(zero) or "none"))


# ================================================================================================ ident
FIELDS = ("rows_uav", "rows_ff", "rows_vic", "rows_dec", "rows_trig", "eval", "terminal_step", "steps_done",
          "crashed", "stdout_sha", "stdout_tags", "inline_violations", "warning_count")


def probe_ident(a_tag, b_tag):
    A, B = load(a_tag), load(b_tag)
    common = sorted(set(A) & set(B))
    same = 0
    lines = []
    for c in common:
        da, db = A[c], B[c]
        diff = [k for k in FIELDS if da.get(k) != db.get(k)]
        for k in sorted(set(da.get("mf2") or {}) | set(db.get("mf2") or {})):
            if k != "probe" and (da.get("mf2") or {}).get(k) != (db.get("mf2") or {}).get(k):
                diff.append("mf2." + k)
        same += not diff
        if diff:
            lines.append("    %s DIFFER %s" % (c, diff))
    return same, len(common), lines


def sec_ident():
    out("=" * 100)
    out("P3-1 EVERY NEW SWITCH 0 == a5a496db")
    s, n, lines = probe_ident("fx3v", "fx3rZ")
    out("  (a) probe fx3rZ vs fx3v (a5a496db): %d/%d identical on every behavioural field and every mf2 section  %s" % (
        s, n, "PASS" if s == n == 16 else "FAIL"))
    for ln in lines:
        out(ln)
    # (b) harness
    same = n = 0
    for f in sorted(glob.glob(os.path.join(HERE, "_ffr_fx3hR_*.json"))):
        if ".json." in os.path.basename(f):
            continue
        g = f.replace("_ffr_fx3hR_", "_ffr_fx3rhZ_")
        if not os.path.exists(g):
            continue
        a, b = json.load(open(f, encoding="utf-8")), json.load(open(g, encoding="utf-8"))
        skip = {"tag", "repo", "wall_s", "params", "extra_params"}
        diff = [k for k in sorted(set(a) | set(b)) if k not in skip and a.get(k) != b.get(k)]
        n += 1
        same += not diff
        if diff:
            out("    harness %s DIFFER %s" % (os.path.basename(g), diff[:8]))
    out("  (b) harness fx3rhZ vs fx3hR: %d/%d identical on every field but tag / repo / wall_s / params  %s" % (
        same, n, "PASS" if same == n == 16 else "FAIL"))
    # (c) rbgate
    same = n = 0
    for sh, w in (("a", "east"), ("b", "east"), ("c", "east"), ("s", "south")):
        fr = os.path.join(HERE, "_rblatch_camp2_fx3gR%s_D_%s.json" % (sh, w))
        fz = os.path.join(HERE, "_rblatch_camp2_fx3rgZ%s_D_%s.json" % (sh, w))
        if not (os.path.exists(fr) and os.path.exists(fz)):
            continue
        n += 1
        a, b = strip_rb(json.load(open(fr, encoding="utf-8"))), strip_rb(json.load(open(fz, encoding="utf-8")))
        diff = [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
        same += not diff
        if diff:
            out("    rbgate shard %s DIFFER %s" % (sh, diff[:8]))
    out("  (c) route_blocked fx3rgZ vs fx3gR: %d/%d shards identical (tag / params / per-seed wall_s dropped)  %s" % (
        same, n, "PASS" if same == n == 4 else "FAIL"))


def strip_rb(o):
    if isinstance(o, dict):
        return {k: strip_rb(v) for k, v in o.items()
                if k not in ("tag", "params", "wall_s", "argv", "repo", "head", "src_sha", "started", "finished",
                             "elapsed_s")}
    if isinstance(o, list):
        return [strip_rb(x) for x in o]
    return o


# ================================================================================================ gates
def searcher_osc_episodes(d, full=True):
    """(O): per victim searcher, maximal runs of steps covered by some 10-step window ANYWHERE on the grid,
    the searcher airborne (not docked, not on a return leg) on every step, on <= 2 distinct cells with >= 4
    cell changes (a two-cell alternation). Returns [(uid, start, end, len, cells)]."""
    rows = d["rows_uav"]
    last = len(rows) if full else pre_end(d)
    per = collections.defaultdict(list)
    for t in range(last):
        for u in rows[t]:
            if u[3] == "victim_searcher":
                per[u[0]].append((t, (u[1], u[2]), bool(u[5] or u[6])))
    eps = []
    for uid, seq in per.items():
        n = len(seq)
        mark = [False] * n
        for i in range(0, n - 9):
            w = seq[i:i + 10]
            if any(r for _, _, r in w):
                continue
            cells = {c for _, c, _ in w}
            ch = sum(1 for k in range(1, 10) if w[k][1] != w[k - 1][1])
            if len(cells) <= 2 and ch >= 4:
                for k in range(i, i + 10):
                    mark[k] = True
        i = 0
        while i < n:
            if mark[i]:
                j = i
                while j + 1 < n and mark[j + 1]:
                    j += 1
                eps.append((uid, seq[i][0] + 1, seq[j][0] + 1, j - i + 1, sorted({c for _, c, _ in seq[i:j + 1]})))
                i = j + 1
            else:
                i += 1
    return eps


YIELD_LABELS = ("hold", "hold_escape", "yield_step_aside")


def episode_kind(d, uid, start, end):
    """Amendment 2: attribute an oscillation episode by the executed labels of its steps - YIELD when every
    step's label is a fail-safe yield / hold / its escape or step aside (fix2 item 2), ROUTING when none
    is, MIXED otherwise."""
    labels = []
    for s in range(start, end + 1):
        u = [x for x in d["rows_uav"][s - 1] if x[0] == uid]
        if u:
            labels.append(str(u[0][8]))
    y = sum(1 for a in labels if a in YIELD_LABELS or a.startswith("hold_escape"))
    if y == len(labels):
        return "YIELD"
    if y == 0:
        return "ROUTING"
    return "MIXED(%d/%d yield)" % (y, len(labels))


def fire_waits(d):
    """(W): per UAV, maximal runs of steps labelled ..._fire_wait. Each with the victims it overlaps that
    later DIE (alive and unresolved at some step of the wait, dead at the end) or go UNDETECTED (undetected
    during the wait and never detected by the end)."""
    rows = d["rows_uav"]
    vrows = d["rows_vic"]
    det = d.get("_det") or {}
    end_status = {v[0]: (v[4] or v[3]) for v in vrows[-1]}
    per = collections.defaultdict(list)
    for t, row in enumerate(rows):
        for u in row:
            if str(u[8]).endswith("_fire_wait"):
                per[u[0]].append(t + 1)
    eps = []
    for uid, steps in per.items():
        i = 0
        while i < len(steps):
            j = i
            while j + 1 < len(steps) and steps[j + 1] == steps[j] + 1:
                j += 1
            s0, s1 = steps[i], steps[j]
            later_dead, undetected = [], []
            for v in vrows[s0 - 1]:
                vid = v[0]
                st = v[4] or v[3]
                if st in ("rescued", "dead", "unreachable"):
                    continue
                if end_status.get(vid) == "dead":
                    later_dead.append(vid)
                if vid not in det:            # never detected by the end, so undetected during the wait
                    undetected.append(vid)
            eps.append((uid, s0, s1, s1 - s0 + 1, later_dead, undetected))
            i = j + 1
    return eps


def sec_gates():
    out("=" * 100)
    out("AMENDMENT 1 (N) (O) (W), EVERY ARM. (N) and (O) = 0 BIND every arm that contains A1: %s" % (A1_ARMS,))
    for tag in ALL_ARMS:
        runs = load(tag)
        if not runs:
            continue
        never = sorted(k for k, d in runs.items() if not d.get("terminal_step"))
        osc_full = [(k,) + e + (episode_kind(d, e[0], e[1], e[2]),)
                    for k, d in runs.items() for e in searcher_osc_episodes(d, True)]
        osc_pre = [e for d in runs.values() for e in searcher_osc_episodes(d, False)]
        kinds = collections.Counter(e[-1].split("(")[0] for e in osc_full)
        pock = []
        anywhere = []
        for k, d in runs.items():
            for e in P.pockets(d, r=500, pre_terminal=False)[0]:
                if e["role"] != "victim_searcher":
                    continue
                rows = d["rows_uav"]
                cells = [[u for u in rows[s - 1] if u[0] == e["uid"]][0][1:3] for s in range(e["start"], e["end"] + 1)]
                if sum(1 for i in range(1, len(cells)) if cells[i] != cells[i - 1]) * 3 >= len(cells):
                    anywhere.append((k, e["uid"], e["start"], e["end"], e["len"],
                                     episode_kind(d, e["uid"], e["start"], e["end"])))
            eps, _ = P.pockets(d, pre_terminal=False)
            for e in eps:
                if e["role"] != "victim_searcher":
                    continue
                rows = d["rows_uav"]
                cells = [[u for u in rows[s - 1] if u[0] == e["uid"]][0][1:3] for s in range(e["start"], e["end"] + 1)]
                ch = sum(1 for i in range(1, len(cells)) if cells[i] != cells[i - 1])
                if ch * 3 >= len(cells):
                    pock.append((k, e["uid"], e["start"], e["end"], e["len"]))
        waits = [(k,) + w for k, d in runs.items() for w in fire_waits(d)]
        gated = tag in A1_ARMS
        n_ok = not never
        o_ok = not osc_full and not pock and not anywhere
        out("  %-7s runs %2d | (N) never finish %d %s%s | (O) searcher two-cell alternation episodes FULL %d (PRE %d),"
            " longest %d; pocket-kind oscillation episodes near a depot %d, anywhere %d%s | (W) fire-waits %d, longest %d, overlapping a victim"
            " that later dies %d, that goes undetected %d" % (
                tag, len(runs), len(never), never if never else "", ("  PASS" if n_ok else "  FAIL") if gated else "  (reported)",
                len(osc_full), len(osc_pre), max([e[4] for e in osc_full] or [0]), len(pock), len(anywhere),
                ("  PASS" if o_ok else "  FAIL") if gated else "  (reported)",
                len(waits), max([w[4] for w in waits] or [0]), sum(1 for w in waits if w[5]),
                sum(1 for w in waits if w[6])))
        out("        (O) episodes by mechanism (amendment 2): %s" % (dict(kinds) or "none"))
        for e in osc_full[:8]:
            out("        oscillation %s" % (e,))
        for e in anywhere[:6]:
            out("        pocket-kind oscillation %s" % (e,))
        for w in sorted(waits, key=lambda w: -w[4])[:4]:
            out("        fire-wait %s" % (w,))


# ================================================================================================ A1
def sec_a1():
    out("=" * 100)
    out("P3-2 A1 - DEPOT POCKETS per scenario (UAV-steps PRE / FULL, searcher | tracker), head-on pairs, sweep"
        " targets in the edge band, route clearance violations")
    pairs = (("fx3rZ", "fx3rS"), ("fx3rSZ2", "fx3rS2"), ("fx3rZ", "fx3rA1"))
    for base, arm in pairs:
        A, B = load(base), load(arm)
        if not A or not B:
            continue
        out("  %s -> %s" % (base, arm))
        for sc in "ABCD":
            row = []
            for tag, runs in ((base, A), (arm, B)):
                s_pre = t_pre = s_full = t_full = 0
                for k, d in runs.items():
                    if not k.startswith(sc):
                        continue
                    for full in (False, True):
                        eps, _ = P.pockets(d, pre_terminal=not full)
                        s = sum(e["len"] for e in eps if e["role"] == "victim_searcher")
                        t = sum(e["len"] for e in eps if e["role"] != "victim_searcher")
                        if full:
                            s_full += s
                            t_full += t
                        else:
                            s_pre += s
                            t_pre += t
                row.append("%d/%d | %d/%d" % (s_pre, s_full, t_pre, t_full))
            out("    %s  searcher PRE/FULL | tracker PRE/FULL:  %s   ->   %s" % (sc, row[0], row[1]))
    for tag in ALL_ARMS:
        runs = load(tag)
        if not runs:
            continue
        headon = sweep_bad = sweep_n = clear_bad = clear_n = 0
        for d in runs.values():
            headon += len(head_on_pairs(d))
            for s, byu in (d.get("fx3") or {}).get("ev", {}).items():
                for uid, evs in byu.items():
                    for i, e in enumerate(evs):
                        if e[0] == "S" and e[1]:
                            sweep_n += 1
                            tx, ty = int(e[1][0]), int(e[1][1])
                            if min(tx, 49 - tx, ty, 49 - ty) < 4:
                                sweep_bad += 1
                        if e[0] == "R" and e[3] is not None and i + 1 < len(evs) and evs[i + 1][0] == "H":
                            h = evs[i + 1]
                            fd_here, nb = h[1], h[3]
                            label = e[3][1]
                            if fd_here <= 6 and label not in (WAIT, RETREAT):
                                clear_n += 1
                                if nb[int(e[3][0])][0] < fd_here:
                                    clear_bad += 1
        out("  %-7s head-on searcher pairs (refused into each other's cell >= 10 steps): %d | sweep targets %d, in"
            " the edge band %d | routed steps within 6 of fire %d, closer than d0 %d" % (
                tag, headon, sweep_n, sweep_bad, clear_n, clear_bad))


def head_on_pairs(d):
    """Two victim searchers adjacent, each refused (refused_occupied) on the same >= 10 consecutive steps."""
    rows = d["rows_uav"]
    mu = (d.get("mf2") or {}).get("uav") or []
    run = collections.Counter()
    found = set()
    for t, row in enumerate(rows):
        s = [u for u in row if u[3] == "victim_searcher"]
        m = {x[0]: x for x in (mu[t] if t < len(mu) else ())}
        refused = {u[0]: (u[1], u[2]) for u in s if m.get(u[0]) and m[u[0]][3] == "refused_occupied"}
        ids = sorted(refused)
        live = set()
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = refused[ids[i]], refused[ids[j]]
                if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1:
                    key = (ids[i], ids[j])
                    live.add(key)
                    run[key] += 1
                    if run[key] >= 10:
                        found.add(key)
        for key in list(run):
            if key not in live:
                run[key] = 0
    return found


# ================================================================================================ A2
def leg_gate(d):
    """Return legs from the rows: cycles (a return to a cell the leg had LEFT, repeats collapsed),
    10-frame oscillations (<= 2 cells, >= 2 changes), 10-frame distance-progress stalls (Manhattan to the
    nearest depot cell not below the window start), boxed / open legs."""
    depot = [tuple(c) for c in d["depots"]["cells"]]
    dset = set(depot)
    rows = d["rows_uav"]
    legs = collections.defaultdict(list)
    cur = {}
    for t, row in enumerate(rows):
        for u in row:
            uid, x, y, rtb, dock = u[0], u[1], u[2], u[5], u[6]
            if rtb and not dock:
                cur.setdefault(uid, []).append((t + 1, (x, y)))
            elif uid in cur:
                legs[uid].append((cur.pop(uid), bool(dock)))
    for uid, seq in cur.items():
        legs[uid].append((seq, None))
    res = collections.Counter()
    for uid, lst in legs.items():
        for seq, docked in lst:
            res["legs"] += 1
            cells = [c for _, c in seq]
            col = M_collapse(cells)
            seen = set()
            for i, c in enumerate(col):
                if c in seen:
                    res["cycles"] += 1
                    break
                seen.add(c)
            for i in range(0, len(cells) - 9):
                w = cells[i:i + 10]
                if len(set(w)) <= 2 and sum(1 for k in range(1, 10) if w[k] != w[k - 1]) >= 2:
                    res["osc10"] += 1
                    break
            dist = [min(abs(c[0] - a) + abs(c[1] - b) for a, b in depot) for c in cells]
            for i in range(0, len(dist) - 9):
                if dist[i + 9] >= dist[i]:
                    res["progress_stall10"] += 1
                    break
            if docked is None:
                start = seq[0][0]
                if start + dist[0] + 10 < len(rows):
                    res["open_not_late"] += 1
                else:
                    res["open_late"] += 1
    return res


def M_collapse(cells):
    out_ = []
    for c in cells:
        if not out_ or out_[-1] != c:
            out_.append(c)
    return out_


def sec_a2():
    out("=" * 100)
    out("P3-3 A2 - docked / charging outside a footprint, shared cells, standoffs, outside waits, the return-leg"
        " livelock gate, re-picks, boxed steps, arrivals")
    for tag in ALL_ARMS:
        runs = load(tag)
        if not runs:
            continue
        S = collections.Counter()
        longest_wait = 0
        min_arrival = 999.0
        dock_cells = collections.Counter()
        for d in runs.values():
            dset = {tuple(c) for c in d["depots"]["cells"]}
            prev = {}
            for t, row in enumerate(d["rows_uav"]):
                seen = collections.Counter()
                for u in row:
                    uid, x, y, bat, rtb, dock = u[0], u[1], u[2], u[4], u[5], u[6]
                    seen[(x, y)] += 1
                    if dock and (x, y) not in dset:
                        S["docked_outside"] += 1
                    p = prev.get(uid)
                    if p is not None and bat > p + 1e-9 and (x, y) not in dset:
                        S["charged_outside"] += 1
                    prev[uid] = bat
                S["shared"] += sum(1 for v in seen.values() if v > 1)
            n, w = M.standoffs(d)
            S["std_legs"] += n
            S["standoffs"] += len(w)
            longest_wait = max(longest_wait, outside_wait(d))
            S.update(leg_gate(d))
            for uid, r in ((d.get("fx3") or {}).get("rtb") or {}).items():
                S["boxed"] += int(r.get("boxed", 0) or 0)
                for leg in r.get("log") or []:
                    S["repicks"] += int(leg.get("repicks", 0) or 0)
                    if leg.get("arrival_level") is not None:
                        min_arrival = min(min_arrival, float(leg["arrival_level"]))
                    if leg.get("dock_cell") is not None:
                        c = tuple(leg["dock_cell"])
                        dock_cells["edge" if on_edge(c, dset) else "interior"] += 1
        out("  %-7s docked outside %d | charged outside %d | cells shared %d | legs %d standoffs %d | longest outside"
            " wait %d | cycles %d osc10 %d progress-stall10 %d | open legs not late %d (late %d) | re-picks %d boxed"
            " steps %d | dock cells %s | min arrival %.1f" % (
                tag, S["docked_outside"], S["charged_outside"], S["shared"], S["std_legs"], S["standoffs"], longest_wait,
                S["cycles"], S["osc10"], S["progress_stall10"], S["open_not_late"], S["open_late"], S["repicks"],
                S["boxed"], dict(dock_cells), min_arrival))


def on_edge(c, dset):
    return any((c[0] + dx, c[1] + dy) not in dset for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def outside_wait(d):
    depot = {tuple(c) for c in d["depots"]["cells"]}
    best = 0
    run = {}
    prev = {}
    for row in d["rows_uav"]:
        for u in row:
            uid, x, y, rtb, dock = u[0], u[1], u[2], u[5], u[6]
            c = (x, y)
            near = c not in depot and any(abs(x - a) + abs(y - b) == 1 for a, b in depot)
            run[uid] = run.get(uid, 0) + 1 if (rtb and not dock and near and prev.get(uid) == c) else 0
            best = max(best, run[uid])
            prev[uid] = c
    return best


# ================================================================================================ B
def b_run(d, window=None):
    rows = d["rows_uav"]
    end = pre_end(d)
    if window is not None:
        end = min(end, window)
    st = collections.Counter()
    returns = collections.Counter()
    roles = {}
    prev = {}
    min_ret = 999.0
    for t, row in enumerate(rows):
        s = [u for u in row if u[3] == "victim_searcher"]
        fly = [u for u in s if not u[5] and not u[6]]
        pre = t + 1 <= end
        if s and not fly:
            st["gap_full"] += 1
            st["gap_pre"] += pre
        for u in row:
            uid, role, bat, rtb, dock = u[0], u[3], u[4], u[5], u[6]
            roles[uid] = role
            if role == "victim_searcher":
                if rtb and not dock:
                    st["s_ret_full"] += 1
                    st["s_ret_pre"] += pre
                if not rtb and not dock:
                    st["s_fly_full"] += 1
                    st["s_fly_pre"] += pre
            if rtb and not prev.get(uid):
                returns[uid] += 1
            if rtb and not dock:
                min_ret = min(min_ret, bat)
            if bat <= 0:
                st["zero_battery"] += 1
            prev[uid] = bool(rtb)
    return st, returns, roles, min_ret


def sec_b():
    out("=" * 100)
    out("P3-4 SCENARIO B, FOUR WAYS (B1 + A1 + A2 on in all): gap, returns, B3 firings, lowest return battery,"
        " stranding, outcomes; the STOP rule B23 vs B0")
    base = load("fx3rB0")
    for tag in ("fx3rB0", "fx3rB2", "fx3rB3", "fx3rB23"):
        runs = load(tag)
        if not runs:
            continue
        agg = collections.Counter()
        ret_role = collections.defaultdict(list)
        min_ret = 999.0
        strand = []
        delay_steps = delay_eps = delay_runs = 0
        below_floor = 0
        after_delay_arrivals = []
        outc = collections.Counter()
        for k, d in runs.items():
            st, returns, roles, mr = b_run(d)
            agg.update(st)
            for uid, role in roles.items():
                ret_role[role].append(returns.get(uid, 0))
            min_ret = min(min_ret, mr)
            rtb = (d.get("fx3") or {}).get("rtb") or {}
            run_delays = 0
            for uid, r in rtb.items():
                run_delays += int(r.get("delay_steps", 0) or 0)
                dl = r.get("delay") or []
                prev_step = None
                ends = []
                for e in dl:
                    if prev_step is None or e["step"] != prev_step + 1:
                        delay_eps += 1
                        if prev_step is not None:
                            ends.append(prev_step)
                    prev_step = e["step"]
                    if e["level"] <= e["floor"]:
                        below_floor += 1
                if prev_step is not None:
                    ends.append(prev_step)
                for last in ends:
                    for leg in r.get("log") or []:
                        if leg.get("trigger_step") is not None and leg["trigger_step"] >= last:
                            after_delay_arrivals.append(leg.get("arrival_level"))
                            break
                for leg in r.get("log") or []:
                    if leg.get("arrival_step") is None:
                        start = leg.get("trigger_step") or 0
                        if start + int(leg.get("trigger_distance") or 0) + 10 < len(d["rows_uav"]):
                            strand.append((k, uid, start))
            delay_steps += run_delays
            delay_runs += run_delays > 0
            if st["zero_battery"]:
                strand.append((k, "battery 0"))
            e = d.get("eval") or {}
            outc["rescued"] += e.get("rescued") or 0
            outc["dead"] += e.get("dead") or 0
            outc["nd"] += e.get("never_detected") or 0
            outc["no_term"] += d.get("terminal_step") is None
        rr = {role: "%.2f %s" % (sum(v) / float(len(v)), dict(sorted(collections.Counter(v).items())))
              for role, v in sorted(ret_role.items())}
        arr = [a for a in after_delay_arrivals if a is not None]
        out("  %-7s runs %2d | gap PRE %d FULL %d | searcher flying PRE %d FULL %d | searcher return-leg PRE %d FULL %d"
            % (tag, len(runs), agg["gap_pre"], agg["gap_full"], agg["s_fly_pre"], agg["s_fly_full"], agg["s_ret_pre"],
               agg["s_ret_full"]))
        out("          returns per UAV %s | B3 fired %d UAV-steps, %d episodes, in %d of %d runs (delays at/below the"
            " floor %d) | returns started after a delay arrived at min %s (LOW 30)" % (
                rr, delay_steps, delay_eps, delay_runs, len(runs), below_floor, min(arr) if arr else "-"))
        out("          lowest battery on a return %.1f | stranded (battery 0 or a leg that never completes, not late) %s"
            " | rescued %d dead %d never_detected %d | runs with no terminal step %d" % (
                min_ret, strand or "none", outc["rescued"], outc["dead"], outc["nd"], outc["no_term"]))
        if tag != "fx3rB0" and base:
            G = C = Gf = Cf = n = 0
            for k in sorted(set(base) & set(runs)):
                a, b = base[k], runs[k]
                w = min(a.get("terminal_step") or 361, b.get("terminal_step") or 361) - 1
                sa, _, _, _ = b_run(a, window=w)
                sb, _, _, _ = b_run(b, window=w)
                G += sa["gap_pre"] - sb["gap_pre"]
                C += sa["s_fly_pre"] - sb["s_fly_pre"]
                sfa, _, _, _ = b_run(a)
                sfb, _, _, _ = b_run(b)
                Gf += sfa["gap_full"] - sfb["gap_full"]
                Cf += sfa["s_fly_full"] - sfb["s_fly_full"]
                n += 1
            verdict = ("STOP (C > G)" if C > G else "PASS (C <= G)") if tag == "fx3rB23" else ("C <= G" if C <= G else "C > G")
            out("          vs fx3rB0 (%d pairs, common pre-terminal window): gap closed G %d, searcher flying lost C %d"
                " -> %s | FULL G %d C %d" % (n, G, C, verdict, Gf, Cf))


def sec_b1checks():
    out("=" * 100)
    out("P3-5 SESSION 1's SCENARIO-B CHECKS, THE NEW TEAM (fx3rB0 and fx3rB23)")
    for tag in ("fx3rB0", "fx3rB23"):
        runs = load(tag)
        if not runs:
            continue
        first = collections.defaultdict(set)
        firsts = collections.defaultdict(list)
        later = collections.defaultdict(list)
        arrivals_missing = []
        min_air = 999.0
        trig = collections.Counter()
        bat_reasons = emerg = 0
        for k, d in runs.items():
            for u in d["rows_uav"][0]:
                first[u[3]].add(round(u[4], 3))
            for row in d["rows_uav"]:
                for u in row:
                    if not u[6]:
                        min_air = min(min_air, u[4])
            for uid, r in ((d.get("fx3") or {}).get("rtb") or {}).items():
                role = next((u[3] for u in d["rows_uav"][0] if u[0] == uid), "?")
                for i, leg in enumerate(r.get("log") or []):
                    rec = (leg.get("trigger_step"), round(leg.get("trigger_level") or 0, 1), leg.get("trigger_distance"))
                    (firsts if i == 0 else later)[role].append(rec)
                    if leg.get("arrival_step") is None:
                        start = leg.get("trigger_step") or 0
                        late = start + int(leg.get("trigger_distance") or 0) + 10 >= len(d["rows_uav"])
                        arrivals_missing.append((k, uid, start, "late" if late else "NOT LATE"))
            for tr in d.get("rows_trig") or []:
                for key, v in (tr or {}).items():
                    if "BATTERY" in key:
                        trig[key] += v
            for dec in d.get("rows_dec") or []:
                if "battery" in " ".join(str(w) for w in (dec.get("why") or [])):
                    bat_reasons += 1
                emerg += str(dec.get("mode", "")) == "emergency"
        out("  %-7s battery after step 1 by role %s" % (tag, {k: sorted(v) for k, v in first.items()}))
        for role in sorted(firsts):
            fs = sorted(firsts[role])
            out("          first returns %-15s (step, level, distance): %s" % (role, fs[:10] + (["..."] if len(fs) > 10 else [])))
            out("          later returns %-15s steps %s" % (role, sorted(x[0] for x in later[role])))
        out("          trips without an arrival %s | minimum in-flight battery %.1f | LOW/CRITICAL trigger instances %s |"
            " battery fail-safe reasons %d | emergency steps %d" % (
                arrivals_missing or "none", min_air, dict(trig) or 0, bat_reasons, emerg))


# ================================================================================================ exposure
def sec_exposure():
    out("=" * 100)
    out("P3-6 DRONE STEPS IN FIRE (UAV-steps on a burning cell; smoke separately) - bounds searcher +1.0, all-UAV"
        " +0.5 points")
    for base, arm in (("fx3rZ", "fx3rS"), ("fx3rSZ2", "fx3rS2"), ("fx3rZ", "fx3rA1"), ("fx3rZ", "fx3rA2")):
        vals = []
        for tag in (base, arm):
            S = collections.Counter()
            for d in load(tag).values():
                for row in (d.get("mf2") or {}).get("uav") or []:
                    for u in row:
                        if len(u) < 6 or not isinstance(u[4], int):
                            continue
                        S["n"] += 1
                        S["f"] += u[4]
                        S["sm"] += u[5]
                        if u[1] == "victim_searcher":
                            S["ns"] += 1
                            S["fs"] += u[4]
                            S["sms"] += u[5]
            vals.append(S)
        if not vals[0]["n"] or not vals[1]["n"]:
            continue
        p = lambda S, a, b: 100.0 * S[a] / S[b] if S[b] else 0.0
        ds = p(vals[1], "fs", "ns") - p(vals[0], "fs", "ns")
        da = p(vals[1], "f", "n") - p(vals[0], "f", "n")
        out("  %s -> %s: in fire searcher %.2f%% -> %.2f%% (%+.2f) all-UAV %.2f%% -> %.2f%% (%+.2f) | smoke searcher"
            " %.2f%% -> %.2f%% all-UAV %.2f%% -> %.2f%%  %s" % (
                base, arm, p(vals[0], "fs", "ns"), p(vals[1], "fs", "ns"), ds, p(vals[0], "f", "n"), p(vals[1], "f", "n"),
                da, p(vals[0], "sms", "ns"), p(vals[1], "sms", "ns"), p(vals[0], "sm", "n"), p(vals[1], "sm", "n"),
                "PASS" if ds <= 1.0 and da <= 0.5 else "STOP"))


# ================================================================================================ yields
def sec_yields():
    out("=" * 100)
    out("P3-10 THE SESSION-2 YIELD RULES (a yield of step t decided on row t-1): violations = a yielder returning /"
        " docked / in the depot approach area (Manhattan 3) or without a lower-id airborne non-returning partner"
        " within 2; > 3 in a row; holds / stays that moved")
    for tag in ("fx3rZ", "fx3rS", "fx3rS2", "fx3rB23"):
        runs = load(tag)
        if not runs:
            continue
        c = collections.Counter()
        for d in runs.values():
            depot = [tuple(x) for x in d["depots"]["cells"]]
            rows = d["rows_uav"]
            m = (d.get("mf2") or {}).get("uav") or []
            streak = collections.Counter()
            for t in range(1, len(rows)):
                prev = {u[0]: u for u in rows[t - 1]}
                cur = {u[0]: u for u in rows[t]}
                for mu in (m[t] if t < len(m) else ()):
                    uid = mu[0]
                    p, q = prev.get(uid), cur.get(uid)
                    if mu[2] == 1:
                        c["stays"] += 1
                        if p and q and (q[1], q[2]) != (p[1], p[2]) and not q[5]:
                            c["stay_moved"] += 1
                    if mu[9] == 1:
                        c["yields"] += 1
                        streak[uid] += 1
                        if streak[uid] > 3:
                            c["long"] += 1
                        if p is None or p[5] or p[6]:
                            c["bad"] += 1
                            continue
                        in_area = min(abs(p[1] - a) + abs(p[2] - b) for a, b in depot) <= 3
                        partner = [o for o in rows[t - 1] if o[0] != uid and int(o[0]) < int(uid) and not o[5]
                                   and not o[6] and abs(o[1] - p[1]) + abs(o[2] - p[2]) <= 2]
                        if in_area or not partner or all(min(abs(o[1] - a) + abs(o[2] - b) for a, b in depot) <= 3
                                                         for o in partner):
                            c["bad"] += 1
                        if q and (q[1], q[2]) != (p[1], p[2]):
                            c["yield_moved"] += 1
                    else:
                        streak[uid] = 0
        out("  %-7s yields %d, violations %d, > 3 in a row %d, yields that moved %d | stays %d, moved %d" % (
            tag, c["yields"], c["bad"], c["long"], c["yield_moved"], c["stays"], c["stay_moved"]))


# ================================================================================================ attribution
def sec_attrib():
    out("=" * 100)
    out("P3-11 EACH ITEM ALONE vs fx3rZ - the first differing UAV row (the berth column, 7, excluded: A2 stops the"
        " per-step berth write outside a leg - a recorder difference)")
    Z = load("fx3rZ")
    for tag in ("fx3rA1", "fx3rA2"):
        runs = load(tag)
        for k in sorted(set(Z) & set(runs)):
            a, b = Z[k]["rows_uav"], runs[k]["rows_uav"]
            first = None
            for t in range(min(len(a), len(b))):
                ra = [u[:7] + u[8:] for u in a[t]]
                rb = [u[:7] + u[8:] for u in b[t]]
                if ra != rb:
                    diff = [(x, y) for x, y in zip(ra, rb) if x != y]
                    first = (t + 1, diff[0][1][0], diff[0][1][3], diff[0][0][7], diff[0][1][7])
                    break
            out("  %-6s %s first differing UAV row: %s" % (tag, k, first))


# ================================================================================================ outcomes
def sec_outcomes():
    out("=" * 100)
    out("OUTCOMES (reported, never gated; 16-run arms are a SCREEN) - rescued / dead / never_detected / no terminal,"
        " by arm and by wind")
    for tag in ALL_ARMS:
        runs = load(tag)
        if not runs:
            continue
        tot = collections.Counter()
        byw = collections.defaultdict(collections.Counter)
        for k, d in runs.items():
            e = d.get("eval") or {}
            w = k.split("_")[1]
            for key, val in (("r", e.get("rescued") or 0), ("d", e.get("dead") or 0), ("n", e.get("never_detected") or 0),
                             ("t", int(d.get("terminal_step") is None)), ("ff", e.get("firefighter_deaths") or 0)):
                tot[key] += val
                byw[w][key] += val
        out("  %-7s %d/%d/%d nt %d ffd %d | %s" % (tag, tot["r"], tot["d"], tot["n"], tot["t"], tot["ff"],
                                               " ".join("%s %d/%d/%d" % (w, byw[w]["r"], byw[w]["d"], byw[w]["n"])
                                                        for w in "NSEW" if w in byw)))


def sec_rbgate():
    out("=" * 100)
    out("P3-8 ROUTE_BLOCKED GATE - fx3rgS (shipped) vs fx3gR (a5a496db); known losses east/707, south/101, 202, 404")
    pooled = collections.Counter()
    for sh, w in (("a", "east"), ("b", "east"), ("c", "east"), ("s", "south")):
        fr = os.path.join(HERE, "_rblatch_camp2_fx3gR%s_D_%s.json" % (sh, w))
        fs = os.path.join(HERE, "_rblatch_camp2_fx3rgS%s_D_%s.json" % (sh, w))
        if not (os.path.exists(fr) and os.path.exists(fs)):
            out("  shard %s MISSING" % sh)
            continue
        z, s = json.load(open(fr, encoding="utf-8")), json.load(open(fs, encoding="utf-8"))
        ez = {int(e["seed"]): e for e in (z.get("evals") or [])}
        es_ = {int(e["seed"]): e for e in (s.get("evals") or [])}
        known = {("east", 707), ("south", 101), ("south", 202), ("south", 404)}
        loss, gain, new = [], [], []
        for seed in sorted(set(ez) & set(es_)):
            rz, rs = ez[seed].get("rescued"), es_[seed].get("rescued")
            if rs < rz:
                loss.append((seed, rz, rs))
                if (w, seed) not in known:
                    new.append(seed)
            elif rs > rz:
                gain.append((seed, rz, rs))
        out("  shard %s %-5s rescued %d -> %d | losses %s gains %s | NEW %s | recoveries %d -> %d | latched %d" % (
            sh, w, sum(e["rescued"] for e in ez.values()), sum(e["rescued"] for e in es_.values()), loss, gain,
            new or "none", len(z.get("recoveries") or []), len(s.get("recoveries") or []), len(s.get("latched") or [])))
        pooled["new"] += len(new)
        pooled["rec"] += len(s.get("recoveries") or [])
        pooled["latched"] += len(s.get("latched") or [])
        pooled["r0"] += sum(e["rescued"] for e in ez.values())
        pooled["r1"] += sum(e["rescued"] for e in es_.values())
    out("  POOLED rescued %d -> %d | NEW losses %d | recoveries %d (> 0) | latched %d  => %s" % (
        pooled["r0"], pooled["r1"], pooled["new"], pooled["rec"], pooled["latched"],
        "PASS" if pooled["new"] == 0 and pooled["rec"] > 0 and pooled["latched"] == 0 else "FAIL"))


# ================================================================================================ ROUND 2
R2_ON = ("fx3rS", "fx3rS2", "fx3rA1", "fx3rB0", "fx3rB2", "fx3rB3", "fx3rB23", "fx3rW", "fx3rW2")   # (a)+(b) on
ROUTE_OWNED_END = ("_fire_route",)
FIRE_LABELS = (WAIT, RETREAT)


def switch_on(d, name, default=1):
    v = (d.get("params") or {}).get(name, default)
    return not (v == 0 or v == "0" or v is False)


def edge_allowed(c, n, corner, size=50):
    """The searcher edge filter as a pure (cell, next) predicate (penetration rule / margin 3)."""
    xm = ym = size - 1
    if corner:
        def pen(x, y):
            return max(0, 4 - min(x, xm - x)) + max(0, 4 - min(y, ym - y))
        hp = pen(*c)
        return hp == 0 or pen(*n) < hp
    before = min(c[0], c[1], xm - c[0], ym - c[1])
    after = min(n[0], n[1], xm - n[0], ym - n[1])
    return not (before <= 3 and after <= before)


def route_owned(label):
    label = str(label or "")
    return label.endswith(ROUTE_OWNED_END) or label in FIRE_LABELS


def sec_ident2():
    out("=" * 100)
    out("R2-IDENT 2 - the two new switches 0 == fix3a Part 2 shipped (a1373935): fx3rX vs fx3S")
    s, n, lines = probe_ident("fx3S", "fx3rX")
    out("  probe fx3rX vs fx3S: %d/%d identical on every behavioural field and every mf2 section  %s" % (
        s, n, "PASS" if s == n == 16 else "FAIL"))
    for ln in lines:
        out(ln)


def sec_owner():
    out("=" * 100)
    out("R2-(A) ONE OWNER (addendum B): (i) executed searcher labels with hazard_retreat / _hazard_escape; (ii) gate calls"
        " whose direction changed without a route-owned label; (iii) searcher moves the edge filter forbids (by kind)")
    for tag in ALL_ARMS:
        runs = load(tag)
        if not runs:
            continue
        i_bad = ii_bad = gate_calls = handoffs = 0
        iii = collections.Counter()
        moves = 0
        for key, d in runs.items():
            corner = switch_on(d, "SEARCHER_CORNER_ESCAPE")
            prev = {}
            for t, row in enumerate(d["rows_uav"]):
                for u in row:
                    if u[3] != "victim_searcher":
                        continue
                    lab = str(u[8] or "")
                    if "hazard_retreat" in lab or "_hazard_escape" in lab:
                        i_bad += 1
                    pos = (int(u[1]), int(u[2]))
                    p = prev.get(u[0])
                    if p is not None and p[0] != pos and not p[1] and not u[5] and not u[6]:
                        moves += 1
                        if not edge_allowed(p[0], pos, corner):
                            kind = ("route-owned" if route_owned(lab) or "retarget_to_interior" in lab
                                    or lab == "victim_search_escape_bfs" else lab)
                            iii[kind] += 1
                    prev[u[0]] = (pos, bool(u[5]) or bool(u[6]))
            for step, per in ((d.get("fx3") or {}).get("ev") or {}).items():
                for uid, evs in per.items():
                    for e in evs:
                        if e[0] != "G":
                            continue
                        gate_calls += 1
                        if route_owned(e[4]):
                            handoffs += 1
                        elif e[3] != e[1]:
                            ii_bad += 1
        gated = tag in R2_ON
        if gated:
            verdict = "PASS" if (i_bad == 0 and ii_bad == 0 and sum(iii.values()) == 0) else "FAIL"   # addendum C
        else:
            verdict = "(reported)"
        out("  %-7s (i) %d | (ii) %d of %d gate calls (handed to the route %d) | (iii) forbidden moves %s of %d  %s" % (
            tag, i_bad, ii_bad, gate_calls, handoffs, dict(iii) or 0, moves, verdict))


def ws_series(d):
    ws = (d.get("fx3") or {}).get("ws") or {}
    for step in sorted(ws, key=lambda k: int(k)):
        for uid, w in (ws[step] or {}).items():
            yield int(step), uid, w


def reconstruct_latch_waits(d):
    """(W) addendum C, per LATCH as the implementation defines it: a maximal run of steps whose post-step
    fire_route_target is set and stays within Manhattan 2 of the previous step's value (the stored goal follows a
    shift); None, a jump, or a give-up (route_give_ups rising) ends it. The no-path steps are counted from the rows'
    FIRE_* labels, return-leg / docked steps excluded as b1 does - independent of the implementation's counter. Returns [(uid, goal, count)]."""
    ws = (d.get("fx3") or {}).get("ws") or {}
    labels = {}
    before = {}                             # the DECISION-TIME state of step t = the post-step row of t - 1
    for t, row in enumerate(d["rows_uav"]):
        for u in row:
            if u[3] == "victim_searcher":
                # b1: a step decided on a return-to-base leg (or docked) is not counted - agents.py steers it
                labels[(t + 1, u[0])] = "" if before.get(u[0]) else str(u[8] or "")
        for u in row:
            before[u[0]] = bool(u[5]) or bool(u[6])
    out = []
    for uid in sorted({uid for (_s, uid) in labels}):
        cur, count, gu_prev = None, 0, 0
        for step in range(1, len(d["rows_uav"]) + 1):
            w = (ws.get(str(step)) or {}).get(uid) or {}
            gu = int(w.get("route_give_ups") or 0)
            raw = w.get("fire_route_target")
            t = (int(raw[0]), int(raw[1])) if isinstance(raw, list) and len(raw) >= 2 else None
            lab_fire = labels.get((step, uid)) in FIRE_LABELS
            if gu > gu_prev:                    # a give-up this step: the step closes the latch it belonged to
                if cur is not None:
                    out.append((uid, cur, count + int(lab_fire)))
                cur, count = t, 0
            elif t is None or cur is None or abs(t[0] - cur[0]) + abs(t[1] - cur[1]) > 2:
                if cur is not None:
                    out.append((uid, cur, count))
                cur, count = t, int(lab_fire and t is not None)
            else:
                cur = t
                count += int(lab_fire)
            gu_prev = gu
        if cur is not None:
            out.append((uid, cur, count))
    return out


def reconstruct_target_chains(d):
    """REPORTED (the reviewers' 'each latch bounded, total idling not'): no-path steps per TARGET across latches -
    a chain of route-event targets within Manhattan 2, cut only at a give-up."""
    ev = (d.get("fx3") or {}).get("ev") or {}
    ws = (d.get("fx3") or {}).get("ws") or {}
    labels = {}
    for t, row in enumerate(d["rows_uav"]):
        for u in row:
            if u[3] == "victim_searcher":
                labels[(t + 1, u[0])] = str(u[8] or "")
    out = []
    for uid in sorted({uid for (_s, uid) in labels}):
        anchor, count, gu_prev = None, 0, 0
        for step in range(1, len(d["rows_uav"]) + 1):
            gu = int(((ws.get(str(step)) or {}).get(uid) or {}).get("route_give_ups") or 0)
            targets = [e[1] for e in ((ev.get(str(step)) or {}).get(uid) or []) if e[0] == "R" and e[1]]
            if targets:
                t = (int(round(float(targets[-1][0]))), int(round(float(targets[-1][1]))))
                if anchor is None or abs(t[0] - anchor[0]) + abs(t[1] - anchor[1]) > 2:
                    if anchor is not None:
                        out.append((uid, anchor, count))
                    anchor, count = t, 0
                else:
                    anchor = t
            if labels.get((step, uid)) in FIRE_LABELS and anchor is not None:
                count += 1
            if gu > gu_prev:
                if anchor is not None:
                    out.append((uid, anchor, count))
                anchor, count = None, 0
            gu_prev = gu
        if anchor is not None:
            out.append((uid, anchor, count))
    return out


def wait_hazard_split(d):
    """FIRE_WAIT steps with a hazard (fire or smoke) within 6 of the searcher (the probe's H view at that step)
    vs none (edge-band / unreachable-goal waits)."""
    ev = (d.get("fx3") or {}).get("ev") or {}
    near = far = unknown = 0
    for t, row in enumerate(d["rows_uav"]):
        for u in row:
            if u[3] != "victim_searcher" or str(u[8] or "") != WAIT:
                continue
            hs = [e for e in ((ev.get(str(t + 1)) or {}).get(u[0]) or []) if e[0] == "H"]
            if not hs:
                unknown += 1
            elif min(int(hs[-1][1]), int(hs[-1][2])) <= 6:
                near += 1
            else:
                far += 1
    return near, far, unknown


def sec_bound():
    out("=" * 100)
    out("R2-(B)/(W) THE BOUNDED WAIT (addendum C): give-ups, refusal steps / events, the RECONSTRUCTED per-latch no-path"
        " count (FAIL if > W in a gated arm), repeat give-ups (within Manhattan 6 of an earlier one, same UAV), the"
        " largest per-UAV total of no-path steps, fire-wait steps split by a hazard within 6")
    for tag in ALL_ARMS:
        runs = load(tag)
        if not runs:
            continue
        gu = rf_ev = rf_st = runs_gu = repeat = 0
        worst, over, idle_max, chain_max = 0, 0, 0, 0
        limit = None
        near = far = unk = 0
        for key, d in runs.items():
            limit = int((d.get("params") or {}).get("SEARCHER_ROUTE_WAIT_LIMIT", 20) or 20)
            last = {}
            for step, uid, w in ws_series(d):
                last[uid] = w
            g = sum(int(w.get("route_give_ups") or 0) for w in last.values())
            gu += g
            runs_gu += g > 0
            rf_ev += sum(int(w.get("route_refusals") or 0) for w in last.values())
            rf_st += sum(int(w.get("route_refusal_steps") or 0) for w in last.values())
            for w in last.values():
                logs = w.get("route_give_up_log") or []
                for i, a in enumerate(logs):
                    if any(abs(a[1] - b[1]) + abs(a[2] - b[2]) <= 6 for b in logs[:i]):
                        repeat += 1
            for uid, anchor, count in reconstruct_latch_waits(d):
                worst = max(worst, count)
                over += count > limit
            for uid, anchor, count in reconstruct_target_chains(d):
                chain_max = max(chain_max, count)
            per_uav = collections.Counter()
            for row in d["rows_uav"]:
                for u in row:
                    if u[3] == "victim_searcher" and str(u[8] or "") in FIRE_LABELS:
                        per_uav[u[0]] += 1
            idle_max = max([idle_max] + list(per_uav.values()))
            n_, f_, k_ = wait_hazard_split(d)
            near, far, unk = near + n_, far + f_, unk + k_
        gated = tag in R2_ON
        verdict = ("PASS" if over == 0 else "FAIL") if gated else "(reported)"
        out("  %-7s W=%s | give-ups %d in %d of %d runs, repeat-region give-ups %d | refusals: %d steps (%d events) | "
            "reconstructed per-latch no-path max %d, latches over W %d  %s | per-target chain max %d | per-UAV no-path steps max %d | wait steps"
            " hazard-near %d, no hazard within 6 %d, no view %d" % (
                tag, limit if gated else "-", gu, runs_gu, len(runs), repeat, rf_st, rf_ev, worst, over, verdict,
                chain_max, idle_max, near, far, unk))


def sec_cs():
    out("=" * 100)
    out("R2-(C) C/S 9610: victim_0's [Victim Detection] step and the terminal step (a5a496db 344 / none; pre-latch"
        " 188 / 232; Part 3 latched 337 / none; the smoke of the reviewed code 351 / none - addendum C)")
    for tag in ("fx3v", "fx3S", "fx3rX", "fx3rS", "fx3rA1", "fx3rW"):
        d = load(tag).get("C_S")
        if d is None:
            out("  %-7s (no run)" % tag)
            continue
        fin = [v for v in d["rows_vic"][-1] if v[0] == "victim_0"]
        out("  %-7s victim_0 detected at %s, final %s | terminal step %s" % (
            tag, (d.get("_det") or {}).get("victim_0"), (fin[0][4] or fin[0][3]) if fin else "?",
            d.get("terminal_step")))


def sec_edgecov():
    out("=" * 100)
    out("R2-(E) EDGE COVERAGE (outputs/_fx3b_edgecov.py): ring = edge distance <= 3; observed = within 8 of any UAV")
    import _fx3b_edgecov as E
    for tag in ("fx3v", "fx3S") + ALL_ARMS:
        res = [E.analyse(d) for _k, d in E.runs(tag)]
        if not res:
            continue
        m = len(res)
        sr = sum(r["s_ring"] for r in res)
        sf = sum(r["s_fly"] for r in res)
        never = [v for r in res for v in r["never"]]
        out("  %-7s ring observed PRE %.1f%% FULL %.1f%% | interior PRE %.1f%% FULL %.1f%% | searcher steps in the ring "
            "%.1f%% | victims undetected in the ring %d (%d steps) | never detected %s" % (
                tag, 100 * sum(r["ring_pre"] for r in res) / m, 100 * sum(r["ring_full"] for r in res) / m,
                100 * sum(r["inner_pre"] for r in res) / m, 100 * sum(r["inner_full"] for r in res) / m,
                100.0 * sr / max(1, sf), sum(len(r["ring_undet"]) for r in res),
                sum(sum(r["ring_undet"].values()) for r in res), never or "none"))


def sec_rbgate_w():
    out("=" * 100)
    out("R2-(R) SENSITIVITY route_blocked fx3rgW (W = 39) vs fx3gR - reported, never gated")
    tot = collections.Counter()
    known = {("east", 707), ("south", 101), ("south", 202), ("south", 404)}
    for sh, w in (("a", "east"), ("b", "east"), ("c", "east"), ("s", "south")):
        fr = os.path.join(HERE, "_rblatch_camp2_fx3gR%s_D_%s.json" % (sh, w))
        fw = os.path.join(HERE, "_rblatch_camp2_fx3rgW%s_D_%s.json" % (sh, w))
        if not (os.path.exists(fr) and os.path.exists(fw)):
            out("  shard %s MISSING" % sh)
            continue
        z, s_ = json.load(open(fr, encoding="utf-8")), json.load(open(fw, encoding="utf-8"))
        ez = {int(e["seed"]): e for e in z.get("evals") or []}
        ew = {int(e["seed"]): e for e in s_.get("evals") or []}
        new = [sd for sd in sorted(set(ez) & set(ew))
               if ew[sd]["rescued"] < ez[sd]["rescued"] and (w, sd) not in known]
        out("  shard %s %-5s rescued %d -> %d | NEW losses %s | latched %d" % (
            sh, w, sum(e["rescued"] for e in ez.values()), sum(e["rescued"] for e in ew.values()), new or "none",
            len(s_.get("latched") or [])))
        tot["new"] += len(new)
    out("  POOLED NEW losses %d" % tot["new"])


def sec_trace():
    out("=" * 100)
    out("R2-(R) TRACE of every NEW fx3rgS loss (addendum C): the probe at 360 steps with the campaign's parameters,"
        " tag fx3rgT<w><seed>; consistency = its statuses at step 240 reproduce the campaign's evaluation")
    found = False
    for f in sorted(glob.glob(os.path.join(HERE, "_sd_fx3rgT*.json"))):
        if ".json." in os.path.basename(f):
            continue
        found = True
        tag = os.path.basename(f)[4:-5]
        d = load_one(f)
        w = "east" if tag[6] == "e" else "south"
        seed = int(tag[7:])
        camp = None
        for g in glob.glob(os.path.join(HERE, "_rblatch_camp2_fx3rgS*_D_%s.json" % w)):
            for e in json.load(open(g, encoding="utf-8")).get("evals") or []:
                if int(e["seed"]) == seed:
                    camp = e
        row240 = d["rows_vic"][239] if len(d["rows_vic"]) >= 240 else []
        st240 = collections.Counter((v[4] or v[3]) for v in row240)
        consistent = camp is not None and st240.get("rescued", 0) == camp.get("rescued") and \
            st240.get("dead", 0) == camp.get("dead")
        out("  %s: campaign at 240 rescued %s dead %s candidate %s | probe at 240 %s -> %s" % (
            tag, camp and camp.get("rescued"), camp and camp.get("dead"), camp and camp.get("candidate"),
            dict(st240), "CONSISTENT" if consistent else "NOT COMPARABLE"))
        for v in d["rows_vic"][-1]:
            vid = v[0]
            s240 = next(((x[4] or x[3]) for x in row240 if x[0] == vid), None)
            rescued_at = next((t + 1 for t, row in enumerate(d["rows_vic"])
                               for x in row if x[0] == vid and (x[4] or x[3]) == "rescued"), None)
            out("    %s: detected %s | at 240 %s | at 360 %s | rescued at %s" % (
                vid, (d.get("_det") or {}).get(vid), s240, v[4] or v[3], rescued_at))
    if not found:
        out("  (no trace runs)")


def load_one(path):
    d = json.load(open(path, encoding="utf-8"))
    det = {}
    st = path[:-5] + ".stdout.txt"
    if os.path.exists(st):
        for line in open(st, encoding="utf-8", errors="replace"):
            m = DET_RE.match(line.strip())
            if m and m.group(3) not in det:
                det[m.group(3)] = int(m.group(1))
    d["_det"] = det
    return d


SECTIONS = {"prov": sec_prov, "ident": sec_ident, "gates": sec_gates, "a1": sec_a1, "a2": sec_a2, "b": sec_b,
            "b1checks": sec_b1checks, "exposure": sec_exposure, "yields": sec_yields, "attrib": sec_attrib,
            "outcomes": sec_outcomes, "rbgate": sec_rbgate, "ident2": sec_ident2, "owner": sec_owner,
            "bound": sec_bound, "cs": sec_cs, "edgecov": sec_edgecov, "rbgate_w": sec_rbgate_w, "trace": sec_trace}


def main():
    want = [a for a in sys.argv[1:] if not a.startswith("--")] or list(SECTIONS)
    for w in want:
        SECTIONS[w]()


if __name__ == "__main__":
    main()
