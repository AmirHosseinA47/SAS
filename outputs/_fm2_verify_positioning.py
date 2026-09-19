"""Adversarial verification of TASK A (positioning, fmDRY vs fmOFF). Read-only.
Independent re-derivation from raw harness JSON; does not import the analyst's script.
Reads only outputs/_ffr_fmOFF_*.json and outputs/_ffr_fmDRY_*.json for the 23 tuples by explicit path.
"""
import collections
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAN = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("east", "def", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
ALL = CAN + FRESH
U = ("ff_unit_0", "ff_unit_1")
MODE = sys.argv[1] if len(sys.argv) > 1 else "all"


def lab(t):
    return "%s/%s/%d" % t


def man(a, b):
    if a is None or b is None:
        return None
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def load(tag, t):
    p = os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], t[1], t[2]))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "n=0"
    return "n=%d mean %.2f median %.1f (+%d/-%d/0:%d) min %d max %d" % (
        len(xs), st.mean(xs), st.median(xs), sum(1 for x in xs if x > 0), sum(1 for x in xs if x < 0),
        sum(1 for x in xs if x == 0), min(xs), max(xs))


class R:
    def __init__(self, tag, t):
        d = load(tag, t)
        self.d = d
        self.t = t
        self.pos = {ff: {} for ff in U}
        self.stat = {ff: {} for ff in U}
        self.asg = {ff: {} for ff in U}
        self.dead = {ff: {} for ff in U}
        for i, row in enumerate(d["ff_steps"]):
            for ff, p, s_, a, ex, dd in row:
                self.pos[ff][i + 1] = tuple(p) if p is not None else None
                self.stat[ff][i + 1] = s_
                self.asg[ff][i + 1] = bool(a)
                self.dead[ff][i + 1] = bool(dd)
        self.vpos = collections.defaultdict(dict)
        self.vst = collections.defaultdict(dict)
        for i, row in enumerate(d["victim_steps"]):
            for v, p, s_ in row:
                self.vpos[v][i + 1] = tuple(p) if p is not None else None
                self.vst[v][i + 1] = s_
        self.vids = sorted(self.vst)
        self.final = {v: self.vst[v][len(d["victim_steps"])] for v in self.vids}
        self.death = {}
        for ff in U:
            ds = [k for k in sorted(self.dead[ff]) if self.dead[ff][k]]
            self.death[ff] = ds[0] if ds else None
        self.rows = {ff: {} for ff in U}
        for r in d.get("firefight_log") or []:
            self.rows[r["ff"]][r["step"]] = r
        self.ok = [a for a in d["assigns"] if a["ok"]]
        self.term = d.get("terminal_step")
        self._burn = None

    def burning(self, k):
        if self._burn is None:
            fr = [set() for _ in range(242)]
            for key, ivs in (self.d.get("burn_intervals") or {}).items():
                c = tuple(int(v) for v in key.split(","))
                for a, b in ivs:
                    for j in range(a, 241 if b is None else b):
                        fr[j].add(c)
            self._burn = fr
        return self._burn[k]

    def fdist(self, cell, k):
        B = self.burning(k)
        if cell is None or not B:
            return None
        return min(abs(cell[0] - x) + abs(cell[1] - y) for x, y in B)

    def engaged_at(self, ff, s):
        now, prev = self.rows[ff].get(s), self.rows[ff].get(s - 1)
        return bool((now is not None and now.get("engaged")) or (now is None and prev is not None and prev.get("engaged")))

    def streak_of(self, ff, s):
        rows = self.rows[ff]
        k = s if s in rows else (s - 1 if (s - 1) in rows else None)
        if k is None:
            return None
        a = k
        while (a - 1) in rows:
            a -= 1
        b = k
        while (b + 1) in rows:
            b += 1
        return (a, b, tuple(rows[a]["cell"]))

    def contact(self, ff, v, s):
        return next((e["step"] for e in self.d["exit_starts"] if e["ff"] == ff and e["victim"] == v and e["step"] >= s), None)

    def contact_any(self, v, s):
        return next((e["step"] for e in self.d["exit_starts"] if e["victim"] == v and e["step"] >= s), None)

    def completion(self, v):
        return next((c["step"] for c in self.d["completions"] if c["victim"] == v), None)

    def timeline(self):
        ev = collections.defaultdict(set)
        d = self.d
        for a in d["assigns"]:
            ev[a["step"]].add(("assign", a["ff"], a["vid"], a["reason"], a["ok"]))
        for a in d["unassigns"]:
            ev[a["step"]].add(("unassign", a["ff"], a["vid"], a["reason"]))
        for e in d["exit_starts"]:
            ev[e["step"]].add(("contact", e["ff"], e["victim"]))
        for c in d["completions"]:
            ev[c["step"]].add(("complete", c["ff"], c["victim"]))
        for e in d["absence_log"]:
            ev[e["step"]].add(("absence", e["event"], e["ff"]))
        for p in d["planner"]:
            ev[p["step"]].add(("planner", p["action"], p.get("vid"), p["reason"], p.get("ff"), p.get("n_available")))
        for v in self.vids:
            prev = None
            for k in range(1, 241):
                s_ = self.vst[v][k]
                if s_ != prev:
                    ev[k].add(("vstat", v, s_))
                prev = s_
        for ff in U:
            if self.death[ff]:
                ev[self.death[ff]].add(("ffdead", ff))
        return ev


