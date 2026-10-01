"""A2 extras: G == 0 issues, log correlation on G > 0, drop_swept normalised, first approach to victim_0's start
cell per arm vs CUR, fire-tracker distance proxy."""
import collections
from common import *  # noqa

P = print

P("=" * 100)
P("X1. issued Bayes targets with G recorded as 0 (round(G, 5) == 0) and log-log correlation on G > 0")
for group in (("fb3bdr", "fb3bdr2"), ("fb3bfr", "fb3bfr2", "fb3vs3r")):
    G, X, D = [], [], []
    for tag in group:
        for seed, d in load(tag).items():
            smp = samples(d)
            det = A.det_times(d)
            nb = len(d["rows_vic"][0])
            for r in d["fb3"]["issued"] or []:
                if r[4] is None:
                    continue
                s = r[0]
                n_unf = nb - sum(1 for t in det.values() if t is not None and t <= s - 1)
                if n_unf <= 0:
                    continue
                near = min(smp, key=lambda x: (abs(x[0] - s), x[0]))
                G.append(r[4]); X.append(n_unf * near[3]); D.append(near[1])
    G, X, D = map(np.asarray, (G, X, D))
    hi = D > THRESH
    pos = (G > 0) & (X > 0)
    P("  %-26s issues %d | G==0: DEAD<=.5 %d/%d, DEAD>.5 %d/%d | Pearson(log G, log n_unf*alive) on G>0: %.3f (n %d)" % (
        "+".join(group), len(G), int(((G == 0) & ~hi).sum()), int((~hi).sum()), int(((G == 0) & hi).sum()),
        int(hi.sum()), float(np.corrcoef(np.log(G[pos]), np.log(X[pos]))[0, 1]), int(pos.sum())))
    # alive mass at those samples
    P("     n_unf*alive at DEAD>.5 issues: min %.4f median %.4f max %.4f" % (X[hi].min(), np.median(X[hi]), X[hi].max()))

P("=" * 100)
P("X2. drop_swept per Bayes-delivered step (delivered_steps - lo_continuation_steps), per run")
for has in (True, False):
    rat = []
    for tag in RESCREEN:
        for seed, d in load(tag).items():
            if any(i and i["max"] > THRESH for i in classify(d).values()) != has:
                continue
            tot = collections.Counter()
            for per in (d["fb3"].get("stats") or {}).values():
                tot.update(per)
            bayes = tot["delivered_steps"] - tot["lo_continuation_steps"]
            if bayes > 0:
                rat.append((tot["drop_swept"] / bayes, tot["drop_swept"], bayes, tot["selections"]))
    P("  %s flagged victim: runs %d | drop_swept per Bayes-delivered step: mean %.4f median %.4f | Bayes-delivered steps"
      " median %s | drop_swept/selections mean %.3f" % (
          "WITH" if has else "WITHOUT", len(rat), mean([r[0] for r in rat]), med([r[0] for r in rat]),
          med([r[2] for r in rat]), mean([r[1] / r[3] for r in rat if r[3]])))

P("=" * 100)
P("X3. First step ANY UAV (and any SEARCHER) is within 8 of the ring cell (40, 25) - victim_0's start - per arm, 16 seeds")
for tag in ("fx3mS",) + ("fb3bdr", "fb3bfr") + ("fx3mS2", "fb3bdr2", "fb3bfr2"):
    any_first, s_first = [], []
    for seed, d in sorted(load(tag).items()):
        fa = fs = None
        for t, row in enumerate(d["rows_uav"]):
            for u in row:
                if u[1] is None:
                    continue
                if dist((u[1], u[2]), (40, 25)) <= 8:
                    fa = fa or t + 1
                    if u[3] == "victim_searcher":
                        fs = fs or t + 1
            if fa and fs:
                break
        any_first.append(fa if fa else 361)
        s_first.append(fs if fs else 361)
    P("  %-8s any UAV: median %s, <= 60 in %d/16, never %d | searcher: median %s, <= 60 in %d/16, never %d" % (
        tag, med(any_first), sum(1 for x in any_first if x <= 60), sum(1 for x in any_first if x == 361),
        med(s_first), sum(1 for x in s_first if x <= 60), sum(1 for x in s_first if x == 361)))

P("  victim_0 first detection per arm (16 seeds): median, <= 60, never")
for tag in ("fx3mS", "fb3bdr", "fb3bfr", "fx3mS2", "fb3bdr2", "fb3bfr2"):
    ts = [A.det_times(d).get("victim_0") for d in load(tag).values()]
    tt = [t if t is not None else 361 for t in ts]
    P("   %-8s median %s, <= 60: %d/16, never %d, list %s" % (tag, med(tt), sum(1 for t in tt if t <= 60),
                                                         sum(1 for t in ts if t is None), sorted(tt)))

P("=" * 100)
P("X4. Proxy for fire proximity (INFERRED proxy): distance victim -> nearest airborne fire_tracker, per window step")
for lab, sel in (("FLAGGED", True), ("NON-FLAGGED", False)):
    xs, xs_late = [], []
    for tag in RESCREEN:
        for seed, d in load(tag).items():
            for v, info in classify(d).items():
                if not info or (info["max"] > THRESH) != sel:
                    continue
                for s in window(d, v):
                    p = vrow(d, s, v)[1:3]
                    ds = [dist((u[1], u[2]), p) for u in d["rows_uav"][s - 1]
                          if u[1] is not None and u[3] == "fire_tracker" and not (u[5] or u[6])]
                    if ds:
                        xs.append(min(ds))
                        if s >= 70:
                            xs_late.append(min(ds))
    P("  %-11s all window steps: median %.1f p10 %.1f (n %d) | steps >= 70: median %.1f p10 %.1f (n %d)" % (
        lab, med(xs), q(xs, .1), len(xs), med(xs_late), q(xs_late, .1), len(xs_late)))
