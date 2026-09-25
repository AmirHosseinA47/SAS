"""Read-only: for named _ffr_*.json files, the row at which a unit that was exiting
on the previous row becomes dead: its exiting flag, whether its cell burns at k,
and whether any exiting & alive row ever sits on a burning cell."""
import sys
sys.dont_write_bytecode = True
import json
import os
from collections import Counter

OUT = r"E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"


def burning_fn(d):
    iv = {}
    for key, lst in (d.get("burn_intervals") or {}).items():
        x, y = (int(v) for v in key.split(","))
        iv[(x, y)] = [(a, b if b is not None else 10 ** 9) for a, b in lst]

    def burning(c, k):
        return any(a <= k < b for a, b in iv.get(c, ()))
    return burning


C = Counter()
ex = []
for name in sys.argv[1:]:
    assert QUAR not in name and "/" not in name and "\\" not in name
    p = os.path.join(OUT, name)
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:  # noqa: BLE001
        C["unreadable"] += 1
        continue
    if "burn_intervals" not in d:
        C["no_bi"] += 1
        continue
    C["files"] += 1
    burning = burning_fn(d)
    prev = {}
    for i, row in enumerate(d["ff_steps"]):
        k = i + 1
        cur = {}
        for r in row:
            ffid, cell, status, assigned, exiting, dead = r
            cur[ffid] = r
            c = tuple(cell) if cell is not None else None
            if exiting and not dead and status != "dead" and c is not None:
                C["exit_alive_rows"] += 1
                if burning(c, k):
                    C["exit_alive_in_fire"] += 1
                    ex.append((name, ffid, k, c))
            pr = prev.get(ffid)
            if dead and pr is not None and not pr[5] and pr[4]:
                C["death_after_exiting"] += 1
                C["death_row_exiting=%s" % bool(exiting)] += 1
                C["death_cell_burning=%s" % (burning(c, k) if c else None)] += 1
        prev = cur
print(dict(C))
print(ex[:10])
