import json, os
from collections import deque

OUT = r"E:\Projects\SAS\outputs"
W = H = 50


def load(tag, wind="east", roles="def", seed=101):
    p = os.path.join(OUT, "_ffr_%s_%s_%s_%s.json" % (tag, wind, roles, seed))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def burning_at(d, step):
    out = set()
    for key, ivs in (d.get("burn_intervals") or {}).items():
        for s, e in ivs:
            if s <= step and (e is None or step < e):
                x, y = key.split(",")
                out.add((int(x), int(y)))
                break
    # still-open intervals are not in burn_intervals (burn_open is not exported)
    return out


def bfs(start, burning):
    if start in burning:
        return set()
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if not (0 <= n[0] < W and 0 <= n[1] < H):
                continue
            if n in seen or n in burning:
                continue
            seen.add(n)
            q.append(n)
    return seen


def summary(tag):
    d = load(tag)
    print("=" * 30, tag, "steps", d.get("steps"))
    ev = d.get("eval") or {}
    print("eval rescued=%s dead=%s unreachable=%s geo=%s nd=%s ffdeaths=%s terminal=%s causes=%s" % (
        ev.get("rescued"), ev.get("dead"), ev.get("unreachable"), ev.get("geographically_isolated"),
        ev.get("never_detected"), ev.get("firefighter_deaths"), ev.get("terminal_step"), ev.get("unreachable_causes")))
    print("params FF/absence:", {k: v for k, v in (d.get("params") or {}).items() if "ABSENCE" in k or "FIREFIGHT" in k or "FLEE" in k})
    print("extra_params:", d.get("extra_params"))
    print("exit_starts", d.get("exit_starts"))
    print("completions", d.get("completions"))
    print("assigns", d.get("assigns"))
    print("unassigns", d.get("unassigns"))
    print("unreachable_escape_log", d.get("unreachable_escape_log"))
    print("absence_log", d.get("absence_log"))
    print("recycles", d.get("recycles"))
    # deaths
    ffs = d["ff_steps"]
    vs = d["victim_steps"]
    prev = {}
    for i, row in enumerate(ffs):
        for r in row:
            if r[5] and not prev.get(r[0]):
                print("FF death", r[0], "step", i + 1, "at", r[1])
            prev[r[0]] = r[5]
    prevs = {}
    for i, row in enumerate(vs):
        for r in row:
            if prevs.get(r[0]) != r[2]:
                print("victim status", r[0], "step", i + 1, "->", r[2], "at", r[1])
            prevs[r[0]] = r[2]
    fl = [e for e in (d.get("victim_flee_log") or []) if e.get("victim_id") == "victim_0"]
    print("victim_0 flee moves:", [(e["step"], e["from"], e["to"]) for e in fl])
    return d


def enclosure(d, lo, hi):
    ffs = d["ff_steps"]
    vs = d["victim_steps"]
    for step in range(lo, hi + 1):
        i = step - 1
        burning = burning_at(d, step)
        u1 = [r for r in ffs[i] if r[0].endswith("unit_1")][0]
        cell = tuple(u1[1]) if u1[1] else None
        v0 = [r for r in vs[i] if r[0] == "victim_0"][0]
        reach = bfs(cell, burning) if cell else set()
        edge = sum(1 for c in reach if c[0] in (0, W - 1) or c[1] in (0, H - 1))
        # neighbours of the cell
        nb = []
        if cell:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cell[0] + dx, cell[1] + dy)
                if n in burning:
                    nb.append("B")
                elif any((n[0] + a, n[1] + b) in burning for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    nb.append("a")
                else:
                    nb.append(".")
        other = []
        for vr in vs[i]:
            if vr[0] in ("victim_2", "victim_3") and vr[1]:
                other.append("%s:%s" % (vr[0][-1], tuple(vr[1]) in reach))
        print(step, "u1", cell, "e%d" % u1[4], "v0", tuple(v0[1]) if v0[1] else None, v0[2],
              "nburning", len(burning), "region", len(reach), "edgecells", edge,
              "exit(49,20) in region", (49, 20) in reach, "nb[+x,-x,+y,-y]", "".join(nb), "others", " ".join(other))


d = summary("f2cDRY")
enclosure(d, 140, 180)
summary("f2cOFF")
summary("f2cEFS")
