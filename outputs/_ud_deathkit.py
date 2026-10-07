"""Urgency round, the 22.9 per-death review: a READ-ONLY viewer over the committed screen records, so every reviewer
reads the same fields the same way. Nothing here classifies; it prints.

usage (run from the worktree root; <run> is a record file name in outputs/, e.g. _sd_ud2u4_B_N.json):
  _ud_deathkit.py cell  <cell id>                       e.g. set4/uniform/B_N - the four arms' deaths (from
                                                        _ud_deaths.json), first row difference vs arm 0
  _ud_deathkit.py unit  <run> <unit> [s0] [s1] [--boards <replay boards json>]
        per step: cell, status, bound victim, target, exiting / carrying / route_blocked flags, the mv row
        (branch, acted, clean distance dc, fire-free df, G-ESC, cell class pre/post, fire distance), the LIVE fix
        event at that step, the commands naming the unit; with --boards (a _ud_replay.py board file of the SAME
        run line): the cell's class on the decision board (B burning, A fire-adjacent, S smoky, C clean), the
        burning cells within Manhattan 3, and the clean BFS distance from the unit to its target on that board
  _ud_deathkit.py victim <run> <victim>                 detection, path, status changes, binds, kicks naming her,
                                                        U1 decisions, M8 entry, death
  _ud_deathkit.py diff  <runA> <runB> [unit]            the first step at which the rows (all, or one unit's) differ
  _ud_deathkit.py board <boards json> <step> <unit> [radius]   ASCII map around the unit on its decision board
rows_ff columns: unit, x, y, status, bound, exiting, dead, carrying, victim, target, rb, extra (step = index + 1).
"""
from __future__ import annotations

import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
_cache = {}


def load(name):
    p = name if os.path.isabs(name) or os.path.exists(name) else os.path.join(HERE, name)
    if p not in _cache:
        with open(p, encoding="utf-8") as fh:
            _cache[p] = json.load(fh)
    return _cache[p]


def mv_rows(d):
    cols = d["mv"]["cols"]
    return [dict(zip(cols, r)) for r in d["mv"]["rows"]]


def board_index(bd):
    by = {}
    for step, uid, pos, tgt, st, ex, dig in bd["decisions"]:
        by[(step, uid)] = (pos, tgt, st, ex, dig)
    return by


def board_sets(bd, dig):
    b = bd["boards"][dig]
    return {tuple(c) for c in b["burning"]}, {tuple(c) for c in b["smoky"]}


def cls(cell, burning, smoky):
    if cell in burning:
        return "B"
    if any((cell[0] + ox, cell[1] + oy) in burning for ox, oy in N4):
        return "A"
    if cell in smoky:
        return "S"
    return "C"


def clean_bfs(src, dst, burning, smoky, w, h):
    """BFS over CLEAN cells (src exempt); hops to dst or None."""
    if dst is None:
        return None
    dst = tuple(dst)
    seen = {tuple(src): 0}
    q = deque([tuple(src)])
    while q:
        c = q.popleft()
        if c == dst:
            return seen[c]
        for ox, oy in N4:
            n = (c[0] + ox, c[1] + oy)
            if n in seen or not (0 <= n[0] < w and 0 <= n[1] < h):
                continue
            if cls(n, burning, smoky) != "C":
                continue
            seen[n] = seen[c] + 1
            q.append(n)
    return None


def cmd_unit(d, unit):
    return [c for c in (d.get("dp") or {}).get("commands") or [] if c[4] == unit]


def do_unit(run, unit, s0=1, s1=360, boards=None):
    d = load(run)
    mv = {(r["step"], r["unit"]): r for r in mv_rows(d)}
    ev = {}
    for e in d.get("mv_events") or []:
        if e.get("unit") == unit and e.get("live"):
            ev.setdefault(e["step"], []).append("%s->%s(today %s)" % (e["kind"], e.get("taken"),
                                                                       (e.get("today") or [None, None])[1]))
    cmds = {}
    for c in cmd_unit(d, unit):
        cmds.setdefault(c[0], []).append("%s:%s %s %s" % (c[1], c[2], c[3], c[5]))
    bd = load(boards) if boards else None
    bi = board_index(bd) if bd else {}
    w, h = (bd["grid"] if bd and bd.get("grid") else (50, 50))
    print("step cell     status         victim    target    ex ca rb | mv branch    acted dc  df  gesc pre>post fd "
          "| fix | cmds" + (" | board: cell class, burning within 3, clean dist to target" if bd else ""))
    for t, row in enumerate(d["rows_ff"]):
        step = t + 1
        if step < s0 or step > s1:
            continue
        r = next((x for x in row if x[0] == unit), None)
        if r is None:
            continue
        m = mv.get((step, unit))
        mvs = "%-12s %-5s %-3s %-3s %-4s %s>%s %s" % (
            m["branch"], m["acted"] or "-", m["dc"], m["df"], "T" if m["gesc"] else "F", m["cls_pre"], m["cls_post"],
            m["fd_post"]) if m else "-"
        line = "%-4d %-8s %-14s %-9s %-9s %d  %d  %d  | %s | %s | %s" % (
            step, "(%s,%s)" % (r[1], r[2]), r[3], r[8] or "-", r[9] if r[9] else "-", r[5] or 0, r[7] or 0, r[10] or 0,
            mvs, ";".join(ev.get(step, [])) or "-", ";".join(cmds.get(step, [])) or "-")
        if bd:
            k = bi.get((step, unit))
            if k:
                pos, tgt, st, ex, dig = k
                burning, smoky = board_sets(bd, dig)
                near = sorted(c for c in burning if abs(c[0] - pos[0]) + abs(c[1] - pos[1]) <= 3)
                line += " | %s near%s %s dist %s" % (cls(tuple(pos), burning, smoky), len(near), near[:6],
                                                     clean_bfs(pos, tgt, burning, smoky, w, h))
        print(line)
        if r[6]:
            print("     ^ DEAD at step %d" % step)
            break


