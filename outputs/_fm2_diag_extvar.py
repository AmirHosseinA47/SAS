"""firemech round 2, TASK C diagnostic - why extinguish's per-run sign is a coin flip. READ-ONLY.

usage: .venv/Scripts/python.exe outputs/_fm2_diag_extvar.py [--out outputs/_fm2_diag_extvar.txt]

Reads ONLY explicit harness JSON paths outputs/_ffr_<arm>_<wind>_<rr>_<seed>.json for the arms
fmOFF, fmES, fmEFS, fmF, fmFS on the canonical 13 + fresh 10 tuples. Never globs, never reads
outputs/_firemech_rewound_20260914/, never reads any f2* result. Runs no simulation.

DEFINITIONS (reused from outputs/_firemech_analyze.py where they exist)
  ever        fire_ground_final cells with has_burned (index 0)
  cleared     fire_cleared_unburned_final
  intact      2500 - ever - cleared;  delta = intact(arm) - intact(fmOFF), same tuple
  de-dup      east/def excluded (it shares its OFF fire with east/half at the same seed)
  B[t]        burning set in the post-step observation of step t, from burn_intervals
              ([a, b) = burning at steps a..b-1; b None = still burning at 240)
  D(t)        B_arm[t] XOR B_OFF[t]
  writes      firefight_log rows with wrote True: (step, TARGET cell, kind)
              kind ext = extinguish, clr_s = clear of a scorched cell, clr_u = clear of a
              never-burned cell (the row's scorched flag)
  tick        a step t with t % FIRE_SPREAD_SPEED(3) == 0 (Fire.steps_counter == harness step;
              verified below from the OFF interval boundaries)
  cone(t)     union over writes w with step_w <= t of the Chebyshev ball of radius 3*k(w,t)
              around the target, k = number of ticks in (step_w, t]. Built incrementally:
              dilate by 3 on every tick, then add the cells written at t.
  inside/out  |D(t) & cone(t)| / |D(t) - cone(t)|

DRAW-STREAM RECONSTRUCTION (the H1 instrument)
  Fire.step draws one random.random() per NOT-YET-burnt Fire agent per tick, in unique_id
  order = x*50+y (set_fire_agents loops x then y, DENSITY_PROB = 1, FIXED_WIND = True so
  Wind.apply_wind draws nothing; the UAV random direction draw only runs without the
  extension pipeline). A cell latched burnt at tick L still draws at L (the draw precedes the
  latch) and draws nothing from L+3 on. Latch tick per cell:
    natural burn-out      end of its last burn interval (a tick)
    extinguished at w     first tick > w (fuel 0 + has_burned -> latch on that tick's step)
    scorched clear at w   first tick > w
    never-burned clear    never (fuel 0 but not has_burned: it draws for ever)
  draw index of cell u at tick T = (draws of all earlier ticks) + (rank of u among the cells
  drawing at T). A cell's draw is ALIGNED with fmOFF iff both indices are equal.
  shift tick Ts = first tick with a misaligned cell drawing in both arms; u0 = its first uid.
  VALIDATION (reported, must hold if the reconstruction is right):
    V1 every OFF interval boundary is a tick (except the ignition cell's start 1)
    V2 fuel0 of a naturally burnt-out cell = number of ticks in (a, b] summed over its
       intervals; must lie in 7..10 and agree across every run of the same seed
    V3 no D outside the cone at any step < Ts (physics is local while draws are aligned)
    V4 every outside-cone D cell at step Ts has uid >= u0
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N = 50
CELLS = N * N
STEPS = 240
TICK = 3
NEVER = 10 ** 6

CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "def", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
ARMS = ["fmES", "fmEFS", "fmF", "fmFS"]
LAGS = [0, 3, 6, 9, 12, 15, 18, 21, 24, 30, 45, 60]

OUT: list[str] = []


def say(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def label(t):
    return "%s/%s/%d" % t


def path(tag, t):
    p = os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], t[1], t[2]))
    assert "rewound" not in p
    return p


def first_tick_after(w):
    return (w // TICK + 1) * TICK


def ticks_in(a, b):
    """number of ticks in (a, b]"""
    return b // TICK - a // TICK


# ------------------------------------------------------------------ morphology --
CHEB3 = [(dx, dy) for dx in range(-3, 4) for dy in range(-3, 4)]
DISC3 = [(dx, dy) for dx in range(-3, 4) for dy in range(-3, 4) if dx * dx + dy * dy <= 9]


def dilate(m, offs, r=3):
    pad = np.pad(m, r)
    out = np.zeros_like(m)
    for dx, dy in offs:
        out |= pad[r + dx:r + dx + N, r + dy:r + dy + N]
    return out


# ------------------------------------------------------------------ extraction --
def extract(tag, t):
    with open(path(tag, t), encoding="utf-8") as f:
        d = json.load(f)
    R = {"tag": tag, "t": t}
    ev = d["eval"]
    R["rescued"] = int(ev.get("rescued") or 0)
    R["terminal"] = ev.get("terminal_step")
    fgf = d["fire_ground_final"]
    hb = np.zeros((N, N), bool)
    bt = np.zeros((N, N), bool)
    bn = np.zeros((N, N), bool)
    for k, v in fgf.items():
        x, y = (int(z) for z in k.split(","))
        hb[x, y], bt[x, y], bn[x, y] = bool(v[0]), bool(v[1]), bool(v[2])
    R["hb"], R["bt"], R["bn"] = hb, bt, bn
    R["ever"] = int(hb.sum())
    R["cleared"] = int(d.get("fire_cleared_unburned_final") or 0)
    R["intact"] = CELLS - R["ever"] - R["cleared"]
    bi = d["burn_intervals"]
    R["bi"] = {}
    B = np.zeros((STEPS + 1, N, N), bool)
    bounds_bad = []
    for k, ivs in bi.items():
        x, y = (int(z) for z in k.split(","))
        ivs = sorted(ivs, key=lambda iv: iv[0])
        R["bi"][(x, y)] = ivs
        for a, b in ivs:
            e = STEPS + 1 if b is None else b
            B[a:e, x, y] = True
            if a == 1:
                B[0, x, y] = True
            bounds_bad.append((a, b))
    R["B"] = B
    R["bounds"] = bounds_bad
    log = d.get("firefight_log") or []
    W = []
    for r in log:
        if not r.get("wrote"):
            continue
        c = (int(r["target"][0]), int(r["target"][1]))
        if r["action"] == "extinguish":
            kind = "ext"
        elif r["action"] == "clear":
            kind = "clr_s" if r.get("scorched") else "clr_u"
        else:
            raise SystemExit("unexpected write action %r" % r["action"])
        W.append((int(r["step"]), c, kind, r["ff"], r.get("dist")))
    W.sort(key=lambda w: w[0])
    R["W"] = W
    R["counters"] = d.get("firefight_counters")
    R["digests"] = d.get("fire_digests") or []
    return R


def latch_ticks(R):
    """(L array, natural list [(cell, fuel0, last_end)], problems)"""
    L = np.full((N, N), NEVER, int)
    wmap = {}
    probs = []
    for s, c, kind, _ff, _d in R["W"]:
        if kind in ("ext", "clr_s"):
            if c in wmap:
                probs.append("double latch write on %s" % (c,))
            wmap[c] = s
    natural = []
    for c, s in wmap.items():
        tau = first_tick_after(s)
        if tau <= STEPS:
            if not R["bt"][c]:
                probs.append("written cell %s (w=%d) not burnt at end" % (c, s))
            L[c] = tau
    xs, ys = np.nonzero(R["bt"])
    for x, y in zip(xs.tolist(), ys.tolist()):
        if (x, y) in wmap:
            continue
        ivs = R["bi"].get((x, y))
        if not ivs:
            probs.append("burnt cell %s has no interval" % ((x, y),))
            continue
        a_last, b_last = ivs[-1]
        if b_last is None or b_last % TICK:
            probs.append("burnt cell %s last end %s" % ((x, y), b_last))
            continue
        L[x, y] = b_last
        fuel0 = sum(ticks_in(a, b) for a, b in ivs)
        natural.append(((x, y), fuel0))
    return L, natural, probs, wmap


def draw_alignment(LA, LO):
    ticks = np.arange(TICK, STEPS + 1, TICK)
    la, lo = LA.reshape(-1), LO.reshape(-1)
    dA = la[None, :] >= ticks[:, None]
    dO = lo[None, :] >= ticks[:, None]
    cA = np.concatenate([[0], np.cumsum(dA.sum(1))[:-1]])
    cO = np.concatenate([[0], np.cumsum(dO.sum(1))[:-1]])
    iA = cA[:, None] + np.cumsum(dA, axis=1) - 1
    iO = cO[:, None] + np.cumsum(dO, axis=1) - 1
    mis = dA & dO & (iA != iO)
    return ticks, dA, dO, mis


# ------------------------------------------------------------------ statistics --
def ranks(v):
    v = list(v)
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def spearman(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 4:
        return None, len(pairs)
    ra, rb = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return (num / den if den else None), len(pairs)


def auc(pos, neg):
    """P(value in pos > value in neg), ties 0.5 - Mann-Whitney U / (n1 n2)"""
    pos = [x for x in pos if x is not None]
    neg = [x for x in neg if x is not None]
    if not pos or not neg:
        return None
    s = 0.0
    for x in pos:
        for y in neg:
            s += 1.0 if x > y else (0.5 if x == y else 0.0)
    return s / (len(pos) * len(neg))


def binom_tail_ge(k, n):
    """one-sided P(X >= k), X ~ Bin(n, 1/2)"""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def perm_p_auc(pos, neg):
    """two-sided exact permutation p of |AUC - 0.5| over all splits of the pooled values"""
    import itertools
    pos = [x for x in pos if x is not None]
    neg = [x for x in neg if x is not None]
    if not pos or not neg:
        return None
    obs = abs(auc(pos, neg) - 0.5)
    allv = pos + neg
    n, k = len(allv), len(neg)
    hit = tot = 0
    for comb in itertools.combinations(range(n), k):
        cs = set(comb)
        ng = [allv[i] for i in comb]
        ps = [allv[i] for i in range(n) if i not in cs]
        tot += 1
        if abs(auc(ps, ng) - 0.5) >= obs - 1e-12:
            hit += 1
    return hit / tot


def perm_p_spearman(a, b, n_perm=20000):
    import random as _r
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 4:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    obs, _n = spearman(xs, ys)
    if obs is None:
        return None
    rng = _r.Random(12345)
    hit = 0
    for _ in range(n_perm):
        ys2 = ys[:]
        rng.shuffle(ys2)
        r, _n = spearman(xs, ys2)
        if r is not None and abs(r) >= abs(obs) - 1e-12:
            hit += 1
    return hit / n_perm


def med(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def fmt(x, nd=2):
    if x is None:
        return "-"
    if isinstance(x, float):
        if x.is_integer() and abs(x) >= 2:
            return str(int(x))
        return ("%." + str(nd) + "f") % x
    return str(x)


# ------------------------------------------------------------------ per-run -----
def analyse(R, O):
    t = R["t"]
    S = {"t": t, "arm": R["tag"], "delta": R["intact"] - O["intact"], "intact": R["intact"],
         "off_intact": O["intact"], "off_ever": O["ever"], "ever": R["ever"], "cleared": R["cleared"],
         "rescued": R["rescued"], "off_rescued": O["rescued"], "terminal": R["terminal"]}
    W = R["W"]
    S["n_w"] = len(W)
    S["n_ext"] = sum(1 for w in W if w[2] == "ext")
    S["n_clr_s"] = sum(1 for w in W if w[2] == "clr_s")
    S["n_clr_u"] = sum(1 for w in W if w[2] == "clr_u")
    cnt = R["counters"] or {}
    S["counter_ok"] = (int(cnt.get("extinguished", 0)) == S["n_ext"]
                       and int(cnt.get("cleared", 0)) == S["n_clr_s"] + S["n_clr_u"]
                       and int(cnt.get("cleared_unburned", 0)) == S["n_clr_u"]) if cnt else (not W)
    S["w1"] = W[0][0] if W else None
    S["w1_kind"] = W[0][2] if W else None
    term = R["terminal"]
    S["ext_before_term"] = sum(1 for w in W if w[2] == "ext" and (term is None or w[0] <= term))
    S["ext_after_term"] = sum(1 for w in W if w[2] == "ext" and term is not None and w[0] > term)
    ext_steps = [w[0] for w in W if w[2] == "ext"]
    S["ext1"] = ext_steps[0] if ext_steps else None
    S["ext_med_step"] = med(ext_steps)
    BA, BO = R["B"], O["B"]
    S["burning_at_w1"] = int(BO[S["w1"]].sum()) if W else None

    # digest divergence (round-1 attribution, re-verified)
    fa, fb = R["digests"], O["digests"]
    S["dig_div"] = next((i + 1 for i, (x, y) in enumerate(zip(fa, fb)) if x != y), None)
    S["digests"] = fa

    # cone and D series
    by_step = collections.defaultdict(list)
    for w in W:
        by_step[w[0]].append(w)
    cone = np.zeros((N, N), bool)
    din = [0] * (STEPS + 1)
    dout = [0] * (STEPS + 1)
    area = [0] * (STEPS + 1)
    first_D = first_out = sat = None
    out_masks = {}
    for s in range(1, STEPS + 1):
        if s % TICK == 0 and cone.any():
            cone = dilate(cone, CHEB3)
        for w in by_step.get(s, ()):
            cone[w[1]] = True
        D = BA[s] ^ BO[s]
        i_, o_ = int((D & cone).sum()), int((D & ~cone).sum())
        din[s], dout[s], area[s] = i_, o_, int(cone.sum())
        if first_D is None and (i_ + o_):
            first_D = s
        if first_out is None and o_:
            first_out = s
            out_masks[s] = D & ~cone
        if sat is None and area[s] == CELLS:
            sat = s
    S["din"], S["dout"], S["area"] = din, dout, area
    S["first_D"], S["first_out"], S["sat"] = first_D, first_out, sat

    # draw stream
    LA, natA, probA, wmapA = latch_ticks(R)
    LO, natO, probO, _ = latch_ticks(O)
    S["latch_problems"] = probA + probO
    S["natural_fuel"] = natA
    ticks, dA, dO, mis = draw_alignment(LA, LO)
    anym = mis.any(1)
    if anym.any():
        ti = int(np.argmax(anym))
        S["Ts"] = int(ticks[ti])
        S["u0"] = int(np.argmax(mis[ti]))
        # cells whose drawing status differs at some tick <= Ts: the shift's cause
        la, lo = LA.reshape(-1), LO.reshape(-1)
        cause = np.nonzero((la != lo) & (np.minimum(la, lo) < S["Ts"]))[0].tolist()
        kinds = []
        wk = {w[1]: w[2] for w in W}
        for u in cause:
            c = (u // N, u % N)
            kinds.append((c, wk.get(c, "natural"), int(la[u]) if la[u] < NEVER else None,
                          int(lo[u]) if lo[u] < NEVER else None))
        S["cause"] = kinds
    else:
        S["Ts"], S["u0"], S["cause"] = None, None, []
    # V3 / V4
    Ts = S["Ts"]
    lim5 = Ts if Ts is not None else STEPS + 1
    S["V5_viol"] = int((BA[1:lim5] & ~BO[1:lim5]).sum())
    # refine: the latch tick itself (Ts - 3). Fire.step sets burning False on a cell that latches
    # DURING the step pass, so higher-uid cells of the same tick already read it as not burning.
    # A cell latching in OFF but still burning in the arm on that tick is a source only in the arm.
    S["V5_strict"] = 0
    S["V5_latch_tick"] = []
    if S["V5_viol"]:
        la, lo = LA.reshape(-1), LO.reshape(-1)
        for s in range(1, lim5):
            xs, ys = np.nonzero(BA[s] & ~BO[s])
            for x, y in zip(xs.tolist(), ys.tolist()):
                tick = (s // TICK) * TICK
                expl = False
                if Ts is not None and tick == Ts - TICK:
                    u_self = x * N + y
                    if la[u_self] != lo[u_self] and min(la[u_self], lo[u_self]) == tick:
                        expl = "self"
                    else:
                        for dx, dy in DISC3:
                            u = (x + dx) * N + (y + dy)
                            if (dx, dy) != (0, 0) and 0 <= x + dx < N and 0 <= y + dy < N and u < u_self \
                                    and la[u] != lo[u] and min(la[u], lo[u]) == tick:
                                expl = "lower-uid neighbour"
                                break
                if expl:
                    S["V5_latch_tick"].append((s, (x, y), expl))
                else:
                    S["V5_strict"] += 1
    if Ts is not None:
        ba_by = BA[1:Ts].any(axis=0)
        bo_by = BO[1:Ts].any(axis=0)
        S["pre_shift_ever_arm_only"] = int((ba_by & ~bo_by).sum())
        S["pre_shift_ever_off_only"] = int((bo_by & ~ba_by).sum())
        S["pre_shift_clr_u"] = sum(1 for w in W if w[2] == "clr_u" and w[0] < Ts)
        S["pre_shift_writes"] = sum(1 for w in W if w[0] < Ts)
    else:
        S["pre_shift_ever_arm_only"] = S["pre_shift_ever_off_only"] = S["pre_shift_clr_u"] = None
        S["pre_shift_writes"] = None
    lim = Ts if Ts is not None else STEPS + 1
    S["V3_viol"] = sum(dout[s] for s in range(1, min(lim, STEPS + 1)))
    S["V4_viol"] = 0
    S["V4_next_below"] = None
    if Ts is not None and dout[Ts]:
        # rebuild the cone at Ts and at the next tick
        cone2 = np.zeros((N, N), bool)
        cones = {}
        for s in range(1, min(STEPS, Ts + TICK) + 1):
            if s % TICK == 0 and cone2.any():
                cone2 = dilate(cone2, CHEB3)
            for w in by_step.get(s, ()):
                cone2[w[1]] = True
            if s in (Ts, Ts + TICK):
                cones[s] = cone2.copy()
        D = BA[Ts] ^ BO[Ts]
        xs, ys = np.nonzero(D & ~cones[Ts])
        S["V4_viol"] = sum(1 for x, y in zip(xs.tolist(), ys.tolist()) if x * N + y < S["u0"])
        if Ts + TICK in cones:
            # negative control: one tick later every draw is misaligned, so outside-cone
            # differences below u0 become possible - they should now appear
            D2 = BA[Ts + TICK] ^ BO[Ts + TICK]
            xs, ys = np.nonzero(D2 & ~cones[Ts + TICK])
            S["V4_next_below"] = sum(1 for x, y in zip(xs.tolist(), ys.tolist()) if x * N + y < S["u0"])
    # re-roll exposure: misaligned draws of cells at risk in OFF (burning, or a burning
    # cell within euclidean 3 in the OFF observation of the previous step)
    expo = 0
    expo_ticks = []
    misn = mis.sum(1)
    for ti, T in enumerate(ticks.tolist()):
        if not misn[ti]:
            expo_ticks.append(0)
            continue
        risk = dilate(BO[T - 1], DISC3).reshape(-1)
        e = int((mis[ti] & risk).sum())
        expo += e
        expo_ticks.append(e)
    S["expo"] = expo
    S["mis_frac_240"] = float(misn[-1]) / max(1, int((dA[-1] & dO[-1]).sum()))
    # OFF growth still to come after Ts (cells first burning after Ts)
    if Ts is not None:
        first_burn_off = np.argmax(BO, axis=0)
        ever_off_any = BO.any(axis=0)
        S["off_growth_after_Ts"] = int((ever_off_any & (first_burn_off > Ts)).sum())
        S["off_burning_at_Ts"] = int(BO[Ts].sum())
    else:
        S["off_growth_after_Ts"] = None
        S["off_burning_at_Ts"] = None
    # end-state churn of has_burned
    a_only = R["hb"] & ~O["hb"]
    o_only = O["hb"] & ~R["hb"]
    S["churn_arm_only"] = int(a_only.sum())
    S["churn_off_only"] = int(o_only.sum())
    if W:
        wm = np.zeros((N, N), bool)
        for w in W:
            wm[w[1]] = True
        near = dilate(wm, CHEB3)  # Chebyshev <= 3 of any write cell
        near6 = dilate(near, CHEB3)  # <= 6
        chg = a_only | o_only
        S["churn_near6"] = int((chg & near6).sum())
        S["churn_far6"] = int((chg & ~near6).sum())
    else:
        S["churn_near6"] = S["churn_far6"] = 0
    S["frac_out_240"] = (dout[STEPS] / (din[STEPS] + dout[STEPS])) if (din[STEPS] + dout[STEPS]) else None
    # extinguish consumption (for remaining fuel, joined with fuel0 later)
    ext_cons = []
    for s, c, kind, ff, dist in W:
        if kind != "ext":
            continue
        ivs = R["bi"].get(c) or []
        consumed = sum(ticks_in(a, b) for a, b in ivs if b is not None and b <= s)
        # the OFF counterfactual of this cell at s (exact only for writes before Ts)
        off_burning = bool(BO[s][c])
        off_end = None
        for a, b in O["bi"].get(c) or []:
            if a <= s and (b is None or s < b):
                off_end = b
        ext_cons.append({"step": s, "cell": c, "consumed": consumed, "exact_cf": Ts is None or s < Ts - TICK,
                         "off_burning": off_burning, "off_end": off_end, "off_latch": int(LO[c]) if LO[c] < NEVER else None,
                         "after_term": term is not None and s > term,
                         "nb_burning": int(sum(1 for dx, dy in DISC3 if (dx, dy) != (0, 0)
                                               and 0 <= c[0] + dx < N and 0 <= c[1] + dy < N
                                               and BA[s][c[0] + dx, c[1] + dy]))})
    S["ext_cons"] = ext_cons
    return S


# ------------------------------------------------------------------ pre-registered rule --
# Written and frozen BEFORE any f2c* result was read (none has been read by this file's author).
# Stock values it is anchored to (de-dup 20, printed in section 8): fmES median |delta| 214.5, G 0.0731.
STOCK_ES_MEDIAN_ABS = 214.5
STOCK_ES_G = 0.0731


def prereg_measures(es_rows, f_rows):
    def block(rows):
        dd = [S for S in rows if S["t"][1] != "def"]
        up = sum(1 for S in dd if S["delta"] > 0)
        dn = sum(1 for S in dd if S["delta"] < 0)
        nc = up + dn
        wr = [S for S in dd if S["w1"] is not None]
        chg = [abs(S["delta"]) for S in dd if S["delta"]]
        allv = [S["delta"] for S in dd]
        mean = sum(allv) / len(allv)
        v = np.array([x for x in allv if x != 0], dtype=np.int64)
        if len(v):
            signs = (((np.arange(2 ** len(v), dtype=np.int64)[:, None] >> np.arange(len(v))) & 1) * 2 - 1)
            pflip = float((np.abs(signs @ v) >= abs(int(v.sum()))).mean())
        else:
            pflip = None
        d6 = [S["din"][S["w1"] + 6] + S["dout"][S["w1"] + 6] for S in wr if S["w1"] + 6 <= STEPS]
        d30 = [S["din"][S["w1"] + 30] + S["dout"][S["w1"] + 30] for S in wr if S["w1"] + 30 <= STEPS]
        attrib_bad = sum(1 for S in dd if not ((S["w1"] is not None and S["dig_div"] == S["w1"])
                                               or (S["w1"] is None and S["dig_div"] is None)))
        return {
            "n": len(dd), "up": up, "down": dn, "same": len(dd) - nc, "S": (up / nc) if nc else None,
            "p_sign": binom_tail_ge(up, nc) if nc else None, "M": med(chg),
            "G": sum(S["delta"] for S in dd) / max(1, sum(S["off_ever"] for S in dd)),
            "BD": sum(1 for S in dd if S["delta"] <= -20), "n_write": len(wr),
            "SM": sum(1 for S in wr if abs(S["delta"]) <= 10), "mean": mean, "p_flip": pflip,
            "D6": med(d6), "D30": med(d30), "outside_total": sum(sum(S["dout"]) for S in dd),
            "outside_runs": sum(1 for S in dd if sum(S["dout"])), "attrib_bad": attrib_bad,
            "R_ao": sum(S["churn_arm_only"] for S in dd) / max(1, sum(S["churn_off_only"] for S in dd)),
        }
    return block(es_rows), block(f_rows)


def prereg_verdict(E, F, crn):
    lines = []
    valid = E["attrib_bad"] == 0 and F["attrib_bad"] == 0
    if crn:
        valid = valid and E["outside_total"] == 0 and F["outside_total"] == 0
    lines.append("VALIDITY: attribution violations ES %d F %d; outside-cone D total ES %d (%d runs) F %d (%d runs)"
                 " -> %s" % (E["attrib_bad"], F["attrib_bad"], E["outside_total"], E["outside_runs"],
                             F["outside_total"], F["outside_runs"],
                             ("VALID" if valid else "INVALID - no inference") if crn else
                             "(stock dry run: outside-cone D is EXPECTED here, the re-roll produces it)"))
    f_cons = F["S"] is not None and F["S"] >= 0.80 and F["p_sign"] <= 0.05
    e_cons = E["S"] is not None and E["S"] >= 0.80 and E["p_sign"] <= 0.05
    e_mixed = E["S"] is not None and E["S"] <= 0.65
    lines.append("CONTROL f2cF-type sign: %d up / %d down / %d same, S %s p %s -> %s" % (
        F["up"], F["down"], F["same"], fmt(F["S"]), fmt(F["p_sign"], 4), "consistent" if f_cons else "NOT consistent"))
    lines.append("ES: %d up / %d down / %d same, S %s p_sign %s | M %s | G %.4f (F %.4f) | BD %d | SM %d of %d |"
                 " mean %+.1f p_flip %s | median |D| +6 %s +30 %s | R_ao %.3f (F %.3f)" % (
                     E["up"], E["down"], E["same"], fmt(E["S"]), fmt(E["p_sign"], 4), fmt(E["M"]), E["G"], F["G"],
                     E["BD"], E["SM"], E["n_write"], E["mean"], fmt(E["p_flip"], 4), fmt(E["D6"], 0), fmt(E["D30"], 0),
                     E["R_ao"], F["R_ao"]))
    if not crn:
        branch = ("near-inert" if (E["n_write"] and E["SM"] >= 0.5 * E["n_write"] and abs(E["G"]) <= 0.01
                                   and (E["D30"] or 0) <= 10)
                  else "consistent" if e_cons else "mixed-with-large-downs" if (e_mixed and E["BD"] >= 2)
                  else "between thresholds")
        lines.append("RULE BRANCH ON STOCK DATA: %s. This only describes the stock coin flip (the re-roll is present"
                     " here); it is not a diagnosis - only CRN data can be diagnosed by this rule." % branch)
        return lines
    if not valid:
        verdict = "NO VERDICT (invalid probe)"
    elif E["n_write"] and E["SM"] >= 0.5 * E["n_write"] and abs(E["G"]) <= 0.01 and (E["D30"] or 0) <= 10:
        verdict = "H3: extinguish is physically near-inert here (late / going-out cells); sign uninformative"
    elif e_cons:
        g_ref = 0.5 * F["G"] if F["G"] > 0 else 0.5 * STOCK_ES_G
        if E["G"] >= g_ref:
            verdict = "H1: the stock coin flip was the draw re-roll; extinguish's own effect is one-signed and not small"
        else:
            verdict = "H1 + H4: the stock coin flip was the re-roll; extinguish's own effect is one-signed but small"
    elif e_mixed and E["BD"] >= 2:
        if f_cons:
            verdict = ("H2: extinguish's effect is two-signed WITHOUT any re-roll (physical front redirection or"
                       " closed-loop physics); the coin flip is not a stream artefact")
        else:
            verdict = ("INCONCLUSIVE: without the re-roll BOTH mechanics are two-signed; closed-loop physics, not"
                       " the stream, sets the sign; H1 vs H2 not separable by this probe")
    else:
        verdict = "INCONCLUSIVE (between the thresholds)"
    lines.append("VERDICT: " + verdict)
    return lines


def narrative(rows):
    """The report's reading of the data sections. Every number is taken from the computed rows / STATE."""
    V = STATE["val"]
    fuel0 = STATE["fuel0"]
    flip = STATE["flip"]
    yard = STATE["yard"]
    fbfb = STATE["fbfb"]
    corr = STATE["corr"]
    E_st, F_st = STATE["prereg_stock"]
    es, ff = rows["fmES"], rows["fmF"]
    L = []
    w = L.append

    def dirc(arm, sel):
        rr = [S for S in rows[arm] if sel(S)]
        return (sum(1 for S in rr if S["delta"] > 0), sum(1 for S in rr if S["delta"] < 0),
                sum(1 for S in rr if S["delta"] == 0), sum(S["delta"] for S in rr))
    canon, fresh = set(CANON), set(FRESH)
    esc, esf = dirc("fmES", lambda S: S["t"] in canon), dirc("fmES", lambda S: S["t"] in fresh)
    es23 = dirc("fmES", lambda S: True)
    esdd = dirc("fmES", lambda S: S["t"][1] != "def")
    fc = [dirc(a_, lambda S: True) for a_ in ("fmF", "fmFS", "fmEFS")]
    f23 = dirc("fmF", lambda S: True)

    es_ext = [S for S in es if S["ext1"] is not None]
    hit = [S for S in es_ext if S["Ts"] == first_tick_after(S["ext1"]) + TICK]
    miss = [S for S in es_ext if S not in hit]
    miss_rem = []
    for S in miss:
        e = S["ext_cons"][0]
        f0 = fuel0.get((S["t"][2], e["cell"]))
        miss_rem.append(None if f0 is None else f0 - e["consumed"])
    with_out = [S for S in hit if S["first_out"] is not None]
    out_at = sum(1 for S in with_out if S["first_out"] == S["Ts"])
    d1 = sorted(S["din"][first_tick_after(S["ext1"])] + S["dout"][first_tick_after(S["ext1"])] for S in es_ext)
    d2_out = sorted(S["dout"][S["Ts"]] for S in hit)
    d2_in = sorted(S["din"][S["Ts"]] for S in hit)

    def kind_lags(kind):
        rr = [S for arm in ARMS for S in rows[arm] if S["w1_kind"] == kind and S["Ts"] is not None]
        v = [S["Ts"] - S["w1"] for S in rr]
        vd = sorted(S["Ts"] - S["first_D"] for S in rr if S["first_D"] is not None)
        vo = [S["first_out"] - S["w1"] for S in rr if S["first_out"] is not None]
        return len(rr), min(v), med(v), max(v), vd, vo
    kl = {k: kind_lags(k) for k in ("ext", "clr_s", "clr_u")}
    sat_before = {arm: (sum(1 for S in rows[arm] if S["Ts"] is not None and S["sat"] is not None and S["sat"] < S["Ts"]),
                        sum(1 for S in rows[arm] if S["Ts"] is not None)) for arm in ARMS}
    pre = {}
    for arm in ARMS:
        rr = [S for S in rows[arm] if S["Ts"] is not None]
        pre[arm] = {"ao": sum(S["pre_shift_ever_arm_only"] for S in rr), "oo": sum(S["pre_shift_ever_off_only"] for S in rr),
                    "lag": med([S["Ts"] - S["w1"] for S in rr]), "clr_u": med([S["pre_shift_clr_u"] for S in rr]),
                    "d_before": med([S["din"][S["Ts"] - 1] + S["dout"][S["Ts"] - 1] for S in rr]), "n": len(rr)}
    causes = {arm: collections.Counter(S["cause"][0][1] for S in rows[arm] if S["cause"]) for arm in ARMS}
    far = {}
    for arm in ARMS:
        rr = [S for S in rows[arm] if S["w1"] is not None]
        fa_, ne_ = sum(S["churn_far6"] for S in rr), sum(S["churn_near6"] for S in rr)
        dd_ = [S for S in rr if S["t"][1] != "def"]
        far[arm] = (fa_ / max(1, fa_ + ne_), sum(S["churn_arm_only"] for S in dd_) / max(1, sum(S["churn_off_only"] for S in dd_)))
    scale = {}
    for arm in ARMS:
        dd_ = [S for S in rows[arm] if S["t"][1] != "def"]
        scale[arm] = med([abs(S["delta"]) for S in dd_ if S["delta"]])

    allx = [(S, e) for S in es for e in S["ext_cons"]]
    known = [(S, e, fuel0[(S["t"][2], e["cell"])] - e["consumed"]) for S, e in allx
             if fuel0.get((S["t"][2], e["cell"])) is not None]
    rem1 = sum(1 for _S, _e, r in known if r == 1)
    after_t = sum(1 for _S, e in allx if e["after_term"])
    late180 = sum(1 for _S, e in allx if e["step"] > 180)
    fx = [(S, S["ext_cons"][0]) for S in es if S["ext_cons"]]
    left = sorted(e["off_end"] - e["step"] for _S, e in fx if e["off_end"] is not None)
    relatch = sorted(e["off_latch"] - e["step"] for _S, e in fx if e["off_latch"] is not None)

    fm = {S["t"]: S for S in ff}
    efs_x = [S for S in rows["fmEFS"] if S["n_ext"]]
    earlier = sum(1 for S in efs_x if (S["Ts"] or NEVER) < (fm[S["t"]]["Ts"] or NEVER))
    later = sum(1 for S in efs_x if (S["Ts"] or NEVER) > (fm[S["t"]]["Ts"] or NEVER))
    out_earlier = sum(1 for S in efs_x if (S["first_out"] or NEVER) < (fm[S["t"]]["first_out"] or NEVER))
    pre_x = [S for S in efs_x if fm[S["t"]]["Ts"] is None or S["ext1"] < fm[S["t"]]["Ts"]]
    efs_tot_ext = sum(S["n_ext"] for S in rows["fmEFS"])
    efs_tot_clr = sum(S["n_clr_s"] + S["n_clr_u"] for S in rows["fmEFS"])

    fl_es, fl_f = flip[("fmES", "de-dup 20")], flip[("fmF", "de-dup 20")]
    c_first = corr["first extinguish step"]
    c_grow = corr["OFF growth after Ts"]
    c_expo = corr["re-roll exposure"]
    lat_auc = corr["share ext after terminal"]
    minp = min((v[1] for v in corr.values() if v[1] is not None), default=None)
    minpa = min((v[4] for v in corr.values() if v[4] is not None), default=None)

    def thr(n):
        k = next((k for k in range(n + 1) if k / n >= 0.8 and binom_tail_ge(k, n) <= 0.05), None)
        return k, int(math.floor(0.65 * n))

    w("=" * 100)
    w("TASK C - WHY EXTINGUISH'S PER-RUN SIGN IS A COIN FLIP   (firemech round 2 diagnosis)")
    w("script outputs/_fm2_diag_extvar.py - read-only, runs no simulation, re-runnable in ~15 s")
    w("data: harness JSON of fmOFF, fmES, fmEFS, fmF, fmFS on the canonical 13 + fresh 10 tuples (115 files),")
    w("      opened by explicit path only. NOT read: outputs/_firemech_rewound_20260914/, any f2* result file.")
    w("      outputs/_fm2probe_queue.txt was read once for the CRN arm names, tuples and flags - no results.")
    w("=" * 100)
    w("")
    w("A. ANSWER IN BRIEF")
    w("  1. H1 IS THE MECHANISM, AND IT IS EXACT. The first extinguish shifts the shared fire draw stream on the")
    w("     SECOND fire tick after the write on %d of %d fmES runs with an extinguish. In the %d exceptions (%s)"
      % (len(hit), len(es_ext), len(miss), ", ".join(label(S["t"]) for S in miss)))
    w("     the first extinguished cell had remaining fuel %s; a cell with 1 fuel left latches on the same tick as"
      % " and ".join(fmt(r) for r in miss_rem))
    w("     its OFF copy, so such a write shifts nothing and the shift waits for a later event.")
    never_out = [S for S in hit if S["first_out"] is None]
    w("     On the shift tick itself the fire already differs OUTSIDE the physical light cone on %d of the %d"
      % (out_at, len(hit)))
    w("     (median %s cells outside, %s inside, over those %d)." % (
        fmt(med([S["dout"][S["Ts"]] for S in with_out if S["first_out"] == S["Ts"]])),
        fmt(med([S["din"][S["Ts"]] for S in with_out if S["first_out"] == S["Ts"]])), out_at))
    if never_out:
        w("     %s never differs outside the cone (OFF burning cells at the shift: %s)." % (
            ", ".join(label(S["t"]) for S in never_out), ", ".join(str(S["off_burning_at_Ts"]) for S in never_out)))
    w("     One tick earlier - the write's pure physics, draws still aligned - the difference was %s-%s cells"
      % (d1[0], d1[-1]))
    w("     (median %s, the extinguished cell included). So everything fmES-vs-fmOFF measures after ~5 steps is a"
      % fmt(med(d1)))
    w("     comparison against a re-rolled fire, not against the same fire minus one cell.")
    w("  2. THE COIN FLIP IS SIGNAL-TO-NOISE, NOT ABSENCE OF EFFECT. fmES's mean per-run intact gain is %+.1f cells"
      % fl_es["mean"])
    w("     (de-dup 20), exact sign-flip randomisation p = %.3f (all 23: %.3f). Its null - delta symmetric about 0 -"
      % (fl_es["p"], flip[("fmES", "all 23")]["p"]))
    w("     is what 'the writes do nothing to the fire, the run is only re-rolled' implies: the arm's and OFF's")
    w("     continuations would then be exchangeable.")
    w("     But the per-run sd is %.1f, %.2fx fmF's %.1f. mean/sd %.2f predicts %.0f%% of changed runs up; observed %.0f%%"
      % (fl_es["sd"], fl_es["sd"] / fl_f["sd"], fl_f["sd"], fl_es["mean"] / fl_es["sd"], 100 * fl_es["phi"],
         100 * fl_es["share"]))
    w("     (%d of %d). fmF: mean %+.1f, mean/sd %.2f predicts %.0f%%, observed %.0f%%. Both arms' up-shares are what their"
      % (esdd[0], esdd[0] + esdd[1], fl_f["mean"], fl_f["mean"] / fl_f["sd"], 100 * fl_f["phi"], 100 * fl_f["share"]))
    w("     signal-to-noise predicts. Reading: H4 (a real positive mean with large per-run noise) on top of H1 (the")
    w("     re-roll is where that noise comes from). The sign test alone (%d of %d, p %.3f) cannot see the mean."
      % (esdd[0], esdd[0] + esdd[1], binom_tail_ge(esdd[0], esdd[0] + esdd[1])))
    w("  3. WHY FIREBREAK SURVIVES THE SAME RE-ROLL. Every writing run re-rolls eventually (%d of %d runs with a"
      % (sum(1 for arm in ARMS for S in rows[arm] if S["Ts"] is not None),
         sum(1 for arm in ARMS for S in rows[arm] if S["w1"] is not None)))
    w("     write, all 4 arms). What differs is what is already done when it happens. fmF's first shift comes a median")
    w("     %s steps after its first write, after a median %s never-burned clears; before that shift the fire is"
      % (fmt(pre["fmF"]["lag"]), fmt(pre["fmF"]["clr_u"])))
    w("     strictly smaller than OFF's (pooled %d cells burned in OFF but not in fmF, %d the other way). fmES shifts"
      % (pre["fmF"]["oo"], pre["fmF"]["ao"]))
    w("     a median %s steps after its first write, with %d cells burned-in-OFF-only pooled over %d runs. From then on"
      % (fmt(pre["fmES"]["lag"]), pre["fmES"]["oo"], pre["fmES"]["n"]))
    w("     its outcome is a new sample of the remaining fire plus whatever later extinguishes add. The durability of")
    w("     a fuel-free band against the re-roll is an INTERPRETATION consistent with these numbers (and with fmF vs")
    w("     fmFS, same history then diverged: sign disagreements %d of %d, |delta difference| median %s), not an"
      % (fbfb["fmFS"]["sign_dis"], fbfb["fmFS"]["differ"], fmt(fbfb["fmFS"]["diff_med"])))
    w("     isolated measurement.")
    w("  4. THE SIGN IS NOT PREDICTABLE PER RUN at a corrected level: 14 correlates of fmES's delta (de-dup 20), none")
    w("     below Bonferroni 0.0036 (smallest permutation p: rho %s, AUC %s). Leanings: an EARLY first extinguish"
      % (fmt(minp, 3), fmt(minpa, 3)))
    w("     leans up (Spearman %s, p %s; AUC %s, p %s)." % (
        fmt(c_first[0]), fmt(c_first[1], 3), fmt(c_first[3]), fmt(c_first[4], 3)))
    w("     OFF's own growth after the shift leans up (AUC %s, p %s) - that one is expected even with ZERO effect" % (
        fmt(c_grow[3]), fmt(c_grow[4], 3)))
    w("     (a re-roll regresses toward the mean when OFF happened to grow a lot).")
    nulls = ["share ext after terminal", "ext after terminal", "n_ext", "burning cells at first write",
             "OFF ever_burned at 240"]
    w("     Lateness, number of extinguishes, burning size at the first write, OFF's final size: AUC %s-%s." % (
        fmt(min(corr[k][3] for k in nulls)), fmt(max(corr[k][3] for k in nulls))))
    w("  5. H3 IS REFUTED IN ITS 'ABOUT TO BURN OUT' FORM and true-but-not-the-sign-driver in its 'late' form (E).")
    w("  6. H2 CANNOT BE TESTED ON STOCK DATA - and stock data shows why: while draws are aligned the physics is")
    w("     one-signed (the arm's burning set is a subset of OFF's on every step before the shift, all %d writing runs;"
      % sum(1 for arm in ARMS for S in rows[arm] if S["w1"] is not None))
    w("     the only %d exception cell-steps, in %d runs, are a cell re-igniting in the arm on the very tick its OFF copy burnt"
      % (V["v5_expl"], V["v5_runs"]))
    w("     out). A 'redirected' cell - burning in the arm but never in OFF - needs a burn-out timing difference, and")
    w("     that same event shifts the stream one tick later. Stock data cannot separate redirection from re-roll;")
    w("     the CRN probe can. Its pre-registered predictions and decision rule are section G.")
    w("")
    w("B. ROUND-1 NUMBERS RE-VERIFIED (section 0 below; every one reproduces)")
    w("  fmES per-run intact vs fmOFF: canonical %d up / %d down, fresh %d up / %d down / %d unchanged; pooled %+d (23"
      % (esc[0], esc[1], esf[0], esf[1], esf[2], es23[3]))
    w("  runs), %+d de-dup 20. Firebreak arms over 23: fmF %d/%d/%d, fmFS %d/%d/%d, fmEFS %d/%d/%d up/down/same (fmF %d of %d"
      % ((esdd[3],) + fc[0][:3] + fc[1][:3] + fc[2][:3] + (f23[0], f23[0] + f23[1])))
    w("  changed runs up; fmF sign test p %.4f). Digest attribution: first divergence == first write on 20/20 writing"
      % binom_tail_ge(f23[0], f23[0] + f23[1]))
    w("  runs in all 4 arms, 3 no-write runs identical. fmEFS writes: %d extinguishes, %d clears." % (efs_tot_ext, efs_tot_clr))
    w("")
    w("C. LIGHT-CONE TEST (sections 1-2)")
    w("  INSTRUMENTS VALIDATED FIRST. Ticks: 0 of %d OFF interval boundaries off the t%%3==0 phase. Fuel model:"
      % V["v1_n"])
    w("  %d natural burn-outs on %d (seed, cell) keys give fuel0 in 7..10 with 0 disagreements across arms AND winds."
      % (V["v2_obs"], V["v2_keys"]))
    w("  Draw-stream reconstruction: 0 runs with an outside-cone difference before the reconstructed shift tick (V3);")
    w("  on the %d runs with outside-cone differences exactly at the shift tick, all lie at uid >= the first misaligned"
      % V["v4_runs"])
    w("  uid (V4), while one tick later such cells appear below it on %d of %d runs (%d cells) - so V4 is not vacuous."
      % STATE["v4neg"])
    w("  MECHANICS AS OBSERVED, sharpened against the brief's description:")
    w("   - An extinguished cell keeps drawing on the first tick after the write (the draw precedes the latch) and")
    w("     stops on the second; if it had exactly 1 fuel left OFF's copy latches on that same tick and nothing shifts.")
    w("     First-write-extinguish runs (all arms): shift %d-%s steps after the write, median %s."
      % (kl["ext"][1], kl["ext"][3], fmt(kl["ext"][2])))
    w("   - A never-burned clear keeps drawing for ever. Runs whose first write was one: shift %d-%d steps after it,"
      % (kl["clr_u"][1], kl["clr_u"][3]))
    w("     median %s. Cause of the first shift in fmF: natural burn-out timing %d, a later scorched clear %d, a"
      % (fmt(kl["clr_u"][2]), causes["fmF"].get("natural", 0), causes["fmF"].get("clr_s", 0)))
    w("     cleared cell whose OFF copy burnt out %d. The brief's '>= ~21 steps' holds from the first WRITE (min %d)."
      % (causes["fmF"].get("clr_u", 0), kl["clr_u"][1]))
    nat_lag = sorted(S["Ts"] - S["first_D"] for arm in ARMS for S in rows[arm]
                     if S["w1_kind"] == "clr_u" and S["cause"] and S["cause"][0][1] == "natural" and S["first_D"] is not None)
    w("     It does NOT hold from the first burning-state difference: on natural-burn-out-caused runs Ts - Dn")
    w("     is %s-%s steps (median %s) - a cell near the end of its fuel needs only one lost burning tick to change"
      % (nat_lag[0], nat_lag[-1], fmt(med(nat_lag))))
    w("     its burn-out tick.")
    w("   - A SCORCHED clear (has_burned, fuel left) latches on the next tick like an extinguish: runs whose first write")
    w("     was one shift %d-%s steps after it (n %d). fmF made %d of its %d clears on scorched cells (section 2)."
      % (kl["clr_s"][1], kl["clr_s"][3], kl["clr_s"][0], sum(S["n_clr_s"] for S in ff),
         sum(S["n_clr_s"] + S["n_clr_u"] for S in ff)))
    w("   - Outside-cone observation is often impossible for firebreak: the cone covers all 2500 cells BEFORE the shift")
    w("     on %d of %d fmF runs (fmES %d of %d). There the shift is visible only through the draw reconstruction."
      % (sat_before["fmF"] + sat_before["fmES"]))
    def lagser(kind, lags):
        rr = [S for arm in ARMS for S in rows[arm] if S["w1_kind"] == kind]
        out = []
        for lag in lags:
            ins = [S["din"][S["w1"] + lag] for S in rr if S["w1"] + lag <= STEPS]
            ous = [S["dout"][S["w1"] + lag] for S in rr if S["w1"] + lag <= STEPS]
            out.append("+%d %s/%s" % (lag, fmt(med(ins), 0), fmt(med(ous), 0)))
        return ", ".join(out)
    w("  SIZES (section 9, by kind of first write, all arms, median |D| inside/outside the cone):")
    w("    extinguish-first         %s" % lagser("ext", (3, 6, 15, 30)))
    w("    never-burned-clear-first %s" % lagser("clr_u", (3, 30, 45, 60)))
    sat240 = [(arm, sum(1 for S in rows[arm] if S["w1"] is not None and S["sat"] is not None),
               sum(1 for S in rows[arm] if S["w1"] is not None)) for arm in ARMS]
    w("  The fraction of D outside the cone AT 240 is uninformative: the cone is saturated by 240 on")
    w("  %s writing runs." % ", ".join("%s %d/%d" % s_ for s_ in sat240))
    w("  Its end-state substitute: has_burned churn farther than 6 cells from every write is %.0f%% for fmES vs"
      % (100 * far["fmES"][0]))
    w("  %.0f-%.0f%% for the firebreak arms; burned-in-arm-only / burned-in-OFF-only (R_ao, de-dup) %.3f vs %.3f-%.3f."
      % (100 * min(far[a_][0] for a_ in ("fmF", "fmFS", "fmEFS")), 100 * max(far[a_][0] for a_ in ("fmF", "fmFS", "fmEFS")),
         far["fmES"][1], min(far[a_][1] for a_ in ("fmF", "fmFS", "fmEFS")), max(far[a_][1] for a_ in ("fmF", "fmFS", "fmEFS"))))
    w("")
    w("D. SCALES AND CORRELATES (sections 3, 4, 9)")
    w("  median |delta| over changed de-dup runs: fmES %s, fmF %s, fmFS %s, fmEFS %s." % (
        fmt(scale["fmES"]), fmt(scale["fmF"]), fmt(scale["fmFS"]), fmt(scale["fmEFS"])))
    w("  Re-roll yardstick: over %d de-dup pairs of runs of the same tuple (arm vs OFF, and firebreak vs firebreak"
      % STATE["yard_rho"][1])
    w("  pairs that differ by no extinguish), |intact difference| tracks the fire still to come after the pair's own")
    w("  shift tick (Spearman %s). Per unit of that growth fmES-vs-OFF is %.3f, fmF-vs-OFF %.3f, firebreak-vs-"
      % (fmt(STATE["yard_rho"][0]), yard["fmES-OFF"]["ratio"], yard["fmF-OFF"]["ratio"]))
    w("  firebreak %.3f-%.3f (medians of per-pair ratios). fmES shifts earlier (pair median tick %s vs %s) with more"
      % (min(yard[k]["ratio"] for k in ("fmF-fmFS", "fmF-fmEFS", "fmFS-fmEFS")),
         max(yard[k]["ratio"] for k in ("fmF-fmFS", "fmF-fmEFS", "fmFS-fmEFS")), fmt(yard["fmES-OFF"]["Ts"]),
         fmt(yard["fmF-OFF"]["Ts"])))
    w("  fire left (growth median %s vs %s). By the per-pair ratio fmES carries no more difference per unit of fire"
      % (fmt(yard["fmES-OFF"]["growth"]), fmt(yard["fmF-OFF"]["growth"])))
    w("  left than firebreak; by the ratio of medians it carries more (%.2f vs %.2f). The yardstick therefore cannot"
      % (yard["fmES-OFF"]["diff"] / yard["fmES-OFF"]["growth"], yard["fmF-OFF"]["diff"] / yard["fmF-OFF"]["growth"]))
    w("  settle how much of fmES's larger spread is its earlier re-roll; and no stock arm re-rolls without also")
    w("  intervening, so the pure re-roll noise scale is NOT measured directly.")
    w("  |delta| does scale with re-roll exposure (fmES rho|.| %s) and with growth after the shift (rho|.| %s)."
      % (fmt(c_expo[2]), fmt(c_grow[2])))
    late_es = [S for S in es if S["w1"] is not None and not (S["first_out"] is not None and S["first_out"] - S["w1"] <= 15)]
    w("  The %d fmES runs whose first outside-cone difference came late (> 15 steps) or never: |delta| %s, first"
      % (len(late_es), ", ".join("%+d" % S["delta"] for S in late_es)))
    w("  extinguish at %s - near the end of the fire, so timing and re-roll exposure are confounded there."
      % ", ".join(str(S["ext1"]) for S in late_es))
    w("")
    w("E. H3 - WHAT fmES EXTINGUISHES (section 5)")
    w("  'About to burn out': %d of %d extinguishes with known fuel0 had exactly 1 fuel left (%.0f%%); remaining fuel is"
      % (rem1, len(known), 100.0 * rem1 / max(1, len(known))))
    w("  spread over 1-10. REFUTED as the main story.")
    w("  'About to go out anyway': on the FIRST extinguish per run (OFF is its exact counterfactual) the OFF cell would")
    w("  have kept burning only %s steps median (%d of %d within 3 steps) - burning cells flicker - but %d of %d re-ignited"
      % (fmt(med(left)), sum(1 for x in left if x <= 3), len(left), len(relatch), len(fx)))
    w("  and burnt out later in OFF (median %s steps after the write). An extinguish therefore mostly removes a cell's"
      % fmt(med(relatch)))
    w("  FUTURE re-burning, like a scorched clear, not its present flame.")
    w("  'Mostly late': %d of %d extinguishes (%.0f%%) come after the arm's terminal_step, %d after step 180. TRUE, but"
      % (after_t, len(allx), 100.0 * after_t / max(1, len(allx)), late180))
    w("  the share after terminal does not predict the sign (AUC %s, p %s)." % (fmt(lat_auc[3]), fmt(lat_auc[4], 3)))
    w("")
    w("F. fmEFS (FULL CONFIG) vs fmF ON THE SAME TUPLE (section 6)")
    w("  %d fmEFS runs have any extinguish (%d extinguishes in all vs %d clears). Their shift tick is EARLIER than fmF's"
      % (len(efs_x), efs_tot_ext, efs_tot_clr))
    w("  on %d, later on %d, the same on %d; the first outside-cone difference is earlier on only %d (the cone had"
      % (earlier, later, len(efs_x) - earlier - later, out_earlier))
    pre_caused = sum(1 for S in pre_x if S["Ts"] is not None and (fm[S["t"]]["Ts"] is None or S["Ts"] < fm[S["t"]]["Ts"])
                     and S["cause"] and S["cause"][0][1] == "ext")
    w("  saturated in the others). The first extinguish precedes fmF's shift tick on %d runs; %d of them shift earlier"
      % (len(pre_x), pre_caused))
    w("  with the extinguished cell as the cause (first extinguish < fmF shift tick, EFS shift, EFS delta / fmF delta):")
    for S in pre_x:
        w("    %-16s %3d < %3d   EFS shift %s   EFS %+d / fmF %+d" % (
            label(S["t"]), S["ext1"], fm[S["t"]]["Ts"], fmt(S["Ts"]), S["delta"], fm[S["t"]]["delta"]))
    agree_sign = sum(1 for S in pre_x if (S["delta"] > 0) == (fm[S["t"]]["delta"] > 0)
                     and (S["delta"] < 0) == (fm[S["t"]]["delta"] < 0))
    w("  On the other %d the stream had already shifted in the matching firebreak history when the first extinguish"
      % (len(efs_x) - len(pre_x)))
    w("  came. On the %d earlier-shift runs the sign agrees with fmF %d times; magnitudes differ by %s cells."
      % (len(pre_x), agree_sign, ", ".join(str(abs(S["delta"] - fm[S["t"]]["delta"])) for S in pre_x)))
    w("")
    w("G. PRE-REGISTRATION FOR THE CRN PROBE (f2cOFF, f2cES, f2cF) - WRITTEN BEFORE ANY f2c* RESULT WAS READ")
    w("  Under CRN each fire draw is a function of (seed, cell uid, the cell's own tick) - outputs/_fm2_probe_harness.py")
    w("  crn_uniform - so a write can change the fire only physically. CRN arms are compared only with f2cOFF (a")
    w("  different, equally distributed fire from stock), on the de-dup 20 (east/def still shares its OFF fire).")
    w("  MEASURES (code: prereg_measures / prereg_verdict; apply with --prereg-tags f2cOFF,f2cES,f2cF):")
    w("    S = up / (up + down) over changed runs, with the one-sided sign test p;  M = median |delta| over changed")
    w("    runs;  G = pooled delta / pooled f2cOFF ever_burned;  BD = down runs with delta <= -20;  SM = runs with a")
    w("    write and |delta| <= 10;  D6 / D30 = median |D| at first write + 6 / + 30 steps;  R_ao = pooled burned-in-")
    w("    arm-only / burned-in-OFF-only;  p_flip = exact sign-flip p of the mean.")
    w("  STOCK VALUES (same code, section 10): fmES S %.2f (p %.3f), M %s, G %.4f, BD %d, SM %d of %d, D6 %s, D30 %s,"
      % (E_st["S"], E_st["p_sign"], fmt(E_st["M"]), E_st["G"], E_st["BD"], E_st["SM"], E_st["n_write"],
         fmt(E_st["D6"], 0), fmt(E_st["D30"], 0)))
    w("    R_ao %.3f, p_flip %.3f;  fmF S %.2f (p %.4f), M %s, G %.4f, BD %d, R_ao %.3f." % (
        E_st["R_ao"], E_st["p_flip"], F_st["S"], F_st["p_sign"], fmt(F_st["M"]), F_st["G"], F_st["BD"], F_st["R_ao"]))
    w("  PREDICTIONS (f2cES vs f2cOFF; the light-cone rows hold under EVERY hypothesis and are validity checks):")
    w("    all  first fire-digest divergence == first write step on every writing run; NO cell outside the cone at")
    w("         any step of any f2cES or f2cF run (stock fmES: %d outside cell-steps on %d of %d de-dup writing runs)."
      % (E_st["outside_total"], E_st["outside_runs"], E_st["n_write"]))
    w("         The first-tick physics of the first extinguish should look like stock's (0-4 cells).")
    w("    H1   the coin flip was the re-roll; extinguish's own effect is one-signed: S >= 0.80 with sign-test")
    w("         p <= 0.05, BD <= 1, M below stock's %s, D6 far below stock's %s (expect <= 20), R_ao well below"
      % (fmt(STOCK_ES_MEDIAN_ABS), fmt(E_st["D6"], 0)))
    w("         stock fmES's %.3f (expect near stock firebreak's %.3f-%.3f), G >= half of f2cF's G." % (
        E_st["R_ao"], min(far[a_][1] for a_ in ("fmF", "fmFS", "fmEFS")), max(far[a_][1] for a_ in ("fmF", "fmFS", "fmEFS"))))
    w("    H4   small true effect plus re-roll noise: the H1 sign pattern (or too few changed runs to test it), with")
    w("         G below half of f2cF's G (or below %.4f if f2cF's G <= 0), M small." % (0.5 * STOCK_ES_G))
    w("    H2   physical redirection: S <= 0.65 and BD >= 2 while the cone check passes and f2cF stays consistent;")
    w("         R_ao >= 0.25; D30 of the same order as stock (>= 50).")
    w("    H3   near-inert extinguish: SM >= half of the writing runs, |G| <= 0.01, D30 <= 10.")
    w("  DECISION RULE (first match wins; frozen in prereg_verdict):")
    w("    0. INVALID -> no verdict: any attribution violation, or any outside-cone cell in f2cES or f2cF.")
    w("    1. H3 if SM >= 0.5 * writing runs AND |G| <= 0.01 AND D30 <= 10.")
    w("    2. S >= 0.80 and p_sign <= 0.05: H1 if G >= 0.5 * G(f2cF) [0.5 * %.4f if G(f2cF) <= 0], else H1 + H4."
      % STOCK_ES_G)
    w("    3. S <= 0.65 and BD >= 2: H2 if f2cF is consistent (S >= 0.80, p <= 0.05); otherwise INCONCLUSIVE - without")
    w("       the stream both mechanics are two-signed and closed-loop physics, not the re-roll, sets the sign.")
    w("    4. otherwise INCONCLUSIVE.")
    w("  Thresholds in counts (S >= 0.80 with one-sided p <= 0.05 / S <= 0.65):")
    w("    " + "  ".join("n%d: >=%s / <=%d" % ((n,) + thr(n)) for n in range(10, 21)))
    w("  Honest limits of the rule: n is small (stock had %d changed de-dup runs), so a real but weak one-signed effect can"
      % (E_st["up"] + E_st["down"]))
    w("  land in 'inconclusive'; CRN keeps the closed loop, so unit behaviour still differs run to run (a mixed sign")
    w("  under CRN with a consistent f2cF points at extinguish's own physics, but does not by itself say whether it")
    w("  is front redirection or where the units happen to stand).")
    w("")
    w("H. NOT ESTABLISHED")
    w("  - The pure re-roll noise scale (no stock arm re-rolls without intervening; section 9 is a yardstick only).")
    w("  - H2 on stock data (the physics-only window of an extinguish is one tick).")
    w("  - That a band's effect is durable against re-roll (consistent with the data, not isolated).")
    w("  - The draw reconstruction assumes Fire.step is the only consumer of the shared stream during steps (grep:")
    w("    agents.py Wind draws only when FIXED_WIND is False - it is True; the UAV random direction only without the")
    w("    extension pipeline). V3/V4 with a non-vacuous negative control are the evidence; no call site was traced")
    w("    at runtime.")
    w("  - The sign-flip p assumes the 20 de-dup runs are independent; the 14-correlate screen is uncorrected except")
    w("    where Bonferroni is stated.")
    return L