def call_pos(r, a, conv):
    s, ff = a["step"], a["ff"]
    if conv == "pre":
        return r.pos[ff].get(s - 1) if s > 1 else None
    if conv == "post":
        return r.pos[ff].get(s)
    # rule: returned at s -> post; initial & idle after s-1 -> post; else pre
    ret = any(e["event"] == "returned" and e["ff"] == ff and e["step"] == s for e in r.d["absence_log"])
    if ret:
        return r.pos[ff].get(s)
    idle_prev = (s > 1 and r.stat[ff].get(s - 1) == "available" and not r.asg[ff].get(s - 1))
    if a["reason"] == "initial" and idle_prev:
        return r.pos[ff].get(s)
    return r.pos[ff].get(s - 1)


def vcall(r, a, conv):
    s = a["step"]
    if conv == "pre":
        return r.vpos[a["vid"]].get(s - 1)
    if conv == "post":
        return r.vpos[a["vid"]].get(s)
    ret = any(e["event"] == "returned" and e["ff"] == a["ff"] and e["step"] == s for e in r.d["absence_log"])
    idle_prev = (s > 1 and r.stat[a["ff"]].get(s - 1) == "available" and not r.asg[a["ff"]].get(s - 1))
    if ret or (a["reason"] == "initial" and idle_prev):
        return r.vpos[a["vid"]].get(s)
    return r.vpos[a["vid"]].get(s - 1)


def P(*a):
    print(*a)


RUNS = {t: (R("fmOFF", t), R("fmDRY", t)) for t in ALL}

# ------------------------------------------------------------------ S1 outcomes
P("=" * 90)
P("S1 OUTCOMES")
changed = []
tot = collections.Counter()
for t in ALL:
    o, d = RUNS[t]
    eo, ed = o.d["eval"], d.d["eval"]
    diffs = []
    for k in ("rescued", "dead", "firefighter_deaths"):
        if eo[k] != ed[k]:
            diffs.append("%s %+d" % (k, ed[k] - eo[k]))
    for v in o.vids:
        if o.final[v] != d.final[v]:
            diffs.append("%s %s->%s" % (v, o.final[v], d.final[v]))
    tot["rOFF"] += eo["rescued"]; tot["rDRY"] += ed["rescued"]
    if t[1] != "def":
        tot["dOFF"] += eo["rescued"]; tot["dDRY"] += ed["rescued"]
    fd = sum(1 for a, b in zip(o.d["fire_digests"], d.d["fire_digests"]) if a == b)
    sp = o.d["victim_spawns"] == d.d["victim_spawns"]
    deaths = "OFF %s DRY %s" % ({f: o.death[f] for f in U if o.death[f]}, {f: d.death[f] for f in U if d.death[f]})
    P("  %-15s OFF %d/%d/%d t%s  DRY %d/%d/%d t%s  fire_eq %d spawns %s | %s | %s" % (
        lab(t), eo["rescued"], eo["dead"], eo["firefighter_deaths"], o.term, ed["rescued"], ed["dead"],
        ed["firefighter_deaths"], d.term, fd, sp, "; ".join(diffs) or "-", deaths))
    if diffs:
        changed.append(t)
P("  totals rescued counted OFF %d DRY %d | dedup OFF %d DRY %d" % (tot["rOFF"], tot["rDRY"], tot["dOFF"], tot["dDRY"]))
P("  changed runs:", len(changed), [lab(t) for t in changed])
# death identity/timing changes on unchanged-count runs
for t in ALL:
    o, d = RUNS[t]
    if o.death != d.death:
        swap = set(f for f in U if o.death[f]) != set(f for f in U if d.death[f])
        P("  death change %-15s OFF %s DRY %s identity-swap %s count-same %s in-changed %s" % (
            lab(t), o.death, d.death, swap,
            o.d["eval"]["firefighter_deaths"] == d.d["eval"]["firefighter_deaths"], t in changed))

# ------------------------------------------------------------------ S2 engagement and first dispatch
P("=" * 90)
P("S2 STEP-1 ENGAGEMENT, FIRST DISPATCH")
eng1 = 0
firsts = []
for t in ALL:
    o, d = RUNS[t]
    for ff in U:
        r1 = d.rows[ff].get(1)
        eng1 += int(bool(r1 and r1.get("engaged")))
    a = min(d.ok, key=lambda x: x["step"])
    ao = min(o.ok, key=lambda x: x["step"])
    s = a["step"]
    berth = tuple(d.rows[a["ff"]][1]["cell"])
    other = [f for f in U if f != a["ff"]][0]
    for conv in ("post", "pre"):
        cp = call_pos(d, a, conv)
        op = d.pos[other][s] if conv == "post" else d.pos[other][s - 1]
        vp = d.vpos[a["vid"]][s] if conv == "post" else d.vpos[a["vid"]][s - 1]
        firsts.append((t, conv, s, ao["step"], man(cp, berth), man(cp, op), man(op, vp) - man(cp, vp),
                       a["ff"] == ao["ff"] and a["vid"] == ao["vid"]))
    # first confirmed victim frame
