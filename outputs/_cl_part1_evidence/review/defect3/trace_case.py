"""Trace a recorded D3 case: carrier + carried victim positions, burn state, statuses.
Read-only on E:/Projects/SAS/outputs (named files only)."""
import json, sys

path, ff, vid, lo, hi = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
d = json.load(open(path))
bi = d["burn_intervals"]


def burning(cell, step):
    iv = bi.get("%d,%d" % cell)
    if not iv:
        return False
    for a, b in iv:
        if a <= step and (b is None or step < b):
            return True
    return False

print("eval", {k: d["eval"][k] for k in ("rescued", "dead", "unreachable", "geographically_isolated", "never_detected", "firefighter_deaths", "terminal_step")})
print("exit_starts", [e for e in d["exit_starts"] if e["ff"] == ff])
print("unassigns", d["unassigns"])
print("escape", d["unreachable_escape_log"])
print("sample bi", list(bi.items())[:2])
for s in range(lo, hi + 1):
    i = s - 1
    ffr = [r for r in d["ff_steps"][i] if r[0] == ff][0]
    br = [r for r in d["ff_bind_steps"][i] if r[0] == ff][0] if d.get("ff_bind_steps") else None
    vr = [r for r in d["victim_steps"][i] if r[0] == vid][0]
    fpos = tuple(ffr[1]) if ffr[1] else None
    nb = ""
    if fpos:
        x, y = fpos
        nb = "".join("B" if burning((x + dx, y + dy), s) else "." for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))
    print(s, ffr, br, vr, nb)
