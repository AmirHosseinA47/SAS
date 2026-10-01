"""For each flagged victim detected by a searcher: the detecting searcher's active target at the detection step."""
from common import *  # noqa

for tag in RESCREEN:
    for seed, d in sorted(load(tag).items()):
        cl = classify(d)
        du = det_uav(tag, seed)
        smp = samples(d)
        for v, info in cl.items():
            if not info or info["max"] <= THRESH or v not in du:
                continue
            t, uid = du[v]
            iss = [r for r in d["fb3"]["issued"] if r[1] == uid and r[0] <= t]
            if not iss:
                print(tag, seed, v, "no issued target for", uid)
                continue
            r = iss[-1]
            p = vrow(d, t, v)[1:3]
            near = min(smp, key=lambda x: (abs(x[0] - r[0]), x[0]))
            print("%-8s %s %-9s det %d by %s | active target %s issued at %d (L %d, G %s, S %s) dist target->victim(t) %.1f |"
                  " DEAD at issue (nearest sample %d) %.3f | n_unf*alive %.4f" % (
                      tag, seed, v, t, uid, r[2], r[0], r[3], r[4], r[5], dist(tuple(r[2]), tuple(p)), near[0], near[1],
                      near[2] * near[3]))
