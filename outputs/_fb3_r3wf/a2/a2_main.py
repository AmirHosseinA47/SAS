"""A2 analyses 0-4 on the re-screen Bayes arms (recorded JSON only)."""
import collections
from common import *  # noqa

P = print

# ------------------------------------------------------------------ 0. sanity + flagged list
P("=" * 100)
P("0. SANITY")
stat_names = collections.Counter()
mono_viol = 0
for tag in RESCREEN + SCREEN:
    for seed, d in load(tag).items():
        for row in d["rows_vic"]:
            for v in row:
                stat_names[(v[3])] += 1
        sm = samples(d)
        for i in range(1, len(sm)):
            if sm[i][1] < sm[i - 1][1] - 1e-9:
                mono_viol += 1
P("victim marker statuses (rows_vic[.][3]) over all re-screen+screen runs:", dict(stat_names))
P("DEAD mass decreases between consecutive samples (all 160 runs):", mono_viol)

flag = []          # (tag, seed, v, info)
nonflag = []
for tag in RESCREEN:
    for seed, d in sorted(load(tag).items()):
        for v, info in classify(d).items():
            if info is None:
                continue
            (flag if info["max"] > THRESH else nonflag).append((tag, seed, v, info))
P("flagged %d, non-flagged (sampled alive+undetected, max <= 0.5) %d" % (len(flag), len(nonflag)))
for tag, seed, v, info in flag:
    P("  FLAG %-8s %s %-9s first>0.5 %s max %.4f@%d det %s" % (
        tag, seed, v, info["first"], info["max"], info["max_step"], A.det_times(load(tag)[seed]).get(v)))

# step alignment check: n_unfound recorded at sample s == n_brief - #{det <= s}
bad = tot = 0
for tag in RESCREEN:
    for seed, d in load(tag).items():
        det = A.det_times(d)
        nb = len(d["rows_vic"][0])
        for s, dead, n_unf, alive in samples(d):
            tot += 1
            exp = nb - sum(1 for t in det.values() if t is not None and t <= s)
            bad += exp != n_unf
P("n_unfound(sample s) == n_brief - #{first detection <= s}: mismatches %d / %d" % (bad, tot))

# ------------------------------------------------------------------ 1. paths and issued targets
P("=" * 100)
P("1. PATHS AND ISSUED TARGETS over the alive+undetected window")
COV = {}


def cov(tag, seed):
    k = (tag, seed)
    if k not in COV:
        COV[k] = cover_stack(load(tag)[seed])
    return COV[k]


def victim_stats(tag, seed, v, info, restrict_from=None):
    d = load(tag)[seed]
    win = window(d, v)
    if restrict_from is not None:
        win = [s for s in win if s >= restrict_from]
    if not win:
        return None
    pos = {s: tuple(vrow(d, s, v)[1:3]) for s in win}
    path = [pos[s] for s in win]
    moves = sum(1 for i in range(1, len(path)) if path[i] != path[i - 1])
    total = sum(abs(path[i][0] - path[i - 1][0]) + abs(path[i][1] - path[i - 1][1]) for i in range(1, len(path)))
    net = dist(path[0], path[-1])
    wset = set(win)
    # issued targets during the window (issue step s in window), distance to victim at s
    iss = [r for r in (d["fb3"]["issued"] or []) if r[0] in wset]
    di = [dist(tuple(r[2]), pos[r[0]]) for r in iss]
    chance8 = [float(np.mean(np.hypot(POOL[:, 0] - pos[r[0]][0], POOL[:, 1] - pos[r[0]][1]) <= 8)) for r in iss]
    chance16 = [float(np.mean(np.hypot(POOL[:, 0] - pos[r[0]][0], POOL[:, 1] - pos[r[0]][1]) <= 16)) for r in iss]
    # active targets per step: label 'victim_search_targeting' and latest issued target of that uid <= s
    by_uid = collections.defaultdict(list)
    for r in d["fb3"]["issued"] or []:
        by_uid[r[1]].append(r)
    da = []
    for s in win:
        for u in d["rows_uav"][s - 1]:
            if u[8] != "victim_search_targeting":
                continue
            last = [r for r in by_uid.get(u[0], []) if r[0] <= s]
            if last:
                da.append(dist(tuple(last[-1][2]), pos[s]))
    # nearest UAV (any role) and nearest searcher distance per step
    nu, ns = [], []
    for s in win:
        row = d["rows_uav"][s - 1]
        ds = [dist((u[1], u[2]), pos[s]) for u in row if u[1] is not None]
        nu.append(min(ds))
        dss = [dist((u[1], u[2]), pos[s]) for u in row if u[1] is not None and u[3] == "victim_searcher"]
        if dss:
            ns.append(min(dss))
    return {"win": (win[0], win[-1], len(win)), "start": path[0], "moves": moves, "total": total, "net": net,
            "n_iss": len(iss), "di": di, "c8": chance8, "c16": chance16, "da": da, "nu": nu, "ns": ns}


