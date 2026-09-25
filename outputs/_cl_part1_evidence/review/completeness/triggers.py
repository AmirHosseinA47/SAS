"""How often would HOLD (carrier route_blocked drop) and SERVED (isolation marking of a
carried victim) even TRIGGER in the shipped configuration's recorded arms?
Reads explicit _ffr_<tag>_*.json names from a NON-recursive listing that skips the
quarantine by name."""
import json, os, re
O = "E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"
TAGS = ["ugD", "uhD", "ugKD", "uhC", "ugC", "ugKC"]
names = [n for n in os.listdir(O) if n != QUAR and n.endswith(".json") and n.startswith("_ffr_")]
pat = re.compile(r"^_ffr_(%s)_(east|south|west|north)_(half|def)_(\d+)\.json$" % "|".join(TAGS))
res = {}
for n in sorted(names):
    m = pat.match(n)
    if not m:
        continue
    tag = m.group(1)
    d = json.load(open(os.path.join(O, n), encoding="utf-8"))
    fs = d.get("ff_steps") or []
    exiting_at = {}
    for i, row in enumerate(fs):
        for r in row:
            exiting_at[(i + 1, r[0])] = bool(r[4])   # end of step i+1
    drops, iso = [], []
    for u in d.get("unassigns") or []:
        s, ff = u["step"], u["ff"]
        was_exiting = exiting_at.get((s - 1, ff), False)
        if not was_exiting:
            continue
        if u.get("reason") == "replacement_after_blocked":
            drops.append((s, ff, u.get("vid")))
        elif u.get("reason") == "geographically_isolated":
            iso.append((s, ff, u.get("vid")))
    r = res.setdefault(tag, {"runs": 0, "drop_runs": [], "iso_runs": [], "steps": set()})
    r["runs"] += 1
    r["steps"].add(d.get("steps"))
    key = "%s/%s/%s" % (m.group(2), m.group(3), m.group(4))
    if drops:
        r["drop_runs"].append((key, drops))
    if iso:
        r["iso_runs"].append((key, iso))
for tag, r in res.items():
    print(tag, "runs", r["runs"], "steps", sorted(r["steps"]))
    print("   exiting-unit route_blocked drops:", len(r["drop_runs"]), r["drop_runs"])
    print("   exiting-unit isolation releases:", len(r["iso_runs"]), r["iso_runs"])
