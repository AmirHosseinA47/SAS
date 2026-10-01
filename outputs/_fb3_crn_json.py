"""Every top-level outputs/*.json (non-recursive) whose text mentions FM2P_CRN: is it a REAL CRN run
(an fm2p block with crn_draws > 0)? Grouped by tag stem. Read-only."""
import collections, glob, json, os, re

OUT = r"E:\Projects\SAS\outputs"
res = collections.defaultdict(lambda: collections.Counter())
examples = {}
for p in sorted(glob.glob(os.path.join(OUT, "*.json"))):
    try:
        raw = open(p, "rb").read()
    except Exception:
        continue
    if b"FM2P_CRN" not in raw and b"fm2p" not in raw:
        continue
    base = os.path.basename(p)
    m = re.match(r"(_[a-z0-9]+_[A-Za-z0-9]+?)(_(east|west|north|south|[ABCD])_|_D_|$)", base)
    stem = m.group(1) if m else base[:20]
    try:
        d = json.loads(raw.decode("utf-8"))
    except Exception:
        res[stem]["unparseable"] += 1
        continue
    blocks = []
    if isinstance(d, dict):
        if "fm2p" in d:
            blocks.append(d["fm2p"])
        for v in d.values():           # campaign shards: per-seed dicts
            if isinstance(v, dict) and "fm2p" in v:
                blocks.append(v["fm2p"])
    if not blocks:
        claims = b'"FM2P_CRN": 1' in raw or b"FM2P_CRN=1" in raw or b'"FM2P_CRN": "1"' in raw
        res[stem]["no_fm2p_block" + ("_but_claims_CRN" if claims else "")] += 1
        examples.setdefault((stem, "nob"), base)
        continue
    for b in blocks:
        c = (b.get("counters") or {}).get("crn_draws", 0)
        cfg = b.get("config") or {}
        res[stem]["real_crn" if c and c > 0 else "fm2p_block_no_crn_draws(cfg CRN=%s)" % cfg.get("FM2P_CRN")] += 1
for stem, c in sorted(res.items()):
    print("%-28s %s %s" % (stem, dict(c), examples.get((stem, "nob"), "")))
