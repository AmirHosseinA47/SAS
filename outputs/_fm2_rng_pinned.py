"""firemech round 2 - TASK P: how much of the STOCK fire effect of firefighter writes is physical?

Out of tree, read-only on every existing file. Drives outputs/_fm2_fire_replay.py (the validated
fire-only replay instrument) as a subprocess, ONE replay process at a time, every start gated on
FreeVirtualMemory >= 4,000,000 kB, and analyses its outputs.

For every arm tuple with >= 1 recorded write (fmF, fmFS, fmES, fmEFS; canonical 13 + fresh 10) it
replays the arm's FULL recorded write schedule with --pin-draws <that tuple's recorded fmOFF
no-write draws>: every cell that drew at a tick in fmOFF draws exactly that value again, so the
writes can change the fire only physically (no draw-stream re-roll). It then compares, per run:
  stock  = the recorded arm (harness JSON; == stock replay --writes all, validated)
  pinned = the pinned full-schedule replay
  OFF    = fmOFF (harness JSON for intact; the recorded no-write replay for burnt timing)
and decomposes  d_stock = d_pin + residual  (d = intact - intact(fmOFF), analyzer definition).

Sanity runs: fmOFF --writes none --pin-draws on 2 tuples (must equal fmOFF 240/240), and 2 stock
--writes all spot checks of fmFS arms (not in the instrument's validation set).

Landed-subset stock replays (firebreak arms, runs where some recorded write misses the pinned fire): the
STOCK fire replayed with only the writes that landed under pinning, to separate the draw-stream coupling
from the open-loop schedule mismatch (see the block above replay_subset).

usage
  run    : _fm2_rng_pinned.py --run        [--outdir DIR] [--draws-src DIR]
  subset : _fm2_rng_pinned.py --run-subset [--outdir DIR]      (after --run)
  offset : _fm2_rng_pinned.py --run-offset [--outdir DIR]      (after --run; pure draw-stream offset, no writes)
  report : _fm2_rng_pinned.py --report     [--outdir DIR] [--draws-src DIR] --out FILE [--json ROWS.json]
  (internal) --replay-subset --tag TAG --tuple wind/rr/seed --which all|landed --outdir DIR --out OUT.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")
REPLAY = os.path.join(HERE, "_fm2_fire_replay.py")
SCRATCH = r"C:\Users\ahrar\AppData\Local\Temp\claude\E--Projects-SAS\4822f5f0-3ec2-4a14-8aeb-d97eb91ddf5a\scratchpad"
OUTDIR_DEFAULT = os.path.join(SCRATCH, "taskP", "replay")
DRAWS_SRC_DEFAULT = os.path.join(SCRATCH, "replay")
MIN_FREE_KB = 4000000
NL = "\n"
CELLS = 2500

sys.path.insert(0, HERE)
import _fm2_fire_replay as FR  # noqa: E402

CANON = FR.CANON
FRESH = FR.FRESH
ARMS = ("fmF", "fmFS", "fmES", "fmEFS")
FIREBREAK_ARMS = ("fmF", "fmFS")
SANITY_NONE = (("east", "half", 404), ("south", "half", 303))
SPOT_STOCK = (("fmFS", ("east", "half", 101)), ("fmFS", ("south", "half", 303)))


def tlabel(t):
    return "%s/%s/%d" % t


def arm_path(tag, t):
    return FR.arm_path(tag, *t)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


_WCACHE = {}


def write_rows(tag, t):
    key = (tag, t)
    if key not in _WCACHE:
        d = load(arm_path(tag, t))
        _WCACHE[key] = [r for r in (d.get("firefight_log") or []) if r.get("wrote")]
    return _WCACHE[key]


def rec_off_json(src, t):
    return os.path.join(src, "rp_fmOFF_%s_%s_%d_none.json" % t)


def draws_src(src, t):
    return os.path.join(src, "rp_fmOFF_%s_%s_%d_none.draws" % t)


def draws_local(outdir, t):
    return os.path.join(os.path.dirname(outdir), "draws", "fmOFF_%s_%s_%d_none.draws" % t)


def out_pin(outdir, tag, t, spec):
    return os.path.join(outdir, "pin_%s_%s_%s_%d_%s.json" % ((tag,) + t + (spec,)))


def out_stock(outdir, tag, t):
    return os.path.join(outdir, "stock_%s_%s_%s_%d_all.json" % ((tag,) + t))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_tuples(tag):
    return [t for t in CANON + FRESH if write_rows(tag, t)]


def jobs_list(outdir):
    jobs = []
    for t in SANITY_NONE:
        jobs.append({"kind": "pin", "tag": "fmOFF", "t": t, "spec": "none", "out": out_pin(outdir, "fmOFF", t, "none")})
    for tag in ARMS:
        for t in write_tuples(tag):
            jobs.append({"kind": "pin", "tag": tag, "t": t, "spec": "all", "out": out_pin(outdir, tag, t, "all")})
    for tag, t in SPOT_STOCK:
        jobs.append({"kind": "stock", "tag": tag, "t": t, "spec": "all", "out": out_stock(outdir, tag, t)})
    return jobs


# ================================================================================ run ===
def run(args):
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(os.path.dirname(draws_local(outdir, CANON[0])), exist_ok=True)
    log = open(os.path.join(os.path.dirname(outdir), "run.log"), "a", encoding="utf-8", newline=NL)

    def say(msg):
        line = time.strftime("%H:%M:%S ") + msg
        print(line, flush=True)
        log.write(line + NL)
        log.flush()

    # private copies of the recorded fmOFF draws (sha-checked), so later edits elsewhere cannot move them
    need = sorted(set(j["t"] for j in jobs_list(outdir) if j["kind"] == "pin"))
    for t in need:
        dst = draws_local(outdir, t)
        src = draws_src(args.draws_src, t)
        if not os.path.exists(dst):
            shutil.copyfile(src, dst + ".tmp")
            os.replace(dst + ".tmp", dst)
        if sha256_file(dst) != sha256_file(src):
            say("DRAWS COPY MISMATCH %s" % dst)
            return 2
    jobs = [j for j in jobs_list(outdir) if not os.path.exists(j["out"])]
    say("task P run: %d jobs pending of %d, one replay process at a time" % (len(jobs), len(jobs_list(outdir))))
    t0 = time.time()
    for j in jobs:
        while True:
            fk = FR.free_kb()
            if fk >= MIN_FREE_KB:
                break
            say("free commit %d kB < %d, waiting" % (fk, MIN_FREE_KB))
            time.sleep(20)
        cmd = [PY, REPLAY, "--arm-json", arm_path(j["tag"], j["t"]), "--writes", j["spec"], "--out", j["out"]]
        if j["kind"] == "pin":
            cmd += ["--pin-draws", draws_local(outdir, j["t"])]
        errp = j["out"][:-5] + ".log"
        ts = time.time()
        with open(errp, "w", encoding="utf-8", newline=NL) as errf:
            say("start (free %d kB) %s %s %s %s" % (fk, j["kind"], j["tag"], tlabel(j["t"]), j["spec"]))
            rc = subprocess.run(cmd, stdout=errf, stderr=subprocess.STDOUT, cwd=REPO).returncode
        ok = os.path.exists(j["out"])
        say("done rc=%d out=%s %.0fs %s" % (rc, ok, time.time() - ts, os.path.basename(j["out"])))
    say("task P run finished in %.0fs" % (time.time() - t0))
    log.close()
    return 0


# ============================================================================= report ===
def sign(x):
    return (x > 0) - (x < 0)


def sign_test_p(pos, neg):
    """Exact two-sided sign test on the nonzero values."""
    n = pos + neg
    if n == 0:
        return None
    k = min(pos, neg)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / float(2 ** n)
    return min(1.0, 2.0 * tail)


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def median(v):
    v = sorted(v)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2.0


def harness_sets(d):
    """Final has_burned and cleared cell sets of a harness JSON (analyzer definitions)."""
    fgf = d.get("fire_ground_final") or {}
    hb = set(tuple(int(v) for v in k.split(",")) for k, v in fgf.items() if v[0])
    clear_targets = set((int(r["target"][0]), int(r["target"][1])) for r in (d.get("firefight_log") or [])
                        if r.get("wrote") and r["action"] == "clear")
    cleared = clear_targets - hb
    return hb, cleared


def components(hb_off, hb_x, cl_x):
    saved = len(hb_off - hb_x - cl_x)
    extra = len(hb_x - hb_off)
    wasted = len(cl_x - hb_off)
    return saved, extra, wasted


def analyse_pin_run(outdir, src, tag, t, FA, off_cache):
    rp_path = out_pin(outdir, tag, t, "all")
    if not os.path.exists(rp_path):
        return None
    rp = load(rp_path)
    arm = load(arm_path(tag, t))
    off = load(arm_path("fmOFF", t))
    SA, SO = FA.run_summary(arm, None), FA.run_summary(off, None)
    if t not in off_cache:
        off_cache.clear()
        recj = load(rec_off_json(src, t))
        off_cache[t] = (FR.load_trace(rec_off_json(src, t)), recj)
    O, recj = off_cache[t]
    P = FR.load_trace(rp_path)
    cells = [(c[1], c[2]) for c in rp["fires"]]
    uid_of = {(c[1], c[2]): c[0] for c in rp["fires"]}
    rows = [r for r in (arm.get("firefight_log") or []) if r.get("wrote")]
    sel = rp["writes_selected"]
    assert len(sel) == len(rows)

    R = {"tag": tag, "t": t, "sample": "canon" if t in CANON else "fresh", "wind": t[0], "rr": t[1]}
    R["intact_off"], R["intact_stock"], R["intact_pin"] = SO["intact"], SA["intact"], rp["final"]["intact"]
    R["off_rec_intact_ok"] = (O["final"]["intact"] == SO["intact"]
                              and recj["digest_vs_arm"]["matched"] == recj["digest_vs_arm"]["compared"] == 240)
    R["d_stock"] = SA["intact"] - SO["intact"]
    R["d_pin"] = rp["final"]["intact"] - SO["intact"]
    R["resid"] = R["d_stock"] - R["d_pin"]
    R["n_ext"] = sum(1 for r in rows if r["action"] == "extinguish")
    R["n_clear"] = sum(1 for r in rows if r["action"] == "clear")
    R["land_ext"] = sum(1 for w in sel if w["action"] == "extinguish" and w["applied"])
    R["land_clear"] = sum(1 for w in sel if w["action"] == "clear" and w["applied"])
    R["fallback"] = rp["pin_counts"]["fallback"]
    R["pinned_draws"] = rp["pin_counts"]["pinned"]
    R["first_write"] = rows[0]["step"]
    R["first_write_applied"] = sel[0]["applied"]

    # ---- failure causes, from the pinned trace's own state at the write step
    landed_before = {}
    causes = {}
    fail_detail = []
    for w in sel:
        cell = tuple(w["cell"])
        s = w["step"]
        k = s - 1
        if w["applied"]:
            landed_before.setdefault(cell, []).append(w["i"])
            continue
        burnt_p = cell in P["burnt"][k]
        burning_p = cell in P["burning"][k]
        prior = [i for i in landed_before.get(cell, []) if i < w["i"]]
        ever_p = any(cell in P["burning"][j] for j in range(0, k + 1))
        off_burning = cell in O["burning"][k]
        off_burnt = cell in O["burnt"][k]
        off_ever = any(cell in O["burning"][j] for j in range(0, k + 1))
        if burnt_p:
            c = "burnt"
        elif prior:
            c = "already-written"
        elif w["action"] == "clear":
            c = "burning" if burning_p else "UNEXPLAINED"
        else:
            if burning_p:
                c = "UNEXPLAINED"
            elif ever_p:
                c = "burned-earlier-not-burning"
            else:
                later = any(cell in P["burning"][j] for j in range(k + 1, len(P["burning"])))
                c = "fire-not-yet-there" if later else "fire-never-there"
        key = w["action"] + ":" + c
        causes[key] = causes.get(key, 0) + 1
        fail_detail.append({"i": w["i"], "step": s, "action": w["action"], "cell": list(cell), "cause": c,
                            "off_burning": off_burning, "off_burnt": off_burnt, "off_ever_by_step": off_ever})
    R["fail_causes"] = causes
    R["first_fail_step"] = min((f["step"] for f in fail_detail), default=None)
    odd = []
    for f in fail_detail:
        if f["action"] == "clear" and not (f["off_burning"] or f["off_burnt"]):
            c = tuple(f["cell"])
            k = f["step"] - 1
            p_on = [j + 1 for j in range(len(P["burning"])) if c in P["burning"][j] and (j == 0 or c not in P["burning"][j - 1])]
            o_on = [j + 1 for j in range(len(O["burning"])) if c in O["burning"][j] and (j == 0 or c not in O["burning"][j - 1])]
            o_off = [j + 1 for j in range(1, len(O["burning"])) if c not in O["burning"][j] and c in O["burning"][j - 1]]
            p_bt = next((j + 1 for j in range(len(P["burnt"])) if c in P["burnt"][j]), None)
            o_bt = next((j + 1 for j in range(len(O["burnt"])) if c in O["burnt"][j]), None)
            odd.append(dict(f, pinned_ignitions=p_on[:6], off_ignitions=o_on[:6], off_goes_out=o_off[:6],
                            pinned_burnt_step=p_bt, off_burnt_step=o_bt))
    R["fail_odd"] = odd
    R["fail_off_state"] = {
        "clear_fail_off_burning_or_burnt": sum(1 for f in fail_detail if f["action"] == "clear"
                                               and (f["off_burning"] or f["off_burnt"])),
        "clear_fail": sum(1 for f in fail_detail if f["action"] == "clear"),
        "ext_fail_off_burning": sum(1 for f in fail_detail if f["action"] == "extinguish" and f["off_burning"]),
        "ext_fail": sum(1 for f in fail_detail if f["action"] == "extinguish"),
    }

    # ---- final-state components vs OFF: saved / extra burned / wasted clears
    hb_off = O["has_burned"]
    hb_p = P["has_burned"]
    cl_p = set(cells[i] for i in rp["final_cleared"])
    hb_a, cl_a = harness_sets(arm)
    R["cleared_set_ok"] = (len(cl_a) == int(arm.get("fire_cleared_unburned_final") or 0))
    R["comp_pin"] = components(hb_off, hb_p, cl_p)
    R["comp_stock"] = components(hb_off, hb_a, cl_a)
    assert R["comp_pin"][0] - R["comp_pin"][1] - R["comp_pin"][2] == R["d_pin"], (tag, t, R["comp_pin"], R["d_pin"])
    R["comp_stock_ok"] = (R["comp_stock"][0] - R["comp_stock"][1] - R["comp_stock"][2] == R["d_stock"])
    R["hb_symdiff_stock_vs_pin"] = len(hb_a ^ hb_p)
    R["hb_symdiff_pin_vs_off"] = len(hb_p ^ hb_off)
    R["hb_symdiff_stock_vs_off"] = len(hb_a ^ hb_off)

    # ---- physical monotonicity vs OFF
    n = min(len(P["burning"]), len(O["burning"]))
    fb = next((k + 1 for k in range(n) if P["burnt"][k] != O["burnt"][k]), None)
    first_viol = next((k + 1 for k in range(n) if P["burning"][k] - O["burning"][k]), None)
    viol_before = sum(1 for k in range(n) if (fb is None or k + 1 < fb) and (P["burning"][k] - O["burning"][k]))
    R["first_burnt_diff"] = fb
    # stock vs pinned: identical draws (hence identical fire) until the stock draw stream first shifts, which
    # cannot happen before the tick after the first burnt-set difference (fb + FIRE_SPREAD_SPEED)
    ad = arm.get("fire_digests") or []
    R["stock_pin_first_digest_div"] = next((k + 1 for k in range(min(len(ad), len(rp["digests"])))
                                            if ad[k] != rp["digests"][k]), None)
    R["stock_pin_digest_matched"] = sum(1 for k in range(min(len(ad), len(rp["digests"]))) if ad[k] == rp["digests"][k])
    R["first_burning_diff"] = next((k + 1 for k in range(n) if P["burning"][k] != O["burning"][k]), None)
    R["first_extra_burning"] = first_viol
    R["viol_steps_before_fb"] = viol_before
    R["extra_burning_steps_total"] = sum(1 for k in range(n) if P["burning"][k] - O["burning"][k])
    cause = None
    if first_viol is not None:
        v = first_viol
        k = v - 1
        extra = sorted(P["burning"][k] - O["burning"][k])
        speed = rp["spread_speed"]
        tick = (v % speed == 0)

        def read_state(T, kk):
            # burning state a cell reads during step v's tick: burning at end of step v-1, minus cells that
            # burned out at step v (burnt_new at v) - only those with a LOWER uid are already updated when a
            # given cell reads, which is resolved per reader below
            prev = T["burning"][kk - 1] if kk >= 1 else frozenset()
            newb = (T["burnt"][kk] - (T["burnt"][kk - 1] if kk >= 1 else frozenset()))
            return prev, newb

        pp, pnew = read_state(P, k)
        op, onew = read_state(O, k)
        cls = {"off-burnt-pin-not": 0, "extra-burning-neighbour-at-read": 0, "unexplained": 0}
        ex_examples = []
        for c in extra:
            u = uid_of[c]
            if (c in O["burnt"][k]) and (c not in P["burnt"][k]):
                cls["off-burnt-pin-not"] += 1
                continue
            found = None
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    if dx * dx + dy * dy > 9 or (dx == 0 and dy == 0):
                        continue
                    nb = (c[0] + dx, c[1] + dy)
                    if nb not in uid_of:
                        continue
                    lower = uid_of[nb] < u
                    p_read = (nb in pp) and not (lower and nb in pnew)
                    o_read = (nb in op) and not (lower and nb in onew)
                    if p_read and not o_read:
                        found = nb
                        break
                if found:
                    break
            if found is not None:
                cls["extra-burning-neighbour-at-read"] += 1
                if len(ex_examples) < 2:
                    ex_examples.append({"cell": list(c), "neighbour": list(found),
                                        "nb_burning_off_prev": found in op, "nb_burnt_new_off": found in onew})
            else:
                cls["unexplained"] += 1
        cause = {"step": v, "tick_step": tick, "n_extra": len(extra), "classes": cls, "examples": ex_examples,
                 "fb": fb, "v_minus_fb": (v - fb) if fb is not None else None}
    R["viol_cause"] = cause
    return R


def analyse(args, out):
    sys.path.insert(0, HERE)
    import _firemech_analyze as FA  # noqa: E402
    outdir, src = args.outdir, args.draws_src

    def say(s=""):
        out.append(s)
        print(s)

    # ------------------------------------------------------------ inputs / references
    say("INPUT CHECKS")
    for t in CANON + FRESH:
        if t in [x for x in CANON + FRESH if any(write_rows(tag, x) for tag in ARMS)]:
            rj = rec_off_json(src, t)
            dl = draws_local(outdir, t)
            if not (os.path.exists(rj) and os.path.exists(dl)):
                say("  %-16s recorded OFF replay or draws MISSING" % tlabel(t))
                continue
            r = load(rj)
            vals = array("d")
            with open(dl, "rb") as f:
                vals.frombytes(f.read())
            per_tick = []
            for kk in range(80):
                row = vals[kk * 2500:(kk + 1) * 2500]
                per_tick.append(sum(1 for x in row if x == x))
            dpt = [x[1] for x in r["draws_per_tick"]]
            say("  %-16s rec fmOFF replay digest %d/%d intact %d | draws file sha %s.. non-NaN per tick == draws_per_tick %s"
                " (total %d) | sha == source %s" % (
                    tlabel(t), r["digest_vs_arm"]["matched"], r["digest_vs_arm"]["compared"], r["final"]["intact"],
                    sha256_file(dl)[:12], per_tick == dpt, sum(per_tick),
                    sha256_file(dl) == sha256_file(draws_src(src, t))))
    for tag in ARMS:
        zero = [t for t in CANON + FRESH if not write_rows(tag, t)]
        parts = []
        for t in zero:
            a, o = load(arm_path(tag, t)), load(arm_path("fmOFF", t))
            m = sum(1 for x, y in zip(a["fire_digests"], o["fire_digests"]) if x == y)
            dI = FA.run_summary(a, None)["intact"] - FA.run_summary(o, None)["intact"]
            parts.append("%s %d/240 d_intact %+d" % (tlabel(t), m, dI))
        say("  zero-write tuples %-5s (fire digests arm vs fmOFF, harness JSONs): %s" % (tag, "; ".join(parts)))

    # ------------------------------------------------------------ sanity
    say("")
    say("SANITY 1  pinned --writes none on fmOFF (its own recorded draws) must equal fmOFF 240/240")
    for t in SANITY_NONE:
        p = out_pin(outdir, "fmOFF", t, "none")
        if not os.path.exists(p):
            say("  %s MISSING" % tlabel(t))
            continue
        r = load(p)
        off = load(arm_path("fmOFF", t))
        SO = FA.run_summary(off, None)
        C = FR.compare(FR.load_trace(p), FR.load_trace(arm_path("fmOFF", t)))
        say("  %-16s digest vs fmOFF JSON %d/%d first_mismatch %s | compare: digest %d/%d first burning diff %s "
            "has_burned symdiff %d | intact replay %d fmOFF %d | pinned %d fallback %d | wall %.1fs" % (
                tlabel(t), r["digest_vs_arm"]["matched"], r["digest_vs_arm"]["compared"],
                r["digest_vs_arm"]["first_mismatch"], C["digest_matched"], C["digest_compared"],
                C["first_burning_diff"], C["final_has_burned_symdiff"], r["final"]["intact"], SO["intact"],
                r["pin_counts"]["pinned"], r["pin_counts"]["fallback"], r["wall_s"]["total"]))
    say("SANITY 1b stock --writes all spot checks of fmFS arms (outside the instrument's validation set)")
    for tag, t in SPOT_STOCK:
        p = out_stock(outdir, tag, t)
        if not os.path.exists(p):
            say("  %s %s MISSING" % (tag, tlabel(t)))
            continue
        r = load(p)
        SA = FA.run_summary(load(arm_path(tag, t)), None)
        say("  %-5s %-16s digest vs arm %d/%d | selected %d failed %d | ever/cleared/intact replay %d/%d/%d analyzer "
            "%d/%d/%d" % (tag, tlabel(t), r["digest_vs_arm"]["matched"], r["digest_vs_arm"]["compared"],
                          len(r["writes_selected"]), len(r["writes_failed"]), r["final"]["ever"], r["final"]["cleared"],
                          r["final"]["intact"], SA["ever"], SA["cleared"], SA["intact"]))

    # ------------------------------------------------------------ per run
    rows = []
    off_cache = {}
    for tag in ARMS:
        for t in CANON + FRESH:
            if not write_rows(tag, t):
                o = load(arm_path("fmOFF", t))
                a = load(arm_path(tag, t))
                dI = FA.run_summary(a, None)["intact"] - FA.run_summary(o, None)["intact"]
                rows.append({"tag": tag, "t": t, "sample": "canon" if t in CANON else "fresh", "wind": t[0],
                             "rr": t[1], "zero_write": True, "d_stock": dI, "d_pin": 0, "resid": dI,
                             "n_ext": 0, "n_clear": 0, "land_ext": 0, "land_clear": 0})
                continue
            R = analyse_pin_run(outdir, src, tag, t, FA, off_cache)
            if R is None:
                say("  %s %s pinned output MISSING" % (tag, tlabel(t)))
                continue
            R["zero_write"] = False
            rows.append(R)

    say("")
    say("PER RUN  d = intact - intact(fmOFF); resid = d_stock - d_pin; land = landed/recorded writes under pinning")
    say("  comp = saved/extra/wasted vs fmOFF final state (saved: burned in OFF, neither burned nor cleared here;")
    say("  extra: burned here, not in OFF; wasted: cleared cell OFF never burned; d = saved - extra - wasted)")
    say("  fb = first step the burnt set differs from OFF; x1 = first step with a burning cell OFF lacks;")
    say("  vb = steps with such a cell BEFORE fb (must be 0); fbk = fallback draws (cells drawing where OFF was burnt)")
    say("  sdiv = first step the stock arm's fire digest differs from the pinned replay's (- = never)")
    for tag in ARMS:
        say("")
        say("  %-5s %-16s %6s %6s %6s | %9s %9s | %-15s %-15s | %5s %4s %4s %4s %4s %6s | %s" % (
            "arm", "tuple", "d_stk", "d_pin", "resid", "land_clr", "land_ext", "comp stock", "comp pin",
            "fb", "sdiv", "x1", "vb", "1stW", "fbk", "fail causes"))
        for R in [r for r in rows if r["tag"] == tag]:
            if R["zero_write"]:
                say("  %-5s %-16s %+6d %+6d %+6d | zero-write tuple (fire == fmOFF)" % (
                    tag, tlabel(R["t"]), R["d_stock"], R["d_pin"], R["resid"]))
                continue
            say("  %-5s %-16s %+6d %+6d %+6d | %4d/%-4d %4d/%-4d | %-15s %-15s | %5s %4s %4s %4d %4d %6d | %s" % (
                tag, tlabel(R["t"]), R["d_stock"], R["d_pin"], R["resid"], R["land_clear"], R["n_clear"],
                R["land_ext"], R["n_ext"], "%d/%d/%d" % R["comp_stock"], "%d/%d/%d" % R["comp_pin"],
                R["first_burnt_diff"] if R["first_burnt_diff"] is not None else "-",
                R["stock_pin_first_digest_div"] if R["stock_pin_first_digest_div"] is not None else "-",
                R["first_extra_burning"] if R["first_extra_burning"] is not None else "-",
                R["viol_steps_before_fb"], R["first_write"],
                R["fallback"], ", ".join("%s %d" % kv for kv in sorted(R["fail_causes"].items())) or "-"))

    # ------------------------------------------------------------ distributions
    def pick(tag, sample, wind=None):
        xs = [r for r in rows if r["tag"] == tag]
        if sample == "canon":
            xs = [r for r in xs if r["sample"] == "canon"]
        elif sample == "canon-dedup":
            xs = [r for r in xs if r["sample"] == "canon" and r["rr"] != "def"]
        elif sample == "fresh":
            xs = [r for r in xs if r["sample"] == "fresh"]
        elif sample == "dedup":
            xs = [r for r in xs if r["rr"] != "def"]
        if wind:
            xs = [r for r in xs if r["wind"] == wind]
        return xs

    def pnz(xs, key):
        return (sum(1 for r in xs if r[key] > 0), sum(1 for r in xs if r[key] < 0), sum(1 for r in xs if r[key] == 0))

    say("")
    say("POOLED  (all tuples of the sample incl. zero-write ones, which have d_stock = d_pin = 0; up/down/0 per run)")
    say("  %-5s %-12s %3s | %7s %-9s | %7s %-9s | %7s %-9s | %-10s %-10s | %s" % (
        "arm", "sample", "n", "d_stk", "u/d/0", "d_pin", "u/d/0", "resid", "u/d/0", "p(resid)", "p(d_pin)",
        "cross stock x pin: (s+,p+) (s+,p0) (s+,p-) (s0,p+) (s0,p0) (s0,p-) (s-,p+) (s-,p0) (s-,p-)"))
    for tag in ARMS:
        for sample in ("canon", "canon-dedup", "fresh", "counted", "dedup"):
            xs = pick(tag, sample)
            if not xs:
                continue
            a, b, c = pnz(xs, "d_stock")
            e, f, g = pnz(xs, "d_pin")
            h, i, j = pnz(xs, "resid")
            cross = []
            for ss in (1, 0, -1):
                for ps in (1, 0, -1):
                    cross.append(sum(1 for r in xs if sign(r["d_stock"]) == ss and sign(r["d_pin"]) == ps))
            pr, pp = sign_test_p(h, i), sign_test_p(e, f)
            say("  %-5s %-12s %3d | %+7d %-9s | %+7d %-9s | %+7d %-9s | %-10s %-10s | %s" % (
                tag, sample, len(xs), sum(r["d_stock"] for r in xs), "%d/%d/%d" % (a, b, c),
                sum(r["d_pin"] for r in xs), "%d/%d/%d" % (e, f, g), sum(r["resid"] for r in xs), "%d/%d/%d" % (h, i, j),
                ("%.4f" % pr) if pr is not None else "-", ("%.4f" % pp) if pp is not None else "-",
                " ".join("%d" % x for x in cross)))

    say("")
    say("LANDING under pinning (recorded writes that land on the pinned fire; all landed in the stock arm by definition)")
    for tag in ARMS:
        for sample in ("canon", "fresh", "counted", "dedup"):
            xs = [r for r in pick(tag, sample) if not r["zero_write"]]
            if not xs:
                continue
            nc, lc = sum(r["n_clear"] for r in xs), sum(r["land_clear"] for r in xs)
            ne, le = sum(r["n_ext"] for r in xs), sum(r["land_ext"] for r in xs)
            causes = {}
            for r in xs:
                for k, v in r["fail_causes"].items():
                    causes[k] = causes.get(k, 0) + v
            fo = {}
            for r in xs:
                for k, v in r["fail_off_state"].items():
                    fo[k] = fo.get(k, 0) + v
            say("  %-5s %-8s runs %2d | clears %4d/%-4d landed (%s) | extinguishes %4d/%-4d landed (%s) | first write "
                "landed %d/%d | failures: %s | failed clears with the target burning/burnt in OFF at that step %d/%d; "
                "failed extinguishes whose target WAS burning in OFF %d/%d" % (
                    tag, sample, len(xs), lc, nc, ("%.1f%%" % (100.0 * lc / nc)) if nc else "-", le, ne,
                    ("%.1f%%" % (100.0 * le / ne)) if ne else "-", sum(1 for r in xs if r["first_write_applied"]),
                    len(xs), ", ".join("%s %d" % kv for kv in sorted(causes.items())) or "none",
                    fo.get("clear_fail_off_burning_or_burnt", 0), fo.get("clear_fail", 0),
                    fo.get("ext_fail_off_burning", 0), fo.get("ext_fail", 0)))

    for r in rows:
        for f in r.get("fail_odd") or []:
            say("  failed clear whose target was neither burning nor burnt in OFF at that step: %s %s %s" % (
                r["tag"], tlabel(r["t"]), json.dumps(f)))
    say("")
    say("DECOMPOSITION (firebreak arms): d_stock = d_pin (physical) + resid (coupling / re-roll)")
    say("  %-5s %-22s %3s | %7s %7s %7s | resid: %-8s %7s %7s %8s %-9s | |resid| med %s | |d_pin| med %s" % (
        "arm", "subset", "n", "d_stk", "d_pin", "resid", "u/d/0", "mean", "median", "p(sign)", "min..max", "", ""))
    for tag in FIREBREAK_ARMS + ("fmES", "fmEFS"):
        for sample in ("counted", "dedup", "canon", "fresh"):
            for wind in (None, "east", "south"):
                xs = pick(tag, sample, wind)
                if not xs:
                    continue
                h, i, j = pnz(xs, "resid")
                rs = [r["resid"] for r in xs]
                p = sign_test_p(h, i)
                say("  %-5s %-22s %3d | %+7d %+7d %+7d | resid: %-8s %+7.1f %+7.1f %8s %-9s | |resid| med %s | |d_pin| "
                    "med %s" % (tag, sample + ("/" + wind if wind else "/all"), len(xs), sum(r["d_stock"] for r in xs),
                                sum(r["d_pin"] for r in xs), sum(rs), "%d/%d/%d" % (h, i, j), sum(rs) / len(rs),
                                median(rs), ("%.4f" % p) if p is not None else "-", "%+d..%+d" % (min(rs), max(rs)),
                                median([abs(x) for x in rs]), median([abs(r["d_pin"]) for r in xs])))
    # residual stratified by open-loop landing: a recorded write that misses the pinned fire is part of the
    # residual too (the closed-loop schedule was fitted to the re-rolled stock fire)
    say("  residual by open-loop landing (write tuples only; miss = recorded writes that did not land under pinning)")
    for tag in ARMS:
        xs = [r for r in rows if r["tag"] == tag and not r["zero_write"]]
        for wind in (None, "east", "south"):
            ys = [r for r in xs if wind is None or r["wind"] == wind]
            strata = (("all landed", [r for r in ys if r["land_clear"] + r["land_ext"] == r["n_clear"] + r["n_ext"]]),
                      ("1-10% missed", [r for r in ys if 0 < 1.0 - (r["land_clear"] + r["land_ext"]) / float(r["n_clear"] + r["n_ext"]) <= 0.10]),
                      (">10% missed", [r for r in ys if 1.0 - (r["land_clear"] + r["land_ext"]) / float(r["n_clear"] + r["n_ext"]) > 0.10]))
            parts = []
            for name, zs in strata:
                h, i, j = pnz(zs, "resid") if zs else (0, 0, 0)
                parts.append("%s: n %d d_stk %+d d_pin %+d resid %+d (%d/%d/%d)" % (
                    name, len(zs), sum(r["d_stock"] for r in zs), sum(r["d_pin"] for r in zs),
                    sum(r["resid"] for r in zs), h, i, j))
            miss = [1.0 - (r["land_clear"] + r["land_ext"]) / float(r["n_clear"] + r["n_ext"]) for r in ys]
            pc = pearson(miss, [r["resid"] for r in ys])
            say("    %-5s %-5s | %s | pearson(miss fraction, resid) %s" % (
                tag, wind or "all", " | ".join(parts), ("%.2f" % pc) if pc is not None else "-"))
    # fmF vs fmFS residual coupling (same fire worlds)
    for sample in ("counted", "dedup"):
        a = {r["t"]: r for r in pick("fmF", sample) if not r["zero_write"]}
        b = {r["t"]: r for r in pick("fmFS", sample) if not r["zero_write"]}
        common = sorted(set(a) & set(b))
        pr = pearson([a[t]["resid"] for t in common], [b[t]["resid"] for t in common])
        pd = pearson([a[t]["d_stock"] for t in common], [b[t]["d_stock"] for t in common])
        same = sum(1 for t in common if sign(a[t]["resid"]) == sign(b[t]["resid"]) != 0)
        opp = sum(1 for t in common if sign(a[t]["resid"]) * sign(b[t]["resid"]) < 0)
        say("  fmF vs fmFS on the same %d tuples (%s): pearson(resid) %s, pearson(d_stock) %s, resid same sign %d "
            "opposite %d" % (len(common), sample, ("%.2f" % pr) if pr is not None else "-",
                             ("%.2f" % pd) if pd is not None else "-", same, opp))
    for tag in ARMS:
        xs = [r for r in rows if r["tag"] == tag and not r["zero_write"]]
        pr = pearson([r["d_stock"] for r in xs], [r["d_pin"] for r in xs])
        pr2 = pearson([r["resid"] for r in xs], [r["d_pin"] for r in xs])
        say("  %-5s write tuples n=%d: pearson(d_stock, d_pin) %s, pearson(resid, d_pin) %s, "
            "hb symdiff stock-vs-pin total %d (pin-vs-OFF %d, stock-vs-OFF %d)" % (
                tag, len(xs), ("%.2f" % pr) if pr is not None else "-", ("%.2f" % pr2) if pr2 is not None else "-",
                sum(r["hb_symdiff_stock_vs_pin"] for r in xs), sum(r["hb_symdiff_pin_vs_off"] for r in xs),
                sum(r["hb_symdiff_stock_vs_off"] for r in xs)))
    say("")
    say("COMPONENTS pooled over write tuples: saved / extra burned / wasted clears (vs fmOFF final state)")
    for tag in ARMS:
        for sample in ("counted", "dedup"):
            xs = [r for r in pick(tag, sample) if not r["zero_write"]]
            cs = [sum(r["comp_stock"][k] for r in xs) for k in range(3)]
            cp = [sum(r["comp_pin"][k] for r in xs) for k in range(3)]
            say("  %-5s %-8s stock %5d/%5d/%4d (d %+d) | pinned %5d/%5d/%4d (d %+d) | comp_stock identity ok %d/%d, "
                "cleared-set size == fire_cleared_unburned_final %d/%d" % (
                    tag, sample, cs[0], cs[1], cs[2], cs[0] - cs[1] - cs[2], cp[0], cp[1], cp[2], cp[0] - cp[1] - cp[2],
                    sum(1 for r in xs if r["comp_stock_ok"]), len(xs), sum(1 for r in xs if r["cleared_set_ok"]), len(xs)))

    say("")
    say("SANITY 2  physical monotonicity: a pinned all-writes fire must have no burning cell that OFF lacks before the")
    say("          first burnt-set difference (fb). x1 = first step with such a cell; cause classes at x1:")
    say("          off-burnt-pin-not = OFF had burned this cell out by x1, the pinned copy still has fuel (it burned fewer ticks);")
    say("          extra-burning-neighbour-at-read = a Euclidean-3 neighbour burning in the pinned fire and not in OFF")
    say("          at the moment the cell drew (lower-uid burn-outs of the same tick applied)")
    tot_viol = 0
    for tag in ARMS:
        xs = [r for r in rows if r["tag"] == tag and not r["zero_write"]]
        vb = [r for r in xs if r["viol_steps_before_fb"]]
        tot_viol += len(vb)
        with_x1 = [r for r in xs if r["first_extra_burning"] is not None]
        at_fb = sum(1 for r in with_x1 if r["first_burnt_diff"] is not None and r["first_extra_burning"] == r["first_burnt_diff"])
        lags = sorted(r["first_extra_burning"] - r["first_burnt_diff"] for r in with_x1 if r["first_burnt_diff"] is not None)
        cls = {}
        for r in with_x1:
            for k, v in r["viol_cause"]["classes"].items():
                cls[k] = cls.get(k, 0) + v
        say("  %-5s runs %2d | violations before fb: %d runs | runs with any extra burning cell %d (x1 == fb %d; "
            "x1 - fb lags %s) | runs with no burnt diff %d | cause cells at x1: %s | unexplained runs %d" % (
                tag, len(xs), len(vb), len(with_x1), at_fb, lags, sum(1 for r in xs if r["first_burnt_diff"] is None),
                ", ".join("%s %d" % kv for kv in sorted(cls.items())),
                sum(1 for r in with_x1 if r["viol_cause"]["classes"]["unexplained"])))
        for r in vb:
            say("    EXCEPTION %s %s: %d steps before fb=%s, first x1=%s cause=%s" % (
                tag, tlabel(r["t"]), r["viol_steps_before_fb"], r["first_burnt_diff"], r["first_extra_burning"],
                json.dumps(r["viol_cause"])))
        for r in with_x1:
            if r["viol_cause"]["classes"]["unexplained"]:
                say("    UNEXPLAINED %s %s: %s" % (tag, tlabel(r["t"]), json.dumps(r["viol_cause"])))
    say("  total runs with a violation before fb: %d" % tot_viol)

    say("")
    say("SANITY 3  stock arm vs pinned replay: same draws until the stock stream shifts, so their fire digests must")
    say("          agree at every step <= fb + 2 (fb = first burnt-set difference vs OFF; the first shifted draw is at")
    say("          tick fb + 3). div = first stock-vs-pinned digest divergence")
    for tag in ARMS:
        xs = [r for r in rows if r["tag"] == tag and not r["zero_write"]]
        bad = [r for r in xs if r["stock_pin_first_digest_div"] is not None and r["first_burnt_diff"] is not None
               and r["stock_pin_first_digest_div"] <= r["first_burnt_diff"] + 2]
        bad_nofb = [r for r in xs if r["first_burnt_diff"] is None and r["stock_pin_first_digest_div"] is not None]
        lags = sorted((r["stock_pin_first_digest_div"] - r["first_burnt_diff"]) for r in xs
                      if r["stock_pin_first_digest_div"] is not None and r["first_burnt_diff"] is not None)
        same = [r for r in xs if r["stock_pin_first_digest_div"] is None]
        say("  %-5s runs %2d | stock == pinned 240/240: %d | divergence at or before fb+2: %d (and with no fb: %d) | "
            "div - fb lags %s" % (tag, len(xs), len(same), len(bad), len(bad_nofb), lags))
        ff = [r for r in xs if r["first_fail_step"] is not None]
        say("  %-5s        | runs with a missed write %d; first miss at or after the stock-vs-pinned divergence %d, "
            "strictly before it or with no divergence (impossible) %d" % (
                tag, len(ff), sum(1 for r in ff if r["stock_pin_first_digest_div"] is not None
                                  and r["first_fail_step"] >= r["stock_pin_first_digest_div"]),
                sum(1 for r in ff if r["stock_pin_first_digest_div"] is None
                    or r["first_fail_step"] < r["stock_pin_first_digest_div"])))
        for r in bad + bad_nofb:
            say("    EXCEPTION %s %s: div %s fb %s" % (tag, tlabel(r["t"]), r["stock_pin_first_digest_div"],
                                                    r["first_burnt_diff"]))
    return rows


# ============================================================ landed-subset stock replays ===
# A recorded write that misses the pinned fire makes the open-loop residual mix two things: the draw-stream
# coupling and the schedule's fit to the re-rolled stock fire. For every firebreak run with a miss, the STOCK
# fire is replayed with only the writes that landed under pinning (the pinned fire is unchanged by that
# selection: a miss writes nothing). d_sub - d_pin is then a stock-vs-pinned comparison of the same intended
# write set. The subset is passed to the instrument's own run_replay by replacing its module-level
# _select_writes in this process only (the instrument file is not modified); a validation job selects all
# indices through the same path and must reproduce the recorded arm 240/240.
SUBSET_ARMS = ("fmF", "fmFS")
SUBSET_VALIDATE = ("fmF", ("south", "half", 505))


def out_sub(outdir, tag, t, which):
    return os.path.join(outdir, "sub_%s_%s_%s_%d_%s.json" % ((tag,) + t + (which,)))


def replay_subset(args):
    tag = args.tag
    w, rr, s = args.tuple.split("/")
    t = (w, rr, int(s))
    rows = write_rows(tag, t)
    if args.which == "all":
        idx = list(range(len(rows)))
    else:
        rp = load(out_pin(args.outdir, tag, t, "all"))
        idx = [x["i"] for x in rp["writes_selected"] if x["applied"]]
    FR._select_writes = lambda _rows, _spec: list(idx)
    ns = argparse.Namespace(repo=REPO, arm_json=arm_path(tag, t), writes="subset-" + args.which, crn=False,
                            record_draws="", pin_draws="", steps=0, out=args.out)
    return FR.run_replay(ns)


def subset_jobs(outdir):
    jobs = [{"tag": SUBSET_VALIDATE[0], "t": SUBSET_VALIDATE[1], "which": "all",
             "out": out_sub(outdir, SUBSET_VALIDATE[0], SUBSET_VALIDATE[1], "all")}]
    for tag in SUBSET_ARMS:
        for t in write_tuples(tag):
            p = out_pin(outdir, tag, t, "all")
            if os.path.exists(p) and load(p)["writes_failed"]:
                jobs.append({"tag": tag, "t": t, "which": "landed", "out": out_sub(outdir, tag, t, "landed")})
    return jobs


def run_subset(args):
    outdir = args.outdir
    log = open(os.path.join(os.path.dirname(outdir), "run.log"), "a", encoding="utf-8", newline=NL)

    def say(msg):
        line = time.strftime("%H:%M:%S ") + msg
        print(line, flush=True)
        log.write(line + NL)
        log.flush()

    alljobs = subset_jobs(outdir)
    jobs = [j for j in alljobs if not os.path.exists(j["out"])]
    say("task P subset run: %d jobs pending of %d, one replay process at a time" % (len(jobs), len(alljobs)))
    t0 = time.time()
    for j in jobs:
        while True:
            fk = FR.free_kb()
            if fk >= MIN_FREE_KB:
                break
            say("free commit %d kB < %d, waiting" % (fk, MIN_FREE_KB))
            time.sleep(20)
        cmd = [PY, os.path.abspath(__file__), "--replay-subset", "--tag", j["tag"], "--tuple", tlabel(j["t"]),
               "--which", j["which"], "--outdir", outdir, "--out", j["out"]]
        ts = time.time()
        with open(j["out"][:-5] + ".log", "w", encoding="utf-8", newline=NL) as errf:
            say("start (free %d kB) subset %s %s %s" % (fk, j["tag"], tlabel(j["t"]), j["which"]))
            rc = subprocess.run(cmd, stdout=errf, stderr=subprocess.STDOUT, cwd=REPO).returncode
        say("done rc=%d out=%s %.0fs %s" % (rc, os.path.exists(j["out"]), time.time() - ts, os.path.basename(j["out"])))
    say("task P subset run finished in %.0fs" % (time.time() - t0))
    log.close()
    return 0


def analyse_subset(args, out, rows):
    import _firemech_analyze as FA  # noqa: E402
    outdir = args.outdir

    def say(s=""):
        out.append(s)
        print(s)

    say("")
    say("LANDED-SUBSET STOCK REPLAYS (firebreak arms, runs with >= 1 write missing the pinned fire)")
    say("  d_sub = intact of the STOCK fire replayed with only the writes that landed under pinning - intact(fmOFF);")
    say("  coupling = d_sub - d_pin (same intended writes, stock stream vs pinned draws); schedule = d_stock - d_sub")
    say("  (the recorded writes that only land on the re-rolled stock fire, measured in the stock world, re-roll")
    say("  included); sub_land = subset writes that landed in the stock subset replay; sdiv = first digest step where")
    say("  the subset replay differs from the pinned replay")
    vp = out_sub(outdir, SUBSET_VALIDATE[0], SUBSET_VALIDATE[1], "all")
    if os.path.exists(vp):
        v = load(vp)
        SA = FA.run_summary(load(arm_path(SUBSET_VALIDATE[0], SUBSET_VALIDATE[1])), None)
        say("  VALIDATION of the subset path (all indices through the patched selector): %s %s digest vs arm %d/%d, "
            "selected %d failed %d, intact replay %d arm %d" % (
                SUBSET_VALIDATE[0], tlabel(SUBSET_VALIDATE[1]), v["digest_vs_arm"]["matched"],
                v["digest_vs_arm"]["compared"], len(v["writes_selected"]), len(v["writes_failed"]),
                v["final"]["intact"], SA["intact"]))
    else:
        say("  VALIDATION output MISSING")
    by = {(r["tag"], r["t"]): r for r in rows}
    sub_rows = []
    say("  %-5s %-16s %6s %6s %6s %6s | %8s %6s | %9s %4s %4s" % (
        "arm", "tuple", "d_stk", "d_pin", "d_sub", "resid", "coupling", "sched", "sub_land", "fb", "sdiv"))
    for tag in SUBSET_ARMS:
        for t in CANON + FRESH:
            R = by.get((tag, t))
            if R is None or R["zero_write"]:
                continue
            p = out_sub(outdir, tag, t, "landed")
            if not os.path.exists(p):
                R["coupling"] = R["resid"] if R["land_clear"] + R["land_ext"] == R["n_clear"] + R["n_ext"] else None
                R["d_sub"] = R["d_stock"] if R["coupling"] is not None else None
                continue
            s = load(p)
            rp = load(out_pin(outdir, tag, t, "all"))
            d_sub = s["final"]["intact"] - R["intact_off"]
            R["d_sub"] = d_sub
            R["coupling"] = d_sub - R["d_pin"]
            R["sched"] = R["d_stock"] - d_sub
            n_sel = len(s["writes_selected"])
            landed = sum(1 for x in s["writes_selected"] if x["applied"])
            sdiv = next((k + 1 for k in range(240) if s["digests"][k] != rp["digests"][k]), None)
            R["sub_land"] = (landed, n_sel)
            R["sub_sdiv"] = sdiv
            sub_rows.append(R)
            say("  %-5s %-16s %+6d %+6d %+6d %+6d | %+8d %+6d | %4d/%-4d %4s %4s" % (
                tag, tlabel(t), R["d_stock"], R["d_pin"], d_sub, R["resid"], R["coupling"], R["sched"], landed, n_sel,
                R["first_burnt_diff"], sdiv if sdiv is not None else "-"))
    say("  subset replay vs pinned digest divergence at or before fb+2 (impossible): %d of %d" % (
        sum(1 for R in sub_rows if R["sub_sdiv"] is not None and R["sub_sdiv"] <= R["first_burnt_diff"] + 2), len(sub_rows)))
    say("")
    say("  coupling term over ALL write tuples (runs with no miss: coupling = resid; runs with a miss: d_sub - d_pin),")
    say("  plus the schedule term, by wind; zero-write tuples excluded (their terms are 0)")
    for tag in SUBSET_ARMS:
        for sample in ("counted", "dedup", "canon", "fresh"):
            for wind in (None, "east", "south"):
                xs = [r for r in rows if r["tag"] == tag and not r["zero_write"] and r.get("coupling") is not None]
                if sample == "dedup":
                    xs = [r for r in xs if r["rr"] != "def"]
                elif sample in ("canon", "fresh"):
                    xs = [r for r in xs if r["sample"] == sample]
                if wind:
                    xs = [r for r in xs if r["wind"] == wind]
                if not xs:
                    continue
                cs = [r["coupling"] for r in xs]
                h, i, j = sum(1 for c in cs if c > 0), sum(1 for c in cs if c < 0), sum(1 for c in cs if c == 0)
                sched = sum(r["d_stock"] - r["d_sub"] for r in xs)
                p = sign_test_p(h, i)
                say("  %-5s %-14s n %2d | d_stock %+6d = d_pin %+6d + coupling %+5d (%d/%d/%d, p %s, median %+.1f, "
                    "range %+d..%+d) + schedule %+5d" % (
                        tag, sample + "/" + (wind or "all"), len(xs), sum(r["d_stock"] for r in xs),
                        sum(r["d_pin"] for r in xs), sum(cs), h, i, j, ("%.4f" % p) if p is not None else "-",
                        median(cs), min(cs), max(cs), sched))


# ================================================================ pure draw-stream offset ===
# No writes at all. The fmOFF fire is replayed drawing from fmOFF's own recorded draw stream S (the non-NaN
# values of its .draws file in tick, then uid order - exactly the rng stream Fire.step consumed), through a
# pointer that advances one position per draw like the stock rng; at the first draw of tick OFFSET_AT the
# pointer jumps by m. m = 0 must reproduce fmOFF 240/240. m = +1 makes every later draw read the value one
# drawer later in the stream (what an extra drawer does), m = -1 one earlier (what one fewer drawer does). The
# fire changes only through that offset, so any systematic intact change is the coupling itself. Positions past
# the recorded stream (the offset run can draw more often than fmOFF) fall back to crn_uniform.
OFFSET_AT = 99
OFFSETS = (1, -1)


def offset_fires():
    return [t for t in CANON + FRESH if t[1] != "def" and any(write_rows(tag, t) for tag in ARMS)]


def out_off(outdir, t, m):
    return os.path.join(outdir, "off_%s_%s_%d_m%+d_at%d.json" % (t + (m, OFFSET_AT)))


def replay_offset(args):
    w, rr, s = args.tuple.split("/")
    t = (w, rr, int(s))
    m = int(args.offset)
    vals = array("d")
    with open(draws_local(args.outdir, t), "rb") as f:
        vals.frombytes(f.read())
    S = array("d", (v for v in vals if v == v))
    sys.path.insert(0, HERE)
    from _fm2_probe_harness import crn_uniform  # noqa: E402
    st = {"p": 0, "applied": False, "fallback": 0, "max_p": 0, "draws": 0, "seed": int(s)}

    def draw(fire):
        if not st["applied"] and fire.steps_counter == OFFSET_AT:
            st["p"] += m
            st["applied"] = True
        p = st["p"]
        st["p"] = p + 1
        st["draws"] += 1
        if 0 <= p < len(S):
            return S[p]
        st["fallback"] += 1
        return crn_uniform(st["seed"], fire.unique_id, fire.steps_counter)

    orig = FR._install_draw
    FR._install_draw = lambda am, _ignored: orig(am, draw)
    tmp_draws = args.out + ".unused.draws"
    ns = argparse.Namespace(repo=REPO, arm_json=arm_path("fmOFF", t), writes="none", crn=False,
                            record_draws=tmp_draws, pin_draws="", steps=0, out=args.out)
    rc = FR.run_replay(ns)
    if os.path.exists(tmp_draws):
        os.remove(tmp_draws)
    d = load(args.out)
    d["offset_experiment"] = {"m": m, "at_tick": OFFSET_AT, "stream_len": len(S), "draws": st["draws"],
                              "end_pointer": st["p"], "fallback": st["fallback"], "applied": st["applied"]}
    with open(args.out + ".tmp", "w", encoding="utf-8", newline=NL) as f:
        json.dump(d, f)
    os.replace(args.out + ".tmp", args.out)
    print("offset m=%+d at %d: draws %d stream %d end pointer %d fallback %d" % (
        m, OFFSET_AT, st["draws"], len(S), st["p"], st["fallback"]))
    return rc


def offset_jobs(outdir):
    fires = offset_fires()
    jobs = [{"t": fires[0], "m": 0}, {"t": ("south", "half", 404), "m": 0}]
    for m in OFFSETS:
        for t in fires:
            jobs.append({"t": t, "m": m})
    for j in jobs:
        j["out"] = out_off(outdir, j["t"], j["m"])
    return jobs


def run_offset(args):
    outdir = args.outdir
    log = open(os.path.join(os.path.dirname(outdir), "run.log"), "a", encoding="utf-8", newline=NL)

    def say(msg):
        line = time.strftime("%H:%M:%S ") + msg
        print(line, flush=True)
        log.write(line + NL)
        log.flush()

    alljobs = offset_jobs(outdir)
    jobs = [j for j in alljobs if not os.path.exists(j["out"])]
    say("task P offset run: %d jobs pending of %d, one replay process at a time" % (len(jobs), len(alljobs)))
    t0 = time.time()
    for j in jobs:
        while True:
            fk = FR.free_kb()
            if fk >= MIN_FREE_KB:
                break
            say("free commit %d kB < %d, waiting" % (fk, MIN_FREE_KB))
            time.sleep(20)
        cmd = [PY, os.path.abspath(__file__), "--replay-offset", "--tuple", tlabel(j["t"]), "--offset", str(j["m"]),
               "--outdir", outdir, "--out", j["out"]]
        ts = time.time()
        with open(j["out"][:-5] + ".log", "w", encoding="utf-8", newline=NL) as errf:
            say("start (free %d kB) offset %s m=%+d" % (fk, tlabel(j["t"]), j["m"]))
            rc = subprocess.run(cmd, stdout=errf, stderr=subprocess.STDOUT, cwd=REPO).returncode
        say("done rc=%d out=%s %.0fs %s" % (rc, os.path.exists(j["out"]), time.time() - ts, os.path.basename(j["out"])))
    say("task P offset run finished in %.0fs" % (time.time() - t0))
    log.close()
    return 0


def analyse_offset(args, out):
    import _firemech_analyze as FA  # noqa: E402
    outdir = args.outdir

    def say(s=""):
        out.append(s)
        print(s)

    say("")
    say("PURE DRAW-STREAM OFFSET (no writes): fmOFF replayed from its own recorded stream, pointer jumps by m at the")
    say("  first draw of tick %d; d = intact - intact(fmOFF); 17 distinct fire worlds (east/def excluded)" % OFFSET_AT)
    for t in (offset_fires()[0], ("south", "half", 404)):
        p = out_off(outdir, t, 0)
        if not os.path.exists(p):
            say("  VALIDATION m=0 %s MISSING" % tlabel(t))
            continue
        r = load(p)
        SO = FA.run_summary(load(arm_path("fmOFF", t)), None)
        oe = r["offset_experiment"]
        say("  VALIDATION m=0 %-16s digest vs fmOFF %d/%d, intact %d vs %d, draws %d == stream %d, fallback %d" % (
            tlabel(t), r["digest_vs_arm"]["matched"], r["digest_vs_arm"]["compared"], r["final"]["intact"],
            SO["intact"], oe["draws"], oe["stream_len"], oe["fallback"]))
    res = {}
    say("  %-16s %6s | %s" % ("fire", "OFF", " | ".join("m=%+d: d_intact  first_div  |symdiff|  fallback  end_ptr-len" % m
                                                      for m in OFFSETS)))
    for t in offset_fires():
        SO = FA.run_summary(load(arm_path("fmOFF", t)), None)
        parts = []
        ok = True
        for m in OFFSETS:
            p = out_off(outdir, t, m)
            if not os.path.exists(p):
                parts.append("MISSING")
                ok = False
                continue
            r = load(p)
            oe = r["offset_experiment"]
            dI = r["final"]["intact"] - SO["intact"]
            res[(t, m)] = dI
            hb_off = set(tuple(int(v) for v in k.split(",")) for k, v in load(arm_path("fmOFF", t))["fire_ground_final"].items() if v[0])
            cells = [(c[1], c[2]) for c in r["fires"]]
            hb = set(cells[i] for i in r["final_has_burned"])
            parts.append("%+6d  %9s  %8d  %8d  %+6d" % (dI, r["digest_vs_arm"]["first_mismatch"], len(hb ^ hb_off),
                                                        oe["fallback"], oe["end_pointer"] - oe["stream_len"]))
        say("  %-16s %6d | %s" % (tlabel(t), SO["intact"], " | ".join(parts)))
    for wind in (None, "east", "south"):
        for sample in ("both", "canon", "fresh"):
            fires = [t for t in offset_fires() if (wind is None or t[0] == wind)
                     and (sample == "both" or (sample == "canon") == (t in CANON))]
            parts = []
            for m in OFFSETS:
                ds = [res[(t, m)] for t in fires if (t, m) in res]
                if not ds:
                    continue
                h, i, j = sum(1 for x in ds if x > 0), sum(1 for x in ds if x < 0), sum(1 for x in ds if x == 0)
                p = sign_test_p(h, i)
                parts.append("m=%+d n %d sum %+d (%d/%d/%d, p %s, median %+.1f)" % (
                    m, len(ds), sum(ds), h, i, j, ("%.4f" % p) if p is not None else "-", median(ds)))
            pair = [res[(t, 1)] - res[(t, -1)] for t in fires if (t, 1) in res and (t, -1) in res]
            if pair:
                h, i = sum(1 for x in pair if x > 0), sum(1 for x in pair if x < 0)
                parts.append("paired d(+1)-d(-1) sum %+d (%d/%d/%d, p %s)" % (
                    sum(pair), h, i, len(pair) - h - i, ("%.4f" % sign_test_p(h, i)) if sign_test_p(h, i) is not None else "-"))
            say("  %-5s %-5s | %s" % (wind or "all", sample, " | ".join(parts)))


def report(args):
    out = []
    rows = analyse(args, out)
    analyse_subset(args, out, rows)
    analyse_offset(args, out)
    with open(args.out, "w", encoding="utf-8", newline=NL) as f:
        f.write(NL.join(out) + NL)
    if args.json:
        for r in rows:
            r["t"] = list(r["t"])
        with open(args.json, "w", encoding="utf-8", newline=NL) as f:
            json.dump(rows, f, indent=1)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--outdir", default=OUTDIR_DEFAULT)
    ap.add_argument("--draws-src", default=DRAWS_SRC_DEFAULT)
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--run-subset", action="store_true")
    ap.add_argument("--replay-subset", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--tuple", default="")
    ap.add_argument("--which", choices=["all", "landed"], default="landed")
    ap.add_argument("--run-offset", action="store_true")
    ap.add_argument("--replay-offset", action="store_true")
    ap.add_argument("--offset", type=int, default=0)
    args = ap.parse_args()
    if args.replay_offset:
        return replay_offset(args)
    if args.run_offset:
        return run_offset(args)
    if args.replay_subset:
        return replay_subset(args)
    if args.run_subset:
        return run_subset(args)
    if args.run:
        return run(args)
    if args.report:
        if not args.out:
            ap.error("--report needs --out")
        return report(args)
    ap.error("--run or --report")


if __name__ == "__main__":
    raise SystemExit(main())
