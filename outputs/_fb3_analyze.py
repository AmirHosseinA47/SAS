"""fix3b Part 3 screen analyzer (read-only) - every pre-registered check of outputs/fix3b_part1.txt section 9.

usage (repo root): .venv/Scripts/python.exe outputs/_fb3_analyze.py [section ...]
sections: prov ident gates ffosc outcomes exposure targeting invariants spawn rbgate (default: all)

Measures are the session-3a ones, imported unchanged from outputs/_fx3r_analyze.py: (N) = no terminal step by
360; (O) broad = per searcher, steps covered by a 10-step window (airborne) on <= 2 cells with >= 4 changes;
(O) pocket kind = _fx3_pockets episodes (near a depot, and r=500 "anywhere") with changes on >= 1/3 of steps.
Firefighter (O) = the broad measure on firefighter positions (on-grid steps). Coverage = the share of cells
ever inside any UAV's Euclidean-8 detection disc, from rows_uav positions - the same computation for every arm.
"""
from __future__ import annotations

import collections
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)
_ARGS = sys.argv[1:]
sys.argv = sys.argv[:1]
import _fx3r_analyze as R  # noqa: E402
import _fx3_pockets as P  # noqa: E402

SET1 = ("fx3mS", ("fb3lo", "fb3bd", "fb3bf", "fb3rw"))
SET2 = ("fx3mS2", ("fb3lo2", "fb3bd2", "fb3bf2"))
SPAWN = ("fb3vs0", ("fb3vs3",))
GATED = {"fb3lo", "fb3bd", "fb3bf", "fb3lo2", "fb3bd2", "fb3bf2", "fb3vs3"}
NAMES = {"fx3mS": "CUR set1", "fx3mS2": "CUR set2", "fb3lo": "LO", "fb3bd": "BD", "fb3bf": "BF", "fb3rw": "RW",
         "fb3lo2": "LO", "fb3bd2": "BD", "fb3bf2": "BF", "fb3vs0": "CUR spawn1", "fb3vs3": "BF spawn1"}
H = 360
_COV = {}
IDENT_TAGS = ("fb3id", "fb3idb")
RB_TAG = "fb3g"
if "--rescreen" in _ARGS:            # rulings R-1..R-3: the re-screened Bayes arms, the same references and gates
    _ARGS.remove("--rescreen")
    SET1 = ("fx3mS", ("fb3bd", "fb3bdr", "fb3bf", "fb3bfr"))
    SET2 = ("fx3mS2", ("fb3bd2", "fb3bdr2", "fb3bf2", "fb3bfr2"))
    SPAWN = ("fb3vs0", ("fb3vs3", "fb3vs3r"))
    GATED = {"fb3bdr", "fb3bfr", "fb3bdr2", "fb3bfr2", "fb3vs3r"}
    NAMES.update({"fb3bdr": "BD-R", "fb3bfr": "BF-R", "fb3bdr2": "BD-R", "fb3bfr2": "BF-R", "fb3vs3r": "BF-R spawn1"})
    IDENT_TAGS = ("fb3idc",)
    RB_TAG = "fb3h"


def out(*a):
    print(*a)


def load(tag):
    return R.load(tag)


# ------------------------------------------------------------------------------------------------ helpers
def broad_episodes(seq):
    """seq: [(t, cell)] for consecutive steps of one unit (cells None = off grid, breaks the window)."""
    n = len(seq)
    mark = [False] * n
    for i in range(0, n - 9):
        w = seq[i:i + 10]
        if any(c is None for _, c in w) or w[-1][0] - w[0][0] != 9:
            continue
        cells = {c for _, c in w}
        ch = sum(1 for k in range(1, 10) if w[k][1] != w[k - 1][1])
        if len(cells) <= 2 and ch >= 4:
            for k in range(i, i + 10):
                mark[k] = True
    eps, i = [], 0
    while i < n:
        if mark[i]:
            j = i
            while j + 1 < n and mark[j + 1]:
                j += 1
            eps.append((seq[i][0], seq[j][0], j - i + 1))
            i = j + 1
        else:
            i += 1
    return eps


