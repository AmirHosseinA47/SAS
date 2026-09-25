"""How often does D3 (a marking of a victim carried by a live exiting unit) fire in the
SHIPPED configuration's own recorded arms (ungated round ug*/uh*)? Also count geo markings
and the zero-start co-markings. Reads only named _ffr_ug*/_ffr_uh* files listed by a
non-recursive glob of outputs/ (no descent into any directory)."""
import glob, json, os, re

OUT = r"E:\Projects\SAS\outputs"
files = sorted(glob.glob(os.path.join(OUT, "_ffr_ug*.json")) + glob.glob(os.path.join(OUT, "_ffr_uh*.json")))
pat = re.compile(r"_ffr_([A-Za-z0-9]+)_(east|south|west|north)_(half|def)_(\d+)\.json$")
by_tag = {}
d3 = []
geo_total = 0
for f in files:
    m = pat.search(os.path.basename(f))
    if not m:
        continue
    tag = m.group(1)
    d = json.load(open(f))
    by_tag.setdefault(tag, [0, 0, 0, d.get("steps")])
    by_tag[tag][0] += 1
    esc = [e for e in d.get("unreachable_escape_log", []) if e.get("cause") == "geographically_isolated"]
    by_tag[tag][1] += len(esc)
    geo_total += len(esc)
    for e in esc:
        s = e["step"]
        rows = d["ff_steps"][s - 2]
        exiting = [r[0] for r in rows if r[4] and not r[5]]
        carried = {x["victim"] for x in d["exit_starts"] if x["ff"] in exiting and x["step"] <= s}
        if e["victim_id"] in carried:
            by_tag[tag][2] += 1
            d3.append((os.path.basename(f), s, e["victim_id"]))
for t, v in sorted(by_tag.items()):
    print("%-8s runs=%3d geo_markings=%3d custody_markings=%d steps=%s" % (t, v[0], v[1], v[2], v[3]))
print("files", len(files), "geo markings", geo_total, "D3 custody markings", d3)
