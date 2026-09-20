# -*- coding: utf-8 -*-
"""Colour-difference instrument "a" (basemark round).

Pure math, numpy only. No simulation, no model import. Reads two tracked source
files as TEXT (common_fixed_variables.py, serve_dashboard.py) to verify the
palette literals, and outputs/_sc_deltae.py as TEXT to lift its 9 Sharma pairs.

Pipeline
  sRGB 8-bit -> linear RGB (IEC 61966-2-1) -> [vision-condition transform in
  linear RGB, clipped to [0,1]] -> XYZ (D65, 2-degree, Lindbloom sRGB matrix)
  -> CIELAB (white = matrix * (1,1,1), so greys are exactly neutral)
  -> CIEDE2000 (kL=kC=kH=1).
Vision conditions
  normal; protanopia / deuteranopia / tritanopia = Machado, Oliveira & Fernandes
  2009 matrices at severity 1.0; achromatic = grey of Rec.709 relative luminance.
  No 8-bit re-quantisation after simulation.

Writes its full stdout to outputs/_bm_colour_a.txt (UTF-8) from Python.
"""
import ast
import json
import math
import re
import sys
import time

import numpy as np

ROOT = "E:/Projects/SAS"
OUT_TXT = ROOT + "/outputs/_bm_colour_a.txt"
T0 = time.time()
_LINES = []


def P(s=""):
    s = str(s)
    _LINES.append(s)
    print(s)
    sys.stdout.flush()


def hex2rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb2hex(r, g, b):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


# ----------------------------------------------------------------------------
# colour math
# ----------------------------------------------------------------------------
M_RGB2XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                      [0.2126729, 0.7151522, 0.0721750],
                      [0.0193339, 0.1191920, 0.9503041]])
WHITE = M_RGB2XYZ.sum(axis=1)          # XYZ of linear (1,1,1) = D65 to 1e-7
REC709 = np.array([0.2126, 0.7152, 0.0722])
EPS = 216.0 / 24389.0
KAPPA = 24389.0 / 27.0

MACHADO = {
    "protanopia": np.array([[0.152286, 1.052583, -0.204868],
                            [0.114503, 0.786281, 0.099216],
                            [-0.003882, -0.048116, 1.051998]]),
    "deuteranopia": np.array([[0.367322, 0.860646, -0.227968],
                              [0.280085, 0.672501, 0.047413],
                              [-0.011820, 0.042940, 0.968881]]),
    "tritanopia": np.array([[1.255528, -0.076749, -0.178779],
                            [-0.078411, 0.930809, 0.147602],
                            [0.004733, 0.691367, 0.303900]]),
}
CONDS = ["normal", "protanopia", "deuteranopia", "tritanopia", "achromatic"]
CSHORT = {"normal": "norm", "protanopia": "prot", "deuteranopia": "deut",
          "tritanopia": "trit", "achromatic": "achr"}


def srgb_to_linear(rgb):
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _f(t):
    return np.where(t > EPS, np.cbrt(t), (KAPPA * t + 16.0) / 116.0)


def linear_to_lab(lin):
    xyz = lin @ M_RGB2XYZ.T
    f = _f(xyz / WHITE)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    small = np.hypot(a, b) < 1e-9        # float noise on exact greys -> exact 0
    a = np.where(small, 0.0, a)
    b = np.where(small, 0.0, b)
    return np.stack([L, a, b], axis=-1)


def linear_to_srgb8(lin):
    lin = np.clip(lin, 0.0, 1.0)
    e = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1.0 / 2.4) - 0.055)
    return np.floor(255.0 * e + 0.5)


def lab_under(rgb, cond, q8=False):
    """rgb: (n,3) 8-bit sRGB. Returns (n,3) Lab as seen under `cond`.
    q8=False (PRIMARY, the task's definition): simulate in linear RGB, clip, straight to Lab.
    q8=True  (reconciliation only): re-quantise the simulated colour to 8-bit sRGB first, as a
             renderer that paints the simulation would."""
    lin = srgb_to_linear(rgb)
    if cond == "normal":
        return linear_to_lab(lin)
    if cond == "achromatic":
        Y = lin @ REC709
        if q8:
            Y = srgb_to_linear(linear_to_srgb8(Y))
        L = 116.0 * _f(Y) - 16.0
        z = np.zeros_like(L)
        return np.stack([L, z, z], axis=-1)
    sim = np.clip(lin @ MACHADO[cond].T, 0.0, 1.0)
    if q8:
        sim = srgb_to_linear(linear_to_srgb8(sim))
    return linear_to_lab(sim)


