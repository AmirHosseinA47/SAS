"""Seed-matched comparison: latch fix vs f2827ed (the trigger-fix round's
_rb_after_*.json), plus the recovery and overcorrection metrics."""
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))


def load(p):
    with open(os.path.join(BASE, p)) as f:
        return json.load(f)


def by_seed(d):
    return {int(ev["seed"]): ev for ev in d.get("evals", [])}


TOT = {"b": [0, 0, 0], "f": [0, 0, 0]}
regressions, ff_up = [], []

for wind in ("east", "south"):
    try:
        base = load("_rb_after_D_%s.json" % wind)
        fix = load("_rblatch_camp_latchfix_D_%s.json" % wind)
    except FileNotFoundError as e:
        print("MISSING: %s" % e)
        continue
    b, f = by_seed(base), by_seed(fix)
    print("=" * 78)
    print("D/%s   f2827ed (baseline)  ->  latch fix        seeds=%d" % (wind, len(f)))
    print("  seed | rescued        | victims dead   | ff_deaths")
    print("  -----+----------------+----------------+---------------")
    sb = [0, 0, 0]
    sf = [0, 0, 0]
    for seed in [int(s) for s in fix["seeds"].split(",")]:
        eb, ef = b.get(seed), f.get(seed)
        if eb is None or ef is None:
            print("  %-4s MISSING" % seed)
            continue
        rb, db, fb = (int(eb.get("rescued") or 0), int(eb.get("dead") or 0),
                      int(eb.get("firefighter_deaths") or 0))
        rf, df, ff = (int(ef.get("rescued") or 0), int(ef.get("dead") or 0),
                      int(ef.get("firefighter_deaths") or 0))
        for i, v in enumerate((rb, db, fb)):
            sb[i] += v
        for i, v in enumerate((rf, df, ff)):
            sf[i] += v
        mark = ""
        if rf < rb:
            mark += "  <-- RESCUED DOWN"
            regressions.append((wind, seed, rb, rf))
        if ff > fb:
            mark += "  <-- ff_deaths up"
            ff_up.append((wind, seed, fb, ff, rb, rf))
        print("  %-4s | %2d -> %-2d %-6s | %2d -> %-2d %-6s | %d -> %d%s"
              % (seed, rb, rf, "(%+d)" % (rf - rb) if rf != rb else "",
                 db, df, "(%+d)" % (df - db) if df != db else "",
                 fb, ff, mark))
    print("  -----+----------------+----------------+---------------")
    print("  TOT  | %2d -> %-2d %-6s | %2d -> %-2d %-6s | %d -> %d (%+d)"
          % (sb[0], sf[0], "(%+d)" % (sf[0] - sb[0]),
             sb[1], sf[1], "(%+d)" % (sf[1] - sb[1]),
             sb[2], sf[2], sf[2] - sb[2]))
    for i in range(3):
        TOT["b"][i] += sb[i]
        TOT["f"][i] += sf[i]

    st = fix.get("stats", {})
    print("  route_blocked fires        : %s" % st.get("route_blocked_fires", 0))
    print("  RECOVERIES (blocked->live) : %s" % st.get("recoveries", 0))
    print("  end-of-run latched units   : %d" % len(fix.get("latched", [])))
    print("  assigns total              : %s" % st.get("assigns", 0))
    print("  OVERCORRECTION assigns into an already-blocked route : %s"
          % st.get("assign_into_blocked_route", 0))
    print("     of which by a unit that had recovered             : %s"
          % st.get("assign_into_blocked_route_after_recovery", 0))
    if fix.get("recoveries"):
        print("  recovery detail:")
        for r in fix["recoveries"]:
            print("     seed %-5s step %3d %-11s -> %-10s at %s"
                  % (r["seed"], r["step"], r["ff"], r["to"], r["pos"]))
    bad = [a for a in fix.get("assigns", []) if not a["reachable_at_assign"]]
    if bad:
        print("  assigns into a blocked route (detail):")
        for a in bad:
            print("     seed %-5s step %3d %-11s -> %-9s %s->%s reason=%s after_recovery=%s"
                  % (a["seed"], a["step"], a["ff"], a["vid"], a["src"],
                     a["target"], a["reason"], a["after_recovery"]))

print("=" * 78)
print("ALL 18 RUNS   rescued %d -> %d (%+d) | victims dead %d -> %d (%+d) | ff_deaths %d -> %d (%+d)"
      % (TOT["b"][0], TOT["f"][0], TOT["f"][0] - TOT["b"][0],
         TOT["b"][1], TOT["f"][1], TOT["f"][1] - TOT["b"][1],
         TOT["b"][2], TOT["f"][2], TOT["f"][2] - TOT["b"][2]))
print()
print("GATE: rescued must not DECREASE on any combo.")
print("  per-seed rescued regressions: %s" % (regressions or "NONE"))
print("GATE: no unit re-dispatched into a still-blocked route.")
print("GATE: ff_deaths increases (report tradeoff, not automatic fail):")
for w, s, fb, ff, rb, rf in ff_up:
    print("  D/%s seed %s: ff_deaths %d -> %d, rescued %d -> %d" % (w, s, fb, ff, rb, rf))
if not ff_up:
    print("  none")
