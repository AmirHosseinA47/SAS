# Read-only cross-check of the pickup exit_target rule against recorded runs.
# Lists outputs/ NON-recursively (os.listdir) and never enters any subdirectory.
import json
import os
import sys

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"

names = sorted(
    n for n in os.listdir(OUT)
    if n != QUAR and n.startswith("_ffr_") and n.endswith(".json")
    and not n.endswith(".xstrace.json")
)


def rule(pos, H, W):
    x, y = pos
    dists = {(0, y): x, (H - 1, y): H - 1 - x, (x, 0): y, (x, W - 1): W - 1 - y}
    return min(dists, key=dists.get)


files = 0
files_with_comp = 0
comps = 0
pos_ne_exit = 0
no_start = 0
rule_mismatch = 0
not_nearest = 0
dims_seen = {}
examples = []
for n in names:
    path = os.path.join(OUT, n)
    if not os.path.isfile(path):
        continue
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print("skip", n, type(exc).__name__)
        continue
    files += 1
    H = W = 50
    dim = d.get("dim")
    if isinstance(dim, dict):
        H = int(dim.get("HEIGHT", dim.get("height", H)) or H)
        W = int(dim.get("WIDTH", dim.get("width", W)) or W)
    dims_seen[(H, W)] = dims_seen.get((H, W), 0) + 1
    starts = d.get("exit_starts") or []
    completions = d.get("completions") or []
    if completions:
        files_with_comp += 1
    for c in completions:
        comps += 1
        et = tuple(c.get("exit_target") or ())
        pos = tuple(c.get("pos") or ())
        if pos != et:
            pos_ne_exit += 1
            if len(examples) < 5:
                examples.append(("pos!=exit", n, c))
        cand = [
            s for s in starts
            if s.get("ff") == c.get("ff") and s.get("victim") == c.get("victim")
            and int(s.get("step", -1)) < int(c.get("step", 0))
        ]
        if not cand:
            no_start += 1
            continue
        s = max(cand, key=lambda r: int(r.get("step", -1)))
        p = tuple(s.get("ff_pos"))
        if rule(p, H, W) != et:
            rule_mismatch += 1
            if len(examples) < 10:
                examples.append(("rule", n, s, c))
        md = abs(p[0] - et[0]) + abs(p[1] - et[1])
        if md != min(p[0], H - 1 - p[0], p[1], W - 1 - p[1]):
            not_nearest += 1
    del d

print("files read", files, "with completions", files_with_comp)
print("dims", dims_seen)
print("completions", comps)
print("completion pos != exit_target", pos_ne_exit)
print("completion without a matching earlier exit_start", no_start)
print("exit_target != rule(pickup cell)", rule_mismatch)
print("manhattan(pickup, exit_target) != nearest-boundary distance", not_nearest)
for e in examples:
    print(e)
sys.stdout.flush()
