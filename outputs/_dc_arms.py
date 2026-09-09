#!/usr/bin/env python
"""Depot-cost round: read the arms.

  identity   byte-identity of two arms over every recorded field
  outcomes   the mission metrics per arm, per sample
  mechanism  the return leg: trips, distance, share of UAV-steps, charging
  stranded   the redefined no-stranding gate (see --mode stranded notes)
  exposure   UAV-steps on a burning cell / in smoke, per arm
  depots     the depot geometry and per-depot trip attribution

Read-only. Runs no simulation.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))

CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "def", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
SAMPLES = {"canonical": CANON, "fresh": FRESH, "both": CANON + FRESH}

# The identity whitelist. Same list as outputs/_bs_identity.py:43-54 plus the
# fields this round did not touch, so a difference anywhere is caught rather than
# excused. base_station and rtb_log are INCLUDED deliberately: at mode 0 they are
# None and {uid: []}, so this round's additions to them cannot hide a regression.
IDENTITY_FIELDS = [
    "eval", "terminal_step", "fire_final_digest", "fire_digests", "ff_steps",
    "ff_bind_steps", "uav_steps", "uav_actions", "victim_steps",
    "victim_flee_log", "victim_spawns", "first_burn_step", "burn_intervals",
    "fire_ground_final", "victim_flee_moves_total", "victim_holds",
    "victim_lateral_counts", "exit_starts", "retargets", "completions",
    "recycles", "assigns", "unassigns", "unreachable_marks", "planner",
    "idle", "absence_log", "absence_counters", "unreachable_escape_log",
    "rescue_event_counts", "rescue_failed", "pending_removal_failures_total",
    "leftover_pending", "base_station", "rtb_log", "rtb_counters",
    "partition_steps", "stdout_sha256", "stdout_lines",
]

METRICS = ["rescued", "dead", "never_detected", "unreachable",
           "geographically_isolated", "horizon_unresolved", "candidate",
           "firefighter_deaths", "burnt_cells"]


def load(tag, wind, roles, seed):
    p = os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, roles, seed))
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def runs(tag, sample):
    out = []
    for wind, roles, seed in SAMPLES[sample]:
        d = load(tag, wind, roles, seed)
        if d is not None:
            out.append(((wind, roles, seed), d))
    return out


def _ev(d, key):
    return (d.get("eval") or {}).get(key)


# ---------------------------------------------------------------- identity ----
# The three keys this round added INSIDE each rtb_log record. They are written by
# the SOURCE's own agents.py, so a comparison against a checkout that predates the
# round finds them absent on that side - the instrument recording the source
# faithfully, not the source behaving differently. --rtb-new-keys drops exactly
# these three and nothing else, so every pre-existing key is still compared.
RTB_NEW_KEYS = ("target_depot", "target_berth", "home_depot")

# The four sub-keys this round added INSIDE the recorded "base_station" object.
# Same class as RTB_NEW_KEYS and the same justification: they describe structures
# that exist on model.base_station only AFTER this round, so against a checkout
# that predates it the harness records them EMPTY (its `.get(...) or ()` finds
# nothing). That is the instrument recording a representation the old source does
# not have - not the old source behaving differently. The four PRE-EXISTING
# sub-keys (origin, size, uav_berths, firefighter_berths) are still compared, and
# they are what would actually catch a geometry regression.
BS_NEW_KEYS = ("depots", "uav_berths_by_depot", "uav_home", "firefighter_home")


def _strip_bs_new_keys(bs):
    if not isinstance(bs, dict):
        return bs
    return {k: v for k, v in bs.items() if k not in BS_NEW_KEYS}


def _strip_rtb_new_keys(log):
    if not isinstance(log, dict):
        return log
    return {
        uid: [{k: v for k, v in rec.items() if k not in RTB_NEW_KEYS}
              if isinstance(rec, dict) else rec
              for rec in (trips or [])]
        for uid, trips in log.items()
    }


def mode_identity(args):
    a, b = args.a, args.b
    total = same = 0
    field_diffs: dict = {}
    missing = 0
    for wind, roles, seed in SAMPLES[args.sample]:
        da, db = load(a, wind, roles, seed), load(b, wind, roles, seed)
        if da is None or db is None:
            missing += 1
            continue
        total += 1
        if getattr(args, "rtb_new_keys", False):
            da = dict(da); db = dict(db)
            da["rtb_log"] = _strip_rtb_new_keys(da.get("rtb_log"))
            db["rtb_log"] = _strip_rtb_new_keys(db.get("rtb_log"))
            da["base_station"] = _strip_bs_new_keys(da.get("base_station"))
            db["base_station"] = _strip_bs_new_keys(db.get("base_station"))
        diffs = [f for f in IDENTITY_FIELDS if da.get(f) != db.get(f)]
        if diffs:
            for f in diffs:
                field_diffs.setdefault(f, []).append((wind, roles, seed))
        else:
            same += 1
    print("IDENTITY  %s vs %s  sample=%s%s"
          % (a, b, args.sample,
             "  [dropped on BOTH sides: 3 new rtb_log keys + 4 new "
             "base_station sub-keys, which a pre-round source cannot produce]"
             if getattr(args, "rtb_new_keys", False) else ""))
    print("  %d / %d runs IDENTICAL on all %d fields   (missing files: %d)"
          % (same, total, len(IDENTITY_FIELDS), missing))
    if not field_diffs:
        return
    print("  DIFFERING FIELDS:")
    for f, where in sorted(field_diffs.items()):
        print("    %-32s on %d of %d runs" % (f, len(where), total))
    # The instrument-drift signature, applied automatically so the reading is not
    # left to judgement: the same field set on EVERY run, and no evaluation metric.
    every = all(len(w) == total for w in field_diffs.values())
    has_eval = "eval" in field_diffs
    print()
    if every and not has_eval:
        print("  SIGNATURE: the differing field set is IDENTICAL on every run and")
        print("  contains no evaluation metric. That is SCHEMA DRIFT, not a")
        print("  regression - re-measure the reference with the current harness")
        print("  rather than relaxing this comparison.")
    else:
        print("  SIGNATURE: differences are NOT uniform across runs%s."
              % (" and `eval` differs" if has_eval else ""))
        print("  That is a BEHAVIOURAL difference, not drift.")


# ---------------------------------------------------------------- outcomes ----
def _terminal(rr):
    """terminal_step summary: how many runs resolved every victim, and how fast.

    A separate column rather than another METRICS entry because it is not a count
    that can be summed - it is None on a run where the victims never all reached a
    terminal state, and summing that with zeros would read as "resolved at step 0".
    Reported as resolved/total and the mean step among the runs that resolved.
    """
    vals = [d.get("terminal_step") for _k, d in rr]
    got = [int(v) for v in vals if v is not None]
    if not got:
        return "term  0/%d      -" % len(vals)
    return "term %2d/%d  mean %5.1f" % (len(got), len(vals), statistics.mean(got))


def mode_outcomes(args):
    print("OUTCOMES  sample=%s" % args.sample)
    print("  (terminal_step is not summable - it is None when the victims never")
    print("   all reach a terminal state - so it is reported as resolved/total")
    print("   and the mean step among the runs that did resolve.)")
    hdr = "  %-8s %5s " % ("arm", "runs") + " ".join("%9s" % m[:9] for m in METRICS)
    print(hdr)
    base = None
    for tag in args.a.split(","):
        rr = runs(tag, args.sample)
        if not rr:
            print("  %-8s   (no runs)" % tag)
            continue
        tot = [sum(int(_ev(d, m) or 0) for _k, d in rr) for m in METRICS]
        print("  %-8s %5d " % (tag, len(rr)) + " ".join("%9d" % v for v in tot)
              + "  " + _terminal(rr))
        if base is None:
            base, base_tag = tot, tag
    if base is not None and len(args.a.split(",")) > 1:
        print("\n  DELTAS against %s" % base_tag)
        for tag in args.a.split(",")[1:]:
            rr = runs(tag, args.sample)
            if not rr:
                continue
            tot = [sum(int(_ev(d, m) or 0) for _k, d in rr) for m in METRICS]
            print("  %-8s %5s " % (tag, "") + " ".join(
                "%+9d" % (v - b) for v, b in zip(tot, base)))


# --------------------------------------------------------------- mechanism ----
def mode_mechanism(args):
    print("MECHANISM  sample=%s   (the metric this round exists to move is the"
          % args.sample)
    print("           return-leg share of UAV-steps, against 17.5%)")
    print("  %-8s %5s %6s %7s %8s %8s %9s %8s %8s"
          % ("arm", "runs", "trips", "arrived", "mean d", "mean dur",
             "return %", "charge %", "arr batt"))
    for tag in args.a.split(","):
        rr = runs(tag, args.sample)
        if not rr:
            continue
        trips = arrived = 0
        dists, durs, arrb = [], [], []
        ret_steps = chg_steps = uav_steps_total = 0
        for _k, d in rr:
            n_uav = len(d.get("rtb_counters") or {}) or 4
            uav_steps_total += n_uav * int(d.get("steps") or 240)
            for _uid, c in (d.get("rtb_counters") or {}).items():
                ret_steps += int(c.get("return_steps") or 0)
                chg_steps += int(c.get("charge_steps") or 0)
            for _uid, log in (d.get("rtb_log") or {}).items():
                for t in log:
                    trips += 1
                    dists.append(t.get("trigger_distance"))
                    if t.get("arrival_step") is not None:
                        arrived += 1
                        durs.append(t["arrival_step"] - t["trigger_step"])
                        arrb.append(t["arrival_level"])
        print("  %-8s %5d %6d %7d %8s %8s %8.2f%% %7.2f%% %8s"
              % (tag, len(rr), trips, arrived,
                 ("%.1f" % statistics.mean(dists)) if dists else "-",
                 ("%.1f" % statistics.mean(durs)) if durs else "-",
                 100.0 * ret_steps / max(uav_steps_total, 1),
                 100.0 * chg_steps / max(uav_steps_total, 1),
                 ("%.1f" % statistics.mean(arrb)) if arrb else "-"))


# ---------------------------------------------------------------- stranded ----
def mode_stranded(args):
    """The redefined gate.

    "Zero battery outside the depot" passed all five of the base-station round's
    permanently deadlocked legs, because they end with 37-42 battery in hand. The
    gate here is POSITIONAL: a UAV that is rtb_active at the horizon and has not
    moved for >= --stuck steps is stuck, whatever its battery.
    """
    print("STRANDING  sample=%s   stuck threshold = %d steps without moving"
          % (args.sample, args.stuck))
    print("  %-8s %5s %9s %9s %9s"
          % ("arm", "runs", "zero-batt", "stuck", "unarrived"))
    for tag in args.a.split(","):
        rr = runs(tag, args.sample)
        if not rr:
            continue
        zero = stuck = unarrived = 0
        detail = []
        for (wind, roles, seed), d in rr:
            station = d.get("base_station")
            depot_cells = set()
            if station:
                size = int(station["size"])
                for ox, oy in (station.get("depots") or [station["origin"]]):
                    depot_cells |= {(ox + i, oy + j)
                                    for i in range(size) for j in range(size)}
            for _uid, log in (d.get("rtb_log") or {}).items():
                for t in log:
                    if t.get("arrival_step") is None:
                        unarrived += 1
            rows = d.get("uav_steps") or []
            if not rows:
                continue
            order = [str(r[0]) for r in rows[0]]
            for a, uid in enumerate(order):
                last = rows[-1][a]
                pos = tuple(last[1]) if last[1] else None
                batt = float(last[4] or 0.0)
                state = str(last[5] or "")
                if batt <= 0.0 and pos not in depot_cells:
                    zero += 1
                if state == "returning":
                    n = 0
                    for i in range(len(rows) - 1, -1, -1):
                        if tuple(rows[i][a][1]) != pos:
                            break
                        n += 1
                    if n >= args.stuck:
                        stuck += 1
                        detail.append("%s/%s/%s %s at %s for %d steps batt %.1f"
                                      % (wind, roles, seed, uid, pos, n, batt))
        print("  %-8s %5d %9d %9d %9d" % (tag, len(rr), zero, stuck, unarrived))
        for line in detail:
            print("        %s" % line)


# ---------------------------------------------------------------- exposure ----
def mode_exposure(args):
    print("EXPOSURE  sample=%s   UAV-steps on a burning cell / in smoke" % args.sample)
    print("  %-8s %5s %9s %9s" % ("arm", "runs", "burning", "smoke"))
    for tag in args.a.split(","):
        rr = runs(tag, args.sample)
        if not rr:
            continue
        n = burn = smoke = 0
        for _k, d in rr:
            for row in (d.get("uav_actions") or []):
                for cell in row:
                    n += 1
                    # uav_actions row: [uid, action, burning, vis_smoke, agent_smoke, dist]
                    if len(cell) > 2 and cell[2]:
                        burn += 1
                    if len(cell) > 3 and (cell[3] or (len(cell) > 4 and cell[4])):
                        smoke += 1
        if n:
            print("  %-8s %5d %8.2f%% %8.2f%%"
                  % (tag, len(rr), 100.0 * burn / n, 100.0 * smoke / n))


# ------------------------------------------------------------------ depots ----
def mode_depots(args):
    print("DEPOTS  sample=%s" % args.sample)
    for tag in args.a.split(","):
        rr = runs(tag, args.sample)
        if not rr:
            continue
        st = rr[0][1].get("base_station")
        if not st:
            print("  %-8s no depot (feature off)" % tag)
            continue
        by_target: dict = {}
        dist_by_target: dict = {}
        home_hist: dict = {}
        for _k, d in rr:
            for h in (d.get("base_station") or {}).get("uav_home") or []:
                home_hist[int(h)] = home_hist.get(int(h), 0) + 1
            for _uid, log in (d.get("rtb_log") or {}).items():
                for t in log:
                    k = int(t.get("target_depot") or 0)
                    by_target[k] = by_target.get(k, 0) + 1
                    dist_by_target.setdefault(k, []).append(t["trigger_distance"])
        print("  %-8s origins %-26s spawn homes %s"
              % (tag, st.get("depots") or [st["origin"]],
                 dict(sorted(home_hist.items()))))
        for k in sorted(by_target):
            print("           depot %d: %4d trips, mean return distance %.1f"
                  % (k, by_target[k], statistics.mean(dist_by_target[k])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True,
                    choices=("identity", "outcomes", "mechanism", "stranded",
                             "exposure", "depots"))
    ap.add_argument("--a", default="dcoff")
    ap.add_argument("--b", default="dcref")
    ap.add_argument("--sample", default="canonical",
                    choices=("canonical", "fresh", "both"))
    ap.add_argument("--stuck", type=int, default=10)
    ap.add_argument("--rtb-new-keys", dest="rtb_new_keys", action="store_true",
                    help="drop this round's three new rtb_log keys before "
                         "comparing. ONLY for a comparison against a source "
                         "that predates them (dcAref); see mode_identity.")
    args = ap.parse_args()
    {"identity": mode_identity, "outcomes": mode_outcomes,
     "mechanism": mode_mechanism, "stranded": mode_stranded,
     "exposure": mode_exposure, "depots": mode_depots}[args.mode](args)


if __name__ == "__main__":
    main()
