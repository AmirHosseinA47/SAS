"""Before/after rasterisation for the record. Reuses the cached step-60 ground
state, so this is pure drawing - no model run, no RNG."""
from __future__ import annotations
import json, os
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
CS, W, H = 11, 50, 50
base = json.load(open(os.path.join(BASE, "_sc_ground.json"), encoding="utf-8"))

PANELS = [("#2b2b2b", "BEFORE  scorched == burnt == #2b2b2b"),
          ("#895e00", "AFTER   scorched #895e00 / burnt #2b2b2b")]
PW, PH = W * CS + 20, H * CS + 46
img = Image.new("RGB", (PW * 2 + 250, PH + 26), "#141414")
d = ImageDraw.Draw(img)
for i, (hexc, label) in enumerate(PANELS):
    ox = i * PW
    d.text((ox + 4, 6), label, fill="#eeeeee")
    for x, y, g, col in base:
        c = hexc if g == "scorched" else col
        x0, y0 = ox + x * CS, 22 + (H - 1 - y) * CS
        d.rectangle([x0, y0, x0 + CS - 1, y0 + CS - 1], fill=c)
    for k in range(W + 1):
        d.line([(ox + k * CS, 22), (ox + k * CS, 22 + H * CS)], fill="#0d0d0d")
        d.line([(ox, 22 + k * CS), (ox + W * CS, 22 + k * CS)], fill="#0d0d0d")

lx = PW * 2 + 10
d.text((lx, 6), "step 60, D/east/half seed 101", fill="#eeeeee")
rows = [("#895e00", "scorched  n=155   re-ignites 96.6%"),
        ("#2b2b2b", "burnt     n=97    absorbing, safe"),
        ("#fe2301", "fire      n=204"),
        ("#175808", "vegetation n=2044")]
for k, (c, t) in enumerate(rows):
    d.rectangle([lx, 34 + k * 26, lx + 18, 52 + k * 26], fill=c, outline="#888888")
    d.text((lx + 26, 39 + k * 26), t, fill="#dddddd")
d.text((lx, 34 + len(rows) * 26 + 14), "at actual cell size:", fill="#aaaaaa")
for k, (c, t) in enumerate((("#2b2b2b", "burnt"), ("#895e00", "scorched"))):
    yy = 34 + len(rows) * 26 + 32 + k * (CS + 18)
    for j in range(8):
        d.rectangle([lx + j * CS, yy, lx + j * CS + CS - 1, yy + CS - 1], fill=c)
    d.text((lx + 8 * CS + 8, yy), t, fill="#cccccc")
out = os.path.join(BASE, "_sc_before_after.png")
img.save(out)
print("WROTE", out, img.size)
