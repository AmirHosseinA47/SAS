"""firemech round 2 - TASK B: south/half/404, the single write-caused rescue loss. Read-only.

usage:  .venv/Scripts/python.exe outputs/_fm2_diag_south404.py
writes: outputs/_fm2_diag_south404.txt (overwritten)

INPUTS (explicit paths only, nothing else under outputs/ is read)
  outputs/_ffr_{fmOFF,fmREF,fmDRY,fmEFS,fmF,fmFS,fmES}_south_half_404.json   harness runs
  outputs/_rblatch_camp2_{fmgOFF,fmgEFS,fmgFB}s_D_south.json                 gate shards

WHAT IS COMPUTED, AND FROM WHAT
  Every agent-side number comes straight from the harness JSON fields.
  Fire-side numbers come from the JSON too (fire_digests, burn_intervals,
  fire_ground_final), plus ONE derived instrument:

  OFFLINE FIRE REPLAY (no model, no harness, no mesa import; pure Python + numpy
  for the distance table). The fire is open-loop: Fire.step/advance read only
  fire state and one shared random.Random(seed) stream, which nothing else
  consumes after construction (agents.py / wildfire_model.py / src_extension
  grep: the only runtime draws are Fire.step's random.random(); Wind never
  changes with FIXED_WIND=True; the absence RNG is a separate Random seeded
  before set_fire_agents). Firefighter writes are the only outside input, and
  the harness records every one (firefight_log rows with wrote True). The
  replay reproduces, in unique-id (row-major x*50+y) order:
    - set_fire_agents: randint x_c, randint y_c, then per cell random() (density
      test) and randint(7,10) (Fire.__init__ fuel)
    - Fire.step at steps % 3 == 0: probability_of_fire (radius-3 Moore
      neighbourhood in mesa's order, distance_rate = norm**-2 within 3, south
      wind MU=0.9), * 0.75, clamp, ONE draw per non-burnt cell, fuel decrement,
      burnt latch - including the quirk that a cell turning burnt sets
      burning=False DURING the step loop, so later ids see it unburning
    - Fire.advance, then that step's firebreak writes (firefighter_remove_fuel
      precondition re-checked), then the harness digest string
      "uid:<burning><burnt><fuel>" joined by "|"
  It is accepted only if it reproduces the recorded sha256 fire digest of
  fmOFF, fmDRY, fmEFS, fmF and fmFS on 240/240 steps and the recorded
  burn_intervals of fmDRY and fmEFS on 240/240 steps (checked below; the
  report states the result). Counterfactual fires (write subsets, aligned
  draws) are then exact for the FIRE; closed-loop agent outcomes of a
  counterfactual are NOT computed - only bounded where the fire is provably
  identical to a recorded arm.

DEFINITIONS
  tick            a step t with t % 3 == 0 (Fire.steps_counter == model step)
  B_arm(t)        cells burning in the post-step observation of step t
                  (burn_intervals: [start, end) = observations start..end-1)
  D(t)            B_DRY(t) XOR B_EFS(t)
  loose cone      a write landing after step s is first read by the tick
                  t1 = next multiple of 3 above s; at tick t it can have reached
                  Chebyshev distance t - t1 (3 cells per tick)
  tight test      for a D cell at tick t: PHYS = its own (burning,burnt,fuel)
                  entering t differs, or any cell of its radius-3 Moore
                  neighbourhood differs in that state; DRAW = the random number
                  it received at tick t differs (or it drew in one arm only).
                  A physical propagation needs PHYS; a pure re-roll is DRAW
                  without PHYS. Neither is impossible (asserted).
  drawing set     cells not burnt entering a tick. From recorded data alone: a
                  cell burnt at the end became burnt on the tick that ends its
                  LAST burn interval (fuel = its count of burning ticks, 7..10,
                  checked), so it draws at tick t iff that end >= t.
  prefix s        FM2P_WRITE_BEFORE=s (outputs/_fm2_probe_harness.py): fire writes
                  land only on steps < s; later decisions run DRY (shadow set).
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import random

import numpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_TXT = os.path.join(HERE, "_fm2_diag_south404.txt")
SEED = 404
N = 50
STEPS = 240
SPEED = 3
MULT = 0.75
MU = 0.9
FLEE_TRIGGER = 3

ARMS = ["fmOFF", "fmREF", "fmDRY", "fmEFS", "fmF", "fmFS", "fmES"]
OUT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def hdr(title):
    say("")
    say("=" * 96)
    say(title)
    say("=" * 96)


def load_json(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


D = {a: load_json("_ffr_%s_south_half_404.json" % a) for a in ARMS}
GATE = {t: load_json("_rblatch_camp2_%ss_D_south.json" % t) for t in ("fmgOFF", "fmgEFS", "fmgFB")}


def uid(c):
    return int(c[0]) * N + int(c[1])


def cell(u):
    return divmod(u, N)


def fmt(c):
    return "(%d,%d)" % (c[0], c[1]) if c is not None else "None"


def manh(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


# ================================================================== replay ====
def _factor_table():
    tab = {}
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx == 0 and dy == 0:
                continue
            # distance_rate(s, s_) with s = centre (0,0), s_ = neighbour (dx,dy)
            m = numpy.linalg.norm(numpy.array((0, 0)) - numpy.array((dx, dy)))
            aux = (m ** -2.0 if m <= 3 else 0) * 1
            # Wind.is_on_wind_direction('south'): centre[1] < adjacent[1] and same x
            if (0 < dy) and (dx == 0):
                aux = aux + (MU * (1 - aux))
            else:
                aux = aux - (MU * aux)
            tab[(dx, dy)] = float(1 - aux)
    return tab


def _neighbours():
    tab = _factor_table()
    nb, full = [], []
    for x in range(N):
        for y in range(N):
            lst, allc = [], []
            for nx in range(max(0, x - 3), min(N, x + 4)):
                for ny in range(max(0, y - 3), min(N, y + 4)):
                    if nx == x and ny == y:
                        continue
                    allc.append(nx * N + ny)
                    f = tab[(nx - x, ny - y)]
                    if f != 1.0:  # an exact 1.0 factor leaves the ordered product unchanged
                        lst.append((nx * N + ny, f))
            nb.append(lst)
            full.append(allc)
    return nb, full


NB, NB_ALL = _neighbours()


def replay(writes, draw_override=None, record=False, snap_ticks=()):
    """writes {step: [(x,y),...]}. Returns per-step burning/burnt bytes, digests, and
    (record) per-tick draw values (None = no draw) and cell probabilities."""
    rng = random.Random(SEED)
    xc = rng.randint(10, N - 10 - 1)
    yc = rng.randint(10, N - 10 - 1)
    fuel, burning = [], []
    for i in range(N):
        for j in range(N):
            rng.random()
            fuel.append(rng.randint(7, 10))
            burning.append(i == xc and j == yc)
    M = N * N
    burnt = [False] * M
    has_burned = list(burning)
    res = {"origin": (xc, yc), "digests": [], "burning": [], "burnt": [], "draws": {}, "probs": {},
           "snap": {}, "write_ok": {}}
    for step in range(1, STEPS + 1):
        if step % SPEED == 0:
            if step in snap_ticks:
                res["snap"][step] = (bytes(burning), bytes(burnt), bytes(fuel))
            nxt = [False] * M
            dr = [None] * M if record else None
            pr = [0.0] * M if record else None
            for u in range(M):
                if burnt[u]:
                    continue
                if fuel[u] > 0:
                    prod = 1.0
                    for v, f in NB[u]:
                        if burning[v]:
                            prod *= f
                    P = 1 - prod
                else:
                    P = 0
                cp = max(0.0, min(1.0, P * MULT))
                g = rng.random()
                if draw_override is not None:
                    g = draw_override(u, step, g)
                if record:
                    dr[u] = g
                    pr[u] = cp
                nxt[u] = g < cp
                if burning[u]:
                    has_burned[u] = True
                    if fuel[u] > 0:
                        fuel[u] = fuel[u] - 1
                if has_burned[u] and fuel[u] <= 0:
                    burnt[u] = True
                    burning[u] = False
                    nxt[u] = False
            for u in range(M):
                burning[u] = False if burnt[u] else nxt[u]
            if record:
                res["draws"][step] = dr
                res["probs"][step] = pr
        for c in writes.get(step, ()):
            u = uid(c)
            ok = (not burnt[u]) and (not burning[u]) and fuel[u] > 0
            if ok:
                fuel[u] = 0
            res["write_ok"][(step, tuple(c))] = ok
        res["digests"].append(hashlib.sha256(
            "|".join("%d:%d%d%s" % (u, int(burning[u]), int(burnt[u]), fuel[u]) for u in range(M)).encode()
        ).hexdigest())
        res["burning"].append(bytes(burning))
        res["burnt"].append(bytes(burnt))
    return res


def bset(bts):
    return {i for i, v in enumerate(bts) if v}


def first_div(seq_a, seq_b, start=1):
    for i, (a, b) in enumerate(zip(seq_a, seq_b)):
        if a != b:
            return i + start
    return None


# ================================================================ helpers ====
def diff_keys(a, b, exclude):
    keys = (set(a) | set(b)) - set(exclude)
    return sorted(k for k in keys if a.get(k, "<absent>") != b.get(k, "<absent>"))


def burning_from_intervals(d):
    out = [set() for _ in range(STEPS + 1)]
    for k, ivs in d["burn_intervals"].items():
        x, y = map(int, k.split(","))
        for a, b in ivs:
            for t in range(a, (STEPS + 1) if b is None else b):
                out[t].add(x * N + y)
    return out


def writes_of(d):
    w = collections.defaultdict(list)
    for r in d.get("firefight_log") or []:
        if r.get("wrote"):
            w[r["step"]].append(tuple(r["target"]))
    return dict(w)


def pos_series(d, key, ent):
    """step -> row for one entity (ff_steps / victim_steps)."""
    s = {}
    for i, row in enumerate(d[key]):
        for r in row:
            if r[0] == ent:
                s[i + 1] = r
    return s


def segments(series, f):
    segs, prev = [], object()
    for t in sorted(series):
        v = f(series[t])
        if v != prev:
            segs.append([t, t, v])
            prev = v
        else:
            segs[-1][1] = t
    return segs


def status_segments(d, key, ent, idx):
    return [(a, b, v) for a, b, v in segments(pos_series(d, key, ent), lambda r: r[idx])]


def path_tokens(d, key, ent, t0, t1):
    s = pos_series(d, key, ent)
    toks = []
    for t in range(t0, t1 + 1):
        p = s[t][1]
        toks.append("%d:%s" % (t, "-" if p is None else "%d,%d" % (p[0], p[1])))
    return toks


def print_tokens(toks, per=10, indent="      "):
    for i in range(0, len(toks), per):
        say(indent + " ".join(toks[i:i + per]))


def final_victims(d):
    res = {}
    for vid in sorted(d["victim_spawns"]):
        s = pos_series(d, "victim_steps", vid)
        segs = status_segments(d, "victim_steps", vid, 2)
        last = s[STEPS]
        term = [(a, v) for a, _b, v in segs if v in ("rescued", "dead")]
        tstep = term[0][0] if term else None
        tcell = s[tstep][1] if (tstep and s[tstep][1] is not None) else (s[tstep - 1][1] if tstep else None)
        res[vid] = {"final": last[2], "final_pos": last[1], "term_step": tstep, "term_cell": tcell}
    return res


def ff_deaths(d):
    out = {}
    for ff in ("ff_unit_0", "ff_unit_1"):
        s = pos_series(d, "ff_steps", ff)
        dead = [t for t in sorted(s) if s[t][5]]
        out[ff] = (dead[0], s[dead[0]][1]) if dead else None
    return out


# ================================================================== report ====
def main():
    efs, dry, off, ffF, ffFS = D["fmEFS"], D["fmDRY"], D["fmOFF"], D["fmF"], D["fmFS"]
    say("south/half/404 - write-caused rescue loss diagnosis (fmEFS vs fmDRY, with fmOFF / fmF / fmFS)")
    say("generated by outputs/_fm2_diag_south404.py from the harness JSON (explicit paths); read-only")

    # ------------------------------------------------------------ outcomes ----
    hdr("0. OUTCOMES AND IDENTITIES")
    say("  arm     rescued dead ff_deaths candidate terminal burnt | per victim: final status (terminal step, cell)"
        " | ff deaths")
    for a in ARMS:
        ev = D[a]["eval"]
        fv = final_victims(D[a])
        vtxt = "  ".join("%s:%s(%s,%s)" % (v[-1], x["final"], x["term_step"] if x["term_step"] else "-",
                                           fmt(x["term_cell"]) if x["term_step"] else fmt(x["final_pos"]))
                         for v, x in fv.items())
        fd = ff_deaths(D[a])
        ftxt = " ".join("%s@%s%s" % (k[-1], v[0], fmt(v[1])) for k, v in fd.items() if v) or "none"
        say("  %-6s %7s %4s %9s %9s %8s %5s | %s | %s" % (a, ev["rescued"], ev["dead"], ev["firefighter_deaths"],
                                                       ev["candidate"], ev["terminal_step"], ev["burnt_cells"],
                                                       vtxt, ftxt))
    ex = ("tag", "repo", "wall_s", "params", "extra_params")
    for x, y in (("fmOFF", "fmREF"), ("fmEFS", "fmFS"), ("fmEFS", "fmF"), ("fmDRY", "fmOFF"), ("fmEFS", "fmDRY")):
        dk = diff_keys(D[x], D[y], ex)
        say("  %s vs %s: %s" % (x, y, ("value-identical (excluding %s)" % ", ".join(ex)) if not dk
                                else "%d differing keys: %s" % (len(dk), ", ".join(dk))))
    for x, y in (("fmEFS", "fmF"), ("fmEFS", "fmFS"), ("fmEFS", "fmDRY")):
        la, lb = D[x]["firefight_log"], D[y]["firefight_log"]
        fields = sorted({k for ra, rb in zip(la, lb) for k in set(ra) | set(rb) if ra.get(k, "<a>") != rb.get(k, "<a>")})
        say("  firefight_log %s vs %s: rows %d/%d, fields differing on some row: %s" % (
            x, y, len(la), len(lb), fields or "none"))
    say("  => the round-1 claim 'fmF identical to fmEFS run for run' HOLDS on this tuple, and more strongly:")
    say("     fmF differs from fmEFS only in the configuration-dependent log fields above (K/T/exit_guard);")
    say("     fmFS is value-identical to fmEFS. Everything below said of fmEFS applies to both.")

    # -------------------------------------------------------------- writes ----
    hdr("1. EVERY WRITE, AND THE FIRST FIRE-DIGEST DIVERGENCE")
    W = writes_of(efs)
    wlist = [(s, c) for s in sorted(W) for c in W[s]]
    dry_rows = {(r["step"], r["ff"], tuple(r["target"])): r for r in dry["firefight_log"]}
    say("  step unit       unit_cell target  action scorched | same row in fmDRY (dry, wrote) | fmF wrote")
    f_rows = {(r["step"], r["ff"], tuple(r["target"])): r for r in ffF["firefight_log"]}
    for r in efs["firefight_log"]:
        if not r.get("wrote"):
            continue
        k = (r["step"], r["ff"], tuple(r["target"]))
        dr, fr = dry_rows.get(k), f_rows.get(k)
        say("  %4d %-10s %-9s %-7s %-6s %-8s | %s | %s" % (
            r["step"], r["ff"], fmt(r["cell"]), fmt(r["target"]), r["action"], r["scorched"],
            ("dry=%s wrote=%s action=%s" % (dr["dry"], dr["wrote"], dr["action"])) if dr else "MISSING",
            fr.get("wrote") if fr else "MISSING"))
    ext = sum(1 for r in efs["firefight_log"] if r.get("wrote") and r["action"] == "extinguish")
    say("  writes: %d (clear %d, extinguish %d, scorched %d); counters %s; last firefight_log row at step %d" % (
        len(wlist), len(wlist) - ext, ext, sum(1 for r in efs["firefight_log"] if r.get("wrote") and r.get("scorched")),
        efs["firefight_counters"], max(r["step"] for r in efs["firefight_log"])))
    shadow = {tuple(c) for c in (dry.get("firefight_shadow") or [])}
    say("  fmDRY firefight_shadow == set of fmEFS write targets: %s" % (shadow == {c for _s, c in wlist}))
    fw = min(W)
    fdd = first_div(efs["fire_digests"], dry["fire_digests"])
    say("  first write step %d; first fire-digest divergence fmEFS vs fmDRY = step %s, vs fmOFF = step %s;"
        " fmDRY vs fmOFF digests identical %d/240" % (
            fw, fdd, first_div(efs["fire_digests"], off["fire_digests"]),
            sum(a == b for a, b in zip(dry["fire_digests"], off["fire_digests"]))))
    say("  CHECK first divergence == first write step: %s" % ("PASS" if fdd == fw else "FAIL"))
    BD, BE = burning_from_intervals(dry), burning_from_intervals(efs)
    fb = next((t for t in range(1, STEPS + 1) if BD[t] != BE[t]), None)
    say("  but the BURNING set (burn_intervals) first differs only at step %s: steps %d..%d the digest differs in"
        " the fuel field of the cleared cells alone" % (fb, fw, fb - 1))

    # ---------------------------------------------------------------- fire ----
    hdr("2. FIRE DIFFERENCE PROPAGATION")
    snap = tuple(range(66, 121, 3))
    rOFF = replay({})
    rD = replay({}, record=True, snap_ticks=snap)
    rE = replay(W, record=True, snap_ticks=snap)
    say("  2.0 REPLAY VALIDATION (the instrument is used only if all of these pass)")
    say("      origin cell from the seed: %s (recorded burn_intervals has a [1,3) interval at: %s)" % (
        fmt(rOFF["origin"]), [k for k, ivs in off["burn_intervals"].items() for iv in ivs if iv[0] == 1]))
    checks = []
    for name, r, d in (("fmOFF", rOFF, off), ("fmDRY", rD, dry), ("fmEFS", rE, efs), ("fmF", rE, ffF), ("fmFS", rE, ffFS)):
        m = sum(a == b for a, b in zip(r["digests"], d["fire_digests"]))
        checks.append(m == STEPS)
        say("      replay digest == recorded %-6s %d/240" % (name, m))
    for name, r, B in (("fmDRY", rD, BD), ("fmEFS", rE, BE)):
        m = sum(bset(r["burning"][t - 1]) == B[t] for t in range(1, STEPS + 1))
        checks.append(m == STEPS)
        say("      replay burning == recorded burn_intervals %-6s %d/240" % (name, m))
    for name, r, d in (("fmDRY", rD, dry), ("fmEFS", rE, efs)):
        rec = {uid(tuple(map(int, k.split(",")))) for k, v in d["fire_ground_final"].items() if v[1]}
        ok = bset(r["burnt"][-1]) == rec
        checks.append(ok)
        say("      replay burnt@240 == fire_ground_final burnt %-6s %s (%d cells)" % (name, ok, len(rec)))
    say("      every write landed in the replay (precondition true): %s" % all(rE["write_ok"].values()))
    VALID = all(checks)
    say("      REPLAY VALID: %s" % VALID)
    if not VALID:
        say("      replay invalid - every replay-derived statement below is void")

    # 2.1 D(t), loose cone
    say("")
    say("  2.1 D(t) = cells burning in exactly one arm (recorded burn_intervals), per tick")
    first_vis = {}
    for s, c in wlist:
        t1 = (s // 3 + 1) * 3
        first_vis[(s, c)] = t1
    say("      writes are first read by ticks: %s" % sorted(set(first_vis.values())))
    say("      tick |D| DRY-only EFS-only  max_cheb_to_nearest_write  outside_loose_cone  cells (<=8 listed)")
    prev_nonempty = False
    for t in range(3, STEPS + 1, 3):
        Dt = BD[t] ^ BE[t]
        if not Dt and not prev_nonempty and t < 69:
            continue
        prev_nonempty = bool(Dt)
        if t > 90 and t % 15 != 0:
            continue
        outside = 0
        mx = 0
        for u in Dt:
            cu = cell(u)
            dmin = min(cheb(cu, c) for _s, c in wlist)
            mx = max(mx, dmin)
            if not any(t >= first_vis[(s, c)] and cheb(cu, c) <= t - first_vis[(s, c)] for s, c in wlist):
                outside += 1
        lst = " ".join(fmt(cell(u)) + ("D" if u in BD[t] else "E") for u in sorted(Dt)) if len(Dt) <= 8 else ""
        say("      %4d %4d %8d %8d  %25s  %18d  %s" % (t, len(Dt), len(Dt & BD[t]), len(Dt & BE[t]),
                                                     mx if Dt else "-", outside, lst))
    say("      (D is empty on every tick before %d; rows after 90 are every 15th tick.)" % fb)
    cover = next(t for t in range(3, STEPS + 1, 3)
                 if all(any(t >= first_vis[(s, c)] and cheb(cell(u), c) <= t - first_vis[(s, c)] for s, c in wlist)
                        for u in range(N * N)))
    say("      The loose cone (3 cells per tick since the write) covers all 2500 cells from tick %d on, so after"
        " that it cannot flag anything - hence the tight test in 2.3." % cover)
    for name, d in (("fmDRY", dry), ("fmEFS", efs)):
        bad = [(k, iv) for k, ivs in d["burn_intervals"].items() for iv in ivs
               if (iv[0] % 3 and iv[0] != 1) or (iv[1] is not None and iv[1] % 3)]
        say("      fire ticks are steps divisible by 3: %s burn_interval bounds off a multiple of 3 (origin's start"
            " 1 excepted): %d" % (name, len(bad)))
    chain = sorted({u for t in range(69, 82, 3) for u in (BD[t] ^ BE[t])})
    say("      cells in D on ticks 69..81 and their burn intervals (D=fmDRY, E=fmEFS):")
    for u in chain:
        k = "%d,%d" % cell(u)
        say("        %-8s written? %-5s  D %s  E %s" % (fmt(cell(u)), cell(u) in {c for _s, c in wlist},
                                                      dry["burn_intervals"].get(k), efs["burn_intervals"].get(k)))
    for c in sorted({c for _s, c in wlist}):
        k = "%d,%d" % c
        say("        write %-8s D %s  E %s" % (fmt(c), dry["burn_intervals"].get(k), efs["burn_intervals"].get(k)))

    # 2.2 drawing sets from recorded data only
    say("")
    say("  2.2 RNG STREAM SHIFT, from recorded data alone (burn_intervals + fire_ground_final)")
    tb = {}
    for name, d in (("fmDRY", dry), ("fmEFS", efs)):
        ends, badfuel = {}, 0
        for k, v in d["fire_ground_final"].items():
            if not v[1]:
                continue
            ivs = d["burn_intervals"][k]
            ticks = sum(((b - (0 if a == 1 else a)) // 3) for a, b in ivs)
            if not (7 <= ticks <= 10):
                badfuel += 1
            ends[uid(tuple(map(int, k.split(","))))] = ivs[-1][1]
        tb[name] = ends
        say("      %s: %d burnt cells; burning-tick count outside fuel range 7..10: %d" % (name, len(ends), badfuel))
    shift_tick, shift_cells = None, None
    for t in range(3, STEPS + 1, 3):
        da = {u for u in range(N * N) if not (u in tb["fmDRY"] and tb["fmDRY"][u] < t)}
        de = {u for u in range(N * N) if not (u in tb["fmEFS"] and tb["fmEFS"][u] < t)}
        if da != de:
            shift_tick = t
            shift_cells = (sorted(da - de), sorted(de - da))
            break
    say("      first tick whose drawing set differs: %s; drawing only in fmDRY: %s; only in fmEFS: %s" % (
        shift_tick, [fmt(cell(u)) for u in shift_cells[0]], [fmt(cell(u)) for u in shift_cells[1]]))
    rep_shift = next((t for t in range(3, STEPS + 1, 3)
                      if [g is None for g in rD["draws"][t]] != [g is None for g in rE["draws"][t]]), None)
    say("      replay agrees: first drawing-set difference at tick %s" % rep_shift)
    su = (shift_cells[0] + shift_cells[1])[0]
    say("      => at tick %d fmEFS draws ONE extra number, at unique id %d %s; every cell after it in id order"
        " at that tick, and every cell at every later tick, reads a different number" % (shift_tick, su, fmt(cell(su))))
    for t in (shift_tick, shift_tick + 3):
        live = [u for u in range(N * N) if rD["probs"][t][u] > 0 or rE["probs"][t][u] > 0]
        rer = [u for u in live if rD["draws"][t][u] != rE["draws"][t][u]]
        say("      tick %d: cells with nonzero ignition probability in either arm %d, of which given a different"
            " random number %d" % (t, len(live), len(rer)))
    say("      cleared cells (fuel 0, never burned) keep drawing in fmEFS on every tick: %s" % all(
        rE["draws"][t][uid(c)] is not None for t in range(12, STEPS + 1, 3) for _s, c in wlist))

    # 2.3 tight test
    say("")
    say("  2.3 TIGHT TEST of each D cell (PHYS = own or radius-3 neighbourhood state entering the tick differs;"
        " DRAW = its random number differs)")
    rows = []
    for t in snap:
        Dt = bset(rD["burning"][t - 1]) ^ bset(rE["burning"][t - 1])
        sd, se = rD["snap"][t], rE["snap"][t]
        diff_state = {u for u in range(N * N) if (sd[0][u], sd[1][u], sd[2][u]) != (se[0][u], se[1][u], se[2][u])}
        cnt = collections.Counter()
        near_ids = []
        for u in Dt:
            phys = u in diff_state or any(v in diff_state for v in NB_ALL[u])
            drw = rD["draws"][t][u] != rE["draws"][t][u]
            cls = "phys" if phys and not drw else "reroll" if drw and not phys else "both" if phys else "NEITHER"
            cnt[cls] += 1
            if cls != "reroll":
                near_ids.append(u)
        rows.append((t, len(Dt), cnt, near_ids))
        if Dt:
            say("      tick %3d |D| %3d  phys-only %3d  reroll-only %3d  both %3d  NEITHER %d%s" % (
                t, len(Dt), cnt["phys"], cnt["reroll"], cnt["both"], cnt["NEITHER"],
                ("   non-reroll cells: " + " ".join(fmt(cell(u)) for u in sorted(near_ids))) if len(near_ids) <= 10 else ""))
    t84 = shift_tick
    D84 = bset(rD["burning"][t84 - 1]) ^ bset(rE["burning"][t84 - 1])
    low = [u for u in D84 if u < su]
    hi_same = [u for u in range(su + 1, N * N) if rD["draws"][t84][u] is not None
               and rE["draws"][t84][u] is not None and rD["draws"][t84][u] == rE["draws"][t84][u]]
    lo_diff = [u for u in range(0, su) if rD["draws"][t84][u] != rE["draws"][t84][u]]
    say("      tick %d: cells with id < %d whose number differs: %d; drawing cells with id > %d whose number is the"
        " same: %d; D cells with id < %d: %d (only a physical cause could put one there)" % (
            t84, su, len(lo_diff), su, len(hi_same), su, len(low)))
    say("      NEITHER must be 0 on every tick (a difference with no physical and no draw cause would falsify the"
        " model of the fire): %s" % all(r[2]["NEITHER"] == 0 for r in rows))

    # 2.4 physical-only counterfactual
    say("")
    say("  2.4 PHYSICAL-ONLY COUNTERFACTUAL: fmEFS's writes, but each cell reads the SAME random number it read in"
        " fmDRY at that tick (the stream shift removed)")
    say("      a cell that is burnt in fmDRY but still drawing here has no fmDRY number; it gets g=1-1e-6 (never"
        " ignites) in run A and g=0 (ignites whenever its probability is > 0) in run B - the two bound it")
    phys = {}
    for tagname, gfb in (("A", 1 - 1e-6), ("B", 0.0)):
        fb_live = []

        def ov(u, t, g, gfb=gfb, fb_live=fb_live):
            v = rD["draws"][t][u]
            if v is None:
                fb_live.append((t, u))
                return gfb
            return v
        rp = replay(W, draw_override=ov)
        phys[tagname] = rp
        ticks = [(t, bset(rp["burning"][t - 1]) ^ bset(rD["burning"][t - 1])) for t in range(3, STEPS + 1, 3)]
        nz = [(t, s) for t, s in ticks if s]
        allu = set().union(*[s for _t, s in nz]) if nz else set()
        xs = [cell(u) for u in allu]
        say("      run %s: ticks with a difference %d, max |D| %d, union %d cells spanning x %s..%s y %s..%s;"
            " fallback draws used %d; first difference tick %s" % (
                tagname, len(nz), max((len(s) for _t, s in nz), default=0), len(allu),
                min(c[0] for c in xs), max(c[0] for c in xs), min(c[1] for c in xs), max(c[1] for c in xs),
                len(fb_live), nz[0][0] if nz else None))
    say("      for comparison fmEFS vs fmDRY (recorded): max |D| %d, union %d cells spanning x %s..%s y %s..%s" % (
        max(len(BD[t] ^ BE[t]) for t in range(1, STEPS + 1)),
        len(set().union(*[BD[t] ^ BE[t] for t in range(1, STEPS + 1)])),
        min(cell(u)[0] for t in range(1, STEPS + 1) for u in BD[t] ^ BE[t]),
        max(cell(u)[0] for t in range(1, STEPS + 1) for u in BD[t] ^ BE[t]),
        min(cell(u)[1] for t in range(1, STEPS + 1) for u in BD[t] ^ BE[t]),
        max(cell(u)[1] for t in range(1, STEPS + 1) for u in BD[t] ^ BE[t])))

    # proximity of D to agents
    say("")
    say("  2.5 CLOSEST APPROACH of a fire difference to each agent (manhattan; agent position from the named arm,"
        " difference at the same step; format distance@step)")
    ents = [("victim_0", "victim_steps"), ("victim_2", "victim_steps"), ("victim_3", "victim_steps"),
            ("ff_unit_0", "ff_steps")]
    APPROACH = {}
    for ent, key in ents:
        parts = []
        for dname, dd in (("fmDRY", dry), ("fmEFS", efs)):
            s = pos_series(dd, key, ent)
            for label, getD in (("recorded", lambda t: BD[t] ^ BE[t]),
                                ("physA", lambda t: bset(phys["A"]["burning"][t - 1]) ^ bset(rD["burning"][t - 1])),
                                ("physB", lambda t: bset(phys["B"]["burning"][t - 1]) ^ bset(rD["burning"][t - 1]))):
                best = (999, None)
                for t in range(1, STEPS + 1):
                    p = s[t][1]
                    if p is None or s[t][2] in ("dead", "rescued") or (key == "ff_steps" and s[t][5]):
                        continue
                    Dt = getD(t)
                    if not Dt:
                        continue
                    m = min(manh(p, cell(u)) for u in Dt)
                    if m < best[0]:
                        best = (m, t)
                parts.append("%s/%s %s@%s" % (dname[2:], label, best[0], best[1]))
                APPROACH[(ent, dname, label)] = best
        say("      %-9s %s" % (ent, "  ".join(parts)))
    say("      (flee trigger distance is %d manhattan; a physical-only difference that never comes within ~%d of an"
        " agent cannot have changed its decisions)" % (FLEE_TRIGGER, FLEE_TRIGGER + 1))

    # ----------------------------------------------------------- timelines ----
    hdr("3. AGENT TIMELINES")
    say("  3.1 FIRST DIVERGENCE fmEFS vs fmDRY, per record and per entity")
    say("      fire digest %s | burning set %s | drawing set (re-roll) tick %s" % (fdd, fb, shift_tick))
    for key in ("uav_actions", "ff_steps", "victim_steps", "uav_steps", "ff_bind_steps"):
        res = {}
        for i, (ra, rb) in enumerate(zip(efs[key], dry[key])):
            ma, mb = {r[0]: r for r in ra}, {r[0]: r for r in rb}
            for k in set(ma) | set(mb):
                if k not in res and ma.get(k) != mb.get(k):
                    res[k] = (i + 1, ma.get(k), mb.get(k))
        for k, (t, a, b) in sorted(res.items(), key=lambda kv: kv[1][0]):
            say("      %-13s %-10s step %3d  EFS %s  DRY %s" % (key, k, t, a[1:], b[1:]))
    pa, pb = efs["planner"], dry["planner"]
    i = next((i for i, (x, y) in enumerate(zip(pa, pb)) if x != y), None)
    say("      planner: entries identical up to index %s; first differing entry EFS %s / DRY %s" % (
        i, {k: pa[i][k] for k in ("step", "reason", "action", "vid", "ff")},
        {k: pb[i][k] for k in ("step", "reason", "action", "vid", "ff")}))
    for key in ("assigns", "unassigns", "exit_starts", "completions"):
        j = next((j for j, (x, y) in enumerate(zip(efs[key], dry[key])) if x != y), None)
        say("      %-11s first differing entry index %s (EFS %s | DRY %s)" % (
            key, j, efs[key][j] if j is not None and j < len(efs[key]) else None,
            dry[key][j] if j is not None and j < len(dry[key]) else None))
    ffd = first_div(efs["ff_steps"], dry["ff_steps"])
    say("      CHECK units' positions identical before the burning sets differ (DRY emulates the writes with a"
        " shadow set): ff_steps identical through step %d; burning first differs at %d; re-roll at %d -> %s" % (
            ffd - 1, fb, shift_tick, "PASS (and identical beyond, until 2 steps after the re-roll)" if ffd > fb else "FAIL"))

    say("")
    say("  3.2 WHAT EACH AGENT SAW AT ITS FIRST DIVERGENCE (differing burning cells within manhattan %d of its"
        " position, and whether each is a re-rolled draw or physical, by the tight test)" % (FLEE_TRIGGER + 2))

    def classify(t, u):
        if t % 3 != 0 or t not in rD["snap"]:
            return "?"
        sd, se = rD["snap"][t], rE["snap"][t]
        diff_state = lambda v: (sd[0][v], sd[1][v], sd[2][v]) != (se[0][v], se[1][v], se[2][v])  # noqa: E731
        ph = diff_state(u) or any(diff_state(v) for v in NB_ALL[u])
        dr_ = rD["draws"][t][u] != rE["draws"][t][u]
        return "phys" if ph and not dr_ else "reroll" if dr_ and not ph else "both" if ph else "NEITHER"

    say("      (for the UAV the radius is its recorded fire distance + 1, since that field is what changed)")
    div_cls = {}
    for ent, key, t in (("uav 2503", None, 84), ("ff_unit_0", "ff_steps", 86), ("victim_2", "victim_steps", 87),
                        ("victim_3", "victim_steps", 90), ("victim_0", "victim_steps", 97)):
        if key is None:
            p = next(r[1] for r in dry["uav_steps"][t - 1] if r[0] == "2503")
            radius = max(next(r[5] for r in dry["uav_actions"][t - 1] if r[0] == "2503"),
                         next(r[5] for r in efs["uav_actions"][t - 1] if r[0] == "2503")) + 1
        else:
            p = pos_series(dry, key, ent)[t - 1][1]
            radius = FLEE_TRIGGER + 2
        tick = t - (t % 3)
        near = sorted(u for u in (BD[tick] ^ BE[tick]) if manh(p, cell(u)) <= radius)
        cl = [classify(tick, u) for u in near]
        div_cls[ent] = collections.Counter(cl)
        pdist = [min((manh(p, cell(u)) for u in (bset(phys[g]["burning"][tick - 1]) ^ bset(rD["burning"][tick - 1]))),
                     default=None) for g in ("A", "B")]
        say("      %-9s diverges at step %3d from common cell %s; D within %d at tick %d: %s | classes %s |"
            " physical-only difference at that tick: nearest %s (A) / %s (B)" % (
                ent, t, fmt(p), radius, tick,
                " ".join("%s%s:%s" % (fmt(cell(u)), "D" if u in BD[tick] else "E", c) for u, c in zip(near, cl)) or "none",
                dict(div_cls[ent]), "none" if pdist[0] is None else pdist[0], "none" if pdist[1] is None else pdist[1]))
    say("      'both' = the cell's number was re-rolled AND its neighbourhood state already differs - and that"
        " neighbourhood difference is itself a product of the tick-84/87 re-rolls (2.3: no phys-only cell exists"
        " outside the band region on ticks 84-87)")

    for vid in ("victim_2",):
        say("")
        say("  3.3 VICTIM_2 TIMELINE")
        for a in ("fmOFF", "fmDRY", "fmEFS"):
            d = D[a]
            say("    %s" % a)
            say("      status segments: %s" % " ".join("%d-%d:%s" % s for s in status_segments(d, "victim_steps", vid, 2)))
            segs = segments(pos_series(d, "victim_steps", vid), lambda r: tuple(r[1]) if r[1] else None)
            say("      position segments: %s" % " ".join("%d-%d:%s" % (a_, b_, fmt(v) if v else "-") for a_, b_, v in segs))
            fl = [r for r in d["victim_flee_log"] if r["victim_id"] == vid]
            say("      flee moves %d: %s" % (len(fl), " ".join("%d:%s>%s(d%d>%d)" % (r["step"], fmt(r["from"]), fmt(r["to"]),
                                                                             r["fire_dist_before"], r["fire_dist_after"]) for r in fl)))
            ho = [r for r in d["victim_holds"] if r.get("victim") == vid]
            say("      holds %d by reason %s, steps %s..%s" % (len(ho), dict(collections.Counter(r["reason"] for r in ho)),
                                                         ho[0]["step"] if ho else "-", ho[-1]["step"] if ho else "-"))
            say("      assigns: %s" % [(x["step"], x["ff"], x["reason"], x["ok"]) for x in d["assigns"] if x["vid"] == vid])
            say("      unassigns: %s" % [(x["step"], x["ff"], x["reason"], x["ok"]) for x in d["unassigns"] if x["vid"] == vid])
            say("      exit_starts: %s" % [(x["step"], x["ff"], x["ff_pos"], x["victim_pos"], x["contact"]) for x in d["exit_starts"] if x["victim"] == vid])
            say("      completions: %s" % [(x["step"], x["ff"], x["pos"]) for x in d["completions"] if x["victim"] == vid])
            rt = [x for x in d["retargets"] if x["victim"] == vid]
            say("      retargets on victim_2: %d %s" % (len(rt), [(x["step"], x["ff"], x["to"]) for x in rt]))
            # rescuer path per assignment window
            ok_as = [x for x in d["assigns"] if x["vid"] == vid and x["ok"]]
            for x in ok_as:
                ends = [u["step"] for u in d["unassigns"] if u["vid"] == vid and u["ff"] == x["ff"] and u["step"] > x["step"]]
                ends += [c["step"] for c in d["completions"] if c["victim"] == vid and c["ff"] == x["ff"] and c["step"] >= x["step"]]
                later = [y["step"] for y in ok_as if y["step"] > x["step"]]
                end = min(ends + later + [STEPS])
                s = pos_series(d, "ff_steps", x["ff"])
                p0 = s[x["step"]][1]
                vpos = pos_series(d, "victim_steps", vid)[x["step"]][1]
                say("      rescuer %s path, assign step %d -> %d (unit at %s, victim at %s, manhattan %s, steps left to %d: %d):" % (
                    x["ff"], x["step"], end, fmt(p0), fmt(vpos), manh(p0, vpos) if p0 and vpos else "-", STEPS, STEPS - x["step"]))
                print_tokens(path_tokens(d, "ff_steps", x["ff"], x["step"], end))
            say("      hold steps: %s" % " ".join(str(r["step"]) for r in ho))
            B = burning_from_intervals(d)
            vs = pos_series(d, "victim_steps", vid)
            say("      nearest burning cell (manhattan) every 10 steps from 80: %s" % " ".join(
                "%d:%s" % (t, min((manh(vs[t][1], cell(u)) for u in B[t]), default="-") if vs[t][1] else "-")
                for t in range(80, STEPS + 1, 10)))
            on_fire =[t for t in range(1, STEPS + 1) if vs[t][1] and vs[t][2] not in ("rescued", "dead") and uid(vs[t][1]) in B[t]]
            last_alive = max(t for t in range(1, STEPS + 1) if vs[t][1] is not None)
            p = vs[last_alive][1]
            md = min((manh(p, cell(u)) for u in B[last_alive]), default=None)
            say("      steps standing on a burning cell while alive: %s; last on-grid step %d at %s, status %s,"
                " nearest burning cell then %s" % (on_fire or "none", last_alive, fmt(p), vs[last_alive][2], md))
        say("      victim_2 DEATH: does not die in any of these arms (OFF rescued, DRY rescued, EFS alive and"
            " unresolved at 240). The loss is a rescue not completed by the horizon, not a death.")

    say("")
    say("  3.4 VICTIM_0 AND VICTIM_3, DRY vs EFS (the victims whose fates differ)")
    for vid in ("victim_0", "victim_3"):
        for a in ("fmOFF", "fmDRY", "fmEFS"):
            d = D[a]
            segs = segments(pos_series(d, "victim_steps", vid), lambda r: tuple(r[1]) if r[1] else None)
            st = status_segments(d, "victim_steps", vid, 2)
            fv = final_victims(d)[vid]
            B = burning_from_intervals(d)
            extra = ""
            if fv["final"] == "dead":
                t = fv["term_step"]
                c = pos_series(d, "victim_steps", vid)[t][1]
                nbs = [(c[0] + ox, c[1] + oy) for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if 0 <= c[0] + ox < N and 0 <= c[1] + oy < N]
                extra = " | death step %d at %s, own cell burning %s, burning 4-neighbours %d/%d" % (
                    t, fmt(c), uid(c) in B[t], sum(uid(n) in B[t] for n in nbs), len(nbs))
            say("    %-8s %-6s status %s%s" % (vid, a, " ".join("%d-%d:%s" % s for s in st), extra))
            say("             positions %s" % " ".join("%d-%d:%s" % (x, y, fmt(v) if v else "-") for x, y, v in segs))

    say("")
    say("  3.5 FF_UNIT_0 (the only unit alive after step 72 in fmDRY and fmEFS)")
    for a in ("fmDRY", "fmEFS"):
        d = D[a]
        say("    %s status: %s" % (a, " ".join("%d-%d:%s" % s for s in status_segments(d, "ff_steps", "ff_unit_0", 2))))
        s = pos_series(d, "ff_steps", "ff_unit_0")
        jumps = [(t, s[t - 1][1], s[t][1]) for t in range(2, STEPS + 1)
                 if s[t][1] and s[t - 1][1] and manh(s[t][1], s[t - 1][1]) > 1]
        say("      on-grid moves longer than 1 cell per step: %s" % (jumps or "none"))
        say("      binding: %s" % " ".join("%d-%d:%s" % tuple(x) for x in segments(pos_series(d, "ff_bind_steps", "ff_unit_0"), lambda r: r[1] or "-")))
        say("      path steps 71..%d (victim_0 window):" % (162 if a == "fmDRY" else 210))
        print_tokens(path_tokens(d, "ff_steps", "ff_unit_0", 71, 162 if a == "fmDRY" else 210))
    s1d, s1e = pos_series(dry, "ff_steps", "ff_unit_1"), pos_series(efs, "ff_steps", "ff_unit_1")
    dd1 = ff_deaths(efs)["ff_unit_1"]
    say("    ff_unit_1 rows identical fmDRY vs fmEFS on all 240 steps: %s (dies at step %d at %s)" % (
        all(s1d[t] == s1e[t] for t in range(1, STEPS + 1)), dd1[0], fmt(dd1[1])))
    for a in ("fmDRY", "fmEFS"):
        say("    %s unit status at 240: %s" % (a, [(r[0], r[2]) for r in D[a]["ff_steps"][-1]]))

    # ------------------------------------------------------------- chain ----
    hdr("4. CAUSAL CHAIN FROM THE WRITES TO THE LOST RESCUE")
    vd0, ve0 = final_victims(dry)["victim_0"], final_victims(efs)["victim_0"]
    a_dry = next(x for x in dry["assigns"] if x["vid"] == "victim_2" and x["ok"] and x["step"] > 100)
    a_efs = next(x for x in efs["assigns"] if x["vid"] == "victim_2" and x["ok"] and x["step"] > 100)
    pd = pos_series(dry, "ff_steps", "ff_unit_0")[a_dry["step"]][1]
    pe = pos_series(efs, "ff_steps", "ff_unit_0")[a_efs["step"]][1]
    vd = pos_series(dry, "victim_steps", "victim_2")[a_dry["step"]][1]
    ve = pos_series(efs, "victim_steps", "victim_2")[a_efs["step"]][1]
    cd = next(c for c in dry["completions"] if c["victim"] == "victim_2")
    say("  (a) WRITES: %d firebreak clears on steps %d..%d, 0 extinguishes, all on never-burned cells in the band"
        " around x 6..9, y 40..43." % (len(wlist), min(W), max(W)))
    say("  (b) PHYSICAL EFFECT, ticks %d..%d: at most %d cells burn differently at once, all within Chebyshev %d of"
        " a written cell (2.1). The written cell (7,40) does not ignite at tick 69; the difference walks"
        " (7,37)/(8,40) -> (8,37) -> (8,35)." % (fb, shift_tick - 3,
                                                  max(len(BD[t] ^ BE[t]) for t in range(fb, shift_tick)),
                                                  max(min(cheb(cell(u), c) for _s, c in wlist)
                                                      for t in range(fb, shift_tick) for u in BD[t] ^ BE[t])))
    k35 = "%d,%d" % cell(su)
    say("  (c) BURN-OUT TIMING CHANGE: %s does not re-ignite at tick %d in fmEFS (fmDRY %s, fmEFS %s). It is burnt"
        " in fmDRY at tick %d but keeps one unit of fuel in fmEFS, and fmEFS only burns it out later." % (
            fmt(cell(su)), shift_tick - 6, dry["burn_intervals"][k35], efs["burn_intervals"][k35], shift_tick - 3))
    say("  (d) RNG RE-ROLL at tick %d: fmEFS draws one extra number at id %d; %d cells with a nonzero ignition"
        " probability get a different number on that tick alone, and D jumps from 0 to %d cells, up to Chebyshev"
        " %d from the writes (2.1-2.3). From here the two runs are different fire realisations." % (
            shift_tick, su,
            len([u for u in range(N * N) if (rD["probs"][shift_tick][u] > 0 or rE["probs"][shift_tick][u] > 0)
                 and rD["draws"][shift_tick][u] != rE["draws"][shift_tick][u]]),
            len(BD[shift_tick] ^ BE[shift_tick]),
            max(min(cheb(cell(u), c) for _s, c in wlist) for u in BD[shift_tick] ^ BE[shift_tick])))
    say("      The physical effect alone (2.4) stays in x 0..10, y 32..49. Its closest approach on the fmDRY"
        " trajectories: victim_0 %s, victim_3 %s, ff_unit_0 %s, victim_2 %s (manhattan@step, 2.5)." % tuple(
            "%s@%s" % APPROACH[(e, "fmDRY", "physA")] for e in ("victim_0", "victim_3", "ff_unit_0", "victim_2")))
    say("  (e) AGENTS DIVERGE ONLY AFTER THE RE-ROLL, all on or after tick %d (3.1):" % shift_tick)
    say("      - UAV fire distances at 84")
    say("      - ff_unit_0's route at %d" % ffd)
    say("      - victim_2 holds instead of fleeing at 87 (its own cell (0,30) burns in fmDRY only)")
    say("      - victim_3 at 90, victim_0 at 97")
    say("      Classes of the nearby differing cells (3.2):")
    say("      - ff_unit_0 %s, victim_2 %s: pure re-rolls" % (dict(div_cls["ff_unit_0"]), dict(div_cls["victim_2"])))
    say("      - victim_3 %s, victim_0 %s: 'both', re-rolled numbers on neighbourhoods the earlier re-rolls had"
        " already changed" % (dict(div_cls["victim_3"]), dict(div_cls["victim_0"])))
    say("      The physical-only difference is empty on ticks %s." % ",".join(
        str(t) for t in range(81, 99, 3) if not (bset(phys["A"]["burning"][t - 1]) ^ bset(rD["burning"][t - 1]))))
    say("  (f) VICTIM_0 SURVIVES LONGER: fmDRY victim_0 dies step %s at %s (same step and cell as fmOFF); fmEFS"
        " victim_0 flees along the x=49 edge toward higher y and dies step %s at %s." % (
            vd0["term_step"], fmt(vd0["term_cell"]), ve0["term_step"], fmt(ve0["term_cell"])))
    say("  (g) THE ONLY LIVING UNIT IS FREED %d STEPS LATER: ff_unit_0 has held victim_0 since step 71 in both arms"
        " (ff_unit_1 died at 72 in both). fmDRY: reassigned to victim_2 at %d from %s, victim_2 at %s, manhattan"
        " %d; contact at %s, completion at %d." % (
            a_efs["step"] - a_dry["step"], a_dry["step"], fmt(pd), fmt(vd), manh(pd, vd),
            next(x["step"] for x in dry["exit_starts"] if x["victim"] == "victim_2"), cd["step"]))
    say("      fmEFS: reassigned at %d from %s, victim_2 at %s, manhattan %d > the %d steps left, with at most 1"
        " cell per step (3.5). The rescue cannot finish by 240, and victim_2 is unresolved at the horizon." % (
            a_efs["step"], fmt(pe), fmt(ve), manh(pe, ve), STEPS - a_efs["step"]))
    say("  (h) SIDE EFFECT OF THE SAME REALISATION: victim_3 dies at step %s in fmEFS; in fmDRY it is alive and"
        " unrescued at 240. That is the +1 dead." % final_victims(efs)["victim_3"]["term_step"])
    say("  VERDICT among (i)-(iv): (iii). An RNG re-roll triggered by a burn-out timing change produced an unrelated"
        " fire difference, and that difference reached the agents.")
    say("    (i)  NO:")
    say("         - the physical-only difference is empty on the ticks where the agents first diverge")
    say("         - it never comes closer than %s to victim_0, %s to victim_3 or %s to ff_unit_0 on either"
        " trajectory" % tuple("%d" % min(APPROACH[(e, a_, "physA")][0], APPROACH[(e, a_, "physB")][0])
                             for e in ("victim_0", "victim_3", "ff_unit_0") for a_ in ("fmDRY",)))
    say("         - victim_2: %d on its fmDRY path. On its fmEFS path it comes to %d at step %d, but by then"
        " victim_2 had been standing still at (0,31) since step 93, in a position that exists only because of"
        " the re-roll" % (APPROACH[("victim_2", "fmDRY", "physA")][0], APPROACH[("victim_2", "fmEFS", "physA")][0],
                           APPROACH[("victim_2", "fmEFS", "physA")][1]))
    say("    (ii) NO:")
    say("         - ff_steps (positions and route_blocked status) are identical through step %d" % (ffd - 1))
    say("         - planner, assigns and unassigns are identical until the step-%d entry (3.1)" % pb[i]["step"])
    say("         - the two route_blocked replacements before that (58, 71) occur identically in both arms")
    say("    (iv) NO as a cause: dispatch follows unchanged rules on changed inputs.")
    say("         - The first dispatch difference (step %d) is a route-block of ff_unit_0 on its way to victim_0"
        " that happens in fmDRY and not in fmEFS, because fire and victim_0 are already different there." % pb[i]["step"])
    say("         - From 162 on, the difference is that victim_0 is still alive in fmEFS (f).")
    say("  WHERE IT BECOMES UNKNOWABLE FROM RECORDED DATA")
    say("    - The chain (a)-(e) is exact: replay-validated, down to the draw.")
    say("    - After tick %d the fire is a new realisation of %d+ differing cells. Recorded data cannot say which"
        " of them sent victim_0 along the edge toward higher y (fmEFS, from step 147) instead of lower y (fmDRY,"
        " from 141), or left ff_unit_0's route open at 150 (blocked in fmDRY). There is no single cause, and no"
        " counterfactual agent run exists (3.4, 3.5)." % (shift_tick, len(BD[shift_tick] ^ BE[shift_tick])))
    say("    - Whether the physical firebreak alone (no re-roll) would change any rescue: the 2.4 fire is exact,"
        " but its closed-loop run does not exist. Given the distances above an effect is implausible, but it is"
        " not measured.")
    say("    - Whether victim_2 would be rescued in fmEFS after 240: horizon-truncated, not recorded.")

    # ------------------------------------------------------ route_blocked ----
    hdr("5. RELATION TO THE ROUTE_BLOCKED GATE")
    for a in ("fmOFF", "fmDRY", "fmEFS"):
        d = D[a]
        eps = []
        for ff in ("ff_unit_0", "ff_unit_1"):
            for x, y, v in status_segments(d, "ff_steps", ff, 2):
                if v == "route_blocked":
                    eps.append("%s %d-%d@%s" % (ff[-1], x, y, fmt(pos_series(d, "ff_steps", ff)[x][1])))
        say("  %-6s rescue_event route_blocked=%s; replacement/casualty unassigns %s; route_blocked status episodes"
            " (unit start-end@cell) %s" % (a, d["rescue_event_counts"].get("route_blocked"),
                                           [(x["step"], x["ff"][-1], x["vid"][-1], x["reason"]) for x in d["unassigns"]],
                                           eps or "none (flag cleared within the step)"))
    for g, h in (("fmgOFF", "fmOFF"), ("fmgEFS", "fmEFS"), ("fmgFB", "fmF")):
        rec = next(e for e in GATE[g]["evals"] if e.get("seed") == SEED)
        same = {k: v for k, v in rec.items() if k not in ("seed", "wall_s")} == D[h]["eval"]
        fires = [(x["step"], x["ff"][-1], x["pos"]) for x in GATE[g]["exact_fires"] if x.get("seed") == SEED]
        say("  gate %-6s seed 404: rescued %s dead %s ff_deaths %s terminal %s; eval == harness %s: %s;"
            " exact route_blocked fires %s" % (g, rec["rescued"], rec["dead"], rec["firefighter_deaths"],
                                               rec["terminal_step"], h, same, fires))
    fo, fdv, fe = final_victims(off), final_victims(dry), final_victims(efs)
    say("  per victim OFF -> DRY -> EFS: " + "; ".join("%s %s->%s->%s" % (v, fo[v]["final"], fdv[v]["final"], fe[v]["final"])
                                                      for v in sorted(fo)))
    for g in ("fmgOFF", "fmgEFS", "fmgFB"):
        lat = [x for x in (GATE[g].get("latched") or []) if isinstance(x, dict) and x.get("seed") == SEED]
        dth = [x for x in (GATE[g].get("deaths") or []) if isinstance(x, dict) and x.get("seed") == SEED]
        say("  gate %-6s seed 404 latched entries %s; unit deaths %s" % (g, lat or "none", dth or "none"))
    say("  READING:")
    say("  - The gate's south/404 deepening 3 -> 1 (fmgOFF -> fmgEFS/fmgFB) is this same run: the gate eval"
        " records equal the harness evals.")
    say("  - It splits into two separate losses.")
    say("    - Positioning, present identically in fmDRY: victim_3 is not rescued, where fmOFF rescues it at 189."
        " ff_unit_1 is assigned victim_3 at step 14 while engaged at the band, is route-blocked at 58 and dies"
        " at 72. The single remaining unit never reaches victim_3 by 240.")
    say("    - Fire writes: victim_2, through the re-roll chain of section 4. The same realisation also kills"
        " victim_3 (dead +1).")
    say("  - Neither loss is a route_blocked mechanism or a new latch.")
    say("    - fmEFS's route_blocked events: 58 (ff_unit_1) and 71 (ff_unit_0, whose route to victim_2 is"
        " blocked, so it is given victim_0) happen at the same steps and cells in fmDRY.")
    say("    - fmOFF has the same kind of block on the route to victim_2 at 69 (ff_unit_1 at (13,40)).")
    say("    - The third fmEFS event, 210, is victim_0 enclosed as it dies.")
    say("    - No unit is route_blocked at 240.")
    say("  - What the route_blocked replacement at 71 does in DRY/EFS is put the last living unit on victim_0"
        " while victim_2 waits.")
    say("    - Under the lowest-id rule with one unit, victim_2's rescue cannot start before victim_0 is resolved."
        " fmDRY even re-assigns victim_0 to the same unit after its block at 150.")
    say("    - The re-rolled fire moved victim_0's resolution from 162 to 210, and the crossing (41 and 45 cells)"
        " then decides whether the 240 horizon is met.")
    say("  - The known four-seed route_blocked regression on this seed (ihrest 4 -> fmgOFF 3) is quoted from"
        " outputs/_firemech_rbgate.txt, not re-derived here.")

    # ----------------------------------------------------------- bisection ----
    hdr("6. CLOSED-LOOP BISECTION WITH FM2P_WRITE_BEFORE=s")
    say("  Premise check: every prefix variant's burning AND burnt sets equal fmDRY's through step 68. Units'"
        " decisions on steps <= 16 (the last firefight_log row) read only burning/burnt/smoke and the fuel set"
        " minus the shadow, whose union is the same in every variant. So a prefix run makes exactly fmEFS's writes"
        " on steps < s.")
    variants = []
    for s in range(9, 18):
        wr = {st: cs for st, cs in W.items() if st < s}
        variants.append(("s=%d" % s, wr))
    extra = [("steps<13 + (7,40)@13", {**{st: cs for st, cs in W.items() if st < 13}, 13: [(7, 40)]}),
             ("steps<13 + (8,43)@13", {**{st: cs for st, cs in W.items() if st < 13}, 13: [(8, 43)]})]
    for st, c in wlist:
        extra.append(("only %s@%d" % (fmt(c), st), {st: [c]}))
    for st, c in wlist:
        wr = collections.defaultdict(list)
        for s2, c2 in wlist:
            if (s2, c2) != (st, c):
                wr[s2].append(c2)
        extra.append(("all but %s@%d" % (fmt(c), st), dict(wr)))

    def drawset_div(ra, rb):
        return next((t for t in range(3, STEPS + 1, 3) if [g is None for g in ra["draws"][t]] != [g is None for g in rb["draws"][t]]), None)

    say("  variant                 writes | vs fmDRY: burning burnt reroll | vs fmEFS: burning burnt reroll | class")
    premise = True
    table = {}
    for name, wr in variants + extra:
        r = replay(wr, record=True)
        bdiv_d = first_div(r["burning"], rD["burning"])
        tdiv_d = first_div(r["burnt"], rD["burnt"])
        bdiv_e = first_div(r["burning"], rE["burning"])
        tdiv_e = first_div(r["burnt"], rE["burnt"])
        if min(x for x in (bdiv_d, tdiv_d, 999) if x is not None) < 69:
            premise = False
        cls = ("== fmDRY fire" if bdiv_d is None and tdiv_d is None else
               "== fmEFS fire" if bdiv_e is None and tdiv_e is None else "third realisation")
        table[name] = (bdiv_d, tdiv_d, bdiv_e, tdiv_e, cls)
        say("  %-22s %6d | %9s %5s %6s | %9s %5s %6s | %s" % (
            name, sum(len(v) for v in wr.values()), bdiv_d, tdiv_d, drawset_div(r, rD),
            bdiv_e, tdiv_e, drawset_div(r, rE), cls))
    say("  premise (all variants identical to fmDRY in burning and burnt through step 68): %s" % premise)
    say("")
    say("  PREDICTIONS PER s (fire exact; agent predictions certain only while the fire equals a recorded arm):")
    for s in range(9, 18):
        bd_, td_, be_, te_, cls = table["s=%d" % s]
        if cls == "== fmDRY fire":
            pred = "IDENTICAL to fmDRY in every agent field -> rescued 2 dead 1 ffd 1, victim_2 rescued at 205"
        elif cls == "== fmEFS fire":
            pred = "IDENTICAL to fmEFS in every agent field -> rescued 1 dead 2 ffd 1, victim_2 unresolved at 240"
        else:
            if bd_ is not None and bd_ >= (be_ or 0):
                follow, until = "fmDRY", min(x for x in (bd_, td_) if x is not None) - 1
            else:
                follow, until = "fmEFS", min(x for x in (be_, te_) if x is not None) - 1
            pred = ("agents identical to %s through step %d (fmDRY and fmEFS agents are identical through 83 anyway), then"
                    " a fire neither arm saw -> outcome NOT predictable from recorded data" % (follow, until))
        say("    s=%-3d %s" % (s, pred))
    say("")
    say("  RECOMMENDED RUNS (5 + 1 optional), with what each tests:")
    say("    s=9   identity control: no write lands -> must equal fmDRY (all values but the fm2p key) - proves the"
        " wrapper is inert")
    say("    s=17  identity control: every write lands -> must equal fmEFS")
    say("    s=16  sharp prediction: (6,42)@16 is fire-neutral given the other 9 writes -> must equal fmEFS in every"
        " agent field. Only these may differ: fire_digests (the fuel of (6,42), from step 16), the step-16"
        " firefight_log row's dry/wrote, firefight_counters, firefight_shadow, fire_cleared_unburned_final, and"
        " the params/fm2p keys. A different rescue here would falsify the replay or the premise.")
    say("    s=14  the re-roll trigger is in: the fire equals fmEFS through step %d, so it contains fmEFS's tick-84"
        " re-roll. Afterwards a new realisation (fmEFS-relative re-roll at tick %s)." % (
            table["s=14"][2] - 1, drawset_div(replay({st: cs for st, cs in W.items() if st < 14}, record=True), rE)))
    say("    s=13  the trigger is out: the fire equals fmDRY through step %d, then a new realisation." % (table["s=13"][0] - 1))
    say("    s=15  (optional) fire equals fmEFS through step %d." % (table["s=15"][2] - 1))
    say("  WHAT ISOLATES THE CAUSAL WRITE")
    say("    - The only write that reproduces fmEFS's tick-84 re-roll ON ITS OWN is (7,40)@13 by ff_unit_0: 'only"
        " (7,40)@13' equals fmEFS in burning through step %s." % (table["only (7,40)@13"][2] - 1))
    say("    - Removing it ('all but (7,40)@13') keeps the fire equal to fmDRY until step %s." % (table["all but (7,40)@13"][0] - 1))
    say("    - WRITE_BEFORE cannot separate it from (8,43)@13 (ff_unit_1, same step). The replay can:"
        " 'steps<13 + (8,43)@13' is the s=13 fire, 'steps<13 + (7,40)@13' re-rolls like fmEFS.")
    say("    - A per-unit write filter would be needed to run that split closed-loop; the probe harness has no such"
        " key (FM2P_ENGAGE_ONLY changes behaviour, not just writes).")
    say("  EXPECTED OUTCOMES UNDER HYPOTHESIS (iii)")
    say("    - s=9 -> fmDRY; s=16, s=17 -> fmEFS (certain).")
    say("    - s=10..15 each run their own fire realisation after step 90..114, so their rescued counts are draws"
        " from the re-roll lottery.")
    say("    - Non-monotone in s, and NOT explained by which cells were cleared. The s=13 vs s=14 boundary"
        " decides only which realisation the run starts from.")
    say("    - The only mechanism prediction (iii) makes for s=10..15: whatever changes victim_2's rescue there"
        " again runs through the time the last unit is freed (victim_0's or victim_3's fate), not through fire"
        " near the band.")
    say("    - A run that loses victim_2 with fire identical to fmDRY near victim_0 and ff_unit_0 would contradict"
        " (iii). Check this from the probe's own burn_intervals.")
    say("    - Direct test of (iii) versus (i): FM2P_CRN=1 arms (CRN-DRY vs CRN-EFS). With the stream shift gone,"
        " (iii) predicts no rescue difference unless a physical difference reaches an agent. Their writes are"
        " unknowable offline, since CRN is a different fire.")
    say("  VALIDATING THE PROBE RUNS WITH THIS SCRIPT'S REPLAY")
    say("    - For each probe JSON, replay() its OWN recorded writes (firefight_log rows with wrote True). The"
        " result must match its fire_digests and burn_intervals 240/240.")
    say("    - Shadow (dry) rows are not writes, so they are left out of the replay exactly as the probe left them"
        " out of the fire.")
    say("    - Burning and burnt must then equal the table above for that s. A mismatch means a unit wrote on a"
        " step or cell this analysis did not predict, e.g. an idle unit in a new realisation.")

    with open(OUT_TXT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
