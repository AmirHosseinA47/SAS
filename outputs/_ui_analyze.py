"""Part 1 measurement for the route_blocked unassign inflow, at HEAD 62b4fbe.

Answers, per combo and pooled:

  1. how many route_blocked-triggered unassigns occur
  2. of those, how many leave the unit with ZERO legal escape at the moment of
     release  (rel_enclosed: every in-bounds neighbour burning - the same test
     _revalidate_route_blocked_firefighters and the idle-retreat C1 bucket use)
  3. of the zero-escape ones, how many die within N steps vs eventually escape
  4. what the release step itself does to a NON-enclosed unit: _move_toward
     continues after the unassign and moves it, so the release-step landing
     cell is compared against the best free neighbour that was available
  5. latency from release to the unit's first _survival_move, and to its first
     genuinely safe cell
  6. which firefighter deaths trace back to a route_blocked release, and how
     many steps later

usage: _ui_analyze.py "outputs/_ui_p1_*.json" [--within 10]
"""
import argparse, collections, glob, json


def combo_of(d):
    return "%s/%s" % (d["wind"][0].upper(), d["roles"][0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--within", type=int, default=10)
    ap.add_argument("--dump", action="store_true", help="one line per release")
    a = ap.parse_args()

    paths = []
    for f in a.files:
        paths.extend(sorted(glob.glob(f)) or [f])

    releases = []          # every route_blocked-triggered unassign
    all_unassign = collections.Counter()
    rb_fire = collections.Counter()
    deaths_all = []
    combos = []

    for p in paths:
        with open(p) as fh:
            d = json.load(fh)
        combo = combo_of(d)
        combos.append(combo)
        moves = {m["mid"]: m for m in d["moves"]}
        # per (seed, ff_id) step-indexed trace
        tr = collections.defaultdict(dict)
        for r in d["fftrace"]:
            tr[(r["seed"], r["ff_id"])][r["step"]] = r
        last_step = d["steps"]
        surv = collections.defaultdict(list)
        for s in d["surv"]:
            surv[(s["seed"], s["ff"])].append(s["step"])

        for x in d["deaths"]:
            y = dict(x)
            y["combo"] = combo
            deaths_all.append(y)

        for r in d["rb"]:
            rb_fire[(combo, "fired" if r.get("fired") else "already")] += 1

        assigns = collections.defaultdict(list)
        for ev in d["lifecycle"]:
            if ev.get("kind") == "assign" and ev.get("ok"):
                assigns[(ev["seed"], ev["ff_id"], ev.get("victim", ""))].append(ev)

        for ev in d["lifecycle"]:
            if ev.get("kind") != "unassign":
                continue
            all_unassign[(combo, ev.get("reason", ""))] += 1
            if "blocked" not in str(ev.get("reason", "")):
                continue
            if not ev.get("ok"):
                continue
            rec = dict(ev)
            rec["combo"] = combo
            mv = moves.get(ev.get("mid"))
            rec["mv"] = mv
            key = (ev["seed"], ev["ff_id"])
            t = tr[key]
            step = ev["step"]

            # --- outcome after release -------------------------------------
            died_at = None
            for s in range(step, last_step + 1):
                row = t.get(s)
                if row and row.get("dead"):
                    died_at = s
                    break
            rec["died_at"] = died_at
            rec["died_in"] = (died_at - step) if died_at is not None else None
            # first genuinely safe cell after release
            safe_at = None
            for s in range(step, last_step + 1):
                row = t.get(s)
                if row is None or row.get("dead"):
                    break
                if row.get("cell_safe"):
                    safe_at = s
                    break
            rec["safe_at"] = safe_at
            rec["safe_in"] = (safe_at - step) if safe_at is not None else None
            # first step after release where the unit was no longer enclosed
            free_at = None
            for s in range(step, last_step + 1):
                row = t.get(s)
                if row is None or row.get("dead"):
                    break
                if not row.get("enclosed", False):
                    free_at = s
                    break
            rec["free_at"] = free_at
            rec["free_in"] = (free_at - step) if free_at is not None else None
            # first _survival_move at or after the release step
            nxt = [s for s in surv[(ev["seed"], ev["ff"])] if s >= step]
            rec["surv_at"] = min(nxt) if nxt else None
            rec["surv_in"] = (min(nxt) - step) if nxt else None
            rec["alive_at_end"] = (t.get(last_step) or {}).get("dead") is False

            # --- the dispatch that put it here -----------------------------
            cands = [x for x in assigns.get((ev["seed"], ev["ff_id"],
                                             ev.get("victim", "")), [])
                     if x["step"] <= step]
            asg = max(cands, key=lambda x: x["step"]) if cands else None
            rec["asg"] = asg
            rec["transit"] = (step - asg["step"]) if asg else None
            releases.append(rec)

    W = a.within
    print("=" * 78)
    print("PART 1 STEP 3 - route_blocked unassign inflow at HEAD 62b4fbe")
    print("=" * 78)
    print("combos: %s" % ", ".join(combos))
    print()

    # ---- 1. how many -------------------------------------------------------
    by_combo = collections.Counter(r["combo"] for r in releases)
    print("1. ROUTE_BLOCKED-TRIGGERED UNASSIGNS")
    for c in sorted(by_combo):
        print("     %-10s %d" % (c, by_combo[c]))
    print("     %-10s %d" % ("TOTAL", len(releases)))
    print()
    print("   all unassign reasons seen (sanity):")
    for (c, reason), n in sorted(all_unassign.items()):
        print("     %-10s %-32s %d" % (c, reason or "(blank)", n))
    print()
    print("   _mark_route_blocked firings (fired = status flipped):")
    for k, n in sorted(rb_fire.items()):
        print("     %-10s %-10s %d" % (k[0], k[1], n))
    print()

    # ---- 2. enclosure at release ------------------------------------------
    enc = [r for r in releases if r.get("rel_enclosed")]
    notenc = [r for r in releases if not r.get("rel_enclosed")]
    print("2. POSTURE AT THE MOMENT OF RELEASE")
    print("     zero legal escape (every in-bounds neighbour burning) : %d / %d"
          % (len(enc), len(releases)))
    print("     had at least one free neighbour                       : %d / %d"
          % (len(notenc), len(releases)))
    print()
    # NOTE: rescued_victim is set at ASSIGN time, so "carrying_pre" only means
    # "has an assigned victim marker". exiting_pre is the real carrying flag.
    print("     released while EXITING (actually carrying a victim out) : %d"
          % sum(1 for r in releases if r.get("exiting_pre")))
    print("     released while approaching (en_route)                   : %d"
          % sum(1 for r in releases if not r.get("exiting_pre")))
    print()
    print("     breakdown of the released unit's own cell:")
    for label, sub in (("enclosed", enc), ("not enclosed", notenc)):
        if not sub:
            continue
        print("       %-13s on_fire=%d  smoke=%d  adj_fire=%d  cell_safe=%d  "
              "mfd0=%d" % (
                  label,
                  sum(1 for r in sub if r.get("rel_on_fire")),
                  sum(1 for r in sub if r.get("rel_smoke")),
                  sum(1 for r in sub if r.get("rel_adj_fire")),
                  sum(1 for r in sub if r.get("rel_cell_safe")),
                  sum(1 for r in sub if r.get("rel_mfd") == 0)))
    print()

    # ---- 3. fate of the zero-escape releases -------------------------------
    print("3. FATE OF THE ZERO-ESCAPE (ENCLOSED) RELEASES   [N=%d steps]" % W)
    died_w = [r for r in enc if r["died_in"] is not None and r["died_in"] <= W]
    died_l = [r for r in enc if r["died_in"] is not None and r["died_in"] > W]
    lived = [r for r in enc if r["died_in"] is None]
    print("     died within %d steps of release : %d" % (W, len(died_w)))
    if died_w:
        print("        of which died on the release step itself: %d"
              % sum(1 for r in died_w if r["died_in"] == 0))
        print("        died_in distribution: %s"
              % sorted(r["died_in"] for r in died_w))
    print("     died later than %d steps        : %d" % (W, len(died_l)))
    print("     survived to end of run          : %d" % len(lived))
    if lived:
        print("        of which regained a free neighbour, steps later: %s"
              % sorted(r["free_in"] for r in lived if r["free_in"] is not None))
        print("        of which reached a SAFE cell, steps later     : %s"
              % sorted(r["safe_in"] for r in lived if r["safe_in"] is not None))
    print()
    print("   same for the NOT-enclosed releases, for contrast:")
    dw = [r for r in notenc if r["died_in"] is not None and r["died_in"] <= W]
    dl = [r for r in notenc if r["died_in"] is not None and r["died_in"] > W]
    lv = [r for r in notenc if r["died_in"] is None]
    print("     died within %d : %d   died later : %d   survived : %d"
          % (W, len(dw), len(dl), len(lv)))
    if dw:
        print("        died_in distribution: %s" % sorted(r["died_in"] for r in dw))
    print("     reached a SAFE cell, steps after release: %s"
          % sorted(r["safe_in"] for r in notenc if r["safe_in"] is not None))
    print("     never reached a safe cell: %d"
          % sum(1 for r in notenc if r["safe_in"] is None))
    print()

    # ---- 4. what the release step itself does ------------------------------
    print("4. WHAT _move_toward DOES ON THE RELEASE STEP (after the unassign)")
    moved = [r for r in releases if r.get("mv") and r["mv"].get("moved")]
    still = [r for r in releases if r.get("mv") and not r["mv"].get("moved")]
    nomv = [r for r in releases if not r.get("mv")]
    print("     unit MOVED on the release step   : %d" % len(moved))
    print("     unit did NOT move                : %d" % len(still))
    print("     release not inside a _move_toward: %d" % len(nomv))
    if moved:
        worse = [r for r in moved
                 if r["mv"]["post_mfd"] is not None and r.get("rel_mfd") is not None
                 and r["mv"]["post_mfd"] < r["rel_mfd"]]
        same = [r for r in moved
                if r["mv"]["post_mfd"] == r.get("rel_mfd")]
        better = [r for r in moved
                  if r["mv"]["post_mfd"] is not None and r.get("rel_mfd") is not None
                  and r["mv"]["post_mfd"] > r["rel_mfd"]]
        print("       fire distance after that move: worse %d / same %d / better %d"
              % (len(worse), len(same), len(better)))
        subopt = [r for r in moved
                  if r.get("rel_best_free_mfd") is not None
                  and r["mv"]["post_mfd"] is not None
                  and r["mv"]["post_mfd"] < r["rel_best_free_mfd"]]
        print("       landed on a cell WORSE than the best free neighbour that")
        print("       was available at release      : %d / %d" % (len(subopt), len(moved)))
        print("       landed adjacent to fire       : %d"
              % sum(1 for r in moved if r["mv"].get("post_adj_fire")))
        print("       landed ON fire                : %d"
              % sum(1 for r in moved if r["mv"].get("post_on_fire")))
        print("       landed on a genuinely safe cell: %d"
              % sum(1 for r in moved if r["mv"].get("post_safe")))
        print("       a safe neighbour existed at release but was not taken: %d"
              % sum(1 for r in moved
                    if r.get("rel_n_safe", 0) > 0 and not r["mv"].get("post_safe")))
    print()

    # ---- 4b. release taxonomy ---------------------------------------------
    # advance() runs at most one _survival_move per step, and only reaches
    # _move_toward from the immediate-danger branch when that _survival_move
    # FAILED to move the unit. So surv_in == 0 means "the retreat logic
    # already ran this very step, before the release, and found nothing".
    print("4b. RELEASE TAXONOMY  (was the retreat logic already consulted?)")
    tax = collections.Counter()
    tax_rows = collections.defaultdict(list)
    for r in releases:
        danger = bool(r.get("rel_on_fire") or r.get("rel_smoke")
                      or r.get("rel_adj_fire")
                      or (r.get("rel_mfd") is not None and r["rel_mfd"] <= 1))
        pre_surv = (r.get("surv_in") == 0)
        if r.get("rel_enclosed"):
            k = "i   enclosed (no free neighbour at all)"
        elif danger:
            k = "ii  free neighbour, but in immediate danger"
        else:
            k = "iii free neighbour, NOT in immediate danger"
        k += "   [survival_move already ran this step: %s]" % ("YES" if pre_surv else "no")
        tax[k] += 1
        tax_rows[k].append(r)
    for k in sorted(tax):
        print("     %-70s %d" % (k, tax[k]))
    print()
    for k in sorted(tax_rows):
        sub = tax_rows[k]
        died = [r for r in sub if r["died_in"] is not None]
        print("     %s" % k)
        print("        died later                 : %d/%d  (gaps %s)"
              % (len(died), len(sub), sorted(r["died_in"] for r in died)))
        mvd = [r for r in sub if (r.get("mv") or {}).get("moved")]
        print("        moved on the release step  : %d/%d" % (len(mvd), len(sub)))
        if mvd:
            print("           of those, ended closer to fire than they started: %d"
                  % sum(1 for r in mvd
                        if r["mv"]["post_mfd"] is not None
                        and r.get("rel_mfd") is not None
                        and r["mv"]["post_mfd"] < r["rel_mfd"]))
            print("           of those, a strictly better free cell existed and")
            print("           was not taken                                  : %d"
                  % sum(1 for r in mvd
                        if r.get("rel_best_free_mfd") is not None
                        and r["mv"]["post_mfd"] is not None
                        and r["mv"]["post_mfd"] < r["rel_best_free_mfd"]))
    print()

    # ---- 5. latency --------------------------------------------------------
    print("5. LATENCY FROM RELEASE TO RETREAT MACHINERY")
    lat = [r["surv_in"] for r in releases if r["surv_in"] is not None]
    print("     _survival_move ran %d/%d releases; delay distribution: %s"
          % (len(lat), len(releases), collections.Counter(lat).most_common()))
    print("     releases where _survival_move NEVER ran afterwards: %d"
          % sum(1 for r in releases if r["surv_in"] is None))
    print()

    # ---- 6. death attribution ---------------------------------------------
    print("6. FIREFIGHTER DEATHS AND THEIR RELATION TO A route_blocked RELEASE")
    rel_by_unit = collections.defaultdict(list)
    for r in releases:
        rel_by_unit[(r["combo"], r["seed"], r["ff_id"])].append(r["step"])
    print("     total firefighter deaths in sample: %d" % len(deaths_all))
    tied, untied = [], []
    for x in deaths_all:
        prior = [s for s in rel_by_unit.get((x["combo"], x["seed"], x["ff_id"]), [])
                 if s <= x["step"]]
        if prior:
            x["last_release"] = max(prior)
            x["gap"] = x["step"] - max(prior)
            tied.append(x)
        else:
            untied.append(x)
    print("     preceded by a route_blocked release of that same unit: %d"
          % len(tied))
    print("     not preceded by one                                  : %d"
          % len(untied))
    for x in sorted(tied, key=lambda z: (z["combo"], z["seed"], z["step"])):
        print("       %-6s %-4s %-11s died step %3d at %-9s  gap %d steps"
              % (x["combo"], x["seed"], x["ff"], x["step"], x["pos"], x["gap"]))
    for x in sorted(untied, key=lambda z: (z["combo"], z["seed"], z["step"])):
        print("       %-6s %-4s %-11s died step %3d at %-9s  (no release) cat=%s"
              % (x["combo"], x["seed"], x["ff"], x["step"], x["pos"], x["cat"]))
    print()

    # ---- 7. was it predictable at dispatch? --------------------------------
    print("7. WAS THE BLOCKAGE VISIBLE AT DISPATCH TIME?  (Part 2 step 6)")
    with_asg = [r for r in releases if r.get("asg")]
    print("     releases traced back to their assign event: %d / %d"
          % (len(with_asg), len(releases)))
    if with_asg:
        openr = [r for r in with_asg if r["asg"].get("dsp_route_open")]
        closed = [r for r in with_asg if r["asg"].get("dsp_route_open") is False]
        unk = [r for r in with_asg if r["asg"].get("dsp_route_open") is None]
        print("       route was OPEN at commitment   : %d" % len(openr))
        print("       route was ALREADY CLOSED       : %d" % len(closed))
        print("       not measurable                 : %d" % len(unk))
        print("     transit steps between assign and route_blocked release:")
        tr = sorted(r["transit"] for r in with_asg if r["transit"] is not None)
        print("       %s" % tr)
        if tr:
            print("       min %d  median %d  max %d"
                  % (tr[0], tr[len(tr) // 2], tr[-1]))
        if closed:
            print("     for the ALREADY-CLOSED ones, was a rival with an open route")
            print("     available at that moment?")
            for r in closed:
                print("       %-6s %-4s %-11s step %3d  chosen_dist=%s  "
                      "alt_open=%s alt_blocked=%s"
                      % (r["combo"], r["seed"], r["ff"], r["asg"]["step"],
                         r["asg"].get("dsp_dist"), r["asg"].get("dsp_alt_open"),
                         r["asg"].get("dsp_alt_blocked")))
        print("     alternatives available at commitment (all releases):")
        print("       assigns with >=1 OTHER dispatchable unit: %d / %d"
              % (sum(1 for r in with_asg
                     if (r["asg"].get("dsp_alt_open", 0)
                         + r["asg"].get("dsp_alt_blocked", 0)) > 0), len(with_asg)))
        print("       of those, at least one alternative with an OPEN route: %d"
              % sum(1 for r in with_asg if r["asg"].get("dsp_alt_open", 0) > 0))
    print()

    if a.dump:
        print("=" * 78)
        print("PER-RELEASE DETAIL")
        print("=" * 78)
        hdr = ("combo  seed ff          step pos       mfd free safe ideal enc "
               "onfire | moved post      pmfd psafe | died_in safe_in")
        print(hdr)
        for r in sorted(releases, key=lambda z: (z["combo"], z["seed"], z["step"])):
            mv = r.get("mv") or {}
            print("%-6s %-4s %-11s %4d %-9s %3s %4s %4s %5s %3s %6s | %5s %-9s %4s %5s | %7s %7s"
                  % (r["combo"], r["seed"], r["ff"], r["step"],
                     r.get("rel_pos"), r.get("rel_mfd"), r.get("rel_n_free"),
                     r.get("rel_n_safe"), r.get("rel_n_ideal"),
                     "Y" if r.get("rel_enclosed") else "-",
                     "Y" if r.get("rel_on_fire") else "-",
                     "Y" if mv.get("moved") else "-", mv.get("post_pos"),
                     mv.get("post_mfd"), "Y" if mv.get("post_safe") else "-",
                     r.get("died_in"), r.get("safe_in")))


main()
