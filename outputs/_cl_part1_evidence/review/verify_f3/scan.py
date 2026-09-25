"""Verify F3: in shipped-config recorded arms, how often would HOLD and SERVED trigger?
Non-recursive listdir of outputs/, skips the quarantine by name, reads only _ffr_<tag>_*.json.
HOLD trigger  = route_blocked unassign (replacement_after_blocked) of a unit exiting at end of step s-1.
SERVED trigger = geographically_isolated entry in unreachable_escape_log whose victim is bound
                 (ff_bind_steps) to a unit exiting at end of step s-1 or s.
SERVED near-miss = longest run of carrying steps in which no OTHER unit is alive, on grid and
                 not exiting (zero reachability starts -> the streak is certainly running).
"""
import json, os, re, sys
O = "E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"
TAGS = sys.argv[1].split(",")
names = [n for n in os.listdir(O) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json")]
pat = re.compile(r"^_ffr_(%s)_(east|south|west|north)_(half|def)_(\d+)\.json$" % "|".join(TAGS))
out = {}
for n in sorted(names):
    m = pat.match(n)
    if not m:
        continue
    tag = m.group(1)
    key = "%s/%s/%s" % (m.group(2), m.group(3), m.group(4))
    d = json.load(open(os.path.join(O, n), encoding="utf-8"))
    fs = d.get("ff_steps") or []
    bs = d.get("ff_bind_steps") or []
    ex = {}
    dead = {}
    pos = {}
    for i, row in enumerate(fs):
        for r in row:
            ex[(i + 1, r[0])] = bool(r[4])
            dead[(i + 1, r[0])] = bool(r[5]) or r[2] == "dead"
            pos[(i + 1, r[0])] = r[1]
    bind = {}
    for i, row in enumerate(bs):
        for r in row:
            bind[(i + 1, r[0])] = r[1]
    ffs = sorted({r[0] for row in fs for r in row})
    o = out.setdefault(tag, {"runs": 0, "drops": [], "cust_marks": [], "all_geo": 0, "near": []})
    o["runs"] += 1
    for u in d.get("unassigns") or []:
        s, ff = u["step"], u["ff"]
        if u.get("reason") == "replacement_after_blocked" and ex.get((s - 1, ff), False):
            o["drops"].append((key, s, ff, u.get("vid"), "carrier_dead_same_step" if dead.get((s, ff)) else "carrier_alive"))
    for e in d.get("unreachable_escape_log") or []:
        if e.get("cause") != "geographically_isolated":
            continue
        o["all_geo"] += 1
        s, vid = e.get("step"), e.get("victim_id")
        for ff in ffs:
            for t in (s - 1, s):
                if bind.get((t, ff)) == vid and ex.get((t, ff)):
                    o["cust_marks"].append((key, s, vid, ff))
                    break
    # near-miss: longest zero-other-start run during a carry
    best = (0, None)
    for ff in ffs:
        run = 0
        for i in range(1, len(fs) + 1):
            if ex.get((i, ff)) and not dead.get((i, ff)):
                others = [g for g in ffs if g != ff and not dead.get((i, g)) and pos.get((i, g)) is not None and not ex.get((i, g))]
                run = run + 1 if not others else 0
                if run > best[0]:
                    best = (run, (ff, i))
            else:
                run = 0
    o["near"].append((best[0], key, best[1]))
for tag in TAGS:
    o = out.get(tag)
    if not o:
        print(tag, "no files"); continue
    near = sorted(o["near"], reverse=True)[:3]
    print("%s runs=%d HOLD-triggers=%d %s" % (tag, o["runs"], len(o["drops"]), o["drops"]))
    print("     SERVED-triggers=%d %s ; all geo markings=%d" % (len(o["cust_marks"]), o["cust_marks"], o["all_geo"]))
    print("     longest zero-other-start carry run (top3): %s" % near)
