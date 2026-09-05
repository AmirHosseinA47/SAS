"""Feature 2 (victims flee approaching fire): compare _ffr_harness.py waves.

usage:
  _vm_analyze.py --base vmbase --ctrl vmoff --feat vmon

Three arms, all produced by the SAME outputs/_ffr_harness.py against different
checkouts / --set overrides, so every field lines up seed for seed:

  base  9c3eac6, the pre-feature reference
  ctrl  the feature source with VICTIM_FLEE_TRIGGER_DISTANCE=0 (kill switch)
  feat  the feature source at its defaults

What it checks, in the order the brief demands it:
  1. kill-switch byte identity, ctrl vs base, on every recorded field
  2. fire-map identity on BOTH arms - victims are inert to fire spread, so the
     feature arm must also be per-step identical; a divergence is a coupling
     that should not exist
  3. seed-matched outcome metrics
  4. the deaths split: AVOIDED vs RELOCATED vs CAUSED, and for every death
     whether it happened on the spawn cell or somewhere the victim fled to
  5. detection: never_detected, plus BOTH unreachable escape-hatch causes
  6. the contact assertion: no rescue may begin exiting without the firefighter
     standing on the victim
"""
from __future__ import annotations

import argparse
import collections
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
COMBOS = (
    [("east", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("east", "default", s) for s in (101, 202, 303)]
)

# every recorded field the kill switch must reproduce exactly
IDENTITY_FIELDS = (
    "eval", "fire_digests", "ff_steps", "completions", "recycles", "assigns",
    "unassigns", "unreachable_marks", "planner", "recycle_to_next_assign",
    "idle", "absence_log", "absence_counters", "unreachable_escape_log",
    "rescue_event_counts", "rescue_failed", "terminal_step",
    "pending_removal_failures_total", "leftover_pending", "stdout_sha256",
    "first_burn_step", "fire_ground_final",
)


def _name(tag, wind, roles, seed):
    rr = "def" if roles == "default" else roles
    return os.path.join(BASE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def load(tag):
    runs, missing = {}, []
    for wind, roles, seed in COMBOS:
        p = _name(tag, wind, roles, seed)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            missing.append(os.path.basename(p))
            continue
        with open(p, encoding="utf-8") as f:
            runs[(wind, roles, seed)] = json.load(f)
    if missing:
        print("  MISSING (%d): %s" % (len(missing), ", ".join(missing)))
    return runs


def label(k):
    return "D/%s/%s %d" % (k[0], k[1], k[2])


def rule(title):
    print("\n" + "=" * 96)
    print(title)
    print("=" * 96)


# ----------------------------------------------------------------------
# per-victim facts derived from the per-step victim rows
# ----------------------------------------------------------------------
def victim_facts(run):
    """{vid: {...}} - death step/cell, final cell/status, moves, displacement."""
    spawns = {k: (tuple(v) if v else None) for k, v in (run.get("victim_spawns") or {}).items()}
    steps = run.get("victim_steps") or []
    flee = run.get("victim_flee_log") or []
    fbs = run.get("first_burn_step") or {}

    moves = collections.defaultdict(list)
    for e in flee:
        moves[str(e.get("victim_id") or "")].append(e)

    facts: dict = {}
    # One pass, 1-based step index to match the harness's own step numbering.
    # The first row on which the marker reads "dead" is the casualty step, and
    # the cell on that row is where it died: `_check_fire_casualties` runs in
    # the post-move cycle of the same model.step() the row was recorded after.
    for idx, row in enumerate(steps, start=1):
        for vid, cell, status in row:
            f = facts.get(vid)
            if f is None:
                f = facts[vid] = {
                    "spawn": spawns.get(vid),
                    "death_step": None, "death_cell": None,
                    "first_cell": None,
                    "final_cell": None, "final_status": "",
                    "first_move_step": None,
                }
            if f.get("first_cell") is None and cell:
                f["first_cell"] = tuple(cell)
            f["final_cell"] = tuple(cell) if cell else None
            f["final_status"] = status
            if status == "dead" and f["death_step"] is None:
                f["death_step"] = idx
                f["death_cell"] = tuple(cell) if cell else None

    for vid, f in facts.items():
        ms = moves.get(vid, [])
        f["moves"] = len(ms)
        f["first_move_step"] = ms[0]["step"] if ms else None
        f["last_move_step"] = ms[-1]["step"] if ms else None
        f["max_displacement"] = max([m.get("displacement") or 0 for m in ms], default=0)
        f["escapes"] = sum(1 for m in ms if m.get("escaped_own_cell"))
        end_cell = f["death_cell"] or f["final_cell"]
        # Anchor: the recorded spawn cell when the arm has one. The baseline
        # predates the spawn_cell attribute, and there a victim's first observed
        # cell IS its spawn, because nothing ever moved it.
        sp = f["spawn"] or f.get("first_cell")
        f["anchor"] = sp
        f["end_displacement"] = (
            None if (end_cell is None or sp is None)
            else abs(end_cell[0] - sp[0]) + abs(end_cell[1] - sp[1])
        )
        f["dead"] = f["death_step"] is not None
        f["died_on_spawn"] = bool(f["dead"] and sp is not None and f["death_cell"] == sp)
        f["died_elsewhere"] = bool(f["dead"] and sp is not None and f["death_cell"] != sp)
        # moves into ground that caught fire only afterwards
        into_later_burned = 0
        for m in ms:
            to = m.get("to") or []
            if len(to) < 2:
                continue
            ig = fbs.get("%d,%d" % (int(to[0]), int(to[1])))
            if ig is not None and int(ig) > int(m.get("step") or 0):
                into_later_burned += 1
        f["moves_into_later_burned"] = into_later_burned
        # what ground is the victim standing on at the end
        ground = (run.get("fire_ground_final") or {})
        f["end_ground"] = None
        if end_cell is not None:
            g = ground.get("%d,%d" % (end_cell[0], end_cell[1]))
            if g:
                has_burned, burnt, burning = int(g[0]), int(g[1]), int(g[2])
                f["end_ground"] = (
                    "burning" if burning else
                    "burnt" if burnt else
                    "scorched" if has_burned else "green"
                )
    return facts


# ----------------------------------------------------------------------
def identity_check(base, ctrl):
    rule("1. KILL-SWITCH CONTROL vs 9c3eac6 BASELINE - expected byte-identical")
    print("  %-22s %s" % ("combo", "first field that differs, or IDENTICAL"))
    print("  " + "-" * 80)
    ok = 0
    for k in COMBOS:
        b, c = base.get(k), ctrl.get(k)
        if b is None or c is None:
            print("  %-22s MISSING ARM" % label(k))
            continue
        diff = [f for f in IDENTITY_FIELDS if b.get(f) != c.get(f)]
        if not diff:
            ok += 1
            print("  %-22s IDENTICAL" % label(k))
        else:
            print("  %-22s DIFFERS: %s" % (label(k), ", ".join(diff)))
    print("\n  byte-identical on all %d recorded fields: %d/%d runs"
          % (len(IDENTITY_FIELDS), ok, len(COMBOS)))
    return ok == len(COMBOS)


def fire_identity(base, arm, name):
    """Victims are inert to fire spread, so BOTH arms must match per step."""
    print("\n  fire-map identity, %s vs baseline (per-step digest):" % name)
    all_ok = True
    for k in COMBOS:
        b, a = base.get(k), arm.get(k)
        if b is None or a is None:
            continue
        bd, ad = b.get("fire_digests") or [], a.get("fire_digests") or []
        if bd == ad:
            continue
        all_ok = False
        first = next((i for i, (x, y) in enumerate(zip(bd, ad)) if x != y), min(len(bd), len(ad)))
        print("    %-22s DIVERGES at step %d  (len %d vs %d)"
              % (label(k), first + 1, len(bd), len(ad)))
    print("    %s" % ("identical on every step of all 13 runs"
                      if all_ok else "*** DIVERGENCE - a leaked coupling ***"))
    return all_ok


def metrics(base, feat):
    rule("3. FEATURE ARM vs BASELINE, SEED-MATCHED")
    hdr = ("combo", "rescued", "dead", "unreach", "nvdet", "geoiso", "ffdead", "terminal")
    print("  %-22s %-12s %-12s %-10s %-10s %-10s %-10s %-12s" % hdr)
    print("  " + "-" * 100)
    tot = collections.Counter()
    for k in COMBOS:
        b, f = base.get(k), feat.get(k)
        if b is None or f is None:
            continue
        be, fe = b["eval"], f["eval"]

        def cell(key):
            x, y = be.get(key, 0) or 0, fe.get(key, 0) or 0
            s = "%s -> %s" % (x, y)
            if x != y:
                s += " (%+d)" % (y - x)
            return s

        print("  %-22s %-12s %-12s %-10s %-10s %-10s %-10s %-12s" % (
            label(k), cell("rescued"), cell("dead"), cell("unreachable"),
            cell("never_detected"), cell("geographically_isolated"),
            cell("firefighter_deaths"),
            "%s -> %s" % (be.get("terminal_step"), fe.get("terminal_step"))))
        for m in ("rescued", "dead", "unreachable", "never_detected",
                  "geographically_isolated", "firefighter_deaths"):
            tot["b_" + m] += int(be.get(m, 0) or 0)
            tot["f_" + m] += int(fe.get(m, 0) or 0)
    print("  " + "-" * 100)
    print("  %-22s %-12s %-12s %-10s %-10s %-10s %-10s" % (
        "TOTAL",
        "%d -> %d (%+d)" % (tot["b_rescued"], tot["f_rescued"], tot["f_rescued"] - tot["b_rescued"]),
        "%d -> %d (%+d)" % (tot["b_dead"], tot["f_dead"], tot["f_dead"] - tot["b_dead"]),
        "%d -> %d" % (tot["b_unreachable"], tot["f_unreachable"]),
        "%d -> %d" % (tot["b_never_detected"], tot["f_never_detected"]),
        "%d -> %d" % (tot["b_geographically_isolated"], tot["f_geographically_isolated"]),
        "%d -> %d" % (tot["b_firefighter_deaths"], tot["f_firefighter_deaths"])))
    return tot


def deaths_split(base, feat):
    rule("4. THE KEY QUESTION - DEATHS AVOIDED vs DEATHS RELOCATED")
    print("  A victim that outruns fire for 40 steps and then dies is not a save.")
    print("  Every feature-arm death is classified, and every baseline death is")
    print("  traced into the feature arm.\n")

    avoided, caused, both_dead = [], [], []
    for k in COMBOS:
        b, f = base.get(k), feat.get(k)
        if b is None or f is None:
            continue
        bf, ff = victim_facts(b), victim_facts(f)
        for vid in sorted(set(bf) | set(ff)):
            bd = bf.get(vid, {}).get("dead", False)
            fd = ff.get(vid, {}).get("dead", False)
            rec = (k, vid, bf.get(vid, {}), ff.get(vid, {}))
            if bd and not fd:
                avoided.append(rec)
            elif fd and not bd:
                caused.append(rec)
            elif bd and fd:
                both_dead.append(rec)

    print("  DEATHS AVOIDED (died at baseline, alive in the feature arm): %d" % len(avoided))
    if avoided:
        print("    %-22s %-9s %-11s %-6s %-8s %-12s %s"
              % ("combo", "victim", "base death", "moves", "endDisp", "endGround", "final status"))
        for k, vid, b, f in avoided:
            print("    %-22s %-9s step %-6s %-6d %-8s %-12s %s"
                  % (label(k), vid, b.get("death_step"), f.get("moves", 0),
                     f.get("end_displacement"), f.get("end_ground"), f.get("final_status")))

    print("\n  DEATHS CAUSED (alive at baseline, dead in the feature arm): %d" % len(caused))
    for k, vid, b, f in caused:
        print("    %-22s %-9s died step %-5s on %-10s moves=%d endDisp=%s onSpawn=%s"
              % (label(k), vid, f.get("death_step"), f.get("death_cell"),
                 f.get("moves", 0), f.get("end_displacement"), f.get("died_on_spawn")))

    reloc = [r for r in both_dead if r[3].get("moves", 0) > 0]
    stayed = [r for r in both_dead if r[3].get("moves", 0) == 0]
    print("\n  DEATHS RELOCATED (dead in BOTH arms, but fled first): %d" % len(reloc))
    if reloc:
        print("    %-22s %-9s %-11s %-11s %-6s %-8s %-9s %s"
              % ("combo", "victim", "base death", "feat death", "moves", "endDisp",
                 "onSpawn", "steps fled->died"))
        for k, vid, b, f in reloc:
            fm, ds = f.get("first_move_step"), f.get("death_step")
            span = (ds - fm) if (fm is not None and ds is not None) else None
            print("    %-22s %-9s step %-6s step %-6s %-6d %-8s %-9s %s"
                  % (label(k), vid, b.get("death_step"), ds, f.get("moves", 0),
                     f.get("end_displacement"), f.get("died_on_spawn"), span))
    print("\n  DEATHS UNCHANGED (dead in both arms, never moved): %d" % len(stayed))

    # where every feature-arm death happened
    on_spawn = sum(1 for k in COMBOS if feat.get(k)
                   for v in victim_facts(feat[k]).values()
                   if v.get("dead") and v.get("died_on_spawn"))
    off_spawn = sum(1 for k in COMBOS if feat.get(k)
                    for v in victim_facts(feat[k]).values()
                    if v.get("died_elsewhere"))
    print("\n  EVERY feature-arm death by where it happened:")
    print("    on the cell it started on      : %d" % on_spawn)
    print("    on a cell it moved to          : %d" % off_spawn)
    return avoided, caused, reloc, stayed


def mechanism(feat):
    rule("5. MECHANISM - WHAT THE MOVEMENT ACTUALLY DID")
    # "total displacement" == number of moves: every step is exactly one cell.
    # Reported once, not twice under two headings.
    print("  %-22s %-8s %-8s %-9s %-9s %-9s %-9s"
          % ("combo", "moved", "steps", "maxFromSp", "endFromSp", "escapes", "intoBurn"))
    print("  " + "-" * 82)
    tot = collections.Counter()
    for k in COMBOS:
        f = feat.get(k)
        if f is None:
            continue
        facts = victim_facts(f)
        movers = [v for v in facts.values() if v.get("moves", 0) > 0]
        moves = sum(v["moves"] for v in facts.values())
        maxd = max([v.get("max_displacement") or 0 for v in facts.values()], default=0)
        esc = sum(v.get("escapes", 0) for v in facts.values())
        into = sum(v.get("moves_into_later_burned", 0) for v in facts.values())
        enddisp = sum(v.get("end_displacement") or 0 for v in facts.values()
                      if v.get("moves", 0) > 0)
        print("  %-22s %-8d %-8d %-9d %-9d %-9d %-9d"
              % (label(k), len(movers), moves, maxd, enddisp, esc, into))
        tot["movers"] += len(movers)
        tot["moves"] += moves
        tot["escapes"] += esc
        tot["into"] += into
        tot["victims"] += len(facts)
    print("  " + "-" * 82)
    print("  TOTAL victims=%d, victims that moved=%d, moves=%d, "
          "own-cell escapes=%d, moves into ground that burned later=%d"
          % (tot["victims"], tot["movers"], tot["moves"], tot["escapes"], tot["into"]))

    print("\n  final displacement from spawn, victims that moved:")
    disp = [v.get("end_displacement") for k in COMBOS if feat.get(k)
            for v in victim_facts(feat[k]).values()
            if v.get("moves", 0) > 0 and v.get("end_displacement") is not None]
    if disp:
        disp.sort()
        print("    n=%d  min=%d  median=%d  max=%d   (leash is 6)"
              % (len(disp), disp[0], disp[len(disp) // 2], disp[-1]))
    else:
        print("    no victim moved")

    print("\n  ground a moved victim ends the run standing on:")
    ground = collections.Counter(
        v.get("end_ground") for k in COMBOS if feat.get(k)
        for v in victim_facts(feat[k]).values() if v.get("moves", 0) > 0)
    for g, n in sorted(ground.items(), key=lambda x: -x[1]):
        print("    %-10s %d" % (g, n))
    print("    NOTE: a static victim could never stand on burnt or scorched ground.")
    return tot


def detection(base, feat):
    rule("6. DETECTION AND THE UNREACHABLE ESCAPE HATCHES")
    print("  Both causes reported per run against the baseline, since the")
    print("  'largely inert' conclusion in Part 1 was argued, not proven.\n")
    print("  %-22s %-22s %-22s %s"
          % ("combo", "never_detected", "geographically_isolated", "escape-hatch marks"))
    print("  " + "-" * 96)
    bad = False
    for k in COMBOS:
        b, f = base.get(k), feat.get(k)
        if b is None or f is None:
            continue
        bn, fn = b["eval"].get("never_detected", 0), f["eval"].get("never_detected", 0)
        bg, fg = b["eval"].get("geographically_isolated", 0), f["eval"].get("geographically_isolated", 0)
        marks = [(e.get("victim_id"), e.get("cause"), e.get("step"))
                 for e in (f.get("unreachable_escape_log") or [])]
        if fn > bn or fg > bg:
            bad = True
        print("  %-22s %-22s %-22s %s"
              % (label(k), "%s -> %s%s" % (bn, fn, " ***" if fn > bn else ""),
                 "%s -> %s%s" % (bg, fg, " ***" if fg > bg else ""),
                 marks if marks else "-"))
    print("\n  any run where either cause increased: %s" % ("YES ***" if bad else "no"))
    return not bad


def contact(base, feat):
    rule("7. CONTACT ASSERTION - NO RESCUE MAY BEGIN WITHOUT THE FIREFIGHTER ON THE VICTIM")
    print("  The stale target_pos let a unit reach a cell the victim had left,")
    print("  flip to exiting against empty ground, and teleport the victim to")
    print("  itself. Asserted directly at the exiting False->True transition.\n")
    for tag, runs in (("baseline", base), ("feature", feat)):
        starts = [(k, e) for k in COMBOS if runs.get(k)
                  for e in (runs[k].get("exit_starts") or [])]
        bad = [(k, e) for k, e in starts if not e.get("contact")]
        print("  %-9s exit transitions: %-4d   without contact: %d%s"
              % (tag, len(starts), len(bad), "  *** FABRICATED RESCUE ***" if bad else ""))
        for k, e in bad:
            print("      %-22s step %-4s ff=%s at %s victim=%s at %s"
                  % (label(k), e.get("step"), e.get("ff"), e.get("ff_pos"),
                     e.get("victim"), e.get("victim_pos")))
    rt = [(k, e) for k in COMBOS if feat.get(k) for e in (feat[k].get("retargets") or [])]
    print("\n  live re-targets in the feature arm: %d" % len(rt))
    for k, e in rt[:20]:
        print("      %-22s step %-4s ff=%s victim=%s %s -> %s"
              % (label(k), e.get("step"), e.get("ff"), e.get("victim"),
                 e.get("from"), e.get("to")))
    if len(rt) > 20:
        print("      ... %d more" % (len(rt) - 20))
    base_rt = sum(len(base[k].get("retargets") or []) for k in COMBOS if base.get(k))
    print("  live re-targets in the baseline arm: %d (expected 0 - nothing refreshed it)" % base_rt)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--ctrl", default=None)
    ap.add_argument("--feat", default=None)
    args = ap.parse_args()

    print("Loading base=%s ctrl=%s feat=%s" % (args.base, args.ctrl, args.feat))
    base = load(args.base)
    ctrl = load(args.ctrl) if args.ctrl else {}
    feat = load(args.feat) if args.feat else {}

    gates = {}
    if ctrl:
        gates["kill_switch"] = identity_check(base, ctrl)
        rule("2. FIRE-MAP IDENTITY - REQUIRED ON BOTH ARMS")
        print("  Victim movement draws from no RNG and a victim's presence in a")
        print("  cell is invisible to Fire.probability_of_fire, so a seed-matched")
        print("  run must reproduce the fire map step for step in BOTH arms.")
        gates["fire_ctrl"] = fire_identity(base, ctrl, "control")
    if feat:
        if "fire_ctrl" not in gates:
            rule("2. FIRE-MAP IDENTITY - REQUIRED ON BOTH ARMS")
        gates["fire_feat"] = fire_identity(base, feat, "feature")
        tot = metrics(base, feat)
        gates["dead_not_up"] = tot["f_dead"] <= tot["b_dead"]
        deaths_split(base, feat)
        mechanism(feat)
        gates["detection"] = detection(base, feat)
        contact(base, feat)

    rule("GATE SUMMARY")
    for name, ok in gates.items():
        print("  %-16s %s" % (name, "PASS" if ok else "FAIL"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