def load_rows(off_tag, arm_tags, tuples):
    rows = {arm: [] for arm in arm_tags}
    for t in tuples:
        O = extract(off_tag, t)
        for arm in arm_tags:
            R = extract(arm, t)
            S = analyse(R, O)
            del S["natural_fuel"]
            rows[arm].append(S)
            del R
        del O
    return rows


# ------------------------------------------------------------------ main --------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "_fm2_diag_extvar.txt"))
    ap.add_argument("--prereg-tags", default="",
                    help="OFF,ES,F tags (e.g. f2cOFF,f2cES,f2cF): apply ONLY the pre-registered rule, print, exit")
    a = ap.parse_args()
    tuples = CANON + FRESH
    if a.prereg_tags:
        off_tag, es_tag, f_tag = a.prereg_tags.split(",")
        rows = load_rows(off_tag, [es_tag, f_tag], tuples)
        E, F = prereg_measures(rows[es_tag], rows[f_tag])
        for line in ["PRE-REGISTERED RULE applied to %s vs %s (control %s), de-dup 20" % (es_tag, off_tag, f_tag)] + \
                prereg_verdict(E, F, crn=True):
            say(line)
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(OUT) + "\n")
        return
    rows = {arm: [] for arm in ARMS}
    fuel_obs = collections.defaultdict(list)  # (seed, cell) -> [(fuel0, label)]
    v1_bad = 0
    v1_n = 0
    offs = {}
    for t in tuples:
        O = extract("fmOFF", t)
        for a_, b_ in O["bounds"]:
            v1_n += 1
            if not ((a_ % TICK == 0 or a_ == 1) and (b_ is None or b_ % TICK == 0)):
                v1_bad += 1
        LO, natO, probO, _ = latch_ticks(O)
        for c, f0 in natO:
            fuel_obs[(t[2], c)].append((f0, "fmOFF " + label(t)))
        offs[t] = {"ever": O["ever"], "intact": O["intact"], "rescued": O["rescued"], "terminal": O["terminal"],
                   "n_ign_cells": int(O["B"].any(axis=0).sum()), "probs": probO}
        KEEP[("fmOFF", t)] = {"L": LO, "fb": np.where(O["B"].any(axis=0), np.argmax(O["B"], axis=0), NEVER),
                              "intact": O["intact"], "digests": O["digests"]}
        for arm in ARMS:
            R = extract(arm, t)
            KEEP[(arm, t)] = {"L": latch_ticks(R)[0], "fb": np.where(R["B"].any(axis=0), np.argmax(R["B"], axis=0), NEVER),
                              "intact": R["intact"], "digests": R["digests"]}
            S = analyse(R, O)
            for c, f0 in S["natural_fuel"]:
                fuel_obs[(t[2], c)].append((f0, arm + " " + label(t)))
            del S["natural_fuel"]
            rows[arm].append(S)
            del R
        del O
        print("done", label(t), file=sys.stderr)

    canon_set, fresh_set = set(CANON), set(FRESH)

    say("TASK C - WHY EXTINGUISH'S PER-RUN SIGN IS A COIN FLIP  (outputs/_fm2_diag_extvar.py, read-only)")
    say("data: fmOFF, fmES, fmEFS, fmF, fmFS x canonical 13 + fresh 10 harness JSON; nothing else read")
    say("")
    say("=" * 100)
    say("0. RE-VERIFICATION OF ROUND-1 NUMBERS (intact = 2500 - ever - cleared, vs fmOFF per run)")
    say("=" * 100)
    for arm in ARMS:
        for name, sel in (("canonical", canon_set), ("fresh", fresh_set)):
            rr = [S for S in rows[arm] if S["t"] in sel]
            up = sum(1 for S in rr if S["delta"] > 0)
            dn = sum(1 for S in rr if S["delta"] < 0)
            eq = sum(1 for S in rr if S["delta"] == 0)
            say("  %-6s %-9s up %2d / down %2d / unchanged %2d   pooled delta %+6d" % (
                arm, name, up, dn, eq, sum(S["delta"] for S in rr)))
        rr = rows[arm]
        dd = [S for S in rr if S["t"][1] != "def"]
        say("  %-6s all 23: pooled %+d (OFF intact %d, arm intact %d);  de-dup 20: pooled %+d" % (
            arm, sum(S["delta"] for S in rr), sum(S["off_intact"] for S in rr), sum(S["intact"] for S in rr),
            sum(S["delta"] for S in dd)))
    fup = sum(1 for S in rows["fmF"] if S["delta"] > 0)
    fch = sum(1 for S in rows["fmF"] if S["delta"] != 0)
    say("  fmF changed runs up: %d of %d" % (fup, fch))
    say("  digest attribution re-check (first fire-digest divergence == first write step):")
    for arm in ARMS:
        ok = sum(1 for S in rows[arm] if S["w1"] is not None and S["dig_div"] == S["w1"])
        idn = sum(1 for S in rows[arm] if S["w1"] is None and S["dig_div"] is None)
        bad = [label(S["t"]) for S in rows[arm] if not ((S["w1"] is not None and S["dig_div"] == S["w1"])
                                                         or (S["w1"] is None and S["dig_div"] is None))]
        say("    %-6s exact %2d  no-write identical %d  violations %s" % (arm, ok, idn, bad or "none"))
    say("  write counts vs firefight_counters: %s" % (
        "all agree" if all(S["counter_ok"] for arm in ARMS for S in rows[arm]) else
        [(arm, label(S["t"])) for arm in ARMS for S in rows[arm] if not S["counter_ok"]]))

    say("")
    say("=" * 100)
    say("1. INSTRUMENT VALIDATION")
    say("=" * 100)
    say("  V1 OFF burn-interval boundaries on ticks (t %% 3 == 0; ignition cell start 1): %d of %d boundaries violate"
        % (v1_bad, v1_n))
    lp = [(arm, label(S["t"]), p) for arm in ARMS for S in rows[arm] for p in S["latch_problems"]]
    lp += [("fmOFF", label(t), p) for t in tuples for p in offs[t]["probs"]]
    say("  latch reconstruction problems (burnt cell without a tick-ending interval, written cell not burnt): %d%s"
        % (len(lp), (" " + str(lp[:5])) if lp else ""))
    bad_range = sum(1 for k, v in fuel_obs.items() for f0, _l in v if not 7 <= f0 <= 10)
    conflicts = [(k, sorted(set(f for f, _l in v))) for k, v in fuel_obs.items() if len(set(f for f, _l in v)) > 1]
    n_obs = sum(len(v) for v in fuel_obs.values())
    say("  V2 fuel0 from natural burn-outs: %d observations on %d (seed, cell) keys; out of 7..10: %d;"
        " keys with disagreeing values across runs (same seed, any wind/arm): %d" % (
            n_obs, len(fuel_obs), bad_range, len(conflicts)))
    if conflicts:
        say("     first conflicts: %s" % conflicts[:5])
    hist = collections.Counter(f0 for v in fuel_obs.values() for f0, _l in v[:1])
    say("     fuel0 histogram (one per key): %s" % dict(sorted(hist.items())))
    v3 = [(arm, label(S["t"]), S["V3_viol"]) for arm in ARMS for S in rows[arm] if S["V3_viol"]]
    v4 = [(arm, label(S["t"]), S["V4_viol"]) for arm in ARMS for S in rows[arm] if S["V4_viol"]]
    n_ts = sum(1 for arm in ARMS for S in rows[arm] if S["Ts"] is not None)
    n_ts_out = sum(1 for arm in ARMS for S in rows[arm] if S["Ts"] is not None and S["dout"][S["Ts"]])
    say("  V3 D outside the cone before the reconstructed shift tick Ts: %d run(s) violate %s" % (len(v3), v3 or ""))
    say("  V4 outside-cone D at Ts only on uid >= u0: %d run(s) violate %s  (%d runs have outside D exactly at Ts,"
        " of %d with a shift)" % (len(v4), v4 or "", n_ts_out, n_ts))
    v5 = [(arm, label(S["t"]), S["V5_viol"]) for arm in ARMS for S in rows[arm] if S["V5_viol"]]
    say("  V5 monotone coupling: while draws are aligned (steps < Ts; all 240 steps on no-shift runs) the spread")
    say("     probability is monotone in the burning set and no write adds fuel, so B_arm(t) must be a SUBSET of")
    say("     B_OFF(t): cells burning in the arm but not in OFF before Ts: %d run(s) have any %s" % (len(v5), v5 or ""))
    v5s = [(arm, label(S["t"]), S["V5_strict"]) for arm in ARMS for S in rows[arm] if S["V5_strict"]]
    say("     refined: a cell-step is EXPLAINED if it lies in the tick window of Ts-3 (the first latch-difference")
    say("     tick) and either the cell itself latched on that tick in OFF but not in the arm (OFF's copy burnt out,")
    say("     the arm's copy kept fuel and its aligned draw re-ignited it), or a lower-uid cell within euclidean 3 did")
    say("     (Fire.step sets burning False on a latching cell during the step pass): explained %d %s, unexplained %d%s" % (
        sum(len(S["V5_latch_tick"]) for arm in ARMS for S in rows[arm]),
        dict(collections.Counter(e[2] for arm in ARMS for S in rows[arm] for e in S["V5_latch_tick"])),
        sum(S["V5_strict"] for arm in ARMS for S in rows[arm]), (" " + str(v5s)) if v5s else ""))
    say("     so the aligned-draw physics is one-signed except through a burn-out timing difference - the same event"
        " that shifts the stream one tick later")

    fuel0 = {}
    for k, v in fuel_obs.items():
        vals = collections.Counter(f for f, _l in v)
        fuel0[k] = vals.most_common(1)[0][0] if len(vals) == 1 else None
    STATE["val"] = {"v1_bad": v1_bad, "v1_n": v1_n, "latch_problems": len(lp), "v2_obs": n_obs, "v2_keys": len(fuel_obs),
                    "v2_range": bad_range, "v2_conflicts": len(conflicts), "v3": len(v3), "v4": len(v4),
                    "v4_runs": n_ts_out, "n_ts": n_ts, "v5_runs": len(v5),
                    "v5_expl": sum(len(S["V5_latch_tick"]) for arm in ARMS for S in rows[arm]),
                    "v5_unexpl": sum(S["V5_strict"] for arm in ARMS for S in rows[arm])}
    STATE["fuel0"] = fuel0

    say("")
    say("=" * 100)
    say("2. LIGHT-CONE TEST, PER RUN")
    say("=" * 100)
    say("  w1 = first write step/kind; Dn = first step D non-empty; Ts = reconstructed first misaligned draw tick;")
    say("  out = first step with D outside the cone; sat = step the cone covers all 2500 cells;")
    say("  cause = the cell(s) whose draw/latch status differs before Ts: kind, latch tick arm/OFF;")
    say("  in/out@lag = |D inside| / |D outside| at first write + lag steps")
    for arm in ARMS:
        say("")
        say("  --- %s ---" % arm)
        say("  %-15s %6s %4s %4s %4s %4s %4s %5s  %-40s %s" % (
            "tuple", "delta", "w1", "kind", "Dn", "Ts", "out", "sat", "cause (cell kind latchA/latchO)",
            "in/out @ +0 +3 +6 +9 +12 +15 +21 +30 +60 | @240"))
        for S in rows[arm]:
            if S["w1"] is None:
                say("  %-15s %+6d  no write" % (label(S["t"]), S["delta"]))
                continue
            w1 = S["w1"]
            ser = []
            for lag in (0, 3, 6, 9, 12, 15, 21, 30, 60):
                s = w1 + lag
                ser.append("%d/%d" % (S["din"][s], S["dout"][s]) if s <= STEPS else "-")
            cause = "; ".join("%s %s %s/%s" % ("%d,%d" % c, k, la, lo) for c, k, la, lo in S["cause"][:2])
            if len(S["cause"]) > 2:
                cause += " +%d" % (len(S["cause"]) - 2)
            say("  %-15s %+6d %4d %-5s %4s %4s %4s %4s  %-40s %s | %d/%d" % (
                label(S["t"]), S["delta"], w1, S["w1_kind"], fmt(S["first_D"]), fmt(S["Ts"]), fmt(S["first_out"]),
                fmt(S["sat"]), cause[:40], " ".join(ser), S["din"][STEPS], S["dout"][STEPS]))

    say("")
    say("  LAG SUMMARY by kind of the FIRST shift-causing write (all 4 arms pooled; runs with a write)")
    groups = collections.defaultdict(list)
    for arm in ARMS:
        for S in rows[arm]:
            if S["w1"] is None:
                continue
            groups["first write " + S["w1_kind"]].append(S)
    for g, rr in sorted(groups.items()):
        lag_ts = [S["Ts"] - S["w1"] for S in rr if S["Ts"] is not None]
        lag_out = [S["first_out"] - S["w1"] for S in rr if S["first_out"] is not None]
        lag_D = [S["first_D"] - S["w1"] for S in rr if S["first_D"] is not None]
        say("    %-18s runs %2d | Ts-w1: n %2d min %s median %s max %s | out-w1: n %2d min %s median %s max %s |"
            " Dn-w1 median %s | no shift %d" % (
                g, len(rr), len(lag_ts), fmt(min(lag_ts) if lag_ts else None), fmt(med(lag_ts)),
                fmt(max(lag_ts) if lag_ts else None), len(lag_out), fmt(min(lag_out) if lag_out else None),
                fmt(med(lag_out)), fmt(max(lag_out) if lag_out else None), fmt(med(lag_D)),
                sum(1 for S in rr if S["Ts"] is None)))
    for g, rr in sorted(groups.items()):
        v = sorted(S["Ts"] - S["first_D"] for S in rr if S["Ts"] is not None and S["first_D"] is not None)
        say("    %-18s Ts - Dn (first burning-state difference to first misaligned draw): %s" % (g, v))
    say("  cone saturated before the shift (outside-cone difference unobservable): %s" % "  ".join(
        "%s %d/%d" % (arm, sum(1 for S in rows[arm] if S["Ts"] is not None and S["sat"] is not None and S["sat"] < S["Ts"]),
                      sum(1 for S in rows[arm] if S["Ts"] is not None)) for arm in ARMS))
    es_ = [S for S in rows["fmES"] if S["ext1"] is not None]
    hit = [S for S in es_ if S["Ts"] == first_tick_after(S["ext1"]) + TICK]
    say("  fmES: Ts == the SECOND tick after the first extinguish on %d of %d runs with an extinguish; exceptions: %s" % (
        len(hit), len(es_), ", ".join("%s ext1 %d Ts %s" % (label(S["t"]), S["ext1"], fmt(S["Ts"]))
                                      for S in es_ if S not in hit) or "none"))
    say("  fmES: |D| at the FIRST tick after the first extinguish (draws still aligned there: pure physics of one"
        " write): %s" % sorted(S["din"][first_tick_after(S["ext1"])] + S["dout"][first_tick_after(S["ext1"])]
                               for S in es_ if first_tick_after(S["ext1"]) <= STEPS))
    say("  fmES: |D| one tick later, at the second tick (= Ts on the runs above), inside / outside the cone: %s" % "  ".join(
        "%d/%d" % (S["din"][first_tick_after(S["ext1"]) + TICK], S["dout"][first_tick_after(S["ext1"]) + TICK])
        for S in es_ if first_tick_after(S["ext1"]) + TICK <= STEPS))
    say("  |D| on the step BEFORE the shift tick (Ts - 1: the purely physical difference built up while every draw")
    say("  was still aligned), median [min-max] per arm, runs with a shift:")
    for arm in ARMS:
        v = [S["din"][S["Ts"] - 1] + S["dout"][S["Ts"] - 1] for S in rows[arm] if S["Ts"] is not None]
        rr = [S for S in rows[arm] if S["Ts"] is not None]
        say("    %-6s n %2d median %s [%s-%s]  steps of aligned physics after the first write (Ts - w1) median %s" % (
            arm, len(v), fmt(med(v)), min(v), max(v), fmt(med([S["Ts"] - S["w1"] for S in rr]))))
        say("           cumulative before Ts: cells burned in OFF but not the arm median %s [%s-%s], in the arm but"
            " not OFF median %s; writes before Ts median %s (never-burned clears %s); pooled OFF-only %d arm-only %d" % (
                fmt(med([S["pre_shift_ever_off_only"] for S in rr])), min(S["pre_shift_ever_off_only"] for S in rr),
                max(S["pre_shift_ever_off_only"] for S in rr), fmt(med([S["pre_shift_ever_arm_only"] for S in rr])),
                fmt(med([S["pre_shift_writes"] for S in rr])), fmt(med([S["pre_shift_clr_u"] for S in rr])),
                sum(S["pre_shift_ever_off_only"] for S in rr), sum(S["pre_shift_ever_arm_only"] for S in rr)))
    say("  writes by kind, pooled: %s" % "  ".join("%s ext %d clr_s %d clr_u %d" % (
        arm, sum(S["n_ext"] for S in rows[arm]), sum(S["n_clr_s"] for S in rows[arm]),
        sum(S["n_clr_u"] for S in rows[arm])) for arm in ARMS))
    say("  cause of the shift, by kind of the causing cell (first listed cause per run):")
    for arm in ARMS:
        c = collections.Counter(S["cause"][0][1] if S["cause"] else ("no shift" if S["w1"] is not None else "no write")
                                for S in rows[arm])
        say("    %-6s %s" % (arm, dict(c)))
    say("  out - Ts (steps from the first misaligned tick to the first outside-cone difference):")
    for arm in ARMS:
        v = [S["first_out"] - S["Ts"] for S in rows[arm] if S["Ts"] is not None and S["first_out"] is not None]
        say("    %-6s n %2d  values %s" % (arm, len(v), sorted(v)))
    say("  median |D inside| / |D outside| over runs, by lag after first write:")
    for arm in ARMS:
        rr = [S for S in rows[arm] if S["w1"] is not None]
        parts = []
        for lag in LAGS:
            ins = [S["din"][S["w1"] + lag] for S in rr if S["w1"] + lag <= STEPS]
            ous = [S["dout"][S["w1"] + lag] for S in rr if S["w1"] + lag <= STEPS]
            parts.append("+%d %s/%s" % (lag, fmt(med(ins), 0), fmt(med(ous), 0)))
        say("    %-6s %s" % (arm, "  ".join(parts)))
    say("  D at the extremes: max over steps of |D|, and |D| at 240 (median over runs with a write):")
    for arm in ARMS:
        rr = [S for S in rows[arm] if S["w1"] is not None]
        say("    %-6s max|D| median %s  |D|@240 median %s  frac outside cone @240 median %s (cone saturated on %d/%d)" % (
            arm, fmt(med([max(a + b for a, b in zip(S["din"], S["dout"])) for S in rr])),
            fmt(med([S["din"][STEPS] + S["dout"][STEPS] for S in rr])),
            fmt(med([S["frac_out_240"] for S in rr])), sum(1 for S in rr if S["sat"] is not None), len(rr)))

    say("")
    say("=" * 100)
    say("3. END-STATE CHURN vs NET: has_burned in arm only / in OFF only (net ever change = arm_only - off_only)")
    say("=" * 100)
    say("  churn = arm_only + off_only. Under a local, one-signed effect churn ~ |net|; under a re-roll churn >> |net|.")
    for arm in ARMS:
        rr = [S for S in rows[arm] if S["w1"] is not None]
        ch = [S["churn_arm_only"] + S["churn_off_only"] for S in rr]
        net = [abs(S["churn_arm_only"] - S["churn_off_only"]) for S in rr]
        ratio = [c / n if n else None for c, n in zip(ch, net)]
        far = sum(S["churn_far6"] for S in rr)
        near = sum(S["churn_near6"] for S in rr)
        say("  %-6s runs %2d  pooled churn %6d  pooled |net| %5d  median churn/|net| %s  churn >6 cells (Chebyshev)"
            " from every write: %d of %d (%.0f%%)" % (
                arm, len(rr), sum(ch), sum(net), fmt(med(ratio)), far, far + near, 100.0 * far / max(1, far + near)))
        dd_ = [S for S in rr if S["t"][1] != "def"]
        ao, oo = sum(S["churn_arm_only"] for S in dd_), sum(S["churn_off_only"] for S in dd_)
        say("         de-dup: pooled burned-in-arm-only %d, burned-in-OFF-only %d, R_ao = %.3f" % (ao, oo, ao / max(1, oo)))
    say("  per run (arm_only/off_only, churn far>6):")
    for arm in ARMS:
        say("    %-6s %s" % (arm, "  ".join("%s %d/%d f%d" % (label(S["t"]).replace("/half", "").replace("east", "E")
                                                          .replace("south", "S"), S["churn_arm_only"],
                                                          S["churn_off_only"], S["churn_far6"])
                                        for S in rows[arm] if S["w1"] is not None)))

    say("")
    say("=" * 100)
    say("4. fmES PER-RUN CORRELATES OF THE INTACT DELTA")
    say("=" * 100)
    es = rows["fmES"]
    say("  %-15s %6s %4s %5s %5s %5s %6s %5s %4s %6s %6s %6s %5s %6s %5s" % (
        "tuple", "delta", "next", "ext1", "Ts", "term", "e<=T/>T", "bw1", "out", "offEv", "grwTs", "brnTs",
        "expo", "churn", "rem1"))
    for S in es:
        rem = []
        for e in S["ext_cons"]:
            f0 = fuel0.get((S["t"][2], e["cell"]))
            if f0 is not None:
                rem.append(f0 - e["consumed"])
        S["rem"] = rem
        S["rem1_frac"] = (sum(1 for r in rem if r == 1) / len(rem)) if rem else None
        say("  %-15s %+6d %4d %5s %5s %5s %3d/%-3d %5s %4s %6d %6s %6s %5d %6d %5s" % (
            label(S["t"]), S["delta"], S["n_ext"], fmt(S["ext1"]), fmt(S["Ts"]), fmt(S["terminal"]),
            S["ext_before_term"], S["ext_after_term"], fmt(S["burning_at_w1"]), fmt(S["first_out"]),
            S["off_ever"], fmt(S["off_growth_after_Ts"]), fmt(S["off_burning_at_Ts"]), S["expo"],
            S["churn_arm_only"] + S["churn_off_only"], fmt(S["rem1_frac"])))
    say("  columns: next = extinguishes; e<=T/>T = extinguishes at/before vs after the arm's terminal_step;")
    say("  bw1 = burning cells at the first write; offEv = OFF ever_burned at 240; grwTs = OFF cells first burning")
    say("  after Ts; brnTs = OFF burning cells at Ts; expo = sum over ticks of misaligned draws on cells at risk;")
    say("  rem1 = share of this run's extinguishes whose cell had exactly 1 fuel left (would burn out next tick)")

    dd = [S for S in es if S["t"][1] != "def"]
    feats = [
        ("n_ext", lambda S: S["n_ext"]),
        ("first extinguish step", lambda S: S["ext1"]),
        ("median extinguish step", lambda S: S["ext_med_step"]),
        ("ext at/before terminal", lambda S: S["ext_before_term"]),
        ("ext after terminal", lambda S: S["ext_after_term"]),
        ("share ext after terminal", lambda S: (S["ext_after_term"] / S["n_ext"]) if S["n_ext"] else None),
        ("burning cells at first write", lambda S: S["burning_at_w1"]),
        ("OFF ever_burned at 240", lambda S: S["off_ever"]),
        ("OFF growth after Ts", lambda S: S["off_growth_after_Ts"]),
        ("OFF burning at Ts", lambda S: S["off_burning_at_Ts"]),
        ("re-roll exposure", lambda S: S["expo"]),
        ("first outside-cone step", lambda S: S["first_out"]),
        ("share ext with 1 fuel left", lambda S: S["rem1_frac"]),
        ("frac D outside cone @240", lambda S: S["frac_out_240"]),
    ]
    say("")
    say("  de-dup 20 (east/def excluded). rho = Spearman vs delta; rho|.| = vs |delta|;")
    say("  AUC(up>down) over changed runs = P(feature of an up run > feature of a down run), 0.5 = no signal")
    ch = [S for S in dd if S["delta"] != 0]
    ups = [S for S in ch if S["delta"] > 0]
    dns = [S for S in ch if S["delta"] < 0]
    say("  changed runs %d: up %d, down %d, unchanged %d" % (len(ch), len(ups), len(dns), len(dd) - len(ch)))
    say("  sign test (one-sided, H0 P(up)=1/2): de-dup fmES %d up of %d changed p %.3f; all-23 fmES %d of %d p %.3f;"
        " all-23 fmF %d of %d p %.4f" % (
            len(ups), len(ch), binom_tail_ge(len(ups), len(ch)),
            sum(1 for S in es if S["delta"] > 0), sum(1 for S in es if S["delta"] != 0),
            binom_tail_ge(sum(1 for S in es if S["delta"] > 0), sum(1 for S in es if S["delta"] != 0)),
            sum(1 for S in rows["fmF"] if S["delta"] > 0), sum(1 for S in rows["fmF"] if S["delta"] != 0),
            binom_tail_ge(sum(1 for S in rows["fmF"] if S["delta"] > 0), sum(1 for S in rows["fmF"] if S["delta"] != 0))))
    say("  p_rho = permutation p of rho (20000 shuffles, fixed seed); p_AUC = exact two-sided permutation p;"
        " %d features tested, Bonferroni 0.05 -> %.4f" % (len(feats), 0.05 / len(feats)))
    STATE["corr"] = {}
    for name, f in feats:
        r1, n1 = spearman([f(S) for S in dd], [S["delta"] for S in dd])
        r2, n2 = spearman([f(S) for S in dd], [abs(S["delta"]) for S in dd])
        au = auc([f(S) for S in ups], [f(S) for S in dns])
        p1 = perm_p_spearman([f(S) for S in dd], [S["delta"] for S in dd])
        pa = perm_p_auc([f(S) for S in ups], [f(S) for S in dns])
        STATE["corr"][name] = (r1, p1, r2, au, pa)
        say("    %-30s rho %6s p_rho %5s (n %2d)  rho|.| %6s  AUC %5s p_AUC %5s   up median %s / down median %s" % (
            name, fmt(r1), fmt(p1, 3), n1, fmt(r2), fmt(au), fmt(pa, 3), fmt(med([f(S) for S in ups])),
            fmt(med([f(S) for S in dns]))))

    say("")
    say("  |delta| SCALES (runs with a write, all 23 tuples; changed runs only in the medians of |delta|)")
    for arm in ARMS:
        rr = [S for S in rows[arm] if S["w1"] is not None]
        chg = [abs(S["delta"]) for S in rr if S["delta"]]
        say("    %-6s runs with write %2d  changed %2d  |delta| median %s mean %s max %s   up %d down %d" % (
            arm, len(rr), len(chg), fmt(med(chg)), fmt(sum(chg) / len(chg) if chg else None, 1), max(chg) if chg else "-",
            sum(1 for S in rr if S["delta"] > 0), sum(1 for S in rr if S["delta"] < 0)))
    say("  by how soon the draw stream shifts (all 4 arms pooled, runs with a write):")
    classes = collections.defaultdict(list)
    for arm in ARMS:
        for S in rows[arm]:
            if S["w1"] is None:
                continue
            if S["Ts"] is None:
                k = "no shift within 240"
            elif S["Ts"] - S["w1"] <= 6:
                k = "shift <= 6 steps after w1"
            elif S["Ts"] - S["w1"] <= 30:
                k = "shift 7-30 steps after w1"
            else:
                k = "shift > 30 steps after w1"
            classes[k].append(S)
    for k in sorted(classes):
        rr = classes[k]
        chg = [abs(S["delta"]) for S in rr if S["delta"]]
        say("    %-28s runs %2d (%s)  up %2d down %2d same %2d  |delta| median %s mean %s  churn/|net| median %s" % (
            k, len(rr), dict(collections.Counter(S["arm"] for S in rr)), sum(1 for S in rr if S["delta"] > 0),
            sum(1 for S in rr if S["delta"] < 0), sum(1 for S in rr if S["delta"] == 0), fmt(med(chg)),
            fmt(sum(chg) / len(chg) if chg else None, 1),
            fmt(med([(S["churn_arm_only"] + S["churn_off_only"]) / abs(S["churn_arm_only"] - S["churn_off_only"])
                     for S in rr if S["churn_arm_only"] != S["churn_off_only"]]))))
    say("  by whether the first outside-cone difference comes within 15 steps of the first write:")
    for arm in ARMS + ["all"]:
        pool = [S for a_ in (ARMS if arm == "all" else [arm]) for S in rows[a_] if S["w1"] is not None]
        early = [S for S in pool if S["first_out"] is not None and S["first_out"] - S["w1"] <= 15]
        late = [S for S in pool if not (S["first_out"] is not None and S["first_out"] - S["w1"] <= 15)]
        def desc(rr):
            chg = [abs(S["delta"]) for S in rr if S["delta"]]
            return "n %2d up %2d down %2d |delta| median %s" % (len(rr), sum(1 for S in rr if S["delta"] > 0),
                                                              sum(1 for S in rr if S["delta"] < 0), fmt(med(chg)))
        say("    %-6s non-local early: %s   | local-first/late: %s" % (arm, desc(early), desc(late)))
    say("  |delta| vs re-roll exposure and vs OFF growth after Ts, all 4 arms pooled (runs with a shift):")
    pool = [S for arm in ARMS for S in rows[arm] if S["Ts"] is not None]
    r_e, n_e = spearman([S["expo"] for S in pool], [abs(S["delta"]) for S in pool])
    r_g, n_g = spearman([S["off_growth_after_Ts"] for S in pool], [abs(S["delta"]) for S in pool])
    r_c, n_c = spearman([S["churn_arm_only"] + S["churn_off_only"] for S in pool], [abs(S["delta"]) for S in pool])
    say("    rho(|delta|, exposure) %s (n %d)   rho(|delta|, OFF growth after Ts) %s (n %d)   rho(|delta|, churn) %s" % (
        fmt(r_e), n_e, fmt(r_g), n_g, fmt(r_c)))
    say("  same fire world, different run (east/def vs east/half at the same seed, fmOFF identical fire):")
    for arm in ARMS:
        m = {S["t"]: S for S in rows[arm]}
        say("    %-6s %s" % (arm, "  ".join("s%d half %+d / def %+d" % (s, m[("east", "half", s)]["delta"],
                                                                   m[("east", "def", s)]["delta"])
                                      for s in (101, 202, 303))))

    say("")
    say("=" * 100)
    say("5. H3 INSTRUMENTS: WHAT fmES EXTINGUISHES")
    say("=" * 100)
    allx = [(S, e) for S in es for e in S["ext_cons"]]
    rem_all = [fuel0.get((S["t"][2], e["cell"])) for S, e in allx]
    known = [(S, e, f0 - e["consumed"]) for (S, e), f0 in zip(allx, rem_all) if f0 is not None]
    say("  extinguishes %d; fuel0 known (cell burnt out naturally in some run of the same seed) for %d" % (
        len(allx), len(known)))
    say("  remaining fuel at the write (1 = would burn out on the next tick anyway): %s" % dict(
        sorted(collections.Counter(r for _S, _e, r in known).items())))
    bad_rem = [r for _S, _e, r in known if r < 1]
    say("  remaining < 1 (would contradict the fuel model): %d" % len(bad_rem))
    say("  after the arm's terminal_step: %d of %d (%.0f%%);  by step: <=60 %d, 61-120 %d, 121-180 %d, >180 %d" % (
        sum(1 for _S, e in allx if e["after_term"]), len(allx), 100.0 * sum(1 for _S, e in allx if e["after_term"]) / max(1, len(allx)),
        sum(1 for _S, e in allx if e["step"] <= 60), sum(1 for _S, e in allx if 60 < e["step"] <= 120),
        sum(1 for _S, e in allx if 120 < e["step"] <= 180), sum(1 for _S, e in allx if e["step"] > 180)))
    say("  burning cells within euclidean 3 of the extinguished cell at the write (arm state): median %s, "
        "0 neighbours %d, <=2 %d" % (fmt(med([e["nb_burning"] for _S, e in allx])),
                                     sum(1 for _S, e in allx if e["nb_burning"] == 0),
                                     sum(1 for _S, e in allx if e["nb_burning"] <= 2)))
    fx = [(S, e) for S in es for e in S["ext_cons"][:1]]
    say("  FIRST extinguish per run (OFF is its exact counterfactual - nothing differs before it):")
    say("    %-15s %4s %-7s %8s %6s %7s %4s %s" % ("tuple", "step", "cell", "OFFburn", "OFFend", "OFFlatch", "rem",
                                                 "OFF steps left burning"))
    for S, e in fx:
        f0 = fuel0.get((S["t"][2], e["cell"]))
        say("    %-15s %4d %-7s %8s %6s %7s %4s %s" % (
            label(S["t"]), e["step"], "%d,%d" % e["cell"], e["off_burning"], fmt(e["off_end"]), fmt(e["off_latch"]),
            fmt(f0 - e["consumed"] if f0 is not None else None),
            fmt((e["off_end"] - e["step"]) if e["off_end"] is not None else None)))
    left = [(e["off_end"] - e["step"]) for _S, e in fx if e["off_end"] is not None]
    say("    OFF steps the cell would still have burned: %s" % sorted(left))
    agree = disagree = 0
    for S, e in fx:
        f0 = fuel0.get((S["t"][2], e["cell"]))
        if f0 is None or e["off_latch"] is None:
            continue
        same_latch = e["off_latch"] == first_tick_after(e["step"])
        if (f0 - e["consumed"] == 1) == same_latch:
            agree += 1
        else:
            disagree += 1
    say("    check: remaining fuel 1 <=> OFF latches on the first tick after the write (so no draw shift from it):"
        " agree %d, disagree %d" % (agree, disagree))
    say("    OFF went on to latch (burn out) this cell later: %d of %d first-extinguished cells; OFF latch - write"
        " step: %s" % (sum(1 for _S, e in fx if e["off_latch"] is not None), len(fx),
                       sorted(e["off_latch"] - e["step"] for _S, e in fx if e["off_latch"] is not None)))
    say("  ALL extinguishes, the OFF cell at the same step (exact counterfactual only before Ts; a proxy after):")
    say("    OFF burning at the write step: %d of %d;  OFF latched the cell by 240: %d" % (
        sum(1 for _S, e in allx if e["off_burning"]), len(allx), sum(1 for _S, e in allx if e["off_latch"] is not None)))
    say("    share of extinguishes by step band that are after the arm's terminal_step: %s" % "  ".join(
        "%s %d/%d" % (nm, sum(1 for _S, e in allx if lo < e["step"] <= hi and e["after_term"]),
                      sum(1 for _S, e in allx if lo < e["step"] <= hi))
        for nm, lo, hi in (("<=60", 0, 60), ("61-120", 60, 120), ("121-180", 120, 180), (">180", 180, 999))))

    say("")
    say("=" * 100)
    say("6. fmEFS WITH ANY EXTINGUISH vs fmF ON THE SAME TUPLE")
    say("=" * 100)
    fm = {S["t"]: S for S in rows["fmF"]}
    say("  %-15s %5s %5s %6s | %4s %-5s %5s %5s | %4s %-5s %5s %5s | %6s %6s" % (
        "tuple", "EFSx", "ext1", "EFScz", "w1", "kind", "Ts", "out", "w1F", "kindF", "TsF", "outF", "dEFS", "dF"))
    cmp_ts = []
    cmp_out = []
    for S in rows["fmEFS"]:
        if not S["n_ext"]:
            continue
        F = fm[S["t"]]
        cz = S["cause"][0][1] if S["cause"] else "-"
        say("  %-15s %5d %5s %6s | %4s %-5s %5s %5s | %4s %-5s %5s %5s | %+6d %+6d" % (
            label(S["t"]), S["n_ext"], fmt(S["ext1"]), cz, fmt(S["w1"]), S["w1_kind"], fmt(S["Ts"]), fmt(S["first_out"]),
            fmt(F["w1"]), F["w1_kind"], fmt(F["Ts"]), fmt(F["first_out"]), S["delta"], F["delta"]))
        cmp_ts.append((S["Ts"], F["Ts"]))
        cmp_out.append((S["first_out"], F["first_out"]))

    def earlier(pairs):
        e = l = s = 0
        for a_, b_ in pairs:
            a_ = NEVER if a_ is None else a_
            b_ = NEVER if b_ is None else b_
            e += a_ < b_
            l += a_ > b_
            s += a_ == b_
        return e, l, s
    say("  EFS shift tick earlier / later / same than fmF: %s;  first outside-cone step earlier / later / same: %s" % (
        earlier(cmp_ts), earlier(cmp_out)))
    pre = [S for S in rows["fmEFS"] if S["n_ext"] and (fm[S["t"]]["Ts"] is None or S["ext1"] < fm[S["t"]]["Ts"])]
    say("  EFS runs whose first extinguish precedes fmF's shift tick: %d of %d: %s" % (
        len(pre), sum(1 for S in rows["fmEFS"] if S["n_ext"]),
        ", ".join("%s ext1 %d < TsF %s -> TsEFS %s (cause %s)" % (
            label(S["t"]), S["ext1"], fmt(fm[S["t"]]["Ts"]), fmt(S["Ts"]), S["cause"][0][1] if S["cause"] else "-")
            for S in pre)))
    say("  EFS first extinguish at or after fmF's shift tick: %d (the stream had already shifted in the matching"
        " firebreak history)" % (sum(1 for S in rows["fmEFS"] if S["n_ext"]) - len(pre)))
    say("  runs with no extinguish in fmEFS: %d: %s" % (
        sum(1 for S in rows["fmEFS"] if not S["n_ext"]),
        ", ".join("%s Ts %s/F %s" % (label(S["t"]), fmt(S["Ts"]), fmt(fm[S["t"]]["Ts"]))
                  for S in rows["fmEFS"] if not S["n_ext"])))
    say("  fmEFS pooled writes: extinguish %d, clear %d (scorched %d)" % (
        sum(S["n_ext"] for S in rows["fmEFS"]), sum(S["n_clr_s"] + S["n_clr_u"] for S in rows["fmEFS"]),
        sum(S["n_clr_s"] for S in rows["fmEFS"])))

    say("")
    say("=" * 100)
    say("7. THE FIREBREAK ARMS AMONG THEMSELVES (same tuple, fmF vs fmFS vs fmEFS)")
    say("=" * 100)
    fs = {S["t"]: S for S in rows["fmFS"]}
    efs = {S["t"]: S for S in rows["fmEFS"]}
    for nm, other in (("fmFS", fs), ("fmEFS", efs)):
        same_series = sum(1 for t in tuples if fm[t]["w1"] is not None and fm[t]["digests"] == other[t]["digests"])
        div = []
        diffs = []
        sign_dis = 0
        for t in tuples:
            if fm[t]["w1"] is None:
                continue
            a_, b_ = fm[t]["digests"], other[t]["digests"]
            dv = next((i + 1 for i, (x, y) in enumerate(zip(a_, b_)) if x != y), None)
            if dv is not None:
                div.append(dv)
                diffs.append(abs(fm[t]["delta"] - other[t]["delta"]))
                if (fm[t]["delta"] > 0) != (other[t]["delta"] > 0) or (fm[t]["delta"] < 0) != (other[t]["delta"] < 0):
                    sign_dis += 1
        say("  fmF vs %-6s runs with a write %d: identical fire 240/240 on %d; differing on %d (first divergence steps"
            " %s); |delta_F - delta_%s| median %s max %s; sign disagreements %d" % (
                nm, sum(1 for t in tuples if fm[t]["w1"] is not None), same_series, len(div), sorted(div), nm,
                fmt(med(diffs)), max(diffs) if diffs else "-", sign_dis))
        STATE.setdefault("fbfb", {})[nm] = {"same": same_series, "differ": len(div), "div_med": med(div),
                                           "diff_med": med(diffs), "sign_dis": sign_dis}
    say("  (the firebreak arms' identical up/down counts are NOT three confirmations: they share the same history")
    say("   up to their first divergence, and their shift ticks coincide on most tuples - section 2)")

    say("")
    say("=" * 100)
    say("8. STOCK REFERENCE VALUES FOR THE CRN PRE-REGISTRATION (de-dup 20, east/def excluded)")
    say("=" * 100)
    REF = {}
    for arm in ARMS:
        rr = [S for S in rows[arm] if S["t"][1] != "def"]
        chg = [abs(S["delta"]) for S in rr if S["delta"]]
        G = sum(S["delta"] for S in rr) / sum(S["off_ever"] for S in rr)
        up = sum(1 for S in rr if S["delta"] > 0)
        dn = sum(1 for S in rr if S["delta"] < 0)
        big_dn = sum(1 for S in rr if S["delta"] <= -20)
        wr = [S for S in rr if S["w1"] is not None]
        small = sum(1 for S in wr if abs(S["delta"]) <= 10)
        REF[arm] = {"median_abs": med(chg), "G": G, "up": up, "down": dn, "big_down": big_dn,
                    "small": small, "n_write": len(wr)}
        say("  %-6s up %2d down %2d unchanged %2d | median |delta| (changed) %s | pooled delta %+d over OFF ever %d:"
            " G = %.4f | down runs <= -20: %d | runs with a write and |delta| <= 10: %d of %d" % (
                arm, up, dn, len(rr) - up - dn, fmt(med(chg)), sum(S["delta"] for S in rr),
                sum(S["off_ever"] for S in rr), G, big_dn, small, len(wr)))
        ins = []
        for lag in (6, 12, 21, 30):
            vals = [S["din"][S["w1"] + lag] + S["dout"][S["w1"] + lag] for S in wr if S["w1"] + lag <= STEPS]
            ins.append("+%d %s" % (lag, fmt(med(vals), 0)))
        say("         median |D| (inside + outside) after the first write: %s" % "  ".join(ins))
    STATE["REF"] = REF

    say("")
    say("=" * 100)
    say("9. RE-ROLL YARDSTICK AND THE POOLED MEAN")
    say("=" * 100)
    say("  Pairs of runs of the same tuple, both reconstructed: Ts_pair = first misaligned draw tick between them;")
    say("  growth = cells first burning after Ts_pair in the reference run (fmOFF for arm-vs-OFF, the first-named arm")
    say("  otherwise); |diff| = |intact difference|. If re-roll noise sets the scale, |diff| tracks growth for every")
    say("  pair type, including pairs that differ by no extinguish at all (firebreak vs firebreak).")
    pair_types = [("fmES-OFF", "fmOFF", "fmES"), ("fmF-OFF", "fmOFF", "fmF"), ("fmFS-OFF", "fmOFF", "fmFS"),
                  ("fmEFS-OFF", "fmOFF", "fmEFS"), ("fmF-fmFS", "fmF", "fmFS"), ("fmF-fmEFS", "fmF", "fmEFS"),
                  ("fmFS-fmEFS", "fmFS", "fmEFS")]
    allpairs = []
    for name, ref, oth in pair_types:
        vals = []
        for t in tuples:
            if t[1] == "def":
                continue
            A, Bk = KEEP[(ref, t)], KEEP[(oth, t)]
            if A["digests"] == Bk["digests"]:
                continue
            ticks, dA, dO, mis = draw_alignment(Bk["L"], A["L"])
            anym = mis.any(1)
            Tsp = int(ticks[int(np.argmax(anym))]) if anym.any() else None
            if Tsp is None:
                vals.append((t, None, None, abs(Bk["intact"] - A["intact"])))
                continue
            growth = int(((A["fb"] > Tsp) & (A["fb"] < NEVER)).sum())
            vals.append((t, Tsp, growth, abs(Bk["intact"] - A["intact"])))
        allpairs += [(name,) + v for v in vals]
        ratio = [d / g for _t, T, g, d in vals if g]
        say("    %-11s pairs %2d (no shift %d)  Ts_pair median %s  growth median %s  |diff| median %s  |diff|/growth"
            " median %s" % (name, len(vals), sum(1 for v in vals if v[1] is None), fmt(med([v[1] for v in vals])),
                            fmt(med([v[2] for v in vals])), fmt(med([v[3] for v in vals])), fmt(med(ratio), 3)))
        STATE.setdefault("yard", {})[name] = {"n": len(vals), "Ts": med([v[1] for v in vals]),
                                             "growth": med([v[2] for v in vals]), "diff": med([v[3] for v in vals]),
                                             "ratio": med(ratio)}
    pp = [p for p in allpairs if p[2] is not None]
    r_all, n_all = spearman([p[3] for p in pp], [p[4] for p in pp])
    STATE["yard_rho"] = (r_all, n_all)
    say("    rho(|diff|, growth after Ts_pair) over all %d de-dup pairs: %s" % (n_all, fmt(r_all)))
    for lo, hi in ((0, 250), (250, 600), (600, 1000), (1000, 3000)):
        grp = collections.defaultdict(list)
        for p in pp:
            if lo <= p[3] < hi:
                grp["ES-OFF" if p[0] == "fmES-OFF" else ("FB-OFF" if p[0].endswith("-OFF") else "FB-FB")].append(p[4])
        say("    growth %4d-%-4d  |diff| median: ES-OFF %s (n %d)   firebreak-OFF %s (n %d)   firebreak-firebreak %s (n %d)" % (
            lo, hi, fmt(med(grp["ES-OFF"])), len(grp["ES-OFF"]), fmt(med(grp["FB-OFF"])), len(grp["FB-OFF"]),
            fmt(med(grp["FB-FB"])), len(grp["FB-FB"])))

    say("")
    say("  Pooled mean delta, exact sign-flip randomisation test (H0: per-run delta symmetric about 0):")
    for arm in ARMS:
        for nm, sel in (("de-dup 20", lambda S: S["t"][1] != "def"), ("all 23", lambda S: True)):
            v = np.array([S["delta"] for S in rows[arm] if sel(S) and S["delta"] != 0], dtype=np.int64)
            n = len(v)
            obs = abs(int(v.sum()))
            signs = (((np.arange(2 ** n, dtype=np.int64)[:, None] >> np.arange(n)) & 1) * 2 - 1)
            sums = np.abs(signs @ v)
            p = float((sums >= obs).mean())
            allv = [S["delta"] for S in rows[arm] if sel(S)]
            mean = sum(allv) / len(allv)
            sd = math.sqrt(sum((x - mean) ** 2 for x in allv) / (len(allv) - 1))
            phi = 0.5 * (1 + math.erf((mean / sd) / math.sqrt(2)))
            say("    %-6s %-9s mean %+7.1f  sd %6.1f  se %5.1f  sign-flip p (two-sided) %.4f  mean/sd %.2f ->"
                " normal-approx P(up) %.2f (observed up share of changed %.2f)" % (
                    arm, nm, mean, sd, sd / math.sqrt(len(allv)), p, mean / sd, phi,
                    sum(1 for x in allv if x > 0) / max(1, sum(1 for x in allv if x != 0))))
            STATE.setdefault("flip", {})[(arm, nm)] = {
                "mean": mean, "sd": sd, "p": p, "phi": phi,
                "share": sum(1 for x in allv if x > 0) / max(1, sum(1 for x in allv if x != 0))}
            del signs, sums

    say("")
    say("  median |D inside| / |D outside| by kind of the FIRST write (all arms pooled):")
    for kind in ("ext", "clr_s", "clr_u"):
        rr = [S for arm in ARMS for S in rows[arm] if S["w1_kind"] == kind]
        parts = []
        for lag in LAGS:
            ins = [S["din"][S["w1"] + lag] for S in rr if S["w1"] + lag <= STEPS]
            ous = [S["dout"][S["w1"] + lag] for S in rr if S["w1"] + lag <= STEPS]
            parts.append("+%d %s/%s" % (lag, fmt(med(ins), 0), fmt(med(ous), 0)))
        say("    %-5s n %2d  %s" % (kind, len(rr), "  ".join(parts)))
    say("  V4 strength: u0 (first misaligned uid at Ts, of 2500), outside-cone D cells at Ts (all at uid >= u0 by V4),")
    say("  and the negative control: outside-cone D cells with uid < u0 ONE TICK LATER (when every draw is misaligned):")
    v4r = [S for arm in ARMS for S in rows[arm] if S["Ts"] is not None and S["dout"][S["Ts"]]]
    say("    %s" % "  ".join("%s %s u0 %d out %d below-u0-next %s" % (
        S["arm"], label(S["t"]), S["u0"], S["dout"][S["Ts"]], fmt(S["V4_next_below"])) for S in v4r))
    say("    runs where below-u0 outside differences appear one tick later: %d of %d (cells: %d)" % (
        sum(1 for S in v4r if S["V4_next_below"]), sum(1 for S in v4r if S["V4_next_below"] is not None),
        sum(S["V4_next_below"] or 0 for S in v4r)))
    STATE["v4neg"] = (sum(1 for S in v4r if S["V4_next_below"]), sum(1 for S in v4r if S["V4_next_below"] is not None),
                      sum(S["V4_next_below"] or 0 for S in v4r))

    say("")
    say("=" * 100)
    say("10. PRE-REGISTERED RULE - DRY RUN ON STOCK DATA (fmES vs fmOFF, control fmF; crn checks off)")
    say("=" * 100)
    E, F = prereg_measures(rows["fmES"], rows["fmF"])
    for line in prereg_verdict(E, F, crn=False):
        say("  " + line)
    say("  (on stock data the rule reads the coin flip as it stands; on CRN data --prereg-tags f2cOFF,f2cES,f2cF")
    say("   applies the identical code with the light-cone validity check switched on)")
    STATE["prereg_stock"] = (E, F)

    STATE["rows"] = rows
    STATE["offs"] = offs
    narr = narrative(rows)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(narr) + "\n\n" + "#" * 100 + "\n# DETAILED DATA SECTIONS (everything the narrative"
                " quotes is printed below)\n" + "#" * 100 + "\n\n" + "\n".join(OUT) + "\n")


STATE: dict = {}
KEEP: dict = {}

if __name__ == "__main__":
    main()
