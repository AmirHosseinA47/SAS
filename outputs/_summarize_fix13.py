"""Compare a matrix prefix against the fix8 and fix12 baselines.

Reads outputs/<prefix>_<scenario>_<wind>.txt for the 16 combos and parses the
per-seed CSV block (authoritative; the human-readable block above it is
redundant). Reports:

  1. Headline totals, with the non-terminal count carried alongside them,
     because never_detected is only expressible on a run that reaches a
     terminal state.
  2. never_detected PER VICTIM ID.
  3. Genuine changes vs classification artifacts. A never_detected mark is an
     ARTIFACT when that run's all_terminal flag differs between the two trees:
     a run that newly terminates can express marks the comparison tree never
     had the chance to express, and vice versa. Raw totals are therefore not
     comparable across trees with different termination rates; the
     like-for-like total restricted to runs terminal in BOTH trees is.
  4. Seed-trading signature: whether misses were eliminated, or relocated to a
     different seed of the same victim / a different victim of the same run.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCENARIOS = ("A", "B", "C", "D")
WINDS = ("north", "south", "east", "west")
HEADER = "seed,rescued,dead,"


def parse(prefix: str) -> dict:
    """-> {(scenario, wind, seed): row}"""
    runs: dict = {}
    for s in SCENARIOS:
        for w in WINDS:
            path = os.path.join(ROOT, "outputs", "%s_%s_%s.txt" % (prefix, s, w))
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
            cols = None
            for line in lines:
                if line.startswith(HEADER):
                    cols = line.split(",")
                    continue
                if cols is None or not line or not line[0].isdigit():
                    continue
                parts = line.split(",")
                if len(parts) < len(cols) - 1:
                    continue
                rec = dict(zip(cols, parts))
                nd_victims = set()
                for tok in (parts[len(cols) - 1] if len(parts) >= len(cols) else "").split(";"):
                    tok = tok.strip()
                    if ":" in tok and tok.split(":", 1)[1] == "never_detected":
                        nd_victims.add(tok.split(":", 1)[0])
                runs[(s, w, int(rec["seed"]))] = dict(
                    scenario=s,
                    wind=w,
                    seed=int(rec["seed"]),
                    rescued=int(rec["rescued"]),
                    dead=int(rec["dead"]),
                    nd=int(rec["never_detected"]),
                    ff_deaths=int(rec["firefighter_deaths"]),
                    candidate=int(rec["candidate"]),
                    total_victims=int(rec["total_victims"]),
                    all_terminal=rec["all_terminal"].strip() == "True",
                    terminal_step=rec.get("terminal_step", "").strip(),
                    nd_victims=nd_victims,
                )
    return runs


def totals(runs: dict) -> dict:
    return dict(
        n_runs=len(runs),
        nd=sum(r["nd"] for r in runs.values()),
        rescued=sum(r["rescued"] for r in runs.values()),
        dead=sum(r["dead"] for r in runs.values()),
        ff_deaths=sum(r["ff_deaths"] for r in runs.values()),
        non_terminal=sum(1 for r in runs.values() if not r["all_terminal"]),
    )


def victim_map(runs: dict) -> dict:
    """-> {(scenario, wind, victim_id): set(seeds)}"""
    out: dict = {}
    for (s, w, sd), r in runs.items():
        for v in r["nd_victims"]:
            out.setdefault((s, w, v), set()).add(sd)
    return out


def fmt_combo(s: str, w: str) -> str:
    return "%s/%s" % (s, w)


def compare(new: dict, base: dict, new_name: str, base_name: str, log) -> None:
    log("")
    log("=" * 78)
    log("%s  vs  %s" % (new_name.upper(), base_name.upper()))
    log("=" * 78)

    tn, tb = totals(new), totals(base)
    log("")
    log("%-18s %10s %10s %9s" % ("metric", base_name, new_name, "delta"))
    log("-" * 50)
    for key, label, better_low in (
        ("nd", "never_detected", True),
        ("rescued", "rescued", False),
        ("dead", "dead", True),
        ("ff_deaths", "ff_deaths", True),
        ("non_terminal", "non-terminal", True),
    ):
        d = tn[key] - tb[key]
        arrow = ""
        if d != 0:
            good = (d < 0) if better_low else (d > 0)
            arrow = "  better" if good else "  WORSE"
        log("%-18s %10s %10s %+9d%s" % (label, tb[key], tn[key], d, arrow))
    log("%-18s %10d %10d" % ("runs parsed", tb["n_runs"], tn["n_runs"]))

    common = sorted(set(new) & set(base))

    def term_changed(k) -> bool:
        """Terminal status = the all_terminal flag AND the step it terminated on.

        A run that terminates later leaves the never_detected timeout more time
        to fire, so a step shift manufactures marks just as a False->True flip
        does. This is the rule that reproduces the fix12-vs-fix8 split of 4
        artifacts out of 11 raw marks.
        """
        return (
            new[k]["all_terminal"] != base[k]["all_terminal"]
            or new[k]["terminal_step"] != base[k]["terminal_step"]
        )

    same_term = [k for k in common if not term_changed(k)]
    diff_term = [k for k in common if term_changed(k)]

    log("")
    log("LIKE-FOR-LIKE (runs with identical terminal status in both trees: %d of %d)"
        % (len(same_term), len(common)))
    ll_new = sum(new[k]["nd"] for k in same_term)
    ll_base = sum(base[k]["nd"] for k in same_term)
    log("  never_detected on those runs: %s %d -> %s %d  (%+d)"
        % (base_name, ll_base, new_name, ll_new, ll_new - ll_base))

    log("")
    log("ARTIFACT SPLIT of %s's %d never_detected marks" % (new_name, tn["nd"]))
    art = [k for k in diff_term if new[k]["nd"] > 0]
    art_marks = sum(new[k]["nd"] for k in art)
    log("  genuine  (terminal status identical to %s): %d" % (base_name, tn["nd"] - art_marks))
    log("  ARTIFACT (terminal status changed):         %d" % art_marks)
    for k in sorted(art):
        log("      %-10s seed=%-5d victims=%-22s all_terminal %s->%s  step %s->%s"
            % (fmt_combo(k[0], k[1]), k[2],
               ",".join(sorted(new[k]["nd_victims"])) or "-",
               base[k]["all_terminal"], new[k]["all_terminal"],
               base[k]["terminal_step"] or "-", new[k]["terminal_step"] or "-"))

    suppressed = [
        k for k in common
        if base[k]["nd"] > 0
        and base[k]["all_terminal"] and not new[k]["all_terminal"]
    ]
    sup_marks = sum(base[k]["nd"] for k in suppressed)
    log("")
    log("SUPPRESSED marks (%s had them; %s's run stopped terminating, so it is" % (base_name, new_name))
    log("not charged for them even though the victim was still not found): %d" % sup_marks)
    for k in sorted(suppressed):
        log("      %-10s seed=%-5d victims=%s"
            % (fmt_combo(k[0], k[1]), k[2], ",".join(sorted(base[k]["nd_victims"])) or "-"))
    log("  => %s comparable total = %d raw + %d suppressed = %d"
        % (new_name, tn["nd"], sup_marks, tn["nd"] + sup_marks))

    vn, vb = victim_map(new), victim_map(base)
    log("")
    log("NEVER_DETECTED PER VICTIM ID")
    log("  %-10s %-9s %-18s %-18s %s"
        % ("combo", "victim", "%s seeds" % base_name, "%s seeds" % new_name, "verdict"))
    traded_seed = []
    for key in sorted(set(vn) | set(vb)):
        s, w, v = key
        B, F = vb.get(key, set()), vn.get(key, set())
        gone, added = sorted(B - F), sorted(F - B)
        if gone and added:
            verdict = "TRADED seeds %s -> %s" % (gone, added)
            traded_seed.append((key, gone, added))
        elif gone and not F:
            verdict = "eliminated"
        elif gone:
            verdict = "reduced"
        elif added and not B:
            verdict = "NEW"
        elif added:
            verdict = "increased"
        else:
            verdict = "unchanged"
        log("  %-10s %-9s %-18s %-18s %s"
            % (fmt_combo(s, w), v,
               ",".join(str(x) for x in sorted(B)) or "-",
               ",".join(str(x) for x in sorted(F)) or "-",
               verdict))

    log("")
    log("SEED-TRADING SIGNATURE")
    log("  (a) same victim, miss moved to a different seed:")
    if traded_seed:
        for key, gone, added in traded_seed:
            log("      %-10s %-9s  %s -> %s" % (fmt_combo(key[0], key[1]), key[2], gone, added))
    else:
        log("      none")
    swaps = []
    for k in common:
        B, F = base[k]["nd_victims"], new[k]["nd_victims"]
        if B and F and B != F and (F - B) and (B - F):
            swaps.append((k, sorted(B), sorted(F)))
    log("  (b) same run, miss moved to a different victim:")
    if swaps:
        for k, B, F in swaps:
            log("      %-10s seed=%-5d %s -> %s" % (fmt_combo(k[0], k[1]), k[2], B, F))
    else:
        log("      none")
    elim = [k for k in sorted(set(vb)) if not vn.get(k)]
    newv = [k for k in sorted(set(vn)) if not vb.get(k)]
    log("  (c) net: %d victim-combos fully eliminated, %d newly appearing"
        % (len(elim), len(newv)))
    for k in elim:
        log("      eliminated: %-10s %s (was seeds %s)"
            % (fmt_combo(k[0], k[1]), k[2], ",".join(str(x) for x in sorted(vb[k]))))
    for k in newv:
        log("      NEW:        %-10s %s (now seeds %s)"
            % (fmt_combo(k[0], k[1]), k[2], ",".join(str(x) for x in sorted(vn[k]))))


def diagnostics(new: dict, base: dict, new_name: str, base_name: str, log) -> None:
    """Why the artifact marks appear, and what they cost.

    The artifact rule exists to avoid over-charging a tree for marks it only got
    the chance to express. It cannot be read as exoneration when the tree itself
    caused the termination change, so the termination shift and the rescue count
    are reported next to it.
    """
    def tstep(r) -> int:
        return int(r["terminal_step"]) if r["terminal_step"] else 240

    log("")
    log("-" * 78)
    log("DIAGNOSTICS: %s vs %s" % (new_name, base_name))
    log("-" * 78)
    vb = [tstep(r) for r in base.values()]
    vn = [tstep(r) for r in new.values()]
    log("")
    log("terminal_step (240 = never terminated):")
    log("  %-6s mean=%6.1f  median=%5.1f  terminating <150: %2d  <100: %2d"
        % (base_name, sum(vb) / len(vb), sorted(vb)[len(vb) // 2],
           sum(1 for x in vb if x < 150), sum(1 for x in vb if x < 100)))
    log("  %-6s mean=%6.1f  median=%5.1f  terminating <150: %2d  <100: %2d"
        % (new_name, sum(vn) / len(vn), sorted(vn)[len(vn) // 2],
           sum(1 for x in vn if x < 150), sum(1 for x in vn if x < 100)))

    common = sorted(set(new) & set(base))
    late = [k for k in common if tstep(new[k]) - tstep(base[k]) >= 30]
    log("")
    log("runs terminating >=30 steps LATER under %s: %d of %d"
        % (new_name, len(late), len(common)))
    for k in sorted(late, key=lambda z: tstep(base[z]) - tstep(new[z])):
        log("     %-10s seed=%-5d %3d -> %3d (%+4d)  rescued %d->%d  nd %d->%d"
            % (fmt_combo(k[0], k[1]), k[2], tstep(base[k]), tstep(new[k]),
               tstep(new[k]) - tstep(base[k]),
               base[k]["rescued"], new[k]["rescued"], base[k]["nd"], new[k]["nd"]))

    log("")
    log("rescued by combo (%s -> %s):" % (base_name, new_name))
    tb = tn = 0
    for s in SCENARIOS:
        for w in WINDS:
            ks = [k for k in common if k[0] == s and k[1] == w]
            a = sum(base[k]["rescued"] for k in ks)
            b = sum(new[k]["rescued"] for k in ks)
            tb += a
            tn += b
            flag = "" if a == b else ("  WORSE" if b < a else "  better")
            log("  %-10s %2d -> %2d  (%+d)%s" % (fmt_combo(s, w), a, b, b - a, flag))
    log("  %-10s %2d -> %2d  (%+d)" % ("TOTAL", tb, tn, tn - tb))

    log("")
    log("SCOPE CHECK - the patch edits only the non-west branch of")
    log("_finalize_coverage_target, so west-wind runs must be unchanged:")
    fields = ("rescued", "dead", "nd", "ff_deaths", "candidate", "all_terminal",
              "terminal_step")
    for w in WINDS:
        ks = [k for k in common if k[1] == w]
        d = sum(1 for k in ks if any(base[k][f] != new[k][f] for f in fields))
        log("  %-6s wind: %2d of %2d runs differ%s"
            % (w, d, len(ks), "   <- expected 0" if w == "west" else ""))


def main() -> int:
    prefix = sys.argv[1] if len(sys.argv) > 1 else "fix13"
    lines: list = []

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lines.append(msg)

    trees = {}
    for name in ("fix8", "fix12", prefix):
        trees[name] = parse(name)
        log("parsed %-6s %d runs" % (name, len(trees[name])))

    missing = [k for k in trees["fix12"] if k not in trees[prefix]]
    if missing:
        log("")
        log("WARNING: %s is INCOMPLETE - %d runs missing. Numbers below are partial."
            % (prefix, len(missing)))

    for base in ("fix8", "fix12"):
        compare(trees[prefix], trees[base], prefix, base, log)
        diagnostics(trees[prefix], trees[base], prefix, base, log)

    out = os.path.join(ROOT, "outputs", "%s_report.txt" % prefix)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    log("")
    log("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
