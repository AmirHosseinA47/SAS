import json, os
from collections import defaultdict, Counter

SCRATCH = os.path.dirname(os.path.abspath(__file__))
res = json.load(open(os.path.join(SCRATCH, "scan_c.json"), encoding="utf-8"))
rows = res["rows"]
print("markings", len(rows), "skipped", res["skipped"][:5])
print("has_bind False markings:", sum(1 for r in rows if not r["has_bind"]),
      "files:", sorted({r["file"] for r in rows if not r["has_bind"]}))
print("class counts (all markings):", Counter(r["class"] for r in rows))
print("recon_geo_reachable (should be False):", Counter(str(r["recon_geo_reachable"]) for r in rows))
print("starts_empty by class:", Counter((r["class"], r["starts_empty"]) for r in rows))

groups = defaultdict(list)
for r in rows:
    groups[(r["wind"], r["roles"], r["seed"], r["victim"], r["step"])].append(r)
print("distinct (wind,roles,seed,victim,step):", len(groups))
dc = Counter()
for k, g in groups.items():
    classes = {r["class"] for r in g}
    dc[tuple(sorted(classes))] += 1
print("distinct by class:", dc)
dse = Counter()
for k, g in groups.items():
    dse[(g[0]["class"], g[0]["starts_empty"])] += 1
print("distinct by (class, starts_empty):", dse)

print("\n=== CUSTODY markings ===")
for k, g in sorted(groups.items()):
    if not any(r["class"] == "custody" for r in g):
        continue
    for r in g:
        print(json.dumps({x: r[x] for x in ("tag", "wind", "roles", "seed", "victim", "step", "streak", "carriers",
                                            "pickup_same_step", "unassigned_ff", "living_at_bfs", "starts_empty",
                                            "victim_cell", "co_marked", "final_victim", "victim_death_step",
                                            "steps_run", "carrier_info", "eval_rescued")}))

print("\n=== APPROACH markings ===")
for k, g in sorted(groups.items()):
    if not any(r["class"] == "approach" for r in g):
        continue
    r = g[0]
    print(k, "tags", [x["tag"] for x in g], "approachers", r["approachers"], "unassigned", r["unassigned_ff"],
          "living", r["living_at_bfs"], "starts_empty", r["starts_empty"], "final", r["final_victim"],
          "death", r["victim_death_step"])

print("\n=== UNBOUND markings, starts_empty True (distinct) ===")
n = 0
for k, g in sorted(groups.items()):
    r = g[0]
    if r["class"] == "unbound" and r["starts_empty"]:
        n += 1
        print(k, "tags", [x["tag"] for x in g], "living", r["living_at_bfs"], "final", r["final_victim"],
              "co_marked", r["co_marked"])
print("count", n)
