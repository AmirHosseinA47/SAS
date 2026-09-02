"""Defect #9-A2: side-by-side candidate comparison on the REAL map.

Runs the canonical combo once to step 60, then paints the same ground grid N
times, once per candidate scorched colour, so the choice can be judged on the
actual spatial distribution of scorched vs burnt rather than on swatches.
Panel 0 is the current merged rendering (the "before").
Read-only: reads agent attributes, calls nothing that mutates or draws RNG.
"""
from __future__ import annotations
import contextlib, io as _io, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agents as am, common_fixed_variables as cfv, wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import _cell_color

BASE = os.path.dirname(os.path.abspath(__file__))
CS = 7
W = H = cfv.WIDTH
STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 60

CANDIDATES = [
    ("#2b2b2b", "CURRENT (merged)"),
    ("#895e00", "ember bronze  - unanimous judge winner"),
    ("#66301c", "ember char    - semantics lens"),
    ("#9a6960", "terracotta    - accessibility lens"),
    ("#4d3020", "smould. brown - minimalist lens"),
    ("#7a3b12", "mid rust      - collision runner-up"),
]


def ground(a):
    if getattr(a, "burning", False):
        return "burning"
    if getattr(a, "burnt", False):
        return "burnt"
    if getattr(a, "has_burned", False):
        return "scorched"
    return "virgin"


rng = random.Random(101)
cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
apply_scenario_config(cfv, wf, NUM_AGENTS=4, NUM_VICTIMS=4, NUM_FIREFIGHTERS=2,
                      WIND_DIRECTION="east", BATCH_SIZE=300,
                      FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
                      NUM_FIRE_TRACKERS=2, NUM_VICTIM_SEARCHERS=2)
with contextlib.redirect_stdout(_io.StringIO()):
    model = WildFireModel(); model.debug_log = False
    for _ in range(STEPS):
        model.step()

fires = [a for a in model.schedule.agents if type(a).__name__ == "Fire"]
base = [(int(a.pos[0]), int(a.pos[1]), ground(a), _cell_color(a)) for a in fires]
counts = {}
for _, _, g, _c in base:
    counts[g] = counts.get(g, 0) + 1

PW = W * CS + 16
panels = []
for i, (hexc, label) in enumerate(CANDIDATES):
    ox = (i % 3) * PW
    oy = (i // 3) * (H * CS + 46)
    rects = []
    for x, y, g, col in base:
        c = hexc if g == "scorched" else col
        rects.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
                     % (ox + x * CS, oy + 22 + (H - 1 - y) * CS, CS, CS, c))
    grid = ['<g stroke="rgba(0,0,0,0.18)" stroke-width="0.5">']
    for k in range(W + 1):
        grid.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                    % (ox + k * CS + .5, oy + 22, ox + k * CS + .5, oy + 22 + H * CS))
    for k in range(H + 1):
        grid.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                    % (ox, oy + 22 + k * CS + .5, ox + W * CS, oy + 22 + k * CS + .5))
    grid.append('</g>')
    panels.append(
        '<text x="%d" y="%d" font-family="monospace" font-size="12" fill="#eee">%s  %s</text>'
        % (ox + 2, oy + 15, hexc, label)
        + "".join(rects) + "".join(grid))

TW = PW * 3
TH = (H * CS + 46) * 2 + 30
svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
       % (TW, TH, TW, TH)
       + '<rect width="100%%" height="100%%" fill="#141414"/>'
       + "".join(panels)
       + '<text x="4" y="%d" font-family="monospace" font-size="12" fill="#9a9a9a">'
         'D/east/half seed 101, step %d - virgin %d / burning %d / scorched %d / burnt %d'
         '  (burnt stays #2b2b2b in every panel)</text>'
       % (TH - 8, STEPS, counts.get("virgin", 0), counts.get("burning", 0),
          counts.get("scorched", 0), counts.get("burnt", 0))
       + '</svg>')
out = os.path.join(BASE, "_sc_candidates.svg")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(svg)
print("WROTE", out)
print("counts:", counts)
