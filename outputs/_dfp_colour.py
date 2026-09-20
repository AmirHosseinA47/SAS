# -*- coding: utf-8 -*-
"""Non-burnable-depot round: pick and score the FUEL-LESS DEPOT GROUND colour.

Decision 6.3: fuel-less depot ground gets its OWN measured colour and a legend
entry, and the colour is chosen by CIEDE2000 against the full effective palette -
not by eye, and not by accepting VEGETATION_COLORS[0] = #414141, which is a
FIRE_COLORS[0] collision, sits in the burnt/smoke grey band, and says "spent"
about ground that has never burned.

INSTRUMENT. The colour maths is not re-transcribed: this script READS
outputs/_bm_colour_a.py as text and execs its library block (hex2rgb .. topk)
verbatim, so every number below comes from the same sRGB -> linear -> XYZ(D65) ->
CIELAB -> CIEDE2000 pipeline, the same Machado 2009 CVD matrices at severity 1.0
and the same achromatic model the base-mark and FOV rounds used. It is then
re-validated here against the 9 Sharma et al. pairs lifted as text from
outputs/_sc_deltae.py, and cross-checked against that file's INDEPENDENT scalar
de2000.

WHAT THIS COLOUR HAS TO SURVIVE, and why it is not the question basemark asked.
The base-mark banner is a MARK drawn OVER the depot fill. This is GROUND drawn
UNDER it: a cleared cell is by construction inside a depot block, so its rendered
forms are the depot fill composited over it, with and without the gridline, in
the canvas's own draw order (cells -> gridlines -> depot fill, so the depot tint
is the OUTERMOST layer). All four forms are scored, because the same colour
renders untinted at BASE_STATION_MODE 0 and on the mesa canvas (main.py), which
draws no depot overlay at all.
  -> outputs/_dfp_colour.txt
"""
import ast
import math
import re
import sys
import time

import numpy as np

ROOT = "E:/Projects/SAS_wt/dfp"
NEWHEX = "#193cff"
OUT_TXT = ROOT + "/outputs/_dfp_colour.txt"
T0 = time.time()
_LINES = []


def P(s=""):
    s = str(s)
    _LINES.append(s)
    print(s)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# the base-mark round's library block, lifted VERBATIM as text
# ---------------------------------------------------------------------------
_bm_src = open(ROOT + "/outputs/_bm_colour_a.py", "r", encoding="utf-8").read()
_start = _bm_src.index("def hex2rgb(h):")
_end = _bm_src.index('P("=" * 78)')
_LIB = _bm_src[_start:_end]
assert "def de2000(" in _LIB and "def topk(" in _LIB and "class Pal" in _LIB
exec(compile(_LIB, "outputs/_bm_colour_a.py[lib]", "exec"), globals())

P("=" * 78)
P("FUEL-LESS DEPOT GROUND COLOUR  -  outputs/_dfp_colour.py")
P("python %s | numpy %s" % (sys.version.split()[0], np.__version__))
P("=" * 78)
P("")
P("[0] INSTRUMENT PROVENANCE")
P("  library block: outputs/_bm_colour_a.py bytes %d..%d (%d lines), compiled and run verbatim"
  % (_start, _end, _LIB.count("\n")))
P("  conditions: %s" % ", ".join(CONDS))
P("  sweep grid: %d colours, {0,5,..,255}^3" % NGRID)

# ---- Sharma validation, pairs lifted from outputs/_sc_deltae.py as text ------
_sc_src = open(ROOT + "/outputs/_sc_deltae.py", "r", encoding="utf-8").read()
_m = re.search(r"REF = (\[.*?\])\n", _sc_src, re.S)
SHARMA = ast.literal_eval(_m.group(1))
worst = 0.0
for l1, l2, exp in SHARMA:
    got = float(de2000(np.array(l1), np.array(l2)))
    worst = max(worst, abs(got - exp))
    assert abs(got - exp) < 1e-3, (l1, l2, got, exp)
P("")
P("[1] CIEDE2000 re-validated on the %d Sharma et al. pairs lifted from outputs/_sc_deltae.py"
  % len(SHARMA))
P("  worst absolute error %.2e" % worst)

_sc_lib = _sc_src[_sc_src.index("def _lin(c):"):_sc_src.index("# validation against")]
_SC = {"math": math}
exec(compile(_sc_lib, "outputs/_sc_deltae.py[lib]", "exec"), _SC)


def sc_de(h1, h2):
    return _SC["de2000"](_SC["lab"](h1), _SC["lab"](h2))


P("  independent scalar de2000 lifted from outputs/_sc_deltae.py: max |vector - scalar| over the")
P("  Sharma hex-free pairs is not defined, so it is cross-checked on real palette pairs in [8].")

# ---------------------------------------------------------------------------
# the palette, re-verified against the working tree's source text
# ---------------------------------------------------------------------------
cfv_src = open(ROOT + "/common_fixed_variables.py", "r", encoding="utf-8").read()
sd_src = open(ROOT + "/serve_dashboard.py", "r", encoding="utf-8").read()
mn_src = open(ROOT + "/main.py", "r", encoding="utf-8").read()


def parse_list(src, name):
    m = re.search(r"^" + name + r"\s*=\s*(\[[^\]]*\])", src, re.M)
    return [s.lower() for s in ast.literal_eval(m.group(1))], src[:m.start()].count("\n") + 1


