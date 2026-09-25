import json, os, re, collections
O = "E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"
names = [n for n in os.listdir(O) if n != QUAR and n.endswith(".json") and n.startswith("_ffr_")]
def tag_of(n):
    m = re.match(r"^_ffr_(.+?)_(east|south|west|north)_(half|def)_(\d+)\.json$", n)
    return m.groups() if m else None
tags = ("uhD", "uhC", "uhY", "ugD", "ugC", "ugY", "ugKD", "ugKC", "ugKY")
res = collections.defaultdict(lambda: collections.Counter())
for n in sorted(names):
    g = tag_of(n)
    if not g or g[0] not in tags: continue
    d = json.load(open(os.path.join(O, n), encoding="utf-8"))
    ffs = d.get("ff_steps") or []
    R = res[g[0]]
    R["runs"] += 1
    def exiting_before(step, ff):
        i = step - 2  # row index for the observation after step-1
        if i < 0 or i >= len(ffs): return None
        for r in ffs[i]:
            if r[0] == ff: return bool(r[4])
        return None
    for u in d.get("unassigns") or []:
        ff = u.get("ff"); st = u.get("step"); rs = u.get("reason")
        eb = exiting_before(st, ff)
        if rs == "replacement_after_blocked" and eb:
            R["carrier_drop"] += 1
        if rs == "geographically_isolated" and eb:
            R["custody_isolation"] += 1
        if rs == "geographically_isolated":
            R["iso_unassign_any"] += 1
    for e in d.get("unreachable_escape_log") or []:
        if e.get("cause") == "geographically_isolated": R["iso_marks"] += 1
    # stalled legs census-style
    starts = d.get("exit_starts") or []
    for c in d.get("completions") or []:
        st = [e for e in starts if e.get("victim") == c.get("victim") and e.get("step", 10**9) <= c.get("step", -1)]
        if not st or not c.get("exit_target") or not st[-1].get("ff_pos"): continue
        s = st[-1]; dist = abs(s["ff_pos"][0]-c["exit_target"][0]) + abs(s["ff_pos"][1]-c["exit_target"][1])
        R["legs"] += 1
        if c["step"] - s["step"] > dist + 5: R["stalled"] += 1
for t in tags:
    print(t, dict(res[t]))
