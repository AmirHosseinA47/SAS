"""For each distinct custody case: over the whole 30-step streak window, the
carrier's fire-free 4-connected region (burning cells impassable, as in
_safe_path_reachable_cells), whether it holds the exit target, and whether
BFS from the carrier would have covered each co-marked victim at least once.
Also validates the 5 non-empty-start markings against the model's verdict."""
import json, os
from collections import deque, defaultdict

OUT = r"E:\Projects\SAS\outputs"
SCRATCH = os.path.dirname(os.path.abspath(__file__))
W = H = 50
rows = json.load(open(os.path.join(SCRATCH, "scan_c2.json"), encoding="utf-8"))


def burning_at(d, step):
    out = set()
    for key, ivs in (d.get("burn_intervals") or {}).items():
        for s, e in ivs:
            if s <= step and (e is None or step < e):
                x, y = key.split(",")
                out.add((int(x), int(y)))
                break
    return out


def bfs(starts, burning):
    seen = set()
    q = deque()
    for s in starts:
        s = tuple(s)
        if s in burning or s in seen:
            continue
        seen.add(s)
        q.append(s)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if not (0 <= n[0] < W and 0 <= n[1] < H) or n in seen or n in burning:
                continue
            seen.add(n)
            q.append(n)
    return seen


groups = defaultdict(list)
for r in rows:
    groups[(r["wind"], r["roles"], r["seed"], r["victim"], r["step"])].append(r)

cache = {}


def load(tag, wind, roles, seed):
    k = (tag, wind, roles, seed)
    if k not in cache:
        cache.clear()
        cache[k] = json.load(open(os.path.join(OUT, "_ffr_%s_%s_%s_%s.json" % k), encoding="utf-8"))
    return cache[k]


print("=== custody windows ===")
for k, g in sorted(groups.items()):
    cr = [x for x in g if x["custody"]]
    if not cr:
        continue
    r = cr[0]
    d = load(r["tag"], r["wind"], r["roles"], r["seed"])
    s = r["step"]
    c = r["carry"]
    cu = c["carrier"]
    et = tuple(c["exit_target"])
    lo = s - 29
    ffs = d["ff_steps"]
    vs = d["victim_steps"]
    min_reg = None
    exit_in_all = True
    other_cov = defaultdict(int)
    others = [x["victim"] for x in rows if (x["wind"], x["roles"], x["seed"], x["step"], x["tag"]) == (r["wind"], r["roles"], r["seed"], s, r["tag"]) and x["victim"] != r["victim"]]
    positions = []
    other_units = []
    for st in range(lo, s + 1):
        row = ffs[st - 1]
        cc = [x for x in row if x[0] == cu][0]
        cell = tuple(cc[1])
        positions.append(cell)
        other_units.append([(x[0], x[2], x[4], x[5]) for x in row if x[0] != cu])
        burning = burning_at(d, st)
        reg = bfs([cell], burning)
        min_reg = len(reg) if min_reg is None else min(min_reg, len(reg))
        if et not in reg:
            exit_in_all = False
        for ov in others:
            vr = [x for x in vs[st - 1] if x[0] == ov]
            if vr and vr[0][1] and tuple(vr[0][1]) in reg:
                other_cov[ov] += 1
    # oscillation: count reversals (A->B->A)
    rev = sum(1 for i in range(2, len(positions)) if positions[i] == positions[i - 2] and positions[i] != positions[i - 1])
    # first step the other unit was dead / state before window
    print(k, "tag", r["tag"], "window", lo, s, "carrier", cu, "pickup", c["pickup_step"], "exit", et,
          "min_carrier_region", min_reg, "exit_in_region_every_step", exit_in_all,
          "reversals", rev, "distinct_cells", len(set(positions)),
          "others_marked", others, "steps_in_carrier_region(of 30)", dict(other_cov))
    print("    path", positions[0], "->", positions[-1], "| other unit at window start:", other_units[0], "at pickup-1:",
          [(x[0], x[2], x[4], x[5]) for x in ffs[c["pickup_step"] - 2] if x[0] != cu] if c["pickup_step"] else None)

print("\n=== non-empty-start markings: model verdict vs reconstruction ===")
for k, g in sorted(groups.items()):
    r = g[0]
    if r["starts_empty"] or any(x["custody"] for x in g):
        continue
    d = load(r["tag"], r["wind"], r["roles"], r["seed"])
    s = r["step"]
    starts = [tuple(x[1]) for x in d["ff_steps"][s - 1] if x[0] in r["living"]]
    burning = burning_at(d, s)
    reg = bfs(starts, burning)
    vr = [x for x in d["victim_steps"][s - 1] if x[0] == r["victim"]][0]
    print(k, "tags", [x["tag"] for x in g], "living", r["living"], "victim cell", vr[1],
          "recon geo_reachable", (tuple(vr[1]) in reg) if vr[1] else None, "region", len(reg))
