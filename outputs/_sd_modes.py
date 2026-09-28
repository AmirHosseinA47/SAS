"""sysdebug Part 3/5: fail-safe mode vs active reasons vs analyzer triggers, from _sd_*.json rows.

For every run in the queue: per step the fail-safe mode, its active reasons and the analyzer
trigger counts. Reports (a) share of steps per mode, (b) for each mode, how often each reason
is present, (c) steps whose mode is non-normal and whose reasons are ALL from the three
artifact alarms named in planner_part1 11A(c) (collision, drift, communication), and
(d) per trigger type the share of steps it fires. Read-only.

usage: _sd_modes.py <queue.jsonl> [...]
"""
import collections
import json
import os
import sys

REPO = r"E:\Projects\SAS"
ARTIFACT_REASONS = {"collision_risk", "extreme_drift", "critical_communication"}


def main():
    names = []
    for q in sys.argv[1:]:
        names += [json.loads(l)["name"] for l in open(q, encoding="utf-8") if l.strip()]
    mode_steps = collections.Counter()
    reason_in_mode = collections.defaultdict(collections.Counter)
    artifact_only = collections.Counter()
    trig_steps = collections.Counter()
    total = 0
    first_nonnormal = []
    for n in names:
        p = os.path.join(REPO, "outputs", "_sd_%s.json" % n)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        for t, (dec, trig) in enumerate(zip(d["rows_dec"], d["rows_trig"]), start=1):
            total += 1
            m = dec.get("mode", "?")
            why = set(dec.get("why") or [])
            mode_steps[m] += 1
            for r in why:
                reason_in_mode[m][r] += 1
            if m != "normal" and why and why <= ARTIFACT_REASONS:
                artifact_only[m] += 1
            for k in trig:
                trig_steps[k] += 1
        fn = next((t for t, dec in enumerate(d["rows_dec"], start=1) if dec.get("mode") != "normal"), None)
        first_nonnormal.append(fn)
    print("runs=%d steps=%d" % (len(first_nonnormal), total))
    print("first non-normal step per run:", first_nonnormal)
    print("\nMODE share of steps:")
    for m, c in mode_steps.most_common():
        print("  %-24s %6d  %5.1f%%" % (m, c, 100.0 * c / total))
    print("\nREASON presence within each mode (share of that mode's steps):")
    for m, c in mode_steps.most_common():
        print("  %s:" % m)
        for r, k in reason_in_mode[m].most_common():
            print("      %-28s %6d  %5.1f%%" % (r, k, 100.0 * k / c))
    print("\nNON-NORMAL steps whose reasons are ALL artifact alarms:")
    for m, c in artifact_only.most_common():
        print("  %-24s %6d  (%.1f%% of that mode)" % (m, c, 100.0 * c / mode_steps[m]))
    print("\nTRIGGER TYPE share of steps it fires on:")
    for k, c in trig_steps.most_common():
        print("  %-32s %6d  %5.1f%%" % (k, c, 100.0 * c / total))


if __name__ == "__main__":
    main()
