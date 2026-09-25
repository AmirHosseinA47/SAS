"""dcC/dfC south/half/606: during the 143-171 carry, is each co-marked victim's cell
reachable (burning-only BFS, the model's rule) from the carrier's cell? Named files only."""
import json, os
from collections import deque

OUT = r"E:\Projects\SAS\outputs"
for f in ("_ffr_dcC_south_half_606.json", "_ffr_dfC_south_half_606.json"):
    d = json.load(open(os.path.join(OUT, f)))
    bi = d["burn_intervals"]
    W = H = 50

    def burning_at(s):
        out = set()
        for k, ivs in bi.items():
            for a, b in ivs:
                if a <= s and (b is None or s < b):
                    x, y = map(int, k.split(","))
                    out.add((x, y))
                    break
        return out

    print(f, "exit_starts", [e for e in d["exit_starts"] if 130 <= e["step"] <= 172],
          "completions", [c for c in d["completions"] if 130 <= c["step"] <= 180])
    hits = {}
    for s in range(143, 172):
        ffr = [r for r in d["ff_steps"][s - 1] if r[4] and not r[5]]
        if not ffr:
            continue
        start = tuple(ffr[0][1])
        burn = burning_at(s)
        if start in burn:
            continue
        seen = {start}
        q = deque([start])
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if n in seen or n in burn or not (0 <= n[0] < H and 0 <= n[1] < W):
                    continue
                seen.add(n)
                q.append(n)
        for r in d["victim_steps"][s - 1]:
            if r[0] in ("victim_1", "victim_2") and r[1] is not None:
                hits.setdefault(r[0], []).append((s, tuple(r[1]) in seen))
    for v, lst in hits.items():
        print("  ", v, "reachable on", sum(1 for _, ok in lst if ok), "of", len(lst), "carry steps; last", lst[-3:])
