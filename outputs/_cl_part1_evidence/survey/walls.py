import re, sys, statistics, collections, os
os.chdir(r"E:\Projects\SAS\outputs")
LOGS = sys.argv[1:]
pat = re.compile(r"^\[(\d\d:\d\d:\d\d)\] DONE (\S+) rc=(\d+) (\d+)s (\S+) (\S+) seed=(\d+) .*wall=(\d+)s")
start = re.compile(r"^\[(\d\d:\d\d:\d\d)\] POOL START (.*)$")
for lg in LOGS:
    by = collections.defaultdict(list)
    heads = []
    first = last = None
    for ln in open(lg, encoding="utf-8", errors="replace"):
        m = start.match(ln)
        if m:
            heads.append(m.group(1) + " " + m.group(2)[:200])
        m = pat.match(ln)
        if m:
            name = m.group(2)
            arm = name.split("_")[0]
            by[arm].append(int(m.group(8)))
            last = m.group(1)
    print("==", lg)
    for h in heads:
        print("  START", h)
    tot = []
    for arm, ws in sorted(by.items()):
        tot += ws
        print("  %-8s n=%3d mean=%6.0f median=%6.0f min=%5d max=%5d" % (arm, len(ws), statistics.mean(ws), statistics.median(ws), min(ws), max(ws)))
    if tot:
        print("  ALL      n=%3d mean=%6.0f median=%6.0f  last DONE %s" % (len(tot), statistics.mean(tot), statistics.median(tot), last))
