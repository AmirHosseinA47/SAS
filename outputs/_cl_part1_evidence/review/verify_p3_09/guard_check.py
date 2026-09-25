"""Verify P3-09: does the draft's OWN extension reproduce U30 from _ug_seeds.choose()?
Read-only: imports outputs/_ug_seeds.py (python -B, no pycache), which lists outputs/ and
outputs/_ffr_logs/ NON-recursively (skipping the quarantine by name) and runs git ls-files.
"""
import os
import re
import sys

ROOT = r"E:\Projects\SAS"
sys.path.insert(0, os.path.join(ROOT, "outputs"))
import _ug_seeds as U  # noqa: E402

frozen = U.frozen_u30()
fseeds = {s for _c, s in frozen}
QUAR = "_firemech_rewound_20260914"

# 1. every name (git + non-recursive listing) carrying a U30 seed token
names = set(U.git_names("--", "outputs")) | set(U.git_names("--others", "--exclude-standard", "--", "outputs"))
for d in ("outputs", os.path.join("outputs", "_ffr_logs")):
    for n in os.listdir(os.path.join(ROOT, d)):
        if n == QUAR:
            continue
        names.add(d.replace("\\", "/") + "/" + n)
hits = {}
for p in names:
    b = os.path.basename(p)
    toks = {int(t) for t in re.findall(r"\d+", b)}
    t = toks & fseeds
    if t:
        hits.setdefault(p, t)
# group by basename prefix (up to first '_' after the tag)
by_prefix = {}
for p in sorted(hits):
    b = os.path.basename(p).lower()
    if U._own(p):
        continue
    m = re.match(r"^(_ffr_[a-z]+|_rblatch_camp2_[a-z]+|_[a-z]+|[a-z]+)", b)
    key = m.group(1) if m else b[:8]
    by_prefix.setdefault(key, set()).update(hits[p])
print("names carrying U30 seeds NOT skipped by the current OWN, by prefix:")
for k in sorted(by_prefix):
    print("  %-22s %d seeds %s" % (k, len(by_prefix[k]), sorted(by_prefix[k])))

# queue files (tracked) carrying U30 tokens and not own
print("tracked queue files with U30 tokens not own:")
for p in U.git_names("--", "outputs"):
    b = os.path.basename(p).lower()
    if b.endswith(".txt") and "queue" in b and not U._own(p):
        toks = U._tokens(open(os.path.join(ROOT, p), "rb").read().decode("utf-8", "replace"))
        t = toks & fseeds
        if t:
            print("  ", p, len(t), sorted(t))


def run(own):
    U.OWN = own
    tuples, rej, sources, n_used = U.choose()
    got = [(c, s) for c, s, _cell, _i in tuples]
    return got == frozen, n_used, [s for c, s in got if s not in fseeds][:5]


BASE = ("_ug", "ungated", "_ffr_ug", "_rblatch_camp2_ug", "ug", "_uh", "_ffr_uh", "uh")
DRAFT = BASE + ("_xs", "xs", "exitstall", "_cl", "cl", "carryleg")
REVIEW = BASE + ("_xs", "_ffr_xs", "xs", "exitstall", "_cl", "_ffr_cl", "_rblatch_camp2_cl", "cl", "carryleg")
for name, own in (("current", BASE), ("draft 8.3", DRAFT), ("reviewer", REVIEW)):
    ok, n_used, extra = run(own)
    print("%-10s choose()==frozen: %s  used=%d  first non-U30 accepted: %s" % (name, ok, n_used, extra))