def summarise(rows, label):
    di = [x for r in rows for x in r["di"]]
    c8 = [x for r in rows for x in r["c8"]]
    c16 = [x for r in rows for x in r["c16"]]
    da = [x for r in rows for x in r["da"]]
    ns = [x for r in rows for x in r["ns"]]
    if not di:
        P("  %s: no issued targets in windows" % label)
        return
    w8 = sum(1 for x in di if x <= 8) / len(di)
    w16 = sum(1 for x in di if x <= 16) / len(di)
    P("  %s: victims %d, issued-in-window %d | issued target->victim dist: min %.1f median %.1f mean %.1f |"
      " within 8: %.3f (chance %.3f, ratio %.2f) | within 16: %.3f (chance %.3f, ratio %.2f)" % (
          label, len(rows), len(di), min(di), med(di), mean(di), w8, mean(c8), w8 / mean(c8), w16, mean(c16),
          w16 / mean(c16)))
    if da:
        P("       active-target steps %d: median dist %.1f, within 8 %.3f, within 16 %.3f | nearest-searcher dist"
          " per window step: median %.1f, p10 %.1f (n %d)" % (
              len(da), med(da), sum(1 for x in da if x <= 8) / len(da), sum(1 for x in da if x <= 16) / len(da),
              med(ns), q(ns, .1), len(ns)))


F1, F1hi, N1, N1late = [], [], [], []
P("per flagged victim (window = alive+undetected steps; hi = from first sampled step > 0.5):")
P("  arm      seed  victim     window       start    moves total net | iss  min  med  w8   w16  | hi: iss min med w8 w16 | nearest searcher med/min")
for tag, seed, v, info in flag:
    r = victim_stats(tag, seed, v, info)
    rh = victim_stats(tag, seed, v, info, restrict_from=info["first"])
    F1.append(r)
    F1hi.append(rh)
    f = lambda xs, k: (sum(1 for x in xs if x <= k) / len(xs)) if xs else float("nan")
    P("  %-8s %s  %-9s %3d-%3d(%3d) %-8s %4d %4d %5.1f | %3d %4.1f %4.1f %.2f %.2f | %3d %4s %4s %.2f %.2f | %.1f / %.1f" % (
        tag, seed, v, r["win"][0], r["win"][1], r["win"][2], r["start"], r["moves"], r["total"], r["net"],
        r["n_iss"], min(r["di"]) if r["di"] else float("nan"), med(r["di"]) or float("nan"), f(r["di"], 8),
        f(r["di"], 16), rh["n_iss"], ("%.1f" % min(rh["di"])) if rh["di"] else "-",
        ("%.1f" % med(rh["di"])) if rh["di"] else "-", f(rh["di"], 8), f(rh["di"], 16),
        med(r["ns"]) or float("nan"), min(r["ns"]) if r["ns"] else float("nan")))
for tag, seed, v, info in nonflag:
    r = victim_stats(tag, seed, v, info)
    if r:
        N1.append(r)
    r2 = victim_stats(tag, seed, v, info, restrict_from=70)
    if r2:
        N1late.append(r2)
P("POOLED:")
summarise(F1, "FLAGGED full window      ")
summarise(F1hi, "FLAGGED steps >= first>.5")
summarise(N1, "NON-FLAGGED full window  ")
summarise(N1late, "NON-FLAGGED steps >= 70  ")
mv = lambda rows, k: [r[k] for r in rows]
P("  path: flagged moves median %s (range %s-%s), total %s, net median %.1f | non-flagged moves median %s, net median %.1f,"
  " window length median flagged %s vs non-flagged %s" % (
      med(mv(F1, "moves")), min(mv(F1, "moves")), max(mv(F1, "moves")), med(mv(F1, "total")), med(mv(F1, "net")),
      med(mv(N1, "moves")), med(mv(N1, "net")), med([r["win"][2] for r in F1]), med([r["win"][2] for r in N1])))
P("  moves per window step: flagged %.3f, non-flagged %.3f" % (
    sum(mv(F1, "moves")) / sum(r["win"][2] for r in F1), sum(mv(N1, "moves")) / sum(r["win"][2] for r in N1)))

# ------------------------------------------------------------------ 2. coverage around the victim
P("=" * 100)
P("2. COVERAGE AROUND THE VICTIM (UAV Euclidean-8 discs from rows_uav, every UAV, end of step)")