P("  units engaged on step-1 row: %d/46" % eng1)
for conv in ("post", "pre"):
    F = [x for x in firsts if x[1] == conv]
    P("  [%s] first DRY ok assign step: %s ; OFF: %s" % (conv, sorted(collections.Counter(x[2] for x in F).items()),
                                                         sorted(collections.Counter(x[3] for x in F).items())))
    P("  [%s] mean step %.2f; disp from berth %s" % (conv, st.mean(x[2] for x in F), stats([x[4] for x in F])))
    P("  [%s] inter-unit distance %s list %s" % (conv, stats([x[5] for x in F]), sorted(x[5] for x in F)))
    P("  [%s] other-minus-called distance to victim %s list %s" % (conv, stats([x[6] for x in F]), sorted(x[6] for x in F)))
    P("  [%s] first assign same (ff,vid) OFF vs DRY: %d/23" % (conv, sum(1 for x in F if x[7])))

# ------------------------------------------------------------------ S3 detection
P("=" * 90)
P("S3 DETECTION")
same_det = 0
first_conf = []
for t in ALL:
    o, d = RUNS[t]
    def det(r):
        return {v: next((k for k in range(1, 241) if r.vst[v][k] != "candidate"), None) for v in r.vids}
    def plan1(r):
        out = {}
        for p in r.d["planner"]:
            out.setdefault(p["vid"], p["step"])
        return out
    do, dd = det(o), det(d)
    same_det += int(do == dd)
    first_conf.append(min(x for x in do.values() if x is not None))
    if do != dd:
        P("  DETECTION DIFFERS", lab(t), do, dd)
    if plan1(o) != plan1(d):
        P("  first planner row differs", lab(t), plan1(o), plan1(d))
P("  first non-candidate status identical per victim: %d/23; earliest non-candidate frame per run: %s" % (
    same_det, sorted(first_conf)))
# what statuses appear before 14
sts = collections.Counter()
for t in ALL:
    o, d = RUNS[t]
    for v in o.vids:
        for k in range(1, 14):
            sts[o.vst[v][k]] += 1
P("  victim statuses in frames 1-13 (OFF):", dict(sts))

