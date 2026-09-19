"""Adversarial verifier for task D (completion threshold), outputs/_fm2_diag_priority.{py,txt}.

Independent re-derivation from the raw harness JSON. Read-only. No simulation. Does not import the
analyst's script. Prints to stdout only.

Own implementations (deliberately different code paths from the analyst):
  fire view      burning = burn_intervals; burnt-by-s = burnt at 240 (fire_ground_final[1]) and the
                 end of the LAST burn interval <= s, for cells never worked; worked cells are non-fuel
                 from their first work step. Unit view at step s: same-step writes of units that advance
                 earlier are applied, own/later ones are not (order tested both ways).
  reachability   time-stepped numpy propagation (reachable-burning mask per post-step), not intervals.
"""
from __future__ import annotations

import collections
import json
import os
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N, S, INF = 50, 240, 10 ** 6
CAN = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("east", "def", s) for s in (101, 202, 303)])
FR = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
      + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
ALLT = CAN + FR
ARMS = ["fmEFS", "fmF", "fmFS", "fmES", "fmDRY"]
WORKA = ("clear", "extinguish")
BANDOFF = sorted([(dx, dy, dx * dx + dy * dy) for dx in range(-5, 6) for dy in range(-5, 6)
                  if dx * dx + dy * dy <= 25], key=lambda o: o[2])
K9 = [(dx, dy) for dx in range(-3, 4) for dy in range(-3, 4) if 0 < dx * dx + dy * dy <= 9]
K4 = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if 0 < dx * dx + dy * dy <= 4]


def P(*a):
    print(" ".join(str(x) for x in a))
    sys.stdout.flush()


def lab(t):
    return "%s/%s/%d" % t