def cov_stats(tag, seed, v, steps_from=None):
    d = load(tag)[seed]
    C = cov(tag, seed)
    win = window(d, v)
    if steps_from is not None:
        win = [s for s in win if s >= steps_from]
    res = collections.defaultdict(list)
    for s in win:
        p = tuple(vrow(d, s, v)[1:3])
        i = s - 1                         # cover index of step s
        for W in (10, 30):
            lo = max(0, i - W)
            recent = C[lo:i].any(axis=0) if i > lo else np.zeros((50, 50), bool)   # steps s-W .. s-1
            for R, off in ((8, OFF8), (16, OFF16)):
                xs, ys = disc_cells(p, off)
                res["d%d_w%d" % (R, W)].append(float(recent[xs, ys].mean()))
            res["grid_w%d" % W].append(float(recent.mean()))
        ever = C[:i].any(axis=0) if i > 0 else np.zeros((50, 50), bool)
        xs, ys = disc_cells(p, OFF8)
        res["d8_ever"].append(float(ever[xs, ys].mean()))
        res["grid_ever"].append(float(ever.mean()))
        # the victim's own cell: covered before s? last cover step
        prev = np.nonzero(C[:i, p[0], p[1]])[0]
        res["own_prev"].append(1.0 if prev.size else 0.0)
        res["own_age"].append(float(i - prev[-1]) if prev.size else float("nan"))
        res["edge"].append(min(p[0], p[1], 49 - p[0], 49 - p[1]))
        # fire distance bounds from mf2 uav rows (Manhattan; 99 = no fire): upper = min(fd_u + |u-v|_1)
        mrow = (d.get("mf2") or {}).get("uav") or []
        if i < len(mrow):
            pos_u = {u[0]: (u[1], u[2]) for u in d["rows_uav"][i] if u[1] is not None}
            ub = []
            for m in mrow[i]:
                if m[0] in pos_u and isinstance(m[6], int) and m[6] < 99:
                    ub.append(m[6] + abs(pos_u[m[0]][0] - p[0]) + abs(pos_u[m[0]][1] - p[1]))
            res["fire_ub"].append(min(ub) if ub else float("nan"))
    return res


def pool(rows, key):
    return [x for r in rows for x in r[key] if x == x]


def cov_summary(rows, label):
    P("  %s: victim-steps %d" % (label, len(pool(rows, "d8_w10"))))
    for k in ("d8_w10", "d8_w30", "d16_w10", "d16_w30", "grid_w10", "grid_w30", "d8_ever", "grid_ever"):
        xs = pool(rows, k)
        P("     %-9s mean %.3f median %.3f" % (k, mean(xs), med(xs)))
    own = pool(rows, "own_prev")
    age = pool(rows, "own_age")
    P("     own cell covered at some earlier step: %.3f of steps; age since last cover (when covered) median %s" % (
        mean(own), med(age)))
    e = pool(rows, "edge")
    fu = pool(rows, "fire_ub")
    P("     distance to grid edge median %s, share <= 4 (band) %.3f | fire-distance UPPER bound (Manhattan) median %s,"
      " share <= 6: %.3f (n %d)" % (med(e), sum(1 for x in e if x <= 4) / len(e), med(fu),
                                    (sum(1 for x in fu if x <= 6) / len(fu)) if fu else float("nan"), len(fu)))


CF, CFhi, CN, CNlate = [], [], [], []
P("per flagged victim (steps >= first sampled > 0.5): d8_w10 d8_w30 d16_w30 grid_w30 d8_ever own_prev own_age_med edge_med fire_ub_med")
for tag, seed, v, info in flag:
    r = cov_stats(tag, seed, v)
    rh = cov_stats(tag, seed, v, info["first"])
    CF.append(r)
    CFhi.append(rh)
    P("  %-8s %s %-9s  %.2f  %.2f  %.2f  %.2f  %.2f  %.2f  %s  %s  %s" % (
        tag, seed, v, mean(rh["d8_w10"]), mean(rh["d8_w30"]), mean(rh["d16_w30"]), mean(rh["grid_w30"]),
        mean(rh["d8_ever"]), mean(rh["own_prev"]), med([x for x in rh["own_age"] if x == x]), med(rh["edge"]),
        med([x for x in rh["fire_ub"] if x == x])))
for tag, seed, v, info in nonflag:
    CN.append(cov_stats(tag, seed, v))
    r2 = cov_stats(tag, seed, v, 70)
    if r2["d8_w10"]:
        CNlate.append(r2)
cov_summary(CF, "FLAGGED full window")
cov_summary(CFhi, "FLAGGED steps >= first > .5")
cov_summary(CN, "NON-FLAGGED full window")
cov_summary(CNlate, "NON-FLAGGED steps >= 70")

# ------------------------------------------------------------------ 3. how detected
P("=" * 100)
P("3. DETECTIONS: detecting UAV (stdout UAV id), role and execution label at step t and t-1")


