"""Planner round Part 1, section 4.2: the real would-win states under the exact design (e3x,
confidence 1.0), per run and direction, with the demands - and the direction census."""
import collections, contextlib, glob, importlib.util, io, json, sys
sys.argv = ["x", "--glob", "/nonexistent", "--variant", "e3x"]
spec = importlib.util.spec_from_file_location("off", "/home/user/SAS/outputs/_pl_verify/_pl_offline.py")
with contextlib.redirect_stdout(io.StringIO()):
    off = importlib.util.module_from_spec(spec); spec.loader.exec_module(off)
census = collections.Counter()
for p in sorted(glob.glob("/home/user/SAS/outputs/_pl_verify/_pl_v2_observe_*.json")):
    d = json.load(open(p)); tag = "%s/%s" % (d["label"][2:], d["seed"])
    berths = off.berths_for("half" if d["label"].endswith("/half") else "default")
    shown = set()
    for s in d["shadow"]:
        if s.get("base") is None:
            continue
        D = off.demands(s)
        flagged = {e for t in s.get("instab", []) for e in t[1]}
        avail = [u for u in s["uav"] if not u["rtb"] and not u["dock"]
                 and u["batt"] - off.rtb_trigger(u, berths) > off.H_STEPS * off.E_MOVE and u["id"] not in flagged]
        n_av = collections.Counter(u["role"] for u in avail)
        n = collections.Counter(u["role"] for u in s["uav"])
        best = None
        for u in avail:
            b = off.VS if u["role"] == off.FT else off.FT
            if n_av[u["role"]] <= 1:
                continue
            v = off.values(s, u, b, D, n, off.rtb_trigger(u, berths), berths)
            sc, ev = off.score(v, u, b, s["mode"], 1.0)
            if best is None or sc > best[0]:
                best = (sc, u["id"], b, v)
        if not best or best[0] <= s["base"]:
            continue
        direction = "to_search" if best[2] == off.VS else "to_tracking"
        census[(direction, "victims_undetected" if D["vict"] > 0 else "all_detected")] += 1
        if direction not in shown:
            shown.add(direction)
            print("%-17s step %3d %-26s %s -> %-16s score %.3f vs baseline %.3f" % (
                tag, s["step"], s["mode"], best[1], best[2], best[0], s["base"]))
            print("   demands fire %.3f vict %.3f unc %.3f stale %.3f | B %d stale %d | values %s" % (
                D["fire"], D["vict"], D["unc"], D["stale"], s["B"], s["B_status"].get("stale_information", 0),
                {k.split("_")[0]: round(x, 3) for k, x in best[3].items()}))
print("DIRECTION CENSUS of would-win steps:", dict(census))