def fpath(tag, t):
    return os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], t[1], t[2]))


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def md(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def manh(c, R):
    x, y = c
    out = []
    for dx in range(-R, R + 1):
        k = R - abs(dx)
        for dy in range(-k, k + 1):
            if 0 <= x + dx < N and 0 <= y + dy < N:
                out.append((x + dx, y + dy))
    return out


def d2map(burn):
    out = np.full((N, N), 999, np.int32)
    p = np.zeros((N + 10, N + 10), bool)
    p[5:5 + N, 5:5 + N] = burn
    for dx, dy, d2 in BANDOFF:
        sh = p[5 + dx:5 + dx + N, 5 + dy:5 + dy + N]
        out = np.where(sh & (out == 999), d2, out)
    return out


def dil(m, offs):
    p = np.zeros((N + 6, N + 6), bool)
    p[3:3 + N, 3:3 + N] = m
    out = np.zeros((N, N), bool)
    for dx, dy in offs:
        out |= p[3 + dx:3 + dx + N, 3 + dy:3 + dy + N]
    return out


class Run:
    def __init__(self, tag, t):
        with open(fpath(tag, t), encoding="utf-8") as f:
            d = json.load(f)
        self.tag, self.t, self.d = tag, t, d
        self.term = d.get("terminal_step")
        assert self.term == d["eval"].get("terminal_step"), "terminal mismatch"
        self.dry = tag == "fmDRY"
        self.B = np.zeros((S + 2, N, N), bool)
        self.ivs = {}
        self.abut = 0
        for k, iv in (d.get("burn_intervals") or {}).items():
            x, y = (int(v) for v in k.split(","))
            L = sorted((a, S + 1 if b is None else b) for a, b in iv)
            self.ivs[(x, y)] = L
            for i, (a, b) in enumerate(L):
                self.B[a:b, x, y] = True
                if i and L[i - 1][1] >= a:
                    self.abut += 1
        self.fbs = np.full((N, N), INF, np.int64)
        for k, s in (d.get("first_burn_step") or {}).items():
            x, y = (int(v) for v in k.split(","))
            self.fbs[x, y] = s
        self.burnt240 = np.zeros((N, N), bool)
        self.ever = 0
        for k, v in (d.get("fire_ground_final") or {}).items():
            x, y = (int(q) for q in k.split(","))
            self.burnt240[x, y] = bool(v[1])
            self.ever += int(bool(v[0]))
        self.lastend = np.full((N, N), INF, np.int64)
        for (x, y), L in self.ivs.items():
            fin = [b for a, b in L if b <= S]
            if fin:
                self.lastend[x, y] = max(fin)
        self.log = d.get("firefight_log") or []
        self.rows = collections.defaultdict(dict)
        for r in self.log:
            self.rows[r["ff"]][r["step"]] = r
        if self.dry:
            self.work = [r for r in self.log if r["action"] in WORKA and r.get("dry")]
        else:
            self.work = [r for r in self.log if r["action"] in WORKA and r.get("wrote")]
        self.stale = sum(1 for r in self.log if r["action"] in WORKA and not r.get("wrote") and not self.dry)
        self.wfirst = np.full((N, N), INF, np.int64)
        self.work_at = collections.defaultdict(list)
        for r in self.work:
            c = tuple(r["target"])
            self.wfirst[c] = min(self.wfirst[c], r["step"])
            self.work_at[r["step"]].append(r)
        self.worked_ever = self.wfirst < INF
        self.pos = collections.defaultdict(dict)
        for i, row in enumerate(d.get("ff_steps") or []):
            for ff, p, st, asg, ex, dead in row:
                self.pos[ff][i + 1] = (tuple(p) if p is not None else None, st, asg, ex, dead)
        self.vfinal = {}
        self.vdead = {}
        for i, row in enumerate(d.get("victim_steps") or []):
            for vid, p, st in row:
                self.vfinal[vid] = st
                if st == "dead" and vid not in self.vdead:
                    self.vdead[vid] = i + 1
        self.ok = [a for a in (d.get("assigns") or []) if a.get("ok")]

    def burning_from(self, c, k):
        """first post-step >= k at which cell c is burning"""
        for a, b in self.ivs.get(c, ()):
            st = max(a, k)
            if st < b:
                return st
        return None

    def state(self, s):
        burn = self.B[s]
        worked = self.wfirst <= s
        burnt = self.burnt240 & ~self.worked_ever & (self.lastend <= s)
        fuel = ~burn & ~worked & ~burnt
        d2 = d2map(burn)
        return {"burn": burn, "worked": worked, "burnt": burnt, "fuel": fuel, "d2": d2,
                "band": fuel & (d2 > 4) & (d2 <= 25)}

    def reach_dep(self, r, blocked, offs=K9):
        bl = np.zeros((N, N), bool)
        for c in blocked:
            bl[c] = True
        Bb = self.B & ~bl[None, :, :]
        R = Bb[r].copy()
        ever = np.zeros((N, N), bool)
        for t in range(r + 1, S + 1):
            cur, prv = Bb[t], Bb[t - 1]
            R = (cur & prv & R) | (cur & ~prv & dil(R, offs))
            ever |= R
        dep = (self.fbs > r) & (self.fbs <= S) & ~bl & ~ever
        return dep, bl


# ---------------------------------------------------------------- section 0 validation
def validate(run, order):
    rank = {u: i for i, u in enumerate(order)}
    res = collections.Counter()
    cache = {}
    for r in run.log:
        s, u = r["step"], r["ff"]
        same = run.work_at.get(s, ())
        early = [w for w in same if rank[w["ff"]] < rank[u]]
        late = [w for w in same if rank[w["ff"]] >= rank[u]]
        worked = run.wfirst < s
        for w in early:
            worked = worked.copy() if worked is run.wfirst else worked
            worked[tuple(w["target"])] = True
        burn = run.B[s]
        extra = []
        if not run.dry:
            extra = [tuple(w["target"]) for w in late if w["action"] == "extinguish"]
        if extra:
            burn = burn.copy()
            for c in extra:
                burn[c] = True
        # worked cells whose first work is AT s by a late unit: not worked in the view
        burnt = run.burnt240 & ~run.worked_ever & (run.lastend <= s)
        fuel = ~burn & ~worked & ~burnt
        key = (s, tuple(sorted(extra)))
        if key not in cache:
            cache.clear()
            cache[key] = d2map(burn)
        d2 = cache[key]
        ring = (d2 > 4) & (d2 <= 25)
        if r.get("band") is not None:
            res["band_n"] += 1
            res["band_ok"] += int(int((fuel & ring).sum()) == r["band"])
            fa = (run.fbs > s) & ~worked & ~burn
            res["ap_ok"] += int(int((fa & ring).sum()) == r["band"])
        if r.get("front") is not None:
            shadow = worked if run.dry else np.zeros((N, N), bool)
            nb = np.zeros((N, N), bool)
            nb[1:, :] |= fuel[:-1, :]
            nb[:-1, :] |= fuel[1:, :]
            nb[:, 1:] |= fuel[:, :-1]
            nb[:, :-1] |= fuel[:, 1:]
            res["front_n"] += 1
            res["front_ok"] += int(int((burn & ~shadow & nb).sum()) == r["front"])
        xs, ys = np.nonzero(burn)
        cx, cy = r["cell"]
        dd = int((np.abs(xs - cx) + np.abs(ys - cy)).min()) if len(xs) else 999
        res["dist_n"] += 1
        res["dist_ok"] += int(dd == r["dist"])
    return res


def main():
    # victim finals for fmOFF
    offv, off_ever_cl = {}, {}
    for t in ALLT:
        o = Run("fmOFF", t)
        offv[t] = dict(o.vfinal)
        off_ever_cl[t] = (o.ever, int(o.d.get("fire_cleared_unburned_final") or 0))
        del o
    P("fmOFF loaded")
    summary = {}
    for tag in ARMS:
        A = collections.defaultdict(list)
        V = collections.Counter()
        stops = []
        intact = [0, 0]
        exp = collections.Counter()
        for t in ALLT:
            run = Run(tag, t)
            ev_ec = (run.ever, int(run.d.get("fire_cleared_unburned_final") or 0))
            di = (off_ever_cl[t][0] + off_ever_cl[t][1]) - (ev_ec[0] + ev_ec[1])
            intact[0] += di
            if t[1] != "def":
                intact[1] += di
            if tag in ("fmEFS", "fmDRY", "fmF"):
                for oname, order in (("u0first", ["ff_unit_0", "ff_unit_1"]), ("u1first", ["ff_unit_1", "ff_unit_0"])):
                    if oname == "u1first" and tag != "fmEFS":
                        continue
                    V.update({oname + ":" + k: v for k, v in validate(run, order).items()})
            else:
                V.update({"u0first:" + k: v for k, v in validate(run, ["ff_unit_0", "ff_unit_1"]).items()})
            V["stale"] += run.stale
            V["abut"] += run.abut
            # ---- preemptions
            evs = []
            for a in run.ok:
                s, u = a["step"], a["ff"]
                now, prev = run.rows[u].get(s), run.rows[u].get(s - 1)
                if not ((now is not None and now.get("engaged")) or (now is None and prev is not None and prev.get("engaged"))):
                    continue
                win = [w for w in run.work if w["ff"] == u and s - 10 < w["step"] <= s]
                cl = [w for w in win if w["action"] == "clear"]
                ex = [w for w in win if w["action"] == "extinguish"]
                cls = "W" if cl else ("X" if ex else "A")
                pp = run.pos[u].get(s - 1)
                redis = now is None and pp is not None and bool(pp[2])
                e = {"t": t, "s": s, "u": u, "vid": a["vid"], "cls": cls, "redis": redis, "now": now is not None,
                     "cl": cl, "win": win, "reason": a["reason"]}
                evs.append(e)
            for e in evs:
                A["ev"].append((lab(t), e["s"], e["u"], e["vid"], e["cls"], e["redis"], e["now"],
                                None if run.term is None else e["s"] - run.term, t in CAN))
            # ---- W segment metrics (distinct and re-dispatch)
            for e in evs:
                if e["cls"] != "W":
                    continue
                s, u = e["s"], e["u"]
                anc = tuple(e["cl"][-1]["target"])
                st = run.state(s)
                m = {"t": t, "s": s, "u": u, "vid": e["vid"], "redis": e["redis"], "anchor": anc}
                for R in (3, 5, 8, 12, 16):
                    m["R%d" % R] = [c for c in manh(anc, R) if st["band"][c]]
                m["n3"], m["n5"] = len(m["R3"]), len(m["R5"])
                fa = (run.fbs > s) & ~st["worked"] & ~st["burn"] & (st["d2"] > 4) & (st["d2"] <= 25)
                m["ap3"] = sum(1 for c in manh(anc, 3) if fa[c])
                near = [tuple(w["target"]) for w in e["cl"]] + [anc]
                later = sorted((w["step"], w["ff"]) for w in run.work if w["action"] == "clear" and w["step"] > s
                               and min(md(tuple(w["target"]), c) for c in near) <= 5)
                m["first_other"] = next((k - s for k, f in later if f != u), None)
                m["first_same"] = next((k - s for k, f in later if f == u), None)
                m["nobody"] = not later
                fate = collections.Counter()
                igs = []
                for c in m["R3"]:
                    fw = min((w["step"] for w in run.work if tuple(w["target"]) == c and w["step"] > s), default=None)
                    ig = run.burning_from(c, s + 1)
                    if fw is not None and (ig is None or fw < ig):
                        fate["c"] += 1
                    elif ig is not None:
                        fate["b"] += 1
                        igs.append(ig)
                    else:
                        fate["o"] += 1
                m["fate"] = fate
                m["breach"] = (min(igs) - s) if igs else None
                for M in (5, 8):
                    cells = [c for c in manh(anc, M) if st["fuel"][c] and st["d2"][c] > 25 and run.fbs[c] > s]
                    m["stake%d" % M] = sum(1 for c in cells if run.fbs[c] <= S)
                base = []
                if run.dry:
                    base = [tuple(int(v) for v in c) for c in np.argwhere(st["worked"] & ~st["burn"] & ~st["burnt"])]
                d0, _ = run.reach_dep(s, base)
                m["san"] = int(d0.sum()) if not run.dry else 0
                if tag in ("fmEFS", "fmF", "fmFS", "fmDRY"):
                    for key, blk, offs in (("dep3", m["R3"], K9), ("dep5", m["R5"], K9), ("dep8", m["R8"], K9),
                                           ("dep12", m["R12"], K9), ("dep16", m["R16"], K9)):
                        if not blk:
                            m[key] = 0
                            continue
                        dx_, _ = run.reach_dep(s, base + blk, offs)
                        m[key] = int((dx_ & ~d0).sum())
                    if tag == "fmEFS":
                        d0s, _ = run.reach_dep(s, base, K4)
                        for key, blk in (("dep3s", m["R3"]), ("dep5s", m["R5"])):
                            if not blk:
                                m[key] = 0
                                continue
                            dx_, _ = run.reach_dep(s, base + blk, K4)
                            m[key] = int((dx_ & ~d0s).sum())
                        ring = [tuple(int(v) for v in c) for c in np.argwhere(~st["burn"] & ~st["burnt"] & (st["d2"] > 4) & (st["d2"] <= 25))]
                        dr, bl = run.reach_dep(s, ring)
                        beyond = st["fuel"] & (st["d2"] > 25) & (run.fbs > s) & (run.fbs <= S)
                        m["ring_beyond"] = int(beyond.sum())
                        m["ring_missed"] = int((beyond & ~dr).sum())
                        m["ring_dep"] = int(dr.sum())
                # ---- cost
                vid = e["vid"]
                nxt = min((a["step"] for a in run.ok if a["ff"] == u and a["step"] > s), default=INF)
                cont = next((x for x in (run.d.get("exit_starts") or []) if x["ff"] == u and x["victim"] == vid
                             and s <= x["step"] < nxt), None)
                comp = next((x for x in (run.d.get("completions") or []) if x["ff"] == u and x["victim"] == vid
                             and s <= x["step"] < nxt), None)
                m["final"] = run.vfinal.get(vid)
                m["off_final"] = offv[t].get(vid)
                m["lat"] = cont["step"] - s if cont else None
                m["s_cell"] = None
                if cont:
                    ig = run.burning_from(tuple(cont["victim_pos"]), cont["step"])
                    m["s_cell"] = ig - cont["step"] if ig is not None else None
                end = comp["step"] if comp else min(nxt - 1, S)
                dth = next((k for k in sorted(run.pos[u]) if run.pos[u][k][4]), None)
                if dth is not None:
                    end = min(end, dth)
                sp = []
                for k in range(s, end + 1):
                    p = run.pos[u].get(k, (None,))[0]
                    if p is None:
                        continue
                    ig = run.burning_from(p, k)
                    if ig is not None:
                        sp.append(ig - k)
                m["s_path"] = min(sp) if sp else None
                A["W"].append(m)
            # ---- preempted victims (distinct, all classes)
            for e in evs:
                if e["redis"]:
                    continue
                A["vict"].append((t, e["vid"], e["cls"], run.vfinal.get(e["vid"]), offv[t].get(e["vid"])))
            # ---- stops baseline (firebreak arms)
            if tag != "fmES":
                pre_u = collections.defaultdict(list)
                for e in evs:
                    pre_u[e["u"]].append(e["s"])
                for u in ("ff_unit_0", "ff_unit_1"):
                    wk = [w for w in run.work if w["ff"] == u]
                    for w in wk:
                        if w["action"] != "clear":
                            continue
                        tt, c = w["step"], tuple(w["target"])
                        if any(tt < x["step"] <= tt + 10 and md(tuple(x["target"]), c) <= 5 for x in wk):
                            continue
                        pre = any(tt <= s <= tt + 9 for s in pre_u[u])
                        st = run.state(tt)
                        cells = [q for q in manh(c, 5) if st["fuel"][q] and st["d2"][q] > 25 and run.fbs[q] > tt]
                        crossed = sum(1 for q in cells if run.fbs[q] <= S)
                        stops.append((tt, pre, crossed, run.term is None or tt <= run.term))
            # ---- exposure
            clears = [w for w in run.work if w["action"] == "clear"]
            exp["clears"] += len(clears)
            exp["pre_term"] += sum(1 for w in clears if run.term is None or w["step"] <= run.term)
            exp["nonterm_run"] += sum(1 for w in clears if run.term is None)
            last_ok = max((a["step"] for a in run.ok), default=-1)
            exp["before_last_assign"] += sum(1 for w in clears if w["step"] <= last_ok)
            wev = [e for e in evs if e["cls"] == "W" and not e["redis"]]
            inwin = set()
            mult = 0
            for e in wev:
                ids = [id(w) for w in e["cl"]]
                inwin.update(ids)
                mult += len(ids)
            wev_all = [e for e in evs if e["cls"] == "W"]
            exp["w_win_union"] += len(inwin)
            exp["w_win_mult_distinct"] += mult
            exp["w_win_mult_all"] += sum(len(e["cl"]) for e in wev_all)
            eng = [r for r in run.log if r.get("engaged")]
            exp["engaged"] += len(eng)
            exp["eng_after"] += sum(1 for r in eng if run.term is not None and r["step"] > run.term)
            del run
        summary[tag] = (A, V, stops, intact, exp)
        report(tag, A, V, stops, intact, exp)


def report(tag, A, V, stops, intact, exp):
    P("")
    P("=" * 90)
    P("ARM", tag)
    P("  validation:", dict(V))
    ev = A["ev"]
    dist = [x for x in ev if not x[5]]
    P("  preemptions counted %d, distinct %d, re-dispatch %s" % (len(ev), len(dist), [x[:4] for x in ev if x[5]]))
    P("  counted W/X/A", collections.Counter(x[4] for x in ev), " distinct", collections.Counter(x[4] for x in dist))
    P("  de-dup (no east/def) counted", len([x for x in ev if "/def/" not in x[0]]),
      collections.Counter(x[4] for x in ev if "/def/" not in x[0]))
    P("  s<=20: %d of %d (W among %d)" % (sum(1 for x in ev if x[1] <= 20), len(ev), sum(1 for x in ev if x[1] <= 20 and x[4] == "W")))
    P("  terminal: before %d nonterm %d at %d after %d; median steps before %s; at-terminal rows %s" % (
        sum(1 for x in ev if x[7] is not None and x[7] < 0), sum(1 for x in ev if x[7] is None),
        sum(1 for x in ev if x[7] == 0), sum(1 for x in ev if x[7] is not None and x[7] > 0),
        med([-x[7] for x in ev if x[7] is not None and x[7] < 0]), [x for x in ev if x[7] == 0]))
    P("  assign with row at s / without:", sum(1 for x in ev if x[6]), sum(1 for x in ev if not x[6]))
    P("  canonical W", sum(1 for x in ev if x[8] and x[4] == "W"), "fresh W", sum(1 for x in ev if not x[8] and x[4] == "W"))
    W = A["W"]
    Wd = [m for m in W if not m["redis"]]
    if Wd:
        P("  --- W events (distinct %d) ---" % len(Wd))
        for m in W:
            P("   %-16s s=%3d %s anc=%s n3=%d n5=%d ap3=%d oth=%s same=%s nobody=%s fate=%s brch=%s stk5=%d stk8=%d san=%d "
              "dep3=%s dep5=%s dep8=%s dep16=%s d3s=%s d5s=%s ring=%s/%s  final=%s off=%s lat=%s Sc=%s Sp=%s%s" % (
                  lab(m["t"]), m["s"], m["u"][-1], m["anchor"], m["n3"], m["n5"], m["ap3"], m["first_other"], m["first_same"],
                  m["nobody"], dict(m["fate"]), m["breach"], m["stake5"], m["stake8"], m["san"], m.get("dep3"), m.get("dep5"),
                  m.get("dep8"), m.get("dep16"), m.get("dep3s"), m.get("dep5s"), m.get("ring_missed"), m.get("ring_beyond"),
                  m["final"], m["off_final"], m["lat"], m["s_cell"], m["s_path"], " r" if m["redis"] else ""))
        n3 = [m["n3"] for m in Wd]
        P("  n3 median %s sum %d max %d | n5 median %s sum %d" % (med(n3), sum(n3), max(n3), med([m["n5"] for m in Wd]),
                                                              sum(m["n5"] for m in Wd)))
        P("  nobody %d | other %d (median %s) | same %d (median %s)" % (
            sum(1 for m in Wd if m["nobody"]), sum(1 for m in Wd if m["first_other"] is not None),
            med([m["first_other"] for m in Wd]), sum(1 for m in Wd if m["first_same"] is not None),
            med([m["first_same"] for m in Wd])))
        ne = [m for m in Wd if m["n3"] > 0]
        P("  R3 non-empty %d breached %d completed %d | stake5 crossed %d cells %d | stake8 crossed %d cells %d" % (
            len(ne), sum(1 for m in ne if m["fate"]["b"] > 0), sum(1 for m in ne if m["fate"]["c"] == m["n3"]),
            sum(1 for m in Wd if m["stake5"] > 0), sum(m["stake5"] for m in Wd),
            sum(1 for m in Wd if m["stake8"] > 0), sum(m["stake8"] for m in Wd)))
        cand = [m for m in ne if m["fate"]["b"] > 0 and m["breach"] is not None and m["breach"] > m["n3"]]
        P("  geometric (a)(b)(c): breached %d in-time %d stake5>0 %d cells %d" % (
            sum(1 for m in ne if m["fate"]["b"] > 0), len(cand), sum(1 for m in cand if m["stake5"] > 0),
            sum(m["stake5"] for m in cand if m["stake5"] > 0)))
        if Wd[0].get("dep3") is not None:
            P("  dep sums: dep3 %d dep5 %d dep8 %d dep12 %d dep16 %d | sanity max %d" % tuple(
                [sum(m[k] for m in Wd) for k in ("dep3", "dep5", "dep8", "dep12", "dep16")] + [max(m["san"] for m in Wd)]))
            P("  dep3 canonical/fresh %d/%d dep5 %d/%d" % (
                sum(m["dep3"] for m in Wd if m["t"] in CAN), sum(m["dep3"] for m in Wd if m["t"] in FR),
                sum(m["dep5"] for m in Wd if m["t"] in CAN), sum(m["dep5"] for m in Wd if m["t"] in FR)))
            P("  median n8 %s n12 %s n16 %s" % (med([len(m["R8"]) for m in Wd]), med([len(m["R12"]) for m in Wd]),
                                             med([len(m["R16"]) for m in Wd])))
        if Wd[0].get("dep3s") is not None:
            P("  strong links dep3s %d dep5s %d | ring: events all-cut %d/%d, beyond %d, missed %d, ring_dep %d" % (
                sum(m["dep3s"] for m in Wd), sum(m["dep5s"] for m in Wd),
                sum(1 for m in Wd if m["ring_missed"] == 0), len(Wd), sum(m["ring_beyond"] for m in Wd),
                sum(m["ring_missed"] for m in Wd), sum(m["ring_dep"] for m in Wd)))
        resc = [m for m in Wd if m["final"] == "rescued"]
        P("  COST: delay3 median %s max %d sum %d; rescued W %d, lat median %s; R5 median %s" % (
            med(n3), max(n3), sum(n3), len(resc), med([m["lat"] for m in resc]), med([m["n5"] for m in Wd])))
        P("  at risk S_cell<n3 %s | S_path<n3 %s" % (
            [(lab(m["t"]), m["s"], m["vid"], m["s_cell"], m["n3"], m["off_final"]) for m in resc if m["s_cell"] is not None and m["s_cell"] < m["n3"]],
            [(lab(m["t"]), m["s"], m["vid"], m["s_path"], m["n3"]) for m in resc if m["s_path"] is not None and m["s_path"] < m["n3"]]))
        wv = {}
        for m in Wd:
            wv[(m["t"], m["vid"])] = (m["final"], m["off_final"])
        P("  W victims %d lost arm %d lost OFF %d arm-only %s OFF-only %s" % (
            len(wv), sum(1 for f, o in wv.values() if f != "rescued"), sum(1 for f, o in wv.values() if o != "rescued"),
            [(lab(k[0]), k[1]) for k, (f, o) in wv.items() if f != "rescued" and o == "rescued"],
            [(lab(k[0]), k[1]) for k, (f, o) in wv.items() if f == "rescued" and o != "rescued"]))
    av = {}
    for t, vid, cls, f, o in A["vict"]:
        av[(t, vid)] = (f, o)
    P("  all preempted victims %d lost arm %d lost OFF %d arm-only %s OFF-only %s" % (
        len(av), sum(1 for f, o in av.values() if f != "rescued"), sum(1 for f, o in av.values() if o != "rescued"),
        [(lab(k[0]), k[1]) for k, (f, o) in av.items() if f != "rescued" and o == "rescued"],
        [(lab(k[0]), k[1]) for k, (f, o) in av.items() if f == "rescued" and o != "rescued"]))
    if stops:
        pe = [x for x in stops if x[1]]
        npe = [x for x in stops if not x[1]]
        P("  STOPS %d: preempted %d crossed %d med t %s | non-preempted %d crossed %d med t %s | non-pre t<=60 %d | "
          "non-pre pre-terminal %d crossed %d | preempted t<=60 %d" % (
              len(stops), len(pe), sum(1 for x in pe if x[2] > 0), med([x[0] for x in pe]), len(npe),
              sum(1 for x in npe if x[2] > 0), med([x[0] for x in npe]), sum(1 for x in npe if x[0] <= 60),
              sum(1 for x in npe if x[3]), sum(1 for x in npe if x[3] and x[2] > 0), sum(1 for x in pe if x[0] <= 60)))
    P("  intact vs OFF counted %+d dedup %+d" % tuple(intact))
    P("  exposure", dict(exp))


def strict_dep(run, r, blocked):
    """Variant: at every fire tick (step % 3 == 0) a burning cell - new OR continuing - is reachable only if a
    reachable cell within euclid 3 burned at the previous post-step (probability_of_fire has no self term,
    so a burning cell's continuation also needs burning neighbours). Between ticks the state carries."""
    bl = np.zeros((N, N), bool)
    for c in blocked:
        bl[c] = True
    Bb = run.B & ~bl[None, :, :]
    R = Bb[r].copy()
    ever = np.zeros((N, N), bool)
    for t in range(r + 1, S + 1):
        cur, prv = Bb[t], Bb[t - 1]
        if t % 3 == 0:
            R = cur & dil(R, K9)
        else:
            R = (cur & prv & R) | (cur & ~prv & dil(R, K9))
        ever |= R
    return (run.fbs > r) & (run.fbs <= S) & ~bl & ~ever


def pressure_share(run, r, R3, anchor, M=8):
    """For cells within manhattan M of the anchor first igniting after r: share of the (wind-free) ignition
    pressure sum(d^-2) at k-1 that came from R3 cells, and how many had >= 1 R3 parent."""
    R3s = set(R3)
    shares, with_par = [], 0
    for c in manh(anchor, M):
        k = run.fbs[c]
        if not (r < k <= S):
            continue
        tot = part = 0.0
        for dx, dy in K9:
            q = (c[0] + dx, c[1] + dy)
            if 0 <= q[0] < N and 0 <= q[1] < N and run.B[k - 1][q]:
                w = 1.0 / (dx * dx + dy * dy)
                tot += w
                if q in R3s:
                    part += w
        if tot > 0:
            shares.append(part / tot)
            with_par += int(part > 0)
    return shares, with_par


def extra():
    for tag in ("fmEFS", "fmF", "fmFS"):
        tots = collections.Counter()
        ost = collections.Counter()
        alt = []
        allshares = []
        P("")
        P("EXTRA", tag)
        for t in ALLT:
            run = Run(tag, t)
            for a in run.ok:
                s, u = a["step"], a["ff"]
                now, prev = run.rows[u].get(s), run.rows[u].get(s - 1)
                if not ((now is not None and now.get("engaged")) or (now is None and prev is not None and prev.get("engaged"))):
                    continue
                pp = run.pos[u].get(s - 1)
                if now is None and pp is not None and bool(pp[2]):
                    continue
                cl = [w for w in run.work if w["ff"] == u and s - 10 < w["step"] <= s and w["action"] == "clear"]
                if not cl:
                    continue
                anc = tuple(cl[-1]["target"])
                st = run.state(s)
                R = {k: [c for c in manh(anc, k) if st["band"][c]] for k in (3, 5, 8, 16)}
                d0 = strict_dep(run, s, [])
                tots["san"] = max(tots["san"], int(d0.sum()))
                for k in (3, 5, 8, 16):
                    if R[k]:
                        tots["sdep%d" % k] += int((strict_dep(run, s, R[k]) & ~d0).sum())
                sh, wp = pressure_share(run, s, R[3], anc)
                allshares.extend(sh)
                tots["ign_m8"] += len(sh)
                tots["ign_m8_with_R3_parent"] += wp
                tots["pressure_from_R3"] += sum(sh)
                # other unit state at post-step s
                o = [x for x in ("ff_unit_0", "ff_unit_1") if x != u][0]
                p = run.pos[o].get(s)
                if p is None or p[4]:
                    os_ = "dead"
                elif p[0] is None:
                    os_ = "off-grid"
                elif p[2] or p[3]:
                    os_ = "on rescue"
                else:
                    lr = run.rows[o].get(s) or run.rows[o].get(s - 1)
                    ow = [w for w in run.work if w["ff"] == o and s - 10 < w["step"] <= s and w["action"] == "clear"]
                    os_ = ("working" if ow else "engaged") if (lr is not None and lr.get("engaged")) else "idle"
                ost[os_] += 1
                if tag == "fmEFS" and lab(t) in ("east/half/404", "east/half/101", "south/half/404") and s in (14, 16, 135):
                    P("  case %s s=%d %s victim %s row_at_s %s other=%s pos_u@s-1 %s pos_u@s %s vdead %s term %s" % (
                        lab(t), s, u, a["vid"], now is not None, os_, run.pos[u].get(s - 1), run.pos[u].get(s),
                        run.vdead.get(a["vid"]), run.term))
            del run
        P("  strict-continuation dep sums (distinct W):", dict(tots))
        P("  other unit at post-step s:", dict(ost))
        if allshares:
            P("  pressure share from R3 over later ignitions within manh 8: mean %.3f, cells with any R3 parent %d/%d" % (
                sum(allshares) / len(allshares), tots["ign_m8_with_R3_parent"], tots["ign_m8"]))
    # the OFF-dead victim east/half/404 victim_1 and the arm-only losses, in fmOFF and fmEFS
    for tag in ("fmOFF", "fmEFS", "fmDRY"):
        for t, vid in ((("east", "half", 404), "victim_1"), (("south", "half", 404), "victim_3"), (("east", "half", 101), "victim_0")):
            run = Run(tag, t)
            asg = [(a["step"], a["ff"], a["reason"]) for a in run.ok if a["vid"] == vid]
            una = [(a["step"], a["ff"], a["reason"]) for a in (run.d.get("unassigns") or []) if a["vid"] == vid]
            xs = [(x["step"], x["ff"]) for x in (run.d.get("exit_starts") or []) if x["victim"] == vid]
            sp = run.d.get("victim_spawns", {}).get(vid)
            pos16 = {u: run.pos[u].get(16, (None,))[0] for u in ("ff_unit_0", "ff_unit_1")}
            P("  %s %s %s: final %s dead@%s assigns %s unassigns %s contacts %s spawn %s ff pos@16 %s fbs(spawn) %s" % (
                tag, lab(t), vid, run.vfinal.get(vid), run.vdead.get(vid), asg[:6], una[:6], xs[:4], sp, pos16,
                run.fbs[tuple(sp)] if sp else None))
            del run


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--aclass":
        for tag in ("fmEFS",):
            acts, dists, ev_le20, first_work = collections.Counter(), [], 0, []
            for t in ALLT:
                run = Run(tag, t)
                fw = min((w["step"] for w in run.work), default=None)
                first_work.append(fw)
                for a in run.ok:
                    s, u = a["step"], a["ff"]
                    now, prev = run.rows[u].get(s), run.rows[u].get(s - 1)
                    if not ((now is not None and now.get("engaged")) or (now is None and prev is not None and prev.get("engaged"))):
                        continue
                    if any(w["ff"] == u and s - 10 < w["step"] <= s for w in run.work):
                        continue
                    lr = now if now is not None else prev
                    acts[lr["action"]] += 1
                    dists.append(lr["dist"])
                del run
            P("A-class latest actions", dict(acts), "fire dist median", med(dists), "min", min(dists), "max", max(dists))
            P("first work step per run (EFS):", sorted(x for x in first_work if x is not None))
    elif len(sys.argv) > 1 and sys.argv[1] == "--extra":
        extra()
    else:
        main()
