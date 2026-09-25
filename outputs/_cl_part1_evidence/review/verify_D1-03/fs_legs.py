"""Read-only offline reconstruction of carrying legs from recorded _ffr_*.json.

Opens ONLY explicit file names built from the census text (no directory walk).
Fire state seen by a firefighter advancing at step k = burning set after step k
(Fire agents precede firefighters in the schedule; SimultaneousActivation).
ff_steps[k-1] = unit state after step k. Smoke is NOT recorded -> not modelled.
"""
import json
import os
import re
import sys
from collections import Counter

OUT = r"E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"
N = 50


def load(tag, wind, roles, seed):
    name = "_ffr_%s_%s_%s_%s.json" % (tag, wind, "def" if roles == "default" else roles, seed)
    assert QUAR not in name
    p = os.path.join(OUT, name)
    if not os.path.isfile(p):
        return None, name
    with open(p, encoding="utf-8") as f:
        return json.load(f), name


def burning_at(d):
    iv = {}
    for key, lst in (d.get("burn_intervals") or {}).items():
        x, y = (int(v) for v in key.split(","))
        iv[(x, y)] = [(a, b if b is not None else 10 ** 9) for a, b in lst]

    def burning(cell, k):
        for a, b in iv.get(cell, ()):
            if a <= k < b:
                return True
        return False

    def ever_burned_before(cell, k):
        return any(a <= k for a, _b in iv.get(cell, ()))
    return burning, ever_burned_before


def nb(c):
    x, y = c
    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (x + ox, y + oy)
        if 0 <= n[0] < N and 0 <= n[1] < N:
            yield n


def on_boundary(c):
    return c[0] in (0, N - 1) or c[1] in (0, N - 1)


