"""Per-step fate of unit mass on a fire-front cell, an interior burning cell, and a cell next to the fire (predict only)."""
import sys
sys.path.insert(0, r"E:\Projects\SAS")
import numpy as np
from src_extension.knowledge.victim_search_belief import VictimSearchBelief, MotionParams
H = W = 50
fire = {(x, y) for x in range(50) for y in range(20, 31)}       # a burning band y = 20..30
for mode in ("diffusion", "flee"):
    for name, cell in (("front y=20", (25, 20)), ("interior y=25", (25, 25)), ("outside y=19", (25, 19)),
                       ("outside y=14", (25, 14)), ("outside y=10", (25, 10))):
        b = VictimSearchBelief.with_uniform_prior(H, W, 1, excluded=())
        b.p[:, :] = 0.0; b.p[cell] = 1.0
        b.predict(fire, MotionParams(mode=mode))
        stay = float(b.p[cell]); onfire = sum(float(b.p[c]) for c in fire)
        print("%-9s %-14s stays %.4f  mass on burning cells after predict %.4f" % (mode, name, stay, onfire))
# trapped interior mass over a burn of ~25 steps
for pbo in (0.0, 0.1, 0.5):
    print("interior mass left after 25 steps of burn-over %.1f: %.4f" % (pbo, (1 - pbo) ** 25))