def mech(label):
    label = str(label or "")
    if label == "victim_search_targeting":
        return "TARGETING"
    if label == "victim_search_random_walk":
        return "RW"
    if label in R.FIRE_LABELS:
        return "FIRE"
    if label.startswith("hold") or "yield" in label:
        return "YIELD"
    if "hazard_retreat" in label:
        return "GATE"
    if label.endswith("_fire_route") or "retarget_to_interior" in label or label == "victim_search_escape_bfs":
        return "ROUTE"
    return "PLAN"


def searcher_o(d):
    """(broad episodes with mechanism, pocket-near-depot count, pocket-anywhere count) - R.sec_gates' rules."""
    rows = d["rows_uav"]
    lab = {}
    for t, row in enumerate(rows):
        for u in row:
            lab[(t + 1, u[0])] = str(u[8] or "")
    broad = []
    for e in R.searcher_osc_episodes(d, True):
        uid, s0, s1 = e[0], e[1], e[2]
        c = collections.Counter(mech(lab.get((s, uid))) for s in range(s0, s1 + 1))
        broad.append((uid, s0, s1, e[3], max(c, key=c.get), dict(c)))
    pock = anywhere = 0
    for r, store in ((5, "near"), (500, "any")):
        eps = P.pockets(d, r=r, pre_terminal=False)[0]
        for e in eps:
            if e["role"] != "victim_searcher":
                continue
            cells = [[u for u in rows[s - 1] if u[0] == e["uid"]][0][1:3] for s in range(e["start"], e["end"] + 1)]
            if sum(1 for i in range(1, len(cells)) if cells[i] != cells[i - 1]) * 3 >= len(cells):
                if store == "near":
                    pock += 1
                else:
                    anywhere += 1
    return broad, pock, anywhere


def ff_episodes(d):
    per = collections.defaultdict(list)
    for t, row in enumerate(d["rows_ff"]):
        for f in row:
            cell = (f[1], f[2]) if f[1] is not None and f[2] is not None else None
            per[f[0]].append((t + 1, cell))
    eps = []
    for fid, seq in per.items():
        for s0, s1, n in broad_episodes(seq):
            eps.append((fid, s0, s1, n))
    return eps


def coverage_curve(d, steps=(60, 120, 180, 240, 300, 360)):
    import numpy as np
    from src_extension.knowledge.victim_search_belief import disc_mask, disc_offsets

    off = _COV.setdefault("off", disc_offsets(8.0))
    cov = np.zeros((50, 50), dtype=bool)
    res = {}
    for t, row in enumerate(d["rows_uav"]):
        cov |= disc_mask(50, 50, [(int(u[1]), int(u[2])) for u in row if u[1] is not None], off)
        if t + 1 in steps:
            res[t + 1] = float(cov.mean())
    return res


def det_times(d):
    """{victim: first detection step or None} over every victim of the run (stdout '[Victim Detection]')."""
    vids = [v[0] for v in d["rows_vic"][0]]
    det = d.get("_det") or {}
    return {v: det.get(v) for v in vids}


def run_mean_det(d, eligible=None):
    times = det_times(d)
    vals = [min(t, H) if t is not None else H for v, t in times.items() if eligible is None or v in eligible]
    return statistics.mean(vals) if vals else None


def eligible_victims(d_ref, d_arm):
    """Victims not found at launch (first detection step > 1) in EITHER arm - launch detections are
    strategy-independent (fix3b_part1.txt 10.5)."""
    a, b = det_times(d_ref), det_times(d_arm)
    return {v for v in a if not ((a[v] is not None and a[v] <= 1) or (b.get(v) is not None and b[v] <= 1))}


