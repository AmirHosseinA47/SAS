import json, sys
src, dst = sys.argv[1], sys.argv[2]
labels, results = {}, {}
for line in open(src, encoding="utf-8"):
    d = json.loads(line)
    if d.get("type") == "started":
        labels[d["agentId"]] = d.get("label")
    elif d.get("type") == "result":
        results[d["agentId"]] = d["result"]
by_label = {labels[a]: r for a, r in results.items()}
out = []
tot = {}
for lab in sorted(l for l in by_label if l.startswith("critic:")):
    lens = lab.split(":", 1)[1]
    r = by_label[lab]
    if isinstance(r, str):
        r = json.loads(r)
    out.append("#" * 100)
    out.append("LENS %s   quarantine: %s" % (lens, r.get("quarantine_contact")))
    for f in r["findings"]:
        if f["severity"] == "low":
            out.append("-" * 60)
            out.append("[%s] LOW %s sec %s: %s || FIX: %s" % (lens, f["id"], f["section"], f["claim"], f["fix"]))
            continue
        v = by_label.get("verify:%s:%s" % (lens, f["id"]))
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                v = {"verdict": "?", "reasoning": v, "corrected_fix": ""}
        v = v or {"verdict": "MISSING", "reasoning": "", "corrected_fix": ""}
        tot[v.get("verdict")] = tot.get(v.get("verdict"), 0) + 1
        out.append("=" * 100)
        out.append("[%s] %s %s sec %s VERDICT %s" % (lens, f["id"], f["severity"], f["section"], v.get("verdict")))
        out.append("CLAIM: " + f["claim"])
        out.append("EVIDENCE: " + f["evidence"])
        out.append("FIX(reviewer): " + f["fix"])
        out.append("VERIFIER: " + v.get("reasoning", ""))
        out.append("FIX(verified): " + v.get("corrected_fix", ""))
out.append("TOTALS %s" % tot)
open(dst, "w", encoding="utf-8").write("\n".join(out))
print(tot)
