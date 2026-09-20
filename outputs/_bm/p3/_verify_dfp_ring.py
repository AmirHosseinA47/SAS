"""Cells outside a 5x5 corner block whose ignition probability the block can influence.
Chebyshev-3 (mesa Moore radius 3) versus what distance_rate actually lets through (Euclidean <= 3)."""
import math
W = H = 50
for name, (ox, oy) in {"SE": (45, 0), "NW": (0, 45)}.items():
    blk = {(ox + i, oy + j) for i in range(5) for j in range(5)}
    cheb = set(); eucl = set()
    for x in range(W):
        for y in range(H):
            if (x, y) in blk:
                continue
            for (bx, by) in blk:
                dx, dy = abs(x - bx), abs(y - by)
                if max(dx, dy) <= 3:
                    cheb.add((x, y))
                    if math.hypot(dx, dy) <= 3:
                        eucl.add((x, y))
    print(name, "Chebyshev<=3:", len(cheb), " Euclidean<=3 (distance_rate nonzero):", len(eucl),
          " cheb-only (zero influence):", sorted(cheb - eucl))