# ------------------------------------------------------------------------------------------------ sections
def sec_prov():
    out("=" * 110)
    out("PROVENANCE - heads, source hashes vs this tree, fix3b switches, probe, CRN")
    for tag in IDENT_TAGS + SET1[1] + SET2[1] + (SPAWN[0],) + SPAWN[1]:
        runs = load(tag)
        if not runs:
            out("  %-7s (no runs)" % tag)
            continue
        heads = collections.Counter(str(d.get("head"))[:8] for d in runs.values())
        bad = sum(1 for d in runs.values() for rel, sha in (d.get("src_sha") or {}).items()
                  if os.path.exists(os.path.join(REPO, rel)) and R.raw_sha(os.path.join(REPO, rel)) != sha)
        eff = collections.Counter(json.dumps((d.get("fb3") or {}).get("eff")) for d in runs.values())
        crn = collections.Counter(str(((d.get("fb3") or {}).get("crn") or {}).get("on")) for d in runs.values())
        out("  %-7s runs %2d heads %s | src differing from tree %d | eff %s | crn %s" % (
            tag, len(runs), dict(heads), bad, dict(eff), dict(crn)))


def sec_ident():
    out("=" * 110)
    out("ID - fb3id (every switch at default, the new probe, CRN off) vs fx3mS (11785ae6 source): value identity on"
        " the fx3m FIELDS + every mf2 section")
    for tag in IDENT_TAGS:
        if not load(tag):
            out("  %s (no runs)" % tag)
            continue
        same, n, lines = R.probe_ident(tag, "fx3mS")
        heads = sorted({str(d.get("head"))[:8] for d in load(tag).values()})
        out("  %-6s (head %s) vs fx3mS  %d / %d identical  => %s" % (
            tag, ",".join(heads), same, n, "PASS" if same == n == 16 else "FAIL - STOP"))
        for ln in lines:
            out(ln)


def _gate_pair(ref, arms):
    rr = load(ref)
    ref_never = sorted(k for k, d in rr.items() if not d.get("terminal_step"))
    ro = [searcher_o(d) for d in rr.values()]
    ref_b = sum(len(x[0]) for x in ro)
    ref_p = sum(x[1] for x in ro)
    ref_a = sum(x[2] for x in ro)
    out("  %-10s %-7s runs %2d | (N) %d %s | (O) broad %d (longest %d), pocket near depot %d, pocket anywhere %d" % (
        NAMES.get(ref, ref), ref, len(rr), len(ref_never), ref_never or "", ref_b,
        max([e[3] for x in ro for e in x[0]] or [0]), ref_p, ref_a))
    for tag in arms:
        runs = load(tag)
        if not runs:
            out("  %-10s %-7s (no runs)" % (NAMES.get(tag, tag), tag))
            continue
        never = sorted(k for k, d in runs.items() if not d.get("terminal_step"))
        res = {k: searcher_o(d) for k, d in runs.items()}
        b = [(k,) + e for k, x in res.items() for e in x[0]]
        p = sum(x[1] for x in res.values())
        a = sum(x[2] for x in res.values())
        mechs = collections.Counter(e[5] for e in b)
        gated = tag in GATED
        n_ok = len(never) <= len(ref_never)
        o_ok = len(b) <= ref_b and p <= ref_p and a <= ref_a
        out("  %-10s %-7s runs %2d | (N) %d %s %s | (O) broad %d (longest %d), pocket near depot %d, pocket anywhere %d"
            " %s | target 0: N %s O %s" % (
                NAMES.get(tag, tag), tag, len(runs), len(never), never or "",
                ("PASS" if n_ok else "FAIL") if gated else "(reported)", len(b), max([e[4] for e in b] or [0]), p, a,
                ("PASS" if o_ok else "FAIL") if gated else "(reported)",
                "met" if not never else "not met", "met" if not (b or p or a) else "not met"))
        out("               (O) broad episodes by mechanism: %s" % (dict(mechs) or "none"))
        for e in b[:10]:
            out("               episode %s" % (e,))


