"""fix2 Part 1: which source did the recorded fix1 probe runs execute?

Compares each outputs/_sd_mf1P_*.json src_sha (16-hex sha256 prefixes of 11 source files)
with the same prefixes computed from the working tree (branch fix2 == c08456b, clean).
Read-only.
"""
import glob
import hashlib
import json
import os
import sys

REPO = r"E:\Projects\SAS"


def sha(path):
    # The working tree's line endings changed with the fix1 merge (core.autocrlf=true:
    # wildfire_model.py is CRLF now, LF when the fix1 runs hashed it). The index is LF
    # everywhere, so compare LF-normalized content, which is what git compares.
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()[:16]


def main():
    pats = sys.argv[1:] or ["_sd_mf1P_*.json"]
    files = []
    for p in pats:
        files += sorted(glob.glob(os.path.join(REPO, "outputs", p)))
    now = None
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        ss = d.get("src_sha") or {}
        if now is None:
            now = {k: sha(os.path.join(REPO, k)) for k in ss}
        diff = [k for k in ss if ss[k] != now.get(k)]
        print("%-28s head=%s seed=%s %s/%s complete=%s extra=%s src_equal_HEAD=%s %s" % (
            os.path.basename(f), str(d.get("head"))[:7], d.get("seed"), d.get("scenario"),
            d.get("wind"), d.get("complete"), d.get("extra_params"), not diff, diff))


if __name__ == "__main__":
    main()
