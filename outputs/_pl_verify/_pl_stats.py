"""Planner round Part 1: descriptive statistics quoted in planner_part1.txt, from the C13 observe
recorder data (v1 files; the simulation is identical under both recorder versions)."""
import glob, json, sys, importlib.util, collections
sys.argv = ["x", "--glob", "/nonexistent", "--variant", "e3"]
spec = importlib.util.spec_from_file_location("off", "/home/user/SAS/outputs/_pl_verify/_pl_offline.py")
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    off = importlib.util.module_from_spec(spec); spec.loader.exec_module(off)
conf = collections.defaultdict(list); first_trig = []; last_trig = []; nosearch = []; nosearch_m = []
for p in sorted(glob.glob("/home/user/SAS/outputs/_pl_verify/_pl_v_observe_*.json")):
    d = json.load(open(p)); tag = "%s/%s" % (d["label"], d["seed"])
    berths = off.berths_for("half" if d["label"].endswith("/half") else "default")
    seen = {}
    ns = nsm = 0
    for s in d["shadow"]:
        if s["step"] in (1, 2, 10, 20, 30):
            conf[s["step"]].append(round(float(s.get("role_conf") or 0.0), 4))
        for u in s["uav"]:
            if (u["rtb"] or u["dock"]) and u["id"] not in seen:
                seen[u["id"]] = s["step"] - 1          # pre-move record: trigger was the step before
        if not any(u["role"] == "victim_searcher" and not u["rtb"] and not u["dock"] for u in s["uav"]):
            ns += 1
        if not any(u["role"] == "victim_searcher" and not u["rtb"] and not u["dock"]
                   and u["batt"] - off.rtb_trigger(u, berths) > 3.0 for u in s["uav"]):
            nsm += 1
    if seen:
        first_trig.append(min(seen.values())); last_trig.append(max(seen.values()))
    nosearch.append(ns); nosearch_m.append(nsm)
for k in sorted(conf):
    v = sorted(conf[k]); print("role-option confidence at step %d: min %.3f max %.3f  values %s" % (k, v[0], v[-1], collections.Counter(v).most_common(4)))
print("first RTB trigger per run: %d-%d ; last: %d-%d" % (min(first_trig), max(first_trig), min(last_trig), max(last_trig)))
print("steps with no available searcher per run (not returning/docked): %d-%d %s" % (min(nosearch), max(nosearch), nosearch))
print("  ... with the I1 margin too: %d-%d" % (min(nosearch_m), max(nosearch_m)))
d = json.load(open("/home/user/SAS/outputs/_pl_verify/_pl_v_observe_east_half_101.json"))
for s in d["shadow"]:
    if s["step"] in (30, 31):
        print("east/half/101 pre-move record of step %d: believed B=%d ground-truth burning=%d" % (s["step"], s["B"], s["gtB"]))