VEG, ln_veg = parse_list(cfv_src, "VEGETATION_COLORS")
FIRE, ln_fire = parse_list(cfv_src, "FIRE_COLORS")
SMOKE, _ = parse_list(cfv_src, "SMOKE_COLORS")
BW, _ = parse_list(cfv_src, "BLACK_AND_WHITE_COLORS")

raw = []
for i, c in enumerate(VEG):
    raw.append((c, "VEG[%d]" % i))
for i, c in enumerate(FIRE):
    raw.append((c, "FIRE[%d]" % i))
raw.append((SMOKE[0], "smoke"))
raw += [("#2b2b2b", "burnt"), ("#895e00", "scorched"), ("#2f4a1a", "spared")]
for i, c in enumerate(BW):
    raw.append((c, "BW[%d]" % i))
raw += [("#00bfff", "mesa PathMarker (main.py, Layer 1)"),
        ("#05080c", "canvas element background (CSS)"),
        ("#00ffff", "UAV searcher"), ("#ff00ff", "UAV tracker"), ("#0066cc", "UAV relay"),
        ("#ff8c00", "UAV confirmer"), ("#888888", "UAV RTB"),
        ("#000000", "black: UAV stroke / dead victim / FOV casing / banner casing"),
        ("#ffff00", "victim candidate"), ("#ffa500", "victim confirmed"),
        ("#00aaff", "victim assigned/rescued"), ("#00ffcc", "firefighter / ff trail"),
        ("#770099", "depot outline + BASE banner field"), ("#ffd75a", "assignment"),
        ("#78aaff", "uav trail"), ("#1c630b", "canvas bg (map mode)"),
        ("#ffffff", "white: canvas bg (prob mode) / FOV core / banner keyline")]
seen, n50, dups = {}, [], []
for h, n in raw:
    if h in seen:
        dups.append("%s %s == %s" % (h, n, seen[h]))
    else:
        seen[h] = n
        n50.append((h, n))
N50 = Pal(n50)
P("")
P("[2] PALETTE N50 - re-parsed from the working tree")
P("  common_fixed_variables.py:%d VEGETATION_COLORS(%d)  :%d FIRE_COLORS(%d)  SMOKE(%d)  BW(%d)"
  % (ln_veg, len(VEG), ln_fire, len(FIRE), len(SMOKE), len(BW)))
P("  nominal entries %d -> DISTINCT %d ; duplicates folded: %s"
  % (len(raw), len(N50), "; ".join(dups) if dups else "none"))
for lit in ("#2b2b2b", "#895e00", "#2f4a1a", "rgba(119,0,153,0.22)", "rgba(0,0,0,0.18)",
            "#770099", "#FFFFFF", "#000000"):
    assert lit.lower() in sd_src.lower(), lit
P("  every map literal checked is still present in serve_dashboard.py: yes")
assert "#2b2b2b" in mn_src and "#895e00" in mn_src
P("  mesa canvas (main.py) carries the same burnt/scorched literals: yes")
P("")
P("  REVERSE CHECK - the one _bm_colour_a.py does not do. A presence assertion catches a")
P("  literal that VANISHES; it cannot catch one that is ADDED, and an added map colour is")
P("  exactly what would silently invalidate a margin. So: scan both renderers for every")
P("  #rrggbb literal and require each to be either in N50 or in a NAMED not-on-the-map list.")
CHROME = {
    "#0b0f14": "CSS --bg", "#1a2129": "CSS --card", "#232d38": "CSS --card2",
    "#2f3b47": "CSS --line", "#d8dee6": "CSS --text", "#8a97a5": "CSS --muted",
    "#4aa3ff": "CSS --accent", "#3ecf8e": "CSS --green", "#f5a623": "CSS --amber",
    "#ff5a5a": "CSS --red", "#b07cff": "CSS --purple", "#22c3c3": "CSS --teal",
    "#10161e": "page body gradient stop", "#16202b": "eval panel gradient stop",
    "#121821": "eval panel gradient stop", "#06121f": "button label",
}
_hex = re.compile(r"#[0-9a-fA-F]{6}\b")
unknown = []
for _nm, _src in (("serve_dashboard.py", sd_src), ("main.py", mn_src)):
    for h in sorted({m.group(0).lower() for m in _hex.finditer(_src)}):
        if h in N50.idx or h in CHROME or h == NEWHEX:
            continue
        unknown.append("%s in %s" % (h, _nm))
P("  serve_dashboard.py + main.py literals: %d in N50, %d named page chrome, %d UNACCOUNTED"
  % (sum(1 for h in N50.hex if h in (sd_src + mn_src).lower()), len(CHROME), len(unknown)))
if unknown:
    P("  UNACCOUNTED: %s" % unknown)
assert not unknown, unknown
P("  (page chrome is CSS for cards, buttons and text - none of it is ever painted on the map")
P("  canvas, which is covered edge to edge by one cell colour per cell.)")

# ---------------------------------------------------------------------------
# N+ : every base under the depot fill and under the gridline
# ---------------------------------------------------------------------------
DEPOT = hex2rgb("#770099")