def det_info(tag, seed, v):
    d = load(tag)[seed]
    du = det_uav(tag, seed).get(v)
    if du is None:
        return None
    t, uid = du
    out = {"t": t, "uid": uid}
    for lag, key in ((0, "now"), (1, "prev")):
        s = t - lag
        if s < 1:
            out[key] = None
            continue
        u = next((x for x in d["rows_uav"][s - 1] if x[0] == uid), None)
        vr = vrow(d, s, v)
        out[key] = (u[3], u[8], round(dist((u[1], u[2]), (vr[1], vr[2])), 1) if vr and u[1] is not None else None) if u else None
    # was the UAV within 8 at END of t-1 (=> pre-move detection at t) ?
    return out


def mech(lbl):
    if lbl == "victim_search_targeting":
        return "TARGETING"
    return A.mech(lbl)


cnt_f = collections.Counter()
for tag, seed, v, info in flag:
    di = det_info(tag, seed, v)
    if di is None:
        P("  %-8s %s %-9s never detected" % (tag, seed, v))
        continue
    P("  %-8s %s %-9s det step %d by UAV %s | step t: %s | step t-1: %s" % (tag, seed, v, di["t"], di["uid"],
                                                                         di["now"], di["prev"]))
    cnt_f[(di["now"][0], mech(di["now"][1]), mech(di["prev"][1]) if di["prev"] else None)] += 1
P("  FLAGGED (role, mech at t, mech at t-1):", dict(cnt_f))

cnt_n = collections.Counter()
cnt_nr = collections.Counter()
cnt_late = collections.Counter()
for tag in RESCREEN:
    for seed, d in sorted(load(tag).items()):
        cl = classify(d)
        for v, info in cl.items():
            if info is None or info["max"] > THRESH:
                continue
            di = det_info(tag, seed, v)
            if di is None or di["now"] is None:
                continue
            k = (di["now"][0], mech(di["now"][1]), mech(di["prev"][1]) if di["prev"] else None)
            cnt_n[k] += 1
            cnt_nr[di["now"][0]] += 1
            if di["t"] >= 70:
                cnt_late[k] += 1
P("  NON-FLAGGED (detected at step >= 10, sampled): %d detections; by role %s" % (sum(cnt_n.values()), dict(cnt_nr)))
for k, n in cnt_n.most_common():
    P("     %s: %d" % (k, n))
P("  NON-FLAGGED detected at step >= 70: %s" % dict(cnt_late))

# all detections incl. victims detected before step 10 (no sample) - baseline by role
allc = collections.Counter()
for tag in RESCREEN:
    for seed, d in load(tag).items():
        for v, (t, uid) in det_uav(tag, seed).items():
            u = next((x for x in d["rows_uav"][t - 1] if x[0] == uid), None)
            allc[(u[3] if u else "?", mech(u[8]) if u else "?")] += 1
P("  ALL detections in re-screen arms (role, mech at t): %s" % dict(allc))

# ------------------------------------------------------------------ 4. delay vs paired current searcher
P("=" * 100)
P("4. FIRST DETECTION vs the paired current-searcher run (same seed key)")
for tag, seed, v, info in flag:
    d = load(tag)[seed]
    ref = load(REF[tag]).get(seed)
    if ref is None:
        P("  %-8s %s %-9s ref missing" % (tag, seed, v))
        continue
    p_arm = {x[0]: tuple(x[1:3]) for x in d["rows_vic"][0]}
    p_ref = {x[0]: tuple(x[1:3]) for x in ref["rows_vic"][0]}
    sp_arm = (d.get("fb3") or {}).get("spawn")
    sp_ref = (ref.get("fb3") or {}).get("spawn")
    same1 = p_arm == p_ref
    same_sp = (sp_arm == sp_ref) if (sp_arm and sp_ref) else None
    ta = A.det_times(d).get(v)
    tr = A.det_times(ref).get(v)
    fa = next((x[3] for x in d["rows_vic"][-1] if x[0] == v), "?")
    fr = next((x[3] for x in ref["rows_vic"][-1] if x[0] == v), "?")
    # first step the two victims' positions differ (victim motion depends on the fire/RNG path)
    diverge = next((s for s in range(1, min(len(d["rows_vic"]), len(ref["rows_vic"])) + 1)
                    if tuple(vrow(d, s, v)[1:3]) != tuple(vrow(ref, s, v)[1:3])), None)
    P("  %-8s %s %-9s step-1 positions equal (all victims) %s, spawn equal %s | first det arm %s vs ref(%s) %s |"
      " delta %s | final arm %s ref %s | victim path first differs at step %s" % (
          tag, seed, v, same1, same_sp, ta, REF[tag], tr,
          (ta if ta is not None else 361) - (tr if tr is not None else 361), fa, fr, diverge))
