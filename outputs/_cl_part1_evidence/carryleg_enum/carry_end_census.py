"""Read-only: every exiting True -> False transition in recorded runs, by mechanism.

For each unit and step s where ff_steps says exiting at the end of s-1 and not
exiting at the end of s, classify:
  completion  - a completions record for (ff, s)
  blocked     - an unassign reason containing 'block' for (ff, s)
  isolated    - an unassign reason containing 'isolat' for (ff, s)
  other_unassign - any other unassign for (ff, s)
  death_only  - the unit is dead at s with no unassign/completion
  unexplained - none of the above
Also: carriers still exiting at the last recorded step (horizon).
Also: dead-at-s for units exiting at s-1, split by whether an unassign preceded.
"""
import json
import os
from collections import Counter, defaultdict

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
names = sorted(n for n in os.listdir(OUT) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json"))

cls = Counter()
distinct = defaultdict(set)
death_with = Counter()
horizon = 0
horizon_distinct = set()
unexplained = []
for n in names:
    with open(os.path.join(OUT, n), encoding="utf-8") as fh:
        d = json.load(fh)
    ffs = d.get("ff_steps") or []
    if not ffs:
        continue
    run = (d.get("wind"), d.get("scenario"), d.get("seed"))
    comp = defaultdict(list)
    for c in d.get("completions") or []:
        comp[(c.get("ff"), int(c.get("step", 0)))].append(c)
    una = defaultdict(list)
    for u in d.get("unassigns") or []:
        una[(u.get("ff"), int(u.get("step", 0)))].append(str(u.get("reason")))
    for i in range(1, len(ffs)):
        s = i + 1
        before = {r[0]: r for r in ffs[i - 1]}
        after = {r[0]: r for r in ffs[i]}
        for ff, rb in before.items():
            if not rb[4]:
                continue
            ra = after.get(ff)
            if ra is None or ra[4]:
                continue
            reasons = una.get((ff, s), [])
            if comp.get((ff, s)):
                k = "completion"
            elif any("block" in r for r in reasons):
                k = "blocked"
            elif any("isolat" in r for r in reasons):
                k = "isolated"
            elif reasons:
                k = "other_unassign:" + ",".join(reasons)
            elif ra[5]:
                k = "death_only"
            else:
                k = "unexplained"
                unexplained.append((n, ff, s, rb, ra))
            cls[k] += 1
            distinct[k].add(run + (ff, s))
            if ra[5]:
                death_with[k] += 1
    last = ffs[-1]
    for r in last:
        if r[4]:
            horizon += 1
            horizon_distinct.add(run + (r[0],))

print("exiting -> not exiting transitions, all recorded runs with ff_steps:")
for k, c in cls.most_common():
    print(f"  {k:40s} records={c:5d} distinct(run,ff,step)={len(distinct[k]):4d} carrier dead at that step={death_with[k]}")
print("still exiting at the last recorded step (horizon):", horizon, "distinct(run,ff):", len(horizon_distinct))
print("unexplained examples:", unexplained[:5])
