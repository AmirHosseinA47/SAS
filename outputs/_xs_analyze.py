"""Exit-stall round, Part 1 - analysis of the probe wave (outputs/exitstall_prereg.txt).
Read-only. -> outputs/_xs_analysis.txt (tests) and outputs/_xs_legs.txt (step-by-step legs)

  T0  identity   each trace run == its recorded run over the steps it ran (per-step series,
                 every event list cut at that step). The harness eval is a function of the
                 LAST step, so a shorter replay's eval cannot be compared with the recorded
                 run's; the per-step victim/firefighter status series carry the same facts.
  H1  state leak onto the carrying leg: (a) reads, (b) accessor calls, (c) movers,
      (d) XS_RESET=exit legs identical
  H2  mechanism: every carrying step of the 11 stalled legs by _move_toward's own tier
  H3  positioning-only: where/when its stalled legs start vs the control's same victim
  H4  XS_RESET=assign: first divergence, and whether it precedes the carrying leg
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERIES = ("fire_digests", "victim_steps", "ff_steps", "ff_bind_steps", "uav_steps", "uav_actions", "partition_steps")
EVENTS = ("assigns", "unassigns", "completions", "recycles", "firefight_log", "retargets", "exit_starts",
          "unreachable_marks", "planner", "absence_log", "victim_flee_log", "victim_lateral_log",
          "unreachable_escape_log", "victim_holds", "rescue_failed")
MODE_FIELDS = ("_firefight_suspended", "_idle_retreat_origin", "_idle_retreat_steps", "_idle_retreat_stalled",
               "_idle_retreat_last_cell")
GRID = 50
# (trace tag, recorded tag, wind, roles, seed, steps, stalled victim)
TRACES = [
    ("xsTD", "uhD", "east", "half", 2070841104, 120, "victim_0"),
    ("xsTD", "uhD", "east", "half", 294124329, 151, "victim_0"),
    ("xsTD", "uhD", "east", "half", 1433805104, 290, "victim_0"),
    ("xsTD", "uhD", "south", "half", 1048395951, 271, "victim_0"),
    ("xsTD", "uhD", "east", "default", 1749069988, 207, "victim_3"),
    ("xsTY", "uhY", "east", "half", 2070841104, 120, "victim_0"),
    ("xsTY", "uhY", "east", "half", 294124329, 151, "victim_0"),
    ("xsTK", "ugKC", "east", "half", 294124329, 179, "victim_0"),
    ("xsTK", "ugKC", "east", "half", 2070841104, 127, "victim_0"),
    ("xsTK", "ugKC", "east", "default", 1420331661, 158, "victim_0"),
    ("xsTK", "ugKC", "south", "half", 903347495, 82, "victim_2"),
]
RESETS = [("xsRED", "uhD"), ("xsREY", "uhY"), ("xsRAD", "uhD"), ("xsRAY", "uhY")]
OUT, LEGS = [], []


def say(s=""):
    OUT.append(str(s))
    print(s)


def leg(s=""):
    LEGS.append(str(s))


def fname(tag, w, r, s, ext=".json"):
    return os.path.join(HERE, "_ffr_%s_%s_%s_%d%s" % (tag, w, "def" if r == "default" else r, s, ext))


def load(p):
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def prefix_diffs(a, b, n):
    diffs = []
    for k in SERIES:
        x, y = a.get(k), b.get(k)
        if x is None and y is None:
            continue
        if not isinstance(x, list) or not isinstance(y, list) or len(x) != n or x != y[:n]:
            first = None
            if isinstance(x, list) and isinstance(y, list):
                first = next((i + 1 for i, (p, q) in enumerate(zip(x, y)) if p != q), None)
            diffs.append("%s (first differs at step %s)" % (k, first))
    for k in EVENTS:
        x, y = a.get(k), b.get(k)
        if not isinstance(x, list) and not isinstance(y, list):
            continue
        if not isinstance(x, list) or not isinstance(y, list):
            diffs.append(k + " (present in one run only)")
            continue
        yy = [e for e in y if isinstance(e, dict) and e.get("step", 10 ** 9) <= n]
        if x != yy:
            diffs.append("%s (%d vs %d events <= %d)" % (k, len(x), len(yy), n))
    return diffs


def leg_bounds(d, vid):
    comp = next((c for c in d.get("completions") or [] if c.get("victim") == vid), None)
    if comp is None:
        return None
    st = [e for e in d.get("exit_starts") or [] if e.get("victim") == vid and e["step"] <= comp["step"]]
    return (st[-1]["step"], comp["step"], comp["ff"], tuple(comp["exit_target"])) if st else None


def on_boundary(p):
    return p is not None and (p[0] in (0, GRID - 1) or p[1] in (0, GRID - 1))


def predicted(mt):
    """_move_toward's choice from the recorded neighbour tests (agents.py tier pools)."""
    nb = [n for n in mt["neighbours"] if not n["fire"]]
    if not nb:
        return None, None
    pools = [[n for n in nb if n["improving"] and not n["adj_fire"] and not n["smoke"]],
             [n for n in nb if n["maintaining"] and not n["adj_fire"] and not n["smoke"]],
             [n for n in nb if not n["adj_fire"] and not n["smoke"]]]
    for tier, pool in enumerate(pools, start=1):
        if pool:
            best = min(pool, key=lambda n: (n["dist_after"], 0 if n["preferred"] else 1))
            return best["cell"], tier
    # tier 4: least risk (agents.py _firefighter_cell_risk: 100 x fire-adjacent + 10 x smoky)
    best = min(nb, key=lambda n: (100 * n["adj_fire"] + 10 * n["smoke"], n["dist_after"], 0 if n["preferred"] else 1))
    return best["cell"], 4


