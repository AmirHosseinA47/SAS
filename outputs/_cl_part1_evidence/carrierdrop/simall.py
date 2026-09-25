"""Read-only: the hold-custody estimate (sim.py rules) over EVERY distinct route_blocked carrier
drop in the record (scan.json), one representative file per distinct drop."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim  # noqa: E402

OUT_DIR = r"E:\Projects\SAS\outputs"
HERE = os.path.dirname(os.path.abspath(__file__))


def exit_target(p):
    x, y = p
    dists = {(0, y): x, (49, y): 49 - x, (x, 0): y, (x, 49): 49 - y}
    return min(dists, key=dists.get)


with open(os.path.join(HERE, "scan.json"), encoding="utf-8") as f:
    S = json.load(f)
seen = {}
for d in S["drops"]:
    if d["reason"] != "replacement_after_blocked" or d["file"].startswith("_ffr_xs"):
        continue
    key = (tuple(d["tup"]), d["ff"], d["vid"], d["step"], tuple(d["cell"]))
    seen.setdefault(key, []).append(d)
for key, ds in sorted(seen.items(), key=lambda kv: str(kv[0])):
    d0 = ds[0]
    with open(os.path.join(OUT_DIR, d0["file"]), encoding="utf-8") as f:
        d = json.load(f)
    st = [e for e in d["exit_starts"] if e["ff"] == d0["ff"] and e["victim"] == d0["vid"] and e["step"] <= d0["step"]]
    p0 = tuple(st[-1]["ff_pos"])
    tgt = exit_target(p0)
    bi = d.get("burn_intervals") or {}
    horizon = len(d["ff_steps"])
    wrote = sum(1 for r in (d.get("firefight_log") or []) if r.get("wrote"))
    crn = bool((d.get("extra_params") or {}).get("FM2P_CRN"))
    outs = []
    for tail in (0, 4):
        o, s, pos, path = sim.run(bi, tuple(d0["cell"]), tgt, d0["step"], horizon, tail, False)
        outs.append("%s@%s%s" % (o, s, pos))
    o1, s1, pos1, _ = sim.run(bi, tuple(d0["cell"]), tgt, d0["step"], horizon, 0, True)
    tags = sorted(set(x["tag"] for x in ds))
    print("%s/%s/%s %s %s drop@%d %s exit %s ffdead=%s vdeath=%s | S2 est: %s | F1 est: %s@%s | fire writes in file=%d CRN=%s | %d files: %s" % (
        key[0][0], key[0][1], key[0][2], d0["ff"], d0["vid"], d0["step"], tuple(d0["cell"]), tgt, d0["ff_dead_at_drop"], d0["vdeath"],
        " / ".join(outs), o1, s1, wrote, crn, len(ds), ",".join(tags)[:120]))