def sec_gates():
    out("=" * 110)
    out("GATES G-N / G-O (fix3b_part1.txt 9): per seed set, each targeting arm vs CUR on the same seeds; must not rise"
        " (target 0). RW and the CUR spawn arm are reported only.")
    for ref, arms in (SET1, SET2, SPAWN):
        _gate_pair(ref, arms)


def sec_ffosc():
    out("=" * 110)
    out("FIREFIGHTER (O) - REPORTED, not gated: the broad two-cell measure on firefighter positions")
    for ref, arms in (SET1, SET2, SPAWN):
        for tag in (ref,) + arms:
            runs = load(tag)
            if not runs:
                continue
            eps = [(k,) + e for k, d in runs.items() for e in ff_episodes(d)]
            out("  %-10s %-7s firefighter episodes %d, longest %d %s" % (
                NAMES.get(tag, tag), tag, len(eps), max([e[4] for e in eps] or [0]), eps[:4]))


def sec_outcomes():
    out("=" * 110)
    out("OUTCOMES - rescued / dead / ff deaths / never detected (stdout events, incl. died undetected); per-run mean"
        " first-detection step over eligible victims (censored at 360), paired vs CUR on the same seeds; coverage")
    for ref, arms in (SET1, SET2, SPAWN):
        rr = load(ref)
        for tag in (ref,) + arms:
            runs = load(tag)
            if not runs:
                continue
            ev = collections.Counter()
            for d in runs.values():
                e = d.get("eval") or {}
                ev["rescued"] += int(e.get("rescued") or 0)
                ev["dead"] += int(e.get("dead") or 0)
                ev["ffd"] += int(e.get("firefighter_deaths") or 0)
                ev["victims"] += len(d["rows_vic"][0])
                ev["nd"] += sum(1 for t in det_times(d).values() if t is None)
            cov = collections.defaultdict(list)
            for d in runs.values():
                for s, v in coverage_curve(d).items():
                    cov[s].append(v)
            covs = " ".join("%d:%.3f" % (s, statistics.mean(v)) for s, v in sorted(cov.items()))
            line = "  %-10s %-7s victims %3d rescued %3d dead %2d ffdead %d never_detected %2d | coverage %s" % (
                NAMES.get(tag, tag), tag, ev["victims"], ev["rescued"], ev["dead"], ev["ffd"], ev["nd"], covs)
            out(line)
            if tag != ref:
                diffs = []
                for k in sorted(set(rr) & set(runs)):
                    el = eligible_victims(rr[k], runs[k])
                    a, b = run_mean_det(rr[k], el), run_mean_det(runs[k], el)
                    if a is not None and b is not None:
                        diffs.append((k, round(b - a, 1)))
                vals = [x[1] for x in diffs]
                if vals:
                    out("               paired per-run mean detection step (arm - CUR): mean %+.1f median %+.1f SD %.1f |"
                        " better %d worse %d equal %d | %s" % (
                            statistics.mean(vals), statistics.median(vals),
                            statistics.pstdev(vals) if len(vals) > 1 else 0.0,
                            sum(1 for v in vals if v < 0), sum(1 for v in vals if v > 0),
                            sum(1 for v in vals if v == 0), diffs))


def sec_exposure():
    out("=" * 110)
    out("EXPOSURE - UAV-steps on a burning cell / on smoke (mf2 uav rows), searcher and all-UAV")
    for ref, arms in (SET1, SET2, SPAWN):
        for tag in (ref,) + arms:
            S = collections.Counter()
            for d in load(tag).values():
                for row in (d.get("mf2") or {}).get("uav") or []:
                    for u in row:
                        if len(u) < 6 or not isinstance(u[4], int):
                            continue
                        S["n"] += 1
                        S["f"] += u[4]
                        S["sm"] += u[5]
                        if u[1] == "victim_searcher":
                            S["ns"] += 1
                            S["fs"] += u[4]
                            S["sms"] += u[5]
            if not S["n"]:
                continue
            p = lambda a, b: 100.0 * S[a] / S[b] if S[b] else 0.0
            out("  %-10s %-7s in fire: searcher %.2f%% all-UAV %.2f%% | smoke: searcher %.2f%% all-UAV %.2f%%" % (
                NAMES.get(tag, tag), tag, p("fs", "ns"), p("f", "n"), p("sms", "ns"), p("sm", "n")))


