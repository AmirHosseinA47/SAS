"""Carrying-leg round, Part 3: READ the D-9 probe (spec L; design D-9 (b); prereg section 9).

MECHANISM EVIDENCE ONLY - never an outcome result, never pooled with any Part 3 set.

Inputs: outputs/_cl_probe_queue.txt (clPS0 / clPS1) and outputs/_cl_probe_crn_queue.txt
(clKPS0 / clKPS1), loaded through _cl_common.RunIndex (full provenance: the line, the harness
JSON, the sidecar - SystemExit on any mismatch) PLUS outputs/_cl_probe.sidecar_problem on
every run (the kill was applied by _cl_probe.py, exactly once, as the line says).

Per tuple and instrument:
  THE KILL      the probe_kill event: step, unit, cell, bound victim, the unassign,
                outcome, and `others` - the premise: another unit alive, on grid and
                exiting at the kill step (a live carrier).
  PRE-SCREEN    the SERVED-0 run's custody markings (_cl_legs.custody_markings: an
                isolation write-off of a victim in a live exiting carrier's custody, M4).
                KEPT iff >= 1. Frozen before any run (spec L). A dropped tuple's SERVED-1
                run is reported for information only.
  SERVED 0 vs 1 (kept tuples)
                custody markings at SERVED 1 (and whether each SERVED-0 marking's victim
                is still marked), SERVED's own site (sidecar served_by_custody_only_not_geo,
                its first event step), the first differing step S1 vs S0 (_cl_common
                .first_diff over the per-step series), the marked victim's fate in each
                (final status, completion step and unit), and the run totals from the
                harness eval (rescued, dead, ff_deaths, terminal_step).
  VERDICT per kept tuple (pre-registered, prereg section 9):
    ACTED CORRECTLY   every SERVED-0 custody marking's victim is unmarked at SERVED 1,
                      served_by_custody_only_not_geo > 0, and the first differing step is
                      >= the first served_by_custody_only_not_geo event step (nothing moved
                      before SERVED's own site fired);
    DID NOT ACT       S1 value-identical to S0 (same custody markings);
    ANOMALY           anything else -> to the maintainer.
  SERVED ships on the probe (D-9) only if EVERY kept tuple reads ACTED CORRECTLY and at
  least one tuple is kept; 0 kept -> "D-9 PROBE FOUND NOTHING TO OBSERVE" -> to the
  maintainer. The fate of the marked victim is REPORTED, never gated (mechanism, not
  outcome).

usage: .venv/Scripts/python.exe -B outputs/_cl_probe_analyze.py [> outputs/_cl_probe_report.txt]
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cl_common as C  # noqa: E402
import _cl_legs as L  # noqa: E402
import _cl_probe as P  # noqa: E402
import _cl_seedcheck  # noqa: E402

QUEUES = (os.path.join(HERE, "_cl_probe_queue.txt"), os.path.join(HERE, "_cl_probe_crn_queue.txt"))
PAIRS = (("stock", "clPS0", "clPS1"), ("crn", "clKPS0", "clKPS1"))


def say(*a):
    print(*a)


def fate(d, vid):
    """(final status, completion step, completing unit) of victim vid."""
    rows = d.get("victim_steps") or []
    status = None
    if rows:
        for r in rows[-1]:
            if r[0] == vid:
                status = r[2]
    comp = [(int(c["step"]), c.get("ff")) for c in d.get("completions") or [] if c.get("victim") == vid]
    return status, (comp[0] if comp else (None, None))


def totals(d):
    ev = d.get("eval") or {}
    return "rescued %s dead %s ff_deaths %s never_detected %s terminal %s" % (
        ev.get("rescued"), ev.get("dead"), ev.get("ff_deaths"), ev.get("never_detected"),
        d.get("terminal_step"))


def kill_of(sc):
    ev = (sc.get("events") or {}).get("probe_kill") or []
    return dict(zip(P.EVENT_FIELDS, ev[0])) if ev else None


def premise(k):
    """A live, on-grid, exiting OTHER unit at the kill step (others: [id, exiting, dead,
    bound, pos])."""
    if not k:
        return False, "no probe_kill event"
    live = [o for o in (k.get("others") or []) if o[1] and not o[2] and o[4] is not None]
    if live:
        return True, "live carrier(s) at the kill: %s" % ", ".join("%s bound %s at %s" % (o[0], o[3] or "-", o[4])
                                                                  for o in live)
    return False, "no live carrier at the kill (others %r)" % (k.get("others"),)


def site_first(sc):
    evs = (sc.get("events") or {}).get("served_by_custody_only") or []
    not_geo = [e for e in evs if isinstance(e, list) and len(e) >= 2 and e[1] is False]
    return (not_geo[0][0] if not_geo else None), len(evs)


def main():
    checked = _cl_seedcheck.run_checks(say=lambda *_a: None)
    sets = C.seed_sets(checked)
    idx = C.RunIndex(list(QUEUES), sets)
    counts = idx.verify_all()
    say("=" * 96)
    say("D-9 PROBE - MECHANISM EVIDENCE ONLY (never an outcome result; never pooled)")
    say("  queues: %s" % ", ".join(os.path.basename(q) for q in QUEUES))
    say("  runs loaded and provenance-checked through _cl_common.RunIndex: %d" % counts["ff"])
    bad = []
    for tag, tup in idx.ff:
        why = P.sidecar_problem(idx.line(tag, tup)["sets"], idx.sidecar(tag, tup))
        if why:
            bad.append("%s %s: %s" % (tag, C.label(tup), why))
    if bad:
        for b in bad:
            say("  PROBE SIDECAR PROBLEM " + b)
        raise SystemExit("CL_PROBE_ANALYZE STOP: %d run(s) without sound probe evidence" % len(bad))
    say("  _cl_probe.sidecar_problem: clean on every run")
    kept, verdicts = 0, []
    for inst, t0, t1 in PAIRS:
        for tup in idx.tuples(t0):
            d0, d1 = idx.load(t0, tup), idx.load(t1, tup)
            s0, s1 = idx.sidecar(t0, tup), idx.sidecar(t1, tup)
            k0, k1 = kill_of(s0), kill_of(s1)
            say("-" * 96)
            say("%s %s  (%s vs %s)" % (inst.upper(), C.label(tup), t1, t0))
            for name, k in (("S0", k0), ("S1", k1)):
                ok, txt = premise(k)
                say("  kill %s: step %s %s at %s bound %r active %s unassign %s -> %s; premise %s: %s" % (
                    name, k["step"], k["ff_id"], k["pos"], k["bound_victim_id"], k["had_active_rescue"],
                    k["unassign_metadata_keys"], k["outcome"], "YES" if ok else "NO", txt))
            m0 = L.custody_markings(d0)
            m1 = L.custody_markings(d1)
            if m0 is None or m1 is None:
                raise SystemExit("CL_PROBE_ANALYZE STOP: a run has no ff_bind_steps")
            marks0, marks1 = m0[0], m1[0]
            say("  S0 custody markings %d: %s" % (len(marks0), "; ".join(
                "%s@%d by %s (%s, streak %s)" % (m["victim"], m["step"], m["ff"], m["kind"], m["streak"])
                for m in marks0) or "none"))
            say("  S1 custody markings %d: %s" % (len(marks1), "; ".join(
                "%s@%d by %s (%s)" % (m["victim"], m["step"], m["ff"], m["kind"]) for m in marks1) or "none"))
            ct1 = s1.get("counters") or {}
            first_site, nsite = site_first(s1)
            fd, fkeys = C.first_diff_detail(d0, d1)
            say("  S1 SERVED site: custody_calls %s custody_victim_steps %s served_by_custody_only %s "
                "not_geo %s (first not-geo event step %s)" % (
                    ct1.get("custody_calls"), ct1.get("custody_victim_steps"), ct1.get("served_by_custody_only"),
                    ct1.get("served_by_custody_only_not_geo"), first_site))
            say("  first differing step S1 vs S0: %s %s" % (fd, fkeys))
            for m in marks0:
                f0, f1 = fate(d0, m["victim"]), fate(d1, m["victim"])
                say("  marked victim %s: S0 final %s completion %s | S1 final %s completion %s" % (
                    m["victim"], f0[0], f0[1], f1[0], f1[1]))
            say("  totals S0: %s" % totals(d0))
            say("  totals S1: %s" % totals(d1))
            if not marks0:
                say("  PRE-SCREEN: DROPPED (no custody marking at SERVED 0) - S1 reported for information only")
                continue
            kept += 1
            still = {m["victim"] for m in marks1} & {m["victim"] for m in marks0}
            first_step = fd
            nog = ct1.get("served_by_custody_only_not_geo") or 0
            if not still and nog > 0 and first_site is not None and (first_step is None or first_step >= first_site):
                v = "ACTED CORRECTLY"
            elif first_step is None and [(m["victim"], m["step"]) for m in marks1] == \
                    [(m["victim"], m["step"]) for m in marks0]:
                v = "DID NOT ACT"
            else:
                v = "ANOMALY -> to the maintainer (still marked %s, not_geo %s, first diff %s, first site %s)" % (
                    sorted(still), nog, first_step, first_site)
            say("  PRE-SCREEN: KEPT.  VERDICT: %s" % v)
            verdicts.append((inst, C.label(tup), v))
    say("=" * 96)
    say("SUMMARY  kept %d of %d tuple/instrument pairs" % (kept, sum(len(idx.tuples(t0)) for _i, t0, _t in PAIRS)))
    for inst, lab, v in verdicts:
        say("  %-5s %-28s %s" % (inst, lab, v))
    if kept == 0:
        say("D-9 PROBE FOUND NOTHING TO OBSERVE -> to the maintainer")
    elif all(v == "ACTED CORRECTLY" for _i, _l, v in verdicts):
        say("D-9 PROBE: SERVED ACTED CORRECTLY on every kept tuple (mechanism evidence)")
    else:
        say("D-9 PROBE: NOT every kept tuple reads ACTED CORRECTLY -> SERVED does not ship on the probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
