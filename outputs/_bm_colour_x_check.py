# -*- coding: utf-8 -*-
"""_bm_colour_x_check.py - THIRD instrument ("x"): a small independent cross-check of
outputs/_bm_colour_a.py (Machado 2009) and outputs/_bm_colour_b.py (Vienot 1999 / Brettel 1997).

Part 1  my own scalar implementation on the `math` module only (no numpy): sRGB -> linear ->
        XYZ(D65) -> CIELAB -> CIEDE2000, WCAG 2.x contrast, and source-over compositing done
        with exact Fractions. Written from the published formulae.
Part 2  a's and b's OWN functions, lifted from their source text by AST (function defs and
        constant tables only - none of their sweeps, prints or file writes execute), evaluated
        on the same inputs at full precision, so the three columns are comparable past 2 dp.
Part 3  palette set equality: a's and b's own palette-building statements (AST-lifted by line
        range, prints stubbed) against my own build.
Part 4  model-free re-derivation of the headline numbers (NORMAL and ACHROMATIC vision only -
        I deliberately carry no CVD model, so nothing here can agree with a or b by sharing one).

No simulation, no model import, no tracked file touched. Writes outputs/_bm_colour_x_check.txt.
"""
import ast
import hashlib
import math
import random
import sys
import time
from fractions import Fraction

ROOT = "E:/Projects/SAS"
OUT_TXT = ROOT + "/outputs/_bm_colour_x_check.txt"
A_PY = ROOT + "/outputs/_bm_colour_a.py"
B_PY = ROOT + "/outputs/_bm_colour_b.py"
T0 = time.time()
_LINES = []


def P(s=""):
    s = str(s)
    _LINES.append(s)
    print(s)
    sys.stdout.flush()


# ---------------------------------------------------------------------------------------------
# Part 1 - own maths
# ---------------------------------------------------------------------------------------------
M = ((0.4124564, 0.3575761, 0.1804375),
     (0.2126729, 0.7151522, 0.0721750),
     (0.0193339, 0.1191920, 0.9503041))
D65 = (0.95047, 1.0, 1.08883)
LAB_EPS = 216.0 / 24389.0
LAB_KAPPA = 24389.0 / 27.0


def hx(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def tohex(t):
    return "#%02x%02x%02x" % tuple(t)


def s2l(v8):
    c = v8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def flab(t):
    return t ** (1.0 / 3.0) if t > LAB_EPS else (LAB_KAPPA * t + 16.0) / 116.0


def lab_normal(rgb, snap):
    """snap=True : an R=G=B input is returned exactly neutral (a*=b*=0), as instrument a does.
       snap=False: nominal D65 white, nothing snapped, as instrument b does (greys keep ~2e-5 chroma,
                   because the matrix's Y row sums to 1.0000001, not 1)."""
    r, g, b = (s2l(v) for v in rgb)
    X = M[0][0] * r + M[0][1] * g + M[0][2] * b
    Y = M[1][0] * r + M[1][1] * g + M[1][2] * b
    Z = M[2][0] * r + M[2][1] * g + M[2][2] * b
    fx, fy, fz = flab(X / D65[0]), flab(Y / D65[1]), flab(Z / D65[2])
    L, a_, b_ = 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)
    if snap and rgb[0] == rgb[1] == rgb[2]:
        a_ = b_ = 0.0
    return (L, a_, b_)


def lum709(rgb):
    r, g, b = (s2l(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def lab_achrom(rgb):
    """grey of the Rec.709 relative luminance, exactly neutral."""
    return (116.0 * flab(lum709(rgb)) - 16.0, 0.0, 0.0)


def de00(l1, l2):
    """CIEDE2000, kL=kC=kH=1, after Sharma, Wu & Dalal (2005) eqs (2)-(22)."""
    L1, a1, b1 = l1
    L2, a2, b2 = l2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb7 = ((C1 + C2) / 2.0) ** 7
    G = 0.5 * (1.0 - math.sqrt(Cb7 / (Cb7 + 25.0 ** 7)))
    a1p, a2p = (1.0 + G) * a1, (1.0 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = 0.0 if (a1p == 0.0 and b1 == 0.0) else math.degrees(math.atan2(b1, a1p)) % 360.0
    h2p = 0.0 if (a2p == 0.0 and b2 == 0.0) else math.degrees(math.atan2(b2, a2p)) % 360.0
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0.0:
        dhp = 0.0
    else:
        d = h2p - h1p
        dhp = d if abs(d) <= 180.0 else (d - 360.0 if d > 180.0 else d + 360.0)
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2.0))
    Lbp, Cbp = (L1 + L2) / 2.0, (C1p + C2p) / 2.0
    if C1p * C2p == 0.0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180.0:
        hbp = (h1p + h2p) / 2.0
    elif h1p + h2p < 360.0:
        hbp = (h1p + h2p + 360.0) / 2.0
    else:
        hbp = (h1p + h2p - 360.0) / 2.0
    T = (1.0 - 0.17 * math.cos(math.radians(hbp - 30.0)) + 0.24 * math.cos(math.radians(2.0 * hbp))
         + 0.32 * math.cos(math.radians(3.0 * hbp + 6.0)) - 0.20 * math.cos(math.radians(4.0 * hbp - 63.0)))
    dth = 30.0 * math.exp(-(((hbp - 275.0) / 25.0) ** 2))
    Rc = 2.0 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    Sl = 1.0 + 0.015 * (Lbp - 50.0) ** 2 / math.sqrt(20.0 + (Lbp - 50.0) ** 2)
    Sc = 1.0 + 0.045 * Cbp
    Sh = 1.0 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2.0 * dth)) * Rc
    q = (dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh)
    return math.sqrt(max(q, 0.0))