def do_victim(run, vid):
    d = load(run)
    prev = None
    det = None
    for t, row in enumerate(d["rows_vic"]):
        r = next((x for x in row if x[0] == vid), None)
        if r is None:
            continue
        key = (r[3], r[4], r[5])
        if key != prev:
            print("step %-4d cell (%s,%s) status %s / %s assigned %s flags %s" % (t + 1, r[1], r[2], r[3], r[4],
                                                                                r[5] or "-", r[6:]))
            prev = key
    for c in (d.get("dp") or {}).get("commands") or []:
        if c[3] == vid:
            print("cmd", c)
    for e in (d.get("dp") or {}).get("m8") or []:
        if e.get("victim") == vid:
            print("m8", e)
    for K in (d.get("ud") or {}).get("kicks") or []:
        if vid in [w[0] if isinstance(w, list) else w for w in (K.get("W") or [])]:
            print("kick step %s site %s qualifies %s index %s u1 %s bound %s rec %s" % (
                K.get("step"), K.get("site"), K.get("qualifies"), K.get("index"), K.get("u1"), K.get("bound"),
                (K.get("rec") or {}).get(vid)))
    for x in (d.get("ud") or {}).get("decisions") or []:
        if x.get("vid") == vid:
            print("decision", {k: x.get(k) for k in ("step", "T", "c", "d", "P", "served", "accepted", "pickup",
                                                      "death")})
    print("fate", ((d.get("ud") or {}).get("fates") or {}).get(vid))


def do_diff(ra, rb, unit=None):
    a, b = load(ra), load(rb)
    for k in ("rows_ff", "rows_vic", "rows_uav"):
        for t in range(min(len(a[k]), len(b[k]))):
            x, y = a[k][t], b[k][t]
            if unit and k == "rows_ff":
                x = [r for r in x if r[0] == unit]
                y = [r for r in y if r[0] == unit]
            elif unit:
                continue
            if x != y:
                print("%s first differs at step %d:\n  A %s\n  B %s" % (k, t + 1, x, y))
                break
        else:
            print("%s identical over %d steps" % (k, min(len(a[k]), len(b[k]))))


def do_board(boards, step, unit, radius=6):
    bd = load(boards)
    k = board_index(bd).get((step, unit))
    if not k:
        print("no decision of %s at step %d in %s" % (unit, step, boards))
        return
    pos, tgt, st, ex, dig = k
    burning, smoky = board_sets(bd, dig)
    w, h = bd["grid"]
    print("step %d %s at %s target %s status %s exiting %s; wind %s" % (step, unit, pos, tgt, st, ex, bd["wind"]))
    print("legend: U unit, V target, # burning, a fire-adjacent, s smoky, . clean; x across, y down")
    for y in range(pos[1] - radius, pos[1] + radius + 1):
        line = ""
        for x in range(pos[0] - radius, pos[0] + radius + 1):
            c = (x, y)
            if not (0 <= x < w and 0 <= y < h):
                line += " "
            elif list(c) == list(pos):
                line += "U"
            elif tgt and list(c) == list(tgt):
                line += "V"
            else:
                line += {"B": "#", "A": "a", "S": "s", "C": "."}[cls(c, burning, smoky)]
        print("  y=%-3d %s" % (y, line))


def do_cell(cell):
    with open(os.path.join(HERE, "_ud_deaths.json"), encoding="utf-8") as fh:
        T = json.load(fh)
    e = next((x for x in T if x["cell"] == cell), None)
    if e is None:
        print("no such cell")
        return
    print(cell, "seed", e["seed"])
    for arm, a in e["arms"].items():
        print(" arm %-2s %s rescued %s first_row_diff_vs_0 %s acted %s" % (arm, a["path"], a["rescued"],
                                                                          a.get("first_row_diff_vs_0"),
                                                                          a.get("acted_live")))
        for x in a["DD"]:
            print("    DD %s det %s death %s class %s flags %s m8 %s same_in_0 %s" % (
                x["victim"], x["det"], x["death"], x["cls"], x["flags"], x["m8"], x.get("same_in_0")))
        for x in a["ff"]:
            print("    FF %s death %s own live fixes %d last %s gap %s same_in_0 %s last_row %s" % (
                x["unit"], x["death"], x["n_fix_events"], x["last_fix_step"], x["gap_last_fix_to_death"],
                x.get("same_in_0"), x["last_row"]))
            print("       state changes", x["state_changes"])
            print("       commands", x["commands"])


def main():
    a = sys.argv[1:]
    boards = None
    if "--boards" in a:
        i = a.index("--boards")
        boards = a[i + 1]
        del a[i:i + 2]
    if not a:
        print(__doc__)
        return 2
    cmd = a[0]
    if cmd == "cell":
        do_cell(a[1])
    elif cmd == "unit":
        do_unit(a[1], a[2], int(a[3]) if len(a) > 3 else 1, int(a[4]) if len(a) > 4 else 360, boards)
    elif cmd == "victim":
        do_victim(a[1], a[2])
    elif cmd == "diff":
        do_diff(a[1], a[2], a[3] if len(a) > 3 else None)
    elif cmd == "board":
        do_board(a[1], int(a[2]), a[3], int(a[4]) if len(a) > 4 else 6)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
