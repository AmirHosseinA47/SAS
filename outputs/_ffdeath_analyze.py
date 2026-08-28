import json, sys, collections, os

for path in sys.argv[1:]:
    d = json.load(open(path))
    print("=" * 78)
    print("%s  scenario %s / wind %s  seeds=%s steps=%s"
          % (os.path.basename(path), d["scenario"], d["wind"], d["seeds"], d["steps"]))
    ev = d["dispatches"]
    deaths = d["deaths"]
    print("dispatch decisions (action=assign): %d" % len(ev))
    print("firefighter deaths: %d" % len(deaths))
    print()
    print("--- per dispatch ---")
    print("%-6s %-5s %-8s %-6s %-5s %-6s %-7s %-5s %-6s %-6s"
          % ("seed", "step", "victim", "ff", "man", "bfs", "detour", "pool", "clrAlt", "betterAlt"))
    for e in ev:
        print("%-6s %-5s %-8s %-6s %-5s %-6s %-7s %-5s %-6s %-6s"
              % (e["seed"], e["step"], e["victim_id"], e["ff_id"], e["manhattan"],
                 e["bfs"], e["detour"], e["pool_size"], e["n_clear_alternatives"],
                 e["n_strictly_better_alt"]))
    n_no_path = sum(1 for e in ev if e["bfs"] is None)
    n_detour = sum(1 for e in ev if e["bfs"] is not None and e["detour"] > 0)
    print()
    print("dispatches with NO live path at dispatch time : %d / %d" % (n_no_path, len(ev)))
    print("dispatches with a path but non-zero detour    : %d / %d" % (n_detour, len(ev)))
    print("dispatches where a strictly-better-routed alt existed: %d"
          % sum(1 for e in ev if e["n_strictly_better_alt"] > 0))

    # build trace index: last known bfs per (seed,ff) before death
    tr = collections.defaultdict(dict)
    for t in d["trace"]:
        tr[(t["seed"], t["ff_id"])][t["step"]] = t["bfs"]

    print()
    print("--- deaths classified ---")
    cats = collections.Counter()
    for dd in deaths:
        key = (dd["seed"], dd["ff_id"])
        prior = [e for e in ev if e["seed"] == dd["seed"] and e["ff_id"] == dd["ff_id"]
                 and e["step"] <= dd["step"]]
        disp = prior[-1] if prior else None
        steps_en_route = tr[key]
        blocked_steps = sorted(s for s, v in steps_en_route.items()
                               if v is None and s <= dd["step"])
        if disp is None:
            cat = "c: died with no assign dispatch on record (never dispatched / idle)"
        elif disp["bfs"] is None:
            cat = "a: dispatched with NO live path"
        elif blocked_steps and blocked_steps[0] > disp["step"]:
            cat = "b: path clear at dispatch, fire closed route at step %d" % blocked_steps[0]
        elif not steps_en_route:
            cat = "c: died but never observed en route (no target_pos)"
        else:
            cat = "b: path clear at dispatch and stayed reachable; fire reached its cell"
        cats[cat.split(":")[0]] += 1
        print("seed %-5s step %-4s ff %-6s pos %-9s target=%s exiting=%s | dispatch %s | %s"
              % (dd["seed"], dd["step"], dd["ff_id"], dd["pos"], dd["had_target"],
                 dd["exiting"],
                 ("step %s man=%s bfs=%s" % (disp["step"], disp["manhattan"], disp["bfs"]))
                 if disp else "none",
                 cat))
    print()
    print("category counts:", dict(cats))
    print()
    print("route_blocked firings:", len(d["route_blocked_fires"]), d["route_blocked_fires"][:5])
    print("move stats:", d["move_stats"])
