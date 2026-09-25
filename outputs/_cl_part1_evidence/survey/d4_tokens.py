"""Read-only: do the dcd4 fourth-set seeds (from the committed _dcd4_queue.txt) now appear as tokens
that _dcd4_seeds.filename_tokens() would count (non-recursive outputs/ listing, skipping _ffr_d4*/_dcd4*/dcd4*)?
Does NOT import or run any selector."""
import os, re, collections
ROOT = r"E:\Projects\SAS"
QUAR = "_firemech_rewound_20260914"
seeds = set()
for ln in open(os.path.join(ROOT, "outputs", "_dcd4_queue.txt"), encoding="utf-8"):
    f = ln.strip().split("|")
    if len(f) >= 5 and f[0].startswith("d4") and not f[0].startswith("d4x"):
        seeds.add(int(f[4]))
print("dcd4 queue distinct seeds (d4A/d4D/d4off):", len(seeds))
hits = collections.defaultdict(set)
for n in os.listdir(os.path.join(ROOT, "outputs")):
    if n == QUAR:
        continue
    if n.lower().startswith(("_ffr_d4", "_dcd4", "dcd4")):
        continue
    for t in re.findall(r"\d+", n):
        v = int(t)
        if v in seeds:
            hits[v].add(n)
print("dcd4 seeds now appearing in other names:", len(hits))
for v in sorted(hits)[:40]:
    ex = sorted(hits[v])
    print("  %d %d names e.g. %s" % (v, len(ex), ex[:2]))
