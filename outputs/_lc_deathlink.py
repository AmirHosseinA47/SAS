"""Link each firefighter death in the 62b4fbe 13-run sample to any last_cell
sole-exit refusal in the K steps before it.

The idle-retreat round bucketed deaths by the state at the LETHAL step only.
This asks a different question: in the run-up to the death, did the last_cell
guard ever refuse the unit's only free neighbour, and what was it refusing?
"""
from __future__ import annotations
import glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
MAXC = 6
WINDOW = 10


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def tup(x):
    return None if x is None else (int(x[0]), int(x[1]))


def eff(r):
    cell, origin, last = tup(r.get("pos")), tup(r.get("origin")), tup(r.get("last_cell"))
    if origin is None or ((not r.get("target_pos")) and man(cell, origin) > MAXC):
        return cell, None
    return origin, last


print("=" * 78)
print("EVERY FIREFIGHTER DEATH vs last_cell SOLE-EXIT REFUSALS IN THE PRIOR "
      "%d STEPS" % WINDOW)
print("=" * 78)
tot_linked = 0
tot_deaths = 0
for fp in sorted(glob.glob(os.path.join(HERE, "_ir_p3_POST_*.json"))):
    tag = os.path.basename(fp)[len("_ir_p3_POST_"):-len(".json")]
    d = json.load(open(fp))
    surv = [r for r in (d.get("surv") or []) if r.get("pos") is not None]
    for dd in d.get("deaths") or []:
        tot_deaths += 1
        s, st, ff = dd["seed"], dd["step"], dd["ff"]
        hits = []
        for r in surv:
            if r.get("seed") != s or r.get("ff") != ff:
                continue
            if not (st - WINDOW <= r.get("step", -1) <= st):
                continue
            eo, el = eff(r)
            free = [tup(c) for c in (r.get("free_cells") or [])]
            if len(free) == 1 and el is not None and free[0] == el:
                hits.append((r, eo, el, free))
        if hits:
            tot_linked += 1
        print()
        print("DEATH  %-18s seed %-5s step %-4s %-11s at %s"
              % (tag, s, st, ff, dd.get("pos")))
        print("       last_cell sole-exit refusals in window: %d" % len(hits))
        for (r, eo, el, free) in hits:
            print("         step %-4s pos %-8s only-free/last %-8s cur_dist=%s "
                  "n_safe=%s better=%s idle=%s stalled=%s moved=%s leash_d=%d"
                  % (r["step"], "%d,%d" % tup(r["pos"]), "%d,%d" % el,
                     r.get("cur_dist"), r.get("n_safe"),
                     r.get("strictly_better_exists"), r.get("idle"),
                     r.get("stalled_pre"), r.get("moved"), man(free[0], eo)))
print()
print("-" * 78)
print("deaths with >=1 last_cell sole-exit refusal within %d steps: %d / %d"
      % (WINDOW, tot_linked, tot_deaths))
