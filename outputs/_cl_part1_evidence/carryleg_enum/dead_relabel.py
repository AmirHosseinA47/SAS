"""Read-only: recorded victim markers that go from 'dead' back to a non-dead status."""
import json
import os
from collections import Counter

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
names = sorted(n for n in os.listdir(OUT) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json"))
hits = []
trans = Counter()
for n in names:
    with open(os.path.join(OUT, n), encoding="utf-8") as fh:
        d = json.load(fh)
    vs = d.get("victim_steps") or []
    for i in range(1, len(vs)):
        before = {v[0]: v for v in vs[i - 1]}
        for v in vs[i]:
            b = before.get(v[0])
            if b and b[2] == "dead" and v[2] != "dead":
                trans[(b[2], v[2])] += 1
                if len(hits) < 10:
                    hits.append((n, i + 1, b, v))
print("dead -> non-dead marker transitions (end-of-step snapshots):", sum(trans.values()), dict(trans))
for h in hits:
    print("  ", h)
