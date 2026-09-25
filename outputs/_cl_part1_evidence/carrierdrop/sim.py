"""Read-only offline estimate: what a custody-kept carrier would do after the recorded drop.

Fire is held at its RECORDED history (burn_intervals). The carrier replays
agents.py _move_toward (2369-2464) toward its fixed exit cell: burning neighbours dropped,
tiers 1-3 over clean cells, tier 4 least risk; with no non-burning neighbour it holds.
Smoke is not recorded, so two variants: smoke never (S0), and smoke on any cell whose
burn interval ended within the last 4 steps (S4, the diagnosis's exhaustion tail).
A carrier dies when its cell is burning in the post-step observation (it moves before the
casualty sweep). It completes on the step after it stands on the exit cell (F0), or on the
step after it stands on ANY boundary cell (F1, for comparison only).
"""
import json
import os

OUT_DIR = r"E:\Projects\SAS\outputs"
HERE = os.path.dirname(os.path.abspath(__file__))
W = H = 50


def burning_at(bi, cell, s):
    for st, en in bi.get("%d,%d" % cell, []):
        if st <= s and (en is None or s < en):
            return True
    return False


def smoky(bi, cell, s, tail):
    if tail <= 0:
        return False
    for st, en in bi.get("%d,%d" % cell, []):
        if en is not None and en <= s < en + tail:
            return True
    return False


def nbrs(c):
    out = []
    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (c[0] + ox, c[1] + oy)
        if 0 <= n[0] < W and 0 <= n[1] < H:
            out.append(n)
    return out


def move_toward(bi, pos, tgt, s, tail):
    cx, cy = pos
    tx, ty = tgt
    dx, dy = tx - cx, ty - cy
    if abs(dx) >= abs(dy):
        pref = (cx + (1 if dx > 0 else -1 if dx < 0 else 0), cy)
    else:
        pref = (cx, cy + (1 if dy > 0 else -1 if dy < 0 else 0))
    d0 = abs(cx - tx) + abs(cy - ty)
    scored = []
    for c in nbrs(pos):
        if burning_at(bi, c, s):
            continue
        da = abs(c[0] - tx) + abs(c[1] - ty)
        adj = any(burning_at(bi, n, s) for n in [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)])
        sm = smoky(bi, c, s, tail)
        scored.append(dict(cell=c, da=da, imp=da < d0, mnt=da == d0, adj=adj, sm=sm, pref=c == pref,
                           risk=(100 if adj else 0) + (10 if sm else 0)))
    if not scored:
        return pos, 0
    pools = [[i for i in scored if i["imp"] and not i["adj"] and not i["sm"]],
             [i for i in scored if i["mnt"] and not i["adj"] and not i["sm"]],
             [i for i in scored if not i["adj"] and not i["sm"]]]
    for t, p in enumerate(pools, 1):
        if p:
            return min(p, key=lambda i: (i["da"], 0 if i["pref"] else 1))["cell"], t
    return min(scored, key=lambda i: (i["risk"], i["da"], 0 if i["pref"] else 1))["cell"], 4


def on_bnd(c):
    return c[0] in (0, W - 1) or c[1] in (0, H - 1)


def run(bi, start, tgt, drop_step, horizon, tail, f1):
    pos = start
    path = []
    for s in range(drop_step + 1, horizon + 1):
        # completion check at the start of the advance (agents.py:1820)
        if pos == tgt or (f1 and on_bnd(pos)):
            return ("COMPLETE", s, pos, path)
        pos, tier = move_toward(bi, pos, tgt, s, tail)
        path.append((s, pos, tier))
        if burning_at(bi, pos, s):
            return ("DIES", s, pos, path)
    return ("HORIZON", horizon, pos, path)


def main():
    with open(os.path.join(HERE, "drops.json"), encoding="utf-8") as f:
        rows = json.load(f)
    for r in rows:
        if r["kind"] in ("HORIZON", "A"):
            continue
        if not any(u[3] == "replacement_after_blocked" and u[1] == r["ff"] for u in r["unassigns"]):
            continue
        with open(os.path.join(OUT_DIR, r["file"]), encoding="utf-8") as f:
            d = json.load(f)
        bi = d.get("burn_intervals") or {}
        horizon = len(d["ff_steps"])
        drop = tuple(r["cell_prev"])
        tgt = tuple(r["exit"])
        print("=" * 90)
        print(r["tag"], r["file"], r["ff"], r["vid"], "drop", r["end"], drop, "exit", tgt, "recorded kind", r["kind"],
              "recorded ff death", r["ff_death"], "victim death", r["v_death"])
        for tail in (0, 4):
            for f1 in (False, True):
                out, s, pos, path = run(bi, drop, tgt, r["end"], horizon, tail, f1)
                print("   smoke_tail=%d F1=%s -> %s at step %s cell %s after %d moves; path %s" % (
                    tail, f1, out, s, pos, len(path), path[:30]))


if __name__ == "__main__":
    main()
