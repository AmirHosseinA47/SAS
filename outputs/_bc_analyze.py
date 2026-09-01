"""Defect #9 Part 2: aggregate the 13 instrumented runs. Read-only."""
from __future__ import annotations
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ORDER = [("east_half", "D/east  half"), ("south_half", "D/south half"),
         ("east_def", "D/east  def ")]
SNAPS = ("60", "120", "180", "240")
LOOKBACK = 10


def load():
    runs = []
    for tag, _ in ORDER:
        for p in sorted(glob.glob("outputs/_bc_%s_*.json" % tag)):
            d = json.load(open(p, encoding="utf-8"))
            d["_tag"] = tag
            runs.append(d)
    return runs


def main():
    runs = load()
    out = io.open("outputs/_bc_analysis.txt", "w", encoding="utf-8")

    def w(s=""):
        out.write(s + "\n")
        print(s)

    w("RUNS LOADED: %d" % len(runs))
    w()
    w("1. GRID BURN STATE OVER TIME  (50x50 = 2500 cells)")
    w("-" * 78)
    w("%-14s %5s | %-27s | %-27s" % ("combo", "seed",
                                     "burnt @60/120/180/240",
                                     "scorched(has_burned,!burnt)"))
    tot_b = {s: 0 for s in SNAPS}
    tot_s = {s: 0 for s in SNAPS}
    tot_f = {s: 0 for s in SNAPS}
    n_snap = 0
    for r in runs:
        sn = r["snapshots"]
        b = "/".join(str(sn.get(s, {}).get("burnt", "-")).rjust(4) for s in SNAPS)
        sc = "/".join(str(sn.get(s, {}).get("scorched", "-")).rjust(4) for s in SNAPS)
        lbl = dict(ORDER)[r["_tag"]]
        w("%-14s %5d | %s | %s" % (lbl, r["seed"], b, sc))
        if all(s in sn for s in SNAPS):
            n_snap += 1
            for s in SNAPS:
                tot_b[s] += sn[s]["burnt"]
                tot_s[s] += sn[s]["scorched"]
                tot_f[s] += sn[s]["burning"]
    if n_snap:
        w()
        w("MEAN over %d runs, as %% of the 2500-cell grid:" % n_snap)
        w("  step        %s" % "  ".join(s.rjust(6) for s in SNAPS))
        w("  burnt       %s" % "  ".join(
            ("%.1f%%" % (100.0 * tot_b[s] / n_snap / 2500)).rjust(6) for s in SNAPS))
        w("  scorched    %s" % "  ".join(
            ("%.1f%%" % (100.0 * tot_s[s] / n_snap / 2500)).rjust(6) for s in SNAPS))
        w("  burning     %s" % "  ".join(
            ("%.1f%%" % (100.0 * tot_f[s] / n_snap / 2500)).rjust(6) for s in SNAPS))
        w()
        w("  ratio scorched:burnt  %s" % "  ".join(
            ("%.2f" % (tot_s[s] / max(tot_b[s], 1))).rjust(6) for s in SNAPS))
        w("  (cells that RENDER charred but still hold fuel and can re-ignite,")
        w("   per genuinely burnt cell - main.py:77 / serve_dashboard.py:63)")

    w()
    w("2. FIREFIGHTER CONTACT WITH BURNT GROUND")
    w("-" * 78)
    st = sb = ss = mt = mb = av = tk = 0
    for r in runs:
        f = r["ff"]
        st += f["stand_total"]; sb += f["stand_burnt"]; ss += f["stand_scorched"]
        mt += f["moves_total"]; mb += f["move_onto_burnt"]
        av += f["burnt_nb_available"]; tk += f["burnt_nb_taken"]
    w("  firefighter-steps alive, total ................. %6d" % st)
    w("    of which standing on a BURNT cell ............ %6d  (%.2f%%)"
      % (sb, 100.0 * sb / max(st, 1)))
    w("    of which standing on a SCORCHED cell ......... %6d  (%.2f%%)"
      % (ss, 100.0 * ss / max(st, 1)))
    w("  moves executed ................................. %6d" % mt)
    w("    of which onto a BURNT cell ................... %6d  (%.2f%%)"
      % (mb, 100.0 * mb / max(mt, 1)))
    w("  steps where a safe BURNT neighbour existed ..... %6d  (%.2f%% of steps)"
      % (av, 100.0 * av / max(st, 1)))
    w("    and the unit moved onto it ................... %6d" % tk)

    w()
    w("3. UAV OBSERVATION EFFORT")
    w("-" * 78)
    ot = ob = osc = obn = 0
    for r in runs:
        u = r["uav"]
        ot += u["obs_total"]; ob += u["obs_burnt"]
        osc += u.get("obs_scorched", 0); obn += u["obs_burning"]
    w("  cell-observations (UAV x cell x step, radius 8) . %8d" % ot)
    w("    on BURNT ground ............................... %8d  (%.2f%%)"
      % (ob, 100.0 * ob / max(ot, 1)))
    w("    on SCORCHED ground ............................ %8d  (%.2f%%)"
      % (osc, 100.0 * osc / max(ot, 1)))
    w("    on ACTIVELY BURNING ground .................... %8d  (%.2f%%)"
      % (obn, 100.0 * obn / max(ot, 1)))
    w("    on unburnt/green ground ....................... %8d  (%.2f%%)"
      % (ot - ob - osc - obn, 100.0 * (ot - ob - osc - obn) / max(ot, 1)))

    w()
    w("4. FIREFIGHTER DEATHS - WAS BURNT GROUND AVAILABLE AS AN ESCAPE?")
    w("-" * 78)
    deaths = []
    for r in runs:
        for d in r["deaths"]:
            deaths.append((r, d))
    w("  total firefighter deaths across the %d runs: %d" % (len(runs), len(deaths)))
    w()
    if deaths:
        w("  %-14s %5s %-6s %5s %-11s | burnt nb in last %d steps"
          % ("combo", "seed", "unit", "step", "died on", LOOKBACK))
        any_burnt = 0
        any_scorched = 0
        for r, d in deaths:
            trace = r["ff_trace"].get(d["unit"], [])
            dstep = d["step"]
            window = [t for t in trace if dstep - LOOKBACK <= t["step"] < dstep]
            nb_burnt = sum(1 for t in window
                           for n in t["nb"] if n["burnt"] and not n["burning"])
            nb_scor = sum(1 for t in window
                          for n in t["nb"] if n.get("scorched") and not n["burning"])
            steps_with = sum(1 for t in window
                             if any(n["burnt"] and not n["burning"] for n in t["nb"]))
            if steps_with:
                any_burnt += 1
            if nb_scor:
                any_scorched += 1
            died_on = "burnt" if d.get("cell_was_burnt") else (
                "scorched" if d.get("cell_was_scorched") else "burning/green")
            w("  %-14s %5d %-6s %5d %-11s | %d burnt-nb over %d step(s); scorched-nb %d"
              % (dict(ORDER)[r["_tag"]], r["seed"], d["unit"][:6], dstep,
                 died_on, nb_burnt, steps_with, nb_scor))
        w()
        w("  deaths with >=1 safe BURNT neighbour in the %d steps before death: %d / %d"
          % (LOOKBACK, any_burnt, len(deaths)))
        w("  deaths with >=1 SCORCHED neighbour in that window ..............: %d / %d"
          % (any_scorched, len(deaths)))

    w()
    w("5. RUN OUTCOMES (cross-check against evaluate_scenarios)")
    w("-" * 78)
    w("  %-14s %5s %8s %7s %8s %9s" % ("combo", "seed", "ff_deaths",
                                       "rescued", "burnt", "terminal"))
    tot_d = 0
    for r in runs:
        e = r["eval"]
        tot_d += e["firefighter_deaths"]
        w("  %-14s %5d %8d %7d %8d %9s"
          % (dict(ORDER)[r["_tag"]], r["seed"], e["firefighter_deaths"],
             e["rescued"], e["burnt_cells"], e["terminal_step"]))
    w("  %-14s %5s %8d" % ("TOTAL", "", tot_d))
    out.close()


if __name__ == "__main__":
    main()
