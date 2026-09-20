"""Do victim statuses ever change AFTER terminal_step in the recorded corpus? Reads JSON only."""
import glob, json, os
BASE = "E:/Projects/SAS/outputs"
files = sorted(glob.glob(os.path.join(BASE, "_ffr_f3OFF_*.json")))
shown = False
for fp in files:
    d = json.load(open(fp))
    name = os.path.basename(fp)[len("_ffr_f3OFF_"):-5]
    vs = d.get("victim_steps") or []
    term = d.get("terminal_step")
    if not shown:
        print("victim_steps rows:", len(vs), "sample row[0]:", vs[0][:2] if vs else None)
        shown = True
    if term is None:
        print("%-18s term None" % name); continue
    # rows are per step (index 0 -> step 1)
    changes = []
    prev = None
    for i, row in enumerate(vs):
        step = i + 1
        cur = {str(r[0]): tuple(r[1:]) for r in row}
        if prev is not None and step > term:
            for vid, val in cur.items():
                pv = prev.get(vid)
                if pv is not None and pv != val:
                    changes.append((step, vid, pv, val))
        prev = cur
    stat_changes = [c for c in changes]
    print("%-18s term %3d  post-terminal victim row changes: %d %s" % (name, term, len(stat_changes), stat_changes[:4]))
