import collections
import os
import pickle
import sys

SCR = os.path.dirname(os.path.abspath(__file__))
D = pickle.load(open(os.path.join(SCR, "d1_legs.pkl"), "rb"))
ONLY_TRACKED = "--tracked" in sys.argv
comp = [r for r in D["comp"] if r["tracked"] or not ONLY_TRACKED]
broken = [r for r in D["broken"] if r["tracked"] or not ONLY_TRACKED]
print("file set:", "tracked at 80ca7b3 only" if ONLY_TRACKED else "all census-eligible (incl. untracked ugmD)")


def rkey(r):
    return (r["wind"], r["roles"], r["seed"], r["cls"], r["vid"], r["ff"], r["s0"], r["s1"], r["p0"], r["tgt"])


# ---------------- item 2
distinct = collections.OrderedDict()
for r in comp:
    distinct.setdefault(rkey(r), []).append(r)
print("\nITEM 2  distinct completed legs:", len(distinct))
for cls in ("OFF", "ON"):
    ks = [k for k in distinct if k[3] == cls]
    bad = [k for k in ks if any(r["dist"] != r["nbdist"] for r in distinct[k])]
    st = [k for k in ks if (k[7] - k[6]) > distinct[k][0]["dist"] + 5]
    print("  %s: distinct %d, stalled %d, distance != nearest-boundary distance: %d" % (cls, len(ks), len(st), len(bad)))
# tie-break: how often is the nearest boundary cell ambiguous (several at the same distance)?
ties = 0
for k, rs in distinct.items():
    x, y = k[8]
    ds = [x, 49 - x, y, 49 - y]
    if ds.count(min(ds)) > 1:
        ties += 1
print("  distinct legs whose pickup cell has >1 nearest boundary cell (tie):", ties)
dist0 = sum(1 for k, rs in distinct.items() if rs[0]["dist"] == 0)
print("  distinct legs picked up ON the boundary (distance 0):", dist0)

# ---------------- item 3
print("\nITEM 3  distinct STALLED legs: first step at whose start the carrier stood on ANY boundary cell (= a mode-1 completion step)")
tot = collections.Counter()
rows = []
for k, rs in distinct.items():
    r0 = rs[0]
    leg = k[7] - k[6]
    if leg <= r0["dist"] + 5:
        continue
    fbs = sorted(set(r["first_b"] for r in rs))
    cells = sorted(set(r["first_b_cell"] for r in rs))
    fb = r0["first_b"]
    sav = k[7] - fb
    newleg = fb - k[6]
    un = newleg <= r0["dist"] + 5
    dcell = abs(k[8][0] - r0["first_b_cell"][0]) + abs(k[8][1] - r0["first_b_cell"][1])
    un_alt = newleg <= dcell + 5
    tags = sorted(set(r["tag"] for r in rs))
    rows.append((k, r0, leg, fb, sav, newleg, un, un_alt, dcell, fbs, cells, tags))
    tot[(k[3], "legs")] += 1
    tot[(k[3], "excess")] += leg - r0["dist"] - 1
    tot[(k[3], "saving")] += sav
    tot[(k[3], "saving>0")] += sav > 0
    tot[(k[3], "unstall")] += un
    tot[(k[3], "unstall_alt")] += un_alt
    tot[(k[3], "newexcess")] += max(0, newleg - r0["dist"] - 1)
rows.sort(key=lambda t: (t[0][3] != "OFF", str(t[0][0]), str(t[0][1]), t[0][2], t[0][6]))
print("  cls wind/roles/seed vid ff: s0-s1 leg/dist | first_on_boundary(start-of-step) cell | saving | new leg | unstalled(nearest) unstalled(to-that-cell,dist) | n files [first_b values if they differ]")
for (k, r0, leg, fb, sav, newleg, un, un_alt, dcell, fbs, cells, tags) in rows:
    print("  %-3s %s/%s/%s %s %s: %d-%d %d/%d | %d %s | %d | %d | %s %s(%d) | %d%s" % (
        k[3], k[0], k[1], k[2], k[4], k[5], k[6], k[7], leg, r0["dist"], fb, list(r0["first_b_cell"]), sav, newleg,
        "UNSTALL" if un else "still", "UNSTALL" if un_alt else "still", dcell, len(distinct[k]),
        "" if len(fbs) == 1 else " DIFFER %s" % fbs))
for cls in ("OFF", "ON"):
    print("  %s: %d stalled legs, %d excess steps; mode-1 saving %d steps on %d legs; un-stalled by the bound: %d (nearest-boundary distance), %d (distance to the boundary cell reached); excess left %d" % (
        cls, tot[(cls, "legs")], tot[(cls, "excess")], tot[(cls, "saving")], tot[(cls, "saving>0")], tot[(cls, "unstall")],
        tot[(cls, "unstall_alt")], tot[(cls, "newexcess")]))

# cross-check the diagnosis's 1038 / 81 on the 12 matched arms
GROUPS = [["uhC", "uhD", "uhY"], ["ugKC", "ugKD", "ugKY"], ["fmOFF", "fmEFS", "fmDRY"], ["f2cOFF", "f2cEFS", "f2cDRY"]]
import re
by_tag_file = collections.defaultdict(dict)
for n in os.listdir("E:/Projects/SAS/outputs"):
    if n == "_firemech_rewound_20260914":
        continue
    m = re.match(r"^_ffr_(.+?)_(east|south|west|north)_(half|def)_(\d+)\.json$", n)
    if m:
        by_tag_file[m.group(1)][n] = (m.group(2), m.group(3), int(m.group(4)))
exc = sav = 0
for g in GROUPS:
    common = set.intersection(*(set(by_tag_file[t].values()) for t in g))
    for t in g:
        files = {f for f, tup in by_tag_file[t].items() if tup in common}
        for r in comp:
            if r["tag"] != t or r["file"] not in files:
                continue
            leg = r["s1"] - r["s0"]
            if leg > r["dist"] + 5:
                exc += leg - r["dist"] - 1
                sav += r["s1"] - r["first_b"]
print("  12 matched arms, common tuples (arm-occurrences): excess %d, saving s1 - first_b %d" % (exc, sav))
