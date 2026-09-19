"""Adversarial verification of the south/half/404 diagnosis (TASK B). Read-only.

Independent code; does not import or run outputs/_fm2_diag_south404.py.
usage: .venv/Scripts/python.exe outputs/_fm2_verify_south404.py [json|replay|all]
Reads only explicit paths:
  outputs/_ffr_{fmOFF,fmREF,fmDRY,fmEFS,fmF,fmFS}_south_half_404.json
  outputs/_rblatch_camp2_{fmgOFF,fmgEFS,fmgFB}s_D_south.json
Prints to stdout; writes nothing.
"""
import hashlib
import json
import os
import random
import sys
from array import array

import numpy

HERE = os.path.dirname(os.path.abspath(__file__))
N = 50
T = 240
SEED = 404


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


ARMS = ["fmOFF", "fmREF", "fmDRY", "fmEFS", "fmF", "fmFS"]
R = {a: load("_ffr_%s_south_half_404.json" % a) for a in ARMS}
EFS, DRY, OFF = R["fmEFS"], R["fmDRY"], R["fmOFF"]


def key2c(k):
    x, y = k.split(",")
    return (int(x), int(y))


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def manh(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def burning_by_step(d):
    """B[t] = set of cells burning in post-step observation of step t (1..240)."""
    B = [set() for _ in range(T + 1)]
    for k, ivs in d["burn_intervals"].items():
        c = key2c(k)
        for s, e in ivs:
            for t in range(s, (T + 1) if e is None else e):
                B[t].add(c)
    return B


def writes(d):
    out = []
    for r in d.get("firefight_log") or []:
        if r.get("wrote"):
            out.append((r["step"], r["ff"], tuple(r["cell"]), tuple(r["target"]), r["action"], r.get("scorched")))
    return out


def rows_by_entity(d, key):
    out = {}
    for i, row in enumerate(d[key]):
        for r in row:
            out.setdefault(r[0], {})[i + 1] = r
    return out


def segs(series):
    out = []
    for t in sorted(series):
        v = series[t]
        if out and out[-1][2] == v:
            out[-1][1] = t
        else:
            out.append([t, t, v])
    return out


# =========================================================================== JSON
def json_checks():
    print("=" * 90)
    print("A. OUTCOMES AND IDENTITIES")
    for a in ARMS:
        ev = R[a]["eval"]
        print("  %-6s rescued %s dead %s ffd %s burnt %s terminal %s never_detected %s" % (
            a, ev["rescued"], ev["dead"], ev["firefighter_deaths"], ev["burnt_cells"], R[a]["terminal_step"],
            ev["never_detected"]))
    excl = {"tag", "repo", "wall_s", "params", "extra_params"}

    def dk(a, b):
        ks = (set(R[a]) | set(R[b])) - excl
        return sorted(k for k in ks if R[a].get(k, "<abs>") != R[b].get(k, "<abs>"))

    for a, b in (("fmEFS", "fmFS"), ("fmEFS", "fmF"), ("fmOFF", "fmREF"), ("fmEFS", "fmDRY")):
        print("  diff keys %s vs %s: %s" % (a, b, dk(a, b)))
    for other in ("fmF", "fmFS", "fmDRY"):
        la, lb = EFS["firefight_log"], R[other]["firefight_log"]
        fields = set()
        for ra, rb in zip(la, lb):
            for k in set(ra) | set(rb):
                if ra.get(k) != rb.get(k):
                    fields.add(k)
        print("  firefight_log fmEFS vs %s: rows %d/%d, differing fields %s" % (other, len(la), len(lb), sorted(fields)))
    print("  params fmF:", R["fmF"]["extra_params"], " fmFS:", R["fmFS"]["extra_params"], " fmEFS:", EFS["extra_params"],
          " fmDRY:", DRY["extra_params"])
    dry_rows_pre9 = [(r["step"], r["ff"], r["dry"]) for r in DRY["firefight_log"] if r["step"] < 9]
    efs_rows_pre9 = [(r["step"], r["ff"], r["dry"]) for r in EFS["firefight_log"] if r["step"] < 9]
    print("  firefight_log rows with step<9: fmDRY %d (dry values %s), fmEFS %d (dry values %s)" % (
        len(dry_rows_pre9), sorted({x[2] for x in dry_rows_pre9}), len(efs_rows_pre9), sorted({x[2] for x in efs_rows_pre9})))

    print("=" * 90)
    print("B. WRITES AND FIRE")
    W = writes(EFS)
    for w in W:
        print("  write step %d %s unit_cell %s target %s %s scorched=%s" % w)
    print("  n writes %d, actions %s, counters %s" % (len(W), sorted({w[4] for w in W}), EFS["firefight_counters"]))
    print("  fmF writes == fmEFS writes (step, ff, target):", [(w[0], w[1], w[3]) for w in writes(R["fmF"])] == [(w[0], w[1], w[3]) for w in W])
    print("  fmDRY shadow:", sorted(tuple(c) for c in (DRY.get("firefight_shadow") or [])))
    print("  fmDRY shadow == EFS targets:", sorted(tuple(c) for c in (DRY.get("firefight_shadow") or [])) == sorted(w[3] for w in W))
    print("  fmDRY rows wrote any:", any(r.get("wrote") for r in DRY["firefight_log"]),
          " fmDRY last ff row step", max(r["step"] for r in DRY["firefight_log"]),
          " fmEFS last ff row step", max(r["step"] for r in EFS["firefight_log"]))

    def first_div(a, b):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return i + 1
        return None

    print("  first digest divergence EFS vs DRY:", first_div(EFS["fire_digests"], DRY["fire_digests"]),
          " EFS vs OFF:", first_div(EFS["fire_digests"], OFF["fire_digests"]),
          " DRY vs OFF:", first_div(DRY["fire_digests"], OFF["fire_digests"]),
          " F vs EFS:", first_div(R["fmF"]["fire_digests"], EFS["fire_digests"]),
          " FS vs EFS:", first_div(R["fmFS"]["fire_digests"], EFS["fire_digests"]))
    BD, BE, BO = burning_by_step(DRY), burning_by_step(EFS), burning_by_step(OFF)
    fdb = next((t for t in range(1, T + 1) if BD[t] != BE[t]), None)
    print("  first burning-set divergence EFS vs DRY (burn_intervals):", fdb,
          " DRY vs OFF:", next((t for t in range(1, T + 1) if BD[t] != BO[t]), None))
    # interval bounds on multiples of 3
    offm = 0
    for d in (DRY, EFS):
        for k, ivs in d["burn_intervals"].items():
            for s, e in ivs:
                if s % 3 and not (s == 1):
                    offm += 1
                if e is not None and e % 3:
                    offm += 1
    print("  interval bounds off multiples of 3 (start=1 excepted):", offm,
          " cells with a [1,x) interval:", [k for k, ivs in EFS["burn_intervals"].items() if ivs[0][0] == 1])
    wcells = [w[3] for w in W]
    print("  D(t) table, ticks 63..90 and selected:")
    Dsets = {}
    for t in list(range(63, 91, 3)) + [105, 120, 150, 180, 210, 240]:
        Dd = BD[t] - BE[t]
        De = BE[t] - BD[t]
        Dall = Dd | De
        Dsets[t] = Dall
        mc = max((min(cheb(c, w) for w in wcells) for c in Dall), default=None)
        print("   tick %3d |D| %3d DRY-only %3d EFS-only %3d max cheb to nearest write %s  %s" % (
            t, len(Dall), len(Dd), len(De), mc,
            " ".join("(%d,%d)%s" % (c[0], c[1], "D" if c in Dd else "E") for c in sorted(Dall))[:120] if len(Dall) <= 8 else ""))
    empty_before = all(BD[t] == BE[t] for t in range(1, 69))
    print("  D empty on every step before 69:", empty_before)
    for c in ((8, 35), (8, 37), (7, 37), (7, 40), (8, 40)):
        k = "%d,%d" % c
        print("   %s DRY %s | EFS %s" % (k, DRY["burn_intervals"].get(k), EFS["burn_intervals"].get(k)))

    # --- conservative recorded-data cone: H(t) = writes U all earlier D cells; a D(t) cell farther than
    #     Chebyshev 3 from every H(t) cell has NO possible physical cause.
    H = set(wcells)
    print("  conservative physical-cause test (recorded data only):")
    for t in range(69, 91, 3):
        Dall = (BD[t] - BE[t]) | (BE[t] - BD[t])
        outside = [c for c in Dall if min(cheb(c, h) for h in H) > 3]
        print("   tick %d |D| %d  outside cheb-3 of (writes U earlier D, |H|=%d): %d" % (t, len(Dall), len(H), len(outside)))
        H |= Dall

    # --- drawing sets from recorded data (burn_intervals + fire_ground_final)
    def ticks_burning(ivs):
        n = 0
        for s, e in ivs:
            ee = T if e is None else e
            n += sum(1 for tt in range(s + 1, ee + 1) if tt % 3 == 0)
        return n

    def burnout_tick(d):
        out, bad = {}, 0
        for k, flags in d["fire_ground_final"].items():
            has_burned, burnt, burning_now = flags
            ivs = d["burn_intervals"].get(k) or []
            if burnt:
                b = ivs[-1][1]
                nb = ticks_burning(ivs)
                if not (7 <= nb <= 10):
                    bad += 1
                out[key2c(k)] = b
        return out, bad

    bo_d, bad_d = burnout_tick(DRY)
    bo_e, bad_e = burnout_tick(EFS)
    print("  burnt cells DRY %d (burn-tick count outside 7..10: %d), EFS %d (outside: %d)" % (len(bo_d), bad_d, len(bo_e), bad_e))

    def drawers(bo, t):
        return {key2c(k) for k in EFS["fire_ground_final"] if not (key2c(k) in bo and bo[key2c(k)] < t)}

    first_ds = None
    for t in range(3, T + 1, 3):
        a, b = drawers(bo_d, t), drawers(bo_e, t)
        if a != b:
            first_ds = (t, sorted(a - b), sorted(b - a))
            break
    print("  first tick with different drawing set (recorded):", first_ds[0], " DRY-only drawers", first_ds[1][:5],
          " EFS-only drawers", first_ds[2][:5], " uid of EFS-only:", [c[0] * N + c[1] for c in first_ds[2]])
    t84 = 84
    Dall = (BD[t84] - BE[t84]) | (BE[t84] - BD[t84])
    print("  tick 84: D cells with uid < 435:", sorted(c for c in Dall if c[0] * N + c[1] < 435),
          " max cheb to writes:", max(min(cheb(c, w) for w in wcells) for c in Dall))

    print("=" * 90)
    print("C. FIRST AGENT DIVERGENCES EFS vs DRY")
    for key in ("ff_steps", "victim_steps", "uav_steps", "ff_bind_steps"):
        ea, da = rows_by_entity(EFS, key), rows_by_entity(DRY, key)
        for ent in sorted(ea):
            fd = next((t for t in range(1, T + 1) if ea[ent].get(t) != da[ent].get(t)), None)
            print("   %-13s %-10s first diff step %s  EFS %s DRY %s" % (
                key, ent, fd, ea[ent].get(fd) if fd else "", da[ent].get(fd) if fd else ""))
    ea, da = rows_by_entity(EFS, "uav_actions"), rows_by_entity(DRY, "uav_actions")
    for ent in sorted(ea):
        fd_any = next((t for t in range(1, T + 1) if ea[ent].get(t) != da[ent].get(t)), None)
        fd_act = next((t for t in range(1, T + 1) if ea[ent][t][1] != da[ent][t][1]), None)
        fd_vsm = next((t for t in range(1, T + 1) if ea[ent][t][3] != da[ent][t][3]), None)
        print("   uav_actions %s first diff any field %s (EFS %s DRY %s); action label %s; visibility-smoke %s" % (
            ent, fd_any, ea[ent].get(fd_any), da[ent].get(fd_any), fd_act, fd_vsm))
    for key in ("planner", "assigns", "unassigns", "exit_starts", "completions", "retargets", "victim_flee_log", "victim_holds"):
        a, b = EFS[key], DRY[key]
        idx = next((i for i in range(max(len(a), len(b))) if (a[i] if i < len(a) else None) != (b[i] if i < len(b) else None)), None)
        print("   %-15s first differing index %s: EFS %s | DRY %s" % (
            key, idx, a[idx] if idx is not None and idx < len(a) else None, b[idx] if idx is not None and idx < len(b) else None))
    # any agent-record difference before 69?
    print("   NOTE first ff/victim/uav position difference must be after the burning divergence", fdb)

    print("=" * 90)
    print("D. TIMELINES")
    for a in ("fmOFF", "fmDRY", "fmEFS"):
        d = R[a]
        V = rows_by_entity(d, "victim_steps")
        F = rows_by_entity(d, "ff_steps")
        FB = rows_by_entity(d, "ff_bind_steps")
        B = burning_by_step(d)
        print("  --", a)
        for vid in sorted(V):
            st = {t: V[vid][t][2] for t in V[vid]}
            ss = segs(st)
            dead = next((t for t in range(1, T + 1) if st[t] == "dead"), None)
            resc = next((t for t in range(1, T + 1) if st[t] == "rescued"), None)
            dcell = V[vid][dead][1] if dead else None
            print("   %s status %s | dead@%s cell %s own cell burning %s | rescued@%s | final %s at %s" % (
                vid, [(x[0], x[1], x[2]) for x in ss], dead, dcell,
                (tuple(dcell) in B[dead]) if dcell else None, resc, V[vid][T][2], V[vid][T][1]))
        for ff in sorted(F):
            dd = next((t for t in range(1, T + 1) if F[ff][t][5]), None)
            print("   %s dead@%s pos %s | status@240 %s | bind segs %s" % (
                ff, dd, F[ff][dd][1] if dd else None, F[ff][T][2],
                [(x[0], x[1], x[2]) for x in segs({t: FB[ff][t][1] for t in FB[ff]})]))
            rb = segs({t: F[ff][t][2] == "route_blocked" for t in F[ff]})
            print("      route_blocked episodes:", [(x[0], x[1], F[ff][x[0]][1]) for x in rb if x[2]])
        print("   assigns", [(x["step"], x["ff"], x["vid"], x["reason"]) for x in d["assigns"]])
        print("   unassigns", [(x["step"], x["ff"], x["vid"], x["reason"]) for x in d["unassigns"]])
        print("   exit_starts", [(x["step"], x["ff"], x["victim"]) for x in d["exit_starts"]])
        print("   completions", [(x["step"], x["ff"], x["victim"]) for x in d["completions"]])
        print("   rescue_event_counts", d["rescue_event_counts"])
        print("   planner", [(x["step"], x["reason"], x["action"], x["vid"], x["ff"]) for x in d["planner"]])
    # reassignment geometry
    for a, t in (("fmDRY", 162), ("fmEFS", 210)):
        d = R[a]
        V = rows_by_entity(d, "victim_steps")
        F = rows_by_entity(d, "ff_steps")
        u_pre, u_post = F["ff_unit_0"][t - 1][1], F["ff_unit_0"][t][1]
        v2 = V["victim_2"][t][1]
        print("  %s reassignment step %d: ff_unit_0 pre-step %s post-step %s; victim_2 at %s; manhattan pre %d post %d; steps left %d" % (
            a, t, u_pre, u_post, v2, manh(u_pre, v2), manh(u_post, v2), T - t))
    F = rows_by_entity(EFS, "ff_steps")
    V = rows_by_entity(EFS, "victim_steps")
    mx = 0
    for t in range(2, T + 1):
        p, q = F["ff_unit_0"][t - 1][1], F["ff_unit_0"][t][1]
        if p and q:
            mx = max(mx, manh(p, q))
    print("  EFS ff_unit_0 max on-grid per-step move:", mx, " pos@240", F["ff_unit_0"][T][1], " victim_2@240", V["victim_2"][T])
    BE = burning_by_step(EFS)
    on_burn = [t for t in range(1, T + 1) if V["victim_2"][t][1] and tuple(V["victim_2"][t][1]) in BE[t]]
    print("  EFS victim_2 steps on a burning cell:", on_burn,
          " nearest burning @240:", min(manh(V["victim_2"][T][1], c) for c in BE[T]) if BE[T] else None)
    # victim_2 flee/holds per arm, and victim_0 trajectory direction
    for a in ("fmDRY", "fmEFS"):
        d = R[a]
        fl = [(x["step"], tuple(x["from"]), tuple(x["to"])) for x in d["victim_flee_log"] if x["victim_id"] == "victim_2"]
        ho = [x["step"] for x in d["victim_holds"] if x["victim"] == "victim_2"]
        print("  %s victim_2 flee moves %d, last 4 %s; holds %d (steps %s..%s)" % (a, len(fl), fl[-4:], len(ho), min(ho), max(ho)))
        V = rows_by_entity(d, "victim_steps")
        pts = segs({t: tuple(V["victim_0"][t][1]) if V["victim_0"][t][1] else None for t in range(130, 165)})
        print("  %s victim_0 positions 130..164: %s" % (a, [(x[0], x[1], x[2]) for x in pts]))
    # victim_2 at step 86/87, burning of its cells
    BD = burning_by_step(DRY)
    for a, d, B in (("fmDRY", DRY, BD), ("fmEFS", EFS, BE)):
        V = rows_by_entity(d, "victim_steps")
        print("  %s victim_2 pos 85..88 %s; (0,30) burning at 84/87: %s/%s; (0,29) %s/%s" % (
            a, [V["victim_2"][t][1] for t in (85, 86, 87, 88)], (0, 30) in B[84], (0, 30) in B[87], (0, 29) in B[84], (0, 29) in B[87]))
    Fd, Fe = rows_by_entity(DRY, "ff_steps"), rows_by_entity(EFS, "ff_steps")
    print("  ff_unit_1 rows identical DRY vs EFS all steps:", all(Fd["ff_unit_1"][t] == Fe["ff_unit_1"][t] for t in range(1, T + 1)))

    print("=" * 90)
    print("E. GATE SHARDS")
    for g, h in (("fmgOFF", "fmOFF"), ("fmgEFS", "fmEFS"), ("fmgFB", "fmF")):
        G = load("_rblatch_camp2_%ss_D_south.json" % g)
        ev = [e for e in G["evals"] if e.get("seed") == 404]
        same = None
        if ev:
            e = {k: v for k, v in ev[0].items() if k not in ("seed", "wall_s")}
            same = e == R[h]["eval"]
            diffk = sorted(k for k in set(e) | set(R[h]["eval"]) if e.get(k) != R[h]["eval"].get(k))
        print("  %s seed404 eval n=%d rescued %s dead %s ffd %s; == harness %s: %s (diff keys %s)" % (
            g, len(ev), ev[0]["rescued"], ev[0]["dead"], ev[0]["firefighter_deaths"], h, same, diffk))
        print("    exact_fires 404:", [(x["step"], x["ff"], x["pos"]) for x in G["exact_fires"] if x.get("seed") == 404])
        print("    latched 404:", [x for x in G["latched"] if isinstance(x, dict) and x.get("seed") == 404],
              " deaths 404:", [x for x in G["deaths"] if x.get("seed") == 404])


# ========================================================================= REPLAY
def build_neighbours():
    """(uid, factor) for burning-neighbour factors != 1.0, in mesa get_neighborhood order (nx asc, ny asc)."""
    MU = 0.9
    nb = []
    for x in range(N):
        for y in range(N):
            lst = []
            for nx in range(max(0, x - 3), min(N, x + 4)):
                for ny in range(max(0, y - 3), min(N, y + 4)):
                    if (nx, ny) == (x, y):
                        continue
                    m = numpy.linalg.norm(numpy.array((x, y)) - numpy.array((nx, ny)))
                    dr = m ** -2.0 if m <= 3 else 0
                    aux = dr * 1
                    # Wind.is_on_wind_direction('south'): centre[1] < adjacent[1] and same x
                    if (y < ny) and (x == nx):
                        aux = aux + (MU * (1 - aux))
                    else:
                        aux = aux - (MU * aux)
                    f = 1 - aux
                    if f != 1.0:
                        lst.append((nx * N + ny, float(f)))
            nb.append(lst)
    return nb


NB = None


def replay(wr, override=None, keep_draws=False, keep_state=False):
    """wr: dict step -> list of (x,y). override(u, tick, g) -> g. Returns dict."""
    global NB
    if NB is None:
        NB = build_neighbours()
    M = N * N
    rng = random.Random(SEED)
    xc = rng.randint(10, N - 10 - 1)
    yc = rng.randint(10, N - 10 - 1)
    fuel = [0] * M
    burning = [False] * M
    for i in range(N):
        for j in range(N):
            rng.random()
            fuel[i * N + j] = rng.randint(7, 10)
            burning[i * N + j] = (i == xc and j == yc)
    burnt = [False] * M
    hb = list(burning)
    out = {"origin": (xc, yc), "dig": [], "B": [], "BT": [], "draws": {}, "cp": {}, "state_in": {}, "wok": []}
    for step in range(1, T + 1):
        if step % 3 == 0:
            if keep_state:
                out["state_in"][step] = (bytes(burning), bytes(burnt), bytes(fuel))
            nxt = [False] * M
            dr = array("d", [-1.0]) * M if keep_draws else None
            cpa = array("d", [0.0]) * M if keep_draws else None
            for u in range(M):
                if burnt[u]:
                    continue
                if fuel[u] > 0:
                    prod = 1.0
                    for v, f in NB[u]:
                        if burning[v]:
                            prod = prod * f
                    P = 1 - prod
                else:
                    P = 0
                cp = P * 0.75
                cp = max(0.0, min(1.0, cp))
                g = rng.random()
                if override is not None:
                    g = override(u, step, g)
                if keep_draws:
                    dr[u] = g
                    cpa[u] = cp
                nxt[u] = g < cp
                if burning[u]:
                    hb[u] = True
                    if fuel[u] > 0:
                        fuel[u] -= 1
                if hb[u] and fuel[u] <= 0:
                    burnt[u] = True
                    burning[u] = False
                    nxt[u] = False
            for u in range(M):
                burning[u] = False if burnt[u] else nxt[u]
            if keep_draws:
                out["draws"][step] = dr
                out["cp"][step] = cpa
        for c in wr.get(step, ()):
            u = c[0] * N + c[1]
            ok = (not burnt[u]) and (not burning[u]) and fuel[u] > 0
            if ok:
                fuel[u] = 0
            out["wok"].append((step, c, ok))
        out["dig"].append(hashlib.sha256("|".join(
            "%d:%d%d%s" % (u, int(burning[u]), int(burnt[u]), fuel[u]) for u in range(M)).encode()).hexdigest())
        out["B"].append(bytes(burning))
        out["BT"].append(bytes(burnt))
    return out


def wdict(ws):
    d = {}
    for s, c in ws:
        d.setdefault(s, []).append(tuple(c))
    return d


def bset(b):
    return {(u // N, u % N) for u, v in enumerate(b) if v}


def replay_checks():
    print("=" * 90)
    print("F. INDEPENDENT FIRE REPLAY")
    W = [(w[0], w[3]) for w in writes(EFS)]
    WF = [(w[0], w[3]) for w in writes(R["fmF"])]
    rd = replay({}, keep_draws=True, keep_state=True)
    re_ = replay(wdict(W), keep_draws=True, keep_state=True)
    rf = replay(wdict(WF))
    print("  origin", rd["origin"])
    for name, rr in (("fmOFF", rd), ("fmREF", rd), ("fmDRY", rd), ("fmEFS", re_), ("fmFS", re_), ("fmF", rf)):
        m = sum(1 for a, b in zip(rr["dig"], R[name]["fire_digests"]) if a == b)
        print("  replay digest == recorded %s: %d/240" % (name, m))
    BD, BE = burning_by_step(DRY), burning_by_step(EFS)
    print("  replay burning == burn_intervals DRY %d/240, EFS %d/240" % (
        sum(1 for t in range(1, T + 1) if bset(rd["B"][t - 1]) == BD[t]),
        sum(1 for t in range(1, T + 1) if bset(re_["B"][t - 1]) == BE[t])))
    print("  all writes landed:", all(ok for _, _, ok in re_["wok"]))
    # drawing set and draw differences
    first = None
    for t in range(3, T + 1, 3):
        a = [u for u in range(N * N) if rd["draws"][t][u] >= 0]
        b = [u for u in range(N * N) if re_["draws"][t][u] >= 0]
        if a != b:
            first = (t, sorted(set(a) - set(b)), sorted(set(b) - set(a)))
            break
    print("  replay first drawing-set difference:", first)
    for t in (81, 84, 87):
        dd, de = rd["draws"][t], re_["draws"][t]
        cd, ce = rd["cp"][t], re_["cp"][t]
        nz = [u for u in range(N * N) if cd[u] > 0 or ce[u] > 0]
        diffnum = [u for u in nz if dd[u] != de[u]]
        lo = [u for u in range(N * N) if u < 435 and dd[u] >= 0 and de[u] >= 0 and dd[u] != de[u]]
        hi_same = [u for u in range(N * N) if u > 435 and dd[u] >= 0 and de[u] >= 0 and dd[u] == de[u]]
        print("  tick %d: cells with cp>0 in either arm %d, of which a different number (incl. one-arm drawers) %d;"
              " uid<435 differing %d; uid>435 same %d" % (t, len(nz), len(diffnum), len(lo), len(hi_same)))
    # tight classification of D cells at ticks 69..120
    sd, se = rd["state_in"], re_["state_in"]

    def phys(t, u):
        x, y = divmod(u, N)
        for nx in range(max(0, x - 3), min(N, x + 4)):
            for ny in range(max(0, y - 3), min(N, y + 4)):
                v = nx * N + ny
                if sd[t][0][v] != se[t][0][v] or sd[t][1][v] != se[t][1][v] or sd[t][2][v] != se[t][2][v]:
                    return True
        return False

    for t in list(range(69, 97, 3)) + [120]:
        Dall = bset(rd["B"][t - 1]) ^ bset(re_["B"][t - 1])
        cls = {"phys": 0, "draw": 0, "both": 0, "neither": 0}
        for c in Dall:
            u = c[0] * N + c[1]
            p = phys(t, u)
            q = rd["draws"][t][u] != re_["draws"][t][u]
            cls["both" if p and q else "phys" if p else "draw" if q else "neither"] += 1
        print("  tick %d |D| %d classes %s" % (t, len(Dall), cls))

    # physical-only counterfactual: EFS writes, each (cell, tick) reads fmDRY's number; fallback when DRY did not draw
    ddraws = rd["draws"]
    res_cf = {}
    for label, fb in (("A_never", 1.0), ("B_always", 0.0)):
        def ov(u, t, g, fb=fb):
            x = ddraws[t][u]
            return x if x >= 0 else fb
        rc = replay(wdict(W), override=ov)
        diffs = [bset(rc["B"][t - 1]) ^ bset(rd["B"][t - 1]) for t in range(1, T + 1)]
        uni = set().union(*diffs)
        first_t = next((t for t in range(1, T + 1) if diffs[t - 1]), None)
        print("  phys-only %s: first diff %s, max |D| %d, union %d cells, x %s..%s y %s..%s; empty at 81/84/87: %s" % (
            label, first_t, max(len(x) for x in diffs), len(uni), min(c[0] for c in uni), max(c[0] for c in uni),
            min(c[1] for c in uni), max(c[1] for c in uni), [not diffs[t - 1] for t in (81, 84, 87)]))
        res_cf[label] = diffs
    # closest approach of phys-only difference to agents on DRY paths
    for arm in ("fmDRY", "fmEFS"):
        d = R[arm]
        ents = {}
        ents.update(rows_by_entity(d, "victim_steps"))
        ents.update(rows_by_entity(d, "ff_steps"))
        for ent in ("victim_0", "victim_2", "victim_3", "ff_unit_0"):
            best = None
            for label, diffs in res_cf.items():
                for t in range(1, T + 1):
                    p = ents[ent][t][1]
                    if p is None or not diffs[t - 1]:
                        continue
                    if arm == "fmEFS" or True:
                        dm = min(manh(p, c) for c in diffs[t - 1])
                        if best is None or dm < best[0]:
                            best = (dm, t, label)
            print("  closest phys-only difference to %s on %s path: %s" % (ent, arm, best))

    # prefix and write-subset variants
    BDr = [bset(b) for b in rd["B"]]
    BEr = [bset(b) for b in re_["B"]]

    def cmp(rr):
        B = [bset(b) for b in rr["B"]]
        fd = next((t for t in range(1, T + 1) if B[t - 1] != BDr[t - 1]), None)
        fe = next((t for t in range(1, T + 1) if B[t - 1] != BEr[t - 1]), None)
        td = next((t for t in range(1, T + 1) if rr["BT"][t - 1] != rd["BT"][t - 1]), None)
        te = next((t for t in range(1, T + 1) if rr["BT"][t - 1] != re_["BT"][t - 1]), None)
        pre68 = all(B[t - 1] == BDr[t - 1] and rr["BT"][t - 1] == rd["BT"][t - 1] for t in range(1, 69))
        return fd, td, fe, te, pre68

    variants = []
    for s in range(9, 18):
        variants.append(("s=%d" % s, [w for w in W if w[0] < s]))
    w13a = [w for w in W if w[0] < 13]
    variants.append(("steps<13 + (7,40)@13", w13a + [(13, (7, 40))]))
    variants.append(("steps<13 + (8,43)@13", w13a + [(13, (8, 43))]))
    variants.append(("only (7,40)@13", [(13, (7, 40))]))
    variants.append(("only (8,43)@13", [(13, (8, 43))]))
    variants.append(("all but (7,40)@13", [w for w in W if w != (13, (7, 40))]))
    variants.append(("all but (6,41)@12", [w for w in W if w != (12, (6, 41))]))
    variants.append(("all but (6,42)@16", [w for w in W if w != (16, (6, 42))]))
    s13 = None
    for name, ws in variants:
        rr = replay(wdict(ws))
        fd, td, fe, te, pre68 = cmp(rr)
        print("  %-24s writes %2d | vs DRY burning %s burnt %s | vs EFS burning %s burnt %s | ==DRY thru 68: %s | digests==EFS %d/240" % (
            name, len(ws), fd, td, fe, te, pre68, sum(1 for a, b in zip(rr["dig"], EFS["fire_digests"]) if a == b)))
        if name == "s=13":
            s13 = [bset(b) for b in rr["B"]]
        if name == "steps<13 + (8,43)@13":
            B = [bset(b) for b in rr["B"]]
            print("     equals s=13 burning 240/240:", s13 is not None and all(B[i] == s13[i] for i in range(T)))


def early_records():
    """Earliest step at which any step-stamped record differs EFS vs DRY; detail of victim_holds diffs < 84."""
    print("=" * 90)
    print("G. EARLIEST RECORD DIFFERENCES (step-stamped lists)")
    for key in sorted(EFS):
        a, b = EFS[key], DRY.get(key)
        if not isinstance(a, list) or not a or not isinstance(a[0], dict) or "step" not in a[0]:
            continue
        sa, sb = {}, {}
        for r in a:
            sa.setdefault(r["step"], []).append(r)
        for r in b or []:
            sb.setdefault(r["step"], []).append(r)
        fd = next((t for t in sorted(set(sa) | set(sb)) if sa.get(t) != sb.get(t)), None)
        print("  %-22s earliest differing step %s" % (key, fd))
    ha = [r for r in EFS["victim_holds"] if r["step"] < 86]
    hb = [r for r in DRY["victim_holds"] if r["step"] < 86]
    print("  victim_holds <86: EFS %d DRY %d" % (len(ha), len(hb)))
    ia = {(r["step"], r["victim"]): r for r in ha}
    ib = {(r["step"], r["victim"]): r for r in hb}
    for k in sorted(set(ia) | set(ib)):
        ra, rb = ia.get(k), ib.get(k)
        if ra != rb:
            if ra is None or rb is None:
                print("   ", k, "only in", "EFS" if rb is None else "DRY", ra or rb)
                continue
            f = {kk: (ra.get(kk), rb.get(kk)) for kk in set(ra) | set(rb) if ra.get(kk) != rb.get(kk)}
            print("   ", k, "fields differ:", f)
    # partition_steps / other per-step lists
    for key in ("partition_steps",):
        fd = next((i + 1 for i, (x, y) in enumerate(zip(EFS[key], DRY[key])) if x != y), None)
        print("  %s first differing step %s" % (key, fd))


def extra_checks():
    print("=" * 90)
    print("H. EXTRA REPLAY CHECKS")
    W = [(w[0], w[3]) for w in writes(EFS)]
    rd = replay({}, keep_draws=True, keep_state=True)
    re_ = replay(wdict(W), keep_draws=True, keep_state=True)
    BDr = [bset(b) for b in rd["B"]]
    BEr = [bset(b) for b in re_["B"]]
    # loose cone coverage
    t1 = {w: (w[0] // 3 + 1) * 3 for w in W}
    cover = None
    for t in range(12, 120, 3):
        ok = all(any(cheb((x, y), w[1]) <= t - t1[w] for w in W if t >= t1[w]) for x in range(N) for y in range(N))
        if ok:
            cover = t
            break
    print("  loose cone (radius t - first-read tick per write) covers all 2500 cells from tick", cover)
    # s=13 vs steps<13 + (8,43)@13
    s13 = replay(wdict([w for w in W if w[0] < 13]))
    v843 = replay(wdict([w for w in W if w[0] < 13] + [(13, (8, 43))]))
    B1 = [bset(b) for b in s13["B"]]
    B2 = [bset(b) for b in v843["B"]]
    fd = next((t for t in range(1, T + 1) if B1[t - 1] != B2[t - 1]), None)
    fdt = next((t for t in range(1, T + 1) if s13["BT"][t - 1] != v843["BT"][t - 1]), None)
    print("  s=13 vs steps<13+(8,43)@13: first burning diff %s, first burnt diff %s, |D| at 240 %d" % (
        fd, fdt, len(B1[T - 1] ^ B2[T - 1])))
    if fd:
        print("    D at first diff:", sorted(B1[fd - 1] ^ B2[fd - 1])[:10])
    # all singles and all-buts
    for w in W:
        rr = replay(wdict([w]))
        B = [bset(b) for b in rr["B"]]
        print("  only %s@%d: vs DRY burning %s | vs EFS burning %s" % (
            w[1], w[0], next((t for t in range(1, T + 1) if B[t - 1] != BDr[t - 1]), None),
            next((t for t in range(1, T + 1) if B[t - 1] != BEr[t - 1]), None)))
    for w in W:
        rr = replay(wdict([x for x in W if x != w]))
        B = [bset(b) for b in rr["B"]]
        print("  all but %s@%d: vs DRY burning %s | vs EFS burning %s" % (
            w[1], w[0], next((t for t in range(1, T + 1) if B[t - 1] != BDr[t - 1]), None),
            next((t for t in range(1, T + 1) if B[t - 1] != BEr[t - 1]), None)))
    # classification of D cells near each agent at its first divergence
    sd, se = rd["state_in"], re_["state_in"]

    def phys(t, u):
        x, y = divmod(u, N)
        for nx in range(max(0, x - 3), min(N, x + 4)):
            for ny in range(max(0, y - 3), min(N, y + 4)):
                v = nx * N + ny
                if sd[t][0][v] != se[t][0][v] or sd[t][1][v] != se[t][1][v] or sd[t][2][v] != se[t][2][v]:
                    return True
        return False

    for ent, t, c0, rad in (("ff_unit_0", 84, (25, 40), 5), ("victim_2", 87, (0, 30), 5), ("victim_3", 90, (38, 3), 5),
                            ("victim_0", 96, (41, 25), 5), ("uav2503", 84, (42, 38), 11)):
        Dall = BDr[t - 1] ^ BEr[t - 1]
        near = sorted(c for c in Dall if manh(c, c0) <= rad)
        cls = {}
        for c in near:
            u = c[0] * N + c[1]
            p = phys(t, u)
            q = rd["draws"][t][u] != re_["draws"][t][u]
            k = "both" if p and q else "phys" if p else "draw" if q else "neither"
            cls[k] = cls.get(k, 0) + 1
        print("  %s tick %d near %s r%d: %d cells %s classes %s" % (ent, t, c0, rad, len(near), near[:12], cls))
    # where are the 15 'both' cells at tick 84, and the 8 'phys' cells at tick 90
    for t, want in ((84, "both"), (90, "phys")):
        Dall = BDr[t - 1] ^ BEr[t - 1]
        sel = []
        for c in sorted(Dall):
            u = c[0] * N + c[1]
            p = phys(t, u)
            q = rd["draws"][t][u] != re_["draws"][t][u]
            k = "both" if p and q else "phys" if p else "draw" if q else "neither"
            if k == want:
                sel.append(c)
        print("  tick %d '%s' cells: %s" % (t, want, sel))
    # state differences entering tick 84 (where are they)
    t = 84
    sdiff = [divmod(v, N) for v in range(N * N) if sd[t][0][v] != se[t][0][v] or sd[t][1][v] != se[t][1][v] or sd[t][2][v] != se[t][2][v]]
    print("  cells with differing state entering tick 84:", sdiff)
    # counterfactual burnt-in-DRY drawers (the fallback) near agents: count fallback uses
    # smoke dependence check: does Smoke read live fuel?


def misc_checks():
    print("=" * 90)
    print("I. MISC")
    W = [(w[0], w[3]) for w in writes(EFS)]
    s13 = replay(wdict([w for w in W if w[0] < 13]))
    v843 = replay(wdict([w for w in W if w[0] < 13] + [(13, (8, 43))]))
    uni = set()
    steps = []
    for t in range(1, T + 1):
        d = bset(s13["B"][t - 1]) ^ bset(v843["B"][t - 1])
        if d:
            steps.append(t)
        uni |= d
    print("  s=13 vs steps<13+(8,43)@13: union of burning differences over 240 steps %s on steps %s..%s (%d steps)" % (
        sorted(uni), steps[0] if steps else None, steps[-1] if steps else None, len(steps)))
    s16 = replay(wdict([w for w in W if w[0] < 16]))
    print("  s=16 final digest == fmEFS fire_final_digest:", s16["dig"][-1] == EFS["fire_final_digest"],
          " s=9-like (no writes) final == fmDRY final:", replay({})["dig"][-1] == DRY["fire_final_digest"])
    for arm in ("fmEFS", "fmDRY"):
        p = os.path.join(HERE, "_ffr_%s_south_half_404.stdout.txt" % arm)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            hits = [ln for ln in lines if "clear" in ln.lower() or "firefight" in ln.lower()]
            print("  %s stdout lines %d, lines mentioning clear/firefight: %s" % (arm, len(lines), hits[:5]))
        else:
            print("  %s stdout file not present" % arm)
    # victim_0 and victim_3 in DRY/EFS: which victim ids were confirmed-needy when ff_unit_0 was released
    for arm, t in (("fmDRY", 162), ("fmEFS", 210)):
        V = rows_by_entity(R[arm], "victim_steps")
        print("  %s step %d victim statuses: %s" % (arm, t, [(v, V[v][t][2], V[v][t][1]) for v in sorted(V)]))
    # physical-only counterfactual: ff_unit_1's death region vs NW difference (ff_unit_1 dies 72 at (0,8))
    # idle units after step 16 in EFS (would a WRITE_BEFORE s>16 run ever call the dry switch?)
    F = rows_by_entity(EFS, "ff_steps")
    idle = [(ff, t) for ff in F for t in range(17, T + 1)
            if F[ff][t][2] == "available" and not F[ff][t][3] and not F[ff][t][4] and not F[ff][t][5] and F[ff][t][1] is not None]
    print("  EFS idle unit-steps after 16 (available, not assigned/exiting/dead, on grid):", idle[:10], len(idle))


def uav_checks():
    print("=" * 90)
    print("J. UAVs (not covered by the analyst's closest-approach list)")
    W = [(w[0], w[3]) for w in writes(EFS)]
    rd = replay({}, keep_draws=True, keep_state=True)
    re_ = replay(wdict(W), keep_draws=True, keep_state=True)
    BDr = [bset(b) for b in rd["B"]]
    BEr = [bset(b) for b in re_["B"]]
    sd, se = rd["state_in"], re_["state_in"]

    def cls_of(t, c):
        u = c[0] * N + c[1]
        x, y = c
        p = False
        for nx in range(max(0, x - 3), min(N, x + 4)):
            for ny in range(max(0, y - 3), min(N, y + 4)):
                v = nx * N + ny
                if sd[t][0][v] != se[t][0][v] or sd[t][1][v] != se[t][1][v] or sd[t][2][v] != se[t][2][v]:
                    p = True
        q = rd["draws"][t][u] != re_["draws"][t][u]
        return "both" if p and q else "phys" if p else "draw" if q else "neither"

    Ud = rows_by_entity(DRY, "uav_steps")
    Ue = rows_by_entity(EFS, "uav_steps")
    for uid in sorted(Ud):
        print("  UAV %s role %s | DRY pos 80..89 %s" % (uid, Ud[uid][84][2], [tuple(Ud[uid][t][1]) for t in range(80, 90)]))
        print("            EFS pos 80..89 %s" % [tuple(Ue[uid][t][1]) for t in range(80, 90)])
        for t in (84, 87):
            p = tuple(Ud[uid][t][1])
            nd = min(manh(p, c) for c in BDr[t - 1])
            ne = min(manh(p, c) for c in BEr[t - 1])
            Dall = BDr[t - 1] ^ BEr[t - 1]
            near = sorted(c for c in Dall if manh(p, c) <= max(nd, ne) + 2)
            cl = {}
            for c in near:
                k = cls_of(t, c)
                cl[k] = cl.get(k, 0) + 1
            print("     tick %d at %s nearest burning DRY %d EFS %d; D cells within that+2: %d classes %s" % (t, p, nd, ne, len(near), cl))
    # phys-only counterfactual closest approach for UAVs
    ddraws = rd["draws"]

    def ov(u, t, g):
        x = ddraws[t][u]
        return x if x >= 0 else 1.0
    rc = replay(wdict(W), override=ov)
    diffs = [bset(rc["B"][t - 1]) ^ BDr[t - 1] for t in range(1, T + 1)]
    for uid in sorted(Ud):
        best = None
        for t in range(1, T + 1):
            p = Ud[uid][t][1]
            if p is None or not diffs[t - 1]:
                continue
            dm = min(manh(p, c) for c in diffs[t - 1])
            if best is None or dm < best[0]:
                best = (dm, t)
        print("  phys-only(A) closest approach to UAV %s on DRY path: %s" % (uid, best))
        pre = [(min(manh(Ud[uid][t][1], c) for c in diffs[t - 1]), t) for t in range(1, 205)
               if Ud[uid][t][1] is not None and diffs[t - 1]]
        print("     before step 205: min %s; first step within 5: %s" % (min(pre) if pre else None,
                                                                         next((t for dm, t in pre if dm <= 5), None)))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("json", "all"):
        json_checks()
    if mode in ("early", "all"):
        early_records()
    if mode in ("replay", "all"):
        replay_checks()
    if mode in ("extra", "all"):
        extra_checks()
    if mode in ("misc", "all"):
        misc_checks()
    if mode in ("uav", "all"):
        uav_checks()
