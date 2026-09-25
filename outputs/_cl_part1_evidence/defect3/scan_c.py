"""Record-wide scan of geographically_isolated markings (read-only).

Lists outputs/ NON-recursively (os.listdir), skips the quarantine directory by
name and never opens anything but top-level _ffr_<tag>_<wind>_<roles>_<seed>.json
files. Writes only to this scratch directory.
"""
import json, os, re, sys
from collections import deque, defaultdict

OUT = r"E:\Projects\SAS\outputs"
SCRATCH = os.path.dirname(os.path.abspath(__file__))
QUAR = "_firemech_rewound_20260914"
PAT = re.compile(r"^_ffr_(.+)_(east|west|north|south)_(half|def)_(\d+)\.json$")
W = H = 50


def burning_at(d, step):
    out = set()
    for key, ivs in (d.get("burn_intervals") or {}).items():
        for s, e in ivs:
            if s <= step and (e is None or step < e):
                x, y = key.split(",")
                out.add((int(x), int(y)))
                break
    return out


def bfs(starts, burning):
    seen = set()
    q = deque()
    for s in starts:
        s = tuple(s)
        if s in burning or s in seen:
            continue
        if not (0 <= s[0] < W and 0 <= s[1] < H):
            continue
        seen.add(s)
        q.append(s)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if not (0 <= n[0] < W and 0 <= n[1] < H):
                continue
            if n in seen or n in burning:
                continue
            seen.add(n)
            q.append(n)
    return seen


