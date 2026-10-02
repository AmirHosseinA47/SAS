"""untune RE-SCREEN analysis (outputs/untune_part1.txt 13.5). A development check, not a result.

usage: _ut_analyze2.py [section ...]   sections: prov ident gates latch rbgate recall dead outcomes where attrib
                                                 exposure post invariants ffosc r5 isolation (default: all)
Pairs: as shipped ut0* (reused after ident + spot) vs ut2* (SEARCHER_UNTUNED 1: recall + channel fix on).
Also reported: ut3* (channel fix OFF), ut2bf (Bayes-flee + untuned, ring set 1), the rb shards utR (fix on) and
utQ (fix off). Reuses _ut_analyze.py / _fb3_analyze.py measures unchanged.
"""
from __future__ import annotations

import collections
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_ARGS = sys.argv[1:]
sys.argv = sys.argv[:1]
sys.path.insert(0, HERE)
import _ut_analyze as U  # noqa: E402

A, R = U.A, U.R
out = A.out
PAIRS = (("ut0r", "ut2r", "ring set 1"), ("ut0r2", "ut2r2", "ring set 2"),
         ("ut0u", "ut2u", "uniform set 1"), ("ut0u2", "ut2u2", "uniform set 2"))
OFF = {"ut2r": "ut3r", "ut2r2": "ut3r2", "ut2u": "ut3u", "ut2u2": "ut3u2"}      # channel fix off
PRIOR = {"ut2r": "ut1r", "ut2r2": "ut1r2", "ut2u": "ut1u", "ut2u2": "ut1u2"}    # first screen (no recall / fix)
U.PAIRS = PAIRS
A.GATED = {p[1] for p in PAIRS}
for t in ("ut2r", "ut2r2", "ut2u", "ut2u2"):
    A.NAMES[t] = "UNT+R " + t[3:]
for t in ("ut3r", "ut3r2", "ut3u", "ut3u2"):
    A.NAMES[t] = "UNT+R-fix " + t[3:]
A.NAMES["ut2bf"] = "BF+UNT+R ring1"


def last_det(d):
    return U._last_detection(d)


def episodes(d):
    return A.searcher_o(d)[0]


def ff_status_track(d):
    """Per firefighter: route_blocked sets / clears over the run, and whether it ends route_blocked."""
    prev, sets, clears = {}, collections.Counter(), collections.Counter()
    for row in d["rows_ff"]:
        for f in row:
            fid, st = f[0], str(f[3] or "")
            if st == "route_blocked" and prev.get(fid) != "route_blocked":
                sets[fid] += 1
            elif st != "route_blocked" and prev.get(fid) == "route_blocked":
                clears[fid] += 1
            prev[fid] = st
    latched = sorted(fid for fid, st in prev.items() if st == "route_blocked")
    return sets, clears, latched


def sec_prov():
    out("=" * 110)
    out("PROVENANCE - heads, source hashes vs this tree, switches each run saw, CRN, ut observer errors")
    for tag in ("utid2", "utidu2", "ut0rS", "ut0uS") + tuple(p[1] for p in PAIRS) + tuple(OFF.values()) + ("ut2bf",):
        runs = A.load(tag)
        if not runs:
            out("  %-7s (no runs)" % tag)
            continue
        heads = collections.Counter(str(d.get("head"))[:8] for d in runs.values())
        bad = sum(1 for d in runs.values() for rel, sha in (d.get("src_sha") or {}).items()
                  if os.path.exists(os.path.join(A.REPO, rel)) and R.raw_sha(os.path.join(A.REPO, rel)) != sha)
        sw = collections.Counter(json.dumps((d.get("ut") or {}).get("switch"), sort_keys=True) for d in runs.values())
        crn = collections.Counter(str(((d.get("fb3") or {}).get("crn") or {}).get("on")) for d in runs.values())
        tgt = collections.Counter(str(((d.get("fb3") or {}).get("eff") or {}).get("searcher_targeting"))
                                  for d in runs.values())
        errs = sum(len((d.get("ut") or {}).get("errors") or []) for d in runs.values())
        out("  %-7s runs %2d heads %s | src differing %d | crn %s | targeting %s | ut errors %d" % (
            tag, len(runs), dict(heads), bad, dict(crn), dict(tgt), errs))
        out("          switch %s" % dict(sw))


