"""For every carrier drop (unassign reason replacement_after_blocked of a unit exiting at the
previous row) in the shipped-config ug*/uh* runs, print the carried victim's reconstructed
custody streak at the drop step (consecutive steps with no live, on-grid, non-exiting unit's
burning-only region covering the carrier cell). Read-only, named files, non-recursive glob."""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import deque

OUT = r"E:\Projects\SAS\outputs"
W = H = 50
pat = re.compile(r"^_ffr_([A-Za-z0-9]+)_(east|south|west|north)_(half|def)_(\d+)\.json$")


def burning_at(d, t):
    out = set()
    for key, ivs in (d.get("burn_intervals") or {}).items():
        for s, e in ivs:
            if s <= t and (e is None or t < e):
                x, y = key.split(","); out.add((int(x), int(y))); break
    return out


def bfs(starts, burning):
    seen = set(); q = deque()
    for s in starts:
        s = tuple(s)
        if s in burning or s in seen:
            continue
        seen.add(s); q.append(s)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < W and 0 <= n[1] < H and n not in seen and n not in burning:
                seen.add(n); q.append(n)
    return seen


tags = sys.argv[1].split(",")
files = sorted(sum((glob.glob(os.path.join(OUT, "_ffr_%s_*.json" % t)) for t in tags), []))
for f in files:
    bn = os.path.basename(f)
    if not pat.match(bn):
        continue
    d = json.load(open(f, encoding="utf-8"))
    ffs = d["ff_steps"]; binds = d.get("ff_bind_steps")
    if not binds:
        continue
    for u in d.get("unassigns", []):
        if u.get("reason") != "replacement_after_blocked":
            continue
        s = int(u["step"])
        prow = ffs[s - 2]
        uid = None
        for r in prow:
            if (r[0] == u["ff"] or r[0].endswith(u["ff"])) and r[4] and not r[5]:
                uid = r[0]
        if uid is None:
            continue
        v = u["vid"]
        # walk back from s-1 counting custody streak
        streak = 0
        t = s - 1
        while t >= 1:
            row = ffs[t - 1]
            b = {r[0]: r[1] for r in binds[t - 1]}
            me = [r for r in row if r[0] == uid]
            if not me or not me[0][4] or b.get(uid) != v:
                break
            living = [tuple(r[1]) for r in row if not r[5] and str(r[2]).lower() != "dead" and not r[4] and r[1] is not None]
            if tuple(me[0][1]) in bfs(living, burning_at(d, t)):
                break
            streak += 1
            t -= 1
        print(bn, "drop@", s, uid, v, "custody streak before drop:", streak)
