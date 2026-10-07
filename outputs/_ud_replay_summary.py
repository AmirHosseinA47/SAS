"""Urgency round, the 22.9 per-death review: summary of the knockout replays (outputs/_ud_replay/).

For each dying unit of _ud_rp_deaths.json (an arm-M / MU firefighter death not present in arm 0):
  - R0 reproduction check: the replay's rows / commands / eval / stdout equal the committed record;
  - for each knockout (KO-OWN, KO-LAST, KO-OTHERS): the knockouts actually applied (step, unit, kind, the cell the
    fix would have taken), the first row difference from R0, and the unit's fate: alive at its original death step
    or not, its death step in the replay (None = survives the run), and the run's firefighter deaths, rescued and
    detected-victim deaths.
usage: _ud_replay_summary.py [--json <out>]
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RD = os.path.join(HERE, "_ud_replay")


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def ff_death(d, unit):
    for t, row in enumerate(d["rows_ff"]):
        for r in row:
            if r[0] == unit and r[6]:
                return t + 1
    return None


def first_diff(a, b):
    for t in range(min(len(a["rows_ff"]), len(b["rows_ff"]))):
        if any(a[k][t] != b[k][t] for k in ("rows_ff", "rows_vic", "rows_uav")):
            return t + 1
    return None


def outcome(d):
    ev = d.get("eval") or {}
    ffd = sorted({r[0] for row in d["rows_ff"] for r in row if r[6]})
    return {"rescued": ev.get("rescued"), "dead": ev.get("dead"), "ff_deaths": ev.get("firefighter_deaths"),
            "ff_dead_units": ffd}


def main():
    deaths = load(os.path.join(RD, "_ud_rp_deaths.json"))
    out = []
    for dd in deaths:
        run, unit, t = dd["run"], dd["unit"], dd["death"]
        rec = load(os.path.join(HERE, "_sd_%s.json" % run))
        r0p = os.path.join(RD, "_sd_udrp_%s_R0.json" % run)
        item = {"run": run, "cell": dd["cell"], "arm": dd["arm"], "unit": unit, "death": t, "own_fixes": dd["fixes"],
                "last_fix": dd["last"]}
        if not os.path.exists(r0p):
            item["R0"] = "MISSING"
            out.append(item)
            continue
        r0 = load(r0p)
        same = all(rec[k] == r0[k] for k in ("rows_ff", "rows_vic", "rows_uav", "rows_dec", "rows_trig", "eval"))
        same = same and rec["dp"]["commands"] == r0["dp"]["commands"] and rec["mv_events"] == r0["mv_events"]
        with open(os.path.join(HERE, "_sd_%s.stdout.txt" % run), encoding="utf-8") as fh:
            s_rec = fh.read()
        with open(os.path.join(RD, "_sd_udrp_%s_R0.stdout.txt" % run), encoding="utf-8") as fh:
            s_r0 = fh.read()
        item["R0"] = {"reproduces": bool(same and s_rec == s_r0), "unit_death": ff_death(r0, unit), **outcome(r0)}
        ush = unit.replace("ff_unit_", "f")
        for ko in ("KOown", "KOlast", "KOothers"):
            p = os.path.join(RD, "_sd_udrp_%s_%s_%s.json" % (run, ush, ko))
            bp = os.path.join(RD, "_bd_udrp_%s_%s_%s.json" % (run, ush, ko))
            if not os.path.exists(p):
                item[ko] = None if not dd["fixes"] and ko != "KOothers" else "MISSING"
                continue
            d = load(p)
            bd = load(bp)
            ud = ff_death(d, unit)
            item[ko] = {"applied": bd.get("ko_applied"), "rules": bd.get("ko_rules"),
                        "first_diff_vs_R0": first_diff(r0, d), "unit_death": ud,
                        "alive_at_t": ud is None or ud > t, "errors": (d.get("ud") or {}).get("errors"),
                        **outcome(d)}
        out.append(item)
    for it in out:
        print("=" * 100)
        print("%s %s arm %s: %s dies at %d | own live fixes %s (last %s)" % (
            it["run"], it["cell"], it["arm"], it["unit"], it["death"], it["own_fixes"], it["last_fix"]))
        print("  R0:", it["R0"])
        for ko in ("KOown", "KOlast", "KOothers"):
            v = it.get(ko)
            if isinstance(v, dict):
                print("  %-8s applied %s | first diff vs R0 %s | unit death %s (alive at t: %s) | ff deaths %s %s | "
                      "rescued %s dead %s" % (ko, [(a[0], a[1], a[2]) for a in (v["applied"] or [])][:12],
                                              v["first_diff_vs_R0"], v["unit_death"], v["alive_at_t"],
                                              v["ff_deaths"], v["ff_dead_units"], v["rescued"], v["dead"]))
            else:
                print("  %-8s %s" % (ko, v))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
