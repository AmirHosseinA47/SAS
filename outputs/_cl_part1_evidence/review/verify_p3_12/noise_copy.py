import json, os, re
O = "E:/Projects/SAS/outputs"
u30 = []
for line in open(os.path.join(O, "_ug_seeds.txt"), encoding="utf-8"):
    m = re.match(r"^(east|south)\|(half|default)\s+seed (\d+)", line)
    if m:
        u30.append((m.group(1), "def" if m.group(2) == "default" else "half", int(m.group(3))))
def ev(tag, t):
    p = os.path.join(O, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], t[1], t[2]))
    if not os.path.exists(p): return None
    d = json.load(open(p, encoding="utf-8"))
    e = d["eval"]
    return e["rescued"], e["dead"], e["firefighter_deaths"], d["fire_digests"]
def cmp(a, b):
    ra = rb = 0; up = down = same = 0; firesame = 0; n = 0
    for t in u30:
        x, y = ev(a, t), ev(b, t)
        if x is None or y is None: continue
        n += 1; ra += x[0]; rb += y[0]
        if y[0] > x[0]: up += 1
        elif y[0] < x[0]: down += 1
        else: same += 1
        if x[3] == y[3]: firesame += 1
    print("%-5s -> %-5s n=%d rescued %d -> %d  up %d down %d same %d  fire-identical runs %d" % (a, b, n, ra, rb, up, down, same, firesame))
for a, b in (("ugC","ugD"),("ugKC","ugKD"),("ugKC","ugKY"),("ugKD","ugKY"),("uhC","uhD"),("uhD","uhY"),("ugD","ugY")):
    cmp(a, b)
