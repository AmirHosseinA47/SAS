"""Fire mechanic round 1, Part 3 analysis (outputs/firemech_part1.txt section 7.3). Read-only.

usage:
  _firemech_analyze.py --sample canonical|fresh|both|rb18 [--arms fmOFF,fmEFS,...] [--out FILE]

Every number below is derived from the harness JSON exactly - the feature's own
per-advance log (firefight_log), the per-step fire digests, burn_intervals and
ff_steps - never inferred from snapshots of something else.

Definitions
  identity         deep equality of every JSON field except the listed ones
  ever_burned      fire_ground_final cells with has_burned        (end of run)
  cleared          fire_cleared_unburned_final: fuel 0, never burned (0 when absent -
                   only a firebreak can produce such a cell)
  intact           cells - ever_burned - cleared                  (net fire effect)
  first write      first firefight_log row with wrote True (DRY rows never write)
  attribution      a WET arm's first fire-digest divergence from fmOFF must be
                   exactly its first write step; a DRY arm must match 240/240
  engaged          a log row whose plan was not None (the unit worked or approached,
                   or its retreat fired on a step it had a plan)
  S-hold           a work/move row with fire distance <= IDLE_RETREAT_SAFETY_BUFFER (3):
                   a step the idle buffer alone would have spent retreating
  exit-guard trip  a row with suppression configured (K < 3), fire within 3, guard False
  preemption       an ok assign landing on a unit whose latest row (this step, or the
                   previous step with no row this step) was engaged
  exposed clear    a cleared never-burned cell some cell within euclidean 3 of which
                   burned at a LATER step (so it would have had a nonzero ignition chance)
  cycle            >= 8 consecutive per-step rows of one unit with no write and whose
                   post-advance positions cover <= 4 distinct cells (maximal runs)
  alternation      move -> retreat -> move on three consecutive steps of one unit
  death engaged    the unit's log row ON its death step is engaged (its advance on that
                   step was firefighting); the casualty check runs after every advance
  E1 / E2          drone steps on a burning cell, computed by _dcd4_analyze.summarize:
                   E1 searcher-only (interior-hazard definition), E2 all-UAV
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _dcd4_analyze as AN  # noqa: E402

CELLS = 2500
STEPS = 240
BUFFER = 3

CANONICAL = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
RB18 = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
        + [("east", "half", s) for s in (606, 707, 808, 909)]
        + [("east", "half", s) for s in (111, 222, 333, 444)]
        + [("south", "half", s) for s in (101, 202, 303, 404, 505)])

ALL_ARMS = ["fmREF", "fmOFF", "fmF", "fmFS", "fmES", "fmEFS", "fmDRY"]
IDENTITY_ARMS = [("fmS", "fmOFF"), ("fmE", "fmOFF"), ("fmEF", "fmF")]
WORK = ("extinguish", "clear")

OUT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def label(t):
    return "%s/%s/%d" % (t[0], "def" if t[1] == "default" else t[1], t[2])


def path(tag, t):
    rr = "def" if t[1] == "default" else t[1]
    return os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], rr, t[2]))


_CACHE = {}


def load(tag, t):
    key = (tag,) + tuple(t)
    if key not in _CACHE:
        p = path(tag, t)
        d = None
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        _CACHE[key] = d
    return _CACHE[key]


def drop(tag):
    for k in [k for k in _CACHE if k[0] == tag]:
        del _CACHE[k]


def diff_keys(a, b, exclude):
    keys = (set(a) | set(b)) - set(exclude)
    return sorted(k for k in keys if a.get(k, "<absent>") != b.get(k, "<absent>"))


# ------------------------------------------------------------------ identity ---
def identity_block(sample_name, tuples, new, old, exclude, why):
    same, missing, rows = 0, 0, []
    for t in tuples:
        a, b = load(new, t), load(old, t)
        if a is None or b is None:
            missing += 1
            rows.append("    %-16s MISSING %s" % (label(t), new if a is None else old))
            continue
        dk = diff_keys(a, b, exclude)
        if not dk:
            same += 1
        else:
            rows.append("    %-16s DIFFERS in %s" % (label(t), ", ".join(dk)))
    n = len(tuples) - missing
    verdict = "PASS" if same == n and missing == 0 else "FAIL"
    say("  %-6s == %-6s  %s  %d/%d identical%s   (%s; excluded: %s)" % (
        new, old, verdict, same, n, (", %d missing" % missing) if missing else "", why,
        ", ".join(sorted(exclude))))
    for r in rows:
        say(r)
    return verdict


# ------------------------------------------------------------------ per run ----
def burning_at(bi, cell, step):
    for a, b in bi.get("%d,%d" % cell) or ():
        if a <= step and (b is None or step < b):
            return True
    return False


def burned_later(bi, cell, step):
    """Some cell within euclidean 3 of `cell` burning at any step > `step`."""
    x, y = cell
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx * dx + dy * dy > 9:
                continue
            for a, b in bi.get("%d,%d" % (x + dx, y + dy)) or ():
                end = STEPS + 1 if b is None else b
                if max(a, step + 1) < end:
                    return True
    return False


def run_summary(d, off):
    ev = d["eval"]
    S = {
        "rescued": int(ev.get("rescued") or 0), "dead": int(ev.get("dead") or 0),
        "ffd": int(ev.get("firefighter_deaths") or 0), "nd": int(ev.get("never_detected") or 0),
        "unreach": int(ev.get("unreachable") or 0), "burnt": int(ev.get("burnt_cells") or 0),
        "terminal": ev.get("terminal_step"), "wall": float(d.get("wall_s") or 0.0),
    }
    fgf = d.get("fire_ground_final") or {}
    S["ever"] = sum(1 for v in fgf.values() if v[0])
    S["burning240"] = sum(1 for v in fgf.values() if v[2])
    S["cleared"] = int(d.get("fire_cleared_unburned_final") or 0)
    S["intact"] = CELLS - S["ever"] - S["cleared"]
    log = d.get("firefight_log") or []
    bi = d.get("burn_intervals") or {}
    term = S["terminal"]

    writes = [r for r in log if r.get("wrote")]
    S["first_write"] = min((r["step"] for r in writes), default=None)
    S["ext"] = sum(1 for r in writes if r["action"] == "extinguish")
    clears = [r for r in writes if r["action"] == "clear"]
    S["clear"] = len(clears)
    S["clear_scorched"] = sum(1 for r in clears if r.get("scorched"))
    S["exposed"] = sum(1 for r in clears
                       if not r.get("scorched") and burned_later(bi, tuple(r["target"]), r["step"]))
    S["dry"] = sum(1 for r in log if r.get("dry") and r["action"] in WORK)
    S["rows"] = len(log)
    S["engaged"] = sum(1 for r in log if r.get("engaged"))
    S["moves"] = sum(1 for r in log if r["action"] == "move")
    S["none"] = sum(1 for r in log if r["action"] == "none")
    S["none_band"] = sum(1 for r in log if r["action"] == "none" and (r.get("band") or 0) > 0)
    S["blocked"] = sum(1 for r in log if r["action"] == "none" and r.get("blocked_target") is not None)
    S["lookahead_rej"] = sum(int(r.get("lookahead_rejected") or 0) for r in log)
    S["retreat"] = sum(1 for r in log if r["action"] == "retreat")
    S["retreat_plan"] = sum(1 for r in log if r["action"] == "retreat" and r.get("engaged"))
    S["suspend_set"] = sum(1 for r in log if r.get("suspend_set"))
    S["s_hold"] = sum(1 for r in log if r["action"] in WORK + ("move",) and r["dist"] <= BUFFER)
    S["suspended"] = sum(1 for r in log if r.get("suspended"))
    S["exit_trip"] = sum(1 for r in log
                         if r.get("K", BUFFER) < BUFFER and r["dist"] <= BUFFER and not r.get("exit_guard"))
    S["after_term"] = sum(1 for r in log if r.get("engaged") and term is not None and r["step"] > term)

    by_ff = collections.defaultdict(dict)
    for r in log:
        by_ff[r["ff"]][r["step"]] = r
    pre = 0
    for a in d.get("assigns") or []:
        if not a.get("ok"):
            continue
        rows = by_ff.get(a["ff"], {})
        now, prev = rows.get(a["step"]), rows.get(a["step"] - 1)
        if (now is not None and now.get("engaged")) or (now is None and prev is not None and prev.get("engaged")):
            pre += 1
    S["preempt"] = pre

    # positions after each advance, per unit
    pos = collections.defaultdict(dict)
    for i, row in enumerate(d.get("ff_steps") or []):
        for ff, p, st, asg, ex, dead in row:
            pos[ff][i + 1] = (tuple(p) if p is not None else None, st, asg, ex, dead)

    cycles, alts = [], 0
    for ff, rows in by_ff.items():
        steps = sorted(rows)
        run = []
        for s in steps + [None]:
            r = rows.get(s) if s is not None else None
            ok = (r is not None and not r.get("wrote") and not (r.get("dry") and r["action"] in WORK)
                  and (not run or s == run[-1] + 1))
            if ok:
                run.append(s)
                continue
            if len(run) >= 8:
                cells = {pos[ff].get(k, (None,))[0] for k in run}
                if len(cells) <= 4:
                    cycles.append((ff, run[0], run[-1], len(cells)))
            run = [s] if (r is not None and not r.get("wrote")
                          and not (r.get("dry") and r["action"] in WORK)) else []
        for s in steps:
            a, b, c = rows.get(s), rows.get(s + 1), rows.get(s + 2)
            if a and b and c and (a["action"], b["action"], c["action"]) == ("move", "retreat", "move"):
                alts += 1
    S["cycles"] = cycles
    S["alts"] = alts

    deaths = []
    for ff, steps in pos.items():
        dead_steps = [s for s in sorted(steps) if steps[s][4]]
        if not dead_steps:
            continue
        s = dead_steps[0]
        cell = steps[s][0]
        prev = steps.get(s - 1)
        r = by_ff.get(ff, {}).get(s)
        nb_burn = nb_all = 0
        if cell is not None:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cell[0] + ox, cell[1] + oy)
                if 0 <= n[0] < 50 and 0 <= n[1] < 50:
                    nb_all += 1
                    nb_burn += int(burning_at(bi, n, s))
        prev_r = by_ff.get(ff, {}).get(s - 1)
        deaths.append({
            "ff": ff, "step": s, "cell": cell,
            "engaged": bool(r and r.get("engaged")),
            # a unit can only die on a cell that is ALREADY burning when its advance
            # runs, so its death-step row is recomputed on that burning cell; the
            # previous row is its last decision before the fatal fire tick
            "engaged_prev": bool(prev_r and prev_r.get("engaged")),
            "row": r["action"] if r else None,
            "prev_row": prev_r.get("action") if prev_r else None,
            "T": r["T"] if r else None, "dist": r["dist"] if r else None,
            "nb": "%d/%d" % (nb_burn, nb_all),
            # full enclosure: every in-bounds 4-neighbour burning at the death step;
            # otherwise a non-burning neighbour existed and the unchanged retreat
            # routine did not take it (leash edge, stall, or a same-tick spread)
            "enclosure": "full" if nb_all and nb_burn == nb_all else "free-exit",
            "assigned_before": bool(prev and prev[2]),
            "status_before": prev[1] if prev else None,
            "after_terminal": term is not None and s > term,
        })
    S["deaths"] = deaths

    if off is not None:
        fa, fb = d.get("fire_digests") or [], off.get("fire_digests") or []
        div = next((i + 1 for i, (x, y) in enumerate(zip(fa, fb)) if x != y), None)
        if div is None and len(fa) != len(fb):
            div = min(len(fa), len(fb)) + 1
        S["fire_div"] = div
    else:
        S["fire_div"] = None

    E = AN.summarize(d, "fm")
    for k in ("e1n", "e1d", "e2n", "e2d"):
        S[k] = E[k]
    return S


# ------------------------------------------------------------------ report ----
def pooled(runs, key):
    return sum(r[key] for r in runs)


def sample_report(name, tuples, arms):
    say("")
    say("=" * 100)
    say("SAMPLE %s (%d runs)" % (name, len(tuples)))
    say("=" * 100)
    summaries = {}
    for tag in arms:
        rows = []
        for t in tuples:
            d = load(tag, t)
            if d is None:
                continue
            off = load("fmOFF", t) if tag != "fmOFF" else None
            rows.append((t, run_summary(d, off)))
        summaries[tag] = rows
    present = {tag: len(rows) for tag, rows in summaries.items()}
    say("runs present: " + "  ".join("%s %d/%d" % (k, v, len(tuples)) for k, v in present.items()))

    def dedup(rows):
        return [(t, s) for t, s in rows if t[1] != "default"]

    for title, pick in (("counted", lambda r: r), ("de-duplicated fire worlds, east/def excluded", dedup)):
        say("")
        say("OUTCOMES (%s)" % title)
        say("  %-6s %4s %7s %5s %8s %6s %5s %7s %9s" % (
            "arm", "runs", "rescued", "dead", "ff_death", "nevdet", "unrch", "nonterm", "mean_term"))
        for tag in arms:
            rr = [s for _t, s in pick(summaries[tag])]
            if not rr:
                continue
            terms = [s["terminal"] for s in rr if s["terminal"] is not None]
            say("  %-6s %4d %7d %5d %8d %6d %5d %7d %9s" % (
                tag, len(rr), pooled(rr, "rescued"), pooled(rr, "dead"), pooled(rr, "ffd"),
                pooled(rr, "nd"), pooled(rr, "unreach"), sum(1 for s in rr if s["terminal"] is None),
                ("%.1f" % (sum(terms) / len(terms))) if terms else "-"))
        say("")
        say("FIRE END STATE (%s)   intact = %d - ever_burned - cleared" % (title, CELLS))
        say("  %-6s %4s %7s %7s %7s %7s %11s   vs fmOFF: burnt / ever / intact" % (
            "arm", "runs", "burnt", "ever", "cleared", "intact", "burning@240"))
        base = {t: s for t, s in pick(summaries.get("fmOFF", []))}
        for tag in arms:
            rows = pick(summaries[tag])
            rr = [s for _t, s in rows]
            if not rr:
                continue
            delta = ""
            if tag != "fmOFF" and base:
                paired = [(s, base[t]) for t, s in rows if t in base]
                if paired:
                    delta = "%+d / %+d / %+d  (paired %d)" % (
                        sum(a["burnt"] - b["burnt"] for a, b in paired),
                        sum(a["ever"] - b["ever"] for a, b in paired),
                        sum(a["intact"] - b["intact"] for a, b in paired), len(paired))
            say("  %-6s %4d %7d %7d %7d %7d %11d   %s" % (
                tag, len(rr), pooled(rr, "burnt"), pooled(rr, "ever"), pooled(rr, "cleared"),
                pooled(rr, "intact"), pooled(rr, "burning240"), delta))

    say("")
    say("FIRE DIGEST ATTRIBUTION vs fmOFF, per run")
    say("  %-6s %s" % ("arm", "identical 240/240 | first divergence == first write | VIOLATIONS"))
    for tag in arms:
        if tag in ("fmOFF",):
            continue
        ident = exact = 0
        viol = []
        for t, s in summaries[tag]:
            if load("fmOFF", t) is None:
                continue
            if s["fire_div"] is None:
                ident += 1
                if s["first_write"] is not None:
                    viol.append("%s wrote at %s but fire identical" % (label(t), s["first_write"]))
            elif s["first_write"] is not None and s["fire_div"] == s["first_write"]:
                exact += 1
            else:
                viol.append("%s diverges at %s, first write %s" % (label(t), s["fire_div"], s["first_write"]))
        say("  %-6s identical %2d | exact %2d | violations %d%s" % (
            tag, ident, exact, len(viol), (": " + "; ".join(viol)) if viol else ""))

    say("")
    say("MECHANISM (pooled rows of the feature's own log)")
    cols = ("ext", "clear", "clear_scorched", "exposed", "dry", "engaged", "moves", "none", "blocked",
            "lookahead_rej",
            "retreat", "retreat_plan", "suspend_set", "s_hold", "suspended", "exit_trip", "preempt",
            "after_term", "alts")
    say("  %-6s " % "arm" + " ".join("%9s" % c[:9] for c in cols) + " %6s" % "cycles")
    for tag in arms:
        rr = [s for _t, s in summaries[tag]]
        if not rr:
            continue
        say("  %-6s " % tag + " ".join("%9d" % pooled(rr, c) for c in cols)
            + " %6d" % sum(len(s["cycles"]) for s in rr))
    for tag in arms:
        cyc = [(label(t),) + c for t, s in summaries[tag] for c in s["cycles"]]
        if cyc:
            say("  %s cycles: %s" % (tag, "; ".join("%s %s steps %d-%d on %d cells" % c for c in cyc)))

    say("")
    say("DRONE STEPS ON A BURNING CELL   E1 searcher-only (interior-hazard) | E2 all-UAV")
    for tag in arms:
        rr = [s for _t, s in summaries[tag]]
        if not rr:
            continue
        say("  %-6s E1 %-22s E2 %s" % (tag, AN.pct(pooled(rr, "e1n"), pooled(rr, "e1d")),
                                        AN.pct(pooled(rr, "e2n"), pooled(rr, "e2d"))))

    say("")
    say("FIREFIGHTER DEATHS   engaged = the unit's advance ON its death step had a firefighting plan;")
    say("  engaged_prev = its advance on the step BEFORE did (its last decision before the fatal tick);")
    say("  firefighting-related = either. A unit with no row on both steps was not eligible (e.g. on a rescue).")
    for tag in arms:
        dd = [(label(t), x) for t, s in summaries[tag] for x in s["deaths"]]
        say("  %-6s deaths %d  engaged-at-death %d  engaged-prev %d  firefighting-related %d  after-terminal %d  "
            "full-enclosure %d  free-exit %d" % (
                tag, len(dd), sum(1 for _l, x in dd if x["engaged"]), sum(1 for _l, x in dd if x["engaged_prev"]),
                sum(1 for _l, x in dd if x["engaged"] or x["engaged_prev"]),
                sum(1 for _l, x in dd if x["after_terminal"]),
                sum(1 for _l, x in dd if x["enclosure"] == "full"),
                sum(1 for _l, x in dd if x["enclosure"] != "full")))
        for lab, x in dd:
            say("      %-15s %s step %3d cell %-9s engaged %-5s prev_engaged %-5s row %-10s prev %-10s T %-4s "
                "dist %-4s burning-nbrs %s (%s)  before: %s assigned %s  after_terminal %s" % (
                    lab, x["ff"], x["step"], AN.fmt_cell(x["cell"]), x["engaged"], x["engaged_prev"], x["row"],
                    x["prev_row"], x["T"], x["dist"], x["nb"], x["enclosure"], x["status_before"],
                    x["assigned_before"], x["after_terminal"]))

    say("")
    say("WALL TIME (mean s per run)  " + "  ".join(
        "%s %.0f" % (tag, sum(s["wall"] for _t, s in summaries[tag]) / len(summaries[tag]))
        for tag in arms if summaries[tag]))

    say("")
    say("PER RUN   r/d/ff  b=burnt e=ever c=cleared i=intact | w=writes ext/clear @first write")
    for t in tuples:
        parts = []
        for tag in arms:
            s = dict(summaries[tag]).get(t)
            if s is None:
                parts.append("%s -" % tag)
                continue
            parts.append("%s %d/%d/%d b%d e%d c%d i%d w%d/%d@%s" % (
                tag, s["rescued"], s["dead"], s["ffd"], s["burnt"], s["ever"], s["cleared"], s["intact"],
                s["ext"], s["clear"], s["first_write"]))
        say("  %-15s %s" % (label(t), " | ".join(parts)))
    return summaries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="canonical", choices=["canonical", "fresh", "both", "rb18"])
    ap.add_argument("--arms", default=",".join(ALL_ARMS))
    ap.add_argument("--no-identity", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    arms = [x for x in a.arms.split(",") if x]
    samples = {"canonical": [("canonical 13", CANONICAL)], "fresh": [("fresh 10", FRESH)],
               "both": [("canonical 13", CANONICAL), ("fresh 10", FRESH), ("canonical+fresh 23", CANONICAL + FRESH)],
               "rb18": [("rbgate 18", RB18)]}[a.sample]

    if not a.no_identity:
        say("KILL SWITCH AND IDENTITY ARMS")
        tuples = CANONICAL + FRESH if a.sample in ("both", "fresh") else (RB18 if a.sample == "rb18" else CANONICAL)
        base_ex = ("tag", "repo", "wall_s")
        identity_block("kill switch", tuples, "fmOFF", "fmREF", base_ex, "this branch, no --set vs 6adeb4f, same harness")
        identity_block("ref vs dfD", tuples if a.sample != "rb18" else [], "fmREF", "dfD" if a.sample != "rb18" else "drhD",
                       base_ex + ("params", "extra_params"),
                       "6adeb4f no --set vs the flip round's explicit --set dcD arm")
        if a.sample in ("canonical", "both"):
            for new, old in IDENTITY_ARMS:
                identity_block("identity", CANONICAL, new, old, base_ex + ("params", "extra_params"),
                               "identity by construction")
    for name, tuples in samples:
        sample_report(name, tuples, [x for x in arms if x != "fmREF"])
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
