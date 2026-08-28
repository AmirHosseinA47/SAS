"""Analyse the before/after route_blocked campaign JSONs."""
from __future__ import annotations
import collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = {473: "survival-fallthrough", 484: "survival-fallthrough",
        522: "moving-to-victim", 533: "moving-to-victim",
        557: "exiting-with-victim", 568: "exiting-with-victim"}


def load(tag):
    out = []
    for wind in ("east", "south"):
        p = os.path.join(HERE, "_rb_%s_D_%s.json" % (tag, wind))
        if os.path.exists(p):
            with open(p) as f:
                out.append(json.load(f))
        else:
            print("MISSING %s" % p)
    return out


def sitename(line):
    return SITE.get(int(line), "line-%s" % line)


def summarise(tag):
    docs = load(tag)
    if not docs:
        return None
    calls, fires, marks, deaths, latched, evals = [], [], [], [], [], []
    stats = collections.Counter()
    timing = collections.Counter()
    for d in docs:
        w = d["wind"]
        # east and south reuse the same seed numbers - tag every record with the
        # wind so (wind, seed, ff) is a unique run/unit key.
        for rec in d["calls"] + d["fires"] + d["marks"] + d["deaths"] + d.get("latched", []):
            rec["wind"] = w
        calls += d["calls"]
        fires += d["fires"]
        marks += d["marks"]
        deaths += d["deaths"]
        latched += d.get("latched", [])
        for e in d["evals"]:
            e = dict(e)
            e["wind"] = d["wind"]
            evals.append(e)
        stats.update(d["stats"])
        timing.update(d.get("timing_ns", {}))
    return {"calls": calls, "fires": fires, "marks": marks, "deaths": deaths,
            "latched": latched, "evals": evals, "stats": stats, "timing": timing,
            "windows": [(d["wind"], d["seeds"]) for d in docs]}


def call_table(s, label):
    calls = s["calls"]
    n = len(calls)
    print("  %s: %d _move_toward calls across %d runs" % (label, n, len(s["evals"])))
    by = collections.Counter(sitename(c["line"]) for c in calls)
    for k, v in sorted(by.items()):
        print("      site %-22s %5d  (%.1f%%)" % (k, v, 100.0 * v / max(n, 1)))
    old = [c for c in calls if c["scored_empty"]]
    new = [c for c in calls if c["bfs"] is None]
    newa = [c for c in new if not c["exiting"]]
    print("      all-4-neighbours-burning (old cond) : %4d  (%.2f%%)"
          % (len(old), 100.0 * len(old) / max(n, 1)))
    print("      no-live-path            (new cond) : %4d  (%.2f%%)"
          % (len(new), 100.0 * len(new) / max(n, 1)))
    print("      no-live-path, approach only        : %4d  (%.2f%%)"
          % (len(newa), 100.0 * len(newa) / max(n, 1)))
    for lbl, sub in (("old", old), ("new", new)):
        b = collections.Counter(sitename(c["line"]) for c in sub)
        if b:
            print("      %s-cond hits by site: %s"
                  % (lbl, ", ".join("%s=%d" % kv for kv in sorted(b.items()))))
    print("      ACTUAL route_blocked transitions   : %4d  (%.2f%% of calls)"
          % (len(s["fires"]), 100.0 * len(s["fires"]) / max(n, 1)))
    print("      _mark_route_blocked calls          : %4d   suppressed: %d "
          "(of which standing-in-fire: %d)"
          % (s["stats"]["mark_calls"], s["stats"]["mark_suppressed"],
             s["stats"]["mark_suppressed_self_on_fire"]))


def episodes(calls, *, approach_only=True):
    """Contiguous per-(seed,ff) runs of no-live-path calls -> first step of each."""
    by = collections.defaultdict(list)
    for c in calls:
        if c["bfs"] is not None:
            continue
        if approach_only and c["exiting"]:
            continue
        by[(c["wind"], c["seed"], c["ff"])].append(c["step"])
    eps = []
    for (wind, seed, ff), steps in by.items():
        steps = sorted(set(steps))
        start = prev = steps[0]
        for st in steps[1:]:
            if st - prev > 3:
                eps.append((wind, seed, ff, start, prev))
                start = st
            prev = st
        eps.append((wind, seed, ff, start, prev))
    return sorted(eps)


