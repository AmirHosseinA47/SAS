"""Ungated round, Part 3: WHY did the stock channel lose rescues on U30? Read-only.

For every victim rescued in the control (ugC) but not in the shipped arm (ugD) - and the
same for the positioning-only arm (ugY, whose fire is identical to ugC's on 30/30) - the
victim's timeline in BOTH arms, straight from the harness JSON:
  confirmed  first step the victim's status is no longer candidate
  assign     every ok assign of this victim: step, unit, the unit's manhattan distance to
             the victim at that step, and whether that unit was ENGAGED (firefight plan)
             on the assign step or the step before
  done       completion step (control), or the victim's status / the assigned unit's
             state and remaining distance at step 240 (feature)
Classifies each loss:
  HORIZON    still assigned at 240, the unit alive and closing: the rescue was late, not failed
  STUCK      still assigned at 240, the unit alive but not closing in its last 30 steps
  UNIT-DIED  the assigned unit died before completing
  UNREACH / DEAD / NOT-ASSIGNED   victim status at 240
Also: for every U30 tuple, the step of the FIRST ok assign in each arm and the step the
last victim was resolved, so the timing shift is visible beyond the lost victims.

  .venv/Scripts/python.exe -B outputs/_ug_loss_diag.py > outputs/_ug_loss_diag.txt
"""
from __future__ import annotations

import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _ug_analyze as U  # noqa: E402


def timeline(d, vid):
    vs = d.get("victim_steps") or []
    confirmed = next((i + 1 for i, row in enumerate(vs)
                      for v in row if v[0] == vid and v[2] not in ("candidate",)), None)
    pos_at = {}
    for i, row in enumerate(vs):
        for v in row:
            if v[0] == vid:
                pos_at[i + 1] = tuple(v[1]) if v[1] else None
    ffpos = collections.defaultdict(dict)
    for i, row in enumerate(d.get("ff_steps") or []):
        for ff, p, st, asg, ex, dead in row:
            ffpos[ff][i + 1] = (tuple(p) if p else None, st, asg, ex, dead)
    log = collections.defaultdict(dict)
    for r in d.get("firefight_log") or []:
        log[r["ff"]][r["step"]] = r
    assigns = []
    for a in d.get("assigns") or []:
        if a.get("ok") and a.get("vid") == vid:
            s, ff = a["step"], a["ff"]
            up = ffpos[ff].get(s - 1, ffpos[ff].get(s, (None,)))[0]
            vp = pos_at.get(s)
            dist = abs(up[0] - vp[0]) + abs(up[1] - vp[1]) if up and vp else None
            eng = bool((log[ff].get(s) or {}).get("engaged") or (log[ff].get(s - 1) or {}).get("engaged"))
            assigns.append((s, ff, dist, eng))
    done = next((c["step"] for c in (d.get("completions") or []) if c.get("victim") == vid), None)
    final = vs[-1] if vs else []
    status = next((v[2] for v in final if v[0] == vid), None)
    end = None
    if assigns and done is None:
        ff = assigns[-1][1]
        p240, st, asg, ex, dead = ffpos[ff].get(240, (None, None, None, None, None))
        vp = pos_at.get(240)
        d240 = abs(p240[0] - vp[0]) + abs(p240[1] - vp[1]) if p240 and vp else None
        p210 = ffpos[ff].get(210, (None,))[0]
        d210 = abs(p210[0] - vp[0]) + abs(p210[1] - vp[1]) if p210 and vp else None
        end = {"ff": ff, "ff_status": st, "dead": dead, "exiting": ex, "d240": d240, "d210": d210}
    return {"confirmed": confirmed, "assigns": assigns, "done": done, "status": status, "end": end}


def classify(tl):
    st = tl["status"]
    if st == "dead":
        return "DEAD"
    if st == "unreachable":
        return "UNREACH"
    if not tl["assigns"]:
        return "NOT-ASSIGNED (%s)" % st
    e = tl["end"] or {}
    if e.get("dead"):
        return "UNIT-DIED"
    if e.get("exiting"):
        return "HORIZON (carrying out at 240)"
    if e.get("d240") is not None and e.get("d210") is not None and e["d240"] < e["d210"]:
        return "HORIZON (closing: %s -> %s cells in the last 30 steps)" % (e["d210"], e["d240"])
    return "STUCK (%s -> %s cells in the last 30 steps, unit %s)" % (e.get("d210"), e.get("d240"), e.get("ff_status"))


def main():
    sys.stdout.reconfigure(newline="\n")
    print("WHY THE STOCK CHANNEL LOST RESCUES ON U30 (control ugC vs shipped ugD vs positioning-only ugY)")
    kinds = collections.Counter()
    for feat in ("ugD", "ugY"):
        print("\n" + "=" * 88)
        print("rescued in ugC, not in %s" % feat)
        print("=" * 88)
        for t in U.U30:
            a, b = U.load("ugC", t), U.load(feat, t)
            if a is None or b is None:
                continue
            va, vb = U.victims(a), U.victims(b)
            for vid in sorted(va):
                if va[vid] == "rescued" and vb.get(vid) != "rescued":
                    ta, tb = timeline(a, vid), timeline(b, vid)
                    k = classify(tb)
                    kinds[(feat, k.split(" (")[0])] += 1
                    print("%-26s %s" % (U.label(t), vid))
                    print("    control : confirmed %s  assigns %s  rescued at %s" % (
                        ta["confirmed"], [(s, f[-1], dd, "ENG" if e else "-") for s, f, dd, e in ta["assigns"]], ta["done"]))
                    print("    %-8s: confirmed %s  assigns %s  -> %s at 240   %s" % (
                        feat, tb["confirmed"], [(s, f[-1], dd, "ENG" if e else "-") for s, f, dd, e in tb["assigns"]],
                        tb["status"], k))
    print("\nLOSS KINDS: %s" % dict(kinds))
    print("\n" + "=" * 88)
    print("TIMING ACROSS ALL U30 TUPLES: first ok assign step and last-victim-resolved (terminal) step")
    print("=" * 88)
    fa = collections.defaultdict(list)
    for t in U.U30:
        row = []
        for tag in ("ugC", "ugY", "ugD"):
            S = U.S_(tag, t)
            d = U.load(tag, t)
            oks = [x["step"] for x in (d.get("assigns") or []) if x.get("ok")]
            f = min(oks) if oks else None
            fa[tag].append(f)
            row.append("%s first-assign %-4s terminal %-4s rescued %d" % (tag, f, S["terminal"], S["rescued"]))
        print("  %-26s %s" % (U.label(t), " | ".join(row)))
    for tag in ("ugC", "ugY", "ugD"):
        xs = [x for x in fa[tag] if x is not None]
        print("  %s first ok assign: mean %.1f over %d runs" % (tag, sum(xs) / len(xs), len(xs)))


if __name__ == "__main__":
    main()