def de_neutral(L1, L2):
    """CIEDE2000 between two exactly neutral colours collapses to |dL|/S_L (C'=0 kills dC', dH', R_T)."""
    Lb = (L1 + L2) / 2.0
    return abs(L2 - L1) / (1.0 + 0.015 * (Lb - 50.0) ** 2 / math.sqrt(20.0 + (Lb - 50.0) ** 2))


def wcag_lum(rgb, thr):
    out = []
    for v in rgb:
        c = v / 255.0
        out.append(c / 12.92 if c <= thr else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def wcag_cr(rgb1, rgb2, thr=0.03928):
    l1, l2 = wcag_lum(rgb1, thr), wcag_lum(rgb2, thr)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def over_frac(src, alpha, dst):
    """source-over in sRGB byte space, exact rational arithmetic, round-half-up = floor(x + 1/2)."""
    return tuple(int(math.floor(alpha * s + (1 - alpha) * d + Fraction(1, 2))) for s, d in zip(src, dst))


A22, A18 = Fraction(22, 100), Fraction(18, 100)
DEPOT = hx("#770099")
WHITE, BLACK = (255, 255, 255), (0, 0, 0)

P("=" * 100)
P("_bm_colour_x_check.py - third instrument x (python %s, math + fractions only for its own numbers)" % sys.version.split()[0])
for pth in (A_PY, B_PY):
    P("  sha256 %s  %s" % (hashlib.sha256(open(pth, "rb").read()).hexdigest()[:16], pth))
P("=" * 100)

# ---- 1a. validate my CIEDE2000 -------------------------------------------------------------
P("")
P("1a. MY CIEDE2000 vs reference pairs that exist as files on disk")
sc_src = open(ROOT + "/outputs/_sc_deltae.py", encoding="utf-8").read()
ref9 = None
for node in ast.parse(sc_src).body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "REF":
        ref9 = ast.literal_eval(node.value)
w9 = max(abs(de00(a_, b_) - e_) for a_, b_, e_ in ref9)
P("  outputs/_sc_deltae.py:52-60 REF: %d pairs, worst |err| = %.2e" % (len(ref9), w9))


def lift_table(path, name):
    for node in ast.parse(open(path, encoding="utf-8").read()).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return ast.literal_eval(node.value)


shA = lift_table(A_PY, "SHARMA")
shB = lift_table(B_PY, "SHARMA34")
P("  a's SHARMA table (a.py:358-393) rows=%d ; b's SHARMA34 (b.py:263-298) rows=%d ; tables identical: %s"
  % (len(shA), len(shB), shA == shB))
w34 = 0.0
wsym = 0.0
for n_, x_, y_, e_ in shA:
    w34 = max(w34, abs(de00(x_, y_) - e_), abs(de00(y_, x_) - e_))
    wsym = max(wsym, abs(de00(x_, y_) - de00(y_, x_)))
P("  my de00 on those 34 rows, both argument orders: worst |err| = %.2e ; worst asymmetry = %.2e" % (w34, wsym))
rnd = random.Random(7)
wn = 0.0
for _ in range(5000):
    l1_, l2_ = rnd.uniform(0, 100), rnd.uniform(0, 100)
    wn = max(wn, abs(de00((l1_, 0.0, 0.0), (l2_, 0.0, 0.0)) - de_neutral(l1_, l2_)))
P("  neutral-pair identity de00((L1,0,0),(L2,0,0)) == |dL|/S_L on 5000 random pairs: max |diff| = %.2e" % wn)
same = all(wcag_lum((v, v, v), 0.03928) == wcag_lum((v, v, v), 0.04045) for v in range(256))
P("  WCAG linearisation threshold 0.03928 (b.py:821) vs 0.04045 (a.py:80 via wcag_lum) give identical luminance"
  " for all 256 byte values: %s" % same)

# ---------------------------------------------------------------------------------------------
# Part 2 - lift a's and b's own functions
# ---------------------------------------------------------------------------------------------


def lift(path, fn_names, const_names):
    ns = {"__name__": "lifted"}
    got = []
    for node in ast.parse(open(path, encoding="utf-8").read()).body:
        keep = isinstance(node, (ast.Import, ast.ImportFrom))
        if isinstance(node, ast.FunctionDef) and node.name in fn_names:
            keep = True
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in const_names):
            keep = True
        if keep:
            exec(compile(ast.Module(body=[node], type_ignores=[]), path, "exec"), ns)
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                got.append(getattr(node, "name", None) or node.targets[0].id)
    return ns, got


A, gotA = lift(A_PY,
               {"hex2rgb", "rgb2hex", "srgb_to_linear", "_f", "linear_to_lab", "linear_to_srgb8", "lab_under",
                "de2000", "de2000_scalar", "wcag_lum", "wcag_cr", "over_pct", "lab1"},
               {"M_RGB2XYZ", "WHITE", "REC709", "EPS", "KAPPA", "MACHADO", "CONDS", "CSHORT"})
B, gotB = lift(B_PY,
               {"hex2rgb", "rgb2hex", "srgb8_to_lin", "lin_to_lab", "_p7", "de2000", "vos_xy", "xyY_to_XYZ",
                "tritan_params", "make_tritan", "sim_protan", "sim_deutan", "sim_achrom", "lab_of", "rel_lum",
                "cr", "over"},
               {"M_RGB2XYZ", "WHITE_D65", "_25_7", "M_V", "M_V_INV", "PROTAN_K", "DEUTAN_K", "SP", "CMF_485",
                "CMF_660", "CONDS", "SIMS"})
P("")
P("2. LIFTED (AST, defs + constant tables only): a -> %d objects, b -> %d objects" % (len(gotA), len(gotB)))


def A_de(h1, h2, cond):
    return float(A["de2000"](A["lab1"](h1, cond), A["lab1"](h2, cond)))


def B_de(h1, h2, cond):
    return float(B["de2000"](B["lab_of"]([B["hex2rgb"](h1)], cond), B["lab_of"]([B["hex2rgb"](h2)], cond))[0])


