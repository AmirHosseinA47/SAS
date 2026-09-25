import json, collections, os
HERE = "E:/Projects/SAS/outputs"
for n in ["_ffr_uhD_east_half_1291443119.json", "_ffr_uhC_east_half_1291443119.json", "_ffr_f2cDRY_east_def_101.json"]:
    with open(os.path.join(HERE, n), encoding="utf-8") as f:
        d = json.load(f)
    print("==", n, "keys:", sorted(d.keys())[:80])
    print("  wind/roles/seed/steps:", d.get("wind"), d.get("roles"), d.get("seed"), d.get("steps"), len(d.get("ff_steps") or []))
    print("  exit_starts:", d.get("exit_starts"))
    print("  completions:", d.get("completions"))
    print("  unassigns:", d.get("unassigns"))
    print("  unreachable_marks:", d.get("unreachable_marks"))
    print("  unassign reasons:", collections.Counter(u.get("reason") for u in d.get("unassigns") or []))
    fs = d["ff_steps"]
    print("  ff_steps[0]:", fs[0])
    print("  victim_steps[0]:", d["victim_steps"][0])
    print("  ff_bind_steps[0]:", (d.get("ff_bind_steps") or [None])[0])
