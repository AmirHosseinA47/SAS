"""Phantom-rescue round: mechanism and seed-matched analysis over the 13-run
scenario-D sample recorded by outputs/_ffr_harness.py.

usage:
  _ph_analyze.py --base ph5000                       # mechanism report, one arm
  _ph_analyze.py --base ph5000 --feat phfix          # + seed-matched comparison
  _ph_analyze.py --identity ph5000 vmon3             # are two recorded arms the same runs?

Everything is derived from the recorded event trail. Event steps are the
value of evaluation_timesteps_counter when the event fired; per-step state
rows (ff_steps, ff_bind_steps, victim_steps) at index i hold the state after
step i+1, so an event at step s is reflected in row s-1 (checked on
D/east/half 303: the assign at step 41 shows assigned=True in row 40, the
completion at step 101 shows the unit off-grid in row 100).

Per run:
  double-assignments   an accepted assign of victim V to unit B while unit A,
                       alive and neither unassigned nor completed, is bound to V
  releases             unassigns carrying the fix reason
  phantom exits        exiting False->True with no victim under the unit
  phantom completions  a second completion for a victim already completed
  phantom absences     a rescue absence taken for a victim another unit had
                       already carried out
  loser bound-steps    steps a losing claimant stayed bound after the rescue
  dead-bound           a unit still bound to a victim after that victim died
                       (the victim_dead recall skips route_blocked units)
and, when ff_bind_steps is present (harness from this round on), a stranding
check: every released unit must later be in the dispatch pool, be assigned
again, be dead or off-grid, or have had no confirmed victim left to serve.
"""
from __future__ import annotations