def lead_times(s, label, *, counterfactual):
    deaths = s["deaths"]
    print("\n  %s - lead time before each firefighter death (%d deaths)"
          % (label, len(deaths)))
    if counterfactual:
        eps = episodes(s["calls"])
        src = collections.defaultdict(list)
        for wind, seed, ff, first, last in eps:
            src[(wind, seed, ff)].append((first, last))
    else:
        src = collections.defaultdict(list)
        for f in s["fires"]:
            src[(f["wind"], f["seed"], f["ff"])].append((f["step"], f["step"]))
    hits = 0
    print("      %-6s %-6s %-11s %-6s  %-28s %s"
          % ("wind", "seed", "ff", "death", "signal (counterfactual)" if counterfactual
             else "signal (actual firing)", "lead"))
    for d in sorted(deaths, key=lambda x: (x["wind"], x["seed"], x["step"])):
        key = (d["wind"], d["seed"], d.get("unit_id") or d["ff_id"])
        cands = [w for w in src.get(key, []) if w[0] <= d["step"]]
        if cands:
            first = min(c[0] for c in cands)
            lead = d["step"] - first
            hits += 1
            note = "step %d" % first
        else:
            lead = None
            note = "never fired before death"
        print("      %-6s %-6s %-11s %-6s  %-28s %s"
              % (d["wind"], d["seed"], key[2], d["step"], note,
                 ("%d steps" % lead) if lead is not None else "-"))
    print("      signalled before death: %d/%d" % (hits, len(deaths)))


def metrics(before, after):
    print("\n  PER-SEED METRICS (campaign config: 2 fire-trackers + 2 searchers)")
    print("      %-6s %-6s | %-22s | %-22s | %s"
          % ("wind", "seed", "before r/d/ff", "after r/d/ff", "delta"))
    bi = {(e["wind"], e["seed"]): e for e in before["evals"]}
    ai = {(e["wind"], e["seed"]): e for e in after["evals"]} if after else {}
    tb = [0, 0, 0]
    ta = [0, 0, 0]
    for k in sorted(bi):
        b = bi[k]
        a = ai.get(k)
        bv = (b.get("rescued"), b.get("dead"), b.get("firefighter_deaths"))
        tb[0] += bv[0] or 0; tb[1] += bv[1] or 0; tb[2] += bv[2] or 0
        if a is None:
            print("      %-6s %-6s | r=%s d=%s ff=%s        | %-22s |"
                  % (k[0], k[1], bv[0], bv[1], bv[2], "(not run)"))
            continue
        av = (a.get("rescued"), a.get("dead"), a.get("firefighter_deaths"))
        ta[0] += av[0] or 0; ta[1] += av[1] or 0; ta[2] += av[2] or 0
        delta = "same" if av == bv else "r%+d d%+d ff%+d" % (
            (av[0] or 0) - (bv[0] or 0), (av[1] or 0) - (bv[1] or 0),
            (av[2] or 0) - (bv[2] or 0))
        print("      %-6s %-6s | r=%s d=%s ff=%s%s| r=%s d=%s ff=%s%s| %s"
              % (k[0], k[1], bv[0], bv[1], bv[2], " " * 10,
                 av[0], av[1], av[2], " " * 10, delta))
    print("      TOTALS before r=%d d=%d ff=%d | after r=%d d=%d ff=%d"
          % (tb[0], tb[1], tb[2], ta[0], ta[1], ta[2]))


def main():
    before = summarise("before")
    after = summarise("after")
    print("=" * 78)
    print("route_blocked CAMPAIGN ANALYSIS")
    print("=" * 78)
    for tag, s in (("BEFORE (unmodified HEAD)", before), ("AFTER (fix applied)", after)):
        if s is None:
            print("\n%s: no data" % tag)
            continue
        print("\n%s" % tag)
        call_table(s, "calls")
        ns = s["timing"]
        tot = len(s["calls"]) or 1
        print("      cost: _fire_cells %.2f ms/call, BFS %.2f ms/call, "
              "%.1f s total over %d calls"
              % (ns.get("firecells_ns", 0) / 1e6 / tot,
                 ns.get("bfs_ns", 0) / 1e6 / tot,
                 (ns.get("firecells_ns", 0) + ns.get("bfs_ns", 0)) / 1e9, tot))
        wall = sum(float(e.get("wall_s") or 0) for e in s["evals"])
        if wall:
            print("      total run wall time %.0f s -> instrumentation share %.2f%%"
                  % (wall, 100.0 * (ns.get("firecells_ns", 0)
                                    + ns.get("bfs_ns", 0)) / 1e9 / wall))
        if s["latched"]:
            print("      LATCHED (alive, still route_blocked at end of run): %d"
                  % len(s["latched"]))
            for l in s["latched"]:
                print("          %s seed=%s %s pos=%s assigned=%s target=%s"
                      % (l["wind"], l["seed"], l["ff_id"], l["pos"], l["assigned"],
                         l["target_pos"]))
        else:
            print("      LATCHED at end of run: 0")

    if before:
        lead_times(before, "BEFORE / counterfactual: when the NEW condition WOULD "
                   "first have gone true", counterfactual=True)
        lead_times(before, "BEFORE / actual old-trigger firings",
                   counterfactual=False)
    if after:
        lead_times(after, "AFTER / actual firings", counterfactual=False)
        print("\n  AFTER firings in detail:")
        for f in after["fires"]:
            print("      %-6s seed=%-5s step=%-4s ff=%-11s exiting=%-5s "
                  "self_on_fire=%-5s pos=%s"
                  % (f["wind"], f["seed"], f["step"], f["ff"], f["exiting"],
                     f["self_on_fire"], f["pos"]))
    if before and after:
        metrics(before, after)


main()
