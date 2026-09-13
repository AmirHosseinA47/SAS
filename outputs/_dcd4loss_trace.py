"""dcd4loss: per-victim / per-unit trace extractor for seed-matched harness arms.

Read-only over committed harness artifacts (outputs/_ffr_<tag>_<wind>_half_<seed>.json
and .stdout.txt). Runs no simulation.

INDEXING (verified, see --mode align): WildFireModel.step() increments
evaluation_timesteps_counter FIRST, so during step k the counter is k, and every
harness per-step list (uav_steps, ff_steps, victim_steps, ...) is appended after
model.step() returns: list index i is the POST-state of step i+1. Every step quoted
by this tool is the model step number (index + 1). Stdout decision lines that carry
a step (Victim Detection) use the same counter.

DECISIONS come from decision-site records, not snapshots:
  detection   stdout "[Victim Detection] step=k UAV-u detected v" (printed inside
              _detect_victims_in_uav_radius, first detection only)
  assign/unassign/mark_unreachable  harness REC wraps of apply_physical_rescue_command
  planner     harness wrap of select_rescue_assignment (pool sizes)
  completions / exit_starts / retargets   harness wrap of Firefighter.advance
  rtb         rtb_log (trigger_step, arrival_step, released_step per trip)
Snapshots (positions, statuses) are used for WHERE things were, and for the
status transitions that have no printed step (death, route_blocked), which are
stamped at the first post-state that shows them.

usage:
  _dcd4loss_trace.py --mode align    --wind south --seed 404 --tag drhD
  _dcd4loss_trace.py --mode victims  --wind south --seed 404 --tags drhZ,drhD
  _dcd4loss_trace.py --mode diverge  --wind south --seed 404 --a drhZ --b drhD
  _dcd4loss_trace.py --mode snapshot --wind south --seed 404 --tag drhD --step 160
  _dcd4loss_trace.py --mode victim   --wind south --seed 404 --tag drhD --vid victim_0
  _dcd4loss_trace.py --mode uavs     --wind south --seed 404 --tag drhD [--every 10]
  _dcd4loss_trace.py --mode ffs      --wind south --seed 404 --tag drhD
  _dcd4loss_trace.py --mode approach --wind south --seed 404 --tags drhZ,drhD --vid victim_0
  _dcd4loss_trace.py --mode stdout   --wind south --seed 404 --tag drhD
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RADIUS = 8  # common_fixed_variables.UAV_OBSERVATION_RADIUS (euclidean, <=)
_CACHE: dict = {}


def load(tag, wind, seed, roles="half"):
    key = (tag, wind, seed, roles)
    if key in _CACHE:
        return _CACHE[key]
    base = os.path.join(HERE, "_ffr_%s_%s_%s_%s" % (tag, wind, roles, seed))
    with open(base + ".json", "r", encoding="utf-8") as fh:
        d = json.load(fh)
    raw = open(base + ".stdout.txt", "rb").read()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    d["_stdout"] = raw.decode(enc).splitlines()
    _CACHE[key] = d
    return d


def stdout_events(d):
    """Stdout lines in order, each with the bracket of model steps it must lie in.

    Only Victim Detection lines carry an exact step. Monitoring (step=) and
    KnowledgeManager (t=) lines are anchors: a line between anchors a and b
    happened in a step s with a <= s <= b.
    """
    out = []
    last = 0
    pending = []
    for ln in d["_stdout"]:
        m = re.search(r"\[Victim Detection\] step=(\d+)", ln)
        a = re.search(r"\[Monitoring\] step=(\d+)", ln)
        k = re.search(r"\[KnowledgeManager\] t=(\d+)", ln)
        exact = int(m.group(1)) if m else None
        anchor = int(a.group(1)) if a else (int(k.group(1)) if k else None)
        if exact is not None:
            for p in pending:
                p["hi"] = exact
            pending = []
            out.append({"line": ln, "lo": exact, "hi": exact})
            last = exact
        elif anchor is not None:
            for p in pending:
                p["hi"] = anchor
            pending = []
            last = anchor
        else:
            e = {"line": ln, "lo": last, "hi": None}
            pending.append(e)
            out.append(e)
    for p in pending:
        p["hi"] = d["steps"]
    return out


def detections(d):
    res = {}
    for ln in d["_stdout"]:
        m = re.search(r"\[Victim Detection\] step=(\d+) UAV-(\S+) detected (\S+) at \((\d+), (\d+)\)", ln)
        if m:
            res.setdefault(m.group(3), (int(m.group(1)), m.group(2), (int(m.group(4)), int(m.group(5)))))
    return res


def rows_by_id(row):
    return {r[0]: r for r in row}


def victim_transitions(d, vid):
    tr = []
    prev = None
    for i, row in enumerate(d["victim_steps"]):
        r = rows_by_id(row).get(vid)
        st = r[2] if r else None
        if st != prev:
            tr.append((i + 1, st, r[1] if r else None))
            prev = st
    return tr


def final_status(d, vid):
    r = rows_by_id(d["victim_steps"][-1]).get(vid)
    return r[2] if r else None


def ff_transitions(d, ffid):
    tr = []
    prev = None
    for i, (row, brow) in enumerate(zip(d["ff_steps"], d["ff_bind_steps"])):
        r = rows_by_id(row).get(ffid)
        b = rows_by_id(brow).get(ffid)
        key = (r[2], r[3], r[4], r[5], b[1] if b else None, b[2] if b else None, b[4] if b else None)
        if key != prev:
            tr.append((i + 1, r[1], "status=%s assigned=%s exiting=%s dead=%s bound=%s avail=%s offgrid=%s" % key))
            prev = key
    return tr


def uav_runs(d, uid):
    """Compressed runs of (role, action, base_state) with start/end step and cells."""
    runs = []
    acts = d.get("uav_actions") or []
    for i, row in enumerate(d["uav_steps"]):
        u = rows_by_id(row)[uid]
        a = rows_by_id(acts[i])[uid] if i < len(acts) else [uid, "?"]
        key = (u[2], a[1], u[5])
        if runs and runs[-1]["key"] == key:
            runs[-1]["end"] = i + 1
            runs[-1]["to"] = u[1]
        else:
            runs.append({"key": key, "start": i + 1, "end": i + 1, "from": u[1], "to": u[1], "batt": u[4]})
    return runs


def mode_align(args):
    d = load(args.tag, args.wind, args.seed)
    det = detections(d)
    print("detection step (stdout) vs first post-state index whose marker status leaves 'candidate'")
    for vid, (k, u, cell) in sorted(det.items()):
        tr = victim_transitions(d, vid)
        first = next(((s, st) for s, st, _ in tr if st not in ("candidate", None)), None)
        print("  %s detected step=%d by UAV-%s at %s | first non-candidate post-state: step %s (%s)"
              % (vid, k, u, cell, first[0] if first else None, first[1] if first else None))
    print("assigns (harness step) vs first post-state with ff bound to that victim")
    for a in d["assigns"]:
        s0 = None
        for i, brow in enumerate(d["ff_bind_steps"]):
            b = rows_by_id(brow).get(a["ff"])
            if b and b[1] == a["vid"] and i + 1 >= a["step"]:
                s0 = i + 1
                break
        print("  assign step=%s %s->%s ok=%s reason=%s | bound in post-state of step %s" % (a["step"], a["ff"], a["vid"], a["ok"], a["reason"], s0))


def mode_victims(args):
    for tag in args.tags.split(","):
        d = load(tag, args.wind, args.seed)
        e = d["eval"]
        det = detections(d)
        print("== %s  rescued %s dead %s unreachable %s nd %s ffd %s terminal %s" % (
            tag, e["rescued"], e["dead"], e["unreachable"], e["never_detected"], e["firefighter_deaths"], e["terminal_step"]))
        vids = [r[0] for r in d["victim_steps"][0]]
        for vid in vids:
            tr = victim_transitions(d, vid)
            dt = det.get(vid)
            asg = [(a["step"], a["ff"], a["reason"], a["ok"]) for a in d["assigns"] if a["vid"] == vid]
            una = [(a["step"], a["ff"], a["reason"]) for a in d["unassigns"] if a["vid"] == vid]
            unr = [(a["step"], a["ff"], a["reason"]) for a in d["unreachable_marks"] if a["vid"] == vid]
            comp = [(c["step"], c["ff"]) for c in d["completions"] if c["victim"] == vid]
            print("  %s spawn %s final=%s" % (vid, d["victim_spawns"].get(vid), final_status(d, vid)))
            print("     detected: %s" % (("step %d by UAV-%s at %s" % dt) if dt else "NEVER (no stdout detection line)"))
            print("     status transitions (step, status, cell): %s" % tr)
            print("     assigns %s" % asg)
            if una:
                print("     unassigns %s" % una)
            if unr:
                print("     unreachable_marks %s" % unr)
            print("     completions %s" % comp)


def _cmp_rows(ra, rb):
    diffs = []
    ia, ib = rows_by_id(ra), rows_by_id(rb)
    for k in sorted(set(ia) | set(ib)):
        if ia.get(k) != ib.get(k):
            diffs.append((k, ia.get(k), ib.get(k)))
    return diffs


def mode_diverge(args):
    A = load(args.a, args.wind, args.seed)
    B = load(args.b, args.wind, args.seed)
    print("first divergence %s vs %s, %s/%s (model step = index+1)" % (args.a, args.b, args.wind, args.seed))
    fd = next((i for i, (x, y) in enumerate(zip(A["fire_digests"], B["fire_digests"])) if x != y), None)
    print("  fire_digests: %s" % ("IDENTICAL all %d steps" % len(A["fire_digests"]) if fd is None else "step %d" % (fd + 1)))
    for key in ("uav_steps", "uav_actions", "ff_steps", "ff_bind_steps", "victim_steps"):
        la, lb = A.get(key) or [], B.get(key) or []
        first = None
        for i, (x, y) in enumerate(zip(la, lb)):
            if x != y:
                first = i
                break
        if first is None:
            print("  %s: IDENTICAL over %d steps" % (key, min(len(la), len(lb))))
            continue
        print("  %s: first differs at step %d" % (key, first + 1))
        for k, xa, xb in _cmp_rows(la[first], lb[first]):
            print("      %s  %s: %s | %s: %s" % (k, args.a, xa, args.b, xb))
    pa, pb = A.get("partition_steps") or [], B.get("partition_steps") or []
    first = next((i for i, (x, y) in enumerate(zip(pa, pb)) if x != y), None)
    if first is None:
        print("  partition_steps: IDENTICAL")
    else:
        x, y = pa[first], pb[first]
        print("  partition_steps: first differs at step %d" % (first + 1))
        for sub in ("searchers", "lanes", "sectors", "targets"):
            if x.get(sub) != y.get(sub):
                print("      %s  %s: %s\n      %s  %s: %s" % (sub, args.a, x.get(sub), sub, args.b, y.get(sub)))
    # first differing decision records
    for key in ("assigns", "unassigns", "planner", "completions", "unreachable_marks"):
        la, lb = A.get(key) or [], B.get(key) or []
        first = next((i for i, (x, y) in enumerate(zip(la, lb)) if x != y), None)
        if first is None and len(la) == len(lb):
            print("  %s: IDENTICAL (%d records)" % (key, len(la)))
        else:
            j = first if first is not None else min(len(la), len(lb))
            print("  %s: first differing record #%d  %s: %s | %s: %s" % (
                key, j, args.a, la[j] if j < len(la) else None, args.b, lb[j] if j < len(lb) else None))
    da, db = detections(A), detections(B)
    order_a = sorted((v[0], k, v[1]) for k, v in da.items())
    order_b = sorted((v[0], k, v[1]) for k, v in db.items())
    print("  detections %s: %s" % (args.a, order_a))
    print("  detections %s: %s" % (args.b, order_b))


def mode_snapshot(args):
    d = load(args.tag, args.wind, args.seed)
    i = args.step - 1
    print("post-state of step %d, %s %s/%s" % (args.step, args.tag, args.wind, args.seed))
    acts = rows_by_id((d.get("uav_actions") or [[]] * (i + 1))[i]) if d.get("uav_actions") else {}
    parts = d.get("partition_steps") or []
    tg = (parts[i].get("targets") or {}) if i < len(parts) else {}
    lanes = (parts[i].get("lanes") or {}) if i < len(parts) else {}
    for u in d["uav_steps"][i]:
        a = acts.get(u[0], [None, None, None, None, None, None])
        print("  UAV %s %s role=%s batt=%s base=%r action=%s burning=%s fdist=%s target=%s lane=%s" % (
            u[0], u[1], u[2], u[4], u[5], a[1], a[2], a[5], tg.get(u[0]), lanes.get(u[0])))
    brow = rows_by_id(d["ff_bind_steps"][i])
    for f in d["ff_steps"][i]:
        b = brow.get(f[0])
        print("  FF  %s %s status=%s assigned=%s exiting=%s dead=%s bound=%s avail=%s" % (
            f[0], f[1], f[2], f[3], f[4], f[5], b[1] if b else None, b[2] if b else None))
    burning = set()
    for key, ivs in (d.get("burn_intervals") or {}).items():
        for s, e in ivs:
            if s <= args.step and (e is None or args.step < e):
                burning.add(tuple(int(v) for v in key.split(",")))
    for v in d["victim_steps"][i]:
        cell = v[1]
        fd = min((abs(cell[0] - x) + abs(cell[1] - y) for x, y in burning), default=None) if cell else None
        print("  VIC %s %s status=%s fire_manhattan=%s" % (v[0], cell, v[2], fd))
    print("  burning cells: %d" % len(burning))


def mode_victim(args):
    d = load(args.tag, args.wind, args.seed)
    vid = args.vid
    print("victim %s in %s %s/%s" % (vid, args.tag, args.wind, args.seed))
    print("  transitions: %s" % victim_transitions(d, vid))
    print("  detection: %s" % (detections(d).get(vid),))
    print("  flee moves: %s" % [(f["step"], f["from"], f["to"]) for f in d.get("victim_flee_log", []) if f.get("victim_id") == vid])
    print("  holds: %s" % [(h["step"], h["reason"], h.get("cell")) for h in d.get("victim_holds", []) if h.get("victim") == vid][:60])
    print("  retargets: %s" % [(r["step"], r["ff"], r["from"], r["to"]) for r in d["retargets"] if r["victim"] == vid])
    print("  planner records naming it: %s" % [p for p in d["planner"] if p["vid"] == vid])
    for ln in stdout_events(d):
        if vid in ln["line"]:
            print("  stdout [%s..%s] %s" % (ln["lo"], ln["hi"], ln["line"]))
    # which ff was bound per step
    prev = None
    for i, brow in enumerate(d["ff_bind_steps"]):
        bound = tuple(b[0] for b in brow if b[1] == vid)
        if bound != prev:
            print("  step %d bound units: %s" % (i + 1, list(bound)))
            prev = bound


def mode_uavs(args):
    d = load(args.tag, args.wind, args.seed)
    print("UAV runs %s %s/%s  (role, action, base_state) [start-end] from->to" % (args.tag, args.wind, args.seed))
    for u in d["uav_steps"][0]:
        uid = u[0]
        print(" UAV %s spawn %s" % (uid, u[1]))
        for r in uav_runs(d, uid):
            if r["end"] - r["start"] + 1 >= args.minrun or r["key"][2]:
                print("   [%3d-%3d] %-15s %-55s %-9s %s->%s batt0=%s" % (
                    r["start"], r["end"], r["key"][0], r["key"][1], r["key"][2], r["from"], r["to"], r["batt"]))
        if args.every:
            pts = [(i + 1, rows_by_id(row)[uid][1]) for i, row in enumerate(d["uav_steps"]) if (i + 1) % args.every == 0]
            print("   every %d: %s" % (args.every, pts))
    print(" rtb_log: %s" % json.dumps(d.get("rtb_log")))


def mode_ffs(args):
    d = load(args.tag, args.wind, args.seed)
    for f in d["ff_steps"][0]:
        print(" FF %s" % f[0])
        for s, cell, desc in ff_transitions(d, f[0]):
            print("   step %3d %s %s" % (s, cell, desc))
    print(" planner: %s" % d["planner"])
    print(" assigns: %s" % d["assigns"])
    print(" unassigns: %s" % d["unassigns"])
    print(" completions: %s" % d["completions"])


def mode_approach(args):
    """Per UAV: steps at which it was within RADIUS (euclidean) of the victim's
    recorded post-state cell, over steps 1..detection step INCLUSIVE (all 240
    steps if never detected), and the closest approach in that window (first
    occurrence on ties). Geometry only - detection itself is read from stdout.
    (An earlier draft scanned to detection+5; corrected after the verification
    pass caught it.)"""
    for tag in args.tags.split(","):
        d = load(tag, args.wind, args.seed)
        det = detections(d).get(args.vid)
        limit = det[0] if det else d["steps"]
        print("== %s %s detection=%s (window steps 1..%d)" % (tag, args.vid, det, limit))
        for u in d["uav_steps"][0]:
            uid = u[0]
            best = (1e9, None, None, None)
            within = []
            for i in range(0, min(limit, d["steps"])):
                ur = rows_by_id(d["uav_steps"][i])[uid]
                vr = rows_by_id(d["victim_steps"][i]).get(args.vid)
                if not vr or vr[1] is None or ur[1] is None:
                    continue
                dist = ((ur[1][0] - vr[1][0]) ** 2 + (ur[1][1] - vr[1][1]) ** 2) ** 0.5
                if dist < best[0]:
                    best = (dist, i + 1, ur[1], vr[1])
                if dist <= RADIUS:
                    within.append(i + 1)
            print("   UAV %s (%s) closest %s at step %s uav %s victim %s; within r=%d at steps %s" % (
                uid, u[2], round(best[0], 2), best[1], best[2], best[3], RADIUS, within[:20]))


def mode_stdout(args):
    d = load(args.tag, args.wind, args.seed)
    for e in stdout_events(d):
        if e["line"].startswith("[Monitoring]") or e["line"].startswith("[KnowledgeManager]"):
            continue
        print("[%s..%s] %s" % (e["lo"], e["hi"], e["line"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True)
    ap.add_argument("--wind", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--tag")
    ap.add_argument("--tags")
    ap.add_argument("--a")
    ap.add_argument("--b")
    ap.add_argument("--step", type=int)
    ap.add_argument("--vid")
    ap.add_argument("--every", type=int, default=0)
    ap.add_argument("--minrun", type=int, default=1)
    args = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    {"align": mode_align, "victims": mode_victims, "diverge": mode_diverge, "snapshot": mode_snapshot,
     "victim": mode_victim, "uavs": mode_uavs, "ffs": mode_ffs, "approach": mode_approach,
     "stdout": mode_stdout}[args.mode](args)


if __name__ == "__main__":
    main()
