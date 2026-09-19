"""Adversarial verification of task C (extvar). Independent re-derivation from raw harness JSON.
Does NOT import or run _fm2_diag_extvar.py. Read-only; prints to stdout.
usage: .venv/Scripts/python.exe outputs/_fm2_verify_extvar.py
"""
import json
import math
import os
import collections
import itertools
import random

import numpy as np

OUT = r"E:\Projects\SAS\outputs"
N = 50
STEPS = 240
INF = 10 ** 9
ARMS = ["fmES", "fmEFS", "fmF", "fmFS"]
CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "def", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
TUPLES = CANON + FRESH

# analyst section-2 table columns (tuple delta w1 kind Dn Ts out sat), copied from the report as read
ANALYST = {
"fmES": """east/half/101 +178 47 ext 47 51 51 87
east/half/202 +133 101 ext 101 105 105 138
east/half/303 -20 109 ext 109 114 114 150
east/half/404 +388 15 ext 15 21 21 57
east/half/505 +77 111 ext 111 117 117 147
south/half/101 -3 207 ext 207 222 - -
south/half/202 -212 124 ext 124 129 129 156
south/half/303 -58 106 ext 106 111 111 156
south/half/404 +217 14 ext 14 18 18 51
south/half/505 +280 100 ext 100 105 105 147
east/def/101 +591 33 ext 33 39 39 75
east/def/202 -125 54 ext 54 60 60 90
east/def/303 -1 175 ext 175 210 213 222
east/half/606 +492 44 ext 44 48 48 87
east/half/707 +0 - - - - - -
east/half/808 -37 85 ext 85 90 90 126
east/half/909 +339 121 ext 121 126 126 156
east/half/1010 +614 51 ext 51 57 57 90
south/half/606 +246 45 ext 45 51 51 84
south/half/707 +0 205 ext 205 210 - -
south/half/808 +0 - - - - - -
south/half/909 +0 - - - - - -
south/half/1010 -232 67 ext 67 72 72 117""",
"fmEFS": """east/half/101 +33 39 clr_u 69 99 - 84
east/half/202 +182 96 clr_u 138 138 - 138
east/half/303 +107 105 clr_u 126 141 144 150
east/half/404 +167 10 clr_u 84 108 - 51
east/half/505 -19 78 clr_u 90 129 - 126
south/half/101 -7 41 clr_u 141 174 - 84
south/half/202 +100 119 clr_u 162 186 - 153
south/half/303 +56 104 clr_u 111 135 - 153
south/half/404 +64 9 clr_u 69 84 - 51
south/half/505 +206 92 clr_s 96 96 96 138
east/def/101 +194 27 clr_u 63 78 - 69
east/def/202 +289 51 clr_u 63 81 - 90
east/def/303 +107 172 clr_s 177 177 177 219
east/half/606 +283 38 clr_u 69 90 - 87
east/half/707 +0 - - - - - -
east/half/808 +18 81 clr_u 99 117 117 126
east/half/909 -77 47 clr_u 93 117 - 93
east/half/1010 +105 46 clr_u 106 111 - 87
south/half/606 +8 38 clr_u 84 102 - 81
south/half/707 +0 203 clr_s 207 207 - -
south/half/808 +0 - - - - - -
south/half/909 +0 - - - - - -
south/half/1010 +163 67 ext 67 72 72 117""",
"fmF": """east/half/101 -9 39 clr_u 69 99 - 84
east/half/202 +209 96 clr_u 138 138 - 138
east/half/303 +127 105 clr_u 126 141 144 150
east/half/404 +165 10 clr_u 84 108 - 51
east/half/505 +30 78 clr_u 90 129 - 126
south/half/101 -7 41 clr_u 141 174 - 84
south/half/202 +98 119 clr_u 162 186 - 153
south/half/303 +138 104 clr_u 111 153 - 153
south/half/404 +64 9 clr_u 69 84 - 51
south/half/505 +199 94 clr_s 99 99 99 138
east/def/101 +233 27 clr_u 63 78 - 69
east/def/202 +515 51 clr_u 63 87 - 90
east/def/303 +129 172 clr_s 177 177 177 219
east/half/606 +292 38 clr_u 69 90 - 87
east/half/707 +0 - - - - - -
east/half/808 +33 81 clr_u 99 117 117 126
east/half/909 -9 47 clr_u 93 117 - 93
east/half/1010 +37 46 clr_u 114 135 - 87
south/half/606 +277 38 clr_u 84 102 - 81
south/half/707 +0 203 clr_s 207 207 - -
south/half/808 +0 - - - - - -
south/half/909 +0 - - - - - -
south/half/1010 +139 69 clr_u 81 108 - 117""",
"fmFS": """east/half/101 +48 39 clr_u 69 99 - 84
east/half/202 +186 96 clr_u 138 138 - 138
east/half/303 +126 105 clr_u 126 141 144 150
east/half/404 +167 10 clr_u 84 108 - 51
east/half/505 -19 78 clr_u 90 129 - 126
south/half/101 -7 41 clr_u 141 174 - 84
south/half/202 +150 119 clr_u 162 186 - 153
south/half/303 +57 104 clr_u 111 153 - 153
south/half/404 +64 9 clr_u 69 84 - 51
south/half/505 +100 92 clr_s 96 96 96 138
east/def/101 +184 27 clr_u 63 78 - 69
east/def/202 +369 51 clr_u 63 87 - 90
east/def/303 +129 172 clr_s 177 177 177 219
east/half/606 +284 38 clr_u 69 90 - 87
east/half/707 +0 - - - - - -
east/half/808 +60 81 clr_u 99 117 117 126
east/half/909 -32 47 clr_u 93 117 - 93
east/half/1010 +168 46 clr_u 111 135 - 87
south/half/606 +124 38 clr_u 84 102 - 81
south/half/707 +0 203 clr_s 207 207 - -
south/half/808 +0 - - - - - -
south/half/909 +0 - - - - - -
south/half/1010 +200 67 clr_u 75 105 - 117""",
}