def sec_ident():
    out("=" * 110)
    out("ID - every switch at default (the ruling switches ship 1 but act only with SEARCHER_UNTUNED 1), CRN off;"
        " and the CRN SPOT CHECK of the reused shipped arm")
    ok = True
    for tag, ref in (("utid2", "fb3idg"), ("utidu2", "fb3vs0")):
        same, n, lines = R.probe_ident(tag, ref)
        ok &= same == n == 16
        out("  %-7s vs %-7s %d / %d identical  => %s" % (tag, ref, same, n, "PASS" if same == n == 16 else "FAIL"))
        for ln in lines:
            out(ln)
    for tag, ref in (("ut0rS", "ut0r"), ("ut0uS", "ut0u")):
        same, n, lines = R.probe_ident(tag, ref)
        ok &= same == n == 4
        out("  %-7s vs %-7s %d / %d identical (CRN)  => %s" % (tag, ref, same, n, "PASS" if same == n == 4 else "FAIL"))
        for ln in lines:
            out(ln)
    out("  => %s" % ("PASS - the shipped arm ut0* is reused" if ok else "FAIL - STOP"))


def sec_gates():
    out("=" * 110)
    out("GATES G-N / G-O (13.5): ut2 (untuned + recall + channel fix) vs ut0 (shipped), same seeds, CRN; must not"
        " rise, target 0. G-O SPLIT before / after each run's own last detection.")
    verdict, pooled = [], collections.Counter()
    for ref, arm, label in PAIRS:
        rr, ra = A.load(ref), A.load(arm)
        if len(rr) != 16 or len(ra) != 16:
            verdict.append((label, "INCOMPLETE %d / %d runs" % (len(rr), len(ra))))
            continue
        n_ref = sorted(k for k, d in rr.items() if not d.get("terminal_step"))
        n_arm = sorted(k for k, d in ra.items() if not d.get("terminal_step"))
        tot = {}
        for tag, runs in ((ref, rr), (arm, ra)):
            c = collections.Counter()
            for k, d in runs.items():
                b, p, a = A.searcher_o(d)
                last = last_det(d)
                c["broad"] += len(b)
                c["near"] += p
                c["any"] += a
                for e in b:
                    when = "after" if last is not None and e[1] >= last else "before"
                    c["broad_" + when] += 1
                    pooled[(tag[:3], when)] += 1
            tot[tag] = c
        cr, ca = tot[ref], tot[arm]
        ok = len(n_arm) <= len(n_ref) and ca["broad"] <= cr["broad"] and ca["near"] <= cr["near"] and ca["any"] <= cr["any"]
        verdict.append((label, "PASS" if ok else "FAIL"))
        out("  %-14s N %d %s -> %d %s | broad %d -> %d (before %d -> %d, after %d -> %d) | pocket near %d -> %d |"
            " pocket any %d -> %d  => %s" % (
                label, len(n_ref), n_ref or "", len(n_arm), n_arm or "", cr["broad"], ca["broad"], cr["broad_before"],
                ca["broad_before"], cr["broad_after"], ca["broad_after"], cr["near"], ca["near"], cr["any"], ca["any"],
                "PASS" if ok else "FAIL"))
        for k, d in sorted(ra.items()):
            last = last_det(d)
            rows = U._ut_rows(d)
            for e in episodes(d):
                out("       %s %s uid %s %d-%d (%d) %s last_det %s %s case %s" % (
                    arm, k, e[0], e[1], e[2], e[3], e[4], last,
                    "AFTER" if last is not None and e[1] >= last else "before", U._case_at(rows, e[1])))
    out("  pooled broad episodes (ut0 shipped, ut2 untuned+recall): %s" % dict(sorted(pooled.items())))
    for tag in tuple(OFF.values()) + ("ut2bf",):
        runs = A.load(tag)
        if not runs:
            continue
        c = collections.Counter()
        for d in runs.values():
            b, p, a = A.searcher_o(d)
            last = last_det(d)
            c["N"] += not d.get("terminal_step")
            c["broad"] += len(b)
            c["near"] += p
            c["any"] += a
            for e in b:
                c["after" if last is not None and e[1] >= last else "before"] += 1
        out("  reported %-6s %s" % (tag, dict(c)))
    out("  VERDICT: %s" % verdict)


