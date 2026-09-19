"""firemech round 2 - TASK O: IS A PURE DRAW-STREAM OFFSET NEUTRAL?  Out of tree, read-only on sources.

A no-write fire replay of an fmOFF tuple (outputs/_fm2_fire_replay.py construction, imported, not
edited) in which, from fire tick T on, the n-th draw of the run (in consumption order, counting
from the start of the run) is the OFF run's own stream value U[n + k]:
  k > 0 : a cell reads the number that would have been consumed k draws later (as if k extra
          cells had drawn earlier). Implemented by discarding k values of the SAME Random state
          at the first draw of tick T; values past OFF's end simply continue the generator.
  k < 0 : a cell reads the number consumed |k| draws earlier (as if |k| fewer cells had drawn).
          Implemented as a delay line of length |k| primed with the last |k| values consumed
          before tick T.
  k = 0 : the stock replay (must equal fmOFF 240/240).
No fire write happens; only the alignment of random numbers to cells changes.

Checks done inside every run (stored in the output JSON, block "offset"):
  * the consumed values A[n] are compared with G[n] (n < n_T) and G[n + k] (n >= n_T), where G is
    regenerated from the Random state captured at the first draw (= state after construction);
  * with --ref-draws (an OFF .draws file recorded by _fm2_fire_replay.py --record-draws or by a
    k = 0 run of this script) the recorded OFF stream S is compared with G (S == G[:len(S)]) and
    A[n] with S[n + k] wherever n + k < len(S);
  * the (p, burning, value) of every drawer is stored for the ticks in --rec-ticks.

usage
  run     : _fm2_rng_offset.py --run --tuple WIND RR SEED --T STEP --k K --out OUT.json
                               [--ref-draws FILE] [--save-draws FILE] [--rec-ticks 30,33]
            T is the model STEP of a fire tick (a multiple of 3: steps 3, 6, ..., 240).
  batch   : _fm2_rng_offset.py --batch validate|off|main|k3|arms|pinned --outdir DIR [--jobs 2]
            (at most 2 subprocesses; every start gated on FreeVirtualMemory >= 4,000,000 kB)
  analyze : _fm2_rng_offset.py --analyze offset|mechanism|arms|all --outdir DIR [--pinned-txt F]
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import math
import os
import random
import subprocess
import sys
import time
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")
sys.path.insert(0, HERE)
import _fm2_fire_replay as R  # noqa: E402

N = 2500
W = 50
STEPS = 240
SPEED = 3
NTICKS = STEPS // SPEED
MIN_FREE_KB = 4000000
NL = "\n"
NAN = float("nan")
SEEDS = (101, 202, 303, 404, 505, 606, 707, 808, 909, 1010)
CANON_SEEDS = (101, 202, 303, 404, 505)
TUPLES = [("east", "half", s) for s in SEEDS] + [("south", "half", s) for s in SEEDS]
MAIN_COMBOS = [(30, 1), (30, -1), (90, 1), (90, -1)]
K3_COMBOS = [(30, 3), (30, -3)]
# added after the main results: a replication of the T=90 wind x k-sign interaction at a new tick
# (T=93, fresh alignment of every post-T number) and an intermediate onset (T=60)
REP_COMBOS = [(93, 1), (93, -1), (60, 1), (60, -1)]
ALL_COMBOS = MAIN_COMBOS + K3_COMBOS + REP_COMBOS
STUDY_REPLAY = ("C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/"
                "4822f5f0-3ec2-4a14-8aeb-d97eb91ddf5a/scratchpad/replay")


# ============================================================================ run ===
def run_one(args) -> int:
    sys.path.insert(0, REPO)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402  (same module object run_replay imports)
    if int(am.FIRE_SPREAD_SPEED) != SPEED:
        raise SystemExit("FIRE_SPREAD_SPEED %r != 3" % am.FIRE_SPREAD_SPEED)
    wind, rr, seed = args.tuple[0], args.tuple[1], int(args.tuple[2])
    T, k = int(args.T), int(args.k)
    if T % SPEED or not SPEED <= T <= STEPS:
        raise SystemExit("T must be a fire-tick step (multiple of 3 in 3..240)")
    rec_ticks = set(int(x) for x in args.rec_ticks.split(",") if x.strip()) if args.rec_ticks else set()
    rec = array("d", [NAN]) * (NTICKS * N)
    st = {"n": 0, "n_T": None, "state0": None, "started": False, "skipped": [], "reused": [],
          "last": collections.deque(maxlen=max(1, -k)), "line": None, "ticks": {}}

    def draw(fire):
        rng = am.random
        if st["state0"] is None:
            st["state0"] = rng.getstate()
        sc = fire.steps_counter
        if sc >= T and not st["started"]:
            st["started"] = True
            st["n_T"] = st["n"]
            if k > 0:
                for _ in range(k):
                    st["skipped"].append(rng.random())
            elif k < 0:
                if len(st["last"]) != -k:
                    raise SystemExit("fewer than |k| draws before T")
                st["line"] = collections.deque(st["last"])
                st["reused"] = list(st["last"])
        if k < 0 and st["started"]:
            st["line"].append(rng.random())
            v = st["line"].popleft()
        else:
            v = rng.random()
            if k < 0:
                st["last"].append(v)
        uid = fire.unique_id
        rec[(sc // SPEED - 1) * N + uid] = v
        st["n"] += 1
        if sc in rec_ticks:
            st["ticks"].setdefault(sc, []).append([uid, fire.cell_prob, int(bool(fire.burning)), v])
        return v

    R._install_draw(am, draw)
    ns = argparse.Namespace(arm_json=R.arm_path("fmOFF", wind, rr, seed), writes="none", crn=False,
                            record_draws="", pin_draws="", steps=0, out=args.out, repo=REPO)
    rc = R.run_replay(ns)
    if rc != 0:
        return rc
    with open(args.out, encoding="utf-8") as f:
        out = json.load(f)
    if [c[0] for c in out["fires"]] != list(range(N)) or any(c[1] * W + c[2] != c[0] for c in out["fires"]):
        raise SystemExit("layout is not uid = 50*x + y")
    # ---- stream checks
    A = [v for v in rec if v == v]
    n_T = st["n_T"] if st["n_T"] is not None else len(A)
    g = random.Random()
    g.setstate(st["state0"])
    L = len(A) + max(k, 0) + 5
    G = [g.random() for _ in range(L)]
    bad_g = 0
    for n, v in enumerate(A):
        j = n if n < n_T else n + k
        if not (0 <= j < L) or G[j] != v:
            bad_g += 1
    chk = {"T": T, "k": k, "n_T": n_T, "draws_total": len(A), "draws_before_T": n_T,
           "skipped_values": st["skipped"], "reused_values": st["reused"],
           "vs_regenerated_stream": {"checked": len(A), "mismatch": bad_g}}
    if args.ref_draws:
        ref = array("d")
        with open(args.ref_draws, "rb") as f:
            ref.frombytes(f.read())
        S = [v for v in ref if v == v]
        s_vs_g = sum(1 for n in range(min(len(S), L)) if S[n] != G[n])
        inside = mism = beyond = 0
        for n, v in enumerate(A):
            j = n if n < n_T else n + k
            if 0 <= j < len(S):
                inside += 1
                if S[j] != v:
                    mism += 1
            else:
                beyond += 1
        chk["vs_ref_draws"] = {"file": os.path.abspath(args.ref_draws), "ref_len": len(S),
                               "ref_vs_regenerated_mismatch": s_vs_g, "checked": inside,
                               "mismatch": mism, "beyond_ref": beyond}
    chk["ticks"] = {str(t): sorted(v) for t, v in st["ticks"].items()}
    out["offset"] = chk
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline=NL) as f:
        json.dump(out, f)
    os.replace(tmp, args.out)
    if args.save_draws:
        tmpd = args.save_draws + ".tmp"
        with open(tmpd, "wb") as f:
            f.write(rec.tobytes())
        os.replace(tmpd, args.save_draws)
    print("offset T=%d k=%+d n_T=%d draws=%d regen_mismatch=%d ref=%s" % (
        T, k, n_T, len(A), bad_g, chk.get("vs_ref_draws")))
    return 0


# ========================================================================== batch ===
def tname(t):
    return "%s_%s_%d" % t


def off_json(outdir, t):
    return os.path.join(outdir, "off_%s_k0.json" % tname(t))


def off_draws(outdir, t):
    return os.path.join(outdir, "off_%s_k0.draws" % tname(t))


def arm_json_name(outdir, T, k, t):
    return os.path.join(outdir, "off_%s_T%d_k%s%d.json" % (tname(t), T, "p" if k > 0 else "m", abs(k)))


def study_draws(t):
    p = os.path.join(STUDY_REPLAY, "rp_fmOFF_%s_%s_%d_none.draws" % t)
    return p if os.path.exists(p) else ""


def writes_count(tag, t):
    with open(R.arm_path(tag, *t), encoding="utf-8") as f:
        d = json.load(f)
    return sum(1 for r in (d.get("firefight_log") or []) if r.get("wrote"))


def wr_json(outdir, tag, t, pinned=False):
    return os.path.join(outdir, "wr_%s_%s_all%s.json" % (tag, tname(t), "_pin" if pinned else ""))


def build_jobs(plan, outdir):
    jobs = []
    me = os.path.abspath(__file__)
    if plan in ("validate", "off"):
        ts = [("east", "half", 101), ("south", "half", 404)] if plan == "validate" else TUPLES
        for t in ts:
            cmd = [PY, me, "--run", "--tuple", t[0], t[1], str(t[2]), "--T", "240", "--k", "0",
                   "--rec-ticks", "30,33,90,93", "--out", off_json(outdir, t), "--save-draws", off_draws(outdir, t)]
            sd = study_draws(t)
            if sd:
                cmd += ["--ref-draws", sd]
            jobs.append({"out": off_json(outdir, t), "cmd": cmd, "need": []})
    elif plan in ("main", "k3", "rep"):
        combos = {"main": MAIN_COMBOS, "k3": K3_COMBOS, "rep": REP_COMBOS}[plan]
        for T, k in combos:
            for t in TUPLES:
                o = arm_json_name(outdir, T, k, t)
                cmd = [PY, me, "--run", "--tuple", t[0], t[1], str(t[2]), "--T", str(T), "--k", str(k),
                       "--rec-ticks", "%d,%d" % (T, T + 3), "--out", o, "--ref-draws", off_draws(outdir, t)]
                jobs.append({"out": o, "cmd": cmd, "need": [off_draws(outdir, t)]})
    elif plan in ("arms", "pinned"):
        for tag in ("fmF", "fmES"):
            for t in TUPLES:
                if writes_count(tag, t) == 0:
                    continue
                o = wr_json(outdir, tag, t, pinned=(plan == "pinned"))
                cmd = [PY, os.path.join(HERE, "_fm2_fire_replay.py"), "--arm-json", R.arm_path(tag, *t),
                       "--writes", "all", "--out", o]
                if plan == "pinned":
                    cmd += ["--pin-draws", off_draws(outdir, t)]
                jobs.append({"out": o, "cmd": cmd, "need": [off_draws(outdir, t)] if plan == "pinned" else []})
    return jobs


def done(o):
    if not os.path.exists(o):
        return False
    try:
        with open(o, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return False
    if os.path.basename(o).startswith("off_"):
        return "offset" in d
    return True


def run_batch(args) -> int:
    os.makedirs(args.outdir, exist_ok=True)
    jobs = build_jobs(args.batch, args.outdir)
    jn = max(1, min(2, int(args.jobs)))
    log = open(os.path.join(args.outdir, "batch_%s.log" % args.batch), "a", encoding="utf-8", newline=NL)

    def say(m):
        line = time.strftime("%H:%M:%S ") + m
        print(line, flush=True)
        log.write(line + NL)
        log.flush()

    pending = [j for j in jobs if not done(j["out"])]
    say("batch %s: %d jobs, %d to run, jobs=%d" % (args.batch, len(jobs), len(pending), jn))
    running = []
    t0 = time.time()
    lowest = None
    while pending or running:
        for item in list(running):
            p, j, ts, errf = item
            if p.poll() is not None:
                errf.close()
                running.remove(item)
                say("done rc=%s %.0fs %s" % (p.returncode, time.time() - ts, os.path.basename(j["out"])))
        if pending and len(running) < jn:
            j = pending[0]
            if any(not os.path.exists(x) for x in j["need"]):
                say("SKIP (missing prerequisite) %s" % os.path.basename(j["out"]))
                pending.pop(0)
                continue
            fk = R.free_kb()
            if fk < MIN_FREE_KB:
                say("free commit %d kB < %d, waiting" % (fk, MIN_FREE_KB))
                time.sleep(20)
                continue
            lowest = fk if lowest is None else min(lowest, fk)
            pending.pop(0)
            errf = open(j["out"][:-5] + ".log", "w", encoding="utf-8", newline=NL)
            p = subprocess.Popen(j["cmd"], stdout=errf, stderr=subprocess.STDOUT, cwd=REPO)
            running.append((p, j, time.time(), errf))
            say("start (free %d kB) %s" % (fk, os.path.basename(j["out"])))
            continue
        time.sleep(2)
    say("batch %s finished in %.0fs; lowest free commit at a start %s kB" % (args.batch, time.time() - t0, lowest))
    log.close()
    return 0


# ======================================================================== analysis ===
def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def ever_by_step(r):
    """cumulative count of cells that have been burning by the end of each step (1-based list)."""
    seen = set(r["initial_burning"])
    out = []
    for on in r["burning_on"]:
        seen.update(on)
        out.append(len(seen))
    return out


def burning_sets(r):
    cur = set(r["initial_burning"])
    res = []
    for on, off in zip(r["burning_on"], r["burning_off"]):
        cur = (cur - set(off)) | set(on)
        res.append(frozenset(cur))
    return res


def burnt_sets(r):
    cur = set()
    res = []
    for new in r["burnt_new"]:
        cur |= set(new)
        res.append(frozenset(cur))
    return res


def mean(v):
    return sum(v) / len(v) if v else float("nan")


def sd(v):
    if len(v) < 2:
        return float("nan")
    m = mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def signflip_p(values):
    """exact two-sided sign-flip p of sum(values); each value is one cluster."""
    obs = abs(sum(values))
    n = len(values)
    hit = 0
    for signs in itertools.product((1, -1), repeat=n):
        if abs(sum(s * v for s, v in zip(signs, values))) >= obs - 1e-9:
            hit += 1
    return hit / float(2 ** n)


def spearman(a, b):
    def ranks(v):
        idx = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[idx[j + 1]] == v[idx[i]]:
                j += 1
            for m in range(i, j + 1):
                rk[idx[m]] = (i + j) / 2.0 + 1
            i = j + 1
        return rk
    return pearson(ranks(a), ranks(b))


def pearson(a, b):
    ma, mb = mean(a), mean(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if sa == 0 or sb == 0:
        return float("nan")
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def analyze_offset(args):
    import _firemech_analyze as FA  # noqa: E402
    od = args.outdir
    offs = {}
    print("A. VALIDATION OF THE k = 0 REPLAYS (the OFF reference of every offset arm)")
    print("   digest = replay vs fmOFF harness fire_digests; intact vs _firemech_analyze.run_summary(fmOFF);")
    print("   regen = consumed values vs the regenerated Random stream; ref = vs the independently recorded")
    print("   study .draws of _fm2_fire_replay.py --record-draws (S==G: recorded OFF stream == regenerated)")
    for t in TUPLES:
        p = off_json(od, t)
        if not os.path.exists(p):
            print("   %-16s MISSING" % ("%s/%s/%d" % t))
            continue
        r = load(p)
        S = FA.run_summary(load(R.arm_path("fmOFF", *t)), None)
        o = r["offset"]
        dv = r["digest_vs_arm"]
        ref = o.get("vs_ref_draws")
        offs[t] = r
        print("   %-16s digest %3d/%3d meaningful=%s | intact replay %4d analyzer %4d same=%s | draws %6d regen mismatch %d"
              " | ref %s" % ("%s/%s/%d" % t, dv["matched"], dv["compared"], dv["meaningful"], r["final"]["intact"],
                            S["intact"], r["final"]["intact"] == S["intact"], o["draws_total"],
                            o["vs_regenerated_stream"]["mismatch"],
                            ("checked %d mismatch %d S==G mismatch %d" % (ref["checked"], ref["mismatch"],
                                                                         ref["ref_vs_regenerated_mismatch"]))
                            if ref else "none (no study .draws for this tuple)"))
        sdp = study_draws(t)
        if sdp and os.path.exists(off_draws(od, t)):
            with open(sdp, "rb") as f1, open(off_draws(od, t), "rb") as f2:
                same = f1.read() == f2.read()
            print("   %-16s saved .draws byte-identical to the study's --record-draws file: %s" % ("", same))
    print("")
    print("B. DRAWS PER FIRE TICK (within-tick vs cumulative sanity; draws at a tick = cells not burnt)")
    for t, r in offs.items():
        dpt = dict((a, b) for a, b in r["draws_per_tick"])
        tot = sum(dpt.values())
        print("   %-16s tick@30 %4d @90 %4d @150 %4d @240 %4d | first tick < 2500: step %s | total draws %6d"
              " | burnt at 240: %4d" % ("%s/%s/%d" % t, dpt[30], dpt[90], dpt[150], dpt[240],
                                        next((a for a, b in r["draws_per_tick"] if b < N), None), tot,
                                        r["final"]["burnt"]))
    if offs:
        d30 = [dict(r["draws_per_tick"])[30] for r in offs.values()]
        d90 = [dict(r["draws_per_tick"])[90] for r in offs.values()]
        d240 = [dict(r["draws_per_tick"])[240] for r in offs.values()]
        drops = []
        for r in offs.values():
            v = [b for a, b in r["draws_per_tick"]]
            drops += [v[i] - v[i + 1] for i in range(len(v) - 1)]
        print("   range over the 20 tuples: tick@30 %d..%d, @90 %d..%d, @240 %d..%d; per-tick change in the draw"
              " count: max drop %d, mean drop %.2f, ticks with no change %d of %d" % (
                  min(d30), max(d30), min(d90), max(d90), min(d240), max(d240), max(drops), mean(drops),
                  sum(1 for x in drops if x == 0), len(drops)))
    print("")
    combos = ALL_COMBOS
    table = {}
    print("C. OFFSET ARMS: intact(arm) - intact(OFF) PER RUN (stream check: regen / ref mismatches must be 0)")
    for T, k in combos:
        rows = []
        for t in TUPLES:
            p = arm_json_name(od, T, k, t)
            if not (os.path.exists(p) and t in offs):
                continue
            a = load(p)
            o = offs[t]
            oc = a["offset"]
            ref = oc.get("vs_ref_draws") or {}
            ea, eo = ever_by_step(a), ever_by_step(o)
            sym = len(set(a["final_has_burned"]) ^ set(o["final_has_burned"]))
            first_div = next((i + 1 for i in range(STEPS) if a["digests"][i] != o["digests"][i]), None)
            pre = sum(1 for i in range(T - 1) if a["digests"][i] != o["digests"][i])
            rows.append({"t": t, "T": T, "k": k, "d": a["final"]["intact"] - o["final"]["intact"],
                         "d_ever_T": ea[T - 1] - eo[T - 1], "d_ever_T3": ea[T + 2] - eo[T + 2],
                         "d_ever_T15": ea[min(T + 14, STEPS - 1)] - eo[min(T + 14, STEPS - 1)],
                         "d_ever_T30": ea[min(T + 29, STEPS - 1)] - eo[min(T + 29, STEPS - 1)],
                         "d_burning_T": a["burning_count"][T - 1] - o["burning_count"][T - 1],
                         "sym": sym, "first_div": first_div, "pre_T_div": pre,
                         "regen_bad": oc["vs_regenerated_stream"]["mismatch"], "ref_bad": ref.get("mismatch"),
                         "ref_checked": ref.get("checked"), "beyond": ref.get("beyond_ref"),
                         "draws": oc["draws_total"], "off_draws": o["offset"]["draws_total"],
                         "arm_intact": a["final"]["intact"], "off_intact": o["final"]["intact"]})
        table[(T, k)] = rows
        if not rows:
            continue
        print("  T=%d k=%+d  (n=%d)" % (T, k, len(rows)))
        print("   %-16s %5s %5s %6s | %6s %6s %6s %6s %6s | %6s %5s %5s | %6s %6s %6s %7s %7s" % (
            "tuple", "OFF", "arm", "d", "dEvT", "dEvT+3", "+15", "+30", "dBrnT", "symdif", "div", "preT",
            "regen", "ref", "beyond", "drawsA", "drawsO"))
        for x in rows:
            print("   %-16s %5d %5d %+6d | %+6d %+6d %+6d %+6d %+6d | %6d %5s %5d | %6d %6s %6s %7d %7d" % (
                "%s/%s/%d" % x["t"], x["off_intact"], x["arm_intact"], x["d"], x["d_ever_T"], x["d_ever_T3"],
                x["d_ever_T15"], x["d_ever_T30"], x["d_burning_T"], x["sym"], x["first_div"], x["pre_T_div"],
                x["regen_bad"], x["ref_bad"], x["beyond"], x["draws"], x["off_draws"]))
    print("")
    print("D. SUMMARY PER (T, k): mean, sd, sign counts, exact sign-flip p (two-sided)")
    print("   pooled p: clusters = seeds (east/half/s + south/half/s share ignition and fuel map), 2^10 flips;")
    print("   wind split p: each run its own cluster. 'ever by T+3/T+15/T+30' = the same statistics for the count")
    print("   of cells ever burning by that step, arm - OFF (POSITIVE = the arm's fire is BIGGER at that step)")
    summ = {}
    for (T, k), rows in table.items():
        if not rows:
            continue
        for label, key in (("final intact", "d"), ("ever by T+3 (+ = arm bigger)", "d_ever_T3"),
                           ("ever by T+15", "d_ever_T15"), ("ever by T+30", "d_ever_T30")):
            line = []
            for wsel in ("both", "east", "south"):
                xs = [x for x in rows if wsel == "both" or x["t"][0] == wsel]
                v = [x[key] for x in xs]
                if wsel == "both":
                    cl = collections.defaultdict(int)
                    for x in xs:
                        cl[x["t"][2]] += x[key]
                    p = signflip_p(list(cl.values()))
                else:
                    p = signflip_p(v)
                line.append("%s n=%2d mean %+8.1f sd %6.1f +/-/0 %2d/%2d/%2d p %.3f" % (
                    wsel, len(v), mean(v), sd(v), sum(1 for z in v if z > 0), sum(1 for z in v if z < 0),
                    sum(1 for z in v if z == 0), p))
                if key == "d":
                    summ[(T, k, wsel)] = (mean(v), sd(v), p, len(v))
            print("   T=%-3d k=%+d %-32s | %s" % (T, k, label, " | ".join(line)))
    print("")
    ks = [(T, k) for (T, k) in table if table[(T, k)]]
    allrows = [x for key in ks for x in table[key]]
    if allrows:
        print("E. POOLED MAGNITUDE OF A PURE RE-ROLL (all offset arms): |d| median %s mean %.1f; sd of d %.1f;"
              " arms with d = 0: %d of %d; final has_burned symdiff median %s" % (
                  sorted(abs(x["d"]) for x in allrows)[len(allrows) // 2], mean([abs(x["d"]) for x in allrows]),
                  sd([x["d"] for x in allrows]), sum(1 for x in allrows if x["d"] == 0), len(allrows),
                  sorted(x["sym"] for x in allrows)[len(allrows) // 2]))
        pairs = []
        for t in TUPLES:
            a = [x for x in table.get((30, 1), []) if x["t"] == t]
            b = [x for x in table.get((30, -1), []) if x["t"] == t]
            if a and b:
                pairs.append((a[0]["d"], b[0]["d"]))
        if pairs:
            print("   T=30: pearson(d[k=+1], d[k=-1]) over tuples = %.2f (n=%d); T=30 vs T=90 k=+1: %s" % (
                pearson([p[0] for p in pairs], [p[1] for p in pairs]), len(pairs),
                "%.2f" % pearson([x["d"] for x in table[(30, 1)]], [x["d"] for x in table[(90, 1)]])
                if len(table.get((30, 1), [])) == len(table.get((90, 1), [])) == 20 else "n/a"))
        print("   stream checks over all offset arms: regen mismatches %d, ref mismatches %s, ref values checked %d" % (
            sum(x["regen_bad"] for x in allrows), sum((x["ref_bad"] or 0) for x in allrows),
            sum((x["ref_checked"] or 0) for x in allrows)))
        print("   steps with a digest difference before T: %d (must be 0); first digest divergence == T: %d of %d" % (
            sum(x["pre_T_div"] for x in allrows), sum(1 for x in allrows if x["first_div"] == x["T"]),
            len(allrows)))
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline=NL) as f:
            json.dump({"%d_%d" % key: rows for key, rows in table.items()}, f)
    return table


def rel_class(u, s, wind):
    ux, uy = divmod(u, W)
    sx, sy = divmod(s, W)
    dx, dy = sx - ux, sy - uy
    if wind == "east":
        along, lat = dx, dy
    else:
        along, lat = -dy, dx
    if along == 0 and abs(lat) <= 3:
        return "lateral"
    if lat == 0 and 0 < along <= 3:
        return "ahead"
    if lat == 0 and -3 <= along < 0:
        return "behind"
    return "far/wrap"


def analyze_mechanism(args):
    od = args.outdir
    print("F. MECHANISM AT THE FIRST OFFSET TICK T (state before T is identical in arm and OFF, so every")
    print("   cell's ignition probability p is the same; only the number it is compared with moves).")
    print("   u = a drawing cell that was NOT burning before T and has p > 0 (a front cell).")
    print("   s(u) = the drawer whose OFF number u reads (k positions away in OFF's consumption order at T).")
    print("   s relative to u along the wind: ahead = downwind of u, behind = upwind (toward the fire),")
    print("   lateral = across the wind; far/wrap = the row wrap (x, 49) -> (x+1, 0) or skipped burnt cells.")
    print("   ign_O / ign_A = u ignites at T in OFF / in the arm (from burning_on at step T; checked == value < p).")
    print("   E_A = sum of the conditional expectation of the arm ignition GIVEN OFF's outcome for s:")
    print("         if s ignited in OFF (U_s < p_s): min(p_u, p_s)/p_s ; else (U_s >= p_s): max(0, p_u - p_s)/(1 - p_s);")
    print("         for s burning before T the same formulas with s's own p (its draw decided whether it kept burning).")
    print("   sum_p = sum of p_u = the expected ignitions in BOTH arms before any number is seen.")
    agg = collections.OrderedDict()
    checks = collections.Counter()
    per_run = []
    for T, k in ALL_COMBOS:
        for t in TUPLES:
            pa, po = arm_json_name(od, T, k, t), off_json(od, t)
            if not (os.path.exists(pa) and os.path.exists(po)):
                continue
            a, o = load(pa), load(po)
            ta = a["offset"]["ticks"].get(str(T))
            to = o["offset"]["ticks"].get(str(T))
            if ta is None or to is None:
                checks["missing tick record"] += 1
                continue
            A = {row[0]: row for row in ta}
            O = {row[0]: row for row in to}
            if set(A) != set(O):
                checks["drawer set differs"] += 1
                continue
            drawers = sorted(O)
            pos = {u: i for i, u in enumerate(drawers)}
            pmis = sum(1 for u in drawers if A[u][1] != O[u][1] or A[u][2] != O[u][2])
            checks["p or burning mismatch arm vs OFF at T"] += pmis
            on_A = set(a["burning_on"][T - 1])
            on_O = set(o["burning_on"][T - 1])
            off_O = set(o["burning_off"][T - 1])
            off_A = set(a["burning_off"][T - 1])
            burnt_new_O = set(o["burnt_new"][T - 1])
            d_ign = 0
            d_keep = 0
            run_cls = collections.Counter()
            for u in drawers:
                p_u, burn_u, vA = A[u][1], A[u][2], A[u][3]
                vO = O[u][3]
                j = pos[u] + k
                if 0 <= j < len(drawers):
                    s = drawers[j]
                    if vA != O[s][3]:
                        checks["arm value != OFF value of s(u)"] += 1
                else:
                    s = None
                if burn_u:
                    if u in burnt_new_O:
                        continue
                    kept_O = u not in off_O
                    kept_A = u not in off_A
                    if kept_O != (vO < p_u):
                        checks["OFF keep != (U<p)"] += 1
                    if kept_A != (vA < p_u):
                        checks["arm keep != (V<p)"] += 1
                    d_keep += int(kept_A) - int(kept_O)
                    continue
                if p_u <= 0:
                    if u in on_A or u in on_O:
                        checks["ignition with p=0"] += 1
                    continue
                iO, iA = u in on_O, u in on_A
                if iO != (vO < p_u):
                    checks["OFF ign != (U<p)"] += 1
                if iA != (vA < p_u):
                    checks["arm ign != (V<p)"] += 1
                if s is None:
                    cls, sst, ea = "outside tick", "-", p_u
                else:
                    cls = rel_class(u, s, t[0])
                    p_s, burn_s = O[s][1], O[s][2]
                    low = O[s][3] < p_s
                    if burn_s:
                        sst = "s burning, kept" if low else "s burning, went out"
                    else:
                        sst = "s ignited" if low else ("s not ignited, p_s>0" if p_s > 0 else "s p_s=0")
                    if low:
                        ea = min(p_u, p_s) / p_s
                    else:
                        ea = max(0.0, p_u - p_s) / (1.0 - p_s) if p_s < 1 else 0.0
                    run_cls[(cls, sst)] += 1
                    pr = "p_u>p_s" if p_u > p_s else ("p_u<p_s" if p_u < p_s else "p_u=p_s")
                    key2 = (t[0], k, "by p", pr, sst)
                    g2 = agg.setdefault(key2, [0, 0, 0, 0.0, 0.0])
                    g2[0] += 1
                    g2[1] += iO
                    g2[2] += iA
                    g2[3] += ea
                    g2[4] += p_u
                d_ign += int(iA) - int(iO)
                key = (t[0], k, cls, sst)
                g = agg.setdefault(key, [0, 0, 0, 0.0, 0.0])
                g[0] += 1
                g[1] += iO
                g[2] += iA
                g[3] += ea
                g[4] += p_u
                gt = agg.setdefault((t[0], k, "ALL", "all front cells"), [0, 0, 0, 0.0, 0.0])
                gt[0] += 1
                gt[1] += iO
                gt[2] += iA
                gt[3] += ea
                gt[4] += p_u
            per_run.append({"T": T, "k": k, "t": t, "d_ign": d_ign, "d_keep": d_keep,
                            "d_burning_T": a["burning_count"][T - 1] - o["burning_count"][T - 1],
                            "d_final": a["final"]["intact"] - o["final"]["intact"]})
    print("   consistency checks (all must be 0): %s" % dict(checks))
    print("")
    print("   pooled over runs and both T (k=+-1) or T=30 (k=+-3):")
    print("   %-5s %-3s %-9s %-24s %6s %6s %6s %+7s %8s %8s" % ("wind", "k", "s rel", "s state in OFF", "n_u",
                                                               "ign_O", "ign_A", "dIgn", "E_A", "sum_p"))
    for key in sorted(agg, key=lambda z: (z[0], z[1], z[2] != "ALL", z[2], z[3])):
        g = agg[key]
        if key[2] == "by p":
            continue
        print("   %-5s %+3d %-9s %-24s %6d %6d %6d %+7d %8.1f %8.1f" % (key[0], key[1], key[2], key[3], g[0], g[1], g[2],
                                                                  g[2] - g[1], g[3], g[4]))
    print("")
    print("   the same front cells split by p_u vs p_s (the number u reads was drawn against p_s):")
    for key in sorted((z for z in agg if z[2] == "by p"), key=lambda z: (z[0], z[1], z[3], z[4])):
        g = agg[key]
        print("   %-5s %+3d %-9s %-24s %6d %6d %6d %+7d %8.1f %8.1f" % (key[0], key[1], key[3], key[4], g[0], g[1], g[2],
                                                                  g[2] - g[1], g[3], g[4]))
    print("")
    print("   per (T, k, wind): ignitions arm - OFF at T summed over runs (sign counts over runs), burning cells kept")
    print("   arm - OFF, burning count arm - OFF after step T, and the final intact delta of the same runs")
    grp = collections.defaultdict(list)
    for x in per_run:
        grp[(x["T"], x["k"], x["t"][0])].append(x)
    for key in sorted(grp):
        xs = grp[key]
        v = [x["d_ign"] for x in xs]
        print("   T=%-3d k=%+d %-5s n=%2d | dIgn sum %+5d mean %+6.2f +/-/0 %2d/%2d/%2d p %.3f | dKeep sum %+5d |"
              " dBurning@T sum %+5d | final d sum %+6d" % (
                  key[0], key[1], key[2], len(xs), sum(v), mean(v), sum(1 for z in v if z > 0),
                  sum(1 for z in v if z < 0), sum(1 for z in v if z == 0), signflip_p(v),
                  sum(x["d_keep"] for x in xs), sum(x["d_burning_T"] for x in xs), sum(x["d_final"] for x in xs)))
    if per_run:
        print("   pearson(dBurning@T, final d) over all runs = %.2f (n=%d)" % (
            pearson([x["d_burning_T"] for x in per_run], [x["d_final"] for x in per_run]), len(per_run)))


def seed_cluster_p(pairs):
    """pairs: list of (tuple, value); clusters by seed (east/half/s + south/half/s)."""
    cl = collections.defaultdict(float)
    for t, v in pairs:
        cl[t[2]] += v
    return signflip_p(list(cl.values()))


def fmt_stats(v):
    return "n=%2d sum %+7.0f mean %+7.1f sd %6.1f +/-/0 %2d/%2d/%2d" % (
        len(v), sum(v), mean(v), sd(v), sum(1 for z in v if z > 0), sum(1 for z in v if z < 0),
        sum(1 for z in v if z == 0))


def reroll_baseline(od):
    combos = [(30, 1), (30, -1), (90, 1), (90, -1), (30, 3), (30, -3)]
    B, B30, B90 = {}, {}, {}
    for t in TUPLES:
        po = off_json(od, t)
        if not os.path.exists(po):
            continue
        oi = load(po)["final"]["intact"]
        d = {}
        for T, k in combos:
            pa = arm_json_name(od, T, k, t)
            if os.path.exists(pa):
                d[(T, k)] = load(pa)["final"]["intact"] - oi
        if d:
            B[t] = mean(list(d.values()))
            v30 = [v for (T, k), v in d.items() if T == 30]
            v90 = [v for (T, k), v in d.items() if T == 90]
            B30[t] = mean(v30) if v30 else float("nan")
            B90[t] = mean(v90) if v90 else float("nan")
    return B, B30, B90


def analyze_reroll(args):
    import _firemech_analyze as FA  # noqa: E402
    od = args.outdir
    combos = MAIN_COMBOS + K3_COMBOS
    D = {}
    E = {}
    offc = {}
    for T, k in ALL_COMBOS:
        for t in TUPLES:
            pa, po = arm_json_name(od, T, k, t), off_json(od, t)
            if os.path.exists(pa) and os.path.exists(po):
                if t not in offc:
                    offc[t] = load(po)
                o = offc[t]
                a = load(pa)
                D[(T, k, t)] = a["final"]["intact"] - o["final"]["intact"]
                ea, eo = ever_by_step(a), ever_by_step(o)
                E[(T, k, t)] = {h: ea[min(T + h - 1, STEPS - 1)] - eo[min(T + h - 1, STEPS - 1)] for h in (3, 15, 30, 60)}
    print("H. WHAT THE OFFSET ARMS SHARE: A DIRECTIONAL COUPLING (k sign) OR THE OFF RUN'S OWN LUCK?")
    print("H1. paired k contrast per tuple, c = d(T, +|k|) - d(T, -|k|): the OFF run cancels, a sign-dependent")
    print("    coupling would survive. p pooled = sign-flip over seeds; wind interaction = per seed c_south - c_east.")
    for T, kk in ((30, 1), (90, 1), (30, 3), (93, 1), (60, 1)):
        rows = [(t, D[(T, kk, t)] - D[(T, -kk, t)]) for t in TUPLES if (T, kk, t) in D and (T, -kk, t) in D]
        if not rows:
            continue
        for wsel in ("both", "east", "south"):
            xs = [(t, v) for t, v in rows if wsel == "both" or t[0] == wsel]
            v = [z for _, z in xs]
            p = seed_cluster_p(xs) if wsel == "both" else signflip_p(v)
            print("    T=%-3d |k|=%d %-5s %s p %.3f" % (T, kk, wsel, fmt_stats(v), p))
        inter = []
        ce_l, cs_l = [], []
        for s_ in SEEDS:
            ce = [v for t, v in rows if t == ("east", "half", s_)]
            cs = [v for t, v in rows if t == ("south", "half", s_)]
            if ce and cs:
                inter.append(cs[0] - ce[0])
                ce_l.append(ce[0])
                cs_l.append(cs[0])
        if inter:
            print("    T=%-3d |k|=%d wind interaction (c_south - c_east per seed) %s p %.3f | per seed c_east %s"
                  " c_south %s | pearson(c_east, c_south) %.2f" % (
                      T, kk, fmt_stats(inter), signflip_p(inter), ce_l, cs_l, pearson(ce_l, cs_l)))
            for kx in (kk, -kk):
                de = [D[(T, kx, ("east", "half", s_))] for s_ in SEEDS if (T, kx, ("east", "half", s_)) in D]
                ds = [D[(T, kx, ("south", "half", s_))] for s_ in SEEDS if (T, kx, ("south", "half", s_)) in D]
                if len(de) == len(ds) == len(SEEDS):
                    print("      k=%+d: pearson over seeds of d(east/s), d(south/s) = %.2f" % (kx, pearson(de, ds)))
        for h in (3, 15, 30, 60):
            rows_e = [(t, E[(T, kk, t)][h] - E[(T, -kk, t)][h]) for t in TUPLES if (T, kk, t) in E and (T, -kk, t) in E]
            parts = []
            for wsel in ("both", "east", "south"):
                xs = [(t, v) for t, v in rows_e if wsel == "both" or t[0] == wsel]
                v = [z for _, z in xs]
                pp = seed_cluster_p(xs) if wsel == "both" else signflip_p(v)
                parts.append("%s mean %+6.1f sd %5.1f +/-/0 %2d/%2d/%2d p %.3f" % (
                    wsel, mean(v), sd(v), sum(1 for z in v if z > 0), sum(1 for z in v if z < 0),
                    sum(1 for z in v if z == 0), pp))
            print("      early fire size, contrast of (ever burning by step T+%d: arm - OFF) between +|k| and -|k|"
                  " (+ = +|k| arm bigger): %s" % (h, " | ".join(parts)))
    print("")
    print("H2. the common component: b(tuple) = mean of d over the tuple's offset arms (all 6 when present;")
    print("    b30 = the 4 arms with T=30, b90 = the 2 arms with T=90). If an offset only re-rolls the fire,")
    print("    E[arm | seed, history before T] is the same for every arm, so b estimates E[intact] - intact(OFF):")
    print("    how lucky or unlucky the recorded OFF realisation was after T.")
    B, B30, B90 = {}, {}, {}
    within = []
    print("    %-16s %5s | %s | %7s %7s %7s | %6s" % ("tuple", "OFF", " ".join("%7s" % ("T%dk%+d" % c) for c in combos),
                                                  "b", "b30", "b90", "sd_in"))
    for t in TUPLES:
        vals = [D[(T, k, t)] for T, k in combos if (T, k, t) in D]
        if not vals:
            continue
        B[t] = mean(vals)
        v30 = [D[(30, k, t)] for k in (1, -1, 3, -3) if (30, k, t) in D]
        v90 = [D[(90, k, t)] for k in (1, -1) if (90, k, t) in D]
        B30[t] = mean(v30) if v30 else float("nan")
        B90[t] = mean(v90) if v90 else float("nan")
        within.extend([x - B[t] for x in vals])
        offi = load(off_json(od, t))["final"]["intact"]
        print("    %-16s %5d | %s | %+7.1f %+7.1f %+7.1f | %6.1f" % (
            "%s/%s/%d" % t, offi, " ".join(("%+7d" % D[(T, k, t)]) if (T, k, t) in D else "      -" for T, k in combos),
            B[t], B30[t], B90[t], sd(vals)))
    if B:
        nper = mean([sum(1 for T, k in combos if (T, k, t) in D) for t in B])
        dof = sum(sum(1 for T, k in combos if (T, k, t) in D) - 1 for t in B)
        s_in = math.sqrt(sum(x * x for x in within) / dof) if dof else float("nan")
        s_b = sd(list(B.values()))
        print("    within-tuple sd (pooled) %.1f; sd of b over tuples %.1f; expected sd of b from within-noise alone"
              " %.1f (n per tuple %.1f)" % (s_in, s_b, s_in / math.sqrt(nper), nper))
        for label, sel in (("all 20", TUPLES), ("canonical 10 (seeds 101-505)", [t for t in TUPLES if t[2] in CANON_SEEDS]),
                           ("fresh 10 (606-1010)", [t for t in TUPLES if t[2] not in CANON_SEEDS]),
                           ("east", [t for t in TUPLES if t[0] == "east"]), ("south", [t for t in TUPLES if t[0] == "south"])):
            xs = [(t, B[t]) for t in sel if t in B]
            v = [z for _, z in xs]
            p = seed_cluster_p(xs) if label in ("all 20",) or "10" in label else signflip_p(v)
            print("    b over %-30s %s p %.3f | b30 sum %+7.0f | b90 sum %+7.0f" % (
                label, fmt_stats(v), p, sum(B30[t] for t in sel if t in B), sum(B90[t] for t in sel if t in B)))
        pr = [(D[(30, 1, t)], D[(30, -1, t)]) for t in TUPLES if (30, 1, t) in D and (30, -1, t) in D]
        pr2 = [(mean([D[(30, 1, t)], D[(30, -1, t)]]), mean([D[(90, 1, t)], D[(90, -1, t)]])) for t in TUPLES
               if all((T, k, t) in D for T in (30, 90) for k in (1, -1))]
        if pr:
            print("    across tuples: pearson(d[T30,k+1], d[T30,k-1]) = %.2f (n=%d); pearson(mean T30 k+-1, mean T90 k+-1)"
                  " = %.2f (n=%d); pearson(OFF intact, b) = %.2f" % (
                      pearson([a for a, _ in pr], [b for _, b in pr]), len(pr),
                      pearson([a for a, _ in pr2], [b for _, b in pr2]) if len(pr2) > 2 else float("nan"), len(pr2),
                      pearson([load(off_json(od, t))["final"]["intact"] for t in B], [B[t] for t in B])))
    print("")
    print("H3. round-1 stock arms against the same OFF: d_arm = intact(arm) - intact(fmOFF) (analyzer definition),")
    print("    and d_arm - b (the arm's change beyond what a pure re-roll of this OFF gives on average).")
    arms = {}
    for tag in ("fmDRY", "fmF", "fmFS", "fmES", "fmEFS"):
        for t in TUPLES:
            SA = FA.run_summary(load(R.arm_path(tag, *t)), None)
            SO = FA.run_summary(load(R.arm_path("fmOFF", *t)), None)
            arms[(tag, t)] = (SA["intact"] - SO["intact"], SA.get("first_write"))
    for tag in ("fmDRY", "fmF", "fmFS", "fmES", "fmEFS"):
        for label, sel in (("all 20", TUPLES), ("canon 10", [t for t in TUPLES if t[2] in CANON_SEEDS]),
                           ("fresh 10", [t for t in TUPLES if t[2] not in CANON_SEEDS])):
            ts = [t for t in sel if t in B]
            if not ts:
                continue
            da = [arms[(tag, t)][0] for t in ts]
            ex = [(t, arms[(tag, t)][0] - B[t]) for t in ts]
            v = [z for _, z in ex]
            print("    %-5s %-8s d_arm %s p %.3f || d_arm - b %s p %.3f || spearman(d_arm, b) %.2f" % (
                tag, label, fmt_stats(da), seed_cluster_p([(t, arms[(tag, t)][0]) for t in ts]), fmt_stats(v),
                seed_cluster_p(ex), spearman(da, [B[t] for t in ts]) if len(set(da)) > 1 else float("nan")))
            if tag != "fmDRY":
                for lab, BX in (("b30", B30), ("b90", B90)):
                    ex2 = [(t, arms[(tag, t)][0] - BX[t]) for t in ts]
                    v2 = [z for _, z in ex2]
                    print("    %-5s %-8s                                                                   "
                          "   d_arm - %s %s p %.3f || spearman(d_arm, %s) %.2f" % (
                              "", "", lab, fmt_stats(v2), seed_cluster_p(ex2), lab,
                              spearman(da, [BX[t] for t in ts]) if len(set(da)) > 1 else float("nan")))
    if args.json:
        with open(args.json + ".reroll.json", "w", encoding="utf-8", newline=NL) as f:
            json.dump({"b": {"%s_%s_%d" % t: v for t, v in B.items()}, "b30": {"%s_%s_%d" % t: v for t, v in B30.items()},
                       "b90": {"%s_%s_%d" % t: v for t, v in B90.items()},
                       "arms": {"%s|%s_%s_%d" % ((k[0],) + k[1]): v for k, v in arms.items()}}, f)
    return B, B30, B90, arms


def kernel():
    ks = []
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if (dx or dy) and dx * dx + dy * dy <= 9:
                ks.append((dx, dy))
    return ks


def front_mask(np, burning, blocked):
    """burning, blocked: bool arrays (50, 50) indexed [x, y]. p > 0 iff some burning cell within
    euclidean 3 (grid is not a torus) and the cell itself is neither burning nor blocked."""
    B = np.zeros((W + 6, W + 6), dtype=bool)
    B[3:-3, 3:-3] = burning
    near = np.zeros((W, W), dtype=bool)
    for dx, dy in kernel():
        near |= B[3 + dx:3 + dx + W, 3 + dy:3 + dy + W]
    return near & ~burning & ~blocked


def analyze_arms(args):
    import numpy as np
    import _firemech_analyze as FA  # noqa: E402
    od = args.outdir
    print("G. WRITING ARMS: THE ACTUAL DRAW OFFSET OF FRONT CELLS (stock fmF / fmES, all writes replayed)")
    print("   offset(u, tick t) = (arm draws consumed before u's draw at t) - (OFF draws consumed before u's draw")
    print("   at t), both counted from step 1 = cumulative (sum over earlier ticks of arm drawers - OFF drawers)")
    print("   + within tick (OFF burnt cells with lower uid - arm burnt cells with lower uid).")
    print("   front cell (arm) = not burnt, not burning, not cleared before t, with a burning cell within")
    print("   euclidean 3 at the start of tick t (exactly the cells with p > 0 unless fuel is 0).")
    print("   k > 0 means the arm's front cell reads a LATER number than OFF's cell at that position would.")
    pinned = {}
    if args.pinned_txt and os.path.exists(args.pinned_txt):
        print("   (pinned numbers: from %s)" % args.pinned_txt)
    res = []
    for tag in ("fmF", "fmES"):
        for t in TUPLES:
            pa = wr_json(od, tag, t)
            po = off_json(od, t)
            if not (os.path.exists(pa) and os.path.exists(po)):
                continue
            a, o = load(pa), load(po)
            ok = a["digest_vs_arm"]["matched"] == a["digest_vs_arm"]["compared"] == STEPS
            SA = FA.run_summary(load(R.arm_path(tag, *t)), None)
            SO = FA.run_summary(load(R.arm_path("fmOFF", *t)), None)
            burnA, burnO = burnt_sets(a), burnt_sets(o)
            bingA = burning_sets(a)
            dA = dict((x, y) for x, y in a["draws_per_tick"])
            dO = dict((x, y) for x, y in o["draws_per_tick"])
            clears = sorted((w["step"], w["cell"]) for w in a["writes_selected"] if w["applied"])
            first_write = min((w["step"] for w in a["writes_selected"]), default=None)
            cum = 0
            series = {}
            first_shift = None
            ci = 0
            cleared = np.zeros((W, W), dtype=bool)
            for tick in range(SPEED, STEPS + 1, SPEED):
                if dA[tick] != dO[tick] and first_shift is None:
                    first_shift = tick
                prevA = burnA[tick - 2] if tick >= 2 else frozenset()
                prevO = burnO[tick - 2] if tick >= 2 else frozenset()
                if len(prevA) != N - dA[tick] or len(prevO) != N - dO[tick]:
                    raise SystemExit("burnt-set / draws_per_tick disagreement %s %s tick %d" % (tag, t, tick))
                while ci < len(clears) and clears[ci][0] < tick:
                    cleared[clears[ci][1][0], clears[ci][1][1]] = True
                    ci += 1
                bA = np.zeros(N, dtype=np.int64)
                bO = np.zeros(N, dtype=np.int64)
                if prevA:
                    bA[list(prevA)] = 1
                if prevO:
                    bO[list(prevO)] = 1
                cA = np.concatenate(([0], np.cumsum(bA)[:-1]))
                cO = np.concatenate(([0], np.cumsum(bO)[:-1]))
                offv = cum + (cO - cA)
                burning = np.zeros(N, dtype=bool)
                sb = bingA[tick - 2] if tick >= 2 else frozenset(a["initial_burning"])
                if sb:
                    burning[list(sb)] = True
                fm = front_mask(np, burning.reshape(W, W), bA.reshape(W, W).astype(bool) | cleared).reshape(N)
                vals = offv[fm]
                series[tick] = (len(vals), float(vals.mean()) if len(vals) else 0.0,
                                int((vals > 0).sum()), int((vals < 0).sum()))
                cum += dA[tick] - dO[tick]
            ticks_after = [tk for tk in series if first_shift is not None and tk >= first_shift and series[tk][0]]
            early = [tk for tk in ticks_after if tk < first_shift + 30]
            wmean = (sum(series[tk][1] * series[tk][0] for tk in ticks_after) / sum(series[tk][0] for tk in ticks_after)
                     if ticks_after else 0.0)
            emean = (sum(series[tk][1] * series[tk][0] for tk in early) / sum(series[tk][0] for tk in early)
                     if early else 0.0)
            pin_p = wr_json(od, tag, t, pinned=True)
            d_pin = None
            pin_fail = pin_sel = None
            if os.path.exists(pin_p):
                rp = load(pin_p)
                d_pin = rp["final"]["intact"] - SO["intact"]
                pin_fail, pin_sel = len(rp["writes_failed"]), len(rp["writes_selected"])
            res.append({"tag": tag, "t": t, "ok": ok, "d_all": SA["intact"] - SO["intact"], "d_pin": d_pin,
                        "pin_fail": pin_fail, "pin_sel": pin_sel,
                        "first_write": first_write, "first_shift": first_shift, "series": series,
                        "wmean": wmean, "emean": emean, "cum240": cum,
                        "intact_check": a["final"]["intact"] == SA["intact"]})
    BB, BB30, BB90 = reroll_baseline(od)
    for tag in ("fmF", "fmES"):
        xs = [x for x in res if x["tag"] == tag]
        if not xs:
            continue
        print("")
        print("  %s  (n=%d tuples with >= 1 write; replay digest 240/240 vs arm: %d; replay intact == analyzer: %d)" % (
            tag, len(xs), sum(1 for x in xs if x["ok"]), sum(1 for x in xs if x["intact_check"])))
        print("   %-16s %6s %6s %6s %6s %6s | %7s %7s %7s | mean front offset at step:" % (
            "tuple", "d_all", "d_pin", "resid", "write1", "shift1", "early30", "wmean", "cum240"))
        show = (30, 60, 90, 120, 150, 180, 210, 240)
        print("   %-16s %6s %6s %6s %6s %6s | %7s %7s %7s | %s" % ("", "", "", "", "", "", "", "", "",
                                                                  " ".join("%6d" % s for s in show)))
        for x in xs:
            resid = (x["d_all"] - x["d_pin"]) if x["d_pin"] is not None else None
            print("   %-16s %+6d %6s %6s %6s %6s | %+7.1f %+7.1f %+7d | %s" % (
                "%s/%s/%d" % x["t"], x["d_all"], "%+d" % x["d_pin"] if x["d_pin"] is not None else "?",
                "%+d" % resid if resid is not None else "?", x["first_write"], x["first_shift"], x["emean"], x["wmean"],
                x["cum240"], " ".join(("%+6.1f" % x["series"][s][1]) if x["series"][s][0] else "     -" for s in show)))
        print("   over runs, per step: mean of the per-run front-cell mean offset; runs with mean > 0 / < 0;"
              " front cells with offset > 0 / < 0 (pooled)")
        for s in show:
            v = [x["series"][s][1] for x in xs if x["series"][s][0]]
            print("     step %3d: mean %+8.2f  runs +/- %2d/%2d  cells +/- %6d/%6d  (runs with front cells %d)" % (
                s, mean(v) if v else float("nan"), sum(1 for z in v if z > 0), sum(1 for z in v if z < 0),
                sum(x["series"][s][2] for x in xs), sum(x["series"][s][3] for x in xs), len(v)))
        e = [x["emean"] for x in xs if x["first_shift"] is not None]
        wv = [x["wmean"] for x in xs if x["first_shift"] is not None]
        print("   first 30 steps after the first draw-count difference: mean of per-run mean %+.2f, runs +/-/0 %d/%d/%d;"
              " whole run from that tick: %+.2f, runs +/-/0 %d/%d/%d; no draw-count difference by 240: %d" % (
                  mean(e), sum(1 for z in e if z > 0), sum(1 for z in e if z < 0), sum(1 for z in e if z == 0),
                  mean(wv), sum(1 for z in wv if z > 0), sum(1 for z in wv if z < 0), sum(1 for z in wv if z == 0),
                  sum(1 for x in xs if x["first_shift"] is None)))
        dd = [x for x in xs if x["first_shift"] is not None]
        if len(dd) >= 3:
            print("   endogeneity: spearman(whole-run front offset, d_all) = %.2f; spearman(early30, d_all) = %.2f (n=%d)" % (
                spearman([x["wmean"] for x in dd], [x["d_all"] for x in dd]),
                spearman([x["emean"] for x in dd], [x["d_all"] for x in dd]), len(dd)))
        rp = [x for x in dd if x["d_pin"] is not None]
        if len(rp) >= 3:
            resid = [x["d_all"] - x["d_pin"] for x in rp]
            conc_e = sum(1 for x, r in zip(rp, resid) if x["emean"] * r > 0)
            opp_e = sum(1 for x, r in zip(rp, resid) if x["emean"] * r < 0)
            conc_w = sum(1 for x, r in zip(rp, resid) if x["wmean"] * r > 0)
            opp_w = sum(1 for x, r in zip(rp, resid) if x["wmean"] * r < 0)
            print("   residual (stock d_all - pinned d_pin): sum %+d mean %+.1f +/-/0 %d/%d/%d; sign(early30 offset) =="
                  " sign(resid) %d, opposite %d; sign(whole-run offset) == sign(resid) %d, opposite %d;"
                  " spearman(early30, resid) %.2f, spearman(whole-run, resid) %.2f (n=%d)" % (
                      sum(resid), mean(resid), sum(1 for z in resid if z > 0), sum(1 for z in resid if z < 0),
                      sum(1 for z in resid if z == 0), conc_e, opp_e, conc_w, opp_w,
                      spearman([x["emean"] for x in rp], resid), spearman([x["wmean"] for x in rp], resid), len(rp)))
            print("   pinned replays: selected writes %d, not landed %d (%.1f%%)" % (
                sum(x["pin_sel"] for x in rp), sum(x["pin_fail"] for x in rp),
                100.0 * sum(x["pin_fail"] for x in rp) / max(1, sum(x["pin_sel"] for x in rp))))
            rb = [x for x in rp if x["t"] in BB]
            if len(rb) >= 3:
                rr = [x["d_all"] - x["d_pin"] for x in rb]
                for lab, BX in (("b (all 6 offset arms)", BB), ("b30", BB30), ("b90", BB90)):
                    bv = [BX[x["t"]] for x in rb]
                    print("   residual vs the tuple's pure re-roll baseline %-22s: spearman %.2f pearson %.2f | sum resid %+d"
                          " vs sum baseline %+.0f | resid - baseline %s p %.3f (n=%d)" % (
                              lab, spearman(rr, bv), pearson(rr, bv), sum(rr), sum(bv),
                              fmt_stats([a - b for a, b in zip(rr, bv)]),
                              seed_cluster_p([(x["t"], a - b) for x, a, b in zip(rb, rr, bv)]), len(rb)))
                for lab, sel in (("canon", CANON_SEEDS), ("fresh", tuple(s for s in SEEDS if s not in CANON_SEEDS))):
                    ss = [(x, a) for x, a in zip(rb, rr) if x["t"][2] in sel]
                    if ss:
                        print("     %s: n=%d sum d_all %+d, sum d_pin %+d, sum resid %+d, sum b %+.0f, sum b30 %+.0f, sum b90 %+.0f" % (
                            lab, len(ss), sum(x["d_all"] for x, _ in ss), sum(x["d_pin"] for x, _ in ss),
                            sum(a for _, a in ss), sum(BB[x["t"]] for x, _ in ss), sum(BB30[x["t"]] for x, _ in ss),
                            sum(BB90[x["t"]] for x, _ in ss)))
    if args.json:
        with open(args.json + ".arms.json", "w", encoding="utf-8", newline=NL) as f:
            json.dump([{k2: (v if k2 != "series" else {str(a): b for a, b in v.items()}) for k2, v in x.items()}
                       for x in res], f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--tuple", nargs=3)
    ap.add_argument("--T", type=int, default=240)
    ap.add_argument("--k", type=int, default=0)
    ap.add_argument("--rec-ticks", default="")
    ap.add_argument("--ref-draws", default="")
    ap.add_argument("--save-draws", default="")
    ap.add_argument("--out")
    ap.add_argument("--batch", choices=["validate", "off", "main", "k3", "rep", "arms", "pinned"])
    ap.add_argument("--analyze", choices=["offset", "mechanism", "reroll", "arms", "all"])
    ap.add_argument("--outdir")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--json", default="")
    ap.add_argument("--pinned-txt", default="")
    args = ap.parse_args()
    if args.run:
        return run_one(args)
    if args.batch:
        return run_batch(args)
    if args.analyze:
        if args.analyze in ("offset", "all"):
            analyze_offset(args)
        if args.analyze in ("mechanism", "all"):
            analyze_mechanism(args)
        if args.analyze in ("reroll", "all"):
            analyze_reroll(args)
        if args.analyze in ("arms", "all"):
            analyze_arms(args)
        return 0
    ap.error("one of --run, --batch, --analyze")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
