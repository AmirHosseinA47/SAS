"""Mode-1 direct effect on BROKEN legs (fire as recorded, up to the first boundary touch):
a broken exit leg whose carrier stood on a boundary cell before the break becomes a
completion at (first boundary end-of-step + 1) under mode 1. Is that completion stalled by
the draft's M1-primary (n > d + 5, d = nearest-boundary distance from pickup)?
Read-only; non-recursive listing of outputs/, quarantine skipped by name."""
import json
import os
import re

OUT = r"E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"
PAT = re.compile(r"^_ffr_(ug[A-Za-z]*|uh[A-Za-z]*)_(east|south|west|north)_(half|def)_(\d+)\.json$")


def bd(p):
    x, y = p
    return min(x, 49 - x, y, 49 - y)


names = sorted(n for n in os.listdir(OUT) if n != QUAR and PAT.match(n))
for n in names:
    with open(os.path.join(OUT, n), encoding="utf-8") as f:
        d = json.load(f)
    es = d.get("exit_starts") or []
    cs = d.get("completions") or []
    fs = d.get("ff_steps") or []
    steps = d.get("steps")
    for e in es:
        ff, v, s0 = e["ff"], e["victim"], e["step"]
        if not e.get("ff_pos"):
            continue
        done = [c for c in cs if c["ff"] == ff and c["victim"] == v and c["step"] >= s0]
        # a later exit_start by same pair ends this leg
        nxt = [x["step"] for x in es if x["ff"] == ff and x["victim"] == v and x["step"] > s0]
        if done and (not nxt or done[0]["step"] <= min(nxt)):
            continue
        # broken or horizon: walk until not exiting
        p0 = tuple(e["ff_pos"])
        d0 = bd(p0)
        firstb = None
        end = None
        for k in range(s0 - 1, len(fs)):
            row = [r for r in fs[k] if r[0] == ff]
            if not row:
                continue
            r = row[0]
            if not r[4] and k + 1 > s0:
                end = (k + 1, r[2], r[5])
                break
            if r[1] and r[4] and firstb is None and bd(r[1]) == 0:
                firstb = (k + 1, tuple(r[1]))
        if firstb is None:
            print("%-44s %s %s s0=%d d=%d NO boundary touch end=%s" % (n, v, ff, s0, d0, end))
            continue
        n1 = firstb[0] + 1 - s0
        d1 = abs(firstb[1][0] - p0[0]) + abs(firstb[1][1] - p0[1])
        print("%-44s %s %s s0=%d d=%d firstB=%s mode1_leg=%d stalled_primary=%s stalled_reached=%s end=%s steps=%s" % (
            n, v, ff, s0, d0, firstb, n1, n1 > d0 + 5, n1 > d1 + 5, end, steps))