def sec_latch():
    out("=" * 110)
    out("LATCH (13.3 caution): route_blocked sets / clears per arm (from rows_ff), units route_blocked at the END of"
        " each run, and NEW latches = a unit latched in the arm that the shipped run on the same seed does not have")
    verdict = []
    for ref, arm, label in PAIRS:
        rr = A.load(ref)
        for tag in (ref, arm, OFF.get(arm)):
            runs = A.load(tag) if tag else {}
            if not runs:
                continue
            S = C = 0
            latched_runs, new = [], []
            for k, d in sorted(runs.items()):
                sets, clears, latched = ff_status_track(d)
                S += sum(sets.values())
                C += sum(clears.values())
                if latched:
                    latched_runs.append((k, latched))
                if tag != ref and k in rr:
                    base = set(ff_status_track(rr[k])[2])
                    extra = sorted(set(latched) - base)
                    if extra:
                        new.append((k, extra))
            out("  %-14s %-6s route_blocked sets %3d clears %3d | runs ending latched %s | NEW latches %s" % (
                label, tag, S, C, latched_runs or "none", (new or "none") if tag != ref else "-"))
            if tag != ref:
                verdict.append((label, tag, ("PASS" if not new else "FAIL") if len(runs) == 16
                                else "INCOMPLETE %d runs" % len(runs)))
    out("  VERDICT (no new latch): %s" % verdict)


def sec_rbgate():
    for tag, what in (("utR", "channel fix ON"), ("utQ", "channel fix OFF")):
        A.RB_TAG = tag
        out("(route_blocked gate: %s = the fx3gS shards + SEARCHER_UNTUNED=1, recall on, %s; the header names the"
            " old arm)" % (tag, what))
        A.sec_rbgate()


def sec_recall():
    out("=" * 110)
    out("RECALL (13.1) - per arm: searchers recalled, recall trigger relative to the run's last detection, legs"
        " that docked, boxed steps on recall legs, searchers airborne at the end")
    for tag in tuple(p[1] for p in PAIRS) + tuple(OFF.values()) + ("ut2bf",):
        runs = A.load(tag)
        if not runs:
            continue
        c = collections.Counter()
        lag = []
        for d in runs.values():
            u = d.get("ut") or {}
            last = last_det(d)
            for uid, trips in (u.get("recall") or {}).items():
                c["searchers"] += 1
                if trips:
                    c["recalled"] += 1
                    c["trips"] += len(trips)
                    t0 = trips[0]
                    c["docked"] += t0.get("arrival_step") is not None
                    c["boxed_steps"] += int(t0.get("boxed_steps") or 0)
                    if last is not None and t0.get("trigger_step") is not None:
                        lag.append(int(t0["trigger_step"]) - int(last))
            rows = u.get("rows") or []
            if rows and len(rows[-1]) > 10:
                c["airborne_end"] += rows[-1][10]
            c["runs_all_found"] += last is not None
        out("  %-6s %s | trigger - last detection: %s" % (
            tag, dict(c), ("min %d median %s max %d" % (min(lag), statistics.median(lag), max(lag))) if lag else "n/a"))