def X_de(h1, h2, cond, snap=True):
    if cond == "achromatic":
        return de00(lab_achrom(hx(h1)), lab_achrom(hx(h2)))
    return de00(lab_normal(hx(h1), snap), lab_normal(hx(h2), snap))


la, lb, lxs, lxr = A["lab1"]("#770099", "normal"), B["lab_of"]([hx("#770099")], "normal")[0], \
    lab_normal(hx("#770099"), True), lab_normal(hx("#ffffff"), False)
P("  Lab(#770099) normal: a=(%.6f, %.6f, %.6f)  b=(%.6f, %.6f, %.6f)  x=(%.6f, %.6f, %.6f)"
  % (tuple(la) + tuple(lb) + lxs))
P("  Lab(#ffffff) with nominal D65 and no snapping (b's path, my arithmetic) = (%.7f, %.3e, %.3e)  <- white is NOT exactly"
  % lxr)
P("  neutral in b: Y row of the matrix sums to 1.0000001. a divides by the matrix row sums and zeroes |ab|<1e-9 (a.py:57,93-95).")
lbw = B["lab_of"]([(255, 255, 255)], "normal")[0]
P("  b's own Lab(#ffffff) = (%.7f, %.3e, %.3e)" % tuple(lbw))

# ---- the six requested quantities ------------------------------------------------------------
P("")
P("3. THE REQUESTED QUANTITIES - x (mine) next to a and b at full precision; 'txt' = what a / b printed")
P("   x_snap = greys exactly neutral (a's convention) ; x_raw = nominal D65, nothing snapped (b's convention)")
P("-" * 100)
rows = [("(a) dE00(#770099,#ffffff) normal", "#770099", "#ffffff", "a.txt:326/327 64.38 ; b.txt:233/234 64.37"),
        ("(b) dE00(#770099,#000000) normal", "#770099", "#000000", "a.txt:416 34.82 ; b.txt:289 34.82")]
RES = {}
for label, h1, h2, txt in rows:
    xs, xr, av, bv = X_de(h1, h2, "normal", True), X_de(h1, h2, "normal", False), A_de(h1, h2, "normal"), B_de(h1, h2, "normal")
    RES[label[:3]] = (xs, xr, av, bv)
    P("  %-36s x_snap %.6f  x_raw %.6f | a %.6f | b %.6f | a-b %+.6f | x_snap-a %+.1e  x_raw-b %+.1e   [%s]"
      % (label, xs, xr, av, bv, av - bv, xs - av, xr - bv, txt))
# (c)
gx = lab_achrom(hx("#2f831b"))
cx_w, cx_k = de00(gx, lab_achrom(WHITE)), de00(gx, lab_achrom(BLACK))
ca_w, ca_k = A_de("#2f831b", "#ffffff", "achromatic"), A_de("#2f831b", "#000000", "achromatic")
cb_w, cb_k = B_de("#2f831b", "#ffffff", "achrom"), B_de("#2f831b", "#000000", "achrom")
P("  (c) two-tone vs #2f831b, achromatic : grey L* = %.6f (Y709 = %.8f)" % (gx[0], lum709(hx("#2f831b"))))
P("      x: dE(grey,white) %.6f  dE(grey,black) %.6f  -> max %.6f" % (cx_w, cx_k, max(cx_w, cx_k)))
P("      a: dE(grey,white) %.6f  dE(grey,black) %.6f  -> max %.6f   [a.txt:130 38.2603]" % (ca_w, ca_k, max(ca_w, ca_k)))
P("      b: dE(grey,white) %.6f  dE(grey,black) %.6f  -> max %.6f   [b.txt:131 38.2603]" % (cb_w, cb_k, max(cb_w, cb_k)))
RES["(c)"] = (max(cx_w, cx_k), max(ca_w, ca_k), max(cb_w, cb_k))
# (d)
P("  (d) depot-fill composite, #770099 @ 0.22 source-over, sRGB bytes, round-half-up")
COMPD = {}
for g in ("#2b2b2b", "#1c630b", "#459f30"):
    mine = over_frac(DEPOT, A22, hx(g))
    a_c = A["over_pct"](DEPOT, 22, hx(g))
    b_c = B["over"](DEPOT, 22, hx(g))
    exact = [float(A22 * s + (1 - A22) * d) for s, d in zip(DEPOT, hx(g))]
    COMPD[g] = mine
    P("      over %s : exact (%.2f, %.2f, %.2f) -> x %s | a %s | b %s"
      % (g, exact[0], exact[1], exact[2], tohex(mine), tohex(a_c), tohex(b_c)))
P("      [a.txt:205 burnt #3c2243 ; a.txt:190 VEG[9] #304d2a ; a.txt:186 VEG[5] #507c47 ; b.txt:153 #3c2243 ; b.txt:151 #304d2a]")
# (e)
P("  (e) WCAG 2.x contrast ratios")
e_rows = [("#770099 vs composite-over-#1c630b", DEPOT, COMPD["#1c630b"], "a.txt:442 1.01 ; b.txt:317 1.01"),
          ("#ffffff vs #770099", WHITE, DEPOT, "a.txt:484 9.36 ; b.txt:328 9.36")]
for label, c1, c2, txt in e_rows:
    P("      %-36s x %.6f | a %.6f | b %.6f   [%s]"
      % (label, wcag_cr(c1, c2), A["wcag_cr"](c1, c2), B["cr"](tohex(c1), tohex(c2)), txt))
c5 = COMPD["#459f30"]
xw, xk = wcag_cr(WHITE, c5), wcag_cr(BLACK, c5)
aw, ak = A["wcag_cr"](WHITE, c5), A["wcag_cr"](BLACK, c5)
bw, bk = B["cr"]("#ffffff", tohex(c5)), B["cr"]("#000000", tohex(c5))
P("      better of W/K vs composite-over-#459f30 (%s): x max(%.6f, %.6f) = %.6f | a %.6f | b %.6f   [a.txt:438 4.87 ; b.txt:313 4.87]"
  % (tohex(c5), xw, xk, max(xw, xk), max(aw, ak), max(bw, bk)))
