# -*- coding: utf-8 -*-
"""_bm_colour_b.py - colour-difference instrument "b" (independent implementation).

Pure math + pure source reading. Never imports the model, never runs a simulation.
numpy only. Writes its full stdout to outputs/_bm_colour_b.txt (UTF-8) from Python.

Pipeline
  sRGB8 -> linear sRGB (IEC 61966-2-1) -> [vision simulation in LINEAR RGB, clip to
  gamut] -> XYZ (D65, 2-degree) -> CIELAB -> CIEDE2000 (kL=kC=kH=1).

Vision conditions
  normal
  protan / deutan : Vienot, Brettel & Mollon 1999 (single plane, published RGB->LMS
                    matrix for BT.709 primaries and the published projection constants)
  tritan          : Brettel, Vienot & Mollon 1997 (two half-planes, neutral E, anchors
                    485 nm and 660 nm), carried out in the same LMS space
  achrom          : grey of the Rec.709 relative luminance
"""
import ast
import json
import re
import sys
import time

import numpy as np

ROOT = "E:/Projects/SAS"
OUT_TXT = ROOT + "/outputs/_bm_colour_b.txt"
T0 = time.time()
_LINES = []


def out(s=""):
    s = str(s)
    _LINES.append(s)
    try:
        print(s, flush=True)
    except Exception:
        print(s.encode("ascii", "replace").decode("ascii"), flush=True)


# ----------------------------------------------------------------------------
# colour math
# ----------------------------------------------------------------------------
M_RGB2XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                      [0.2126729, 0.7151522, 0.0721750],
                      [0.0193339, 0.1191920, 0.9503041]])
WHITE_D65 = np.array([0.95047, 1.00000, 1.08883])


def hex2rgb(h):
    h = h.strip().lstrip("#").lower()
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb2hex(t):
    return "#%02x%02x%02x" % (int(t[0]), int(t[1]), int(t[2]))


def srgb8_to_lin(rgb8):
    c = np.asarray(rgb8, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_lab(lin):
    xyz = (lin @ M_RGB2XYZ.T) / WHITE_D65
    f = np.where(xyz > 216.0 / 24389.0, np.cbrt(xyz), (841.0 / 108.0) * xyz + 4.0 / 29.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


_25_7 = 25.0 ** 7


def _p7(x):
    x2 = x * x
    x4 = x2 * x2
    return x4 * x2 * x


def de2000(lab1, lab2):
    """Vectorised CIEDE2000 (Sharma, Wu & Dalal 2005 formulation), kL=kC=kH=1."""
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cb7 = _p7((C1 + C2) * 0.5)
    G = 0.5 * (1.0 - np.sqrt(Cb7 / (Cb7 + _25_7)))
    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2
    C1p = np.hypot(a1p, b1)
    C2p = np.hypot(a2p, b2)
    h1p = np.where(C1p == 0, 0.0, np.degrees(np.arctan2(b1, a1p)) % 360.0)
    h2p = np.where(C2p == 0, 0.0, np.degrees(np.arctan2(b2, a2p)) % 360.0)
    dLp = L2 - L1
    dCp = C2p - C1p
    CC = C1p * C2p
    dh = h2p - h1p
    dhp = np.where(np.abs(dh) <= 180.0, dh, np.where(dh > 180.0, dh - 360.0, dh + 360.0))
    dhp = np.where(CC == 0, 0.0, dhp)
    dHp = 2.0 * np.sqrt(CC) * np.sin(np.radians(dhp) * 0.5)
    Lbp = (L1 + L2) * 0.5
    Cbp = (C1p + C2p) * 0.5
    hs = h1p + h2p
    hbp = np.where(np.abs(h1p - h2p) <= 180.0, hs * 0.5,
                   np.where(hs < 360.0, (hs + 360.0) * 0.5, (hs - 360.0) * 0.5))
    hbp = np.where(CC == 0, hs, hbp)
    T = (1.0 - 0.17 * np.cos(np.radians(hbp - 30.0)) + 0.24 * np.cos(np.radians(2.0 * hbp))
         + 0.32 * np.cos(np.radians(3.0 * hbp + 6.0)) - 0.20 * np.cos(np.radians(4.0 * hbp - 63.0)))
    dth = 30.0 * np.exp(-(((hbp - 275.0) / 25.0) ** 2))
    Cbp7 = _p7(Cbp)
    Rc = 2.0 * np.sqrt(Cbp7 / (Cbp7 + _25_7))
    Lm = (Lbp - 50.0) ** 2
    Sl = 1.0 + 0.015 * Lm / np.sqrt(20.0 + Lm)
    Sc = 1.0 + 0.045 * Cbp
    Sh = 1.0 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2.0 * dth)) * Rc
    x = dCp / Sc
    y = dHp / Sh
    v = (dLp / Sl) ** 2 + x * x + y * y + Rt * x * y
    return np.sqrt(np.maximum(v, 0.0))


# ----------------------------------------------------------------------------
# vision simulation
# ----------------------------------------------------------------------------
# Vienot, Brettel & Mollon 1999: linear RGB (BT.709 primaries) -> LMS (Smith-Pokorny,
# Judd-Vos), and the two published projection rules.
M_V = np.array([[17.8824, 43.5161, 4.11935],
                [3.45565, 27.1554, 3.86714],
                [0.0299566, 0.184309, 1.46709]])
M_V_INV = np.linalg.inv(M_V)
PROTAN_K = (2.02344, -2.52581)   # L' = k0*M + k1*S
DEUTAN_K = (0.494207, 1.24827)   # M' = k0*L + k1*S

# Smith & Pokorny 1975 cone fundamentals from Judd-Vos XYZ'
SP = np.array([[0.15514, 0.54312, -0.03286],
               [-0.15514, 0.45684, 0.03286],
               [0.0, 0.0, 0.01608]])


def vos_xy(x, y):
    """Vos 1978 chromaticity transform CIE1931 (x,y) -> Judd-Vos (x',y')."""
    den = 0.03845 * x + 0.01496 * y + 1.0
    return ((1.0271 * x - 0.00008 * y - 0.00009) / den,
            (0.00376 * x + 1.0072 * y + 0.00764) / den)


def xyY_to_XYZ(x, y, Y=1.0):
    return np.array([x / y * Y, Y, (1.0 - x - y) / y * Y])


# CIE 1931 2-degree CMF rows at the two tritan anchor wavelengths (the Judd / Vos
# modification only alters the functions below ~460 nm).
CMF_485 = np.array([0.05795, 0.16930, 0.61620])
CMF_660 = np.array([0.16490, 0.06100, 0.00000])


def tritan_params(variant):
    """Return (E_lms, A485_lms, A660_lms); only DIRECTIONS matter (planes through 0)."""
    ex, ey = vos_xy(1.0 / 3.0, 1.0 / 3.0)
    E = SP @ xyY_to_XYZ(ex, ey)
    A485 = SP @ CMF_485
    A660 = SP @ CMF_660
    if variant == "V1":   # anchors pushed through the Vos chromaticity formula too
        s = CMF_485.sum(); x, y = vos_xy(CMF_485[0] / s, CMF_485[1] / s)
        A485 = SP @ xyY_to_XYZ(x, y)
        s = CMF_660.sum(); x, y = vos_xy(CMF_660[0] / s, CMF_660[1] / s)
        A660 = SP @ xyY_to_XYZ(x, y)
    elif variant == "V2":  # neutral axis = monitor white (D65) instead of E
        E = M_V @ np.ones(3)
    return E, A485, A660