def sec_targeting():
    out("=" * 110)
    out("TARGETING COUNTERS - selections, give-ups / drops by reason, fallbacks, planner/executor mismatches, share"
        " of searcher steps steered by the strategy, reachability at issue, per-step compute (ms)")
    for tag in SET1[1] + SET2[1] + SPAWN[1]:
        runs = load(tag)
        if not runs:
            continue
        tot = collections.Counter()
        issued = reach = 0
        bms, pms = [], []
        steer = steps = 0
        for d in runs.values():
            fb = d.get("fb3") or {}
            for per in (fb.get("stats") or {}).values():
                tot.update(per)
            for row in fb.get("issued") or []:
                issued += 1
                reach += 1 if row[6] else 0
            t = fb.get("timing") or {}
            bms += (t.get("belief_ms") or {}).get("raw") or []
            pms += (t.get("plan_ms") or {}).get("raw") or []
            times = det_times(d)
            t_all = max(times.values()) if times and all(t is not None for t in times.values()) else None
            for t, row in enumerate(d["rows_uav"]):
                for u in row:
                    if u[3] == "victim_searcher" and not (u[5] or u[6]):
                        own = str(u[8]) in ("victim_search_targeting", "victim_search_random_walk")
                        steps += 1
                        steer += 1 if own else 0
                        if t_all is None or t + 1 < t_all:          # an undetected victim remains
                            tot["_pre_steps"] += 1
                            tot["_pre_steer"] += 1 if own else 0
        q = lambda xs, f: sorted(xs)[min(len(xs) - 1, int(f * len(xs)))] if xs else 0
        pre_s, pre_n = tot.pop("_pre_steer", 0), tot.pop("_pre_steps", 0)
        out("  %-7s %s" % (tag, dict(sorted(tot.items()))))
        out("          WHILE AN UNDETECTED VICTIM REMAINS: strategy-steered airborne searcher steps %d / %d (%.1f%%)" % (
            pre_s, pre_n, 100.0 * pre_s / pre_n if pre_n else 0.0))
        out("          issued %d, reachable at issue %d (%.1f%%) | strategy-steered airborne searcher steps %d / %d (%.1f%%)"
            " | belief ms median %.2f p95 %.2f | planner ms median %.2f p95 %.2f" % (
                issued, reach, 100.0 * reach / issued if issued else 0.0, steer, steps,
                100.0 * steer / steps if steps else 0.0, q(bms, .5), q(bms, .95), q(pms, .5), q(pms, .95)))


def sec_invariants():
    out("=" * 110)
    out("INVARIANTS - inline violations, crashes, warnings (must be 0 new)")
    for ref, arms in (SET1, SET2, SPAWN):
        for tag in (ref,) + arms:
            runs = load(tag)
            if not runs:
                continue
            viol = collections.Counter()
            for d in runs.values():
                for k, v in (d.get("inline_violation_counts") or {}).items():
                    viol[k] += int(v or 0)
            alarms = collections.Counter()
            for d in runs.values():
                for row in (d.get("mf2") or {}).get("fleet") or []:
                    if isinstance(row, list) and len(row) > 3 and isinstance(row[3], dict):
                        for k, v in row[3].items():
                            alarms[str(k).split("|")[0]] += int(v or 0)
            out("  %-10s %-7s crashed %d | inline violations %s | warnings %d | fail-safe alarms %s" % (
                NAMES.get(tag, tag), tag, sum(1 for d in runs.values() if d.get("crashed")), dict(viol) or 0,
                sum(int(d.get("warning_count") or 0) for d in runs.values()), dict(alarms) or 0))


