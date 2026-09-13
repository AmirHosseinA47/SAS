"""FOV-frame round: side-by-side before/after of the real dashboard render.

Deliberately NOT built on _sc_beforeafter_png.py. That script paints per-cell
from a ground-state dump of Fire agents only, has no concept of an overlay, and
would render two IDENTICAL panels for this change. Both panels here come from
_fov_render.py, i.e. from the shipped drawMap executed in headless Chromium, so
what is compared is the real renderer at both commits.

usage: _fov_beforeafter_png.py <prefix> <out.png>   (after _fov_render.py)
"""
from __future__ import annotations
import os, sys
from PIL import Image, ImageDraw

PAD, GAP, TOP = 14, 18, 30
BG, FG, SUB = (24, 24, 24), (238, 238, 238), (150, 150, 150)


def main() -> int:
    prefix, out = sys.argv[1], sys.argv[2]
    pre = Image.open("%s_pre.png" % prefix).convert("RGB")
    post = Image.open("%s_post.png" % prefix).convert("RGB")
    w, h = pre.size
    canvas = Image.new("RGB", (PAD * 2 + w * 2 + GAP, TOP + h + PAD), BG)
    canvas.paste(pre, (PAD, TOP))
    canvas.paste(post, (PAD + w + GAP, TOP))
    d = ImageDraw.Draw(canvas)
    d.text((PAD, 8), "BEFORE  7f951cb - no observation overlay", fill=SUB)
    d.text((PAD + w + GAP, 8),
           "AFTER  17x17 UAV frame (white core / black casing) + manhattan victim flee diamond",
           fill=FG)
    for x in (PAD, PAD + w + GAP):
        d.rectangle([x - 1, TOP - 1, x + w, TOP + h], outline=(70, 70, 70))
    canvas.save(out)
    print("wrote %s  (%dx%d)" % (out, canvas.size[0], canvas.size[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
