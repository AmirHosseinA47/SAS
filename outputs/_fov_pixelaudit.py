"""FOV-frame round: prove the rendered-pixel delta is EXACTLY the overlay.

The positive control has to do more than "the digest moved" - it has to account
for what moved. This recomputes, in Python and independently of the browser, the
geometry the JS is supposed to have drawn, expands it into the set of pixels a
3px-wide stroke can touch, and then checks two-way containment against the
measured pre/post pixel diff:

  A. every CHANGED pixel lies on a predicted stroke   -> no stray repaint
  B. every predicted stroke has changed pixels        -> nothing silently missing

A is the falsifiable half: one changed pixel off-geometry means the patch moved
something it should not have.

usage: _fov_pixelaudit.py <frame.json> <prefix>   (after _fov_render.py)
"""
from __future__ import annotations
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
TOL = 2.0          # 3px casing -> +/-1.5, plus antialias spill


def snap(v: float) -> float:
    return round(v) + 0.5


def frame_segments(blob):
    """The stroke centrelines the JS should draw, in canvas pixels."""
    fr = blob["frame"]
    W, H, cs = blob["width"], blob["height"], blob["cs"]
    R, VFR = blob["fov_radius"], blob["victim_flee_radius"]
    segs = []
    for u in fr.get("uavs", []):
        xlo, xhi = max(0, u["x"] - R), min(W - 1, u["x"] + R)
        ylo, yhi = max(0, u["y"] - R), min(H - 1, u["y"] + R)
        if xhi < xlo or yhi < ylo:
            continue
        L, Rt = snap(xlo * cs), snap((xhi + 1) * cs)
        T, B = snap((H - 1 - yhi) * cs), snap((H - ylo) * cs)
        segs += [(L, T, Rt, T), (Rt, T, Rt, B), (Rt, B, L, B), (L, B, L, T)]
    if VFR > 0:
        for v in fr.get("victims", []):
            if not v.get("flee"):
                continue
            def inset(x, y, v=v):
                return (0 <= x < W and 0 <= y < H
                        and abs(x - v["x"]) + abs(y - v["y"]) <= VFR)
            for dy in range(-VFR, VFR + 1):
                for dx in range(-VFR, VFR + 1):
                    x, y = v["x"] + dx, v["y"] + dy
                    if not inset(x, y):
                        continue
                    x0, x1 = x * cs, (x + 1) * cs
                    yt, yb = (H - 1 - y) * cs, (H - y) * cs
                    if not inset(x - 1, y): segs.append((snap(x0), snap(yt), snap(x0), snap(yb)))
                    if not inset(x + 1, y): segs.append((snap(x1), snap(yt), snap(x1), snap(yb)))
                    if not inset(x, y + 1): segs.append((snap(x0), snap(yt), snap(x1), snap(yt)))
                    if not inset(x, y - 1): segs.append((snap(x0), snap(yb), snap(x1), snap(yb)))
    return segs


def ink_mask(segs, w, h, tol=TOL):
    """Pixels within tol of any (axis-aligned) segment centreline."""
    mask = set()
    for (x0, y0, x1, y1) in segs:
        lox, hix = sorted((x0, x1)); loy, hiy = sorted((y0, y1))
        for px in range(max(0, int(lox - tol)), min(w, int(hix + tol) + 1)):
            for py in range(max(0, int(loy - tol)), min(h, int(hiy + tol) + 1)):
                cx = min(max(px + 0.5, lox), hix)
                cy = min(max(py + 0.5, loy), hiy)
                if abs(px + 0.5 - cx) <= tol and abs(py + 0.5 - cy) <= tol:
                    mask.add((px, py))
    return mask


def main() -> int:
    blob = json.load(open(sys.argv[1])); prefix = sys.argv[2]
    from PIL import Image
    pre = Image.open("%s_pre.png" % prefix).convert("RGB")
    post = Image.open("%s_post.png" % prefix).convert("RGB")
    w, h = post.size
    a, b = list(pre.getdata()), list(post.getdata())
    changed = {(i % w, i // w) for i, (x, y) in enumerate(zip(a, b)) if x != y}

    segs = frame_segments(blob)
    mask = ink_mask(segs, w, h)

    stray = changed - mask
    covered = changed & mask
    # B: per-segment, did anything change near it?
    silent = []
    for s in segs:
        m = ink_mask([s], w, h)
        if not (m & changed):
            silent.append(s)

    print("canvas            %dx%d = %d px" % (w, h, w * h))
    print("segments drawn    %d  (%d UAV frame sides + %d diamond edges)"
          % (len(segs), 4 * len(blob["frame"].get("uavs", [])),
             len(segs) - 4 * len(blob["frame"].get("uavs", []))))
    print("predicted ink     %d px (within %.1f px of a centreline)" % (len(mask), TOL))
    print("changed           %d px" % len(changed))
    print("A changed on-geometry   %d / %d" % (len(covered), len(changed)))
    print("A STRAY (off-geometry)  %d          <-- must be 0" % len(stray))
    print("B segments with no change %d / %d   <-- must be 0" % (len(silent), len(segs)))
    if stray:
        print("  sample stray:", sorted(stray)[:12])
    if silent:
        print("  sample silent:", silent[:6])
    ok = (not stray) and (not silent)
    print("PIXEL AUDIT:", "PASS" if ok else "FAIL")
    json.dump({"canvas": [w, h], "segments": len(segs), "predicted_ink": len(mask),
               "changed": len(changed), "on_geometry": len(covered),
               "stray": len(stray), "silent_segments": len(silent), "pass": ok},
              open("%s_pixelaudit.json" % prefix, "w"), indent=2, sort_keys=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