def code(n):
    if n["fire"]:
        return "F"
    return ("a" if n["adj_fire"] else "") + ("s" if n["smoke"] else "") or "ok"


def main():
    sys.stdout.reconfigure(newline="\n")
    say("EXIT-LEG STALL, PART 1 - probe wave analysis (pre-registration outputs/exitstall_prereg.txt)")
    traces = {}
    say("")
    say("T0 IDENTITY: each trace run vs its recorded run, over the steps it ran")
    t0_ok = True
    for tag, ref, w, r, s, n, vid in TRACES:
        a, b = load(fname(tag, w, r, s)), load(fname(ref, w, r, s))
        t = load(fname(tag, w, r, s, ".xstrace.json"))
        lab = "%s %s/%s/%d" % (tag, w, r, s)
        if a is None or b is None or t is None:
            say("  %-32s MISSING (run %s, recorded %s, trace %s)" % (lab, a is not None, b is not None, t is not None))
            t0_ok = False
            continue
        diffs = prefix_diffs(a, b, n)
        if a.get("steps") != n:
            diffs.append("steps %r" % a.get("steps"))
        say("  %-32s vs %-5s %s%s" % (lab, ref, "IDENTICAL over %d steps" % n if not diffs else "DIFFERS: ",
                                     "; ".join(diffs)))
        if t.get("errors"):
            say("      probe errors: %s" % t["errors"][:3])
            diffs.append("probe errors")
        if diffs:
            t0_ok = False
        else:
            traces[(tag, w, r, s)] = (a, t, vid)
    say("  T0 %s (%d of %d traces readable)" % ("PASS" if t0_ok else "FAIL", len(traces), len(TRACES)))

    # ---------------- H1 ----------------
    say("")
    say("H1 STATE LEAK ONTO THE CARRYING LEG - every carrying advance in every readable trace run")
    reads = collections.Counter()
    n_carry = 0
    movers = collections.Counter()
    acc = collections.Counter()
    acc_chain = collections.Counter()
    mode_seen = collections.Counter()
    outside_carry = []
    between_carry = []
    for (tag, w, r, s), (a, t, vid) in sorted(traces.items()):
        carrying_at = {}
        for row in t["advances"]:
            carrying_at[(row["step"], row["ff"])] = row["carrying"]
            if not row["carrying"]:
                continue
            n_carry += 1
            reads.update(row.get("reads") or [])
            for m in row["moves"]:
                movers[m["chain"][0] if m["chain"] else "?"] += 1
            for k in MODE_FIELDS:
                v = row["fields"].get(k, "<absent>")
                mode_seen["%s=%s" % (k, json.dumps(v))] += 1
        for c in t["accessor_calls"]:
            acc[c["accessor"]] += 1
            acc_chain[" <- ".join(c["chain"][:2])] += 1
        for m in t["outside_moves"]:
            if carrying_at.get((m["step"], m["ff"])) or carrying_at.get((m["step"] - 1, m["ff"])):
                outside_carry.append((tag, w, r, s, m))
        for ch in t["between_changes"]:
            if carrying_at.get((ch["step"], ch["ff"])) and carrying_at.get((ch["step"] - 1, ch["ff"])):
                between_carry.append((tag, w, r, s, ch))
    leaked_reads = sorted(k for k in reads if k in MODE_FIELDS or "firefight_suspended" in k)
    say("  carrying advances examined: %d" % n_carry)
    say("  (a) attributes READ on the unit during carrying advances (name: advances):")
    say("      " + ", ".join("%s: %d" % kv for kv in sorted(reads.items())))
    say("      firefighting/idle-mode fields among them: %s" % (", ".join(leaked_reads) or "NONE"))
    say("      values those fields HELD during carrying advances (field=value: advances):")
    for kv in sorted(mode_seen.items()):
        say("        %s: %d" % kv)
    say("  (b) ff_firefight_* accessor calls during carrying advances: %s" % (dict(acc) or "none"))
    say("      call sites: %s" % (dict(acc_chain) or "none"))
    say("      ff_firefight_engaged_retreat_range calls: %d" % acc.get("ff_firefight_engaged_retreat_range", 0))
    say("  (c) grid moves made during carrying advances, by the function that made them: %s" % dict(movers))
    say("      moves of a carrying unit made OUTSIDE its advance: %d%s" % (
        len(outside_carry), "".join("\n        %s %s/%s/%d %s" % x for x in outside_carry[:10])))
    say("      unit fields changed BETWEEN two carrying advances (model-side writes): %d%s" % (
        len(between_carry), "".join("\n        %s %s/%s/%d %s" % x for x in between_carry[:10])))

    say("  (d) XS_RESET=exit: carrying legs vs recorded, position for position")
    d_ok = True
    for rtag, ref in RESETS[:2]:
        for tag, rref, w, r, s, n, vid in TRACES:
            if rref != ref:
                continue
            a, b = load(fname(rtag, w, r, s)), load(fname(ref, w, r, s))
            if a is None or b is None:
                say("      %s %s/%s/%d MISSING" % (rtag, w, r, s))
                d_ok = False
                continue
            lb = leg_bounds(b, vid)
            la = leg_bounds(a, vid)
            same_leg = la == lb
            diffs = prefix_diffs(a, b, n)
            d_ok = d_ok and same_leg
            say("      %-6s %s/%s/%d %s: leg %s vs recorded %s -> %s; whole run %s" % (
                rtag, w, r, s, vid, la, lb, "SAME LEG" if same_leg else "LEG CHANGED",
                "identical" if not diffs else "differs: " + "; ".join(diffs[:3])))
    h1 = (not leaked_reads) and acc.get("ff_firefight_engaged_retreat_range", 0) == 0 and \
        set(movers) <= {"_move_toward"} and not outside_carry and d_ok
    say("  H1 %s" % ("REFUTED for the carrying leg: no mode field read, K never read, only _move_toward moves the unit, "
                     "reset-at-exit legs identical" if h1 else "NOT REFUTED - see the failing item above"))

    # ---------------- H2 + the step-by-step legs ----------------
    say("")
    say("H2 MECHANISM - every carrying step of every stalled leg, by _move_toward's tier")
    leg("EXIT-LEG STALL, PART 1 - every stalled carrying leg, step by step (from the probe traces)")
    leg("Per step: step  pos -> next  mover  tier(pred)  | neighbours: cell dist code  (code: ok = tier-eligible,")
    leg("a = adjacent to fire, s = smoke, as = both, F = burning; * = the 'preferred' axis step) | exit cell state")
    leg("| nearest fire | 7x7 fire window (north up; U unit, F fire, s smoke, . fuel, _ burnt/no fuel, # off-grid).")
    leg("Mode fields are printed in full at the leg start and then only when they change.")
    tier_all = collections.Counter()
    mism = 0
    for (tag, w, r, s), (a, t, vid) in sorted(traces.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][3])):
        lb = leg_bounds(a, vid)
        if lb is None:
            say("  %s %s/%s/%d %s: no completed leg in the replay" % (tag, w, r, s, vid))
            continue
        s0, s1, ff, tgt = lb
        rows = [x for x in t["advances"] if x["ff"] == ff and s0 < x["step"] <= s1]
        tiers = collections.Counter()
        away = back = 0
        first_boundary = next((x["step"] for x in rows if on_boundary(x["pos"])), None)
        exit_states = collections.Counter(x["exit_target_fire"] for x in rows)
        leg("")
        leg("=" * 110)
        leg("%s %s/%s/%d %s  unit %s  exit start %d  completion %d  exit cell %s  (%d steps, %d cells)" % (
            tag, w, r, s, vid, ff, s0, s1, list(tgt), s1 - s0,
            abs(rows[0]["pos"][0] - tgt[0]) + abs(rows[0]["pos"][1] - tgt[1]) if rows else -1))
        prev_fields = None
        prev_pos = [rows[0]["pos"]] if rows else []   # the leg's start cell counts for a step-back
        for x in rows:
            mt = x["move_toward"][0] if x["move_toward"] else None
            mover = ",".join(m["chain"][0] for m in x["moves"]) or "-"
            tier = x.get("tier_after")
            pc, pt = predicted(mt) if mt else (None, None)
            if mt:
                tiers[mt["tier"]] += 1
                tier_all[mt["tier"]] += 1
                if pc is not None and (pc != mt["chosen"] or pt != mt["tier"]):
                    mism += 1
                db = mt["dist_before"]
                da = abs(mt["chosen"][0] - tgt[0]) + abs(mt["chosen"][1] - tgt[1])
                away += da > db
                back += (len(prev_pos) >= 2 and mt["chosen"] == prev_pos[-2])
            nbs = " ".join("%d,%d:%d:%s%s" % (n["cell"][0], n["cell"][1], n["dist_after"], code(n), "*" if n["preferred"] else "")
                           for n in (mt["neighbours"] if mt else []))
            f = x["fields"]
            if prev_fields is None:
                fl = "FIELDS " + json.dumps(f, sort_keys=True)
            else:
                ch = {k: f.get(k) for k in set(f) | set(prev_fields) if f.get(k) != prev_fields.get(k)}
                fl = ("changed " + json.dumps(ch, sort_keys=True)) if ch else ""
            prev_fields = f
            leg("%4d %s->%s %-12s t%s(p%s) | %s | exit %s | nf %s | %s %s" % (
                x["step"], x["pos"], x["pos_after"], mover, tier, pt, nbs, x["exit_target_fire"], x["nearest_fire"],
                "/".join(x["fire"]), fl))
            prev_pos.append(x["pos_after"])
        say("  %s %s/%s/%d %s: leg %d-%d (%d steps); first on ANY boundary cell at step %s; tiers %s; steps AWAY from "
            "the exit %d; immediate step-backs %d; exit cell state over the leg %s" % (
                tag, w, r, s, vid, s0, s1, s1 - s0, first_boundary, dict(sorted(tiers.items())), away, back,
                dict(exit_states)))
    say("  all stalled legs: tiers %s; recomputed-rule mismatches %d" % (dict(sorted(tier_all.items())), mism))

    # ---------------- H3 ----------------
    say("")
    say("H3 POSITIONING-ONLY: the same victim's leg in the control (uhC) vs the ungated arms")
    for tag, ref, w, r, s, n, vid in TRACES:
        if tag != "xsTY":
            continue
        c = load(fname("uhC", w, r, s))
        y = load(fname("uhY", w, r, s))
        dd = load(fname("uhD", w, r, s))
        for lab, d in (("uhC", c), ("uhY", y), ("uhD", dd)):
            if d is None:
                continue
            lb = leg_bounds(d, vid)
            st = next((e for e in d.get("exit_starts") or [] if e.get("victim") == vid and lb and e["step"] == lb[0]), None)
            asg = [x for x in d.get("assigns") or [] if x.get("vid") == vid]
            say("  %s/%s/%d %s %s: assigns %s; exit start %s at %s; completion %s; exit cell %s" % (
                w, r, s, vid, lab, [(x["step"], x["ff"], x["reason"]) for x in asg],
                lb[0] if lb else None, st["ff_pos"] if st else None, lb[1] if lb else None, list(lb[3]) if lb else None))

    # ---------------- H4 ----------------
    say("")
    say("H4 XS_RESET=assign: does state left by the idle/firefighting mode steer the APPROACH leg?")
    for rtag, ref in RESETS[2:]:
        for tag, rref, w, r, s, n, vid in TRACES:
            if rref != ref:
                continue
            a, b = load(fname(rtag, w, r, s)), load(fname(ref, w, r, s))
            if a is None or b is None:
                say("  %s %s/%s/%d MISSING" % (rtag, w, r, s))
                continue
            first = next((i + 1 for i, (p, q) in enumerate(zip(a["ff_steps"], b["ff_steps"][:n])) if p != q), None)
            la, lb = leg_bounds(a, vid), leg_bounds(b, vid)
            say("  %-6s %s/%s/%d: ff_steps first differ at step %s; stalled-victim leg %s vs recorded %s" % (
                rtag, w, r, s, first, la, lb))

    with open(os.path.join(HERE, "_xs_analysis.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")
    with open(os.path.join(HERE, "_xs_legs.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(LEGS) + "\n")


if __name__ == "__main__":
    main()