def make_tritan(variant):
    E, A485, A660 = tritan_params(variant)
    n1 = np.cross(E, A485)
    n2 = np.cross(E, A660)

    def sim(lin):
        lms = lin @ M_V.T
        L, M = lms[..., 0], lms[..., 1]
        use660 = (M * E[0]) < (E[1] * L)          # M/L below the neutral's -> 660 nm half-plane
        S485 = -(n1[0] * L + n1[1] * M) / n1[2]
        S660 = -(n2[0] * L + n2[1] * M) / n2[2]
        lms2 = np.stack([L, M, np.where(use660, S660, S485)], axis=-1)
        return np.clip(lms2 @ M_V_INV.T, 0.0, 1.0)
    return sim


def sim_protan(lin):
    lms = lin @ M_V.T
    lms2 = np.stack([PROTAN_K[0] * lms[..., 1] + PROTAN_K[1] * lms[..., 2], lms[..., 1], lms[..., 2]], axis=-1)
    return np.clip(lms2 @ M_V_INV.T, 0.0, 1.0)


def sim_deutan(lin):
    lms = lin @ M_V.T
    lms2 = np.stack([lms[..., 0], DEUTAN_K[0] * lms[..., 0] + DEUTAN_K[1] * lms[..., 2], lms[..., 2]], axis=-1)
    return np.clip(lms2 @ M_V_INV.T, 0.0, 1.0)


def sim_achrom(lin):
    Y = lin @ np.array([0.2126, 0.7152, 0.0722])
    return np.clip(np.stack([Y, Y, Y], axis=-1), 0.0, 1.0)


CONDS = ["normal", "protan", "deutan", "tritan", "achrom"]
SIMS = {"normal": lambda lin: lin, "protan": sim_protan, "deutan": sim_deutan,
        "tritan": make_tritan("V0"), "achrom": sim_achrom}


def lab_of(rgb8, cond, sim=None):
    lin = srgb8_to_lin(np.asarray(rgb8, dtype=np.float64).reshape(-1, 3))
    f = sim if sim is not None else SIMS[cond]
    return lin_to_lab(f(lin))


def labs_all(rgb8):
    return {c: lab_of(rgb8, c) for c in CONDS}


def min_over_palette(labX, labP, rgbX=None, rgbP=None, chunk=4096):
    """min and argmin over the palette for every X; if rgbX/rgbP given, the entry with
    an identical sRGB triple is excluded (self-exclusion)."""
    n = labX.shape[0]
    mn = np.empty(n)
    am = np.empty(n, dtype=np.int64)
    for i in range(0, n, chunk):
        d = de2000(labX[i:i + chunk, None, :], labP[None, :, :])
        if rgbX is not None:
            same = (rgbX[i:i + chunk, None, :] == rgbP[None, :, :]).all(-1)
            d = np.where(same, np.inf, d)
        am[i:i + chunk] = d.argmin(1)
        mn[i:i + chunk] = d.min(1)
    return mn, am


# ============================================================================
out("=" * 100)
out("_bm_colour_b.py  - colour-difference instrument b   (numpy %s, python %s)" % (np.__version__, sys.version.split()[0]))
out("=" * 100)

