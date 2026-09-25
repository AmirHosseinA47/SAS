"""Read-only: per distinct isolation-escape carrier case, the carry leg step by step."""
import json
import os
import sys

OUT = r"E:\Projects\SAS\outputs"
files = sys.argv[1:]
for n in files:
    with open(os.path.join(OUT, n), encoding="utf-8") as fh:
        d = json.load(fh)
    ffs = d["ff_steps"]
    vs = d["victim_steps"]
    dim = d.get("dim")
    print("=" * 70)
    print(n, "dim", dim, "steps", d.get("steps"), "terminal", d.get("terminal_step"))
    print("eval", {k: d["eval"].get(k) for k in ("rescued", "dead", "unreachable", "total_victims", "firefighter_deaths")})
    print("escape log", d.get("unreachable_escape_log"))
    print("unassigns", d.get("unassigns"))
    print("exit_starts", d.get("exit_starts"))
    print("completions", d.get("completions"))
    print("absence", [(a.get("event"), a.get("step"), a.get("ff")) for a in d.get("absence_log") or []])
    for u in d.get("unassigns") or []:
        if "isolat" not in str(u.get("reason")):
            continue
        ff = u["ff"]
        vid = u["vid"]
        s = int(u["step"])
        es = [e for e in d["exit_starts"] if e["ff"] == ff and e["victim"] == vid and e["step"] <= s][-1]
        p0 = es["step"]
        x, y = es["ff_pos"]
        H = W = 50
        dists = {(0, y): x, (H - 1, y): H - 1 - x, (x, 0): y, (x, W - 1): W - 1 - y}
        ex = min(dists, key=dists.get)
        print(f"-- carry {ff}/{vid} pickup {p0} at {es['ff_pos']} exit {ex} unassign {s}")
        prev = None
        for i in range(max(0, p0 - 3), min(len(ffs), s + 4)):
            row = {r[0]: r for r in ffs[i]}
            me = row[ff]
            others = [(k, r[2], r[1], r[4]) for k, r in row.items() if k != ff]
            vrow = [v for v in vs[i] if v[0] == vid][0]
            pos = me[1]
            dex = abs(pos[0] - ex[0]) + abs(pos[1] - ex[1]) if pos else None
            print(f"  {i+1:4d} {me[1]} {me[2]:12s} asg={int(me[3])} ex={int(me[4])} dead={int(me[5])} d_exit={dex}  victim={vrow[1]} {vrow[2]:12s} others={others}")
