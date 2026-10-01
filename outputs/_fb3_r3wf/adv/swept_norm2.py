"""Synthetic (no simulator): same fire + UAV trajectory, p_bo 0.1 vs 0 vs I-style (zero+renorm).
Held target T at (40,40), never covered, never burning. Track Sp(T)/Sp(issue) and the step drop_swept would fire
if a UAV sweeps part of T's disc late."""
import sys
sys.path.insert(0, r"E:\Projects\SAS")
import numpy as np
from src_extension.knowledge.victim_search_belief import VictimSearchBelief, MotionParams, disc_convolve
H = W = 50
def run(pbo, renorm=False, partial=False):
    b = VictimSearchBelief.with_uniform_prior(H, W, 3, excluded=())
    mp = MotionParams(mode="diffusion", burnover=pbo)
    T = (40, 40); s_issue = None; out = []
    for t in range(1, 121):
        burning = {(x, y) for x in range(0, 25) for y in range(0, min(50, 5 + t // 3))}
        b.predict(burning, mp)
        uav = [(10 + (t % 30), 15)] if t < 100 else []
        if partial and t >= 100:
            uav = [(40, 30)]            # covers part of T's disc late
        b.measure(uav, set(), t)
        if renorm:
            for c in burning: b.p[c] = 0.0
            b.p /= b.p.sum()
        else:
            b.burn_over(burning, pbo)
        Sp = disc_convolve(b.p, b.offsets)[T]
        if t == 20: s_issue = Sp
        if t >= 20: out.append((t, Sp / s_issue, b.dead))
    return out
for lab, kw in (("pbo0.1", dict(pbo=0.1)), ("pbo0", dict(pbo=0.0)), ("I renorm", dict(pbo=1.0, renorm=True))):
    o = run(**kw); op = run(partial=True, **kw)
    print(lab, "ratio@100 %.4f dead@100 %.4f | partial-sweep ratio@120 %.4f" % (o[80][1], o[80][2], op[-1][1]))