import argparse
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
RUNS = (
    [("east", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("east", "default", s) for s in (101, 202, 303)]
)
DEFAULT_RELEASE = "released_after_rescue_complete"
RECALL_REASONS = ("fire_casualty", "victim_dead_recall")


def _name(tag, wind, roles, seed):
    rr = "def" if roles == "default" else roles
    return os.path.join(BASE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def load(tag):
    runs = {}
    for k in RUNS:
        p = _name(tag, *k)
        if not os.path.exists(p):
            print("  MISSING %s" % os.path.basename(p))
            continue
        with open(p, encoding="utf-8") as f:
            runs[k] = json.load(f)
    return runs


def label(k):
    return "%s/%-4s %d" % (k[0], "def" if k[1] == "default" else k[1], k[2])


def rule(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def first_divergence(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i + 1
    if len(a) != len(b):
        return n + 1
    return None


def analyze_run(run, release_reason):
    steps_total = int(run.get("steps", 240) or 240)
    ev = []
    for a in run.get("assigns") or []:
        if a.get("ok"):
            ev.append((int(a["step"]), 2, "assign", str(a["ff"]), str(a["vid"]), str(a.get("reason", ""))))
    for u in run.get("unassigns") or []:
        if u.get("ok"):
            ev.append((int(u["step"]), 1, "unassign", str(u["ff"]), str(u["vid"]), str(u.get("reason", ""))))
    for c in run.get("completions") or []:
        ev.append((int(c["step"]), 0, "complete", str(c["ff"]), str(c["victim"]), ""))
    # within a step: completions happen in the move phase, unassigns (release,
    # drain, recall) after it, re-dispatch assigns last
    ev.sort(key=lambda e: (e[0], e[1]))

    death_step = {}
    for i, row in enumerate(run.get("victim_steps") or []):
        for v in row:
            if v[2] == "dead" and v[0] not in death_step:
                death_step[v[0]] = i + 1
    deaths_by_step = {}
    for vid, s in death_step.items():
        deaths_by_step.setdefault(s, []).append(vid)

    bound = {}
    doubles, releases, phantom_completions, losers, dead_bound = [], [], [], [], []
    first_completion = {}
    loser_open = {}
    deadb_open = {}
    steps_seen = sorted(set([e[0] for e in ev] + list(deaths_by_step.keys())))
    idx = 0
    for s in steps_seen:
        while idx < len(ev) and ev[idx][0] == s:
            step, _o, kind, ff, vid, reason = ev[idx]
            idx += 1
            if kind == "assign":
                others = sorted(f for f, v in bound.items() if v == vid and f != ff)
                if others:
                    doubles.append({"step": step, "vid": vid, "first": others[0], "second": ff, "reason": reason})
                bound[ff] = vid
            elif kind == "unassign":
                bound.pop(ff, None)
                if release_reason and release_reason in reason:
                    releases.append({"step": step, "ff": ff, "vid": vid})
                if ff in loser_open:
                    st, lv = loser_open.pop(ff)
                    losers.append({"ff": ff, "vid": lv, "from": st, "to": step, "bound_steps": step - st, "end": "unassign:" + reason})
                if ff in deadb_open:
                    st, dv = deadb_open.pop(ff)
                    dead_bound.append({"ff": ff, "vid": dv, "from": st, "to": step, "bound_steps": step - st, "end": "unassign:" + reason})
            else:
                if vid not in first_completion:
                    first_completion[vid] = (step, ff)
                    for f, v in list(bound.items()):
                        if v == vid and f != ff:
                            loser_open[f] = (step, vid)
                else:
                    phantom_completions.append({"step": step, "ff": ff, "vid": vid,
                                                "first_by": first_completion[vid][1],
                                                "first_step": first_completion[vid][0]})
                bound.pop(ff, None)
                if ff in loser_open:
                    st, lv = loser_open.pop(ff)
                    losers.append({"ff": ff, "vid": lv, "from": st, "to": step, "bound_steps": step - st, "end": "phantom_completion"})
                if ff in deadb_open:
                    st, dv = deadb_open.pop(ff)
                    dead_bound.append({"ff": ff, "vid": dv, "from": st, "to": step, "bound_steps": step - st, "end": "phantom_completion"})
        for vid in deaths_by_step.get(s, []):
            for f, v in bound.items():
                if v == vid and f not in deadb_open:
                    deadb_open[f] = (s, vid)
    for f, (st, lv) in loser_open.items():
        losers.append({"ff": f, "vid": lv, "from": st, "to": steps_total, "bound_steps": steps_total - st, "end": "horizon"})
    for f, (st, dv) in deadb_open.items():
        dead_bound.append({"ff": f, "vid": dv, "from": st, "to": steps_total, "bound_steps": steps_total - st, "end": "horizon"})

    for d in doubles:
        fc = first_completion.get(d["vid"])
        if fc is None:
            d["outcome"] = "victim_dead" if d["vid"] in death_step else "unresolved"
        elif fc[1] == d["second"]:
            d["outcome"] = "second_rescued@%d" % fc[0]
        elif fc[1] == d["first"]:
            d["outcome"] = "first_rescued@%d" % fc[0]
        else:
            d["outcome"] = "other_rescued:%s@%d" % (fc[1], fc[0])

    phantom_exits = [e for e in run.get("exit_starts") or [] if not e.get("contact")]
    removed = [e for e in run.get("absence_log") or [] if e.get("event") == "removed"]
    phantom_abs = []
    for e in removed:
        fc = first_completion.get(str(e.get("victim", "")))
        if fc is not None and fc[1] != str(e.get("ff", "")) and fc[0] < int(e.get("step", 0)):
            phantom_abs.append({"step": int(e["step"]), "ff": e["ff"], "vid": e.get("victim"),
                                "duration": e.get("duration"), "first_by": fc[1], "first_step": fc[0]})
    return {
        "doubles": doubles,
        "releases": releases,
        "phantom_exits": phantom_exits,
        "phantom_completions": phantom_completions,
        "phantom_absences": phantom_abs,
        "absences_total": len(removed),
        "losers": losers,
        "dead_bound": dead_bound,
        "first_completion": first_completion,
    }


def stranding(run, releases):
    fb = run.get("ff_bind_steps")
    rows = run.get("ff_steps") or []
    vs = run.get("victim_steps") or []
    out = []
    for r in releases:
        s, ff = int(r["step"]), r["ff"]
        rec = {"step": s, "ff": ff, "vid": r["vid"]}
        later = [int(a["step"]) for a in run.get("assigns") or []
                 if a.get("ok") and a["ff"] == ff and int(a["step"]) > s]
        rec["next_assign_step"] = min(later) if later else None
        pool = None
        if isinstance(fb, list) and fb:
            for i in range(max(s - 1, 0), len(fb)):
                for b in fb[i]:
                    if b[0] == ff and b[2]:
                        pool = i + 1
                        break
                if pool is not None:
                    break
            rec["pool_step"] = pool
        else:
            rec["pool_step"] = None
            rec["pool_note"] = "no ff_bind_steps in this arm"
        last = None
        if rows:
            for x in rows[-1]:
                if x[0] == ff:
                    last = x
        rec["final"] = last
        work = False
        for i in range(max(s - 1, 0), len(vs)):
            for v in vs[i]:
                if v[2] in ("confirmed", "assigned", "delayed"):
                    work = True
                    break
            if work:
                break
        rec["work_after"] = work
        dead_or_off = bool(last is not None and (last[5] or last[1] is None))
        ok = (rec["next_assign_step"] is not None) or (pool is not None) or dead_or_off or (not work)
        rec["verdict"] = "OK" if ok else "STRANDED?"
        out.append(rec)
    return out


def mechanism(runs, tag, release_reason, recall_check=False):
    rule("MECHANISM: arm %s" % tag)
    tot = {"doubles": 0, "releases": 0, "phantom_exits": 0, "phantom_completions": 0,
           "phantom_absences": 0, "absences_total": 0, "loser_steps": 0, "dead_bound": 0, "dead_bound_steps": 0}
    outcomes = {}
    strand_all = []
    for k in RUNS:
        run = runs.get(k)
        if run is None:
            continue
        a = analyze_run(run, release_reason)
        tot["doubles"] += len(a["doubles"])
        tot["releases"] += len(a["releases"])
        tot["phantom_exits"] += len(a["phantom_exits"])
        tot["phantom_completions"] += len(a["phantom_completions"])
        tot["phantom_absences"] += len(a["phantom_absences"])
        tot["absences_total"] += a["absences_total"]
        tot["loser_steps"] += sum(x["bound_steps"] for x in a["losers"])
        tot["dead_bound"] += len(a["dead_bound"])
        tot["dead_bound_steps"] += sum(x["bound_steps"] for x in a["dead_bound"])
        quiet = not (a["doubles"] or a["releases"] or a["phantom_exits"] or a["phantom_completions"]
                     or a["phantom_absences"] or a["losers"] or a["dead_bound"])
        print("  %-16s absences=%d %s" % (label(k), a["absences_total"], "(no double-claim activity)" if quiet else ""))
        for d in a["doubles"]:
            key = d["outcome"].split("@")[0]
            outcomes[key] = outcomes.get(key, 0) + 1
            print("      DOUBLE   step %3d  %s: first=%s second=%s (%s) -> %s"
                  % (d["step"], d["vid"], d["first"], d["second"], d["reason"], d["outcome"]))
        for r in a["releases"]:
            print("      RELEASE  step %3d  %s freed from %s" % (r["step"], r["ff"], r["vid"]))
        for x in a["losers"]:
            print("      LOSER    %s bound to rescued %s for %d steps (%d-%d, end=%s)"
                  % (x["ff"], x["vid"], x["bound_steps"], x["from"], x["to"], x["end"]))
        for e in a["phantom_exits"]:
            print("      PHANTOM EXIT       step %3d  %s at %s, victim %s pos=%s"
                  % (e["step"], e["ff"], e["ff_pos"], e["victim"], e["victim_pos"]))
        for e in a["phantom_completions"]:
            print("      PHANTOM COMPLETION step %3d  %s for %s (first by %s at %d)"
                  % (e["step"], e["ff"], e["vid"], e["first_by"], e["first_step"]))
        for e in a["phantom_absences"]:
            print("      PHANTOM ABSENCE    step %3d  %s off-grid %s steps for %s (rescued by %s at %d)"
                  % (e["step"], e["ff"], e["duration"], e["vid"], e["first_by"], e["first_step"]))
        for x in a["dead_bound"]:
            print("      DEAD-BOUND %s bound to dead %s for %d steps (%d-%d, end=%s)"
                  % (x["ff"], x["vid"], x["bound_steps"], x["from"], x["to"], x["end"]))
        if a["releases"]:
            for rec in stranding(run, a["releases"]):
                strand_all.append((k, rec))
                print("      STRAND-CHECK %s released@%d: pool_step=%s next_assign=%s work_after=%s final=%s -> %s%s"
                      % (rec["ff"], rec["step"], rec["pool_step"], rec["next_assign_step"], rec["work_after"],
                         rec["final"], rec["verdict"], (" [%s]" % rec["pool_note"]) if rec.get("pool_note") else ""))
        if recall_check:
            recalls = [{"step": int(u["step"]), "ff": str(u["ff"]), "vid": str(u["vid"])}
                       for u in run.get("unassigns") or []
                       if u.get("ok") and str(u.get("reason", "")) in RECALL_REASONS]
            for rec in stranding(run, recalls):
                strand_all.append((k, rec))
                print("      RECALL-CHECK %s recalled@%d: pool_step=%s next_assign=%s work_after=%s final=%s -> %s%s"
                      % (rec["ff"], rec["step"], rec["pool_step"], rec["next_assign_step"], rec["work_after"],
                         rec["final"], rec["verdict"], (" [%s]" % rec["pool_note"]) if rec.get("pool_note") else ""))
    print()
    print("  TOTALS %s: double-assignments %d | releases %d | phantom exits %d | phantom completions %d"
          % (tag, tot["doubles"], tot["releases"], tot["phantom_exits"], tot["phantom_completions"]))
    print("         rescue absences %d, of which phantom %d | loser bound-steps %d | dead-bound cases %d (%d steps)"
          % (tot["absences_total"], tot["phantom_absences"], tot["loser_steps"], tot["dead_bound"], tot["dead_bound_steps"]))
    if outcomes:
        print("         double-assignment outcomes: %s" % ", ".join("%s=%d" % kv for kv in sorted(outcomes.items())))
    bad = [(k, r) for k, r in strand_all if r["verdict"] != "OK"]
    if strand_all:
        print("         stranding check: %d released unit(s), %d flagged" % (len(strand_all), len(bad)))
    return tot, strand_all


def compare(base, feat, base_tag, feat_tag):
    rule("SEED-MATCHED: %s (baseline) vs %s (fix)   r=rescued d=dead f=ff_deaths n=never_detected t=terminal" % (base_tag, feat_tag))
    tb = [0, 0, 0, 0]
    tf = [0, 0, 0, 0]
    ident = 0
    n = 0
    fire_same = 0
    for k in RUNS:
        b = base.get(k)
        f = feat.get(k)
        if b is None or f is None:
            print("  %-16s missing" % label(k))
            continue
        n += 1
        eb, ef = b["eval"], f["eval"]
        vb = [eb["rescued"], eb["dead"], eb["firefighter_deaths"], int(eb.get("never_detected", 0) or 0)]
        vf = [ef["rescued"], ef["dead"], ef["firefighter_deaths"], int(ef.get("never_detected", 0) or 0)]
        for i in range(4):
            tb[i] += vb[i]
            tf[i] += vf[i]
        div = first_divergence(b["fire_digests"], f["fire_digests"])
        if div is None:
            fire_same += 1
        same_out = b["stdout_sha256"] == f["stdout_sha256"]
        same_ff = b["ff_steps"] == f["ff_steps"]
        # rows are [id, pos, status, assigned, exiting, dead]; drop the status
        # label so a D2 relabel (en_route -> available) is told apart from a
        # unit that actually moved or changed flags
        strip = lambda rows: [[[r[0], r[1]] + list(r[3:]) for r in row] for row in rows]
        same_cells = strip(b["ff_steps"]) == strip(f["ff_steps"])
        same_victims = b.get("victim_steps") == f.get("victim_steps")
        same_eval = eb == ef
        same = same_out and same_ff and same_victims and same_eval
        if same:
            ident += 1
            verdict = "identical run"
        else:
            parts = []
            if not same_cells:
                parts.append("ff cells/flags")
            elif not same_ff:
                parts.append("ff status label only")
            if not same_victims:
                parts.append("victim rows")
            if not same_eval:
                parts.append("eval")
            if not same_out:
                parts.append("stdout")
            verdict = "differs: " + ", ".join(parts)
            if not [p for p in parts if p not in ("stdout", "ff status label only")]:
                verdict = "label/stdout ONLY (same cells, flags, victims, eval)"
        print("  %-16s r%d d%d f%d n%d t=%-4s | r%d d%d f%d n%d t=%-4s | %+d %+d %+d %+d | fire %s | %s"
              % (label(k), vb[0], vb[1], vb[2], vb[3], str(eb.get("terminal_step")),
                 vf[0], vf[1], vf[2], vf[3], str(ef.get("terminal_step")),
                 vf[0] - vb[0], vf[1] - vb[1], vf[2] - vb[2], vf[3] - vb[3],
                 "identical" if div is None else "DIVERGES@%d" % div,
                 verdict))
    print()
    print("  TOTAL baseline r=%d d=%d f=%d n=%d | fix r=%d d=%d f=%d n=%d | delta r%+d d%+d f%+d n%+d"
          % (tb[0], tb[1], tb[2], tb[3], tf[0], tf[1], tf[2], tf[3],
             tf[0] - tb[0], tf[1] - tb[1], tf[2] - tb[2], tf[3] - tb[3]))
    print("  fire map identical on %d/%d runs; whole run identical on %d/%d" % (fire_same, n, ident, n))


def identity(a_tag, b_tag):
    a = load(a_tag)
    b = load(b_tag)
    rule("IDENTITY: %s vs %s" % (a_tag, b_tag))
    fields = ["eval", "terminal_step", "fire_digests", "ff_steps", "victim_steps", "completions", "recycles",
              "assigns", "unassigns", "unreachable_marks", "planner", "absence_log", "exit_starts",
              "retargets", "stdout_sha256"]
    same_runs = 0
    for k in RUNS:
        x = a.get(k)
        y = b.get(k)
        if x is None or y is None:
            print("  %-16s missing" % label(k))
            continue
        diff = [fld for fld in fields if x.get(fld) != y.get(fld)]
        if not diff:
            same_runs += 1
        print("  %-16s %s" % (label(k), "identical on all %d fields" % len(fields) if not diff else "DIFFERS: " + ",".join(diff)))
    print("  identical runs: %d/%d" % (same_runs, len(RUNS)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None)
    ap.add_argument("--feat", default=None)
    ap.add_argument("--release-reason", default=DEFAULT_RELEASE)
    ap.add_argument("--identity", nargs=2, default=None, metavar=("TAG_A", "TAG_B"))
    ap.add_argument("--recall-check", action="store_true",
                    help="also run the stranding check on victim_dead recalls (reason fire_casualty)")
    a = ap.parse_args()
    if a.identity:
        identity(a.identity[0], a.identity[1])
        return 0
    if not a.base:
        ap.error("--base or --identity required")
    base = load(a.base)
    mechanism(base, a.base, a.release_reason, recall_check=a.recall_check)
    if a.feat:
        feat = load(a.feat)
        mechanism(feat, a.feat, a.release_reason, recall_check=a.recall_check)
        compare(base, feat, a.base, a.feat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
