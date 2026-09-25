"""Read-only: compact summary of each isolation-escape unassign of an exiting carrier."""
import json
import os

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
names = sorted(n for n in os.listdir(OUT) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json"))
seen = {}
for n in names:
    with open(os.path.join(OUT, n), encoding="utf-8") as fh:
        d = json.load(fh)
    ffs = d.get("ff_steps") or []
    if not ffs:
        continue
    vs = d.get("victim_steps") or []
    for u in d.get("unassigns") or []:
        if "isolat" not in str(u.get("reason")):
            continue
        s = int(u["step"])
        ff = u["ff"]
        prev = {r[0]: r for r in ffs[s - 2]}
        if not prev[ff][4]:
            continue
        vid = u["vid"]
        es = [e for e in d["exit_starts"] if e["ff"] == ff and e["victim"] == vid and e["step"] <= s][-1]
        p0 = es["step"]
        x, y = es["ff_pos"]
        H = W = 50
        dists = {(0, y): x, (H - 1, y): H - 1 - x, (x, 0): y, (x, W - 1): W - 1 - y}
        ex = min(dists, key=dists.get)
        # last step (<= s-1) at which some OTHER unit was alive, on grid, not exiting
        last_other = None
        for i in range(s - 2, -1, -1):
            row = ffs[i]
            if any(r[0] != ff and not r[5] and r[1] is not None and not r[4] and r[2] != "dead" for r in row):
                last_other = i + 1
                break
        others_desc = [(r[0], r[2], r[1] is None) for r in ffs[s - 2] if r[0] != ff]
        pos_at = [tuple(ffs[i][[r[0] for r in ffs[i]].index(ff)][1]) for i in range(max(p0 - 1, s - 11), s - 1)]
        pos_prev = prev[ff][1]
        d_exit = abs(pos_prev[0] - ex[0]) + abs(pos_prev[1] - ex[1])
        marked_same = [e["victim_id"] for e in d.get("unreachable_escape_log") or [] if int(e["step"]) == s]
        # fate of carried victim at the end
        vend = [v for v in vs[-1] if v[0] == vid][0]
        key = (d.get("wind"), d.get("scenario"), d.get("seed"), ff, vid, p0, s)
        seen.setdefault(key, []).append(d.get("tag"))
        if len(seen[key]) > 1:
            continue
        print(f"{n}: wind={d.get('wind')} scen={d.get('scenario')} seed={d.get('seed')} nFF={len(ffs[0])}")
        print(f"   carry {ff}/{vid} pickup={p0}@{es['ff_pos']} exit={ex} unassign={s} carry_steps={s - p0}"
              f" d_exit_prev={d_exit} last_other_living_step={last_other} others={others_desc}")
        print(f"   distinct cells over the last 10 carrying steps: {len(set(pos_at))}; marked same step: {marked_same};"
              f" carried victim at end: {vend[1]} {vend[2]}; eval rescued={d['eval'].get('rescued')} unreachable={d['eval'].get('unreachable')}")
print()
for k, tags in seen.items():
    print(k, len(tags), sorted(tags))
