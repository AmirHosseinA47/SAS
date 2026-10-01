"""Scan top-level outputs/*.txt|*.md (non-recursive) for CRN / fire-pinned claims; decode utf-16 or utf-8."""
import glob, os, re, sys, json

OUT = r"E:\Projects\SAS\outputs"
PAT = re.compile(r"(FM2P_CRN|\bCRN\b|fire[- ]pinned|pinned fire|pin(?:s|ned)? (?:the|every) (?:fire|seed)|common random)", re.I)


def read(p):
    raw = open(p, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    if raw.count(b"\x00") > len(raw) // 4:
        return raw.decode("utf-16-le", "replace")
    return raw.decode("utf-8", "replace")


hits = {}
for pat in ("*.txt", "*.md"):
    for p in sorted(glob.glob(os.path.join(OUT, pat))):
        try:
            t = read(p)
        except Exception as e:
            continue
        lines = t.splitlines()
        h = [(i + 1, ln.strip()[:220]) for i, ln in enumerate(lines) if PAT.search(ln)]
        if h:
            hits[os.path.basename(p)] = h
mode = sys.argv[1] if len(sys.argv) > 1 else "count"
for f, h in sorted(hits.items(), key=lambda kv: -len(kv[1])):
    if mode == "count":
        print("%5d %s" % (len(h), f))
    else:
        print("=" * 10, f)
        for i, ln in h:
            print("  %d: %s" % (i, ln))