# (f)
cb_hex = tohex(COMPD["#2b2b2b"])
fs, fr, fa, fb = X_de("#770099", cb_hex, "normal", True), X_de("#770099", cb_hex, "normal", False), \
    A_de("#770099", cb_hex, "normal"), B_de("#770099", cb_hex, "normal")
P("  (f) dE00(#770099, composite-over-#2b2b2b = %s) normal: x_snap %.6f  x_raw %.6f | a %.6f | b %.6f"
  "   [neither txt prints this pair]" % (cb_hex, fs, fr, fa, fb))

# ---------------------------------------------------------------------------------------------
# Part 3 - palette set equality
# ---------------------------------------------------------------------------------------------
P("")
P("4. PALETTE SETS - a's and b's own building statements (lifted by line range, prints stubbed) vs my own build")
P("-" * 100)


def lift_ranges(path, ranges, ns):
    for node in ast.parse(open(path, encoding="utf-8").read()).body:
        if any(lo <= node.lineno <= hi for lo, hi in ranges):
            exec(compile(ast.Module(body=[node], type_ignores=[]), path, "exec"), ns)
    return ns


class _PalStub(object):
    def __init__(self, entries):
        self.hex = [h for h, _ in entries]


import re as _re  # noqa: E402  (a's parse_list needs it)

nsA = {"ROOT": ROOT, "ast": ast, "re": _re, "P": lambda *a_, **k_: None, "Pal": _PalStub,
       "hex2rgb": A["hex2rgb"], "rgb2hex": A["rgb2hex"]}
lift_ranges(A_PY, [(447, 448), (453, 462), (494, 515), (660, 700)], nsA)
A_N50 = [h for h, _ in nsA["n50"]]
A_NP = nsA["build_nplus"]("literal")[0].hex
A_NPC = nsA["build_nplus"]("code")[0].hex
nsB = {"ROOT": ROOT, "ast": ast, "out": lambda *a_, **k_: None, "hex2rgb": B["hex2rgb"], "rgb2hex": B["rgb2hex"]}
lift_ranges(B_PY, [(386, 399), (432, 459), (594, 620)], nsB)
B_N50 = list(nsB["N50"])
B_NP = nsB["build_nplus"]("spec")[1]
B_NPZ = nsB["build_nplus"]("canvas")[1]

# my own build: ramps parsed from the tracked source as text, the rest are literals I read at HEAD
cfv = {}
for node in ast.parse(open(ROOT + "/common_fixed_variables.py", encoding="utf-8", errors="replace").read()).body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in (
            "VEGETATION_COLORS", "FIRE_COLORS", "SMOKE_COLORS", "BLACK_AND_WHITE_COLORS"):
        cfv[node.targets[0].id] = ([s.lower() for s in ast.literal_eval(node.value)], node.lineno)
VEG, FIRE = cfv["VEGETATION_COLORS"][0], cfv["FIRE_COLORS"][0]
SMOKE, BW = cfv["SMOKE_COLORS"][0], cfv["BLACK_AND_WHITE_COLORS"][0]
P("  common_fixed_variables.py:%d VEG n=%d  :%d FIRE n=%d  :%d SMOKE n=%d  :%d BW n=%d"
  % (cfv["VEGETATION_COLORS"][1], len(VEG), cfv["FIRE_COLORS"][1], len(FIRE), cfv["SMOKE_COLORS"][1], len(SMOKE),
     cfv["BLACK_AND_WHITE_COLORS"][1], len(BW)))
OTHERS = ["#2b2b2b",  # serve_dashboard.py:62 burnt
          "#895e00",  # :64 scorched
          "#2f4a1a",  # :163 spared vegetation
          "#00ffff", "#ff00ff", "#0066cc", "#ff8c00", "#888888", "#000000",  # :69-70 roles + fallback
          "#ffff00", "#ffa500", "#00aaff",  # :74-75 victims
          "#00ffcc",  # :201 firefighter ; :851 ff trail rgba(0,255,204)
          "#770099",  # :764-766 depot
          "#ffd75a",  # :855,:858 rgba(255,215,90)
          "#78aaff",  # :851 rgba(120,170,255)
          "#1c630b", "#ffffff"]  # :743 / :740 canvas backgrounds
X_N50 = list(dict.fromkeys(VEG + FIRE + SMOKE + OTHERS[:3] + BW + OTHERS[3:]))
GROUNDS = ([(c, "VEG[%d]" % i) for i, c in enumerate(VEG)] + [(c, "FIRE[%d]" % i) for i, c in enumerate(FIRE) if i > 0]
           + [(SMOKE[0], "smoke"), ("#2b2b2b", "burnt"), ("#895e00", "scorched"), ("#2f4a1a", "spared")]
           + [(c, "BW[%d]" % i) for i, c in enumerate(BW)])


def build(alpha_d, alpha_g, order):
    ents = list(X_N50)
    names = {h: "N50" for h in ents}
    comp = {}
    for g, nm in GROUNDS:
        c1 = over_frac(DEPOT, alpha_d, hx(g))
        if order == "spec":
            c2 = over_frac(BLACK, alpha_g, c1)
        else:
            c2 = over_frac(DEPOT, alpha_d, over_frac(BLACK, alpha_g, hx(g)))
        comp[nm] = (tohex(c1), tohex(c2))
        for h, tag in ((tohex(c1), "depot/" + nm), (tohex(c2), "grid+depot/" + nm)):
            if h not in names:
                names[h] = tag
                ents.append(h)
    return ents, names, comp


X_NP, X_NAMES, X_COMP = build(A22, A18, "spec")
X_NPC, _, X_COMPC = build(A22, A18, "canvas")
P("  N50 : |a| = %d  |b| = %d  |x| = %d   a==b: %s   a==x: %s" % (len(set(A_N50)), len(set(B_N50)), len(set(X_N50)),
                                                                 set(A_N50) == set(B_N50), set(A_N50) == set(X_N50)))