def sec_spawn():
    out("=" * 110)
    out("SPAWN ENVIRONMENT - VICTIM_SPAWN_MODE 1: the two arms see the same victims per seed; none on the ring")
    a, b = load("fb3vs0"), load("fb3vs3")
    ring = {(40, 25), (32, 46), (13, 34), (7, 12), (30, 11), (25, 48), (10, 25), (25, 3), (14, 44), (17, 12)}
    same = sum(1 for k in set(a) & set(b) if (a[k].get("fb3") or {}).get("spawn") == (b[k].get("fb3") or {}).get("spawn"))
    on_ring = sum(1 for d in a.values() for c in ((d.get("fb3") or {}).get("spawn") or {}).values() if tuple(c) in ring)
    out("  same spawn in both arms: %d / %d | spawn cells on a ring cell: %d" % (same, len(set(a) & set(b)), on_ring))


def sec_rbgate():
    out("=" * 110)
    out("ROUTE_BLOCKED GATE - %s (SEARCHER_TARGETING 3) vs fx3gS (the shipped state); no NEW loss" % RB_TAG)
    pooled = collections.Counter()
    for sh, w in (("a", "east"), ("b", "east"), ("c", "east"), ("s", "south")):
        fr = os.path.join(HERE, "_rblatch_camp2_fx3gS%s_D_%s.json" % (sh, w))
        fs = os.path.join(HERE, "_rblatch_camp2_%s%s_D_%s.json" % (RB_TAG, sh, w))
        if not (os.path.exists(fr) and os.path.exists(fs)):
            out("  shard %s MISSING" % sh)
            continue
        z, s = json.load(open(fr, encoding="utf-8")), json.load(open(fs, encoding="utf-8"))
        ez = {int(e["seed"]): e for e in (z.get("evals") or [])}
        es_ = {int(e["seed"]): e for e in (s.get("evals") or [])}
        loss, gain = [], []
        for seed in sorted(set(ez) & set(es_)):
            rz, rs = ez[seed].get("rescued"), es_[seed].get("rescued")
            if rs < rz:
                loss.append((seed, rz, rs))
            elif rs > rz:
                gain.append((seed, rz, rs))
        out("  shard %s %-5s rescued %d -> %d | dead %d -> %d | NEW losses %s gains %s | recoveries %d -> %d | latched %d" % (
            sh, w, sum(e["rescued"] for e in ez.values()), sum(e["rescued"] for e in es_.values()),
            sum(e.get("dead") or 0 for e in ez.values()), sum(e.get("dead") or 0 for e in es_.values()),
            loss or "none", gain or "none", len(z.get("recoveries") or []), len(s.get("recoveries") or []),
            len(s.get("latched") or [])))
        pooled["new"] += len(loss)
        pooled["latched"] += len(s.get("latched") or [])
        pooled["r0"] += sum(e["rescued"] for e in ez.values())
        pooled["r1"] += sum(e["rescued"] for e in es_.values())
    out("  POOLED rescued %d -> %d | NEW losses %d | latched at end %d  => %s" % (
        pooled["r0"], pooled["r1"], pooled["new"], pooled["latched"],
        "PASS" if pooled["new"] == 0 and pooled["latched"] == 0 else "FAIL"))


SECTIONS = {"prov": sec_prov, "ident": sec_ident, "gates": sec_gates, "ffosc": sec_ffosc, "outcomes": sec_outcomes,
            "exposure": sec_exposure, "targeting": sec_targeting, "invariants": sec_invariants, "spawn": sec_spawn,
            "rbgate": sec_rbgate}


def main():
    names = _ARGS or list(SECTIONS)
    for n in names:
        SECTIONS[n]()


if __name__ == "__main__":
    main()
