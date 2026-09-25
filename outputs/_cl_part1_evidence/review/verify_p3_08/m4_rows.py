"""Read-only: test which recorded row an M4 'custody marking' test must read.

For every geographically_isolated escape-log entry (step s, victim v):
  A = some ff exiting in ff_steps[s-2] AND bound to v in ff_bind_steps[s-2]   (before-step row)
  B = some ff exiting in ff_steps[s-1] AND bound to v in ff_bind_steps[s-1]   (after-step row)
  U = an unassigns row {s, ff, v, reason geographically_isolated}
  D = an unassigns row at step s for v with another reason (a same-step drop)
Non-recursive listing of outputs/ only; the quarantine directory name is skipped.
"""
import json
import os
from collections import Counter

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
names = sorted(n for n in os.listdir(OUT)
               if n != QUAR and n.startswith("_ffr_") and n.endswith(".json"))
cnt = Counter()
examples = {}
for n in names:
    p = os.path.join(OUT, n)
    if not os.path.isfile(p):
        continue
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        cnt["unreadable"] += 1
        continue
    ffs = d.get("ff_steps") or []
    fbs = d.get("ff_bind_steps") or []
    if not ffs or not fbs:
        continue
    unas = d.get("unassigns") or []
    for e in d.get("unreachable_escape_log") or []:
        if e.get("cause") != "geographically_isolated":
            continue
        s = int(e["step"])
        v = e["victim_id"]
        if s < 2 or s - 1 >= len(ffs):
            cnt["out_of_range"] += 1
            continue

        def custody(i):
            ex = {r[0] for r in ffs[i] if r[4] and not r[5] and r[1] is not None}
            bd = {r[0] for r in fbs[i] if r[1] == v}
            return ex & bd

        A = custody(s - 2)
        B = custody(s - 1)
        U = [u for u in unas if int(u["step"]) == s and u["vid"] == v and "isolat" in str(u["reason"])]
        D = [u for u in unas if int(u["step"]) == s and u["vid"] == v and "isolat" not in str(u["reason"])]
        uff = {u["ff"] for u in U}
        cnt["markings"] += 1
        key = ("A" if A else "-") + ("B" if B else "-") + ("U" if U else "-") + ("D" if D else "-") \
            + ("m" if (A & uff) else "-")
        cnt[key] += 1
        examples.setdefault(key, []).append((n, s, v, sorted(A), sorted(B), [(u["ff"], u["reason"]) for u in U],
                                             [(u["ff"], u["reason"]) for u in D]))
print("files", len(names))
for k, c in sorted(cnt.items()):
    print(k, c)
print()
for k, ex in sorted(examples.items()):
    print("==", k, len(ex))
    for x in ex[:4]:
        print("  ", x)
# f2cDRY check
p = os.path.join(OUT, "_ffr_f2cDRY_east_def_101.json")
with open(p, encoding="utf-8") as fh:
    d = json.load(fh)
for i in (175, 176):
    print("f2cDRY row", i, "ff_steps", [r for r in d["ff_steps"][i] if r[0] == "ff_unit_1"],
          "bind", [r for r in d["ff_bind_steps"][i] if r[0] == "ff_unit_1"])
