import json, sys
src, dst = sys.argv[1], sys.argv[2]
labels = {}
out = []
for line in open(src, encoding="utf-8"):
    d = json.loads(line)
    if d.get("type") == "started":
        labels[d["agentId"]] = d.get("label")
    if d.get("type") == "result":
        out.append("===== %s (%s)\n%s\n" % (labels.get(d["agentId"]), d["agentId"], d["result"] if isinstance(d["result"], str) else json.dumps(d["result"], indent=1)))
open(dst, "w", encoding="utf-8").write("\n".join(out))
print(len(out), "results")
