"""Base-mark round: the flag's geometry, recomputed in Python INDEPENDENTLY of the JS.

Two consumers:
  * Part 1 - pixel-level interaction rates against recorded runs (how much FOV /
    diamond stroke the flag hides, how often a unit marker covers the flag).
  * Part 3 - the pixel audit's two-way containment: the set of pixels the JS
    is supposed to paint, by tone, derived here from the design's numbers and not
    from the browser.

Pixel-art on integer coordinates: every pixel is exactly one tone, so the
prediction is an exact set, not a tolerance band.
"""
from __future__ import annotations

CASING, KEYLINE = (0, 0, 0), (255, 255, 255)


def _q(v: float, s: float) -> int:
    import math
    return max(1, int(math.floor(v * s + 0.5)))   # Math.round, not banker's rounding


def js_round(v: float) -> int:
    """Math.round: half rounds UP (toward +inf), unlike Python's banker's round."""
    import math
    return int(math.floor(v + 0.5))


def flag_pixels(d: dict, W: int, H: int, cs: float, field=(0x77, 0x00, 0x99), K: float = 1.0) -> dict:
    """{(px, py): (r, g, b)} for one depot descriptor {x, y, size}."""
    bw = d["size"] * cs
    s = K * min(1.5, max(0.6, bw / 56.0))
    q = lambda v: _q(v, s)
    bx = js_round(d["x"] * cs)
    by = js_round((H - d["y"] - d["size"]) * cs)
    bR = js_round((d["x"] + d["size"]) * cs)
    east = d["x"] > 0 and d["x"] + d["size"] >= W
    pw = q(3)
    poleL = (bR - q(4) - pw) if east else (bx + q(4))
    top = by + q(3)
    ph = q(30)
    rows, lmin, lmax = q(11), q(2), q(17)
    out: dict = {}

    def rect(x, y, w, h, col):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                out[(xx, yy)] = col

    def pen(grow, col):
        for j in range(rows):
            ln = lmax if rows < 2 else js_round(lmin + (lmax - lmin) * (1 - abs(2 * j - (rows - 1)) / (rows - 1)))
            y = top + q(2) + j
            if east:
                rect(poleL - ln - grow, y - grow, ln + grow, 1 + 2 * grow, col)
            else:
                rect(poleL + pw, y - grow, ln + grow, 1 + 2 * grow, col)

    pen(2, CASING)
    rect(poleL, top, pw, ph, CASING)
    rect(poleL + 1, top + 1, max(1, pw - 2), ph - 2, KEYLINE)
    pen(1, KEYLINE)
    pen(0, field)
    cw, ch = int(W * cs), int(H * cs)
    return {p: c for p, c in out.items() if 0 <= p[0] < cw and 0 <= p[1] < ch}


def banner_pixels(d: dict, W: int, H: int, cs: float, field=(0x77, 0x00, 0x99)) -> dict:
    """The banner flag. {(px, py): tone}; tone is None inside the cloth INTERIOR,
    where a pixel is either the field colour or a clipped glyph blend (field..white)
    - font-dependent, so only its containment is predicted, not its value."""
    bw = d["size"] * cs
    s = min(1.5, max(0.6, bw / 56.0))
    q = lambda v: _q(v, s)
    bx = js_round(d["x"] * cs)
    by = js_round((H - d["y"] - d["size"]) * cs)
    bR = js_round((d["x"] + d["size"]) * cs)
    east = d["x"] > 0 and d["x"] + d["size"] >= W
    pw = q(3)
    poleL = (bR - q(4) - pw) if east else (bx + q(4))
    top = by + q(3)
    ph = q(30)
    cw, ch = q(28), q(15)
    cx = (poleL - cw + 1) if east else (poleL + pw - 1)
    out: dict = {}

    def rect(x, y, w, h, col):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                out[(xx, yy)] = col

    rect(poleL, top, pw, ph, CASING); rect(cx, top, cw, ch, CASING)
    rect(poleL + 1, top + 1, max(1, pw - 2), ph - 2, KEYLINE); rect(cx + 1, top + 1, cw - 2, ch - 2, KEYLINE)
    rect(cx + 2, top + 2, cw - 4, ch - 4, None)
    cwid, chei = int(W * cs), int(H * cs)
    return {p: c for p, c in out.items() if 0 <= p[0] < cwid and 0 <= p[1] < chei}


if __name__ == "__main__":
    from collections import Counter
    for d in ({"x": 0, "y": 45, "size": 5}, {"x": 45, "y": 0, "size": 5}):
        px = flag_pixels(d, 50, 50, 11.2)
        xs = [p[0] for p in px]; ys = [p[1] for p in px]
        tones = Counter(px.values())
        print("depot", d, "ink px", len(px), "bbox x %d..%d y %d..%d" % (min(xs), max(xs), min(ys), max(ys)),
              "tones", {"#%02x%02x%02x" % k: v for k, v in tones.items()})
