"""Timeline extractor for the seed-808 latch diagnosis. Read-only over the
JSON traces produced by _l808_trace.py."""
import json, sys, collections

path = sys.argv[1]
d = json.load(open(path))
tr = d["trace"]
ev = d["events"]
print("== %s  mode=%s seed=%s wind=%s terminal_step=%s ==" % (
    path, d.get("mode"), d.get("seed"), d.get("wind"), d.get("terminal_step")))
e = d.get("eval", {})
print("   eval: rescued=%s dead=%s never_detected=%s ffdeaths=%s" % (
    e.get("rescued"), e.get("dead"), e.get("never_detected"), e.get("firefighter_deaths")))

# ---- victim liveness timeline -------------------------------------------
live_by_step = []
for i, t in enumerate(tr, start=1):
    live = [v["id"] for v in t["victims"] if v.get("needs")]
    live_by_step.append((i, live))
last_live = None
for i, live in live_by_step:
    if live:
        last_live = i
print("   last step with a live victim needing rescue: %s" % last_live)
# victim terminal steps
vfirst_term = {}
for i, t in enumerate(tr, start=1):
    for v in t["victims"]:
        if not v.get("needs") and v["id"] not in vfirst_term:
            vfirst_term[v["id"]] = (i, v.get("status"))
print("   victim first-terminal steps: %s" % json.dumps(vfirst_term))

# ---- firefighter status timeline ----------------------------------------
for ff_idx in range(len(tr[0]["ff"])):
    uid = tr[0]["ff"][ff_idx]["id"]
    print("\n-- %s --" % uid)
    prev = None
    runs = []
    for i, t in enumerate(tr, start=1):
        f = t["ff"][ff_idx]
        key = (f["status"], f["assigned"], f["exiting"], f["dead"],
               tuple(f["target"]) if f["target"] else None,
               f["bound"])
        if key != prev:
            runs.append((i, f))
            prev = key
    for i, f in runs:
        print("   s%-4d pos=%-9s status=%-14s assigned=%-5s exiting=%-5s target=%-9s bound=%s" % (
            i, f["pos"], f["status"], f["assigned"], f["exiting"],
            f["target"], f["bound"]))
    # first step it became route_blocked and never left it
    final = tr[-1]["ff"][ff_idx]
    if final["status"] == "route_blocked" and not final["dead"]:
        latch_from = None
        for i in range(len(tr), 0, -1):
            if tr[i - 1]["ff"][ff_idx]["status"] == "route_blocked":
                latch_from = i
            else:
                break
        print("   >> LATCHED continuously from step %s to %s (%d steps)" % (
            latch_from, len(tr), len(tr) - latch_from + 1))
        print("   >> at latch onset s%s: assigned=%s target=%s bound=%s" % (
            latch_from, tr[latch_from - 1]["ff"][ff_idx]["assigned"],
            tr[latch_from - 1]["ff"][ff_idx]["target"],
            tr[latch_from - 1]["ff"][ff_idx]["bound"]))
        live_at = [v["id"] for v in tr[latch_from - 1]["victims"] if v.get("needs")]
        print("   >> live victims at latch onset: %s" % live_at)
        # how many steps of the latch had a live victim present
        with_live = sum(1 for i in range(latch_from, len(tr) + 1)
                        if any(v.get("needs") for v in tr[i - 1]["victims"]))
        print("   >> steps of the latch with >=1 live victim: %d  (without: %d)" % (
            with_live, (len(tr) - latch_from + 1) - with_live))
        # unassigned+live-victim window = when the revalidation pass could act
        actionable = [i for i in range(latch_from, len(tr) + 1)
                      if any(v.get("needs") for v in tr[i - 1]["victims"])
                      and not tr[i - 1]["ff"][ff_idx]["assigned"]
                      and not tr[i - 1]["ff"][ff_idx]["exiting"]]
        print("   >> steps where the pass COULD have acted (unassigned & live victim): %d %s" % (
            len(actionable), actionable[:20]))

print("\n== events ==")
for x in ev:
    print("   " + json.dumps(x))
