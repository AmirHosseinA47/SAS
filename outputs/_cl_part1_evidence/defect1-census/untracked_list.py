import os, re, collections, json
HERE = "E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"
SCR = os.path.dirname(os.path.abspath(__file__))
tracked = set(l.strip() for l in open(os.path.join(SCR, "tracked_80ca7b3.txt"), encoding="utf-8") if l.strip())
names = sorted(n for n in os.listdir(HERE) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json"))
census = [n for n in names if not n.startswith("_ffr_xs") and ".xstrace." not in n]
print("all _ffr_*.json:", len(names), " census-eligible:", len(census), " tracked@80ca7b3 _ffr_*.json:", len(tracked))
un = [n for n in names if n not in tracked]
by = collections.defaultdict(list)
for n in un:
    m = re.match(r"^_ffr_(.+?)_(east|south|west|north)_", n)
    by[m.group(1) if m else n].append(n)
print("NOT tracked at 80ca7b3:", len(un))
for t in sorted(by):
    print("  %-14s %3d  %s" % (t, len(by[t]), (" ".join(by[t]) if len(by[t]) <= 4 else by[t][0] + " ... " + by[t][-1])))
# tracked but missing on disk
miss = sorted(tracked - set(names))
print("tracked at 80ca7b3 but not on disk:", len(miss), miss[:10])
# for untracked census-eligible files, their feature-2 status and class
for n in un:
    if n.startswith("_ffr_xs") or ".xstrace." in n:
        continue
    with open(os.path.join(HERE, n), encoding="utf-8") as f:
        d = json.load(f)
    st = os.stat(os.path.join(HERE, n))
    import time
    print("  untracked census file:", n, "feature2:", "exit_starts" in d and "completions" in d, "class:", "ON" if d.get("firefight_log") else "OFF",
          "tag:", d.get("tag"), "mtime:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
          "steps:", len(d.get("ff_steps") or []), "comps:", len(d.get("completions") or []))
