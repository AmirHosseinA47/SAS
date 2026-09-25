"""Read-only F7 check: which U30 seeds would the _ug_seeds guard still count as 'used'
under three OWN variants, on today's names and on this round's planned names.
Does NOT import or run the selector. Non-recursive listings only; quarantine skipped by name.
No git --others scan (tracked ls-files only)."""
import os, re, subprocess, collections
ROOT = r"E:\Projects\SAS"
QUAR = "_firemech_rewound_20260914"
CUR = ("_ug", "ungated", "_ffr_ug", "_rblatch_camp2_ug", "ug", "_uh", "_ffr_uh", "uh")
DRAFT = CUR + ("_xs", "xs", "exitstall", "_cl", "cl", "carryleg")
REVIEWER = CUR + ("_xs", "_ffr_xs", "xs", "exitstall", "_cl", "_ffr_cl", "_rblatch_camp2_cl", "cl", "carryleg")
u30 = []
for line in open(os.path.join(ROOT, "outputs", "_ug_seeds.txt"), encoding="utf-8"):
    m = re.match(r"^(east|south)\|(half|default)\s+seed (\d+)", line)
    if m:
        u30.append((m.group(1), m.group(2), int(m.group(3))))
assert len(u30) == 30, len(u30)
U = {s for _w, _r, s in u30}

names = []
for d in ("outputs", os.path.join("outputs", "_ffr_logs"), os.path.join("outputs", "_cl_replay")):
    full = os.path.join(ROOT, d)
    if not os.path.isdir(full):
        continue
    for n in os.listdir(full):
        if n == QUAR:
            continue
        names.append(d.replace("\\", "/") + "/" + n)
out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z", "--", "outputs"], capture_output=True, check=True).stdout.decode("utf-8", "replace")
tracked = [p for p in out.split("\0") if p and QUAR not in p]
names_all = sorted(set(names) | set(tracked))

planned = []
for w, r, s in u30:
    rr = "def" if r == "default" else r
    for tag in ("clC", "clD", "clKC", "clKD", "clM1", "clM2"):
        planned.append("outputs/_ffr_%s_%s_%s_%d.json" % (tag, w, rr, s))
        planned.append("outputs/_ffr_logs/%s_%s_%s_%d.out" % (tag, w, rr, s))


def hits(own, name_list):
    h = collections.defaultdict(set)
    for p in name_list:
        b = os.path.basename(p).lower()
        if b.startswith(own):
            continue
        for t in re.findall(r"\d+", os.path.basename(p)):
            if int(t) in U:
                h[int(t)].add(p)
    return h


def qhits(own):
    h = collections.defaultdict(set)
    for p in tracked:
        b = os.path.basename(p).lower()
        if b.endswith(".txt") and "queue" in b and not b.startswith(own):
            txt = open(os.path.join(ROOT, p), "rb").read().decode("utf-8", "replace")
            for t in re.findall(r"\d+", txt):
                if int(t) >= 100 and int(t) in U:
                    h[int(t)].add(p)
    return h


for label, own in (("CURRENT", CUR), ("DRAFT 8.3", DRAFT), ("REVIEWER", REVIEWER)):
    for scope, nl in (("today", names_all), ("today+planned cl runs", names_all + planned)):
        h = hits(own, nl)
        q = qhits(own)
        seeds = set(h) | set(q)
        print("%-10s %-24s U30 seeds hit: %2d" % (label, scope, len(seeds)))
        pref = collections.Counter()
        for v in h:
            for p in h[v]:
                pref[re.sub(r"_(east|south).*", "", os.path.basename(p))] += 1
        if pref:
            print("      name prefixes:", dict(pref.most_common(12)))
        if q:
            print("      queue files:", sorted({p for v in q for p in q[v]}))
