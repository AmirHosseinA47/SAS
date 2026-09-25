"""For each D3 tuple, across every recorded run of the SAME tuple (non-recursive listdir of
outputs/, names only), report for each co-marked 'other' victim: first confirmed step,
first assigned step, end status. Tests whether co-marked candidates are ever detected /
rescued in sibling runs (i.e. whether keeping them unmarked could matter)."""
import json, os, re, collections

OUT = r"E:\Projects\SAS\outputs"
names = os.listdir(OUT)  # non-recursive, names only
CASES = {
    ("east", "def", "101"): ["victim_1", "victim_2", "victim_3"],
    ("east", "half", "606"): ["victim_1", "victim_3"],
    ("east", "half", "1010"): ["victim_1", "victim_2"],
    ("east", "half", "1323590814"): ["victim_1", "victim_3"],
    ("south", "half", "404"): ["victim_2"],
    ("west", "half", "303"): ["victim_0", "victim_1", "victim_3"],
    ("west", "half", "505"): ["victim_0", "victim_1", "victim_3"],
}
pat = re.compile(r"^_ffr_(.+)_(east|west|north|south)_(half|def)_(\d+)\.json$")
for (w, r, s), vids in CASES.items():
    files = sorted(n for n in names if (m := pat.match(n)) and m.group(2) == w and m.group(3) == r and m.group(4) == s)
    summ = {v: collections.Counter() for v in vids}
    detail = {v: [] for v in vids}
    for f in files:
        try:
            d = json.load(open(os.path.join(OUT, f)))
        except Exception as e:
            continue
        vs = d.get("victim_steps")
        if not vs:
            continue
        for v in vids:
            first_conf = None
            first_asg = None
            end = None
            for i, rows in enumerate(vs):
                for row in rows:
                    if row[0] != v:
                        continue
                    st = row[2]
                    if st in ("confirmed", "assigned", "rescued") and first_conf is None:
                        first_conf = i + 1
                    if st == "assigned" and first_asg is None:
                        first_asg = i + 1
                    end = st
            esc = [(e["step"], e["cause"]) for e in d.get("unreachable_escape_log", []) if e["victim_id"] == v]
            summ[v][end] += 1
            detail[v].append((f[5:].split("_" + w)[0], len(vs), first_conf, first_asg, end, esc))
    print("==", w, r, s, "files", len(files))
    for v in vids:
        print("  ", v, dict(summ[v]))
        confd = [x for x in detail[v] if x[2] is not None]
        print("     runs where ever confirmed:", len(confd), "of", len(detail[v]))
        for x in confd[:8]:
            print("       ", x)