P("  N+  : |a| = %d  |b| = %d  |x| = %d   a==b: %s   a==x: %s" % (len(set(A_NP)), len(set(B_NP)), len(set(X_NP)),
                                                                 set(A_NP) == set(B_NP), set(A_NP) == set(X_NP)))
P("  N+ canvas draw order (depot OVER gridline): |a| = %d  |b| = %d  |x| = %d   a==b: %s   a==x: %s"
  % (len(set(A_NPC)), len(set(B_NPZ)), len(set(X_NPC)), set(A_NPC) == set(B_NPZ), set(A_NPC) == set(X_NPC)))
ties = []
for g, nm in GROUNDS:
    for s, d, ch in zip(DEPOT, hx(g), "RGB"):
        v = A22 * s + (1 - A22) * d
        if v - math.floor(v) == Fraction(1, 2):
            ties.append("%s.%s=%s" % (nm, ch, float(v)))
    c1 = hx(X_COMP[nm][0])
    for d, ch in zip(c1, "RGB"):
        v = (1 - A18) * d
        if v - math.floor(v) == Fraction(1, 2):
            ties.append("grid/%s.%s=%s" % (nm, ch, float(v)))
P("  exact .5 ties among the 228 composite channels (where half-up vs half-even would differ): %d  %s"
  % (len(ties), ", ".join(ties)))
A8d, A8g = Fraction(round(0.22 * 255), 255), Fraction(round(0.18 * 255), 255)
X_NP8, _, X_COMP8 = build(A8d, A8g, "spec")
ndiff = sum(1 for nm in X_COMP for k in (0, 1) if X_COMP[nm][k] != X_COMP8[nm][k])
P("  SENSITIVITY (not the task's definition): a browser stores alpha in 8 bits (0.22 -> %d/255, 0.18 -> %d/255);"
  % (round(0.22 * 255), round(0.18 * 255)))
P("     with those alphas %d of the 76 composites change by >= 1 LSB in some channel" % ndiff)

# ---------------------------------------------------------------------------------------------
# Part 4 - headline re-derivations, normal + achromatic only
# ---------------------------------------------------------------------------------------------
P("")
P("5. HEADLINES RE-DERIVED BY x (no CVD model in this script)")
P("-" * 100)
LABN = {h: lab_normal(hx(h), True) for h in X_NP}
LABA = {h: lab_achrom(hx(h)) for h in X_NP}
for h in ("#824bff", "#ff00ff"):
    LABN.setdefault(h, lab_normal(hx(h), True))
    LABA.setdefault(h, lab_achrom(hx(h)))


def multitone(tones, pal, labs):
    best = None
    for e in pal:
        sc = max(de00(labs[t], labs[e]) for t in tones)
        if best is None or sc < best[0]:
            best = (sc, e)
    return best


# H1 flat ceiling
t1 = time.time()
palL = sorted(LABA[h][0] for h in X_N50)
lin_tab = [s2l(v) for v in range(256)]
vals = list(range(0, 256, 5))
best = (-1.0, None)
top = []
for r in vals:
    for g in vals:
        yrg = 0.2126 * lin_tab[r] + 0.7152 * lin_tab[g]
        for b in vals:
            L = 116.0 * flab(yrg + 0.0722 * lin_tab[b]) - 16.0
            m = min(de_neutral(L, pl) for pl in palL)
            if m > 2.70:
                top.append((m, (r, g, b)))
top.sort(key=lambda t: (-t[0], t[1]))
P("  H1 FLAT CEILING. For every colour worst-of-5 <= its ACHROMATIC score, so max over the grid of the achromatic")
P("     score is an upper bound on the ceiling under ANY dichromat model; it is attained where the other four exceed it.")
P("     achromatic-only sweep of the 140608-colour grid vs N50 (x): top 5 = %s   [%.0fs]"
  % ("  ".join("%s %.4f" % (tohex(c), m) for m, c in top[:5]), time.time() - t1))
c0 = "#050541"
n0 = min((de00(lab_normal(hx(c0), True), LABN[h]), h) for h in X_N50)
P("     at %s: x normal-vision min vs N50 = %.4f (%s) ; a.txt:112 prot=17.53 deut=20.73 trit=9.78 ; b.txt:114 pro=15.34 deu=19.53 tri=9.11"
  % (c0, n0[0], n0[1]))
P("     -> all four non-achromatic conditions exceed the achromatic score in BOTH dichromat models, so the ceiling is model-independent.")
gaps = []
for i in range(len(palL) - 1):
    a2, b2 = palL[i], palL[i + 1]
    for _ in range(200):
        mid = (a2 + b2) / 2.0
        if de_neutral(mid, palL[i]) < de_neutral(mid, palL[i + 1]):
            a2 = mid
        else:
            b2 = mid
    gaps.append((de_neutral(a2, palL[i]), palL[i], palL[i + 1], a2))
gmax = max(gaps)
P("     continuous bound: the largest achromatic gap of N50 is L* %.4f..%.4f; the best possible grey sits at L* %.4f and scores %.4f"
  % (gmax[1], gmax[2], gmax[3], gmax[0]))
P("     -> the 5-step grid value (%.4f) is within %.4f of the supremum over ALL colours (%.4f)." % (top[0][0], gmax[0] - top[0][0], gmax[0]))

# H2 two-tone vs N50
tn = multitone(["#ffffff", "#000000"], X_N50, LABN)
ta = multitone(["#ffffff", "#000000"], X_N50, LABA)
P("  H2 TWO-TONE vs N50 : x normal %.4f at %s ; x achromatic %.4f at %s   [a.txt:126,130 40.3162/38.2603 ; b.txt:127,131 40.3162/38.2603]"
  % (tn[0], tn[1], ta[0], ta[1]))
