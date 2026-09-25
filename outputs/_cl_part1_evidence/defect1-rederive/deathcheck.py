# Read-only: every firefighter death in the recorded runs, classified by whether
# the unit was carrying (exiting) at the end of the previous step, and whether it
# moved and whether every in-grid neighbour of its death cell was burning in the
# post-step observation (burn_intervals are [start, end) over post-step reads).
# Lists outputs/ NON-recursively; never enters a subdirectory.
import json
import os

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
names = sorted(
    n for n in os.listdir(OUT)
    if n != QUAR and n.startswith("_ffr_") and n.endswith(".json")
    and not n.endswith(".xstrace.json")
)
H = W = 50


def burning_at(intervals, key, s):
    for st, en in intervals.get(key, ()):
        if st <= s and (en is None or s < en):
            return True
    return False


stats = {
    "files": 0,
    "deaths": 0,
    "deaths_prev_exiting": 0,
    "prev_exiting_moved": 0,
    "prev_exiting_own_not_burning": 0,
    "prev_exiting_all_nbrs_burning": 0,
    "prev_exiting_some_nbr_not_burning": 0,
    "prev_exiting_exit_after_step": 0,
    "deaths_same_step_as_completion": 0,
    "deaths_prev_not_exiting": 0,
}
examples = []
distinct = set()
for n in names:
    try:
        with open(os.path.join(OUT, n), encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        continue
    stats["files"] += 1
    fs = d.get("ff_steps") or []
    bi = d.get("burn_intervals") or {}
    comps = {(c.get("ff"), int(c.get("step", -1))) for c in (d.get("completions") or [])}
    for i in range(1, len(fs)):
        prev = {r[0]: r for r in fs[i - 1]}
        for r in fs[i]:
            ff, pos, status, assigned, exiting, dead = r[:6]
            p = prev.get(ff)
            if p is None or not dead or p[5]:
                continue
            s = i + 1  # ff_steps[i] is the post-step read of step i+1
            stats["deaths"] += 1
            if (ff, s) in comps:
                stats["deaths_same_step_as_completion"] += 1
            if not p[4]:
                stats["deaths_prev_not_exiting"] += 1
                continue
            stats["deaths_prev_exiting"] += 1
            if exiting:
                stats["prev_exiting_exit_after_step"] += 1
            ppos = tuple(p[1]) if p[1] is not None else None
            cpos = tuple(pos) if pos is not None else None
            if ppos != cpos:
                stats["prev_exiting_moved"] += 1
            cell = cpos or ppos
            key = "%d,%d" % cell
            if not burning_at(bi, key, s):
                stats["prev_exiting_own_not_burning"] += 1
            nbrs = [
                (cell[0] + dx, cell[1] + dy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= cell[0] + dx < H and 0 <= cell[1] + dy < W
            ]
            unburnt = [c for c in nbrs if not burning_at(bi, "%d,%d" % c, s)]
            if unburnt:
                stats["prev_exiting_some_nbr_not_burning"] += 1
                if len(examples) < 8:
                    examples.append((n, ff, s, cell, unburnt, status))
            else:
                stats["prev_exiting_all_nbrs_burning"] += 1
            distinct.add((d.get("wind"), d.get("scenario"), d.get("seed"), ff, s, cell))
    del d

for k, v in stats.items():
    print(k, v)
print("distinct (wind, scenario, seed, ff, step, cell) carrier deaths:", len(distinct))
for e in examples:
    print("EXAMPLE", e)