def lab(t):
    return "%s/%s/%d" % t


def fpath(tag, t):
    return os.path.join(OUT, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], t[1], t[2]))


def nt(s):
    """first fire tick strictly after step s"""
    return (s // 3 + 1) * 3


def ticks_in(a, b):
    """multiples of 3 in (a, b]"""
    return b // 3 - a // 3


def k2c(k):
    x, y = k.split(",")
    return int(x), int(y)


def med(v):
    v = sorted(v)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


GX, GY = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")


def extract(d):
    R = {}
    fgf = d["fire_ground_final"]
    R["hb"] = np.zeros((N, N), bool)
    R["burnt"] = np.zeros((N, N), bool)
    for k, v in fgf.items():
        x, y = k2c(k)
        R["hb"][x, y] = bool(v[0])
        R["burnt"][x, y] = bool(v[1])
    R["ncells"] = len(fgf)
    R["ever"] = int(R["hb"].sum())
    R["cleared"] = int(d.get("fire_cleared_unburned_final") or 0)
    R["intact"] = 2500 - R["ever"] - R["cleared"]
    R["bi"] = {k2c(k): v for k, v in d["burn_intervals"].items()}
    B = np.zeros((STEPS + 1, N, N), bool)
    for (x, y), ivs in R["bi"].items():
        for a, b in ivs:
            B[a:(STEPS + 1 if b is None else b), x, y] = True
    R["B"] = B
    R["dig"] = d["fire_digests"]
    R["term"] = d.get("terminal_step")
    R["seed"] = int(d["seed"])
    R["counters"] = d.get("firefight_counters")
    W = []
    for r in d.get("firefight_log") or []:
        if r.get("wrote"):
            W.append((int(r["step"]), (int(r["target"][0]), int(r["target"][1])), r["action"], r.get("scorched")))
    W.sort()
    R["W"] = W
    return R


def classify_writes(R):
    """kind by my own rule: ext; clr_s if the cell has a completed burn interval ending <= step; else clr_u"""
    out = []
    flag_mismatch = 0
    ext_end_mismatch = 0
    for s, c, act, sc in R["W"]:
        ivs = R["bi"].get(c, [])
        if act == "extinguish":
            kind = "ext"
            if not any(b == s for a, b in ivs):
                ext_end_mismatch += 1
        else:
            hb_before = any(b is not None and b <= s for a, b in ivs)
            kind = "clr_s" if hb_before else "clr_u"
            if bool(sc) != hb_before:
                flag_mismatch += 1
        out.append((s, c, kind))
    return out, flag_mismatch, ext_end_mismatch


def latch_grid(R, kinds):
    L = np.full((N, N), INF, dtype=np.int64)
    wcell = {}
    dup = 0
    for s, c, kind in kinds:
        if c in wcell:
            dup += 1
        else:
            wcell[c] = (s, kind)
    problems = []
    fuel_obs = []
    for x in range(N):
        for y in range(N):
            c = (x, y)
            ivs = R["bi"].get(c, [])
            if c in wcell:
                s, kind = wcell[c]
                if kind in ("ext", "clr_s"):
                    T1 = nt(s)
                    if T1 <= STEPS:
                        L[x, y] = T1
                        if not R["burnt"][x, y]:
                            problems.append(("written-not-burnt", c))
                else:
                    if R["burnt"][x, y] or R["hb"][x, y]:
                        problems.append(("clr_u-burnt", c))
            elif R["burnt"][x, y]:
                if not ivs or any(b is None for a, b in ivs):
                    problems.append(("burnt-no-closed-interval", c))
                    continue
                end = max(b for a, b in ivs)
                if end % 3:
                    problems.append(("latch-off-tick", c))
                L[x, y] = end
                fuel_obs.append((c, sum(ticks_in(a, b) for a, b in ivs)))
    return L, wcell, dup, problems, fuel_obs


def cone_entry(kinds):
    e = np.full((N, N), INF, dtype=np.int64)
    dmin = np.full((N, N), INF, dtype=np.int64)
    if not kinds:
        return e, dmin
    arr = np.array([(s, c[0], c[1]) for s, c, k in kinds], dtype=np.int64)
    for i in range(0, len(arr), 200):
        ch = arr[i:i + 200]
        s = ch[:, 0][:, None, None]
        d = np.maximum(np.abs(GX[None] - ch[:, 1][:, None, None]), np.abs(GY[None] - ch[:, 2][:, None, None]))
        m = -(-d // 3)
        ent = np.where(d == 0, s, 3 * (s // 3 + m))
        e = np.minimum(e, ent.min(axis=0))
        dmin = np.minimum(dmin, d.min(axis=0))
    return e, dmin


def spearman(a, b):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2.0
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def auc(up, dn):
    if not up or not dn:
        return None
    s = 0.0
    for u in up:
        for d in dn:
            s += 1.0 if u > d else 0.5 if u == d else 0.0
    return s / (len(up) * len(dn))


def auc_exact_p(vals, is_up):
    obs = auc([v for v, u in zip(vals, is_up) if u], [v for v, u in zip(vals, is_up) if not u])
    n, k = len(vals), sum(is_up)
    cnt = tot = 0
    for comb in itertools.combinations(range(n), k):
        cs = set(comb)
        a = auc([vals[i] for i in cs], [vals[i] for i in range(n) if i not in cs])
        tot += 1
        if abs(a - 0.5) >= abs(obs - 0.5) - 1e-12:
            cnt += 1
    return obs, cnt / tot


def main():
    runs = {arm: {} for arm in ARMS}
    offs = {}
    fuel = collections.defaultdict(list)   # (seed, cell) -> [f0 obs]
    v1_bad = v1_n = 0
    latch_problems = collections.Counter()
    flag_mm = ext_end_mm = dup_writes = 0
    counter_mm = []
    base_rate = []   # for first extinguish: OFF burning cells at the same step whose flame ends at nt(s)
    for t in TUPLES:
        O = extract(json.load(open(fpath("fmOFF", t), encoding="utf-8")))
        for (x, y), ivs in O["bi"].items():
            for a, b in ivs:
                if a != 1:
                    v1_n += 1
                    v1_bad += a % 3 != 0
                if b is not None:
                    v1_n += 1
                    v1_bad += b % 3 != 0
        okinds, _, _ = classify_writes(O)
        LO, _, _, prob, fobs = latch_grid(O, okinds)
        for p in prob:
            latch_problems[("fmOFF",) + (p[0],)] += 1
        for c, f0 in fobs:
            fuel[(O["seed"], c)].append(f0)
        O["L"] = LO
        offs[t] = O
        for arm in ARMS:
            A = extract(json.load(open(fpath(arm, t), encoding="utf-8")))
            kinds, fm, em = classify_writes(A)
            flag_mm += fm
            ext_end_mm += em
            LA, wcell, dup, prob, fobs = latch_grid(A, kinds)
            dup_writes += dup
            for p in prob:
                latch_problems[(arm, p[0])] += 1
            for c, f0 in fobs:
                fuel[(A["seed"], c)].append(f0)
            S = {"t": t, "delta": A["intact"] - O["intact"], "kinds": kinds, "term": A["term"],
                 "ever": A["ever"], "cleared": A["cleared"], "seed": A["seed"], "off_ever": O["ever"]}
            cn = A["counters"] or {}
            ne = sum(1 for k in kinds if k[2] == "ext")
            ncl = sum(1 for k in kinds if k[2] != "ext")
            nu = sum(1 for k in kinds if k[2] == "clr_u")
            if (cn.get("extinguished"), cn.get("cleared"), cn.get("cleared_unburned")) != (ne, ncl, nu):
                counter_mm.append((arm, lab(t), cn, ne, ncl, nu))
            # digest attribution
            dd = next((i + 1 for i, (a, b) in enumerate(zip(A["dig"], O["dig"])) if a != b), None)
            S["dig_div"] = dd
            S["w1"] = kinds[0][0] if kinds else None
            S["w1kinds"] = sorted(set(k[2] for k in kinds if k[0] == S["w1"])) if kinds else []
            # draw shift
            diff = LA != LO
            Ts = u0 = None
            causes = []
            if diff.any():
                mn = np.minimum(LA, LO)
                m0 = int(mn[diff].min())
                if m0 + 3 <= STEPS:
                    Ts = m0 + 3
                    cells = np.argwhere(diff & (mn == m0))
                    u0 = min(int(x) * N + int(y) for x, y in cells)
                    for x, y in sorted(cells.tolist(), key=lambda c: c[0] * N + c[1]):
                        c = (x, y)
                        if c in wcell and wcell[c][0] < Ts:
                            causes.append((c, wcell[c][1], int(LA[x, y]), int(LO[x, y])))
                        else:
                            causes.append((c, "natural", int(LA[x, y]), int(LO[x, y])))
            S["Ts"], S["u0"], S["causes"] = Ts, u0, causes
            e, dmin = cone_entry(kinds)
            D = A["B"] ^ O["B"]
            stp = np.arange(STEPS + 1)[:, None, None]
            inside = e[None] <= stp
            Din = (D & inside).sum(axis=(1, 2))
            Dout = (D & ~inside).sum(axis=(1, 2))
            S["Din"], S["Dout"] = Din, Dout
            Dtot = Din + Dout
            S["Dn"] = next((i for i in range(1, STEPS + 1) if Dtot[i]), None)
            S["out"] = next((i for i in range(1, STEPS + 1) if Dout[i]), None)
            S["sat"] = int(e.max()) if kinds and e.max() <= STEPS else None
            # V4: outside cells at Ts all at uid >= u0 ; negative control one tick later
            if Ts is not None and Dout[Ts]:
                cells = np.argwhere(D[Ts] & ~(e <= Ts))
                S["v4_bad"] = sum(1 for x, y in cells if x * N + y < u0)
                if Ts + 3 <= STEPS:
                    cells2 = np.argwhere(D[Ts + 3] & ~(e <= Ts + 3))
                    S["v4_ctrl"] = sum(1 for x, y in cells2 if x * N + y < u0)
            # pre-Ts one-signedness
            lim = Ts if Ts is not None else STEPS + 1
            armb = A["B"][1:lim]
            offb = O["B"][1:lim]
            S["v5_cellsteps"] = int((armb & ~offb).sum())
            everA = armb.any(axis=0)
            everO = offb.any(axis=0)
            S["pre_off_only"] = int((everO & ~everA).sum())
            S["pre_arm_only"] = int((everA & ~everO).sum())
            if S["v5_cellsteps"]:
                pos = np.argwhere(armb & ~offb)
                S["v5_detail"] = sorted(set((int(p[0]) + 1, int(p[1]), int(p[2])) for p in pos))
            S["writes_before_Ts"] = sum(1 for k in kinds if Ts is None or k[0] < Ts)
            S["clru_before_Ts"] = sum(1 for k in kinds if k[2] == "clr_u" and (Ts is None or k[0] < Ts))
            S["D_Ts_minus1"] = int(Dtot[Ts - 1]) if Ts else None
            # churn
            aonly = A["hb"] & ~O["hb"]
            oonly = ~A["hb"] & O["hb"]
            S["arm_only"], S["off_only"] = int(aonly.sum()), int(oonly.sum())
            S["churn_far"] = int(((aonly | oonly) & (dmin > 6)).sum()) if kinds else 0
            # OFF growth after Ts / burning at Ts
            if Ts:
                first = {c: min(a for a, b in ivs) for c, ivs in O["bi"].items()}
                S["grw_gt"] = sum(1 for v in first.values() if v > Ts)
                S["grw_ge"] = sum(1 for v in first.values() if v >= Ts)
                S["brn_Ts"] = int(O["B"][Ts].sum())
            # extinguish detail
            ext = [(s, c) for s, c, k in kinds if k == "ext"]
            S["ext"] = ext
            S["ext_detail"] = []
            for s, c in ext:
                ivs = A["bi"].get(c, [])
                consumed = sum(ticks_in(a, b) for a, b in ivs if b is not None and b <= s)
                S["ext_detail"].append({"s": s, "c": c, "consumed": consumed, "after_term": A["term"] is not None and s > A["term"]})
            if ext:
                s1 = ext[0][0]
                S["ext1_cells"] = [c for s, c in ext if s == s1]
                T1 = nt(s1)
                S["D_T1"] = int(Dtot[T1]) if T1 <= STEPS else None
                if Ts is not None:
                    S["D_Ts_in_out"] = (int(Din[Ts]), int(Dout[Ts]))
                oc = []
                for c in S["ext1_cells"]:
                    ivs = O["bi"].get(c, [])
                    cur = [(a, b) for a, b in ivs if a <= s1 and (b is None or s1 < b)]
                    later = [(a, b) for a, b in ivs if a > s1]
                    oend = cur[0][1] if cur else None
                    olatch = int(LO[c]) if LO[c] < INF else None
                    oc.append({"c": c, "off_burning": bool(cur), "off_end": oend, "off_latch": olatch,
                               "reignite": bool(later)})
                    if arm == "fmES" and cur and c == S["ext1_cells"][0]:
                        # base rate over all OFF burning cells at step s1 in this run
                        tot = endnext = relater = 0
                        for cc, ivv in O["bi"].items():
                            for a, b in ivv:
                                if a <= s1 and (b is None or s1 < b):
                                    tot += 1
                                    endnext += (b == nt(s1))
                                    relater += any(a2 > s1 for a2, b2 in ivv)
                        base_rate.append((lab(t), endnext, tot, relater, (cur[0][1] == nt(s1)), bool(later)))
                S["ext1_off"] = oc
            S["L"] = LA
            S["fb"] = np.where(A["B"].any(axis=0), np.argmax(A["B"], axis=0), INF)
            S["intact"] = A["intact"]
            runs[arm][t] = S
            del A
        O["fb"] = np.where(O["B"].any(axis=0), np.argmax(O["B"], axis=0), INF)
        del O["B"]

    # --------------------------------------------------------------- reports
    print("=" * 100)
    print("0. ROUND-1 NUMBERS")
    for arm in ARMS:
        for nm, tt in (("canonical", CANON), ("fresh", FRESH)):
            ds = [runs[arm][t]["delta"] for t in tt]
            print("  %-6s %-9s up %2d down %2d same %2d pooled %+d" % (
                arm, nm, sum(d > 0 for d in ds), sum(d < 0 for d in ds), sum(d == 0 for d in ds), sum(ds)))
        allv = [runs[arm][t]["delta"] for t in TUPLES]
        dd = [runs[arm][t]["delta"] for t in TUPLES if t[1] != "def"]
        print("  %-6s all23 pooled %+d up %d down %d same %d | dedup20 pooled %+d up %d down %d same %d" % (
            arm, sum(allv), sum(d > 0 for d in allv), sum(d < 0 for d in allv), sum(d == 0 for d in allv),
            sum(dd), sum(d > 0 for d in dd), sum(d < 0 for d in dd), sum(d == 0 for d in dd)))
        att = collections.Counter()
        for t in TUPLES:
            S = runs[arm][t]
            if S["w1"] is None:
                att["nowrite-identical" if S["dig_div"] is None else "nowrite-DIFF"] += 1
            else:
                att["exact" if S["dig_div"] == S["w1"] else "VIOLATION"] += 1
        kc = collections.Counter(k[2] for t in TUPLES for k in runs[arm][t]["kinds"])
        print("         attribution %s | writes by kind %s total clears %d" % (dict(att), dict(kc), kc["clr_s"] + kc["clr_u"]))
    print("  counter mismatches:", counter_mm[:5], "n", len(counter_mm))
    print("  scorched-flag vs my interval rule mismatches:", flag_mm, " extinguish without interval ending at write step:", ext_end_mm, " duplicate write cells:", dup_writes)

    print("=" * 100)
    print("1. INSTRUMENTS")
    print("  V1 OFF boundaries off tick: %d of %d" % (v1_bad, v1_n))
    print("  latch problems:", dict(latch_problems))
    nobs = sum(len(v) for v in fuel.values())
    vals = [x for v in fuel.values() for x in v]
    conflicts = sum(1 for v in fuel.values() if len(set(v)) > 1)
    print("  V2 fuel obs %d keys %d range %s..%s conflicts %d hist(one per key) %s" % (
        nobs, len(fuel), min(vals), max(vals), conflicts,
        dict(sorted(collections.Counter(v[0] for v in fuel.values()).items()))))
    # V3/V4
    v3 = []
    v4n = v4bad = v4ctrl_runs = v4ctrl_cells = 0
    for arm in ARMS:
        for t in TUPLES:
            S = runs[arm][t]
            if S["out"] is not None and (S["Ts"] is None or S["out"] < S["Ts"]):
                v3.append((arm, lab(t), S["out"], S["Ts"]))
            if "v4_bad" in S:
                v4n += 1
                v4bad += S["v4_bad"] > 0
                if S.get("v4_ctrl"):
                    v4ctrl_runs += 1
                    v4ctrl_cells += S["v4_ctrl"]
    print("  V3 outside-cone D before Ts:", v3)
    print("  V4 runs with outside D at Ts %d, violating %d; control one tick later below-u0 on %d runs (%d cells)" % (
        v4n, v4bad, v4ctrl_runs, v4ctrl_cells))

    print("=" * 100)
    print("2. PER-RUN TABLE COMPARISON vs ANALYST (delta w1 kind Dn Ts out sat)")
    for arm in ARMS:
        mism = []
        for line in ANALYST[arm].splitlines():
            tok = line.split()
            tl = tok[0].split("/")
            t = (tl[0], tl[1], int(tl[2]))
            S = runs[arm][t]
            mine = [S["delta"], S["w1"], "+".join(S["w1kinds"]) if S["w1kinds"] else None, S["Dn"], S["Ts"], S["out"], S["sat"]]
            theirs = [int(tok[1])] + [None if x == "-" else (x if i == 2 else int(x)) for i, x in enumerate(tok[2:], start=1)]
            if mine != theirs:
                mism.append((lab(t), "mine", mine, "analyst", theirs))
        print("  %-6s mismatches %d" % (arm, len(mism)))
        for m in mism:
            print("     ", m)

    print("=" * 100)
    print("3. fmES SHIFT MECHANICS")
    es = runs["fmES"]
    n_T1p3 = 0
    exc = []
    rem1_check = collections.Counter()
    for t in TUPLES:
        S = es[t]
        if not S["ext"]:
            continue
        s1 = S["ext"][0][0]
        T1 = nt(s1)
        rems = []
        for dd_, oc in zip([x for x in S["ext_detail"] if x["s"] == s1], S["ext1_off"]):
            f0 = fuel.get((S["seed"], dd_["c"]))
            r = (f0[0] - dd_["consumed"]) if f0 else None
            rems.append(r)
            if r is not None:
                rem1_check["agree" if (r == 1) == (oc["off_latch"] == T1) else "disagree"] += 1
        if S["Ts"] == T1 + 3:
            n_T1p3 += 1
        else:
            exc.append((lab(t), s1, S["Ts"], rems, [o["off_latch"] for o in S["ext1_off"]]))
    print("  Ts == nt(ext1)+3 on %d of %d runs with an extinguish; exceptions %s" % (
        n_T1p3, sum(1 for t in TUPLES if es[t]["ext"]), exc))
    print("  remaining fuel 1 <=> OFF latches at nt(ext1):", dict(rem1_check))
    outeq = [(lab(t), es[t]["out"], es[t]["Ts"]) for t in TUPLES if es[t]["ext"] and es[t]["Ts"] == nt(es[t]["ext"][0][0]) + 3]
    n_eq = sum(1 for _, o, ts in outeq if o == ts)
    print("  out == Ts on %d of %d; others %s" % (n_eq, len(outeq), [x for x in outeq if x[1] != x[2]]))
    io = [es[t]["D_Ts_in_out"] for t in TUPLES if es[t]["ext"] and es[t]["out"] == es[t]["Ts"] and es[t]["Ts"] == nt(es[t]["ext"][0][0]) + 3]
    print("  at Ts (runs out==Ts): inside median %s outside median %s n %d" % (med([a for a, b in io]), med([b for a, b in io]), len(io)))
    dT1 = sorted(es[t]["D_T1"] for t in TUPLES if es[t]["ext"])
    print("  |D| at nt(ext1): %s median %s" % (dT1, med(dT1)))
    print("  base rate (fmES first ext): OFF burning cells at write step whose flame ends at nt(s):",
          [(x[0], "%d/%d=%.2f" % (x[1], x[2], x[1] / x[2])) for x in base_rate])
    br_all = sum(x[1] for x in base_rate) / max(1, sum(x[2] for x in base_rate))
    rl_all = sum(x[3] for x in base_rate) / max(1, sum(x[2] for x in base_rate))
    print("  pooled base rate end-at-next-tick %.3f ; re-ignite-later base rate %.3f (n runs %d)" % (br_all, rl_all, len(base_rate)))

    def pb_tail(ps, k):
        dist = [1.0]
        for p in ps:
            nd = [0.0] * (len(dist) + 1)
            for i, q in enumerate(dist):
                nd[i] += q * (1 - p)
                nd[i + 1] += q * p
            dist = nd
        return sum(dist[k:]), sum(i * q for i, q in enumerate(dist))
    obs_end = sum(1 for x in base_rate if x[4])
    obs_rel = sum(1 for x in base_rate if x[5])
    p_end, e_end = pb_tail([x[1] / x[2] for x in base_rate], obs_end)
    p_rel, e_rel = pb_tail([x[3] / x[2] for x in base_rate], obs_rel)
    print("  first-ext cells: flame ends at next tick %d of %d (expected from same-step base rates %.1f, P(>=obs) %.4f); re-ignite later %d (expected %.1f, P(>=obs) %.3f)" % (
        obs_end, len(base_rate), e_end, p_end, obs_rel, e_rel, p_rel))
    fx = []
    for t in TUPLES:
        S = es[t]
        if S["ext"]:
            s1 = S["ext"][0][0]
            for o in S["ext1_off"][:1]:
                fx.append((lab(t), s1, o["c"], o["off_burning"], o["off_end"], o["off_latch"], o["reignite"],
                           (o["off_end"] - s1) if o["off_end"] else None))
    print("  first-ext OFF counterfactual (tuple, s, cell, burning, end, latch, reignite later, steps left):")
    for x in fx:
        print("    ", x)
    print("  steps left <= 3: %d of %d; OFF latched later (latch not None): %d; re-ignited later (separate later OFF interval): %d; latched & re-ignited %d" % (
        sum(1 for x in fx if x[7] is not None and x[7] <= 3), len(fx), sum(1 for x in fx if x[5] is not None),
        sum(1 for x in fx if x[6]), sum(1 for x in fx if x[6] and x[5] is not None)))
    lat = sorted(x[5] - x[1] for x in fx if x[5] is not None)
    print("  OFF latch - s:", lat, "median", med(lat))
    lat2 = sorted(x[5] - x[1] for x in fx if x[5] is not None and x[6])
    print("  OFF latch - s (re-ignited only):", lat2, "median", med(lat2))

    print("=" * 100)
    print("4. LAGS / CAUSES / PRE-Ts (all arms)")
    bykind = collections.defaultdict(list)
    tsdn = collections.defaultdict(list)
    for arm in ARMS:
        for t in TUPLES:
            S = runs[arm][t]
            if S["w1"] is None:
                continue
            kk = "+".join(S["w1kinds"])
            bykind[kk].append((arm, lab(t), S["Ts"] - S["w1"] if S["Ts"] else None, S["out"] - S["w1"] if S["out"] else None))
            if S["Ts"]:
                cause = S["causes"][0][1] if S["causes"] else "?"
                tsdn[(kk, cause)].append(S["Ts"] - S["Dn"])
    for kk, v in sorted(bykind.items()):
        lags = [x[2] for x in v if x[2] is not None]
        outs = [x[3] for x in v if x[3] is not None]
        print("  first write %-10s runs %2d Ts-w1 min %s med %s max %s (no shift %d) | out-w1 n %d min %s med %s max %s" % (
            kk, len(v), min(lags), med(lags), max(lags), sum(1 for x in v if x[2] is None), len(outs),
            min(outs) if outs else "-", med(outs), max(outs) if outs else "-"))
    for k, v in sorted(tsdn.items()):
        print("  Ts-Dn first-kind %-10s cause %-8s n %2d min %s med %s max %s %s" % (k[0], k[1], len(v), min(v), med(v), max(v), sorted(v)))
    for arm in ARMS:
        cc = collections.Counter((runs[arm][t]["causes"][0][1] if runs[arm][t]["causes"] else "no shift") for t in TUPLES)
        wr = [runs[arm][t] for t in TUPLES if runs[arm][t]["w1"] is not None]
        shifted = [S for S in wr if S["Ts"]]
        satb = sum(1 for S in wr if S["sat"] is not None and S["Ts"] is not None and S["sat"] < S["Ts"])
        print("  %-6s causes %s | writing runs %d shifted %d | sat<Ts %d | med Ts-w1 %s | med writes<Ts %s clr_u<Ts %s | med |D|@Ts-1 %s | pre OFF-only pooled %d arm-only pooled %d | v5 cell-steps %d in %d runs" % (
            arm, dict(cc), len(wr), len(shifted), satb, med([S["Ts"] - S["w1"] for S in shifted]),
            med([S["writes_before_Ts"] for S in shifted]), med([S["clru_before_Ts"] for S in shifted]),
            med([S["D_Ts_minus1"] for S in shifted]), sum(S["pre_off_only"] for S in wr), sum(S["pre_arm_only"] for S in wr),
            sum(S["v5_cellsteps"] for S in wr), sum(1 for S in wr if S["v5_cellsteps"])))
        for S in wr:
            if S["v5_cellsteps"]:
                det = S["v5_detail"]
                sts = sorted(set(d[0] for d in det))
                cells = sorted(set((d[1], d[2]) for d in det))
                # is each cell the OFF-latched one at Ts-3?
                print("      v5 %s %s steps %s cells %s Ts %s causes %s" % (arm, lab(S["t"]), sts, cells, S["Ts"], S["causes"]))

    print("=" * 100)
    print("5. SIGN / MEAN / SCALES")

    def signflip(v):
        v = np.array([x for x in v if x != 0], dtype=np.int64)
        n = len(v)
        signs = (((np.arange(2 ** n, dtype=np.int64)[:, None] >> np.arange(n)) & 1) * 2 - 1)
        return float((np.abs(signs @ v) >= abs(int(v.sum()))).mean())

    def binom_ge(k, n):
        return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n

    for arm in ARMS:
        for nm, sel in (("dedup20", lambda t: t[1] != "def"), ("all23", lambda t: True)):
            v = [runs[arm][t]["delta"] for t in TUPLES if sel(t)]
            up = sum(x > 0 for x in v)
            dn = sum(x < 0 for x in v)
            mean = sum(v) / len(v)
            sd1 = float(np.std(v, ddof=1))
            sd0 = float(np.std(v, ddof=0))
            pu = 0.5 * (1 + math.erf(mean / sd1 / math.sqrt(2)))
            chg = [abs(x) for x in v if x]
            print("  %-6s %-7s mean %+.1f sd(ddof1) %.1f sd(ddof0) %.1f signflip p %.4f | up %d down %d sign p %.4f | Phi(mean/sd) %.2f obs up share %.2f | med|delta| changed %s" % (
                arm, nm, mean, sd1, sd0, signflip(v), up, dn, binom_ge(up, up + dn), pu, up / (up + dn), med(chg)))

    print("=" * 100)
    print("6. fmES CORRELATES (dedup 20)")
    dd = [es[t] for t in TUPLES if t[1] != "def"]
    feats = {}
    for S in dd:
        S["f_ext1"] = S["ext"][0][0] if S["ext"] else None
        S["f_next"] = len(S["ext"])
        S["f_share_after"] = (sum(1 for x in S["ext_detail"] if x["after_term"]) / len(S["ext"])) if S["ext"] else None
        S["f_grw"] = S.get("grw_gt")
        S["f_grw_ge"] = S.get("grw_ge")
    for fname in ("f_ext1", "f_next", "f_share_after", "f_grw", "f_grw_ge"):
        rows = [(S[fname], S["delta"]) for S in dd if S[fname] is not None]
        rho = spearman([r[0] for r in rows], [r[1] for r in rows])
        rng = random.Random(12345)
        ys = [r[1] for r in rows]
        xs = [r[0] for r in rows]
        cnt = 0
        for _ in range(5000):
            yy = ys[:]
            rng.shuffle(yy)
            if abs(spearman(xs, yy)) >= abs(rho) - 1e-12:
                cnt += 1
        ch = [(r[0], r[1] > 0) for r in rows if r[1] != 0]
        a, p = auc_exact_p([c[0] for c in ch], [c[1] for c in ch])
        upm = med([c[0] for c in ch if c[1]])
        dnm = med([c[0] for c in ch if not c[1]])
        print("  %-14s n %d rho %.2f perm p %.3f | AUC %.2f exact p %.3f | up median %s down median %s" % (fname, len(rows), rho, cnt / 5000, a, p, upm, dnm))
    print("  per-run (tuple, delta, ext1, n_ext, share_after_term, grw>Ts, grw>=Ts, OFF burning at Ts):")
    for S in dd:
        print("    ", lab(S["t"]), S["delta"], S["f_ext1"], S["f_next"], None if S["f_share_after"] is None else round(S["f_share_after"], 2), S.get("grw_gt"), S.get("grw_ge"), S.get("brn_Ts"))

    print("=" * 100)
    print("7. H3 (fmES all extinguishes)")
    allx = [x for t in TUPLES for x in es[t]["ext_detail"]]
    rems = []
    for t in TUPLES:
        for x in es[t]["ext_detail"]:
            f0 = fuel.get((es[t]["seed"], x["c"]))
            if f0:
                rems.append(f0[0] - x["consumed"])
    print("  extinguishes %d, fuel0 known %d, remaining hist %s" % (len(allx), len(rems), dict(sorted(collections.Counter(rems).items()))))
    print("  after terminal %d; step >180 %d" % (sum(1 for x in allx if x["after_term"]), sum(1 for x in allx if x["s"] > 180)))

    print("=" * 100)
    print("8. fmEFS vs fmF")
    earlier = later = same = 0
    oe = ol = os_ = 0
    pre = []
    for t in TUPLES:
        E = runs["fmEFS"][t]
        F = runs["fmF"][t]
        if not E["ext"]:
            continue
        a, b = E["Ts"] or INF, F["Ts"] or INF
        earlier += a < b
        later += a > b
        same += a == b
        ao, bo = E["out"] or INF, F["out"] or INF
        oe += ao < bo
        ol += ao > bo
        os_ += ao == bo
        if E["ext"][0][0] < b:
            pre.append((lab(t), E["ext"][0][0], F["Ts"], E["Ts"], E["causes"][0][1] if E["causes"] else None, E["delta"], F["delta"]))
    print("  EFS runs with ext %d: Ts earlier %d later %d same %d; out earlier %d later %d same %d" % (earlier + later + same, earlier, later, same, oe, ol, os_))
    print("  first ext before fmF Ts:", pre)
    print("  total EFS ext %d" % sum(len(runs["fmEFS"][t]["ext"]) for t in TUPLES))

    print("=" * 100)
    print("9. CHURN")
    for arm in ARMS:
        wr = [runs[arm][t] for t in TUPLES if runs[arm][t]["w1"] is not None]
        churn = sum(S["arm_only"] + S["off_only"] for S in wr)
        far = sum(S["churn_far"] for S in wr)
        dd_ = [S for S in wr if S["t"][1] != "def"]
        dd_all = [runs[arm][t] for t in TUPLES if t[1] != "def"]
        print("  %-6s churn %d far>6 %d (%.0f%%) | dedup arm_only %d off_only %d R_ao %.3f" % (
            arm, churn, far, 100.0 * far / churn, sum(S["arm_only"] for S in dd_all), sum(S["off_only"] for S in dd_all),
            sum(S["arm_only"] for S in dd_all) / sum(S["off_only"] for S in dd_all)))

    print("=" * 100)
    print("11. EXTRA: overlap in pooled lag sets, sign-flip robustness, prereg stock measures, growth after Ts")
    for kk in ("clr_u", "clr_s", "ext"):
        v = [(arm, t) for arm in ARMS for t in TUPLES if runs[arm][t]["w1"] is not None and "+".join(runs[arm][t]["w1kinds"]) == kk]
        distinct_t = set(t for _, t in v)
        distinct_hist = set((t, runs[a][t]["w1"], runs[a][t]["Ts"], runs[a][t]["Dn"]) for a, t in v)
        print("  first-kind %-6s runs %d distinct tuples %d distinct (tuple,w1,Ts,Dn) %d" % (kk, len(v), len(distinct_t), len(distinct_hist)))
    v5set = set((t, runs[a][t]["Ts"]) for a in ARMS for t in TUPLES if runs[a][t]["v5_cellsteps"])
    print("  V5 distinct (tuple,Ts) events:", len(v5set))
    v4set = set((t, runs[a][t]["u0"], runs[a][t]["Ts"]) for a in ARMS for t in TUPLES if "v4_bad" in runs[a][t])
    print("  V4 distinct (tuple,u0,Ts) among the runs with outside D at Ts:", len(v4set))
    for nm, sel in (("canon-dedup10", lambda t: t in CANON and t[1] != "def"), ("fresh10", lambda t: t in FRESH),
                    ("east/def3", lambda t: t[1] == "def")):
        v = [runs["fmES"][t]["delta"] for t in TUPLES if sel(t)]
        print("  fmES %-14s deltas %s sum %+d signflip p %.4f" % (nm, v, sum(v), signflip(v)))
    dd_t = [t for t in TUPLES if t[1] != "def"]
    loo = []
    for drop in dd_t:
        v = [runs["fmES"][t]["delta"] for t in dd_t if t != drop]
        loo.append((signflip(v), lab(drop)))
    loo.sort()
    print("  fmES dedup leave-one-out sign-flip p: max %.4f (drop %s), min %.4f" % (loo[-1][0], loo[-1][1], loo[0][0]))
    v = sorted([runs["fmES"][t]["delta"] for t in dd_t])
    print("  fmES dedup drop top-2 (%s): p %.4f" % (v[-2:], signflip(v[:-2])))
    for arm in ("fmES", "fmF"):
        ddr = [runs[arm][t] for t in dd_t]
        wr = [S for S in ddr if S["w1"] is not None]
        d6 = [int(S["Din"][S["w1"] + 6] + S["Dout"][S["w1"] + 6]) for S in wr if S["w1"] + 6 <= STEPS]
        d30 = [int(S["Din"][S["w1"] + 30] + S["Dout"][S["w1"] + 30]) for S in wr if S["w1"] + 30 <= STEPS]
        print("  %-5s dedup: outside-cone cell-steps %d on %d runs | D6 med %s D30 med %s | BD %d | SM %d of %d | G %.4f | growth>Ts med %s Ts med %s" % (
            arm, sum(int(S["Dout"].sum()) for S in ddr), sum(1 for S in ddr if S["Dout"].sum()), med(d6), med(d30),
            sum(1 for S in ddr if S["delta"] <= -20), sum(1 for S in wr if abs(S["delta"]) <= 10), len(wr),
            sum(S["delta"] for S in ddr) / sum(S["off_ever"] for S in ddr),
            med([S["grw_gt"] for S in wr if S.get("grw_gt") is not None]), med([S["Ts"] for S in wr if S["Ts"]])))

    print("=" * 100)
    print("12. RE-ROLL YARDSTICK PAIRS (dedup, both runs reconstructed)")
    allpairs = []
    for p1, p2 in (("fmES", "OFF"), ("fmF", "OFF"), ("fmFS", "OFF"), ("fmEFS", "OFF"), ("fmF", "fmFS"), ("fmF", "fmEFS"), ("fmFS", "fmEFS")):
        rows = []
        noshift = 0
        for t in dd_t:
            R1 = runs[p1][t]
            if p2 == "OFF":
                if R1["w1"] is None:
                    continue
                L2, fb_ref, int2 = offs[t]["L"], offs[t]["fb"], offs[t]["intact"]
            else:
                R2 = runs[p2][t]
                if R1["w1"] is None and R2["w1"] is None:
                    continue
                L2, fb_ref, int2 = R2["L"], R1["fb"], R2["intact"]
            diff = R1["L"] != L2
            if not diff.any():
                noshift += 1
                continue
            m0 = int(np.minimum(R1["L"], L2)[diff].min())
            if m0 + 3 > STEPS:
                noshift += 1
                continue
            tsp = m0 + 3
            growth = int((fb_ref > tsp).sum() - (fb_ref >= INF).sum())
            rows.append((tsp, growth, abs(R1["intact"] - int2)))
        allpairs += [(p1, p2) + r for r in rows]
        ratios = [r[2] / r[1] for r in rows if r[1] > 0]
        print("  %-6s-%-6s pairs %d (no shift %d) Ts med %s growth med %s |diff| med %s ratio med %.3f ratio-of-medians %.3f" % (
            p1, p2, len(rows), noshift, med([r[0] for r in rows]), med([r[1] for r in rows]), med([r[2] for r in rows]),
            med(ratios), med([r[2] for r in rows]) / med([r[1] for r in rows])))
    print("  total pairs %d rho(|diff|, growth) %.2f" % (len(allpairs), spearman([p[3] for p in allpairs], [p[4] for p in allpairs])))

    print("=" * 100)
    print("10. fmF vs fmFS sign disagreements (runs with a write, differing fire)")
    dis = [(lab(t), runs["fmF"][t]["delta"], runs["fmFS"][t]["delta"]) for t in TUPLES
           if runs["fmF"][t]["w1"] is not None and (runs["fmF"][t]["delta"] > 0) != (runs["fmFS"][t]["delta"] > 0)]
    print("  ", dis)


if __name__ == "__main__":
    main()