# ------------------------------------------------------------------ S4 divergences
P("=" * 90)
P("S4 FIRST DIVERGENCES (frame k = post step k)")
m4_viol = 0
order_ok = 0
for t in ALL:
    o, d = RUNS[t]
    def fdiv(a, b):
        return next((i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
    ffd = fdiv(o.d["ff_steps"], d.d["ff_steps"])
    vd = fdiv(o.d["victim_steps"], d.d["victim_steps"])
    ud = fdiv(o.d["uav_steps"], d.d["uav_steps"])
    uad = fdiv(o.d["uav_actions"], d.d["uav_actions"])
    flo = [(e["step"], e["victim_id"], e["from"], e["to"]) for e in o.d["victim_flee_log"]]
    fld = [(e["step"], e["victim_id"], e["from"], e["to"]) for e in d.d["victim_flee_log"]]
    fi = next((i for i, (x, y) in enumerate(zip(flo, fld)) if x != y), None)
    if fi is None and len(flo) != len(fld):
        fi = min(len(flo), len(fld))
    fl = None if fi is None else min([z[0] for z in (flo[fi:fi + 1] + fld[fi:fi + 1])])
    to, td = o.timeline(), d.timeline()
    tdiv = next((k for k in range(0, 242) if to.get(k, set()) != td.get(k, set())), None)
    tdelta = (sorted(to.get(tdiv, set()) - td.get(tdiv, set()), key=str), sorted(td.get(tdiv, set()) - to.get(tdiv, set()), key=str)) if tdiv else None
    # per-victim: position divergence vs that victim's own timeline divergence
    viol = []
    for v in o.vids:
        pd = next((k for k in range(1, 241) if o.vpos[v][k] != d.vpos[v][k]), None)
        if pd is None:
            continue
        def vev(tl):
            return {k: set(e for e in s_ if v in e) for k, s_ in tl.items()}
        vo, vdd = vev(to), vev(td)
        vt = next((k for k in range(0, 241) if vo.get(k, set()) != vdd.get(k, set())), None)
        if vt is None or pd < vt:
            viol.append((v, pd, vt))
    m4_viol += len(viol)
    ok = (vd is None or tdiv is None or vd >= tdiv) and (ud is None or (tdiv is not None and ud > tdiv))
    order_ok += int(ok)
    if fl is not None and tdiv is not None and fl < tdiv:
        P("  FLEE LOG DIVERGES BEFORE TIMELINE", lab(t), fl, tdiv)
    P("  %-15s ff %s | victim %s | flee %s | uav %s act %s | timeline %s %s | pos-before-own-event %s" % (
        lab(t), ffd, vd, fl, ud, uad, tdiv, tdelta, viol))
P("  runs where victim div >= timeline div and uav div > timeline div: %d/23; victim pos-before-event violations %d" % (order_ok, m4_viol))

# ------------------------------------------------------------------ S5 per victim first ok assign
P("=" * 90)
P("S5 PER-VICTIM FIRST OK ASSIGN, DRY - OFF")
for conv in ("rule", "pre", "post"):
    sd, dd_, cd, cda, first_d, later_d, first_c, later_c = [], [], [], [], [], [], [], []
    dd20, cd20 = [], []
    flips = collections.Counter()
    n = 0
    for t in ALL:
        o, d = RUNS[t]
        firstff = {}
        for arm, r in (("o", o), ("d", d)):
            for ff in U:
                firstff[(arm, ff)] = min((a["step"] for a in r.ok if a["ff"] == ff), default=None)
        for v in o.vids:
            if o.final[v] != d.final[v]:
                flips[(o.final[v], d.final[v])] += 1
            ao = next((a for a in sorted(o.ok, key=lambda x: x["step"]) if a["vid"] == v), None)
            ad = next((a for a in sorted(d.ok, key=lambda x: x["step"]) if a["vid"] == v), None)
            if ao is None or ad is None:
                continue
            n += 1
            sd.append(ad["step"] - ao["step"])
            xd, xo = man(call_pos(d, ad, conv), vcall(d, ad, conv)), man(call_pos(o, ao, conv), vcall(o, ao, conv))
            x = (xd - xo) if (xd is not None and xo is not None) else None
            dd_.append(x)
            co, cdr = o.contact(ao["ff"], v, ao["step"]), d.contact(ad["ff"], v, ad["step"])
            c = (cdr - ad["step"]) - (co - ao["step"]) if (co is not None and cdr is not None) else None
            cd.append(c)
            coa, cdra = o.contact_any(v, ao["step"]), d.contact_any(v, ad["step"])
            cda.append((cdra - ad["step"]) - (coa - ao["step"]) if (coa is not None and cdra is not None) else None)
            isfirst = firstff[("o", ao["ff"])] == ao["step"] and firstff[("d", ad["ff"])] == ad["step"]
            (first_d if isfirst else later_d).append(x)
            (first_c if isfirst else later_c).append(c)
            if t[1] != "def":
                dd20.append(x); cd20.append(c)
    P("  [%s] n=%d step %s" % (conv, n, stats(sd)))
    P("  [%s] distance %s" % (conv, stats(dd_)))
    P("  [%s] contact(same ff) %s" % (conv, stats(cd)))
    P("  [%s] contact(any ff)  %s" % (conv, stats(cda)))
    P("  [%s] dedup20 distance %s contact %s" % (conv, stats(dd20), stats(cd20)))
    P("  [%s] first-dispatch(both arms) distance %s contact %s" % (conv, stats(first_d), stats(first_c)))
    P("  [%s] later distance %s contact %s" % (conv, stats(later_d), stats(later_c)))
P("  flips:", dict(flips))

# completions shift
cs = []
for t in ALL:
    o, d = RUNS[t]
    for v in o.vids:
        a, b = o.completion(v), d.completion(v)
        if a is not None and b is not None:
            cs.append(b - a)
P("  completion shift (victims completed in both) %s" % stats(cs))

# ------------------------------------------------------------------ S6 chooser convention check
P("=" * 90)
P("S6 CHOOSER CONVENTION CHECK (planner assigns with n_available==2)")
for conv in ("rule", "pre", "post"):
    agree = tot2 = 0
    bad = []
    for t in ALL:
        for arm, r in zip(("OFF", "DRY"), RUNS[t]):
            for p in r.d["planner"]:
                if p["action"] != "assign" or p.get("n_available") != 2:
                    continue
                a = next((x for x in r.ok if x["step"] == p["step"] and x["ff"] == p["ff"] and x["vid"] == p["vid"]), None)
                if a is None:
                    continue
                vp = vcall(r, a, conv)
                ds = []
                for ff in U:
                    fake = dict(a); fake["ff"] = ff
                    ds.append((man(call_pos(r, fake, conv), vp), ff))
                if any(x[0] is None for x in ds):
                    continue
                tot2 += 1
                ch = min(ds)[1]
                if ch == a["ff"]:
                    agree += 1
                else:
                    bad.append((arm, lab(t), a["step"], a["ff"], a["vid"], ds))
    P("  [%s] nearest-rule agrees %d/%d; disagreements %s" % (conv, agree, tot2, bad[:6]))

# ------------------------------------------------------------------ S7 preemption and displacement
P("=" * 90)
P("S7 PREEMPTION / DISPLACEMENT")
for conv in ("rule", "pre", "post"):
    n = e = 0
    disp, disp_first, disp_later = [], [], []
    alld = {"OFF": [], "DRY": []}
    for t in ALL:
        o, d = RUNS[t]
        for arm, r in (("OFF", o), ("DRY", d)):
            for a in r.ok:
                alld[arm].append(man(call_pos(r, a, conv), vcall(r, a, conv)))
        for a in d.ok:
            n += 1
            e += int(d.engaged_at(a["ff"], a["step"]))
            sk = d.streak_of(a["ff"], a["step"])
            if sk is not None:
                x = man(call_pos(d, a, conv), sk[2])
                disp.append(x)
                (disp_first if sk[0] == 1 else disp_later).append(x)
    P("  [%s] DRY ok assigns %d engaged %d (%.1f%%); disp in streak %s; first %s; later %s" % (
        conv, n, e, 100.0 * e / n, stats(disp), stats(disp_first), stats(disp_later)))
    P("  [%s] all ok assign distance OFF %s | DRY %s" % (conv, stats(alld["OFF"]), stats(alld["DRY"])))

# engaged later calls: matched OFF assign by (victim, ordinal)
P("  ENGAGED DRY calls matched to OFF by (victim, ordinal) [rule]:")
for grp in ("first", "later"):
    dl, cl, rows = [], [], []
    for t in ALL:
        o, d = RUNS[t]
        for a in d.ok:
            if not d.engaged_at(a["ff"], a["step"]):
                continue
            sk = d.streak_of(a["ff"], a["step"])
            isfirst = sk is not None and sk[0] == 1
            if (grp == "first") != isfirst:
                continue
            ordd = [x for x in sorted(d.ok, key=lambda y: y["step"]) if x["vid"] == a["vid"]].index(a)
            oo = [x for x in sorted(o.ok, key=lambda y: y["step"]) if x["vid"] == a["vid"]]
            if ordd >= len(oo):
                rows.append((lab(t), a["step"], a["vid"], "no OFF match"))
                continue
            b = oo[ordd]
            x = man(call_pos(d, a, "rule"), vcall(d, a, "rule")) - man(call_pos(o, b, "rule"), vcall(o, b, "rule"))
            cdr, co = d.contact(a["ff"], a["vid"], a["step"]), o.contact(b["ff"], b["vid"], b["step"])
            c = (cdr - a["step"]) - (co - b["step"]) if cdr is not None and co is not None else None
            dl.append(x); cl.append(c)
            if grp == "later":
                rows.append((lab(t), a["vid"], "DRY s%d %s disp %s d=%d contact %s" % (
                    a["step"], a["ff"], man(call_pos(d, a, "rule"), sk[2]) if sk else None,
                    man(call_pos(d, a, "rule"), vcall(d, a, "rule")), None if cdr is None else cdr - a["step"]),
                    "OFF s%d %s d=%d contact %s" % (b["step"], b["ff"], man(call_pos(o, b, "rule"), vcall(o, b, "rule")),
                                                    None if co is None else co - b["step"]), "final %s->%s" % (o.final[a["vid"]], d.final[a["vid"]])))
    P("    %s: distance delta %s ; contact delta %s" % (grp, stats(dl), stats(cl)))
    for rw in rows:
        P("      ", rw)

if MODE == "all":
    # ------------------------------------------------------------------ S8 per-run facts
    P("=" * 90)
    P("S8 PER-RUN FACTS")

    def show_assigns(t):
        o, d = RUNS[t]
        for arm, r in (("OFF", o), ("DRY", d)):
            for a in sorted(r.ok, key=lambda x: x["step"]):
                cp = call_pos(r, a, "rule"); vp = vcall(r, a, "rule")
                other = [f for f in U if f != a["ff"]][0]
                s = a["step"]
                sk = r.streak_of(a["ff"], s) if arm == "DRY" else None
                P("    %s s%-3d %s->%s %-26s at %s pre %s post %s v %s d=%s eng %s streak %s | other %s pre %s post %s st %s asg %s d=%s | contact %s complete %s" % (
                    arm, s, a["ff"], a["vid"], a["reason"], cp, r.pos[a["ff"]].get(s - 1), r.pos[a["ff"]].get(s), vp, man(cp, vp),
                    r.engaged_at(a["ff"], s) if arm == "DRY" else "-", sk, other, r.pos[other].get(s - 1), r.pos[other].get(s),
                    r.stat[other].get(s), r.asg[other].get(s), man(r.pos[other].get(s), vp),
                    r.contact(a["ff"], a["vid"], s), r.completion(a["vid"])))
            P("    %s unassigns %s" % (arm, [(u["step"], u["ff"], u["vid"], u["reason"]) for u in r.d["unassigns"]]))
            P("    %s planner non-assign %s" % (arm, [(p["step"], p["action"], p["vid"], p["reason"], p.get("n_available")) for p in r.d["planner"] if p["action"] != "assign"]))
            P("    %s exit_starts %s" % (arm, [(e["step"], e["ff"], e["victim"], e["ff_pos"]) for e in r.d["exit_starts"]]))
            P("    %s completions %s" % (arm, [(c["step"], c["ff"], c["victim"], c["pos"]) for c in r.d["completions"]]))
            P("    %s returns %s" % (arm, [(e["step"], e["ff"], e.get("cell")) for e in r.d["absence_log"] if e["event"] == "returned"]))
            P("    %s deaths %s at %s ; term %s ; final %s" % (arm, r.death, {f: r.pos[f].get(r.death[f]) if r.death[f] else None for f in U}, r.term, r.final))

    for t in [("east", "half", 101), ("east", "half", 404), ("south", "half", 202), ("south", "half", 404),
              ("east", "def", 101), ("east", "def", 303), ("east", "half", 606), ("south", "half", 808),
              ("south", "half", 909)]:
        P("  ---- %s" % lab(t))
        show_assigns(t)

    def path(r, ff, a, b, stepby=1):
        return " ".join("%d%s" % (k, r.pos[ff].get(k)) for k in range(a, b + 1, stepby))

    def expo(r, ff, a, b):
        fds = [r.fdist(r.pos[ff].get(k), k) for k in range(a, b + 1)]
        fds2 = [x for x in fds if x is not None]
        return "frames %d min_fd %s frames<=1 %d" % (len(fds2), min(fds2) if fds2 else None, sum(1 for x in fds2 if x <= 1))

    o, d = RUNS[("east", "half", 101)]
    P("  eh101 DRY ff_unit_0 77-138:", expo(d, "ff_unit_0", 77, 138))
    P("  eh101 DRY path 96-140:", path(d, "ff_unit_0", 96, 140, 4))
    P("  eh101 OFF ff_unit_0 90-127:", expo(o, "ff_unit_0", 90, 127))
    P("  eh101 OFF ff_unit_0 frames 190-196:", [(k, o.pos["ff_unit_0"][k], o.stat["ff_unit_0"][k], o.asg["ff_unit_0"][k], o.dead["ff_unit_0"][k]) for k in range(188, 197)])
    P("  eh101 victim_0 DRY vst 130-138:", [(k, d.vpos["victim_0"][k], d.vst["victim_0"][k]) for k in range(130, 139)])
    o, d = RUNS[("east", "half", 404)]
    P("  eh404 OFF ff_unit_0 frames 236-240:", [(k, o.pos["ff_unit_0"][k], o.stat["ff_unit_0"][k], o.dead["ff_unit_0"][k]) for k in range(236, 241)])
    o, d = RUNS[("south", "half", 909)]
    P("  s909 DRY ff_unit_0 14-36:", path(d, "ff_unit_0", 14, 36, 2), expo(d, "ff_unit_0", 14, 36))
    P("  s909 OFF ff_unit_0 14-60:", path(o, "ff_unit_0", 14, 60, 3), expo(o, "ff_unit_0", 14, 203))
    o, d = RUNS[("south", "half", 808)]
    P("  s808 DRY ff_unit_0 14-51:", path(d, "ff_unit_0", 14, 51, 3), expo(d, "ff_unit_0", 14, 51))
    P("  s808 OFF ff_unit_0 14-60:", path(o, "ff_unit_0", 14, 60, 3))
    o, d = RUNS[("east", "half", 606)]
    P("  eh606 DRY ff_unit_0 139-240:", path(d, "ff_unit_0", 139, 240, 6), expo(d, "ff_unit_0", 139, 240))
    P("  eh606 DRY streak at 139:", d.streak_of("ff_unit_0", 139), "OFF ff_unit_0 death", o.death, "OFF victim_0 final frames", [(k, o.vst["victim_0"][k]) for k in (206, 207)])
    o, d = RUNS[("east", "def", 101)]
    P("  def101 DRY ff_unit_1 117-240:", path(d, "ff_unit_1", 117, 240, 6), expo(d, "ff_unit_1", 117, 240))
    P("  def101 DRY ff_unit_1 row s86:", d.rows["ff_unit_1"].get(86), "streak", d.streak_of("ff_unit_1", 86))
    P("  def101 DRY ff_unit_0 streak at 86:", d.streak_of("ff_unit_0", 86), "ff_unit_1 streak at 117", d.streak_of("ff_unit_1", 117))
    P("  def101 victim_3 DRY pos 230-240:", [(k, d.vpos["victim_3"][k], d.vst["victim_3"][k]) for k in (200, 220, 237, 240)])
    rb = sum(1 for k in range(117, 241) if d.stat["ff_unit_1"][k] == "route_blocked")
    P("  def101 DRY ff_unit_1 route_blocked frames 117-240:", rb)

    # counterfactual first-window distances for 909 / 808 under U0 / U1
    for t in [("south", "half", 909), ("south", "half", 808), ("south", "half", 404)]:
        o, d = RUNS[t]
        s = 14
        vp = d.vpos["victim_3"][s]
        P("  %s s14 victim_3 %s | DRY u0 %s d=%d u1 %s d=%d | OFF u0 %s d=%d u1 %s d=%d" % (
            lab(t), vp, d.pos["ff_unit_0"][s], man(d.pos["ff_unit_0"][s], vp), d.pos["ff_unit_1"][s], man(d.pos["ff_unit_1"][s], vp),
            o.pos["ff_unit_0"][s], man(o.pos["ff_unit_0"][s], vp), o.pos["ff_unit_1"][s], man(o.pos["ff_unit_1"][s], vp)))

# ------------------------------------------------------------------ S9 episode outcomes
P("=" * 90)
P("S9 EPISODE OUTCOMES of ok assigns (first of: contact, rb-unassign(step>s), unit death, next assign of unit, victim terminal)")


def episode(r, a):
    s, ff, v = a["step"], a["ff"], a["vid"]
    cands = []
    c = r.contact(ff, v, s)
    if c is not None:
        cands.append((c, 0, "contact"))
    u = next((x["step"] for x in r.d["unassigns"] if x["ff"] == ff and x["vid"] == v and x["step"] > s), None)
    if u is not None:
        cands.append((u, 1, "unassign"))
    if r.death[ff] is not None and r.death[ff] >= s:
        cands.append((r.death[ff], 2, "unit_death"))
    n = next((x["step"] for x in sorted(r.ok, key=lambda y: y["step"]) if x["ff"] == ff and x["step"] > s), None)
    if n is not None:
        cands.append((n, 3, "next_assign"))
    vt = next((k for k in range(s, 241) if r.vst[v][k] in ("rescued", "dead")), None)
    if vt is not None:
        cands.append((vt, 4, "victim_" + r.vst[v][vt]))
    if not cands:
        return (240, "horizon")
    m = min(cands)
    return (m[0], m[2])


for label_, pick in (("each unit's first ok assign", "first"), ("all ok assigns", "all")):
    for arm_i, arm in enumerate(("OFF", "DRY")):
        cnt = collections.Counter()
        cnt_eng = collections.Counter()
        for t in ALL:
            r = RUNS[t][arm_i]
            firsts_ = {ff: min((a["step"] for a in r.ok if a["ff"] == ff), default=None) for ff in U}
            for a in r.ok:
                if pick == "first" and firsts_[a["ff"]] != a["step"]:
                    continue
                e = episode(r, a)[1]
                cnt[e] += 1
                if arm == "DRY" and r.engaged_at(a["ff"], a["step"]):
                    cnt_eng[e] += 1
        P("  %-28s %s %s%s" % (label_, arm, dict(cnt), ("   engaged-at-call subset %s" % dict(cnt_eng)) if arm == "DRY" else ""))

# unit deaths inside an episode (died before contact on that assign)
P("  unit died inside an episode (by arm):")
for arm_i, arm in enumerate(("OFF", "DRY")):
    rows = []
    for t in ALL:
        r = RUNS[t][arm_i]
        for a in r.ok:
            e = episode(r, a)
            if e[1] == "unit_death":
                sk = r.streak_of(a["ff"], a["step"]) if arm == "DRY" else None
                rows.append((lab(t), a["step"], a["ff"], a["vid"], "died", e[0],
                             "engaged" if (arm == "DRY" and r.engaged_at(a["ff"], a["step"])) else "-",
                             "disp %s" % (man(call_pos(r, a, "rule"), sk[2]) if sk else None)))
    P("   ", arm, len(rows), rows)

# censoring on per-victim first assign contact
P("  per-victim first ok assign: contact in OFF only / DRY only:")
oo = do_ = 0
for t in ALL:
    o, d = RUNS[t]
    for v in o.vids:
        ao = next((a for a in sorted(o.ok, key=lambda x: x["step"]) if a["vid"] == v), None)
        ad = next((a for a in sorted(d.ok, key=lambda x: x["step"]) if a["vid"] == v), None)
        if ao is None or ad is None:
            continue
        co, cd_ = o.contact(ao["ff"], v, ao["step"]), d.contact(ad["ff"], v, ad["step"])
        if co is not None and cd_ is None:
            oo += 1
            P("    OFF-only", lab(t), v, "OFF +%d" % (co - ao["step"]), "final %s->%s" % (o.final[v], d.final[v]))
        if cd_ is not None and co is None:
            do_ += 1
            P("    DRY-only", lab(t), v, "DRY +%d" % (cd_ - ad["step"]), "final %s->%s" % (o.final[v], d.final[v]))
P("  OFF-only %d DRY-only %d" % (oo, do_))

# ------------------------------------------------------------------ S10 co-location
P("=" * 90)
P("S10 CO-LOCATION of the two units (same cell, both on grid, both alive)")
for arm_i, arm in enumerate(("OFF", "DRY")):
    tot_frames = 0
    idle_both = 0
    runs_ = 0
    for t in ALL:
        r = RUNS[t][arm_i]
        n = sum(1 for k in range(1, 241) if r.pos["ff_unit_0"][k] is not None and r.pos["ff_unit_0"][k] == r.pos["ff_unit_1"][k]
                and not r.dead["ff_unit_0"][k] and not r.dead["ff_unit_1"][k])
        m = sum(1 for k in range(1, 241) if r.pos["ff_unit_0"][k] is not None and r.pos["ff_unit_0"][k] == r.pos["ff_unit_1"][k]
                and k in r.rows["ff_unit_0"] and k in r.rows["ff_unit_1"])
        tot_frames += n
        idle_both += m
        runs_ += int(n > 0)
    P("  %s co-located frames %d on %d runs; with both units having a feature-log row that step %d" % (arm, tot_frames, runs_, idle_both))

# ------------------------------------------------------------------ S11 victim positions at call 14 in 909 / unit fire exposure
P("=" * 90)
P("S11 909 / 808 approach: fire distance along each arm's first-call path, and where OFF's unit was when DRY's died")
for t, dstep in ((("south", "half", 909), 36), (("south", "half", 808), 51), (("south", "half", 404), 72)):
    o, d = RUNS[t]
    fu = [f for f in U if d.death[f] == dstep][0]
    P("  %s DRY %s death s%d at %s; burning at that cell at s%d: %s; OFF same unit at s%d: %s fd %s" % (
        lab(t), fu, dstep, d.pos[fu][dstep], dstep, d.pos[fu][dstep] in d.burning(dstep), dstep, o.pos[fu][dstep],
        o.fdist(o.pos[fu][dstep], dstep)))
    first_o = min(a["step"] for a in o.ok if a["vid"] == "victim_3")
    ao = [a for a in o.ok if a["vid"] == "victim_3"][0]
    ad = [a for a in d.ok if a["vid"] == "victim_3"][0]
    P("    OFF first victim_3 call %s %s ; DRY %s %s" % (ao["step"], ao["ff"], ad["step"], ad["ff"]))
    P("    OFF %s fd per 2 steps 14-70: %s" % (ao["ff"], [(k, o.pos[ao["ff"]][k], o.fdist(o.pos[ao["ff"]][k], k)) for k in range(14, 71, 4)]))
    P("    DRY %s fd per 2 steps 14-%d: %s" % (ad["ff"], dstep, [(k, d.pos[ad["ff"]][k], d.fdist(d.pos[ad["ff"]][k], k)) for k in range(14, dstep + 1, 4)]))
    P("    OFF %s status frames 14-120 counts: %s" % (ao["ff"], dict(collections.Counter(o.stat[ao["ff"]][k] for k in range(14, 121)))))

# preemption count in OFF (sanity: must be 0 - no rows)
P("  OFF firefight_log rows total: %d" % sum(len(RUNS[t][0].d.get("firefight_log") or []) for t in ALL))

P("=" * 90)
P("S12 first-dispatch episodes ending in route_blocked unassign, per arm; and rb frames/exposure on every first-dispatch episode")
for arm_i, arm in enumerate(("OFF", "DRY")):
    rows = []
    for t in ALL:
        r = RUNS[t][arm_i]
        for ff in U:
            a = min((x for x in r.ok if x["ff"] == ff), key=lambda x: x["step"], default=None)
            if a is None:
                continue
            e = episode(r, a)
            if e[1] == "unassign":
                rows.append((lab(t), a["step"], ff, a["vid"], "unassign s%d" % e[0], "death %s" % r.death[ff]))
    P("  ", arm, len(rows))
    for x in rows:
        P("     ", x)
# exposure on first-dispatch episodes: frames at fire distance <= 1 from call to contact/unassign, both arms, same (victim) pairing
P("  first-dispatch victim_3-type long trips: frames at fd<=1 until episode end, OFF vs DRY (same victim)")
for t in ALL:
    o, d = RUNS[t]
    out = []
    for arm, r in (("OFF", o), ("DRY", d)):
        for ff in U:
            a = min((x for x in r.ok if x["ff"] == ff), key=lambda x: x["step"], default=None)
            if a is None:
                continue
            e = episode(r, a)
            fds = [r.fdist(r.pos[ff].get(k), k) for k in range(a["step"], min(e[0], 240) + 1)]
            fds = [x for x in fds if x is not None]
            out.append("%s %s->%s s%d end %s@%d adj%d" % (arm, ff[-1], a["vid"][-1], a["step"], e[1], e[0], sum(1 for x in fds if x <= 1)))
    P("   %-15s %s" % (lab(t), " | ".join(out)))

P("=" * 90)
P("S13 small checks")
nones = [lab(t) for t in ALL if next((i for i, (x, y) in enumerate(zip(RUNS[t][0].d["uav_steps"], RUNS[t][1].d["uav_steps"])) if x != y), None) is None]
P("  uav_steps never diverge on %d runs: %s" % (len(nones), nones))
o, d = RUNS[("east", "half", 404)]
P("  eh404 OFF victim_1 first dead frame:", next((k for k in range(1, 241) if o.vst["victim_1"][k] == "dead"), None))
o, d = RUNS[("east", "def", 303)]
P("  def303 DRY ff_unit_1 route_blocked frames 63-141:", sum(1 for k in range(63, 142) if d.stat["ff_unit_1"][k] == "route_blocked"))
# first-dispatch pairing by OFF unit's first assign victim -> DRY first assign of that victim
dd46, cc46 = [], []
for t in ALL:
    o, d = RUNS[t]
    for ff in U:
        ao = min((x for x in o.ok if x["ff"] == ff), key=lambda x: x["step"])
        ad = min((x for x in d.ok if x["vid"] == ao["vid"]), key=lambda x: x["step"], default=None)
        if ad is None:
            continue
        dd46.append(man(call_pos(d, ad, "rule"), vcall(d, ad, "rule")) - man(call_pos(o, ao, "rule"), vcall(o, ao, "rule")))
        co, cd_ = o.contact(ao["ff"], ao["vid"], ao["step"]), d.contact(ad["ff"], ad["vid"], ad["step"])
        if co is not None and cd_ is not None:
            cc46.append(cd_ - co)
P("  first dispatch (OFF unit's first assign victim, DRY first assign of that victim): distance %s ; contact STEP delta %s" % (stats(dd46), stats(cc46)))
# victim status frames: 'confirmed' only appears after an unassign?
conf_first = collections.Counter()
for t in ALL:
    for r in RUNS[t]:
        for v in r.vids:
            seq = [r.vst[v][k] for k in range(1, 241)]
            if "confirmed" in seq:
                i = seq.index("confirmed")
                conf_first["preceded by assigned" if "assigned" in seq[:i] else "not preceded by assigned"] += 1
P("  victim_steps 'confirmed' first appearance:", dict(conf_first))