def sec_dead():
    out("=" * 110)
    out("SEARCHING FOR THE DEAD (13.1) - the honest count stays > 0 because a victim died unseen: runs and steps with"
        " known count > 0 and NO live undetected victim (truth-side instrument)")
    for tag in tuple(p[1] for p in PAIRS) + tuple(OFF.values()) + ("ut2bf",):
        runs = A.load(tag)
        if not runs:
            continue
        nruns, steps, cells = 0, 0, []
        for k, d in sorted(runs.items()):
            rows = (d.get("ut") or {}).get("rows") or []
            s = sum(1 for r in rows if len(r) > 8 and r[2] > 0 and r[8] == 0)
            if s:
                nruns += 1
                steps += s
                cells.append((k, s))
        out("  %-6s runs %2d / %2d, steps %4d | %s" % (tag, nruns, len(runs), steps, cells))


def sec_post():
    out("=" * 110)
    out("AFTER THE LAST DETECTION - searcher steps airborne, in fire, on smoke (mf2 uav rows), per arm")
    for ref, arm, label in PAIRS:
        for tag in (ref, arm, OFF.get(arm)):
            runs = A.load(tag) if tag else {}
            if not runs:
                continue
            S = collections.Counter()
            for d in runs.values():
                last = last_det(d)
                if last is None:
                    continue
                S["runs"] += 1
                for t, row in enumerate((d.get("mf2") or {}).get("uav") or []):
                    if t + 1 < last:
                        continue
                    for u in row:
                        if len(u) < 6 or u[1] != "victim_searcher" or not isinstance(u[4], int):
                            continue
                        S["steps"] += 1
                        S["fire"] += u[4]
                        S["smoke"] += u[5]
            out("  %-14s %-6s runs with all found %2d | searcher records after the last detection %5d, in fire %d,"
                " on smoke %d" % (label, tag, S["runs"], S["steps"], S["fire"], S["smoke"]))


def sec_isolation():
    out("=" * 110)
    out("ISOLATION - channel fix: ut2 (on) vs ut3 (off), same head, same seeds; recall: ut3 (recall on, fix off)"
        " vs ut1 (first screen: neither; across heads, reported only)")
    for ref, arm, label in PAIRS:
        a2, a3, a1 = A.load(arm), A.load(OFF[arm]), A.load(PRIOR[arm])
        if not a2 or not a3:
            continue
        diff_cells = [k for k in sorted(set(a2) & set(a3)) if a2[k].get("rows_uav") != a3[k].get("rows_uav")
                      or a2[k].get("rows_ff") != a3[k].get("rows_ff")]
        d_res = sum(U._ev(a2[k], "rescued") - U._ev(a3[k], "rescued") for k in set(a2) & set(a3))
        d_dead = sum(U._ev(a2[k], "dead") - U._ev(a3[k], "dead") for k in set(a2) & set(a3))
        out("  %-14s fix on vs off: cells differing %d %s | rescued %+d dead %+d" % (
            label, len(diff_cells), diff_cells, d_res, d_dead))
        if a1:
            c3 = sum(1 for d in a3.values() for e in episodes(d)
                     if last_det(d) is not None and e[1] >= last_det(d))
            c1 = sum(1 for d in a1.values() for e in episodes(d)
                     if last_det(d) is not None and e[1] >= last_det(d))
            out("  %-14s recall: broad episodes after the last detection ut1 (no recall) %d -> ut3 (recall) %d" % (
                label, c1, c3))


def _with_pairs(fn):
    U._with_pairs(fn)


SECTIONS = {"prov": sec_prov, "ident": sec_ident, "gates": sec_gates, "latch": sec_latch, "rbgate": sec_rbgate,
            "recall": sec_recall, "dead": sec_dead, "outcomes": lambda: _with_pairs(A.sec_outcomes),
            "where": U.sec_where, "attrib": U.sec_attrib, "exposure": lambda: _with_pairs(A.sec_exposure),
            "post": sec_post, "invariants": lambda: _with_pairs(A.sec_invariants),
            "ffosc": lambda: _with_pairs(A.sec_ffosc), "r5": lambda: _with_pairs(A.sec_r5),
            "isolation": sec_isolation}


def main():
    for n in (_ARGS or list(SECTIONS)):
        SECTIONS[n]()


if __name__ == "__main__":
    main()
