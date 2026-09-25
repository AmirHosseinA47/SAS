import re, sys
rows = []
for line in open(r"E:/Projects/SAS/outputs/_cl_replay/cf_census.txt", encoding="utf-8"):
    if "|" not in line or "s0=" not in line:
        continue
    head, tail = line.split("|", 1)
    d = dict(kv.split("=") for kv in tail.split())
    d = {k: (None if v == "None" else int(v)) for k, v in d.items()}
    m = re.search(r"(\S+\.json)\s+(\S+)\s+(\S+)\s+s0=(\d+)\s+rec=(\d+)\s+dist=(\d+)", head)
    rows.append((m.groups(), d))
print("detail rows", len(rows))
for a, b in (("F5", "F1"), ("F5", "F1F4"), ("F5", "F4"), ("F5", "base")):
    worse = [(g, d[a], d[b]) for g, d in rows if d[a] is not None and d[b] is not None and d[a] > d[b]]
    print(a, ">", b, len(worse))
    for w in worse[:12]:
        print("   ", w)
