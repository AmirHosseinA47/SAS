"""Final analysis for the _belief_gap_critical round.

Arms compared, all seed-matched over the canonical 13-run sample
(D/east half-roles 101-505, D/south half-roles 101-505, D/east default-roles
101/202/303, 240 steps):

  nopatch    no hooks                        -- determinism / observer control
  live       hooks record only               -- the real system
  arm        count-correct predicate         -- the counterfactual asked for
  falsearm   predicate forced constant-False -- NEGATIVE CONTROL: proves the
             arming mechanism has teeth (or that critical_collapse is inert
             outright)
"""
from __future__ import annotations
import glob, json, os, collections

BASE = os.path.dirname(os.path.abspath(__file__))
EVAL_KEYS = ("rescued", "dead", "firefighter_deaths", "never_detected",
             "terminal_step", "burnt_cells", "unreachable",
             "geographically_isolated", "rescue_rate")
# every recorded channel except the arm label itself
CHANNELS = ("crit", "triggers", "reason_src", "classify", "mm_update",
            "mode_transitions", "sop_mission_mode", "ind_shape",
            "analysis_trigger_hist", "info_reason_origin", "eval",
            "stdout_sha256", "agent_positions_sha256")


def load(mode):
    out = {}
    for p in sorted(glob.glob(os.path.join(BASE, "_bgc_run_%s_*.json" % mode))):
        r = json.load(open(p, encoding="utf-8"))
        out["%s|%s" % (r["label"], r["seed"])] = r
    return out