# H3 two/three-tone vs N+
t2n = multitone(["#ffffff", "#000000"], X_NP, LABN)
t2a = multitone(["#ffffff", "#000000"], X_NP, LABA)
P("  H3 TWO-TONE vs N+  : x normal %.4f at %s (%s) ; x achromatic %.4f at %s (%s)   [a.txt:311,315 40.0370/36.9038 ; b.txt:227 40.04/36.9038]"
  % (t2n[0], t2n[1], X_NAMES[t2n[1]], t2a[0], t2a[1], X_NAMES[t2a[1]]))
for X in ("#770099", "#ff00ff", "#824bff"):
    t3n = multitone(["#000000", "#ffffff", X], X_NP, LABN)
    t3a = multitone(["#000000", "#ffffff", X], X_NP, LABA)
    P("     THREE-TONE X=%s : x normal %.4f at %s ; x achromatic %.4f at %s ; gain over two-tone %+.4f / %+.4f"
      % (X, t3n[0], t3n[1], t3a[0], t3a[1], t3n[0] - t2n[0], t3a[0] - t2a[0]))
# H4 field min
f_n = min((de00(LABN["#770099"], LABN[h]), h) for h in X_NP if h != "#770099")
f_a = min((de00(LABA["#770099"], LABA[h]), h) for h in X_NP if h != "#770099")
nobw = [h for h in X_NP if not X_NAMES[h].startswith(("depot/BW", "grid+depot/BW"))]
f_n2 = min((de00(LABN["#770099"], LABN[h]), h) for h in nobw if h != "#770099")
LABNC = {h: lab_normal(hx(h), True) for h in X_NPC}
f_nc = min((de00(LABNC["#770099"], LABNC[h]), h) for h in X_NPC if h != "#770099")
P("  H4 FIELD #770099 vs N+ (self excluded): x normal %.4f nearest %s (%s) ; x achromatic %.4f nearest %s (%s)"
  % (f_n[0], f_n[1], X_NAMES[f_n[1]], f_a[0], f_a[1], X_NAMES[f_a[1]]))
P("     [a.txt:222 16.80 #523759 / 0.05 #543f5b ; b.txt:162 16.80 #523759 / 0.05 #543f5b]")
P("     without the 22 BW-ground composites (%d entries): x normal %.4f nearest %s (%s)   [b.txt:174 17.22 #4d3354 ; a does not report it]"
  % (len(nobw), f_n2[0], f_n2[1], X_NAMES[f_n2[1]]))
P("     canvas draw order N+ (%d entries): x normal %.4f nearest %s   [a.txt:222 16.80 ; b.txt:347 16.80]" % (len(X_NPC), f_nc[0], f_nc[1]))
# H5 identity
idn = min(X_de("#770099", "#ffffff", "normal"), X_de("#770099", "#000000", "normal"))
ida = min(X_de("#770099", "#ffffff", "achromatic"), X_de("#770099", "#000000", "achromatic"))
P("  H5 IDENTITY #770099 vs {#ffffff,#000000}: x normal %.4f ; x achromatic %.4f   [a.txt:416 34.82 ... 19.70 ; b.txt:289 34.82 ... 19.70]"
  % (idn, ida))
P("     dichromat columns: a 32.02/31.55/30.73 ; b 31.74/32.78/27.10 - all above the achromatic 19.70 in both, so 'worst' is model-free.")
# H6 WCAG
W15 = [(c, "VEG[%d]" % i) for i, c in enumerate(VEG)] + [("#2b2b2b", "burnt"), ("#895e00", "scorched"), (SMOKE[0], "smoke")]


def wmin(hexes):
    return min((max(wcag_cr(WHITE, hx(h)), wcag_cr(BLACK, hx(h))), h) for h in hexes)


w_d = wmin([X_COMP[nm][0] for _, nm in W15])
w_g = wmin([X_COMP[nm][1] for _, nm in W15])
w_gc = wmin([X_COMPC[nm][1] for _, nm in W15])
w_d38 = wmin([X_COMP[nm][0] for _, nm in GROUNDS])
w_g38 = wmin([X_COMP[nm][1] for _, nm in GROUNDS])
w_b = wmin([c for c, _ in W15])
P("  H6 WCAG min of better-of-white/black: x depot composites (15 grounds) %.4f at %s ; x gridlined composites (15) %.4f at %s ;"
  % (w_d[0], w_d[1], w_g[0], w_g[1]))
P("     x bare (15) %.4f at %s   [a.txt:448 4.87 #507c47 ; a.txt:465 4.65 #836d89 ; a.txt:482 4.79 #2f831b ; b.txt:326 4.87 #507c47 ; b has no gridlined WCAG]"
  % (w_b[0], w_b[1]))
P("     gridlined composites in CANVAS draw order (15): %.4f at %s ; over ALL 38 grounds: depot %.4f at %s, gridlined %.4f at %s"
  % (w_gc[0], w_gc[1], w_d38[0], w_d38[1], w_g38[0], w_g38[1]))
P("     theoretical floor of better-of-white/black over ANY colour = sqrt(1.05/0.05) = %.4f (at luminance %.4f)"
  % (math.sqrt(21.0), math.sqrt(1.05 * 0.05) - 0.05))
m77 = min((wcag_cr(DEPOT, hx(X_COMP[nm][k])), X_COMP[nm][k]) for _, nm in W15 for k in (0, 1))
P("     #770099 alone vs the 30 depot-tinted entries: min %.4f at %s   [a.txt:483 1.01 #304d2a]" % m77)
# 8-bit alpha sensitivity on the headlines that involve composites
LAB8N = {h: lab_normal(hx(h), True) for h in X_NP8}
LAB8A = {h: lab_achrom(hx(h)) for h in X_NP8}
s3 = multitone(["#000000", "#ffffff", "#770099"], X_NP8, LAB8A)
s4 = min((de00(LAB8N["#770099"], LAB8N[h]), h) for h in X_NP8 if h != "#770099")
s6d = wmin([X_COMP8[nm][0] for _, nm in W15])
s6g = wmin([X_COMP8[nm][1] for _, nm in W15])
P("  SENSITIVITY to 8-bit alpha (56/255, 46/255), N+ = %d entries: three-tone achromatic %.4f at %s ; field normal %.4f at %s ;"
  % (len(X_NP8), s3[0], s3[1], s4[0], s4[1]))
