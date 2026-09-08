"""Classify each end-of-run route_blocked latch found in the _ffr_ arms.

The question per latch: at the moment the flag went up and stayed up, was there
still a LIVE victim (one neither dead, rescued nor unreachable) anywhere on the
grid? If no live victim remained for the whole tail, the revalidation pass at
wildfire_model.py:2523 returns at its `if not victim_cells: return` guard and
the flag has no referent - the D6-adjacent gap.

victim_steps rows are per-step lists of [vid, pos, status] (schema probed at
runtime and reported, so a mismatch is visible rather than silently wrong).
Read-only.
"""
import glob, json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
TERMINAL = {"dead", "rescued", "unreachable"}

targets = sys.argv[1:] or None


def victim_live(row):
    """row -> (vid, status) tolerant of a couple of recorded shapes."""
    if isinstance(row, dict):
        return str(row.get("id") or row.get("vid")), str(row.get("status") or "")
    if isinstance(row, (list, tuple)):
        vid = str(row[0])
        status = None
        for x in row[1:]:
            if isinstance(x, str):
                status = x
        return vid, str(status or "")
    return None, ""


printed_schema = False
for p in sorted(glob.glob(os.path.join(BASE, "_ffr_*.json"))):
    b = os.path.basename(p)[len("_ffr_"):-len(".json")]
    m = re.match(r"^([A-Za-z0-9]+)_(east|south|west|north)_([A-Za-z0-9]+)_(\d+)$", b)
    if not m:
        continue
    arm, wind, roles, seed = m.groups()
    if targets and arm not in targets:
        continue
    try:
        d = json.load(open(p))
    except Exception:
        continue
    ffs = d.get("ff_steps") or []
    vss = d.get("victim_steps") or []
    if not ffs:
        continue
    last = ffs[-1]
    latched = [r for r in last
               if len(r) >= 6 and str(r[2]).strip().lower() == "route_blocked" and not r[5]]
    if not latched:
        continue
    if not printed_schema and vss:
        print("victim_steps row schema sample: %s" % json.dumps(vss[-1])[:200])
        printed_schema = True
    n = min(len(ffs), len(vss)) if vss else 0
    for r in latched:
        uid = str(r[0])
        idx = None
        for i, row in enumerate(last):
            if str(row[0]) == uid:
                idx = i
        # first step of the terminal route_blocked run
        latch_from = len(ffs)
        for i in range(len(ffs), 0, -1):
            row = ffs[i - 1][idx] if idx is not None and idx < len(ffs[i - 1]) else None
            if row and str(row[2]).strip().lower() == "route_blocked":
                latch_from = i
            else:
                break
        live_tail = None
        if n:
            live_tail = 0
            for s in range(latch_from, n + 1):
                vrow = vss[s - 1]
                any_live = False
                for vr in (vrow or []):
                    _, st = victim_live(vr)
                    if st.strip().lower() not in TERMINAL:
                        any_live = True
                        break
                if any_live:
                    live_tail += 1
        shape = ("NO-REFERENT for whole tail" if live_tail == 0 else
                 "live victim present for %s of %s tail steps" % (live_tail, len(ffs) - latch_from + 1)
                 if live_tail is not None else "victim_steps unavailable")
        print("%-14s %-6s %-5s %-5s %-10s latch_from=%-4s tail=%-4s  %s" % (
            arm, wind, roles, seed, uid, latch_from, len(ffs) - latch_from + 1, shape))
