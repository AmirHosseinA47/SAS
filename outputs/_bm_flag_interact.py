"""Base-mark round: PIXEL-level interaction of the flag with the existing marks,
over the recorded runs. Cell-level "touches" overstates it (a clamped FOV frame
runs along the map border through the same cells the flag stands in, but 2-3 px
away from its ink), so this works on pixel sets.

The flag is drawn ABOVE the sensing overlays and BELOW trails, assignment lines
and unit markers. So:  stroke px under flag ink = frame line the flag hides;
unit-marker px over flag ink = flag the unit hides.

usage: _bm_flag_interact.py outputs/_bm/trace_*.json
"""
from __future__ import annotations
import json, math, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from _bm_flag_geom import flag_pixels, banner_pixels, js_round

W = H = 50; CS = 11.2; FOVR = 8; VFR = 3


def snap(v):
    return js_round(v) + 0.5


def stroke_px(segs):
    """Pixels of a 3px casing along axis-aligned segments (centrelines on .5)."""
    out = set()
    for x0, y0, x1, y1 in segs:
        lox, hix = sorted((x0, x1)); loy, hiy = sorted((y0, y1))
        for px in range(int(math.floor(lox - 1.5)), int(math.ceil(hix + 1.5))):
            for py in range(int(math.floor(loy - 1.5)), int(math.ceil(hiy + 1.5))):
                if 0 <= px < 560 and 0 <= py < 560:
                    out.add((px, py))
    return out


def fov_segs(u):
    xlo, xhi = max(0, u["x"] - FOVR), min(W - 1, u["x"] + FOVR)
    ylo, yhi = max(0, u["y"] - FOVR), min(H - 1, u["y"] + FOVR)
    L, R = snap(xlo * CS), snap((xhi + 1) * CS)
    T, B = snap((H - 1 - yhi) * CS), snap((H - ylo) * CS)
    return [(L, T, R, T), (R, T, R, B), (R, B, L, B), (L, B, L, T)]


def diamond_segs(v, r):
    def ins(x, y):
        return 0 <= x < W and 0 <= y < H and abs(x - v["x"]) + abs(y - v["y"]) <= r
    segs = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            x, y = v["x"] + dx, v["y"] + dy
            if not ins(x, y):
                continue
            x0, x1, yt, yb = x * CS, (x + 1) * CS, (H - 1 - y) * CS, (H - y) * CS
            if not ins(x - 1, y): segs.append((snap(x0), snap(yt), snap(x0), snap(yb)))
            if not ins(x + 1, y): segs.append((snap(x1), snap(yt), snap(x1), snap(yb)))
            if not ins(x, y + 1): segs.append((snap(x0), snap(yt), snap(x1), snap(yt)))
            if not ins(x, y - 1): segs.append((snap(x0), snap(yb), snap(x1), snap(yb)))
    return segs


def marker_px(x, y, inset):
    x0, y0 = (x + inset) * CS, (H - 1 - y + inset) * CS
    side = CS * (1 - 2 * inset)
    return {(px, py) for px in range(int(math.floor(x0)), int(math.ceil(x0 + side)))
            for py in range(int(math.floor(y0)), int(math.ceil(y0 + side)))}


def disc_px(x, y):
    cx, cy, rad = (x + 0.5) * CS, (H - 1 - y + 0.5) * CS, 0.5 * CS
    return {(a, b) for a in range(int(cx - rad) - 1, int(cx + rad) + 2)
            for b in range(int(cy - rad) - 1, int(cy + rad) + 2)
            if (a + 0.5 - cx) ** 2 + (b + 0.5 - cy) ** 2 <= rad * rad}


def main() -> int:
    geom = banner_pixels if "--banner" in sys.argv else flag_pixels
    sys.argv = [a for a in sys.argv if a != "--banner"]
    pooled = {"steps": 0, "fov_hide": 0, "dia_hide": 0, "unit_cover": 0,
              "fov_px": [], "unit_px": []}
    for path in sys.argv[1:]:
        t = json.load(open(path)); rows = t["rows"]
        flags = [set(geom(d, W, H, CS)) for d in t["depots"]]
        ink = set().union(*flags)
        n = len(rows); fh = dh = uc = 0; fpx = []; upx = []
        for r in rows:
            f = stroke_px([s for u in r["uavs"] for s in fov_segs(u)]) & ink
            d = stroke_px([s for v in r["victims"] if v["flee"] for s in diamond_segs(v, VFR)]) & ink
            m = set()
            for u in r["uavs"]:
                m |= marker_px(u["x"], u["y"], 0.1)
            for ff in r["ffs"]:
                if ff["pos"] is not None:
                    m |= marker_px(ff["pos"][0], ff["pos"][1], 0.15)
            for v in r["victims"]:
                m |= disc_px(v["x"], v["y"])      # drawMap draws an arc of radius 0.5*cs, not a square
            m &= ink
            fh += bool(f); dh += bool(d); uc += bool(m)
            if f: fpx.append(len(f))
            if m: upx.append(len(m))
        print("%s/%d: flag hides FOV stroke px on %d/%d steps (%.1f%%), median %s px of the mark's ink; "
              "hides victim-diamond px on %d (%.1f%%); a unit marker covers flag ink on %d (%.1f%%), median %s px"
              % (t["wind"], t["seed"], fh, n, 100.0 * fh / n,
                 sorted(fpx)[len(fpx) // 2] if fpx else 0, dh, 100.0 * dh / n, uc, 100.0 * uc / n,
                 sorted(upx)[len(upx) // 2] if upx else 0))
        pooled["steps"] += n; pooled["fov_hide"] += fh; pooled["dia_hide"] += dh
        pooled["unit_cover"] += uc; pooled["fov_px"] += fpx; pooled["unit_px"] += upx
    n = pooled["steps"]
    print("POOLED %d steps: flag hides some FOV stroke %.1f%% (max %d px on a step, of a frame perimeter of ~%d px); "
          "hides some victim-diamond stroke %.1f%%; unit marker over flag ink %.1f%% (max %d px of the two marks' ink)"
          % (n, 100.0 * pooled["fov_hide"] / n, max(pooled["fov_px"] or [0]), int(4 * 17 * CS * 3),
             100.0 * pooled["dia_hide"] / n, 100.0 * pooled["unit_cover"] / n, max(pooled["unit_px"] or [0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