def main():
    names = []
    for n in os.listdir(OUT):  # non-recursive
        if n == QUAR:
            continue
        m = PAT.match(n)
        if not m or n.endswith(".xstrace.json"):
            continue
        names.append((n, m))
    names.sort()
    n_files = len(names)
    n_with_log_field = 0
    n_with_bind = 0
    n_geo_files = 0
    rows = []
    skipped = []
    for n, m in names:
        p = os.path.join(OUT, n)
        with open(p, "rb") as f:
            raw = f.read()
        has_log = b'"unreachable_escape_log"' in raw
        if has_log:
            n_with_log_field += 1
        if b'"ff_bind_steps"' in raw:
            n_with_bind += 1
        if b'"cause": "geographically_isolated"' not in raw and b'"cause":"geographically_isolated"' not in raw:
            continue
        d = json.loads(raw.decode("utf-8"))
        del raw
        log = d.get("unreachable_escape_log") or []
        geo = [e for e in log if e.get("cause") == "geographically_isolated"]
        if not geo:
            continue
        n_geo_files += 1
        tag = m.group(1)
        wind, roles, seed = m.group(2), m.group(3), int(m.group(4))
        ffs = d.get("ff_steps")
        binds = d.get("ff_bind_steps")
        vs = d.get("victim_steps")
        exit_starts = d.get("exit_starts")
        if not ffs or vs is None:
            skipped.append((n, "no ff_steps/victim_steps"))
            continue
        unassigns = d.get("unassigns") or []
        completions = d.get("completions") or []
        steps_run = len(ffs)
        # final victim states
        final_v = {r[0]: (r[1], r[2]) for r in vs[-1]} if vs else {}
        death_step = {}
        prev = {}
        for i, row in enumerate(vs):
            for r in row:
                if r[2] == "dead" and prev.get(r[0]) != "dead":
                    death_step[r[0]] = i + 1
                prev[r[0]] = r[2]
        ff_death = {}
        prevd = {}
        for i, row in enumerate(ffs):
            for r in row:
                if r[5] and not prevd.get(r[0]):
                    ff_death[r[0]] = i + 1
                prevd[r[0]] = r[5]
        marked_same_step = defaultdict(list)
        for e in geo:
            marked_same_step[int(e["step"])].append(e["victim_id"])
        for e in geo:
            s = int(e["step"])
            v = e["victim_id"]
            if s < 2 or s > steps_run:
                skipped.append((n, "step out of range %d" % s))
                continue
            prow = ffs[s - 2]
            crow = ffs[s - 1]
            pb = {r[0]: r[1] for r in (binds[s - 2] if binds else [])}
            cb = {r[0]: r[1] for r in (binds[s - 1] if binds else [])}
            carriers = set()
            approachers = set()
            if binds:
                for r in prow:
                    uid, cell, status, assigned, exiting, dead = r
                    if dead or pb.get(uid) != v:
                        continue
                    if exiting:
                        carriers.add(uid)
                    elif assigned:
                        approachers.add(uid)
                # carrier still bound after the step (no unassign issued)
                for r in crow:
                    uid, cell, status, assigned, exiting, dead = r
                    if not dead and exiting and cb.get(uid) == v:
                        carriers.add(uid)
            pickup_now = set()
            for x in (exit_starts or []):
                if int(x["step"]) == s and x["victim"] == v:
                    pickup_now.add(x["ff"])
            # map unit_id (ff_unit_N) to marker id used in ff_steps
            ids = [r[0] for r in crow]

            def mid(unit):
                for i2 in ids:
                    if i2 == unit or i2.endswith(unit):
                        return i2
                return unit
            for u in pickup_now:
                carriers.add(mid(u))
                approachers.discard(mid(u))
            ua = [u for u in unassigns if int(u["step"]) == s and u["vid"] == v]
            ua_ff = sorted({u["ff"] for u in ua})
            # living units at the BFS (end of step s, before unassign):
            living_cells = []
            living_ids = []
            for r in crow:
                uid, cell, status, assigned, exiting, dead = r
                if dead or str(status).lower() == "dead" or cell is None:
                    continue
                if exiting or uid in carriers:
                    continue
                living_cells.append(tuple(cell))
                living_ids.append(uid)
            burning = burning_at(d, s)
            region = bfs(living_cells, burning)
            vcell = None
            for r in vs[s - 1]:
                if r[0] == v:
                    vcell = tuple(r[1]) if r[1] else None
            recon_geo = (vcell in region) if vcell else None
            carrier_info = None
            if carriers:
                cu = sorted(carriers)[0]
                ccell = None
                for r in crow:
                    if r[0] == cu:
                        ccell = tuple(r[1]) if r[1] else None
                creg = bfs([ccell], burning) if ccell else set()
                edge = sum(1 for c in creg if c[0] in (0, W - 1) or c[1] in (0, H - 1))
                # pickup step of this carry
                pk = [int(x["step"]) for x in (exit_starts or []) if x["victim"] == v and mid(x["ff"]) == cu and int(x["step"]) <= s]
                pk_step = max(pk) if pk else None
                carrier_info = {
                    "carrier": cu, "carrier_cell": ccell, "pickup": pk_step,
                    "carrier_region": len(creg), "carrier_region_edge_cells": edge,
                    "carrier_death": ff_death.get(cu),
                    "carrier_status_at_mark": [r[2] for r in crow if r[0] == cu],
                }
            cls = "custody" if carriers else ("approach" if approachers else "unbound")
            rows.append({
                "file": n, "tag": tag, "wind": wind, "roles": roles, "seed": seed,
                "victim": v, "step": s, "streak": e.get("streak"), "class": cls,
                "carriers": sorted(carriers), "approachers": sorted(approachers),
                "pickup_same_step": sorted(pickup_now),
                "unassigned_ff": ua_ff,
                "living_at_bfs": living_ids, "starts_empty": not living_cells,
                "victim_cell": vcell, "recon_geo_reachable": recon_geo,
                "co_marked": sorted(x for x in marked_same_step[s] if x != v),
                "final_victim": final_v.get(v), "victim_death_step": death_step.get(v),
                "steps_run": steps_run, "has_bind": bool(binds),
                "carrier_info": carrier_info,
                "eval_rescued": (d.get("eval") or {}).get("rescued"),
            })
        del d
    res = {
        "n_files": n_files, "n_with_log_field": n_with_log_field, "n_with_bind": n_with_bind,
        "n_geo_files": n_geo_files, "rows": rows, "skipped": skipped,
    }
    with open(os.path.join(SCRATCH, "scan_c.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("files", n_files, "with_log_field", n_with_log_field, "with_bind", n_with_bind,
          "files_with_geo", n_geo_files, "geo markings", len(rows), "skipped", len(skipped))


main()
