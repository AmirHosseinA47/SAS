"""Independent CIEDE2000 re-check of the chosen scorched colour against every
colour that can co-occur on the map. No third-party deps; validated against
three Sharma et al. reference pairs before use.
"""
import math

def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def lab(h):
    h = h.lstrip('#')
    r, g, b = (_lin(int(h[i:i+2], 16)) for i in (0, 2, 4))
    X = (0.4124564*r + 0.3575761*g + 0.1804375*b) / 0.95047
    Y = (0.2126729*r + 0.7151522*g + 0.0721750*b) / 1.00000
    Z = (0.0193339*r + 0.1191920*g + 0.9503041*b) / 1.08883
    f = lambda t: t ** (1/3) if t > 216/24389 else (841/108) * t + 4/29
    fx, fy, fz = f(X), f(Y), f(Z)
    return (116*fy - 16, 500*(fx - fy), 200*(fy - fz))

def de2000(l1, l2):
    L1, a1, b1 = l1; L2, a2, b2 = l2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb**7 / (Cb**7 + 25**7))) if Cb > 0 else 0.5
    a1p, a2p = (1+G)*a1, (1+G)*a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0
    dLp = L2 - L1; dCp = C2p - C1p
    if C1p*C2p == 0: dhp = 0
    elif abs(h2p-h1p) <= 180: dhp = h2p - h1p
    elif h2p-h1p > 180: dhp = h2p - h1p - 360
    else: dhp = h2p - h1p + 360
    dHp = 2*math.sqrt(C1p*C2p)*math.sin(math.radians(dhp)/2)
    Lbp = (L1+L2)/2; Cbp = (C1p+C2p)/2
    if C1p*C2p == 0: hbp = h1p + h2p
    elif abs(h1p-h2p) <= 180: hbp = (h1p+h2p)/2
    elif h1p+h2p < 360: hbp = (h1p+h2p+360)/2
    else: hbp = (h1p+h2p-360)/2
    T = (1 - 0.17*math.cos(math.radians(hbp-30)) + 0.24*math.cos(math.radians(2*hbp))
         + 0.32*math.cos(math.radians(3*hbp+6)) - 0.20*math.cos(math.radians(4*hbp-63)))
    dth = 30*math.exp(-((hbp-275)/25)**2)
    Rc = 2*math.sqrt(Cbp**7/(Cbp**7+25**7)) if Cbp > 0 else 0
    Sl = 1 + (0.015*(Lbp-50)**2)/math.sqrt(20+(Lbp-50)**2)
    Sc = 1 + 0.045*Cbp; Sh = 1 + 0.015*Cbp*T
    Rt = -math.sin(math.radians(2*dth))*Rc
    return math.sqrt((dLp/Sl)**2 + (dCp/Sc)**2 + (dHp/Sh)**2
                     + Rt*(dCp/Sc)*(dHp/Sh))

# validation against Sharma et al. reference pairs
REF = [((50.0,2.6772,-79.7751),(50.0,0.0,-82.7485),2.0425),
       ((50.0,3.1571,-77.2803),(50.0,0.0,-82.7485),2.8615),
       ((50.0,2.5,0.0),(50.0,0.0,-2.5),4.3065),
       ((50.0,2.5,0.0),(73.0,25.0,-18.0),27.1492),
       ((50.0,2.5,0.0),(50.0,3.1736,0.5854),1.0000),
       ((50.0,2.5,0.0),(50.0,3.2972,0.0),1.0000),
       ((60.2574,-34.0099,36.2677),(60.4626,-34.1751,39.4387),1.2644),
       ((22.7233,20.0904,-46.6940),(23.0331,14.9730,-42.5619),2.0373),
       ((2.0776,0.0795,-1.1350),(0.9033,-0.0636,-0.5514),0.9082)]
worst=0.0
for a,b,exp in REF:
    got = de2000(a,b); worst=max(worst,abs(got-exp))
    assert abs(got-exp) < 1e-3, (a,b,got,exp)
print("CIEDE2000 validated on %d Sharma et al. reference pairs, worst err %.2e" % (len(REF), worst))

VEG = ["#414141","#9eff89","#85e370","#72d05c","#62c14c","#459f30",
       "#389023","#2f831b","#236f11","#1c630b","#175808","#124b05"]
FIRE = ["#414141","#d8d675","#eae740","#fefa01","#fed401","#feaa01",
        "#fe7001","#fe5501","#fe3e01","#fe2f01","#fe2301","#fe0101"]
OTHER = {"#ababab":"smoke","#2b2b2b":"BURNT","#2f4a1a":"spared veg",
         "#1c630b":"canvas bg","#00ffff":"UAV searcher","#ff00ff":"UAV tracker",
         "#0066cc":"UAV relay","#ff8c00":"UAV confirmer","#888888":"UAV RTB",
         "#000000":"black/dead","#ffff00":"victim cand","#ffa500":"victim conf",
         "#00aaff":"victim assigned","#00ffcc":"firefighter","#ffd75a":"assign line"}
PAL = {}
for i,c in enumerate(VEG): PAL[c] = PAL.get(c,"") or "VEG[%d]"%i
for i,c in enumerate(FIRE): PAL.setdefault(c,"FIRE[%d]"%i)
for c,n in OTHER.items(): PAL.setdefault(c,n)

def grid(h):  # canvas composites the 0.18-alpha black gridline over the cell
    h=h.lstrip('#'); return '#%02x%02x%02x' % tuple(int(round(int(h[i:i+2],16)*0.82)) for i in (0,2,4))

for CAND in ("#895e00","#2b2b2b"):
    ds = sorted((de2000(lab(CAND), lab(c)), c, n) for c,n in PAL.items() if c != CAND)
    print("\n=== %s ===" % CAND)
    print("  min dE2000 over %d co-occurring colours: %.2f  (%s %s)"
          % (len(ds), ds[0][0], ds[0][1], ds[0][2]))
    for d,c,n in ds[:6]:
        print("     %6.2f  %-9s %s" % (d,c,n))
print("\nKEY PAIR  scorched vs burnt")
print("  #895e00 vs #2b2b2b, plain      : %.2f" % de2000(lab("#895e00"), lab("#2b2b2b")))
print("  same, both under the gridline  : %.2f"
      % de2000(lab(grid("#895e00")), lab(grid("#2b2b2b"))))
print("  STATUS QUO #2b2b2b vs #2b2b2b  : %.2f" % de2000(lab("#2b2b2b"), lab("#2b2b2b")))
print("\nSANITY  is the candidate in any locked-against list?")
print("  in VEGETATION_COLORS:", "#895e00" in VEG,
      "| in FIRE_COLORS:", "#895e00" in FIRE,
      "| == smoke:", "#895e00"=="#ababab",
      "| == spared veg:", "#895e00"=="#2f4a1a",
      "| == burnt:", "#895e00"=="#2b2b2b")
