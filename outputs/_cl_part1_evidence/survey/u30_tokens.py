"""Read-only: which U30 seeds now appear as tokens the _ug_seeds guard would count as 'used'.
Does NOT import or run the selector. Non-recursive listings only; the quarantine name is skipped."""
import os, re, subprocess, collections
ROOT = r"E:\Projects\SAS"
QUAR = "_firemech_rewound_20260914"
OWN = ("_ug", "ungated", "_ffr_ug", "_rblatch_camp2_ug", "ug", "_uh", "_ffr_uh", "uh")
u30 = []
for line in open(os.path.join(ROOT, "outputs", "_ug_seeds.txt"), encoding="utf-8"):
    m = re.match(r"^(east|south)\|(half|default)\s+seed (\d+)", line)
    if m:
        u30.append(int(m.group(3)))
assert len(u30) == 30
hits = collections.defaultdict(set)
for d in ("outputs", os.path.join("outputs", "_ffr_logs")):
    for n in os.listdir(os.path.join(ROOT, d)):
        if n == QUAR:
            continue
        if os.path.basename(n).lower().startswith(OWN):
            continue
        for t in re.findall(r"\d+", n):
            v = int(t)
            if v in u30:
                hits[v].add(d + "/" + n)
# tracked queue files (name contains 'queue', ends .txt, not own)
out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z", "--", "outputs"], capture_output=True, check=True).stdout.decode("utf-8", "replace")
tracked = [p for p in out.split("\0") if p and QUAR not in p]
qhits = collections.defaultdict(set)
for p in tracked:
    b = os.path.basename(p).lower()
    if b.endswith(".txt") and "queue" in b and not b.startswith(OWN):
        txt = open(os.path.join(ROOT, p), "rb").read().decode("utf-8", "replace")
        for t in re.findall(r"\d+", txt):
            v = int(t)
            if v in u30:
                qhits[v].add(p)
print("U30 seeds hit by non-own FILE NAMES: %d" % len(hits))
for v in sorted(hits):
    ex = sorted(hits[v])
    print("  %d  %d names, e.g. %s" % (v, len(ex), ex[:3]))
print("U30 seeds hit by tracked non-own QUEUE files: %d" % len(qhits))
for v in sorted(qhits):
    print("  %d  %s" % (v, sorted(qhits[v])))
print("tracked _xs files:", [p for p in tracked if os.path.basename(p).startswith("_xs")][:20])
