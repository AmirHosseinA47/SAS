"""Read-only census: how does a live carry end without a completion, per recorded run.

Reads outputs/_ffr_*.json (non-recursive listdir, quarantine dir never touched).
For every unassign record whose unit was EXITING at the end of the previous step,
records the reason. Also records carries that end by the carrier's death with no
unassign, and exits that end at the horizon.
Writes nothing under the repo.
"""
import json
import os
import sys
from collections import Counter, defaultdict

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"

names = sorted(
    n for n in os.listdir(OUT)
    if n != QUAR and n.startswith("_ffr_") and n.endswith(".json")
)

reason_all = Counter()          # unassign reason on an exiting unit, all files
reason_distinct = defaultdict(set)
escape_rows = []
drop_rows = []
other_rows = []
files_with_ffsteps = 0
bad = 0

for n in names:
    path = os.path.join(OUT, n)
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        bad += 1
        continue
    ffs = d.get("ff_steps") or []
    if not ffs:
        continue
    files_with_ffsteps += 1
    tag = d.get("tag")
    key_run = (d.get("wind"), d.get("scenario"), d.get("seed"))
    dim = d.get("dim") or {}
    # previous-step state lookup
    def state_at(step, ff):
        i = step - 1
        if i < 0 or i >= len(ffs):
            return None
        for row in ffs[i]:
            if row[0] == ff:
                return row
        return None
    exit_starts = d.get("exit_starts") or []
    for u in d.get("unassigns") or []:
        step = int(u.get("step", 0) or 0)
        ff = u.get("ff")
        prev = state_at(step - 1, ff)
        if prev is None:
            continue
        _ff, pos, status, assigned, exiting, dead = prev
        if not exiting:
            continue
        reason = u.get("reason")
        reason_all[reason] += 1
        dkey = key_run + (ff, u.get("vid"), step)
        reason_distinct[reason].add(dkey)
        # other units alive, on grid, not exiting at the previous step
        others = []
        for row in ffs[step - 2] if step - 2 < len(ffs) else []:
            if row[0] == ff:
                continue
            if row[5] or row[1] is None or row[4] or row[2] == "dead":
                continue
            others.append(row[0])
        # pickup cell for this carry
        es = [e for e in exit_starts if e.get("ff") == ff and e.get("victim") == u.get("vid") and int(e.get("step", 0)) <= step]
        pick = es[-1] if es else None
        rec = dict(file=n, tag=tag, step=step, ff=ff, vid=u.get("vid"),
                   reason=reason, pos_prev=pos, status_prev=status,
                   living_others=len(others), pickup=pick and (pick.get("step"), pick.get("ff_pos")))
        if reason and "isolat" in str(reason):
            escape_rows.append(rec)
        elif reason and "block" in str(reason):
            drop_rows.append(rec)
        else:
            other_rows.append(rec)

print("files scanned:", len(names), "with ff_steps:", files_with_ffsteps, "unreadable:", bad)
print("unassigns of a unit that was EXITING at the end of the previous step, by reason:")
for r, c in reason_all.most_common():
    print(f"  {r!r:45s} records={c:4d} distinct(wind,scen,seed,ff,vid,step)={len(reason_distinct[r])}")
print()
print("isolation-escape unassigns of an exiting carrier:")
for r in escape_rows:
    print("  ", r)
print()
print("non-block, non-isolation unassigns of an exiting unit:")
for r in other_rows:
    print("  ", r)
print()
print("route_blocked unassigns of an exiting carrier: records", len(drop_rows))
lo = Counter(r["living_others"] for r in drop_rows)
print("  living other units at the previous step:", dict(lo))
print("  distinct:", len({(r["file"].split("_", 3)[3] if r["file"].count("_") >= 3 else r["file"], r["ff"], r["vid"], r["step"]) for r in drop_rows}))
