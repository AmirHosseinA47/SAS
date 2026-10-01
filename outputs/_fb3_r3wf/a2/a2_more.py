"""A2 analyses 5-7 plus flagged-victim positions."""
import collections
from common import *  # noqa

P = print


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x, y):
    rx = np.argsort(np.argsort(x))
    ry = np.argsort(np.argsort(y))
    return pearson(rx, ry)


def dead_at(smp, s):
    """DEAD share at step s from the monotone samples: (lo, hi) = (sample at floor10, sample at ceil10)."""
    lo = [x for x in smp if x[0] <= s]
    hi = [x for x in smp if x[0] >= s]
    return (lo[-1][1] if lo else 0.0), (hi[0][1] if hi else None)


# ------------------------------------------------------------------ positions of flagged victims
P("=" * 100)
P("F. FLAGGED VICTIM POSITIONS (rows_vic end of step) at step 1, first>0.5 sample, last window step; edge dist")
for tag in RESCREEN:
    for seed, d in sorted(load(tag).items()):
        for v, info in classify(d).items():
            if not info or info["max"] <= THRESH:
                continue
            w = window(d, v)
            p1 = vrow(d, 1, v)[1:3]
            pf = vrow(d, info["first"], v)[1:3]
            pl = vrow(d, w[-1], v)[1:3]
            P("  %-8s %s %-9s step1 %s | step %d %s | step %d %s (edge dist %d) | final status %s" % (
                tag, seed, v, p1, info["first"], pf, w[-1], pl, min(pl[0], pl[1], 49 - pl[0], 49 - pl[1]),
                next(x[3] for x in d["rows_vic"][-1] if x[0] == v)))

# ------------------------------------------------------------------ 5. G vs n_unf * alive_mass
P("=" * 100)
P("5. ISSUED G (exact along-path gain on lambda_cond) vs n_unf(at issue) * alive_mass(nearest sample)")
P("   n_unf at issue step s = n_brief - #{first detection <= s-1} (belief.detected_ids is updated post-move,"
  " wildfire_model.py:2770-2774; planning runs pre-move)")
for group in (("fb3bdr", "fb3bdr2"), ("fb3bfr", "fb3bfr2", "fb3vs3r"), RESCREEN):
    G, X, D, S, FR = [], [], [], [], []
    for tag in group:
        for seed, d in load(tag).items():
            smp = samples(d)
            if not smp:
                continue
            det = A.det_times(d)
            nb = len(d["rows_vic"][0])
            for r in d["fb3"]["issued"] or []:
                if r[4] is None:
                    continue          # LO (eff 1) issue: no G
                s = r[0]
                n_unf = nb - sum(1 for t in det.values() if t is not None and t <= s - 1)
                near = min(smp, key=lambda x: (abs(x[0] - s), x[0]))
                alive = near[3]
                dead = near[1]
                if n_unf <= 0:
                    continue
                G.append(r[4])
                X.append(n_unf * alive)
                D.append(dead)
                S.append(r[5])
                FR.append(r[4] / (n_unf * alive) if alive > 0 else float("nan"))
    G, X, D, S, FR = map(np.asarray, (G, X, D, S, FR))
    hi = D > THRESH
    P("  %-34s issues %d | Pearson(G, n_unf*alive) %.3f, Spearman %.3f, Pearson(logG, logX) %.3f" % (
        "+".join(group), len(G), pearson(G, X), spearman(G, X), pearson(np.log(G), np.log(X))))
    for name, m in (("DEAD <= 0.5", ~hi), ("DEAD > 0.5", hi)):
        if m.sum() == 0:
            P("     %s: none" % name)
            continue
        P("     %s: n %d | G min %.4f median %.4f max %.4f | n_unf*alive median %.3f | G/(n_unf*alive) median %.3f"
          " p10 %.3f p90 %.3f | S(=Sp at issue, p-disc) median %.4f max %.4f" % (
              name, m.sum(), G[m].min(), np.median(G[m]), G[m].max(), np.median(X[m]), np.nanmedian(FR[m]),
              np.nanpercentile(FR[m], 10), np.nanpercentile(FR[m], 90), np.median(S[m]), S[m].max()))
    # DEAD bins
    bins = [0, .1, .25, .5, .75, 1.01]
    row = []
    for a, b in zip(bins[:-1], bins[1:]):
        m = (D >= a) & (D < b)
        if m.sum():
            row.append("[%.2f,%.2f) n %d G med %.4f frac med %.3f" % (a, b, m.sum(), np.median(G[m]),
                                                                     np.nanmedian(FR[m])))
    P("     by DEAD bin: " + " | ".join(row))

# ------------------------------------------------------------------ 6. counters, association only
P("=" * 100)
P("6. STRATEGY COUNTERS per run (fb3.stats summed over searchers) - runs WITH a flagged victim vs WITHOUT (association)")
keys = ("selections", "drop_reached", "drop_swept", "giveup_unreachable", "drop_battery", "fallback_entries",
        "fallback_steps", "delivered_steps", "lo_continuation_steps", "drop_return_leg", "skip_onhazard",
        "skip_route_field_inactive", "fallback_boxed_by_uavs")