P("     WCAG depot %.4f at %s ; WCAG gridlined %.4f at %s" % (s6d[0], s6d[1], s6g[0], s6g[1]))

# ---- near-neutral cross-term: why a and b differ by 0.01 in a handful of normal-vision cells ----
P("")
P("6. WHY a AND b DIFFER IN THE 2nd DECIMAL ON A FEW NORMAL-VISION CELLS (grey-vs-chromatic pairs)")
P("-" * 100)
for h1, h2, txt in (("#770099", "#ffffff", "a 64.38 / b 64.37"), ("#770099", "#ababab", "a 49.25 / b 49.24"),
                    ("#ff66ff", "#ffffff", "a 36.62 / b 36.61"), ("#ff00ff", "#2b2b2b", "a 49.05 / b 49.04"),
                    ("#ff00ff", "#ababab", "a 33.07 / b 33.06")):
    P("  dE(%s,%s): x_snap %.5f  x_raw %.5f | a %.5f | b %.5f | a-b %+.5f   [%s]"
      % (h1, h2, X_de(h1, h2, "normal", True), X_de(h1, h2, "normal", False), A_de(h1, h2, "normal"),
         B_de(h1, h2, "normal"), A_de(h1, h2, "normal") - B_de(h1, h2, "normal"), txt))
worst = (0.0, None)
for h in X_NP:
    for t in ("#ffffff", "#000000", "#770099", "#ababab", "#818181"):
        d = abs(A_de(t, h, "normal") - B_de(t, h, "normal"))
        if d > worst[0]:
            worst = (d, (t, h))
P("  max |a-b| under NORMAL vision over {#ffffff,#000000,#770099,#ababab,#818181} x N+ (%d pairs): %.5f at %s"
  % (5 * len(X_NP), worst[0], worst[1]))
worst = (0.0, None)
for h in X_NP:
    for t in ("#ffffff", "#000000", "#770099", "#ababab", "#818181"):
        d = abs(A_de(t, h, "achromatic") - B_de(t, h, "achrom"))
        if d > worst[0]:
            worst = (d, (t, h))
P("  max |a-b| under ACHROMATIC vision over the same pairs: %.2e at %s" % (worst[0], worst[1]))

# ---------------------------------------------------------------------------------------------
# Part 7 - mechanical side-by-side of everything both instruments PRINTED (text reading only)
# ---------------------------------------------------------------------------------------------
import json  # noqa: E402

P("")
P("7. SIDE BY SIDE OF WHAT a AND b PRINTED (RESULT_JSON lines + the 4a per-condition rows), 2-dp values")
P("-" * 100)
a_txt = open(ROOT + "/outputs/_bm_colour_a.txt", encoding="utf-8").read().splitlines()
b_txt = open(ROOT + "/outputs/_bm_colour_b.txt", encoding="utf-8").read().splitlines()
JA = json.loads([l for l in a_txt if l.startswith("RESULT_JSON_FULL=")][0].split("=", 1)[1])
JB = json.loads([l for l in b_txt if l.startswith("RESULT_JSON=")][0].split("=", 1)[1])
MUST = []     # (label, a, b) normal / achromatic cells - must agree
SPREAD = []   # (label, a, b) dichromat cells - models differ by design


def must(label, a_v, b_v):
    MUST.append((label, a_v, b_v))


# the a.txt flat ceiling / two-tone are printed to 4 dp in the body even though its JSON rounds to 2
fa = [l for l in a_txt if l.strip().startswith("#050541  2.")][0].split()
must("flat ceiling (4dp, a.txt:112 / b JSON)", float(fa[1]), JB["flat_ceiling"])
P("  flat ceiling colour: a %s | b %s" % (JA["flat_ceiling_colour"], JB["flat_ceiling_colour"]))
ta_ = [l for l in a_txt if "achromatic   min over 50 entries" in l][0]
must("two-tone vs N50 (4dp, a.txt:130 / b JSON)", float(ta_.split("=")[1].split()[0]), JB["two_tone_score"])
t3_ = [l for l in a_txt if "achromatic   min over 126 entries" in l][0]
must("two-tone vs N+ achromatic (4dp, a.txt:315 / b JSON)", float(t3_.split("=")[1].split()[0]), JB["two_tone_vs_nplus"])
for k in ("n50_count", "nplus_count"):
    must(k, JA[k], JB[k])
must("N+ canvas-order count", JA["nplus_codeorder_count"], JB["nplus_canvas_zorder_count"])
must("depot hue", JA["depot_hue_deg"], JB["depot_hue"])
must("depot chroma", JA["depot_chroma"], JB["depot_chroma"])
bper = {}
for l in b_txt[161:172]:
    hx_ = l.split()[0]
    bper[hx_] = dict((kv.split("=")[0], float(kv.split("=")[1])) for kv in l.split("|")[1].split())
for fa_, fb_ in zip(JA["field_candidates"], JB["field_candidates"]):
    assert fa_["hex"] == fb_["hex"]
    h = fa_["hex"]
    must("4a %s normal_min" % h, fa_["normal_min"], fb_["normal_min"])
    must("4a %s achromatic" % h, fa_["per_cond"]["achr"], bper[h]["ach"])
    must("4a %s worst_min (both bound by achromatic)" % h, fa_["worst_min"], fb_["worst_min"])
    if fa_["normal_nearest"] != fb_["normal_nearest"]:
        P("  !! 4a %s nearest differs: a %s b %s" % (h, fa_["normal_nearest"], fb_["normal_nearest"]))
    for ka, kb in (("prot", "pro"), ("deut", "deu"), ("trit", "tri")):
        SPREAD.append(("4a %s %s" % (h, ka), fa_["per_cond"][ka], bper[h][kb]))
