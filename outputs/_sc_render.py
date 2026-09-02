"""Defect #9-A2: before/after visual sample.

Runs ONE canonical combo (D/east/half, seed 101) to a chosen step, then paints
the 50x50 ground grid to an SVG using the LIVE serve_dashboard._cell_color, so
the same script produces the "before" image at HEAD and the "after" image once
the patch is applied. Cells whose ground state is scorched are also listed in a
side panel count, and an inset strip shows the burnt vs scorched swatches at the
actual on-screen cell size.

Read-only with respect to the model: it calls _cell_color, nothing else.

usage: _sc_render.py <tag> [steps]
"""
from __future__ import annotations
import contextlib, io as _io, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import _cell_color

BASE = os.path.dirname(os.path.abspath(__file__))
CS = 11          # px per cell
W = H = cfv.WIDTH


def ground(a):
    if getattr(a, "burning", False):
        return "burning"
    if getattr(a, "burnt", False):
        return "burnt"
    if getattr(a, "has_burned", False):
        return "scorched"
    return "virgin"


def main(tag, steps):
    rng = random.Random(101)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=4, NUM_VICTIMS=4, NUM_FIREFIGHTERS=2,
                          WIND_DIRECTION="east", BATCH_SIZE=300,
                          FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
                          NUM_FIRE_TRACKERS=2, NUM_VICTIM_SEARCHERS=2)
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            model.step()

    fires = [a for a in model.schedule.agents if type(a).__name__ == "Fire"]
    counts, swatch = {}, {}
    parts = []
    for a in fires:
        x, y = int(a.pos[0]), int(a.pos[1])
        col = _cell_color(a)
        g = ground(a)
        counts[g] = counts.get(g, 0) + 1
        swatch.setdefault(g, col)
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
                     % (x * CS, (H - 1 - y) * CS, CS, CS, col))

    grid = []
    for i in range(W + 1):
        grid.append('<line x1="%.1f" y1="0" x2="%.1f" y2="%d"/>' % (i * CS + .5, i * CS + .5, H * CS))
    for j in range(H + 1):
        grid.append('<line x1="0" y1="%.1f" x2="%d" y2="%.1f"/>' % (j * CS + .5, W * CS, j * CS + .5))

    order = ["virgin", "burning", "scorched", "burnt"]
    rows = []
    for k, g in enumerate(order):
        if g not in counts:
            continue
        rows.append(
            '<rect x="%d" y="%d" width="18" height="18" fill="%s" stroke="#888"/>'
            '<text x="%d" y="%d" font-family="monospace" font-size="13" fill="#eee">'
            '%s  n=%d  %s</text>'
            % (W * CS + 14, 34 + k * 26, swatch[g],
               W * CS + 38, 48 + k * 26, g, counts[g], swatch[g]))

    inset_y = 34 + len(order) * 26 + 22
    inset = ['<text x="%d" y="%d" font-family="monospace" font-size="12" fill="#aaa">'
             'at actual cell size:</text>' % (W * CS + 14, inset_y)]
    for k, g in enumerate(("burnt", "scorched")):
        if g not in swatch:
            continue
        for i in range(6):
            inset.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
                         % (W * CS + 14 + i * CS, inset_y + 10 + k * (CS + 16), CS, CS, swatch[g]))
        inset.append('<text x="%d" y="%d" font-family="monospace" font-size="11" fill="#ccc">%s</text>'
                     % (W * CS + 20 + 6 * CS, inset_y + 20 + k * (CS + 16), g))

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d">' % (W * CS + 300, H * CS + 40, W * CS + 300, H * CS + 40)
        + '<rect width="100%%" height="100%%" fill="#141414"/>'
        + '<text x="4" y="16" font-family="monospace" font-size="13" fill="#eee">'
          'D/east/half seed 101, step %d  &#8212; %s</text>' % (steps, tag)
        + '<g transform="translate(0,24)">'
        + "".join(parts)
        + '<g stroke="rgba(0,0,0,0.18)" stroke-width="0.5">' + "".join(grid) + '</g>'
        + '</g>'
        + '<g transform="translate(0,24)">' + "".join(rows) + "".join(inset) + '</g>'
        + '</svg>'
    )
    out = os.path.join(BASE, "_sc_map_%s.svg" % tag)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print("WROTE", out)
    for g in order:
        if g in counts:
            print("  %-9s n=%-5d %s" % (g, counts[g], swatch[g]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "before",
         int(sys.argv[2]) if len(sys.argv) > 2 else 60)
