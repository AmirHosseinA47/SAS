"""untune Part 3 screen analysis (outputs/untune_part1.txt 7.2 / 7.3 / 11.10). A development check, not a result.

usage: _ut_analyze.py [section ...]   sections: prov ident gates outcomes where attrib exposure invariants ffosc r5
                                                rbgate (default: all)
Reuses outputs/_fb3_analyze.py's measures unchanged (searcher (O) episodes broad + pocket, never-finish,
detection times from the stdout '[Victim Detection]' events, coverage, exposure, invariants, the rbgate shards).
Pairs: as shipped (SEARCHER_UNTUNED 0) vs untuned (1), same seeds, CRN on, per placement x seed set.
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
import _fb3_analyze as A  # noqa: E402

R = A.R
PAIRS = (("ut0r", "ut1r", "ring set 1"), ("ut0r2", "ut1r2", "ring set 2"),
         ("ut0u", "ut1u", "uniform set 1"), ("ut0u2", "ut1u2", "uniform set 2"))
A.GATED = {p[1] for p in PAIRS}
A.NAMES.update({"ut0r": "SHIP ring1", "ut1r": "UNT ring1", "ut0r2": "SHIP ring2", "ut1r2": "UNT ring2",
                "ut0u": "SHIP uni1", "ut1u": "UNT uni1", "ut0u2": "SHIP uni2", "ut1u2": "UNT uni2"})
PHASES = ("exploration", "evacuation", "rescue_active", "degraded_operation", "emergency")
out = A.out


def _passes():
    """Run an _fb3_analyze section over all four pairs (it iterates SET1, SET2, SPAWN)."""
    return ((PAIRS[0], PAIRS[1], PAIRS[2]), (PAIRS[3],))


def _with_pairs(fn):
    for group in _passes():
        trip = [(p[0], (p[1],)) for p in group] + [("", ())] * (3 - len(group))
        A.SET1, A.SET2, A.SPAWN = trip
        fn()


def sec_prov():
    out("=" * 110)
    out("PROVENANCE - heads, source hashes vs this tree, the untune switch each run saw, CRN, ut observer errors")
    for tag in ("utid", "utidu") + tuple(t for p in PAIRS for t in p[:2]):
        runs = A.load(tag)
        if not runs:
            out("  %-6s (no runs)" % tag)
            continue
        heads = collections.Counter(str(d.get("head"))[:8] for d in runs.values())
        bad = sum(1 for d in runs.values() for rel, sha in (d.get("src_sha") or {}).items()
                  if os.path.exists(os.path.join(A.REPO, rel)) and R.raw_sha(os.path.join(A.REPO, rel)) != sha)
        sw = collections.Counter(json.dumps((d.get("ut") or {}).get("switch")) for d in runs.values())
        crn = collections.Counter(str(((d.get("fb3") or {}).get("crn") or {}).get("on")) for d in runs.values())
        spawn = collections.Counter(str(((d.get("fb3") or {}).get("eff") or {}).get("victim_spawn_mode"))
                                    for d in runs.values())
        errs = sum(len((d.get("ut") or {}).get("errors") or []) for d in runs.values())
        out("  %-6s runs %2d heads %s | src differing %d | switch %s | crn %s | spawn mode %s | ut errors %d" % (
            tag, len(runs), dict(heads), bad, dict(sw), dict(crn), dict(spawn), errs))


def sec_ident():
    out("=" * 110)
    out("ID - SEARCHER_UNTUNED 0 through the ut probe, CRN off: value identity on the fx3m FIELDS + every mf2 section")
    for tag, ref in (("utid", "fb3idg"), ("utidu", "fb3vs0")):
        if not A.load(tag):
            out("  %s (no runs)" % tag)
            continue
        same, n, lines = R.probe_ident(tag, ref)
        out("  %-6s vs %-7s %d / %d identical  => %s" % (tag, ref, same, n, "PASS" if same == n == 16 else "FAIL - STOP"))
        for ln in lines:
            out(ln)


def _ut_rows(d):
    return {int(r[0]): r for r in ((d.get("ut") or {}).get("rows") or [])}


def _last_detection(d):
    t = A.det_times(d)
    return max(t.values()) if t and all(v is not None for v in t.values()) else None


def _case_at(rows, s):
    r = rows.get(s) or rows.get(s - 1)
    if r is None:
        return "?"
    pf, kf = r[1], r[2]
    return "A" if pf > 0 and kf == 0 else "B" if pf == 0 and kf > 0 else "-"


def sec_gates():
    out("=" * 110)
    out("GATES G-N / G-O (untune_part1.txt 7.2): untuned vs as shipped on the same seeds, per placement x seed set;"
        " must not rise (target 0). Episodes listed with: after the last detection? and case A / B at their start")
    verdict = []
    for ref, arm, label in PAIRS:
        out("  -- %s" % label)
        A._gate_pair(ref, (arm,))
        rr, ra = A.load(ref), A.load(arm)
        if not rr or not ra:
            verdict.append((label, "MISSING"))
            continue
        n_ref = sum(1 for d in rr.values() if not d.get("terminal_step"))
        n_arm = sum(1 for d in ra.values() if not d.get("terminal_step"))
        o_ref = [A.searcher_o(d) for d in rr.values()]
        o_arm = {k: A.searcher_o(d) for k, d in ra.items()}
        b_ref, b_arm = sum(len(x[0]) for x in o_ref), sum(len(x[0]) for x in o_arm.values())
        p_ref, p_arm = sum(x[1] for x in o_ref), sum(x[1] for x in o_arm.values())
        a_ref, a_arm = sum(x[2] for x in o_ref), sum(x[2] for x in o_arm.values())
        ok = n_arm <= n_ref and b_arm <= b_ref and p_arm <= p_ref and a_arm <= a_ref
        verdict.append((label, "PASS" if ok else "FAIL", "N %d->%d" % (n_ref, n_arm),
                        "O broad %d->%d pocket-near %d->%d pocket-any %d->%d" % (b_ref, b_arm, p_ref, p_arm, a_ref, a_arm)))
        for tag, runs in ((ref, rr), (arm, ra)):
            for k, d in sorted(runs.items()):
                rows, last = _ut_rows(d), _last_detection(d)
                for e in A.searcher_o(d)[0]:
                    out("     %-6s %s ep uid %s steps %d-%d (%d) mech %s | last detection %s -> %s | case %s" % (
                        tag, k, e[0], e[1], e[2], e[3], e[4], last,
                        "AFTER" if last is not None and e[1] >= last else "before", _case_at(rows, e[1])))
    out("  VERDICT:")
    for v in verdict:
        out("    %s" % (v,))


def sec_outcomes():
    _with_pairs(A.sec_outcomes)


def sec_exposure():
    _with_pairs(A.sec_exposure)


def sec_invariants():
    _with_pairs(A.sec_invariants)


def sec_ffosc():
    _with_pairs(A.sec_ffosc)


def sec_r5():
    _with_pairs(A.sec_r5)


def _ev(d, key):
    return int((d.get("eval") or {}).get(key) or 0)


def sec_where():
    out("=" * 110)
    out("WHERE - untuned minus as shipped, per scenario x wind (summed over the cell's run), and per victim location")
    for ref, arm, label in PAIRS:
        rr, ra = A.load(ref), A.load(arm)
        if not rr or not ra:
            continue
        out("  -- %s" % label)
        out("     cell  rescued  dead  never_det  mean_det(eligible)  | identical trajectories?")
        for k in sorted(set(rr) & set(ra)):
            a, b = rr[k], ra[k]
            el = A.eligible_victims(a, b)
            ma, mb = A.run_mean_det(a, el), A.run_mean_det(b, el)
            nda = sum(1 for t in A.det_times(a).values() if t is None)
            ndb = sum(1 for t in A.det_times(b).values() if t is None)
            same = a.get("rows_uav") == b.get("rows_uav")
            out("     %-4s  %d->%d   %d->%d   %d->%d   %s  | %s" % (
                k, _ev(a, "rescued"), _ev(b, "rescued"), _ev(a, "dead"), _ev(b, "dead"), nda, ndb,
                "%.1f->%.1f" % (ma, mb) if ma is not None and mb is not None else "n/a", "SAME" if same else "differ"))
        by_wind = collections.defaultdict(collections.Counter)
        for k in sorted(set(rr) & set(ra)):
            w = k.split("_")[1]
            by_wind[w]["differ"] += rr[k].get("rows_uav") != ra[k].get("rows_uav")
            by_wind[w]["d_rescued"] += _ev(ra[k], "rescued") - _ev(rr[k], "rescued")
            by_wind[w]["d_dead"] += _ev(ra[k], "dead") - _ev(rr[k], "dead")
        out("     by wind: %s" % {w: dict(c) for w, c in sorted(by_wind.items())})
        # per victim location: first detection step summed differences, by region of the spawn cell
        reg = collections.defaultdict(list)
        for k in sorted(set(rr) & set(ra)):
            sp = ((rr[k].get("fb3") or {}).get("spawn") or {})
            ta, tb = A.det_times(rr[k]), A.det_times(ra[k])
            for vid, cell in sp.items():
                if vid not in ta or vid not in tb:
                    continue
                x, y = cell
                va = min(ta[vid], A.H) if ta[vid] is not None else A.H
                vb = min(tb[vid], A.H) if tb[vid] is not None else A.H
                if (ta[vid] is not None and ta[vid] <= 1) or (tb[vid] is not None and tb[vid] <= 1):
                    continue
                for name in (("west" if x < 25 else "east"), ("south" if y < 25 else "north"),
                             ("edge band" if not (4 <= x <= 45 and 4 <= y <= 45) else "interior")):
                    reg[name].append(vb - va)
                if label.startswith("ring"):
                    reg["ring %s (%d,%d)" % (vid, x, y)].append(vb - va)
        for name, vals in sorted(reg.items()):
            out("     detection step (untuned - shipped, censored at %d) %-22s n %3d mean %+.1f median %+.1f |"
                " earlier %d later %d equal %d" % (A.H, name, len(vals), statistics.mean(vals),
                                                   statistics.median(vals), sum(v < 0 for v in vals),
                                                   sum(v > 0 for v in vals), sum(v == 0 for v in vals)))


def sec_attrib():
    out("=" * 110)
    out("ATTRIBUTION (11.10) - from the ut recorders: steps in case A (privileged searcher count > 0, known = 0) and"
        " case B (privileged 0, known > 0); mission-phase steps that differ between the two mission counts; the"
        " escape x bounds firings; the untuned sweep latches")
    for ref, arm, label in PAIRS:
        for tag in (ref, arm):
            runs = A.load(tag)
            if not runs:
                continue
            c = collections.Counter()
            latches = collections.Counter()
            for d in runs.values():
                u = d.get("ut") or {}
                for r in u.get("rows") or []:
                    pf, kf, pm, km, ph_p, ph_k, ph_a = r[1:8]
                    c["steps"] += 1
                    c["caseA"] += pf > 0 and kf == 0
                    c["caseB"] += pf == 0 and kf > 0
                    c["mission_differs"] += pm != km
                    c["mission_gt0_differs"] += (pm > 0) != (km > 0)
                    c["phase_differs"] += ph_p != ph_k
                    c["runs_with_caseA"] += 0
                c["runs_with_caseA"] += any(r[1] > 0 and r[2] == 0 for r in u.get("rows") or [])
                c["runs_with_caseB"] += any(r[1] == 0 and r[2] > 0 for r in u.get("rows") or [])
                for k2, v in (u.get("corridor") or {}).items():
                    c["corr_" + k2] += int(v or 0)
                for uid, latch in (u.get("sweep") or {}).items():
                    latches[json.dumps(latch)] += 1
            out("  %-10s %-6s %s" % (label, tag, dict(c)))
            out("               sweep latches at the end: %s" % dict(latches))


def sec_rbgate():
    A.RB_TAG = "utg"
    out("(route_blocked gate: utg = the fx3gS shards + SEARCHER_UNTUNED=1; the header line below names the old arm)")
    A.sec_rbgate()


SECTIONS = {"prov": sec_prov, "ident": sec_ident, "gates": sec_gates, "outcomes": sec_outcomes, "where": sec_where,
            "attrib": sec_attrib, "exposure": sec_exposure, "invariants": sec_invariants, "ffosc": sec_ffosc,
            "r5": sec_r5, "rbgate": sec_rbgate}


def main():
    for n in (_ARGS or list(SECTIONS)):
        SECTIONS[n]()


if __name__ == "__main__":
    main()