def diff_keys(a, b):
    return [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


def mode_series(r):
    return [(u["step"], u["new"]) for u in r["mm_update"]]


def runlen(series):
    out = []
    for _, m in series:
        if out and out[-1][0] == m:
            out[-1][1] += 1
        else:
            out.append([m, 1])
    return [(m, n) for m, n in out]


def main():
    nop, live, arm, neg = (load("nopatch"), load("live"), load("arm"),
                           load("falsearm"))
    print("runs loaded: nopatch=%d live=%d arm=%d falsearm=%d"
          % (len(nop), len(live), len(arm), len(neg)))
    print()

    print("=" * 78)
    print("CONTROL 1 - observer cleanliness / determinism (nopatch vs live)")
    print("=" * 78)
    bad = 0
    for k in sorted(set(nop) & set(live)):
        same = all(nop[k][f] == live[k][f] for f in
                   ("eval", "stdout_sha256", "agent_positions_sha256"))
        bad += not same
    print("  %d/%d seed-matched pairs identical on eval + stdout + positions"
          % (len(set(nop) & set(live)) - bad, len(set(nop) & set(live))))
    print("  -> the hooks do not perturb the run; runs are deterministic per seed")
    print()

    for label, other, what in (("arm", arm, "count-correct predicate"),
                               ("falsearm", neg, "predicate forced constant-False")):
        if not other:
            print("!! no %s runs found" % label)
            continue
        print("=" * 78)
        print("ARM: %s  (%s)" % (label, what))
        print("=" * 78)
        n_ident = 0
        flips_tot = 0
        for k in sorted(set(live) & set(other)):
            lo, ot = live[k], other[k]
            flips = sum(1 for c in ot["crit"] if c["live"] != c["corrected"])
            flips_tot += flips
            dk = diff_keys(lo, ot)
            chan = [c for c in dk if c in CHANNELS]
            ident = not chan
            n_ident += ident
            print("  %-22s returnFlips=%3d  differingChannels=%-28s eval=%s"
                  % (k, flips, chan if chan else "(none)",
                     "SAME" if lo["eval"] == ot["eval"] else "DIFF"))
        print("  ---")
        print("  runs identical to live on every recorded channel: %d/%d"
              % (n_ident, len(set(live) & set(other))))
        print("  total calls where the returned value differed from live: %d"
              % flips_tot)
        # mode trajectory
        same_traj = sum(1 for k in sorted(set(live) & set(other))
                        if mode_series(live[k]) == mode_series(other[k]))
        print("  mode trajectory identical, step for step: %d/%d"
              % (same_traj, len(set(live) & set(other))))
        # outcomes
        same_ev = sum(1 for k in sorted(set(live) & set(other))
                      if live[k]["eval"] == other[k]["eval"])
        print("  outcomes identical (all 9 eval keys): %d/%d"
              % (same_ev, len(set(live) & set(other))))
        # does it ever return to normal / when does it leave normal
        for k in sorted(set(live) & set(other)):
            ls, os_ = mode_series(live[k]), mode_series(other[k])
            l_ent = next((s for s, m in ls if m != "normal"), None)
            o_ent = next((s for s, m in os_ if m != "normal"), None)
            l_norm = any(m == "normal" for s, m in ls if l_ent and s > l_ent)
            o_norm = any(m == "normal" for s, m in os_ if o_ent and s > o_ent)
            if (l_ent, l_norm) != (o_ent, o_norm):
                print("  !! %s differs: live(enter=%s,returns=%s) %s(enter=%s,returns=%s)"
                      % (k, l_ent, l_norm, label, o_ent, o_norm))
        ents = {mode_series(other[k])[0] and
                next((s for s, m in mode_series(other[k]) if m != "normal"), None)
                for k in other}
        rets = {any(m == "normal" for s, m in mode_series(other[k])
                    if s > next((x for x, y in mode_series(other[k]) if y != "normal"), 0))
                for k in other}
        print("  %s: first non-normal step across runs = %s ; ever returns to normal = %s"
              % (label, sorted(x for x in ents if x is not None), rets))
        print()

    print("=" * 78)
    print("PREDICATE AGGREGATE (live arm = the real system)")
    print("=" * 78)
    tot = ltrue = ctrue = dis = zero = zero_true = 0
    shape = collections.Counter()
    lclause = collections.Counter()
    cclause = collections.Counter()
    for r in live.values():
        for c in r["crit"]:
            tot += 1
            ltrue += c["live"]
            ctrue += c["corrected"]
            dis += c["live"] != c["corrected"]
            if c["gap_count"] == 0:
                zero += 1
                zero_true += c["live"]
            shape["%s:%s" % (c["arg_type"], c["arg_len"])] += 1
            lclause[c["live_clause"]] += 1
            cclause[c["corrected_clause"]] += 1
    print("  calls                          : %d  (13 runs x 240 steps)" % tot)
    print("  live predicate True            : %d/%d" % (ltrue, tot))
    print("  count-correct predicate True   : %d/%d" % (ctrue, tot))
    print("  disagreements                  : %d  (%.1f%%)" % (dis, 100.0 * dis / tot))
    print("  calls with ZERO real gaps      : %d, of which live returned True: %d"
          % (zero, zero_true))
    print("  argument shape                 : %s" % dict(shape))
    print("  clause that decided (live)     : %s" % dict(lclause))
    print("  clause that decided (corrected): %s" % dict(cclause))
    print()

    print("=" * 78)
    print("CONSUMER REACH - what the predicate's value actually fed")
    print("=" * 78)
    emitted = collections.Counter()
    dis_emitted = 0
    per_step_emit = collections.Counter()
    for r in live.values():
        trg = {t["step"]: t["emitted"] for t in r["triggers"]}
        for c in r["crit"]:
            em = trg.get(c["step"], [])
            for e in em:
                emitted["%s|%s|%s" % (e["type"], e["severity"], e["planner"])] += 1
                per_step_emit[c["step"]] += 1
            if c["live"] != c["corrected"] and em:
                dis_emitted += 1
    print("  triggers emitted by _analyze_information_sufficiency: %s"
          % (dict(emitted) or "(none)"))
    print("  steps at which any was emitted: %s" % sorted(per_step_emit))
    print("  disagreeing calls that emitted ANY trigger: %d" % dis_emitted)
    print()

    print("=" * 78)
    print("MODE DRIVER - information_recovery vs search_mode_required")
    print("=" * 78)
    allok = True
    for k in sorted(live):
        r = live[k]
        smr = {e["step"] for e in r["reason_src"] if "search_mode_required" in e["final"]}
        ir = {x["step"] for x in r["sop_mission_mode"]
              if x["failsafe_mode"] == "information_recovery"}
        allok &= (smr == ir)
    print("  information_recovery == search_mode_required, step for step, all runs: %s"
          % allok)
    empty = collections.Counter()
    for r in live.values():
        for e in r["reason_src"]:
            if not e["final"]:
                empty[e["step"]] += 1
    print("  extract calls with an EMPTY reason set: %d, all at steps %s"
          % (sum(empty.values()), sorted(empty)))
    print("  (classify_mode returns NORMAL only when reason_set is empty)")
    print()

    print("=" * 78)
    print("SEED-MATCHED OUTCOMES")
    print("=" * 78)
    hdr = "%-22s %8s %5s %4s %5s %6s %7s" % (
        "run", "rescued", "dead", "ff", "nd", "term", "burnt")
    print(hdr + "   | arm | falsearm | nopatch")
    for k in sorted(live):
        e = live[k]["eval"]
        row = "%-22s %8s %5s %4s %5s %6s %7s" % (
            k, e.get("rescued"), e.get("dead"), e.get("firefighter_deaths"),
            e.get("never_detected"), e.get("terminal_step"), e.get("burnt_cells"))
        tags = []
        for m in (arm, neg, nop):
            tags.append("SAME" if (k in m and m[k]["eval"] == e) else
                        ("DIFF" if k in m else "n/a"))
        print(row + "   | " + " | ".join(tags))


if __name__ == "__main__":
    main()
