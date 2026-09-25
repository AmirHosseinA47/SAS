"""For every recorded route_blocked CARRIER drop, the reconstructed geo streak of the
carried victim at the step before the drop, and the number of living (non-exiting,
on-grid, alive) other units then.

Read-only. Non-recursive os.listdir of outputs/, names _ffr_*.json only; the quarantine
directory name never matches and is skipped explicitly anyway.
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from streak import burning_at, bfs  # noqa: E402

OUT = r"E:\Projects\SAS\outputs"
Q = "_firemech_rewound_20260914"


def streak_series(d, vid, upto):
    bi = d["burn_intervals"]
    ffs = d["ff_steps"]
    binds = d["ff_bind_steps"]
    vs = d["victim_steps"]
    streak = 0
    prev = {}
    res = {}
    for s in range(1, upto + 1):
        i = s - 1
        burning = burning_at(bi, s)
        living = [(r[0], tuple(r[1])) for r in ffs[i]
                  if not (r[5] or r[2] == "dead" or r[4] or r[1] is None)]
        reach = bfs([c for _, c in living], burning)
        v = {r[0]: r for r in vs[i]}.get(vid)
        vcell = tuple(v[1]) if v and v[1] is not None else None
        vstat = v[2] if v else ""
        bindmap = {b[0]: b[1] for b in binds[i]}
        aff = ""
        for r in ffs[i]:
            if r[5] or not r[3] or r[2] in ("dead", "route_blocked"):
                continue
            if bindmap.get(r[0]) == vid:
                aff = r[0]
                break
        appr = False
        newd = {}
        if vcell is not None:
            for fid, c in living:
                dist = abs(c[0] - vcell[0]) + abs(c[1] - vcell[1])
                newd[fid] = dist
                if fid == aff and prev.get(fid) is not None and dist < prev[fid]:
                    appr = True
        prev = newd
        geo = vcell is not None and vcell in reach
        if vstat in ("rescued", "dead", "unreachable", "cancelled"):
            streak = 0
        elif not appr and not geo:
            streak += 1
        else:
            streak = 0
        res[s] = (streak, len(living))
    return res


def main():
    names = sorted(n for n in os.listdir(OUT)
                   if n != Q and n.startswith("_ffr_") and n.endswith(".json"))
    seen = {}
    for n in names:
        p = os.path.join(OUT, n)
        with open(p, "rb") as f:
            raw = f.read()
        if b"replacement_after_blocked" not in raw:
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        if "ff_steps" not in d or "burn_intervals" not in d or "ff_bind_steps" not in d:
            continue
        for u in d.get("unassigns", []) or []:
            if u.get("reason") != "replacement_after_blocked":
                continue
            s = int(u["step"])
            if s < 2:
                continue
            prow = {r[0]: r for r in d["ff_steps"][s - 2]}
            pb = {b[0]: b[1] for b in d["ff_bind_steps"][s - 2]}
            r = prow.get(u["ff"])
            if not r or not r[4] or pb.get(u["ff"]) != u["vid"]:
                continue  # not a carrier drop
            ss = streak_series(d, u["vid"], s)
            st_prev, liv_prev = ss[s - 1]
            key = (d.get("wind"), d.get("roles"), d.get("seed"), u["ff"], u["vid"], s)
            seen.setdefault(key, []).append((d.get("tag"), st_prev, liv_prev))
    print("distinct drops (wind,roles,seed,ff,vid,step):", len(seen))
    for k, v in sorted(seen.items(), key=lambda kv: -max(x[1] for x in kv[1])):
        print(k, "max streak before drop", max(x[1] for x in v),
              "living others", sorted(set(x[2] for x in v)), "tags", [x[0] for x in v][:6])


if __name__ == "__main__":
    main()
