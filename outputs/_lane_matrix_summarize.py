"""Summarize outputs/lane_matrix/*.json into the PART 2 #4 table."""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "outputs/lane_matrix"
ORDER = [("C", w) for w in ("east", "west", "north", "south")] + \
        [("D", w) for w in ("east", "west", "north", "south")]


def mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def main():
    files = {}
    for p in glob.glob(os.path.join(BASE, "*.json")):
        tag = os.path.splitext(os.path.basename(p))[0]
        with open(p, encoding="utf-8") as fh:
            files[tag] = json.load(fh)

    print("PER-COMBO SUMMARY (5 seeds each, 240 steps)")
    print("")
    hdr = ("  combo       resc  dead  unre  nd   | lane obs_frac (mean)      "
           "spread | lane-compliance (mean)   | id_chg")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    all_spreads = []
    total_id_changes = 0
    for sc, w in ORDER:
        tag = "%s_%s" % (sc, w)
        rows = files.get(tag)
        if not rows:
            print("  %-11s <not finished>" % tag)
            continue
        uids = sorted(rows[0]["lane_final"].keys())
        fr = {u: [r["lane_final"][u]["obs_frac"] for r in rows if u in r["lane_final"]]
              for u in uids}
        comp = {u: [r["lane_compliance"][u] for r in rows if u in r["lane_compliance"]]
                for u in uids}
        spreads = []
        for r in rows:
            vals = [v["obs_frac"] for v in r["lane_final"].values()]
            spreads.append(max(vals) - min(vals))
        all_spreads.extend(spreads)
        idc = sum(len(r["id_change_events"]) for r in rows)
        total_id_changes += idc
        print("  %-11s %4.1f  %4.1f  %4.1f  %3.1f | %-24s %6.3f | %-24s | %d"
              % (tag,
                 mean([r["rescued"] for r in rows]),
                 mean([r["dead"] for r in rows]),
                 mean([r["unreachable"] for r in rows]),
                 mean([r["never_detected"] for r in rows]),
                 " ".join("%s=%.3f" % (u, mean(fr[u])) for u in uids),
                 mean(spreads),
                 " ".join("%s=%.2f" % (u, mean(comp[u])) for u in uids),
                 idc))

    print("")
    print("  mean per-run lane obs_frac SPREAD (max-min) across all combos: %.4f"
          % mean(all_spreads))
    print("  max  per-run lane obs_frac SPREAD observed:                    %.4f"
          % (max(all_spreads) if all_spreads else float("nan")))
    print("  runs with any mid-run searcher-id / lane change:               %d"
          % total_id_changes)

    # worst-imbalance runs
    worst = []
    for tag, rows in files.items():
        for r in rows:
            vals = {u: v["obs_frac"] for u, v in r["lane_final"].items()}
            if len(vals) < 2:
                continue
            worst.append((max(vals.values()) - min(vals.values()), tag, r["seed"], vals))
    worst.sort(reverse=True)
    print("")
    print("WORST PER-RUN LANE IMBALANCE (the work-stealing signature)")
    for spread, tag, seed, vals in worst[:10]:
        print("   spread=%.3f  %s seed=%d  %s"
              % (spread, tag, seed, {u: round(v, 3) for u, v in vals.items()}))

    # checkpoint trajectory of imbalance
    print("")
    print("LANE UNCERTAINTY IMBALANCE OVER TIME (mean |lane_a - lane_b| uncertain_frac)")
    for sc, w in ORDER:
        tag = "%s_%s" % (sc, w)
        rows = files.get(tag)
        if not rows:
            continue
        line = []
        for t in (40, 120, 200):
            gaps = []
            for r in rows:
                cp = next((c for c in r["checkpoints"] if c["step"] == t), None)
                if not cp:
                    continue
                vals = [v["uncertain_frac"] for v in cp["lanes"].values()]
                if len(vals) >= 2:
                    gaps.append(max(vals) - min(vals))
            line.append("t%d=%.3f" % (t, mean(gaps)))
        print("   %-11s %s" % (tag, "  ".join(line)))

    # never_detected attribution
    print("")
    print("never_detected VICTIM ATTRIBUTION PER LANE")
    nd_any = False
    for tag, rows in files.items():
        for r in rows:
            # unreachable_causes is "vid:cause;vid:cause" from _build_evaluation
            causes = {}
            for part in str(r.get("unreachable_causes") or "").split(";"):
                if ":" in part:
                    vid, _, c = part.partition(":")
                    causes[vid.strip()] = c.strip()
            for v in r["victims"]:
                cause = v["cause"] or causes.get(v["victim_id"], "")
                if cause == "never_detected":
                    nd_any = True
                    print("   %s seed=%s %s pos=%s lane_owner=%s"
                          % (tag, r["seed"], v["victim_id"], v["pos"], v["lanes"]))
    if not nd_any:
        print("   none - never_detected was 0 on every run in this matrix")

    print("")
    print("ALL non-terminal / unreachable OUTCOMES BY LANE (broader than never_detected)")
    seen_any = False
    for sc, w in ORDER:
        tag = "%s_%s" % (sc, w)
        rows = files.get(tag)
        if not rows:
            continue
        per_lane = {}
        for r in rows:
            causes = {}
            for part in str(r.get("unreachable_causes") or "").split(";"):
                if ":" in part:
                    vid, _, c = part.partition(":")
                    causes[vid.strip()] = c.strip()
            for v in r["victims"]:
                owner = ",".join(v["lanes"]) or "-"
                d = per_lane.setdefault(owner, {})
                key = v["status"]
                if v["status"] == "unreachable":
                    key = "unreachable:" + (v["cause"] or causes.get(v["victim_id"], "?"))
                d[key] = d.get(key, 0) + 1
        if per_lane:
            seen_any = True
            print("   %-11s %s" % (tag, {k: dict(sorted(v.items()))
                                         for k, v in sorted(per_lane.items())}))
    if not seen_any:
        print("   (no data)")

    print("")
    print("VICTIM PLACEMENT VS THE LANE SPLIT (deterministic ring, same every seed)")
    for sc in ("C", "D"):
        for w in ("east", "north"):
            tag = "%s_%s" % (sc, w)
            rows = files.get(tag)
            if not rows:
                continue
            r = rows[0]
            print("   %-8s lanes=%s" % (
                tag, {u: "%s[%d..%d]" % tuple(v) for u, v in r["lanes_t0"].items()}))
            for v in r["victims"]:
                print("        %-10s pos=%-14s owner=%s status=%s"
                      % (v["victim_id"], v["pos"], v["lanes"], v["status"]))
            break


if __name__ == "__main__":
    main()
