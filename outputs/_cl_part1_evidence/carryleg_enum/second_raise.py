"""Read-only: recorded rows where a unit is exiting AND status route_blocked (custody kept under the flag)."""
import json
import os
from collections import Counter

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
names = sorted(n for n in os.listdir(OUT) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json"))
rows = 0
runs = set()
examples = []
pre_block = Counter()
for n in names:
    with open(os.path.join(OUT, n), encoding="utf-8") as fh:
        d = json.load(fh)
    ffs = d.get("ff_steps") or []
    for i, step_rows in enumerate(ffs):
        for r in step_rows:
            if r[4] and r[2] == "route_blocked":
                rows += 1
                runs.add((n, r[0]))
                if len(examples) < 12:
                    examples.append((n, i + 1, r))
print("exiting rows with status route_blocked:", rows, "in", len(runs), "(file, ff) pairs")
for e in examples:
    print("  ", e)