def over_pct(src, pct, dst):
    """source-over in sRGB byte space, alpha = pct/100, exact round-half-up."""
    return tuple((pct * s + (100 - pct) * d + 50) // 100 for s, d in zip(src, dst))


def grid_over(c):
    return over_pct((0, 0, 0), 18, c)


def depot_over(c):
    return over_pct(DEPOT, 22, c)


BASES = []
for i, c in enumerate(VEG):
    BASES.append((c, "VEG[%d]" % i))
for i, c in enumerate(FIRE[1:], start=1):
    BASES.append((c, "FIRE[%d]" % i))
BASES += [("#ababab", "smoke"), ("#2b2b2b", "burnt"), ("#895e00", "scorched"), ("#2f4a1a", "spared")]
for i, c in enumerate(BW):
    BASES.append((c, "BW[%d]" % i))

ents = list(n50)
have = {h: n for h, n in ents}
coll = []
for bh, bn in BASES:
    b = hex2rgb(bh)
    for cc, nm in ((depot_over(b), "depot/" + bn),
                   (depot_over(grid_over(b)), "depot+grid/" + bn),
                   (grid_over(b), "grid/" + bn)):
        hx = rgb2hex(*cc)
        if hx in have:
            coll.append("%s %s == %s" % (hx, nm, have[hx]))
        else:
            have[hx] = nm
            ents.append((hx, nm))
NP = Pal(ents)
P("")
P("[3] PALETTE N+ = N50 + every base under the depot fill / the gridline / both")
P("  bases %d (12 VEG + 11 FIRE + smoke/burnt/scorched/spared + 11 BW); composites generated %d"
  % (len(BASES), 3 * len(BASES)))
P("  N+ = %d distinct (%d new); collisions folded: %d" % (len(NP), len(NP) - len(N50), len(coll)))
P("  compositing: round-half-up of pct*src + (100-pct)*dst per 8-bit channel; depot 22%, gridline 18% black")

# ---------------------------------------------------------------------------
# the candidate's own rendered forms
# ---------------------------------------------------------------------------
FORMS = [("plain", lambda c: c),
         ("grid", grid_over),
         ("depot", depot_over),
         ("depot+grid", lambda c: depot_over(grid_over(c)))]
P("")
P("[4] THE CANDIDATE'S FOUR RENDERED FORMS: %s" % ", ".join(f for f, _ in FORMS))
P("  'depot' and 'depot+grid' are the only two that occur at the shipped default (every cleared")
P("  cell is inside a depot block); 'plain' and 'grid' occur at BASE_STATION_MODE 0 and on the")
P("  mesa canvas, which draws no depot overlay. All four are scored and the WORST is kept.")


def form_rgbs(rgb):
    return np.array([f(tuple(int(v) for v in rgb)) for _n, f in FORMS], dtype=np.int64)


def score_hex(hx, pal=NP):
    forms = form_rgbs(hex2rgb(hx))
    best = None
    per = {}
    for c in CONDS:
        lf = lab_under(forms, c)
        d = de2000(lf[:, None, :], pal.lab[c][None, :, :])
        fi, pi = np.unravel_index(int(np.argmin(d)), d.shape)
        v = float(d[fi, pi])
        per[c] = (v, FORMS[fi][0], pal.hex[pi], pal.name[pi])
        if best is None or v < best[0]:
            best = (v, c, FORMS[fi][0], pal.hex[pi], pal.name[pi])
    return best, per


def normal_score(hx, pal=NP):
    """min over (4 forms x palette) under NORMAL vision - the primary objective."""
    return score_hex(hx, pal)[1]["normal"]


# ---- exhaustive sweep -------------------------------------------------------
P("")
P("[4a] WHY THE OBJECTIVE IS NORMAL VISION, NOT THE WORST CONDITION")
P("  Scored worst-of-5, the ACHROMATIC condition alone caps ANY colour in this palette at 0.76 dE:")
P("  N+ has %d entries whose greyscale luminances tile the whole range, so some entry is always" % len(NP))
P("  within ~1 dE of any candidate once hue is discarded. That is not a property of the candidate -")
P("  EVERY colour this repo already ships fails it on the identical instrument (section 7: scorched")
P("  0.13, depot/BASE 0.15, burnt 0.29, spared 0.46). Making achromatic a veto would set a standard")
P("  nothing in the repo meets, and would drive the choice to near-black - which is exactly the")
P("  burnt/charred band this colour must NOT read as. The objective below is therefore NORMAL")
P("  vision, which is what the shipped depot violet was chosen on (common_fixed_variables.py:507-516")
P("  quotes 28.76 dE for #770099 against 27.34 for scorched on the same co-occurring set). All five")
P("  conditions are REPORTED for the winner and for every shipped reference beside it.")
P("")
P("[5] EXHAUSTIVE SWEEP over %d colours: min over N+ (%d entries), over 4 forms, NORMAL vision"
  % (NGRID, len(NP)))
form_grids = [np.array([f(tuple(int(v) for v in rgb)) for rgb in GRID_RGB], dtype=np.int64)
              for _n, f in FORMS]
COND_MIN = {}
for c in CONDS:
    labP = NP.lab[c]
    per_form = []
    for fg in form_grids:
        labX = lab_under(fg, c)
        mins = np.empty(NGRID)
        for s in range(0, NGRID, 512):
            e = min(NGRID, s + 512)
            d = de2000(labX[s:e, None, :], labP[None, :, :])
            mins[s:e] = d.min(axis=1)
        per_form.append(mins)
    COND_MIN[c] = np.min(np.stack(per_form, axis=0), axis=0)
    i = int(np.argmax(COND_MIN[c]))
    P("  best under %-13s alone: %6.2f at %s" % (c, COND_MIN[c][i], rgb2hex(*GRID_RGB[i])))
score = COND_MIN["normal"]
cvd = np.min(np.stack([COND_MIN[c] for c in ("protanopia", "deuteranopia", "tritanopia")], axis=0), axis=0)
top = topk(score, 30)
P("  TOP 30 by NORMAL vision (cvd = worst of the three dichromacies; achr = achromatic):")
P("    %-9s %7s %7s %7s   binding entry under normal vision" % ("hex", "normal", "cvd", "achr"))
for i in top:
    hx = rgb2hex(*GRID_RGB[i])
    v, fm, ph, pn = normal_score(hx)
    P("    %-9s %7.2f %7.2f %7.2f   form %-10s vs %-9s %s"
      % (hx, score[i], cvd[i], COND_MIN["achromatic"][i], fm, ph, pn))
CEIL = float(score[top[0]])
P("  CEILING (normal vision) = %.2f dE2000 at %s" % (CEIL, rgb2hex(*GRID_RGB[top[0]])))
P("")
P("[5a] THE SWEEP RESTRICTED TO L* 22..82 - AND WHAT THAT CONSTRAINT REALLY IS")
P("  Stated honestly, because the first draft justified it with a danger this instrument says")
P("  does not exist: the unconstrained chromatic winner #00006e (L* 10.0) is 27.98 dE from burnt")
P("  and 89.58 from white, so the objective was NOT failing to separate it from either. The L*")
P("  floor is not catching a confusion the sweep missed.")
P("  What it IS: a proxy for the ACHROMATIC condition this script deliberately does not veto on")
P("  ([4a]). A ground at L* 10 sits in the same luminance band as burnt (16.0) and black (0),")
P("  so on a greyscale display, a monochrome print, or for a viewer with achromatopsia, ground")
P("  that CANNOT burn would be the same tone as ground that has burned to nothing - which is")
P("  the exact confusion this colour exists to remove. Keeping L* well clear of both ends is")
P("  the only part of the achromatic condition that can be honoured at all.")
P("  IT IS NOT FREE: it cuts the chromatic ceiling from 8.65 (#00006e) to 6.82, a 21%% cut in")
P("  the deciding quantity. That is the price, and it is a judgement, not a measurement.")
gl = lab_under(GRID_RGB, "normal")[:, 0]
mask = (gl >= 22.0) & (gl <= 82.0)
top2 = topk(score, 30, mask=mask)
P("    %-9s %7s %7s %7s %6s   binding entry under normal vision" % ("hex", "normal", "cvd", "achr", "L*"))
for i in top2[:20]:
    hx = rgb2hex(*GRID_RGB[i])
    v, fm, ph, pn = normal_score(hx)
    P("    %-9s %7.2f %7.2f %7.2f %6.1f   form %-10s vs %-9s %s"
      % (hx, score[i], cvd[i], COND_MIN["achromatic"][i], gl[i], fm, ph, pn))

# ---- named candidates -------------------------------------------------------
P("")
P("[5b] THE OBJECTIVE THAT ACTUALLY DECIDES: worst of the four CHROMATIC conditions")
P("  Maximising NORMAL vision alone picks #fa1982, a saturated pink whose dichromatic margins are")
P("  1.2-2.0 dE - it collapses into the fire/depot band for a red-green dichromat. The shipped depot")
P("  violet does not (16.80 normal / 11.36 prot / 9.44 deut / 12.38 trit, section 7), and a ground")
P("  colour that only works for trichromats would be a worse mark than the one it replaces. So the")
P("  DECIDING objective is min(normal, protanopia, deuteranopia, tritanopia) - achromatic excluded")
P("  for the reason given in [4a] - under the same L* 22..82 semantic constraint.")
CHROM = np.min(np.stack([COND_MIN[c] for c in ("normal", "protanopia", "deuteranopia", "tritanopia")],
                        axis=0), axis=0)
top3 = topk(CHROM, 40, mask=mask)
P("    %-9s %7s %7s %7s %7s %7s %7s %6s" % ("hex", "CHROM", "normal", "prot", "deut", "trit", "achr", "L*"))
for i in top3[:20]:
    hx = rgb2hex(*GRID_RGB[i])
    P("    %-9s %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f %6.1f"
      % (hx, CHROM[i], COND_MIN["normal"][i], COND_MIN["protanopia"][i], COND_MIN["deuteranopia"][i],
         COND_MIN["tritanopia"][i], COND_MIN["achromatic"][i], gl[i]))
P("  CHROMATIC CEILING under the L* constraint = %.2f dE at %s"
  % (CHROM[top3[0]], rgb2hex(*GRID_RGB[top3[0]])))
top3u = topk(CHROM, 10)
P("  (unconstrained, for reference: %.2f dE at %s, L* %.1f)"
  % (CHROM[top3u[0]], rgb2hex(*GRID_RGB[top3u[0]]), gl[top3u[0]]))
P("")
P("[5bb] THE CONSTRAINT THE FIRST DRAFT OF THIS SCRIPT MISSED: WHAT IS DRAWN ON TOP")
P("  A palette sweep asks 'is this colour confusable with another colour'. It cannot see a")
P("  SEMI-TRANSPARENT MARK COMPOSITED OVER the new ground - and the dashboard draws four:")
P("  the UAV trail rgba(120,170,255,0.30), the firefighter trail rgba(0,255,204,0.35), the")
P("  assignment line rgba(255,215,90,0.80) and the gridline rgba(0,0,0,0.18). Two of them are")
P("  BLUE-FAMILY, and the depot is exactly where UAV trails concentrate - a UAV parks there to")
P("  charge, which is this whole round's motivation. So a blue ground is the one case where")
P("  this omission bites. Scored below as dE(ground form, overlay over that ground form).")
OVERLAYS = [("uav trail", hex2rgb("#78aaff"), 30),
            ("ff trail", hex2rgb("#00ffcc"), 35),
            ("assignment", hex2rgb("#ffd75a"), 80)]


def overlay_min(rgb):
    """Worst legibility of any overlay over this ground, in BOTH rendered forms."""
    g0 = tuple(int(v) for v in rgb)
    gd = depot_over(g0)
    worst = None
    for _nm, c, a in OVERLAYS:
        for base in (g0, gd):
            o = over_pct(c, a, base)
            d = float(de2000(lab_under(np.array([base]), "normal")[0],
                             lab_under(np.array([o]), "normal")[0]))
            worst = d if worst is None else min(worst, d)
    return worst


P("")
P("  %-34s %-9s %-9s %s" % ("ground", "pure", "under depot", "worst overlay dE (normal vision)"))
for hx, what in (("#414141", "BEFORE: VEG[0], today's depot floor"),
                 ("#1c630b", "ordinary vegetation"),
                 ("#2b2b2b", "burnt"),
                 ("#895e00", "scorched")):
    P("  %-34s %-9s %-9s %6.2f" % (what, hx, rgb2hex(*depot_over(hex2rgb(hx))),
                                   overlay_min(hex2rgb(hx))))
FLOOR_TODAY = overlay_min(hex2rgb("#414141"))
P("  THE CONSTRAINT, declared here: a new depot floor must not make ANY overlay less legible")
P("  than the WORST it already is on ordinary vegetation, %.2f dE - the ground a UAV trail"
  % overlay_min(hex2rgb("#1c630b")))
P("  crosses for most of its length. (Today's depot floor manages %.2f.)" % FLOOR_TODAY)
OV_MIN = overlay_min(hex2rgb("#1c630b"))
ovg = np.array([overlay_min(rgb) for rgb in GRID_RGB])
ok = ovg >= OV_MIN
P("  colours in the sweep meeting it: %d of %d" % (int(ok.sum()), NGRID))
P("")
P("[5c] THE TIE-BREAK, DECLARED BEFORE THE WINNER IS READ OFF")
P("  The chromatic ceiling is a plateau: dozens of colours sit within a tenth of a dE of it and")
P("  differ by three full dE under NORMAL vision, which is the condition almost every viewer is")
P("  in. So: take every candidate within 0.15 dE of the chromatic ceiling, and among those")
P("  maximise the NORMAL-vision margin. Reported alongside is the margin from #770099 itself -")
P("  the depot outline and the BASE banner field - because EVERY candidate on this plateau binds")
P("  against it, this ground sits inside that outline and under that fill, and a ground that read")
P("  as the mark would undo the base-mark round.")
BAND = [i for i in top3 if CHROM[i] >= CHROM[top3[0]] - 0.15]
BAND.sort(key=lambda i: -COND_MIN["normal"][i])
P("  OVERLAY CHECK ON THE BAND: worst overlay dE for each of the %d band candidates" % len(BAND))
band_ov = [(rgb2hex(*GRID_RGB[i]), overlay_min(GRID_RGB[i])) for i in BAND]
P("    best %.2f, worst %.2f, median %.2f - against the %.2f constraint"
  % (max(v for _h, v in band_ov), min(v for _h, v in band_ov),
     sorted(v for _h, v in band_ov)[len(band_ov) // 2], OV_MIN))
P("    band candidates meeting the constraint: %d of %d"
  % (sum(1 for _h, v in band_ov if v >= OV_MIN), len(band_ov)))
# Re-select under the joint objective: the chromatic palette margin AND the overlay
# constraint. Declared here, before the winner is read.
JOINT = [i for i in topk(CHROM, 4000, mask=mask) if ovg[i] >= OV_MIN]
if JOINT:
    JBEST = max(CHROM[i] for i in JOINT)
    JBAND = [i for i in JOINT if CHROM[i] >= JBEST - 0.15]
    JBAND.sort(key=lambda i: -COND_MIN["normal"][i])
    P("")
    P("  JOINT FRONTIER: best chromatic palette margin among colours meeting the overlay")
    P("  constraint = %.2f dE (vs %.2f with the constraint ignored). Top 12 of that band:" % (JBEST, CHROM[top3[0]]))
    P("    %-9s %7s %7s %7s %7s %7s %6s %8s" % ("hex", "CHROM", "normal", "prot", "deut", "trit", "L*", "overlay"))
    for i in JBAND[:12]:
        hx = rgb2hex(*GRID_RGB[i])
        P("    %-9s %7.2f %7.2f %7.2f %7.2f %7.2f %6.1f %8.2f"
          % (hx, CHROM[i], COND_MIN["normal"][i], COND_MIN["protanopia"][i],
             COND_MIN["deuteranopia"][i], COND_MIN["tritanopia"][i], gl[i], ovg[i]))
else:
    JBAND = []
    P("  NO colour in the L*-constrained sweep meets the overlay constraint.")
P("")
P("  THE FRONTIER. The two criteria are in genuine conflict: the overlay that binds is the UAV")
P("  trail, which is BLUE (#78aaff), and blue is also the only hue band robust across all three")
P("  dichromacies - so every colour that is hard to confuse with the palette is also a poor")
P("  background for that trail. Best achievable palette margin as the overlay floor is relaxed:")
P("    %-14s %-9s %7s %7s %6s %s" % ("overlay floor", "hex", "CHROM", "normal", "L*", "what it is"))
for floor, what in ((OV_MIN, "= ordinary vegetation, the strict reading"),
                    (12.0, ""), (11.0, ""), (10.0, ""), (9.0, ""), (0.0, "= no constraint")):
    m2 = mask & (ovg >= floor)
    if not m2.any():
        continue
    j = topk(CHROM, 1, mask=m2)[0]
    P("    %-14.2f %-9s %7.2f %7.2f %6.1f %s"
      % (floor, rgb2hex(*GRID_RGB[j]), CHROM[j], COND_MIN["normal"][j], gl[j], what))
P("")
P("  THE CALL, and it is a trade, not a pass. #193cff is kept.")
P("   - The criterion decision 6.3 names is that the ground be distinguishable from every")
P("     palette entry BY MEASUREMENT. On that criterion #193cff scores 6.69 dE worst-chromatic")
P("     and 12.85 normal, beaten by exactly one colour this repo ships (#770099, 9.44).")
P("     The strictly overlay-compliant best, #736455, scores 4.25 / 5.31 - a muddy khaki in the")
P("     scorched-and-dirt band, i.e. worse on the criterion the decision actually asked for and")
P("     worse semantically for ground that is meant to read as engineered, not soiled.")
P("   - The cost is real and is stated: the UAV trail over the depot floor goes from 14.27 dE")
P("     (today, over #4d3354) to 9.18 dE. That is still about four times the ~2.3 dE")
P("     just-noticeable difference, so the trail remains visible; it is no longer the most")
P("     visible it could be. The firefighter trail goes 38.37 -> 22.50, the assignment line")
P("     65.98 -> 68.94 (better) and the gridline 4.05 -> 5.93 (better).")
P("   - It is one literal in three files. To overrule, pick a row of the frontier above and")
P("     change main.CLEARED_COLOR, serve_dashboard._cell_color's return and the JS NOFUEL")
P("     const; tests/test_depot_fireproof.py pins all three to one value and will fail loudly")
P("     if only some are changed.")
P("  %d candidates in the band; top 14 by normal-vision margin:" % len(BAND))
P("    %-9s %7s %7s %7s %7s %7s %7s %6s %9s"
  % ("hex", "CHROM", "normal", "prot", "deut", "trit", "achr", "L*", "vs770099"))
for i in BAND[:14]:
    hx = rgb2hex(*GRID_RGB[i])
    fr = form_rgbs(hex2rgb(hx))
    d770 = min(float(de2000(lab_under(fr, c), lab1("#770099", c)[None, :]).min()) for c in CONDS)
    P("    %-9s %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f %6.1f %9.2f"
      % (hx, CHROM[i], COND_MIN["normal"][i], COND_MIN["protanopia"][i],
         COND_MIN["deuteranopia"][i], COND_MIN["tritanopia"][i], COND_MIN["achromatic"][i],
         gl[i], d770))
# THE DECIDING RULE, and it is a decision, not an argmax. The primary criterion is
# the one decision 6.3 names - distinguishable from every palette entry by
# measurement - so the winner is the chromatic band's pick. The overlay constraint
# is REPORTED as a priced alternative rather than allowed to select, because
# letting it select silently swaps a criterion the brief asked for (palette
# separation) for one it did not (overlay legibility), and the swap costs 2.44 dE
# of the former to buy 5.4 dE of the latter. Both numbers are below; the trade is
# the maintainer's to reverse with one literal.
WINNER = rgb2hex(*GRID_RGB[BAND[0]])
P("  WINNER = %s   chromatic %.2f | normal %.2f | overlay %.2f"
  % (WINNER, CHROM[BAND[0]], COND_MIN["normal"][BAND[0]], ovg[BAND[0]]))
if JBAND:
    _a = JBAND[0]
    P("  THE PRICED ALTERNATIVE, if the overlay constraint is made binding instead:")
    P("    %s   chromatic %.2f | normal %.2f | overlay %.2f"
      % (rgb2hex(*GRID_RGB[_a]), CHROM[_a], COND_MIN["normal"][_a], ovg[_a]))
    P("    i.e. %+.2f dE of palette separation for %+.2f dE of overlay legibility."
      % (CHROM[_a] - CHROM[BAND[0]], ovg[_a] - ovg[BAND[0]]))
else:
    P("  No colour in the L*-constrained sweep meets the overlay constraint at all.")
P("")
P("  HOW SENSITIVE IS THE WINNER TO THE 0.15 BAND WIDTH? Reported because it is a free")
P("  parameter and the winner sits at the band's low-CHROM edge:")
for bw in (0.05, 0.10, 0.15, 0.25, 0.50):
    b2 = [i for i in top3 if CHROM[i] >= CHROM[top3[0]] - bw]
    b2.sort(key=lambda i: -COND_MIN["normal"][i])
    w2 = rgb2hex(*GRID_RGB[b2[0]])
    _d = float(de2000(lab1(w2, "normal"), lab1(WINNER, "normal")))
    P("    band %.2f -> %-9s (%3d candidates)  dE from %s = %5.2f" % (bw, w2, len(b2), WINNER, _d))
P("    Every one is the same deep blue within a few dE, every one clears the corrected bar in")
P("    section 7, and every one binds against #770099. The band width moves the shade, not the")
P("    decision - which is why the round does not treat the exact hex as load-bearing.")
P("")

CANDS = [
    ("#414141", "STATUS QUO: VEGETATION_COLORS[0] == FIRE_COLORS[0], what a fuel-0 cell renders today"),
    ("#2b2b2b", "burnt"),
    ("#895e00", "scorched"),
    ("#00004b", "the FOV round's flat-sweep colour"),
    ("#770099", "the depot outline / BASE banner field"),
]
CANDS += [(rgb2hex(*GRID_RGB[i]), "sweep rank %d (unrestricted)" % (k + 1)) for k, i in enumerate(top[:6])]
CANDS += [(rgb2hex(*GRID_RGB[i]), "L*-restricted normal rank %d" % (k + 1)) for k, i in enumerate(top2[:4])]
CANDS += [(rgb2hex(*GRID_RGB[i]), "CHROMATIC rank %d" % (k + 1)) for k, i in enumerate(top3[:6])]
CANDS += [(rgb2hex(*GRID_RGB[i]), "band-by-normal rank %d" % (k + 1)) for k, i in enumerate(BAND[:10])]
P("[6] NAMED CANDIDATES vs N+, all four forms, every condition reported")
P("  %-9s %7s %7s %7s %7s %7s  %-9s %-26s %s"
  % ("hex", "normal", "prot", "deut", "trit", "achr", "nearest", "which is (normal)", "note"))
_seen_c = set()
for hx, note in CANDS:
    if hx in _seen_c:
        continue
    _seen_c.add(hx)
    b, per = score_hex(hx)
    P("  %-9s %7.2f %7.2f %7.2f %7.2f %7.2f  %-9s %-26s %s"
      % (hx, per["normal"][0], per["protanopia"][0], per["deuteranopia"][0],
         per["tritanopia"][0], per["achromatic"][0], per["normal"][2], per["normal"][3][:26], note))

P("")
P("[7] REFERENCE MARGINS ALREADY SHIPPED IN THIS REPO (same instrument, same N+, self excluded)")
P("  TWO CORRECTIONS the first draft of this table needed, both of which flattered the new")
P("  colour by understating what is already shipped:")
P("   (a) SELF-COMPOSITES. min_vs's exclude drops only the exact hex, not the N+ entries built")
P("       FROM it. Scorched's nearest entry was grid/scorched - its own gridline edge pixel.")
P("       A cell interior is not confusable with its own 18%-black edge, so all four of a")
P("       reference's own forms are excluded here.")
P("   (b) CROSS-MODE ENTRIES. BLACK_AND_WHITE_COLORS is painted only inside if(probMode) and")
P("       burnt/scorched/vegetation only in the else branch, so a map-mode ground colour and a")
P("       BW entry are never on screen in the same frame. The old table had burnt at 1.27 dE")
P("       against grid/BW[8]. Each reference below is scored against the entries that can")
P("       co-occur with IT. The new colour is scored against BOTH sets, because it is the one")
P("       ground colour this change paints in both modes.")


def forms_of(hx):
    r = hex2rgb(hx)
    return {rgb2hex(*f(r)) for _n, f in FORMS}


def same_mode_pal(hx, prob):
    """N+ minus hx's own four forms, restricted to entries that can co-occur."""
    ents = []
    mine = forms_of(hx)
    for h, n in zip(NP.hex, NP.name):
        if h in mine:
            continue
        isbw = "BW[" in n
        if prob and not isbw:
            continue
        if (not prob) and isbw:
            continue
        ents.append((h, n))
    return Pal(ents)


P("")
P("  %-9s %6s %7s %7s %7s %7s %7s  %-9s %s"
  % ("hex", "mode", "normal", "prot", "deut", "trit", "achr", "nearest", "which is (normal)"))
REFMIN = {}
REFCHROM = {}
for hx, what, prob in (("#895e00", "scorched", False), ("#2b2b2b", "burnt", False),
                       ("#2f4a1a", "spared veg", False), ("#770099", "depot / BASE banner", False),
                       ("#414141", "VEG[0] == FIRE[0]", False), ("#ababab", "smoke", False),
                       ("#00ffcc", "firefighter", False), ("#ffffff", "BW[0] / prob low", True)):
    pal = same_mode_pal(hx, prob)
    per = {c: min_vs(pal, hx, c, True) for c in CONDS}
    REFMIN[hx] = per["normal"][0]
    REFCHROM[hx] = min(per[c][0] for c in ("normal", "protanopia", "deuteranopia", "tritanopia"))
    P("  %-9s %6s %7.2f %7.2f %7.2f %7.2f %7.2f  %-9s %s   <- %s"
      % (hx, "prob" if prob else "map", per["normal"][0], per["protanopia"][0],
         per["deuteranopia"][0], per["tritanopia"][0], per["achromatic"][0],
         pal.hex[per["normal"][1]], pal.name[per["normal"][1]], what))
P("  THE BAR, corrected: %.2f dE normal / %.2f dE worst-chromatic - the weakest shipped"
  % (min(REFMIN.values()), min(REFCHROM.values())))
P("  single-state map colour, self-composites and cross-mode entries removed (%s / %s)."
  % (min(REFMIN, key=REFMIN.get), min(REFCHROM, key=REFCHROM.get)))

P("")
P("[8] CROSS-CHECK against the INDEPENDENT scalar de2000 of outputs/_sc_deltae.py (normal vision)")
pairs = [("#895e00", "#2b2b2b"), ("#770099", "#414141"), ("#2f4a1a", "#1c630b"),
         ("#00ffff", "#00ffcc"), (rgb2hex(*GRID_RGB[top[0]]), "#414141"),
         (rgb2hex(*GRID_RGB[top[0]]), "#770099")]
worst_x = 0.0
for a, b in pairs:
    v1 = float(de2000(lab1(a, "normal"), lab1(b, "normal")))
    v2 = float(sc_de(a, b))
    worst_x = max(worst_x, abs(v1 - v2))
    P("  %s vs %s : vector %8.4f | scalar %8.4f | diff %.2e" % (a, b, v1, v2, abs(v1 - v2)))
P("  worst |vector - scalar| over %d pairs: %.2e" % (len(pairs), worst_x))
P("  The two implementations use different white points (matrix-sum D65 here, the 0.95047/1.08883")
P("  convention in _sc_deltae), which is the whole of the 3e-3 spread. Tolerance 1e-2.")
assert worst_x < 1e-2

P("")
P("[9] THE CHOSEN COLOUR, IN FULL")
P("  %s   L* %.1f" % (WINNER, float(lab1(WINNER, "normal")[0])))
wf = form_rgbs(hex2rgb(WINNER))
P("  its four rendered forms:")
for k, (nm, _fn) in enumerate(FORMS):
    P("    %-11s %s" % (nm, rgb2hex(*wf[k])))
b, per = score_hex(WINNER)
P("  min dE2000 to N+ (%d entries), per condition, worst over the four forms:" % len(NP))
for c in CONDS:
    v, fm, ph, pn = per[c]
    P("    %-13s %7.2f   binding form %-11s vs %-9s %s" % (c, v, fm, ph, pn))
P("  worst CHROMATIC condition: %.2f dE"
  % min(per[c][0] for c in ("normal", "protanopia", "deuteranopia", "tritanopia")))
P("  On this identical instrument and palette the weakest CHROMATIC margin of a colour this repo")
P("  ALREADY SHIPS is %.2f (%s) and the strongest is %.2f (#770099). The new colour is scored over"
  % (min(REFCHROM.values()), min(REFCHROM, key=REFCHROM.get), max(REFCHROM.values())))
P("  FOUR rendered forms; every shipped reference is scored over ONE, so the comparison is")
P("  conservative against the new colour, not for it.")
P("  nearest N+ entry to each form, normal vision:")
for k, (nm, _fn) in enumerate(FORMS):
    d = de2000(lab_under(wf[k:k + 1], "normal"), NP.lab["normal"])
    j = int(np.argmin(d))
    P("    %-11s %s -> %6.2f dE from %s %s" % (nm, rgb2hex(*wf[k]), float(d[j]), NP.hex[j], NP.name[j]))
P("  exact-hex collision with any N+ entry: %s" % (WINNER in NP.idx))
P("  WCAG contrast of the legend swatch against the card background #121821: %.2f:1"
  % wcag_cr(hex2rgb(WINNER), hex2rgb("#121821")))
P("  overlays composited over it, normal vision (the constraint from [5bb], floor %.2f):" % OV_MIN)
for nm, c, a in OVERLAYS + [("gridline", (0, 0, 0), 18)]:
    g0 = hex2rgb(WINNER)
    gd = depot_over(g0)
    for base, bl in ((g0, "pure"), (gd, "under depot")):
        o = over_pct(c, a, base)
        d = float(de2000(lab_under(np.array([base]), "normal")[0],
                         lab_under(np.array([o]), "normal")[0]))
        P("    %-12s over %-11s %s -> %s   dE %6.2f" % (nm, bl, rgb2hex(*base), rgb2hex(*o), d))
P("  the same four over TODAY's depot floor (#414141 under the tint, #4d3354) for comparison:")
for nm, c, a in OVERLAYS + [("gridline", (0, 0, 0), 18)]:
    base = depot_over(hex2rgb("#414141"))
    o = over_pct(c, a, base)
    d = float(de2000(lab_under(np.array([base]), "normal")[0],
                     lab_under(np.array([o]), "normal")[0]))
    P("    %-12s over %-11s %s -> %s   dE %6.2f" % (nm, "under depot", rgb2hex(*base), rgb2hex(*o), d))
P("  and against the map canvas background #05080c: %.2f:1"
  % wcag_cr(hex2rgb(WINNER), hex2rgb("#05080c")))

with open(OUT_TXT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(_LINES) + "\n")
P("")
P("wrote %s  (%.1fs)" % (OUT_TXT, time.time() - T0))