grp = {True: collections.defaultdict(list), False: collections.defaultdict(list)}
runinfo = []
for tag in RESCREEN:
    for seed, d in sorted(load(tag).items()):
        cl = classify(d)
        has = any(i and i["max"] > THRESH for i in cl.values())
        tot = collections.Counter()
        for per in (d["fb3"].get("stats") or {}).values():
            tot.update(per)
        smp = samples(d)
        maxdead = max((x[1] for x in smp), default=0)
        for k in keys:
            grp[has][k].append(tot.get(k, 0))
        grp[has]["max_dead_any"].append(maxdead)
        runinfo.append((tag, seed, has, dict(tot), maxdead))
P("  runs with flagged victim: %d, without: %d" % (len(grp[True]["selections"]), len(grp[False]["selections"])))
for k in keys + ("max_dead_any",):
    a, b = grp[True][k], grp[False][k]
    P("   %-26s WITH mean %8.2f median %8.2f | WITHOUT mean %8.2f median %8.2f" % (k, mean(a), med(a), mean(b), med(b)))

# per-step association: targeting-steered share of airborne searcher steps by DEAD state, while n_unf > 0
P("  Time-resolved (labels): airborne searcher steps while an undetected victim remains (s < last first-detection"
  " or any never detected), split by DEAD share at s (monotone; floor-sample > .5 => > .5; ceil-sample <= .5 => <= .5;"
  " in-between excluded)")
for tag in RESCREEN:
    c = collections.Counter()
    for seed, d in load(tag).items():
        smp = samples(d)
        det = A.det_times(d)
        t_all = max(det.values()) if det and all(t is not None for t in det.values()) else None
        for t, row in enumerate(d["rows_uav"]):
            s = t + 1
            if t_all is not None and s >= t_all:
                continue
            lo, hi = dead_at(smp, s)
            if lo > THRESH:
                cls = "hi"
            elif hi is not None and hi <= THRESH:
                cls = "lo"
            else:
                continue
            for u in row:
                if u[3] == "victim_searcher" and not (u[5] or u[6]):
                    c[cls + "_n"] += 1
                    lbl = str(u[8])
                    c[cls + "_tg"] += lbl == "victim_search_targeting"
    P("   %-8s DEAD<=.5: steered %d/%d (%.1f%%) | DEAD>.5: steered %d/%d (%.1f%%)" % (
        tag, c["lo_tg"], c["lo_n"], 100.0 * c["lo_tg"] / max(1, c["lo_n"]), c["hi_tg"], c["hi_n"],
        100.0 * c["hi_tg"] / max(1, c["hi_n"])))

# issue rate per searcher-step by DEAD state
P("  Issue rate (issued targets per airborne-searcher step), same split")
for tag in RESCREEN:
    c = collections.Counter()
    for seed, d in load(tag).items():
        smp = samples(d)
        det = A.det_times(d)
        t_all = max(det.values()) if det and all(t is not None for t in det.values()) else None
        iss = collections.Counter(r[0] for r in d["fb3"]["issued"] or [] if r[4] is not None)
        for t, row in enumerate(d["rows_uav"]):
            s = t + 1
            if t_all is not None and s >= t_all:
                continue
            lo, hi = dead_at(smp, s)
            cls = "hi" if lo > THRESH else ("lo" if (hi is not None and hi <= THRESH) else None)
            if cls is None:
                continue
            c[cls + "_n"] += sum(1 for u in row if u[3] == "victim_searcher" and not (u[5] or u[6]))
            c[cls + "_i"] += iss.get(s, 0)
    P("   %-8s DEAD<=.5: %d issues / %d steps = %.3f | DEAD>.5: %d / %d = %.3f" % (
        tag, c["lo_i"], c["lo_n"], c["lo_i"] / max(1, c["lo_n"]), c["hi_i"], c["hi_n"], c["hi_i"] / max(1, c["hi_n"])))

# ------------------------------------------------------------------ 7. screen 0.5 vs re-screen 0.1
P("=" * 100)
P("7. DEAD share over sampled alive+undetected victim-steps, per arm (screen burn-over 0.5 vs re-screen 0.1)")
for tag in SCREEN + RESCREEN:
    vals, per_v, nflag, dist100, dist360 = [], [], 0, [], []
    for seed, d in load(tag).items():
        for v, info in classify(d).items():
            if not info:
                continue
            vals += [x[1] for x in info["pts"]]
            per_v.append(info["max"])
            nflag += info["max"] > THRESH
        smp = {x[0]: x[1] for x in samples(d)}
        if 100 in smp:
            dist100.append(smp[100])
        if 360 in smp:
            dist360.append(smp[360])
    P("  %-8s burn-over %s | victim-steps %d: max %.4f median %.4f share > .5 %.3f | victims %d, max>.5 %d |"
      " run DEAD@100 median %.3f, DEAD@360 median %.3f" % (
          tag, load(tag)[sorted(load(tag))[0]]["fb3"]["switches"]["SEARCHER_BELIEF_BURNOVER"], len(vals), max(vals),
          med(vals), sum(1 for x in vals if x > THRESH) / len(vals), len(per_v), nflag, med(dist100), med(dist360)))
