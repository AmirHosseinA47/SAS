"""Read-only: carrying steps that STARTED on a cell burning in that step's post-step board
(the decision board if Fire precedes firefighters): prev row exiting&alive at c, burning(c,k)."""
import sys
sys.dont_write_bytecode = True
import json, os
from collections import Counter
OUT = r"E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"
def bf(d):
    iv = {}
    for key, lst in (d.get("burn_intervals") or {}).items():
        x, y = (int(v) for v in key.split(","))
        iv[(x, y)] = [(a, b if b is not None else 10 ** 9) for a, b in lst]
    return lambda c, k: any(a <= k < b for a, b in iv.get(c, ()))
C = Counter(); ex = []
for name in sys.argv[1:]:
    assert QUAR not in name and "/" not in name
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        d = json.load(f)
    if "burn_intervals" not in d:
        continue
    b = bf(d); prev = {}
    for i, row in enumerate(d["ff_steps"]):
        k = i + 1; cur = {}
        for r in row:
            ffid, cell, status, assigned, exiting, dead = r; cur[ffid] = r
            pr = prev.get(ffid)
            if pr is not None and pr[4] and not pr[5] and pr[1] is not None:
                c0 = tuple(pr[1])
                C["carry_steps"] += 1
                if b(c0, k):
                    C["start_cell_burning"] += 1
                    C["survived=%s" % (not dead)] += 1
                    if not dead:
                        ex.append((name, ffid, k, c0, cell, exiting))
        prev = cur
print(dict(C)); print(ex[:12])
