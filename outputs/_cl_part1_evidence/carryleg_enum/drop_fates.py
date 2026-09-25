"""Read-only: fate of every route_blocked drop of an exiting carrier in the recorded runs.

Per record: carrier dead at the drop step; victim status at drop step and its
first terminal status after; whether the same victim was later picked up again
(exit_starts) and by whom; whether it was eventually rescued (completions).
Distinct key: (wind, scenario, seed, ff, vid, step) - a proxy; the same tuple in
different arms can be a different trajectory.
"""
import json
import os
from collections import Counter

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
names = sorted(n for n in os.listdir(OUT) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json"))
recs = []
for n in names:
    with open(os.path.join(OUT, n), encoding="utf-8") as fh:
        d = json.load(fh)
    ffs = d.get("ff_steps") or []
    if not ffs:
        continue
    vs = d.get("victim_steps") or []
    if not vs:
        continue
    for u in d.get("unassigns") or []:
        if "block" not in str(u.get("reason")):
            continue
        s = int(u["step"])
        ff, vid = u["ff"], u["vid"]
        prev = {r[0]: r for r in ffs[s - 2]}
        if not prev[ff][4]:
            continue
        now = {r[0]: r for r in ffs[s - 1]}
        ff_dead_same = bool(now[ff][5])
        # victim trajectory after
        vfate = None
        vfate_step = None
        for i in range(s - 1, len(vs)):
            v = [x for x in vs[i] if x[0] == vid][0]
            if v[2] in ("dead", "rescued", "unreachable"):
                vfate, vfate_step = v[2], i + 1
                break
        repick = [e for e in d.get("exit_starts") or [] if e["victim"] == vid and e["step"] > s]
        rescued_by = [c for c in d.get("completions") or [] if c.get("victim") == vid and c["step"] > s]
        # carrier death step after the drop
        ff_death = None
        for i in range(s - 1, len(ffs)):
            r = {x[0]: x for x in ffs[i]}[ff]
            if r[5]:
                ff_death = i + 1
                break
        recs.append(dict(file=n, key=(d.get("wind"), d.get("scenario"), d.get("seed"), ff, vid, s),
                         ff_dead_same=ff_dead_same, vfate=vfate, vgap=(vfate_step - s) if vfate_step else None,
                         repick=[(e["step"], e["ff"]) for e in repick], rescued=bool(rescued_by),
                         ff_death_gap=(ff_death - s) if ff_death else None))

print("records", len(recs), "distinct keys", len({r["key"] for r in recs}))
seen = {}
for r in recs:
    seen.setdefault(r["key"], []).append(r)
c = Counter()
for k, rs in sorted(seen.items(), key=lambda kv: str(kv[0])):
    r = rs[0]
    same = all((x["ff_dead_same"], x["vfate"], x["vgap"], x["rescued"]) == (r["ff_dead_same"], r["vfate"], r["vgap"], r["rescued"]) for x in rs)
    print(k, "n=%d" % len(rs), "ff_dead_same=%s" % r["ff_dead_same"], "victim=%s after %s" % (r["vfate"], r["vgap"]),
          "repick=%s" % r["repick"], "rescued=%s" % r["rescued"], "ff_death_after=%s" % r["ff_death_gap"],
          "" if same else "ARMS DIFFER")
    c[(r["ff_dead_same"], r["vfate"])] += 1
print(c)
