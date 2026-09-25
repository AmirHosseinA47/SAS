"""Refinement of scan_c: unit-state census at every geo marking, custody for
files without ff_bind_steps via exit_starts, carry geometry. Read-only; lists
outputs/ non-recursively and skips the quarantine name."""
import json, os, re
from collections import defaultdict, Counter

OUT = r"E:\Projects\SAS\outputs"
SCRATCH = os.path.dirname(os.path.abspath(__file__))
QUAR = "_firemech_rewound_20260914"
PAT = re.compile(r"^_ffr_(.+)_(east|west|north|south)_(half|def)_(\d+)\.json$")
H = W = 50


def exit_target(cell):
    x, y = cell
    dists = {(0, y): x, (H - 1, y): H - 1 - x, (x, 0): y, (x, W - 1): W - 1 - y}
    return min(dists, key=dists.get)


def main():
    out = []
    for n in sorted(os.listdir(OUT)):
        if n == QUAR:
            continue
        m = PAT.match(n)
        if not m or n.endswith(".xstrace.json"):
            continue
        p = os.path.join(OUT, n)
        with open(p, "rb") as f:
            raw = f.read()
        if b'"cause": "geographically_isolated"' not in raw and b'"cause":"geographically_isolated"' not in raw:
            continue
        d = json.loads(raw.decode("utf-8"))
        del raw
        geo = [e for e in (d.get("unreachable_escape_log") or []) if e.get("cause") == "geographically_isolated"]
        if not geo:
            continue
        ffs = d["ff_steps"]
        binds = d.get("ff_bind_steps")
        vs = d["victim_steps"]
        xs = d.get("exit_starts") or []
        comps = d.get("completions") or []
        unassigns = d.get("unassigns") or []

        def unit_of(uid):
            return uid  # ff_steps ids are ff_unit_N, exit_starts ff are ff_unit_N

        # carrying victim per unit per step from exit_starts + ff_steps exiting flag
        def carrying(uid, step):
            """victim the unit carries at the END of `step`, via last exit_start <= step."""
            row = ffs[step - 1]
            r = [x for x in row if x[0] == uid]
            if not r or not r[0][4] or r[0][5]:
                return None
            if binds:
                b = [x for x in binds[step - 1] if x[0] == uid]
                return b[0][1] if b and b[0][1] else "?"
            st = [x for x in xs if x["ff"] == uid and int(x["step"]) <= step]
            return st[-1]["victim"] if st else "?"

        for e in geo:
            s = int(e["step"])
            v = e["victim_id"]
            # unit census at the BFS: end of step s, before the unassign. A unit the
            # escape unassigned at s was carrying/approaching; its pre-unassign
            # exiting flag is read from step s-1 (it cannot change phase except by
            # completion, which would have removed it).
            census = []
            carriers_of_v = []
            living = []
            ua_ff = sorted({u["ff"] for u in unassigns if int(u["step"]) == s and u["reason"] == "geographically_isolated"})
            for r in ffs[s - 1]:
                uid, cell, status, assigned, exiting, dead = r
                if dead or str(status).lower() == "dead":
                    census.append("%s:dead" % uid)
                    continue
                if cell is None:
                    census.append("%s:offgrid" % uid)
                    continue
                cv = carrying(uid, s)
                if cv is None and uid in ua_ff:
                    cv = carrying(uid, s - 1)
                    if cv is None:
                        # pickup on this very step?
                        st = [x for x in xs if x["ff"] == uid and int(x["step"]) == s]
                        cv = st[-1]["victim"] if st else None
                if cv is not None:
                    census.append("%s:carrying %s" % (uid, cv))
                    if cv == v:
                        carriers_of_v.append(uid)
                    continue
                living.append(uid)
                bnd = ""
                if binds:
                    b = [x for x in binds[s - 1] if x[0] == uid]
                    bnd = b[0][1] if b else ""
                census.append("%s:%s%s" % (uid, status, (" ->" + bnd) if bnd else ""))
            carry = None
            if carriers_of_v:
                cu = carriers_of_v[0]
                st = [x for x in xs if x["ff"] == cu and x["victim"] == v and int(x["step"]) <= s]
                pk = st[-1] if st else None
                ccell = [r[1] for r in ffs[s - 1] if r[0] == cu][0]
                if ccell is None or cu in ua_ff:
                    ccell = [r[1] for r in ffs[s - 1] if r[0] == cu][0]
                et = exit_target(tuple(pk["ff_pos"])) if pk else None
                later_death = None
                for i in range(s, len(ffs)):
                    rr = [r for r in ffs[i] if r[0] == cu]
                    if rr and rr[0][5]:
                        later_death = i + 1
                        break
                carry = {
                    "carrier": cu, "pickup_step": pk["step"] if pk else None,
                    "pickup_cell": pk["ff_pos"] if pk else None, "exit_target": et,
                    "leg_dist": (abs(pk["ff_pos"][0] - et[0]) + abs(pk["ff_pos"][1] - et[1])) if pk else None,
                    "carrier_cell_at_mark": ccell,
                    "dist_to_exit_at_mark": (abs(ccell[0] - et[0]) + abs(ccell[1] - et[1])) if (et and ccell) else None,
                    "on_boundary_at_mark": bool(ccell and (ccell[0] in (0, W - 1) or ccell[1] in (0, H - 1))),
                    "carrier_death": later_death,
                }
            # victim fate
            death = None
            final = None
            for i in range(s - 1, len(vs)):
                r = [x for x in vs[i] if x[0] == v]
                if r:
                    final = (r[0][1], r[0][2])
                    if r[0][2] == "dead" and death is None:
                        death = i + 1
            vflee_after = [(x["step"], x["from"], x["to"]) for x in (d.get("victim_flee_log") or [])
                           if x.get("victim_id") == v and int(x["step"]) > s]
            out.append({
                "tag": m.group(1), "wind": m.group(2), "roles": m.group(3), "seed": int(m.group(4)),
                "victim": v, "step": s, "streak": e.get("streak"),
                "census": census, "living": living, "starts_empty": not living,
                "custody": bool(carriers_of_v), "carry": carry, "unassigned_ff": ua_ff,
                "victim_final": final, "victim_death_step": death, "victim_flee_moves_after": len(vflee_after),
                "has_bind": bool(binds), "has_burn_intervals": "burn_intervals" in d,
                "steps_run": len(ffs), "eval": {k: (d.get("eval") or {}).get(k) for k in ("rescued", "dead", "unreachable", "geographically_isolated", "never_detected")},
            })
        del d
    with open(os.path.join(SCRATCH, "scan_c2.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)

    groups = defaultdict(list)
    for r in out:
        groups[(r["wind"], r["roles"], r["seed"], r["victim"], r["step"])].append(r)
    print("markings", len(out), "distinct", len(groups))
    cls = Counter()
    for k, g in groups.items():
        r = g[0]
        c = "custody" if any(x["custody"] for x in g) else "other"
        cls[(c, r["starts_empty"])] += 1
    print("distinct by (custody, starts_empty):", cls)
    print("markings by (custody, starts_empty):", Counter((r["custody"], r["starts_empty"]) for r in out))
    print("\n=== CUSTODY (distinct) ===")
    for k, g in sorted(groups.items()):
        if not any(x["custody"] for x in g):
            continue
        r = [x for x in g if x["custody"]][0]
        print(k, "n_tags", len(g), "tags", sorted(x["tag"] for x in g))
        print("   census", r["census"], "carry", r["carry"])
        print("   victim final", r["victim_final"], "death", r["victim_death_step"], "flee_after", r["victim_flee_moves_after"],
              "eval", r["eval"], "burn_iv", r["has_burn_intervals"], "bind", r["has_bind"])
    print("\n=== NON-CUSTODY, starts_empty (distinct): unit census ===")
    cc = Counter()
    for k, g in sorted(groups.items()):
        r = g[0]
        if any(x["custody"] for x in g) or not r["starts_empty"]:
            continue
        kinds = tuple(sorted({c.split(":", 1)[1].split(" ")[0] for c in r["census"]}))
        cc[kinds] += 1
        print(k, "n_tags", len(g), "census", r["census"], "final", r["victim_final"], "death", r["victim_death_step"])
    print("census kinds:", cc)
    print("\n=== NON-CUSTODY, starts non-empty (distinct) ===")
    for k, g in sorted(groups.items()):
        r = g[0]
        if any(x["custody"] for x in g) or r["starts_empty"]:
            continue
        print(k, "n_tags", len(g), "census", r["census"], "final", r["victim_final"], "death", r["victim_death_step"])


main()