def de2000(lab1, lab2):
    """Vectorised CIEDE2000, broadcasting over leading dims. kL=kC=kH=1."""
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cb7 = ((C1 + C2) / 2.0) ** 7
    G = 0.5 * (1.0 - np.sqrt(Cb7 / (Cb7 + 25.0 ** 7)))
    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2
    C1p = np.hypot(a1p, b1)
    C2p = np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360.0
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360.0
    dLp = L2 - L1
    dCp = C2p - C1p
    prod = C1p * C2p
    dh = h2p - h1p
    dhp = np.where(prod == 0.0, 0.0,
                   np.where(np.abs(dh) <= 180.0, dh,
                            np.where(dh > 180.0, dh - 360.0, dh + 360.0)))
    dHp = 2.0 * np.sqrt(prod) * np.sin(np.radians(dhp) / 2.0)
    Lbp = (L1 + L2) / 2.0
    Cbp = (C1p + C2p) / 2.0
    hs = h1p + h2p
    hbp = np.where(prod == 0.0, hs,
                   np.where(np.abs(h1p - h2p) <= 180.0, hs / 2.0,
                            np.where(hs < 360.0, (hs + 360.0) / 2.0,
                                     (hs - 360.0) / 2.0)))
    T = (1.0 - 0.17 * np.cos(np.radians(hbp - 30.0))
         + 0.24 * np.cos(np.radians(2.0 * hbp))
         + 0.32 * np.cos(np.radians(3.0 * hbp + 6.0))
         - 0.20 * np.cos(np.radians(4.0 * hbp - 63.0)))
    dth = 30.0 * np.exp(-(((hbp - 275.0) / 25.0) ** 2))
    Cbp7 = Cbp ** 7
    Rc = 2.0 * np.sqrt(Cbp7 / (Cbp7 + 25.0 ** 7))
    Sl = 1.0 + 0.015 * (Lbp - 50.0) ** 2 / np.sqrt(20.0 + (Lbp - 50.0) ** 2)
    Sc = 1.0 + 0.045 * Cbp
    Sh = 1.0 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2.0 * dth)) * Rc
    q = ((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
         + Rt * (dCp / Sc) * (dHp / Sh))
    return np.sqrt(np.maximum(q, 0.0))


def de2000_scalar(l1, l2):
    """Independent scalar transcription (math only) - cross-checks the vector one."""
    L1, a1, b1 = l1
    L2, a2, b2 = l2
    C1 = math.sqrt(a1 * a1 + b1 * b1)
    C2 = math.sqrt(a2 * a2 + b2 * b2)
    Cm = 0.5 * (C1 + C2)
    G = 0.5 * (1.0 - math.sqrt(Cm ** 7 / (Cm ** 7 + 6103515625.0)))
    ap1 = a1 * (1.0 + G)
    ap2 = a2 * (1.0 + G)
    Cp1 = math.sqrt(ap1 * ap1 + b1 * b1)
    Cp2 = math.sqrt(ap2 * ap2 + b2 * b2)

    def hue(bb, aa):
        if bb == 0.0 and aa == 0.0:
            return 0.0
        h = math.degrees(math.atan2(bb, aa))
        return h + 360.0 if h < 0.0 else h
    hp1 = hue(b1, ap1)
    hp2 = hue(b2, ap2)
    dL = L2 - L1
    dC = Cp2 - Cp1
    if Cp1 * Cp2 == 0.0:
        dh = 0.0
    else:
        dh = hp2 - hp1
        if dh > 180.0:
            dh -= 360.0
        elif dh < -180.0:
            dh += 360.0
    dH = 2.0 * math.sqrt(Cp1 * Cp2) * math.sin(math.radians(dh / 2.0))
    Lm = 0.5 * (L1 + L2)
    Cpm = 0.5 * (Cp1 + Cp2)
    if Cp1 * Cp2 == 0.0:
        hm = hp1 + hp2
    elif abs(hp1 - hp2) <= 180.0:
        hm = 0.5 * (hp1 + hp2)
    elif hp1 + hp2 < 360.0:
        hm = 0.5 * (hp1 + hp2 + 360.0)
    else:
        hm = 0.5 * (hp1 + hp2 - 360.0)
    T = (1.0 - 0.17 * math.cos(math.radians(hm - 30.0))
         + 0.24 * math.cos(math.radians(2.0 * hm))
         + 0.32 * math.cos(math.radians(3.0 * hm + 6.0))
         - 0.20 * math.cos(math.radians(4.0 * hm - 63.0)))
    dtheta = 30.0 * math.exp(-(((hm - 275.0) / 25.0) ** 2))
    RC = 2.0 * math.sqrt(Cpm ** 7 / (Cpm ** 7 + 6103515625.0))
    SL = 1.0 + (0.015 * (Lm - 50.0) ** 2) / math.sqrt(20.0 + (Lm - 50.0) ** 2)
    SC = 1.0 + 0.045 * Cpm
    SH = 1.0 + 0.015 * Cpm * T
    RT = -math.sin(math.radians(2.0 * dtheta)) * RC
    return math.sqrt(max(0.0, (dL / SL) ** 2 + (dC / SC) ** 2 + (dH / SH) ** 2
                         + RT * (dC / SC) * (dH / SH)))


def wcag_lum(rgb):
    return float(srgb_to_linear(np.array(rgb, dtype=float)) @ REC709)


def wcag_cr(rgb1, rgb2):
    l1, l2 = wcag_lum(rgb1), wcag_lum(rgb2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


class Pal(object):
    def __init__(self, entries):
        self.hex = [h for h, _ in entries]
        self.name = [n for _, n in entries]
        self.idx = {h: i for i, h in enumerate(self.hex)}
        assert len(self.idx) == len(self.hex), "palette has duplicate hex"
        self.rgb = np.array([hex2rgb(h) for h in self.hex], dtype=np.int64)
        self.lab = {c: lab_under(self.rgb, c) for c in CONDS}
        self.lab_q8 = {c: lab_under(self.rgb, c, q8=True) for c in CONDS}

    def __len__(self):
        return len(self.hex)


def lab1(hexv, cond):
    return lab_under(np.array([hex2rgb(hexv)]), cond)[0]


def min_vs(pal, hexv, cond, exclude_self):
    d = de2000(lab1(hexv, cond)[None, :], pal.lab[cond])
    if exclude_self and hexv in pal.idx:
        d = d.copy()
        d[pal.idx[hexv]] = np.inf
    i = int(np.argmin(d))
    return float(d[i]), i


def worst_vs(pal, hexv, exclude_self):
    """min over palette under each condition; returns (worst value, cond, idx, per-cond dict)."""
    per = {}
    for c in CONDS:
        per[c] = min_vs(pal, hexv, c, exclude_self)
    wc = min(CONDS, key=lambda c: per[c][0])
    return per[wc][0], wc, per[wc][1], per


# grid of the exhaustive sweep
VALS = np.arange(0, 256, 5)
_g = np.stack(np.meshgrid(VALS, VALS, VALS, indexing="ij"), axis=-1).reshape(-1, 3)
GRID_RGB = _g.astype(np.int64)
NGRID = GRID_RGB.shape[0]


def grid_index(rgb):
    r, g, b = rgb
    if r % 5 or g % 5 or b % 5:
        return None
    return (r // 5) * 52 * 52 + (g // 5) * 52 + (b // 5)


def sweep_min(pal, cond, exclude_self=False, drop_hex=(), chunk=512, q8=False):
    """For every grid colour: min dE2000 vs the palette under `cond` (+ argmin)."""
    labX = lab_under(GRID_RGB, cond, q8=q8)
    labP = (pal.lab_q8 if q8 else pal.lab)[cond]
    keep = np.array([h not in drop_hex for h in pal.hex])
    self_col = np.full(NGRID, -1, dtype=np.int64)
    if exclude_self:
        for h, i in pal.idx.items():
            gi = grid_index(hex2rgb(h))
            if gi is not None:
                self_col[gi] = i
    mins = np.empty(NGRID)
    args = np.empty(NGRID, dtype=np.int64)
    for s in range(0, NGRID, chunk):
        e = min(NGRID, s + chunk)
        d = de2000(labX[s:e, None, :], labP[None, :, :])
        if not keep.all():
            d[:, ~keep] = np.inf
        sc = self_col[s:e]
        rows = np.nonzero(sc >= 0)[0]
        if rows.size:
            d[rows, sc[rows]] = np.inf
        args[s:e] = d.argmin(axis=1)
        mins[s:e] = d[np.arange(e - s), args[s:e]]
    return mins, args


def topk(score, k, mask=None):
    sc = score.copy()
    if mask is not None:
        sc[~mask] = -np.inf
    order = np.argsort(-sc, kind="stable")[:k]
    return [int(i) for i in order if np.isfinite(sc[i])]


# ============================================================================
P("=" * 78)
P("COLOUR INSTRUMENT a  -  outputs/_bm_colour_a.py")
P("python %s | numpy %s" % (sys.version.split()[0], np.__version__))
P("=" * 78)

# ---- 0. self-checks --------------------------------------------------------
P("\n[0] SELF-CHECKS")
for k, m in MACHADO.items():
    rs = m.sum(axis=1)
    P("  Machado 2009 %-12s severity 1.0 row sums = %s  (must be 1: greys and white are fixed points)"
      % (k, np.array2string(rs, precision=6)))
    assert np.all(np.abs(rs - 1.0) < 2e-6)
P("  XYZ white used (matrix * (1,1,1)) = %s  (nominal D65 0.95047 1.00000 1.08883)"
  % np.array2string(WHITE, precision=7))
for hx, exp in (("#ffffff", (100.0, 0.0, 0.0)), ("#000000", (0.0, 0.0, 0.0)),
                ("#ff0000", (53.24, 80.09, 67.20)), ("#00ff00", (87.73, -86.18, 83.18)),
                ("#0000ff", (32.30, 79.19, -107.86))):
    got = lab1(hx, "normal")
    P("  Lab(%s) = (%.4f, %.4f, %.4f)   textbook (%.2f, %.2f, %.2f)"
      % ((hx,) + tuple(got) + exp))
    assert max(abs(got[i] - exp[i]) for i in range(3)) < 0.02, hx
rng = np.random.RandomState(12345)
A = np.column_stack([rng.uniform(0, 100, 4000), rng.uniform(-128, 128, 4000), rng.uniform(-128, 128, 4000)])
B = np.column_stack([rng.uniform(0, 100, 4000), rng.uniform(-128, 128, 4000), rng.uniform(-128, 128, 4000)])
A[:200, 1:] = 0.0            # exercise the C'=0 branches
B[100:300, 1:] = 0.0
dv = de2000(A, B)
ds = np.array([de2000_scalar(tuple(A[i]), tuple(B[i])) for i in range(len(A))])
P("  vectorised vs independent scalar CIEDE2000 on 4000 random Lab pairs (400 with C=0): max |diff| = %.2e"
  % np.max(np.abs(dv - ds)))
assert np.max(np.abs(dv - ds)) < 1e-9
dsym = de2000(B, A)
P("  symmetry dE(a,b)-dE(b,a): max |diff| = %.2e" % np.max(np.abs(dv - dsym)))

# ---- 1. Sharma validation --------------------------------------------------
P("\n[1] CIEDE2000 VALIDATION - Sharma, Wu & Dalal (2005) test data")
SHARMA = [
    (1, (50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    (2, (50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    (3, (50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
    (4, (50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
    (5, (50.0000, -1.1848, -84.8006), (50.0000, 0.0000, -82.7485), 1.0000),
    (6, (50.0000, -0.9009, -85.5211), (50.0000, 0.0000, -82.7485), 1.0000),
    (7, (50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
    (8, (50.0000, -1.0000, 2.0000), (50.0000, 0.0000, 0.0000), 2.3669),
    (9, (50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0009), 7.1792),
    (10, (50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0010), 7.1792),
    (11, (50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0011), 7.2195),
    (12, (50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0012), 7.2195),
    (13, (50.0000, -0.0010, 2.4900), (50.0000, 0.0009, -2.4900), 4.8045),
    (14, (50.0000, -0.0010, 2.4900), (50.0000, 0.0010, -2.4900), 4.8045),
    (15, (50.0000, -0.0010, 2.4900), (50.0000, 0.0011, -2.4900), 4.7461),
    (16, (50.0000, 2.5000, 0.0000), (50.0000, 0.0000, -2.5000), 4.3065),
    (17, (50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    (18, (50.0000, 2.5000, 0.0000), (61.0000, -5.0000, 29.0000), 22.8977),
    (19, (50.0000, 2.5000, 0.0000), (56.0000, -27.0000, -3.0000), 31.9030),
    (20, (50.0000, 2.5000, 0.0000), (58.0000, 24.0000, 15.0000), 19.4535),
    (21, (50.0000, 2.5000, 0.0000), (50.0000, 3.1736, 0.5854), 1.0000),
    (22, (50.0000, 2.5000, 0.0000), (50.0000, 3.2972, 0.0000), 1.0000),
    (23, (50.0000, 2.5000, 0.0000), (50.0000, 1.8634, 0.5757), 1.0000),
    (24, (50.0000, 2.5000, 0.0000), (50.0000, 3.2592, 0.3350), 1.0000),
    (25, (60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    (26, (63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    (27, (61.2901, 3.7196, -5.3901), (61.4292, 2.2480, -4.9620), 1.8731),
    (28, (35.0831, -44.1164, 3.7933), (35.0232, -40.0716, 1.5901), 1.8645),
    (29, (22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    (30, (36.4612, 47.8580, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
    (31, (90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    (32, (90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    (33, (6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
    (34, (2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]
# the 9 pairs of outputs/_sc_deltae.py, lifted from its source text
_sc_src = open(ROOT + "/outputs/_sc_deltae.py", "r", encoding="utf-8").read()
_m = re.search(r"^REF\s*=\s*(\[.*?\])\s*^worst", _sc_src, re.S | re.M)
SC_REF = ast.literal_eval(_m.group(1))
P("  pairs lifted from outputs/_sc_deltae.py REF: %d" % len(SC_REF))
sc_in_sharma = 0
for a_, b_, e_ in SC_REF:
    hit = [n for n, x, y, e in SHARMA if x == tuple(a_) and y == tuple(b_) and abs(e - e_) < 1e-12]
    sc_in_sharma += bool(hit)
P("  of those, present verbatim in my 34-row table: %d" % sc_in_sharma)
P("  PROTOCOL: the 34 rows below were written down ONCE from memory and never edited after a run.")
P("  A row is ACCEPTED only if it reproduces the published dE00 to 1e-4 in BOTH implementations and")
P("  in both argument orders; a failing row is DROPPED and reported, not tuned. (A mis-remembered digit")
P("  in any of 6 inputs at 4 dp cannot reproduce a 4-dp published value by accident, so a pass also")
P("  certifies the recall.)")
P("   #   got(vector)   published   |err|      scalar-vector  status")
n_ok, worst_err, dropped = 0, 0.0, []
for n, x, y, e in SHARMA:
    gv = float(de2000(np.array(x), np.array(y)))
    gr = float(de2000(np.array(y), np.array(x)))
    gs = de2000_scalar(x, y)
    err = max(abs(gv - e), abs(gr - e), abs(gs - e))
    ok = err < 1e-4
    if ok:
        n_ok += 1
        worst_err = max(worst_err, err)
    else:
        dropped.append(n)
    P("  %2d   %10.6f   %9.4f   %.2e   %+.1e       %s" % (n, gv, e, err, gs - gv, "ok" if ok else "DROPPED"))
worst9 = max(abs(float(de2000(np.array(a_), np.array(b_))) - e_) for a_, b_, e_ in SC_REF)
P("  RESULT: %d of 34 rows reproduce to 1e-4 (worst |err| over accepted rows %.2e); dropped rows: %s"
  % (n_ok, worst_err, dropped if dropped else "none"))
P("  the 9 _sc_deltae.py pairs: worst |err| %.2e (that script reported 4.17e-05)" % worst9)
P("  EXTERNAL CORROBORATION (2026-09-19, by web fetch AFTER the table was frozen; not re-checkable offline):")
P("  all 34 rows equal G. Sharma's published ciede2000testdata.txt (hajim.rochester.edu/ece/sites/gsharma/")
P("  ciede2000/dataNprograms/), and the three Machado severity-1.0 matrices equal the severity-100 entries of")
P("  colorspacious/cvd.py (github.com/njsmith/colorspacious). No row or coefficient was changed as a result.")
SHARMA_OK, SHARMA_WORST = n_ok, worst_err

# ---- 2. vision conditions ---------------------------------------------------
P("\n[2] VISION CONDITIONS")
P("  normal | protanopia, deuteranopia, tritanopia = Machado/Oliveira/Fernandes 2009, severity 1.0,")
P("  applied to LINEAR RGB then clipped to [0,1] | achromatic = R=G=B=Y(Rec.709: .2126 .7152 .0722).")
P("  No 8-bit re-quantisation between simulation and Lab.")
for hx in ("#770099", "#fe0101", "#1c630b"):
    row = []
    for c in CONDS:
        l_ = lab1(hx, c)
        row.append("%s (%.1f,%.1f,%.1f)" % (CSHORT[c], l_[0], l_[1], l_[2]))
    P("  %s -> %s" % (hx, "  ".join(row)))

# ---- 3. palette verification -----------------------------------------------
P("\n[3] PALETTE N50 - verified against the source text at the working tree (== HEAD for tracked files)")
cfv_src = open(ROOT + "/common_fixed_variables.py", "r", encoding="utf-8").read()
sd_src = open(ROOT + "/serve_dashboard.py", "r", encoding="utf-8").read()
cfv_lines = cfv_src.splitlines()
sd_lines = sd_src.splitlines()


def parse_list(src, name):
    m = re.search(r"^" + name + r"\s*=\s*(\[[^\]]*\])", src, re.M)
    ln = src[:m.start()].count("\n") + 1
    return [s.lower() for s in ast.literal_eval(m.group(1))], ln


VEG, ln_veg = parse_list(cfv_src, "VEGETATION_COLORS")
FIRE, ln_fire = parse_list(cfv_src, "FIRE_COLORS")
SMOKE, ln_smoke = parse_list(cfv_src, "SMOKE_COLORS")
BW, ln_bw = parse_list(cfv_src, "BLACK_AND_WHITE_COLORS")
P("  common_fixed_variables.py:%d VEGETATION_COLORS (%d)  :%d FIRE_COLORS (%d)  :%d SMOKE_COLORS (%d)  :%d BLACK_AND_WHITE_COLORS (%d)"
  % (ln_veg, len(VEG), ln_fire, len(FIRE), ln_smoke, len(SMOKE), ln_bw, len(BW)))
_mjs = re.search(r"const BW=(\[[^\]]*\]);", sd_src)
JS_BW = [s.lower() for s in ast.literal_eval(_mjs.group(1))]
P("  serve_dashboard.py:%d JS BW ramp == cfv BLACK_AND_WHITE_COLORS: %s"
  % (sd_src[:_mjs.start()].count("\n") + 1, JS_BW == BW))


def sd_find(lit):
    return [i + 1 for i, l in enumerate(sd_lines) if lit.lower() in l.lower()]


SD_LITS = [("#2b2b2b", "burnt"), ("#895e00", "scorched"), ("#2f4a1a", "spared veg"),
           ("#00FFFF", "UAV victim_searcher"), ("#FF00FF", "UAV fire_tracker"),
           ("#0066CC", "UAV relay"), ("#FF8C00", "UAV victim_confirmer"),
           ("#888888", "UAV return_to_base"), ("#FFFF00", "victim candidate"),
           ("#FFA500", "victim confirmed"), ("#00AAFF", "victim assigned/rescued"),
           ("#00FFCC", "firefighter"), ("rgba(119,0,153,0.22)", "depot fill = #770099 @0.22"),
           ("strokeStyle='#770099'", "depot outline"), ("rgba(0,255,204,0.35)", "ff trail = #00ffcc @0.35"),
           ("rgba(120,170,255,0.30)", "uav trail = #78aaff @0.30"),
           ("rgba(255,215,90,0.8)", "assignment line = #ffd75a @0.8"),
           ("rgba(255,215,90,0.9)", "assignment dot = #ffd75a @0.9"),
           ("rgba(0,0,0,0.18)", "gridline black @0.18"),
           ("strokeStyle='#000000'", "FOV frame casing"), ("strokeStyle='#FFFFFF'", "FOV frame core")]
for lit, what in SD_LITS:
    lns = sd_find(lit)
    P("  serve_dashboard.py:%-18s %-26s %s" % (",".join(map(str, lns[:4])), lit, what))
    assert lns, lit
assert rgb2hex(119, 0, 153) == "#770099" and rgb2hex(120, 170, 255) == "#78aaff"
assert rgb2hex(255, 215, 90) == "#ffd75a" and rgb2hex(0, 255, 204) == "#00ffcc"

raw = []
for i, c in enumerate(VEG):
    raw.append((c, "VEG[%d]" % i))
for i, c in enumerate(FIRE):
    raw.append((c, "FIRE[%d]" % i))
raw.append((SMOKE[0], "smoke"))
raw += [("#2b2b2b", "burnt"), ("#895e00", "scorched"), ("#2f4a1a", "spared")]
for i, c in enumerate(BW):
    raw.append((c, "BW[%d]" % i))
raw += [("#00ffff", "UAV searcher"), ("#ff00ff", "UAV tracker"), ("#0066cc", "UAV relay"),
        ("#ff8c00", "UAV confirmer"), ("#888888", "UAV RTB"), ("#000000", "UAV fallback/dead victim/dead ff/UAV stroke"),
        ("#ffff00", "victim candidate"), ("#ffa500", "victim confirmed"), ("#00aaff", "victim assigned"),
        ("#00aaff", "victim rescued"), ("#00ffcc", "firefighter"), ("#770099", "depot"),
        ("#ffd75a", "assignment"), ("#00ffcc", "trail ff"), ("#78aaff", "trail uav"),
        ("#1c630b", "canvas bg normal mode"), ("#ffffff", "canvas bg prob mode")]
seen, n50, dups = {}, [], []
for h, n in raw:
    if h in seen:
        dups.append("%s %s == %s" % (h, n, seen[h]))
    else:
        seen[h] = n
        n50.append((h, n))
N50 = Pal(n50)
TASK_N50 = ("#414141 #9eff89 #85e370 #72d05c #62c14c #459f30 #389023 #2f831b #236f11 #1c630b #175808 #124b05 "
            "#d8d675 #eae740 #fefa01 #fed401 #feaa01 #fe7001 #fe5501 #fe3e01 #fe2f01 #fe2301 #fe0101 "
            "#ababab #2b2b2b #895e00 #2f4a1a "
            "#ffffff #e6e6e6 #c9c9c9 #b1b1b1 #a1a1a1 #818181 #636363 #474747 #303030 #1a1a1a #000000 "
            "#00ffff #ff00ff #0066cc #ff8c00 #888888 #ffff00 #ffa500 #00aaff #00ffcc #770099 #ffd75a #78aaff").split()
P("  nominal entries enumerated from source: %d ; DISTINCT: %d ; task list distinct: %d ; sets equal: %s"
  % (len(raw), len(N50), len(set(TASK_N50)), set(TASK_N50) == set(N50.hex)))
P("  duplicates folded (%d): %s" % (len(dups), "; ".join(dups)))
assert set(TASK_N50) == set(N50.hex)
Lsorted = sorted(N50.lab["normal"][:, 0])
gaps = np.diff(Lsorted)
P("  N50 L* values: %d distinct (2dp), mean spacing %.2f, largest gap %.2f   (earlier round: 50 distinct, 2.04, 9.26)"
  % (len(set(round(v, 2) for v in Lsorted)), gaps.mean(), gaps.max()))

# ---- 3a. flat sweep vs N50 --------------------------------------------------
P("\n[3a] EXHAUSTIVE FLAT SWEEP vs N50: grid {0,5,..,255}^3 = %d colours, score = min over N50, WORST of 5 conditions" % NGRID)
per_cond_min = {}
for c in CONDS:
    per_cond_min[c], _ = sweep_min(N50, c)
    i = int(np.argmax(per_cond_min[c]))
    P("  best under %-12s alone: %6.2f at %s" % (c, per_cond_min[c][i], rgb2hex(*GRID_RGB[i])))
stack = np.stack([per_cond_min[c] for c in CONDS], axis=0)
flat_score = stack.min(axis=0)
flat_wc = stack.argmin(axis=0)
top = topk(flat_score, 10)
P("  TOP 10 worst-condition scores:")
for i in top:
    P("    %s  %.4f  (binding condition %s; per-cond %s)"
      % (rgb2hex(*GRID_RGB[i]), flat_score[i], CONDS[flat_wc[i]],
         " ".join("%s=%.2f" % (CSHORT[c], per_cond_min[c][i]) for c in CONDS)))
FLAT_CEIL = float(flat_score[top[0]])
FLAT_HEX = rgb2hex(*GRID_RGB[top[0]])
gi = grid_index(hex2rgb("#00004b"))
P("  earlier round's colour #00004b on my instrument: worst-cond %.4f (%s)"
  % (flat_score[gi], " ".join("%s=%.2f" % (CSHORT[c], per_cond_min[c][gi]) for c in CONDS)))
P("  FLAT CEILING = %.2f dE2000 at %s   (earlier round: 2.73 near #00004b)" % (FLAT_CEIL, FLAT_HEX))

# ---- 3b. two-tone vs N50 ----------------------------------------------------
P("\n[3b] TWO-TONE MARK {#ffffff,#000000} vs N50: score(b) = max over tones; min over N50; worst condition")


def multitone(pal, tones):
    """returns dict cond -> (n_pal,) array of max-over-tones dE, and argmax tone."""
    out = {}
    for c in CONDS:
        d = np.stack([de2000(lab1(t, c)[None, :], pal.lab[c]) for t in tones], axis=0)
        out[c] = (d.max(axis=0), d.argmax(axis=0), d)
    return out


def multitone_report(pal, tones, label):
    mt = multitone(pal, tones)
    best = None
    for c in CONDS:
        sc = mt[c][0]
        i = int(np.argmin(sc))
        P("    %-12s min over %d entries = %7.4f at %s (%s) [tone %s]"
          % (c, len(pal), sc[i], pal.hex[i], pal.name[i], tones[int(mt[c][1][i])]))
        if best is None or sc[i] < best[0]:
            best = (float(sc[i]), c, pal.hex[i], pal.name[i])
    P("    => %s worst-condition min = %.2f  (%s, at %s %s)" % (label, best[0], best[1], best[2], best[3]))
    return best, mt


tt_best, tt_mt = multitone_report(N50, ["#ffffff", "#000000"], "two-tone vs N50")
TWO_TONE = tt_best[0]
for t in ("#ffffff", "#000000"):
    i = N50.idx[t]
    P("    palette entry %s (IN the palette): same tone scores %.4f, other tone %.4f -> entry score %.4f (normal)"
      % (t, float(tt_mt["normal"][2][0 if t == "#ffffff" else 1][i]),
         float(tt_mt["normal"][2][1 if t == "#ffffff" else 0][i]), float(tt_mt["normal"][0][i])))
P("    handling: NOTHING is excluded. A tone identical to a palette entry scores 0 for that tone, the")
P("    other tone scores ~100, and max() keeps the 100 - so the identities cannot bind the minimum.")
P("  TWO-TONE SCORE = %.2f   (earlier round: 38.37)" % TWO_TONE)
bw_pal = Pal([(h, "BW[%d]" % i) for i, h in enumerate(BW)])
P("  side check, two-tone vs the 11-step BW ramp only (earlier round quoted 40.32 'in probability mode'):")
multitone_report(bw_pal, ["#ffffff", "#000000"], "two-tone vs BW ramp")

# ---- 3c. other earlier-round numbers ---------------------------------------
P("\n[3c] OTHER EARLIER-ROUND NUMBERS RE-MEASURED (fovframe_part1.txt 4.2-4.4; cfv comment :507-516)")
for hx, note in (("#ff1493", "earlier: 16.59 normal, 0.63 worst-case"),
                 ("#990033", "earlier: 25.97 normal, 0.34 achromatic"),
                 ("#000000", "earlier: 5.52 worst-case with exact identities excluded"),
                 ("#c0c0c0", "earlier: 1.74 worst-case (a different 14-candidate probe)")):
    w, wc, wi, per = worst_vs(N50, hx, exclude_self=True)
    P("  %s vs N50 (self excluded): %s | worst %.2f (%s, %s)   [%s]"
      % (hx, " ".join("%s=%.2f" % (CSHORT[c], per[c][0]) for c in CONDS), w, wc, N50.hex[wi], note))
sc37 = Pal([(h, n) for h, n in n50 if h in set(VEG + FIRE + ["#ababab", "#2b2b2b", "#2f4a1a", "#00ffff", "#ff00ff",
            "#0066cc", "#ff8c00", "#888888", "#000000", "#ffff00", "#ffa500", "#00aaff", "#00ffcc", "#ffd75a"])])
d_, i_ = min_vs(sc37, "#895e00", "normal", True)
P("  #895e00 vs the %d-colour _sc_deltae.py set: %.2f (%s)   [that script prints 27.34 (#414141)]" % (len(sc37), d_, sc37.hex[i_]))
sc38 = Pal([(h, n) for h, n in zip(sc37.hex, sc37.name)] + [("#895e00", "scorched")])
d_, i_ = min_vs(sc38, "#770099", "normal", True)
P("  #770099 vs that set + #895e00 (%d): %.2f (%s)   [cfv comment: 28.76 over '39 co-occurring']" % (len(sc38), d_, sc38.hex[i_]))

# ---- 4. N+ ------------------------------------------------------------------
P("\n[3d] RECONCILIATION - every NORMAL-vision number above matches the earlier round to 2 dp; the ones that")
P("  differ (38.26 vs 38.37, 2.76 vs 2.73, 0.30 vs 0.34, 0.60 vs 0.63) are all bound by the ACHROMATIC condition.")
P("  Test: re-quantise each simulated colour to 8-bit sRGB before Lab ('q8'). NOT my primary definition.")
q8_min = {}
for c in CONDS:
    q8_min[c], _ = sweep_min(N50, c, q8=True)
q8_stack = np.stack([q8_min[c] for c in CONDS], axis=0)
q8_score = q8_stack.min(axis=0)
q8_top = topk(q8_score, 5)
for i in q8_top:
    P("    q8 flat sweep: %s  %.4f  (binding %s)"
      % (rgb2hex(*GRID_RGB[i]), q8_score[i], CONDS[int(q8_stack[:, i].argmin())]))
Q8_CEIL = float(q8_score[q8_top[0]])
Q8_HEX = rgb2hex(*GRID_RGB[q8_top[0]])
P("    q8 flat ceiling = %.2f at %s ; q8 score of #00004b = %.4f ; grid colours tied at the ceiling (|d|<1e-9): %d"
  % (Q8_CEIL, Q8_HEX, q8_score[grid_index(hex2rgb("#00004b"))], int((np.abs(q8_score - Q8_CEIL) < 1e-9).sum())))
q8_tt = None
for c in CONDS:
    d = np.stack([de2000(lab_under(np.array([hex2rgb(t)]), c, q8=True)[0][None, :], N50.lab_q8[c])
                  for t in ("#ffffff", "#000000")], axis=0).max(axis=0)
    i = int(np.argmin(d))
    if q8_tt is None or d[i] < q8_tt[0]:
        q8_tt = (float(d[i]), c, N50.hex[i])
P("    q8 two-tone vs N50 = %.2f (%s, at %s)   [earlier round 38.37]" % q8_tt)
Q8_TWO_TONE = q8_tt[0]
_ACH = {}
for hx, tgt in (("#ff1493", "0.63"), ("#990033", "0.34")):
    lx = lab_under(np.array([hex2rgb(hx)]), "achromatic", q8=True)[0]
    d = de2000(lx[None, :], N50.lab_q8["achromatic"])
    du = min_vs(N50, hx, "achromatic", True)[0]
    _ACH[hx] = (du, float(d.min()))
    P("    achromatic min of %s vs N50: unquantised %.2f, q8 %.2f (%s)   [earlier round %s]"
      % (hx, du, float(d.min()), N50.hex[int(d.argmin())], tgt))
_q8_ok = (round(Q8_CEIL, 2) == 2.73 and abs(q8_score[grid_index(hex2rgb("#00004b"))] - Q8_CEIL) < 1e-9
          and round(Q8_TWO_TONE, 2) == 38.37)
P("  READING (computed, not asserted): q8 reproduces the earlier 2.73-at-#00004b AND 38.37 exactly: %s." % _q8_ok)
P("  If True, the earlier instrument most likely measured an 8-bit RENDERED greyscale, and the 0.03 / 0.11 gaps")
P("  are that quantisation - not a CIEDE2000 or CVD-matrix disagreement. #990033's 0.34: q8 gives %.2f."
  % _ACH["#990033"][1])
P("  #ff1493's 0.63 is reproduced by NEITHER definition (%.2f unquantised / %.2f q8) - unexplained."
  % _ACH["#ff1493"])
P("  The earlier probe (_fov_palette.py, a session-scratchpad file per fovframe_part1.txt Appendix A) is not in")
P("  the repo, so its grey/CVD model cannot be inspected directly; this attribution is an inference from")
P("  matching numbers, not a reading of its code.")

# ---- 4. N+ (section header printed below) -----------------------------------
P("\n[4] PALETTE N+ = N50 + depot-fill composites + gridlined composites")
DEPOT = hex2rgb("#770099")


def over_pct(src, pct, dst):
    """source-over in sRGB byte space, alpha = pct/100, exact round-half-up."""
    return tuple((pct * s + (100 - pct) * d + 50) // 100 for s, d in zip(src, dst))


BASES = []
for i, c in enumerate(VEG):
    BASES.append((c, "VEG[%d]" % i))
for i, c in enumerate(FIRE[1:], start=1):
    BASES.append((c, "FIRE[%d]" % i))
BASES += [("#ababab", "smoke"), ("#2b2b2b", "burnt"), ("#895e00", "scorched"), ("#2f4a1a", "spared")]
for i, c in enumerate(BW):
    BASES.append((c, "BW[%d]" % i))
P("  base colours the depot fill can sit on: %d (12 VEG + 11 FIRE + smoke/burnt/scorched/spared + 11 BW)" % len(BASES))


def build_nplus(order):
    ents = list(n50)
    have = {h: n for h, n in ents}
    coll = []
    comp = {}
    for bh, bn in BASES:
        b = hex2rgb(bh)
        if order == "literal":      # gridline OVER (depot over base) - the task's wording
            c1 = over_pct(DEPOT, 22, b)
            c2 = over_pct((0, 0, 0), 18, c1)
        else:                        # canvas draw order: depot OVER (gridline over base)
            c1 = over_pct(DEPOT, 22, b)
            c2 = over_pct(DEPOT, 22, over_pct((0, 0, 0), 18, b))
        for cc, nm in ((c1, "depot/" + bn), (c2, "grid+depot/" + bn)):
            hx = rgb2hex(*cc)
            comp[nm] = hx
            if hx in have:
                coll.append("%s %s == %s" % (hx, nm, have[hx]))
            else:
                have[hx] = nm
                ents.append((hx, nm))
    return Pal(ents), comp, coll


NP, COMP, coll = build_nplus("literal")
P("  compositing: round-half-up of 0.22*src + 0.78*dst per 8-bit channel; gridline = 0.82*c (black @0.18)")
P("  PRIMARY N+ (task wording: gridline over the depot composite): %d distinct = 50 + %d new of %d composites"
  % (len(NP), len(NP) - 50, 2 * len(BASES)))
P("  collisions folded: %s" % ("; ".join(coll) if coll else "none"))
NPC, COMPC, collc = build_nplus("code")
P("  VARIANT N+code (actual canvas order serve_dashboard.py:746-749 then :764 - depot fill drawn OVER the")
P("  gridline): %d distinct; collisions: %s" % (len(NPC), "; ".join(collc) if collc else "none"))
P("  composites (primary):")
for bh, bn in BASES:
    P("    %-9s %s -> depot/ %s   grid+depot/ %s   (code-order gridline px: %s)"
      % (bn, bh, COMP["depot/" + bn], COMP["grid+depot/" + bn], COMPC["grid+depot/" + bn]))

# ---- 4a. candidates ---------------------------------------------------------
CANDS = ["#770099", "#ffffff", "#000000", "#990033", "#ff1493", "#c0c0c0", "#9933ff",
         "#b266ff", "#ff66ff", "#5500aa", "#aa00ff"]
P("\n[4a] FIELD CANDIDATES vs N+ (%d). 'excl' = X's own hex removed from the palette; 'incl' = not removed" % len(NP))
P("  hex      inN+  normal_min(excl) nearest                         worst_min(excl) cond  nearest                        | incl: normal worst | N+code: normal worst")
FIELD = []
for x in CANDS:
    inp = x in NP.idx
    dn, i_n = min_vs(NP, x, "normal", True)
    w, wc, wi, per = worst_vs(NP, x, True)
    dn_i, _ = min_vs(NP, x, "normal", False)
    w_i = worst_vs(NP, x, False)[0]
    dn_c, ic = min_vs(NPC, x, "normal", True)
    w_c = worst_vs(NPC, x, True)[0]
    P("  %s  %-4s  %7.2f  %-38s %7.2f  %-5s %-30s | %6.2f %6.2f | %6.2f %6.2f"
      % (x, "yes" if inp else "no", dn, "%s %s" % (NP.hex[i_n], NP.name[i_n]), w, CSHORT[wc],
         "%s %s" % (NP.hex[wi], NP.name[wi]), dn_i, w_i, dn_c, w_c))
    FIELD.append({"hex": x, "in_palette": inp, "normal_min": round(dn, 2),
                  "normal_nearest": NP.hex[i_n], "normal_nearest_name": NP.name[i_n],
                  "worst_min": round(w, 2), "worst_cond": wc, "worst_nearest": NP.hex[wi],
                  "normal_min_incl_self": round(dn_i, 2), "worst_min_incl_self": round(w_i, 2),
                  "per_cond": {CSHORT[c]: round(per[c][0], 2) for c in CONDS},
                  "codeorder_normal_min": round(dn_c, 2), "codeorder_worst_min": round(w_c, 2)})
P("  per-condition minima (excl self):")
for f in FIELD:
    P("    %s  %s" % (f["hex"], "  ".join("%s=%6.2f" % (k, v) for k, v in f["per_cond"].items())))

# ---- 4b. sweep vs N+ under normal vision ------------------------------------
P("\n[4b] EXHAUSTIVE SWEEP, best FIELD colour under NORMAL vision vs N+ (X itself excluded when X is in N+)")
np_min, np_arg = sweep_min(NP, "normal", exclude_self=True)
np_min_cond = {"normal": np_min}
labG = lab_under(GRID_RGB, "normal")
hG = np.degrees(np.arctan2(labG[:, 2], labG[:, 1])) % 360.0
cG = np.hypot(labG[:, 1], labG[:, 2])
ld = lab1("#770099", "normal")
H_DEPOT = math.degrees(math.atan2(ld[2], ld[1])) % 360.0
C_DEPOT = math.hypot(ld[1], ld[2])
P("  #770099 in CIELAB: L*=%.2f a*=%.2f b*=%.2f  C*ab=%.2f  h_ab=%.2f deg" % (ld[0], ld[1], ld[2], C_DEPOT, H_DEPOT))
dh = np.abs((hG - H_DEPOT + 180.0) % 360.0 - 180.0)
FAM = (dh <= 25.0) & (cG >= 40.0)
P("  family = |h_ab - %.2f| <= 25 deg AND C*ab >= 40: %d of %d grid colours" % (H_DEPOT, int(FAM.sum()), NGRID))


NOTPAL = np.ones(NGRID, dtype=bool)          # grid colours that are NOT themselves an N+ entry
for _h in NP.hex:
    _gi = grid_index(hex2rgb(_h))
    if _gi is not None:
        NOTPAL[_gi] = False
P("  grid colours that are themselves N+ entries: %d (%s)"
  % (int((~NOTPAL).sum()), " ".join(rgb2hex(*GRID_RGB[i]) for i in np.nonzero(~NOTPAL)[0])))


def list_top(title, idxs, score, arg, pal):
    P("  " + title)
    rows = []
    for r, i in enumerate(idxs, 1):
        x = rgb2hex(*GRID_RGB[i])
        w, wc, wi, _ = worst_vs(pal, x, True)
        inp = x in pal.idx
        P("    %2d. %s  normal_min %6.2f (nearest %s %s)  L*=%.1f C*=%.1f h=%.1f | worst-of-5 %.2f (%s)%s"
          % (r, x, score[i], pal.hex[arg[i]], pal.name[arg[i]], labG[i, 0], cG[i], hG[i], w, CSHORT[wc],
             ("   <-- IS the N+ entry '%s': exact identity, dE 0.00 if self is not excluded" % pal.name[pal.idx[x]]) if inp else ""))
        rows.append({"hex": x, "normal_min": round(float(score[i]), 2), "nearest": pal.hex[arg[i]],
                     "nearest_name": pal.name[arg[i]], "worst_min": round(w, 2), "worst_cond": wc,
                     "in_palette": inp, "L": round(float(labG[i, 0]), 1), "C": round(float(cG[i]), 1),
                     "h": round(float(hG[i]), 1)})
    return rows


BEST_ANY = list_top("TOP 10 OVERALL - LITERAL RULE (X excluded from N+ when X is an entry):",
                    topk(np_min, 10), np_min, np_arg, NP)
BEST_ANY_NP = list_top("TOP 10 OVERALL - palette members barred from candidacy:",
                       topk(np_min, 10, NOTPAL), np_min, np_arg, NP)
BEST_FAM = list_top("TOP 10 IN THE DEPOT HUE FAMILY - LITERAL RULE (scored vs all of N+, #770099 INCLUDED as an entry):",
                    topk(np_min, 10, FAM), np_min, np_arg, NP)
BEST_FAM_NP = list_top("TOP 10 IN THE FAMILY - palette members barred from candidacy:",
                       topk(np_min, 10, FAM & NOTPAL), np_min, np_arg, NP)
d77, i77 = min_vs(NP, "#770099", "normal", True)
rank77 = int((np_min[FAM] > d77).sum()) + 1
P("  #770099 itself (off-grid: 119 and 153 are not multiples of 5; self excluded): %.2f (nearest %s %s) -> would rank %d of %d in the family, %d of %d overall"
  % (d77, NP.hex[i77], NP.name[i77], rank77, int(FAM.sum()), int((np_min > d77).sum()) + 1, NGRID))
np_min2, np_arg2 = sweep_min(NP, "normal", exclude_self=True, drop_hex=("#770099",))
BEST_FAM2 = list_top("TOP 10 IN THE FAMILY, VARIANT - #770099 (the depot's own outline) dropped from N+ because a flag in the"
                     " depot's family is the SAME entity; palette members barred:",
                     topk(np_min2, 10, FAM & NOTPAL), np_min2, np_arg2, NP)
for r in BEST_FAM2:
    r["dE_to_770099"] = round(float(de2000(lab1(r["hex"], "normal"), lab1("#770099", "normal"))), 2)
P("    dE2000 of those to #770099: %s" % "  ".join("%s=%.2f" % (r["hex"], r["dE_to_770099"]) for r in BEST_FAM2))
npc_min, npc_arg = sweep_min(NPC, "normal", exclude_self=True)
tc = topk(npc_min, 3, NOTPAL)
tcf = topk(npc_min, 3, FAM & NOTPAL)
P("  sensitivity, N+code order (palette members barred): top-3 overall %s ; top-3 family %s"
  % (", ".join("%s %.2f" % (rgb2hex(*GRID_RGB[i]), npc_min[i]) for i in tc),
     ", ".join("%s %.2f" % (rgb2hex(*GRID_RGB[i]), npc_min[i]) for i in tcf)))

# ---- 4c. three-tone ---------------------------------------------------------
P("\n[4c] THREE-TONE MARK {#000000 casing, #ffffff keyline, X field} vs N+: entry score = max over the 3 tones")
SPECIFIC = ["#770099", "#ffffff", "#000000", "#2b2b2b", "#895e00", "#ababab", "#1c630b", "#124b05",
            "#fe0101", "#fefa01", "#ff00ff", "#00ffff", "#00ffcc", "#ffff00"]
THREE = {}
xs = ["#770099"]
XTAG = {"#770099": "depot colour"}
for _x, _t in ((BEST_FAM[0]["hex"], "best family colour, literal rule (4b)"),
               (BEST_FAM_NP[0]["hex"], "best family colour that is not itself a palette entry (4b)"),
               (BEST_FAM2[0]["hex"], "best family colour, #770099-dropped variant (4b)")):
    if _x not in xs:
        xs.append(_x)
        XTAG[_x] = _t
    else:
        XTAG[_x] += " == " + _t
P("  reference, TWO-TONE {#000000,#ffffff} vs N+:")
tt_np_best, tt_np = multitone_report(NP, ["#000000", "#ffffff"], "two-tone vs N+")
for x in xs:
    tones = ["#000000", "#ffffff", x]
    tag = XTAG[x]
    P("  X = %s  (%s)" % (x, tag))
    best, mt = multitone_report(NP, tones, "three-tone X=%s vs N+" % x)
    mtc = multitone(NPC, tones)
    wcode = min(float(mtc[c][0].min()) for c in CONDS)
    P("    (N+code order: worst-condition min = %.2f)" % wcode)
    ent = {}
    P("    specific entries:   entry      normal  [tone]      worst-of-5 (cond)   field-tone-alone normal / worst")
    for e in SPECIFIC:
        i = NP.idx[e]
        sn = float(mt["normal"][0][i])
        tn = tones[int(mt["normal"][1][i])]
        wcnd = min(CONDS, key=lambda c: float(mt[c][0][i]))
        sw = float(mt[wcnd][0][i])
        fn = float(mt["normal"][2][2][i])
        fw = min(float(mt[c][2][2][i]) for c in CONDS)
        P("      %-8s %-14s %7.2f  [%s]   %7.2f (%s)        %7.2f / %7.2f"
          % (e, NP.name[i][:14], sn, tn, sw, CSHORT[wcnd], fn, fw))
        ent[e] = {"normal": round(sn, 2), "worst": round(sw, 2), "worst_cond": wcnd,
                  "field_alone_normal": round(fn, 2), "field_alone_worst": round(fw, 2)}
    # how many entries does the field tone actually win?
    wins = int((mt["normal"][1] == 2).sum())
    P("    entries of N+ where the FIELD tone is the best of the three (normal vision): %d of %d" % (wins, len(NP)))
    THREE[x] = {"tag": tag, "in_palette": x in NP.idx, "worst_min": round(best[0], 2), "worst_cond": best[1], "argmin_entry": best[2],
                "argmin_name": best[3], "codeorder_worst_min": round(wcode, 2),
                "normal_min": round(float(mt["normal"][0].min()), 2),
                "field_wins_normal": wins, "entries": ent}
THREE["_two_tone_reference"] = {"worst_min": round(tt_np_best[0], 2), "worst_cond": tt_np_best[1],
                                "argmin_entry": tt_np_best[2]}

# ---- 4d. identity vs the FOV frame ------------------------------------------
P("\n[4d] MARK-vs-MARK IDENTITY against the two-tone FOV frame: identity(X) = min(dE(X,#ffffff), dE(X,#000000))")
P("  hex       " + "  ".join("%-6s" % CSHORT[c] for c in CONDS) + "  worst (cond)   [nearer frame tone, normal]")
IDENT = {}
for x in CANDS + [h for h in xs if h not in CANDS]:
    row = {}
    for c in CONDS:
        dw = float(de2000(lab1(x, c), lab1("#ffffff", c)))
        dk = float(de2000(lab1(x, c), lab1("#000000", c)))
        row[c] = (min(dw, dk), "#ffffff" if dw < dk else "#000000")
    wc = min(CONDS, key=lambda c: row[c][0])
    P("  %s   %s  %6.2f (%s)   [%s]" % (x, "  ".join("%6.2f" % row[c][0] for c in CONDS), row[wc][0], CSHORT[wc], row["normal"][1]))
    IDENT[x] = dict([(CSHORT[c], round(row[c][0], 2)) for c in CONDS] + [("worst", round(row[wc][0], 2)), ("worst_cond", wc)])

# ---- 4e. WCAG ---------------------------------------------------------------
P("\n[4e] WCAG 2.x CONTRAST RATIO of #ffffff / #000000 / #770099 against the depot-tinted ground")
WK = {"#ffffff": (255, 255, 255), "#000000": (0, 0, 0), "#770099": DEPOT}
wbases = [(c, "VEG[%d]" % i) for i, c in enumerate(VEG)] + [("#2b2b2b", "burnt"), ("#895e00", "scorched"), ("#ababab", "smoke")]
WCAG = {}
for kind in ("depot/", "grid+depot/", "bare "):
    P("  --- %s entries ---      hex       white    black    #770099   better(W/K)" % kind.strip())
    mn = (1e9, None)
    mn77 = (1e9, None)
    for bh, bn in wbases:
        hx = bh if kind == "bare " else COMP[kind + bn]
        rgb = hex2rgb(hx)
        cw, ck, c7 = wcag_cr(WK["#ffffff"], rgb), wcag_cr(WK["#000000"], rgb), wcag_cr(WK["#770099"], rgb)
        better = max(cw, ck)
        if better < mn[0]:
            mn = (better, "%s%s %s" % (kind, bn, hx))
        if c7 < mn77[0]:
            mn77 = (c7, "%s%s %s" % (kind, bn, hx))
        P("    %-22s %s  %6.2f   %6.2f   %6.2f    %6.2f (%s)" % (kind + bn, hx, cw, ck, c7, better, "W" if cw >= ck else "K"))
    P("    min over these %d of the BETTER of white/black = %.2f:1 at %s ; min #770099 = %.2f:1 at %s"
      % (len(wbases), mn[0], mn[1], mn77[0], mn77[1]))
    WCAG[kind.strip()] = {"min_better_wk": round(mn[0], 2), "at": mn[1], "min_770099": round(mn77[0], 2), "at_770099": mn77[1]}
_u = [WCAG["depot/"], WCAG["grid+depot/"]]
_ub = min(_u, key=lambda d: d["min_better_wk"])
_u7 = min(_u, key=lambda d: d["min_770099"])
P("  UNION of the 30 depot-tinted entries (depot/ + grid+depot/): min BETTER of white/black = %.2f:1 at %s ;"
  " min #770099 = %.2f:1 at %s" % (_ub["min_better_wk"], _ub["at"], _u7["min_770099"], _u7["at_770099"]))
WCAG["union_depot_tinted_30"] = {"min_better_wk": _ub["min_better_wk"], "at": _ub["at"],
                                 "min_770099": _u7["min_770099"], "at_770099": _u7["at_770099"]}
P("  #770099 vs #ffffff = %.2f:1 ; #770099 vs #000000 = %.2f:1 ; #ffffff vs #000000 = %.2f:1"
  % (wcag_cr(DEPOT, (255, 255, 255)), wcag_cr(DEPOT, (0, 0, 0)), wcag_cr((255, 255, 255), (0, 0, 0))))

# ---- result json ------------------------------------------------------------
RESULT = {
    "instrument": "a",
    "sharma_pairs_ok": SHARMA_OK, "sharma_worst_err": float("%.3g" % SHARMA_WORST),
    "flat_ceiling": round(FLAT_CEIL, 2), "flat_ceiling_colour": FLAT_HEX,
    "two_tone_score": round(TWO_TONE, 2), "two_tone_at": tt_best[2], "two_tone_cond": tt_best[1],
    "q8_reconciliation": {"flat_ceiling": round(Q8_CEIL, 2), "flat_ceiling_colour": Q8_HEX,
                          "two_tone_score": round(Q8_TWO_TONE, 2)},
    "n50_count": len(N50), "nplus_count": len(NP), "nplus_codeorder_count": len(NPC),
    "field_candidates": FIELD,
    "best_any": BEST_ANY[:3], "best_any_not_in_palette": BEST_ANY_NP[:3],
    "best_family": BEST_FAM[:3], "best_family_not_in_palette": BEST_FAM_NP[:3],
    "best_family_770099_dropped": BEST_FAM2[:3],
    "depot_hue_deg": round(H_DEPOT, 2), "depot_chroma": round(C_DEPOT, 2),
    "three_tone": THREE, "identity": IDENT, "wcag": WCAG,
}
P("\nRESULT_JSON_FULL=" + json.dumps(RESULT, separators=(",", ":"), sort_keys=False))


def _t3(rows):
    return [{"hex": r["hex"], "normal_min": r["normal_min"], "nearest": r["nearest"],
             "in_palette": r["in_palette"]} for r in rows[:3]]


COMPACT = {
    "flat_ceiling": RESULT["flat_ceiling"], "flat_ceiling_colour": FLAT_HEX,
    "two_tone_score": RESULT["two_tone_score"], "n50_count": len(N50), "nplus_count": len(NP),
    "q8": RESULT["q8_reconciliation"], "nplus_codeorder_count": len(NPC),
    "field_candidates": [{"hex": f["hex"], "normal_min": f["normal_min"], "normal_nearest": f["normal_nearest"],
                          "worst_min": f["worst_min"], "worst_cond": CSHORT[f["worst_cond"]],
                          "in_palette": f["in_palette"]} for f in FIELD],
    "best_any": _t3(BEST_ANY), "best_any_not_in_palette": _t3(BEST_ANY_NP),
    "best_family": _t3(BEST_FAM), "best_family_not_in_palette": _t3(BEST_FAM_NP),
    "best_family_770099_dropped": _t3(BEST_FAM2),
    "three_tone": dict((x, {"worst_min": v["worst_min"], "worst_cond": CSHORT[v["worst_cond"]],
                            "argmin": v["argmin_entry"], "field_wins_normal": v["field_wins_normal"],
                            "entries_normal_worst": dict((e, [w["normal"], w["worst"]])
                                                         for e, w in v["entries"].items())})
                       for x, v in THREE.items() if not x.startswith("_")),
    "two_tone_vs_nplus": THREE["_two_tone_reference"]["worst_min"],
    "identity": dict((x, [v[CSHORT[c]] for c in CONDS] + [v["worst"]]) for x, v in IDENT.items()),
    "identity_cols": [CSHORT[c] for c in CONDS] + ["worst"],
    "wcag_min_better_wk": {"depot": WCAG["depot/"]["min_better_wk"], "grid_depot": WCAG["grid+depot/"]["min_better_wk"],
                           "bare": WCAG["bare"]["min_better_wk"]},
    "wcag_min_770099": {"depot": WCAG["depot/"]["min_770099"], "grid_depot": WCAG["grid+depot/"]["min_770099"],
                        "bare": WCAG["bare"]["min_770099"]},
}
P("\nRESULT_JSON=" + json.dumps(COMPACT, separators=(",", ":"), sort_keys=False))
P("\nelapsed %.1f s" % (time.time() - T0))
with open(OUT_TXT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(_LINES) + "\n")
print("wrote " + OUT_TXT)