for key in ("best_any", "best_family", "best_any_not_in_palette", "best_family_not_in_palette"):
    for i, (ra, rb) in enumerate(zip(JA[key], JB[key])):
        if ra["hex"] != rb["hex"]:
            P("  !! %s[%d] hex differs: a %s b %s" % (key, i, ra["hex"], rb["hex"]))
        must("4b %s[%d] %s normal_min" % (key, i, ra["hex"]), ra["normal_min"], rb["normal_min"])
        must("4b %s[%d] %s worst_min" % (key, i, ra["hex"]), ra["worst_min"], rb["worst_min"])
for X in JB["three_tone"]:
    ea, eb = JA["three_tone"][X], JB["three_tone"][X]
    must("4c X=%s worst_min" % X, ea["worst_min"], eb["worst_min"])
    must("4c X=%s normal_min" % X, ea["normal_min"], eb["normal_min"])
    for e in eb["entries"]:
        must("4c X=%s entry %s normal" % (X, e), ea["entries"][e]["normal"], eb["entries"][e]["normal"])
        must("4c X=%s entry %s field-alone normal" % (X, e), ea["entries"][e]["field_alone_normal"], eb["entries"][e]["field_only_normal"])
        both_ach = ea["entries"][e]["worst_cond"] == "achromatic" and eb["entries"][e]["worst_cond"] == "achrom"
        (must if both_ach else (lambda *a_: SPREAD.append(a_)))(
            "4c X=%s entry %s worst-of-5" % (X, e), ea["entries"][e]["worst"], eb["entries"][e]["worst"])
        SPREAD.append(("4c X=%s entry %s field-alone worst-of-5" % (X, e), ea["entries"][e]["field_alone_worst"], eb["entries"][e]["field_only_worst"]))
IDB = dict(JB["identity"])
IDB.update(JB["identity_extra"])
for X, vb in IDB.items():
    va = JA["identity"][X]
    must("4d identity %s normal" % X, va["norm"], vb["normal"])
    must("4d identity %s achromatic" % X, va["achr"], vb["achrom"])
    for ka, kb in (("prot", "protan"), ("deut", "deutan"), ("trit", "tritan")):
        SPREAD.append(("4d identity %s %s" % (X, ka), va[ka], vb[kb]))
    SPREAD.append(("4d identity %s WORST" % X, va["worst"], vb["worst"]))
must("4e WCAG min better-of-W/K, 15 depot composites", JA["wcag"]["depot/"]["min_better_wk"], JB["wcag_min_better_wb_composites"])
wa = dict((l.split()[1], [float(v) for v in l.split()[2:5]]) for l in a_txt if l.strip().startswith("depot/"))
wb = dict((l.split()[1], [float(v) for v in l.split()[2:5]]) for l in b_txt if l.strip().startswith("depot>"))
for h in wb:
    for j, nm in enumerate(("white", "black", "#770099")):
        must("4e WCAG %s vs %s" % (nm, h), wa[h][j], wb[h][j])
bad = [(lab_, x_, y_) for lab_, x_, y_ in MUST if abs(x_ - y_) > 0.05]
nz = [(lab_, x_, y_) for lab_, x_, y_ in MUST if abs(x_ - y_) > 1e-9]
P("  NORMAL / ACHROMATIC / count cells compared: %d ; max |a-b| = %.4f ; cells over the 0.05 tolerance: %d"
  % (len(MUST), max(abs(x_ - y_) for _, x_, y_ in MUST), len(bad)))
for lab_, x_, y_ in bad:
    P("    !! OVER TOLERANCE %-60s a %s  b %s" % (lab_, x_, y_))
P("  cells that differ at all (%d):" % len(nz))
for lab_, x_, y_ in nz:
    P("     %-64s a %-9s b %-9s diff %+.4f" % (lab_, x_, y_, x_ - y_))
P("  DICHROMAT cells (Machado 2009 vs Vienot 1999 / Brettel 1997) - spread reported, not an error: %d cells" % len(SPREAD))
for tag in ("prot", "deut", "trit"):
    sub = [(abs(x_ - y_), lab_, x_, y_) for lab_, x_, y_ in SPREAD if lab_.endswith(tag)]
    sub.sort(reverse=True)
    P("     %-4s: n=%d  median |a-b| = %.2f  max |a-b| = %.2f (%s: a %.2f, b %.2f)"
      % (tag, len(sub), sorted(s[0] for s in sub)[len(sub) // 2], sub[0][0], sub[0][1], sub[0][2], sub[0][3]))
for lab_, x_, y_ in SPREAD:
    if lab_.endswith("WORST") and abs(x_ - y_) > 1e-9:
        P("     identity worst-of-5 differs: %-28s a %.2f  b %.2f" % (lab_, x_, y_))
w5 = [(abs(x_ - y_), lab_, x_, y_) for lab_, x_, y_ in SPREAD if "worst-of-5" in lab_ and abs(x_ - y_) > 1e-9]
P("     4c worst-of-5 cells not bound by achromatic in both, or field-alone, that differ: %d ; largest %s"
  % (len(w5), "%.2f (%s: a %.2f, b %.2f)" % max(w5) if w5 else "-"))
P("  a-only / b-only numbers (no counterpart to compare): a: WCAG gridlined 4.65, WCAG bare-15 4.79, '#770099-dropped' family list,")
P("     X=#7d00fa three-tone, q8 table ; b: 104-entry no-BW subset (17.22), tritan variants V1/V2, gamma-space achromatic variants.")

P("")
P("elapsed %.1f s" % (time.time() - T0))
with open(OUT_TXT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(_LINES) + "\n")
