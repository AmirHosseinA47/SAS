"""Base-station round: kill-switch identity, and the mechanism report.

Two jobs, both read-only over harness JSON:

  --mode identity   compare a BASE_STATION_MODE=0 arm against a 16b2da8 checkout
                    arm on every recorded field. This is the kill-switch gate:
                    anything that differs means the "off" path is not the
                    pre-feature code. Uses the same field list as
                    outputs/_vm_analyze.py, plus the base-station additions,
                    minus the uav_steps columns the round itself added (a mode-0
                    arm has battery "" and base_state "" on both sides, so they
                    are compared, not skipped - see UAV_STEP_NOTE).

  --mode mechanism  the Part 3 mechanism table for an armed arm: return trips,
                    how long each took, how far the UAV was, who arrived and who
                    did not, steps spent charging, and every lane/sector
                    reshuffle attributable to a charging transition.

usage:
  _bs_identity.py --mode identity  --a ksoff --b ksbase [--sample canonical|fresh]
  _bs_identity.py --mode mechanism --a bsfull [--sample canonical]
"""
from __future__ import annotations

import argparse
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

CANONICAL = (
    [("east", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("east", "default", s) for s in (101, 202, 303)]
)
FRESH = (
    [("east", "half", s) for s in (606, 707, 808, 909, 1010)]
    + [("south", "half", s) for s in (606, 707, 808, 909, 1010)]
)

# Every recorded field the kill switch must reproduce exactly. The first block is
# outputs/_vm_analyze.py's list verbatim; the second is what this round added.
IDENTITY_FIELDS = (
    "eval", "fire_digests", "ff_steps", "completions", "recycles", "assigns",
    "unassigns", "unreachable_marks", "planner", "recycle_to_next_assign",
    "idle", "absence_log", "absence_counters", "unreachable_escape_log",
    "rescue_event_counts", "rescue_failed", "terminal_step",
    "pending_removal_failures_total", "leftover_pending", "stdout_sha256",
    "first_burn_step", "fire_ground_final",
    # base-station round. uav_steps now carries battery and base_state columns;
    # on a mode-0 arm those are the untouched drain and "" respectively, so they
    # are still a valid identity field and are deliberately NOT excused.
    "uav_steps", "victim_steps", "victim_flee_log", "base_station", "rtb_log",
)


def _name(tag, wind, roles, seed):
    rr = "def" if roles == "default" else roles
    return os.path.join(BASE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def _load(tag, combos):
    runs, missing = {}, []
    for wind, roles, seed in combos:
        path = _name(tag, wind, roles, seed)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            missing.append(os.path.basename(path))
            continue
        with open(path, "r", encoding="utf-8") as handle:
            runs[(wind, roles, seed)] = json.load(handle)
    return runs, missing


def _first_diff(a, b, path=""):
    """Locate the first difference, so a failure names a step, not just a field."""
    if type(a) is not type(b) and not (
        isinstance(a, (int, float)) and isinstance(b, (int, float))
    ):
        return "%s: type %s vs %s" % (path or "<root>", type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b), key=str):
            if key not in a:
                return "%s.%s: missing on A" % (path, key)
            if key not in b:
                return "%s.%s: missing on B" % (path, key)
            found = _first_diff(a[key], b[key], "%s.%s" % (path, key))
            if found:
                return found
        return ""
    if isinstance(a, list):
        if len(a) != len(b):
            return "%s: length %d vs %d" % (path or "<root>", len(a), len(b))
        for index, (left, right) in enumerate(zip(a, b)):
            found = _first_diff(left, right, "%s[%d]" % (path, index))
            if found:
                return found
        return ""
    if a != b:
        return "%s: %r vs %r" % (path or "<root>", a, b)
    return ""


def identity(args) -> int:
    combos = FRESH if args.sample == "fresh" else CANONICAL
    a_runs, a_missing = _load(args.a, combos)
    b_runs, b_missing = _load(args.b, combos)
    print("=" * 78)
    print("KILL-SWITCH IDENTITY   %s (feature source, mode 0)  vs  %s (16b2da8)"
          % (args.a, args.b))
    print("sample: %s, %d runs" % (args.sample, len(combos)))
    print("=" * 78)
    if a_missing or b_missing:
        print("MISSING  A: %s" % (", ".join(a_missing) or "none"))
        print("MISSING  B: %s" % (", ".join(b_missing) or "none"))
    identical = 0
    for key in combos:
        if key not in a_runs or key not in b_runs:
            print("  %-22s SKIPPED (missing)" % (str(key),))
            continue
        run_a, run_b = a_runs[key], b_runs[key]
        diffs = []
        for field in IDENTITY_FIELDS:
            found = _first_diff(run_a.get(field), run_b.get(field), field)
            if found:
                diffs.append(found)
        label = "%s/%s/%d" % key
        if not diffs:
            identical += 1
            print("  %-22s IDENTICAL on all %d fields" % (label, len(IDENTITY_FIELDS)))
        else:
            print("  %-22s DIFFERS on %d field(s)" % (label, len(diffs)))
            for line in diffs[:4]:
                print("       %s" % line[:200])
    print("-" * 78)
    print("RESULT: %d/%d runs byte-identical" % (identical, len(combos)))
    print("GATE:   %s" % ("PASS" if identical == len(combos) else "FAIL"))
    return 0 if identical == len(combos) else 1


def mechanism(args) -> int:
    combos = FRESH if args.sample == "fresh" else CANONICAL
    runs, missing = _load(args.a, combos)
    print("=" * 78)
    print("BASE-STATION MECHANISM REPORT   arm=%s   sample=%s" % (args.a, args.sample))
    print("=" * 78)
    if missing:
        print("MISSING: %s" % ", ".join(missing))

    trips = arrived = stranded = 0
    return_steps = charge_steps = 0
    durations, distances, arrival_levels = [], [], []
    zero_battery_outside = []
    reshuffles = mid_traverse = 0
    lane_changes = sector_changes = 0
    charging_attributable = []
    roster_changes = []

    for key in combos:
        run = runs.get(key)
        if run is None:
            continue
        label = "%s/%s/%d" % key
        for uav_id, log in sorted((run.get("rtb_log") or {}).items()):
            for trip in log:
                trips += 1
                distances.append(int(trip.get("trigger_distance") or 0))
                if trip.get("arrival_step") is not None:
                    arrived += 1
                    durations.append(
                        int(trip["arrival_step"]) - int(trip["trigger_step"])
                    )
                    arrival_levels.append(float(trip.get("arrival_level") or 0.0))
                else:
                    stranded += 1
                    print("  UNARRIVED  %-18s uav %s trigger_step=%s level=%.1f dist=%s"
                          % (label, uav_id, trip.get("trigger_step"),
                             float(trip.get("trigger_level") or 0.0),
                             trip.get("trigger_distance")))
        for uav_id, counters in sorted((run.get("rtb_counters") or {}).items()):
            return_steps += int(counters.get("return_steps") or 0)
            charge_steps += int(counters.get("charge_steps") or 0)

        # A UAV at zero battery that is not docked is a stranded UAV. uav_steps
        # rows are [id, cell, role, selected_dir, battery, base_state].
        for step_index, row in enumerate(run.get("uav_steps") or []):
            for entry in row:
                if len(entry) < 6:
                    continue
                if float(entry[4]) <= 0.0 and entry[5] not in ("charging", "docked"):
                    zero_battery_outside.append((label, entry[0], step_index + 1))
                    break

        # Partition churn. A change is counted when a UAV's lane or sector tuple
        # differs from the previous step, or when the searcher roster itself
        # changes. "charging-attributable" means some UAV's base_state changed on
        # that same step - which is the brief's actual question, and which the
        # design predicts should be ZERO, because both rosters are role-based and
        # position-blind and a parked UAV keeps its role. "mid-traverse" means the
        # affected UAV still had an unreached target on that step.
        steps_rows = run.get("uav_steps") or []
        snapshots = run.get("partition_steps") or []
        previous = None
        previous_states = None
        for step_index, snapshot in enumerate(snapshots):
            states = {}
            if step_index < len(steps_rows):
                for entry in steps_rows[step_index]:
                    if len(entry) >= 6:
                        states[str(entry[0])] = entry[5]
            transition = previous_states is not None and states != previous_states
            if previous is not None and snapshot:
                if snapshot.get("searchers") != previous.get("searchers"):
                    roster_changes.append((label, step_index + 1,
                                           previous.get("searchers"),
                                           snapshot.get("searchers")))
                for uav_id, lane in (snapshot.get("lanes") or {}).items():
                    if (previous.get("lanes") or {}).get(uav_id) != lane:
                        lane_changes += 1
                        if transition:
                            charging_attributable.append(
                                ("lane", label, uav_id, step_index + 1))
                        if (snapshot.get("targets") or {}).get(uav_id):
                            mid_traverse += 1
                for uav_id, sector in (snapshot.get("sectors") or {}).items():
                    if (previous.get("sectors") or {}).get(uav_id) != sector:
                        sector_changes += 1
                        if transition:
                            charging_attributable.append(
                                ("sector", label, uav_id, step_index + 1))
                reshuffles = lane_changes + sector_changes
            previous = snapshot or previous
            previous_states = states

    def mean(values):
        return (sum(values) / len(values)) if values else 0.0

    print()
    print("  return trips fired                 %d" % trips)
    print("  ... reached the depot              %d" % arrived)
    print("  ... still en route at the horizon   %d" % stranded)
    print("  mean trip duration (steps)         %.1f" % mean(durations))
    print("  mean distance at trigger (cells)   %.1f" % mean(distances))
    print("  mean battery on arrival            %.1f" % mean(arrival_levels))
    print("  total steps spent returning        %d" % return_steps)
    print("  total steps spent charging         %d" % charge_steps)
    print()
    print("  UAVs at zero battery outside depot %d %s"
          % (len(zero_battery_outside), zero_battery_outside[:5] or ""))
    # Sectors are recomputed every step from the fire's bounding box, so a large
    # sector-change count is the BASELINE's normal behaviour and says nothing
    # about this feature. Lanes only move when the searcher roster changes, which
    # is the thing the brief is actually asking about, and the roster is
    # role-based and position-blind - so the design predicts zero.
    print("  searcher LANE changes              %d" % lane_changes)
    print("  ... of those, mid-traverse         %d" % mid_traverse)
    print("  tracker SECTOR changes             %d   (recomputed every step from"
          % sector_changes)
    print("                                         the fire bbox - baseline churn)")
    print("  searcher ROSTER changes            %d %s"
          % (len(roster_changes), roster_changes[:3] or ""))
    print("  changes coinciding with a")
    print("      base-state transition          %d %s"
          % (len(charging_attributable), charging_attributable[:5] or ""))
    print()
    print("  GATE no-stranding: %s"
          % ("PASS" if not zero_battery_outside else "FAIL"))
    return 0


OUTCOME_KEYS = (
    "rescued", "dead", "never_detected", "unreachable", "geographically_isolated",
    "horizon_unresolved", "candidate", "firefighter_deaths", "burnt_cells",
)


def outcomes(args) -> int:
    """Seed-matched outcome table across the arm ladder.

    Each arm is compared against the arm one rung BELOW it, so a difference
    attributes to exactly one increment - that is the whole point of making
    BASE_STATION_MODE an ordinal ladder whose levels are strict supersets.
    """
    combos = FRESH if args.sample == "fresh" else CANONICAL
    tags = [t.strip() for t in args.a.split(",") if t.strip()]
    loaded = {}
    for tag in tags:
        runs, missing = _load(tag, combos)
        loaded[tag] = runs
        if missing:
            print("MISSING %-9s %d run(s): %s" % (tag, len(missing), ", ".join(missing[:4])))
    print("=" * 78)
    print("OUTCOME LADDER   sample=%s   %d runs per arm" % (args.sample, len(combos)))
    print("=" * 78)
    print("  %-10s %s" % ("arm", " ".join("%8s" % k[:8] for k in OUTCOME_KEYS)))
    totals = {}
    for tag in tags:
        row, present = [], 0
        for key in OUTCOME_KEYS:
            total = 0
            for combo in combos:
                run = loaded[tag].get(combo)
                if run is None:
                    continue
                total += int((run.get("eval") or {}).get(key, 0) or 0)
            row.append(total)
        present = len(loaded[tag])
        totals[tag] = row
        print("  %-10s %s   (%d/%d runs)"
              % (tag, " ".join("%8d" % v for v in row), present, len(combos)))
    print()
    print("  INCREMENTS (each arm minus the one above it in this list)")
    for index in range(1, len(tags)):
        prev_tag, tag = tags[index - 1], tags[index]
        delta = [b - a for a, b in zip(totals[prev_tag], totals[tag])]
        print("  %-10s %s"
              % ("%s-%s" % (tag[:4], prev_tag[:4]),
                 " ".join(("%+8d" % v) if v else "%8s" % "." for v in delta)))
    print()
    print("  PER-SEED rescued / never_detected, first vs last arm")
    if len(tags) >= 2:
        first, last = tags[0], tags[-1]
        for combo in combos:
            run_a = loaded[first].get(combo)
            run_b = loaded[last].get(combo)
            if run_a is None or run_b is None:
                continue
            ea, eb = run_a.get("eval") or {}, run_b.get("eval") or {}
            mark = "" if (ea.get("rescued") == eb.get("rescued")
                          and ea.get("never_detected") == eb.get("never_detected")) else "  <-- changed"
            print("    %-18s rescued %d -> %d   never_detected %d -> %d%s"
                  % ("%s/%s/%d" % combo, ea.get("rescued", 0), eb.get("rescued", 0),
                     ea.get("never_detected", 0), eb.get("never_detected", 0), mark))
    return 0


def exposure(args) -> int:
    """UAV action-label mix and fire exposure per arm.

    uav_actions rows are [uav_id, action_label, burning, smoke_a, smoke_b,
    dist_to_nearest_fire] - recorded by the interior-hazard round. Two jobs here:

      1. the corner spawn puts every UAV at boundary distance <= 4 from step 0,
         which is expected to shift the searcher label mix toward the
         interior-retarget branch. This measures that instead of inferring it
         from a test threshold.
      2. mechanism 1 keeps the fire, smoke and hard-safety filters and mechanism 2
         is fire-blind by construction. The burning/smoke columns are what makes
         that difference visible rather than merely asserted.
    """
    combos = FRESH if args.sample == "fresh" else CANONICAL
    tags = [t.strip() for t in args.a.split(",") if t.strip()]
    print("=" * 78)
    print("ACTION MIX AND FIRE EXPOSURE   sample=%s" % args.sample)
    print("=" * 78)
    for tag in tags:
        runs, missing = _load(tag, combos)
        if missing:
            print("  MISSING %-9s %d run(s)" % (tag, len(missing)))
        labels: dict[str, int] = {}
        rows = burning = smoke = 0
        dist_total = 0.0
        for run in runs.values():
            for step_row in run.get("uav_actions") or []:
                for entry in step_row:
                    if len(entry) < 6:
                        continue
                    rows += 1
                    labels[str(entry[1])] = labels.get(str(entry[1]), 0) + 1
                    burning += 1 if entry[2] else 0
                    smoke += 1 if (entry[3] or entry[4]) else 0
                    try:
                        dist_total += float(entry[5])
                    except (TypeError, ValueError):
                        pass
        if not rows:
            print("  %-9s no data" % tag)
            continue
        top = sorted(labels.items(), key=lambda kv: -kv[1])[:5]
        print("  %-9s %d uav-steps over %d runs" % (tag, rows, len(runs)))
        print("             on a BURNING cell %6d (%5.2f%%)   in SMOKE %6d (%5.2f%%)"
              % (burning, 100.0 * burning / rows, smoke, 100.0 * smoke / rows))
        print("             mean distance to nearest fire %.2f" % (dist_total / rows))
        for label, count in top:
            print("               %-52s %6d (%5.2f%%)"
                  % (label[:52], count, 100.0 * count / rows))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["identity", "mechanism", "outcomes", "exposure"],
        required=True,
    )
    parser.add_argument("--a", required=True, help="arm tag under test")
    parser.add_argument("--b", help="reference arm tag (identity mode)")
    parser.add_argument("--sample", default="canonical", choices=["canonical", "fresh"])
    args = parser.parse_args()
    if args.mode == "identity":
        if not args.b:
            parser.error("--b is required for identity mode")
        return identity(args)
    if args.mode == "outcomes":
        return outcomes(args)
    if args.mode == "exposure":
        return exposure(args)
    return mechanism(args)


if __name__ == "__main__":
    raise SystemExit(main())