# ----------------------------------------------------------------------------
# 1. CIEDE2000 validation
# ----------------------------------------------------------------------------
out("")
out("1. CIEDE2000 VALIDATION (Sharma, Wu & Dalal 2005, Table 1)")
out("-" * 100)
ANCHOR9 = [((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
           ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
           ((50.0, 2.5, 0.0), (50.0, 0.0, -2.5), 4.3065),
           ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
           ((50.0, 2.5, 0.0), (50.0, 3.1736, 0.5854), 1.0000),
           ((50.0, 2.5, 0.0), (50.0, 3.2972, 0.0), 1.0000),
           ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
           ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
           ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082)]
SHARMA34 = [
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
TOL = 1e-4
anchor_keys = set((a, b, e) for a, b, e in ANCHOR9)
n_anchor_ok = 0
worst_anchor = 0.0
for a, b, e in ANCHOR9:
    got = float(de2000(np.array(a), np.array(b)))
    worst_anchor = max(worst_anchor, abs(got - e))
    n_anchor_ok += abs(got - e) < TOL
assert n_anchor_ok == 9, "anchor pairs from outputs/_sc_deltae.py:52-60 must all reproduce"
kept, dropped = [], []
worst_all = 0.0
worst_sym = 0.0
for idx, a, b, e in SHARMA34:
    got = float(de2000(np.array(a), np.array(b)))
    rev = float(de2000(np.array(b), np.array(a)))
    err = abs(got - e)
    src = "file" if (a, b, e) in anchor_keys else "recalled"
    if err < TOL:
        kept.append((idx, src, got, e, err))
        worst_all = max(worst_all, err)
        worst_sym = max(worst_sym, abs(got - rev))
    else:
        dropped.append((idx, src, got, e, err))
out("  9 anchor pairs (outputs/_sc_deltae.py:52-60): %d/9 reproduce to 1e-4, worst |err| = %.2e" % (n_anchor_ok, worst_anchor))
out("  34 candidate pairs entered (9 from the file + 25 recalled from the published table);")
out("  a recalled pair is KEPT only if it reproduces its published value to 1e-4 - a mis-remembered")
out("  coordinate cannot pass that gate by accident - and is otherwise DROPPED, never adjusted.")
out("  kept = %d   dropped = %d   worst |err| over kept = %.2e   worst asymmetry dE(a,b)-dE(b,a) = %.2e"
    % (len(kept), len(dropped), worst_all, worst_sym))
out("  (published values carry 4 decimals, so 5e-5 of any error is rounding of the reference itself)")
for idx, src, got, e, err in kept:
    out("    pair %2d  %-8s  got %8.4f  ref %8.4f  err %.1e" % (idx, src, got, e, err))
for idx, src, got, e, err in dropped:
    out("    pair %2d  %-8s  got %8.4f  ref %8.4f  err %.1e   DROPPED" % (idx, src, got, e, err))
N_SHARMA = len(kept)
WORST_SHARMA = worst_all

# ----------------------------------------------------------------------------
# 2. vision model self-checks
# ----------------------------------------------------------------------------
out("")
out("2. VISION CONDITIONS - model self-checks")
out("-" * 100)
# (i) rebuild the Vienot matrix from first principles: BT.709 primaries + D65, Vos 1978
#     chromaticity transform, Smith-Pokorny fundamentals. Agreement corroborates all three
#     remembered ingredients at once (published matrix, SP matrix, Vos formula).
prim = [(0.64, 0.33), (0.30, 0.60), (0.15, 0.06)]
cols = np.stack([xyY_to_XYZ(*vos_xy(x, y)) for x, y in prim], axis=1)
wht = xyY_to_XYZ(*vos_xy(0.3127, 0.3290))
Yp = np.linalg.solve(cols, wht)
M_rebuilt = 100.0 * (SP @ (cols * Yp))
rel = np.abs(M_rebuilt - M_V) / np.abs(M_V)
out("  Vienot 1999 RGB->LMS matrix rebuilt from BT.709 primaries + D65 + Vos(1978) + Smith-Pokorny:")
for r in range(3):
    out("     rebuilt %12.6f %12.6f %12.6f    published %12.6f %12.6f %12.6f"
        % (tuple(M_rebuilt[r]) + tuple(M_V[r])))
out("     max relative deviation rebuilt vs published = %.2e" % rel.max())
# (ii) the published projection constants are the plane through black, white and blue
w = M_V @ np.ones(3)
bl = M_V @ np.array([0.0, 0.0, 1.0])
kp = np.linalg.solve(np.array([[w[1], w[2]], [bl[1], bl[2]]]), np.array([w[0], bl[0]]))
kd = np.linalg.solve(np.array([[w[0], w[2]], [bl[0], bl[2]]]), np.array([w[1], bl[1]]))
out("  protan constants: derived (plane through K,W,B) %.5f %.5f   published %.5f %.5f" % (kp[0], kp[1], PROTAN_K[0], PROTAN_K[1]))
out("  deutan constants: derived (plane through K,W,B) %.6f %.5f   published %.6f %.5f" % (kd[0], kd[1], DEUTAN_K[0], DEUTAN_K[1]))
# (iii) tritan anchors
for nm, cmf, exp in (("485", CMF_485, (0.0687, 0.2007)), ("660", CMF_660, (0.7300, 0.2700))):
    s = cmf.sum()
    out("  tritan anchor %s nm: CMF row %s -> xy (%.4f, %.4f)   spectral-locus table value (%.4f, %.4f)"
        % (nm, tuple(cmf), cmf[0] / s, cmf[1] / s, exp[0], exp[1]))
E0, A1, A2 = tritan_params("V0")
out("  tritan (Brettel 1997): neutral E M/L = %.5f ; 485 nm M/L = %.5f (>E -> 485 half-plane) ; 660 nm M/L = %.5f (<E -> 660 half-plane)"
    % (E0[1] / E0[0], A1[1] / A1[0], A2[1] / A2[0]))
for cond in ("protan", "deutan", "tritan"):
    dmax = 0.0
    for g in (0, 64, 128, 171, 255):
        dmax = max(dmax, float(de2000(lab_of([(g, g, g)], "normal"), lab_of([(g, g, g)], cond))[0]))
    out("  invariance of greys under %-6s: max dE2000(grey, sim(grey)) over 5 greys = %.4f" % (cond, dmax))
out("  NOTE tritan greys move slightly because the 1997 model's neutral axis is equal-energy E, not the")
out("  monitor's D65 white (1999 replaced E by the monitor white for protan/deutan). Variant V2 below")
out("  re-runs the headline numbers with D65 as the tritan neutral; V1 pushes the anchors through Vos too.")

# ----------------------------------------------------------------------------
# 3. palette N50, verified against the source at HEAD
# ----------------------------------------------------------------------------
out("")
out("3. PALETTE N50 - verified against source")
out("-" * 100)
cfv_src = open(ROOT + "/common_fixed_variables.py", encoding="utf-8", errors="replace").read()
ramps = {}
for node in ast.parse(cfv_src).body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        nm = node.targets[0].id
        if nm in ("VEGETATION_COLORS", "FIRE_COLORS", "SMOKE_COLORS", "BLACK_AND_WHITE_COLORS"):
            ramps[nm] = ([s.lower() for s in ast.literal_eval(node.value)], node.lineno)
TASK_VEG = "#414141 #9eff89 #85e370 #72d05c #62c14c #459f30 #389023 #2f831b #236f11 #1c630b #175808 #124b05".split()
TASK_FIRE = "#d8d675 #eae740 #fefa01 #fed401 #feaa01 #fe7001 #fe5501 #fe3e01 #fe2f01 #fe2301 #fe0101".split()
TASK_BW = "#ffffff #e6e6e6 #c9c9c9 #b1b1b1 #a1a1a1 #818181 #636363 #474747 #303030 #1a1a1a #000000".split()
VEG, veg_ln = ramps["VEGETATION_COLORS"]
FIRE, fire_ln = ramps["FIRE_COLORS"]
SMOKE, smoke_ln = ramps["SMOKE_COLORS"]
BW, bw_ln = ramps["BLACK_AND_WHITE_COLORS"]
out("  common_fixed_variables.py:%d VEGETATION_COLORS      n=%d  == task list: %s" % (veg_ln, len(VEG), VEG == TASK_VEG))
out("  common_fixed_variables.py:%d FIRE_COLORS            n=%d  [0]=%s (shared with VEG[0]: %s); [1:] == task list: %s"
    % (fire_ln, len(FIRE), FIRE[0], FIRE[0] == VEG[0], FIRE[1:] == TASK_FIRE))
out("  common_fixed_variables.py:%d SMOKE_COLORS           %s" % (smoke_ln, SMOKE))
out("  common_fixed_variables.py:%d BLACK_AND_WHITE_COLORS n=%d  == task list: %s" % (bw_ln, len(BW), BW == TASK_BW))
sd_lines = open(ROOT + "/serve_dashboard.py", encoding="utf-8", errors="replace").read().splitlines()


def find_lines(needle):
    n = needle.lower()
    return [i + 1 for i, ln in enumerate(sd_lines) if n in ln.lower()]


SD_LITERALS = [("burnt", "#2b2b2b"), ("scorched", "#895e00"), ("spared veg", "#2f4a1a"),
               ("UAV victim_searcher", "#00ffff"), ("UAV fire_tracker", "#ff00ff"), ("UAV relay", "#0066cc"),
               ("UAV victim_confirmer", "#ff8c00"), ("UAV return_to_base", "#888888"),
               ("victim candidate", "#ffff00"), ("victim confirmed", "#ffa500"), ("victim assigned/rescued", "#00aaff"),
               ("firefighter", "#00ffcc"), ("depot outline/label", "#770099"),
               ("depot fill", "rgba(119,0,153,0.22)"), ("gridline", "rgba(0,0,0,0.18)"),
               ("assignment (=#ffd75a)", "rgba(255,215,90,"), ("trail ff (=#00ffcc)", "rgba(0,255,204,"),
               ("trail uav (=#78aaff)", "rgba(120,170,255,"), ("canvas bg (=VEG[9])", "'#1c630b'"),
               ("JS BW ramp", 'const BW=["#ffffff","#e6e6e6","#c9c9c9","#b1b1b1","#a1a1a1","#818181","#636363","#474747","#303030","#1a1a1a","#000000"]')]
all_found = True
for label, lit in SD_LITERALS:
    ls = find_lines(lit)
    all_found = all_found and bool(ls)
    shown = lit if len(lit) < 30 else lit[:27] + "..."
    out("  serve_dashboard.py  %-26s %-30s lines %s" % (label, shown, ls[:8] if ls else "NOT FOUND"))
assert rgb2hex((255, 215, 90)) == "#ffd75a" and rgb2hex((120, 170, 255)) == "#78aaff" and rgb2hex((0, 255, 204)) == "#00ffcc"
assert rgb2hex((119, 0, 153)) == "#770099"
out("  every literal found: %s ; rgba(255,215,90)=#ffd75a, rgba(120,170,255)=#78aaff, rgba(0,255,204)=#00ffcc, rgba(119,0,153)=#770099" % all_found)

PAL = {}       # hex -> [names]
ORDER = []
N_LISTED = [0]


def add(pal, order, h, name):
    h = h.lower()
    if h in pal:
        pal[h].append(name)
        return False
    pal[h] = [name]
    order.append(h)
    return True


dups = []
listed = ([(c, "VEG[%d]" % i) for i, c in enumerate(VEG)] + [(c, "FIRE[%d]" % i) for i, c in enumerate(FIRE)]
          + [(SMOKE[0], "smoke"), ("#2b2b2b", "burnt"), ("#895e00", "scorched"), ("#2f4a1a", "spared")]
          + [(c, "BW[%d]" % i) for i, c in enumerate(BW)]
          + [("#00ffff", "UAV searcher"), ("#ff00ff", "UAV tracker"), ("#0066cc", "UAV relay"),
             ("#ff8c00", "UAV confirmer"), ("#888888", "UAV RTB"),
             ("#ffff00", "victim cand"), ("#ffa500", "victim conf"), ("#00aaff", "victim assigned"),
             ("#00ffcc", "firefighter"), ("#770099", "depot"), ("#ffd75a", "assignment"),
             ("#00ffcc", "trail ff"), ("#78aaff", "trail uav")])
for h, nm in listed:
    if not add(PAL, ORDER, h, nm):
        dups.append((h, nm, PAL[h][0]))
N50 = list(ORDER)
out("  listed entries = %d ; distinct = %d ; duplicates folded: %s"
    % (len(listed), len(N50), ", ".join("%s %s==%s" % d for d in dups)))
out("  (other literals on the map surface add nothing new: dead victim / dead firefighter / role fallback /")
out("   UAV stroke '#000' are all #000000 = BW[10]; canvas bg #1c630b = VEG[9]; probMode bg #ffffff = BW[0])")
N50_COUNT = len(N50)


def pname(h, pal=None):
    pal = pal if pal is not None else PAL
    return "%s %s" % (h, "/".join(pal[h][:2]))


rgb50 = np.array([hex2rgb(h) for h in N50], dtype=np.int64)
lab50 = labs_all(rgb50)

# cross-checks against numbers the earlier rounds published (normal vision is model-free)
out("")
out("  cross-checks of the normal-vision pipeline against earlier published numbers:")
sc_set = list(dict.fromkeys(VEG + FIRE + ["#ababab", "#2b2b2b", "#2f4a1a", "#1c630b", "#00ffff", "#ff00ff", "#0066cc",
                                          "#ff8c00", "#888888", "#000000", "#ffff00", "#ffa500", "#00aaff", "#00ffcc", "#ffd75a"]))
d = de2000(lab_of([hex2rgb("#895e00")], "normal")[:, None, :], lab_of([hex2rgb(h) for h in sc_set], "normal")[None])[0]
out("    #895e00 min dE vs the %d colours of outputs/_sc_deltae.py:67-79 = %.2f  (common_fixed_variables.py:515-516 says 27.34)"
    % (len(sc_set), d.min()))
for hx, ref_norm, ref_other, where in (("#990033", 25.97, "0.34 achromatic", "outputs/fovframe_part1.txt:631-633"),
                                       ("#ff1493", 16.59, "0.63 worst-case", "outputs/fovframe_part1.txt:594-595")):
    res = {}
    for c in CONDS:
        dd = de2000(lab_of([hex2rgb(hx)], c)[:, None, :], lab50[c][None])[0]
        res[c] = (float(dd.min()), N50[int(dd.argmin())])
    wc = min(CONDS, key=lambda c: res[c][0])
    out("    %s vs N50: normal %.2f (%s) ; achrom %.2f ; worst %.2f (%s)   earlier: normal %.2f, %s  [%s]"
        % (hx, res["normal"][0], res["normal"][1], res["achrom"][0], res[wc][0], wc, ref_norm, ref_other, where))
dd = de2000(lab_of([hex2rgb("#000000")], "normal")[:, None, :], lab50["normal"][None])[0]
dd = np.where((rgb50 == 0).all(1), np.inf, dd)
res_b = []
for c in CONDS:
    d2 = de2000(lab_of([(0, 0, 0)], c)[:, None, :], lab50[c][None])[0]
    d2 = np.where((rgb50 == 0).all(1), np.inf, d2)
    res_b.append(float(d2.min()))
out("    #000000 vs N50, exact identity excluded: normal %.2f ; worst of 5 %.2f   (earlier: 5.52, outputs/fovframe_part1.txt:554-555)"
    % (float(dd.min()), min(res_b)))

# ----------------------------------------------------------------------------
# 3a. exhaustive FLAT sweep
# ----------------------------------------------------------------------------
out("")
out("3a. EXHAUSTIVE FLAT SWEEP  {0,5,...,255}^3 vs N50, worst of 5 vision conditions, nothing excluded")
out("-" * 100)
g = np.arange(0, 256, 5)
GR, GG, GB = np.meshgrid(g, g, g, indexing="ij")
GRID = np.stack([GR.ravel(), GG.ravel(), GB.ravel()], axis=1).astype(np.int64)
GRID_LIN = srgb8_to_lin(GRID)
out("  grid size = %d" % GRID.shape[0])
flat = {}
flat_arg = {}
for c in CONDS:
    labX = lin_to_lab(SIMS[c](GRID_LIN))
    flat[c], flat_arg[c] = min_over_palette(labX, lab50[c])
    i = int(flat[c].argmax())
    out("  %-7s alone: best min-dE = %6.2f at %s (nearest %s)   [%.0fs]"
        % (c, flat[c][i], rgb2hex(GRID[i]), pname(N50[int(flat_arg[c][i])]), time.time() - T0))


def ceiling(flatd):
    stack = np.stack([flatd[c] for c in CONDS], axis=0)
    worst = stack.min(0)
    wcond = stack.argmin(0)
    order = np.lexsort((np.arange(worst.size), -worst))
    return worst, wcond, order


worst, wcond, order = ceiling(flat)
FLAT_CEIL = float(worst[order[0]])
FLAT_COL = rgb2hex(GRID[order[0]])
out("  FLAT CEILING (worst of 5) = %.4f dE2000 at %s   [earlier round: 2.73 near #00004b]" % (FLAT_CEIL, FLAT_COL))
out("  top 8 of the sweep:")
for i in order[:8]:
    c = CONDS[int(wcond[i])]
    out("     %s  worst %.4f  binding condition %-6s nearest %-28s | per-condition %s"
        % (rgb2hex(GRID[i]), worst[i], c, pname(N50[int(flat_arg[c][i])]),
           " ".join("%s=%.2f" % (cc[:3], flat[cc][i]) for cc in CONDS)))
i4b = int(np.where((GRID == np.array(hex2rgb("#00004b"))).all(1))[0][0])
out("  the earlier round's #00004b in THIS instrument: worst %.4f (binding %s); per-condition %s ; rank %d of %d"
    % (worst[i4b], CONDS[int(wcond[i4b])], " ".join("%s=%.2f" % (cc[:3], flat[cc][i4b]) for cc in CONDS),
       int(np.where(order == i4b)[0][0]) + 1, order.size))
out("  share of the grid scoring below 1.0 / 2.0 / 2.3 (JND) worst-case: %.1f%% / %.1f%% / %.1f%%"
    % (100 * (worst < 1).mean(), 100 * (worst < 2).mean(), 100 * (worst < 2.3).mean()))

# ----------------------------------------------------------------------------
# 3b. two-tone mark
# ----------------------------------------------------------------------------
out("")
out("3b. TWO-TONE MARK {#ffffff,#000000} vs N50 - score(b)=max over tones, min over palette, worst condition")
out("-" * 100)


def multi_tone(tones_hex, pal_hex, pal_labs, sims=None):
    """returns per-condition (min score, argmin entry) and the per-entry score matrix."""
    sims = sims or SIMS
    per = {}
    mat = {}
    for c in CONDS:
        labT = lin_to_lab(sims[c](srgb8_to_lin(np.array([hex2rgb(t) for t in tones_hex], dtype=np.float64))))
        d = de2000(labT[:, None, :], pal_labs[c][None, :, :])     # tones x palette
        sc = d.max(0)
        mat[c] = d
        per[c] = (float(sc.min()), pal_hex[int(sc.argmin())], tones_hex[int(d[:, int(sc.argmin())].argmax())])
    return per, mat


tt, tt_mat = multi_tone(["#ffffff", "#000000"], N50, lab50)
for c in CONDS:
    out("  %-7s min over N50 of max(dE(white,b),dE(black,b)) = %7.4f   binding entry %-24s (better tone there: %s)"
        % (c, tt[c][0], pname(tt[c][1]), tt[c][2]))
wc = min(CONDS, key=lambda c: tt[c][0])
TWO_TONE = tt[wc][0]
out("  TWO-TONE SCORE = %.4f (binding condition %s, entry %s)   [earlier round: 38.37]" % (TWO_TONE, wc, pname(tt[wc][1])))
iw, ib = N50.index("#ffffff"), N50.index("#000000")
out("  HANDLING OF #ffffff / #000000 BEING IN N50: nothing is excluded. Against b=#ffffff the white tone scores")
out("  %.2f and the black tone %.2f, so score(b)=%.2f; against b=#000000 it is %.2f / %.2f -> %.2f. An identical tone"
    % (tt_mat["normal"][0, iw], tt_mat["normal"][1, iw], tt_mat["normal"][:, iw].max(),
       tt_mat["normal"][0, ib], tt_mat["normal"][1, ib], tt_mat["normal"][:, ib].max()))
out("  contributes 0 but the OTHER tone contributes ~100, so neither entry can bind the minimum; the binding entry")
out("  is always a MID-lightness colour, where both tones are ~equally far.")
out("  ratio two-tone / flat ceiling = %.1fx   [earlier round: 14.0x]" % (TWO_TONE / FLAT_CEIL))

# ----------------------------------------------------------------------------
# 4. N+ palette
# ----------------------------------------------------------------------------
out("")
out("4. PALETTE N+ = N50 + depot-fill composites (+ gridline)")
out("-" * 100)


def over(src, a100, dst):
    """source-over in sRGB byte space, integer round-half-up: (a*s + (1-a)*d)."""
    return tuple((a100 * s + (100 - a100) * d_ + 50) // 100 for s, d_ in zip(src, dst))


DEPOT = hex2rgb("#770099")
GROUNDS = ([(c, "VEG[%d]" % i) for i, c in enumerate(VEG)] + [(c, "FIRE[%d]" % i) for i, c in enumerate(FIRE) if i > 0]
           + [(SMOKE[0], "smoke"), ("#2b2b2b", "burnt"), ("#895e00", "scorched"), ("#2f4a1a", "spared")]
           + [(c, "BW[%d]" % i) for i, c in enumerate(BW)])
out("  grounds a flag can sit on: %d  (12 VEG + 11 FIRE + smoke + burnt + scorched + spared + 11 BW)" % len(GROUNDS))


def build_nplus(zorder):
    pal = {h: list(v) for h, v in PAL.items()}
    order_ = list(N50)
    comp = {}
    n_new = [0, 0]
    for hx, nm in GROUNDS:
        c1 = over(DEPOT, 22, hex2rgb(hx))
        if zorder == "spec":      # gridline over (depot over ground) - the task's wording
            c2 = over((0, 0, 0), 18, c1)
        else:                      # canvas z-order: depot over (gridline over ground)
            c2 = over(DEPOT, 22, over((0, 0, 0), 18, hex2rgb(hx)))
        comp[nm] = (rgb2hex(c1), rgb2hex(c2))
        n_new[0] += add(pal, order_, rgb2hex(c1), "depot>" + nm)
        n_new[1] += add(pal, order_, rgb2hex(c2), "grid+depot>" + nm)
    return pal, order_, comp, n_new


PALP, NPLUS, COMP, n_new = build_nplus("spec")
out("  N+ (task wording: 0.18 black gridline OVER the 0.22 depot composite): %d = 50 + %d new depot composites + %d new gridline composites"
    % (len(NPLUS), n_new[0], n_new[1]))
collide = [(h, v) for h, v in PALP.items() if len(v) > 1 and any(n.startswith(("depot>", "grid+depot>")) for n in v)
           and not all(n.startswith(("depot>", "grid+depot>")) for n in v)]
multi = [(h, v) for h, v in PALP.items() if len(v) > 1 and all(n.startswith(("depot>", "grid+depot>")) for n in v)]
out("  composites colliding with an N50 colour: %s" % (collide if collide else "none"))
out("  composites colliding with each other: %s" % (multi if multi else "none"))
PALZ, NPLUSZ, COMPZ, n_newz = build_nplus("canvas")
out("  Z-ORDER NOTE: serve_dashboard.py draws ground (:740-744) -> gridlines (:746-749) -> depot fill (:764), so on the")
out("  real canvas the depot fill sits OVER the gridline. That variant (N+z) has %d entries; union of both = %d."
    % (len(NPLUSZ), len(set(NPLUS) | set(NPLUSZ))))
out("  The gridline stroke is also lineWidth 0.5 (:746), i.e. half-pixel coverage, so 0.18 is an upper bound on its")
out("  darkening. All headline numbers below use the task-wording N+; section 5 re-runs 4(a) on N+z.")
for nm in ("VEG[0]", "VEG[1]", "VEG[9]", "VEG[11]", "burnt", "scorched", "smoke", "BW[0]", "BW[10]"):
    out("     %-9s ground %s -> depot composite %s -> +gridline %s   (canvas z-order: %s)"
        % (nm, dict((n, h) for h, n in GROUNDS)[nm], COMP[nm][0], COMP[nm][1], COMPZ[nm][1]))
rgbP = np.array([hex2rgb(h) for h in NPLUS], dtype=np.int64)
labP = labs_all(rgbP)
NPLUS_COUNT = len(NPLUS)

# ----------------------------------------------------------------------------
# 4a. candidate FIELD colours
# ----------------------------------------------------------------------------
CANDS = ["#770099", "#ffffff", "#000000", "#990033", "#ff1493", "#c0c0c0", "#9933ff", "#b266ff", "#ff66ff", "#5500aa", "#aa00ff"]


def cand_table(cands, pal_hex, pal_rgb, pal_labs, pal_names, sims=None):
    sims = sims or SIMS
    rows = []
    for hx in cands:
        rgb = np.array([hex2rgb(hx)], dtype=np.int64)
        same = (pal_rgb == rgb[0]).all(1)
        per = {}
        for c in CONDS:
            labX = lin_to_lab(sims[c](srgb8_to_lin(rgb)))
            d = de2000(labX[:, None, :], pal_labs[c][None])[0]
            d = np.where(same, np.inf, d)
            per[c] = (float(d.min()), pal_hex[int(d.argmin())])
        wc_ = min(CONDS, key=lambda c: per[c][0])
        rows.append({"hex": hx, "in_palette": bool(same.any()), "per": per, "worst_cond": wc_})
    return rows


out("")
out("4a. CANDIDATE FIELD COLOURS vs N+ (an entry identical to X is excluded and flagged 'self')")
out("-" * 100)
rows4a = cand_table(CANDS, NPLUS, rgbP, labP, PALP)
# secondary view: drop the 22 composites whose ground is the BW ramp (probability-mode only)
MAPMODE = [h for h in NPLUS if not all(n.startswith(("depot>BW[", "grid+depot>BW[")) for n in PALP[h])]
rgbM = np.array([hex2rgb(h) for h in MAPMODE], dtype=np.int64)
labM = labs_all(rgbM)
rows4a_map = cand_table(CANDS, MAPMODE, rgbM, labM, PALP)
out("  %-8s %-5s %8s  %-34s %8s  %-7s %-34s | %s" % ("X", "self", "normal", "nearest (normal)", "worst", "cond", "nearest (worst)", "per-condition"))
for r in rows4a:
    p = r["per"]
    out("  %-8s %-5s %8.2f  %-34s %8.2f  %-7s %-34s | %s"
        % (r["hex"], "yes" if r["in_palette"] else "no", p["normal"][0], pname(p["normal"][1], PALP),
           p[r["worst_cond"]][0], r["worst_cond"], pname(p[r["worst_cond"]][1], PALP),
           " ".join("%s=%.2f" % (c[:3], p[c][0]) for c in CONDS)))
out("  same, against the %d-entry subset without the 22 BW-ground composites (those exist only in probability mode):" % len(MAPMODE))
for r in rows4a_map:
    p = r["per"]
    out("  %-8s normal %6.2f  %-34s worst %6.2f %-6s" % (r["hex"], p["normal"][0], pname(p["normal"][1], PALP),
                                                       p[r["worst_cond"]][0], r["worst_cond"]))

# ----------------------------------------------------------------------------
# 4b. exhaustive FIELD sweep, normal vision
# ----------------------------------------------------------------------------
out("")
out("4b. EXHAUSTIVE FIELD SWEEP, NORMAL vision, vs N+ (self excluded)")
out("-" * 100)
labG = lin_to_lab(GRID_LIN)
fmin, farg = min_over_palette(labG, labP["normal"], rgbX=GRID, rgbP=rgbP, chunk=2048)
ordn = np.lexsort((np.arange(fmin.size), -fmin))
lab_dep = lab_of([DEPOT], "normal")[0]
H0 = float(np.degrees(np.arctan2(lab_dep[2], lab_dep[1])) % 360.0)
C0 = float(np.hypot(lab_dep[1], lab_dep[2]))
out("  #770099: L*=%.2f a*=%.2f b*=%.2f  C*=%.2f  h_ab=%.2f deg ; family = |h - %.2f| <= 25 and C* >= 40"
    % (lab_dep[0], lab_dep[1], lab_dep[2], C0, H0, H0))
hG = np.degrees(np.arctan2(labG[:, 2], labG[:, 1])) % 360.0
cG = np.hypot(labG[:, 1], labG[:, 2])
fam = (np.abs((hG - H0 + 180.0) % 360.0 - 180.0) <= 25.0) & (cG >= 40.0)
out("  grid colours in the family: %d of %d" % (int(fam.sum()), fam.size))
in_pal_grid = (GRID[:, None, :] == rgbP[None, :, :]).all(-1).any(1)


def worst5(hx, pal_rgb, pal_labs, pal_hex):
    r = cand_table([hx], pal_hex, pal_rgb, pal_labs, None)[0]
    return r["per"][r["worst_cond"]][0], r["worst_cond"]


def top_rows(idx_list, label):
    out("  %s" % label)
    res = []
    for rank, i in enumerate(idx_list, 1):
        hx = rgb2hex(GRID[i])
        w5, w5c = worst5(hx, rgbP, labP, NPLUS)
        out("    %2d  %s  normal-min %6.2f  nearest %-34s L*=%5.1f C*=%5.1f h=%5.1f  self-in-N+=%s  (worst-of-5 %.2f %s)"
            % (rank, hx, fmin[i], pname(NPLUS[int(farg[i])], PALP), labG[i, 0], cG[i], hG[i],
               "yes" if in_pal_grid[i] else "no", w5, w5c))
        res.append({"hex": hx, "normal_min": round(float(fmin[i]), 2), "nearest": NPLUS[int(farg[i])],
                    "worst_min": round(w5, 2), "in_palette": bool(in_pal_grid[i])})
    return res


BEST_ANY = top_rows(list(ordn[:10]), "top 10 overall:")
fam_order = [i for i in ordn if fam[i]][:10]
BEST_FAM = top_rows(fam_order, "top 10 within the depot hue family:")
r77 = [r for r in rows4a if r["hex"] == "#770099"][0]
rank77 = int((fmin[fam] > r77["per"]["normal"][0]).sum()) + 1
out("  #770099 itself (off-grid, 0x77=119): normal-min %.2f, would rank %d among the %d family grid colours ; %d of all %d grid colours beat it"
    % (r77["per"]["normal"][0], rank77, int(fam.sum()), int((fmin > r77["per"]["normal"][0]).sum()), fmin.size))
BEST_FAM_HEX = BEST_FAM[0]["hex"]
BEST_ANY_FREE = top_rows([i for i in ordn if not in_pal_grid[i]][:3], "top 3 overall that are NOT already a palette colour:")
BEST_FAM_FREE = top_rows([i for i in ordn if fam[i] and not in_pal_grid[i]][:3], "top 3 in the family that are NOT already a palette colour:")
BEST_FAM_FREE_HEX = BEST_FAM_FREE[0]["hex"]
if BEST_FAM_HEX != BEST_FAM_FREE_HEX:
    out("  NOTE the literal family winner %s IS a palette entry (%s): the self-exclusion rule hides a 0.00 identity" % (BEST_FAM_HEX, "/".join(PALP[BEST_FAM_HEX])))
    out("  collision with an existing semantic mark. 4(c) is therefore run for #770099, for the literal winner, AND for")
    out("  the best family colour that is free, %s." % BEST_FAM_FREE_HEX)

# ----------------------------------------------------------------------------
# 4c. three-tone mark
# ----------------------------------------------------------------------------
out("")
out("4c. THREE-TONE MARK {#000000 casing, #ffffff keyline, X field} vs N+ (nothing excluded)")
out("-" * 100)
ENTRIES14 = ["#770099", "#ffffff", "#000000", "#2b2b2b", "#895e00", "#ababab", "#1c630b", "#124b05",
             "#fe0101", "#fefa01", "#ff00ff", "#00ffff", "#00ffcc", "#ffff00"]
tt_plus, _ = multi_tone(["#ffffff", "#000000"], NPLUS, labP)
wc2 = min(CONDS, key=lambda c: tt_plus[c][0])
out("  reference: TWO-tone {#ffffff,#000000} vs N+ : worst %.4f (%s, entry %s) ; per-condition %s"
    % (tt_plus[wc2][0], wc2, pname(tt_plus[wc2][1], PALP), " ".join("%s=%.2f" % (c[:3], tt_plus[c][0]) for c in CONDS)))
THREE = {}
for X in dict.fromkeys(["#770099", BEST_FAM_HEX, BEST_FAM_FREE_HEX]):
    tones = ["#000000", "#ffffff", X]
    per, mat = multi_tone(tones, NPLUS, labP)
    wc3 = min(CONDS, key=lambda c: per[c][0])
    out("")
    out("  X = %s : min over N+ per condition: %s" % (X, " ".join("%s=%.2f" % (c[:3], per[c][0]) for c in CONDS)))
    out("     THREE-TONE worst-condition min = %.4f (%s, binding entry %s, best tone there %s) ; gain over two-tone = %+.4f"
        % (per[wc3][0], wc3, pname(per[wc3][1], PALP), per[wc3][2], per[wc3][0] - tt_plus[wc2][0]))
    # how often is the FIELD the best tone?
    nfield = int((mat["normal"].argmax(0) == 2).sum())
    out("     entries of N+ for which the FIELD is the best of the three tones (normal vision): %d of %d" % (nfield, len(NPLUS)))
    out("     %-9s %-16s %9s %-8s %9s %-7s %11s" % ("entry", "name", "normal", "by tone", "worst-5", "cond", "field-only"))
    ent = {}
    for e in ENTRIES14:
        j = NPLUS.index(e)
        sc = {c: float(mat[c][:, j].max()) for c in CONDS}
        wce = min(CONDS, key=lambda c: sc[c])
        tone_n = tones[int(mat["normal"][:, j].argmax())]
        fo = float(mat["normal"][2, j])
        fo_w = min(float(mat[c][2, j]) for c in CONDS)
        out("     %-9s %-16s %9.2f %-8s %9.2f %-7s %11.2f  (field-only worst-5 %.2f)"
            % (e, PALP[e][0], sc["normal"], tone_n, sc[wce], wce, fo, fo_w))
        ent[e] = {"normal": round(sc["normal"], 2), "worst": round(sc[wce], 2), "worst_cond": wce,
                  "field_only_normal": round(fo, 2), "field_only_worst": round(fo_w, 2)}
    THREE[X] = {"worst_min": round(per[wc3][0], 2), "worst_cond": wc3, "binding_entry": per[wc3][1],
                "normal_min": round(per["normal"][0], 2), "entries": ent}

# ----------------------------------------------------------------------------
# 4d. identity vs the two-tone FOV frame
# ----------------------------------------------------------------------------
out("")
out("4d. MARK-vs-MARK IDENTITY against the FOV frame {#ffffff,#000000}: identity(X)=min(dE(X,#fff),dE(X,#000))")
out("-" * 100)
IDENT = {}
out("  %-8s %s %9s  %-6s" % ("X", " ".join("%8s" % c for c in CONDS), "worst", "cond"))
for hx in CANDS:
    per = {}
    for c in CONDS:
        lx = lab_of([hex2rgb(hx)], c)
        lw = lab_of([(255, 255, 255)], c)
        lk = lab_of([(0, 0, 0)], c)
        per[c] = float(min(de2000(lx, lw)[0], de2000(lx, lk)[0]))
    wcd = min(CONDS, key=lambda c: per[c])
    out("  %-8s %s %9.2f  %-6s" % (hx, " ".join("%8.2f" % per[c] for c in CONDS), per[wcd], wcd))
    IDENT[hx] = dict([(c, round(per[c], 2)) for c in CONDS] + [("worst", round(per[wcd], 2)), ("worst_cond", wcd)])
IDENT_EXTRA = {}
for hx in dict.fromkeys([BEST_FAM_HEX, BEST_FAM_FREE_HEX]):
    per = {c: float(min(de2000(lab_of([hex2rgb(hx)], c), lab_of([(255, 255, 255)], c))[0],
                        de2000(lab_of([hex2rgb(hx)], c), lab_of([(0, 0, 0)], c))[0])) for c in CONDS}
    wcd = min(CONDS, key=lambda c: per[c])
    out("  %-8s %s %9.2f  %-6s  (from 4b)" % (hx, " ".join("%8.2f" % per[c] for c in CONDS), per[wcd], wcd))
    IDENT_EXTRA[hx] = dict([(c, round(per[c], 2)) for c in CONDS] + [("worst", round(per[wcd], 2)), ("worst_cond", wcd)])

# ----------------------------------------------------------------------------
# 4e. WCAG contrast
# ----------------------------------------------------------------------------
out("")
out("4e. WCAG 2.x CONTRAST of #ffffff / #000000 / #770099 against the grounds a flag sits on")
out("-" * 100)


def rel_lum(rgb):
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(lin @ np.array([0.2126, 0.7152, 0.0722]))


def cr(h1, h2):
    a, b = rel_lum(hex2rgb(h1)), rel_lum(hex2rgb(h2))
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


xc = [("black on #2b2b2b", cr("#000000", "#2b2b2b"), 1.48), ("black on #124b05", cr("#000000", "#124b05"), 2.03),
      ("black on #175808", cr("#000000", "#175808"), 2.44), ("black on #1c630b", cr("#000000", "#1c630b"), 2.84),
      ("black on #414141", cr("#000000", "#414141"), 2.06), ("black on smoke", cr("#000000", "#ababab"), 9.14),
      ("black on #2f831b", cr("#000000", "#2f831b"), 4.38), ("black on scorched", cr("#000000", "#895e00"), 3.67),
      ("white on #2f831b", cr("#ffffff", "#2f831b"), 4.79)]
out("  cross-check vs outputs/fovframe_part1.txt:546-552,648: " + " ; ".join("%s %.2f (ref %.2f)" % t for t in xc))
gmin = min(max(cr("#ffffff", rgb2hex((v, v, v))), cr("#000000", rgb2hex((v, v, v)))) for v in range(256))
out("  min over the 256 greys of better-of-white/black = %.2f:1  (ref 4.61, outputs/fovframe_part1.txt:621-622)" % gmin)
wrows = []
for i, c in enumerate(VEG):
    wrows.append(("depot>VEG[%d]" % i, COMP["VEG[%d]" % i][0], "composite"))
for nm in ("burnt", "scorched", "smoke"):
    wrows.append(("depot>" + nm, COMP[nm][0], "composite"))
for nm, hx in (("burnt", "#2b2b2b"), ("scorched", "#895e00"), ("smoke", "#ababab")):
    wrows.append((nm + " (nominal)", hx, "nominal"))
out("  %-20s %-8s %8s %8s %9s %10s" % ("ground", "hex", "white", "black", "#770099", "better w/b"))
WCAG = []
for nm, hx, kind in wrows:
    w_, k_, d_ = cr("#ffffff", hx), cr("#000000", hx), cr("#770099", hx)
    out("  %-20s %-8s %8.2f %8.2f %9.2f %10.2f" % (nm, hx, w_, k_, d_, max(w_, k_)))
    WCAG.append({"ground": nm, "hex": hx, "kind": kind, "white": round(w_, 2), "black": round(k_, 2),
                 "depot": round(d_, 2), "better_wb": round(max(w_, k_), 2)})
comp_rows = [r for r in WCAG if r["kind"] == "composite"]
mc = min(comp_rows, key=lambda r: r["better_wb"])
ma = min(WCAG, key=lambda r: r["better_wb"])
md = min(WCAG, key=lambda r: r["depot"])
md3 = [r["ground"] for r in WCAG if r["depot"] < 3.0]
out("  MIN of better-of-white/black over the 15 composites = %.2f:1 (%s %s) ; over all 18 rows = %.2f:1 (%s %s)"
    % (mc["better_wb"], mc["ground"], mc["hex"], ma["better_wb"], ma["ground"], ma["hex"]))
out("  #770099 field alone: min %.2f:1 (%s) ; below 3:1 on %d of 18 rows: %s" % (md["depot"], md["ground"], len(md3), ", ".join(md3)))
out("  internal contrast of the mark: #770099 vs #ffffff %.2f:1 ; #770099 vs #000000 %.2f:1 ; white vs black %.2f:1"
    % (cr("#770099", "#ffffff"), cr("#770099", "#000000"), cr("#ffffff", "#000000")))

# ----------------------------------------------------------------------------
# 5. sensitivity
# ----------------------------------------------------------------------------
out("")
out("5. SENSITIVITY")
out("-" * 100)
out("  (i) tritan model variants - only the tritan condition changes; V0 is the instrument, V1/V2 are what-ifs")
SENS = {}
for var, desc in (("V0", "E neutral, CMF anchors (instrument)"), ("V1", "E neutral, anchors through Vos formula"),
                  ("V2", "D65 monitor-white neutral, CMF anchors")):
    sims = dict(SIMS)
    sims["tritan"] = make_tritan(var)
    l50 = dict(lab50)
    l50["tritan"] = lab_of(rgb50, "tritan", sims["tritan"])
    fl = dict(flat)
    fl["tritan"], _ = min_over_palette(lin_to_lab(sims["tritan"](GRID_LIN)), l50["tritan"])
    w_, wc_, o_ = ceiling(fl)
    t2, _ = multi_tone(["#ffffff", "#000000"], N50, l50, sims)
    wct = min(CONDS, key=lambda c: t2[c][0])
    lP = dict(labP)
    lP["tritan"] = lab_of(rgbP, "tritan", sims["tritan"])
    rows = cand_table(CANDS, NPLUS, rgbP, lP, PALP, sims)
    out("    %s %-40s flat ceiling %.4f at %s (binding %s) ; tritan-alone best %.2f ; two-tone %.4f (%s) ; tritan two-tone %.4f"
        % (var, desc, w_[o_[0]], rgb2hex(GRID[o_[0]]), CONDS[int(wc_[o_[0]])], fl["tritan"].max(), t2[wct][0], wct, t2["tritan"][0]))
    out("       4a worst-of-5 per candidate: " + " ".join("%s=%.2f(%s)" % (r["hex"], r["per"][r["worst_cond"]][0], r["worst_cond"][:3]) for r in rows))
    SENS[var] = {"flat_ceiling": round(float(w_[o_[0]]), 4), "flat_colour": rgb2hex(GRID[o_[0]]), "two_tone": round(t2[wct][0], 4)}
out("  (ii) what could explain 2.73 / 38.37 (earlier round) vs this instrument - both are bound by the ACHROMATIC condition")


def lin_to_srgb8(lin):
    c = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(np.maximum(lin, 0.0), 1.0 / 2.4) - 0.055)
    return np.rint(np.clip(c, 0.0, 1.0) * 255.0)


def q8(f):
    return lambda lin: srgb8_to_lin(lin_to_srgb8(f(lin)))


def achrom_luma(coef, quant):
    k = np.array(coef)

    def f(lin):
        enc = lin_to_srgb8(lin) / 255.0      # recovers the gamma-encoded bytes exactly
        yp = enc @ k
        yp = np.rint(yp * 255.0) / 255.0 if quant else yp
        Y = srgb8_to_lin(yp * 255.0)
        return np.stack([Y, Y, Y], axis=-1)
    return f


_keep = []
_flat_cache = {id(SIMS[c]): flat[c] for c in CONDS}


def headline(sims):
    l50 = {c: lab_of(rgb50, c, sims[c]) for c in CONDS}
    fl = {}
    for c in CONDS:
        if id(sims[c]) not in _flat_cache:
            _keep.append(sims[c])
            _flat_cache[id(sims[c])] = min_over_palette(lin_to_lab(sims[c](GRID_LIN)), l50[c])[0]
        fl[c] = _flat_cache[id(sims[c])]
    w_, wc_, o_ = ceiling(fl)
    t2, _ = multi_tone(["#ffffff", "#000000"], N50, l50, sims)
    wct = min(CONDS, key=lambda c: t2[c][0])
    return float(w_[o_[0]]), rgb2hex(GRID[o_[0]]), CONDS[int(wc_[o_[0]])], t2[wct][0], wct, t2[wct][1]


ACH = {}
for label, sims in (("instrument (linear Rec.709 Y, unquantised)", dict(SIMS)),
                    ("same, simulated colour rounded to 8-bit sRGB (all conditions)", {c: (SIMS[c] if c == "normal" else q8(SIMS[c])) for c in CONDS}),
                    ("achrom = Rec.709 coefficients on GAMMA-ENCODED bytes, unrounded", dict(SIMS, achrom=achrom_luma((0.2126, 0.7152, 0.0722), False))),
                    ("achrom = Rec.709 coefficients on GAMMA-ENCODED bytes, rounded", dict(SIMS, achrom=achrom_luma((0.2126, 0.7152, 0.0722), True))),
                    ("achrom = Rec.601 luma on GAMMA-ENCODED bytes, rounded", dict(SIMS, achrom=achrom_luma((0.299, 0.587, 0.114), True)))):
    h = headline(sims)
    out("    %-66s flat ceiling %.4f at %s (%s) ; two-tone %.4f (%s, %s)" % ((label,) + h))
    ACH[label] = {"flat_ceiling": round(h[0], 4), "flat_colour": h[1], "two_tone": round(h[3], 4)}
out("    earlier round                                                      flat ceiling 2.73   near #00004b     ; two-tone 38.37")
out("  (iii) 4(a) re-run on N+z (canvas z-order: depot fill OVER the gridline), %d entries:" % len(NPLUSZ))
rgbZ = np.array([hex2rgb(h) for h in NPLUSZ], dtype=np.int64)
labZ = labs_all(rgbZ)
rowsz = cand_table(CANDS, NPLUSZ, rgbZ, labZ, PALZ)
for r, r0 in zip(rowsz, rows4a):
    p = r["per"]
    out("    %-8s normal %6.2f (%-30s) worst %6.2f %-6s | task-wording N+: normal %6.2f worst %6.2f"
        % (r["hex"], p["normal"][0], pname(p["normal"][1], PALZ), p[r["worst_cond"]][0], r["worst_cond"],
           r0["per"]["normal"][0], r0["per"][r0["worst_cond"]][0]))

# ----------------------------------------------------------------------------
# RESULT_JSON
# ----------------------------------------------------------------------------
RESULT = {
    "instrument": "b",
    "sharma_pairs": N_SHARMA, "sharma_worst_err": float("%.2e" % WORST_SHARMA),
    "flat_ceiling": round(FLAT_CEIL, 4), "flat_ceiling_colour": FLAT_COL,
    "two_tone_score": round(TWO_TONE, 4), "two_tone_cond": wc, "two_tone_entry": tt[wc][1],
    "n50_count": N50_COUNT, "nplus_count": NPLUS_COUNT, "nplus_canvas_zorder_count": len(NPLUSZ),
    "two_tone_vs_nplus": round(tt_plus[wc2][0], 4),
    "field_candidates": [{"hex": r["hex"], "normal_min": round(r["per"]["normal"][0], 2),
                          "normal_nearest": r["per"]["normal"][1],
                          "worst_min": round(r["per"][r["worst_cond"]][0], 2), "worst_cond": r["worst_cond"],
                          "in_palette": r["in_palette"]} for r in rows4a],
    "best_any": BEST_ANY[:3], "best_family": BEST_FAM[:3],
    "best_any_not_in_palette": BEST_ANY_FREE[:3], "best_family_not_in_palette": BEST_FAM_FREE[:3],
    "field_candidates_no_bw_composites": [{"hex": r["hex"], "normal_min": round(r["per"]["normal"][0], 2),
                                           "normal_nearest": r["per"]["normal"][1],
                                           "worst_min": round(r["per"][r["worst_cond"]][0], 2)} for r in rows4a_map],
    "identity_extra": IDENT_EXTRA, "achromatic_definition_sensitivity": ACH,
    "depot_hue": round(H0, 2), "depot_chroma": round(C0, 2),
    "three_tone": THREE, "identity": IDENT,
    "wcag_min_better_wb_composites": mc["better_wb"], "wcag_min_better_wb_all18": ma["better_wb"],
    "tritan_sensitivity": SENS,
}
out("")
out("RESULT_JSON=" + json.dumps(RESULT, separators=(",", ":")))
out("")
out("elapsed %.1f s" % (time.time() - T0))
with open(OUT_TXT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(_LINES) + "\n")
