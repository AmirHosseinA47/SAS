# Pure geometry check of the pickup exit_target rule (agents.py:1784-1793).
# No model import. Replicates mesa 1.2.1 _Grid.out_of_bounds for
# MultiGrid(HEIGHT, WIDTH, False): grid.width = HEIGHT (x), grid.height = WIDTH (y).
import itertools


def out_of_bounds(pos, H, W):
    x, y = pos
    return x < 0 or x >= H or y < 0 or y >= W


def exit_target(pos, H, W):
    x, y = pos
    dists = {
        (0, y): x,
        (H - 1, y): H - 1 - x,
        (x, 0): y,
        (x, W - 1): W - 1 - y,
    }
    return min(dists, key=dists.get), dists


def check(H, W):
    cells = [(x, y) for x in range(H) for y in range(W)]
    boundary_oob = {
        c for c in cells
        if any(out_of_bounds((c[0] + dx, c[1] + dy), H, W)
               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    }
    boundary_set = {c for c in cells if c[0] in (0, H - 1) or c[1] in (0, W - 1)}
    assert boundary_oob == boundary_set, (H, W)
    bad_nearest = 0
    bad_value = 0
    bad_member = 0
    ties = 0
    tie_order_ok = 0
    collisions = 0
    for c in cells:
        et, dists = exit_target(c, H, W)
        if et not in boundary_set:
            bad_member += 1
        md = abs(c[0] - et[0]) + abs(c[1] - et[1])
        true_min = min(abs(c[0] - b[0]) + abs(c[1] - b[1]) for b in boundary_set)
        if md != true_min:
            bad_nearest += 1
        for k, v in dists.items():
            if abs(c[0] - k[0]) + abs(c[1] - k[1]) != v:
                bad_value += 1
        if len(dists) < 4:
            collisions += 1
        vals = list(dists.values())
        m = min(vals)
        if vals.count(m) > 1:
            ties += 1
            # first key in insertion order with the minimal value
            first = next(k for k, v in dists.items() if v == m)
            if first == et:
                tie_order_ok += 1
    return dict(H=H, W=W, cells=len(cells), boundary=len(boundary_set),
                bad_member=bad_member, bad_nearest=bad_nearest,
                bad_value=bad_value, collisions=collisions, ties=ties,
                tie_first_in_insertion_order=tie_order_ok)


for H, W in ((50, 50), (40, 60), (60, 40), (1, 5), (2, 2), (3, 7)):
    print(check(H, W))

# Tier-2 emptiness: a 4-neighbour step always changes manhattan distance by +-1.
cnt = 0
for cx, cy, tx, ty in itertools.product(range(-3, 4), repeat=4):
    d0 = abs(cx - tx) + abs(cy - ty)
    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d1 = abs(cx + ox - tx) + abs(cy + oy - ty)
        assert abs(d1 - d0) == 1
        cnt += 1
print("tier2 check: all", cnt, "neighbour steps change distance by exactly 1")

# Preferred cell is always improving when target != pos.
bad = 0
for cx, cy, tx, ty in itertools.product(range(-3, 4), repeat=4):
    if (cx, cy) == (tx, ty):
        continue
    dx, dy = tx - cx, ty - cy
    if abs(dx) >= abs(dy):
        p = (cx + (1 if dx > 0 else -1 if dx < 0 else 0), cy)
    else:
        p = (cx, cy + (1 if dy > 0 else -1 if dy < 0 else 0))
    if abs(p[0] - tx) + abs(p[1] - ty) >= abs(cx - tx) + abs(cy - ty):
        bad += 1
print("preferred-not-improving cases:", bad)
