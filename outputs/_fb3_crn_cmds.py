"""Every recorded command line (non-recursive outputs/: *.argv, *queue*.jsonl, *queue*.txt, *.poollog, *.sh)
that carries FM2P_CRN: which script ran it. Read-only."""
import collections, glob, json, os, re, sys

OUT = r"E:\Projects\SAS\outputs"


def read(p):
    raw = open(p, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    if raw.count(b"\x00") > len(raw) // 4:
        return raw.decode("utf-16-le", "replace")
    return raw.decode("utf-8", "replace")


SCRIPT = re.compile(r"([A-Za-z0-9_\-]+\.py)")
rows = []
files = set()
for pat in ("*.argv", "*queue*.jsonl", "*queue*.txt", "*.jsonl", "*.sh", "*.ps1", "*_state.txt"):
    files.update(glob.glob(os.path.join(OUT, pat)))
for p in sorted(files):
    try:
        t = read(p)
    except Exception:
        continue
    for ln in t.splitlines():
        if "FM2P_CRN" not in ln:
            continue
        scripts = [s for s in SCRIPT.findall(ln)]
        # value of FM2P_CRN
        m = re.search(r"FM2P_CRN[\"']?\s*[=:]\s*[\"']?([0-9A-Za-z.]+)", ln)
        val = m.group(1) if m else "?"
        tag = None
        mt = re.search(r"--tag[\"',\s]+([A-Za-z0-9_]+)", ln) or re.search(r"\"name\":\s*\"([A-Za-z0-9_]+)\"", ln)
        if mt:
            tag = mt.group(1)
        rows.append((os.path.basename(p), tuple(scripts[:3]), val, tag, ln.strip()[:200]))

by_script = collections.Counter()
for f, s, v, tag, ln in rows:
    by_script[(s[0] if s else "(no script on line)", v)] += 1
print("COMMAND LINES CARRYING FM2P_CRN, by first script on the line and value:")
for k, n in by_script.most_common():
    print("  %5d  %-40s FM2P_CRN=%s" % (n, k[0], k[1]))
if len(sys.argv) > 1:
    want = sys.argv[1]
    for f, s, v, tag, ln in rows:
        if (s[0] if s else "(no script on line)") == want:
            print(f, tag, v, ln[:160])
