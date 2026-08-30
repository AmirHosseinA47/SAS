"""Summarise a _rblatch_trace_*.json: what happened to the unit after the latch."""
import json, sys, collections

for path in sys.argv[1:]:
    d = json.load(open(path))
    tr = d["trace"]
    unit = d["unit"]
    print("=" * 78)
    print("%s  seed=%s  unit=%s  eval=%s" % (
        d["tag"], d["seed"], unit,
        {k: d["eval"].get(k) for k in ("rescued", "dead", "firefighter_deaths")}))
    print("marks:", d["marks"])
    print("-" * 78)
    print("STATE TRANSITIONS (status / assigned / target / dead):")
    for e in d["events"]:
        print("  step %3d  %-14s assigned=%-5s target=%-10s dead=%-5s pos=%s"
              % (e["step"], e["status"], e["assigned"], e["target_pos"],
                 e["dead"], e["pos"]))
    # find latch onset
    onset = None
    for r in tr:
        if r["status"] == "route_blocked":
            onset = r["step"]; break
    print("-" * 78)
    if onset is None:
        print("unit never entered route_blocked")
        continue
    after = [r for r in tr if r["step"] >= onset]
    print("LATCH ONSET step %d ; %d trace rows to end of run" % (onset, len(after)))
    moved = sum(1 for i in range(1, len(after))
                if after[i]["pos"] != after[i-1]["pos"])
    print("  distinct positions after onset : %d" % len({tuple(r["pos"] or ()) for r in after}))
    print("  steps where the unit MOVED     : %d" % moved)
    print("  ever dead                      : %s" % any(r["dead"] for r in after))
    print("  ever left route_blocked        : %s"
          % any(r["status"] != "route_blocked" for r in after))
    print("  ever re-assigned               : %s" % any(r["assigned"] for r in after))
    reach = [r for r in after if (r["victims_reachable"] or 0) > 0]
    print("  steps with >=1 REACHABLE victim: %d / %d" % (len(reach), len(after)))
    if reach:
        print("  FIRST recovery opportunity     : step %d (reachable=%s)"
              % (reach[0]["step"], reach[0]["reachable_ids"]))
        print("  LAST  recovery opportunity     : step %d" % reach[-1]["step"])
    nf = [r["nearest_fire"] for r in after if r["nearest_fire"] is not None]
    if nf:
        print("  nearest-fire dist  min/med/max : %s / %s / %s"
              % (min(nf), sorted(nf)[len(nf)//2], max(nf)))
    print("-" * 78)
    print("PER-STEP (every 5th step + all transitions), from onset:")
    hdr = "  step   pos        status        asgn tgt        nfire  pend reach  reachable"
    print(hdr)
    prev_reach = None
    for r in after:
        show = (r["step"] % 5 == 0 or r["step"] in (onset, after[-1]["step"])
                or r["victims_reachable"] != prev_reach)
        prev_reach = r["victims_reachable"]
        if not show:
            continue
        print("  %4d  %-10s %-13s %-4s %-10s %-6s %-4s %-5s %s"
              % (r["step"], r["pos"], r["status"], r["assigned"],
                 r["target_pos"], r["nearest_fire"], r["victims_pending"],
                 r["victims_reachable"], r["reachable_ids"]))