def md(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def pos_of(d, ff, k):
    if k < 1 or k > len(d["ff_steps"]):
        return None
    for row in d["ff_steps"][k - 1]:
        if row[0] == ff:
            return tuple(row[1]) if row[1] is not None else None
    return None


def legs(d):
    out = []
    starts = d.get("exit_starts") or []
    for c in d.get("completions") or []:
        st = [e for e in starts if e.get("victim") == c.get("victim") and e.get("step", 10 ** 9) <= c.get("step", -1)]
        if not st or not c.get("exit_target") or not st[-1].get("ff_pos"):
            continue
        s = st[-1]
        out.append(dict(victim=c["victim"], ff=c.get("ff"), s0=s["step"], s1=c["step"], p0=tuple(s["ff_pos"]),
                        exit=tuple(c["exit_target"]), dist=md(s["ff_pos"], c["exit_target"])))
    return out


def classify(d, leg, verbose=False):
    burning, burned_before = burning_at(d)
    ff, ex, s0, s1 = leg["ff"], leg["exit"], leg["s0"], leg["s1"]
    path = []
    for k in range(s0, s1 + 1):
        path.append((k, pos_of(d, ff, k)))
    first_bnd = None
    for k, p in path:
        if p is not None and on_boundary(p) and first_bnd is None:
            first_bnd = k
    reversals = 0
    away = 0
    stay = 0
    tiers = Counter()
    exit_adj_steps = 0
    exit_burn_steps = 0
    rows = []
    for i in range(1, len(path)):
        k, p = path[i]
        kp, pp = path[i - 1]
        if p is None or pp is None:
            continue
        # decision at step k made from pp with fire state at k
        dist_before = md(pp, ex)
        dist_after = md(p, ex)
        if dist_after > dist_before:
            away += 1
        if p == pp:
            stay += 1
        if i >= 2 and path[i - 2][1] == p and p != pp:
            reversals += 1
        ex_adj = any(burning(n, k) for n in nb(ex))
        ex_b = burning(ex, k)
        exit_adj_steps += ex_adj
        exit_burn_steps += ex_b
        # reconstruct tier (no smoke): improving&!adj -> 1 ; maintaining&!adj -> 2 ; !adj -> 3 ; else 4
        cand = []
        for c in nb(pp):
            if burning(c, k):
                continue
            adj = any(burning(n, k) for n in nb(c))
            cand.append((c, md(c, ex), adj))
        imp = [c for c in cand if c[1] < dist_before and not c[2]]
        mnt = [c for c in cand if c[1] == dist_before and not c[2]]
        safe = [c for c in cand if not c[2]]
        tier = 1 if imp else 2 if mnt else 3 if safe else 4 if cand else 0
        tiers[tier] += 1
        blocked_imp = [c for c in cand if c[1] < dist_before and c[2]]
        rows.append((k, pp, p, dist_before, dist_after, tier, ex_b, ex_adj,
                     [c[0] for c in blocked_imp], [c for c in nb(pp) if burning(c, k)]))
    saved_f1 = (s1 - first_bnd) if first_bnd is not None else 0
    res = dict(first_bnd=first_bnd, saved_f1=saved_f1, reversals=reversals, away=away, stay=stay,
               tiers=dict(tiers), exit_adj_steps=exit_adj_steps, exit_burn_steps=exit_burn_steps,
               steps=s1 - s0)
    if verbose:
        for r in rows:
            print("      k=%d %s->%s d %d->%d tier~%d exit_burn=%d exit_adj=%d blocked_improving=%s burning_nbrs=%s" % r)
    return res


def census_stalls(path):
    items = []
    with open(path, encoding="utf-8") as f:
        cls = None
        for line in f:
            m = re.match(r"^FIRE MECHANIC (ON|OFF):", line)
            if m:
                cls = m.group(1)
            m = re.match(r"^\s+STALL (\w+)/(\w+)/(\d+) (victim_\d+) (ff_unit_\d+): (\d+) steps for (\d+) cells \((\d+)-(\d+)\) from \[(\d+), (\d+)\] to \[(\d+), (\d+)\]\s+\[first seen in tag (\w+)\]", line)
            if m:
                g = m.groups()
                items.append(dict(cls=cls, wind=g[0], roles=g[1], seed=g[2], victim=g[3], ff=g[4],
                                  s0=int(g[7]), s1=int(g[8]), exit=(int(g[11]), int(g[12])), tag=g[13]))
    return items


if __name__ == "__main__":
    verbose_keys = set(sys.argv[1:])
    items = census_stalls(os.path.join(OUT, "_xs_census.txt"))
    print("stalled distinct legs parsed:", len(items))
    agg = Counter()
    for it in items:
        d, name = load(it["tag"], it["wind"], it["roles"], it["seed"])
        if d is None:
            print("MISSING", name)
            continue
        lg = [l for l in legs(d) if l["victim"] == it["victim"] and l["ff"] == it["ff"] and l["s0"] == it["s0"] and l["s1"] == it["s1"]]
        if not lg:
            print("NOLEG", name, it)
            continue
        leg = lg[0]
        key = "%s/%s/%s/%s" % (it["tag"], it["wind"], it["seed"], it["victim"])
        v = key in verbose_keys or "ALL" in verbose_keys
        print("%-4s %-40s %s %d-%d dist=%d exit=%s" % (it["cls"], key, it["ff"], leg["s0"], leg["s1"], leg["dist"], leg["exit"]))
        r = classify(d, leg, verbose=v)
        print("     steps=%d first_on_boundary=%s F1_saves=%d reversals=%d away=%d stay=%d tiers~%s exit_burning_steps=%d exit_fire_adj_steps=%d" % (
            r["steps"], r["first_bnd"], r["saved_f1"], r["reversals"], r["away"], r["stay"], r["tiers"], r["exit_burn_steps"], r["exit_adj_steps"]))
        agg[(it["cls"], "legs")] += 1
        agg[(it["cls"], "f1_any")] += r["saved_f1"] > 0
        agg[(it["cls"], "f1_resolves")] += (r["first_bnd"] is not None and (r["first_bnd"] - leg["s0"]) <= leg["dist"] + 5)
        agg[(it["cls"], "osc")] += r["reversals"] >= 2
        agg[(it["cls"], "exit_adj")] += r["exit_adj_steps"] > 0
    print(dict(agg))
