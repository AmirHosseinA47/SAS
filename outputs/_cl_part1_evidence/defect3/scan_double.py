"""Record-wide: any successful assign of a victim while an exiting (carrying)
unit is bound to it (a second claimant on a carried victim), and any step at
which a carrying unit's status is route_blocked. Non-recursive listing,
quarantine skipped by name, read-only."""
import json, os, re, time

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
PAT = re.compile(r"^_ffr_(.+)_(east|west|north|south)_(half|def)_(\d+)\.json$")
t0 = time.time()
n = nb = 0
double = []
rb_carry = {}
for name in sorted(os.listdir(OUT)):
    if name == QUAR:
        continue
    m = PAT.match(name)
    if not m or name.endswith(".xstrace.json"):
        continue
    n += 1
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        d = json.load(f)
    binds = d.get("ff_bind_steps")
    ffs = d.get("ff_steps")
    if not binds or not ffs:
        continue
    nb += 1
    for a in d.get("assigns") or []:
        if not a.get("ok"):
            continue
        s = int(a["step"])
        if s < 2:
            continue
        prev_b = {r[0]: r[1] for r in binds[s - 2]}
        for r in ffs[s - 2]:
            if r[4] and not r[5] and prev_b.get(r[0]) == a["vid"] and r[0] != a["ff"]:
                double.append((name, s, a["vid"], a["ff"], r[0]))
    cnt = 0
    for i, row in enumerate(ffs):
        for r in row:
            if r[4] and not r[5] and str(r[2]).lower() == "route_blocked":
                cnt += 1
    if cnt:
        rb_carry[name] = cnt
    del d
print("files", n, "with binds", nb, "secs", round(time.time() - t0, 1))
print("assign to a carried victim (second claimant):", len(double), double[:10])
print("files with a carrying unit in route_blocked status (post-step rows):", len(rb_carry),
      "total rows", sum(rb_carry.values()), list(rb_carry.items())[:8])
