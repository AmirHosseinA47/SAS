import json, os, sys
O = "E:/Projects/SAS/outputs"
names = sys.argv[1:]
for n in names:
    p = os.path.join(O, n)
    d = json.load(open(p, encoding="utf-8"))
    print(n, "| repo", d.get("repo"), "| steps", d.get("steps"), "| extra", d.get("extra_params"),
          "| fm2p", ("fm2p" in d) and (d["fm2p"] or {}).get("config"), "| uav_actions", d.get("uav_actions") is not None,
          "| nsteps", len(d.get("ff_steps") or []), "| rescued", (d.get("eval") or {}).get("rescued"))
