import json, os
HERE = "E:/Projects/SAS/outputs"
C13 = [("east", "half", s) for s in (101, 202, 303, 404, 505)] + \
      [("south", "half", s) for s in (101, 202, 303, 404, 505)] + \
      [("east", "def", s) for s in (101, 202, 303)]


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


for tag in ("ugD", "ugKD", "f2cEFS", "fmEFS", "fmDRY", "f2cDRY"):
    tot = 0
    nlegs = 0
    lines = []
    for w, r, s in C13:
        fn = os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, w, r, s))
        if not os.path.exists(fn):
            continue
        d = json.load(open(fn, encoding="utf-8"))
        starts = d.get("exit_starts") or []
        for c in d.get("completions") or []:
            st = [e for e in starts if e.get("victim") == c.get("victim") and e.get("step", 10 ** 9) <= c.get("step", -1)]
            if not st or not c.get("exit_target"):
                continue
            s0 = st[-1]
            dist = man(s0["ff_pos"], c["exit_target"])
            leg = c["step"] - s0["step"]
            nlegs += 1
            if leg > dist + 5:
                tot += 1
                lines.append("%s/%s/%d %s leg %d d %d" % (w, r, s, c["victim"], leg, dist))
    print(tag, "C13 stalls", tot, "of", nlegs, lines)
