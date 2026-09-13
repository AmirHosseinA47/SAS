"""Blind independent checker for the dcd4 analysis spec.

Reads committed harness JSONs ONE AT A TIME, reduces each to a small per-run
summary, then aggregates per (tag, sample). No simulation, no writes outside
the scratchpad.
"""
import glob
import json
import os
import sys
from collections import Counter

OUT = r"E:\Projects\SAS\outputs"
SCR = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(SCR, "dcd4_blind_results.json")
H = W = 50
N_STEPS = 240

CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])

TAGS_BOTH = ["dcoff", "dcA", "dcB", "dcC", "dcD",
             "dfzero", "dfA", "dfB", "dfC", "dfD", "dfkill"]
TAGS_CANON_ONLY = ["dfm2ref", "dfm2fix", "ihbase"]
TAGS_FRESH_ONLY = ["dimfreshbase"]


def fpath(tag, wind, roles, seed):
    rr = "def" if roles == "default" else "half"
    return os.path.join(OUT, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def tup(p):
    return None if p is None else (int(p[0]), int(p[1]))


def footprints(bs):
    """list of (x0, y0, size) per depot; cells (x0+i, y0+j), i,j in [0,size)."""
    if not bs:
        return []
    size = int(bs["size"])
    deps = bs.get("depots") or [bs["origin"]]
    return [(int(o[0]), int(o[1]), size) for o in deps]


def in_fp(c, fp):
    x0, y0, s = fp
    return c is not None and x0 <= c[0] < x0 + s and y0 <= c[1] < y0 + s


def in_any_fp(c, fps):
    return any(in_fp(c, f) for f in fps)


def ranked_cells(fp):
    x0, y0, s = fp
    cells = [(x0 + i, y0 + j) for i in range(s) for j in range(s)]
    return sorted(cells, key=lambda c: (-min(c[0], c[1], H - 1 - c[0], W - 1 - c[1]), c[0], c[1]))


def state_class(bs):
    if bs is None:
        return "none"
    if bs == "":
        return "flying"
    if bs == "returning":
        return "returning"
    return "docked_charging"  # "charging" (mode>=3) or "docked" (mode 2)


def runs_of(flags):
    """maximal runs of True: list of (start, length)."""
    out = []
    i = 0
    n = len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j < n and flags[j]:
                j += 1
            out.append((i, j - i))
            i = j
        else:
            i += 1
    return out


def majority_state(states):
    c = Counter(states)
    top = c.most_common()
    best = top[0][1]
    tied = [s for s, k in top if k == best]
    mixed = len(c) > 1
    if len(tied) == 1:
        return tied[0], mixed, False
    # tie: the state of the first frame of the run among the tied ones
    for s in states:
        if s in tied:
            return s, mixed, True
    return tied[0], mixed, True


def analyze_run(tag, wind, roles, seed, d):
    rid = "%s/%s/%s" % (wind, roles, seed)
    r = {"id": rid}
    ev = d["eval"]
    r["rescued"] = int(ev.get("rescued", 0))
    r["dead"] = int(ev.get("dead", 0))
    r["nd"] = int(ev.get("never_detected", 0))
    r["ffd"] = int(ev.get("firefighter_deaths", 0))
    r["term"] = ev.get("terminal_step")
    r["top_term"] = d.get("terminal_step")

    bi = d.get("burn_intervals") or {}
    ivs = {}
    for k, lst in bi.items():
        x, y = k.split(",")
        ivs[(int(x), int(y))] = [(int(a), (10 ** 9 if b is None else int(b))) for a, b in lst]

    def burning(cell, step):  # step is 1-based harness step
        if cell is None:
            return False
        for a, b in ivs.get(cell, ()):
            if a <= step < b:
                return True
        return False

    us = d["uav_steps"]
    nfr = len(us)
    r["nframes"] = nfr
    # per-uid timelines
    uids = []
    tl = {}
    for i, row in enumerate(us):
        for e in row:
            uid = str(e[0])
            if uid not in tl:
                tl[uid] = [None] * nfr
                uids.append(uid)
            tl[uid][i] = (tup(e[1]), e[2] if len(e) > 2 else None,
                          (e[4] if len(e) > 4 else None), (e[5] if len(e) > 5 else None))
    r["n_uav_rows"] = len(uids)

    bs = d.get("base_station")
    fps = footprints(bs)
    r["n_depots"] = len(fps)

    # ---- E1 / E2 / E3 -------------------------------------------------
    e1n = e1d = 0
    bflag = {}
    for uid in uids:
        fl = []
        for i in range(nfr):
            t = tl[uid][i]
            if t is None or t[0] is None:
                fl.append(False)
                continue
            b = burning(t[0], i + 1)
            fl.append(b)
            if t[1] == "victim_searcher":
                e1d += 1
                if b:
                    e1n += 1
        bflag[uid] = fl
    r["e1n"], r["e1d"] = e1n, e1d

    ua = d.get("uav_actions")
    if ua:
        e2n = e2d = mism = 0
        for i, row in enumerate(ua):
            if row is None:
                continue
            for e in row:
                e2d += 1
                e2n += int(e[2])
                uid = str(e[0])
                if uid in bflag and i < nfr:
                    if bool(e[2]) != bflag[uid][i]:
                        mism += 1
        r["e2n"], r["e2d"], r["e2_mismatch"] = e2n, e2d, mism
    else:
        r["e2n"] = r["e2d"] = r["e2_mismatch"] = None

    streaks = []   # (uid, role_first, start, length, state, mixed, tie, maj_role)
    streaks_srch = []  # flag = burning AND role == victim_searcher
    stays = []
    for uid in uids:
        fl = bflag[uid]
        for s, L in runs_of(fl):
            sts = [state_class(tl[uid][k][3]) for k in range(s, s + L)]
            st, mixed, tie = majority_state(sts)
            roles_ = [tl[uid][k][1] for k in range(s, s + L)]
            mr = Counter(roles_).most_common(1)[0][0]
            streaks.append((uid, roles_[0], s, L, st, mixed, tie, mr))
        sfl = [fl[k] and tl[uid][k] is not None and tl[uid][k][1] == "victim_searcher" for k in range(nfr)]
        for s, L in runs_of(sfl):
            sts = [state_class(tl[uid][k][3]) for k in range(s, s + L)]
            st, mixed, tie = majority_state(sts)
            streaks_srch.append((uid, "victim_searcher", s, L, st, mixed, tie, "victim_searcher"))
        # same-cell stays while that cell burns
        k = 0
        while k < nfr:
            if not fl[k]:
                k += 1
                continue
            c = tl[uid][k][0]
            j = k
            while j < nfr and fl[j] and tl[uid][j][0] == c:
                j += 1
            L = j - k
            if L >= 2:
                sts = [state_class(tl[uid][q][3]) for q in range(k, j)]
                st, mixed, tie = majority_state(sts)
                stays.append({"uid": uid, "role": tl[uid][k][1], "cell": list(c), "start_frame": k,
                              "start_step": k + 1, "length": L, "state": st, "mixed": mixed, "tie": tie,
                              "in_depot": in_any_fp(c, fps)})
            k = j
    r["streaks"] = streaks
    r["streaks_srch"] = streaks_srch
    r["stays"] = stays

    # ---- M1..M5 ----------------------------------------------------------
    rl = d.get("rtb_log") or {}
    rc = d.get("rtb_counters") or {}
    r["n_uav"] = len(rc) or 4
    r["return_steps"] = sum(int(v.get("return_steps", 0)) for v in rc.values())
    r["charge_steps"] = sum(int(v.get("charge_steps", 0)) for v in rc.values())
    uav_berths = [tup(c) for c in (bs or {}).get("uav_berths", [])]
    ff_berths = [tup(c) for c in (bs or {}).get("firefighter_berths", [])]
    by_dep = [[tup(c) for c in row] for row in (bs or {}).get("uav_berths_by_depot", [])]
    n_uavs_bs = len(uav_berths)
    # derived per-depot ranking (checks orientation, gives ff berths at every depot)
    derived_ok = None
    ff_all = set(ff_berths)
    if fps:
        rk = [ranked_cells(f) for f in fps]
        der = [[rk[di][a] for di in range(len(fps))] for a in range(n_uavs_bs)]
        derived_ok = (der == by_dep) if by_dep else None
        n_ff = len(ff_berths)
        for di in range(len(fps)):
            for q in range(n_ff):
                ff_all.add(rk[di][n_uavs_bs + q])
    r["derived_berths_match"] = derived_ok

    def uav_index(uid):
        b = tup((rc.get(uid) or {}).get("berth"))
        if b is not None and b in uav_berths and uav_berths.count(b) == 1:
            return uav_berths.index(b)
        return uids.index(uid) if uid in uids else None

    trips = []
    for uid, lst in rl.items():
        idx = uav_index(uid)
        for ti, t in enumerate(lst):
            tb = tup(t.get("target_berth"))
            dc = tup(t.get("dock_cell"))
            arrived = t.get("arrival_step") is not None
            rec = {"uid": uid, "ti": ti, "trigger_step": t.get("trigger_step"),
                   "dist": t.get("trigger_distance"), "target_depot": t.get("target_depot"),
                   "target_berth": tb, "arrived": arrived, "arrival_step": t.get("arrival_step"),
                   "dock_cell": dc, "fallback": False}
            if arrived and dc != tb:
                rec["fallback"] = True
                # HOME classification
                if dc in uav_berths and any(uav_berths[j] == dc for j in range(n_uavs_bs) if j != idx):
                    hc = "other_uav_home_berth"
                elif idx is not None and idx < n_uavs_bs and dc == uav_berths[idx]:
                    hc = "own_home_berth"
                elif dc in ff_berths:
                    hc = "ff_berth"
                elif in_any_fp(dc, fps):
                    hc = "plain_depot_cell"
                else:
                    hc = "outside_depots"
                # by-depot classification
                if any(dc in by_dep[j] for j in range(len(by_dep)) if j != idx):
                    bc = "other_uav_berth_any_depot"
                elif idx is not None and idx < len(by_dep) and dc in by_dep[idx]:
                    bc = "own_berth_other_depot"
                elif dc in ff_all:
                    bc = "ff_berth_any_depot"
                elif in_any_fp(dc, fps):
                    bc = "plain_depot_cell"
                else:
                    bc = "outside_depots"
                rec["home_class"] = hc
                rec["bydepot_class"] = bc
            trips.append(rec)
    r["trips"] = trips

    # ---- D1 / D3 --------------------------------------------------------
    stuck = {}
    zb = []
    last = nfr - 1
    for uid in uids:
        t = tl[uid][last]
        if t is None:
            continue
        pos, role, batt, bst = t
        if bst == "returning":
            n = 0
            k = last
            while k >= 0 and tl[uid][k] is not None and tl[uid][k][0] == pos:
                n += 1
                k -= 1
            if n >= 10:
                stuck[uid] = {"uid": uid, "cell": list(pos) if pos else None, "frames": n, "battery": batt}
        fb = batt if batt is not None else (rc.get(uid) or {}).get("final_battery")
        if fb is not None and fb <= 0 and not in_any_fp(pos, fps):
            zb.append({"uid": uid, "cell": list(pos) if pos else None, "battery": fb})
    r["stuck"] = list(stuck.values())
    r["zerobatt"] = zb

    # ---- D2 ----------------------------------------------------------------
    un = []
    for t in trips:
        if t["arrived"]:
            continue
        uid = t["uid"]
        tlast = tl[uid][last]
        cls = "NOT-TRUNCATED"
        info = {}
        if tlast is not None and tlast[3] == "returning" and uid not in stuck:
            p1 = tlast[0]
            p0 = tl[uid][last - 10][0] if last - 10 >= 0 and tl[uid][last - 10] else None
            if p1 is not None and p0 is not None and t["target_berth"] is not None:
                d1 = man(p1, t["target_berth"])
                d0 = man(p0, t["target_berth"])
                info = {"d_last": d1, "d_minus10": d0}
                if d1 < d0:
                    cls = "HORIZON-TRUNCATED"
        # VARIANT (not the spec rule): bound the look-back to the trip itself. If
        # the trip is younger than 11 frames, the frame 10 earlier predates the
        # trigger, so compare against trigger_distance (pre-move distance at the
        # trigger step) instead.
        leg_frames = (nfr - (t["trigger_step"] - 1)) if t["trigger_step"] is not None else None
        info["leg_frames"] = leg_frames
        vcls = "NOT-TRUNCATED"
        if tlast is not None and tlast[3] == "returning" and uid not in stuck and t["target_berth"] is not None and tlast[0]:
            d1 = man(tlast[0], t["target_berth"])
            if leg_frames is not None and leg_frames >= 11:
                ref = info.get("d_minus10")
            else:
                ref = t["dist"]
            info["variant_ref_distance"] = ref
            if ref is not None and d1 < ref:
                vcls = "HORIZON-TRUNCATED"
        info["variant_class"] = vcls
        un.append({"uid": uid, "trigger_step": t["trigger_step"], "target_berth": list(t["target_berth"]) if t["target_berth"] else None,
                   "last_state": tlast[3] if tlast else None, "last_cell": list(tlast[0]) if tlast and tlast[0] else None,
                   "stuck": uid in stuck, "class": cls, **info})
    r["unarrived"] = un

    # ---- L1..L6 ------------------------------------------------------------
    legs = []
    offsets = []
    for uid in uids:
        flags = [tl[uid][k] is not None and tl[uid][k][3] == "returning" for k in range(nfr)]
        leg_runs = runs_of(flags)
        utrips = [t for t in trips if t["uid"] == uid]
        # empirical alignment: pair leg n with trip n (in order)
        for n, (s, L) in enumerate(leg_runs):
            if n < len(utrips) and utrips[n]["trigger_step"] is not None:
                offsets.append(utrips[n]["trigger_step"] - s)
        for n, (s, L) in enumerate(leg_runs):
            pos = [tl[uid][k][0] for k in range(s, s + L)]
            # trip mapping by trigger_step == first frame + OFFSET (set below, rechecked)
            legs.append({"uid": uid, "start": s, "len": L, "pos": pos, "n": n,
                         "ends_at_horizon": s + L == nfr})
        r.setdefault("_utrips", {})[uid] = utrips
    r["offsets"] = offsets
    r["legs_raw"] = legs
    return r


def leg_metrics(r, fps_by_run, offset):
    """Compute L2..L6 for legs of one run, using trigger_step == start + offset."""
    out = []
    for lg in r["legs_raw"]:
        pos = lg["pos"]
        L = len(pos)
        # L2 freeze
        best = cur = 1
        for k in range(1, L):
            if pos[k] == pos[k - 1] and pos[k] is not None:
                cur += 1
                best = max(best, cur)
            else:
                cur = 1
        freeze = best >= 3
        # collapse
        col = []
        for p in pos:
            if not col or col[-1] != p:
                col.append(p)
        cc = Counter(col)
        cycle = any(v >= 2 for v in cc.values())
        revisit = any(v >= 3 for v in cc.values())
        # VARIANT (not the spec rule): uncollapsed - some cell occupies >= 3 frames
        revisit_raw = any(v >= 3 for v in Counter(pos).values())
        osc = False
        for k in range(0, L - 9):
            win = pos[k:k + 10]
            if len(set(win)) <= 2 and sum(1 for q in range(1, 10) if win[q] != win[q - 1]) >= 2:
                osc = True
                break
        # trip mapping
        cands = [t for t in r["_utrips"][lg["uid"]] if t["trigger_step"] == lg["start"] + offset]
        trip = cands[0] if len(cands) == 1 else None
        l6_in = l6_out = False
        l6_first = None
        longest_nd = None
        nviol = 0
        if trip is not None and trip["target_berth"] is not None:
            tb = trip["target_berth"]
            td = trip["target_depot"] or 0
            fp = fps_by_run[td] if td < len(fps_by_run) else None
            dd = [man(p, tb) if p is not None else None for p in pos]
            for k in range(0, L - 10):
                if dd[k] is None or dd[k + 10] is None:
                    continue
                if dd[k + 10] >= dd[k]:
                    nviol += 1
                    if l6_first is None:
                        l6_first = (k, pos[k], dd[k], dd[k + 10])
                    if fp is not None and in_fp(pos[k], fp):
                        l6_in = True
                    else:
                        l6_out = True
            best = cur = 1
            for k in range(1, L):
                if dd[k] is not None and dd[k - 1] is not None and dd[k] >= dd[k - 1]:
                    cur += 1
                    best = max(best, cur)
                else:
                    cur = 1
            longest_nd = best
        out.append({"uid": lg["uid"], "start": lg["start"], "len": L, "freeze": freeze, "freeze_len": best if False else None,
                    "cycle": cycle, "osc": osc, "revisit": revisit, "revisit_raw": revisit_raw,
                    "mapped": trip is not None,
                    "l6": l6_in or l6_out, "l6_in": l6_in, "l6_out": l6_out, "l6_nviol": nviol,
                    "l6_first": l6_first, "longest_nondec": longest_nd,
                    "end_cell": list(pos[-1]) if pos[-1] else None, "horizon": lg["ends_at_horizon"],
                    "trip_arrived": trip["arrived"] if trip else None,
                    "target_berth": list(trip["target_berth"]) if trip and trip["target_berth"] else None,
                    "max_freeze": _max_freeze(pos)})
    return out


def _max_freeze(pos):
    best = cur = 1
    for k in range(1, len(pos)):
        if pos[k] == pos[k - 1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def slim(r, offset):
    fps = r.pop("_fps")
    r["legs"] = leg_metrics(r, fps, offset)
    del r["legs_raw"]
    del r["_utrips"]
    return r


# ---------------------------------------------------------------------------
def load_arm(tag, sample_list, offset_holder):
    runs = []
    missing = []
    for wind, roles, seed in sample_list:
        p = fpath(tag, wind, roles, seed)
        if not os.path.exists(p):
            missing.append(p)
            continue
        with open(p, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        r = analyze_run(tag, wind, roles, seed, d)
        r["_fps"] = footprints(d.get("base_station"))
        del d
        runs.append(r)
    return runs, missing


def agg(prefix, runs, R, detail):
    n = len(runs)
    R[prefix + ".runs_present"] = n
    for k, key in (("rescued", "rescued"), ("dead", "dead"), ("nd", "never_detected"), ("ffd", "ff_deaths")):
        R[prefix + "." + key] = sum(r[k] for r in runs)
    res = [r["term"] for r in runs if r["term"] is not None]
    R[prefix + ".terminal_resolved"] = "%d/%d" % (len(res), n)
    R[prefix + ".terminal_mean_resolved"] = round(sum(res) / len(res), 4) if res else None
    trips = [t for r in runs for t in r["trips"]]
    R[prefix + ".trips"] = len(trips)
    R[prefix + ".trips_arrived"] = sum(1 for t in trips if t["arrived"])
    dists = [t["dist"] for t in trips if t["dist"] is not None]
    R[prefix + ".mean_trigger_distance"] = round(sum(dists) / len(dists), 3) if dists else None
    denom = sum(r["n_uav"] * N_STEPS for r in runs)
    rs = sum(r["return_steps"] for r in runs)
    cs = sum(r["charge_steps"] for r in runs)
    R[prefix + ".return_steps"] = rs
    R[prefix + ".return_share_pct"] = round(100.0 * rs / denom, 3) if denom else None
    R[prefix + ".charge_steps"] = cs
    R[prefix + ".charge_share_pct"] = round(100.0 * cs / denom, 3) if denom else None
    R[prefix + ".share_denominator"] = denom
    fb = [t for t in trips if t["fallback"]]
    R[prefix + ".fallback_docks"] = len(fb)
    R[prefix + ".fallback_home_class"] = dict(Counter(t["home_class"] for t in fb))
    R[prefix + ".fallback_bydepot_class"] = dict(Counter(t["bydepot_class"] for t in fb))
    if fb:
        detail[prefix + ".fallback_list"] = [
            {"run": r["id"], "uid": t["uid"], "trigger_step": t["trigger_step"], "target_berth": t["target_berth"],
             "dock_cell": t["dock_cell"], "home_class": t["home_class"], "bydepot_class": t["bydepot_class"]}
            for r in runs for t in r["trips"] if t["fallback"]]
    if any(r["n_depots"] >= 2 for r in runs):
        by = {}
        for t in trips:
            by.setdefault(t["target_depot"], []).append(t["dist"])
        for dep, lst in sorted(by.items()):
            R[prefix + ".depot%s.trips" % dep] = len(lst)
            R[prefix + ".depot%s.mean_trigger_distance" % dep] = round(sum(lst) / len(lst), 3)
    dm = [r["derived_berths_match"] for r in runs if r["derived_berths_match"] is not None]
    if dm:
        R[prefix + ".derived_ranking_matches_by_depot_berths"] = "%d/%d" % (sum(dm), len(dm))
    # E1 E2
    e1n = sum(r["e1n"] for r in runs)
    e1d = sum(r["e1d"] for r in runs)
    R[prefix + ".E1_searcher_exposure"] = "%d/%d" % (e1n, e1d)
    R[prefix + ".E1_searcher_exposure_pct"] = round(100.0 * e1n / e1d, 3) if e1d else None
    e2r = [r for r in runs if r["e2d"] is not None]
    if e2r:
        e2n = sum(r["e2n"] for r in e2r)
        e2d = sum(r["e2d"] for r in e2r)
        R[prefix + ".E2_all_uav_exposure"] = "%d/%d" % (e2n, e2d)
        R[prefix + ".E2_all_uav_exposure_pct"] = round(100.0 * e2n / e2d, 3) if e2d else None
        R[prefix + ".E2_flag_mismatch_vs_burn_intervals"] = sum(r["e2_mismatch"] for r in e2r)
        R[prefix + ".E2_runs_with_uav_actions"] = len(e2r)
    # E3
    def sk(lst, label):
        lens = [s[3] for s in lst]
        R[prefix + ".E3_%s.ge2" % label] = sum(1 for x in lens if x >= 2)
        R[prefix + ".E3_%s.ge3" % label] = sum(1 for x in lens if x >= 3)
        R[prefix + ".E3_%s.ge5" % label] = sum(1 for x in lens if x >= 5)
        R[prefix + ".E3_%s.max" % label] = max(lens) if lens else 0
        for st in ("flying", "returning", "docked_charging"):
            sl = [s[3] for s in lst if s[4] == st]
            R[prefix + ".E3_%s.%s.ge2/ge3/ge5/max" % (label, st)] = "%d/%d/%d/%d" % (
                sum(1 for x in sl if x >= 2), sum(1 for x in sl if x >= 3), sum(1 for x in sl if x >= 5), max(sl) if sl else 0)
        R[prefix + ".E3_%s.mixed_state_runs_ge2" % label] = sum(1 for s in lst if s[5] and s[3] >= 2)
        R[prefix + ".E3_%s.tied_state_runs_ge2" % label] = sum(1 for s in lst if s[6] and s[3] >= 2)
    allst = [s for r in runs for s in r["streaks"]]
    sk(allst, "all")
    sk([s for r in runs for s in r["streaks_srch"]], "searcher_flagANDrole")
    sk([s for s in allst if s[7] == "victim_searcher"], "searcher_majorityrole")
    sk([s for s in allst if s[1] == "victim_searcher"], "searcher_firstframerole")
    stays = [s for r in runs for s in r["stays"]]
    lens = [s["length"] for s in stays]
    R[prefix + ".E3_samecell.ge2"] = sum(1 for x in lens if x >= 2)
    R[prefix + ".E3_samecell.ge3"] = sum(1 for x in lens if x >= 3)
    R[prefix + ".E3_samecell.ge5"] = sum(1 for x in lens if x >= 5)
    R[prefix + ".E3_samecell.max"] = max(lens) if lens else 0
    for st in ("flying", "returning", "docked_charging"):
        sl = [s["length"] for s in stays if s["state"] == st]
        R[prefix + ".E3_samecell.%s.ge2/ge3/ge5/max" % st] = "%d/%d/%d/%d" % (
            sum(1 for x in sl if x >= 2), sum(1 for x in sl if x >= 3), sum(1 for x in sl if x >= 5), max(sl) if sl else 0)
    R[prefix + ".E3_samecell.mixed_state"] = sum(1 for s in stays if s["mixed"])
    srs = [s["length"] for s in stays if s["role"] == "victim_searcher"]
    R[prefix + ".E3_samecell_searcher_firstrole.ge2/ge3/ge5/max"] = "%d/%d/%d/%d" % (
        len(srs), sum(1 for x in srs if x >= 3), sum(1 for x in srs if x >= 5), max(srs) if srs else 0)
    ge5 = [dict(run=r["id"], **s) for r in runs for s in r["stays"] if s["length"] >= 5]
    detail[prefix + ".samecell_ge5_list"] = ge5
    R[prefix + ".E3_samecell_ge5_list"] = ["%s uid=%s role=%s cell=%s step=%d len=%d state=%s in_depot=%s" % (
        s["run"], s["uid"], s["role"], tuple(s["cell"]), s["start_step"], s["length"], s["state"], s["in_depot"]) for s in ge5]
    # D1 D2 D3
    st_ = [dict(run=r["id"], **s) for r in runs for s in r["stuck"]]
    R[prefix + ".D1_stuck"] = len(st_)
    R[prefix + ".D1_stuck_list"] = ["%s uid=%s cell=%s frames=%d batt=%s" % (s["run"], s["uid"], tuple(s["cell"]), s["frames"], s["battery"]) for s in st_]
    un = [dict(run=r["id"], **u) for r in runs for u in r["unarrived"]]
    R[prefix + ".D2_unarrived"] = len(un)
    R[prefix + ".D2_horizon_truncated"] = sum(1 for u in un if u["class"] == "HORIZON-TRUNCATED")
    R[prefix + ".D2_not_truncated"] = sum(1 for u in un if u["class"] != "HORIZON-TRUNCATED")
    R[prefix + ".D2_list"] = ["%s uid=%s trig=%s target=%s last_state=%s last_cell=%s stuck=%s leg_frames=%s d_last=%s d_-10=%s -> %s | VARIANT ref=%s -> %s" % (
        u["run"], u["uid"], u["trigger_step"], u["target_berth"], u["last_state"], u["last_cell"], u["stuck"],
        u.get("leg_frames"), u.get("d_last"), u.get("d_minus10"), u["class"], u.get("variant_ref_distance"),
        u.get("variant_class")) for u in un]
    zb = [dict(run=r["id"], **z) for r in runs for z in r["zerobatt"]]
    R[prefix + ".D3_zerobatt"] = len(zb)
    # legs
    legs = [dict(run=r["id"], **lg) for r in runs for lg in r["legs"]]
    R[prefix + ".L1_legs"] = len(legs)
    R[prefix + ".L1_legs_mapped_to_trip"] = sum(1 for lg in legs if lg["mapped"])
    R[prefix + ".L1_leg_frames_sum"] = sum(lg["len"] for lg in legs)
    R[prefix + ".L2_freeze"] = sum(1 for lg in legs if lg["freeze"])
    R[prefix + ".L3_cycle"] = sum(1 for lg in legs if lg["cycle"])
    R[prefix + ".L4_oscillation"] = sum(1 for lg in legs if lg["osc"])
    R[prefix + ".L5_revisit"] = sum(1 for lg in legs if lg["revisit"])
    R[prefix + ".L5_VARIANT_uncollapsed_cell_in_ge3_frames"] = sum(1 for lg in legs if lg["revisit_raw"])
    R[prefix + ".L1_legs_shorter_than_10_frames(no_L4_window)"] = sum(1 for lg in legs if lg["len"] < 10)
    R[prefix + ".L1_legs_shorter_than_11_frames(no_L6_pair)"] = sum(1 for lg in legs if lg["len"] < 11)
    R[prefix + ".D2_VARIANT_trip_bounded_horizon_truncated"] = sum(1 for u in un if u.get("variant_class") == "HORIZON-TRUNCATED")
    R[prefix + ".L6_legs_violating"] = sum(1 for lg in legs if lg["l6"])
    R[prefix + ".L6_legs_with_violation_inside_target_depot"] = sum(1 for lg in legs if lg["l6_in"])
    R[prefix + ".L6_legs_with_violation_outside_target_depot"] = sum(1 for lg in legs if lg["l6_out"])
    R[prefix + ".L6_legs_inside_only"] = sum(1 for lg in legs if lg["l6_in"] and not lg["l6_out"])
    R[prefix + ".L6_legs_outside_only"] = sum(1 for lg in legs if lg["l6_out"] and not lg["l6_in"])
    R[prefix + ".L6_legs_both"] = sum(1 for lg in legs if lg["l6_out"] and lg["l6_in"])
    nd = [lg["longest_nondec"] for lg in legs if lg["longest_nondec"] is not None]
    R[prefix + ".L6_longest_nondecreasing_stretch_frames"] = max(nd) if nd else None
    R[prefix + ".L2_freeze_list"] = ["%s uid=%s start_frame=%d len=%d max_freeze=%d end=%s" % (
        lg["run"], lg["uid"], lg["start"], lg["len"], lg["max_freeze"], lg["end_cell"]) for lg in legs if lg["freeze"]]
    R[prefix + ".L6_list"] = ["%s uid=%s start_frame=%d len=%d nviol=%d in=%s out=%s first(k,pos,d,d+10)=%s longest_nd=%s end=%s horizon=%s arrived=%s" % (
        lg["run"], lg["uid"], lg["start"], lg["len"], lg["l6_nviol"], lg["l6_in"], lg["l6_out"],
        lg["l6_first"], lg["longest_nondec"], lg["end_cell"], lg["horizon"], lg["trip_arrived"]) for lg in legs if lg["l6"]]
    R[prefix + ".L5_list"] = ["%s uid=%s start_frame=%d len=%d" % (lg["run"], lg["uid"], lg["start"], lg["len"]) for lg in legs if lg["revisit"]]


def selftest(R):
    """Known reference values. ('eq', key, value) exact; ('r', key, value, nd) rounded to nd decimals."""
    T = []
    def eq(k, v): T.append(("eq", k, v))
    def rd(k, v, nd): T.append(("r", k, v, nd))
    eq("dfD.both.trips", 92); eq("dfD.both.trips_arrived", 92); rd("dfD.both.mean_trigger_distance", 29.4, 1)
    rd("dfD.both.return_share_pct", 12.41, 2); eq("dfD.both.return_steps", 2741); eq("dfD.both.charge_steps", 1196)
    rd("dfD.both.charge_share_pct", 5.42, 2); eq("dfD.both.fallback_docks", 2)
    eq("dfD.canonical.return_steps", 1560); rd("dfD.canonical.return_share_pct", 12.50, 2); eq("dfD.canonical.fallback_docks", 2)
    eq("dfD.fresh.trips", 40); rd("dfD.fresh.mean_trigger_distance", 29.20, 2); eq("dfD.fresh.return_steps", 1181)
    rd("dfD.fresh.return_share_pct", 12.30, 2); eq("dfD.fresh.fallback_docks", 0)
    eq("dfA.both.trips", 90); rd("dfA.both.mean_trigger_distance", 41.0, 1); eq("dfA.both.return_steps", 3705)
    rd("dfA.both.return_share_pct", 16.78, 2); eq("dfA.both.charge_steps", 1009); rd("dfA.both.charge_share_pct", 4.57, 2)
    eq("dfA.both.fallback_docks", 2); eq("dfA.fresh.return_steps", 1523)
    eq("dcD.both.return_steps", 2735); rd("dcD.both.return_share_pct", 12.39, 2); eq("dcD.both.fallback_docks", 1)
    eq("dcA.both.return_steps", 3711); rd("dcA.both.return_share_pct", 16.81, 2); eq("dcA.both.fallback_docks", 1)
    eq("dfD.both.fallback_home_class", {"other_uav_home_berth": 1, "plain_depot_cell": 1})
    eq("dfA.both.fallback_home_class", {"other_uav_home_berth": 1, "plain_depot_cell": 1})
    eq("dfD.both.fallback_bydepot_class", {"other_uav_berth_any_depot": 2})
    for k, v in (("dfD.canonical", "439/12480"), ("dfD.fresh", "186/9600"), ("dfA.canonical", "382/12480"),
                 ("dfA.fresh", "231/9600"), ("dfzero.canonical", "180/12480"), ("dfzero.fresh", "193/9600")):
        eq(k + ".E2_all_uav_exposure", v)
    for k, v in (("dfD.canonical", 3.52), ("dfD.fresh", 1.94), ("dfA.canonical", 3.06), ("dfA.fresh", 2.41),
                 ("dfzero.canonical", 1.44), ("dfzero.fresh", 2.01)):
        rd(k + ".E2_all_uav_exposure_pct", v, 2)
    for k, v, p in (("dfzero.canonical", "115/5520", 2.08), ("dfzero.fresh", "152/4800", 3.17),
                    ("dfD.canonical", "278/5520", 5.04), ("dfD.fresh", "156/4800", 3.25),
                    ("dfA.canonical", "286/5520", 5.18), ("dfA.fresh", "203/4800", 4.23),
                    ("ihbase.canonical", "117/5520", 2.12), ("dimfreshbase.fresh", "143/4800", 2.98)):
        eq(k + ".E1_searcher_exposure", v); rd(k + ".E1_searcher_exposure_pct", p, 2)
    eq("dfD.both.E3_all.max", 18); eq("dfD.both.E3_all.ge3", 65); eq("dfD.both.E3_all.ge5", 25)
    eq("dfA.both.E3_all.max", 13); eq("dfA.both.E3_all.ge3", 57); eq("dfA.both.E3_all.ge5", 21)
    for s, vals in (("canonical", (82, 50, 18, 15)), ("fresh", (26, 15, 7, 18))):
        for lab, v in zip(("ge2", "ge3", "ge5", "max"), vals):
            eq("dfD.%s.E3_all.%s" % (s, lab), v)
    for lab, v in zip(("ge2", "ge3", "ge5", "max"), (49, 31, 11, 15)):
        eq("dfD.canonical.E3_searcher_flagANDrole.%s" % lab, v)
    eq("dfD.canonical.E3_samecell.ge2", 24); eq("dfD.fresh.E3_samecell.ge2", 3)
    eq("dcB.fresh.D1_stuck", 1); eq("dcB.fresh.D1_stuck_list", ["east/half/808 uid=2500 cell=(4, 44) frames=38 batt=35.4"])
    eq("dcB.canonical.D1_stuck", 0)
    for t in ("dfA", "dfB", "dfC", "dfD"):
        for s in ("canonical", "fresh"):
            eq("%s.%s.D1_stuck" % (t, s), 0)
    eq("dfm2ref.canonical.D1_stuck", 5)
    T.append(("fn", "dfm2ref.canonical.D1_stuck_list(all 2502 at (3,44), frames 34/36/43/63/66)",
              lambda: (all("uid=2502 cell=(3, 44)" in x for x in R["dfm2ref.canonical.D1_stuck_list"])
                       and sorted(int(x.split("frames=")[1].split()[0]) for x in R["dfm2ref.canonical.D1_stuck_list"]) == [34, 36, 43, 63, 66])))
    eq("dcB.fresh.D2_unarrived", 1); eq("dcC.canonical.D2_unarrived", 3); eq("dfD.both.D2_unarrived", 0)
    for t, v in (("dfA", (2, 0, 0)), ("dfB", (15, 0, 0)), ("dfC", (20, 0, 0)), ("dfD", (3, 0, 0)), ("dcB", (11, 0, 0)),
                 ("dfkill", (11, 0, 0))):
        eq(t + ".both.L2_freeze", v[0]); eq(t + ".both.L3_cycle", v[1]); eq(t + ".both.L4_oscillation", v[2])
    eq("dfm2ref.canonical.L2_freeze", 5); eq("dfm2ref.canonical.L3_cycle", 0); eq("dfm2ref.canonical.L4_oscillation", 0)
    for p, v in (("dfD.both", (68, 16, 5, 10, "21/23", 162.0)), ("dcD.canonical", (39, 10, 1, 6, "12/13", 151.9)),
                 ("dcD.fresh", (29, 6, 4, 4, "9/10", 175.6)), ("dcoff.canonical", (35, 12, 0, 8, "10/13", 169.6)),
                 ("dcoff.fresh", (29, 4, 1, 7, "6/10", 173.2)), ("dcA.canonical", (38, 10, 4, 4, "13/13", 170.4)),
                 ("dcA.fresh", (29, 6, 4, 1, "9/10", 184.3)),
                 ("rbgate.rbc", (53, 11, 2, 9, "14/18", 186.8)), ("rbgate.dcrbA", (48, 12, 11, 6, "17/18", 182.9)),
                 ("rbgate.dcrbD", (57, 11, 2, 9, "17/18", 149.4))):
        eq(p + ".rescued", v[0]); eq(p + ".dead", v[1]); eq(p + ".never_detected", v[2]); eq(p + ".ff_deaths", v[3])
        eq(p + ".terminal_resolved", v[4]); rd(p + ".terminal_mean_resolved", v[5], 1)
    eq("pooled41.baseline.never_detected", 3); eq("pooled41.baseline.rescued", 117)
    eq("pooled41.dcD.never_detected", 7); eq("pooled41.dcD.rescued", 125)
    eq("pooled41.dcA.never_detected", 19); eq("pooled41.dcA.rescued", 115)
    # positive controls for L6
    T.append(("fn", "L6 positive control dcB.fresh east/half/808 uid 2500 (outside target depot)",
              lambda: any(x.startswith("east/half/808 uid=2500 ") and "out=True" in x for x in R["dcB.fresh.L6_list"])))
    T.append(("fn", "L6 positive control dfm2ref five stuck legs uid 2502",
              lambda: sorted(x.split(" start_frame")[0] for x in R["dfm2ref.canonical.L6_list"]) == sorted(
                  x.split(" cell=")[0] for x in R["dfm2ref.canonical.D1_stuck_list"])))
    T.append(("fn", "L5 positive control dcB.fresh east/half/808 uid 2500 (spec: must fire)",
              lambda: any(x.startswith("east/half/808 uid=2500 ") for x in R["dcB.fresh.L5_list"])))
    T.append(("fn", "L5 positive control dfm2ref five stuck legs (spec: must fire)",
              lambda: R["dfm2ref.canonical.L5_revisit"] >= 5))
    npass = nfail = 0
    for item in T:
        if item[0] == "fn":
            ok = bool(item[2]())
            name, got, want = item[1], ok, True
        else:
            name, want = item[1], item[2]
            got = R.get(name)
            if item[0] == "eq":
                ok = got == want
            else:
                ok = got is not None and round(got + 1e-12, item[3]) == round(want, item[3])
        R["selftest." + name] = ("PASS" if ok else "FAIL") + " got=%s want=%s" % (got, want)
        npass += ok
        nfail += (not ok)
    R["selftest._summary"] = "%d PASS, %d FAIL" % (npass, nfail)
    print(R["selftest._summary"])
    for k, v in R.items():
        if k.startswith("selftest.") and "FAIL" in str(v)[:4]:
            print("  ", k, v)


def main():
    R = {}
    detail = {}
    all_offsets = Counter()
    samples = {"canonical": CANON, "fresh": FRESH}
    plan = [(t, ("canonical", "fresh")) for t in TAGS_BOTH] + [(t, ("canonical",)) for t in TAGS_CANON_ONLY] + \
           [(t, ("fresh",)) for t in TAGS_FRESH_ONLY]
    offset = int(os.environ.get("LEG_OFFSET", "1"))
    for tag, smp in plan:
        both = []
        for s in smp:
            runs, missing = load_arm(tag, samples[s], None)
            for r in runs:
                if tag in ("dfD",):
                    all_offsets.update(r["offsets"])
                R.setdefault("offsets_all_arms", Counter()).update(r["offsets"])
                slim(r, offset)
            R["%s.%s.expected_runs" % (tag, s)] = len(samples[s])
            agg("%s.%s" % (tag, s), runs, R, detail)
            both.extend(runs)
            print(tag, s, len(runs), "missing", len(missing), flush=True)
        if len(smp) == 2:
            agg("%s.both" % tag, both, R, detail)
        del both
    R["leg_offset_used(trigger_step - first_returning_frame_index)"] = offset
    R["dfD.leg_offset_distribution"] = {str(k): v for k, v in all_offsets.items()}
    R["offsets_all_arms"] = {str(k): v for k, v in R["offsets_all_arms"].items()}

    # rbgate shards
    shard_map = {"a": "east", "b": "east", "c": "east", "s": "south"}
    for tag in ("rbc", "dcrbA", "dcrbD", "dcrbB", "dcrbC", "dfrb"):
        evs = []
        present = 0
        for sh, wind in shard_map.items():
            p = os.path.join(OUT, "_rblatch_camp2_%s%s_D_%s.json" % (tag, sh, wind))
            if not os.path.exists(p):
                continue
            present += 1
            with open(p, "r", encoding="utf-8") as fh:
                dd = json.load(fh)
            evs.extend(dd["evals"])
            del dd
        pre = "rbgate.%s" % tag
        R[pre + ".shards_present"] = present
        R[pre + ".seeds"] = len(evs)
        R[pre + ".rescued"] = sum(int(e.get("rescued", 0)) for e in evs)
        R[pre + ".dead"] = sum(int(e.get("dead", 0)) for e in evs)
        R[pre + ".never_detected"] = sum(int(e.get("never_detected", 0)) for e in evs)
        R[pre + ".ff_deaths"] = sum(int(e.get("firefighter_deaths", 0)) for e in evs)
        res = [e["terminal_step"] for e in evs if e.get("terminal_step") is not None]
        R[pre + ".terminal_resolved"] = "%d/%d" % (len(res), len(evs))
        R[pre + ".terminal_mean_resolved"] = round(sum(res) / len(res), 4) if res else None
    for name, jt, rt in (("baseline", "dcoff", "rbc"), ("dcD", "dcD", "dcrbD"), ("dcA", "dcA", "dcrbA")):
        R["pooled41.%s.never_detected" % name] = R["%s.both.never_detected" % jt] + R["rbgate.%s.never_detected" % rt]
        R["pooled41.%s.rescued" % name] = R["%s.both.rescued" % jt] + R["rbgate.%s.rescued" % rt]
        R["pooled41.%s.runs" % name] = R["%s.both.runs_present" % jt] + R["rbgate.%s.seeds" % rt]

    # d4 presence only (not analysed; wave in progress)
    for tag in ("d4off", "d4D", "d4A", "d4xD", "d4xA", "d4x0"):
        R["d4presence.%s.json_files_present" % tag] = len(
            [p for p in glob.glob(os.path.join(OUT, "_ffr_%s_*.json" % tag))
             if os.path.basename(p).split("_")[2] == tag])

    selftest(R)
    with open(RES, "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=1, sort_keys=True, default=str)
    with open(os.path.join(SCR, "dcd4_blind_detail.json"), "w", encoding="utf-8") as fh:
        json.dump(detail, fh, indent=1, default=str)
    print("wrote", RES)


if __name__ == "__main__":
    main()
