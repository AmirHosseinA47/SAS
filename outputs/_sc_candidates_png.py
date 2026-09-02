"""Rasterise the candidate comparison so it can be inspected as an image.

Reuses the cached ground state written by _sc_candidates.py instead of re-running
the model, so this is pure drawing.
"""
from __future__ import annotations
import json, os, sys
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
CS = 7
W = H = 50
CANDIDATES = [
    ("#2b2b2b", "CURRENT (merged)"),
    ("#895e00", "ember bronze (winner)"),
    ("#66301c", "ember char"),
    ("#9a6960", "terracotta"),
    ("#4d3020", "smouldering brown"),
    ("#7a3b12", "mid rust"),
]

with open(os.path.join(BASE, "_sc_ground.json"), encoding="utf-8") as fh:
    base = json.load(fh)

PW, PH = W * CS + 16, H * CS + 40
img = Image.new("RGB", (PW * 3, PH * 2 + 18), "#141414")
d = ImageDraw.Draw(img)
for i, (hexc, label) in enumerate(CANDIDATES):
    ox, oy = (i % 3) * PW, (i // 3) * PH
    d.text((ox + 3, oy + 4), "%s  %s" % (hexc, label), fill="#eeeeee")
    for x, y, g, col in base:
        c = hexc if g == "scorched" else col
        x0, y0 = ox + x * CS, oy + 20 + (H - 1 - y) * CS
        d.rectangle([x0, y0, x0 + CS - 1, y0 + CS - 1], fill=c)
    for k in range(W + 1):
        d.line([(ox + k * CS, oy + 20), (ox + k * CS, oy + 20 + H * CS)], fill="#0d0d0d")
        d.line([(ox, oy + 20 + k * CS), (ox + W * CS, oy + 20 + k * CS)], fill="#0d0d0d")
d.text((4, PH * 2 + 4), "D/east/half seed 101 step 60 - scorched 155 / burnt 97 / "
                        "burning 204 / virgin 2044; burnt stays #2b2b2b in every panel",
       fill="#9a9a9a")
out = os.path.join(BASE, "_sc_candidates.png")
img.save(out)
print("WROTE", out, img.size)
