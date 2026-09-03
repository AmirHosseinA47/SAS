import json, collections, sys
a = json.load(open(sys.argv[1]))
r = a["resets"]
print("total resets", len(r))
print("by site:", dict(collections.Counter(x["site"] for x in r)))
print("by site WHERE cleared_lc:",
      dict(collections.Counter(x["site"] for x in r if x["cleared_lc"])))
mv = a["moves"]
print("moves by path:", dict(collections.Counter(m["path"] for m in mv if m["moved"])))
sv = [m for m in mv if m["path"] == "survival"]
print("survival calls", len(sv), "moved", sum(1 for m in sv if m["moved"]))
print("lc_was_cleared_pre", sum(1 for m in sv if m.get("lc_was_cleared_pre")))
print("reversal_vs_shadow", sum(1 for m in sv if m.get("reversal_vs_shadow")))
c = a["cand"]
print("cand calls", len(c), "lc_cleared_by_reset",
      sum(1 for x in c if x["lc_cleared_by_reset"]))
