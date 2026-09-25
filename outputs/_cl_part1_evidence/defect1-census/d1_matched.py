import collections, os, pickle, re
SCR = os.path.dirname(os.path.abspath(__file__))
D = pickle.load(open(os.path.join(SCR, "d1_legs.pkl"), "rb"))
GROUPS = [["uhC", "uhD", "uhY"], ["ugKC", "ugKD", "ugKY"], ["fmOFF", "fmEFS", "fmDRY"], ["f2cOFF", "f2cEFS", "f2cDRY"]]
by_tag_file = collections.defaultdict(dict)
for n in os.listdir("E:/Projects/SAS/outputs"):
    if n == "_firemech_rewound_20260914":
        continue
    m = re.match(r"^_ffr_(.+?)_(east|south|west|north)_(half|def)_(\d+)\.json$", n)
    if m:
        by_tag_file[m.group(1)][n] = (m.group(2), m.group(3), int(m.group(4)))
occ = []
for g in GROUPS:
    common = set.intersection(*(set(by_tag_file[t].values()) for t in g))
    for t in g:
        files = {f for f, tup in by_tag_file[t].items() if tup in common}
        occ += [r for r in D["broken"] if r["tag"] == t and r["file"] in files]
print("matched-arm broken arm-occurrences:", len(occ), collections.Counter(r["cause"] for r in occ))
nh = [r for r in occ if r["cause"] != "horizon"]
print("non-horizon:", len(nh), collections.Counter(r["cause"] for r in nh))
print("  with a replacement_after_blocked unassign at the end step:", sum(1 for r in nh if "replacement_after_blocked" in r["ua_end"]))
print("  victims dead:", sum(1 for r in nh if r["victim_dead"] is not None))
print("  arms:", sorted(set(r["tag"] for r in nh)))
k1 = set((r["wind"], r["roles"], r["seed"], r["cls"], r["vid"], r["ff"], r["s0"], r["end"], r["p0"], r["cause"]) for r in nh)
k0 = set(k[:9] for k in k1)
print("  distinct (cause-keyed):", len(k1), " without cause:", len(k0))
print("  carrier on a boundary cell before the break:", sum(1 for r in nh if r["first_b"] is not None),
      sorted((r["tag"], r["seed"], r["end"] - r["first_b"]) for r in nh if r["first_b"] is not None))
